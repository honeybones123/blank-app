"""Pure candidate-state delta policy owned by the application layer."""

from __future__ import annotations

from typing import Any


def diff_candidate_state_updates(
    base_state: dict[str, Any] | None,
    final_state: dict[str, Any] | None,
) -> dict[str, Any]:
    """Return a plain update diff from base state to final candidate state."""

    base = dict(base_state or {})
    delta: dict[str, Any] = {}
    for key, value in dict(final_state or {}).items():
        if key not in base:
            delta[key] = value
            continue
        base_value = base[key]
        if isinstance(value, float) or isinstance(base_value, float):
            try:
                if abs(float(base_value) - float(value)) > 1e-9:
                    delta[key] = value
            except (TypeError, ValueError):
                if base_value != value:
                    delta[key] = value
        elif base_value != value:
            delta[key] = value
    return delta


__all__ = ["diff_candidate_state_updates"]
