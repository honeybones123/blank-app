"""Adapter from the application port to the current Design Brain runtime."""

from __future__ import annotations

from typing import Callable, Mapping

from application.design_brain_port import DesignBrainExecution, DesignBrainRequest
from inputs_application.design_brain_pipeline_runtime import (
    run_live_design_brain_pipeline,
)
from design_brain.candidate_evaluation import (
    build_full_candidate_evaluation_result_projection,
    build_target_band_fallback_scored_candidate,
    diff_candidate_state_updates,
    resolve_auto_design_band_reacher_delta_metrics,
    resolve_auto_design_band_reaching_candidate_goal_score,
    resolve_auto_design_candidate_objective_util,
    resolve_auto_design_candidate_target_band_metrics,
    resolve_auto_design_candidate_violation_score,
    resolve_auto_design_shallower_beam_metrics,
    resolve_auto_design_shallower_beam_selection_key,
    resolve_auto_design_shear_candidate_practicality_metrics,
    resolve_candidate_bending_demand_util,
    resolve_candidate_domain_max_distance,
    resolve_candidate_domain_score,
    resolve_candidate_domain_total_distance,
    resolve_candidate_in_target_band,
    resolve_candidate_required_domain_progress,
    resolve_candidate_required_domains_satisfied,
    resolve_candidate_step_improves,
    project_active_fail_executor_evaluated_candidate_result,
    resolve_active_fail_executor_candidate_eval_source,
    resolve_target_band_candidate_domains_for_updates,
    resolve_target_band_candidate_sort_key,
    resolve_target_band_exhaustion_refinement_allowed,
    resolve_target_band_next_hop_precheck,
    resolve_target_band_selected_candidate_acceptance,
    select_best_target_band_refinement_candidate,
    select_target_band_ranked_candidate,
)
from design_brain.families.bending import (
    build_bottom_reo_arrangement_pool_from_state,
    build_bottom_reo_evaluated_candidate_filter_boundary,
    build_bottom_reo_evaluated_candidate_filter_record,
    build_bottom_reo_guidance_change_lines_for_updates,
    candidate_ductility_governs,
    candidate_ductility_util,
)
from design_brain.family_classification import load_family_classification_contract
from design_brain.family_classification_runtime import classify_family_from_whole_beam_evidence
from design_brain.families.registry import normalise_governing_family
from design_brain.final_design_guide_formatter import build_final_design_guide_card_format
from design_brain.families.bending_fail_governs.geometry_ratio import (
    bending_depth_width_ratio_limit,
    depth_width_ratio,
)
from design_brain.design_guide_controller import (
    build_design_guide_controller_active_fail_executor_no_repair_blocker_from_evidence,
    build_design_guide_controller_compute_active_under_capacity_blocker_projection,
    identify_design_guide_controller_materially_overprovided_non_governing_families,
    resolve_design_guide_controller_guidance_action_generated_updates,
    resolve_design_guide_controller_guidance_action_payload_updates,
)
from design_brain.final_publication import (
    build_final_design_guide_primary_apply_payload_projection,
    build_final_design_guide_publication,
    build_final_publication_cta_from_current_state,
    final_design_guide_publication_from_dict,
    stable_final_publication_hash,
)
from design_brain.publication import (
    accepted_green_exact_blocker_is_valid,
    design_guide_cache_fingerprint_from_plain_data,
    design_guide_primary_apply_state_fingerprint_from_state,
    normalise_design_guide_candidate_id,
)
from design_brain.repair import (
    candidate_preview_statuses_have_explicit_fail,
    requires_full_coverage_for_primary_one_click,
)


LegacyGuidanceProvider = Callable[[DesignBrainRequest], Mapping[str, object]]


class LegacyDesignBrainAdapter:
    """Keep current behavior behind the replacement boundary during cutover."""

    def __init__(self, guidance_provider: LegacyGuidanceProvider) -> None:
        if not callable(guidance_provider):
            raise TypeError("guidance_provider must be callable")
        self._guidance_provider = guidance_provider

    def run(self, request: DesignBrainRequest) -> DesignBrainExecution:
        guidance_payload = dict(self._guidance_provider(request) or {})
        execution = run_live_design_brain_pipeline(
            engineering_snapshot=request.engineering_snapshot,
            guidance_payload=guidance_payload,
            family_override=request.family_hint,
            resolved_inputs=request.resolved_inputs,
            engineering_calculations=request.engineering_calculations,
        )
        return DesignBrainExecution(
            result=execution.result,
            stage_trace=tuple(execution.stage_trace),
            pipeline_applied=bool(execution.pipeline_applied),
            bypass_reason=execution.bypass_reason,
        )


__all__ = [
    "LegacyDesignBrainAdapter",
    "LegacyGuidanceProvider",
    "build_full_candidate_evaluation_result_projection",
    "build_target_band_fallback_scored_candidate",
    "diff_candidate_state_updates",
    "resolve_auto_design_band_reacher_delta_metrics",
    "resolve_auto_design_band_reaching_candidate_goal_score",
    "resolve_auto_design_candidate_objective_util",
    "resolve_auto_design_candidate_target_band_metrics",
    "resolve_auto_design_candidate_violation_score",
    "resolve_auto_design_shallower_beam_metrics",
    "resolve_auto_design_shallower_beam_selection_key",
    "resolve_auto_design_shear_candidate_practicality_metrics",
    "resolve_candidate_bending_demand_util",
    "resolve_candidate_domain_max_distance",
    "resolve_candidate_domain_score",
    "resolve_candidate_domain_total_distance",
    "resolve_candidate_in_target_band",
    "resolve_candidate_required_domain_progress",
    "resolve_candidate_required_domains_satisfied",
    "resolve_candidate_step_improves",
    "project_active_fail_executor_evaluated_candidate_result",
    "resolve_active_fail_executor_candidate_eval_source",
    "resolve_target_band_candidate_domains_for_updates",
    "resolve_target_band_candidate_sort_key",
    "resolve_target_band_exhaustion_refinement_allowed",
    "resolve_target_band_next_hop_precheck",
    "resolve_target_band_selected_candidate_acceptance",
    "select_best_target_band_refinement_candidate",
    "select_target_band_ranked_candidate",
    "build_bottom_reo_arrangement_pool_from_state",
    "build_bottom_reo_evaluated_candidate_filter_boundary",
    "build_bottom_reo_evaluated_candidate_filter_record",
    "build_bottom_reo_guidance_change_lines_for_updates",
    "candidate_ductility_governs",
    "candidate_ductility_util",
    "load_family_classification_contract",
    "classify_family_from_whole_beam_evidence",
    "normalise_governing_family",
    "build_final_design_guide_card_format",
    "build_design_guide_controller_active_fail_executor_no_repair_blocker_from_evidence",
    "build_design_guide_controller_compute_active_under_capacity_blocker_projection",
    "identify_design_guide_controller_materially_overprovided_non_governing_families",
    "build_final_design_guide_primary_apply_payload_projection",
    "build_final_design_guide_publication",
    "build_final_publication_cta_from_current_state",
    "final_design_guide_publication_from_dict",
    "stable_final_publication_hash",
    "accepted_green_exact_blocker_is_valid",
    "design_guide_cache_fingerprint_from_plain_data",
    "design_guide_primary_apply_state_fingerprint_from_state",
    "normalise_design_guide_candidate_id",
    "candidate_preview_statuses_have_explicit_fail",
    "requires_full_coverage_for_primary_one_click",
    "resolve_design_guide_controller_guidance_action_generated_updates",
    "resolve_design_guide_controller_guidance_action_payload_updates",
    "bending_depth_width_ratio_limit",
    "depth_width_ratio",
]
