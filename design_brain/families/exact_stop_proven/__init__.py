from __future__ import annotations

from typing import Any

from design_brain.shared.schemas import FamilyResult


FAMILY_ID = "EXACT_STOP_PROVEN"


def evaluate_exact_stop_proven(context: dict[str, Any]) -> FamilyResult:
    """Scaffold public API for the exact-stop-proven governing family."""

    raise NotImplementedError("EXACT_STOP_PROVEN is scaffolded; migration is pending.")


__all__ = ["FAMILY_ID", "evaluate_exact_stop_proven"]

