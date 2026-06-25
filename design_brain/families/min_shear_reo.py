"""Minimum shear reinforcement governing stop shell."""

from __future__ import annotations

from design_brain.families.base import DiagnosticFamilyStrategy, FamilyStrategyMetadata


class MinShearReoFamily(DiagnosticFamilyStrategy):
    metadata = FamilyStrategyMetadata(
        governing_state="MIN_SHEAR_REO_GOVERNS",
        owner="design_brain.families.min_shear_reo.MinShearReoFamily",
        candidate_strategy="adapter_to_existing_shear_cleanup_attempts",
        ranking_strategy="disabled_when_minimum_shear_reinforcement_governs",
        evidence_strategy="minimum_shear_reinforcement_exact_stop_evidence",
        publication_rule="shear_minimum_reinforcement_optimisation_stop",
        cta_rule="disabled_when_minimum_shear_reinforcement_governs",
        affected_by_shared_helpers=("spacing_checks", "cover_checks", "candidate_schema"),
        regression_id="min_shear_reo_governs_exact_stop_regression",
    )


__all__ = ["MinShearReoFamily"]
