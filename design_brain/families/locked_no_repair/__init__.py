from __future__ import annotations

from typing import Any

from design_brain.shared.schemas import FamilyResult
from .strategy import LockedNoRepairFamily


FAMILY_ID = "LOCKED_NO_REPAIR"


def evaluate_locked_no_repair(context: dict[str, Any]) -> FamilyResult:
    """Scaffold public API for the locked/no-repair governing family."""

    raise NotImplementedError("LOCKED_NO_REPAIR is scaffolded; migration is pending.")


__all__ = ["FAMILY_ID", "LockedNoRepairFamily", "evaluate_locked_no_repair"]
