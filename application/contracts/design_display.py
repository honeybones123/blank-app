"""Application-owned display contracts for the final Design Guide card."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


FINAL_DESIGN_GUIDE_CARD_DATA_ATTRIBUTE_FIELDS = (
    ("data-selected-family-id", "selected_family_id"),
    ("data-selected-family", "selected_family"),
    ("data-selection-reason", "selection_reason"),
    ("data-published-family-id", "published_family_id"),
    ("data-cta-family-id", "cta_family_id"),
    ("data-apply-payload-family-id", "apply_payload_family_id"),
    ("data-candidate-family-id", "candidate_family_id"),
    ("data-card-family-id", "card_family_id"),
    ("data-family-selection-source", "family_selection_source"),
    ("data-family-selection-contract", "family_selection_contract"),
    ("data-family-chooser-contract", "family_chooser_contract"),
    ("data-rejected-families", "rejected_families"),
    ("data-selection-evidence", "selection_evidence"),
    ("data-matched-family-ids", "matched_family_ids"),
    ("data-raw-state-flags", "raw_state_flags"),
    ("data-family-match-passed", "family_match_passed"),
    ("data-family-match-violation-reason", "family_match_violation_reason"),
    ("data-family-route-owner", "family_route_owner"),
    ("data-family-early-dispatch-used", "family_early_dispatch_used"),
    ("data-generic-one-click-solver-skipped", "generic_one_click_solver_skipped"),
    ("data-generic-target-band-search-skipped", "generic_target_band_search_skipped"),
    ("data-generic-optimisation-cleanup-skipped", "generic_optimisation_cleanup_skipped"),
    ("data-generic-publication-fallback-skipped", "generic_publication_fallback_skipped"),
    ("data-direct-target-band-bypassed-by-family-owner", "direct_target_band_bypassed_by_family_owner"),
    ("data-family-ladder-candidate-count", "family_ladder_candidate_count"),
    ("data-render-contract-enabled", "render_contract_enabled"),
    ("data-render-cta-enabled", "render_cta_enabled"),
    ("data-render-action-type", "render_action_type"),
    ("data-render-update-count", "render_update_count"),
    ("data-render-blocking-reason", "render_blocking_reason"),
    ("data-render-cta-payload-id", "render_cta_payload_id"),
    ("data-render-gate-condition", "render_gate_condition"),
    ("data-render-gate-pres-show-apply", "render_gate_pres_show_apply"),
    ("data-render-gate-effective-action", "render_gate_effective_action"),
    ("data-render-gate-terminal-exact", "render_gate_terminal_exact"),
    ("data-render-gate-button-enabled", "render_gate_button_enabled"),
    ("data-render-gate-vm-cta-enabled", "render_gate_vm_cta_enabled"),
    ("data-outcome-state", "outcome_state"),
    ("data-status", "status"),
    ("data-title", "title"),
    ("data-blocker-reason", "blocker_reason"),
    ("data-publication-hash", "publication_hash"),
    ("data-authority-hash", "authority_hash"),
    ("data-final-publication-authority-hash", "final_publication_authority_hash"),
    ("data-final-publication-cta-hash", "final_publication_cta_hash"),
    ("data-final-publication-display-hash", "final_publication_display_hash"),
)


@dataclass(frozen=True)
class FinalDesignGuideFormatSection:
    title: str
    rows: tuple[dict[str, Any], ...] = ()
    visible: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class FinalDesignGuideCardFormat:
    selected_family: str
    outcome_state: str
    tone: str
    tone_source: str
    title: str
    badge: str
    summary: str
    blocker_explanation: str
    governing_label: str
    cta: dict[str, Any] = field(default_factory=dict)
    sections: tuple[FinalDesignGuideFormatSection, ...] = ()
    required_test_ids: tuple[str, ...] = ()
    publication_hash: str | None = None
    display_hash: str | None = None
    cta_hash: str | None = None
    evidence_hash: str | None = None
    contract_hash: str | None = None
    format_hash: str | None = None
    source: str = "FinalDesignGuidePublication"
    renderer_driving: bool = False
    product_driving: bool = False
    apply_driving: bool = False
    session_driving: bool = False
    data_attributes: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            **asdict(self),
            "sections": tuple(section.to_dict() for section in self.sections),
        }


__all__ = [
    "FINAL_DESIGN_GUIDE_CARD_DATA_ATTRIBUTE_FIELDS",
    "FinalDesignGuideCardFormat",
    "FinalDesignGuideFormatSection",
]
