"""Pre-hydration shear-state normalisation with explicit dependencies."""

from __future__ import annotations

from typing import Any, Callable, Mapping, MutableMapping

from state_and_helpers import SHARED_DEFAULTS


CANONICAL_NO_SHEAR_SLIG_MM = 200.0
REO_BAR_DIAS = (10, 12, 16, 20, 24, 28, 32, 36, 40)
REO_SPACINGS = (75, 100, 125, 150, 175, 200, 225, 250, 275, 300)


def _int_value(state: Mapping[str, Any], key: str, default: int) -> int:
    try:
        value = state.get(key, default)
        return int(default if value is None else value)
    except Exception:
        return int(default)


def _float_value(state: Mapping[str, Any], key: str, default: float) -> float:
    try:
        value = state.get(key, default)
        return float(default if value is None else value)
    except Exception:
        return float(default)


def build_invalid_shear_state_updates(
    base_state: Mapping[str, Any],
    updates: Mapping[str, Any] | None = None,
    *,
    dev_mode: bool = False,
) -> dict[str, Any]:
    # Keep the router boundary on the same canonical engineering rule as the
    # widget callback and V2 adapter.  A second local implementation previously
    # allowed odd leg counts to survive hydration and crash BeamInputs.validated().
    from inputs_application.shear_state_normalization import (
        normalize_invalid_shear_state_updates,
    )

    return normalize_invalid_shear_state_updates(
        dict(base_state or {}),
        dict(updates or {}),
        source="app:router_pre_hydrate",
        dev_mode=dev_mode,
    )


def run_inputs_pre_hydrate_shear_normalization(
    session_state: MutableMapping[str, Any],
    *,
    set_shared_fn: Callable[..., None],
    source: str = "app:router_pre_hydrate",
) -> bool:
    current_state = {
        key: session_state.get(key, default)
        for key, default in SHARED_DEFAULTS.items()
    }
    updates = build_invalid_shear_state_updates(
        current_state,
        dev_mode=bool(session_state.get("_dev_mode")),
    )
    if not updates:
        return False
    for key, value in updates.items():
        set_shared_fn(key, value, source=source)
    session_state["_inputs_shear_shared_normalised_this_run"] = True
    return True


__all__ = [
    "build_invalid_shear_state_updates",
    "run_inputs_pre_hydrate_shear_normalization",
]
