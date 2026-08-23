import math

import pytest

from bending_neutral_axis_teaching import neutral_axis_hand_solution
from engineering_page_sections.bending_uls_checks import (
    _teaching_steel_response_state,
)


def _derive(*, areas, depths, stresses, dn, b=250.0, D=300.0, fc=40.0, fsy=500.0, alpha2=0.79, gamma=0.87):
    return neutral_axis_hand_solution(
        b=b, D=D, fc=fc, fsy=fsy, Es=200000.0,
        alpha2=alpha2, gamma=gamma, dn=dn, block_depth=gamma * dn,
        layer_areas=tuple(areas), layer_depths=tuple(depths),
        layer_stresses=tuple(stresses),
        layer_labels=tuple(f"Layer {i + 1}" for i in range(len(areas))),
        section_shape="RECT",
    )


def test_current_yielded_bottom_and_elastic_top_reproduces_authoritative_root():
    result = _derive(
        areas=(235.61944901923448, 157.07963267948966),
        depths=(255.0, 45.0),
        stresses=(-500.0, -414.4983606138398),
        dn=26.614138620848223,
    )

    assert [row["state"] for row in result["rows"]] == [
        "yielded tension", "elastic tension",
    ]
    assert result["linear"] is False
    assert result["reproduced"] is True
    assert result["polynomial_at_dn"] == pytest.approx(0.0, abs=1e-6)


def test_teaching_neutral_axis_root_matches_the_published_reference_depth():
    """Parity remains an internal regression check, never card content."""
    published_dn = 26.614138620848223
    result = _derive(
        areas=(235.61944901923448, 157.07963267948966),
        depths=(255.0, 45.0),
        stresses=(-500.0, -414.4983606138398),
        dn=published_dn,
    )
    roots = [root for root, valid in result["roots"] if valid]

    assert roots
    assert min(abs(root - published_dn) for root in roots) <= 1e-6


@pytest.mark.parametrize(
    ("strain", "final_stress", "expected"),
    (
        (-0.001, -200.0, "Elastic tension"),
        (-0.004, -500.0, "Yielded tension"),
        (0.001, 200.0, "Elastic compression"),
        (0.004, 500.0, "Yielded compression"),
    ),
)
def test_teaching_steel_states_follow_published_stress_sign_and_yield_limit(
    strain, final_stress, expected
):
    trial, yielded, state = _teaching_steel_response_state(
        strain=strain, final_stress_mpa=final_stress, Es_mpa=200000.0, fsy_mpa=500.0
    )

    assert state == expected
    assert yielded is (abs(trial) > 500.0)
    assert abs(final_stress) <= 500.0


def test_all_yielded_layers_reduce_to_linear_equilibrium():
    areas = (600.0, 400.0)
    kc = 0.79 * 40.0 * 250.0 * 0.87
    dn = sum(areas) * 500.0 / kc
    result = _derive(
        areas=areas,
        depths=(255.0, 230.0),
        stresses=(-500.0, -500.0),
        dn=dn,
    )

    assert result["linear"] is True
    assert result["sum_q"] == 0.0
    assert result["reproduced"] is True
    assert result["roots"][0][0] == pytest.approx(dn)


def test_multiple_elastic_layers_are_all_included_in_quadratic_terms():
    dn = 120.0
    areas = (200.0, 150.0)
    depths = (180.0, 60.0)
    stresses = tuple(
        max(-500.0, min(500.0, 200000.0 * 0.003 * (dn - y) / dn))
        for y in depths
    )
    result = _derive(areas=areas, depths=depths, stresses=stresses, dn=dn)

    assert [row["state"] for row in result["rows"]] == [
        "elastic tension", "elastic compression",
    ]
    assert result["sum_q"] == pytest.approx(sum(areas) * 200000.0 * 0.003)
    assert result["sum_qy"] == pytest.approx(
        sum(area * 200000.0 * 0.003 * depth for area, depth in zip(areas, depths))
    )


def test_non_rectangular_section_does_not_claim_quadratic_reproduction():
    result = neutral_axis_hand_solution(
        b=300.0, D=600.0, fc=40.0, fsy=500.0, Es=200000.0,
        alpha2=0.79, gamma=0.87, dn=150.0, block_depth=130.5,
        layer_areas=(1000.0,), layer_depths=(550.0,),
        layer_stresses=(-500.0,), layer_labels=("Bottom",),
        section_shape="T",
    )

    assert result["roots"] == ()
    assert result["reproduced"] is False
