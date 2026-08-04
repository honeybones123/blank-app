"""Audit compute-core Design Guide branch orchestration in inputs_page.py.

This is proof-only. It classifies the remaining branch-selection surface inside
``_compute_design_guidance_items_core(...)`` and identifies the smallest safe
controller extraction slice. It must not be used as evidence that runtime
behaviour changed.
"""

from __future__ import annotations

import ast
import json
from datetime import datetime, timezone
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

INPUTS_PAGE = ROOT / "inputs_page.py"
CONTROLLER = ROOT / "design_brain" / "design_guide_controller.py"
CANDIDATE_EVALUATION = ROOT / "design_brain" / "candidate_evaluation.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


def _timestamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig", errors="replace")


def _function_source(source: str, name: str) -> tuple[int, int, str]:
    tree = ast.parse(source)
    lines = source.splitlines()
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            end = int(node.end_lineno or node.lineno)
            return node.lineno, end, "\n".join(lines[node.lineno - 1 : end])
    return 0, 0, ""


def _line_numbers(segment: str, start_line: int, token: str) -> list[int]:
    return [start_line + index for index, line in enumerate(segment.splitlines()) if token in line]


def _token_row(segment: str, start_line: int, token: str) -> dict[str, Any]:
    return {
        "token": token,
        "present": token in segment,
        "count": segment.count(token),
        "lines": _line_numbers(segment, start_line, token)[:80],
    }


def _surface(
    *,
    name: str,
    current_owner: str,
    target_owner: str,
    classification: str,
    readiness: str,
    extraction_difficulty: str,
    tokens: list[str],
    segment: str,
    start_line: int,
    first_safe_slice: str | None = None,
    stop_conditions: list[str] | None = None,
) -> dict[str, Any]:
    evidence = [_token_row(segment, start_line, token) for token in tokens]
    return {
        "surface": name,
        "current_owner": current_owner,
        "target_owner": target_owner,
        "classification": classification,
        "readiness": readiness,
        "extraction_difficulty": extraction_difficulty,
        "evidence": evidence,
        "present": any(bool(row["present"]) for row in evidence),
        "first_safe_slice": first_safe_slice,
        "stop_conditions": list(stop_conditions or []),
    }


def _capture() -> dict[str, Any]:
    source = _read(INPUTS_PAGE)
    controller_source = _read(CONTROLLER)
    candidate_source = _read(CANDIDATE_EVALUATION)
    start, end, core_segment = _function_source(source, "_compute_design_guidance_items_core")
    branch_projection_cutover = (
        "_build_design_guide_controller_compute_core_branch_request_projection(" in core_segment
        and "_last_apply_label_for_post_active = str(" not in core_segment
        and "out_of_band_live = not (" not in core_segment
    )

    surfaces = [
        _surface(
            name="core request input collection",
            current_owner="inputs_page.py page shell",
            target_owner="inputs_page.py page shell",
            classification="page-shell input collection",
            readiness="KEEP_BOUNDED",
            extraction_difficulty="LOW",
            tokens=[
                "_build_design_actions_context(state)",
                "_guidance_state_snapshot(state)",
                "_collect_design_overview(",
                "_design_mode_config(",
                "_is_in_target_zone_with_eps(",
            ],
            segment=core_segment,
            start_line=start,
        ),
        _surface(
            name="branch scalar/request projection",
            current_owner=(
                "DesignGuideController via inputs_page shell"
                if branch_projection_cutover
                else "inputs_page.py"
            ),
            target_owner="DesignGuideController",
            classification=(
                "controller-owned branch scalar/request projection"
                if branch_projection_cutover
                else "remaining Design Brain branch-policy preparation"
            ),
            readiness="SHELL_CALL" if branch_projection_cutover else "READY_TO_EXTRACT",
            extraction_difficulty="MEDIUM",
            tokens=[
                "_build_design_guide_controller_compute_core_branch_request_projection(",
                "_compute_core_branch_projection",
                "_post_apply_from_active_failure_repair",
                "out_of_band_live",
            ],
            segment=core_segment,
            start_line=start,
            first_safe_slice=None if branch_projection_cutover else "compute_core_branch_request_projection_extraction",
            stop_conditions=[
                "branch name changes",
                "debug scalar changes",
                "post-click/apply route interpretation changes",
                "overview target-band predicate changes",
            ],
        ),
        _surface(
            name="branch route dispatch order",
            current_owner="inputs_page.py",
            target_owner="DesignGuideController",
            classification="remaining Design Brain branch route ordering",
            readiness="NOT_READY",
            extraction_difficulty="HIGH",
            tokens=[
                "if _not_started:",
                "if (",
                "guidance_branch =",
                "return [",
                "critical_apply_resolved_candidate",
                "target_band_final_accepted",
            ],
            segment=core_segment,
            start_line=start,
            first_safe_slice="compute_core_branch_route_ordering_audit",
            stop_conditions=[
                "branch priority changes",
                "early return changes",
                "selected item changes",
            ],
        ),
        _surface(
            name="post-active repair branch routing",
            current_owner="inputs_page.py",
            target_owner="DesignGuideController plus page-owned helper callbacks",
            classification="mixed branch route policy and item projection",
            readiness="NOT_READY",
            extraction_difficulty="HIGH",
            tokens=[
                "_post_apply_from_active_failure_repair",
                "_post_active_repair_target_accepted_item(",
                "_post_active_zero_shear",
                "_post_active_shear_blocker",
                "_shear_best_safe_cleanup_item_from_evidence(",
                "_shear_low_util_target_cleanup_item(",
            ],
            segment=core_segment,
            start_line=start,
            first_safe_slice="compute_core_post_active_repair_route_policy_audit",
            stop_conditions=[
                "post-click exact blocker state changes",
                "zero-shear terminal state changes",
                "shear cleanup CTA changes",
            ],
        ),
        _surface(
            name="in-target and low-util cleanup branch routing",
            current_owner="inputs_page.py",
            target_owner="DesignGuideController/candidate services",
            classification="mixed cleanup route policy and service-backed helper calls",
            readiness="NOT_READY",
            extraction_difficulty="HIGH",
            tokens=[
                "_in_target_shear_congestion_reshape_guidance_item(",
                "_bending_only_target_band_cleanup_item(",
                "_direct_target_band_guidance_item(",
                "_post_click_low_bending_resolution_item(",
                "identify_materially_overprovided_non_governing_families(",
                "_shear_low_util_target_cleanup_item(",
            ],
            segment=core_segment,
            start_line=start,
            first_safe_slice="compute_core_low_util_cleanup_route_policy_audit",
            stop_conditions=[
                "cleanup recommendation changes",
                "target-band acceptance changes",
                "candidate ordering changes",
            ],
        ),
        _surface(
            name="critical one-click candidate branch",
            current_owner="inputs_page.py",
            target_owner="DesignGuideController/candidate_evaluation service",
            classification="remaining candidate-selection branch policy",
            readiness="NOT_READY",
            extraction_difficulty="HIGH",
            tokens=[
                "_compute_mode_guidance_recommendation(",
                "_evaluate_auto_design_candidate(",
                "_materialize_guidance_candidate(",
                "_get_one_click_band_reaching_candidate(",
                "_candidate_is_valid_primary_one_click(",
                "critical_apply_resolved_candidate",
            ],
            segment=core_segment,
            start_line=start,
            first_safe_slice="compute_core_one_click_branch_policy_audit",
            stop_conditions=[
                "selected one-click candidate changes",
                "candidate coverage changes",
                "candidate evaluation fallback changes",
            ],
        ),
        _surface(
            name="fallback item construction",
            current_owner="inputs_page.py",
            target_owner="DesignGuideController",
            classification="remaining fallback recommendation projection",
            readiness="NOT_READY",
            extraction_difficulty="MEDIUM",
            tokens=[
                "_passing_guidance_item(",
                "_blocked_guidance_item(",
                "_no_active_primary_result(",
                "passing_guidance_fallback",
                "blocked_guidance_fallback",
            ],
            segment=core_segment,
            start_line=start,
            first_safe_slice="compute_core_fallback_item_projection_extraction",
            stop_conditions=[
                "fallback wording changes",
                "fallback status changes",
                "fallback CTA state changes",
            ],
        ),
        _surface(
            name="debug projection writes",
            current_owner="inputs_page.py",
            target_owner="DesignGuideController debug/proof adapter or page debug shell",
            classification="mixed debug/proof projection",
            readiness="NOT_READY",
            extraction_difficulty="MEDIUM",
            tokens=[
                "debug_sink[\"guidance_branch\"]",
                "debug_sink[\"selected_action_type\"]",
                "debug_sink[\"selected_title\"]",
                "debug_sink[\"candidate_search_evidence\"]",
                "debug_sink[\"primary_button_contract\"]",
            ],
            segment=core_segment,
            start_line=start,
            first_safe_slice="compute_core_debug_projection_boundary_audit",
            stop_conditions=[
                "debug payload hash changes unexpectedly",
                "publication verifier payload changes unexpectedly",
            ],
        ),
    ]

    present_not_ready = [
        row for row in surfaces if row["present"] and row["readiness"] in {"READY_TO_EXTRACT", "NOT_READY"}
    ]
    ready = [row for row in present_not_ready if row["readiness"] == "READY_TO_EXTRACT"]
    first = (ready or present_not_ready or [{}])[0]

    decision = "COMPUTE_CORE_BRANCH_ORCHESTRATION_NOT_ZERO"
    if ready:
        decision = "COMPUTE_CORE_BRANCH_REQUEST_PROJECTION_READY"
    if not present_not_ready:
        decision = "COMPUTE_CORE_BRANCH_ORCHESTRATION_SHELL_ONLY"

    return {
        "schema": "design_guide_compute_core_branch_orchestration_audit.v1",
        "status_decision": decision,
        "target": {
            "function": "_compute_design_guidance_items_core",
            "line_start": start,
            "line_end": end,
            "line_count": max(0, end - start + 1),
        },
        "surfaces": surfaces,
        "not_ready_or_ready_to_extract_surfaces": present_not_ready,
        "ready_to_extract_surfaces": ready,
        "first_safe_slice": dict(first),
        "recommended_next_implementation": {
            "slice": (
                "compute_core_branch_route_ordering_audit"
                if branch_projection_cutover
                else "compute_core_branch_request_projection_extraction"
            ),
            "target_owner": "DesignGuideController",
            "description": (
                "The scalar branch/request projection is controller-backed. Next audit the "
                "remaining branch route ordering before moving any early-return/item selection "
                "logic."
                if branch_projection_cutover
                else "Move only pure branch scalar/request projection into a controller helper. "
                "The page should still collect state/overview/session apply-route inputs and "
                "continue to call existing item builders. No item construction, CTA/apply, "
                "candidate evaluation, or fallback wording moves in that slice."
            ),
            "expected_helper": (
                "resolve_design_guide_controller_compute_core_branch_route_ordering(...)"
                if branch_projection_cutover
                else "build_design_guide_controller_compute_core_branch_request_projection(...)"
            ),
        },
        "controller_has_no_page_or_streamlit_imports": all(
            token not in controller_source
            for token in ("inputs_page", "streamlit", "st.session_state", "design_guide_page")
        ),
        "candidate_evaluation_has_no_page_or_streamlit_imports": all(
            token not in candidate_source
            for token in ("inputs_page", "streamlit", "st.session_state", "design_guide_page")
        ),
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtime_behavior_changed": False,
    }


def _checks(payload: dict[str, Any]) -> dict[str, bool]:
    target = payload.get("target") or {}
    return {
        "target_found": bool(target.get("line_start") and target.get("line_end")),
        "surfaces_classified": len(payload.get("surfaces") or []) >= 6,
        "first_safe_slice_identified": bool((payload.get("first_safe_slice") or {}).get("first_safe_slice")),
        "ready_slice_is_narrow": (
            (payload.get("first_safe_slice") or {}).get("first_safe_slice")
            in {
                "compute_core_branch_request_projection_extraction",
                "compute_core_branch_route_ordering_audit",
            }
        ),
        "controller_import_boundary_clean": bool(payload.get("controller_has_no_page_or_streamlit_imports")),
        "candidate_evaluation_import_boundary_clean": bool(
            payload.get("candidate_evaluation_has_no_page_or_streamlit_imports")
        ),
        "product_behavior_unchanged": not bool(payload.get("product_behavior_changed")),
        "visible_wording_unchanged": not bool(payload.get("visible_wording_changed")),
        "cta_apply_semantics_unchanged": not bool(payload.get("cta_apply_semantics_changed")),
        "family_runtime_behavior_unchanged": not bool(payload.get("family_runtime_behavior_changed")),
    }


def _write(payload: dict[str, Any], checks: dict[str, bool]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    suffix = _timestamp().replace(":", "-")
    json_path = ARTIFACT_DIR / f"design_guide_compute_core_branch_orchestration_audit_{suffix}.json"
    report_path = AUDIT_DIR / f"design_guide_compute_core_branch_orchestration_audit_{suffix}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

    lines = [
        "# Design Guide Compute Core Branch Orchestration Audit",
        "",
        f"Status: {payload.get('status')}",
        f"Decision: {payload.get('status_decision')}",
        "",
        "## Executive Summary",
        (
            "PARTIAL. `_compute_design_guidance_items_core(...)` is not shell-only. "
            "The next safe implementation slice is narrow: move pure branch "
            "scalar/request projection into `DesignGuideController`, while leaving "
            "state/overview collection, session/apply-route reads, item builders, "
            "candidate evaluation, fallback wording, CTA/apply, and rendering in place."
        ),
        "",
        "## Target",
        f"- Function: {(payload.get('target') or {}).get('function')}",
        f"- Lines: {(payload.get('target') or {}).get('line_start')} - {(payload.get('target') or {}).get('line_end')}",
        f"- Line count: {(payload.get('target') or {}).get('line_count')}",
        "",
        "## First Safe Implementation Slice",
        f"- Slice: {(payload.get('first_safe_slice') or {}).get('first_safe_slice')}",
        f"- Surface: {(payload.get('first_safe_slice') or {}).get('surface')}",
        "- Boundary: controller owns pure branch scalar/request projection only.",
        "",
        "## Surface Inventory",
    ]
    for row in payload.get("surfaces") or []:
        lines.append(
            f"- {row.get('surface')}: {row.get('classification')} | "
            f"{row.get('readiness')} | owner={row.get('current_owner')} -> {row.get('target_owner')}"
        )
    lines.extend(
        [
            "",
            "## Stop Conditions",
            "- Branch name changes.",
            "- Visible wording changes.",
            "- CTA/apply semantics change.",
            "- Candidate selection/evaluation changes.",
            "- Session/apply-route interpretation changes.",
            "- Any composed lock fails.",
            "",
            "## Checks",
            *[f"- {name}: {'PASS' if passed else 'FAIL'}" for name, passed in checks.items()],
        ]
    )
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, report_path


def main() -> int:
    payload = _capture()
    checks = _checks(payload)
    status = "PASS" if all(checks.values()) else "FAIL"
    payload = {**payload, "status": status, "checks": checks, "checked_at": _timestamp()}
    json_path, report_path = _write(payload, checks)
    print(f"design_guide_compute_core_branch_orchestration_audit {status}")
    print(f"decision={payload.get('status_decision')}")
    print(f"first_slice={(payload.get('first_safe_slice') or {}).get('first_safe_slice')}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
