"""Immutable reinforcement arrangement and fit contracts."""
from dataclasses import dataclass
from typing import Literal

@dataclass(frozen=True, slots=True)
class ReinforcementRow:
    row_index: int
    bar_count: int
    clear_spacing_mm: float
    centre_from_tension_face_mm: float

@dataclass(frozen=True, slots=True)
class ReinforcementArrangement:
    total_bar_count: int
    bar_diameter_mm: float
    rows: tuple[ReinforcementRow, ...]
    layer_count: int
    clear_row_gap_mm: float
    reinforcement_centroid_mm: float
    effective_depth_mm: float

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
