import pytest

from inputs_v2.domain.beam_inputs import (
    BeamInputs,
    ServiceabilityInputs,
    TimeDependentInputs,
)
from inputs_v2.engineering.engineering_calculator import EngineeringCalculator

from inputs_v2.engineering.crack_control import (
    CrackControlInput,
    calculate_crack_control,
)
from inputs_v2.engineering.legacy_snapshot.crack_control import (
    compute_crack_control_values,
)


@pytest.mark.parametrize(
    ("diameter", "spacing", "limit", "member_type", "stress", "face"),
    [
        (10.0, 50.0, 0.2, "Primarily tension", 120.0, "bottom"),
        (16.0, 150.0, 0.3, "Flexure", 180.0, "bottom"),
        (24.0, 225.0, 0.4, "Flexure", 240.0, "top"),
        (40.0, 300.0, 0.3, "Primarily tension", 0.0, "bottom"),
    ],
)
def test_crack_control_uses_clause_8623_effective_tension_area(
    diameter: float,
    spacing: float,
    limit: float,
    member_type: str,
    stress: float,
    face: str,
) -> None:
    values = CrackControlInput(
        width_mm=300.0,
        depth_mm=600.0,
        cover_mm=40.0,
        bar_diameter_mm=diameter,
        bar_spacing_mm=spacing,
        steel_area_mm2=2400.0,
        concrete_strength_mpa=40.0,
        concrete_modulus_mpa=30_000.0,
        steel_modulus_mpa=200_000.0,
        steel_strength_mpa=500.0,
        crack_width_limit_mm=limit,
        member_type=member_type,
        outer_steel_stress_mpa=stress,
        creep_coefficient=2.0,
        shrinkage_strain=650e-6,
        bond_factor=0.8,
        strain_distribution_factor=0.5,
        neutral_axis_depth_mm=180.0,
        tension_face=face,
    )
    current = calculate_crack_control(values).as_family_values()
    legacy = compute_crack_control_values(
        b=values.width_mm,
        D=values.depth_mm,
        c=values.cover_mm,
        db=values.bar_diameter_mm,
        spacing=values.bar_spacing_mm,
        Ast=values.steel_area_mm2,
        fc=values.concrete_strength_mpa,
        Ec=values.concrete_modulus_mpa,
        Es=values.steel_modulus_mpa,
        fsy=values.steel_strength_mpa,
        wmax_choice=values.crack_width_limit_mm,
        member_type=values.member_type,
        sigma_sr=values.outer_steel_stress_mpa,
        phi_ce=values.creep_coefficient,
        eps_cs=values.shrinkage_strain,
        k1=values.bond_factor,
        k2=values.strain_distribution_factor,
        crack_tension_face=values.tension_face,
    )
    # Table-method fields are unchanged; the direct-width calculation is
    # independently checked against Clause 8.6.2.3 rather than the superseded
    # snapshot equation.
    for key in (
        "sigma_table_A",
        "sigma_table_B",
        "sigma_table_combined",
        "sigma_08fsy",
        "sigma_allow_table",
        "utilisation_table",
        "passes_table",
    ):
        expected = legacy[key]
        if isinstance(expected, bool):
            assert current[key] is expected
        else:
            assert current[key] == pytest.approx(expected, rel=0.0, abs=1e-12)

    tension_zone_depth = values.cover_mm + values.bar_diameter_mm / 2.0
    expected_height = min(
        2.5 * tension_zone_depth,
        (values.depth_mm - values.neutral_axis_depth_mm) / 3.0,
        values.depth_mm / 2.0,
    )
    expected_area = values.width_mm * expected_height
    expected_ratio = values.steel_area_mm2 / expected_area
    expected_fct = 0.6 * values.concrete_strength_mpa**0.5
    expected_ne = (
        (1.0 + values.creep_coefficient)
        * values.steel_modulus_mpa
        / values.concrete_modulus_mpa
    )
    expected_strain = max(
        values.outer_steel_stress_mpa / values.steel_modulus_mpa
        - 0.6
        * expected_fct
        / (values.steel_modulus_mpa * expected_ratio)
        * (1.0 + expected_ne * expected_ratio)
        + values.shrinkage_strain,
        0.6 * values.outer_steel_stress_mpa / values.steel_modulus_mpa,
    )
    expected_spacing = (
        3.4 * values.cover_mm
        + 0.3
        * values.bond_factor
        * values.strain_distribution_factor
        * values.bar_diameter_mm
        / expected_ratio
    )
    assert current["height_eff"] == pytest.approx(expected_height)
    assert current["Aceff"] == pytest.approx(expected_area)
    assert current["rho_eff"] == pytest.approx(expected_ratio)
    assert current["eps_diff"] == pytest.approx(expected_strain)
    assert current["sr_max"] == pytest.approx(expected_spacing)
    assert current["w_calc"] == pytest.approx(expected_spacing * expected_strain)


def test_crack_control_rejects_non_finite_inputs() -> None:
    values = CrackControlInput(
        width_mm=float("nan"),
        depth_mm=600.0,
        cover_mm=40.0,
        bar_diameter_mm=16.0,
        bar_spacing_mm=150.0,
        steel_area_mm2=2400.0,
        concrete_strength_mpa=40.0,
        concrete_modulus_mpa=30_000.0,
        steel_modulus_mpa=200_000.0,
        steel_strength_mpa=500.0,
        crack_width_limit_mm=0.3,
        member_type="Flexure",
        outer_steel_stress_mpa=180.0,
        creep_coefficient=2.0,
        shrinkage_strain=650e-6,
        bond_factor=0.8,
        strain_distribution_factor=0.5,
        neutral_axis_depth_mm=180.0,
    )
    with pytest.raises(ValueError, match="width_mm must be finite"):
        calculate_crack_control(values)


def test_authoritative_cracked_section_uses_the_input_concrete_modulus() -> None:
    inputs = BeamInputs(
        width_mm=300.0,
        depth_mm=600.0,
        serviceability=ServiceabilityInputs(moment_knm=120.0),
        time_dependent=TimeDependentInputs(concrete_modulus_mpa=25_000.0),
    ).validated()
    families = EngineeringCalculator().calculate(inputs).families
    result = families["crack_control"]
    cracked = families["bending"]["sls_cracked_section"]
    tension_layers = tuple(
        layer for layer in cracked["layers"] if layer["state"] == "tension"
    )
    outer = max(tension_layers, key=lambda layer: layer["depth_from_compression_mm"])

    assert cracked["concrete_modulus_mpa"] == pytest.approx(25_000.0)
    assert cracked["modular_ratio"] == pytest.approx(200_000.0 / 25_000.0)
    assert abs(cracked["equilibrium_residual_mm3"]) <= cracked["solver_tolerance_mm3"]
    assert result["sigma_sr"] == pytest.approx(abs(outer["stress_mpa"]))
    assert result["sls_cracked_section"] == cracked
