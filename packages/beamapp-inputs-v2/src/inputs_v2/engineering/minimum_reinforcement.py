"""Minimum longitudinal tensile reinforcement for the current section model."""

from __future__ import annotations

from math import sqrt


def rectangular_minimum_tensile_area_mm2(
    *,
    width_mm: float,
    overall_depth_mm: float,
    effective_depth_mm: float,
    concrete_strength_mpa: float,
    reinforcement_strength_mpa: float,
) -> float:
    """Return AS 3600:2018 Clause 8.1.6.1 minimum steel for a rectangle."""

    width = float(width_mm)
    overall_depth = float(overall_depth_mm)
    effective_depth = float(effective_depth_mm)
    concrete_strength = float(concrete_strength_mpa)
    reinforcement_strength = float(reinforcement_strength_mpa)
    if min(
        width,
        overall_depth,
        effective_depth,
        concrete_strength,
        reinforcement_strength,
    ) <= 0.0:
        return 0.0
    flexural_tensile_strength = 0.6 * sqrt(concrete_strength)
    alpha_b = 0.20
    return float(
        alpha_b
        * (overall_depth / effective_depth) ** 2
        * (flexural_tensile_strength / reinforcement_strength)
        * width
        * effective_depth
    )


__all__ = ["rectangular_minimum_tensile_area_mm2"]
