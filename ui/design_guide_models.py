"""Resolved Design Guide display model containers."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Mapping, Sequence


@dataclass(frozen=True)
class DesignGuideCardDataAttributeFields:
    """Already-resolved fields used to build Design Guide card data attributes."""

    selected_family_id: str = ""
    selected_family: str = ""
    selection_reason: str = ""
    published_family_id: str = ""
    cta_family_id: str = ""
    apply_payload_family_id: str = ""
    candidate_family_id: str = ""
    card_family_id: str = ""
    family_selection_source: str = ""
    family_selection_contract: str = ""
    family_chooser_contract: str = ""
    rejected_families: Mapping[str, object] = field(default_factory=dict)
    selection_evidence: Mapping[str, object] = field(default_factory=dict)
    matched_family_ids: Sequence[object] = field(default_factory=list)
    raw_state_flags: Mapping[str, object] = field(default_factory=dict)
    family_match_passed: object = None
    family_match_violation_reason: str = ""
    family_route_owner: str = ""
    family_early_dispatch_used: str = ""
    generic_one_click_solver_skipped: str = ""
    generic_target_band_search_skipped: str = ""
    generic_optimisation_cleanup_skipped: str = ""
    generic_publication_fallback_skipped: str = ""
    direct_target_band_bypassed_by_family_owner: str = ""
    family_ladder_candidate_count: str = ""
    render_contract_enabled: str = ""
    render_cta_enabled: str = ""
    render_action_type: str = ""
    render_update_count: str = ""
    render_blocking_reason: str = ""
    render_cta_payload_id: str = ""
    render_gate_condition: str = ""
    render_gate_pres_show_apply: str = ""
    render_gate_effective_action: str = ""
    render_gate_terminal_exact: str = ""
    render_gate_button_enabled: str = ""
    render_gate_vm_cta_enabled: str = ""
    publication_hash: str = ""
    final_publication_authority_hash: str = ""
    final_publication_cta_hash: str = ""
    final_publication_display_hash: str = ""


@dataclass(frozen=True)
class DesignGuideCardDecisionDisplayFields:
    """Final Design Guide card decision/display fields before render-model assembly."""

    final_status: str = ""
    final_title: str = ""
    final_pill_label: str = ""
    final_reasons: list[dict[str, Any]] = field(default_factory=list)
    final_why_body: str = ""
    final_main_text: str = ""
    final_card_tone: str = ""
    final_card_class: str = ""
    terminal_status: dict[str, Any] = field(default_factory=dict)
    cta_label: str = ""
    cta_enabled: bool = False
    cta_reason: str = ""
    button_contract_attributes: dict[str, Any] = field(default_factory=dict)
    blocker_evidence_display_fields: dict[str, Any] = field(default_factory=dict)
    action_state: dict[str, Any] = field(default_factory=dict)
    blocked_display_state: dict[str, Any] = field(default_factory=dict)
    repair_identity: dict[str, Any] = field(default_factory=dict)
    apply_identity: str = ""
    blocker_reason: str = ""


@dataclass(frozen=True)
class DesignGuideCardRenderModel:
    """Container for already-resolved Design Guide card display data."""

    family: str = ""
    family_label: str = ""
    title: str = ""
    status: str = ""
    pill: str = ""
    governing_label: str = ""
    terminal_status: dict[str, Any] = field(default_factory=dict)
    main_text: str = ""
    why_body: str = ""
    final_reasons: list[dict[str, Any]] = field(default_factory=list)
    reason_display_rows: list[dict[str, Any]] = field(default_factory=list)
    cta_label: str = ""
    cta_enabled: bool = False
    cta_reason: str = ""
    button_contract_attributes: dict[str, Any] = field(default_factory=dict)
    blocker_evidence_display_fields: dict[str, Any] = field(default_factory=dict)
    card_tone: str = ""
    card_class: str = ""
    current_rows: list[dict[str, Any]] = field(default_factory=list)
    preview_rows: dict[str, Any] = field(default_factory=dict)
    preview_display_rows: list[dict[str, Any]] = field(default_factory=list)
    details_text: str = ""
    details_payload: dict[str, Any] = field(default_factory=dict)
    details_enabled: bool = False
    section_title: str = ""
    ladder_stop_html: str = ""
    repair_identity: dict[str, Any] = field(default_factory=dict)
    apply_identity: str = ""
    blocker_reason: str = ""
    verifier_fields: dict[str, Any] = field(default_factory=dict)
    data_attributes: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
