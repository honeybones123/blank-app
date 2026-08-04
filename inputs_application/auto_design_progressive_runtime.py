"""Typed progressive auto-design candidate construction and evaluation."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Callable

from inputs_application.candidate_metrics import int_from_state
from inputs_application.recommendation_support import (
    resolve_geometry_width_context,
)
from inputs_application.state_utils import float_from_state


@dataclass(frozen=True)
class ProgressiveAutoDesignRuntime:
    auto_design_target_util: float
    collect_failures: Callable[[dict], list[tuple[str, float]]]
    choose_strategy: Callable[[list[tuple[str, float]]], str]
    evaluate_full: Callable[..., dict | None]
    guidance_state_snapshot: Callable[[dict], dict]


def _apply_bottom_bar_count_update(
    candidate: dict,
    state: dict,
    new_total: int,
) -> None:
    current_second_row = int_from_state(state, "bot2_count", 0)
    if current_second_row > 0:
        new_first_row = max(2, int(math.ceil(new_total / 2.0)))
        new_second_row = max(0, int(new_total - new_first_row))
    else:
        new_first_row = max(2, int(new_total))
        new_second_row = 0
    candidate["bot1_count"] = int(new_first_row)
    candidate["bot2_count"] = int(new_second_row)
    candidate["bot_row_count"] = 2 if new_second_row > 0 else 1
    candidate["nb_bot"] = int(new_first_row + new_second_row)


def build_progressive_candidate(
    state: dict,
    strategy: str,
    results: dict,
    *,
    runtime: ProgressiveAutoDesignRuntime,
) -> dict:
    candidate: dict[str, object] = {}
    bending_util = (results.get("bending") or {}).get("util")
    row_count = int(results.get("row_count", 1) or 1)
    width_key, _, current_width = resolve_geometry_width_context(state)
    current_depth = float_from_state(state, "D", 600.0)
    current_total_bottom = max(
        int_from_state(state, "bot1_count", 0)
        + int_from_state(state, "bot2_count", 0),
        int_from_state(state, "nb_bot", 0),
        2,
    )
    if strategy == "increase_capacity":
        utilisation_ratio = 1.05
        try:
            if bending_util is not None:
                utilisation_ratio = max(
                    float(bending_util)
                    / float(runtime.auto_design_target_util),
                    1.02,
                )
        except Exception:
            utilisation_ratio = 1.05
        suggested_total = max(
            current_total_bottom + 1,
            int(math.ceil(current_total_bottom * utilisation_ratio)),
        )
        _apply_bottom_bar_count_update(
            candidate,
            state,
            suggested_total,
        )
        depth_multiplier = 1.05
        try:
            if bending_util is not None and float(bending_util) > 1.2:
                depth_multiplier = 1.10
        except Exception:
            pass
        candidate["D"] = float(current_depth * depth_multiplier)
    elif strategy == "increase_depth":
        candidate["D"] = float(current_depth * 1.10)
    elif strategy == "increase_shear":
        current_spacing = float_from_state(state, "s_lig", 200.0)
        candidate["s_lig"] = float(max(75.0, current_spacing * 0.7))
        candidate["lig_legs"] = int(
            max(int_from_state(state, "lig_legs", 2), 2)
        )
    elif strategy == "optimise":
        _apply_bottom_bar_count_update(
            candidate,
            state,
            max(2, current_total_bottom - 1),
        )
    if row_count > 3:
        candidate[width_key] = float(current_width * 1.10)
        if width_key != "b":
            candidate["b"] = float(current_width * 1.10)
    return candidate


def run_progressive_auto_design_step(
    state: dict,
    results: dict,
    *,
    runtime: ProgressiveAutoDesignRuntime,
) -> tuple[dict | None, list[tuple[str, float]], str]:
    failures = runtime.collect_failures(results)
    if not failures:
        return None, failures, "optimise"
    strategy = runtime.choose_strategy(failures)
    candidate = build_progressive_candidate(
        state,
        strategy,
        results,
        runtime=runtime,
    )
    if not candidate:
        return None, failures, strategy
    return candidate, failures, strategy


def evaluate_progressive_candidate_update(
    state: dict,
    updates: dict,
    *,
    pass_idx: int,
    candidate_type: str,
    runtime: ProgressiveAutoDesignRuntime,
) -> dict | None:
    if not updates:
        return None
    trial_state = dict(state)
    trial_state.update(updates)
    evaluated = runtime.evaluate_full(
        runtime.guidance_state_snapshot(trial_state),
        source=f"progressive_auto_design_pass_{int(pass_idx)}",
        label=f"Progressive {candidate_type}",
        action_type="auto_design",
        updates=dict(updates),
    )
    if not isinstance(evaluated, dict):
        return None
    candidate = dict(evaluated)
    candidate["state"] = dict(candidate.get("state") or trial_state)
    candidate["updates"] = dict(updates)
    candidate["candidate_type"] = str(candidate_type)
    candidate["candidate_priority"] = {
        "compound": 0,
        "geometry": 1,
        "reo": 2,
    }.get(str(candidate_type), 9)
    candidate.setdefault(
        "label",
        f"Progressive {candidate_type} update",
    )
    return candidate


__all__ = [
    "ProgressiveAutoDesignRuntime",
    "build_progressive_candidate",
    "evaluate_progressive_candidate_update",
    "run_progressive_auto_design_step",
]
