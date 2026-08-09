from inputs_v2.application.design_brain.shear_repair_policy import (
    generate_shear_repair_specs,
)
from inputs_v2.domain.beam_inputs import BeamInputs


def test_shear_repair_policy_preserves_declared_lane_order() -> None:
    specs = generate_shear_repair_specs(BeamInputs().validated(), 1.5)
    lanes = [spec.lane for spec in specs]
    assert len(specs) == 763
    assert lanes[:7] == ["spacing"] * 7
    assert lanes[7:28] == ["legs"] * 21
    assert lanes[28:91] == ["diameter"] * 63
    assert lanes[91:133] == ["depth"] * 42
    assert lanes[133:] == ["width"] * 630


def test_locked_geometry_removes_depth_and_width_lanes() -> None:
    current = BeamInputs(width_locked=True, depth_locked=True).validated()
    specs = generate_shear_repair_specs(current, 3.0)
    assert len(specs) == 91
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
