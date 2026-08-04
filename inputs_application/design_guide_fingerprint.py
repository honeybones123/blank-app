"""Canonical Design Guide cache identity owned outside the legacy bridge."""

from __future__ import annotations

from typing import Any, Mapping

from application.contracts.design_policy import (
    DESIGN_OPTIMISATION_GOAL_LABELS,
    resolve_design_optimisation_goal,
)
from calculations.design_actions import resolve_design_actions_from_state as resolve_design_actions


DESIGN_GUIDE_ALGORITHM_VERSION = "shear_congestion_reshape_v2"
DESIGN_GUIDE_CACHE_SCHEMA = "dg_cache_v2026_04_27_in_target_local_cleanup_all_families"


def build_design_guide_fingerprint(state: Mapping[str, Any] | None = None) -> tuple:
    current_state = dict(state or {})
    return (
        DESIGN_GUIDE_CACHE_SCHEMA,
        DESIGN_GUIDE_ALGORITHM_VERSION,
        str(
            resolve_design_optimisation_goal(
                current_state,
                goal_labels=DESIGN_OPTIMISATION_GOAL_LABELS,
                default_goal="balanced",
            )
        ),
        str(current_state.get("sec_shape")),
        float(current_state.get("b", 0.0) or 0.0),
        float(current_state.get("D", 0.0) or 0.0),
        float(current_state.get("fc", 0.0) or 0.0),
        float(current_state.get("fsy", 0.0) or 0.0),
        float(current_state.get("uls_Mstar", 0.0) or 0.0),
        float(current_state.get("uls_Vstar", 0.0) or 0.0),
        float(current_state.get("uls_Nstar", 0.0) or 0.0),
        float(current_state.get("Tu_star", 0.0) or 0.0),
        int(current_state.get("bot_row_count", 0) or 0),
        int(current_state.get("bot1_count", 0) or 0),
        float(current_state.get("db_bot_1", 0.0) or 0.0),
        int(current_state.get("bot2_count", 0) or 0),
        float(current_state.get("db_bot_2", 0.0) or 0.0),
        float(current_state.get("lig_d", 0.0) or 0.0),
        int(current_state.get("lig_legs", 0) or 0),
        float(current_state.get("s_lig", 0.0) or 0.0),
        tuple(resolve_design_actions(current_state).get("signature", ())),
    )


design_guide_fingerprint = build_design_guide_fingerprint


__all__ = [
    "DESIGN_GUIDE_ALGORITHM_VERSION",
    "DESIGN_GUIDE_CACHE_SCHEMA",
    "build_design_guide_fingerprint",
    "design_guide_fingerprint",
]
