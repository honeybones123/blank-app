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
)
from inputs_v2.engineering.engineering_calculator import EngineeringCalculator


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
