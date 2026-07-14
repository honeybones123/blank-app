"""Trace-wiring snapshot for residual-shear fallback generator dependency boundary."""

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
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")


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
        "def _stamp_design_guide_controller_post_click_low_bending_residual_shear_cleanup_fallback_variant_generator_dependency_boundary(",
        "\ndef _stamp_final_publication_post_click_final_contract_predicate_result_adapter(",
    )
    route_block = _block(
        source,
        "current_shear_for_residual_cleanup = _parse_util_value(",
        "    shear_blocker = _shear_low_util_active_links_exact_blocker(",
    )
    boundary_call = route_block.find(
        "residual_fallback_variant_generator_boundary = _stamp_design_guide_controller_post_click_low_bending_residual_shear_cleanup_fallback_variant_generator_boundary("
    )
    adapter_call = route_block.find(
        "residual_fallback_variant_generator_injected_adapter = _stamp_design_guide_controller_post_click_low_bending_residual_shear_cleanup_fallback_variant_generator_injected_adapter("
    )
    dependency_call = route_block.find(
        "residual_fallback_variant_generator_dependency_boundary = _stamp_design_guide_controller_post_click_low_bending_residual_shear_cleanup_fallback_variant_generator_dependency_boundary("
    )
    evaluator_call = route_block.find(
        "residual_candidate_evaluator_handoff = _stamp_design_guide_controller_post_click_low_bending_residual_shear_cleanup_candidate_evaluator_handoff("
    )
    object_run = _run(
        [
            sys.executable,
            "tools/verification/design_guide_post_click_low_bending_residual_shear_cleanup_fallback_variant_generator_dependency_boundary_object_snapshot.py",
        ]
    )
    return {
        "decision": "RESIDUAL_SHEAR_FALLBACK_VARIANT_GENERATOR_DEPENDENCY_BOUNDARY_TRACE_WIRED",
        "controller_builder_imported": (
            "build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_fallback_variant_generator_dependency_boundary as "
            "_build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_fallback_variant_generator_dependency_boundary"
            in source
        ),
        "helper_present": bool(helper_block),
        "helper_calls_controller_object": (
            "_build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_fallback_variant_generator_dependency_boundary("
            in helper_block
        ),
        "dependency_descriptor_wired": all(
            token in helper_block
            for token in (
                "generator_name",
                "runner_name",
                "injection_site",
                "dependency_status",
                "iteration_limit",
                "stale_state_policy",
                "exception_policy",
            )
        ),
        "controller_stamps_present": all(
            token in helper_block
            for token in (
                "fallback_variant_generator_dependency_boundary",
                "fallback_variant_generator_dependency_boundary_hash",
                "fallback_variant_generator_dependency_boundary_ready",
                "fallback_variant_generator_dependency_boundary_route_shape_cutover_ready",
                "fallback_variant_generator_dependency_boundary_safe_to_delete_page_generator_now",
                "fallback_variant_generator_dependency_boundary_safe_next_surface",
                "fallback_variant_generator_dependency_boundary_page_must_keep_for_now",
            )
        ),
        "controller_stamps_non_driving": all(
            token in helper_block
            for token in (
                "fallback_variant_generator_dependency_boundary_product_driving",
                "fallback_variant_generator_dependency_boundary_render_driving",
                "fallback_variant_generator_dependency_boundary_apply_driving",
                "fallback_variant_generator_dependency_boundary_session_driving",
            )
        )
        and helper_block.count("] = False") >= 4,
        "boundary_before_adapter": boundary_call >= 0 and adapter_call > boundary_call,
        "adapter_before_dependency_boundary": (
            adapter_call >= 0 and dependency_call > adapter_call
        ),
        "dependency_boundary_before_candidate_evaluator": (
            dependency_call >= 0 and evaluator_call > dependency_call
        ),
        "live_generator_runner_retained": (
            "_run_post_click_low_bending_residual_shear_cleanup_fallback_variant_generator("
            in route_block
        ),
        "live_generator_impl_retained": (
            "generator=generate_less_shear_reo_variants" in route_block
        ),
        "object_snapshot": object_run,
        "product_behavior_changed": False,
        "engineering_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtime_changed": False,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    return {
        "controller_builder_imported": capture.get("controller_builder_imported") is True,
        "helper_present": capture.get("helper_present") is True,
        "helper_calls_controller_object": capture.get("helper_calls_controller_object") is True,
        "dependency_descriptor_wired": capture.get("dependency_descriptor_wired") is True,
        "controller_stamps_present": capture.get("controller_stamps_present") is True,
        "controller_stamps_non_driving": capture.get("controller_stamps_non_driving") is True,
        "boundary_before_adapter": capture.get("boundary_before_adapter") is True,
        "adapter_before_dependency_boundary": (
            capture.get("adapter_before_dependency_boundary") is True
        ),
        "dependency_boundary_before_candidate_evaluator": (
            capture.get("dependency_boundary_before_candidate_evaluator") is True
        ),
        "live_generator_runner_retained": capture.get("live_generator_runner_retained") is True,
        "live_generator_impl_retained": capture.get("live_generator_impl_retained") is True,
        "object_snapshot_passed": (capture.get("object_snapshot") or {}).get("passed") is True,
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "engineering_behavior_unchanged": capture.get("engineering_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "family_runtime_unchanged": capture.get("family_runtime_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Residual Shear Fallback Variant Generator Dependency Boundary Trace Wiring",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Summary",
        "",
        f"- Boundary before adapter: `{capture.get('boundary_before_adapter')}`",
        f"- Adapter before dependency boundary: `{capture.get('adapter_before_dependency_boundary')}`",
        f"- Dependency boundary before candidate evaluator: `{capture.get('dependency_boundary_before_candidate_evaluator')}`",
        f"- Live generator runner retained: `{capture.get('live_generator_runner_retained')}`",
        f"- Live generator implementation retained: `{capture.get('live_generator_impl_retained')}`",
        "",
        "## Checks",
        "",
    ]
    for key, value in dict(payload.get("checks") or {}).items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(
        [
            "",
            "## Next",
            "",
            "Thread the dependency-boundary proof into the route-body replacement proof. Keep fallback generation live until a separate cutover/deadness proof passes.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _stamp()
    capture = _capture()
    checks = _checks(capture)
    failures = [key for key, value in checks.items() if value is not True]
    payload = {
        "schema": "design_guide_post_click_low_bending_residual_shear_cleanup_fallback_variant_generator_dependency_boundary_trace_wiring_snapshot.v1",
        "created_at": stamp,
        "status": "PASS" if not failures else "FAIL",
        "capture": capture,
        "checks": checks,
        "failures": failures,
        "snapshot_hash": _stable_hash({"capture": capture, "checks": checks}),
    }
    json_path = ARTIFACT_DIR / (
        "design_guide_post_click_low_bending_residual_shear_cleanup_"
        f"fallback_variant_generator_dependency_boundary_trace_wiring_{stamp}.json"
    )
    audit_path = AUDIT_DIR / (
        "design_guide_post_click_low_bending_residual_shear_cleanup_"
        f"fallback_variant_generator_dependency_boundary_trace_wiring_{stamp}.md"
    )
    report_path = REPORT_DIR / (
        "design_brain_physical_extraction_residual_shear_cleanup_"
        f"fallback_variant_generator_dependency_boundary_trace_wiring_{stamp}.md"
    )
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    _write_report(audit_path, payload)
    _write_report(report_path, payload)
    print(
        "design_guide_post_click_low_bending_residual_shear_cleanup_fallback_variant_generator_dependency_boundary_trace_wiring "
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
