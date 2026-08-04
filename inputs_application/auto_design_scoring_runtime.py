"""Permanent assembly for the frozen auto-design scoring runtime."""

from __future__ import annotations

from typing import Any, Callable

from application.candidate_scoring_policy import (
    resolve_auto_design_candidate_violation_score,
)
from application.candidate_objective_policy import (
    resolve_auto_design_candidate_objective_util,
)
from inputs_application.legacy_design_brain_adapter import (
    resolve_auto_design_shallower_beam_metrics,
    resolve_auto_design_shear_candidate_practicality_metrics,
    resolve_candidate_in_target_band,
)
from inputs_application.candidate_metrics import compute_reo_complexity
from inputs_application.geometry_search_policy import (
    candidate_ductility_governs,
    candidate_ductility_util,
    design_optimisation_goal,
)
from inputs_application.one_click_optimization_policy import (
    candidate_bending_demand_util as resolve_candidate_bending_demand_util,
)
from inputs_application.recommendation_support import resolve_geometry_width_context
from inputs_application.state_utils import float_from_state
from inputs_application.policy_constants import (
    EFFICIENCY_TARGET_UTIL_MAX,
    EFFICIENCY_TARGET_UTIL_MIN,
)
from inputs_application.design_guide_runtime_contracts import (
    AutoDesignScoringRuntime,
)


def _ductility_fix_tier(
    candidate: dict,
    reference_candidate: dict | None,
) -> int:
    if not isinstance(candidate, dict):
        return 4
    reference = reference_candidate or {}
    candidate_state = dict(candidate.get("state") or {})
    reference_state = dict(reference.get("state") or {})
    updates = dict(candidate.get("updates") or {})
    width_key, _, _ = resolve_geometry_width_context(
        reference_state or candidate_state
    )
    bottom_keys = {
        "bot_row_count",
        "bot1_layout_mode",
        "bot1_count",
        "db_bot_1",
        "bot2_layout_mode",
        "bot2_count",
        "db_bot_2",
        "bot_row_1_mode",
        "bot_row_1_bars",
        "bot_row_1_spacing",
        "bot_row_1_dia",
        "bot_row_2_mode",
        "bot_row_2_bars",
        "bot_row_2_spacing",
        "bot_row_2_dia",
    }
    if any(
        key in updates
        for key in {"Ast_top", "db_top", "nb_top", "top_row_count"}
    ):
        return 4
    reference_width = float(
        resolve_geometry_width_context(reference_state or candidate_state)[2]
    )
    reference_depth = float(
        reference.get(
            "depth",
            float_from_state(reference_state or candidate_state, "D", 0.0),
        )
        or float_from_state(reference_state or candidate_state, "D", 0.0)
    )
    candidate_width = float(resolve_geometry_width_context(candidate_state)[2])
    candidate_depth = float(
        candidate.get("depth", float_from_state(candidate_state, "D", 0.0))
        or float_from_state(candidate_state, "D", 0.0)
    )
    width_growth = candidate_width > reference_width + 1e-6
    depth_growth = candidate_depth > reference_depth + 1e-6
    ast_growth = (
        float(candidate.get("Ast_bot", 0.0) or 0.0)
        > float(reference.get("Ast_bot", 0.0) or 0.0) + 1e-6
    )
    if updates and set(updates).issubset(bottom_keys) and not ast_growth:
        return 1
    if width_growth and not depth_growth:
        return 2
    if depth_growth:
        return 3
    if not ast_growth:
        return 1
    if width_growth:
        return 2
    return 4


def _ductility_tier_label(tier: int) -> str:
    return {
        1: "Tier 1 steel-ratio reduction",
        2: "Tier 2 width",
        3: "Tier 3 depth",
        4: "Tier 4 advanced",
    }.get(int(tier), "Tier 4 advanced")


def _candidate_ductility_reason(
    candidate: dict,
    reference_candidate: dict | None,
) -> str:
    tier = _ductility_fix_tier(candidate, reference_candidate)
    return {
        1: "reduce bottom tensile ratio first",
        2: "prefer width before depth",
        3: "depth fallback after steel/width",
    }.get(tier, "advanced or mixed ductility fix")


def _shallower_beam_candidate_tier(candidate: dict) -> tuple[int, str]:
    state = dict(candidate.get("state") or {})
    width = float(resolve_geometry_width_context(state)[2])
    depth = float_from_state(state, "D", 0.0)
    seed_width = float(candidate.get("_seed_width", width) or width)
    seed_depth = float(candidate.get("_seed_depth", depth) or depth)
    candidate_width = float(candidate.get("width", width) or width)
    candidate_depth = float(candidate.get("depth", depth) or depth)
    width_increased = candidate_width > seed_width + 1e-9
    depth_increased = candidate_depth > seed_depth + 1e-9
    if not width_increased and not depth_increased:
        return 0, "local_or_detailing"
    if width_increased and not depth_increased:
        return 1, "width_before_depth"
    if width_increased and depth_increased:
        return 2, "width_plus_depth_fallback"
    return 3, "depth_fallback"


def _candidate_is_practical(candidate: dict, mode_config: dict) -> bool:
    if not candidate:
        return False
    congestion_limit = float(
        mode_config.get("practicality_congestion_limit", 20.0)
    )
    return (
        int(candidate.get("row_count", 0) or 0) <= 2
        and float(candidate.get("reo_congestion_index", 0.0) or 0.0)
        <= congestion_limit
    )


def _candidate_util_distance(candidate: dict, mode_config: dict) -> float:
    util = resolve_auto_design_candidate_objective_util(
        candidate,
        optimisation_goal_resolver=lambda state: design_optimisation_goal(state),
    )
    target_min = float(mode_config["target_util_min"])
    target_max = float(mode_config["target_util_max"])
    midpoint = (target_min + target_max) / 2.0
    if util < target_min:
        return target_min - util
    if util > target_max:
        return util - target_max
    return abs(util - midpoint)


def _failed_check_labels(candidate: dict) -> list[str]:
    statuses = ((candidate or {}).get("overview") or {}).get("statuses", {})
    return [
        key.replace("_", " ")
        for key in ("bending", "shear", "crack", "deflection")
        if str(statuses.get(key, "") or "") == "FAIL"
    ]


def _reject_heavier_steel_lower_demand_util(
    current: dict,
    candidate: dict,
) -> bool:
    if (
        float(candidate.get("Ast_bot", 0.0) or 0.0)
        <= float(current.get("Ast_bot", 0.0) or 0.0) + 1e-6
    ):
        return False
    current_util = resolve_candidate_bending_demand_util(current)
    candidate_util = resolve_candidate_bending_demand_util(candidate)
    return bool(
        current_util is not None
        and candidate_util is not None
        and candidate_util < current_util - 1e-9
    )


def build_auto_design_scoring_runtime(
    *,
    agent_debug_log: Callable[..., Any],
) -> AutoDesignScoringRuntime:
    candidate_in_target_band = lambda candidate, mode: resolve_candidate_in_target_band(
        candidate,
        mode,
        default_target_min=EFFICIENCY_TARGET_UTIL_MIN,
        default_target_max=EFFICIENCY_TARGET_UTIL_MAX,
        optimisation_goal_resolver=lambda state: design_optimisation_goal(state),
    )
    objective_util = lambda candidate: resolve_auto_design_candidate_objective_util(
        candidate,
        optimisation_goal_resolver=lambda state: design_optimisation_goal(state),
    )
    return AutoDesignScoringRuntime(
        agent_debug_log=agent_debug_log,
        candidate_bending_demand_util=resolve_candidate_bending_demand_util,
        candidate_ductility_governs=candidate_ductility_governs,
        candidate_ductility_reason=_candidate_ductility_reason,
        candidate_ductility_util=candidate_ductility_util,
        candidate_in_target_band=candidate_in_target_band,
        candidate_is_practical=_candidate_is_practical,
        candidate_objective_util=objective_util,
        candidate_util_distance=_candidate_util_distance,
        candidate_violation_score=resolve_auto_design_candidate_violation_score,
        ductility_fix_tier=_ductility_fix_tier,
        ductility_tier_label=_ductility_tier_label,
        mode_target_midpoint=lambda mode: (
            float(mode["target_util_min"]) + float(mode["target_util_max"])
        )
        / 2.0,
        failed_check_labels=_failed_check_labels,
        reject_heavier_steel_lower_demand_util=_reject_heavier_steel_lower_demand_util,
        shallower_beam_candidate_tier=_shallower_beam_candidate_tier,
        shallower_beam_metrics=resolve_auto_design_shallower_beam_metrics,
        shear_candidate_practicality_metrics=resolve_auto_design_shear_candidate_practicality_metrics,
        compute_reo_complexity=compute_reo_complexity,
        utilisation_gap=_candidate_util_distance,
    )


__all__ = ["build_auto_design_scoring_runtime"]
