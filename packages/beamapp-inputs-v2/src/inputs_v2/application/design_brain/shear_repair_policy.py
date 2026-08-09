"""Deterministic candidate-space policy for shear failure repair."""

from __future__ import annotations

from typing import NamedTuple

from inputs_v2.domain.beam_inputs import BeamInputs


class ShearRepairSpec(NamedTuple):
    lane: str
    changes: dict[str, float | int]
    edit_size: float


def generate_shear_repair_specs(
    current: BeamInputs, current_utilisation: float
) -> tuple[ShearRepairSpec, ...]:
    """Generate the V1-ordered spacing-to-geometry shear repair ladder."""
    spacings = (300.0, 250.0, 200.0, 175.0, 150.0, 125.0, 100.0)
    legs_values = (2, 4, 6)
    diameters = (10, 12, 16)
    depths = (
        ()
        if current.depth_locked
        else tuple(current.depth_mm + 25.0 * i for i in range(1, 7))
    )
    max_width = (
        current.width_mm
        if current.width_locked
        else min(
            3000.0,
            max(current.width_mm + 100.0, 2.0 * current.width_mm),
        )
    )
    widths = tuple(
        current.width_mm + 25.0 * i
        for i in range(1, int((max_width - current.width_mm) / 25.0) + 1)
    )
    candidates: list[ShearRepairSpec] = []
    for spacing in spacings:
        candidates.append(
            ShearRepairSpec(
                "spacing",
                {"shear_spacing_mm": spacing},
                abs(spacing - current.shear.spacing_mm) / 100.0,
            )
        )
    for legs in legs_values:
        for spacing in spacings:
            candidates.append(
                ShearRepairSpec(
                    "legs",
                    {"shear_legs": legs, "shear_spacing_mm": spacing},
                    1.0 + abs(spacing - current.shear.spacing_mm) / 100.0,
                )
            )
    for diameter in diameters:
        for legs in legs_values:
            for spacing in spacings:
                candidates.append(
                    ShearRepairSpec(
                        "diameter",
                        {
                            "shear_diameter_mm": diameter,
                            "shear_legs": legs,
                            "shear_spacing_mm": spacing,
                        },
                        2.0 + abs(spacing - current.shear.spacing_mm) / 100.0,
                    )
                )
    for depth in depths:
        for spacing in spacings:
            candidates.append(
                ShearRepairSpec(
                    "depth",
                    {"depth_mm": depth, "shear_spacing_mm": spacing},
                    3.0 + (depth - current.depth_mm) / 100.0,
                )
            )
    for width in widths:
        for diameter in diameters:
            for legs in legs_values:
                for spacing in spacings:
                    candidates.append(
                        ShearRepairSpec(
                            "width",
                            {
                                "width_mm": width,
                                "shear_diameter_mm": diameter,
                                "shear_legs": legs,
                                "shear_spacing_mm": spacing,
                            },
                            4.0
                            + (width - current.width_mm) / 100.0
                            + abs(diameter - current.shear.diameter_mm) / 10.0
                            + abs(legs - current.shear.legs) / 2.0,
                        )
                    )
    if current_utilisation > 2.0 and not current.depth_locked:
        _append_coordinated_geometry(candidates, current, widths)
    return tuple(candidates)


def _append_coordinated_geometry(
    candidates: list[ShearRepairSpec],
    current: BeamInputs,
    widths: tuple[float, ...],
) -> None:
    coordinated_links = (
        (10, 2, 100.0), (10, 4, 100.0), (10, 6, 100.0),
        (12, 2, 100.0), (12, 4, 100.0), (12, 6, 100.0),
        (16, 2, 100.0), (16, 4, 100.0), (16, 6, 100.0),
        (16, 6, 125.0), (16, 6, 150.0), (16, 6, 175.0), (16, 6, 200.0),
    )
    for width in (float(current.width_mm), *widths):
        maximum_depth = min(5000.0, 2.0 * width, current.depth_mm + 700.0)
        depths = tuple(
            current.depth_mm + 50.0 * i
            for i in range(1, int((maximum_depth - current.depth_mm) / 50.0) + 1)
        )
        for depth in depths:
            estimated_min_ast = 0.006 * width * max(
                depth - current.bottom.cover_mm, 1.0
            )
            bottom_pool = sorted(
                (
                    (bars * 0.7854 * diameter**2, bars, diameter)
                    for bars in range(2, 9)
                    for diameter in (10, 12, 16, 20, 24, 28, 32, 36, 40)
                    if bars * 0.7854 * diameter**2 >= estimated_min_ast
                ),
                key=lambda item: item[0],
            )[:5]
            if not bottom_pool:
                bottom_pool = [
                    (0.0, current.bottom.bars, current.bottom.diameter_mm)
                ]
            for _area, bottom_bars, bottom_diameter in bottom_pool:
                for diameter, legs, spacing in coordinated_links:
                    candidates.append(
                        ShearRepairSpec(
                            "coordinated_geometry",
                            {
                                "width_mm": width,
                                "depth_mm": depth,
                                "bottom_bars": bottom_bars,
                                "bottom_diameter_mm": bottom_diameter,
                                "shear_diameter_mm": diameter,
                                "shear_legs": legs,
                                "shear_spacing_mm": spacing,
                            },
                            5.0
                            + (width - current.width_mm) / 100.0
                            + (depth - current.depth_mm) / 100.0
                            + abs(bottom_bars - current.bottom.bars)
                            + abs(bottom_diameter - current.bottom.diameter_mm) / 10.0
                            + abs(diameter - current.shear.diameter_mm) / 10.0
                            + abs(legs - current.shear.legs) / 2.0,
                        )
                    )


__all__ = ["ShearRepairSpec", "generate_shear_repair_specs"]
