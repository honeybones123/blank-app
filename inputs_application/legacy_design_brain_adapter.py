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
]
