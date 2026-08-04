"""Typed final and next-hop candidate selection for auto design."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class AutoDesignFinalSelectionRuntime:
    candidate_is_good_enough: Callable[..., bool]
    candidate_materially_worsens: Callable[..., bool]
    candidate_sort_key_for_mode: Callable[..., tuple]
    shallower_beam_selection_key: Callable[..., tuple]
    utilisation_gap: Callable[[dict, dict], float]


def select_final_candidate(
    results: list[dict],
    mode_config: dict,
    baseline_candidate: dict | None = None,
    *,
    runtime: AutoDesignFinalSelectionRuntime,
) -> dict | None:
    filtered = [
        result
        for result in results
        if result
        and not (
            baseline_candidate is not None
            and runtime.candidate_materially_worsens(
                result,
                baseline_candidate,
                mode_config,
                phase="final",
            )
        )
    ]
    if not filtered:
        return baseline_candidate
    strategy = str(
        mode_config.get("search_strategy", "balanced") or "balanced"
    )
    in_zone = [
        result
        for result in filtered
        if bool(result.get("is_compliant"))
        and runtime.candidate_is_good_enough(result, mode_config)
    ]
    if in_zone:
        if strategy == "shallow" and baseline_candidate is not None:
            return min(
                in_zone,
                key=lambda item: (
                    runtime.shallower_beam_selection_key(
                        item,
                        baseline_candidate,
                        mode_config,
                    ),
                    runtime.candidate_sort_key_for_mode(
                        item,
                        mode_config,
                    ),
                    item.get("score", float("inf")),
                ),
            )
        return min(
            in_zone,
            key=lambda item: (
                runtime.candidate_sort_key_for_mode(item, mode_config),
                item.get("score", float("inf")),
            ),
        )
    compliant = [
        result for result in filtered if bool(result.get("is_compliant"))
    ]
    if compliant:
        if strategy == "shallow" and baseline_candidate is not None:
            return min(
                compliant,
                key=lambda item: (
                    runtime.shallower_beam_selection_key(
                        item,
                        baseline_candidate,
                        mode_config,
                    ),
                    runtime.utilisation_gap(item, mode_config),
                    runtime.candidate_sort_key_for_mode(
                        item,
                        mode_config,
                    ),
                    item.get("score", float("inf")),
                ),
            )
        return min(
            compliant,
            key=lambda item: (
                runtime.utilisation_gap(item, mode_config),
                runtime.candidate_sort_key_for_mode(item, mode_config),
                item.get("score", float("inf")),
            ),
        )
    return min(
        filtered,
        key=lambda item: (
            int(item.get("fail_count", 0) or 0),
            float(item.get("worst_util", float("inf")) or float("inf")),
            runtime.candidate_sort_key_for_mode(item, mode_config),
            item.get("score", float("inf")),
        ),
    )


def select_best_next_hop_candidate(
    current_result: dict,
    candidate_results: list[dict],
    mode_config: dict,
    *,
    phase: str,
    runtime: AutoDesignFinalSelectionRuntime,
) -> dict | None:
    viable = [
        result
        for result in candidate_results
        if result
        and not runtime.candidate_materially_worsens(
            result,
            current_result,
            mode_config,
            phase=phase,
        )
    ]
    if not viable:
        return None
    if phase == "solve_to_pass" and not bool(
        current_result.get("is_compliant")
    ):
        return min(
            viable,
            key=lambda item: (
                0 if bool(item.get("is_compliant")) else 1,
                int(item.get("fail_count", 0) or 0),
                float(item.get("worst_util", 999.0) or 999.0),
                runtime.candidate_sort_key_for_mode(item, mode_config),
                float(item.get("score", 0.0) or 0.0),
            ),
        )
    return min(
        viable,
        key=lambda item: (
            runtime.candidate_sort_key_for_mode(item, mode_config),
            float(item.get("score", 0.0) or 0.0),
        ),
    )


__all__ = [
    "AutoDesignFinalSelectionRuntime",
    "select_best_next_hop_candidate",
    "select_final_candidate",
]
