import pytest
import math

from inputs_v2.engineering.bending_capacity import (
    BendingCapacityInput,
    calculate_bending_capacity,
)
from inputs_v2.engineering.legacy_snapshot.bending import solve_bending_capacity


def _values(**changes) -> BendingCapacityInput:
    values = dict(
        width_mm=300.0, depth_mm=600.0, concrete_strength_mpa=32.0,
        reinforcement_strength_mpa=500.0, capacity_factor=0.85,
        bottom_steel_area_mm2=2454.0, top_steel_area_mm2=804.0,
        positive_effective_depth_mm=550.0, top_steel_depth_mm=50.0,
    )
    values.update(changes)
    return BendingCapacityInput(**values)


def _legacy_payload(values: BendingCapacityInput) -> dict:
    return {
        "b": values.width_mm, "D": values.depth_mm,
        "fc": values.concrete_strength_mpa,
        "fsy": values.reinforcement_strength_mpa,
        "phi_bend": values.capacity_factor,
        "Ast_bot": values.bottom_steel_area_mm2,
        "Ast_top": values.top_steel_area_mm2,
        "d": values.positive_effective_depth_mm,
        "do": values.top_steel_depth_mm,
    }


@pytest.mark.parametrize(
    ("sign", "demand", "values"),
    [
        ("positive", 200.0, _values()),
        ("negative", 100.0, _values()),
        ("positive", 0.0, _values()),
        ("negative", 100.0, _values(top_steel_area_mm2=0.0)),
        ("invalid", 500.0, _values(concrete_strength_mpa=65.0)),
    ],
)
def test_bending_capacity_preserves_snapshot_numerical_parity(sign, demand, values) -> None:
    current = calculate_bending_capacity(moment_sign=sign, demand_knm=demand, values=values)
    legacy = solve_bending_capacity(sign, demand, _legacy_payload(values))
    assert current.keys() == legacy.keys()
    for key, expected in legacy.items():
        if isinstance(expected, float):
            assert current[key] == pytest.approx(expected, rel=0.0, abs=1e-12, nan_ok=True)
        else:
            assert current[key] == expected


def test_overreinforced_section_never_publishes_negative_or_infinite_capacity() -> None:
    result = calculate_bending_capacity(
        moment_sign="positive",
        demand_knm=100.0,
        values=_values(
            depth_mm=400.0,
            concrete_strength_mpa=20.0,
            bottom_steel_area_mm2=8042.47719318987,
            positive_effective_depth_mm=324.0,
        ),
    )
    assert result["phi_Mu_kNm"] == 0.0
    assert result["Mu_nom_kNm"] == 0.0
    assert math.isfinite(result["util"])
    assert result["util"] > 1.0
    assert result["status"] == "FAIL"
