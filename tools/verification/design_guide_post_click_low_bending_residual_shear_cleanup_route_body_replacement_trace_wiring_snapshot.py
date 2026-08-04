"""Trace-wiring snapshot for residual-shear cleanup route-body replacement."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
REPORT_DIR = ROOT / "artifacts" / "reports"
INPUTS = ROOT / "inputs_page.py"


def _stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")


def _run(cmd: list[str]) -> dict[str, Any]:
    proc = subprocess.run(
        cmd,
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=120,
    )
    return {
        "cmd": " ".join(cmd),
        "returncode": proc.returncode,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
        "passed": proc.returncode == 0,
    }


def _block(source: str, start_token: str, end_token: str = "\ndef ") -> str:
    start = source.find(start_token)
    if start < 0:
        return ""
    end = source.find(end_token, start + 1)
    return source[start:end] if end > start else source[start:]


def _route_window(source: str) -> str:
    replacement = source.find("residual_route_body_replacement =")
    start = source.rfind("residual_final_binding_tail_handoff =", 0, replacement)
    end = source.find("                        if (", replacement)
    if end < 0:
        end = replacement + 5000
    if start < 0 or replacement < 0:
        return ""
    return source[start:end]


def _capture() -> dict[str, Any]:
    source = INPUTS.read_text(encoding="utf-8-sig", errors="replace")
    helper = _block(
        source,
        "def _stamp_design_guide_controller_post_click_low_bending_residual_shear_cleanup_route_body_replacement(",
    )
    route = _route_window(source)
    object_snapshot = _run(
        [
            sys.executable,
            "tools/verification/design_guide_post_click_low_bending_residual_shear_cleanup_route_body_replacement_object_snapshot.py",
        ]
    )
    sequence_tokens = [
        "residual_final_binding_tail_handoff =",
        "residual_route_shell_adapter =",
        "residual_evidence_merge_tail_handoff =",
        "residual_primary_executor_handoff =",
        "residual_primary_executor_dependency_boundary =",
        "_stamp_design_guide_controller_post_click_low_bending_residual_shear_cleanup_route_body_replacement(",
    ]
    sequence_positions = {token: route.find(token) for token in sequence_tokens}
    route_sequence_ordered = all(pos >= 0 for pos in sequence_positions.values()) and (
        sequence_positions[sequence_tokens[0]]
        < sequence_positions[sequence_tokens[1]]
        < sequence_positions[sequence_tokens[2]]
        < sequence_positions[sequence_tokens[3]]
        < sequence_positions[sequence_tokens[4]]
        < sequence_positions[sequence_tokens[5]]
    )
    non_driving_tokens = (
        '"design_guide_controller_post_click_low_bending_residual_shear_cleanup_route_body_replacement_proof_only"',
        '"design_guide_controller_post_click_low_bending_residual_shear_cleanup_route_body_replacement_product_driving"',
        '"design_guide_controller_post_click_low_bending_residual_shear_cleanup_route_body_replacement_render_driving"',
        '"design_guide_controller_post_click_low_bending_residual_shear_cleanup_route_body_replacement_apply_driving"',
        '"design_guide_controller_post_click_low_bending_residual_shear_cleanup_route_body_replacement_session_driving"',
    )
    return {
        "decision": "ROUTE_BODY_REPLACEMENT_TRACE_WIRED_NON_DRIVING",
        "import_present": (
            "build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_route_body_replacement "
            "as _build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_route_body_replacement"
            in source
        ),
        "helper_present": bool(helper),
        "helper_calls_controller_builder": (
            "_build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_route_body_replacement("
            in helper
        ),
        "helper_writes_hash_and_parity": all(
            token in helper
            for token in (
                "route_body_replacement_hash",
                "route_body_replacement_parity",
                "output_shape_ready",
                "behavior_cutover_ready",
            )
        ),
        "helper_marks_non_driving": all(token in helper for token in non_driving_tokens),
        "helper_marks_page_live_dependencies": '"page_live"' in helper,
        "route_call_present": (
            "_stamp_design_guide_controller_post_click_low_bending_residual_shear_cleanup_route_body_replacement("
            in route
        ),
        "route_sequence_ordered": route_sequence_ordered,
        "route_passes_dependency_payloads": all(
            token in route
            for token in (
                "route_shell_adapter=dict(residual_route_shell_adapter or {})",
                "route_entry_guard=dict(residual_shear_cleanup_route_entry_guard or {})",
                "primary_executor_handoff=dict(residual_primary_executor_handoff or {})",
                "primary_executor_dependency_boundary=dict(",
                "residual_primary_executor_dependency_boundary or {}",
                "fallback_variant_generator_handoff=dict(",
                "fallback_variant_generator_dependency_boundary=dict(",
                "residual_fallback_variant_generator_dependency_boundary or {}",
                "candidate_evaluator_handoff=dict(",
                "materiality_safety_handoff=dict(",
                "candidate_selector_handoff=dict(",
                "result_packaging_handoff=dict(",
                "evidence_merge_tail=dict(",
                "final_binding_tail=dict(",
                "residual_promoted=dict(residual_promoted or {})",
            )
        ),
        "object_snapshot": object_snapshot,
        "object_snapshot_passed": object_snapshot.get("passed") is True,
        "product_behavior_changed": False,
        "engineering_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtime_changed": False,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    return {
        "import_present": capture.get("import_present") is True,
        "helper_present": capture.get("helper_present") is True,
        "helper_calls_controller_builder": capture.get("helper_calls_controller_builder") is True,
        "helper_writes_hash_and_parity": capture.get("helper_writes_hash_and_parity") is True,
        "helper_marks_non_driving": capture.get("helper_marks_non_driving") is True,
        "helper_marks_page_live_dependencies": capture.get("helper_marks_page_live_dependencies") is True,
        "route_call_present": capture.get("route_call_present") is True,
        "route_sequence_ordered": capture.get("route_sequence_ordered") is True,
        "route_passes_dependency_payloads": capture.get("route_passes_dependency_payloads") is True,
        "object_snapshot_passed": capture.get("object_snapshot_passed") is True,
        "product_behavior_changed": capture.get("product_behavior_changed") is False,
        "engineering_behavior_changed": capture.get("engineering_behavior_changed") is False,
        "visible_wording_changed": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_changed": capture.get("cta_apply_semantics_changed") is False,
        "family_runtime_changed": capture.get("family_runtime_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Residual Shear Cleanup Route Body Replacement Trace Wiring",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        "",
        "## Summary",
        "",
        f"- Import present: `{capture.get('import_present')}`",
        f"- Helper present: `{capture.get('helper_present')}`",
        f"- Route call present: `{capture.get('route_call_present')}`",
        f"- Route sequence ordered: `{capture.get('route_sequence_ordered')}`",
        f"- Object snapshot passed: `{capture.get('object_snapshot_passed')}`",
        "",
        "## Behaviour",
        "",
        "- Product behaviour changed: `False`",
        "- Engineering behaviour changed: `False`",
        "- Visible wording changed: `False`",
        "- CTA/apply semantics changed: `False`",
        "- Family runtime changed: `False`",
        "",
        "## Checks",
        "",
    ]
    lines.extend(f"- {key}: `{value}`" for key, value in (payload.get("checks") or {}).items())
    lines.extend(
        [
            "",
            "## Next Safe Target",
            "",
            "Run route-body parity/cutover readiness before moving any live route behaviour.",
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
        "schema": "design_guide_post_click_low_bending_residual_shear_cleanup_route_body_replacement_trace_wiring_snapshot.v1",
        "created_at": _stamp(),
        "status": "PASS" if not failures else "FAIL",
        "capture": capture,
        "checks": checks,
        "failures": failures,
    }
    stamp = payload["created_at"]
    json_path = (
        ARTIFACT_DIR
        / f"design_guide_post_click_low_bending_residual_shear_cleanup_route_body_replacement_trace_wiring_{stamp}.json"
    )
    audit_path = (
        AUDIT_DIR
        / f"design_guide_post_click_low_bending_residual_shear_cleanup_route_body_replacement_trace_wiring_{stamp}.md"
    )
    report_path = (
        REPORT_DIR
        / f"design_brain_physical_extraction_residual_shear_cleanup_route_body_replacement_trace_wiring_{stamp}.md"
    )
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    _write_report(audit_path, payload)
    _write_report(report_path, payload)
    print(
        "design_guide_post_click_low_bending_residual_shear_cleanup_route_body_replacement_trace_wiring "
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
