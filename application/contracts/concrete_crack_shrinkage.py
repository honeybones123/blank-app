"""Typed contracts for selectable concrete crack-control and shrinkage methods."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Mapping


class CrackControlMethod(StrEnum):
    EXISTING_AS3600 = "existing_as3600"
    AS5100_WALL = "as5100_wall"
    EC2 = "ec2"
    CIRIA_C766_EC2 = "ciria_c766_ec2"


class ShrinkageMethod(StrEnum):
    EXISTING_AS3600 = "existing_as3600"
    EC2_C766 = "ec2_c766"


@dataclass(frozen=True, slots=True)
class MethodReference:
    document: str
    edition: str
    clause: str


@dataclass(frozen=True, slots=True)
class MethodResult:
    method: CrackControlMethod | ShrinkageMethod
    reference: MethodReference
    values: Mapping[str, float | bool | str]
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class AS5100WallCrackControlInput:
    wall_thickness_mm: float
    provided_horizontal_area_per_face_mm2_per_m: float | None = None
    provided_vertical_spacing_mm: float | None = None
    in_base_zone: bool = False
    restrained_for_shrinkage_or_temperature: bool = True


@dataclass(frozen=True, slots=True)
class AS5100WallCrackControlResult:
    method: CrackControlMethod
    reference: MethodReference
    design_strip_width_mm: float
    calculation_thickness_per_face_mm: float
    required_ratio: float
    required_area_per_face_mm2_per_m: float
    maximum_spacing_mm: float
    provided_area_per_face_mm2_per_m: float | None
    provided_spacing_mm: float | None
    area_utilisation: float | None
    area_passes: bool | None
    spacing_passes: bool | None
    passes: bool | None
    warnings: tuple[str, ...]


class RestraintType(StrEnum):
    CONTINUOUS_EDGE = "continuous_edge"
    END = "end"
    INTERNAL = "internal"


@dataclass(frozen=True, slots=True)
class C766CrackControlInput:
    restraint_type: RestraintType
    temperature_drop_early_c: float
    temperature_change_long_term_c: float
    thermal_expansion_per_c: float
    autogenous_shrinkage_early: float
    autogenous_shrinkage_long_term: float
    drying_shrinkage: float
    restraint_early: float
    restraint_medium: float
    restraint_long_term: float
    tensile_strain_capacity: float
    creep_coefficient_early: float = 0.65
    creep_coefficient_long_term: float = 0.5
    cover_mm: float | None = None
    bar_diameter_mm: float | None = None
    effective_reinforcement_ratio: float | None = None
    bond_coefficient_k1: float = 0.8
    strain_distribution_k2: float = 1.0
    crack_spacing_k3: float = 3.4
    crack_spacing_k4: float = 0.425


@dataclass(frozen=True, slots=True)
class C766CrackControlResult:
    method: CrackControlMethod
    reference: MethodReference
    restrained_strain: float
    crack_initiates: bool
    crack_inducing_strain: float
    maximum_crack_spacing_mm: float | None
    characteristic_crack_width_mm: float | None
    warnings: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class C766MinimumReinforcementInput:
    concrete_tension_area_mm2: float
    mean_tensile_strength_at_cracking_mpa: float
    reinforcement_yield_strength_mpa: float
    stress_distribution_coefficient_kc: float
    non_uniform_stress_coefficient_k: float
    edge_restraint_factor: float


@dataclass(frozen=True, slots=True)
class C766MinimumReinforcementResult:
    required_area_mm2: float
    edge_load_transfer_coefficient: float
    reference: MethodReference


@dataclass(frozen=True, slots=True)
class C766EndRestraintInput:
    effective_modular_ratio: float
    non_uniform_stress_coefficient_k: float
    stress_distribution_coefficient_kc: float
    characteristic_tensile_strength_at_cracking_mpa: float
    reinforcement_modulus_mpa: float
    reinforcement_ratio_total_to_tension_area: float
    cover_mm: float | None = None
    bar_diameter_mm: float | None = None
    effective_reinforcement_ratio: float | None = None
    bond_coefficient_k1: float = 0.8
    strain_distribution_k2: float = 1.0
    crack_spacing_k3: float = 3.4
    crack_spacing_k4: float = 0.425


@dataclass(frozen=True, slots=True)
class C766EndRestraintResult:
    method: CrackControlMethod
    reference: MethodReference
    crack_inducing_strain: float
    maximum_crack_spacing_mm: float | None
    characteristic_crack_width_mm: float | None
    warnings: tuple[str, ...]


class CementClass(StrEnum):
    SLOW = "S"
    NORMAL = "N"
    RAPID = "R"


@dataclass(frozen=True, slots=True)
class EC2C766ShrinkageInput:
    characteristic_cylinder_strength_mpa: float
    relative_humidity_percent: float
    cement_class: CementClass
    concrete_area_mm2: float
    drying_perimeter_mm: float
    age_days: float
    drying_start_age_days: float


@dataclass(frozen=True, slots=True)
class EC2C766ShrinkageResult:
    method: ShrinkageMethod
    reference: MethodReference
    mean_compressive_strength_mpa: float
    notional_size_mm: float
    nominal_drying_shrinkage: float
    size_coefficient_kh: float
    drying_time_coefficient: float
    drying_shrinkage: float
    autogenous_shrinkage: float
    total_shrinkage: float
    warnings: tuple[str, ...]
