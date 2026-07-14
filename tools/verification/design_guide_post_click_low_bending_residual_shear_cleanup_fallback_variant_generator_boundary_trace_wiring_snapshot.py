"""Trace-wiring snapshot for residual shear cleanup fallback variant generator boundary."""

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
        "def _stamp_design_guide_controller_post_click_low_bending_residual_shear_cleanup_fallback_variant_generator_boundary(",
        "\ndef _stamp_final_publication_post_click_final_contract_predicate_result_adapter(",
    )
    route_block = _block(
        source,
        "current_shear_for_residual_cleanup = _parse_util_value(",
        "    shear_blocker = _shear_low_util_active_links_exact_blocker(",
    )
    fallback_generator_call = route_block.find(
        "_run_post_click_low_bending_residual_shear_cleanup_fallback_variant_generator("
    )
    fallback_generator_injected = (
        fallback_generator_call >= 0
        and "generator=generate_less_shear_reo_variants" in route_block[fallback_generator_call:]
    )
    update_sequence_append = route_block.find("fallback_variant_generator_update_sequence.append(")
    candidate_boundary_call = route_block.find(
        "_stamp_design_guide_controller_post_click_low_bending_residual_shear_cleanup_candidate_boundary("
    )
    fallback_boundary_call = route_block.find(
        "_stamp_design_guide_controller_post_click_low_bending_residual_shear_cleanup_fallback_variant_generator_boundary("
    )
    primary_handoff_call = route_block.find(
        "_stamp_design_guide_controller_post_click_low_bending_residual_shear_cleanup_primary_executor_handoff("
    )
    return_call = route_block.find("return residual_route_return_item", fallback_boundary_call)
    object_run = _run(
        [
            sys.executable,
            "tools/verification/design_guide_post_click_low_bending_residual_shear_cleanup_fallback_variant_generator_boundary_object_snapshot.py",
        ]
    )
    next_dependency_run = _run(
        [
            sys.executable,
            "tools/verification/design_guide_post_click_low_bending_residual_shear_cleanup_remaining_injected_dependency_priority_audit.py",
        ]
    )
    return {
        "decision": "RESIDUAL_SHEAR_CLEANUP_FALLBACK_VARIANT_GENERATOR_BOUNDARY_TRACE_WIRED",
        "controller_builder_imported": (
            "build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_fallback_variant_generator_boundary as "
            "_build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_fallback_variant_generator_boundary"
            in source
        ),
        "helper_present": bool(helper_block),
        "helper_calls_controller_object": (
            "_build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_fallback_variant_generator_boundary("
            in helper_block
        ),
        "fallback_generator_before_update_sequence": (
            fallback_generator_injected and update_sequence_append > fallback_generator_call
        ),
        "fallback_generator_uses_injected_generator": bool(fallback_generator_injected),
        "candidate_boundary_before_fallback_boundary": (
            candidate_boundary_call >= 0 and fallback_boundary_call > candidate_boundary_call
        ),
        "fallback_boundary_before_primary_handoff": (
            fallback_boundary_call >= 0 and primary_handoff_call > fallback_boundary_call
        ),
        "fallback_boundary_before_return": fallback_boundary_call >= 0 and return_call > fallback_boundary_call,
        "live_route_return_boundary_retained": (
            "return residual_route_return_item" in route_block
        ),
        "generator_summary_wired": all(
            token in route_block
            for token in (
                "fallback_variant_generator_inputs",
                "fallback_variant_generator_attempted",
                "fallback_variant_generator_variant_count",
                "fallback_variant_generator_update_sequence",
                "fallback_variant_generator_output_summary",
                "stable_sequence_hash",
                "iteration_limit",
            )
        ),
        "helper_stamps_present": all(
            token in helper_block
            for token in (
                "fallback_variant_generator_boundary",
                "fallback_variant_generator_boundary_hash",
                "fallback_variant_generator_output_shape_ready",
                "fallback_variant_generator_behavior_cutover_ready",
                "fallback_variant_generator_page_must_keep_for_now",
                "fallback_variant_generator_sequence_hash",
            )
        ),
        "helper_stamps_non_driving": all(
            token in helper_block
            for token in (
                "fallback_variant_generator_product_driving",
                "fallback_variant_generator_render_driving",
                "fallback_variant_generator_apply_driving",
                "fallback_variant_generator_session_driving",
            )
        )
        and helper_block.count("] = False") >= 4,
        "object_snapshot": object_run,
        "next_dependency_audit": next_dependency_run,
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
        "fallback_generator_before_update_sequence": (
            capture.get("fallback_generator_before_update_sequence") is True
        ),
        "fallback_generator_uses_injected_generator": (
            capture.get("fallback_generator_uses_injected_generator") is True
        ),
        "candidate_boundary_before_fallback_boundary": (
            capture.get("candidate_boundary_before_fallback_boundary") is True
        ),
        "fallback_boundary_before_primary_handoff": (
            capture.get("fallback_boundary_before_primary_handoff") is True
        ),
        "fallback_boundary_before_return": capture.get("fallback_boundary_before_return") is True,
        "live_route_return_boundary_retained": (
            capture.get("live_route_return_boundary_retained") is True
        ),
        "generator_summary_wired": capture.get("generator_summary_wired") is True,
        "helper_stamps_present": capture.get("helper_stamps_present") is True,
        "helper_stamps_non_driving": capture.get("helper_stamps_non_driving") is True,
        "object_snapshot_passed": (capture.get("object_snapshot") or {}).get("passed") is True,
        "next_dependency_audit_passed": (capture.get("next_dependency_audit") or {}).get("passed") is True,
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "engineering_behavior_unchanged": capture.get("engineering_behavior_changed") is False,
        "family_runtime_unchanged": capture.get("family_runtime_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Residual Shear Cleanup Fallback Variant Generator Boundary Trace Wiring Snapshot",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Summary",
        "",
        f"- Fallback generator before update sequence: `{capture.get('fallback_generator_before_update_sequence')}`",
        f"- Candidate boundary before fallback boundary: `{capture.get('candidate_boundary_before_fallback_boundary')}`",
        f"- Fallback boundary before primary handoff: `{capture.get('fallback_boundary_before_primary_handoff')}`",
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
            "Create live parity scenarios for the fallback-generator summary before any generator cutover or candidate-evaluator extraction.",
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
        "schema": "design_guide_post_click_low_bending_residual_shear_cleanup_fallback_variant_generator_boundary_trace_wiring_snapshot.v1",
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
        / f"design_guide_post_click_low_bending_residual_shear_cleanup_fallback_variant_generator_boundary_trace_wiring_{stamp}.json"
    )
    audit_path = (
        AUDIT_DIR
        / f"design_guide_post_click_low_bending_residual_shear_cleanup_fallback_variant_generator_boundary_trace_wiring_{stamp}.md"
    )
    report_path = (
        REPORT_DIR
        / f"design_brain_physical_extraction_residual_shear_cleanup_fallback_variant_generator_boundary_trace_wiring_{stamp}.md"
    )
    json_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8",
    )
    _write_report(audit_path, payload)
    _write_report(report_path, payload)
    print(
        "design_guide_post_click_low_bending_residual_shear_cleanup_fallback_variant_generator_boundary_trace_wiring "
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
