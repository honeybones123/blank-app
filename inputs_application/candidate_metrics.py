"""Pure candidate projection and reinforcement metrics."""

from __future__ import annotations

import math
from typing import Any, Mapping

from inputs_application.recommendation_evaluation import effective_bottom_design_state
from inputs_application.recommendation_support import resolve_geometry_width_context
from inputs_application.state_utils import float_from_state


def int_from_state(state: Mapping[str, Any], key: str, default: int = 0) -> int:
    try:
        return int(float(state.get(key, default) or 0))
    except (TypeError, ValueError):
        return int(default)


def candidate_bottom_updates(state: Mapping[str, Any]) -> dict[str, int] | None:
    # Combined-family candidates intentionally cross the family boundary using
    # canonical row-model keys.  Those keys must take precedence over the
    # retained legacy aliases from the base state; otherwise the evaluator
    # silently tests the old reinforcement rather than the proposed update.
    diameter_1 = int_from_state(
        state,
        "bot_row_1_dia",
        int_from_state(state, "db_bot_1", 0),
    )
    count_1 = int_from_state(
        state,
        "bot_row_1_bars",
        int_from_state(state, "bot1_count", 0),
    )
    count_2 = int_from_state(
        state,
        "bot_row_2_bars",
        int_from_state(state, "bot2_count", 0),
    )
    if diameter_1 <= 0 or count_1 + count_2 <= 0:
        return None
    return {
        "db_bot_1": diameter_1,
        "db_bot_2": int_from_state(
            state,
            "bot_row_2_dia",
            int_from_state(state, "db_bot_2", diameter_1),
        ),
        "bot1_count": count_1,
        "bot2_count": count_2,
    }


def candidate_shear_updates(state: Mapping[str, Any]) -> dict[str, float | int]:
    return {
        "lig_d": int_from_state(state, "lig_d", 10),
        "lig_legs": int_from_state(state, "lig_legs", 2),
        "s_lig": float_from_state(state, "s_lig", 200.0),
    }


def bottom_row_count(state: Mapping[str, Any]) -> int:
    explicit = int_from_state(state, "bot_row_count", 0)
    if explicit > 0:
        return explicit
    return (
        2
        if int_from_state(
            state,
            "bot_row_2_bars",
            int_from_state(state, "bot2_count", 0),
        )
        > 0
        else 1
    )


def bottom_bar_count(
    state: Mapping[str, Any],
    bottom_state: Mapping[str, Any] | None = None,
) -> int:
    resolved = dict(bottom_state or effective_bottom_design_state(state))
    explicit = int(resolved.get("nb_bot", 0) or 0)
    if explicit > 0:
        return explicit
    return int_from_state(
        state,
        "bot_row_1_bars",
        int_from_state(state, "bot1_count", 0),
    ) + int_from_state(
        state,
        "bot_row_2_bars",
        int_from_state(state, "bot2_count", 0),
    )


def reo_congestion_index(
    state: Mapping[str, Any],
    bottom_state: Mapping[str, Any] | None = None,
) -> float:
    resolved = dict(bottom_state or effective_bottom_design_state(state))
    total_bars = bottom_bar_count(state, resolved)
    rows = max(bottom_row_count(state), 1)
    diameter = float(
        resolved.get("db_bot", 0.0)
        or float_from_state(
            state,
            "bot_row_1_dia",
            float_from_state(state, "db_bot_1", 0.0),
        )
    )
    width = max(float(resolve_geometry_width_context(state)[2]), 1.0)
    return float(
        total_bars
        + max(rows - 1, 0) * 2.5
        + (total_bars * max(diameter, 1.0)) / width
    )


def status_from_candidate_util(util: float | None) -> str:
    if util is None or (isinstance(util, float) and math.isnan(util)):
        return "—"
    if util <= 1.0:
        return "NEAR LIMIT" if util >= 0.95 else "PASS"
    return "FAIL"


_SEARCH_CANDIDATE_UPDATE_KEYS: tuple[str, ...] = (
    "b",
    "bw",
    "tw",
    "D",
    "fc",
    "lig_d",
    "lig_legs",
    "s_lig",
    "bot_row_count",
    "bot1_layout_mode",
    "bot1_count",
    "db_bot_1",
    "bot2_layout_mode",
    "bot2_count",
    "db_bot_2",
    "bot_row_1_mode",
    "bot_row_1_bars",
    "bot_row_1_spacing",
    "bot_row_1_dia",
    "bot_row_2_mode",
    "bot_row_2_bars",
    "bot_row_2_spacing",
    "bot_row_2_dia",
)


def candidate_state_to_shared_updates(
    seed_state: Mapping[str, Any],
    candidate_state: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        key: candidate_state.get(key)
        for key in _SEARCH_CANDIDATE_UPDATE_KEYS
        if seed_state.get(key) != candidate_state.get(key)
    }


def compute_reo_complexity(candidate: Mapping[str, Any]) -> float:
    state = dict(candidate.get("state") or {})
    count_1 = int_from_state(
        state,
        "bot_row_1_bars",
        int_from_state(state, "bot1_count", 0),
    )
    count_2 = int_from_state(
        state,
        "bot_row_2_bars",
        int_from_state(state, "bot2_count", 0),
    )
    layer_imbalance = float(abs(count_1 - count_2)) if count_2 > 0 else 0.0
    return (
        int(candidate.get("bar_count", 0) or 0) * 1.0
        + int(candidate.get("row_count", 1) or 1) * 8.0
        + float(candidate.get("reo_congestion_index", 0.0) or 0.0) * 12.0
        + layer_imbalance * 3.0
    )


__all__ = [
    "bottom_bar_count",
    "bottom_row_count",
    "candidate_bottom_updates",
    "candidate_shear_updates",
    "candidate_state_to_shared_updates",
    "compute_reo_complexity",
    "int_from_state",
    "reo_congestion_index",
    "status_from_candidate_util",
]
