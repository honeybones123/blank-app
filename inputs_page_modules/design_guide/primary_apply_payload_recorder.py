"""Primary Apply payload recording coordination for the Inputs Design Guide."""

from __future__ import annotations

from typing import Any


_PRIMARY_APPLY_PAYLOAD_RECORDER_DEPENDENCIES: tuple[str, ...] = (
    "_build_design_guide_button_contract_source_records",
    "_build_design_guide_primary_apply_payload",
    "_resolve_design_guide_button_contract_source_precedence",
    "_set_design_guide_primary_payload_binding_audit",
    "_stamp_final_publication_cta_authority",
    "cta_button_source_precedence_order",
    "cta_candidate_source_keys",
    "cta_payload_source_precedence_order",
    "cta_source_payload_labels",
    "DESIGN_GUIDE_DEBUG_BUNDLE_KEY",
    "DESIGN_GUIDE_PRIMARY_APPLY_PAYLOAD_KEY",
    "st",
)


def bind_primary_apply_payload_recorder_dependencies(namespace: dict[str, Any]) -> None:
    globals().update(
        {
            name: namespace[name]
            for name in _PRIMARY_APPLY_PAYLOAD_RECORDER_DEPENDENCIES
            if name in namespace
        }
    )


def _record_rendered_design_guide_primary_apply_payload(
    *,
    item: dict,
    rec: dict,
    button_contract: dict,
    state: dict,
) -> dict:
    payload = _build_design_guide_primary_apply_payload(
        item=dict(item or {}),
        rec=dict(rec or {}),
        button_contract=dict(button_contract or {}),
        state=dict(state or {}),
    )
    if not payload:
        st.session_state.pop(DESIGN_GUIDE_PRIMARY_APPLY_PAYLOAD_KEY, None)
        _set_design_guide_primary_payload_binding_audit(
            visible_primary_candidate_id=None,
            button_contract_candidate_id=(
                (button_contract or {}).get("source_candidate_id")
                or (button_contract or {}).get("candidate_id")
            ),
            queued_apply_candidate_id=None,
            applied_candidate_id=None,
            visible_updates={},
            button_contract_updates=dict((button_contract or {}).get("updates") or {}),
            queued_apply_updates={},
            applied_updates={},
            payload_binding_match=False,
            payload_update_match=False,
            stale_apply_payload_blocked=False,
            canonical_primary_payload_exists=False,
            legacy_fallback_used=False,
        )
        return {}
    final_item = {
        **dict(item or {}),
        "button_contract": dict(button_contract or {}),
        "action_payload": dict(payload),
        "selected_action_updates": dict(payload.get("updates") or {}),
        "updates": dict(payload.get("updates") or {}),
        "candidate_id": payload.get("candidate_id"),
        "source_candidate_id": payload.get("source_candidate_id"),
        "action_type": payload.get("action_type"),
        "family": payload.get("family"),
    }
    source_records = _build_design_guide_button_contract_source_records(
        displayed_primary_item=final_item,
        primary_item=final_item,
        guidance_debug=dict(st.session_state.get(DESIGN_GUIDE_DEBUG_BUNDLE_KEY) or {}),
        pending_recommendation=dict(rec or {}),
        apply_payload_session_keys=dict(payload),
        button_contract_session_keys=dict(button_contract or {}),
        source_candidates={},
        publication_recovery_sources={},
    )
    source_resolution = _resolve_design_guide_button_contract_source_precedence(
        final_published_item=final_item,
        source_candidates=dict(source_records.source_candidates),
        final_cta_action_payload=dict(payload),
        source_records=source_records,
        button_contract_source_precedence_order=cta_button_source_precedence_order(),
        payload_source_precedence_order=cta_payload_source_precedence_order(),
        candidate_source_keys=cta_candidate_source_keys(),
        source_payload_labels=cta_source_payload_labels(),
    )
    source_precedence = {
        "winning_button_contract_source": source_resolution.winning_button_contract_source,
        "winning_update_payload_source": source_resolution.winning_update_payload_source,
        "winning_action_type_source": source_resolution.winning_action_type_source,
        "winning_candidate_source": source_resolution.winning_candidate_source,
    }
    stamped_contract = _stamp_final_publication_cta_authority(
        contract=dict(button_contract or {}),
        item=final_item,
        debug=dict(st.session_state.get(DESIGN_GUIDE_DEBUG_BUNDLE_KEY) or {}),
        action_payload=dict(payload),
        source_precedence=source_precedence,
    )
    payload["winning_button_contract_source"] = source_resolution.winning_button_contract_source
    payload["winning_update_payload_source"] = source_resolution.winning_update_payload_source
    payload["winning_action_type_source"] = source_resolution.winning_action_type_source
    payload["winning_candidate_source"] = source_resolution.winning_candidate_source
    payload["final_cta_action_payload_summary"] = dict(source_resolution.final_cta_action_payload_summary)
    payload["final_publication_cta_hash"] = stamped_contract.get("final_publication_cta_hash")
    st.session_state[DESIGN_GUIDE_PRIMARY_APPLY_PAYLOAD_KEY] = dict(payload)
    _set_design_guide_primary_payload_binding_audit(
        visible_primary_candidate_id=payload.get("candidate_id"),
        button_contract_candidate_id=payload.get("source_candidate_id"),
        queued_apply_candidate_id=None,
        applied_candidate_id=None,
        visible_updates=dict(payload.get("visible_updates") or payload.get("updates") or {}),
        button_contract_updates=dict(payload.get("button_contract_updates") or payload.get("updates") or {}),
        queued_apply_updates={},
        applied_updates={},
        payload_binding_match=True,
        payload_update_match=True,
        stale_apply_payload_blocked=False,
        canonical_primary_payload_exists=True,
        legacy_fallback_used=False,
        render_fingerprint=payload.get("render_fingerprint"),
        state_fingerprint=payload.get("state_fingerprint"),
        winning_button_contract_source=source_resolution.winning_button_contract_source,
        winning_update_payload_source=source_resolution.winning_update_payload_source,
        winning_action_type_source=source_resolution.winning_action_type_source,
        winning_candidate_source=source_resolution.winning_candidate_source,
        final_publication_cta_hash=stamped_contract.get("final_publication_cta_hash"),
    )
    return payload
