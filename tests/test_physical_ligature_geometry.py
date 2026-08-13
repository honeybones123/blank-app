from __future__ import annotations

import re

import pytest

from section_layout import compute_section_layout_pure
from section_props.reo_layout import compute_longitudinal_reo_layout_T_I
from ui.diagrams.ligature_geometry import build_rounded_ligature_shapes


def _path_points(shape: dict) -> list[tuple[float, float]]:
    values = [float(value) for value in re.findall(r"-?\d+(?:\.\d+)?", shape["path"])]
    return list(zip(values[0::2], values[1::2]))


@pytest.mark.parametrize("diameter", [6.0, 10.0, 12.0, 16.0, 20.0])
def test_ligature_straight_portions_use_exact_physical_diameter(diameter: float) -> None:
    shapes = build_rounded_ligature_shapes(
        outside_x0=40.0,
        outside_y0=40.0,
        outside_x1=360.0,
        outside_y1=560.0,
        diameter_mm=diameter,
        legs=2,
        color="#222",
    )

    top_straight = _path_points(shapes[0])
    bottom_straight = _path_points(shapes[1])
    assert max(y for _, y in top_straight) - min(y for _, y in top_straight) == pytest.approx(diameter)
    assert max(y for _, y in bottom_straight) - min(y for _, y in bottom_straight) == pytest.approx(diameter)


def test_rounded_ligature_has_four_curved_constant_thickness_corners() -> None:
    diameter = 12.0
    shapes = build_rounded_ligature_shapes(
        outside_x0=40.0,
        outside_y0=40.0,
        outside_x1=260.0,
        outside_y1=460.0,
        diameter_mm=diameter,
        legs=2,
        color="#222",
    )

    # Four straight strips followed by four sampled quarter-annuli.
    assert len(shapes) == 8
    for corner in shapes[4:8]:
        points = _path_points(corner)
        assert len(points) == 22
        # The outer and inner arcs use different radii separated by exactly db.
        outer_start = points[0]
        inner_end = points[-1]
        assert abs(outer_start[0] - inner_end[0]) + abs(outer_start[1] - inner_end[1]) == pytest.approx(diameter)


def test_multi_leg_ligature_uses_full_diameter_filled_internal_legs() -> None:
    diameter = 16.0
    shapes = build_rounded_ligature_shapes(
        outside_x0=40.0,
        outside_y0=40.0,
        outside_x1=360.0,
        outside_y1=560.0,
        diameter_mm=diameter,
        legs=4,
        color="#222",
    )

    assert len(shapes) == 10
    for internal_leg in shapes[-2:]:
        points = _path_points(internal_leg)
        assert max(x for x, _ in points) - min(x for x, _ in points) == pytest.approx(diameter)


def test_longitudinal_bar_surface_is_tangent_to_inside_ligature_surface() -> None:
    cover = 40.0
    ligature_diameter = 12.0
    bar_diameter = 20.0
    layout = compute_section_layout_pure(
        b=300.0,
        D=500.0,
        cover_bot=cover,
        cover_top=cover,
        cover_side=cover,
        nb_or_s_bot_1=3,
        db_bot_1=bar_diameter,
        nb_or_s_bot_2=0,
        db_bot_2=0,
        nb_or_s_top_1=2,
        db_top_1=bar_diameter,
        nb_or_s_top_2=0,
        db_top_2=0,
        rowgap_bot=40.0,
        rowgap_top=40.0,
        lig_legs=2,
        lig_d=ligature_diameter,
    )

    bottom = layout["reo_layout"]["bottom"][0]
    left_bar_edge = min(bottom["x"]) - bar_diameter / 2.0
    right_bar_edge = max(bottom["x"]) + bar_diameter / 2.0
    bottom_bar_edge = float(bottom["y"]) + bar_diameter / 2.0

    assert left_bar_edge == pytest.approx(cover + ligature_diameter)
    assert right_bar_edge == pytest.approx(300.0 - cover - ligature_diameter)
    assert bottom_bar_edge == pytest.approx(500.0 - cover - ligature_diameter)


def test_t_section_web_bars_are_tangent_to_inside_web_ligature() -> None:
    layout = compute_longitudinal_reo_layout_T_I(
        shape_name="T-Section",
        dims={"bf": 600.0, "tf": 150.0, "bw": 300.0, "D": 600.0},
        cover_side=40.0,
        cover_top=40.0,
        cover_bot=40.0,
        min_clear_spacing=20.0,
        rowgap_top=40.0,
        rowgap_bot=40.0,
        reo={
            "lig_d": 12.0,
            "lig_legs": 2,
            "top_rows": [{"active": True, "mode": "Count", "bars": 2, "dia": 20.0}],
            "bottom_rows": [{"active": True, "mode": "Count", "bars": 2, "dia": 20.0}],
        },
        max_rows=2,
    )

    bottom = layout["bottom_web"][0]
    web_left = (600.0 - 300.0) / 2.0
    assert min(bottom["x"]) - 10.0 == pytest.approx(web_left + 40.0 + 12.0)
    assert float(bottom["y"][0]) + 10.0 == pytest.approx(600.0 - 40.0 - 12.0)
