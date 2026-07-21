"""Design Guide card data-attribute evidence resolution.

This module resolves verifier-visible product/evidence fields for the Design
Guide card. It does not read Streamlit session state, create candidates, decide
CTA availability, apply payloads, or render HTML.
"""

from __future__ import annotations

from dataclasses import dataclass
import json

from ui.design_guide_models import DesignGuideCardDataAttributeFields

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
class DesignGuideCardResolvedScalars:
    """Resolved scalar inputs for Design Guide card attributes and model metadata."""

    family: str = ""
    selected_family_name_attr: str = ""
    apply_identity: str = ""
    family_route_owner_attr: str = ""
    family_early_dispatch_attr: str = ""
    generic_one_click_skipped_attr: str = ""
    generic_target_band_skipped_attr: str = ""
    generic_cleanup_skipped_attr: str = ""
    generic_publication_fallback_skipped_attr: str = ""
    direct_target_bypassed_attr: str = ""
    family_ladder_candidate_count_attr: str = ""
    contract_enabled_attr: str = ""
    cta_enabled_attr: str = ""
    contract_action_type_attr: str = ""
    contract_update_count_attr: str = ""
    contract_blocking_reason_attr: str = ""
    cta_payload_id_attr: str = ""
    render_gate_condition_attr: str = ""
    render_gate_pres_show_attr: str = ""
    render_gate_effective_action_attr: str = ""
    render_gate_terminal_exact_attr: str = ""
    render_gate_button_enabled_attr: str = ""
    render_gate_vm_cta_attr: str = ""


def assemble_final_design_guide_card_data_attribute_scalars(
    fields: DesignGuideCardDataAttributeFields,
) -> dict:
    """Serialise resolved Design Guide card fields into stable scalar attributes."""
    return {
        "selected_family_id": str(fields.selected_family_id or "").strip(),
        "selected_family": str(fields.selected_family or "").strip(),
        "selection_reason": str(fields.selection_reason or "").strip(),
        "published_family_id": str(fields.published_family_id or "").strip(),
        "cta_family_id": str(fields.cta_family_id or "").strip(),
        "apply_payload_family_id": str(fields.apply_payload_family_id or "").strip(),
        "candidate_family_id": str(fields.candidate_family_id or "").strip(),
        "card_family_id": str(fields.card_family_id or "").strip(),
        "family_selection_source": str(fields.family_selection_source or "").strip(),
        "family_selection_contract": str(fields.family_selection_contract or "").strip(),
        "family_chooser_contract": str(fields.family_chooser_contract or "").strip(),
        "rejected_families": json.dumps(fields.rejected_families or {}, sort_keys=True),
        "selection_evidence": json.dumps(fields.selection_evidence or {}, sort_keys=True),
        "matched_family_ids": json.dumps(fields.matched_family_ids or [], sort_keys=True),
        "raw_state_flags": json.dumps(fields.raw_state_flags or {}, sort_keys=True),
        "family_match_passed": str(fields.family_match_passed).strip(),
        "family_match_violation_reason": str(fields.family_match_violation_reason or "").strip(),
        "family_route_owner": str(fields.family_route_owner or "").strip(),
        "family_early_dispatch_used": str(fields.family_early_dispatch_used or "").strip(),
        "generic_one_click_solver_skipped": str(fields.generic_one_click_solver_skipped or "").strip(),
        "generic_target_band_search_skipped": str(fields.generic_target_band_search_skipped or "").strip(),
        "generic_optimisation_cleanup_skipped": str(fields.generic_optimisation_cleanup_skipped or "").strip(),
        "generic_publication_fallback_skipped": str(fields.generic_publication_fallback_skipped or "").strip(),
        "direct_target_band_bypassed_by_family_owner": str(
            fields.direct_target_band_bypassed_by_family_owner or ""
        ).strip(),
        "family_ladder_candidate_count": str(fields.family_ladder_candidate_count or "").strip(),
        "render_contract_enabled": str(fields.render_contract_enabled or "").strip(),
        "render_cta_enabled": str(fields.render_cta_enabled or "").strip(),
        "render_action_type": str(fields.render_action_type or "").strip(),
        "render_update_count": str(fields.render_update_count or "").strip(),
        "render_blocking_reason": str(fields.render_blocking_reason or "").strip(),
        "render_cta_payload_id": str(fields.render_cta_payload_id or "").strip(),
        "render_gate_condition": str(fields.render_gate_condition or "").strip(),
        "render_gate_pres_show_apply": str(fields.render_gate_pres_show_apply or "").strip(),
        "render_gate_effective_action": str(fields.render_gate_effective_action or "").strip(),
        "render_gate_terminal_exact": str(fields.render_gate_terminal_exact or "").strip(),
        "render_gate_button_enabled": str(fields.render_gate_button_enabled or "").strip(),
        "render_gate_vm_cta_enabled": str(fields.render_gate_vm_cta_enabled or "").strip(),
        "publication_hash": str(fields.publication_hash or "").strip(),
        "final_publication_authority_hash": str(fields.final_publication_authority_hash or "").strip(),
        "final_publication_cta_hash": str(fields.final_publication_cta_hash or "").strip(),
        "final_publication_display_hash": str(fields.final_publication_display_hash or "").strip(),
    }


def resolve_design_guide_card_resolved_scalars(
    vm_d: dict,
    details: dict,
    cta: dict,
    contract: dict,
    render_gate_probe: dict,
    candidate_evidence: dict,
    *,
    contract_enabled: bool,
) -> DesignGuideCardResolvedScalars:
    """Resolve verifier-sensitive Design Guide card scalar inputs."""
    speed_diag_sources = [vm_d, details, candidate_evidence]

    def _speed_diag_bool_attr(key: str) -> str:
        for source in speed_diag_sources:
            if isinstance(source, dict) and key in source:
                return str(bool(source.get(key)))
        return ""

    def _speed_diag_value_attr(key: str) -> str:
        for source in speed_diag_sources:
            if isinstance(source, dict) and source.get(key) not in (None, "", [], {}):
                return str(source.get(key))
        return ""

    family_route_owner_attr = str(vm_d.get("family_route_owner") or details.get("family_route_owner") or "").strip()
    family_early_dispatch_attr = (
        _speed_diag_bool_attr("family_early_dispatch_used")
        or _speed_diag_bool_attr("early_family_dispatch_used")
    )
    generic_one_click_skipped_attr = _speed_diag_bool_attr("generic_one_click_solver_skipped")
    generic_target_band_skipped_attr = _speed_diag_bool_attr("generic_target_band_search_skipped")
    generic_cleanup_skipped_attr = _speed_diag_bool_attr("generic_optimisation_cleanup_skipped")
    generic_publication_fallback_skipped_attr = _speed_diag_bool_attr("generic_publication_fallback_skipped")
    direct_target_bypassed_attr = _speed_diag_bool_attr("direct_target_band_bypassed_by_family_owner")
    family_ladder_candidate_count_attr = (
        _speed_diag_value_attr("combined_fail_contract_ladder_candidate_count")
        or _speed_diag_value_attr("bending_fail_contract_ladder_candidate_count")
        or _speed_diag_value_attr("shear_fail_contract_ladder_candidate_count")
    )
    if (
        not family_early_dispatch_attr
        and "combined_bending_shear_fail" in family_route_owner_attr.lower()
        and generic_one_click_skipped_attr == "True"
        and generic_target_band_skipped_attr == "True"
    ):
        family_early_dispatch_attr = "True"

    family = str(
        vm_d.get("selected_family_id")
        or vm_d.get("selected_family")
        or details.get("selected_family_id")
        or ""
    ).strip()
    apply_identity = str(vm_d.get("apply_payload_family_id") or details.get("apply_payload_family_id") or "").strip()
    selected_family_name_attr = str(vm_d.get("selected_family") or details.get("selected_family") or family).strip()

    return DesignGuideCardResolvedScalars(
        family=family,
        selected_family_name_attr=selected_family_name_attr,
        apply_identity=apply_identity,
        family_route_owner_attr=family_route_owner_attr,
        family_early_dispatch_attr=family_early_dispatch_attr,
        generic_one_click_skipped_attr=generic_one_click_skipped_attr,
        generic_target_band_skipped_attr=generic_target_band_skipped_attr,
        generic_cleanup_skipped_attr=generic_cleanup_skipped_attr,
        generic_publication_fallback_skipped_attr=generic_publication_fallback_skipped_attr,
        direct_target_bypassed_attr=direct_target_bypassed_attr,
        family_ladder_candidate_count_attr=family_ladder_candidate_count_attr,
        contract_enabled_attr=str(bool(contract_enabled)),
        cta_enabled_attr=str(bool(cta.get("enabled"))),
        contract_action_type_attr=str(contract.get("action_type") or "").strip(),
        contract_update_count_attr=str(len(dict(contract.get("updates") or {}))),
        contract_blocking_reason_attr=str(contract.get("blocking_reason") or "").strip(),
        cta_payload_id_attr=str(cta.get("payload_id") or "").strip(),
        render_gate_condition_attr=str(bool(render_gate_probe.get("render_button_condition"))),
        render_gate_pres_show_attr=str(bool(render_gate_probe.get("pres_show_apply"))),
        render_gate_effective_action_attr=str(render_gate_probe.get("effective_render_action_type") or "").strip(),
        render_gate_terminal_exact_attr=str(bool(render_gate_probe.get("terminal_exact_accepted"))),
        render_gate_button_enabled_attr=str(bool(render_gate_probe.get("button_contract_enabled"))),
        render_gate_vm_cta_attr=str(bool(render_gate_probe.get("final_view_cta_enabled"))),
    )


def _resolve_design_guide_card_data_attribute_fields(
    vm_d: dict,
    details: dict,
    *,
    scalars: DesignGuideCardResolvedScalars,
) -> DesignGuideCardDataAttributeFields:
    """Collect product, CTA, and verifier evidence fields before scalar rendering."""
    verifier_payload = {}
    for source in (vm_d, details):
        if isinstance(source, dict) and isinstance(source.get("final_publication_verifier_payload"), dict):
            verifier_payload = dict(source.get("final_publication_verifier_payload") or {})
            break

    def _first_scalar(*keys: str) -> str:
        for source in (vm_d, details, verifier_payload):
            if not isinstance(source, dict):
                continue
            for key in keys:
                value = source.get(key)
                if value not in (None, "", [], {}):
                    return str(value).strip()
        return ""

    def _first_payload_scalar(*keys: str) -> str:
        return _first_scalar(*keys)

    def _first_payload_value(*keys: str, default=None):
        for source in (vm_d, details, verifier_payload):
            if not isinstance(source, dict):
                continue
            for key in keys:
                value = source.get(key)
                if value not in (None, "", [], {}):
                    return value
        return default

    return DesignGuideCardDataAttributeFields(
        selected_family_id=scalars.family or _first_payload_scalar("selected_family_id", "selected_family"),
        selected_family=scalars.selected_family_name_attr
        or _first_payload_scalar("selected_family", "selected_family_id"),
        selection_reason=_first_payload_scalar("selection_reason", "selected_family_reason"),
        published_family_id=_first_payload_scalar("published_family_id"),
        cta_family_id=_first_payload_scalar("cta_family_id"),
        apply_payload_family_id=scalars.apply_identity or _first_payload_scalar("apply_payload_family_id"),
        candidate_family_id=_first_payload_scalar("candidate_family_id"),
        card_family_id=_first_payload_scalar("card_family_id"),
        family_selection_source=_first_payload_scalar("family_selection_source"),
        family_selection_contract=_first_payload_scalar("family_selection_contract"),
        family_chooser_contract=_first_payload_scalar("family_chooser_contract"),
        rejected_families=_first_payload_value("rejected_families", default={}),
        selection_evidence=_first_payload_value("selection_evidence", default={}),
        matched_family_ids=_first_payload_value("matched_family_ids", default=[]),
        raw_state_flags=_first_payload_value("raw_state_flags", default={}),
        family_match_passed=(
            vm_d.get("family_match_passed")
            if vm_d.get("family_match_passed") is not None
            else details.get("family_match_passed")
            if details.get("family_match_passed") is not None
            else verifier_payload.get("family_match_passed")
        ),
        family_match_violation_reason=(
            _first_payload_scalar("family_match_violation_reason")
        ),
        family_route_owner=scalars.family_route_owner_attr or _first_payload_scalar("family_route_owner"),
        family_early_dispatch_used=scalars.family_early_dispatch_attr,
        generic_one_click_solver_skipped=scalars.generic_one_click_skipped_attr,
        generic_target_band_search_skipped=scalars.generic_target_band_skipped_attr,
        generic_optimisation_cleanup_skipped=scalars.generic_cleanup_skipped_attr,
        generic_publication_fallback_skipped=scalars.generic_publication_fallback_skipped_attr,
        direct_target_band_bypassed_by_family_owner=scalars.direct_target_bypassed_attr,
        family_ladder_candidate_count=scalars.family_ladder_candidate_count_attr,
        render_contract_enabled=scalars.contract_enabled_attr,
        render_cta_enabled=scalars.cta_enabled_attr,
        render_action_type=scalars.contract_action_type_attr,
        render_update_count=scalars.contract_update_count_attr,
        render_blocking_reason=scalars.contract_blocking_reason_attr,
        render_cta_payload_id=scalars.cta_payload_id_attr,
        render_gate_condition=scalars.render_gate_condition_attr,
        render_gate_pres_show_apply=scalars.render_gate_pres_show_attr,
        render_gate_effective_action=scalars.render_gate_effective_action_attr,
        render_gate_terminal_exact=scalars.render_gate_terminal_exact_attr,
        render_gate_button_enabled=scalars.render_gate_button_enabled_attr,
        render_gate_vm_cta_enabled=scalars.render_gate_vm_cta_attr,
        publication_hash=_first_scalar("publication_hash", "final_publication_publication_hash"),
        final_publication_authority_hash=_first_scalar("final_publication_authority_hash"),
        final_publication_cta_hash=_first_scalar(
            "final_publication_cta_hash",
            "cta_authority_hash",
            "cta_hash",
        ),
        final_publication_display_hash=_first_scalar(
            "final_publication_display_hash",
            "display_authority_hash",
            "display_hash",
        ),
    )
