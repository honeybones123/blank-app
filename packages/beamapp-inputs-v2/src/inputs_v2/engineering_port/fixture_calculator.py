"""Deterministic placeholder. It contains no production engineering claims."""

from inputs_v2.domain.beam_inputs import BeamInputs
from inputs_v2.domain.engineering_result import EngineeringResult


class FixtureCalculator:
    def calculate(self, inputs: BeamInputs) -> EngineeringResult:
        return EngineeringResult(
            source_revision=inputs.revision,
            source_hash=inputs.content_hash,
            status="fixture",
            summary="Isolated UI proof — production calculations are not connected.",
        )

