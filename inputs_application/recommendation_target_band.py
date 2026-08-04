"""Application-owned target-band annotations for recommendation candidates."""

from __future__ import annotations

from inputs_application.legacy_design_brain_adapter import (
    resolve_auto_design_candidate_target_band_metrics,
)
from inputs_application.geometry_search_policy import design_optimisation_goal
from inputs_application.policy_constants import (
    EFFICIENCY_TARGET_UTIL_MAX,
    EFFICIENCY_TARGET_UTIL_MIN,
)


def annotate_candidate_target_band_metrics(
    candidate: dict,
    mode_config: dict,
) -> None:
    if not candidate:
        return
    candidate.update(
        resolve_auto_design_candidate_target_band_metrics(
            candidate,
            mode_config,
            default_target_min=EFFICIENCY_TARGET_UTIL_MIN,
            default_target_max=EFFICIENCY_TARGET_UTIL_MAX,
            optimisation_goal_resolver=design_optimisation_goal,
        )
    )


__all__ = ["annotate_candidate_target_band_metrics"]
