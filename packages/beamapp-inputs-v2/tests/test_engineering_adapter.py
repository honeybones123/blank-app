from __future__ import annotations

import pytest

from inputs_v2.domain.beam_inputs import BeamInputs
from inputs_v2.domain.engineering_result import EngineeringResult
from inputs_v2.engineering_port.production_adapter import ProductionEngineeringAdapter


def test_production_adapter_preserves_revision_tag() -> None:
    inputs = BeamInputs().validated()

    def approved_calculator(value: BeamInputs) -> EngineeringResult:
        return EngineeringResult(value.revision, value.content_hash, "production", "parity fixture")

    result = ProductionEngineeringAdapter(approved_calculator).calculate(inputs)
    assert result.status == "production"
    assert result.source_hash == inputs.content_hash


def test_production_adapter_rejects_stale_result() -> None:
    inputs = BeamInputs().validated()

    def stale_calculator(value: BeamInputs) -> EngineeringResult:
        return EngineeringResult(value.revision - 1, value.content_hash, "production", "stale")

    with pytest.raises(ValueError, match="tagged"):
        ProductionEngineeringAdapter(stale_calculator).calculate(inputs)

