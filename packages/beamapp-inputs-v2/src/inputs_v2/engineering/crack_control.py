"""V2-owned crack-control calculation component."""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass


_STRESS_BY_DIAMETER = {
    10: {0.2: 190, 0.3: 265, 0.4: 335},
    12: {0.2: 175, 0.3: 245, 0.4: 305},
    16: {0.2: 155, 0.3: 215, 0.4: 270},
    20: {0.2: 140, 0.3: 195, 0.4: 240},
    24: {0.2: 125, 0.3: 175, 0.4: 215},
    28: {0.2: 115, 0.3: 160, 0.4: 200},
    32: {0.2: 105, 0.3: 150, 0.4: 185},
    36: {0.2: 100, 0.3: 140, 0.4: 175},
    40: {0.2: 90, 0.3: 130, 0.4: 165},
}
_STRESS_BY_SPACING = {
    50: {0.2: 200, 0.3: 300, 0.4: 400},
    100: {0.2: 170, 0.3: 270, 0.4: 360},
    150: {0.2: 155, 0.3: 245, 0.4: 330},
    200: {0.2: 145, 0.3: 225, 0.4: 300},
    250: {0.2: 135, 0.3: 210, 0.4: 280},
    300: {0.2: 125, 0.3: 200, 0.4: 260},
}


@dataclass(frozen=True)
class CrackControlInput:
    width_mm: float
    depth_mm: float
    cover_mm: float
    bar_diameter_mm: float
    bar_spacing_mm: float
    steel_area_mm2: float
    concrete_strength_mpa: float
    concrete_modulus_mpa: float
    steel_modulus_mpa: float
    steel_strength_mpa: float
    crack_width_limit_mm: float
    member_type: str
    outer_steel_stress_mpa: float
    creep_coefficient: float
    shrinkage_strain: float
    bond_factor: float
    strain_distribution_factor: float
    neutral_axis_depth_mm: float
    tension_face: str = "bottom"


@dataclass(frozen=True)
class CrackControlResult:
    d_eff: float
    height_eff: float
    Aceff: float
    rho_eff: float
    sigma_table_A: float
    sigma_table_B: float
    sigma_table_combined: float
    sigma_08fsy: float
    sigma_allow_table: float
    utilisation_table: float
    passes_table: bool
    direct_width_applicable: bool
    fct_eff: float
    ne: float
    eps_diff: float | None
    sr_max: float | None
    w_calc: float | None
    utilisation_w: float | None
    passes_w: bool | None

    def as_family_values(self) -> dict[str, float | bool | None]:
        return asdict(self)


def calculate_crack_control(values: CrackControlInput) -> CrackControlResult:
    """Calculate the AS 3600 table and direct crack-width checks."""
    _validate_finite(values)
    tension_steel_face_distance = values.cover_mm + values.bar_diameter_mm / 2.0
    d_eff = values.depth_mm - tension_steel_face_distance
    height_eff = min(
        2.5 * max(values.depth_mm - d_eff, 0.0),
        max(values.depth_mm - values.neutral_axis_depth_mm, 0.0) / 3.0,
        values.depth_mm / 2.0,
    )
    effective_area = values.width_mm * max(height_eff, 1.0)
    ratio = values.steel_area_mm2 / effective_area if effective_area > 0 else 0.0
    sigma_a = _table_stress(_STRESS_BY_DIAMETER, values.bar_diameter_mm, values.crack_width_limit_mm)
    sigma_b = _table_stress(_STRESS_BY_SPACING, values.bar_spacing_mm, values.crack_width_limit_mm)
    sigma_combined = sigma_a if values.member_type == "Primarily tension" else max(sigma_a, sigma_b)
    sigma_strength_limit = 0.8 * values.steel_strength_mpa
    sigma_allow = min(sigma_combined, sigma_strength_limit)
    table_util = values.outer_steel_stress_mpa / sigma_allow if sigma_allow > 0 else 0.0
    # Clause 8.6.2.3 uses mean axial tensile strength. Clause 3.1.1.3 gives
    # characteristic f'ct = 0.36 sqrt(f'c), with mean value 1.4 times that.
    tensile_strength = 1.4 * 0.36 * math.sqrt(
        max(values.concrete_strength_mpa, 1.0)
    )
    modular_ratio = (
        (1.0 + values.creep_coefficient)
        * values.steel_modulus_mpa
        / values.concrete_modulus_mpa
        if values.concrete_modulus_mpa > 0
        else 0.0
    )
    direct_width_applicable = values.bar_spacing_mm <= 5.0 * (
        values.cover_mm + 0.5 * values.bar_diameter_mm
    )
    strain_difference = (
        _strain_difference(values, tensile_strength, ratio, modular_ratio)
        if direct_width_applicable
        else None
    )
    crack_spacing = (
        _maximum_crack_spacing(values, ratio)
        if direct_width_applicable
        else None
    )
    crack_width = (
        crack_spacing * strain_difference
        if crack_spacing is not None and strain_difference is not None
        else None
    )
    width_util = (
        crack_width / values.crack_width_limit_mm
        if crack_width is not None and values.crack_width_limit_mm > 0
        else None
    )
    return CrackControlResult(
        d_eff=d_eff,
        height_eff=height_eff,
        Aceff=effective_area,
        rho_eff=ratio,
        sigma_table_A=sigma_a,
        sigma_table_B=sigma_b,
        sigma_table_combined=sigma_combined,
        sigma_08fsy=sigma_strength_limit,
        sigma_allow_table=sigma_allow,
        utilisation_table=table_util,
        passes_table=table_util <= 1.0,
        direct_width_applicable=direct_width_applicable,
        fct_eff=tensile_strength,
        ne=modular_ratio,
        eps_diff=strain_difference,
        sr_max=crack_spacing,
        w_calc=crack_width,
        utilisation_w=width_util,
        passes_w=width_util <= 1.0 if width_util is not None else None,
    )


def _table_stress(table: dict, value: float, width_limit: float) -> float:
    width_key = min((0.2, 0.3, 0.4), key=lambda item: abs(item - width_limit))
    value_key = min(sorted(table), key=lambda item: abs(item - value))
    return float(table[value_key][width_key])


def _strain_difference(
    values: CrackControlInput, tensile_strength: float, ratio: float, modular_ratio: float
) -> float:
    if ratio <= 0:
        return 0.0
    term1 = values.outer_steel_stress_mpa / values.steel_modulus_mpa
    term2 = (
        0.6
        * tensile_strength
        / (values.steel_modulus_mpa * ratio)
        * (1.0 + modular_ratio * ratio)
    )
    return max(
        term1 - term2 + values.shrinkage_strain,
        0.6 * values.outer_steel_stress_mpa / values.steel_modulus_mpa,
    )


def _maximum_crack_spacing(values: CrackControlInput, ratio: float) -> float:
    if ratio <= 0:
        return 0.0
    return (
        3.4 * values.cover_mm
        + 0.3
        * values.bond_factor
        * values.strain_distribution_factor
        * values.bar_diameter_mm
        / ratio
    )


def _validate_finite(values: CrackControlInput) -> None:
    for name, value in vars(values).items():
        if isinstance(value, (int, float)) and not math.isfinite(float(value)):
            raise ValueError(f"{name} must be finite")


__all__ = ["CrackControlInput", "CrackControlResult", "calculate_crack_control"]
