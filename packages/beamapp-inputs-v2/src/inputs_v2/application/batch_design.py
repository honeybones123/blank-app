"""Isolated batch-design coordination with per-beam input ownership."""

from __future__ import annotations

from dataclasses import dataclass

from inputs_v2.domain.beam_inputs import BeamInputs
from inputs_v2.domain.engineering_result import EngineeringResult
from inputs_v2.engineering_port.protocol import EngineeringCalculator
from inputs_v2.engineering_port.fixture_calculator import FixtureCalculator


@dataclass(frozen=True, slots=True)
class BatchBeam:
    beam_id: str
    inputs: BeamInputs

    def __post_init__(self) -> None:
        if not self.beam_id.strip():
            raise ValueError("beam_id is required")
        self.inputs.validated()


@dataclass(frozen=True, slots=True)
class BatchDesignResult:
    beam_id: str
    source_revision: int
    result: EngineeringResult


def calculate_batch(beams: tuple[BatchBeam, ...], calculator: EngineeringCalculator) -> tuple[BatchDesignResult, ...]:
    if len({beam.beam_id for beam in beams}) != len(beams):
        raise ValueError("batch beam IDs must be unique")
    return tuple(
        BatchDesignResult(beam.beam_id, beam.inputs.revision, calculator.calculate(beam.inputs))
        for beam in beams
    )


def calculate_fixture_batch(beams: tuple[BatchBeam, ...]) -> tuple[BatchDesignResult, ...]:
    """Run the isolated fixture calculator without leaking it into presentation."""
    return calculate_batch(beams, FixtureCalculator())
