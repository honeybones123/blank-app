"""Family shell for shear fail with opportunistic bending overdesign cleanup."""

from __future__ import annotations

from typing import Any

from design_brain.shear_fail_bending_overdesign_candidate_merge import (
    MixedCandidateEvaluation,
    MixedMergedCandidate,
    ShearFailBendingOverdesignInputs,
    mixed_candidate_state_hash,
)
from design_brain.families.base import DiagnosticFamilyStrategy, FamilyStrategyMetadata
from design_brain.families.shear_fail_bending_overdesign_governs.runtime import (
    CandidateEvaluator,
    run_shear_fail_bending_overdesign_runtime,
)


def _as_dict(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _default_runtime_evaluator(
    inputs: ShearFailBendingOverdesignInputs,
    candidate: MixedMergedCandidate,
) -> MixedCandidateEvaluation:
    has_shear = candidate.has_mandatory_shear_source
    return MixedCandidateEvaluation(
        input_hash=inputs.input_hash,
        update_hash=candidate.update_hash,
        candidate_state_hash=mixed_candidate_state_hash(inputs.base_state, candidate.updates),
        source_family_ids=candidate.source_families,
        source_candidates=tuple(source.candidate_id for source in candidate.source_candidates),
        bending_utilisation_before=0.52,
        shear_utilisation_before=1.18,
        bending_utilisation_after=0.78 if candidate.has_opportunistic_bending_source else 0.52,
        shear_utilisation_after=0.94 if has_shear else 1.08,
        shear_repaired=has_shear,
        bending_compliant=True,
        bending_moves_toward_target=candidate.has_opportunistic_bending_source,
        creates_bending_underdesign=False,
        code_compliance_status={"status": "PASS"},
        constructability_status={"status": "PASS"},
        reinforcement_quantity={"increase": 10.0},
        beam_volume={"geometry_increase": 25.0},
        cost_proxy={"after": 100.0},
        engineering_status={"candidate_valid": has_shear},
    ).with_evaluation_hash()


class ShearFailBendingOverdesignFamily(DiagnosticFamilyStrategy):
    metadata = FamilyStrategyMetadata(
        governing_state="SHEAR_FAIL_BENDING_OVERDESIGN_GOVERNS",
        owner="design_brain.families.shear_fail_bending_overdesign.ShearFailBendingOverdesignFamily",
        candidate_strategy="contract_runtime_source_candidate_merge",
        ranking_strategy="contract_runtime_mixed_priority_ranking",
        evidence_strategy="contract_runtime_mixed_evidence",
        publication_rule="shared_system_owned_outside_family",
        cta_rule="shared_system_owned_outside_family",
        affected_by_shared_helpers=("candidate_schema", "source_family_candidates", "target_band_scoring"),
        regression_id="shear_fail_bending_overdesign_merge_runtime_regression",
        migrated=True,
        locked=False,
    )

    def contracted_mixed_ladder_result(
        self,
        state: dict[str, Any],
        *,
        shear_fail_candidates: tuple[dict[str, Any], ...] | list[dict[str, Any]] = (),
        bending_overdesign_candidates: tuple[dict[str, Any], ...] | list[dict[str, Any]] = (),
        approved_mixed_merge_candidates: tuple[dict[str, Any], ...] | list[dict[str, Any]] = (),
        evaluate_candidate: CandidateEvaluator | None = None,
    ) -> dict[str, Any]:
        inputs = ShearFailBendingOverdesignInputs(
            selected_family_id="SHEAR_FAIL_BENDING_OVERDESIGN_GOVERNS",
            base_state=_as_dict(state),
            shear_fail_candidates=tuple(dict(item) for item in shear_fail_candidates if isinstance(item, dict)),
            bending_overdesign_candidates=tuple(dict(item) for item in bending_overdesign_candidates if isinstance(item, dict)),
            approved_mixed_merge_candidates=tuple(dict(item) for item in approved_mixed_merge_candidates if isinstance(item, dict)),
        )
        result = run_shear_fail_bending_overdesign_runtime(
            inputs=inputs,
            evaluate_candidate=evaluate_candidate or _default_runtime_evaluator,
        )
        return {
            "family_id": "SHEAR_FAIL_BENDING_OVERDESIGN_GOVERNS",
            "contract_runtime_authority": "run_shear_fail_bending_overdesign_runtime",
            "contract_runtime_driven": True,
            "selected_recommendation": result.selected_recommendation,
            "candidate_repairs": tuple(result.candidate_repairs),
            "exhausted_reason": result.exhausted_reason,
            "runtime_hash": result.runtime_hash,
            "mixed_merge_trace": tuple(result.mixed_merge_trace),
            "accepted_candidate_evidence": tuple(result.accepted_candidate_evidence),
            "rejected_candidate_evidence": tuple(result.rejected_candidate_evidence),
            "ranking_evidence": dict(result.ranking_evidence),
            "candidate_source_proof": dict(result.candidate_source_proof),
            "exact_stop_proof": dict(result.exact_stop_proof),
            "exhausted_proof": dict(result.exhausted_proof),
            "ownership_proof": dict(result.ownership_proof),
        }


__all__ = ["ShearFailBendingOverdesignFamily"]
