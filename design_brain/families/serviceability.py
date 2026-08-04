"""Serviceability governing-family shell."""

from __future__ import annotations

from design_brain.families.base import DiagnosticFamilyStrategy, FamilyStrategyMetadata


class ServiceabilityFamily(DiagnosticFamilyStrategy):
    metadata = FamilyStrategyMetadata(
        governing_state="SERVICEABILITY_GOVERNS",
        owner="design_brain.families.serviceability.ServiceabilityFamily",
        candidate_strategy="contract_runtime_candidate_generation",
        ranking_strategy="contract_runtime_serviceability_ranking",
        evidence_strategy="contract_runtime_exact_stop_exhausted_and_blocker_evidence",
        publication_rule="serviceability_repair_blocked_or_optimisation_stop",
        cta_rule="enabled_only_when_preview_resolves_serviceability",
        affected_by_shared_helpers=("capacity_checks", "candidate_schema", "target_band_scoring"),
        regression_id="serviceability_governs_regression",
        migrated=True,
    )

    def contracted_serviceability_ladder_result(
        self,
        base_state: dict,
        *,
        evaluate_candidate=None,
    ) -> dict:
        """Return the contract-runtime result for app-gateway verification."""

        from design_brain.families.serviceability_governs import evaluate_serviceability_governs

        context = {"base_state": dict(base_state or {})}
        if evaluate_candidate is not None:
            context["evaluate_candidate"] = evaluate_candidate
        result = evaluate_serviceability_governs(context)
        runtime_result = dict((result.evidence or {}).get("runtime_result") or {})
        return {
            "contract_runtime_driven": True,
            "runtime_authority": result.lock_proof.get("contract_runtime_authority"),
            "contract_runtime_authority": result.lock_proof.get("contract_runtime_authority"),
            "ladder_hash": runtime_result.get("ladder_hash"),
            "runtime_result": runtime_result,
            "status": result.status,
            "selected_recommendation": result.selected_candidate,
            "updates": dict(result.updates or {}),
        }


__all__ = ["ServiceabilityFamily"]
