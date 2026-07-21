"""Primary Design Guide CTA queue coordination for the Inputs page."""

from __future__ import annotations

from typing import Any


_PRIMARY_BUTTON_QUEUE_DEPENDENCIES: tuple[str, ...] = (
    "AUTO_DESIGN_AUTO_INVOKE_KEY",
    "AUTO_DESIGN_REQUEST_SOURCE_KEY",
    "AUTO_DESIGN_REQUEST_TS_KEY",
    "DESIGN_GUIDE_PRIMARY_APPLY_PAYLOAD_KEY",
    "_begin_design_guide_apply_trace",
    "_consume_design_guide_component_cta_value",
    "_design_guide_primary_apply_state_fingerprint",
    "_emit_design_guide_apply_trace_run_end",
    "_normalise_design_guide_candidate_id",
    "_recommendation_blocked_reason",
    "_set_design_guide_live_breadcrumb",
    "_set_design_guide_primary_payload_binding_audit",
    "_shared_state_snapshot",
    "apply_recommendation_result",
    "st",
    "sys",
    "time",
)


def bind_primary_button_queue_dependencies(namespace: dict[str, Any]) -> None:
    globals().update(
        {
            name: namespace[name]
            for name in _PRIMARY_BUTTON_QUEUE_DEPENDENCIES
            if name in namespace
        }
    )


def _queue_primary_design_guide_button_action(
    rec: dict,
    primary_route_target: str,
    apply_label: str,
    button_contract: dict | None = None,
) -> None:
    """Queue the visible primary Design Guide CTA before the next render paints stale guidance."""
    rec_dict = dict(rec or {})
    route_target = str(primary_route_target or "").strip() or "handle_apply_buttons"
    contract = dict(button_contract or {})
    canonical = dict(st.session_state.get(DESIGN_GUIDE_PRIMARY_APPLY_PAYLOAD_KEY) or {})
    if canonical:
        current_fp = _design_guide_primary_apply_state_fingerprint(_shared_state_snapshot())
        expected_fp = str(canonical.get("state_fingerprint") or "")
        canonical = _consume_design_guide_component_cta_value(
            canonical_payload=canonical,
            expected_fingerprint=expected_fp,
            current_fingerprint=current_fp,
            apply_label=apply_label,
        )
        if canonical is None:
            return
        canonical_updates = dict(canonical.get("updates") or {})
        canonical_candidate_id = _normalise_design_guide_candidate_id(
            canonical.get("candidate_id"),
            canonical.get("source_candidate_id"),
            contract.get("source_candidate_id"),
            contract.get("candidate_id"),
            family=str(canonical.get("family") or contract.get("family") or ""),
            updates=canonical_updates,
        )
        canonical_label = str(canonical.get("label") or apply_label or "Apply recommendation").strip()
        resolved_candidate = {
            "action_type": "apply_resolved_candidate",
            "family": canonical.get("family"),
            "updates": dict(canonical_updates),
            "candidate_id": canonical_candidate_id,
            "source_candidate_id": canonical_candidate_id,
            "label": canonical_label,
        }
        action_payload = {
            "resolved_candidate_updates": dict(canonical_updates),
            "resolved_candidate_action_type": "apply_resolved_candidate",
            "resolved_candidate_family_tag": canonical.get("family"),
            "updates": dict(canonical_updates),
            "source_candidate_id": canonical_candidate_id,
            "candidate_id": canonical_candidate_id,
            "resolved_candidate": dict(resolved_candidate),
            "resolved_candidate_label": canonical_label,
            "resolved_candidate_post_util": canonical.get("expected_util"),
            "primary_apply_render_fingerprint": canonical.get("render_fingerprint"),
            "primary_apply_state_fingerprint": canonical.get("state_fingerprint"),
            "primary_apply_payload_source": canonical.get("source"),
        }
        rec_dict = {
            **rec_dict,
            "_source": "design_guide_primary_apply_payload",
            "title": canonical_label,
            "label": canonical_label,
            "action_type": "apply_resolved_candidate",
            "family": canonical.get("family"),
            "updates": dict(canonical_updates),
            "resolved_candidate_updates": dict(canonical_updates),
            "source_candidate_id": canonical_candidate_id,
            "candidate_id": canonical_candidate_id,
            "resolved_candidate": dict(resolved_candidate),
            "action_payload": dict(action_payload),
            "apply": {
                "mode": "apply_resolved_candidate",
                "payload": dict(action_payload),
            },
            "canonical_primary_payload": dict(canonical),
        }
        route_target = "handle_apply_buttons"
        _set_design_guide_primary_payload_binding_audit(
            visible_primary_candidate_id=canonical_candidate_id,
            button_contract_candidate_id=canonical_candidate_id,
            queued_apply_candidate_id=canonical_candidate_id,
            applied_candidate_id=None,
            visible_updates=dict(canonical.get("visible_updates") or canonical_updates),
            button_contract_updates=dict(canonical.get("button_contract_updates") or canonical_updates),
            queued_apply_updates=dict(canonical_updates),
            applied_updates={},
            payload_binding_match=True,
            payload_update_match=True,
            stale_apply_payload_blocked=False,
            canonical_primary_payload_exists=True,
            legacy_fallback_used=False,
        )
    contract_action_type = str(contract.get("action_type") or "").strip()
    contract_family = str(contract.get("family") or "").strip()
    contract_updates = dict(contract.get("updates") or {})
    if not canonical and contract_action_type == "apply_resolved_candidate" and contract_updates:
        contract_candidate_id = contract.get("candidate_id") or contract.get("source_candidate_id")
        contract_label = str(
            contract.get("label")
            or rec_dict.get("title")
            or rec_dict.get("label")
            or "Apply recommendation"
        ).strip()
        contract_resolved_candidate = {
            "action_type": "apply_resolved_candidate",
            "family": contract_family or rec_dict.get("family"),
            "updates": dict(contract_updates),
            "candidate_id": contract_candidate_id,
            "source_candidate_id": contract.get("source_candidate_id"),
            "label": contract_label,
        }
        contract_payload = {
            **dict(rec_dict.get("action_payload") or {}),
            "resolved_candidate_updates": dict(contract_updates),
            "resolved_candidate_action_type": "apply_resolved_candidate",
            "updates": dict(contract_updates),
            "source_candidate_id": contract.get("source_candidate_id"),
            "candidate_id": contract_candidate_id,
            "resolved_candidate": dict(contract_resolved_candidate),
            "resolved_candidate_label": contract_label,
        }
        rec_dict.update(
            {
                "action_type": "apply_resolved_candidate",
                "family": contract_family or rec_dict.get("family"),
                "updates": dict(contract_updates),
                "resolved_candidate_updates": dict(contract_updates),
                "source_candidate_id": contract.get("source_candidate_id"),
                "candidate_id": contract_candidate_id,
                "resolved_candidate": dict(contract_resolved_candidate),
                "action_payload": dict(contract_payload),
                "apply": {
                    "mode": "apply_resolved_candidate",
                    "payload": dict(contract_payload),
                },
            }
        )
    if contract_action_type == "apply_resolved_candidate" or dict(contract.get("updates") or {}):
        try:
            st.session_state["_design_guide_post_cleanup_acceptance_enabled"] = True
        except Exception:
            pass
    _set_design_guide_live_breadcrumb(
        "DG BUTTON CLICK",
        {
            "button_key": "apply_design_guide",
            "button_label": str(apply_label or ""),
            "route_target": route_target,
            "button_contract": dict(contract),
            "queued_via": "on_click",
        },
    )
    print(
        "DG BUTTON CLICK\n"
        "button_key=apply_design_guide\n"
        f"button_label={apply_label}\n"
        f"button_contract_action_type={contract_action_type}\n"
        f"button_contract_family={contract_family}\n"
        "section=design_guide_primary_card\n"
        f"next_function={route_target}\n",
        file=sys.stderr,
        end="",
        flush=True,
    )
    print(
        f"DG PRIMARY BUTTON -> {route_target.upper()}\n"
        "button_key=apply_design_guide\n",
        file=sys.stderr,
        end="",
        flush=True,
    )
    if route_target == "handle_auto_design":
        st.session_state["_inputs_action_run_auto_design"] = True
        st.session_state[AUTO_DESIGN_AUTO_INVOKE_KEY] = True
        st.session_state["auto_design_invoke_set"] = True
        st.session_state["auto_design_invoke_pending"] = True
        st.session_state[AUTO_DESIGN_REQUEST_TS_KEY] = time.time()
        st.session_state[AUTO_DESIGN_REQUEST_SOURCE_KEY] = "primary_apply_button"
        st.session_state["auto_design_request_source"] = "primary_apply_button"
        st.session_state["auto_design_invoke_consumed"] = False
        return
    st.session_state["pending_recommendation"] = rec_dict
    st.session_state["_inputs_action_apply_recommendation_payload"] = rec_dict
    st.session_state["pending_recommendation_applied_id"] = None
    st.session_state["_inputs_action_apply_recommendation"] = True
    _begin_design_guide_apply_trace(
        recommendation=rec_dict,
        source="primary_apply_button",
    )
    try:
        st.session_state.pop("_inputs_action_apply_recommendation", None)
        outcome = apply_recommendation_result(rec_dict)
    except Exception:
        raise
    if outcome == "failed":
        st.session_state.pop("_inputs_action_apply_recommendation", None)
        st.session_state.pop("_inputs_action_apply_recommendation_payload", None)
        _emit_design_guide_apply_trace_run_end(
            stop_reason=_recommendation_blocked_reason(rec_dict) or "apply_recommendation_failed",
            final_updates={},
            winner_label=str(rec_dict.get("title") or rec_dict.get("label") or ""),
        )
        return
    if outcome in {"dispatch_ok", "committed_fallback"}:
        st.session_state.pop("_inputs_action_apply_recommendation", None)
        st.session_state["pending_recommendation_applied_id"] = rec_dict.get("recommendation_id")
        st.session_state["pending_recommendation"] = None
        st.session_state.pop("_inputs_action_apply_recommendation_payload", None)
        st.session_state["_solver_result"] = None
        return


__all__ = [
    "bind_primary_button_queue_dependencies",
    "_queue_primary_design_guide_button_action",
]
