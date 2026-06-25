from __future__ import annotations

from typing import Any

from design_brain.families.bending_and_shear_overdesign_govern.runtime import (
    CombinedOverdesignGovernsResult,
    run_combined_overdesign_governs_runtime,
)
from design_brain.shared.schemas import FamilyResult


FAMILY_ID = "COMBINED_OVERDESIGN_GOVERNS"
RUNTIME_FAMILY_ID = "COMBINED_OVERDESIGN"


def evaluate_bending_and_shear_overdesign_govern(context: dict[str, Any]) -> FamilyResult:
    """Evaluate combined overdesign through the contract merge runtime."""

    from design_brain.families.combined_cleanup import CombinedCleanupFamily

    state = dict(context.get("state") or context.get("base_state") or context.get("payload") or {})
    family = CombinedCleanupFamily()
    ladder = family.contracted_optimisation_ladder_specs(
        state,
        bending_overdesign_candidates=tuple(context.get("bending_overdesign_candidates") or ()),
        shear_overdesign_candidates=tuple(context.get("shear_overdesign_candidates") or ()),
        approved_combined_merge_candidates=tuple(context.get("approved_combined_merge_candidates") or ()),
    )
    selected = dict(ladder.get("selected_recommendation") or {})
    updates = dict(selected.get("updates") or {})
    return FamilyResult(
        family_id=FAMILY_ID,
        is_applicable=True,
        status="CONTRACT_RUNTIME_READY",
        selected_candidate=selected or None,
        updates=updates,
        evidence={
            "contract_runtime_authority": "run_combined_overdesign_governs_runtime",
            "runtime_family_id": RUNTIME_FAMILY_ID,
            "ladder": ladder,
        },
        publication={},
        cta_contract={},
        lock_proof={
            "contract_runtime_driven": True,
            "runtime_authority": "run_combined_overdesign_governs_runtime",
            "legacy_decision_authority": False,
            "combined_generates_no_optimisation_ladder": True,
            "shared_systems_remain_shared": True,
        },
    )


__all__ = [
    "CombinedOverdesignGovernsResult",
    "FAMILY_ID",
    "RUNTIME_FAMILY_ID",
    "evaluate_bending_and_shear_overdesign_govern",
    "run_combined_overdesign_governs_runtime",
]
