"""Audit Design Guide render item emission against publication authority.

Proof-only. This browser/live verifier compares the Design Brain publication
title/display truth, the render bridge/debug item, and the visible DOM card.
It does not change rendering, publication, CTA/apply, family runtimes, visible
wording, or engineering behaviour.
"""

from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any

from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.verification.design_guide_rerun_trigger_source_profile import (  # noqa: E402
    DEFAULT_RECIPE,
    _best_browser_state,
    _query,
    _start_streamlit,
    _wait_for_http,
)


ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
INPUTS_PAGE = ROOT / "inputs_page.py"
DESIGN_GUIDE_PAGE = ROOT / "design_guide_page.py"


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _compact(value: Any, *, depth: int = 4, max_items: int = 20) -> Any:
    if depth < 0:
        if isinstance(value, (dict, list, tuple, set)):
            return f"<{type(value).__name__}>"
        return value
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for index, (key, item) in enumerate(value.items()):
            if index >= max_items:
                out["..."] = f"{len(value) - max_items} more"
                break
            out[str(key)] = _compact(item, depth=depth - 1, max_items=max_items)
        return out
    if isinstance(value, (list, tuple, set)):
        seq = list(value)
        out = [_compact(item, depth=depth - 1, max_items=max_items) for item in seq[:max_items]]
        if len(seq) > max_items:
            out.append(f"... {len(seq) - max_items} more")
        return out
    return value


def _find_key_values(value: Any, wanted: set[str], *, depth: int = 8, prefix: str = "$") -> dict[str, list[dict[str, Any]]]:
    found: dict[str, list[dict[str, Any]]] = {}
    if depth < 0:
        return found
    if isinstance(value, dict):
        for key, item in value.items():
            child = f"{prefix}.{key}"
            if str(key) in wanted and item not in (None, "", [], {}):
                found.setdefault(str(key), []).append({"path": child, "value": item})
            nested = _find_key_values(item, wanted, depth=depth - 1, prefix=child)
            for nested_key, rows in nested.items():
                found.setdefault(nested_key, []).extend(rows)
    elif isinstance(value, (list, tuple)):
        for index, item in enumerate(list(value)[:80]):
            nested = _find_key_values(item, wanted, depth=depth - 1, prefix=f"{prefix}[{index}]")
            for nested_key, rows in nested.items():
                found.setdefault(nested_key, []).extend(rows)
    return found


def _first_text(*values: Any) -> str:
    for value in values:
        if value is None:
            continue
        text = str(value).replace("\n", " ").strip()
        if text:
            return " ".join(text.split())
    return ""


def _source_line_number(path: Path, needle: str) -> int | None:
    try:
        text = path.read_text(encoding="utf-8")
    except Exception:
        return None
    index = text.find(needle)
    if index < 0:
        return None
    return text.count("\n", 0, index) + 1


def _static_source_map() -> dict[str, Any]:
    inputs = INPUTS_PAGE.read_text(encoding="utf-8")
    page = DESIGN_GUIDE_PAGE.read_text(encoding="utf-8")
    markers = {
        "render_final_panel": (DESIGN_GUIDE_PAGE, "def render_final_panel("),
        "render_fast_design_guidance_panel": (INPUTS_PAGE, "def _render_fast_design_guidance_panel("),
        "secondary_items_renderer": (INPUTS_PAGE, "def _render_guidance_secondary_items("),
        "card_view_model": (INPUTS_PAGE, "def build_design_guide_card_view_model("),
        "final_visible_authority_adapter": (INPUTS_PAGE, "def _final_visible_resolution_from_final_publication_authority("),
        "final_visible_publication_call": (INPUTS_PAGE, "_final_visible_resolution_from_final_publication_authority("),
    }
    return {
        "render_final_panel_calls_render_panel": "render_panel(sync_callbacks, inputs_render_audit)" in page,
        "render_fast_has_heading": 'st.markdown("### Design Guide")' in inputs,
        "render_fast_records_publication_snapshot": "_record_design_guide_publication_snapshot(" in inputs,
        "render_fast_uses_final_publication_adapter": "_final_visible_resolution_from_final_publication_authority(" in inputs,
        "secondary_items_uses_card_view_model": "build_design_guide_card_view_model(" in inputs,
        "line_numbers": {
            key: _source_line_number(path, needle)
            for key, (path, needle) in markers.items()
        },
    }


def _dom_projection(page) -> dict[str, Any]:
    return dict(
        page.evaluate(
            r"""
            () => {
              const clean = (value) => String(value || "").replace(/\s+/g, " ").trim();
              const visible = (el) => {
                if (!el || !el.getBoundingClientRect) return false;
                const style = window.getComputedStyle(el);
                const rect = el.getBoundingClientRect();
                return style.display !== "none"
                  && style.visibility !== "hidden"
                  && Number(style.opacity || "1") > 0.02
                  && rect.width > 2
                  && rect.height > 2;
              };
              const payload = (el) => {
                if (!el) return {exists: false, visible: false, text: ""};
                const rect = el.getBoundingClientRect();
                return {
                  exists: true,
                  visible: visible(el),
                  in_viewport: rect.bottom >= 0 && rect.top <= window.innerHeight,
                  text: clean(el.innerText || el.textContent),
                  testid: el.getAttribute ? el.getAttribute("data-testid") : null,
                  cls: String(el.className || ""),
                  rect: {
                    top: Math.round(rect.top),
                    bottom: Math.round(rect.bottom),
                    height: Math.round(rect.height),
                    width: Math.round(rect.width)
                  }
                };
              };
              const visibleEls = Array.from(document.querySelectorAll("body *")).filter(visible);
              const productHeadings = visibleEls.filter((el) => {
                const text = clean(el.innerText || el.textContent);
                if (text !== "Design Guide") return false;
                const parent = clean(el.parentElement ? el.parentElement.innerText || "" : "");
                return !/Design Guide Debug|Debug session state/i.test(parent);
              });
              const cards = Array.from(document.querySelectorAll('[data-testid="design-guide-card"], details.fast-guidance-item, .fast-guidance-item, .dg-card')).filter(visible);
              const titles = Array.from(document.querySelectorAll('[data-testid="design-guide-title"], .dg-title')).filter(visible);
              const statusPills = Array.from(document.querySelectorAll('[data-testid="design-guide-status-pill"], .dg-status-pill')).filter(visible);
              const buttons = visibleEls.filter((el) => {
                const tag = String(el.tagName || "").toLowerCase();
                const role = el.getAttribute ? String(el.getAttribute("role") || "") : "";
                const text = clean(el.innerText || el.textContent);
                return tag === "button" || role === "button" || /Apply|Run one-click|Repair required|Cleanup required/i.test(text);
              }).slice(0, 30);
              const firstCard = cards[0] || null;
              const firstTitle = titles.find((el) => firstCard && firstCard.contains(el)) || titles[0] || null;
              const firstStatus = statusPills.find((el) => firstCard && firstCard.contains(el)) || statusPills[0] || null;
              const bodyText = clean(document.body ? document.body.innerText : "");
              return {
                body_text_hash: bodyText ? bodyText.length + ":" + bodyText.slice(0, 120) : "",
                product_heading_count: productHeadings.length,
                product_headings: productHeadings.slice(0, 8).map(payload),
                card_count: cards.length,
                first_card: payload(firstCard),
                visible_card_titles: titles.slice(0, 12).map(payload),
                visible_status_pills: statusPills.slice(0, 12).map(payload),
                first_card_title: payload(firstTitle),
                first_card_status: payload(firstStatus),
                visible_buttons: buttons.map(payload),
              };
            }
            """
        )
        or {}
    )


def _browser_publication_projection(state: dict[str, Any]) -> dict[str, Any]:
    dg_probe = dict(state.get("design_guide_probe") or {})
    debug = dict(dg_probe.get("debug_bundle") or {})
    verifier_payload = dict(debug.get("final_publication_verifier_payload") or {})
    display = dict(verifier_payload.get("display") or {})
    cta = dict(verifier_payload.get("cta") or {})
    display_truth = dict(
        debug.get("displayed_primary_display_truth")
        or debug.get("primary_display_truth")
        or {}
    )
    button_contract = dict(
        debug.get("displayed_primary_button_contract")
        or debug.get("primary_button_contract")
        or debug.get("button_contract")
        or {}
    )
    key_values = _find_key_values(
        state,
        {
            "primary_card_title",
            "selected_title",
            "title_main",
            "title",
            "final_publication_display_hash",
            "final_publication_authority_hash",
            "displayed_primary_display_truth",
            "final_publication_verifier_payload",
        },
        depth=7,
    )
    return {
        "browser_recipe": state.get("browser_recipe"),
        "browser_probe_phase": state.get("browser_probe_phase") or state.get("probe_phase"),
        "probe_primary_title": _first_text(dg_probe.get("primary_card_title")),
        "debug_primary_title": _first_text(debug.get("primary_card_title")),
        "debug_selected_title": _first_text(debug.get("selected_title")),
        "publication_display_title": _first_text(
            display.get("title"),
            display.get("title_main"),
            verifier_payload.get("title"),
            verifier_payload.get("title_main"),
        ),
        "publication_title": _first_text(
            verifier_payload.get("title"),
            verifier_payload.get("title_main"),
            verifier_payload.get("published_item_id"),
        ),
        "display_truth_title": _first_text(display_truth.get("title"), display_truth.get("title_main")),
        "guidance_branch": dg_probe.get("guidance_branch") or debug.get("guidance_branch"),
        "render_plan_debug": _compact(dg_probe.get("render_plan_debug") or debug.get("render_plan_debug") or {}, depth=3),
        "button_contract": {
            "enabled": button_contract.get("enabled"),
            "actionable": button_contract.get("actionable"),
            "action_type": button_contract.get("action_type"),
            "family": button_contract.get("family"),
            "updates_count": len(dict(button_contract.get("updates") or {})),
            "blocking_reason": button_contract.get("blocking_reason"),
        },
        "cta": {
            "enabled": cta.get("enabled"),
            "actionable": cta.get("actionable"),
            "action_type": cta.get("action_type"),
            "updates_count": len(dict(cta.get("updates") or {})),
            "blocking_reason": cta.get("blocking_reason"),
        },
        "hashes": {
            "final_publication_authority_hash": debug.get("final_publication_authority_hash")
            or verifier_payload.get("final_publication_authority_hash"),
            "final_publication_display_hash": debug.get("final_publication_display_hash")
            or verifier_payload.get("final_publication_display_hash"),
            "publication_hash": debug.get("publication_hash") or verifier_payload.get("publication_hash"),
        },
        "title_key_samples": _compact(key_values, depth=4, max_items=8),
    }


def _capture(base_url: str, *, recipe: str, headed: bool) -> dict[str, Any]:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=not headed)
        page = browser.new_page(viewport={"width": 1600, "height": 1100})
        page.set_default_timeout(30_000)
        url = _query(base_url, {"page": "inputs", "browser_recipe": recipe})
        page.goto(url, wait_until="domcontentloaded", timeout=90_000)
        page.wait_for_timeout(3500)
        state = _best_browser_state(page, recipe, timeout_s=12.0)
        page.evaluate(
            r"""
            () => {
              const clean = (value) => String(value || "").replace(/\s+/g, " ").trim();
              const headings = Array.from(document.querySelectorAll("body *")).filter((el) => {
                const text = clean(el.innerText || el.textContent);
                if (text !== "Design Guide") return false;
                const parent = clean(el.parentElement ? el.parentElement.innerText || "" : "");
                return !/Design Guide Debug|Debug session state/i.test(parent);
              });
              const target = headings[headings.length - 1] || headings[0];
              if (target && target.scrollIntoView) target.scrollIntoView({block: "start", inline: "nearest"});
            }
            """
        )
        page.wait_for_timeout(800)
        dom = _dom_projection(page)
        browser.close()
    return {
        "url": url,
        "recipe": recipe,
        "browser_publication_projection": _browser_publication_projection(state),
        "dom_projection": dom,
        "browser_state_hash": _stable_hash(_compact(state, depth=5, max_items=25)),
    }


def _classify(capture: dict[str, Any]) -> dict[str, Any]:
    browser = dict(capture.get("browser_publication_projection") or {})
    dom = dict(capture.get("dom_projection") or {})
    dom_title = _first_text((dom.get("first_card_title") or {}).get("text"))
    publication_title = _first_text(
        browser.get("publication_display_title"),
        browser.get("probe_primary_title"),
        browser.get("debug_primary_title"),
        browser.get("debug_selected_title"),
    )
    probe_title = _first_text(browser.get("probe_primary_title"), browser.get("debug_primary_title"))
    card_count = int(dom.get("card_count") or 0)
    title_matches_publication = bool(publication_title and dom_title == publication_title)
    title_matches_probe = bool(probe_title and dom_title == probe_title)
    card_visible = bool((dom.get("first_card") or {}).get("visible"))
    if not publication_title:
        diagnosis = "NO_PUBLICATION_TITLE_AVAILABLE"
        next_slice = "Trace publication construction before render emission."
    elif card_count <= 0 or not card_visible:
        diagnosis = "PUBLICATION_AVAILABLE_CARD_NOT_VISIBLE"
        next_slice = "Audit render_panel/slot emission and card view-model creation."
    elif title_matches_publication:
        diagnosis = "PUBLICATION_TITLE_EMITTED"
        next_slice = "No title-emission fix needed; continue layout/performance profiling."
    elif dom_title and not title_matches_publication:
        diagnosis = "VISIBLE_CARD_TITLE_DIFFERS_FROM_PUBLICATION_TITLE"
        next_slice = (
            "Audit build_design_guide_card_view_model/title normalization and the "
            "render-time blocker title projection before changing wording."
        )
    else:
        diagnosis = "CARD_VISIBLE_TITLE_MISSING"
        next_slice = "Audit card view-model title field and DOM renderer title binding."
    return {
        "status": "PASS",
        "diagnosis": diagnosis,
        "publication_title": publication_title,
        "probe_title": probe_title,
        "dom_first_card_title": dom_title,
        "title_matches_publication": title_matches_publication,
        "title_matches_probe": title_matches_probe,
        "card_count": card_count,
        "card_visible": card_visible,
        "button_contract_enabled": (browser.get("button_contract") or {}).get("enabled"),
        "button_contract_updates_count": (browser.get("button_contract") or {}).get("updates_count"),
        "cta_enabled": (browser.get("cta") or {}).get("enabled"),
        "cta_updates_count": (browser.get("cta") or {}).get("updates_count"),
        "recommended_next_slice": next_slice,
    }


def _markdown(payload: dict[str, Any]) -> str:
    cls = dict(payload.get("classification") or {})
    browser = dict(payload.get("browser_publication_projection") or {})
    dom = dict(payload.get("dom_projection") or {})
    lines = [
        "# Design Guide Render Item Emission Gate Audit",
        "",
        f"- Status: `{payload.get('status')}`",
        f"- Diagnosis: `{cls.get('diagnosis')}`",
        f"- Product behaviour changed: `{payload.get('product_behaviour_changed')}`",
        f"- Publication title: `{cls.get('publication_title')}`",
        f"- Probe title: `{cls.get('probe_title')}`",
        f"- DOM first card title: `{cls.get('dom_first_card_title')}`",
        f"- Title matches publication: `{cls.get('title_matches_publication')}`",
        f"- Card count: `{cls.get('card_count')}`",
        f"- Card visible: `{cls.get('card_visible')}`",
        f"- Button contract enabled: `{cls.get('button_contract_enabled')}`",
        f"- CTA enabled: `{cls.get('cta_enabled')}`",
        "",
        "## Render Plan",
        "",
        "```json",
        json.dumps(browser.get("render_plan_debug") or {}, indent=2, sort_keys=True, default=str),
        "```",
        "",
        "## First Visible Card",
        "",
        "```json",
        json.dumps(dom.get("first_card") or {}, indent=2, sort_keys=True, default=str)[:2500],
        "```",
        "",
        "## Source Map",
        "",
        "```json",
        json.dumps(payload.get("static_source_map") or {}, indent=2, sort_keys=True, default=str),
        "```",
        "",
        "## Next Safe Slice",
        "",
        str(cls.get("recommended_next_slice") or ""),
        "",
    ]
    return "\n".join(lines) + "\n"


def _write(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = str(payload["created_at"])
    json_path = ARTIFACT_DIR / f"design_guide_render_item_emission_gate_audit_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_render_item_emission_gate_audit_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    md_path.write_text(_markdown(payload), encoding="utf-8")
    return json_path, md_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8622)
    parser.add_argument("--base-url", default=os.environ.get("DESIGN_GUIDE_RENDER_ITEM_EMISSION_URL"))
    parser.add_argument("--recipe", default=DEFAULT_RECIPE)
    parser.add_argument("--headed", action="store_true")
    args = parser.parse_args(argv)

    process: subprocess.Popen | None = None
    base_url = str(args.base_url or f"http://localhost:{args.port}")
    created_at = _stamp()
    try:
        if not args.base_url:
            env_before = dict(os.environ)
            os.environ["CODEX_BROWSER_TEST_MODE"] = "1"
            try:
                process = _start_streamlit(args.port)
            finally:
                os.environ.clear()
                os.environ.update(env_before)
            _wait_for_http(base_url, timeout_s=70.0)
        capture = _capture(base_url, recipe=str(args.recipe), headed=bool(args.headed))
        classification = _classify(capture)
        payload = {
            "schema": "design_guide_render_item_emission_gate_audit.v1",
            "created_at": created_at,
            "status": classification["status"],
            "classification": classification,
            "product_behaviour_changed": False,
            "behaviour_scope": {
                "rendering_changed": False,
                "publication_changed": False,
                "cta_apply_changed": False,
                "family_runtime_changed": False,
                "visible_wording_changed": False,
                "engineering_behaviour_changed": False,
            },
            "static_source_map": _static_source_map(),
            **capture,
        }
        json_path, md_path = _write(payload)
        print(f"wrote {json_path}")
        print(f"wrote {md_path}")
        print(json.dumps({"status": payload["status"], **classification}, indent=2, sort_keys=True))
        return 0
    finally:
        if process is not None:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()


if __name__ == "__main__":
    raise SystemExit(main())
