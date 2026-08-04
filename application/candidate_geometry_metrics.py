"""Application-owned geometry metrics used by candidate ranking."""

from __future__ import annotations

from typing import Any

from inputs_application.recommendation_support import resolve_geometry_width_context


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
    "resolve_auto_design_shallower_beam_metrics",
    "resolve_auto_design_shear_candidate_practicality_metrics",
]
