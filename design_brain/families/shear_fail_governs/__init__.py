from __future__ import annotations

from typing import Any

from design_brain.families.base import FamilyStrategyContext
from design_brain.families.shear_fail_governs.runtime import shear_fail_governs_contract_lane_order
from design_brain.shared.schemas import FamilyResult


FAMILY_ID = "SHEAR_FAIL_GOVERNS"


def evaluate_shear_fail_governs(context: dict[str, Any]) -> FamilyResult:
    """Evaluate the shear-fail governing family through the legacy adapter.

    This is a compatibility API only. It does not route product behaviour
    through the new package yet; it delegates to the existing diagnostic
    ``ShearFailFamily`` strategy and adapts read-only diagnostics to the shared
    ``FamilyResult`` shape.
    """

    from design_brain.families.shear_fail import ShearFailFamily

    strategy = ShearFailFamily()
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
    is_applicable = bool(classification.get("shear_fail_identified"))
    governing_score = classification.get("shear_util")
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
            "contract_runtime_authority": "run_shear_fail_governs_ladder_runtime",
            "contract_runtime_lane_order": tuple(shear_fail_governs_contract_lane_order()),
        },
        publication=publication_result,
        cta_contract=cta_result,
        lock_proof={
            "compatibility_api": True,
            "legacy_owner": strategy.metadata.owner,
            "contract_runtime_authority": "run_shear_fail_governs_ladder_runtime",
            "contract_runtime_lane_order": tuple(shear_fail_governs_contract_lane_order()),
            "product_routing_enabled": False,
        },
    )


__all__ = ["FAMILY_ID", "evaluate_shear_fail_governs"]
