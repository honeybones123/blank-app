"""Primary Design Guide Apply payload assembly."""

from __future__ import annotations

from typing import Any

from design_brain.final_publication import (
    build_final_design_guide_primary_apply_payload_projection,
)


_PRIMARY_APPLY_PAYLOAD_DEPENDENCIES: tuple[str, ...] = (
    "_design_guide_apply_updates_current_state_guard",
    "_design_guide_button_contract_enabled",
    "_design_guide_primary_apply_state_fingerprint",
    "_guidance_item_family",
    "_guidance_item_source_candidate_id",
    "_normalise_design_guide_candidate_id",
    "_resolve_recommendation_updates",
    "stable_fingerprint_for_payload",
)


def bind_primary_apply_payload_dependencies(namespace: dict[str, Any]) -> None:
    globals().update(
        {
            name: namespace[name]
            for name in _PRIMARY_APPLY_PAYLOAD_DEPENDENCIES
            if name in namespace
        }
    )


def _build_design_guide_primary_apply_payload(
    *,
    item: dict,
    rec: dict,
    button_contract: dict,
    state: dict,
) -> dict:
    contract = dict(button_contract or {})
    updates = dict(contract.get("updates") or {})
    action_type = str(contract.get("action_type") or "").strip()
    family = str(contract.get("family") or _guidance_item_family(item) or rec.get("family") or "").strip()
    if not (_design_guide_button_contract_enabled(contract) and action_type == "apply_resolved_candidate" and updates):
        return {}
    visible_updates = dict(_resolve_recommendation_updates(dict(item or {}), state=state) or updates)
    if visible_updates != updates:
        visible_updates = dict(updates)
    current_state_apply_guard = _design_guide_apply_updates_current_state_guard(state, updates)
    if not bool(current_state_apply_guard.get("pass")):
        return {}
    candidate_id = _normalise_design_guide_candidate_id(
        _guidance_item_source_candidate_id(item),
        contract.get("source_candidate_id"),
        contract.get("candidate_id"),
        rec.get("source_candidate_id"),
        rec.get("candidate_id"),
        family=family,
        updates=updates,
    )
    state_fp = _design_guide_primary_apply_state_fingerprint(state)
    render_fingerprint = str(
        stable_fingerprint_for_payload(
            {
                "candidate_id": candidate_id,
                "action_type": action_type,
                "family": family,
                "updates": dict(updates),
                "state_fingerprint": state_fp,
            }
        )
    )
    selected_family_id = (
        contract.get("selected_family_id")
        or contract.get("published_family_id")
        or contract.get("cta_family_id")
        or contract.get("apply_payload_family_id")
        or family
    )
    extra_payload_fields = {
        key: value
        for key, value in {
            "selected_family_id": selected_family_id,
            "published_family_id": contract.get("published_family_id") or selected_family_id,
            "cta_family_id": contract.get("cta_family_id") or selected_family_id,
            "apply_payload_family_id": contract.get("apply_payload_family_id") or selected_family_id,
            "governing_family": contract.get("governing_family") or selected_family_id,
            "payload_owner": contract.get("payload_owner"),
            "payload_action_family": contract.get("payload_action_family"),
            "payload_action_kind": contract.get("payload_action_kind"),
        }.items()
        if value is not None
    }
    projection = build_final_design_guide_primary_apply_payload_projection(
        item=dict(item or {}),
        rec=dict(rec or {}),
        button_contract=contract,
        updates=updates,
        visible_updates=visible_updates,
        current_state_apply_guard=dict(current_state_apply_guard),
        candidate_id=candidate_id,
        family=family,
        selected_family_id=selected_family_id,
        action_type=action_type,
        state_fingerprint=state_fp,
        render_fingerprint=render_fingerprint,
        expected_util=contract.get("expected_util"),
        label=str(
            contract.get("label")
            or item.get("title_main")
            or item.get("title")
            or rec.get("title")
            or rec.get("label")
            or "Apply recommendation"
        ).strip(),
        extra_payload_fields=dict(extra_payload_fields),
    )
    return dict(projection.get("payload") or {})
