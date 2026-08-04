from __future__ import annotations

from typing import Any

from design_brain.shared.schemas import FamilyResult


FAMILY_ID = "TARGET_BAND_REACHED"


def evaluate_target_band_reached(context: dict[str, Any]) -> FamilyResult:
    """Scaffold public API for the target-band-reached governing family."""

    raise NotImplementedError("TARGET_BAND_REACHED is scaffolded; migration is pending.")


__all__ = ["FAMILY_ID", "evaluate_target_band_reached"]

