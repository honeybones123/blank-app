"""Permanent Inputs page batch runtime."""

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

import design_guide_page

from inputs_application.policy_constants import DESIGN_GUIDE_LAST_APPLY_ROUTE_KEY

from inputs_application.design_guide_fingerprint import DESIGN_GUIDE_ALGORITHM_VERSION


from application.design_run_coordinator import ensure_design_result

from application.engineering_snapshot import build_engineering_input_snapshot_from_resolved_state

from application.guidance_result_adapter import guidance_payload_from_authoritative_design_result

from inputs_application.state_utils import application_guidance_context, bottom_reo_state_label, float_from_state, guidance_state_snapshot, shared_state_snapshot, shear_state_label, updates_match_state

from inputs_application.recommendation_support import design_optimisation_goal_label, resolve_geometry_width_context, severe_shear_failure, shear_severity_band

from inputs_application.recommendation_envelope import attach_recommendation_envelope, recommendation_blocked_reason

from inputs_application.live_apply import execute_typed_apply

from inputs_application.post_apply_state import rehydrate_typed_post_apply_acceptance

from inputs_application.guidance_ui_state import prepare_guidance_ui_state

from inputs_application.design_guide_fingerprint import design_guide_fingerprint

from inputs_application.shear_widget_reconciliation import ShearWidgetReconciliationRuntime, reconcile_shear_widgets_with_shared

from inputs_application.summary_state_runtime import InputsSummaryStateRuntime, resolve_inputs_summary_state

from inputs_application.canonical_runtime_contracts import CanonicalConvenienceResyncRuntime, CanonicalDesignStatePackRuntime
from inputs_page_modules.app_bridge.canonical_convenience_resync import _apply_canonical_convenience_resync_to_shared, convenience_scalar_differs

from inputs_page_modules.app_bridge.canonical_design_state_pack import _build_canonical_design_state_pack_for_app_bridge as build_canonical_design_state_pack

from bending_checks_helpers import build_bending_check_rows_from_state

from batch_design.ui.project_beam_manager_adapters import (
    beam_option_labels as build_batch_beam_option_labels,
    build_beam_schedule_df as build_batch_beam_schedule_df,
    build_schedule_export_df as build_batch_schedule_export_df,
    build_schedule_preview_df as build_batch_schedule_preview_df,
    format_beam_status_badge as format_batch_beam_status_badge,
    format_last_checked as format_batch_last_checked,
    publish_batch_design_results_to_beam_records,
    sync_beam_records_from_schedule_df as sync_batch_beam_records_from_schedule_df,
)

from batch_design.design_brain_adapter import BatchDesignGuidanceAdapter

from batch_design.ui.page import BatchDesignPageContext, render_batch_design_page

from crack_checks_helpers import build_crack_check_rows_from_state, pick_governing_check_row

from deflection_checks_helpers import build_deflection_check_rows_from_state

from application.contracts.design_policy import DESIGN_OPTIMISATION_GOAL_LABELS, resolve_design_optimisation_goal

from application.contracts.family_classification import load_family_classification_contract

from engineering_check_ui import BENDING_ROW_UID_TO_TAB, SHEAR_ROW_UID_TO_TAB

from inputs_application.one_click_entrypoint import run_one_click_auto_design

from inputs_page_modules.calculations import render_inputs_calculation_explainer_trace as render_inputs_calculation_explainer_trace_module

from inputs_page_modules.diagrams import (
    InputsDiagramSourceSnapshot,
    build_inputs_diagram_view_model,
    render_inputs_3d_diagram_block,
    render_inputs_fast_model_block,
    render_inputs_section_2d_diagram_block,
)

from inputs_page_modules.fragments import run_inputs_fragment

from inputs_page_modules.diagrams.source_projection import build_section_outline_points_and_bbox as build_section_outline_points_and_bbox_module

from inputs_application.v2_design_brain_ui_boundary import (
    DESIGN_GUIDE_APPLY_TRACE_RUN_ID_KEY,
    append_design_guide_trace as append_design_guide_trace_module,
    begin_design_guide_apply_trace,
    design_guide_tracer_path as design_guide_tracer_path_module,
    design_guide_tracer_verbose_log as design_guide_tracer_verbose_log_module,
    end_design_guide_apply_trace,
    render_design_guide_debug_sidebar,
    render_design_guide_panel_orchestration,
    set_design_guide_live_breadcrumb,
)

from inputs_application.state_projection import (
    build_auto_design_governing_fingerprint as build_auto_design_governing_fingerprint_module,
    build_guidance_state_snapshot as build_guidance_state_snapshot_module,
)

from inputs_page_modules.session import (
    build_inputs_auto_design_invoke_debug_snapshot,
    build_inputs_design_guide_dirty_mark_plan,
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

from inputs_page_modules.apply_routing import handle_inputs_apply_buttons

from inputs_page_modules.landing import (
    inputs_has_design_actions_or_loads,
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

from inputs_page_modules.summaries import render_inputs_summary_expanders_and_tables_current_coordinator

from inputs_page_modules.summaries.render_coordinators import render_inputs_summary_container_current as render_inputs_summary_container_current_module

from inputs_page_modules.summaries.display_state import render_inputs_summary_display_state as render_inputs_summary_display_state_module

from inputs_application.v2_design_brain_ui_boundary import should_render_design_guide_slot_from_publication_eligibility

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
    _request_inputs_engineering_commit,
    _write_sync_trace_line,
    add_new_beam_record,
    delete_beam_record,
    duplicate_active_beam_record,
    ensure_beam_project_initialized,
    finalize_auto_design_publish,
    get_sync_callbacks,
    get_active_beam_summary,
    get_deflection_limit_label_from_ratio,
    get_deflection_limit_ratio,
    get_param,
    get_widget_key_for_shared,
    build_legacy_longitudinal_mirrors_from_rows,
    apply_beam_project_param_snapshot,
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
    ux_probe_record,
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

from inputs_application.page_runtime.common import (
    AUTO_DESIGN_AUTO_INVOKE_KEY,
    AUTO_DESIGN_REQUEST_SOURCE_KEY,
    AUTO_DESIGN_REQUEST_TS_KEY,
    DEBUG_DESIGN_GUIDANCE_PROBE,
    DESIGN_GUIDE_APPLY_BANNER_KEY,
    DESIGN_GUIDE_APPLY_BANNER_META_KEY,
    DESIGN_GUIDE_DEBUG_BUNDLE_KEY,
    DESIGN_GUIDE_FIRST_TARGET_BAND_STEP_KEY,
    DESIGN_GUIDE_HISTORY_ANCHOR_KEY,
    DESIGN_GUIDE_NEEDS_REFRESH_KEY,
    DESIGN_GUIDE_PENDING_STEP_CTX_KEY,
    DESIGN_GUIDE_RANK_TRACE_KEY,
    DESIGN_GUIDE_RECO_TRACE_KEY,
    DESIGN_GUIDE_SIDEBAR_DEBUG_TOGGLE_KEY,
    DESIGN_GUIDE_STEP_HISTORY_KEY,
    INPUTS_PAGE_TAB_KEYS,
    K_D_OPTIONS,
    K_V_METHOD_OPTIONS,
    MODEL_RENDER_FINGERPRINT_KEYS,
    PRIMARY_GEOMETRY_KEYS,
    REO_BAR_DIAS,
    REO_COUNTS_0_12,
    REO_LAYOUT_MODE,
    REO_SPACINGS,
    RESULT_CACHE_KEY,
    _AGENT_DEBUG_LOG_PATH,
    _INPUTS_DEBUG_AUDIT,
    _INPUTS_DESIGN_ACTIONS_ANCHOR_ID,
    _INPUTS_PENDING_NAV_PAGE_SLUG_KEY,
    _INPUTS_SCROLL_DESIGN_ACTIONS_FLAG,
    _agent_debug_log,
    _append_design_guide_trace,
    _apply_canonical_convenience_resync,
    _auto_design_governing_fingerprint,
    _build_canonical_design_state_pack,
    _build_inputs_diagram_source_snapshot,
    _clear_auto_design_runtime_latches,
    _clear_design_guide_transient_ui_state,
    _compute_design_guidance_items,
    _debug_check_design_action_consistency,
    _debug_resolved_guidance_actions,
    _design_action_widget_specs,
    _design_guide_sidebar_debug_enabled,
    _design_guide_tracer_path,
    _design_guide_tracer_verbose_log,
    _execute_authoritative_apply_current_coordinator,
    _force_inputs_apply_refresh_cycle,
    _get_outline_points_and_bbox,
    _get_sec_shape,
    _guidance_state_snapshot,
    _handle_inputs_apply_buttons_current_coordinator,
    _inputs_pre_widget_trace,
    _invalidate_design_guide_caches,
    _is_inputs_longitudinal_reo_widget_key,
    _longitudinal_reo_widget_audit_snapshot,
    _mark_design_guide_dirty,
    _parse_util_value,
    _queue_inputs_refresh,
    _reconcile_design_action_widgets_with_shared,
    _record_inputs_diagram_view_model_trace,
    _record_inputs_rerun_trigger,
    _request_shear_widget_seed_from_shared,
    _reseed_inputs_longitudinal_reo_widgets_from_shared,
    _resolve_design_actions_from_state,
    _resolved_inputs_summary_state,
    _shared_state_snapshot,
    _shared_toggle,
    _sync_auto_design_invalidation,
    _sync_design_action_widget_to_shared,
    cached_make_section_figure,
    inputs_hydration_trace_log,
    log_debug,
    make_beam_3d_figure,
    make_summary_cross_section_figure,
)

def save_active_batch_beam_to_table() -> None:
    _apply_canonical_convenience_resync(
        source="beam_manager:save_active_to_table"
    )
    persist_active_beam_from_shared()
    st.session_state["_beam_skip_auto_persist_once"] = False


def activate_batch_project_beam(beam_id: str) -> bool:
    """Switch the active batch beam and commit its full input snapshot.

    ``set_active_beam`` performs the storage hydration.  This coordinator is
    the application boundary that also aligns the revisioned input snapshot,
    ensuring every page sees the selected beam's actions, dimensions and
    reinforcement immediately rather than waiting for a later widget edit.
    """

    changed = set_active_beam(beam_id)
    if not changed:
        return False
    _apply_canonical_convenience_resync(
        source="batch_design:activate_project_beam"
    )
    _request_inputs_engineering_commit("inputs_batch_design_activate_beam")
    return True


def publish_batch_design_results(results) -> set[str]:
    """Persist V2 batch proposals and promote an active one to app state."""

    updated_beam_ids = publish_batch_design_results_to_beam_records(results)
    active_beam_id = str(st.session_state.get("active_beam_id") or "").strip()
    if active_beam_id not in updated_beam_ids:
        return updated_beam_ids

    active_record = dict(
        (st.session_state.get("beam_records") or {}).get(active_beam_id) or {}
    )
    meta = dict(active_record.get("meta") or {})
    if not (
        isinstance(meta.get("batch_design_applied_updates"), dict)
        or str(meta.get("auto_design_source_beam_id") or "").strip()
    ):
        # V2 did not accept a proposal for this row. Keep its current
        # engineering state untouched rather than manufacturing a new input
        # revision from a failed/exhausted batch result.
        return updated_beam_ids
    params = dict(active_record.get("params") or {})
    if not params:
        return updated_beam_ids

    # The Batch button is the explicit auto-design action.  Once V2 has
    # accepted a proposal for the active member, hydrate the exact persisted
    # result and commit it as the next authoritative input revision so all
    # pages, diagrams and calculations immediately agree with the table.
    apply_beam_project_param_snapshot(params)
    _apply_canonical_convenience_resync(
        source="batch_design:apply_active_verified_proposal"
    )
    # Batch Run redraws inside the Inputs fragment.  A fragment redraw does
    # not pass through app.py's top-level widget hydration, leaving the old
    # ``inputs_*`` values able to win the model-preview overlay even though
    # the calculation has already committed the V2 proposal.  Reseed now,
    # from this exact active-beam snapshot, before the local redraw.
    _force_inputs_apply_refresh_cycle(
        "batch_design:apply_active_verified_proposal"
    )
    # Give the Batch editor a fresh widget identity on its next render.
    # Reusing its pre-design identity lets Streamlit replay the old table
    # frame into auto-save, overwriting this proposal and causing a rerun
    # loop.  The record above remains the sole authoritative source.
    st.session_state["_batch_design_project_beam_editor_epoch"] = (
        int(st.session_state.get("_batch_design_project_beam_editor_epoch", 0) or 0)
        + 1
    )
    st.session_state["_force_hydrate_widgets_after_beam_load"] = True
    _request_inputs_engineering_commit("inputs_batch_design_apply_proposal")
    return updated_beam_ids


def sync_batch_project_beam_editor_auto_save(schedule_df) -> set[str]:
    """Commit project-table edits without a second manual save action.

    The table owns the stored beam record.  When its active row changes, the
    row is first hydrated into the shared input model and then promoted through
    the same canonical input transaction used by ordinary Inputs widgets.
    """

    changed_beam_ids = sync_batch_beam_records_from_schedule_df(schedule_df)
    if not changed_beam_ids:
        return changed_beam_ids

    active_beam_id = str(st.session_state.get("active_beam_id") or "").strip()
    if active_beam_id and active_beam_id in changed_beam_ids:
        record = dict(
            (st.session_state.get("beam_records") or {}).get(active_beam_id)
            or {}
        )
        apply_beam_project_param_snapshot(dict(record.get("params") or {}))
        _request_inputs_engineering_commit(
            "inputs_batch_design_project_beam_table",
        )
    else:
        # Non-active rows still need to survive navigation/refresh immediately.
        persist_state_snapshot()
    return changed_beam_ids

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
            set_active_beam=activate_batch_project_beam,
            add_beam=add_new_beam_record,
            duplicate_beam=duplicate_active_beam_record,
            delete_beam=delete_beam_record,
            reset_workspace=reset_app_to_clean_starter_workspace,
            force_refresh=_force_inputs_apply_refresh_cycle,
            log_rerun=render_inputs_beam_load_triggered_rerun_log_coordinator,
            save_active_to_table=save_active_batch_beam_to_table,
            apply_resync=_apply_canonical_convenience_resync,
            build_schedule_preview_df=build_batch_schedule_preview_df,
            build_schedule_editor_df=build_batch_beam_schedule_df,
            sync_schedule_editor_df=sync_batch_project_beam_editor_auto_save,
            publish_batch_design_results=publish_batch_design_results,
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
