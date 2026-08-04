"""Pure BENDING_FAIL_GOVERNS depth/width ratio policy helpers."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from design_brain.families.bending_fail_governs.contract import depth_width_rule


@dataclass(frozen=True)
class BendingDepthWidthGuardResult:
    """Pure result for a generated geometry update checked against the contract."""

    updates: dict[str, Any]
    blocked: bool
    rescued: bool
    reason: str | None
    depth_width_ratio: float | None
    maximum_depth_width_ratio: float
    required_width: float | None


def bending_depth_width_ratio_limit() -> float:
    """Return the contract-owned maximum preferred depth/width ratio."""

    try:
        return float(depth_width_rule().get("maximum_preferred_ratio") or 2.0)
    except Exception:
        return 2.0


def depth_width_ratio(*, width: float, depth: float) -> float | None:
    """Return D/b for explicit primitive geometry surfaces."""

    try:
        width_f = float(width)
        depth_f = float(depth)
    except (TypeError, ValueError):
        return None
    if width_f <= 0.0 or depth_f <= 0.0:
        return None
    return depth_f / width_f


def depth_width_ratio_exceeds_contract(*, width: float, depth: float) -> bool:
    """Return whether explicit geometry exceeds the contract-owned ratio."""

    ratio = depth_width_ratio(width=width, depth=depth)
    return ratio is not None and ratio > bending_depth_width_ratio_limit() + 1e-9


def guard_bending_depth_width_geometry_update(
    *,
    current_width: float,
    current_depth: float,
    updates: dict[str, Any],
    width_update_key: str,
    width_locked: bool,
    allow_width_rescue: bool,
    minimum_practical_width: float,
) -> BendingDepthWidthGuardResult:
    """Apply the contract ratio to explicit geometry update primitives.

    The helper owns the policy. Callers own extraction of live state and key names.
    """

    out = dict(updates or {})
    limit = bending_depth_width_ratio_limit()
    depth = float(current_depth or 0.0)
    if "D" in out:
        try:
            depth = float(out.get("D"))
        except (TypeError, ValueError):
            depth = float(current_depth or 0.0)
    width = float(current_width or 0.0)
    for candidate_key in (width_update_key, "b", "beam_width", "beam_b", "width"):
        if candidate_key in out:
            try:
                width = float(out.get(candidate_key))
            except (TypeError, ValueError):
                width = float(current_width or 0.0)
            break

    ratio = depth_width_ratio(width=width, depth=depth)
    if ratio is None or ratio <= limit + 1e-9:
        return BendingDepthWidthGuardResult(
            updates=out,
            blocked=False,
            rescued=False,
            reason=None,
            depth_width_ratio=ratio,
            maximum_depth_width_ratio=limit,
            required_width=None,
        )

    if width_locked or not allow_width_rescue:
        return BendingDepthWidthGuardResult(
            updates={},
            blocked=True,
            rescued=False,
            reason="depth_width_ratio_above_contract_limit",
            depth_width_ratio=ratio,
            maximum_depth_width_ratio=limit,
            required_width=None,
        )

    required_width = float(
        int(math.ceil(max(float(minimum_practical_width), depth / limit) / 10.0) * 10)
    )
    if required_width <= width + 1e-9:
        return BendingDepthWidthGuardResult(
            updates=out,
            blocked=False,
            rescued=False,
            reason=None,
            depth_width_ratio=ratio,
            maximum_depth_width_ratio=limit,
            required_width=required_width,
        )

    out[width_update_key] = required_width
    if width_update_key != "b":
        out["b"] = required_width
    rescued_ratio = depth_width_ratio(width=required_width, depth=depth)
    return BendingDepthWidthGuardResult(
        updates=out,
        blocked=False,
        rescued=True,
        reason="width_rescued_depth_width_ratio",
        depth_width_ratio=rescued_ratio,
        maximum_depth_width_ratio=limit,
        required_width=required_width,
    )


__all__ = [
    "BendingDepthWidthGuardResult",
    "bending_depth_width_ratio_limit",
    "depth_width_ratio",
    "depth_width_ratio_exceeds_contract",
    "guard_bending_depth_width_geometry_update",
]
