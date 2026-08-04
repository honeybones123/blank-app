"""Audit Design Guide heading-without-card DOM states.

Proof-only. Captures whether FinalDesignGuidePublication/browser-state truth has
a primary card while the visible DOM only contains the Design Guide heading.
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
    _stable_hash,
    _stable_json,
    _wait_for_http,
)


ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _dom_audit(page, *, primary_titles: list[str]) -> dict[str, Any]:
    return dict(
        page.evaluate(
            r"""
            (primaryTitles) => {
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
              const all = Array.from(document.querySelectorAll("body *"));
              const bodyText = clean(document.body ? document.body.innerText : "");
              const titles = Array.from(primaryTitles || []).map(clean).filter(Boolean);
              const titleMatches = titles.length
                ? all.filter((el) => titles.some((title) => clean(el.innerText || el.textContent).includes(title))).slice(0, 20)
                : [];
              const matchedTitle = titles.find((title) => bodyText.includes(title)) || "";
              const dgHeadings = all.filter((el) => clean(el.innerText || el.textContent) === "Design Guide").slice(0, 20);
              const cardClassMatches = all.filter((el) => /fast-guidance|design-guide|final-publication|guidance-card/i.test(`${el.getAttribute ? el.getAttribute("data-testid") || "" : ""} ${String(el.className || "")}`)).slice(0, 40);
              const actionMatches = all.filter((el) => /Apply recommendation|Run one-click|Repair required|Governing utilisation|Design is efficient|Strengthening required|blocked|repair/i.test(clean(el.innerText || el.textContent))).slice(0, 40);
              const payload = (el) => {
                const rect = el.getBoundingClientRect();
                return {
                  tag: String(el.tagName || "").toLowerCase(),
                  visible: visible(el),
                  in_viewport: rect.bottom >= 0 && rect.top <= window.innerHeight,
                  text: clean(el.innerText || el.textContent).slice(0, 260),
                  testid: el.getAttribute ? el.getAttribute("data-testid") : null,
                  cls: String(el.className || "").slice(0, 180),
                  rect: {
                    top: Math.round(rect.top),
                    bottom: Math.round(rect.bottom),
                    height: Math.round(rect.height),
                    width: Math.round(rect.width)
                  }
                };
              };
              return {
                body_text_length: bodyText.length,
                body_contains_primary_title: !!matchedTitle,
                matched_primary_title: matchedTitle,
                primary_title_candidates: titles,
                body_contains_blocked: /blocked|repair/i.test(bodyText),
                design_guide_heading_count: dgHeadings.length,
                design_guide_headings: dgHeadings.map(payload),
                primary_title_match_count: titleMatches.length,
                primary_title_matches: titleMatches.map(payload),
                card_class_match_count: cardClassMatches.length,
                card_class_matches: cardClassMatches.map(payload),
                action_match_count: actionMatches.length,
                action_matches: actionMatches.map(payload),
                body_excerpt_after_design_guide: (() => {
                  const idx = bodyText.indexOf("Design Guide");
                  return idx >= 0 ? bodyText.slice(idx, idx + 800) : "";
                })()
              };
            }
            """,
            primary_titles,
        )
        or {}
    )


def _capture(base_url: str, *, recipe: str, headed: bool) -> dict[str, Any]:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=not headed)
        page = browser.new_page(viewport={"width": 1600, "height": 1100})
        page.set_default_timeout(30_000)
        url = _query(base_url, {"page": "inputs", "browser_recipe": recipe})
        page.goto(url, wait_until="domcontentloaded", timeout=90_000)
        page.wait_for_timeout(3500)
        state = _best_browser_state(page, recipe, timeout_s=10.0)
        dg_probe = dict(state.get("design_guide_probe") or {})
        debug_bundle = dict(dg_probe.get("debug_bundle") or {})
        verifier_payload = dict(debug_bundle.get("final_publication_verifier_payload") or {})
        display = dict(verifier_payload.get("display") or {})
        primary_titles = []
        for value in (
            display.get("title"),
            display.get("title_main"),
            verifier_payload.get("title"),
            verifier_payload.get("title_main"),
            dg_probe.get("primary_card_title"),
            debug_bundle.get("primary_card_title"),
            debug_bundle.get("selected_title"),
        ):
            text = str(value or "").strip()
            if text and text not in primary_titles:
                primary_titles.append(text)
        page.evaluate(
            r"""
            () => {
              const clean = (value) => String(value || "").replace(/\s+/g, " ").trim();
              const matches = Array.from(document.querySelectorAll("body *")).filter((el) => clean(el.innerText || el.textContent) === "Design Guide");
              const target = matches.find((el) => !/Debug/i.test(clean(el.parentElement ? el.parentElement.innerText || "" : ""))) || matches[0];
              if (target && target.scrollIntoView) target.scrollIntoView({block: "start", inline: "nearest"});
            }
            """
        )
        page.wait_for_timeout(700)
        dom = _dom_audit(page, primary_titles=primary_titles)
        browser.close()
    return {
        "url": url,
        "recipe": recipe,
        "browser_state_summary": {
            "browser_recipe": state.get("browser_recipe"),
            "browser_probe_phase": state.get("browser_probe_phase") or state.get("probe_phase"),
            "primary_card_title": primary_titles[0] if primary_titles else "",
            "primary_card_title_candidates": primary_titles,
            "primary_card_intent": dg_probe.get("primary_card_intent"),
            "button_contract_enabled": dg_probe.get("button_contract_enabled"),
            "button_contract_update_count": len(dict(dg_probe.get("button_contract_updates") or {})),
            "guidance_branch": dg_probe.get("guidance_branch"),
            "terminal_state": dg_probe.get("terminal_state"),
            "needs_refresh": dg_probe.get("needs_refresh"),
            "render_plan_debug": dg_probe.get("render_plan_debug"),
            "render_eligibility_trace": dg_probe.get("render_eligibility_trace"),
            "final_publication_authority_hash": debug_bundle.get("final_publication_authority_hash"),
            "final_publication_display_hash": debug_bundle.get("final_publication_display_hash"),
        },
        "dom": dom,
    }


def _classify(capture: dict[str, Any]) -> dict[str, Any]:
    state = dict(capture.get("browser_state_summary") or {})
    dom = dict(capture.get("dom") or {})
    has_publication_title = bool(state.get("primary_card_title"))
    title_in_dom = bool(dom.get("body_contains_primary_title"))
    has_heading = int(dom.get("design_guide_heading_count") or 0) > 0
    card_matches = int(dom.get("card_class_match_count") or 0)
    action_matches = int(dom.get("action_match_count") or 0)
    if has_publication_title and not title_in_dom and has_heading:
        diagnosis = "PUBLICATION_TITLE_NOT_EMITTED_AFTER_HEADING"
        next_slice = "Audit render_final_panel/_render_fast_design_guidance_panel item emission gate for this recipe."
    elif has_publication_title and title_in_dom:
        diagnosis = "VERIFIER_SELECTOR_GAP_CARD_TEXT_PRESENT"
        next_slice = "Tighten visual consistency selectors; product card text is present."
    elif not has_publication_title:
        diagnosis = "NO_PUBLICATION_TITLE_IN_BROWSER_STATE"
        next_slice = "Trace Design Guide publication generation before render."
    else:
        diagnosis = "NEEDS_MANUAL_REVIEW"
        next_slice = "Inspect DOM and render plan debug."
    return {
        "status": "PASS",
        "diagnosis": diagnosis,
        "has_publication_title": has_publication_title,
        "publication_title_in_dom": title_in_dom,
        "design_guide_heading_present": has_heading,
        "card_class_match_count": card_matches,
        "action_match_count": action_matches,
        "button_contract_enabled": state.get("button_contract_enabled"),
        "recommended_next_slice": next_slice,
    }


def _markdown(payload: dict[str, Any]) -> str:
    cls = dict(payload.get("classification") or {})
    state = dict(payload.get("browser_state_summary") or {})
    lines = [
        "# Design Guide Heading Without Card DOM Audit",
        "",
        f"- Status: `{payload.get('status')}`",
        f"- Diagnosis: `{cls.get('diagnosis')}`",
        f"- Product behaviour changed: `{payload.get('product_behaviour_changed')}`",
        f"- Primary title: `{state.get('primary_card_title')}`",
        f"- Title in DOM: `{cls.get('publication_title_in_dom')}`",
        f"- Heading present: `{cls.get('design_guide_heading_present')}`",
        f"- Card class matches: `{cls.get('card_class_match_count')}`",
        f"- Action matches: `{cls.get('action_match_count')}`",
        "",
        "## Next Safe Slice",
        "",
        str(cls.get("recommended_next_slice") or ""),
        "",
        "## DOM Excerpt",
        "",
        "```text",
        str((payload.get("dom") or {}).get("body_excerpt_after_design_guide") or "")[:1000],
        "```",
    ]
    return "\n".join(lines) + "\n"


def _write(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = str(payload["created_at"])
    json_path = ARTIFACT_DIR / f"design_guide_heading_without_card_dom_audit_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_heading_without_card_dom_audit_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    md_path.write_text(_markdown(payload), encoding="utf-8")
    return json_path, md_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8621)
    parser.add_argument("--base-url", default=os.environ.get("DESIGN_GUIDE_HEADING_WITHOUT_CARD_URL"))
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
            "schema": "design_guide_heading_without_card_dom_audit.v1",
            "created_at": created_at,
            "status": classification["status"],
            "product_behaviour_changed": False,
            "base_url": base_url,
            "classification": classification,
            "snapshot_hash": _stable_hash({"capture": capture, "classification": classification}),
            **capture,
        }
        json_path, md_path = _write(payload)
        print(f"wrote {json_path}")
        print(f"wrote {md_path}")
        print(json.dumps(classification, indent=2, sort_keys=True))
        return 0 if payload["status"] == "PASS" else 1
    finally:
        if process is not None:
            process.terminate()
            try:
                process.wait(timeout=10)
            except Exception:
                process.kill()


if __name__ == "__main__":
    raise SystemExit(main())
