"""Shared permanent runtime for Inputs page composition concerns."""

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
from application.design_brain_port import DesignBrainRequest

from application.engineering_snapshot import build_engineering_input_snapshot_from_resolved_state

from application.guidance_result_adapter import build_authoritative_design_result_from_guidance_payload, guidance_payload_from_authoritative_design_result

from inputs_application.state_utils import application_guidance_context, bottom_reo_state_label, float_from_state, guidance_state_snapshot, shared_state_snapshot, shear_state_label, updates_match_state

from inputs_application.recommendation_support import design_optimisation_goal_label, resolve_geometry_width_context, severe_shear_failure, shear_severity_band

from inputs_application.recommendation_envelope import attach_recommendation_envelope, recommendation_blocked_reason

from inputs_application.live_apply import execute_typed_apply

from inputs_application.one_click_session import OneClickSessionStore


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
from application.publication_identity import normalise_design_guide_candidate_id

from application.design_guide_fingerprint_policy import (
    design_guide_cache_fingerprint_from_plain_data,
    design_guide_primary_apply_state_fingerprint_from_state,
)

from application.contracts.family_classification import load_family_classification_contract

from engineering_check_ui import BENDING_ROW_UID_TO_TAB, SHEAR_ROW_UID_TO_TAB

from inputs_application.one_click_entrypoint import run_one_click_auto_design

from inputs_application.design_brain_composition import build_new_design_brain_service

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
    "bot_row_count",
    "bot_row_1_mode",
    "bot_row_1_bars",
    "bot_row_1_spacing",
    "bot_row_1_dia",
    "bot_row_2_mode",
    "bot_row_2_bars",
    "bot_row_2_spacing",
    "bot_row_2_dia",
    "top_row_count",
    "top_row_1_mode",
    "top_row_1_bars",
    "top_row_1_spacing",
    "top_row_1_dia",
    "top_row_2_mode",
    "top_row_2_bars",
    "top_row_2_spacing",
    "top_row_2_dia",
    "lig_d",
    "lig_legs",
    "s_lig",
    "top_flange_reo_enabled",
    "bot_flange_reo_enabled",
    "top_flange_mirror_lr",
    "bot_flange_mirror_lr",
    "top_flange_left_count",
    "top_flange_left_dia",
    "top_flange_left_rows",
    "top_flange_left_row_spacing",
    "top_flange_left_clear_spacing_mode",
    "top_flange_right_count",
    "top_flange_right_dia",
    "top_flange_right_rows",
    "top_flange_right_row_spacing",
    "top_flange_right_clear_spacing_mode",
    "bot_flange_left_count",
    "bot_flange_left_dia",
    "bot_flange_left_rows",
    "bot_flange_left_row_spacing",
    "bot_flange_left_clear_spacing_mode",
    "bot_flange_right_count",
    "bot_flange_right_dia",
    "bot_flange_right_rows",
    "bot_flange_right_row_spacing",
    "bot_flange_right_clear_spacing_mode",
    "top_flange_transverse_enabled",
    "bot_flange_transverse_enabled",
    "top_flange_transverse_dia",
    "bot_flange_transverse_dia",
    "top_flange_transverse_spacing",
    "bot_flange_transverse_spacing",
    "top_flange_transverse_legs",
    "bot_flange_transverse_legs",
}

_V2_BATCH_DESIGN_BRAIN_SERVICE = None

DEBUG_DESIGN_GUIDANCE_PROBE = True

def _compute_design_guidance_items(
    state: dict,
    *,
    guidance_debug_verbose: bool | None = None,
    debug_enabled: bool = False,
    request_kind: str = "design_guide",
) -> dict:
    """Run the same V2 Design Brain used by the main Inputs card.

    Batch Design historically called the retired V1 guidance runner.  Under
    the V2-only composition that function returned an empty compatibility
    payload, so batch rows silently bypassed the authoritative Design Brain.
    Keep the batch adapter's dictionary shape, but derive every value from the
    neutral service result instead of reintroducing a second calculator.
    """

    del guidance_debug_verbose, debug_enabled, request_kind
    if not isinstance(state, dict):
        raise TypeError("design guidance state must be a dictionary")
    global _V2_BATCH_DESIGN_BRAIN_SERVICE
    if _V2_BATCH_DESIGN_BRAIN_SERVICE is None:
        _V2_BATCH_DESIGN_BRAIN_SERVICE = build_new_design_brain_service()
    snapshot = build_engineering_input_snapshot_from_resolved_state(state)
    revision = int(
        state.get("_inputs_workspace_revision")
        or state.get("input_revision")
        or state.get("_inputs_input_revision")
        or 1
    )
    execution = _V2_BATCH_DESIGN_BRAIN_SERVICE.run(
        DesignBrainRequest(
            engineering_snapshot=snapshot,
            resolved_inputs=dict(state),
            input_revision=revision,
        )
    )
    result = execution.result
    payload = guidance_payload_from_authoritative_design_result(result)
    calculations = dict(result.current_calculations or {})
    # A reviewed batch run is asking V2 to design the member, not merely to
    # report the capacity of its starting geometry.  When V2 has accepted a
    # proposal, it has already published verified post-proposal packs at the
    # adapter boundary.  Consume those exact packs; otherwise retain the
    # current-result packs so an exhausted/blocked candidate remains visible
    # as a failure instead of being represented as a passing redesign.
    candidate_evaluation = (
        dict(result.candidate_evaluation)
        if isinstance(result.candidate_evaluation, dict)
        else {}
    )
    candidate_accepted = bool(
        isinstance(result.selected_candidate, dict)
        and candidate_evaluation.get("accepted")
    )
    packs_key = "proposed_packs" if candidate_accepted else "packs"
    packs = dict(calculations.get(packs_key) or calculations.get("packs") or {})

    def _number(value: Any) -> float | None:
        try:
            if value in (None, "", "—", "-"):
                return None
            return float(value)
        except (TypeError, ValueError):
            return None

    statuses: dict[str, str] = {}
    utilisations: list[float] = []
    for family, pack in packs.items():
        if not isinstance(pack, dict):
            continue
        rows = list(pack.get("rows") or [])
        status = str(pack.get("summary_status") or "").strip().upper()
        if not status and rows and isinstance(rows[0], dict):
            status = str(rows[0].get("status") or "").strip().upper()
        if status:
            statuses[str(family)] = status
        util = _number(pack.get("summary_util"))
        if util is None:
            util = _number(pack.get("summary_util_total"))
        if util is None and rows and isinstance(rows[0], dict):
            util = _number(rows[0].get("util"))
        if util is not None:
            utilisations.append(util)
    worst_util = max(utilisations, default=None)
    any_fail = any(status == "FAIL" for status in statuses.values())
    selected = dict(result.selected_candidate or {})
    overview = {
        "statuses": statuses,
        "any_fail": any_fail,
        "all_key_pass": not any_fail,
        "worst_util": worst_util,
    }
    payload["debug_trace"] = {
        "overview": overview,
        "source": "inputs_v2",
        "result_basis": "verified_v2_proposal" if candidate_accepted else "current_design",
        "input_revision": revision,
        "engineering_hash": result.engineering_hash,
    }
    payload["design_brain_result"] = {
        "selected_candidate_label": (
            selected.get("candidate_id")
            or selected.get("label")
            or result.governing_family
        ),
        "selected_section": selected.get("section"),
        "utilisation": worst_util,
        "result_basis": "verified_v2_proposal" if candidate_accepted else "current_design",
        # Batch Design owns the member records, so carry V2's exact
        # approved changes across this neutral adapter boundary.  The batch
        # publisher can then update the selected member without reproducing
        # V2 candidate generation or guessing reinforcement values.
        "selected_updates": (
            dict(result.selected_updates) if candidate_accepted else {}
        ),
        "selected_candidate": selected if candidate_accepted else {},
        "source": "inputs_v2",
    }
    return payload

def log_debug(message, value=None):
    print(f"[INPUTS DEBUG] {message}: {value}")

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

def _apply_canonical_convenience_resync(*, source: str) -> dict:
    runtime = CanonicalConvenienceResyncRuntime(_agent_debug_log, _build_canonical_design_state_pack, convenience_scalar_differs, _guidance_state_snapshot, st.session_state, set_shared, _shared_state_snapshot)
    return _apply_canonical_convenience_resync_to_shared(source=source, runtime=runtime)

def _build_canonical_design_state_pack(state: dict) -> dict:
    return build_canonical_design_state_pack(state, runtime=CanonicalDesignStatePackRuntime(_guidance_state_snapshot))

def _resolved_inputs_summary_state() -> tuple[dict, dict]:
    runtime = InputsSummaryStateRuntime(design_guide_fingerprint, _guidance_state_snapshot, st.session_state, _shared_state_snapshot, ux_probe_record)
    return resolve_inputs_summary_state(runtime)

def _handle_inputs_apply_buttons_current_coordinator() -> None:
    handle_inputs_apply_buttons(
        st_module=st,
        stderr=sys.stderr,
        design_guide_apply_trace_run_id_key=DESIGN_GUIDE_APPLY_TRACE_RUN_ID_KEY,
        set_live_breadcrumb_fn=lambda label, extra=None: set_design_guide_live_breadcrumb(st.session_state, label, extra),
        begin_apply_trace_fn=lambda **kwargs: begin_design_guide_apply_trace(
            st.session_state,
            append_trace=_append_design_guide_trace,
            **kwargs,
        ),
        apply_recommendation_result_fn=_execute_authoritative_apply_current_coordinator,
        recommendation_blocked_reason_fn=recommendation_blocked_reason,
        emit_apply_trace_run_end_fn=lambda **kwargs: end_design_guide_apply_trace(
            st.session_state,
            append_trace=_append_design_guide_trace,
            **kwargs,
        ),
        record_rerun_trigger_fn=_record_inputs_rerun_trigger,
    )

def _execute_authoritative_apply_current_coordinator(recommendation: dict[str, Any]) -> str:
    result_store = InputsSessionServices.from_mapping(
        st.session_state
    ).engineering_results
    current_result = result_store.current()
    typed = execute_typed_apply(
        session_state=st.session_state,
        current_result=current_result,
        recommendation=recommendation,
        set_shared=set_shared,
        finalize_publish=finalize_auto_design_publish,
        persist_active_beam=persist_active_beam_from_shared,
    )
    command = typed.command
    st.session_state["_typed_inputs_apply_probe"] = {
        "status": command.status,
        "reason": typed.mutation.reason if typed.mutation else command.reason,
        "updates": dict(typed.mutation.updates) if typed.mutation else {},
    }
    if command.status in {"dispatch_ok", "rerun_required"}:
        result_store.clear()
        st.session_state[
            "_inputs_authoritative_result_snapshot_update_pending"
        ] = True
    st.session_state["_authoritative_apply_command_probe"] = {
        "status": command.status,
        "reason": command.reason,
        "recommendation_id": command.recommendation_id,
        "source": "application.apply_command",
    }
    return command.status


def _begin_design_guide_apply_trace(*, recommendation: dict | None, source: str) -> str | None:
    """Application-owned adapter for the extracted CTA queue."""
    return begin_design_guide_apply_trace(
        st.session_state,
        recommendation=recommendation,
        source=source,
        append_trace=_append_design_guide_trace,
    )


def _emit_design_guide_apply_trace_run_end(
    *,
    stop_reason: str,
    final_updates: dict | None = None,
    winner_label: str | None = None,
    **kwargs: Any,
) -> None:
    """Application-owned adapter for the extracted CTA queue."""
    end_design_guide_apply_trace(
        st.session_state,
        stop_reason=stop_reason,
        final_updates=final_updates,
        winner_label=winner_label,
        append_trace=_append_design_guide_trace,
        **kwargs,
    )


def _set_design_guide_live_breadcrumb(label: str, extra: dict | None = None) -> None:
    set_design_guide_live_breadcrumb(st.session_state, label, extra)


def _design_guide_primary_apply_state_fingerprint(state: dict | None = None) -> str:
    return str(
        design_guide_primary_apply_state_fingerprint_from_state(
            dict(state or {}),
            cache_fingerprint=design_guide_cache_fingerprint_from_plain_data,
        )
    )


def _consume_design_guide_component_cta_value(
    *,
    canonical_payload: dict | None,
    expected_fingerprint: str | None,
    current_fingerprint: str | None,
    apply_label: str | None = None,
) -> dict | None:
    """Reject stale CTA payloads without reintroducing the page bridge."""
    if not isinstance(canonical_payload, dict):
        return None
    expected = str(expected_fingerprint or "").strip()
    current = str(current_fingerprint or "").strip()
    if expected and current and expected != current:
        return None
    payload = dict(canonical_payload)
    if apply_label and not str(payload.get("label") or "").strip():
        payload["label"] = str(apply_label)
    return payload


def _sync_auto_design_invoke_pending_field() -> None:
    pending = bool(
        st.session_state.get("auto_design_invoke_pending")
        or st.session_state.get("_auto_design_invoke_pending")
    )
    st.session_state["auto_design_invoke_pending"] = pending


authoritative_apply_command_fn = _execute_authoritative_apply_current_coordinator
_normalise_design_guide_candidate_id = normalise_design_guide_candidate_id
apply_recommendation_result = _execute_authoritative_apply_current_coordinator

def _design_guide_sidebar_debug_enabled() -> bool:
    try:
        return bool(st.session_state.get(DESIGN_GUIDE_SIDEBAR_DEBUG_TOGGLE_KEY, False))
    except Exception:
        return False

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
            location="inputs_application.page_runtime.common:_invalidate_design_guide_caches",
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

def _shared_state_snapshot() -> dict:
    return {
        key: st.session_state.get(key, default)
        for key, default in SHARED_DEFAULTS.items()
    }

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
        layout = compute_section_layout(model_state) if isinstance(model_state, dict) else compute_section_layout()
    explicit_state = isinstance(model_state, dict)
    shared_state = dict(model_state) if explicit_state else _shared_state_snapshot()
    try:
        if explicit_state:
            raw_shape = str(
                shared_state.get("sec_shape")
                or shared_state.get("shape_name")
                or "RECT"
            )
            raw_shape_lower = raw_shape.strip().lower()
            sec_shape = (
                "T"
                if raw_shape_lower.startswith("t")
                else "I"
                if raw_shape_lower.startswith("i")
                else "RECT"
            )
            outline_points, outline_width, outline_depth = build_section_outline_points_and_bbox_module(
                sec_shape=sec_shape,
                b=float(shared_state.get("b", 400.0) or 400.0),
                D=float(shared_state.get("D", 600.0) or 600.0),
                bf=float(shared_state.get("bf", 600.0) or 600.0),
                tf=float(shared_state.get("tf", 120.0) or 120.0),
                bw=float(shared_state.get("bw", 300.0) or 300.0),
                tw=float(shared_state.get("tw", 200.0) or 200.0),
            )
        else:
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
    span_length = (
        shared_state.get("L", 3000.0)
        if explicit_state
        else shared_state.get("L", get_param("L", 3000.0))
    )
    return InputsDiagramSourceSnapshot(
        layout=dict(layout or {}),
        shared_state=shared_state,
        tension_face=(
            shared_state.get("active_tension_face")
            if explicit_state
            else st.session_state.get("active_tension_face")
        ),
        fallback_cover_side=float(shared_state.get("cover_side", 40.0) or 40.0),
        fallback_cover_top=float(shared_state.get("cover_top", 40.0) or 40.0),
        fallback_cover_bot=float(shared_state.get("cover_bot", 40.0) or 40.0),
        fallback_width=float(shared_state.get("b", outline_width) or outline_width),
        fallback_depth=float(shared_state.get("D", outline_depth) or outline_depth),
        span_length=float(span_length or 3000.0),
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
    return OneClickSessionStore(st.session_state).clear_auto_design_runtime_latches(reason)

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
    OneClickSessionStore(st.session_state).invalidate_after_design_state_change(
        current_fingerprint=current_fingerprint,
        transient_keys=(
            "pending_recommendation",
            "pending_recommendation_applied_id",
            "_solver_result",
            "_one_click_run_feedback",
            "auto_design_status",
            "auto_design_steps",
            "auto_design_request_source",
            AUTO_DESIGN_REQUEST_SOURCE_KEY,
            AUTO_DESIGN_REQUEST_TS_KEY,
            AUTO_DESIGN_AUTO_INVOKE_KEY,
            "_inputs_action_run_auto_design",
            "auto_design_invoke_set",
            "auto_design_invoke_pending",
            "auto_design_invoke_consumed",
        ),
    )

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

def _resolve_design_actions_from_state(state: dict) -> dict:
    return resolve_design_actions(state)

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
    if keys:
        # One command owns the full engineering-edit transaction: clear any
        # route-return lock, mark the authoritative snapshot pending, and
        # advance exactly one workspace revision.
        _request_inputs_engineering_commit(
            f"inputs_{str(keys[0])}",
            changed_keys=tuple(str(key) for key in keys),
        )
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


def reconcile_inputs_design_actions_before_authority() -> list[str]:
    """Commit fragment widget state before authoritative engineering refresh."""

    if is_design_governing():
        return []
    selected_mode = str(st.session_state.get("loads_edit_mode", "ULS") or "ULS")
    selected_prefix = "sls" if selected_mode.upper() == "SLS" else "uls"
    return _reconcile_design_action_widgets_with_shared(selected_prefix)


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
