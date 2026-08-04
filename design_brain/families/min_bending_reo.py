"""Minimum bending reinforcement governing stop shell."""

from __future__ import annotations

from design_brain.families.base import DiagnosticFamilyStrategy, FamilyStrategyMetadata


class MinBendingReoFamily(DiagnosticFamilyStrategy):
    metadata = FamilyStrategyMetadata(
        governing_state="MIN_BENDING_REO_GOVERNS",
        owner="design_brain.families.min_bending_reo.MinBendingReoFamily",
        candidate_strategy="adapter_to_existing_bending_cleanup_attempts",
        ranking_strategy="disabled_when_minimum_bending_reinforcement_governs",
        evidence_strategy="minimum_bending_reinforcement_exact_stop_evidence",
        publication_rule="bending_minimum_reinforcement_optimisation_stop",
        cta_rule="disabled_when_minimum_bending_reinforcement_governs",
        affected_by_shared_helpers=("capacity_checks", "cover_checks", "candidate_schema"),
        regression_id="min_bending_reo_governs_exact_stop_regression",
        migrated=True,
    )


__all__ = ["MinBendingReoFamily"]
