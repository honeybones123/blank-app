"""Typed reinforced-concrete section geometry contracts.

Section shape changes how an existing Design Brain family generates and
evaluates candidates.  These value objects contain geometry facts only; they
have no family-selection, ranking, publication, or Apply authority.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TypeAlias


@dataclass(frozen=True, slots=True)
class RectSectionGeometry:
    width_mm: float
    depth_mm: float

    @property
    def shape(self) -> str:
        return "RECT"

    def validated(self) -> "RectSectionGeometry":
        if not 150.0 <= float(self.width_mm) <= 3000.0:
            raise ValueError("Rectangular section width must be between 150 and 3000 mm.")
        if not 200.0 <= float(self.depth_mm) <= 5000.0:
            raise ValueError("Rectangular section depth must be between 200 and 5000 mm.")
        return self

    @property
    def concrete_area_mm2(self) -> float:
        return float(self.width_mm) * float(self.depth_mm)


@dataclass(frozen=True, slots=True)
class TSectionGeometry:
    web_width_mm: float
    depth_mm: float
    flange_width_mm: float
    flange_thickness_mm: float

    @property
    def shape(self) -> str:
        return "T"

    def validated(self) -> "TSectionGeometry":
        _validate_flanged_geometry(
            web_width_mm=self.web_width_mm,
            depth_mm=self.depth_mm,
            flange_width_mm=self.flange_width_mm,
            flange_thickness_mm=self.flange_thickness_mm,
            symmetric_i=False,
        )
        return self

    @property
    def concrete_area_mm2(self) -> float:
        web_depth = float(self.depth_mm) - float(self.flange_thickness_mm)
        return (
            float(self.web_width_mm) * web_depth
            + float(self.flange_width_mm) * float(self.flange_thickness_mm)
        )


@dataclass(frozen=True, slots=True)
class SymmetricISectionGeometry:
    web_width_mm: float
    depth_mm: float
    flange_width_mm: float
    flange_thickness_mm: float

    @property
    def shape(self) -> str:
        return "I"

    def validated(self) -> "SymmetricISectionGeometry":
        _validate_flanged_geometry(
            web_width_mm=self.web_width_mm,
            depth_mm=self.depth_mm,
            flange_width_mm=self.flange_width_mm,
            flange_thickness_mm=self.flange_thickness_mm,
            symmetric_i=True,
        )
        return self

    @property
    def concrete_area_mm2(self) -> float:
        web_depth = float(self.depth_mm) - 2.0 * float(self.flange_thickness_mm)
        return (
            float(self.web_width_mm) * web_depth
            + 2.0 * float(self.flange_width_mm) * float(self.flange_thickness_mm)
        )


SectionGeometry: TypeAlias = (
    RectSectionGeometry | TSectionGeometry | SymmetricISectionGeometry
)


def _validate_flanged_geometry(
    *,
    web_width_mm: float,
    depth_mm: float,
    flange_width_mm: float,
    flange_thickness_mm: float,
    symmetric_i: bool,
) -> None:
    web = float(web_width_mm)
    depth = float(depth_mm)
    flange = float(flange_width_mm)
    thickness = float(flange_thickness_mm)
    if not 150.0 <= web <= 3000.0:
        raise ValueError("Section web width must be between 150 and 3000 mm.")
    if not 200.0 <= depth <= 5000.0:
        raise ValueError("Section depth must be between 200 and 5000 mm.")
    if flange < web:
        raise ValueError("Flange width must be at least the web width.")
    if not 0.0 < thickness < depth:
        raise ValueError("Flange thickness must be within the section depth.")
    if symmetric_i and 2.0 * thickness >= depth:
        raise ValueError("I-section flanges must leave a positive web depth.")


def geometry_from_values(
    *,
    section_shape: str,
    width_mm: float,
    depth_mm: float,
    flange_width_mm: float | None,
    flange_thickness_mm: float | None,
    web_width_mm: float | None,
) -> SectionGeometry:
    """Build the exact typed geometry represented by canonical input fields."""

    shape = str(section_shape).upper()
    if shape == "RECT":
        return RectSectionGeometry(float(width_mm), float(depth_mm)).validated()
    if flange_width_mm is None or flange_thickness_mm is None or web_width_mm is None:
        raise ValueError("Flanged sections require flange width, flange thickness and web width.")
    values = {
        "web_width_mm": float(web_width_mm),
        "depth_mm": float(depth_mm),
        "flange_width_mm": float(flange_width_mm),
        "flange_thickness_mm": float(flange_thickness_mm),
    }
    if shape == "T":
        return TSectionGeometry(**values).validated()
    if shape == "I":
        return SymmetricISectionGeometry(**values).validated()
    raise ValueError("Section shape is not supported.")
