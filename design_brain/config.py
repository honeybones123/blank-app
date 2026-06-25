"""Pure Design Brain configuration decision helpers.

This module does not read Streamlit/session state and does not import page code.
Page wrappers are responsible for supplying explicit config dictionaries and
defaults.
"""

from __future__ import annotations

from typing import Any, Mapping


def resolve_design_optimisation_goal(
    source: Mapping[str, Any] | None,
    *,
    goal_labels: Mapping[str, Any],
    default_goal: str = "balanced",
) -> str:
    """Return a supported optimisation goal from an explicit source mapping."""
    goal = str((source or {}).get("design_optimisation_goal", default_goal) or default_goal)
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
