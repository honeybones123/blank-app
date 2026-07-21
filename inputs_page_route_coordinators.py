"""Temporary route-coordinator bridge for the live Inputs shell.

The shell is the routed Inputs page. These functions still live in
``inputs_page.py`` while their remaining dependencies are being moved. Keeping
the bridge explicit makes the final old-page deletion dependency visible.
"""

from __future__ import annotations

import copy
import html
import os
import json
import sys
import time
from datetime import datetime
from typing import Any

import streamlit as st

import inputs_page_app_contract_bridge as _legacy_inputs_page
from bending_checks_helpers import build_bending_check_rows_from_state
from batch_design.ui.project_beam_manager_adapters import (
    beam_option_labels as build_batch_beam_option_labels,
    build_beam_schedule_df as build_batch_beam_schedule_df,
    build_schedule_export_df as build_batch_schedule_export_df,
    build_schedule_preview_df as build_batch_schedule_preview_df,
    format_beam_status_badge as format_batch_beam_status_badge,
    format_last_checked as format_batch_last_checked,
    sync_beam_records_from_schedule_df as sync_batch_beam_records_from_schedule_df,
)
from batch_design.design_brain_adapter import BatchDesignGuidanceAdapter
from batch_design.ui.page import BatchDesignPageContext, render_batch_design_page
from crack_checks_helpers import build_crack_check_rows_from_state, pick_governing_check_row
from deflection_checks_helpers import build_deflection_check_rows_from_state
from design_brain.config import (
    DESIGN_OPTIMISATION_GOAL_LABELS,
    resolve_design_optimisation_goal,
)
from engineering_check_ui import BENDING_ROW_UID_TO_TAB, SHEAR_ROW_UID_TO_TAB
from inputs_page_app_contract_bridge import (
    _apply_canonical_convenience_resync_to_shared_for_app_bridge,
    _build_canonical_design_state_pack_for_app_bridge,
    _compute_design_guidance_items,
    _get_design_guide_fp,
    _resolved_inputs_summary_state,
)
from inputs_page_modules.calculations import (
    render_inputs_calculation_explainer_trace as render_inputs_calculation_explainer_trace_module,
)
from inputs_page_modules.diagrams import (
    InputsDiagramSourceSnapshot,
    build_inputs_diagram_view_model,
    render_inputs_3d_diagram_block,
    render_inputs_fast_model_block,
    render_inputs_section_2d_diagram_block,
)
from inputs_page_modules.diagrams.source_projection import (
    build_section_outline_points_and_bbox as build_section_outline_points_and_bbox_module,
)
from inputs_page_modules.design_guide import render_design_guide_panel_orchestration
from inputs_page_modules.design_guide.debug_sidebar import render_design_guide_debug_sidebar
from inputs_page_modules.design_guide.trace import (
    append_design_guide_trace as append_design_guide_trace_module,
    design_guide_tracer_path as design_guide_tracer_path_module,
    design_guide_tracer_verbose_log as design_guide_tracer_verbose_log_module,
)
from inputs_page_modules.design_guide.state_projection import (
    build_auto_design_governing_fingerprint as build_auto_design_governing_fingerprint_module,
    build_guidance_state_snapshot as build_guidance_state_snapshot_module,
)
from inputs_page_modules.session import (
    build_inputs_auto_design_invoke_debug_snapshot,
    build_inputs_design_guide_cached_debug_trust_decision,
    build_inputs_design_guide_dirty_mark_plan,
    build_inputs_design_guide_guidance_cache_result,
    build_inputs_design_guide_guidance_cache_write_plan,
    build_inputs_design_guide_transient_ui_clear_plan,
    build_inputs_model_reo_widget_mirror_overlay_plan,
    build_inputs_model_state_debug_payload_snapshot,
    build_inputs_rerun_trigger_record_plan,
    build_inputs_session_source_snapshot,
    render_inputs_dev_session_debug_sidebar as render_inputs_dev_session_debug_sidebar_module,
)
from inputs_page_modules.session.startup_hydration import render_inputs_startup_hydration as render_inputs_startup_hydration_module
from inputs_page_modules.session.longitudinal_reo_widget_sync import (
    is_inputs_longitudinal_reo_widget_key as is_inputs_longitudinal_reo_widget_key_module,
    longitudinal_reo_widget_audit_snapshot as longitudinal_reo_widget_audit_snapshot_module,
    reseed_inputs_longitudinal_reo_widgets_from_shared as reseed_inputs_longitudinal_reo_widgets_from_shared_module,
)
from inputs_page_modules.auto_design_routing import handle_inputs_auto_design
from inputs_page_modules.apply_routing import handle_inputs_apply_buttons
from inputs_page_modules.landing import (
    inputs_show_landing_dashboard,
    render_landing_card,
)
from inputs_page_modules.performance import (
    render_inputs_perf_finalization_current_coordinator,
    render_inputs_perf_marker_setup_coordinator,
)
from inputs_page_modules.page_styles import apply_inputs_page_css
from inputs_page_modules.tail import (
    render_inputs_debug_audit as render_inputs_debug_audit_module,
    render_inputs_post_summary_actions_and_dev_audit as render_inputs_post_summary_actions_and_dev_audit_module,
    render_inputs_tail as render_inputs_tail_module,
)
from inputs_page_modules.recommendation_panels import (
    render_bottom_recommendation_panel,
    render_geometry_recommendation_panel,
    render_shear_recommendation_panel,
)
from inputs_page_modules.summaries import render_inputs_summary_expanders_and_tables_current_coordinator
from inputs_page_modules.summaries.render_coordinators import render_inputs_summary_container_current as render_inputs_summary_container_current_module
from inputs_page_modules.summaries.display_state import render_inputs_summary_display_state as render_inputs_summary_display_state_module
from inputs_page_modules.summaries.pipeline import render_inputs_summary_pipeline as render_inputs_summary_pipeline_module
from inputs_page_modules.summaries.rows_from_packs import render_inputs_summary_rows_from_packs as render_inputs_summary_rows_from_packs_module
from inputs_page_modules.summaries.state_cache import render_inputs_summary_state_cache as render_inputs_summary_state_cache_module
from inputs_page_modules.widgets.render_coordinators import (
    render_inputs_bottom_reinforcement_column as render_inputs_bottom_reinforcement_column_module,
    render_inputs_detailed_support_lower_row as render_inputs_detailed_support_lower_row_module,
    render_inputs_design_actions_section as render_inputs_design_actions_section_module,
    render_inputs_flange_reinforcement as render_inputs_flange_reinforcement_module,
    render_inputs_geometry_materials_top_section as render_inputs_geometry_materials_top_section_module,
    render_inputs_materials_and_section_2d as render_inputs_materials_and_section_2d_module,
    render_inputs_shear_reinforcement_column as render_inputs_shear_reinforcement_column_module,
    render_inputs_top_reinforcement_column as render_inputs_top_reinforcement_column_module,
    render_inputs_widget_sections as render_inputs_widget_sections_module,
)
from inputs_page_modules.widgets.model_reo_overlay import (
    overlay_inputs_reo_widget_mirrors_for_model as overlay_inputs_reo_widget_mirrors_for_model_module,
)
from inputs_page_modules.widgets.shear_widget_seed import (
    request_shear_widget_seed_from_shared as request_shear_widget_seed_from_shared_module,
)
from inputs_page_modules.widgets.design_action_sync import (
    commit_design_action_widgets_to_shared as commit_design_action_widgets_to_shared_module,
    debug_check_design_action_consistency as debug_check_design_action_consistency_module,
    design_action_widget_specs as design_action_widget_specs_module,
    hydrate_design_action_widgets_from_shared as hydrate_design_action_widgets_from_shared_module,
    make_design_action_widget_callback as make_design_action_widget_callback_module,
    mirror_design_action_proxies_from_shared as mirror_design_action_proxies_from_shared_module,
    reconcile_design_action_widgets_with_shared as reconcile_design_action_widgets_with_shared_module,
    render_design_action_number_row as render_design_action_number_row_module,
    sync_design_action_widget_to_shared as sync_design_action_widget_to_shared_module,
)
from state_and_helpers import (
    DEFLECTION_LIMIT_HELP_TEXT,
    DEFLECTION_LIMIT_OPTIONS,
    RESULT_KEYS,
    SHARED_DEFAULTS,
    TAB_KEYS,
    _invalidate_inputs_summary_packs,
    _write_sync_trace_line,
    add_new_beam_record,
    delete_beam_record,
    duplicate_active_beam_record,
    ensure_beam_project_initialized,
    get_sync_callbacks,
    get_active_beam_summary,
    get_deflection_limit_label_from_ratio,
    get_deflection_limit_ratio,
    get_param,
    get_widget_key_for_shared,
    build_legacy_longitudinal_mirrors_from_rows,
    hc_log as _state_hc_log,
    hc_try,
    hydrate_active_page_widgets_from_shared,
    init_shared_session_state,
    is_design_governing,
    load_active_beam_into_shared,
    mark_user_edit,
    persist_active_beam_from_shared,
    persist_state_snapshot,
    publish_normalized_final_shear_truth_to_session,
    reset_app_to_clean_starter_workspace,
    resolve_design_actions,
    set_active_beam,
    set_shared,
    speed_profiled,
    update_active_beam_summary_from_results,
)
from shear_checks_helpers import build_shear_check_rows_from_state
from section_layout import compute_section_layout
from section_props.plotly_3d import make_section_3d_figure
from section_props.plotly_section import make_sectionA_figure
from ui.diagrams.inputs_3d_diagram import build_inputs_beam_3d_figure
from ui.diagrams.section_diagram import build_summary_cross_section_result
from widgets_helpers import (
    _register_rendered_key,
    apply_calcbox_css,
    apply_global_widget_css,
    info_i_button,
    label_with_hover,
    main_longitudinal_reo_pair_labels,
    normalized_sec_shape_ui,
    number_row,
    page_divider,
    render_longitudinal_reo_row_config_controls,
    render_longitudinal_reo_rows,
    seed_widget_from_shared,
    select_row,
    v2_radio,
)


RESULT_CACHE_KEY = "cached_results"
DESIGN_GUIDE_SIDEBAR_DEBUG_TOGGLE_KEY = "inputs_design_guide_debug_sidebar_v1"
DESIGN_GUIDE_DEBUG_BUNDLE_KEY = "_design_guide_debug_bundle"
DESIGN_GUIDE_RECO_TRACE_KEY = "_design_guide_reco_trace"
DESIGN_GUIDE_RANK_TRACE_KEY = "_design_guide_rank_trace"
DESIGN_GUIDE_APPLY_BANNER_KEY = "_design_guide_apply_banner_payload"
DESIGN_GUIDE_APPLY_BANNER_META_KEY = "_design_guide_apply_banner_meta"
DESIGN_GUIDE_STEP_HISTORY_KEY = "_design_guide_step_history"
DESIGN_GUIDE_FIRST_TARGET_BAND_STEP_KEY = "_design_guide_first_target_band_step"
DESIGN_GUIDE_HISTORY_ANCHOR_KEY = "_design_guide_history_anchor"
DESIGN_GUIDE_PENDING_STEP_CTX_KEY = "_design_guide_pending_step_ctx"
DESIGN_GUIDE_GUIDANCE_CACHE_FP_KEY = "_design_guide_cached_fingerprint"
DESIGN_GUIDE_GUIDANCE_CACHE_ITEMS_KEY = "_design_guide_cached_items"
DESIGN_GUIDE_GUIDANCE_CACHE_DEBUG_KEY = "_design_guide_cached_debug"
DESIGN_GUIDE_SIMPLE_CACHE_FP_KEY = "_design_guide_fp"
DESIGN_GUIDE_SIMPLE_CACHE_ITEMS_KEY = "_design_guide_cache"
DESIGN_GUIDE_NEEDS_REFRESH_KEY = "_design_guide_needs_refresh"
_INPUTS_SCROLL_DESIGN_ACTIONS_FLAG = "_inputs_pending_scroll_design_actions"
_INPUTS_PENDING_NAV_PAGE_SLUG_KEY = "_pending_nav_page_slug"
_INPUTS_DESIGN_ACTIONS_ANCHOR_ID = "inputs_design_actions_anchor"
AUTO_DESIGN_AUTO_INVOKE_KEY = "_auto_design_auto_invoke"
AUTO_DESIGN_REQUEST_TS_KEY = "_auto_design_requested_at_ts"
AUTO_DESIGN_REQUEST_SOURCE_KEY = "_auto_design_request_source"
INPUTS_PAGE_TAB_KEYS = {sk: wk for wk, sk in TAB_KEYS.items() if str(wk).startswith("inputs_")}
_INPUTS_DEBUG_AUDIT = os.environ.get("INPUTS_DEBUG_AUDIT", "").strip().lower() in (
    "1",
    "true",
    "yes",
    "on",
)
_AGENT_DEBUG_LOG_PATH = "/Users/jonathonleggo/Library/CloudStorage/OneDrive-Personal/Documents/GitHub/complete-app/.cursor/debug.log"
REO_BAR_DIAS = [10, 12, 16, 20, 24, 28, 32, 36, 40]
REO_COUNTS_0_12 = list(range(0, 13))
REO_SPACINGS = [75, 100, 125, 150, 175, 200, 225, 250, 275, 300]
REO_LAYOUT_MODE = ["Count", "Spacing"]
K_D_OPTIONS = [
    "None (no ducts in web)",
    "Prestressing ducts present (apply k_d)",
]
K_V_METHOD_OPTIONS = [
    "General εx-based (Cl. 8.2.4.2)",
    "Simplified non-prestressed (Cl. 8.2.4.3)",
]
PRIMARY_GEOMETRY_KEYS = {
    "sec_shape",
    "b",
    "D",
    "bf",
    "tf",
    "bw",
    "tw",
    "bf_bot",
    "tf_bot",
}
MODEL_RENDER_FINGERPRINT_KEYS = PRIMARY_GEOMETRY_KEYS | {
    "cover_top",
    "cover_bot",
    "cover_side",
    "rowgap_top",
    "rowgap_bot",
    "bot_row_count",
    "bot1_count",
    "db_bot_1",
    "bot2_count",
    "db_bot_2",
    "top_row_count",
    "top1_count",
    "db_top_1",
    "top2_count",
    "db_top_2",
    "lig_d",
    "lig_legs",
    "s_lig",
}


def log_debug(message, value=None):
    print(f"[INPUTS DEBUG] {message}: {value}")


def render_inputs_initial_session_state_coordinator(*, ss: dict) -> None:
    init_shared_session_state()
    if RESULT_CACHE_KEY not in ss:
        ss[RESULT_CACHE_KEY] = None


def inputs_hydration_trace_log(phase: str, **extra: object) -> None:
    """Preserve the current legacy-inert hydration trace behavior."""

    _ = phase
    _ = extra


def _agent_debug_log(
    message: str,
    data: dict | None = None,
    *,
    location: str,
    hypothesis_id: str,
    run_id: str = "auto_design_debug",
) -> None:
    try:
        timestamp = int(datetime.now().timestamp() * 1000)
        payload = {
            "id": f"log_{timestamp}_{hypothesis_id}",
            "timestamp": timestamp,
            "location": location,
            "message": message,
            "data": data or {},
            "runId": run_id,
            "hypothesisId": hypothesis_id,
        }
        with open(_AGENT_DEBUG_LOG_PATH, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, default=str) + "\n")
    except Exception:
        pass


def _is_inputs_longitudinal_reo_widget_key(widget_key: str | None) -> bool:
    return is_inputs_longitudinal_reo_widget_key_module(widget_key)


def _longitudinal_reo_widget_audit_snapshot(label: str) -> dict:
    return longitudinal_reo_widget_audit_snapshot_module(
        state=st.session_state,
        label=label,
        copy_deepcopy_fn=copy.deepcopy,
        agent_debug_log_fn=_agent_debug_log,
    )


def _reseed_inputs_longitudinal_reo_widgets_from_shared(reason: str, *, force: bool = False) -> dict:
    return reseed_inputs_longitudinal_reo_widgets_from_shared_module(
        state=st.session_state,
        reason=reason,
        force=force,
        time_time_fn=time.time,
        copy_deepcopy_fn=copy.deepcopy,
        is_longitudinal_widget_key_fn=_is_inputs_longitudinal_reo_widget_key,
        agent_debug_log_fn=_agent_debug_log,
    )


def _request_shear_widget_seed_from_shared(reason: str) -> dict:
    return request_shear_widget_seed_from_shared_module(
        state=st.session_state,
        reason=reason,
        agent_debug_log_fn=_agent_debug_log,
    )


def _force_inputs_apply_refresh_cycle(reason: str) -> dict:
    _longitudinal_reo_widget_audit_snapshot("before_inputs_hydrate")
    hydrate_active_page_widgets_from_shared("inputs", force_on_page_change=True)
    _longitudinal_reo_widget_audit_snapshot("after_inputs_hydrate")
    longitudinal_payload = _reseed_inputs_longitudinal_reo_widgets_from_shared(reason, force=True)
    shear_payload = _request_shear_widget_seed_from_shared(reason)
    _longitudinal_reo_widget_audit_snapshot("after_inputs_longitudinal_reseed")
    st.session_state["_inputs_longitudinal_reo_force_refresh_reason"] = str(reason or "")
    st.session_state["_inputs_longitudinal_reo_force_refresh_processed_this_run"] = True
    st.session_state["_inputs_shear_force_refresh_processed_this_run"] = True
    combined_payload = {
        "reason": str(reason or ""),
        "longitudinal_payload": longitudinal_payload,
        "shear_payload": shear_payload,
    }
    st.session_state["_inputs_apply_refresh_cycle_latest"] = dict(combined_payload)
    return combined_payload


def render_inputs_param_snapshot_coordinator():
    params = {key: st.session_state.get(key) for key in st.session_state.keys()}

    def fast_get_param(key, default=None):
        return params.get(key, default)

    return params, fast_get_param


def render_inputs_page_load_start_coordinator(*, ss: dict) -> float:
    if _INPUTS_DEBUG_AUDIT:
        log_debug("---- INPUTS PAGE LOAD START ----")
        for key in SHARED_DEFAULTS.keys():
            log_debug(f"SHARED INIT - {key}", st.session_state.get(key))
        for shared_key, tab_key in INPUTS_PAGE_TAB_KEYS.items():
            log_debug(f"TAB INIT - {shared_key} <- {tab_key}", st.session_state.get(tab_key))

    _write_sync_trace_line("\n=== PAGE RENDER: inputs ===")
    render_started_at = time.perf_counter()

    ensure_beam_project_initialized()
    if ss.get("_beam_skip_auto_persist_once") is None:
        ss["_beam_skip_auto_persist_once"] = False
    return render_started_at


def _inputs_final_log_append(name, payload) -> None:
    import session_state_final_log as _ssl

    _ssl.append_session_state_final_log(name, payload)


def _inputs_final_log_increment(name, amount) -> None:
    import session_state_final_log as _ssl

    _ssl.ssl_increment(name, amount)


def _inputs_final_log_set_flag(name, value) -> None:
    import session_state_final_log as _ssl

    _ssl.ssl_set_flag(name, value)


def render_inputs_startup_hydration_coordinator(*, ss: dict, mark) -> None:
    render_inputs_startup_hydration_module(
        ss=ss,
        mark=mark,
        load_active_beam_into_shared_fn=load_active_beam_into_shared,
        apply_canonical_convenience_resync_to_shared_fn=_apply_canonical_convenience_resync_to_shared_for_app_bridge,
        inputs_hydration_trace_log_fn=inputs_hydration_trace_log,
        force_inputs_apply_refresh_cycle_fn=_force_inputs_apply_refresh_cycle,
        agent_debug_log_fn=_agent_debug_log,
        final_log_append_fn=_inputs_final_log_append,
        final_log_increment_fn=_inputs_final_log_increment,
        final_log_set_flag_fn=_inputs_final_log_set_flag,
    )


def _wrap_longitudinal_reo_sync_callbacks(sync_callbacks: dict) -> dict:
    wrapped = dict(sync_callbacks or {})

    def _make_wrapper(widget_key: str, fn):
        def _wrapped_callback():
            fn()
            snapshot = _longitudinal_reo_widget_audit_snapshot(f"after_longitudinal_sync_callback:{widget_key}")
            callback_record = {
                "changed_widget": widget_key,
                "shared_row_model": dict(snapshot.get("shared_row_model") or {}),
                "inputs_widget_mirror": dict(snapshot.get("inputs_widget_mirror") or {}),
                "diff_summary": dict(snapshot.get("diff_summary") or {}),
            }
            callback_store = dict(st.session_state.get("_inputs_longitudinal_reo_callback_audit") or {})
            callback_history = list(callback_store.get("history") or [])
            callback_history.append(copy.deepcopy(callback_record))
            if len(callback_history) > 24:
                callback_history = callback_history[-24:]
            callback_store["latest"] = copy.deepcopy(callback_record)
            callback_store["history"] = callback_history
            st.session_state["_inputs_longitudinal_reo_callback_audit"] = callback_store
            try:
                _agent_debug_log(
                    "Inputs longitudinal reo sync callback audit",
                    callback_record,
                    location="inputs_page.py:_wrap_longitudinal_reo_sync_callbacks",
                    hypothesis_id="H_INPUTS_LONGITUDINAL_WIDGET_CALLBACK",
                )
            except Exception:
                pass
        return _wrapped_callback

    for widget_key, fn in list(wrapped.items()):
        if callable(fn) and _is_inputs_longitudinal_reo_widget_key(widget_key):
            wrapped[widget_key] = _make_wrapper(str(widget_key), fn)
    return wrapped


def _fresh_inputs_render_audit() -> dict[str, str]:
    return {
        "old_auto_design_panel_rendered": "no",
        "design_guide_rendered": "no",
        "current_design_summary_rendered": "no",
        "next_mode_recommendation_rendered": "no",
        "bottom_tightening_rendered": "no",
        "geometry_tightening_rendered": "no",
        "shear_tightening_rendered": "no",
    }


def _render_recommendation_section_header(
    title: str,
    *,
    help_text: str,
    level: str,
    render_popover_content,
    render_popover_always=None,
) -> None:
    title_col, info_col = st.columns([0.92, 0.08], vertical_alignment="center")
    with title_col:
        if level == "h2":
            st.markdown(f"## {title}")
        else:
            st.subheader(title)
    with info_col:
        with info_i_button(help_text=help_text):
            if render_popover_always is not None:
                render_popover_always()
                st.divider()
            load_key = f"_load_recommendation_popover_{title.lower().replace(' ', '_')}"
            load_pressed = st.button(
                "Load recommendation tools",
                key=load_key,
                type="secondary",
                use_container_width=True,
            )
            if load_pressed:
                render_popover_content()
            else:
                st.caption("Load recommendation tools on demand.")


def _render_bottom_recommendation_panel(*, button_key: str, source: str, compact: bool) -> None:
    render_bottom_recommendation_panel(
        st_module=st,
        button_key=button_key,
        source=source,
        compact=compact,
        shared_state_snapshot_fn=_legacy_inputs_page._shared_state_snapshot,
        resolve_popover_recommendation_fn=_legacy_inputs_page._resolve_popover_recommendation,
        compute_bottom_reo_recommendation_fn=_legacy_inputs_page._compute_bottom_reo_recommendation,
        updates_match_state_fn=_legacy_inputs_page._updates_match_state,
        design_optimisation_goal_label_fn=_legacy_inputs_page._design_optimisation_goal_label,
        bottom_reo_state_label_fn=_legacy_inputs_page._bottom_reo_state_label,
        evaluate_bending_with_bottom_state_fn=_legacy_inputs_page._evaluate_bending_with_bottom_state,
        effective_bottom_design_state_fn=_legacy_inputs_page._effective_bottom_design_state,
        apply_bottom_reo_recommendation_fn=_legacy_inputs_page._apply_bottom_reo_recommendation,
    )


def _render_shear_recommendation_panel(*, button_key: str, source: str, compact: bool) -> None:
    render_shear_recommendation_panel(
        st_module=st,
        button_key=button_key,
        source=source,
        compact=compact,
        shared_state_snapshot_fn=_legacy_inputs_page._shared_state_snapshot,
        guidance_state_snapshot_fn=_legacy_inputs_page._guidance_state_snapshot,
        build_shear_check_rows_from_state_fn=build_shear_check_rows_from_state,
        resolve_popover_recommendation_fn=_legacy_inputs_page._resolve_popover_recommendation,
        compute_shear_recommendation_fn=_legacy_inputs_page._compute_shear_recommendation,
        design_optimisation_goal_label_fn=_legacy_inputs_page._design_optimisation_goal_label,
        shear_state_label_fn=_legacy_inputs_page._shear_state_label,
        parse_util_value_fn=_parse_util_value,
        shear_severity_band_fn=_legacy_inputs_page._shear_severity_band,
        updates_match_state_fn=_legacy_inputs_page._updates_match_state,
        severe_shear_failure_fn=_legacy_inputs_page._severe_shear_failure,
        apply_shear_recommendation_fn=_legacy_inputs_page._apply_shear_recommendation,
    )


def _render_geometry_recommendation_panel(*, button_key: str, source: str, compact: bool) -> None:
    render_geometry_recommendation_panel(
        st_module=st,
        button_key=button_key,
        source=source,
        compact=compact,
        shared_state_snapshot_fn=_legacy_inputs_page._shared_state_snapshot,
        resolve_popover_recommendation_fn=_legacy_inputs_page._resolve_popover_recommendation,
        compute_geometry_recommendation_fn=_legacy_inputs_page._compute_geometry_recommendation,
        updates_match_state_fn=_legacy_inputs_page._updates_match_state,
        design_optimisation_goal_label_fn=_legacy_inputs_page._design_optimisation_goal_label,
        resolve_geometry_width_context_fn=_legacy_inputs_page._resolve_geometry_width_context,
        float_from_state_fn=_legacy_inputs_page._float_from_state,
        evaluate_bending_with_bottom_state_fn=_legacy_inputs_page._evaluate_bending_with_bottom_state,
        evaluate_shear_with_state_fn=_legacy_inputs_page._evaluate_shear_with_state,
        apply_geometry_recommendation_fn=_legacy_inputs_page._apply_geometry_recommendation,
    )


def _render_inputs_materials_subsection(sync_callbacks: dict, *, show_heading: bool = True) -> None:
    if show_heading:
        st.subheader("Materials")
    w_fsy = get_widget_key_for_shared("fsy", prefix="inputs_") or "inputs_fsy"
    w_fc = get_widget_key_for_shared("fc", prefix="inputs_") or "inputs_fc"
    fsy_val = float(st.session_state.get(w_fsy, get_param("fsy", 500.0)))
    fc_val = float(st.session_state.get(w_fc, get_param("fc", 40.0)))
    number_row(
        "Steel MPa",
        w_fsy,
        fsy_val,
        sync_callbacks,
        help_text="Yield strength of reinforcement (fsy).",
    )
    number_row(
        "Concrete MPa",
        w_fc,
        fc_val,
        sync_callbacks,
        help_text="Characteristic compressive strength of concrete (f'c).",
    )


def _render_section_2d_diagram_block(*, compact: bool = False, model_state: dict | None = None):
    return render_inputs_section_2d_diagram_block(
        st_module=st,
        compact=compact,
        model_state=model_state,
        time_perf_counter_fn=time.perf_counter,
        inputs_geometry_fingerprint_fn=_inputs_geometry_fingerprint,
        make_summary_cross_section_figure_fn=make_summary_cross_section_figure,
        copy_deepcopy_fn=copy.deepcopy,
        render_plotly_diagram_fn=st.plotly_chart,
    )


def _render_3d_diagram_block(*, compact: bool = False, model_state: dict | None = None):
    return render_inputs_3d_diagram_block(
        st_module=st,
        compact=compact,
        model_state=model_state,
        time_perf_counter_fn=time.perf_counter,
        inputs_geometry_fingerprint_fn=_inputs_geometry_fingerprint,
        copy_deepcopy_fn=copy.deepcopy,
        compute_section_layout_fn=compute_section_layout,
        shared_state_snapshot_fn=_shared_state_snapshot,
        cache_json_fn=_cache_json,
        cached_make_section_3d_figure_fn=cached_make_section_3d_figure,
        make_beam_3d_figure_fn=make_beam_3d_figure,
        render_plotly_diagram_fn=st.plotly_chart,
    )


def _inputs_geometry_fingerprint(state: dict | None = None) -> tuple:
    source = state if isinstance(state, dict) else st.session_state
    return tuple((k, source.get(k)) for k in sorted(MODEL_RENDER_FINGERPRINT_KEYS))


def _inputs_model_reo_widget_keys() -> tuple[str, ...]:
    keys: list[str] = []
    for section in ("bot", "top"):
        keys.append(f"inputs_{section}_row_count")
        for row_index in range(1, 5):
            prefix = f"inputs_{section}_row_{row_index}"
            keys.extend(
                (
                    f"{prefix}_mode",
                    f"{prefix}_bars",
                    f"{prefix}_spacing",
                    f"{prefix}_dia",
                )
            )
    return tuple(keys)


def _overlay_inputs_reo_widget_mirrors_for_model(
    state: dict,
    *,
    summary_debug: dict | None = None,
) -> tuple[dict, dict]:
    widget_values: dict = {}
    for widget_key in _inputs_model_reo_widget_keys():
        if widget_key in st.session_state:
            widget_values[widget_key] = st.session_state.get(widget_key)
    return overlay_inputs_reo_widget_mirrors_for_model_module(
        page_slug=str(st.session_state.get("page_slug", "inputs") or "inputs"),
        state=state,
        summary_debug=summary_debug,
        widget_state=widget_values,
        overlay_plan_fn=build_inputs_model_reo_widget_mirror_overlay_plan,
        build_legacy_longitudinal_mirrors_from_rows_fn=build_legacy_longitudinal_mirrors_from_rows,
        build_canonical_design_state_pack_fn=_build_canonical_design_state_pack_for_app_bridge,
    )


def _resolved_inputs_model_state() -> tuple[dict, dict]:
    resolved, summary_debug = _resolved_inputs_summary_state()
    model_state, model_widget_debug = _overlay_inputs_reo_widget_mirrors_for_model(
        dict(resolved),
        summary_debug=summary_debug,
    )
    debug_snapshot = build_inputs_model_state_debug_payload_snapshot(
        summary_debug=summary_debug,
        model_widget_debug=model_widget_debug,
    )
    return dict(model_state), dict(debug_snapshot.debug_payload)


def _render_with_temporary_model_state(model_state: dict | None, render_fn):
    if not isinstance(model_state, dict) or not model_state:
        return render_fn()
    sentinel = object()
    original_values: dict[str, object] = {}
    try:
        for key, value in model_state.items():
            original_values[key] = st.session_state.get(key, sentinel)
            st.session_state[key] = value
        return render_fn()
    finally:
        for key, value in original_values.items():
            if value is sentinel:
                st.session_state.pop(key, None)
            else:
                st.session_state[key] = value


def _render_fast_model_block(sync_callbacks: dict, model_state: dict | None = None) -> None:
    return render_inputs_fast_model_block(
        st_module=st,
        sync_callbacks=sync_callbacks,
        model_state=model_state,
        shared_toggle_fn=_shared_toggle,
        render_with_temporary_model_state_fn=_render_with_temporary_model_state,
        render_3d_diagram_block_fn=_render_3d_diagram_block,
        render_section_2d_diagram_block_fn=_render_section_2d_diagram_block,
    )


def _caption_inputs_deflection_limit_ratio() -> None:
    """Show active L/Δ ratio and implied δlim next to Inputs deflection limit control."""
    L_mm = float(get_param("L", 3000.0) or 3000.0)
    r = float(get_deflection_limit_ratio(get_param("defl_limit_ratio", 250.0)))
    limit_label = get_deflection_limit_label_from_ratio(r)
    if r <= 0:
        st.caption("Serviceability deflection limit ratio: —")
        return
    lim_mm = L_mm / r
    st.caption(
        f"Serviceability deflection limit ratio: **{limit_label}** → δlim ≈ {lim_mm:.2f} mm (L = {L_mm:.0f} mm)."
    )


def _resolve_inputs_support_and_deflection_defaults() -> dict:
    """Single owner for support/deflection defaults in Inputs page render."""
    from deflection import get_deflection_diagram_support_condition, _deflection_support_options_for_value

    support_resolution = get_deflection_diagram_support_condition(st.session_state)
    support_current = support_resolution["support_type"]
    support_options = _deflection_support_options_for_value(support_current)
    defl_limit_val = get_deflection_limit_ratio(st.session_state.get("defl_limit_ratio", 250.0))
    defl_limit_options_by_ratio = {int(v): str(k) for k, v in DEFLECTION_LIMIT_OPTIONS.items()}
    return {
        "support_current": support_current,
        "support_options": support_options,
        "defl_limit_val": defl_limit_val,
        "defl_limit_options_by_ratio": defl_limit_options_by_ratio,
    }


def _render_materials_and_sectionA_2d(sync_callbacks):
    render_inputs_materials_and_section_2d_module(
        st_module=st,
        sync_callbacks=sync_callbacks,
        get_widget_key_for_shared_fn=get_widget_key_for_shared,
        select_row_fn=select_row,
        is_design_governing_fn=is_design_governing,
        resolve_support_and_deflection_defaults_fn=_resolve_inputs_support_and_deflection_defaults,
        caption_deflection_limit_ratio_fn=_caption_inputs_deflection_limit_ratio,
        number_row_fn=number_row,
        render_3d_diagram_block_fn=_render_3d_diagram_block,
        deflection_limit_help_text=DEFLECTION_LIMIT_HELP_TEXT,
        k_v_method_options=K_V_METHOD_OPTIONS,
    )


def _render_time_dependent_inputs(sync_callbacks):
    st.subheader("Time-dependent inputs")

    t_shrink_val = float(st.session_state.get("inputs_t_shrink", get_param("t_shrink", 365.0)))
    number_row(
        "Shrinkage time t (days)",
        "inputs_t_shrink",
        t_shrink_val,
        sync_callbacks,
        help_text="Time since commencement of drying (days).",
    )

    t_creep_val = float(st.session_state.get("inputs_t_creep", get_param("t_creep", 365.0)))
    number_row(
        "Creep time t (days)",
        "inputs_t_creep",
        t_creep_val,
        sync_callbacks,
        help_text="Time after loading (days).",
    )

    tau_val = float(st.session_state.get("inputs_age_at_loading", get_param("age_at_loading", 28.0)))
    number_row(
        "Age at loading τ (days)",
        "inputs_age_at_loading",
        tau_val,
        sync_callbacks,
        help_text="Age of concrete at loading (days).",
    )


def _render_ducts_prestress_voids_inputs(sync_callbacks):
    st.subheader("Ducts / Prestress voids")

    n_ducts_val = float(st.session_state.get("inputs_n_ducts", get_param("n_ducts", 0.0)))
    duct_dia_val = float(st.session_state.get("inputs_duct_dia", get_param("duct_dia", 0.0)))

    number_row(
        "Number of ducts crossing web",
        "inputs_n_ducts",
        n_ducts_val,
        sync_callbacks,
        help_text="Number of ducts/voids crossing the web (set 0 for none).",
    )

    number_row(
        "Duct diameter (mm)",
        "inputs_duct_dia",
        duct_dia_val,
        sync_callbacks,
        help_text="Nominal duct/void diameter (mm).",
    )

    w_k_d_option = get_widget_key_for_shared("k_d_option", prefix="inputs_") or "inputs_k_d_option"
    k_d_val = st.session_state.get("k_d_option", "None (no ducts in web)")
    select_row(
        "k_d factor for prestressing ducts",
        w_k_d_option,
        K_D_OPTIONS,
        k_d_val,
        sync_callbacks,
        help_text="Select whether ducts are present in the web (affects k_d factor).",
    )








def _render_fast_next_hint(message: str, *, css_extra_class: str = "") -> None:
    cls = "fast-next-hint" + (f" {css_extra_class}" if css_extra_class else "")
    st.markdown(f"<div class='{cls}'>{html.escape(message)}</div>", unsafe_allow_html=True)




def _handle_inputs_apply_buttons_current_coordinator() -> None:
    handle_inputs_apply_buttons(
        st_module=st,
        stderr=sys.stderr,
        design_guide_apply_trace_run_id_key=_legacy_inputs_page.DESIGN_GUIDE_APPLY_TRACE_RUN_ID_KEY,
        set_live_breadcrumb_fn=_legacy_inputs_page._set_design_guide_live_breadcrumb,
        begin_apply_trace_fn=_legacy_inputs_page._begin_design_guide_apply_trace,
        apply_recommendation_result_fn=_legacy_inputs_page.apply_recommendation_result,
        recommendation_blocked_reason_fn=_legacy_inputs_page._recommendation_blocked_reason,
        emit_apply_trace_run_end_fn=_legacy_inputs_page._emit_design_guide_apply_trace_run_end,
        record_rerun_trigger_fn=_record_inputs_rerun_trigger,
    )


def _handle_inputs_auto_design_current_coordinator() -> None:
    handle_inputs_auto_design(
        st_module=st,
        stderr=sys.stderr,
        time_module=time,
        legacy_page=_legacy_inputs_page,
        auto_design_auto_invoke_key=AUTO_DESIGN_AUTO_INVOKE_KEY,
        auto_design_request_source_key=AUTO_DESIGN_REQUEST_SOURCE_KEY,
        record_rerun_trigger_fn=_record_inputs_rerun_trigger,
        persist_active_beam_from_shared_fn=persist_active_beam_from_shared,
        persist_state_snapshot_fn=persist_state_snapshot,
    )


def render_inputs_pre_widget_apply_and_render_setup_coordinator(*, ss: dict, fast_get_param):
    corrected_invalid_shear_state = bool(st.session_state.pop("_inputs_shear_shared_normalised_this_run", False))
    if corrected_invalid_shear_state:
        inputs_hydration_trace_log("shear_widget_refresh_after_router_norm", refreshed=True)

    fast_focus_section = st.session_state.pop("_fast_mode_focus_section", None)

    # Apply callbacks remain behavior-critical; the dispatcher is extracted while
    # the Apply engine dependencies stay injected until their own parity slice.
    _handle_inputs_apply_buttons_current_coordinator()

    sync_callbacks = _wrap_longitudinal_reo_sync_callbacks(get_sync_callbacks())

    inputs_render_audit = _fresh_inputs_render_audit()
    ss["_inputs_render_audit_live"] = inputs_render_audit
    apply_inputs_page_css()
    apply_global_widget_css()
    apply_calcbox_css()
    try:
        publish_normalized_final_shear_truth_to_session(source="render_inputs:pre_summary")
    except Exception:
        pass

    if ss.get("_dev_mode", False):
        dbg = dict(ss.get("_debug_d_consistency", {}))
        dbg["ui_display_d_mm"] = float(fast_get_param("d", 0.0) or 0.0)
        ss["_debug_d_consistency"] = dbg

    return corrected_invalid_shear_state, fast_focus_section, sync_callbacks, inputs_render_audit


def inputs_debug_audit_enabled() -> bool:
    return bool(_INPUTS_DEBUG_AUDIT)


def inputs_audit_snapshot_state():
    snapshot = build_inputs_session_source_snapshot(st.session_state)
    return {entry.key: entry.value for entry in snapshot.entries}


def render_inputs_dev_session_debug_sidebar_coordinator(*, ss: dict) -> None:
    render_inputs_dev_session_debug_sidebar_module(
        sidebar_module=st,
        state=st.session_state,
        ss=ss,
        design_guide_sidebar_debug_toggle_key=DESIGN_GUIDE_SIDEBAR_DEBUG_TOGGLE_KEY,
    )


def _design_guide_sidebar_debug_enabled() -> bool:
    try:
        return bool(st.session_state.get(DESIGN_GUIDE_SIDEBAR_DEBUG_TOGGLE_KEY, False))
    except Exception:
        return False


def _auto_design_invoke_debug_snapshot() -> dict:
    try:
        snapshot = build_inputs_auto_design_invoke_debug_snapshot(
            force_auto_redesign=st.session_state.get("_force_auto_redesign", False),
            auto_design_auto_invoke=st.session_state.get(AUTO_DESIGN_AUTO_INVOKE_KEY, False),
            auto_design_request_source=st.session_state.get("auto_design_request_source")
            or st.session_state.get(AUTO_DESIGN_REQUEST_SOURCE_KEY),
            auto_design_requested_at_ts=st.session_state.get(AUTO_DESIGN_REQUEST_TS_KEY),
            auto_design_invoke_pending=st.session_state.get("auto_design_invoke_pending", False),
        )
        return dict(snapshot.debug_payload)
    except Exception:
        return {
            "force_auto_redesign": None,
            "auto_design_auto_invoke": None,
            "auto_design_request_source": None,
            "auto_design_requested_at_ts": None,
            "auto_design_invoke_pending": None,
        }


def _design_guide_tracer_path() -> str:
    return design_guide_tracer_path_module()


def _design_guide_tracer_verbose_log() -> bool:
    return design_guide_tracer_verbose_log_module()


def _append_design_guide_trace(
    event: str,
    data: dict,
    *,
    run_id: str,
    source: str,
) -> None:
    append_design_guide_trace_module(
        event,
        data,
        run_id=run_id,
        source=source,
        tracer_path_fn=_design_guide_tracer_path,
        tracer_verbose_log_fn=_design_guide_tracer_verbose_log,
        agent_debug_log_fn=_agent_debug_log,
    )


def _clear_design_guide_transient_ui_state(
    *,
    clear_history: bool = False,
    preserve_apply_banner: bool = False,
) -> None:
    transient_keys = [
        DESIGN_GUIDE_APPLY_BANNER_META_KEY,
        DESIGN_GUIDE_GUIDANCE_CACHE_FP_KEY,
        DESIGN_GUIDE_GUIDANCE_CACHE_ITEMS_KEY,
        DESIGN_GUIDE_GUIDANCE_CACHE_DEBUG_KEY,
        DESIGN_GUIDE_SIMPLE_CACHE_FP_KEY,
        DESIGN_GUIDE_SIMPLE_CACHE_ITEMS_KEY,
        DESIGN_GUIDE_PENDING_STEP_CTX_KEY,
    ]
    clear_plan = build_inputs_design_guide_transient_ui_clear_plan(
        base_transient_keys=tuple(transient_keys),
        apply_banner_key=DESIGN_GUIDE_APPLY_BANNER_KEY,
        always_clear_keys=(
            DESIGN_GUIDE_DEBUG_BUNDLE_KEY,
            DESIGN_GUIDE_RECO_TRACE_KEY,
            DESIGN_GUIDE_RANK_TRACE_KEY,
        ),
        history_keys=(
            DESIGN_GUIDE_STEP_HISTORY_KEY,
            DESIGN_GUIDE_FIRST_TARGET_BAND_STEP_KEY,
            DESIGN_GUIDE_HISTORY_ANCHOR_KEY,
        ),
        clear_history=bool(clear_history),
        preserve_apply_banner=bool(preserve_apply_banner),
    )
    for key in clear_plan.all_keys:
        st.session_state.pop(key, None)


def _invalidate_design_guide_caches(
    *,
    reason: str,
    updated_keys: list[str] | None = None,
    preserve_apply_banner: bool = False,
) -> list[str]:
    removed: list[str] = []
    _clear_design_guide_transient_ui_state(
        clear_history=False,
        preserve_apply_banner=preserve_apply_banner,
    )
    for session_key in list(st.session_state.keys()):
        if str(session_key).startswith("_recommendation_cache_"):
            removed.append(str(session_key))
            st.session_state.pop(session_key, None)
    if bool(st.session_state.get("_dev_mode")):
        _agent_debug_log(
            "Invalidated design guide caches",
            {
                "reason": reason,
                "updated_keys": list(updated_keys or []),
                "removed_cache_keys": removed,
            },
            location="inputs_page_route_coordinators.py:_invalidate_design_guide_caches",
            hypothesis_id="H301",
        )
    return removed


def _mark_design_guide_dirty() -> None:
    """Inputs changed vs last rendered guide; clear stale cards/cache (not beam state)."""
    dirty_plan = build_inputs_design_guide_dirty_mark_plan(
        refresh_key=DESIGN_GUIDE_NEEDS_REFRESH_KEY,
        clear_history=False,
        preserve_apply_banner=False,
    )
    st.session_state[dirty_plan.refresh_key] = dirty_plan.refresh_value
    _clear_design_guide_transient_ui_state(
        clear_history=dirty_plan.clear_history,
        preserve_apply_banner=dirty_plan.preserve_apply_banner,
    )


def create_summary_container():
    return st.container()


def render_inputs_batch_design_context_coordinator(*, ss: dict):
    beam_labels = build_batch_beam_option_labels()
    beam_order = ss.get("beam_order", [])
    active_beam_id = ss.get("active_beam_id")
    if active_beam_id not in beam_order and beam_order:
        active_beam_id = beam_order[0]
    return beam_labels, beam_order, active_beam_id


def _shared_state_snapshot() -> dict:
    return {
        key: st.session_state.get(key, default)
        for key, default in SHARED_DEFAULTS.items()
    }


def _cache_json(value) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


@st.cache_data(show_spinner=False)
def cached_make_section_figure(
    *,
    shape_name: str,
    dims_json: str,
    reo_json: str,
    show_shear: bool,
    show_dn: bool = False,
    dn: float = 0.0,
    tension_face: str | None = None,
):
    return make_sectionA_figure(
        shape_name=shape_name,
        dims=json.loads(dims_json),
        reo=json.loads(reo_json),
        show_shear=show_shear,
        show_dn=show_dn,
        dn=dn,
        tension_face=tension_face,
    )


@st.cache_data(show_spinner=False)
def cached_make_section_3d_figure(
    *,
    shape_name: str,
    dims_json: str,
    reo_layout_json: str,
    reo_inputs_json: str,
    show_shear: bool = False,
    L_vis: float = 900.0,
):
    return make_section_3d_figure(
        shape_name=shape_name,
        dims=json.loads(dims_json),
        reo_layout=json.loads(reo_layout_json),
        reo_inputs=json.loads(reo_inputs_json),
        show_shear=show_shear,
        L_vis=L_vis,
    )


def _get_sec_shape():
    s = st.session_state.get("sec_shape", "RECT")
    if s not in ("RECT", "T", "I"):
        s = "RECT"
    return s


def _get_outline_points_and_bbox():
    """
    Returns:
      pts: list[(x, y)] closed polygon (y downwards)
      b_box: overall width used for layout/axes (max width)
      D: overall depth
    """
    return build_section_outline_points_and_bbox_module(
        sec_shape=_get_sec_shape(),
        b=float(get_param("b", 400.0)),
        D=float(get_param("D", 600.0)),
        bf=float(get_param("bf", 600.0)),
        tf=float(get_param("tf", 120.0)),
        bw=float(get_param("bw", 300.0)),
        tw=float(get_param("tw", 200.0)),
    )


def _build_inputs_diagram_source_snapshot(layout=None, model_state: dict | None = None) -> InputsDiagramSourceSnapshot:
    if layout is None:
        layout = compute_section_layout()
    shared_state = dict(model_state) if isinstance(model_state, dict) else _shared_state_snapshot()
    try:
        outline_points, outline_width, outline_depth = _get_outline_points_and_bbox()
    except Exception:
        dims = dict((layout or {}).get("dims") or {})
        outline_width = float(dims.get("b", dims.get("bf", 400.0)) or 400.0)
        outline_depth = float(dims.get("D", 600.0) or 600.0)
        outline_points = (
            (0.0, 0.0),
            (outline_width, 0.0),
            (outline_width, outline_depth),
            (0.0, outline_depth),
            (0.0, 0.0),
        )
    return InputsDiagramSourceSnapshot(
        layout=dict(layout or {}),
        shared_state=shared_state,
        tension_face=st.session_state.get("active_tension_face"),
        fallback_cover_side=float(shared_state.get("cover_side", 40.0) or 40.0),
        fallback_cover_top=float(shared_state.get("cover_top", 40.0) or 40.0),
        fallback_cover_bot=float(shared_state.get("cover_bot", 40.0) or 40.0),
        fallback_width=float(shared_state.get("b", outline_width) or outline_width),
        fallback_depth=float(shared_state.get("D", outline_depth) or outline_depth),
        span_length=float(shared_state.get("L", get_param("L", 3000.0)) or 3000.0),
        outline_points=tuple(tuple(point) for point in outline_points),
        outline_width=float(outline_width),
        outline_depth=float(outline_depth),
    )


def _record_inputs_diagram_view_model_trace(source, view_model, *, live_cutover: bool) -> None:
    st.session_state["_inputs_diagram_view_model_trace"] = {
        "diagram_view_model_trace_source": "inputs_page_modules.diagrams",
        "diagram_view_model_trace_only": True,
        "live_cutover": bool(live_cutover),
        "section_2d_display_hash": view_model.section_2d.display_hash,
        "beam_3d_display_hash": view_model.beam_3d.display_hash,
        "diagram_display_hash": view_model.display_hash,
        "source_layout_keys": sorted(dict(source.layout or {}).keys()),
    }


@speed_profiled("ui_render.make_summary_cross_section_figure", category="render")
def make_summary_cross_section_figure():
    layout = compute_section_layout()
    source = _build_inputs_diagram_source_snapshot(layout)
    view_model = build_inputs_diagram_view_model(source)
    _record_inputs_diagram_view_model_trace(source, view_model, live_cutover=False)
    section_vm = view_model.section_2d
    result = build_summary_cross_section_result(
        layout=layout,
        tension_face=section_vm.tension_face,
        fallback_cover_side=float(section_vm.fallback_cover_side),
        fallback_cover_top=float(section_vm.fallback_cover_top),
        fallback_cover_bot=float(section_vm.fallback_cover_bot),
        section_figure_builder=cached_make_section_figure,
    )
    if result.error_message:
        st.error(result.error_message)
    return result.figure


@speed_profiled("ui_render.make_beam_3d_figure", category="render")
def make_beam_3d_figure():
    layout = compute_section_layout()
    if st.session_state.get("_debug_reo_layout", False):
        st.write("3D reo_layout:", (layout.get("reo_layout") if isinstance(layout, dict) else None))
    source = _build_inputs_diagram_source_snapshot(layout)
    view_model = build_inputs_diagram_view_model(source)
    _record_inputs_diagram_view_model_trace(source, view_model, live_cutover=False)
    beam_vm = view_model.beam_3d
    return build_inputs_beam_3d_figure(
        shape_name=beam_vm.shape_name,
        shape_key=beam_vm.shape_key,
        outline_points=list(beam_vm.outline_points),
        b_box=float(beam_vm.b_box),
        D=float(beam_vm.D),
        L_plot=float(beam_vm.L_plot),
        fallback_width=float(beam_vm.fallback_width),
        cover_bot=float(beam_vm.cover_bot),
        cover_top=float(beam_vm.cover_top),
        cover_side=float(beam_vm.cover_side),
        lig_d=float(beam_vm.lig_d),
        lig_legs=int(beam_vm.lig_legs),
        s_lig=float(beam_vm.s_lig),
        reo_layout=dict(beam_vm.reo_layout or {}),
        cage=dict(beam_vm.cage or {}),
        resolved_bars=list(beam_vm.resolved_bars or ()),
    )


def _clear_auto_design_runtime_latches(reason: str) -> dict:
    ss = st.session_state
    before = {
        "_solver_running": bool(ss.get("_solver_running", False)),
        "_compute_in_progress": bool(ss.get("_compute_in_progress", False)),
        "auto_design_latch_owner": str(ss.get("auto_design_latch_owner") or ""),
        "auto_design_invoke_consumed": bool(ss.get("auto_design_invoke_consumed", False)),
    }
    ss["_solver_running"] = False
    ss["_compute_in_progress"] = False
    ss["auto_design_latch_owner"] = ""
    ss["auto_design_invoke_consumed"] = False
    payload = {
        "reason": str(reason or ""),
        "before": before,
        "after": {
            "_solver_running": bool(ss.get("_solver_running", False)),
            "_compute_in_progress": bool(ss.get("_compute_in_progress", False)),
            "auto_design_latch_owner": str(ss.get("auto_design_latch_owner") or ""),
            "auto_design_invoke_consumed": bool(ss.get("auto_design_invoke_consumed", False)),
        },
    }
    ss["_auto_design_latch_clear_latest"] = dict(payload)
    return payload


def _guidance_state_snapshot(state: dict | None = None) -> dict:
    return build_guidance_state_snapshot_module(
        state,
        result_keys=RESULT_KEYS,
        shared_defaults=SHARED_DEFAULTS,
    )


def _auto_design_governing_fingerprint(state: dict | None = None) -> tuple:
    source = state or _shared_state_snapshot()
    actions = _resolve_design_actions_from_state(source)
    return build_auto_design_governing_fingerprint_module(source, actions=actions)


def _sync_auto_design_invalidation(state: dict | None = None) -> None:
    current_fingerprint = _auto_design_governing_fingerprint(state)
    previous_fingerprint = st.session_state.get("_auto_design_last_fingerprint")
    if previous_fingerprint is None:
        st.session_state["_auto_design_last_fingerprint"] = current_fingerprint
        return
    if current_fingerprint != previous_fingerprint:
        st.session_state["_auto_design_invalidated"] = True
        st.session_state["_auto_design_last_fingerprint"] = current_fingerprint
        st.session_state.pop("pending_recommendation", None)
        st.session_state.pop("pending_recommendation_applied_id", None)
        st.session_state.pop("_solver_result", None)
        st.session_state.pop("_one_click_run_feedback", None)
        st.session_state.pop("auto_design_status", None)
        st.session_state.pop("auto_design_steps", None)
        st.session_state.pop("auto_design_request_source", None)
        st.session_state.pop(AUTO_DESIGN_REQUEST_SOURCE_KEY, None)
        st.session_state.pop(AUTO_DESIGN_REQUEST_TS_KEY, None)
        st.session_state.pop(AUTO_DESIGN_AUTO_INVOKE_KEY, None)
        st.session_state.pop("_inputs_action_run_auto_design", None)
        st.session_state.pop("auto_design_invoke_set", None)
        st.session_state.pop("auto_design_invoke_pending", None)
        st.session_state.pop("auto_design_invoke_consumed", None)
        _clear_auto_design_runtime_latches("design_state_changed")


def _debug_resolved_guidance_actions(state: dict | None = None) -> dict:
    source_state = _guidance_state_snapshot(state)
    actions = _resolve_design_actions_from_state(source_state)
    return {
        "resolved_source": actions.get("source"),
        "Mu": actions.get("Mu"),
        "Vu": actions.get("Vu"),
        "Nu": actions.get("Nu"),
        "SLS_M": actions.get("SLS_M"),
        "SLS_V": actions.get("SLS_V"),
        "actions_source": actions.get("actions_source"),
        "actions_mode": actions.get("actions_mode"),
        "signature": tuple(actions.get("signature", ())),
    }


def save_active_batch_beam_to_table() -> None:
    _apply_canonical_convenience_resync_to_shared_for_app_bridge(
        source="beam_manager:save_active_to_table"
    )
    persist_active_beam_from_shared()
    st.session_state["_beam_skip_auto_persist_once"] = False


def _record_inputs_rerun_trigger(reason: str, meta: dict | None = None) -> None:
    plan = build_inputs_rerun_trigger_record_plan(
        reason=reason,
        meta=meta,
        existing_triggers=st.session_state.get("_inputs_rerun_trigger_events"),
        timestamp=time.time(),
        max_events=24,
    )
    st.session_state["_inputs_rerun_trigger_events"] = list(plan.stored_triggers)
    try:
        import session_state_final_log as _ssl

        _ssl.append_session_state_final_log(
            plan.ssl_trigger_reason,
            dict(plan.log_payload),
        )
        _ssl.ssl_record_rerun_trigger(plan.ssl_trigger_reason)
    except Exception:
        pass


def render_inputs_beam_load_triggered_rerun_log_coordinator(reason: str) -> None:
    _record_inputs_rerun_trigger(
        "beam_load_triggered_rerun",
        meta={"reason": reason, "hydration_layer": "render_inputs"},
    )


def render_inputs_batch_design_manager_coordinator(
    *,
    ss: dict,
    beam_labels: dict,
    beam_order: list,
    active_beam_id: str,
) -> None:
    render_batch_design_page(
        BatchDesignPageContext(
            session_state=ss,
            beam_order=beam_order,
            active_beam_id=active_beam_id,
            beam_labels=beam_labels,
            set_active_beam=set_active_beam,
            add_beam=add_new_beam_record,
            duplicate_beam=duplicate_active_beam_record,
            delete_beam=delete_beam_record,
            reset_workspace=reset_app_to_clean_starter_workspace,
            force_refresh=_force_inputs_apply_refresh_cycle,
            log_rerun=render_inputs_beam_load_triggered_rerun_log_coordinator,
            save_active_to_table=save_active_batch_beam_to_table,
            apply_resync=_apply_canonical_convenience_resync_to_shared_for_app_bridge,
            build_schedule_preview_df=build_batch_schedule_preview_df,
            build_schedule_editor_df=build_batch_beam_schedule_df,
            sync_schedule_editor_df=sync_batch_beam_records_from_schedule_df,
            build_schedule_export_df=build_batch_schedule_export_df,
            get_active_summary=get_active_beam_summary,
            format_status_badge=format_batch_beam_status_badge,
            format_last_checked=format_batch_last_checked,
            make_section_preview_figure=make_summary_cross_section_figure,
            render_plotly_diagram=st.plotly_chart,
            design_brain_adapter=BatchDesignGuidanceAdapter(
                base_state_provider=_shared_state_snapshot,
                design_guidance_runner=_compute_design_guidance_items,
                request_kind="auto_design",
            ),
        )
    )


def render_inputs_page_divider_coordinator() -> None:
    page_divider()


def _design_optimisation_goal(state: dict | None = None) -> str:
    source = state if isinstance(state, dict) else st.session_state
    return resolve_design_optimisation_goal(
        source,
        goal_labels=DESIGN_OPTIMISATION_GOAL_LABELS,
        default_goal="balanced",
    )


def _geometry_lock_enabled(source: dict | None = None) -> bool:
    resolved = source if isinstance(source, dict) else st.session_state
    return bool((resolved or {}).get("optimisation_lock_geometry", False))


def _sync_auto_design_mode_tracking(state: dict | None = None) -> None:
    current_mode = _design_optimisation_goal(state)
    previous_mode = st.session_state.get("_prev_auto_design_mode")
    if previous_mode is None:
        st.session_state["_prev_auto_design_mode"] = current_mode
        return
    if current_mode != previous_mode:
        st.session_state["_force_auto_redesign"] = True
        st.session_state["_prev_auto_design_mode"] = current_mode
        st.session_state["_auto_design_reason"] = "mode_changed"


def _shared_toggle(
    label: str,
    widget_key: str,
    shared_key: str,
    default: bool,
    sync_callbacks: dict,
    *,
    help_text: str | None = None,
) -> bool:
    _register_rendered_key(widget_key)
    seed_widget_from_shared(widget_key, shared_key, bool(default))
    return st.toggle(
        label,
        key=widget_key,
        help=help_text,
        on_change=sync_callbacks.get(widget_key),
    )


def _render_design_optimisation_inputs(sync_callbacks: dict) -> None:
    select_row(
        "Optimise for",
        "inputs_design_optimisation_goal",
        DESIGN_OPTIMISATION_GOAL_LABELS,
        _design_optimisation_goal(_shared_state_snapshot()),
        sync_callbacks,
        help_text=(
            "Tailor design guidance and auto-design recommendations to the preferred "
            "beam optimisation objective."
        ),
    )
    st.caption("This changes how guidance and guided design fixes are prioritised.")
    _shared_toggle(
        "Lock geometry",
        "inputs_optimisation_lock_geometry",
        "optimisation_lock_geometry",
        False,
        sync_callbacks,
        help_text=(
            "When enabled, optimisation keeps beam geometry fixed and only adjusts "
            "reinforcement/detailing variables where possible."
        ),
    )
    if _geometry_lock_enabled(_shared_state_snapshot()):
        st.caption("Geometry locked: optimisation is limited to reinforcement and detailing changes.")


def render_inputs_design_mode_selector_coordinator(*, sync_callbacks: dict) -> bool:
    top_dm_l, top_dm_r = st.columns([8, 1], gap="small", vertical_alignment="top")
    with top_dm_l:
        seed_widget_from_shared("inputs_detailed_mode_toggle", "inputs_detailed_mode", False)
        inputs_detailed_mode = v2_radio(
            label="Design mode",
            key="inputs_detailed_mode_toggle",
            options=[False, True],
            default_index=1 if bool(_shared_state_snapshot().get("inputs_detailed_mode", False)) else 0,
            format_func=lambda value: "Detailed" if value else "Fast",
            horizontal=True,
            help="Choose between the streamlined fast workflow and the full detailed design workspace.",
            on_change=sync_callbacks.get("inputs_detailed_mode_toggle"),
        )
    with top_dm_r:
        _pad_i, _info_i = st.columns([0.2, 0.8], gap="small")
        with _info_i:
            with info_i_button(
                help_text=(
                    "Design mode: Fast streamlines inputs; Detailed opens the full workspace. "
                    "Use the controls below to set the optimisation goal for design guidance and "
                    "auto-design recommendations."
                )
            ):
                _render_design_optimisation_inputs(sync_callbacks)
    return bool(inputs_detailed_mode)


def render_inputs_page_setup_current_coordinator(*, ss: dict) -> dict[str, Any]:
    render_inputs_initial_session_state_coordinator(ss=ss)

    inputs_hydration_trace_log("render_inputs_entry", note="router_already_hydrated")

    _PARAMS, fast_get_param = render_inputs_param_snapshot_coordinator()
    _ = _PARAMS

    _t0, _perf_start, _perf_marks, _sub_marks, _mark, _sub_mark = (
        render_inputs_perf_marker_setup_coordinator(ss=ss)
    )

    _mark("start")
    render_started_at = render_inputs_page_load_start_coordinator(ss=ss)

    render_inputs_startup_hydration_coordinator(ss=ss, mark=_mark)

    (
        corrected_invalid_shear_state,
        fast_focus_section,
        sync_callbacks,
        inputs_render_audit,
    ) = render_inputs_pre_widget_apply_and_render_setup_coordinator(
        ss=ss,
        fast_get_param=fast_get_param,
    )

    before_state = inputs_audit_snapshot_state() if inputs_debug_audit_enabled() else None

    render_inputs_dev_session_debug_sidebar_coordinator(ss=ss)

    summary_container = create_summary_container()

    beam_labels, beam_order, active_beam_id = render_inputs_batch_design_context_coordinator(ss=ss)
    render_inputs_batch_design_manager_coordinator(
        ss=ss,
        beam_labels=beam_labels,
        beam_order=beam_order,
        active_beam_id=active_beam_id,
    )

    render_inputs_page_divider_coordinator()
    _mark("beam_manager")
    _sub_mark("start")

    inputs_detailed_mode = render_inputs_design_mode_selector_coordinator(
        sync_callbacks=sync_callbacks,
    )

    return {
        "fast_get_param": fast_get_param,
        "t0": _t0,
        "perf_start": _perf_start,
        "perf_marks": _perf_marks,
        "sub_marks": _sub_marks,
        "mark": _mark,
        "sub_mark": _sub_mark,
        "render_started_at": render_started_at,
        "corrected_invalid_shear_state": corrected_invalid_shear_state,
        "fast_focus_section": fast_focus_section,
        "sync_callbacks": sync_callbacks,
        "inputs_render_audit": inputs_render_audit,
        "before_state": before_state,
        "summary_container": summary_container,
        "inputs_detailed_mode": inputs_detailed_mode,
    }


def render_inputs_top_section_layout_slots_coordinator(
    *,
    inputs_detailed_mode: bool,
    sync_callbacks: dict,
    inputs_render_audit: dict[str, str],
    fast_focus_section: str | None,
):
    bottom_slot = None
    shear_slot = None
    model_slot = None
    if inputs_detailed_mode:
        render_design_guide_panel_orchestration(
            coordinator_owner=_legacy_inputs_page,
            sync_callbacks=sync_callbacks,
            inputs_render_audit=inputs_render_audit,
            fast_focus_section=fast_focus_section,
        )
        left_inputs, right_diagram = st.columns([1.15, 1.85], gap="large")
        with left_inputs:
            actions_slot = st.container()
            geometry_slot = st.container()
    else:
        render_design_guide_panel_orchestration(
            coordinator_owner=_legacy_inputs_page,
            sync_callbacks=sync_callbacks,
            inputs_render_audit=inputs_render_audit,
        )
        fast_left, fast_right = st.columns([1.0, 1.5], gap="medium")
        with fast_left:
            actions_slot = st.container()
            geometry_slot = st.container()
        with fast_right:
            model_slot = st.container()
        right_diagram = None
    return bottom_slot, shear_slot, model_slot, actions_slot, geometry_slot, right_diagram


DEBUG_DESIGN_GUIDANCE_PROBE = True


def _resolve_design_actions_from_state(state: dict) -> dict:
    return resolve_design_actions(state)


def _render_design_action_number_row(
    *,
    label: str,
    widget_key: str,
    help_text: str,
    on_change,
    disabled: bool = False,
    col_label=None,
    col_input=None,
) -> float:
    return render_design_action_number_row_module(
        st_module=st,
        label=label,
        widget_key=widget_key,
        help_text=help_text,
        on_change=on_change,
        disabled=disabled,
        col_label=col_label,
        col_input=col_input,
        label_with_hover_fn=label_with_hover,
        register_rendered_key_fn=_register_rendered_key,
    )


def _debug_check_design_action_consistency(state: dict) -> None:
    debug_check_design_action_consistency_module(
        state,
        st_module=st,
        debug_design_guidance_probe=DEBUG_DESIGN_GUIDANCE_PROBE,
        resolve_design_actions_from_state_fn=_resolve_design_actions_from_state,
        agent_debug_log_fn=_agent_debug_log,
    )


def _design_action_widget_specs(selected_prefix: str) -> list[dict]:
    return design_action_widget_specs_module(selected_prefix)


def _make_design_action_widget_callback(widget_key: str, shared_key: str, proxy_key: str | None = None):
    return make_design_action_widget_callback_module(
        widget_key,
        shared_key,
        proxy_key,
        sync_design_action_widget_to_shared_fn=_sync_design_action_widget_to_shared,
    )


def _queue_inputs_refresh(source: str, keys: list[str], *, focus_section: str | None = None) -> None:
    try:
        import session_state_final_log as _ssl

        _ssl.append_session_state_final_log(
            "queue_inputs_refresh",
            {
                "source": source,
                "keys": list(keys)[:48],
                "had_reseed_before_pop": bool(st.session_state.get("_force_inputs_widget_reseed_once")),
            },
        )
        _ssl.ssl_increment("queue_inputs_refresh_count", 1)
    except Exception:
        pass
    st.session_state.pop("_force_inputs_widget_reseed_once", None)
    next_focus_map = {
        "fast_mode:geometry_recommendation": "model",
        "fast_mode:bottom_recommendation": "shear",
    }
    next_focus_section = focus_section or next_focus_map.get(source)
    if next_focus_section:
        st.session_state["_fast_mode_focus_section"] = next_focus_section
    if str(source).startswith("guidance:"):
        st.session_state["_design_guide_banner_generic_only"] = True
    st.session_state["_pending_inputs_apply_refresh"] = {
        "source": source,
        "keys": keys,
    }
    inputs_hydration_trace_log("queue_inputs_refresh", source=source, keys=list(keys)[:24])


def _sync_design_action_widget_to_shared(
    widget_key: str,
    shared_key: str,
    proxy_key: str | None = None,
    *,
    trigger_rerun: bool = False,
) -> None:
    sync_design_action_widget_to_shared_module(
        widget_key,
        shared_key,
        proxy_key,
        trigger_rerun=trigger_rerun,
        st_module=st,
        debug_design_guidance_probe=DEBUG_DESIGN_GUIDANCE_PROBE,
        append_design_guide_trace_fn=_append_design_guide_trace,
        get_param_fn=get_param,
        mark_user_edit_fn=mark_user_edit,
        set_shared_fn=set_shared,
        invalidate_inputs_summary_packs_fn=_invalidate_inputs_summary_packs,
        queue_inputs_refresh_fn=_queue_inputs_refresh,
        invalidate_design_guide_caches_fn=_invalidate_design_guide_caches,
        mark_design_guide_dirty_fn=_mark_design_guide_dirty,
        persist_active_beam_from_shared_fn=persist_active_beam_from_shared,
        persist_state_snapshot_fn=persist_state_snapshot,
        debug_resolved_guidance_actions_fn=_debug_resolved_guidance_actions,
        shared_state_snapshot_fn=_shared_state_snapshot,
        sync_auto_design_invalidation_fn=_sync_auto_design_invalidation,
        debug_check_design_action_consistency_fn=_debug_check_design_action_consistency,
        time_ms_fn=lambda: int(time.time() * 1000),
    )


def _mirror_design_action_proxies_from_shared(selected_prefix: str) -> None:
    mirror_design_action_proxies_from_shared_module(
        selected_prefix,
        get_param_fn=get_param,
        set_shared_fn=set_shared,
    )


def _hydrate_design_action_widgets_from_shared(
    selected_prefix: str,
    *,
    force: bool = False,
    design_controls: bool = False,
) -> None:
    hydrate_design_action_widgets_from_shared_module(
        selected_prefix,
        st_module=st,
        get_param_fn=get_param,
        state_hc_log_fn=_state_hc_log,
        design_action_widget_specs_fn=_design_action_widget_specs,
        force=force,
        design_controls=design_controls,
    )


def _commit_design_action_widgets_to_shared(selected_prefix: str) -> None:
    commit_design_action_widgets_to_shared_module(
        selected_prefix,
        st_module=st,
        design_action_widget_specs_fn=_design_action_widget_specs,
        sync_design_action_widget_to_shared_fn=_sync_design_action_widget_to_shared,
    )


def _reconcile_design_action_widgets_with_shared(selected_prefix: str) -> list[str]:
    return reconcile_design_action_widgets_with_shared_module(
        selected_prefix,
        st_module=st,
        design_action_widget_specs_fn=_design_action_widget_specs,
        get_param_fn=get_param,
        sync_design_action_widget_to_shared_fn=_sync_design_action_widget_to_shared,
        debug_design_guidance_probe=DEBUG_DESIGN_GUIDANCE_PROBE,
        append_design_guide_trace_fn=_append_design_guide_trace,
        time_ms_fn=lambda: int(time.time() * 1000),
    )


def _inputs_inject_scroll_to_design_actions() -> None:
    """Scroll main view to the Design Actions anchor (one-shot)."""
    if not st.session_state.pop(_INPUTS_SCROLL_DESIGN_ACTIONS_FLAG, False):
        return
    import streamlit.components.v1 as components

    aid = json.dumps(_INPUTS_DESIGN_ACTIONS_ANCHOR_ID)
    components.html(
        f"""
<script>
(function() {{
  const doc = window.parent.document;
  const id = {aid};
  let tries = 0;
  function tick() {{
    const el = doc.getElementById(id);
    if (el) {{
      try {{ el.scrollIntoView({{ behavior: "smooth", block: "start" }}); }} catch (e) {{}}
      return;
    }}
    tries += 1;
    if (tries < 80) setTimeout(tick, 50);
  }}
  setTimeout(tick, 120);
}})();
</script>
""",
        height=0,
    )


def render_inputs_design_actions_section_current_coordinator(
    *,
    actions_slot,
    inputs_detailed_mode: bool,
    sync_callbacks: dict,
    sub_mark,
) -> None:
    render_inputs_design_actions_section_module(
        st_module=st,
        actions_slot=actions_slot,
        inputs_detailed_mode=bool(inputs_detailed_mode),
        sync_callbacks=sync_callbacks,
        sub_mark=sub_mark,
        design_actions_anchor_id=_INPUTS_DESIGN_ACTIONS_ANCHOR_ID,
        info_i_button_fn=info_i_button,
        get_widget_key_for_shared_fn=get_widget_key_for_shared,
        commit_design_action_widgets_to_shared_fn=_commit_design_action_widgets_to_shared,
        mirror_design_action_proxies_from_shared_fn=_mirror_design_action_proxies_from_shared,
        is_design_governing_fn=is_design_governing,
        hydrate_design_action_widgets_from_shared_fn=_hydrate_design_action_widgets_from_shared,
        design_action_widget_specs_fn=_design_action_widget_specs,
        make_design_action_widget_callback_fn=_make_design_action_widget_callback,
        render_design_action_number_row_fn=_render_design_action_number_row,
        reconcile_design_action_widgets_with_shared_fn=_reconcile_design_action_widgets_with_shared,
        debug_check_design_action_consistency_fn=_debug_check_design_action_consistency,
        shared_state_snapshot_fn=_shared_state_snapshot,
    )


def render_inputs_geometry_materials_top_section_current_coordinator(
    *,
    geometry_slot,
    right_diagram,
    model_slot,
    inputs_detailed_mode: bool,
    sync_callbacks: dict,
    fast_get_param,
    mark,
    sub_mark,
) -> None:
    return render_inputs_geometry_materials_top_section_module(
        st_module=st,
        geometry_slot=geometry_slot,
        right_diagram=right_diagram,
        model_slot=model_slot,
        inputs_detailed_mode=bool(inputs_detailed_mode),
        sync_callbacks=sync_callbacks,
        fast_get_param=fast_get_param,
        mark=mark,
        sub_mark=sub_mark,
        recommendation_section_header_fn=_render_recommendation_section_header,
        geometry_recommendation_panel_fn=_render_geometry_recommendation_panel,
        select_row_fn=select_row,
        number_row_fn=number_row,
        materials_subsection_fn=_render_inputs_materials_subsection,
        section_2d_diagram_block_fn=_render_section_2d_diagram_block,
        resolved_inputs_model_state_fn=_resolved_inputs_model_state,
        fast_model_block_fn=_render_fast_model_block,
        page_divider_fn=page_divider,
    )


def create_reinforcement_columns():
    return st.columns(3, gap="large")


def get_inputs_section_shape_for_reinforcement() -> str:
    return st.session_state.get(
        "inputs_sec_shape",
        st.session_state.get("sec_shape", "RECT"),
    )


def render_inputs_bottom_reinforcement_column_current_coordinator(
    *,
    col_bot_reo,
    inputs_detailed_mode: bool,
    sync_callbacks: dict,
    fast_get_param,
    sec_shape_reo_ui,
    is_ti_reo_ui: bool,
    bot_hdr: str,
) -> None:
    return render_inputs_bottom_reinforcement_column_module(
        st_module=st,
        col_bot_reo=col_bot_reo,
        inputs_detailed_mode=bool(inputs_detailed_mode),
        sync_callbacks=sync_callbacks,
        fast_get_param=fast_get_param,
        sec_shape_reo_ui=sec_shape_reo_ui,
        is_ti_reo_ui=bool(is_ti_reo_ui),
        bot_hdr=bot_hdr,
        longitudinal_reo_widget_audit_snapshot_fn=_longitudinal_reo_widget_audit_snapshot,
        get_widget_key_for_shared_fn=get_widget_key_for_shared,
        seed_widget_from_shared_fn=seed_widget_from_shared,
        recommendation_section_header_fn=_render_recommendation_section_header,
        bottom_recommendation_panel_fn=_render_bottom_recommendation_panel,
        render_longitudinal_reo_row_config_controls_fn=render_longitudinal_reo_row_config_controls,
        agent_debug_log_fn=_agent_debug_log,
        render_longitudinal_reo_rows_fn=render_longitudinal_reo_rows,
        number_row_fn=number_row,
        reo_layout_mode=REO_LAYOUT_MODE,
        reo_counts_0_12=REO_COUNTS_0_12,
        reo_spacings=REO_SPACINGS,
        reo_bar_dias=REO_BAR_DIAS,
    )


def render_inputs_top_reinforcement_column_current_coordinator(
    *,
    col_top_reo,
    inputs_detailed_mode: bool,
    sync_callbacks: dict,
    fast_get_param,
    sec_shape_reo_ui,
    is_ti_reo_ui: bool,
    top_hdr: str,
) -> None:
    return render_inputs_top_reinforcement_column_module(
        st_module=st,
        col_top_reo=col_top_reo,
        inputs_detailed_mode=bool(inputs_detailed_mode),
        sync_callbacks=sync_callbacks,
        fast_get_param=fast_get_param,
        sec_shape_reo_ui=sec_shape_reo_ui,
        is_ti_reo_ui=bool(is_ti_reo_ui),
        top_hdr=top_hdr,
        longitudinal_reo_widget_audit_snapshot_fn=_longitudinal_reo_widget_audit_snapshot,
        get_widget_key_for_shared_fn=get_widget_key_for_shared,
        seed_widget_from_shared_fn=seed_widget_from_shared,
        recommendation_section_header_fn=_render_recommendation_section_header,
        render_longitudinal_reo_row_config_controls_fn=render_longitudinal_reo_row_config_controls,
        render_longitudinal_reo_rows_fn=render_longitudinal_reo_rows,
        number_row_fn=number_row,
        reo_layout_mode=REO_LAYOUT_MODE,
        reo_counts_0_12=REO_COUNTS_0_12,
        reo_spacings=REO_SPACINGS,
        reo_bar_dias=REO_BAR_DIAS,
    )


def render_inputs_shear_reinforcement_column_current_coordinator(
    *,
    col_shear_mat,
    inputs_detailed_mode: bool,
    fast_focus_section: str | None,
    corrected_invalid_shear_state: bool,
    sync_callbacks: dict,
) -> None:
    return render_inputs_shear_reinforcement_column_module(
        st_module=st,
        col_shear_mat=col_shear_mat,
        inputs_detailed_mode=bool(inputs_detailed_mode),
        fast_focus_section=fast_focus_section,
        corrected_invalid_shear_state=bool(corrected_invalid_shear_state),
        sync_callbacks=sync_callbacks,
        render_fast_next_hint_fn=_render_fast_next_hint,
        recommendation_section_header_fn=_render_recommendation_section_header,
        shear_recommendation_panel_fn=_render_shear_recommendation_panel,
        get_widget_key_for_shared_fn=get_widget_key_for_shared,
        shared_state_snapshot_fn=_shared_state_snapshot,
        request_shear_widget_seed_from_shared_fn=_request_shear_widget_seed_from_shared,
        seed_widget_from_shared_fn=seed_widget_from_shared,
        agent_debug_log_fn=_agent_debug_log,
        select_row_fn=select_row,
        number_row_fn=number_row,
        reo_bar_dias=REO_BAR_DIAS,
    )


def render_inputs_flange_reinforcement_current_coordinator(
    *,
    sync_callbacks: dict,
    fast_get_param,
) -> None:
    return render_inputs_flange_reinforcement_module(
        st_module=st,
        sync_callbacks=sync_callbacks,
        fast_get_param=fast_get_param,
        select_row_fn=select_row,
        number_row_fn=number_row,
        reo_bar_dias=REO_BAR_DIAS,
    )


def render_inputs_detailed_support_lower_row_current_coordinator(
    *,
    inputs_detailed_mode: bool,
    sync_callbacks: dict,
    fast_get_param,
    mark,
    sub_mark,
) -> None:
    return render_inputs_detailed_support_lower_row_module(
        st_module=st,
        inputs_detailed_mode=bool(inputs_detailed_mode),
        sync_callbacks=sync_callbacks,
        fast_get_param=fast_get_param,
        mark=mark,
        sub_mark=sub_mark,
        page_divider_fn=page_divider,
        materials_and_section_2d_fn=_render_materials_and_sectionA_2d,
        time_dependent_inputs_fn=_render_time_dependent_inputs,
        ducts_prestress_voids_inputs_fn=_render_ducts_prestress_voids_inputs,
        label_with_hover_fn=label_with_hover,
        number_row_fn=number_row,
    )


def render_inputs_post_widget_autopersist_current_coordinator(*, ss: dict) -> bool:
    skip_active_beam_record_write = bool(ss.get("_beam_skip_auto_persist_once", False))
    if skip_active_beam_record_write:
        ss["_beam_skip_auto_persist_once"] = False
    elif ss.get("inputs_dirty"):
        _apply_canonical_convenience_resync_to_shared_for_app_bridge(
            source="inputs_page:inputs_dirty_autopersist"
        )
        persist_active_beam_from_shared()
    return skip_active_beam_record_write


def render_inputs_widget_sections_current_coordinator(
    *,
    ss: dict,
    inputs_detailed_mode: bool,
    sync_callbacks: dict,
    inputs_render_audit: dict[str, str],
    fast_focus_section: str | None,
    fast_get_param,
    corrected_invalid_shear_state: bool,
    mark,
    sub_mark,
):
    return render_inputs_widget_sections_module(
        ss=ss,
        inputs_detailed_mode=bool(inputs_detailed_mode),
        sync_callbacks=sync_callbacks,
        inputs_render_audit=inputs_render_audit,
        fast_focus_section=fast_focus_section,
        fast_get_param=fast_get_param,
        corrected_invalid_shear_state=bool(corrected_invalid_shear_state),
        mark=mark,
        sub_mark=sub_mark,
        top_section_layout_slots_fn=render_inputs_top_section_layout_slots_coordinator,
        design_actions_section_fn=render_inputs_design_actions_section_current_coordinator,
        geometry_materials_top_section_fn=render_inputs_geometry_materials_top_section_current_coordinator,
        create_reinforcement_columns_fn=create_reinforcement_columns,
        get_section_shape_for_reinforcement_fn=get_inputs_section_shape_for_reinforcement,
        normalized_sec_shape_fn=normalized_sec_shape_ui,
        longitudinal_pair_labels_fn=main_longitudinal_reo_pair_labels,
        bottom_reinforcement_column_fn=render_inputs_bottom_reinforcement_column_current_coordinator,
        top_reinforcement_column_fn=render_inputs_top_reinforcement_column_current_coordinator,
        shear_reinforcement_column_fn=render_inputs_shear_reinforcement_column_current_coordinator,
        flange_reinforcement_fn=render_inputs_flange_reinforcement_current_coordinator,
        detailed_support_lower_row_fn=render_inputs_detailed_support_lower_row_current_coordinator,
        post_widget_autopersist_fn=render_inputs_post_widget_autopersist_current_coordinator,
    )


def render_inputs_summary_state_cache_current_coordinator(*, ss: dict, mark):
    return render_inputs_summary_state_cache_module(
        ss=ss,
        mark=mark,
        resolved_inputs_summary_state_fn=_resolved_inputs_summary_state,
        resolve_design_actions_fn=resolve_design_actions,
        design_guide_fp_fn=_get_design_guide_fp,
        hc_try_fn=hc_try,
        build_bending_pack_fn=build_bending_check_rows_from_state,
        build_shear_pack_fn=build_shear_check_rows_from_state,
        build_crack_pack_fn=build_crack_check_rows_from_state,
        build_deflection_pack_fn=build_deflection_check_rows_from_state,
    )


def hc_log(*args, **kwargs) -> None:
    _state_hc_log(*args, **kwargs)




def _pack_meta(name: str, pack):
    _ = name
    rows = (pack or {}).get("rows") or []
    return {
        "rows_n": len(rows),
        "uids": [row.get("uid") for row in rows][:30],
        "statuses": [row.get("status") for row in rows][:30],
    }


def render_inputs_summary_rows_from_packs_current_coordinator(
    *,
    bend_pack,
    shear_pack,
    crack_pack,
    defl_pack,
):
    return render_inputs_summary_rows_from_packs_module(
        st_module=st,
        bend_pack=bend_pack,
        shear_pack=shear_pack,
        crack_pack=crack_pack,
        defl_pack=defl_pack,
    )


def _overall_status_from_rows(rows):
    if not rows:
        return "\u2014", "rgba(31, 119, 180, 0.08)"
    filtered = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        if row.get("is_informational"):
            continue
        status = str(row.get("status", "")).upper()
        if status == "INFO":
            continue
        filtered.append(row)
    if not filtered:
        return "\u2014", "rgba(31, 119, 180, 0.08)"
    statuses = [str(row.get("status", "")).upper() for row in filtered]
    if any("FAIL" in status or status == "NG" for status in statuses):
        return "FAIL", "rgba(255,0,0,0.12)"
    if any("WARN" in status or "NEAR LIMIT" in status or status == "CHECK" for status in statuses):
        return "NEAR LIMIT", "rgba(255,193,7,0.15)"
    if any("PASS" in status or status == "OK" for status in statuses):
        return "PASS", "rgba(0,128,0,0.12)"
    return "\u2014", "rgba(31, 119, 180, 0.08)"


def _primary_row(rows):
    if not rows:
        return None
    for row in rows:
        if row.get("is_primary"):
            return row
    return rows[0]


def _parse_util_value(value) -> float | None:
    if value in (None, "", "\u2014"):
        return None
    try:
        return float(value)
    except Exception:
        try:
            return float(str(value).strip())
        except Exception:
            return None


def render_inputs_summary_display_state_current_coordinator(
    *,
    summary_state: dict,
    shear_pack,
    BENDING_ROWS,
    SHEAR_ROWS,
    CRACK_ROWS,
    DEFLECTION_ROWS,
):
    return render_inputs_summary_display_state_module(
        st_module=st,
        summary_state=summary_state,
        shear_pack=shear_pack,
        BENDING_ROWS=BENDING_ROWS,
        SHEAR_ROWS=SHEAR_ROWS,
        CRACK_ROWS=CRACK_ROWS,
        DEFLECTION_ROWS=DEFLECTION_ROWS,
        primary_row_fn=_primary_row,
        pick_governing_check_row_fn=pick_governing_check_row,
        overall_status_from_rows_fn=_overall_status_from_rows,
        parse_util_value_fn=_parse_util_value,
    )


def _design_guide_debug_has_coherent_overview(debug: dict | None) -> bool:
    if not isinstance(debug, dict):
        return False
    overview = debug.get("overview")
    return isinstance(overview, dict) and len(overview) > 0 and (
        "worst_util" in overview or "all_key_pass" in overview
    )


def _design_guide_debug_has_efficiency_state(debug: dict | None) -> bool:
    if not isinstance(debug, dict):
        return False
    efficiency_state = debug.get("efficiency_tightening_state")
    return isinstance(efficiency_state, dict) and "classification" in efficiency_state


def _design_guide_cached_debug_bundle_complete(debug: dict | None) -> bool:
    if not isinstance(debug, dict) or not debug:
        return False
    if not isinstance(debug.get("guidance_resolved_state"), dict):
        return False
    return _design_guide_debug_has_coherent_overview(debug) and _design_guide_debug_has_efficiency_state(debug)


_DESIGN_GUIDE_NON_CACHE_DEBUG_KEYS = frozenset(
    {
        "design_guide_presentation",
        "design_guide_feedback_status",
        "design_guide_feedback_reason",
        "design_guide_feedback_fail_fingerprint",
        "design_guide_current_fail_fingerprint",
        "design_guide_blocked_feedback_matches_current_state",
        "design_guide_stale_blocked_feedback_cleared",
        "design_guide_stale_blocked_feedback_reason",
        "design_guide_one_click_cta_suppressed",
        "design_guide_one_click_cta_suppressed_reason",
    }
)


def _get_cached_design_guide_guidance(fingerprint: tuple) -> tuple[list[dict], dict, bool]:
    def _debug_trustworthy(value: object) -> bool:
        debug = value if isinstance(value, dict) else None
        trust_decision = build_inputs_design_guide_cached_debug_trust_decision(
            bundle_complete=_design_guide_cached_debug_bundle_complete(debug),
            debug_publication_fingerprint=str(fingerprint),
            requested_fingerprint=str(fingerprint),
        )
        return bool(trust_decision.trustworthy)

    simple_cached_fp = st.session_state.get(DESIGN_GUIDE_SIMPLE_CACHE_FP_KEY)
    simple_cached_items = st.session_state.get(DESIGN_GUIDE_SIMPLE_CACHE_ITEMS_KEY)
    cached_fp = st.session_state.get(DESIGN_GUIDE_GUIDANCE_CACHE_FP_KEY)
    items = st.session_state.get(DESIGN_GUIDE_GUIDANCE_CACHE_ITEMS_KEY)
    debug = st.session_state.get(DESIGN_GUIDE_GUIDANCE_CACHE_DEBUG_KEY)
    cache_result = build_inputs_design_guide_guidance_cache_result(
        fingerprint=fingerprint,
        simple_cached_fp=simple_cached_fp,
        simple_cached_items=simple_cached_items,
        simple_debug=debug if isinstance(debug, dict) else {},
        simple_debug_trustworthy=_debug_trustworthy(debug),
        cached_fp=cached_fp,
        cached_items=items,
        cached_debug=debug if isinstance(debug, dict) else {},
        cached_debug_trustworthy=_debug_trustworthy(debug),
    )
    return list(cache_result.items), dict(cache_result.debug), bool(cache_result.cache_hit)


def _set_cached_design_guide_guidance(
    fingerprint: tuple,
    guidance_items: list[dict] | None,
    guidance_debug: dict | None,
) -> None:
    cache_plan = build_inputs_design_guide_guidance_cache_write_plan(
        fingerprint=fingerprint,
        guidance_items=guidance_items,
        guidance_debug=guidance_debug,
        non_cache_debug_keys=_DESIGN_GUIDE_NON_CACHE_DEBUG_KEYS,
    )
    st.session_state[DESIGN_GUIDE_SIMPLE_CACHE_FP_KEY] = cache_plan.fingerprint
    st.session_state[DESIGN_GUIDE_SIMPLE_CACHE_ITEMS_KEY] = list(cache_plan.guidance_items or [])
    st.session_state[DESIGN_GUIDE_GUIDANCE_CACHE_FP_KEY] = cache_plan.fingerprint
    st.session_state[DESIGN_GUIDE_GUIDANCE_CACHE_ITEMS_KEY] = list(cache_plan.guidance_items or [])
    st.session_state[DESIGN_GUIDE_GUIDANCE_CACHE_DEBUG_KEY] = dict(cache_plan.cache_debug)


def render_inputs_summary_guidance_cache_current_coordinator(
    *,
    summary_state: dict,
    summary_state_debug: dict,
):
    if DESIGN_GUIDE_SIMPLE_CACHE_ITEMS_KEY not in st.session_state:
        st.session_state[DESIGN_GUIDE_SIMPLE_CACHE_ITEMS_KEY] = None
    if DESIGN_GUIDE_SIMPLE_CACHE_FP_KEY not in st.session_state:
        st.session_state[DESIGN_GUIDE_SIMPLE_CACHE_FP_KEY] = None
    summary_fp = _get_design_guide_fp(summary_state)
    summary_guidance_items, _, summary_guidance_cache_hit = _get_cached_design_guide_guidance(summary_fp)
    if not summary_guidance_cache_hit:
        summary_guidance_payload = _compute_design_guidance_items(
            summary_state,
            guidance_debug_verbose=False,
            debug_enabled=False,
        )
        summary_guidance_items = list(summary_guidance_payload.get("guidance_items") or [])
        summary_debug = dict(summary_guidance_payload.get("debug_trace") or {})
        summary_debug["design_guide_render_state_source"] = "lightweight_overlay_state"
        _set_cached_design_guide_guidance(
            summary_fp,
            summary_guidance_items,
            summary_debug,
        )
    summary_state_debug["design_guide_render_state_source"] = "lightweight_overlay_state"
    governing_check = summary_guidance_items[0].get("check_key") if summary_guidance_items else None
    return summary_guidance_items, governing_check


def render_inputs_summary_row_finalization_current_coordinator(
    *,
    skip_active_beam_record_write: bool,
    BENDING_ROWS,
    SHEAR_ROWS,
    CRACK_ROWS,
    DEFLECTION_ROWS,
) -> None:
    for rows, route in (
        (BENDING_ROWS, "bending"),
        (SHEAR_ROWS, "shear"),
        (CRACK_ROWS, "crack"),
        (DEFLECTION_ROWS, "deflection"),
    ):
        for row in rows:
            if row.get("is_informational") or str(row.get("status", "")).upper() == "INFO":
                row["ok"] = None
            elif "ok" not in row:
                status = row.get("status", "-")
                row["ok"] = True if status == "PASS" else False if status in ("FAIL", "NG", "NEAR LIMIT") else None
            row.setdefault("route_page", route)
            uid = str(row.get("uid") or "")
            if not row.get("tab"):
                if route == "bending" and uid in BENDING_ROW_UID_TO_TAB:
                    row["tab"] = BENDING_ROW_UID_TO_TAB[uid]
                elif route == "shear" and uid in SHEAR_ROW_UID_TO_TAB:
                    row["tab"] = SHEAR_ROW_UID_TO_TAB[uid]

    if not skip_active_beam_record_write:
        update_active_beam_summary_from_results(
            bending_rows=BENDING_ROWS,
            shear_rows=SHEAR_ROWS,
            crack_rows=CRACK_ROWS,
            deflection_rows=DEFLECTION_ROWS,
        )


def render_inputs_calculation_explainer_trace_coordinator(
    *,
    BENDING_ROWS,
    SHEAR_ROWS,
    CRACK_ROWS,
    DEFLECTION_ROWS,
    results_version: int,
    summary_action_fp,
    trace_fn,
) -> None:
    render_inputs_calculation_explainer_trace_module(
        st_module=st,
        BENDING_ROWS=BENDING_ROWS,
        SHEAR_ROWS=SHEAR_ROWS,
        CRACK_ROWS=CRACK_ROWS,
        DEFLECTION_ROWS=DEFLECTION_ROWS,
        results_version=results_version,
        summary_action_fp=summary_action_fp,
        trace_fn=trace_fn,
    )


def _inputs_pre_widget_trace(*args, **kwargs):
    block = args[0] if args else kwargs.pop("block", "")
    payload = dict(kwargs or {})
    if os.environ.get("PERF_TRACE_INPUTS", "").strip().lower() not in (
        "1",
        "true",
        "yes",
        "on",
    ):
        return None
    label = str(block or "").strip()
    if not label:
        return None
    try:
        path = st.session_state.get("_inputs_pre_widget_trace_path")
        if not path:
            os.makedirs(os.path.join("artifacts", "performance"), exist_ok=True)
            stamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
            path = os.path.join(
                "artifacts",
                "performance",
                f"inputs_pre_widget_trace_{stamp}.jsonl",
            )
            st.session_state["_inputs_pre_widget_trace_path"] = path
        row = {
            "block": label,
            "timestamp": datetime.now().isoformat(timespec="milliseconds"),
            **payload,
        }
        with open(path, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(row, default=str, sort_keys=True) + "\n")
    except Exception:
        pass
    return None


def render_inputs_summary_container_current_coordinator(
    *,
    summary_container,
    sync_callbacks: dict,
    BENDING_ROWS,
    SHEAR_ROWS,
    CRACK_ROWS,
    DEFLECTION_ROWS,
    defl_pack,
    governing_check,
    bending_cap,
    bending_demand,
    bending_util_str,
    bending_status,
    bending_colour,
    shear_cap,
    shear_demand,
    shear_util_str,
    shear_status,
    shear_colour,
    shear_summary_status_note,
    shear_governing_name,
    shear_governing_source,
    shear_reason,
    crack_cap,
    crack_demand,
    crack_util_str,
    crack_status,
    crack_colour,
    defl_cap,
    defl_demand,
    defl_util_str,
    defl_status,
    defl_colour,
) -> None:
    payload = dict(locals())
    payload.update(
        {
            "st_module": st,
            "result_cache_key": RESULT_CACHE_KEY,
            "inputs_show_landing_dashboard_fn": inputs_show_landing_dashboard,
            "render_landing_card_fn": render_landing_card,
            "render_summary_expanders_and_tables_fn": render_inputs_summary_expanders_and_tables_current_coordinator,
        }
    )
    render_inputs_summary_container_current_module(**payload)


def render_inputs_summary_pipeline_current_coordinator(
    *,
    ss: dict,
    summary_container,
    sync_callbacks: dict,
    skip_active_beam_record_write: bool,
    mark,
) -> None:
    render_inputs_summary_pipeline_module(
        ss=ss,
        st_module=st,
        summary_container=summary_container,
        sync_callbacks=sync_callbacks,
        skip_active_beam_record_write=skip_active_beam_record_write,
        mark=mark,
        summary_state_cache_fn=render_inputs_summary_state_cache_current_coordinator,
        pack_meta_fn=_pack_meta,
        hc_log_fn=hc_log,
        summary_rows_from_packs_fn=render_inputs_summary_rows_from_packs_current_coordinator,
        summary_display_state_fn=render_inputs_summary_display_state_current_coordinator,
        summary_guidance_cache_fn=render_inputs_summary_guidance_cache_current_coordinator,
        summary_row_finalization_fn=render_inputs_summary_row_finalization_current_coordinator,
        calculation_explainer_trace_fn=render_inputs_calculation_explainer_trace_coordinator,
        summary_container_fn=render_inputs_summary_container_current_coordinator,
        pre_widget_trace_fn=_inputs_pre_widget_trace,
    )


def render_inputs_post_summary_actions_and_dev_audit_current_coordinator(
    *,
    inputs_render_audit: dict[str, str],
) -> None:
    render_inputs_post_summary_actions_and_dev_audit_module(
        st_module=st,
        inputs_render_audit=inputs_render_audit,
        inject_scroll_to_design_actions_fn=_inputs_inject_scroll_to_design_actions,
        apply_buttons_fn=_handle_inputs_apply_buttons_current_coordinator,
        auto_design_fn=_handle_inputs_auto_design_current_coordinator,
        agent_debug_log_fn=_agent_debug_log,
    )


def render_inputs_debug_audit_current_coordinator(*, before_state) -> None:
    render_inputs_debug_audit_module(
        inputs_debug_audit=_INPUTS_DEBUG_AUDIT,
        before_state=before_state,
        st_module=st,
        input_page_tab_keys=INPUTS_PAGE_TAB_KEYS,
        shared_defaults=SHARED_DEFAULTS,
        log_debug_fn=log_debug,
    )


def render_design_guide_debug_sidebar_current_coordinator() -> None:
    render_design_guide_debug_sidebar(
        st_module=st,
        sidebar_debug_enabled_fn=_design_guide_sidebar_debug_enabled,
        clear_transient_ui_state_fn=_clear_design_guide_transient_ui_state,
        auto_design_invoke_debug_snapshot_fn=_auto_design_invoke_debug_snapshot,
        debug_bundle_key=DESIGN_GUIDE_DEBUG_BUNDLE_KEY,
        reco_trace_key=DESIGN_GUIDE_RECO_TRACE_KEY,
    )


def render_inputs_tail_current_coordinator(
    *,
    inputs_render_audit: dict[str, str],
    before_state,
    mark,
    perf_start,
    perf_marks,
    sub_marks,
    t0,
) -> None:
    render_inputs_tail_module(
        inputs_render_audit=inputs_render_audit,
        before_state=before_state,
        mark=mark,
        perf_start=perf_start,
        perf_marks=perf_marks,
        sub_marks=sub_marks,
        t0=t0,
        post_summary_actions_fn=render_inputs_post_summary_actions_and_dev_audit_current_coordinator,
        debug_audit_fn=render_inputs_debug_audit_current_coordinator,
        design_guide_debug_sidebar_fn=render_design_guide_debug_sidebar_current_coordinator,
        perf_finalization_fn=render_inputs_perf_finalization_current_coordinator,
    )


__all__ = [
    "render_design_guide_debug_sidebar_current_coordinator",
    "_inputs_pre_widget_trace",
    "_pack_meta",
    "hc_log",
    "render_inputs_debug_audit_current_coordinator",
    "render_inputs_calculation_explainer_trace_coordinator",
    "render_inputs_perf_finalization_current_coordinator",
    "render_inputs_page_setup_current_coordinator",
    "render_inputs_post_summary_actions_and_dev_audit_current_coordinator",
    "render_inputs_summary_container_current_coordinator",
    "render_inputs_summary_display_state_current_coordinator",
    "render_inputs_summary_guidance_cache_current_coordinator",
    "render_inputs_summary_pipeline_current_coordinator",
    "render_inputs_summary_row_finalization_current_coordinator",
    "render_inputs_summary_rows_from_packs_current_coordinator",
    "render_inputs_summary_state_cache_current_coordinator",
    "render_inputs_tail_current_coordinator",
    "render_inputs_widget_sections_current_coordinator",
]
