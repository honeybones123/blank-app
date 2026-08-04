"""Permanent typed assembly for bottom recommendation selection."""

from __future__ import annotations

from typing import Any

from inputs_application.legacy_design_brain_adapter import (
    candidate_ductility_governs,
    candidate_ductility_util,
)
from inputs_application.auto_design_candidate_selector_runtime import (
    build_auto_design_candidate_selector_runtime,
)
from inputs_application.recommendation_primitives import geometry_trial_axis_for_bottom
from inputs_application.state_utils import updates_match_state
from inputs_page_modules.design_guide.auto_design_candidate_selector import (
    _select_best_auto_design_candidate,
)
from inputs_application.design_guide_runtime_contracts import (
    AutoDesignScoringRuntime,
    BottomRecommendationSelectorRuntime,
)


GUIDANCE_SHALLOW_GEOMETRY_SCORE_TIE_EPS = 24.0


def strictly_rejectable_band_winner(
    candidate: dict | None,
    *,
    state: dict,
) -> tuple[bool, str]:
    if not isinstance(candidate, dict):
        return True, "invalid_candidate"
    if not bool(candidate.get("is_compliant")):
        return True, "noncompliant_candidate"
    if not bool(candidate.get("candidate_reaches_target_band")):
        return True, "not_target_band_candidate"
    updates = candidate.get("updates")
    if not isinstance(updates, dict) or not updates:
        return True, "missing_or_unusable_updates"
    if updates_match_state(state, updates):
        return True, "noop_updates_match_state"
    if not str(candidate.get("label") or "").strip():
        return True, "missing_label"
    return False, "ok"


def legacy_bottom_local_rejection_reason(
    pick: dict,
    *,
    seed_candidate: dict,
    seed_bu_f: float | None,
    ductility_seed: bool,
    seed_du: float | None,
) -> str | None:
    raw = ((pick.get("overview") or {}).get("utils") or {}).get("bending")
    try:
        bending_util = float(raw) if raw is not None else None
    except (TypeError, ValueError):
        bending_util = None
    if bending_util is None:
        return "missing_bending_util"
    if ductility_seed:
        pick_ductility = candidate_ductility_util(pick)
        if (
            seed_du is not None
            and pick_ductility is not None
            and float(pick_ductility) >= float(seed_du) - 1e-9
        ):
            return "ductility_not_improved"
        return None
    if (
        seed_bu_f is not None
        and bending_util >= float(seed_bu_f) - 1e-9
    ):
        return "bending_util_not_improved"
    return None


def build_bottom_selector_runtime(
    *,
    scoring: AutoDesignScoringRuntime,
    trace: Any,
) -> BottomRecommendationSelectorRuntime:
    auto_selector = build_auto_design_candidate_selector_runtime(
        scoring=scoring,
        trace=trace,
    )
    return BottomRecommendationSelectorRuntime(
        shallow_geometry_score_tie_eps=GUIDANCE_SHALLOW_GEOMETRY_SCORE_TIE_EPS,
        candidate_ductility_governs=candidate_ductility_governs,
        candidate_ductility_util=candidate_ductility_util,
        geometry_trial_axis=geometry_trial_axis_for_bottom,
        strictly_rejectable_band_winner=strictly_rejectable_band_winner,
        legacy_local_rejection_reason=legacy_bottom_local_rejection_reason,
        log_candidate_rank=trace.log_candidate_rank,
        merge_rank_trace=trace.merge_rank_trace,
        score_candidate=auto_selector.score_auto_design_candidate,
        select_best_candidate=lambda candidates, mode, seed: _select_best_auto_design_candidate(
            candidates,
            mode,
            seed,
            runtime=auto_selector,
        ),
        updates_match_state=updates_match_state,
    )


__all__ = [
    "build_bottom_selector_runtime",
    "legacy_bottom_local_rejection_reason",
    "strictly_rejectable_band_winner",
]
