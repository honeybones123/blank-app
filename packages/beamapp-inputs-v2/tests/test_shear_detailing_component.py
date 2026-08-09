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
    assert current.keys() == legacy.keys()
    for key, expected in legacy.items():
        if isinstance(expected, bool):
            assert current[key] is expected
        else:
            assert current[key] == pytest.approx(expected, rel=0.0, abs=1e-15)


def test_shear_detailing_rejects_non_finite_values() -> None:
    with pytest.raises(ValueError, match="web_width_mm must be finite"):
        calculate_shear_detailing(
            ShearDetailingInput(100.0, 200.0, 32.0, float("nan"), 500.0, 400.0)
        )
