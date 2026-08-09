"""Deterministic search-space policy for bending repair candidates."""

from __future__ import annotations

from typing import NamedTuple

from inputs_v2.domain.beam_inputs import BeamInputs
from inputs_v2.application.design_brain_apply import Candidate
from inputs_v2.engineering.reinforcement_fit import practical_row_counts


class BendingRepairSpec(NamedTuple):
    width_mm: float
    depth_mm: float
    bars: int
    diameter_mm: int
    row_counts: tuple[int, ...]


class BendingWidthLane(NamedTuple):
    width_mm: float
    candidates: tuple[BendingRepairSpec, ...]


class BendingReductionSpec(NamedTuple):
    width_mm: float
    depth_mm: float
    bars: int
    diameter_mm: int
    row_counts: tuple[int, ...]


class ProportionBalanceSpec(NamedTuple):
    width_mm: float
    depth_mm: float
    bars: int
    diameter_mm: int
    row_counts: tuple[int, ...]


def generate_bending_width_lanes(
    current: BeamInputs,
    current_utilisation: float,
    target_low: float = 0.85,
) -> tuple[BendingWidthLane, ...]:
    """Generate the ordered primary bending ladder, grouped by width lane."""
    widths = _width_trials(current, current_utilisation, target_low)
    return tuple(
        BendingWidthLane(
            width,
            tuple(
                BendingRepairSpec(width, depth, bars, diameter, rows)
                for depth in _depth_trials(
                    current, width, current_utilisation, target_low
                )
                for bars in range(2, 13)
                for diameter in (10, 12, 16, 20, 24, 28, 32, 36, 40)
                for rows in practical_row_counts(bars)
            ),
        )
        for width in widths
    )


def generate_bending_reduction_specs(
    current: BeamInputs,
) -> tuple[BendingReductionSpec, ...]:
    """Generate smaller-section cleanup trials in deterministic V1 order."""
    return tuple(
        BendingReductionSpec(float(width), float(depth), bars, diameter, rows)
        for depth in range(
            max(200, int(current.depth_mm) - 350),
            int(current.depth_mm),
            50,
        )
        for width in range(
            max(150, int(current.width_mm) - 175),
            int(current.width_mm) + 1,
            25,
        )
        if width * depth < current.width_mm * current.depth_mm
        for bars in range(2, 13)
        for diameter in (10, 12, 16, 20, 24, 28, 32, 36, 40)
        for rows in practical_row_counts(bars)
    )


def generate_proportion_balance_specs(
    current: BeamInputs,
    candidate: Candidate,
    *,
    evaluation_limit: int = 24,
) -> tuple[ProportionBalanceSpec, ...]:
    """Generate the bounded proportion-balancing ladder in declared order."""
    specs: list[ProportionBalanceSpec] = []
    proposal = candidate.proposal
    for depth in (
        proposal.depth_mm - 25.0,
        proposal.depth_mm - 50.0,
        proposal.depth_mm - 75.0,
    ):
        if depth < 200.0 or depth > 2.0 * proposal.width_mm:
            continue
        for width in (
            proposal.width_mm,
            proposal.width_mm - 25.0,
            proposal.width_mm - 50.0,
        ):
            if width < 150.0:
                continue
            for bars in (
                proposal.bottom_bars,
                proposal.bottom_bars + 1,
                proposal.bottom_bars + 2,
            ):
                for rows in practical_row_counts(bars):
                    if len(specs) >= evaluation_limit:
                        return tuple(specs)
                    specs.append(
                        ProportionBalanceSpec(
                            width,
                            depth,
                            bars,
                            proposal.bottom_diameter_mm,
                            rows,
                        )
                    )
    return tuple(specs)


def _width_trials(
    current: BeamInputs, current_utilisation: float, target_low: float
) -> tuple[float, ...]:
    if current.width_locked:
        return (float(current.width_mm),)
    max_width = min(
        3000.0,
        max(current.width_mm + 100.0, 2.0 * current.width_mm),
    )
    increases = tuple(
        current.width_mm + 25.0 * i
        for i in range(1, int((max_width - current.width_mm) / 25.0) + 1)
    )
    if current_utilisation >= target_low:
        return (float(current.width_mm), *increases)
    reductions = tuple(
        current.width_mm - 25.0 * i
        for i in range(
            1,
            int((current.width_mm - 150.0) / 25.0) + 1,
        )
    )
    # When the current summary utilisation is low, especially because minimum
    # tensile reinforcement governs, test the smallest standard widths first.
    # This reaches a proportionate compliant section before spending the Fast
    # budget exhaustively on oversized width lanes.
    return (*reversed(reductions), float(current.width_mm), *increases)


def _depth_trials(
    current: BeamInputs,
    width_mm: float,
    current_utilisation: float,
    target_low: float,
) -> tuple[float, ...]:
    max_depth = min(5000.0, 2.0 * width_mm)
    depths = {float(current.depth_mm)}
    if current_utilisation < target_low and not current.depth_locked:
        depths.update(
            float(depth)
            for depth in range(
                200,
                int(current.depth_mm),
                25,
            )
            if depth <= max_depth
        )
    if not current.depth_locked and max_depth > current.depth_mm:
        depths.update(
            float(depth)
            for depth in range(
                int(current.depth_mm) + 50,
                int(max_depth) + 1,
                50,
            )
        )
        depths.add(float(max_depth))
    return tuple(sorted(depths))


__all__ = [
    "BendingRepairSpec",
    "BendingReductionSpec",
    "BendingWidthLane",
    "ProportionBalanceSpec",
    "generate_bending_reduction_specs",
    "generate_bending_width_lanes",
    "generate_proportion_balance_specs",
]
