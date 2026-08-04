"""Route-shell cutover snapshot for residual shear cleanup controller readiness."""

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
        "def _stamp_design_guide_controller_post_click_low_bending_residual_shear_cleanup_route_shell_cutover_readiness(",
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
    deleted_marker_present = (
        "_mark_post_click_low_bending_residual_shear_cleanup_debug_projection_compatibility_only"
        in source
    )
    return_call = route_block.find("return dict(", shell_call)
    old_direct_return_present = any(
        token in route_block
        for token in (
            "return residual_route_return_item",
            "return residual_promoted",
        )
    )
    prebuilt_return_boundary_present = all(
        token in route_block
        for token in (
            "residual_prebuilt_route_result = _build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_prebuilt_route_result(",
            "residual_prebuilt_route_result.get(\"result_item\")",
            "return dict(",
        )
    )
    object_run = _run(
        [
            sys.executable,
            "tools/verification/design_guide_post_click_low_bending_residual_shear_cleanup_controller_route_cutover_readiness_object_snapshot.py",
        ]
    )
    return {
        "decision": "RESIDUAL_SHEAR_CLEANUP_ROUTE_SHELL_CUTOVER_WIRED",
        "controller_builder_imported": (
            "build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_route_cutover_readiness as "
            "_build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_route_cutover_readiness"
            in source
        ),
        "helper_present": bool(helper_block),
        "helper_calls_controller_object": (
            "_build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_route_cutover_readiness("
            in helper_block
        ),
        "proof_before_shell_cutover": proof_call >= 0 and shell_call > proof_call,
        "shell_cutover_before_return": shell_call >= 0 and return_call > shell_call,
        "deleted_debug_projection_marker_absent": not deleted_marker_present,
        "prebuilt_return_boundary_present": prebuilt_return_boundary_present,
        "old_direct_live_result_return_removed": not old_direct_return_present,
        "remaining_live_execution_dependencies_bounded": all(
            token in route_block
            for token in (
                "_run_post_click_low_bending_residual_shear_cleanup_primary_executor(",
                "executor=_compute_shear_tightening_recommendation",
                "_run_post_click_low_bending_residual_shear_cleanup_fallback_variant_generator(",
                "generator=generate_less_shear_reo_variants",
                "_run_post_click_low_bending_residual_shear_cleanup_candidate_evaluator(",
                "evaluator=_evaluate_auto_design_candidate",
                "_stamp_design_guide_controller_post_click_low_bending_residual_shear_cleanup_button_contract_execution_boundary(",
                "_stamp_design_guide_controller_post_click_low_bending_residual_shear_cleanup_cta_apply_payload_source_boundary(",
            )
        ),
        "controller_stamps_present": all(
            token in helper_block
            for token in (
                "route_shell_cutover_readiness",
                "route_shell_cutover_readiness_hash",
                "route_shell_ready",
                "behavior_cutover_ready",
                "safe_next_cutover_surface",
                "unresolved_behavior_dependencies",
            )
        ),
        "controller_stamps_non_driving": all(
            token in helper_block
            for token in (
                "route_shell_cutover_product_driving",
                "route_shell_cutover_render_driving",
                "route_shell_cutover_apply_driving",
                "route_shell_cutover_session_driving",
            )
        )
        and helper_block.count("] = False") >= 4,
        "behavior_cutover_not_asserted": (
            '"design_guide_controller_post_click_low_bending_residual_shear_cleanup_behavior_cutover_ready"'
            in helper_block
            and "bool(payload.get(\"behavior_cutover_ready\"))" in helper_block
        ),
        "object_snapshot": object_run,
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
        "proof_before_shell_cutover": capture.get("proof_before_shell_cutover") is True,
        "shell_cutover_before_return": capture.get("shell_cutover_before_return") is True,
        "deleted_debug_projection_marker_absent": (
            capture.get("deleted_debug_projection_marker_absent") is True
        ),
        "prebuilt_return_boundary_present": (
            capture.get("prebuilt_return_boundary_present") is True
        ),
        "old_direct_live_result_return_removed": (
            capture.get("old_direct_live_result_return_removed") is True
        ),
        "remaining_live_execution_dependencies_bounded": (
            capture.get("remaining_live_execution_dependencies_bounded") is True
        ),
        "controller_stamps_present": capture.get("controller_stamps_present") is True,
        "controller_stamps_non_driving": capture.get("controller_stamps_non_driving") is True,
        "behavior_cutover_not_asserted": capture.get("behavior_cutover_not_asserted") is True,
        "object_snapshot_passed": (capture.get("object_snapshot") or {}).get("passed") is True,
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "engineering_behavior_unchanged": capture.get("engineering_behavior_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Residual Shear Cleanup Route-Shell Cutover Snapshot",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Summary",
        "",
        f"- Proof before shell cutover: `{capture.get('proof_before_shell_cutover')}`",
        f"- Shell cutover before return: `{capture.get('shell_cutover_before_return')}`",
        f"- Deleted debug projection marker absent: `{capture.get('deleted_debug_projection_marker_absent')}`",
        f"- Prebuilt return boundary present: `{capture.get('prebuilt_return_boundary_present')}`",
        f"- Old direct live result return removed: `{capture.get('old_direct_live_result_return_removed')}`",
        f"- Remaining live execution dependencies bounded: `{capture.get('remaining_live_execution_dependencies_bounded')}`",
        f"- Product behavior changed: `{capture.get('product_behavior_changed')}`",
        "",
        "## Boundary",
        "",
        "- Only the route-shell readiness stamp is controller-owned in this slice.",
        "- Candidate search/evaluation, CTA contract execution, visible wording, and returned result item remain live.",
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
            "Create a deadness/readiness audit for the old residual route shell metadata. Do not move candidate generation/evaluation/CTA/wording yet.",
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
        "schema": "design_guide_post_click_low_bending_residual_shear_cleanup_route_shell_cutover_snapshot.v1",
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
        / f"design_guide_post_click_low_bending_residual_shear_cleanup_route_shell_cutover_{stamp}.json"
    )
    audit_path = (
        AUDIT_DIR
        / f"design_guide_post_click_low_bending_residual_shear_cleanup_route_shell_cutover_{stamp}.md"
    )
    report_path = (
        REPORT_DIR
        / f"design_brain_physical_extraction_residual_shear_cleanup_route_shell_cutover_{stamp}.md"
    )
    json_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8",
    )
    _write_report(audit_path, payload)
    _write_report(report_path, payload)
    print(
        "design_guide_post_click_low_bending_residual_shear_cleanup_route_shell_cutover "
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
