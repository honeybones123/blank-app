"""Immutable calculation-complete input for Shrinkage check presentation."""

from __future__ import annotations

from dataclasses import dataclass

from application.contracts.concrete_crack_shrinkage import (
    EC2C766ShrinkageResult,
)


@dataclass(frozen=True, slots=True)
class ShrinkageChecksSnapshot:
    method: str
    method_result: EC2C766ShrinkageResult | None
    width_mm: float
    depth_mm: float
    gross_area_mm2: float
    faces_exposed: str
    exposed_perimeter_mm: float
    notional_thickness_raw_mm: float
    notional_thickness_table_mm: int
    concrete_strength_mpa: float
    concrete_strength_table_mpa: float
    environment: str
    environment_short_label: str
    time_days: float
    k1: float
    eps_cse: float
    eps_cse_final: float
    eps_csd_final: float
    eps_csd_t: float
    eps_cs_total: float


__all__ = ["ShrinkageChecksSnapshot"]
