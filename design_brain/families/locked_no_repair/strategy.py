"""Locked-input no-repair governing-family shell."""

from __future__ import annotations

from design_brain.families.base import DiagnosticFamilyStrategy, FamilyStrategyMetadata


class LockedNoRepairFamily(DiagnosticFamilyStrategy):
    metadata = FamilyStrategyMetadata(
        governing_state="LOCKED_NO_REPAIR",
        owner="design_brain.families.locked_no_repair.LockedNoRepairFamily",
        candidate_strategy="adapter_to_existing_lock_constrained_attempts",
        ranking_strategy="disabled_when_locked_inputs_prevent_safe_repair",
        evidence_strategy="locked_input_no_repair_evidence",
        publication_rule="locked_input_blocked",
        cta_rule="disabled_with_named_locked_input_reason",
        affected_by_shared_helpers=("candidate_schema",),
        regression_id="locked_no_repair_regression",
        migrated=True,
    )


__all__ = ["LockedNoRepairFamily"]
