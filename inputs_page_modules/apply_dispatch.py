"""Apply dispatch coordinators for Inputs page recommendation results."""

from __future__ import annotations

from typing import Any

from inputs_page_modules.debug_output import safe_debug_print


_APPLY_RECOMMENDATION_RESULT_NAMES: tuple[str, ...] = (
    "DESIGN_GUIDE_LAST_APPLY_ROUTE_KEY",
    "_effective_apply_mode_and_payload_from_pending",
    "_emit_design_guide_apply_trace_run_end",
    "_local_cleanup_acceptance_fingerprint",
    "_recommendation_blocked_reason",
    "_recommendation_commit_eligible",
    "_set_design_guide_live_breadcrumb",
    "_set_design_guide_primary_payload_binding_audit",
    "_set_one_click_run_feedback",
    "_shared_state_snapshot",
    "apply_design_candidate",
    "apply_guidance_action",
)


def _bind_apply_recommendation_result_globals(
    *,
    legacy_page: Any,
    st_module: Any,
    sys_module: Any,
) -> None:
    namespace = globals()
    namespace["st"] = st_module
    namespace["sys"] = sys_module
    for name in _APPLY_RECOMMENDATION_RESULT_NAMES:
        namespace[name] = getattr(legacy_page, name)


def apply_recommendation_result_coordinator(
    *,
    legacy_page: Any,
    st_module: Any,
    sys_module: Any,
    rec: dict,
) -> str:
    _bind_apply_recommendation_result_globals(
        legacy_page=legacy_page,
        st_module=st_module,
        sys_module=sys_module,
    )
    return apply_recommendation_result(rec)


def apply_recommendation_result(rec: dict) -> str:
    _set_design_guide_live_breadcrumb(
        "DG APPLY_RECOMMENDATION_RESULT",
        {"has_rec": bool(isinstance(rec, dict) and rec)},
    )
    safe_debug_print(
        "DG ALT APPLY ENTRY\n"
        "function=apply_recommendation_result\n",
        file=sys.stderr,
        end="",
        flush=True,
    )
    if not _recommendation_commit_eligible(rec):
        rec_d = rec if isinstance(rec, dict) else {}
        _set_one_click_run_feedback(
            status="blocked",
            reason=_recommendation_blocked_reason(rec) or "candidate_not_commit_eligible",
            winning_label=str(rec_d.get("title") or ""),
            winning_action_type=str(rec_d.get("action_type") or ""),
        )
        return "failed"
    mode, payload = _effective_apply_mode_and_payload_from_pending(rec)
    if mode:
        try:
            st.session_state["_design_guide_post_cleanup_acceptance_enabled"] = True
        except Exception:
            pass
    if mode and isinstance(payload, dict):
        if apply_guidance_action(mode, payload):
            st.session_state.pop("_one_click_run_feedback", None)
            return "dispatch_ok"
        if str((rec or {}).get("_source") or "") == "design_guide_primary_apply_payload":
            _set_design_guide_primary_payload_binding_audit(
                legacy_fallback_used=False,
                primary_apply_dispatch_failed=True,
                payload_binding_match=False,
                payload_update_match=False,
            )
            _set_one_click_run_feedback(
                status="blocked",
                reason="canonical_primary_payload_dispatch_failed",
                winning_label=str((rec or {}).get("title") or ""),
                winning_action_type=str((rec or {}).get("action_type") or ""),
            )
            return "failed"
    if str((rec or {}).get("_source") or "") == "design_guide_primary_apply_payload":
        _set_design_guide_primary_payload_binding_audit(
            legacy_fallback_used=False,
            primary_apply_dispatch_failed=True,
            payload_binding_match=False,
            payload_update_match=False,
        )
        return "failed"
    resolved_candidate = rec.get("resolved_candidate")
    if isinstance(resolved_candidate, dict) and isinstance(resolved_candidate.get("updates"), dict) and resolved_candidate.get("updates"):
        fallback_candidate = resolved_candidate
    else:
        fallback_candidate = rec
    if apply_design_candidate(st.session_state, fallback_candidate):
        try:
            st.session_state["_design_guide_post_cleanup_acceptance_enabled"] = True
            st.session_state["_design_guide_post_cleanup_acceptance_fp"] = (
                _local_cleanup_acceptance_fingerprint(_shared_state_snapshot())
            )
        except Exception:
            pass
        _emit_design_guide_apply_trace_run_end(
            stop_reason="applied_recommendation",
            final_updates=dict((fallback_candidate or {}).get("updates") or {}),
            winner_label=str(
                (
                    fallback_candidate.get("label")
                    if isinstance(fallback_candidate, dict)
                    else rec.get("title")
                )
                or ""
            ),
        )
        st.session_state.pop("_one_click_run_feedback", None)
        st.session_state[DESIGN_GUIDE_LAST_APPLY_ROUTE_KEY] = {
            **dict(st.session_state.get(DESIGN_GUIDE_LAST_APPLY_ROUTE_KEY) or {}),
            "apply_used_resolved_candidate_payload": bool(
                isinstance(fallback_candidate, dict)
                and isinstance(fallback_candidate.get("updates"), dict)
                and bool(fallback_candidate.get("updates")),
            ),
            "apply_direct_resolved_candidate": True,
            "apply_fell_back_to_generic_solver": False,
            "apply_fallback_reason": "legacy_direct_updates_fallback",
            "resolved_candidate_label": (
                fallback_candidate.get("label")
                if isinstance(fallback_candidate, dict)
                else rec.get("title")
            ),
        }
        _set_design_guide_primary_payload_binding_audit(
            legacy_fallback_used=True,
            applied_candidate_id=(
                fallback_candidate.get("source_candidate_id")
                or fallback_candidate.get("candidate_id")
                if isinstance(fallback_candidate, dict)
                else None
            ),
            applied_updates=dict((fallback_candidate or {}).get("updates") or {}),
        )
        return "committed_fallback"
    return "failed"
