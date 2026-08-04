"""Application-owned secondary bending tightening candidate generation."""

from __future__ import annotations

import math

from inputs_application.legacy_design_brain_adapter import build_bottom_reo_arrangement_pool_from_state
from inputs_application.candidate_identity import make_auto_design_candidate_key
from inputs_application.candidate_metrics import candidate_bottom_updates
from inputs_application.geometry_search_policy import (
    build_auto_design_context,
    design_mode_config,
)
from inputs_application.recommendation_evaluation import (
    effective_bottom_design_state,
    evaluate_bending_with_bottom_state,
)
from inputs_application.recommendation_primitives import (
    bottom_arrangement_to_shared_updates,
)
from inputs_application.state_utils import bottom_reo_state_label


GUIDANCE_INEFFICIENT_UTIL_THRESHOLD = 0.75
BOTTOM_RECOMMENDATION_BAR_DIAMETERS = (10, 12, 16, 20, 24, 28, 32, 36, 40)
BOTTOM_RECOMMENDATION_CANDIDATE_LIMIT = 20


def candidate_bending_reserve_util(candidate: dict | None) -> float | None:
    if not candidate:
        return None
    bending_pack = ((candidate.get("overview") or {}).get("packs") or {}).get(
        "bending"
    ) or {}
    capacity = float(bending_pack.get("summary_phiMu_kNm", 0.0) or 0.0)
    demand = float(bending_pack.get("summary_Mu_star_kNm", 0.0) or 0.0)
    if capacity > 1e-9:
        return demand / capacity
    raw = ((candidate.get("overview") or {}).get("utils") or {}).get("bending")
    if raw is None:
        return None
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(value) else value


def secondary_action_reserves(candidate: dict | None) -> dict:
    reserves: dict[str, dict] = {}
    bending_util = candidate_bending_reserve_util(candidate)
    if (
        bending_util is not None
        and bending_util <= GUIDANCE_INEFFICIENT_UTIL_THRESHOLD
    ):
        overview = (candidate or {}).get("overview") or {}
        bending_pack = (overview.get("packs") or {}).get("bending") or {}
        reserves["bending"] = {
            "util": bending_util,
            "bottom_reo": bottom_reo_state_label(
                dict((candidate or {}).get("state") or {})
            ),
            "phiMu": bending_pack.get("summary_phiMu_kNm"),
            "Mu_star": bending_pack.get("summary_Mu_star_kNm"),
        }
    return reserves


def generate_secondary_bending_tightening_states(
    base_candidate: dict,
    *,
    limit: int = 3,
) -> list[dict]:
    bending_util = candidate_bending_reserve_util(base_candidate)
    if (
        bending_util is None
        or bending_util > GUIDANCE_INEFFICIENT_UTIL_THRESHOLD
    ):
        return []
    base_state = dict(base_candidate.get("state") or {})
    if not base_state:
        return []
    current_ast = float(base_candidate.get("Ast_bot", 0.0) or 0.0)
    low_reo_mode = design_mode_config("less_longitudinal_reinforcement")
    context = build_auto_design_context(
        base_state,
        low_reo_mode,
        reference_overview=base_candidate.get("overview"),
    )
    states: dict[tuple, dict] = {}
    raw_limit = max(limit * 2, 6)
    for band in range(2):
        arrangements = build_bottom_reo_arrangement_pool_from_state(
            base_state,
            low_reo_mode,
            band=band,
            context=context,
            limit=raw_limit,
            bar_diameters=BOTTOM_RECOMMENDATION_BAR_DIAMETERS,
            default_limit=BOTTOM_RECOMMENDATION_CANDIDATE_LIMIT,
        )
        for arrangement in arrangements:
            candidate_state = dict(base_state)
            candidate_state.update(
                bottom_arrangement_to_shared_updates(arrangement)
            )
            bottom_updates = candidate_bottom_updates(candidate_state)
            preview_bottom = effective_bottom_design_state(
                candidate_state,
                bottom_updates,
            )
            if (
                float(preview_bottom.get("Ast_bot", 0.0) or 0.0)
                >= current_ast - 1e-6
            ):
                continue
            states[make_auto_design_candidate_key(candidate_state)] = candidate_state

    def _sort_key(candidate_state: dict) -> tuple[float, float]:
        bottom_updates = candidate_bottom_updates(candidate_state)
        bending = (
            evaluate_bending_with_bottom_state(candidate_state, bottom_updates)
            or {}
        )
        bottom = effective_bottom_design_state(candidate_state, bottom_updates)
        return (
            abs(float(bending.get("Mu_util", 999.0) or 999.0) - 0.85),
            float(bottom.get("Ast_bot", 0.0) or 0.0),
        )

    return sorted(states.values(), key=_sort_key)[:limit]


__all__ = [
    "BOTTOM_RECOMMENDATION_BAR_DIAMETERS",
    "BOTTOM_RECOMMENDATION_CANDIDATE_LIMIT",
    "GUIDANCE_INEFFICIENT_UTIL_THRESHOLD",
    "candidate_bending_reserve_util",
    "generate_secondary_bending_tightening_states",
    "secondary_action_reserves",
]
