"""Independent hand-calculation checks for the AS 3600 bending solver."""

from __future__ import annotations

import math

import pytest

from inputs_v2.engineering.bending_capacity import (
    BendingCapacityInput,
    bending_strength_reduction_factor,
    calculate_bending_capacity,
    stress_block_factors,
)


def _values(**changes) -> BendingCapacityInput:
    values = dict(
        width_mm=300.0, depth_mm=600.0, concrete_strength_mpa=32.0,
        reinforcement_strength_mpa=500.0, capacity_factor=0.85,
        bottom_steel_area_mm2=1200.0, top_steel_area_mm2=0.0,
        positive_effective_depth_mm=550.0, top_steel_depth_mm=50.0,
    )
    values.update(changes)
    return BendingCapacityInput(**values)


@pytest.mark.parametrize("target_ku", [0.30, 0.40])
def test_rectangular_hand_calculation_on_both_sides_of_ku_036(target_ku: float) -> None:
    fc, fsy, b, d = 32.0, 500.0, 300.0, 550.0
    alpha2, gamma = stress_block_factors(fc)
    dn = target_ku * d
    a = gamma * dn
    ast = alpha2 * fc * b * a / fsy
    nominal = ast * fsy * (d - a / 2.0) / 1_000_000.0
    expected_phi = max(0.65, min(0.85, 1.24 - 13.0 * target_ku / 12.0))

    result = calculate_bending_capacity(
        moment_sign="positive", demand_knm=100.0,
        values=_values(bottom_steel_area_mm2=ast),
    )

    assert result["dn_mm"] == pytest.approx(dn, rel=1e-9)
    assert result["ku"] == pytest.approx(target_ku, rel=1e-9)
    assert result["Mu_nom_kNm"] == pytest.approx(nominal, rel=1e-9)
    assert result["phi"] == pytest.approx(expected_phi, rel=1e-9)
    assert result["phi_Mu_kNm"] == pytest.approx(expected_phi * nominal, rel=1e-9)


@pytest.mark.parametrize(
    ("shape", "target_dn", "expected_area"),
    [
        ("T", 80.0, lambda a: 700.0 * a),
        ("T", 220.0, lambda a: 700.0 * 120.0 + 300.0 * (a - 120.0)),
        ("I", 220.0, lambda a: 700.0 * 100.0 + 250.0 * (a - 100.0)),
    ],
)
def test_flanged_section_neutral_axis_uses_shape_specific_equilibrium(
    shape: str, target_dn: float, expected_area,
) -> None:
    fc, fsy, d = 40.0, 500.0, 550.0
    alpha2, gamma = stress_block_factors(fc)
    tf = 120.0 if shape == "T" else 100.0
    bw = 300.0 if shape == "T" else 250.0
    a = gamma * target_dn
    concrete_area = expected_area(a)
    ast = alpha2 * fc * concrete_area / fsy

    result = calculate_bending_capacity(
        moment_sign="positive", demand_knm=100.0,
        values=_values(
            concrete_strength_mpa=fc, bottom_steel_area_mm2=ast,
            section_shape=shape, flange_width_mm=700.0,
            flange_thickness_mm=tf, web_width_mm=bw,
        ),
    )

    assert result["shape_equilibrium_valid"] is True
    assert result["dn_mm"] == pytest.approx(target_dn, rel=1e-9)


def test_t_section_hogging_uses_bottom_web_as_compression_face() -> None:
    fc, fsy, D, d_hog, target_dn = 40.0, 500.0, 600.0, 550.0, 100.0
    alpha2, gamma = stress_block_factors(fc)
    # The bottom compression block remains within the 300 mm web; the 700 mm
    # top flange must not be used for this hogging equilibrium.
    top_area = alpha2 * fc * 300.0 * gamma * target_dn / fsy
    result = calculate_bending_capacity(
        moment_sign="negative", demand_knm=100.0,
        values=_values(
            depth_mm=D, bottom_steel_area_mm2=0.0,
            top_steel_area_mm2=top_area, concrete_strength_mpa=fc, section_shape="T",
            flange_width_mm=700.0, flange_thickness_mm=120.0,
            web_width_mm=300.0, top_steel_depth_mm=D - d_hog,
        ),
    )

    assert result["compression_face"] == "bottom"
    assert result["d_mm"] == pytest.approx(d_hog)
    assert result["dn_mm"] == pytest.approx(target_dn, rel=1e-9)


def test_compression_steel_uses_strain_compatibility_in_force_and_moment() -> None:
    fc, fsy, b, d, ds, target_dn, asc = 32.0, 500.0, 300.0, 550.0, 50.0, 220.0, 900.0
    alpha2, gamma = stress_block_factors(fc)
    a = gamma * target_dn
    concrete_force = alpha2 * fc * b * a
    compression_stress = min(
        fsy, 200_000.0 * 0.003 * (target_dn - ds) / target_dn
    )
    compression_force = asc * (compression_stress - alpha2 * fc)
    ast = (concrete_force + compression_force) / fsy
    expected_moment = abs(
        concrete_force * a / 2.0 + compression_force * ds - ast * fsy * d
    ) / 1_000_000.0

    result = calculate_bending_capacity(
        moment_sign="positive", demand_knm=100.0,
        values=_values(
            bottom_steel_area_mm2=ast, top_steel_area_mm2=asc,
            top_steel_depth_mm=ds,
        ),
    )

    assert result["dn_mm"] == pytest.approx(target_dn, rel=1e-9)
    assert result["steel_layer_stresses_mpa"][1] == pytest.approx(compression_stress)
    assert result["Mu_nom_kNm"] == pytest.approx(expected_moment, rel=1e-9)
    assert abs(result["equilibrium_residual_n"]) < 1e-6
    assert result["steel_layer_areas_mm2"] == pytest.approx((ast, asc))
    assert sum(-force for force in result["steel_layer_forces_n"] if force < 0.0) == pytest.approx(result["tension_force_n"])
    assert sum(force for force in result["steel_layer_forces_n"] if force > 0.0) == pytest.approx(result["compression_steel_force_n"])
    assert result["concrete_force_n"] + result["compression_steel_force_n"] - result["tension_force_n"] == pytest.approx(result["equilibrium_residual_n"], abs=1e-6)


def test_phi_is_bounded_by_table_222_limits() -> None:
    assert bending_strength_reduction_factor(0.10) == pytest.approx(0.85)
    assert bending_strength_reduction_factor(0.90) == pytest.approx(0.65)


def test_active_top_layer_is_published_as_elastic_tension_for_shallow_na() -> None:
    bottom_area = 3.0 * math.pi * 10.0**2 / 4.0
    top_area = 2.0 * math.pi * 10.0**2 / 4.0
    result = calculate_bending_capacity(
        moment_sign="positive",
        demand_knm=200.0,
        values=BendingCapacityInput(
            width_mm=250.0,
            depth_mm=300.0,
            concrete_strength_mpa=40.0,
            reinforcement_strength_mpa=500.0,
            capacity_factor=0.85,
            bottom_steel_area_mm2=bottom_area,
            top_steel_area_mm2=top_area,
            positive_effective_depth_mm=255.0,
            top_steel_depth_mm=45.0,
            bottom_layer_labels=("Bottom reinforcement — 3-N10",),
            top_layer_labels=("Top reinforcement — 2-N10",),
        ),
    )

    assert result["steel_layer_labels"] == (
        "Bottom reinforcement — 3-N10",
        "Top reinforcement — 2-N10",
    )
    assert result["steel_layer_depths_mm"] == pytest.approx((255.0, 45.0))
    assert result["steel_layer_stresses_mpa"] == pytest.approx((-500.0, -414.4983606))
    assert result["steel_layer_forces_n"] == pytest.approx((-117809.7245, -65109.2502))
    assert sum(-force for force in result["steel_layer_forces_n"] if force < 0.0) == pytest.approx(result["tension_force_n"])
    assert result["concrete_force_n"] == pytest.approx(result["tension_force_n"])
    trace = result["neutral_axis_iteration_trace"]
    assert tuple(entry["iteration"] for entry in trace) == (1, 2, 3, 100)
    assert trace[-1]["dn_mm"] == pytest.approx(result["dn_mm"], rel=1e-9)
    assert trace[-1]["equilibrium_residual_n"] == pytest.approx(0.0, abs=1e-6)


def test_zero_area_top_row_is_not_published_as_a_steel_layer() -> None:
    """A visible zero-bar top row must not turn a singly reinforced beam multi-layer."""
    result = calculate_bending_capacity(
        moment_sign="positive",
        demand_knm=100.0,
        values=_values(
            bottom_layers=((1200.0, 550.0),),
            top_layers=((0.0, 50.0),),
        ),
    )

    assert result["steel_layer_areas_mm2"] == pytest.approx((1200.0,))
    assert result["steel_layer_faces"] == ("bottom",)
