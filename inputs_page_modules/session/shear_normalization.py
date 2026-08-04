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
    resolved = dict(base_state or {})
    normalized = dict(updates or {})
    resolved.update(normalized)
    lig_legs = _int_value(resolved, "lig_legs", 0)
    lig_d = _int_value(resolved, "lig_d", 0)
    if lig_legs <= 0:
        normalized["lig_legs"] = 0
        normalized["lig_d"] = 0
        spacing = _float_value(
            resolved,
            "s_lig",
            CANONICAL_NO_SHEAR_SLIG_MM,
        )
        if abs(spacing - CANONICAL_NO_SHEAR_SLIG_MM) > 1e-9:
            normalized["s_lig"] = CANONICAL_NO_SHEAR_SLIG_MM
        return normalized
    if lig_legs >= 2 and lig_d <= 0:
        current_dia = _int_value(resolved, "lig_d", 0)
        starter_dia = current_dia if current_dia > 0 else next(
            (dia for dia in REO_BAR_DIAS if dia <= 16),
            10,
        )
        if dev_mode:
            assert starter_dia > 0, "Invalid shear state: ligatures active but diameter is zero"
        normalized["lig_d"] = int(starter_dia)
    spacing = _float_value(resolved, "s_lig", 0.0)
    if lig_legs >= 2 and spacing <= 0.0:
        current_spacing = _float_value(resolved, "s_lig", 0.0)
        if current_spacing > 0.0:
            starter_spacing = min(
                REO_SPACINGS,
                key=lambda value: abs(float(value) - current_spacing),
            )
        else:
            starter_spacing = 200.0 if 200 in REO_SPACINGS else REO_SPACINGS[len(REO_SPACINGS) // 2]
        normalized["s_lig"] = float(starter_spacing)
    return normalized


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
