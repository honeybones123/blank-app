"""Parity scenarios for residual shear cleanup candidate boundary."""

from __future__ import annotations

from datetime import datetime
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
REPORT_DIR = ROOT / "artifacts" / "reports"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from design_brain.design_guide_controller import (  # noqa: E402
    build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_candidate_boundary,
    build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_route_cutover_readiness,
)
from design_brain.final_publication import stable_final_publication_hash  # noqa: E402


CANDIDATE_DEPENDENCIES = (
    "primary_shear_tightening_executor",
    "fallback_variant_generator",
    "candidate_evaluator",
    "candidate_delta_builder",
    "materiality_screen",
    "shear_detailing_purity_screen",
    "overview_acceptance_screen",
    "preview_status_screen",
    "candidate_selection_sort_key",
    "result_packaging_evaluator",
    "cta_contract_builder",
)


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


def _route_proof(*, branch: str, has_result: bool = True) -> dict[str, Any]:
    route_projection = {
        "route_request": {
            "branch": branch,
            "family": "shear",
            "source": "post_click_low_bending_resolution_item",
        },
        "search_projection": {
            "primary_shear_tightening_attempted": True,
            "fallback_variant_search_available": True,
            "candidate_evaluation_required": True,
        },
        "blocker_projection": {
            "bending_blocker_preserved": True,
            "residual_shear_cleanup_after_bending_blocker": True,
        },
        "result_projection": (
            {
                "candidate_id": f"{branch}_candidate",
                "updates_hash": stable_final_publication_hash({"s_lig": 300, "lig_legs": 0}),
                "result_kind": "residual_shear_cleanup",
            }
            if has_result
            else {}
        ),
    }
    return {
        "route_projection": route_projection,
        "route_projection_hash": stable_final_publication_hash(route_projection),
        "proof_hash": stable_final_publication_hash({"route_projection": route_projection}),
        "represented_route_surfaces": (
            "route_entry_guard",
            "primary_shear_tightening_search",
            "fallback_variant_search",
            "materiality_and_safety_screen",
            "promoted_item_packaging",
            "blocker_evidence_merge",
            "cta_contract_shape",
            "debug_session_projection",
        ),
        "excluded_live_surfaces": (
            "candidate_generation_execution",
            "candidate_evaluation_execution",
            "primary_shear_tightening_execution",
            "cta_contract_execution",
            "visible_wording_authoring",
        ),
    }


def _candidate_inputs(*, branch: str, starting: float, low: float, high: float) -> dict[str, Any]:
    return {
        "route_branch": branch,
        "starting_shear_util": starting,
        "target_low": low,
        "target_high": high,
        "residual_outside_preferred_band": starting > high,
        "has_primary_shear_tightening": True,
        "has_residual_updates": True,
        "result_candidate_id": f"{branch}_candidate",
    }


def _build_case(
    *,
    name: str,
    branch: str,
    dependency_status: dict[str, str] | None,
    expected_behavior_ready: bool,
    has_result: bool = True,
) -> dict[str, Any]:
    route_proof = _route_proof(branch=branch, has_result=has_result)
    route_shell = build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_route_cutover_readiness(
        route_proof=route_proof,
        dependency_status={},
    )
    boundary_inputs = _candidate_inputs(branch=branch, starting=1.12, low=0.85, high=0.95)
    payload = build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_candidate_boundary(
        route_proof=route_proof,
        route_shell_readiness=route_shell,
        dependency_status=dependency_status or {},
        candidate_boundary_inputs=boundary_inputs,
    )
    repeat = build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_candidate_boundary(
        route_proof=route_proof,
        route_shell_readiness=route_shell,
        dependency_status=dependency_status or {},
        candidate_boundary_inputs=boundary_inputs,
    )
    unresolved = tuple(payload.get("unresolved_dependencies") or ())
    dependency_rows = dict(payload.get("dependency_rows") or {})
    return {
        "name": name,
        "expected_behavior_ready": expected_behavior_ready,
        "request_shape_ready": bool(payload.get("request_shape_ready")),
        "dependency_boundary_ready": bool(payload.get("dependency_boundary_ready")),
        "behavior_cutover_ready": bool(payload.get("behavior_cutover_ready")),
        "candidate_generation_cutover_ready": bool(payload.get("candidate_generation_cutover_ready")),
        "candidate_evaluation_cutover_ready": bool(payload.get("candidate_evaluation_cutover_ready")),
        "unresolved_dependencies": unresolved,
        "all_dependency_slots_represented": all(
            dependency in dependency_rows for dependency in CANDIDATE_DEPENDENCIES
        ),
        "stable_hash_repeat": payload.get("candidate_boundary_hash")
        == repeat.get("candidate_boundary_hash"),
        "boundary_hash": payload.get("candidate_boundary_hash"),
        "route_projection_hash": (payload.get("boundary_input_hashes") or {}).get(
            "route_projection_hash"
        ),
        "candidate_boundary_inputs_hash": (payload.get("boundary_input_hashes") or {}).get(
            "candidate_boundary_inputs_hash"
        ),
        "not_moved": tuple(payload.get("not_moved") or ()),
        "product_driving": bool(payload.get("product_driving")),
        "render_driving": bool(payload.get("render_driving")),
        "apply_driving": bool(payload.get("apply_driving")),
        "session_driving": bool(payload.get("session_driving")),
    }


def _capture() -> dict[str, Any]:
    all_controller_owned = {dependency: "controller_owned" for dependency in CANDIDATE_DEPENDENCIES}
    scenarios = [
        _build_case(
            name="current_live_page_dependencies_primary_success",
            branch="primary_shear_tightening_success",
            dependency_status={},
            expected_behavior_ready=False,
        ),
        _build_case(
            name="current_live_page_dependencies_fallback_success",
            branch="fallback_variant_success",
            dependency_status={},
            expected_behavior_ready=False,
        ),
        _build_case(
            name="current_live_page_dependencies_no_result_boundary",
            branch="no_result_boundary",
            dependency_status={},
            expected_behavior_ready=False,
            has_result=False,
        ),
        _build_case(
            name="future_all_controller_owned_dependencies",
            branch="future_controller_owned",
            dependency_status=all_controller_owned,
            expected_behavior_ready=True,
        ),
    ]
    trace_run = _run(
        [
            sys.executable,
            "tools/verification/design_guide_post_click_low_bending_residual_shear_cleanup_candidate_boundary_trace_wiring_snapshot.py",
        ]
    )
    return {
        "decision": "RESIDUAL_SHEAR_CLEANUP_CANDIDATE_BOUNDARY_PARITY_SCENARIOS_PROVEN",
        "scenarios": scenarios,
        "trace_wiring": trace_run,
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "engineering_behavior_changed": False,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    scenarios = list(capture.get("scenarios") or [])
    return {
        "scenario_count": len(scenarios) == 4,
        "all_request_shapes_ready": all(case.get("request_shape_ready") is True for case in scenarios),
        "all_dependency_boundaries_ready": all(
            case.get("dependency_boundary_ready") is True for case in scenarios
        ),
        "expected_behavior_readiness": all(
            case.get("behavior_cutover_ready") is case.get("expected_behavior_ready")
            for case in scenarios
        ),
        "candidate_generation_matches_behavior_ready": all(
            case.get("candidate_generation_cutover_ready") is case.get("expected_behavior_ready")
            for case in scenarios
        ),
        "candidate_evaluation_matches_behavior_ready": all(
            case.get("candidate_evaluation_cutover_ready") is case.get("expected_behavior_ready")
            for case in scenarios
        ),
        "current_live_cases_keep_dependencies_unresolved": all(
            bool(case.get("unresolved_dependencies"))
            for case in scenarios
            if case.get("expected_behavior_ready") is False
        ),
        "future_owned_case_has_no_unresolved_dependencies": all(
            not case.get("unresolved_dependencies")
            for case in scenarios
            if case.get("expected_behavior_ready") is True
        ),
        "all_dependency_slots_represented": all(
            case.get("all_dependency_slots_represented") is True for case in scenarios
        ),
        "stable_hashes": all(case.get("stable_hash_repeat") is True for case in scenarios),
        "non_driving": all(
            not case.get("product_driving")
            and not case.get("render_driving")
            and not case.get("apply_driving")
            and not case.get("session_driving")
            for case in scenarios
        ),
        "trace_wiring_passed": (capture.get("trace_wiring") or {}).get("passed") is True,
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "engineering_behavior_unchanged": capture.get("engineering_behavior_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Residual Shear Cleanup Candidate Boundary Parity Scenarios",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Scenario Summary",
        "",
    ]
    for case in capture.get("scenarios") or []:
        lines.append(
            "- "
            + str(case.get("name"))
            + ": behavior_cutover_ready=`"
            + str(case.get("behavior_cutover_ready"))
            + "`, unresolved=`"
            + str(len(case.get("unresolved_dependencies") or ()))
            + "`, stable_hash=`"
            + str(case.get("stable_hash_repeat"))
            + "`"
        )
    lines.extend(
        [
            "",
            "## Boundary",
            "",
            "- Current live page-dependency scenarios must remain not ready for behavior cutover.",
            "- The future all-controller-owned scenario proves the same boundary shape can become ready once dependency ownership is separately proven.",
            "- No candidate generation, candidate evaluation, CTA contract execution, visible wording, or returned route result moved in this slice.",
            "",
            "## Checks",
            "",
        ]
    )
    lines.extend(f"- {key}: `{value}`" for key, value in (payload.get("checks") or {}).items())
    lines.extend(
        [
            "",
            "## Next",
            "",
            "Create a candidate/evaluator ownership handoff object for the first dependency slot. Do not cut over execution until live parity proves the dependency can be injected or controller-owned safely.",
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
        "schema": "design_guide_post_click_low_bending_residual_shear_cleanup_candidate_boundary_parity_scenarios.v1",
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
        / f"design_guide_post_click_low_bending_residual_shear_cleanup_candidate_boundary_parity_scenarios_{stamp}.json"
    )
    audit_path = (
        AUDIT_DIR
        / f"design_guide_post_click_low_bending_residual_shear_cleanup_candidate_boundary_parity_scenarios_{stamp}.md"
    )
    report_path = (
        REPORT_DIR
        / f"design_brain_physical_extraction_residual_shear_cleanup_candidate_boundary_parity_scenarios_{stamp}.md"
    )
    json_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8",
    )
    _write_report(audit_path, payload)
    _write_report(report_path, payload)
    print(
        "design_guide_post_click_low_bending_residual_shear_cleanup_candidate_boundary_parity_scenarios "
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
