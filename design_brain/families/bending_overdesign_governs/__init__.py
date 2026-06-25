from __future__ import annotations

from typing import Any

from design_brain.families.bending_overdesign_governs.runtime import (
    BendingOverdesignGovernsResult,
    bending_overdesign_contract_lane_order,
    run_bending_overdesign_governs_runtime,
)
from design_brain.shared.schemas import FamilyResult


FAMILY_ID = "BENDING_OVERDESIGN_GOVERNS"


def evaluate_bending_overdesign_governs(context: dict[str, Any]) -> FamilyResult:
    """Evaluate the bending-overdesign family through the contract runtime proof surface."""

    from design_brain.families.bending_cleanup import BendingCleanupFamily

    family = BendingCleanupFamily()
    state = dict(context.get("state") or context.get("base_state") or context.get("payload") or {})
    ladder = family.contracted_optimisation_ladder_specs(state)
    selected = dict(ladder.get("selected_recommendation") or {})
    updates = dict(selected.get("updates") or {})
    return FamilyResult(
        family_id=FAMILY_ID,
        is_applicable=True,
        status="CONTRACT_RUNTIME_READY",
        selected_candidate=selected or None,
        updates=updates,
        evidence={
            "contract_runtime_authority": "run_bending_overdesign_governs_runtime",
            "ladder": ladder,
            "contract_lane_order": bending_overdesign_contract_lane_order(),
        },
        publication={},
        cta_contract={},
        lock_proof={
            "contract_runtime_driven": True,
            "runtime_authority": "run_bending_overdesign_governs_runtime",
            "legacy_decision_authority": False,
            "product_routing_enabled": False,
            "shared_systems_remain_shared": True,
        },
    )


__all__ = [
    "BendingOverdesignGovernsResult",
    "FAMILY_ID",
    "bending_overdesign_contract_lane_order",
    "evaluate_bending_overdesign_governs",
    "run_bending_overdesign_governs_runtime",
]
