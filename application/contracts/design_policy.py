"""Application-owned design policy configuration.

The page and application layers consume this policy contract directly.  The
legacy ``design_brain.config`` module remains only as a compatibility export
for the current implementation until the replacement adapter is connected.
"""

from __future__ import annotations

from typing import Any, Mapping

from optimisation_config import get_target_utilisation_band


_BALANCED_TARGET_UTIL_MIN, _BALANCED_TARGET_UTIL_MAX = get_target_utilisation_band(
    "balanced"
)

AUTO_DESIGN_MODE_CONFIG = {
    "balanced": {
        "label": "Balanced design",
        "target_util_min": _BALANCED_TARGET_UTIL_MIN,
        "target_util_max": _BALANCED_TARGET_UTIL_MAX,
        "search_strategy": "balanced",
        "max_frontier": 5,
        "material_depth_delta_mm": 25.0,
        "material_reo_complexity_delta": 4.0,
        "practicality_congestion_limit": 20.0,
        "complexity_penalty": 0.9,
        "prefer_shallower_section": False,
        "prefer_lower_reo_congestion": False,
        "allow_high_steel_ratio": False,
        "geometry_penalty": 1.0,
        "width_penalty": 0.45,
        "steel_penalty": 1.0,
        "reo_congestion_penalty": 1.0,
        "depth_priority": "secondary",
        "depth_growth_multiplier": 1.8,
    },
    "shallower_beam": {
        "label": "Shallower beam",
        "target_util_min": 0.85,
        "target_util_max": 0.98,
        "search_strategy": "shallow",
        "max_frontier": 4,
        "material_depth_delta_mm": 25.0,
        "material_reo_complexity_delta": 999.0,
        "practicality_congestion_limit": 28.0,
        "complexity_penalty": 0.4,
        "prefer_shallower_section": True,
        "prefer_lower_reo_congestion": False,
        "allow_high_steel_ratio": True,
        "geometry_penalty": 2.5,
        "width_penalty": 0.55,
        "steel_penalty": 0.8,
        "reo_congestion_penalty": 1.0,
        "depth_priority": "primary",
        "depth_growth_multiplier": 2.8,
    },
    "less_longitudinal_reinforcement": {
        "label": "Less longitudinal reinforcement",
        "target_util_min": 0.75,
        "target_util_max": 0.90,
        "search_strategy": "low_reo",
        "max_frontier": 4,
        "material_depth_delta_mm": 999.0,
        "material_reo_complexity_delta": 4.0,
        "practicality_congestion_limit": 18.0,
        "complexity_penalty": 1.8,
        "prefer_shallower_section": False,
        "prefer_lower_reo_congestion": True,
        "allow_high_steel_ratio": False,
        "geometry_penalty": 0.8,
        "width_penalty": 0.35,
        "steel_penalty": 1.2,
        "reo_congestion_penalty": 2.0,
        "depth_priority": "tertiary",
        "depth_growth_multiplier": 1.0,
    },
    "less_shear_reinforcement": {
        "label": "Less shear reinforcement",
        "target_util_min": 0.78,
        "target_util_max": 0.92,
        "search_strategy": "balanced",
        "max_frontier": 4,
        "material_depth_delta_mm": 25.0,
        "material_reo_complexity_delta": 6.0,
        "practicality_congestion_limit": 20.0,
        "complexity_penalty": 1.0,
        "prefer_shallower_section": False,
        "prefer_lower_reo_congestion": False,
        "allow_high_steel_ratio": False,
        "geometry_penalty": 0.9,
        "width_penalty": 0.35,
        "steel_penalty": 0.95,
        "reo_congestion_penalty": 1.15,
        "depth_priority": "secondary",
        "depth_growth_multiplier": 1.2,
    },
}

DESIGN_OPTIMISATION_GOAL_LABELS = {
    key: str(config["label"])
    for key, config in AUTO_DESIGN_MODE_CONFIG.items()
}


def resolve_design_optimisation_goal(
    source: Mapping[str, Any] | None,
    *,
    goal_labels: Mapping[str, Any],
    default_goal: str = "balanced",
) -> str:
    """Return a supported optimisation goal from an explicit source mapping."""

    goal = str(
        (source or {}).get("design_optimisation_goal", default_goal) or default_goal
    )
    if goal not in goal_labels:
        return default_goal
    return goal


def resolve_design_mode_config(
    goal: str | None,
    *,
    mode_config_by_goal: Mapping[str, Mapping[str, Any]],
    default_goal: str = "balanced",
) -> dict:
    """Return a copied design-mode config for an explicit goal."""

    resolved_goal = goal or default_goal
    return dict(mode_config_by_goal.get(resolved_goal, mode_config_by_goal[default_goal]))


def resolve_efficiency_target_band(
    mode_config: Mapping[str, Any] | None = None,
    *,
    goal: str | None,
    mode_config_by_goal: Mapping[str, Mapping[str, Any]],
    default_low: float,
    default_high: float,
    default_goal: str = "balanced",
) -> tuple[float, float, bool]:
    """Resolve target-band scalars from explicit config and defaults."""

    resolved_goal = goal or default_goal
    cfg = dict(mode_config or {})
    has_explicit_band = "target_util_min" in cfg and "target_util_max" in cfg
    if has_explicit_band:
        lo = float(cfg.get("target_util_min", default_low) or default_low)
        hi = float(cfg.get("target_util_max", default_high) or default_high)
        default_used = bool(
            resolved_goal == default_goal
            and abs(lo - default_low) <= 1e-9
            and abs(hi - default_high) <= 1e-9
        )
        return lo, hi, default_used
    if resolved_goal == default_goal:
        return default_low, default_high, True
    fallback_cfg = resolve_design_mode_config(
        resolved_goal,
        mode_config_by_goal=mode_config_by_goal,
        default_goal=default_goal,
    )
    lo = float(fallback_cfg.get("target_util_min", default_low) or default_low)
    hi = float(fallback_cfg.get("target_util_max", default_high) or default_high)
    return lo, hi, False


__all__ = [
    "AUTO_DESIGN_MODE_CONFIG",
    "DESIGN_OPTIMISATION_GOAL_LABELS",
    "resolve_design_mode_config",
    "resolve_design_optimisation_goal",
    "resolve_efficiency_target_band",
]
