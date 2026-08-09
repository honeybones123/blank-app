from dataclasses import replace

from inputs_v2.application.design_brain.ratio_policy import (
    ratio_gate_required,
    ratio_review_required,
)
from inputs_v2.application.design_brain_service import DesignBrainService
from inputs_v2.domain.beam_inputs import BeamInputs


def _calculated(inputs: BeamInputs):
    result = DesignBrainService()._calculator.calculate_current(inputs).result
    assert result is not None
    return result


def test_ratio_policy_accepts_ordinary_compliant_reinforcement() -> None:
    baseline = BeamInputs().validated()
    inputs = replace(
        baseline,
        bottom=replace(baseline.bottom, bars=3, diameter_mm=16),
    ).validated()
    result = _calculated(inputs)
    assert ratio_review_required(inputs, result) is False
    assert ratio_gate_required(inputs, inputs, result) is False


def test_ratio_policy_gates_strong_low_ratio_without_geometry_justification() -> None:
    current = BeamInputs().validated()
    proposal = replace(current, width_mm=600.0, depth_mm=900.0).validated()
    result = _calculated(proposal)
    assert ratio_review_required(proposal, result)
    assert ratio_gate_required(proposal, proposal, result)


def test_ratio_policy_allows_low_ratio_after_material_geometry_increase() -> None:
    current = BeamInputs().validated()
    proposal = replace(current, width_mm=600.0, depth_mm=900.0).validated()
    result = _calculated(proposal)
    assert ratio_review_required(proposal, result)
    assert ratio_gate_required(current, proposal, result) is False


def test_ratio_policy_allows_low_ratio_after_material_geometry_reduction() -> None:
    current = replace(BeamInputs(), width_mm=350.0, depth_mm=600.0).validated()
    proposal = replace(current, width_mm=250.0, depth_mm=400.0).validated()
    result = _calculated(proposal)
    assert ratio_review_required(proposal, result)
    assert ratio_gate_required(current, proposal, result) is False
