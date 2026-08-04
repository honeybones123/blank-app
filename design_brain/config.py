"""Compatibility exports for the application-owned design policy contract."""

from application.contracts.design_policy import (
    AUTO_DESIGN_MODE_CONFIG,
    DESIGN_OPTIMISATION_GOAL_LABELS,
    resolve_design_mode_config,
    resolve_design_optimisation_goal,
    resolve_efficiency_target_band,
)

__all__ = [
    "AUTO_DESIGN_MODE_CONFIG",
    "DESIGN_OPTIMISATION_GOAL_LABELS",
    "resolve_design_mode_config",
    "resolve_design_optimisation_goal",
    "resolve_efficiency_target_band",
]
