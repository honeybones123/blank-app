from __future__ import annotations

from typing import Any

from design_brain.bending_fail_shear_overdesign_candidate_merge import (
    BendingFailShearOverdesignInputs,
    MixedCandidateEvaluation,
    MixedMergedCandidate,
    mixed_candidate_state_hash,
)
from design_brain.families.bending_fail_shear_overdesign_governs.runtime import (
    BendingFailShearOverdesignResult,
    run_bending_fail_shear_overdesign_runtime,
)
from design_brain.shared.schemas import FamilyResult


FAMILY_ID = "BENDING_FAIL_SHEAR_OVERDESIGN_GOVERNS"


def _inputs_from_context(context: dict[str, Any]) -> BendingFailShearOverdesignInputs:
    supplied = context.get("inputs")
    if isinstance(supplied, BendingFailShearOverdesignInputs):
        return supplied
    if isinstance(supplied, dict):
        return BendingFailShearOverdesignInputs(**supplied)
    return BendingFailShearOverdesignInputs(
        selected_family_id=str(context.get("selected_family_id") or FAMILY_ID),
        base_state=dict(context.get("base_state") or context.get("state") or {}),
        geometry=dict(context.get("geometry") or {}),
        reinforcement=dict(context.get("reinforcement") or {}),
        material_properties=dict(context.get("material_properties") or {}),
        actions=dict(context.get("actions") or {}),
        constraints=dict(context.get("constraints") or {}),
        bending_fail_candidates=tuple(context.get("bending_fail_candidates") or ()),
        shear_overdesign_candidates=tuple(context.get("shear_overdesign_candidates") or ()),
        approved_mixed_merge_candidates=tuple(context.get("approved_mixed_merge_candidates") or ()),
    )


def _default_evaluator(
    inputs: BendingFailShearOverdesignInputs,
    candidate: MixedMergedCandidate,
) -> MixedCandidateEvaluation:
    return MixedCandidateEvaluation(
        input_hash=inputs.input_hash,
        update_hash=candidate.update_hash,
        candidate_state_hash=mixed_candidate_state_hash(inputs.base_state, candidate.updates),
        source_family_ids=candidate.source_families,
        source_candidates=tuple(source.candidate_id for source in candidate.source_candidates),
        bending_repaired=False,
        shear_compliant=False,
        creates_shear_underdesign=False,
        code_compliance_status={"status": "NOT_EVALUATED"},
        constructability_status={"status": "NOT_EVALUATED"},
        rejection_reasons=("candidate evaluator adapter not supplied",),
        engineering_status={"candidate_valid": False},
    ).with_evaluation_hash()


def evaluate_bending_fail_shear_overdesign_governs(context: dict[str, Any]) -> FamilyResult:
    """Evaluate the mixed family through the contract merge runtime."""

    context_payload = dict(context or {})
    inputs = _inputs_from_context(context_payload)
    evaluator = context_payload.get("evaluate_candidate") or _default_evaluator
    result = run_bending_fail_shear_overdesign_runtime(inputs=inputs, evaluate_candidate=evaluator)
    selected = result.selected_recommendation
    return FamilyResult(
        family_id=FAMILY_ID,
        is_applicable=inputs.selected_family_id == FAMILY_ID,
        governing_score=None,
        status=result.status,
        selected_candidate=selected,
        updates=dict((selected or {}).get("updates") or {}),
        blockers=[{"reason": result.exhausted_reason, "source": "mixed_contract_runtime"}] if result.exhausted_reason else [],
        evidence={
            "contract_runtime_authority": "run_bending_fail_shear_overdesign_runtime",
            "runtime_result": result.to_family_result_payload(),
            "candidate_source_proof": result.candidate_source_proof,
            "ranking_evidence": result.ranking_evidence,
            "ownership_proof": result.ownership_proof,
        },
        publication={},
        cta_contract={},
        lock_proof={
            "runtime_authority": "run_bending_fail_shear_overdesign_runtime",
            "mixed_generates_no_bending_repair_ladder": True,
            "mixed_generates_no_shear_optimisation_ladder": True,
            "mandatory_objective": "bending repair",
            "opportunistic_objective": "shear optimisation",
            "runtime_hash": result.runtime_hash,
        },
    )


__all__ = [
    "BendingFailShearOverdesignInputs",
    "BendingFailShearOverdesignResult",
    "FAMILY_ID",
    "evaluate_bending_fail_shear_overdesign_governs",
    "run_bending_fail_shear_overdesign_runtime",
]
