"""Permanent Inputs page setup runtime."""

from __future__ import annotations

import copy

import html

import os

import json

import time

from datetime import datetime

from pathlib import Path

from typing import Any

from uuid import uuid4

import streamlit as st

import design_guide_page


from inputs_application.design_guide_fingerprint import DESIGN_GUIDE_ALGORITHM_VERSION

from application.design_run_coordinator import ensure_design_result

from application.engineering_snapshot import build_engineering_input_snapshot_from_resolved_state

from application.guidance_result_adapter import guidance_payload_from_authoritative_design_result

from application.contracts.design_brain import (
    AuthoritativeDesignResult,
    coerce_authoritative_design_result,
)
from application.design_brain_port import DesignBrainRequest

from inputs_application.action_source_control import (
    authoritative_action_source_projection,
    uses_load_analysis_actions,
)

from inputs_application.state_utils import application_guidance_context, bottom_reo_state_label, float_from_state, guidance_state_snapshot, shared_state_snapshot, shear_state_label, updates_match_state

from inputs_application.recommendation_support import design_optimisation_goal_label, resolve_geometry_width_context, severe_shear_failure, shear_severity_band

from inputs_application.recommendation_envelope import attach_recommendation_envelope, recommendation_blocked_reason

from inputs_application.live_apply import execute_typed_apply

from inputs_application.post_apply_state import rehydrate_typed_post_apply_acceptance

from inputs_application.guidance_ui_state import prepare_guidance_ui_state

from inputs_application.design_guide_fingerprint import design_guide_fingerprint

from inputs_application.shear_widget_reconciliation import ShearWidgetReconciliationRuntime, reconcile_shear_widgets_with_shared

from inputs_application.summary_state_runtime import InputsSummaryStateRuntime, resolve_inputs_summary_state

from inputs_application.widget_state_projection import merge_current_engineering_widget_state
from inputs_application.engineering_input_store import should_reuse_committed_engineering_baseline
from inputs_application.session_services import InputsSessionServices
from inputs_application.design_brain_composition import (
    build_design_brain_service,
    calculate_v2_authoritative_result,
    v2_engineering_calculation_contract_version,
)
from inputs_application.design_brain_job_service import DesignBrainJobService

from inputs_application.canonical_runtime_contracts import CanonicalConvenienceResyncRuntime, CanonicalDesignStatePackRuntime
from inputs_page_modules.app_bridge.canonical_convenience_resync import _apply_canonical_convenience_resync_to_shared, convenience_scalar_differs

from inputs_page_modules.app_bridge.canonical_design_state_pack import _build_canonical_design_state_pack_for_app_bridge as build_canonical_design_state_pack

from bending_checks_helpers import build_bending_check_rows_from_state

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

from inputs_application.v2_design_brain_ui_boundary import render_design_guide_panel_orchestration


from inputs_application.v2_design_brain_ui_boundary import render_design_guide_debug_sidebar

from inputs_application.v2_design_brain_ui_boundary import append_design_guide_trace as append_design_guide_trace_module, design_guide_tracer_path as design_guide_tracer_path_module, design_guide_tracer_verbose_log as design_guide_tracer_verbose_log_module

from inputs_application.v2_design_brain_ui_boundary import DESIGN_GUIDE_APPLY_TRACE_RUN_ID_KEY, begin_design_guide_apply_trace, end_design_guide_apply_trace, set_design_guide_live_breadcrumb

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
    INPUTS_DESIGN_STARTED_KEY,
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

from inputs_application.engineering_state_projection import (
    rebuild_engineering_derived_state,
)

from state_and_helpers import (
    BEAM_PROJECT_PARAM_KEYS,
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
    finalize_auto_design_publish,
    get_sync_callbacks,
    get_active_beam_summary,
    get_deflection_limit_label_from_ratio,
    get_deflection_limit_ratio,
    get_beam_project_param_snapshot,
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

def render_inputs_initial_session_state_coordinator(*, ss: dict) -> None:
    init_shared_session_state()
    if RESULT_CACHE_KEY not in ss:
        ss[RESULT_CACHE_KEY] = None

def render_inputs_param_snapshot_coordinator():
    # The Inputs page has fragment-owned widget/diagram regions.  A fragment
    # rerun keeps the page-context closure from the original shell render, so
    # a frozen ``params`` dictionary would return pre-edit values after a
    # widget callback had already committed a newer transaction. V2 rebuilds
    # its model on every rerun; use the current session-backed value (or the
    # caller's default) on every fragment pass.
    params = {key: st.session_state.get(key) for key in st.session_state.keys()}

    def fast_get_param(key, default=None):
        return st.session_state.get(key, default)

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
        apply_canonical_convenience_resync_to_shared_fn=_apply_canonical_convenience_resync,
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
            # The wrapped canonical sync callback already owns the one input
            # revision request. This wrapper adds audit evidence only.
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

def _build_live_engineering_input_snapshot_current_coordinator(state: dict) -> Any:
    return build_engineering_input_snapshot_from_resolved_state(
        rebuild_engineering_derived_state(state),
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

def _has_explicit_design_state_current_coordinator(state: dict) -> bool:
    """Recognize no-load detailing states that still require Design Guide proof."""

    for key in (
        "bot1_count",
        "bot2_count",
        "top1_count",
        "top2_count",
        "bot_row_count",
        "top_row_count",
        "lig_legs",
    ):
        try:
            if float((state or {}).get(key) or 0.0) > 0.0:
                return True
        except (TypeError, ValueError):
            continue
    return False


def _engineering_transaction_widget_keys(
    *,
    design_governing: bool,
    loads_edit_mode: str,
) -> dict[str, str]:
    """Return widget projections that may enter one input transaction."""

    transaction_widget_keys = dict(INPUTS_PAGE_TAB_KEYS)
    if design_governing:
        # Load Analysis actions are an immutable derived projection. Disabled
        # manual widgets may still exist in Streamlit session state, but they
        # cannot write back over that projection.
        for key in (
            "uls_Mstar",
            "uls_Mstar_pos_manual",
            "uls_Mstar_neg_manual",
            "uls_Vstar",
            "uls_Nstar",
            "sls_Mstar",
            "sls_Mstar_pos_manual",
            "sls_Mstar_neg_manual",
            "sls_Vstar",
            "sls_Nstar",
        ):
            transaction_widget_keys.pop(key, None)
        return transaction_widget_keys
    selected_prefix = (
        "sls" if str(loads_edit_mode or "ULS").strip().upper() == "SLS" else "uls"
    )
    transaction_widget_keys.update(
        {
            f"{selected_prefix}_Mstar_pos_manual": "inputs_load_Mstar_pos_proxy",
            f"{selected_prefix}_Mstar_neg_manual": "inputs_load_Mstar_neg_proxy",
            f"{selected_prefix}_Vstar": "inputs_load_Vstar_proxy",
            f"{selected_prefix}_Nstar": "inputs_load_Nstar_proxy",
        }
    )
    return transaction_widget_keys


def _merge_current_engineering_widget_state_current_coordinator(
    state: dict,
    state_debug: dict | None,
) -> tuple[dict, dict]:
    """Use the current edit snapshot before the pre-widget Design Brain run."""
    debug = dict(state_debug or {})
    shared_only = bool(debug.get("summary_shared_only_mode"))
    design_governing = is_design_governing()
    transaction_widget_keys = _engineering_transaction_widget_keys(
        design_governing=design_governing,
        loads_edit_mode=str(st.session_state.get("loads_edit_mode", "ULS") or "ULS"),
    )
    # The visible manual-action controls are edit commands, not calculation
    # projections. Their historical ``load_*_proxy`` mappings remain for
    # render compatibility, while the extra mappings above commit the same
    # values to their canonical ULS/SLS owners.
    resolved, overlay_keys = merge_current_engineering_widget_state(
        state,
        st.session_state,
        transaction_widget_keys,
        shared_only_mode=shared_only,
    )


    resolved = rebuild_engineering_derived_state(resolved)
    debug["pre_widget_engineering_widget_bridge"] = {
        "applied": bool(overlay_keys),
        "shared_only_suppressed": shared_only,
        "overlay_keys": list(overlay_keys),
        "source": "current_inputs_widget_snapshot" if overlay_keys else "resolved_shared_snapshot",
    }
    return resolved, debug


def _canonical_input_transaction_state_current_coordinator(
    resolved_state: dict,
) -> dict:
    """Project the resolved model onto the one beam-input transaction schema.

    Summary resolution deliberately contains calculated and published values as
    well as inputs.  Those values are consumers of an input revision and must
    never become fields in the input transaction itself.
    """

    state = dict(resolved_state or {})
    # V2 validates BeamInputs before it can calculate.  Older Runtime
    # sessions did not constrain the geometry widget, so a stale ``inputs_D``
    # value of 0 could be projected into the canonical transaction and crash
    # the whole workspace.  Repair only out-of-range legacy/session values at
    # this boundary; ordinary in-range user edits remain untouched.
    geometry_bounds = {
        "D": (200.0, 5000.0, 600.0),
    }
    for shared_key, (minimum, maximum, fallback) in geometry_bounds.items():
        try:
            candidate = float(state.get(shared_key))
        except (TypeError, ValueError):
            candidate = float("nan")
        if minimum <= candidate <= maximum:
            continue
        widget_key = next(
            (key for key, value in TAB_KEYS.items() if value == shared_key),
            None,
        )
        repaired = None
        for source_key in (widget_key, shared_key):
            try:
                source_value = float(st.session_state.get(source_key))
            except (TypeError, ValueError):
                continue
            if minimum <= source_value <= maximum:
                repaired = source_value
                break
        if repaired is None:
            try:
                shared_default = float(SHARED_DEFAULTS.get(shared_key, fallback))
            except (TypeError, ValueError):
                shared_default = float(fallback)
            repaired = shared_default if minimum <= shared_default <= maximum else float(fallback)
        state[shared_key] = repaired
        # Keep the widget mirror and canonical alias aligned for the next
        # render, while the transaction below becomes the single authority.
        st.session_state[shared_key] = repaired
        if widget_key:
            st.session_state[widget_key] = repaired
    return {
        key: copy.deepcopy(
            state[key]
            if key in state
            else st.session_state.get(key, SHARED_DEFAULTS.get(key))
        )
        for key in BEAM_PROJECT_PARAM_KEYS
    }


def _ensure_authoritative_design_result_current_coordinator(
    *,
    include_design_brain: bool = True,
) -> Any | None:
    """Seed or reuse the session-owned result before Design Guide rendering."""

    current_state, current_state_debug = _resolved_inputs_summary_state()
    services = InputsSessionServices.from_mapping(st.session_state)
    input_store = services.input_snapshots
    committed_state = input_store.committed()
    active_beam_id = str(
        st.session_state.get("active_beam_id") or ""
    ).strip()
    beam_input_state = input_store.current_for_beam(active_beam_id)
    beam_committed_state = dict(beam_input_state.snapshot or {})
    if beam_committed_state:
        committed_state = copy.deepcopy(beam_committed_state)
        # The beam-owned transaction is the navigation authority.  A page
        # rerun can recreate Streamlit widget keys from defaults before the
        # Inputs setup coordinator runs; letting those defaults overlay the
        # committed result leaves the visible widgets on one revision while
        # the Design Brain card remains on another.  Re-seed the widget mirror
        # from the active beam snapshot before resolving any downstream state.
        # Widget callbacks commit first, so this is also safe after a genuine
        # edit: the snapshot already contains the new value.
        hydrated_widget_keys: list[str] = []
        for shared_key, widget_key in INPUTS_PAGE_TAB_KEYS.items():
            if shared_key not in beam_committed_state:
                continue
            value = copy.deepcopy(beam_committed_state[shared_key])
            if st.session_state.get(widget_key) != value:
                st.session_state[widget_key] = value
                hydrated_widget_keys.append(str(widget_key))
        current_state = copy.deepcopy(beam_committed_state)
        current_state_debug = dict(current_state_debug)
        current_state_debug["beam_snapshot_widget_hydration"] = {
            "applied": True,
            "active_beam_id": active_beam_id,
            "source_revision": int(beam_input_state.revision or 0),
            "source_hash": beam_input_state.engineering_hash,
            "hydrated_widget_keys": sorted(hydrated_widget_keys),
        }
    if uses_load_analysis_actions(st.session_state):
        # The beam snapshot owns the selected source, while the current Load
        # Analysis solve owns its derived ULS/SLS values. Reapply that typed
        # projection after navigation hydration so an older beam snapshot
        # cannot replace the selected analysis actions with zero manual ones.
        current_state.update(
            authoritative_action_source_projection(st.session_state)
        )
    committed_beam_id = str(
        st.session_state.get(
            "_inputs_engineering_input_store_active_beam_id"
        )
        or ""
    ).strip()
    same_beam_return_restore = bool(
        st.session_state.get("_inputs_same_beam_return_active")
        and active_beam_id
        and committed_beam_id == active_beam_id
    )
    latest_input_revision = int(input_store.current().revision or 0)
    route_snapshot_is_latest = bool(
        not committed_beam_id
        or committed_beam_id != active_beam_id
        or int(beam_input_state.revision or 0) >= latest_input_revision
    )
    if same_beam_return_restore:
        result_map = dict(
            st.session_state.get(
                "_inputs_authoritative_design_result_by_beam_v1"
            )
            or {}
        )
        result_revision_map = dict(
            st.session_state.get(
                "_inputs_authoritative_design_result_revision_by_beam_v1"
            )
            or {}
        )
        committed_result = (
            result_map.get(active_beam_id)
            or services.engineering_results.current()
        )
        committed_snapshot_hash = (
            _build_live_engineering_input_snapshot_current_coordinator(
                committed_state
            ).engineering_hash
            if committed_state
            else None
        )
        result_matches_snapshot = bool(
            committed_result is not None
            and committed_result.engineering_hash == committed_snapshot_hash
        )
        result_matches_revision = bool(
            committed_result is not None
            and int(result_revision_map.get(active_beam_id) or 0)
            == int(beam_input_state.revision or 0)
        )
        st.session_state["_inputs_route_return_debug"] = {
            "branch": "route_return_candidate",
            "active_beam_id": active_beam_id,
            "committed_beam_id": committed_beam_id,
            "beam_state_present": bool(beam_committed_state),
            "beam_state_keys": len(beam_committed_state),
            "result_map_hash": getattr(
                result_map.get(active_beam_id),
                "engineering_hash",
                None,
            ),
            "current_result_hash_before": getattr(
                services.engineering_results.current(),
                "engineering_hash",
                None,
            ),
            "selected_result_hash": getattr(
                committed_result,
                "engineering_hash",
                None,
            ),
            "beam_input_revision": beam_input_state.revision,
            "latest_input_revision": latest_input_revision,
            "route_snapshot_is_latest": route_snapshot_is_latest,
            "result_matches_snapshot": result_matches_snapshot,
            "result_matches_revision": result_matches_revision,
        }
        if (
            committed_result is not None
            and committed_state
            and route_snapshot_is_latest
            and result_matches_snapshot
            # A design change can preserve the same engineering hash when it
            # only resolves aliases or display projections.  Hash equality is
            # therefore necessary but not sufficient: never republish the
            # previous revision after Apply.
            and result_matches_revision
            # A route-return result may be an engineering-only V2 result. It
            # is safe to reuse for summaries, but it is not a Design Brain
            # publication. The Design Brain caller must continue through the
            # V2 preview until the result carries its publication envelope.
            and (
                not include_design_brain
                or bool(committed_result.final_publication)
            )
        ):
            # The router has already restored shared state. Seed the widget
            # mirror from the same immutable transaction and reuse the exact
            # result; this return is not a new engineering run.
            for shared_key, widget_key in INPUTS_PAGE_TAB_KEYS.items():
                if shared_key in committed_state:
                    st.session_state[widget_key] = copy.deepcopy(
                        committed_state[shared_key]
                    )
            st.session_state["_inputs_committed_engineering_baseline_probe"] = {
                "applied": True,
                "active_beam_id": active_beam_id or None,
                "committed_beam_id": committed_beam_id or None,
                "same_beam_route_return": True,
                "shared_only_suppressed": True,
                "seeded_widget_keys": sorted(
                    str(widget_key)
                    for shared_key, widget_key in INPUTS_PAGE_TAB_KEYS.items()
                    if shared_key in committed_state
                ),
                "source": "session_owned_committed_result_route_return",
            }
            st.session_state["_authoritative_design_result_runtime_probe"] = {
                "engineering_hash": committed_result.engineering_hash,
                "reuse_decision": {
                    "reused": True,
                    "reason": "same_beam_route_return_committed_result",
                },
                "source": "inputs_same_beam_route_return",
            }
            # Re-align the legacy global transaction record with the beam-owned
            # snapshot so downstream probes and renderers cannot observe the
            # derived-only transaction that another route may have produced.
            restored_transaction = input_store.commit_active_beam(
                committed_state,
                changed_keys=(),
                source="same_beam_route_return_restore",
            )
            restored_snapshot = _build_live_engineering_input_snapshot_current_coordinator(
                committed_state
            )
            st.session_state["_inputs_engineering_input_transaction_probe"] = {
                "draft_hash": restored_transaction.engineering_hash,
                "committed_hash": restored_transaction.engineering_hash,
                "revision": restored_transaction.revision,
                "changed_keys": list(restored_transaction.changed_keys),
                "source": restored_transaction.source,
                "engineering_hash": restored_snapshot.engineering_hash,
            }
            st.session_state["_inputs_route_authority_armed"] = True
            services.engineering_results.store(
                committed_result,
                source_input_revision=beam_input_state.revision,
            )
            st.session_state["_inputs_route_return_debug"]["branch"] = (
                "route_return_reused_result"
            )
            prepare_guidance_ui_state(
                st.session_state,
                committed_state,
                preserve_apply_banner=True,
                clear_transient=_clear_design_guide_transient_ui_state,
            )
            st.session_state.pop("_inputs_route_return_pending", None)
            return committed_result
    same_beam_route_return = bool(
        st.session_state.get("_inputs_same_beam_return_active")
        and active_beam_id
        and committed_beam_id == active_beam_id
    )
    shared_only_mode = bool(
        current_state_debug.get("summary_shared_only_mode")
    )
    snapshot_update_pending = bool(
        st.session_state.get(
            "_inputs_authoritative_result_snapshot_update_pending"
        )
    )
    if snapshot_update_pending:
        # A callback has already committed a newer beam-owned input revision.
        # Shared-only route protection may not replace it with the preceding
        # authoritative result while the calculation fragment catches up.
        shared_only_mode = False
        current_state_debug["summary_shared_only_mode"] = False
        current_state_debug["summary_shared_only_reason"] = (
            "newer_committed_input_revision"
        )
    reuse_committed_baseline = should_reuse_committed_engineering_baseline(
        committed_state_present=bool(committed_state),
        active_beam_id=active_beam_id,
        committed_beam_id=committed_beam_id,
        shared_only_mode=shared_only_mode,
        same_beam_route_return=same_beam_route_return,
        # Typed Apply has already committed a newer shared transaction.  The
        # previous beam baseline is now a fallback, not an input authority.
        snapshot_update_pending=snapshot_update_pending,
    )
    # Returning to the same beam is a restore of the session-owned Inputs
    # transaction, not a new engineering edit. The router may have refreshed
    # legacy derived values while another page was active; keep those values
    # from becoming a new Design Brain input snapshot on this one return pass.
    if same_beam_route_return and reuse_committed_baseline:
        shared_only_mode = True
        current_state_debug["summary_shared_only_mode"] = True
        current_state_debug["summary_shared_only_reason"] = "same_beam_route_return_committed_baseline"
    seeded_widget_keys: list[str] = []
    if reuse_committed_baseline:
        current_state = dict(committed_state)
        for shared_key, widget_key in INPUTS_PAGE_TAB_KEYS.items():
            if (
                shared_key in committed_state
                and (
                    widget_key not in st.session_state
                    or same_beam_route_return
                )
            ):
                st.session_state[widget_key] = copy.deepcopy(
                    committed_state[shared_key]
                )
                seeded_widget_keys.append(str(widget_key))
    committed_baseline_probe = {
        "applied": reuse_committed_baseline,
        "active_beam_id": active_beam_id or None,
        "committed_beam_id": committed_beam_id or None,
        "same_beam_route_return": same_beam_route_return,
        "snapshot_update_pending": snapshot_update_pending,
        "shared_only_suppressed": shared_only_mode,
        "seeded_widget_keys": sorted(seeded_widget_keys),
        "source": (
            "session_owned_committed_engineering_state"
            if reuse_committed_baseline
            else (
                "typed_apply_pending_shared_snapshot"
                if snapshot_update_pending
                else "resolved_shared_snapshot"
            )
        ),
    }
    current_state_debug[
        "committed_engineering_input_baseline"
    ] = dict(committed_baseline_probe)
    st.session_state[
        "_inputs_committed_engineering_baseline_probe"
    ] = dict(committed_baseline_probe)
    current_state, current_state_debug = (
        _merge_current_engineering_widget_state_current_coordinator(
            current_state,
            current_state_debug,
        )
    )
    st.session_state["_inputs_pre_widget_engineering_state_bridge"] = dict(
        current_state_debug.get("pre_widget_engineering_widget_bridge") or {}
    )
    # Capacity summaries are useful before actions are entered and must remain
    # visible for a zero-action beam.  Calculation therefore always receives
    # the committed design snapshot.  The Design Brain independently treats
    # the same snapshot as ``no_design_actions`` and publishes its idle card;
    # absence of loads is not an absence of calculable section capacity.
    overlay_keys = tuple(
        current_state_debug.get("pre_widget_engineering_widget_bridge", {}).get(
            "overlay_keys",
            (),
        )
    )
    canonical_input_state = _canonical_input_transaction_state_current_coordinator(
        current_state
    )
    if (
        active_beam_id
        and snapshot_update_pending
        and int(beam_input_state.revision or 0) > 0
        and beam_committed_state
    ):
        # The typed Apply transaction already committed this exact snapshot.
        # Do not project derived widget aliases back through the store on the
        # first rerun: that creates revision N+1 while the displayed Apply
        # candidate is still bound to revision N, producing a false stale
        # candidate rejection.  Reuse the transaction when its one-shot
        # revision marker matches the beam-owned snapshot.
        pending_revision = int(
            st.session_state.get("_inputs_pending_input_revision") or 0
        )
        typed_apply_transaction = bool(
            pending_revision > 0
            and pending_revision == int(beam_input_state.revision or 0)
            and st.session_state.get("_typed_apply_input_transaction_probe")
        )
        if typed_apply_transaction:
            input_transaction = beam_input_state
            current_state = copy.deepcopy(beam_committed_state)
        elif dict(beam_committed_state) == dict(canonical_input_state):
            input_transaction = beam_input_state
            current_state = copy.deepcopy(beam_committed_state)
        else:
            # The widget callback normally owns this input transaction.  A
            # historical action-widget path may commit only a proxy value, so
            # reconcile that case when it is not the typed Apply transaction.
            input_transaction = input_store.commit_active_beam(
                canonical_input_state,
                changed_keys=overlay_keys,
                source="authoritative_widget_transaction_reconcile",
            )
            current_state = copy.deepcopy(input_transaction.to_dict())
    elif active_beam_id:
        input_transaction = input_store.commit_active_beam(
            canonical_input_state,
            changed_keys=overlay_keys,
            source="authoritative_design_transaction",
        )
    else:
        input_store.capture_draft(
            canonical_input_state,
            changed_keys=overlay_keys,
            source="current_inputs_widget_projection",
        )
        input_store.commit_draft(
            source="authoritative_design_transaction",
        )
        input_transaction = input_store.current()
    st.session_state.pop("_inputs_route_return_pending", None)
    current_state = rebuild_engineering_derived_state(input_store.committed())
    st.session_state["_inputs_engineering_input_transaction_probe"] = {
        "draft_hash": input_transaction.engineering_hash,
        "committed_hash": input_transaction.engineering_hash,
        "revision": input_transaction.revision,
        "changed_keys": list(input_transaction.changed_keys),
        "source": input_transaction.source,
    }
    snapshot = _build_live_engineering_input_snapshot_current_coordinator(current_state)
    st.session_state["_inputs_engineering_input_transaction_probe"] = {
        **dict(st.session_state.get("_inputs_engineering_input_transaction_probe") or {}),
        "engineering_hash": snapshot.engineering_hash,
    }
    sidebar_debug = _design_guide_sidebar_debug_enabled()
    # Family classification belongs to the current V2 input revision.  The
    # previous Apply route is audit evidence, not authority to pin the next
    # run to the old family.  Reusing it here caused a successfully applied
    # bending cleanup to be published again as the same ACTION/no-op card.
    family_override = None
    guidance_context = application_guidance_context(current_state, st.session_state)
    design_brain_service = (
        build_design_brain_service(
            lambda request: _compute_design_guidance_items(
                dict(request.resolved_inputs),
                guidance_debug_verbose=request.debug_enabled,
                debug_enabled=request.debug_enabled,
            )
        )
        if include_design_brain
        else None
    )

    def _compute(snapshot_value):
        if not include_design_brain:
            return calculate_v2_authoritative_result(
                engineering_snapshot=snapshot_value,
                resolved_inputs=guidance_context,
                input_revision=int(input_transaction.revision),
            )
        existing_calculation_version = str(
            dict(existing_result.current_calculations or {}).get(
                "calculation_contract_version"
            )
            or ""
        ) if existing_result is not None else ""
        engineering_calculations = (
            dict(existing_result.current_calculations or {})
            if (
                existing_result is not None
                and existing_result.engineering_hash
                == snapshot_value.engineering_hash
                and existing_calculation_version
                == v2_engineering_calculation_contract_version()
            )
            else {}
        )
        if design_brain_service is None:
            raise RuntimeError("Design Brain service was not composed")
        execution = design_brain_service.run(
            DesignBrainRequest(
                engineering_snapshot=snapshot_value,
                input_revision=int(input_transaction.revision),
                family_hint=str(family_override or "").strip() or None,
                resolved_inputs=guidance_context,
                engineering_calculations=engineering_calculations,
                debug_enabled=sidebar_debug,
            )
        )
        return execution.result

    existing_result = services.engineering_results.current()
    expected_calculation_contract_version = (
        v2_engineering_calculation_contract_version()
    )
    # A calculation-only result may need one follow-up Design Brain pass to
    # publish its CTA.  Do that at most once for a given engineering hash.
    # Re-forcing on every Streamlit rerun replaces the candidate publication
    # for unchanged inputs and makes Apply appear to jump between solutions.
    force_refresh_key = "_inputs_design_brain_force_refresh_hash_v1"
    previous_force_refresh_hash = str(
        st.session_state.get(force_refresh_key) or ""
    )
    force_design_brain_refresh = bool(
        include_design_brain
        and existing_result is not None
        and existing_result.engineering_hash == snapshot.engineering_hash
        and not existing_result.final_publication
        and previous_force_refresh_hash != snapshot.engineering_hash
    )
    if force_design_brain_refresh:
        st.session_state[force_refresh_key] = snapshot.engineering_hash
    result = ensure_design_result(
        result_store=services.engineering_results,
        snapshot=snapshot,
        compute_fn=_compute,
        force=(
            force_design_brain_refresh
        ),
        source_input_revision=input_transaction.revision,
        expected_calculation_contract_version=(
            expected_calculation_contract_version
        ),
    )
    st.session_state["_inputs_route_return_debug"] = {
        "branch": "normal_coordinator",
        "route_return_active": bool(
            st.session_state.get("_inputs_same_beam_return_active")
        ),
        "result_hash": result.engineering_hash,
        "snapshot_hash": snapshot.engineering_hash,
    }
    results_by_beam = dict(
        st.session_state.get(
            "_inputs_authoritative_design_result_by_beam_v1"
        )
        or {}
    )
    # A route-return guard may be present on the first Inputs render in a
    # browser session, but it must not suppress the first authoritative result.
    # Only reuse the guard when that beam already has a result for this
    # transaction; otherwise publish the freshly computed V2 result normally.
    route_return_missing_result = bool(
        st.session_state.get("_inputs_same_beam_return_active")
        and active_beam_id
        and active_beam_id not in results_by_beam
    )
    result_revisions_by_beam = dict(
        st.session_state.get(
            "_inputs_authoritative_design_result_revision_by_beam_v1"
        )
        or {}
    )
    stored_beam_result = coerce_authoritative_design_result(
        results_by_beam.get(active_beam_id)
    )
    stored_beam_revision = result_revisions_by_beam.get(active_beam_id)
    stored_result_is_current = bool(
        stored_beam_result is not None
        and stored_beam_result.engineering_hash == result.engineering_hash
        and stored_beam_revision is not None
        and int(stored_beam_revision) == int(input_transaction.revision)
        and (
            not include_design_brain
            or not result.final_publication
            or bool(stored_beam_result.final_publication)
        )
    )
    # The per-beam result is the read authority for Bending, Shear and the
    # serviceability pages.  It must follow the current immutable input
    # transaction even when a previous entry for the beam already exists.
    # The former "only when missing" gate left those pages permanently on an
    # unavailable/stale pack after Apply or a normal Inputs edit.
    should_store_result = bool(
        active_beam_id
        and services.engineering_results.source_input_revision()
        == input_transaction.revision
        and (
            route_return_missing_result
            or snapshot_update_pending
            or not stored_result_is_current
        )
    )
    if should_store_result:
        results_by_beam[active_beam_id] = result
        st.session_state[
            "_inputs_authoritative_design_result_by_beam_v1"
        ] = results_by_beam
        result_revisions_by_beam[active_beam_id] = int(
            input_transaction.revision
        )
        st.session_state[
            "_inputs_authoritative_design_result_revision_by_beam_v1"
        ] = result_revisions_by_beam
        st.session_state.pop(
            "_inputs_authoritative_result_snapshot_update_pending",
            None,
        )
        st.session_state.pop("_inputs_pending_input_revision", None)
    st.session_state["_inputs_route_authority_armed"] = True
    prepare_guidance_ui_state(st.session_state, current_state, preserve_apply_banner=True, clear_transient=_clear_design_guide_transient_ui_state)
    st.session_state["_authoritative_design_result_runtime_probe"] = {
        "engineering_hash": result.engineering_hash,
        "reuse_decision": dict(
            st.session_state.get("_authoritative_design_result_last_decision") or {}
        ),
        "source": "inputs_pre_widget_application_coordinator",
    }
    return result


def refresh_inputs_authoritative_design_result() -> Any | None:
    """Refresh or reuse the authoritative result for current committed inputs."""
    return _ensure_authoritative_design_result_current_coordinator()


def refresh_inputs_engineering_result() -> Any | None:
    return _ensure_authoritative_design_result_current_coordinator(
        include_design_brain=False
    )


def refresh_inputs_design_brain_result() -> Any | None:
    return _ensure_authoritative_design_result_current_coordinator(
        include_design_brain=True
    )


def _design_brain_outputs_root() -> Path:
    configured = str(os.environ.get("BEAM_OUTPUTS_DIR") or "").strip()
    if configured:
        return Path(configured).expanduser().resolve()
    return Path(__file__).resolve().parents[3] / "complete-app - Outputs"


def refresh_inputs_design_brain_result_background() -> Any | None:
    """Submit/poll Design Brain without running its search on the session thread."""

    engineering_result = _ensure_authoritative_design_result_current_coordinator(
        include_design_brain=False
    )
    if engineering_result is None:
        return None
    services = InputsSessionServices.from_mapping(st.session_state)
    input_store = services.input_snapshots
    transaction = input_store.current()
    current_state = input_store.committed()
    input_revision = int(transaction.revision or 0)
    snapshot = _build_live_engineering_input_snapshot_current_coordinator(
        current_state
    )
    if engineering_result.engineering_hash != snapshot.engineering_hash:
        raise ValueError("engineering result changed before Design Brain submission")
    existing = services.engineering_results.current()
    if (
        existing is not None
        and existing.engineering_hash == snapshot.engineering_hash
        and services.engineering_results.source_input_revision() == input_revision
        and bool(existing.final_publication)
    ):
        return existing
    active_beam_id = str(st.session_state.get("active_beam_id") or "").strip()
    owner_id = str(
        st.session_state.get("_inputs_design_brain_job_owner_id") or ""
    ).strip()
    if not owner_id:
        owner_id = uuid4().hex
        st.session_state["_inputs_design_brain_job_owner_id"] = owner_id
    # Reclassify every new revision.  The prior publication family remains
    # diagnostic evidence only and must not override the family sorter.
    family_override = None
    guidance_context = application_guidance_context(
        current_state,
        st.session_state,
    )
    session_seed = {
        key: st.session_state.get(key)
        for key in (
            "_dev_mode",
            "_design_guide_post_cleanup_acceptance_enabled",
            "_design_guide_post_cleanup_acceptance_fp",
        )
        if key in st.session_state
    }
    service = DesignBrainJobService(
        outputs_root=_design_brain_outputs_root(),
        app_root=Path(__file__).resolve().parents[2],
    )
    poll = service.poll_or_submit(
        owner_id=owner_id,
        beam_id=active_beam_id,
        input_revision=input_revision,
        engineering_snapshot=snapshot,
        engineering_calculations=dict(
            engineering_result.current_calculations or {}
        ),
        guidance_context=guidance_context,
        family_override=str(family_override or "").strip() or None,
        guidance_debug_verbose=_design_guide_sidebar_debug_enabled(),
        session_seed=session_seed,
    )
    st.session_state["_inputs_design_brain_job_probe"] = {
        "status": poll.status,
        "input_revision": poll.input_revision,
        "engineering_hash": poll.engineering_hash,
        "job_id": poll.job_id,
        "elapsed_ms": poll.elapsed_ms,
        "error": poll.error,
    }
    if poll.status == "failed":
        return engineering_result
    if poll.status != "ready" or not isinstance(poll.result, dict):
        return engineering_result
    result = AuthoritativeDesignResult(**dict(poll.result))
    if result.engineering_hash != snapshot.engineering_hash:
        raise ValueError("Design Brain worker returned a different engineering hash")
    expected_authority_hash = (
        result.with_publication_authority_hash().publication_authority_hash
    )
    if result.publication_authority_hash != expected_authority_hash:
        raise ValueError("Design Brain worker returned an invalid authority hash")
    latest_transaction = input_store.current()
    latest_snapshot = _build_live_engineering_input_snapshot_current_coordinator(
        input_store.committed()
    )
    if (
        int(latest_transaction.revision or 0) != input_revision
        or latest_snapshot.engineering_hash != result.engineering_hash
    ):
        st.session_state["_inputs_design_brain_job_probe"]["status"] = (
            "stale_result_rejected"
        )
        return engineering_result
    services.engineering_results.store(
        result,
        source_input_revision=input_revision,
    )
    if active_beam_id:
        result_map = dict(
            st.session_state.get(
                "_inputs_authoritative_design_result_by_beam_v1"
            )
            or {}
        )
        result_map[active_beam_id] = result
        st.session_state[
            "_inputs_authoritative_design_result_by_beam_v1"
        ] = result_map
        revision_map = dict(
            st.session_state.get(
                "_inputs_authoritative_design_result_revision_by_beam_v1"
            )
            or {}
        )
        revision_map[active_beam_id] = input_revision
        st.session_state[
            "_inputs_authoritative_design_result_revision_by_beam_v1"
        ] = revision_map
    prepare_guidance_ui_state(
        st.session_state,
        current_state,
        preserve_apply_banner=True,
        clear_transient=_clear_design_guide_transient_ui_state,
    )
    return result

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

def render_inputs_batch_design_context_coordinator(*, ss: dict):
    from batch_design.ui.project_beam_manager_adapters import (
        beam_option_labels as build_batch_beam_option_labels,
    )

    beam_labels = build_batch_beam_option_labels()
    beam_order = ss.get("beam_order", [])
    active_beam_id = ss.get("active_beam_id")
    if active_beam_id not in beam_order and beam_order:
        active_beam_id = beam_order[0]
    return beam_labels, beam_order, active_beam_id

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

    beam_labels, beam_order, active_beam_id = render_inputs_batch_design_context_coordinator(ss=ss)

    # The visible design-mode selector is emitted by the page shell after the
    # Inputs summary so it cannot push the primary content down the page.
    inputs_detailed_mode = bool(ss.get("inputs_detailed_mode", False))

    return {
        "fast_get_param": fast_get_param,
        "t0": _t0,
        "perf_start": _perf_start,
        "perf_marks": _perf_marks,
        "sub_marks": _sub_marks,
        "mark": _mark,
        "sub_mark": _sub_mark,
        "pre_widget_trace": _inputs_pre_widget_trace,
        "render_started_at": render_started_at,
        "corrected_invalid_shear_state": corrected_invalid_shear_state,
        "fast_focus_section": fast_focus_section,
        "sync_callbacks": sync_callbacks,
        "inputs_render_audit": inputs_render_audit,
        "before_state": before_state,
        "inputs_detailed_mode": inputs_detailed_mode,
        "beam_labels": beam_labels,
        "beam_order": beam_order,
        "active_beam_id": active_beam_id,
    }
