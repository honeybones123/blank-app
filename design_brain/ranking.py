"""Design Brain candidate ranking helpers.

This module owns pure score tuple construction and target-band proximity
scoring. It does not search, generate candidates, evaluate formulas, apply
updates, or render UI.
"""

from __future__ import annotations

from typing import Any


def _as_float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def distance_to_band(util: float | None, lo: float, hi: float) -> float | None:
    if util is None:
        return None
    if lo <= util <= hi:
        return 0.0
    if util < lo:
        return float(lo - util)
    return float(util - hi)


def selection_sort_key(candidate: dict, target_low: float, target_high: float) -> tuple:
    preview = _as_float(candidate.get("preview_util"))
    target_mid = (float(target_low) + float(target_high)) / 2.0
    return (
        float(candidate.get("distance_to_target_band") if candidate.get("distance_to_target_band") is not None else 1e9),
        abs(float(preview) - target_mid) if preview is not None else 1e9,
        len(dict(candidate.get("updates") or {})),
        str(candidate.get("title") or ""),
        str(candidate.get("candidate_id") or ""),
    )
