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


@dataclass(frozen=True)
class ShearDetailingResult:
    Asv_over_s: float
    Asv_min_over_s: float
    min_shear_ok: bool
    max_spacing: float
    spacing_ok: bool

    def as_family_values(self) -> dict[str, float | bool]:
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
    return ShearDetailingResult(
        Asv_over_s=provided,
        Asv_min_over_s=minimum,
        min_shear_ok=provided >= minimum,
        max_spacing=maximum_spacing,
        spacing_ok=spacing <= maximum_spacing if spacing else False,
    )


def _validate_finite(values: ShearDetailingInput) -> None:
    for name, value in vars(values).items():
        if value is not None and not math.isfinite(float(value)):
            raise ValueError(f"{name} must be finite")


__all__ = [
    "ShearDetailingInput",
    "ShearDetailingResult",
    "calculate_shear_detailing",
]
