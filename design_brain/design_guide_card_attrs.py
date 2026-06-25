"""Design Guide card data-attribute evidence resolution.

This module resolves verifier-visible product/evidence fields for the Design
Guide card. It does not read Streamlit session state, create candidates, decide
CTA availability, apply payloads, or render HTML.
"""

from __future__ import annotations

from dataclasses import dataclass

from ui.design_guide_models import DesignGuideCardDataAttributeFields


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
    return DesignGuideCardDataAttributeFields(
        selected_family_id=scalars.family,
        selected_family=scalars.selected_family_name_attr,
        selection_reason=vm_d.get("selection_reason") or details.get("selection_reason") or "",
        published_family_id=vm_d.get("published_family_id") or details.get("published_family_id") or "",
        cta_family_id=vm_d.get("cta_family_id") or details.get("cta_family_id") or "",
        apply_payload_family_id=scalars.apply_identity,
        candidate_family_id=vm_d.get("candidate_family_id") or details.get("candidate_family_id") or "",
        card_family_id=vm_d.get("card_family_id") or details.get("card_family_id") or "",
        family_selection_source=vm_d.get("family_selection_source") or details.get("family_selection_source") or "",
        family_selection_contract=vm_d.get("family_selection_contract") or details.get("family_selection_contract") or "",
        family_chooser_contract=vm_d.get("family_chooser_contract") or details.get("family_chooser_contract") or "",
        rejected_families=vm_d.get("rejected_families") or details.get("rejected_families") or {},
        selection_evidence=vm_d.get("selection_evidence") or details.get("selection_evidence") or {},
        matched_family_ids=vm_d.get("matched_family_ids") or details.get("matched_family_ids") or [],
        raw_state_flags=vm_d.get("raw_state_flags") or details.get("raw_state_flags") or {},
        family_match_passed=(
            vm_d.get("family_match_passed")
            if vm_d.get("family_match_passed") is not None
            else details.get("family_match_passed")
        ),
        family_match_violation_reason=(
            vm_d.get("family_match_violation_reason")
            or details.get("family_match_violation_reason")
            or ""
        ),
        family_route_owner=scalars.family_route_owner_attr,
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
    )
