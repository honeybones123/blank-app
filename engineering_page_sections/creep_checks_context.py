"""Immutable, calculation-complete input for Creep check presentation."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CreepChecksSnapshot:
    width_mm: float
    depth_mm: float
    gross_area_mm2: float
    faces_exposed: str
    exposed_perimeter_mm: float
    notional_thickness_raw_mm: float
    notional_thickness_table_mm: int
    time_after_loading_days: float
    age_at_loading_days: float
    concrete_strength_mpa: float
    concrete_modulus_mpa: float
    environment: str
    alpha2: float
    phi_cc_b: float
    k2: float
    k3: float
    k4: float
    k5: float
    k6: float
    phi_cc_t: float
    phi_cc_star_table: float
    sustained_moment_knm: float
    sustained_compression_fibre: str
    sustained_section_modulus_mm3: float
    sustained_stress_mpa: float
    sustained_stress_ratio: float
    eps_cc: float
    eps_cc_micro: float


__all__ = ["CreepChecksSnapshot"]
