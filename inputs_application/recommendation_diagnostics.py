"""Typed diagnostic emitters for Inputs recommendations."""

from __future__ import annotations

from typing import Any, Callable

from inputs_application.engineering_predicates import (
    shear_reinforcement_is_active,
)
from inputs_application.recommendation_evaluation import evaluate_shear_with_state
from inputs_application.state_utils import float_from_state


def _int_from_state(state: dict, key: str, default: int) -> int:
    try:
        return int(float(state.get(key, default) or 0))
    except (TypeError, ValueError):
        return int(default)


def log_shear_candidate_debug(
    *,
    source: str,
    candidate_state: dict,
    candidate: dict | None,
    agent_debug_log: Callable[..., Any],
    enabled: bool,
) -> None:
    if not enabled:
        return
    shear_preview = evaluate_shear_with_state(candidate_state) or {}
    phi_vu = 0.0
    equivalent_shear = 0.0
    try:
        results = shear_preview.get("results")
        phi_vu = float(getattr(results, "phi_Vu", 0.0) or 0.0)
        equivalent_shear = float(getattr(results, "V_eq", 0.0) or 0.0)
    except Exception:
        phi_vu = 0.0
        equivalent_shear = 0.0
    agent_debug_log(
        "Shear candidate debug",
        {
            "source": source,
            "lig_legs": _int_from_state(candidate_state, "lig_legs", 0),
            "lig_d": _int_from_state(candidate_state, "lig_d", 0),
            "s_lig": float_from_state(candidate_state, "s_lig", 0.0),
            "shear_reinforcement_active": shear_reinforcement_is_active(
                candidate_state
            ),
            "phiVu": phi_vu,
            "Veq": equivalent_shear,
            "shear_util": (
                float(shear_preview.get("util", 0.0) or 0.0)
                if shear_preview
                else None
            ),
            "candidate_score": (
                None if candidate is None else candidate.get("score")
            ),
        },
        location="inputs_page.py:shear_candidate_debug",
        hypothesis_id="H_SHEAR_DEBUG",
    )


def log_shear_ladder_attempt(
    state: dict,
    *,
    ladder_mode: str,
    branch: str,
    lig_legs: int,
    s_lig: float,
    proposed_updates: dict | None,
    expected_util_after: float | None,
    decision: str,
    reason: str,
    agent_debug_log: Callable[..., Any],
    enabled: bool = True,
) -> None:
    if not enabled:
        return
    agent_debug_log(
        "Shear ladder candidate",
        {
            "ladder_mode": ladder_mode,
            "branch": branch,
            "current_lig_legs": lig_legs,
            "current_s_lig": s_lig,
            "proposed_updates": proposed_updates,
            "expected_util_after": expected_util_after,
            "decision": decision,
            "reason": reason,
        },
        location="inputs_page.py:_compute_shear_recommendation:ladder",
        hypothesis_id="H_SHEAR_LADDER",
    )


__all__ = ["log_shear_candidate_debug", "log_shear_ladder_attempt"]
