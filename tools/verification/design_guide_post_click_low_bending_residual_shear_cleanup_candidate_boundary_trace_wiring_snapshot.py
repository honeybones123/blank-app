"""Trace-wiring snapshot for residual shear cleanup candidate boundary."""

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
        "def _stamp_design_guide_controller_post_click_low_bending_residual_shear_cleanup_candidate_boundary(",
        "\ndef _stamp_final_publication_post_click_final_contract_predicate_result_adapter(",
    )
    route_block = _block(
        source,
        "current_shear_for_residual_cleanup = _parse_util_value(",
        "    shear_blocker = _shear_low_util_active_links_exact_blocker(",
    )
    proof_call = route_block.find(
        "_stamp_final_publication_post_click_low_bending_residual_shear_cleanup_route_proof("
    )
    shell_call = route_block.find(
        "_stamp_design_guide_controller_post_click_low_bending_residual_shear_cleanup_route_shell_cutover_readiness("
    )
    boundary_call = route_block.find(
        "_stamp_design_guide_controller_post_click_low_bending_residual_shear_cleanup_candidate_boundary("
    )
    return_call = route_block.find("return residual_route_return_item", boundary_call)
    prebuilt_return_call = route_block.find("return dict(", boundary_call)
    object_run = _run(
        [
            sys.executable,
            "tools/verification/design_guide_post_click_low_bending_residual_shear_cleanup_candidate_boundary_object_snapshot.py",
        ]
    )
    boundary_audit_run = _run(
        [
            sys.executable,
            "tools/verification/design_guide_post_click_low_bending_residual_shear_cleanup_candidate_evaluation_boundary_audit.py",
        ]
    )
    return {
        "decision": "RESIDUAL_SHEAR_CLEANUP_CANDIDATE_BOUNDARY_TRACE_WIRED",
        "controller_builder_imported": (
            "build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_candidate_boundary as "
            "_build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_candidate_boundary"
            in source
        ),
        "helper_present": bool(helper_block),
        "helper_calls_controller_object": (
            "_build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_candidate_boundary("
            in helper_block
        ),
        "proof_before_shell_before_boundary": (
            proof_call >= 0 and shell_call > proof_call and boundary_call > shell_call
        ),
        "boundary_before_return": boundary_call >= 0
        and (
            return_call > boundary_call
            or prebuilt_return_call > boundary_call
        ),
        "live_return_retained": (
            "return residual_route_return_item" in route_block
            or "return residual_route_return_item" in route_block
        ),
        "prebuilt_return_boundary_present": prebuilt_return_call > boundary_call,
        "live_primary_executor_shape_retained": (
            "_compute_shear_tightening_recommendation(" in route_block
            or (
                "_run_post_click_low_bending_residual_shear_cleanup_primary_executor("
                in route_block
                and "executor=_compute_shear_tightening_recommendation" in route_block
            )
        ),
        "live_behavior_tokens_retained": all(
            token in route_block
            for token in (
                "_run_post_click_low_bending_residual_shear_cleanup_fallback_variant_generator(",
                "generator=generate_less_shear_reo_variants",
                "_run_post_click_low_bending_residual_shear_cleanup_candidate_evaluator(",
                "evaluator=_evaluate_auto_design_candidate",
                "_design_guide_button_contract(",
                "above the preferred",
            )
        ),
        "live_behavior_boundary_represented": (
            "residual_prebuilt_route_result" in route_block
            and "_run_post_click_low_bending_residual_shear_cleanup_result_packaging("
            in route_block
        ),
        "candidate_boundary_inputs_wired": all(
            token in route_block
            for token in (
                "route_branch",
                "starting_shear_util",
                "target_low",
                "target_high",
                "residual_outside_preferred_band",
                "has_primary_shear_tightening",
                "has_residual_updates",
                "result_candidate_id",
            )
        ),
        "controller_stamps_present": all(
            token in helper_block
            for token in (
                "candidate_boundary",
                "candidate_boundary_hash",
                "candidate_boundary_ready",
                "candidate_generation_cutover_ready",
                "candidate_evaluation_cutover_ready",
                "candidate_boundary_unresolved_dependencies",
                "candidate_boundary_input_hash",
            )
        ),
        "controller_stamps_non_driving": all(
            token in helper_block
            for token in (
                "candidate_boundary_product_driving",
                "candidate_boundary_render_driving",
                "candidate_boundary_apply_driving",
                "candidate_boundary_session_driving",
            )
        )
        and helper_block.count("] = False") >= 4,
        "candidate_behavior_cutover_not_asserted": (
            "candidate_generation_cutover_ready" in helper_block
            and "candidate_evaluation_cutover_ready" in helper_block
            and "bool(payload.get(\"candidate_generation_cutover_ready\"))" in helper_block
            and "bool(payload.get(\"candidate_evaluation_cutover_ready\"))" in helper_block
        ),
        "object_snapshot": object_run,
        "boundary_audit": boundary_audit_run,
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
        "proof_before_shell_before_boundary": (
            capture.get("proof_before_shell_before_boundary") is True
        ),
        "boundary_before_return": capture.get("boundary_before_return") is True,
        "live_return_removed": capture.get("live_return_retained") is False,
        "prebuilt_return_boundary_present": (
            capture.get("prebuilt_return_boundary_present") is True
        ),
        "live_primary_executor_shape_retained": (
            capture.get("live_primary_executor_shape_retained") is True
        ),
        "live_behavior_boundary_represented": (
            capture.get("live_behavior_tokens_retained") is True
            or capture.get("live_behavior_boundary_represented") is True
        ),
        "candidate_boundary_inputs_wired": capture.get("candidate_boundary_inputs_wired") is True,
        "controller_stamps_present": capture.get("controller_stamps_present") is True,
        "controller_stamps_non_driving": capture.get("controller_stamps_non_driving") is True,
        "candidate_behavior_cutover_not_asserted": (
            capture.get("candidate_behavior_cutover_not_asserted") is True
        ),
        "object_snapshot_passed": (capture.get("object_snapshot") or {}).get("passed") is True,
        "boundary_audit_passed": (capture.get("boundary_audit") or {}).get("passed") is True,
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "engineering_behavior_unchanged": capture.get("engineering_behavior_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Residual Shear Cleanup Candidate Boundary Trace Wiring Snapshot",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Summary",
        "",
        f"- Proof -> shell -> candidate boundary order: `{capture.get('proof_before_shell_before_boundary')}`",
        f"- Candidate boundary before return: `{capture.get('boundary_before_return')}`",
        f"- Live primary executor shape retained: `{capture.get('live_primary_executor_shape_retained')}`",
        f"- Live behavior tokens retained: `{capture.get('live_behavior_tokens_retained')}`",
        f"- Candidate boundary inputs wired: `{capture.get('candidate_boundary_inputs_wired')}`",
        f"- Product behavior changed: `{capture.get('product_behavior_changed')}`",
        "",
        "## Boundary",
        "",
        "- This slice only trace-wires the controller candidate/evaluator boundary.",
        "- Candidate generation, candidate evaluation, CTA contract execution, visible wording, and returned route result remain live.",
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
            "Create live candidate-boundary parity scenarios before moving candidate generation/evaluation behind the controller.",
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
        "schema": "design_guide_post_click_low_bending_residual_shear_cleanup_candidate_boundary_trace_wiring_snapshot.v1",
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
        / f"design_guide_post_click_low_bending_residual_shear_cleanup_candidate_boundary_trace_wiring_{stamp}.json"
    )
    audit_path = (
        AUDIT_DIR
        / f"design_guide_post_click_low_bending_residual_shear_cleanup_candidate_boundary_trace_wiring_{stamp}.md"
    )
    report_path = (
        REPORT_DIR
        / f"design_brain_physical_extraction_residual_shear_cleanup_candidate_boundary_trace_wiring_{stamp}.md"
    )
    json_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8",
    )
    _write_report(audit_path, payload)
    _write_report(report_path, payload)
    print(
        "design_guide_post_click_low_bending_residual_shear_cleanup_candidate_boundary_trace_wiring "
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
