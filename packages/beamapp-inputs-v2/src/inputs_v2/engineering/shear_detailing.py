"""V2-owned shear reinforcement detailing checks."""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class ShearDetailingInput:
    reinforcement_area_mm2: float
    spacing_mm: float | None
    concrete_strength_mpa: float
    web_width_mm: float
    reinforcement_strength_mpa: float
    section_depth_mm: float | None
    effective_legs: int = 0
    link_diameter_mm: float = 0.0
    side_cover_mm: float = 40.0


@dataclass(frozen=True)
class ShearDetailingResult:
    Asv_over_s: float
    Asv_min_over_s: float
    min_shear_ok: bool
    max_spacing: float
    spacing_ok: bool
    transverse_leg_centres_mm: tuple[float, ...]
    transverse_adjacent_spacings_mm: tuple[float, ...]
    transverse_max_leg_spacing_mm: float
    transverse_spacing_limit_mm: float
    transverse_minimum_even_legs: int | None
    transverse_spacing_ok: bool
    transverse_fit_ok: bool

    def as_family_values(self) -> dict[str, object]:
        return asdict(self)


def calculate_shear_detailing(values: ShearDetailingInput) -> ShearDetailingResult:
    """Check minimum transverse steel and AS 3600 maximum spacing."""
    _validate_finite(values)
    spacing = values.spacing_mm
    provided = values.reinforcement_area_mm2 / spacing if spacing else 0.0
    strength = values.reinforcement_strength_mpa or 1.0
    minimum = (
        0.08
        * math.sqrt(max(values.concrete_strength_mpa, 0.0))
        * values.web_width_mm
        / strength
    )
    maximum_spacing = (
        min(0.75 * values.section_depth_mm, 500.0)
        if values.section_depth_mm
        else 500.0
    )
    (
        leg_centres,
        adjacent_spacings,
        transverse_max_spacing,
        transverse_limit,
        minimum_even_legs,
        transverse_spacing_ok,
        transverse_fit_ok,
    ) = _transverse_leg_spacing(values)
    return ShearDetailingResult(
        Asv_over_s=provided,
        Asv_min_over_s=minimum,
        min_shear_ok=provided >= minimum,
        max_spacing=maximum_spacing,
        spacing_ok=spacing <= maximum_spacing if spacing else False,
        transverse_leg_centres_mm=leg_centres,
        transverse_adjacent_spacings_mm=adjacent_spacings,
        transverse_max_leg_spacing_mm=transverse_max_spacing,
        transverse_spacing_limit_mm=transverse_limit,
        transverse_minimum_even_legs=minimum_even_legs,
        transverse_spacing_ok=transverse_spacing_ok,
        transverse_fit_ok=transverse_fit_ok,
    )


def _transverse_leg_spacing(
    values: ShearDetailingInput,
) -> tuple[
    tuple[float, ...],
    tuple[float, ...],
    float,
    float,
    int | None,
    bool,
    bool,
]:
    """Resolve fitted across-width leg centres and maximum adjacent spacing."""

    legs = int(values.effective_legs or 0)
    depth = max(float(values.section_depth_mm or 0.0), 0.0)
    limit = min(600.0, depth) if depth > 0.0 else 0.0
    if legs <= 0:
        return (), (), 0.0, limit, 0, True, True

    link_diameter = max(float(values.link_diameter_mm or 0.0), 0.0)
    centre_offset = float(values.side_cover_mm) + link_diameter / 2.0
    outer_span = float(values.web_width_mm) - 2.0 * centre_offset
    fit_ok = legs >= 2 and link_diameter > 0.0 and outer_span >= 0.0 and limit > 0.0
    if not fit_ok:
        return (), (), 0.0, limit, None, False, False

    raw_minimum = math.ceil(outer_span / limit) + 1
    minimum_even = next(
        (candidate for candidate in (2, 4, 6, 8) if candidate >= raw_minimum),
        None,
    )
    step = outer_span / (legs - 1)
    centres = tuple(centre_offset + index * step for index in range(legs))
    adjacent = tuple(
        centres[index + 1] - centres[index]
        for index in range(len(centres) - 1)
    )
    maximum = max(adjacent, default=0.0)
    spacing_ok = (
        minimum_even is not None
        and legs in (2, 4, 6, 8)
        and maximum <= limit + 1e-9
    )
    return centres, adjacent, maximum, limit, minimum_even, spacing_ok, True


def _validate_finite(values: ShearDetailingInput) -> None:
    for name, value in vars(values).items():
        if value is not None and not math.isfinite(float(value)):
            raise ValueError(f"{name} must be finite")


__all__ = [
    "ShearDetailingInput",
    "ShearDetailingResult",
    "calculate_shear_detailing",
]
