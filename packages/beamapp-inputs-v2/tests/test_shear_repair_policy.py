from inputs_v2.application.design_brain.shear_repair_policy import (
    generate_shear_repair_specs,
)
from inputs_v2.domain.beam_inputs import BeamInputs


def test_shear_repair_policy_preserves_declared_lane_order() -> None:
    specs = generate_shear_repair_specs(BeamInputs().validated(), 1.5)
    lanes = [spec.lane for spec in specs]
    assert len(specs) == 1001
    assert lanes[:7] == ["spacing"] * 7
    assert lanes[7:35] == ["legs"] * 28
    assert lanes[35:119] == ["diameter"] * 84
    assert lanes[119:161] == ["depth"] * 42
    assert lanes[161:] == ["width"] * 840


def test_locked_geometry_removes_depth_and_width_lanes() -> None:
    current = BeamInputs(width_locked=True, depth_locked=True).validated()
    specs = generate_shear_repair_specs(current, 3.0)
    assert len(specs) == 119
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
