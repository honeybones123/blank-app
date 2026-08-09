"""Session-backed cache for on-demand Inputs recommendations."""

from __future__ import annotations

import json
from typing import Any, Callable

from calculations.design_actions import resolve_design_actions_from_state as resolve_design_actions
from state_and_helpers import SHARED_DEFAULTS
from inputs_application.recommendation_store import RecommendationStore


def recommendation_cache_fingerprint(state: dict[str, Any]) -> str:
    fingerprint_state = {
        key: state.get(key, default)
        for key, default in SHARED_DEFAULTS.items()
    }
    fingerprint_state["_resolved_design_actions"] = resolve_design_actions(state)
    try:
        return json.dumps(fingerprint_state, sort_keys=True, default=str)
    except Exception:
        return str(sorted((str(key), str(value)) for key, value in fingerprint_state.items()))


def resolve_popover_recommendation(
    *,
    st_module: Any,
    cache_name: str,
    state: dict[str, Any],
    button_key: str,
    compute_fn: Callable[[dict[str, Any]], dict[str, Any] | None],
    empty_message: str,
) -> dict[str, Any] | None:
    recommendation_store = RecommendationStore(st_module.session_state)
    fingerprint = recommendation_cache_fingerprint(state)
    cache_entry = recommendation_store.get(cache_name, fingerprint=fingerprint)
    recommendation = cache_entry.get("recommendation") if cache_entry else None
    generate_pressed = st_module.button(
        "Generate current recommendation" if recommendation is None else "Refresh recommendation",
        key=f"{button_key}_generate",
        type="secondary",
        width="stretch",
    )
    if generate_pressed:
        recommendation = compute_fn(state)
        recommendation_store.put(
            cache_name,
            fingerprint=fingerprint,
            recommendation=recommendation,
        )
    if recommendation is None:
        st_module.caption(empty_message)
    return recommendation


__all__ = [
    "RecommendationStore",
    "recommendation_cache_fingerprint",
    "resolve_popover_recommendation",
]
