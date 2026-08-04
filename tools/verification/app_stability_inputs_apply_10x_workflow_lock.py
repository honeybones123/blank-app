"""Repeat-lock the Inputs Design Guide Apply workflow.

Phase 2 stability proof: a critical Apply workflow must settle repeatedly with
one action, one final publication, no loading shell residue, no duplicate action
CTA, and no unexpected scroll movement.
"""

from __future__ import annotations

import argparse
from datetime import datetime
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.verification.app_stability_inputs_apply_interaction_trace import (  # noqa: E402
    _run_trace,
)
from tools.verification.helpers.browser_one_click_regression import (  # noqa: E402
    _start_streamlit,
)


ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _classify_iteration(trace: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    if not trace.get("initial_final_card_ready"):
        failures.append("initial_final_card_not_ready")
    if not (trace.get("click_result") or {}).get("clicked"):
        failures.append("apply_cta_not_clicked")
    if not trace.get("run_end_event"):
        failures.append("run_end_not_captured")
    if not trace.get("post_apply_final_card_ready"):
        failures.append("post_apply_final_card_not_ready")
    if trace.get("duplicate_action_risk"):
        failures.append("duplicate_action_risk")
    if trace.get("loading_shell_after_apply"):
        failures.append("loading_shell_after_apply")

    before_scroll = int((trace.get("dom_before") or {}).get("scrollY") or 0)
    after_scroll = int((trace.get("dom_after") or {}).get("scrollY") or 0)
    if abs(after_scroll - before_scroll) > 20:
        failures.append("unexpected_scroll_movement")

    if trace.get("solver_state_timeout") and trace.get(
        "solver_state_handoff_classification"
    ) != "run_end_and_final_card_settled_solver_probe_consumed":
        failures.append("unclassified_solver_state_timeout")
    return failures


def _write_report(payload: dict[str, Any], path: Path) -> None:
    summary = payload.get("summary") or {}
    lines = [
        "# Inputs Apply 10x Workflow Lock",
        "",
        f"Status: `{payload.get('status')}`",
        f"Generated: `{payload.get('timestamp')}`",
        f"Recipe: `{payload.get('browser_recipe')}`",
        f"Repetitions: `{summary.get('repetitions')}`",
        "",
        "## Summary",
        "",
        f"- passed iterations: `{summary.get('passed_iterations')}`",
        f"- failed iterations: `{summary.get('failed_iterations')}`",
        f"- solver handoff classifications: `{summary.get('solver_state_handoff_classifications')}`",
        f"- duplicate action count: `{summary.get('duplicate_action_count')}`",
        f"- loading shell count: `{summary.get('loading_shell_count')}`",
        f"- scroll movement failures: `{summary.get('scroll_movement_failures')}`",
        "",
        "## Iterations",
        "",
    ]
    for item in payload.get("iterations") or []:
        lines.extend(
            [
                f"### Iteration {item.get('iteration')}",
                "",
                f"- status: `{item.get('status')}`",
                f"- failures: `{item.get('failures')}`",
                f"- handoff: `{item.get('solver_state_handoff_classification')}`",
                f"- run_end: `{item.get('run_end_captured')}`",
                f"- final card: `{item.get('post_apply_final_card_ready')}`",
                f"- scroll before/after: `{item.get('scroll_before')}` / `{item.get('scroll_after')}`",
                "",
            ]
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8504")
    parser.add_argument("--start-streamlit", action="store_true")
    parser.add_argument("--port", type=int, default=8519)
    parser.add_argument("--browser-recipe", default="LIVE_FUZZ_SHEAR_FAIL_BENDING_OVERDESIGN_GOVERNS_01")
    parser.add_argument("--repetitions", type=int, default=10)
    parser.add_argument("--card-timeout-s", type=float, default=45.0)
    parser.add_argument("--apply-timeout-s", type=float, default=25.0)
    parser.add_argument("--headed", action="store_true")
    args = parser.parse_args(argv)

    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    process = None
    base_url = args.base_url
    iterations: list[dict[str, Any]] = []
    startup_failure: dict[str, Any] | None = None
    try:
        if args.start_streamlit:
            base_url = f"http://127.0.0.1:{int(args.port)}"
            try:
                process = _start_streamlit(int(args.port))
            except Exception as exc:
                startup_failure = {
                    "exception_type": type(exc).__name__,
                    "message": str(exc),
                    "root_cause_candidate": {
                        "production_path": "tools.verification.helpers.browser_one_click_regression._start_streamlit",
                        "first_divergence": "isolated Streamlit process did not become reachable",
                        "downstream_effect": "Apply workflow could not start; no family result was certified",
                    },
                }
        for index in range(1, int(args.repetitions) + 1):
            if startup_failure:
                break
            trace = _run_trace(
                base_url,
                args.browser_recipe,
                card_timeout_s=args.card_timeout_s,
                apply_timeout_s=args.apply_timeout_s,
                headless=not args.headed,
            )
            failures = _classify_iteration(trace)
            iterations.append(
                {
                    "iteration": index,
                    "status": "PASS" if not failures else "FAIL",
                    "failures": failures,
                    "solver_state_handoff_classification": trace.get(
                        "solver_state_handoff_classification"
                    ),
                    "run_end_captured": bool(trace.get("run_end_event")),
                    "post_apply_final_card_ready": bool(trace.get("post_apply_final_card_ready")),
                    "duplicate_action_risk": bool(trace.get("duplicate_action_risk")),
                    "loading_shell_after_apply": bool(trace.get("loading_shell_after_apply")),
                    "scroll_before": int((trace.get("dom_before") or {}).get("scrollY") or 0),
                    "scroll_after": int((trace.get("dom_after") or {}).get("scrollY") or 0),
                    "trace": trace,
                }
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
            try:
                process._codex_startup_log_handle.close()  # type: ignore[attr-defined]
            except Exception:
                pass

    all_failures = [
        {"iteration": item.get("iteration"), "failures": item.get("failures")}
        for item in iterations
        if item.get("failures")
    ]
    handoff_counts: dict[str, int] = {}
    for item in iterations:
        key = str(item.get("solver_state_handoff_classification") or "unknown")
        handoff_counts[key] = handoff_counts.get(key, 0) + 1

    payload = {
        "schema": "app_stability_inputs_apply_10x_workflow_lock.v1",
        "status": "PASS" if not all_failures else "FAIL",
        "timestamp": _stamp(),
        "base_url": base_url,
        "started_isolated_streamlit": bool(args.start_streamlit),
        "browser_recipe": args.browser_recipe,
        "summary": {
            "repetitions": int(args.repetitions),
            "passed_iterations": sum(1 for item in iterations if item.get("status") == "PASS"),
            "failed_iterations": sum(1 for item in iterations if item.get("status") != "PASS"),
            "solver_state_handoff_classifications": handoff_counts,
            "duplicate_action_count": sum(1 for item in iterations if item.get("duplicate_action_risk")),
            "loading_shell_count": sum(1 for item in iterations if item.get("loading_shell_after_apply")),
            "scroll_movement_failures": sum(
                1 for item in iterations if "unexpected_scroll_movement" in (item.get("failures") or [])
            ),
        },
        "failures": all_failures,
        "iterations": iterations,
        "startup_failure": startup_failure,
        "product_behaviour_changed": False,
    }
    if startup_failure:
        payload["status"] = "FAIL"
        payload["failures"] = [{"iteration": 0, "failures": ["isolated_streamlit_startup_failed"]}]
    stamp = payload["timestamp"]
    json_path = ARTIFACT_DIR / f"app_stability_inputs_apply_10x_workflow_lock_{stamp}.json"
    md_path = AUDIT_DIR / f"app_stability_inputs_apply_10x_workflow_lock_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    _write_report(payload, md_path)
    print(f"app_stability_inputs_apply_10x_workflow_lock {payload['status']}")
    print(f"json={json_path}")
    print(f"report={md_path}")
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
