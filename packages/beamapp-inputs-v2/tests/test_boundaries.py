from inputs_v2.application.calculation_coordinator import CalculationCoordinator
from inputs_v2.domain.beam_inputs import BeamInputs
from inputs_v2.domain.engineering_result import EngineeringResult
from inputs_v2.engineering_port.fixture_calculator import FixtureCalculator
from inputs_v2.infrastructure.memory_repository import InMemoryBeamInputsRepository


def test_calculation_publication_matches_input_revision() -> None:
    inputs = BeamInputs()
    publication = CalculationCoordinator(FixtureCalculator()).calculate_current(inputs)
    assert publication.stale is False
    assert publication.result is not None
    assert publication.result.source_revision == inputs.revision
    assert publication.result.source_hash == inputs.content_hash


def test_repository_is_per_beam_and_rejects_older_revision() -> None:
    repository = InMemoryBeamInputsRepository()
    current = BeamInputs(revision=2)
    repository.save("A", current)
    repository.save("B", BeamInputs(revision=1))
    assert repository.load("A") == current
    assert repository.load("B").revision == 1
    try:
        repository.save("A", BeamInputs(revision=1))
    except ValueError as exc:
        assert "newer" in str(exc)
    else:
        raise AssertionError("older revision was accepted")


def test_stale_result_is_not_published_as_current() -> None:
    class StaleCalculator:
        def calculate(self, inputs):
            return EngineeringResult(inputs.revision - 1, "old", "fixture", "stale")

    publication = CalculationCoordinator(StaleCalculator()).calculate_current(BeamInputs(revision=3))
    assert publication.stale is True
    assert publication.result is None

