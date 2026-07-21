"""Apply resolved-candidate payload coordinator for the Inputs page."""

from __future__ import annotations

from typing import Any

from inputs_page_modules.debug_output import safe_debug_print


def apply_resolved_candidate_payload(
    *,
    legacy_page: Any,
    st_module: Any,
    stderr: Any,
    payload: dict,
) -> bool:
    """Apply a pre-resolved Design Guide candidate without owning candidate logic."""
    st = st_module
    _set_design_guide_live_breadcrumb = legacy_page._set_design_guide_live_breadcrumb
    _normalise_design_guide_candidate_id = legacy_page._normalise_design_guide_candidate_id
    _normalise_invalid_shear_state_updates = legacy_page._normalise_invalid_shear_state_updates
    _shared_state_snapshot = legacy_page._shared_state_snapshot
    evaluate_candidate_full = legacy_page.evaluate_candidate_full
    _guidance_state_snapshot = legacy_page._guidance_state_snapshot
    _local_cleanup_acceptance_fingerprint = legacy_page._local_cleanup_acceptance_fingerprint
    _DESIGN_GUIDE_POST_CLEANUP_ACCEPTED_FPS = legacy_page._DESIGN_GUIDE_POST_CLEANUP_ACCEPTED_FPS
    _build_design_actions_context = legacy_page._build_design_actions_context
    _collect_design_overview = legacy_page._collect_design_overview
    _prepare_guidance_apply_banner_meta = legacy_page._prepare_guidance_apply_banner_meta
    _set_shared_updates = legacy_page._set_shared_updates
    _pop_inputs_widget_keys_for_shared_updates = legacy_page._pop_inputs_widget_keys_for_shared_updates
    derive_design_actions = legacy_page.derive_design_actions
    _clear_legacy_auto_design_request_flags = legacy_page._clear_legacy_auto_design_request_flags
    _debug_log_design_guide_consistency = legacy_page._debug_log_design_guide_consistency
    _finalize_design_guide_apply_step_history = legacy_page._finalize_design_guide_apply_step_history
    _store_design_guide_apply_banner_payload = legacy_page._store_design_guide_apply_banner_payload
    _record_design_guide_auto_geometry_applied = legacy_page._record_design_guide_auto_geometry_applied
    _design_guide_cache_fingerprint = legacy_page._design_guide_cache_fingerprint
    _invalidate_design_guide_caches = legacy_page._invalidate_design_guide_caches
    finalize_auto_design_publish = legacy_page.finalize_auto_design_publish
    persist_active_beam_from_shared = legacy_page.persist_active_beam_from_shared
    persist_state_snapshot = legacy_page.persist_state_snapshot
    _set_design_guide_primary_payload_binding_audit = legacy_page._set_design_guide_primary_payload_binding_audit
    _emit_design_guide_apply_trace_run_end = legacy_page._emit_design_guide_apply_trace_run_end
    DESIGN_GUIDE_LAST_APPLY_ROUTE_KEY = legacy_page.DESIGN_GUIDE_LAST_APPLY_ROUTE_KEY
    DESIGN_GUIDE_DEBUG_BUNDLE_KEY = legacy_page.DESIGN_GUIDE_DEBUG_BUNDLE_KEY
    DESIGN_GUIDE_APPLY_BANNER_META_KEY = legacy_page.DESIGN_GUIDE_APPLY_BANNER_META_KEY
    DESIGN_GUIDE_PENDING_STEP_CTX_KEY = legacy_page.DESIGN_GUIDE_PENDING_STEP_CTX_KEY
    DESIGN_GUIDE_PANEL_BASELINE_FP_KEY = legacy_page.DESIGN_GUIDE_PANEL_BASELINE_FP_KEY
    DESIGN_GUIDE_NEEDS_REFRESH_KEY = legacy_page.DESIGN_GUIDE_NEEDS_REFRESH_KEY
    DESIGN_GUIDE_PRIMARY_APPLY_PAYLOAD_KEY = legacy_page.DESIGN_GUIDE_PRIMARY_APPLY_PAYLOAD_KEY
    DESIGN_GUIDE_PRIMARY_PAYLOAD_BINDING_AUDIT_KEY = legacy_page.DESIGN_GUIDE_PRIMARY_PAYLOAD_BINDING_AUDIT_KEY

    _set_design_guide_live_breadcrumb(
        "DG APPLY_RESOLVED_PAYLOAD",
        {"has_updates": bool((dict(payload or {})).get("resolved_candidate_updates"))},
    )
    safe_debug_print(
        "DG ALT APPLY ENTRY\n"
        "function=_apply_resolved_candidate_payload\n",
        file=stderr,
        end="",
        flush=True,
    )
    payload_dict = dict(payload or {})
    label = str(payload_dict.get("resolved_candidate_label") or payload_dict.get("label") or "Apply recommendation").strip()
    candidate_action_type = str(payload_dict.get("resolved_candidate_action_type") or "apply_compound_guidance").strip()
    updates = dict(payload_dict.get("resolved_candidate_updates") or {})
    candidate_id = _normalise_design_guide_candidate_id(
        payload_dict.get("source_candidate_id"),
        payload_dict.get("candidate_id"),
        (dict(payload_dict.get("resolved_candidate") or {})).get("source_candidate_id"),
        (dict(payload_dict.get("resolved_candidate") or {})).get("candidate_id"),
        family=str(payload_dict.get("resolved_candidate_family_tag") or ""),
        updates=updates,
    )
    expected_post_util = payload_dict.get("resolved_candidate_post_util")
    try:
        expected_post_util = float(expected_post_util) if expected_post_util is not None else None
    except Exception:
        expected_post_util = None
    st.session_state[DESIGN_GUIDE_LAST_APPLY_ROUTE_KEY] = {
        **dict(st.session_state.get(DESIGN_GUIDE_LAST_APPLY_ROUTE_KEY) or {}),
        "post_apply_resolved_candidate_attempted": True,
        "apply_used_resolved_candidate_payload": bool(updates),
        "apply_direct_resolved_candidate": bool(updates),
        "apply_fell_back_to_generic_solver": False,
        "apply_fallback_reason": None if updates else "missing_resolved_candidate_updates",
        "resolved_candidate_label": label,
        "resolved_candidate_action_type": candidate_action_type,
        "resolved_candidate_id": candidate_id,
        "applied_candidate_id": None,
        "queued_apply_candidate_id": candidate_id,
        "queued_apply_updates": dict(updates),
        "expected_post_util": expected_post_util,
    }
    if not updates:
        st.session_state[DESIGN_GUIDE_LAST_APPLY_ROUTE_KEY] = {
            **dict(st.session_state.get(DESIGN_GUIDE_LAST_APPLY_ROUTE_KEY) or {}),
            "post_apply_resolved_candidate_attempted": True,
            "apply_used_resolved_candidate_payload": False,
            "apply_direct_resolved_candidate": False,
            "apply_fell_back_to_generic_solver": False,
            "apply_fallback_reason": "missing_resolved_candidate_updates",
            "post_apply_resolved_candidate_label": label,
            "post_apply_resolved_candidate_expected_util": expected_post_util,
        }
        return False

    original_action_type = candidate_action_type
    family_tag = payload_dict.get("resolved_candidate_family_tag")
    subfamilies = list(payload_dict.get("resolved_candidate_subfamilies") or []) if isinstance(payload_dict.get("resolved_candidate_subfamilies"), list) else []
    change_lines = list(payload_dict.get("guidance_change_lines") or [])

    prior_state = _shared_state_snapshot()
    updates = _normalise_invalid_shear_state_updates(
        prior_state,
        updates,
        source="guidance:apply_resolved_candidate",
    )
    st.session_state["_allow_design_guide_apply_shared_keys_once"] = sorted(str(k) for k in updates.keys())
    expected_state = dict(prior_state)
    expected_state.update(updates)
    applied_candidate = evaluate_candidate_full(
        _guidance_state_snapshot(expected_state),
        source="guidance:apply_resolved_candidate:post_apply_preview",
        updates=updates,
    )
    if isinstance(applied_candidate, dict):
        try:
            preview_overview = dict(applied_candidate.get("overview") or {})
            if bool(preview_overview.get("all_key_pass")) and not bool(preview_overview.get("any_fail")):
                accepted_fp = _local_cleanup_acceptance_fingerprint(expected_state)
                _DESIGN_GUIDE_POST_CLEANUP_ACCEPTED_FPS.add(accepted_fp)
                st.session_state["_design_guide_post_cleanup_acceptance_fp"] = accepted_fp
        except Exception:
            pass
    st.session_state["_design_guide_post_cleanup_acceptance_enabled"] = True
    pre_ctx = _build_design_actions_context(prior_state)
    pre_overview = _collect_design_overview(prior_state, context=pre_ctx)
    bundle = st.session_state.get(DESIGN_GUIDE_DEBUG_BUNDLE_KEY) or {}
    step_bundle = st.session_state.get(DESIGN_GUIDE_DEBUG_BUNDLE_KEY) or {}
    one_click_available_at_step_start = bool(
        step_bundle.get("one_click_critical_candidate_exists") or updates,
    )
    one_click_label_at_step_start = (
        payload_dict.get("resolved_candidate_label")
        or step_bundle.get("one_click_critical_candidate_label")
        or label
    )
    _prepare_guidance_apply_banner_meta("apply_resolved_candidate", payload_dict)
    meta = st.session_state.get(DESIGN_GUIDE_APPLY_BANNER_META_KEY) or {}
    st.session_state[DESIGN_GUIDE_PENDING_STEP_CTX_KEY] = {
        "pre_overview": pre_overview,
        "guidance_branch_before": bundle.get("guidance_branch"),
        "action_type": "apply_resolved_candidate",
        "payload": dict(payload_dict),
        "recommendation_title": str(meta.get("title") or label),
        "recommendation_label_at_step_start": str(
            payload_dict.get("resolved_candidate_label")
            or payload_dict.get("label")
            or meta.get("title")
            or label
            or "",
        ),
        "recommendation_action_type_at_step_start": "apply_resolved_candidate",
        "used_resolved_payload": True,
        "one_click_candidate_available_at_step_start": True,
        "one_click_candidate_label_at_step_start": one_click_label_at_step_start,
    }

    current_apply_guard = legacy_page._design_guide_apply_updates_current_state_guard(prior_state, updates)
    if not current_apply_guard.get("pass"):
        st.session_state[DESIGN_GUIDE_LAST_APPLY_ROUTE_KEY] = {
            **dict(st.session_state.get(DESIGN_GUIDE_LAST_APPLY_ROUTE_KEY) or {}),
            "apply_fallback_reason": "current_state_apply_preview_blocked",
            "current_state_apply_preview_blocked": True,
            "current_state_apply_guard": dict(current_apply_guard),
        }
        st.session_state.pop(DESIGN_GUIDE_PRIMARY_APPLY_PAYLOAD_KEY, None)
        return False

    _set_shared_updates(updates, source="guidance:apply_resolved_candidate")
    if any(k in {"lig_d", "lig_legs", "s_lig"} for k in updates.keys()):
        st.session_state["_skip_shear_widget_backflow_once"] = True
        st.session_state["_skip_shear_widget_backflow_runs"] = 4
    cleared_widget_keys = _pop_inputs_widget_keys_for_shared_updates(updates)
    if any(k in {"lig_d", "lig_legs", "s_lig"} for k in updates.keys()):
        shear_widget_map = {
            "inputs_lig_d": "lig_d",
            "inputs_lig_legs": "lig_legs",
            "inputs_s_lig": "s_lig",
            "shear_lig_d": "lig_d",
            "shear_lig_legs": "lig_legs",
            "shear_s_lig": "s_lig",
        }
        hydrated_map = st.session_state.get("_hydrated_from_shared_map")
        for widget_key, shared_key in shear_widget_map.items():
            if shared_key not in updates:
                continue
            value = st.session_state.get(shared_key)
            st.session_state[widget_key] = value
            st.session_state[f"_cached_{widget_key}"] = value
            if isinstance(hydrated_map, dict):
                hydrated_map[widget_key] = value
    st.session_state["_apply_resolved_candidate_widget_refresh_debug"] = {
        "updated_keys": sorted(str(k) for k in updates.keys()),
        "cleared_widget_keys": sorted(str(k) for k in cleared_widget_keys),
        "source": "guidance:apply_resolved_candidate",
    }
    try:
        derive_design_actions()
    except Exception:
        pass
    _clear_legacy_auto_design_request_flags(clear_invoke=False)
    try:
        _debug_log_design_guide_consistency(
            source="guidance:apply_resolved_candidate",
            applied_candidate=applied_candidate,
        )
    except Exception:
        pass
    post_apply_candidate = evaluate_candidate_full(
        _guidance_state_snapshot(_shared_state_snapshot()),
        source="guidance:apply_resolved_candidate:post_apply_live",
        label=label,
        action_type="apply_resolved_candidate",
        updates=updates,
    )
    if isinstance(post_apply_candidate, dict):
        post_apply_candidate = dict(post_apply_candidate)
        post_apply_candidate["label"] = label
        post_apply_candidate["updates"] = dict(updates)
        post_apply_candidate["recommendation_family_tag"] = family_tag
        post_apply_candidate["subfamilies"] = list(subfamilies)
        post_apply_candidate["guidance_change_lines"] = list(change_lines)
        post_overview = dict(post_apply_candidate.get("overview") or {})
        if bool(post_overview.get("all_key_pass")) and not bool(post_overview.get("any_fail")):
            try:
                st.session_state["_design_guide_post_cleanup_acceptance_fp"] = (
                    _local_cleanup_acceptance_fingerprint(_shared_state_snapshot())
                )
                _DESIGN_GUIDE_POST_CLEANUP_ACCEPTED_FPS.add(
                    st.session_state["_design_guide_post_cleanup_acceptance_fp"]
                )
                st.session_state["_design_guide_post_cleanup_acceptance_enabled"] = True
            except Exception:
                pass

    st.session_state[DESIGN_GUIDE_LAST_APPLY_ROUTE_KEY] = {
        "apply_used_resolved_candidate_payload": True,
        "apply_fell_back_to_generic_solver": False,
        "apply_fallback_reason": None,
        "apply_direct_resolved_candidate": True,
        "resolved_candidate_label": label,
        "resolved_candidate_action_type": original_action_type,
        "resolved_candidate_family_tag": family_tag,
        "resolved_candidate_subfamilies": subfamilies,
        "expected_post_util": expected_post_util,
        "one_click_candidate_available_at_step_start": True,
        "one_click_candidate_label_at_step_start": one_click_label_at_step_start,
        "post_apply_resolved_candidate_attempted": True,
        "post_apply_resolved_candidate_label": label,
        "post_apply_resolved_candidate_expected_util": expected_post_util,
    }

    applied_candidate_record = {
        "label": label,
        "updates": dict(updates),
        "recommendation_family_tag": family_tag,
        "subfamilies": list(subfamilies),
        "guidance_change_lines": list(change_lines),
    }
    try:
        _finalize_design_guide_apply_step_history(
            prior_state=prior_state,
            source="guidance:apply_resolved_candidate",
            applied_candidate=applied_candidate_record,
        )
    except Exception:
        pass
    try:
        _store_design_guide_apply_banner_payload(prior_state, _shared_state_snapshot())
        _record_design_guide_auto_geometry_applied(prior_state, updates)
    except Exception:
        pass
    st.session_state[DESIGN_GUIDE_PANEL_BASELINE_FP_KEY] = _design_guide_cache_fingerprint(
        _shared_state_snapshot(),
    )
    st.session_state.pop(DESIGN_GUIDE_NEEDS_REFRESH_KEY, None)
    _invalidate_design_guide_caches(
        reason="guidance:apply_resolved_candidate",
        updated_keys=list(updates.keys()),
        preserve_apply_banner=True,
    )
    finalize_auto_design_publish(
        updated_keys=sorted(list(updates.keys())),
        source="guidance:apply_resolved_candidate",
        focus_section="shear" if any(k in {"lig_d", "lig_legs", "s_lig"} for k in updates.keys()) else "model",
        set_run_design_clicked=True,
    )
    try:
        persist_active_beam_from_shared()
    except Exception:
        pass
    try:
        persist_state_snapshot()
    except Exception:
        pass
    after_state = _shared_state_snapshot()
    derived_mirror_keys = {
        "Ast_bot",
        "bot_entry",
        "db_bot",
        "nb_bot",
        "s_bot",
        "s_top",
        "total_bot_bars",
    }
    actual_changed_updates = {
        str(key): after_state.get(key)
        for key in sorted(set(str(k) for k in prior_state.keys()) | set(str(k) for k in after_state.keys()))
        if str(prior_state.get(key)) != str(after_state.get(key))
        and (str(key) in set(str(k) for k in updates.keys()) or str(key) not in derived_mirror_keys)
    }
    stale_changed_keys = sorted(
        key for key in actual_changed_updates.keys()
        if key not in set(str(k) for k in updates.keys()) and key not in derived_mirror_keys
    )
    _set_design_guide_primary_payload_binding_audit(
        queued_apply_candidate_id=candidate_id,
        queued_apply_updates=dict(updates),
        applied_candidate_id=candidate_id,
        applied_updates=dict(updates),
        applied_changed_keys=sorted(str(k) for k in actual_changed_updates.keys()),
        actual_changed_updates=dict(actual_changed_updates),
        stale_candidate_changed_keys=list(stale_changed_keys),
        stale_apply_payload_blocked=False,
        canonical_primary_payload_exists=bool(st.session_state.get(DESIGN_GUIDE_PRIMARY_APPLY_PAYLOAD_KEY)),
        legacy_fallback_used=False,
    )
    last_route = dict(st.session_state.get(DESIGN_GUIDE_LAST_APPLY_ROUTE_KEY) or {})
    last_route.update(
        {
            "queued_apply_candidate_id": candidate_id,
            "applied_candidate_id": candidate_id,
            "queued_apply_updates": dict(updates),
            "applied_updates": dict(updates),
            "applied_changed_keys": sorted(str(k) for k in actual_changed_updates.keys()),
            "actual_changed_updates": dict(actual_changed_updates),
            "stale_candidate_changed_keys": list(stale_changed_keys),
            "payload_binding_match": bool(
                st.session_state.get(DESIGN_GUIDE_PRIMARY_PAYLOAD_BINDING_AUDIT_KEY, {}).get("payload_binding_match")
            ),
            "payload_update_match": bool(
                st.session_state.get(DESIGN_GUIDE_PRIMARY_PAYLOAD_BINDING_AUDIT_KEY, {}).get("payload_update_match")
            ),
            "stale_apply_payload_blocked": False,
            "legacy_fallback_used": False,
        }
    )
    st.session_state[DESIGN_GUIDE_LAST_APPLY_ROUTE_KEY] = last_route
    _emit_design_guide_apply_trace_run_end(
        stop_reason="applied_recommendation",
        final_updates=dict(updates),
        winner_label=label,
    )

    st.rerun()
    return True


