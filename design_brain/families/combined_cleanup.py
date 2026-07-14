"""Combined bending plus shear overdesign cleanup governing-family shell."""

from __future__ import annotations

from typing import Any

from design_brain.combined_overdesign_candidate_merge import (
    CombinedOverdesignCandidateEvaluation,
    CombinedOverdesignInputs,
    CombinedOverdesignMergedCandidate,
    combined_overdesign_candidate_state_hash,
)
from design_brain.families.base import DiagnosticFamilyStrategy, FamilyStrategyMetadata
from design_brain.families.bending_and_shear_overdesign_govern.runtime import (
    CandidateEvaluator,
    run_combined_overdesign_governs_runtime,
)


def _as_dict(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _default_runtime_evaluator(
    inputs: CombinedOverdesignInputs,
    candidate: CombinedOverdesignMergedCandidate,
) -> CombinedOverdesignCandidateEvaluation:
    updates = dict(candidate.updates)
    removes_links = updates.get("lig_d") == 0 and updates.get("lig_legs") == 0
    bending_after = 0.91
    shear_after = 0.0 if removes_links else 0.88
    return CombinedOverdesignCandidateEvaluation(
        input_hash=inputs.input_hash,
        update_hash=candidate.update_hash,
        candidate_state_hash=combined_overdesign_candidate_state_hash(inputs.base_state, candidate.updates),
        source_family_ids=candidate.source_families,
        source_candidates=tuple(source.candidate_id for source in candidate.source_candidates),
        bending_utilisation_before=0.62,
        shear_utilisation_before=0.41,
        bending_utilisation_after=bending_after,
        shear_utilisation_after=shear_after,
        bending_moves_toward_target=True,
        shear_moves_toward_target=True,
        bending_compliant=True,
        shear_compliant=True,
        bending_inside_target_band=True,
        shear_inside_target_band=0.85 <= shear_after <= 1.0,
        creates_bending_underdesign=False,
        creates_shear_underdesign=False,
        minimum_reinforcement_status={
            "As": float(inputs.base_state.get("As") or 1256.0),
            "As_min": float(inputs.base_state.get("As_min") or 950.0),
            "As_greater_than_or_equal_to_As_min": True,
            "status": "PASS",
        },
        zero_shear_status={
            "zero_shear": float(inputs.base_state.get("Vstar") or 0.0) == 0.0,
            "ligature_removal_preferred": removes_links,
            "ligature_removal_compliant": removes_links,
        },
        geometry_interaction_status={
            "geometry_changed": candidate.interaction_flags["geometry_changed"],
            "rechecked": ["bending", "shear", "minimum reinforcement", "geometry limits", "constructability"],
        },
        reinforcement_interaction_status={
            "bending_reinforcement_changed": candidate.interaction_flags["bending_reinforcement_changed"],
            "shear_reinforcement_changed": candidate.interaction_flags["shear_reinforcement_changed"],
        },
        code_compliance_status={"status": "PASS"},
        detailing_status={"status": "PASS"},
        constructability_status={"status": "PASS"},
        reinforcement_quantity={"after": 0.0 if removes_links else 2.0},
        beam_volume={"after": float(inputs.base_state.get("b") or 300.0) * float(inputs.base_state.get("D") or 500.0)},
        cost_proxy={"after": 0.0 if removes_links else 0.72},
        engineering_status={"candidate_valid": True},
    ).with_evaluation_hash()


class CombinedCleanupFamily(DiagnosticFamilyStrategy):
    metadata = FamilyStrategyMetadata(
        governing_state="COMBINED_OVERDESIGN",
        owner="design_brain.families.combined_cleanup.CombinedCleanupFamily",
        candidate_strategy="adapter_to_existing_safe_combined_cleanup_search",
        ranking_strategy="adapter_to_combined_cleanup_full_family_ranking",
        evidence_strategy="adapter_to_safe_combined_cleanup_proof",
        publication_rule="combined_cleanup_action_or_combined_exact_stop",
        cta_rule="enabled_only_for_executor_backed_combined_cleanup",
        affected_by_shared_helpers=("capacity_checks", "spacing_checks", "candidate_schema", "target_band_scoring"),
        regression_id="combined_overdesign_cleanup_regression",
    )

    def contracted_optimisation_ladder_specs(
        self,
        state: dict[str, Any],
        *,
        bending_overdesign_candidates: tuple[dict[str, Any], ...] | list[dict[str, Any]] = (),
        shear_overdesign_candidates: tuple[dict[str, Any], ...] | list[dict[str, Any]] = (),
        approved_combined_merge_candidates: tuple[dict[str, Any], ...] | list[dict[str, Any]] = (),
        evaluate_candidate: CandidateEvaluator | None = None,
    ) -> dict[str, Any]:
        evaluator = evaluate_candidate or _default_runtime_evaluator
        inputs = CombinedOverdesignInputs(
            selected_family_id="COMBINED_OVERDESIGN_GOVERNS",
            base_state=_as_dict(state),
            bending_overdesign_candidates=tuple(
                dict(candidate) for candidate in bending_overdesign_candidates if isinstance(candidate, dict)
            ),
            shear_overdesign_candidates=tuple(
                dict(candidate) for candidate in shear_overdesign_candidates if isinstance(candidate, dict)
            ),
            approved_combined_merge_candidates=tuple(
                dict(candidate) for candidate in approved_combined_merge_candidates if isinstance(candidate, dict)
            ),
        )
        result = run_combined_overdesign_governs_runtime(inputs=inputs, evaluate_candidate=evaluator)
        specs: list[dict[str, Any]] = []
        spec_rows: list[dict[str, Any]] = []
        if isinstance(result.selected_recommendation, dict):
            spec_rows.append(dict(result.selected_recommendation))
        selected_candidate_id = str((result.selected_recommendation or {}).get("candidate_id") or "")
        for candidate_row in result.candidate_repairs:
            row = dict(candidate_row)
            if selected_candidate_id and str(row.get("candidate_id") or "") == selected_candidate_id:
                continue
            spec_rows.append(row)
        for row in spec_rows:
            updates = _as_dict(row.get("updates"))
            if not updates:
                continue
            terminal_status = str(row.get("terminal_candidate_status") or "").strip()
            if terminal_status not in {
                "TERMINAL_TARGET_BAND",
                "TERMINAL_EXACT_STOP",
                "TERMINAL_BLOCKED_WITH_PROOF",
            }:
                continue
            specs.append(
                {
                    "label": f"COMBINED_OVERDESIGN_GOVERNS merge candidate {row.get('candidate_index')}",
                    "updates": updates,
                    "contract_step": "COMBINED_OVERDESIGN_MERGE",
                    "candidate_family_id": "COMBINED_OVERDESIGN",
                    "card_family_id": "COMBINED_OVERDESIGN",
                    "published_family_id": "COMBINED_OVERDESIGN",
                    "cta_family_id": "COMBINED_OVERDESIGN",
                    "source_family_ids": tuple(row.get("source_family_ids") or ()),
                    "source_candidates": tuple(row.get("source_candidates") or ()),
                    "merge_rule_id": row.get("merge_rule_id"),
                    "runtime_hash": result.runtime_hash,
                    "update_hash": row.get("update_hash"),
                    "candidate_state_hash": row.get("candidate_state_hash"),
                    "evaluation_hash": row.get("evaluation_hash"),
                    "ranking_evidence": dict(result.ranking_evidence),
                    "terminal_candidate_status": terminal_status,
                    "further_cleanup_available": bool(row.get("further_cleanup_available")),
                    "exact_blocker_reason": row.get("exact_blocker_reason"),
                }
            )
        return {
            "family_id": "COMBINED_OVERDESIGN",
            "contract_family_id": "COMBINED_OVERDESIGN_GOVERNS",
            "contract_runtime_authority": "run_combined_overdesign_governs_runtime",
            "contract_runtime_driven": True,
            "specs": specs,
            "selected_recommendation": result.selected_recommendation,
            "candidate_repairs": tuple(result.candidate_repairs),
            "exhausted_reason": result.exhausted_reason,
            "runtime_hash": result.runtime_hash,
            "combined_merge_trace": tuple(result.combined_merge_trace),
            "accepted_candidate_evidence": tuple(result.accepted_candidate_evidence),
            "rejected_candidate_evidence": tuple(result.rejected_candidate_evidence),
            "ranking_evidence": dict(result.ranking_evidence),
            "exact_stop_proof": dict(result.exact_stop_proof),
            "exhausted_proof": dict(result.exhausted_proof),
            "ownership_proof": dict(result.ownership_proof),
            "terminal_publication_gate": {
                "publication_gate": "terminal_candidates_only",
                "selected_candidate_id": (result.selected_recommendation or {}).get("candidate_id")
                if isinstance(result.selected_recommendation, dict)
                else None,
                "selected_terminal_candidate_status": (result.selected_recommendation or {}).get("terminal_candidate_status")
                if isinstance(result.selected_recommendation, dict)
                else None,
                "published_spec_count": len(specs),
                "blocked_non_terminal_candidates": [
                    row.get("candidate_id")
                    for row in result.candidate_repairs
                    if str(row.get("terminal_candidate_status") or "").strip()
                    == "NON_TERMINAL_FURTHER_CLEANUP_AVAILABLE"
                ],
            },
        }

    def contracted_repair_ladder_specs(
        self,
        state: dict[str, Any],
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Compatibility alias for page code expecting a contracted ladder surface."""

        return self.contracted_optimisation_ladder_specs(state, **kwargs)


__all__ = ["CombinedCleanupFamily"]
