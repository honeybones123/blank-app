"""Typed contracts for cross-fragment summary handoffs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class InputsSummaryCalculationSource:
    """Immutable handoff from visible Summary rendering to Calculation."""

    bending_rows: tuple[dict[str, Any], ...]
    shear_rows: tuple[dict[str, Any], ...]
    crack_rows: tuple[dict[str, Any], ...]
    deflection_rows: tuple[dict[str, Any], ...]
    results_version: int
    summary_action_fp: Any


__all__ = ["InputsSummaryCalculationSource"]
