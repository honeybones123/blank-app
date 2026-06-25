"""Pure Design Guide output-formatting helpers.

This module packages already-resolved display fields. It does not choose
families, decide CTA availability, mutate page/session state, or render HTML.
"""

from __future__ import annotations

from design_brain.design_guide_card_attrs import DesignGuideCardResolvedScalars
from ui.design_guide_models import (
    DesignGuideCardDataAttributeFields,
    DesignGuideCardDecisionDisplayFields,
    DesignGuideCardRenderModel,
)


def build_design_guide_card_decision_display_fields(
    *,
    status: str,
    title: str,
    pill: str,
    reasons: list[dict],
    reason_texts: list[str],
    summary_line: str,
    card_class: str,
    vm_d: dict,
    cta: dict,
    contract: dict,
    card_scalars: DesignGuideCardResolvedScalars,
    disabled_action_with_blocker: bool,
    section_title_override: str,
    exact_rows: dict,
    blocker_rows: dict,
    blocker_reason: str,
) -> DesignGuideCardDecisionDisplayFields:
    """Package final card decision/display fields without changing decisions."""
    return DesignGuideCardDecisionDisplayFields(
        final_status=status,
        final_title=title,
        final_pill_label=pill,
        final_reasons=[dict(row) for row in list(reasons or []) if isinstance(row, dict)],
        final_why_body=reason_texts[0] if reason_texts else "",
        final_main_text=summary_line,
        final_card_tone=str(vm_d.get("tone") or status).strip(),
        final_card_class=str(card_class or "").strip(),
        terminal_status={
            "status": status,
            "pill": pill,
            "terminal_exact": card_scalars.render_gate_terminal_exact_attr == "True",
        },
        cta_label=str(cta.get("label") or "").strip(),
        cta_enabled=bool(cta.get("enabled")),
        cta_reason=str(cta.get("reason") or cta.get("blocking_reason") or contract.get("blocking_reason") or "").strip(),
        button_contract_attributes={
            "enabled": card_scalars.contract_enabled_attr == "True",
            "action_type": card_scalars.contract_action_type_attr,
            "update_count": card_scalars.contract_update_count_attr,
            "blocking_reason": card_scalars.contract_blocking_reason_attr,
        },
        blocker_evidence_display_fields={
            "exact_rows": exact_rows,
            "blocker_rows": blocker_rows,
            "disabled_action_with_blocker": disabled_action_with_blocker,
            "section_title_override": section_title_override,
        },
        action_state={
            "status": status,
            "cta_enabled": bool(cta.get("enabled")),
            "button_contract_enabled": card_scalars.contract_enabled_attr == "True",
            "disabled_action_with_blocker": disabled_action_with_blocker,
        },
        blocked_display_state={
            "is_blocked": status in {"blocked", "error"},
            "section_title_override": section_title_override,
            "blocker_reason": blocker_reason,
        },
        repair_identity={
            "payload_id": card_scalars.cta_payload_id_attr,
            "family": card_scalars.family,
            "is_repair": "repair" in card_scalars.cta_payload_id_attr.lower(),
            "is_cleanup": "cleanup" in card_scalars.cta_payload_id_attr.lower(),
        },
        apply_identity=card_scalars.apply_identity,
        blocker_reason=blocker_reason,
    )


def build_design_guide_card_render_model_fields(
    *,
    card_scalars: DesignGuideCardResolvedScalars,
    decision_display: DesignGuideCardDecisionDisplayFields,
    governing: str,
    reason_display_rows: list[dict],
    preview_display_rows: list[dict],
    details_text: str,
    details: dict,
    details_enabled: bool,
    section_title: str,
    ladder_stop_html: str,
    data_attributes: DesignGuideCardDataAttributeFields,
    vm_d: dict,
) -> DesignGuideCardRenderModel:
    """Package the final Design Guide render model from resolved display fields."""
    return DesignGuideCardRenderModel(
        family=card_scalars.family,
        family_label=card_scalars.selected_family_name_attr,
        title=decision_display.final_title,
        status=decision_display.final_status,
        pill=decision_display.final_pill_label,
        governing_label=governing,
        terminal_status=decision_display.terminal_status,
        main_text=decision_display.final_main_text,
        why_body=decision_display.final_why_body,
        final_reasons=decision_display.final_reasons,
        reason_display_rows=reason_display_rows,
        cta_label=decision_display.cta_label,
        cta_enabled=decision_display.cta_enabled,
        cta_reason=decision_display.cta_reason,
        button_contract_attributes=decision_display.button_contract_attributes,
        blocker_evidence_display_fields=decision_display.blocker_evidence_display_fields,
        card_tone=decision_display.final_card_tone,
        card_class=decision_display.final_card_class,
        current_rows=[dict(row) for row in list(vm_d.get("current") or []) if isinstance(row, dict)],
        preview_rows=dict(vm_d.get("preview") or {}),
        preview_display_rows=preview_display_rows,
        details_text=details_text,
        details_payload=details,
        details_enabled=bool(details_enabled),
        section_title=section_title,
        ladder_stop_html=ladder_stop_html,
        repair_identity=decision_display.repair_identity,
        apply_identity=decision_display.apply_identity,
        blocker_reason=decision_display.blocker_reason,
        verifier_fields={
            "selected_family_id": card_scalars.family,
            "selected_family": vm_d.get("selected_family"),
            "published_family_id": vm_d.get("published_family_id") or details.get("published_family_id"),
            "cta_family_id": vm_d.get("cta_family_id") or details.get("cta_family_id"),
            "apply_payload_family_id": card_scalars.apply_identity,
            "candidate_family_id": vm_d.get("candidate_family_id") or details.get("candidate_family_id"),
            "card_family_id": vm_d.get("card_family_id") or details.get("card_family_id"),
            "family_route_owner": vm_d.get("family_route_owner") or details.get("family_route_owner"),
            "family_match_passed": vm_d.get("family_match_passed") or details.get("family_match_passed"),
            "family_match_violation_reason": (
                vm_d.get("family_match_violation_reason")
                or details.get("family_match_violation_reason")
            ),
            "render_cta_payload_id": card_scalars.cta_payload_id_attr,
        },
        data_attributes=data_attributes,
    )
