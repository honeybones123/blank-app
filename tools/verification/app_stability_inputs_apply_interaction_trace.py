"""Trace one Inputs Design Guide Apply interaction end-to-end.

Phase 3 proof for the stability goal. This verifier records the current
click-to-settled-publication path without changing product behaviour.
"""

from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import json
from pathlib import Path
import sys
import time
from typing import Any

from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.verification.design_guide_family_browser_live_visual_consistency_snapshot import (  # noqa: E402
    _wait_for_final_design_guide_card,
)
from tools.verification.helpers.browser_helpers import _load_browser_state  # noqa: E402
from tools.verification.helpers.browser_one_click_regression import (  # noqa: E402
    TRACER_PATH,
    _query,
    _start_streamlit,
    _wait_for_http,
    _wait_for_run_end,
    _wait_for_solver_state,
)
from tools.verification.run_family_10_fuzz_audit import (  # noqa: E402
    _action_button_probe,
    _click_first_enabled_action,
)


ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode("utf-8")).hexdigest()[:16]


def _tracer_offset() -> int:
    try:
        return TRACER_PATH.stat().st_size
    except OSError:
        return 0


def _dom_state(page) -> dict[str, Any]:
    return dict(
        page.evaluate(
            """
            () => {
              const clean = (value) => String(value || "").replace(/\\s+/g, " ").trim();
              const hash = (value) => {
                const text = String(value || "");
                let h = 2166136261;
                for (let i = 0; i < text.length; i += 1) {
                  h ^= text.charCodeAt(i);
                  h = Math.imul(h, 16777619);
                }
                return (h >>> 0).toString(16);
              };
              const bodyText = clean(document.body ? document.body.innerText : "");
              const guideCandidates = Array.from(document.querySelectorAll("[data-testid*='design-guide' i], .fast-guidance-item, body"))
                .map((el) => clean(el.innerText || el.textContent))
                .filter((text) => /Design Guide|Apply|Run one-click|PASS|ACTION|ERROR|blocked|Checking design guidance/i.test(text));
              const guideText = guideCandidates[0] || "";
              return {
                scrollY: Math.round(window.scrollY || 0),
                bodyTextLength: bodyText.length,
                bodyTextHash: hash(bodyText),
                loadingShellVisible: /Checking design guidance|Reviewing strength, detailing, serviceability/i.test(bodyText),
                designGuideTextHash: hash(guideText),
                designGuideTextSample: guideText.slice(0, 700),
                buttonTexts: Array.from(document.querySelectorAll("button")).slice(0, 80).map((button) => clean(button.innerText || button.textContent)).filter(Boolean)
              };
            }
            """
        )
    )


def _summarise_browser_state(state: dict[str, Any]) -> dict[str, Any]:
    timing = dict(state.get("render_timing") or state.get("timing") or {})
    solver_result = dict(state.get("solver_result") or {})
    feedback = dict(state.get("one_click_feedback") or {})
    final_publication = dict(state.get("final_publication") or state.get("final_design_guide_publication") or {})
    summary = dict(state.get("summary_state_probe") or {})
    return {
        "state_hash": _stable_hash(state),
        "top_level_keys": sorted(state.keys())[:120],
        "render_timing_rerun_seq": timing.get("rerun_seq") or state.get("rerun_seq"),
        "render_timing_event_count": len(timing.get("recent_events") or state.get("render_timing_events") or []),
        "solver_result_keys": sorted(solver_result.keys()),
        "one_click_feedback_keys": sorted(feedback.keys()),
        "final_publication_keys": sorted(final_publication.keys()),
        "selected_family": (
            final_publication.get("selected_family")
            or state.get("selected_family")
            or summary.get("selected_family")
            or summary.get("selected_family_id")
        ),
        "outcome_state": final_publication.get("outcome_state") or state.get("outcome_state"),
        "publication_hash": final_publication.get("publication_hash") or state.get("publication_hash"),
    }


def _try_load_browser_state(page, *, timeout_s: float) -> tuple[dict[str, Any], dict[str, Any]]:
    try:
        state = _load_browser_state(page, timeout_s=timeout_s)
        return state, {"available": True, "error": None}
    except Exception as exc:
        return {}, {"available": False, "error": f"{type(exc).__name__}: {exc}"}


def _write_markdown(payload: dict[str, Any], path: Path) -> None:
    trace = payload.get("trace") or {}
    lines = [
        "# Inputs Apply Interaction Trace",
        "",
        f"Status: `{payload.get('status')}`",
        f"Generated: `{payload.get('timestamp')}`",
        f"Recipe: `{payload.get('browser_recipe')}`",
        "",
        "## Click Path",
        "",
        f"- initial final card ready: `{trace.get('initial_final_card_ready')}`",
        f"- initial action buttons: `{trace.get('button_probe_before')}`",
        f"- click result: `{trace.get('click_result')}`",
        f"- run end captured: `{bool(trace.get('run_end_event'))}`",
        f"- solver state timeout: `{trace.get('solver_state_timeout')}`",
        f"- solver state handoff classification: `{trace.get('solver_state_handoff_classification')}`",
        f"- post-apply final card ready: `{trace.get('post_apply_final_card_ready')}`",
        f"- duplicate action risk: `{trace.get('duplicate_action_risk')}`",
        f"- loading shell after apply: `{trace.get('loading_shell_after_apply')}`",
        "",
        "## Stability Signals",
        "",
        f"- scroll before: `{(trace.get('dom_before') or {}).get('scrollY')}`",
        f"- scroll after: `{(trace.get('dom_after') or {}).get('scrollY')}`",
        f"- body hash before: `{(trace.get('dom_before') or {}).get('bodyTextHash')}`",
        f"- body hash after: `{(trace.get('dom_after') or {}).get('bodyTextHash')}`",
        f"- browser state before hash: `{(trace.get('browser_state_before') or {}).get('state_hash')}`",
        f"- browser state after hash: `{(trace.get('browser_state_after') or {}).get('state_hash')}`",
        "",
        "## First Root-Cause Candidate",
        "",
        str(payload.get("first_root_cause_candidate") or "No root-cause candidate produced."),
        "",
        "## Next Slice",
        "",
        str(payload.get("recommended_next_slice") or "No recommendation produced."),
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _run_trace(base_url: str, recipe: str, *, card_timeout_s: float, apply_timeout_s: float, headless: bool) -> dict[str, Any]:
    _wait_for_http(base_url)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=headless)
        context = browser.new_context(viewport={"width": 1280, "height": 900})
        page = context.new_page()
        page.goto(
            _query(base_url, {"page": "inputs", "browser_recipe": recipe, "stability_trace": "1"}),
            wait_until="domcontentloaded",
            timeout=90_000,
        )
        initial_card = _wait_for_final_design_guide_card(page, timeout_s=card_timeout_s)
        before_state, before_state_probe = _try_load_browser_state(page, timeout_s=min(6.0, card_timeout_s))
        dom_before = _dom_state(page)
        button_probe_before = _action_button_probe(page)
        tracer_start = _tracer_offset()
        click_started_ms = int(time.time() * 1000)
        click_result = _click_first_enabled_action(page)
        after_state: dict[str, Any] = {}
        solver_state_timeout = False
        run_end_event = None
        post_apply_card: dict[str, Any] = {}
        if click_result.get("clicked"):
            try:
                after_state, solver_state_timeout = _wait_for_solver_state(
                    page,
                    timeout_ms=int(max(3.0, apply_timeout_s) * 1000),
                )
            except Exception:
                solver_state_timeout = True
                after_state = {}
            run_end_event, _ = _wait_for_run_end(
                tracer_start,
                timeout_s=max(3.0, apply_timeout_s),
                start_time_ms=click_started_ms,
            )
            post_apply_card = _wait_for_final_design_guide_card(page, timeout_s=card_timeout_s)
        else:
            after_state, _ = _try_load_browser_state(page, timeout_s=min(6.0, card_timeout_s))
            post_apply_card = _wait_for_final_design_guide_card(page, timeout_s=card_timeout_s)
        dom_after = _dom_state(page)
        _, after_state_probe = _try_load_browser_state(page, timeout_s=1.0)
        button_probe_after = _action_button_probe(page)
        browser.close()

    duplicate_action_risk = bool(
        click_result.get("clicked")
        and int((button_probe_after or {}).get("enabled_action_count") or 0) > 0
        and not (post_apply_card or {}).get("final_card_ready")
    )
    run_end_data = dict((run_end_event or {}).get("data") or {})
    solver_state_handoff_classification = "not_applicable"
    if click_result.get("clicked"):
        if solver_state_timeout and run_end_data and (post_apply_card or {}).get("final_card_ready"):
            solver_state_handoff_classification = "run_end_and_final_card_settled_solver_probe_consumed"
        elif solver_state_timeout:
            solver_state_handoff_classification = "solver_probe_timeout_without_complete_settle_proof"
        elif after_state.get("solver_result") or after_state.get("one_click_feedback"):
            solver_state_handoff_classification = "solver_probe_state_available"
        else:
            solver_state_handoff_classification = "no_solver_probe_state_needed"
    return {
        "initial_final_card_ready": bool((initial_card or {}).get("final_card_ready")),
        "post_apply_final_card_ready": bool((post_apply_card or {}).get("final_card_ready")),
        "button_probe_before": button_probe_before,
        "button_probe_after": button_probe_after,
        "click_result": click_result,
        "run_end_event": run_end_event,
        "solver_state_timeout": bool(solver_state_timeout),
        "browser_state_before_probe": before_state_probe,
        "browser_state_after_probe": after_state_probe,
        "browser_state_before": _summarise_browser_state(before_state),
        "browser_state_after": _summarise_browser_state(after_state),
        "dom_before": dom_before,
        "dom_after": dom_after,
        "initial_card_probe": initial_card,
        "post_apply_card_probe": post_apply_card,
        "duplicate_action_risk": duplicate_action_risk,
        "loading_shell_after_apply": bool((dom_after or {}).get("loadingShellVisible")),
        "solver_state_handoff_classification": solver_state_handoff_classification,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8504")
    parser.add_argument("--start-streamlit", action="store_true", help="Start an isolated CODEX_BROWSER_TEST_MODE app")
    parser.add_argument("--port", type=int, default=8517)
    parser.add_argument("--browser-recipe", default="R3A_M300_V400")
    parser.add_argument("--card-timeout-s", type=float, default=45.0)
    parser.add_argument("--apply-timeout-s", type=float, default=20.0)
    parser.add_argument("--headed", action="store_true")
    args = parser.parse_args(argv)

    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    process = None
    base_url = args.base_url
    try:
        if args.start_streamlit:
            base_url = f"http://127.0.0.1:{int(args.port)}"
            process = _start_streamlit(int(args.port))
        trace = _run_trace(
            base_url,
            args.browser_recipe,
            card_timeout_s=args.card_timeout_s,
            apply_timeout_s=args.apply_timeout_s,
            headless=not args.headed,
        )
    finally:
        if process is not None:
            try:
                process.terminate()
                process.wait(timeout=10)
            except Exception:
                try:
                    process.kill()
                except Exception:
                    pass
    failures: list[str] = []
    if not trace.get("initial_final_card_ready"):
        failures.append("initial_final_design_guide_card_not_ready")
    if trace.get("click_result", {}).get("clicked") and not trace.get("post_apply_final_card_ready"):
        failures.append("post_apply_final_design_guide_card_not_ready")
    if trace.get("duplicate_action_risk"):
        failures.append("duplicate_action_risk_after_apply")
    if trace.get("loading_shell_after_apply"):
        failures.append("loading_shell_after_apply")

    root_cause = "Inputs Apply trace captured successfully; first fix should target the first failing signal above."
    if trace.get("loading_shell_after_apply"):
        root_cause = "The settled path can leave a loading shell visible after Apply; inspect final-publication slot readiness before page-specific layout changes."
    elif trace.get("duplicate_action_risk"):
        root_cause = "The Apply path can leave an enabled action visible after click without a settled final card; inspect action idempotency and publication handoff."
    elif trace.get("solver_state_handoff_classification") == "run_end_and_final_card_settled_solver_probe_consumed":
        root_cause = "The product visibly settles from run_end/final publication, but the legacy solver-result probe can be empty after the result is consumed; classify this as telemetry handoff lag, not product failure."
    elif not trace.get("click_result", {}).get("clicked"):
        root_cause = "The selected recipe did not expose an enabled Apply CTA; use this as a no-action stability trace or rerun with an ACTION recipe."

    payload = {
        "schema": "app_stability_inputs_apply_interaction_trace.v1",
        "status": "PASS" if not failures else "FAIL",
        "timestamp": _stamp(),
        "base_url": base_url,
        "started_isolated_streamlit": bool(args.start_streamlit),
        "browser_recipe": args.browser_recipe,
        "failures": failures,
        "trace": trace,
        "first_root_cause_candidate": root_cause,
        "recommended_next_slice": "Add a focused stability regression for the first failing signal, then fix that one shared path only.",
        "product_behaviour_changed": False,
    }
    stamp = payload["timestamp"]
    json_path = ARTIFACT_DIR / f"app_stability_inputs_apply_interaction_trace_{stamp}.json"
    md_path = AUDIT_DIR / f"app_stability_inputs_apply_interaction_trace_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    _write_markdown(payload, md_path)
    print(f"app_stability_inputs_apply_interaction_trace {payload['status']}")
    print(f"json={json_path}")
    print(f"report={md_path}")
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
