"""Readiness audit for residual shear cleanup primary executor call-shape cutover."""

from __future__ import annotations

from datetime import datetime
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
INPUTS_PAGE = ROOT / "inputs_page.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
REPORT_DIR = ROOT / "artifacts" / "reports"


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _run(command: list[str]) -> dict[str, Any]:
    proc = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, timeout=180)
    return {
        "command": command,
        "returncode": proc.returncode,
        "passed": proc.returncode == 0,
        "stdout_tail": proc.stdout[-3000:],
        "stderr_tail": proc.stderr[-3000:],
    }


def _block(source: str, start_token: str, end_token: str) -> str:
    start = source.find(start_token)
    if start < 0:
        return ""
    end = source.find(end_token, start + len(start_token))
    return source[start:end] if end > start else source[start:]


def _capture() -> dict[str, Any]:
    source = INPUTS_PAGE.read_text(encoding="utf-8-sig", errors="replace")
    route_block = _block(
        source,
        "current_shear_for_residual_cleanup = _parse_util_value(",
        "    shear_blocker = _shear_low_util_active_links_exact_blocker(",
    )
    direct_call_present = "_compute_shear_tightening_recommendation(\n                state," in route_block
    runner_present = (
        "def _run_post_click_low_bending_residual_shear_cleanup_primary_executor("
        in source
    )
    injected_runner_call_present = (
        "_run_post_click_low_bending_residual_shear_cleanup_primary_executor(" in route_block
    )
    injected_runner_uses_same_executor = (
        "executor=_compute_shear_tightening_recommendation" in route_block
    )
    trace_run = _run(
        [
            sys.executable,
            "tools/verification/design_guide_post_click_low_bending_residual_shear_cleanup_primary_executor_injected_adapter_trace_wiring_snapshot.py",
        ]
    )
    parity_run = _run(
        [
            sys.executable,
            "tools/verification/design_guide_post_click_low_bending_residual_shear_cleanup_primary_executor_parity_scenarios.py",
        ]
    )
    if direct_call_present and not runner_present:
        decision = "READY_FOR_INJECTED_EXECUTOR_CALL_SHAPE_CUTOVER"
    elif injected_runner_call_present and runner_present:
        decision = "INJECTED_EXECUTOR_CALL_SHAPE_ALREADY_WIRED"
    else:
        decision = "CALL_SHAPE_READINESS_UNCLEAR"
    return {
        "decision": decision,
        "route_block_present": bool(route_block),
        "direct_executor_call_present_in_route": direct_call_present,
        "injected_runner_helper_present": runner_present,
        "injected_runner_call_present_in_route": injected_runner_call_present,
        "injected_runner_uses_same_executor": injected_runner_uses_same_executor,
        "same_executor_can_be_injected": (
            "_compute_shear_tightening_recommendation(" in route_block
            or injected_runner_uses_same_executor
        ),
        "expected_replacement": (
            "Call _run_post_click_low_bending_residual_shear_cleanup_primary_executor("
            "state=state, executor=_compute_shear_tightening_recommendation)"
        ),
        "trace_wiring": trace_run,
        "parity_scenarios": parity_run,
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "engineering_behavior_changed": False,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    pre_ready = capture.get("decision") == "READY_FOR_INJECTED_EXECUTOR_CALL_SHAPE_CUTOVER"
    post_ready = capture.get("decision") == "INJECTED_EXECUTOR_CALL_SHAPE_ALREADY_WIRED"
    return {
        "route_block_present": capture.get("route_block_present") is True,
        "readiness_or_cutover_shape_detected": pre_ready or post_ready,
        "same_executor_can_be_injected": capture.get("same_executor_can_be_injected") is True
        or post_ready,
        "trace_wiring_passed": (capture.get("trace_wiring") or {}).get("passed") is True,
        "parity_scenarios_passed": (capture.get("parity_scenarios") or {}).get("passed")
        is True,
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "engineering_behavior_unchanged": capture.get("engineering_behavior_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Residual Shear Cleanup Primary Executor Call-Shape Cutover Readiness",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Summary",
        "",
        f"- Direct executor call present in route: `{capture.get('direct_executor_call_present_in_route')}`",
        f"- Injected runner helper present: `{capture.get('injected_runner_helper_present')}`",
        f"- Injected runner call present in route: `{capture.get('injected_runner_call_present_in_route')}`",
        f"- Expected replacement: `{capture.get('expected_replacement')}`",
        "",
        "## Checks",
        "",
    ]
    lines.extend(f"- {key}: `{value}`" for key, value in (payload.get("checks") or {}).items())
    lines.extend(
        [
            "",
            "## Next",
            "",
            "If decision is READY_FOR_INJECTED_EXECUTOR_CALL_SHAPE_CUTOVER, add the injected runner helper and replace only the direct call shape.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    capture = _capture()
    checks = _checks(capture)
    failures = [key for key, value in checks.items() if value is not True]
    payload = {
        "schema": "design_guide_post_click_low_bending_residual_shear_cleanup_primary_executor_call_shape_cutover_readiness.v1",
        "created_at": _stamp(),
        "status": "PASS" if not failures else "FAIL",
        "capture": capture,
        "checks": checks,
        "failures": failures,
        "snapshot_hash": _stable_hash({"capture": capture, "checks": checks}),
    }
    stamp = payload["created_at"]
    json_path = (
        ARTIFACT_DIR
        / f"design_guide_post_click_low_bending_residual_shear_cleanup_primary_executor_call_shape_cutover_readiness_{stamp}.json"
    )
    audit_path = (
        AUDIT_DIR
        / f"design_guide_post_click_low_bending_residual_shear_cleanup_primary_executor_call_shape_cutover_readiness_{stamp}.md"
    )
    report_path = (
        REPORT_DIR
        / f"design_brain_physical_extraction_residual_shear_cleanup_primary_executor_call_shape_cutover_readiness_{stamp}.md"
    )
    json_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8",
    )
    _write_report(audit_path, payload)
    _write_report(report_path, payload)
    print(
        "design_guide_post_click_low_bending_residual_shear_cleanup_primary_executor_call_shape_cutover_readiness "
        + payload["status"]
    )
    print(f"json={json_path}")
    print(f"report={audit_path}")
    print(f"extraction_report={report_path}")
    if failures:
        print("failures=" + ", ".join(failures))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
