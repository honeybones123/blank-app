"""Bending calculation fact and authoritative summary boundaries."""

from typing import Any, Dict

from calculations.bending import compute_bending_capacity_from_state_values
from inputs_application.authoritative_check_packs import (
    authoritative_check_pack_or_unavailable,
)


def compute_bending_capacity_from_state(st_state: Dict[str, Any]) -> Dict[str, Any]:
    """Pure candidate-evaluation fact retained for the Design Brain adapter."""

    lig_diameter_mm = float(st_state.get("lig_d", 0.0) or 0.0)
    return compute_bending_capacity_from_state_values(
        st_state,
        lig_diameter_mm=lig_diameter_mm,
    )


def build_bending_check_rows_from_state(st_state: Dict[str, Any]) -> Dict[str, Any]:
    """Project the current V2 result; never run the legacy page calculator."""

    return authoritative_check_pack_or_unavailable(st_state, "bending")


__all__ = [
    "build_bending_check_rows_from_state",
    "compute_bending_capacity_from_state",
]
