"""Audit remaining compute guidance core/wrapper Design Brain surfaces.

This is a focused inventory for the final zero-authority tail. It does not
execute product code and does not change behaviour.
"""

from __future__ import annotations

import ast
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
INPUTS_PAGE = ROOT / "inputs_page.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig", errors="replace")


def _function_segment(source: str, name: str) -> tuple[int, int, str]:
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            lines = source.splitlines()
            return node.lineno, int(node.end_lineno or node.lineno), "\n".join(
                lines[node.lineno - 1 : int(node.end_lineno or node.lineno)]
            )
    raise RuntimeError(f"Function not found: {name}")


def _contains(segment: str, *tokens: str) -> bool:
    return all(token in segment for token in tokens)


def build_payload() -> dict[str, Any]:
    source = _read(INPUTS_PAGE)
    core_start, core_end, core_segment = _function_segment(source, "_compute_design_guidance_items_core")
    wrapper_start, wrapper_end, wrapper_segment = _function_segment(source, "_compute_design_guidance_items")

    serviceability_block_present = _contains(
        wrapper_segment,
        "_primary_check_for_evidence in {\"crack\", \"deflection\"}",
        "_attempted_updates_for_evidence",
        "_serviceability_truth",
        "primary_item_for_evidence[\"display_truth\"]",
    )
    post_active_shear_block_present = _contains(
        core_segment,
        "post_active_repair_shear_cleanup_blocked",
        "blocker_item = _guidance_item(",
        "blocker_contract = {",
        "blocker_truth = {",
    )
    optimisation_selector_present = _contains(
        core_segment,
        "_select_primary_optimisation_candidate(",
        "primary_optimisation_selection_owner",
        "legacy_fallback",
    )
    auto_design_seed_present = _contains(
        wrapper_segment,
        'request_kind_norm == "auto_design"',
        "evaluate_candidate_full(gs, source=\"single_pass_auto_design_seed\")",
        "run_auto_design_solver(gs, results)",
    )
    late_evidence_lane_present = _contains(
        wrapper_segment,
        "late_evidence_lane_enter",
        "_prepare_compute_missing_candidate_search_evidence(",
        "_sync_compute_late_evidence_to_primary_item(",
    )
    cache_shell_present = _contains(
        wrapper_segment,
        "get_rerun_pure_cache(",
        "set_rerun_pure_cache(",
        "_design_guide_candidate_search_reuse_store(",
    )

    surfaces: list[dict[str, Any]] = [
        {
            "surface": "serviceability_crack_deflection_exact_blocker_materialization",
            "function": "_compute_design_guidance_items",
            "line_range": "75387-75481",
            "present": serviceability_block_present,
            "classification": "C_INPUTS_PAGE_STILL_OWNS_DESIGN_BRAIN_LOGIC",
            "target_owner": "DesignGuideController",
            "deletion_readiness": "READY_FOR_CONTROLLER_PROJECTION_CUTOVER",
            "risk": "MEDIUM",
            "first_safe_slice": (
                "Move the pure crack/deflection attempted-updates, blocker reason, evidence update, "
                "and display-truth projection into a controller helper. Keep page-owned row extraction "
                "and mutation application in inputs_page.py."
            ),
            "required_verifier": "design_guide_compute_serviceability_blocker_projection_extraction.py",
        },
        {
            "surface": "post_active_shear_cleanup_blocked_item_projection",
            "function": "_compute_design_guidance_items_core",
            "line_range": "69789-69942",
            "present": post_active_shear_block_present,
            "classification": "C_INPUTS_PAGE_STILL_OWNS_DESIGN_BRAIN_LOGIC",
            "target_owner": "DesignGuideController",
            "deletion_readiness": "NOT_READY_UNTIL_SERVICEABILITY_SLICE_DONE",
            "risk": "HIGH",
            "first_safe_slice": "Move blocker item/contract/truth projection after serviceability blocker projection.",
            "required_verifier": "design_guide_compute_post_active_shear_blocker_projection_extraction.py",
        },
        {
            "surface": "optimisation_selector_debug_and_legacy_fallback_packaging",
            "function": "_compute_design_guidance_items_core",
            "line_range": "71020-71117",
            "present": optimisation_selector_present,
            "classification": "MIXED_CONTROLLER_SELECTOR_WITH_PAGE_DEBUG_SHELL",
            "target_owner": "DesignGuideController plus page debug shell",
            "deletion_readiness": "NOT_READY",
            "risk": "MEDIUM",
            "first_safe_slice": "Audit selected-candidate fallback/debug packaging separately.",
            "required_verifier": "design_guide_compute_optimisation_selector_packaging_boundary_audit.py",
        },
        {
            "surface": "auto_design_seed_wrapper",
            "function": "_compute_design_guidance_items",
            "line_range": "75252-75270",
            "present": auto_design_seed_present,
            "classification": "PAGE_WRAPPER_EXECUTION_BOUNDARY",
            "target_owner": "candidate evaluation service and auto-design solver boundary",
            "deletion_readiness": "NOT_READY",
            "risk": "HIGH",
            "first_safe_slice": "Do not touch until candidate-evaluation execution boundary is explicitly moved.",
            "required_verifier": "design_guide_auto_design_seed_boundary_audit.py",
        },
        {
            "surface": "late_evidence_lane_orchestration",
            "function": "_compute_design_guidance_items",
            "line_range": "75286-75547",
            "present": late_evidence_lane_present,
            "classification": "MIXED_CONTROLLER_PROJECTIONS_WITH_PAGE_ORCHESTRATION",
            "target_owner": "FinalDesignGuidePublication/DesignGuideController plus page shell",
            "deletion_readiness": "PARTIAL_AFTER_SERVICEABILITY_SLICE",
            "risk": "HIGH",
            "first_safe_slice": "Peel off pure projection blocks one at a time, starting with serviceability blocker materialization.",
            "required_verifier": "design_guide_compute_serviceability_blocker_projection_extraction.py",
        },
        {
            "surface": "cache_trace_session_shell",
            "function": "_compute_design_guidance_items",
            "line_range": "74997-75151",
            "present": cache_shell_present,
            "classification": "APPROVED_PAGE_SESSION_CACHE_TRACE_SHELL",
            "target_owner": "inputs_page.py shell",
            "deletion_readiness": "SHELL_ONLY",
            "risk": "LOW",
            "first_safe_slice": "No extraction before compute output builder is fully controller-owned.",
            "required_verifier": "design_brain_inputs_page_zero_authority_inventory_lock.py",
        },
    ]

    remaining_page_logic = [s for s in surfaces if s["classification"].startswith("C_") and s["present"]]
    first_slice = (
        remaining_page_logic[0]["surface"]
        if remaining_page_logic
        else "optimisation_selector_debug_and_legacy_fallback_packaging"
    )
    status = "PARTIAL" if remaining_page_logic else "PASS"
    return {
        "schema": "design_guide_compute_guidance_core_tail_boundary_audit.v1",
        "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ"),
        "status": status,
        "decision": "NOT_ZERO_COMPUTE_TAIL_HAS_EXACT_FIRST_EXTRACTION_SLICE",
        "core_function": {
            "name": "_compute_design_guidance_items_core",
            "line_start": core_start,
            "line_end": core_end,
            "line_count": core_end - core_start + 1,
        },
        "wrapper_function": {
            "name": "_compute_design_guidance_items",
            "line_start": wrapper_start,
            "line_end": wrapper_end,
            "line_count": wrapper_end - wrapper_start + 1,
        },
        "surfaces": surfaces,
        "remaining_page_owned_design_brain_logic_count": len(remaining_page_logic),
        "first_safe_implementation_slice": first_slice,
        "stop_conditions": [
            "visible wording changes",
            "CTA/apply semantics change",
            "family runtime behaviour changes",
            "candidate evidence changes outside the targeted serviceability projection",
            "composed lock fails",
        ],
    }


def _write_report(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = str(payload["created_at"])
    json_path = ARTIFACT_DIR / f"design_guide_compute_guidance_core_tail_boundary_audit_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_compute_guidance_core_tail_boundary_audit_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

    rows = [
        "| Surface | Function | Classification | Target owner | Readiness | Risk |",
        "|---|---|---|---|---|---|",
    ]
    for surface in payload["surfaces"]:
        rows.append(
            "| {surface} | {function} {line_range} | {classification} | {target_owner} | {deletion_readiness} | {risk} |".format(
                **surface
            )
        )
    md = [
        "# Design Guide Compute Guidance Core Tail Boundary Audit",
        "",
        "## Executive Summary",
        f"{payload['status']} - {payload['decision']}",
        "",
        "## Current State",
        f"- `_compute_design_guidance_items_core`: {payload['core_function']['line_count']} lines",
        f"- `_compute_design_guidance_items`: {payload['wrapper_function']['line_count']} lines",
        f"- Remaining page-owned Design Brain logic surfaces: {payload['remaining_page_owned_design_brain_logic_count']}",
        "",
        "## Inventory",
        *rows,
        "",
        "## First Safe Implementation Slice",
        payload["first_safe_implementation_slice"],
        "",
        "Move only the pure serviceability crack/deflection exact-blocker projection into `DesignGuideController`. Keep page-owned row extraction, debug/session mutation, cache, trace, and render/apply plumbing in `inputs_page.py`.",
        "",
        "## Stop Conditions",
        *[f"- {condition}" for condition in payload["stop_conditions"]],
    ]
    md_path.write_text("\n".join(md) + "\n", encoding="utf-8")
    return json_path, md_path


def main() -> int:
    payload = build_payload()
    json_path, md_path = _write_report(payload)
    print(f"design_guide_compute_guidance_core_tail_boundary_audit {payload['status']}")
    print(f"decision={payload['decision']}")
    print(f"json={json_path}")
    print(f"report={md_path}")
    return 0 if payload["status"] in {"PASS", "PARTIAL"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
