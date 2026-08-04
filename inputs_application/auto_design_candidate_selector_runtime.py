"""Permanent assembly for the typed auto-design candidate selector."""

from __future__ import annotations

from typing import Any

from application.candidate_scoring_policy import (
    resolve_auto_design_candidate_violation_score,
)
from application.candidate_geometry_metrics import (
    resolve_auto_design_band_reacher_delta_metrics,
    resolve_auto_design_band_reaching_candidate_goal_score,
)
from inputs_application.legacy_design_brain_adapter import (
    resolve_auto_design_shallower_beam_selection_key,
    resolve_candidate_in_target_band,
)
from inputs_application.candidate_metrics import int_from_state
from inputs_application.geometry_search_policy import design_optimisation_goal
from inputs_application.recommendation_support import resolve_geometry_width_context
from inputs_application.recommendation_target_band import (
    annotate_candidate_target_band_metrics,
)
from inputs_application.state_utils import float_from_state
from inputs_application.policy_constants import (
    EFFICIENCY_TARGET_UTIL_MAX,
    EFFICIENCY_TARGET_UTIL_MIN,
)
from inputs_application.design_guide_runtime_contracts import (
    AutoDesignCandidateSelectorRuntime,
)
from inputs_application.design_guide_runtime_contracts import AutoDesignScoringRuntime
from inputs_page_modules.design_guide.auto_design_scoring import (
    _score_auto_design_candidate_components,
)


def _target_midpoint(mode_config: dict) -> float:
    return (
        float(
            mode_config.get(
                "target_util_min",
                EFFICIENCY_TARGET_UTIL_MIN,
            )
        )
        + float(
            mode_config.get(
                "target_util_max",
                EFFICIENCY_TARGET_UTIL_MAX,
            )
        )
    ) / 2.0


def _is_valid_reo_layout(
    bar_count,
    diameter,
    beam_width,
    cover,
    minimum_spacing,
) -> bool:
    available = beam_width - 2 * cover
    required = (
        bar_count * diameter
        + (bar_count - 1) * minimum_spacing
    )
    return bool(bar_count >= 2 and required <= available)


def build_auto_design_candidate_selector_runtime(
    *,
    scoring: AutoDesignScoringRuntime,
    trace: Any,
) -> AutoDesignCandidateSelectorRuntime:
    def score_candidate(
        candidate: dict,
        mode_config: dict,
        seed_candidate: dict,
    ) -> float:
        components = _score_auto_design_candidate_components(
            candidate,
            mode_config,
            seed_candidate,
            runtime=scoring,
        )
        candidate["_score_components"] = dict(components)
        return float(components.get("total_score", 0.0) or 0.0)

    return AutoDesignCandidateSelectorRuntime(
        active_rank_trace=None,
        annotate_candidate_target_band_metrics=annotate_candidate_target_band_metrics,
        band_reacher_delta_metrics=resolve_auto_design_band_reacher_delta_metrics,
        candidate_in_target_band=lambda candidate, mode: resolve_candidate_in_target_band(
            candidate,
            mode,
            default_target_min=EFFICIENCY_TARGET_UTIL_MIN,
            default_target_max=EFFICIENCY_TARGET_UTIL_MAX,
            optimisation_goal_resolver=lambda state: design_optimisation_goal(state),
        ),
        candidate_violation_score=resolve_auto_design_candidate_violation_score,
        design_optimisation_goal=lambda state=None: design_optimisation_goal(
            state or {}
        ),
        design_width_value=lambda state: float(
            resolve_geometry_width_context(state)[2]
        ),
        float_from_state=float_from_state,
        int_from_state=int_from_state,
        merge_rank_trace=trace.merge_rank_trace,
        score_auto_design_candidate=score_candidate,
        score_band_reaching_candidate_for_goal=lambda candidate, goal, current_state, mode: resolve_auto_design_band_reaching_candidate_goal_score(
            candidate,
            goal,
            current_state,
            target_mid=_target_midpoint(mode),
        ),
        shallower_beam_selection_key=lambda candidate, seed, mode: resolve_auto_design_shallower_beam_selection_key(
            candidate,
            seed,
            mode,
            target_mid=_target_midpoint(mode),
            default_target_min=EFFICIENCY_TARGET_UTIL_MIN,
            default_target_max=EFFICIENCY_TARGET_UTIL_MAX,
            optimisation_goal_resolver=lambda state: design_optimisation_goal(state),
        ),
        is_valid_reo_layout=_is_valid_reo_layout,
    )


__all__ = ["build_auto_design_candidate_selector_runtime"]
