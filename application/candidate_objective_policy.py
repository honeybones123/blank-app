"""Application-owned objective utilisation policy for candidate ranking."""

from __future__ import annotations

import math
from typing import Any, Callable

from inputs_application.one_click_optimization_policy import (
    candidate_bending_demand_util,
)


def resolve_auto_design_candidate_objective_util(
    candidate: dict[str, Any] | None,
    *,
    optimisation_goal: str | None = None,
    optimisation_goal_resolver: Callable[[dict[str, Any]], str] | None = None,
) -> float:
    """Resolve the objective utilisation used by target-band candidate ranking."""

    candidate_d = candidate if isinstance(candidate, dict) else {}
    state = candidate_d.get("state") if isinstance(candidate_d.get("state"), dict) else {}
    if optimisation_goal is not None:
        goal = str(optimisation_goal or "")
    elif callable(optimisation_goal_resolver):
        goal = str(optimisation_goal_resolver(dict(state or {})) or "")
    else:
        goal = str(state.get("design_optimisation_goal") or "balanced")
    overview = candidate_d.get("overview") if isinstance(candidate_d.get("overview"), dict) else {}
    utils = overview.get("utils") if isinstance(overview.get("utils"), dict) else {}
    target_domain = str(candidate_d.get("target_domain_for_band") or "").strip().lower()
    bending_demand_util = candidate_bending_demand_util(candidate_d)

    if target_domain == "shear" or goal == "less_shear_reinforcement":
        objective_values = [utils.get("shear")]
    else:
        objective_values = [bending_demand_util, utils.get("shear")]

    resolved_values: list[float] = []
    for value in objective_values:
        if value is None:
            continue
        try:
            resolved = float(value)
        except Exception:
            continue
        if not math.isnan(resolved):
            resolved_values.append(resolved)

    if resolved_values:
        return max(resolved_values)
    return float(candidate_d.get("worst_util", 0.0) or 0.0)


__all__ = ["resolve_auto_design_candidate_objective_util"]
