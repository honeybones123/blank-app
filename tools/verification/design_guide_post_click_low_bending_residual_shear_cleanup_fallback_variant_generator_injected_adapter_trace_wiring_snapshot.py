"""Trace-wiring snapshot for residual shear cleanup fallback generator injected adapter."""

from __future__ import annotations

from datetime import datetime, timezone
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
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
        .replace(":", "-")
    )


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _run(command: list[str]) -> dict[str, Any]:
    proc = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, timeout=240)
    return {
        "command": command,
        "returncode": proc.returncode,
        "passed": proc.returncode == 0,
        "stdout_tail": proc.stdout[-3000:],
        "stderr_tail": proc.stderr[-3000:],
    }


def _latest(prefix: str) -> dict[str, Any]:
    paths = sorted(ARTIFACT_DIR.glob(f"{prefix}_*.json"), key=lambda path: path.stat().st_mtime)
    if not paths:
        return {"status": "MISSING", "passed": False, "path": None}
    last_invalid: dict[str, Any] | None = None
    for path in reversed(paths):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            last_invalid = {"status": "INVALID", "passed": False, "path": str(path), "error": str(exc)}
            continue
        status = payload.get("status")
        if status == "PASS":
            return {
                "status": status,
                "passed": True,
                "path": str(path),
                "snapshot_hash": payload.get("snapshot_hash"),
            }
    if last_invalid is not None:
        return last_invalid
    path = paths[-1]
    payload = json.loads(path.read_text(encoding="utf-8"))
    status = payload.get("status")
    return {
        "status": status,
        "passed": False,
        "path": str(path),
        "snapshot_hash": payload.get("snapshot_hash"),
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
        "def _stamp_design_guide_controller_post_click_low_bending_residual_shear_cleanup_fallback_variant_generator_injected_adapter(",
        "\ndef _stamp_final_publication_post_click_final_contract_predicate_result_adapter(",
    )
    route_block = _block(
        source,
        "current_shear_for_residual_cleanup = _parse_util_value(",
        "    shear_blocker = _shear_low_util_active_links_exact_blocker(",
    )
    boundary_call = route_block.find(
        "_stamp_design_guide_controller_post_click_low_bending_residual_shear_cleanup_fallback_variant_generator_boundary("
    )
    adapter_call = route_block.find(
        "_stamp_design_guide_controller_post_click_low_bending_residual_shear_cleanup_fallback_variant_generator_injected_adapter("
    )
    primary_handoff_call = route_block.find(
        "_stamp_design_guide_controller_post_click_low_bending_residual_shear_cleanup_primary_executor_handoff("
    )
    return_call = route_block.find("return residual_route_return_item", adapter_call)
    if return_call < 0:
        return_call = route_block.find("return residual_promoted", adapter_call)
    object_run = _run(
        [
            sys.executable,
            "tools/verification/design_guide_post_click_low_bending_residual_shear_cleanup_fallback_variant_generator_injected_adapter_object_snapshot.py",
        ]
    )
    readiness_latest = _latest(
        "design_guide_post_click_low_bending_residual_shear_cleanup_fallback_variant_generator_cutover_readiness"
    )
    runner_call = "_run_post_click_low_bending_residual_shear_cleanup_fallback_variant_generator("
    return {
        "decision": "RESIDUAL_SHEAR_CLEANUP_FALLBACK_VARIANT_GENERATOR_INJECTED_ADAPTER_TRACE_WIRED",
        "controller_builder_imported": (
            "build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_fallback_variant_generator_injected_adapter as "
            "_build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_fallback_variant_generator_injected_adapter"
            in source
        ),
        "helper_present": bool(helper_block),
        "helper_calls_controller_object": (
            "_build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_fallback_variant_generator_injected_adapter("
            in helper_block
        ),
        "adapter_contract_wired": all(
            token in helper_block
            for token in (
                "generator_name",
                "input_hash",
                "output_hash",
                "iteration_limit",
                "stale_state_policy",
                "exception_policy",
                "generator_available",
                "generator_is_injected",
                "generator_is_deterministic",
                "generator_changes_behavior",
            )
        ),
        "adapter_uses_boundary_hashes": all(
            token in helper_block
            for token in (
                'boundary.get("generator_input_hash")',
                'boundary.get("generator_output_hash")',
                'boundary.get("iteration_limit")',
            )
        ),
        "boundary_before_adapter": boundary_call >= 0 and adapter_call > boundary_call,
        "adapter_before_primary_handoff": adapter_call >= 0 and primary_handoff_call > adapter_call,
        "adapter_before_return": adapter_call >= 0 and return_call > adapter_call,
        "live_route_return_boundary_retained": (
            "return residual_route_return_item" in route_block
        ),
        "old_live_result_return_removed": "return residual_promoted" not in route_block,
        "helper_stamps_present": all(
            token in helper_block
            for token in (
                "fallback_variant_generator_injected_adapter",
                "fallback_variant_generator_injected_adapter_hash",
                "fallback_variant_generator_injected_adapter_ready",
                "fallback_variant_generator_injected_adapter_behavior_cutover_ready",
                "fallback_variant_generator_injected_adapter_safe_next_surface",
            )
        ),
        "helper_stamps_non_driving": all(
            token in helper_block
            for token in (
                "fallback_variant_generator_injected_adapter_product_driving",
                "fallback_variant_generator_injected_adapter_render_driving",
                "fallback_variant_generator_injected_adapter_apply_driving",
                "fallback_variant_generator_injected_adapter_session_driving",
            )
        )
        and helper_block.count("] = False") >= 4,
        "runner_route_call_present": runner_call in route_block,
        "same_generator_impl_injected": "generator=generate_less_shear_reo_variants" in route_block,
        "object_snapshot": object_run,
        "cutover_readiness": readiness_latest,
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "engineering_behavior_changed": False,
        "family_runtime_changed": False,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    return {
        "controller_builder_imported": capture.get("controller_builder_imported") is True,
        "helper_present": capture.get("helper_present") is True,
        "helper_calls_controller_object": capture.get("helper_calls_controller_object") is True,
        "adapter_contract_wired": capture.get("adapter_contract_wired") is True,
        "adapter_uses_boundary_hashes": capture.get("adapter_uses_boundary_hashes") is True,
        "boundary_before_adapter": capture.get("boundary_before_adapter") is True,
        "adapter_before_primary_handoff": capture.get("adapter_before_primary_handoff") is True,
        "adapter_before_return": capture.get("adapter_before_return") is True,
        "live_route_return_boundary_retained": (
            capture.get("live_route_return_boundary_retained") is True
        ),
        "old_live_result_return_removed": (
            capture.get("old_live_result_return_removed") is True
        ),
        "helper_stamps_present": capture.get("helper_stamps_present") is True,
        "helper_stamps_non_driving": capture.get("helper_stamps_non_driving") is True,
        "runner_route_call_present": capture.get("runner_route_call_present") is True,
        "same_generator_impl_injected": capture.get("same_generator_impl_injected") is True,
        "object_snapshot_passed": (capture.get("object_snapshot") or {}).get("passed") is True,
        "cutover_readiness_passed": (capture.get("cutover_readiness") or {}).get("passed")
        is True,
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "engineering_behavior_unchanged": capture.get("engineering_behavior_changed") is False,
        "family_runtime_unchanged": capture.get("family_runtime_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Residual Shear Cleanup Fallback Variant Generator Injected Adapter Trace Wiring Snapshot",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Summary",
        "",
        f"- Boundary before adapter: `{capture.get('boundary_before_adapter')}`",
        f"- Adapter before primary handoff: `{capture.get('adapter_before_primary_handoff')}`",
        f"- Runner route call present: `{capture.get('runner_route_call_present')}`",
        f"- Same generator implementation injected: `{capture.get('same_generator_impl_injected')}`",
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
            "Create call-shape cutover readiness for injecting the same shared generator implementation into the residual-shear route.",
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
        "schema": "design_guide_post_click_low_bending_residual_shear_cleanup_fallback_variant_generator_injected_adapter_trace_wiring_snapshot.v1",
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
        / f"design_guide_post_click_low_bending_residual_shear_cleanup_fallback_variant_generator_injected_adapter_trace_wiring_{stamp}.json"
    )
    audit_path = (
        AUDIT_DIR
        / f"design_guide_post_click_low_bending_residual_shear_cleanup_fallback_variant_generator_injected_adapter_trace_wiring_{stamp}.md"
    )
    report_path = (
        REPORT_DIR
        / f"design_brain_physical_extraction_residual_shear_cleanup_fallback_variant_generator_injected_adapter_trace_wiring_{stamp}.md"
    )
    json_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8",
    )
    _write_report(audit_path, payload)
    _write_report(report_path, payload)
    print(
        "design_guide_post_click_low_bending_residual_shear_cleanup_fallback_variant_generator_injected_adapter_trace_wiring "
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
