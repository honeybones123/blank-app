"""Revision-aware calculation coordination; no persistence or UI concerns."""

from __future__ import annotations

from dataclasses import dataclass

from inputs_v2.domain.beam_inputs import BeamInputs
from inputs_v2.domain.engineering_result import EngineeringResult
from inputs_v2.engineering_port.protocol import EngineeringCalculator
from inputs_v2.engineering_port.fixture_calculator import FixtureCalculator
from inputs_v2.engineering.engineering_calculator import EngineeringCalculator


@dataclass(frozen=True, slots=True)
class CalculationPublication:
    requested_revision: int
    result: EngineeringResult | None
    stale: bool


class CalculationCoordinator:
    def __init__(self, calculator: EngineeringCalculator) -> None:
        self._calculator = calculator

    def calculate_current(self, inputs: BeamInputs) -> CalculationPublication:
        result = self._calculator.calculate(inputs)
        stale = result.source_revision != inputs.revision or result.source_hash != inputs.content_hash
        return CalculationPublication(inputs.revision, None if stale else result, stale)


def calculate_fixture_current(inputs: BeamInputs) -> EngineeringResult | None:
    """Calculate the isolated fixture through the application boundary."""
    return CalculationCoordinator(FixtureCalculator()).calculate_current(inputs).result


def calculate_legacy_shadow_current(inputs: BeamInputs) -> EngineeringResult | None:
    """Run copied V1 formulas in shadow mode without changing displayed output."""
    return CalculationCoordinator(EngineeringCalculator()).calculate_current(inputs).result
