"""Browser/live audit for Design Guide card state and CTA consistency.

Proof-only. Captures visible summary cards, visible Design Guide card, Browser
state probes when available, CTA/display/publication evidence, and classifies
whether the card is stale, tone-mismatched, or missing/hidden an Apply CTA.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
from datetime import datetime
from typing import Any
from urllib.parse import urlencode

from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.verification.helpers.browser_helpers import _load_browser_state  # noqa: E402
from tools.verification.helpers.browser_one_click_regression import (  # noqa: E402
    _start_streamlit,
    _wait_for_http,
)


ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
DEFAULT_RECIPE = "R1A_M300_V0"


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _query(base_url: str, params: dict[str, Any]) -> str:
    return f"{base_url.rstrip('/')}/?{urlencode({key: value for key, value in params.items() if value is not None})}"


def _latest(prefix: str) -> dict[str, Any]:
    paths = sorted(ARTIFACT_DIR.glob(f"{prefix}_*.json"), key=lambda item: item.stat().st_mtime)
    if not paths:
        return {"found": False, "path": None, "status": None, "passed": False}
    path = paths[-1]
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {
            "found": True,
            "path": str(path),
            "status": "UNREADABLE",
            "passed": False,
            "error": f"{type(exc).__name__}: {exc}",
        }
    return {
        "found": True,
        "path": str(path),
        "status": payload.get("status"),
        "passed": payload.get("status") == "PASS",
        "snapshot_hash": payload.get("snapshot_hash") or payload.get("profile_hash"),
    }


def _float_or_none(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except Exception:
        pass
    text = str(value or "").replace(",", "").strip()
    match = re.search(r"[-+]?\d+(?:\.\d+)?", text)
    if not match:
        return None
    try:
        return float(match.group(0))
    except Exception:
        return None


def _norm_status(value: Any) -> str:
    text = str(value or "").strip().upper()
    if "FAIL" in text:
        return "FAIL"
    if "PASS" in text:
        return "PASS"
    if "NEAR" in text or "WARN" in text or "CHECK" in text:
        return "WARN"
    if "CAPACITY" in text:
        return "CAPACITY"
    if "NOT RUN" in text:
        return "NOT RUN"
    return text


def _families_from_text(text: str) -> dict[str, dict[str, Any]]:
    clean = " ".join(str(text or "").split())
    out: dict[str, dict[str, Any]] = {}
    family_patterns = {
        "bending": r"Bending(?:\s+[—-]\s+ULS)?\s+(?P<body>.{0,220}?)(?=Shear|Crack|Deflection|Preview|Why|$)",
        "shear": r"Shear(?:\s+[—-]\s+ULS)?\s+(?P<body>.{0,220}?)(?=Bending|Crack|Deflection|Preview|Why|$)",
        "crack": r"Crack(?: control)?(?:\s+[—-]\s+SLS)?\s+(?P<body>.{0,220}?)(?=Bending|Shear|Deflection|Preview|Why|$)",
        "deflection": r"Deflection(?:\s+[—-]\s+SLS)?\s+(?P<body>.{0,220}?)(?=Bending|Shear|Crack|Preview|Why|$)",
    }
    for family, pattern in family_patterns.items():
        match = re.search(pattern, clean, flags=re.IGNORECASE)
        if not match:
            continue
        body = match.group("body")
        status_match = re.search(r"\b(PASS|FAIL|NEAR LIMIT|WARN|CHECK|CAPACITY|NOT RUN)\b", body, flags=re.IGNORECASE)
        util = None
        util_match = re.search(r"(?:Utilisation|utilisation)\s+([-+]?\d+(?:\.\d+)?)", body, flags=re.IGNORECASE)
        if util_match:
            util = _float_or_none(util_match.group(1))
        else:
            # Current rows in the Design Guide card are usually compact:
            # "Bending 1.33 FAIL".
            compact_match = re.search(r"\b([-+]?\d+(?:\.\d+)?)\s+(?:PASS|FAIL|NEAR LIMIT|WARN|CHECK)\b", body, flags=re.IGNORECASE)
            if compact_match:
                util = _float_or_none(compact_match.group(1))
        out[family] = {
            "util": util,
            "status": _norm_status(body if status_match else ""),
            "text": body[:220],
        }
    return out


def _snapshot_visible_dom(page) -> dict[str, Any]:
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
              const rectPayload = (el) => {
                if (!el || !el.getBoundingClientRect || !visible(el)) return null;
                const rect = el.getBoundingClientRect();
                return {
                  top: Math.round(rect.top),
                  bottom: Math.round(rect.bottom),
                  left: Math.round(rect.left),
                  right: Math.round(rect.right),
                  width: Math.round(rect.width),
                  height: Math.round(rect.height)
                };
              };
              const summaryCards = Array.from(document.querySelectorAll(".summary-check-card")).filter(visible).map((el) => ({
                text: clean(el.innerText || el.textContent),
                cls: String(el.className || ""),
                rect: rectPayload(el)
              }));
              const allCandidates = Array.from(document.querySelectorAll(
                "[data-testid='design-guide-card'], .fast-guidance-item, [data-testid*='design-guide' i], section, div"
              )).filter(visible);
              const cardSignature = /Design is|Strengthening required|Design Guide blocker|repair proof incomplete|cleanup proof incomplete|Why action is required|Why repair is blocked|Preview after proposed change/i;
              const cardContent = /Bending|Shear|Current|Preview|Apply|Strengthening|required|ERROR|proof incomplete/i;
              const bodyTextFull = clean(document.body ? document.body.innerText : "");
              const dgOptions = allCandidates.map((el) => {
                const text = clean(el.innerText || el.textContent);
                const rect = rectPayload(el);
                if (!rect || !cardSignature.test(text) || !cardContent.test(text)) return null;
                const className = String(el.className || "");
                let score = (rect.width * rect.height) / 1000;
                if (rect.height > window.innerHeight * 0.82 || text.length > 4500 || /\bstApp\b/.test(className)) score += 10000;
                if (/Current/i.test(text)) score -= 800;
                if (/Preview after proposed change|Why action is required|Why repair is blocked/i.test(text)) score -= 500;
                if (/fast-guidance|design-guide/i.test(className)) score -= 300;
                if (rect.width < 300 || rect.height < 35) score += 2000;
                return { el, score };
              }).filter(Boolean).sort((a, b) => a.score - b.score);
              const dg = dgOptions.length ? dgOptions[0].el : null;
              const dgRect = dg ? rectPayload(dg) : null;
              const dgIsWholeApp = !!(dg && (/\bstApp\b/.test(String(dg.className || "")) || (dgRect && dgRect.height > window.innerHeight * 0.82)));
              const bodyWindow = (() => {
                const match = bodyTextFull.match(/Design Guide\s+(?:PASS|ACTION|BLOCKED|ERROR|WARN|NEXT)\s+[\s\S]*?(?=\s+Design mode|\s+Design Actions|\s+Positive design moment|\s+Geometry & Materials|$)/i);
                return match ? clean(match[0]) : "";
              })();
              const dgText = (dg && !dgIsWholeApp) ? clean(dg.innerText || dg.textContent) : bodyWindow;
              const buttons = Array.from(document.querySelectorAll("button")).filter(visible).map((el) => ({
                text: clean(el.innerText || el.textContent),
                disabled: !!el.disabled || el.getAttribute("aria-disabled") === "true",
                cls: String(el.className || ""),
                rect: rectPayload(el)
              }));
              const pills = dg ? Array.from(dg.querySelectorAll("span, div, button")).filter(visible).map((el) => {
                const text = clean(el.innerText || el.textContent);
                const rect = rectPayload(el);
                if (!text || text.length > 80 || !rect) return null;
                const style = window.getComputedStyle(el);
                return {
                  text,
                  cls: String(el.className || ""),
                  background: style.backgroundColor,
                  color: style.color,
                  rect
                };
              }).filter(Boolean).slice(0, 80) : [];
              return {
                url: window.location.href,
                body_text_sample: clean(document.body ? document.body.innerText : "").slice(0, 2000),
                summary_cards: summaryCards,
                summary_text: summaryCards.map((item) => item.text).join(" | "),
                design_guide_card: dgText ? {
                  text: dgText,
                  cls: dg && !dgIsWholeApp ? String(dg.className || "") : "body-window-design-guide-card",
                  rect: dg && !dgIsWholeApp ? rectPayload(dg) : null,
                } : null,
                design_guide_pills: pills,
                visible_buttons: buttons,
                visible_apply_like_buttons: buttons.filter((item) => /Apply|Run one-click|Strengthen|Repair|Improve/i.test(item.text || "")),
                constraints_text_present: /Constraints:\s*none/i.test(clean(document.body ? document.body.innerText : "")),
                design_guide_loading_shell_present: /Design Guide\s+Checking design guidance/i.test(clean(document.body ? document.body.innerText : "")),
              };
            }
            """
        )
        or {}
    )


def _wait_for_visible_card(page, timeout_s: float | None = None) -> dict[str, Any]:
    if timeout_s is None:
        timeout_s = float(os.environ.get("DESIGN_GUIDE_CARD_STATE_AUDIT_TIMEOUT") or "45")
    started = time.perf_counter()
    latest: dict[str, Any] = {}
    while time.perf_counter() - started <= timeout_s:
        latest = _snapshot_visible_dom(page)
        if latest.get("design_guide_card") and latest.get("summary_cards"):
            return latest
        time.sleep(0.35)
    return latest


def _try_load_browser_state(page, timeout_s: float = 5.0) -> tuple[dict[str, Any], str | None]:
    try:
        return dict(_load_browser_state(page, timeout_s=timeout_s) or {}), None
    except Exception as exc:
        return {}, f"{type(exc).__name__}: {exc}"


def _state_digest(state: dict[str, Any]) -> dict[str, Any]:
    summary_overview = dict(state.get("summary_overview_probe") or {})
    design_probe = dict(state.get("design_guide_probe") or {})
    debug_bundle = dict(design_probe.get("debug_bundle") or {})
    final_payload = dict(debug_bundle.get("final_publication_verifier_payload") or {})
    actual_render = dict(debug_bundle.get("actual_card_render_probe") or {})
    button_contract = dict(
        debug_bundle.get("displayed_primary_button_contract")
        or debug_bundle.get("primary_button_contract")
        or design_probe.get("primary_button_contract")
        or {}
    )
    display_truth = dict(
        debug_bundle.get("displayed_primary_display_truth")
        or debug_bundle.get("primary_display_truth")
        or design_probe.get("primary_display_truth")
        or {}
    )
    binding = dict(state.get("design_guide_primary_payload_binding_audit") or {})
    return {
        "summary_overview_utils": dict(summary_overview.get("utils") or {}),
        "summary_overview_statuses": dict(summary_overview.get("statuses") or {}),
        "summary_overview_governing_util": summary_overview.get("governing_util"),
        "design_guide_overview_utils": dict(design_probe.get("overview_utils") or {}),
        "design_guide_overview_statuses": dict(design_probe.get("overview_statuses") or {}),
        "design_guide_primary_title": design_probe.get("primary_card_title"),
        "design_guide_primary_current_util": design_probe.get("primary_current_util"),
        "design_guide_primary_preview_util": design_probe.get("primary_preview_util"),
        "display_truth": display_truth,
        "button_contract": button_contract,
        "button_contract_enabled": bool(
            button_contract.get("enabled")
            or button_contract.get("actionable")
            or design_probe.get("button_contract_enabled")
        ),
        "button_contract_updates": dict(button_contract.get("updates") or design_probe.get("button_contract_updates") or {}),
        "payload_binding_audit": binding,
        "final_publication": {
            "publication_hash": final_payload.get("publication_hash"),
            "outcome_state": final_payload.get("outcome_state"),
            "selected_family": final_payload.get("selected_family"),
            "published_item_id": final_payload.get("published_item_id"),
            "cta_hash": (final_payload.get("cta") or {}).get("cta_hash") if isinstance(final_payload.get("cta"), dict) else final_payload.get("cta_hash"),
            "display_hash": (final_payload.get("display") or {}).get("display_hash") if isinstance(final_payload.get("display"), dict) else final_payload.get("display_hash"),
        },
        "actual_card_render_probe": actual_render,
        "debug_bundle_keys": sorted(debug_bundle.keys())[:120],
    }


def _compare_family_maps(left: dict[str, dict[str, Any]], right: dict[str, dict[str, Any]]) -> dict[str, Any]:
    rows: dict[str, Any] = {}
    mismatches = []
    for family in sorted(set(left) | set(right)):
        lrow = dict(left.get(family) or {})
        rrow = dict(right.get(family) or {})
        lutil = _float_or_none(lrow.get("util"))
        rutil = _float_or_none(rrow.get("util"))
        util_delta = None if lutil is None or rutil is None else round(abs(lutil - rutil), 4)
        status_match = (
            not lrow.get("status")
            or not rrow.get("status")
            or _norm_status(lrow.get("status")) == _norm_status(rrow.get("status"))
        )
        util_match = util_delta is None or util_delta <= 0.03
        row = {
            "summary": lrow,
            "design_guide": rrow,
            "util_delta": util_delta,
            "util_match": util_match,
            "status_match": status_match,
        }
        rows[family] = row
        if not util_match or not status_match:
            mismatches.append(family)
    return {"rows": rows, "mismatched_families": mismatches}


def _classify(visible: dict[str, Any], browser_state: dict[str, Any], browser_state_error: str | None) -> dict[str, Any]:
    summary_visible = _families_from_text(str(visible.get("summary_text") or ""))
    dg_text = str((visible.get("design_guide_card") or {}).get("text") or "")
    current_section = dg_text
    if "Current" in dg_text and "Preview after proposed change" in dg_text:
        current_section = dg_text.split("Current", 1)[1].split("Preview after proposed change", 1)[0]
    dg_visible_current = _families_from_text(current_section)
    visible_compare = _compare_family_maps(summary_visible, dg_visible_current)

    state = _state_digest(browser_state) if browser_state else {}
    summary_probe_map = {
        family: {"util": util, "status": (state.get("summary_overview_statuses") or {}).get(family)}
        for family, util in (state.get("summary_overview_utils") or {}).items()
    }
    dg_probe_map = {
        family: {"util": util, "status": (state.get("design_guide_overview_statuses") or {}).get(family)}
        for family, util in (state.get("design_guide_overview_utils") or {}).items()
    }
    probe_compare = _compare_family_maps(summary_probe_map, dg_probe_map) if browser_state else {
        "rows": {},
        "mismatched_families": [],
    }

    card = dict(visible.get("design_guide_card") or {})
    card_text = str(card.get("text") or "")
    button_contract_enabled = bool(state.get("button_contract_enabled")) if state else None
    apply_like_buttons = list(visible.get("visible_apply_like_buttons") or [])
    enabled_apply_like_buttons = [button for button in apply_like_buttons if not button.get("disabled")]
    action_pills = [
        pill for pill in list(visible.get("design_guide_pills") or [])
        if re.search(r"\bACTION\b|Governing utilisation", str(pill.get("text") or ""), flags=re.IGNORECASE)
    ]
    card_is_red = "fail" in str(card.get("cls") or "").lower() or "rgb(255" in _stable_json(card).lower()
    blue_action_on_red = bool(card_is_red and action_pills)
    action_card_without_visible_enabled_button = bool(
        re.search(r"\bACTION\b|Strengthening required|repair required", card_text, flags=re.IGNORECASE)
        and not enabled_apply_like_buttons
    )
    visible_mismatch = bool(visible_compare.get("mismatched_families"))
    probe_mismatch = bool(probe_compare.get("mismatched_families"))
    browser_state_available = bool(browser_state and not browser_state_error)
    loading_shell_present = bool(visible.get("design_guide_loading_shell_present"))
    likely_source = "no_mismatch_detected"
    if loading_shell_present and not card:
        likely_source = "design_guide_loading_or_stale_shell_timeout"
    elif visible_mismatch and browser_state_available and probe_mismatch:
        likely_source = "summary_and_design_guide_probe_state_mismatch"
    elif visible_mismatch and browser_state_available and not probe_mismatch:
        likely_source = "visible_render_model_or_dom_stale_mismatch"
    elif visible_mismatch and not browser_state_available:
        likely_source = "visible_mismatch_browser_state_unavailable"
    elif action_card_without_visible_enabled_button:
        likely_source = "cta_enabled_or_visibility_mismatch"
    elif blue_action_on_red:
        likely_source = "card_tone_pill_style_mismatch"

    return {
        "browser_state_available": browser_state_available,
        "browser_state_error": browser_state_error,
        "summary_visible": summary_visible,
        "design_guide_visible_current": dg_visible_current,
        "visible_summary_vs_design_guide": visible_compare,
        "summary_probe_vs_design_guide_probe": probe_compare,
        "button_contract_enabled": button_contract_enabled,
        "visible_apply_like_button_count": len(apply_like_buttons),
        "visible_enabled_apply_like_button_count": len(enabled_apply_like_buttons),
        "action_card_without_visible_enabled_button": action_card_without_visible_enabled_button,
        "blue_action_on_red_card": blue_action_on_red,
        "constraints_none_visible": bool(visible.get("constraints_text_present")),
        "design_guide_loading_shell_present": loading_shell_present,
        "likely_source": likely_source,
        "requires_fix": bool(
            (loading_shell_present and not card)
            or
            visible_mismatch
            or probe_mismatch
            or action_card_without_visible_enabled_button
            or blue_action_on_red
        ),
        "recommended_next_step": (
            "Investigate why the live Design Guide remains on the checking shell and Browser-state proof is unavailable."
            if loading_shell_present and not card
            else "Fix the publication/render handoff that lets visible Design Guide current rows differ from the visible summary."
            if visible_mismatch
            else (
                "Fix CTA visibility/binding for actionable cards."
                if action_card_without_visible_enabled_button
                else (
                    "Fix card tone/pill style derivation."
                    if blue_action_on_red
                    else "No live card/CTA inconsistency found in this sample."
                )
            )
        ),
    }


def _escape_md(value: str) -> str:
    return value.replace("|", "\\|")


def _write_report(payload: dict[str, Any], path: Path) -> None:
    classification = dict(payload.get("classification") or {})
    state = dict(payload.get("browser_state_digest") or {})
    lines = [
        "# Design Guide Live Card State / CTA Consistency Audit",
        "",
        f"Status: `{payload['status']}`",
        f"Target URL: `{payload['target_url']}`",
        f"Product behaviour changed: `{payload['product_behaviour_changed']}`",
        "",
        "## Executive Summary",
        "",
        f"- Browser state available: `{classification.get('browser_state_available')}`",
        f"- Likely source: `{classification.get('likely_source')}`",
        f"- Requires fix: `{classification.get('requires_fix')}`",
        f"- Visible Apply-like buttons: `{classification.get('visible_apply_like_button_count')}`",
        f"- Visible enabled Apply-like buttons: `{classification.get('visible_enabled_apply_like_button_count')}`",
        f"- Design Guide loading shell present: `{classification.get('design_guide_loading_shell_present')}`",
        f"- Action card without visible enabled button: `{classification.get('action_card_without_visible_enabled_button')}`",
        f"- Blue action/governing pills on red card: `{classification.get('blue_action_on_red_card')}`",
        "",
        "## Visible Summary vs Design Guide Current Rows",
        "",
        "| Family | Summary util/status | Design Guide util/status | Delta | Match |",
        "| --- | --- | --- | ---: | --- |",
    ]
    rows = dict((classification.get("visible_summary_vs_design_guide") or {}).get("rows") or {})
    for family, row in rows.items():
        row = dict(row or {})
        summary = dict(row.get("summary") or {})
        dg = dict(row.get("design_guide") or {})
        lines.append(
            f"| `{family}` | `{summary.get('util')}` / `{summary.get('status')}` | `{dg.get('util')}` / `{dg.get('status')}` | `{row.get('util_delta')}` | util=`{row.get('util_match')}`, status=`{row.get('status_match')}` |"
        )
    lines.extend(["", "## Publication / CTA Digest", ""])
    lines.append(f"- Final publication: `{json.dumps(state.get('final_publication') or {}, sort_keys=True, default=str)}`")
    lines.append(f"- Button contract enabled: `{state.get('button_contract_enabled')}`")
    lines.append(f"- Button contract updates: `{json.dumps(state.get('button_contract_updates') or {}, sort_keys=True, default=str)}`")
    lines.append(f"- Payload binding audit: `{json.dumps(state.get('payload_binding_audit') or {}, sort_keys=True, default=str)[:500]}`")
    lines.extend(["", "## Recommendation", "", str(classification.get("recommended_next_step") or "")])
    if payload.get("failures"):
        lines.extend(["", "## Failures", ""])
        for failure in payload["failures"]:
            lines.append(f"- `{failure}`")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    recipe = os.environ.get("DESIGN_GUIDE_CARD_STATE_AUDIT_RECIPE") or DEFAULT_RECIPE
    explicit_url = (os.environ.get("DESIGN_GUIDE_CARD_STATE_AUDIT_URL") or "").strip()
    port = int(os.environ.get("DESIGN_GUIDE_CARD_STATE_AUDIT_PORT") or "8543")
    base_url = f"http://127.0.0.1:{port}"
    target_url = explicit_url or _query(base_url, {"page": "inputs", "browser_recipe": recipe})
    process: subprocess.Popen | None = None
    started_own_server = False
    errors: list[str] = []
    visible: dict[str, Any] = {}
    browser_state: dict[str, Any] = {}
    browser_state_error: str | None = None

    try:
        if not explicit_url:
            started_own_server = True
            env_before = dict(os.environ)
            os.environ["CODEX_BROWSER_TEST_MODE"] = "1"
            os.environ["CODEX_RENDER_TIMING_TRACE"] = "1"
            os.environ["AUTO_DESIGN_SPEED_PROFILE"] = "1"
            try:
                process = _start_streamlit(port)
            finally:
                os.environ.clear()
                os.environ.update(env_before)
            _wait_for_http(base_url)
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            context = browser.new_context(viewport={"width": 1920, "height": 1080})
            page = context.new_page()
            page.set_default_timeout(30_000)
            page.goto(target_url, wait_until="domcontentloaded", timeout=90_000)
            visible = _wait_for_visible_card(page)
            browser_state, browser_state_error = _try_load_browser_state(
                page,
                timeout_s=10.0 if started_own_server else 2.0,
            )
            if browser_state:
                # Re-sample once after Browser state is attached, so DOM and
                # proof payload are from the same settled paint where possible.
                page.wait_for_timeout(250)
                visible = _snapshot_visible_dom(page)
            context.close()
            browser.close()
    except Exception as exc:
        errors.append(f"{type(exc).__name__}: {exc}")
    finally:
        if process is not None:
            process.terminate()
            try:
                process.wait(timeout=10)
            except Exception:
                process.kill()

    classification = _classify(visible, browser_state, browser_state_error)
    browser_state_digest = _state_digest(browser_state) if browser_state else {}
    supporting_artifacts = {
        "render_bridge_lock": _latest("design_guide_render_bridge_lock"),
        "compute_resolver_publication_bridge_lock": _latest("design_guide_compute_resolver_publication_bridge_lock"),
        "design_guide_independence_lock": _latest("design_guide_independence_lock"),
    }
    failures: list[str] = []
    if not visible.get("summary_cards"):
        failures.append("visible_summary_cards_not_found")
    if not visible.get("design_guide_card"):
        failures.append("visible_design_guide_card_not_found")
    if classification.get("design_guide_loading_shell_present") and not visible.get("design_guide_card"):
        failures.append("design_guide_loading_shell_timeout")
    for name, artifact in supporting_artifacts.items():
        if artifact.get("passed") is not True:
            failures.append(f"{name}_not_passed")
    if errors:
        failures.extend(f"browser_error::{error}" for error in errors)
    status = "PASS" if not failures else "FAIL"
    payload: dict[str, Any] = {
        "schema": "design_guide_live_card_state_cta_consistency_audit.v1",
        "status": status,
        "created_at": stamp,
        "recipe": recipe,
        "target_url": target_url,
        "started_own_server": started_own_server,
        "product_behaviour_changed": False,
        "code_changed": False,
        "visible": visible,
        "browser_state_available": bool(browser_state),
        "browser_state_error": browser_state_error,
        "browser_state_digest": browser_state_digest,
        "classification": classification,
        "supporting_artifacts": supporting_artifacts,
        "errors": errors,
        "failures": failures,
    }
    payload["audit_hash"] = _stable_hash(
        {
            "target_url": target_url,
            "visible": visible,
            "browser_state_digest": browser_state_digest,
            "classification": classification,
            "errors": errors,
        }
    )
    artifact_path = ARTIFACT_DIR / f"design_guide_live_card_state_cta_consistency_audit_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_live_card_state_cta_consistency_audit_{stamp}.md"
    artifact_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    _write_report(payload, report_path)
    print(
        json.dumps(
            {
                "status": status,
                "artifact": str(artifact_path),
                "report": str(report_path),
                "likely_source": classification.get("likely_source"),
                "requires_fix": classification.get("requires_fix"),
            },
            indent=2,
        )
    )
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
