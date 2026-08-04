"""Target-band reached governing-family shell."""

from __future__ import annotations

from design_brain.families.base import DiagnosticFamilyStrategy, FamilyStrategyMetadata


class TargetBandFamily(DiagnosticFamilyStrategy):
    metadata = FamilyStrategyMetadata(
        governing_state="TARGET_BAND_REACHED",
        owner="design_brain.families.target_band.TargetBandFamily",
        candidate_strategy="no_candidate_when_current_state_inside_target_band",
        ranking_strategy="no_ranking_when_no_action_required",
        evidence_strategy="target_band_current_state_evidence",
        publication_rule="target_reached_terminal_only_with_no_pending_cleanup",
        cta_rule="disabled_when_target_band_reached",
        affected_by_shared_helpers=("utilisation_calculations", "target_band_scoring", "candidate_schema"),
        regression_id="target_band_reached_regression",
        migrated=True,
    )


__all__ = ["TargetBandFamily"]
