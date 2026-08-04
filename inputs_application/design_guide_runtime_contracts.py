"""Pure callable contracts used to assemble Design Guide recommendation stages."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


@dataclass(frozen=True)
class AutoDesignScoringRuntime:
    agent_debug_log: Callable[..., None]
    candidate_bending_demand_util: Callable[[dict], float | None]
    candidate_ductility_governs: Callable[[dict], bool]
    candidate_ductility_reason: Callable[[dict, dict], str | None]
    candidate_ductility_util: Callable[[dict], float | None]
    candidate_in_target_band: Callable[[dict, dict], bool]
    candidate_is_practical: Callable[[dict, dict], bool]
    candidate_objective_util: Callable[[dict], float]
    candidate_util_distance: Callable[[dict, dict], float]
    candidate_violation_score: Callable[[dict], float]
    ductility_fix_tier: Callable[[dict, dict], int]
    ductility_tier_label: Callable[[int], str]
    mode_target_midpoint: Callable[[dict], float]
    failed_check_labels: Callable[[dict], list[str]]
    reject_heavier_steel_lower_demand_util: Callable[[dict, dict], bool]
    shallower_beam_candidate_tier: Callable[[dict], tuple]
    shallower_beam_metrics: Callable[[dict, dict], dict]
    shear_candidate_practicality_metrics: Callable[[dict, dict], dict]
    compute_reo_complexity: Callable[[dict], float]
    utilisation_gap: Callable[[dict, dict], float]


@dataclass(frozen=True)
class AutoDesignCandidateSelectorRuntime:
    active_rank_trace: list[dict] | None
    annotate_candidate_target_band_metrics: Any
    band_reacher_delta_metrics: Any
    candidate_in_target_band: Any
    candidate_violation_score: Any
    design_optimisation_goal: Any
    design_width_value: Any
    float_from_state: Any
    int_from_state: Any
    merge_rank_trace: Any
    score_auto_design_candidate: Any
    score_band_reaching_candidate_for_goal: Any
    shallower_beam_selection_key: Any
    is_valid_reo_layout: Any


@dataclass(frozen=True)
class BottomRecommendationSelectorRuntime:
    shallow_geometry_score_tie_eps: float
    candidate_ductility_governs: Callable[[dict], bool]
    candidate_ductility_util: Callable[[dict], float | None]
    geometry_trial_axis: Callable[[dict, dict], str | None]
    strictly_rejectable_band_winner: Callable[..., tuple[bool, str | None]]
    legacy_local_rejection_reason: Callable[..., str | None]
    log_candidate_rank: Callable[..., None]
    merge_rank_trace: Callable[[dict], None]
    score_candidate: Callable[..., float]
    select_best_candidate: Callable[..., dict | None]
    updates_match_state: Callable[[dict, dict], bool]


__all__ = [
    "AutoDesignCandidateSelectorRuntime",
    "AutoDesignScoringRuntime",
    "BottomRecommendationSelectorRuntime",
]
