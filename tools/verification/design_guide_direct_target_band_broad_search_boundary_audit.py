"""Audit remaining broad direct target-band search ownership before extraction."""

from __future__ import annotations

import ast
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

INPUTS_PAGE = ROOT / "inputs_page.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"

TARGET = "_direct_target_band_guidance_item"


SURFACES: list[dict[str, Any]] = [
    {
        "surface": "family-owned early active-failure bypass",
        "tokens": ["_active_fail_near_current_repair_item(", "generic_target_band_search_skipped"],
        "current_owner": "inputs_page route bridge calling family-owned repair",
        "target_owner": "DesignGuideController route policy plus family runtime",
        "classification": "unsafe to move in broad-search slice",
        "first_safe_slice": "separate active-failure route bridge audit",
    },
    {
        "surface": "diagnostic/session proof bookkeeping",
        "tokens": ["st.session_state", "_direct_target_band_diag_trace(", "_proof_active_key"],
        "current_owner": "inputs_page",
        "target_owner": "page shell non-authoritative diagnostics",
        "classification": "page/session guard allowed to remain",
        "first_safe_slice": "none until controller route owns all search output",
    },
    {
        "surface": "ladder stage update attempt generation",
        "tokens": ["_service_stage_updates(", "_build_direct_target_band_ladder_stage_update_attempts("],
        "current_owner": "design_brain.candidate_evaluation with page adapter",
        "target_owner": "candidate evaluation service",
        "classification": "already service-backed",
        "first_safe_slice": "none",
    },
    {
        "surface": "broad shear option generation",
        "tokens": ["shear_options: list[dict]", "_generate_escalated_shear_states(", "generate_less_shear_reo_variants("],
        "current_owner": "inputs_page",
        "target_owner": "candidate evaluation service with injected variant rows",
        "classification": "Design Brain candidate generation still page-owned",
        "first_safe_slice": "broad_search_shear_option_generation_service_boundary",
    },
    {
        "surface": "broad width/depth geometry loop",
        "tokens": ["for width in width_values", "for depth in depth_values", "_geometry_state_with_updates("],
        "current_owner": "inputs_page",
        "target_owner": "candidate evaluation service search-plan generator",
        "classification": "Design Brain search orchestration still page-owned",
        "first_safe_slice": "broad_search_geometry_plan_service_boundary",
    },
    {
        "surface": "broad bottom trial generation",
        "tokens": ["_enumerate_bottom_reo_design_trials(", "_generate_local_bottom_arrangements(", "trial_bottoms"],
        "current_owner": "inputs_page",
        "target_owner": "candidate evaluation service with page-injected arrangement rows",
        "classification": "callback-heavy generation not ready for blind move",
        "first_safe_slice": "prebuilt bottom trial packaging boundary",
    },
    {
        "surface": "broad candidate evaluation execution",
        "tokens": ["_evaluate_updates(", "_evaluate_direct_target_band_candidate_with_service("],
        "current_owner": "inputs_page shell loop plus candidate evaluation service",
        "target_owner": "candidate evaluation service/controller route once search plan parity exists",
        "classification": "evaluation execution still page-owned but service-backed",
        "first_safe_slice": "do not move before search plan parity",
    },
    {
        "surface": "safe/target/fallback ranking",
        "tokens": ["safe = [", "target = [", "selected = min(", "_direct_candidate_final_cleanup_key("],
        "current_owner": "inputs_page with controller sort-key helpers",
        "target_owner": "DesignGuideController selection policy",
        "classification": "Design Brain ranking still page-owned",
        "first_safe_slice": "direct_target_final_selection_policy_extraction",
    },
    {
        "surface": "evidence and item projection",
        "tokens": ["_build_candidate_search_evidence(", "_guidance_item_from_resolved_candidate(", "item[\"action_payload\"]"],
        "current_owner": "inputs_page",
        "target_owner": "FinalDesignGuidePublication/controller projection adapter",
        "classification": "publication projection still page-owned",
        "first_safe_slice": "do not move before selection policy extraction",
    },
]


def _timestamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig", errors="replace")


def _function_source(source: str, name: str) -> tuple[int, int, str]:
    tree = ast.parse(source)
    lines = source.splitlines()
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node.lineno, int(node.end_lineno or node.lineno), "\n".join(
                lines[node.lineno - 1 : int(node.end_lineno or node.lineno)]
            )
    return 0, 0, ""


def _line_numbers(segment: str, start_line: int, token: str) -> list[int]:
    return [start_line + idx for idx, line in enumerate(segment.splitlines()) if token in line]


def _capture() -> dict[str, Any]:
    source = _read(INPUTS_PAGE)
    start, end, segment = _function_source(source, TARGET)
    selected_tail = segment.split('selected = selection_result.get("selected_candidate")', 1)[-1]
    broad_shear_options_service_backed = (
        "_build_direct_target_band_broad_shear_options(raw_shear_options)" in segment
        and "dedup_shear" not in segment
        and "shear_options: list[dict] = [{}]" not in segment
    )
    broad_geometry_plan_service_backed = (
        "_build_direct_target_band_broad_geometry_plan(" in segment
        and "for geometry_row in geometry_plan:" in segment
        and "for width in width_values:" not in segment
        and "for depth in depth_values:" not in segment
    )
    broad_bottom_trial_packaging_service_backed = (
        "_build_direct_target_band_broad_bottom_trial_attempts(" in segment
        and "for trial in packaged_bottom_trials:" in segment
        and "trial_bottoms.insert(0," not in segment
        and "for trial in trial_bottoms[:24]:" not in segment
    )
    final_selection_policy_controller_owned = (
        "_select_design_guide_controller_direct_target_final_candidate(" in segment
        and "target_covering_all_current_low" not in segment
        and "active_accepted_band_candidates" not in segment
    )
    selection_dependency_row_controller_owned = (
        "_build_design_guide_controller_direct_target_selection_row(" in segment
        and '"final_cleanup_sort_key": _direct_candidate_final_cleanup_key(c)' not in segment
        and '"preferred_band_distance": _candidate_strength_family_band_distance(' not in segment
        and '"families_in_accepted_band": _candidate_strength_families_in_band(' not in segment
    )
    guidance_item_projection_controller_owned = (
        "_build_design_guide_controller_direct_target_guidance_item_projection(" in selected_tail
        and 'item["action_payload"] = payload' not in selected_tail
        and 'item["resolved_candidate"] = resolved' not in selected_tail
    )
    surfaces: list[dict[str, Any]] = []
    for surface in SURFACES:
        token_rows = []
        for token in list(surface.get("tokens") or []):
            lines = _line_numbers(segment, start, str(token))
            token_rows.append(
                {
                    "token": token,
                    "present": bool(lines),
                    "lines": lines[:20],
                    "count": segment.count(str(token)),
                }
            )
        present_count = sum(1 for row in token_rows if row.get("present"))
        row = {
            **surface,
            "tokens_found": token_rows,
            "present": present_count > 0,
            "present_count": present_count,
        }
        if row.get("surface") == "broad shear option generation" and broad_shear_options_service_backed:
            row.update(
                {
                    "current_owner": "design_brain.candidate_evaluation with page-injected variant rows",
                    "target_owner": "candidate evaluation service",
                    "classification": "already service-backed",
                    "first_safe_slice": "none",
                }
            )
        if row.get("surface") == "broad width/depth geometry loop" and broad_geometry_plan_service_backed:
            row.update(
                {
                    "current_owner": "design_brain.candidate_evaluation plan rows plus page geometry mutation",
                    "target_owner": "candidate evaluation service search-plan generator",
                    "classification": "plan service-backed; geometry mutation remains page-owned",
                    "first_safe_slice": "prebuilt bottom trial packaging boundary",
                }
            )
        if row.get("surface") == "broad bottom trial generation" and broad_bottom_trial_packaging_service_backed:
            row.update(
                {
                    "current_owner": "design_brain.candidate_evaluation packaging plus page-injected bottom trial rows",
                    "target_owner": "candidate evaluation service with page-injected arrangement rows",
                    "classification": "packaging service-backed; arrangement generation remains page-owned",
                    "first_safe_slice": "direct target selection policy extraction",
                }
            )
        if row.get("surface") == "safe/target/fallback ranking" and final_selection_policy_controller_owned:
            row.update(
                {
                    "current_owner": "DesignGuideController final selection policy plus page dependency rows",
                    "target_owner": "DesignGuideController selection policy",
                    "classification": "selection policy controller-owned; dependency rows remain page-owned",
                    "first_safe_slice": "selection dependency row extraction",
                }
            )
            if selection_dependency_row_controller_owned:
                row.update(
                    {
                        "current_owner": "DesignGuideController final selection policy and dependency row builder",
                        "target_owner": "DesignGuideController selection policy",
                        "classification": "selection policy and dependency rows controller-owned",
                        "first_safe_slice": "evidence/item projection adapter audit",
                    }
                )
        if row.get("surface") == "evidence and item projection" and guidance_item_projection_controller_owned:
            row.update(
                {
                    "current_owner": "DesignGuideController projection adapter with page shell debug/repair bridge",
                    "target_owner": "DesignGuideController projection adapter",
                    "classification": "projection adapter controller-owned; debug and repair bridge remain bounded page shell",
                    "first_safe_slice": "direct_target_repair_bridge_and_debug_shell_boundary_audit",
                }
            )
        surfaces.append(row)

    remaining_page_owned = [
        row
        for row in surfaces
        if row.get("present")
        and str(row.get("classification") or "") in {
            "Design Brain candidate generation still page-owned",
            "Design Brain search orchestration still page-owned",
            "Design Brain ranking still page-owned",
            "publication projection still page-owned",
            "callback-heavy generation not ready for blind move",
        }
    ]
    if (
        broad_shear_options_service_backed
        and broad_geometry_plan_service_backed
        and broad_bottom_trial_packaging_service_backed
        and final_selection_policy_controller_owned
        and selection_dependency_row_controller_owned
        and guidance_item_projection_controller_owned
    ):
        next_slice = {
            "name": "direct_target_repair_bridge_and_debug_shell_boundary_audit",
            "why": (
                "Direct target candidate generation packaging, selection policy, dependency rows, evidence context, "
                "guidance projection, and payload evidence mirrors are controller/service-backed. The remaining "
                "visible direct-target tail is page-shell repair bridge and non-authoritative debug diagnostics."
            ),
            "move": (
                "Audit the repair bridge/debug shell boundary before any move. Keep family repair decision, "
                "debug/session diagnostics, CTA/apply routing, and visible wording unchanged."
            ),
            "required_verifier": "design_guide_direct_target_repair_bridge_debug_shell_boundary_audit.py",
        }
    elif (
        broad_shear_options_service_backed
        and broad_geometry_plan_service_backed
        and broad_bottom_trial_packaging_service_backed
        and final_selection_policy_controller_owned
        and selection_dependency_row_controller_owned
    ):
        next_slice = {
            "name": "direct_target_evidence_item_projection_adapter_audit",
            "why": (
                "Direct target final selection policy and dependency row construction are now controller-owned. The "
                "remaining Design Brain-owned surface in the direct-target helper is evidence/item projection, with "
                "debug/session diagnostics and evaluation execution still bounded as page shell/service-backed."
            ),
            "move": (
                "Audit the evidence/item projection boundary before moving it. Keep candidate evaluation execution, "
                "debug/session diagnostics, CTA/apply payload, and wording unchanged."
            ),
            "required_verifier": "design_guide_direct_target_evidence_item_projection_adapter_audit.py",
        }
    elif (
        broad_shear_options_service_backed
        and broad_geometry_plan_service_backed
        and broad_bottom_trial_packaging_service_backed
        and final_selection_policy_controller_owned
    ):
        next_slice = {
            "name": "direct_target_selection_dependency_row_extraction_or_evidence_projection_audit",
            "why": (
                "Direct target final selection policy is now controller-owned. The remaining surfaces are dependency "
                "row construction, evidence/item projection, debug/session diagnostics, and evaluation execution."
            ),
            "move": (
                "Audit whether selection dependency row construction can move without pulling page-only after-state, "
                "material-family, or geometry-lock helpers into the controller. Otherwise target evidence projection "
                "with a proof-only adapter first."
            ),
            "required_verifier": "design_guide_direct_target_selection_dependency_row_boundary_audit.py",
        }
    elif (
        broad_shear_options_service_backed
        and broad_geometry_plan_service_backed
        and broad_bottom_trial_packaging_service_backed
    ):
        next_slice = {
            "name": "direct_target_final_selection_policy_extraction",
            "why": (
                "The narrower broad-search generation/package surfaces are now service-backed. The remaining high-value "
                "Design Brain-owned surface is final safe/target/fallback ranking and selected-candidate policy."
            ),
            "move": (
                "Move only pure final candidate selection policy into DesignGuideController. Keep candidate evaluation "
                "execution, evidence construction, item projection, debug/session diagnostics, CTA/apply payload, and "
                "wording unchanged."
            ),
            "required_verifier": "design_guide_direct_target_final_selection_policy_extraction.py",
        }
    elif broad_shear_options_service_backed and broad_geometry_plan_service_backed:
        next_slice = {
            "name": "prebuilt_bottom_trial_packaging_boundary",
            "why": (
                "Broad shear option packaging and width/depth plan construction are now service-backed. The next "
                "remaining generation surface is bottom-trial packaging, while callback-heavy arrangement generation "
                "must stay page-owned until separately injected."
            ),
            "move": (
                "Move only prebuilt broad bottom trial normalization/limit insertion into candidate_evaluation. Keep "
                "bottom arrangement generators, geometry state mutation, candidate evaluation, ranking, evidence, "
                "projection, debug/session diagnostics, CTA/apply payload, and wording unchanged."
            ),
            "required_verifier": "design_guide_direct_target_broad_bottom_trial_packaging_boundary.py",
        }
    elif broad_shear_options_service_backed:
        next_slice = {
            "name": "broad_search_geometry_plan_service_boundary",
            "why": (
                "Broad shear option packaging is now service-backed. The next remaining generation surface is the "
                "plain width/depth geometry search plan before callback-heavy bottom-trial generation."
            ),
            "move": (
                "Move only the broad direct-target width/depth geometry plan construction into candidate_evaluation. "
                "Keep geometry state mutation, bottom trial generation, candidate evaluation, ranking, evidence, "
                "projection, debug/session diagnostics, CTA/apply payload, and wording unchanged."
            ),
            "required_verifier": "design_guide_direct_target_broad_geometry_plan_boundary.py",
        }
    else:
        next_slice = {
            "name": "broad_search_shear_option_generation_service_boundary",
            "why": (
                "The shear option block is narrower than the full width/depth/bottom nested search and can be moved as "
                "plain option packaging while keeping variant generation callbacks and evaluation execution page-owned."
            ),
            "move": (
                "Move only broad direct-target shear option dedupe/packaging into candidate_evaluation. Keep the actual "
                "variant generators, geometry loops, bottom trials, candidate evaluation, ranking, evidence, projection, "
                "debug/session diagnostics, CTA/apply payload, and wording unchanged."
            ),
            "required_verifier": "design_guide_direct_target_broad_shear_option_generation_boundary.py",
        }
    return {
        "schema": "design_guide_direct_target_band_broad_search_boundary_audit.v1",
        "target": {
            "name": TARGET,
            "line_start": start,
            "line_end": end,
            "line_count": max(0, end - start + 1),
        },
        "surfaces": surfaces,
        "remaining_page_owned_surface_count": len(remaining_page_owned),
        "remaining_page_owned_surfaces": [row.get("surface") for row in remaining_page_owned],
        "broad_shear_options_service_backed": bool(broad_shear_options_service_backed),
        "broad_geometry_plan_service_backed": bool(broad_geometry_plan_service_backed),
        "broad_bottom_trial_packaging_service_backed": bool(broad_bottom_trial_packaging_service_backed),
        "final_selection_policy_controller_owned": bool(final_selection_policy_controller_owned),
        "selection_dependency_row_controller_owned": bool(selection_dependency_row_controller_owned),
        "guidance_item_projection_controller_owned": bool(guidance_item_projection_controller_owned),
        "decision": "PARTIAL_EXTRACTION_READY",
        "first_safe_slice": next_slice,
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtime_changed": False,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    surfaces = list(capture.get("surfaces") or [])
    by_name = {str(row.get("surface")): row for row in surfaces}
    return {
        "target_found": bool((capture.get("target") or {}).get("line_start")),
        "ladder_generation_already_service_backed": bool(by_name.get("ladder stage update attempt generation", {}).get("present")),
        "remaining_page_owned_surfaces_identified_or_zero_locked": (
            int(capture.get("remaining_page_owned_surface_count") or 0) > 0
            or bool(capture.get("guidance_item_projection_controller_owned"))
        ),
        "first_safe_slice_identified": bool((capture.get("first_safe_slice") or {}).get("name")),
        "no_product_behavior_change": not bool(capture.get("product_behavior_changed")),
        "visible_wording_unchanged": not bool(capture.get("visible_wording_changed")),
        "cta_apply_semantics_unchanged": not bool(capture.get("cta_apply_semantics_changed")),
        "family_runtime_unchanged": not bool(capture.get("family_runtime_changed")),
    }


def _write(payload: dict[str, Any], checks: dict[str, bool]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    suffix = _timestamp().replace(":", "-")
    json_path = ARTIFACT_DIR / f"design_guide_direct_target_band_broad_search_boundary_audit_{suffix}.json"
    report_path = AUDIT_DIR / f"design_guide_direct_target_band_broad_search_boundary_audit_{suffix}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Design Guide Direct Target-Band Broad Search Boundary Audit",
        "",
        f"Status: {payload['status']}",
        f"Decision: {payload.get('decision')}",
        "",
        "## Remaining Page-Owned Surfaces",
        *[f"- {name}" for name in payload.get("remaining_page_owned_surfaces") or []],
        "",
        "## Surface Inventory",
    ]
    for row in payload.get("surfaces") or []:
        lines.append(
            f"- {row.get('surface')}: {row.get('classification')} -> {row.get('target_owner')}"
        )
    lines.extend(
        [
            "",
            "## First Safe Slice",
            f"- Name: `{(payload.get('first_safe_slice') or {}).get('name')}`",
            f"- Why: {(payload.get('first_safe_slice') or {}).get('why')}",
            f"- Move: {(payload.get('first_safe_slice') or {}).get('move')}",
            f"- Verifier: `{(payload.get('first_safe_slice') or {}).get('required_verifier')}`",
            "",
            "## Checks",
            *[f"- {name}: {'PASS' if passed else 'FAIL'}" for name, passed in checks.items()],
        ]
    )
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, report_path


def main() -> int:
    capture = _capture()
    checks = _checks(capture)
    status = "PASS" if all(checks.values()) else "FAIL"
    payload = {
        **capture,
        "status": status,
        "checks": checks,
        "checked_at": _timestamp(),
    }
    json_path, report_path = _write(payload, checks)
    print(f"design_guide_direct_target_band_broad_search_boundary_audit {status}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
