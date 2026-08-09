"""Mutation contract proving that release verifiers reject false evidence.

This is deliberately an offline verification boundary.  It checks independent
relationships and invokes the production coherence guards; it does not make
Design Brain decisions or alter Runtime state.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from math import isclose
from pathlib import Path
import sys
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from application.apply_command import execute_apply_command
from application.contracts.design_brain import (
    EngineeringInputSnapshot,
    build_authoritative_design_result,
)
from application.design_brain_port import DesignBrainExecution, DesignBrainRequest
from application.design_brain_service import DesignBrainService as RuntimeDesignBrainService
from inputs_v2.application.candidate_evaluation import complete_compliance
from inputs_v2.application.design_brain_apply import apply_candidate
from inputs_v2.application.design_brain_service import DesignBrainService as V2DesignBrainService
from inputs_v2.application.design_guide_orchestrator import DesignGuideOrchestrator
from inputs_v2.domain.beam_inputs import ActionInputs, BeamInputs
from inputs_v2.domain.engineering_result import EngineeringResult
from inputs_v2.engineering.check_metadata import AS3600_2018_CHECKS


class EvidenceRejected(AssertionError):
    """Raised when supplied release evidence contradicts its authority."""


def verify_capacity_utilisation_evidence(
    inputs: BeamInputs,
    result: EngineeringResult,
    *,
    relative_tolerance: float = 1e-9,
) -> None:
    """Verify stored bending utilisation from independent demand/capacity data."""

    bending = result.families.get("bending")
    if not isinstance(bending, dict):
        raise EvidenceRejected("missing bending evidence")
    capacity = float(bending.get("phi_Mu_kNm", 0.0) or 0.0)
    stored_utilisation = float(bending.get("util", 0.0) or 0.0)
    demand = abs(float(inputs.actions.bending_moment_knm))
    if capacity <= 0.0:
        raise EvidenceRejected("non-positive bending capacity")
    independently_derived = demand / capacity
    if not isclose(
        stored_utilisation,
        independently_derived,
        rel_tol=relative_tolerance,
        abs_tol=1e-12,
    ):
        raise EvidenceRejected("bending capacity/utilisation relationship mismatch")


def verify_clause_evidence(result: EngineeringResult) -> None:
    """Verify calculation-owned clause records against the approved registry."""

    seen: set[str] = set()
    for family in result.families.values():
        metadata = family.get("check_metadata", {}) if isinstance(family, dict) else {}
        if not isinstance(metadata, dict):
            raise EvidenceRejected("invalid check metadata collection")
        for check_id, actual in metadata.items():
            expected = AS3600_2018_CHECKS.get(str(check_id))
            if expected is None or actual != expected:
                raise EvidenceRejected(f"clause metadata mismatch: {check_id}")
            seen.add(str(check_id))
    if not seen:
        raise EvidenceRejected("missing clause evidence")


def verify_mandatory_check_evidence(result: EngineeringResult) -> None:
    """Use the production mandatory-check gateway and fail closed."""

    if not complete_compliance(result):
        raise EvidenceRejected("mandatory candidate checks are incomplete or failed")


def verify_publication_authority_hash(result: Any) -> None:
    """Recompute the immutable publication envelope and reject tampering."""

    expected = result.with_publication_authority_hash().publication_authority_hash
    if not result.publication_authority_hash or result.publication_authority_hash != expected:
        raise EvidenceRejected("publication authority hash mismatch")


def _expect_rejection(label: str, operation: Callable[[], Any]) -> None:
    try:
        operation()
    except (EvidenceRejected, ValueError):
        return
    raise AssertionError(f"mutation was not rejected: {label}")


def _compliant_fixture() -> tuple[BeamInputs, EngineeringResult]:
    current = BeamInputs(
        actions=ActionInputs(bending_moment_knm=200.0, shear_force_kn=0.0)
    ).validated()
    decision = DesignGuideOrchestrator().decide(current)
    if decision.proposed_result is None or decision.candidate is None:
        raise AssertionError("fixture did not produce an actionable proposal")
    outcome = apply_candidate(current, decision.candidate)
    if not outcome.applied:
        raise AssertionError(f"positive fixture proposal did not apply: {outcome.reason}")
    proposed = outcome.inputs
    if proposed.content_hash != decision.proposed_result.source_hash:
        raise AssertionError("positive fixture proposal identity mismatch")
    return proposed, decision.proposed_result


def verify_engineering_mutations() -> None:
    inputs, result = _compliant_fixture()

    # Positive controls must pass before their corresponding mutations matter.
    verify_capacity_utilisation_evidence(inputs, result)
    verify_clause_evidence(result)
    verify_mandatory_check_evidence(result)

    capacity_families = deepcopy(result.families)
    capacity_families["bending"]["phi_Mu_kNm"] *= 1.10
    _expect_rejection(
        "capacity",
        lambda: verify_capacity_utilisation_evidence(
            inputs, replace(result, families=capacity_families)
        ),
    )

    utilisation_families = deepcopy(result.families)
    utilisation_families["bending"]["util"] *= 0.90
    _expect_rejection(
        "utilisation",
        lambda: verify_capacity_utilisation_evidence(
            inputs, replace(result, families=utilisation_families)
        ),
    )

    mandatory_families = deepcopy(result.families)
    mandatory_families.pop("reinforcement_fit")
    _expect_rejection(
        "mandatory-check",
        lambda: verify_mandatory_check_evidence(
            replace(result, families=mandatory_families)
        ),
    )

    clause_families = deepcopy(result.families)
    clause_families["bending"]["check_metadata"]["bending_capacity"][
        "clause"
    ] = "8.1.999"
    _expect_rejection(
        "clause",
        lambda: verify_clause_evidence(replace(result, families=clause_families)),
    )


class _StaticPort:
    def __init__(self, execution: DesignBrainExecution) -> None:
        self.execution = execution

    def run(self, _request: DesignBrainRequest) -> DesignBrainExecution:
        return self.execution


def verify_state_and_apply_mutations() -> None:
    snapshot = EngineeringInputSnapshot(
        geometry={"b": 300.0, "D": 500.0},
        design_actions={"Mu": 200.0, "Vu": 0.0},
    )
    result = build_authoritative_design_result(
        engineering_snapshot=snapshot,
        governing_family="BENDING_FAIL_GOVERNS",
        family_outcome="ACTION",
        selected_candidate={"candidate_id": "bend:candidate-1"},
        selected_updates={"D": 550.0},
        final_publication={"outcome_state": "ACTION"},
        cta_model={"enabled": True},
        apply_payload={
            "candidate_id": "bend:candidate-1",
            "family": "BENDING_FAIL_GOVERNS",
            "updates": {"D": 550.0},
        },
    )
    verify_publication_authority_hash(result)
    request = DesignBrainRequest(
        engineering_snapshot=snapshot,
        input_revision=7,
    )

    # Positive coherence and exact-candidate controls.
    execution = DesignBrainExecution(result=result, input_revision=7)
    RuntimeDesignBrainService(_StaticPort(execution)).run(request)
    dispatched: list[dict[str, Any]] = []
    apply_result = execute_apply_command(
        current_result=result,
        recommendation=dict(result.apply_payload),
        apply_fn=lambda payload: dispatched.append(payload) or "dispatch_ok",
    )
    if apply_result.status != "dispatch_ok" or len(dispatched) != 1:
        raise AssertionError("positive Apply candidate control failed")

    _expect_rejection(
        "revision",
        lambda: RuntimeDesignBrainService(
            _StaticPort(replace(execution, input_revision=6))
        ).run(request),
    )

    other_snapshot = replace(snapshot, geometry={"b": 325.0, "D": 500.0})
    hash_mutation = replace(result, engineering_hash=other_snapshot.engineering_hash)
    _expect_rejection(
        "engineering-hash",
        lambda: RuntimeDesignBrainService(
            _StaticPort(DesignBrainExecution(result=hash_mutation, input_revision=7))
        ).run(request),
    )

    authority_hash_mutation = replace(result, publication_authority_hash="corrupt")
    _expect_rejection(
        "publication-authority-hash",
        lambda: verify_publication_authority_hash(authority_hash_mutation),
    )

    rejected_dispatches: list[dict[str, Any]] = []
    candidate_result = execute_apply_command(
        current_result=result,
        recommendation={
            **result.apply_payload,
            "candidate_id": "bend:different-candidate",
        },
        apply_fn=lambda payload: rejected_dispatches.append(payload) or "dispatch_ok",
    )
    if (
        candidate_result.status != "failed"
        or candidate_result.reason != "stale_authoritative_apply_payload"
        or rejected_dispatches
    ):
        raise AssertionError("Apply-candidate mutation was not rejected before dispatch")

    update_dispatches: list[dict[str, Any]] = []
    update_result = execute_apply_command(
        current_result=result,
        recommendation={
            **result.apply_payload,
            "updates": {"D": 900.0},
        },
        apply_fn=lambda payload: update_dispatches.append(payload) or "dispatch_ok",
    )
    if (
        update_result.status != "failed"
        or update_result.reason != "stale_authoritative_apply_payload"
        or update_dispatches
    ):
        raise AssertionError("Apply-candidate update mutation was not rejected before dispatch")


def main() -> None:
    verify_engineering_mutations()
    verify_state_and_apply_mutations()
    print(
        "verifier mutation contract: PASS "
        "(capacity, utilisation, mandatory-check, clause, revision, hash, Apply-candidate)"
    )


if __name__ == "__main__":
    main()
