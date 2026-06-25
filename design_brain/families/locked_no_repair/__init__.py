from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any

from design_brain.shared.schemas import FamilyResult


FAMILY_ID = "LOCKED_NO_REPAIR"


def _load_legacy_locked_no_repair_family() -> type:
    legacy_path = Path(__file__).resolve().parent.parent / "locked_no_repair.py"
    spec = importlib.util.spec_from_file_location(
        "design_brain.families._legacy_locked_no_repair",
        legacy_path,
    )
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load legacy locked_no_repair module from {legacy_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.LockedNoRepairFamily


LockedNoRepairFamily = _load_legacy_locked_no_repair_family()


def evaluate_locked_no_repair(context: dict[str, Any]) -> FamilyResult:
    """Scaffold public API for the locked/no-repair governing family."""

    raise NotImplementedError("LOCKED_NO_REPAIR is scaffolded; migration is pending.")


__all__ = ["FAMILY_ID", "LockedNoRepairFamily", "evaluate_locked_no_repair"]
