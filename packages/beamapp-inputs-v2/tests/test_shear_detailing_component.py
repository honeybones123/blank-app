import pytest

from inputs_v2.engineering.legacy_snapshot.shear import (
    shear_reinforcement_spacing_check_values,
)
from inputs_v2.engineering.shear_detailing import (
    ShearDetailingInput,
    calculate_shear_detailing,
)


@pytest.mark.parametrize(
    ("area", "spacing", "strength", "width", "steel_strength", "depth"),
    [
        (157.08, 200.0, 32.0, 250.0, 500.0, 400.0),
        (314.16, 500.0, 50.0, 300.0, 500.0, 1000.0),
        (0.0, None, 25.0, 200.0, 500.0, None),
        (100.0, 600.0, 100.0, 1000.0, 0.0, 1200.0),
    ],
)
def test_shear_detailing_preserves_snapshot_numerical_parity(
    area: float,
    spacing: float | None,
    strength: float,
    width: float,
    steel_strength: float,
    depth: float | None,
) -> None:
    current = calculate_shear_detailing(
        ShearDetailingInput(area, spacing, strength, width, steel_strength, depth)
    ).as_family_values()
    legacy = shear_reinforcement_spacing_check_values(
        Asv_mm2=area,
        s_lig_mm=spacing,
        fc_mpa=strength,
        b_v_mm=width,
        f_syv_mpa=steel_strength,
        D_mm=depth,
    )
    for key, expected in legacy.items():
        if isinstance(expected, bool):
            assert current[key] is expected
        else:
            assert current[key] == pytest.approx(expected, rel=0.0, abs=1e-15)


def test_two_legs_pass_for_450_by_825_example() -> None:
    result = calculate_shear_detailing(
        ShearDetailingInput(
            157.08,
            200.0,
            40.0,
            450.0,
            500.0,
            825.0,
            effective_legs=2,
            link_diameter_mm=10.0,
            side_cover_mm=40.0,
        )
    )
    assert result.transverse_leg_centres_mm == pytest.approx((45.0, 405.0))
    assert result.transverse_adjacent_spacings_mm == pytest.approx((360.0,))
    assert result.transverse_max_leg_spacing_mm == pytest.approx(360.0)
    assert result.transverse_spacing_limit_mm == pytest.approx(600.0)
    assert result.transverse_minimum_even_legs == 2
    assert result.transverse_spacing_ok is True


@pytest.mark.parametrize(
    ("width", "depth", "legs", "expected_minimum", "expected_ok"),
    [
        (450.0, 825.0, 2, 2, True),
        (690.0, 300.0, 2, 4, False),
        (690.0, 300.0, 4, 4, True),
        (1890.0, 300.0, 6, 8, False),
        (1890.0, 300.0, 8, 8, True),
        (3000.0, 200.0, 8, None, False),
    ],
)
def test_transverse_spacing_selects_minimum_supported_even_legs(
    width: float,
    depth: float,
    legs: int,
    expected_minimum: int | None,
    expected_ok: bool,
) -> None:
    result = calculate_shear_detailing(
        ShearDetailingInput(
            157.08,
            200.0,
            40.0,
            width,
            500.0,
            depth,
            effective_legs=legs,
            link_diameter_mm=10.0,
            side_cover_mm=40.0,
        )
    )
    assert result.transverse_minimum_even_legs == expected_minimum
    assert result.transverse_spacing_ok is expected_ok


def test_shear_detailing_rejects_non_finite_values() -> None:
    with pytest.raises(ValueError, match="web_width_mm must be finite"):
        calculate_shear_detailing(
            ShearDetailingInput(100.0, 200.0, 32.0, float("nan"), 500.0, 400.0)
        )
