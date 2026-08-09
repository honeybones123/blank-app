"""The only seam permitted for connecting production engineering formulas.

The adapter deliberately depends on a callable supplied by infrastructure or a
future Runtime bridge.  It never imports Streamlit, page modules, or Runtime
state, and it rejects results that are not tagged to the exact input revision.
"""

from __future__ import annotations

from collections.abc import Callable

from inputs_v2.domain.beam_inputs import BeamInputs
from inputs_v2.domain.engineering_result import EngineeringResult


class ProductionEngineeringAdapter:
    """Wrap an approved production calculator behind the V2 calculator port."""

    def __init__(self, calculate_fn: Callable[[BeamInputs], EngineeringResult]) -> None:
        self._calculate_fn = calculate_fn

    def calculate(self, inputs: BeamInputs) -> EngineeringResult:
        result = self._calculate_fn(inputs)
        if not isinstance(result, EngineeringResult):
            raise TypeError("production adapter must return EngineeringResult")
        if result.source_revision != inputs.revision or result.source_hash != inputs.content_hash:
            raise ValueError("production result is not tagged to the supplied Inputs V2 revision")
        return result

