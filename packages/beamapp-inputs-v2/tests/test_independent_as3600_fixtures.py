"""Standard-derived engineering fixtures independent of production outputs.

Authorities were visually reviewed against AS 3600:2018(+A1):
- Clause 3.1.1.3, PDF page 46 (printed page 44): f'ct.f = 0.6 sqrt(f'c)
- Table 2.2.2, PDF page 38 (printed page 36): bending phi expression
- Clause 8.1.3, PDF page 112 (printed page 110): rectangular stress block
- Clause 8.1.6.1, PDF page 113 (printed page 111): minimum tensile steel
- Clauses 8.2.1.9, 8.2.3.1, 8.2.3.3 and 8.2.4.1, PDF pages 117-119
  (printed pages 115-117): shear depth, strength and web crushing

Expected values below are evaluated from those equations, not copied from an
EngineeringCalculator result.  Production is imported only inside the tests.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import pi, radians, sqrt, tan

import pytest

from inputs_v2.domain.beam_inputs import (
    ActionInputs,
    BeamInputs,
    LongitudinalReinforcement,
    MaterialInputs,
    ServiceabilityInputs,
)
from inputs_v2.engineering.engineering_calculator import EngineeringCalculator
from inputs_v2.engineering.deflection import DeflectionInput, calculate_deflection
from inputs_v2.engineering.crack_control import (
    CrackControlInput,
    calculate_crack_control,
)
from inputs_v2.engineering.reinforcement_fit import evaluate_arrangement
from inputs_v2.domain.beam_inputs import ShearReinforcement
from inputs_v2.application.design_brain_families import (
    DesignFamily,
    classify_design_family,
)


@dataclass(frozen=True, slots=True)
class RectangularFlexureFixture:
    fixture_id: str
    width_mm: float
    depth_mm: float
    cover_mm: float
    bar_count: int
    bar_diameter_mm: float
    concrete_strength_mpa: float
    steel_strength_mpa: float
    demand_knm: float
    clauses: tuple[str, ...]
    review_status: str = "STANDARD_DERIVED_VISUALLY_REVIEWED"


RECTANGULAR_FLEXURE = RectangularFlexureFixture(
    fixture_id="as3600_rectangular_300x500_4n20_fc32",
    width_mm=300.0,
    depth_mm=500.0,
    cover_mm=40.0,
    bar_count=4,
    bar_diameter_mm=20.0,
    concrete_strength_mpa=32.0,
    steel_strength_mpa=500.0,
    demand_knm=150.0,
    clauses=("3.1.1.3", "Table 2.2.2(b)(i)", "8.1.3", "8.1.6.1"),
)


def _standard_derived_values(case: RectangularFlexureFixture) -> dict[str, float]:
    effective_depth = case.depth_mm - case.cover_mm - case.bar_diameter_mm / 2.0
    steel_area = case.bar_count * pi * case.bar_diameter_mm**2 / 4.0
    alpha2 = max(0.67, 0.85 - 0.0015 * case.concrete_strength_mpa)
    gamma = max(0.67, 0.97 - 0.0025 * case.concrete_strength_mpa)
    neutral_axis = steel_area * case.steel_strength_mpa / (
        alpha2
        * case.concrete_strength_mpa
        * gamma
        * case.width_mm
    )
    ku = neutral_axis / effective_depth
    phi = min(0.85, max(0.65, 1.24 - 13.0 * ku / 12.0))
    nominal_moment = (
        steel_area
        * case.steel_strength_mpa
        * (effective_depth - gamma * neutral_axis / 2.0)
        / 1e6
    )
    flexural_tensile_strength = 0.6 * sqrt(case.concrete_strength_mpa)
    alpha_b = 0.20  # Rectangular section, Clause 8.1.6.1.
    minimum_steel = (
        alpha_b
        * (case.depth_mm / effective_depth) ** 2
        * (flexural_tensile_strength / case.steel_strength_mpa)
        * case.width_mm
        * effective_depth
    )
    return {
        "effective_depth_mm": effective_depth,
        "steel_area_mm2": steel_area,
        "alpha2": alpha2,
        "gamma": gamma,
        "neutral_axis_mm": neutral_axis,
        "ku": ku,
        "phi": phi,
        "nominal_moment_knm": nominal_moment,
        "design_moment_knm": phi * nominal_moment,
        "minimum_steel_mm2": minimum_steel,
    }


def _production_result(case: RectangularFlexureFixture) -> dict[str, object]:
    inputs = BeamInputs(
        width_mm=case.width_mm,
        depth_mm=case.depth_mm,
        bottom=LongitudinalReinforcement(
            bars=case.bar_count,
            diameter_mm=case.bar_diameter_mm,
            cover_mm=case.cover_mm,
        ),
        materials=MaterialInputs(
            concrete_strength_mpa=case.concrete_strength_mpa,
            reinforcement_strength_mpa=case.steel_strength_mpa,
        ),
        actions=ActionInputs(bending_moment_knm=case.demand_knm),
    ).validated()
    return EngineeringCalculator().calculate(inputs).families["bending"]


def test_rectangular_bending_matches_standard_derived_fixture() -> None:
    case = RECTANGULAR_FLEXURE
    expected = _standard_derived_values(case)
    actual = _production_result(case)

    assert case.review_status == "STANDARD_DERIVED_VISUALLY_REVIEWED"
    assert actual["d_mm"] == pytest.approx(expected["effective_depth_mm"], rel=1e-12)
    assert actual["Ast_tension_mm2"] == pytest.approx(expected["steel_area_mm2"], rel=1e-12)
    assert actual["alpha2"] == pytest.approx(expected["alpha2"], rel=1e-12)
    assert actual["gamma"] == pytest.approx(expected["gamma"], rel=1e-12)
    assert actual["dn_mm"] == pytest.approx(expected["neutral_axis_mm"], rel=1e-12)
    assert actual["ku"] == pytest.approx(expected["ku"], rel=1e-12)
    assert actual["phi"] == pytest.approx(expected["phi"], rel=1e-12)
    assert actual["Mu_nom_kNm"] == pytest.approx(expected["nominal_moment_knm"], rel=1e-12)
    assert actual["phi_Mu_kNm"] == pytest.approx(expected["design_moment_knm"], rel=1e-12)


def test_minimum_tensile_steel_matches_standard_derived_fixture() -> None:
    case = RECTANGULAR_FLEXURE
    expected = _standard_derived_values(case)
    actual = _production_result(case)

    assert actual["Ast_min_mm2"] == pytest.approx(
        expected["minimum_steel_mm2"], rel=1e-12
    )


def test_unreinforced_shear_matches_standard_derived_fixture() -> None:
    """Verify the declared simplified-method branch from standard equations."""

    case = RECTANGULAR_FLEXURE
    shear_demand_kn = 40.0
    effective_depth = case.depth_mm - case.cover_mm - case.bar_diameter_mm / 2.0
    shear_depth = max(0.72 * case.depth_mm, 0.9 * effective_depth)
    # The calculator explicitly selects the Clause 8.2.4.3 simplified branch.
    kv = min(200.0 / (1000.0 + 1.3 * shear_depth), 0.10)
    theta = radians(36.0)
    concrete_capacity_kn = (
        kv
        * case.width_mm
        * shear_depth
        * min(sqrt(case.concrete_strength_mpa), 8.0)
        / 1000.0
    )
    shear_phi = 0.75  # Table 2.2.2(e)(i), Class N fitments.
    cot_theta = 1.0 / tan(theta)
    web_capacity_kn = (
        0.55
        * case.concrete_strength_mpa
        * case.width_mm
        * shear_depth
        * (cot_theta / (1.0 + cot_theta**2))
        / 1000.0
    )
    inputs = BeamInputs(
        width_mm=case.width_mm,
        depth_mm=case.depth_mm,
        bottom=LongitudinalReinforcement(
            bars=case.bar_count,
            diameter_mm=case.bar_diameter_mm,
            cover_mm=case.cover_mm,
        ),
        materials=MaterialInputs(
            concrete_strength_mpa=case.concrete_strength_mpa,
            reinforcement_strength_mpa=case.steel_strength_mpa,
        ),
        actions=ActionInputs(shear_force_kn=shear_demand_kn),
    ).validated()
    actual = EngineeringCalculator().calculate(inputs).families["shear"]

    assert actual["d_v"] == pytest.approx(shear_depth, rel=1e-12)
    assert actual["k_v"] == pytest.approx(kv, rel=1e-12)
    assert actual["Vuc_kN"] == pytest.approx(concrete_capacity_kn, rel=1e-12)
    assert actual["Vus_kN"] == pytest.approx(0.0, abs=1e-12)
    assert actual["phi_Vu"] == pytest.approx(
        shear_phi * concrete_capacity_kn, rel=1e-12
    )
    assert actual["Vu_max_kN"] == pytest.approx(web_capacity_kn, rel=1e-12)
    assert actual["shear_ok"] is (shear_phi * concrete_capacity_kn >= shear_demand_kn)
    assert actual["web_ok"] is (shear_phi * web_capacity_kn >= shear_demand_kn)


def test_continuous_end_span_deflection_matches_standard_derived_fixture() -> None:
    """Generic Continuous uses the conservative end-span Clause 8.5.4 case."""

    values = DeflectionInput(
        span_m=6.0,
        concrete_modulus_mpa=30_000.0,
        concrete_strength_mpa=32.0,
        effective_width_mm=300.0,
        web_width_mm=300.0,
        effective_depth_mm=450.0,
        tension_steel_area_mm2=4.0 * pi * 20.0**2 / 4.0,
        compression_steel_area_mm2=2.0 * pi * 10.0**2 / 4.0,
        permanent_udl_kn_per_m=8.0,
        imposed_udl_kn_per_m=3.0,
        sustained_load_factor=0.4,
        support_condition="Continuous",
    )
    beta = values.effective_width_mm / values.web_width_mm
    reinforcement_ratio = values.tension_steel_area_mm2 / (
        values.effective_width_mm * values.effective_depth_mm
    )
    ratio_limit = (
        0.001
        * values.concrete_strength_mpa ** (1.0 / 3.0)
        / beta ** (2.0 / 3.0)
    )
    assert reinforcement_ratio >= ratio_limit
    k1 = (5.0 - 0.04 * values.concrete_strength_mpa) * reinforcement_ratio + 0.002
    inertia = min(
        k1 * values.effective_width_mm * values.effective_depth_mm**3,
        0.1
        * values.effective_width_mm
        * values.effective_depth_mm**3
        / beta ** (2.0 / 3.0),
    )
    coefficient = 2.4 / 384.0  # Continuous end span, conservative generic case.
    span_mm = values.span_m * 1000.0
    total_load = values.permanent_udl_kn_per_m + values.imposed_udl_kn_per_m
    sustained_load = (
        values.permanent_udl_kn_per_m
        + values.sustained_load_factor * values.imposed_udl_kn_per_m
    )
    short_term = (
        coefficient
        * total_load
        * span_mm**4
        / (values.concrete_modulus_mpa * inertia)
    )
    sustained_short = (
        coefficient
        * sustained_load
        * span_mm**4
        / (values.concrete_modulus_mpa * inertia)
    )
    kcs = max(
        2.0
        - 1.2
        * values.compression_steel_area_mm2
        / values.tension_steel_area_mm2,
        0.8,
    )
    actual = calculate_deflection(values)

    assert actual.effective_inertia_mm4 == pytest.approx(inertia, rel=1e-12)
    assert actual.support_coefficient == pytest.approx(coefficient, rel=1e-12)
    assert actual.short_term_mm == pytest.approx(short_term, rel=1e-12)
    assert actual.sustained_short_term_mm == pytest.approx(
        sustained_short, rel=1e-12
    )
    assert actual.sustained_deflection_factor == pytest.approx(kcs, rel=1e-12)
    assert actual.long_term_addition_mm == pytest.approx(
        kcs * sustained_short, rel=1e-12
    )
    assert actual.total_mm == pytest.approx(
        short_term + kcs * sustained_short, rel=1e-12
    )


def test_crack_control_matches_standard_derived_fixture() -> None:
    """Verify Table 8.6.2.2 and direct-width Clause 8.6.2.3 independently."""

    width = 300.0
    depth = 600.0
    cover = 40.0
    diameter = 20.0
    spacing = 150.0
    steel_area = 4.0 * pi * diameter**2 / 4.0
    neutral_axis = 180.0
    steel_stress = 180.0
    steel_modulus = 200_000.0
    concrete_modulus = 30_000.0
    concrete_strength = 40.0
    creep = 2.0
    shrinkage = 300e-6
    k1 = 0.8
    k2 = 0.5
    limit = 0.3

    effective_depth = depth - cover - diameter / 2.0
    effective_height = min(
        2.5 * (depth - effective_depth),
        (depth - neutral_axis) / 3.0,
        depth / 2.0,
    )
    effective_area = width * effective_height
    reinforcement_ratio = steel_area / effective_area
    mean_axial_tensile_strength = 1.4 * 0.36 * sqrt(concrete_strength)
    effective_modular_ratio = (1.0 + creep) * steel_modulus / concrete_modulus
    strain_difference = max(
        steel_stress / steel_modulus
        - 0.6
        * mean_axial_tensile_strength
        / (steel_modulus * reinforcement_ratio)
        * (1.0 + effective_modular_ratio * reinforcement_ratio)
        + shrinkage,
        0.6 * steel_stress / steel_modulus,
    )
    maximum_spacing = (
        3.4 * cover + 0.3 * k1 * k2 * diameter / reinforcement_ratio
    )
    crack_width = maximum_spacing * strain_difference
    values = CrackControlInput(
        width_mm=width,
        depth_mm=depth,
        cover_mm=cover,
        bar_diameter_mm=diameter,
        bar_spacing_mm=spacing,
        steel_area_mm2=steel_area,
        concrete_strength_mpa=concrete_strength,
        concrete_modulus_mpa=concrete_modulus,
        steel_modulus_mpa=steel_modulus,
        steel_strength_mpa=500.0,
        crack_width_limit_mm=limit,
        member_type="Primarily flexure",
        outer_steel_stress_mpa=steel_stress,
        creep_coefficient=creep,
        shrinkage_strain=shrinkage,
        bond_factor=k1,
        strain_distribution_factor=k2,
        neutral_axis_depth_mm=neutral_axis,
    )
    actual = calculate_crack_control(values)

    assert actual.sigma_table_A == pytest.approx(195.0, abs=1e-12)
    assert actual.sigma_table_B == pytest.approx(245.0, abs=1e-12)
    assert actual.sigma_allow_table == pytest.approx(245.0, abs=1e-12)
    assert actual.utilisation_table == pytest.approx(steel_stress / 245.0, rel=1e-12)
    assert actual.d_eff == pytest.approx(effective_depth, rel=1e-12)
    assert actual.height_eff == pytest.approx(effective_height, rel=1e-12)
    assert actual.Aceff == pytest.approx(effective_area, rel=1e-12)
    assert actual.rho_eff == pytest.approx(reinforcement_ratio, rel=1e-12)
    assert actual.fct_eff == pytest.approx(mean_axial_tensile_strength, rel=1e-12)
    assert actual.ne == pytest.approx(effective_modular_ratio, rel=1e-12)
    assert actual.eps_diff == pytest.approx(strain_difference, rel=1e-12)
    assert actual.sr_max == pytest.approx(maximum_spacing, rel=1e-12)
    assert actual.w_calc == pytest.approx(crack_width, rel=1e-12)
    assert actual.utilisation_w == pytest.approx(crack_width / limit, rel=1e-12)


def test_direct_crack_width_is_not_claimed_outside_spacing_limit() -> None:
    values = CrackControlInput(
        width_mm=300.0,
        depth_mm=600.0,
        cover_mm=40.0,
        bar_diameter_mm=10.0,
        bar_spacing_mm=300.0,
        steel_area_mm2=4.0 * pi * 10.0**2 / 4.0,
        concrete_strength_mpa=40.0,
        concrete_modulus_mpa=30_000.0,
        steel_modulus_mpa=200_000.0,
        steel_strength_mpa=500.0,
        crack_width_limit_mm=0.3,
        member_type="Primarily flexure",
        outer_steel_stress_mpa=120.0,
        creep_coefficient=2.0,
        shrinkage_strain=300e-6,
        bond_factor=0.8,
        strain_distribution_factor=0.5,
        neutral_axis_depth_mm=180.0,
    )
    assert values.bar_spacing_mm > 5.0 * (
        values.cover_mm + 0.5 * values.bar_diameter_mm
    )
    actual = calculate_crack_control(values)

    assert not actual.direct_width_applicable
    assert actual.eps_diff is None
    assert actual.sr_max is None
    assert actual.w_calc is None
    assert actual.utilisation_w is None
    assert actual.passes_w is None


def test_reinforcement_fit_matches_independent_geometry_fixture() -> None:
    inputs = BeamInputs(
        width_mm=300.0,
        depth_mm=500.0,
        bottom=LongitudinalReinforcement(
            bars=4,
            diameter_mm=20,
            cover_mm=40.0,
        ),
        shear=ShearReinforcement(
            diameter_mm=10,
            legs=2,
            spacing_mm=200.0,
        ),
    ).validated()
    fit = evaluate_arrangement(inputs, (4,))
    usable_width = 300.0 - 2.0 * (40.0 + 10.0)
    clear_spacing = (usable_width - 4.0 * 20.0) / 3.0
    row_centre = 40.0 + 10.0 + 20.0 / 2.0

    assert fit.accepted
    assert fit.arrangement.rows[0].clear_spacing_mm == pytest.approx(
        clear_spacing, rel=1e-12
    )
    assert fit.congestion.horizontal_clearance_margin_mm == pytest.approx(
        clear_spacing - 20.0, rel=1e-12
    )
    assert fit.arrangement.reinforcement_centroid_mm == pytest.approx(
        row_centre, rel=1e-12
    )
    assert fit.arrangement.effective_depth_mm == pytest.approx(
        inputs.depth_mm - row_centre, rel=1e-12
    )
    result = EngineeringCalculator().calculate(inputs)
    reinforcement = result.families["reinforcement_fit"]
    geometry = result.families["geometry"]
    assert reinforcement["cover_status"] == "NOT CHECKED"
    assert reinforcement["cover_check_basis"] == "specified_cover_only"
    assert geometry["policy_basis"] == "application_constructability"


@pytest.mark.parametrize(
    ("bending_ratio", "shear_ratio", "expected_family"),
    (
        (1.20, 1.20, DesignFamily.BENDING_AND_SHEAR_FAIL_GOVERN),
        (0.40, 0.40, DesignFamily.COMBINED_OVERDESIGN),
    ),
)
def test_combined_family_matches_independent_strength_predicates(
    bending_ratio: float,
    shear_ratio: float,
    expected_family: DesignFamily,
) -> None:
    case = RECTANGULAR_FLEXURE
    expected = _standard_derived_values(case)
    effective_depth = expected["effective_depth_mm"]
    shear_depth = max(0.72 * case.depth_mm, 0.9 * effective_depth)
    kv = min(200.0 / (1000.0 + 1.3 * shear_depth), 0.10)
    shear_design_capacity = (
        0.75
        * kv
        * case.width_mm
        * shear_depth
        * min(sqrt(case.concrete_strength_mpa), 8.0)
        / 1000.0
    )
    inputs = BeamInputs(
        width_mm=case.width_mm,
        depth_mm=case.depth_mm,
        bottom=LongitudinalReinforcement(
            bars=case.bar_count,
            diameter_mm=case.bar_diameter_mm,
            cover_mm=case.cover_mm,
        ),
        materials=MaterialInputs(
            concrete_strength_mpa=case.concrete_strength_mpa,
            reinforcement_strength_mpa=case.steel_strength_mpa,
        ),
        actions=ActionInputs(
            bending_moment_knm=bending_ratio * expected["design_moment_knm"],
            shear_force_kn=shear_ratio * shear_design_capacity,
        ),
    ).validated()
    result = EngineeringCalculator().calculate(inputs)
    actual_bending_ratio = float(result.families["bending"]["util"])
    actual_shear_ratio = inputs.actions.shear_force_kn / float(
        result.families["shear"]["phi_Vu"]
    )

    assert actual_bending_ratio == pytest.approx(bending_ratio, rel=1e-12)
    assert actual_shear_ratio == pytest.approx(shear_ratio, rel=1e-12)
    assert classify_design_family(result, inputs) is expected_family


def test_serviceability_family_matches_independent_deflection_predicate() -> None:
    case = RECTANGULAR_FLEXURE
    expected = _standard_derived_values(case)
    span_m = 6.0
    permanent_udl = 100.0
    imposed_udl = 50.0
    effective_depth = expected["effective_depth_mm"]
    beta = 1.0
    steel_area = expected["steel_area_mm2"]
    reinforcement_ratio = steel_area / (case.width_mm * effective_depth)
    k1 = (5.0 - 0.04 * case.concrete_strength_mpa) * reinforcement_ratio + 0.002
    inertia = min(
        k1 * case.width_mm * effective_depth**3,
        0.1 * case.width_mm * effective_depth**3 / beta ** (2.0 / 3.0),
    )
    coefficient = 5.0 / 384.0
    span_mm = span_m * 1000.0
    short_term = (
        coefficient
        * (permanent_udl + imposed_udl)
        * span_mm**4
        / (30_000.0 * inertia)
    )
    compression_area = 2.0 * pi * 10.0**2 / 4.0
    kcs = max(2.0 - 1.2 * compression_area / steel_area, 0.8)
    sustained_short = (
        coefficient
        * (permanent_udl + 0.4 * imposed_udl)
        * span_mm**4
        / (30_000.0 * inertia)
    )
    independently_derived_total = short_term + kcs * sustained_short
    limit = span_mm / 250.0
    assert independently_derived_total > limit

    shear_depth = max(0.72 * case.depth_mm, 0.9 * effective_depth)
    shear_design_capacity = (
        0.75
        * min(200.0 / (1000.0 + 1.3 * shear_depth), 0.10)
        * case.width_mm
        * shear_depth
        * min(sqrt(case.concrete_strength_mpa), 8.0)
        / 1000.0
    )
    inputs = BeamInputs(
        width_mm=case.width_mm,
        depth_mm=case.depth_mm,
        span_mm=span_mm,
        bottom=LongitudinalReinforcement(
            bars=case.bar_count,
            diameter_mm=case.bar_diameter_mm,
            cover_mm=case.cover_mm,
        ),
        materials=MaterialInputs(
            concrete_strength_mpa=case.concrete_strength_mpa,
            reinforcement_strength_mpa=case.steel_strength_mpa,
        ),
        actions=ActionInputs(
            bending_moment_knm=0.90 * expected["design_moment_knm"],
            shear_force_kn=0.90 * shear_design_capacity,
        ),
        serviceability=ServiceabilityInputs(
            moment_knm=0.0,
            permanent_udl_knm_per_m=permanent_udl,
            imposed_udl_knm_per_m=imposed_udl,
            sustained_load_factor=0.4,
        ),
    ).validated()
    result = EngineeringCalculator().calculate(inputs)
    serviceability = result.families["serviceability"]

    assert serviceability["deflection_mm"] == pytest.approx(
        independently_derived_total, rel=1e-12
    )
    assert serviceability["deflection_util"] == pytest.approx(
        independently_derived_total / limit, rel=1e-12
    )
    assert serviceability["status"] == "FAIL"
    assert classify_design_family(result, inputs) is DesignFamily.SERVICEABILITY_GOVERNS
