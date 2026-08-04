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


__all__ = ["resolve_auto_design_shallower_beam_metrics"]
