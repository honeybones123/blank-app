"""Canonical project geometry limits for Design Brain search ladders.

These are engineering-search boundaries, not UI widget limits.  Family
runtimes may stop an unlocked geometry ladder only after every legal
increment up to these absolute dimensions has been considered.
"""

from __future__ import annotations

import math


PROJECT_MAX_BEAM_DEPTH_MM = 5000.0
PROJECT_MAX_BEAM_WIDTH_MM = 5000.0
GEOMETRY_LADDER_INCREMENT_MM = 25.0


def incremental_geometry_values(
    current_mm: float,
    maximum_mm: float,
    *,
    increment_mm: float = GEOMETRY_LADDER_INCREMENT_MM,
) -> tuple[float, ...]:
    """Return monotonic increments above ``current_mm`` up to the maximum."""

    current = float(current_mm)
    maximum = float(maximum_mm)
    increment = float(increment_mm)
    if increment <= 0.0:
        raise ValueError("Geometry ladder increment must be positive")
    if current >= maximum - 1e-9:
        return ()
    count = max(0, int(math.floor((maximum - current + 1e-9) / increment)))
    return tuple(current + increment * step for step in range(1, count + 1))


def project_depth_values(
    current_mm: float,
    *,
    increment_mm: float = GEOMETRY_LADDER_INCREMENT_MM,
) -> tuple[float, ...]:
    return incremental_geometry_values(
        current_mm,
        maximum_mm=PROJECT_MAX_BEAM_DEPTH_MM,
        increment_mm=increment_mm,
    )


def project_width_values(
    current_mm: float,
    *,
    increment_mm: float = GEOMETRY_LADDER_INCREMENT_MM,
) -> tuple[float, ...]:
    return incremental_geometry_values(
        current_mm,
        maximum_mm=PROJECT_MAX_BEAM_WIDTH_MM,
        increment_mm=increment_mm,
    )


def within_project_geometry_limits(depth_mm: float, width_mm: float) -> bool:
    return (
        float(depth_mm) <= PROJECT_MAX_BEAM_DEPTH_MM + 1e-9
        and float(width_mm) <= PROJECT_MAX_BEAM_WIDTH_MM + 1e-9
    )


__all__ = [
    "GEOMETRY_LADDER_INCREMENT_MM",
    "PROJECT_MAX_BEAM_DEPTH_MM",
    "PROJECT_MAX_BEAM_WIDTH_MM",
    "incremental_geometry_values",
    "project_depth_values",
    "project_width_values",
    "within_project_geometry_limits",
]
