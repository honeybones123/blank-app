"""Isolated dispatch and verified standard-specific calculation branches.

The existing AS 3600 page calculations remain in their current modules. This
module introduces no session-state or UI dependency.
"""

from __future__ import annotations

import math

from application.contracts.concrete_crack_shrinkage import (
    AS5100WallCrackControlInput,
    AS5100WallCrackControlResult,
    C766CrackControlInput,
    C766CrackControlResult,
    C766EndRestraintInput,
    C766EndRestraintResult,
    C766MinimumReinforcementInput,
    C766MinimumReinforcementResult,
    CementClass,
    CrackControlMethod,
    EC2C766ShrinkageInput,
    EC2C766ShrinkageResult,
    MethodReference,
    ShrinkageMethod,
)


AS5100_WALL_REFERENCE = MethodReference(
    document="AS 5100.5",
    edition="2017 incorporating Amendment No. 1 (November 2018)",
    clause="11.7.2",
)

C766_REFERENCE = MethodReference(
    document="CIRIA C766",
    edition="2018 revised with errata 2019 and 2020",
    clause="Equations 3.1, 3.6, 3.20-3.23",
)

EC2_C766_SHRINKAGE_REFERENCE = MethodReference(
    document="CIRIA C766 / BS EN 1992-1-1:2004",
    edition="C766 Appendix A3-A4, revised with errata 2019 and 2020",
    clause="Equations A3.1-A3.5 and A4.1-A4.3",
)


def calculate_as5100_wall_crack_control(
    inputs: AS5100WallCrackControlInput,
) -> AS5100WallCrackControlResult:
    """Calculate restrained-wall horizontal reinforcement per AS 5100.5 Cl 11.7.2.

    Required areas are reported per face for a one-metre-wide wall strip. For
    walls thicker than 500 mm, the clause note permits 250 mm to be used near
    each surface. This calculation is only the Clause 11.7.2 crack-control
    minimum; strength and Clause 11.7.1 requirements remain separate gates.
    """
    thickness = float(inputs.wall_thickness_mm)
    if thickness <= 0.0:
        raise ValueError("wall_thickness_mm must be greater than zero")
    if inputs.provided_horizontal_area_per_face_mm2_per_m is not None:
        if inputs.provided_horizontal_area_per_face_mm2_per_m < 0.0:
            raise ValueError("provided horizontal reinforcement area cannot be negative")
    if inputs.provided_vertical_spacing_mm is not None:
        if inputs.provided_vertical_spacing_mm <= 0.0:
            raise ValueError("provided vertical spacing must be greater than zero")

    design_strip_width_mm = 1_000.0
    calculation_thickness_mm = 250.0 if thickness > 500.0 else thickness / 2.0
    required_ratio = 0.011 if inputs.in_base_zone else 0.008
    if not inputs.restrained_for_shrinkage_or_temperature:
        required_ratio = 0.0

    required_area = required_ratio * calculation_thickness_mm * design_strip_width_mm
    maximum_spacing = min(2.5 * thickness, 300.0)
    if inputs.in_base_zone:
        maximum_spacing = min(maximum_spacing, 150.0)

    provided_area = inputs.provided_horizontal_area_per_face_mm2_per_m
    provided_spacing = inputs.provided_vertical_spacing_mm
    area_utilisation = None
    area_passes = None
    spacing_passes = None
    if provided_area is not None:
        area_utilisation = required_area / provided_area if provided_area > 0.0 else float("inf")
        area_passes = provided_area >= required_area
    if provided_spacing is not None:
        spacing_passes = provided_spacing <= maximum_spacing

    passes = None
    checks = [check for check in (area_passes, spacing_passes) if check is not None]
    if checks:
        passes = all(checks)

    warnings = (
        "Clause 11.7.2 is a crack-control minimum only; also check Clause 11.7.1 and strength requirements.",
    )
    if not inputs.restrained_for_shrinkage_or_temperature:
        warnings += (
            "Clause 11.7.2 restrained-wall ratio was not applied because restraint was declared absent.",
        )

    return AS5100WallCrackControlResult(
        method=CrackControlMethod.AS5100_WALL,
        reference=AS5100_WALL_REFERENCE,
        design_strip_width_mm=design_strip_width_mm,
        calculation_thickness_per_face_mm=calculation_thickness_mm,
        required_ratio=required_ratio,
        required_area_per_face_mm2_per_m=required_area,
        maximum_spacing_mm=maximum_spacing,
        provided_area_per_face_mm2_per_m=provided_area,
        provided_spacing_mm=provided_spacing,
        area_utilisation=area_utilisation,
        area_passes=area_passes,
        spacing_passes=spacing_passes,
        passes=passes,
        warnings=warnings,
    )


def dispatch_crack_control(
    method: CrackControlMethod,
    inputs: AS5100WallCrackControlInput,
) -> AS5100WallCrackControlResult:
    """Dispatch a typed crack-control request to its isolated implementation."""
    if method is CrackControlMethod.AS5100_WALL:
        return calculate_as5100_wall_crack_control(inputs)
    raise NotImplementedError(f"No typed dispatcher implementation for {method.value!r}")


def calculate_c766_crack_control(inputs: C766CrackControlInput) -> C766CrackControlResult:
    """Evaluate the C766 restrained-strain and EC2 crack-width equation chain.

    Strains use dimensionless units. Temperature prediction and restraint-factor
    derivation remain upstream inputs so this function does not imply parity with
    the corrected proprietary CIRIA spreadsheets.
    """
    non_negative = {
        "temperature_drop_early_c": inputs.temperature_drop_early_c,
        "temperature_change_long_term_c": inputs.temperature_change_long_term_c,
        "thermal_expansion_per_c": inputs.thermal_expansion_per_c,
        "autogenous_shrinkage_early": inputs.autogenous_shrinkage_early,
        "autogenous_shrinkage_long_term": inputs.autogenous_shrinkage_long_term,
        "drying_shrinkage": inputs.drying_shrinkage,
        "tensile_strain_capacity": inputs.tensile_strain_capacity,
    }
    for name, value in non_negative.items():
        if value < 0.0:
            raise ValueError(f"{name} cannot be negative")
    for name, value in (
        ("restraint_early", inputs.restraint_early),
        ("restraint_medium", inputs.restraint_medium),
        ("restraint_long_term", inputs.restraint_long_term),
    ):
        if not 0.0 <= value <= 1.0:
            raise ValueError(f"{name} must be between zero and one")

    if inputs.restraint_type.value == "end":
        raise NotImplementedError(
            "C766 end-restraint crack-inducing strain requires the separate Equation 3.12 material/reinforcement contract"
        )
    if inputs.restraint_type.value == "internal":
        restrained_strain = (
            inputs.creep_coefficient_early
            * inputs.temperature_drop_early_c
            * inputs.thermal_expansion_per_c
            * inputs.restraint_early
        )
    else:
        restrained_strain = (
            inputs.creep_coefficient_early
            * (inputs.thermal_expansion_per_c * inputs.temperature_drop_early_c + inputs.autogenous_shrinkage_early)
            * inputs.restraint_early
            + inputs.creep_coefficient_early
            * (
                inputs.autogenous_shrinkage_long_term - inputs.autogenous_shrinkage_early
                + inputs.thermal_expansion_per_c * inputs.temperature_change_long_term_c
            )
            * inputs.restraint_medium
            + inputs.creep_coefficient_long_term
            * inputs.drying_shrinkage
            * inputs.restraint_long_term
        )
    crack_initiates = restrained_strain > inputs.tensile_strain_capacity
    crack_inducing_strain = max(restrained_strain - 0.5 * inputs.tensile_strain_capacity, 0.0)

    spacing_inputs = (
        inputs.cover_mm,
        inputs.bar_diameter_mm,
        inputs.effective_reinforcement_ratio,
    )
    maximum_spacing = None
    crack_width = None
    if any(value is not None for value in spacing_inputs) and not all(
        value is not None for value in spacing_inputs
    ):
        raise ValueError("cover, bar diameter and effective reinforcement ratio must be supplied together")
    if all(value is not None for value in spacing_inputs):
        cover = float(inputs.cover_mm)
        diameter = float(inputs.bar_diameter_mm)
        ratio = float(inputs.effective_reinforcement_ratio)
        if cover < 0.0 or diameter <= 0.0 or ratio <= 0.0:
            raise ValueError("crack-spacing geometry and reinforcement ratio must be positive")
        maximum_spacing = (
            inputs.crack_spacing_k3 * cover
            + inputs.crack_spacing_k4
            * inputs.bond_coefficient_k1
            * inputs.strain_distribution_k2
            * diameter
            / ratio
        )
        crack_width = maximum_spacing * crack_inducing_strain

    return C766CrackControlResult(
        method=CrackControlMethod.CIRIA_C766_EC2,
        reference=C766_REFERENCE,
        restrained_strain=restrained_strain,
        crack_initiates=crack_initiates,
        crack_inducing_strain=crack_inducing_strain,
        maximum_crack_spacing_mm=maximum_spacing,
        characteristic_crack_width_mm=crack_width,
        warnings=(
            "Temperature changes and restraint factors are explicit design inputs; no CIRIA spreadsheet-parity claim is made.",
        ),
    )


def calculate_c766_minimum_reinforcement(
    inputs: C766MinimumReinforcementInput,
) -> C766MinimumReinforcementResult:
    """Calculate C766 Equation 3.20 minimum reinforcement for edge restraint."""
    if inputs.concrete_tension_area_mm2 <= 0.0:
        raise ValueError("concrete_tension_area_mm2 must be greater than zero")
    if inputs.mean_tensile_strength_at_cracking_mpa <= 0.0:
        raise ValueError("mean tensile strength must be greater than zero")
    if inputs.reinforcement_yield_strength_mpa <= 0.0:
        raise ValueError("reinforcement yield strength must be greater than zero")
    if not 0.0 <= inputs.edge_restraint_factor <= 1.0:
        raise ValueError("edge restraint factor must be between zero and one")
    edge_load_transfer = 1.0 - 0.5 * inputs.edge_restraint_factor
    required_area = (
        edge_load_transfer
        * inputs.stress_distribution_coefficient_kc
        * inputs.non_uniform_stress_coefficient_k
        * inputs.concrete_tension_area_mm2
        * (0.7 * inputs.mean_tensile_strength_at_cracking_mpa)
        / inputs.reinforcement_yield_strength_mpa
    )
    return C766MinimumReinforcementResult(
        required_area_mm2=required_area,
        edge_load_transfer_coefficient=edge_load_transfer,
        reference=C766_REFERENCE,
    )


def _crack_spacing_and_width(
    *,
    crack_inducing_strain: float,
    cover_mm: float | None,
    bar_diameter_mm: float | None,
    effective_reinforcement_ratio: float | None,
    k1: float,
    k2: float,
    k3: float,
    k4: float,
) -> tuple[float | None, float | None]:
    values = (cover_mm, bar_diameter_mm, effective_reinforcement_ratio)
    if any(value is not None for value in values) and not all(value is not None for value in values):
        raise ValueError("cover, bar diameter and effective reinforcement ratio must be supplied together")
    if not all(value is not None for value in values):
        return None, None
    cover = float(cover_mm)
    diameter = float(bar_diameter_mm)
    ratio = float(effective_reinforcement_ratio)
    if cover < 0.0 or diameter <= 0.0 or ratio <= 0.0:
        raise ValueError("crack-spacing geometry and reinforcement ratio must be positive")
    spacing = k3 * cover + k4 * k1 * k2 * diameter / ratio
    return spacing, spacing * crack_inducing_strain


def calculate_c766_end_restraint(
    inputs: C766EndRestraintInput,
) -> C766EndRestraintResult:
    """Calculate C766 Equation 3.12 end-restraint crack-inducing strain."""
    positive = {
        "effective_modular_ratio": inputs.effective_modular_ratio,
        "non_uniform_stress_coefficient_k": inputs.non_uniform_stress_coefficient_k,
        "stress_distribution_coefficient_kc": inputs.stress_distribution_coefficient_kc,
        "characteristic_tensile_strength_at_cracking_mpa": inputs.characteristic_tensile_strength_at_cracking_mpa,
        "reinforcement_modulus_mpa": inputs.reinforcement_modulus_mpa,
        "reinforcement_ratio_total_to_tension_area": inputs.reinforcement_ratio_total_to_tension_area,
    }
    for name, value in positive.items():
        if value <= 0.0:
            raise ValueError(f"{name} must be greater than zero")
    crack_inducing = (
        0.5
        * inputs.effective_modular_ratio
        * inputs.non_uniform_stress_coefficient_k
        * inputs.stress_distribution_coefficient_kc
        * inputs.characteristic_tensile_strength_at_cracking_mpa
        / inputs.reinforcement_modulus_mpa
        * (
            1.0
            + 1.0
            / (
                inputs.effective_modular_ratio
                * inputs.reinforcement_ratio_total_to_tension_area
            )
        )
    )
    spacing, width = _crack_spacing_and_width(
        crack_inducing_strain=crack_inducing,
        cover_mm=inputs.cover_mm,
        bar_diameter_mm=inputs.bar_diameter_mm,
        effective_reinforcement_ratio=inputs.effective_reinforcement_ratio,
        k1=inputs.bond_coefficient_k1,
        k2=inputs.strain_distribution_k2,
        k3=inputs.crack_spacing_k3,
        k4=inputs.crack_spacing_k4,
    )
    return C766EndRestraintResult(
        method=CrackControlMethod.CIRIA_C766_EC2,
        reference=C766_REFERENCE,
        crack_inducing_strain=crack_inducing,
        maximum_crack_spacing_mm=spacing,
        characteristic_crack_width_mm=width,
        warnings=(
            "Equation 3.12 provides an upper-bound end-restraint crack width unless a project-specific length/tension-stiffening assessment is made.",
        ),
    )


def _ec2_size_coefficient(notional_size_mm: float) -> float:
    """Interpolate BS EN 1992-1-1 Table 3.3 values reproduced in C766 Figure A3.2."""
    points = ((100.0, 1.0), (200.0, 0.85), (300.0, 0.75), (500.0, 0.70))
    if notional_size_mm <= points[0][0]:
        return points[0][1]
    if notional_size_mm >= points[-1][0]:
        return points[-1][1]
    for (x0, y0), (x1, y1) in zip(points, points[1:]):
        if x0 <= notional_size_mm <= x1:
            fraction = (notional_size_mm - x0) / (x1 - x0)
            return y0 + fraction * (y1 - y0)
    raise AssertionError("notional-size interpolation interval not found")


def calculate_ec2_c766_shrinkage(inputs: EC2C766ShrinkageInput) -> EC2C766ShrinkageResult:
    """Calculate EC2 drying and autogenous shrinkage using C766 Appendices A3-A4."""
    if inputs.characteristic_cylinder_strength_mpa <= 0.0:
        raise ValueError("characteristic cylinder strength must be greater than zero")
    if not 0.0 <= inputs.relative_humidity_percent <= 100.0:
        raise ValueError("relative humidity must be between zero and 100 percent")
    if inputs.concrete_area_mm2 <= 0.0 or inputs.drying_perimeter_mm <= 0.0:
        raise ValueError("concrete area and drying perimeter must be greater than zero")
    if inputs.age_days < 0.0 or inputs.drying_start_age_days < 0.0:
        raise ValueError("ages cannot be negative")

    cement_coefficients = {
        CementClass.SLOW: (3.0, 0.13),
        CementClass.NORMAL: (4.0, 0.12),
        CementClass.RAPID: (6.0, 0.11),
    }
    alpha_ds1, alpha_ds2 = cement_coefficients[inputs.cement_class]
    mean_strength = inputs.characteristic_cylinder_strength_mpa + 8.0
    beta_rh = 1.55 * (1.0 - (inputs.relative_humidity_percent / 100.0) ** 3)
    nominal_drying = (
        0.85
        * (
            220.0
            + 110.0
            * alpha_ds1
            * math.exp(-alpha_ds2 * mean_strength / 10.0)
        )
        * 1e-6
        * beta_rh
    )
    notional_size = 2.0 * inputs.concrete_area_mm2 / inputs.drying_perimeter_mm
    kh = _ec2_size_coefficient(notional_size)
    drying_duration = max(inputs.age_days - inputs.drying_start_age_days, 0.0)
    beta_ds = (
        drying_duration
        / (drying_duration + 0.04 * math.sqrt(notional_size**3))
        if drying_duration > 0.0
        else 0.0
    )
    drying = beta_ds * kh * nominal_drying
    ultimate_autogenous = 2.5 * max(inputs.characteristic_cylinder_strength_mpa - 10.0, 0.0) * 1e-6
    beta_as = 1.0 - math.exp(-0.2 * math.sqrt(inputs.age_days))
    autogenous = beta_as * ultimate_autogenous
    return EC2C766ShrinkageResult(
        method=ShrinkageMethod.EC2_C766,
        reference=EC2_C766_SHRINKAGE_REFERENCE,
        mean_compressive_strength_mpa=mean_strength,
        notional_size_mm=notional_size,
        nominal_drying_shrinkage=nominal_drying,
        size_coefficient_kh=kh,
        drying_time_coefficient=beta_ds,
        drying_shrinkage=drying,
        autogenous_shrinkage=autogenous,
        total_shrinkage=drying + autogenous,
        warnings=(
            "This is the published EC2 equation path reproduced in C766 Appendices A3-A4; it does not claim parity with CIRIA's corrected spreadsheets.",
        ),
    )


def dispatch_shrinkage(
    method: ShrinkageMethod,
    inputs: EC2C766ShrinkageInput,
) -> EC2C766ShrinkageResult:
    if method is ShrinkageMethod.EC2_C766:
        return calculate_ec2_c766_shrinkage(inputs)
    raise NotImplementedError(f"No typed dispatcher implementation for {method.value!r}")
