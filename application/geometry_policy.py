"""Application-owned primitive geometry policy."""

from __future__ import annotations

from typing import Any


MAXIMUM_PREFERRED_DEPTH_WIDTH_RATIO = 2.0


def bending_depth_width_ratio_limit() -> float:
    """Return the contract-owned maximum preferred depth/width ratio."""

    return MAXIMUM_PREFERRED_DEPTH_WIDTH_RATIO


def depth_width_ratio(*, width: float, depth: float) -> float | None:
    """Return D/b for explicit primitive geometry values."""

    try:
        width_f = float(width)
        depth_f = float(depth)
    except (TypeError, ValueError):
        return None
    if width_f <= 0.0 or depth_f <= 0.0:
        return None
    return depth_f / width_f


__all__ = [
    "MAXIMUM_PREFERRED_DEPTH_WIDTH_RATIO",
    "bending_depth_width_ratio_limit",
    "depth_width_ratio",
]
