
import copy
import json
import html
import os
from urllib.parse import urlencode
import inspect
from datetime import datetime
import math
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import time

_INPUTS_DEBUG_AUDIT = os.environ.get("INPUTS_DEBUG_AUDIT", "").strip().lower() in ("1", "true", "yes", "on")


def log_debug(message, value=None):
    print(f"[INPUTS DEBUG] {message}: {value}")


def _inputs_audit_snapshot_state():
    """Best-effort snapshot of session state for diff (may skip unpickleable values)."""
    out: dict[str, object] = {}
    for k in list(st.session_state.keys()):
        try:
            out[k] = copy.deepcopy(st.session_state.get(k))
        except Exception:
            try:
                out[k] = st.session_state.get(k)
            except Exception:
                out[k] = "<unreadable>"
    return out


def _wrap_inputs_sync_callbacks(raw: dict, log_debug_fn) -> dict:
    def sync_callback_wrapper(fn, name):
        def wrapper():
            log_debug_fn(f"SYNC CALLBACK TRIGGERED - {name}")
            before = dict(st.session_state)
            fn()
            for k in before:
                if before.get(k) != st.session_state.get(k):
                    log_debug_fn(
                        f"SYNC CHANGE - {k}",
                        f"{before.get(k)} -> {st.session_state.get(k)}",
                    )
        return wrapper

    return {k: sync_callback_wrapper(v, k) for k, v in raw.items()}


from state_and_helpers import (
    BEAM_STATUS_FAIL,
    BEAM_STATUS_NOT_RUN,
    BEAM_STATUS_PASS,
    BEAM_STATUS_WARN,
    SHARED_DEFAULTS,
    build_beam_schedule_rows,
    ensure_beam_project_initialized,
    load_active_beam_into_shared,
    set_active_beam,
    add_new_beam_record,
    duplicate_active_beam_record,
    delete_beam_record,
    make_not_run_beam_summary,
    persist_active_beam_from_shared,
    reset_app_to_clean_starter_workspace,
    update_active_beam_summary_from_results,
    hydrate_active_page_widgets_from_shared,
    init_shared_session_state,
    get_sync_callbacks,
    get_param,
    mark_user_edit,
    resolve_design_actions,
    get_active_beam_summary,
    update_results,
    compute_all_results,
    recalc_derived_values,
    is_design_governing,
    get_widget_key_for_shared,
    set_shared,
    load_proxies_from_active_set,
    derive_design_actions,
    TAB_KEYS,
    hc_log,
    hc_try,
    DEFLECTION_LIMIT_OPTIONS,
    DEFLECTION_LIMIT_HELP_TEXT,
    get_deflection_limit_ratio,
    get_deflection_limit_label_from_ratio,
)

# Inputs page: shared_key -> inputs_* widget key (same role as TAB_KEYS['inputs'] in audit spec)
INPUTS_PAGE_TAB_KEYS = {sk: wk for wk, sk in TAB_KEYS.items() if str(wk).startswith("inputs_")}

RESULT_CACHE_KEY = "cached_results"

from widgets_helpers import (
    apply_global_widget_css,
    apply_calcbox_css,
    number_row,
    select_row,
    calcbox,
    show_reo_message,
    label_with_hover,
    info_i_button,
    page_divider,
    seed_widget_from_shared,
    _register_rendered_key,
    v2_radio,
    render_longitudinal_reo_rows,
    render_longitudinal_reo_row_config_controls,
    main_longitudinal_reo_pair_labels,
    main_longitudinal_reo_change_line_prefixes,
    normalized_sec_shape_ui,
)

try:
    from ui_seamless_steps import inject_seamless_steps_css, render_clickable_summary_table
except Exception:
    def inject_seamless_steps_css():
        return None

    def render_clickable_summary_table(*args, **kwargs):
        return ""
from deflection_checks_helpers import build_deflection_check_rows_from_state
from bending_checks_helpers import build_bending_check_rows_from_state
from shear_checks_helpers import build_shear_check_rows_from_state
from crack_checks_helpers import build_crack_check_rows_from_state, pick_governing_check_row
from engineering_check_ui import (
    BENDING_ROW_UID_TO_TAB,
    SHEAR_ROW_UID_TO_TAB,
    resolve_jump_target_id,
    summary_cell_display,
)
from report_helpers import (
    build_beam_schedule_export_rows,
    format_report_status_badge,
    format_report_status_label,
)


# --- Pure compute functions from design core (no circular imports)
# NOTE: Heavy imports are deferred inside render_inputs() to avoid
# startup timeouts on networked/OneDrive filesystems.
from section_layout import compute_section_layout
from section_props.plotly_section import make_sectionA_figure
from section_props.plotly_3d import make_section_3d_figure
from section_props.reo_layout import (
    compute_longitudinal_reo_layout_T_I,
    dev_warnings_bars_outside_concrete,
    resolve_longitudinal_bars_from_layout,
)
from section_props.shape_utils import normalise_shape_name
# from deflection import _compute_deflection_results  # TODO: add later

_AGENT_DEBUG_LOG_PATH = "/Users/jonathonleggo/Library/CloudStorage/OneDrive-Personal/Documents/GitHub/complete-app/.cursor/debug.log"
DEBUG_DESIGN_GUIDANCE_PROBE = True

# Design guidance ladders / geometry trials: small deterministic sets only.
GUIDANCE_LADDER_EARLY_STOP_UTIL = 0.85
GUIDANCE_GEOMETRY_TRIAL_DELTAS_MM = (25, 50)
# Shallower-beam: prefer depth+width correction over width-only growth when section is very deep vs template.
GUIDANCE_SHALLOW_CORRECTION_MIN_D_OVER_TEMPLATE_MM = 150.0
GUIDANCE_SHALLOW_CORRECTION_METRIC_MARGIN = 0.08
GUIDANCE_SHALLOW_CORRECTION_MIN_DEPTH_DROP_MM = 40.0

# Sidebar-only Design Guide / solver debug (main page stays clean when off).
DESIGN_GUIDE_SIDEBAR_DEBUG_TOGGLE_KEY = "inputs_design_guide_debug_sidebar_v1"
DESIGN_GUIDE_DEBUG_BUNDLE_KEY = "_design_guide_debug_bundle"
DESIGN_GUIDE_RECO_TRACE_KEY = "_design_guide_reco_trace"
DESIGN_GUIDE_RANK_TRACE_KEY = "_design_guide_rank_trace"
DESIGN_GUIDE_APPLY_BANNER_KEY = "_design_guide_apply_banner_payload"
DESIGN_GUIDE_APPLY_BANNER_META_KEY = "_design_guide_apply_banner_meta"
DESIGN_GUIDE_REF_BEAM_ID_KEY = "_design_guide_ref_beam_id"
DESIGN_GUIDE_REFERENCE_D_KEY = "design_guide_reference_D"
DESIGN_GUIDE_REFERENCE_B_KEY = "design_guide_reference_b"
DESIGN_GUIDE_SESSION_ANCHOR_D_KEY = "design_guide_session_anchor_D"
DESIGN_GUIDE_LAST_USER_GEOM_KEY = "design_guide_last_user_geometry"
DESIGN_GUIDE_LAST_AUTO_GEOM_KEY = "design_guide_last_applied_auto_geometry"
DESIGN_GUIDE_GEOMETRY_TRIAL_DEBUG_KEY = "_design_guide_geometry_trial_debug"
DESIGN_GUIDE_STEP_HISTORY_KEY = "_design_guide_step_history"
DESIGN_GUIDE_FIRST_TARGET_BAND_STEP_KEY = "_design_guide_first_target_band_step"
DESIGN_GUIDE_HISTORY_ANCHOR_KEY = "_design_guide_history_anchor"
DESIGN_GUIDE_PENDING_STEP_CTX_KEY = "_design_guide_pending_step_ctx"
DESIGN_GUIDE_LAST_APPLY_ROUTE_KEY = "_design_guide_last_apply_route"
DESIGN_GUIDE_GUIDANCE_CACHE_FP_KEY = "_design_guide_cached_fingerprint"
DESIGN_GUIDE_GUIDANCE_CACHE_ITEMS_KEY = "_design_guide_cached_items"
DESIGN_GUIDE_GUIDANCE_CACHE_DEBUG_KEY = "_design_guide_cached_debug"
DESIGN_GUIDE_NEEDS_REFRESH_KEY = "_design_guide_needs_refresh"
DESIGN_GUIDE_PANEL_BASELINE_FP_KEY = "_design_guide_panel_baseline_fingerprint"


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
        DESIGN_GUIDE_PENDING_STEP_CTX_KEY,
    ]
    if not preserve_apply_banner:
        transient_keys.append(DESIGN_GUIDE_APPLY_BANNER_KEY)
    for key in transient_keys:
        st.session_state.pop(key, None)

    st.session_state.pop(DESIGN_GUIDE_DEBUG_BUNDLE_KEY, None)
    st.session_state.pop(DESIGN_GUIDE_RECO_TRACE_KEY, None)
    st.session_state.pop(DESIGN_GUIDE_RANK_TRACE_KEY, None)

    if clear_history:
        st.session_state.pop(DESIGN_GUIDE_STEP_HISTORY_KEY, None)
        st.session_state.pop(DESIGN_GUIDE_FIRST_TARGET_BAND_STEP_KEY, None)
        st.session_state.pop(DESIGN_GUIDE_HISTORY_ANCHOR_KEY, None)


def _mark_design_guide_dirty() -> None:
    """Inputs changed vs last rendered guide; clear stale cards/cache (not beam state)."""
    st.session_state[DESIGN_GUIDE_NEEDS_REFRESH_KEY] = True
    _clear_design_guide_transient_ui_state(clear_history=False, preserve_apply_banner=False)


def _clear_design_guide_guidance_render_cache() -> None:
    _clear_design_guide_transient_ui_state(clear_history=False, preserve_apply_banner=False)


def _get_cached_design_guide_guidance(
    fingerprint: tuple,
) -> tuple[list[dict], dict, bool]:
    cached_fp = st.session_state.get(DESIGN_GUIDE_GUIDANCE_CACHE_FP_KEY)
    if cached_fp != fingerprint:
        return [], {}, False

    items = st.session_state.get(DESIGN_GUIDE_GUIDANCE_CACHE_ITEMS_KEY)
    debug = st.session_state.get(DESIGN_GUIDE_GUIDANCE_CACHE_DEBUG_KEY)

    return (
        list(items or []),
        dict(debug or {}),
        True,
    )


def _set_cached_design_guide_guidance(
    fingerprint: tuple,
    guidance_items: list[dict] | None,
    guidance_debug: dict | None,
) -> None:
    st.session_state[DESIGN_GUIDE_GUIDANCE_CACHE_FP_KEY] = fingerprint
    st.session_state[DESIGN_GUIDE_GUIDANCE_CACHE_ITEMS_KEY] = list(guidance_items or [])
    st.session_state[DESIGN_GUIDE_GUIDANCE_CACHE_DEBUG_KEY] = dict(guidance_debug or {})


def _design_guide_cache_fingerprint(state: dict) -> tuple:
    return (
        str(_design_optimisation_goal(state)),
        str(state.get("sec_shape")),
        float(state.get("b", 0.0) or 0.0),
        float(state.get("D", 0.0) or 0.0),
        float(state.get("fc", 0.0) or 0.0),
        float(state.get("fsy", 0.0) or 0.0),
        float(state.get("uls_Mstar", 0.0) or 0.0),
        float(state.get("uls_Vstar", 0.0) or 0.0),
        float(state.get("uls_Nstar", 0.0) or 0.0),
        float(state.get("Tu_star", 0.0) or 0.0),
        int(state.get("bot_row_count", 0) or 0),
        int(state.get("bot1_count", 0) or 0),
        float(state.get("db_bot_1", 0.0) or 0.0),
        int(state.get("bot2_count", 0) or 0),
        float(state.get("db_bot_2", 0.0) or 0.0),
        float(state.get("lig_d", 0.0) or 0.0),
        int(state.get("lig_legs", 0) or 0),
        float(state.get("s_lig", 0.0) or 0.0),
        tuple(_resolve_design_actions_from_state(state).get("signature", ())),
    )


_COMPOUND_GEOMETRY_UPDATE_KEYS = frozenset(
    {"b", "bw", "D", "bf", "tf", "tw", "bf_bot", "tf_bot"},
)
_COMPOUND_BOTTOM_UPDATE_KEYS = frozenset(
    {
        "bot_row_count",
        "bot1_layout_mode",
        "bot1_count",
        "bot1_spacing",
        "db_bot_1",
        "bot2_layout_mode",
        "bot2_count",
        "bot2_spacing",
        "db_bot_2",
        "bot_row_1_mode",
        "bot_row_1_bars",
        "bot_row_1_spacing",
        "bot_row_1_dia",
        "bot_row_2_mode",
        "bot_row_2_bars",
        "bot_row_2_spacing",
        "bot_row_2_dia",
        "bot_row_3_mode",
        "bot_row_3_bars",
        "bot_row_3_spacing",
        "bot_row_3_dia",
        "bot_row_4_mode",
        "bot_row_4_bars",
        "bot_row_4_spacing",
        "bot_row_4_dia",
        "Ast_bot",
    },
)
_COMPOUND_SHEAR_UPDATE_KEYS = frozenset({"lig_d", "lig_legs", "s_lig"})


def _design_guide_sidebar_debug_enabled() -> bool:
    try:
        return bool(st.session_state.get(DESIGN_GUIDE_SIDEBAR_DEBUG_TOGGLE_KEY, False))
    except Exception:
        return False


def _reset_design_guide_reco_trace() -> None:
    st.session_state[DESIGN_GUIDE_RECO_TRACE_KEY] = []


def _append_design_guide_reco_trace(entry: dict) -> None:
    if not _design_guide_sidebar_debug_enabled():
        return
    lst = st.session_state.setdefault(DESIGN_GUIDE_RECO_TRACE_KEY, [])
    lst.append(dict(entry))


def _merge_design_guide_rank_trace(entry: dict) -> None:
    if not entry:
        return
    cur = st.session_state.get(DESIGN_GUIDE_RANK_TRACE_KEY)
    base = dict(cur) if isinstance(cur, dict) else {}
    for key, value in entry.items():
        if key == "efficiency_growth_rejection" and isinstance(value, dict):
            acc = base.get("efficiency_growth_rejections")
            if not isinstance(acc, list):
                acc = []
            acc.append(dict(value))
            base["efficiency_growth_rejections"] = acc
        else:
            base[key] = value
    st.session_state[DESIGN_GUIDE_RANK_TRACE_KEY] = base


def _design_guide_history_anchor_from_state(state: dict) -> tuple:
    return (
        str(_design_optimisation_goal(state)),
        str(st.session_state.get(DESIGN_GUIDE_REF_BEAM_ID_KEY) or ""),
        tuple(_resolve_design_actions_from_state(state).get("signature", ())),
    )


def _maybe_reset_design_guide_step_history(state: dict) -> None:
    anchor = _design_guide_history_anchor_from_state(state)
    prev = st.session_state.get(DESIGN_GUIDE_HISTORY_ANCHOR_KEY)
    if prev is not None and prev != anchor:
        st.session_state[DESIGN_GUIDE_STEP_HISTORY_KEY] = []
        st.session_state[DESIGN_GUIDE_FIRST_TARGET_BAND_STEP_KEY] = None
    st.session_state[DESIGN_GUIDE_HISTORY_ANCHOR_KEY] = anchor


def _worst_util_in_efficiency_target_band(overview: dict | None) -> bool:
    if not isinstance(overview, dict):
        return False
    try:
        w = float(overview.get("worst_util", 0.0) or 0.0)
    except (TypeError, ValueError):
        return False
    return bool(EFFICIENCY_TARGET_UTIL_MIN <= w <= EFFICIENCY_TARGET_UTIL_MAX) and bool(overview.get("all_key_pass"))


def _signature_dict_for_step_history(state: dict) -> dict:
    return {
        "D_mm": round(float(_float_from_state(state, "D", 0.0) or 0.0), 3),
        "b_mm": round(float(_design_width_value(state) or 0.0), 3),
        "goal": str(_design_optimisation_goal(state)),
    }


def _finalize_design_guide_apply_step_history(
    *,
    prior_state: dict,
    source: str,
    applied_candidate: dict | None,
) -> None:
    if not str(source).startswith("guidance:"):
        return
    ctx = st.session_state.pop(DESIGN_GUIDE_PENDING_STEP_CTX_KEY, None)
    if not isinstance(ctx, dict):
        return
    post_state = _shared_state_snapshot()
    design_context_post = _build_design_actions_context(post_state)
    post_overview = _collect_design_overview(post_state, context=design_context_post)
    pre_overview = ctx.get("pre_overview") or {}
    action_type = str(ctx.get("action_type") or "")
    payload = dict(ctx.get("payload") or {})
    mode_cfg = _design_mode_config(_design_optimisation_goal(post_state))
    tmin = float(mode_cfg.get("target_util_min", EFFICIENCY_TARGET_UTIL_MIN) or EFFICIENCY_TARGET_UTIL_MIN)
    tmax = float(mode_cfg.get("target_util_max", EFFICIENCY_TARGET_UTIL_MAX) or EFFICIENCY_TARGET_UTIL_MAX)
    try:
        pre_wu = float((pre_overview or {}).get("worst_util", 0.0) or 0.0)
    except (TypeError, ValueError):
        pre_wu = 0.0
    try:
        post_wu = float((post_overview or {}).get("worst_util", 0.0) or 0.0)
    except (TypeError, ValueError):
        post_wu = 0.0
    pre_band = _worst_util_in_efficiency_target_band(pre_overview)
    post_band = _worst_util_in_efficiency_target_band(post_overview)
    entered = bool(not pre_band and post_band)
    first_step = st.session_state.get(DESIGN_GUIDE_FIRST_TARGET_BAND_STEP_KEY)
    step_list = st.session_state.setdefault(DESIGN_GUIDE_STEP_HISTORY_KEY, [])
    step_index = len(step_list) + 1
    if entered and first_step is None:
        st.session_state[DESIGN_GUIDE_FIRST_TARGET_BAND_STEP_KEY] = step_index
        first_after = step_index
    else:
        first_after = int(first_step) if first_step is not None else None
    title = str(ctx.get("recommendation_title") or "").strip()
    if not title:
        title = str(payload.get("guidance_banner_title") or payload.get("label") or _guidance_default_banner_title(action_type))
    rec_ft = None
    rec_sf: list | None = None
    if action_type == "apply_resolved_candidate" and isinstance(applied_candidate, dict):
        rec_ft = applied_candidate.get("recommendation_family_tag")
        rec_sf = (
            list(applied_candidate.get("subfamilies") or [])
            if isinstance(applied_candidate.get("subfamilies"), list)
            else None
        )
    elif action_type == "apply_bottom_recommendation":
        try:
            br = _compute_bottom_reo_recommendation(prior_state)
            if isinstance(br, dict):
                rec_ft = br.get("recommendation_family_tag")
                rec_sf = list(br.get("subfamilies") or []) if isinstance(br.get("subfamilies"), list) else None
        except Exception:
            rec_ft, rec_sf = None, None
    change_lines: list[str] = []
    try:
        change_lines = list(_guidance_apply_change_lines(prior_state, post_state) or [])
    except Exception:
        change_lines = []
    entry = {
        "step_index": step_index,
        "applied_at": datetime.now().isoformat(timespec="seconds"),
        "guidance_branch_before": ctx.get("guidance_branch_before"),
        "recommendation_title": str(title),
        "recommendation_family_tag": rec_ft,
        "recommendation_subfamilies": rec_sf,
        "pre_apply_worst_util": pre_wu,
        "post_apply_worst_util": post_wu,
        "pre_apply_statuses": dict((pre_overview or {}).get("statuses") or {}),
        "post_apply_statuses": dict((post_overview or {}).get("statuses") or {}),
        "pre_apply_signature": _signature_dict_for_step_history(prior_state),
        "post_apply_signature": _signature_dict_for_step_history(post_state),
        "pre_apply_target_band": [tmin, tmax],
        "entered_target_band_on_this_step": entered,
        "first_target_band_step_after_apply": first_after,
        "applied_change_lines": change_lines,
        "action_type": action_type,
        "recommendation_label_at_step_start": ctx.get("recommendation_label_at_step_start"),
        "recommendation_action_type_at_step_start": ctx.get("recommendation_action_type_at_step_start"),
        "used_resolved_payload": bool(ctx.get("used_resolved_payload")),
        "one_click_candidate_available_at_step_start": bool(ctx.get("one_click_candidate_available_at_step_start")),
        "one_click_candidate_label_at_step_start": ctx.get("one_click_candidate_label_at_step_start"),
    }
    step_list.append(entry)


def _design_guide_step_history_debug_summary() -> dict:
    hist = list(st.session_state.get(DESIGN_GUIDE_STEP_HISTORY_KEY) or [])
    first = st.session_state.get(DESIGN_GUIDE_FIRST_TARGET_BAND_STEP_KEY)
    ever = first is not None
    steps_to = int(first) if first is not None else None
    latest = hist[-1] if hist else {}
    tail = hist[-10:] if len(hist) > 10 else list(hist)
    compact = []
    for e in hist:
        if not isinstance(e, dict):
            continue
        compact.append(
            {
                "step": e.get("step_index"),
                "pre": e.get("pre_apply_worst_util"),
                "post": e.get("post_apply_worst_util"),
                "entered_band": bool(e.get("entered_target_band_on_this_step")),
                "title": e.get("recommendation_title"),
            }
        )
    return {
        "design_guide_step_history_count": len(hist),
        "design_guide_step_history_tail": tail,
        "first_target_band_step": first,
        "current_step_index": len(hist),
        "ever_entered_target_band": ever,
        "steps_to_first_target_band": steps_to,
        "latest_step_pre_util": (latest or {}).get("pre_apply_worst_util"),
        "latest_step_post_util": (latest or {}).get("post_apply_worst_util"),
        "latest_step_title": (latest or {}).get("recommendation_title"),
        "latest_step_used_resolved_payload": bool((latest or {}).get("used_resolved_payload")),
        "converged_in_one_click": bool(steps_to == 1),
        "design_guide_step_history_compact": compact,
    }


def _render_design_guide_debug_sidebar() -> None:
    if not _design_guide_sidebar_debug_enabled():
        return
    st.sidebar.divider()
    st.sidebar.caption("Design Guide Debug")
    if st.sidebar.button("Clear design guide UI state", key="_dg_debug_clear_transient_ui"):
        _clear_design_guide_transient_ui_state(clear_history=False, preserve_apply_banner=False)
        st.rerun()
    bundle = st.session_state.get(DESIGN_GUIDE_DEBUG_BUNDLE_KEY) or {}
    trace = st.session_state.get(DESIGN_GUIDE_RECO_TRACE_KEY) or []

    with st.sidebar.expander("Guidance Selection", expanded=False):
        st.json(
            {
                "guidance_branch": bundle.get("guidance_branch"),
                "governing_action": bundle.get("governing_action"),
                "primary_utils": bundle.get("primary_utils"),
                "selected_action_type": bundle.get("selected_action_type"),
                "selected_title": bundle.get("selected_title"),
                "guidance_items": bundle.get("guidance_items_summary"),
            }
        )

    with st.sidebar.expander("Candidates", expanded=False):
        st.json(
            {
                "overview_utils": (bundle.get("overview") or {}).get("utils") if isinstance(bundle.get("overview"), dict) else None,
                "overview_statuses": (bundle.get("overview") or {}).get("statuses") if isinstance(bundle.get("overview"), dict) else None,
                "current_design_summary": bundle.get("current_design_summary"),
                "efficiency_snippet": {
                    "mode_tightening": bundle.get("next_mode_recommendation"),
                    "bottom_tightening": bundle.get("bottom_tightening"),
                },
            }
        )

    with st.sidebar.expander("Scores / Ranking", expanded=False):
        st.json(
            {
                "fingerprints": bundle.get("fingerprints"),
                "resolved_guidance_actions": bundle.get("resolved_guidance_actions"),
                "reco_trace_tail": trace[-20:] if trace else [],
            }
        )

    with st.sidebar.expander("Rejections", expanded=False):
        rejects = [t for t in trace if str(t.get("event") or "") == "rejected"]
        st.json({"recent_rejections": rejects[-30:], "rejection_count": len(rejects)})

    with st.sidebar.expander("Step history (compact)", expanded=False):
        st.json(bundle.get("design_guide_step_history_compact") or [])

    with st.sidebar.expander("Full probe (raw)", expanded=False):
        st.json(bundle)


def _agent_debug_log(message: str, data: dict | None = None, *, location: str, hypothesis_id: str, run_id: str = "auto_design_debug") -> None:
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


def apply_inputs_page_css():
    # Main block padding is applied app-wide via apply_global_widget_css() in app.py.

    # Extra CSS so special widgets (side cover + exposure class)
    # use the same effective width as the standard number_row inputs.
    st.markdown(
        """
        <style>
        .nr-field select,
        .nr-field input {
            width: 100% !important;
        }

        /* Remove any container framing around Plotly charts */
        div[data-testid="stPlotlyChart"], 
        div[data-testid="stPlotlyChart"] > div,
        div[data-testid="stPlotlyChart"] > div > div {
            border: none !important;
            box-shadow: none !important;
            outline: none !important;
        }
        .inputs-page-main-diagram-wrap {
            margin: 0;
            padding: 0;
        }
        /* Main inputs diagram: cap height to reduce overflow (complements reduced Plotly layout height) */
        .inputs-page-main-diagram-wrap div[data-testid="stPlotlyChart"] {
            max-height: min(52vh, 560px);
        }
        @media print {
          .inputs-diagram-materials-group {
            break-inside: avoid;
            page-break-inside: avoid;
          }
        }
        .fast-start-here {
            background: rgba(30, 41, 59, 0.12);
            border: 1px solid rgba(30, 41, 59, 0.22);
            box-shadow: 0 1px 3px rgba(15, 23, 42, 0.08);
            border-radius: 14px;
            padding: 1rem 1rem;
            margin: 0.25rem 0 1rem 0;
        }
        .fast-start-here-kicker {
            font-size: 0.8rem;
            font-weight: 800;
            letter-spacing: 0.08em;
            text-transform: uppercase;
            color: rgba(15, 23, 42, 0.82);
            margin-bottom: 0.2rem;
        }
        .fast-start-here-title {
            font-size: 1.05rem;
            font-weight: 700;
            color: rgba(15, 23, 42, 0.96);
        }
        .fast-phase-label {
            margin: 0.45rem 0 0.45rem 0;
            font-size: 0.7rem;
            font-weight: 700;
            letter-spacing: 0.12em;
            text-transform: uppercase;
            color: rgba(100, 116, 139, 0.95);
        }
        .fast-next-hint {
            background: rgba(59, 130, 246, 0.09);
            border: 1px solid rgba(59, 130, 246, 0.18);
            color: rgba(30, 64, 175, 0.95);
            border-radius: 12px;
            padding: 0.55rem 0.8rem;
            margin: 0.15rem 0 0.55rem 0;
            font-size: 0.92rem;
            font-weight: 600;
        }
        .fast-next-hint.fast-next-hint--design-guide-follow {
            display: block;
            width: 100%;
            box-sizing: border-box;
            margin-top: 0.65rem;
            margin-bottom: 0.15rem;
        }
        .stButton > button {
            padding-top: 0.35rem !important;
            padding-bottom: 0.35rem !important;
        }
        .stMarkdown h2, .stMarkdown h3 {
            margin-top: 0.6rem !important;
            margin-bottom: 0.25rem !important;
        }
        .stMarkdown h2 {
            font-size: 1.65rem !important;
            font-weight: 800 !important;
        }
        .stMarkdown h3 {
            font-size: 1.35rem !important;
            font-weight: 800 !important;
        }
        .fast-live-checks {
            border: 1px solid rgba(49, 51, 63, 0.12);
            border-radius: 12px;
            background: rgba(255, 255, 255, 0.9);
            padding: 0.7rem 0.85rem;
            margin-top: 0.55rem;
        }
        .fast-live-check-row {
            display: grid;
            grid-template-columns: 1.3fr 0.8fr 0.7fr;
            gap: 0.5rem;
            align-items: center;
            padding: 0.3rem 0;
            border-top: 1px solid rgba(49, 51, 63, 0.08);
            font-size: 0.92rem;
        }
        .fast-live-check-row:first-of-type {
            border-top: none;
        }
        .fast-live-check-status {
            text-align: right;
            font-weight: 700;
        }
        .fast-guidance-item {
            border-top: 1px solid rgba(49, 51, 63, 0.08);
            border-left: 4px solid transparent;
            border-radius: 10px;
            padding: 0.92rem 0.95rem;
            margin-top: 0.7rem;
            line-height: 1.42;
        }
        .fast-guidance-item:first-of-type {
            border-top: none;
            margin-top: 0;
        }
        .fast-guidance-item.fail {
            background: #FEF2F2;
            border-left-color: #dc2626;
        }
        .fast-guidance-item.warn {
            background: #FFF7ED;
            border-left-color: #f59e0b;
        }
        .fast-guidance-item.pass {
            background: #F0FDF4;
            border-left-color: #16a34a;
        }
        .fast-guidance-item.guidance-success {
            background: #ECFDF5;
            border-left-color: #15803d;
            border-top: none;
        }
        .fast-guidance-item.guidance-success .fast-guidance-badge.guidance-success {
            background: #15803d;
        }
        .fast-guidance-item.efficiency {
            background: #EFF6FF;
            border-left-color: #2563eb;
        }
        .fast-guidance-item.start {
            background: #F8FAFC;
            border-left-color: #64748b;
        }
        .fast-guidance-item.secondary {
            margin-top: 1rem;
            border-left-width: 3px;
            box-shadow: inset 0 0 0 1px rgba(148, 163, 184, 0.12);
        }
        .fast-guidance-item.secondary.fail {
            background: #FFF7F7;
            border-left-color: rgba(220, 38, 38, 0.38);
        }
        .fast-guidance-item.secondary.warn {
            background: #FFFAF2;
            border-left-color: rgba(245, 158, 11, 0.42);
        }
        .fast-guidance-item.secondary.pass {
            background: #F7FCF8;
            border-left-color: rgba(22, 163, 74, 0.34);
        }
        .fast-guidance-item.secondary.efficiency {
            background: #F5F9FF;
            border-left-color: rgba(37, 99, 235, 0.34);
        }
        .fast-guidance-head {
            display: flex;
            align-items: center;
            gap: 0.5rem;
            margin-bottom: 0.32rem;
        }
        .fast-guidance-badge {
            font-size: 0.68rem;
            font-weight: 800;
            text-transform: uppercase;
            letter-spacing: 0.06em;
            padding: 0.18rem 0.48rem;
            border-radius: 999px;
            color: #fff;
        }
        .fast-guidance-badge.fail {
            background: #dc2626;
        }
        .fast-guidance-badge.warn {
            background: #f59e0b;
        }
        .fast-guidance-badge.pass {
            background: #16a34a;
        }
        .fast-guidance-badge.efficiency {
            background: #2563eb;
        }
        .fast-guidance-badge.start {
            background: #64748b;
        }
        .fast-guidance-item.secondary .fast-guidance-badge.fail {
            background: rgba(220, 38, 38, 0.82);
        }
        .fast-guidance-item.secondary .fast-guidance-badge.warn {
            background: rgba(245, 158, 11, 0.84);
        }
        .fast-guidance-item.secondary .fast-guidance-badge.pass {
            background: rgba(22, 163, 74, 0.8);
        }
        .fast-guidance-item.secondary .fast-guidance-badge.efficiency {
            background: rgba(37, 99, 235, 0.82);
        }
        .fast-guidance-title-wrap {
            display: inline-flex;
            flex-wrap: wrap;
            align-items: baseline;
            gap: 0.38rem;
        }
        .fast-guidance-title {
            font-weight: 800;
            font-size: 0.98rem;
        }
        .fast-guidance-title-util {
            font-size: 0.84rem;
            color: rgba(71, 85, 105, 0.88);
            font-weight: 600;
        }
        .fast-guidance-action {
            font-size: 0.93rem;
            line-height: 1.35;
        }
        .fast-guidance-primary {
            font-size: 0.98rem;
            line-height: 1.42;
            font-weight: 800;
            margin-top: 0.18rem;
            color: rgba(15, 23, 42, 0.96);
        }
        .fast-guidance-secondary {
            margin-top: 0.28rem;
            font-size: 0.84rem;
            color: rgba(71, 85, 105, 0.84);
        }
        .fast-guidance-reason {
            margin-top: 0.24rem;
            font-size: 0.83rem;
            color: rgba(71, 85, 105, 0.95);
        }
        .fast-guidance-proposed {
            margin-top: 0.32rem;
            padding: 0.5rem 0.55rem;
            border-radius: 8px;
            background: rgba(241, 245, 249, 0.75);
            border: 1px solid rgba(148, 163, 184, 0.35);
            font-size: 0.84rem;
            line-height: 1.45;
            color: rgba(30, 41, 59, 0.96);
        }
        .fast-guidance-levers {
            margin-top: 0.22rem;
            font-size: 0.81rem;
            color: rgba(100, 116, 139, 0.98);
        }
        .fast-guidance-list {
            margin: 0.45rem 0 0 1rem;
            padding: 0;
            color: rgba(51, 65, 85, 0.96);
            font-size: 0.88rem;
        }
        .fast-guidance-list li {
            margin: 0.16rem 0;
        }
        .element-container:has(.fast-guidance-action-anchor) + div button[kind="secondary"] {
            justify-content: flex-start;
            align-items: flex-start;
            text-align: left;
            white-space: normal;
            height: auto;
            min-height: 0;
            padding: 0.92rem 0.95rem;
            border-radius: 10px;
            border: 1px solid rgba(15, 23, 42, 0.12);
            border-left: 4px solid transparent;
            background: #ffffff;
            color: #0f172a;
            box-shadow: 0 1px 2px rgba(15, 23, 42, 0.08);
            transition: transform 120ms ease, box-shadow 120ms ease, border-color 120ms ease;
            opacity: 1 !important;
        }
        .element-container:has(.fast-guidance-action-anchor) + div button[kind="secondary"]:hover {
            transform: translateY(-1px);
            box-shadow: 0 6px 14px rgba(15, 23, 42, 0.10);
            border-color: rgba(15, 23, 42, 0.18);
        }
        .element-container:has(.fast-guidance-action-anchor) + div button[kind="secondary"]:disabled {
            opacity: 1 !important;
            cursor: default;
            transform: none;
            box-shadow: 0 1px 2px rgba(15, 23, 42, 0.08);
            border-color: rgba(15, 23, 42, 0.12);
        }
        .element-container:has(.fast-guidance-action-anchor) + div button[kind="secondary"] p {
            margin: 0;
            line-height: 1.42;
        }
        .element-container:has(.fast-guidance-action-anchor) + div button[kind="secondary"] em {
            color: rgba(71, 85, 105, 0.9);
        }
        .element-container:has(.fast-guidance-action-anchor--fail) + div button[kind="secondary"] {
            background: #FEF2F2;
            border-left-color: #dc2626;
        }
        .element-container:has(.fast-guidance-action-anchor--warn) + div button[kind="secondary"] {
            background: #FFF7ED;
            border-left-color: #f59e0b;
        }
        .element-container:has(.fast-guidance-action-anchor--pass) + div button[kind="secondary"] {
            background: #F0FDF4;
            border-left-color: #16a34a;
        }
        .element-container:has(.fast-guidance-action-anchor--efficiency) + div button[kind="secondary"] {
            background: #EFF6FF;
            border-left-color: #2563eb;
        }
        .element-container:has(.fast-guidance-action-anchor--secondary) + div button[kind="secondary"] {
            margin-top: 1rem;
            border-left-width: 3px;
            box-shadow: inset 0 0 0 1px rgba(148, 163, 184, 0.12);
        }
        .element-container:has(.fast-guidance-action-anchor--secondary.fast-guidance-action-anchor--fail) + div button[kind="secondary"] {
            background: #FFF7F7;
            border-left-color: rgba(220, 38, 38, 0.38);
        }
        .element-container:has(.fast-guidance-action-anchor--secondary.fast-guidance-action-anchor--warn) + div button[kind="secondary"] {
            background: #FFFAF2;
            border-left-color: rgba(245, 158, 11, 0.42);
        }
        .element-container:has(.fast-guidance-action-anchor--secondary.fast-guidance-action-anchor--pass) + div button[kind="secondary"] {
            background: #F7FCF8;
            border-left-color: rgba(22, 163, 74, 0.34);
        }
        .element-container:has(.fast-guidance-action-anchor--secondary.fast-guidance-action-anchor--efficiency) + div button[kind="secondary"] {
            background: #F5F9FF;
            border-left-color: rgba(37, 99, 235, 0.34);
        }
        .fast-auto-design-summary {
            margin: 0.55rem 0 0.7rem 0;
            padding: 0.75rem 0.85rem;
            border-radius: 12px;
            border: 1px solid rgba(37, 99, 235, 0.18);
            background: rgba(239, 246, 255, 0.92);
        }
        .fast-auto-design-summary.success {
            border-color: rgba(22, 163, 74, 0.2);
            background: rgba(240, 253, 244, 0.94);
        }
        .fast-auto-design-summary-title {
            font-size: 0.92rem;
            font-weight: 800;
            color: rgba(15, 23, 42, 0.96);
            margin-bottom: 0.35rem;
        }
        .fast-auto-design-summary-step {
            font-size: 0.84rem;
            color: rgba(30, 41, 59, 0.92);
            margin-top: 0.16rem;
        }
        .element-container:has(.fast-guidance-action-anchor--static) + div button[kind="secondary"] em {
            color: rgba(100, 116, 139, 0.9);
        }
    </style>
    """,
        unsafe_allow_html=True,
    )

# CSS for seamless steps (summary table styling) is injected via inject_seamless_steps_css()

BEAM_MANAGER_EDITABLE_COLUMNS = [
    "beam_id",
    "beam_label",
    "sec_shape",
    "b",
    "bf",
    "tf",
    "bw",
    "tw",
    "D",
    "L",
    "cover_top",
    "cover_bot",
    "cover_side",
    "fc",
    "fsy",
    "bot1_count",
    "db_bot_1",
    "top1_count",
    "db_top_1",
    "lig_d",
    "lig_legs",
    "s_lig",
]

BEAM_MANAGER_STATUS_COLUMNS = [
    "active",
    "overall_status",
    "bending_status",
    "shear_status",
    "crack_status",
    "deflection_status",
    "last_checked_at",
]

BEAM_MANAGER_TABLE_COLUMNS = [
    "active",
    "beam_id",
    "beam_label",
    "overall_status",
    "bending_status",
    "shear_status",
    "crack_status",
    "deflection_status",
    "last_checked_at",
    "sec_shape",
    "b",
    "bf",
    "tf",
    "bw",
    "tw",
    "D",
    "L",
    "cover_top",
    "cover_bot",
    "cover_side",
    "fc",
    "fsy",
    "bot1_count",
    "db_bot_1",
    "top1_count",
    "db_top_1",
    "lig_d",
    "lig_legs",
    "s_lig",
]

BEAM_MANAGER_NUMERIC_COLUMNS = {
    "b",
    "bf",
    "tf",
    "bw",
    "tw",
    "D",
    "L",
    "cover_top",
    "cover_bot",
    "cover_side",
    "fc",
    "fsy",
    "bot1_count",
    "db_bot_1",
    "top1_count",
    "db_top_1",
    "lig_d",
    "lig_legs",
    "s_lig",
}

BEAM_MANAGER_INT_COLUMNS = {
    "bot1_count",
    "db_bot_1",
    "top1_count",
    "db_top_1",
    "lig_d",
    "lig_legs",
}


def _beam_option_labels():
    labels = {}
    beam_records = st.session_state.get("beam_records", {})
    for beam_id in st.session_state.get("beam_order", []):
        record = beam_records.get(beam_id, {})
        label = str(record.get("beam_label") or beam_id)
        labels[beam_id] = f"{label} ({beam_id})"
    return labels


def _format_beam_status(status: str) -> str:
    return format_report_status_label(status)


def _format_beam_status_badge(status: str, *, strength_status: str | None = None, detailing_status: str | None = None) -> str:
    return format_report_status_badge(
        status,
        strength_status=strength_status,
        detailing_status=detailing_status,
    )


def _format_last_checked(value) -> str:
    if not value:
        return "Not run"
    text = str(value).strip()
    if "T" in text:
        return text.replace("T", " ")
    return text


def _build_beam_schedule_df() -> pd.DataFrame:
    rows = []
    for item in build_beam_schedule_rows():
        params = {key: item.get(key, SHARED_DEFAULTS.get(key)) for key in BEAM_MANAGER_EDITABLE_COLUMNS}
        row = {
            "active": "🔵 ACTIVE" if item.get("active") else "",
            "beam_id": item.get("beam_id"),
            "beam_label": item.get("beam_label"),
            "overall_status": _format_beam_status_badge(
                item.get("overall_status"),
                strength_status=item.get("strength_status"),
                detailing_status=item.get("detailing_status"),
            ),
            "bending_status": _format_beam_status_badge(item.get("bending_status")),
            "shear_status": _format_beam_status_badge(item.get("shear_status")),
            "crack_status": _format_beam_status_badge(item.get("crack_status")),
            "deflection_status": _format_beam_status_badge(item.get("deflection_status")),
            "last_checked_at": _format_last_checked(item.get("last_checked_at")),
        }
        for column in BEAM_MANAGER_EDITABLE_COLUMNS:
            if column in row:
                continue
            row[column] = params.get(column)
        rows.append(row)
    return pd.DataFrame(rows, columns=BEAM_MANAGER_TABLE_COLUMNS)


def _format_report_value(value, digits: int = 2):
    if value is None:
        return "-"
    if isinstance(value, float):
        return round(value, digits)
    return value


def _dict_to_label_value_df(data: dict, value_label: str = "Value") -> pd.DataFrame:
    rows = []
    for key, value in (data or {}).items():
        rows.append(
            {
                "Item": str(key).replace("_", " ").title(),
                value_label: _format_report_value(value, 3 if "util" in str(key).lower() else 2),
            }
        )
    return pd.DataFrame(rows)


def _build_schedule_preview_df() -> pd.DataFrame:
    rows = []
    for item in build_beam_schedule_export_rows():
        if item.get("sec_shape") == "T":
            geometry_summary = f"T bw {item.get('bw') or 0} / bf {item.get('bf') or 0} / D {item.get('D') or 0} / L {item.get('L') or 0}"
        elif item.get("sec_shape") == "I":
            geometry_summary = f"I tw {item.get('tw') or 0} / bf {item.get('bf') or 0} / D {item.get('D') or 0} / L {item.get('L') or 0}"
        else:
            geometry_summary = f"RECT {item.get('b') or 0} x {item.get('D') or 0} / L {item.get('L') or 0}"
        reo_summary = (
            f"Bottom {int(item.get('bot1_count') or 0)}N{int(item.get('db_bot_1') or 0)} | "
            f"Top {int(item.get('top1_count') or 0)}N{int(item.get('db_top_1') or 0)} | "
            f"Lig N{int(item.get('lig_d') or 0)} @ {int(item.get('s_lig') or 0)}"
        )
        rows.append(
            {
                "Active": "ACTIVE" if item.get("active") else "",
                "Beam ID": item.get("beam_id"),
                "Label": item.get("beam_label"),
                "Geometry": geometry_summary,
                "Reinforcement": reo_summary,
                "Overall": _format_beam_status_badge(
                    item.get("overall_status"),
                    strength_status=item.get("strength_status"),
                    detailing_status=item.get("detailing_status"),
                ),
                "Bending": _format_beam_status_badge(item.get("bending_status")),
                "Shear": _format_beam_status_badge(item.get("shear_status")),
                "Crack": _format_beam_status_badge(item.get("crack_status")),
                "Deflection": _format_beam_status_badge(item.get("deflection_status")),
                "Last Checked": _format_last_checked(item.get("last_checked_at")),
            }
        )
    return pd.DataFrame(rows)


def _coerce_beam_schedule_value(column: str, value):
    if pd.isna(value):
        return SHARED_DEFAULTS.get(column)
    if column in BEAM_MANAGER_INT_COLUMNS:
        try:
            return int(value)
        except Exception:
            return int(SHARED_DEFAULTS.get(column, 0) or 0)
    if column in BEAM_MANAGER_NUMERIC_COLUMNS:
        try:
            return float(value)
        except Exception:
            return SHARED_DEFAULTS.get(column)
    if column == "beam_label":
        text = str(value).strip()
        return text or "Beam"
    if column == "sec_shape":
        text = str(value or "RECT").strip().upper()
        return text if text in ("RECT", "T", "I") else "RECT"
    return value


def _sync_beam_records_from_schedule_df(schedule_df: pd.DataFrame) -> set[str]:
    changed_beam_ids = set()
    if schedule_df is None or schedule_df.empty:
        return changed_beam_ids

    beam_records = st.session_state.get("beam_records", {})
    for row in schedule_df.to_dict("records"):
        beam_id = row.get("beam_id")
        if beam_id not in beam_records:
            continue

        record = beam_records[beam_id]
        params = dict(record.get("params", {}) or {})
        row_changed = False
        params_changed = False

        new_label = _coerce_beam_schedule_value("beam_label", row.get("beam_label"))
        if record.get("beam_label") != new_label:
            record["beam_label"] = new_label
            row_changed = True

        for column in BEAM_MANAGER_EDITABLE_COLUMNS:
            if column in ("beam_id", "beam_label"):
                continue
            new_value = _coerce_beam_schedule_value(column, row.get(column))
            if params.get(column) != new_value:
                params[column] = new_value
                row_changed = True
                params_changed = True

        if row_changed:
            meta = record.get("meta") if isinstance(record.get("meta"), dict) else {}
            meta["updated_at"] = datetime.utcnow().isoformat(timespec="seconds")
            record["params"] = params
            record["meta"] = meta
            if params_changed:
                # Edited schedule rows are passive stored data until explicitly loaded again.
                record["summary"] = make_not_run_beam_summary()
            changed_beam_ids.add(beam_id)

    return changed_beam_ids


# ------------------------------------------------------------
#  SHARED HELPERS FOR BAR & LEG LAYOUT
# ------------------------------------------------------------
def _two_row_positions_width(n_bars, bar_dia, w_min, w_max):
    """
    Decide bar positions along width for up to 2 rows.

    Rules:
      - A single row can carry at most `max_single` bars based on min spacing.
      - If n_bars > max_single, we use 2 rows and ensure BOTH rows
        respect the same max bars/spacing rule.
      - Row 2:
          * if 1 bar  -> centred
          * if >=2    -> spaced like row 1 (linspace over width)
    """
    if n_bars <= 0:
        return [], []

    span = w_max - w_min
    if span <= 0:
        return [], []

    # basic spacing rule
    min_pitch = max(bar_dia * 1.6, span / 20.0)
    max_single = max(1, int(span // min_pitch))

    # One row OK
    if n_bars <= max_single:
        xs1 = np.linspace(w_min, w_max, n_bars)
        return xs1.tolist(), []

    # Two rows, each respecting max_single
    n1 = min(max_single, math.ceil(n_bars / 2))
    n2 = n_bars - n1
    if n2 > max_single:
        n2 = max_single
        n1 = n_bars - n2

    xs1 = np.linspace(w_min, w_max, n1)

    if n2 <= 0:
        xs2 = np.array([])
    elif n2 == 1:
        xs2 = np.array([(w_min + w_max) / 2.0])
    else:
        xs2 = np.linspace(w_min, w_max, n2)

    return xs1.tolist(), xs2.tolist()


def _get_cached_results(bucket: str):
    results = st.session_state.get("results", {})
    return results.get(bucket)


def _get_results_updated_at(bucket: str):
    meta = st.session_state.get("results_meta", {})
    return (meta.get(bucket) or {}).get("updated_at")


def _overall_status_from_rows(rows):
    if not rows:
        return "—", "rgba(31, 119, 180, 0.08)"
    filtered = []
    for r in rows:
        if not isinstance(r, dict):
            continue
        if r.get("is_informational"):
            continue
        stt = str(r.get("status", "")).upper()
        if stt == "INFO":
            continue
        filtered.append(r)
    if not filtered:
        return "—", "rgba(31, 119, 180, 0.08)"
    statuses = [str(r.get("status", "")).upper() for r in filtered]
    if any("FAIL" in s or s == "NG" for s in statuses):
        return "FAIL", "rgba(255,0,0,0.12)"
    if any("WARN" in s or "NEAR LIMIT" in s or s == "CHECK" for s in statuses):
        return "NEAR LIMIT", "rgba(255,193,7,0.15)"
    if any("PASS" in s or s == "OK" for s in statuses):
        return "PASS", "rgba(0,128,0,0.12)"
    return "—", "rgba(31, 119, 180, 0.08)"


def _primary_row(rows):
    if not rows:
        return None
    for r in rows:
        if r.get("is_primary"):
            return r
    return rows[0]


def _pack_meta(name, pack):
    rows = (pack or {}).get("rows") or []
    return {
        "rows_n": len(rows),
        "uids": [r.get("uid") for r in rows][:30],
        "statuses": [r.get("status") for r in rows][:30],
    }


def _normalise_row(r: dict, route_page: str) -> dict:
    status = r.get("status", "—")
    is_informational = bool(r.get("is_informational", False))
    ok = r.get("ok", None)
    if is_informational or str(status).upper() == "INFO":
        ok = None
    elif ok is None:
        if status == "PASS":
            ok = True
        elif status == "FAIL":
            ok = False
        elif status in ("NEAR LIMIT", "WARN", "CHECK"):
            ok = None

    cap = r.get("capacity")
    act = r.get("action")
    calc = r.get("calculated")
    req = r.get("requirement")
    val = r.get("value", "—")
    lim = r.get("limit", "—")
    if cap is None or str(cap).strip() == "":
        cap = calc if calc is not None and str(calc).strip() != "" else val
    if act is None or str(act).strip() == "":
        act = req if req is not None and str(req).strip() != "" else lim
    if calc is None or str(calc).strip() == "":
        calc = cap
    if req is None or str(req).strip() == "":
        req = act

    return {
        "uid": r.get("uid", ""),
        "title": r.get("title", ""),
        "row_type": r.get("row_type", ""),
        "calculated": calc,
        "requirement": req,
        "capacity": cap,
        "action": act,
        "value": val,
        "limit": lim,
        "util": r.get("util") if r.get("util") is not None else "—",
        "status": status,
        "ok": ok,
        "is_informational": is_informational,
        "is_primary": bool(r.get("is_primary", False)),
        "route_page": r.get("route_page", route_page),
        "tab": r.get("tab", ""),
    }




def _internal_leg_positions(y_min, y_max, n_legs):
    """Internal stirrup leg positions across width."""
    if n_legs <= 2:
        return []
    span = y_max - y_min
    if span <= 0:
        return []
    # equally spaced between outer legs
    return [y_min + span * j / (n_legs - 1) for j in range(1, n_legs - 1)]


# ------------------------------------------------------------
#  SHAPE-AWARE OUTLINE + CLAMP HELPERS (Section A)
# ------------------------------------------------------------
def _get_sec_shape():
    # Prefer shared value; fall back safely
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
    sec_shape = _get_sec_shape()
    D = float(get_param("D", 600.0))

    if sec_shape == "RECT":
        b = float(get_param("b", 400.0))
        pts = [(0, 0), (b, 0), (b, D), (0, D), (0, 0)]
        return pts, b, D

    if sec_shape == "T":
        bf = float(get_param("bf", 600.0))
        tf = float(get_param("tf", 120.0))
        bw = float(get_param("bw", 300.0))

        # Sanity clamps
        tf = max(1.0, min(tf, D))
        bw = max(1.0, min(bw, bf))

        x_web0 = 0.5 * (bf - bw)
        x_web1 = x_web0 + bw

        pts = [
            (0, 0), (bf, 0), (bf, tf),
            (x_web1, tf), (x_web1, D),
            (x_web0, D), (x_web0, tf),
            (0, tf),
            (0, 0),
        ]
        return pts, bf, D

    # sec_shape == "I"
    bf = float(get_param("bf", 600.0))
    tf = float(get_param("tf", 120.0))
    tw = float(get_param("tw", 200.0))

    tf = max(1.0, min(tf, 0.5 * D))
    tw = max(1.0, min(tw, bf))

    x_web0 = 0.5 * (bf - tw)
    x_web1 = x_web0 + tw
    y_bot_flange_top = D - tf

    pts = [
        (0, 0), (bf, 0), (bf, tf),
        (x_web1, tf), (x_web1, y_bot_flange_top),
        (bf, y_bot_flange_top), (bf, D),
        (0, D), (0, y_bot_flange_top),
        (x_web0, y_bot_flange_top), (x_web0, tf),
        (0, tf),
        (0, 0),
    ]
    return pts, bf, D


def _xspan_at_y(pts, y):
    """Return (xmin, xmax) of polygon intersection with horizontal line y."""
    xs = []
    for (x1, y1), (x2, y2) in zip(pts[:-1], pts[1:]):
        # ignore horizontal edges
        if y1 == y2:
            continue
        # check if y is within edge range (half-open to avoid double counts)
        if (y1 <= y < y2) or (y2 <= y < y1):
            t = (y - y1) / (y2 - y1)
            x = x1 + t * (x2 - x1)
            xs.append(x)
    if len(xs) < 2:
        return None
    xs.sort()
    return xs[0], xs[-1]


def _clamp_bar_xs_to_outline(xs, y, pts, bar_d):
    span = _xspan_at_y(pts, y)
    if not span:
        return xs
    xmin, xmax = span
    r = 0.5 * max(0.0, float(bar_d))
    xmin += r
    xmax -= r
    if xmax <= xmin:
        # too tight: collapse to centre
        xc = 0.5 * (span[0] + span[1])
        return [xc for _ in xs]
    return [min(max(x, xmin), xmax) for x in xs]


# ------------------------------------------------------------
#  MINI 2D CROSS-SECTION LABELS (SECTION A)
# ------------------------------------------------------------
def _section_dim_scale_mm(dims: dict) -> tuple[float, float, float, float, float, float, float, float, float, float]:
    """
    Shared geometry for section dimension overlays (mm).
    Returns (D, bf, tf, bw, tw, x_span, x_off, y_off, ah, aw).
    Keep in sync with _ti_annotation_bounds_for_model_mm.
    """
    D = float(dims.get("D", 0.0) or 0.0)
    bf = float(dims.get("bf", 0.0) or 0.0)
    tf = float(dims.get("tf", 0.0) or 0.0)
    bw = float(dims.get("bw", 0.0) or 0.0)
    tw = float(dims.get("tw", 0.0) or 0.0)
    b = float(dims.get("b", 0.0) or 0.0)
    x_span = max(bf, bw, tw, b, 1.0)
    x_off = 0.08 * x_span
    y_off = 0.08 * max(D, 1.0)
    ah = 0.025 * x_span
    aw = 0.012 * max(D, 1.0)
    return D, bf, tf, bw, tw, x_span, x_off, y_off, ah, aw


def _ti_annotation_bounds_for_model_mm(shape_name: str, dims: dict) -> tuple[float, float, float, float] | None:
    """
    Axis-data bounds (mm) that contain T/I dimension lines, arrowheads, and typical label positions.
    None if this shape does not use the T/I dimension overlay.
    """
    sn = str(shape_name or "")
    if not (sn.startswith("T-Section") or sn.startswith("I-Section")):
        return None
    D, bf, _tf, bw, tw, x_span, x_off, y_off, ah, _aw = _section_dim_scale_mm(dims)
    # Slack for ~12pt annotations and arrowhead extent beyond extension points
    txt = max(12.0, 0.022 * max(x_span, D, 1.0))
    xmin = min(0.0, -1.60 * x_off - ah - txt)
    xmax = max(bf, bf + x_off + ah + txt)
    ymin = min(0.0, -1.45 * y_off - txt)
    ymax = max(D, D + 1.45 * y_off + txt)
    if sn.startswith("T-Section") and bw > 0:
        x_web1 = (bf - bw) / 2.0 + bw
        xmax = max(xmax, x_web1 + txt)
        ymax = max(ymax, D + 0.75 * y_off + txt)
    if sn.startswith("I-Section") and tw > 0:
        x_web1 = (bf - tw) / 2.0 + tw
        xmax = max(xmax, x_web1 + txt)
    return xmin, xmax, ymin, ymax


def _add_section_dimension_labels(fig, *, shape_name: str, dims: dict, reo: dict):
    """
    Adds engineering-style dimension labels with double-ended arrows to Plotly 2D section figure.
    Coordinates are in mm, with y=0 at top and y increasing downward.
    """
    # NOTE: Plotly doesn't have "double arrow" lines as a primitive,
    # so we draw the dimension line + small V-shaped arrowheads at BOTH ends.
    import math

    D, bf, tf, bw, tw, x_span, x_off, y_off, ah, aw = _section_dim_scale_mm(dims)

    cover_top = float(reo.get("cover_top", 0.0) or 0.0)
    cover_bot = float(reo.get("cover_bot", 0.0) or 0.0)
    cover_side = float(reo.get("cover_side", 0.0) or 0.0)

    def _add_line(x0, y0, x1, y1):
        fig.add_shape(type="line", x0=x0, y0=y0, x1=x1, y1=y1,
                      line=dict(width=1, color="black"))

    def _arrowhead_at_point(px, py, angle_rad):
        """
        Draws a small 'V' arrowhead centered at (px,py) pointing along angle_rad.
        """
        # two legs at +/- 25 degrees
        for sgn in (-1, +1):
            a = angle_rad + sgn * math.radians(25)
            x1 = px - ah * math.cos(a)
            y1 = py - ah * math.sin(a)
            _add_line(px, py, x1, y1)

    def add_dim_x(x0, x1, y, text):
        # dimension line
        _add_line(x0, y, x1, y)
        # arrowheads (pointing inward)
        _arrowhead_at_point(x0, y, 0.0)          # points to +x
        _arrowhead_at_point(x1, y, math.pi)      # points to -x
        # text
        fig.add_annotation(
            x=(x0 + x1) / 2.0,
            y=y - 0.45 * y_off,
            text=text,
            showarrow=False,
            font=dict(size=12, color="black"),
        )

    def add_dim_y(x, y0, y1, text):
        # dimension line
        _add_line(x, y0, x, y1)
        # arrowheads (pointing inward)
        _arrowhead_at_point(x, y0, math.pi/2)        # points down
        _arrowhead_at_point(x, y1, -math.pi/2)       # points up
        # text
        fig.add_annotation(
            x=x - 0.60 * x_off,
            y=(y0 + y1) / 2.0,
            text=text,
            showarrow=False,
            font=dict(size=12, color="black"),
        )

    # ----- Dimension labels per shape -----
    if shape_name.startswith("T-Section"):
        add_dim_x(0.0, bf, -y_off, f"bf = {bf:.0f} mm")
        add_dim_y(-x_off, 0.0, D, f"D = {D:.0f} mm")
        add_dim_y(bf + x_off, 0.0, tf, f"tf = {tf:.0f} mm")

        if bw > 0:
            x_web0 = (bf - bw) / 2.0
            x_web1 = x_web0 + bw
            add_dim_x(x_web0, x_web1, D + 0.75 * y_off, f"bw = {bw:.0f} mm")

    elif shape_name.startswith("I-Section"):
        add_dim_x(0.0, bf, -y_off, f"bf = {bf:.0f} mm")
        add_dim_y(-x_off, 0.0, D, f"D = {D:.0f} mm")
        add_dim_y(bf + x_off, 0.0, tf, f"tf = {tf:.0f} mm")

        if tw > 0:
            x_web0 = (bf - tw) / 2.0
            x_web1 = x_web0 + tw
            add_dim_x(x_web0, x_web1, D / 2.0, f"tw = {tw:.0f} mm")

    else:
        if D > 0:
            add_dim_y(-x_off, 0.0, D, f"D = {D:.0f} mm")

    # Covers note
    fig.add_annotation(
        x=0.5 * x_span,
        y=D + 1.45 * y_off,
        text=f"cover(top/bot/side) = {cover_top:.0f}/{cover_bot:.0f}/{cover_side:.0f} mm",
        showarrow=False,
        font=dict(size=12, color="black"),
    )

    return fig


# ------------------------------------------------------------
#  MINI 2D CROSS-SECTION  (SECTION A)
# ------------------------------------------------------------
def make_summary_cross_section_figure():
    import streamlit as st
    import plotly.graph_objects as go
    from section_props.plot import apply_section_axes
    from section_layout import compute_section_layout

    layout = compute_section_layout()
    shape_name = str(layout.get("shape_name", "Rectangle (b × D)"))
    shape_name = layout.get("shape_name", "Rectangle (b × D)")
    dims = layout.get("dims", {})
    reo = layout.get("reo", {})
    shape_key = str(shape_name).strip().lower()
    is_ti = ("t-section" in shape_key) or ("i-section" in shape_key) or shape_key.startswith("t") or shape_key.startswith("i")
    is_rect = ("rectangle" in shape_key) or (shape_key == "rect")

    def _finalize_section_figure(
        fig,
        width_mm: float,
        depth_mm: float,
        *,
        shape_name: str | None = None,
        dims: dict | None = None,
    ):
        """
        Set axis limits with padding. For T/I, union section [0,W]×[0,D] with dimension annotation
        extents so arrows and labels are not clipped; then add a small margin (5–8% typical).
        """
        fig.update_layout(
            autosize=True,
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            margin=dict(l=6, r=6, t=6, b=6),
        )
        gx0, gx1 = 0.0, float(width_mm)
        gy0, gy1 = 0.0, float(depth_mm)
        ext = None
        if shape_name is not None and dims is not None:
            ext = _ti_annotation_bounds_for_model_mm(str(shape_name), dims)
        if ext is not None:
            ex0, ex1, ey0, ey1 = ext
            gx0 = min(gx0, ex0)
            gx1 = max(gx1, ex1)
            gy0 = min(gy0, ey0)
            gy1 = max(gy1, ey1)
        span_x = max(gx1 - gx0, 1e-6)
        span_y = max(gy1 - gy0, 1e-6)
        if ext is not None:
            pad_x = max(0.05 * span_x, 0.03 * max(width_mm, 1.0), 16.0)
            pad_y = max(0.08 * span_y, 0.05 * max(depth_mm, 1.0), 20.0)
        else:
            pad_x = max(25.0, 0.08 * max(width_mm, 1.0))
            pad_y = max(25.0, 0.08 * max(depth_mm, 1.0))
        fig.update_xaxes(
            range=[gx0 - pad_x, gx1 + pad_x],
            showgrid=False,
            zeroline=False,
        )
        fig.update_yaxes(
            range=[gy1 + pad_y, gy0 - pad_y],
            showgrid=False,
            zeroline=False,
            scaleanchor="x",
            scaleratio=1,
        )
        return fig

    if is_ti:
        try:
            fig = make_sectionA_figure(
                shape_name=shape_name,
                dims=dims,
                reo=reo,
                show_shear=True,
                tension_face=st.session_state.get("active_tension_face"),
            )
            fig = _add_section_dimension_labels(fig, shape_name=shape_name, dims=dims, reo=reo)

            W = float(dims.get("bf", dims.get("b", 0.0)) or 0.0)
            D = float(dims.get("D", 0.0) or 0.0)
            return _finalize_section_figure(fig, W, D, shape_name=shape_name, dims=dims)

        except ValueError as e:
            st.error(f"Reinforcement layout failed: {e}")

            # Fall back to diagram with ligs disabled (still shows section outline + dims)
            reo_no_bars = dict(reo)
            reo_no_bars.update({
                "nb_top": 0,
                "db_top": 0.0,
                "nb_bot": 0,
                "db_bot": 0.0,
                "lig_d": 0.0,
                "lig_legs": 0,
            })

            fig = make_sectionA_figure(
                shape_name=shape_name,
                dims=dims,
                reo=reo_no_bars,
                show_shear=True,
                tension_face=st.session_state.get("active_tension_face"),
            )
            fig = _add_section_dimension_labels(fig, shape_name=shape_name, dims=dims, reo=reo_no_bars)

            W = float(dims.get("bf", dims.get("b", 0.0)) or 0.0)
            D = float(dims.get("D", 0.0) or 0.0)
            return _finalize_section_figure(fig, W, D, shape_name=shape_name, dims=dims)

    if not is_rect:
        return None

    # --- Unified 2D reo: draw from canonical layout["reo_layout"] (same as 3D) ---
    b = float(dims.get("b", 0.0) or 0.0)
    D = float(dims.get("D", 0.0) or 0.0)

    fig = go.Figure()
    fig.add_shape(
        type="rect",
        x0=0, y0=0, x1=b, y1=D,
        line=dict(color="black", width=2),
        fillcolor="rgba(0,0,0,0)",
    )

    reo_layout = layout.get("reo_layout") or {"bottom": [], "top": []}

    def _add_layer_circles(fig, layer, color):
        xs = layer.get("x", []) or []
        y = float(layer.get("y", 0.0) or 0.0)
        db = float(layer.get("db", 0.0) or 0.0)
        if (not xs) or (db <= 0):
            return

        r = db / 2.0
        for x in xs:
            x = float(x)
            fig.add_shape(
                type="circle",
                x0=x - r, y0=y - r,
                x1=x + r, y1=y + r,
                line=dict(color="black", width=1),
                fillcolor=color,
                opacity=1.0,
            )

    for layer in (reo_layout.get("bottom") or []):
        _add_layer_circles(fig, layer, "rgba(0,0,255,0.9)")

    for layer in (reo_layout.get("top") or []):
        _add_layer_circles(fig, layer, "rgba(255,0,0,0.9)")

    lig_d = float(reo.get("lig_d", 0.0) or 0.0)
    lig_legs = int(reo.get("lig_legs", 0) or 0)

    if lig_d > 0 and lig_legs >= 2:
        # covers (use whatever your reo dict uses; fall back to session state)
        cover_side = float(reo.get("cover_side", st.session_state.get("cover_side", 40.0)) or 40.0)
        cover_top = float(reo.get("cover_top", st.session_state.get("cover_top", 40.0)) or 40.0)
        cover_bot = float(reo.get("cover_bot", st.session_state.get("cover_bot", 40.0)) or 40.0)

        x0, x1 = cover_side, b - cover_side
        y0, y1 = cover_top, D - cover_bot

        if x1 > x0 and y1 > y0:
            # closed stirrup outline
            fig.add_shape(
                type="rect",
                x0=x0, y0=y0, x1=x1, y1=y1,
                line=dict(color="black", width=2),
                fillcolor="rgba(0,0,0,0)",
            )

            # internal legs if any
            if lig_legs > 2:
                span = x1 - x0
                for j in range(1, lig_legs - 1):
                    x = x0 + span * j / (lig_legs - 1)
                    fig.add_shape(
                        type="line",
                        x0=x, y0=y0, x1=x, y1=y1,
                        line=dict(color="black", width=2),
                    )

    apply_section_axes(fig, W=b, D=D)
    return _finalize_section_figure(fig, b, D)

# -------------------------------------------------------------------
# Backwards-compatible entrypoint expected by app.py
# Do not remove: app.py routes to inputs_page.render_inputs
# -------------------------------------------------------------------
def render_inputs():
    """
    Stable alias for the Inputs page renderer.

    Some versions of app.py call inputs_page.render_inputs.
    If the internal renderer is renamed, keep this alias so routing never breaks.
    """
    # Try common renderer names in order of preference
    if "render_inputs_page" in globals():
        return globals()["render_inputs_page"]()
    if "render_page" in globals():
        return globals()["render_page"]()
    if "render" in globals():
        return globals()["render"]()
    if "page" in globals():
        return globals()["page"]()

    raise AttributeError(
        "inputs_page.py: No Inputs renderer found. Expected one of: "
        "render_inputs_page(), render_page(), render(), page()."
    )


# ------------------------------------------------------------
#  3D BEAM – BENDING & SHEAR VISUAL  (SECTION A)
# ------------------------------------------------------------
def make_beam_3d_figure():
    # --- parameters from session state ---
    from section_layout import compute_section_layout
    
    layout = compute_section_layout()
    if st.session_state.get("_debug_reo_layout", False):
        st.write("3D reo_layout:", (layout.get("reo_layout") if isinstance(layout, dict) else None))
    shape_name = str(layout.get("shape_name", "Rectangle (b × D)"))
    dims = layout.get("dims", {})
    reo = layout.get("reo", {})
    b = float(dims.get("b", get_param("b", 400.0)))
    D = float(dims.get("D", get_param("D", 600.0)))
    L = float(get_param("L", 3000.0))
    L_plot = max(min(L, 3000.0), 400.0)

    cover_bot = float(reo.get("cover_bot", 40.0))
    cover_top = float(reo.get("cover_top", 40.0))
    cover_side = reo.get("cover_side")
    if cover_side is None:
        cover_side = min(cover_top, cover_bot)
    cover_side = float(cover_side)

    shared_state = _shared_state_snapshot()
    lig_d = float(shared_state.get("lig_d", reo.get("lig_d", 0.0)) or 0.0)
    lig_legs = int(shared_state.get("lig_legs", reo.get("lig_legs", 0)) or 0)
    s_lig = float(shared_state.get("s_lig", reo.get("s_lig", 200.0)) or 200.0)

    traces = []

    # ----- section outline wireframe extruded along length -----
    pts, b_box, D = _get_outline_points_and_bbox()

    # --- RECT concrete body (faint) so outline never "disappears" visually ---
    # We only add this for RECT (T/I use other 3D viewer)
    if shape_name.startswith("Rectangle"):
        # Simple box mesh (x = length, y = width, z = depth from top)
        x0, x1 = 0.0, float(L_plot)
        y0, y1 = 0.0, float(b_box)
        z0, z1 = 0.0, float(D)

        vx = np.array([x0, x1, x1, x0, x0, x1, x1, x0], dtype=float)
        vy = np.array([y0, y0, y1, y1, y0, y0, y1, y1], dtype=float)
        vz = np.array([z0, z0, z0, z0, z1, z1, z1, z1], dtype=float)

        # Triangulated faces
        tri_i = [0, 0, 0, 4, 4, 1, 5, 2, 6, 3, 7, 6]
        tri_j = [1, 2, 3, 5, 7, 5, 6, 6, 7, 7, 4, 2]
        tri_k = [2, 3, 0, 6, 4, 2, 7, 3, 4, 0, 5, 1]

        traces.append(
            go.Mesh3d(
                x=vx,
                y=vy,
                z=vz,
                i=tri_i,
                j=tri_j,
                k=tri_k,
                color="#cccccc",
                opacity=0.18,
                flatshading=True,
                hoverinfo="skip",
                showlegend=False,
            )
        )

    # Map 2D (x,y) -> 3D (y,z) because x in section = width (3D y), y in section = depth (3D z)
    ys = [p[0] for p in pts]
    zs = [p[1] for p in pts]

    # outline at x=0 and x=L
    traces.append(go.Scatter3d(
        x=[0.0] * len(pts),
        y=ys,
        z=zs,
        mode="lines",
        line=dict(width=6, color="rgba(20,20,20,0.95)"),
        hoverinfo="skip",
        showlegend=False,
    ))
    traces.append(go.Scatter3d(
        x=[L_plot] * len(pts),
        y=ys,
        z=zs,
        mode="lines",
        line=dict(width=6, color="rgba(20,20,20,0.95)"),
        hoverinfo="skip",
        showlegend=False,
    ))

    # connect corresponding vertices to show extrusion
    for i in range(len(pts) - 1):
        traces.append(go.Scatter3d(
            x=[0.0, L_plot],
            y=[ys[i], ys[i]],
            z=[zs[i], zs[i]],
            mode="lines",
            line=dict(width=6, color="rgba(20,20,20,0.95)"),
            hoverinfo="skip",
            showlegend=False,
        ))

    # ----- longitudinal bar positions - use canonical layout -----
    reo_layout = layout.get("reo_layout") or {"bottom": [], "top": []}

    def _add_bar_cylinder(traces, x0, x1, y0, z0, db, color):
        """Add a true-scale cylinder from x0->x1 with radius=db/2 in data units (mm)."""
        r = float(db) / 2.0
        if r <= 0:
            return

        n_theta = 18  # balance quality vs performance
        theta = np.linspace(0, 2 * np.pi, n_theta)

        # Surface grids (n_theta x 2)
        X = np.column_stack([np.full(n_theta, x0), np.full(n_theta, x1)])
        Y = np.column_stack([y0 + r * np.cos(theta), y0 + r * np.cos(theta)])
        Z = np.column_stack([z0 + r * np.sin(theta), z0 + r * np.sin(theta)])

        traces.append(
            go.Surface(
                x=X, y=Y, z=Z,
                colorscale=[[0, color], [1, color]],
                showscale=False,
                opacity=1.0,
                hoverinfo="skip",
                name="Reo",
            )
        )

    def _iter_band_xy(layer_data):
        """Yield (section_x, section_y, db) per bar; supports scalar or per-bar y lists."""
        xs = layer_data.get("x") or []
        y_raw = layer_data.get("y")
        db = float(layer_data.get("db", 0.0) or 0.0)
        if not xs or db <= 0.0:
            return
        if isinstance(y_raw, (int, float)):
            yf = float(y_raw)
            for xp in xs:
                yield float(xp), yf, db
            return
        ys = list(y_raw)
        if len(ys) == len(xs):
            for xp, yp in zip(xs, ys):
                yield float(xp), float(yp), db
        elif len(ys) == 1:
            yf = float(ys[0])
            for xp in xs:
                yield float(xp), yf, db
        else:
            n = min(len(xs), len(ys))
            for i in range(n):
                yield float(xs[i]), float(ys[i]), db

    max_bar_d = 0.0
    for layer_list in (reo_layout.get("bottom", []), reo_layout.get("top", [])):
        for layer_data in layer_list:
            max_bar_d = max(max_bar_d, float(layer_data.get("db", 0.0)))
    horiz_clear = 0.5 * max_bar_d
    reo_points_3d = []

    shape_key = normalise_shape_name(shape_name)
    if shape_key in ("T", "I"):
        resolved = resolve_longitudinal_bars_from_layout(
            shape_name=shape_name,
            dims=dims,
            reo_layout=reo_layout,
        )
        if st.session_state.get("_debug_reo_layout", False):
            for msg in dev_warnings_bars_outside_concrete(resolved, shape_name, dims):
                st.warning(msg)
        for bar in resolved:
            x_pos = float(bar.get("x_mm", 0.0) or 0.0)
            z_pos = float(bar.get("y_mm", 0.0) or 0.0)
            db = float(bar.get("dia_mm", 0.0) or 0.0)
            face = str(bar.get("face") or "bottom")
            color = "#d62728" if face == "top" else "#1f77b4"
            reo_points_3d.append({"x": x_pos, "y": z_pos, "db": db})
            _add_bar_cylinder(traces, 0.0, L_plot, x_pos, z_pos, db, color)
    else:
        # Rectangle: legacy top/bottom bands (zip x/y for multi-row layouts).
        for layer_data in reo_layout.get("bottom", []):
            for x_pos, z_pos, db in _iter_band_xy(layer_data):
                reo_points_3d.append({"x": x_pos, "y": z_pos, "db": db})
                _add_bar_cylinder(traces, 0.0, L_plot, x_pos, z_pos, db, "#1f77b4")
        for layer_data in reo_layout.get("top", []):
            for x_pos, z_pos, db in _iter_band_xy(layer_data):
                reo_points_3d.append({"x": x_pos, "y": z_pos, "db": db})
                _add_bar_cylinder(traces, 0.0, L_plot, x_pos, z_pos, db, "#d62728")

    # ----- shear ligs -----
    def add_shear_hoop_at_x(x0):
        # Same shear cage as 2D / compute_shear_reo_layout_T_I (web-only for T/I). Do not
        # expand stirrups to min/max of all longitudinal bars (flange bars would span void).
        _cage_lc = layout.get("cage") or {}
        _ok_cage = (
            _cage_lc.get("x0") is not None
            and _cage_lc.get("x1") is not None
            and _cage_lc.get("y0") is not None
            and _cage_lc.get("y1") is not None
            and float(_cage_lc["x1"]) > float(_cage_lc["x0"])
            and float(_cage_lc["y1"]) > float(_cage_lc["y0"])
        )
        if _ok_cage:
            y_left = float(_cage_lc["x0"])
            y_right = float(_cage_lc["x1"])
            z_top = float(_cage_lc["y0"])
            z_bot = float(_cage_lc["y1"])
        elif reo_points_3d:
            y_left = min(pt["x"] - pt["db"] / 2.0 for pt in reo_points_3d)
            y_right = max(pt["x"] + pt["db"] / 2.0 for pt in reo_points_3d)
            z_top = min(pt["y"] - pt["db"] / 2.0 for pt in reo_points_3d)
            z_bot = max(pt["y"] + pt["db"] / 2.0 for pt in reo_points_3d)
        else:
            y_left = cover_side
            y_right = b - cover_side
            z_top = cover_top + max(lig_d, 6.0)
            z_bot = D - (cover_bot + max(lig_d, 6.0))

        min_z = 5.0
        max_z = D - 5.0
        min_y = 5.0
        max_y = float(b_box) - 5.0
        y_left = float(np.clip(y_left, min_y, max_y))
        y_right = float(np.clip(y_right, min_y, max_y))
        z_top_c = float(np.clip(z_top, min_z, max_z))
        z_bot_c = float(np.clip(z_bot, min_z, max_z))

        Xs = [x0] * 5
        Ys = [y_left, y_right, y_right, y_left, y_left]
        Zs = [z_top_c, z_top_c, z_bot_c, z_bot_c, z_top_c]

        lw = max(1.5, abs(lig_d) * 0.35)
        traces.append(
            go.Scatter3d(
                x=Xs,
                y=Ys,
                z=Zs,
                mode="lines",
                line=dict(width=lw, color="black"),
                hoverinfo="skip",
                showlegend=False,
            )
        )

        if lig_legs > 2:
            for yi in _internal_leg_positions(y_left, y_right, lig_legs):
                traces.append(
                    go.Scatter3d(
                        x=[x0, x0],
                        y=[yi, yi],
                        z=[z_top_c, z_bot_c],
                        mode="lines",
                        line=dict(width=lw * 0.9, color="black"),
                        hoverinfo="skip",
                        showlegend=False,
                    )
                )

    if lig_d > 0 and s_lig > 0 and lig_legs >= 2:
        s_eff = max(40.0, float(s_lig))
        n_hoops = int(max(1, min(80, round(L_plot / s_eff))))
        xs = np.linspace(s_eff / 2.0, L_plot - s_eff / 2.0, n_hoops)
        for x0 in xs:
            add_shear_hoop_at_x(x0)

    fig = go.Figure(data=traces)
    fig.update_layout(
        autosize=True,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        scene_aspectmode="manual",
        scene_aspectratio=dict(x=2.4, y=max(0.7, b_box / max(D, 1.0)), z=1.0),
        scene_camera=dict(
            eye=dict(x=1.8, y=1.2, z=0.6),
            center=dict(x=0, y=0, z=0),
            up=dict(x=0, y=0, z=1),
        ),
        scene=dict(
            xaxis=dict(
                range=[0.0, L_plot],
                visible=False,
                showgrid=False,
                zeroline=False,
                showticklabels=False,
            ),
            yaxis=dict(
                range=[0.0, b_box],
                visible=False,
                showgrid=False,
                zeroline=False,
                showticklabels=False,
            ),
            zaxis=dict(
                range=[float(D), 0.0],
                visible=False,
                showgrid=False,
                zeroline=False,
                showticklabels=False,
            ),
        ),
        margin=dict(l=8, r=8, t=8, b=8),
        showlegend=False,
    )
    
    # Make the 3D background transparent too
    fig.update_scenes(
        bgcolor="rgba(0,0,0,0)",
    )
    
    return fig


# ------------------------------------------------------------
#  STATUS HELPER
# ------------------------------------------------------------
def _safe_ratio(num, den):
    """
    Return num/den, but:
      - if den is 0, None or NaN -> return None (treated as 'Not calculated').
    """
    try:
        if den is None:
            return None
        # protect against NaN
        if isinstance(den, float) and math.isnan(den):
            return None
        if den == 0:
            return None
        return num / den
    except Exception:
        return None


def _status_and_colour(util, cap_exists):
    if not cap_exists or util is None or math.isnan(util):
        return "Not calculated", "#e0e0e0"
    if util < 0.95:
        return "PASS", "#d5f5d5"
    if util <= 1.0:
        return "NEAR LIMIT", "#fff4c2"
    return "FAIL", "#f8d0d0"


# ------------------------------------------------------------
#  MAIN INPUT PAGE
# ------------------------------------------------------------
# Safe option lists for reinforcement inputs
REO_BAR_DIAS = [10, 12, 16, 20, 24, 28, 32, 36, 40]
REO_COUNTS_0_12 = list(range(0, 13))  # 0..12 inclusive
REO_SPACINGS = [75, 100, 125, 150, 175, 200, 225, 250, 275, 300]
REO_LAYOUT_MODE = ["Count", "Spacing"]
AUTO_DESIGN_MODE_CONFIG = {
    "balanced": {
        "label": "Balanced design",
        "target_util_min": 0.80,
        "target_util_max": 0.90,
        "search_strategy": "balanced",
        "max_frontier": 5,
        "material_depth_delta_mm": 25.0,
        "material_reo_complexity_delta": 4.0,
        "practicality_congestion_limit": 20.0,
        "complexity_penalty": 0.9,
        "prefer_shallower_section": False,
        "prefer_lower_reo_congestion": False,
        "allow_high_steel_ratio": False,
        "geometry_penalty": 1.0,
        "width_penalty": 0.45,
        "steel_penalty": 1.0,
        "reo_congestion_penalty": 1.0,
        "depth_priority": "secondary",
        "depth_growth_multiplier": 1.8,
    },
    "shallower_beam": {
        "label": "Shallower beam",
        "target_util_min": 0.85,
        "target_util_max": 0.98,
        "search_strategy": "shallow",
        "max_frontier": 4,
        "material_depth_delta_mm": 25.0,
        "material_reo_complexity_delta": 999.0,
        "practicality_congestion_limit": 28.0,
        "complexity_penalty": 0.4,
        "prefer_shallower_section": True,
        "prefer_lower_reo_congestion": False,
        "allow_high_steel_ratio": True,
        "geometry_penalty": 2.5,
        "width_penalty": 0.55,
        "steel_penalty": 0.8,
        "reo_congestion_penalty": 1.0,
        "depth_priority": "primary",
        "depth_growth_multiplier": 2.8,
    },
    "less_longitudinal_reinforcement": {
        "label": "Less longitudinal reinforcement",
        "target_util_min": 0.75,
        "target_util_max": 0.90,
        "search_strategy": "low_reo",
        "max_frontier": 4,
        "material_depth_delta_mm": 999.0,
        "material_reo_complexity_delta": 4.0,
        "practicality_congestion_limit": 18.0,
        "complexity_penalty": 1.8,
        "prefer_shallower_section": False,
        "prefer_lower_reo_congestion": True,
        "allow_high_steel_ratio": False,
        "geometry_penalty": 0.8,
        "width_penalty": 0.35,
        "steel_penalty": 1.2,
        "reo_congestion_penalty": 2.0,
        "depth_priority": "tertiary",
        "depth_growth_multiplier": 1.0,
    },
    "less_shear_reinforcement": {
        "label": "Less shear reinforcement",
        "target_util_min": 0.78,
        "target_util_max": 0.92,
        "search_strategy": "balanced",
        "max_frontier": 4,
        "material_depth_delta_mm": 25.0,
        "material_reo_complexity_delta": 6.0,
        "practicality_congestion_limit": 20.0,
        "complexity_penalty": 1.0,
        "prefer_shallower_section": False,
        "prefer_lower_reo_congestion": False,
        "allow_high_steel_ratio": False,
        "geometry_penalty": 0.9,
        "width_penalty": 0.35,
        "steel_penalty": 0.95,
        "reo_congestion_penalty": 1.15,
        "depth_priority": "secondary",
        "depth_growth_multiplier": 1.2,
    },
}
DESIGN_OPTIMISATION_GOAL_LABELS = {
    key: str(config["label"])
    for key, config in AUTO_DESIGN_MODE_CONFIG.items()
}
EFFICIENCY_TARGET_UTIL_MIN = 0.80
EFFICIENCY_TARGET_UTIL_MAX = 0.90
TARGET_BAND_EPS = 0.005
CONSERVATIVE_UTIL_THRESHOLD = 0.65
GUIDANCE_INEFFICIENT_UTIL_THRESHOLD = 0.75
GUIDANCE_NEAR_LIMIT_UTIL_THRESHOLD = 0.95
GUIDANCE_SHEAR_DEMAND_ABS_TOL_KN = 1.0
GUIDANCE_TORSION_DEMAND_ABS_TOL_KNM = 0.5
GUIDANCE_SHEAR_UTIL_NEGLIGIBLE = 0.08
GUIDANCE_SHALLOW_GEOMETRY_SCORE_TIE_EPS = 24.0
GUIDANCE_COMPOUND_VS_PURE_GEOMETRY_SCORE_MARGIN = 28.0
CANONICAL_NO_SHEAR_SLIG_MM = 200.0
GUIDANCE_TARGET_UTIL_MIN = 0.80
GUIDANCE_TARGET_UTIL_MAX = 0.95
GUIDANCE_UNDERSIZED_DONE_BLOCK_UTIL = 0.80
GUIDANCE_STRONGLY_UNDERUTILISED_UTIL = 0.60
TARGET_BAND_ACTIONABLE_GEO_DELTA_MM = 0.5
TARGET_BAND_ACTIONABLE_AST_DELTA_MM2 = 5.0
IN_BAND_MIN_WIDTH_ALONE_MM = 50.0
IN_BAND_MIN_DEPTH_DELTA_MM = 25.0
IN_BAND_MIN_AST_DELTA_MM2 = 120.0
IN_BAND_COMPOUND_MIN_WIDTH_MM = 38.0
IN_BAND_COMPOUND_MIN_AST_MM2 = 70.0
IN_BAND_COMPOUND_MIN_DEPTH_MM = 18.0
IN_BAND_GOAL_ALIGN_MIN_SHALLOW = 14.0
IN_BAND_GOAL_ALIGN_MIN_BALANCED = 10.0
IN_BAND_SHALLOW_DEPTH_UP_MIN_GAIN = 22.0
AUTO_DESIGN_MAX_STEPS = 6
AUTO_DESIGN_MAX_STAGE_CANDIDATES = 20
AUTO_DESIGN_MAX_KEPT_RESULTS = 5
AUTO_DESIGN_MAX_TOTAL_UNIQUE_EVALS = 100
AUTO_DESIGN_MAX_HOPS_TO_PASS = 4
AUTO_DESIGN_MAX_REFINEMENT_HOPS = 3
AUTO_DESIGN_MAX_HOPS = AUTO_DESIGN_MAX_HOPS_TO_PASS
AUTO_DESIGN_MAX_TIGHTENING_ITERS = 8
AUTO_DESIGN_MAX_LOCAL_CANDIDATES_PER_ITER = 12
AUTO_DESIGN_MAX_FIRST_HOP_RAW_CANDIDATES = 32
AUTO_DESIGN_MAX_LATER_HOP_RAW_CANDIDATES = 16

K_D_OPTIONS = [
    "None (no ducts in web)",
    "Prestressing ducts present (apply k_d)",
]

K_V_METHOD_OPTIONS = [
    "General εx-based (Cl. 8.2.4.2)",
    "Simplified non-prestressed (Cl. 8.2.4.3)",
]


def _render_ducts_prestress_voids_inputs(sync_callbacks):
    """Render Ducts / Prestress voids section widgets (UI-only, no logic changes)."""
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

    # k_d dropdown
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


def _render_serviceability_shrinkage_inputs(sync_callbacks):
    """Render Loading conditions section widgets (UI-only, no logic changes)."""
    st.subheader("Loading conditions")
    design_controls = is_design_governing()
    
    # Support condition (k2) dropdown — resolved label matches deflection calcs / design auto-derive
    support_bundle = _resolve_inputs_support_and_deflection_defaults()
    support_current = support_bundle["support_current"]
    support_options = support_bundle["support_options"]
    w_support = get_widget_key_for_shared("defl_support_type", prefix="inputs_") or "inputs_defl_support_type"
    if design_controls:
        st.info(
            "🔒 Support condition (k₂) is **auto-derived** from the Design / SFD model "
            "(matches deflection calculations)."
        )
    select_row(
        "Support condition (k₂)",
        w_support,
        support_options,
        support_current,
        sync_callbacks,
        help_text="Support condition determines the deflection coefficient k₂ used in AS 3600 deflection calculations.",
        disabled=design_controls,
    )
    
    # Deflection limit L/Δ
    w_defl_limit = get_widget_key_for_shared("defl_limit_ratio", prefix="inputs_") or "inputs_defl_limit_ratio"
    defl_limit_val = support_bundle["defl_limit_val"]
    defl_limit_options_by_ratio = support_bundle["defl_limit_options_by_ratio"]
    select_row(
        "Deflection limit L/Δ",
        w_defl_limit,
        defl_limit_options_by_ratio,
        defl_limit_val,
        sync_callbacks,
        help_text=DEFLECTION_LIMIT_HELP_TEXT,
    )
    _caption_inputs_deflection_limit_ratio()


def _render_time_dependent_inputs(sync_callbacks):
    """Render time-dependent inputs (creep/shrinkage) widgets."""
    st.subheader("Time-dependent inputs")

    # Shrinkage time (days)
    t_shrink_val = float(st.session_state.get("inputs_t_shrink", get_param("t_shrink", 365.0)))
    number_row(
        "Shrinkage time t (days)",
        "inputs_t_shrink",
        t_shrink_val,
        sync_callbacks,
        help_text="Time since commencement of drying (days).",
    )

    # Creep time (days)
    t_creep_val = float(st.session_state.get("inputs_t_creep", get_param("t_creep", 365.0)))
    number_row(
        "Creep time t (days)",
        "inputs_t_creep",
        t_creep_val,
        sync_callbacks,
        help_text="Time after loading (days).",
    )

    # Age at loading (days)
    tau_val = float(st.session_state.get("inputs_age_at_loading", get_param("age_at_loading", 28.0)))
    number_row(
        "Age at loading τ (days)",
        "inputs_age_at_loading",
        tau_val,
        sync_callbacks,
        help_text="Age of concrete at loading (days).",
    )


def _render_inputs_materials_subsection(sync_callbacks: dict, *, show_heading: bool = True) -> None:
    """Steel/concrete material inputs (widget keys unchanged)."""
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


def _render_materials_and_sectionA_2d(sync_callbacks):
    """Support conditions, shear section params, then 3D diagram (detailed mode). Materials render under main diagram."""
    mat_col, sec2d_col = st.columns([1.15, 1.85], gap="large")
    
    with mat_col:
        st.subheader("Support conditions")
        
        # Member / faces exposed dropdown
        faces_options = [
            "Slab – one face exposed",
            "Slab – two faces exposed",
            "Beam – three faces exposed",
            "Column – four faces exposed",
        ]
        faces_current = st.session_state.get("member_faces_exposed", "Beam – three faces exposed")
        if faces_current not in faces_options:
            faces_current = "Beam – three faces exposed"
        
        w_faces = get_widget_key_for_shared("member_faces_exposed", prefix="inputs_") or "inputs_member_faces_exposed"
        select_row(
            "Member / faces exposed",
            w_faces,
            faces_options,
            faces_current,
            sync_callbacks,
            help_text="Number of faces exposed to drying environment (affects shrinkage calculations).",
        )
        
        # Shrinkage environment dropdown
        env_options = [
            "Arid environment",
            "Interior environment",
            "Temperate inland environment",
            "Tropical / near-coastal / coastal environment",
        ]
        env_current = st.session_state.get("shrinkage_env", "Temperate inland environment")
        if env_current not in env_options:
            env_current = "Temperate inland environment"
        
        w_env = get_widget_key_for_shared("shrinkage_env", prefix="inputs_") or "inputs_shrinkage_env"
        select_row(
            "Shrinkage environment (Table 3.1.7.2)",
            w_env,
            env_options,
            env_current,
            sync_callbacks,
            help_text="Shrinkage environment classification per AS 3600 Table 3.1.7.2.",
        )
        
        # Creep environment dropdown
        creep_env_options = [
            "Arid environment",
            "Interior environment",
            "Temperate inland environment",
            "Tropical / near-coastal / coastal environment",
        ]
        creep_env_current = st.session_state.get("env_option", "Temperate inland environment")
        if creep_env_current not in creep_env_options:
            creep_env_current = "Temperate inland environment"
        
        w_creep_env = get_widget_key_for_shared("env_option", prefix="inputs_") or "inputs_env_option"
        select_row(
            "Creep environment (Tables 3.1.8.2 & 3.1.8.3)",
            w_creep_env,
            creep_env_options,
            creep_env_current,
            sync_callbacks,
            help_text="Creep environment classification per AS 3600 Tables 3.1.8.2 & 3.1.8.3.",
        )
        
        # Support condition (k2) dropdown
        design_controls = is_design_governing()
        support_bundle = _resolve_inputs_support_and_deflection_defaults()
        support_current = support_bundle["support_current"]
        support_options = support_bundle["support_options"]
        w_support = get_widget_key_for_shared("defl_support_type", prefix="inputs_") or "inputs_defl_support_type"
        if design_controls:
            st.info(
                "🔒 Support condition (k₂) is **auto-derived** from the Design / SFD model "
                "(matches deflection calculations)."
            )
        select_row(
            "Support condition (k₂)",
            w_support,
            support_options,
            support_current,
            sync_callbacks,
            help_text="Support condition determines the deflection coefficient k₂ used in AS 3600 deflection calculations.",
            disabled=design_controls,
        )
        
        # Deflection limit L/Δ
        w_defl_limit = get_widget_key_for_shared("defl_limit_ratio", prefix="inputs_") or "inputs_defl_limit_ratio"
        defl_limit_val = support_bundle["defl_limit_val"]
        defl_limit_options_by_ratio = support_bundle["defl_limit_options_by_ratio"]
        select_row(
            "Deflection limit L/Δ",
            w_defl_limit,
            defl_limit_options_by_ratio,
            defl_limit_val,
            sync_callbacks,
            help_text=DEFLECTION_LIMIT_HELP_TEXT,
        )
        _caption_inputs_deflection_limit_ratio()

        st.markdown("")
        st.subheader("Shear section parameters")

        w_d_g = get_widget_key_for_shared("d_g", prefix="inputs_") or "inputs_d_g"
        w_k_v_method = get_widget_key_for_shared("k_v_method", prefix="inputs_") or "inputs_k_v_method"

        d_g_val = float(st.session_state.get("d_g", 20.0))
        k_v_val = st.session_state.get("k_v_method", "General εx-based (Cl. 8.2.4.2)")

        number_row(
            "Maximum aggregate size d_g (mm)",
            w_d_g,
            d_g_val,
            sync_callbacks,
            help_text="Maximum aggregate size used in shear provisions (mm).",
        )

        select_row(
            "k_v method",
            w_k_v_method,
            K_V_METHOD_OPTIONS,
            k_v_val,
            sync_callbacks,
            help_text="Select the k_v method for shear capacity (AS 3600 8.2.4.2 vs 8.2.4.3).",
        )
    
    with sec2d_col:
        _render_3d_diagram_block()


def _render_section_2d_diagram_block(*, compact: bool = False):
    """Render the 2D section diagram only (UI order/presentation helper)."""
    diagram_started_at = time.perf_counter()
    sec_shape = st.session_state.get("sec_shape", "RECT")
    # region agent log
    _agent_debug_log(
        "Entered 2D diagram render",
        {
            "compact": bool(compact),
            "sec_shape": str(sec_shape or ""),
        },
        location="inputs_page.py:_render_section_2d_diagram_block:start",
        hypothesis_id="H20",
    )
    # endregion

    if sec_shape == "RECT":
        _required = ["b", "D"]
    elif sec_shape == "T":
        _required = ["bf", "tf", "bw", "D"]
    else:  # "I"
        _required = ["bf", "tf", "tw", "D"]

    _missing = [k for k in _required if st.session_state.get(k) in (None, "", 0)]
    if _missing:
        st.info("2D section diagram not available right now (inputs are still saved).")
        return

    fig_sec = None
    try:
        fig_sec = make_summary_cross_section_figure()
        if fig_sec is None:
            raise ValueError("2D section diagram function returned None (fig is None)")
    except Exception as e:
        st.warning(f"2D section diagram failed: {e}")
        with st.expander("Diagram debug details"):
            st.exception(e)
        return

    if fig_sec is not None:
        try:
            # ~12% shorter than legacy 540/620 to limit vertical overflow
            fig_sec.update_layout(
                autosize=True,
                height=(475 if compact else 545),
                margin=dict(l=4, r=4, t=4, b=4),
            )
        except Exception:
            pass
        st.markdown('<div class="inputs-page-main-diagram-wrap">', unsafe_allow_html=True)
        st.plotly_chart(
            fig_sec,
            use_container_width=True,
            config={"displayModeBar": False},
        )
        st.markdown("</div>", unsafe_allow_html=True)
        # region agent log
        _agent_debug_log(
            "Completed 2D diagram render",
            {
                "compact": bool(compact),
                "elapsed_ms": round((time.perf_counter() - diagram_started_at) * 1000.0, 1),
            },
            location="inputs_page.py:_render_section_2d_diagram_block:end",
            hypothesis_id="H20",
        )
        # endregion


def _render_3d_diagram_block(*, compact: bool = False):
    """Render the 3D diagram only (UI order/presentation helper)."""
    diagram_started_at = time.perf_counter()
    # region agent log
    _agent_debug_log(
        "Entered 3D diagram render",
        {
            "compact": bool(compact),
        },
        location="inputs_page.py:_render_3d_diagram_block:start",
        hypothesis_id="H21",
    )
    # endregion
    layout = compute_section_layout()
    shape_name = layout.get("shape_name", "Rectangle (b × D)")
    dims = layout.get("dims", {})
    reo = dict(layout.get("reo", {}))
    shared_state = _shared_state_snapshot()
    reo["lig_d"] = float(shared_state.get("lig_d", reo.get("lig_d", 0.0)) or 0.0)
    reo["lig_legs"] = int(shared_state.get("lig_legs", reo.get("lig_legs", 0)) or 0)
    reo["s_lig"] = float(shared_state.get("s_lig", reo.get("s_lig", 200.0)) or 200.0)
    reo_layout = layout.get("reo_layout", {})

    st.markdown(
        """
        <style>
        div[data-testid="stPlotlyChart"] {
          border: 1px solid rgba(0,0,0,0.12);
          border-radius: 8px;
          background: #fff;
          overflow: hidden;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    if shape_name.startswith(("T-Section", "I-Section")):
        if not isinstance(reo_layout, dict):
            reo_layout = {"top": [], "bottom": []}

        fig3d = make_section_3d_figure(
            shape_name=shape_name,
            dims=dims,
            reo_layout=reo_layout,
            reo_inputs=reo,
            show_shear=True,
            L_vis=900.0,
        )
        BASE_H = 360 if compact else 420
        fig3d.update_layout(
            height=int(int(BASE_H * 7 / 5) * 0.88),
            margin=dict(l=4, r=4, t=4, b=4),
        )
        st.markdown('<div class="inputs-page-main-diagram-wrap">', unsafe_allow_html=True)
        st.plotly_chart(
            fig3d,
            use_container_width=True,
            config={"displayModeBar": False}
        )
        st.markdown("</div>", unsafe_allow_html=True)
        # region agent log
        _agent_debug_log(
            "Completed 3D diagram render",
            {
                "compact": bool(compact),
                "shape_name": str(shape_name or ""),
                "elapsed_ms": round((time.perf_counter() - diagram_started_at) * 1000.0, 1),
            },
            location="inputs_page.py:_render_3d_diagram_block:end:t_i",
            hypothesis_id="H21",
        )
        # endregion
    else:
        fig3d = make_beam_3d_figure()
        BASE_H = 410 if compact else 480
        _h3d = int(int(BASE_H * 7 / 5) * 0.88)
        fig3d.update_layout(
            height=_h3d,
            margin=dict(l=4, r=4, t=4, b=4),
        )
        st.markdown('<div class="inputs-page-main-diagram-wrap">', unsafe_allow_html=True)
        st.plotly_chart(
            fig3d,
            width="stretch",
            height=_h3d,
            config={"displayModeBar": True}
        )
        st.markdown("</div>", unsafe_allow_html=True)
        # region agent log
        _agent_debug_log(
            "Completed 3D diagram render",
            {
                "compact": bool(compact),
                "shape_name": str(shape_name or ""),
                "elapsed_ms": round((time.perf_counter() - diagram_started_at) * 1000.0, 1),
            },
            location="inputs_page.py:_render_3d_diagram_block:end:rect",
            hypothesis_id="H21",
        )
        # endregion


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


def _geometry_lock_enabled(source: dict | None = None) -> bool:
    resolved = source if isinstance(source, dict) else st.session_state
    return bool((resolved or {}).get("optimisation_lock_geometry", False))


def _design_optimisation_goal(state: dict | None = None) -> str:
    source = state if isinstance(state, dict) else st.session_state
    goal = str((source or {}).get("design_optimisation_goal", "balanced") or "balanced")
    if goal not in DESIGN_OPTIMISATION_GOAL_LABELS:
        return "balanced"
    return goal


def _design_optimisation_goal_label(state: dict | None = None) -> str:
    goal = _design_optimisation_goal(state)
    return DESIGN_OPTIMISATION_GOAL_LABELS[goal]


def _design_mode_config(goal: str | None = None) -> dict:
    resolved_goal = goal or _design_optimisation_goal()
    return dict(AUTO_DESIGN_MODE_CONFIG.get(resolved_goal, AUTO_DESIGN_MODE_CONFIG["balanced"]))


def _mode_target_midpoint(mode_config: dict) -> float:
    return (float(mode_config["target_util_min"]) + float(mode_config["target_util_max"])) / 2.0


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


def _bottom_arrangement_to_shared_updates(arrangement: dict) -> dict:
    count_1 = int(arrangement.get("bot1_count", 0) or 0)
    count_2 = int(arrangement.get("bot2_count", 0) or 0)
    dia_1 = int(arrangement.get("db_bot_1", 0) or 0)
    dia_2 = int(arrangement.get("db_bot_2", dia_1) or dia_1)
    row_count = 2 if count_2 > 0 else 1
    return {
        "bot1_layout_mode": "Count",
        "bot1_count": count_1,
        "db_bot_1": dia_1,
        "bot2_layout_mode": "Count",
        "bot2_count": count_2,
        "db_bot_2": dia_2,
        "bot_row_count": row_count,
        "bot_row_1_mode": "Count",
        "bot_row_1_bars": count_1,
        "bot_row_1_spacing": 0.0,
        "bot_row_1_dia": dia_1,
        "bot_row_2_mode": "Count",
        "bot_row_2_bars": count_2,
        "bot_row_2_spacing": 0.0,
        "bot_row_2_dia": dia_2,
    }


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


def _render_design_optimisation_control(sync_callbacks: dict) -> None:
    with info_i_button(
        help_text=(
            "Choose the preferred optimisation goal for design guidance and "
            "auto-design recommendations."
        )
    ):
        _render_design_optimisation_inputs(sync_callbacks)
    _sync_auto_design_mode_tracking(_shared_state_snapshot())


def _shared_state_snapshot() -> dict:
    return {
        key: st.session_state.get(key, default)
        for key, default in SHARED_DEFAULTS.items()
    }


def _auto_design_governing_fingerprint(state: dict | None = None) -> tuple:
    source = state or _shared_state_snapshot()
    actions = _resolve_design_actions_from_state(source)
    governing_keys = (
        "design_optimisation_goal",
        "optimisation_lock_geometry",
        "sec_shape",
        "b",
        "bw",
        "tw",
        "D",
        "fc",
        "fsy",
        "Ec",
        "Es",
        "phi_bend",
        "phi_shear",
        "cover_top",
        "cover_bot",
        "cover_side",
        "rowgap_top",
        "rowgap_bot",
        "Ast_top",
        "Tu_star",
        "P_star",
        "lig_d",
        "lig_legs",
        "s_lig",
        "bot_row_count",
        "bot1_layout_mode",
        "bot1_count",
        "db_bot_1",
        "bot2_layout_mode",
        "bot2_count",
        "db_bot_2",
        "bot_row_1_mode",
        "bot_row_1_bars",
        "bot_row_1_spacing",
        "bot_row_1_dia",
        "bot_row_2_mode",
        "bot_row_2_bars",
        "bot_row_2_spacing",
        "bot_row_2_dia",
    )
    fingerprint = [(key, str(source.get(key))) for key in governing_keys]
    fingerprint.extend([
        ("resolved_Mu", str(actions.get("Mu"))),
        ("resolved_Vu", str(actions.get("Vu"))),
        ("resolved_Nu", str(actions.get("Nu"))),
        ("resolved_SLS_M", str(actions.get("SLS_M"))),
        ("resolved_SLS_V", str(actions.get("SLS_V"))),
        ("resolved_source", str(actions.get("source"))),
    ])
    return tuple(fingerprint)


def _sync_auto_design_invalidation(state: dict | None = None) -> None:
    current_fingerprint = _auto_design_governing_fingerprint(state)
    previous_fingerprint = st.session_state.get("_auto_design_last_fingerprint")
    if previous_fingerprint is None:
        st.session_state["_auto_design_last_fingerprint"] = current_fingerprint
        return
    if current_fingerprint != previous_fingerprint:
        st.session_state["_auto_design_invalidated"] = True


def _should_run_auto_design() -> bool:
    should_run = bool(
        st.session_state.get("_auto_design_requested", False)
        or st.session_state.get("_force_auto_redesign", False)
        or st.session_state.get("_auto_design_invalidated", False)
    )
    return should_run


def _guidance_state_snapshot(state: dict | None = None) -> dict:
    snapshot = dict(st.session_state)
    for key, default in SHARED_DEFAULTS.items():
        snapshot.setdefault(key, default)
    if isinstance(state, dict):
        snapshot.update(state)
    return snapshot


def _bottom_reo_state_label(state: dict) -> str:
    mode_1 = str(state.get("bot1_layout_mode", "Count") or "Count")
    mode_2 = str(state.get("bot2_layout_mode", "Count") or "Count")
    if mode_1 == "Count" and mode_2 == "Count":
        count_1 = int(state.get("bot1_count", 0) or 0)
        count_2 = int(state.get("bot2_count", 0) or 0)
        dia = int(state.get("db_bot_1", state.get("db_bot", 0)) or 0)
        if count_1 > 0:
            return _practical_bottom_reo_label(count_1, count_2, dia)
    spacing_1 = float(state.get("bot1_spacing", 0.0) or 0.0)
    dia_1 = int(state.get("db_bot_1", 0) or 0)
    return f"N{dia_1} @ {int(spacing_1)}"


def _shear_state_label(state: dict) -> str:
    legs = int(state.get("lig_legs", 0) or 0)
    if legs <= 0:
        return "No ligs"
    return (
        f"{legs}-leg "
        f"N{int(state.get('lig_d', 0) or 0)} @ {int(float(state.get('s_lig', 0.0) or 0.0))}"
    )


def _top_reo_state_label(state: dict) -> str:
    mode_1 = str(state.get("top1_layout_mode", "Count") or "Count")
    mode_2 = str(state.get("top2_layout_mode", "Count") or "Count")
    count_1 = int(state.get("top1_count", 0) or 0)
    count_2 = int(state.get("top2_count", 0) or 0)
    if mode_1 == "Count" and mode_2 == "Count":
        dia = int(state.get("db_top_1", state.get("db_top", 0)) or 0)
        if count_1 > 0 or count_2 > 0:
            return _practical_bottom_reo_label(count_1, count_2, dia)
        return "None"
    spacing_1 = float(state.get("top1_spacing", 0.0) or 0.0)
    dia_1 = int(state.get("db_top_1", 0) or 0)
    return f"N{dia_1} @ {int(spacing_1)}"


def _guidance_shear_links_banner_fragment(state: dict) -> str | None:
    legs = int(state.get("lig_legs", 0) or 0)
    if legs <= 0:
        return None
    return f"N{int(state.get('lig_d', 0) or 0)}, {legs}-leg @{int(float(state.get('s_lig', 0.0) or 0.0))}"


def _design_guide_apply_snapshot(state: dict) -> dict:
    wk, _wl, wv = _resolve_geometry_width_context(state)
    return {
        "width_key": wk,
        "b": float(wv or 0.0),
        "D": float(_float_from_state(state, "D", 0.0)),
        "bottom_label": _bottom_reo_state_label(state),
        "top_label": _top_reo_state_label(state),
        "shear_fragment": _guidance_shear_links_banner_fragment(state),
    }


def _guidance_apply_change_lines(before: dict, after: dict) -> list[str]:
    lines: list[str] = []
    _, _, bw = _resolve_geometry_width_context(before)
    _, _, aw = _resolve_geometry_width_context(after)
    try:
        if abs(float(aw) - float(bw)) > 1e-6:
            lines.append(f"Width: {int(round(float(bw)))} → {int(round(float(aw)))} mm")
    except (TypeError, ValueError):
        pass
    try:
        b_d = float(_float_from_state(before, "D", 0.0))
        a_d = float(_float_from_state(after, "D", 0.0))
        if abs(a_d - b_d) > 1e-6:
            lines.append(f"Depth: {int(round(b_d))} → {int(round(a_d))} mm")
    except (TypeError, ValueError):
        pass
    bl = _bottom_reo_state_label(before)
    al = _bottom_reo_state_label(after)
    bot_phrase, top_phrase = main_longitudinal_reo_change_line_prefixes(after)
    if bl != al:
        lines.append(f"{bot_phrase}: {bl} → {al}")
    tl_b = _top_reo_state_label(before)
    tl_a = _top_reo_state_label(after)
    if tl_b != tl_a:
        lines.append(f"{top_phrase}: {tl_b} → {tl_a}")
    bf = _guidance_shear_links_banner_fragment(before)
    af = _guidance_shear_links_banner_fragment(after)
    if bf != af:
        if af is None:
            lines.append(f"Shear links: {bf} → removed")
        elif bf is None:
            lines.append(f"Shear links: none → {af}")
        else:
            lines.append(f"Shear links: {bf} → {af}")
    return lines


def _guidance_change_lines_for_updates(before: dict, updates: dict | None) -> list[str]:
    if not updates:
        return []
    after = dict(before)
    after.update(updates)
    return _guidance_apply_change_lines(before, after)


def _build_candidate_change_lines(candidate: dict | None, current_state: dict) -> list[str]:
    if not candidate or not isinstance(current_state, dict):
        return []
    cand_state = dict(candidate.get("state") or {})
    if not cand_state:
        return []
    return _guidance_apply_change_lines(current_state, cand_state)


def _sync_design_guide_geometry_reference(state: dict) -> None:
    bid = str(st.session_state.get("active_beam_id") or "")
    prev = str(st.session_state.get(DESIGN_GUIDE_REF_BEAM_ID_KEY) or "")
    d_now = float(_float_from_state(state, "D", float(SHARED_DEFAULTS.get("D", 600.0))))
    _, _, w_now = _resolve_geometry_width_context(state)
    w_now = float(w_now or 0.0)
    if bid and bid != prev:
        st.session_state[DESIGN_GUIDE_REF_BEAM_ID_KEY] = bid
        st.session_state[DESIGN_GUIDE_REFERENCE_D_KEY] = d_now
        st.session_state[DESIGN_GUIDE_REFERENCE_B_KEY] = w_now
    if st.session_state.get(DESIGN_GUIDE_SESSION_ANCHOR_D_KEY) is None:
        st.session_state[DESIGN_GUIDE_SESSION_ANCHOR_D_KEY] = d_now


def _design_guide_effective_reference_depth(state: dict) -> float:
    ref = st.session_state.get(DESIGN_GUIDE_REFERENCE_D_KEY)
    if ref is None:
        ref = float(SHARED_DEFAULTS.get("D", 600.0))
    else:
        ref = float(ref)
    anchor = st.session_state.get(DESIGN_GUIDE_SESSION_ANCHOR_D_KEY)
    if anchor is not None:
        ref = min(ref, float(anchor))
    tmpl = float(SHARED_DEFAULTS.get("D", 600.0))
    return min(ref, tmpl)


def _record_design_guide_auto_geometry_applied(prior_state: dict, updates: dict) -> None:
    geom_keys = {"D", "b", "bw", "bf", "tw", "tf"}
    if not geom_keys.intersection(set(updates.keys())):
        return
    _, _, wb = _resolve_geometry_width_context(prior_state)
    after = dict(prior_state)
    after.update(updates)
    _, _, wa = _resolve_geometry_width_context(after)
    st.session_state[DESIGN_GUIDE_LAST_AUTO_GEOM_KEY] = {
        "D": float(_float_from_state(after, "D", 0.0)),
        "b": float(wa or 0.0),
    }


def _guidance_card_why_body(item: dict) -> str:
    w = item.get("guidance_why")
    if isinstance(w, str) and w.strip():
        t = w.strip()
        if t.lower().startswith("why:"):
            return t[4:].strip() or t
        return t
    r = str(item.get("reasoning") or "").strip()
    if not r:
        return ""
    if r.lower().startswith("why:"):
        return r[4:].strip() or r
    return r


def _guidance_item_payload_fingerprint(item: dict, state: dict) -> tuple:
    at = str(item.get("action_type") or "")
    pl = dict(item.get("action_payload") or {})

    def _norm_val(v: object) -> object:
        if isinstance(v, float):
            return round(v, 4)
        if isinstance(v, (int, str, bool)) or v is None:
            return v
        return str(v)

    if at == "apply_compound_guidance":
        u = dict(pl.get("updates") or {})
        return ("apply_compound_guidance", tuple(sorted((k, _norm_val(u[k])) for k in sorted(u))))
    try:
        u = _guidance_action_updates(at, pl, state=state) or {}
    except Exception:
        u = {}
    return (at, tuple(sorted((k, _norm_val(u[k])) for k in sorted(u))))


def _family_tag_from_compound_updates(u: dict, state: dict) -> str:
    subs = _compound_subfamilies_from_updates(u)
    sf = set(subs)
    if sf >= {"geometry", "bottom_reo"}:
        d0, d1, w0, w1 = _compound_geometry_deltas(state, u)
        if d1 > d0 + 0.5 and w1 > w0 + 0.5:
            return "compound_depth_width_bottom"
        if d1 > d0 + 0.5:
            return "compound_depth_bottom"
        if w1 > w0 + 0.5:
            return "compound_width_bottom"
        return "compound_geometry_bottom"
    if sf >= {"shear", "bottom_reo"}:
        return "shear_bottom_compound"
    if sf >= {"geometry", "shear"}:
        return "compound_geometry_shear"
    return "compound_other"


def _guidance_item_family_tag(item: dict, state: dict) -> str:
    at = str(item.get("action_type") or "")
    pl = dict(item.get("action_payload") or {})
    if at == "apply_compound_guidance":
        u = dict(pl.get("updates") or {})
        return _family_tag_from_compound_updates(u, state)
    if at == "apply_bottom_recommendation":
        return "pure_bottom_reo"
    if at == "increase_width":
        return "pure_geometry_width"
    if at == "increase_depth":
        return "pure_geometry_depth"
    if at in ("apply_geometry_recommendation", "tighten_geometry"):
        return "geometry_recommendation"
    if at in ("apply_shear_recommendation", "increase_link_spacing", "reduce_number_of_legs", "reduce_link_spacing"):
        return "shear_adjust"
    if at == "apply_mode_recommendation":
        return "mode_guidance"
    if at == "reduce_bottom_reinforcement":
        return "bottom_reduction"
    return at or "unknown"


def _dedupe_guidance_items_for_display(items: list[dict], state: dict) -> tuple[list[dict], dict]:
    def _effective_updates(item: dict) -> dict:
        at = str(item.get("action_type") or "")
        pl = dict(item.get("action_payload") or {})
        if at == "apply_compound_guidance":
            return dict(pl.get("updates") or {})
        try:
            return dict(_guidance_action_updates(at, pl, state=state) or {})
        except Exception:
            return {}

    def _materially_distinct(a: dict, b: dict) -> bool:
        if str(a.get("check_key") or "") != str(b.get("check_key") or ""):
            return True
        fa = _guidance_item_family_tag(a, state)
        fb = _guidance_item_family_tag(b, state)
        if fa == fb:
            return False
        ua = _effective_updates(a)
        ub = _effective_updates(b)
        if not ua and not ub:
            return False
        ka = set(ua.keys())
        kb = set(ub.keys())
        if not ka and not kb:
            return False
        if ka == kb:
            # Same changed fields is usually a wording variant; keep one.
            return False
        overlap = len(ka & kb)
        union = max(len(ka | kb), 1)
        overlap_ratio = float(overlap) / float(union)
        if overlap_ratio >= 0.75:
            return False
        return True

    before = len(items)
    dropped: list[dict] = []
    out: list[dict] = []
    seen: set[tuple] = set()
    for it in items:
        if not isinstance(it, dict):
            continue
        fp = _guidance_item_payload_fingerprint(it, state)
        if fp in seen:
            dropped.append(
                {
                    "title_main": it.get("title_main"),
                    "action_type": it.get("action_type"),
                    "dropped_reason": "duplicate_action_payload",
                    "family_tag": _guidance_item_family_tag(it, state),
                },
            )
            continue
        seen.add(fp)
        if out and (not _materially_distinct(out[0], it)):
            dropped.append(
                {
                    "title_main": it.get("title_main"),
                    "action_type": it.get("action_type"),
                    "dropped_reason": "near_duplicate_primary_overlap",
                    "family_tag": _guidance_item_family_tag(it, state),
                },
            )
            continue
        out.append(it)
    if len(out) > 2:
        for it in out[2:]:
            dropped.append(
                {
                    "title_main": it.get("title_main"),
                    "action_type": it.get("action_type"),
                    "dropped_reason": "only_primary_and_one_distinct_alternative_allowed",
                    "family_tag": _guidance_item_family_tag(it, state),
                },
            )
        out = out[:2]
    return out, {
        "guidance_items_before_dedupe_count": before,
        "guidance_items_after_dedupe_count": len(out),
        "dropped_guidance_items_summary": dropped,
        "primary_card_family_tag": _guidance_item_family_tag(out[0], state) if out else None,
        "secondary_card_family_tag": _guidance_item_family_tag(out[1], state) if len(out) > 1 else None,
        "secondary_card_materially_distinct": bool(len(out) > 1),
    }


def _design_guide_candidate_family(item: dict | None) -> str:
    if not isinstance(item, dict):
        return "none"
    at = str(item.get("action_type") or "")
    if at == "apply_compound_guidance":
        return "compound"
    if at in ("apply_geometry_recommendation", "increase_depth", "increase_width", "tighten_geometry"):
        return "geometry"
    if at in ("apply_bottom_recommendation", "reduce_bottom_reinforcement", "reduce_bar_spacing"):
        return "bottom_reo"
    if at in ("apply_shear_recommendation", "increase_link_spacing", "reduce_number_of_legs", "reduce_link_spacing"):
        return "shear"
    if at == "apply_mode_recommendation":
        return "mode_guidance"
    ck = str(item.get("check_key") or "")
    return ck if ck else "general"


def _proposed_change_lines_for_guidance_item(item: dict, state: dict) -> list[str]:
    cached = item.get("guidance_change_lines")
    if isinstance(cached, list) and cached:
        return [str(x).strip() for x in cached if str(x).strip()]
    action_type = item.get("action_type")
    if not action_type:
        return []
    try:
        updates = _guidance_action_updates(
            str(action_type),
            dict(item.get("action_payload") or {}),
            state=state,
        )
    except Exception:
        updates = None
    lines = _guidance_change_lines_for_updates(state, updates or {})
    if lines:
        return lines
    if updates:
        return ["Apply this recommendation to update the model."]
    return ["Review the recommendation and apply if appropriate."]


def _guidance_card_proposed_change_html(item: dict, state: dict) -> str:
    lines = _proposed_change_lines_for_guidance_item(item, state)
    if not lines:
        return ""
    inner = "<br>".join(html.escape(x) for x in lines)
    return (
        f"<div class='fast-guidance-proposed'>"
        f"<strong>Proposed change</strong><br>{inner}"
        f"</div>"
    )


def _guidance_compact_change_text(change_lines: list[str]) -> str:
    lines = [str(x).strip() for x in (change_lines or []) if str(x).strip()]
    if not lines:
        return "No direct design changes identified."
    return " | ".join(lines[:3])


def _guidance_item_payload(item: dict | None) -> dict:
    if not isinstance(item, dict):
        return {}
    payload = item.get("action_payload")
    return dict(payload) if isinstance(payload, dict) else {}


def _guidance_item_is_resolved_one_click(item: dict | None) -> bool:
    if not isinstance(item, dict):
        return False
    payload = _guidance_item_payload(item)
    return bool(
        str(item.get("action_type") or "") == "apply_resolved_candidate"
        and payload.get("resolved_candidate_updates")
        and payload.get("resolved_candidate_reaches_target_band") is not None
    )


def _guidance_item_expected_util(item: dict | None):
    payload = _guidance_item_payload(item)
    value = payload.get("expected_governing_util")
    if value is None:
        value = payload.get("resolved_candidate_post_util")
    try:
        return float(value) if value is not None else None
    except Exception:
        return None


def _guidance_expected_util_text(value) -> str:
    try:
        if value is None:
            return "Expected util: -"
        return f"Expected util: {float(value):.2f}"
    except Exception:
        return "Expected util: -"


def _guidance_single_sentence(text: str) -> str:
    raw = " ".join(str(text or "").strip().split())
    if not raw:
        return ""
    for marker in (". ", "! ", "? "):
        if marker in raw:
            return raw.split(marker, 1)[0].strip() + marker.strip()
    if raw.endswith((".", "!", "?")):
        return raw
    return raw + "."


def _guidance_compact_why_text(item: dict) -> str:
    payload = dict(item.get("action_payload") or {})
    why_raw = str(payload.get("guidance_why_text_compact") or _guidance_card_why_body(item) or "").strip()
    if why_raw.lower().startswith("why:"):
        why_raw = why_raw[4:].strip()
    why_one = _guidance_single_sentence(why_raw)
    if not why_one:
        return "Why: This update targets the governing check and improves utilisation."
    return f"Why: {why_one}"


def _guidance_compact_alternatives_text(item: dict) -> str:
    payload = dict(item.get("action_payload") or {})
    alt_raw = str(payload.get("guidance_alternatives_text_compact") or "").strip()
    if not alt_raw:
        sec = str(item.get("secondary_action") or "").strip()
        if sec and sec.lower() not in {"none", "n/a", "no secondary action required."}:
            alt_raw = sec
    if not alt_raw:
        return ""
    if alt_raw.lower().startswith("other options:"):
        return alt_raw
    return f"Other options: {alt_raw}"


def _guidance_primary_compact_lines_html(item: dict, state: dict) -> str:
    payload = _guidance_item_payload(item)
    payload_change_lines = payload.get("guidance_change_lines")
    if isinstance(payload_change_lines, list) and payload_change_lines:
        change_lines = [str(x).strip() for x in payload_change_lines if str(x).strip()]
    else:
        direct_change_lines = item.get("guidance_change_lines")
        if isinstance(direct_change_lines, list) and direct_change_lines:
            change_lines = [str(x).strip() for x in direct_change_lines if str(x).strip()]
        else:
            change_lines = _proposed_change_lines_for_guidance_item(item, state)
    change_summary = str(
        payload.get("guidance_change_summary_compact")
        or _guidance_compact_change_text(change_lines)
    ).strip()
    why_text = _guidance_compact_why_text(item)
    alt_text = _guidance_compact_alternatives_text(item)
    is_resolved = _guidance_item_is_resolved_one_click(item)
    expected_util = _guidance_item_expected_util(item)
    expected_text = f"Expected util: {expected_util:.2f}" if (is_resolved and expected_util is not None) else ""
    lines = [
        f"<div class='fast-guidance-reason'>{html.escape('Change: ' + change_summary)}</div>",
        f"<div class='fast-guidance-reason'>{html.escape(why_text)}</div>",
    ]
    if expected_text:
        lines.insert(1, f"<div class='fast-guidance-reason'>{html.escape(expected_text)}</div>")
    if alt_text:
        lines.append(f"<div class='fast-guidance-secondary'>{html.escape(alt_text)}</div>")
    return "".join(lines)


def _guidance_default_alternatives_text(state: dict, updates: dict, subfamilies: list[str]) -> str:
    sf = set(subfamilies or _compound_subfamilies_from_updates(updates))
    if sf >= {"geometry", "bottom_reo"}:
        d0, d1, w0, w1 = _compound_geometry_deltas(state, updates)
        if w1 > w0 + 0.5 and d1 <= d0 + 0.5:
            return "Other options: Increase depth instead, or use a different bottom reo layout."
        if d1 > d0 + 0.5 and w1 <= w0 + 0.5:
            return "Other options: Increase width instead, or use a different bottom reo layout."
        return "Other options: Use a geometry-first step, or a different bottom reo layout."
    if "shear" in sf:
        return "Other options: Tighten stirrup spacing, or increase the number of legs."
    if "geometry" in sf:
        return "Other options: Increase depth or section width."
    if "bottom_reo" in sf:
        return "Other options: Use a different bottom reo layout."
    return ""


def _geometry_trial_title_for_choice(base_title: str, g: dict, state: dict) -> str:
    upd = dict(g.get("updates") or {})
    if not upd:
        return base_title
    merged = _merge_guidance_state(state, upd)
    d0 = float(_float_from_state(state, "D", 0.0))
    d1 = float(_float_from_state(merged, "D", d0))
    wkey, _, w0 = _resolve_geometry_width_context(state)
    w0 = float(w0 or 0.0)
    w1 = float(upd.get(wkey, merged.get(wkey, w0)) or w0)
    if d1 < d0 - 1e-9 and w1 > w0 + 1e-9:
        return "Rebalance depth and width for bending"
    if d1 < d0 - 1e-9 and w1 <= w0 + 1e-9:
        return "Reduce depth slightly for bending"
    if w1 > w0 + 1e-9 and abs(d1 - d0) <= 1e-9:
        return "Increase width slightly for bending"
    if d1 > d0 + 1e-9 and w1 <= w0 + 1e-9:
        return "Increase depth for bending"
    if d1 > d0 + 1e-9 and w1 > w0 + 1e-9:
        return "Increase depth and width for bending"
    return base_title


def _shallower_beam_correction_trial_updates(state: dict) -> list[tuple[str, dict]]:
    seed = dict(state)
    wkey, _, w0 = _resolve_geometry_width_context(seed)
    w0 = float(w0 or 0.0)
    d0 = float(_float_from_state(seed, "D", 600.0))
    trials: list[tuple[str, dict]] = []
    for d_step in (50.0, 100.0):
        for w_add in (25.0, 50.0):
            new_d = d0 - d_step
            if new_d < 350.0:
                continue
            new_w = w0 + w_add
            tw = _geometry_state_with_updates(seed, depth=new_d, width=new_w)
            upd: dict[str, float] = {}
            if abs(float(tw.get("D", d0)) - d0) > 1e-9:
                upd["D"] = float(tw["D"])
            if wkey in tw and abs(float(tw[wkey]) - w0) > 1e-9:
                upd[wkey] = float(tw[wkey])
            if wkey != "b" and "b" in tw:
                upd["b"] = float(tw["b"])
            if len(upd) >= 2:
                trials.append(
                    (
                        f"Reduce depth ~{int(d_step)} mm and widen ~{int(w_add)} mm (shallower-beam correction)",
                        upd,
                    )
                )
    return trials


def _guidance_default_banner_title(action_type: str) -> str:
    mapping = {
        "apply_geometry_recommendation": "Adjust section geometry",
        "apply_bottom_recommendation": "Adjust bottom reinforcement",
        "apply_shear_recommendation": "Adjust shear reinforcement",
        "apply_compound_guidance": "Combined design update",
        "apply_resolved_candidate": "Apply one-click design",
        "apply_mode_recommendation": "Apply optimisation recommendation",
        "reduce_bottom_reinforcement": "Reduce bottom reinforcement",
        "tighten_geometry": "Tighten section geometry",
        "increase_link_spacing": "Increase link spacing",
        "reduce_number_of_legs": "Reduce number of shear legs",
        "increase_depth": "Increase beam depth",
        "increase_width": "Increase beam width",
        "reduce_link_spacing": "Reduce link spacing",
        "deflection_reduce_sustained_load": "Adjust sustained loads",
        "reduce_bar_spacing": "Reduce bar spacing",
        "guided_solve_step": "Guided design step",
    }
    return mapping.get(str(action_type or ""), "Design guide update")


def _prepare_guidance_apply_banner_meta(action_type: str, payload: dict | None) -> None:
    p = dict(payload or {})
    title = p.get("guidance_banner_title") or p.get("label")
    if not title:
        title = _guidance_default_banner_title(action_type)
    st.session_state[DESIGN_GUIDE_APPLY_BANNER_META_KEY] = {
        "title": str(title),
        "summary": p.get("guidance_banner_summary"),
        "action_type": str(action_type or ""),
    }


def _store_design_guide_apply_banner_payload(prior_state: dict, after_state: dict) -> None:
    meta = st.session_state.pop(DESIGN_GUIDE_APPLY_BANNER_META_KEY, None)
    if not isinstance(meta, dict):
        return
    title = meta.get("title") or _guidance_default_banner_title(str(meta.get("action_type") or ""))
    summary = meta.get("summary")
    change_lines = _guidance_apply_change_lines(prior_state, after_state)
    st.session_state[DESIGN_GUIDE_APPLY_BANNER_KEY] = {
        "applied_at": datetime.now().isoformat(timespec="seconds"),
        "recommendation_title": str(title),
        "recommendation_summary": summary,
        "before": _design_guide_apply_snapshot(prior_state),
        "after": _design_guide_apply_snapshot(after_state),
        "change_lines": change_lines,
    }


def _render_design_guide_post_apply_banner(fast_focus_section: str | None) -> None:
    if fast_focus_section != "model":
        return
    payload = st.session_state.pop(DESIGN_GUIDE_APPLY_BANNER_KEY, None)
    fallback = "Model updated below. Review the live section before continuing."
    if not isinstance(payload, dict):
        return
    title_raw = str(payload.get("recommendation_title") or "Applied recommendation")
    title_esc = html.escape(title_raw)
    lines = payload.get("change_lines") or []
    usable = [str(x).strip() for x in lines if str(x).strip()]
    if usable:
        body = "<br>".join(html.escape(x) for x in usable)
        inner = (
            f"<div class='fast-auto-design-summary-title'>Applied recommendation: {title_esc}</div>"
            f"<div class='fast-auto-design-summary-step'>{body}</div>"
        )
        st.markdown(
            f"<div class='fast-auto-design-summary fast-next-hint--design-guide-follow'>{inner}</div>",
            unsafe_allow_html=True,
        )
        return
    inner = (
        f"<div class='fast-auto-design-summary-title'>Applied recommendation: {title_esc}</div>"
        f"<div class='fast-auto-design-summary-step'>{html.escape(fallback)}</div>"
    )
    st.markdown(
        f"<div class='fast-auto-design-summary fast-next-hint--design-guide-follow'>{inner}</div>",
        unsafe_allow_html=True,
    )


def _compound_subfamilies_from_updates(updates: dict) -> list[str]:
    if not updates:
        return []
    keys = set(updates.keys())
    out: list[str] = []
    if keys & _COMPOUND_GEOMETRY_UPDATE_KEYS:
        out.append("geometry")
    if keys & _COMPOUND_BOTTOM_UPDATE_KEYS:
        out.append("bottom_reo")
    if keys & _COMPOUND_SHEAR_UPDATE_KEYS:
        out.append("shear")
    return out


def _compound_geometry_deltas(state: dict, updates: dict) -> tuple[float, float, float, float]:
    """Returns (d0, d1, w0, w1) for width key resolved from state."""
    s0 = _guidance_state_snapshot(state)
    s1 = dict(s0)
    s1.update(updates)
    d0 = float(_float_from_state(s0, "D", 0.0) or 0.0)
    d1 = float(_float_from_state(s1, "D", d0) or d0)
    wkey, _, w0f = _resolve_geometry_width_context(s0)
    w0 = float(w0f or 0.0)
    w1 = float(_design_width_value(s1) or w0)
    return d0, d1, w0, w1


def _compound_guidance_title_reasoning_why(
    state: dict,
    updates: dict,
    subfamilies: list[str],
    *,
    strengthening: bool,
) -> tuple[str, str, str]:
    """Returns (title_main, reasoning_with_why_prefix, guidance_why_plain)."""
    sf = set(subfamilies)
    eps = 0.5
    d0, d1, w0, w1 = _compound_geometry_deltas(state, updates) if updates else (0.0, 0.0, 0.0, 0.0)
    grow_d = d1 > d0 + eps
    grow_w = w1 > w0 + eps

    if strengthening:
        if sf >= {"geometry", "bottom_reo"}:
            if grow_d and grow_w:
                title = "Increase depth, width, and bottom reinforcement"
            elif grow_d and not grow_w:
                title = "Increase depth and bottom reinforcement"
            elif grow_w and not grow_d:
                title = "Increase width and bottom reinforcement"
            else:
                title = "Adjust section and bottom reinforcement"
            why = (
                "Bending demand is above capacity. Changing the section together with bottom steel is the most direct "
                "way to bring capacity in line with the applied actions."
            )
            return (
                title,
                f"Why: {why}",
                why,
            )
        if sf >= {"shear", "bottom_reo"}:
            title = "Reduce shear links and adjust bottom reinforcement"
            why = (
                "Shear links look heavier than needed for the applied shear. Reducing links and rebalancing longitudinal "
                "steel keeps detailing consistent with demand."
            )
            return (title, f"Why: {why}", why)
        if sf >= {"geometry", "shear"}:
            title = "Adjust section geometry and shear reinforcement"
            why = (
                "Flexure and shear both need attention. Updating geometry and shear reinforcement together avoids fixing "
                "one check while leaving the other marginal."
            )
            return (title, f"Why: {why}", why)
        why = "Several inputs need to move together to reach a compliant, coherent design."
        return (
            "Apply combined strengthening update",
            f"Why: {why}",
            why,
        )
    if sf >= {"geometry", "bottom_reo"}:
        title = "Reduce section size and rebalance bottom reinforcement"
        why = (
            "Utilisation is below the target band. A small section trim with a light steel rebalance moves the design "
            "toward efficient use without large jumps."
        )
        return (title, f"Why: {why}", why)
    if sf >= {"shear", "bottom_reo"}:
        title = "Reduce shear links and trim bottom reinforcement"
        why = (
            "The section is conservative on shear and steel. Relaxing links and trimming bottom steel tightens the design "
            "without increasing member size."
        )
        return (title, f"Why: {why}", why)
    if sf >= {"geometry", "shear"}:
        title = "Tighten geometry and shear reinforcement"
        why = (
            "Reserve is available on both flexure-related geometry and shear. Coordinated reductions keep detailing "
            "consistent while lifting utilisation toward the target band."
        )
        return (title, f"Why: {why}", why)
    why = "Combined adjustments move several checks together toward the target utilisation band."
    return (
        "Apply coordinated efficiency update",
        f"Why: {why}",
        why,
    )


def _compound_strengthening_viable(seed_candidate: dict, trial_candidate: dict | None) -> bool:
    if not trial_candidate:
        return False
    if bool(trial_candidate.get("is_compliant")):
        return True
    return is_valid_progress_while_failing(trial_candidate, seed_candidate)


def _efficiency_distance_to_target_band(worst: float) -> float:
    if GUIDANCE_TARGET_UTIL_MIN <= worst <= GUIDANCE_TARGET_UTIL_MAX:
        return 0.0
    if worst < GUIDANCE_TARGET_UTIL_MIN:
        return GUIDANCE_TARGET_UTIL_MIN - worst
    return worst - GUIDANCE_TARGET_UTIL_MAX


def _compound_efficiency_incoherent(
    base_state: dict,
    trial_state: dict,
    seed_candidate: dict,
    trial_candidate: dict,
) -> bool:
    d0 = float(_float_from_state(base_state, "D", 0.0))
    d1 = float(_float_from_state(trial_state, "D", 0.0))
    _, _, w0 = _resolve_geometry_width_context(base_state)
    _, _, w1 = _resolve_geometry_width_context(trial_state)
    a0 = float(seed_candidate.get("Ast_bot", 0.0) or 0.0)
    a1 = float(trial_candidate.get("Ast_bot", 0.0) or 0.0)
    if d1 > d0 + 1e-9 and a1 > a0 + 1e-9:
        return True
    if w1 > w0 + 1e-9 and d1 > d0 + 1e-9:
        return True
    return False


def _try_compound_strengthening_guidance_item(
    state: dict,
    overview: dict,
    primary_item: dict | None,
) -> dict | None:
    if not _recommendation_search_allowed(state):
        return None
    if str((primary_item or {}).get("check_key") or "") != "bending":
        return None
    seed_c = evaluate_candidate_full(_guidance_state_snapshot(state), source="compound_strengthen_seed")
    if not seed_c:
        return None

    geo_rec = None if _geometry_lock_enabled(state) else _compute_geometry_recommendation(state)
    bot_rec = _compute_bottom_reo_recommendation(state)
    design_context = _build_design_actions_context(state)
    actions = design_context.get("actions") or {}
    shear_clean = _try_shear_no_demand_cleanup_recommendation(state, overview, actions)

    geo_u = dict((geo_rec or {}).get("updates") or {})
    bot_u: dict = {}
    if bot_rec:
        bot_u = dict(bot_rec.get("updates") or {})
        if not bot_u and isinstance(bot_rec.get("arrangement"), dict):
            bot_u = dict(_bottom_arrangement_to_shared_updates(bot_rec["arrangement"]) or {})
    clean_u = dict((shear_clean or {}).get("updates") or {})

    merged_pairs: list[tuple[dict, list[str]]] = []

    def _consider(merged: dict) -> None:
        if not merged or _updates_match_state(state, merged):
            return
        subs = _compound_subfamilies_from_updates(merged)
        if len(set(subs)) < 2:
            return
        merged_pairs.append((merged, subs))

    _consider({**geo_u, **bot_u})
    _consider({**clean_u, **bot_u})
    _consider({**clean_u, **geo_u})
    all_u = {**clean_u, **geo_u, **bot_u}
    _consider(all_u)

    if not merged_pairs:
        return None

    best: tuple[dict, list[str], dict] | None = None
    best_wu = float("inf")

    for merged, subs in merged_pairs:
        trial_st = dict(state)
        trial_st.update(merged)
        trial_c = evaluate_candidate_full(
            _guidance_state_snapshot(trial_st),
            source="compound_strengthen_rank",
            updates=merged,
        )
        if not trial_c or not _compound_strengthening_viable(seed_c, trial_c):
            continue
        wu = float(trial_c.get("worst_util", 999.0) or 999.0)

        single_best = float("inf")
        if geo_u:
            tg = dict(state)
            tg.update(geo_u)
            cg = evaluate_candidate_full(_guidance_state_snapshot(tg), source="compound_strengthen_geo_only")
            if cg:
                single_best = min(single_best, float(cg.get("worst_util", 999.0) or 999.0))
        if bot_u:
            tb = dict(state)
            tb.update(bot_u)
            cb = evaluate_candidate_full(_guidance_state_snapshot(tb), source="compound_strengthen_bot_only")
            if cb:
                single_best = min(single_best, float(cb.get("worst_util", 999.0) or 999.0))
        if single_best < float("inf") and wu > single_best + 1e-6:
            continue

        if wu < best_wu - 1e-9:
            best_wu = wu
            best = (merged, subs, trial_c)

    if not best:
        return None
    merged, subs, _trial_c = best
    title, reasoning, guidance_why = _compound_guidance_title_reasoning_why(
        state, merged, subs, strengthening=True,
    )
    c_lines = _guidance_change_lines_for_updates(state, merged)
    return _guidance_item(
        "bending",
        title,
        "Apply recommendation",
        None,
        reasoning,
        "Key levers: depth D, beam width, bottom reinforcement, shear links",
        "apply_compound_guidance",
        {
            "updates": merged,
            "guidance_banner_title": title,
            "guidance_banner_summary": reasoning,
        },
        status=str((primary_item or {}).get("status") or "FAIL"),
        util=(primary_item or {}).get("util"),
        guidance_change_lines=c_lines or None,
        guidance_why=guidance_why,
    )


def _try_compound_efficiency_guidance_item(state: dict, efficiency_state: dict) -> dict | None:
    if efficiency_state.get("mode_tightening"):
        return None
    if not bool(efficiency_state.get("is_efficiency_reduction_mode")):
        return None
    if not _recommendation_search_allowed(state):
        return None

    overview = efficiency_state.get("overview") or {}
    filter_growth = bool(efficiency_state.get("filter_growth_candidates"))

    seed_c = evaluate_candidate_full(_guidance_state_snapshot(state), source="compound_efficiency_seed")
    if not seed_c:
        return None

    bottom_t = efficiency_state.get("bottom_tightening")
    geometry_t = efficiency_state.get("geometry_tightening")
    shear_t = efficiency_state.get("shear_tightening")

    design_context = _build_design_actions_context(state)
    actions = dict(design_context.get("actions") or {})
    shear_clean = _try_shear_no_demand_cleanup_recommendation(state, overview, actions)

    bottom_u: dict = {}
    if bottom_t and isinstance(bottom_t.get("arrangement"), dict):
        bottom_u = dict(_bottom_arrangement_to_shared_updates(bottom_t["arrangement"]) or {})

    geo_u = dict((geometry_t or {}).get("updates") or {})
    clean_u = dict((shear_clean or {}).get("updates") or {})
    shear_u = dict((shear_t or {}).get("updates") or {}) if shear_t else {}
    shear_merge = clean_u if clean_u else shear_u

    candidates_ranked: list[tuple[float, dict, dict]] = []

    for merged in (
        {**geo_u, **bottom_u},
        {**shear_merge, **bottom_u},
        {**shear_merge, **geo_u},
    ):
        if not merged or _updates_match_state(state, merged):
            continue
        subs = _compound_subfamilies_from_updates(merged)
        if len(set(subs)) < 2:
            continue
        trial_st = dict(state)
        trial_st.update(merged)
        trial_c = evaluate_candidate_full(
            _guidance_state_snapshot(trial_st),
            source="compound_efficiency_rank",
            updates=merged,
        )
        if not trial_c or not bool(trial_c.get("is_compliant")):
            continue
        if filter_growth and _candidate_is_growth_move(seed_c, trial_c):
            _log_efficiency_growth_rejection(
                candidate_family="compound",
                seed_candidate=seed_c,
                candidate=trial_c,
            )
            continue
        if filter_growth and _compound_efficiency_incoherent(state, trial_st, seed_c, trial_c):
            continue
        w_after = float(((trial_c.get("overview") or {}).get("worst_util")) or 0.0)
        dist = _efficiency_distance_to_target_band(w_after)
        candidates_ranked.append((dist, merged, trial_c))

    if not candidates_ranked:
        return None
    candidates_ranked.sort(key=lambda row: row[0])
    _dist, merged, _trial_c = candidates_ranked[0]
    subs = _compound_subfamilies_from_updates(merged)
    title, reasoning, guidance_why = _compound_guidance_title_reasoning_why(
        state, merged, subs, strengthening=False,
    )
    worst = float(overview.get("worst_util", 0.0) or 0.0)
    focus = _governing_focus_from_overview(overview)
    ce_lines = _guidance_change_lines_for_updates(state, merged)
    return _guidance_item(
        focus,
        title,
        "Apply recommendation",
        None,
        reasoning,
        "Key levers: depth D, beam width, bottom reinforcement, shear links",
        "apply_compound_guidance",
        {
            "updates": merged,
            "guidance_banner_title": title,
            "guidance_banner_summary": reasoning,
        },
        status="EFFICIENCY",
        util=worst,
        guidance_change_lines=ce_lines or None,
        guidance_why=guidance_why,
    )


def _design_guide_focus_label(focus: str | None) -> str:
    mapping = {
        "bending": "Bending",
        "shear": "Shear",
        "geometry": "Geometry",
        "crack": "Crack control",
        "deflection": "Deflection",
        "general": "Overall design",
    }
    return mapping.get(str(focus or "general").strip().lower(), "Overall design")


def _guidance_governing_primary_action(overview: dict | None) -> tuple[str, dict[str, float | None]]:
    utils = ((overview or {}).get("utils") or {})
    primary_utils: dict[str, float | None] = {}
    ranked: list[tuple[str, float]] = []
    for key in ("bending", "shear"):
        raw = utils.get(key)
        try:
            resolved = float(raw)
        except Exception:
            primary_utils[key] = None
            continue
        if math.isnan(resolved):
            primary_utils[key] = None
            continue
        primary_utils[key] = resolved
        ranked.append((key, resolved))
    if ranked:
        ranked.sort(key=lambda item: item[1], reverse=True)
        return ranked[0][0], primary_utils
    return "general", primary_utils


def _governing_focus_from_overview(overview: dict | None) -> str:
    governing_action, _ = _guidance_governing_primary_action(overview)
    if governing_action != "general":
        return governing_action
    utils = ((overview or {}).get("utils") or {})
    ranked = [("crack", utils.get("crack")), ("deflection", utils.get("deflection"))]
    best_key = "general"
    best_util = -1.0
    for key, value in ranked:
        try:
            resolved = float(value)
        except Exception:
            continue
        if math.isnan(resolved):
            continue
        if resolved > best_util:
            best_key = key
            best_util = resolved
    return best_key


def _log_guidance_branch_governing_mismatch(
    *,
    guidance_branch: str,
    governing_action: str,
    primary_utils: dict[str, float | None],
    selected_item: dict | None,
) -> None:
    if not bool(st.session_state.get("_dev_mode")):
        return
    branch_name = str(guidance_branch or "")
    branch_action = branch_name
    for prefix in ("critical_", "efficiency_", "passing_guidance_"):
        if branch_name.startswith(prefix):
            branch_action = branch_name[len(prefix) :]
            break
    is_shear_branch = (
        "shear" in branch_name
        or _guidance_action_to_payload_name(branch_action) == "shear_tightening"
        or str((selected_item or {}).get("check_key") or "") == "shear"
    )
    if not is_shear_branch:
        return
    bending_util = primary_utils.get("bending")
    shear_util = primary_utils.get("shear")
    if bending_util is None or shear_util is None:
        return
    if float(shear_util) >= float(bending_util):
        return
    _agent_debug_log(
        "Shear branch selected while bending util exceeds shear util",
        {
            "guidance_branch": guidance_branch,
            "governing_action": governing_action,
            "bending_util": bending_util,
            "shear_util": shear_util,
            "selected_action_type": None if not selected_item else selected_item.get("action_type"),
            "selected_title": None if not selected_item else selected_item.get("title_main"),
        },
        location="inputs_page.py:_compute_design_guidance_items",
        hypothesis_id="H_GUIDANCE_GOVERNING",
    )


def _candidate_debug_summary(candidate: dict | None) -> dict | None:
    if not candidate:
        return None
    candidate_state = dict(candidate.get("state") or {})
    overview = dict(candidate.get("overview") or {})
    bending_pack = ((overview.get("packs") or {}).get("bending") or {})
    summary = {
        "label": str(candidate.get("label") or ""),
        "bottom_reo_label": _bottom_reo_state_label(candidate_state) if candidate_state else "",
        "b": float(_design_width_value(candidate_state) if candidate_state else 0.0),
        "D": float(candidate.get("depth", _float_from_state(candidate_state, "D", 0.0)) if candidate_state else 0.0),
        "bot1_count": int(candidate_state.get("bot1_count", 0) or 0),
        "bot2_count": int(candidate_state.get("bot2_count", 0) or 0),
        "db_bot_1": int(candidate_state.get("db_bot_1", candidate_state.get("db_bot", 0)) or 0),
        "db_bot_2": int(candidate_state.get("db_bot_2", candidate_state.get("db_bot_1", candidate_state.get("db_bot", 0))) or 0),
        "bars": int(candidate_state.get("bot1_count", 0) or 0) + int(candidate_state.get("bot2_count", 0) or 0),
        "dia": int(candidate_state.get("db_bot_1", candidate_state.get("db_bot", 0)) or 0),
        "Ast_bot": float(candidate.get("Ast_bot", 0.0) or 0.0),
        "summary_phiMu_kNm": float(bending_pack.get("summary_phiMu_kNm", 0.0) or 0.0),
        "summary_Mu_star_kNm": float(bending_pack.get("summary_Mu_star_kNm", 0.0) or 0.0),
        "bending_util": None,
        "worst_util": float(candidate.get("worst_util", 0.0) or 0.0),
        "real_util": None,
        "optimisation_score": float(_candidate_objective_util(candidate)),
        "score": None if candidate.get("score") is None else float(candidate.get("score", 0.0) or 0.0),
        "pass": bool(candidate.get("is_compliant")),
        "source": str(candidate.get("source") or ""),
        "ductility_util": _candidate_ductility_util(candidate),
        "ductility_pass": None,
        "ductility_tier": int(candidate.get("_ductility_tier", 0) or 0),
        "ductility_tier_label": str(candidate.get("_ductility_tier_label") or ""),
        "reason_selected": str(candidate.get("_ductility_reason") or ""),
    }
    try:
        bending_util = ((overview.get("utils") or {}).get("bending"))
        summary["bending_util"] = None if bending_util is None else float(bending_util)
    except Exception:
        summary["bending_util"] = None
    phi_m = float(summary["summary_phiMu_kNm"] or 0.0)
    mu_m = float(summary["summary_Mu_star_kNm"] or 0.0)
    summary["real_util"] = (mu_m / phi_m) if phi_m > 1e-9 else None
    if summary["ductility_util"] is not None:
        summary["ductility_pass"] = bool(float(summary["ductility_util"]) <= 1.0)
    return summary


def _materialize_full_evaluated_candidate(candidate: dict | None, *, source: str) -> dict | None:
    if not candidate:
        return None
    candidate_state = dict(candidate.get("state") or {})
    if not candidate_state:
        return None
    full_candidate = evaluate_candidate_full(
        candidate_state,
        source=source,
        label=str(candidate.get("label") or source.replace("_", " ").title()),
        action_type=str(candidate.get("action_type") or ""),
        updates=dict(candidate.get("updates") or {}),
    )
    if full_candidate is None:
        return None
    for key in (
        "score",
        "reo_complexity",
        "guidance_preview_util",
        "arrangement",
        "actual_ast",
        "required_ast",
    ):
        if key in candidate:
            full_candidate[key] = candidate.get(key)
    return full_candidate


def _overview_debug_summary(state: dict, overview: dict | None) -> dict:
    resolved_overview = overview or {}
    bending_pack = ((resolved_overview.get("packs") or {}).get("bending") or {})
    utils = dict(resolved_overview.get("utils") or {})
    return {
        "bottom_reo_label": _bottom_reo_state_label(state),
        "Ast_bot": float((_effective_bottom_design_state(state) or {}).get("Ast_bot", 0.0) or 0.0),
        "summary_phiMu_kNm": float(bending_pack.get("summary_phiMu_kNm", 0.0) or 0.0),
        "summary_Mu_star_kNm": float(bending_pack.get("summary_Mu_star_kNm", 0.0) or 0.0),
        "bending_util": None if utils.get("bending") is None else float(utils.get("bending")),
        "worst_util": float(resolved_overview.get("worst_util", 0.0) or 0.0),
        "governing_focus": _design_guide_focus_label(_governing_focus_from_overview(resolved_overview)),
    }


def _build_crack_pack_from_state(state: dict) -> dict:
    crack = _evaluate_crack_with_state(state, bottom_updates=_candidate_bottom_updates(state))
    if crack is None:
        return {"summary_util": None, "rows": []}
    util = float(crack.get("util", 0.0) or 0.0)
    sigma_sr = float(crack.get("sigma_sr", 0.0) or 0.0)
    sigma_allow = float(crack.get("sigma_allow_table", 0.0) or 0.0)
    w_calc = float(crack.get("w_calc", 0.0) or 0.0)
    w_lim = _float_from_state(state, "wmax_char_limit", 0.3)
    return {
        "summary_util": util,
        "rows": [
            {
                "uid": "crk_step_4",
                "title": "Governing outcome",
                "value": "Both checks pass" if util <= 1.0 else "One or more checks fail",
                "limit": "Table stress + direct width",
                "util": "—",
                "status": "PASS" if util <= 1.0 else "FAIL",
                "route_page": "crack",
            },
            {
                "uid": "crk_step_2",
                "title": "Table-based crack control check",
                "value": f"σ_sr = {sigma_sr:.1f} MPa",
                "limit": f"σ_allow = {sigma_allow:.1f} MPa" if sigma_allow > 0.0 else "—",
                "util": f"{(sigma_sr / sigma_allow):.2f}" if sigma_allow > 0.0 else "—",
                "status": _status_from_candidate_util((sigma_sr / sigma_allow) if sigma_allow > 0.0 else None),
                "route_page": "crack",
            },
            {
                "uid": "crk_step_3",
                "title": "Direct crack width check",
                "value": f"w = {w_calc:.3f} mm",
                "limit": f"w'max = {w_lim:.3f} mm" if w_lim > 0.0 else "—",
                "util": f"{(w_calc / w_lim):.2f}" if w_lim > 0.0 else "—",
                "status": _status_from_candidate_util((w_calc / w_lim) if w_lim > 0.0 else None),
                "route_page": "crack",
            },
        ],
    }


def _build_deflection_pack_from_state(state: dict) -> dict:
    deflection = _evaluate_deflection_with_state(state, bottom_updates=_candidate_bottom_updates(state))
    if deflection is None:
        return {
            "summary_delta_total_mm": None,
            "summary_defl_limit_mm": None,
            "summary_util_total": None,
            "rows": [],
        }
    return dict(deflection.get("pack") or {})


def _collect_design_overview(state: dict, context: dict | None = None) -> dict:
    design_context = context or _build_design_actions_context(state)
    overview_state = dict(design_context.get("state") or _state_with_resolved_design_actions(state))
    actions = dict(design_context.get("actions") or _resolve_design_actions_from_state(overview_state))
    bend_pack = build_bending_check_rows_from_state(overview_state) or {}
    shear_pack = build_shear_check_rows_from_state(overview_state) or {}
    crack_pack = _build_crack_pack_from_state(overview_state)
    defl_pack = _build_deflection_pack_from_state(overview_state)

    crack_rows = crack_pack.get("rows") or []
    crack_utils = [_parse_util_value(row.get("util")) for row in crack_rows]
    crack_util_values = [util for util in crack_utils if util is not None]

    bending_status, _ = _overall_status_from_rows(bend_pack.get("rows") or [])
    shear_status, _ = _overall_status_from_rows(shear_pack.get("rows") or [])
    crack_status, _ = _overall_status_from_rows(crack_rows)
    deflection_status, _ = _overall_status_from_rows(defl_pack.get("rows") or [])

    bending_util = _parse_util_value(bend_pack.get("summary_util"))
    shear_util = _parse_util_value(shear_pack.get("summary_util"))
    crack_util = max(crack_util_values) if crack_util_values else None
    deflection_util = _parse_util_value(defl_pack.get("summary_util_total"))

    statuses = {
        "bending": bending_status,
        "shear": shear_status,
        "crack": crack_status,
        "deflection": deflection_status,
    }
    util_map = {
        "bending": bending_util,
        "shear": shear_util,
        "crack": crack_util,
        "deflection": deflection_util,
    }
    tracked_statuses = [status for status in statuses.values() if status not in ("—", "")]
    any_fail = any(status == "FAIL" for status in tracked_statuses)
    any_warn = any(status == "NEAR LIMIT" for status in tracked_statuses)
    all_key_pass = bool(tracked_statuses) and all(status == "PASS" for status in tracked_statuses)
    worst_util = max((util for util in util_map.values() if util is not None), default=0.0)
    return {
        "packs": {
            "bending": bend_pack,
            "shear": shear_pack,
            "crack": crack_pack,
            "deflection": defl_pack,
        },
        "statuses": statuses,
        "utils": util_map,
        "any_fail": any_fail,
        "any_warn": any_warn,
        "all_key_pass": all_key_pass,
        "worst_util": worst_util,
        "actions_used": actions,
    }


def _state_with_overrides(state: dict, **updates) -> dict:
    new_state = dict(state)
    new_state.update(updates)
    return new_state


def _resolve_geometry_width_context(state: dict) -> tuple[str, str, float]:
    sec_shape = str(state.get("sec_shape", "RECT") or "RECT")
    if sec_shape == "T":
        return "bw", "Web width bw (mm)", float(state.get("bw", state.get("b", 300.0)) or 300.0)
    if sec_shape == "I":
        return "tw", "Web thickness tw (mm)", float(state.get("tw", state.get("b", 200.0)) or 200.0)
    return "b", "Width b (mm)", float(state.get("b", 400.0) or 400.0)


def _design_width_value(state: dict) -> float:
    _, _, width = _resolve_geometry_width_context(state)
    return float(width)


def _float_from_state(state: dict, key: str, default: float) -> float:
    value = state.get(key)
    if value is None:
        return float(default)
    try:
        return float(value)
    except Exception:
        return float(default)


def _int_from_state(state: dict, key: str, default: int) -> int:
    value = state.get(key)
    if value is None:
        return int(default)
    try:
        return int(value)
    except Exception:
        return int(default)


def _mode_value_from_state(
    state: dict,
    mode_key: str,
    count_key: str,
    spacing_key: str,
    default_count: float,
    default_spacing: float = 200.0,
) -> float:
    mode = str(state.get(mode_key, "Count") or "Count")
    if mode == "Spacing":
        value = state.get(spacing_key)
        return float(default_spacing if value is None else value)
    value = state.get(count_key)
    return float(default_count if value is None else value)


def _uls_action_from_state(state: dict, action: str) -> float:
    resolved_actions = _resolve_design_actions_from_state(state)
    resolved_map = {
        "M": "Mu",
        "V": "Vu",
        "N": "Nu",
        "T": "Tu",
        "P": "Pu",
    }
    resolved_key = resolved_map.get(action)
    if resolved_key is not None:
        mapped = resolved_actions.get(resolved_key)
        if mapped is not None:
            return float(mapped)

    shared_map = {
        "M": "uls_Mstar",
        "V": "uls_Vstar",
        "N": "uls_Nstar",
    }
    if action in shared_map:
        return _float_from_state(state, shared_map[action], 0.0)
    if action == "T":
        return _float_from_state(state, "Tu_star", 0.0)
    if action == "P":
        return _float_from_state(state, "P_star", 0.0)
    return 0.0


def _resolve_design_actions_from_state(state: dict) -> dict:
    return resolve_design_actions(state)


def _state_with_resolved_design_actions(state: dict, actions: dict | None = None) -> dict:
    resolved = _guidance_state_snapshot(state)
    actions = dict(actions or _resolve_design_actions_from_state(resolved))
    resolved["uls_Mstar"] = float(actions.get("Mu", _float_from_state(resolved, "uls_Mstar", 0.0)) or 0.0)
    resolved["uls_Vstar"] = float(actions.get("Vu", _float_from_state(resolved, "uls_Vstar", 0.0)) or 0.0)
    resolved["uls_Nstar"] = float(actions.get("Nu", _float_from_state(resolved, "uls_Nstar", 0.0)) or 0.0)
    resolved["Mu_star"] = float(actions.get("Mu", _float_from_state(resolved, "Mu_star", 0.0)) or 0.0)
    resolved["Vu_star"] = float(actions.get("Vu", _float_from_state(resolved, "Vu_star", 0.0)) or 0.0)
    resolved["N_star"] = float(actions.get("Nu", _float_from_state(resolved, "N_star", 0.0)) or 0.0)
    resolved["sls_Mstar"] = float(actions.get("SLS_M", _float_from_state(resolved, "sls_Mstar", 0.0)) or 0.0)
    resolved["uls_Mstar_pos_manual"] = float(
        _float_from_state(
            resolved,
            "uls_Mstar_pos_manual",
            max(0.0, _float_from_state(resolved, "uls_Mstar", 0.0)),
        )
        or 0.0
    )
    resolved["uls_Mstar_neg_manual"] = float(
        _float_from_state(
            resolved,
            "uls_Mstar_neg_manual",
            max(0.0, -_float_from_state(resolved, "uls_Mstar", 0.0)),
        )
        or 0.0
    )
    resolved["sls_Mstar_pos_manual"] = float(
        _float_from_state(
            resolved,
            "sls_Mstar_pos_manual",
            max(0.0, _float_from_state(resolved, "sls_Mstar", 0.0)),
        )
        or 0.0
    )
    resolved["sls_Mstar_neg_manual"] = float(
        _float_from_state(
            resolved,
            "sls_Mstar_neg_manual",
            max(0.0, -_float_from_state(resolved, "sls_Mstar", 0.0)),
        )
        or 0.0
    )
    resolved["sls_Vstar"] = float(actions.get("SLS_V", _float_from_state(resolved, "sls_Vstar", 0.0)) or 0.0)
    resolved["Tu_star"] = float(actions.get("Tu", _float_from_state(resolved, "Tu_star", 0.0)) or 0.0)
    resolved["P_star"] = float(actions.get("Pu", _float_from_state(resolved, "P_star", 0.0)) or 0.0)
    resolved["actions_uls"] = {
        "M": resolved["uls_Mstar"],
        "V": resolved["uls_Vstar"],
        "N": resolved["uls_Nstar"],
        "T": resolved["Tu_star"],
        "P": resolved["P_star"],
    }
    return resolved


def _build_design_actions_context(state: dict) -> dict:
    source_state = _guidance_state_snapshot(state)
    actions = _resolve_design_actions_from_state(source_state)
    return {
        "state": _state_with_resolved_design_actions(source_state, actions),
        "actions": dict(actions),
        "action_signature": tuple(actions.get("signature", ())),
    }


def _design_action_widget_specs(selected_prefix: str) -> list[dict]:
    return [
        {
            "label": "Positive design moment Mu*+ (kNm)",
            "widget_key": "inputs_load_Mstar_pos_proxy",
            "shared_key": f"{selected_prefix}_Mstar_pos_manual",
            "proxy_key": "load_Mstar_pos_proxy",
            "help_text": "Sagging bending demand magnitude (top in compression, bottom in tension).",
            "disabled_in_design_mode": True,
        },
        {
            "label": "Negative design moment Mu*- (kNm)",
            "widget_key": "inputs_load_Mstar_neg_proxy",
            "shared_key": f"{selected_prefix}_Mstar_neg_manual",
            "proxy_key": "load_Mstar_neg_proxy",
            "help_text": "Hogging bending demand magnitude (top in tension, bottom in compression). Enter as positive.",
            "disabled_in_design_mode": True,
        },
        {
            "label": "Applied prestress P* (kN)",
            "widget_key": "inputs_P_star",
            "shared_key": "P_star",
            "proxy_key": None,
            "help_text": "Net prestress force at the section (compression positive).",
            "disabled_in_design_mode": False,
        },
        {
            "label": "Design torsion Tu* (kNm)",
            "widget_key": "inputs_Tu_star",
            "shared_key": "Tu_star",
            "proxy_key": None,
            "help_text": "Factored torsion; used on torsion page (placeholder here).",
            "disabled_in_design_mode": True,
        },
        {
            "label": "Design shear Vu* (kN)",
            "widget_key": "inputs_load_Vstar_proxy",
            "shared_key": f"{selected_prefix}_Vstar",
            "proxy_key": "load_Vstar_proxy",
            "help_text": "Factored design shear at the critical section.",
            "disabled_in_design_mode": True,
        },
        {
            "label": "Axial force N* (kN)",
            "widget_key": "inputs_load_Nstar_proxy",
            "shared_key": f"{selected_prefix}_Nstar",
            "proxy_key": "load_Nstar_proxy",
            "help_text": "Axial action at the section (+compression / −tension).",
            "disabled_in_design_mode": True,
        },
    ]


def _sync_design_action_widget_to_shared(widget_key: str, shared_key: str, proxy_key: str | None = None) -> None:
    value = st.session_state.get(widget_key)
    if value is None:
        return
    numeric_value = float(value or 0.0)
    if shared_key.endswith("_Mstar_pos_manual") or shared_key.endswith("_Mstar_neg_manual"):
        numeric_value = max(0.0, numeric_value)
    mark_user_edit(widget_key, shared_key)
    set_shared(shared_key, numeric_value, source="design_action_widget_sync")
    if proxy_key:
        set_shared(proxy_key, numeric_value, source="design_action_widget_sync")
    if shared_key.endswith("_Mstar_pos_manual") or shared_key.endswith("_Mstar_neg_manual"):
        prefix = "uls" if shared_key.startswith("uls_") else "sls"
        pos = float(get_param(f"{prefix}_Mstar_pos_manual", 0.0) or 0.0)
        neg = float(get_param(f"{prefix}_Mstar_neg_manual", 0.0) or 0.0)
        set_shared(f"{prefix}_Mstar", float(pos - neg), source="design_action_widget_sync")
        if prefix == "uls":
            set_shared("Mu_star_pos_manual", float(pos), source="design_action_widget_sync")
            set_shared("Mu_star_neg_manual", float(neg), source="design_action_widget_sync")
            set_shared("Mu_star_manual", float(pos - neg), source="design_action_widget_sync")
            set_shared("load_Mstar_proxy", float(pos - neg), source="design_action_widget_sync")
    if shared_key in {"uls_Nstar", "sls_Nstar"}:
        set_shared("N_star", numeric_value, source="design_action_widget_sync")
    _mark_design_guide_dirty()
    _sync_auto_design_invalidation(_shared_state_snapshot())
    if DEBUG_DESIGN_GUIDANCE_PROBE:
        _debug_check_design_action_consistency(_shared_state_snapshot())


def _make_design_action_widget_callback(widget_key: str, shared_key: str, proxy_key: str | None = None):
    def _callback() -> None:
        _sync_design_action_widget_to_shared(widget_key, shared_key, proxy_key)

    return _callback


def _commit_design_action_widgets_to_shared(selected_prefix: str) -> None:
    for spec in _design_action_widget_specs(selected_prefix):
        widget_key = spec["widget_key"]
        if widget_key not in st.session_state:
            continue
        _sync_design_action_widget_to_shared(
            widget_key,
            str(spec["shared_key"]),
            spec.get("proxy_key"),
        )


def _mirror_design_action_proxies_from_shared(selected_prefix: str) -> None:
    proxy_pairs = (
        ("load_Mstar_pos_proxy", f"{selected_prefix}_Mstar_pos_manual"),
        ("load_Mstar_neg_proxy", f"{selected_prefix}_Mstar_neg_manual"),
        ("load_Mstar_proxy", f"{selected_prefix}_Mstar"),
        ("load_Vstar_proxy", f"{selected_prefix}_Vstar"),
        ("load_Nstar_proxy", f"{selected_prefix}_Nstar"),
    )
    for proxy_key, shared_key in proxy_pairs:
        set_shared(proxy_key, float(get_param(shared_key, 0.0) or 0.0), source="design_action_proxy_mirror")


def _hydrate_design_action_widgets_from_shared(selected_prefix: str, *, force: bool = False, design_controls: bool = False) -> None:
    specs = _design_action_widget_specs(selected_prefix)
    signature = (
        selected_prefix,
        bool(design_controls),
        tuple(
            float(get_param(str(spec["shared_key"]), 0.0) or 0.0)
            for spec in specs
        ),
    )
    should_hydrate = force or design_controls or st.session_state.get("_design_action_widget_signature") != signature
    # Snapshot widget keys before sync (for dev-only hydration trace).
    _dbg_w_pos = st.session_state.get("inputs_load_Mstar_pos_proxy")
    _dbg_w_neg = st.session_state.get("inputs_load_Mstar_neg_proxy")
    _dbg_w_signed = st.session_state.get("inputs_load_Mstar_proxy")
    for spec in specs:
        widget_key = str(spec["widget_key"])
        shared_key = str(spec["shared_key"])
        if should_hydrate or widget_key not in st.session_state:
            shared_value = float(get_param(shared_key, 0.0) or 0.0)
            old_widget_value = st.session_state.get(widget_key)
            if old_widget_value != shared_value:
                st.session_state[widget_key] = shared_value
    st.session_state["_design_action_widget_signature"] = signature

    # TODO(remove): temporary hydration trace for design-action ghost values (canonical vs widget).
    if bool(st.session_state.get("_dev_mode")):
        try:
            hc_log(
                "[design_action_hydrate]",
                selected_prefix=selected_prefix,
                actions_mode=st.session_state.get("actions_mode"),
                design_controls=bool(design_controls),
                should_hydrate=bool(should_hydrate),
                canonical_pos=float(
                    get_param(f"{selected_prefix}_Mstar_pos_manual", 0.0) or 0.0
                ),
                canonical_neg=float(
                    get_param(f"{selected_prefix}_Mstar_neg_manual", 0.0) or 0.0
                ),
                canonical_signed=float(
                    get_param(f"{selected_prefix}_Mstar", 0.0) or 0.0
                ),
                widget_pos_before=_dbg_w_pos,
                widget_neg_before=_dbg_w_neg,
                widget_signed_before=_dbg_w_signed,
                widget_pos_after_render=st.session_state.get("inputs_load_Mstar_pos_proxy"),
                widget_neg_after_render=st.session_state.get("inputs_load_Mstar_neg_proxy"),
                widget_signed_after_render=st.session_state.get("inputs_load_Mstar_proxy"),
            )
        except Exception:
            pass


def _render_design_action_number_row(
    *,
    label: str,
    widget_key: str,
    help_text: str,
    on_change,
    disabled: bool = False,
) -> float:
    col1, col2 = st.columns([1, 2], gap="medium")
    with col1:
        label_with_hover(label, help_text, required=False)
    with col2:
        _register_rendered_key(widget_key)
        return float(
            st.number_input(
                label,
                key=widget_key,
                format="%.1f",
                step=1.0,
                label_visibility="collapsed",
                on_change=on_change,
                disabled=disabled,
            )
            or 0.0
        )


def _debug_check_design_action_consistency(state: dict) -> None:
    if not DEBUG_DESIGN_GUIDANCE_PROBE:
        return
    if str(st.session_state.get("loads_edit_mode", "ULS") or "ULS").upper() != "ULS":
        return
    actions = _resolve_design_actions_from_state(state)
    payload = {
        "widget_M_pos": st.session_state.get("inputs_load_Mstar_pos_proxy"),
        "widget_M_neg": st.session_state.get("inputs_load_Mstar_neg_proxy"),
        "widget_V": st.session_state.get("inputs_load_Vstar_proxy"),
        "shared_uls_M": st.session_state.get("uls_Mstar"),
        "shared_uls_M_pos": st.session_state.get("uls_Mstar_pos_manual"),
        "shared_uls_M_neg": st.session_state.get("uls_Mstar_neg_manual"),
        "shared_uls_V": st.session_state.get("uls_Vstar"),
        "resolved_M": actions.get("Mu"),
        "resolved_V": actions.get("Vu"),
    }
    _agent_debug_log(
        "Design action consistency check",
        payload,
        location="inputs_page.py:_debug_check_design_action_consistency",
        hypothesis_id="H51",
    )


def _resolve_auto_design_actions_from_state(state: dict) -> dict:
    return _resolve_design_actions_from_state(state)


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


def _state_with_resolved_auto_design_actions(state: dict, actions: dict | None) -> dict:
    return _state_with_resolved_design_actions(state, actions)


def _effective_bottom_design_state(state: dict, bottom_updates: dict | None = None) -> dict:
    from bending_core import _effective_depth_centroid_pure

    D = _float_from_state(state, "D", 600.0)
    cover_bot = _float_from_state(state, "cover_bot", 40.0)
    rowgap_bot = _float_from_state(state, "rowgap_bot", 60.0)
    b = _design_width_value(state)

    if bottom_updates:
        db_bot = float(bottom_updates["db_bot_1"])
        nb_bot = int(bottom_updates["bot1_count"]) + int(bottom_updates["bot2_count"])
        Ast_bot = (nb_bot * math.pi * db_bot**2) / 4.0
    else:
        db_bot = _float_from_state(
            state,
            "db_bot",
            _float_from_state(state, "db_bot_1", 20.0),
        )
        nb_bot = _int_from_state(state, "nb_bot", 0)
        Ast_bot = _float_from_state(state, "Ast_bot", 0.0)

    if nb_bot <= 0 or db_bot <= 0:
        d_centroid = max(D - cover_bot, 0.0)
    else:
        d_centroid = _effective_depth_centroid_pure(
            b=b,
            D=D,
            nb_bot=nb_bot,
            db_bot=db_bot,
            cover_bot=cover_bot,
            rowgap_bot=rowgap_bot,
        )
        if d_centroid in (None, 0):
            d_centroid = D - cover_bot - db_bot / 2.0

    return {
        "Ast_bot": float(Ast_bot),
        "db_bot": float(db_bot),
        "nb_bot": int(nb_bot),
        "d_centroid": float(d_centroid),
    }


def _evaluate_bending_with_bottom_state(state: dict, bottom_updates: dict | None = None) -> dict | None:
    from bending_core import _get_compute_bending_capacity_pure

    bottom_state = _effective_bottom_design_state(state, bottom_updates)
    b = _design_width_value(state)
    D = _float_from_state(state, "D", 600.0)
    fc = _float_from_state(state, "fc", 40.0)
    fsy = _float_from_state(state, "fsy", 500.0)
    phi = _float_from_state(state, "phi_bend", 0.85)
    Mu_star = _uls_action_from_state(state, "M")
    cover_bot = _float_from_state(state, "cover_bot", 40.0)
    rowgap_bot = _float_from_state(state, "rowgap_bot", 60.0)

    if b <= 0 or D <= 0 or bottom_state["db_bot"] <= 0 or bottom_state["nb_bot"] <= 0:
        return None

    compute_fn = _get_compute_bending_capacity_pure()
    results = compute_fn(
        b=b,
        D=D,
        fc=fc,
        fsy=fsy,
        Ast=bottom_state["Ast_bot"],
        Mu_star=Mu_star,
        phi=phi,
        d_input=bottom_state["d_centroid"],
        cover_bot=cover_bot,
        db_bot=bottom_state["db_bot"],
        nb_bot=bottom_state["nb_bot"],
        rowgap_bot=rowgap_bot,
    )
    results["Ast_bot"] = bottom_state["Ast_bot"]
    results["d_centroid"] = bottom_state["d_centroid"]
    results["db_bot"] = bottom_state["db_bot"]
    results["nb_bot"] = bottom_state["nb_bot"]
    return results


def _evaluate_shear_with_state(
    state: dict,
    *,
    bottom_updates: dict | None = None,
    shear_updates: dict | None = None,
) -> dict | None:
    from shear_core import ShearInputs, run_shear_calc

    bottom_state = _effective_bottom_design_state(state, bottom_updates)
    b = _design_width_value(state)
    D = _float_from_state(state, "D", 600.0)
    fc = _float_from_state(state, "fc", 40.0)
    fsy = _float_from_state(state, "fsy", 500.0)
    Ec = _float_from_state(state, "Ec", 30000.0)
    Es = _float_from_state(state, "Es", 200000.0)
    phi = _float_from_state(state, "phi_shear", 0.75)
    d_g = _float_from_state(state, "d_g", 20.0)

    lig_d = _float_from_state(
        shear_updates or state,
        "lig_d",
        _float_from_state(state, "lig_d", 10.0),
    )
    lig_legs = _float_from_state(
        shear_updates or state,
        "lig_legs",
        _float_from_state(state, "lig_legs", 2.0),
    )
    s_lig = _float_from_state(
        shear_updates or state,
        "s_lig",
        _float_from_state(state, "s_lig", 200.0),
    )

    kv_method = str(state.get("k_v_method", "General εx-based (Cl. 8.2.4.2)") or "General εx-based (Cl. 8.2.4.2)")
    use_general_kv = ("8.2.4.2" in kv_method) or ("ε" in kv_method) or ("ex" in kv_method.lower())

    kd_option_selected = str(state.get("k_d_option", "None (no ducts in web)") or "None (no ducts in web)")
    kd_value_map = {
        "None (no ducts in web)": 0.0,
        "0.5 – steel ducts, grouted": 0.5,
        "0.8 – plastic ducts, grouted": 0.8,
        "1.2 – ungrouted ducts": 1.2,
        "Prestressing ducts present (apply k_d)": 0.5,
    }
    k_d = float(kd_value_map.get(kd_option_selected, 0.0))
    sum_duct = _float_from_state(state, "n_ducts", 0.0) * _float_from_state(state, "duct_dia", 0.0)

    inp = ShearInputs(
        b=b,
        D=D,
        d=bottom_state["d_centroid"],
        fc=fc,
        fsy=fsy,
        Ec=Ec,
        Es=Es,
        M_star=_uls_action_from_state(state, "M"),
        V_star=_uls_action_from_state(state, "V"),
        T_star=_uls_action_from_state(state, "T"),
        N_star=_uls_action_from_state(state, "N"),
        P_v=_uls_action_from_state(state, "P"),
        phi=phi,
        sigma_cp=0.0,
        A_st=bottom_state["Ast_bot"],
        A_pt=0.0,
        f_po=0.0,
        A_ct=_float_from_state(state, "A_ct_default", b * D / 2.0),
        d_g=d_g,
        lig_d=lig_d,
        legs=lig_legs,
        s_lig=s_lig,
        use_general_kv=use_general_kv,
        sum_duct=sum_duct,
        k_d=k_d,
    )
    res = run_shear_calc(inp)
    util = (res.V_eq / res.phi_Vu) if res.phi_Vu > 0 else float("inf")
    phi_vu_max = phi * res.Vu_max_kN
    web_util = (res.V_eq / phi_vu_max) if phi_vu_max > 0 else float("inf")
    return {
        "results": res,
        "util": util,
        "web_util": web_util,
        "lig_d": lig_d,
        "lig_legs": int(lig_legs),
        "s_lig": s_lig,
    }


def _shear_results_allow_no_transverse_links(res, *, phi: float) -> bool:
    """
    True only if the member may omit closed shear links: no torsion design, concrete carries V*,
    and factored shear is low enough that minimum shear reinforcement is not mandatory
    (V* <= 0.5 φ Vuc per typical AS 3600 detailing practice).
    """
    if res is None:
        return False
    if bool(getattr(res, "torsion_required", True)):
        return False
    if not bool(getattr(res, "shear_ok", False)):
        return False
    veq = float(getattr(res, "V_eq", 0.0) or 0.0)
    vuc = float(getattr(res, "Vuc_kN", 0.0) or 0.0)
    phi_f = float(phi)
    if vuc <= 1e-12:
        return abs(veq) <= 1e-6
    if veq > 0.5 * phi_f * vuc + 1e-6:
        return False
    return True


def _shear_state_eligible_for_no_links(state: dict) -> bool:
    """Pre-check on current geometry/actions before trying a zero–shear-link trial."""
    s_nom = float(max(_float_from_state(state, "s_lig", 200.0), 1.0))
    preview = _evaluate_shear_with_state(
        state,
        shear_updates={"lig_legs": 0, "lig_d": 0, "s_lig": s_nom},
    )
    if not preview:
        return False
    res = preview.get("results")
    phi = _float_from_state(state, "phi_shear", 0.75)
    return _shear_results_allow_no_transverse_links(res, phi=phi)


def _shear_no_links_candidate_passes_code(state: dict, candidate: dict | None) -> bool:
    """Re-validate zero-link candidate after full fast eval (torsion, strength, min-shear gate)."""
    if not candidate:
        return False
    cs = dict(candidate.get("state") or {})
    if _int_from_state(cs, "lig_legs", -1) != 0:
        return True
    s_nom = float(max(_float_from_state(cs, "s_lig", 1.0), 1.0))
    preview = _evaluate_shear_with_state(
        cs,
        shear_updates={"lig_legs": 0, "lig_d": 0, "s_lig": s_nom},
    )
    if not preview:
        return False
    res = preview.get("results")
    phi = _float_from_state(state, "phi_shear", 0.75)
    return _shear_results_allow_no_transverse_links(res, phi=phi)


def _effective_bottom_spacing(state: dict, bottom_updates: dict | None = None) -> float:
    from section_layout import compute_bar_layout_pure

    if bottom_updates:
        count_1 = int(bottom_updates.get("bot1_count", 0) or 0)
        dia = float(bottom_updates.get("db_bot_1", 0.0) or 0.0)
    else:
        count_1 = _int_from_state(state, "bot1_count", _int_from_state(state, "nb_bot", 0))
        dia = _float_from_state(state, "db_bot_1", _float_from_state(state, "db_bot", 0.0))
    if count_1 <= 1 or dia <= 0.0:
        return _float_from_state(state, "s_bot", 0.0)
    layout = compute_bar_layout_pure(
        b=_design_width_value(state),
        cover_side=_float_from_state(state, "cover_side", 40.0),
        nb_or_s=float(count_1),
        db=float(dia),
        s_min=max(float(dia), 25.0),
        rowgap=_float_from_state(state, "rowgap_bot", 60.0),
    )
    return float(layout.get("s_actual", _float_from_state(state, "s_bot", 0.0)) or 0.0)


def _compute_sls_outer_steel_stress_with_state(state: dict, *, bottom_updates: dict | None = None) -> float | None:
    bottom_state = _effective_bottom_design_state(state, bottom_updates)
    b = _design_width_value(state)
    D = _float_from_state(state, "D", 600.0)
    d = float(bottom_state.get("d_centroid", 0.0) or 0.0)
    Ast = float(bottom_state.get("Ast_bot", 0.0) or 0.0)
    Ec = _float_from_state(state, "Ec", 30000.0)
    Es = _float_from_state(state, "Es", 200000.0)
    Ms = _float_from_state(state, "sls_Mstar", _float_from_state(state, "uls_Mstar", 0.0))
    if not (b > 0.0 and D > 0.0 and d > 0.0 and Ast > 0.0 and Ec > 0.0 and Es > 0.0):
        return None
    n_as = (Es / Ec) * Ast
    if n_as <= 0.0:
        return None
    a_coeff = b / 2.0
    b_coeff = n_as
    c_coeff = -n_as * d
    discriminant = b_coeff**2 - 4.0 * a_coeff * c_coeff
    if discriminant >= 0.0 and a_coeff > 0.0:
        dn_sls = (-b_coeff + math.sqrt(discriminant)) / (2.0 * a_coeff)
        dn_sls = max(1.0, min(dn_sls, D))
    else:
        dn_sls = d / 2.0
    i_cr = (b * dn_sls**3 / 3.0) + n_as * (d - dn_sls) ** 2
    if i_cr <= 0.0:
        return None
    kappa = (Ms * 1e6) / (Ec * i_cr)
    return float(Es * kappa * (d - dn_sls))


def _evaluate_crack_with_state(state: dict, *, bottom_updates: dict | None = None) -> dict | None:
    from crack_page import table_sigma_max_A, table_sigma_max_B, calc_eps_diff, calc_sr_max

    bottom_state = _effective_bottom_design_state(state, bottom_updates)
    sigma_sr = _compute_sls_outer_steel_stress_with_state(state, bottom_updates=bottom_updates)
    db = float(bottom_state.get("db_bot", 0.0) or 0.0)
    ast = float(bottom_state.get("Ast_bot", 0.0) or 0.0)
    b = _float_from_state(state, "b_crack", _design_width_value(state))
    D = _float_from_state(state, "D", 600.0)
    cover_bot = _float_from_state(state, "cover_bot", 40.0)
    spacing = _effective_bottom_spacing(state, bottom_updates=bottom_updates)
    fc = _float_from_state(state, "fc", 32.0)
    Ec = _float_from_state(state, "Ec", 30000.0)
    Es = _float_from_state(state, "Es", 200000.0)
    fsy = _float_from_state(state, "fsy", 500.0)
    phi_ce = _float_from_state(state, "phi_cc_t", 2.0)
    eps_cs = _float_from_state(state, "eps_cs_total_micro", 300.0) * 1e-6
    wmax_choice = _float_from_state(state, "wmax_char_limit", 0.3)
    member_type = str(state.get("crack_member_type", "Primarily flexure") or "Primarily flexure")
    k1 = _float_from_state(state, "crack_k1", 0.8)
    k2 = _float_from_state(state, "crk_k2", _float_from_state(state, "crack_k2", 0.5))
    if sigma_sr is None or db <= 0.0 or ast <= 0.0 or b <= 0.0 or D <= 0.0 or wmax_choice <= 0.0:
        return None
    d_eff = D - cover_bot - db / 2.0
    height_eff = min(2.5 * cover_bot, max(D - d_eff, 0.0), D / 2.0)
    a_ceff = b * max(height_eff, 1.0)
    rho_eff = ast / a_ceff if a_ceff > 0.0 else 0.0
    sigma_table_a = table_sigma_max_A(db, wmax_choice)
    sigma_table_b = table_sigma_max_B(max(spacing, 1.0), wmax_choice)
    sigma_table_combined = sigma_table_a if member_type == "Primarily tension" else max(sigma_table_a, sigma_table_b)
    sigma_allow_table = min(sigma_table_combined, 0.8 * fsy)
    util_table = sigma_sr / sigma_allow_table if sigma_allow_table > 0.0 else 0.0
    fct_eff = 0.6 * math.sqrt(max(fc, 1.0))
    n_e = (1.0 + phi_ce) * Es / Ec if Ec > 0.0 else 0.0
    eps_diff = calc_eps_diff(
        sigma_sr=sigma_sr,
        Es=Es,
        fct_eff=fct_eff,
        rho_eff=rho_eff,
        ne=n_e,
        eps_cs=eps_cs,
    )
    sr_max = calc_sr_max(c_mm=cover_bot, db_mm=db, rho_eff=rho_eff, k1=k1, k2=k2)
    w_calc = sr_max * eps_diff
    util_w = w_calc / wmax_choice if wmax_choice > 0.0 else 0.0
    util = max(util_table, util_w)
    return {
        "sigma_sr": float(sigma_sr),
        "sigma_allow_table": float(sigma_allow_table),
        "w_calc": float(w_calc),
        "util": float(util),
        "passes": bool(util <= 1.0),
    }


def _evaluate_deflection_with_state(state: dict, *, bottom_updates: dict | None = None) -> dict | None:
    from deflection import (
        _derive_equiv_udl_from_actions,
        calc_ief_simplified,
        calc_deflection_as3600,
        get_resolved_deflection_support_type,
    )

    bottom_state = _effective_bottom_design_state(state, bottom_updates)
    b = _design_width_value(state)
    fc = _float_from_state(state, "fc", 32.0)
    Ec = _float_from_state(state, "Ec", 30000.0)
    Ast = float(bottom_state.get("Ast_bot", 0.0) or 0.0)
    Asc = _float_from_state(state, "Ast_top", 0.0)
    d = float(bottom_state.get("d_centroid", 0.0) or 0.0)
    beff = _float_from_state(state, "defl_beff", b)
    bw = _float_from_state(state, "defl_bw", b)
    psi_s = _float_from_state(state, "psi_udl", _float_from_state(state, "psi_s", _float_from_state(state, "defl_psi_s", 0.4)))
    defl_limit_ratio = _float_from_state(state, "defl_limit_ratio", 250.0)
    g_udl = _float_from_state(state, "g_udl_kNm_per_m", _float_from_state(state, "g_kNm", _float_from_state(state, "g_line_kNm", 0.0)))
    q_udl = _float_from_state(state, "q_udl_kNm_per_m", _float_from_state(state, "q_kNm", _float_from_state(state, "q_line_kNm", 0.0)))
    w_sls = _float_from_state(state, "w_sls_kNm_per_m", 0.0)
    sls_Mstar = state.get("sls_Mstar")
    sls_Vstar = state.get("sls_Vstar")
    # Support resolution uses live session (SFD / actions_mode), not the local candidate dict.
    support_type = get_resolved_deflection_support_type(st.session_state)

    L_m = _float_from_state(state, "defl_L_eff", 0.0)
    if L_m <= 0.0:
        L_m = _float_from_state(state, "span_L_m", _float_from_state(state, "L_m", 0.0))
    if L_m <= 0.0:
        L_mm = _float_from_state(state, "L", 0.0)
        if L_mm > 0.0:
            L_m = L_mm / 1000.0

    if not (b > 0.0 and fc > 0.0 and Ec > 0.0 and Ast > 0.0 and d > 0.0 and L_m > 0.0):
        return None

    ief, _, _, _, _, _ = calc_ief_simplified(fc, max(beff, b), max(bw, min(bw, b) if bw > 0 else b), d, Ast)
    derived = _derive_equiv_udl_from_actions(
        M_kNm=None if sls_Mstar is None else float(sls_Mstar),
        V_kN=None if sls_Vstar is None else float(sls_Vstar),
        L_m=L_m,
        support_type=support_type,
    )
    if derived.get("w_kN_per_m") is not None:
        w_used = float(derived.get("w_kN_per_m") or 0.0)
    elif w_sls > 0.0:
        w_used = float(w_sls)
    else:
        w_used = float(g_udl + q_udl)

    if w_used > 0.0 and (g_udl + q_udl) > 0.0:
        g_ratio = float(g_udl) / float(g_udl + q_udl)
        g_equiv = w_used * g_ratio
        q_equiv = w_used * (1.0 - g_ratio)
    else:
        g_equiv = float(g_udl)
        q_equiv = float(q_udl if w_used <= 0.0 else 0.0)

    results = calc_deflection_as3600(
        L_m=L_m,
        Ec=Ec,
        Ief=ief,
        g_kNm=g_equiv,
        q_kNm=q_equiv,
        psi_s=psi_s,
        support_type=support_type,
        Ast=Ast,
        Asc=Asc,
    )
    if not results or results.get("ok") is False:
        return None

    L_mm = float(results.get("L_mm", L_m * 1000.0) or (L_m * 1000.0))
    defl_limit = (L_mm / defl_limit_ratio) if defl_limit_ratio > 0.0 else 0.0
    util = (float(results.get("delta_total", 0.0) or 0.0) / defl_limit) if defl_limit > 0.0 else None
    status = _status_from_candidate_util(util)
    return {
        "delta_total": float(results.get("delta_total", 0.0) or 0.0),
        "defl_limit": float(defl_limit),
        "util": None if util is None else float(util),
        "status": status,
        "passes": bool(util is not None and util <= 1.0),
        "pack": {
            "summary_delta_total_mm": float(results.get("delta_total", 0.0) or 0.0),
            "summary_defl_limit_mm": float(defl_limit),
            "summary_util_total": None if util is None else float(util),
            "rows": [{
                "uid": "defl_total",
                "title": "Total deflection (short + long-term)",
                "value": f"δtotal = {float(results.get('delta_total', 0.0) or 0.0):.2f} mm",
                "limit": f"δlim = {float(defl_limit):.2f} mm" if defl_limit > 0.0 else "—",
                "util": "—" if util is None else f"{float(util):.2f}",
                "status": status,
                "ok": None if util is None else bool(util <= 1.0),
                "route_page": "deflection",
                "tab": "Long-term deflection",
                "is_primary": True,
            }],
        },
    }


def _practical_bottom_reo_label(count_1: int, count_2: int, dia: int) -> str:
    if count_2 > 0:
        return f"{count_1}N{dia} + {count_2}N{dia}"
    return f"{count_1}N{dia}"


def _normalise_bottom_layer_order(arrangement: dict) -> dict:
    normalised = dict(arrangement)
    bot1_count = int(normalised.get("bot1_count", 0) or 0)
    bot2_count = int(normalised.get("bot2_count", 0) or 0)
    db1 = int(normalised.get("db_bot_1", 0) or 0)
    db2 = int(normalised.get("db_bot_2", 0) or 0)

    layer2_is_preferred = False
    if db2 > db1:
        layer2_is_preferred = True
    elif db2 == db1 and bot2_count > bot1_count:
        layer2_is_preferred = True

    if layer2_is_preferred:
        normalised["bot1_layout_mode"], normalised["bot2_layout_mode"] = (
            normalised.get("bot2_layout_mode", "Count"),
            normalised.get("bot1_layout_mode", "Count"),
        )
        normalised["bot1_count"], normalised["bot2_count"] = bot2_count, bot1_count
        normalised["db_bot_1"], normalised["db_bot_2"] = db2, db1
    return normalised


def _shear_preview_for_updates(state: dict, shear_updates: dict) -> dict | None:
    from shear_checks_helpers import build_shear_check_rows_from_state

    preview_state = _guidance_state_snapshot(state)
    preview_state.update(shear_updates)
    pack = build_shear_check_rows_from_state(preview_state)
    if not pack:
        return None

    web_util = float("inf")
    for row in pack.get("rows", []):
        if row.get("title") == "Web-crushing strength":
            try:
                web_util = float(row.get("util"))
            except Exception:
                web_util = float("inf")
            break

    util = pack.get("summary_util")
    try:
        util = float(util)
    except Exception:
        util = float("inf")

    return {
        "util": util,
        "web_util": web_util,
        "phi_vu": float(pack.get("summary_phiVu_kN", 0.0) or 0.0),
        "veq": float(pack.get("summary_Veq_kN", 0.0) or 0.0),
        "rows": pack.get("rows", []),
    }


def _required_ast_for_arrangement(state: dict, arrangement: dict) -> float:
    from bending_core import _get_compute_bending_capacity_pure

    b = _design_width_value(state)
    D = _float_from_state(state, "D", 600.0)
    fc = _float_from_state(state, "fc", 40.0)
    fsy = _float_from_state(state, "fsy", 500.0)
    phi = _float_from_state(state, "phi_bend", 0.85)
    Mu_star = _uls_action_from_state(state, "M")
    cover_bot = _float_from_state(state, "cover_bot", 40.0)
    rowgap_bot = _float_from_state(state, "rowgap_bot", 60.0)

    compute_fn = _get_compute_bending_capacity_pure()
    low = 0.0
    high = float(arrangement["Ast_bot"])
    for _ in range(40):
        trial = 0.5 * (low + high)
        trial_results = compute_fn(
            b=b,
            D=D,
            fc=fc,
            fsy=fsy,
            Ast=trial,
            Mu_star=Mu_star,
            phi=phi,
            d_input=arrangement["d_centroid"],
            cover_bot=cover_bot,
            db_bot=arrangement["db_bot"],
            nb_bot=arrangement["nb_bot"],
            rowgap_bot=rowgap_bot,
        )
        util = float(trial_results.get("Mu_util", float("inf")))
        if util <= 1.0:
            high = trial
        else:
            low = trial
    return float(high)


def _bottom_row_count_from_state(state: dict) -> int:
    explicit = _int_from_state(state, "bot_row_count", 0)
    if explicit > 0:
        return explicit
    return 2 if _int_from_state(state, "bot2_count", 0) > 0 else 1


def _bottom_bar_count_from_state(state: dict, bottom_state: dict | None = None) -> int:
    resolved = bottom_state or _effective_bottom_design_state(state)
    count = int(resolved.get("nb_bot", 0) or 0)
    if count > 0:
        return count
    return _int_from_state(state, "bot1_count", 0) + _int_from_state(state, "bot2_count", 0)


def _reo_congestion_index(state: dict, bottom_state: dict | None = None) -> float:
    resolved = bottom_state or _effective_bottom_design_state(state)
    total_bars = _bottom_bar_count_from_state(state, resolved)
    row_count = max(_bottom_row_count_from_state(state), 1)
    bar_dia = float(resolved.get("db_bot", 0.0) or _float_from_state(state, "db_bot_1", 0.0))
    width = max(_design_width_value(state), 1.0)
    rows_penalty = max(row_count - 1, 0) * 2.5
    density_penalty = (total_bars * max(bar_dia, 1.0)) / width
    return float(total_bars + rows_penalty + density_penalty)


def _status_from_candidate_util(util: float | None) -> str:
    if util is None or (isinstance(util, float) and math.isnan(util)):
        return "—"
    if util <= 1.0:
        return "NEAR LIMIT" if util >= 0.95 else "PASS"
    return "FAIL"


def _candidate_bottom_updates(candidate_state: dict) -> dict | None:
    db_1 = _int_from_state(candidate_state, "db_bot_1", 0)
    count_1 = _int_from_state(candidate_state, "bot1_count", 0)
    count_2 = _int_from_state(candidate_state, "bot2_count", 0)
    if db_1 <= 0 or (count_1 + count_2) <= 0:
        return None
    return {
        "db_bot_1": db_1,
        "db_bot_2": _int_from_state(candidate_state, "db_bot_2", db_1),
        "bot1_count": count_1,
        "bot2_count": count_2,
    }


def _candidate_shear_updates(candidate_state: dict) -> dict:
    return {
        "lig_d": _int_from_state(candidate_state, "lig_d", 10),
        "lig_legs": _int_from_state(candidate_state, "lig_legs", 2),
        "s_lig": _float_from_state(candidate_state, "s_lig", 200.0),
    }


def _shear_reinforcement_is_active(state: dict | None) -> bool:
    if not isinstance(state, dict):
        return False
    return (
        _int_from_state(state, "lig_legs", 0) >= 2
        and _int_from_state(state, "lig_d", 0) > 0
        and _float_from_state(state, "s_lig", 0.0) > 0.0
    )


def _starter_shear_diameter(state: dict) -> int:
    current_dia = _int_from_state(state, "lig_d", 0)
    if current_dia > 0:
        return int(current_dia)
    practical_dias = [dia for dia in REO_BAR_DIAS if dia <= 16]
    return int(practical_dias[0] if practical_dias else 10)


def _starter_shear_spacing(state: dict) -> float:
    current_spacing = _float_from_state(state, "s_lig", 0.0)
    if current_spacing > 0.0 and REO_SPACINGS:
        return float(min(REO_SPACINGS, key=lambda value: abs(float(value) - current_spacing)))
    if 200 in REO_SPACINGS:
        return 200.0
    return float(REO_SPACINGS[min(len(REO_SPACINGS) - 1, len(REO_SPACINGS) // 2)] if REO_SPACINGS else 200.0)


def _activation_shear_state(state: dict) -> dict:
    activated = dict(state)
    activated.update({
        "lig_legs": 2,
        "lig_d": int(_starter_shear_diameter(state)),
        "s_lig": float(_starter_shear_spacing(state)),
    })
    return activated


def _normalise_invalid_shear_state_updates(
    base_state: dict,
    updates: dict,
    *,
    source: str,
) -> dict:
    resolved_state = dict(base_state or {})
    normalised_updates = dict(updates or {})
    resolved_state.update(normalised_updates)
    lig_legs = _int_from_state(resolved_state, "lig_legs", 0)
    lig_d = _int_from_state(resolved_state, "lig_d", 0)
    if lig_legs >= 2 and lig_d <= 0:
        starter_dia = int(_starter_shear_diameter(resolved_state))
        _agent_debug_log(
            "Invalid shear state: ligatures active but lig_d <= 0",
            {
                "source": source,
                "lig_legs": lig_legs,
                "lig_d_before": lig_d,
                "lig_d_after": starter_dia,
                "s_lig": _float_from_state(resolved_state, "s_lig", 0.0),
            },
            location="inputs_page.py:shear_state_normalisation",
            hypothesis_id="H_SHEAR_INVALID",
        )
        if bool(st.session_state.get("_dev_mode")):
            assert starter_dia > 0, "Invalid shear state: ligatures active but diameter is zero"
        normalised_updates["lig_d"] = starter_dia
    s_lig = _float_from_state(resolved_state, "s_lig", 0.0)
    if lig_legs >= 2 and s_lig <= 0.0:
        starter_spacing = float(_starter_shear_spacing(resolved_state))
        normalised_updates["s_lig"] = starter_spacing
    return normalised_updates


def _normalise_invalid_shear_state_in_shared(*, source: str) -> bool:
    current_state = _shared_state_snapshot()
    normalised_updates = _normalise_invalid_shear_state_updates(current_state, {}, source=source)
    if not normalised_updates:
        return False
    for shared_key, value in normalised_updates.items():
        set_shared(shared_key, value, source=source)
    return True


def _refresh_canonical_shear_widgets(*, source: str) -> None:
    shared_state = _shared_state_snapshot()
    widget_map = {
        get_widget_key_for_shared("lig_d", prefix="inputs_") or "inputs_lig_d": int(shared_state.get("lig_d", 0) or 0),
        get_widget_key_for_shared("lig_legs", prefix="inputs_") or "inputs_lig_legs": int(shared_state.get("lig_legs", 0) or 0),
        get_widget_key_for_shared("s_lig", prefix="inputs_") or "inputs_s_lig": float(shared_state.get("s_lig", 0.0) or 0.0),
    }
    hydrated_map = st.session_state.get("_hydrated_from_shared_map")
    for widget_key, value in widget_map.items():
        st.session_state[widget_key] = value
        st.session_state[f"_cached_{widget_key}"] = value
        if isinstance(hydrated_map, dict):
            hydrated_map[widget_key] = value
    st.session_state["_force_inputs_widget_reseed_once"] = True
    if bool(st.session_state.get("_dev_mode")):
        _agent_debug_log(
            "Refreshed canonical shear widgets from shared state",
            {
                "source": source,
                "widget_values": widget_map,
            },
            location="inputs_page.py:_refresh_canonical_shear_widgets",
            hypothesis_id="H_SHEAR_WIDGET",
        )


def _invalid_shear_spacing_change_without_activation(
    base_state: dict,
    candidate_state: dict,
    *,
    source: str,
) -> bool:
    if _shear_reinforcement_is_active(base_state):
        return False
    spacing_before = _float_from_state(base_state, "s_lig", 0.0)
    spacing_after = _float_from_state(candidate_state, "s_lig", spacing_before)
    candidate_legs = _int_from_state(candidate_state, "lig_legs", 0)
    if candidate_legs >= 2 or abs(spacing_after - spacing_before) <= 1e-9:
        return False
    _agent_debug_log(
        "Invalid shear candidate: spacing changed without activating stirrups",
        {
            "source": source,
            "lig_legs": candidate_legs,
            "lig_d": _int_from_state(candidate_state, "lig_d", 0),
            "s_lig": spacing_after,
            "shear_reinforcement_active": False,
        },
        location="inputs_page.py:shear_activation_guard",
        hypothesis_id="H_SHEAR_INVALID",
    )
    return True


def _log_shear_candidate_debug(
    *,
    source: str,
    candidate_state: dict,
    candidate: dict | None,
) -> None:
    if not bool(st.session_state.get("_dev_mode")):
        return
    shear_preview = _evaluate_shear_with_state(candidate_state) or {}
    phi_vu = 0.0
    veq = 0.0
    try:
        results = shear_preview.get("results")
        phi_vu = float(getattr(results, "phi_Vu", 0.0) or 0.0)
        veq = float(getattr(results, "V_eq", 0.0) or 0.0)
    except Exception:
        phi_vu = 0.0
        veq = 0.0
    _agent_debug_log(
        "Shear candidate debug",
        {
            "source": source,
            "lig_legs": _int_from_state(candidate_state, "lig_legs", 0),
            "lig_d": _int_from_state(candidate_state, "lig_d", 0),
            "s_lig": _float_from_state(candidate_state, "s_lig", 0.0),
            "shear_reinforcement_active": _shear_reinforcement_is_active(candidate_state),
            "phiVu": phi_vu,
            "Veq": veq,
            "shear_util": float(shear_preview.get("util", 0.0) or 0.0) if shear_preview else None,
            "candidate_score": None if candidate is None else candidate.get("score"),
        },
        location="inputs_page.py:shear_candidate_debug",
        hypothesis_id="H_SHEAR_DEBUG",
    )


def _shear_severity_band(util: float | None) -> str:
    if util is None:
        return "mild"
    value = float(util)
    if value < 1.15:
        return "mild"
    if value < 1.75:
        return "moderate"
    if value < 3.0:
        return "severe"
    return "extreme"


def _severe_shear_failure(util: float | None) -> bool:
    return _shear_severity_band(util) in ("severe", "extreme")


def _candidate_bending_reserve_util(candidate: dict | None) -> float | None:
    if not candidate:
        return None
    util = _candidate_bending_demand_util(candidate)
    if util is not None:
        return float(util)
    raw = ((candidate.get("overview") or {}).get("utils") or {}).get("bending")
    if raw is None:
        return None
    try:
        value = float(raw)
    except Exception:
        return None
    return None if math.isnan(value) else value


def _secondary_action_reserves(candidate: dict | None) -> dict:
    reserves: dict[str, dict] = {}
    bending_util = _candidate_bending_reserve_util(candidate)
    if bending_util is not None and bending_util <= GUIDANCE_INEFFICIENT_UTIL_THRESHOLD:
        reserves["bending"] = {
            "util": bending_util,
            "bottom_reo": _bottom_reo_state_label(dict((candidate or {}).get("state") or {})),
            "phiMu": (((candidate or {}).get("overview") or {}).get("packs") or {}).get("bending", {}).get("summary_phiMu_kNm"),
            "Mu_star": (((candidate or {}).get("overview") or {}).get("packs") or {}).get("bending", {}).get("summary_Mu_star_kNm"),
        }
    return reserves


def _shear_candidate_type(base_state: dict, candidate_state: dict) -> str:
    width_key, _, current_width = _resolve_geometry_width_context(base_state)
    current_depth = _float_from_state(base_state, "D", 0.0)
    next_width = _float_from_state(candidate_state, width_key, current_width)
    next_depth = _float_from_state(candidate_state, "D", current_depth)
    width_changed = abs(next_width - current_width) > 1e-9
    depth_changed = abs(next_depth - current_depth) > 1e-9
    current_spacing = _float_from_state(base_state, "s_lig", 0.0)
    next_spacing = _float_from_state(candidate_state, "s_lig", current_spacing)
    current_legs = _int_from_state(base_state, "lig_legs", 0)
    next_legs = _int_from_state(candidate_state, "lig_legs", current_legs)
    current_dia = _int_from_state(base_state, "lig_d", 0)
    next_dia = _int_from_state(candidate_state, "lig_d", current_dia)
    if next_legs == 0 and current_legs > 0:
        return "no shear links"
    spacing_tighter = next_spacing < current_spacing - 1e-9
    legs_increased = next_legs > current_legs
    dia_increased = next_dia > current_dia
    if (width_changed or depth_changed) and (spacing_tighter or legs_increased or dia_increased):
        return "combined"
    if depth_changed:
        return "depth increase"
    if width_changed:
        return "width increase"
    if dia_increased and not spacing_tighter and not legs_increased:
        return "larger dia"
    if legs_increased and not spacing_tighter:
        return "more legs"
    if spacing_tighter:
        return "spacing"
    if dia_increased:
        return "larger dia"
    if legs_increased:
        return "more legs"
    return "spacing"


def _generate_secondary_bending_tightening_states(base_candidate: dict, *, limit: int = 3) -> list[dict]:
    bending_util = _candidate_bending_reserve_util(base_candidate)
    if bending_util is None or bending_util > GUIDANCE_INEFFICIENT_UTIL_THRESHOLD:
        return []
    base_state = dict(base_candidate.get("state") or {})
    if not base_state:
        return []
    current_ast = float(base_candidate.get("Ast_bot", 0.0) or 0.0)
    low_reo_mode = _design_mode_config("less_longitudinal_reinforcement")
    context = _build_auto_design_context(
        base_state,
        low_reo_mode,
        reference_overview=base_candidate.get("overview"),
    )
    states: dict[tuple, dict] = {}
    raw_limit = max(limit * 2, 6)
    for band in range(2):
        for arrangement in _generate_local_bottom_arrangements(
            base_state,
            low_reo_mode,
            band=band,
            context=context,
            limit=raw_limit,
        ):
            candidate_state = dict(base_state)
            candidate_state.update(_bottom_arrangement_to_shared_updates(arrangement))
            preview_bottom = _effective_bottom_design_state(candidate_state, _candidate_bottom_updates(candidate_state))
            if float(preview_bottom.get("Ast_bot", 0.0) or 0.0) >= current_ast - 1e-6:
                continue
            states[_make_auto_design_candidate_key(candidate_state)] = candidate_state
    ordered_states = sorted(
        states.values(),
        key=lambda item: (
            abs(float((_evaluate_bending_with_bottom_state(item, _candidate_bottom_updates(item)) or {}).get("Mu_util", 999.0) or 999.0) - 0.85),
            float(_effective_bottom_design_state(item, _candidate_bottom_updates(item)).get("Ast_bot", 0.0) or 0.0),
        ),
    )
    return ordered_states[:limit]


def _generate_escalated_shear_states(state: dict, *, severity_band: str) -> list[tuple[str, dict]]:
    base_state = _activation_shear_state(state) if not _shear_reinforcement_is_active(state) else dict(state)
    current_spacing = _int_from_state(base_state, "s_lig", 200)
    current_legs = max(_int_from_state(base_state, "lig_legs", 2), 2)
    current_dia = max(_int_from_state(base_state, "lig_d", 10), 10)
    width_key, _, current_width = _resolve_geometry_width_context(base_state)
    current_depth = _float_from_state(base_state, "D", 600.0)
    max_legs = 10 if severity_band == "extreme" else 8
    max_dia = 24 if severity_band == "extreme" else 20
    leg_values = sorted(set([current_legs, min(current_legs + 2, max_legs), min(current_legs + 4, max_legs)]))
    dia_values = sorted(set([dia for dia in REO_BAR_DIAS if current_dia <= dia <= max_dia] + [current_dia]))
    spacing_targets = [value for value in REO_SPACINGS if value <= current_spacing]
    spacing_values = sorted(set(spacing_targets[:3] + [current_spacing])) or [current_spacing]
    width_steps = [current_width + 50.0, current_width + 100.0]
    depth_steps = [current_depth + 50.0, current_depth + 100.0]
    if severity_band == "extreme":
        width_steps.append(current_width + 150.0)
        depth_steps.append(current_depth + 150.0)

    generated: dict[tuple, tuple[str, dict]] = {}

    def _store(candidate_state: dict) -> None:
        key = _make_auto_design_candidate_key(candidate_state)
        generated[key] = (_shear_candidate_type(state, candidate_state), candidate_state)

    for spacing in spacing_values:
        for legs in leg_values:
            for dia in dia_values:
                candidate_state = dict(base_state)
                candidate_state.update({
                    "lig_d": int(dia),
                    "lig_legs": int(legs),
                    "s_lig": float(spacing),
                })
                _store(candidate_state)

    if not _geometry_lock_enabled(state):
        for width in width_steps:
            candidate_state = dict(base_state)
            candidate_state[width_key] = float(width)
            if width_key != "b":
                candidate_state["b"] = float(width)
            _store(candidate_state)
        for depth in depth_steps:
            candidate_state = dict(base_state)
            candidate_state["D"] = float(depth)
            _store(candidate_state)
        strong_spacing = float(min(spacing_values)) if spacing_values else float(current_spacing)
        strong_legs = int(max(leg_values))
        strong_dia = int(max(dia_values))
        for width in width_steps:
            for depth in depth_steps:
                candidate_state = dict(base_state)
                candidate_state.update({
                    width_key: float(width),
                    "D": float(depth),
                    "lig_d": strong_dia,
                    "lig_legs": strong_legs,
                    "s_lig": strong_spacing,
                })
                if width_key != "b":
                    candidate_state["b"] = float(width)
                _store(candidate_state)

    return list(generated.values())


def _shear_recommendation_rank_key(
    candidate: dict,
    *,
    base_state: dict,
    severity_band: str,
    seed_shear_util: float | None,
) -> tuple:
    candidate_state = dict(candidate.get("state") or {})
    candidate_type = _shear_candidate_type(base_state, candidate_state)
    rank_components = _shear_rank_component_breakdown(
        candidate,
        base_state=base_state,
        severity_band=severity_band,
        seed_shear_util=seed_shear_util,
    )
    resolved_util = float(rank_components.get("resolved_shear_util", float("inf")) or float("inf"))
    bending_util = _candidate_bending_reserve_util(candidate)
    bending_distance = abs(float(bending_util) - 0.85) if bending_util is not None else float("inf")
    ast_bot = float(candidate.get("Ast_bot", 0.0) or 0.0)
    severe_complexity_order = {
        "more legs": 0,
        "larger dia": 0,
        "width increase": 1,
        "depth increase": 1,
        "combined": 2,
        "spacing": 3,
    }
    soft_goal_bias = 0
    if _severe_shear_failure(seed_shear_util):
        goal = _design_optimisation_goal(candidate_state)
        if goal == "shallower_beam" and candidate_type == "depth increase":
            soft_goal_bias = 1
        elif goal == "less_shear_reinforcement" and candidate_type in {"more legs", "larger dia", "spacing"}:
            soft_goal_bias = 1
    secondary_combined_bonus = 0 if bool(candidate.get("secondary_actions_combined")) else 1
    return (
        int(rank_components.get("primary_shear_recovery_contribution", 999) or 999),
        resolved_util,
        secondary_combined_bonus if resolved_util <= 1.05 else 1,
        bending_distance,
        ast_bot,
        severe_complexity_order.get(candidate_type, 4) if _severe_shear_failure(seed_shear_util) else 0,
        soft_goal_bias,
        float(candidate.get("score", float("inf")) or float("inf")),
        float(candidate.get("depth", 0.0) or 0.0),
        float(candidate.get("width", 0.0) or 0.0),
    )


def _shear_family_label(candidate_type: str, candidate: dict | None, *, seed_candidate: dict | None = None) -> str:
    mapping = {
        "spacing": "spacing tighter",
        "more legs": "more legs",
        "larger dia": "larger link dia",
        "width increase": "width increase",
        "depth increase": "depth increase",
        "combined": "combined geometry + stronger shear",
    }
    label = mapping.get(str(candidate_type or ""), str(candidate_type or "spacing tighter"))
    if str(candidate_type or "") == "combined" and candidate and seed_candidate:
        candidate_state = dict(candidate.get("state") or {})
        seed_state = dict(seed_candidate.get("state") or {})
        candidate_ast = float(candidate.get("Ast_bot", 0.0) or 0.0)
        seed_ast = float(seed_candidate.get("Ast_bot", 0.0) or 0.0)
        width_key, _, seed_width = _resolve_geometry_width_context(seed_state)
        candidate_width = _float_from_state(candidate_state, width_key, seed_width)
        seed_depth = _float_from_state(seed_state, "D", 0.0)
        candidate_depth = _float_from_state(candidate_state, "D", seed_depth)
        if candidate_ast < seed_ast - 1e-6:
            if abs(candidate_width - seed_width) > 1e-9 or abs(candidate_depth - seed_depth) > 1e-9:
                label = "combined geometry + lighter bottom reo"
            else:
                label = "combined shear + lighter bottom reo"
    elif candidate and seed_candidate:
        candidate_state = dict(candidate.get("state") or {})
        seed_state = dict(seed_candidate.get("state") or {})
        width_key, _, seed_width = _resolve_geometry_width_context(seed_state)
        candidate_width = _float_from_state(candidate_state, width_key, seed_width)
        seed_depth = _float_from_state(seed_state, "D", 0.0)
        candidate_depth = _float_from_state(candidate_state, "D", seed_depth)
        candidate_ast = float(candidate.get("Ast_bot", 0.0) or 0.0)
        seed_ast = float(seed_candidate.get("Ast_bot", 0.0) or 0.0)
        if (
            candidate_ast < seed_ast - 1e-6
            and (
                abs(candidate_width - seed_width) > 1e-9
                or abs(candidate_depth - seed_depth) > 1e-9
            )
        ):
            label = "combined geometry + lighter bottom reo"
    return label


def _shear_rank_component_breakdown(
    candidate: dict,
    *,
    base_state: dict,
    severity_band: str,
    seed_shear_util: float | None,
) -> dict:
    candidate_state = dict(candidate.get("state") or {})
    candidate_type = _shear_candidate_type(base_state, candidate_state)
    shear_preview = _evaluate_shear_with_state(candidate_state) or {}
    shear_util = candidate.get("overview", {}).get("utils", {}).get("shear")
    if shear_util is None:
        shear_util = shear_preview.get("util")
    try:
        resolved_util = float(shear_util)
    except Exception:
        resolved_util = float("inf")
    bending_util = _candidate_bending_reserve_util(candidate)
    bending_band_penalty = 0 if (bending_util is not None and 0.75 <= float(bending_util) <= 0.95) else 1
    bending_distance = abs(float(bending_util) - 0.85) if bending_util is not None else float("inf")
    ast_bot = float(candidate.get("Ast_bot", 0.0) or 0.0)
    improvement_ratio = resolved_util / max(float(seed_shear_util or resolved_util or 1.0), 1e-9)
    severe_type_order = {
        "combined": 1,
        "depth increase": 2,
        "width increase": 2,
        "larger dia": 1,
        "more legs": 1,
        "spacing": 0,
    }
    type_order = severe_type_order.get(candidate_type, 4)
    unresolved_penalty = (
        0 if resolved_util <= 1.00 else
        1 if resolved_util <= 1.05 else
        2 if resolved_util <= 1.15 else
        3 if resolved_util <= 1.35 else
        4 if resolved_util <= 1.75 else
        5
    )
    weak_spacing_penalty = 0
    if _severe_shear_failure(seed_shear_util):
        if candidate_type == "spacing" and (resolved_util > 1.10 or improvement_ratio > 0.55):
            weak_spacing_penalty = 4
        elif candidate_type in {"more legs", "larger dia"} and resolved_util > 1.35:
            weak_spacing_penalty = 1
    return {
        "primary_shear_recovery_contribution": unresolved_penalty + weak_spacing_penalty,
        "secondary_bending_efficiency_contribution": bending_band_penalty + bending_distance,
        "goal_bias_contribution": type_order if _severe_shear_failure(seed_shear_util) else 0,
        "severity_band": severity_band,
        "ast_bot_tiebreak": ast_bot,
        "resolved_shear_util": resolved_util,
        "improvement_ratio": improvement_ratio,
    }


def _shear_candidate_audit_entry(
    *,
    family: str,
    candidate_state: dict,
    candidate: dict | None,
    seed_candidate: dict,
    mode_config: dict,
    severity_band: str,
    seed_shear_util: float | None,
    candidate_source: str,
    selected: bool,
    reject_reason: str,
    survived_filters: bool = False,
) -> dict:
    shear_preview = _evaluate_shear_with_state(candidate_state) or {}
    overview = (candidate or {}).get("overview") or {}
    bending_pack = (overview.get("packs") or {}).get("bending") or {}
    score_components = dict((candidate or {}).get("_score_components") or {})
    rank_components = (
        _shear_rank_component_breakdown(
            candidate,
            base_state=seed_candidate.get("state") or {},
            severity_band=severity_band,
            seed_shear_util=seed_shear_util,
        )
        if candidate is not None else {}
    )
    material_complexity_penalty = (
        float(score_components.get("steel_penalty", 0.0) or 0.0)
        + float(score_components.get("congestion_penalty", 0.0) or 0.0)
        + float(score_components.get("row_penalty", 0.0) or 0.0)
        + float(score_components.get("shear_density_penalty", 0.0) or 0.0)
    )
    candidate_type = str(
        (candidate or {}).get("shear_candidate_type")
        or _shear_candidate_type(seed_candidate.get("state") or {}, candidate_state)
    )
    shear_util = float(shear_preview.get("util", 0.0) or 0.0) if shear_preview else None
    return {
        "family": family,
        "label": str((candidate or {}).get("label") or _shear_state_label(candidate_state)),
        "candidate_source": str(candidate_source or (candidate or {}).get("source") or ""),
        "candidate_type": candidate_type,
        "candidate_key": (
            _make_auto_design_candidate_key(dict((candidate or {}).get("state") or candidate_state))
            if candidate_state else None
        ),
        "b": _design_width_value(candidate_state),
        "D": _float_from_state(candidate_state, "D", 0.0),
        "lig_d": _int_from_state(candidate_state, "lig_d", 0),
        "lig_legs": _int_from_state(candidate_state, "lig_legs", 0),
        "s_lig": _float_from_state(candidate_state, "s_lig", 0.0),
        "bottom_reo_label": _bottom_reo_state_label(candidate_state),
        "phiVu": float(shear_preview.get("phi_vu", 0.0) or 0.0),
        "Veq": float(shear_preview.get("veq", 0.0) or 0.0),
        "shear_util": shear_util,
        "primary_failure_fixed": None if shear_util is None else bool(shear_util <= 1.0 + 1e-6),
        "phiMu": float(bending_pack.get("summary_phiMu_kNm", 0.0) or 0.0),
        "Mu_star": float(bending_pack.get("summary_Mu_star_kNm", 0.0) or 0.0),
        "bending_util": _candidate_bending_reserve_util(candidate) if candidate is not None else None,
        "score_total": None if candidate is None else float(candidate.get("score", 0.0) or 0.0),
        "score": None if candidate is None else float(candidate.get("score", 0.0) or 0.0),
        "survived_filters": bool(survived_filters),
        "selected": bool(selected),
        "reject_reason": str(reject_reason or ""),
        "score_components": {
            "primary_shear_recovery_contribution": rank_components.get("primary_shear_recovery_contribution"),
            "secondary_bending_efficiency_contribution": rank_components.get("secondary_bending_efficiency_contribution"),
            "geometry_penalty": score_components.get("geometry_penalty"),
            "goal_bias_adjustment": rank_components.get("goal_bias_contribution"),
            "material_complexity_penalty": material_complexity_penalty,
            "total_score": score_components.get("total_score", (candidate or {}).get("score")),
        },
    }


def _log_severe_shear_escalation(
    *,
    source: str,
    seed_candidate: dict,
    severity_band: str,
    candidates: list[dict],
    selected: dict | None,
    family_audit: dict[str, list[dict]] | None = None,
) -> None:
    if not bool(st.session_state.get("_dev_mode")):
        return
    audit = dict(family_audit or {})
    families = [
        "spacing tighter",
        "more legs",
        "larger link dia",
        "width increase",
        "depth increase",
        "combined geometry + stronger shear",
        "combined geometry + lighter bottom reo",
        "combined shear + lighter bottom reo",
    ]

    def _entry_order(item: dict) -> tuple:
        return (
            0 if bool(item.get("survived_filters")) else 1,
            0 if bool(item.get("selected")) else 1,
            float(item.get("score_total") if item.get("score_total") is not None else float("inf")),
            float(item.get("shear_util") if item.get("shear_util") is not None else float("inf")),
        )

    def _selection_reason_chain(selected_entry: dict | None, contender_entry: dict | None) -> str:
        if not selected_entry:
            return "no candidate selected"
        if contender_entry is None:
            return "selected candidate was the only ranked survivor"
        if selected_entry.get("candidate_key") == contender_entry.get("candidate_key"):
            return "selected as best candidate in its family and overall"
        reasons: list[str] = []
        selected_score = float(selected_entry.get("score_total") if selected_entry.get("score_total") is not None else float("inf"))
        contender_score = float(contender_entry.get("score_total") if contender_entry.get("score_total") is not None else float("inf"))
        reasons.append(f"score_total {selected_score:.2f} vs {contender_score:.2f}")
        selected_primary = float((((selected_entry.get("score_components") or {}).get("primary_shear_recovery_contribution")) or float("inf")))
        contender_primary = float((((contender_entry.get("score_components") or {}).get("primary_shear_recovery_contribution")) or float("inf")))
        if selected_primary != contender_primary:
            reasons.append(f"primary shear recovery {selected_primary:.2f} vs {contender_primary:.2f}")
        selected_secondary = float((((selected_entry.get("score_components") or {}).get("secondary_bending_efficiency_contribution")) or float("inf")))
        contender_secondary = float((((contender_entry.get("score_components") or {}).get("secondary_bending_efficiency_contribution")) or float("inf")))
        if selected_secondary != contender_secondary:
            reasons.append(f"secondary bending efficiency {selected_secondary:.2f} vs {contender_secondary:.2f}")
        selected_geometry = float((((selected_entry.get("score_components") or {}).get("geometry_penalty")) or 0.0))
        contender_geometry = float((((contender_entry.get("score_components") or {}).get("geometry_penalty")) or 0.0))
        if selected_geometry != contender_geometry:
            reasons.append(f"geometry penalty {selected_geometry:.2f} vs {contender_geometry:.2f}")
        selected_goal = float((((selected_entry.get("score_components") or {}).get("goal_bias_adjustment")) or 0.0))
        contender_goal = float((((contender_entry.get("score_components") or {}).get("goal_bias_adjustment")) or 0.0))
        if selected_goal != contender_goal:
            reasons.append(f"goal bias adjustment {selected_goal:.2f} vs {contender_goal:.2f}")
        selected_material = float((((selected_entry.get("score_components") or {}).get("material_complexity_penalty")) or 0.0))
        contender_material = float((((contender_entry.get("score_components") or {}).get("material_complexity_penalty")) or 0.0))
        if selected_material != contender_material:
            reasons.append(f"material/complexity penalty {selected_material:.2f} vs {contender_material:.2f}")
        return "; ".join(reasons)

    candidates_per_family = {}
    survivors_per_family = {}
    best_per_family = {}
    top_3_per_family = {}
    family_key_map = {
        "spacing tighter": "best_spacing_candidate",
        "more legs": "best_more_legs_candidate",
        "larger link dia": "best_larger_dia_candidate",
        "width increase": "best_width_candidate",
        "depth increase": "best_depth_candidate",
        "combined geometry + stronger shear": "best_combined_candidate",
        "combined geometry + lighter bottom reo": "best_combined_geometry_lighter_bottom_candidate",
        "combined shear + lighter bottom reo": "best_combined_shear_lighter_bottom_candidate",
    }
    for family in families:
        entries = list(audit.get(family, []))
        if not entries:
            continue
        ordered = sorted(entries, key=_entry_order)
        candidates_per_family[family] = len(entries)
        survivors_per_family[family] = sum(1 for entry in entries if bool(entry.get("survived_filters")))
        top_3_per_family[family] = {
            "family": family,
            "generated": len(entries),
            "survived": survivors_per_family[family],
            "top_candidates": ordered[:3],
        }
        best_per_family[family] = ordered[0]
    global_selected = next(
        (
            entry
            for family in families
            for entry in audit.get(family, [])
            if bool(entry.get("selected"))
        ),
        None,
    )
    family_comparison = {}
    for family, entry in best_per_family.items():
        family_comparison[family_key_map.get(family, f"best_{family}")] = {
            "label": entry.get("label"),
            "score": entry.get("score_total"),
            "shear_util": entry.get("shear_util"),
            "bending_util": entry.get("bending_util"),
            "b": entry.get("b"),
            "D": entry.get("D"),
            "lig_d": entry.get("lig_d"),
            "lig_legs": entry.get("lig_legs"),
            "s_lig": entry.get("s_lig"),
            "bottom_reo_label": entry.get("bottom_reo_label"),
            "reason": _selection_reason_chain(global_selected, entry),
        }
    losing_entries = [
        entry for family, entry in best_per_family.items()
        if not global_selected or entry.get("candidate_key") != global_selected.get("candidate_key")
    ]
    best_losing_entry = min(losing_entries, key=_entry_order) if losing_entries else None
    final_selected_reason = _selection_reason_chain(global_selected, best_losing_entry)
    _agent_debug_log(
        "Severe shear escalation candidates",
        {
            "source": source,
            "optimisation_goal": _design_optimisation_goal(seed_candidate.get("state") or {}),
            "geometry_lock": _geometry_lock_enabled(seed_candidate.get("state") or {}),
            "primary_action": "shear",
            "secondary_actions_with_reserve": _secondary_action_reserves(seed_candidate),
            "shear_utilisation": ((seed_candidate.get("overview") or {}).get("utils") or {}).get("shear"),
            "severity_band": severity_band,
            "total_candidates_generated": int(sum(candidates_per_family.values())),
            "candidates_generated_by_family": candidates_per_family,
            "total_candidates_survived": int(sum(survivors_per_family.values())),
            "candidates_survived_by_family": survivors_per_family,
            "combined_candidates_generated": bool(
                candidates_per_family.get("combined geometry + stronger shear")
                or candidates_per_family.get("combined geometry + lighter bottom reo")
                or candidates_per_family.get("combined shear + lighter bottom reo")
            ),
            "best_overall_candidate": global_selected,
            "best_candidate_per_family": best_per_family,
            "top_3_per_family": top_3_per_family,
            "family_comparison": {
                **family_comparison,
                "final_selected_candidate": None if global_selected is None else {
                    "label": global_selected.get("label"),
                    "score": global_selected.get("score_total"),
                    "shear_util": global_selected.get("shear_util"),
                    "bending_util": global_selected.get("bending_util"),
                    "b": global_selected.get("b"),
                    "D": global_selected.get("D"),
                    "lig_d": global_selected.get("lig_d"),
                    "lig_legs": global_selected.get("lig_legs"),
                    "s_lig": global_selected.get("s_lig"),
                    "bottom_reo_label": global_selected.get("bottom_reo_label"),
                    "reason": final_selected_reason,
                },
            },
            "final_selected_reason": final_selected_reason,
            "end_of_run_summary": {
                "optimisation_goal": _design_optimisation_goal(seed_candidate.get("state") or {}),
                "geometry_lock": _geometry_lock_enabled(seed_candidate.get("state") or {}),
                "primary_action": "shear",
                "secondary_actions_with_reserve": _secondary_action_reserves(seed_candidate),
                "severity_band": severity_band,
                "total_candidates_generated": int(sum(candidates_per_family.values())),
                "candidates_generated_by_family": candidates_per_family,
                "total_candidates_survived": int(sum(survivors_per_family.values())),
                "final_selected_family": None if global_selected is None else global_selected.get("family"),
                "final_selected_label": None if global_selected is None else global_selected.get("label"),
                "final_selected_score": None if global_selected is None else global_selected.get("score_total"),
                "final_selected_reason": final_selected_reason,
                "best_losing_family": None if best_losing_entry is None else best_losing_entry.get("family"),
                "best_losing_candidate": None if best_losing_entry is None else best_losing_entry.get("label"),
                "best_losing_reason": None if best_losing_entry is None else _selection_reason_chain(global_selected, best_losing_entry),
            },
        },
        location="inputs_page.py:severe_shear_escalation",
        hypothesis_id="H_SHEAR_ESCALATION",
    )


def _candidate_state_with_effective_bottom_for_overview(
    candidate_state: dict,
    bottom_updates: dict | None,
) -> dict:
    """Merge effective bottom steel / d into flat state so build_bending_check_rows_from_state matches _evaluate_bending_with_bottom_state."""
    merged = dict(candidate_state)
    bs = _effective_bottom_design_state(candidate_state, bottom_updates)
    nb = int(bs.get("nb_bot", 0) or 0)
    db = float(bs.get("db_bot", 0.0) or 0.0)
    if nb > 0 and db > 0.0:
        merged["Ast_bot"] = float(bs.get("Ast_bot", 0.0) or 0.0)
        merged["db_bot"] = db
        merged["nb_bot"] = nb
        merged["d"] = float(bs.get("d_centroid", 0.0) or 0.0)
    return merged


def _phi_mu_cap_knm_from_bending(bending: dict | None) -> float:
    if not bending:
        return 0.0
    return float(bending.get("phi_Mu_cap", 0.0) or 0.0)


def _candidate_bending_demand_util(candidate: dict) -> float | None:
    """Mu* / φMu from bending pack (demand / flexural capacity), not ductility/min-steel util."""
    if not isinstance(candidate, dict):
        return None
    ov = candidate.get("overview") or {}
    bp = (ov.get("packs") or {}).get("bending") or {}
    phi = float(bp.get("summary_phiMu_kNm", 0.0) or 0.0)
    mu = float(bp.get("summary_Mu_star_kNm", 0.0) or 0.0)
    if phi <= 1e-9:
        return None
    return mu / phi


def _candidate_bending_component_util(candidate: dict, key: str) -> float | None:
    if not isinstance(candidate, dict):
        return None
    components = candidate.get("bending_components", {}) or {}
    raw = components.get(key)
    try:
        value = float(raw)
    except Exception:
        return None
    if math.isnan(value):
        return None
    return value


def _candidate_ductility_util(candidate: dict) -> float | None:
    return _candidate_bending_component_util(candidate, "ductility_util")


def _candidate_flexural_util(candidate: dict) -> float | None:
    return _candidate_bending_component_util(candidate, "flexural_util")


def _candidate_min_steel_util(candidate: dict) -> float | None:
    return _candidate_bending_component_util(candidate, "min_steel_util")


def _candidate_ductility_governs(candidate: dict | None) -> bool:
    if not isinstance(candidate, dict):
        return False
    ductility_util = _candidate_ductility_util(candidate)
    if ductility_util is None:
        return False
    governing = [
        value
        for value in (
            _candidate_flexural_util(candidate),
            _candidate_min_steel_util(candidate),
            ductility_util,
        )
        if value is not None
    ]
    if not governing:
        return False
    return ductility_util >= max(governing) - 1e-6 and ductility_util >= 0.85


def _ductility_governs_overview(overview: dict | None) -> bool:
    rows = (((overview or {}).get("packs") or {}).get("bending") or {}).get("rows") or []
    ductility_row = next((row for row in rows if str(row.get("title") or "") == "Ductility limit"), None)
    flexural_row = next((row for row in rows if str(row.get("title") or "") == "Flexural strength capacity"), None)
    ductility_util = _parse_util_value((ductility_row or {}).get("util"))
    flexural_util = _parse_util_value((flexural_row or {}).get("util"))
    if ductility_util is None:
        return False
    candidates = [value for value in (ductility_util, flexural_util) if value is not None]
    return bool(candidates) and ductility_util >= max(candidates) - 1e-6 and ductility_util >= 0.85


def _ductility_fix_tier(candidate: dict, reference_candidate: dict | None) -> int:
    if not isinstance(candidate, dict):
        return 4
    reference_candidate = reference_candidate or {}
    candidate_state = dict(candidate.get("state") or {})
    reference_state = dict(reference_candidate.get("state") or {})
    updates = dict(candidate.get("updates") or {})
    width_key, _, _ = _resolve_geometry_width_context(reference_state or candidate_state)
    bottom_keys = {
        "bot_row_count",
        "bot1_layout_mode",
        "bot1_count",
        "db_bot_1",
        "bot2_layout_mode",
        "bot2_count",
        "db_bot_2",
        "bot_row_1_mode",
        "bot_row_1_bars",
        "bot_row_1_spacing",
        "bot_row_1_dia",
        "bot_row_2_mode",
        "bot_row_2_bars",
        "bot_row_2_spacing",
        "bot_row_2_dia",
    }
    advanced_keys = {"Ast_top", "db_top", "nb_top", "top_row_count"}
    if any(key in updates for key in advanced_keys):
        return 4

    ref_width = _design_width_value(reference_state or candidate_state)
    ref_depth = float(reference_candidate.get("depth", _float_from_state(reference_state or candidate_state, "D", 0.0)) or _float_from_state(reference_state or candidate_state, "D", 0.0))
    cand_width = _design_width_value(candidate_state)
    cand_depth = float(candidate.get("depth", _float_from_state(candidate_state, "D", 0.0)) or _float_from_state(candidate_state, "D", 0.0))
    width_growth = cand_width > ref_width + 1e-6
    depth_growth = cand_depth > ref_depth + 1e-6
    ast_growth = float(candidate.get("Ast_bot", 0.0) or 0.0) > float(reference_candidate.get("Ast_bot", 0.0) or 0.0) + 1e-6

    if updates and set(updates).issubset(bottom_keys) and not ast_growth:
        return 1
    if width_growth and not depth_growth:
        return 2
    if depth_growth:
        return 3
    if not ast_growth:
        return 1
    if width_growth:
        return 2
    return 4


def _ductility_tier_label(tier: int) -> str:
    return {
        1: "Tier 1 steel-ratio reduction",
        2: "Tier 2 width",
        3: "Tier 3 depth",
        4: "Tier 4 advanced",
    }.get(int(tier), "Tier 4 advanced")


def _candidate_ductility_reason(candidate: dict, reference_candidate: dict | None) -> str:
    tier = _ductility_fix_tier(candidate, reference_candidate)
    if tier == 1:
        return "reduce bottom tensile ratio first"
    if tier == 2:
        return "prefer width before depth"
    if tier == 3:
        return "depth fallback after steel/width"
    return "advanced or mixed ductility fix"


def _candidate_changes_geometry(reference_state: dict | None, candidate_state: dict | None) -> bool:
    before = reference_state if isinstance(reference_state, dict) else {}
    after = candidate_state if isinstance(candidate_state, dict) else {}
    return any(before.get(key) != after.get(key) for key in PRIMARY_GEOMETRY_KEYS)


def _candidate_changes_local_variables(reference_state: dict | None, candidate_state: dict | None) -> bool:
    before = reference_state if isinstance(reference_state, dict) else {}
    after = candidate_state if isinstance(candidate_state, dict) else {}
    changed = [key for key in after.keys() if before.get(key) != after.get(key)]
    return any(key not in PRIMARY_GEOMETRY_KEYS for key in changed)


def _shallower_beam_candidate_tier(candidate: dict) -> tuple[int, str]:
    candidate_state = dict(candidate.get("state") or {})
    seed_width = float(candidate.get("_seed_width", _design_width_value(candidate_state)) or _design_width_value(candidate_state))
    seed_depth = float(candidate.get("_seed_depth", _float_from_state(candidate_state, "D", 0.0)) or _float_from_state(candidate_state, "D", 0.0))
    candidate_width = float(candidate.get("width", _design_width_value(candidate_state)) or _design_width_value(candidate_state))
    candidate_depth = float(candidate.get("depth", _float_from_state(candidate_state, "D", 0.0)) or _float_from_state(candidate_state, "D", 0.0))
    width_increased = candidate_width > seed_width + 1e-9
    depth_increased = candidate_depth > seed_depth + 1e-9
    if not width_increased and not depth_increased:
        return 0, "local_or_detailing"
    if width_increased and not depth_increased:
        return 1, "width_before_depth"
    if width_increased and depth_increased:
        return 2, "width_plus_depth_fallback"
    return 3, "depth_fallback"


def _shallower_beam_metrics(candidate: dict, seed_candidate: dict) -> dict:
    candidate_state = dict(candidate.get("state") or {})
    seed_state = dict(seed_candidate.get("state") or {})
    seed_depth = float(seed_candidate.get("depth", _float_from_state(seed_state, "D", 0.0)) or _float_from_state(seed_state, "D", 0.0))
    candidate_depth = float(candidate.get("depth", _float_from_state(candidate_state, "D", 0.0)) or _float_from_state(candidate_state, "D", 0.0))
    seed_width = float(seed_candidate.get("width", _design_width_value(seed_state)) or _design_width_value(seed_state))
    candidate_width = float(candidate.get("width", _design_width_value(candidate_state)) or _design_width_value(candidate_state))
    seed_ast = float(seed_candidate.get("Ast_bot", 0.0) or 0.0)
    candidate_ast = float(candidate.get("Ast_bot", 0.0) or 0.0)
    depth_reduction = max(seed_depth - candidate_depth, 0.0)
    width_growth = max(candidate_width - seed_width, 0.0)
    reinforcement_growth = max(candidate_ast - seed_ast, 0.0)
    shallowness_score = depth_reduction - (0.45 * width_growth) - (0.04 * reinforcement_growth)
    materially_shallower = depth_reduction >= 50.0 or (depth_reduction >= 25.0 and width_growth <= 50.0 and reinforcement_growth <= 120.0)
    return {
        "depth_reduction": depth_reduction,
        "width_growth": width_growth,
        "reinforcement_growth": reinforcement_growth,
        "shallowness_score": shallowness_score,
        "materially_shallower": materially_shallower,
    }


def _shallower_beam_selection_key(candidate: dict, seed_candidate: dict, mode_config: dict) -> tuple:
    seed_state = dict(seed_candidate.get("state") or {})
    cand_state = dict(candidate.get("state") or {})
    seed_depth = float(seed_candidate.get("depth", _float_from_state(seed_state, "D", 0.0)) or _float_from_state(seed_state, "D", 0.0))
    cand_depth = float(candidate.get("depth", _float_from_state(cand_state, "D", 0.0)) or _float_from_state(cand_state, "D", 0.0))
    seed_width = float(seed_candidate.get("width", _design_width_value(seed_state)) or _design_width_value(seed_state))
    cand_width = float(candidate.get("width", _design_width_value(cand_state)) or _design_width_value(cand_state))
    seed_ast = float(seed_candidate.get("Ast_bot", 0.0) or 0.0)
    cand_ast = float(candidate.get("Ast_bot", 0.0) or 0.0)
    delta_d_mm = max(cand_depth - seed_depth, 0.0)
    delta_b_mm = max(cand_width - seed_width, 0.0)
    delta_ast_bot = max(cand_ast - seed_ast, 0.0)
    is_geometry = bool(candidate.get("recommendation_geometry_trial"))
    in_band = 0 if _candidate_in_target_band(candidate, mode_config) else 1
    congestion = float(candidate.get("reo_congestion_index", 0.0) or 0.0)
    return (
        0 if bool(candidate.get("is_compliant")) else 1,
        in_band,
        delta_d_mm,
        0 if not is_geometry else 1,
        delta_b_mm,
        delta_ast_bot,
        congestion,
        round(float(candidate.get("score", float("inf")) or float("inf")), 4),
        float(utilisation_gap(candidate, mode_config)),
        float(candidate.get("worst_util", float("inf")) or float("inf")),
    )


def _shear_cleanup_possible(state: dict | None) -> bool:
    if not isinstance(state, dict):
        return False
    lig_legs = _int_from_state(state, "lig_legs", 0)
    s_lig = _float_from_state(state, "s_lig", 0.0)
    max_spacing = float(max(REO_SPACINGS) if REO_SPACINGS else 300.0)
    return lig_legs > 0 or (s_lig > 0.0 and s_lig < max_spacing - 1e-9)


def _shear_demands_negligible(actions: dict | None) -> bool:
    if not isinstance(actions, dict):
        return False
    try:
        vu = abs(float(actions.get("Vu", 0.0) or 0.0))
        tu = abs(float(actions.get("Tu", 0.0) or 0.0))
    except (TypeError, ValueError):
        return False
    return vu <= GUIDANCE_SHEAR_DEMAND_ABS_TOL_KN + 1e-12 and tu <= GUIDANCE_TORSION_DEMAND_ABS_TOL_KNM + 1e-12


def _critical_case_name(candidate: dict | None) -> str:
    overview = ((candidate or {}).get("overview") or {})
    utils = dict(overview.get("utils") or {})
    ranked = []
    for key in ("bending", "shear", "crack", "deflection"):
        try:
            value = float(utils.get(key))
        except Exception:
            continue
        if not math.isnan(value):
            ranked.append((key, value))
    if not ranked:
        return "overall"
    ranked.sort(key=lambda item: item[1], reverse=True)
    return str(ranked[0][0])


def _critical_case_util(candidate: dict | None, case_name: str) -> float | None:
    overview = ((candidate or {}).get("overview") or {})
    raw = ((overview.get("utils") or {}).get(case_name))
    try:
        value = float(raw)
    except Exception:
        return None
    return None if math.isnan(value) else value


def _protected_case_min_util(
    protected_before: float | None,
    mode_config: dict,
) -> float:
    target_min = float(mode_config.get("target_util_min", 0.8) or 0.8)
    if protected_before is None:
        return target_min - 0.02
    return max(0.0, min(target_min, float(protected_before)) - 0.02)


def _candidate_reduces_noncritical_provision(candidate: dict, reference_candidate: dict) -> bool:
    if not candidate or not reference_candidate:
        return False
    if float(candidate.get("Ast_bot", 0.0) or 0.0) < float(reference_candidate.get("Ast_bot", 0.0) or 0.0) - 1e-6:
        return True
    if float(candidate.get("shear_density", 0.0) or 0.0) < float(reference_candidate.get("shear_density", 0.0) or 0.0) - 1e-6:
        return True
    if float(candidate.get("reo_complexity", compute_reo_complexity(candidate)) or 0.0) < float(reference_candidate.get("reo_complexity", compute_reo_complexity(reference_candidate)) or 0.0) - 1e-6:
        return True
    return False


def _cleanup_candidate_rank(candidate: dict, reference_candidate: dict, protected_case: str) -> tuple:
    protected_util = _critical_case_util(candidate, protected_case)
    protected_distance = abs(float(protected_util) - float(_critical_case_util(reference_candidate, protected_case) or 0.0)) if protected_util is not None else float("inf")
    local_priority = 0 if _candidate_changes_local_variables(reference_candidate.get("state"), candidate.get("state")) else 1
    geometry_penalty = 1 if _candidate_changes_geometry(reference_candidate.get("state"), candidate.get("state")) else 0
    steel_area = float(candidate.get("Ast_bot", 0.0) or 0.0) + float(candidate.get("Ast_top", 0.0) or 0.0)
    complexity = float(candidate.get("reo_complexity", compute_reo_complexity(candidate)) or 0.0)
    return (
        protected_distance,
        geometry_penalty,
        local_priority,
        steel_area,
        complexity,
        float(candidate.get("score", float("inf")) or float("inf")),
    )


def _candidate_preserves_protected_case(
    candidate: dict,
    protected_case: str,
    *,
    protected_min_util: float,
) -> bool:
    if not candidate or not bool(candidate.get("is_compliant")):
        return False
    protected_util = _critical_case_util(candidate, protected_case)
    if protected_util is None:
        return False
    if protected_util > 1.0 + 1e-9:
        return False
    return protected_util >= protected_min_util - 1e-9


def _cleanup_candidate_debug_payload(
    candidate: dict,
    reference_candidate: dict,
    protected_case: str,
    *,
    accepted: bool,
    reason: str,
) -> dict:
    geometry_changed = _candidate_changes_geometry(reference_candidate.get("state"), candidate.get("state"))
    local_changed = _candidate_changes_local_variables(reference_candidate.get("state"), candidate.get("state"))
    return {
        "candidate_label": str(candidate.get("label") or ""),
        "variables_changed": sorted(list((candidate.get("updates") or {}).keys())),
        "candidate_type": "geometry_fallback" if geometry_changed else "local_cleanup",
        "geometry_changed": geometry_changed,
        "local_changed": local_changed,
        "protected_case": protected_case,
        "protected_util_before": _critical_case_util(reference_candidate, protected_case),
        "protected_util_after": _critical_case_util(candidate, protected_case),
        "overall_worst_util": float(candidate.get("worst_util", 0.0) or 0.0),
        "accepted": bool(accepted),
        "reason": reason,
    }


def _cleanup_stop_reason_message(stop_reason: str) -> str:
    mapping = {
        "no_more_local_cleanup_candidates": "No further local reductions available without impacting the critical case.",
        "no_more_safe_local_reductions": "No further safe local reductions available without impacting the critical case.",
        "cleanup_iteration_cap_hit": "Cleanup stopped at the iteration cap while protecting the critical case.",
    }
    return mapping.get(str(stop_reason or ""), "")


def _log_phi_mu_capacity_mismatch(
    *,
    source: str,
    pack_phi_knm: float,
    direct_phi_knm: float,
    candidate_state_keys_sample: list[str],
) -> None:
    rel_tol = 0.02
    abs_tol = 0.5
    lo = max(abs(pack_phi_knm), abs(direct_phi_knm), 1.0) * rel_tol
    if abs(pack_phi_knm - direct_phi_knm) <= max(lo, abs_tol):
        return
    _agent_debug_log(
        "AUTO DESIGN USING STALE CAPACITY",
        {
            "error": "phiMu_from_pack_mismatch_vs_direct_bending",
            "source": source,
            "summary_phiMu_kNm_pack": pack_phi_knm,
            "phi_Mu_cap_direct_bending": direct_phi_knm,
            "delta_knm": abs(pack_phi_knm - direct_phi_knm),
            "state_key_sample": candidate_state_keys_sample,
        },
        location="inputs_page.py:phi_mu_capacity_check",
        hypothesis_id="H_PHI_CAPACITY",
    )
    if bool(st.session_state.get("_dev_mode")):
        assert abs(pack_phi_knm - direct_phi_knm) <= max(lo, abs_tol), (
            "AUTO DESIGN USING STALE CAPACITY: pack phiMu vs direct bending phi_Mu_cap"
        )


def _reject_heavier_steel_lower_demand_util(current: dict, candidate: dict) -> bool:
    """More bottom steel but lower Mu*/phiMu is not an efficiency improvement."""
    ast0 = float(current.get("Ast_bot", 0.0) or 0.0)
    ast1 = float(candidate.get("Ast_bot", 0.0) or 0.0)
    if ast1 <= ast0 + 1e-6:
        return False
    u0 = _candidate_bending_demand_util(current)
    u1 = _candidate_bending_demand_util(candidate)
    if u0 is None or u1 is None:
        return False
    return u1 < u0 - 1e-9


def evaluate_candidate_full(
    candidate_state: dict,
    *,
    source: str = "full_eval",
    label: str | None = None,
    action_type: str | None = None,
    updates: dict | None = None,
) -> dict | None:
    bottom_updates = _candidate_bottom_updates(candidate_state)
    shear_updates = _candidate_shear_updates(candidate_state)
    overview_state = _candidate_state_with_effective_bottom_for_overview(candidate_state, bottom_updates)
    crack = _evaluate_crack_with_state(candidate_state, bottom_updates=bottom_updates)
    deflection = _evaluate_deflection_with_state(candidate_state, bottom_updates=bottom_updates)
    base_overview = _collect_design_overview(overview_state)
    bending = _evaluate_bending_with_bottom_state(candidate_state, bottom_updates)
    shear = _evaluate_shear_with_state(
        candidate_state,
        bottom_updates=bottom_updates,
        shear_updates=shear_updates,
    )

    bending_util = None
    bending_status = "—"
    flexural_util = None
    ductility_util = None
    min_steel_util = None
    if bending:
        flexural_util = float(bending.get("Mu_util", float("inf")))
        try:
            ductility_util = float(bending.get("ku", 0.0) or 0.0) / 0.36 if bending.get("ku") is not None else None
        except Exception:
            ductility_util = None
        try:
            as_min = float(bending.get("As_min", 0.0) or 0.0)
            ast = float(bending.get("Ast_bot", 0.0) or 0.0)
            if ast > 0.0 and as_min > 0.0:
                min_steel_util = as_min / ast
        except Exception:
            min_steel_util = None
        bending_util = flexural_util
        if bending_util is not None and math.isnan(bending_util):
            bending_util = None
        governs = [
            u
            for u in (flexural_util, ductility_util, min_steel_util)
            if u is not None and not math.isnan(u)
        ]
        if governs:
            if any(u > 1.0 for u in governs):
                bending_status = "FAIL"
            elif any(u >= 0.95 for u in governs):
                bending_status = "NEAR LIMIT"
            else:
                bending_status = "PASS"
        else:
            bending_status = "—"

    shear_util = None
    shear_status = "—"
    if shear:
        shear_candidates = []
        for value in (shear.get("util"), shear.get("web_util")):
            try:
                coerced = float(value)
            except Exception:
                continue
            if not math.isnan(coerced):
                shear_candidates.append(coerced)
        shear_util = max(shear_candidates, default=None)
        shear_status = _status_from_candidate_util(shear_util)

    statuses = dict(base_overview["statuses"])
    statuses["bending"] = bending_status
    statuses["shear"] = shear_status
    if crack is not None:
        crack_util = float(crack.get("util", 0.0) or 0.0)
        statuses["crack"] = _status_from_candidate_util(crack_util)
    if deflection is not None:
        statuses["deflection"] = str(deflection.get("status") or "—")
    utils = dict(base_overview["utils"])
    utils["bending"] = bending_util
    utils["shear"] = shear_util
    if crack is not None:
        utils["crack"] = float(crack.get("util", 0.0) or 0.0)
    if deflection is not None:
        utils["deflection"] = deflection.get("util")
    packs = dict(base_overview["packs"])
    if deflection is not None:
        packs["deflection"] = dict(deflection.get("pack") or {})
    tracked_statuses = [status for status in statuses.values() if status not in ("—", "")]
    overview = {
        "packs": packs,
        "statuses": statuses,
        "utils": utils,
        "any_fail": any(status == "FAIL" for status in tracked_statuses),
        "any_warn": any(status == "NEAR LIMIT" for status in tracked_statuses),
        "all_key_pass": bool(tracked_statuses) and all(status == "PASS" for status in tracked_statuses),
        "worst_util": max((util for util in utils.values() if util is not None), default=0.0),
    }
    pack_phi = float(((overview.get("packs") or {}).get("bending") or {}).get("summary_phiMu_kNm", 0.0) or 0.0)
    direct_phi = _phi_mu_cap_knm_from_bending(bending)
    _log_phi_mu_capacity_mismatch(
        source=source,
        pack_phi_knm=pack_phi,
        direct_phi_knm=direct_phi,
        candidate_state_keys_sample=sorted(list(candidate_state.keys()))[:40],
    )
    bottom_state = _effective_bottom_design_state(candidate_state, bottom_updates)
    width = _design_width_value(candidate_state)
    depth = _float_from_state(candidate_state, "D", 600.0)
    shear_density = (
        _int_from_state(candidate_state, "lig_legs", 0)
        * max(_int_from_state(candidate_state, "lig_d", 0), 1) ** 2
    ) / max(_float_from_state(candidate_state, "s_lig", 200.0), 1.0)
    fail_count = sum(1 for status in overview["statuses"].values() if status == "FAIL")
    return {
        "source": source,
        "label": label or source.replace("_", " ").title(),
        "action_type": action_type,
        "updates": dict(updates or {}),
        "state": candidate_state,
        "overview": overview,
        "bottom_state": bottom_state,
        "width": float(width),
        "depth": float(depth),
        "Ast_bot": float(bottom_state.get("Ast_bot", 0.0) or 0.0),
        "Ast_top": _float_from_state(candidate_state, "Ast_top", 0.0),
        "bar_count": _bottom_bar_count_from_state(candidate_state, bottom_state),
        "row_count": _bottom_row_count_from_state(candidate_state),
        "reo_congestion_index": _reo_congestion_index(candidate_state, bottom_state),
        "shear_density": float(shear_density),
        "bending_components": {
            "flexural_util": flexural_util if bending else None,
            "ductility_util": ductility_util if bending else None,
            "min_steel_util": min_steel_util if bending else None,
        },
        "is_compliant": bool(overview["all_key_pass"]),
        "worst_util": float(overview["worst_util"] or 0.0),
        "fail_count": fail_count,
    }


def _evaluate_auto_design_candidate(
    state: dict,
    *,
    updates: dict | None = None,
    source: str,
    label: str | None = None,
    action_type: str | None = None,
) -> dict | None:
    candidate_state = _guidance_state_snapshot(state)
    if updates:
        candidate_state.update(updates)
    return evaluate_candidate_full(
        candidate_state,
        source=source,
        label=label,
        action_type=action_type,
        updates=updates,
    )


def _candidate_objective_util(candidate: dict) -> float:
    """Score distance-to-target band: uses Mu*/phiMu (bending) when available, not ductility/min-steel."""
    state = candidate.get("state") if isinstance(candidate, dict) else {}
    goal = _design_optimisation_goal(state if isinstance(state, dict) else {})
    utils = candidate.get("overview", {}).get("utils", {}) if isinstance(candidate, dict) else {}

    bend_du = _candidate_bending_demand_util(candidate) if isinstance(candidate, dict) else None

    if goal == "less_shear_reinforcement":
        objective_values = [utils.get("shear")]
    else:
        objective_values = [bend_du, utils.get("shear")]

    resolved_values: list[float] = []
    for value in objective_values:
        if value is None:
            continue
        try:
            resolved = float(value)
        except Exception:
            continue
        if not math.isnan(resolved):
            resolved_values.append(resolved)

    if resolved_values:
        return max(resolved_values)
    return float(candidate.get("worst_util", 0.0) or 0.0)


def _candidate_in_target_band(candidate: dict, mode_config: dict) -> bool:
    util = _candidate_objective_util(candidate)
    return float(mode_config["target_util_min"]) <= util <= float(mode_config["target_util_max"])


def _distance_to_target_band(util: float, target_min: float, target_max: float) -> float:
    try:
        u = float(util)
        lo = float(target_min)
        hi = float(target_max)
    except (TypeError, ValueError):
        return float("inf")
    if lo <= u <= hi:
        return 0.0
    if u < lo:
        return lo - u
    return u - hi


def _candidate_reaches_target_band_one_step(candidate: dict, mode_config: dict) -> bool:
    if not candidate or not bool(candidate.get("is_compliant")):
        return False
    return _candidate_in_target_band(candidate, mode_config)


def _annotate_candidate_target_band_metrics(candidate: dict, mode_config: dict) -> None:
    if not candidate:
        return
    try:
        util = float(_candidate_objective_util(candidate))
    except Exception:
        util = float(candidate.get("worst_util", 0.0) or 0.0)
    tmin = float(mode_config.get("target_util_min", EFFICIENCY_TARGET_UTIL_MIN) or EFFICIENCY_TARGET_UTIL_MIN)
    tmax = float(mode_config.get("target_util_max", EFFICIENCY_TARGET_UTIL_MAX) or EFFICIENCY_TARGET_UTIL_MAX)
    candidate["candidate_post_util"] = util
    candidate["candidate_distance_to_target_band"] = _distance_to_target_band(util, tmin, tmax)
    candidate["candidate_reaches_target_band"] = _candidate_reaches_target_band_one_step(candidate, mode_config)


def _candidate_in_target_zone(candidate: dict, mode_config: dict) -> bool:
    if not candidate:
        return False
    if not bool(candidate.get("is_compliant")):
        return False

    util = float(candidate.get("worst_util", 0.0) or 0.0)
    target_min = float(mode_config.get("target_util_min", 0.80) or 0.80)
    target_max = float(mode_config.get("target_util_max", 0.90) or 0.90)
    return target_min <= util <= target_max


def _candidate_violation_score(candidate: dict) -> float:
    util = float(candidate.get("worst_util", 0.0) or 0.0)
    overflow = max(util - 1.0, 0.0)
    fail_count = int(candidate.get("fail_count", 0) or 0)
    return overflow * 100.0 + fail_count * 25.0


def _score_auto_design_candidate_components(candidate: dict, mode_config: dict, seed_candidate: dict) -> dict:
    util = _candidate_objective_util(candidate)
    target_min = float(mode_config["target_util_min"])
    target_max = float(mode_config["target_util_max"])
    target_mid = _mode_target_midpoint(mode_config)
    if util < target_min:
        util_penalty = (target_min - util) * 80.0
    elif util > target_max:
        util_penalty = (util - target_max) * 120.0
    else:
        util_penalty = abs(util - target_mid) * 24.0

    depth = float(candidate.get("depth", 0.0) or 0.0)
    width = float(candidate.get("width", 0.0) or 0.0)
    seed_depth = float(seed_candidate.get("depth", depth) or depth)
    depth_growth = max(depth - seed_depth, 0.0)
    depth_penalty = (depth / 50.0) * float(mode_config["geometry_penalty"])
    depth_penalty += (depth_growth / 25.0) * float(mode_config.get("depth_growth_multiplier", 1.0))
    width_penalty = (width / 50.0) * float(mode_config.get("width_penalty", 0.4))

    steel_area = float(candidate.get("Ast_bot", 0.0) or 0.0) + float(candidate.get("Ast_top", 0.0) or 0.0)
    steel_penalty = (steel_area / 100.0) * float(mode_config["steel_penalty"])
    congestion_penalty = float(candidate.get("reo_congestion_index", 0.0) or 0.0) * float(mode_config["reo_congestion_penalty"])
    row_penalty = max(int(candidate.get("row_count", 1) or 1) - 1, 0) * 2.0
    if mode_config.get("prefer_lower_reo_congestion"):
        row_penalty *= 1.75

    shear_density_penalty = 0.0
    if mode_config["label"] == "Less shear reinforcement":
        shear_density_penalty = float(candidate.get("shear_density", 0.0) or 0.0) * 0.08
    shallow_metrics = _shallower_beam_metrics(candidate, seed_candidate)
    shallowness_score = 0.0
    width_growth_penalty = 0.0
    reinforcement_growth_penalty = 0.0
    non_material_shallow_penalty = 0.0
    if str(mode_config.get("search_strategy", "balanced") or "balanced") == "shallow":
        shallowness_score = float(shallow_metrics.get("shallowness_score", 0.0) or 0.0)
        width_growth_penalty = float(shallow_metrics.get("width_growth", 0.0) or 0.0) * 0.9
        reinforcement_growth_penalty = float(shallow_metrics.get("reinforcement_growth", 0.0) or 0.0) * 0.06
        if not bool(shallow_metrics.get("materially_shallower")) and (
            float(shallow_metrics.get("width_growth", 0.0) or 0.0) >= 100.0
            or float(shallow_metrics.get("reinforcement_growth", 0.0) or 0.0) >= 150.0
        ):
            non_material_shallow_penalty = 60.0

    ductility_priority = _candidate_ductility_governs(seed_candidate)
    candidate["_ductility_priority"] = bool(ductility_priority)
    if ductility_priority:
        tier = _ductility_fix_tier(candidate, seed_candidate)
        candidate["_ductility_tier"] = int(tier)
        candidate["_ductility_tier_label"] = _ductility_tier_label(tier)
        candidate["_ductility_reason"] = _candidate_ductility_reason(candidate, seed_candidate)
    else:
        candidate.pop("_ductility_tier", None)
        candidate.pop("_ductility_tier_label", None)
        candidate.pop("_ductility_reason", None)

    if not bool(candidate.get("is_compliant")):
        total_score = 10000.0 + _candidate_violation_score(candidate)
        return {
            "util_penalty": util_penalty,
            "geometry_penalty": depth_penalty + width_penalty,
            "depth_penalty": depth_penalty,
            "width_penalty": width_penalty,
            "steel_penalty": steel_penalty,
            "congestion_penalty": congestion_penalty,
            "row_penalty": row_penalty,
            "shear_density_penalty": shear_density_penalty,
            "goal_bias_penalty": 0.0,
            "shear_improvement_contribution": util_penalty,
            "bending_efficiency_contribution": steel_penalty + row_penalty,
            "shallowness_score": shallowness_score,
            "width_growth_penalty": width_growth_penalty,
            "reinforcement_growth_penalty": reinforcement_growth_penalty,
            "total_score": total_score,
        }
    if ductility_priority:
        tier = int(candidate.get("_ductility_tier", 4) or 4)
        ductility_util = _candidate_ductility_util(candidate)
        seed_ductility_util = _candidate_ductility_util(seed_candidate)
        ductility_overflow = max((float(ductility_util) if ductility_util is not None else 999.0) - 1.0, 0.0)
        ductility_penalty = ductility_overflow * 1200.0
        if ductility_util is None:
            ductility_penalty += 200.0
        else:
            ductility_penalty += float(ductility_util) * 120.0
        if ductility_util is not None and seed_ductility_util is not None and float(ductility_util) >= float(seed_ductility_util) - 1e-6:
            ductility_penalty += 140.0
        ast_growth = max(float(candidate.get("Ast_bot", 0.0) or 0.0) - float(seed_candidate.get("Ast_bot", 0.0) or 0.0), 0.0)
        steel_growth_penalty = ast_growth * 0.06
        depth_growth_penalty = max(depth - seed_depth, 0.0) * 0.9
        width_growth_penalty = max(width - float(seed_candidate.get("width", width) or width), 0.0) * 0.15
        tier_penalty = {1: 0.0, 2: 10.0, 3: 30.0, 4: 55.0}.get(int(tier), 55.0)
        total_score = (
            (util_penalty * 0.3)
            + ductility_penalty
            + tier_penalty
            + (steel_penalty * 0.4)
            + steel_growth_penalty
            + (congestion_penalty * 0.8)
            + row_penalty
            + width_growth_penalty
            + depth_growth_penalty
            + shear_density_penalty
            + non_material_shallow_penalty
            - max(shallowness_score, 0.0) * 0.1
        )
        return {
            "util_penalty": util_penalty * 0.3,
            "geometry_penalty": width_growth_penalty + depth_growth_penalty,
            "depth_penalty": depth_growth_penalty,
            "width_penalty": width_growth_penalty,
            "steel_penalty": (steel_penalty * 0.4) + steel_growth_penalty,
            "congestion_penalty": congestion_penalty * 0.8,
            "row_penalty": row_penalty,
            "shear_density_penalty": shear_density_penalty,
            "goal_bias_penalty": tier_penalty,
            "shear_improvement_contribution": util_penalty * 0.3,
            "bending_efficiency_contribution": ductility_penalty,
            "shallowness_score": shallowness_score,
            "width_growth_penalty": width_growth_penalty,
            "reinforcement_growth_penalty": reinforcement_growth_penalty,
            "total_score": total_score,
        }

    shallow_delta_d_extra = 0.0
    shallow_same_d_bonus = 0.0
    if str(mode_config.get("search_strategy", "balanced") or "balanced") == "shallow":
        sd = float(seed_candidate.get("depth", depth) or depth)
        delta_d_grow = max(depth - sd, 0.0)
        shallow_delta_d_extra = delta_d_grow * 3.4
        if delta_d_grow <= 1e-9:
            shallow_same_d_bonus = -48.0

    compound_width_reo_bonus = 0.0
    if (
        str(mode_config.get("search_strategy", "balanced") or "balanced") == "shallow"
        and bool(candidate.get("recommendation_compound"))
        and str(candidate.get("compound_geo_axis") or "") == "width"
    ):
        sd = float(seed_candidate.get("depth", depth) or depth)
        if depth <= sd + 1e-9:
            compound_width_reo_bonus = -18.0

    total_score = (
        util_penalty
        + depth_penalty
        + width_penalty
        + steel_penalty
        + congestion_penalty
        + row_penalty
        + shear_density_penalty
        + width_growth_penalty
        + reinforcement_growth_penalty
        + non_material_shallow_penalty
        + shallow_delta_d_extra
        + shallow_same_d_bonus
        + compound_width_reo_bonus
        - max(shallowness_score, 0.0) * 0.6
    )
    return {
        "util_penalty": util_penalty,
        "geometry_penalty": depth_penalty + width_penalty,
        "depth_penalty": depth_penalty,
        "width_penalty": width_penalty,
        "steel_penalty": steel_penalty,
        "congestion_penalty": congestion_penalty,
        "row_penalty": row_penalty,
        "shear_density_penalty": shear_density_penalty,
        "goal_bias_penalty": 0.0,
        "shear_improvement_contribution": util_penalty,
        "bending_efficiency_contribution": steel_penalty + row_penalty,
        "shallowness_score": shallowness_score,
        "width_growth_penalty": width_growth_penalty,
        "reinforcement_growth_penalty": reinforcement_growth_penalty,
        "shallow_delta_d_extra": shallow_delta_d_extra,
        "shallow_same_d_bonus": shallow_same_d_bonus,
        "compound_width_reo_bonus": compound_width_reo_bonus,
        "total_score": total_score,
    }


def _score_auto_design_candidate(candidate: dict, mode_config: dict, seed_candidate: dict) -> float:
    components = _score_auto_design_candidate_components(candidate, mode_config, seed_candidate)
    candidate["_score_components"] = dict(components)
    return float(components.get("total_score", 0.0) or 0.0)


def _score_band_reaching_candidate_for_goal(
    candidate: dict,
    goal: str,
    current_state: dict,
    mode_config: dict,
) -> tuple[float, str]:
    cs = dict(candidate.get("state") or {})
    d0 = float(_float_from_state(current_state, "D", 0.0) or 0.0)
    d1 = float(_float_from_state(cs, "D", d0) or d0)
    w0 = float(_design_width_value(current_state) or 0.0)
    w1 = float(_design_width_value(cs) or w0)
    ast0 = float(_float_from_state(current_state, "Ast_bot", 0.0) or 0.0)
    ast1 = float(candidate.get("Ast_bot", _float_from_state(cs, "Ast_bot", ast0)) or ast0)
    delta_d = max(d1 - d0, 0.0)
    delta_w = max(w1 - w0, 0.0)
    delta_ast = max(ast1 - ast0, 0.0)
    post_util = float(candidate.get("candidate_post_util", _candidate_objective_util(candidate)) or 0.0)
    target_mid = _mode_target_midpoint(mode_config)
    congestion = float(candidate.get("reo_congestion_index", 0.0) or 0.0)
    row_pen = max(int(candidate.get("row_count", 1) or 1) - 2, 0)

    if goal == "shallower_beam":
        score = (
            (delta_d * 2000.0)
            + (d1 * 0.6)
            + (delta_ast * 0.08)
            + (delta_w * 0.04)
            + (congestion * 20.0)
            + (row_pen * 8.0)
        )
        if (
            bool(candidate.get("recommendation_compound"))
            and str(candidate.get("compound_geo_axis") or "") == "width"
            and delta_d <= 1e-6
        ):
            score -= 30.0
        return score, "shallower_prefers_min_depth_then_steel_then_width"

    score = (
        (abs(post_util - target_mid) * 90.0)
        + (delta_d * 0.3)
        + (delta_w * 0.25)
        + (delta_ast * 0.04)
        + (congestion * 18.0)
        + (row_pen * 8.0)
    )
    return score, "balanced_prefers_practical_low_congestion_near_target_mid"


def _band_reacher_delta_metrics(candidate: dict, current_state: dict) -> dict:
    cs = dict(candidate.get("state") or {})
    d0 = float(_float_from_state(current_state, "D", 0.0) or 0.0)
    d1 = float(_float_from_state(cs, "D", d0) or d0)
    w0 = float(_design_width_value(current_state) or 0.0)
    w1 = float(_design_width_value(cs) or w0)
    ast0 = float(_float_from_state(current_state, "Ast_bot", 0.0) or 0.0)
    ast1 = float(candidate.get("Ast_bot", _float_from_state(cs, "Ast_bot", ast0)) or ast0)
    return {
        "result_depth": d1,
        "delta_d": max(d1 - d0, 0.0),
        "delta_w": max(w1 - w0, 0.0),
        "delta_ast": max(ast1 - ast0, 0.0),
        "congestion": float(candidate.get("reo_congestion_index", 0.0) or 0.0),
        "row_pen": max(int(candidate.get("row_count", 1) or 1) - 2, 0),
    }


def _select_best_auto_design_candidate(candidates: list[dict], mode_config: dict, seed_candidate: dict) -> dict | None:
    if not candidates:
        return None
    for candidate in candidates:
        _annotate_candidate_target_band_metrics(candidate, mode_config)
        candidate["score"] = _score_auto_design_candidate(candidate, mode_config, seed_candidate)
    strategy = str(mode_config.get("search_strategy", "balanced") or "balanced")
    compliant = [candidate for candidate in candidates if candidate.get("is_compliant")]
    band_reachers = [candidate for candidate in compliant if candidate.get("candidate_reaches_target_band")]
    one_click_available = len(band_reachers) > 0
    current_in_band = bool(seed_candidate.get("is_compliant")) and _candidate_in_target_band(seed_candidate, mode_config)
    in_band = [candidate for candidate in compliant if _candidate_in_target_band(candidate, mode_config)]
    best_scored_compliant = (
        (
            min(compliant, key=lambda item: _shallower_beam_selection_key(item, seed_candidate, mode_config))
            if strategy == "shallow" else
            min(compliant, key=lambda item: (item["score"], item["depth"], item["width"]))
        )
        if compliant else None
    )
    best_scored_in_band = (
        (
            min(in_band, key=lambda item: _shallower_beam_selection_key(item, seed_candidate, mode_config))
            if strategy == "shallow" else
            min(in_band, key=lambda item: (item["score"], item["depth"], item["width"]))
        )
        if in_band else None
    )
    # region agent log
    _agent_debug_log(
        "Selector candidate band decision",
        {
            "mode_label": str(mode_config.get("label") or ""),
            "candidate_count": len(candidates),
            "compliant_count": len(compliant),
            "band_reacher_count": len(band_reachers),
            "in_band_count": len(in_band),
            "one_click_convergence_available": one_click_available,
            "best_scored_compliant": None if best_scored_compliant is None else {
                "source": str(best_scored_compliant.get("source") or ""),
                "label": str(best_scored_compliant.get("label") or ""),
                "score": float(best_scored_compliant.get("score", 0.0) or 0.0),
                "worst_util": float(best_scored_compliant.get("worst_util", 0.0) or 0.0),
                "in_band": bool(_candidate_in_target_band(best_scored_compliant, mode_config)),
                "has_updates": bool(best_scored_compliant.get("updates")),
            },
            "best_scored_in_band": None if best_scored_in_band is None else {
                "source": str(best_scored_in_band.get("source") or ""),
                "label": str(best_scored_in_band.get("label") or ""),
                "score": float(best_scored_in_band.get("score", 0.0) or 0.0),
                "worst_util": float(best_scored_in_band.get("worst_util", 0.0) or 0.0),
                "has_updates": bool(best_scored_in_band.get("updates")),
            },
        },
        location="inputs_page.py:_select_best_auto_design_candidate",
        hypothesis_id="H25",
    )
    # endregion
    if _design_guide_sidebar_debug_enabled():
        local_only = bool(compliant) and not one_click_available
        reason = (
            "at_least_one_compliant_candidate_reaches_target_band_in_one_move"
            if one_click_available
            else (
                "no_compliant_candidate_reaches_target_band_in_one_move"
                if compliant
                else "no_compliant_candidates"
            )
        )
        _merge_design_guide_rank_trace(
            {
                "auto_design_convergence_selection": {
                    "one_click_convergence_available": one_click_available,
                    "one_click_convergence_reason": reason,
                    "local_step_selected_only_because_no_band_reaching_candidate": local_only,
                    "compliant_count": len(compliant),
                    "band_reacher_count": len(band_reachers),
                    "winner_pool_mode": (
                        "band_reachers_only"
                        if (not current_in_band and bool(band_reachers))
                        else "all_compliant"
                    ),
                    "band_reacher_labels_considered": [
                        str(c.get("label") or "")[:100]
                        for c in band_reachers[:24]
                    ],
                },
            },
        )
    winner: dict | None = None
    selected_because_band = False
    winner_pool_mode = "all_compliant"
    winner_goal_score: float | None = None
    runner_up_goal_score: float | None = None
    goal_tie_break_reason: str | None = None
    if compliant:
        force_band_reacher_pool = bool((not current_in_band) and band_reachers)
        if force_band_reacher_pool:
            pool = band_reachers
            selected_because_band = True
            winner_pool_mode = "band_reachers_only"
        else:
            pool = compliant
            selected_because_band = False
            winner_pool_mode = "all_compliant"
        if selected_because_band:
            goal = _design_optimisation_goal(dict(seed_candidate.get("state") or {}))
            pref = "shallower" if goal == "shallower_beam" else "balanced"
            current_state = dict(seed_candidate.get("state") or {})
            ranked_pool: list[tuple[tuple, dict]] = []
            for item in pool:
                gscore, greason = _score_band_reaching_candidate_for_goal(
                    item,
                    goal,
                    current_state,
                    mode_config,
                )
                deltas = _band_reacher_delta_metrics(item, current_state)
                item["winning_candidate_goal_preference"] = pref
                item["candidate_goal_score"] = gscore
                item["candidate_goal_tie_break_reason"] = greason
                item["candidate_goal_delta_d_mm"] = deltas.get("delta_d")
                item["candidate_goal_delta_ast_mm2"] = deltas.get("delta_ast")
                item["candidate_goal_delta_w_mm"] = deltas.get("delta_w")
                if goal == "shallower_beam":
                    rank_key = (
                        float(gscore),
                        float(deltas.get("result_depth", item.get("depth", 0.0)) or 0.0),
                        float(deltas.get("delta_ast", 0.0) or 0.0),
                        float(deltas.get("delta_w", 0.0) or 0.0),
                        _shallower_beam_selection_key(item, seed_candidate, mode_config) if strategy == "shallow" else (),
                        float(item.get("score", 0.0) or 0.0),
                        float(item.get("depth", 0.0) or 0.0),
                        float(item.get("width", 0.0) or 0.0),
                    )
                else:
                    rank_key = (
                        float(gscore),
                        float(item.get("score", 0.0) or 0.0),
                        float(deltas.get("congestion", 0.0) or 0.0),
                        float(deltas.get("row_pen", 0.0) or 0.0),
                        float(deltas.get("delta_d", 0.0) or 0.0),
                        float(deltas.get("delta_w", 0.0) or 0.0),
                        float(deltas.get("delta_ast", 0.0) or 0.0),
                        float(item.get("depth", 0.0) or 0.0),
                        float(item.get("width", 0.0) or 0.0),
                    )
                ranked_pool.append((rank_key, item))
            ranked_pool.sort(key=lambda row: row[0])
            winner = ranked_pool[0][1]
            winner_goal_score = float(winner.get("candidate_goal_score", 0.0) or 0.0)
            goal_tie_break_reason = str(winner.get("candidate_goal_tie_break_reason") or "")
            if len(ranked_pool) > 1:
                runner = ranked_pool[1][1]
                runner_up_goal_score = float(runner.get("candidate_goal_score", 0.0) or 0.0)
                winner["runner_up_goal_score"] = runner_up_goal_score
        else:
            if strategy == "shallow":
                winner = min(pool, key=lambda item: _shallower_beam_selection_key(item, seed_candidate, mode_config))
            else:
                winner = min(
                    pool,
                    key=lambda item: (
                        item["score"],
                        float(item.get("candidate_distance_to_target_band") or 0.0),
                        item["depth"],
                        item["width"],
                    ),
                )
    else:
        winner = min(
            candidates,
            key=lambda item: (
                _candidate_violation_score(item),
                _shallower_beam_selection_key(item, seed_candidate, mode_config) if strategy == "shallow" else (),
                item["score"],
                item["depth"],
                item["width"],
            ),
        )
        selected_because_band = False
    if winner is not None:
        winner["winning_candidate_post_util"] = winner.get("candidate_post_util")
        winner["winning_candidate_reaches_target_band"] = winner.get("candidate_reaches_target_band")
        winner["winning_candidate_distance_to_target_band"] = winner.get("candidate_distance_to_target_band")
        winner["winning_candidate_selected_because_reaches_band"] = selected_because_band
        winner["winning_candidate_selected_from_band_reachers"] = selected_because_band
        winner["winner_pool_mode"] = winner_pool_mode
        winner["band_reacher_labels_considered"] = [str(c.get("label") or "")[:100] for c in band_reachers[:24]]
        winner["winning_candidate_goal_score"] = winner_goal_score
        winner["runner_up_goal_score"] = runner_up_goal_score
        winner["goal_tie_break_reason"] = goal_tie_break_reason
        winner["winning_candidate_goal_preference"] = (
            "shallower"
            if _design_optimisation_goal(dict(seed_candidate.get("state") or {})) == "shallower_beam"
            else "balanced"
        )
        if _design_guide_sidebar_debug_enabled():
            _merge_design_guide_rank_trace(
                {
                    "auto_design_goal_tie_break": {
                        "winning_candidate_goal_score": winner_goal_score,
                        "runner_up_goal_score": runner_up_goal_score,
                        "goal_tie_break_reason": goal_tie_break_reason,
                        "winning_candidate_goal_preference": winner.get("winning_candidate_goal_preference"),
                        "winner_label": str(winner.get("label") or ""),
                    },
                    "auto_design_final_selector": {
                        "winner_pool_mode": winner_pool_mode,
                        "selected_because_band": selected_because_band,
                        "final_winner_label": str(winner.get("label") or ""),
                        "final_winner_reaches_target_band": bool(winner.get("candidate_reaches_target_band")),
                        "final_winner_post_util": winner.get("candidate_post_util"),
                        "final_winner_goal_score": winner_goal_score,
                    },
                },
            )
    return winner


def _reinforcement_options_remain(state: dict) -> bool:
    count_1 = _int_from_state(state, "bot1_count", 0)
    count_2 = _int_from_state(state, "bot2_count", 0)
    dia_1 = _int_from_state(state, "db_bot_1", 0)
    dia_2 = _int_from_state(state, "db_bot_2", dia_1 or 0)
    can_increase_bar_count = count_1 < max(REO_COUNTS_0_12)
    can_grow_second_row = count_2 < max(REO_COUNTS_0_12)
    can_add_row = count_1 > 0 and count_2 <= 0
    can_increase_bar_dia = dia_1 < max(REO_BAR_DIAS) or dia_2 < max(REO_BAR_DIAS)
    can_rebalance = count_1 > 2 and count_1 != count_2
    return any((
        can_increase_bar_count,
        can_grow_second_row,
        can_add_row,
        can_increase_bar_dia,
        can_rebalance,
    ))


def _candidate_materially_improves(current_candidate: dict, trial_candidate: dict) -> bool:
    if not trial_candidate:
        return False
    current_worst = float(current_candidate.get("worst_util", float("inf")) or float("inf"))
    trial_worst = float(trial_candidate.get("worst_util", float("inf")) or float("inf"))
    if bool(trial_candidate.get("is_compliant")) and not bool(current_candidate.get("is_compliant")):
        return True
    return trial_worst < current_worst - 1e-6


def _geometry_changes_allowed(
    candidate: dict,
    goal: str,
    *,
    bottom_candidates: list[dict] | None = None,
    shear_candidates: list[dict] | None = None,
) -> bool:
    if _geometry_lock_enabled((candidate or {}).get("state") or {}):
        return False
    return True


def _generate_bottom_reo_candidates(state: dict, mode_config: dict) -> list[dict]:
    from section_layout import compute_bar_layout_pure
    started_at = time.perf_counter()

    # region agent log
    _agent_debug_log(
        "Entered bottom candidate generation",
        {
            "callers": [frame.function for frame in inspect.stack()[1:6]],
            "mode_label": str(mode_config.get("label") or ""),
        },
        location="inputs_page.py:_generate_bottom_reo_candidates",
        hypothesis_id="H12",
    )
    # endregion

    b = _design_width_value(state)
    cover_side = _float_from_state(state, "cover_side", 40.0)
    rowgap_bot = _float_from_state(state, "rowgap_bot", 60.0)
    candidates: list[dict] = []
    seed_candidate = _evaluate_auto_design_candidate(state, source="seed")
    arrangement_attempts = 0
    bending_preview_total_ms = 0.0
    full_eval_total_ms = 0.0
    required_ast_total_ms = 0.0
    updates_and_label_total_ms = 0.0
    layout_cache: dict[tuple[int, int], dict] = {}

    for dia in REO_BAR_DIAS:
        s_min = max(float(dia), 25.0)

        def _layout_for_count(count: int) -> dict:
            cache_key = (int(dia), int(count))
            cached = layout_cache.get(cache_key)
            if cached is not None:
                return cached
            layout = compute_bar_layout_pure(
                b=b,
                cover_side=cover_side,
                nb_or_s=float(count),
                db=float(dia),
                s_min=s_min,
                rowgap=rowgap_bot,
            )
            layout_cache[cache_key] = layout
            return layout

        for count_1 in range(2, 13):
            layout_1 = _layout_for_count(count_1)
            if not layout_1.get("fits_single_row", False):
                continue
            for count_2 in range(0, 13):
                if count_2 > 0:
                    layout_2 = _layout_for_count(count_2)
                    if not layout_2.get("fits_single_row", False):
                        continue
                arrangement = _normalise_bottom_layer_order({
                    "bot1_layout_mode": "Count",
                    "bot1_count": count_1,
                    "db_bot_1": dia,
                    "bot2_layout_mode": "Count",
                    "bot2_count": count_2,
                    "db_bot_2": dia,
                })
                arrangement_attempts += 1
                bending_started_at = time.perf_counter()
                bending = _evaluate_bending_with_bottom_state(state, arrangement)
                bending_preview_total_ms += (time.perf_counter() - bending_started_at) * 1000
                if not bending:
                    continue
                as_min = float(bending.get("As_min", 0.0) or 0.0)
                actual_ast = float(bending.get("Ast_bot", 0.0) or 0.0)
                if actual_ast < as_min:
                    continue
                updates_started_at = time.perf_counter()
                updates = _bottom_arrangement_to_shared_updates(arrangement)
                label = _practical_bottom_reo_label(
                    int(arrangement.get("bot1_count", 0)),
                    int(arrangement.get("bot2_count", 0)),
                    int(arrangement.get("db_bot_1", dia)),
                )
                updates_and_label_total_ms += (time.perf_counter() - updates_started_at) * 1000
                eval_started_at = time.perf_counter()
                candidate = _evaluate_auto_design_candidate(
                    state,
                    updates=updates,
                    source="bottom_reo",
                    label=label,
                    action_type="apply_bottom_recommendation",
                )
                full_eval_total_ms += (time.perf_counter() - eval_started_at) * 1000
                if candidate is None:
                    continue
                candidate["arrangement"] = arrangement
                candidate["actual_ast"] = actual_ast
                candidates.append(candidate)
    score_total_ms = 0.0
    for candidate in candidates:
        score_started_at = time.perf_counter()
        candidate["score"] = _score_auto_design_candidate(candidate, mode_config, seed_candidate)
        score_total_ms += (time.perf_counter() - score_started_at) * 1000
    sample_candidate = None
    for candidate in candidates:
        sample_components = candidate.get("bending_components", {})
        flexural_util = sample_components.get("flexural_util")
        if flexural_util is not None and flexural_util < 1.0:
            sample_candidate = candidate
            break
    if sample_candidate is not None:
        # region agent log
        _agent_debug_log(
            "Sample bottom candidate evaluation",
            {
                "label": str(sample_candidate.get("label") or ""),
                "updates": dict(sample_candidate.get("updates") or {}),
                "overview_utils": dict(sample_candidate.get("overview", {}).get("utils", {})),
                "overview_statuses": dict(sample_candidate.get("overview", {}).get("statuses", {})),
                "bending_components": dict(sample_candidate.get("bending_components", {})),
                "worst_util": float(sample_candidate.get("worst_util", 0.0) or 0.0),
                "is_compliant": bool(sample_candidate.get("is_compliant")),
            },
            location="inputs_page.py:_generate_bottom_reo_candidates",
            hypothesis_id="H9",
        )
        # endregion
    # region agent log
    _agent_debug_log(
        "Bottom candidate generation timing breakdown",
        {
            "mode_label": str(mode_config.get("label") or ""),
            "arrangement_attempts": arrangement_attempts,
            "candidate_count": len(candidates),
            "updates_and_label_total_ms": round(updates_and_label_total_ms, 1),
            "required_ast_total_ms": round(required_ast_total_ms, 1),
            "score_total_ms": round(score_total_ms, 1),
        },
        location="inputs_page.py:_generate_bottom_reo_candidates:breakdown",
        hypothesis_id="H22",
    )
    # endregion
    # region agent log
    _agent_debug_log(
        "Completed bottom candidate generation",
        {
            "mode_label": str(mode_config.get("label") or ""),
            "depth": float(state.get("D", 0.0) or 0.0),
            "width": float(state.get("b", 0.0) or 0.0),
            "arrangement_attempts": arrangement_attempts,
            "candidate_count": len(candidates),
            "layout_cache_size": len(layout_cache),
            "bending_preview_total_ms": round(bending_preview_total_ms, 1),
            "full_eval_total_ms": round(full_eval_total_ms, 1),
            "required_ast_total_ms": round(required_ast_total_ms, 1),
            "duration_ms": round((time.perf_counter() - started_at) * 1000, 1),
        },
        location="inputs_page.py:_generate_bottom_reo_candidates:end",
        hypothesis_id="H18",
    )
    # endregion
    return candidates


def _generate_shear_candidates(state: dict, mode_config: dict) -> list[dict]:
    candidates: list[dict] = []
    current_active = _shear_reinforcement_is_active(state)
    seed_candidate = _evaluate_auto_design_candidate(state, source="seed")
    seed_shear_util = (((seed_candidate or {}).get("overview") or {}).get("utils") or {}).get("shear")
    severity_band = _shear_severity_band(seed_shear_util)
    candidate_state_items: list[tuple[str, dict]] = []
    if current_active:
        candidate_legs = [2, 4, 6]
        candidate_dias = [dia for dia in REO_BAR_DIAS if dia <= 16]
        spacing_values = sorted(REO_SPACINGS, reverse=True)
    else:
        candidate_legs = [2]
        candidate_dias = [_starter_shear_diameter(state)]
        spacing_values = [_starter_shear_spacing(state)]
    for dia in candidate_dias:
        for legs in candidate_legs:
            for spacing in spacing_values:
                candidate_state = dict(state)
                candidate_state.update({
                    "lig_d": dia,
                    "lig_legs": legs,
                    "s_lig": float(spacing),
                })
                candidate_state_items.append((_shear_candidate_type(state, candidate_state), candidate_state))
    if _severe_shear_failure(seed_shear_util):
        candidate_state_items.extend(_generate_escalated_shear_states(state, severity_band=severity_band))
    deduped_items: dict[tuple, tuple[str, dict]] = {}
    for candidate_type, candidate_state in candidate_state_items:
        deduped_items[_make_auto_design_candidate_key(candidate_state)] = (candidate_type, candidate_state)
    for candidate_type, candidate_state in deduped_items.values():
        updates = {
            key: value
            for key, value in candidate_state.items()
            if key in SHARED_DEFAULTS and state.get(key) != value
        }
        if _invalid_shear_spacing_change_without_activation(
            state,
            candidate_state,
            source="_generate_shear_candidates",
        ):
            continue
        candidate = _evaluate_auto_design_candidate(
            state,
            updates=updates,
            source="shear",
            label=f"{candidate_type.title()}: {_shear_state_label(candidate_state)}",
            action_type="apply_shear_recommendation",
        )
        if candidate is None:
            _log_shear_candidate_debug(
                source="_generate_shear_candidates",
                candidate_state=candidate_state,
                candidate=None,
            )
            continue
        candidate["shear_candidate_type"] = candidate_type
        if seed_candidate is not None:
            candidate["score"] = _score_auto_design_candidate(candidate, mode_config, seed_candidate)
        _log_shear_candidate_debug(
            source="_generate_shear_candidates",
            candidate_state=candidate_state,
            candidate=candidate,
        )
        candidates.append(candidate)
    if _severe_shear_failure(seed_shear_util) and seed_candidate is not None:
        existing_keys = {_make_auto_design_candidate_key(dict(candidate.get("state") or {})) for candidate in candidates}
        ranked_base = sorted(
            candidates,
            key=lambda item: _shear_recommendation_rank_key(
                item,
                base_state=state,
                severity_band=severity_band,
                seed_shear_util=seed_shear_util,
            ),
        )[:4]
        for base_candidate in ranked_base:
            for combined_state in _generate_secondary_bending_tightening_states(base_candidate, limit=3):
                combined_key = _make_auto_design_candidate_key(combined_state)
                if combined_key in existing_keys:
                    continue
                combined_updates = {
                    key: value
                    for key, value in combined_state.items()
                    if key in SHARED_DEFAULTS and state.get(key) != value
                }
                combined_candidate = _evaluate_auto_design_candidate(
                    state,
                    updates=combined_updates,
                    source="shear_combined",
                    label=(
                        f"Combined: {_shear_state_label(combined_state)}"
                        f" + {_bottom_reo_state_label(combined_state)}"
                    ),
                    action_type="apply_shear_recommendation",
                )
                if combined_candidate is None:
                    continue
                combined_candidate["shear_candidate_type"] = "combined"
                combined_candidate["secondary_actions_combined"] = True
                combined_candidate["score"] = _score_auto_design_candidate(combined_candidate, mode_config, seed_candidate)
                candidates.append(combined_candidate)
                existing_keys.add(combined_key)
    if _severe_shear_failure(seed_shear_util) and seed_candidate is not None:
        _log_severe_shear_escalation(
            source="_generate_shear_candidates",
            seed_candidate=seed_candidate,
            severity_band=severity_band,
            candidates=candidates,
            selected=None,
        )
    return candidates


def _shear_governing_fallback_resolved_candidate(state: dict, mode_cfg: dict) -> dict | None:
    """
    When bounded geometry+bottom one-click finds nothing but shear governs, pick the best
    compliant option from the same shear enumeration used elsewhere so the guide can show
    apply_resolved_candidate + post-apply util (not only reduce_link_spacing steps).
    """
    if not isinstance(state, dict):
        return None
    evaluated_list = _generate_shear_candidates(state, mode_cfg)
    compliant = [c for c in evaluated_list if isinstance(c, dict) and bool(c.get("is_compliant"))]
    if not compliant:
        return None

    def _rank(c: dict) -> tuple[float, float]:
        try:
            wu = float(c.get("worst_util", 999.0) or 999.0)
        except (TypeError, ValueError):
            wu = 999.0
        su_raw = ((c.get("overview") or {}).get("utils") or {}).get("shear")
        try:
            su = float(su_raw) if su_raw is not None else wu
        except (TypeError, ValueError):
            su = wu
        return (wu, su)

    best = sorted(compliant, key=_rank)[0]
    merged_updates = dict(best.get("updates") or {})
    if not merged_updates:
        return None
    _annotate_candidate_target_band_metrics(best, mode_cfg)
    resolved = dict(best)
    post_util = best.get("candidate_post_util", best.get("worst_util"))
    try:
        post_util = float(post_util) if post_util is not None else None
    except (TypeError, ValueError):
        post_util = None
    tmin = float(mode_cfg.get("target_util_min", EFFICIENCY_TARGET_UTIL_MIN) or EFFICIENCY_TARGET_UTIL_MIN)
    tmax = float(mode_cfg.get("target_util_max", EFFICIENCY_TARGET_UTIL_MAX) or EFFICIENCY_TARGET_UTIL_MAX)
    reaches_band = bool(post_util is not None and tmin <= post_util <= tmax)
    resolved["candidate_reaches_target_band"] = reaches_band
    resolved["reaches_target_band"] = reaches_band
    resolved["updates"] = merged_updates
    resolved["action_type"] = "apply_resolved_candidate"
    resolved["guidance_change_lines"] = _guidance_change_lines_for_updates(state, merged_updates)
    subfamilies = _compound_subfamilies_from_updates(merged_updates)
    resolved["subfamilies"] = list(subfamilies)
    resolved["recommendation_family_tag"] = _family_tag_from_compound_updates(merged_updates, state)
    title, _, _ = _compound_guidance_title_reasoning_why(
        state,
        merged_updates,
        subfamilies,
        strengthening=True,
    )
    resolved["label"] = str(title or best.get("label") or "Apply shear reinforcement upgrade")
    return resolved


def _best_bottom_candidate_for_state(state: dict, mode_config: dict) -> dict | None:
    candidates = _generate_bottom_reo_candidates(state, mode_config)
    return _select_best_auto_design_candidate(candidates, mode_config, _evaluate_auto_design_candidate(state, source="seed"))


def _generate_geometry_candidates(
    state: dict,
    mode_config: dict,
    current_candidate: dict,
    *,
    bottom_candidates: list[dict] | None = None,
    shear_candidates: list[dict] | None = None,
) -> list[dict]:
    started_at = time.perf_counter()
    if _geometry_lock_enabled(state):
        return []
    goal = _design_optimisation_goal(state)
    if not _geometry_changes_allowed(
        current_candidate,
        goal,
        bottom_candidates=bottom_candidates,
        shear_candidates=shear_candidates,
    ):
        # region agent log
        _agent_debug_log(
            "Geometry candidates blocked",
            {
                "goal": goal,
                "current_is_compliant": bool(current_candidate.get("is_compliant")),
                "reinforcement_options_remain": _reinforcement_options_remain(current_candidate["state"]),
                "current_worst_util": float(current_candidate.get("worst_util", 0.0) or 0.0),
                "bottom_improvement_exists": any(_candidate_materially_improves(current_candidate, trial) for trial in (bottom_candidates or [])),
                "shear_improvement_exists": any(_candidate_materially_improves(current_candidate, trial) for trial in (shear_candidates or [])),
            },
            location="inputs_page.py:_generate_geometry_candidates",
            hypothesis_id="H8",
        )
        # endregion
        return []

    width_key, _, current_width = _resolve_geometry_width_context(state)
    current_depth = _float_from_state(state, "D", 600.0)
    depth_min = current_depth - (200.0 if goal == "shallower_beam" else 100.0)
    depth_max = current_depth + (150.0 if goal == "shallower_beam" else 200.0)
    width_min = current_width - 100.0
    width_max = current_width + 150.0
    width_start = max(250, int(math.floor(max(250.0, width_min) / 50.0) * 50))
    width_stop = int(math.ceil(width_max / 50.0) * 50) + 50
    depth_start = max(350, int(math.floor(max(350.0, depth_min) / 50.0) * 50))
    depth_stop = int(math.ceil(depth_max / 50.0) * 50) + 50
    # region agent log
    _agent_debug_log(
        "Geometry candidate search started",
        {
            "goal": goal,
            "width_key": width_key,
            "width_range": [width_start, width_stop, 50],
            "depth_range": [depth_start, depth_stop, 50],
            "candidate_grid_size": max(0, len(list(range(width_start, width_stop, 50)))) * max(0, len(list(range(depth_start, depth_stop, 50)))),
        },
        location="inputs_page.py:_generate_geometry_candidates:start",
        hypothesis_id="H10",
    )
    # endregion

    seed_candidate = _evaluate_auto_design_candidate(state, source="seed")
    candidates: list[dict] = []
    geometry_points_evaluated = 0
    for width in range(width_start, width_stop, 50):
        for depth in range(depth_start, depth_stop, 50):
            geometry_points_evaluated += 1
            geometry_updates = {width_key: float(width), "D": float(depth)}
            if width_key != "b":
                geometry_updates["b"] = float(width)
            combined_updates = dict(geometry_updates)
            candidate = _evaluate_auto_design_candidate(
                state,
                updates=combined_updates,
                source="geometry",
                label=f"{int(width)} x {int(depth)} mm",
                action_type="apply_geometry_recommendation",
            )
            if candidate is None:
                continue
            candidates.append(candidate)
    for candidate in candidates:
        candidate["score"] = _score_auto_design_candidate(candidate, mode_config, seed_candidate)
    # region agent log
    _agent_debug_log(
        "Geometry candidate search completed",
        {
            "goal": goal,
            "candidate_count": len(candidates),
            "geometry_points_evaluated": geometry_points_evaluated,
            "nested_bottom_calls": 0,
            "nested_bottom_total_ms": 0.0,
            "duration_ms": round((time.perf_counter() - started_at) * 1000, 1),
            "best_worst_util": min((float(candidate.get("worst_util", float("inf")) or float("inf")) for candidate in candidates), default=None),
        },
        location="inputs_page.py:_generate_geometry_candidates:end",
        hypothesis_id="H10",
    )
    # endregion
    return candidates


def _recommendation_search_allowed(state: dict) -> bool:
    design_context = _build_design_actions_context(state)
    guidance_state = dict(design_context.get("state") or _guidance_state_snapshot(state))
    overview = _collect_design_overview(guidance_state, context=design_context)
    return not _guidance_not_started(guidance_state, overview)


def _compute_bottom_reo_tightening_recommendation(state: dict) -> dict | None:
    state = _guidance_state_snapshot(state)
    current_bottom = _effective_bottom_design_state(state)
    current_ast = float(current_bottom.get("Ast_bot", 0.0) or 0.0)
    if current_ast <= 0.0:
        return None

    mode_config = _design_mode_config(_design_optimisation_goal(state))
    seed_candidate = evaluate_candidate_full(state, source="guidance_bottom_seed")
    if not seed_candidate:
        return None
    context = _build_auto_design_context(
        seed_candidate["state"],
        mode_config,
        reference_overview=seed_candidate.get("overview"),
    )
    eval_cache: dict = {}
    metrics = {
        "_reference_overview": seed_candidate.get("overview"),
        "generated_count": 0,
        "unique_eval_count": 0,
        "cache_hits": 0,
        "fast_eval_total_ms": 0.0,
        "cap_hit": False,
    }

    candidates: list[dict] = []
    for band in range(2):
        for arrangement in _generate_local_bottom_arrangements(state, mode_config, band=band, context=context):
            candidate_state = dict(state)
            candidate_state.update(_bottom_arrangement_to_shared_updates(arrangement))
            candidate = _evaluate_candidate_fast(
                candidate_state,
                seed_state=seed_candidate["state"],
                context=context,
                eval_cache=eval_cache,
                metrics=metrics,
                source="guidance_bottom_tighten",
                label=_practical_bottom_reo_label(
                    int(arrangement.get("bot1_count", 0) or 0),
                    int(arrangement.get("bot2_count", 0) or 0),
                    int(arrangement.get("db_bot_1", 0) or 0),
                ),
                action_type="reduce_bottom_reinforcement",
            )
            if candidate is None:
                continue
            actual_ast = float(candidate.get("Ast_bot", 0.0) or 0.0)
            if not bool(candidate.get("is_compliant")) or actual_ast >= current_ast - 1e-6:
                continue
            candidate["actual_ast"] = actual_ast
            candidate["arrangement"] = arrangement
            candidates.append(candidate)

    if not candidates:
        return None

    best = min(
        candidates,
        key=lambda item: (
            0 if EFFICIENCY_TARGET_UTIL_MIN <= float(item.get("overview", {}).get("utils", {}).get("bending", 0.0) or 0.0) <= EFFICIENCY_TARGET_UTIL_MAX else 1,
            abs(float(item.get("overview", {}).get("utils", {}).get("bending", 0.0) or 0.0) - 0.85),
            int(item.get("row_count", 1) or 1),
            int(item.get("bar_count", 0) or 0),
            float(item.get("Ast_bot", 0.0) or 0.0),
        ),
    )
    return {
        "arrangement": dict(best.get("arrangement") or {}),
        "updates": _bottom_arrangement_to_shared_updates(dict(best.get("arrangement") or {})),
        "actual_ast": float(best.get("actual_ast", 0.0) or 0.0),
        "util": float(best.get("overview", {}).get("utils", {}).get("bending", 0.0) or 0.0),
        "label": str(best.get("label") or ""),
        "score": float(best.get("score", 0.0) or 0.0),
        "candidate_summary": _candidate_debug_summary(best),
        "candidate_type": "bottom",
    }


def _compute_shear_tightening_recommendation(state: dict) -> dict | None:
    state = _guidance_state_snapshot(state)
    design_context = _build_design_actions_context(state)
    overview = _collect_design_overview(state, context=design_context)
    if not _shear_change_is_relevant(overview, design_context.get("actions") or {}) and not _shear_cleanup_possible(state):
        return None
    if not _shear_reinforcement_is_active(state):
        return None
    actions = design_context.get("actions") or {}
    if _shear_demands_negligible(actions):
        full_clear = _try_shear_no_demand_cleanup_recommendation(state, overview, actions)
        if full_clear:
            return {
                "updates": dict(full_clear.get("updates") or {}),
                "label": str(full_clear.get("label") or ""),
                "util": float(full_clear.get("util", 0.0) or 0.0),
                "web_util": float(full_clear.get("web_util", 0.0) or 0.0),
                "action_type": "apply_shear_recommendation",
                "score": 0.0,
                "candidate_type": "no_shear_design_cleanup",
            }
    current_spacing = float(state.get("s_lig", 200.0) or 200.0)
    current_legs = int(state.get("lig_legs", 2) or 2)
    current_dia = int(state.get("lig_d", 10) or 10)
    current_density = (current_legs * max(current_dia, 1) ** 2) / max(current_spacing, 1.0)

    mode_config = _design_mode_config(_design_optimisation_goal(state))
    seed_candidate = evaluate_candidate_full(state, source="guidance_shear_seed")
    if not seed_candidate:
        return None
    context = _build_auto_design_context(
        seed_candidate["state"],
        mode_config,
        reference_overview=seed_candidate.get("overview"),
    )
    eval_cache: dict = {}
    metrics = {
        "_reference_overview": seed_candidate.get("overview"),
        "generated_count": 0,
        "unique_eval_count": 0,
        "cache_hits": 0,
        "fast_eval_total_ms": 0.0,
        "cap_hit": False,
    }

    candidates: list[dict] = []
    for candidate_state in generate_less_shear_reo_variants(seed_candidate, mode_config):
        candidate = _evaluate_candidate_fast(
            candidate_state,
            seed_state=seed_candidate["state"],
            context=context,
            eval_cache=eval_cache,
            metrics=metrics,
            source="guidance_shear_tighten",
            label=_shear_state_label(candidate_state),
            action_type="increase_link_spacing",
        )
        if _invalid_shear_spacing_change_without_activation(
            state,
            candidate_state,
            source="guidance_shear_tighten",
        ):
            continue
        if candidate is None or not bool(candidate.get("is_compliant")):
            _log_shear_candidate_debug(
                source="guidance_shear_tighten",
                candidate_state=candidate_state,
                candidate=candidate,
            )
            continue
        candidate["score"] = _score_auto_design_candidate(candidate, mode_config, seed_candidate)
        _log_shear_candidate_debug(
            source="guidance_shear_tighten",
            candidate_state=candidate_state,
            candidate=candidate,
        )
        spacing = float(candidate_state.get("s_lig", current_spacing) or current_spacing)
        legs = int(candidate_state.get("lig_legs", current_legs) or current_legs)
        dia = int(candidate_state.get("lig_d", current_dia) or current_dia)
        candidate_density = (legs * max(dia, 1) ** 2) / max(spacing, 1.0)
        if candidate_density >= current_density - 1e-9:
            continue
        spacing_increase = max(spacing - current_spacing, 0.0)
        leg_reduction = max(current_legs - legs, 0)
        dia_reduction = max(current_dia - dia, 0)
        if spacing_increase <= 0.0 and leg_reduction <= 0 and dia_reduction <= 0:
            continue
        candidate["action_type"] = "increase_link_spacing" if spacing_increase > 0.0 else "reduce_number_of_legs"
        candidate["label"] = f"{legs}-leg N{dia} @ {int(spacing)}"
        candidates.append(candidate)

    if not candidates:
        return None

    best = min(
        candidates,
        key=lambda item: (
            0 if EFFICIENCY_TARGET_UTIL_MIN <= float(item.get("overview", {}).get("utils", {}).get("shear", 0.0) or 0.0) <= EFFICIENCY_TARGET_UTIL_MAX else 1,
            abs(float(item.get("overview", {}).get("utils", {}).get("shear", 0.0) or 0.0) - 0.85),
            0 if str(item.get("action_type") or "") == "increase_link_spacing" else 1,
            -float(item.get("state", {}).get("s_lig", current_spacing) or current_spacing),
            int(item.get("state", {}).get("lig_legs", current_legs) or current_legs),
            int(item.get("state", {}).get("lig_d", current_dia) or current_dia),
        ),
    )
    preview = _shear_preview_for_updates(state, dict(best.get("updates") or {})) or {}
    ct = "no_shear_design_cleanup" if str(best.get("candidate_type") or "") == "no_shear_design_cleanup" else "shear"
    return {
        "updates": dict(best.get("updates") or {}),
        "label": str(best.get("label") or ""),
        "util": float(best.get("overview", {}).get("utils", {}).get("shear", 0.0) or 0.0),
        "web_util": float(preview.get("web_util", best.get("overview", {}).get("utils", {}).get("shear", 0.0)) or 0.0),
        "action_type": str(best.get("action_type") or "increase_link_spacing"),
        "score": float(best.get("score", 0.0) or 0.0),
        "candidate_summary": _candidate_debug_summary(best),
        "candidate_type": ct,
    }


def _geometry_tightening_trial_updates(state: dict) -> list[dict]:
    goal = _design_optimisation_goal(state)
    width_key, _, current_width = _resolve_geometry_width_context(state)
    current_depth = _float_from_state(state, "D", 600.0)
    unique_updates: dict[tuple[tuple[str, str], ...], dict] = {}

    def _add_trial(width: float, depth: float) -> None:
        rounded_width = float(int(round(max(250.0, width) / 10.0) * 10))
        rounded_depth = float(int(round(max(350.0, depth) / 10.0) * 10))
        updates = {width_key: rounded_width, "D": rounded_depth}
        if width_key != "b":
            updates["b"] = rounded_width
        if _updates_match_state(state, updates):
            return
        signature = tuple(sorted((key, str(value)) for key, value in updates.items()))
        unique_updates[signature] = updates

    if goal == "shallower_beam":
        _add_trial(current_width, current_depth - 100.0)
        _add_trial(current_width, current_depth - 50.0)
        _add_trial(current_width - 50.0, current_depth - 50.0)
        _add_trial(current_width - 50.0, current_depth)
    elif goal == "balanced":
        _add_trial(current_width, current_depth - 50.0)
        _add_trial(current_width - 50.0, current_depth)
        _add_trial(current_width - 50.0, current_depth - 50.0)
    elif goal == "less_longitudinal_reinforcement":
        _add_trial(current_width, current_depth - 50.0)
        _add_trial(current_width - 50.0, current_depth)
    else:
        _add_trial(current_width, current_depth - 50.0)

    return list(unique_updates.values())


def _compute_geometry_tightening_recommendation(state: dict) -> dict | None:
    state = _guidance_state_snapshot(state)
    if _geometry_lock_enabled(state):
        return None
    seed_candidate = evaluate_candidate_full(state, source="guidance_geometry_seed")
    if not seed_candidate or not bool(seed_candidate.get("is_compliant")):
        return None

    mode_config = _design_mode_config(_design_optimisation_goal(state))
    current_score = _score_auto_design_candidate(seed_candidate, mode_config, seed_candidate)
    context = _build_auto_design_context(
        seed_candidate["state"],
        mode_config,
        reference_overview=seed_candidate.get("overview"),
    )
    eval_cache: dict = {}
    metrics = {
        "_reference_overview": seed_candidate.get("overview"),
        "generated_count": 0,
        "unique_eval_count": 0,
        "cache_hits": 0,
        "fast_eval_total_ms": 0.0,
        "cap_hit": False,
    }
    candidates: list[dict] = []
    for updates in _geometry_tightening_trial_updates(state):
        width_key, _, _ = _resolve_geometry_width_context(state)
        trial_width = float(updates.get(width_key, updates.get("b", 0.0)) or 0.0)
        trial_depth = float(updates.get("D", 0.0) or 0.0)
        candidate_state = dict(state)
        candidate_state.update(updates)
        candidate = _evaluate_candidate_fast(
            candidate_state,
            seed_state=seed_candidate["state"],
            context=context,
            eval_cache=eval_cache,
            metrics=metrics,
            source="geometry_tighten",
            label=f"{int(trial_width)} x {int(trial_depth)} mm",
            action_type="tighten_geometry",
        )
        if candidate is None or not bool(candidate.get("is_compliant")):
            continue
        candidate["score"] = _score_auto_design_candidate(candidate, mode_config, seed_candidate)
        candidates.append(candidate)

    if not candidates:
        return None

    best = min(
        candidates,
        key=lambda item: (
            float(item.get("score", float("inf"))),
            0 if _candidate_in_target_band(item, mode_config) else 1,
            float(item.get("depth", 0.0) or 0.0),
            float(item.get("width", 0.0) or 0.0),
        ),
    )
    if float(best.get("score", float("inf"))) >= current_score - 1e-6:
        return None

    width_key, width_label, _ = _resolve_geometry_width_context(state)
    return {
        "updates": dict(best.get("updates") or {}),
        "width_key": width_key,
        "width_label": width_label,
        "width": float(best.get("width", 0.0) or 0.0),
        "depth": float(best.get("depth", 0.0) or 0.0),
        "util": float(best.get("worst_util", 0.0) or 0.0),
        "score": float(best.get("score", 0.0) or 0.0),
        "label": str(best.get("label") or ""),
        "candidate_summary": _candidate_debug_summary(best),
        "candidate_type": "geometry",
    }


def _guidance_objective_util_from_overview(overview: dict, goal: str) -> float | None:
    utils = dict((overview or {}).get("utils") or {})
    bend_pack = ((overview or {}).get("packs") or {}).get("bending") or {}
    phi_m = float(bend_pack.get("summary_phiMu_kNm", 0.0) or 0.0)
    mu_m = float(bend_pack.get("summary_Mu_star_kNm", 0.0) or 0.0)
    bend_demand = (mu_m / phi_m) if phi_m > 1e-9 else None
    if goal == "less_shear_reinforcement":
        value = utils.get("shear")
        return None if value is None else float(value)
    candidates = [value for value in (bend_demand, utils.get("bending"), utils.get("shear")) if value is not None]
    if not candidates:
        return None
    return max(float(value) for value in candidates)


def _mode_recommendation_expected_bend_util(mode_tighten: dict | None) -> float | None:
    """Mu*/φMu for the recommended trial; avoids stale objective_util / worst_util."""
    if not isinstance(mode_tighten, dict):
        return None
    for key in ("expected_util", "real_util"):
        raw = mode_tighten.get(key)
        if raw is None:
            continue
        try:
            v = float(raw)
        except Exception:
            continue
        if not math.isnan(v):
            return v
    cs = mode_tighten.get("candidate_summary") or {}
    phi_m = float(cs.get("summary_phiMu_kNm", 0.0) or 0.0)
    mu_m = float(cs.get("summary_Mu_star_kNm", 0.0) or 0.0)
    if phi_m > 1e-9:
        return mu_m / phi_m
    return None


def _mode_guidance_focus_from_updates(updates: dict) -> str:
    geometry_keys = {"D", "b", "bw", "tw"}
    bottom_keys = {
        "bot_row_count",
        "bot1_layout_mode",
        "bot1_count",
        "db_bot_1",
        "bot2_layout_mode",
        "bot2_count",
        "db_bot_2",
        "bot_row_1_mode",
        "bot_row_1_bars",
        "bot_row_1_spacing",
        "bot_row_1_dia",
        "bot_row_2_mode",
        "bot_row_2_bars",
        "bot_row_2_spacing",
        "bot_row_2_dia",
    }
    shear_keys = {"lig_d", "lig_legs", "s_lig"}
    if any(key in updates for key in geometry_keys):
        return "geometry"
    if any(key in updates for key in bottom_keys):
        return "bending"
    if any(key in updates for key in shear_keys):
        return "shear"
    return "general"


def _guidance_action_to_payload_name(action_type: str) -> str | None:
    mapping = {
        "apply_mode_recommendation": "mode_tightening",
        "apply_bottom_recommendation": "bottom_tightening",
        "apply_geometry_recommendation": "geometry_tightening",
        "apply_shear_recommendation": "shear_tightening",
        "reduce_bottom_reinforcement": "bottom_tightening",
        "reduce_bar_spacing": "bottom_tightening",
        "tighten_geometry": "geometry_tightening",
        "increase_depth": "geometry_tightening",
        "increase_width": "geometry_tightening",
        "reduce_link_spacing": "shear_tightening",
        "increase_link_spacing": "shear_tightening",
        "reduce_number_of_legs": "shear_tightening",
        "deflection_reduce_sustained_load": "general",
    }
    return mapping.get(str(action_type or ""))


def _is_design_guide_good_utilisation_band(util: object) -> bool:
    if util is None:
        return False
    try:
        u = float(util)
    except (TypeError, ValueError):
        return False
    return (not math.isnan(u)) and 0.80 <= u <= 0.95


def _is_design_guide_terminal_safe_item(item: dict) -> bool:
    title = str(item.get("title_main") or "")
    primary = str(item.get("primary_action") or "")
    hay = f"{title} {primary}".lower()
    needles = (
        "no further safe local reductions",
        "no further local reductions",
        "no further recommendations",
        "critical case solved",
        "reducing non-critical provisions has reached a safe limit",
        "geometry locked for optimisation",
        "geometry locked. optimisation is limited",
    )
    return any(n in hay for n in needles)


def _design_guide_primary_uses_success_style(item: dict) -> bool:
    """Green 'done' card: resolved safe/complete only, not active fix recommendations."""
    bucket = str(item.get("bucket") or "")
    if bucket == "fail":
        return False
    if bucket == "start":
        return False
    has_apply = bool(item.get("action_type"))
    if has_apply and bucket in ("fail", "warn", "efficiency"):
        return False
    if bucket == "warn" and not _is_design_guide_terminal_safe_item(item):
        return False
    terminal = _is_design_guide_terminal_safe_item(item)
    good_band = _is_design_guide_good_utilisation_band(item.get("util"))
    if terminal:
        return True
    if good_band and bucket == "pass":
        return True
    return False


def _render_guidance_secondary_items(
    guidance_items: list[dict],
    *,
    guidance_disp_state: dict,
    inputs_render_audit: dict[str, str] | None = None,
    start_index: int = 0,
) -> None:
    for idx, item in enumerate(guidance_items):
        if idx < start_index:
            continue
        badge_label = _guidance_card_label(item)
        item_bucket = item["bucket"] if idx == 0 and start_index == 0 else ("warn" if item["bucket"] == "fail" else item["bucket"])
        if idx == 0 and start_index == 0 and item_bucket == "fail":
            util_v = _parse_util_value(item.get("util"))
            if util_v is not None and util_v <= 1.0:
                # Display-only: recommendation card at/under 100% shows close/warn styling.
                item_bucket = "warn"
        is_static = not item.get("action_type")
        before_after = item.get("guidance_before_after") or _guidance_before_after_text(item, guidance_disp_state)
        use_success_style = (
            idx == 0
            and start_index == 0
            and _design_guide_primary_uses_success_style(item)
        )
        anchor_class = (
            "fast-guidance-action-anchor "
            f"fast-guidance-action-anchor--{item_bucket} "
            + ("fast-guidance-action-anchor--primary" if idx == 0 and start_index == 0 else "fast-guidance-action-anchor--secondary")
            + (" fast-guidance-action-anchor--static" if is_static else "")
        )
        if use_success_style:
            card_class = "fast-guidance-item pass guidance-success"
        else:
            card_class = f"fast-guidance-item {item_bucket}"
        if idx > 0 or start_index > 0:
            card_class += " secondary"
        badge_class = (
            f"fast-guidance-badge {item_bucket} guidance-success"
            if use_success_style
            else f"fast-guidance-badge {item_bucket}"
        )
        compact_primary_actionable = bool(idx == 0 and start_index == 0 and item.get("action_type"))
        before_after_html = (
            f"<div class='fast-guidance-secondary'><strong>Before -&gt; After</strong><br>{html.escape(before_after)}</div>"
            if before_after else
            (
                f"<div class='fast-guidance-secondary'><strong>Alternative</strong><br>{html.escape(item['secondary_action'])}</div>"
                if item.get("secondary_action") else ""
            )
        )
        title_util_html = (
            f"<span class='fast-guidance-title-util'>{html.escape(item['title_util'])}</span>"
            if item.get("title_util") else ""
        )
        start_steps_html = ""
        if item_bucket == "start":
            start_steps = item.get("start_steps") or []
            if start_steps:
                start_steps_html = (
                    "<ul class='fast-guidance-list'>"
                    + "".join(f"<li>{html.escape(step)}</li>" for step in start_steps)
                    + "</ul>"
                )
        why_body = _guidance_card_why_body(item)
        why_html = (
            f"<div class='fast-guidance-reason'><strong>Why</strong><br>{html.escape(why_body)}</div>"
            if why_body
            else f"<div class='fast-guidance-reason'>{html.escape(str(item.get('reasoning') or ''))}</div>"
        )
        proposed_html = (
            _guidance_card_proposed_change_html(item, guidance_disp_state)
            if item.get("action_type")
            else ""
        )
        compact_primary_html = (
            _guidance_primary_compact_lines_html(item, guidance_disp_state)
            if compact_primary_actionable
            else ""
        )
        body_html = (
            compact_primary_html
            if compact_primary_actionable
            else f"{why_html}{proposed_html}{start_steps_html}{before_after_html}"
        )
        card_html = (
            f"<div class='{card_class}'>"
            f"<div class='fast-guidance-head'>"
            f"<span class='{badge_class}'>{html.escape(badge_label)}</span>"
            f"<span class='fast-guidance-title-wrap'>"
            f"<span class='fast-guidance-title'>{html.escape(item['title_main'])}</span>"
            f"{title_util_html}"
            f"</span>"
            f"</div>"
            f"{body_html}"
            f"</div>"
        )
        if inputs_render_audit is not None:
            _at = str(item.get("action_type") or "")
            _st = str(item.get("status") or "")
            if _at == "apply_mode_recommendation":
                inputs_render_audit["next_mode_recommendation_rendered"] = "yes"
            if _st == "EFFICIENCY":
                if _at == "reduce_bottom_reinforcement":
                    inputs_render_audit["bottom_tightening_rendered"] = "yes"
                elif _at == "tighten_geometry":
                    inputs_render_audit["geometry_tightening_rendered"] = "yes"
                elif _at in ("increase_link_spacing", "reduce_number_of_legs", "apply_shear_recommendation"):
                    inputs_render_audit["shear_tightening_rendered"] = "yes"
        st.markdown(card_html, unsafe_allow_html=True)
        if item.get("action_type"):
            st.markdown(f"<div class='{anchor_class}'></div>", unsafe_allow_html=True)
            guidance_pressed = st.button(
                item["primary_action"],
                key=f"fast_guidance_apply_{idx}_{item.get('action_type') or 'static'}",
                type="secondary",
                use_container_width=True,
                disabled=is_static,
            )
            _agent_debug_log(
                "Rendered fast guidance action button",
                {
                    "index": idx,
                    "title": str(item.get("title_main") or ""),
                    "action_type": str(item.get("action_type") or ""),
                    "pressed": bool(guidance_pressed),
                    "button_key": f"fast_guidance_apply_{idx}_{item.get('action_type') or 'static'}",
                },
                location="inputs_page.py:_render_guidance_secondary_items",
                hypothesis_id="H17",
            )
            if guidance_pressed:
                if idx == 0 and start_index == 0:
                    _apply_current_guidance_item(item)
                else:
                    apply_guidance_action(item["action_type"], item.get("action_payload") or {})
        elif item.get("primary_action"):
            st.markdown(
                f"<div class='fast-guidance-secondary'><strong>Status</strong><br>{html.escape(item['primary_action'])}</div>",
                unsafe_allow_html=True,
            )


def _apply_current_guidance_item(item: dict | None) -> bool:
    if not isinstance(item, dict):
        return False
    action_type = str(item.get("action_type") or "").strip()
    if not action_type:
        return False
    payload = dict(item.get("action_payload") or {})
    current_route = dict(st.session_state.get(DESIGN_GUIDE_LAST_APPLY_ROUTE_KEY) or {})
    label = str(
        payload.get("resolved_candidate_label")
        or item.get("title_main")
        or "",
    )
    st.session_state[DESIGN_GUIDE_LAST_APPLY_ROUTE_KEY] = {
        **current_route,
        "ui_clicked_action_type": action_type,
        "ui_clicked_has_resolved_payload": bool(payload.get("resolved_candidate_updates")),
        "post_apply_resolved_candidate_attempted": action_type == "apply_resolved_candidate",
        "ui_clicked_label": label,
    }
    current_state = _shared_state_snapshot()
    pre_overview = _collect_design_overview(
        current_state,
        context=_build_design_actions_context(current_state),
    )
    bundle = st.session_state.get(DESIGN_GUIDE_DEBUG_BUNDLE_KEY) or {}
    st.session_state[DESIGN_GUIDE_PENDING_STEP_CTX_KEY] = {
        "guidance_branch_before": bundle.get("guidance_branch"),
        "recommendation_title": str(item.get("title_main") or ""),
        "recommendation_label_at_step_start": label,
        "recommendation_action_type_at_step_start": action_type,
        "action_type": action_type,
        "payload": payload,
        "pre_overview": pre_overview,
        "used_resolved_payload": bool(payload.get("resolved_candidate_updates")),
        "one_click_candidate_available_at_step_start": bool(
            action_type == "apply_resolved_candidate" and payload.get("resolved_candidate_updates"),
        ),
        "one_click_candidate_label_at_step_start": payload.get("resolved_candidate_label"),
    }
    if action_type == "apply_resolved_candidate":
        return _apply_resolved_candidate_payload(payload)
    return apply_guidance_action(action_type, payload)


def _compute_mode_guidance_recommendation_uncached(state: dict) -> dict | None:
    state = _guidance_state_snapshot(state)
    if not _recommendation_search_allowed(state):
        return None
    seed_candidate = _evaluate_auto_design_candidate(state, source="guidance_seed")
    if not seed_candidate or not bool(seed_candidate.get("is_compliant")):
        return None
    mode = _design_optimisation_goal(state)
    optimiser_result = run_full_auto_design(seed_candidate, mode, force=False)
    best_candidate = _materialize_full_evaluated_candidate(
        (optimiser_result or {}).get("candidate"),
        source="mode_guidance_selected_full",
    )
    if not best_candidate:
        return None
    updates = dict(best_candidate.get("updates") or {})
    if not updates or _updates_match_state(state, updates):
        return None
    current_summary = _candidate_debug_summary(seed_candidate) or {}
    candidate_summary = _candidate_debug_summary(best_candidate) or {}
    current_ast = float(current_summary.get("Ast_bot", 0.0) or 0.0)
    recommended_ast = float(candidate_summary.get("Ast_bot", 0.0) or 0.0)
    governing_focus = _governing_focus_from_overview(seed_candidate.get("overview") or {})
    focus = _mode_guidance_focus_from_updates(updates)
    heavier_for_tightening = recommended_ast > current_ast + 1e-6
    if bool(st.session_state.get("_dev_mode")) and heavier_for_tightening:
        non_bending_reason = focus != "bending" or governing_focus != "bending"
        _agent_debug_log(
            "Heavier candidate produced for tightening recommendation",
            {
                "warning": not non_bending_reason,
                "current_candidate": current_summary,
                "recommended_candidate": candidate_summary,
                "governing_focus": governing_focus,
                "recommendation_focus": focus,
                "non_bending_reason_identified": non_bending_reason,
            },
            location="inputs_page.py:_compute_mode_guidance_recommendation_uncached",
            hypothesis_id="H307",
        )
    phi_m = float(candidate_summary.get("summary_phiMu_kNm", 0.0) or 0.0)
    mu_m = float(candidate_summary.get("summary_Mu_star_kNm", 0.0) or 0.0)
    expected_bend_util = (mu_m / phi_m) if phi_m > 1e-9 else None
    expected_util = expected_bend_util
    mode_goal = _design_optimisation_goal(best_candidate.get("state") or seed_candidate.get("state") or {})
    if mode_goal == "less_shear_reinforcement":
        su = ((best_candidate.get("overview") or {}).get("utils") or {}).get("shear")
        try:
            if su is not None and not math.isnan(float(su)):
                expected_util = float(su)
        except Exception:
            pass
    recommendation = {
        "updates": updates,
        "label": str(best_candidate.get("label") or ""),
        "focus": focus,
        "score": float(best_candidate.get("score", 0.0) or 0.0),
        "optimisation_score": float(_candidate_objective_util(best_candidate)),
        "expected_util": expected_util,
        "real_util": candidate_summary.get("real_util"),
        "material_change": bool((optimiser_result or {}).get("material_change")),
        "candidate_summary": candidate_summary,
        "candidate_type": "mode",
    }
    if bool(st.session_state.get("_dev_mode")):
        fast_candidate = (optimiser_result or {}).get("candidate")
        _agent_debug_log(
            "Computed mode guidance recommendation",
            {
                "solver_seed": current_summary,
                "selected_candidate": candidate_summary,
                "selected_candidate_fast_eval": _candidate_debug_summary(fast_candidate),
                "recommendation": recommendation,
                "fast_vs_full_compare": {
                    "fast": _candidate_debug_summary(fast_candidate),
                    "full": candidate_summary,
                },
                "selection_metrics": (optimiser_result or {}).get("metrics"),
            },
            location="inputs_page.py:_compute_mode_guidance_recommendation_uncached",
            hypothesis_id="H305",
        )
    return recommendation


def _compute_mode_guidance_recommendation(state: dict) -> dict | None:
    cached = _cached_recommendation("mode_guidance", state)
    if cached is not None:
        if isinstance(cached, dict):
            upd = cached.get("updates") or {}
            if upd and not _updates_match_state(state, upd):
                return cached
        st.session_state.pop("_recommendation_cache_mode_guidance", None)
    recommendation = _compute_mode_guidance_recommendation_uncached(state)
    _store_cached_recommendation("mode_guidance", state, recommendation)
    return recommendation


def _recommendation_preview_util(recommendation: dict | None) -> float | None:
    if not isinstance(recommendation, dict):
        return None
    mode_util = _mode_recommendation_expected_bend_util(recommendation)
    if mode_util is not None:
        return mode_util
    values: list[float] = []
    for key in ("util", "real_util", "bending_util", "shear_util"):
        value = recommendation.get(key)
        try:
            resolved = float(value)
        except Exception:
            continue
        if not math.isnan(resolved):
            values.append(resolved)
    if values:
        return max(values)
    return None


def _materialize_guidance_candidate(base_candidate: dict | None, recommendation: dict | None, *, source: str) -> dict | None:
    if not base_candidate or not isinstance(recommendation, dict):
        return None
    updates = dict(recommendation.get("updates") or recommendation.get("arrangement") or {})
    if not updates:
        return None
    candidate = _evaluate_auto_design_candidate(
        base_candidate.get("state") or {},
        updates=updates,
        source=source,
        label=str(recommendation.get("label") or source.replace("_", " ").title()),
        action_type="auto_design",
    )
    if candidate is not None:
        candidate["guidance_preview_util"] = _recommendation_preview_util(recommendation)
    return candidate


def _guidance_candidate_for_refinement_start(base_candidate: dict | None, efficiency_state: dict | None, mode_config: dict) -> dict | None:
    if not base_candidate or not isinstance(efficiency_state, dict):
        return None
    current_util = float((base_candidate or {}).get("worst_util", 0.0) or 0.0)
    recommendation_specs = [
        ("bottom_tightening", "guidance_bottom_seed"),
        ("mode_tightening", "guidance_mode_seed"),
        ("geometry_tightening", "guidance_geometry_seed"),
    ]
    for key, source in recommendation_specs:
        recommendation = efficiency_state.get(key)
        preview_util = _recommendation_preview_util(recommendation)
        if preview_util is None or preview_util <= current_util + 1e-9:
            continue
        candidate = _materialize_guidance_candidate(base_candidate, recommendation, source=source)
        if candidate is None or not bool(candidate.get("is_compliant")):
            continue
        candidate_util = float(candidate.get("worst_util", 0.0) or 0.0)
        if candidate_materially_worsens(candidate, base_candidate, mode_config, phase="guidance_seed"):
            continue
        if candidate_util <= current_util + 1e-9:
            continue
        _agent_debug_log(
            "Injecting guidance candidate into refinement start",
            {
                "current_util": current_util,
                "guidance_util": candidate_util,
                "guidance_preview_util": preview_util,
                "guidance_label": recommendation.get("label"),
            },
            location="inputs_page.py:auto_design_start",
            hypothesis_id="H201",
        )
        return candidate
    return None


def _shear_change_is_relevant(overview: dict, actions: dict) -> bool:
    Vu = float(actions.get("Vu", 0.0) or 0.0)
    shear_util = float((((overview or {}).get("utils") or {}).get("shear", 0.0)) or 0.0)
    if Vu <= 0.0:
        return False
    if shear_util < 0.20:
        return False
    return True


def _is_in_target_zone(overview: dict, mode_config: dict) -> bool:
    worst_util = float((overview or {}).get("worst_util", 0.0) or 0.0)
    return float(mode_config["target_util_min"]) <= worst_util <= float(mode_config["target_util_max"])


def _is_in_target_zone_with_eps(overview: dict, mode_config: dict, *, eps: float = TARGET_BAND_EPS) -> bool:
    worst_util = float((overview or {}).get("worst_util", 0.0) or 0.0)
    lo = float(mode_config.get("target_util_min", EFFICIENCY_TARGET_UTIL_MIN) or EFFICIENCY_TARGET_UTIL_MIN)
    hi = float(mode_config.get("target_util_max", EFFICIENCY_TARGET_UTIL_MAX) or EFFICIENCY_TARGET_UTIL_MAX)
    return lo <= worst_util <= (hi + float(eps))


def _efficiency_state_has_valid_candidate(efficiency_state: dict) -> bool:
    if not isinstance(efficiency_state, dict):
        return False
    return any(
        efficiency_state.get(key) is not None
        for key in ("mode_tightening", "bottom_tightening", "shear_tightening", "geometry_tightening")
    )


def _efficiency_reduction_profile_from_overview(overview: dict | None) -> bool:
    if not isinstance(overview, dict):
        return False
    if not bool(overview.get("all_key_pass")) or bool(overview.get("any_fail")):
        return False
    try:
        worst = float(overview.get("worst_util", 0.0) or 0.0)
    except (TypeError, ValueError):
        return False
    return worst < float(GUIDANCE_UNDERSIZED_DONE_BLOCK_UTIL)


def _shear_change_is_reinforcement_growth(seed_state: dict, cand_state: dict) -> bool:
    sd = _int_from_state(seed_state, "lig_d", 0)
    sl = _int_from_state(seed_state, "lig_legs", 0)
    cd = _int_from_state(cand_state, "lig_d", 0)
    cl = _int_from_state(cand_state, "lig_legs", 0)
    ss = _float_from_state(seed_state, "s_lig", 200.0)
    cs = _float_from_state(cand_state, "s_lig", 200.0)
    if sd <= 0 and sl < 2 and cd <= 0 and cl < 2:
        return False
    if cd <= 0 and cl < 2 and (sd > 0 or sl >= 2):
        return False
    if cd > sd or cl > sl:
        return True
    if cd > 0 and cl >= 2 and sd > 0 and sl >= 2 and cs < ss - 1e-9:
        return True
    return False


def _candidate_is_growth_move(seed_candidate: dict, candidate: dict) -> bool:
    if not seed_candidate or not candidate:
        return False
    seed_st = dict(seed_candidate.get("state") or {})
    cand_st = dict(candidate.get("state") or {})
    d0 = float(seed_candidate.get("depth", _float_from_state(seed_st, "D", 0.0)) or _float_from_state(seed_st, "D", 0.0))
    d1 = float(candidate.get("depth", _float_from_state(cand_st, "D", 0.0)) or _float_from_state(cand_st, "D", 0.0))
    if d1 > d0 + 1e-9:
        return True
    _, _, w0 = _resolve_geometry_width_context(seed_st)
    w0 = float(w0 or 0.0)
    w1 = float(candidate.get("width", _design_width_value(cand_st)) or _design_width_value(cand_st))
    if w1 > w0 + 1e-9:
        return True
    a0 = float(seed_candidate.get("Ast_bot", 0.0) or 0.0)
    a1 = float(candidate.get("Ast_bot", 0.0) or 0.0)
    if a1 > a0 + 1e-9:
        return True
    if _shear_change_is_reinforcement_growth(seed_st, cand_st):
        return True
    return False


def _log_efficiency_growth_rejection(
    *,
    candidate_family: str,
    seed_candidate: dict,
    candidate: dict | None,
    extra: dict | None = None,
) -> None:
    deltas = {}
    if candidate and seed_candidate:
        seed_st = dict(seed_candidate.get("state") or {})
        cand_st = dict(candidate.get("state") or {})
        d0 = float(seed_candidate.get("depth", _float_from_state(seed_st, "D", 0.0)) or _float_from_state(seed_st, "D", 0.0))
        d1 = float((candidate or {}).get("depth", _float_from_state(cand_st, "D", 0.0)) or _float_from_state(cand_st, "D", 0.0))
        _, _, w0 = _resolve_geometry_width_context(seed_st)
        w0 = float(w0 or 0.0)
        w1 = float((candidate or {}).get("width", _design_width_value(cand_st)) or _design_width_value(cand_st))
        a0 = float(seed_candidate.get("Ast_bot", 0.0) or 0.0)
        a1 = float((candidate or {}).get("Ast_bot", 0.0) or 0.0)
        sd = _int_from_state(seed_st, "lig_d", 0)
        sl = _int_from_state(seed_st, "lig_legs", 0)
        cd = _int_from_state(cand_st, "lig_d", 0)
        cl = _int_from_state(cand_st, "lig_legs", 0)
        deltas = {
            "delta_D_mm": round(d1 - d0, 3),
            "delta_b_mm": round(w1 - w0, 3),
            "delta_Ast_bot": round(a1 - a0, 3),
            "removed_shear_links": bool((sd > 0 or sl >= 2) and cd <= 0 and cl < 2),
        }
    payload = {
        "event": "rejected",
        "candidate_family": candidate_family,
        "reason": "growth_move_blocked_in_efficiency_mode",
        **deltas,
    }
    if extra:
        payload.update(extra)
    _merge_design_guide_rank_trace({"efficiency_growth_rejection": dict(payload)})


def _exhaustion_map_fully_resolved_for_terminal(exhaust: dict | None) -> bool:
    if not isinstance(exhaust, dict) or not exhaust:
        return False
    for _fam, rec in exhaust.items():
        if not isinstance(rec, dict):
            return False
        if not bool(rec.get("tried")):
            return False
        if bool(rec.get("accepted")):
            continue
        if rec.get("rejected_reason"):
            continue
        return False
    return True


def _can_emit_efficiency_terminal_state(worst_u: float, exhaust: dict | None) -> tuple[bool, str]:
    try:
        w = float(worst_u)
    except (TypeError, ValueError):
        w = 0.0
    if GUIDANCE_TARGET_UTIL_MIN <= w <= GUIDANCE_TARGET_UTIL_MAX:
        return True, "in_target_band"
    if w >= float(GUIDANCE_UNDERSIZED_DONE_BLOCK_UTIL):
        return True, "worst_util_above_undersized_done_block"
    if not _exhaustion_map_fully_resolved_for_terminal(exhaust):
        return False, "exhaustion_incomplete_or_unresolved"
    return True, "undersized_but_all_reduction_families_resolved"


def _build_efficiency_exhaustion_map(
    *,
    state: dict,
    overview: dict,
    conservative: bool,
    bottom_tighten: dict | None,
    shear_tighten: dict | None,
    geometry_tighten: dict | None,
    shear_cleanup_possible: bool,
    bending_inefficient: bool,
    shear_inefficient: bool,
) -> dict:
    ex: dict[str, dict] = {
        "shear_cleanup": {"tried": False, "accepted": False, "rejected_reason": None},
        "bottom_reo_reduction": {"tried": False, "accepted": False, "rejected_reason": None},
        "depth_reduction": {"tried": False, "accepted": False, "rejected_reason": None},
        "width_reduction": {"tried": False, "accepted": False, "rejected_reason": None},
    }
    if _shear_reinforcement_is_active(state):
        ex["shear_cleanup"]["tried"] = True
        if shear_tighten:
            ups = dict(shear_tighten.get("updates") or {})
            trial_st = dict(state)
            trial_st.update(ups)
            if shear_tighten.get("candidate_type") == "no_shear_design_cleanup":
                ex["shear_cleanup"]["accepted"] = True
            elif not _shear_change_is_reinforcement_growth(state, trial_st):
                ex["shear_cleanup"]["accepted"] = True
            else:
                ex["shear_cleanup"]["rejected_reason"] = "shear_tightening_was_growth_not_reduction"
        elif shear_cleanup_possible or shear_inefficient:
            ex["shear_cleanup"]["rejected_reason"] = "no_safe_shear_reduction_candidate"
        else:
            ex["shear_cleanup"]["rejected_reason"] = "shear_not_marked_inefficient"
    else:
        ex["shear_cleanup"]["tried"] = True
        ex["shear_cleanup"]["accepted"] = True

    if conservative and bending_inefficient:
        ex["bottom_reo_reduction"]["tried"] = True
        if bottom_tighten:
            ex["bottom_reo_reduction"]["accepted"] = True
        else:
            ex["bottom_reo_reduction"]["rejected_reason"] = "no_safe_bottom_reduction_candidate"
    else:
        ex["bottom_reo_reduction"]["tried"] = True
        ex["bottom_reo_reduction"]["rejected_reason"] = (
            "bending_not_inefficient_vs_guidance_threshold" if not bending_inefficient else "efficiency_branch_inactive"
        )

    if conservative and geometry_tighten:
        ex["depth_reduction"]["tried"] = True
        ex["width_reduction"]["tried"] = True
        ups = dict(geometry_tighten.get("updates") or {})
        wkey, _, w0 = _resolve_geometry_width_context(state)
        d0 = _float_from_state(state, "D", 0.0)
        d1 = float(ups.get("D", d0) or d0)
        w1 = float(ups.get(wkey, w0) or w0)
        depth_down = d1 < d0 - 1e-9
        width_down = w1 < float(w0) - 1e-9
        if depth_down:
            ex["depth_reduction"]["accepted"] = True
        else:
            ex["depth_reduction"]["rejected_reason"] = "no_depth_reduction_in_selected_geometry_trial"
        if width_down:
            ex["width_reduction"]["accepted"] = True
        else:
            ex["width_reduction"]["rejected_reason"] = "no_width_reduction_in_selected_geometry_trial"
    elif conservative:
        ex["depth_reduction"]["tried"] = True
        ex["width_reduction"]["tried"] = True
        ex["depth_reduction"]["rejected_reason"] = "geometry_tightening_unavailable"
        ex["width_reduction"]["rejected_reason"] = "geometry_tightening_unavailable"
    else:
        ex["depth_reduction"]["tried"] = True
        ex["width_reduction"]["tried"] = True
        ex["depth_reduction"]["rejected_reason"] = "efficiency_branch_inactive"
        ex["width_reduction"]["rejected_reason"] = "efficiency_branch_inactive"

    return ex


def compute_efficiency_tightening_state(state: dict, context: dict | None = None) -> dict:
    design_context = context or _build_design_actions_context(state)
    working_state = dict(design_context.get("state") or _state_with_resolved_design_actions(state))
    actions = dict(design_context.get("actions") or _resolve_design_actions_from_state(working_state))
    overview = _collect_design_overview(working_state, context=design_context)
    utils = overview["utils"]
    bending_inefficient = utils["bending"] is not None and utils["bending"] <= GUIDANCE_INEFFICIENT_UTIL_THRESHOLD
    shear_relevant = _shear_change_is_relevant(overview, actions)
    shear_cleanup_possible = _shear_cleanup_possible(working_state)
    shear_inefficient = (
        utils["shear"] is not None
        and utils["shear"] <= GUIDANCE_INEFFICIENT_UTIL_THRESHOLD
        and shear_relevant
    )
    try:
        worst_u = float(overview.get("worst_util", 0.0) or 0.0)
    except (TypeError, ValueError):
        worst_u = 0.0
    efficiency_moves_ok = (
        bool(overview["all_key_pass"])
        and not bool(overview["any_fail"])
        and (not bool(overview["any_warn"]) or worst_u < float(GUIDANCE_UNDERSIZED_DONE_BLOCK_UTIL))
    )
    conservative = bool(efficiency_moves_ok and (bending_inefficient or shear_inefficient))
    classification = "acceptable"
    if overview["any_fail"]:
        classification = "failing"
    elif overview["any_warn"] or overview["worst_util"] >= GUIDANCE_NEAR_LIMIT_UTIL_THRESHOLD:
        classification = "near_limit"
    elif conservative:
        classification = "inefficient"
    elif overview["all_key_pass"] and EFFICIENCY_TARGET_UTIL_MIN <= overview["worst_util"] <= EFFICIENCY_TARGET_UTIL_MAX:
        classification = "optimal"

    mode_tighten = _compute_mode_guidance_recommendation(working_state) if conservative else None
    if mode_tighten and isinstance(mode_tighten, dict):
        mtu = mode_tighten.get("updates") or {}
        if not mtu or _updates_match_state(working_state, mtu):
            mode_tighten = None
            st.session_state.pop("_recommendation_cache_mode_guidance", None)
    if (
        mode_tighten
        and _efficiency_reduction_profile_from_overview(overview)
    ):
        seed_chk = evaluate_candidate_full(_guidance_state_snapshot(working_state), source="efficiency_mode_growth_gate")
        if seed_chk:
            trial_st = dict(working_state)
            trial_st.update(dict(mode_tighten.get("updates") or {}))
            tri_chk = evaluate_candidate_full(_guidance_state_snapshot(trial_st), source="efficiency_mode_growth_gate_trial")
            if tri_chk and _candidate_is_growth_move(seed_chk, tri_chk):
                _log_efficiency_growth_rejection(
                    candidate_family="mode_guidance",
                    seed_candidate=seed_chk,
                    candidate=tri_chk,
                    extra={"label": str(mode_tighten.get("label") or "")},
                )
                mode_tighten = None
                st.session_state.pop("_recommendation_cache_mode_guidance", None)
    bottom_tighten = _compute_bottom_reo_tightening_recommendation(working_state) if conservative and bending_inefficient and mode_tighten is None else None
    shear_tighten = (
        _compute_shear_tightening_recommendation(working_state)
        if efficiency_moves_ok
        and (shear_inefficient or shear_cleanup_possible)
        and mode_tighten is None
        else None
    )
    geometry_tighten = _compute_geometry_tightening_recommendation(working_state) if conservative and mode_tighten is None else None
    is_efficiency_reduction_mode = bool(conservative or _efficiency_reduction_profile_from_overview(overview))
    filter_growth_candidates = bool(_efficiency_reduction_profile_from_overview(overview))
    exhaustion_map = _build_efficiency_exhaustion_map(
        state=working_state,
        overview=overview,
        conservative=conservative,
        bottom_tighten=bottom_tighten,
        shear_tighten=shear_tighten,
        geometry_tighten=geometry_tighten,
        shear_cleanup_possible=shear_cleanup_possible,
        bending_inefficient=bending_inefficient,
        shear_inefficient=shear_inefficient,
    )
    return {
        "classification": classification,
        "overview": overview,
        "conservative": conservative,
        "efficiency_moves_ok": efficiency_moves_ok,
        "mode_tightening": mode_tighten,
        "bottom_tightening": bottom_tighten,
        "shear_tightening": shear_tighten,
        "geometry_tightening": geometry_tighten,
        "actions_used": actions,
        "shear_relevant": shear_relevant,
        "shear_cleanup_possible": shear_cleanup_possible,
        "shear_inefficient": shear_inefficient,
        "bending_inefficient": bending_inefficient,
        "is_efficiency_reduction_mode": is_efficiency_reduction_mode,
        "filter_growth_candidates": filter_growth_candidates,
        "exhaustion_map": exhaustion_map,
        "worst_util": worst_u,
        "strongly_underutilised": bool(worst_u < float(GUIDANCE_STRONGLY_UNDERUTILISED_UTIL)),
    }


def _geometry_trial_axis_for_bottom_rec(candidate: dict, state: dict) -> str | None:
    if not candidate.get("recommendation_geometry_trial"):
        return None
    u = candidate.get("updates") or {}
    if "D" in u:
        return "depth"
    wkey, _, _ = _resolve_geometry_width_context(state)
    if wkey in u:
        return "width"
    return None


def _collapse_bottom_geometry_width_depth_trials(
    filtered: list[dict],
    *,
    state: dict,
    seed_candidate: dict,
    mode_config: dict,
    efficiency_reduction_only: bool = False,
) -> list[dict]:
    if efficiency_reduction_only:
        _merge_design_guide_rank_trace(
            {
                "bottom_geo_collapse": {
                    "geometry_mode": "reduction",
                    "chosen_axis": None,
                    "chosen_axis_reason": "efficiency_reduction_only_skip_growth_axis_compare",
                    "rejected_growth_axes": ["depth", "width"],
                }
            }
        )
        return filtered
    pure = [c for c in filtered if not c.get("recommendation_compound")]
    compounds = [c for c in filtered if c.get("recommendation_compound")]
    geo = [c for c in pure if c.get("recommendation_geometry_trial")]
    reo = [c for c in pure if not c.get("recommendation_geometry_trial")]
    if not geo or not reo:
        return filtered
    depth_geo = [c for c in geo if _geometry_trial_axis_for_bottom_rec(c, state) == "depth"]
    width_geo = [c for c in geo if _geometry_trial_axis_for_bottom_rec(c, state) == "width"]
    if not depth_geo or not width_geo:
        return filtered
    for c in depth_geo + width_geo:
        if c.get("score") is None:
            c["score"] = _score_auto_design_candidate(c, mode_config, seed_candidate)
    best_depth = _select_best_auto_design_candidate(depth_geo, mode_config, seed_candidate)
    best_width = _select_best_auto_design_candidate(width_geo, mode_config, seed_candidate)
    if not best_depth or not best_width:
        return filtered
    strategy = str(mode_config.get("search_strategy", "balanced") or "balanced")
    if strategy == "shallow":
        sd = float(best_depth.get("score", float("inf")) or float("inf"))
        sw = float(best_width.get("score", float("inf")) or float("inf"))
        if sw <= sd + GUIDANCE_SHALLOW_GEOMETRY_SCORE_TIE_EPS:
            chosen = best_width
            depth_beat_width_reason = (
                f"depth_score_not_better_by_{GUIDANCE_SHALLOW_GEOMETRY_SCORE_TIE_EPS:.0f}"
                if sd + 1e-9 < sw
                else "scores_tied_prefer_width"
            )
        else:
            chosen = best_depth
            depth_beat_width_reason = "depth_score_materially_better_than_width"
        _merge_design_guide_rank_trace(
            {
                "bottom_geo_collapse": {
                    "geometry_mode": "growth",
                    "best_depth_score": sd,
                    "best_width_score": sw,
                    "chosen_axis": "width" if chosen is best_width else "depth",
                    "depth_beat_width_reason": depth_beat_width_reason,
                }
            }
        )
    else:
        chosen = _select_best_auto_design_candidate([best_depth, best_width], mode_config, seed_candidate)
        if chosen:
            _merge_design_guide_rank_trace(
                {
                    "bottom_geo_collapse": {
                        "geometry_mode": "growth",
                        "chosen_axis": _geometry_trial_axis_for_bottom_rec(chosen, state),
                        "chosen_axis_reason": "balanced_mode_best_of_width_depth",
                    }
                }
            )
    if not chosen:
        return compounds + pure
    other_geo = [
        c for c in geo if _geometry_trial_axis_for_bottom_rec(c, state) not in ("depth", "width")
    ]
    return compounds + reo + [chosen] + other_geo


def _annotate_bottom_reo_candidate_deltas(candidate: dict, seed_candidate: dict, state: dict) -> None:
    ss = dict(seed_candidate.get("state") or state)
    bs = dict(candidate.get("state") or {})
    seed_d = float(seed_candidate.get("depth", _float_from_state(ss, "D", 0.0)) or _float_from_state(ss, "D", 0.0))
    cand_d = float(candidate.get("depth", _float_from_state(bs, "D", 0.0)) or _float_from_state(bs, "D", 0.0))
    seed_b = float(seed_candidate.get("width", _design_width_value(ss)) or _design_width_value(ss))
    cand_b = float(candidate.get("width", _design_width_value(bs)) or _design_width_value(bs))
    seed_ast = float(seed_candidate.get("Ast_bot", 0.0) or 0.0)
    cand_ast = float(candidate.get("Ast_bot", 0.0) or 0.0)
    candidate["delta_D_mm"] = round(cand_d - seed_d, 3)
    candidate["delta_b_mm"] = round(cand_b - seed_b, 3)
    candidate["delta_Ast_bot"] = round(cand_ast - seed_ast, 3)


def _bottom_recommendation_compound_title(axis: str, geo_label: str) -> str:
    if axis == "width":
        return "Increase width and rebalance bottom reinforcement"
    if axis == "depth":
        return "Increase depth and adjust bottom reinforcement"
    gl = str(geo_label or "").strip()
    return f"Adjust geometry and bottom reinforcement ({gl})" if gl else "Adjust geometry and bottom reinforcement"


def _compound_merged_signature_preview(seed_state: dict, compound_state: dict) -> dict:
    u = _candidate_state_to_shared_updates(seed_state, compound_state)
    wkey, _, _ = _resolve_geometry_width_context(seed_state)
    order = [
        wkey,
        "D",
        "bot_row_count",
        "bot1_count",
        "bot2_count",
        "db_bot_1",
        "db_bot_2",
    ]
    return {k: u[k] for k in order if k in u}


def _bottom_recommendation_compound_effective_signature(seed_state: dict, compound_state: dict) -> tuple:
    u = _candidate_state_to_shared_updates(seed_state, compound_state)
    items: list[tuple[str, float | int | str]] = []
    for k in sorted(u.keys()):
        v = u[k]
        if isinstance(v, float):
            items.append((k, round(float(v), 6)))
        else:
            items.append((k, v))
    return tuple(items)


def _select_top_geometry_seeds_for_compound(
    candidates: list[dict],
    state: dict,
    axis: str,
    *,
    limit: int,
) -> list[dict]:
    geo = [
        c
        for c in candidates
        if c.get("recommendation_geometry_trial")
        and _geometry_trial_axis_for_bottom_rec(c, state) == axis
    ]

    def _geom_sort_key(c: dict) -> float:
        bu = ((c.get("overview") or {}).get("utils") or {}).get("bending")
        try:
            return float(bu) if bu is not None else 999.0
        except (TypeError, ValueError):
            return 999.0

    geo_sorted = sorted(geo, key=_geom_sort_key)
    picked: list[dict] = []
    seen_marker: set[tuple[str, float]] = set()
    for c in geo_sorted:
        u = dict(c.get("updates") or {})
        if axis == "width":
            wkey, _, _ = _resolve_geometry_width_context(state)
            if wkey not in u:
                continue
            try:
                marker = ("width", round(float(u[wkey]), 3))
            except (TypeError, ValueError):
                continue
        elif axis == "depth":
            if "D" not in u:
                continue
            try:
                marker = ("depth", round(float(u["D"]), 3))
            except (TypeError, ValueError):
                continue
        else:
            continue
        if marker in seen_marker:
            continue
        seen_marker.add(marker)
        picked.append(c)
        if len(picked) >= limit:
            break
    return picked


def _append_geometry_bottom_compound_candidates(
    *,
    state: dict,
    seed_candidate: dict,
    candidates: list[dict],
    mode_config: dict,
    context: dict,
    eval_cache: dict,
    metrics: dict,
    compound_stats: dict,
    compound_trace_log: list[dict],
) -> None:
    """Width/depth + bottom reo compounds using layouts regenerated on geometry-adjusted states."""
    seed_state = seed_candidate["state"]
    layout_cache_cmp = context.setdefault("layout_fit_cache", {})
    width_geo_all = [
        c
        for c in candidates
        if c.get("recommendation_geometry_trial")
        and _geometry_trial_axis_for_bottom_rec(c, state) == "width"
    ]
    depth_geo_all = [
        c
        for c in candidates
        if c.get("recommendation_geometry_trial")
        and _geometry_trial_axis_for_bottom_rec(c, state) == "depth"
    ]
    compound_stats["geometry_seed_candidates_considered"] = len(width_geo_all) + len(depth_geo_all)

    seen_compound_sigs: set[tuple] = set()

    def _trace_sample(
        *,
        axis: str,
        geo_lbl: str,
        ro_lbl: str | None,
        merged_preview: dict,
        result: str,
        reason: str,
        score: float | None = None,
    ) -> None:
        if len(compound_trace_log) >= 48:
            return
        row: dict = {
            "family": "compound",
            "subfamilies": ["geometry", "bottom_reo"],
            "axis": axis,
            "width_seed_label": geo_lbl if axis == "width" else None,
            "depth_seed_label": geo_lbl if axis == "depth" else None,
            "bottom_trial_label": ro_lbl,
            "merged_signature": merged_preview,
            "result": result,
            "reason": reason,
        }
        if score is not None:
            row["score"] = score
        compound_trace_log.append(row)

    def _consume_axis(axis: str, seed_limit: int, selected_key: str, trials_key: str) -> None:
        seeds = _select_top_geometry_seeds_for_compound(candidates, state, axis, limit=seed_limit)
        compound_stats[selected_key] = len(seeds)
        if not seeds:
            _trace_sample(
                axis=axis,
                geo_lbl="",
                ro_lbl=None,
                merged_preview={},
                result="skipped",
                reason=f"no_{axis}_geometry_seeds_after_dedupe",
            )
            return
        for geo_cand in seeds:
            geo_upd = dict(geo_cand.get("updates") or {})
            geo_lbl = str(geo_cand.get("label") or "")
            base_state = dict(state)
            base_state.update(geo_upd)
            local_arrs: list[dict] = []
            seen_a: set[tuple[int, int, int]] = set()
            for band in (0, 1):
                for arrangement in _generate_local_bottom_arrangements(
                    base_state,
                    mode_config,
                    band=band,
                    context=context,
                    limit=18,
                ):
                    sig_a = (
                        int(arrangement.get("bot1_count", 0) or 0),
                        int(arrangement.get("bot2_count", 0) or 0),
                        int(arrangement.get("db_bot_1", 0) or 0),
                    )
                    if sig_a in seen_a:
                        continue
                    seen_a.add(sig_a)
                    local_arrs.append(arrangement)
                    if len(local_arrs) >= 26:
                        break
                if len(local_arrs) >= 26:
                    break

            for arrangement in local_arrs:
                b_upd = _bottom_arrangement_to_shared_updates(arrangement)
                ro_lbl = _practical_bottom_reo_label(
                    int(arrangement.get("bot1_count", 0) or 0),
                    int(arrangement.get("bot2_count", 0) or 0),
                    int(arrangement.get("db_bot_1", 0) or 0),
                )
                if _updates_match_state(base_state, b_upd):
                    compound_stats["rejected_no_layout_variation"] += 1
                    _trace_sample(
                        axis=axis,
                        geo_lbl=geo_lbl,
                        ro_lbl=ro_lbl,
                        merged_preview=_compound_merged_signature_preview(
                            seed_state,
                            dict(base_state),
                        ),
                        result="rejected",
                        reason="no_layout_variation_vs_geometry_adjusted_state",
                    )
                    continue
                compound_state = dict(base_state)
                compound_state.update(b_upd)
                merged_sig = _bottom_recommendation_compound_effective_signature(seed_state, compound_state)
                merged_preview = _compound_merged_signature_preview(seed_state, compound_state)
                if merged_sig in seen_compound_sigs:
                    compound_stats["rejected_duplicate_signature"] += 1
                    _trace_sample(
                        axis=axis,
                        geo_lbl=geo_lbl,
                        ro_lbl=ro_lbl,
                        merged_preview=merged_preview,
                        result="rejected",
                        reason="duplicate_signature",
                    )
                    continue
                merged_upd_check = _candidate_state_to_shared_updates(seed_state, compound_state)
                if not merged_upd_check:
                    compound_stats["rejected_invalid_merge"] += 1
                    _trace_sample(
                        axis=axis,
                        geo_lbl=geo_lbl,
                        ro_lbl=ro_lbl,
                        merged_preview=merged_preview,
                        result="rejected",
                        reason="invalid_merge_empty_updates",
                    )
                    continue
                if _updates_match_state(state, merged_upd_check):
                    compound_stats["rejected_same_as_current"] += 1
                    _trace_sample(
                        axis=axis,
                        geo_lbl=geo_lbl,
                        ro_lbl=ro_lbl,
                        merged_preview=merged_preview,
                        result="rejected",
                        reason="same_as_current_live_state",
                    )
                    continue
                if not _arrangement_fits_state(compound_state, arrangement, layout_cache=layout_cache_cmp):
                    compound_stats["compound_layout_reject_count"] += 1
                    _trace_sample(
                        axis=axis,
                        geo_lbl=geo_lbl,
                        ro_lbl=ro_lbl,
                        merged_preview=merged_preview,
                        result="rejected",
                        reason="layout_no_fit",
                    )
                    continue
                compound_stats[trials_key] += 1
                clabel = f"{geo_lbl} + {ro_lbl}"
                comp = _evaluate_candidate_fast(
                    compound_state,
                    seed_state=seed_state,
                    context=context,
                    eval_cache=eval_cache,
                    metrics=metrics,
                    source="bottom_recommendation_compound",
                    label=clabel,
                    action_type="apply_bottom_recommendation",
                )
                if comp is None or _updates_match_state(state, comp.get("updates") or {}):
                    compound_stats["rejected_eval_cap_or_none"] += 1
                    _trace_sample(
                        axis=axis,
                        geo_lbl=geo_lbl,
                        ro_lbl=ro_lbl,
                        merged_preview=merged_preview,
                        result="rejected",
                        reason="eval_cap_or_noop_updates",
                    )
                    continue
                if not comp.get("is_compliant"):
                    compound_stats["rejected_noncompliant"] += 1
                seen_compound_sigs.add(merged_sig)
                compound_stats["compound_candidates_generated_count"] += 1
                comp["recommendation_compound"] = True
                comp["recommendation_geometry_trial"] = True
                comp["recommendation_bottom_trial"] = True
                comp["subfamilies"] = ["geometry", "bottom_reo"]
                comp["recommendation_family_tag"] = f"compound_{axis}_bottom"
                comp["compound_geo_axis"] = axis
                comp["arrangement"] = dict(arrangement)
                comp["actual_ast"] = float(comp.get("Ast_bot", 0.0) or 0.0)
                comp["guidance_recommendation_title"] = _bottom_recommendation_compound_title(axis, geo_lbl)
                _annotate_bottom_reo_candidate_deltas(comp, seed_candidate, state)
                candidates.append(comp)
                sc = comp.get("score")
                _trace_sample(
                    axis=axis,
                    geo_lbl=geo_lbl,
                    ro_lbl=ro_lbl,
                    merged_preview=merged_preview,
                    result="accepted_pool",
                    reason="evaluated_ok",
                    score=float(sc) if sc is not None else None,
                )

    _consume_axis("width", 3, "width_seed_candidates_selected_for_compound", "bottom_layout_trials_attempted_on_width_state")
    _consume_axis("depth", 2, "depth_seed_candidates_selected_for_compound", "bottom_layout_trials_attempted_on_depth_state")


def _maybe_prefer_compound_over_pure_geometry(
    best: dict | None,
    ranked: list[dict],
    *,
    state: dict,
    seed_candidate: dict,
    mode_config: dict,
) -> dict | None:
    if not best:
        return best
    if best.get("recommendation_compound"):
        return best
    if not best.get("recommendation_geometry_trial"):
        return best
    axis = _geometry_trial_axis_for_bottom_rec(best, state)
    if axis not in ("width", "depth"):
        return best
    try:
        best_score = float(best.get("score", 1e9) or 1e9)
    except (TypeError, ValueError):
        best_score = 1e9
    strategy = str(mode_config.get("search_strategy", "balanced") or "balanced")
    seed_d = float(seed_candidate.get("depth", 0.0) or 0.0)
    margin = float(GUIDANCE_COMPOUND_VS_PURE_GEOMETRY_SCORE_MARGIN)
    pick: dict | None = None
    pick_score = float("inf")
    for c in ranked:
        if not c.get("recommendation_compound"):
            continue
        if str(c.get("compound_geo_axis") or "") != axis:
            continue
        if not (best.get("is_compliant") and c.get("is_compliant")):
            continue
        if axis == "width" and strategy == "shallow":
            try:
                cd = float(c.get("depth", seed_d) or seed_d)
            except (TypeError, ValueError):
                continue
            if cd > seed_d + 1e-9:
                continue
        try:
            sc = float(c.get("score", 1e9) or 1e9)
        except (TypeError, ValueError):
            continue
        if sc <= best_score + margin and sc < pick_score:
            pick = c
            pick_score = sc
    if pick is not None:
        return pick
    return best


def _bottom_recommendation_prefilter_ok(
    seed_candidate: dict,
    candidate: dict,
    state: dict,
) -> tuple[bool, str]:
    if not str(candidate.get("label") or "").strip():
        return False, "missing_label"
    if _candidate_ductility_governs(seed_candidate):
        sdu = _candidate_ductility_util(seed_candidate)
        tdu = _candidate_ductility_util(candidate)
        if sdu is None or tdu is None:
            return False, "missing_ductility_util"
        if float(tdu) >= float(sdu) - 1e-9:
            return False, "ductility_not_improved"
    else:
        sb = ((seed_candidate.get("overview") or {}).get("utils") or {}).get("bending")
        tb = ((candidate.get("overview") or {}).get("utils") or {}).get("bending")
        try:
            if sb is None or tb is None:
                return False, "missing_bending_util"
            if float(tb) >= float(sb) - 1e-9:
                return False, "bending_util_not_improved"
        except (TypeError, ValueError):
            return False, "missing_bending_util"
    return True, "ok"


def _compute_bottom_reo_recommendation(state: dict) -> dict | None:
    state = _guidance_state_snapshot(state)
    started_at = time.perf_counter()
    # region agent log
    _agent_debug_log(
        "Entered bottom recommendation compute",
        {
            "callers": [frame.function for frame in inspect.stack()[1:5]],
            "recommendation_search_allowed": bool(_recommendation_search_allowed(state)),
        },
        location="inputs_page.py:_compute_bottom_reo_recommendation",
        hypothesis_id="H11",
    )
    # endregion
    if not _recommendation_search_allowed(state):
        return None
    design_context_br = _build_design_actions_context(state)
    overview_br = _collect_design_overview(state, context=design_context_br)
    efficiency_reduction_only = _efficiency_reduction_profile_from_overview(overview_br)
    mode_config = _design_mode_config(_design_optimisation_goal(state))
    seed_candidate = evaluate_candidate_full(state, source="bottom_recommendation_seed")
    if not seed_candidate:
        return None
    context = _build_auto_design_context(
        seed_candidate["state"],
        mode_config,
        reference_overview=seed_candidate.get("overview"),
    )
    eval_cache: dict = {}
    metrics = {
        "_reference_overview": seed_candidate.get("overview"),
        "generated_count": 0,
        "unique_eval_count": 0,
        "cache_hits": 0,
        "fast_eval_total_ms": 0.0,
        "cap_hit": False,
    }
    candidates: list[dict] = []
    for band in range(2):
        for arrangement in _generate_local_bottom_arrangements(state, mode_config, band=band, context=context):
            candidate_state = dict(state)
            candidate_state.update(_bottom_arrangement_to_shared_updates(arrangement))
            candidate = _evaluate_candidate_fast(
                candidate_state,
                seed_state=seed_candidate["state"],
                context=context,
                eval_cache=eval_cache,
                metrics=metrics,
                source="bottom_recommendation",
                label=_practical_bottom_reo_label(
                    int(arrangement.get("bot1_count", 0) or 0),
                    int(arrangement.get("bot2_count", 0) or 0),
                    int(arrangement.get("db_bot_1", 0) or 0),
                ),
                action_type="apply_bottom_recommendation",
            )
            if candidate is None or _updates_match_state(state, candidate.get("updates", {})):
                continue
            candidate["arrangement"] = arrangement
            candidate["actual_ast"] = float(candidate.get("Ast_bot", 0.0) or 0.0)
            candidate["recommendation_family_tag"] = "pure_bottom_reo"
            candidates.append(candidate)

    if not _geometry_lock_enabled(state) and not efficiency_reduction_only:
        geo_axes = (
            ("increase_width", "increase_depth")
            if str(mode_config.get("search_strategy", "balanced") or "balanced") == "shallow"
            else ("increase_depth", "increase_width")
        )
        for d in GUIDANCE_GEOMETRY_TRIAL_DELTAS_MM:
            for atype in geo_axes:
                payload = {"delta_mm": float(d)}
                updates = _guidance_action_updates(atype, payload, state=state)
                if not updates or _updates_match_state(state, updates):
                    continue
                cand_state = dict(state)
                cand_state.update(updates)
                geo_label = (
                    f"Increase depth D by {int(d)} mm"
                    if atype == "increase_depth"
                    else f"Increase section width by {int(d)} mm"
                )
                geo_cand = _evaluate_candidate_fast(
                    cand_state,
                    seed_state=seed_candidate["state"],
                    context=context,
                    eval_cache=eval_cache,
                    metrics=metrics,
                    source="bottom_recommendation_geometry",
                    label=geo_label,
                    action_type=str(atype),
                )
                if geo_cand is None or _updates_match_state(state, geo_cand.get("updates", {})):
                    continue
                geo_cand["recommendation_geometry_trial"] = True
                geo_cand["actual_ast"] = float(geo_cand.get("Ast_bot", 0.0) or 0.0)
                _gax = _geometry_trial_axis_for_bottom_rec(geo_cand, state)
                geo_cand["recommendation_family_tag"] = (
                    f"pure_geometry_{_gax}" if _gax in ("width", "depth") else "pure_geometry"
                )
                candidates.append(geo_cand)

    compound_stats: dict = {
        "geometry_seed_candidates_considered": 0,
        "width_seed_candidates_selected_for_compound": 0,
        "depth_seed_candidates_selected_for_compound": 0,
        "bottom_layout_trials_attempted_on_width_state": 0,
        "bottom_layout_trials_attempted_on_depth_state": 0,
        "compound_candidates_generated_count": 0,
        "compound_layout_reject_count": 0,
        "rejected_no_layout_variation": 0,
        "rejected_duplicate_signature": 0,
        "rejected_noncompliant": 0,
        "rejected_score_inferior": 0,
        "rejected_invalid_merge": 0,
        "rejected_same_as_current": 0,
        "rejected_filtered_by_family_collapse": 0,
        "rejected_eval_cap_or_none": 0,
        "compound_zero_generation_hints": [],
        "compound_stage_skipped_reason": None,
    }
    compound_trace_log: list[dict] = []
    if not _geometry_lock_enabled(state) and not efficiency_reduction_only:
        _append_geometry_bottom_compound_candidates(
            state=state,
            seed_candidate=seed_candidate,
            candidates=candidates,
            mode_config=mode_config,
            context=context,
            eval_cache=eval_cache,
            metrics=metrics,
            compound_stats=compound_stats,
            compound_trace_log=compound_trace_log,
        )
        if int(compound_stats.get("compound_candidates_generated_count", 0) or 0) == 0:
            hints: list[str] = []
            if int(compound_stats.get("geometry_seed_candidates_considered", 0) or 0) == 0:
                hints.append("no_geometry_trial_candidates_in_pool_for_compound")
            elif (
                int(compound_stats.get("width_seed_candidates_selected_for_compound", 0) or 0) == 0
                and int(compound_stats.get("depth_seed_candidates_selected_for_compound", 0) or 0) == 0
            ):
                hints.append("no_unique_geometry_seeds_after_util_sort_or_missing_axis_keys")
            elif (
                int(compound_stats.get("rejected_no_layout_variation", 0) or 0) > 0
                and int(compound_stats.get("bottom_layout_trials_attempted_on_width_state", 0) or 0)
                + int(compound_stats.get("bottom_layout_trials_attempted_on_depth_state", 0) or 0)
                == 0
            ):
                hints.append("layout_variation_rejects_only_no_eval_attempts")
            elif int(compound_stats.get("rejected_eval_cap_or_none", 0) or 0) > 0:
                hints.append("eval_cap_or_noop_blocked_all_successful_compound_evals")
            compound_stats["compound_zero_generation_hints"] = hints
    else:
        compound_stats["compound_stage_skipped_reason"] = "geometry_lock_or_efficiency_reduction"

    filtered: list[dict] = []
    for candidate in candidates:
        if candidate is None or _updates_match_state(state, candidate.get("updates") or {}):
            continue
        if not _candidate_materially_improves(seed_candidate, candidate):
            continue
        bu = ((candidate.get("overview") or {}).get("utils") or {}).get("bending")
        if bu is None:
            continue
        ok_pf, rsn_pf = _bottom_recommendation_prefilter_ok(seed_candidate, candidate, state)
        if not ok_pf:
            if candidate.get("recommendation_compound"):
                compound_stats["rejected_score_inferior"] = int(
                    compound_stats.get("rejected_score_inferior", 0) or 0,
                ) + 1
            _log_design_reco_candidate_rank(
                domain="bending",
                event="rejected",
                candidate=candidate,
                reason=str(rsn_pf),
            )
            continue
        filtered.append(candidate)

    if efficiency_reduction_only:
        fg: list[dict] = []
        for candidate in filtered:
            if _candidate_is_growth_move(seed_candidate, candidate):
                _log_efficiency_growth_rejection(
                    candidate_family="bottom_reo",
                    seed_candidate=seed_candidate,
                    candidate=candidate,
                )
                continue
            fg.append(candidate)
        filtered = fg
        _merge_design_guide_rank_trace(
            {
                "efficiency_bottom_ranked_after_growth_filter": [
                    str(c.get("label") or "") for c in filtered[:16]
                ],
            },
        )

    filtered = _collapse_bottom_geometry_width_depth_trials(
        filtered,
        state=state,
        seed_candidate=seed_candidate,
        mode_config=mode_config,
        efficiency_reduction_only=efficiency_reduction_only,
    )

    compound_kept_count = sum(1 for c in filtered if c.get("recommendation_compound"))
    _compound_stage_payload = dict(compound_stats)
    _compound_stage_payload["compound_candidates_kept_count"] = compound_kept_count
    _compound_stage_payload["compound_trace_sample"] = compound_trace_log[:48]
    _merge_design_guide_rank_trace(
        {
            "bottom_recommendation_compound_stage": _compound_stage_payload,
        },
    )

    if DEBUG_DESIGN_GUIDANCE_PROBE:
        _agent_debug_log(
            "Bottom recommendation candidate pool",
            {
                "raw_count": len(candidates),
                "after_improvement_filter": len(filtered),
            },
            location="inputs_page.py:_compute_bottom_reo_recommendation:filter",
            hypothesis_id="H_DESIGN_RECO_RANK",
        )

    if not filtered:
        _agent_debug_log(
            "Completed bottom recommendation compute",
            {
                "found_recommendation": False,
                "duration_ms": round((time.perf_counter() - started_at) * 1000, 1),
            },
            location="inputs_page.py:_compute_bottom_reo_recommendation:end",
            hypothesis_id="H19",
        )
        return None

    for cand in filtered:
        _annotate_bottom_reo_candidate_deltas(cand, seed_candidate, state)
    for cand in filtered:
        if cand.get("score") is None:
            cand["score"] = _score_auto_design_candidate(cand, mode_config, seed_candidate)
    for cand in filtered:
        _annotate_candidate_target_band_metrics(cand, mode_config)
    ranked_bottom = _keep_top_candidates(filtered, mode_config, limit=min(16, len(filtered)))

    best = _pick_best_bottom_recommendation_by_selector(
        ranked_bottom,
        state=state,
        seed_candidate=seed_candidate,
        mode_config=mode_config,
    )
    best = _maybe_prefer_compound_over_pure_geometry(
        best,
        ranked_bottom,
        state=state,
        seed_candidate=seed_candidate,
        mode_config=mode_config,
    )
    if best:
        _annotate_candidate_target_band_metrics(best, mode_config)
        _br_pool = [c for c in filtered if c.get("candidate_reaches_target_band")]
        best["winning_candidate_post_util"] = best.get("candidate_post_util")
        best["winning_candidate_reaches_target_band"] = best.get("candidate_reaches_target_band")
        best["winning_candidate_distance_to_target_band"] = best.get("candidate_distance_to_target_band")
        best["winning_candidate_selected_because_reaches_band"] = bool(_br_pool) and bool(
            best.get("candidate_reaches_target_band")
        )
    if not best or _updates_match_state(state, best.get("updates", {})):
        _agent_debug_log(
            "Completed bottom recommendation compute",
            {
                "found_recommendation": False,
                "duration_ms": round((time.perf_counter() - started_at) * 1000, 1),
            },
            location="inputs_page.py:_compute_bottom_reo_recommendation:end",
            hypothesis_id="H19",
        )
        return None
    if efficiency_reduction_only and _candidate_is_growth_move(seed_candidate, best):
        _log_efficiency_growth_rejection(
            candidate_family="bottom_reo",
            seed_candidate=seed_candidate,
            candidate=best,
            extra={"stage": "post_selector_guard"},
        )
        _agent_debug_log(
            "Completed bottom recommendation compute",
            {
                "found_recommendation": False,
                "duration_ms": round((time.perf_counter() - started_at) * 1000, 1),
                "reason": "growth_blocked_efficiency_reduction",
            },
            location="inputs_page.py:_compute_bottom_reo_recommendation:end",
            hypothesis_id="H19",
        )
        return None
    arrangement = dict(best.get("arrangement") or {})
    required_ast = 0.0
    if arrangement:
        selected_bending = _evaluate_bending_with_bottom_state(state, arrangement)
        if selected_bending:
            required_ast = float(_required_ast_for_arrangement(state, {
                "Ast_bot": float(best.get("actual_ast", 0.0) or 0.0),
                "db_bot": float(selected_bending.get("db_bot", 0.0) or 0.0),
                "nb_bot": int(selected_bending.get("nb_bot", 0) or 0),
                "d_centroid": float(selected_bending.get("d_centroid", 0.0) or 0.0),
            }))
    # region agent log
    _agent_debug_log(
        "Completed bottom recommendation compute",
        {
            "found_recommendation": True,
            "label": str(best.get("label") or ""),
            "duration_ms": round((time.perf_counter() - started_at) * 1000, 1),
        },
        location="inputs_page.py:_compute_bottom_reo_recommendation:end",
        hypothesis_id="H19",
    )
    # endregion
    if _design_guide_sidebar_debug_enabled():
        seed_bu = ((seed_candidate.get("overview") or {}).get("utils") or {}).get("bending")
        _append_design_guide_reco_trace(
            {
                "domain": "bending",
                "event": "final_selected",
                "candidate_label": str(best.get("label") or ""),
                "candidate_type": (
                    "compound_geometry_bottom"
                    if best.get("recommendation_compound")
                    else (
                        "geometry_trial"
                        if best.get("recommendation_geometry_trial")
                        else "bottom_reo"
                    )
                ),
                "updates": dict(best.get("updates") or {}),
                "score": best.get("score"),
                "util_before": float(seed_bu) if seed_bu is not None else None,
                "util_after": float(
                    (best.get("overview") or {}).get("utils", {}).get("bending", 0.0) or 0.0
                ),
            }
        )
    ss = dict(seed_candidate.get("state") or {})
    bs = dict(best.get("state") or {})
    seed_D = float(seed_candidate.get("depth", _float_from_state(ss, "D", 0.0)) or _float_from_state(ss, "D", 0.0))
    best_D = float(best.get("depth", _float_from_state(bs, "D", 0.0)) or _float_from_state(bs, "D", 0.0))
    seed_b = float(seed_candidate.get("width", _design_width_value(ss)) or _design_width_value(ss))
    best_b = float(best.get("width", _design_width_value(bs)) or _design_width_value(bs))
    seed_ast = float(seed_candidate.get("Ast_bot", 0.0) or 0.0)
    best_ast = float(best.get("Ast_bot", 0.0) or 0.0)
    band_reachers = [c for c in filtered if c.get("candidate_reaches_target_band")]
    one_click_available = len(band_reachers) > 0
    _merge_design_guide_rank_trace(
        {
            "bottom_recommendation_pick": {
                "delta_D_mm": round(best_D - seed_D, 3),
                "delta_b_mm": round(best_b - seed_b, 3),
                "delta_Ast_bot": round(best_ast - seed_ast, 3),
                "geometry_trial": bool(best.get("recommendation_geometry_trial")),
                "label": str(best.get("label") or ""),
                "winning_candidate_is_compound": bool(best.get("recommendation_compound")),
                "winning_candidate_subfamilies": list(best.get("subfamilies") or []),
                "winning_candidate_family_tag": best.get("recommendation_family_tag"),
                "winning_candidate_delta_b_mm": best.get("delta_b_mm"),
                "winning_candidate_delta_D_mm": best.get("delta_D_mm"),
                "winning_candidate_delta_Ast_bot": best.get("delta_Ast_bot"),
                "winning_candidate_post_util": best.get("candidate_post_util"),
                "winning_candidate_reaches_target_band": best.get("candidate_reaches_target_band"),
                "winning_candidate_distance_to_target_band": best.get("candidate_distance_to_target_band"),
                "winning_candidate_selected_because_reaches_band": best.get(
                    "winning_candidate_selected_because_reaches_band",
                ),
                "one_click_convergence_available": one_click_available,
                "one_click_convergence_reason": (
                    "at_least_one_compliant_candidate_reaches_target_band_in_one_move"
                    if one_click_available
                    else "no_compliant_candidate_reaches_target_band_in_one_move"
                ),
                "local_step_selected_only_because_no_band_reaching_candidate": (
                    any(bool(c.get("is_compliant")) for c in filtered) and not one_click_available
                ),
                "evaluated_candidates_band_preview": [
                    {
                        "label": str(c.get("label") or "")[:80],
                        "candidate_post_util": c.get("candidate_post_util"),
                        "candidate_reaches_target_band": c.get("candidate_reaches_target_band"),
                        "candidate_distance_to_target_band": c.get("candidate_distance_to_target_band"),
                    }
                    for c in filtered[:24]
                ],
            },
        }
    )
    disp_label = str(best.get("label") or "")
    if best.get("recommendation_compound"):
        disp_label = str(best.get("guidance_recommendation_title") or disp_label)
    gcl = _guidance_change_lines_for_updates(state, dict(best.get("updates") or {}))
    return {
        "arrangement": arrangement,
        "updates": dict(best.get("updates") or {}),
        "actual_ast": float(best.get("actual_ast", 0.0) or 0.0),
        "required_ast": required_ast,
        "util": float(best.get("overview", {}).get("utils", {}).get("bending", 0.0) or 0.0),
        "label": disp_label,
        "score": float(best.get("score", 0.0) or 0.0),
        "recommendation_compound": bool(best.get("recommendation_compound")),
        "subfamilies": list(best.get("subfamilies") or []),
        "recommendation_family_tag": best.get("recommendation_family_tag"),
        "guidance_recommendation_title": best.get("guidance_recommendation_title"),
        "delta_b_mm": float(best.get("delta_b_mm") or 0.0),
        "delta_D_mm": float(best.get("delta_D_mm") or 0.0),
        "delta_Ast_bot": float(best.get("delta_Ast_bot") or 0.0),
        "guidance_change_lines": gcl,
    }


def _shear_recommendation_overview_is_failing(overview: dict) -> bool:
    statuses = overview.get("statuses") or {}
    if str(statuses.get("shear") or "") == "FAIL":
        return True
    su = (overview.get("utils") or {}).get("shear")
    try:
        if su is not None and float(su) > 1.0 + 1e-12:
            return True
    except (TypeError, ValueError):
        pass
    return False


def _shear_recommendation_overview_is_conservative_cleanup(overview: dict) -> bool:
    if _shear_recommendation_overview_is_failing(overview):
        return False
    if not bool(overview.get("all_key_pass")):
        return False
    statuses = overview.get("statuses") or {}
    if str(statuses.get("shear") or "") != "PASS":
        return False
    su = (overview.get("utils") or {}).get("shear")
    if su is None:
        return False
    try:
        return float(su) <= float(GUIDANCE_INEFFICIENT_UTIL_THRESHOLD)
    except (TypeError, ValueError):
        return False


def _log_shear_ladder_attempt(
    state: dict,
    *,
    ladder_mode: str,
    branch: str,
    lig_legs: int,
    s_lig: float,
    proposed_updates: dict | None,
    expected_util_after: float | None,
    decision: str,
    reason: str,
) -> None:
    if not DEBUG_DESIGN_GUIDANCE_PROBE:
        return
    _agent_debug_log(
        "Shear ladder candidate",
        {
            "ladder_mode": ladder_mode,
            "branch": branch,
            "current_lig_legs": lig_legs,
            "current_s_lig": s_lig,
            "proposed_updates": proposed_updates,
            "expected_util_after": expected_util_after,
            "decision": decision,
            "reason": reason,
        },
        location="inputs_page.py:_compute_shear_recommendation:ladder",
        hypothesis_id="H_SHEAR_LADDER",
    )


def _iter_shear_recommendation_ladder_states(state: dict, *, conservative: bool) -> list[tuple[str, dict]]:
    trials: list[tuple[str, dict]] = []
    geo_lock = _geometry_lock_enabled(state)
    cur_s = float(_float_from_state(state, "s_lig", 0.0) or 0.0)
    cur_legs = max(_int_from_state(state, "lig_legs", 2), 2)
    cur_dia = max(_int_from_state(state, "lig_d", 10), 10)
    width_key, _, cur_w = _resolve_geometry_width_context(state)
    cur_d = float(_float_from_state(state, "D", 600.0) or 600.0)
    cur_fc = float(_float_from_state(state, "fc", 32.0) or 32.0)

    def _push(branch: str, st: dict) -> None:
        trials.append((branch, dict(st)))

    if conservative:
        if _shear_reinforcement_is_active(state):
            looser = [float(x) for x in REO_SPACINGS if float(x) > cur_s + 1e-9]
            for s in sorted(looser)[:4]:
                ns = dict(state)
                ns["lig_legs"] = int(max(_int_from_state(state, "lig_legs", 2), 2))
                ns["lig_d"] = int(max(_int_from_state(state, "lig_d", 10), 10))
                ns["s_lig"] = float(s)
                _push("spacing_looser", ns)
            if cur_legs > 2:
                nl = max(2, cur_legs - 2)
                ns = dict(state)
                ns["lig_legs"] = int(nl)
                ns["lig_d"] = int(cur_dia)
                ns["s_lig"] = float(cur_s)
                _push("legs_down", ns)
            smaller_dias = [int(d) for d in REO_BAR_DIAS if int(d) < int(cur_dia) and int(d) >= 10]
            for nd in sorted(smaller_dias, reverse=True)[:3]:
                ns = dict(state)
                ns["lig_d"] = int(nd)
                ns["lig_legs"] = int(cur_legs)
                ns["s_lig"] = float(cur_s)
                _push("dia_down", ns)
        if _int_from_state(state, "lig_legs", 0) > 0 and _shear_state_eligible_for_no_links(state):
            ns = dict(state)
            ns["lig_legs"] = 0
            ns["lig_d"] = 0
            ns["s_lig"] = float(max(_float_from_state(state, "s_lig", 200.0), 1.0))
            _push("no_ligs", ns)
        return trials

    if not _shear_reinforcement_is_active(state):
        act = _activation_shear_state(state)
        if _make_auto_design_candidate_key(act) != _make_auto_design_candidate_key(state):
            _push("shear_activation", act)
        return trials

    eligible_s = [float(x) for x in REO_SPACINGS if float(x) < cur_s - 1e-9]
    for s in sorted(eligible_s)[:5]:
        ns = dict(state)
        ns["lig_legs"] = int(cur_legs)
        ns["lig_d"] = int(cur_dia)
        ns["s_lig"] = float(s)
        _push("spacing_tighter", ns)
    for nl in (cur_legs + 2, cur_legs + 4, min(cur_legs + 6, 8)):
        if nl < 2 or nl == cur_legs:
            continue
        ns = dict(state)
        ns["lig_legs"] = int(nl)
        ns["lig_d"] = int(cur_dia)
        ns["s_lig"] = float(cur_s)
        _push("legs_up", ns)
    for nd in REO_BAR_DIAS:
        if int(nd) > int(cur_dia) and int(nd) <= 24:
            ns = dict(state)
            ns["lig_d"] = int(nd)
            ns["lig_legs"] = int(cur_legs)
            ns["s_lig"] = float(cur_s)
            _push("dia_up", ns)

    if not geo_lock:
        for delta in GUIDANCE_GEOMETRY_TRIAL_DELTAS_MM:
            ns = dict(state)
            ns["D"] = float(int(round(max(350.0, cur_d + float(delta)) / 10.0) * 10))
            _push("depth_up", ns)
        for delta in GUIDANCE_GEOMETRY_TRIAL_DELTAS_MM:
            ns = dict(state)
            nw = float(int(round(max(250.0, cur_w + float(delta)) / 10.0) * 10))
            ns[width_key] = nw
            if width_key != "b":
                ns["b"] = nw
            _push("width_up", ns)

    if cur_fc < 65.0:
        ns = dict(state)
        ns["fc"] = float(min(65.0, int(round((cur_fc + 5.0) / 5.0) * 5)))
        if abs(float(ns["fc"]) - cur_fc) > 1e-9:
            _push("material_fc", ns)

    return trials


def _shear_ladder_validate_candidate(
    state: dict,
    candidate: dict | None,
    *,
    branch: str,
    conservative: bool,
    baseline_shear_util: float | None,
) -> tuple[bool, str]:
    if candidate is None:
        return False, "eval_none"
    updates = candidate.get("updates") or {}
    if not updates:
        return False, "empty_updates"
    if _updates_match_state(state, updates):
        return False, "no_state_change"
    cs = dict(candidate.get("state") or {})
    legs = _int_from_state(cs, "lig_legs", 0)
    if legs == 1:
        return False, "lig_legs_single_leg_forbidden"
    dia = _int_from_state(cs, "lig_d", 0)
    if legs > 0 and dia <= 0:
        return False, "zero_link_diameter"
    s_prop = _float_from_state(cs, "s_lig", 0.0)
    s_cur = _float_from_state(state, "s_lig", 0.0)
    leg_cur = max(_int_from_state(state, "lig_legs", 2), 2)
    new_util = ((candidate.get("overview") or {}).get("utils") or {}).get("shear")

    if conservative:
        if not bool(candidate.get("is_compliant")):
            return False, "not_compliant"
        if branch == "no_ligs":
            if legs != 0:
                return False, "no_ligs_branch_requires_zero_legs"
            if not _shear_state_eligible_for_no_links(state):
                return False, "no_links_not_eligible_precheck"
            if not _shear_no_links_candidate_passes_code(state, candidate):
                return False, "no_links_torsion_or_min_shear_or_strength"
            return True, "accepted"
        if legs == 0:
            return False, "zero_ligs_only_via_no_ligs_branch"
        if legs < 2:
            return False, "lig_legs_below_2"
        if branch == "spacing_looser" and s_prop <= s_cur + 1e-9:
            return False, "spacing_not_increased"
        if branch == "legs_down":
            if leg_cur <= 2 or legs >= leg_cur:
                return False, "legs_not_reduced"
        if branch == "dia_down":
            if dia >= _int_from_state(state, "lig_d", 0):
                return False, "dia_not_reduced"
        return True, "accepted"

    if legs == 0:
        return False, "zero_ligs_in_failing_branch"
    if legs < 2:
        return False, "lig_legs_below_2"
    if legs < leg_cur:
        return False, "removed_closed_ligs"
    if branch == "spacing_tighter" and s_cur > 1e-9 and s_prop >= s_cur - 1e-9:
        return False, "spacing_not_reduced"
    if new_util is None:
        return False, "missing_shear_util"
    try:
        nu = float(new_util)
        if math.isnan(nu):
            return False, "missing_shear_util"
    except (TypeError, ValueError):
        return False, "missing_shear_util"
    if baseline_shear_util is not None:
        if float(nu) >= float(baseline_shear_util) - 1e-9:
            return False, "shear_util_not_improved"
    return True, "accepted"


def _log_design_reco_candidate_rank(
    *,
    domain: str,
    event: str,
    candidate: dict | None,
    reason: str,
    util_before: float | None = None,
    util_after: float | None = None,
) -> None:
    payload = {
        "domain": domain,
        "event": event,
        "reason": reason,
        "candidate_label": None if candidate is None else str(candidate.get("label") or ""),
        "candidate_source": None if candidate is None else str(candidate.get("source") or ""),
        "candidate_type": None
        if candidate is None
        else str(
            candidate.get("shear_candidate_type")
            or candidate.get("shear_ladder_branch")
            or candidate.get("recommendation_geometry_trial")
            or "",
        ),
        "branch": None if candidate is None else str(candidate.get("shear_ladder_branch") or ""),
        "updates": None if candidate is None else dict(candidate.get("updates") or {}),
        "score": None if candidate is None else candidate.get("score"),
        "util_before": util_before,
        "util_after": util_after,
        "candidate_post_util": None if candidate is None else candidate.get("candidate_post_util"),
        "candidate_reaches_target_band": None if candidate is None else candidate.get("candidate_reaches_target_band"),
        "candidate_distance_to_target_band": None
        if candidate is None
        else candidate.get("candidate_distance_to_target_band"),
    }
    if DEBUG_DESIGN_GUIDANCE_PROBE:
        _agent_debug_log(
            "Design recommendation ranking",
            payload,
            location="inputs_page.py:_log_design_reco_candidate_rank",
            hypothesis_id="H_DESIGN_RECO_RANK",
        )
    if _design_guide_sidebar_debug_enabled():
        _append_design_guide_reco_trace(payload)


def _shear_util_from_overview_candidate(candidate: dict | None) -> float | None:
    if not candidate:
        return None
    try:
        u = ((candidate.get("overview") or {}).get("utils") or {}).get("shear")
        if u is None:
            return None
        f = float(u)
        return None if math.isnan(f) else f
    except (TypeError, ValueError):
        return None


def _shear_recommendation_prefinal_eligible(
    candidate: dict | None,
    *,
    state: dict,
    conservative: bool,
    baseline_su: float | None,
) -> tuple[bool, str]:
    if not candidate:
        return False, "none"
    updates = candidate.get("updates") or {}
    if not updates:
        return False, "empty_updates"
    if _updates_match_state(state, updates):
        return False, "noop"
    if not str(candidate.get("label") or "").strip():
        return False, "missing_label"
    if candidate.get("score") is None:
        return False, "missing_score"
    su = _shear_util_from_overview_candidate(candidate)
    if su is None:
        return False, "missing_shear_util"
    if not conservative and baseline_su is not None and float(su) >= float(baseline_su) - 1e-9:
        return False, "shear_util_not_improved"
    branch = str(candidate.get("shear_ladder_branch") or "")
    cs = dict(candidate.get("state") or {})
    if branch == "spacing_tighter":
        s_prop = _float_from_state(cs, "s_lig", _float_from_state(state, "s_lig", 0.0))
        s_cur = _float_from_state(state, "s_lig", 0.0)
        if s_cur > 1e-9 and s_prop >= s_cur - 1e-9:
            return False, "spacing_not_reduced"
    if not conservative:
        legs = _int_from_state(cs, "lig_legs", 0)
        if legs > 0 and legs < 2:
            return False, "lig_legs_below_2"
    return True, "ok"


def _pick_best_shear_recommendation_by_selector(
    candidates: list[dict],
    *,
    state: dict,
    seed_candidate: dict,
    mode_config: dict,
    conservative: bool,
    baseline_su: float | None,
) -> dict | None:
    pool = [c for c in candidates if c]
    while pool:
        pick = _select_best_auto_design_candidate(pool, mode_config, seed_candidate)
        if pick is None:
            return None
        if _updates_match_state(state, pick.get("updates") or {}):
            _log_design_reco_candidate_rank(
                domain="shear",
                event="rejected",
                candidate=pick,
                reason="noop_updates_match_state",
                util_after=_shear_util_from_overview_candidate(pick),
            )
            pool = [x for x in pool if x is not pick]
            continue
        su = _shear_util_from_overview_candidate(pick)
        if su is None:
            _log_design_reco_candidate_rank(
                domain="shear",
                event="rejected",
                candidate=pick,
                reason="missing_shear_util",
            )
            pool = [x for x in pool if x is not pick]
            continue
        if not conservative and baseline_su is not None and float(su) >= float(baseline_su) - 1e-9:
            _log_design_reco_candidate_rank(
                domain="shear",
                event="rejected",
                candidate=pick,
                reason="shear_util_not_improved_vs_baseline",
                util_before=float(baseline_su),
                util_after=float(su),
            )
            pool = [x for x in pool if x is not pick]
            continue
        _log_design_reco_candidate_rank(
            domain="shear",
            event="accepted",
            candidate=pick,
            reason="selector_top_valid",
            util_before=None if conservative else baseline_su,
            util_after=float(su),
        )
        return pick
    return None


def _is_strictly_rejectable_band_winner(candidate: dict | None, *, state: dict) -> tuple[bool, str]:
    if not isinstance(candidate, dict):
        return True, "invalid_candidate"
    if not bool(candidate.get("is_compliant")):
        return True, "noncompliant_candidate"
    if not bool(candidate.get("candidate_reaches_target_band")):
        return True, "not_target_band_candidate"
    updates = candidate.get("updates")
    if not isinstance(updates, dict) or not updates:
        return True, "missing_or_unusable_updates"
    if _updates_match_state(state, updates):
        return True, "noop_updates_match_state"
    if not str(candidate.get("label") or "").strip():
        return True, "missing_label"
    return False, "ok"


def _legacy_bottom_local_rejection_reason(
    pick: dict,
    *,
    seed_candidate: dict,
    seed_bu_f: float | None,
    ductility_seed: bool,
    seed_du: float | None,
) -> str | None:
    bu = ((pick.get("overview") or {}).get("utils") or {}).get("bending")
    try:
        bu_f = float(bu) if bu is not None else None
    except (TypeError, ValueError):
        bu_f = None
    if bu_f is None:
        return "missing_bending_util"
    if ductility_seed:
        pdu = _candidate_ductility_util(pick)
        if seed_du is not None and pdu is not None and float(pdu) >= float(seed_du) - 1e-9:
            return "ductility_not_improved"
        return None
    if seed_bu_f is not None and float(bu_f) >= float(seed_bu_f) - 1e-9:
        return "bending_util_not_improved"
    return None


def _pick_best_bottom_recommendation_by_selector(
    candidates: list[dict],
    *,
    state: dict,
    seed_candidate: dict,
    mode_config: dict,
) -> dict | None:
    pool = [c for c in candidates if c]
    seed_bu = ((seed_candidate.get("overview") or {}).get("utils") or {}).get("bending")
    try:
        seed_bu_f = float(seed_bu) if seed_bu is not None else None
    except (TypeError, ValueError):
        seed_bu_f = None
    ductility_seed = _candidate_ductility_governs(seed_candidate)
    seed_du = _candidate_ductility_util(seed_candidate)
    while pool:
        pick = _select_best_auto_design_candidate(pool, mode_config, seed_candidate)
        if pick is None:
            return None
        _band_seen = bool(pick.get("candidate_reaches_target_band")) and bool(pick.get("is_compliant"))
        if _band_seen:
            _strict_reject, _strict_reason = _is_strictly_rejectable_band_winner(pick, state=state)
            if _strict_reject:
                _log_design_reco_candidate_rank(
                    domain="bending",
                    event="rejected",
                    candidate=pick,
                    reason=f"strict_band_reject:{_strict_reason}",
                )
                _merge_design_guide_rank_trace(
                    {
                        "final_selector_band_winner_seen": True,
                        "final_selector_band_winner_accepted": False,
                        "final_selector_band_winner_rejected_reason": str(_strict_reason),
                        "final_selector_used_strict_band_accept_rule": True,
                        "winner_pool_mode": pick.get("winner_pool_mode"),
                        "selected_because_band": bool(pick.get("winning_candidate_selected_from_band_reachers")),
                    },
                )
                pool = [x for x in pool if x is not pick]
                continue
            _legacy_reason = _legacy_bottom_local_rejection_reason(
                pick,
                seed_candidate=seed_candidate,
                seed_bu_f=seed_bu_f,
                ductility_seed=ductility_seed,
                seed_du=seed_du,
            )
            _log_design_reco_candidate_rank(
                domain="bending",
                event="accepted",
                candidate=pick,
                reason="strict_band_winner_accept",
                util_before=seed_du if ductility_seed else seed_bu_f,
                util_after=_candidate_ductility_util(pick) if ductility_seed else pick.get("candidate_post_util"),
            )
            _merge_design_guide_rank_trace(
                {
                    "final_selector_band_winner_seen": True,
                    "final_selector_band_winner_accepted": True,
                    "final_selector_band_winner_rejected_reason": None,
                    "final_selector_used_strict_band_accept_rule": True,
                    "winner_pool_mode": pick.get("winner_pool_mode"),
                    "selected_because_band": bool(pick.get("winning_candidate_selected_from_band_reachers")),
                    "final_winner_label": str(pick.get("label") or ""),
                    "final_winner_reaches_target_band": bool(pick.get("candidate_reaches_target_band")),
                    "final_winner_post_util": pick.get("candidate_post_util"),
                    "final_winner_goal_score": pick.get("candidate_goal_score"),
                    "final_selector_band_winner_would_have_legacy_reject_reason": _legacy_reason,
                    "final_selector_band_winner_accepted_over_legacy_gate": bool(_legacy_reason),
                },
            )
            return pick
        if not str(pick.get("label") or "").strip():
            _log_design_reco_candidate_rank(
                domain="bending",
                event="rejected",
                candidate=pick,
                reason="missing_label",
            )
            pool = [x for x in pool if x is not pick]
            continue
        if _updates_match_state(state, pick.get("updates") or {}):
            _log_design_reco_candidate_rank(
                domain="bending",
                event="rejected",
                candidate=pick,
                reason="noop_updates_match_state",
            )
            pool = [x for x in pool if x is not pick]
            continue
        bu = ((pick.get("overview") or {}).get("utils") or {}).get("bending")
        try:
            bu_f = float(bu) if bu is not None else None
        except (TypeError, ValueError):
            bu_f = None
        if bu_f is None:
            _log_design_reco_candidate_rank(
                domain="bending",
                event="rejected",
                candidate=pick,
                reason="missing_bending_util",
            )
            pool = [x for x in pool if x is not pick]
            continue
        if ductility_seed:
            pdu = _candidate_ductility_util(pick)
            if seed_du is not None and pdu is not None and float(pdu) >= float(seed_du) - 1e-9:
                _log_design_reco_candidate_rank(
                    domain="bending",
                    event="rejected",
                    candidate=pick,
                    reason="ductility_not_improved",
                    util_before=float(seed_du),
                    util_after=float(pdu) if pdu is not None else None,
                )
                pool = [x for x in pool if x is not pick]
                continue
        elif seed_bu_f is not None and float(bu_f) >= float(seed_bu_f) - 1e-9:
            _log_design_reco_candidate_rank(
                domain="bending",
                event="rejected",
                candidate=pick,
                reason="bending_util_not_improved",
                util_before=float(seed_bu_f),
                util_after=float(bu_f),
            )
            pool = [x for x in pool if x is not pick]
            continue
        _log_design_reco_candidate_rank(
            domain="bending",
            event="accepted",
            candidate=pick,
            reason="selector_top_valid",
            util_before=seed_du if ductility_seed else seed_bu_f,
            util_after=_candidate_ductility_util(pick) if ductility_seed else bu_f,
        )
        _merge_design_guide_rank_trace(
            {
                "final_selector_band_winner_seen": False,
                "final_selector_band_winner_accepted": False,
                "final_selector_band_winner_rejected_reason": None,
                "final_selector_used_strict_band_accept_rule": False,
                "winner_pool_mode": pick.get("winner_pool_mode"),
                "selected_because_band": bool(pick.get("winning_candidate_selected_from_band_reachers")),
                "final_winner_label": str(pick.get("label") or ""),
                "final_winner_reaches_target_band": bool(pick.get("candidate_reaches_target_band")),
                "final_winner_post_util": pick.get("candidate_post_util"),
                "final_winner_goal_score": pick.get("candidate_goal_score"),
            },
        )
        return pick
    return None


def _try_shear_no_demand_cleanup_recommendation(state: dict, overview: dict, actions: dict) -> dict | None:
    if not _shear_demands_negligible(actions):
        return None
    if not _shear_reinforcement_is_active(state):
        return None
    su = ((overview or {}).get("utils") or {}).get("shear")
    try:
        su_f = float(su) if su is not None else 0.0
        if math.isnan(su_f):
            su_f = 0.0
    except (TypeError, ValueError):
        su_f = 0.0
    if su_f > GUIDANCE_SHEAR_UTIL_NEGLIGIBLE:
        return None
    cleanup_updates = {
        "lig_d": 0,
        "lig_legs": 0,
        "s_lig": float(CANONICAL_NO_SHEAR_SLIG_MM),
    }
    if _updates_match_state(state, cleanup_updates):
        return None
    trial_state = dict(state)
    trial_state.update(cleanup_updates)
    cand = evaluate_candidate_full(
        _guidance_state_snapshot(trial_state),
        source="shear_no_demand_cleanup_probe",
        updates=cleanup_updates,
    )
    if not cand or not bool(cand.get("is_compliant")):
        _merge_design_guide_rank_trace(
            {"shear_no_demand_cleanup": {"accepted": False, "reason": "non_compliant_when_links_cleared"}},
        )
        return None
    shear_preview = _evaluate_shear_with_state(dict(cand.get("state") or trial_state)) or {}
    _merge_design_guide_rank_trace(
        {
            "shear_no_demand_cleanup": {
                "accepted": True,
                "removed_shear_links": True,
                "prior_lig_d": _int_from_state(state, "lig_d", 0),
                "prior_lig_legs": _int_from_state(state, "lig_legs", 0),
            },
        },
    )
    return {
        "updates": dict(cleanup_updates),
        "label": "Remove shear reinforcement (no shear/torsion design demand)",
        "util": float(((cand.get("overview") or {}).get("utils") or {}).get("shear", 0.0) or 0.0),
        "web_util": float(shear_preview.get("web_util", 0.0) or 0.0),
        "phi_vu": float(shear_preview.get("phi_vu", 0.0) or 0.0),
        "veq": float(shear_preview.get("veq", 0.0) or 0.0),
        "score": 0.0,
        "severity_band": "cleanup",
        "candidate_type": "no_shear_design_cleanup",
    }


def _compute_shear_recommendation(state: dict) -> dict | None:
    state = _guidance_state_snapshot(state)
    if not _recommendation_search_allowed(state):
        return None
    design_context = _build_design_actions_context(state)
    overview = _collect_design_overview(state, context=design_context)
    actions = design_context.get("actions") or {}
    cleanup_rec = _try_shear_no_demand_cleanup_recommendation(state, overview, actions)
    if cleanup_rec is not None:
        return cleanup_rec
    if not _shear_change_is_relevant(overview, actions):
        return None
    mode_config = _design_mode_config(_design_optimisation_goal(state))
    seed_candidate = evaluate_candidate_full(state, source="shear_recommendation_seed")
    if not seed_candidate:
        return None
    context = _build_auto_design_context(
        seed_candidate["state"],
        mode_config,
        reference_overview=seed_candidate.get("overview"),
    )
    eval_cache: dict = {}
    metrics = {
        "_reference_overview": seed_candidate.get("overview"),
        "generated_count": 0,
        "unique_eval_count": 0,
        "cache_hits": 0,
        "fast_eval_total_ms": 0.0,
        "cap_hit": False,
    }
    seed_shear_util = (((seed_candidate or {}).get("overview") or {}).get("utils") or {}).get("shear")
    try:
        baseline_su = float(seed_shear_util) if seed_shear_util is not None else None
    except (TypeError, ValueError):
        baseline_su = None
    severity_band = _shear_severity_band(seed_shear_util)
    family_audit: dict[str, list[dict]] = {}
    conservative = _shear_recommendation_overview_is_conservative_cleanup(overview)
    ladder_mode = "conservative" if conservative else "failing"
    cur_legs_log = _int_from_state(state, "lig_legs", 0)
    cur_s_log = _float_from_state(state, "s_lig", 0.0)

    trial_states = _iter_shear_recommendation_ladder_states(state, conservative=conservative)
    seen_keys: set[tuple] = set()
    candidates: list[dict] = []

    for branch, candidate_state in trial_states:
        ck = _make_auto_design_candidate_key(candidate_state)
        if ck in seen_keys:
            _log_shear_ladder_attempt(
                state,
                ladder_mode=ladder_mode,
                branch=branch,
                lig_legs=cur_legs_log,
                s_lig=cur_s_log,
                proposed_updates=None,
                expected_util_after=None,
                decision="rejected",
                reason="duplicate_candidate_state",
            )
            continue
        seen_keys.add(ck)
        if _invalid_shear_spacing_change_without_activation(
            state,
            candidate_state,
            source="shear_recommendation",
        ):
            _log_shear_ladder_attempt(
                state,
                ladder_mode=ladder_mode,
                branch=branch,
                lig_legs=cur_legs_log,
                s_lig=cur_s_log,
                proposed_updates=None,
                expected_util_after=None,
                decision="rejected",
                reason="invalid_spacing_without_activation",
            )
            continue
        candidate = _evaluate_candidate_fast(
            candidate_state,
            seed_state=seed_candidate["state"],
            context=context,
            eval_cache=eval_cache,
            metrics=metrics,
            source="shear_recommendation",
            label=_shear_state_label(candidate_state),
            action_type="apply_shear_recommendation",
        )
        pu = (candidate or {}).get("updates")
        eu = None
        if candidate:
            try:
                eu = float(((candidate.get("overview") or {}).get("utils") or {}).get("shear") or float("nan"))
                if math.isnan(eu):
                    eu = None
            except (TypeError, ValueError):
                eu = None
        ok, reason = _shear_ladder_validate_candidate(
            state,
            candidate,
            branch=branch,
            conservative=conservative,
            baseline_shear_util=None if conservative else baseline_su,
        )
        _log_shear_ladder_attempt(
            state,
            ladder_mode=ladder_mode,
            branch=branch,
            lig_legs=cur_legs_log,
            s_lig=cur_s_log,
            proposed_updates=dict(pu) if isinstance(pu, dict) else None,
            expected_util_after=eu,
            decision="accepted" if ok else "rejected",
            reason=reason,
        )
        if not ok or candidate is None:
            _log_shear_candidate_debug(
                source="shear_recommendation",
                candidate_state=candidate_state,
                candidate=candidate,
            )
            continue
        if not conservative and candidate_materially_worsens(candidate, seed_candidate, mode_config, phase="shear_recommendation"):
            _log_shear_ladder_attempt(
                state,
                ladder_mode=ladder_mode,
                branch=branch,
                lig_legs=cur_legs_log,
                s_lig=cur_s_log,
                proposed_updates=dict(candidate.get("updates") or {}),
                expected_util_after=eu,
                decision="rejected",
                reason="materially_worse_non_shear",
            )
            continue
        candidate["score"] = _score_auto_design_candidate(candidate, mode_config, seed_candidate)
        candidate["shear_candidate_type"] = _shear_candidate_type(state, candidate.get("state") or candidate_state)
        candidate["shear_ladder_branch"] = branch
        _log_shear_candidate_debug(
            source="shear_recommendation",
            candidate_state=candidate_state,
            candidate=candidate,
        )
        candidates.append(candidate)

    if not conservative and _severe_shear_failure(seed_shear_util) and candidates:
        existing_keys = {_make_auto_design_candidate_key(dict(candidate.get("state") or {})) for candidate in candidates}
        ranked_base = _combined_shear_seed_candidates(
            candidates,
            seed_candidate=seed_candidate,
            base_state=state,
            severity_band=severity_band,
            seed_shear_util=seed_shear_util,
            limit=8,
        )
        for base_candidate in ranked_base:
            for combined_state in _generate_secondary_bending_tightening_states(base_candidate, limit=3):
                combined_key = _make_auto_design_candidate_key(combined_state)
                if combined_key in existing_keys:
                    continue
                combined_candidate = _evaluate_candidate_fast(
                    combined_state,
                    seed_state=seed_candidate["state"],
                    context=context,
                    eval_cache=eval_cache,
                    metrics=metrics,
                    source="shear_recommendation_combined",
                    label=(
                        f"Combined: {_shear_state_label(combined_state)}"
                        f" + {_bottom_reo_state_label(combined_state)}"
                    ),
                    action_type="apply_shear_recommendation",
                )
                pu_c = (combined_candidate or {}).get("updates")
                eu_c = None
                if combined_candidate:
                    try:
                        eu_c = float(((combined_candidate.get("overview") or {}).get("utils") or {}).get("shear") or float("nan"))
                        if math.isnan(eu_c):
                            eu_c = None
                    except (TypeError, ValueError):
                        eu_c = None
                ok_c, reason_c = _shear_ladder_validate_candidate(
                    state,
                    combined_candidate,
                    branch="combined_secondary_bending",
                    conservative=False,
                    baseline_shear_util=baseline_su,
                )
                _log_shear_ladder_attempt(
                    state,
                    ladder_mode=ladder_mode,
                    branch="combined_secondary_bending",
                    lig_legs=cur_legs_log,
                    s_lig=cur_s_log,
                    proposed_updates=dict(pu_c) if isinstance(pu_c, dict) else None,
                    expected_util_after=eu_c,
                    decision="accepted" if ok_c else "rejected",
                    reason=reason_c,
                )
                if not ok_c or combined_candidate is None:
                    continue
                if candidate_materially_worsens(combined_candidate, seed_candidate, mode_config, phase="shear_recommendation"):
                    _log_shear_ladder_attempt(
                        state,
                        ladder_mode=ladder_mode,
                        branch="combined_secondary_bending",
                        lig_legs=cur_legs_log,
                        s_lig=cur_s_log,
                        proposed_updates=dict(combined_candidate.get("updates") or {}),
                        expected_util_after=eu_c,
                        decision="rejected",
                        reason="materially_worse_non_shear",
                    )
                    continue
                combined_candidate["score"] = _score_auto_design_candidate(combined_candidate, mode_config, seed_candidate)
                combined_candidate["shear_candidate_type"] = "combined"
                combined_candidate["secondary_actions_combined"] = True
                combined_candidate["shear_ladder_branch"] = "combined_secondary_bending"
                candidates.append(combined_candidate)
                existing_keys.add(combined_key)

    if not candidates:
        _log_severe_shear_escalation(
            source="_compute_shear_recommendation",
            seed_candidate=seed_candidate,
            severity_band=severity_band,
            candidates=[],
            selected=None,
            family_audit=family_audit,
        )
        return None

    for cand in candidates:
        if cand.get("score") is None:
            cand["score"] = _score_auto_design_candidate(cand, mode_config, seed_candidate)

    eligible_shear: list[dict] = []
    for cand in candidates:
        ok_el, rsn_el = _shear_recommendation_prefinal_eligible(
            cand,
            state=state,
            conservative=conservative,
            baseline_su=None if conservative else baseline_su,
        )
        if ok_el:
            eligible_shear.append(cand)
        else:
            _log_design_reco_candidate_rank(
                domain="shear",
                event="rejected",
                candidate=cand,
                reason=str(rsn_el),
                util_before=None if conservative else baseline_su,
                util_after=_shear_util_from_overview_candidate(cand),
            )
    if conservative and _efficiency_reduction_profile_from_overview(overview):
        filtered_es: list[dict] = []
        for cand in eligible_shear:
            if _candidate_is_growth_move(seed_candidate, cand):
                _log_efficiency_growth_rejection(
                    candidate_family="shear",
                    seed_candidate=seed_candidate,
                    candidate=cand,
                )
                continue
            filtered_es.append(cand)
        eligible_shear = filtered_es
    if not eligible_shear:
        _log_severe_shear_escalation(
            source="_compute_shear_recommendation",
            seed_candidate=seed_candidate,
            severity_band=severity_band,
            candidates=candidates,
            selected=None,
            family_audit=family_audit,
        )
        return None

    ranked_shear = _keep_top_candidates(eligible_shear, mode_config, limit=min(16, len(eligible_shear)))

    best = _pick_best_shear_recommendation_by_selector(
        ranked_shear,
        state=state,
        seed_candidate=seed_candidate,
        mode_config=mode_config,
        conservative=conservative,
        baseline_su=None if conservative else baseline_su,
    )
    if not best:
        _log_severe_shear_escalation(
            source="_compute_shear_recommendation",
            seed_candidate=seed_candidate,
            severity_band=severity_band,
            candidates=candidates,
            selected=None,
            family_audit=family_audit,
        )
        return None
    shear_preview = _evaluate_shear_with_state(best.get("state") or state) or {}
    _log_severe_shear_escalation(
        source="_compute_shear_recommendation",
        seed_candidate=seed_candidate,
        severity_band=severity_band,
        candidates=candidates,
        selected=best,
        family_audit=family_audit,
    )
    if _design_guide_sidebar_debug_enabled():
        _append_design_guide_reco_trace(
            {
                "domain": "shear",
                "event": "final_selected",
                "candidate_label": str(best.get("label") or ""),
                "branch": str(best.get("shear_ladder_branch") or ""),
                "candidate_type": str(best.get("shear_candidate_type") or ""),
                "updates": dict(best.get("updates") or {}),
                "score": best.get("score"),
                "util_before": None if conservative else baseline_su,
                "util_after": _shear_util_from_overview_candidate(best),
            }
        )
    return {
        "updates": dict(best.get("updates") or {}),
        "label": str(best.get("label") or ""),
        "util": float(best.get("overview", {}).get("utils", {}).get("shear", 0.0) or 0.0),
        "web_util": float(shear_preview.get("web_util", 0.0) or 0.0),
        "phi_vu": float(shear_preview.get("phi_vu", 0.0) or 0.0),
        "veq": float(shear_preview.get("veq", 0.0) or 0.0),
        "score": float(best.get("score", 0.0) or 0.0),
        "severity_band": severity_band,
        "candidate_type": str(best.get("shear_candidate_type") or _shear_candidate_type(state, best.get("state") or state)),
    }


def _compute_geometry_recommendation(state: dict) -> dict | None:
    state = _guidance_state_snapshot(state)
    started_at = time.perf_counter()
    if _geometry_lock_enabled(state):
        return None
    if not _recommendation_search_allowed(state):
        return None
    mode_config = _design_mode_config(_design_optimisation_goal(state))
    seed_candidate = evaluate_candidate_full(state, source="geometry_recommendation_seed")
    if not seed_candidate:
        return None
    context = _build_auto_design_context(
        seed_candidate["state"],
        mode_config,
        reference_overview=seed_candidate.get("overview"),
    )
    eval_cache: dict = {}
    metrics = {
        "_reference_overview": seed_candidate.get("overview"),
        "generated_count": 0,
        "unique_eval_count": 0,
        "cache_hits": 0,
        "fast_eval_total_ms": 0.0,
        "cap_hit": False,
    }
    geometry_states: list[dict] = []
    if bool(seed_candidate.get("is_compliant")):
        for updates in _geometry_tightening_trial_updates(state):
            candidate_state = dict(state)
            candidate_state.update(updates)
            geometry_states.append(candidate_state)
    else:
        goal = _design_optimisation_goal(state)
        if goal == "shallower_beam":
            geometry_states.extend(generate_shallower_or_equal_depths(seed_candidate))
            geometry_states.extend(generate_slightly_deeper_depths(seed_candidate))
        elif goal == "less_longitudinal_reinforcement":
            geometry_states.extend(generate_same_or_larger_geometry_options(seed_candidate))
        else:
            geometry_states.extend(_generate_balanced_geometry_options(seed_candidate))

    deduped_states: dict[tuple, dict] = {}
    for candidate_state in geometry_states:
        deduped_states[_make_auto_design_candidate_key(candidate_state)] = candidate_state
    candidates: list[dict] = []
    for candidate_state in list(deduped_states.values())[:AUTO_DESIGN_MAX_STAGE_CANDIDATES]:
        candidate = _evaluate_candidate_fast(
            candidate_state,
            seed_state=seed_candidate["state"],
            context=context,
            eval_cache=eval_cache,
            metrics=metrics,
            source="geometry_recommendation",
            label=f"{int(_design_width_value(candidate_state))} x {int(_float_from_state(candidate_state, 'D', 0.0))} mm",
            action_type="apply_geometry_recommendation",
        )
        if candidate is None or _updates_match_state(state, candidate.get("updates", {})):
            continue
        candidates.append(candidate)
    best = _keep_top_candidates(candidates, mode_config, limit=1)
    best = best[0] if best else None
    if not best or _updates_match_state(state, best.get("updates", {})):
        # region agent log
        _agent_debug_log(
            "Completed geometry recommendation compute",
            {
                "found_recommendation": False,
                "duration_ms": round((time.perf_counter() - started_at) * 1000, 1),
            },
            location="inputs_page.py:_compute_geometry_recommendation:end",
            hypothesis_id="H20",
        )
        # endregion
        return None
    width_key, width_label, _ = _resolve_geometry_width_context(state)
    # region agent log
    _agent_debug_log(
        "Completed geometry recommendation compute",
        {
            "found_recommendation": True,
            "width": float(best.get("width", 0.0) or 0.0),
            "depth": float(best.get("depth", 0.0) or 0.0),
            "duration_ms": round((time.perf_counter() - started_at) * 1000, 1),
        },
        location="inputs_page.py:_compute_geometry_recommendation:end",
        hypothesis_id="H20",
    )
    # endregion
    return {
        "updates": dict(best.get("updates") or {}),
        "width_key": width_key,
        "width_label": width_label,
        "width": float(best.get("width", 0.0) or 0.0),
        "depth": float(best.get("depth", 0.0) or 0.0),
        "bending_util": float(best.get("overview", {}).get("utils", {}).get("bending", 0.0) or 0.0),
        "shear_util": float(best.get("overview", {}).get("utils", {}).get("shear", 0.0) or 0.0),
        "web_util": float((_evaluate_shear_with_state(best.get("state") or state) or {}).get("web_util", 0.0) or 0.0),
        "required_ast": float(best.get("required_ast", 0.0) or 0.0),
        "score": float(best.get("score", 0.0) or 0.0),
    }


def _set_shared_updates(updates: dict, *, source: str) -> None:
    for shared_key, value in updates.items():
        set_shared(shared_key, value, source=source)
    if any(key in {"lig_d", "lig_legs", "s_lig"} for key in updates):
        _normalise_invalid_shear_state_in_shared(source=f"{source}:shear_shared_normalise")
        _refresh_canonical_shear_widgets(source=f"{source}:shear_widget_refresh")


def _combined_shear_seed_candidates(
    candidates: list[dict],
    *,
    seed_candidate: dict,
    base_state: dict,
    severity_band: str,
    seed_shear_util: float | None,
    limit: int = 8,
) -> list[dict]:
    if not candidates:
        return []
    ranked = sorted(
        candidates,
        key=lambda item: _shear_recommendation_rank_key(
            item,
            base_state=base_state,
            severity_band=severity_band,
            seed_shear_util=seed_shear_util,
        ),
    )
    selected: dict[tuple, dict] = {}
    for candidate in ranked:
        family = _shear_family_label(
            str(candidate.get("shear_candidate_type") or _shear_candidate_type(base_state, dict(candidate.get("state") or {}))),
            candidate,
            seed_candidate=seed_candidate,
        )
        if family not in selected:
            selected[family] = candidate
    ordered: list[dict] = []
    seen: set[tuple] = set()
    for candidate in list(selected.values()) + ranked[: max(2, limit // 2)]:
        candidate_key = _make_auto_design_candidate_key(dict(candidate.get("state") or {}))
        if candidate_key in seen:
            continue
        seen.add(candidate_key)
        ordered.append(candidate)
        if len(ordered) >= limit:
            break
    return ordered


def _commit_auto_design_candidate_to_shared(candidate: dict) -> dict:
    if not candidate:
        return {}

    candidate_state = dict(candidate.get("state") or {})
    if not candidate_state:
        return {}
    pre_commit_state = _shared_state_snapshot()

    tracked_keys = [
        "b", "bw", "D", "tw", "bf", "tf", "bf_bot", "tf_bot",
        "cover_top", "cover_bot", "cover_side",
        "rowgap_top", "rowgap_bot",
        "lig_d", "lig_legs", "s_lig",
        "n_ducts", "duct_dia",
        "k_d_option", "k_v_method",
        "bot_row_count", "top_row_count",
        "bot1_layout_mode", "bot1_count", "bot1_spacing", "db_bot_1",
        "bot2_layout_mode", "bot2_count", "bot2_spacing", "db_bot_2",
        "top1_layout_mode", "top1_count", "top1_spacing", "db_top_1",
        "top2_layout_mode", "top2_count", "top2_spacing", "db_top_2",
        "bot_row_1_mode", "bot_row_1_bars", "bot_row_1_spacing", "bot_row_1_dia",
        "bot_row_2_mode", "bot_row_2_bars", "bot_row_2_spacing", "bot_row_2_dia",
        "bot_row_3_mode", "bot_row_3_bars", "bot_row_3_spacing", "bot_row_3_dia",
        "bot_row_4_mode", "bot_row_4_bars", "bot_row_4_spacing", "bot_row_4_dia",
        "top_row_1_mode", "top_row_1_bars", "top_row_1_spacing", "top_row_1_dia",
        "top_row_2_mode", "top_row_2_bars", "top_row_2_spacing", "top_row_2_dia",
        "top_row_3_mode", "top_row_3_bars", "top_row_3_spacing", "top_row_3_dia",
        "top_row_4_mode", "top_row_4_bars", "top_row_4_spacing", "top_row_4_dia",
    ]

    updates: dict[str, float | int | str | bool | None] = {}
    for key in tracked_keys:
        if key in candidate_state:
            updates[key] = candidate_state.get(key)
    updates = _normalise_invalid_shear_state_updates(
        _shared_state_snapshot(),
        updates,
        source="auto_design_commit",
    )

    for key, value in updates.items():
        set_shared(key, value, source="auto_design_commit")

    hydrated_map = st.session_state.get("_hydrated_from_shared_map")
    cleared_widget_keys: set[str] = set()

    alias_widget_keys: dict[str, list[str]] = {
        "db_bot_1": ["inputs_db_bot_1", "inputs_nb_or_s_bot_1"],
        "db_bot_2": ["inputs_db_bot_2", "inputs_nb_or_s_bot_2"],
        "db_top_1": ["inputs_db_top_1", "inputs_nb_or_s_top_1"],
        "db_top_2": ["inputs_db_top_2", "inputs_nb_or_s_top_2"],
        "bot1_layout_mode": ["inputs_bot1_layout_mode"],
        "bot1_count": ["inputs_bot1_count"],
        "bot1_spacing": ["inputs_bot1_spacing"],
        "bot2_layout_mode": ["inputs_bot2_layout_mode"],
        "bot2_count": ["inputs_bot2_count"],
        "bot2_spacing": ["inputs_bot2_spacing"],
        "top1_layout_mode": ["inputs_top1_layout_mode"],
        "top1_count": ["inputs_top1_count"],
        "top1_spacing": ["inputs_top1_spacing"],
        "top2_layout_mode": ["inputs_top2_layout_mode"],
        "top2_count": ["inputs_top2_count"],
        "top2_spacing": ["inputs_top2_spacing"],
    }

    for key in list(updates.keys()):
        widget_keys_to_clear = [f"inputs_{key}"]
        widget_keys_to_clear.extend(alias_widget_keys.get(key, []))
        if key.startswith(("bot_row_", "top_row_")):
            widget_keys_to_clear.append(f"inputs_{key}")
        for widget_key in widget_keys_to_clear:
            st.session_state.pop(widget_key, None)
            st.session_state.pop(f"_cached_{widget_key}", None)
            cleared_widget_keys.add(widget_key)

    if isinstance(hydrated_map, dict):
        for key in updates:
            hydrated_map.pop(f"inputs_{key}", None)
            for widget_key in alias_widget_keys.get(key, []):
                hydrated_map.pop(widget_key, None)
        for widget_key in cleared_widget_keys:
            hydrated_map.pop(widget_key, None)

    for key in list(updates.keys()):
        st.session_state.pop(f"_cached_inputs_{key}", None)

    invalidated_recommendation_cache_keys = _invalidate_design_guide_caches(
        reason="auto_design_commit",
        updated_keys=list(updates.keys()),
    )

    st.session_state["_force_inputs_widget_reseed_once"] = True
    st.session_state["_force_auto_redesign"] = False
    st.session_state["_auto_design_invalidated"] = True
    st.session_state.pop("_auto_design_last_fingerprint", None)
    if bool(st.session_state.get("_dev_mode")):
        _agent_debug_log(
            "Set one-shot Inputs widget reseed flag after auto-design commit",
            {
                "force_inputs_widget_reseed_once": bool(st.session_state.get("_force_inputs_widget_reseed_once")),
                "invalidated_recommendation_cache_keys": invalidated_recommendation_cache_keys,
                "tracked_shared": {
                    "bot_row_1_dia": st.session_state.get("bot_row_1_dia"),
                    "bot_row_1_bars": st.session_state.get("bot_row_1_bars"),
                    "bot_row_count": st.session_state.get("bot_row_count"),
                    "bot1_count": st.session_state.get("bot1_count"),
                },
            },
            location="inputs_page.py:_commit_auto_design_candidate_to_shared",
            hypothesis_id="H121",
        )
    _agent_debug_log(
        "Cleared row widget keys after auto-design commit",
        {
            "updated_keys": sorted(list(updates.keys())),
            "cleared_widget_keys": sorted(cleared_widget_keys),
            "remaining_inputs_bot_row_1_dia": st.session_state.get("inputs_bot_row_1_dia"),
            "shared_bot_row_1_dia": st.session_state.get("bot_row_1_dia"),
            "remaining_inputs_db_bot_1": st.session_state.get("inputs_db_bot_1"),
            "shared_db_bot_1": st.session_state.get("db_bot_1"),
        },
        location="inputs_page.py:_commit_auto_design_candidate_to_shared",
        hypothesis_id="H121",
    )
    return updates


def _queue_inputs_refresh(source: str, keys: list[str], *, focus_section: str | None = None) -> None:
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


def _recommendation_fingerprint_state(state: dict) -> dict:
    fingerprint_state = {
        key: state.get(key, default)
        for key, default in SHARED_DEFAULTS.items()
    }
    fingerprint_state["_resolved_design_actions"] = _resolve_design_actions_from_state(state)
    return fingerprint_state


def _recommendation_cache_fingerprint(state: dict) -> str:
    fingerprint_state = _recommendation_fingerprint_state(state)
    try:
        return json.dumps(fingerprint_state, sort_keys=True, default=str)
    except Exception:
        return str(sorted((str(key), str(value)) for key, value in fingerprint_state.items()))


def _cached_recommendation(cache_name: str, state: dict):
    cache_key = f"_recommendation_cache_{cache_name}"
    cache_entry = st.session_state.get(cache_key)
    fingerprint = _recommendation_cache_fingerprint(state)
    if isinstance(cache_entry, dict) and cache_entry.get("fingerprint") == fingerprint:
        return cache_entry.get("recommendation")
    return None


def _store_cached_recommendation(cache_name: str, state: dict, recommendation) -> None:
    cache_key = f"_recommendation_cache_{cache_name}"
    st.session_state[cache_key] = {
        "fingerprint": _recommendation_cache_fingerprint(state),
        "recommendation": recommendation,
    }


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
            location="inputs_page.py:_invalidate_design_guide_caches",
            hypothesis_id="H301",
        )
    return removed


def _debug_log_design_guide_consistency(*, source: str, applied_candidate: dict | None = None) -> None:
    if not bool(st.session_state.get("_dev_mode")):
        return
    fresh_state = _shared_state_snapshot()
    design_context = _build_design_actions_context(fresh_state)
    fresh_overview = _collect_design_overview(fresh_state, context=design_context)
    guide_debug: dict = {"overview": fresh_overview}
    _compute_design_guidance_items(fresh_state, debug_sink=guide_debug)
    efficiency_state = dict(guide_debug.get("efficiency_tightening_state") or {})
    next_mode_recommendation = dict(efficiency_state.get("mode_tightening") or {})
    current_summary = _overview_debug_summary(fresh_state, fresh_overview)
    applied_summary = _candidate_debug_summary(applied_candidate)
    warning = False
    if applied_summary is not None and applied_summary.get("bottom_reo_label") != current_summary.get("bottom_reo_label"):
        warning = True
    if next_mode_recommendation and str(next_mode_recommendation.get("label") or "") == str(current_summary.get("bottom_reo_label") or ""):
        warning = True
    _agent_debug_log(
        "Post-commit design guide consistency check",
        {
            "source": source,
            "warning": warning,
            "committed_bottom_reo_label": current_summary.get("bottom_reo_label"),
            "overview_bottom_reo_label": current_summary.get("bottom_reo_label"),
            "applied_candidate_label": None if applied_summary is None else applied_summary.get("bottom_reo_label"),
            "current_utilisation_shown": current_summary.get("worst_util"),
            "actual_overview_utilisation": current_summary.get("worst_util"),
            "next_recommendation_label": next_mode_recommendation.get("label"),
            "next_recommendation_expected_util": next_mode_recommendation.get("expected_util"),
            "next_recommendation_optimisation_score": next_mode_recommendation.get("optimisation_score"),
            "guidance_branch": guide_debug.get("guidance_branch"),
            "overview_summary": current_summary,
            "applied_summary": applied_summary,
            "next_recommendation_summary": next_mode_recommendation.get("candidate_summary"),
        },
        location="inputs_page.py:_debug_log_design_guide_consistency",
        hypothesis_id="H302",
    )


def _resolve_popover_recommendation(
    *,
    cache_name: str,
    state: dict,
    button_key: str,
    compute_fn,
    empty_message: str,
):
    recommendation = _cached_recommendation(cache_name, state)
    generate_pressed = st.button(
        "Generate current recommendation" if recommendation is None else "Refresh recommendation",
        key=f"{button_key}_generate",
        type="secondary",
        use_container_width=True,
    )
    # region agent log
    _agent_debug_log(
        "Rendered popover recommendation resolver",
        {
            "cache_name": cache_name,
            "button_key": button_key,
            "generate_pressed": bool(generate_pressed),
            "has_cached_recommendation": recommendation is not None,
        },
        location="inputs_page.py:_resolve_popover_recommendation",
        hypothesis_id="H13",
    )
    # endregion
    if generate_pressed:
        recommendation = compute_fn(state)
        _store_cached_recommendation(cache_name, state, recommendation)
    if recommendation is None:
        st.caption(empty_message)
    return recommendation


def _clear_legacy_auto_design_request_flags() -> None:
    """Session flags for the legacy progressive auto-design panel; clear when guidance commits changes."""
    st.session_state.pop("_auto_design_reason", None)
    st.session_state["_auto_design_requested"] = False


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


def _apply_shared_updates(updates: dict, *, source: str, rerun: bool = True, focus_section: str | None = None) -> bool:
    if not updates:
        return False
    prior_state = _shared_state_snapshot()
    updates = _normalise_invalid_shear_state_updates(prior_state, updates, source=source)
    expected_state = dict(prior_state)
    expected_state.update(updates)
    applied_candidate = evaluate_candidate_full(
        _guidance_state_snapshot(expected_state),
        source=f"{source}:post_apply_preview",
        updates=updates,
    )
    _set_shared_updates(updates, source=source)
    recalc_derived_values()
    compute_all_results()
    if source != "fast_mode:auto_design_to_pass":
        update_results(auto_design_steps=[], auto_design_status="")
    if str(source).startswith("guidance:"):
        _clear_legacy_auto_design_request_flags()
        _finalize_design_guide_apply_step_history(
            prior_state=prior_state,
            source=source,
            applied_candidate=applied_candidate,
        )
        _store_design_guide_apply_banner_payload(prior_state, _shared_state_snapshot())
        _record_design_guide_auto_geometry_applied(prior_state, updates)
        st.session_state[DESIGN_GUIDE_PANEL_BASELINE_FP_KEY] = _design_guide_cache_fingerprint(
            _shared_state_snapshot(),
        )
        st.session_state.pop(DESIGN_GUIDE_NEEDS_REFRESH_KEY, None)
    _debug_log_design_guide_consistency(source=source, applied_candidate=applied_candidate)
    _invalidate_design_guide_caches(
        reason=source,
        updated_keys=list(updates.keys()),
        preserve_apply_banner=bool(str(source).startswith("guidance:")),
    )
    _queue_inputs_refresh(source, list(updates.keys()), focus_section=focus_section)
    if rerun:
        st.rerun()
    return True


def _guidance_action_updates(action_type: str, payload: dict, *, state: dict | None = None) -> dict | None:
    current_state = state or _shared_state_snapshot()
    payload = payload or {}

    if action_type == "apply_resolved_candidate":
        resolved_updates = payload.get("resolved_candidate_updates")
        if isinstance(resolved_updates, dict) and resolved_updates:
            return dict(resolved_updates)
        explicit_updates = payload.get("updates")
        return dict(explicit_updates) if isinstance(explicit_updates, dict) and explicit_updates else None

    if action_type == "apply_compound_guidance":
        u = payload.get("updates")
        return dict(u) if isinstance(u, dict) else None

    if action_type == "apply_geometry_recommendation":
        explicit_updates = (payload or {}).get("updates")
        if isinstance(explicit_updates, dict) and explicit_updates:
            return dict(explicit_updates)
        recommendation = _compute_geometry_recommendation(current_state)
        return dict((recommendation or {}).get("updates") or {})

    if action_type == "apply_mode_recommendation":
        explicit_updates = payload.get("updates")
        return explicit_updates if isinstance(explicit_updates, dict) else None

    if action_type == "apply_bottom_recommendation":
        explicit_updates = payload.get("updates")
        if isinstance(explicit_updates, dict) and explicit_updates:
            if _updates_match_state(current_state, explicit_updates):
                return None
            return dict(explicit_updates)
        recommendation = _compute_bottom_reo_recommendation(current_state)
        if recommendation and recommendation.get("updates"):
            return recommendation.get("updates")
        arrangement = (recommendation or {}).get("arrangement")
        return _bottom_arrangement_to_shared_updates(arrangement) if isinstance(arrangement, dict) else None

    if action_type == "apply_shear_recommendation":
        explicit_updates = payload.get("updates")
        if isinstance(explicit_updates, dict):
            return explicit_updates
        recommendation = _compute_shear_recommendation(current_state)
        return (recommendation or {}).get("updates")

    if action_type == "reduce_bottom_reinforcement":
        explicit_updates = payload.get("updates")
        if isinstance(explicit_updates, dict):
            if any(
                key.startswith("bot_row_") for key in explicit_updates
            ) or "bot_row_count" in explicit_updates:
                return explicit_updates
            return _bottom_arrangement_to_shared_updates(explicit_updates)
        recommendation = _compute_bottom_reo_tightening_recommendation(current_state)
        arrangement = (recommendation or {}).get("arrangement")
        return _bottom_arrangement_to_shared_updates(arrangement) if isinstance(arrangement, dict) else None

    if action_type == "increase_link_spacing":
        explicit_updates = payload.get("updates")
        if isinstance(explicit_updates, dict):
            return explicit_updates
        recommendation = _compute_shear_tightening_recommendation(current_state)
        if recommendation and recommendation.get("action_type") == "increase_link_spacing":
            return recommendation.get("updates")
        return None

    if action_type == "reduce_number_of_legs":
        explicit_updates = payload.get("updates")
        if isinstance(explicit_updates, dict):
            return explicit_updates
        recommendation = _compute_shear_tightening_recommendation(current_state)
        if recommendation and recommendation.get("action_type") == "reduce_number_of_legs":
            return recommendation.get("updates")
        return None

    if action_type == "tighten_geometry":
        explicit_updates = payload.get("updates")
        if isinstance(explicit_updates, dict):
            return explicit_updates
        recommendation = _compute_geometry_tightening_recommendation(current_state)
        return (recommendation or {}).get("updates")

    updates: dict[str, float | int | str] = {}

    if action_type == "increase_depth":
        current_D = float(current_state.get("D", 600.0) or 600.0)
        delta_mm = float(payload.get("delta_mm", 50) or 50.0)
        new_D = max(100.0, current_D + delta_mm)
        updates["D"] = float(int(round(new_D / 10.0) * 10))

    elif action_type == "increase_width":
        width_key, _, current_width = _resolve_geometry_width_context(current_state)
        delta_mm = float(payload.get("delta_mm", 50) or 50.0)
        new_width = max(100.0, current_width + delta_mm)
        updates[width_key] = float(int(round(new_width / 10.0) * 10))

    elif action_type == "reduce_link_spacing":
        explicit_updates = payload.get("updates")
        if isinstance(explicit_updates, dict) and explicit_updates:
            if _updates_match_state(current_state, explicit_updates):
                return None
            return dict(explicit_updates)
        current_spacing = float(current_state.get("s_lig", 200.0) or 200.0)
        delta_mm = float(payload.get("delta_mm", 25) or 25.0)
        minimum_spacing = float(payload.get("minimum_spacing", min(REO_SPACINGS)) or min(REO_SPACINGS))
        new_spacing = max(minimum_spacing, current_spacing - delta_mm)
        updates["s_lig"] = float(int(round(new_spacing / 5.0) * 5))
        if _updates_match_state(current_state, updates):
            return None

    elif action_type == "deflection_reduce_sustained_load":
        explicit_updates = payload.get("updates")
        if isinstance(explicit_updates, dict) and explicit_updates:
            if _updates_match_state(current_state, explicit_updates):
                return None
            return dict(explicit_updates)
        return None

    elif action_type == "reduce_bar_spacing":
        delta_mm = float(payload.get("delta_mm", 25) or 25.0)
        minimum_spacing = float(payload.get("minimum_spacing", min(REO_SPACINGS)) or min(REO_SPACINGS))
        layout_mode = str(current_state.get("bot1_layout_mode", "Count") or "Count")
        if layout_mode == "Spacing":
            current_spacing = float(current_state.get("bot1_spacing", 200.0) or 200.0)
            new_spacing = max(minimum_spacing, current_spacing - delta_mm)
            resolved_spacing = float(int(round(new_spacing / 5.0) * 5))
            updates["bot1_spacing"] = resolved_spacing
            updates["bot_row_1_mode"] = "Spacing"
            updates["bot_row_1_spacing"] = resolved_spacing
            updates["bot_row_count"] = max(_int_from_state(current_state, "bot_row_count", 1), 1)
        else:
            current_count = int(current_state.get("bot1_count", 4) or 4)
            if current_count < max(REO_COUNTS_0_12):
                updates.update(_bottom_arrangement_to_shared_updates({
                    "bot1_count": current_count + 1,
                    "bot2_count": int(current_state.get("bot2_count", 0) or 0),
                    "db_bot_1": int(current_state.get("db_bot_1", 20) or 20),
                    "db_bot_2": int(current_state.get("db_bot_2", current_state.get("db_bot_1", 20)) or current_state.get("db_bot_1", 20)),
                }))
            else:
                current_count_2 = int(current_state.get("bot2_count", 0) or 0)
                if current_count_2 < max(REO_COUNTS_0_12):
                    updates.update(_bottom_arrangement_to_shared_updates({
                        "bot1_count": current_count,
                        "bot2_count": current_count_2 + 1,
                        "db_bot_1": int(current_state.get("db_bot_1", 20) or 20),
                        "db_bot_2": int(current_state.get("db_bot_2", current_state.get("db_bot_1", 20)) or current_state.get("db_bot_1", 20)),
                    }))

    return updates or None


def _describe_guidance_step(before_state: dict, after_state: dict, action_type: str, updates: dict) -> str:
    if "D" in updates:
        before_depth = int(float(before_state.get("D", 0.0) or 0.0))
        after_depth = int(float(after_state.get("D", 0.0) or 0.0))
        verb = "Reduced" if after_depth < before_depth else "Increased"
        return f"{verb} depth D from {before_depth} to {after_depth} mm."
    width_key, width_label, _ = _resolve_geometry_width_context(after_state)
    if width_key in updates:
        before_width = int(float(before_state.get(width_key, 0.0) or 0.0))
        after_width = int(float(after_state.get(width_key, 0.0) or 0.0))
        width_short = "b" if width_key == "b" else width_key
        verb = "Reduced" if after_width < before_width else "Increased"
        return f"{verb} {width_short} from {before_width} to {after_width} mm."
    if any(key in updates for key in ("bot1_count", "bot2_count", "db_bot_1", "db_bot_2", "Ast_bot")):
        return f"Updated bottom reinforcement from {_bottom_reo_state_label(before_state)} to {_bottom_reo_state_label(after_state)}."
    if any(key in updates for key in ("s_lig", "lig_legs", "lig_d")):
        return f"Updated shear reinforcement from {_shear_state_label(before_state)} to {_shear_state_label(after_state)}."
    load_keys = ("g_udl_kNm_per_m", "g_kNm", "g_line_kNm")
    if any(key in updates for key in load_keys):
        parts: list[str] = []
        for key in load_keys:
            if key not in updates:
                continue
            try:
                b0 = float(before_state.get(key, 0.0) or 0.0)
                a0 = float(after_state.get(key, 0.0) or 0.0)
                parts.append(f"{key} {b0:.3f} → {a0:.3f} kN/m")
            except Exception:
                parts.append(str(key))
        if parts:
            return "Adjusted sustained load inputs: " + "; ".join(parts) + "."
    return f"Applied {action_type.replace('_', ' ')}."
    st.rerun()


def _failed_check_labels(candidate: dict) -> list[str]:
    statuses = ((candidate or {}).get("overview") or {}).get("statuses", {})
    labels: list[str] = []
    for key in ("bending", "shear", "crack", "deflection"):
        if str(statuses.get(key, "") or "") == "FAIL":
            labels.append(key.replace("_", " "))
    return labels


def clone_candidate_state_for_next_hop(candidate: dict) -> dict:
    return _guidance_state_snapshot(dict(candidate.get("state") or {}))


def build_auto_design_step_summary(old_candidate: dict, new_candidate: dict, *, hop: int, phase_label: str = "Hop") -> str:
    old_du = _candidate_bending_demand_util(old_candidate)
    new_du = _candidate_bending_demand_util(new_candidate)
    old_util = float(old_du) if old_du is not None else float(_candidate_objective_util(old_candidate))
    new_util = float(new_du) if new_du is not None else float(_candidate_objective_util(new_candidate))
    util_label = "bending Mu*/phiMu" if old_du is not None and new_du is not None else "optimisation score"
    old_status = "PASS" if bool(old_candidate.get("is_compliant")) else "FAIL"
    new_status = "PASS" if bool(new_candidate.get("is_compliant")) else "FAIL"
    summary = (
        f"{phase_label} {hop}: "
        f"D {float(old_candidate.get('depth', 0.0) or 0.0):.0f} -> {float(new_candidate.get('depth', 0.0) or 0.0):.0f} mm, "
        f"bottom steel {float(old_candidate.get('Ast_bot', 0.0) or 0.0):.0f} -> {float(new_candidate.get('Ast_bot', 0.0) or 0.0):.0f} mm2, "
        f"{util_label} {old_util:.2f} -> {new_util:.2f}, "
        f"status {old_status} -> {new_status}."
    )
    old_failed = set(_failed_check_labels(old_candidate))
    new_failed = set(_failed_check_labels(new_candidate))
    cleared = sorted(old_failed - new_failed)
    if cleared:
        summary += f" Cleared: {', '.join(cleared)}."
    remaining = sorted(new_failed)
    if remaining and new_status == "FAIL":
        summary += f" Remaining: {', '.join(remaining)}."
    return summary


def _candidate_state_signature(candidate: dict | None) -> tuple:
    if not candidate:
        return ()
    return _make_auto_design_candidate_key(clone_candidate_state_for_next_hop(candidate))


def is_valid_progress_while_failing(new_candidate: dict | None, old_candidate: dict | None) -> bool:
    if not new_candidate or not old_candidate:
        return False
    if bool(new_candidate.get("is_compliant")):
        return True
    old_failed = set(_failed_check_labels(old_candidate))
    new_failed = set(_failed_check_labels(new_candidate))
    old_util = float(old_candidate.get("worst_util", 999.0) or 999.0)
    new_util = float(new_candidate.get("worst_util", 999.0) or 999.0)
    if new_failed != old_failed and len(new_failed) < len(old_failed):
        return True
    if new_util < old_util - 0.01:
        return True
    return _candidate_state_signature(new_candidate) != _candidate_state_signature(old_candidate)


def candidate_is_overdesigned(result: dict, mode_config: dict) -> bool:
    if not result or not bool(result.get("is_compliant")):
        return False
    util = _candidate_objective_util(result)
    return util < float(mode_config.get("target_util_min", 0.8) or 0.8) - 0.05


def _render_fast_model_block(sync_callbacks: dict) -> None:
    title_col, toggle_col = st.columns([4.0, 1.4], gap="small")
    with title_col:
        st.markdown("## Model")
    with toggle_col:
        show_3d = _shared_toggle(
            "3D model",
            "inputs_fast_mode_show_3d_toggle",
            "fast_mode_show_3d",
            False,
            sync_callbacks,
        )
    if show_3d:
        _render_3d_diagram_block(compact=True)
    else:
        _render_section_2d_diagram_block(compact=True)


def _render_fast_phase_header(label: str) -> None:
    st.markdown(f"<div class='fast-phase-label'>{label}</div>", unsafe_allow_html=True)


def _render_fast_next_hint(message: str, *, css_extra_class: str = "") -> None:
    cls = "fast-next-hint" + (f" {css_extra_class}" if css_extra_class else "")
    st.markdown(f"<div class='{cls}'>{html.escape(message)}</div>", unsafe_allow_html=True)


def _updates_match_state(state: dict, updates: dict) -> bool:
    for key, expected in updates.items():
        actual = state.get(key)
        if isinstance(expected, float):
            try:
                if abs(float(actual) - float(expected)) > 1e-9:
                    return False
            except Exception:
                return False
            continue
        if actual != expected:
            return False
    return True


def _apply_geometry_recommendation(*, source: str) -> bool:
    recommendation = _compute_geometry_recommendation(_shared_state_snapshot())
    if not recommendation:
        return False
    return _apply_shared_updates(recommendation["updates"], source=source)


def _apply_bottom_reo_recommendation(*, source: str) -> bool:
    recommendation = _compute_bottom_reo_recommendation(_shared_state_snapshot())
    if not recommendation:
        return False
    updates = recommendation.get("updates") or _bottom_arrangement_to_shared_updates(recommendation.get("arrangement") or {})
    return _apply_shared_updates(updates, source=source)


def _apply_shear_recommendation(*, source: str) -> bool:
    recommendation = _compute_shear_recommendation(_shared_state_snapshot())
    if not recommendation:
        return False
    return _apply_shared_updates(recommendation["updates"], source=source)


def apply_guided_solve_sequence(*, source: str) -> bool:
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
            current_candidate = evaluate_candidate_full(_guidance_state_snapshot(), source="guidance_sequence_step")
            if current_candidate and bool(current_candidate.get("is_compliant")):
                st.rerun()
                return True
        if not changed_this_cycle:
            break
    if any_applied:
        st.rerun()
    return any_applied


def _apply_resolved_candidate_payload(payload: dict) -> bool:
    payload_dict = dict(payload or {})
    label = str(payload_dict.get("resolved_candidate_label") or payload_dict.get("label") or "Apply recommendation").strip()
    candidate_action_type = str(payload_dict.get("resolved_candidate_action_type") or "apply_compound_guidance").strip()
    updates = dict(payload_dict.get("resolved_candidate_updates") or {})
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
    expected_state = dict(prior_state)
    expected_state.update(updates)
    applied_candidate = evaluate_candidate_full(
        _guidance_state_snapshot(expected_state),
        source="guidance:apply_resolved_candidate:post_apply_preview",
        updates=updates,
    )
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

    _set_shared_updates(updates, source="guidance:apply_resolved_candidate")

    try:
        recalc_derived_values()
    except Exception:
        pass
    try:
        derive_design_actions()
    except Exception:
        pass

    try:
        compute_all_results()
    except Exception:
        pass
    try:
        update_results(auto_design_steps=[], auto_design_status="")
    except Exception:
        pass
    _clear_legacy_auto_design_request_flags()
    _debug_log_design_guide_consistency(
        source="guidance:apply_resolved_candidate",
        applied_candidate=applied_candidate,
    )
    post_apply_candidate = evaluate_candidate_full(
        _guidance_state_snapshot(),
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
    _queue_inputs_refresh(
        "guidance:apply_resolved_candidate",
        list(updates.keys()),
        focus_section="model",
    )

    try:
        st.rerun()
    except Exception:
        pass
    return True


def apply_guidance_action(action_type: str, payload: dict) -> bool:
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
            return False
        recalc_derived_values()
        compute_all_results()
        update_results(auto_design_steps=[], auto_design_status="")
        _clear_legacy_auto_design_request_flags()
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
        _queue_inputs_refresh(f"guidance:{action_type}", list(final_updates.keys()), focus_section="model")
        st.rerun()
        return True
    current_candidate = evaluate_candidate_full(_guidance_state_snapshot(), source="guidance_action_seed")
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
    # region agent log
    _agent_debug_log(
        "Completed guidance action update resolution",
        {
            "action_type": str(action_type or ""),
            "resolved_updates": 0 if not updates else len(updates),
            "duration_ms": round((time.perf_counter() - started_at) * 1000, 1),
        },
        location="inputs_page.py:apply_guidance_action",
        hypothesis_id="H21",
    )
    # endregion
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


def _candidate_updates_signature(candidate: dict) -> tuple:
    updates = candidate.get("updates") or {}
    return tuple(sorted((key, str(value)) for key, value in updates.items()))


def _build_efficiency_auto_design_candidates(
    state: dict,
    mode_config: dict,
    current_candidate: dict,
) -> list[dict]:
    candidates: list[dict] = []
    utils = current_candidate.get("overview", {}).get("utils", {})

    bottom_tighten = None
    bending_util = utils.get("bending")
    if bending_util is not None and float(bending_util) <= GUIDANCE_INEFFICIENT_UTIL_THRESHOLD:
        bottom_tighten = _compute_bottom_reo_tightening_recommendation(state)
    if bottom_tighten:
        bottom_updates = _bottom_arrangement_to_shared_updates(bottom_tighten.get("arrangement") or {})
        if bottom_updates:
            candidate = _evaluate_auto_design_candidate(
                state,
                updates=bottom_updates,
                source="efficiency_bottom",
                label=str(bottom_tighten.get("label") or "Tighten bottom reinforcement"),
                action_type="reduce_bottom_reinforcement",
            )
            if candidate is not None:
                candidates.append(candidate)

    shear_tighten = None
    shear_util = utils.get("shear")
    if shear_util is not None and float(shear_util) <= GUIDANCE_INEFFICIENT_UTIL_THRESHOLD:
        shear_tighten = _compute_shear_tightening_recommendation(state)
    if shear_tighten and shear_tighten.get("updates"):
        candidate = _evaluate_auto_design_candidate(
            state,
            updates=dict(shear_tighten.get("updates") or {}),
            source="efficiency_shear",
            label=str(shear_tighten.get("label") or "Tighten shear reinforcement"),
            action_type=str(shear_tighten.get("action_type") or "increase_link_spacing"),
        )
        if candidate is not None:
            candidates.append(candidate)

    geometry_tighten = _compute_geometry_tightening_recommendation(state)
    if geometry_tighten and geometry_tighten.get("updates"):
        candidate = _evaluate_auto_design_candidate(
            state,
            updates=dict(geometry_tighten.get("updates") or {}),
            source="efficiency_geometry",
            label=str(geometry_tighten.get("label") or "Tighten geometry"),
            action_type="tighten_geometry",
        )
        if candidate is not None:
            candidates.append(candidate)

    seed_candidate = _evaluate_auto_design_candidate(state, source="seed")
    if seed_candidate is not None:
        for candidate in candidates:
            candidate["score"] = _score_auto_design_candidate(candidate, mode_config, seed_candidate)
    return candidates


def _build_auto_design_candidates(state: dict, mode_config: dict, seed_candidate: dict, current_candidate: dict) -> list[dict]:
    started_at = time.perf_counter()
    candidates = [current_candidate]
    bottom_started_at = time.perf_counter()
    bottom_candidates = _generate_bottom_reo_candidates(state, mode_config)
    bottom_duration_ms = (time.perf_counter() - bottom_started_at) * 1000
    shear_started_at = time.perf_counter()
    shear_candidates = _generate_shear_candidates(state, mode_config)
    shear_duration_ms = (time.perf_counter() - shear_started_at) * 1000
    geometry_started_at = time.perf_counter()
    geometry_candidates = _generate_geometry_candidates(
        state,
        mode_config,
        current_candidate,
        bottom_candidates=bottom_candidates,
        shear_candidates=shear_candidates,
    )
    geometry_duration_ms = (time.perf_counter() - geometry_started_at) * 1000
    candidates.extend(bottom_candidates)
    candidates.extend(shear_candidates)
    candidates.extend(geometry_candidates)
    deduped: dict[tuple, dict] = {}
    for candidate in candidates:
        signature = _candidate_updates_signature(candidate)
        existing = deduped.get(signature)
        if existing is None or float(candidate.get("score", float("inf"))) < float(existing.get("score", float("inf"))):
            deduped[signature] = candidate
    def _group_summary(group: list[dict]) -> dict:
        if not group:
            return {"count": 0}
        best_worst = min(float(item.get("worst_util", float("inf")) or float("inf")) for item in group)
        bending_utils = [
            float(item.get("overview", {}).get("utils", {}).get("bending"))
            for item in group
            if item.get("overview", {}).get("utils", {}).get("bending") is not None
        ]
        shear_utils = [
            float(item.get("overview", {}).get("utils", {}).get("shear"))
            for item in group
            if item.get("overview", {}).get("utils", {}).get("shear") is not None
        ]
        crack_utils = [
            float(item.get("overview", {}).get("utils", {}).get("crack"))
            for item in group
            if item.get("overview", {}).get("utils", {}).get("crack") is not None
        ]
        deflection_utils = [
            float(item.get("overview", {}).get("utils", {}).get("deflection"))
            for item in group
            if item.get("overview", {}).get("utils", {}).get("deflection") is not None
        ]
        flexural_utils = [
            float(item.get("bending_components", {}).get("flexural_util"))
            for item in group
            if item.get("bending_components", {}).get("flexural_util") is not None
        ]
        ductility_utils = [
            float(item.get("bending_components", {}).get("ductility_util"))
            for item in group
            if item.get("bending_components", {}).get("ductility_util") is not None
        ]
        return {
            "count": len(group),
            "best_worst_util": best_worst,
            "best_bending_util": min(bending_utils) if bending_utils else None,
            "best_shear_util": min(shear_utils) if shear_utils else None,
            "best_crack_util": min(crack_utils) if crack_utils else None,
            "best_deflection_util": min(deflection_utils) if deflection_utils else None,
            "best_flexural_util": min(flexural_utils) if flexural_utils else None,
            "best_ductility_util": min(ductility_utils) if ductility_utils else None,
        }
    # region agent log
    _agent_debug_log(
        "Built auto-design candidate pool",
        {
            "counts": {
                "current": 1,
                "bottom": len(bottom_candidates),
                "shear": len(shear_candidates),
                "geometry": len(geometry_candidates),
                "total_raw": len(candidates),
                "total_deduped": len(deduped),
            },
            "stage_durations_ms": {
                "bottom": round(bottom_duration_ms, 1),
                "shear": round(shear_duration_ms, 1),
                "geometry": round(geometry_duration_ms, 1),
                "total": round((time.perf_counter() - started_at) * 1000, 1),
            },
            "empty_update_candidates": sum(1 for candidate in candidates if not candidate.get("updates")),
            "current_utils": dict(current_candidate.get("overview", {}).get("utils", {})),
            "current_statuses": dict(current_candidate.get("overview", {}).get("statuses", {})),
            "current_bending_components": dict(current_candidate.get("bending_components", {})),
            "group_summary": {
                "bottom": _group_summary(bottom_candidates),
                "shear": _group_summary(shear_candidates),
                "geometry": _group_summary(geometry_candidates),
            },
        },
        location="inputs_page.py:_build_auto_design_candidates",
        hypothesis_id="H2",
    )
    # endregion
    return list(deduped.values())


def _candidate_util_distance(candidate: dict, mode_config: dict) -> float:
    util = _candidate_objective_util(candidate)
    target_min = float(mode_config["target_util_min"])
    target_max = float(mode_config["target_util_max"])
    target_mid = _mode_target_midpoint(mode_config)
    if util < target_min:
        return target_min - util
    if util > target_max:
        return util - target_max
    return abs(util - target_mid)


def _candidate_layer_imbalance_penalty(candidate: dict) -> float:
    state = candidate.get("state") or {}
    count_1 = _int_from_state(state, "bot1_count", 0)
    count_2 = _int_from_state(state, "bot2_count", 0)
    if count_2 <= 0:
        return 0.0
    return float(abs(count_1 - count_2))


def compute_reo_complexity(candidate: dict) -> float:
    total_bar_count = int(candidate.get("bar_count", 0) or 0)
    row_count = int(candidate.get("row_count", 1) or 1)
    congestion_index = float(candidate.get("reo_congestion_index", 0.0) or 0.0)
    layer_imbalance_penalty = _candidate_layer_imbalance_penalty(candidate)
    return (
        total_bar_count * 1.0
        + row_count * 8.0
        + congestion_index * 12.0
        + layer_imbalance_penalty * 3.0
    )


def _candidate_is_practical(candidate: dict, mode_config: dict) -> bool:
    if not candidate:
        return False
    congestion_limit = float(mode_config.get("practicality_congestion_limit", 20.0))
    return (
        int(candidate.get("row_count", 0) or 0) <= 2
        and float(candidate.get("reo_congestion_index", 0.0) or 0.0) <= congestion_limit
    )


def depth_delta_mm(candidate_a: dict, candidate_b: dict) -> float:
    return float(candidate_a.get("depth", 0.0) or 0.0) - float(candidate_b.get("depth", 0.0) or 0.0)


def reo_complexity_delta(candidate_a: dict, candidate_b: dict) -> float:
    return float(candidate_a.get("reo_complexity", compute_reo_complexity(candidate_a)) or 0.0) - float(
        candidate_b.get("reo_complexity", compute_reo_complexity(candidate_b)) or 0.0
    )


def is_materially_shallower(candidate: dict, seed_candidate: dict, mode_config: dict) -> bool:
    threshold = float(mode_config.get("material_depth_delta_mm", 25.0))
    return depth_delta_mm(candidate, seed_candidate) <= -threshold


def is_materially_simpler_reo(candidate: dict, seed_candidate: dict, mode_config: dict) -> bool:
    threshold = float(mode_config.get("material_reo_complexity_delta", 4.0))
    if int(candidate.get("row_count", 0) or 0) < int(seed_candidate.get("row_count", 0) or 0):
        return True
    if int(candidate.get("bar_count", 0) or 0) <= int(seed_candidate.get("bar_count", 0) or 0) - 2:
        return True
    return reo_complexity_delta(candidate, seed_candidate) <= -threshold


def _candidate_materially_better_for_mode(candidate: dict, seed_candidate: dict, mode_config: dict) -> bool:
    strategy = str(mode_config.get("search_strategy", "balanced") or "balanced")
    if not candidate or not bool(candidate.get("is_compliant")):
        return False
    if strategy == "shallow":
        return _candidate_is_practical(candidate, mode_config) and is_materially_shallower(candidate, seed_candidate, mode_config)
    if strategy == "low_reo":
        return _candidate_is_practical(candidate, mode_config) and is_materially_simpler_reo(candidate, seed_candidate, mode_config)
    if _candidate_in_target_band(candidate, mode_config) and not _candidate_in_target_band(seed_candidate, mode_config):
        return True
    return float(candidate.get("score", float("inf")) or float("inf")) < float(seed_candidate.get("score", float("inf")) or float("inf")) - 0.5


def _candidate_sort_key_for_mode(candidate: dict, mode_config: dict) -> tuple:
    strategy = str(mode_config.get("search_strategy", "balanced") or "balanced")
    compliant_penalty = 0 if bool(candidate.get("is_compliant")) else 1
    practical_penalty = 0 if _candidate_is_practical(candidate, mode_config) else 1
    violation = _candidate_violation_score(candidate)
    fail_count = int(candidate.get("fail_count", 0) or 0)
    worst_util = float(candidate.get("worst_util", float("inf")) or float("inf"))
    complexity = float(candidate.get("reo_complexity", compute_reo_complexity(candidate)) or 0.0)
    util_distance = _candidate_util_distance(candidate, mode_config)
    depth = float(candidate.get("depth", 0.0) or 0.0)
    width = float(candidate.get("width", 0.0) or 0.0)
    bar_count = int(candidate.get("bar_count", 0) or 0)
    row_count = int(candidate.get("row_count", 0) or 0)
    steel_area = float(candidate.get("Ast_bot", 0.0) or 0.0) + float(candidate.get("Ast_top", 0.0) or 0.0)
    shallow_tier, _ = _shallower_beam_candidate_tier(candidate)
    shallow_metrics = _shallower_beam_metrics(
        candidate,
        {
            "state": dict(candidate.get("state") or {}),
            "depth": float(candidate.get("_seed_depth", depth) or depth),
            "width": float(candidate.get("_seed_width", width) or width),
            "Ast_bot": float(candidate.get("_seed_ast_bot", candidate.get("Ast_bot", 0.0)) or candidate.get("Ast_bot", 0.0) or 0.0),
        },
    )
    if bool(candidate.get("_ductility_priority")):
        ductility_util = _candidate_ductility_util(candidate)
        ductility_value = float(ductility_util) if ductility_util is not None else float("inf")
        tier = int(candidate.get("_ductility_tier", 4) or 4)
        return (
            compliant_penalty,
            0 if ductility_value <= 1.0 else 1,
            max(ductility_value - 1.0, 0.0),
            ductility_value,
            tier,
            steel_area,
            practical_penalty,
            row_count,
            bar_count,
            depth,
            width,
            util_distance,
            complexity,
        )
    if compliant_penalty:
        if strategy == "shallow":
            return (
                compliant_penalty,
                fail_count,
                violation,
                worst_util,
                0 if shallow_metrics.get("materially_shallower") else 1,
                shallow_tier,
                depth,
                float(shallow_metrics.get("width_growth", 0.0) or 0.0),
                float(shallow_metrics.get("reinforcement_growth", 0.0) or 0.0),
                practical_penalty,
                util_distance,
                complexity,
                steel_area,
                width,
            )
        if strategy == "low_reo":
            return (compliant_penalty, fail_count, violation, worst_util, practical_penalty, util_distance, complexity, row_count, bar_count, depth, steel_area)
        return (
            compliant_penalty,
            fail_count,
            violation,
            worst_util,
            practical_penalty,
            util_distance,
            depth,
            complexity,
            width,
            steel_area,
        )
    if strategy == "shallow":
        return (
            compliant_penalty,
            0 if shallow_metrics.get("materially_shallower") else 1,
            shallow_tier,
            depth,
            float(shallow_metrics.get("width_growth", 0.0) or 0.0),
            float(shallow_metrics.get("reinforcement_growth", 0.0) or 0.0),
            practical_penalty,
            util_distance,
            complexity,
            steel_area,
            width,
        )
    if strategy == "low_reo":
        return (compliant_penalty, practical_penalty, complexity, row_count, bar_count, util_distance, depth, steel_area)
    return (
        compliant_penalty,
        0 if _candidate_in_target_band(candidate, mode_config) else 1,
        practical_penalty,
        util_distance,
        depth,
        complexity,
        width,
        steel_area,
    )


def _candidate_dominates_for_mode(candidate_a: dict, candidate_b: dict, mode_config: dict) -> bool:
    if not candidate_a or not candidate_b:
        return False
    if not bool(candidate_a.get("is_compliant")) or not bool(candidate_b.get("is_compliant")):
        return False
    strategy = str(mode_config.get("search_strategy", "balanced") or "balanced")
    util_a = _candidate_util_distance(candidate_a, mode_config)
    util_b = _candidate_util_distance(candidate_b, mode_config)
    complexity_a = float(candidate_a.get("reo_complexity", compute_reo_complexity(candidate_a)) or 0.0)
    complexity_b = float(candidate_b.get("reo_complexity", compute_reo_complexity(candidate_b)) or 0.0)
    depth_a = float(candidate_a.get("depth", 0.0) or 0.0)
    depth_b = float(candidate_b.get("depth", 0.0) or 0.0)
    if strategy == "shallow":
        metrics_a = _shallower_beam_metrics(
            candidate_a,
            {
                "state": dict(candidate_a.get("state") or {}),
                "depth": float(candidate_a.get("_seed_depth", depth_a) or depth_a),
                "width": float(candidate_a.get("_seed_width", float(candidate_a.get("width", 0.0) or 0.0)) or float(candidate_a.get("width", 0.0) or 0.0)),
                "Ast_bot": float(candidate_a.get("_seed_ast_bot", candidate_a.get("Ast_bot", 0.0)) or candidate_a.get("Ast_bot", 0.0) or 0.0),
            },
        )
        metrics_b = _shallower_beam_metrics(
            candidate_b,
            {
                "state": dict(candidate_b.get("state") or {}),
                "depth": float(candidate_b.get("_seed_depth", depth_b) or depth_b),
                "width": float(candidate_b.get("_seed_width", float(candidate_b.get("width", 0.0) or 0.0)) or float(candidate_b.get("width", 0.0) or 0.0)),
                "Ast_bot": float(candidate_b.get("_seed_ast_bot", candidate_b.get("Ast_bot", 0.0)) or candidate_b.get("Ast_bot", 0.0) or 0.0),
            },
        )
        return (
            (0 if metrics_a.get("materially_shallower") else 1) <= (0 if metrics_b.get("materially_shallower") else 1)
            and depth_a <= depth_b
            and float(metrics_a.get("width_growth", 0.0) or 0.0) <= float(metrics_b.get("width_growth", 0.0) or 0.0)
            and float(metrics_a.get("reinforcement_growth", 0.0) or 0.0) <= float(metrics_b.get("reinforcement_growth", 0.0) or 0.0)
            and complexity_a <= complexity_b
            and util_a <= util_b
            and (
                (0 if metrics_a.get("materially_shallower") else 1) < (0 if metrics_b.get("materially_shallower") else 1)
                or depth_a < depth_b
                or float(metrics_a.get("width_growth", 0.0) or 0.0) < float(metrics_b.get("width_growth", 0.0) or 0.0)
                or float(metrics_a.get("reinforcement_growth", 0.0) or 0.0) < float(metrics_b.get("reinforcement_growth", 0.0) or 0.0)
                or complexity_a < complexity_b
                or util_a < util_b
            )
        )
    if strategy == "low_reo":
        rows_a = int(candidate_a.get("row_count", 0) or 0)
        rows_b = int(candidate_b.get("row_count", 0) or 0)
        bars_a = int(candidate_a.get("bar_count", 0) or 0)
        bars_b = int(candidate_b.get("bar_count", 0) or 0)
        return (
            complexity_a <= complexity_b
            and rows_a <= rows_b
            and bars_a <= bars_b
            and depth_a <= depth_b
            and util_a <= util_b
            and (
                complexity_a < complexity_b
                or rows_a < rows_b
                or bars_a < bars_b
                or depth_a < depth_b
                or util_a < util_b
            )
        )
    return (
        util_a <= util_b
        and depth_a <= depth_b
        and complexity_a <= complexity_b
        and (util_a < util_b or depth_a < depth_b or complexity_a < complexity_b)
    )


def utilisation_gap(candidate: dict, mode_config: dict) -> float:
    return _candidate_util_distance(candidate, mode_config)


def candidate_is_good_enough(
    candidate: dict,
    mode_config: dict,
    reference_candidate: dict | None = None,
) -> bool:
    if not candidate or not bool(candidate.get("is_compliant")) or not _candidate_is_practical(candidate, mode_config):
        return False
    strategy = str(mode_config.get("search_strategy", "balanced") or "balanced")
    if strategy == "shallow":
        return (
            _candidate_in_target_band(candidate, mode_config)
            or (reference_candidate is not None and is_materially_shallower(candidate, reference_candidate, mode_config))
        )
    if strategy == "low_reo":
        return (
            _candidate_in_target_band(candidate, mode_config)
            or (reference_candidate is not None and is_materially_simpler_reo(candidate, reference_candidate, mode_config))
        )
    return _candidate_in_target_band(candidate, mode_config)


def _allow_early_target_exit(mode_config: dict) -> bool:
    return str(mode_config.get("search_strategy", "balanced") or "balanced") != "balanced"


def is_meaningfully_better(new_result: dict, old_result: dict, mode_config: dict) -> bool:
    if not new_result or not old_result:
        return False
    strategy = str(mode_config.get("search_strategy", "balanced") or "balanced")
    min_score_improvement = float(mode_config.get("min_score_improvement", 0.25) or 0.25)
    min_util_improvement = float(mode_config.get("min_util_improvement", 0.01) or 0.01)
    score_gain = float(old_result.get("score", float("inf")) or float("inf")) - float(new_result.get("score", float("inf")) or float("inf"))
    util_gain = utilisation_gap(old_result, mode_config) - utilisation_gap(new_result, mode_config)
    depth_gain = float(old_result.get("depth", 0.0) or 0.0) - float(new_result.get("depth", 0.0) or 0.0)
    reo_gain = float(old_result.get("reo_complexity", compute_reo_complexity(old_result)) or 0.0) - float(
        new_result.get("reo_complexity", compute_reo_complexity(new_result)) or 0.0
    )
    if strategy == "shallow":
        return (
            depth_gain >= float(mode_config.get("material_depth_delta_mm", 25.0) or 25.0)
            or score_gain > min_score_improvement
            or util_gain > min_util_improvement
        )
    if strategy == "low_reo":
        return (
            reo_gain >= float(mode_config.get("material_reo_complexity_delta", 4.0) or 4.0)
            or score_gain > min_score_improvement
            or util_gain > min_util_improvement
        )
    return (
        score_gain > min_score_improvement
        or util_gain > min_util_improvement
        or depth_gain >= float(mode_config.get("material_depth_delta_mm", 25.0) or 25.0)
        or reo_gain >= float(mode_config.get("material_reo_complexity_delta", 4.0) or 4.0)
    )


def _ensure_candidate_score(candidate: dict | None, mode_config: dict, seed_candidate: dict) -> dict | None:
    if not candidate:
        return candidate
    candidate["score"] = _score_auto_design_candidate(candidate, mode_config, seed_candidate)
    return candidate


def candidate_materially_worsens(
    new_candidate: dict,
    old_candidate: dict,
    mode_config: dict,
    *,
    phase: str,
) -> bool:
    if not new_candidate or not old_candidate:
        return False
    old_compliant = bool(old_candidate.get("is_compliant"))
    new_compliant = bool(new_candidate.get("is_compliant"))
    if _candidate_ductility_governs(old_candidate):
        old_du = _candidate_ductility_util(old_candidate)
        new_du = _candidate_ductility_util(new_candidate)
        old_ast = float(old_candidate.get("Ast_bot", 0.0) or 0.0)
        new_ast = float(new_candidate.get("Ast_bot", 0.0) or 0.0)
        if (
            new_ast > old_ast + 1e-6
            and old_du is not None
            and (new_du is None or float(new_du) >= float(old_du) - 0.01)
        ):
            _agent_debug_log(
                "Rejected worse auto-design candidate",
                {
                    "phase": phase,
                    "rejection_reason": "heavier_bottom_steel_without_ductility_gain",
                    "old_Ast_bot": old_ast,
                    "new_Ast_bot": new_ast,
                    "old_ductility_util": old_du,
                    "new_ductility_util": new_du,
                },
                location="inputs_page.py:candidate_materially_worsens",
                hypothesis_id="H31_DUCTILITY",
            )
            return True
    if old_compliant and new_compliant and _reject_heavier_steel_lower_demand_util(old_candidate, new_candidate):
        _agent_debug_log(
            "Rejected worse auto-design candidate",
            {
                "phase": phase,
                "rejection_reason": "heavier_bottom_steel_lower_Mu_star_over_phiMu",
                "old_Ast_bot": float(old_candidate.get("Ast_bot", 0.0) or 0.0),
                "new_Ast_bot": float(new_candidate.get("Ast_bot", 0.0) or 0.0),
                "old_bending_demand_util": _candidate_bending_demand_util(old_candidate),
                "new_bending_demand_util": _candidate_bending_demand_util(new_candidate),
            },
            location="inputs_page.py:candidate_materially_worsens",
            hypothesis_id="H31_STEEL",
        )
        return True
    old_failed = set(_failed_check_labels(old_candidate))
    new_failed = set(_failed_check_labels(new_candidate))
    old_worst = float(old_candidate.get("worst_util", 0.0) or 0.0)
    new_worst = float(new_candidate.get("worst_util", 0.0) or 0.0)
    old_gap = float(utilisation_gap(old_candidate, mode_config))
    new_gap = float(utilisation_gap(new_candidate, mode_config))
    strategy = str(mode_config.get("search_strategy", "balanced") or "balanced")
    old_depth = float(old_candidate.get("depth", 0.0) or 0.0)
    new_depth = float(new_candidate.get("depth", 0.0) or 0.0)
    old_complexity = float(old_candidate.get("reo_complexity", compute_reo_complexity(old_candidate)) or 0.0)
    new_complexity = float(new_candidate.get("reo_complexity", compute_reo_complexity(new_candidate)) or 0.0)

    worsens = False
    if not old_compliant:
        if not new_compliant:
            if len(new_failed) > len(old_failed) or new_worst > old_worst + 0.01:
                worsens = True
        if old_compliant and not new_compliant:
            worsens = True
    if old_compliant and new_compliant and new_gap > old_gap + 0.01:
        worsens = True
    if old_compliant and not new_compliant:
        worsens = True
    if old_compliant and new_compliant and strategy == "low_reo":
        if new_complexity > old_complexity + 0.5 and new_gap >= old_gap - 0.01:
            worsens = True
    if old_compliant and new_compliant and strategy == "shallow":
        if new_depth > old_depth + 10.0 and new_gap >= old_gap - 0.01:
            worsens = True

    if worsens:
        _agent_debug_log(
            "Rejected worse auto-design candidate",
            {
                "phase": phase,
                "old_util": old_worst,
                "new_util": new_worst,
                "old_fail_count": int(old_candidate.get("fail_count", 0) or 0),
                "new_fail_count": int(new_candidate.get("fail_count", 0) or 0),
                "old_gap": old_gap,
                "new_gap": new_gap,
            },
            location="inputs_page.py:candidate_materially_worsens",
            hypothesis_id="H31",
        )
    return worsens


def select_final_candidate(results: list[dict], mode_config: dict, baseline_candidate: dict | None = None) -> dict | None:
    filtered = []
    for result in results:
        if not result:
            continue
        if baseline_candidate is not None and candidate_materially_worsens(result, baseline_candidate, mode_config, phase="final"):
            continue
        filtered.append(result)
    if not filtered:
        return baseline_candidate
    strategy = str(mode_config.get("search_strategy", "balanced") or "balanced")
    in_zone = [
        result for result in filtered
        if bool(result.get("is_compliant")) and candidate_is_good_enough(result, mode_config)
    ]
    if in_zone:
        if strategy == "shallow" and baseline_candidate is not None:
            return min(
                in_zone,
                key=lambda item: (
                    _shallower_beam_selection_key(item, baseline_candidate, mode_config),
                    _candidate_sort_key_for_mode(item, mode_config),
                    item.get("score", float("inf")),
                ),
            )
        return min(in_zone, key=lambda item: (_candidate_sort_key_for_mode(item, mode_config), item.get("score", float("inf"))))
    compliant = [result for result in filtered if bool(result.get("is_compliant"))]
    if compliant:
        if strategy == "shallow" and baseline_candidate is not None:
            return min(
                compliant,
                key=lambda item: (
                    _shallower_beam_selection_key(item, baseline_candidate, mode_config),
                    utilisation_gap(item, mode_config),
                    _candidate_sort_key_for_mode(item, mode_config),
                    item.get("score", float("inf")),
                ),
            )
        return min(compliant, key=lambda item: (utilisation_gap(item, mode_config), _candidate_sort_key_for_mode(item, mode_config), item.get("score", float("inf"))))
    return min(filtered, key=lambda item: (int(item.get("fail_count", 0) or 0), float(item.get("worst_util", float("inf")) or float("inf")), _candidate_sort_key_for_mode(item, mode_config), item.get("score", float("inf"))))


def select_best_improving_candidate(current_result: dict, candidate_results: list[dict], mode_config: dict) -> dict | None:
    return select_best_next_hop_candidate(current_result, candidate_results, mode_config, phase="generic")


def select_best_next_hop_candidate(
    current_result: dict,
    candidate_results: list[dict],
    mode_config: dict,
    *,
    phase: str,
) -> dict | None:
    viable: list[dict] = []
    for result in candidate_results:
        if not result:
            continue
        if candidate_materially_worsens(result, current_result, mode_config, phase=phase):
            continue
        viable.append(result)
    if not viable:
        return None
    if phase == "solve_to_pass" and not bool(current_result.get("is_compliant")):
        return min(
            viable,
            key=lambda item: (
                0 if bool(item.get("is_compliant")) else 1,
                int(item.get("fail_count", 0) or 0),
                float(item.get("worst_util", 999.0) or 999.0),
                _candidate_sort_key_for_mode(item, mode_config),
                float(item.get("score", 0.0) or 0.0),
            ),
        )
    return min(
        viable,
        key=lambda item: (_candidate_sort_key_for_mode(item, mode_config), float(item.get("score", 0.0) or 0.0)),
    )


def select_best_compliant_refinement_candidate(
    results: list[dict],
    mode_config: dict,
    baseline_candidate: dict | None = None,
) -> dict | None:
    compliant = [
        result for result in results
        if result
        and bool(result.get("is_compliant"))
        and not (baseline_candidate is not None and candidate_materially_worsens(result, baseline_candidate, mode_config, phase="refinement"))
    ]
    if not compliant:
        return baseline_candidate
    in_zone = [result for result in compliant if utilisation_gap(result, mode_config) <= 0.0]
    if in_zone:
        return min(in_zone, key=lambda result: float(result.get("score", 0.0) or 0.0))
    return min(
        compliant,
        key=lambda result: (
            float(utilisation_gap(result, mode_config)),
            float(result.get("score", 0.0) or 0.0),
        ),
    )


def run_compliant_refinement_phase(
    compliant_candidate: dict,
    mode_config: dict,
    *,
    max_refinement_hops: int,
) -> dict:
    accepted_candidate = compliant_candidate
    best = compliant_candidate
    stop_reason = "refinement_no_better_compliant_candidate"
    steps: list[str] = []
    hop_count = 0
    eval_cache: dict = {}
    metrics = {
        "_reference_overview": compliant_candidate.get("overview"),
        "generated_count": 0,
        "unique_eval_count": 0,
        "cache_hits": 0,
        "fast_eval_total_ms": 0.0,
        "candidate_generation_ms": 0.0,
        "pruning_total_ms": 0.0,
        "solve_reo_total_ms": 0.0,
        "kept_count": 0,
        "cap_hit": False,
    }

    def _log_refinement_stop(proposed_stop_reason: str, accepted: dict | None) -> None:
        efficiency_state = None
        accepted_state = dict((accepted or {}).get("state") or {})
        if accepted_state:
            try:
                efficiency_state = compute_efficiency_tightening_state(_guidance_state_snapshot(accepted_state))
            except Exception:
                efficiency_state = None
        mode_tightening = ((efficiency_state or {}).get("mode_tightening") or {})
        _agent_debug_log(
            "Refinement stop check",
            {
                "stop_reason_candidate": proposed_stop_reason,
                "accepted_worst_util": None if accepted is None else accepted.get("worst_util"),
                "accepted_is_compliant": None if accepted is None else accepted.get("is_compliant"),
                "target_min": mode_config.get("target_util_min"),
                "target_max": mode_config.get("target_util_max"),
                "generated_count": metrics.get("generated_count"),
                "kept_count": metrics.get("kept_count"),
                "unique_eval_count": metrics.get("unique_eval_count"),
                "mode_tightening_optimisation_score": mode_tightening.get("optimisation_score"),
                "mode_tightening_label": mode_tightening.get("label"),
            },
            location="inputs_page.py:refinement_stop_check",
            hypothesis_id="H101",
        )

    context = _build_auto_design_context(
        compliant_candidate["state"],
        mode_config,
        reference_overview=compliant_candidate.get("overview"),
    )
    for hop in range(max(0, int(max_refinement_hops))):
        hop_count = hop + 1
        if _candidate_in_target_zone(accepted_candidate, mode_config):
            stop_reason = "refinement_reached_target_zone"
            _log_refinement_stop(stop_reason, accepted_candidate)
            break
        candidate_states = generate_compliant_refinement_candidates(accepted_candidate, mode_config, context)
        if not candidate_states and int(metrics.get("generated_count", 0) or 0) == 0:
            _agent_debug_log(
                "No candidates generated → forcing refinement seed",
                {},
                location="inputs_page.py:refinement_guard",
                hypothesis_id="H202",
            )
            candidate_states = generate_local_improvement_candidates(
                accepted_candidate,
                mode_config,
                context,
                search_band=1,
                is_first_hop=(hop == 0),
            )
        if not candidate_states:
            stop_reason = "refinement_no_better_compliant_candidate"
            _log_refinement_stop(stop_reason, accepted_candidate)
            break
        candidates: list[dict] = []
        for candidate_state in candidate_states:
            candidate = _evaluate_candidate_fast(
                candidate_state,
                seed_state=compliant_candidate["state"],
                context=context,
                eval_cache=eval_cache,
                metrics=metrics,
                source="refinement",
                label="Refinement",
                action_type="auto_design",
            )
            if candidate is None or not bool(candidate.get("is_compliant")):
                continue
            _ensure_candidate_score(candidate, mode_config, compliant_candidate)
            candidates.append(candidate)
        candidates = _keep_top_candidates(candidates, mode_config, limit=AUTO_DESIGN_MAX_KEPT_RESULTS)
        next_best = select_best_compliant_refinement_candidate(candidates, mode_config, baseline_candidate=accepted_candidate)
        if next_best is None or _candidate_state_signature(next_best) == _candidate_state_signature(accepted_candidate):
            stop_reason = "refinement_no_better_compliant_candidate"
            _log_refinement_stop(stop_reason, accepted_candidate)
            break
        if not is_meaningfully_better(next_best, accepted_candidate, mode_config):
            stop_reason = "refinement_no_better_compliant_candidate"
            _log_refinement_stop(stop_reason, accepted_candidate)
            break
        steps.append(build_auto_design_step_summary(accepted_candidate, next_best, hop=hop_count, phase_label="Refine hop"))
        accepted_candidate = next_best
        best = select_best_compliant_refinement_candidate([best, accepted_candidate], mode_config, baseline_candidate=best) or best
        if _candidate_in_target_zone(accepted_candidate, mode_config):
            stop_reason = "refinement_reached_target_zone"
            _log_refinement_stop(stop_reason, accepted_candidate)
            break
    else:
        stop_reason = "refinement_hop_cap_hit"
        _log_refinement_stop(stop_reason, accepted_candidate)
    return {
        "candidate": best,
        "steps": steps,
        "stop_reason": stop_reason,
        "hop_count": hop_count,
        "metrics": metrics,
    }


def _generate_local_geometry_variants(current_candidate: dict, mode_config: dict, *, is_first_hop: bool = False) -> list[dict]:
    state = dict(current_candidate.get("state") or {})
    if _geometry_lock_enabled(state):
        return []
    strategy = str(mode_config.get("search_strategy", "balanced") or "balanced")
    _, _, current_width = _resolve_geometry_width_context(state)
    current_depth = float(current_candidate.get("depth", _float_from_state(state, "D", 600.0)) or _float_from_state(state, "D", 600.0))
    if _candidate_ductility_governs(current_candidate):
        width_steps = [current_width + 50.0]
        if is_first_hop:
            width_steps.append(current_width + 100.0)
        depth_steps = [current_depth + 50.0]
        if not is_first_hop:
            depth_steps.append(current_depth + 100.0)
        variants: dict[tuple, dict] = {}
        for width in width_steps:
            if width >= 250.0:
                candidate_state = _geometry_state_with_updates(state, width=width)
                variants[_make_auto_design_candidate_key(candidate_state)] = candidate_state
        for depth in depth_steps:
            if depth >= 350.0:
                candidate_state = _geometry_state_with_updates(state, depth=depth)
                variants[_make_auto_design_candidate_key(candidate_state)] = candidate_state
        return list(variants.values())
    depth_steps = [current_depth - 50.0, current_depth + 50.0]
    width_steps: list[float] = []
    if is_first_hop:
        if strategy == "shallow":
            depth_steps = [current_depth - 100.0, current_depth - 50.0, current_depth + 50.0]
        elif strategy == "low_reo":
            depth_steps = [current_depth + 50.0, current_depth + 100.0, current_depth - 50.0]
            width_steps = [current_width + 50.0, current_width + 100.0]
        else:
            depth_steps = [current_depth - 50.0, current_depth + 50.0, current_depth + 100.0]
            width_steps = [current_width - 50.0, current_width + 50.0]
    else:
        if strategy == "shallow":
            depth_steps = [current_depth - 50.0, current_depth + 50.0]
        elif strategy == "low_reo":
            depth_steps = [current_depth + 50.0, current_depth - 50.0]
            width_steps = [current_width + 50.0]
        else:
            width_steps = [current_width - 50.0, current_width + 50.0]
    variants: dict[tuple, dict] = {}
    for depth in depth_steps:
        if depth >= 350.0:
            candidate_state = _geometry_state_with_updates(state, depth=depth)
            variants[_make_auto_design_candidate_key(candidate_state)] = candidate_state
    for width in width_steps:
        if width >= 250.0:
            candidate_state = _geometry_state_with_updates(state, width=width)
            variants[_make_auto_design_candidate_key(candidate_state)] = candidate_state
    return list(variants.values())


def generate_local_improvement_candidates(
    current_candidate: dict,
    mode_config: dict,
    context: dict,
    *,
    search_band: int = 0,
    is_first_hop: bool = False,
) -> list[dict]:
    state = dict(current_candidate.get("state") or {})
    candidates: dict[tuple, dict] = {}
    raw_limit = AUTO_DESIGN_MAX_FIRST_HOP_RAW_CANDIDATES if is_first_hop else AUTO_DESIGN_MAX_LATER_HOP_RAW_CANDIDATES
    bottom_band = max(int(search_band), 1) if is_first_hop else int(search_band)
    for arrangement in _generate_local_bottom_arrangements(state, mode_config, band=bottom_band, context=context, limit=raw_limit):
        candidate_state = dict(state)
        candidate_state.update(_bottom_arrangement_to_shared_updates(arrangement))
        candidates[_make_auto_design_candidate_key(candidate_state)] = candidate_state
    disable_shear_strength_candidates = bool(context.get("disable_shear_strength_candidates"))
    if not disable_shear_strength_candidates:
        shear_bands = [int(search_band)]
        if is_first_hop:
            shear_bands = sorted(set([0, 1]))
        for band in shear_bands:
            for shear_state in _generate_local_shear_states(state, mode_config, band=band, limit=raw_limit):
                candidates[_make_auto_design_candidate_key(shear_state)] = shear_state
    for geometry_state in _generate_local_geometry_variants(current_candidate, mode_config, is_first_hop=is_first_hop):
        candidates[_make_auto_design_candidate_key(geometry_state)] = geometry_state
    candidates.pop(_make_auto_design_candidate_key(state), None)
    return list(candidates.values())


def generate_cleanup_candidates(
    current_candidate: dict,
    mode_config: dict,
    context: dict,
) -> list[dict]:
    state = dict(current_candidate.get("state") or {})
    candidates: dict[tuple, dict] = {}
    for candidate_state in generate_less_bottom_reo_variants(current_candidate, mode_config, context):
        candidates[_make_auto_design_candidate_key(candidate_state)] = candidate_state
    for candidate_state in generate_simpler_layout_variants(current_candidate, mode_config, context):
        candidates[_make_auto_design_candidate_key(candidate_state)] = candidate_state
    if _shear_cleanup_possible(state) and not bool(context.get("disable_shear_cleanup_candidates")):
        for candidate_state in generate_less_shear_reo_variants(current_candidate, mode_config):
            candidates[_make_auto_design_candidate_key(candidate_state)] = candidate_state
    candidates.pop(_make_auto_design_candidate_key(state), None)
    return list(candidates.values())


def generate_smaller_geometry_variants(current_candidate: dict, mode_config: dict) -> list[dict]:
    state = dict(current_candidate.get("state") or {})
    if _geometry_lock_enabled(state):
        return []
    strategy = str(mode_config.get("search_strategy", "balanced") or "balanced")
    current_depth = float(current_candidate.get("depth", _float_from_state(state, "D", 600.0)) or _float_from_state(state, "D", 600.0))
    width_key, _, current_width = _resolve_geometry_width_context(state)
    variants: dict[tuple, dict] = {}
    for depth in [current_depth - 50.0, current_depth - 100.0]:
        if depth >= 350.0:
            candidate_state = _geometry_state_with_updates(state, depth=depth)
            variants[_make_auto_design_candidate_key(candidate_state)] = candidate_state
    if strategy != "shallow":
        narrower = current_width - 50.0
        if narrower >= 250.0:
            candidate_state = _geometry_state_with_updates(state, width=narrower)
            variants[_make_auto_design_candidate_key(candidate_state)] = candidate_state
        if width_key != "b":
            current_rectified = _geometry_state_with_updates(state, width=current_width)
            variants[_make_auto_design_candidate_key(current_rectified)] = current_rectified
    return list(variants.values())


def generate_less_bottom_reo_variants(current_candidate: dict, mode_config: dict, context: dict) -> list[dict]:
    state = dict(current_candidate.get("state") or {})
    current_ast = float(current_candidate.get("Ast_bot", 0.0) or 0.0)
    current_complexity = float(current_candidate.get("reo_complexity", compute_reo_complexity(current_candidate)) or 0.0)
    variants: dict[tuple, dict] = {}
    for arrangement in _generate_local_bottom_arrangements(state, mode_config, band=0, context=context):
        candidate_state = dict(state)
        updates = _bottom_arrangement_to_shared_updates(arrangement)
        candidate_state.update(updates)
        preview_bottom = _effective_bottom_design_state(candidate_state, _candidate_bottom_updates(candidate_state))
        preview_candidate = {
            "state": candidate_state,
            "Ast_bot": float(preview_bottom.get("Ast_bot", 0.0) or 0.0),
            "row_count": _bottom_row_count_from_state(candidate_state),
            "bar_count": _bottom_bar_count_from_state(candidate_state, preview_bottom),
            "reo_congestion_index": _reo_congestion_index(candidate_state, preview_bottom),
        }
        preview_complexity = float(compute_reo_complexity(preview_candidate) or 0.0)
        if (
            float(preview_bottom.get("Ast_bot", 0.0) or 0.0) < current_ast - 1e-6
            or preview_complexity < current_complexity - 1e-6
        ):
            variants[_make_auto_design_candidate_key(candidate_state)] = candidate_state
    return list(variants.values())


def generate_less_shear_reo_variants(current_candidate: dict, mode_config: dict) -> list[dict]:
    state = dict(current_candidate.get("state") or {})
    if not _shear_cleanup_possible(state):
        return []
    current_spacing = _int_from_state(state, "s_lig", 200)
    current_legs = _int_from_state(state, "lig_legs", 2)
    current_dia = _int_from_state(state, "lig_d", 10)
    max_spacing = float(max(REO_SPACINGS) if REO_SPACINGS else 300.0)
    spacing_values = [value for value in REO_SPACINGS if value > current_spacing][:2]
    if max_spacing > current_spacing + 1e-9:
        spacing_values.append(max_spacing)
    spacing_values = sorted(set(float(value) for value in spacing_values))
    leg_values = sorted(set([0, max(0, current_legs - 2), current_legs]))
    dia_values = sorted(set(([0] if current_dia > 0 else []) + ([value for value in REO_BAR_DIAS if value <= current_dia][-2:] or [current_dia])))
    variants: dict[tuple, dict] = {}
    for dia in dia_values:
        for legs in leg_values:
            for spacing in spacing_values or [current_spacing]:
                resolved_dia = 0 if int(legs) <= 0 else int(dia)
                resolved_spacing = max_spacing if int(legs) <= 0 else float(spacing)
                if resolved_dia == current_dia and int(legs) == current_legs and resolved_spacing == current_spacing:
                    continue
                candidate_state = dict(state)
                candidate_state.update({
                    "lig_d": int(resolved_dia),
                    "lig_legs": int(legs),
                    "s_lig": float(resolved_spacing),
                })
                variants[_make_auto_design_candidate_key(candidate_state)] = candidate_state
    return list(variants.values())


def generate_simpler_layout_variants(current_candidate: dict, mode_config: dict, context: dict) -> list[dict]:
    state = dict(current_candidate.get("state") or {})
    current_rows = int(current_candidate.get("row_count", 0) or 0)
    current_bars = int(current_candidate.get("bar_count", 0) or 0)
    variants: dict[tuple, dict] = {}
    for arrangement in _generate_local_bottom_arrangements(state, mode_config, band=0, context=context):
        candidate_state = dict(state)
        candidate_state.update(_bottom_arrangement_to_shared_updates(arrangement))
        row_count = _bottom_row_count_from_state(candidate_state)
        bar_count = _bottom_bar_count_from_state(candidate_state, _effective_bottom_design_state(candidate_state, _candidate_bottom_updates(candidate_state)))
        if row_count < current_rows or bar_count < current_bars:
            variants[_make_auto_design_candidate_key(candidate_state)] = candidate_state
    return list(variants.values())


def generate_compliant_refinement_candidates(current_candidate: dict, mode_config: dict, context: dict) -> list[dict]:
    candidates: dict[tuple, dict] = {}
    for candidate_state in generate_smaller_geometry_variants(current_candidate, mode_config):
        candidates[_make_auto_design_candidate_key(candidate_state)] = candidate_state
    for candidate_state in generate_less_bottom_reo_variants(current_candidate, mode_config, context):
        candidates[_make_auto_design_candidate_key(candidate_state)] = candidate_state
    if _shear_cleanup_possible(dict(current_candidate.get("state") or {})) and not bool(context.get("disable_shear_cleanup_candidates")):
        for candidate_state in generate_less_shear_reo_variants(current_candidate, mode_config):
            candidates[_make_auto_design_candidate_key(candidate_state)] = candidate_state
    for candidate_state in generate_simpler_layout_variants(current_candidate, mode_config, context):
        candidates[_make_auto_design_candidate_key(candidate_state)] = candidate_state
    candidates.pop(_make_auto_design_candidate_key(current_candidate.get("state") or {}), None)
    return list(candidates.values())[:AUTO_DESIGN_MAX_LOCAL_CANDIDATES_PER_ITER]


def _keep_top_candidates(candidates: list[dict], mode_config: dict, *, limit: int) -> list[dict]:
    limit = min(max(int(limit), 1), AUTO_DESIGN_MAX_KEPT_RESULTS)
    deduped: dict[tuple, dict] = {}
    for candidate in candidates:
        if not candidate:
            continue
        candidate.setdefault("reo_complexity", compute_reo_complexity(candidate))
        key = _make_auto_design_candidate_key(candidate.get("state") or {})
        existing = deduped.get(key)
        if existing is None or _candidate_sort_key_for_mode(candidate, mode_config) < _candidate_sort_key_for_mode(existing, mode_config):
            deduped[key] = candidate
    ordered = sorted(deduped.values(), key=lambda item: _candidate_sort_key_for_mode(item, mode_config))
    strategy = str(mode_config.get("search_strategy", "balanced") or "balanced")
    if strategy == "shallow" and bool(st.session_state.get("_dev_mode")) and ordered:
        selected_candidate = ordered[0]
        selected_tier, selected_tier_label = _shallower_beam_candidate_tier(selected_candidate)
        def _baseline_for(item: dict) -> dict:
            return {
                "state": dict(item.get("state") or {}),
                "depth": float(item.get("_seed_depth", item.get("depth", 0.0)) or 0.0),
                "width": float(item.get("_seed_width", item.get("width", 0.0)) or 0.0),
                "Ast_bot": float(item.get("_seed_ast_bot", item.get("Ast_bot", 0.0)) or 0.0),
            }
        best_local_candidate = next(
            (item for item in ordered if _shallower_beam_candidate_tier(item)[0] == 0),
            None,
        )
        best_width_candidate = next(
            (
                item for item in ordered
                if bool(item.get("is_compliant")) and _shallower_beam_candidate_tier(item)[0] == 1
            ),
            None,
        )
        best_depth_candidate = next(
            (
                item for item in ordered
                if bool(item.get("is_compliant")) and _shallower_beam_candidate_tier(item)[0] in (2, 3)
            ),
            None,
        )
        selected_metrics = _shallower_beam_metrics(selected_candidate, _baseline_for(selected_candidate))
        if selected_tier >= 2 and best_width_candidate is not None:
            _agent_debug_log(
                "Depth selected before width in shallower_beam mode — verify ranking justification",
                {
                    "selected_candidate": _candidate_debug_summary(selected_candidate),
                    "selected_tier": selected_tier_label,
                    "best_width_candidate": _candidate_debug_summary(best_width_candidate),
                    "best_width_tier": _shallower_beam_candidate_tier(best_width_candidate)[1],
                    "selected_sort_key": _candidate_sort_key_for_mode(selected_candidate, mode_config),
                    "best_width_sort_key": _candidate_sort_key_for_mode(best_width_candidate, mode_config),
                },
                location="inputs_page.py:_keep_top_candidates",
                hypothesis_id="H_SHALLOW_WIDTH_FIRST",
            )
        if not bool(selected_metrics.get("materially_shallower")) and (
            float(selected_metrics.get("width_growth", 0.0) or 0.0) >= 100.0
            or float(selected_metrics.get("reinforcement_growth", 0.0) or 0.0) >= 150.0
        ):
            _agent_debug_log(
                "Selected candidate is not materially shallower — verify shallower_beam ranking",
                {
                    "selected_candidate": _candidate_debug_summary(selected_candidate),
                    "shallowness_metrics": selected_metrics,
                },
                location="inputs_page.py:_keep_top_candidates",
                hypothesis_id="H_TRUE_SHALLOW",
            )
        def _shallow_debug_payload(item: dict | None) -> dict | None:
            if not item:
                return None
            shallow_metrics = _shallower_beam_metrics(item, _baseline_for(item))
            shear_pack = (((item.get("overview") or {}).get("packs") or {}).get("shear") or {})
            bending_pack = (((item.get("overview") or {}).get("packs") or {}).get("bending") or {})
            return {
                "label": item.get("label"),
                "b": item.get("width"),
                "D": item.get("depth"),
                "bottom_reo_label": _bottom_reo_state_label(dict(item.get("state") or {})),
                "Ast_bot": item.get("Ast_bot"),
                "phiMu": bending_pack.get("summary_phiMu_kNm"),
                "Mu_star": bending_pack.get("summary_Mu_star_kNm"),
                "bending_util": ((item.get("overview") or {}).get("utils") or {}).get("bending"),
                "phiVu": shear_pack.get("summary_phiVu_kN"),
                "Veq": shear_pack.get("summary_Veq_kN"),
                "shear_util": ((item.get("overview") or {}).get("utils") or {}).get("shear"),
                "shallowness_score": ((item.get("_score_components") or {}).get("shallowness_score")),
                "width_growth_penalty": ((item.get("_score_components") or {}).get("width_growth_penalty")),
                "reinforcement_growth_penalty": ((item.get("_score_components") or {}).get("reinforcement_growth_penalty")),
                "total_score": item.get("score"),
                "reason": "selected" if item is selected_candidate else "comparison candidate",
                "shallowness_metrics": shallow_metrics,
            }
        _agent_debug_log(
            "Shallower beam candidate comparison",
            {
                "best_bottom_reo_local_candidate": _shallow_debug_payload(best_local_candidate),
                "best_width_reo_candidate": _shallow_debug_payload(best_width_candidate),
                "best_depth_candidate": _shallow_debug_payload(best_depth_candidate),
                "final_selected_candidate": _shallow_debug_payload(selected_candidate),
            },
            location="inputs_page.py:_keep_top_candidates",
            hypothesis_id="H_SHALLOW_COMPARE",
        )
    kept: list[dict] = []
    candidate_audit: list[dict] = []
    for candidate in ordered:
        decision = "kept"
        if any(_candidate_dominates_for_mode(existing, candidate, mode_config) for existing in kept):
            decision = "discarded_dominated"
            if len(candidate_audit) < 8:
                candidate_audit.append({
                    **(_candidate_debug_summary(candidate) or {}),
                    "decision": decision,
                })
            continue
        if len(kept) >= limit:
            decision = "discarded_limit"
            if len(candidate_audit) < 8:
                candidate_audit.append({
                    **(_candidate_debug_summary(candidate) or {}),
                    "decision": decision,
                })
            continue
        kept.append(candidate)
        if len(candidate_audit) < 8:
            candidate_audit.append({
                **(_candidate_debug_summary(candidate) or {}),
                "decision": decision,
            })
    if bool(st.session_state.get("_dev_mode")) and candidate_audit:
        _agent_debug_log(
            "Ranked kept auto-design candidates",
            {
                "mode": str(mode_config.get("label") or ""),
                "limit": int(limit),
                "ranked_candidates": candidate_audit,
            },
            location="inputs_page.py:_keep_top_candidates",
            hypothesis_id="H304",
        )
        if any(bool(candidate.get("_ductility_priority")) for candidate in ordered):
            _agent_debug_log(
                "Ranked ductility candidates",
                {
                    "mode": str(mode_config.get("label") or ""),
                    "top_candidates": candidate_audit,
                },
                location="inputs_page.py:_keep_top_candidates:ductility",
                hypothesis_id="H304_DUCTILITY",
            )
    return kept


def _make_auto_design_candidate_key(state: dict) -> tuple:
    actions = _resolve_design_actions_from_state(state)
    tracked_keys = (
        "sec_shape",
        "b",
        "bw",
        "tw",
        "D",
        "bf",
        "tf",
        "bf_bot",
        "tf_bot",
        "fc",
        "fsy",
        "Ec",
        "Es",
        "phi_bend",
        "phi_shear",
        "cover_top",
        "cover_bot",
        "cover_side",
        "rowgap_top",
        "rowgap_bot",
        "design_optimisation_goal",
        "optimisation_lock_geometry",
        "Ast_top",
        "Tu_star",
        "P_star",
        "lig_d",
        "lig_legs",
        "s_lig",
        "bot_row_count",
        "bot1_layout_mode",
        "bot1_count",
        "db_bot_1",
        "bot2_layout_mode",
        "bot2_count",
        "db_bot_2",
        "bot_row_1_mode",
        "bot_row_1_bars",
        "bot_row_1_spacing",
        "bot_row_1_dia",
        "bot_row_2_mode",
        "bot_row_2_bars",
        "bot_row_2_spacing",
        "bot_row_2_dia",
    )
    key_parts = [(key, str(state.get(key))) for key in tracked_keys]
    key_parts.extend([
        ("resolved_Mu", str(actions.get("Mu"))),
        ("resolved_Vu", str(actions.get("Vu"))),
        ("resolved_Nu", str(actions.get("Nu"))),
        ("resolved_SLS_M", str(actions.get("SLS_M"))),
        ("resolved_SLS_V", str(actions.get("SLS_V"))),
        ("resolved_source", str(actions.get("source"))),
    ])
    return tuple(key_parts)


def _candidate_state_to_shared_updates(seed_state: dict, candidate_state: dict) -> dict:
    tracked_keys = (
        "b",
        "bw",
        "tw",
        "D",
        "fc",
        "lig_d",
        "lig_legs",
        "s_lig",
        "bot_row_count",
        "bot1_layout_mode",
        "bot1_count",
        "db_bot_1",
        "bot2_layout_mode",
        "bot2_count",
        "db_bot_2",
        "bot_row_1_mode",
        "bot_row_1_bars",
        "bot_row_1_spacing",
        "bot_row_1_dia",
        "bot_row_2_mode",
        "bot_row_2_bars",
        "bot_row_2_spacing",
        "bot_row_2_dia",
    )
    updates: dict[str, float | int | str] = {}
    for key in tracked_keys:
        if seed_state.get(key) != candidate_state.get(key):
            updates[key] = candidate_state.get(key)
    return updates


def _build_auto_design_context(seed_state: dict, mode_config: dict, reference_overview: dict | None = None) -> dict:
    seed_overview = reference_overview or {}
    actions = _resolve_design_actions_from_state(seed_state)
    resolved_seed_state = _state_with_resolved_design_actions(seed_state, actions)
    disable_shear_strength_candidates = bool(seed_overview) and not _shear_change_is_relevant(seed_overview, actions)
    disable_shear_cleanup_candidates = False
    return {
        "seed_state": dict(resolved_seed_state),
        "mode_config": dict(mode_config),
        "mode_signature": str(mode_config.get("search_strategy", "balanced") or "balanced"),
        "actions": dict(actions),
        "actions_signature": tuple(actions.get("signature", ())),
        "seed_overview": seed_overview,
        "ductility_priority": _ductility_governs_overview(seed_overview),
        "geometry_locked": _geometry_lock_enabled(seed_state),
        "disable_shear_strength_candidates": disable_shear_strength_candidates,
        "disable_shear_cleanup_candidates": disable_shear_cleanup_candidates,
        "seen_candidate_keys": set(),
        "layout_fit_cache": {},
    }


def evaluate_candidate_fast(candidate_state: dict, context: dict) -> dict | None:
    seed_overview = (
        context.get("reference_overview")
        or context.get("seed_overview")
        or {"statuses": {}, "utils": {}, "packs": {}}
    )
    eval_state = _state_with_resolved_auto_design_actions(candidate_state, context.get("actions"))
    bottom_updates = _candidate_bottom_updates(eval_state)
    shear_updates = _candidate_shear_updates(eval_state)
    crack = _evaluate_crack_with_state(eval_state, bottom_updates=bottom_updates)
    deflection = _evaluate_deflection_with_state(eval_state, bottom_updates=bottom_updates)
    bending = _evaluate_bending_with_bottom_state(eval_state, bottom_updates)
    shear = _evaluate_shear_with_state(
        eval_state,
        bottom_updates=bottom_updates,
        shear_updates=shear_updates,
    )

    flexural_util = None
    ductility_util = None
    min_steel_util = None
    bending_util = None
    bending_status = "—"
    if bending:
        flexural_util = float(bending.get("Mu_util", float("inf")))
        try:
            ductility_util = float(bending.get("ku", 0.0) or 0.0) / 0.36 if bending.get("ku") is not None else None
        except Exception:
            ductility_util = None
        try:
            as_min = float(bending.get("As_min", 0.0) or 0.0)
            ast = float(bending.get("Ast_bot", 0.0) or 0.0)
            if ast > 0.0 and as_min > 0.0:
                min_steel_util = as_min / ast
        except Exception:
            min_steel_util = None
        bending_util = flexural_util
        if bending_util is not None and math.isnan(bending_util):
            bending_util = None
        governs = [
            u
            for u in (flexural_util, ductility_util, min_steel_util)
            if u is not None and not math.isnan(u)
        ]
        if governs:
            if any(u > 1.0 for u in governs):
                bending_status = "FAIL"
            elif any(u >= 0.95 for u in governs):
                bending_status = "NEAR LIMIT"
            else:
                bending_status = "PASS"
        else:
            bending_status = "—"

    shear_util = None
    shear_status = "—"
    if shear:
        shear_candidates = []
        for value in (shear.get("util"), shear.get("web_util")):
            try:
                resolved = float(value)
            except Exception:
                continue
            if not math.isnan(resolved):
                shear_candidates.append(resolved)
        shear_util = max(shear_candidates, default=None)
        shear_status = _status_from_candidate_util(shear_util)

    statuses = {
        "bending": bending_status,
        "shear": shear_status,
        "crack": _status_from_candidate_util(float(crack.get("util", 0.0) or 0.0)) if crack is not None else str(seed_overview.get("statuses", {}).get("crack", "PASS") or "PASS"),
        "deflection": str(deflection.get("status") or "PASS") if deflection is not None else str(seed_overview.get("statuses", {}).get("deflection", "PASS") or "PASS"),
    }
    utils = {
        "bending": bending_util,
        "shear": shear_util,
        "crack": float(crack.get("util", 0.0) or 0.0) if crack is not None else seed_overview.get("utils", {}).get("crack"),
        "deflection": deflection.get("util") if deflection is not None else seed_overview.get("utils", {}).get("deflection"),
    }
    tracked_statuses = [status for status in statuses.values() if status not in ("—", "")]
    bend_pack: dict = {}
    if bending:
        phi_cap = float(bending.get("phi_Mu_cap", 0.0) or 0.0)
        mu_star = float(_uls_action_from_state(eval_state, "M"))
        dem_util = (mu_star / phi_cap) if phi_cap > 1e-9 else None
        bend_pack = {
            "summary_phiMu_kNm": phi_cap,
            "summary_Mu_star_kNm": mu_star,
            "summary_util": dem_util,
            "rows": [],
        }
    overview = {
        "packs": {"bending": bend_pack} if bend_pack else {},
        "statuses": statuses,
        "utils": utils,
        "any_fail": any(status == "FAIL" for status in tracked_statuses),
        "any_warn": any(status == "NEAR LIMIT" for status in tracked_statuses),
        "all_key_pass": bool(tracked_statuses) and all(status == "PASS" for status in tracked_statuses),
        "worst_util": max((util for util in utils.values() if util is not None), default=0.0),
    }
    bottom_state = _effective_bottom_design_state(eval_state, bottom_updates)
    width = _design_width_value(eval_state)
    depth = _float_from_state(eval_state, "D", 600.0)
    shear_density = (
        _int_from_state(eval_state, "lig_legs", 0)
        * max(_int_from_state(eval_state, "lig_d", 0), 1) ** 2
    ) / max(_float_from_state(eval_state, "s_lig", 200.0), 1.0)
    fail_count = sum(1 for status in overview["statuses"].values() if status == "FAIL")
    return {
        "source": "fast_eval",
        "label": "Fast Eval",
        "action_type": None,
        "updates": {},
        "state": dict(candidate_state),
        "overview": overview,
        "bottom_state": bottom_state,
        "width": float(width),
        "depth": float(depth),
        "Ast_bot": float(bottom_state.get("Ast_bot", 0.0) or 0.0),
        "Ast_top": _float_from_state(eval_state, "Ast_top", 0.0),
        "bar_count": _bottom_bar_count_from_state(eval_state, bottom_state),
        "row_count": _bottom_row_count_from_state(eval_state),
        "reo_congestion_index": _reo_congestion_index(eval_state, bottom_state),
        "shear_density": float(shear_density),
        "bending_components": {
            "flexural_util": flexural_util if bending else None,
            "ductility_util": ductility_util if bending else None,
            "min_steel_util": min_steel_util if bending else None,
        },
        "is_compliant": bool(overview["all_key_pass"]),
        "worst_util": float(overview["worst_util"] or 0.0),
        "fail_count": fail_count,
    }


def _evaluate_candidate_fast(
    candidate_state: dict,
    *,
    seed_state: dict,
    context: dict,
    eval_cache: dict,
    metrics: dict,
    source: str,
    label: str | None = None,
    action_type: str | None = None,
) -> dict | None:
    metrics["generated_count"] = int(metrics.get("generated_count", 0)) + 1
    key = _make_auto_design_candidate_key(candidate_state)
    context.setdefault("seen_candidate_keys", set()).add(key)
    cached = eval_cache.get(key)
    if cached is None:
        if int(metrics.get("unique_eval_count", 0) or 0) >= AUTO_DESIGN_MAX_TOTAL_UNIQUE_EVALS:
            metrics["cap_hit"] = True
            return None
        started_at = time.perf_counter()
        metrics["unique_eval_count"] = int(metrics.get("unique_eval_count", 0)) + 1
        fast_ctx = dict(context)
        ref = metrics.get("_reference_overview")
        if ref is not None:
            fast_ctx["reference_overview"] = ref
        cached = evaluate_candidate_fast(candidate_state, fast_ctx)
        metrics["fast_eval_total_ms"] = float(metrics.get("fast_eval_total_ms", 0.0) or 0.0) + ((time.perf_counter() - started_at) * 1000.0)
        if cached is None:
            return None
        cached = dict(cached)
        cached["reo_complexity"] = compute_reo_complexity(cached)
        eval_cache[key] = cached
    else:
        metrics["cache_hits"] = int(metrics.get("cache_hits", 0)) + 1
    candidate = dict(cached)
    candidate["source"] = source
    candidate["label"] = label or candidate.get("label") or source.replace("_", " ").title()
    candidate["action_type"] = action_type
    candidate["state"] = dict(candidate_state)
    candidate["updates"] = _candidate_state_to_shared_updates(seed_state, candidate_state)
    candidate["_seed_width"] = float(_design_width_value(seed_state) or 0.0)
    candidate["_seed_depth"] = float(_float_from_state(seed_state, "D", 0.0) or 0.0)
    candidate["_seed_ast_bot"] = float((_effective_bottom_design_state(seed_state) or {}).get("Ast_bot", 0.0) or 0.0)
    candidate["reo_complexity"] = float(candidate.get("reo_complexity", compute_reo_complexity(candidate)) or 0.0)
    return candidate


def _option_window(options: list[int], current_value: int, *, down_steps: int, up_steps: int) -> list[int]:
    if not options:
        return []
    if current_value in options:
        index = options.index(current_value)
    else:
        index = min(range(len(options)), key=lambda idx: abs(options[idx] - current_value))
    start = max(0, index - down_steps)
    stop = min(len(options), index + up_steps + 1)
    return list(dict.fromkeys(options[start:stop]))


def _arrangement_fits_state(state: dict, arrangement: dict, *, layout_cache: dict | None = None) -> bool:
    from section_layout import compute_bar_layout_pure

    b = _design_width_value(state)
    cover_side = _float_from_state(state, "cover_side", 40.0)
    rowgap_bot = _float_from_state(state, "rowgap_bot", 60.0)
    dia = int(arrangement.get("db_bot_1", 0) or 0)
    count_1 = int(arrangement.get("bot1_count", 0) or 0)
    count_2 = int(arrangement.get("bot2_count", 0) or 0)
    if count_1 < 2 or dia <= 0:
        return False
    s_min = max(float(dia), 25.0)
    cache = layout_cache if isinstance(layout_cache, dict) else {}
    key_1 = (float(b), float(cover_side), float(rowgap_bot), int(dia), int(count_1))
    layout_1 = cache.get(key_1)
    if layout_1 is None:
        layout_1 = compute_bar_layout_pure(
            b=b,
            cover_side=cover_side,
            nb_or_s=float(count_1),
            db=float(dia),
            s_min=s_min,
            rowgap=rowgap_bot,
        )
        cache[key_1] = layout_1
    if not layout_1.get("fits_single_row", False):
        return False
    if count_2 > 0:
        if count_2 < 2:
            return False
        key_2 = (float(b), float(cover_side), float(rowgap_bot), int(dia), int(count_2))
        layout_2 = cache.get(key_2)
        if layout_2 is None:
            layout_2 = compute_bar_layout_pure(
                b=b,
                cover_side=cover_side,
                nb_or_s=float(count_2),
                db=float(dia),
                s_min=s_min,
                rowgap=rowgap_bot,
            )
            cache[key_2] = layout_2
        if not layout_2.get("fits_single_row", False):
            return False
    return True


def _generate_local_bottom_arrangements(state: dict, mode_config: dict, *, band: int, context: dict | None = None, limit: int | None = None) -> list[dict]:
    strategy = str(mode_config.get("search_strategy", "balanced") or "balanced")
    count_1 = _int_from_state(state, "bot1_count", 0)
    count_2 = _int_from_state(state, "bot2_count", 0)
    dia = _int_from_state(state, "db_bot_1", 20)
    total_bars = max(count_1 + count_2, 2)
    ductility_priority = bool((context or {}).get("ductility_priority"))

    if ductility_priority:
        dia_values = _option_window(REO_BAR_DIAS, dia, down_steps=1 + band, up_steps=0)
        count_1_values = list(range(max(2, count_1 - 2 - band), min(12, count_1 + 1) + 1))
        count_2_values = sorted(set([0, max(0, count_2 - 1), max(0, count_2)]))
        if count_2 <= 0:
            count_2_values = [0]
    elif strategy == "shallow":
        dia_values = _option_window(REO_BAR_DIAS, dia, down_steps=0, up_steps=1 + band)
        count_1_values = list(range(max(2, count_1), min(12, count_1 + 2 + band) + 1))
        count_2_values = [0] if count_2 <= 0 else list(range(max(0, count_2), min(12, count_2 + 1 + band) + 1))
        if count_2 <= 0:
            count_2_values.extend([2, 3 + band])
    elif strategy == "low_reo":
        dia_values = _option_window(REO_BAR_DIAS, dia, down_steps=0, up_steps=1 + band)
        count_1_values = list(range(max(2, count_1 - 2 - band), min(12, count_1 + 1) + 1))
        count_2_values = [0, max(0, count_2 - 1), count_2]
        count_1_values.extend([
            max(2, total_bars - 2 - band),
            max(2, total_bars - 1),
            total_bars,
        ])
    else:
        dia_values = _option_window(REO_BAR_DIAS, dia, down_steps=min(1, band), up_steps=1 + band)
        count_1_values = list(range(max(2, count_1 - 1 - band), min(12, count_1 + 2) + 1))
        count_2_values = [0] + list(range(max(0, count_2 - 1), min(12, count_2 + 1 + band) + 1))

    arrangements: dict[tuple[int, int, int], dict] = {}
    layout_cache = (context or {}).setdefault("layout_fit_cache", {}) if isinstance(context, dict) else {}
    for candidate_dia in dia_values:
        for candidate_count_1 in count_1_values:
            for candidate_count_2 in count_2_values:
                arrangement = _normalise_bottom_layer_order({
                    "bot1_layout_mode": "Count",
                    "bot1_count": int(candidate_count_1),
                    "db_bot_1": int(candidate_dia),
                    "bot2_layout_mode": "Count",
                    "bot2_count": int(max(candidate_count_2, 0)),
                    "db_bot_2": int(candidate_dia),
                })
                signature = (
                    int(arrangement.get("bot1_count", 0) or 0),
                    int(arrangement.get("bot2_count", 0) or 0),
                    int(arrangement.get("db_bot_1", 0) or 0),
                )
                if signature in arrangements:
                    continue
                if not _arrangement_fits_state(state, arrangement, layout_cache=layout_cache):
                    continue
                arrangements[signature] = arrangement

    def _arrangement_rank(item: dict) -> tuple:
        c1 = int(item.get("bot1_count", 0) or 0)
        c2 = int(item.get("bot2_count", 0) or 0)
        total = c1 + c2
        rows = 2 if c2 > 0 else 1
        candidate_dia = int(item.get("db_bot_1", 0) or 0)
        if ductility_priority:
            return (rows, total, candidate_dia)
        if strategy == "shallow":
            return (rows, -candidate_dia, -total)
        if strategy == "low_reo":
            return (rows, total, -candidate_dia)
        return (abs(total - total_bars), rows, abs(candidate_dia - dia))

    resolved_limit = AUTO_DESIGN_MAX_STAGE_CANDIDATES if limit is None else max(int(limit), 1)
    return sorted(arrangements.values(), key=_arrangement_rank)[:resolved_limit]


def _generate_local_shear_states(state: dict, mode_config: dict, *, band: int, limit: int | None = None) -> list[dict]:
    strategy = str(mode_config.get("search_strategy", "balanced") or "balanced")
    if not _shear_reinforcement_is_active(state):
        activation_state = _activation_shear_state(state)
        if _make_auto_design_candidate_key(activation_state) == _make_auto_design_candidate_key(state):
            return []
        return [activation_state]
    current_spacing = _int_from_state(state, "s_lig", 200)
    current_legs = _int_from_state(state, "lig_legs", 2)
    current_dia = _int_from_state(state, "lig_d", 10)
    spacing_values = _option_window(REO_SPACINGS, current_spacing, down_steps=0, up_steps=0)
    tighter_values = [value for value in REO_SPACINGS if value < current_spacing]
    spacing_values.extend(tighter_values[-(2 + band):])
    spacing_values = sorted(set(spacing_values), reverse=True)
    leg_values = sorted(set([current_legs, min(current_legs + 2, 6)]))
    if strategy == "shallow" and current_legs < 6:
        leg_values.append(min(current_legs + 4, 6))
    dia_values = _option_window([dia for dia in REO_BAR_DIAS if dia <= 16], current_dia, down_steps=0, up_steps=1 + band)

    states: dict[tuple, dict] = {}
    for dia in dia_values:
        for legs in leg_values:
            if int(legs) < 2:
                continue
            for spacing in spacing_values:
                candidate_state = dict(state)
                candidate_state.update({
                    "lig_d": int(dia),
                    "lig_legs": int(legs),
                    "s_lig": float(spacing),
                })
                states[_make_auto_design_candidate_key(candidate_state)] = candidate_state
    resolved_limit = AUTO_DESIGN_MAX_STAGE_CANDIDATES if limit is None else max(int(limit), 1)
    return list(states.values())[:resolved_limit]


def _geometry_state_with_updates(base_state: dict, *, depth: float | None = None, width: float | None = None) -> dict:
    candidate_state = dict(base_state)
    width_key, _, current_width = _resolve_geometry_width_context(base_state)
    if depth is not None:
        candidate_state["D"] = float(int(round(max(350.0, depth) / 10.0) * 10))
    if width is not None:
        resolved_width = float(int(round(max(250.0, width) / 10.0) * 10))
        candidate_state[width_key] = resolved_width
        if width_key != "b":
            candidate_state["b"] = resolved_width
    else:
        candidate_state[width_key] = float(current_width)
    return candidate_state


def generate_shallower_or_equal_depths(seed_candidate: dict) -> list[dict]:
    seed_state = dict(seed_candidate.get("state") or {})
    if _geometry_lock_enabled(seed_state):
        return []
    seed_depth = float(seed_candidate.get("depth", _float_from_state(seed_state, "D", 600.0)) or _float_from_state(seed_state, "D", 600.0))
    target_depths = [seed_depth - 100.0, seed_depth - 50.0, seed_depth]
    return [
        _geometry_state_with_updates(seed_state, depth=depth)
        for depth in target_depths
        if depth >= 350.0
    ]


def generate_slightly_deeper_depths(seed_candidate: dict) -> list[dict]:
    seed_state = dict(seed_candidate.get("state") or {})
    if _geometry_lock_enabled(seed_state):
        return []
    seed_depth = float(seed_candidate.get("depth", _float_from_state(seed_state, "D", 600.0)) or _float_from_state(seed_state, "D", 600.0))
    return [
        _geometry_state_with_updates(seed_state, depth=seed_depth + 50.0),
        _geometry_state_with_updates(seed_state, depth=seed_depth + 100.0),
    ]


def generate_shallow_geometry_options(
    seed_candidate: dict,
    *,
    include_deeper: bool,
    is_first_hop: bool,
) -> list[dict]:
    seed_state = dict(seed_candidate.get("state") or {})
    if _geometry_lock_enabled(seed_state):
        return []
    seed_depth = float(seed_candidate.get("depth", _float_from_state(seed_state, "D", 600.0)) or _float_from_state(seed_state, "D", 600.0))
    _, _, current_width = _resolve_geometry_width_context(seed_state)
    target_depths = [seed_depth - 100.0, seed_depth - 50.0, seed_depth]
    if include_deeper:
        target_depths.extend([seed_depth + 50.0, seed_depth + 100.0])
    width_steps = [current_width, current_width + 50.0]
    if is_first_hop:
        width_steps.append(current_width + 100.0)

    options: dict[tuple, dict] = {}
    for depth in target_depths:
        if depth < 350.0:
            continue
        for width in width_steps:
            candidate_state = _geometry_state_with_updates(seed_state, depth=depth, width=width)
            options[_make_auto_design_candidate_key(candidate_state)] = candidate_state
    return list(options.values())


def generate_same_or_larger_geometry_options(seed_candidate: dict) -> list[dict]:
    seed_state = dict(seed_candidate.get("state") or {})
    if _geometry_lock_enabled(seed_state):
        return []
    seed_depth = float(seed_candidate.get("depth", _float_from_state(seed_state, "D", 600.0)) or _float_from_state(seed_state, "D", 600.0))
    width_key, _, current_width = _resolve_geometry_width_context(seed_state)
    if _candidate_ductility_governs(seed_candidate):
        geometries = [
            _geometry_state_with_updates(seed_state, depth=seed_depth),
            _geometry_state_with_updates(seed_state, depth=seed_depth, width=current_width + 50.0),
            _geometry_state_with_updates(seed_state, depth=seed_depth, width=current_width + 100.0),
            _geometry_state_with_updates(seed_state, depth=seed_depth + 50.0),
            _geometry_state_with_updates(seed_state, depth=seed_depth + 50.0, width=current_width + 50.0),
            _geometry_state_with_updates(seed_state, depth=seed_depth + 100.0),
        ]
    else:
        geometries = [
            _geometry_state_with_updates(seed_state, depth=seed_depth),
            _geometry_state_with_updates(seed_state, depth=seed_depth + 50.0),
            _geometry_state_with_updates(seed_state, depth=seed_depth + 100.0),
            _geometry_state_with_updates(seed_state, depth=seed_depth, width=current_width + 50.0),
            _geometry_state_with_updates(seed_state, depth=seed_depth + 50.0, width=current_width + 50.0),
        ]
    deduped: dict[tuple, dict] = {}
    for state in geometries:
        deduped[_make_auto_design_candidate_key(state)] = state
    return list(deduped.values())


def _generate_balanced_geometry_options(seed_candidate: dict) -> list[dict]:
    seed_state = dict(seed_candidate.get("state") or {})
    if _geometry_lock_enabled(seed_state):
        return []
    seed_depth = float(seed_candidate.get("depth", _float_from_state(seed_state, "D", 600.0)) or _float_from_state(seed_state, "D", 600.0))
    _, _, current_width = _resolve_geometry_width_context(seed_state)
    if _candidate_ductility_governs(seed_candidate):
        geometries = [
            _geometry_state_with_updates(seed_state, depth=seed_depth),
            _geometry_state_with_updates(seed_state, depth=seed_depth, width=current_width + 50.0),
            _geometry_state_with_updates(seed_state, depth=seed_depth, width=current_width + 100.0),
            _geometry_state_with_updates(seed_state, depth=seed_depth + 50.0),
        ]
    else:
        geometries = [
            _geometry_state_with_updates(seed_state, depth=seed_depth),
            _geometry_state_with_updates(seed_state, depth=seed_depth - 50.0),
            _geometry_state_with_updates(seed_state, depth=seed_depth + 50.0),
            _geometry_state_with_updates(seed_state, depth=seed_depth, width=current_width - 50.0),
            _geometry_state_with_updates(seed_state, depth=seed_depth, width=current_width + 50.0),
        ]
    deduped: dict[tuple, dict] = {}
    for state in geometries:
        deduped[_make_auto_design_candidate_key(state)] = state
    return list(deduped.values())


def _solve_reo_for_geometry(
    geometry_state: dict,
    *,
    mode_config: dict,
    seed_candidate: dict,
    eval_cache: dict,
    metrics: dict,
) -> dict | None:
    solve_started = time.perf_counter()
    context = _build_auto_design_context(
        seed_candidate["state"],
        mode_config,
        reference_overview=metrics.get("_reference_overview"),
    )
    frontier: list[dict] = []
    base_candidate = _evaluate_candidate_fast(
        geometry_state,
        seed_state=seed_candidate["state"],
        context=context,
        eval_cache=eval_cache,
        metrics=metrics,
        source="geometry_seed",
        label=f"{int(_design_width_value(geometry_state))} x {int(_float_from_state(geometry_state, 'D', 0.0))} mm",
        action_type="auto_design",
    )
    if base_candidate is not None:
        frontier.append(base_candidate)
        if candidate_is_good_enough(base_candidate, mode_config) and _allow_early_target_exit(mode_config):
            metrics["solve_reo_total_ms"] = float(metrics.get("solve_reo_total_ms", 0.0) or 0.0) + ((time.perf_counter() - solve_started) * 1000.0)
            return base_candidate

    max_frontier = int(mode_config.get("max_frontier", 4) or 4)
    for band in range(2):
        if metrics.get("cap_hit"):
            break

        gen_started = time.perf_counter()
        arrangements = _generate_local_bottom_arrangements(geometry_state, mode_config, band=band, context=context)
        metrics["candidate_generation_ms"] = float(metrics.get("candidate_generation_ms", 0.0) or 0.0) + ((time.perf_counter() - gen_started) * 1000.0)
        bottom_candidates: list[dict] = []
        for arrangement in arrangements:
            if metrics.get("cap_hit"):
                break
            candidate_state = dict(geometry_state)
            candidate_state.update(_bottom_arrangement_to_shared_updates(arrangement))
            candidate = _evaluate_candidate_fast(
                candidate_state,
                seed_state=seed_candidate["state"],
                context=context,
                eval_cache=eval_cache,
                metrics=metrics,
                source="reo_band",
                label=_practical_bottom_reo_label(
                    int(arrangement.get("bot1_count", 0) or 0),
                    int(arrangement.get("bot2_count", 0) or 0),
                    int(arrangement.get("db_bot_1", 0) or 0),
                ),
                action_type="auto_design",
            )
            if candidate is not None:
                bottom_candidates.append(candidate)
                if candidate_is_good_enough(candidate, mode_config) and _allow_early_target_exit(mode_config):
                    metrics["solve_reo_total_ms"] = float(metrics.get("solve_reo_total_ms", 0.0) or 0.0) + ((time.perf_counter() - solve_started) * 1000.0)
                    return candidate

        prune_started = time.perf_counter()
        frontier = _keep_top_candidates(frontier + bottom_candidates, mode_config, limit=max_frontier)
        metrics["pruning_total_ms"] = float(metrics.get("pruning_total_ms", 0.0) or 0.0) + ((time.perf_counter() - prune_started) * 1000.0)
        metrics["kept_count"] = max(int(metrics.get("kept_count", 0) or 0), len(frontier))

        refined_candidates: list[dict] = []
        if not bool(context.get("disable_shear_strength_candidates")):
            for candidate in list(frontier):
                if metrics.get("cap_hit"):
                    break
                shear_started = time.perf_counter()
                shear_states = _generate_local_shear_states(candidate["state"], mode_config, band=band)
                metrics["candidate_generation_ms"] = float(metrics.get("candidate_generation_ms", 0.0) or 0.0) + ((time.perf_counter() - shear_started) * 1000.0)
                for shear_state in shear_states:
                    if metrics.get("cap_hit"):
                        break
                    refined = _evaluate_candidate_fast(
                        shear_state,
                        seed_state=seed_candidate["state"],
                        context=context,
                        eval_cache=eval_cache,
                        metrics=metrics,
                        source="shear_band",
                        label=str(candidate.get("label") or "Shear refinement"),
                        action_type="auto_design",
                    )
                    if refined is not None:
                        refined_candidates.append(refined)
                        if candidate_is_good_enough(refined, mode_config) and _allow_early_target_exit(mode_config):
                            metrics["solve_reo_total_ms"] = float(metrics.get("solve_reo_total_ms", 0.0) or 0.0) + ((time.perf_counter() - solve_started) * 1000.0)
                            return refined

        prune_started = time.perf_counter()
        frontier = _keep_top_candidates(frontier + refined_candidates, mode_config, limit=max_frontier)
        metrics["pruning_total_ms"] = float(metrics.get("pruning_total_ms", 0.0) or 0.0) + ((time.perf_counter() - prune_started) * 1000.0)
        metrics["kept_count"] = max(int(metrics.get("kept_count", 0) or 0), len(frontier))

        best_candidate = frontier[0] if frontier else None
        if best_candidate and candidate_is_good_enough(best_candidate, mode_config) and _allow_early_target_exit(mode_config):
            metrics["solve_reo_total_ms"] = float(metrics.get("solve_reo_total_ms", 0.0) or 0.0) + ((time.perf_counter() - solve_started) * 1000.0)
            return best_candidate

    best = frontier[0] if frontier else None
    metrics["solve_reo_total_ms"] = float(metrics.get("solve_reo_total_ms", 0.0) or 0.0) + ((time.perf_counter() - solve_started) * 1000.0)
    return best


def solve_best_reo_for_fixed_depth(candidate_state: dict, mode_config: dict, seed_candidate: dict, eval_cache: dict, metrics: dict) -> dict | None:
    return _solve_reo_for_geometry(candidate_state, mode_config=mode_config, seed_candidate=seed_candidate, eval_cache=eval_cache, metrics=metrics)


def solve_simplest_reo_for_geometry(candidate_state: dict, mode_config: dict, seed_candidate: dict, eval_cache: dict, metrics: dict) -> dict | None:
    return _solve_reo_for_geometry(candidate_state, mode_config=mode_config, seed_candidate=seed_candidate, eval_cache=eval_cache, metrics=metrics)


def solve_balanced_reo_for_geometry(candidate_state: dict, mode_config: dict, seed_candidate: dict, eval_cache: dict, metrics: dict) -> dict | None:
    return _solve_reo_for_geometry(candidate_state, mode_config=mode_config, seed_candidate=seed_candidate, eval_cache=eval_cache, metrics=metrics)


def _choose_better_mode_candidate(current_best: dict | None, candidate: dict | None, mode_config: dict) -> dict | None:
    if candidate is None:
        return current_best
    if current_best is None:
        return candidate
    if candidate_materially_worsens(candidate, current_best, mode_config, phase="mode_search"):
        return current_best
    if not bool(current_best.get("is_compliant")):
        return select_best_next_hop_candidate(current_best, [current_best, candidate], mode_config, phase="solve_to_pass") or current_best
    if _candidate_sort_key_for_mode(candidate, mode_config) < _candidate_sort_key_for_mode(current_best, mode_config):
        return candidate
    return current_best


def optimise_shallow(seed_candidate: dict, mode_config: dict, eval_cache: dict, metrics: dict, *, is_first_hop: bool = False) -> dict:
    best = seed_candidate
    seed_state = dict(seed_candidate.get("state") or {})
    seed_depth = float(seed_candidate.get("depth", _float_from_state(seed_state, "D", 600.0)) or _float_from_state(seed_state, "D", 600.0))
    _, _, current_width = _resolve_geometry_width_context(seed_state)
    same_geometry_candidate = solve_best_reo_for_fixed_depth(seed_state, mode_config, seed_candidate, eval_cache, metrics)
    best = _choose_better_mode_candidate(best, same_geometry_candidate, mode_config) or best
    if same_geometry_candidate and candidate_is_good_enough(same_geometry_candidate, mode_config, reference_candidate=seed_candidate):
        return same_geometry_candidate

    priority_states: dict[tuple, dict] = {}
    if is_first_hop:
        for depth, width in (
            (seed_depth - 50.0, current_width + 100.0),
            (seed_depth - 50.0, current_width + 50.0),
            (seed_depth, current_width + 50.0),
        ):
            if depth < 350.0:
                continue
            candidate_state = _geometry_state_with_updates(seed_state, depth=depth, width=width)
            priority_states[_make_auto_design_candidate_key(candidate_state)] = candidate_state
    for geometry_state in priority_states.values():
        if metrics.get("cap_hit"):
            return best
        candidate = solve_best_reo_for_fixed_depth(geometry_state, mode_config, seed_candidate, eval_cache, metrics)
        best = _choose_better_mode_candidate(best, candidate, mode_config) or best
        if candidate and candidate_is_good_enough(candidate, mode_config, reference_candidate=seed_candidate):
            return candidate

    if not is_first_hop and not bool(seed_candidate.get("is_compliant")):
        for geometry_state in generate_slightly_deeper_depths(seed_candidate):
            if metrics.get("cap_hit"):
                return best
            candidate = solve_best_reo_for_fixed_depth(geometry_state, mode_config, seed_candidate, eval_cache, metrics)
            best = _choose_better_mode_candidate(best, candidate, mode_config) or best
            if candidate and is_valid_progress_while_failing(candidate, seed_candidate):
                return candidate
    for geometry_state in generate_shallow_geometry_options(seed_candidate, include_deeper=False, is_first_hop=is_first_hop):
        if metrics.get("cap_hit"):
            return best
        candidate = solve_best_reo_for_fixed_depth(geometry_state, mode_config, seed_candidate, eval_cache, metrics)
        best = _choose_better_mode_candidate(best, candidate, mode_config) or best
        if candidate and candidate_is_good_enough(candidate, mode_config, reference_candidate=seed_candidate):
            return candidate

    for geometry_state in generate_shallow_geometry_options(seed_candidate, include_deeper=True, is_first_hop=is_first_hop):
        if float(geometry_state.get("D", seed_candidate.get("depth", 0.0)) or 0.0) <= float(seed_candidate.get("depth", 0.0) or 0.0):
            continue
        if metrics.get("cap_hit"):
            return best
        candidate = solve_best_reo_for_fixed_depth(geometry_state, mode_config, seed_candidate, eval_cache, metrics)
        best = _choose_better_mode_candidate(best, candidate, mode_config) or best
        if candidate and candidate_is_good_enough(candidate, mode_config, reference_candidate=seed_candidate):
            return candidate

    return best


def optimise_low_reo(seed_candidate: dict, mode_config: dict, eval_cache: dict, metrics: dict, *, is_first_hop: bool = False) -> dict:
    best = seed_candidate
    same_geometry_candidate = solve_simplest_reo_for_geometry(seed_candidate["state"], mode_config, seed_candidate, eval_cache, metrics)
    best = _choose_better_mode_candidate(best, same_geometry_candidate, mode_config) or best
    if same_geometry_candidate and candidate_is_good_enough(same_geometry_candidate, mode_config, reference_candidate=seed_candidate):
        return same_geometry_candidate
    for geometry_state in generate_same_or_larger_geometry_options(seed_candidate):
        if metrics.get("cap_hit"):
            return best
        candidate = solve_simplest_reo_for_geometry(geometry_state, mode_config, seed_candidate, eval_cache, metrics)
        best = _choose_better_mode_candidate(best, candidate, mode_config) or best
        if candidate and candidate_is_good_enough(candidate, mode_config, reference_candidate=seed_candidate):
            return candidate
    return best


def optimise_balanced(seed_candidate: dict, mode_config: dict, eval_cache: dict, metrics: dict) -> dict:
    best = solve_balanced_reo_for_geometry(seed_candidate["state"], mode_config, seed_candidate, eval_cache, metrics) or seed_candidate
    if candidate_is_good_enough(best, mode_config, reference_candidate=seed_candidate) and _allow_early_target_exit(mode_config):
        return best

    for geometry_state in _generate_balanced_geometry_options(seed_candidate):
        if metrics.get("cap_hit"):
            return best
        candidate = solve_balanced_reo_for_geometry(geometry_state, mode_config, seed_candidate, eval_cache, metrics)
        best = _choose_better_mode_candidate(best, candidate, mode_config) or best
        if candidate and candidate_is_good_enough(candidate, mode_config, reference_candidate=seed_candidate) and _allow_early_target_exit(mode_config):
            return candidate
    return best


def _run_mode_objective_search(seed_candidate: dict, mode_config: dict, eval_cache: dict, metrics: dict, *, is_first_hop: bool = False) -> dict:
    if _geometry_lock_enabled((seed_candidate or {}).get("state") or {}):
        locked = solve_best_reo_for_fixed_depth(seed_candidate["state"], mode_config, seed_candidate, eval_cache, metrics)
        if locked is not None:
            return locked
        return seed_candidate
    strategy = str(mode_config.get("search_strategy", "balanced") or "balanced")
    if strategy == "shallow":
        return optimise_shallow(seed_candidate, mode_config, eval_cache, metrics, is_first_hop=is_first_hop)
    if strategy == "low_reo":
        return optimise_low_reo(seed_candidate, mode_config, eval_cache, metrics, is_first_hop=is_first_hop)
    return optimise_balanced(seed_candidate, mode_config, eval_cache, metrics)


def run_primary_auto_design(seed_candidate: dict, mode_config: dict, eval_cache: dict, metrics: dict, *, is_first_hop: bool = False) -> dict:
    _ensure_candidate_score(seed_candidate, mode_config, seed_candidate)
    if bool(seed_candidate.get("is_compliant")) and _candidate_in_target_zone(seed_candidate, mode_config):
        metrics["phase_a"] = "seed_in_target_cleanup_only"
        metrics["phase_b"] = "cleanup_only"
        return seed_candidate
    phase_results: list[dict] = [seed_candidate]
    feasibility_candidate = seed_candidate
    metrics["phase_a"] = "seed_already_compliant" if bool(seed_candidate.get("is_compliant")) else "search_for_compliance"
    if not bool(seed_candidate.get("is_compliant")):
        feasibility_candidate = _run_mode_objective_search(seed_candidate, mode_config, eval_cache, metrics, is_first_hop=is_first_hop) or seed_candidate
        _ensure_candidate_score(feasibility_candidate, mode_config, seed_candidate)
        phase_results.append(feasibility_candidate)
    objective_seed = select_final_candidate(phase_results, mode_config, baseline_candidate=seed_candidate) or feasibility_candidate or seed_candidate
    metrics["phase_b"] = "objective_search"
    objective_candidate = _run_mode_objective_search(objective_seed, mode_config, eval_cache, metrics, is_first_hop=is_first_hop) or objective_seed
    _ensure_candidate_score(objective_candidate, mode_config, seed_candidate)
    phase_results.append(objective_candidate)
    selected = select_final_candidate(phase_results, mode_config, baseline_candidate=seed_candidate) or objective_candidate or objective_seed
    metrics["primary_phase_result"] = {
        "is_compliant": bool(selected.get("is_compliant")),
        "util_gap": utilisation_gap(selected, mode_config),
        "depth": float(selected.get("depth", 0.0) or 0.0),
        "reo_complexity": float(selected.get("reo_complexity", compute_reo_complexity(selected)) or 0.0),
    }
    return selected


def run_final_tightening_pass(
    initial_candidate: dict,
    mode_config: dict,
    *,
    seed_candidate: dict,
    eval_cache: dict,
    metrics: dict,
    is_first_hop: bool = False,
) -> dict:
    context = _build_auto_design_context(
        seed_candidate["state"],
        mode_config,
        reference_overview=metrics.get("_reference_overview"),
    )
    _ensure_candidate_score(initial_candidate, mode_config, seed_candidate)
    current = initial_candidate
    best = initial_candidate
    explored: list[dict] = [initial_candidate]
    stop_reason = "no_more_candidates"
    for iteration in range(AUTO_DESIGN_MAX_TIGHTENING_ITERS):
        if metrics.get("cap_hit"):
            stop_reason = "evaluation_cap_hit"
            break
        neighbour_states = generate_local_improvement_candidates(
            current,
            mode_config,
            context,
            search_band=1 if is_first_hop and iteration == 0 else 0,
            is_first_hop=is_first_hop and iteration == 0,
        )
        if not neighbour_states:
            stop_reason = "no_more_candidates"
            break
        candidate_results: list[dict] = []
        for candidate_state in neighbour_states:
            candidate = _evaluate_candidate_fast(
                candidate_state,
                seed_state=seed_candidate["state"],
                context=context,
                eval_cache=eval_cache,
                metrics=metrics,
                source="final_tightening",
                label="Final tightening",
                action_type="auto_design",
            )
            if candidate is not None:
                _ensure_candidate_score(candidate, mode_config, seed_candidate)
                if candidate_materially_worsens(candidate, current, mode_config, phase="tightening"):
                    continue
                candidate_results.append(candidate)
        candidate_results = _keep_top_candidates(candidate_results, mode_config, limit=AUTO_DESIGN_MAX_KEPT_RESULTS)
        if not candidate_results:
            stop_reason = "no_more_candidates"
            break
        explored.extend(candidate_results)
        next_best = select_best_next_hop_candidate(current, candidate_results, mode_config, phase="tightening")
        best = select_final_candidate(explored + [best], mode_config, baseline_candidate=best) or best
        metrics["tightening_iterations"] = iteration + 1
        if next_best is None:
            stop_reason = "no_meaningful_candidate"
            break
        if not is_meaningfully_better(next_best, current, mode_config):
            stop_reason = "no_meaningful_improvement"
            break
        current = next_best
        best = select_final_candidate([best, current], mode_config, baseline_candidate=best) or best
        if candidate_is_good_enough(best, mode_config, reference_candidate=seed_candidate):
            stop_reason = "reached_target_zone"
            break
    else:
        stop_reason = "iteration_cap_hit"
    metrics["tightening_stop_reason"] = stop_reason
    return best


def run_cleanup_pass(
    initial_candidate: dict,
    mode_config: dict,
    *,
    seed_candidate: dict,
    eval_cache: dict,
    metrics: dict,
) -> dict:
    context = _build_auto_design_context(
        seed_candidate["state"],
        mode_config,
        reference_overview=metrics.get("_reference_overview"),
    )
    current = initial_candidate
    best = initial_candidate
    protected_case = _critical_case_name(seed_candidate)
    protected_before = _critical_case_util(initial_candidate, protected_case)
    protected_min_util = _protected_case_min_util(protected_before, mode_config)
    metrics["protected_case"] = protected_case
    metrics["protected_util_before_cleanup"] = protected_before
    metrics["protected_min_util"] = protected_min_util
    metrics["cleanup_geometry_locked"] = bool(context.get("geometry_locked"))
    stop_reason = "no_more_safe_local_reductions"
    for iteration in range(AUTO_DESIGN_MAX_TIGHTENING_ITERS):
        candidate_states = generate_cleanup_candidates(current, mode_config, context)
        if not candidate_states:
            stop_reason = "no_more_local_cleanup_candidates"
            break
        candidate_results: list[dict] = []
        for candidate_state in candidate_states:
            candidate = _evaluate_candidate_fast(
                candidate_state,
                seed_state=seed_candidate["state"],
                context=context,
                eval_cache=eval_cache,
                metrics=metrics,
                source="cleanup_pass",
                label="Cleanup",
                action_type="auto_design",
            )
            if candidate is None:
                continue
            _ensure_candidate_score(candidate, mode_config, seed_candidate)
            shear_util_after = _critical_case_util(candidate, "shear")
            if shear_util_after is not None and shear_util_after > 1.0 + 1e-9:
                _agent_debug_log(
                    "Cleanup candidate reviewed",
                    _cleanup_candidate_debug_payload(candidate, current, protected_case, accepted=False, reason="shear_strength_exceeded"),
                    location="inputs_page.py:run_cleanup_pass",
                    hypothesis_id="H_CLEANUP",
                )
                continue
            if not _candidate_reduces_noncritical_provision(candidate, current):
                _agent_debug_log(
                    "Cleanup candidate reviewed",
                    _cleanup_candidate_debug_payload(candidate, current, protected_case, accepted=False, reason="no_noncritical_reduction"),
                    location="inputs_page.py:run_cleanup_pass",
                    hypothesis_id="H_CLEANUP",
                )
                continue
            if not _candidate_preserves_protected_case(candidate, protected_case, protected_min_util=protected_min_util):
                _agent_debug_log(
                    "Cleanup candidate reviewed",
                    _cleanup_candidate_debug_payload(candidate, current, protected_case, accepted=False, reason="protected_case_not_preserved"),
                    location="inputs_page.py:run_cleanup_pass",
                    hypothesis_id="H_CLEANUP",
                )
                continue
            if candidate_materially_worsens(candidate, current, mode_config, phase="cleanup"):
                _agent_debug_log(
                    "Cleanup candidate reviewed",
                    _cleanup_candidate_debug_payload(candidate, current, protected_case, accepted=False, reason="materially_worsens_current"),
                    location="inputs_page.py:run_cleanup_pass",
                    hypothesis_id="H_CLEANUP",
                )
                continue
            candidate_results.append(candidate)
        if not candidate_results:
            stop_reason = "no_more_safe_local_reductions"
            break
        ranked = sorted(candidate_results, key=lambda item: _cleanup_candidate_rank(item, current, protected_case))
        next_best = ranked[0]
        _agent_debug_log(
            "Cleanup candidate reviewed",
            _cleanup_candidate_debug_payload(next_best, current, protected_case, accepted=True, reason="best_safe_local_cleanup"),
            location="inputs_page.py:run_cleanup_pass",
            hypothesis_id="H_CLEANUP",
        )
        best = next_best
        current = next_best
        metrics["cleanup_iterations"] = iteration + 1
    else:
        stop_reason = "cleanup_iteration_cap_hit"
    metrics["cleanup_stop_reason"] = stop_reason
    metrics["cleanup_selected_score"] = float(best.get("score", 0.0) or 0.0) if best else None
    return best


def run_full_auto_design(seed_candidate: dict, mode: str, force: bool = False, is_first_hop: bool = False) -> dict:
    run_started = time.perf_counter()
    mode_config = _design_mode_config(mode)
    eval_cache: dict = {}
    ref_overview = None
    if seed_candidate:
        ref_overview = seed_candidate.get("overview")
        if ref_overview is None and seed_candidate.get("state"):
            ref_overview = _collect_design_overview(seed_candidate["state"])
    metrics = {
        "mode": mode,
        "force": bool(force),
        "optimisation_lock_geometry": _geometry_lock_enabled((seed_candidate or {}).get("state") or {}),
        "generated_count": 0,
        "unique_eval_count": 0,
        "cache_hits": 0,
        "fast_eval_total_ms": 0.0,
        "candidate_generation_ms": 0.0,
        "pruning_total_ms": 0.0,
        "solve_reo_total_ms": 0.0,
        "kept_count": 0,
        "cap_hit": False,
        "_reference_overview": ref_overview,
    }

    primary_best = run_primary_auto_design(seed_candidate, mode_config, eval_cache, metrics, is_first_hop=is_first_hop)
    metrics["phase_c"] = "final_tightening"
    tightened_best = run_final_tightening_pass(
        primary_best,
        mode_config,
        seed_candidate=seed_candidate,
        eval_cache=eval_cache,
        metrics=metrics,
        is_first_hop=is_first_hop,
    )
    metrics["phase_d"] = "cleanup_noncritical"
    cleaned_best = run_cleanup_pass(
        tightened_best,
        mode_config,
        seed_candidate=seed_candidate,
        eval_cache=eval_cache,
        metrics=metrics,
    )
    _ensure_candidate_score(primary_best, mode_config, seed_candidate)
    _ensure_candidate_score(tightened_best, mode_config, seed_candidate)
    _ensure_candidate_score(cleaned_best, mode_config, seed_candidate)
    selected = select_final_candidate([seed_candidate, primary_best, tightened_best, cleaned_best], mode_config, baseline_candidate=seed_candidate) or cleaned_best or tightened_best or primary_best or seed_candidate
    selected = _materialize_full_evaluated_candidate(selected, source="run_full_auto_design:selected_full") or selected
    _final_bending = evaluate_candidate_full(
        dict(selected["state"]),
        source="run_full_auto_design:post_select_bending_verify",
        label=str(selected.get("label") or ""),
        action_type=str(selected.get("action_type") or "auto_design"),
        updates=dict(selected.get("updates") or {}),
    )
    if _final_bending is not None:
        for key in ("reo_complexity", "guidance_preview_util", "arrangement", "actual_ast", "required_ast"):
            if key in selected:
                _final_bending[key] = selected.get(key)
        selected = _final_bending
    selected["score"] = _score_auto_design_candidate(selected, mode_config, seed_candidate)
    material_change = _candidate_materially_better_for_mode(selected, seed_candidate, mode_config)
    metrics["primary_selected_score"] = float(primary_best.get("score", 0.0) or 0.0) if primary_best else None
    metrics["tightened_selected_score"] = float(tightened_best.get("score", 0.0) or 0.0) if tightened_best else None
    metrics["cleanup_selected_score"] = float(cleaned_best.get("score", 0.0) or 0.0) if cleaned_best else None
    metrics["selected_source"] = str(selected.get("source") or "")
    metrics["selected_score"] = float(selected.get("score", 0.0) or 0.0)
    metrics["material_change"] = bool(material_change)
    metrics["selected_depth"] = float(selected.get("depth", 0.0) or 0.0)
    metrics["selected_reo_complexity"] = float(selected.get("reo_complexity", compute_reo_complexity(selected)) or 0.0)
    metrics["total_runtime_ms"] = (time.perf_counter() - run_started) * 1000.0
    _agent_debug_log(
        "Auto-design final selection",
        {
            "mode": mode,
            "phase": "cleanup_noncritical",
            "stop_reason": str(metrics.get("cleanup_stop_reason") or metrics.get("tightening_stop_reason") or ""),
            "optimisation_lock_geometry": bool(metrics.get("optimisation_lock_geometry")),
            "protected_case": str(metrics.get("protected_case") or ""),
            "protected_util_before_cleanup": metrics.get("protected_util_before_cleanup"),
            "selected_score": float(selected.get("score", 0.0) or 0.0),
            "selected_util_gap": float(utilisation_gap(selected, mode_config)),
            "selected_depth": float(selected.get("depth", 0.0) or 0.0),
            "selected_reo_complexity": float(selected.get("reo_complexity", compute_reo_complexity(selected)) or 0.0),
        },
        location="inputs_page.py:run_full_auto_design:final",
        hypothesis_id="H26",
    )
    metrics_out = dict(metrics)
    metrics_out.pop("_reference_overview", None)
    return {
        "candidate": selected,
        "metrics": metrics_out,
        "material_change": material_change,
    }


def run_progressive_auto_design(*, max_steps: int = AUTO_DESIGN_MAX_HOPS_TO_PASS) -> dict:
    _agent_debug_log(
        "run_progressive_auto_design invoked",
        {"max_steps": int(max_steps)},
        location="inputs_page.py:run_progressive_auto_design:invoke",
        hypothesis_id="H6",
    )
    if not _should_run_auto_design():
        return {"status": "idle", "steps": []}

    steps: list[str] = []
    outcome = "no_action"
    solve_stop_reason = "no_action"
    refinement_stop_reason = ""
    compute_all_results()
    initial_state = _shared_state_snapshot()
    current_state = _guidance_state_snapshot(initial_state)
    mode = _design_optimisation_goal(initial_state)
    mode_config = _design_mode_config(mode)
    force_redesign = bool(st.session_state.get("_force_auto_redesign", False))
    requested_force_redesign = force_redesign
    baseline_candidate = evaluate_candidate_full(_guidance_state_snapshot(initial_state), source="seed_base")
    if baseline_candidate is not None:
        _ensure_candidate_score(baseline_candidate, mode_config, baseline_candidate)
    redesign_reason = str(
        st.session_state.get("_auto_design_reason")
        or (
            "mode_changed"
            if force_redesign
            else (
                "not_compliant"
                if baseline_candidate and not baseline_candidate.get("is_compliant")
                else "auto_design_requested"
            )
        )
    )
    best_candidate = baseline_candidate
    best_candidate_seen = baseline_candidate
    best_candidate_accepted = baseline_candidate
    solve_hop_count = 0
    refinement_hop_count = 0
    aggregated_metrics = {
        "optimisation_lock_geometry": _geometry_lock_enabled(initial_state),
        "generated_count": 0,
        "unique_eval_count": 0,
        "cache_hits": 0,
        "fast_eval_total_ms": 0.0,
        "candidate_generation_ms": 0.0,
        "pruning_total_ms": 0.0,
        "solve_reo_total_ms": 0.0,
        "final_full_eval_ms": 0.0,
        "seed_full_eval_ms": 0.0,
        "kept_count": 0,
        "cap_hit": False,
        "total_runtime_ms": 0.0,
        "material_change": False,
        "refinement_fast_eval_total_ms": 0.0,
        "refinement_generated_count": 0,
        "refinement_unique_eval_count": 0,
        "refinement_cache_hits": 0,
    }
    _agent_debug_log(
        "Entered auto-design run",
        {
            "mode": mode,
            "force_redesign": force_redesign,
            "redesign_reason": redesign_reason,
            "seed": None if baseline_candidate is None else {
                "is_compliant": bool(baseline_candidate.get("is_compliant")),
                "worst_util": float(baseline_candidate.get("worst_util", 0.0) or 0.0),
                "depth": float(baseline_candidate.get("depth", 0.0) or 0.0),
                "width": float(baseline_candidate.get("width", 0.0) or 0.0),
                "Ast_bot": float(baseline_candidate.get("Ast_bot", 0.0) or 0.0),
                "row_count": int(baseline_candidate.get("row_count", 0) or 0),
            },
        },
        location="inputs_page.py:run_progressive_auto_design:entry",
        hypothesis_id="H1",
    )

    final_candidate = baseline_candidate
    solve_hop_cap = max(1, int(max_steps))

    for hop in range(solve_hop_cap):
        solve_hop_count = hop + 1
        seed_eval_started = time.perf_counter()
        seed_candidate = evaluate_candidate_full(current_state, source=f"solve_hop_{solve_hop_count}_seed")
        aggregated_metrics["seed_full_eval_ms"] += (time.perf_counter() - seed_eval_started) * 1000.0
        if seed_candidate is None:
            solve_stop_reason = "seed_eval_failed"
            break
        if baseline_candidate is None:
            baseline_candidate = seed_candidate
            best_candidate = seed_candidate
            best_candidate_seen = seed_candidate
            best_candidate_accepted = seed_candidate
        _ensure_candidate_score(seed_candidate, mode_config, baseline_candidate or seed_candidate)

        if bool(seed_candidate.get("is_compliant")) and not (force_redesign and hop == 0):
            best_candidate_accepted = select_final_candidate([best_candidate_accepted, seed_candidate], mode_config, baseline_candidate=best_candidate_accepted) or seed_candidate
            best_candidate = best_candidate_accepted
            final_candidate = best_candidate
            outcome = "pass"
            if _candidate_in_target_zone(seed_candidate, mode_config):
                solve_stop_reason = "already_passes_enter_cleanup" if hop == 0 else "reached_pass_enter_cleanup"
            else:
                solve_stop_reason = "already_passes_needs_refinement" if hop == 0 else "reached_pass_needs_refinement"

        hop_result = run_full_auto_design(seed_candidate, mode, force=force_redesign and hop == 0, is_first_hop=(hop == 0))
        hop_metrics = dict(hop_result.get("metrics") or {})
        next_candidate = hop_result.get("candidate")
        hop_material_change = bool(hop_result.get("material_change"))
        aggregated_metrics["generated_count"] += int(hop_metrics.get("generated_count", 0) or 0)
        aggregated_metrics["unique_eval_count"] += int(hop_metrics.get("unique_eval_count", 0) or 0)
        aggregated_metrics["cache_hits"] += int(hop_metrics.get("cache_hits", 0) or 0)
        aggregated_metrics["fast_eval_total_ms"] += float(hop_metrics.get("fast_eval_total_ms", 0.0) or 0.0)
        aggregated_metrics["candidate_generation_ms"] += float(hop_metrics.get("candidate_generation_ms", 0.0) or 0.0)
        aggregated_metrics["pruning_total_ms"] += float(hop_metrics.get("pruning_total_ms", 0.0) or 0.0)
        aggregated_metrics["solve_reo_total_ms"] += float(hop_metrics.get("solve_reo_total_ms", 0.0) or 0.0)
        aggregated_metrics["total_runtime_ms"] += float(hop_metrics.get("total_runtime_ms", 0.0) or 0.0)
        aggregated_metrics["kept_count"] = max(int(aggregated_metrics.get("kept_count", 0) or 0), int(hop_metrics.get("kept_count", 0) or 0))
        aggregated_metrics["cap_hit"] = bool(aggregated_metrics.get("cap_hit", False) or hop_metrics.get("cap_hit", False))
        aggregated_metrics["material_change"] = bool(aggregated_metrics.get("material_change", False) or hop_material_change)
        for key in ("protected_case", "protected_util_before_cleanup", "protected_min_util", "cleanup_stop_reason", "cleanup_geometry_locked"):
            if key in hop_metrics:
                aggregated_metrics[key] = hop_metrics.get(key)

        if next_candidate is not None:
            _ensure_candidate_score(next_candidate, mode_config, baseline_candidate or seed_candidate)
            best_candidate_seen = select_final_candidate(
                [best_candidate_seen, next_candidate],
                mode_config,
                baseline_candidate=best_candidate_accepted or baseline_candidate,
            ) or best_candidate_seen or next_candidate

        _agent_debug_log(
            "Auto-design solve hop",
            {
                "phase": "solve_to_pass",
                "hop": solve_hop_count,
                "seed_util": None if seed_candidate is None else float(seed_candidate.get("worst_util", 0.0) or 0.0),
                "selected_util": None if next_candidate is None else float(next_candidate.get("worst_util", 0.0) or 0.0),
                "selected_compliant": bool((next_candidate or {}).get("is_compliant")),
            },
            location="inputs_page.py:run_progressive_auto_design:solve_hop",
            hypothesis_id="H27",
        )

        if next_candidate is None:
            best_candidate = select_final_candidate([best_candidate_accepted, seed_candidate], mode_config, baseline_candidate=best_candidate_accepted) or seed_candidate
            final_candidate = best_candidate
            solve_stop_reason = "no_candidate"
            break

        if bool(seed_candidate.get("is_compliant")):
            valid_progress = (
                is_meaningfully_better(next_candidate, seed_candidate, mode_config)
                or _candidate_reduces_noncritical_provision(next_candidate, seed_candidate)
                or _candidate_state_signature(next_candidate) != _candidate_state_signature(seed_candidate)
            )
        else:
            valid_progress = is_valid_progress_while_failing(next_candidate, seed_candidate)
        if not valid_progress:
            best_candidate = select_final_candidate([best_candidate_accepted, seed_candidate, next_candidate], mode_config, baseline_candidate=best_candidate_accepted) or seed_candidate
            final_candidate = best_candidate
            solve_stop_reason = (
                "no_meaningful_improvement" if bool(seed_candidate.get("is_compliant"))
                else "no_valid_progress_while_failing"
            )
            break

        if not candidate_materially_worsens(next_candidate, best_candidate_accepted or seed_candidate, mode_config, phase="solve_to_pass"):
            best_candidate_accepted = select_final_candidate(
                [best_candidate_accepted, next_candidate],
                mode_config,
                baseline_candidate=best_candidate_accepted or seed_candidate,
            ) or best_candidate_accepted or next_candidate
        best_candidate = best_candidate_accepted or next_candidate
        final_candidate = best_candidate
        steps.append(build_auto_design_step_summary(seed_candidate, next_candidate, hop=solve_hop_count, phase_label="Solve hop"))
        current_state = clone_candidate_state_for_next_hop(next_candidate)
        force_redesign = False

        if bool(next_candidate.get("is_compliant")):
            outcome = "pass"
            solve_stop_reason = "reached_pass"
            break
    else:
        solve_stop_reason = "max_hops_to_pass_reached"
        if best_candidate_accepted and bool(best_candidate_accepted.get("is_compliant")):
            outcome = "pass"
        else:
            outcome = "max_steps"

    if best_candidate_accepted is not None and bool(best_candidate_accepted.get("is_compliant")):
        efficiency_state = st.session_state.get("efficiency_tightening_state")
        if not isinstance(efficiency_state, dict):
            try:
                efficiency_state = compute_efficiency_tightening_state(_guidance_state_snapshot(best_candidate_accepted.get("state") or current_state))
            except Exception:
                efficiency_state = {}
        refinement_seed = _guidance_candidate_for_refinement_start(best_candidate_accepted, efficiency_state, mode_config) or best_candidate_accepted
        if refinement_seed is not None:
            best_candidate_seen = select_final_candidate(
                [best_candidate_seen, refinement_seed],
                mode_config,
                baseline_candidate=best_candidate_accepted,
            ) or best_candidate_seen or refinement_seed
        refinement_result = run_compliant_refinement_phase(
            refinement_seed,
            mode_config,
            max_refinement_hops=AUTO_DESIGN_MAX_REFINEMENT_HOPS,
        )
        refinement_hop_count = int(refinement_result.get("hop_count", 0) or 0)
        refinement_stop_reason = str(refinement_result.get("stop_reason") or "")
        refinement_metrics = dict(refinement_result.get("metrics") or {})
        aggregated_metrics["refinement_fast_eval_total_ms"] = float(refinement_metrics.get("fast_eval_total_ms", 0.0) or 0.0)
        aggregated_metrics["refinement_generated_count"] = int(refinement_metrics.get("generated_count", 0) or 0)
        aggregated_metrics["refinement_unique_eval_count"] = int(refinement_metrics.get("unique_eval_count", 0) or 0)
        aggregated_metrics["refinement_cache_hits"] = int(refinement_metrics.get("cache_hits", 0) or 0)
        aggregated_metrics["generated_count"] += int(refinement_metrics.get("generated_count", 0) or 0)
        aggregated_metrics["unique_eval_count"] += int(refinement_metrics.get("unique_eval_count", 0) or 0)
        aggregated_metrics["cache_hits"] += int(refinement_metrics.get("cache_hits", 0) or 0)
        aggregated_metrics["fast_eval_total_ms"] += float(refinement_metrics.get("fast_eval_total_ms", 0.0) or 0.0)
        aggregated_metrics["candidate_generation_ms"] += float(refinement_metrics.get("candidate_generation_ms", 0.0) or 0.0)
        aggregated_metrics["pruning_total_ms"] += float(refinement_metrics.get("pruning_total_ms", 0.0) or 0.0)
        aggregated_metrics["solve_reo_total_ms"] += float(refinement_metrics.get("solve_reo_total_ms", 0.0) or 0.0)
        aggregated_metrics["kept_count"] = max(
            int(aggregated_metrics.get("kept_count", 0) or 0),
            int(refinement_metrics.get("kept_count", 0) or 0),
        )
        aggregated_metrics["cap_hit"] = bool(
            aggregated_metrics.get("cap_hit", False) or refinement_metrics.get("cap_hit", False)
        )
        refined_candidate = refinement_result.get("candidate")
        if refined_candidate is not None and bool(refined_candidate.get("is_compliant")):
            _ensure_candidate_score(refined_candidate, mode_config, baseline_candidate or refined_candidate)
            best_candidate_accepted = select_best_compliant_refinement_candidate(
                [best_candidate_accepted, refined_candidate],
                mode_config,
                baseline_candidate=best_candidate_accepted,
            ) or best_candidate_accepted
            final_candidate = best_candidate_accepted
        steps.extend(list(refinement_result.get("steps") or []))
        outcome = "pass"

    if best_candidate_accepted is not None:
        final_candidate = select_final_candidate(
            [best_candidate_accepted, best_candidate_seen, final_candidate],
            mode_config,
            baseline_candidate=best_candidate_accepted,
        ) or best_candidate_accepted

    final_updates = {}
    final_state = _shared_state_snapshot()
    final_full_eval_ms = 0.0
    committed_candidate_label = None if final_candidate is None else str(final_candidate.get("label") or "")
    committed_candidate_util = None if final_candidate is None else float(final_candidate.get("worst_util", 0.0) or 0.0)
    committed_candidate_signature = _candidate_state_signature(final_candidate)

    if final_candidate is not None and final_candidate.get("state"):
        final_updates = _commit_auto_design_candidate_to_shared(final_candidate)
        if final_updates:
            recalc_derived_values()
            compute_all_results()
            final_state = _shared_state_snapshot()
            final_full_eval_started = time.perf_counter()
            final_candidate = evaluate_candidate_full(_guidance_state_snapshot(final_state), source="final_applied")
            final_full_eval_ms = (time.perf_counter() - final_full_eval_started) * 1000.0
            aggregated_metrics["final_full_eval_ms"] = float(final_full_eval_ms)
            committed_candidate_label = None if final_candidate is None else str(final_candidate.get("label") or committed_candidate_label or "")
            committed_candidate_util = None if final_candidate is None else float(final_candidate.get("worst_util", 0.0) or 0.0)
            committed_candidate_signature = _candidate_state_signature(final_candidate)
            committed_overview = _collect_design_overview(_guidance_state_snapshot(final_state))
            _agent_debug_log(
                "Applied final multi-hop auto-design candidate",
                {
                    "updates": dict(final_updates),
                    "solve_stop_reason": solve_stop_reason,
                    "refinement_stop_reason": refinement_stop_reason,
                    "solve_hops": solve_hop_count,
                    "refinement_hops": refinement_hop_count,
                    "committed_candidate_label": committed_candidate_label,
                    "committed_candidate_util": committed_candidate_util,
                    "committed_candidate_signature": committed_candidate_signature,
                },
                location="inputs_page.py:run_progressive_auto_design:applied",
                hypothesis_id="H28",
            )
            _agent_debug_log(
                "Post auto-design commit check",
                {
                    "committed_db_bot_1": st.session_state.get("db_bot_1"),
                    "committed_bot_row_1_dia": st.session_state.get("bot_row_1_dia"),
                    "committed_lig_legs": st.session_state.get("lig_legs"),
                    "overview_bending_util": ((committed_overview or {}).get("utils") or {}).get("bending"),
                    "overview_shear_util": ((committed_overview or {}).get("utils") or {}).get("shear"),
                    "selected_candidate_label": committed_candidate_label,
                    "selected_candidate_util": committed_candidate_util,
                },
                location="inputs_page.py:auto_design_commit",
                hypothesis_id="H111",
            )
    if final_candidate and final_candidate.get("is_compliant") and outcome != "max_steps":
        outcome = "pass"
        if not refinement_stop_reason and solve_stop_reason not in (
            "already_passes",
            "already_passes_needs_refinement",
            "reached_pass",
            "reached_pass_needs_refinement",
        ):
            solve_stop_reason = "reached_pass"

    final_stop_reason = refinement_stop_reason or solve_stop_reason
    st.session_state["_auto_design_requested"] = False
    st.session_state["_auto_design_invalidated"] = False
    st.session_state["_force_auto_redesign"] = False
    st.session_state["_auto_design_reason"] = redesign_reason
    st.session_state["_auto_design_last_fingerprint"] = _auto_design_governing_fingerprint(final_state)
    st.session_state["_auto_design_last_run"] = {
        "mode": mode,
        "reason": redesign_reason,
        "force_redesign": requested_force_redesign,
        "stop_reason": final_stop_reason,
        "solve_stop_reason": solve_stop_reason,
        "refinement_stop_reason": refinement_stop_reason,
        "solve_hop_count": int(solve_hop_count),
        "refinement_hop_count": int(refinement_hop_count),
        "generated_count": int(aggregated_metrics.get("generated_count", 0) or 0),
        "unique_eval_count": int(aggregated_metrics.get("unique_eval_count", 0) or 0),
        "cache_hits": int(aggregated_metrics.get("cache_hits", 0) or 0),
        "fast_eval_total_ms": float(aggregated_metrics.get("fast_eval_total_ms", 0.0) or 0.0),
        "candidate_generation_ms": float(aggregated_metrics.get("candidate_generation_ms", 0.0) or 0.0),
        "pruning_total_ms": float(aggregated_metrics.get("pruning_total_ms", 0.0) or 0.0),
        "solve_reo_total_ms": float(aggregated_metrics.get("solve_reo_total_ms", 0.0) or 0.0),
        "refinement_fast_eval_total_ms": float(aggregated_metrics.get("refinement_fast_eval_total_ms", 0.0) or 0.0),
        "refinement_generated_count": int(aggregated_metrics.get("refinement_generated_count", 0) or 0),
        "refinement_unique_eval_count": int(aggregated_metrics.get("refinement_unique_eval_count", 0) or 0),
        "refinement_cache_hits": int(aggregated_metrics.get("refinement_cache_hits", 0) or 0),
        "final_full_eval_ms": float(final_full_eval_ms),
        "seed_full_eval_ms": float(aggregated_metrics.get("seed_full_eval_ms", 0.0) or 0.0),
        "kept_count": int(aggregated_metrics.get("kept_count", 0) or 0),
        "cap_hit": bool(aggregated_metrics.get("cap_hit", False)),
        "material_change": bool(aggregated_metrics.get("material_change", False)),
        "seed_score": None if baseline_candidate is None else _score_auto_design_candidate(baseline_candidate, mode_config, baseline_candidate),
        "selected_score": None if final_candidate is None else _score_auto_design_candidate(final_candidate, mode_config, baseline_candidate or final_candidate),
        "committed_candidate_label": committed_candidate_label,
        "committed_candidate_util": committed_candidate_util,
        "committed_candidate_signature": committed_candidate_signature,
    }
    _agent_debug_log(
        "Completed auto-design run",
        {
            "outcome": outcome,
            "solve_stop_reason": solve_stop_reason,
            "refinement_stop_reason": refinement_stop_reason,
            "solve_hop_count": solve_hop_count,
            "refinement_hop_count": refinement_hop_count,
            "steps": list(steps),
            "final": None if final_candidate is None else {
                "is_compliant": bool(final_candidate.get("is_compliant")),
                "worst_util": float(final_candidate.get("worst_util", 0.0) or 0.0),
                "depth": float(final_candidate.get("depth", 0.0) or 0.0),
                "width": float(final_candidate.get("width", 0.0) or 0.0),
            },
        },
        location="inputs_page.py:run_progressive_auto_design:exit",
        hypothesis_id="H1",
    )

    if outcome == "pass":
        steps.append("Design passes.")
    elif solve_stop_reason == "already_passes":
        steps.append("Current design already passes for this auto-design run.")
    elif outcome == "no_action" and not steps:
        steps.append("No better practical candidate was available from the current design state.")
    elif outcome == "max_steps":
        steps.append("Stopped after reaching the solve-to-pass hop limit.")

    if aggregated_metrics.get("optimisation_lock_geometry"):
        steps.append("Geometry locked: optimisation was limited to reinforcement/detailing changes where possible.")
    protected_case = str(aggregated_metrics.get("protected_case") or "")
    protected_util = aggregated_metrics.get("protected_util_before_cleanup")
    if protected_case:
        protected_label = protected_case.replace("_", " ")
        if protected_util is not None:
            steps.append(f"Protected critical case: {protected_label} at utilisation {float(protected_util):.2f} before cleanup.")
        else:
            steps.append(f"Protected critical case: {protected_label}.")
    cleanup_note = _cleanup_stop_reason_message(str(aggregated_metrics.get("cleanup_stop_reason") or ""))
    if cleanup_note:
        steps.append(f"Cleanup result: {cleanup_note}")

    update_results(auto_design_steps=steps, auto_design_status=outcome)
    _queue_inputs_refresh("fast_mode:auto_design_to_pass", ["auto_design_steps", "auto_design_status"], focus_section="model")
    st.rerun()
    return {"status": outcome, "stop_reason": final_stop_reason, "steps": steps}


def _render_progressive_auto_design_panel() -> None:
    live_audit = st.session_state.get("_inputs_render_audit_live")
    if isinstance(live_audit, dict):
        live_audit["old_auto_design_panel_rendered"] = "yes"
    _sync_auto_design_invalidation(_shared_state_snapshot())
    title_col, info_col = st.columns([20, 1], gap="small")
    with title_col:
        st.markdown("### Auto-design")
    with info_col:
        _render_design_optimisation_control(get_sync_callbacks())
    st.caption(
        f"Current preference: **{_design_optimisation_goal_label(_shared_state_snapshot())}**."
    )
    pending_reason = "mode_changed" if st.session_state.get("_force_auto_redesign") else str(st.session_state.get("_auto_design_reason", "") or "")
    if pending_reason:
        st.caption(f"Redesign reason: **{pending_reason.replace('_', ' ')}**.")
    st.caption("Auto-design searches for the best practical passing candidate for the selected preference, not just the first passing fix.")
    auto_design_pressed = st.button(
        "Auto-design to pass",
        key="inputs_auto_design_to_pass",
        type="primary",
        use_container_width=True,
    )
    # region agent log
    _agent_debug_log(
        "Rendered auto-design panel",
        {
            "button_pressed": bool(auto_design_pressed),
            "pending_reason": pending_reason,
            "mode": _design_optimisation_goal(_shared_state_snapshot()),
        },
        location="inputs_page.py:_render_progressive_auto_design_panel",
        hypothesis_id="H7",
    )
    # endregion
    if auto_design_pressed:
        # region agent log
        _agent_debug_log(
            "Auto-design button pressed",
            {
                "mode": _design_optimisation_goal(_shared_state_snapshot()),
                "pending_reason": pending_reason,
            },
            location="inputs_page.py:_render_progressive_auto_design_panel:button",
            hypothesis_id="H6",
        )
        # endregion
        st.session_state["_auto_design_requested"] = True
        st.session_state["_auto_design_reason"] = "auto_design_requested"
        run_progressive_auto_design(max_steps=AUTO_DESIGN_MAX_HOPS)

    steps = st.session_state.get("auto_design_steps", [])
    status = str(st.session_state.get("auto_design_status", "") or "")
    if not steps:
        return

    summary_class = "fast-auto-design-summary success" if status == "pass" else "fast-auto-design-summary"
    steps_html = "".join(
        f"<div class='fast-auto-design-summary-step'>{step}</div>"
        for step in steps
    )
    st.markdown(
        (
            f"<div class='{summary_class}'>"
            "<div class='fast-auto-design-summary-title'>Auto-design steps applied</div>"
            f"{steps_html}"
            "</div>"
        ),
        unsafe_allow_html=True,
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
            # region agent log
            _agent_debug_log(
                "Rendered recommendation section header popover",
                {
                    "title": title,
                    "load_pressed": bool(load_pressed),
                },
                location="inputs_page.py:_render_recommendation_section_header",
                hypothesis_id="H15",
            )
            # endregion
            if load_pressed:
                render_popover_content()
            else:
                st.caption("Load recommendation tools on demand.")


def _render_recommendation_apply_button(
    *,
    button_label: str,
    button_key: str,
    compact: bool,
    applied: bool,
) -> bool:
    return st.button(
        "Applied" if applied else button_label,
        key=button_key,
        type="secondary",
        use_container_width=not compact,
        disabled=applied,
    )


def _render_geometry_recommendation_panel(*, button_key: str, source: str, compact: bool) -> None:
    current_state = _shared_state_snapshot()
    # region agent log
    _agent_debug_log(
        "Entered geometry recommendation panel",
        {"button_key": button_key, "source": source, "compact": bool(compact)},
        location="inputs_page.py:_render_geometry_recommendation_panel",
        hypothesis_id="H14",
    )
    # endregion
    recommendation = _resolve_popover_recommendation(
        cache_name="geometry",
        state=current_state,
        button_key=button_key,
        compute_fn=_compute_geometry_recommendation,
        empty_message="Generate a geometry recommendation on demand for the current beam state.",
    )
    if not recommendation:
        return
    geometry_applied = _updates_match_state(current_state, recommendation["updates"])
    goal_label = _design_optimisation_goal_label(current_state)
    width_key, width_label, current_width = _resolve_geometry_width_context(current_state)
    current_depth = _float_from_state(current_state, "D", 600.0)
    current_bending = _evaluate_bending_with_bottom_state(current_state) or {}
    current_shear = _evaluate_shear_with_state(current_state) or {}
    current_bending_util = float(current_bending.get("Mu_util", 0.0) or 0.0)
    current_shear_util = float(current_shear.get("util", 0.0) or 0.0)
    st.markdown(f"**Key idea**  \n{goal_label} still works through geometry first, and depth usually gives the biggest gain because it improves both lever arm and effective shear depth.")
    st.markdown("**Design impact**")
    st.markdown("- Larger `D` usually reduces bending and shear utilisation together.")
    st.markdown(f"- Width changes are secondary here: current `{width_label}` is {current_width:.0f} mm and the trial value is {recommendation['width']:.0f} mm.")
    st.markdown(f"- This trial moves bending from {current_bending_util:.2f} to {recommendation['bending_util']:.2f} and shear from {current_shear_util:.2f} to {recommendation['shear_util']:.2f}.")
    st.markdown("**Typical action**")
    st.markdown(f"- Test `{width_label} = {recommendation['width']:.0f} mm` with `D = {recommendation['depth']:.0f} mm` when several checks need relief at once.")
    st.caption(f"Web crushing utilisation would become {recommendation['web_util']:.2f}.")
    if _render_recommendation_apply_button(
        button_label="Apply suggested geometry",
        button_key=button_key,
        compact=compact,
        applied=geometry_applied,
    ):
        _apply_geometry_recommendation(source=source)


def _render_bottom_recommendation_panel(*, button_key: str, source: str, compact: bool) -> None:
    current_state = _shared_state_snapshot()
    # region agent log
    _agent_debug_log(
        "Entered bottom recommendation panel",
        {"button_key": button_key, "source": source, "compact": bool(compact)},
        location="inputs_page.py:_render_bottom_recommendation_panel",
        hypothesis_id="H14",
    )
    # endregion
    recommendation = _resolve_popover_recommendation(
        cache_name="bottom_reo",
        state=current_state,
        button_key=button_key,
        compute_fn=_compute_bottom_reo_recommendation,
        empty_message="Generate a bottom reinforcement recommendation on demand for the current beam state.",
    )
    if not recommendation:
        return
    bottom_applied = _updates_match_state(current_state, recommendation["arrangement"])
    goal_label = _design_optimisation_goal_label(current_state)
    current_label = _bottom_reo_state_label(current_state)
    current_bending = _evaluate_bending_with_bottom_state(current_state) or {}
    current_util = float(current_bending.get("Mu_util", 0.0) or 0.0)
    current_ast = _effective_bottom_design_state(current_state)["Ast_bot"]
    st.markdown("**What this controls**")
    st.markdown("- Bottom steel carries the main tension force after flexural cracking, so it mostly changes bending behaviour.")
    st.markdown(f"- Your current preference is `{goal_label}`, so the steel trial aims for a practical amount rather than just adding reserve.")
    st.markdown("**When to change it**")
    st.markdown("- More bars usually spread steel better; larger bars add area faster; extra layers add capacity but can reduce effective depth.")
    st.markdown(f"- This trial changes bending utilisation from {current_util:.2f} to {recommendation['util']:.2f}.")
    st.markdown("**What to avoid**")
    st.markdown("- Do not chase steel area alone if congestion or extra layers start making the section less efficient.")
    st.caption(
        f"Current: {current_label} ({current_ast:.0f} mm^2). "
        f"If applied: {recommendation['label']} ({recommendation['actual_ast']:.0f} mm^2, required {recommendation['required_ast']:.0f} mm^2)."
    )
    if _render_recommendation_apply_button(
        button_label="Apply suggested bottom reo",
        button_key=button_key,
        compact=compact,
        applied=bottom_applied,
    ):
        _apply_bottom_reo_recommendation(source=source)


def _render_shear_recommendation_panel(*, button_key: str, source: str, compact: bool) -> None:
    current_state = _guidance_state_snapshot(_shared_state_snapshot())
    live_pack = build_shear_check_rows_from_state(st.session_state) or {}
    # region agent log
    _agent_debug_log(
        "Entered shear recommendation panel",
        {"button_key": button_key, "source": source, "compact": bool(compact)},
        location="inputs_page.py:_render_shear_recommendation_panel",
        hypothesis_id="H14",
    )
    # endregion
    recommendation = _resolve_popover_recommendation(
        cache_name="shear_reo",
        state=current_state,
        button_key=button_key,
        compute_fn=_compute_shear_recommendation,
        empty_message="Generate a shear reinforcement recommendation on demand for the current beam state.",
    )
    goal_label = _design_optimisation_goal_label(current_state)
    current_shear_label = _shear_state_label(current_state)
    current_shear_util = _parse_util_value(live_pack.get("summary_util"))
    current_phi_vu = float(live_pack.get("summary_phiVu_kN", 0.0) or 0.0)
    current_veq = float(live_pack.get("summary_Veq_kN", 0.0) or 0.0)
    severity_band = _shear_severity_band(current_shear_util)
    shear_applied = bool(recommendation and _updates_match_state(current_state, recommendation["updates"]))
    if not recommendation:
        st.markdown("**Why it matters**")
        st.markdown("- Shear is less forgiving than flexure, so links are there to control diagonal cracking and provide brittle-failure reserve.")
        st.markdown(f"- The current optimisation goal is `{goal_label}`, so the trial balances safety with link efficiency.")
        st.markdown("**Design impact**")
        st.markdown("- Tighter spacing usually lifts shear capacity fastest.")
        st.markdown("- More legs help when spacing is already practical and another direct spacing cut would be too aggressive.")
        st.markdown("- If the current links are already the best practical passing option, no tighter recommendation is shown.")
        st.markdown("**Typical move**")
        st.markdown("- Compare the live links with the proposed trial before applying, especially when web crushing reserve is also important.")
        st.caption(
            f"Current: {current_shear_label} | φVu = {current_phi_vu:.1f} kN | "
            f"V*eq = {current_veq:.1f} kN | utilisation {current_shear_util:.2f}."
        )
        return
    st.markdown("**Why it matters**")
    st.markdown("- Shear is less forgiving than flexure, so links are there to control diagonal cracking and provide brittle-failure reserve.")
    st.markdown(f"- The current optimisation goal is `{goal_label}`, so the trial balances safety with link efficiency.")
    st.markdown("**Design impact**")
    if _severe_shear_failure(current_shear_util):
        rec_type = str(recommendation.get("candidate_type") or "")
        if rec_type == "combined":
            st.markdown("- Combined geometry and link changes are being considered because the current shear failure is severe.")
        elif rec_type in {"depth increase", "width increase"}:
            st.markdown("- Geometry is competing with link changes because the current shear failure is too large for a minor ligature tweak.")
        elif rec_type in {"more legs", "larger dia"}:
            st.markdown("- The trial escalates shear reinforcement significantly because spacing-only changes were too weak for this failure level.")
        else:
            st.markdown("- Spacing-only remained selected because it removes a large share of the current shear failure despite the severe demand.")
    else:
        st.markdown("- Tighter spacing usually lifts shear capacity fastest.")
        st.markdown("- More legs help when spacing is already practical and another direct spacing cut would be too aggressive.")
    st.markdown(f"- This trial changes utilisation from {current_shear_util:.2f} to {recommendation['util']:.2f}.")
    st.markdown("**Typical move**")
    st.markdown("- Compare the live links with the proposed trial before applying, especially when web crushing reserve is also important.")
    st.caption(
        f"Current: {current_shear_label} | φVu = {current_phi_vu:.1f} kN | V*eq = {current_veq:.1f} kN. "
        f"If applied: {recommendation['label']} | φVu = {recommendation['phi_vu']:.1f} kN | "
        f"V*eq = {recommendation['veq']:.1f} kN | web crushing utilisation {recommendation['web_util']:.2f}."
    )
    if _render_recommendation_apply_button(
        button_label="Apply suggested shear reo",
        button_key=button_key,
        compact=compact,
        applied=shear_applied,
    ):
        _apply_shear_recommendation(source=source)


def _render_fast_materials_expander(sync_callbacks: dict) -> None:
    with st.expander("Materials (usually unchanged)", expanded=False):
        st.caption("Material stiffness properties are handled internally and shown in calculation steps where used.")


def _parse_util_value(value) -> float | None:
    if value in (None, "", "—"):
        return None
    try:
        return float(value)
    except Exception:
        try:
            return float(str(value).strip())
        except Exception:
            return None


def _guidance_bucket(status: str, util: float | None = None) -> str:
    upper = str(status or "—").upper()
    if "START" in upper:
        return "start"
    if "EFFICIENCY" in upper or "TIGHTEN" in upper:
        return "efficiency"
    if "FAIL" in upper or upper == "NG":
        return "fail"
    if "WARN" in upper or "NEAR LIMIT" in upper or upper == "CHECK":
        return "warn"
    if util is not None and util > 1.0:
        return "fail"
    if util is not None and util >= 0.9:
        return "warn"
    return "pass"


def _guidance_priority(bucket: str, util: float | None) -> float:
    util_score = util if util is not None else 0.0
    if bucket == "start":
        return 50.0
    if bucket == "fail":
        return 300.0 + util_score
    if bucket == "warn":
        return 200.0 + util_score
    if bucket == "efficiency":
        return 150.0 + util_score
    return 100.0 - util_score


def _format_guidance_title(title: str, util: float | None) -> str:
    if util is None:
        return title
    return f"{title} (utilisation = {util:.2f})"


def _guidance_item(
    check_key: str,
    title: str,
    primary_action: str,
    secondary_action: str | None,
    reasoning: str,
    levers: str,
    action_type: str | None,
    action_payload: dict | None,
    *,
    status: str,
    util: float | None,
    guidance_before_after: str | None = None,
    guidance_change_lines: list[str] | None = None,
    guidance_why: str | None = None,
) -> dict:
    bucket = _guidance_bucket(status, util)
    out: dict = {
        "check_key": check_key,
        "title_main": title,
        "title_util": f"(utilisation = {util:.2f})" if util is not None else None,
        "title": _format_guidance_title(title, util),
        "primary_action": primary_action,
        "secondary_action": secondary_action,
        "reasoning": reasoning,
        "levers": levers,
        "status": status,
        "bucket": bucket,
        "util": util,
        "priority": _guidance_priority(bucket, util),
        "action_type": action_type,
        "action_payload": action_payload or {},
    }
    if guidance_before_after:
        out["guidance_before_after"] = guidance_before_after
    if guidance_change_lines:
        out["guidance_change_lines"] = [str(x) for x in guidance_change_lines if str(x).strip()]
    if guidance_why:
        out["guidance_why"] = str(guidance_why)
    return out


def _guidance_emphasis(index: int, bucket: str) -> str:
    if index == 0 and bucket == "fail":
        return "ACTION"
    if index == 0 and bucket == "efficiency":
        return "TIGHTEN"
    if index == 0:
        return "NEXT"
    return "ALSO"


def _guidance_card_label(item: dict) -> str:
    if item["bucket"] == "start":
        return "START"
    if item["bucket"] in ("fail", "warn"):
        return "NEXT"
    if item["bucket"] == "efficiency":
        return "RECOMMEND"
    return "GOOD"


def _guidance_before_after_text(item: dict, state: dict) -> str | None:
    action_type = item.get("action_type")
    if not action_type:
        return None
    expensive_action_types = {
        "apply_mode_recommendation",
        "apply_bottom_recommendation",
        "apply_geometry_recommendation",
        "apply_shear_recommendation",
        "apply_compound_guidance",
        "reduce_bottom_reinforcement",
        "increase_link_spacing",
        "reduce_number_of_legs",
    }
    if action_type in expensive_action_types:
        return None
    updates = _guidance_action_updates(action_type, item.get("action_payload") or {}, state=state)
    if not updates:
        return None
    after_state = dict(state)
    after_state.update(updates)
    return _describe_guidance_step(state, after_state, action_type, updates)


def _efficiency_guidance_items(state: dict, efficiency_state: dict) -> list[dict]:
    eligible = bool(
        efficiency_state.get("conservative")
        or (
            bool(efficiency_state.get("efficiency_moves_ok"))
            and efficiency_state.get("shear_tightening") is not None
        )
    )
    if not eligible:
        return []

    efficiency_state["target_efficiency_band"] = [GUIDANCE_TARGET_UTIL_MIN, GUIDANCE_TARGET_UTIL_MAX]
    efficiency_state.setdefault("terminal_state_blocked", False)
    efficiency_state.setdefault("terminal_state_block_reason", None)

    goal = _design_optimisation_goal(state)
    items: list[dict] = []
    utils = efficiency_state["overview"]["utils"]
    mode_tighten = efficiency_state.get("mode_tightening")
    bottom_tighten = efficiency_state.get("bottom_tightening")
    shear_tighten = efficiency_state.get("shear_tightening")
    geometry_tighten = efficiency_state.get("geometry_tightening")
    shear_relevant = bool(efficiency_state.get("shear_relevant"))
    shear_cleanup_possible = bool(efficiency_state.get("shear_cleanup_possible"))

    if mode_tighten:
        expected_bend_util = _mode_recommendation_expected_bend_util(mode_tighten)
        if expected_bend_util is None:
            expected_bend_util = _guidance_objective_util_from_overview(efficiency_state["overview"], goal)
        focus = str(mode_tighten.get("focus") or "general")
        title = "Design can be tightened"
        if focus == "geometry":
            title = "Section reserve is high"
        elif focus == "bending":
            title = "Bending reserve is high"
        elif focus == "shear":
            title = "Shear reserve is high"

        if goal == "shallower_beam":
            primary = "Apply recommendation"
            reasoning = "Why: the current design has reserve, and the next recommendation trials a shallower practical section while staying compliant."
        elif goal == "less_longitudinal_reinforcement":
            primary = "Apply recommendation"
            reasoning = "Why: the current design has reserve, and the next recommendation simplifies bottom reinforcement before any broader section change."
        elif goal == "less_shear_reinforcement":
            primary = "Apply recommendation"
            reasoning = "Why: the current design has reserve, and the next recommendation reduces shear demand in the direction of the selected optimisation goal."
        else:
            primary = "Apply recommendation"
            reasoning = "Why: the current design passes comfortably, so the next recommendation moves it toward the preferred practical utilisation band."

        levers = "Key levers: depth D, section width, reinforcement layout, target utilisation band"
        if focus == "bending":
            levers = f"Key levers: bottom reinforcement, arrangement, target utilisation band {EFFICIENCY_TARGET_UTIL_MIN:.2f}-{EFFICIENCY_TARGET_UTIL_MAX:.2f}"
        elif focus == "shear":
            levers = f"Key levers: link spacing, number of legs, target utilisation band {EFFICIENCY_TARGET_UTIL_MIN:.2f}-{EFFICIENCY_TARGET_UTIL_MAX:.2f}"
        elif focus == "geometry":
            levers = f"Key levers: depth D, section width, target utilisation band {EFFICIENCY_TARGET_UTIL_MIN:.2f}-{EFFICIENCY_TARGET_UTIL_MAX:.2f}"

        items.append(
            _guidance_item(
                focus,
                title,
                primary,
                f"Recommended improvement: {mode_tighten['label']}.",
                reasoning,
                levers,
                "apply_mode_recommendation",
                dict(mode_tighten),
                status="EFFICIENCY",
                util=expected_bend_util,
            )
        )
        efficiency_state["terminal_state_blocked"] = False
        efficiency_state["terminal_state_block_reason"] = None
        efficiency_state["efficiency_guidance_items_summary"] = [
            {"title_main": i.get("title_main"), "action_type": i.get("action_type")}
            for i in items
            if isinstance(i, dict)
        ]
        return items

    show_geometry_tighten = bool(geometry_tighten) and goal in ("balanced", "shallower_beam")
    if goal == "less_longitudinal_reinforcement" and geometry_tighten and not bottom_tighten:
        show_geometry_tighten = True

    if show_geometry_tighten and goal == "shallower_beam":
        items.append(
            _guidance_item(
                "geometry",
                "Section reserve is high",
                "Reduce beam depth while staying compliant",
                f"Alternative: trial {geometry_tighten['label']}.",
                "Why: the selected goal prefers a shallower section, and the current reserve is high enough to tighten geometry first.",
                f"Key levers: depth D, section width, target utilisation band {EFFICIENCY_TARGET_UTIL_MIN:.2f}-{EFFICIENCY_TARGET_UTIL_MAX:.2f}",
                "tighten_geometry",
                {"updates": geometry_tighten["updates"]},
                status="EFFICIENCY",
                util=efficiency_state["overview"]["worst_util"],
            )
        )

    if bottom_tighten and utils.get("bending") is not None and utils["bending"] <= GUIDANCE_INEFFICIENT_UTIL_THRESHOLD:
        if goal == "less_longitudinal_reinforcement":
            primary = "Reduce bottom reinforcement slightly"
            reasoning = "Why: bottom steel reserve is high, so you can tighten the design toward a more efficient utilisation band."
        elif goal == "shallower_beam":
            primary = "Trim bottom reinforcement while preserving beam depth"
            reasoning = "Why: the beam passes comfortably, so steel can be reduced before changing the shallower geometry."
        else:
            primary = "Design is conservative. Reduce bottom reinforcement."
            reasoning = "Why: bending reserve is high and can be tightened toward a practical utilisation band."
        items.append(
            _guidance_item(
                "bending",
                "Bending reserve is high",
                primary,
                "Alternative: tighten to an efficient practical design.",
                reasoning,
                f"Key levers: bottom reinforcement, arrangement, target utilisation band {EFFICIENCY_TARGET_UTIL_MIN:.2f}-{EFFICIENCY_TARGET_UTIL_MAX:.2f}",
                "reduce_bottom_reinforcement",
                {"updates": bottom_tighten["arrangement"]},
                status="EFFICIENCY",
                util=utils["bending"],
            )
        )

    if show_geometry_tighten and goal != "shallower_beam":
        if goal == "less_longitudinal_reinforcement":
            primary = "Trim section size only if reinforcement is already practical"
            reasoning = "Why: this goal still prefers simpler reinforcement first, but the section can also be tightened when reserve remains high."
        else:
            primary = "Section reserve is high. Trim the beam slightly."
            reasoning = "Why: after checking steel efficiency, a smaller section can move the beam closer to the target utilisation band."
        items.append(
            _guidance_item(
                "geometry",
                "Section reserve is high",
                primary,
                f"Alternative: trial {geometry_tighten['label']}.",
                reasoning,
                f"Key levers: depth D, section width, target utilisation band {EFFICIENCY_TARGET_UTIL_MIN:.2f}-{EFFICIENCY_TARGET_UTIL_MAX:.2f}",
                "tighten_geometry",
                {"updates": geometry_tighten["updates"]},
                status="EFFICIENCY",
                util=efficiency_state["overview"]["worst_util"],
            )
        )

    if shear_tighten and (
        (utils.get("shear") is not None and utils["shear"] <= GUIDANCE_INEFFICIENT_UTIL_THRESHOLD)
        or shear_cleanup_possible
    ):
        if not shear_relevant and shear_cleanup_possible:
            title = "Shear reinforcement can likely be reduced"
            primary = "Shear reinforcement can likely be reduced"
            reasoning = "Why: shear demand is non-critical, but ligatures are still present and can likely be relaxed safely."
        elif goal == "less_shear_reinforcement":
            title = "Shear reserve is high"
            primary = "Shear reserve is high. Reduce ligature demand."
            reasoning = "Why: the current links are more conservative than needed for the selected goal."
        elif goal == "shallower_beam":
            title = "Shear reserve is high"
            primary = "Ease shear reinforcement before changing geometry"
            reasoning = "Why: the beam already passes comfortably, so link demand can be tightened while keeping depth."
        else:
            title = "Shear reserve is high"
            primary = "Shear reserve is high. Increase link spacing."
            reasoning = "Why: shear capacity reserve is comfortably above demand."
        secondary = (
            f"Alternative: use {shear_tighten['label']}."
            if shear_tighten.get("action_type") == "reduce_number_of_legs"
            else "Alternative: reduce the number of legs if spacing is already practical."
        )
        items.append(
            _guidance_item(
                "shear",
                title,
                primary,
                secondary,
                reasoning,
                f"Key levers: link spacing, number of legs, target utilisation band {EFFICIENCY_TARGET_UTIL_MIN:.2f}-{EFFICIENCY_TARGET_UTIL_MAX:.2f}",
                shear_tighten["action_type"],
                {"updates": shear_tighten["updates"]},
                status="EFFICIENCY",
                util=utils["shear"],
            )
        )

    if not items:
        exhaust = dict(efficiency_state.get("exhaustion_map") or {})
        worst = float(efficiency_state["overview"].get("worst_util", 0) or 0)
        can_term, term_reason = _can_emit_efficiency_terminal_state(worst, exhaust)
        blocked = (not can_term) and worst < float(GUIDANCE_UNDERSIZED_DONE_BLOCK_UTIL)
        efficiency_state["terminal_state_blocked"] = blocked
        efficiency_state["terminal_state_block_reason"] = None if can_term else term_reason
        if not can_term and worst < float(GUIDANCE_UNDERSIZED_DONE_BLOCK_UTIL):
            items.append(
                _guidance_item(
                    "general",
                    "Section still underutilised",
                    "Further safe reductions are being explored",
                    "Optional: use the shear, bottom reinforcement, and geometry panels for on-demand reduction trials.",
                    (
                        "Why: worst utilisation is still below the practical target band, so the guide keeps "
                        "reduction-oriented guidance active instead of treating the design as finished."
                    ),
                    "Key levers: shear links, bottom steel, section geometry, target utilisation band",
                    None,
                    None,
                    status="EFFICIENCY",
                    util=worst,
                )
            )
        else:
            geometry_locked = _geometry_lock_enabled(state)
            title = "No further safe local reductions available"
            primary = "Critical case solved. Reducing non-critical provisions has reached a safe limit."
            if geometry_locked:
                title = "Geometry locked for optimisation"
                primary = "Geometry locked. Optimisation is limited to reinforcement/detailing changes."
            items.append(
                _guidance_item(
                    "general",
                    title,
                    primary,
                    "No further local reductions available without impacting the protected critical case.",
                    (
                        "Why: the governing case is being protected, and no remaining local cleanup move "
                        "can reduce non-critical provision while keeping all checks acceptable."
                    ),
                    "Key levers: protected critical case, local reinforcement/detailing, geometry lock",
                    None,
                    None,
                    status="EFFICIENCY",
                    util=efficiency_state["overview"]["worst_util"],
                )
            )

    efficiency_state["efficiency_guidance_items_summary"] = [
        {"title_main": i.get("title_main"), "action_type": i.get("action_type")}
        for i in items
        if isinstance(i, dict)
    ]
    return items


def _passing_guidance_item(state: dict, overview: dict) -> dict:
    return _guidance_item(
        "general",
        "Design passes with workable reserve",
        "No immediate change needed",
        "Optional: explore alternatives only if you want a different design preference.",
        (
            f"Why: the current beam satisfies the published checks for "
            f"{_design_optimisation_goal_label(state).lower()} with worst utilisation {overview['worst_util']:.2f}."
        ),
        "Key levers: depth D, reinforcement, load path",
        None,
        None,
        status="PASS",
        util=overview["worst_util"],
    )


def _optimal_guidance_item(state: dict, overview: dict) -> dict:
    return _guidance_item(
        "general",
        "Design is in the target utilisation band",
        "No change required",
        "Optional: explore alternatives if you want a different optimisation goal.",
        (
            f"Why: the governing utilisation is {overview['worst_util']:.2f}, which sits in the "
            f"target band of {EFFICIENCY_TARGET_UTIL_MIN:.2f}-{EFFICIENCY_TARGET_UTIL_MAX:.2f}."
        ),
        "Key levers: optimisation preference, geometry, reinforcement",
        None,
        None,
        status="PASS",
        util=overview["worst_util"],
    )


def _candidate_is_materially_actionable(
    state: dict,
    updates: dict | None,
    *,
    delta_b_mm: float | None = None,
    delta_D_mm: float | None = None,
    delta_Ast_bot: float | None = None,
    guidance_change_lines: list | None = None,
) -> bool:
    if guidance_change_lines and any(str(x).strip() for x in guidance_change_lines):
        return True
    u = dict(updates or {})
    if not u or _updates_match_state(state, u):
        return False
    try:
        if delta_b_mm is not None and abs(float(delta_b_mm)) > TARGET_BAND_ACTIONABLE_GEO_DELTA_MM:
            return True
        if delta_D_mm is not None and abs(float(delta_D_mm)) > TARGET_BAND_ACTIONABLE_GEO_DELTA_MM:
            return True
        if delta_Ast_bot is not None and abs(float(delta_Ast_bot)) > TARGET_BAND_ACTIONABLE_AST_DELTA_MM2:
            return True
    except (TypeError, ValueError):
        pass
    material_keys = (
        "bot1_count",
        "bot2_count",
        "db_bot_1",
        "db_bot_2",
        "bot_row_count",
        "bot1_layout_mode",
        "bot2_layout_mode",
        "bot_row_1_mode",
        "bot_row_1_bars",
        "bot_row_2_mode",
        "bot_row_2_bars",
        "lig_d",
        "lig_legs",
        "s_lig",
    )
    if any(k in u for k in material_keys):
        return True
    wkey, _, _ = _resolve_geometry_width_context(state)
    if wkey in u:
        try:
            cur = float(state.get(wkey) or 0.0)
            nu = float(u[wkey])
            if abs(cur - nu) > TARGET_BAND_ACTIONABLE_GEO_DELTA_MM:
                return True
        except (TypeError, ValueError):
            return True
    if "D" in u:
        try:
            d0 = float(_float_from_state(state, "D", 0.0) or 0.0)
            d1 = float(u["D"])
            if abs(d0 - d1) > TARGET_BAND_ACTIONABLE_GEO_DELTA_MM:
                return True
        except (TypeError, ValueError):
            return True
    if "b" in u and wkey != "b":
        try:
            cur = float(_design_width_value(state) or 0.0)
            nu = float(u["b"])
            if abs(cur - nu) > TARGET_BAND_ACTIONABLE_GEO_DELTA_MM:
                return True
        except (TypeError, ValueError):
            return True
    return False


def _in_band_goal_alignment_penalty(cand: dict | None, goal: str) -> float:
    if not isinstance(cand, dict):
        return 1e9
    st = dict(cand.get("state") or {})
    d_val = float(cand.get("depth") or _float_from_state(st, "D", 0.0) or 0.0)
    b_val = float(cand.get("width") or _design_width_value(st) or 0.0)
    ast_val = float(cand.get("Ast_bot", 0.0) or 0.0)
    rc = float(compute_reo_complexity(cand))
    if goal == "shallower_beam":
        return d_val * 0.14 + b_val * 0.035 + ast_val * 0.016 + rc * 4.5
    return ast_val * 0.055 + rc * 9.0 + d_val * 0.055 + b_val * 0.038


def _in_band_strict_material_passes(rec: dict, state: dict, updates: dict) -> bool:
    try:
        db = abs(float(rec.get("delta_b_mm") or 0.0))
        d_d = abs(float(rec.get("delta_D_mm") or 0.0))
        d_ast = abs(float(rec.get("delta_Ast_bot") or 0.0))
    except (TypeError, ValueError):
        return False
    compound = bool(rec.get("recommendation_compound"))
    u = dict(updates or {})
    layout_keys = (
        "bot1_count",
        "bot2_count",
        "db_bot_1",
        "db_bot_2",
        "bot_row_count",
    )
    has_layout = any(k in u for k in layout_keys)
    if d_ast >= IN_BAND_MIN_AST_DELTA_MM2 or d_d >= IN_BAND_MIN_DEPTH_DELTA_MM or db >= IN_BAND_MIN_WIDTH_ALONE_MM:
        return True
    if compound and (
        d_ast >= IN_BAND_COMPOUND_MIN_AST_MM2
        or db >= IN_BAND_COMPOUND_MIN_WIDTH_MM
        or d_d >= IN_BAND_COMPOUND_MIN_DEPTH_MM
        or (has_layout and d_ast >= 45.0)
    ):
        return True
    if has_layout and d_ast >= 80.0:
        return True
    if has_layout and db >= 35.0 and d_ast >= 35.0:
        return True
    return False


def _mode_difference_is_material(rec: dict) -> bool:
    tag = str(rec.get("recommendation_family_tag") or "")
    try:
        db = abs(float(rec.get("delta_b_mm") or 0.0))
    except (TypeError, ValueError):
        db = 0.0
    if tag == "pure_geometry_width" and db < IN_BAND_MIN_WIDTH_ALONE_MM - 1e-9:
        return False
    return True


def _in_band_override_is_strong(rec: dict) -> bool:
    """Extra guard so in-band states do not surface weak refinements."""
    try:
        db = abs(float(rec.get("delta_b_mm") or 0.0))
        d_d = abs(float(rec.get("delta_D_mm") or 0.0))
        d_ast = abs(float(rec.get("delta_Ast_bot") or 0.0))
    except (TypeError, ValueError):
        return False
    if d_d >= 40.0:
        return True
    if d_ast >= 140.0:
        return True
    if db >= 60.0 and d_ast >= 60.0:
        return True
    if bool(rec.get("recommendation_compound")) and (d_d >= 30.0 or db >= 45.0 or d_ast >= 110.0):
        return True
    return False


def _should_override_target_band_done_state(
    rec: dict,
    state: dict,
    overview: dict,
    goal: str,
    mode_config: dict,
    seed_cand: dict | None,
    trial_cand: dict | None,
    *,
    debug_extra: dict | None = None,
) -> tuple[bool, str]:
    if isinstance(debug_extra, dict):
        debug_extra["in_band_overview_worst_util"] = overview.get("worst_util")
    updates = dict(rec.get("updates") or {})
    if not _in_band_strict_material_passes(rec, state, updates):
        if isinstance(debug_extra, dict):
            debug_extra["in_band_materiality_passed"] = False
        return False, "in_band_strict_materiality_fail"
    if isinstance(debug_extra, dict):
        debug_extra["in_band_materiality_passed"] = True
    if not _in_band_override_is_strong(rec):
        if isinstance(debug_extra, dict):
            debug_extra["in_band_strong_override_passed"] = False
        return False, "in_band_override_not_strong_enough"
    if isinstance(debug_extra, dict):
        debug_extra["in_band_strong_override_passed"] = True
    if not _mode_difference_is_material(rec):
        if isinstance(debug_extra, dict):
            debug_extra["mode_difference_material"] = False
        return False, "mode_difference_not_material_pure_geometry_width_nudge"
    if isinstance(debug_extra, dict):
        debug_extra["mode_difference_material"] = True
    if not seed_cand or not trial_cand:
        if isinstance(debug_extra, dict):
            debug_extra["current_goal_alignment_score"] = None
            debug_extra["winner_goal_alignment_score"] = None
            debug_extra["goal_alignment_improvement"] = None
        return False, "missing_seed_or_trial_candidate_for_goal_align"
    pen_c = _in_band_goal_alignment_penalty(seed_cand, goal)
    pen_w = _in_band_goal_alignment_penalty(trial_cand, goal)
    imp = float(pen_c) - float(pen_w)
    if isinstance(debug_extra, dict):
        debug_extra["current_goal_alignment_score"] = pen_c
        debug_extra["winner_goal_alignment_score"] = pen_w
        debug_extra["goal_alignment_improvement"] = imp
    min_gap = IN_BAND_GOAL_ALIGN_MIN_SHALLOW if goal == "shallower_beam" else IN_BAND_GOAL_ALIGN_MIN_BALANCED
    if imp < min_gap - 1e-9:
        return False, "goal_alignment_improvement_below_threshold"
    if goal == "shallower_beam":
        d0 = float(seed_cand.get("depth") or 0.0)
        d1 = float(trial_cand.get("depth") or 0.0)
        if d1 > d0 + 1e-6 and imp < IN_BAND_SHALLOW_DEPTH_UP_MIN_GAIN - 1e-9:
            return False, "shallower_depth_increase_requires_stronger_goal_gain"
    if isinstance(debug_extra, dict):
        debug_extra["in_band_mode_search_strategy"] = str(mode_config.get("search_strategy", "") or "")
    return True, "override_allowed"


def _get_actionable_target_band_winner(
    state: dict,
    overview: dict,
    *,
    debug_extra: dict | None = None,
) -> dict | None:
    if isinstance(debug_extra, dict):
        debug_extra["target_band_default_stop"] = True
        debug_extra["target_band_override_allowed"] = False
        debug_extra["target_band_override_reason"] = None
        debug_extra["in_band_materiality_passed"] = None
        debug_extra["mode_difference_material"] = None
        debug_extra["current_goal_alignment_score"] = None
        debug_extra["winner_goal_alignment_score"] = None
        debug_extra["goal_alignment_improvement"] = None
    if not isinstance(overview, dict) or not bool(overview.get("all_key_pass")):
        if isinstance(debug_extra, dict):
            debug_extra["reason"] = "not_all_key_pass"
        return None
    goal = _design_optimisation_goal(state)
    if goal not in ("balanced", "shallower_beam"):
        if isinstance(debug_extra, dict):
            debug_extra["reason"] = "goal_not_balanced_or_shallower"
        return None
    if not _recommendation_search_allowed(state):
        if isinstance(debug_extra, dict):
            debug_extra["reason"] = "recommendation_search_blocked"
        return None
    if not _reinforcement_options_remain(state):
        if isinstance(debug_extra, dict):
            debug_extra["reason"] = "no_reinforcement_options_remain"
        return None
    try:
        wu = float(overview.get("worst_util", 0.0) or 0.0)
    except (TypeError, ValueError):
        wu = 0.0
    in_band_with_eps = (EFFICIENCY_TARGET_UTIL_MIN <= wu <= (EFFICIENCY_TARGET_UTIL_MAX + TARGET_BAND_EPS))
    if isinstance(debug_extra, dict):
        debug_extra["target_band_eps"] = float(TARGET_BAND_EPS)
        debug_extra["target_band_with_eps_passed"] = bool(in_band_with_eps)
    if not in_band_with_eps:
        if isinstance(debug_extra, dict):
            debug_extra["reason"] = "not_in_efficiency_target_band"
        return None
    if wu > EFFICIENCY_TARGET_UTIL_MAX + 1e-9:
        if isinstance(debug_extra, dict):
            debug_extra["reason"] = "near_upper_band_border_stop_default"
        return None
    rec = _compute_bottom_reo_recommendation(state)
    if not isinstance(rec, dict):
        if isinstance(debug_extra, dict):
            debug_extra["reason"] = "no_bottom_recommendation"
        return None
    updates = dict(rec.get("updates") or {})
    if not updates or _updates_match_state(state, updates):
        if isinstance(debug_extra, dict):
            debug_extra["reason"] = "empty_or_noop_updates"
        return None
    raw_cl = rec.get("guidance_change_lines")
    clines = raw_cl if isinstance(raw_cl, list) else _guidance_change_lines_for_updates(state, updates)
    if not _candidate_is_materially_actionable(
        state,
        updates,
        delta_b_mm=rec.get("delta_b_mm"),
        delta_D_mm=rec.get("delta_D_mm"),
        delta_Ast_bot=rec.get("delta_Ast_bot"),
        guidance_change_lines=None,
    ):
        if isinstance(debug_extra, dict):
            debug_extra["reason"] = "not_materially_actionable"
        return None
    trial = dict(_guidance_state_snapshot(state))
    trial.update(updates)
    cand = evaluate_candidate_full(
        _guidance_state_snapshot(trial),
        source="target_band_actionable_winner_check",
    )
    if not cand or not bool((cand.get("overview") or {}).get("all_key_pass")):
        if isinstance(debug_extra, dict):
            debug_extra["reason"] = "trial_not_compliant_or_eval_failed"
        return None
    mode_cfg = _design_mode_config(goal)
    seed_c = evaluate_candidate_full(
        _guidance_state_snapshot(state),
        source="in_band_goal_align_seed",
    )
    ok_override, o_reason = _should_override_target_band_done_state(
        rec,
        state,
        overview,
        goal,
        mode_cfg,
        seed_c,
        cand,
        debug_extra=debug_extra,
    )
    if isinstance(debug_extra, dict):
        debug_extra["target_band_override_reason"] = o_reason
    if not ok_override:
        if isinstance(debug_extra, dict):
            debug_extra["reason"] = o_reason
        return None
    if isinstance(debug_extra, dict):
        debug_extra["target_band_default_stop"] = False
        debug_extra["target_band_override_allowed"] = True
    gcl = [str(x).strip() for x in (clines or []) if str(x).strip()]
    fam = str(rec.get("recommendation_family_tag") or "")
    subs = list(rec.get("subfamilies") or []) if isinstance(rec.get("subfamilies"), list) else []
    if isinstance(debug_extra, dict):
        debug_extra["family"] = fam
        debug_extra["subfamilies"] = subs
        debug_extra["change_lines"] = gcl
    title = (
        str(rec.get("guidance_recommendation_title") or rec.get("label") or "").strip()
        or "Refine section and bottom reinforcement"
    )
    primary = str(rec.get("label") or "").strip() or "Apply recommended adjustment"
    return _guidance_item(
        "bending",
        title,
        primary,
        "Alternative: keep the current design if the reserve is acceptable.",
        (
            f"Why: worst utilisation is {wu:.2f} (within the "
            f"{EFFICIENCY_TARGET_UTIL_MIN:.2f}-{EFFICIENCY_TARGET_UTIL_MAX:.2f} target band), "
            f"but a practical one-click refinement remains for "
            f"{_design_optimisation_goal_label(state).lower()}."
        ),
        "Key levers: beam width b, depth D, bottom reinforcement layout",
        "apply_bottom_recommendation",
        {},
        status="PASS",
        util=wu,
        guidance_change_lines=gcl or None,
    )


def _merge_target_band_probe_to_debug_sink(sink: dict | None, probe: dict) -> None:
    if not isinstance(sink, dict):
        return
    for k in (
        "target_band_default_stop",
        "target_band_override_allowed",
        "target_band_override_reason",
        "target_band_eps",
        "target_band_with_eps_passed",
        "winner_goal_alignment_score",
        "current_goal_alignment_score",
        "goal_alignment_improvement",
        "in_band_materiality_passed",
        "in_band_strong_override_passed",
        "mode_difference_material",
        "in_band_mode_search_strategy",
        "in_band_overview_worst_util",
    ):
        if k in probe:
            sink[k] = probe.get(k)


def _guidance_not_started(state: dict, overview: dict) -> bool:
    _, _, width = _resolve_geometry_width_context(state)
    depth = _float_from_state(state, "D", 0.0)
    span = _float_from_state(state, "L", 0.0)
    required_inputs_missing = width <= 0.0 or depth <= 0.0 or span <= 0.0

    bending_util = overview["utils"].get("bending")
    shear_util = overview["utils"].get("shear")
    no_key_results = all(util is None or util <= 0.0 for util in (bending_util, shear_util))

    action_values = [
        abs(_uls_action_from_state(state, "M")),
        abs(_uls_action_from_state(state, "V")),
        abs(_uls_action_from_state(state, "N")),
        abs(_uls_action_from_state(state, "T")),
    ]
    no_actions = max(action_values, default=0.0) <= 1e-9

    bottom_state = _effective_bottom_design_state(state)
    no_bottom_reo = (
        float(bottom_state.get("Ast_bot", 0.0) or 0.0) <= 0.0
        or int(bottom_state.get("nb_bot", 0) or 0) <= 0
        or float(bottom_state.get("db_bot", 0.0) or 0.0) <= 0.0
    )
    no_shear_reo = (
        _int_from_state(state, "lig_legs", 0) <= 0
        or _float_from_state(state, "lig_d", 0.0) <= 0.0
        or _float_from_state(state, "s_lig", 0.0) <= 0.0
    )
    return required_inputs_missing or no_key_results or (no_actions and (no_bottom_reo or no_shear_reo))


def _guidance_start_item(state: dict) -> dict:
    _, start_line = _fast_start_here_content(state)
    item = _guidance_item(
        "general",
        "Choose your workflow:",
        start_line,
        None,
        "Or define loads from the Design page",
        "Key levers: geometry, actions, initial reinforcement",
        None,
        None,
        status="START",
        util=None,
    )
    item["start_steps"] = [
        "Fast -> guided design",
        "Detailed -> full control",
    ]
    return item


def _fast_start_here_content(state: dict) -> tuple[str, str]:
    _, _, width = _resolve_geometry_width_context(state)
    depth = _float_from_state(state, "D", 0.0)
    span = _float_from_state(state, "L", 0.0)
    has_geometry = any(value > 0.0 for value in (width, depth, span))

    action_values = [
        abs(_uls_action_from_state(state, "M")),
        abs(_uls_action_from_state(state, "V")),
        abs(_uls_action_from_state(state, "N")),
        abs(_uls_action_from_state(state, "T")),
    ]
    has_actions = max(action_values, default=0.0) > 1e-9

    bottom_state = _effective_bottom_design_state(state)
    has_bottom_reo = (
        float(bottom_state.get("Ast_bot", 0.0) or 0.0) > 0.0
        and int(bottom_state.get("nb_bot", 0) or 0) > 0
        and float(bottom_state.get("db_bot", 0.0) or 0.0) > 0.0
    )
    has_shear_reo = (
        _int_from_state(state, "lig_legs", 0) > 0
        and _float_from_state(state, "lig_d", 0.0) > 0.0
        and _float_from_state(state, "s_lig", 0.0) > 0.0
    )
    is_continue = has_geometry or has_actions or has_bottom_reo or has_shear_reo
    return (
        "CONTINUE" if is_continue else "START",
        "Add reinforcement or loads to activate checks" if is_continue else "Start by setting geometry or reinforcement",
    )


def _log_guidance_ladder_debug(
    ladder_name: str,
    *,
    candidate_label: str,
    candidate_updates: dict | None,
    decision: str,
    reason: str,
    metric_name: str,
    metric_before: float | None,
    metric_after: float | None,
    early_stop: bool = False,
) -> None:
    if not DEBUG_DESIGN_GUIDANCE_PROBE:
        return
    _agent_debug_log(
        "Guidance ladder step",
        {
            "ladder": ladder_name,
            "candidate_label": candidate_label,
            "candidate_updates": candidate_updates,
            "decision": decision,
            "reason": reason,
            "metric_name": metric_name,
            "metric_before": metric_before,
            "metric_after": metric_after,
            "early_stop": bool(early_stop),
        },
        location="inputs_page.py:_log_guidance_ladder_debug",
        hypothesis_id="H_GUIDANCE_LADDER",
    )


def _merge_guidance_state(state: dict, updates: dict) -> dict:
    merged = dict(state)
    merged.update(updates)
    return merged


def _geometry_trial_delta_mm_total(state: dict, updates: dict) -> float:
    d0 = float(state.get("D", 0.0) or 0.0)
    d1 = float(updates.get("D", d0) or d0)
    wkey, _, w0 = _resolve_geometry_width_context(state)
    w0 = float(w0 or 0.0)
    if wkey in updates:
        w1 = float(updates[wkey] or 0.0)
    else:
        w1 = w0
    return abs(d1 - d0) + abs(w1 - w0)


def _geometry_width_depth_trial_specs() -> list[tuple[str, str, dict]]:
    specs: list[tuple[str, str, dict]] = []
    for d in GUIDANCE_GEOMETRY_TRIAL_DELTAS_MM:
        specs.append((f"Increase depth D by {d} mm", "increase_depth", {"delta_mm": float(d)}))
    for d in GUIDANCE_GEOMETRY_TRIAL_DELTAS_MM:
        specs.append((f"Increase section width by {d} mm", "increase_width", {"delta_mm": float(d)}))
    return specs


def _read_metric_for_geometry_trial(state: dict, *, metric: str, bending_mode: str) -> float | None:
    if metric == "shear":
        ev = _evaluate_shear_with_state(state)
        if not ev:
            return None
        u = float(ev.get("util", 0.0) or 0.0)
        return u if math.isfinite(u) else None
    if metric == "crack":
        ev = _evaluate_crack_with_state(state)
        if not ev:
            return None
        return float(ev.get("util", 0.0) or 0.0)
    if metric == "deflection":
        ev = _evaluate_deflection_with_state(state)
        if not ev or ev.get("util") is None:
            return None
        u = float(ev.get("util", 0.0) or 0.0)
        return u if math.isfinite(u) else None
    if metric == "bending":
        b = _evaluate_bending_with_bottom_state(state)
        if not b:
            return None
        if bending_mode == "ductility":
            ku = b.get("ku")
            if ku is None:
                return None
            return float(ku) / 0.36
        mu = float(b.get("Mu_util", 0.0) or 0.0)
        ku = b.get("ku")
        du = (float(ku) / 0.36) if ku is not None else 0.0
        return max(mu, du)
    return None


def _choose_geometry_trial_for_metric(
    state: dict,
    *,
    metric: str,
    baseline_util: float | None = None,
    bending_mode: str = "governing",
    ladder_name: str = "geometry_trial",
) -> dict | None:
    def read_metric(st: dict) -> float | None:
        return _read_metric_for_geometry_trial(st, metric=metric, bending_mode=bending_mode)

    base_u = read_metric(state) if baseline_util is None else float(baseline_util)
    if base_u is None or not math.isfinite(base_u):
        _log_guidance_ladder_debug(
            ladder_name,
            candidate_label="(init)",
            candidate_updates=None,
            decision="rejected",
            reason="missing_baseline_metric",
            metric_name=metric,
            metric_before=None,
            metric_after=None,
        )
        return None

    best: dict | None = None
    best_key: tuple | None = None
    for label, atype, payload in _geometry_width_depth_trial_specs():
        updates = _guidance_action_updates(atype, payload, state=state)
        if not updates or _updates_match_state(state, updates):
            _log_guidance_ladder_debug(
                ladder_name,
                candidate_label=label,
                candidate_updates=updates,
                decision="rejected",
                reason="noop",
                metric_name=metric,
                metric_before=base_u,
                metric_after=None,
            )
            continue
        trial_state = _merge_guidance_state(state, updates)
        nu = read_metric(trial_state)
        if nu is None or not math.isfinite(nu):
            _log_guidance_ladder_debug(
                ladder_name,
                candidate_label=label,
                candidate_updates=updates,
                decision="rejected",
                reason="missing_metric_after",
                metric_name=metric,
                metric_before=base_u,
                metric_after=None,
            )
            continue
        if nu >= base_u - 1e-9:
            _log_guidance_ladder_debug(
                ladder_name,
                candidate_label=label,
                candidate_updates=updates,
                decision="rejected",
                reason="no_improvement_vs_baseline",
                metric_name=metric,
                metric_before=base_u,
                metric_after=nu,
            )
            continue
        passes = nu <= 1.0 + 1e-9
        delta_tot = _geometry_trial_delta_mm_total(state, updates)
        d0 = float(state.get("D", 0.0) or 0.0)
        d_after = float(trial_state.get("D", d0) or d0)
        depth_growth = max(d_after - d0, 0.0)
        wkey, _, w0 = _resolve_geometry_width_context(state)
        w0 = float(w0 or 0.0)
        if wkey in updates:
            w1 = float(updates[wkey] or 0.0)
        else:
            w1 = w0
        width_growth = max(w1 - w0, 0.0)
        if _design_optimisation_goal(state) == "shallower_beam":
            key = (0 if passes else 1, round(float(nu), 2), depth_growth, width_growth, delta_tot)
        else:
            key = (0 if passes else 1, delta_tot, nu)
        if best_key is None or key < best_key:
            best_key = key
            after_state = trial_state
            ba = _describe_guidance_step(state, after_state, atype, updates)
            best = {
                "label": label,
                "action_type": atype,
                "payload": dict(payload),
                "updates": updates,
                "util_before": base_u,
                "util_after": nu,
                "before_after": ba,
            }

    cur_d = float(state.get("D", 0.0) or 0.0)
    ref_d = _design_guide_effective_reference_depth(state)
    tmpl_d = float(SHARED_DEFAULTS.get("D", 600.0))
    trial_debug: dict = {
        "correction_candidate_considered": False,
        "correction_candidate_summary": None,
        "correction_candidate_score": None,
        "correction_candidate_won": False,
        "reference_D": ref_d,
        "current_D": cur_d,
        "D_offset_from_reference": round(cur_d - ref_d, 3),
        "goal_alignment_penalty": round(max(0.0, cur_d - ref_d) / 100.0, 3),
    }
    if (
        best
        and _design_optimisation_goal(state) == "shallower_beam"
        and metric == "bending"
    ):
        best_upd = best.get("updates") or {}
        ts_best = _merge_guidance_state(state, best_upd)
        d_after_best = float(ts_best.get("D", cur_d) or cur_d)
        wkey, _, w0 = _resolve_geometry_width_context(state)
        w0 = float(w0 or 0.0)
        w_after = float(best_upd[wkey]) if wkey in best_upd else w0
        depth_growth_best = max(d_after_best - cur_d, 0.0)
        width_growth_best = max(w_after - w0, 0.0)
        growth_continuation = (
            depth_growth_best < 1e-9
            and width_growth_best > 1e-9
            and cur_d > tmpl_d + GUIDANCE_SHALLOW_CORRECTION_MIN_D_OVER_TEMPLATE_MM
        )
        if growth_continuation:
            trial_debug["correction_candidate_considered"] = True
            best_nu = float(best.get("util_after", 99.0) or 99.0)
            pick_upd: dict | None = None
            pick_nu: float | None = None
            pick_label: str | None = None
            pick_d = cur_d
            for clabel, cupd in _shallower_beam_correction_trial_updates(state):
                if _updates_match_state(state, cupd):
                    continue
                trial_m = _merge_guidance_state(state, cupd)
                nu_c = read_metric(trial_m)
                if nu_c is None or not math.isfinite(nu_c):
                    continue
                d_trial = float(trial_m.get("D", cur_d) or cur_d)
                if cur_d - d_trial < GUIDANCE_SHALLOW_CORRECTION_MIN_DEPTH_DROP_MM - 1e-9:
                    continue
                if nu_c > 1.0 + 1e-9:
                    continue
                if nu_c > best_nu + GUIDANCE_SHALLOW_CORRECTION_METRIC_MARGIN:
                    continue
                if nu_c >= base_u - 1e-9:
                    continue
                if pick_nu is None or nu_c < float(pick_nu) - 1e-9 or (
                    abs(nu_c - float(pick_nu)) < 1e-9 and d_trial < pick_d
                ):
                    pick_upd = dict(cupd)
                    pick_nu = float(nu_c)
                    pick_label = str(clabel)
                    pick_d = d_trial
            if pick_upd is not None and pick_nu is not None and pick_label is not None:
                after_c = _merge_guidance_state(state, pick_upd)
                ba_c = _describe_guidance_step(
                    state, after_c, "apply_geometry_recommendation", pick_upd,
                )
                best = {
                    "label": pick_label,
                    "action_type": "apply_geometry_recommendation",
                    "payload": {"updates": dict(pick_upd)},
                    "updates": dict(pick_upd),
                    "util_before": base_u,
                    "util_after": float(pick_nu),
                    "before_after": ba_c,
                }
                trial_debug["correction_candidate_won"] = True
                trial_debug["correction_candidate_score"] = float(pick_nu)
                trial_debug["correction_candidate_summary"] = pick_label
            else:
                trial_debug["correction_candidate_summary"] = (
                    "no compliant correction within util margin vs width-growth trial"
                )
    st.session_state[DESIGN_GUIDE_GEOMETRY_TRIAL_DEBUG_KEY] = trial_debug

    if best:
        ua = float(best.get("util_after", 99.0) or 99.0)
        _log_guidance_ladder_debug(
            ladder_name,
            candidate_label=str(best.get("label") or ""),
            candidate_updates=best.get("updates"),
            decision="accepted",
            reason="best_scored_trial",
            metric_name=metric,
            metric_before=base_u,
            metric_after=ua,
            early_stop=bool(ua <= GUIDANCE_LADDER_EARLY_STOP_UTIL),
        )
    else:
        _log_guidance_ladder_debug(
            ladder_name,
            candidate_label="(none)",
            candidate_updates=None,
            decision="rejected",
            reason="no_candidate_improved",
            metric_name=metric,
            metric_before=base_u,
            metric_after=None,
        )
    return best


def _crack_ladder_tighten_spacing_updates(state: dict) -> dict | None:
    if str(state.get("bot1_layout_mode", "Count") or "Count") != "Spacing":
        return None
    return _guidance_action_updates(
        "reduce_bar_spacing",
        {"delta_mm": 25.0, "minimum_spacing": float(min(REO_SPACINGS))},
        state=state,
    )


def _crack_ladder_add_one_bottom_bar_updates(state: dict) -> dict | None:
    current_count = int(state.get("bot1_count", 4) or 4)
    current_count_2 = int(state.get("bot2_count", 0) or 0)
    db1 = int(state.get("db_bot_1", 20) or 20)
    db2 = int(state.get("db_bot_2", state.get("db_bot_1", 20)) or state.get("db_bot_1", 20))
    if current_count < max(REO_COUNTS_0_12):
        u = _bottom_arrangement_to_shared_updates({
            "bot1_count": current_count + 1,
            "bot2_count": current_count_2,
            "db_bot_1": db1,
            "db_bot_2": db2,
        })
        if u and not _updates_match_state(state, u):
            return u
    if current_count_2 < max(REO_COUNTS_0_12):
        u = _bottom_arrangement_to_shared_updates({
            "bot1_count": current_count,
            "bot2_count": current_count_2 + 1,
            "db_bot_1": db1,
            "db_bot_2": db2,
        })
        if u and not _updates_match_state(state, u):
            return u
    return None


def _crack_ladder_consolidate_bottom_rows_updates(state: dict) -> dict | None:
    c1 = int(state.get("bot1_count", 0) or 0)
    c2 = int(state.get("bot2_count", 0) or 0)
    if c2 <= 0 or c1 <= 0:
        return None
    db1 = int(state.get("db_bot_1", 20) or 20)
    db2 = int(state.get("db_bot_2", db1) or db1)
    if db1 != db2:
        return None
    merged = {
        "bot1_count": c1 + c2,
        "bot2_count": 0,
        "db_bot_1": db1,
        "db_bot_2": db1,
    }
    if not _arrangement_fits_state(state, merged):
        return None
    u = _bottom_arrangement_to_shared_updates(merged)
    if not u or _updates_match_state(state, u):
        return None
    return u


def _try_crack_ladder_candidate(
    state: dict,
    *,
    label: str,
    updates: dict | None,
    base_util: float,
    ladder_name: str = "crack_ladder",
) -> dict | None:
    if not updates:
        _log_guidance_ladder_debug(
            ladder_name,
            candidate_label=label,
            candidate_updates=None,
            decision="rejected",
            reason="empty_updates",
            metric_name="crack_util",
            metric_before=base_util,
            metric_after=None,
        )
        return None
    if _updates_match_state(state, updates):
        _log_guidance_ladder_debug(
            ladder_name,
            candidate_label=label,
            candidate_updates=updates,
            decision="rejected",
            reason="noop_vs_state",
            metric_name="crack_util",
            metric_before=base_util,
            metric_after=None,
        )
        return None
    ev = _evaluate_crack_with_state(_merge_guidance_state(state, updates))
    if not ev:
        _log_guidance_ladder_debug(
            ladder_name,
            candidate_label=label,
            candidate_updates=updates,
            decision="rejected",
            reason="crack_eval_none",
            metric_name="crack_util",
            metric_before=base_util,
            metric_after=None,
        )
        return None
    nu = float(ev.get("util", 0.0) or 0.0)
    if nu >= base_util - 1e-9:
        _log_guidance_ladder_debug(
            ladder_name,
            candidate_label=label,
            candidate_updates=updates,
            decision="rejected",
            reason="no_improvement",
            metric_name="crack_util",
            metric_before=base_util,
            metric_after=nu,
        )
        return None
    early = nu <= GUIDANCE_LADDER_EARLY_STOP_UTIL and nu <= 1.0 + 1e-9
    _log_guidance_ladder_debug(
        ladder_name,
        candidate_label=label,
        candidate_updates=updates,
        decision="accepted",
        reason="improves_crack_util",
        metric_name="crack_util",
        metric_before=base_util,
        metric_after=nu,
        early_stop=early,
    )
    return {"label": label, "updates": updates, "util_after": nu, "early_stop": early}


def _pick_crack_ladder_first_improvement(state: dict, *, base_util: float) -> dict | None:
    ladder_name = "crack_ladder"
    layout_sp = str(state.get("bot1_layout_mode", "Count") or "Count") == "Spacing"

    if layout_sp:
        u = _crack_ladder_tighten_spacing_updates(state)
        r = _try_crack_ladder_candidate(
            state,
            label="Tighten bottom bar spacing (one step)",
            updates=u,
            base_util=base_util,
            ladder_name=ladder_name,
        )
        if r:
            r["kind"] = "bottom_explicit"
            return r

    u = _crack_ladder_add_one_bottom_bar_updates(state)
    r = _try_crack_ladder_candidate(
        state,
        label="Add one bottom bar",
        updates=u,
        base_util=base_util,
        ladder_name=ladder_name,
    )
    if r:
        r["kind"] = "bottom_explicit"
        return r

    u = _crack_ladder_consolidate_bottom_rows_updates(state)
    r = _try_crack_ladder_candidate(
        state,
        label="Consolidate bottom bars into one row (same total bars)",
        updates=u,
        base_util=base_util,
        ladder_name=ladder_name,
    )
    if r:
        r["kind"] = "bottom_explicit"
        return r

    geo = _choose_geometry_trial_for_metric(
        state,
        metric="crack",
        baseline_util=base_util,
        ladder_name="crack_geometry_trials",
    )
    if not geo:
        return None
    return {
        "kind": "geometry",
        "label": geo["label"],
        "action_type": geo["action_type"],
        "payload": geo["payload"],
        "updates": geo["updates"],
        "util_after": geo["util_after"],
        "before_after": geo.get("before_after"),
    }


def _try_deflection_ladder_candidate(
    state: dict,
    *,
    label: str,
    updates: dict | None,
    base_util: float,
    ladder_name: str = "deflection_ladder",
) -> dict | None:
    if not updates:
        _log_guidance_ladder_debug(
            ladder_name,
            candidate_label=label,
            candidate_updates=None,
            decision="rejected",
            reason="empty_updates",
            metric_name="deflection_util",
            metric_before=base_util,
            metric_after=None,
        )
        return None
    if _updates_match_state(state, updates):
        _log_guidance_ladder_debug(
            ladder_name,
            candidate_label=label,
            candidate_updates=updates,
            decision="rejected",
            reason="noop_vs_state",
            metric_name="deflection_util",
            metric_before=base_util,
            metric_after=None,
        )
        return None
    ev = _evaluate_deflection_with_state(_merge_guidance_state(state, updates))
    if not ev or ev.get("util") is None:
        _log_guidance_ladder_debug(
            ladder_name,
            candidate_label=label,
            candidate_updates=updates,
            decision="rejected",
            reason="deflection_eval_none",
            metric_name="deflection_util",
            metric_before=base_util,
            metric_after=None,
        )
        return None
    nu = float(ev.get("util", 0.0) or 0.0)
    if nu >= base_util - 1e-9:
        _log_guidance_ladder_debug(
            ladder_name,
            candidate_label=label,
            candidate_updates=updates,
            decision="rejected",
            reason="no_improvement",
            metric_name="deflection_util",
            metric_before=base_util,
            metric_after=nu,
        )
        return None
    early = nu <= GUIDANCE_LADDER_EARLY_STOP_UTIL and nu <= 1.0 + 1e-9
    _log_guidance_ladder_debug(
        ladder_name,
        candidate_label=label,
        candidate_updates=updates,
        decision="accepted",
        reason="improves_deflection_util",
        metric_name="deflection_util",
        metric_before=base_util,
        metric_after=nu,
        early_stop=early,
    )
    return {"label": label, "updates": updates, "util_after": nu, "early_stop": early}


def _deflection_ladder_sustained_load_updates(state: dict) -> dict | None:
    for key in ("g_udl_kNm_per_m", "g_kNm", "g_line_kNm"):
        v = _float_from_state(state, key, 0.0)
        if v > 1e-9:
            return {key: float(v * 0.92)}
    return None


def _pick_deflection_ladder_first_improvement(state: dict, *, base_util: float) -> dict | None:
    ladder_name = "deflection_ladder"
    for d in GUIDANCE_GEOMETRY_TRIAL_DELTAS_MM:
        payload = {"delta_mm": float(d)}
        u = _guidance_action_updates("increase_depth", payload, state=state)
        label = f"Increase depth D by {int(d)} mm"
        r = _try_deflection_ladder_candidate(
            state,
            label=label,
            updates=u,
            base_util=base_util,
            ladder_name=ladder_name,
        )
        if r:
            r["kind"] = "geometry"
            r["action_type"] = "increase_depth"
            r["payload"] = payload
            r["before_after"] = _describe_guidance_step(
                state,
                _merge_guidance_state(state, u),
                "increase_depth",
                u,
            )
            return r

    for d in GUIDANCE_GEOMETRY_TRIAL_DELTAS_MM:
        payload = {"delta_mm": float(d)}
        u = _guidance_action_updates("increase_width", payload, state=state)
        label = f"Increase section width by {int(d)} mm"
        r = _try_deflection_ladder_candidate(
            state,
            label=label,
            updates=u,
            base_util=base_util,
            ladder_name=ladder_name,
        )
        if r:
            r["kind"] = "geometry"
            r["action_type"] = "increase_width"
            r["payload"] = payload
            r["before_after"] = _describe_guidance_step(
                state,
                _merge_guidance_state(state, u),
                "increase_width",
                u,
            )
            return r

    lu = _deflection_ladder_sustained_load_updates(state)
    r = _try_deflection_ladder_candidate(
        state,
        label="Reduce sustained dead load (one small step, ~8%)",
        updates=lu,
        base_util=base_util,
        ladder_name=ladder_name,
    )
    if r:
        r["kind"] = "sustained_load"
        r["before_after"] = _describe_guidance_step(
            state,
            _merge_guidance_state(state, lu),
            "deflection_reduce_sustained_load",
            lu,
        )
        return r

    return None


def _bending_near_limit_specific_title(goal: str, action_type: str) -> str | None:
    _ = goal
    if action_type == "increase_width":
        return "Increase width slightly for bending"
    if action_type == "increase_depth":
        return "Increase depth slightly for bending"
    if action_type == "apply_bottom_recommendation":
        return "Adjust bottom reinforcement for bending"
    return None


def _bending_item_from_geometry_trial(
    state: dict,
    *,
    title: str,
    status: str,
    util: float | None,
    bending_mode: str,
    secondary: str,
    levers: str,
    ladder_name: str = "bending_geometry_trials",
) -> dict | None:
    if util is None:
        return None
    g = _choose_geometry_trial_for_metric(
        state,
        metric="bending",
        baseline_util=float(util),
        bending_mode=bending_mode,
        ladder_name=ladder_name,
    )
    if not g:
        return None
    u_after = float(g.get("util_after", 0.0) or 0.0)
    reasoning = (
        f"Why: flexural demand is high. The suggested geometry step ({g['label']}) targets bending utilisation "
        f"from {float(util):.2f} toward {u_after:.2f}."
    )
    chosen_title = _geometry_trial_title_for_choice(title, g, state)
    g_upd = dict(g.get("updates") or {})
    clines = _guidance_change_lines_for_updates(state, g_upd)
    return _guidance_item(
        "bending",
        chosen_title,
        str(g.get("label") or "Apply geometry trial"),
        secondary,
        reasoning,
        levers,
        str(g.get("action_type") or "increase_depth"),
        dict(g.get("payload") or {}),
        status=status,
        util=util,
        guidance_before_after=str(g.get("before_after") or "") or None,
        guidance_change_lines=clines or None,
    )


def _shear_item_from_geometry_trials(
    state: dict,
    *,
    title: str,
    status: str,
    util: float | None,
    secondary: str,
    reasoning_fallback: str,
    levers: str,
    default_depth_delta: float,
    branch: str,
    _emit,
):
    if util is None:
        return None
    g = _choose_geometry_trial_for_metric(
        state,
        metric="shear",
        baseline_util=float(util),
        ladder_name="shear_geometry_trials",
    )
    if g:
        reasoning = (
            f"Why: width/depth trial chooser picked {g['label'].lower()} "
            f"(shear utilisation {float(util):.2f} → {float(g.get('util_after', 0.0) or 0.0):.2f})."
        )
        s_cl = _guidance_change_lines_for_updates(state, dict(g.get("updates") or {}))
        item = _guidance_item(
            "shear",
            _geometry_trial_title_for_choice(title, g, state),
            g["label"],
            secondary,
            reasoning,
            levers,
            str(g.get("action_type") or "increase_depth"),
            dict(g.get("payload") or {}),
            status=status,
            util=util,
            guidance_before_after=str(g.get("before_after") or "") or None,
            guidance_change_lines=s_cl or None,
        )
        return _emit(
            item,
            branch=branch,
            proposed_updates=dict(g.get("updates") or {}),
            expected_util_after=float(g.get("util_after", 0.0) or 0.0),
        )
    depth_payload = {"delta_mm": float(default_depth_delta)}
    depth_updates = _guidance_action_updates("increase_depth", depth_payload, state=state)
    if depth_updates and not _updates_match_state(state, depth_updates):
        item = _guidance_item(
            "shear",
            title,
            f"Increase depth D by ~{int(default_depth_delta)} mm",
            secondary,
            reasoning_fallback,
            levers,
            "increase_depth",
            depth_payload,
            status=status,
            util=util,
        )
        return _emit(item, branch=f"{branch}:depth_fallback_heuristic", proposed_updates=depth_updates)
    return None


def _bending_guidance_item(state: dict, pack: dict) -> dict | None:
    goal = _design_optimisation_goal(state)
    bottom_recommendation_available = (
        _reinforcement_options_remain(state)
        if goal in ("balanced", "shallower_beam")
        else False
    )
    rows = pack.get("rows") or []
    util = _parse_util_value(pack.get("summary_util"))
    status, _ = _overall_status_from_rows(rows)
    flexural_row = next((row for row in rows if str(row.get("title")) == "Flexural strength capacity"), None)
    ductility_row = next((row for row in rows if str(row.get("title")) == "Ductility limit"), None)
    flexural_status = str((flexural_row or {}).get("status") or "")
    ductility_status = str((ductility_row or {}).get("status") or "")
    flexural_util = _parse_util_value((flexural_row or {}).get("util"))
    ductility_util = _parse_util_value((ductility_row or {}).get("util"))
    bucket = _guidance_bucket(status, util)
    ductility_bucket = _guidance_bucket(ductility_status, ductility_util)
    flexural_bucket = _guidance_bucket(flexural_status, flexural_util)
    if ductility_bucket == "fail" and flexural_bucket != "fail":
        if bottom_recommendation_available:
            return _guidance_item(
                "bending",
                "Ductility limit governs",
                "Preferred fix: reduce bottom tensile ratio",
                "Alternative: increase beam width b",
                "Why: a lighter or cleaner bottom layout reduces neutral axis ratio before resorting to heavier geometry.",
                "Key levers: bottom reinforcement ratio, row layout, b, D",
                "apply_bottom_recommendation",
                {},
                status=ductility_status or status,
                util=ductility_util,
            )
        geo_item = _bending_item_from_geometry_trial(
            state,
            title="Ductility limit governs",
            status=ductility_status or status,
            util=ductility_util,
            bending_mode="ductility",
            secondary="Alternative: reduce bottom tensile steel if the layout allows",
            levers="Key levers: b, D, tensile reinforcement ratio",
        )
        if geo_item:
            return geo_item
        return _guidance_item(
            "bending",
            "Ductility limit governs",
            "Preferred fix: increase beam width b",
            "Fallback fix: increase depth D",
            "Why: width improves section balance more gently than inflating depth first when ductility governs.",
            "Key levers: b, D, tensile reinforcement ratio",
            "increase_width",
            {"delta_mm": 50},
            status=ductility_status or status,
            util=ductility_util,
        )
    if ductility_bucket == "warn" and flexural_bucket == "pass":
        if bottom_recommendation_available:
            return _guidance_item(
                "bending",
                "Ductility limit is close to the limit",
                "Preferred fix: reduce bottom tensile ratio slightly",
                "Alternative: increase beam width b",
                "Why: a lighter bottom layout usually adds ductility reserve more efficiently than growing depth.",
                "Key levers: bottom reinforcement ratio, row layout, b, D",
                "apply_bottom_recommendation",
                {},
                status=ductility_status or status,
                util=ductility_util,
            )
        geo_item = _bending_item_from_geometry_trial(
            state,
            title="Ductility limit is close to the limit",
            status=ductility_status or status,
            util=ductility_util,
            bending_mode="ductility",
            secondary="Alternative: reduce bottom tensile steel slightly if practical",
            levers="Key levers: b, D, tensile reinforcement ratio",
        )
        if geo_item:
            return geo_item
        return _guidance_item(
            "bending",
            "Ductility limit is close to the limit",
            "Preferred fix: increase beam width b",
            "Fallback fix: increase depth D",
            "Why: width is the gentler geometry lever for improving section balance when ductility is near the limit.",
            "Key levers: b, D, tensile reinforcement ratio",
            "increase_width",
            {"delta_mm": 50},
            status=ductility_status or status,
            util=ductility_util,
        )
    if bucket == "fail":
        if goal == "shallower_beam":
            if bottom_recommendation_available:
                return _guidance_item(
                    "bending",
                    "Increase bottom reinforcement",
                    "Add bottom reinforcement",
                    "Alternative: widen the section, then increase depth if needed",
                    "Why: flexural demand exceeds capacity. Adding bottom steel raises bending capacity while keeping depth unchanged.",
                    "Key levers: bottom reinforcement, b, D",
                    "apply_bottom_recommendation",
                    {},
                    status=status,
                    util=util,
                )
            geo_item = _bending_item_from_geometry_trial(
                state,
                title="Adjust section width or depth",
                status=status,
                util=util,
                bending_mode="governing",
                secondary="Alternative: add bottom reinforcement if not yet tried",
                levers="Key levers: b, D, bottom reinforcement",
            )
            if geo_item:
                return geo_item
            return _guidance_item(
                "bending",
                "Increase section width",
                "Increase beam width by ~50 mm",
                "Alternative: increase depth D by ~50–100 mm",
                "Why: bottom reinforcement cannot be increased practically; widening is usually the shallower lever before depth.",
                "Key levers: b, D, bottom reinforcement",
                "increase_width",
                {"delta_mm": 50},
                status=status,
                util=util,
            )
        if goal == "less_longitudinal_reinforcement":
            geo_item = _bending_item_from_geometry_trial(
                state,
                title="Increase depth or width for bending",
                status=status,
                util=util,
                bending_mode="governing",
                secondary="Alternative: increase depth first to cut bottom steel demand before widening",
                levers="Key levers: D, b, bottom reinforcement",
            )
            if geo_item:
                return geo_item
            return _guidance_item(
                "bending",
                "Increase depth to reduce steel demand",
                "Increase depth D by ~50-100 mm",
                "Alternative: increase beam width b",
                "Why: a deeper section increases lever arm and reduces required bottom steel for the same moment.",
                "Key levers: D, b, bottom reinforcement",
                "increase_depth",
                {"delta_mm": 100},
                status=status,
                util=util,
            )
        if bottom_recommendation_available:
            return _guidance_item(
                "bending",
                "Increase bottom reinforcement",
                "Add bottom reinforcement",
                "Alternative: increase depth D by ~50-100 mm",
                "Why: flexural demand exceeds capacity. Use practical reinforcement increases before enlarging the section.",
                "Key levers: bottom reinforcement, row layout, D",
                "apply_bottom_recommendation",
                {},
                status=status,
                util=util,
            )
        geo_item = _bending_item_from_geometry_trial(
            state,
            title="Increase depth or width for bending",
            status=status,
            util=util,
            bending_mode="governing",
            secondary="Alternative: add bottom reinforcement if practical",
            levers="Key levers: D, b, bottom reinforcement",
        )
        if geo_item:
            return geo_item
        return _guidance_item(
            "bending",
            "Increase depth",
            "Increase depth D by ~50-100 mm",
            "Alternative: increase beam width b",
            "Why: reinforcement cannot be increased practically, so section depth is the next lever.",
            "Key levers: D, b, bottom reinforcement",
            "increase_depth",
            {"delta_mm": 100},
            status=status,
            util=util,
        )
    if bucket == "warn":
        if goal == "shallower_beam":
            if bottom_recommendation_available:
                primary = "Add bottom reinforcement"
                secondary = "Alternative: widen the section, then increase depth if needed"
                reasoning = "Why: bending is near its limit. A small steel increase adds capacity before changing depth."
                levers = "Key levers: bottom reinforcement, b, D"
                action_type = "apply_bottom_recommendation"
                action_payload = {}
            else:
                primary = "Increase beam width by ~50 mm"
                secondary = "Alternative: increase depth D by ~25–50 mm"
                reasoning = "Why: bottom steel cannot be increased practically; width is usually the shallower lever than depth."
                levers = "Key levers: b, D, bottom reinforcement"
                action_type = "increase_width"
                action_payload = {"delta_mm": 50}
        elif goal == "less_longitudinal_reinforcement":
            primary = "Increase depth D by ~25-50 mm"
            secondary = "Alternative: increase beam width b"
            reasoning = "Why: a slightly deeper section adds reserve and usually cuts required bottom steel."
            levers = "Key levers: D, b, bottom reinforcement"
            action_type = "increase_depth"
            action_payload = {"delta_mm": 50}
        else:
            if bottom_recommendation_available:
                primary = "Tune bottom reinforcement"
                secondary = "Alternative: increase depth D by ~25-50 mm"
                reasoning = "Why: try a small layout or bar change before enlarging the section."
                levers = "Key levers: bottom reinforcement, row layout, D"
                action_type = "apply_bottom_recommendation"
                action_payload = {}
            else:
                primary = "Increase depth D by ~25-50 mm"
                secondary = "Alternative: increase beam width b"
                reasoning = "Why: reinforcement is already constrained; a modest depth increase is the next reserve lever."
                levers = "Key levers: D, b, bottom reinforcement"
                action_type = "increase_depth"
                action_payload = {"delta_mm": 50}
        use_title = _bending_near_limit_specific_title(goal, action_type) or "Bending is close to the limit"
        _upd = _guidance_action_updates(action_type, action_payload, state=state)
        _cl = _guidance_change_lines_for_updates(state, _upd or {})
        return _guidance_item(
            "bending",
            use_title,
            primary,
            secondary,
            reasoning,
            levers,
            action_type,
            action_payload,
            status=status,
            util=util,
            guidance_change_lines=_cl or None,
        )
    return None


def _shear_spacing_guidance_floor_mm() -> float:
    return float(min(REO_SPACINGS)) if REO_SPACINGS else 75.0


def _next_tighter_link_spacing_updates(state: dict) -> dict | None:
    current = float(_float_from_state(state, "s_lig", 0.0) or 0.0)
    if current <= 0.0 or not REO_SPACINGS:
        return None
    eligible = [float(x) for x in REO_SPACINGS if float(x) < current - 1e-9]
    if not eligible:
        return None
    new_s = max(eligible)
    updates = {"s_lig": new_s}
    if _updates_match_state(state, updates):
        return None
    return updates


def _fallback_shear_reinforcement_step_updates(state: dict) -> dict | None:
    legs = max(_int_from_state(state, "lig_legs", 2), 2)
    dia = max(_int_from_state(state, "lig_d", 10), 10)
    if legs < 8:
        nu = {"lig_legs": int(min(8, legs + 2))}
        if not _updates_match_state(state, nu):
            return nu
    for nd in REO_BAR_DIAS:
        if int(nd) > int(dia) and int(nd) <= 24:
            nu = {"lig_d": int(nd)}
            if not _updates_match_state(state, nu):
                return nu
    return None


def _shear_guidance_item_from_search_rec(*, title: str, rec: dict, util, status: str, state: dict) -> dict:
    candidate_type = str(rec.get("candidate_type") or "")
    if candidate_type == "combined":
        primary = "Combined geometry and reinforcement change required"
        secondary = f"Trial: {rec.get('label') or 'combined fix'}"
        reasoning = "Why: shear demand is severely above capacity, so a combined section and link upgrade is the fastest safe recovery path."
    elif candidate_type in {"depth increase", "width increase"}:
        primary = "Increase section width/depth to recover shear capacity"
        secondary = f"Trial: {rec.get('label') or 'geometry fix'}"
        reasoning = "Why: the current shear failure is too severe for a small link tweak alone, so geometry must compete with reinforcement changes."
    elif candidate_type == "no_shear_design_cleanup":
        primary = "Remove designed shear reinforcement (no ULS shear/torsion demand)"
        secondary = "Optional: nominal construction ties per your specification are outside this strength check."
        reasoning = "Why: resolved shear and torsion are negligible, so strength-designed links are not required here."
    elif candidate_type in {"more legs", "larger dia"}:
        primary = "Increase shear reinforcement significantly"
        secondary = f"Trial: {rec.get('label') or 'stronger links'}"
        reasoning = "Why: a severe shear failure needs a major reinforcement step, not just tighter spacing."
    else:
        primary = "Increase shear reinforcement significantly"
        secondary = f"Trial: {rec.get('label') or 'stronger links'}"
        reasoning = (
            "Why: a searched reinforcement or geometry upgrade is the next actionable step "
            f"(shear utilisation trial {float(util or 0.0):.2f} -> {float(rec.get('util', 0.0) or 0.0):.2f})."
        )
    updates = dict(rec.get("updates") or {})
    ba: str | None = None
    if updates and candidate_type != "no_shear_design_cleanup":
        try:
            after_state = dict(state)
            after_state.update(updates)
            ba = _describe_guidance_step(state, after_state, "apply_shear_recommendation", updates)
        except Exception:
            ba = None
    return _guidance_item(
        "shear",
        title,
        primary,
        secondary,
        reasoning,
        "Key levers: link spacing, no. of legs, link diameter, b, D",
        "apply_shear_recommendation",
        {"updates": updates},
        status=status,
        util=util,
        guidance_before_after=ba,
    )


def _log_shear_top_guidance_recommendation(
    state: dict,
    *,
    branch: str,
    item: dict,
    proposed_updates: dict | None,
    expected_util_after: float | None,
    search_label: str | None,
) -> None:
    if not DEBUG_DESIGN_GUIDANCE_PROBE:
        return
    action_type = item.get("action_type")
    before_after = None
    if action_type:
        try:
            before_after = _guidance_before_after_text(dict(item), state)
        except Exception:
            before_after = None
    _agent_debug_log(
        "Design Guide top shear recommendation",
        {
            "branch": branch,
            "lig_legs": _int_from_state(state, "lig_legs", 0),
            "s_lig": _float_from_state(state, "s_lig", 0.0),
            "action_type": action_type,
            "proposed_updates": proposed_updates or (item.get("action_payload") or {}).get("updates"),
            "proposed_label": search_label or item.get("secondary_action"),
            "before_after_text": before_after,
            "expected_util_after": expected_util_after,
            "title_main": item.get("title_main"),
        },
        location="inputs_page.py:_shear_guidance_item",
        hypothesis_id="H_SHEAR_TOP_GUIDE",
    )


def _shear_no_demand_cleanup_guidance_item_if_needed(state: dict) -> dict | None:
    design_context = _build_design_actions_context(state)
    overview = _collect_design_overview(state, context=design_context)
    actions = design_context.get("actions") or {}
    rec = _try_shear_no_demand_cleanup_recommendation(state, overview, actions)
    if not rec or not rec.get("updates") or _updates_match_state(state, rec["updates"]):
        return None
    return _guidance_item(
        "shear",
        "No shear or torsion design demand",
        "Remove unnecessary shear reinforcement (ULS)",
        "Optional: keep nominal construction ties if required by your specification (outside this shear design check).",
        "Why: resolved shear and torsion are negligible, so designed shear links are not required here.",
        "Key levers: link diameter, number of legs, spacing",
        "apply_shear_recommendation",
        {"updates": rec["updates"]},
        status="PASS",
        util=float(((overview.get("utils") or {}).get("shear", 0.0)) or 0.0),
    )


def _shear_guidance_item(state: dict, pack: dict) -> dict | None:
    goal = _design_optimisation_goal(state)
    rows = pack.get("rows") or []
    util = _parse_util_value(pack.get("summary_util"))
    status, _ = _overall_status_from_rows(rows)
    bucket = _guidance_bucket(status, util)

    def _emit(
        item: dict,
        *,
        branch: str,
        proposed_updates: dict | None = None,
        expected_util_after: float | None = None,
        search_label: str | None = None,
    ) -> dict:
        _log_shear_top_guidance_recommendation(
            state,
            branch=branch,
            item=item,
            proposed_updates=proposed_updates,
            expected_util_after=expected_util_after,
            search_label=search_label,
        )
        return item

    if bucket == "fail":
        search_rec = _compute_shear_recommendation(state)
        if (
            search_rec
            and search_rec.get("updates")
            and not _updates_match_state(state, search_rec["updates"])
        ):
            item = _shear_guidance_item_from_search_rec(
                title="Shear governs",
                rec=search_rec,
                util=util,
                status=status,
                state=state,
            )
            return _emit(
                item,
                branch="fail:search",
                proposed_updates=dict(search_rec.get("updates") or {}),
                expected_util_after=float(search_rec.get("util", 0.0) or 0.0),
                search_label=str(search_rec.get("label") or ""),
            )

        if goal == "less_shear_reinforcement":
            geo_item = _shear_item_from_geometry_trials(
                state,
                title="Shear governs",
                status=status,
                util=util,
                secondary="Alternative: add link legs / diameter if geometry is fixed",
                reasoning_fallback="Why: a deeper section can relieve shear demand and avoid congested links.",
                levers="Key levers: D, link spacing, no. of legs",
                default_depth_delta=100.0,
                branch="fail:less_shear_geom",
                _emit=_emit,
            )
            if geo_item:
                return geo_item

        spacing_updates = _next_tighter_link_spacing_updates(state)
        if spacing_updates:
            item = _guidance_item(
                "shear",
                "Shear governs",
                "Tighten link spacing (next standard increment)",
                f"Trial: {_shear_state_label({**state, **spacing_updates})}",
                "Why: closer stirrup spacing increases shear capacity along the member.",
                "Key levers: link spacing, no. of legs, link diameter",
                "reduce_link_spacing",
                {
                    "updates": spacing_updates,
                    "delta_mm": 50,
                    "minimum_spacing": _shear_spacing_guidance_floor_mm(),
                },
                status=status,
                util=util,
            )
            return _emit(item, branch="fail:spacing_step", proposed_updates=spacing_updates)

        fu = _fallback_shear_reinforcement_step_updates(state)
        if fu:
            trial_state = dict(state)
            trial_state.update(fu)
            item = _guidance_item(
                "shear",
                "Shear governs",
                "Increase link legs or bar diameter",
                f"Trial: {_shear_state_label(trial_state)}",
                "Why: link spacing is already at the minimum spacing used in this guide; stronger stirrups are the next practical step.",
                "Key levers: no. of legs, link diameter, spacing, b, D",
                "apply_shear_recommendation",
                {"updates": fu},
                status=status,
                util=util,
            )
            return _emit(item, branch="fail:fallback_reo", proposed_updates=fu)

        geo_item = _shear_item_from_geometry_trials(
            state,
            title="Shear governs",
            status=status,
            util=util,
            secondary="Alternative: increase link legs / diameter if geometry is fixed",
            reasoning_fallback="Why: spacing and standard link upgrades are exhausted at the current geometry; section size is the next structural lever.",
            levers="Key levers: D, b, link layout",
            default_depth_delta=100.0,
            branch="fail:depth_fallback",
            _emit=_emit,
        )
        if geo_item:
            return geo_item

        return None

    if bucket == "warn":
        search_rec = _compute_shear_recommendation(state)
        if (
            search_rec
            and search_rec.get("updates")
            and not _updates_match_state(state, search_rec["updates"])
        ):
            item = _shear_guidance_item_from_search_rec(
                title="Shear is close to the limit",
                rec=search_rec,
                util=util,
                status=status,
                state=state,
            )
            return _emit(
                item,
                branch="warn:search",
                proposed_updates=dict(search_rec.get("updates") or {}),
                expected_util_after=float(search_rec.get("util", 0.0) or 0.0),
                search_label=str(search_rec.get("label") or ""),
            )

        if goal == "less_shear_reinforcement":
            geo_item = _shear_item_from_geometry_trials(
                state,
                title="Shear is close to the limit",
                status=status,
                util=util,
                secondary="Alternative: add link legs / diameter if geometry is fixed",
                reasoning_fallback="Why: modest depth can add reserve before tightening links.",
                levers="Key levers: D, link spacing, no. of legs",
                default_depth_delta=50.0,
                branch="warn:less_shear_geom",
                _emit=_emit,
            )
            if geo_item:
                return geo_item

        spacing_updates = _next_tighter_link_spacing_updates(state)
        if spacing_updates:
            item = _guidance_item(
                "shear",
                "Shear is close to the limit",
                "Tighten link spacing (next standard increment)",
                f"Trial: {_shear_state_label({**state, **spacing_updates})}",
                "Why: closer stirrup spacing adds reserve while keeping the beam shallow.",
                "Key levers: link spacing, no. of legs, link diameter",
                "reduce_link_spacing",
                {
                    "updates": spacing_updates,
                    "delta_mm": 25,
                    "minimum_spacing": _shear_spacing_guidance_floor_mm(),
                },
                status=status,
                util=util,
            )
            return _emit(item, branch="warn:spacing_step", proposed_updates=spacing_updates)

        fu = _fallback_shear_reinforcement_step_updates(state)
        if fu:
            trial_state = dict(state)
            trial_state.update(fu)
            item = _guidance_item(
                "shear",
                "Shear is close to the limit",
                "Increase link legs or bar diameter",
                f"Trial: {_shear_state_label(trial_state)}",
                "Why: link spacing is already at the minimum spacing used in this guide; stronger stirrups add reserve.",
                "Key levers: no. of legs, link diameter, spacing, b, D",
                "apply_shear_recommendation",
                {"updates": fu},
                status=status,
                util=util,
            )
            return _emit(item, branch="warn:fallback_reo", proposed_updates=fu)

        geo_item = _shear_item_from_geometry_trials(
            state,
            title="Shear is close to the limit",
            status=status,
            util=util,
            secondary="Alternative: increase link legs / diameter if geometry is fixed",
            reasoning_fallback="Why: link spacing is at the practical minimum in this guide; section size adds capacity without further congestion.",
            levers="Key levers: D, b, link layout",
            default_depth_delta=50.0,
            branch="warn:depth_fallback",
            _emit=_emit,
        )
        if geo_item:
            return geo_item

        return None

    cleanup_gi = _shear_no_demand_cleanup_guidance_item_if_needed(state)
    if cleanup_gi is not None:
        return cleanup_gi
    return None


def _crack_guidance_item(state: dict, pack: dict) -> dict | None:
    rows = pack.get("rows") or []
    util_candidates = [_parse_util_value(r.get("util")) for r in rows]
    util_values = [u for u in util_candidates if u is not None]
    util = max(util_values) if util_values else None
    status, _ = _overall_status_from_rows(rows)
    bucket = _guidance_bucket(status, util)
    if bucket not in ("fail", "warn"):
        return None
    base = _evaluate_crack_with_state(state)
    if not base:
        return None
    base_u = float(base.get("util", 0.0) or 0.0)
    picked = _pick_crack_ladder_first_improvement(state, base_util=base_u)
    if not picked:
        return None
    u_after = float(picked.get("util_after", 0.0) or 0.0)
    kind = str(picked.get("kind") or "")
    is_fail = bucket == "fail"
    title = "Crack control is failing" if is_fail else "Crack control is close to the limit"
    secondary = "Alternative: review cover and exposure inputs on the Crack page."
    levers = "Key levers: bar spacing, bar count, layout, cover, b, D"
    if kind == "geometry":
        reasoning = (
            f"Why: crack ladder — reinforcement and layout first, then best geometry trial (utilisation {util:.2f} → {u_after:.2f})."
            if util is not None
            else f"Why: geometry trial improves crack utilisation to {u_after:.2f}."
        )
        return _guidance_item(
            "crack",
            title,
            str(picked.get("label") or "Increase section size"),
            secondary,
            reasoning,
            levers,
            str(picked.get("action_type") or "increase_depth"),
            dict(picked.get("payload") or {}),
            status=status,
            util=util,
            guidance_before_after=str(picked.get("before_after") or "") or None,
        )
    updates = dict(picked.get("updates") or {})
    after_st = _merge_guidance_state(state, updates)
    ba = _describe_guidance_step(state, after_st, "reduce_bar_spacing", updates)
    reasoning = (
        f"Why: crack ladder — spacing, bar count, then crack-efficient layout before geometry ({util:.2f} → {u_after:.2f})."
        if util is not None
        else f"Why: crack-control ladder step ({u_after:.2f})."
    )
    return _guidance_item(
        "crack",
        title,
        str(picked.get("label") or "Adjust bottom reinforcement"),
        secondary,
        reasoning,
        levers,
        "reduce_bar_spacing",
        {"updates": updates, "delta_mm": 25.0, "minimum_spacing": float(min(REO_SPACINGS))},
        status=status,
        util=util,
        guidance_before_after=ba or None,
    )


def _deflection_guidance_item(state: dict, pack: dict) -> dict | None:
    rows = pack.get("rows") or []
    util = _parse_util_value(pack.get("summary_util_total"))
    status, _ = _overall_status_from_rows(rows)
    bucket = _guidance_bucket(status, util)
    if bucket not in ("fail", "warn"):
        return None
    base = _evaluate_deflection_with_state(state)
    if not base or base.get("util") is None:
        return None
    base_u = float(base["util"])
    picked = _pick_deflection_ladder_first_improvement(state, base_util=base_u)
    if not picked:
        return None
    u_after = float(picked.get("util_after", 0.0) or 0.0)
    kind = str(picked.get("kind") or "")
    span_note = " Advisory only: a shorter effective span L_eff also reduces deflection (not applied automatically)."
    is_fail = bucket == "fail"
    title = "Deflection is high" if is_fail else "Deflection is close to the limit"
    levers = "Key levers: D, b, sustained loads, span (advisory)"
    secondary = "Alternative: review deflection inputs on the Deflection page." + span_note
    if kind == "sustained_load":
        reasoning = (
            f"Why: deflection ladder — depth and width trials first; then one small sustained-load step ({util:.2f} → {u_after:.2f})."
            if util is not None
            else f"Why: sustained-load adjustment ({u_after:.2f})."
        )
        return _guidance_item(
            "deflection",
            title,
            str(picked.get("label") or "Reduce sustained load slightly"),
            secondary,
            reasoning,
            levers,
            "deflection_reduce_sustained_load",
            {"updates": dict(picked.get("updates") or {})},
            status=status,
            util=util,
            guidance_before_after=str(picked.get("before_after") or "") or None,
        )
    reasoning = (
        f"Why: deflection ladder — depth, then width if it helps stiffness, before load tweaks ({util:.2f} → {u_after:.2f})."
        if util is not None
        else f"Why: geometry step ({u_after:.2f})."
    )
    return _guidance_item(
        "deflection",
        title,
        str(picked.get("label") or "Increase depth"),
        secondary,
        reasoning + span_note,
        levers,
        str(picked.get("action_type") or "increase_depth"),
        dict(picked.get("payload") or {}),
        status=status,
        util=util,
        guidance_before_after=str(picked.get("before_after") or "") or None,
    )


def _one_click_candidate_payload_signature(updates: dict) -> tuple:
    sig: list[tuple[str, object]] = []
    for k in sorted((updates or {}).keys()):
        v = updates.get(k)
        if isinstance(v, float):
            sig.append((k, round(float(v), 6)))
        else:
            sig.append((k, v))
    return tuple(sig)


def _guidance_item_from_selected_candidate(
    candidate: dict,
    *,
    guidance_state: dict,
    overview: dict,
    title: str,
    action_type: str,
    updates: dict,
    action_payload: dict,
    reasoning: str,
    change_lines: list[str] | None = None,
    family_tag: str | None = None,
    subfamilies: list[str] | None = None,
) -> dict:
    item = _guidance_item(
        str(_governing_focus_from_overview(overview) or "bending"),
        title,
        title,
        None,
        reasoning,
        "Key levers: geometry and reinforcement updates selected by one-click convergence ranking",
        str(action_type),
        dict(action_payload),
        status=str((overview.get("statuses") or {}).get("bending") or "FAIL"),
        util=overview.get("worst_util"),
        guidance_change_lines=(change_lines or None),
    )
    resolved_updates = dict(updates or {})
    item["resolved_candidate_label"] = str(title)
    item["resolved_candidate_action_type"] = str(action_type)
    item["resolved_candidate_updates"] = resolved_updates
    item["resolved_candidate_family_tag"] = family_tag
    item["resolved_candidate_subfamilies"] = list(subfamilies or [])
    item["resolved_candidate_post_util"] = candidate.get("candidate_post_util")
    item["resolved_candidate_reaches_target_band"] = bool(candidate.get("candidate_reaches_target_band"))
    return item


def _guidance_item_from_resolved_candidate(
    candidate: dict,
    *,
    state: dict,
    overview: dict,
    title: str | None = None,
    reasoning: str | None = None,
    status: str = "FAIL",
    primary_action: str = "Apply recommendation",
) -> dict:
    if not isinstance(candidate, dict):
        return {}
    updates = dict(candidate.get("updates") or {})
    if not updates:
        return {}

    raw_label = str(candidate.get("label") or title or "Apply recommendation").strip()
    label = raw_label
    vague_title_needles = (
        "coordinated bending upgrade",
        "bending governs",
        "adjust section geometry",
        "apply one-click",
        "apply recommendation",
    )
    if any(n in label.lower() for n in vague_title_needles):
        inferred_subfamilies = _compound_subfamilies_from_updates(updates)
        inferred_title, _, _ = _compound_guidance_title_reasoning_why(
            state,
            updates,
            inferred_subfamilies,
            strengthening=True,
        )
        if str(inferred_title or "").strip():
            label = str(inferred_title).strip()
    family_tag = (
        candidate.get("recommendation_family_tag")
        or candidate.get("family_tag")
        or candidate.get("family")
        or "resolved_candidate"
    )
    subfamilies = list(candidate.get("subfamilies") or []) if isinstance(candidate.get("subfamilies"), list) else []
    alternatives_text = str(
        candidate.get("guidance_alternatives_text_compact")
        or _guidance_default_alternatives_text(state, updates, subfamilies)
        or "",
    ).strip()

    change_lines = list(
        candidate.get("guidance_change_lines")
        or candidate.get("recommendation_change_lines")
        or _guidance_change_lines_for_updates(state, updates)
        or []
    )

    candidate_post_util = candidate.get("worst_util")
    try:
        candidate_post_util = float(candidate_post_util) if candidate_post_util is not None else None
    except Exception:
        candidate_post_util = None

    resolved_action_type = "apply_resolved_candidate"
    original_candidate_action_type = str(
        candidate.get("action_type")
        or candidate.get("resolved_candidate_action_type")
        or "apply_compound_guidance"
    )

    action_payload = {
        "resolved_candidate_updates": updates,
        "resolved_candidate_label": label,
        "resolved_candidate_action_type": original_candidate_action_type,
        "resolved_candidate_family_tag": family_tag,
        "resolved_candidate_subfamilies": subfamilies,
        "resolved_candidate_post_util": candidate_post_util,
        "resolved_candidate_reaches_target_band": bool(
            candidate.get("candidate_reaches_target_band") or candidate.get("reaches_target_band")
        ),
        "force_direct_apply": True,
        "label": label,
        "updates": updates,
        "guidance_change_lines": change_lines,
        "guidance_change_summary_compact": _guidance_compact_change_text(change_lines),
        "guidance_expected_util_text": _guidance_expected_util_text(candidate_post_util),
        "guidance_why_text_compact": _guidance_compact_why_text(
            {
                "reasoning": reasoning or str(candidate.get("reasoning") or ""),
                "action_payload": {},
            },
        ),
        "guidance_alternatives_text_compact": alternatives_text,
    }

    item = _guidance_item(
        "general",
        label,
        primary_action,
        None,
        reasoning or str(candidate.get("reasoning") or "This option brings the design into the target range in one move."),
        "Key levers: geometry and reinforcement updates selected by one-click convergence ranking",
        resolved_action_type,
        action_payload,
        status=status,
        util=overview.get("worst_util"),
        guidance_change_lines=change_lines,
        guidance_before_after=_guidance_before_after_text(
            {
                "action_type": resolved_action_type,
                "action_payload": action_payload,
                "recommendation_change_lines": change_lines,
            },
            state,
        ),
    )

    # Optional duplicated top-level mirrors for easier debugging only.
    item["resolved_candidate_label"] = label
    item["resolved_candidate_action_type"] = original_candidate_action_type
    item["resolved_candidate_family_tag"] = family_tag
    item["resolved_candidate_subfamilies"] = subfamilies
    item["resolved_candidate_updates"] = updates

    return item


def _get_one_click_band_reaching_candidate(
    guidance_state: dict,
    overview: dict,
    *,
    mode_config: dict,
    primary_hint: dict | None = None,
    debug_extra: dict | None = None,
) -> dict | None:
    if isinstance(debug_extra, dict):
        debug_extra["one_click_critical_candidate_exists"] = False
        debug_extra["one_click_critical_candidate_label"] = None
        debug_extra["one_click_critical_candidate_action_type"] = None
        debug_extra["one_click_critical_candidate_post_util"] = None
        debug_extra["one_click_critical_candidate_reaches_target_band"] = False
        debug_extra["one_click_critical_candidate_surfaced"] = False
        debug_extra["one_click_critical_candidate_suppressed_reason"] = "not_checked"
        debug_extra["critical_branch_used_one_click_override"] = False

    seed_candidate = evaluate_candidate_full(
        _guidance_state_snapshot(guidance_state),
        source="one_click_critical_seed",
    )
    if not seed_candidate:
        if isinstance(debug_extra, dict):
            debug_extra["one_click_critical_candidate_suppressed_reason"] = "seed_eval_failed"
        return None
    overview_in_band = bool(overview.get("all_key_pass")) and _is_in_target_zone_with_eps(
        overview,
        mode_config,
        eps=TARGET_BAND_EPS,
    )
    if overview_in_band:
        if isinstance(debug_extra, dict):
            debug_extra["one_click_critical_candidate_suppressed_reason"] = "already_in_target_band"
        return None

    option_specs: list[dict] = []

    def _add_option(
        *,
        updates: dict | None,
        action_type: str,
        payload: dict,
        label: str,
        source: str,
        family_tag: str | None = None,
        subfamilies: list[str] | None = None,
    ) -> None:
        u = dict(updates or {})
        if not u or _updates_match_state(guidance_state, u):
            return
        if not _candidate_is_materially_actionable(guidance_state, u):
            return
        option_specs.append(
            {
                "updates": u,
                "action_type": str(action_type),
                "payload": dict(payload),
                "label": str(label or "").strip() or "Apply one-click recommendation",
                "source": str(source),
                "family_tag": family_tag,
                "subfamilies": list(subfamilies or []),
            },
        )

    if isinstance(primary_hint, dict):
        at = str(primary_hint.get("action_type") or "")
        if at:
            hint_payload = dict(primary_hint.get("action_payload") or {})
            hint_updates = _guidance_action_updates(at, hint_payload, state=guidance_state)
            _add_option(
                updates=hint_updates,
                action_type=at,
                payload=hint_payload,
                label=str(primary_hint.get("primary_action") or primary_hint.get("title_main") or at),
                source="primary_hint",
            )

    bottom_rec = _compute_bottom_reo_recommendation(guidance_state)
    if isinstance(bottom_rec, dict):
        bu = dict(bottom_rec.get("updates") or {})
        if bu:
            is_compound = bool(bottom_rec.get("recommendation_compound"))
            rec_title = str(
                bottom_rec.get("guidance_recommendation_title")
                or bottom_rec.get("label")
                or "Apply bottom recommendation"
            )
            _add_option(
                updates=bu,
                action_type="apply_compound_guidance" if is_compound else "apply_bottom_recommendation",
                payload={
                    "updates": bu,
                    "guidance_banner_title": rec_title,
                    "label": rec_title,
                },
                label=rec_title,
                source="bottom_recommendation",
                family_tag=str(bottom_rec.get("recommendation_family_tag") or ""),
                subfamilies=list(bottom_rec.get("subfamilies") or []) if isinstance(bottom_rec.get("subfamilies"), list) else [],
            )

    geom_rec = _compute_geometry_recommendation(guidance_state)
    if isinstance(geom_rec, dict):
        gu = dict(geom_rec.get("updates") or {})
        if gu:
            g_label = str(geom_rec.get("label") or "Apply geometry recommendation")
            _add_option(
                updates=gu,
                action_type="apply_geometry_recommendation",
                payload={"updates": gu, "label": g_label},
                label=g_label,
                source="geometry_recommendation",
            )

    shear_rec = _compute_shear_recommendation(guidance_state)
    if isinstance(shear_rec, dict):
        su = dict(shear_rec.get("updates") or {})
        if su:
            s_label = str(shear_rec.get("label") or "Apply shear recommendation")
            _add_option(
                updates=su,
                action_type="apply_shear_recommendation",
                payload={"updates": su, "label": s_label},
                label=s_label,
                source="shear_recommendation",
            )

    if not option_specs:
        if isinstance(debug_extra, dict):
            debug_extra["one_click_critical_candidate_suppressed_reason"] = "no_actionable_options"
        return None

    uniq: dict[tuple, dict] = {}
    for spec in option_specs:
        sig = _one_click_candidate_payload_signature(spec.get("updates") or {})
        uniq[sig] = spec
    option_specs = list(uniq.values())

    candidates: list[dict] = []
    for idx, spec in enumerate(option_specs):
        cand = _evaluate_auto_design_candidate(
            guidance_state,
            updates=dict(spec.get("updates") or {}),
            source=f"one_click_critical_option_{idx}",
            label=str(spec.get("label") or "one_click_option"),
            action_type=str(spec.get("action_type") or ""),
        )
        if not cand:
            continue
        cand["_one_click_spec"] = spec
        candidates.append(cand)
    if not candidates:
        if isinstance(debug_extra, dict):
            debug_extra["one_click_critical_candidate_suppressed_reason"] = "candidate_eval_failed"
        return None

    winner = _select_best_auto_design_candidate(candidates, mode_config, seed_candidate)
    if not winner:
        if isinstance(debug_extra, dict):
            debug_extra["one_click_critical_candidate_suppressed_reason"] = "no_selector_winner"
        return None
    if not (bool(winner.get("is_compliant")) and bool(winner.get("candidate_reaches_target_band"))):
        if isinstance(debug_extra, dict):
            debug_extra["one_click_critical_candidate_suppressed_reason"] = "selector_winner_not_band_reacher"
        return None
    spec = dict(winner.get("_one_click_spec") or {})
    updates = dict(spec.get("updates") or {})
    if _updates_match_state(guidance_state, updates):
        if isinstance(debug_extra, dict):
            debug_extra["one_click_critical_candidate_suppressed_reason"] = "winner_noop_updates"
        return None

    title = str(spec.get("label") or winner.get("label") or "Apply one-click recommendation")
    action_type = str(spec.get("action_type") or winner.get("action_type") or "apply_compound_guidance")
    clines = _guidance_change_lines_for_updates(guidance_state, updates)
    post_util = float(winner.get("candidate_post_util", 0.0) or 0.0)
    cur_util = float(seed_candidate.get("worst_util", 0.0) or 0.0)
    resolved_candidate = dict(winner)
    resolved_candidate["label"] = title
    resolved_candidate["action_type"] = action_type
    resolved_candidate["updates"] = dict(updates)
    resolved_candidate["recommendation_family_tag"] = spec.get("family_tag")
    resolved_candidate["subfamilies"] = list(spec.get("subfamilies") or [])
    resolved_candidate["candidate_reaches_target_band"] = bool(winner.get("candidate_reaches_target_band"))
    resolved_candidate["worst_util"] = winner.get("candidate_post_util")
    resolved_candidate["recommendation_change_lines"] = clines or []
    item = _guidance_item_from_resolved_candidate(
        resolved_candidate,
        state=guidance_state,
        overview=overview,
        title=title,
        reasoning=f"Why: this option reaches the target band in one move ({cur_util:.2f} → {post_util:.2f}).",
        status="FAIL",
        primary_action="Apply recommendation",
    )
    if isinstance(debug_extra, dict):
        debug_extra["one_click_critical_candidate_exists"] = True
        debug_extra["one_click_critical_candidate_label"] = title
        debug_extra["one_click_critical_candidate_action_type"] = "apply_resolved_candidate"
        debug_extra["one_click_critical_candidate_post_util"] = post_util
        debug_extra["one_click_critical_candidate_reaches_target_band"] = bool(winner.get("candidate_reaches_target_band"))
        debug_extra["one_click_critical_candidate_suppressed_reason"] = None
    return item


def _enumerate_bottom_reo_design_trials(state: dict, *, mode_config: dict | None = None) -> list[dict]:
    if not isinstance(state, dict):
        return []
    cfg = dict(mode_config or _design_mode_config(_design_optimisation_goal(state)))
    layout_cache: dict = {}
    arrangements = _generate_local_bottom_arrangements(
        state,
        cfg,
        band=2,
        context={"layout_fit_cache": layout_cache},
        limit=12,
    )
    # Include a bounded set of stronger practical layouts so severe starter
    # states (e.g. 200x300 with light reo) can still discover one-click winners.
    stronger_specs = [
        (2, 2, 20),
        (2, 2, 24),
        (2, 2, 28),
        (3, 3, 20),
        (3, 3, 24),
        (3, 3, 28),
        (4, 4, 24),
        (4, 4, 28),
        (6, 0, 24),
        (8, 0, 24),
        (6, 0, 28),
        (8, 0, 28),
    ]
    seen_signatures = {
        (
            int((a or {}).get("bot1_count", 0) or 0),
            int((a or {}).get("bot2_count", 0) or 0),
            int((a or {}).get("db_bot_1", 0) or 0),
        )
        for a in arrangements
    }
    for c1, c2, dia in stronger_specs:
        arr = _normalise_bottom_layer_order(
            {
                "bot1_layout_mode": "Count",
                "bot1_count": int(c1),
                "db_bot_1": int(dia),
                "bot2_layout_mode": "Count",
                "bot2_count": int(c2),
                "db_bot_2": int(dia),
            },
        )
        sig = (
            int(arr.get("bot1_count", 0) or 0),
            int(arr.get("bot2_count", 0) or 0),
            int(arr.get("db_bot_1", 0) or 0),
        )
        if sig in seen_signatures:
            continue
        if not _arrangement_fits_state(state, arr, layout_cache=layout_cache):
            continue
        arrangements.append(arr)
        seen_signatures.add(sig)
    out: list[dict] = []
    for arrangement in arrangements:
        arr = dict(arrangement or {})
        updates = _bottom_arrangement_to_shared_updates(arr)
        if not isinstance(updates, dict):
            continue
        out.append(
            {
                "label": _practical_bottom_reo_label(
                    int(arr.get("bot1_count", 0) or 0),
                    int(arr.get("bot2_count", 0) or 0),
                    int(arr.get("db_bot_1", 0) or 0),
                ),
                "updates": updates,
                "arrangement": arr,
            },
        )
    return out


def _solve_one_click_candidate(
    state: dict,
    *,
    goal: str | None = None,
    expanded: bool = False,
) -> dict | None:
    """
    Bounded one-click solver:
    - searches a practical space of geometry + bottom reinforcement combinations
    - returns the best compliant candidate near the target band
    - returns None if no compliant candidate exists in the bounded search space

    Uses a small geometry grid first; if no in-band compliant candidate is found, reruns with
    the full grid (expanded=True) to match the legacy search breadth.
    """
    if not isinstance(state, dict):
        return None

    goal_name = str(goal or _design_optimisation_goal(state) or "balanced")
    mode_cfg = _design_mode_config(goal_name)
    target_min = float(mode_cfg.get("target_util_min", EFFICIENCY_TARGET_UTIL_MIN) or EFFICIENCY_TARGET_UTIL_MIN)
    target_max = float(mode_cfg.get("target_util_max", EFFICIENCY_TARGET_UTIL_MAX) or EFFICIENCY_TARGET_UTIL_MAX)
    width_key, _, base_width = _resolve_geometry_width_context(state)
    base_width = float(base_width or 0.0)
    base_depth = float(_float_from_state(state, "D", 0.0) or 0.0)

    width_steps_full = [0.0, 25.0, 50.0, 75.0, 100.0, 125.0, 150.0]
    depth_steps_full = [0.0, 25.0, 50.0, 75.0, 100.0, 125.0, 150.0]
    width_steps_small = [0.0, 25.0, 50.0]
    depth_steps_small = [0.0, 25.0, 50.0, 75.0]

    def _distance_to_band(util: float) -> float:
        if util < target_min:
            return target_min - util
        if util > target_max:
            return util - target_max
        return 0.0

    def _goal_key(c: dict) -> tuple:
        post_util = float(c.get("candidate_post_util", c.get("worst_util", 999.0)) or 999.0)
        trial_state = dict(state)
        trial_state.update(dict(c.get("updates") or {}))
        delta_b = float((float(_design_width_value(trial_state) or base_width)) - base_width)
        delta_D = float(_float_from_state(trial_state, "D", base_depth) - base_depth)
        ast_bot = c.get("Ast_bot")
        try:
            ast_bot = float(ast_bot) if ast_bot is not None else 0.0
        except Exception:
            ast_bot = 0.0
        if goal_name == "shallower_beam":
            return (
                0 if bool(c.get("candidate_reaches_target_band")) else 1,
                _distance_to_band(post_util),
                delta_D,
                delta_b,
                ast_bot,
                post_util,
            )
        return (
            0 if bool(c.get("candidate_reaches_target_band")) else 1,
            _distance_to_band(post_util),
            abs(post_util - 0.875),
            delta_b + delta_D,
            ast_bot,
            post_util,
        )

    def _run_pass(width_steps: list[float], depth_steps: list[float]) -> tuple[list[dict], int, int, float | None, list[int], dict[float, list[dict]]]:
        compliant_candidates: list[dict] = []
        explored_candidates = 0
        skipped_invalid = 0
        best_noncompliant_worst_util = None
        bottom_trial_cache: dict[float, list[dict]] = {}
        observed_bottom_trial_counts: list[int] = []

        for db in width_steps:
            for dD in depth_steps:
                geom_state = _geometry_state_with_updates(
                    state,
                    depth=(base_depth + dD) if dD else None,
                    width=(base_width + db) if db else None,
                )
                geom_updates: dict[str, object] = {}
                geom_D = float(_float_from_state(geom_state, "D", base_depth) or base_depth)
                if abs(geom_D - base_depth) > 1e-9:
                    geom_updates["D"] = geom_D
                geom_w = float(_design_width_value(geom_state) or base_width)
                if abs(geom_w - base_width) > 1e-9:
                    geom_updates[width_key] = geom_w
                    if width_key != "b":
                        geom_updates["b"] = geom_w

                width_bucket = round(float(geom_w), 3)
                trial_pool = bottom_trial_cache.get(width_bucket)
                if trial_pool is None:
                    try:
                        trial_pool = list(_enumerate_bottom_reo_design_trials(geom_state, mode_config=mode_cfg) or [])
                    except Exception:
                        trial_pool = []
                    if not trial_pool:
                        trial_pool = [{"label": "Keep current bottom reo", "updates": {}}]
                    bottom_trial_cache[width_bucket] = trial_pool
                observed_bottom_trial_counts.append(len(trial_pool))

                for trial in trial_pool:
                    trial_updates = dict(trial.get("updates") or {})
                    merged_updates = dict(geom_updates)
                    merged_updates.update(trial_updates)
                    if not merged_updates:
                        continue
                    explored_candidates += 1
                    update_keys = set(merged_updates.keys())
                    has_geom = bool(update_keys & _COMPOUND_GEOMETRY_UPDATE_KEYS)
                    has_bottom = bool(update_keys & _COMPOUND_BOTTOM_UPDATE_KEYS)
                    if has_geom and has_bottom:
                        candidate_action_type = "apply_compound_guidance"
                    elif has_bottom:
                        candidate_action_type = "apply_bottom_recommendation"
                    else:
                        candidate_action_type = "apply_geometry_recommendation"
                    try:
                        evaluated = _evaluate_auto_design_candidate(
                            state,
                            updates=merged_updates,
                            source="one_click_solver_search",
                            label=str(trial.get("label") or "Apply one-click design"),
                            action_type=candidate_action_type,
                        )
                    except Exception:
                        skipped_invalid += 1
                        continue
                    if not isinstance(evaluated, dict):
                        skipped_invalid += 1
                        continue
                    if not bool(evaluated.get("is_compliant")):
                        try:
                            wu = float(evaluated.get("worst_util", 0.0) or 0.0)
                            if best_noncompliant_worst_util is None or wu < best_noncompliant_worst_util:
                                best_noncompliant_worst_util = wu
                        except Exception:
                            pass
                        continue
                    _annotate_candidate_target_band_metrics(evaluated, mode_cfg)
                    post_util = evaluated.get("candidate_post_util")
                    try:
                        post_util = float(post_util) if post_util is not None else None
                    except Exception:
                        post_util = None
                    if post_util is None:
                        continue
                    reaches_band = bool(target_min <= post_util <= target_max)
                    resolved = dict(evaluated)
                    resolved["candidate_reaches_target_band"] = reaches_band
                    resolved["reaches_target_band"] = reaches_band
                    resolved["updates"] = dict(merged_updates)
                    resolved["action_type"] = "apply_resolved_candidate"
                    resolved["guidance_change_lines"] = _guidance_change_lines_for_updates(state, merged_updates)
                    subfamilies = _compound_subfamilies_from_updates(merged_updates)
                    resolved["subfamilies"] = list(subfamilies)
                    resolved["recommendation_family_tag"] = _family_tag_from_compound_updates(merged_updates, state)
                    title, _, _ = _compound_guidance_title_reasoning_why(
                        state,
                        merged_updates,
                        subfamilies,
                        strengthening=True,
                    )
                    resolved["label"] = str(title or trial.get("label") or "Apply one-click design")
                    compliant_candidates.append(resolved)

        return (
            compliant_candidates,
            explored_candidates,
            skipped_invalid,
            best_noncompliant_worst_util,
            observed_bottom_trial_counts,
            bottom_trial_cache,
        )

    def _trace_no_compliant(
        explored: int,
        skipped: int,
        obs_counts: list[int],
        btcache: dict[float, list[dict]],
        bnu: float | None,
        *,
        solver_expanded: bool,
    ) -> None:
        if not _design_guide_sidebar_debug_enabled():
            return
        _merge_design_guide_rank_trace(
            {
                "one_click_solver": {
                    "searched": True,
                    "goal": goal_name,
                    "explored_candidates": explored,
                    "skipped_invalid": skipped,
                    "compliant_count": 0,
                    "band_reacher_count": 0,
                    "result": "no_compliant_candidates",
                    "one_click_solver_expanded": bool(solver_expanded),
                },
            },
        )

    def _trace_winner(
        winner: dict,
        compliant: list[dict],
        band_reachers: list[dict],
        explored: int,
        skipped: int,
        *,
        solver_expanded: bool,
    ) -> None:
        if not _design_guide_sidebar_debug_enabled():
            return
        _merge_design_guide_rank_trace(
            {
                "one_click_solver": {
                    "searched": True,
                    "goal": goal_name,
                    "explored_candidates": explored,
                    "skipped_invalid": skipped,
                    "compliant_count": len(compliant),
                    "band_reacher_count": len(band_reachers),
                    "used_pool": "band_reachers" if band_reachers else "all_compliant",
                    "winner_label": winner.get("label"),
                    "winner_post_util": winner.get("candidate_post_util", winner.get("worst_util")),
                    "winner_reaches_target_band": bool(winner.get("candidate_reaches_target_band")),
                    "one_click_solver_expanded": bool(solver_expanded),
                },
            },
        )

    if not expanded:
        compliant_small, ex_s, sk_s, bnu_s, obs_s, btc_s = _run_pass(width_steps_small, depth_steps_small)
        band_small = [c for c in compliant_small if bool(c.get("candidate_reaches_target_band"))]
        if band_small:
            winner = sorted(band_small, key=_goal_key)[0]
            _trace_winner(winner, compliant_small, band_small, ex_s, sk_s, solver_expanded=False)
            return winner
        return _solve_one_click_candidate(state, goal=goal, expanded=True)

    compliant, explored_candidates, skipped_invalid, best_noncompliant_worst_util, observed_bottom_trial_counts, bottom_trial_cache = _run_pass(
        width_steps_full,
        depth_steps_full,
    )

    if not compliant:
        _trace_no_compliant(
            explored_candidates,
            skipped_invalid,
            observed_bottom_trial_counts,
            bottom_trial_cache,
            best_noncompliant_worst_util,
            solver_expanded=True,
        )
        return None

    band_reachers = [c for c in compliant if bool(c.get("candidate_reaches_target_band"))]
    winner_pool = band_reachers if band_reachers else compliant
    winner = sorted(winner_pool, key=_goal_key)[0]
    _trace_winner(
        winner,
        compliant,
        band_reachers,
        explored_candidates,
        skipped_invalid,
        solver_expanded=True,
    )
    return winner


def _compute_design_guidance_items(
    state: dict,
    debug_sink: dict | None = None,
    *,
    guidance_debug_verbose: bool | None = None,
) -> list[dict]:
    design_context = _build_design_actions_context(state)
    guidance_state = dict(design_context.get("state") or _guidance_state_snapshot(state))
    _sync_design_guide_geometry_reference(guidance_state)
    _maybe_reset_design_guide_step_history(guidance_state)
    overview = _collect_design_overview(guidance_state, context=design_context)
    mode_config = _design_mode_config(_design_optimisation_goal(guidance_state))
    target_band_with_eps_passed = _is_in_target_zone_with_eps(overview, mode_config, eps=TARGET_BAND_EPS)
    guidance_branch = "unknown"
    _verbose = True if guidance_debug_verbose is None else bool(guidance_debug_verbose)
    _sink_is_dict = isinstance(debug_sink, dict)
    full_dbg = _sink_is_dict and _verbose
    min_dbg = _sink_is_dict and _verbose
    if min_dbg:
        debug_sink["guidance_resolved_state"] = guidance_state
    if full_dbg:
        debug_sink["overview"] = overview
        debug_sink["overview_actions_used"] = overview.get("actions_used")
        debug_sink["guidance_actions_used"] = dict(design_context.get("actions") or {})
        debug_sink["target_band_eps"] = float(TARGET_BAND_EPS)
        debug_sink["target_band_with_eps_passed"] = bool(target_band_with_eps_passed)
    if _guidance_not_started(guidance_state, overview):
        guidance_branch = "not_started"
        start_item = _guidance_start_item(guidance_state)
        if min_dbg:
            debug_sink["guidance_branch"] = guidance_branch
            debug_sink["selected_action_type"] = start_item.get("action_type")
            debug_sink["selected_title"] = start_item.get("title_main")
        return [start_item]
    governing_action, primary_utils = _guidance_governing_primary_action(overview)
    if full_dbg:
        debug_sink["governing_action"] = governing_action
        debug_sink["primary_utils"] = dict(primary_utils)
    bend_pack = overview["packs"]["bending"]
    shear_pack = overview["packs"]["shear"]
    crack_pack = overview["packs"]["crack"]
    defl_pack = overview["packs"]["deflection"]

    items = [
        _bending_guidance_item(guidance_state, bend_pack),
        _shear_guidance_item(guidance_state, shear_pack),
        _crack_guidance_item(guidance_state, crack_pack),
        _deflection_guidance_item(guidance_state, defl_pack),
    ]
    filtered = [item for item in items if item is not None]
    filtered.sort(key=lambda item: item["priority"], reverse=True)
    governing_item = next(
        (item for item in filtered if str(item.get("check_key") or "") == str(governing_action or "")),
        None,
    )
    critical = [
        item for item in filtered
        if item["bucket"] in ("fail", "warn")
        and (
            item["bucket"] == "fail"
            or item.get("util") is None
            or item["util"] >= GUIDANCE_NEAR_LIMIT_UTIL_THRESHOLD
            or overview["any_fail"]
            or overview["any_warn"]
        )
    ]
    governing_item_is_critical = bool(governing_item and governing_item in critical)
    out_of_band_live = not (bool(overview.get("all_key_pass")) and bool(target_band_with_eps_passed))
    primary_critical = (
        next(
            (
                item for item in critical
                if str(item.get("check_key") or "") == str(governing_action or "")
            ),
            critical[0],
        )
        if critical
        else None
    )
    resolved_one_click_candidate: dict | None = None
    # Bounded one-click search: only when keys do not all pass and a critical item needs
    # an actionable strengthen path. Skip the full search for in-band / passive outcomes
    # (handled later without this solver).
    run_bounded_one_click_solver = (
        bool(overview.get("any_fail"))
        and bool(critical)
    )
    try:
        if run_bounded_one_click_solver:
            resolved_one_click_candidate = _solve_one_click_candidate(
                guidance_state,
                goal=_design_optimisation_goal(guidance_state),
            )
    except Exception:
        resolved_one_click_candidate = None
    if (
        resolved_one_click_candidate is None
        and run_bounded_one_click_solver
        and str(governing_action or "") == "shear"
    ):
        resolved_one_click_candidate = _shear_governing_fallback_resolved_candidate(guidance_state, mode_config)
    one_click_solver_trace = dict((st.session_state.get(DESIGN_GUIDE_RANK_TRACE_KEY) or {}).get("one_click_solver") or {})
    if full_dbg:
        debug_sink["one_click_solver"] = one_click_solver_trace
    if isinstance(resolved_one_click_candidate, dict):
        primary = _guidance_item_from_resolved_candidate(
            resolved_one_click_candidate,
            state=guidance_state,
            overview=overview,
            title=str(resolved_one_click_candidate.get("label") or "Apply one-click design"),
            reasoning="This option is the best compliant one-click design found in the bounded search.",
            status="FAIL",
            primary_action="Apply recommendation",
        )
        guidance_branch = "critical_apply_resolved_candidate"
        if min_dbg:
            payload = dict(primary.get("action_payload") or {})
            debug_sink["one_click_critical_candidate_exists"] = True
            debug_sink["one_click_critical_candidate_label"] = str(resolved_one_click_candidate.get("label") or "")
            debug_sink["one_click_critical_candidate_action_type"] = str(primary.get("action_type") or "")
            debug_sink["one_click_critical_candidate_post_util"] = resolved_one_click_candidate.get("candidate_post_util", resolved_one_click_candidate.get("worst_util"))
            debug_sink["one_click_critical_candidate_reaches_target_band"] = bool(
                resolved_one_click_candidate.get("candidate_reaches_target_band"),
            )
            debug_sink["one_click_critical_candidate_surfaced"] = True
            debug_sink["one_click_critical_candidate_suppressed_reason"] = None
            debug_sink["critical_branch_used_one_click_override"] = True
            debug_sink["primary_guidance_item_action_type"] = primary.get("action_type")
            debug_sink["primary_guidance_item_has_resolved_candidate_payload"] = bool(
                payload.get("resolved_candidate_updates"),
            )
            debug_sink["primary_guidance_item_resolved_candidate_label"] = payload.get("resolved_candidate_label")
            debug_sink["guidance_branch"] = guidance_branch
            debug_sink["selected_action_type"] = primary.get("action_type")
            debug_sink["selected_title"] = primary.get("title_main")
            debug_sink["one_click_candidate_available_at_step_start"] = True
            debug_sink["one_click_candidate_label_at_step_start"] = str(
                resolved_one_click_candidate.get("label") or payload.get("resolved_candidate_label") or "",
            )
        st.session_state.pop(DESIGN_GUIDE_APPLY_BANNER_KEY, None)
        st.session_state.pop(DESIGN_GUIDE_APPLY_BANNER_META_KEY, None)
        return [primary]
    one_click_probe: dict | None = {} if min_dbg else None
    one_click_critical_item: dict | None = None
    one_click_candidate: dict | None = None
    try:
        if out_of_band_live and not bool(overview.get("all_key_pass")):
            mode_recommendation = _compute_mode_guidance_recommendation(guidance_state)
            if isinstance(mode_recommendation, dict):
                base_candidate = _evaluate_auto_design_candidate(guidance_state, source="guidance_primary_seed")
                one_click_candidate = _materialize_guidance_candidate(
                    base_candidate,
                    mode_recommendation,
                    source="guidance_primary_one_click_candidate",
                )
                if one_click_candidate:
                    _annotate_candidate_target_band_metrics(one_click_candidate, mode_config)
                if one_click_candidate and not bool(one_click_candidate.get("is_compliant")):
                    one_click_candidate = None
                if one_click_candidate and not bool(
                    one_click_candidate.get("candidate_reaches_target_band")
                    or one_click_candidate.get("reaches_target_band")
                ):
                    one_click_candidate = None
    except Exception:
        one_click_candidate = None
    if one_click_candidate:
        one_click_critical_item = _guidance_item_from_resolved_candidate(
            one_click_candidate,
            state=guidance_state,
            overview=overview,
            title=str(one_click_candidate.get("label") or "Apply one-click design"),
            reasoning="This option brings the design into the target utilisation band in one move.",
            status="FAIL",
            primary_action="Apply recommendation",
        )
        if isinstance(one_click_probe, dict):
            one_click_probe["one_click_critical_candidate_exists"] = True
            one_click_probe["one_click_critical_candidate_label"] = str(one_click_candidate.get("label") or "")
            one_click_probe["one_click_critical_candidate_action_type"] = str(
                one_click_critical_item.get("action_type")
                or (one_click_critical_item.get("action_payload") or {}).get("resolved_candidate_action_type")
                or "",
            )
            one_click_probe["one_click_critical_candidate_post_util"] = one_click_candidate.get("worst_util")
            one_click_probe["one_click_critical_candidate_reaches_target_band"] = True
            one_click_probe["one_click_critical_candidate_suppressed_reason"] = None
    else:
        one_click_critical_item = _get_one_click_band_reaching_candidate(
            guidance_state,
            overview,
            mode_config=mode_config,
            primary_hint=primary_critical,
            debug_extra=one_click_probe,
        )
    if min_dbg:
        debug_sink["one_click_critical_candidate_exists"] = bool(one_click_probe.get("one_click_critical_candidate_exists"))
        debug_sink["one_click_critical_candidate_label"] = one_click_probe.get("one_click_critical_candidate_label")
        debug_sink["one_click_critical_candidate_action_type"] = one_click_probe.get("one_click_critical_candidate_action_type")
        debug_sink["one_click_critical_candidate_post_util"] = one_click_probe.get("one_click_critical_candidate_post_util")
        debug_sink["one_click_critical_candidate_reaches_target_band"] = bool(
            one_click_probe.get("one_click_critical_candidate_reaches_target_band"),
        )
        debug_sink["one_click_critical_candidate_surfaced"] = False
        debug_sink["one_click_critical_candidate_suppressed_reason"] = one_click_probe.get(
            "one_click_critical_candidate_suppressed_reason",
        )
        debug_sink["critical_branch_used_one_click_override"] = False
        if not out_of_band_live:
            debug_sink["one_click_critical_candidate_suppressed_reason"] = "already_in_target_band_or_passing"
        debug_sink["one_click_candidate_available_at_step_start"] = bool(
            one_click_probe.get("one_click_critical_candidate_exists"),
        )
        debug_sink["one_click_candidate_label_at_step_start"] = one_click_probe.get(
            "one_click_critical_candidate_label",
        )
    if one_click_critical_item is not None and out_of_band_live and critical:
        guidance_branch = "critical_apply_resolved_candidate"
        if min_dbg:
            debug_sink["guidance_branch"] = guidance_branch
            debug_sink["selected_action_type"] = one_click_critical_item.get("action_type")
            debug_sink["selected_title"] = one_click_critical_item.get("title_main")
            debug_sink["one_click_critical_candidate_surfaced"] = True
            debug_sink["one_click_critical_candidate_suppressed_reason"] = None
            debug_sink["critical_branch_used_one_click_override"] = True
            debug_sink["primary_guidance_item_action_type"] = one_click_critical_item.get("action_type")
            debug_sink["primary_guidance_item_has_resolved_candidate_payload"] = bool(
                (one_click_critical_item.get("action_payload") or {}).get("resolved_candidate_updates"),
            )
            debug_sink["primary_guidance_item_resolved_candidate_label"] = (
                (one_click_critical_item.get("action_payload") or {}).get("resolved_candidate_label")
            )
        if str(one_click_critical_item.get("action_type") or "") == "apply_resolved_candidate":
            st.session_state.pop(DESIGN_GUIDE_APPLY_BANNER_KEY, None)
            st.session_state.pop(DESIGN_GUIDE_APPLY_BANNER_META_KEY, None)
        return [one_click_critical_item]
    if (
        one_click_critical_item is not None
        and out_of_band_live
        and (bool(overview.get("any_fail")) or bool(overview.get("any_warn")))
    ):
        guidance_branch = "critical_apply_resolved_candidate_noncritical_bucket"
        if min_dbg:
            debug_sink["guidance_branch"] = guidance_branch
            debug_sink["selected_action_type"] = one_click_critical_item.get("action_type")
            debug_sink["selected_title"] = one_click_critical_item.get("title_main")
            debug_sink["one_click_critical_candidate_surfaced"] = True
            debug_sink["one_click_critical_candidate_suppressed_reason"] = None
            debug_sink["critical_branch_used_one_click_override"] = True
        return [one_click_critical_item]
    if critical and governing_item_is_critical:
        primary = primary_critical or critical[0]
        action_type = str(primary.get("action_type") or "")
        guidance_branch = f"critical_{action_type}" if action_type else "critical_items"
        _log_guidance_branch_governing_mismatch(
            guidance_branch=guidance_branch,
            governing_action=governing_action,
            primary_utils=primary_utils,
            selected_item=primary,
        )
        if min_dbg:
            debug_sink["guidance_branch"] = guidance_branch
            debug_sink["selected_action_type"] = primary.get("action_type")
            debug_sink["selected_title"] = primary.get("title_main")
        remaining = [item for item in critical if item is not primary]
        shear_cleanup_item = _shear_no_demand_cleanup_guidance_item_if_needed(guidance_state)
        if shear_cleanup_item is not None:
            remaining = [shear_cleanup_item] + remaining
        compound_item = _try_compound_strengthening_guidance_item(guidance_state, overview, primary)
        if compound_item:
            head = [compound_item]
        else:
            head = [primary]
        tail_n = max(0, 2 - len(head))
        return head + remaining[:tail_n]
    if critical and not governing_item_is_critical and bool(st.session_state.get("_dev_mode")):
        _agent_debug_log(
            "Suppressed non-governing critical branch",
            {
                "governing_action": governing_action,
                "primary_utils": primary_utils,
                "suppressed_critical_items": [
                    {
                        "check_key": item.get("check_key"),
                        "title": item.get("title_main"),
                        "action_type": item.get("action_type"),
                        "util": item.get("util"),
                    }
                    for item in critical
                ],
                "governing_item": None if governing_item is None else {
                    "check_key": governing_item.get("check_key"),
                    "title": governing_item.get("title_main"),
                    "action_type": governing_item.get("action_type"),
                    "util": governing_item.get("util"),
                    "bucket": governing_item.get("bucket"),
                },
            },
            location="inputs_page.py:_compute_design_guidance_items",
            hypothesis_id="H_GUIDANCE_GOVERNING",
        )
    efficiency_state = compute_efficiency_tightening_state(guidance_state, context=design_context)
    if full_dbg:
        debug_sink["efficiency_tightening_state"] = efficiency_state
        debug_sink["efficiency_actions_used"] = efficiency_state.get("actions_used")
        debug_sink["is_efficiency_reduction_mode"] = bool(efficiency_state.get("is_efficiency_reduction_mode"))
        debug_sink["efficiency_exhaustion_map"] = efficiency_state.get("exhaustion_map")
        debug_sink["efficiency_worst_util"] = efficiency_state.get("worst_util")
        debug_sink["guidance_target_efficiency_band"] = [GUIDANCE_TARGET_UTIL_MIN, GUIDANCE_TARGET_UTIL_MAX]
        debug_sink["strongly_underutilised"] = bool(efficiency_state.get("strongly_underutilised"))
    efficiency_items = _efficiency_guidance_items(guidance_state, efficiency_state)
    compound_eff_item = _try_compound_efficiency_guidance_item(guidance_state, efficiency_state)
    if compound_eff_item:
        compound_eff_item["priority"] = float(compound_eff_item.get("priority") or 0.0) + 25.0
        efficiency_items.insert(0, compound_eff_item)
    if full_dbg:
        debug_sink["terminal_state_blocked"] = efficiency_state.get("terminal_state_blocked")
        debug_sink["terminal_state_block_reason"] = efficiency_state.get("terminal_state_block_reason")
        debug_sink["efficiency_guidance_items_summary"] = [
            {"title_main": i.get("title_main"), "action_type": i.get("action_type")}
            for i in efficiency_items
            if isinstance(i, dict)
        ]
    if efficiency_items:
        efficiency_items.sort(key=lambda item: item["priority"], reverse=True)
        primary = next(
            (
                item for item in efficiency_items
                if str(item.get("check_key") or "") == str(governing_action or "")
            ),
            efficiency_items[0],
        )
        action_type = str(primary.get("action_type") or "")
        guidance_branch = f"efficiency_{action_type}" if action_type else "efficiency_tightening"
        _log_guidance_branch_governing_mismatch(
            guidance_branch=guidance_branch,
            governing_action=governing_action,
            primary_utils=primary_utils,
            selected_item=primary,
        )
        if min_dbg:
            debug_sink["guidance_branch"] = guidance_branch
            debug_sink["selected_action_type"] = primary.get("action_type")
            debug_sink["selected_title"] = primary.get("title_main")
        remaining = [item for item in efficiency_items if item is not primary]
        return [primary] + remaining[:1]
    if overview["all_key_pass"] and target_band_with_eps_passed:
        tb_probe: dict | None = {} if full_dbg else None
        actionable_tb = _get_actionable_target_band_winner(
            guidance_state, overview, debug_extra=tb_probe,
        )
        if actionable_tb:
            guidance_branch = "target_band_actionable_winner"
            if full_dbg:
                debug_sink["guidance_branch"] = guidance_branch
                debug_sink["selected_action_type"] = actionable_tb.get("action_type")
                debug_sink["selected_title"] = actionable_tb.get("title_main")
                debug_sink["actionable_target_band_winner_exists"] = True
                debug_sink["actionable_target_band_winner_family"] = tb_probe.get("family")
                debug_sink["actionable_target_band_winner_subfamilies"] = tb_probe.get("subfamilies")
                debug_sink["actionable_target_band_winner_change_lines"] = tb_probe.get("change_lines")
                debug_sink["optimal_short_circuit_blocked"] = True
                debug_sink["optimal_short_circuit_block_reason"] = str(
                    tb_probe.get("target_band_override_reason") or "target_band_strict_override_passed",
                )
                debug_sink["surfaced_guidance_branch"] = guidance_branch
                debug_sink["surfaced_selected_action_type"] = actionable_tb.get("action_type")
                debug_sink["surfaced_selected_title"] = actionable_tb.get("title_main")
                _merge_target_band_probe_to_debug_sink(debug_sink, tb_probe)
            elif min_dbg:
                debug_sink["guidance_branch"] = guidance_branch
                debug_sink["selected_action_type"] = actionable_tb.get("action_type")
                debug_sink["selected_title"] = actionable_tb.get("title_main")
            return [actionable_tb]
        guidance_branch = "optimal"
        optimal_item = _optimal_guidance_item(guidance_state, overview)
        if full_dbg:
            debug_sink["guidance_branch"] = guidance_branch
            debug_sink["selected_action_type"] = optimal_item.get("action_type")
            debug_sink["selected_title"] = optimal_item.get("title_main")
            debug_sink["actionable_target_band_winner_exists"] = False
            debug_sink["actionable_target_band_winner_family"] = None
            debug_sink["actionable_target_band_winner_subfamilies"] = None
            debug_sink["actionable_target_band_winner_change_lines"] = None
            debug_sink["optimal_short_circuit_blocked"] = False
            debug_sink["optimal_short_circuit_block_reason"] = str(
                tb_probe.get("target_band_override_reason") or tb_probe.get("reason") or "no_actionable_winner",
            )
            debug_sink["surfaced_guidance_branch"] = guidance_branch
            debug_sink["surfaced_selected_action_type"] = optimal_item.get("action_type")
            debug_sink["surfaced_selected_title"] = optimal_item.get("title_main")
            _merge_target_band_probe_to_debug_sink(debug_sink, tb_probe)
        elif min_dbg:
            debug_sink["guidance_branch"] = guidance_branch
            debug_sink["selected_action_type"] = optimal_item.get("action_type")
            debug_sink["selected_title"] = optimal_item.get("title_main")
        return [optimal_item]
    passive_fallback_allowed = (
        overview["all_key_pass"]
        and (
            _is_in_target_zone_with_eps(overview, mode_config, eps=TARGET_BAND_EPS)
            or not _efficiency_state_has_valid_candidate(efficiency_state)
        )
    )
    if filtered:
        primary = next(
            (
                item for item in filtered
                if str(item.get("check_key") or "") == str(governing_action or "")
            ),
            filtered[0],
        )
        action_type = str(primary.get("action_type") or "")
        guidance_branch = f"passing_guidance_{action_type}" if action_type else "passing_guidance_fallback"
        _log_guidance_branch_governing_mismatch(
            guidance_branch=guidance_branch,
            governing_action=governing_action,
            primary_utils=primary_utils,
            selected_item=primary,
        )
        if min_dbg:
            debug_sink["guidance_branch"] = guidance_branch
            debug_sink["selected_action_type"] = primary.get("action_type")
            debug_sink["selected_title"] = primary.get("title_main")
        return [primary]
    if not passive_fallback_allowed:
        guidance_branch = "passing_guidance_blocked"
        blocked_item = _guidance_item(
            "general",
            "Design can be tightened",
            "Review optimisation options",
            "Automatic tightening did not yield a safe passive fallback under the resolved action set.",
            (
                f"Why: the current beam passes, but the resolved actions still place it outside the preferred "
                f"target zone for {_design_optimisation_goal_label(guidance_state).lower()}."
            ),
            "Key levers: optimisation preference, geometry, reinforcement",
            None,
            None,
            status="EFFICIENCY",
            util=overview["worst_util"],
        )
        if min_dbg:
            debug_sink["guidance_branch"] = guidance_branch
            debug_sink["selected_action_type"] = blocked_item.get("action_type")
            debug_sink["selected_title"] = blocked_item.get("title_main")
        return [blocked_item]
    guidance_branch = "passing_guidance_fallback"
    passing_item = _passing_guidance_item(guidance_state, overview)
    if min_dbg:
        debug_sink["guidance_branch"] = guidance_branch
        debug_sink["selected_action_type"] = passing_item.get("action_type")
        debug_sink["selected_title"] = passing_item.get("title_main")
    return [passing_item]


def _render_fast_design_guidance_panel(
    sync_callbacks: dict,
    inputs_render_audit: dict[str, str] | None = None,
    *,
    fast_focus_section: str | None = None,
) -> None:
    if inputs_render_audit is not None:
        inputs_render_audit["design_guide_rendered"] = "yes"
    banner_generic_only = bool(st.session_state.pop("_design_guide_banner_generic_only", False))
    _sync_auto_design_mode_tracking(_shared_state_snapshot())
    st.markdown("### Design Guide")
    current_state = _shared_state_snapshot()
    fingerprint = _design_guide_cache_fingerprint(current_state)
    sidebar_debug = _design_guide_sidebar_debug_enabled()
    if sidebar_debug:
        _reset_design_guide_reco_trace()
    else:
        st.session_state.pop(DESIGN_GUIDE_RECO_TRACE_KEY, None)
        st.session_state.pop(DESIGN_GUIDE_RANK_TRACE_KEY, None)

    if not st.session_state.get(DESIGN_GUIDE_NEEDS_REFRESH_KEY):
        baseline_fp = st.session_state.get(DESIGN_GUIDE_PANEL_BASELINE_FP_KEY)
        if baseline_fp is not None and fingerprint != baseline_fp:
            _mark_design_guide_dirty()

    if st.session_state.get(DESIGN_GUIDE_NEEDS_REFRESH_KEY):
        st.info("Design guide needs refresh.")
        if st.button("Update design guide", key="_design_guide_needs_refresh_ack"):
            st.session_state[DESIGN_GUIDE_PANEL_BASELINE_FP_KEY] = fingerprint
            st.session_state.pop(DESIGN_GUIDE_NEEDS_REFRESH_KEY, None)
            st.rerun()
        return

    guidance_started_at = time.perf_counter()
    guidance_items: list[dict] = []
    guidance_debug: dict = {}
    guidance_cache_hit = False

    cached_items, cached_debug, cache_hit = _get_cached_design_guide_guidance(fingerprint)
    if cache_hit:
        guidance_items = list(cached_items or [])
        guidance_debug = dict(cached_debug or {})
        guidance_cache_hit = True
    else:
        _clear_design_guide_transient_ui_state(
            clear_history=False,
            preserve_apply_banner=True,
        )
        guidance_debug = {}
        guidance_items = _compute_design_guidance_items(
            current_state,
            debug_sink=guidance_debug,
            guidance_debug_verbose=sidebar_debug,
        )
        _set_cached_design_guide_guidance(
            fingerprint,
            guidance_items,
            guidance_debug,
        )
        guidance_cache_hit = False

    guidance_compute_ms = round((time.perf_counter() - guidance_started_at) * 1000.0, 1)
    if sidebar_debug:
        guidance_debug["guidance_compute_ms"] = guidance_compute_ms
        guidance_debug["guidance_cache_hit"] = bool(guidance_cache_hit)
        ocs = dict((guidance_debug.get("one_click_solver") or {}))
        guidance_debug["one_click_solver_expanded"] = bool(ocs.get("one_click_solver_expanded"))
    guidance_disp_state = dict(guidance_debug.get("guidance_resolved_state") or current_state)
    guidance_items, guidance_dedupe_meta = _dedupe_guidance_items_for_display(
        guidance_items,
        guidance_disp_state,
    )
    resolved_guidance_actions = _debug_resolved_guidance_actions(current_state)
    efficiency_state = guidance_debug.get("efficiency_tightening_state") or {}
    mode_mt = efficiency_state.get("mode_tightening")
    bottom_bt = efficiency_state.get("bottom_tightening")
    if sidebar_debug:
        last_apply_route = dict(st.session_state.get(DESIGN_GUIDE_LAST_APPLY_ROUTE_KEY) or {})
        gsum = []
        for it in guidance_items[:12]:
            if isinstance(it, dict):
                gsum.append(
                    {
                        "action_type": it.get("action_type"),
                        "title_main": it.get("title_main"),
                        "status": it.get("status"),
                        "util": it.get("util"),
                    }
                )
        ov = guidance_debug.get("overview") or {}
        primary_item = guidance_items[0] if guidance_items else {}
        primary_payload = dict((primary_item or {}).get("action_payload") or {})
        primary_card_is_resolved_one_click = _guidance_item_is_resolved_one_click(primary_item)
        primary_card_expected_util_value = _guidance_item_expected_util(primary_item)
        primary_card_expected_util_rendered = bool(
            primary_card_is_resolved_one_click and primary_card_expected_util_value is not None,
        )
        trial_geom = dict(st.session_state.get(DESIGN_GUIDE_GEOMETRY_TRIAL_DEBUG_KEY) or {})
        live_design_summary = _overview_debug_summary(guidance_disp_state, ov)
        post_apply_expected = last_apply_route.get("expected_post_util")
        try:
            post_apply_expected = float(post_apply_expected) if post_apply_expected is not None else None
        except Exception:
            post_apply_expected = None
        post_apply_live_worst = ov.get("worst_util")
        try:
            post_apply_live_worst = float(post_apply_live_worst) if post_apply_live_worst is not None else None
        except Exception:
            post_apply_live_worst = None
        mode_cfg_live = _design_mode_config(_design_optimisation_goal(guidance_disp_state))
        post_apply_live_in_target_band = bool(ov.get("all_key_pass")) and _is_in_target_zone_with_eps(
            ov,
            mode_cfg_live,
            eps=TARGET_BAND_EPS,
        )
        post_apply_tol = 0.02
        post_apply_matches = (
            post_apply_expected is not None
            and post_apply_live_worst is not None
            and abs(post_apply_live_worst - post_apply_expected) <= post_apply_tol
        )
        st.session_state[DESIGN_GUIDE_DEBUG_BUNDLE_KEY] = {
            "guidance_compute_ms": guidance_compute_ms,
            "guidance_cache_hit": bool(guidance_cache_hit),
            "one_click_solver_expanded": guidance_debug.get("one_click_solver_expanded"),
            "session_actions": {
                "actions_source": st.session_state.get("actions_source"),
                "inputs_actions_source": st.session_state.get("inputs_actions_source"),
                "actions_mode": st.session_state.get("actions_mode"),
                "load_Mstar_proxy": st.session_state.get("load_Mstar_proxy"),
                "load_Vstar_proxy": st.session_state.get("load_Vstar_proxy"),
                "Mu_star": st.session_state.get("Mu_star"),
                "Vu_star": st.session_state.get("Vu_star"),
                "uls_Mstar": st.session_state.get("uls_Mstar"),
                "uls_Vstar": st.session_state.get("uls_Vstar"),
                "uls_Nstar": st.session_state.get("uls_Nstar"),
                "N_star": st.session_state.get("N_star"),
            },
            "resolved_guidance_actions": resolved_guidance_actions,
            "manual_resolver_lock_check": {
                "uls_Mstar": st.session_state.get("uls_Mstar"),
                "uls_Vstar": st.session_state.get("uls_Vstar"),
                "uls_Nstar": st.session_state.get("uls_Nstar"),
                "resolved_Mu": resolved_guidance_actions.get("Mu"),
                "resolved_Vu": resolved_guidance_actions.get("Vu"),
                "resolved_Nu": resolved_guidance_actions.get("Nu"),
            },
            "overview": guidance_debug.get("overview"),
            "efficiency_tightening_state": guidance_debug.get("efficiency_tightening_state"),
            "current_design_summary": live_design_summary,
            "next_mode_recommendation": mode_mt,
            "bottom_tightening": bottom_bt,
            "guidance_branch": guidance_debug.get("guidance_branch"),
            "overview_actions_used": guidance_debug.get("overview_actions_used"),
            "efficiency_actions_used": guidance_debug.get("efficiency_actions_used"),
            "guidance_actions_used": guidance_debug.get("guidance_actions_used"),
            "fingerprints": {
                "guidance_fingerprint": _recommendation_cache_fingerprint(_guidance_state_snapshot(current_state)),
                "auto_design_governing_fingerprint": _auto_design_governing_fingerprint(current_state),
                "auto_design_action_signature": tuple(_resolve_design_actions_from_state(current_state).get("signature", ())),
                "selected_action_type": guidance_debug.get("selected_action_type"),
                "selected_title": guidance_debug.get("selected_title"),
            },
            "guidance_items_summary": gsum,
            "primary_utils": ov.get("utils"),
            "governing_action": ov.get("governing_action"),
            "is_efficiency_reduction_mode": guidance_debug.get("is_efficiency_reduction_mode"),
            "terminal_state_blocked": guidance_debug.get("terminal_state_blocked"),
            "terminal_state_block_reason": guidance_debug.get("terminal_state_block_reason"),
            "efficiency_exhaustion_map": guidance_debug.get("efficiency_exhaustion_map"),
            "efficiency_guidance_items_summary": guidance_debug.get("efficiency_guidance_items_summary"),
            "guidance_target_efficiency_band": guidance_debug.get("guidance_target_efficiency_band"),
            "efficiency_worst_util": guidance_debug.get("efficiency_worst_util"),
            "strongly_underutilised": guidance_debug.get("strongly_underutilised"),
            "actionable_target_band_winner_exists": guidance_debug.get("actionable_target_band_winner_exists"),
            "actionable_target_band_winner_family": guidance_debug.get("actionable_target_band_winner_family"),
            "actionable_target_band_winner_subfamilies": guidance_debug.get("actionable_target_band_winner_subfamilies"),
            "actionable_target_band_winner_change_lines": guidance_debug.get("actionable_target_band_winner_change_lines"),
            "optimal_short_circuit_blocked": guidance_debug.get("optimal_short_circuit_blocked"),
            "optimal_short_circuit_block_reason": guidance_debug.get("optimal_short_circuit_block_reason"),
            "surfaced_guidance_branch": guidance_debug.get("surfaced_guidance_branch"),
            "surfaced_selected_action_type": guidance_debug.get("surfaced_selected_action_type"),
            "surfaced_selected_title": guidance_debug.get("surfaced_selected_title"),
            "target_band_default_stop": guidance_debug.get("target_band_default_stop"),
            "target_band_override_allowed": guidance_debug.get("target_band_override_allowed"),
            "target_band_override_reason": guidance_debug.get("target_band_override_reason"),
            "target_band_eps": guidance_debug.get("target_band_eps"),
            "target_band_with_eps_passed": guidance_debug.get("target_band_with_eps_passed"),
            "one_click_critical_candidate_exists": guidance_debug.get("one_click_critical_candidate_exists"),
            "one_click_critical_candidate_label": guidance_debug.get("one_click_critical_candidate_label"),
            "one_click_critical_candidate_action_type": guidance_debug.get("one_click_critical_candidate_action_type"),
            "one_click_critical_candidate_post_util": guidance_debug.get("one_click_critical_candidate_post_util"),
            "one_click_critical_candidate_reaches_target_band": guidance_debug.get("one_click_critical_candidate_reaches_target_band"),
            "one_click_critical_candidate_surfaced": guidance_debug.get("one_click_critical_candidate_surfaced"),
            "one_click_critical_candidate_suppressed_reason": guidance_debug.get("one_click_critical_candidate_suppressed_reason"),
            "one_click_solver": guidance_debug.get("one_click_solver"),
            "critical_branch_used_one_click_override": guidance_debug.get("critical_branch_used_one_click_override"),
            "winner_goal_alignment_score": guidance_debug.get("winner_goal_alignment_score"),
            "current_goal_alignment_score": guidance_debug.get("current_goal_alignment_score"),
            "goal_alignment_improvement": guidance_debug.get("goal_alignment_improvement"),
            "in_band_materiality_passed": guidance_debug.get("in_band_materiality_passed"),
            "in_band_strong_override_passed": guidance_debug.get("in_band_strong_override_passed"),
            "mode_difference_material": guidance_debug.get("mode_difference_material"),
            "in_band_mode_search_strategy": guidance_debug.get("in_band_mode_search_strategy"),
            "in_band_overview_worst_util": guidance_debug.get("in_band_overview_worst_util"),
            "design_guide_banner_generic_only": banner_generic_only,
            "design_guide_blue_banner_generic_text_only": bool(
                banner_generic_only and fast_focus_section == "model"
            ),
            "design_guide_rank_trace": st.session_state.get(DESIGN_GUIDE_RANK_TRACE_KEY),
            "recommendation_change_lines": _proposed_change_lines_for_guidance_item(
                primary_item, guidance_disp_state,
            ),
            "recommendation_why_text": _guidance_card_why_body(primary_item),
            "current_candidate_title": primary_item.get("title_main"),
            "current_candidate_family": _design_guide_candidate_family(primary_item),
            "primary_guidance_item_action_type": primary_item.get("action_type"),
            "primary_guidance_item_has_resolved_candidate_payload": bool(
                primary_payload.get("resolved_candidate_updates"),
            ),
            "primary_guidance_item_resolved_candidate_label": primary_payload.get("resolved_candidate_label"),
            "primary_card_is_resolved_one_click": primary_card_is_resolved_one_click,
            "primary_card_expected_util_value": primary_card_expected_util_value,
            "primary_card_expected_util_rendered": primary_card_expected_util_rendered,
            "primary_card_content_source": "primary_action_payload_only",
            "primary_card_used_step_history_content": False,
            "apply_used_resolved_candidate_payload": bool(last_apply_route.get("apply_used_resolved_candidate_payload")),
            "apply_fell_back_to_generic_solver": bool(last_apply_route.get("apply_fell_back_to_generic_solver")),
            "apply_fallback_reason": last_apply_route.get("apply_fallback_reason"),
            "apply_direct_resolved_candidate": bool(last_apply_route.get("apply_direct_resolved_candidate")),
            "expected_post_util": last_apply_route.get("expected_post_util"),
            "one_click_candidate_available_at_step_start": last_apply_route.get(
                "one_click_candidate_available_at_step_start",
            ),
            "one_click_candidate_label_at_step_start": last_apply_route.get(
                "one_click_candidate_label_at_step_start",
            ),
            "correction_candidate_considered": trial_geom.get("correction_candidate_considered"),
            "correction_candidate_summary": trial_geom.get("correction_candidate_summary"),
            "correction_candidate_score": trial_geom.get("correction_candidate_score"),
            "correction_candidate_won": trial_geom.get("correction_candidate_won"),
            "reference_D": trial_geom.get("reference_D"),
            "current_D": trial_geom.get("current_D"),
            "D_offset_from_reference": trial_geom.get("D_offset_from_reference"),
            "goal_alignment_penalty": trial_geom.get("goal_alignment_penalty"),
            "design_guide_reference_b": st.session_state.get(DESIGN_GUIDE_REFERENCE_B_KEY),
            "design_guide_session_anchor_D": st.session_state.get(DESIGN_GUIDE_SESSION_ANCHOR_D_KEY),
            "design_guide_last_user_geometry": st.session_state.get(DESIGN_GUIDE_LAST_USER_GEOM_KEY),
            "design_guide_last_applied_auto_geometry": st.session_state.get(DESIGN_GUIDE_LAST_AUTO_GEOM_KEY),
            "post_apply_resolved_candidate_attempted": bool(
                last_apply_route.get("post_apply_resolved_candidate_attempted"),
            ),
            "post_apply_resolved_candidate_label": last_apply_route.get("resolved_candidate_label"),
            "post_apply_resolved_candidate_expected_util": last_apply_route.get("expected_post_util"),
            "post_apply_live_worst_util": post_apply_live_worst,
            "post_apply_live_in_target_band": post_apply_live_in_target_band,
            "post_apply_live_design_summary": live_design_summary,
            "post_apply_matches_expected_util_within_tol": bool(post_apply_matches),
            **_design_guide_step_history_debug_summary(),
            **guidance_dedupe_meta,
        }
    _render_guidance_secondary_items(
        guidance_items,
        guidance_disp_state=guidance_disp_state,
        inputs_render_audit=inputs_render_audit,
        start_index=0,
    )
    if fast_focus_section == "model":
        _render_design_guide_post_apply_banner(fast_focus_section)

    st.session_state[DESIGN_GUIDE_PANEL_BASELINE_FP_KEY] = fingerprint
    st.session_state.pop(DESIGN_GUIDE_NEEDS_REFRESH_KEY, None)


def render_inputs():
    # NOTE: init_shared_session_state() is called by app.py router before this function runs.
    # Pages must NOT call init/hydrate themselves - the router owns the lifecycle.
    if _INPUTS_DEBUG_AUDIT:
        log_debug("---- INPUTS PAGE LOAD START ----")
        for key in SHARED_DEFAULTS.keys():
            log_debug(f"SHARED INIT - {key}", st.session_state.get(key))
        for shared_key, tab_key in INPUTS_PAGE_TAB_KEYS.items():
            log_debug(f"TAB INIT - {shared_key} <- {tab_key}", st.session_state.get(tab_key))

    from state_and_helpers import _write_sync_trace_line
    _write_sync_trace_line("\n=== PAGE RENDER: inputs ===")
    render_started_at = time.perf_counter()
    # region agent log
    _agent_debug_log(
        "Entered inputs page render",
        {
            "active_beam_id": str(st.session_state.get("active_beam_id") or ""),
            "inputs_detailed_mode": bool(st.session_state.get("inputs_detailed_mode", False)),
            "page_slug": str(st.session_state.get("page_slug") or ""),
        },
        location="inputs_page.py:render_inputs:start",
        hypothesis_id="H18",
    )
    # endregion

    ensure_beam_project_initialized()
    if st.session_state.get("_beam_skip_auto_persist_once") is None:
        st.session_state["_beam_skip_auto_persist_once"] = False

    # Startup precedence: (1) stored active beam hydrate (2) pending apply refresh
    # (3) ordinary rerun only. New-beam starter seeding is handled in state_and_helpers.add_new_beam_record().
    inputs_startup_debug: dict[str, object] = {
        "explicit_beam_hydrate": False,
        "pending_refresh_happened": False,
        "ordinary_rerun_only": True,
    }

    explicit_beam_hydrate = bool(load_active_beam_into_shared())
    inputs_startup_debug["explicit_beam_hydrate"] = explicit_beam_hydrate
    if explicit_beam_hydrate:
        inputs_startup_debug["ordinary_rerun_only"] = False
        hydrate_active_page_widgets_from_shared("inputs", force_on_page_change=True)

    pending_refresh = st.session_state.pop("_pending_inputs_apply_refresh", None)
    if pending_refresh:
        inputs_startup_debug["pending_refresh_happened"] = True
        inputs_startup_debug["ordinary_rerun_only"] = False
        hydrate_active_page_widgets_from_shared("inputs", force_on_page_change=True)

    _agent_debug_log(
        "Inputs beam-module startup trace",
        inputs_startup_debug,
        location="inputs_page.py:render_inputs:beam_startup",
        hypothesis_id="H_BEAM_MODULE_STARTUP",
    )

    corrected_invalid_shear_state = _normalise_invalid_shear_state_in_shared(source="render_inputs:pre_render")
    fast_focus_section = st.session_state.pop("_fast_mode_focus_section", None)

    raw_sync_callbacks = get_sync_callbacks()
    sync_callbacks = (
        _wrap_inputs_sync_callbacks(raw_sync_callbacks, log_debug)
        if _INPUTS_DEBUG_AUDIT
        else raw_sync_callbacks
    )

    if "inputs_dirty" not in st.session_state:
        st.session_state["inputs_dirty"] = True

    inputs_render_audit = _fresh_inputs_render_audit()
    st.session_state["_inputs_render_audit_live"] = inputs_render_audit
    apply_inputs_page_css()
    apply_global_widget_css()
    apply_calcbox_css()

    before_state = _inputs_audit_snapshot_state() if _INPUTS_DEBUG_AUDIT else None

    st.sidebar.toggle(
        "Design Guide Debug",
        value=False,
        key=DESIGN_GUIDE_SIDEBAR_DEBUG_TOGGLE_KEY,
    )

    debug_mode = st.sidebar.checkbox(
        "Debug session state",
        key=f"debug_state_toggle_{st.session_state.get('page_slug','page')}"
    )
    if debug_mode:
        st.sidebar.markdown("### Debug session state")

        debug_keys = [
            "page_slug",
            "actions_source",
            "inputs_actions_source",
            "loads_edit_mode",

            # load proxies
            "load_Mstar_proxy",
            "load_Vstar_proxy",
            "load_Nstar_proxy",

            # shared actions
            "uls_Mstar",
            "uls_Vstar",
            "uls_Nstar",

            # bending derived
            "Mu_star",
            "Mu_star_kNm",

            # shear derived
            "Vu_star",

            # SFD/BMD outputs
            "sfd_Mmax_abs_kNm",
            "sfd_Vmax_abs_kN",
        ]

        st.sidebar.json({
            k: st.session_state.get(k)
            for k in debug_keys
        })

    summary_container = st.container()

    beam_labels = _beam_option_labels()
    beam_order = st.session_state.get("beam_order", [])
    active_beam_id = st.session_state.get("active_beam_id")
    if active_beam_id not in beam_order and beam_order:
        active_beam_id = beam_order[0]

    st.markdown("##### Batch design")
    beam_selector_col, add_beam_col, dup_beam_col, del_beam_col, reset_workspace_col, manager_toggle_col = st.columns(
        [2.9, 0.9, 1.05, 0.9, 1.35, 1.25],
        gap="small",
    )

    with beam_selector_col:
        selected_beam_id = st.selectbox(
            "Active beam",
            options=beam_order,
            index=beam_order.index(active_beam_id) if active_beam_id in beam_order else 0,
            format_func=lambda beam_id: beam_labels.get(beam_id, beam_id),
            key="beam_manager_active_selector",
            help="Only the active beam is loaded into shared state and calculated by the app.",
        )
        # region agent log
        _agent_debug_log(
            "Rendered beam selector",
            {
                "active_beam_id": str(active_beam_id or ""),
                "selected_beam_id": str(selected_beam_id or ""),
                "selector_state": str(st.session_state.get("beam_manager_active_selector") or ""),
                "pending_refresh": bool(pending_refresh),
                "beam_order": [str(beam_id) for beam_id in beam_order],
            },
            location="inputs_page.py:render_inputs:beam_selector",
            hypothesis_id="H21",
        )
        # endregion
        if selected_beam_id != active_beam_id:
            # region agent log
            _agent_debug_log(
                "Beam selector requested beam change",
                {
                    "active_beam_id": str(active_beam_id or ""),
                    "selected_beam_id": str(selected_beam_id or ""),
                    "selector_state": str(st.session_state.get("beam_manager_active_selector") or ""),
                    "pending_refresh": bool(pending_refresh),
                },
                location="inputs_page.py:render_inputs:beam_selector:change",
                hypothesis_id="H21",
            )
            # endregion
            if set_active_beam(selected_beam_id):
                hydrate_active_page_widgets_from_shared("inputs", force_on_page_change=True)
                st.rerun()

    with add_beam_col:
        st.markdown("<div style='height: 1.55rem;'></div>", unsafe_allow_html=True)
        if st.button("Add", key="beam_manager_add_button", use_container_width=True):
            add_new_beam_record()
            hydrate_active_page_widgets_from_shared("inputs", force_on_page_change=True)
            st.rerun()

    with dup_beam_col:
        st.markdown("<div style='height: 1.55rem;'></div>", unsafe_allow_html=True)
        if st.button("Duplicate", key="beam_manager_duplicate_button", use_container_width=True):
            duplicate_active_beam_record()
            hydrate_active_page_widgets_from_shared("inputs", force_on_page_change=True)
            st.rerun()

    with del_beam_col:
        st.markdown("<div style='height: 1.55rem;'></div>", unsafe_allow_html=True)
        if st.button(
            "Delete",
            key="beam_manager_delete_button",
            use_container_width=True,
            disabled=len(beam_order) <= 1,
        ):
            delete_beam_record(active_beam_id)
            hydrate_active_page_widgets_from_shared("inputs", force_on_page_change=True)
            st.rerun()

    with reset_workspace_col:
        st.markdown("<div style='height: 1.55rem;'></div>", unsafe_allow_html=True)
        if st.button(
            "Reset workspace",
            key="beam_manager_reset_workspace",
            use_container_width=True,
            help=(
                "New clean workspace: one starter beam, all design actions set to zero, "
                "and saved session snapshot cleared so values are not restored from disk."
            ),
        ):
            reset_app_to_clean_starter_workspace()

    with manager_toggle_col:
        st.markdown("<div style='height: 1.55rem;'></div>", unsafe_allow_html=True)
        manager_is_shown = bool(st.session_state.get("beam_project_show_manager", False))
        toggle_label = "Hide Manager" if manager_is_shown else "Show Manager"
        if st.button(toggle_label, key="beam_manager_toggle_button", use_container_width=True):
            st.session_state["beam_project_show_manager"] = not manager_is_shown
            st.rerun()

    if st.session_state.get("beam_project_show_manager", False):
        with st.expander("Bulk Beam Manager", expanded=False):
            st.caption("Table-first overview for all stored beams. Non-active beams use stored params and cached summaries only.")
            schedule_export_rows = build_beam_schedule_export_rows()
            schedule_export_df = pd.DataFrame(schedule_export_rows)
            export_name = st.session_state.get("active_project_name") or "beam-project"
            active_summary = get_active_beam_summary()

            st.markdown("##### Beam Schedule")
            schedule_col, export_col = st.columns([4.0, 1.3], gap="small")
            with schedule_col:
                st.dataframe(
                    _build_schedule_preview_df(),
                    hide_index=True,
                    use_container_width=True,
                )
            with export_col:
                st.markdown("<div style='height: 1.55rem;'></div>", unsafe_allow_html=True)
                st.download_button(
                    "Export Beam Schedule (CSV)",
                    data=schedule_export_df.to_csv(index=False),
                    file_name=f"{export_name}_beam_schedule.csv",
                    mime="text/csv",
                    use_container_width=True,
                    key="beam_manager_export_schedule_csv",
                )

            preview_status_col, preview_diagram_col = st.columns([1.1, 1.9], gap="large")
            with preview_status_col:
                st.markdown("##### Active Beam Status")
                active_status_df = pd.DataFrame(
                    [
                        {
                            "Item": "Overall",
                            "Status": _format_beam_status_badge(
                                active_summary.get("overall_status"),
                                strength_status=active_summary.get("strength_status"),
                                detailing_status=active_summary.get("detailing_status"),
                            ),
                        },
                        {
                            "Item": "Strength",
                            "Status": _format_beam_status_badge(active_summary.get("strength_status")),
                        },
                        {
                            "Item": "Detailing",
                            "Status": _format_beam_status_badge(active_summary.get("detailing_status")),
                        },
                        {
                            "Item": "Last Checked",
                            "Status": _format_last_checked(active_summary.get("last_checked_at")),
                        },
                    ]
                )
                st.dataframe(active_status_df, hide_index=True, use_container_width=True)
            with preview_diagram_col:
                st.markdown("##### Active Beam Section Preview")
                try:
                    fig_sec_preview = make_summary_cross_section_figure()
                    st.plotly_chart(
                        fig_sec_preview,
                        use_container_width=True,
                        config={"displayModeBar": False},
                    )
                except Exception as exc:
                    st.info(f"Section preview unavailable: {exc}")

            with st.expander("Quick Edit Table", expanded=False):
                st.caption("Quick edits update stored beam records only. Use the save button to push the active beam's current app state back into the table.")
                schedule_df = _build_beam_schedule_df()
                edited_schedule_df = st.data_editor(
                    schedule_df,
                    key="beam_manager_schedule_editor",
                    hide_index=True,
                    use_container_width=True,
                    num_rows="fixed",
                    column_config={
                        "active": st.column_config.TextColumn("Active", disabled=True),
                        "beam_id": st.column_config.TextColumn("Beam ID", disabled=True),
                        "beam_label": st.column_config.TextColumn("Beam Label"),
                        "overall_status": st.column_config.TextColumn("Overall", disabled=True),
                        "bending_status": st.column_config.TextColumn("Bending", disabled=True),
                        "shear_status": st.column_config.TextColumn("Shear", disabled=True),
                        "crack_status": st.column_config.TextColumn("Crack", disabled=True),
                        "deflection_status": st.column_config.TextColumn("Deflection", disabled=True),
                        "last_checked_at": st.column_config.TextColumn("Last Checked", disabled=True),
                        "sec_shape": st.column_config.SelectboxColumn("Section", options=["RECT", "T", "I"]),
                    },
                )
                changed_schedule_beams = _sync_beam_records_from_schedule_df(edited_schedule_df)
                if active_beam_id in changed_schedule_beams:
                    st.session_state["_beam_skip_auto_persist_once"] = True

                _, manager_save_col = st.columns([3.8, 1.4], gap="small")
                with manager_save_col:
                    st.markdown("<div style='height: 1.55rem;'></div>", unsafe_allow_html=True)
                    if st.button("Save Active Beam Back To Table", key="beam_manager_save_active", use_container_width=True):
                        persist_active_beam_from_shared()
                        st.session_state["_beam_skip_auto_persist_once"] = False
                        st.rerun()

    page_divider()

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

    # ============================
    # 1. Top section layout
    # ============================
    bottom_slot = None
    shear_slot = None
    model_slot = None
    if inputs_detailed_mode:
        _render_fast_design_guidance_panel(
            sync_callbacks,
            inputs_render_audit,
            fast_focus_section=fast_focus_section,
        )
        left_inputs, right_diagram = st.columns([1.15, 1.85], gap="large")
        with left_inputs:
            actions_slot = st.container()
            geometry_slot = st.container()
    else:
        _render_fast_design_guidance_panel(sync_callbacks, inputs_render_audit)
        fast_left, fast_right = st.columns([1.0, 1.5], gap="medium")
        with fast_left:
            actions_slot = st.container()
            geometry_slot = st.container()
        with fast_right:
            model_slot = st.container()
        right_diagram = None

    with actions_slot:
        # --- Design Actions ---
        title_col, info_col = st.columns([20, 1], gap="small")
        with title_col:
            st.markdown("## Design Actions")
        # First-load migration / hydration for legacy values
        legacy_manual = "Manual design actions (inputs below)"
        legacy_design = "Teaching SFD/BMD page (|M|max, |V|max)"

        current_actions_source = st.session_state.get(
            "actions_source",
            legacy_manual,
        )

        # Migrate any old labels
        if current_actions_source == "Manual design actions":
            current_actions_source = legacy_manual
        elif current_actions_source == "Calculated design actions (from SFD/BMD)":
            current_actions_source = legacy_design

        design_actions_toggle_default = (current_actions_source == legacy_design)
        # Align with canonical actions_source when it changes on another page (e.g. SFD/BMD toggle).
        _itk_calculated = "inputs_use_calculated_actions"
        _itk_calculated_intent = "_inputs_use_calculated_actions_user_intent"
        user_intent_pending = bool(st.session_state.get(_itk_calculated_intent, False))
        if (
            (not user_intent_pending)
            and _itk_calculated in st.session_state
            and bool(st.session_state[_itk_calculated]) != bool(
            design_actions_toggle_default
            )
        ):
            st.session_state[_itk_calculated] = bool(design_actions_toggle_default)
            st.rerun()
        with info_col:
            with info_i_button(
                help_text="Explain where design demand comes from and control whether loads are manual or linked to the Design page."
            ):
                st.markdown("**What sets demand**")
                st.markdown("- ULS actions drive bending and shear strength checks.")
                st.markdown("- SLS actions drive crack and deflection serviceability checks.")
                st.markdown("- When linked to the Design page, this screen follows the critical actions from the SFD/BMD workflow.")
                st.markdown("**When to change it**")
                st.markdown("- Use manual inputs for quick studies or hand-checking one beam.")
                st.markdown("- Use linked actions when demand should stay tied to the analysed load model.")
                st.markdown("**What to avoid**")
                st.markdown("- Do not compare a ULS strength result against an SLS load view by mistake.")
                st.divider()
                def _on_inputs_use_calculated_actions_change() -> None:
                    st.session_state[_itk_calculated_intent] = True
                    st.session_state["inputs_dirty"] = True

                use_calculated_actions = st.toggle(
                    "Use calculated design actions",
                    value=design_actions_toggle_default,
                    key="inputs_use_calculated_actions",
                    on_change=_on_inputs_use_calculated_actions_change,
                    help=(
                        "When enabled, the design actions below are taken from the "
                        "Design / SFD-BMD page and become read-only."
                    ),
                )

                selected_mode_preview = "design" if use_calculated_actions else "manual"
                actions_mode_preview = legacy_design if selected_mode_preview == "design" else legacy_manual
                if actions_mode_preview == legacy_design:
                    st.caption("Design actions: From SFD/BMD")
                else:
                    st.caption("Design actions: Manual inputs")

                preview_mode = st.session_state.get("loads_edit_mode", "ULS")
                toggle_widget_key = get_widget_key_for_shared("loads_edit_toggle", prefix="inputs_") or "inputs_loads_edit_toggle"
                edit_sls = st.toggle(
                    "View SLS loads",
                    key=toggle_widget_key,
                    help="Toggle which load set is shown below. ULS drives bending/shear; SLS drives crack/deflection.",
                )
                preview_mode = "SLS" if edit_sls else "ULS"
                preview_action_verb = "viewing" if selected_mode_preview == "design" else "editing"
                st.caption(f"Currently {preview_action_verb}: **{preview_mode}** loads")

        selected_mode = "design" if use_calculated_actions else "manual"
        mapped_source = legacy_design if selected_mode == "design" else legacy_manual

        source_changed = st.session_state.get("actions_source") != mapped_source
        mode_changed = st.session_state.get("actions_mode") != selected_mode

        if source_changed:
            st.session_state["actions_source"] = mapped_source

        if mode_changed:
            st.session_state["actions_mode"] = selected_mode

        if source_changed or mode_changed:
            # region agent log
            _agent_debug_log(
                "Actions source triggered rerun",
                {
                    "source_changed": bool(source_changed),
                    "mode_changed": bool(mode_changed),
                    "mapped_source": str(mapped_source),
                    "selected_mode": str(selected_mode),
                },
                location="inputs_page.py:render_inputs:actions_source_rerun",
                hypothesis_id="H19",
            )
            # endregion
            st.session_state["inputs_dirty"] = True
            st.rerun()

        prev_mode = st.session_state.get("loads_edit_mode", "ULS")
        toggle_widget_key = get_widget_key_for_shared("loads_edit_toggle", prefix="inputs_") or "inputs_loads_edit_toggle"
        new_mode = "SLS" if edit_sls else "ULS"

        if new_mode != prev_mode:
            # region agent log
            _agent_debug_log(
                "Loads edit mode triggered rerun",
                {
                    "previous_mode": str(prev_mode),
                    "new_mode": str(new_mode),
                },
                location="inputs_page.py:render_inputs:loads_mode_rerun",
                hypothesis_id="H19",
            )
            # endregion
            previous_prefix = "sls" if str(prev_mode).upper() == "SLS" else "uls"
            _commit_design_action_widgets_to_shared(previous_prefix)
            st.session_state["loads_edit_mode"] = new_mode
            _mirror_design_action_proxies_from_shared("sls" if str(new_mode).upper() == "SLS" else "uls")
            st.session_state["_force_design_action_widget_hydrate"] = True
            st.session_state["inputs_dirty"] = True
            st.rerun()
        else:
            st.session_state["loads_edit_mode"] = new_mode

        if user_intent_pending:
            st.session_state[_itk_calculated_intent] = False

        design_controls = is_design_governing()
        if design_controls:
            st.info("Locked: Loads are controlled by the Design page (SFD/BMD). Edit loads there.")

        selected_mode = st.session_state.get("loads_edit_mode", "ULS")
        selected_prefix = "sls" if selected_mode == "SLS" else "uls"
        force_design_action_hydrate = bool(st.session_state.pop("_force_design_action_widget_hydrate", False))
        _hydrate_design_action_widgets_from_shared(
            selected_prefix,
            force=force_design_action_hydrate,
            design_controls=design_controls,
        )

        for spec in _design_action_widget_specs(selected_prefix):
            shared_key = str(spec.get("shared_key", ""))
            if not inputs_detailed_mode and (
                shared_key == "P_star" or shared_key.endswith("_Mstar_neg_manual")
            ):
                continue
            callback = _make_design_action_widget_callback(
                str(spec["widget_key"]),
                shared_key,
                spec.get("proxy_key"),
            )
            _render_design_action_number_row(
                label=str(spec["label"]),
                widget_key=str(spec["widget_key"]),
                help_text=str(spec["help_text"]),
                on_change=callback,
                disabled=bool(spec["disabled_in_design_mode"]) and design_controls,
            )

        _debug_check_design_action_consistency(_shared_state_snapshot())

    with geometry_slot:
        # --- Geometry (+ materials in fast mode) ---
        _render_recommendation_section_header(
            "Geometry & Materials" if not inputs_detailed_mode else "Geometry",
            help_text=(
                "Show the current geometry recommendation, the optimisation goal, "
                "the predicted impact, and apply the suggested geometry."
            ),
            level="h2",
            render_popover_content=lambda: _render_geometry_recommendation_panel(
                button_key="inputs_apply_geometry_recommendation",
                source="fast_mode:geometry_recommendation" if not inputs_detailed_mode else "detailed_mode:geometry_recommendation",
                compact=not inputs_detailed_mode,
            ),
        )

        shape_options = ["RECT", "T", "I"]
        sec_shape_current = st.session_state.get("sec_shape", "RECT")
        if sec_shape_current not in shape_options:
            sec_shape_current = "RECT"

        select_row(
            "Section shape",
            "inputs_sec_shape",
            shape_options,
            sec_shape_current,
            sync_callbacks,
            help_text="Select section type. Geometry inputs below update based on this selection.",
        )

        D_val = float(st.session_state.get("inputs_D", get_param("D", 600.0)))
        L_val = float(st.session_state.get("inputs_L", get_param("L", 3000.0)))
        cover_side_val = float(st.session_state.get("inputs_cover_side", get_param("cover_side", 40.0)))
        sec_shape = st.session_state.get("inputs_sec_shape", st.session_state.get("sec_shape", "RECT"))

        if sec_shape == "RECT":
            b_val = float(st.session_state.get("inputs_b", get_param("b", 400.0)))
            number_row(
                "Width b (mm)",
                "inputs_b",
                b_val,
                sync_callbacks,
                help_text="Rectangular section width.",
            )

        elif sec_shape == "T":
            bf_val = float(st.session_state.get("inputs_bf", get_param("bf", 600.0)))
            tf_val = float(st.session_state.get("inputs_tf", get_param("tf", 120.0)))
            bw_val = float(st.session_state.get("inputs_bw", get_param("bw", 300.0)))

            number_row("Flange width bf (mm)", "inputs_bf", bf_val, sync_callbacks)
            number_row("Flange thickness tf (mm)", "inputs_tf", tf_val, sync_callbacks)
            number_row("Web width bw (mm)", "inputs_bw", bw_val, sync_callbacks, help_text="Stem/web width for T section.")

        elif sec_shape == "I":
            bf_val = float(st.session_state.get("inputs_bf", get_param("bf", 600.0)))
            tf_val = float(st.session_state.get("inputs_tf", get_param("tf", 120.0)))
            tw_val = float(st.session_state.get("inputs_tw", get_param("tw", 200.0)))

            number_row("Top flange width bf (mm)", "inputs_bf", bf_val, sync_callbacks)
            number_row("Top flange thickness tf (mm)", "inputs_tf", tf_val, sync_callbacks)
            number_row("Web thickness tw (mm)", "inputs_tw", tw_val, sync_callbacks)

        number_row(
            "Depth D (mm)",
            "inputs_D",
            D_val,
            sync_callbacks,
            help_text="Overall section depth from compression face to soffit.",
        )

        number_row(
            "Span L (mm)",
            "inputs_L",
            L_val,
            sync_callbacks,
            help_text="Clear span used for deflection checks.",
        )

        if inputs_detailed_mode:
            number_row(
                "Side cover (mm)",
                "inputs_cover_side",
                cover_side_val,
                sync_callbacks,
                help_text="Clear side cover to longitudinal reinforcement and ducts.",
            )
        if not inputs_detailed_mode:
            _render_inputs_materials_subsection(sync_callbacks, show_heading=False)
    if inputs_detailed_mode and right_diagram is not None:
        with right_diagram:
            with st.container():
                st.markdown('<div class="inputs-diagram-materials-group">', unsafe_allow_html=True)
                _render_section_2d_diagram_block()
                st.markdown('<div style="margin-bottom: 0.35rem;"></div>', unsafe_allow_html=True)
                st.markdown('<div style="margin-top: 0.35rem;"></div>', unsafe_allow_html=True)
                _render_inputs_materials_subsection(sync_callbacks)
                st.markdown("</div>", unsafe_allow_html=True)

    if inputs_detailed_mode:
        page_divider()
    else:
        with model_slot:
            with st.container():
                st.markdown('<div class="inputs-diagram-materials-group">', unsafe_allow_html=True)
                _render_fast_model_block(sync_callbacks)
                st.markdown("</div>", unsafe_allow_html=True)
        page_divider()

    # ============================
    # 2. REINFORCEMENT SECTIONS
    # ============================
    # region agent log
    _agent_debug_log(
        "Reached reinforcement sections",
        {
            "inputs_detailed_mode": bool(inputs_detailed_mode),
            "elapsed_ms": round((time.perf_counter() - render_started_at) * 1000.0, 1),
        },
        location="inputs_page.py:render_inputs:reinforcement_sections",
        hypothesis_id="H18",
    )
    # endregion
    # Three columns: bottom reo | top reo | shear (materials sit under main diagram).
    col_bot_reo, col_top_reo, col_shear_mat = st.columns(3, gap="large")
    _sec_shape_reo_ui = st.session_state.get(
        "inputs_sec_shape", st.session_state.get("sec_shape", "RECT")
    )
    _is_ti_reo_ui = normalized_sec_shape_ui(_sec_shape_reo_ui) in ("T", "I")
    _bot_hdr, _top_hdr = main_longitudinal_reo_pair_labels(
        _sec_shape_reo_ui, variant="inputs_compact" if not inputs_detailed_mode else "inputs_detailed"
    )

    # --- Bottom reo (web for T/I) ---
    with col_bot_reo:
        w_rowgap_bot = get_widget_key_for_shared("rowgap_bot", prefix="inputs_") or "inputs_rowgap_bot"
        seed_widget_from_shared(w_rowgap_bot, "rowgap_bot", 60.0)
        rowgap_bot_val = float(st.session_state.get(w_rowgap_bot, get_param("rowgap_bot", 60.0)))

        _render_recommendation_section_header(
            _bot_hdr,
            help_text=(
                "Show the current bottom (web) reinforcement recommendation, the optimisation goal, "
                "the predicted impact, and apply the suggested arrangement. "
                "For T and I sections this is web steel, not flange bars."
            ),
            level="subheader",
            render_popover_content=lambda: _render_bottom_recommendation_panel(
                button_key="inputs_apply_bottom_recommendation",
                source="fast_mode:bottom_recommendation" if not inputs_detailed_mode else "detailed_mode:bottom_recommendation",
                compact=not inputs_detailed_mode,
            ),
            render_popover_always=lambda: render_longitudinal_reo_row_config_controls(
                page_prefix="inputs",
                section="bot",
                sync_callbacks=sync_callbacks,
                rowgap_widget_key=w_rowgap_bot,
                rowgap_default=rowgap_bot_val,
                rowgap_help_text="Clear vertical gap between Layer 1 and Layer 2 (mm).",
                sec_shape=_sec_shape_reo_ui,
            ),
        )
        if bool(st.session_state.get("_dev_mode")):
            _agent_debug_log(
                "Bottom reo live snapshot before row widgets (dev)",
                {
                    "shared": {
                        "bot1_count": st.session_state.get("bot1_count"),
                        "db_bot_1": st.session_state.get("db_bot_1"),
                        "bot_row_1_bars": st.session_state.get("bot_row_1_bars"),
                        "bot_row_1_dia": st.session_state.get("bot_row_1_dia"),
                    },
                    "widget": {
                        "inputs_bot1_count": st.session_state.get("inputs_bot1_count"),
                        "inputs_db_bot_1": st.session_state.get("inputs_db_bot_1"),
                        "inputs_bot_row_1_bars": st.session_state.get("inputs_bot_row_1_bars"),
                        "inputs_bot_row_1_dia": st.session_state.get("inputs_bot_row_1_dia"),
                    },
                },
                location="inputs_page.py:render_inputs:before_bottom_reo_rows",
                hypothesis_id="H_BOT_REO_WIDGET_ALIGN",
            )
        render_longitudinal_reo_rows(
            page_prefix="inputs",
            section="bot",
            sync_callbacks=sync_callbacks,
            layout_modes=REO_LAYOUT_MODE,
            count_options=REO_COUNTS_0_12,
            spacing_options=REO_SPACINGS,
            dia_options=REO_BAR_DIAS,
            single_column=True,
            sec_shape=_sec_shape_reo_ui,
        )

        cover_bot_val = float(st.session_state.get("inputs_cover_bot", get_param("cover_bot", 40.0)))
        number_row(
            "Bottom cover (mm)",
            "inputs_cover_bot",
            cover_bot_val,
            sync_callbacks,
            help_text=(
                "Clear cover to the bottom web bars. "
                "For T/I sections, flange bottom cover is set with bottom flange reinforcement."
                if _is_ti_reo_ui
                else "Clear cover to the bottom bars."
            ),
        )

    # --- Top reo (web for T/I) ---
    with col_top_reo:
        w_rowgap_top = get_widget_key_for_shared("rowgap_top", prefix="inputs_") or "inputs_rowgap_top"
        seed_widget_from_shared(w_rowgap_top, "rowgap_top", 60.0)
        rowgap_top_val = float(st.session_state.get(w_rowgap_top, st.session_state.get("rowgap_top", 60.0)))

        _render_recommendation_section_header(
            _top_hdr,
            help_text=(
                "Top web longitudinal reinforcement for hogging, load reversal, or compression-side layers "
                "(T/I: stem/web steel, not flange bars). Uses the same row layout model as bottom reinforcement."
            ),
            level="subheader",
            render_popover_content=lambda: (
                st.markdown(
                    "Edit top web bars directly here; values stay in sync with bending, section, and crack checks. "
                    "There is no separate automated top-reo suggestion on this page yet."
                )
            ),
            render_popover_always=lambda: render_longitudinal_reo_row_config_controls(
                page_prefix="inputs",
                section="top",
                sync_callbacks=sync_callbacks,
                rowgap_widget_key=w_rowgap_top,
                rowgap_default=rowgap_top_val,
                rowgap_help_text="Clear vertical gap between Layer 1 and Layer 2 (mm).",
                sec_shape=_sec_shape_reo_ui,
            ),
        )
        render_longitudinal_reo_rows(
            page_prefix="inputs",
            section="top",
            sync_callbacks=sync_callbacks,
            layout_modes=REO_LAYOUT_MODE,
            count_options=REO_COUNTS_0_12,
            spacing_options=REO_SPACINGS,
            dia_options=REO_BAR_DIAS,
            single_column=True,
            sec_shape=_sec_shape_reo_ui,
        )

        cover_top_val = float(st.session_state.get("inputs_cover_top", get_param("cover_top", 40.0)))
        number_row(
            "Top cover (mm)",
            "inputs_cover_top",
            cover_top_val,
            sync_callbacks,
            help_text=(
                "Clear cover to the top web bars. For T/I sections, flange top cover is set with flange reinforcement."
                if _is_ti_reo_ui
                else "Clear cover to the top bars."
            ),
        )

    # --- Shear + Materials (third column) ---
    with col_shear_mat:
        if not inputs_detailed_mode and fast_focus_section == "shear":
            _render_fast_next_hint("Next step: confirm or auto-design the shear reinforcement below.")
        _render_recommendation_section_header(
            "Shear" if not inputs_detailed_mode else "Shear reinforcement",
            help_text=(
                "Show the current shear recommendation, the optimisation goal, "
                "the predicted impact, and apply the suggested links."
            ),
            level="subheader",
            render_popover_content=lambda: _render_shear_recommendation_panel(
                button_key="inputs_apply_shear_recommendation",
                source="fast_mode:shear_recommendation" if not inputs_detailed_mode else "detailed_mode:shear_recommendation",
                compact=not inputs_detailed_mode,
            ),
        )

        # Get widget keys from TAB_KEYS (not hardcoded)
        w_lig_d = get_widget_key_for_shared("lig_d", prefix="inputs_") or "inputs_lig_d"
        w_lig_legs = get_widget_key_for_shared("lig_legs", prefix="inputs_") or "inputs_lig_legs"
        w_s_lig = get_widget_key_for_shared("s_lig", prefix="inputs_") or "inputs_s_lig"
        shared_lig_d = int(_shared_state_snapshot().get("lig_d", 0) or 0)
        shared_lig_legs = int(_shared_state_snapshot().get("lig_legs", 0) or 0)
        shared_s_lig = float(_shared_state_snapshot().get("s_lig", 200.0) or 200.0)
        if corrected_invalid_shear_state:
            _refresh_canonical_shear_widgets(source="render_inputs:corrected_invalid_shear_state")
        else:
            seed_widget_from_shared(w_lig_d, "lig_d", 0)
            seed_widget_from_shared(w_lig_legs, "lig_legs", 2)
            seed_widget_from_shared(w_s_lig, "s_lig", 200.0)
        widget_lig_d = st.session_state.get(w_lig_d)
        widget_lig_legs = st.session_state.get(w_lig_legs)
        widget_s_lig = st.session_state.get(w_s_lig)
        lig_d_val = int(shared_lig_d)
        lig_legs_val = int(shared_lig_legs)
        s_lig_val = float(shared_s_lig)
        if bool(st.session_state.get("_dev_mode")):
            _agent_debug_log(
                "Shear widget/model audit",
                {
                    "shared": {
                        "lig_d": shared_lig_d,
                        "lig_legs": shared_lig_legs,
                        "s_lig": shared_s_lig,
                    },
                    "widgets": {
                        "inputs_lig_d": widget_lig_d,
                        "inputs_lig_legs": widget_lig_legs,
                        "inputs_s_lig": widget_s_lig,
                    },
                    "rendered_values": {
                        "lig_d": lig_d_val,
                        "lig_legs": lig_legs_val,
                        "s_lig": s_lig_val,
                    },
                },
                location="inputs_page.py:render_inputs:shear_widget_audit",
                hypothesis_id="H_SHEAR_WIDGET",
            )

        select_row(
            "Link Ø (mm)",
            w_lig_d,
            {0: "0 (off)"} | {dia: str(dia) for dia in REO_BAR_DIAS},
            int(lig_d_val),
            sync_callbacks,
            help_text="Nominal diameter of shear reinforcement links (mm).",
        )
        select_row(
            "No. of legs",
            w_lig_legs,
            list(range(2, 13)),
            int(lig_legs_val),
            sync_callbacks,
            help_text="Number of legs per shear link (minimum 2 for shear reinforcement).",
        )
        number_row(
            "Link spacing (mm)",
            w_s_lig,
            s_lig_val,
            sync_callbacks,
            help_text="Centre-to-centre spacing of shear links along the member (mm).",
        )

    sec_shape_for_flange = str(st.session_state.get("sec_shape", get_param("sec_shape", "RECT")) or "RECT")
    if sec_shape_for_flange in ("T", "I"):
        st.markdown("### Flange reinforcement")
        st.caption("Only used for T and I sections. Flange groups are resolved into real bar coordinates for crack/shear participation.")
        flange_col_a, flange_col_b = st.columns(2, gap="large")
        with flange_col_a:
            select_row(
                "Enable top flange bars",
                "inputs_top_flange_reo_enabled",
                [False, True],
                bool(st.session_state.get("top_flange_reo_enabled", False)),
                sync_callbacks,
                help_text="Enable explicit top flange reinforcement groups.",
            )
            select_row(
                "Mirror top left/right",
                "inputs_top_flange_mirror_lr",
                [True, False],
                bool(st.session_state.get("top_flange_mirror_lr", True)),
                sync_callbacks,
                help_text="When enabled, the right-side top flange group mirrors the left-side values.",
            )
            number_row("Top flange left bars", "inputs_top_flange_left_count", float(st.session_state.get("top_flange_left_count", 0) or 0), sync_callbacks, help_text="Total bars in top-left flange group.")
            select_row("Top flange left dia (mm)", "inputs_top_flange_left_dia", REO_BAR_DIAS, int(st.session_state.get("top_flange_left_dia", 16) or 16), sync_callbacks)
            number_row("Top flange left rows", "inputs_top_flange_left_rows", float(st.session_state.get("top_flange_left_rows", 1) or 1), sync_callbacks)
            number_row("Top flange left row spacing (mm)", "inputs_top_flange_left_row_spacing", float(st.session_state.get("top_flange_left_row_spacing", 60.0) or 60.0), sync_callbacks)
            select_row(
                "Top flange left clear spacing mode",
                "inputs_top_flange_left_clear_spacing_mode",
                ["count", "spacing"],
                str(st.session_state.get("top_flange_left_clear_spacing_mode", "count") or "count"),
                sync_callbacks,
            )
            if not bool(st.session_state.get("top_flange_mirror_lr", True)):
                number_row("Top flange right bars", "inputs_top_flange_right_count", float(st.session_state.get("top_flange_right_count", 0) or 0), sync_callbacks)
                select_row("Top flange right dia (mm)", "inputs_top_flange_right_dia", REO_BAR_DIAS, int(st.session_state.get("top_flange_right_dia", 16) or 16), sync_callbacks)
                number_row("Top flange right rows", "inputs_top_flange_right_rows", float(st.session_state.get("top_flange_right_rows", 1) or 1), sync_callbacks)
                number_row("Top flange right row spacing (mm)", "inputs_top_flange_right_row_spacing", float(st.session_state.get("top_flange_right_row_spacing", 60.0) or 60.0), sync_callbacks)
                select_row(
                    "Top flange right clear spacing mode",
                    "inputs_top_flange_right_clear_spacing_mode",
                    ["count", "spacing"],
                    str(st.session_state.get("top_flange_right_clear_spacing_mode", "count") or "count"),
                    sync_callbacks,
                )
        with flange_col_b:
            select_row(
                "Enable bottom flange bars",
                "inputs_bot_flange_reo_enabled",
                [False, True],
                bool(st.session_state.get("bot_flange_reo_enabled", False)),
                sync_callbacks,
                help_text="Enable explicit bottom flange reinforcement groups (I-sections only; ignored for T bottom flange).",
            )
            select_row(
                "Mirror bottom left/right",
                "inputs_bot_flange_mirror_lr",
                [True, False],
                bool(st.session_state.get("bot_flange_mirror_lr", True)),
                sync_callbacks,
                help_text="When enabled, the right-side bottom flange group mirrors the left-side values.",
            )
            number_row("Bottom flange left bars", "inputs_bot_flange_left_count", float(st.session_state.get("bot_flange_left_count", 0) or 0), sync_callbacks)
            select_row("Bottom flange left dia (mm)", "inputs_bot_flange_left_dia", REO_BAR_DIAS, int(st.session_state.get("bot_flange_left_dia", 20) or 20), sync_callbacks)
            number_row("Bottom flange left rows", "inputs_bot_flange_left_rows", float(st.session_state.get("bot_flange_left_rows", 1) or 1), sync_callbacks)
            number_row("Bottom flange left row spacing (mm)", "inputs_bot_flange_left_row_spacing", float(st.session_state.get("bot_flange_left_row_spacing", 60.0) or 60.0), sync_callbacks)
            select_row(
                "Bottom flange left clear spacing mode",
                "inputs_bot_flange_left_clear_spacing_mode",
                ["count", "spacing"],
                str(st.session_state.get("bot_flange_left_clear_spacing_mode", "count") or "count"),
                sync_callbacks,
            )
            if not bool(st.session_state.get("bot_flange_mirror_lr", True)):
                number_row("Bottom flange right bars", "inputs_bot_flange_right_count", float(st.session_state.get("bot_flange_right_count", 0) or 0), sync_callbacks)
                select_row("Bottom flange right dia (mm)", "inputs_bot_flange_right_dia", REO_BAR_DIAS, int(st.session_state.get("bot_flange_right_dia", 20) or 20), sync_callbacks)
                number_row("Bottom flange right rows", "inputs_bot_flange_right_rows", float(st.session_state.get("bot_flange_right_rows", 1) or 1), sync_callbacks)
                number_row("Bottom flange right row spacing (mm)", "inputs_bot_flange_right_row_spacing", float(st.session_state.get("bot_flange_right_row_spacing", 60.0) or 60.0), sync_callbacks)
                select_row(
                    "Bottom flange right clear spacing mode",
                    "inputs_bot_flange_right_clear_spacing_mode",
                    ["count", "spacing"],
                    str(st.session_state.get("bot_flange_right_clear_spacing_mode", "count") or "count"),
                    sync_callbacks,
                )
        st.markdown("#### Flange transverse detailing (optional)")
        st.caption("Detailing/distribution reinforcement in flange regions only. Not used in primary web shear capacity.")
        tr_col1, tr_col2 = st.columns(2, gap="large")
        with tr_col1:
            select_row("Enable top flange transverse", "inputs_top_flange_transverse_enabled", [False, True], bool(st.session_state.get("top_flange_transverse_enabled", False)), sync_callbacks)
            select_row("Top flange transverse dia (mm)", "inputs_top_flange_transverse_dia", REO_BAR_DIAS, int(st.session_state.get("top_flange_transverse_dia", 10) or 10), sync_callbacks)
            number_row("Top flange transverse spacing (mm)", "inputs_top_flange_transverse_spacing", float(st.session_state.get("top_flange_transverse_spacing", 200.0) or 200.0), sync_callbacks)
            number_row("Top flange transverse legs", "inputs_top_flange_transverse_legs", float(st.session_state.get("top_flange_transverse_legs", 2) or 2), sync_callbacks)
        with tr_col2:
            select_row("Enable bottom flange transverse", "inputs_bot_flange_transverse_enabled", [False, True], bool(st.session_state.get("bot_flange_transverse_enabled", False)), sync_callbacks)
            select_row("Bottom flange transverse dia (mm)", "inputs_bot_flange_transverse_dia", REO_BAR_DIAS, int(st.session_state.get("bot_flange_transverse_dia", 10) or 10), sync_callbacks)
            number_row("Bottom flange transverse spacing (mm)", "inputs_bot_flange_transverse_spacing", float(st.session_state.get("bot_flange_transverse_spacing", 200.0) or 200.0), sync_callbacks)
            number_row("Bottom flange transverse legs", "inputs_bot_flange_transverse_legs", float(st.session_state.get("bot_flange_transverse_legs", 2) or 2), sync_callbacks)
    page_divider()

    # ============================
    # 3. Support / materials / shear params + 3D diagram (below Reo section; detailed only)
    # ============================
    if inputs_detailed_mode:
        _render_materials_and_sectionA_2d(sync_callbacks)
        page_divider()

    # Structural recomputation (recalc_derived_values, update_results, compute_*) runs in app.py
    # when inputs_dirty is set by sync callbacks or beam load, then cached_results is refreshed.

    # ============================
    # 2. LOWER ROW – Time-dependent | Ducts / Prestress voids | Crack control
    # ============================
    if inputs_detailed_mode:
        col_td, col_ducts, col_crack = st.columns([1.15, 1.0, 0.85], gap="large")

        with col_td:
            _render_time_dependent_inputs(sync_callbacks)

        with col_ducts:
            _render_ducts_prestress_voids_inputs(sync_callbacks)

        # --- Column 3: Crack Control Inputs ---
        with col_crack:
            st.subheader("Crack Control Inputs")

            options = ["A1", "A2", "B1", "B2", "C1", "C2"]

            current = get_param("exposure_class", "B1")

            if current not in options:
                current = "B1"

            col_exp_label, col_exp_input = st.columns([1, 2])
            with col_exp_label:
                label_with_hover("Exposure class", "Exposure classification to AS 3600 – controls allowable crack width.")
            with col_exp_input:
                if "inputs_exposure_class" in st.session_state:
                    st.selectbox(
                        "Exposure class",
                        options,
                        key="inputs_exposure_class",
                        on_change=sync_callbacks["inputs_exposure_class"],
                        label_visibility="collapsed",
                    )
                else:
                    st.selectbox(
                        "Exposure class",
                        options,
                        key="inputs_exposure_class",
                        index=options.index(current),
                        on_change=sync_callbacks["inputs_exposure_class"],
                        label_visibility="collapsed",
                    )

            # ----------------------------
            # Crack criteria (shared inputs)
            # ----------------------------
            
            # Resultant action / member type
            member_options = ["Primarily flexure", "Primarily tension"]
            member_current = st.session_state.get("crack_member_type", "Primarily flexure")

            col1, col2 = st.columns([1, 2])
            with col1:
                label_with_hover(
                    "Resultant action",
                    "Affects default k₂ assumption and crack model interpretation.",
                )
            with col2:
                st.selectbox(
                    "Resultant action",
                    options=member_options,
                    index=member_options.index(member_current) if member_current in member_options else 0,
                    key="inputs_crack_member_type",
                    on_change=sync_callbacks["inputs_crack_member_type"],
                    label_visibility="collapsed",
                )

            # k1 (bond coefficient)
            k1_options = [0.8, 1.6]
            k1_current = float(st.session_state.get("crack_k1", 0.8))

            col1, col2 = st.columns([1, 2])
            with col1:
                label_with_hover(
                    "k₁ (bond coefficient)",
                    "0.8 for deformed bars, 1.6 for plain bars.",
                )
            with col2:
                st.selectbox(
                    "k1",
                    options=k1_options,
                    index=k1_options.index(k1_current) if k1_current in k1_options else 0,
                    format_func=lambda x: "Deformed bars (k₁ = 0.8)" if abs(x - 0.8) < 1e-9 else "Plain bars (k₁ = 1.6)",
                    key="inputs_crack_k1",
                    on_change=sync_callbacks["inputs_crack_k1"],
                    label_visibility="collapsed",
                )

            # k2 (strain distribution factor) – keep editable
            # default follows member type but only as a seed (State-Lab handles persistence)
            k2_seed = 0.5 if member_current == "Primarily flexure" else 1.0
            number_row(
                "k₂ (strain distribution factor)",
                "inputs_crack_k2",
                float(st.session_state.get("crack_k2", k2_seed)),
                sync_callbacks,
                help_text="Default 0.5 for flexure, 1.0 for tension. Adjust only if using a different assumed strain distribution.",
            )

            # Note: Ducts / Prestress voids section moved alongside Crack control
            # Note: Serviceability + Shrinkage split between Support conditions and Time-dependent inputs

    # ============================
    # 4. Rest of inputs (Time | Crack/Ducts) — compute owned by app.py when inputs_dirty
    # ============================
    skip_active_beam_record_write = bool(st.session_state.get("_beam_skip_auto_persist_once", False))
    if skip_active_beam_record_write:
        st.session_state["_beam_skip_auto_persist_once"] = False
    else:
        persist_active_beam_from_shared()

    # --- Auto-computed summary rows (deflection-style) ---
    bend_pack = hc_try("summary.build_bending_pack", lambda: build_bending_check_rows_from_state(st.session_state))
    shear_pack = hc_try("summary.build_shear_pack", lambda: build_shear_check_rows_from_state(st.session_state))
    crack_pack = hc_try("summary.build_crack_pack", lambda: build_crack_check_rows_from_state(st.session_state))
    defl_pack = hc_try("summary.build_deflection_pack", lambda: build_deflection_check_rows_from_state(st.session_state))
    # region agent log
    _agent_debug_log(
        "Built summary packs",
        {
            "inputs_detailed_mode": bool(inputs_detailed_mode),
            "bend_pack_none": bend_pack is None,
            "shear_pack_none": shear_pack is None,
            "crack_pack_none": crack_pack is None,
            "defl_pack_none": defl_pack is None,
            "elapsed_ms": round((time.perf_counter() - render_started_at) * 1000.0, 1),
        },
        location="inputs_page.py:render_inputs:summary_packs",
        hypothesis_id="H24",
    )
    # endregion

    hc_log(
        "summary.pack_meta",
        bending=_pack_meta("bending", bend_pack),
        shear=_pack_meta("shear", shear_pack),
        crack=_pack_meta("crack", crack_pack),
        deflection=_pack_meta("deflection", defl_pack),
    )

    hc_log(
        "state.snapshot",
        keys_count=len(st.session_state.keys()),
        has_actions_uls=isinstance(st.session_state.get("actions_uls"), dict),
        sample_keys=sorted(list(st.session_state.keys()))[:120],
    )

    bend_err = bend_pack is None
    shear_err = shear_pack is None
    crack_err = crack_pack is None
    defl_err = defl_pack is None

    BENDING_ROWS = [_normalise_row(r, "bending") for r in (bend_pack or {}).get("rows") or []]
    _sp = shear_pack or {}
    _shear_summary_src = _sp.get("summary_rows")
    _shear_mcft_src = _sp.get("mcft_detail_rows")
    if _shear_summary_src is not None and _shear_mcft_src is not None:
        _shear_display_list = list(_shear_summary_src)
        if st.session_state.get("show_mcft_breakdown", False):
            _shear_display_list.extend(_shear_mcft_src)
        SHEAR_ROWS = [_normalise_row(r, "shear") for r in _shear_display_list]
    else:
        SHEAR_ROWS = [_normalise_row(r, "shear") for r in _sp.get("rows") or []]
    CRACK_ROWS = [_normalise_row(r, "crack") for r in (crack_pack or {}).get("rows") or []]
    if bend_err:
        BENDING_ROWS = [{
            "uid": "bend_error",
            "title": "Bending checks failed",
            "value": "—",
            "limit": "—",
            "util": "—",
            "status": "—",
            "route_page": "bending",
        }]
    if shear_err:
        SHEAR_ROWS = [{
            "uid": "shear_error",
            "title": "Shear checks failed",
            "value": "—",
            "limit": "—",
            "util": "—",
            "status": "—",
            "route_page": "shear",
        }]
    if crack_err:
        CRACK_ROWS = [{
            "uid": "crack_error",
            "title": "Crack checks failed",
            "value": "—",
            "limit": "—",
            "util": "—",
            "status": "—",
            "route_page": "crack",
        }]

    DEFLECTION_ROWS = [_normalise_row(r, "deflection") for r in (defl_pack or {}).get("rows") or []]

    if defl_err:
        DEFLECTION_ROWS = [{
            "uid": "defl_error",
            "title": "Deflection checks failed",
            "value": "—",
            "limit": "—",
            "util": "—",
            "status": "—",
            "route_page": "deflection",
        }]
        delta_total = 0.0
        defl_limit = 0.0
        defl_util = None
    else:
        defl_summary = defl_pack or {}
        delta_total = float(defl_summary.get("summary_delta_total_mm") or 0.0)
        defl_limit = float(defl_summary.get("summary_defl_limit_mm") or 0.0)
        defl_util = defl_summary.get("summary_util_total")

    bending_primary = _primary_row(BENDING_ROWS) or {}
    shear_primary = _primary_row(SHEAR_ROWS) or {}
    crack_primary = pick_governing_check_row(CRACK_ROWS) or next(
        (r for r in CRACK_ROWS if not r.get("is_informational")),
        {},
    ) or {}
    defl_primary = _primary_row(DEFLECTION_ROWS) or {}

    bending_cap = bending_primary.get("capacity") or bending_primary.get("value", "—")
    bending_demand = bending_primary.get("action") or bending_primary.get("limit", "—")
    bending_util_str = bending_primary.get("util", "—")
    bending_status, bending_colour = _overall_status_from_rows(BENDING_ROWS)

    shear_cap = shear_primary.get("capacity") or shear_primary.get("value", "—")
    shear_demand = shear_primary.get("action") or shear_primary.get("limit", "—")
    shear_util_str = shear_primary.get("util", "—")
    shear_status, shear_colour = _overall_status_from_rows(SHEAR_ROWS)

    crack_cap = crack_primary.get("capacity") or crack_primary.get("value", "—")
    crack_demand = crack_primary.get("action") or crack_primary.get("limit", "—")
    crack_util_str = crack_primary.get("util", "—")
    crack_status, crack_colour = _overall_status_from_rows(CRACK_ROWS)

    defl_cap = defl_primary.get("capacity") or defl_primary.get("value", "—")
    defl_demand = defl_primary.get("action") or defl_primary.get("limit", "—")
    defl_util_str = defl_primary.get("util", "—")
    defl_status, defl_colour = _overall_status_from_rows(DEFLECTION_ROWS)
    _summary_state = _shared_state_snapshot()
    _summary_fp = _design_guide_cache_fingerprint(_summary_state)
    summary_guidance_items, _, _summary_guidance_cache_hit = _get_cached_design_guide_guidance(_summary_fp)
    if not _summary_guidance_cache_hit:
        summary_guidance_items = _compute_design_guidance_items(
            _summary_state,
            debug_sink=None,
            guidance_debug_verbose=False,
        )
    governing_check = summary_guidance_items[0].get("check_key") if summary_guidance_items else None

    # Helper function to convert status string to ok boolean for render_clickable_summary_table
    def _status_to_ok(status_str):
        """Convert status string to ok boolean: True=pass, False=fail, None=neutral"""
        if status_str == "PASS":
            return True
        elif status_str in ("FAIL", "NEAR LIMIT"):
            return False
        else:
            return None

    # Helper function to generate summary table HTML as string (for embedding in details)
    def _generate_summary_table_html(rows):
        """Generate the summary table HTML as a string (same format as render_clickable_summary_table)"""
        html_parts = ['<div class="summary-wrap"><table class="summary-table">']
        html_parts.append(
            """
<thead>
<tr>
  <th style="width:30%">Check</th>
  <th style="width:24%">Calculated capacity</th>
  <th style="width:24%">Applied design action</th>
  <th style="width:8%">Util</th>
  <th style="width:14%">Status</th>
</tr>
</thead>
<tbody>
"""
        )
        
        for r in rows:
            uid = r["uid"]
            check = r.get("title") or r.get("check", uid)
            value = summary_cell_display(r, "capacity")
            limit = summary_cell_display(r, "action")
            util = r.get("util", "")
            status = r.get("status", "")
            ok = r.get("ok")
            tab = r.get("tab", "")
            
            status_norm = str(status).upper()
            if r.get("is_informational") or status_norm == "INFO":
                cls = ""
            else:
                cls = (
                    "pass" if ok is True
                    else "fail" if ok is False
                    else "warn" if status_norm in ("NEAR LIMIT", "WARN", "CHECK")
                    else ""
                )
            primary = "primary" if r.get("is_primary") else ""
            row_class = f"{cls} {primary}".strip()
            
            jt = resolve_jump_target_id(r)
            route_pg = (r.get("route_page") or "").strip()
            jump_qp = str(jt).strip() if jt is not None else ""
            if not jump_qp:
                jump_qp = str(uid)
            _qp = {"page": route_pg, "jump": jump_qp}
            if str(uid) and str(uid) != jump_qp:
                _qp["jump_row"] = str(uid)
            nav_href = "?" + urlencode(_qp) if route_pg else "#"
            html_parts.append(
                f"""
<tr class="{row_class}" data-tab="{html.escape(str(tab), quote=True)}">
  <td>
    {check} <span class="hint">↳ jump to calc</span>
    <a class="row-link" href="{html.escape(nav_href, quote=True)}" data-uid="{html.escape(str(uid), quote=True)}" data-jump-target="{html.escape(str(jt), quote=True)}" data-tab="{html.escape(str(tab), quote=True)}"></a>
  </td>
  <td>{value}</td>
  <td>{limit}</td>
  <td>{util}</td>
  <td>{status}</td>
</tr>
"""
            )
        
        html_parts.append("</tbody></table></div>")
        return "".join(html_parts)

    for rows, route in (
        (BENDING_ROWS, "bending"),
        (SHEAR_ROWS, "shear"),
        (CRACK_ROWS, "crack"),
        (DEFLECTION_ROWS, "deflection"),
    ):
        for r in rows:
            if r.get("is_informational") or str(r.get("status", "")).upper() == "INFO":
                r["ok"] = None
            elif "ok" not in r:
                status = r.get("status", "—")
                r["ok"] = True if status == "PASS" else False if status in ("FAIL", "NG", "NEAR LIMIT") else None
            r.setdefault("route_page", route)
            uid = str(r.get("uid") or "")
            if not r.get("tab"):
                if route == "bending" and uid in BENDING_ROW_UID_TO_TAB:
                    r["tab"] = BENDING_ROW_UID_TO_TAB[uid]
                elif route == "shear" and uid in SHEAR_ROW_UID_TO_TAB:
                    r["tab"] = SHEAR_ROW_UID_TO_TAB[uid]

    if not skip_active_beam_record_write:
        update_active_beam_summary_from_results(
            bending_rows=BENDING_ROWS,
            shear_rows=SHEAR_ROWS,
            crack_rows=CRACK_ROWS,
            deflection_rows=DEFLECTION_ROWS,
        )

    def _render_inputs_summary_expanders_and_tables() -> None:
        # Inject CSS for seamless steps (summary table styling)
        inject_seamless_steps_css()

        if not BENDING_ROWS:
            st.info("Bending results not available yet. Check inputs or visit Bending page for details.")
        if not SHEAR_ROWS:
            st.info("Shear results not available yet. Check inputs or visit Shear page for details.")
        if not CRACK_ROWS:
            st.info("Crack results not available yet. Check inputs or visit Crack Control page for details.")
        if not DEFLECTION_ROWS:
            st.info("Deflection results not available yet. Check inputs or visit Deflection page for details.")

        # Custom CSS for top-level expandable rows (matching old design)
        # Includes summary table styling (same as render_clickable_summary_table)
        st.markdown("""
<style>
.inputs-top-level-row {
  border: 1px solid rgba(49,51,63,0.15);
  border-radius: 10px;
  margin-bottom: 0.5rem;
  overflow: hidden;
}

.inputs-top-level-row details {
  margin: 0;
}

.inputs-top-level-row summary {
  padding: 14px;
  cursor: pointer;
  list-style: none;
  font-weight: 600;
  border-bottom: 1px solid rgba(49,51,63,0.1);
  display: grid;
  grid-template-columns: 20% 25% 25% 15% 15%;
  align-items: center;
  gap: 10px;
  user-select: none;
}

.inputs-top-level-row summary::-webkit-details-marker {
  display: none;
}

.inputs-top-level-row summary::marker {
  content: "";
}

.inputs-top-level-row details[open] summary {
  border-bottom: 1px solid rgba(49,51,63,0.1);
}

.inputs-top-level-row.governing summary {
  box-shadow: inset 4px 0 0 rgba(15,23,42,0.52), 0 0 0 1px rgba(15,23,42,0.10);
  filter: saturate(1.03);
}

.inputs-top-level-row .details-content {
  padding: 1rem;
  background: white;
  max-height: 500px;
  overflow-y: auto;
  overflow-x: hidden;
}

.inputs-top-level-row details:not([open]) .details-content {
  display: none;
}

/* Summary table styling (from render_clickable_summary_table) */
.summary-wrap {
  border: 1px solid rgba(49,51,63,0.15);
  border-radius: 10px;
  overflow: hidden;
}

.summary-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 16px;
}

.summary-table th {
  background: rgba(49,51,63,0.05);
  text-align: left;
  padding: 14px;
  color: rgba(49,51,63,0.7);
}

.summary-table td {
  padding: 14px;
  border-top: 1px solid rgba(49,51,63,0.1);
  position: relative;
}

/* Default neutral background (matches calcbox blue) - only for rows without pass/fail/warn classes */
.summary-table tbody tr:not(.pass):not(.fail):not(.warn) td {
  background: rgba(31, 119, 180, 0.08);
}

tr.pass td { background: rgba(0,128,0,0.12); }
tr.fail td { background: rgba(255,0,0,0.12); }
tr.warn td { background: rgba(255,193,7,0.15); }

tr.primary td {
  font-weight: 700;
}

tr:hover td { background: rgba(0,0,0,0.04); }

.row-link {
  position: absolute;
  inset: 0;
  z-index: 5;
  display: block;
  cursor: pointer;
}

.hint {
  opacity: 0;
  font-size: 0.9em;
  margin-left: 6px;
  color: rgba(49,51,63,0.6);
}
tr:hover .hint { opacity: 1; }
</style>
""", unsafe_allow_html=True)

        # Top-level expandable rows with summary results
        # Generate table HTML strings
        bending_table_html = _generate_summary_table_html(BENDING_ROWS)
        shear_table_html = _generate_summary_table_html(SHEAR_ROWS)
        crack_table_html = _generate_summary_table_html(CRACK_ROWS)
        defl_summary = defl_pack or {}
        defl_table_html = _generate_summary_table_html(DEFLECTION_ROWS)
        
        # Bending
        st.markdown(
            f"""
<div class="inputs-top-level-row{' governing' if governing_check == 'bending' else ''}">
<details>
<summary style="background-color: {bending_colour};">
  <span><strong>Bending — ULS check</strong></span>
  <span style="text-align:right;"><span style="font-size:0.78rem;opacity:0.72;display:block;">Calculated capacity</span>{bending_cap}</span>
  <span style="text-align:right;"><span style="font-size:0.78rem;opacity:0.72;display:block;">Applied design action</span>{bending_demand}</span>
  <span style="text-align:right;">{bending_util_str}</span>
  <span style="text-align:center;">{bending_status}</span>
    </summary>
<div class="details-content">
{bending_table_html}
</div>
  </details>
      </div>
""",
        unsafe_allow_html=True,
        )

        # Shear
        st.markdown(
            f"""
<div class="inputs-top-level-row{' governing' if governing_check == 'shear' else ''}">
<details>
<summary style="background-color: {shear_colour};">
  <span><strong>Shear — ULS check</strong></span>
  <span style="text-align:right;"><span style="font-size:0.78rem;opacity:0.72;display:block;">Calculated capacity</span>{shear_cap}</span>
  <span style="text-align:right;"><span style="font-size:0.78rem;opacity:0.72;display:block;">Applied design action</span>{shear_demand}</span>
  <span style="text-align:right;">{shear_util_str}</span>
  <span style="text-align:center;">{shear_status}</span>
    </summary>
<div class="details-content">
{shear_table_html}
</div>
  </details>
      </div>
""",
        unsafe_allow_html=True,
        )

        # Crack
        st.markdown(
        f"""
<div class="inputs-top-level-row{' governing' if governing_check == 'crack' else ''}">
<details>
<summary style="background-color: {crack_colour};">
  <span><strong>Crack control — SLS check</strong></span>
  <span style="text-align:right;"><span style="font-size:0.78rem;opacity:0.72;display:block;">Calculated capacity</span>{crack_cap}</span>
  <span style="text-align:right;"><span style="font-size:0.78rem;opacity:0.72;display:block;">Applied design action</span>{crack_demand}</span>
  <span style="text-align:right;">{crack_util_str}</span>
  <span style="text-align:center;">{crack_status}</span>
    </summary>
<div class="details-content">
{crack_table_html}
</div>
  </details>
      </div>
""",
        unsafe_allow_html=True,
        )

        # Deflection
        st.markdown(
        f"""
<div class="inputs-top-level-row{' governing' if governing_check == 'deflection' else ''}">
<details>
<summary style="background-color: {defl_colour};">
  <span><strong>Deflection — SLS check</strong></span>
  <span style="text-align:right;"><span style="font-size:0.78rem;opacity:0.72;display:block;">Calculated capacity</span>{defl_cap}</span>
  <span style="text-align:right;"><span style="font-size:0.78rem;opacity:0.72;display:block;">Applied design action</span>{defl_demand}</span>
  <span style="text-align:right;">{defl_util_str}</span>
  <span style="text-align:center;">{defl_status}</span>
    </summary>
<div class="details-content">
{defl_table_html}
</div>
  </details>
</div>
""",
        unsafe_allow_html=True,
        )

        page_divider()

    def render_summary_table(results):
        _ = results
        _render_inputs_summary_expanders_and_tables()

    # Render the summary back at the very top (where summary_container was created)
    with summary_container:
        st.title("Inputs")
        results = st.session_state.get(RESULT_CACHE_KEY)
        if results is None:
            st.info("Enter design actions to generate results")
        else:
            render_summary_table(results)

    if bool(st.session_state.get("_dev_mode")):
        _agent_debug_log(
            "Inputs dev render audit (end of render_inputs)",
            {
                "old_auto_design_panel_rendered": inputs_render_audit["old_auto_design_panel_rendered"],
                "design_guide_rendered": inputs_render_audit["design_guide_rendered"],
                "current_design_summary_rendered": inputs_render_audit["current_design_summary_rendered"],
                "next_mode_recommendation_rendered": inputs_render_audit["next_mode_recommendation_rendered"],
                "bottom_tightening_rendered": inputs_render_audit["bottom_tightening_rendered"],
                "geometry_tightening_rendered": inputs_render_audit["geometry_tightening_rendered"],
                "shear_tightening_rendered": inputs_render_audit["shear_tightening_rendered"],
            },
            location="inputs_page.py:render_inputs:dev_render_audit_end",
            hypothesis_id="H_INPUTS_DEV_RENDER_AUDIT",
        )

    if _INPUTS_DEBUG_AUDIT and before_state is not None:
        after_widgets_state = st.session_state
        for key in before_state:
            if before_state[key] != after_widgets_state.get(key):
                log_debug(
                    f"STATE CHANGED DURING RENDER - {key}",
                    f"{before_state[key]} -> {after_widgets_state.get(key)}",
                )
        tab_keys = list(INPUTS_PAGE_TAB_KEYS.values())
        for key in SHARED_DEFAULTS.keys():
            if key not in tab_keys:
                if before_state.get(key) != after_widgets_state.get(key):
                    log_debug(
                        f"WARNING: DIRECT SHARED WRITE - {key}",
                        f"{before_state.get(key)} -> {after_widgets_state.get(key)}",
                    )
        log_debug("---- INPUTS PAGE LOAD END ----")

    _render_design_guide_debug_sidebar()

