"""Adapter from the application port to the current Design Brain runtime."""

from __future__ import annotations

from typing import Callable, Mapping

from application.design_brain_port import DesignBrainExecution, DesignBrainRequest
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
)
from design_brain.family_classification_runtime import classify_family_from_whole_beam_evidence
from design_brain.family_ladder_dispatch import resolve_family_ladder_dispatch
from design_brain.whole_beam_family_restamp import restamp_primary_guidance_family_from_whole_beam
from design_brain.pipeline import (
    ApplyCommandConstructionStage,
    ApprovedCandidateProposal,
    AuthoritativeCandidateEvaluation,
    CandidateEvaluationStage,
    CandidateGenerationStage,
    CandidateSelectionStage,
    DesignBrainPipelineDependencies,
    EngineeringResultIntakeStage,
    FamilyDispatchStage,
    GoverningStateClassificationStage,
    PIPELINE_STAGE_ORDER,
    PublicationConstructionStage,
    run_design_brain_pipeline,
)
from design_brain.final_design_guide_formatter import build_final_design_guide_card_format
from design_brain.family_ladder_runtime import (
    FamilyLadderGuidanceRuntime,
    _family_ladder_guidance_item,
    bind_family_ladder_guidance_dependencies,
)
from design_brain.families.geometry_detailing import run_geometry_detailing_governs_runtime
from design_brain.families.registry import family_strategy_for
from design_brain.design_guide_controller import (
    build_design_guide_controller_active_fail_executor_ladder_eval_commands,
    build_design_guide_controller_active_fail_executor_ladder_candidate_meta,
    resolve_design_guide_controller_active_fail_executor_ladder_stop_decision,
    resolve_design_guide_controller_optimisation_candidate_family,
)
from design_brain.bending_overdesign_candidate_evaluation import (
    BendingOverdesignCandidateEvaluation,
    BendingOverdesignCandidateInput,
    BendingOverdesignCandidateUpdate,
    build_bending_overdesign_candidate_state_hash,
)
from design_brain.serviceability_candidate_evaluation import (
    ServiceabilityCandidateEvaluation,
    ServiceabilityCandidateInput,
    ServiceabilityCandidateUpdate,
    build_serviceability_candidate_state_hash,
)
from design_brain.shear_overdesign_candidate_evaluation import (
    ShearOverdesignCandidateEvaluation,
    ShearOverdesignCandidateInput,
    ShearOverdesignCandidateUpdate,
    build_shear_overdesign_candidate_state_hash,
)
from design_brain.shear_fail_bending_overdesign_candidate_merge import (
    MixedCandidateEvaluation as ShearFailBendingOverdesignEvaluation,
    MixedMergedCandidate as ShearFailBendingOverdesignCandidate,
    ShearFailBendingOverdesignInputs,
    mixed_candidate_state_hash as shear_fail_bending_overdesign_state_hash,
)
from design_brain.bending_fail_shear_overdesign_candidate_merge import (
    BendingFailShearOverdesignInputs,
    MixedCandidateEvaluation as BendingFailShearOverdesignEvaluation,
    MixedMergedCandidate as BendingFailShearOverdesignCandidate,
    mixed_candidate_state_hash as bending_fail_shear_overdesign_state_hash,
)
from design_brain.combined_overdesign_candidate_merge import (
    CombinedOverdesignCandidateEvaluation,
    CombinedOverdesignInputs,
    CombinedOverdesignMergedCandidate,
    combined_overdesign_candidate_state_hash,
)
import design_brain.family_ladder_runtime as _family_ladder_runtime_owner


def __getattr__(name: str):
    """Forward legacy family-ladder helpers through the selected adapter."""

    return getattr(_family_ladder_runtime_owner, name)


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(dir(_family_ladder_runtime_owner)))
from design_brain.design_guide_controller import (
    build_design_guide_controller_active_fail_executor_no_repair_blocker_from_evidence,
    build_design_guide_controller_compute_active_under_capacity_blocker_projection,
    identify_design_guide_controller_materially_overprovided_non_governing_families,
)
from design_brain.final_publication import (
    build_final_design_guide_primary_apply_payload_projection,
    build_final_design_guide_publication,
    build_final_publication_cta_from_current_state,
    final_design_guide_publication_from_dict,
)
from design_brain.publication import (
    accepted_green_exact_blocker_is_valid,
    design_guide_cache_fingerprint_from_plain_data,
    design_guide_primary_apply_state_fingerprint_from_state,
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
        # Keep the concrete pipeline import inside the selected implementation
        # boundary.  This also lets legacy result projections depend on this
        # adapter without creating an import cycle through the pipeline.
        from inputs_application.design_brain_pipeline_runtime import (
            run_live_design_brain_pipeline,
        )

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
    "classify_family_from_whole_beam_evidence",
    "build_final_design_guide_card_format",
    "build_design_guide_controller_active_fail_executor_no_repair_blocker_from_evidence",
    "build_design_guide_controller_compute_active_under_capacity_blocker_projection",
    "identify_design_guide_controller_materially_overprovided_non_governing_families",
    "build_final_design_guide_primary_apply_payload_projection",
    "build_final_design_guide_publication",
    "build_final_publication_cta_from_current_state",
    "final_design_guide_publication_from_dict",
    "accepted_green_exact_blocker_is_valid",
    "design_guide_cache_fingerprint_from_plain_data",
    "design_guide_primary_apply_state_fingerprint_from_state",
    "candidate_preview_statuses_have_explicit_fail",
    "requires_full_coverage_for_primary_one_click",
    "resolve_family_ladder_dispatch",
    "restamp_primary_guidance_family_from_whole_beam",
    "ApplyCommandConstructionStage",
    "ApprovedCandidateProposal",
    "AuthoritativeCandidateEvaluation",
    "CandidateEvaluationStage",
    "CandidateGenerationStage",
    "CandidateSelectionStage",
    "DesignBrainPipelineDependencies",
    "EngineeringResultIntakeStage",
    "FamilyDispatchStage",
    "GoverningStateClassificationStage",
    "PIPELINE_STAGE_ORDER",
    "PublicationConstructionStage",
    "run_design_brain_pipeline",
    "FamilyLadderGuidanceRuntime",
    "_family_ladder_guidance_item",
    "bind_family_ladder_guidance_dependencies",
    "run_geometry_detailing_governs_runtime",
    "family_strategy_for",
    "build_design_guide_controller_active_fail_executor_ladder_eval_commands",
    "build_design_guide_controller_active_fail_executor_ladder_candidate_meta",
    "resolve_design_guide_controller_active_fail_executor_ladder_stop_decision",
    "resolve_design_guide_controller_optimisation_candidate_family",
    "BendingOverdesignCandidateEvaluation",
    "BendingOverdesignCandidateInput",
    "BendingOverdesignCandidateUpdate",
    "build_bending_overdesign_candidate_state_hash",
    "ServiceabilityCandidateEvaluation",
    "ServiceabilityCandidateInput",
    "ServiceabilityCandidateUpdate",
    "build_serviceability_candidate_state_hash",
    "ShearOverdesignCandidateEvaluation",
    "ShearOverdesignCandidateInput",
    "ShearOverdesignCandidateUpdate",
    "build_shear_overdesign_candidate_state_hash",
    "ShearFailBendingOverdesignEvaluation",
    "ShearFailBendingOverdesignCandidate",
    "ShearFailBendingOverdesignInputs",
    "shear_fail_bending_overdesign_state_hash",
    "BendingFailShearOverdesignInputs",
    "BendingFailShearOverdesignEvaluation",
    "BendingFailShearOverdesignCandidate",
    "bending_fail_shear_overdesign_state_hash",
    "CombinedOverdesignCandidateEvaluation",
    "CombinedOverdesignInputs",
    "CombinedOverdesignMergedCandidate",
    "combined_overdesign_candidate_state_hash",
]
