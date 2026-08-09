from dataclasses import replace

import pytest

from inputs_v2.application.design_brain_decision import DecisionStatus
from inputs_v2.application.design_guide_orchestrator import DesignGuideOrchestrator
from inputs_v2.application.design_brain_service import DesignBrainService
from inputs_v2.application.design_brain.family_owners import FAMILY_OWNERS, TERMINAL_FAMILIES
from inputs_v2.application.design_brain_families import DesignFamily
from inputs_v2.application.candidate_evaluation import complete_compliance
from inputs_v2.domain.beam_inputs import ActionInputs, BeamInputs, LongitudinalReinforcement
from inputs_v2.domain.engineering_result import EngineeringResult


def test_decision_is_the_single_apply_authority() -> None:
    current = BeamInputs(actions=ActionInputs(bending_moment_knm=200.0)).validated()
    decision = DesignGuideOrchestrator().decide(current)
    assert decision.advice.apply_allowed is decision.apply_allowed
    if decision.apply_allowed:
        assert decision.status is DecisionStatus.ACTION
        assert decision.candidate is not None


def test_pass_decision_never_allows_apply() -> None:
    current = BeamInputs(actions=ActionInputs(bending_moment_knm=200.0)).validated()
    decision = DesignGuideOrchestrator().decide(current)
    if decision.status is DecisionStatus.PASS:
        assert not decision.apply_allowed
        with pytest.raises(ValueError):
            replace(decision, apply_allowed=True)


def test_decision_preserves_source_revision_and_hash() -> None:
    current = BeamInputs(actions=ActionInputs(bending_moment_knm=200.0)).validated()
    decision = DesignGuideOrchestrator().decide(current)
    assert decision.candidate is not None
    assert decision.candidate.source_revision == current.revision
    assert decision.candidate.source_hash == current.content_hash


def test_every_non_terminal_family_has_exactly_one_owner() -> None:
    assert set(FAMILY_OWNERS) == set(DesignFamily) - TERMINAL_FAMILIES
    assert all(owner.family is family for family, owner in FAMILY_OWNERS.items())
    assert all(owner.contract.required_checks for owner in FAMILY_OWNERS.values())
    assert all(owner.contract.target_low < owner.contract.target_high for owner in FAMILY_OWNERS.values())
    assert len({owner.contract.owner_id for owner in FAMILY_OWNERS.values()}) == len(FAMILY_OWNERS)


def test_missing_mandatory_check_metadata_never_defaults_to_pass() -> None:
    result = EngineeringResult(0, "fixture", "complete", "missing checks", families={})
    assert not complete_compliance(result)


def test_apply_uses_the_exact_displayed_proposal() -> None:
    current = BeamInputs(actions=ActionInputs(bending_moment_knm=200.0)).validated()
    decision = DesignGuideOrchestrator().decide(current)
    assert decision.apply_allowed
    outcome = DesignBrainService().apply_decision(current, decision)
    assert outcome.applied
    assert outcome.inputs.content_hash == decision.proposed_result.source_hash


def test_apply_rejects_a_displayed_result_mismatch_without_mutation() -> None:
    current = BeamInputs(actions=ActionInputs(bending_moment_knm=200.0)).validated()
    decision = DesignGuideOrchestrator().decide(current)
    assert decision.proposed_result is not None
    mismatched_result = replace(decision.proposed_result, source_hash="not-the-displayed-proposal")
    mismatched_decision = replace(decision, proposed_result=mismatched_result)
    outcome = DesignBrainService().apply_decision(current, mismatched_decision)
    assert not outcome.applied
    assert outcome.reason == "displayed_proposal_mismatch"
    assert outcome.inputs == current


def test_locked_geometry_cannot_be_mutated_by_any_family_search() -> None:
    baseline = BeamInputs(
        width_mm=300.0,
        depth_mm=500.0,
        width_locked=True,
        depth_locked=True,
        bottom=LongitudinalReinforcement(bars=3, diameter_mm=16),
    ).validated()
    result = DesignBrainService()._calculator.calculate_current(baseline).result
    assert result is not None
    capacity = float(result.families["bending"]["phi_Mu_kNm"])
    current = replace(
        baseline,
        actions=ActionInputs(bending_moment_knm=20.0 * capacity),
    ).validated()

    decision = DesignGuideOrchestrator().decide(current)

    assert decision.status is DecisionStatus.BLOCKED
    assert not decision.apply_allowed
    assert decision.advice.blocker is not None
    assert decision.advice.blocker.blocker_code == "geometry_locked"
    assert "locked by the user" in decision.advice.blocker.governing_requirement
    assert decision.candidate.proposal.width_mm == current.width_mm
    assert decision.candidate.proposal.depth_mm == current.depth_mm
