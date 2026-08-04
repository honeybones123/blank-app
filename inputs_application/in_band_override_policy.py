"""Application-owned policy for surfacing a strong in-band optimisation move."""

from __future__ import annotations

from dataclasses import dataclass

from inputs_application.candidate_metrics import compute_reo_complexity
from inputs_application.recommendation_support import design_width_value
from inputs_application.state_utils import float_from_state


@dataclass(frozen=True)
class InBandOverridePolicy:
    min_width_alone_mm: float
    min_depth_delta_mm: float
    min_ast_delta_mm2: float
    compound_min_width_mm: float
    compound_min_ast_mm2: float
    compound_min_depth_mm: float
    goal_align_min_shallow: float
    goal_align_min_balanced: float
    shallow_depth_up_min_gain: float


def _goal_alignment_penalty(candidate: dict | None, goal: str) -> float:
    if not isinstance(candidate, dict):
        return 1e9
    state = dict(candidate.get("state") or {})
    depth = float(
        candidate.get("depth")
        or float_from_state(state, "D", 0.0)
        or 0.0
    )
    width = float(candidate.get("width") or design_width_value(state) or 0.0)
    ast = float(candidate.get("Ast_bot", 0.0) or 0.0)
    complexity = float(compute_reo_complexity(candidate))
    if goal == "shallower_beam":
        return (
            depth * 0.14
            + width * 0.035
            + ast * 0.016
            + complexity * 4.5
        )
    return (
        ast * 0.055
        + complexity * 9.0
        + depth * 0.055
        + width * 0.038
    )


def _strict_material_passes(
    recommendation: dict,
    updates: dict,
    *,
    policy: InBandOverridePolicy,
) -> bool:
    try:
        delta_width = abs(
            float(recommendation.get("delta_b_mm") or 0.0)
        )
        delta_depth = abs(
            float(recommendation.get("delta_D_mm") or 0.0)
        )
        delta_ast = abs(
            float(recommendation.get("delta_Ast_bot") or 0.0)
        )
    except (TypeError, ValueError):
        return False
    compound = bool(recommendation.get("recommendation_compound"))
    layout_keys = (
        "bot1_count",
        "bot2_count",
        "db_bot_1",
        "db_bot_2",
        "bot_row_count",
    )
    has_layout = any(key in dict(updates or {}) for key in layout_keys)
    if (
        delta_ast >= policy.min_ast_delta_mm2
        or delta_depth >= policy.min_depth_delta_mm
        or delta_width >= policy.min_width_alone_mm
    ):
        return True
    if compound and (
        delta_ast >= policy.compound_min_ast_mm2
        or delta_width >= policy.compound_min_width_mm
        or delta_depth >= policy.compound_min_depth_mm
        or (has_layout and delta_ast >= 45.0)
    ):
        return True
    if has_layout and delta_ast >= 80.0:
        return True
    if has_layout and delta_width >= 35.0 and delta_ast >= 35.0:
        return True
    return False


def _mode_difference_is_material(
    recommendation: dict,
    *,
    policy: InBandOverridePolicy,
) -> bool:
    tag = str(recommendation.get("recommendation_family_tag") or "")
    try:
        delta_width = abs(
            float(recommendation.get("delta_b_mm") or 0.0)
        )
    except (TypeError, ValueError):
        delta_width = 0.0
    return not (
        tag == "pure_geometry_width"
        and delta_width < policy.min_width_alone_mm - 1e-9
    )


def _override_is_strong(recommendation: dict) -> bool:
    try:
        delta_width = abs(
            float(recommendation.get("delta_b_mm") or 0.0)
        )
        delta_depth = abs(
            float(recommendation.get("delta_D_mm") or 0.0)
        )
        delta_ast = abs(
            float(recommendation.get("delta_Ast_bot") or 0.0)
        )
    except (TypeError, ValueError):
        return False
    if delta_depth >= 40.0:
        return True
    if delta_ast >= 140.0:
        return True
    if delta_width >= 60.0 and delta_ast >= 60.0:
        return True
    return bool(recommendation.get("recommendation_compound")) and (
        delta_depth >= 30.0
        or delta_width >= 45.0
        or delta_ast >= 110.0
    )


def should_override_target_band_done_state(
    recommendation: dict,
    state: dict,
    overview: dict,
    goal: str,
    mode_config: dict,
    seed_candidate: dict | None,
    trial_candidate: dict | None,
    *,
    policy: InBandOverridePolicy,
    debug_extra: dict | None = None,
) -> tuple[bool, str]:
    del state
    if isinstance(debug_extra, dict):
        debug_extra["in_band_overview_worst_util"] = overview.get(
            "worst_util"
        )
    updates = dict(recommendation.get("updates") or {})
    if not _strict_material_passes(
        recommendation,
        updates,
        policy=policy,
    ):
        if isinstance(debug_extra, dict):
            debug_extra["in_band_materiality_passed"] = False
        return False, "in_band_strict_materiality_fail"
    if isinstance(debug_extra, dict):
        debug_extra["in_band_materiality_passed"] = True
    if not _override_is_strong(recommendation):
        if isinstance(debug_extra, dict):
            debug_extra["in_band_strong_override_passed"] = False
        return False, "in_band_override_not_strong_enough"
    if isinstance(debug_extra, dict):
        debug_extra["in_band_strong_override_passed"] = True
    if not _mode_difference_is_material(recommendation, policy=policy):
        if isinstance(debug_extra, dict):
            debug_extra["mode_difference_material"] = False
        return (
            False,
            "mode_difference_not_material_pure_geometry_width_nudge",
        )
    if isinstance(debug_extra, dict):
        debug_extra["mode_difference_material"] = True
    if not seed_candidate or not trial_candidate:
        if isinstance(debug_extra, dict):
            debug_extra["current_goal_alignment_score"] = None
            debug_extra["winner_goal_alignment_score"] = None
            debug_extra["goal_alignment_improvement"] = None
        return False, "missing_seed_or_trial_candidate_for_goal_align"
    current_penalty = _goal_alignment_penalty(seed_candidate, goal)
    winner_penalty = _goal_alignment_penalty(trial_candidate, goal)
    improvement = float(current_penalty) - float(winner_penalty)
    if isinstance(debug_extra, dict):
        debug_extra["current_goal_alignment_score"] = current_penalty
        debug_extra["winner_goal_alignment_score"] = winner_penalty
        debug_extra["goal_alignment_improvement"] = improvement
    minimum_gap = (
        policy.goal_align_min_shallow
        if goal == "shallower_beam"
        else policy.goal_align_min_balanced
    )
    if improvement < minimum_gap - 1e-9:
        return False, "goal_alignment_improvement_below_threshold"
    if goal == "shallower_beam":
        initial_depth = float(seed_candidate.get("depth") or 0.0)
        trial_depth = float(trial_candidate.get("depth") or 0.0)
        if (
            trial_depth > initial_depth + 1e-6
            and improvement
            < policy.shallow_depth_up_min_gain - 1e-9
        ):
            return (
                False,
                "shallower_depth_increase_requires_stronger_goal_gain",
            )
    if isinstance(debug_extra, dict):
        debug_extra["in_band_mode_search_strategy"] = str(
            mode_config.get("search_strategy", "") or ""
        )
    return True, "override_allowed"


__all__ = [
    "InBandOverridePolicy",
    "should_override_target_band_done_state",
]
