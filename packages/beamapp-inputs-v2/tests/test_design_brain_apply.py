from dataclasses import replace

import pytest

from inputs_v2.application.design_brain_apply import Candidate, apply_candidate, propose_neutral_candidate
from inputs_v2.application.input_commands import UpdateFirstSlice
from inputs_v2.domain.beam_inputs import BeamInputs, LayoutMode


def proposal(current: BeamInputs) -> Candidate[UpdateFirstSlice]:
    return Candidate(
        candidate_id="fixture-bottom-bars-6",
        source_revision=current.revision,
        source_hash=current.content_hash,
        proposal=UpdateFirstSlice(400, 600, LayoutMode.COUNT, 6, 150, 20, 40),
        rationale="Fixture candidate for the isolated Apply boundary.",
    )


def test_current_candidate_uses_normal_input_command() -> None:
    current = BeamInputs()
    outcome = apply_candidate(current, proposal(current))
    assert outcome.applied is True
    assert outcome.reason == "applied"
    assert outcome.inputs.revision == 1
    assert outcome.inputs.bottom.bars == 6


def test_stale_candidate_is_rejected_without_mutation() -> None:
    current = BeamInputs(revision=2)
    stale = proposal(BeamInputs())
    outcome = apply_candidate(current, stale)
    assert outcome.applied is False
    assert outcome.reason == "stale_candidate"
    assert outcome.inputs == current


def test_neutral_candidate_preserves_geometry_locks() -> None:
    current = BeamInputs(width_locked=True, depth_locked=True)
    candidate = propose_neutral_candidate(current)

    assert candidate.proposal.width_locked is True
    assert candidate.proposal.depth_locked is True


def test_locked_width_change_is_rejected_without_mutation() -> None:
    current = BeamInputs(width_locked=True)
    seed = propose_neutral_candidate(current)
    candidate = replace(seed, proposal=replace(seed.proposal, width_mm=current.width_mm + 25.0))

    outcome = apply_candidate(current, candidate)

    assert outcome.applied is False
    assert outcome.reason == "width_locked"
    assert outcome.inputs == current


def test_locked_depth_change_is_rejected_without_mutation() -> None:
    current = BeamInputs(depth_locked=True)
    seed = propose_neutral_candidate(current)
    candidate = replace(seed, proposal=replace(seed.proposal, depth_mm=current.depth_mm + 25.0))

    outcome = apply_candidate(current, candidate)

    assert outcome.applied is False
    assert outcome.reason == "depth_locked"
    assert outcome.inputs == current


def test_design_brain_cannot_change_user_owned_lock_state() -> None:
    current = BeamInputs(width_locked=True)
    seed = propose_neutral_candidate(current)
    candidate = replace(seed, proposal=replace(seed.proposal, width_locked=False))

    outcome = apply_candidate(current, candidate)

    assert outcome.applied is False
    assert outcome.reason == "lock_state_mutation_forbidden"
    assert outcome.inputs == current


def test_t_section_candidate_applies_complete_web_geometry() -> None:
    current = BeamInputs(
        width_mm=300.0,
        depth_mm=600.0,
        section_shape="T",
        web_width_mm=300.0,
        flange_width_mm=900.0,
        flange_thickness_mm=120.0,
    ).validated()
    seed = propose_neutral_candidate(current)
    candidate = replace(
        seed,
        proposal=replace(
            seed.proposal,
            width_mm=325.0,
            web_width_mm=325.0,
        ),
    )

    outcome = apply_candidate(current, candidate)

    assert outcome.applied is True
    assert outcome.inputs.section_shape == "T"
    assert outcome.inputs.width_mm == 325.0
    assert outcome.inputs.web_width_mm == 325.0
    assert outcome.inputs.flange_width_mm == 900.0
    assert outcome.inputs.flange_thickness_mm == 120.0
    assert outcome.inputs.section_geometry.concrete_area_mm2 == 264000.0


def test_flanged_section_requires_complete_geometry() -> None:
    with pytest.raises(ValueError, match="Flanged sections require"):
        BeamInputs(section_shape="I").validated()
