"""Prove the retired broad Design Guide search engine is physically absent."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
OLD_MODULE = (
    ROOT
    / "inputs_page_modules"
    / "design_guide"
    / "direct_target_band_guidance.py"
)
GENERIC_BROAD_MODULE = (
    ROOT / "inputs_page_modules" / "one_click_candidate_solver.py"
)
SHEAR_FALLBACK_MODULE = (
    ROOT
    / "inputs_page_modules"
    / "design_guide"
    / "shear_fallback_candidate.py"
)
LEGACY_SHEAR_GENERATOR_MODULE = (
    ROOT
    / "inputs_page_modules"
    / "app_bridge"
    / "shear_candidate_generation.py"
)
SHEAR_ESCALATION_MODULE = (
    ROOT / "inputs_application" / "shear_escalation_runtime.py"
)
FAMILY_MODULE = (
    ROOT
    / "inputs_page_modules"
    / "design_guide"
    / "family_ladder_guidance.py"
)
LEGACY_ENGINE_WRAPPER = ROOT / "design_guidance_engine.py"
MODULE_CONTRACT_REGISTRY = (
    ROOT / "tools" / "verification" / "module_contract_registry.json"
)
CANDIDATE_EVALUATION_MODULE = ROOT / "design_brain" / "candidate_evaluation.py"
RETIRED_VERIFIERS = (
    "design_guide_direct_target_active_failure_executor_item_service_boundary_audit.py",
    "design_guide_direct_target_active_failure_executor_bridge_boundary_audit.py",
    "design_guide_direct_target_band_broad_search_boundary_audit.py",
    "design_guide_direct_target_band_candidate_evaluation_service_handoff.py",
    "design_guide_direct_target_band_candidate_generation_boundary.py",
    "design_guide_direct_target_broad_bottom_trial_packaging_boundary.py",
    "design_guide_direct_target_broad_geometry_plan_boundary.py",
    "design_guide_direct_target_broad_shear_option_generation_boundary.py",
    "design_guide_target_band_generator_ranking_projection_extraction_audit.py",
    "design_guide_active_failure_no_target_blocker_extraction.py",
    "design_guide_bending_cleanup_target_and_duplicate_cta_snapshot.py",
    "design_guide_candidate_action_type_extraction.py",
    "design_guide_direct_candidate_final_cleanup_sort_key_extraction.py",
    "design_guide_direct_target_active_failure_family_bypass_metadata_projection.py",
    "design_guide_direct_target_active_failure_route_adapter_cutover.py",
    "design_guide_direct_target_active_failure_route_adapter_cutover_readiness_audit.py",
    "design_guide_direct_target_active_failure_route_condition_policy_adapter.py",
    "design_guide_direct_target_active_failure_route_condition_policy_adapter_audit.py",
    "design_guide_direct_target_active_failure_route_execution_boundary_audit.py",
    "design_guide_direct_target_active_failure_route_request_result_adapter_audit.py",
    "design_guide_direct_target_active_failure_route_request_result_adapter_trace.py",
    "design_guide_direct_target_band_bounded_proof_blocker_extraction.py",
    "design_guide_direct_target_band_guidance_boundary_reaudit.py",
    "design_guide_direct_target_combined_family_bypass_evidence_projection.py",
    "design_guide_direct_target_evidence_context_projection_adapter.py",
    "design_guide_direct_target_evidence_item_projection_adapter_audit.py",
    "design_guide_direct_target_family_callback_execution_boundary_audit.py",
    "design_guide_direct_target_family_repair_bridge_route_policy_audit.py",
    "design_guide_direct_target_family_route_projection_metadata_extraction.py",
    "design_guide_direct_target_final_selection_policy_extraction.py",
    "design_guide_direct_target_guidance_item_projection_boundary_audit.py",
    "design_guide_direct_target_guidance_item_projection_parity_snapshot.py",
    "design_guide_direct_target_ladder_filter_extraction.py",
    "design_guide_direct_target_repair_bridge_debug_shell_boundary_audit.py",
    "design_guide_direct_target_selection_dependency_row_boundary_audit.py",
    "design_guide_direct_target_selection_dependency_row_extraction.py",
    "design_guide_strength_family_band_status_extraction.py",
    "inputs_page_active_failure_visible_truth_priority_branch_verifier.py",
    "inputs_page_direct_target_band_guidance_extraction.py",
    "inputs_page_final_active_repair_item_acquisition_verifier.py",
    "inputs_page_local_cleanup_promotion_extraction.py",
    "inputs_page_one_click_candidate_solver_extraction.py",
    "inputs_page_primary_optimisation_selector_extraction.py",
    "inputs_page_shear_recommendation_rank_key_extraction.py",
    "inputs_page_terminal_direct_cleanup_item_selection_verifier.py",
    "inputs_auto_design_progressive_runtime_owner.py",
    "inputs_candidate_actionability_runtime_owner.py",
    "inputs_efficiency_shear_policy_runtime_owner.py",
    "inputs_guidance_direct_owner_cutover.py",
    "inputs_guidance_policy_primitives_owner.py",
    "inputs_shear_generation_runtime_owner.py",
    "inputs_tightening_runtime_owner.py",
    "design_guide_active_fail_executor_family_ladder_dispatch_handoff.py",
)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def main() -> int:
    family_source = _read(FAMILY_MODULE) if FAMILY_MODULE.exists() else ""
    candidate_source = (
        _read(CANDIDATE_EVALUATION_MODULE)
        if CANDIDATE_EVALUATION_MODULE.exists()
        else ""
    )
    guidance_compute_source = _read(
        ROOT / "inputs_page_modules" / "guidance_compute.py"
    )
    production_paths = [
        ROOT / "inputs_page_modules" / "guidance_compute.py",
        ROOT / "inputs_application" / "page_runtime" / "__init__.py",
        ROOT / "inputs_page_modules" / "design_guide" / "current_coordinators.py",
        ROOT / "inputs_page_modules" / "design_guide" / "local_cleanup_promotion.py",
        ROOT / "inputs_page_modules" / "design_guide" / "primary_optimisation_selector.py",
        ROOT / "inputs_application" / "one_click_runtime_provider.py",
        ROOT / "inputs_application" / "shear_escalation_runtime.py",
    ]
    production_source = "\n".join(
        _read(path) for path in production_paths if path.exists()
    )
    render_source = _read(
        ROOT
        / "inputs_page_modules"
        / "design_guide"
        / "current_coordinators.py"
    )
    retired_runtime_symbols = (
        "DirectTargetBandGuidanceRuntime",
        "bind_direct_target_band_guidance_dependencies",
        "_direct_target_band_guidance_item",
        "inputs_page_modules.design_guide.direct_target_band_guidance",
        "OneClickCandidateSolverRuntime",
        "_ONE_CLICK_CANDIDATE_SOLVER_RUNTIME",
        "_solve_one_click_candidate",
        "inputs_page_modules.one_click_candidate_solver",
        "ShearFallbackCandidateRuntime",
        "_SHEAR_FALLBACK_CANDIDATE_RUNTIME",
        "_shear_governing_fallback_resolved_candidate",
        "shear_governing_fallback_resolved_candidate",
        "inputs_page_modules.design_guide.shear_fallback_candidate",
        "ShearCandidateGenerationRuntime",
        "_generate_shear_candidates",
        "bind_shear_candidate_generation_dependencies",
        "_legacy_shear_candidate_generation_runtime",
        "inputs_page_modules.app_bridge.shear_candidate_generation",
        "_LEGACY_COMPUTE_NAMES",
        "_recommendation_updates_for_envelope",
    )
    broad_search_tokens = (
        "width_values",
        "depth_values",
        "DESIGN_GUIDE_DIRECT_TARGET_MAX_EVALS",
        "max_evaluations = 600",
        "max_evaluations = 6000",
    )
    retired_candidate_helpers = (
        "build_direct_target_band_broad_bottom_trial_attempts",
        "build_direct_target_band_broad_geometry_plan",
        "build_direct_target_band_broad_shear_options",
        "build_direct_target_band_ladder_stage_update_attempts",
        "evaluate_direct_target_band_candidate_with_updates",
    )
    checks = {
        "retired_module_absent": not OLD_MODULE.exists(),
        "generic_broad_solver_module_absent": (
            not GENERIC_BROAD_MODULE.exists()
        ),
        "dead_shear_fallback_module_absent": (
            not SHEAR_FALLBACK_MODULE.exists()
        ),
        "legacy_broad_shear_generator_module_absent": (
            not LEGACY_SHEAR_GENERATOR_MODULE.exists()
        ),
        "minimal_shear_escalation_runtime_present": (
            SHEAR_ESCALATION_MODULE.exists()
            and "class ShearEscalationRuntime"
            in _read(SHEAR_ESCALATION_MODULE)
            and "def generate_escalated_shear_states"
            in _read(SHEAR_ESCALATION_MODULE)
            and "_generate_shear_candidates"
            not in _read(SHEAR_ESCALATION_MODULE)
        ),
        "legacy_engine_wrapper_absent": not LEGACY_ENGINE_WRAPPER.exists(),
        "legacy_engine_registry_reference_absent": (
            MODULE_CONTRACT_REGISTRY.exists()
            and "design_guidance_engine"
            not in _read(MODULE_CONTRACT_REGISTRY)
        ),
        "family_ladder_module_present": FAMILY_MODULE.exists(),
        "retired_runtime_symbols_absent_from_production": not any(
            token in production_source for token in retired_runtime_symbols
        ),
        "family_runtime_wired": (
            "FamilyLadderGuidanceRuntime" in production_source
            and "_family_ladder_guidance_item" in production_source
        ),
        "generic_broad_solver_call_absent": not any(
            token in guidance_compute_source
            for token in (
                "run_bounded_one_click_solver",
                "resolved_one_click_candidate",
                "one_click_solver_search",
                "legacy search breadth",
            )
        ),
        "overdesign_family_ladder_precedes_efficiency_selector": (
            guidance_compute_source.find(
                '"overdesign_family_ladder_first"'
            )
            >= 0
            and guidance_compute_source.find(
                '"overdesign_family_ladder_first"'
            )
            < guidance_compute_source.find(
                "efficiency_items = _efficiency_guidance_items"
            )
        ),
        "broad_grid_tokens_absent": not any(
            token in family_source for token in broad_search_tokens
        ),
        "render_owned_candidate_search_absent": not any(
            token in render_source
            for token in (
                "design_guide_render_shear_fail_bending_overdesign_width_merge",
                "mixed_render_merge_promoted",
                "if False and guidance_items",
            )
        ),
        "retired_render_search_dependencies_absent": not any(
            token in render_source
            for token in (
                "'_family_ladder_guidance_item'",
                "'_evaluate_auto_design_candidate'",
                "'_maybe_promote_safe_local_cleanup_primary'",
                "'_shear_tightening_as_local_cleanup_item'",
                "'legacy_item_from_decision'",
            )
        ),
        "inputs_post_family_redecision_absent": not any(
            token in production_source
            for token in (
                "legacy_item_from_decision",
                "resolve_design_guide_decision(",
                "from design_guidance_engine import",
            )
        ),
        "legacy_engine_decision_session_bridge_absent": not any(
            token in production_source
            for token in (
                "_design_guide_engine_decision",
                "design_guide_engine_decision",
            )
        ),
        "presentation_projects_authoritative_primary": (
            '"presentation_source": "authoritative_primary_item"'
            in _read(
                ROOT
                / "inputs_page_modules"
                / "design_guide"
                / "presentation_state.py"
            )
            and "resolve_design_guide_decision"
            not in _read(
                ROOT
                / "inputs_page_modules"
                / "design_guide"
                / "presentation_state.py"
            )
        ),
        "retired_candidate_helpers_absent": not any(
            token in candidate_source for token in retired_candidate_helpers
        ),
        "retired_compatibility_verifiers_absent": not any(
            (ROOT / "tools" / "verification" / name).exists()
            for name in RETIRED_VERIFIERS
        ),
        "family_dispatch_is_live": (
            "resolve_family_ladder_dispatch" in family_source
            and "family_strategy_for" in family_source
        ),
        "classified_exhaustion_is_fail_closed": (
            "family_ladder_exhausted" in family_source
            and '"legacy_fallback_allowed": False' in family_source
        ),
        "unlocked_underdesign_internal_exhaustion_is_not_publishable": (
            "unlocked_underdesign_ladder_failed_to_repair" in family_source
            and "family_ladder_exhaustion_not_publishable" in family_source
            and "and not geometry_locked" in family_source
            and "and not canonical_project_geometry_exhausted"
            in family_source
        ),
        "canonical_project_limit_exhaustion_is_publishable": (
            "canonical_project_geometry_exhausted" in family_source
            and "Project maximum beam depth and width reached at 5000 mm"
            in family_source
        ),
        "classified_exhaustion_cannot_be_overridden_by_local_cleanup": (
            'debug_trace.get("family_ladder_exhausted_without_legacy_fallback")'
            in guidance_compute_source
            and 'debug_trace.get("legacy_fallback_allowed") is False'
            in guidance_compute_source
            and "local_cleanup_promotion_suppressed_by_family_ladder"
            in guidance_compute_source
            and (
                'and not debug_trace.get(\n'
                '            "family_ladder_exhausted_without_legacy_fallback"'
            )
            in guidance_compute_source
        ),
        "pure_overdesign_exhaustion_keeps_family_flags": (
            '"BENDING_OVERDESIGN_GOVERNS"' in family_source
            and '"SHEAR_OVERDESIGN_GOVERNS"' in family_source
            and '"COMBINED_OVERDESIGN"' in family_source
            and 'if family_flags["bending_overdesigned"]' in family_source
            and 'if family_flags["shear_overdesigned"]' in family_source
        ),
    }
    payload = {
        "schema": "legacy_broad_search_deletion_contract.v1",
        "status": "PASS" if all(checks.values()) else "FAIL",
        "checks": checks,
        "retired_module": str(OLD_MODULE.relative_to(ROOT)),
        "replacement_module": str(FAMILY_MODULE.relative_to(ROOT)),
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
