"""Browser/live attribution for implicit Streamlit widget reruns.

This audit targets controls that can trigger Streamlit reruns without passing
through explicit ``st.rerun()`` exits. It does not change product code,
publication truth, CTA/apply semantics, family runtimes, or visible wording.
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
from urllib.parse import urlencode

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.verification.helpers.browser_helpers import _browser_state_raw_candidates  # noqa: E402
from tools.verification.helpers.browser_one_click_regression import (  # noqa: E402
    _start_streamlit,
    _wait_for_http,
)


ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
DEFAULT_RECIPE = "A_bending_under_only"


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _query(base_url: str, params: dict[str, Any]) -> str:
    clean = {key: value for key, value in params.items() if value is not None}
    return f"{base_url.rstrip('/')}/?{urlencode(clean)}"


def _best_browser_state(page, recipe: str, *, timeout_s: float = 12.0) -> dict[str, Any]:
    deadline = datetime.now().timestamp() + max(0.5, timeout_s)
    best: dict[str, Any] = {}
    best_score = (-1, -1, -1, -1)
    while datetime.now().timestamp() < deadline:
        for raw in _browser_state_raw_candidates(page, timeout_ms=2_000):
            try:
                parsed = json.loads(raw)
            except Exception:
                continue
            if not isinstance(parsed, dict):
                continue
            phase = str(parsed.get("browser_probe_phase") or parsed.get("probe_phase") or "")
            score = (
                1 if parsed.get("browser_recipe") == recipe else 0,
                1 if phase in {"post_page_render", "final"} else 0,
                1 if parsed.get("render_timing_probe") else 0,
                len(raw),
            )
            if score > best_score:
                best = parsed
                best_score = score
            if score[:3] == (1, 1, 1):
                return parsed
        page.wait_for_timeout(250)
    return best


def _state_summary(state: dict[str, Any]) -> dict[str, Any]:
    probe = dict(state.get("speed_profile_probe") or {})
    timing = dict(state.get("render_timing_probe") or {})
    debug_probe = dict(state.get("browser_debug_probe") or {})
    return {
        "rerun_seq": state.get("rerun_seq") or probe.get("rerun_seq") or timing.get("rerun_seq"),
        "inputs_rerun_trigger_events": list(
            state.get("inputs_rerun_trigger_events")
            or probe.get("inputs_rerun_trigger_events")
            or debug_probe.get("inputs_rerun_trigger_events")
            or []
        )[-10:],
        "browser_recipe": state.get("browser_recipe"),
        "publication_hash": (
            state.get("publication_hash")
            or state.get("final_publication_hash")
            or (state.get("final_publication_verifier_payload") or {}).get("publication_hash")
        ),
        "body_hash": _stable_hash(str(state.get("browser_state_text") or state.get("body_text") or ""))[:12],
    }


def _dom_probe(page) -> dict[str, Any]:
    return dict(
        page.evaluate(
            r"""
            () => {
              if (!window.__implicitWidgetLayoutProbe) {
                window.__implicitWidgetLayoutProbe = {cls: 0, entries: []};
                try {
                  new PerformanceObserver((list) => {
                    for (const entry of list.getEntries()) {
                      if (entry.hadRecentInput) continue;
                      window.__implicitWidgetLayoutProbe.cls += Number(entry.value || 0);
                      window.__implicitWidgetLayoutProbe.entries.push({
                        value: Number(entry.value || 0),
                        sources: Array.from(entry.sources || []).slice(0, 4).map((source) => {
                          const node = source.node;
                          if (!node) return {tag: null, text: ""};
                          return {
                            tag: node.tagName,
                            text: String(node.innerText || node.textContent || "").replace(/\s+/g, " ").trim().slice(0, 120),
                            cls: node.className || "",
                            testid: node.getAttribute && node.getAttribute("data-testid")
                          };
                        })
                      });
                    }
                  }).observe({type: "layout-shift", buffered: true});
                } catch (error) {}
              }
              const clean = (value) => String(value || "").replace(/\s+/g, " ").trim();
              const visible = (el) => {
                if (!el || !el.getBoundingClientRect) return false;
                const style = window.getComputedStyle(el);
                const rect = el.getBoundingClientRect();
                return style.display !== "none" && style.visibility !== "hidden"
                  && Number(style.opacity || "1") > 0.02 && rect.width > 2 && rect.height > 2;
              };
              const controls = Array.from(document.querySelectorAll("button,[role='button'],input,select,textarea,label"))
                .filter(visible)
                .map((el, index) => {
                  const rect = el.getBoundingClientRect();
                  return {
                    index,
                    tag: el.tagName,
                    role: el.getAttribute("role") || "",
                    type: el.getAttribute("type") || "",
                    text: clean(el.innerText || el.textContent || el.getAttribute("aria-label") || el.getAttribute("title") || ""),
                    aria: clean(el.getAttribute("aria-label") || ""),
                    testid: el.getAttribute("data-testid") || "",
                    top: Math.round(rect.top),
                    left: Math.round(rect.left),
                    width: Math.round(rect.width),
                    height: Math.round(rect.height)
                  };
                });
              return {
                cls: window.__implicitWidgetLayoutProbe.cls,
                cls_entries_tail: window.__implicitWidgetLayoutProbe.entries.slice(-12),
                controls
              };
            }
            """
        )
    )


def _find_control_index(probe: dict[str, Any], tokens: list[str]) -> int | None:
    wanted = [token.lower() for token in tokens]
    for control in probe.get("controls") or []:
        haystack = " ".join(
            str(control.get(key) or "") for key in ("text", "aria", "testid", "role", "type")
        ).lower()
        if all(token in haystack for token in wanted):
            return int(control.get("index") or 0)
    return None


def _click_control_by_index(page, index: int) -> bool:
    return bool(
        page.evaluate(
            r"""
            (targetIndex) => {
              const visible = (el) => {
                if (!el || !el.getBoundingClientRect) return false;
                const style = window.getComputedStyle(el);
                const rect = el.getBoundingClientRect();
                return style.display !== "none" && style.visibility !== "hidden"
                  && Number(style.opacity || "1") > 0.02 && rect.width > 2 && rect.height > 2;
              };
              const controls = Array.from(document.querySelectorAll("button,[role='button'],input,select,textarea,label"))
                .filter(visible);
              const el = controls[targetIndex];
              if (!el) return false;
              el.scrollIntoView({block: "center", inline: "center"});
              el.click();
              return true;
            }
            """,
            index,
        )
    )


def _wait_for_possible_rerun(page, before_seq: Any, *, recipe: str, timeout_s: float = 10.0) -> dict[str, Any]:
    deadline = datetime.now().timestamp() + max(0.5, timeout_s)
    latest_state: dict[str, Any] = {}
    samples: list[dict[str, Any]] = []
    while datetime.now().timestamp() < deadline:
        state = _best_browser_state(page, recipe, timeout_s=1.0)
        summary = _state_summary(state)
        samples.append(summary)
        latest_state = state
        if summary.get("rerun_seq") is not None and summary.get("rerun_seq") != before_seq:
            break
        page.wait_for_timeout(350)
    return {"state": latest_state, "samples": samples[-12:]}


def _try_action(page, *, recipe: str, action_id: str, tokens: list[str]) -> dict[str, Any]:
    before_probe = _dom_probe(page)
    before_state = _best_browser_state(page, recipe, timeout_s=8.0)
    before_summary = _state_summary(before_state)
    before_cls = float(before_probe.get("cls") or 0.0)
    index = _find_control_index(before_probe, tokens)
    if index is None:
        return {
            "action_id": action_id,
            "status": "SKIPPED",
            "reason": "control_not_visible",
            "tokens": tokens,
            "before": before_summary,
        }
    clicked = _click_control_by_index(page, index)
    if not clicked:
        return {
            "action_id": action_id,
            "status": "SKIPPED",
            "reason": "click_failed",
            "tokens": tokens,
            "before": before_summary,
        }
    page.wait_for_timeout(250)
    after = _wait_for_possible_rerun(page, before_summary.get("rerun_seq"), recipe=recipe, timeout_s=10.0)
    page.wait_for_timeout(650)
    after_probe = _dom_probe(page)
    after_state = _best_browser_state(page, recipe, timeout_s=3.0) or dict(after.get("state") or {})
    after_summary = _state_summary(after_state)
    after_events = list(after_summary.get("inputs_rerun_trigger_events") or [])
    before_events = list(before_summary.get("inputs_rerun_trigger_events") or [])
    explicit_new_events = [event for event in after_events if event not in before_events]
    rerun_happened = (
        after_summary.get("rerun_seq") is not None
        and after_summary.get("rerun_seq") != before_summary.get("rerun_seq")
    )
    return {
        "action_id": action_id,
        "status": "CAPTURED",
        "tokens": tokens,
        "clicked_control_index": index,
        "rerun_happened": bool(rerun_happened),
        "explicit_marker_events_added": explicit_new_events,
        "implicit_rerun": bool(rerun_happened and not explicit_new_events),
        "layout_shift_delta": round(max(0.0, float(after_probe.get("cls") or 0.0) - before_cls), 6),
        "before": before_summary,
        "after": after_summary,
        "samples_tail": after.get("samples"),
        "layout_shift_entries_tail": list(after_probe.get("cls_entries_tail") or [])[-8:],
    }


def _capture(base_url: str, *, recipe: str, headed: bool) -> dict[str, Any]:
    url = _query(base_url, {"page": "inputs", "browser_recipe": recipe, "batch_design_open": 0})
    actions = [
        ("batch_manager_toggle", ["manager"]),
        ("constraints_info_button", ["constraints"]),
        ("design_mode_detailed", ["detailed"]),
        ("design_mode_fast", ["fast"]),
    ]
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=not headed)
        page = browser.new_page(viewport={"width": 1600, "height": 1000})
        page.goto(url, wait_until="domcontentloaded", timeout=90_000)
        page.wait_for_timeout(4500)
        initial_state = _best_browser_state(page, recipe, timeout_s=12.0)
        initial_probe = _dom_probe(page)
        results = []
        for action_id, tokens in actions:
            results.append(_try_action(page, recipe=recipe, action_id=action_id, tokens=tokens))
            page.wait_for_timeout(900)
        final_probe = _dom_probe(page)
        browser.close()
    return {
        "url": url,
        "recipe": recipe,
        "initial_state": _state_summary(initial_state),
        "initial_visible_controls": list(initial_probe.get("controls") or [])[:80],
        "actions": results,
        "final_layout_shift_total": final_probe.get("cls"),
    }


def _classify(capture: dict[str, Any]) -> dict[str, Any]:
    actions = list(capture.get("actions") or [])
    captured = [row for row in actions if row.get("status") == "CAPTURED"]
    implicit = [row for row in captured if row.get("implicit_rerun")]
    explicit = [row for row in captured if row.get("explicit_marker_events_added")]
    max_shift = max([float(row.get("layout_shift_delta") or 0.0) for row in captured] or [0.0])
    if implicit:
        diagnosis = "IMPLICIT_WIDGET_RERUNS_CAPTURED"
        next_slice = "Add narrow rerun-cause markers or stable layout guards around the captured implicit widget controls."
    elif captured:
        diagnosis = "NO_IMPLICIT_WIDGET_RERUN_CAPTURED"
        next_slice = "Use a user-specific interaction recipe to reproduce the visible jump before changing layout."
    else:
        diagnosis = "NO_TARGET_CONTROLS_CAPTURED"
        next_slice = "Update the attribution snapshot selectors for current Inputs controls before product changes."
    return {
        "status": "PASS",
        "diagnosis": diagnosis,
        "captured_action_count": len(captured),
        "implicit_rerun_action_ids": [row.get("action_id") for row in implicit],
        "explicit_marker_action_ids": [row.get("action_id") for row in explicit],
        "max_layout_shift_delta": round(max_shift, 6),
        "recommended_next_slice": next_slice,
    }


def _markdown(payload: dict[str, Any]) -> str:
    cls = payload["classification"]
    lines = [
        "# Design Guide Implicit Widget Rerun Attribution Snapshot",
        "",
        f"- Status: `{payload['status']}`",
        f"- Diagnosis: `{cls['diagnosis']}`",
        f"- Captured actions: `{cls['captured_action_count']}`",
        f"- Implicit rerun actions: `{cls['implicit_rerun_action_ids']}`",
        f"- Max layout shift delta: `{cls['max_layout_shift_delta']}`",
        f"- Product behaviour changed: `{payload['product_behaviour_changed']}`",
        "",
        "## Recommended Next Slice",
        "",
        cls["recommended_next_slice"],
        "",
        "## Actions",
        "",
        "```json",
        json.dumps(payload["capture"].get("actions") or [], indent=2, sort_keys=True),
        "```",
    ]
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8658)
    parser.add_argument("--base-url", default=os.environ.get("DESIGN_GUIDE_IMPLICIT_WIDGET_URL"))
    parser.add_argument("--recipe", default=DEFAULT_RECIPE)
    parser.add_argument("--headed", action="store_true")
    args = parser.parse_args()

    base_url = str(args.base_url or f"http://localhost:{args.port}")
    process: subprocess.Popen | None = None
    try:
        if not args.base_url:
            process = _start_streamlit(args.port)
        _wait_for_http(base_url, timeout_s=70.0)
        capture = _capture(base_url, recipe=str(args.recipe), headed=bool(args.headed))
    finally:
        if process is not None:
            process.terminate()
            try:
                process.wait(timeout=10)
            except Exception:
                process.kill()

    classification = _classify(capture)
    payload = {
        "schema": "design_guide_implicit_widget_rerun_attribution.v1",
        "created_at": _stamp(),
        "status": classification["status"],
        "classification": classification,
        "capture": capture,
        "product_behaviour_changed": False,
        "engineering_behaviour_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtime_changed": False,
    }
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = ARTIFACT_DIR / f"design_guide_implicit_widget_rerun_attribution_{payload['created_at']}.json"
    report_path = AUDIT_DIR / f"design_guide_implicit_widget_rerun_attribution_{payload['created_at']}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    report_path.write_text(_markdown(payload), encoding="utf-8")
    print(f"design_guide_implicit_widget_rerun_attribution {payload['status']}")
    print(f"diagnosis={classification['diagnosis']}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
