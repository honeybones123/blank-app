from inputs_v2.application.batch_design import BatchBeam, calculate_batch
from inputs_v2.domain.beam_inputs import BeamInputs
from inputs_v2.engineering_port.fixture_calculator import FixtureCalculator


def test_batch_design_preserves_per_beam_revisions() -> None:
    results = calculate_batch(
        (BatchBeam("A", BeamInputs(revision=2)), BatchBeam("B", BeamInputs(revision=5))),
        FixtureCalculator(),
    )
    assert [(item.beam_id, item.source_revision) for item in results] == [("A", 2), ("B", 5)]


def test_batch_design_rejects_duplicate_beams() -> None:
    try:
        calculate_batch((BatchBeam("A", BeamInputs()), BatchBeam("A", BeamInputs())), FixtureCalculator())
    except ValueError as exc:
        assert "unique" in str(exc)
    else:
        raise AssertionError("duplicate beam IDs were accepted")
