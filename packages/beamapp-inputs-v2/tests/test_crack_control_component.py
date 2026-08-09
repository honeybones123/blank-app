import pytest

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
def test_crack_control_preserves_snapshot_numerical_parity(
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
    assert current.keys() == legacy.keys()
    for key, expected in legacy.items():
        if isinstance(expected, bool):
            assert current[key] is expected
        else:
            assert current[key] == pytest.approx(expected, rel=0.0, abs=1e-12)


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
    )
    with pytest.raises(ValueError, match="width_mm must be finite"):
        calculate_crack_control(values)
