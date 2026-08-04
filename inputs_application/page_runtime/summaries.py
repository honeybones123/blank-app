"""Permanent Inputs page summaries runtime."""

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

from application.design_result_store import AuthoritativeDesignResultStore

from application.design_run_coordinator import ensure_design_result

from application.engineering_snapshot import build_engineering_input_snapshot_from_resolved_state

from application.guidance_result_adapter import build_authoritative_design_result_from_guidance_payload, guidance_payload_from_authoritative_design_result

from inputs_application.state_utils import application_guidance_context, bottom_reo_state_label, float_from_state, guidance_state_snapshot, shared_state_snapshot, shear_state_label, updates_match_state

from inputs_application.recommendation_support import design_optimisation_goal_label, resolve_geometry_width_context, severe_shear_failure, shear_severity_band

from inputs_application.recommendation_cache import resolve_popover_recommendation

from inputs_application.recommendation_envelope import attach_recommendation_envelope, recommendation_blocked_reason

from inputs_application.live_apply import execute_typed_apply

from inputs_application.post_apply_state import rehydrate_typed_post_apply_acceptance

from inputs_application.guidance_ui_state import prepare_guidance_ui_state

from inputs_application.design_guide_fingerprint import design_guide_fingerprint

from inputs_application.recommendation_evaluation import effective_bottom_design_state, evaluate_bending_with_bottom_state, evaluate_shear_with_state

from inputs_application.popover_recommendation_apply import execute_popover_recommendation_apply

from inputs_application.shear_widget_reconciliation import ShearWidgetReconciliationRuntime, reconcile_shear_widgets_with_shared

from inputs_application.summary_state_runtime import InputsSummaryStateRuntime, resolve_inputs_summary_state

from inputs_application.widget_state_projection import merge_current_engineering_widget_state

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

from inputs_application.guidance_entrypoint import (
    build_guidance_entrypoint_runtime,
    compute_inputs_guidance,
)


from inputs_page_modules.diagrams import (
    InputsDiagramSourceSnapshot,
    build_inputs_diagram_view_model,
    render_inputs_3d_diagram_block,
    render_inputs_fast_model_block,
    render_inputs_section_2d_diagram_block,
)

from inputs_page_modules.fragments import run_inputs_fragment

from inputs_page_modules.diagrams.source_projection import build_section_outline_points_and_bbox as build_section_outline_points_and_bbox_module

from inputs_page_modules.design_guide import render_design_guide_panel_orchestration

from inputs_page_modules.design_guide import current_coordinators as design_guide_current_coordinators

from inputs_page_modules.design_guide.debug_sidebar import render_design_guide_debug_sidebar

from inputs_page_modules.design_guide.trace import append_design_guide_trace as append_design_guide_trace_module, design_guide_tracer_path as design_guide_tracer_path_module, design_guide_tracer_verbose_log as design_guide_tracer_verbose_log_module

from inputs_page_modules.design_guide.apply_trace_session import DESIGN_GUIDE_APPLY_TRACE_RUN_ID_KEY, begin_design_guide_apply_trace, end_design_guide_apply_trace, set_design_guide_live_breadcrumb

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

from inputs_page_modules.auto_design_routing import AutoDesignRoutingRuntime, handle_inputs_auto_design

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

from inputs_page_modules.recommendation_panels import (
    render_bottom_recommendation_panel,
    render_geometry_recommendation_panel,
    render_shear_recommendation_panel,
)

from inputs_page_modules.summaries import render_inputs_summary_expanders_and_tables_current_coordinator

from inputs_page_modules.summaries.render_coordinators import render_inputs_summary_container_current as render_inputs_summary_container_current_module

from inputs_page_modules.summaries.display_state import render_inputs_summary_display_state as render_inputs_summary_display_state_module

from inputs_page_modules.design_guide.render_eligibility import should_render_design_guide_slot_from_publication_eligibility

from inputs_page_modules.recommendation_runtime import compute_bottom_recommendation_for_page, compute_geometry_recommendation_for_page, compute_shear_recommendation_for_page

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
    _GUIDANCE_ENTRYPOINT_RUNTIME,
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

def render_inputs_summary_state_cache_current_coordinator(
    *,
    ss: dict,
    mark,
    region_context=None,
):
    def _summary_state_source():
        if region_context is not None:
            summary_inputs = dict(region_context.resolved_inputs)
            actions = dict(region_context.actions_used)
            summary_inputs.update(
                {
                    "Mu_star": actions.get(
                        "Mu_signed",
                        actions.get("Mu", 0.0),
                    ),
                    "Vu_star": actions.get(
                        "Vu",
                        0.0,
                    ),
                    "Tu_star": actions.get(
                        "Tu",
                        0.0,
                    ),
                    "sls_Mstar": actions.get(
                        "SLS_M_signed",
                        actions.get("SLS_M", 0.0),
                    ),
                    "sls_Vstar": actions.get(
                        "SLS_V",
                        0.0,
                    ),
                }
            )
            return summary_inputs, {
                "summary_state_source": "typed_summary_region_context",
                "summary_state_engineering_hash": (
                    region_context.identity.engineering_hash
                ),
                "summary_state_input_revision": (
                    region_context.identity.input_revision
                ),
                "summary_authoritative_result_remains_publication_source": True,
            }
        authoritative_result = AuthoritativeDesignResultStore(
            st.session_state
        ).current()
        authoritative_inputs = (
            dict(authoritative_result.current_calculations or {}).get(
                "resolved_inputs"
            )
            if authoritative_result is not None
            else None
        )
        if isinstance(authoritative_inputs, dict) and authoritative_inputs:
            return dict(authoritative_inputs), {
                "summary_state_source": "authoritative_design_result",
                "summary_state_engineering_hash": (
                    authoritative_result.engineering_hash
                ),
                "summary_authoritative_result_remains_publication_source": True,
            }
        # Startup/no-result fallback. Once an engineering transaction exists,
        # Summary consumes its resolved input snapshot above.
        resolved_inputs, summary_debug = _resolved_inputs_summary_state()
        shared_only_mode = bool(
            (summary_debug or {}).get("summary_shared_only_mode")
        )
        resolved_inputs, overlay_keys = merge_current_engineering_widget_state(
            resolved_inputs,
            st.session_state,
            INPUTS_PAGE_TAB_KEYS,
            shared_only_mode=shared_only_mode,
        )
        return dict(resolved_inputs), {
            **dict(summary_debug or {}),
            "summary_state_source": "current_widget_resolved_inputs",
            "pre_widget_engineering_widget_bridge": {
                "applied": bool(overlay_keys),
                "shared_only_suppressed": shared_only_mode,
                "overlay_keys": list(overlay_keys),
                "source": (
                    "current_inputs_widget_snapshot"
                    if overlay_keys
                    else "resolved_shared_snapshot"
                ),
            },
            "summary_authoritative_result_remains_publication_source": True,
        }

    return render_inputs_summary_state_cache_module(
        ss=ss,
        mark=mark,
        resolved_inputs_summary_state_fn=_summary_state_source,
        resolve_design_actions_fn=resolve_design_actions,
        design_guide_fp_fn=design_guide_fingerprint,
        hc_try_fn=hc_try,
        build_bending_pack_fn=build_bending_check_rows_from_state,
        build_shear_pack_fn=build_shear_check_rows_from_state,
        build_crack_pack_fn=build_crack_check_rows_from_state,
        build_deflection_pack_fn=build_deflection_check_rows_from_state,
        authoritative_packs=(
            dict(region_context.packs)
            if region_context is not None
            else None
        ),
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

def render_inputs_summary_guidance_cache_current_coordinator(
    *,
    summary_state: dict,
    summary_state_debug: dict,
):
    authoritative_result = AuthoritativeDesignResultStore(st.session_state).current()
    try:
        authoritative_snapshot = build_engineering_input_snapshot_from_resolved_state(
            dict(summary_state or {}),
            contract_versions={
                "design_guide": str(DESIGN_GUIDE_ALGORITHM_VERSION),
                "family_classification": str(
                    (load_family_classification_contract().get("contract_identity") or {}).get(
                        "contract_version"
                    )
                    or ""
                ),
            },
            calculation_versions={"summary_resolver": "resolved_inputs_summary_state.v1"},
        )
    except Exception:
        authoritative_snapshot = None
    summary_guidance_items: list[dict] = []
    authoritative_match = bool(
        authoritative_result is not None
        and authoritative_snapshot is not None
        and authoritative_result.engineering_hash == authoritative_snapshot.engineering_hash
    )
    if authoritative_match:
        authoritative_payload = guidance_payload_from_authoritative_design_result(authoritative_result)
        summary_guidance_items = list(authoritative_payload.get("guidance_items") or [])
    summary_state_debug["design_guide_render_state_source"] = (
        "authoritative_design_result_store" if authoritative_match else "authoritative_result_unavailable"
    )
    summary_guidance_cache_hit = authoritative_match
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

def render_inputs_summary_container_current_coordinator(
    *,
    summary_container,
    sync_callbacks: dict,
    render_title: bool = True,
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
    render_title: bool = True,
    region_context=None,
):
    return render_inputs_summary_pipeline_module(
        ss=ss,
        st_module=st,
        summary_container=summary_container,
        sync_callbacks=sync_callbacks,
        skip_active_beam_record_write=skip_active_beam_record_write,
        mark=mark,
        render_title=render_title,
        region_context=region_context,
        summary_state_cache_fn=render_inputs_summary_state_cache_current_coordinator,
        pack_meta_fn=_pack_meta,
        hc_log_fn=hc_log,
        summary_rows_from_packs_fn=render_inputs_summary_rows_from_packs_current_coordinator,
        summary_display_state_fn=render_inputs_summary_display_state_current_coordinator,
        summary_guidance_cache_fn=render_inputs_summary_guidance_cache_current_coordinator,
        summary_row_finalization_fn=render_inputs_summary_row_finalization_current_coordinator,
        summary_container_fn=render_inputs_summary_container_current_coordinator,
    )
