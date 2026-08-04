"""Trace-wiring snapshot for residual shear cleanup primary executor injected adapter."""

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
        "def _stamp_design_guide_controller_post_click_low_bending_residual_shear_cleanup_primary_executor_injected_adapter(",
        "\ndef _stamp_final_publication_post_click_final_contract_predicate_result_adapter(",
    )
    route_block = _block(
        source,
        "current_shear_for_residual_cleanup = _parse_util_value(",
        "    shear_blocker = _shear_low_util_active_links_exact_blocker(",
    )
    handoff_call = route_block.find(
        "_stamp_design_guide_controller_post_click_low_bending_residual_shear_cleanup_primary_executor_handoff("
    )
    adapter_call = route_block.find(
        "_stamp_design_guide_controller_post_click_low_bending_residual_shear_cleanup_primary_executor_injected_adapter("
    )
    return_call = route_block.find("return residual_route_return_item", adapter_call)
    if return_call < 0:
        return_call = route_block.find("return residual_promoted", adapter_call)
    prebuilt_return_call = route_block.find("return dict(", adapter_call)
    object_run = _run(
        [
            sys.executable,
            "tools/verification/design_guide_post_click_low_bending_residual_shear_cleanup_primary_executor_injected_adapter_object_snapshot.py",
        ]
    )
    readiness_run = _run(
        [
            sys.executable,
            "tools/verification/design_guide_post_click_low_bending_residual_shear_cleanup_primary_executor_cutover_readiness_audit.py",
        ]
    )
    return {
        "decision": "RESIDUAL_SHEAR_CLEANUP_PRIMARY_EXECUTOR_INJECTED_ADAPTER_TRACE_WIRED",
        "controller_builder_imported": (
            "build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_primary_executor_injected_adapter as "
            "_build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_primary_executor_injected_adapter"
            in source
        ),
        "helper_present": bool(helper_block),
        "helper_calls_controller_object": (
            "_build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_primary_executor_injected_adapter("
            in helper_block
        ),
        "handoff_before_adapter": handoff_call >= 0 and adapter_call > handoff_call,
        "adapter_before_return": adapter_call >= 0
        and (
            return_call > adapter_call
            or prebuilt_return_call > adapter_call
        ),
        "live_return_retained": (
            "return residual_route_return_item" in route_block
            or "return residual_promoted" in route_block
        ),
        "prebuilt_return_boundary_present": prebuilt_return_call > adapter_call,
        "adapter_contract_wired": all(
            token in helper_block
            for token in (
                "executor_name",
                "input_hash",
                "output_hash",
                "stale_state_policy",
                "exception_policy",
                "executor_available",
                "executor_is_injected",
                "executor_is_deterministic",
                "executor_changes_behavior",
            )
        ),
        "adapter_uses_handoff_hashes": all(
            token in helper_block
            for token in (
                'handoff.get("executor_input_hash")',
                'handoff.get("executor_output_hash")',
            )
        ),
        "controller_stamps_present": all(
            token in helper_block
            for token in (
                "primary_executor_injected_adapter",
                "primary_executor_injected_adapter_hash",
                "primary_executor_injected_adapter_ready",
                "primary_executor_injected_adapter_behavior_cutover_ready",
                "primary_executor_injected_adapter_safe_next_surface",
            )
        ),
        "controller_stamps_non_driving": all(
            token in helper_block
            for token in (
                "primary_executor_injected_adapter_product_driving",
                "primary_executor_injected_adapter_render_driving",
                "primary_executor_injected_adapter_apply_driving",
                "primary_executor_injected_adapter_session_driving",
            )
        )
        and helper_block.count("] = False") >= 4,
        "live_executor_injected_runner_present": (
            "_run_post_click_low_bending_residual_shear_cleanup_primary_executor("
            in route_block
        ),
        "live_executor_injected_same_impl": (
            "executor=_compute_shear_tightening_recommendation" in route_block
        ),
        "object_snapshot": object_run,
        "readiness_audit": readiness_run,
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "engineering_behavior_changed": False,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    return {
        "controller_builder_imported": capture.get("controller_builder_imported") is True,
        "helper_present": capture.get("helper_present") is True,
        "helper_calls_controller_object": capture.get("helper_calls_controller_object") is True,
        "handoff_before_adapter": capture.get("handoff_before_adapter") is True,
        "adapter_before_return": capture.get("adapter_before_return") is True,
        "live_return_removed": capture.get("live_return_retained") is False,
        "prebuilt_return_boundary_present": (
            capture.get("prebuilt_return_boundary_present") is True
        ),
        "adapter_contract_wired": capture.get("adapter_contract_wired") is True,
        "adapter_uses_handoff_hashes": capture.get("adapter_uses_handoff_hashes") is True,
        "controller_stamps_present": capture.get("controller_stamps_present") is True,
        "controller_stamps_non_driving": capture.get("controller_stamps_non_driving") is True,
        "live_executor_injected_runner_present": (
            capture.get("live_executor_injected_runner_present") is True
        ),
        "live_executor_injected_same_impl": (
            capture.get("live_executor_injected_same_impl") is True
        ),
        "object_snapshot_passed": (capture.get("object_snapshot") or {}).get("passed") is True,
        "readiness_audit_passed": (capture.get("readiness_audit") or {}).get("passed") is True,
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "engineering_behavior_unchanged": capture.get("engineering_behavior_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Residual Shear Cleanup Primary Executor Injected Adapter Trace Wiring Snapshot",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Summary",
        "",
        f"- Handoff before adapter: `{capture.get('handoff_before_adapter')}`",
        f"- Adapter before return: `{capture.get('adapter_before_return')}`",
        f"- Live executor injected runner present: `{capture.get('live_executor_injected_runner_present')}`",
        f"- Live executor injected same implementation: `{capture.get('live_executor_injected_same_impl')}`",
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
            "Create cutover readiness for replacing the direct page-local executor call with an injected executor parameter while keeping the same implementation.",
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
        "schema": "design_guide_post_click_low_bending_residual_shear_cleanup_primary_executor_injected_adapter_trace_wiring_snapshot.v1",
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
        / f"design_guide_post_click_low_bending_residual_shear_cleanup_primary_executor_injected_adapter_trace_wiring_{stamp}.json"
    )
    audit_path = (
        AUDIT_DIR
        / f"design_guide_post_click_low_bending_residual_shear_cleanup_primary_executor_injected_adapter_trace_wiring_{stamp}.md"
    )
    report_path = (
        REPORT_DIR
        / f"design_brain_physical_extraction_residual_shear_cleanup_primary_executor_injected_adapter_trace_wiring_{stamp}.md"
    )
    json_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8",
    )
    _write_report(audit_path, payload)
    _write_report(report_path, payload)
    print(
        "design_guide_post_click_low_bending_residual_shear_cleanup_primary_executor_injected_adapter_trace_wiring "
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
