"""Pure support functions used by Inputs recommendation presentation."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from design_brain.config import (
    DESIGN_OPTIMISATION_GOAL_LABELS,
    resolve_design_optimisation_goal,
)


def design_optimisation_goal_label(state: Mapping[str, Any] | None = None) -> str:
    goal = str(
        resolve_design_optimisation_goal(
            dict(state or {}),
            goal_labels=DESIGN_OPTIMISATION_GOAL_LABELS,
            default_goal="balanced",
        )
    )
    return DESIGN_OPTIMISATION_GOAL_LABELS[goal]


def resolve_geometry_width_context(state: Mapping[str, Any]) -> tuple[str, str, float]:
    sec_shape = str(state.get("sec_shape", "RECT") or "RECT")
    if sec_shape == "T":
        return "bw", "Web width bw (mm)", float(state.get("bw", state.get("b", 300.0)) or 300.0)
    if sec_shape == "I":
        return "tw", "Web thickness tw (mm)", float(state.get("tw", state.get("b", 200.0)) or 200.0)
    return "b", "Width b (mm)", float(state.get("b", 400.0) or 400.0)


def design_width_value(state: Mapping[str, Any]) -> float:
    return float(resolve_geometry_width_context(state)[2])


def shear_severity_band(util: float | None) -> str:
    if util is None:
        return "mild"
    value = float(util)
    if value < 1.15:
        return "mild"
    if value < 1.75:
        return "moderate"
    if value < 3.0:
        return "severe"
    return "extreme"


def severe_shear_failure(util: float | None) -> bool:
    return shear_severity_band(util) in ("severe", "extreme")


__all__ = [
    "design_optimisation_goal_label",
    "design_width_value",
    "resolve_geometry_width_context",
    "severe_shear_failure",
    "shear_severity_band",
]
