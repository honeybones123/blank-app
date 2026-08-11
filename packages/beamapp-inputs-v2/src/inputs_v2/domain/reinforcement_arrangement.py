"""Immutable reinforcement arrangement and fit contracts."""
from dataclasses import dataclass
import math
from typing import Literal

@dataclass(frozen=True, slots=True)
class ReinforcementRow:
    row_index: int
    bar_count: int
    clear_spacing_mm: float
    centre_from_tension_face_mm: float
    bar_diameter_mm: float = 0.0

@dataclass(frozen=True, slots=True)
class ReinforcementArrangement:
    total_bar_count: int
    bar_diameter_mm: float
    rows: tuple[ReinforcementRow, ...]
    layer_count: int
    clear_row_gap_mm: float
    reinforcement_centroid_mm: float
    effective_depth_mm: float

    @property
    def total_steel_area_mm2(self) -> float:
        """Return the exact area of every stored row, including mixed diameters."""

        return sum(
            row.bar_count * math.pi * (row.bar_diameter_mm or self.bar_diameter_mm) ** 2 / 4.0
            for row in self.rows
        )

    @property
    def outer_bar_diameter_mm(self) -> float:
        """Diameter of the row nearest the tension face."""

        if not self.rows:
            return self.bar_diameter_mm
        first = min(self.rows, key=lambda row: row.row_index)
        return first.bar_diameter_mm or self.bar_diameter_mm

@dataclass(frozen=True, slots=True)
class CongestionAssessment:
    horizontal_clearance_margin_mm: float
    vertical_clearance_margin_mm: float
    bars_per_row: tuple[int, ...]
    layer_count: int
    total_longitudinal_bars: int
    transverse_leg_count: int
    practical_spacing_pass: bool
    congestion_class: Literal["low", "moderate", "high", "invalid"]
    reasons: tuple[str, ...] = ()

@dataclass(frozen=True, slots=True)
class ReinforcementFitResult:
    arrangement: ReinforcementArrangement
    horizontal_fit: bool
    vertical_fit: bool
    cover_ok: bool
    clear_spacing_ok: bool
    aggregate_clearance_ok: bool
    accepted: bool
    congestion: CongestionAssessment
    failure_reasons: tuple[str, ...] = ()
