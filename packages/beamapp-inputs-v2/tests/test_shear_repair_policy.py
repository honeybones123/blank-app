from inputs_v2.application.design_brain.shear_repair_policy import (
    generate_shear_repair_specs,
)
from dataclasses import replace

from inputs_v2.domain.beam_inputs import BeamInputs, ShearReinforcement


def test_shear_repair_policy_preserves_declared_lane_order() -> None:
    specs = generate_shear_repair_specs(BeamInputs().validated(), 1.5)
    lanes = [spec.lane for spec in specs]
    assert len(specs) == 1477
    assert lanes[:7] == ["spacing"] * 7
    assert lanes[7:49] == ["legs"] * 42
    assert lanes[49:175] == ["diameter"] * 126
    assert lanes[175:217] == ["depth"] * 42
    assert lanes[217:] == ["width"] * 1260


def test_locked_geometry_removes_depth_and_width_lanes() -> None:
    current = BeamInputs(width_locked=True, depth_locked=True).validated()
    specs = generate_shear_repair_specs(current, 3.0)
    assert len(specs) == 175
    assert {spec.lane for spec in specs} == {"spacing", "legs", "diameter"}


def test_severe_failure_adds_bounded_coordinated_geometry_lane() -> None:
    current = BeamInputs().validated()
    ordinary = generate_shear_repair_specs(current, 2.0)
    severe = generate_shear_repair_specs(current, 2.01)
    coordinated = [spec for spec in severe if spec.lane == "coordinated_geometry"]
    assert len(severe) > len(ordinary)
    assert coordinated
    for spec in coordinated:
        assert spec.changes["depth_mm"] <= 2.0 * spec.changes["width_mm"]
        assert spec.changes["depth_mm"] <= current.depth_mm + 700.0


def test_repair_ladder_never_reduces_existing_leg_count() -> None:
    current = replace(
        BeamInputs(), shear=ShearReinforcement(diameter_mm=10, legs=4)
    ).validated()
    specs = generate_shear_repair_specs(current, 1.5)
    link_specs = [spec for spec in specs if "shear_legs" in spec.changes]
    assert link_specs
    assert all(int(spec.changes["shear_legs"]) >= 4 for spec in link_specs)
    assert all(
        int(spec.changes["shear_legs"]) > 4
        for spec in specs
        if spec.lane == "legs"
    )


def test_maximum_leg_count_can_still_increase_link_diameter() -> None:
    current = replace(
        BeamInputs(), shear=ShearReinforcement(diameter_mm=10, legs=8)
    ).validated()
    specs = generate_shear_repair_specs(current, 1.5)
    assert not [spec for spec in specs if spec.lane == "legs"]
    diameter_specs = [spec for spec in specs if spec.lane == "diameter"]
    assert diameter_specs
    assert {int(spec.changes["shear_legs"]) for spec in diameter_specs} == {8}
    assert {int(spec.changes["shear_diameter_mm"]) for spec in diameter_specs} == {
        10,
        12,
        16,
    }
