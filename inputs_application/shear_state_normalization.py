"""Canonical normalization for Inputs shear-reinforcement state."""

from __future__ import annotations

from inputs_application.candidate_metrics import int_from_state
from inputs_application.state_utils import float_from_state


CANONICAL_NO_SHEAR_SPACING_MM = 200.0
PRACTICAL_SHEAR_DIAMETERS = (10, 12, 16)
PRACTICAL_SHEAR_SPACINGS = (75, 100, 125, 150, 175, 200, 225, 250, 275, 300)
# Runtime UI normalization must remain importable before the bundled V2
# package is loaded by the adapter.  This tuple mirrors the V2 domain contract
# and is guarded by cross-boundary tests.
SUPPORTED_SHEAR_LEG_COUNTS = (2, 3, 4, 5, 6, 8)


def _supported_shear_legs(value: int) -> int:
    """Return the smallest supported arrangement that does not reduce legs."""

    if value < 2:
        return 0
    return next(
        (candidate for candidate in SUPPORTED_SHEAR_LEG_COUNTS if candidate >= value),
        SUPPORTED_SHEAR_LEG_COUNTS[-1],
    )


def normalize_shear_link_pair(
    state: dict,
    *,
    changed_key: str | None = None,
) -> dict[str, int]:
    """Return an atomic, valid diameter/leg pair for a UI selection.

    The two selectboxes are one engineering input.  A rerun must never expose
    the intermediate ``diameter > 0, legs == 0`` (or inverse) state to the
    calculation adapter.
    """

    diameter = int_from_state(state, "lig_d", 0)
    legs = _supported_shear_legs(int_from_state(state, "lig_legs", 0))
    changed = str(changed_key or "").strip()

    if changed == "lig_d":
        if diameter <= 0:
            return {"lig_d": 0, "lig_legs": 0}
        return {"lig_d": diameter, "lig_legs": max(legs, 2)}

    if changed == "lig_legs":
        if legs < 2:
            return {"lig_d": 0, "lig_legs": 0}
        return {
            "lig_d": diameter if diameter > 0 else PRACTICAL_SHEAR_DIAMETERS[0],
            "lig_legs": legs,
        }

    if diameter <= 0 and legs < 2:
        return {"lig_d": 0, "lig_legs": 0}
    if diameter > 0 and legs < 2:
        return {"lig_d": diameter, "lig_legs": 2}
    if diameter <= 0 and legs >= 2:
        return {"lig_d": PRACTICAL_SHEAR_DIAMETERS[0], "lig_legs": legs}
    return {"lig_d": diameter, "lig_legs": legs}


def _starter_shear_diameter(state: dict) -> int:
    current = int_from_state(state, "lig_d", 0)
    return current if current > 0 else PRACTICAL_SHEAR_DIAMETERS[0]


def _starter_shear_spacing(state: dict) -> float:
    current = float_from_state(state, "s_lig", 0.0)
    if current > 0.0:
        return float(
            min(
                PRACTICAL_SHEAR_SPACINGS,
                key=lambda value: abs(float(value) - current),
            )
        )
    return CANONICAL_NO_SHEAR_SPACING_MM


def normalize_invalid_shear_state_updates(
    base_state: dict,
    updates: dict,
    *,
    source: str = "",
    dev_mode: bool = False,
) -> dict:
    del source
    resolved_state = dict(base_state or {})
    normalized = dict(updates or {})
    resolved_state.update(normalized)
    raw_legs = int_from_state(resolved_state, "lig_legs", 0)
    legs = _supported_shear_legs(raw_legs)
    diameter = int_from_state(resolved_state, "lig_d", 0)
    if legs != raw_legs:
        normalized["lig_legs"] = legs
    if legs <= 0:
        normalized["lig_legs"] = 0
        normalized["lig_d"] = 0
        spacing = float_from_state(
            resolved_state,
            "s_lig",
            CANONICAL_NO_SHEAR_SPACING_MM,
        )
        if abs(spacing - CANONICAL_NO_SHEAR_SPACING_MM) > 1e-9:
            normalized["s_lig"] = CANONICAL_NO_SHEAR_SPACING_MM
        return normalized
    if legs >= 2 and diameter <= 0:
        starter_diameter = _starter_shear_diameter(resolved_state)
        if dev_mode:
            assert starter_diameter > 0
        normalized["lig_d"] = starter_diameter
    spacing = float_from_state(resolved_state, "s_lig", 0.0)
    if legs >= 2 and spacing <= 0.0:
        normalized["s_lig"] = _starter_shear_spacing(resolved_state)
    return normalized


__all__ = [
    "SUPPORTED_SHEAR_LEG_COUNTS",
    "normalize_invalid_shear_state_updates",
    "normalize_shear_link_pair",
]
