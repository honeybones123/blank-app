"""Application-owned target-band refinement candidate selection."""

from __future__ import annotations

import math
from typing import Any, Callable

from application.candidate_delta_policy import diff_candidate_state_updates
from application.target_band_domain_policy import resolve_target_band_candidate_domains_for_updates
from application.target_band_evaluation import (
    resolve_candidate_step_improves,
    resolve_candidate_target_band_distance,
)


def build_target_band_refinement_payload_if_valid(
    *,
    candidate_state: dict[str, Any] | None,
    candidate_eval: dict[str, Any] | None,
    candidate_updates: dict[str, Any] | None,
    current_eval: dict[str, Any] | None,
    current_distance: Any,
    mode_config: dict[str, Any] | None,
    spacing_envelope_fail: bool = False,
    default_target_min: float,
    default_target_max: float,
    fail_status: str = "FAIL",
    optimisation_goal_resolver: Callable[[dict[str, Any]], str] | None = None,
    improvement_margin: float = 1e-9,
) -> dict[str, Any] | None:
    if not isinstance(candidate_eval, dict):
        return None
    overview = dict(candidate_eval.get("overview") or {})
    if not bool(overview.get("all_key_pass")) or bool(spacing_envelope_fail):
        return None
    candidate_distance = resolve_candidate_target_band_distance(
        candidate_eval,
        mode_config,
        default_target_min=default_target_min,
        default_target_max=default_target_max,
        fail_status=fail_status,
        optimisation_goal_resolver=optimisation_goal_resolver,
    )
    try:
        resolved_candidate_distance = float(candidate_distance)
        resolved_current_distance = float(current_distance)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(resolved_candidate_distance):
        return None
    if resolved_candidate_distance + float(improvement_margin) >= resolved_current_distance:
        return None
    if not resolve_candidate_step_improves(
        candidate_eval,
        current_eval,
        mode_config,
        default_target_min=default_target_min,
        default_target_max=default_target_max,
        fail_status=fail_status,
        optimisation_goal_resolver=optimisation_goal_resolver,
    ):
        return None
    return {
        "state": dict(candidate_state or {}),
        "eval": candidate_eval,
        "distance": resolved_candidate_distance,
        "updates": dict(candidate_updates or {}),
    }


def select_target_band_best_refinement_payload(
    current_best: dict[str, Any] | None,
    candidate_payload: dict[str, Any] | None,
    *,
    improvement_margin: float = 1e-9,
) -> dict[str, Any] | None:
    if not isinstance(candidate_payload, dict):
        return dict(current_best) if isinstance(current_best, dict) else None
    if not isinstance(current_best, dict):
        return dict(candidate_payload)
    try:
        candidate_distance = float(candidate_payload.get("distance"))
        current_distance = float(current_best.get("distance"))
    except (TypeError, ValueError):
        return dict(current_best)
    if candidate_distance < current_distance - float(improvement_margin):
        return dict(candidate_payload)
    return dict(current_best)


def select_best_target_band_refinement_candidate(
    *,
    candidate_states: list[dict[str, Any]] | tuple[dict[str, Any], ...],
    current_eval: dict[str, Any] | None,
    current_state: dict[str, Any] | None,
    current_distance: Any,
    current_target_domains: list[str] | tuple[str, ...] | set[str] | None,
    mode_config: dict[str, Any] | None,
    state_pack_fn: Callable[[dict[str, Any]], dict[str, Any]],
    evaluator_fn: Callable[..., dict[str, Any] | None],
    target_domain_attachment_fn: Callable[[dict[str, Any], list[str], dict[str, Any] | None], None],
    spacing_envelope_fail_fn: Callable[[dict[str, Any]], bool],
    source: str,
    label: str,
    action_type: str,
    default_target_min: float,
    default_target_max: float,
    fail_status: str = "FAIL",
    optimisation_goal_resolver: Callable[[dict[str, Any]], str] | None = None,
) -> dict[str, Any] | None:
    best_payload: dict[str, Any] | None = None
    base_state = dict(current_state or {})
    base_domains = list(current_target_domains or [])
    for candidate_state_raw in list(candidate_states or []):
        candidate_state = dict(candidate_state_raw or {})
        candidate_eval = evaluator_fn(
            state_pack_fn(candidate_state),
            source=source,
            label=label,
            action_type=action_type,
            updates={},
        )
        if not isinstance(candidate_eval, dict):
            continue
        candidate_updates = diff_candidate_state_updates(base_state, candidate_state)
        if base_domains:
            candidate_target_domains = resolve_target_band_candidate_domains_for_updates(
                base_domains,
                candidate_updates,
            )
            target_domain_attachment_fn(candidate_eval, candidate_target_domains, mode_config)
        payload = build_target_band_refinement_payload_if_valid(
            candidate_state=candidate_state,
            candidate_eval=candidate_eval,
            candidate_updates=candidate_updates,
            current_eval=current_eval,
            current_distance=current_distance,
            mode_config=mode_config,
            spacing_envelope_fail=bool(spacing_envelope_fail_fn(candidate_eval)),
            default_target_min=default_target_min,
            default_target_max=default_target_max,
            fail_status=fail_status,
            optimisation_goal_resolver=optimisation_goal_resolver,
        )
        if payload is not None:
            best_payload = select_target_band_best_refinement_payload(best_payload, payload)
    return best_payload


__all__ = [
    "build_target_band_refinement_payload_if_valid",
    "select_best_target_band_refinement_candidate",
    "select_target_band_best_refinement_payload",
]
