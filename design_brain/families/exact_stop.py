"""Exact-stop proven governing-family shell."""

from __future__ import annotations

from design_brain.families.base import DiagnosticFamilyStrategy, FamilyStrategyMetadata


class ExactStopFamily(DiagnosticFamilyStrategy):
    metadata = FamilyStrategyMetadata(
        governing_state="EXACT_STOP_PROVEN",
        owner="design_brain.families.exact_stop.ExactStopFamily",
        candidate_strategy="no_candidate_when_exhaustive_exact_stop_proven",
        ranking_strategy="disabled_when_exact_stop_proven",
        evidence_strategy="exhaustive_exact_stop_evidence_by_family",
        publication_rule="optimisation_stop_only_with_named_family_exact_proof",
        cta_rule="disabled_when_exact_stop_proven",
        affected_by_shared_helpers=("candidate_schema", "evidence_table_formatting", "target_band_scoring"),
        regression_id="exact_stop_proven_regression",
    )


__all__ = ["ExactStopFamily"]
