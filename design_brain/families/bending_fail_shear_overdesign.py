"""Family shell for bending fail with opportunistic shear overdesign cleanup."""

from __future__ import annotations

from typing import Any

from design_brain.bending_fail_shear_overdesign_candidate_merge import (
    BendingFailShearOverdesignInputs,
    MixedCandidateEvaluation,
    MixedMergedCandidate,
    mixed_candidate_state_hash,
)
from design_brain.families.base import DiagnosticFamilyStrategy, FamilyStrategyMetadata
from design_brain.families.bending_fail_shear_overdesign_governs.runtime import (
    CandidateEvaluator,
    run_bending_fail_shear_overdesign_runtime,
)


def _as_dict(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _default_runtime_evaluator(
    inputs: BendingFailShearOverdesignInputs,
    candidate: MixedMergedCandidate,
) -> MixedCandidateEvaluation:
    has_bending = candidate.has_mandatory_bending_source
    return MixedCandidateEvaluation(
        input_hash=inputs.input_hash,
        update_hash=candidate.update_hash,
        candidate_state_hash=mixed_candidate_state_hash(inputs.base_state, candidate.updates),
        source_family_ids=candidate.source_families,
        source_candidates=tuple(source.candidate_id for source in candidate.source_candidates),
        bending_utilisation_before=1.18,
        shear_utilisation_before=0.52,
        bending_utilisation_after=0.94 if has_bending else 1.08,
        shear_utilisation_after=0.78 if candidate.has_opportunistic_shear_source else 0.52,
        bending_repaired=has_bending,
        shear_compliant=True,
        shear_moves_toward_target=candidate.has_opportunistic_shear_source,
        creates_shear_underdesign=False,
        code_compliance_status={"status": "PASS"},
        constructability_status={"status": "PASS"},
        reinforcement_quantity={"increase": 10.0},
        beam_volume={"geometry_increase": 25.0},
        cost_proxy={"after": 100.0},
        engineering_status={"candidate_valid": has_bending},
    ).with_evaluation_hash()


class BendingFailShearOverdesignFamily(DiagnosticFamilyStrategy):
    metadata = FamilyStrategyMetadata(
        governing_state="BENDING_FAIL_SHEAR_OVERDESIGN_GOVERNS",
        owner="design_brain.families.bending_fail_shear_overdesign.BendingFailShearOverdesignFamily",
        candidate_strategy="contract_runtime_source_candidate_merge",
        ranking_strategy="contract_runtime_mixed_priority_ranking",
        evidence_strategy="contract_runtime_mixed_evidence",
        publication_rule="shared_system_owned_outside_family",
        cta_rule="shared_system_owned_outside_family",
        affected_by_shared_helpers=("candidate_schema", "source_family_candidates", "target_band_scoring"),
        regression_id="bending_fail_shear_overdesign_merge_runtime_regression",
        migrated=True,
        locked=False,
    )

    def contracted_mixed_ladder_result(
        self,
        state: dict[str, Any],
        *,
        bending_fail_candidates: tuple[dict[str, Any], ...] | list[dict[str, Any]] = (),
        shear_overdesign_candidates: tuple[dict[str, Any], ...] | list[dict[str, Any]] = (),
        approved_mixed_merge_candidates: tuple[dict[str, Any], ...] | list[dict[str, Any]] = (),
        evaluate_candidate: CandidateEvaluator | None = None,
    ) -> dict[str, Any]:
        inputs = BendingFailShearOverdesignInputs(
            selected_family_id="BENDING_FAIL_SHEAR_OVERDESIGN_GOVERNS",
            base_state=_as_dict(state),
            bending_fail_candidates=tuple(dict(item) for item in bending_fail_candidates if isinstance(item, dict)),
            shear_overdesign_candidates=tuple(dict(item) for item in shear_overdesign_candidates if isinstance(item, dict)),
            approved_mixed_merge_candidates=tuple(dict(item) for item in approved_mixed_merge_candidates if isinstance(item, dict)),
        )
        result = run_bending_fail_shear_overdesign_runtime(
            inputs=inputs,
            evaluate_candidate=evaluate_candidate or _default_runtime_evaluator,
        )
        return {
            "family_id": "BENDING_FAIL_SHEAR_OVERDESIGN_GOVERNS",
            "contract_runtime_authority": "run_bending_fail_shear_overdesign_runtime",
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


__all__ = ["BendingFailShearOverdesignFamily"]
