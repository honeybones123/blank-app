from __future__ import annotations

from typing import Any

from design_brain.families.base import FamilyStrategyContext
from design_brain.families.bending_fail_governs.runtime import (
    BendingFailGovernsResult,
    bending_fail_governs_contract_lane_order,
    run_bending_fail_governs_ladder_runtime,
)
from design_brain.shared.schemas import FamilyResult


FAMILY_ID = "BENDING_FAIL_GOVERNS"


def evaluate_bending_fail_governs(context: dict[str, Any]) -> FamilyResult:
    """Evaluate the bending-fail governing family through the legacy adapter.

    This compatibility API exposes the target governing-family package shape
    without routing product behaviour through it yet. It delegates to the
    existing diagnostic ``BendingFailFamily`` strategy and adapts read-only
    diagnostics to the shared ``FamilyResult`` shape.
    """

    from design_brain.families.bending_fail import BendingFailFamily

    strategy = BendingFailFamily()
    family_context = FamilyStrategyContext(
        governing_state=FAMILY_ID,
        payload=dict(context.get("payload") or {}),
        primary=dict(context.get("primary") or {}),
        summary=dict(context.get("summary") or {}),
        evidence=dict(context.get("evidence") or {}),
        debug=dict(context.get("debug") or {}),
        classifier=dict(context.get("classifier") or {}),
    )
    classification = strategy.classify(family_context)
    candidate_result = strategy.generate_candidates(family_context)
    ranked_result = strategy.rank_candidates(family_context)
    evidence_result = strategy.build_evidence(family_context, ranked_result)
    publication_result = strategy.publish(family_context, evidence_result)
    cta_result = strategy.get_cta_rule(family_context, evidence_result)
    contract_runtime_order = bending_fail_governs_contract_lane_order()
    is_applicable = bool(classification.get("bending_fail_identified"))
    governing_score = classification.get("bending_util")
    try:
        parsed_score = float(governing_score) if governing_score is not None else None
    except (TypeError, ValueError):
        parsed_score = None
    blockers = []
    if classification.get("unsupported_reason"):
        blockers.append(
            {
                "source": "classification",
                "reason": classification.get("unsupported_reason"),
                "missing_inputs": list(classification.get("missing_inputs") or []),
            }
        )
    if candidate_result.get("unsupported_reason"):
        blockers.append(
            {
                "source": "candidate_result",
                "reason": candidate_result.get("unsupported_reason"),
                "missing_inputs": list(candidate_result.get("missing_inputs") or []),
            }
        )
    return FamilyResult(
        family_id=FAMILY_ID,
        is_applicable=is_applicable,
        governing_score=parsed_score,
        status="FAIL" if is_applicable else "NOT_APPLICABLE",
        selected_candidate=None,
        updates={},
        blockers=blockers,
        evidence={
            "classification": classification,
            "candidate_result": candidate_result,
            "ranked_result": ranked_result,
            "evidence_result": evidence_result,
            "contract_runtime": {
                "authority": "run_bending_fail_governs_ladder_runtime",
                "contract_lane_order": list(contract_runtime_order),
                "legacy_decision_authority": False,
            },
        },
        publication=publication_result,
        cta_contract=cta_result,
        lock_proof={
            "compatibility_api": True,
            "contract_runtime_authority": "run_bending_fail_governs_ladder_runtime",
            "contract_lane_order": list(contract_runtime_order),
            "legacy_decision_authority": False,
            "legacy_owner": strategy.metadata.owner,
            "product_routing_enabled": False,
        },
    )


__all__ = [
    "BendingFailGovernsResult",
    "FAMILY_ID",
    "bending_fail_governs_contract_lane_order",
    "evaluate_bending_fail_governs",
    "run_bending_fail_governs_ladder_runtime",
]
