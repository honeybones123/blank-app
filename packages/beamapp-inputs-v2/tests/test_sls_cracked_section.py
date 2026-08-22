from __future__ import annotations

import math

import pytest

from inputs_v2.engineering.sls_cracked_section import (
    CrackedSectionLayer,
    classify_reinforcement_layer,
    solve_sls_cracked_section,
)


def _layer(layer_id: str, area: float, y: float, label: str | None = None):
    return CrackedSectionLayer(layer_id, label or layer_id, area, y)


def _solve(layers, **overrides):
    values = {
        "width_mm": 250.0,
        "depth_mm": 500.0,
        "concrete_modulus_mpa": 30_000.0,
        "steel_modulus_mpa": 200_000.0,
        "service_moment_knm": 120.0,
        "layers": tuple(layers),
    }
    values.update(overrides)
    return solve_sls_cracked_section(**values)


def test_modular_ratio_is_published_once_from_elastic_moduli() -> None:
    result = _solve((_layer("B1", 800.0, 450.0),))
    assert result["modular_ratio"] == pytest.approx(200_000.0 / 30_000.0)


def test_single_tension_layer_matches_rectangular_hand_solution() -> None:
    area = 800.0
    y = 450.0
    n = 200_000.0 / 30_000.0
    expected = (-n * area + math.sqrt((n * area) ** 2 + 2.0 * 250.0 * n * area * y)) / 250.0
    result = _solve((_layer("B1", area, y),))
    assert result["neutral_axis_depth_mm"] == pytest.approx(expected)


def test_multiple_tension_layers_are_all_included() -> None:
    result = _solve((_layer("B1", 500.0, 460.0), _layer("B2", 350.0, 410.0)))
    assert [layer["state"] for layer in result["layers"]] == ["tension", "tension"]
    assert all(float(layer["first_moment_mm3"]) > 0.0 for layer in result["layers"])


def test_compression_layer_uses_n_minus_one_with_gross_concrete() -> None:
    result = _solve((_layer("B1", 800.0, 450.0), _layer("T1", 300.0, 40.0)))
    top = next(layer for layer in result["layers"] if layer["layer_id"] == "T1")
    assert top["state"] == "compression"
    assert top["transformed_factor"] == pytest.approx(result["modular_ratio"] - 1.0)


def test_multiple_tension_and_compression_layers_are_supported() -> None:
    result = _solve(
        (
            _layer("B1", 400.0, 465.0),
            _layer("B2", 400.0, 420.0),
            _layer("T1", 250.0, 35.0),
            _layer("T2", 250.0, 75.0),
        )
    )
    states = [layer["state"] for layer in result["layers"]]
    assert states.count("tension") == 2
    assert states.count("compression") == 2


def test_physical_top_layer_below_neutral_axis_is_tension() -> None:
    result = _solve((_layer("Bottom", 120.0, 470.0), _layer("Top", 700.0, 180.0)))
    top = next(layer for layer in result["layers"] if layer["layer_id"] == "Top")
    assert top["depth_from_top_mm"] == 180.0
    assert top["state"] == "tension"


def test_layer_classification_changes_with_trial_neutral_axis() -> None:
    assert classify_reinforcement_layer(120.0, 80.0) == "tension"
    assert classify_reinforcement_layer(120.0, 160.0) == "compression"
    assert classify_reinforcement_layer(120.0, 120.0) == "neutral"


def test_ignore_compression_reinforcement_omits_only_compression_layers() -> None:
    layers = (_layer("B1", 800.0, 450.0), _layer("T1", 300.0, 40.0))
    included = _solve(layers)
    ignored = _solve(layers, ignore_compression_reinforcement=True)
    included_top = next(layer for layer in included["layers"] if layer["layer_id"] == "T1")
    ignored_top = next(layer for layer in ignored["layers"] if layer["layer_id"] == "T1")
    assert included_top["included"] is True
    assert ignored_top["included"] is False
    assert ignored_top["transformed_factor"] == 0.0
    assert ignored["neutral_axis_depth_mm"] != pytest.approx(included["neutral_axis_depth_mm"])


def test_zero_area_placeholder_layers_are_ignored() -> None:
    result = _solve((_layer("empty", 0.0, 40.0), _layer("B1", 800.0, 450.0)))
    assert [layer["layer_id"] for layer in result["layers"]] == ["B1"]


def test_layer_order_does_not_change_solution() -> None:
    layers = (_layer("B1", 500.0, 450.0), _layer("B2", 300.0, 400.0), _layer("T1", 250.0, 40.0))
    forwards = _solve(layers)
    backwards = _solve(tuple(reversed(layers)))
    assert forwards["neutral_axis_depth_mm"] == pytest.approx(backwards["neutral_axis_depth_mm"])
    assert forwards["cracked_inertia_mm4"] == pytest.approx(backwards["cracked_inertia_mm4"])


@pytest.mark.parametrize(
    ("shape", "bf", "tf", "bw"),
    (("T", 600.0, 100.0, 250.0), ("I", 600.0, 80.0, 250.0)),
)
def test_flanged_sections_use_shape_specific_compression_geometry(shape, bf, tf, bw) -> None:
    result = _solve(
        (_layer("B1", 1000.0, 450.0),),
        section_shape=shape,
        flange_width_mm=bf,
        flange_thickness_mm=tf,
        web_width_mm=bw,
    )
    rectangular = _solve((_layer("B1", 1000.0, 450.0),))
    assert result["section_shape"] == shape
    assert result["neutral_axis_depth_mm"] != pytest.approx(rectangular["neutral_axis_depth_mm"])
    assert result["concrete_first_moment_mm3"] > 0.0


def test_final_residual_is_within_the_published_solver_tolerance() -> None:
    result = _solve((_layer("B1", 800.0, 450.0), _layer("T1", 300.0, 40.0)))
    assert abs(result["equilibrium_residual_mm3"]) <= result["solver_tolerance_mm3"]


def test_curvature_strain_and_stress_follow_required_sequence() -> None:
    result = _solve((_layer("B1", 800.0, 450.0),))
    expected_curvature = 120.0e6 / (30_000.0 * result["cracked_inertia_mm4"])
    layer = result["layers"][0]
    expected_strain = expected_curvature * layer["signed_distance_from_na_mm"]
    assert result["curvature_per_mm"] == pytest.approx(expected_curvature)
    assert layer["strain"] == pytest.approx(expected_strain)
    assert layer["stress_mpa"] == pytest.approx(200_000.0 * expected_strain)
