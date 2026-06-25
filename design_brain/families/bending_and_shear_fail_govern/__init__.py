from __future__ import annotations

from typing import Any

from design_brain.families.bending_and_shear_fail_govern.runtime import (
    CombinedBendingShearFailResult,
    run_combined_bending_shear_fail_runtime,
)
from design_brain.shared.schemas import FamilyResult


FAMILY_ID = "COMBINED_BENDING_SHEAR_FAIL_GOVERNS"
RUNTIME_FAMILY_ID = "COMBINED_BENDING_SHEAR_FAIL"


def evaluate_bending_and_shear_fail_govern(context: dict[str, Any]) -> FamilyResult:
    """Evaluate the combined active-fail family through the contract merge runtime."""

    from design_brain.families.combined_bending_shear_fail import CombinedBendingShearFailFamily

    family = CombinedBendingShearFailFamily()
    state = dict(context.get("state") or context.get("base_state") or context.get("payload") or {})
    ladder = family.contracted_repair_ladder_specs(
        state,
        bending_fail_candidates=tuple(context.get("bending_fail_candidates") or ()),
        shear_fail_candidates=tuple(context.get("shear_fail_candidates") or ()),
    )
    selected = dict(ladder.get("selected_recommendation") or {})
    return FamilyResult(
        family_id=FAMILY_ID,
        is_applicable=True,
        status="CONTRACT_RUNTIME_READY",
        selected_candidate=selected or None,
        updates=dict(selected.get("updates") or {}),
        blockers=[] if selected else [{"reason": ladder.get("exhausted_reason") or "no valid combined repair exists"}],
        evidence={
            "runtime_family_id": RUNTIME_FAMILY_ID,
            "contract_runtime_authority": "run_combined_bending_shear_fail_runtime",
            "ladder": ladder,
        },
        publication={},
        cta_contract={},
        lock_proof={
            "contract_runtime_driven": True,
            "runtime_authority": "run_combined_bending_shear_fail_runtime",
            "legacy_decision_authority": False,
            "product_routing_enabled": False,
            "shared_systems_remain_shared": True,
        },
    )


__all__ = [
    "CombinedBendingShearFailResult",
    "FAMILY_ID",
    "RUNTIME_FAMILY_ID",
    "evaluate_bending_and_shear_fail_govern",
    "run_combined_bending_shear_fail_runtime",
]
