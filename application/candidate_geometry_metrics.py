"""Application-owned geometry metrics used by candidate ranking."""

from __future__ import annotations

from typing import Any

from inputs_application.recommendation_support import resolve_geometry_width_context
from application.candidate_objective_policy import (
    resolve_auto_design_candidate_objective_util,
)
from application.target_band_evaluation import resolve_candidate_in_target_band


def _target_band_float(source: dict[str, Any], key: str, default: float) -> float:
    value = source.get(key)
    if value is None:
        return float(default)
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _target_band_int(source: dict[str, Any], key: str, default: int) -> int:
    value = source.get(key)
    if value is None:
        return int(default)
    try:
        return int(value)
    except (TypeError, ValueError):
        return int(default)


def resolve_auto_design_shear_candidate_practicality_metrics(
    candidate: dict[str, Any] | None,
    current_state: dict[str, Any] | None,
) -> dict[str, float | int]:
    """Resolve shear cleanup/strength candidate practicality metrics from plain state."""

    candidate_d = candidate if isinstance(candidate, dict) else {}
    cs = dict(candidate_d.get("state") or {})
    current = dict(current_state or {})
    cur_legs = max(_target_band_int(current, "lig_legs", 0), 0)
    cand_legs = max(_target_band_int(cs, "lig_legs", cur_legs), 0)
    cur_s = float(_target_band_float(current, "s_lig", 0.0) or 0.0)
    cand_s = float(_target_band_float(cs, "s_lig", cur_s) or cur_s)
    cur_dia = max(_target_band_int(current, "lig_d", 0), 0)
    cand_dia = max(_target_band_int(cs, "lig_d", cur_dia), 0)
    cur_depth = float(_target_band_float(current, "D", 0.0) or 0.0)
    cand_depth = float(_target_band_float(cs, "D", cur_depth) or cur_depth)
    _, _, cur_width_raw = resolve_geometry_width_context(current)
    _, _, cand_width_raw = resolve_geometry_width_context(cs)
    cur_width = float(cur_width_raw or 0.0)
    cand_width = float(cand_width_raw or cur_width)
    cur_ast_bot = float(_target_band_float(current, "Ast_bot", 0.0) or 0.0)
    cur_ast_top = float(_target_band_float(current, "Ast_top", 0.0) or 0.0)
    cur_ast = cur_ast_bot + cur_ast_top
    cand_ast = (
        float(candidate_d.get("Ast_bot", _target_band_float(cs, "Ast_bot", cur_ast_bot)) or 0.0)
        + float(candidate_d.get("Ast_top", _target_band_float(cs, "Ast_top", cur_ast_top)) or 0.0)
    )

    leg_delta = abs(int(cand_legs) - int(cur_legs))
    spacing_delta = abs(float(cand_s) - float(cur_s))
    dia_delta = abs(int(cand_dia) - int(cur_dia))
    depth_delta = abs(float(cand_depth) - float(cur_depth))
    width_delta = abs(float(cand_width) - float(cur_width))
    steel_delta = abs(float(cand_ast) - float(cur_ast))
    odd_leg_penalty = 0.015 if cand_legs > 0 and cand_legs % 2 == 1 else 0.0
    total_practicality_penalty = odd_leg_penalty + (float(leg_delta) * 0.01)
    geometry_escalation_flag = 1 if (depth_delta > 1e-9 or width_delta > 1e-9) else 0
    geometry_delta = depth_delta + width_delta
    engineering_change = (
        (5.0 if geometry_escalation_flag else 0.0)
        + float(leg_delta)
        + (spacing_delta / 100.0)
        + (dia_delta / 2.0)
        + (geometry_delta / 100.0)
        + (steel_delta / 500.0)
        + total_practicality_penalty
    )
    return {
        "shear_candidate_leg_count": int(cand_legs),
        "shear_candidate_leg_delta": int(leg_delta),
        "shear_candidate_spacing_delta": float(spacing_delta),
        "shear_candidate_dia_delta": int(dia_delta),
        "shear_candidate_depth_delta": float(depth_delta),
        "shear_candidate_width_delta": float(width_delta),
        "shear_candidate_geometry_delta": float(geometry_delta),
        "shear_candidate_geometry_escalation_flag": int(geometry_escalation_flag),
        "shear_candidate_steel_delta": float(steel_delta),
        "shear_candidate_odd_leg_penalty": float(odd_leg_penalty),
        "shear_candidate_total_practicality_penalty": float(total_practicality_penalty),
        "shear_candidate_engineering_change": float(engineering_change),
    }


def resolve_auto_design_band_reacher_delta_metrics(
    candidate: dict[str, Any] | None,
    current_state: dict[str, Any] | None,
) -> dict[str, float | int]:
    """Resolve band-reaching candidate geometry and reinforcement deltas."""

    candidate_d = candidate if isinstance(candidate, dict) else {}
    cs = dict(candidate_d.get("state") or {})
    current = dict(current_state or {})
    d0 = float(_target_band_float(current, "D", 0.0) or 0.0)
    d1 = float(_target_band_float(cs, "D", d0) or d0)
    _, _, w0_raw = resolve_geometry_width_context(current)
    _, _, w1_raw = resolve_geometry_width_context(cs)
    w0 = float(w0_raw or 0.0)
    w1 = float(w1_raw or w0)
    ast0 = float(_target_band_float(current, "Ast_bot", 0.0) or 0.0)
    ast1 = float(candidate_d.get("Ast_bot", _target_band_float(cs, "Ast_bot", ast0)) or ast0)
    return {
        "result_depth": float(d1),
        "delta_d": float(max(d1 - d0, 0.0)),
        "delta_w": float(max(w1 - w0, 0.0)),
        "delta_ast": float(max(ast1 - ast0, 0.0)),
        "congestion": float(candidate_d.get("reo_congestion_index", 0.0) or 0.0),
        "row_pen": int(max(int(candidate_d.get("row_count", 1) or 1) - 2, 0)),
    }


def resolve_auto_design_band_reaching_candidate_goal_score(
    candidate: dict[str, Any] | None,
    goal: str | None,
    current_state: dict[str, Any] | None,
    *,
    target_mid: float,
) -> tuple[float, str]:
    """Resolve the goal-specific score for a candidate that reaches target band."""

    candidate_d = candidate if isinstance(candidate, dict) else {}
    deltas = resolve_auto_design_band_reacher_delta_metrics(candidate_d, current_state)
    d1 = float(deltas.get("result_depth", 0.0) or 0.0)
    delta_d = float(deltas.get("delta_d", 0.0) or 0.0)
    delta_w = float(deltas.get("delta_w", 0.0) or 0.0)
    delta_ast = float(deltas.get("delta_ast", 0.0) or 0.0)
    post_util = float(
        candidate_d.get(
            "candidate_post_util",
            resolve_auto_design_candidate_objective_util(candidate_d),
        )
        or 0.0
    )
    congestion = float(deltas.get("congestion", 0.0) or 0.0)
    row_pen = int(deltas.get("row_pen", 0) or 0)

    if str(goal or "") == "shallower_beam":
        score = (
            (delta_d * 2000.0)
            + (d1 * 0.6)
            + (delta_ast * 0.08)
            + (delta_w * 0.04)
            + (congestion * 20.0)
            + (row_pen * 8.0)
        )
        if (
            bool(candidate_d.get("recommendation_compound"))
            and str(candidate_d.get("compound_geo_axis") or "") == "width"
            and delta_d <= 1e-6
        ):
            score -= 30.0
        return float(score), "shallower_prefers_min_depth_then_steel_then_width"

    score = (
        (abs(post_util - float(target_mid)) * 90.0)
        + (delta_d * 0.3)
        + (delta_w * 0.25)
        + (delta_ast * 0.04)
        + (congestion * 18.0)
        + (row_pen * 8.0)
    )
    return float(score), "balanced_prefers_practical_low_congestion_near_target_mid"


def resolve_auto_design_shallower_beam_selection_key(
    candidate: dict[str, Any] | None,
    seed_candidate: dict[str, Any] | None,
    mode_config: dict[str, Any] | None,
    *,
    target_mid: float,
    default_target_min: float,
    default_target_max: float,
    fail_status: str = "FAIL",
    optimisation_goal_resolver: Callable[[dict[str, Any]], str] | None = None,
) -> tuple[Any, ...]:
    """Resolve the shallow-search selector key from plain candidate data."""

    candidate_d = candidate if isinstance(candidate, dict) else {}
    seed_d = seed_candidate if isinstance(seed_candidate, dict) else {}
    candidate_state = dict(candidate_d.get("state") or {})
    seed_state = dict(seed_d.get("state") or {})
    seed_depth_default = _target_band_float(seed_state, "D", 0.0)
    candidate_depth_default = _target_band_float(candidate_state, "D", 0.0)
    seed_depth = float(seed_d.get("depth", seed_depth_default) or seed_depth_default)
    cand_depth = float(candidate_d.get("depth", candidate_depth_default) or candidate_depth_default)
    _, _, seed_width_default = resolve_geometry_width_context(seed_state)
    _, _, candidate_width_default = resolve_geometry_width_context(candidate_state)
    seed_width = float(seed_d.get("width", seed_width_default) or seed_width_default)
    cand_width = float(candidate_d.get("width", candidate_width_default) or candidate_width_default)
    seed_ast = float(seed_d.get("Ast_bot", 0.0) or 0.0)
    cand_ast = float(candidate_d.get("Ast_bot", 0.0) or 0.0)
    delta_d_mm = max(cand_depth - seed_depth, 0.0)
    delta_b_mm = max(cand_width - seed_width, 0.0)
    delta_ast_bot = max(cand_ast - seed_ast, 0.0)
    is_geometry = bool(candidate_d.get("recommendation_geometry_trial"))
    in_band = 0 if resolve_candidate_in_target_band(
        candidate_d,
        mode_config,
        default_target_min=default_target_min,
        default_target_max=default_target_max,
        fail_status=fail_status,
        optimisation_goal_resolver=optimisation_goal_resolver,
    ) else 1
    congestion = float(candidate_d.get("reo_congestion_index", 0.0) or 0.0)
    util = resolve_auto_design_candidate_objective_util(
        candidate_d,
        optimisation_goal_resolver=optimisation_goal_resolver,
    )
    mode = dict(mode_config or {})
    try:
        target_min = float(mode.get("target_util_min", default_target_min) or default_target_min)
        target_max = float(mode.get("target_util_max", default_target_max) or default_target_max)
    except (TypeError, ValueError):
        target_min = float(default_target_min)
        target_max = float(default_target_max)
    if util < target_min:
        util_gap = target_min - util
    elif util > target_max:
        util_gap = util - target_max
    else:
        util_gap = abs(util - float(target_mid))
    return (
        0 if bool(candidate_d.get("is_compliant")) else 1,
        in_band,
        delta_d_mm,
        0 if not is_geometry else 1,
        delta_b_mm,
        delta_ast_bot,
        congestion,
        round(float(candidate_d.get("score", float("inf")) or float("inf")), 4),
        float(util_gap),
        float(candidate_d.get("worst_util", float("inf")) or float("inf")),
    )
def resolve_auto_design_shallower_beam_metrics(
    candidate: dict[str, Any] | None,
    seed_candidate: dict[str, Any] | None,
) -> dict[str, float | bool]:
    """Resolve shallower-beam preference metrics from plain candidate data."""

    candidate_d = candidate if isinstance(candidate, dict) else {}
    seed_d = seed_candidate if isinstance(seed_candidate, dict) else {}
    candidate_state = dict(candidate_d.get("state") or {})
    seed_state = dict(seed_d.get("state") or {})
    seed_depth_default = _target_band_float(seed_state, "D", 0.0)
    candidate_depth_default = _target_band_float(candidate_state, "D", 0.0)
    _, _, seed_width_default = resolve_geometry_width_context(seed_state)
    _, _, candidate_width_default = resolve_geometry_width_context(candidate_state)
    seed_depth = float(seed_d.get("depth", seed_depth_default) or seed_depth_default)
    candidate_depth = float(candidate_d.get("depth", candidate_depth_default) or candidate_depth_default)
    seed_width = float(seed_d.get("width", seed_width_default) or seed_width_default)
    candidate_width = float(candidate_d.get("width", candidate_width_default) or candidate_width_default)
    seed_ast = float(seed_d.get("Ast_bot", 0.0) or 0.0)
    candidate_ast = float(candidate_d.get("Ast_bot", 0.0) or 0.0)
    depth_reduction = max(seed_depth - candidate_depth, 0.0)
    width_growth = max(candidate_width - seed_width, 0.0)
    reinforcement_growth = max(candidate_ast - seed_ast, 0.0)
    shallowness_score = depth_reduction - (0.45 * width_growth) - (0.04 * reinforcement_growth)
    materially_shallower = (
        depth_reduction >= 50.0
        or (
            depth_reduction >= 25.0
            and width_growth <= 50.0
            and reinforcement_growth <= 120.0
        )
    )
    return {
        "depth_reduction": float(depth_reduction),
        "width_growth": float(width_growth),
        "reinforcement_growth": float(reinforcement_growth),
        "shallowness_score": float(shallowness_score),
        "materially_shallower": bool(materially_shallower),
    }


__all__ = [
    "resolve_auto_design_band_reacher_delta_metrics",
    "resolve_auto_design_band_reaching_candidate_goal_score",
    "resolve_auto_design_shallower_beam_metrics",
    "resolve_auto_design_shallower_beam_selection_key",
    "resolve_auto_design_shear_candidate_practicality_metrics",
]
