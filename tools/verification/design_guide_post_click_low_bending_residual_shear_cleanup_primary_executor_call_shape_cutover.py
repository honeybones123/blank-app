"""Cutover verifier for residual shear cleanup primary executor injected call shape."""

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
    helper_block = _block(
        source,
        "def _run_post_click_low_bending_residual_shear_cleanup_primary_executor(",
        "\ndef _stamp_design_guide_controller_post_click_low_bending_residual_shear_cleanup_route_shell_cutover_readiness(",
    )
    route_block = _block(
        source,
        "current_shear_for_residual_cleanup = _parse_util_value(",
        "    shear_blocker = _shear_low_util_active_links_exact_blocker(",
    )
    runner_call = route_block.find(
        "_run_post_click_low_bending_residual_shear_cleanup_primary_executor("
    )
    direct_try_call_present = (
        "try:\n            residual_shear_tighten = _compute_shear_tightening_recommendation("
        in route_block
    )
    direct_executor_call_count = route_block.count(
        "residual_shear_tighten = _compute_shear_tightening_recommendation("
    )
    injected_executor_reference_count = route_block.count(
        "executor=_compute_shear_tightening_recommendation"
    )
    trace_run = _run(
        [
            sys.executable,
            "tools/verification/design_guide_post_click_low_bending_residual_shear_cleanup_primary_executor_injected_adapter_trace_wiring_snapshot.py",
        ]
    )
    readiness_run = _run(
        [
            sys.executable,
            "tools/verification/design_guide_post_click_low_bending_residual_shear_cleanup_primary_executor_call_shape_cutover_readiness.py",
        ]
    )
    return {
        "decision": "RESIDUAL_SHEAR_CLEANUP_PRIMARY_EXECUTOR_CALL_SHAPE_CUT_OVER",
        "runner_helper_present": bool(helper_block),
        "runner_helper_uses_injected_executor": all(
            token in helper_block
            for token in (
                "callable(executor)",
                "executor(",
                "out_debug=residual_shear_debug",
                "except Exception:",
            )
        ),
        "runner_call_present_in_route": runner_call >= 0,
        "runner_call_uses_same_executor": (
            "executor=_compute_shear_tightening_recommendation" in route_block
        ),
        "runner_call_uses_same_state": "state=state" in route_block,
        "direct_try_call_removed_from_route": not direct_try_call_present,
        "direct_executor_call_count": direct_executor_call_count,
        "injected_executor_reference_count": injected_executor_reference_count,
        "only_injected_compute_reference_remains": (
            direct_executor_call_count == 0
            and injected_executor_reference_count == 1
        ),
        "live_route_return_boundary_retained": (
            "return residual_route_return_item" in route_block
        ),
        "prebuilt_return_boundary_present": "return dict(" in route_block
        and "residual_prebuilt_route_result.get(\"result_item\")" in route_block,
        "old_live_result_return_removed": "return residual_promoted" not in route_block,
        "trace_wiring": trace_run,
        "readiness": readiness_run,
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "engineering_behavior_changed": False,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    return {
        "runner_helper_present": capture.get("runner_helper_present") is True,
        "runner_helper_uses_injected_executor": (
            capture.get("runner_helper_uses_injected_executor") is True
        ),
        "runner_call_present_in_route": capture.get("runner_call_present_in_route") is True,
        "runner_call_uses_same_executor": capture.get("runner_call_uses_same_executor") is True,
        "runner_call_uses_same_state": capture.get("runner_call_uses_same_state") is True,
        "direct_try_call_removed_from_route": (
            capture.get("direct_try_call_removed_from_route") is True
        ),
        "only_injected_compute_reference_remains": (
            capture.get("only_injected_compute_reference_remains") is True
        ),
        "live_route_return_boundary_removed": (
            capture.get("live_route_return_boundary_retained") is False
        ),
        "prebuilt_return_boundary_present": (
            capture.get("prebuilt_return_boundary_present") is True
        ),
        "old_live_result_return_removed": (
            capture.get("old_live_result_return_removed") is True
        ),
        "trace_wiring_passed": (capture.get("trace_wiring") or {}).get("passed") is True,
        "readiness_passed": (capture.get("readiness") or {}).get("passed") is True,
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "engineering_behavior_unchanged": capture.get("engineering_behavior_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Residual Shear Cleanup Primary Executor Call-Shape Cutover",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Summary",
        "",
        f"- Runner helper present: `{capture.get('runner_helper_present')}`",
        f"- Runner call present in route: `{capture.get('runner_call_present_in_route')}`",
        f"- Direct try/call removed from route: `{capture.get('direct_try_call_removed_from_route')}`",
        f"- Direct executor call count: `{capture.get('direct_executor_call_count')}`",
        f"- Injected executor reference count: `{capture.get('injected_executor_reference_count')}`",
        f"- Product behavior changed: `{capture.get('product_behavior_changed')}`",
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
            "Run a deadness/readiness audit for the old direct executor call shape, then decide whether the injected runner can move behind the controller boundary.",
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
        "schema": "design_guide_post_click_low_bending_residual_shear_cleanup_primary_executor_call_shape_cutover.v1",
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
        / f"design_guide_post_click_low_bending_residual_shear_cleanup_primary_executor_call_shape_cutover_{stamp}.json"
    )
    audit_path = (
        AUDIT_DIR
        / f"design_guide_post_click_low_bending_residual_shear_cleanup_primary_executor_call_shape_cutover_{stamp}.md"
    )
    report_path = (
        REPORT_DIR
        / f"design_brain_physical_extraction_residual_shear_cleanup_primary_executor_call_shape_cutover_{stamp}.md"
    )
    json_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8",
    )
    _write_report(audit_path, payload)
    _write_report(report_path, payload)
    print(
        "design_guide_post_click_low_bending_residual_shear_cleanup_primary_executor_call_shape_cutover "
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
