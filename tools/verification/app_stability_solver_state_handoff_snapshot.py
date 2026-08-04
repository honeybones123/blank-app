"""Lock the Inputs Apply solver-state handoff classification.

This proof is intentionally narrow: the product can settle through run_end and
FinalDesignGuidePublication even when the legacy solver-state probe has already
been consumed. That must be classified as telemetry handoff lag, not as a
product failure.
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


def _write_report(payload: dict[str, Any], path: Path) -> None:
    proof = payload.get("proof") or {}
    lines = [
        "# App Stability Solver-State Handoff Snapshot",
        "",
        f"Status: `{payload.get('status')}`",
        f"Generated: `{payload.get('timestamp')}`",
        f"Recipe: `{payload.get('browser_recipe')}`",
        "",
        "## Proof",
        "",
        f"- apply clicked: `{proof.get('apply_clicked')}`",
        f"- run_end captured: `{proof.get('run_end_captured')}`",
        f"- final card settled after Apply: `{proof.get('post_apply_final_card_ready')}`",
        f"- solver state timeout: `{proof.get('solver_state_timeout')}`",
        f"- handoff classification: `{proof.get('solver_state_handoff_classification')}`",
        f"- duplicate action risk: `{proof.get('duplicate_action_risk')}`",
        f"- loading shell after Apply: `{proof.get('loading_shell_after_apply')}`",
        "",
        "## Classification",
        "",
        str(payload.get("classification_note") or ""),
        "",
        "## Failures",
        "",
        "\n".join(f"- `{failure}`" for failure in payload.get("failures") or []) or "None.",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8504")
    parser.add_argument("--start-streamlit", action="store_true")
    parser.add_argument("--port", type=int, default=8518)
    parser.add_argument("--browser-recipe", default="R3A_M300_V400")
    parser.add_argument("--card-timeout-s", type=float, default=45.0)
    parser.add_argument("--apply-timeout-s", type=float, default=25.0)
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

    classification = trace.get("solver_state_handoff_classification")
    run_end_captured = bool(trace.get("run_end_event"))
    post_apply_ready = bool(trace.get("post_apply_final_card_ready"))
    apply_clicked = bool((trace.get("click_result") or {}).get("clicked"))
    solver_state_timeout = bool(trace.get("solver_state_timeout"))

    failures: list[str] = []
    if not apply_clicked:
        failures.append("apply_cta_not_clicked")
    if not run_end_captured:
        failures.append("run_end_not_captured")
    if not post_apply_ready:
        failures.append("post_apply_final_card_not_settled")
    if trace.get("duplicate_action_risk"):
        failures.append("duplicate_action_risk_after_apply")
    if trace.get("loading_shell_after_apply"):
        failures.append("loading_shell_after_apply")
    if solver_state_timeout and classification != "run_end_and_final_card_settled_solver_probe_consumed":
        failures.append("solver_timeout_not_classified_as_consumed_probe")
    if not solver_state_timeout and classification not in {
        "solver_probe_state_available",
        "no_solver_probe_state_needed",
    }:
        failures.append("unexpected_solver_handoff_classification")

    if solver_state_timeout:
        classification_note = (
            "The legacy solver-state probe timed out, but run_end and the final card both settled. "
            "This is locked as telemetry handoff lag rather than product failure."
        )
    else:
        classification_note = (
            "The solver-state probe was available or not needed on this run; the same Apply path still settled "
            "without duplicate action or loading-shell residue."
        )

    payload = {
        "schema": "app_stability_solver_state_handoff_snapshot.v1",
        "status": "PASS" if not failures else "FAIL",
        "timestamp": _stamp(),
        "base_url": base_url,
        "started_isolated_streamlit": bool(args.start_streamlit),
        "browser_recipe": args.browser_recipe,
        "proof": {
            "apply_clicked": apply_clicked,
            "run_end_captured": run_end_captured,
            "post_apply_final_card_ready": post_apply_ready,
            "solver_state_timeout": solver_state_timeout,
            "solver_state_handoff_classification": classification,
            "duplicate_action_risk": bool(trace.get("duplicate_action_risk")),
            "loading_shell_after_apply": bool(trace.get("loading_shell_after_apply")),
        },
        "trace": trace,
        "classification_note": classification_note,
        "failures": failures,
        "product_behaviour_changed": False,
    }
    stamp = payload["timestamp"]
    json_path = ARTIFACT_DIR / f"app_stability_solver_state_handoff_snapshot_{stamp}.json"
    md_path = AUDIT_DIR / f"app_stability_solver_state_handoff_snapshot_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    _write_report(payload, md_path)
    print(f"app_stability_solver_state_handoff_snapshot {payload['status']}")
    print(f"json={json_path}")
    print(f"report={md_path}")
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
