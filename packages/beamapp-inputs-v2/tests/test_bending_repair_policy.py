from inputs_v2.application.design_brain.bending_repair_policy import (
    generate_bending_reduction_specs,
    generate_bending_width_lanes,
    generate_proportion_balance_specs,
)
from inputs_v2.application.design_brain_apply import propose_neutral_candidate
from inputs_v2.domain.beam_inputs import BeamInputs


def test_failed_bending_ladder_expands_width_in_25_mm_order() -> None:
    lanes = generate_bending_width_lanes(BeamInputs().validated(), 1.2)
    assert [lane.width_mm for lane in lanes] == [
        250.0, 275.0, 300.0, 325.0, 350.0, 375.0,
        400.0, 425.0, 450.0, 475.0, 500.0,
    ]
    first = lanes[0].candidates
    assert len(first) == 900
    assert first[0] == (250.0, 300.0, 2, 10, (2,))
    assert first[-1] == (250.0, 500.0, 12, 40, (6, 6))


def test_low_demand_ladder_searches_reductions_before_increases() -> None:
    lanes = generate_bending_width_lanes(BeamInputs().validated(), 0.5)
    assert [lane.width_mm for lane in lanes[:6]] == [
        150.0, 175.0, 200.0, 225.0, 250.0, 275.0,
    ]
    for lane in lanes:
        assert all(candidate.depth_mm <= 2.0 * lane.width_mm for candidate in lane.candidates)


def test_geometry_locks_collapse_bending_search_space() -> None:
    current = BeamInputs(width_locked=True, depth_locked=True).validated()
    lanes = generate_bending_width_lanes(current, 1.2)
    assert len(lanes) == 1
    assert lanes[0].width_mm == current.width_mm
    assert {candidate.depth_mm for candidate in lanes[0].candidates} == {
        current.depth_mm
    }


def test_cleanup_specs_only_reduce_section_area_and_preserve_order() -> None:
    current = BeamInputs().validated()
    specs = generate_bending_reduction_specs(current)
    assert specs
    assert specs[0].width_mm == 150.0
    assert specs[0].depth_mm == 200.0
    assert specs[0].bars == 2
    assert specs[0].diameter_mm == 10
    assert all(
        spec.width_mm * spec.depth_mm < current.width_mm * current.depth_mm
        for spec in specs
    )


def test_proportion_balance_ladder_is_bounded_and_ordered() -> None:
    current = BeamInputs().validated()
    candidate = propose_neutral_candidate(current)
    specs = generate_proportion_balance_specs(current, candidate)
    assert len(specs) == 24
    assert specs[0].depth_mm == candidate.proposal.depth_mm - 25.0
    assert specs[0].width_mm == candidate.proposal.width_mm
    assert specs[0].bars == candidate.proposal.bottom_bars
    assert all(spec.depth_mm <= 2.0 * candidate.proposal.width_mm for spec in specs)


def test_proportion_balance_ladder_honours_explicit_limit() -> None:
    current = BeamInputs().validated()
    candidate = propose_neutral_candidate(current)
    assert len(
        generate_proportion_balance_specs(current, candidate, evaluation_limit=5)
    ) == 5
