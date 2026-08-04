"""Design Guide Apply trace run-end coordination."""

from __future__ import annotations

from typing import Any


_APPLY_TRACE_RUN_END_DEPENDENCIES: tuple[str, ...] = (
    "DESIGN_GUIDE_APPLY_TRACE_META_KEY",
    "DESIGN_GUIDE_APPLY_TRACE_RUN_ID_KEY",
    "DESIGN_GUIDE_LAST_APPLY_ROUTE_KEY",
    "DESIGN_GUIDE_POST_CLEANUP_ACCEPTED_FPS",
    "DESIGN_GUIDE_PRIMARY_PAYLOAD_BINDING_AUDIT_KEY",
    "_append_design_guide_trace",
    "_build_design_actions_context_for_app_bridge",
    "_collect_design_overview",
    "_design_guide_trace_compare_meta",
    "_guidance_state_snapshot",
    "_local_cleanup_acceptance_fingerprint",
    "_new_design_guide_trace_run_id",
    "_overlay_current_normalized_shear_truth_for_app_bridge",
    "_recompute_summary_local_derived_fields_for_app_bridge",
    "_shared_state_snapshot",
    "_trace_compact_overview_dict",
    "_trace_compact_shared_geom_reo",
    "build_inputs_design_guide_apply_trace_run_end_meta_plan",
    "build_inputs_design_guide_apply_trace_run_end_outcome",
    "build_legacy_longitudinal_mirrors_from_rows",
    "st",
)


def bind_apply_trace_run_end_dependencies(namespace: dict[str, Any]) -> None:
    globals().update(
        {
            name: namespace[name]
            for name in _APPLY_TRACE_RUN_END_DEPENDENCIES
            if name in namespace
        }
    )


def _emit_design_guide_apply_trace_run_end(
    *,
    stop_reason: str,
    final_updates: dict | None = None,
    winner_label: str | None = None,
    final_util_override: float | None = None,
    final_statuses_override: dict | None = None,
) -> None:
    run_id = st.session_state.pop(DESIGN_GUIDE_APPLY_TRACE_RUN_ID_KEY, None)
    meta = st.session_state.pop(DESIGN_GUIDE_APPLY_TRACE_META_KEY, None)
    meta_plan = build_inputs_design_guide_apply_trace_run_end_meta_plan(
        run_id=run_id,
        meta=meta,
        recovered_run_id=_new_design_guide_trace_run_id("dgapply_recovered"),
        winner_label=winner_label or "Apply recommendation",
    )
    run_id = meta_plan.run_id
    meta_d = dict(meta_plan.meta)
    current_state = _shared_state_snapshot()
    current_overview = _collect_design_overview(
        current_state,
        context=_build_design_actions_context_for_app_bridge(current_state),
    )
    try:
        trace_state = _guidance_state_snapshot(current_state)
        trace_state.update(build_legacy_longitudinal_mirrors_from_rows(trace_state))
        trace_state = _recompute_summary_local_derived_fields_for_app_bridge(trace_state)
        trace_state.update(build_legacy_longitudinal_mirrors_from_rows(trace_state))
        trace_state = _overlay_current_normalized_shear_truth_for_app_bridge(trace_state)
        trace_context = _build_design_actions_context_for_app_bridge(trace_state)
        trace_overview = _collect_design_overview(
            dict(trace_context.get("state") or trace_state),
            context=trace_context,
        )
        if isinstance(trace_overview, dict) and trace_overview:
            current_overview = trace_overview
            current_state = dict(trace_context.get("state") or trace_state)
    except Exception:
        pass
    outcome = build_inputs_design_guide_apply_trace_run_end_outcome(
        current_overview=current_overview,
        final_util_override=final_util_override,
        final_statuses_override=final_statuses_override,
    )
    final_util = outcome.final_util
    statuses = dict(outcome.statuses)
    if bool(final_updates) and not bool((current_overview or {}).get("any_fail")):
        try:
            accepted_fp = _local_cleanup_acceptance_fingerprint(current_state)
            DESIGN_GUIDE_POST_CLEANUP_ACCEPTED_FPS.add(accepted_fp)
            st.session_state["_design_guide_post_cleanup_acceptance_fp"] = accepted_fp
            st.session_state["_design_guide_post_cleanup_acceptance_enabled"] = True
        except Exception:
            pass
    _append_design_guide_trace(
        "run_end",
        {
            "status": "pass" if bool(final_updates) else "no_action",
            "stop_reason": str(stop_reason or "").strip() or "apply_recommendation",
            "final_live_worst_util": final_util,
            "post_commit_live_worst_util": final_util,
            "post_commit_live_statuses": statuses,
            "all_key_pass": bool((current_overview or {}).get("all_key_pass")),
            "current_shared_compact": _trace_compact_shared_geom_reo(current_state),
            "current_overview": _trace_compact_overview_dict(current_overview),
            "primary_payload_binding_audit": dict(
                st.session_state.get(DESIGN_GUIDE_PRIMARY_PAYLOAD_BINDING_AUDIT_KEY) or {}
            ),
            "last_apply_route": dict(st.session_state.get(DESIGN_GUIDE_LAST_APPLY_ROUTE_KEY) or {}),
            "compare": _design_guide_trace_compare_meta(
                run_id=str(run_id),
                action_signature=str(meta_d.get("action_type") or "") or None,
                goal="design_guide_apply",
                starting_worst_util=meta_d.get("starting_worst_util"),
                ending_worst_util=final_util,
                stop_reason=str(stop_reason or "").strip() or "apply_recommendation",
                winner_label=winner_label or str(meta_d.get("title") or "").strip() or None,
                final_updates=dict(final_updates or {}),
            ),
        },
        run_id=str(run_id),
        source=str(meta_d.get("source") or "design_guide_apply"),
    )


__all__ = [
    "bind_apply_trace_run_end_dependencies",
    "_emit_design_guide_apply_trace_run_end",
]
