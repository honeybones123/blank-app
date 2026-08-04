"""Application-owned target-band candidate annotation."""

from __future__ import annotations

from typing import Any, Callable

from application.candidate_objective_policy import resolve_auto_design_candidate_objective_util
from application.target_band_evaluation import (
    resolve_candidate_in_target_band,
    resolve_distance_to_target_band,
)


def resolve_auto_design_candidate_target_band_metrics(
    candidate: dict[str, Any] | None,
    mode_config: dict[str, Any] | None,
    *,
    default_target_min: float,
    default_target_max: float,
    fail_status: str = "FAIL",
    optimisation_goal_resolver: Callable[[dict[str, Any]], str] | None = None,
) -> dict[str, Any]:
    """Resolve the target-band annotation fields for an auto-design candidate."""

    mode = dict(mode_config or {})
    try:
        target_min = float(mode.get("target_util_min", default_target_min) or default_target_min)
        target_max = float(mode.get("target_util_max", default_target_max) or default_target_max)
    except (TypeError, ValueError):
        target_min = float(default_target_min)
        target_max = float(default_target_max)
    util = resolve_auto_design_candidate_objective_util(
        candidate,
        optimisation_goal_resolver=optimisation_goal_resolver,
    )
    candidate_d = candidate if isinstance(candidate, dict) else {}
    return {
        "candidate_post_util": float(util),
        "candidate_distance_to_target_band": resolve_distance_to_target_band(
            util,
            target_min,
            target_max,
        ),
        "candidate_reaches_target_band": bool(
            bool(candidate_d.get("is_compliant"))
            and resolve_candidate_in_target_band(
                candidate,
                mode,
                default_target_min=default_target_min,
                default_target_max=default_target_max,
                fail_status=fail_status,
                optimisation_goal_resolver=optimisation_goal_resolver,
            )
        ),
    }


__all__ = ["resolve_auto_design_candidate_target_band_metrics"]
