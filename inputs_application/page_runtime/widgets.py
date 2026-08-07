"""Permanent Inputs page widgets runtime."""

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

from inputs_application.session_services import InputsSessionServices

from application.design_run_coordinator import ensure_design_result

from application.engineering_snapshot import build_engineering_input_snapshot_from_resolved_state

from application.guidance_result_adapter import build_authoritative_design_result_from_guidance_payload, guidance_payload_from_authoritative_design_result

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

from crack_checks_helpers import build_crack_check_rows_from_state, pick_governing_check_row

from deflection_checks_helpers import build_deflection_check_rows_from_state

from application.contracts.design_policy import DESIGN_OPTIMISATION_GOAL_LABELS, resolve_design_optimisation_goal

from application.contracts.family_classification import load_family_classification_contract

from engineering_check_ui import BENDING_ROW_UID_TO_TAB, SHEAR_ROW_UID_TO_TAB

from inputs_application.one_click_entrypoint import run_one_click_auto_design

from inputs_page_modules.calculations import render_inputs_calculation_explainer_trace as render_inputs_calculation_explainer_trace_module

from inputs_page_modules.diagrams import (
    InputsBeam3DRegionContext,
    InputsSection2DRegionContext,
    build_beam_3d_request_view_model,
    build_section_2d_request_view_model,
    render_inputs_3d_diagram_block,
    render_inputs_fast_model_block,
    render_inputs_section_2d_diagram_block,
)

from inputs_application.engineering_input_store import InputSnapshotStore

from inputs_application.region_contexts import RevisionIdentity

from inputs_page_modules.diagrams.source_projection import build_section_outline_points_and_bbox as build_section_outline_points_and_bbox_module

from inputs_page_modules.fragments import run_inputs_fragment

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
)

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
    from inputs_application.recommendation_cache import resolve_popover_recommendation
    from inputs_application.recommendation_evaluation import (
        effective_bottom_design_state,
        evaluate_bending_with_bottom_state,
    )
    from inputs_page_modules.recommendation_panels import render_bottom_recommendation_panel
    from inputs_page_modules.recommendation_runtime import compute_bottom_recommendation_for_page

    render_bottom_recommendation_panel(
        st_module=st,
        button_key=button_key,
        source=source,
        compact=compact,
        shared_state_snapshot_fn=lambda: shared_state_snapshot(st.session_state),
        resolve_popover_recommendation_fn=lambda **kwargs: resolve_popover_recommendation(st_module=st, **kwargs),
        compute_bottom_reo_recommendation_fn=lambda state: compute_bottom_recommendation_for_page(state, session_state=st.session_state),
        updates_match_state_fn=updates_match_state,
        design_optimisation_goal_label_fn=design_optimisation_goal_label,
        bottom_reo_state_label_fn=bottom_reo_state_label,
        evaluate_bending_with_bottom_state_fn=evaluate_bending_with_bottom_state,
        effective_bottom_design_state_fn=effective_bottom_design_state,
        apply_bottom_reo_recommendation_fn=lambda **kwargs: _apply_popover_recommendation("bottom", **kwargs),
    )

def _render_shear_recommendation_panel(*, button_key: str, source: str, compact: bool) -> None:
    from inputs_application.recommendation_cache import resolve_popover_recommendation
    from inputs_application.recommendation_evaluation import evaluate_shear_with_state
    from inputs_page_modules.recommendation_panels import render_shear_recommendation_panel
    from inputs_page_modules.recommendation_runtime import compute_shear_recommendation_for_page

    render_shear_recommendation_panel(
        st_module=st,
        button_key=button_key,
        source=source,
        compact=compact,
        shared_state_snapshot_fn=lambda: shared_state_snapshot(st.session_state),
        guidance_state_snapshot_fn=guidance_state_snapshot,
        build_shear_check_rows_from_state_fn=build_shear_check_rows_from_state,
        resolve_popover_recommendation_fn=lambda **kwargs: resolve_popover_recommendation(st_module=st, **kwargs),
        compute_shear_recommendation_fn=lambda state: compute_shear_recommendation_for_page(state, session_state=st.session_state),
        design_optimisation_goal_label_fn=design_optimisation_goal_label,
        shear_state_label_fn=shear_state_label,
        parse_util_value_fn=_parse_util_value,
        shear_severity_band_fn=shear_severity_band,
        updates_match_state_fn=updates_match_state,
        severe_shear_failure_fn=severe_shear_failure,
        apply_shear_recommendation_fn=lambda **kwargs: _apply_popover_recommendation("shear", **kwargs),
    )

def _render_geometry_recommendation_panel(*, button_key: str, source: str, compact: bool) -> None:
    from inputs_application.recommendation_cache import resolve_popover_recommendation
    from inputs_application.recommendation_evaluation import (
        evaluate_bending_with_bottom_state,
        evaluate_shear_with_state,
    )
    from inputs_page_modules.recommendation_panels import render_geometry_recommendation_panel
    from inputs_page_modules.recommendation_runtime import compute_geometry_recommendation_for_page

    render_geometry_recommendation_panel(
        st_module=st,
        button_key=button_key,
        source=source,
        compact=compact,
        shared_state_snapshot_fn=lambda: shared_state_snapshot(st.session_state),
        resolve_popover_recommendation_fn=lambda **kwargs: resolve_popover_recommendation(st_module=st, **kwargs),
        compute_geometry_recommendation_fn=lambda state: compute_geometry_recommendation_for_page(state, session_state=st.session_state),
        updates_match_state_fn=updates_match_state,
        design_optimisation_goal_label_fn=design_optimisation_goal_label,
        resolve_geometry_width_context_fn=resolve_geometry_width_context,
        float_from_state_fn=float_from_state,
        evaluate_bending_with_bottom_state_fn=evaluate_bending_with_bottom_state,
        evaluate_shear_with_state_fn=evaluate_shear_with_state,
        apply_geometry_recommendation_fn=lambda **kwargs: _apply_popover_recommendation("geometry", **kwargs),
    )

def _apply_popover_recommendation(kind: str, *, recommendation: dict, source: str) -> bool:
    from inputs_application.popover_recommendation_apply import execute_popover_recommendation_apply
    from inputs_page_modules.fragments import rerun_inputs_current_scope

    return execute_popover_recommendation_apply(kind=kind, source=source, session_state=st.session_state, recommendation=recommendation, set_shared=set_shared, finalize_publish=finalize_auto_design_publish, persist_active_beam=persist_active_beam_from_shared, invalidate_caches=_invalidate_design_guide_caches, rerun=lambda: rerun_inputs_current_scope(st))

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

def _render_section_2d_diagram_block_current(
    *, compact: bool = False, model_state: dict | None = None,
    workspace_context=None, _retry_latest: bool = False,
):
    beam_id = str(
        getattr(workspace_context, "active_beam_id", None)
        or st.session_state.get("active_beam_id")
        or st.session_state.get("_inputs_engineering_input_store_active_beam_id")
        or "active"
    )
    input_store = InputSnapshotStore(st.session_state)
    # Fragment payloads can contain a context captured before the widget
    # callback committed. The store is the authoritative transaction boundary,
    # so always read the latest beam snapshot first on a workspace rerun.
    input_state = input_store.current_for_beam(beam_id)
    if not input_state.engineering_hash and workspace_context is not None:
        input_state = workspace_context.current_input_state()
    if not input_state.engineering_hash:
        input_state = input_store.current()
    explicit_state = dict(
        input_state.snapshot
        or model_state
        or _resolved_inputs_model_state()[0]
    )
    layout = compute_section_layout(explicit_state)
    source = _build_inputs_diagram_source_snapshot(layout, explicit_state)
    section_view_model = build_section_2d_request_view_model(source)
    identity = RevisionIdentity(
        input_revision=int(input_state.revision),
        engineering_hash=str(
            input_state.engineering_hash
            or section_view_model.display_hash
        ),
    )
    region_context = InputsSection2DRegionContext(
        identity=identity,
        beam_id=beam_id,
        layout=layout,
        view_model=section_view_model,
    )
    st.session_state["_inputs_diagram_view_model_trace"] = {
        "diagram_view_model_trace_source": "inputs_page_modules.diagrams",
        "diagram_view_model_trace_only": True,
        "live_cutover": True,
        "section_2d_display_hash": section_view_model.display_hash,
        "diagram_display_hash": section_view_model.display_hash,
        "source_layout_keys": sorted(dict(source.layout or {}).keys()),
    }

    def _current_identity() -> RevisionIdentity:
        current = input_store.current_for_beam(beam_id)
        if not current.engineering_hash:
            current = input_store.current()
        return RevisionIdentity(
            input_revision=int(current.revision),
            engineering_hash=str(
                current.engineering_hash
                or region_context.identity.engineering_hash
            ),
        )

    latest_identity = _current_identity()
    if latest_identity != region_context.identity and not _retry_latest:
        # A Streamlit widget callback can commit while the surrounding page
        # transaction is still rendering. Rebuild the diagram view model once
        # from the now-authoritative snapshot instead of emitting a stale
        # prior-revision Plotly figure.
        return _render_section_2d_diagram_block_current(
            compact=compact,
            model_state=model_state,
            workspace_context=workspace_context,
            _retry_latest=True,
        )

    return render_inputs_section_2d_diagram_block(
        st_module=st,
        region_context=region_context,
        current_input_identity_fn=_current_identity,
        compact=compact,
        time_perf_counter_fn=time.perf_counter,
        build_summary_cross_section_result_fn=build_summary_cross_section_result,
        section_figure_builder_fn=make_sectionA_figure,
        copy_deepcopy_fn=copy.deepcopy,
        render_plotly_diagram_fn=st.plotly_chart,
    )

def _render_section_2d_diagram_block(
    *, compact: bool = False, model_state: dict | None = None,
    workspace_context=None,
):
    # Diagrams are input previews. Render them in the parent fast workspace so
    # a widget callback cannot commit successfully while a nested child
    # fragment remains on the prior revision.
    return _render_section_2d_diagram_block_current(
        compact=compact,
        model_state=model_state,
        workspace_context=workspace_context,
    )


def _render_3d_diagram_block_current(
    *, compact: bool = False, model_state: dict | None = None,
    workspace_context=None, _retry_latest: bool = False,
):
    beam_id = str(
        getattr(workspace_context, "active_beam_id", None)
        or st.session_state.get("active_beam_id")
        or st.session_state.get("_inputs_engineering_input_store_active_beam_id")
        or "active"
    )
    input_store = InputSnapshotStore(st.session_state)
    # Use the latest committed snapshot rather than a stale parent-fragment
    # context captured before the widget callback.
    input_state = input_store.current_for_beam(beam_id)
    if not input_state.engineering_hash and workspace_context is not None:
        input_state = workspace_context.current_input_state()
    if not input_state.engineering_hash:
        input_state = input_store.current()
    explicit_state = dict(
        input_state.snapshot
        or model_state
        or _resolved_inputs_model_state()[0]
    )
    layout = compute_section_layout(explicit_state)
    source = _build_inputs_diagram_source_snapshot(layout, explicit_state)
    beam_view_model = build_beam_3d_request_view_model(source)
    identity = RevisionIdentity(
        input_revision=int(input_state.revision),
        engineering_hash=str(
            input_state.engineering_hash
            or beam_view_model.display_hash
        ),
    )
    region_context = InputsBeam3DRegionContext(
        identity=identity,
        beam_id=beam_id,
        layout=layout,
        view_model=beam_view_model,
    )
    trace = dict(st.session_state.get("_inputs_diagram_view_model_trace") or {})
    trace.update(
        {
            "diagram_view_model_trace_source": "inputs_page_modules.diagrams",
            "diagram_view_model_trace_only": True,
            "live_cutover": True,
            "beam_3d_display_hash": beam_view_model.display_hash,
            "diagram_display_hash": beam_view_model.display_hash,
            "source_layout_keys": sorted(dict(source.layout or {}).keys()),
        }
    )
    st.session_state["_inputs_diagram_view_model_trace"] = trace

    def _current_identity() -> RevisionIdentity:
        current = input_store.current_for_beam(beam_id)
        if not current.engineering_hash:
            current = input_store.current()
        return RevisionIdentity(
            input_revision=int(current.revision),
            engineering_hash=str(
                current.engineering_hash
                or region_context.identity.engineering_hash
            ),
        )

    latest_identity = _current_identity()
    if latest_identity != region_context.identity and not _retry_latest:
        return _render_3d_diagram_block_current(
            compact=compact,
            model_state=model_state,
            workspace_context=workspace_context,
            _retry_latest=True,
        )

    return render_inputs_3d_diagram_block(
        st_module=st,
        region_context=region_context,
        current_input_identity_fn=_current_identity,
        compact=compact,
        time_perf_counter_fn=time.perf_counter,
        copy_deepcopy_fn=copy.deepcopy,
        cache_json_fn=_cache_json,
        cached_make_section_3d_figure_fn=cached_make_section_3d_figure,
        build_inputs_beam_3d_figure_fn=build_inputs_beam_3d_figure,
        render_plotly_diagram_fn=st.plotly_chart,
    )


def _render_3d_diagram_block(
    *, compact: bool = False, model_state: dict | None = None,
    workspace_context=None,
):
    return _render_3d_diagram_block_current(
        compact=compact,
        model_state=model_state,
        workspace_context=workspace_context,
    )

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
    model_summary_debug = dict(summary_debug or {})
    # The widget callback now commits the beam-owned input revision before this
    # render. A route-return summary mode must not suppress the current visible
    # reinforcement widgets from the input-preview diagram.
    model_summary_debug["summary_shared_only_mode"] = False
    model_summary_debug.pop("summary_shared_only_reason", None)
    return overlay_inputs_reo_widget_mirrors_for_model_module(
        page_slug=str(st.session_state.get("page_slug", "inputs") or "inputs"),
        state=state,
        summary_debug=model_summary_debug,
        widget_state=widget_values,
        overlay_plan_fn=build_inputs_model_reo_widget_mirror_overlay_plan,
        build_legacy_longitudinal_mirrors_from_rows_fn=build_legacy_longitudinal_mirrors_from_rows,
        build_canonical_design_state_pack_fn=_build_canonical_design_state_pack,
    )

def _resolved_inputs_model_state() -> tuple[dict, dict]:
    resolved, summary_debug = _resolved_inputs_summary_state()
    authoritative = _authoritative_state_snapshot()
    # A visible widget edit is the source for the current render.  Replacing it
    # with the last committed result makes the diagram lag behind width/depth
    # widgets and can also preserve stale shear detailing.  Publication still
    # comes from the authoritative result; this only selects the render state.
    current_widget_keys = tuple(
        (f"inputs_{shared_key}", shared_key)
        for shared_key in MODEL_RENDER_FINGERPRINT_KEYS
    )
    widget_state_differs = any(
        widget_key in st.session_state
        and st.session_state.get(widget_key) not in (None, "")
        and str(st.session_state.get(widget_key)) != str((authoritative or {}).get(shared_key))
        for widget_key, shared_key in current_widget_keys
    )
    if authoritative and not widget_state_differs:
        resolved = dict(authoritative)
        summary_debug = {
            **dict(summary_debug or {}),
            "model_state_source": "authoritative_design_result",
            "model_state_engineering_hash": (
                InputsSessionServices.from_mapping(st.session_state).engineering_results.current().engineering_hash
                if InputsSessionServices.from_mapping(st.session_state).engineering_results.current() is not None
                else None
            ),
        }
    elif widget_state_differs:
        summary_debug = {
            **dict(summary_debug or {}),
            "model_state_source": "current_widget_resolved_inputs",
            "model_state_authoritative_result_deferred": True,
        }
    model_state, model_widget_debug = _overlay_inputs_reo_widget_mirrors_for_model(
        dict(resolved),
        summary_debug=summary_debug,
    )
    debug_snapshot = build_inputs_model_state_debug_payload_snapshot(
        summary_debug=summary_debug,
        model_widget_debug=model_widget_debug,
    )
    return dict(model_state), dict(debug_snapshot.debug_payload)

def _render_fast_model_block(sync_callbacks: dict, model_state: dict | None = None) -> None:
    workspace_context = sync_callbacks.get("_workspace_context")
    return render_inputs_fast_model_block(
        st_module=st,
        sync_callbacks=sync_callbacks,
        model_state=model_state,
        shared_toggle_fn=_shared_toggle,
        render_3d_diagram_block_fn=lambda **kwargs: _render_3d_diagram_block_current(
            workspace_context=workspace_context, **kwargs
        ),
        render_section_2d_diagram_block_fn=lambda **kwargs: _render_section_2d_diagram_block_current(
            workspace_context=workspace_context, **kwargs
        ),
    )


def _render_inputs_owned_diagram_fragment_body(
    *,
    inputs_detailed_mode: bool,
    sync_callbacks: dict,
    right_diagram=None,
    model_slot=None,
) -> None:
    """Render the model into the diagram fragment registered by the parent."""

    st_module = st
    workspace_context = sync_callbacks.get("_workspace_context")
    target_slot = right_diagram if inputs_detailed_mode else model_slot
    if target_slot is None:
        return
    with target_slot:
        if inputs_detailed_mode:
            st_module.markdown(
                '<div class="inputs-diagram-materials-group">',
                unsafe_allow_html=True,
            )
            _render_section_2d_diagram_block_current(
                model_state=None,
                workspace_context=workspace_context,
            )
            st_module.markdown(
                '<div style="margin-bottom: 0.35rem;"></div>',
                unsafe_allow_html=True,
            )
            st_module.markdown(
                '<div style="margin-top: 0.35rem;"></div>',
                unsafe_allow_html=True,
            )
            _render_inputs_materials_subsection(sync_callbacks)
            st_module.markdown("</div>", unsafe_allow_html=True)
            return

        model_state, model_state_debug = _resolved_inputs_model_state()
        st_module.session_state["_inputs_fast_model_state_debug"] = {
            **dict(model_state_debug or {}),
            "summary_governing_check_name": model_state.get(
                "shear_truth_governing_check_name"
            ),
            "summary_governing_reason": model_state.get(
                "shear_truth_governing_reason"
            ),
            "fast_model_uses_overlay_state": True,
            "fast_model_overlay_lig_d": model_state_debug.get(
                "model_overlay_lig_d"
            ),
            "fast_model_overlay_lig_legs": model_state_debug.get(
                "model_overlay_lig_legs"
            ),
            "fast_model_overlay_s_lig": model_state_debug.get(
                "model_overlay_s_lig"
            ),
            "fast_model_fingerprint_includes_shear": True,
        }
        with st_module.container():
            st_module.markdown(
                '<div class="inputs-diagram-materials-group">',
                unsafe_allow_html=True,
            )
            _render_fast_model_block(sync_callbacks, model_state=model_state)
            st_module.markdown("</div>", unsafe_allow_html=True)


def _render_inputs_owned_diagram_fragment(
    *,
    inputs_detailed_mode: bool,
    sync_callbacks: dict,
    right_diagram=None,
    model_slot=None,
) -> None:
    """Render the diagram directly in the outer widget workspace."""

    return _render_inputs_owned_diagram_fragment_body(
        inputs_detailed_mode=bool(inputs_detailed_mode),
        sync_callbacks=sync_callbacks,
        right_diagram=right_diagram,
        model_slot=model_slot,
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
    from deflection_support import get_deflection_diagram_support_condition, _deflection_support_options_for_value

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
    workspace_context = sync_callbacks.get("_workspace_context")
    render_inputs_materials_and_section_2d_module(
        st_module=st,
        sync_callbacks=sync_callbacks,
        get_widget_key_for_shared_fn=get_widget_key_for_shared,
        select_row_fn=select_row,
        is_design_governing_fn=is_design_governing,
        resolve_support_and_deflection_defaults_fn=_resolve_inputs_support_and_deflection_defaults,
        caption_deflection_limit_ratio_fn=_caption_inputs_deflection_limit_ratio,
        number_row_fn=number_row,
        render_3d_diagram_block_fn=lambda **kwargs: _render_3d_diagram_block(
            workspace_context=workspace_context, **kwargs
        ),
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

def _authoritative_state_snapshot() -> dict:
    """Return committed engineering state for output-only render paths."""
    result = InputsSessionServices.from_mapping(st.session_state).engineering_results.current()
    calculations = dict(result.current_calculations or {}) if result is not None else {}
    resolved_inputs = calculations.get("resolved_inputs")
    if isinstance(resolved_inputs, dict):
        return dict(resolved_inputs)
    return _shared_state_snapshot()

def _cache_json(value) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))

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

def render_inputs_top_section_layout_slots_coordinator(
    *,
    inputs_detailed_mode: bool,
    sync_callbacks: dict,
    inputs_render_audit: dict[str, str],
    fast_focus_section: str | None,
    mark=None,
):
    marker = mark if callable(mark) else (lambda _name: None)
    bottom_slot = None
    shear_slot = None
    model_slot = None

    if inputs_detailed_mode:
        left_inputs, right_diagram = st.columns([1.15, 1.85], gap="large")
        with left_inputs:
            actions_slot = st.container()
            geometry_slot = st.container()
    else:
        fast_left, fast_right = st.columns([1.0, 1.5], gap="medium")
        with fast_left:
            actions_slot = st.container()
            geometry_slot = st.container()
        with fast_right:
            model_slot = st.container()
        right_diagram = None
    return bottom_slot, shear_slot, model_slot, actions_slot, geometry_slot, right_diagram

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

def _make_design_action_widget_callback(widget_key: str, shared_key: str, proxy_key: str | None = None):
    callback = make_design_action_widget_callback_module(
        widget_key,
        shared_key,
        proxy_key,
        sync_design_action_widget_to_shared_fn=_sync_design_action_widget_to_shared,
    )

    def _committing_callback() -> None:
        # The injected sync path owns invalidation and queues exactly one
        # workspace revision through _queue_inputs_refresh. Do not advance the
        # same transaction again in this rendering wrapper.
        callback()

    return _committing_callback

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
    page_divider()
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
        _apply_canonical_convenience_resync(
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
    nested_section_fragments = str(
        os.environ.get("CODEX_INPUTS_NESTED_SECTION_FRAGMENTS", "0")
    ).strip().lower() not in {"0", "false", "no", "off"}
    return render_inputs_widget_sections_module(
        st_module=st,
        ss=ss,
        inputs_detailed_mode=bool(inputs_detailed_mode),
        sync_callbacks=sync_callbacks,
        inputs_render_audit=inputs_render_audit,
        fast_focus_section=fast_focus_section,
        fast_get_param=fast_get_param,
        corrected_invalid_shear_state=bool(corrected_invalid_shear_state),
        mark=mark,
        sub_mark=sub_mark,
        run_fragment_fn=run_inputs_fragment if nested_section_fragments else None,
        render_diagram_fragment_fn=_render_inputs_owned_diagram_fragment,
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
