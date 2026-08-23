"""Read-only inputs used by AS 3600 Crack Control teaching checks."""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping


@dataclass(frozen=True, slots=True)
class CrackAs3600ChecksSnapshot:
    width_limit_mm: float
    member_type: str
    bar_diameter_mm: float
    bar_spacing_mm: float
    steel_stress_mpa: float
    steel_yield_strength_mpa: float
    table_basis: str
    table_limit_a_mpa: float
    table_limit_b_mpa: float
    table_combined_limit_mpa: float
    yield_limit_mpa: float
    allowable_stress_mpa: float
    table_utilisation: float
    table_passes: bool
    effective_tension_area_mm2: float
    tension_steel_area_mm2: float
    effective_reinforcement_ratio: float
    concrete_tensile_strength_mpa: float
    steel_modulus_mpa: float
    concrete_modulus_mpa: float
    creep_coefficient: float
    effective_modular_ratio: float
    shrinkage_microstrain: float
    strain_difference: float
    cover_mm: float
    bond_coefficient: float
    strain_distribution_factor: float
    maximum_crack_spacing_mm: float
    crack_width_mm: float
    width_utilisation: float
    width_passes: bool
    expanded_steps: Mapping[str, bool]


def freeze_expanded_steps(values: Mapping[str, bool]) -> Mapping[str, bool]:
    return MappingProxyType({str(key): bool(value) for key, value in values.items()})


__all__ = ["CrackAs3600ChecksSnapshot", "freeze_expanded_steps"]
