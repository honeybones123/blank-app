"""Geometry/detailing governing-family shell."""

from __future__ import annotations

from design_brain.families.base import DiagnosticFamilyStrategy, FamilyStrategyMetadata


class GeometryDetailingFamily(DiagnosticFamilyStrategy):
    metadata = FamilyStrategyMetadata(
        governing_state="GEOMETRY_DETAILING_GOVERNS",
        owner="design_brain.families.geometry_detailing.GeometryDetailingFamily",
        candidate_strategy="adapter_to_existing_geometry_and_detailing_attempts",
        ranking_strategy="disabled_or_family_local_when_geometry_detailing_governs",
        evidence_strategy="geometry_detailing_exact_blocker_evidence",
        publication_rule="geometry_detailing_blocked_or_optimisation_stop",
        cta_rule="disabled_unless_executor_backed_candidate_resolves_geometry_detailing",
        affected_by_shared_helpers=("spacing_checks", "cover_checks", "capacity_checks", "candidate_schema"),
        regression_id="geometry_governs_stop_regression",
    )


__all__ = ["GeometryDetailingFamily"]
