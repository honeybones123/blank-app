"""Primary Apply payload recording coordination for the Inputs Design Guide."""

from __future__ import annotations

from typing import Any

from application.design_result_store import AuthoritativeDesignResultStore


_PRIMARY_APPLY_PAYLOAD_RECORDER_DEPENDENCIES: tuple[str, ...] = (
    "_set_design_guide_primary_payload_binding_audit",
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
    authoritative_result = AuthoritativeDesignResultStore(st.session_state).current()
    payload = (
        dict(authoritative_result.apply_payload or {})
        if authoritative_result is not None
        else {}
    )
    if not payload:
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
    payload.setdefault("source", "authoritative_design_result")
    payload_updates = dict(payload.get("updates") or payload.get("resolved_candidate_updates") or {})
    _set_design_guide_primary_payload_binding_audit(
        visible_primary_candidate_id=payload.get("candidate_id"),
        button_contract_candidate_id=payload.get("source_candidate_id"),
        queued_apply_candidate_id=None,
        applied_candidate_id=None,
        visible_updates=dict(payload_updates),
        button_contract_updates=dict(payload_updates),
        queued_apply_updates={},
        applied_updates={},
        payload_binding_match=True,
        payload_update_match=True,
        stale_apply_payload_blocked=False,
        canonical_primary_payload_exists=True,
        legacy_fallback_used=False,
        render_fingerprint=payload.get("render_fingerprint"),
        state_fingerprint=payload.get("state_fingerprint"),
        winning_button_contract_source="authoritative_design_result",
        winning_update_payload_source="authoritative_design_result.apply_payload",
        winning_action_type_source="authoritative_design_result.apply_payload",
        winning_candidate_source="authoritative_design_result.apply_payload",
        final_publication_cta_hash=payload.get("final_publication_cta_hash"),
    )
    return payload
