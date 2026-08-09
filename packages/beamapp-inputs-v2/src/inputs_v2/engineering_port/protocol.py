from typing import Protocol

from inputs_v2.domain.beam_inputs import BeamInputs
from inputs_v2.domain.engineering_result import EngineeringResult


class EngineeringCalculator(Protocol):
    def calculate(self, inputs: BeamInputs) -> EngineeringResult: ...

