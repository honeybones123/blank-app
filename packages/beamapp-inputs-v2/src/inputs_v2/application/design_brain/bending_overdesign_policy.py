"""Deterministic search-space policy for bending overdesign cleanup."""

from __future__ import annotations

from typing import NamedTuple

from inputs_v2.domain.beam_inputs import BeamInputs


class GeometryArrangement(NamedTuple):
    bars: int
    diameter_mm: int


class OverdesignGeometryCell(NamedTuple):
    width_mm: float
    depth_mm: float
    arrangements: tuple[GeometryArrangement, ...]


class ReinforcementReduction(NamedTuple):
    bars: int
    diameter_mm: int


class ShearPreservationOption(NamedTuple):
    reinforcement_index: float
    diameter_mm: int
    legs: int
    spacing_mm: float


def generate_overdesign_geometry_cells(
    current: BeamInputs,
    current_utilisation: float,
) -> tuple[OverdesignGeometryCell, ...]:
    """Return the bounded target-directed geometry cleanup cells."""
    if current.width_locked and current.depth_locked:
        return ()
    widths = (
        (float(current.width_mm),)
        if current.width_locked
        else tuple(
            dict.fromkeys(
                (
                    float(current.width_mm),
                    *(float(width) for width in range(int(current.width_mm) - 25, 149, -25)),
                )
            )
        )
    )
    if current.depth_locked:
        depths = (float(current.depth_mm),)
    else:
        reduced = tuple(
            float(depth)
            for depth in range(int(current.depth_mm) - 25, 199, -25)
        )
        increased = tuple(
            float(depth)
            for depth in range(
                int(current.depth_mm) + 25,
                int(current.depth_mm) + 301,
                25,
            )
        )
        depths = tuple(
            dict.fromkeys((float(current.depth_mm), *reduced, *increased))
        )
    target_measure = (
        current.width_mm
        * current.depth_mm**2
        * max(current_utilisation, 0.01)
        / 0.925
    )
    all_cells = tuple(
        (width, depth)
        for width in widths
        for depth in depths
        if width >= 150.0 and depth >= 200.0 and depth <= 2.0 * width
    )
    predicted = sorted(
        all_cells,
        key=lambda cell: (
            abs(cell[0] * cell[1] ** 2 / max(target_measure, 1.0) - 1.0),
            cell[0] * cell[1],
        ),
    )
    boundary = sorted(
        all_cells,
        key=lambda cell: (cell[0] * cell[1], cell[0], cell[1]),
    )
    selected = tuple(
        dict.fromkeys((*predicted[:24], *all_cells[:24], *boundary[:24]))
    )[:72]
    return tuple(
        OverdesignGeometryCell(
            width,
            depth,
            _geometry_arrangements(current, width, depth),
        )
        for width, depth in selected
    )


def generate_reinforcement_reductions(
    current: BeamInputs,
) -> tuple[ReinforcementReduction, ...]:
    """Return reductions in monotonically descending tensile potential.

    This order lets the family prove a section-level capacity ceiling before
    stopping a long tail of still-weaker reinforcement trials.  The shared
    calculation gateway remains the acceptance authority.
    """
    current_index = current.bottom.bars * current.bottom.diameter_mm**2
    reductions = tuple(
        ReinforcementReduction(bars, diameter)
        for bars in range(2, current.bottom.bars + 1)
        for diameter in (10, 12, 16, 20, 24, 28, 32, 36, 40)
        if bars * diameter**2 < current_index
    )
    return tuple(
        sorted(
            reductions,
            key=lambda item: (
                -item.bars
                * item.diameter_mm**2
                * max(
                    current.depth_mm
                    - current.bottom.cover_mm
                    - item.diameter_mm / 2.0,
                    1.0,
                ),
                item.bars,
                item.diameter_mm,
            ),
        )
    )


def generate_shear_preservation_options(
    current: BeamInputs,
) -> tuple[ShearPreservationOption, ...]:
    """Return the twelve least-dense link upgrades that exceed current links."""
    diameters = tuple(
        diameter
        for diameter in (10, 12, 16, 20, 24, 28, 32)
        if diameter >= max(current.shear.diameter_mm, 10)
    )
    legs = tuple(
        value
        for value in (2, 4, 6, 8)
        if value >= max(current.shear.legs, 2)
    )
    spacings = tuple(
        value
        for value in (
            600.0, 500.0, 400.0, 300.0, 250.0,
            200.0, 175.0, 150.0, 125.0, 100.0,
        )
        if value <= current.shear.spacing_mm
    ) or (current.shear.spacing_mm,)
    current_index = (
        current.shear.legs
        * current.shear.diameter_mm**2
        / max(current.shear.spacing_mm, 1.0)
        if current.shear.diameter_mm and current.shear.legs
        else 0.0
    )
    options = sorted(
        (
            ShearPreservationOption(
                leg_count * diameter**2 / spacing,
                diameter,
                leg_count,
                spacing,
            )
            for diameter in diameters
            for leg_count in legs
            for spacing in spacings
            if leg_count * diameter**2 / spacing > current_index + 1e-9
        ),
        key=lambda row: (
            row.reinforcement_index,
            row.diameter_mm,
            row.legs,
            -row.spacing_mm,
        ),
    )
    return tuple(options[:12])


def _geometry_arrangements(
    current: BeamInputs,
    width_mm: float,
    depth_mm: float,
) -> tuple[GeometryArrangement, ...]:
    estimated_minimum = 0.006 * width_mm * max(
        depth_mm - current.bottom.cover_mm, 1.0
    )
    # This generator must not pre-empt the authoritative minimum-steel
    # calculation with the old 0.6% approximation.  That approximation
    # excluded valid small-section arrangements (for example 2-N10) and
    # forced a second Apply cycle.  Generate a bounded set both below and
    # around the estimate; the shared calculation gateway decides validity.
    pool = sorted(
        (
            (bars * 0.7854 * diameter**2, bars, diameter)
            for bars in range(2, 9)
            for diameter in (10, 12, 16, 20, 24, 28, 32, 36, 40)
        ),
        key=lambda item: item[0],
    )
    nearest = sorted(pool, key=lambda item: abs(item[0] - estimated_minimum))[:8]
    balanced = tuple(dict.fromkeys((*pool[:8], *nearest)))
    return tuple(
        GeometryArrangement(bars, diameter)
        for bars, diameter in dict.fromkeys(
            ((current.bottom.bars, current.bottom.diameter_mm),)
            + tuple((bars, diameter) for _area, bars, diameter in balanced)
        )
    )


__all__ = [
    "GeometryArrangement",
    "OverdesignGeometryCell",
    "ReinforcementReduction",
    "ShearPreservationOption",
    "generate_overdesign_geometry_cells",
    "generate_reinforcement_reductions",
    "generate_shear_preservation_options",
]
