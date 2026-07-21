"""Guidance Apply action dispatch coordination for the Inputs page."""

from __future__ import annotations

from typing import Any

from inputs_page_modules.debug_output import safe_debug_print


_APPLY_GUIDANCE_ACTION_DEPENDENCIES: tuple[str, ...] = (
    "DESIGN_GUIDE_APPLY_BANNER_META_KEY",
    "DESIGN_GUIDE_DEBUG_BUNDLE_KEY",
    "DESIGN_GUIDE_LAST_APPLY_ROUTE_KEY",
    "DESIGN_GUIDE_PENDING_STEP_CTX_KEY",
    "_agent_debug_log",
    "_bottom_arrangement_to_shared_updates",
    "_apply_resolved_candidate_payload",
    "_apply_shared_updates",
    "_build_design_actions_context",
    "_candidate_debug_summary",
    "_clear_legacy_auto_design_request_flags",
    "_collect_design_overview",
    "_commit_auto_design_candidate_to_shared",
    "_compute_bottom_reo_recommendation",
    "_compute_geometry_recommendation",
    "_compute_shear_recommendation",
    "_debug_log_design_guide_consistency",
    "_emit_design_guide_apply_trace_run_end",
    "_finalize_design_guide_apply_step_history",
    "_guidance_action_updates",
    "_guidance_default_banner_title",
    "_guidance_state_snapshot",
    "_materialize_guidance_candidate",
    "_maybe_reset_design_guide_step_history",
    "_prepare_guidance_apply_banner_meta",
    "_record_design_guide_auto_geometry_applied",
    "_set_design_guide_live_breadcrumb",
    "_shared_state_snapshot",
    "_store_design_guide_apply_banner_payload",
    "_updates_match_state",
    "evaluate_candidate_full",
    "st",
    "sys",
    "time",
)


def bind_apply_guidance_action_dependencies(namespace: dict[str, Any]) -> None:
    globals().update(
        {
            name: namespace[name]
            for name in _APPLY_GUIDANCE_ACTION_DEPENDENCIES
            if name in namespace
        }
    )


def apply_guided_solve_sequence(*, source: str) -> bool:
    """
    Internal guided multi-step solve; invoked from apply_guidance_action for specific failing states.
    Not a primary entrypoint for pending recommendation apply (use apply_recommendation_result).
    """
    any_applied = False
    max_cycles = 2
    for _ in range(max_cycles):
        current_state = _shared_state_snapshot()
        current_candidate = evaluate_candidate_full(_guidance_state_snapshot(current_state), source="guidance_sequence_seed")
        if current_candidate is None or bool(current_candidate.get("is_compliant")):
            break
        changed_this_cycle = False
        recommendation_steps = [
            _compute_geometry_recommendation,
            _compute_bottom_reo_recommendation,
            _compute_shear_recommendation,
        ]
        _guided_step_titles = {
            "_compute_geometry_recommendation": "Adjust section geometry",
            "_compute_bottom_reo_recommendation": "Adjust bottom reinforcement",
            "_compute_shear_recommendation": "Adjust shear reinforcement",
        }
        for compute_fn in recommendation_steps:
            state_before = _shared_state_snapshot()
            recommendation = compute_fn(state_before)
            if not recommendation:
                continue
            updates = recommendation.get("updates")
            if not updates:
                arrangement = recommendation.get("arrangement")
                updates = _bottom_arrangement_to_shared_updates(arrangement or {}) if arrangement else None
            if not updates or _updates_match_state(state_before, updates):
                continue
            pre_ctx = _build_design_actions_context(state_before)
            pre_overview = _collect_design_overview(state_before, context=pre_ctx)
            bundle = st.session_state.get(DESIGN_GUIDE_DEBUG_BUNDLE_KEY) or {}
            _prepare_guidance_apply_banner_meta(
                "guided_solve_step",
                {
                    "guidance_banner_title": _guided_step_titles.get(
                        getattr(compute_fn, "__name__", ""),
                        "Guided design step",
                    ),
                },
            )
            meta = st.session_state.get(DESIGN_GUIDE_APPLY_BANNER_META_KEY) or {}
            st.session_state[DESIGN_GUIDE_PENDING_STEP_CTX_KEY] = {
                "pre_overview": pre_overview,
                "guidance_branch_before": bundle.get("guidance_branch"),
                "action_type": "guided_solve_step",
                "payload": {"compute_fn": getattr(compute_fn, "__name__", "")},
                "recommendation_title": str(meta.get("title") or ""),
            }
            applied = _apply_shared_updates(updates, source=source, rerun=False, focus_section="model")
            if not applied:
                st.session_state.pop(DESIGN_GUIDE_PENDING_STEP_CTX_KEY, None)
                continue
            any_applied = True
            changed_this_cycle = True
            current_candidate = evaluate_candidate_full(
                _guidance_state_snapshot(_shared_state_snapshot()),
                source="guidance_sequence_step",
            )
            if current_candidate and bool(current_candidate.get("is_compliant")):
                st.rerun()
                return True
        if not changed_this_cycle:
            break
    if any_applied:
        st.rerun()
    return any_applied


def apply_guidance_action(action_type: str, payload: dict) -> bool:
    """
    Dispatch implementation for guidance-style applies; primary callee of apply_recommendation_result.
    Do not call directly from UI handlers — use apply_recommendation_result(pending_rec).
    """
    _set_design_guide_live_breadcrumb(
        "DG APPLY_GUIDANCE_ACTION",
        {"action_type": str(action_type or "")},
    )
    safe_debug_print(
        "DG ALT APPLY ENTRY\n"
        f"function=apply_guidance_action\n"
        f"action_type={action_type}\n",
        file=sys.stderr,
        end="",
        flush=True,
    )
    started_at = time.perf_counter()
    _maybe_reset_design_guide_step_history(_shared_state_snapshot())
    step_bundle = st.session_state.get(DESIGN_GUIDE_DEBUG_BUNDLE_KEY) or {}
    payload_dict = dict(payload or {})
    if action_type == "apply_resolved_candidate":
        return _apply_resolved_candidate_payload(payload_dict)
    payload_resolved_updates = payload_dict.get("resolved_candidate_updates")
    has_payload_resolved = isinstance(payload_resolved_updates, dict) and bool(payload_resolved_updates)
    one_click_available_at_step_start = bool(
        has_payload_resolved or step_bundle.get("one_click_critical_candidate_exists"),
    )
    one_click_label_at_step_start = (
        payload_dict.get("resolved_candidate_label")
        or step_bundle.get("one_click_critical_candidate_label")
    )
    if action_type == "apply_mode_recommendation":
        prior_snapshot = _shared_state_snapshot()
        pre_ctx = _build_design_actions_context(prior_snapshot)
        pre_overview = _collect_design_overview(prior_snapshot, context=pre_ctx)
        bundle = st.session_state.get(DESIGN_GUIDE_DEBUG_BUNDLE_KEY) or {}
        current_state = _shared_state_snapshot()
        p = dict(payload or {})
        _prepare_guidance_apply_banner_meta(
            action_type,
            {
                **p,
                "guidance_banner_title": p.get("guidance_banner_title")
                or p.get("label")
                or _guidance_default_banner_title(action_type),
            },
        )
        base_candidate = evaluate_candidate_full(_guidance_state_snapshot(current_state), source="guide_apply_mode_seed")
        applied_candidate = _materialize_guidance_candidate(
            base_candidate,
            payload,
            source="guide_apply_mode_candidate",
        )
        if not applied_candidate:
            st.session_state.pop(DESIGN_GUIDE_APPLY_BANNER_META_KEY, None)
            return False
        meta = st.session_state.get(DESIGN_GUIDE_APPLY_BANNER_META_KEY) or {}
        st.session_state[DESIGN_GUIDE_PENDING_STEP_CTX_KEY] = {
            "pre_overview": pre_overview,
            "guidance_branch_before": bundle.get("guidance_branch"),
            "action_type": action_type,
            "payload": p,
            "recommendation_title": str(meta.get("title") or ""),
            "recommendation_label_at_step_start": str(
                p.get("resolved_candidate_label") or p.get("label") or meta.get("title") or "",
            ),
            "recommendation_action_type_at_step_start": str(action_type),
            "used_resolved_payload": bool(p.get("resolved_candidate_updates")),
            "one_click_candidate_available_at_step_start": one_click_available_at_step_start,
            "one_click_candidate_label_at_step_start": one_click_label_at_step_start,
        }
        _agent_debug_log(
            "Applying design guide recommendation via committed candidate path",
            {
                "action_type": action_type,
                "candidate_summary": _candidate_debug_summary(applied_candidate),
            },
            location="inputs_page.py:apply_guidance_action:apply_mode_recommendation",
            hypothesis_id="H303",
        )
        final_updates = _commit_auto_design_candidate_to_shared(applied_candidate)
        if not final_updates:
            st.session_state.pop(DESIGN_GUIDE_APPLY_BANNER_META_KEY, None)
            st.session_state.pop(DESIGN_GUIDE_PENDING_STEP_CTX_KEY, None)
            _emit_design_guide_apply_trace_run_end(
                stop_reason="candidate_commit_failed",
                final_updates={},
                winner_label=str((applied_candidate or {}).get("label") or ""),
            )
            return False
        _clear_legacy_auto_design_request_flags(clear_invoke=False)
        _debug_log_design_guide_consistency(
            source=f"guidance:{action_type}",
            applied_candidate=applied_candidate,
        )
        _finalize_design_guide_apply_step_history(
            prior_state=prior_snapshot,
            source=f"guidance:{action_type}",
            applied_candidate=applied_candidate,
        )
        _store_design_guide_apply_banner_payload(prior_snapshot, _shared_state_snapshot())
        _record_design_guide_auto_geometry_applied(prior_snapshot, final_updates)
        _emit_design_guide_apply_trace_run_end(
            stop_reason="applied_recommendation",
            final_updates=dict(final_updates or {}),
            winner_label=str((applied_candidate or {}).get("label") or ""),
        )
        # Rerun ownership: single st.rerun for this apply path.
        st.rerun()
        return True
    current_candidate = evaluate_candidate_full(
        _guidance_state_snapshot(_shared_state_snapshot()),
        source="guidance_action_seed",
    )
    failing_guidance_actions = {
        "increase_depth",
        "reduce_bar_spacing",
        "apply_geometry_recommendation",
        "apply_bottom_recommendation",
        "apply_shear_recommendation",
    }
    resolved_payload_updates = (
        dict((payload_dict or {}).get("resolved_candidate_updates") or {})
        if isinstance((payload_dict or {}).get("resolved_candidate_updates"), dict)
        else {}
    )
    has_payload_resolved = bool(resolved_payload_updates)
    explicit_updates = (
        dict((payload_dict or {}).get("updates") or {})
        if isinstance((payload_dict or {}).get("updates"), dict)
        else {}
    )
    has_explicit_direct_updates = bool(explicit_updates)
    force_direct_apply = bool((payload_dict or {}).get("force_direct_apply"))
    if (
        current_candidate
        and not bool(current_candidate.get("is_compliant"))
        and action_type in failing_guidance_actions
        and not has_payload_resolved
        and not force_direct_apply
        and not has_explicit_direct_updates
    ):
        st.session_state[DESIGN_GUIDE_LAST_APPLY_ROUTE_KEY] = {
            "apply_used_resolved_candidate_payload": False,
            "apply_fell_back_to_generic_solver": True,
            "apply_fallback_reason": "failing_state_guided_solve_sequence",
            "apply_direct_resolved_candidate": False,
            "one_click_candidate_available_at_step_start": one_click_available_at_step_start,
            "one_click_candidate_label_at_step_start": one_click_label_at_step_start,
        }
        return apply_guided_solve_sequence(source=f"guidance:{action_type}")
    prior_snapshot = _shared_state_snapshot()
    pre_ctx = _build_design_actions_context(prior_snapshot)
    pre_overview = _collect_design_overview(prior_snapshot, context=pre_ctx)
    bundle = st.session_state.get(DESIGN_GUIDE_DEBUG_BUNDLE_KEY) or {}
    _prepare_guidance_apply_banner_meta(action_type, payload or {})
    meta = st.session_state.get(DESIGN_GUIDE_APPLY_BANNER_META_KEY) or {}
    used_resolved_payload = bool(has_payload_resolved)
    updates = {}
    if has_payload_resolved:
        updates = dict(resolved_payload_updates)
    elif has_explicit_direct_updates:
        updates = dict(explicit_updates)
    else:
        updates = _guidance_action_updates(action_type, payload, state=_shared_state_snapshot())
    if not updates:
        st.session_state.pop(DESIGN_GUIDE_APPLY_BANNER_META_KEY, None)
        st.session_state.pop(DESIGN_GUIDE_PENDING_STEP_CTX_KEY, None)
        st.session_state[DESIGN_GUIDE_LAST_APPLY_ROUTE_KEY] = {
            "apply_used_resolved_candidate_payload": used_resolved_payload,
            "apply_fell_back_to_generic_solver": True,
            "apply_fallback_reason": "no_resolved_updates",
            "apply_direct_resolved_candidate": False,
            "one_click_candidate_available_at_step_start": one_click_available_at_step_start,
            "one_click_candidate_label_at_step_start": one_click_label_at_step_start,
        }
        _emit_design_guide_apply_trace_run_end(
            stop_reason="no_resolved_updates",
            final_updates={},
        )
        return False
    st.session_state[DESIGN_GUIDE_PENDING_STEP_CTX_KEY] = {
        "pre_overview": pre_overview,
        "guidance_branch_before": bundle.get("guidance_branch"),
        "action_type": action_type,
        "payload": dict(payload or {}),
        "recommendation_title": str(meta.get("title") or ""),
        "recommendation_label_at_step_start": str(
            payload_dict.get("resolved_candidate_label")
            or payload_dict.get("label")
            or meta.get("title")
            or "",
        ),
        "recommendation_action_type_at_step_start": str(
            payload_dict.get("resolved_candidate_action_type")
            or action_type
            or "",
        ),
        "used_resolved_payload": used_resolved_payload,
        "one_click_candidate_available_at_step_start": one_click_available_at_step_start,
        "one_click_candidate_label_at_step_start": one_click_label_at_step_start,
    }
    st.session_state[DESIGN_GUIDE_LAST_APPLY_ROUTE_KEY] = {
        "apply_used_resolved_candidate_payload": used_resolved_payload,
        "apply_fell_back_to_generic_solver": False,
        "apply_fallback_reason": None,
        "apply_direct_resolved_candidate": False,
        "one_click_candidate_available_at_step_start": one_click_available_at_step_start,
        "one_click_candidate_label_at_step_start": one_click_label_at_step_start,
    }
    return _apply_shared_updates(
        updates,
        source=f"guidance:{action_type}",
        focus_section="model",
    )


__all__ = [
    "bind_apply_guidance_action_dependencies",
    "apply_guided_solve_sequence",
    "apply_guidance_action",
]
