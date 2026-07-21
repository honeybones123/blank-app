"""Resolved summary-state coordination for the Inputs page."""

from __future__ import annotations

from typing import Any


_SUMMARY_STATE_RESOLVER_DEPENDENCIES: tuple[str, ...] = (
    "INPUTS_PAGE_TAB_KEYS",
    "_SHEAR_TRIPLE_DEFERRED_OVERLAY_KEYS",
    "_SUMMARY_OVERLAY_SKIP_LONGITUDINAL_KEYS",
    "_SUMMARY_OVERLAY_SKIP_PREFIXES",
    "_SUMMARY_OVERLAY_SKIP_SHARED_KEYS",
    "_apply_active_page_shear_widget_mirror_overlay_for_app_bridge",
    "_build_legacy_longitudinal_mirrors_from_rows_for_app_bridge",
    "_get_design_guide_fp",
    "_guidance_state_snapshot_for_summary_bridge",
    "_inputs_summary_should_use_shared_only_for_app_bridge",
    "_overlay_current_design_action_results_for_summary_for_app_bridge",
    "_overlay_current_normalized_shear_truth_for_app_bridge",
    "_recompute_summary_local_derived_fields_for_app_bridge",
    "_shared_state_snapshot_for_summary_bridge",
    "build_inputs_summary_debug_payload_snapshot",
    "build_inputs_summary_source_shaping_snapshot",
    "build_inputs_summary_state_mode_marker_snapshot",
    "st",
    "stable_fingerprint_for_payload",
    "ux_probe_record",
)


def bind_summary_state_resolver_dependencies(namespace: dict[str, Any]) -> None:
    globals().update(
        {
            name: namespace[name]
            for name in _SUMMARY_STATE_RESOLVER_DEPENDENCIES
            if name in namespace
        }
    )


def _resolved_inputs_summary_state() -> tuple[dict, dict]:
    base = _guidance_state_snapshot_for_summary_bridge(_shared_state_snapshot_for_summary_bridge())
    shared_only_mode, shared_only_reason = _inputs_summary_should_use_shared_only_for_app_bridge()
    summary_source_shape = build_inputs_summary_source_shaping_snapshot(
        base_state=base,
        source_state=st.session_state,
        input_tab_keys=INPUTS_PAGE_TAB_KEYS,
        skip_shared_keys=_SUMMARY_OVERLAY_SKIP_SHARED_KEYS,
        skip_longitudinal_keys=_SUMMARY_OVERLAY_SKIP_LONGITUDINAL_KEYS,
        skip_prefixes=_SUMMARY_OVERLAY_SKIP_PREFIXES,
        deferred_overlay_keys=_SHEAR_TRIPLE_DEFERRED_OVERLAY_KEYS,
        shared_only_mode=shared_only_mode,
        shared_only_reason=shared_only_reason,
    )
    working = dict(summary_source_shape.working_state)
    overlay_applied: dict[str, dict] = dict(summary_source_shape.overlay_applied)
    ux_probe_record(
        "inputs_summary_source_shaping_delegated",
        meta={
            "module_display_hash": summary_source_shape.display_hash,
            "live_page_cutover": True,
        },
    )

    if shared_only_mode:
        shear_overlay_debug = {
            "shear_widget_overlay_applied": False,
            "shear_widget_overlay_source": "shared_only_suppressed",
            "overlay_s_lig": working.get("s_lig"),
            "overlay_lig_d": working.get("lig_d"),
            "overlay_lig_legs": working.get("lig_legs"),
        }
    else:
        shear_overlay_debug = _apply_active_page_shear_widget_mirror_overlay_for_app_bridge(
            working,
            base,
            overlay_applied,
        )
    design_action_result_overlay = (
        _overlay_current_design_action_results_for_summary_for_app_bridge(
            working,
            overlay_applied,
            source_state=st.session_state,
        )
    )
    working.update(_build_legacy_longitudinal_mirrors_from_rows_for_app_bridge(working))
    resolved = _recompute_summary_local_derived_fields_for_app_bridge(working)
    resolved.update(_build_legacy_longitudinal_mirrors_from_rows_for_app_bridge(resolved))
    resolved = _overlay_current_normalized_shear_truth_for_app_bridge(resolved)

    subset_keys = (
        "b",
        "D",
        "fc",
        "fsy",
        "uls_Mstar",
        "Mu_star",
        "uls_Vstar",
        "Vu_star",
        "Tu_star",
        "bot1_count",
        "bot2_count",
        "db_bot_1",
        "db_bot_2",
        "lig_d",
        "lig_legs",
        "s_lig",
        "Ast_bot",
        "d",
    )
    summary_debug_snapshot = build_inputs_summary_debug_payload_snapshot(
        base_state=base,
        resolved_state=resolved,
        overlay_applied=overlay_applied,
        shear_overlay_debug=shear_overlay_debug,
        design_action_result_overlay=design_action_result_overlay,
        shared_only_mode=shared_only_mode,
        shared_only_reason=shared_only_reason,
        design_guide_fingerprint=_get_design_guide_fp(resolved),
        subset_keys=subset_keys,
    )
    debug_payload = dict(summary_debug_snapshot.debug_payload)
    debug_payload["summary_design_action_result_overlay_count"] = len(design_action_result_overlay)
    debug_payload["summary_design_action_result_overlay_keys"] = list(
        design_action_result_overlay.keys()
    )
    debug_payload["row_model_legacy_sync_applied"] = bool(
        resolved.get("row_model_legacy_sync_applied")
    )
    debug_payload["row_model_legacy_sync_diff_keys"] = list(
        resolved.get("row_model_legacy_sync_diff_keys") or []
    )
    ux_probe_record(
        "inputs_summary_debug_payload_delegated",
        meta={
            "module_display_hash": summary_debug_snapshot.display_hash,
            "live_page_cutover": True,
        },
    )
    summary_state_mode_marker = build_inputs_summary_state_mode_marker_snapshot(
        base_state=base,
        widget_shear_state={
            "inputs_s_lig": st.session_state.get("inputs_s_lig"),
            "inputs_lig_d": st.session_state.get("inputs_lig_d"),
            "inputs_lig_legs": st.session_state.get("inputs_lig_legs"),
        },
        shared_only_mode=shared_only_mode,
        shared_only_reason=shared_only_reason,
        overlay_count=len(overlay_applied),
    )
    st.session_state["_inputs_summary_state_mode"] = dict(
        summary_state_mode_marker.marker_payload
    )
    ux_probe_record(
        "inputs_summary_state_mode_marker_delegated",
        meta={
            "module_display_hash": summary_state_mode_marker.display_hash,
            "live_page_cutover": True,
        },
    )
    ux_probe_record(
        "inputs_page.summary_state_build",
        fingerprint=stable_fingerprint_for_payload(resolved),
        meta={
            "shared_only_mode": bool(shared_only_mode),
            "overlay_count": len(overlay_applied),
        },
    )
    return resolved, debug_payload
