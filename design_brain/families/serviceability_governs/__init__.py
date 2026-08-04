from __future__ import annotations

from typing import Any

from design_brain.families.serviceability_governs.contract import serviceability_contract_lane_order
from design_brain.families.serviceability_governs.runtime import (
    ServiceabilityGovernsResult,
    ServiceabilityInputs,
    run_serviceability_governs_ladder_runtime,
)
from design_brain.serviceability_candidate_evaluation import (
    ServiceabilityCandidateEvaluation,
    ServiceabilityCandidateInput,
    ServiceabilityCandidateUpdate,
    build_serviceability_candidate_state_hash,
)
from design_brain.shared.schemas import FamilyResult


FAMILY_ID = "SERVICEABILITY_GOVERNS"


def _runtime_inputs_from_context(context: dict[str, Any]) -> ServiceabilityInputs:
    supplied = context.get("serviceability_inputs")
    if isinstance(supplied, ServiceabilityInputs):
        return supplied
    if isinstance(supplied, dict):
        return ServiceabilityInputs(**supplied)
    return ServiceabilityInputs(
        selected_family_id=str(context.get("selected_family_id") or FAMILY_ID),
        base_state=dict(context.get("base_state") or context.get("payload") or {}),
        geometry=dict(context.get("geometry") or {}),
        reinforcement=dict(context.get("reinforcement") or {}),
        material_properties=dict(context.get("material_properties") or {}),
        actions=dict(context.get("actions") or {}),
        constraints=dict(context.get("constraints") or {}),
    )


def _default_boundary_evaluator(
    candidate_input: ServiceabilityCandidateInput,
    candidate_update: ServiceabilityCandidateUpdate,
) -> ServiceabilityCandidateEvaluation:
    """Fallback proof evaluator used only when no adapter is supplied."""

    return ServiceabilityCandidateEvaluation(
        input_hash=candidate_input.input_hash,
        update_hash=candidate_update.update_hash,
        candidate_state_hash=build_serviceability_candidate_state_hash(
            candidate_input.base_state,
            candidate_update.updates,
        ),
        serviceability_utilisation=None,
        previous_serviceability_utilisation=None,
        serviceability_improved=False,
        serviceability_compliant=False,
        deflection_status={"status": "NOT_EVALUATED"},
        crack_control_status={"status": "NOT_EVALUATED"},
        strength_status={"overall": "NOT_EVALUATED"},
        code_compliance_status={"overall": "NOT_EVALUATED"},
        constructability_status={"overall": "NOT_EVALUATED"},
        geometry_status={"status": "NOT_EVALUATED"},
        reinforcement_status={"status": "NOT_EVALUATED"},
        blocker_status={
            "blocked": True,
            "reasons": ["candidate evaluator adapter not supplied"],
        },
        capacity_summary={},
        failure_flags={
            "serviceability_fail": True,
            "bending_fail": False,
            "shear_fail": False,
            "constructability_fail": False,
        },
        engineering_status={"overall": "NOT_EVALUATED"},
    ).with_evaluation_hash()


def evaluate_serviceability_governs(context: dict[str, Any]) -> FamilyResult:
    """Evaluate SERVICEABILITY_GOVERNS through the contract runtime."""

    context_payload = dict(context or {})
    runtime_inputs = _runtime_inputs_from_context(context_payload)
    evaluator = context_payload.get("evaluate_candidate") or _default_boundary_evaluator
    result = run_serviceability_governs_ladder_runtime(
        serviceability_inputs=runtime_inputs,
        evaluate_candidate=evaluator,
    )
    return FamilyResult(
        family_id=FAMILY_ID,
        is_applicable=runtime_inputs.selected_family_id == FAMILY_ID,
        governing_score=None,
        status=result.status,
        selected_candidate=result.selected_recommendation,
        updates=dict((result.selected_recommendation or {}).get("updates") or {}),
        blockers=[
            {"reason": result.exhausted_reason, "source": "serviceability_contract_runtime"}
        ]
        if result.exhausted_reason
        else [],
        evidence={
            "contract_runtime_authority": "run_serviceability_governs_ladder_runtime",
            "runtime_result": result.to_dict(),
            "contract_runtime_lane_order": tuple(serviceability_contract_lane_order()),
        },
        publication={},
        cta_contract={},
        lock_proof={
            "compatibility_api": False,
            "contract_runtime_authority": "run_serviceability_governs_ladder_runtime",
            "product_routing_enabled": True,
            "shared_app_ownership_moved": False,
            "ladder_hash": result.ladder_hash,
        },
    )


__all__ = [
    "FAMILY_ID",
    "ServiceabilityGovernsResult",
    "ServiceabilityInputs",
    "evaluate_serviceability_governs",
    "run_serviceability_governs_ladder_runtime",
]
