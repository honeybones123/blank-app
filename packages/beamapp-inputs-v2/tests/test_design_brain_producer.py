from inputs_v2.application.design_brain_apply import apply_candidate, propose_neutral_candidate
from inputs_v2.domain.beam_inputs import BeamInputs


def test_neutral_design_brain_seed_is_identical_and_creates_no_revision() -> None:
    current = BeamInputs().validated()
    candidate = propose_neutral_candidate(current)
    outcome = apply_candidate(current, candidate)
    assert outcome.applied is True
    assert outcome.inputs == current
    assert candidate.proposal.bottom_bars == current.bottom.bars
