"""Pending recommendation construction for the Inputs Design Guide."""

from __future__ import annotations

from typing import Any

from inputs_application.recommendation_envelope import (
    attach_recommendation_envelope as _attach_recommendation_envelope,
    effective_apply_mode_and_payload as _effective_apply_mode_and_payload_from_pending,
)


_PENDING_RECOMMENDATION_DEPENDENCIES: tuple[str, ...] = (
    "DESIGN_GUIDE_APPLY_BANNER_KEY",
    "DESIGN_GUIDE_APPLY_BANNER_META_KEY",
    "DESIGN_GUIDE_PENDING_STEP_CTX_KEY",
    "_ensure_guidance_item_resolved_candidate_payload",
    "_guidance_executor_actionability_contract",
    "_proposed_change_lines_for_guidance_item",
    "_resolve_recommendation_updates",
    "_shared_state_snapshot",
    "st",
)


def _pending_matches_actionable_guidance_item(pending: dict, item: dict) -> bool:
    """Return whether session pending still represents the actionable card."""
    if not isinstance(pending, dict) or not isinstance(item, dict):
        return False
    pending_title = str(pending.get("title") or "").strip()
    item_title = str(
        item.get("canonical_winner_label") or item.get("title_main") or ""
    ).strip()
    if pending_title and item_title and pending_title != item_title:
        return False
    pending_mode, _ = _effective_apply_mode_and_payload_from_pending(pending)
    item_mode = str(item.get("action_type") or "").strip()
    if pending_mode and item_mode and pending_mode != item_mode:
        return False
    return True


def _pending_recommendation_equivalent(
    first: dict | None,
    second: dict | None,
) -> bool:
    """Compare the user-visible and executable identity of recommendations."""
    if not isinstance(first, dict) or not isinstance(second, dict):
        return False
    first_mode, first_payload = _effective_apply_mode_and_payload_from_pending(first)
    second_mode, second_payload = _effective_apply_mode_and_payload_from_pending(second)
    return (
        first_mode == second_mode
        and first_payload == second_payload
        and str(first.get("title") or "").strip()
        == str(second.get("title") or "").strip()
    )


def bind_pending_recommendation_dependencies(namespace: dict[str, Any]) -> None:
    globals().update(
        {
            name: namespace[name]
            for name in _PENDING_RECOMMENDATION_DEPENDENCIES
            if name in namespace
        }
    )


def _build_pending_recommendation(item: dict, state: dict) -> dict | None:
    if not isinstance(item, dict):
        return None
    action_type = str(item.get("action_type") or "").strip()
    if not action_type:
        return None
    _ensure_guidance_item_resolved_candidate_payload(item, state=state)
    updates = _resolve_recommendation_updates(item, state=state)
    if not updates:
        # Some live Design Guide cards are rebuilt from a repaired/coherence-backfilled
        # render state that can be too thin to re-resolve actionable updates. Retry once
        # against the canonical shared snapshot before treating the card as non-executable.
        try:
            live_state = _shared_state_snapshot()
        except Exception:
            live_state = {}
        if isinstance(live_state, dict) and live_state:
            _ensure_guidance_item_resolved_candidate_payload(item, state=live_state)
            updates = _resolve_recommendation_updates(item, state=live_state)
    if not updates:
        return None
    payload = dict(item.get("action_payload") or {})
    resolved_candidate = dict(item.get("resolved_candidate") or {})
    if not isinstance(resolved_candidate.get("updates"), dict) or not resolved_candidate.get("updates"):
        resolved_candidate = {
            **resolved_candidate,
            "label": str(
                item.get("canonical_winner_label")
                or payload.get("resolved_candidate_label")
                or item.get("title_main")
                or "Apply recommendation",
            ).strip(),
            "action_type": str(
                payload.get("resolved_candidate_action_type")
                or action_type
                or "apply_compound_guidance"
            ).strip(),
            "updates": dict(updates),
        }
    payload.setdefault("resolved_candidate_updates", dict(updates))
    payload.setdefault(
        "resolved_candidate_label",
        str(
            item.get("canonical_winner_label")
            or resolved_candidate.get("label")
            or item.get("title_main")
            or "Apply recommendation",
        ).strip(),
    )
    payload.setdefault(
        "resolved_candidate_action_type",
        str(resolved_candidate.get("action_type") or action_type or "apply_compound_guidance").strip(),
    )
    payload.setdefault("updates", dict(updates))
    description = ""
    change_lines = _proposed_change_lines_for_guidance_item(item, state)
    if change_lines:
        description = str(change_lines[0] or "").strip()
    if not description:
        description = str(item.get("reasoning") or "").strip()
    if not description:
        description = "Review and apply this recommendation."
    _pending_title = str(
        item.get("canonical_winner_label")
        or item.get("title_main")
        or "Optimisation available",
    ).strip()
    recommendation_id = (
        str(_pending_title or "Optimisation available"),
        tuple(sorted((str(k), str(v)) for k, v in updates.items())),
    )
    recommendation = {
        "title": _pending_title or "Optimisation available",
        "description": description,
        "updates": updates,
        "action_type": "apply_resolved_candidate" if bool(payload.get("resolved_candidate_updates")) else action_type,
        "action_payload": payload,
        "resolved_candidate": resolved_candidate,
        "has_resolved_candidate_payload": bool(payload.get("resolved_candidate_updates")),
        "recommendation_id": recommendation_id,
    }
    contract_allowed, contract_reason = _guidance_executor_actionability_contract(
        item,
        state=state,
    )
    return _attach_recommendation_envelope(
        recommendation,
        source="guidance",
        status="ready" if contract_allowed else "blocked",
        blocked_reason=None if contract_allowed else contract_reason,
        commit_eligible=True if contract_allowed else False,
    )


def _sync_pending_recommendation_from_guidance(
    guidance_items: list[dict],
    state: dict,
    *,
    terminal_state: str | None = None,
) -> dict | None:
    for item in guidance_items or []:
        if isinstance(item, dict):
            _ensure_guidance_item_resolved_candidate_payload(item, state=state)
    primary_item = guidance_items[0] if guidance_items and isinstance(guidance_items[0], dict) else None
    actionable_item = (
        primary_item
        if isinstance(primary_item, dict) and str(primary_item.get("action_type") or "").strip()
        else None
    )
    terminal_state_norm = str(terminal_state or "").strip()
    if terminal_state_norm == "optimal":
        st.session_state["pending_recommendation"] = None
        st.session_state.pop(DESIGN_GUIDE_APPLY_BANNER_KEY, None)
        st.session_state.pop(DESIGN_GUIDE_APPLY_BANNER_META_KEY, None)
        st.session_state.pop(DESIGN_GUIDE_PENDING_STEP_CTX_KEY, None)
        return None
    if terminal_state_norm == "very_low_demand" and actionable_item is None:
        st.session_state["pending_recommendation"] = None
        st.session_state.pop(DESIGN_GUIDE_APPLY_BANNER_KEY, None)
        st.session_state.pop(DESIGN_GUIDE_APPLY_BANNER_META_KEY, None)
        st.session_state.pop(DESIGN_GUIDE_PENDING_STEP_CTX_KEY, None)
        return None
    existing = st.session_state.get("pending_recommendation")
    if actionable_item is None:
        if isinstance(existing, dict) and str(existing.get("_source") or "").strip() in {"guidance", "auto_design"}:
            st.session_state["pending_recommendation"] = None
        return None

    recommendation = _build_pending_recommendation(actionable_item, state)
    if not isinstance(recommendation, dict):
        if (
            isinstance(existing, dict)
            and str(existing.get("_source") or "").strip() == "guidance"
            and _pending_matches_actionable_guidance_item(existing, actionable_item)
        ):
            return existing
        if isinstance(existing, dict) and str(existing.get("_source") or "").strip() in {"guidance", "auto_design"}:
            st.session_state["pending_recommendation"] = None
        return None
    if _pending_recommendation_equivalent(existing, recommendation):
        if isinstance(existing, dict) and not isinstance(existing.get("recommendation_envelope"), dict):
            existing = _attach_recommendation_envelope(
                existing,
                source=str(existing.get("_source") or "guidance"),
                status="ready",
            )
            st.session_state["pending_recommendation"] = existing
        return existing
    pending_out = {
        **dict(recommendation),
        "_source": "guidance",
    }
    if not isinstance(pending_out.get("recommendation_envelope"), dict):
        pending_out = _attach_recommendation_envelope(
            pending_out,
            source="guidance",
            status="ready",
        )
    st.session_state["pending_recommendation"] = pending_out
    return pending_out


__all__ = [
    "bind_pending_recommendation_dependencies",
    "_build_pending_recommendation",
    "_sync_pending_recommendation_from_guidance",
]
