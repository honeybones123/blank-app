"""Small engineering predicates used by application orchestration."""

from __future__ import annotations

from typing import Any, Mapping

from inputs_application.policy_constants import (
    GUIDANCE_SHEAR_DEMAND_ABS_TOL_KN,
    GUIDANCE_TORSION_DEMAND_ABS_TOL_KNM,
)


def parse_util_value(value: Any) -> float | None:
    if value in (None, "", "—"):
        return None
    try:
        return float(value)
    except Exception:
        try:
            return float(str(value).strip())
        except Exception:
            return None


def shear_reinforcement_is_active(state: Mapping[str, Any] | None) -> bool:
    if not isinstance(state, Mapping):
        return False
    try:
        return (
            int(state.get("lig_legs", 0) or 0) >= 2
            and int(state.get("lig_d", 0) or 0) > 0
            and float(state.get("s_lig", 0.0) or 0.0) > 0.0
        )
    except (TypeError, ValueError):
        return False


def shear_demands_negligible(actions: Mapping[str, Any] | None) -> bool:
    if not isinstance(actions, Mapping):
        return False
    try:
        vu = abs(float(actions.get("Vu", 0.0) or 0.0))
        tu = abs(float(actions.get("Tu", 0.0) or 0.0))
    except (TypeError, ValueError):
        return False
    return (
        vu <= GUIDANCE_SHEAR_DEMAND_ABS_TOL_KN + 1e-12
        and tu <= GUIDANCE_TORSION_DEMAND_ABS_TOL_KNM + 1e-12
    )


__all__ = [
    "parse_util_value",
    "shear_demands_negligible",
    "shear_reinforcement_is_active",
]
