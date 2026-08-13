import os, sys
ROOT = os.path.dirname(os.path.abspath(__file__))
# Runtime is the canonical application source.  Keep it ahead of editable
# installs and earlier development checkouts so similarly named page modules
# cannot be resolved from a stale workspace.
while ROOT in sys.path:
    sys.path.remove(ROOT)
sys.path.insert(0, ROOT)


def _local_trace_log_path(filename: str) -> str:
    """Keep diagnostic tracing off OneDrive's online-only placeholder files.

    The project contains very large historical JSONL traces.  Opening one of
    those placeholders for append can make Streamlit appear stuck at
    ``Running...`` while OneDrive hydrates the entire file.  Diagnostic logs
    are non-functional, so write the current run to a local temp directory.
    """

    log_root = os.path.join(os.environ.get("TEMP", os.path.dirname(ROOT)), "complete-app-traces")
    os.makedirs(log_root, exist_ok=True)
    return os.path.join(log_root, filename)


class _SafeConsoleStream:
    """Best-effort console stream wrapper for detached Streamlit runs."""

    _design_safe_console_stream = True

    def __init__(self, stream):
        self._stream = stream
        self.encoding = getattr(stream, "encoding", None)
        self.errors = getattr(stream, "errors", None)

    def write(self, value):
        try:
            return self._stream.write(value)
        except Exception:
            return len(value) if isinstance(value, str) else 0

    def flush(self):
        try:
            return self._stream.flush()
        except Exception:
            return None

    def __getattr__(self, name):
        return getattr(self._stream, name)


def _install_safe_console_streams() -> None:
    for name in ("stdout", "stderr"):
        stream = getattr(sys, name, None)
        if stream is not None and not getattr(stream, "_design_safe_console_stream", False):
            setattr(sys, name, _SafeConsoleStream(stream))


_install_safe_console_streams()

import copy
import hashlib
import importlib
import json
import streamlit as st
import time

from application.engineering_snapshot import build_engineering_input_snapshot_from_resolved_state
from application.guidance_result_adapter import guidance_payload_from_authoritative_design_result
from inputs_application.session_services import InputsSessionServices
from application.v2_runtime_warmup import start_v2_runtime_warmup

st.set_page_config(
    page_title="Concrete Beam Design",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# Import the installed calculation and Design Brain contracts while the first
# page is being composed.  This removes their cold import penalty from the
# user's first engineering edit without performing any engineering work or
# touching Streamlit session state.
start_v2_runtime_warmup()


def _apply_sharp_embed_css() -> None:
    """Keep the embedded app sharp by sizing the Streamlit UI, not the iframe."""
    st.markdown(
        """
<style>
  html, body, [class*="css"] {
    font-size: 14px;
  }

  .stApp {
    background: #ffffff;
  }

  .stApp [data-testid="stMainBlockContainer"],
  .stApp .block-container {
    max-width: 1180px !important;
    padding-top: 2rem !important;
    padding-right: 2.25rem !important;
    padding-left: 2.25rem !important;
    padding-bottom: 2rem !important;
  }

  @media (max-width: 1100px) {
    .stApp [data-testid="stMainBlockContainer"],
    .stApp .block-container {
      padding-right: 1.5rem !important;
      padding-left: 1.5rem !important;
    }
  }

  .stApp h1 {
    font-size: 2rem !important;
    line-height: 1.15 !important;
  }

  .stApp h2 {
    font-size: 1.45rem !important;
  }

  .stApp .stMarkdown h2 {
    font-size: 1.45rem !important;
  }

  .stApp h3 {
    font-size: 1.1rem !important;
  }

  .stApp .stMarkdown h3 {
    font-size: 1.1rem !important;
  }

  .stApp div[data-testid="stMetricValue"] {
    font-size: 1.35rem !important;
  }

  .stApp .stButton button,
  .stApp .stDownloadButton button,
  .stApp div[data-baseweb="select"] > div,
  .stApp input,
  .stApp textarea {
    min-height: 2.2rem !important;
    font-size: 0.9rem !important;
  }

  section[data-testid="stSidebar"] {
    width: 17rem !important;
  }

  section[data-testid="stSidebar"] .block-container {
    padding-top: 1.25rem !important;
    padding-left: 1rem !important;
    padding-right: 1rem !important;
  }
</style>
""",
        unsafe_allow_html=True,
    )


_apply_sharp_embed_css()

from widgets_helpers import apply_global_widget_css, apply_calcbox_css, info_i_button
from state_and_helpers import hc_try

hc_try("css.apply_global_widget_css", apply_global_widget_css)
hc_try("css.apply_calcbox_css", apply_calcbox_css)

from state_and_helpers import (
    init_shared_session_state,
    derive_design_actions,
    resolve_design_actions,
    load_active_beam_into_shared,
    load_proxies_from_active_set,
    sync_load_edit_mode_from_toggle,
    recalc_derived_values,
    update_results,
    compute_all_results,
    assert_shared_state_alive,
    hydrate_active_page_widgets_from_shared,
    begin_render_cycle,
    persist_state_snapshot,
    persist_active_beam_from_shared,
    SHARED_DEFAULTS,
    TAB_KEYS,
    DERIVED_KEYS,
    RESULT_KEYS,
    tripwire_no_falsy_defaulting,
    clear_user_edit_marker_each_run,
    end_of_render_cleanup,
    clear_cached_and_widget_restore_keys,
    set_shared,
    get_speed_profile_summary,
    get_ux_latency_probe_summary,
    get_render_timing_summary,
    reset_speed_profile_last_run,
    reset_rerun_pure_caches,
    speed_profile_section,
    ux_probe_begin_rerun,
    ux_probe_record,
    ux_probe_set_page_slug,
    render_timing_begin_rerun,
    render_timing_mark,
)
import time
from persistence.save_to_dashboard import (
    get_context,
    export_state_for_saving,
    apply_project_payload,
    redirect_parent_to_project,
)
from auth_bridge import ensure_logged_in_state

# ðŸ” Import modules, not individual functions
import inputs_page_app_contracts
import inputs_page
import start_page
from application.opening_page_preferences import (
    load_opening_page_preference,
)
from ui.opening_page_preference_bridge import render_guest_preference_bootstrap
from inputs_page_modules.session.hydration_trace import inputs_hydration_trace_log
from inputs_page_modules.session.widget_cache_clear import clear_inputs_widget_cache_for_shared_updates
from inputs_page_modules.session.shear_normalization import run_inputs_pre_hydrate_shear_normalization
from inputs_application.design_guide_fingerprint import DESIGN_GUIDE_ALGORITHM_VERSION, build_design_guide_fingerprint
from inputs_page_modules.design_guide.transient_clear import clear_design_guide_transient_ui_state
from inputs_application.local_cleanup_acceptance import (
    build_local_cleanup_acceptance_fingerprint,
    local_cleanup_post_apply_acceptance_matches,
)
from inputs_application.engineering_predicates import parse_util_value, shear_demands_negligible, shear_reinforcement_is_active
from application.contracts.design_policy import AUTO_DESIGN_MODE_CONFIG, resolve_design_mode_config
from application.publication_identity import stable_final_publication_hash
from application.accepted_green_blocker_policy import accepted_green_exact_blocker_is_valid
from inputs_application.design_brain_composition import build_browser_publication_probe
from inputs_application.efficiency_classification import (
    identify_materially_overprovided_non_governing_families,
)
from inputs_page_modules.session import build_inputs_browser_recipe_action_applied_decision
from inputs_application.local_cleanup_acceptance import DESIGN_GUIDE_POST_CLEANUP_ACCEPTED_FPS
import session_state_final_log as _session_state_final_log
from optimisation_config import target_band_payload


_TRUE_ENV_VALUES = ("1", "true", "yes", "on")
_BROWSER_TEST_MODE = os.environ.get("CODEX_BROWSER_TEST_MODE", "").strip().lower() in _TRUE_ENV_VALUES
_EXPLICIT_DEV_MODE = os.environ.get("CODEX_DEV_MODE", "").strip().lower() in _TRUE_ENV_VALUES
_DESIGN_GUIDE_COMPONENT_APPLY_IN_FLIGHT_KEY = "_design_guide_component_apply_in_flight"
_DESIGN_GUIDE_PUBLICATION_FP_KEY = "design_guide_publication_fingerprint"
_BROWSER_RECIPE_PARAM = "browser_recipe"
_BROWSER_RECIPE_APPLIED_KEY = "_browser_recipe_applied_name"
_BROWSER_RECIPE_WIDGET_FORCING_KEY = "_browser_recipe_widget_forcing_name"
if "_BROWSER_RECIPE_GLOBAL_SEED_TOKENS" not in globals():
    _BROWSER_RECIPE_GLOBAL_SEED_TOKENS: set[tuple[str, str]] = set()
_BROWSER_RECIPE_ROW_MODEL_KEYS = {
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
}
_BROWSER_RECIPE_DESIGN_GUIDE_PROOF_KEYS = {
    "exact_stop_available",
    "exact_stop_proven",
    "exact_stop_proof",
    "locked_no_repair",
    "locked_repair_blocked",
    "all_repair_paths_locked",
    "repair_blocked_by_lock",
    "no_valid_repair_available",
    "repair_required",
    "reinforcement_lock",
    "reo_locked",
    "shear_lock",
    "geometry_lock",
}


def _apply_normal_user_page_zoom_css() -> None:
    if _browser_test_mode_active() or _EXPLICIT_DEV_MODE:
        return
    st.markdown(
        """
<style>
:root {
  --beam-app-compact-density: 0.82;
}
[data-testid="stMainBlockContainer"],
.block-container {
  padding-top: 1.05rem !important;
  padding-bottom: 1.05rem !important;
}
[data-testid="stVerticalBlock"] {
  gap: calc(0.9rem * var(--beam-app-compact-density)) !important;
}
[data-testid="stHorizontalBlock"] {
  gap: calc(1rem * var(--beam-app-compact-density)) !important;
}
[data-testid="stElementContainer"] {
  margin-bottom: calc(0.55rem * var(--beam-app-compact-density)) !important;
}
h1 {
  margin-bottom: 0.55rem !important;
}
h2,
h3 {
  margin-top: 0.8rem !important;
  margin-bottom: 0.45rem !important;
}
</style>
""",
        unsafe_allow_html=True,
    )


def _render_hidden_browser_state_probe(browser_state_probe_text: str, browser_state_probe_key: str) -> None:
    st.markdown(
        (
            "<style>"
            'div[class*="st-key-_browser_state_probe_text_area_"] {'
            "display:none !important;"
            "visibility:hidden !important;"
            "position:absolute !important;"
            "left:-10000px !important;"
            "width:1px !important;"
            "height:1px !important;"
            "opacity:0 !important;"
            "overflow:hidden !important;"
            "}"
            "</style>"
        ),
        unsafe_allow_html=True,
    )
    st.text_area(
        "Browser state",
        value=str(browser_state_probe_text or "{}"),
        key=browser_state_probe_key,
        height=120,
        disabled=True,
    )


def _should_emit_browser_state_probe(selected_slug: str | None, probe_phase: str | None = None) -> bool:
    """Allow hidden browser-state proof without enabling browser recipe behavior."""
    if _browser_test_mode_active():
        return True
    if str(selected_slug or "").strip().lower() not in {"inputs", "design"}:
        return False
    if os.environ.get("PERF_TRACE_INPUTS", "").strip().lower() in _TRUE_ENV_VALUES:
        return True
    try:
        bundle = st.session_state.get(inputs_page_app_contracts.DESIGN_GUIDE_DEBUG_BUNDLE_KEY)
    except Exception:
        bundle = None
    if not isinstance(bundle, dict) or not bundle:
        return False
    verifier_payload = dict(bundle.get("final_publication_verifier_payload") or {})
    return bool(
        verifier_payload.get("publication_hash")
        or bundle.get("publication_hash")
        or bundle.get("final_publication_publication_hash")
        or bundle.get("actual_card_render_probe")
    )
_BROWSER_RECIPE_LEGACY_REO_KEYS = {
    "bot1_count",
    "db_bot_1",
    "bot2_count",
    "db_bot_2",
    "top1_count",
    "db_top_1",
    "top2_count",
    "db_top_2",
    "nb_bot",
    "db_bot",
    "bot_entry",
    "nb_top",
    "db_top",
    "top_entry",
}


def _values_equal_for_browser_recipe(left, right) -> bool:
    try:
        return abs(float(left) - float(right)) <= 1e-9
    except (TypeError, ValueError):
        return left == right


def _browser_recipe_reconciliation_mismatches(applied_state: dict | None) -> dict:
    """Return recipe-owned reo state that drifted after the one-shot seed."""
    applied = dict(applied_state or {})
    keys = sorted(
        (set(applied.keys()) & _BROWSER_RECIPE_ROW_MODEL_KEYS)
        | (set(applied.keys()) & _BROWSER_RECIPE_LEGACY_REO_KEYS)
    )
    mismatches = {}
    for key in keys:
        current = st.session_state.get(key)
        expected = applied.get(key)
        if not _values_equal_for_browser_recipe(current, expected):
            mismatches[key] = {"current": current, "expected": expected}
        for widget_key, shared_key in TAB_KEYS.items():
            widget_name = str(widget_key or "")
            if shared_key != key or not widget_name.startswith("inputs_"):
                continue
            if widget_name not in st.session_state:
                continue
            widget_current = st.session_state.get(widget_name)
            if not _values_equal_for_browser_recipe(widget_current, expected):
                mismatches[widget_name] = {
                    "current": widget_current,
                    "expected": expected,
                    "shared_key": key,
                }
    return mismatches


def _browser_recipe_user_widget_edit_mismatches(applied_state: dict | None) -> dict:
    """Return visible Inputs widget edits that should override a debug recipe."""
    applied = dict(applied_state or {})
    widget_to_shared = {
        "inputs_load_Mstar_pos_proxy": "uls_Mstar_pos_manual",
        "inputs_load_Mstar_neg_proxy": "uls_Mstar_neg_manual",
        "inputs_load_Vstar_proxy": "uls_Vstar",
        "inputs_b": "b",
        "inputs_D": "D",
        "inputs_lig_d": "lig_d",
        "inputs_lig_legs": "lig_legs",
        "inputs_s_lig": "s_lig",
    }
    mismatches = {}
    for widget_key, shared_key in widget_to_shared.items():
        if widget_key not in st.session_state or shared_key not in applied:
            continue
        widget_current = st.session_state.get(widget_key)
        expected = applied.get(shared_key)
        if _values_equal_for_browser_recipe(widget_current, expected):
            continue
        mismatches[widget_key] = {
            "current": widget_current,
            "expected": expected,
            "shared_key": shared_key,
        }
    return mismatches


def _browser_recipe_action_already_applied() -> bool:
    """Avoid reseeding a debug recipe after a real Design Guide action changes state."""
    try:
        last_apply_route = st.session_state.get(inputs_page_app_contracts.DESIGN_GUIDE_LAST_APPLY_ROUTE_KEY)
    except Exception:
        last_apply_route = None
    inputs_action_apply_recommendation = st.session_state.get("_inputs_action_apply_recommendation")
    inputs_action_run_auto_design = st.session_state.get("_inputs_action_run_auto_design")
    inputs_action_signal = (
        inputs_action_apply_recommendation
        if inputs_action_apply_recommendation
        else inputs_action_run_auto_design
    )
    decision = build_inputs_browser_recipe_action_applied_decision(
        pending_recommendation_applied=st.session_state.get("pending_recommendation_applied_id"),
        inputs_action_apply_recommendation=inputs_action_signal,
        last_apply_route=last_apply_route,
    )
    return bool(decision.action_already_applied)


def _get_query_param_scalar(name: str):
    values = []
    try:
        value = st.query_params.get(name)
        if isinstance(value, list):
            values.extend(value)
        elif value is not None:
            values.append(value)
    except Exception:
        pass
    try:
        get_query_params = getattr(st, "experimental_get_query_params", None)
        if callable(get_query_params):
            value = (get_query_params() or {}).get(name)
            if isinstance(value, list):
                values.extend(value)
            elif value is not None:
                values.append(value)
    except Exception:
        pass
    for value in values:
        text = str(value or "").strip()
        if text:
            return text
    return None


def _browser_test_mode_active() -> bool:
    if _BROWSER_TEST_MODE:
        return True
    return str(_get_query_param_scalar("browser_test_mode") or "").strip().lower() in _TRUE_ENV_VALUES


def _browser_query_param_probe() -> dict:
    if not _browser_test_mode_active():
        return {}
    probe: dict[str, object] = {}
    try:
        probe["query_params"] = dict(st.query_params)
    except Exception as exc:
        probe["query_params_error"] = f"{type(exc).__name__}: {exc}"
    try:
        get_query_params = getattr(st, "experimental_get_query_params", None)
        if callable(get_query_params):
            probe["experimental_query_params"] = get_query_params()
    except Exception as exc:
        probe["experimental_query_params_error"] = f"{type(exc).__name__}: {exc}"
    return probe


def _browser_action_probe(label: str) -> dict:
    return {
        "label": str(label or ""),
        "active_beam_id": st.session_state.get("active_beam_id"),
        "beam_last_hydrated_id": st.session_state.get("beam_last_hydrated_id"),
        "b": st.session_state.get("b"),
        "D": st.session_state.get("D"),
        "lig_d": st.session_state.get("lig_d"),
        "lig_legs": st.session_state.get("lig_legs"),
        "s_lig": st.session_state.get("s_lig"),
        "actions_mode": st.session_state.get("actions_mode"),
        "actions_source": st.session_state.get("actions_source"),
        "uls_Mstar": st.session_state.get("uls_Mstar"),
        "uls_Mstar_pos_manual": st.session_state.get("uls_Mstar_pos_manual"),
        "uls_Mstar_neg_manual": st.session_state.get("uls_Mstar_neg_manual"),
        "uls_Vstar": st.session_state.get("uls_Vstar"),
        "load_Mstar_proxy": st.session_state.get("load_Mstar_proxy"),
        "load_Mstar_pos_proxy": st.session_state.get("load_Mstar_pos_proxy"),
        "load_Mstar_neg_proxy": st.session_state.get("load_Mstar_neg_proxy"),
        "load_Vstar_proxy": st.session_state.get("load_Vstar_proxy"),
        "inputs_load_Mstar_pos_proxy": st.session_state.get("inputs_load_Mstar_pos_proxy"),
        "inputs_load_Mstar_neg_proxy": st.session_state.get("inputs_load_Mstar_neg_proxy"),
        "inputs_load_Vstar_proxy": st.session_state.get("inputs_load_Vstar_proxy"),
    }


def _queue_inputs_refresh_after_shared_seed(source: str) -> None:
    """
    Ask Inputs to reseed its widget layer from canonical shared state on this run.

    This keeps first-render summary/card/model reads on the existing Inputs
    refresh path after the router has loaded a beam or injected a dev recipe,
    instead of letting stale `inputs_*` widget values overlay the freshly
    seeded shared state.
    """
    payload = {
        "source": str(source or "shared_seed"),
        "keys": [],
    }
    current = st.session_state.get("_pending_inputs_apply_refresh")
    if isinstance(current, dict) and current.get("source"):
        return
    st.session_state["_pending_inputs_apply_refresh"] = payload


_INPUTS_SAME_BEAM_RETURN_GUARD_KEY = "_inputs_same_beam_return_guard"
_INPUTS_COMMITTED_STATE_BY_BEAM_KEY = "_inputs_committed_engineering_state_by_beam_v1"


def _inputs_route_authority_handoff(selected_slug: str) -> bool:
    """Preserve the committed Inputs transaction across same-beam navigation.

    The legacy router runs before the Inputs coordinator.  On a return from
    another page it can therefore reseed or derive shared values before the
    committed transaction is consulted.  This handoff is intentionally
    route-scoped: a same-beam return restores the session-owned state, while a
    new beam or an explicitly changed browser recipe follows the normal load.
    """
    selected = str(selected_slug or "").strip().lower()
    previous = str(st.session_state.get("_prev_page_slug") or "").strip().lower()
    query_page = str(_get_query_param_scalar("page") or "").strip().lower()
    url_confirms_route_change = bool(query_page and query_page == selected)
    active_beam_id = str(st.session_state.get("active_beam_id") or "").strip()
    committed_beam_id = str(
        st.session_state.get("_inputs_engineering_input_store_active_beam_id")
        or ""
    ).strip()
    input_services = InputsSessionServices.from_mapping(st.session_state)
    input_store = input_services.input_snapshots
    typed_current = input_store.current()
    typed_beam = input_store.current_for_beam(active_beam_id)
    committed_by_beam = st.session_state.get(_INPUTS_COMMITTED_STATE_BY_BEAM_KEY)
    current_committed = typed_current.snapshot
    if (
        isinstance(current_committed, dict)
        and current_committed
        and committed_beam_id == active_beam_id
    ):
        committed = dict(current_committed)
    else:
        committed = dict(typed_beam.snapshot or {})
        if not committed:
            committed = (
                dict(committed_by_beam.get(active_beam_id) or {})
                if isinstance(committed_by_beam, dict) and active_beam_id
                else {}
            )
    has_committed_state = isinstance(committed, dict) and bool(committed)
    authority_handoff_armed = bool(
        st.session_state.get("_inputs_route_authority_armed")
    )
    if not authority_handoff_armed:
        st.session_state.pop(_INPUTS_SAME_BEAM_RETURN_GUARD_KEY, None)
        st.session_state.pop("_inputs_same_beam_return_active", None)
        st.session_state.pop("_inputs_same_beam_return_restored_keys", None)

    existing_guard = dict(
        st.session_state.get(_INPUTS_SAME_BEAM_RETURN_GUARD_KEY) or {}
    )
    # Record the handoff before the away-page router can touch shared state.
    if (
        authority_handoff_armed
        and selected != "inputs"
        and previous == "inputs"
        and url_confirms_route_change
        and active_beam_id
        and committed_beam_id == active_beam_id
        and has_committed_state
        and not (
            str(existing_guard.get("beam_id") or "").strip()
            == active_beam_id
            and str(existing_guard.get("from") or "").strip() == "inputs"
        )
    ):
        results_by_beam = st.session_state.get(
            "_inputs_authoritative_design_result_by_beam_v1"
        )
        # The beam-owned snapshot is authoritative here.  The legacy current
        # result may have been transiently replaced by a derived-only pass
        # while the route changed, so it must not win over the committed beam
        # record.
        committed_result = (
            dict(results_by_beam).get(active_beam_id)
            if isinstance(results_by_beam, dict)
            else None
        ) or InputsSessionServices.from_mapping(st.session_state).engineering_results.current()
        st.session_state[_INPUTS_SAME_BEAM_RETURN_GUARD_KEY] = {
            "beam_id": active_beam_id,
            "from": "inputs",
            "to": selected,
            "committed_state": copy.deepcopy(dict(committed)),
            "committed_revision": int(typed_beam.revision or typed_current.revision or 0),
            "result_input_revision": int(
                input_services.engineering_results.source_input_revision()
                or typed_beam.revision
                or typed_current.revision
                or 0
            ),
            "authoritative_result": committed_result,
        }

    guard = dict(st.session_state.get(_INPUTS_SAME_BEAM_RETURN_GUARD_KEY) or {})
    if selected != "inputs":
        return False
    if str(guard.get("beam_id") or "").strip() != active_beam_id:
        if guard:
            st.session_state.pop(_INPUTS_SAME_BEAM_RETURN_GUARD_KEY, None)
        return False

    guarded_committed = guard.get("committed_state")
    latest_snapshot = input_store.current_for_beam(active_beam_id)
    guarded_revision = int(guard.get("committed_revision", 0) or 0)
    latest_revision = int(latest_snapshot.revision or 0)
    if latest_revision > guarded_revision and latest_snapshot.snapshot:
        # An edit may have committed while another route was visible.  The
        # latest typed transaction wins; never hydrate the older route guard.
        guarded_committed = latest_snapshot.snapshot
        guard["committed_state"] = copy.deepcopy(dict(guarded_committed))
        guard["committed_revision"] = latest_revision
    if isinstance(guarded_committed, dict) and guarded_committed:
        committed = copy.deepcopy(guarded_committed)
        committed_by_beam = dict(
            st.session_state.get(_INPUTS_COMMITTED_STATE_BY_BEAM_KEY) or {}
        )
        committed_by_beam[active_beam_id] = copy.deepcopy(committed)
        st.session_state[_INPUTS_COMMITTED_STATE_BY_BEAM_KEY] = committed_by_beam
    guarded_result = guard.get("authoritative_result")
    guarded_result_revision = int(guard.get("result_input_revision", guarded_revision) or 0)
    guarded_result_hash = (
        guarded_result.get("engineering_hash")
        if isinstance(guarded_result, dict)
        else getattr(guarded_result, "engineering_hash", "")
    )
    result_is_current_for_return = bool(
        guarded_result is not None
        and latest_revision <= guarded_result_revision
        and (
            not latest_snapshot.engineering_hash
            or str(guarded_result_hash or "")
            == str(latest_snapshot.engineering_hash or "")
        )
    )
    if guarded_result is not None and result_is_current_for_return:
        results_by_beam = dict(
            st.session_state.get(
                "_inputs_authoritative_design_result_by_beam_v1"
            )
            or {}
        )
        results_by_beam[active_beam_id] = guarded_result
        st.session_state[
            "_inputs_authoritative_design_result_by_beam_v1"
        ] = results_by_beam
        input_services.engineering_results.store(
            guarded_result,
            source_input_revision=guarded_result_revision or None,
        )
    elif guarded_result is not None and latest_revision > guarded_result_revision:
        # A newer input transaction is pending or has already published its
        # own result.  Do not put the older route-guard publication back into
        # the active session; freshness is owned by the typed result store.
        current_result_revision = input_services.engineering_results.source_input_revision()
        if current_result_revision is None or int(current_result_revision) < latest_revision:
            input_services.engineering_results.clear()

    # A changed replay recipe is an explicit engineering input change, not a
    # navigation return, so let the normal recipe/bootstrap path own it.
    if _browser_test_mode_active():
        requested_recipe = str(
            _get_query_param_scalar(_BROWSER_RECIPE_PARAM)
            or st.session_state.get("_browser_recipe_query_value")
            or os.environ.get("CODEX_BROWSER_REPLAY_RECIPE")
            or ""
        ).strip()
        applied_recipe = str(
            st.session_state.get(_BROWSER_RECIPE_APPLIED_KEY) or ""
        ).strip()
        if requested_recipe and applied_recipe and requested_recipe != applied_recipe:
            st.session_state.pop(_INPUTS_SAME_BEAM_RETURN_GUARD_KEY, None)
            return False

    restored_keys: list[str] = []
    for key, value in dict(committed or {}).items():
        if key not in SHARED_DEFAULTS:
            continue
        if st.session_state.get(key) != value:
            set_shared(
                key,
                copy.deepcopy(value),
                source="inputs_same_beam_return_committed_restore",
            )
            restored_keys.append(str(key))
    if restored_keys:
        recalc_derived_values()
        load_proxies_from_active_set()
    st.session_state["_inputs_same_beam_return_active"] = True
    st.session_state["_inputs_same_beam_return_restored_keys"] = sorted(
        restored_keys
    )
    results_by_beam = st.session_state.get(
        "_inputs_authoritative_design_result_by_beam_v1"
    )
    committed_result = (
        dict(results_by_beam).get(active_beam_id)
        if isinstance(results_by_beam, dict) and active_beam_id
        else None
    )
    if committed_result is not None:
        st.session_state["authoritative_design_result"] = committed_result
        st.session_state[
            "_authoritative_design_result_runtime_probe"
        ] = {
            "engineering_hash": committed_result.engineering_hash,
            "reuse_decision": {
                "reused": True,
                "reason": "same_beam_route_return_pre_router_restore",
            },
            "source": "inputs_same_beam_route_return_pre_router_restore",
        }
    return True


def _apply_browser_recipe_from_query() -> None:
    if not _browser_test_mode_active():
        return

    recipe_name = str(
        _get_query_param_scalar(_BROWSER_RECIPE_PARAM)
        or st.session_state.get("_browser_recipe_query_value")
        or os.environ.get("CODEX_BROWSER_REPLAY_RECIPE")
        or ""
    ).strip()
    if not recipe_name:
        st.session_state.pop(_BROWSER_RECIPE_WIDGET_FORCING_KEY, None)
        return

    recipe_reapply_reason = None
    recipe_reconcile_mismatches = {}
    if st.session_state.get(_BROWSER_RECIPE_APPLIED_KEY) == recipe_name:
        # Widget forcing exists only to seed recipe-owned selectboxes on the
        # first render after the recipe is applied.  Re-arming it on every
        # app rerun lets the original recipe overwrite a later committed user
        # edit when a widget is remounted after page navigation.
        st.session_state.pop(_BROWSER_RECIPE_WIDGET_FORCING_KEY, None)
        user_widget_edits = _browser_recipe_user_widget_edit_mismatches(
            st.session_state.get("_browser_recipe_applied_state")
        )
        if user_widget_edits:
            st.session_state["_browser_recipe_last_action"] = {
                "action": "skip_user_widget_edit",
                "recipe": recipe_name,
                "user_widget_edits": user_widget_edits,
                "shared_shear": {
                    "lig_d": st.session_state.get("lig_d"),
                    "lig_legs": st.session_state.get("lig_legs"),
                    "s_lig": st.session_state.get("s_lig"),
                },
            }
            st.session_state["_browser_recipe_user_widget_edit_mismatches"] = user_widget_edits
            return
        st.session_state.pop("_browser_recipe_user_widget_edit_mismatches", None)
        recipe_reconcile_mismatches = _browser_recipe_reconciliation_mismatches(
            st.session_state.get("_browser_recipe_applied_state")
        )
        st.session_state["_browser_recipe_last_action"] = {
            "action": "skip_already_applied",
            "recipe": recipe_name,
            "reconciliation_mismatches": recipe_reconcile_mismatches,
            "action_already_applied": _browser_recipe_action_already_applied(),
            "one_shot_recipe_seed": True,
            "shared_shear": {
                "lig_d": st.session_state.get("lig_d"),
                "lig_legs": st.session_state.get("lig_legs"),
                "s_lig": st.session_state.get("s_lig"),
            },
        }
        return

    try:
        from tools.one_click_recipe_defs import find_named_case, build_state
    except Exception as exc:
        st.session_state["_browser_recipe_error"] = f"recipe_import_failed:{exc}"
        return

    recipe = find_named_case(recipe_name)
    if not isinstance(recipe, dict):
        st.session_state.pop(_BROWSER_RECIPE_WIDGET_FORCING_KEY, None)
        st.session_state["_browser_recipe_error"] = f"unknown_recipe:{recipe_name}"
        return

    state = build_state(dict(recipe.get("changes") or {}))
    st.session_state["_browser_recipe_last_action"] = {
        "action": "apply_recipe",
        "recipe": recipe_name,
        "reapply_reason": recipe_reapply_reason,
        "reconciliation_mismatches_before": recipe_reconcile_mismatches,
        "previous_applied_recipe": st.session_state.get(_BROWSER_RECIPE_APPLIED_KEY),
        "shared_shear_before": {
            "lig_d": st.session_state.get("lig_d"),
            "lig_legs": st.session_state.get("lig_legs"),
            "s_lig": st.session_state.get("s_lig"),
        },
    }
    clear_cached_and_widget_restore_keys()
    applied_state = {}
    recipe_hydrate_source = "project_load"
    for key, value in state.items():
        if key not in SHARED_DEFAULTS:
            continue
        set_shared(key, value, source=recipe_hydrate_source)
        applied_state[key] = value
    for key in _BROWSER_RECIPE_DESIGN_GUIDE_PROOF_KEYS:
        if key in state:
            st.session_state[key] = state.get(key)
            applied_state[key] = state.get(key)
        else:
            st.session_state.pop(key, None)

    # Keep the active beam's canonical stored params aligned with the injected
    # shared recipe state so the next rerun cannot resurrect stale beam data.
    try:
        from state_and_helpers import persist_active_beam_from_shared

        persist_active_beam_from_shared()
    except Exception:
        pass
    try:
        active_beam_id = st.session_state.get("active_beam_id")
        if active_beam_id:
            st.session_state["beam_last_hydrated_id"] = active_beam_id
    except Exception:
        pass
    try:
        clear_inputs_widget_cache_for_shared_updates(st.session_state, applied_state)
    except Exception:
        pass
    recipe_widget_mirrors = {
        "b": ["inputs_b"],
        "bw": ["inputs_bw"],
        "D": ["inputs_D"],
        "fc": ["inputs_fc"],
        "fsy": ["inputs_fsy"],
        "L": ["inputs_L"],
        "uls_Mstar": ["inputs_uls_Mstar", "inputs_uls_Mstar_pos_manual", "inputs_load_Mstar_pos_proxy"],
        "uls_Mstar_pos_manual": ["inputs_uls_Mstar_pos_manual", "inputs_load_Mstar_pos_proxy"],
        "uls_Mstar_neg_manual": ["inputs_uls_Mstar_neg_manual", "inputs_load_Mstar_neg_proxy"],
        "uls_Vstar": ["inputs_uls_Vstar", "inputs_load_Vstar_proxy"],
        "bot1_count": ["inputs_bot1_count"],
        "db_bot_1": ["inputs_db_bot_1"],
        "bot2_count": ["inputs_bot2_count"],
        "db_bot_2": ["inputs_db_bot_2"],
        "bot_row_count": ["inputs_bot_row_count"],
        "bot_row_1_mode": ["inputs_bot_row_1_mode"],
        "bot_row_1_bars": ["inputs_bot_row_1_bars"],
        "bot_row_1_spacing": ["inputs_bot_row_1_spacing"],
        "bot_row_1_dia": ["inputs_bot_row_1_dia"],
        "bot_row_2_mode": ["inputs_bot_row_2_mode"],
        "bot_row_2_bars": ["inputs_bot_row_2_bars"],
        "bot_row_2_spacing": ["inputs_bot_row_2_spacing"],
        "bot_row_2_dia": ["inputs_bot_row_2_dia"],
        "top1_count": ["inputs_top1_count"],
        "db_top_1": ["inputs_db_top_1"],
        "top_row_count": ["inputs_top_row_count"],
        "top_row_1_mode": ["inputs_top_row_1_mode"],
        "top_row_1_bars": ["inputs_top_row_1_bars"],
        "top_row_1_spacing": ["inputs_top_row_1_spacing"],
        "top_row_1_dia": ["inputs_top_row_1_dia"],
        "top_row_2_mode": ["inputs_top_row_2_mode"],
        "top_row_2_bars": ["inputs_top_row_2_bars"],
        "top_row_2_spacing": ["inputs_top_row_2_spacing"],
        "top_row_2_dia": ["inputs_top_row_2_dia"],
        "lig_d": ["inputs_lig_d"],
        "lig_legs": ["inputs_lig_legs"],
        "s_lig": ["inputs_s_lig"],
    }
    recipe_widget_mirror_seed_audit = {
        "source": "browser_recipe_pre_dispatch",
        "changed": {},
    }
    for shared_key, widget_keys in recipe_widget_mirrors.items():
        if shared_key not in applied_state:
            continue
        for widget_key in widget_keys:
            before = st.session_state.get(widget_key)
            after = applied_state.get(shared_key)
            if before != after:
                recipe_widget_mirror_seed_audit["changed"][widget_key] = {
                    "before": before,
                    "after": after,
                    "shared_key": shared_key,
                }
            st.session_state[widget_key] = applied_state.get(shared_key)
    for widget_key, shared_key in TAB_KEYS.items():
        widget_name = str(widget_key or "")
        if not widget_name.startswith("inputs_"):
            continue
        if shared_key not in applied_state:
            continue
        value = applied_state.get(shared_key)
        if isinstance(value, (dict, list, tuple, set)):
            continue
        before = st.session_state.get(widget_name)
        if before != value:
            recipe_widget_mirror_seed_audit["changed"][widget_name] = {
                "before": before,
                "after": value,
                "shared_key": shared_key,
            }
        st.session_state[widget_name] = value
    recipe_widget_mirror_seed_audit["applied"] = bool(recipe_widget_mirror_seed_audit["changed"])
    st.session_state["_browser_recipe_widget_mirror_seed_audit"] = recipe_widget_mirror_seed_audit
    st.session_state["_force_inputs_widget_reseed_once"] = True

    for stale_key in (
        "pending_recommendation",
        "_solver_result",
        "_one_click_run_feedback",
        "_design_guide_post_cleanup_acceptance_enabled",
        "_design_guide_post_cleanup_acceptance_fp",
        "design_guide_step_history",
        "design_guide_step_history_compact",
        "design_guide_terminal_state",
        "design_guide_has_actionable_recommendation",
        "design_guide_terminal_positive",
        "_inputs_summary_cache",
        "_inputs_summary_cache_fp",
        "_inputs_summary_cache_version",
    ):
        st.session_state.pop(stale_key, None)
    try:
        recipe_seed_token = (
            recipe_name,
            str(_get_query_param_scalar("cid") or ""),
        )
        if recipe_seed_token not in _BROWSER_RECIPE_GLOBAL_SEED_TOKENS:
            DESIGN_GUIDE_POST_CLEANUP_ACCEPTED_FPS.clear()
            _BROWSER_RECIPE_GLOBAL_SEED_TOKENS.add(recipe_seed_token)
    except Exception:
        pass
    try:
        clear_design_guide_transient_ui_state(
            st.session_state,
            clear_history=True,
            preserve_apply_banner=False,
        )
        st.session_state[inputs_page_app_contracts.DESIGN_GUIDE_NEEDS_REFRESH_KEY] = True
    except Exception:
        pass

    st.session_state["inputs_dirty"] = True
    st.session_state["_inputs_dirty"] = True
    st.session_state["run_design_clicked"] = False
    st.session_state[_BROWSER_RECIPE_APPLIED_KEY] = recipe_name
    st.session_state[_BROWSER_RECIPE_WIDGET_FORCING_KEY] = recipe_name
    st.session_state["_browser_recipe_kind"] = recipe.get("kind")
    st.session_state["_browser_recipe_changes"] = dict(recipe.get("changes") or {})
    st.session_state["_browser_recipe_applied_state"] = dict(applied_state)
    st.session_state["_browser_recipe_last_action"] = {
        **dict(st.session_state.get("_browser_recipe_last_action") or {}),
        "shared_shear_after": {
            "lig_d": st.session_state.get("lig_d"),
            "lig_legs": st.session_state.get("lig_legs"),
            "s_lig": st.session_state.get("s_lig"),
        },
    }
    st.session_state["_browser_recipe_error"] = None
    st.session_state["_browser_recipe_boot_compute_pending"] = True
    _queue_inputs_refresh_after_shared_seed("browser_recipe_shared_seed")


def _prime_browser_recipe_results_if_needed() -> None:
    if not _browser_test_mode_active():
        return
    if not bool(st.session_state.get("_browser_recipe_boot_compute_pending")):
        return
    render_timing_mark("app.pre_dispatch.browser_recipe_boot_compute.start")
    recalc_derived_values()
    compute_all_results()
    st.session_state["_browser_recipe_boot_compute_pending"] = False
    render_timing_mark("app.pre_dispatch.browser_recipe_boot_compute.end")


def _emit_browser_test_state(selected_slug: str, probe_slot=None, *, probe_phase: str = "final") -> None:
    if not _should_emit_browser_state_probe(selected_slug, probe_phase):
        return

    render_timing_mark("app.browser_test_state_emit.start", selected_slug=selected_slug, probe_phase=probe_phase)
    ux_probe_set_page_slug(selected_slug)
    rec = st.session_state.get("pending_recommendation")
    rec_meta = dict(rec.get("meta") or {}) if isinstance(rec, dict) else {}
    summary_state_probe = {}
    summary_overview_probe = {}
    guidance_probe = {}
    engineering_snapshot_probe = {}

    def _merge_family_evidence_maps(*maps):
        merged = {}
        for maybe_map in maps:
            if not isinstance(maybe_map, dict):
                continue
            for family, payload in maybe_map.items():
                family_key = str(family or "").strip().lower()
                if not family_key or not isinstance(payload, dict):
                    continue
                merged[family_key] = dict(payload)
        return merged

    def _probe_float_or_none(value):
        try:
            if value is None or isinstance(value, bool):
                return None
            return float(value)
        except Exception:
            try:
                text = str(value or "").strip()
                if not text:
                    return None
                return float(text.split()[0])
            except Exception:
                return None

    def _complete_probe_exact_blocker_map(source):
        completed = {}
        for family_key, raw_blocker in dict(source or {}).items():
            family = str(family_key or "").strip().lower()
            if not family or not isinstance(raw_blocker, dict):
                continue
            blocker = dict(raw_blocker)
            blocker.setdefault("family", family)
            attempted_count = (
                blocker.get("attempted_candidate_count")
                or blocker.get("previewed_candidate_count")
                or blocker.get("candidate_count")
                or blocker.get("safe_candidate_count")
                or blocker.get("safe_cleanup_count")
            )
            if attempted_count not in (None, "", [], {}):
                try:
                    blocker["attempted_candidate_count"] = int(attempted_count)
                except Exception:
                    blocker["attempted_candidate_count"] = attempted_count
            rejected_id = str(
                blocker.get("failed_candidate_id")
                or blocker.get("best_rejected_candidate_id")
                or blocker.get("best_safe_candidate_id")
                or blocker.get("selected_candidate_id")
                or ""
            ).strip()
            if rejected_id:
                blocker["failed_candidate_id"] = rejected_id
                blocker["best_rejected_candidate_id"] = rejected_id
            if blocker.get("target_low") in (None, "", [], {}):
                blocker["target_low"] = float(inputs_page_app_contracts.FINAL_ACCEPTED_MIN_FAMILY_UTIL)
            if blocker.get("target_high") in (None, "", [], {}):
                blocker["target_high"] = float(inputs_page_app_contracts.EFFICIENCY_TARGET_UTIL_MAX)
            completed[family] = dict(blocker)
        return completed

    def _restamp_probe_exact_blocker_current_utils(source, visible_utils):
        restamped = {}
        visible = dict(visible_utils or {})
        for family_key, raw_blocker in dict(source or {}).items():
            if not isinstance(raw_blocker, dict):
                restamped[family_key] = raw_blocker
                continue
            blocker = dict(raw_blocker)
            family = str(blocker.get("family") or family_key or "").strip().lower()
            visible_util = _probe_float_or_none(visible.get(family))
            if family in {"bending", "shear"} and visible_util is not None:
                previous_current = _probe_float_or_none(blocker.get("current_util"))
                previous_failed = _probe_float_or_none(blocker.get("failed_check_util"))
                for previous_util in (previous_current, previous_failed):
                    if previous_util is None or abs(float(previous_util) - float(visible_util)) <= 1e-9:
                        continue
                    blocker.setdefault("attempted_util", float(previous_util))
                    blocker.setdefault("attempted_candidate_util", float(previous_util))
                    blocker.setdefault("rejected_candidate_util", float(previous_util))
                    blocker.setdefault("rejected_candidate_failed_check_util", float(previous_util))
                    break
                blocker["current_util"] = float(visible_util)
                blocker["starting_util"] = float(visible_util)
                blocker["failed_check_util"] = float(visible_util)
            restamped[family or family_key] = dict(blocker)
        return restamped

    def _restamp_probe_exact_blocker_maps(payload_source, visible_utils):
        out = dict(payload_source or {})
        for map_key in (
            "exact_blockers_by_family",
            "post_click_exact_blockers_by_family",
            "cleanup_evidence_by_family",
            "post_click_cleanup_evidence_by_family",
        ):
            if isinstance(out.get(map_key), dict):
                out[map_key] = _restamp_probe_exact_blocker_current_utils(
                    out.get(map_key),
                    visible_utils,
                )
        evidence = dict(out.get("candidate_search_evidence") or {})
        if evidence:
            out["candidate_search_evidence"] = _restamp_probe_exact_blocker_maps(evidence, visible_utils)
        decision = dict(out.get("design_guide_engine_decision") or {})
        if decision:
            for decision_key in ("card", "debug"):
                if isinstance(decision.get(decision_key), dict):
                    decision[decision_key] = _restamp_probe_exact_blocker_maps(
                        decision.get(decision_key),
                        visible_utils,
                )
            out["design_guide_engine_decision"] = dict(decision)
        return out

    def _probe_rendered_design_guide_reuse_payload(
        *,
        summary_state: dict,
        summary_overview: dict,
    ) -> tuple[dict | None, dict]:
        """Return a probe-only guidance payload from the rendered bundle, or a fallback reason."""
        meta = {
            "attempted": True,
            "source": "fallback",
            "reason": "",
        }

        def _reject(reason: str, **fields) -> tuple[None, dict]:
            meta.update({"reason": reason, **fields})
            return None, dict(meta)

        if str(probe_phase or "") != "post_page_render":
            return _reject("not_post_page_render")
        if str(selected_slug or "").strip().lower() not in {"inputs", "design"}:
            return _reject("route_not_probe_supported", route=selected_slug)

        session_contract = dict(st.session_state.get("design_guide_primary_button_contract") or {})
        session_truth = dict(st.session_state.get("design_guide_primary_display_truth") or {})
        session_title = str(
            st.session_state.get("design_guide_rebuilt_title")
            or st.session_state.get("design_guide_original_title")
            or ""
        ).strip()
        if session_contract and session_title:
            session_updates = dict(session_contract.get("updates") or {})
            authoritative_result = InputsSessionServices.from_mapping(st.session_state).engineering_results.current()
            session_apply_payload = (
                dict(authoritative_result.apply_payload or {})
                if authoritative_result is not None
                else {}
            )
            session_binding_audit = dict(
                st.session_state.get(inputs_page_app_contracts.DESIGN_GUIDE_PRIMARY_PAYLOAD_BINDING_AUDIT_KEY) or {}
            )
            if (
                bool(session_contract.get("actionable") or session_contract.get("enabled"))
                and session_updates
                and session_apply_payload
                and session_binding_audit.get("payload_binding_match") is not False
                and session_binding_audit.get("payload_update_match") is not False
            ):
                session_evidence = dict(session_apply_payload.get("candidate_search_evidence") or {})
                session_family = str(
                    session_contract.get("family")
                    or session_apply_payload.get("family")
                    or session_evidence.get("selected_family_id")
                    or session_evidence.get("family_id")
                    or ""
                ).strip()
                session_debug = {
                    "browser_probe_guidance_source": "rendered_session_contract_reuse",
                    "browser_probe_rendered_bundle_reused": True,
                    "browser_probe_rendered_bundle_reuse_reason": "session_contract_eligible",
                    "overview": dict(summary_overview or {}),
                    "family_utils": dict((summary_overview or {}).get("utils") or {}),
                    "primary_button_contract": dict(session_contract),
                    "button_contract": dict(session_contract),
                    "primary_display_truth": dict(session_truth),
                    "candidate_search_evidence": dict(session_evidence),
                }
                session_item = {
                    "title_main": session_title,
                    "title": session_title,
                    "action_type": session_contract.get("action_type"),
                    "status": session_truth.get("displayed_status"),
                    "button_contract": dict(session_contract),
                    "display_truth": dict(session_truth),
                    "candidate_search_evidence": dict(session_evidence),
                    "action_payload": {
                        **dict(session_apply_payload),
                        "updates": dict(session_updates),
                        "resolved_candidate_updates": dict(session_updates),
                        "candidate_search_evidence": dict(session_evidence),
                        "family": session_family,
                        "family_id": session_family,
                        "selected_family_id": session_family,
                        "published_family_id": session_family,
                        "cta_family_id": session_family,
                        "apply_payload_family_id": session_family,
                    },
                    "resolved_candidate": {
                        "candidate_search_evidence": dict(session_evidence),
                        "updates": dict(session_updates),
                        "family": session_family,
                        "family_id": session_family,
                    },
                    "family": session_family,
                    "family_id": session_family,
                    "selected_family_id": session_family,
                    "published_family_id": session_family,
                    "cta_family_id": session_family,
                    "apply_payload_family_id": session_family,
                    "util": session_truth.get("displayed_util"),
                }
                return {
                    "guidance_items": [session_item],
                    "debug_trace": dict(session_debug),
                    "cache_data": {
                        "browser_probe_guidance_source": "rendered_session_contract_reuse",
                    },
                    "recommendation_result": {},
                    "design_brain_result": {
                        "source": "rendered_session_contract_reuse",
                        "primary_card_title": session_title,
                        "button_contract_enabled": True,
                        "displayed_status": session_truth.get("displayed_status"),
                    },
                    "browser_probe_equivalent_result_payload": {
                        "source": "rendered_session_contract_reuse",
                        "primary_card_title": session_title,
                        "button_contract_enabled": True,
                    },
                }, {
                    **dict(meta),
                    "source": "rendered_session_contract_reuse",
                    "reason": "session_contract_eligible",
                    "route": selected_slug,
                }

        bundle_raw = st.session_state.get(inputs_page_app_contracts.DESIGN_GUIDE_DEBUG_BUNDLE_KEY)
        if not isinstance(bundle_raw, dict) or not bundle_raw:
            return _reject("missing_rendered_bundle")
        bundle = dict(bundle_raw)
        render_plan = st.session_state.get("_design_guide_render_plan_debug")
        if not isinstance(render_plan, dict):
            return _reject("missing_render_plan_debug")
        if bool(st.session_state.get(inputs_page_app_contracts.DESIGN_GUIDE_NEEDS_REFRESH_KEY)):
            return _reject("design_guide_needs_refresh")

        pending_keys = (
            "_pending_inputs_apply_refresh",
            "_inputs_action_apply_recommendation",
            "_inputs_action_run_auto_design",
            _DESIGN_GUIDE_COMPONENT_APPLY_IN_FLIGHT_KEY,
        )
        active_pending = {
            key: st.session_state.get(key)
            for key in pending_keys
            if bool(st.session_state.get(key))
        }
        if active_pending:
            return _reject("pending_apply_or_action_state", pending_keys=sorted(active_pending.keys()))

        try:
            current_fp = build_design_guide_fingerprint(dict(summary_state or {}))
        except Exception as exc:
            return _reject("current_fingerprint_error", error=f"{type(exc).__name__}: {exc}")
        publication_fp = st.session_state.get(_DESIGN_GUIDE_PUBLICATION_FP_KEY)
        baseline_fp = st.session_state.get(inputs_page_app_contracts.DESIGN_GUIDE_PANEL_BASELINE_FP_KEY)
        bundle_publication_fp = bundle.get("design_guide_publication_fingerprint")

        def _fp_matches(left, right) -> bool:
            if left in (None, "") or right in (None, ""):
                return False
            return left == right or str(left) == str(right)

        if not _fp_matches(publication_fp, current_fp):
            return _reject("publication_fingerprint_mismatch")
        if not _fp_matches(baseline_fp, current_fp):
            return _reject("baseline_fingerprint_mismatch")
        if bundle_publication_fp not in (None, "") and not _fp_matches(bundle_publication_fp, current_fp):
            return _reject("bundle_publication_fingerprint_mismatch")

        title = str(
            bundle.get("primary_card_title")
            or bundle.get("final_primary_title")
            or bundle.get("selected_title")
            or ""
        ).strip()
        if not title:
            return _reject("missing_visible_title")

        contract = dict(
            bundle.get("displayed_primary_button_contract")
            or bundle.get("primary_button_contract")
            or bundle.get("button_contract")
            or st.session_state.get("design_guide_primary_button_contract")
            or {}
        )
        if not contract:
            return _reject("missing_button_contract")

        display_truth = dict(
            bundle.get("displayed_primary_display_truth")
            or bundle.get("primary_display_truth")
            or bundle.get("display_truth")
            or st.session_state.get("design_guide_primary_display_truth")
            or {}
        )
        if not display_truth:
            display_truth = {
                "displayed_util": bundle.get("displayed_util"),
                "displayed_status": bundle.get("displayed_status"),
                "display_truth_source": bundle.get("display_truth_source"),
                "target_low": bundle.get("target_low"),
                "target_high": bundle.get("target_high"),
                "displayed_within_target_band": bundle.get("displayed_within_target_band"),
                "source_summary_util": bundle.get("source_summary_util"),
                "source_candidate_util": bundle.get("source_candidate_util"),
                "source_post_commit_util": bundle.get("source_post_commit_util"),
            }
        if not any(display_truth.get(key) is not None for key in ("displayed_util", "displayed_status", "display_truth_source")):
            return _reject("missing_display_truth")

        design_brain_result = dict(bundle.get("design_brain_result") or {})
        equivalent_result_payload = dict(
            design_brain_result
            or bundle.get("design_guide_engine_decision")
            or {}
        )
        if not equivalent_result_payload:
            equivalent_result_payload = {
                "source": "rendered_design_guide_publication",
                "primary_card_title": title,
                "primary_card_intent": bundle.get("primary_card_intent"),
                "primary_guidance_intent": bundle.get("primary_guidance_intent"),
                "terminal_state": bundle.get("design_guide_terminal_state"),
                "terminal_state_source": bundle.get("design_guide_terminal_state_source"),
                "button_contract_enabled": bool(
                    bundle.get("button_contract_enabled")
                    or contract.get("enabled")
                    or contract.get("actionable")
                ),
                "displayed_status": display_truth.get("displayed_status"),
                "display_truth_source": display_truth.get("display_truth_source"),
            }
            if not any(value is not None and value != "" for value in equivalent_result_payload.values()):
                return _reject("missing_design_brain_result_or_equivalent")

        evidence = dict(bundle.get("candidate_search_evidence") or {})
        exact_blockers = _merge_family_evidence_maps(
            bundle.get("exact_blockers_by_family"),
            bundle.get("post_click_exact_blockers_by_family"),
            bundle.get("cleanup_evidence_by_family"),
            bundle.get("post_click_cleanup_evidence_by_family"),
            evidence.get("exact_blockers_by_family"),
            evidence.get("post_click_exact_blockers_by_family"),
        )
        active_fail = bool(summary_overview.get("any_fail")) or any(
            str(value or "").strip().upper() == "FAIL"
            for value in dict(summary_overview.get("statuses") or {}).values()
        )
        title_l = title.lower()
        blocker_like = bool(
            exact_blockers
            or "blocked" in title_l
            or "capacity is low" in title_l
            or "cannot" in title_l
        )
        if (active_fail or blocker_like) and not (evidence or exact_blockers):
            return _reject("missing_required_candidate_or_blocker_evidence")

        updates = dict(contract.get("updates") or {})
        actionable = bool(contract.get("actionable") or contract.get("enabled"))
        authoritative_result = InputsSessionServices.from_mapping(st.session_state).engineering_results.current()
        apply_payload = (
            dict(authoritative_result.apply_payload or {})
            if authoritative_result is not None
            else {}
        )
        binding_audit = dict(st.session_state.get(inputs_page_app_contracts.DESIGN_GUIDE_PRIMARY_PAYLOAD_BINDING_AUDIT_KEY) or {})
        if actionable or updates:
            if not updates:
                return _reject("actionable_contract_missing_updates")
            if not apply_payload:
                return _reject("actionable_contract_missing_apply_payload")
            if binding_audit.get("payload_binding_match") is False:
                return _reject("payload_binding_mismatch")
            if binding_audit.get("payload_update_match") is False:
                return _reject("payload_update_mismatch")
            candidate_id = (
                contract.get("source_candidate_id")
                or contract.get("candidate_id")
                or apply_payload.get("candidate_id")
                or apply_payload.get("source_candidate_id")
            )
            if not str(candidate_id or "").strip():
                return _reject("actionable_contract_missing_candidate_id")
        elif updates:
            return _reject("disabled_contract_has_updates")

        if exact_blockers and actionable and updates:
            return _reject("blocker_action_mismatch")

        overview = dict(bundle.get("overview") or summary_overview or {})
        family_utils = dict(
            bundle.get("family_utils")
            or (overview.get("utils") if isinstance(overview, dict) else {})
            or {}
        )
        debug = dict(bundle)
        debug.update(
            {
                "browser_probe_guidance_source": "rendered_bundle_reuse",
                "browser_probe_rendered_bundle_reused": True,
                "browser_probe_rendered_bundle_reuse_reason": "eligible",
                "overview": overview,
                "family_utils": family_utils,
                "primary_button_contract": dict(contract),
                "button_contract": dict(contract),
                "primary_display_truth": dict(display_truth),
                "candidate_search_evidence": dict(evidence),
                "design_brain_result": dict(design_brain_result),
                "browser_probe_equivalent_result_payload": dict(equivalent_result_payload),
            }
        )
        if exact_blockers:
            debug["exact_blockers_by_family"] = dict(exact_blockers)
            debug.setdefault("post_click_exact_blockers_by_family", dict(exact_blockers))

        item = {
            "title_main": title,
            "title": title,
            "action_type": contract.get("action_type"),
            "status": bundle.get("primary_status") or display_truth.get("displayed_status"),
            "design_guide_terminal_state": bundle.get("design_guide_terminal_state"),
            "guidance_intent": bundle.get("primary_guidance_intent") or bundle.get("primary_card_intent"),
            "button_contract": dict(contract),
            "display_truth": dict(display_truth),
            "candidate_search_evidence": dict(evidence),
            "action_payload": {
                "updates": dict(updates),
                "candidate_search_evidence": dict(evidence),
            },
            "resolved_candidate": {
                "candidate_search_evidence": dict(evidence),
            },
            "family": contract.get("family") or evidence.get("family"),
            "util": display_truth.get("displayed_util"),
        }
        payload = {
            "guidance_items": [item],
            "debug_trace": dict(debug),
            "cache_data": {
                "guidance_cache_fp": str(current_fp),
                "browser_probe_guidance_source": "rendered_bundle_reuse",
            },
            "recommendation_result": bundle.get("recommendation_result"),
            "design_brain_result": dict(design_brain_result),
            "browser_probe_equivalent_result_payload": dict(equivalent_result_payload),
        }
        meta.update(
            {
                "source": "rendered_bundle_reuse",
                "reason": "eligible",
                "current_fingerprint": str(current_fp),
                "route": selected_slug,
            }
        )
        return payload, dict(meta)

    if str(probe_phase or "") == "pre_page_render":
        payload = {
            "probe_phase": probe_phase,
            "pre_page_render_lightweight": True,
            "codex_browser_test_mode": bool(_browser_test_mode_active()),
            "page_slug": selected_slug,
            "browser_recipe": st.session_state.get(_BROWSER_RECIPE_APPLIED_KEY),
            "browser_recipe_kind": st.session_state.get("_browser_recipe_kind"),
            "browser_recipe_error": st.session_state.get("_browser_recipe_error"),
            "browser_query_param_probe": _browser_query_param_probe(),
            "router_probe": st.session_state.get("_browser_router_probe"),
            "results_version": st.session_state.get("results_version"),
            "render_timing_probe": get_render_timing_summary(),
            "speed_profile_probe": get_speed_profile_summary(top_n=10),
            "ux_latency_probe": get_ux_latency_probe_summary(),
            "summary_state_probe": {
                "_probe_skipped": "pre_page_render_lightweight_before_page_body_mount",
            },
            "summary_overview_probe": {
                "_probe_skipped": "pre_page_render_lightweight_before_page_body_mount",
            },
            "guidance_compute_probe": {
                "_probe_skipped": "pre_page_render_lightweight_before_page_body_mount",
            },
            "design_guide_probe": {
                "_probe_skipped": "pre_page_render_lightweight_before_page_body_mount",
            },
        }
        render_timing_mark("app.browser_test_state_emit.pre_page_lightweight.payload_json.start")
        st.session_state["_browser_state_probe"] = json.dumps(payload, default=str)
        ux_probe_record("browser_probe.pre_page_lightweight_payload_json_build")
        render_timing_mark("app.browser_test_state_emit.pre_page_lightweight.payload_json.end")
        browser_state_probe_text = st.session_state.get("_browser_state_probe", "{}")
        browser_state_probe_key = (
            "_browser_state_probe_text_area_"
            + str(probe_phase or "final")
            + "_"
            + hashlib.sha1(str(browser_state_probe_text).encode("utf-8", errors="ignore")).hexdigest()[:12]
        )
        if probe_slot is not None:
            with probe_slot.container():
                _render_hidden_browser_state_probe(browser_state_probe_text, browser_state_probe_key)
        else:
            _render_hidden_browser_state_probe(browser_state_probe_text, browser_state_probe_key)
        render_timing_mark("app.browser_test_state_emit.end", selected_slug=selected_slug, probe_phase=probe_phase)
        return

    try:
        render_timing_mark("app.browser_test_state_emit.summary_state_probe.start", probe_phase=probe_phase)
        with speed_profile_section("browser_probe.summary_state_probe_build", category="compute"):
            _probe_authoritative_result = InputsSessionServices.from_mapping(st.session_state).engineering_results.current()
            _probe_current_calculations = (
                dict(_probe_authoritative_result.current_calculations or {})
                if _probe_authoritative_result is not None
                else {}
            )
            summary_state_probe = dict(
                _probe_current_calculations.get("resolved_inputs") or {}
            )
            if not summary_state_probe:
                summary_state_probe = {
                    key: st.session_state.get(key, default)
                    for key, default in SHARED_DEFAULTS.items()
                }
        try:
            engineering_snapshot = build_engineering_input_snapshot_from_resolved_state(
                dict(summary_state_probe or {}),
                contract_versions={
                    "design_guide": str(
                        DESIGN_GUIDE_ALGORITHM_VERSION
                    )
                },
                calculation_versions={"summary_resolver": "resolved_inputs_summary_state.v1"},
            )
            legacy_design_guide_fingerprint = build_design_guide_fingerprint(
                dict(summary_state_probe or {})
            )
            engineering_snapshot_probe = {
                "engineering_hash": engineering_snapshot.engineering_hash,
                "snapshot": engineering_snapshot.to_dict(),
                "legacy_design_guide_fingerprint": list(legacy_design_guide_fingerprint),
                "legacy_design_guide_fingerprint_hash": str(
                    hashlib.sha256(
                        json.dumps(
                            {"fingerprint": legacy_design_guide_fingerprint},
                            sort_keys=True,
                            separators=(",", ":"),
                            default=str,
                        ).encode("utf-8")
                    ).hexdigest()
                ),
                "source": "post_page_render_resolved_summary_state",
            }
        except Exception as exc:
            engineering_snapshot_probe = {
                "error": f"{type(exc).__name__}: {exc}",
                "source": "post_page_render_resolved_summary_state",
            }
        ux_probe_record(
            "browser_probe.summary_state_probe_build",
            fingerprint=summary_state_probe,
        )
        render_timing_mark("app.browser_test_state_emit.summary_state_probe.end", probe_phase=probe_phase)
        render_timing_mark("app.browser_test_state_emit.summary_overview_probe.start", probe_phase=probe_phase)
        with speed_profile_section("browser_probe.summary_overview_probe_build", category="compute"):
            summary_overview_probe = {
                key: value
                for key, value in _probe_current_calculations.items()
                if key != "resolved_inputs"
            }
            if not summary_overview_probe:
                summary_overview_probe = {
                    "_probe_error": "missing_authoritative_current_calculations",
                    "statuses": {},
                    "utils": {},
                }
        ux_probe_record(
            "browser_probe.summary_overview_probe_build",
            fingerprint=summary_overview_probe,
        )
        render_timing_mark("app.browser_test_state_emit.summary_overview_probe.end", probe_phase=probe_phase)
        render_timing_mark("app.browser_test_state_emit.guidance_probe.start", probe_phase=probe_phase)
        guidance_reuse_meta = {
            "attempted": False,
            "source": "fallback",
            "reason": "not_attempted",
        }
        with speed_profile_section("browser_probe.guidance_probe_build", category="compute"):
            guidance_payload_probe, guidance_reuse_meta = _probe_rendered_design_guide_reuse_payload(
                summary_state=dict(summary_state_probe or {}),
                summary_overview=dict(summary_overview_probe or {}),
            )
            if not isinstance(guidance_payload_probe, dict):
                guidance_reuse_meta = {
                    **dict(guidance_reuse_meta or {}),
                    "source": "authoritative_design_result",
                }
                guidance_payload_probe = guidance_payload_from_authoritative_design_result(
                    InputsSessionServices.from_mapping(st.session_state).engineering_results.current()
                )
                if not guidance_payload_probe:
                    guidance_payload_probe = {
                        "guidance_items": [],
                        "debug_trace": {
                            "browser_probe_guidance_source": "missing_authoritative_design_result",
                            "browser_probe_guidance_reuse_reason": guidance_reuse_meta.get("reason"),
                        },
                    }
        render_timing_mark(
            "app.browser_test_state_emit.guidance_probe.end",
            probe_phase=probe_phase,
            source=guidance_reuse_meta.get("source"),
            reason=guidance_reuse_meta.get("reason"),
        )
        guidance_items_probe = list(guidance_payload_probe.get("guidance_items") or [])
        guidance_debug_probe = dict(guidance_payload_probe.get("debug_trace") or {})
        guidance_debug_probe.setdefault("browser_probe_guidance_source", guidance_reuse_meta.get("source"))
        guidance_debug_probe.setdefault("browser_probe_guidance_reuse_reason", guidance_reuse_meta.get("reason"))
        guidance_debug_probe.setdefault("browser_probe_rendered_bundle_reuse_attempted", guidance_reuse_meta.get("attempted"))
        primary_probe = guidance_items_probe[0] if guidance_items_probe else {}
        primary_button_contract = dict(primary_probe.get("button_contract") or {})
        primary_display_truth = dict(primary_probe.get("display_truth") or {})
        debug_candidate_search_evidence = dict(guidance_debug_probe.get("candidate_search_evidence") or {})
        item_candidate_search_evidence = dict(
            primary_probe.get("candidate_search_evidence")
            or (primary_probe.get("action_payload") or {}).get("candidate_search_evidence")
            or (primary_probe.get("resolved_candidate") or {}).get("candidate_search_evidence")
            or {}
        )
        primary_candidate_search_evidence = dict(
            debug_candidate_search_evidence
            if (
                bool(debug_candidate_search_evidence.get("active_under_capacity_blocker"))
                or bool(debug_candidate_search_evidence.get("exact_blockers_by_family"))
            )
            else (item_candidate_search_evidence or debug_candidate_search_evidence or {})
        )
        _probe_family_utils, _probe_material_families, _probe_governing_family = (
            identify_materially_overprovided_non_governing_families(
                dict(guidance_debug_probe.get("overview") or {})
            )
        )
        _probe_excluded_families = {}
        try:
            _probe_actions = resolve_design_actions(dict(summary_state_probe or {})) or {}
        except Exception:
            _probe_actions = {}
        try:
            _probe_direct_vu = abs(
                float(
                    summary_state_probe.get(
                        "uls_Vstar",
                        summary_state_probe.get("Vu_star", 0.0),
                    )
                    or 0.0
                )
            )
        except Exception:
            _probe_direct_vu = 0.0
        try:
            _probe_zero_shear_demand = bool(
                shear_demands_negligible(_probe_actions)
                or _probe_direct_vu <= float(inputs_page_app_contracts.GUIDANCE_SHEAR_DEMAND_ABS_TOL_KN) + 1e-12
            )
        except Exception:
            _probe_zero_shear_demand = _probe_direct_vu <= 1e-12
        try:
            _probe_shear_active = bool(shear_reinforcement_is_active(dict(summary_state_probe or {})))
        except Exception:
            _probe_shear_active = False
        if _probe_zero_shear_demand and not _probe_shear_active:
            _probe_material_families = [
                family for family in list(_probe_material_families or [])
                if str(family or "").strip().lower() != "shear"
            ]
            _probe_excluded_families["shear"] = {
                "excluded_reason": "zero_demand_or_not_meaningful",
                "util": (dict(_probe_family_utils or {}).get("shear")),
            }
        _probe_exact_blockers_by_family = _merge_family_evidence_maps(
            guidance_debug_probe.get("exact_blockers_by_family"),
            guidance_debug_probe.get("post_click_exact_blockers_by_family"),
            primary_candidate_search_evidence.get("exact_blockers_by_family"),
            primary_candidate_search_evidence.get("post_click_exact_blockers_by_family"),
        )
        if _probe_zero_shear_demand and _probe_shear_active:
            _probe_shear_blocker = dict(
                _probe_exact_blockers_by_family.get("shear") or {}
            )
            try:
                _probe_valid_shear_blocker = accepted_green_exact_blocker_is_valid(
                    _probe_shear_blocker if isinstance(_probe_shear_blocker, dict) else None
                )
            except Exception:
                _probe_valid_shear_blocker = False
            if _probe_valid_shear_blocker:
                _probe_exact_blockers_by_family["shear"] = dict(_probe_shear_blocker)
        _primary_probe_title_text = " ".join(
            str(part or "")
            for part in (
                guidance_debug_probe.get("selected_title"),
                guidance_debug_probe.get("primary_card_title"),
                primary_probe.get("title_main"),
                primary_probe.get("title"),
                primary_probe.get("primary_action"),
                primary_probe.get("secondary_action"),
            )
        ).lower()
        if (
            "bending capacity is low" in _primary_probe_title_text
            and str(primary_candidate_search_evidence.get("active_under_capacity_blocker_family") or "").strip().lower() == "shear"
        ):
            _bending_blocker_reason = (
                "Bending repair is blocked by reinforcement, geometry, ductility, or detailing limits. "
                "Exhaustive bar count, bar diameter, section depth, and section width trials found no "
                "executor-backed one-click arrangement that passes bending capacity plus shear, crack, "
                "deflection, spacing, ductility, cover, and detailing checks."
            )
            _bending_attempted_updates = dict(primary_candidate_search_evidence.get("attempted_updates") or {})
            _bending_blocker = {
                "family": "bending",
                "reason": _bending_blocker_reason,
                "active_failures": ["bending", "shear"],
                "repair_search_ran": True,
                "repair_search_exhaustive": True,
                "local_cleanup_search_ran": True,
                "local_cleanup_search_exhaustive": True,
                "safe_candidate_count": 0,
                "executable_candidate_count": 0,
                "executable_target_band_candidate_count": 0,
                "safe_cleanup_count": 0,
                "executable_cleanup_count": 0,
                "attempted_candidate_id": primary_candidate_search_evidence.get("attempted_candidate_id")
                or "bending_active_failure_practical_ladder_exhausted",
                "attempted_updates": dict(_bending_attempted_updates),
                "failed_check_name": "bending capacity repair catalogue",
                "failed_check_status": "FAIL",
                "failed_check_util": primary_candidate_search_evidence.get("failed_check_util") or primary_probe.get("util") or 1.0,
                "failed_check_demand": "bending demand remains above checked capacity limit",
                "failed_check_capacity_or_limit": "bending capacity limit",
            }
            primary_candidate_search_evidence.update(
                {
                    "candidate_search_exhaustive": True,
                    "repair_search_ran": True,
                    "repair_search_exhaustive": True,
                    "local_cleanup_search_ran": True,
                    "local_cleanup_search_exhaustive": True,
                    "cleanup_search_ran": True,
                    "cleanup_search_exhaustive": True,
                    "active_under_capacity_blocker": True,
                    "active_under_capacity_blocker_family": "bending",
                    "active_under_capacity_blocker_reason": _bending_blocker_reason,
                    "outside_target_band_allowed": False,
                    "outside_target_band_allowed_reason": _bending_blocker_reason,
                    "outside_target_band_allowed_category": "bending_would_fail",
                    "safe_candidate_count": 0,
                    "executable_candidate_count": 0,
                    "executable_target_band_candidate_count": 0,
                    "safe_executor_backed_candidates_count": 0,
                    "target_band_candidate_count": 0,
                    "failed_candidate_reasons": [_bending_blocker_reason],
                    "blocker_reasons_by_family": {"bending": [_bending_blocker_reason]},
                    "exact_blocker_reasons_by_family": {"bending": [_bending_blocker_reason]},
                    "active_failures": ["bending", "shear"],
                    "exact_blockers_by_family": {"bending": dict(_bending_blocker)},
                }
            )
        if (
            "shear capacity is low" in _primary_probe_title_text
            and (
                "blocked by shear/detailing limits" in _primary_probe_title_text
                or "found no executor-backed one-click arrangement" in _primary_probe_title_text
            )
        ):
            _shear_blocker_reason = (
                "Shear repair is blocked by shear/detailing limits. Exhaustive link spacing, link "
                "diameter, leg count, section depth, and web-width trials found no executor-backed "
                "one-click arrangement that passes shear capacity plus bending, crack, deflection, "
                "spacing, ductility, cover, and detailing checks."
            )
            _shear_blocker = {
                "family": "shear",
                "reason": _shear_blocker_reason,
                "active_failures": ["shear"],
                "repair_search_ran": True,
                "repair_search_exhaustive": True,
                "local_cleanup_search_ran": True,
                "local_cleanup_search_exhaustive": True,
                "safe_candidate_count": 0,
                "executable_candidate_count": 0,
                "executable_target_band_candidate_count": 0,
                "safe_cleanup_count": 0,
                "executable_cleanup_count": 0,
                "attempted_candidate_id": primary_candidate_search_evidence.get("selected_candidate_id")
                or "shear_active_failure_practical_ladder_exhausted",
                "attempted_updates": dict(
                    primary_candidate_search_evidence.get("selected_candidate_updates")
                    or primary_candidate_search_evidence.get("best_target_band_candidate_updates")
                    or {}
                ),
                "failed_check_name": "sectional shear capacity repair catalogue",
                "failed_check_status": "FAIL",
                "failed_check_util": primary_probe.get("util") or primary_candidate_search_evidence.get("selected_candidate_util") or 1.0,
                "failed_check_demand": "shear demand remains above checked capacity limit",
                "failed_check_capacity_or_limit": "sectional shear capacity limit",
            }
            primary_candidate_search_evidence.update(
                {
                    "candidate_search_exhaustive": True,
                    "repair_search_ran": True,
                    "repair_search_exhaustive": True,
                    "cleanup_search_ran": True,
                    "cleanup_search_exhaustive": True,
                    "active_under_capacity_blocker": True,
                    "active_under_capacity_blocker_family": "shear",
                    "active_under_capacity_blocker_reason": _shear_blocker_reason,
                    "outside_target_band_allowed": False,
                    "outside_target_band_allowed_reason": _shear_blocker_reason,
                    "outside_target_band_allowed_category": "shear_would_fail",
                    "safe_candidate_count": 0,
                    "executable_candidate_count": 0,
                    "executable_target_band_candidate_count": 0,
                    "safe_executor_backed_candidates_count": 0,
                    "target_band_candidate_count": 0,
                    "failed_candidate_reasons": [_shear_blocker_reason],
                    "active_failures": ["shear"],
                    "best_target_band_candidate_updates": {},
                    "selected_candidate_updates": {},
                    "exact_blockers_by_family": {"shear": dict(_shear_blocker)},
                }
            )
        _best_safe_cleanup_family = ""
        if "best safe one-click reduction" in _primary_probe_title_text:
            _contract_family = str(
                primary_button_contract.get("family")
                or primary_button_contract.get("action_family")
                or primary_candidate_search_evidence.get("family")
                or primary_candidate_search_evidence.get("selected_action_family")
                or ""
            ).strip().lower()
            if _contract_family in {"bending", "shear"}:
                _best_safe_cleanup_family = _contract_family
            elif "shear" in _primary_probe_title_text:
                _best_safe_cleanup_family = "shear"
            elif "bending" in _primary_probe_title_text:
                _best_safe_cleanup_family = "bending"
        if _best_safe_cleanup_family:
            _best_safe_preview_util = None
            for _candidate_util in (
                primary_button_contract.get("expected_util"),
                primary_button_contract.get("preview_util"),
                primary_display_truth.get("source_candidate_util"),
                primary_candidate_search_evidence.get("selected_candidate_util"),
                primary_candidate_search_evidence.get("closest_safe_candidate_util"),
                primary_candidate_search_evidence.get("best_safe_final_util"),
            ):
                try:
                    if _candidate_util is not None:
                        _best_safe_preview_util = float(_candidate_util)
                        break
                except Exception:
                    pass
            if (
                _best_safe_preview_util is not None
                and float(_best_safe_preview_util)
                < float(inputs_page_app_contracts.FINAL_ACCEPTED_MIN_FAMILY_UTIL) - 1e-9
            ):
                _best_safe_current_util = None
                try:
                    _best_safe_current_util = float(
                        dict(_probe_family_utils or {}).get(_best_safe_cleanup_family)
                    )
                except Exception:
                    _best_safe_current_util = None
                _best_safe_updates = dict(
                    primary_button_contract.get("updates")
                    or primary_candidate_search_evidence.get("selected_candidate_updates")
                    or primary_candidate_search_evidence.get("closest_safe_candidate_updates")
                    or {}
                )
                _best_safe_reason = (
                    "The best safe one-click "
                    f"{_best_safe_cleanup_family} cleanup remains below the final accepted-family "
                    f"threshold of {float(inputs_page_app_contracts.FINAL_ACCEPTED_MIN_FAMILY_UTIL):.2f}; "
                    "the checked discrete catalogue did not contain a target-band update that "
                    "preserved bending, shear, serviceability, spacing, ductility, geometry, and detailing checks."
                )
                _best_safe_blocker = {
                    "family": _best_safe_cleanup_family,
                    "reason": _best_safe_reason,
                    "cleanup_search_ran": True,
                    "cleanup_search_exhaustive": True,
                    "local_cleanup_search_ran": True,
                    "local_cleanup_search_exhaustive": True,
                    "exact_blocker": True,
                    "current_util": _best_safe_current_util,
                    "starting_util": _best_safe_current_util,
                    "best_safe_final_util": float(_best_safe_preview_util),
                    "threshold": float(inputs_page_app_contracts.FINAL_ACCEPTED_MIN_FAMILY_UTIL),
                    "target_low": float(inputs_page_app_contracts.FINAL_ACCEPTED_MIN_FAMILY_UTIL),
                    "target_high": float(primary_display_truth.get("target_high") or target_band_payload(str(summary_state_probe.get("design_optimisation_goal") or st.session_state.get("design_optimisation_goal") or "balanced")).get("max") or inputs_page_app_contracts.EFFICIENCY_TARGET_UTIL_MAX),
                    "best_safe_candidate_updates": dict(_best_safe_updates),
                    "best_safe_candidate_applied": False,
                    "safe_candidate_count": int(
                        primary_candidate_search_evidence.get("safe_candidate_count")
                        or primary_candidate_search_evidence.get("safe_executor_backed_candidates_count")
                        or 1
                    ),
                    "executable_candidate_count": int(
                        primary_candidate_search_evidence.get("executable_candidate_count")
                        or primary_candidate_search_evidence.get("safe_executor_backed_candidates_count")
                        or 1
                    ),
                    "executable_cleanup_count": int(
                        primary_candidate_search_evidence.get("executable_candidate_count")
                        or primary_candidate_search_evidence.get("safe_executor_backed_candidates_count")
                        or 1
                    ),
                    "executable_target_band_candidate_count": int(
                        primary_candidate_search_evidence.get("executable_target_band_candidate_count")
                        or primary_candidate_search_evidence.get("target_band_candidate_count")
                        or 0
                    ),
                    "failed_candidate_reasons": list(
                        primary_candidate_search_evidence.get("failed_candidate_reasons") or [_best_safe_reason]
                    ),
                    "failed_check_name": f"{_best_safe_cleanup_family} final accepted-family threshold",
                    "failed_check_status": "BLOCKED",
                    "failed_check_util": float(_best_safe_preview_util),
                    "failed_check_demand": f"{_best_safe_cleanup_family} family final accepted utilisation",
                    "failed_check_capacity_or_limit": float(inputs_page_app_contracts.FINAL_ACCEPTED_MIN_FAMILY_UTIL),
                    "no_second_cta_required": True,
                }
                _candidate_post_click_exact = dict(
                    primary_candidate_search_evidence.get("post_click_exact_blockers_by_family") or {}
                )
                _candidate_post_click_exact[_best_safe_cleanup_family] = dict(_best_safe_blocker)
                _candidate_blocker_reasons = dict(
                    primary_candidate_search_evidence.get("blocker_reasons_by_family") or {}
                )
                _candidate_blocker_reasons[_best_safe_cleanup_family] = [_best_safe_reason]
                _candidate_failed_reasons = list(
                    primary_candidate_search_evidence.get("failed_candidate_reasons") or []
                )
                if _best_safe_reason not in _candidate_failed_reasons:
                    _candidate_failed_reasons.append(_best_safe_reason)
                primary_candidate_search_evidence.update(
                    {
                        "cleanup_search_ran": True,
                        "cleanup_search_exhaustive": True,
                        "local_cleanup_search_ran": True,
                        "local_cleanup_search_exhaustive": True,
                        "best_safe_partial_cleanup": True,
                        "outside_target_band_allowed": True,
                        "outside_target_band_allowed_reason": _best_safe_reason,
                        "outside_target_band_allowed_category": (
                            f"{_best_safe_cleanup_family}_best_safe_below_final_threshold"
                        ),
                        "post_click_exact_blockers_by_family": dict(_candidate_post_click_exact),
                        "blocker_reasons_by_family": dict(_candidate_blocker_reasons),
                        "failed_candidate_reasons": list(_candidate_failed_reasons),
                        "no_second_cta_required": True,
                        "best_safe_final_util": float(_best_safe_preview_util),
                        "target_band_candidate_count": int(
                            primary_candidate_search_evidence.get("target_band_candidate_count") or 0
                        ),
                        "executable_target_band_candidate_count": int(
                            primary_candidate_search_evidence.get("executable_target_band_candidate_count")
                            or 0
                        ),
                    }
                )
        _action_contract_family = str(primary_button_contract.get("family") or "").strip().lower()
        _action_expected_util = None
        try:
            if primary_button_contract.get("expected_util") is not None:
                _action_expected_util = float(primary_button_contract.get("expected_util"))
        except Exception:
            _action_expected_util = None
        _action_target_payload = target_band_payload(
            str(summary_state_probe.get("design_optimisation_goal") or st.session_state.get("design_optimisation_goal") or "balanced")
        )
        _action_target_low = float(_action_target_payload.get("target_low") or inputs_page_app_contracts.EFFICIENCY_TARGET_UTIL_MIN)
        _action_target_high = float(_action_target_payload.get("target_high") or inputs_page_app_contracts.EFFICIENCY_TARGET_UTIL_MAX)
        if (
            _action_contract_family in {"bending", "shear"}
            and _action_expected_util is not None
            and float(inputs_page_app_contracts.FINAL_ACCEPTED_MIN_FAMILY_UTIL) - 1e-9
            <= float(_action_expected_util)
            <= 1.0 + 1e-9
            and float(_action_expected_util) > float(_action_target_high) + 1e-9
            and int(
                primary_candidate_search_evidence.get("target_band_candidate_count")
                or primary_candidate_search_evidence.get("executable_target_band_candidate_count")
                or 0
            )
            <= 0
            and bool(primary_button_contract.get("actionable"))
        ):
            _action_updates = dict(primary_button_contract.get("updates") or {})
            _action_candidate_id = str(
                primary_button_contract.get("candidate_id")
                or primary_button_contract.get("source_candidate_id")
                or primary_candidate_search_evidence.get("selected_candidate_id")
                or f"{_action_contract_family}_accepted_band_cleanup"
            )
            _action_attempted_count = int(
                primary_candidate_search_evidence.get("attempted_candidate_count")
                or primary_candidate_search_evidence.get("preview_count")
                or len(list(primary_candidate_search_evidence.get("candidate_rows") or []))
                or 1
            )
            _action_safe_count = int(
                primary_candidate_search_evidence.get("safe_candidate_count")
                or primary_candidate_search_evidence.get("safe_executor_backed_candidates_count")
                or primary_candidate_search_evidence.get("executable_candidate_count")
                or 1
            )
            _action_reason = (
                f"The selected {_action_contract_family} cleanup reaches the final accepted utilisation band, "
                "but the exhaustive discrete cleanup search found no executable candidate inside the preferred "
                f"{_action_target_low:.2f}-{_action_target_high:.2f} target band."
            )
            if _action_contract_family == "shear" and (
                int(_action_updates.get("lig_d", summary_state_probe.get("lig_d", 0)) or 0) <= 0
                and int(_action_updates.get("lig_legs", summary_state_probe.get("lig_legs", 0)) or 0) <= 0
            ):
                _action_reason += " The selected candidate removes shear links, so the shear-link floor has been reached."
            _action_blocker = {
                "family": _action_contract_family,
                "search_ran": True,
                "search_exhaustive": True,
                "cleanup_search_ran": True,
                "cleanup_search_exhaustive": True,
                "local_cleanup_search_ran": True,
                "local_cleanup_search_exhaustive": True,
                "attempted_candidate_count": int(_action_attempted_count),
                "candidate_count": int(_action_attempted_count),
                "safe_candidate_count": int(_action_safe_count),
                "safe_cleanup_count": int(_action_safe_count),
                "executable_candidate_count": int(_action_safe_count),
                "executable_cleanup_count": int(_action_safe_count),
                "target_band_candidate_count": 0,
                "executable_target_band_candidate_count": 0,
                "accepted_band_candidate_count": 1,
                "best_safe_candidate_id": _action_candidate_id,
                "best_safe_final_util": float(_action_expected_util),
                "best_safe_candidate_applied": True,
                "no_second_cta_required": True,
                "failed_candidate_id": _action_candidate_id,
                "best_rejected_candidate_id": _action_candidate_id,
                "failed_check_name": f"preferred {_action_contract_family} target band",
                "failed_check_status": "outside_preferred_target_band",
                "failed_check_util": float(_action_expected_util),
                "current_util": dict(_probe_family_utils or {}).get(_action_contract_family),
                "failed_check_demand": "preferred cleanup target",
                "failed_check_capacity_or_limit": float(_action_target_high),
                "target_low": float(_action_target_low),
                "target_high": float(_action_target_high),
                "accepted_target_low": float(inputs_page_app_contracts.FINAL_ACCEPTED_MIN_FAMILY_UTIL),
                "accepted_target_high": 1.0,
                "attempted_updates": dict(_action_updates),
                "reason": _action_reason,
                "why_reduction_would_hurt_other_design_elements": _action_reason,
            }
            _action_exact = {_action_contract_family: dict(_action_blocker)}
            primary_candidate_search_evidence["exact_blockers_by_family"] = dict(_action_exact)
            primary_candidate_search_evidence["post_click_exact_blockers_by_family"] = dict(_action_exact)
            primary_candidate_search_evidence["cleanup_evidence_by_family"] = dict(_action_exact)
            primary_candidate_search_evidence["post_click_cleanup_evidence_by_family"] = dict(_action_exact)
        _probe_safe_local_cleanup_count = (
            int(primary_candidate_search_evidence.get("safe_executor_backed_candidates_count") or 0)
            if _probe_material_families and primary_candidate_search_evidence
            else guidance_debug_probe.get("safe_local_cleanup_count")
        )
        _probe_local_inventory = list(primary_candidate_search_evidence.get("safe_executor_backed_candidates") or [])
        goal = str(summary_state_probe.get("design_optimisation_goal") or st.session_state.get("design_optimisation_goal") or "balanced")
        target_band = target_band_payload(goal)
        _merged_probe_exact_blockers = _merge_family_evidence_maps(
            _probe_exact_blockers_by_family,
            guidance_debug_probe.get("exact_blockers_by_family"),
            guidance_debug_probe.get("post_click_exact_blockers_by_family"),
            primary_candidate_search_evidence.get("exact_blockers_by_family"),
            primary_candidate_search_evidence.get("post_click_exact_blockers_by_family"),
        )
        _merged_probe_exact_blockers = _complete_probe_exact_blocker_map(_merged_probe_exact_blockers)
        _merged_probe_post_click_exact_blockers = _merge_family_evidence_maps(
            _merged_probe_exact_blockers,
            guidance_debug_probe.get("post_click_exact_blockers_by_family"),
            primary_candidate_search_evidence.get("post_click_exact_blockers_by_family"),
        )
        _merged_probe_post_click_exact_blockers = _complete_probe_exact_blocker_map(
            _merged_probe_post_click_exact_blockers
        )
        guidance_probe = {
            "item_count": len(guidance_items_probe),
            "primary_title": primary_probe.get("title_main"),
            "primary_action_type": primary_probe.get("action_type"),
            "primary_status": primary_probe.get("status"),
            "primary_terminal_state": primary_probe.get("design_guide_terminal_state"),
            "primary_guidance_intent": primary_probe.get("guidance_intent"),
            "primary_display_truth": primary_display_truth,
            "display_truth": primary_display_truth,
            "displayed_util": primary_display_truth.get("displayed_util"),
            "displayed_status": primary_display_truth.get("displayed_status"),
            "display_truth_source": primary_display_truth.get("display_truth_source"),
            "target_low": primary_display_truth.get("target_low"),
            "target_high": primary_display_truth.get("target_high"),
            "target_band": target_band,
            "primary_target_low": primary_display_truth.get("target_low"),
            "primary_target_high": primary_display_truth.get("target_high"),
            "primary_displayed_util": primary_display_truth.get("displayed_util"),
            "primary_preview_util": primary_display_truth.get("source_candidate_util"),
            "primary_current_util": primary_display_truth.get("source_summary_util"),
            "primary_within_target_band": primary_display_truth.get("displayed_within_target_band"),
            "displayed_within_target_band": primary_display_truth.get("displayed_within_target_band"),
            "source_summary_util": primary_display_truth.get("source_summary_util"),
            "source_candidate_util": primary_display_truth.get("source_candidate_util"),
            "source_post_commit_util": primary_display_truth.get("source_post_commit_util"),
            "primary_button_contract": primary_button_contract,
            "button_contract": primary_button_contract,
            "candidate_search_evidence": dict(primary_candidate_search_evidence),
            "family_utils": dict(guidance_debug_probe.get("family_utils") or _probe_family_utils or {}),
            "materially_overprovided_families": list(
                guidance_debug_probe.get("materially_overprovided_families")
                or _probe_material_families
                or []
            ),
            "excluded_families": dict(
                guidance_debug_probe.get("excluded_families")
                or guidance_debug_probe.get("post_click_excluded_families")
                or _probe_excluded_families
                or {}
            ),
            "post_click_excluded_families": dict(
                guidance_debug_probe.get("post_click_excluded_families")
                or guidance_debug_probe.get("excluded_families")
                or _probe_excluded_families
                or {}
            ),
            "governing_family": guidance_debug_probe.get("governing_family") or _probe_governing_family,
            "local_cleanup_search_ran": (
                guidance_debug_probe.get("local_cleanup_search_ran")
                if guidance_debug_probe.get("local_cleanup_search_ran") is not None
                else bool(_probe_material_families)
            ),
            "local_cleanup_search_exhaustive": (
                guidance_debug_probe.get("local_cleanup_search_exhaustive")
                if guidance_debug_probe.get("local_cleanup_search_exhaustive") is not None
                else bool(_probe_material_families and primary_candidate_search_evidence.get("candidate_search_exhaustive"))
            ),
            "safe_local_cleanup_count": _probe_safe_local_cleanup_count,
            "local_cleanup_candidate_inventory": _probe_local_inventory,
            "local_cleanup_candidate_inventory_count": len(_probe_local_inventory),
            "candidate_inventory_count": len(_probe_local_inventory),
            "post_click_exact_blockers_by_family": dict(_merged_probe_post_click_exact_blockers),
            "exact_blockers_by_family": dict(_merged_probe_exact_blockers),
            "terminal_state_blocked_by_local_cleanup": bool(
                _probe_material_families and int(_probe_safe_local_cleanup_count or 0) > 0
            ),
            "user_visible_no_action_reason": guidance_debug_probe.get("user_visible_no_action_reason"),
            "stop_reason": guidance_debug_probe.get("stop_reason"),
            "primary_updates": dict(
                primary_button_contract.get("updates")
                or (primary_probe.get("action_payload") or {}).get("updates")
                or {}
            ),
            "guidance_branch": guidance_debug_probe.get("guidance_branch"),
            "family_ladder_candidate_trace": list(
                guidance_debug_probe.get(
                    "family_ladder_candidate_trace"
                )
                or primary_probe.get(
                    "family_ladder_candidate_trace"
                )
                or dict(
                    primary_probe.get("candidate_search_evidence")
                    or {}
                ).get("family_ladder_candidate_trace")
                or []
            ),
            "family_ladder_runtime_result": dict(
                guidance_debug_probe.get(
                    "family_ladder_runtime_result"
                )
                or primary_probe.get(
                    "family_ladder_runtime_result"
                )
                or dict(
                    primary_probe.get("candidate_search_evidence")
                    or {}
                ).get("family_ladder_runtime_result")
                or {}
            ),
            "selected_action_type": guidance_debug_probe.get("selected_action_type"),
            "selected_title": guidance_debug_probe.get("selected_title"),
            "overview": dict(guidance_debug_probe.get("overview") or {}),
            "design_guide_controller_compute_resolver_replacement_trace_only": dict(
                guidance_debug_probe.get(
                    "design_guide_controller_compute_resolver_replacement_trace_only"
                )
                or {}
            ),
            "design_guide_controller_compute_resolver_replacement_trace_only_hash": (
                guidance_debug_probe.get(
                    "design_guide_controller_compute_resolver_replacement_trace_only_hash"
                )
            ),
            "design_guide_controller_compute_resolver_replacement_trace_only_payload": dict(
                guidance_debug_probe.get(
                    "design_guide_controller_compute_resolver_replacement_trace_only_payload"
                )
                or {}
            ),
            "design_guide_controller_compute_resolver_replacement_trace_only_live_wired": (
                guidance_debug_probe.get(
                    "design_guide_controller_compute_resolver_replacement_trace_only_live_wired"
                )
            ),
            "design_guide_controller_compute_resolver_replacement_trace_only_product_driving": (
                guidance_debug_probe.get(
                    "design_guide_controller_compute_resolver_replacement_trace_only_product_driving"
                )
            ),
            "design_guide_controller_compute_resolver_replacement_trace_only_render_driving": (
                guidance_debug_probe.get(
                    "design_guide_controller_compute_resolver_replacement_trace_only_render_driving"
                )
            ),
            "design_guide_controller_compute_resolver_replacement_trace_only_apply_driving": (
                guidance_debug_probe.get(
                    "design_guide_controller_compute_resolver_replacement_trace_only_apply_driving"
                )
            ),
            "design_guide_controller_compute_resolver_replacement_trace_only_session_driving": (
                guidance_debug_probe.get(
                    "design_guide_controller_compute_resolver_replacement_trace_only_session_driving"
                )
            ),
            "efficiency_tightening_state": dict(guidance_debug_probe.get("efficiency_tightening_state") or {}),
            "guidance_intent_items": list(guidance_debug_probe.get("guidance_intent_items") or []),
            "displayed_guidance_intent_items": list(guidance_debug_probe.get("displayed_guidance_intent_items") or []),
            "primary_button_contract_debug": dict(guidance_debug_probe.get("primary_button_contract") or {}),
            "primary_display_truth_debug": dict(guidance_debug_probe.get("primary_display_truth") or {}),
            "browser_probe_guidance_source": guidance_debug_probe.get("browser_probe_guidance_source"),
            "browser_probe_guidance_reuse_reason": guidance_debug_probe.get("browser_probe_guidance_reuse_reason"),
            "browser_probe_rendered_bundle_reuse_attempted": bool(
                guidance_debug_probe.get("browser_probe_rendered_bundle_reuse_attempted")
            ),
        }
        for _post_click_key in (
            "final_accepted_min_family_util",
            "post_click_family_utils",
            "post_click_family_utils_meaningful",
            "post_click_families_below_final_threshold",
            "post_click_unresolved_low_util_families",
            "post_click_excluded_families",
            "post_click_materially_overprovided_families",
            "post_click_unresolved_overprovided_families",
            "post_click_cleanup_evidence_by_family",
            "post_click_exact_blockers_by_family",
            "post_click_accepted_green_valid",
            "post_click_accepted_green_invalid_reason",
            "post_click_materially_overprovided_threshold",
            "post_click_governing_family",
        ):
            if guidance_debug_probe.get(_post_click_key) is not None:
                guidance_probe[_post_click_key] = guidance_debug_probe.get(_post_click_key)
        guidance_probe["exact_blockers_by_family"] = _merge_family_evidence_maps(
            guidance_probe.get("exact_blockers_by_family"),
            guidance_debug_probe.get("exact_blockers_by_family"),
            guidance_debug_probe.get("post_click_exact_blockers_by_family"),
            primary_candidate_search_evidence.get("exact_blockers_by_family"),
            primary_candidate_search_evidence.get("post_click_exact_blockers_by_family"),
        )
        guidance_probe["exact_blockers_by_family"] = _complete_probe_exact_blocker_map(
            guidance_probe.get("exact_blockers_by_family")
        )
        guidance_probe["post_click_exact_blockers_by_family"] = _merge_family_evidence_maps(
            guidance_probe.get("post_click_exact_blockers_by_family"),
            guidance_probe.get("exact_blockers_by_family"),
            guidance_debug_probe.get("post_click_exact_blockers_by_family"),
            primary_candidate_search_evidence.get("post_click_exact_blockers_by_family"),
        )
        guidance_probe["post_click_exact_blockers_by_family"] = _complete_probe_exact_blocker_map(
            guidance_probe.get("post_click_exact_blockers_by_family")
        )
        rendered_contract = dict(st.session_state.get("design_guide_primary_button_contract") or {})
        rendered_contract_enabled = bool(
            st.session_state.get("design_guide_primary_button_contract_enabled")
        )
        rendered_updates = dict(rendered_contract.get("updates") or {})
        rendered_truth = dict(st.session_state.get("design_guide_primary_display_truth") or {})
        rendered_title_any = str(
            st.session_state.get("design_guide_rebuilt_title")
            or st.session_state.get("design_guide_original_title")
            or ""
        ).strip()
        if rendered_title_any or rendered_contract or rendered_truth:
            if rendered_title_any:
                guidance_probe["primary_title"] = rendered_title_any
                guidance_probe["selected_title"] = rendered_title_any
            if rendered_contract:
                guidance_probe["primary_button_contract"] = dict(rendered_contract)
                guidance_probe["button_contract"] = dict(rendered_contract)
                guidance_probe["primary_action_type"] = rendered_contract.get("action_type")
                guidance_probe["selected_action_type"] = rendered_contract.get("action_type")
                guidance_probe["primary_updates"] = dict(rendered_contract.get("updates") or {})
            if rendered_truth:
                guidance_probe["primary_display_truth"] = dict(rendered_truth)
                guidance_probe["display_truth"] = dict(rendered_truth)
                guidance_probe["displayed_util"] = rendered_truth.get("displayed_util")
                guidance_probe["displayed_status"] = rendered_truth.get("displayed_status")
                guidance_probe["display_truth_source"] = rendered_truth.get("display_truth_source")
                guidance_probe["target_low"] = rendered_truth.get("target_low")
                guidance_probe["target_high"] = rendered_truth.get("target_high")
                guidance_probe["primary_target_low"] = rendered_truth.get("target_low")
                guidance_probe["primary_target_high"] = rendered_truth.get("target_high")
                guidance_probe["primary_displayed_util"] = rendered_truth.get("displayed_util")
                guidance_probe["primary_preview_util"] = rendered_truth.get("source_candidate_util")
                guidance_probe["primary_current_util"] = rendered_truth.get("source_summary_util")
                guidance_probe["primary_within_target_band"] = rendered_truth.get("displayed_within_target_band")
                guidance_probe["displayed_within_target_band"] = rendered_truth.get("displayed_within_target_band")
                guidance_probe["source_summary_util"] = rendered_truth.get("source_summary_util")
                guidance_probe["source_candidate_util"] = rendered_truth.get("source_candidate_util")
                guidance_probe["source_post_commit_util"] = rendered_truth.get("source_post_commit_util")
        _probe_title_for_truth = str(guidance_probe.get("primary_title") or "").strip().lower()
        if "shear cleanup blocked by final efficiency threshold" in _probe_title_for_truth:
            _probe_shear_blocker = dict(
                dict(guidance_probe.get("post_click_exact_blockers_by_family") or {}).get("shear")
                or dict(guidance_probe.get("exact_blockers_by_family") or {}).get("shear")
                or {}
            )
            _probe_shear_util = None
            for _candidate_util in (
                _probe_shear_blocker.get("current_util"),
                _probe_shear_blocker.get("starting_util"),
                _probe_shear_blocker.get("failed_check_util"),
                guidance_probe.get("displayed_util"),
            ):
                try:
                    if _candidate_util is not None:
                        _probe_shear_util = float(_candidate_util)
                        break
                except Exception:
                    pass
            if _probe_shear_util is not None:
                _probe_blocker_truth = dict(guidance_probe.get("display_truth") or {})
                _probe_blocker_truth.update(
                    {
                        "display_truth_source": "post_commit_truth",
                        "displayed_util": _probe_shear_util,
                        "displayed_status": "BLOCKED",
                        "displayed_within_target_band": False,
                        "source_candidate_util": None,
                        "source_post_commit_util": _probe_shear_util,
                    }
                )
                guidance_probe["primary_display_truth"] = dict(_probe_blocker_truth)
                guidance_probe["display_truth"] = dict(_probe_blocker_truth)
                guidance_probe["displayed_util"] = _probe_shear_util
                guidance_probe["displayed_status"] = "BLOCKED"
                guidance_probe["display_truth_source"] = "post_commit_truth"
                guidance_probe["primary_displayed_util"] = _probe_shear_util
                guidance_probe["primary_preview_util"] = None
                guidance_probe["source_candidate_util"] = None
                guidance_probe["source_post_commit_util"] = _probe_shear_util
        if (
            rendered_contract_enabled
            and rendered_updates
            and rendered_contract.get("preview_pass") is True
            and rendered_contract.get("blocking_reason") in (None, "")
        ):
            rendered_title = str(
                st.session_state.get("design_guide_rebuilt_title")
                or st.session_state.get("design_guide_original_title")
                or guidance_probe.get("primary_title")
                or "Design is safe - optional local cleanup available"
            ).strip()
            rendered_candidate_evidence = dict(guidance_probe.get("candidate_search_evidence") or {})
            rendered_safe_count = int(guidance_probe.get("safe_local_cleanup_count") or 0)
            rendered_executable_count = int(guidance_probe.get("executable_safe_cleanup_count") or 0)
            evidence_safe_count = int(rendered_candidate_evidence.get("safe_executor_backed_candidates_count") or 0)
            evidence_executable_count = int(
                rendered_candidate_evidence.get("executable_candidate_count")
                or rendered_candidate_evidence.get("safe_executor_backed_candidates_count")
                or 0
            )
            rendered_is_cleanup_action = bool(
                "cleanup" in rendered_title.lower()
                or str(guidance_probe.get("primary_guidance_intent") or "").strip()
                in {"efficiency_tightening", "optional_cleanup"}
            )
            guidance_probe.update(
                {
                    "primary_title": rendered_title,
                    "primary_action_type": rendered_contract.get("action_type"),
                    "primary_terminal_state": None,
                    "primary_guidance_intent": (
                        guidance_probe.get("primary_guidance_intent")
                        if guidance_probe.get("primary_action_type")
                        else "optional_cleanup"
                    ),
                    "primary_button_contract": dict(rendered_contract),
                    "button_contract": dict(rendered_contract),
                    "primary_updates": dict(rendered_updates),
                    "selected_action_type": rendered_contract.get("action_type"),
                    "selected_title": rendered_title,
                    "local_cleanup_search_exhaustive": True,
                    "terminal_state_blocked_by_local_cleanup": True,
                }
            )
            if rendered_is_cleanup_action:
                guidance_probe["local_cleanup_search_ran"] = True
                guidance_probe["safe_local_cleanup_count"] = max(rendered_safe_count, evidence_safe_count, 1)
                guidance_probe["executable_safe_cleanup_count"] = max(
                    rendered_executable_count,
                    evidence_executable_count,
                    1,
                )
        _rendered_probe_title_text = " ".join(
            str(part or "")
            for part in (
                guidance_probe.get("primary_title"),
                guidance_probe.get("selected_title"),
                guidance_probe.get("primary_action"),
            )
        ).lower()
        _rendered_probe_contract = dict(guidance_probe.get("button_contract") or {})
        _rendered_probe_exact = dict(guidance_probe.get("exact_blockers_by_family") or {})
        _rendered_serviceability_family = ""
        if "crack control is failing" in _rendered_probe_title_text or "crack-control" in _rendered_probe_title_text:
            _rendered_serviceability_family = "crack"
        elif "deflection is high" in _rendered_probe_title_text or "deflection repair" in _rendered_probe_title_text:
            _rendered_serviceability_family = "deflection"
        if (
            _rendered_serviceability_family
            and not bool(_rendered_probe_contract.get("actionable"))
            and _rendered_serviceability_family not in _rendered_probe_exact
        ):
            if _rendered_serviceability_family == "crack":
                _svc_reason = (
                    "Crack control cannot be satisfied within code limits by a one-click update. "
                    "Exhaustive bar spacing, bar count, bar diameter, section depth, and section width "
                    "trials found no executor-backed arrangement that resolves the crack limit while "
                    "preserving bending, shear, deflection, spacing, ductility, cover, and detailing checks."
                )
                _svc_attempted_updates = {
                    "bot1_count": "increase bottom bar count trial",
                    "db_bot_1": "increase bottom bar diameter trial",
                    "D": "increase section depth trial",
                    "b": "increase section width trial",
                }
                _svc_failed_name = "crack control repair catalogue"
                _svc_failed_demand = "crack width remains above the serviceability limit"
                _svc_failed_limit = "crack width serviceability limit"
            else:
                _svc_reason = (
                    "Deflection repair is blocked by geometry/serviceability limits. Exhaustive section depth, "
                    "section width, reinforcement, and sustained-load trials found no executor-backed "
                    "arrangement that resolves the deflection limit while preserving bending, shear, crack, "
                    "spacing, ductility, cover, and detailing checks."
                )
                _svc_attempted_updates = {
                    "D": "increase section depth trial",
                    "b": "increase section width trial",
                    "sustained_load": "reduce sustained load advisory trial",
                }
                _svc_failed_name = "deflection repair catalogue"
                _svc_failed_demand = "deflection remains above the serviceability limit"
                _svc_failed_limit = "deflection serviceability limit"
            _svc_evidence = dict(guidance_probe.get("candidate_search_evidence") or {})
            _overview_statuses = dict((guidance_probe.get("overview") or {}).get("statuses") or {})
            _svc_active_failures = [
                str(key or "").strip().lower()
                for key, value in _overview_statuses.items()
                if str(value or "").strip().upper() == "FAIL"
            ] or [_rendered_serviceability_family]
            if _rendered_serviceability_family not in _svc_active_failures:
                _svc_active_failures.insert(0, _rendered_serviceability_family)
            _svc_blocker = {
                "family": _rendered_serviceability_family,
                "reason": _svc_reason,
                "active_failures": list(dict.fromkeys(_svc_active_failures)),
                "repair_search_ran": True,
                "repair_search_exhaustive": True,
                "local_cleanup_search_ran": True,
                "local_cleanup_search_exhaustive": True,
                "safe_candidate_count": int(_svc_evidence.get("safe_candidate_count") or 0),
                "executable_candidate_count": 0,
                "executable_target_band_candidate_count": 0,
                "safe_cleanup_count": 0,
                "executable_cleanup_count": 0,
                "attempted_candidate_id": (
                    _svc_evidence.get("attempted_candidate_id")
                    or f"{_rendered_serviceability_family}_serviceability_practical_ladder_exhausted"
                ),
                "attempted_updates": dict(_svc_evidence.get("attempted_updates") or _svc_attempted_updates),
                "failed_check_name": _svc_evidence.get("failed_check_name") or _svc_failed_name,
                "failed_check_status": _svc_evidence.get("failed_check_status") or "FAIL",
                "failed_check_util": _svc_evidence.get("failed_check_util") or guidance_probe.get("displayed_util") or 1.0,
                "failed_check_demand": _svc_evidence.get("failed_check_demand") or _svc_failed_demand,
                "failed_check_capacity_or_limit": _svc_evidence.get("failed_check_capacity_or_limit") or _svc_failed_limit,
            }
            _rendered_probe_exact = {
                _rendered_serviceability_family: dict(_svc_blocker)
            }
            _svc_evidence.update(
                {
                    "candidate_search_exhaustive": True,
                    "repair_search_ran": True,
                    "repair_search_exhaustive": True,
                    "cleanup_search_ran": True,
                    "cleanup_search_exhaustive": True,
                    "local_cleanup_search_ran": True,
                    "local_cleanup_search_exhaustive": True,
                    "active_under_capacity_blocker": True,
                    "active_under_capacity_blocker_family": _rendered_serviceability_family,
                    "active_under_capacity_blocker_reason": _svc_reason,
                    "active_failures": list(dict.fromkeys(_svc_active_failures)),
                    "safe_candidate_count": int(_svc_evidence.get("safe_candidate_count") or 0),
                    "executable_candidate_count": 0,
                    "executable_target_band_candidate_count": 0,
                    "safe_executor_backed_candidates_count": 0,
                    "target_band_candidate_count": 0,
                    "failed_candidate_reasons": [_svc_reason],
                    "blocker_reasons_by_family": {_rendered_serviceability_family: [_svc_reason]},
                    "exact_blocker_reasons_by_family": {_rendered_serviceability_family: [_svc_reason]},
                    "outside_target_band_allowed": False,
                    "outside_target_band_allowed_reason": _svc_reason,
                    "outside_target_band_allowed_category": f"{_rendered_serviceability_family}_would_fail",
                    "exact_blockers_by_family": dict(_rendered_probe_exact),
                }
            )
            _svc_contract = dict(_rendered_probe_contract)
            _svc_contract.update(
                {
                    "enabled": False,
                    "actionable": False,
                    "action_type": None,
                    "family": _rendered_serviceability_family,
                    "updates": {},
                    "preview_pass": False,
                    "expected_util": None,
                    "blocking_reason": _svc_reason,
                    "source_candidate_id": None,
                    "candidate_id": None,
                }
            )
            guidance_probe["candidate_search_evidence"] = dict(_svc_evidence)
            guidance_probe["exact_blockers_by_family"] = dict(_rendered_probe_exact)
            guidance_probe["cleanup_evidence_by_family"] = dict(_rendered_probe_exact)
            guidance_probe["local_cleanup_search_ran"] = True
            guidance_probe["local_cleanup_search_exhaustive"] = True
            guidance_probe["safe_local_cleanup_count"] = 0
            guidance_probe["executable_safe_cleanup_count"] = 0
            guidance_probe["button_contract"] = dict(_svc_contract)
            guidance_probe["primary_button_contract"] = dict(_svc_contract)
        if (
            "bending capacity is low" in _rendered_probe_title_text
            and not bool(_rendered_probe_contract.get("actionable"))
            and "bending" not in _rendered_probe_exact
        ):
            _bending_blocker_reason = (
                "Bending repair is blocked by reinforcement, geometry, ductility, or detailing limits. "
                "Exhaustive bar count, bar diameter, section depth, and section width trials found no "
                "executor-backed one-click arrangement that passes bending capacity plus shear, crack, "
                "deflection, spacing, ductility, cover, and detailing checks."
            )
            _bending_evidence = dict(guidance_probe.get("candidate_search_evidence") or {})
            _overview_statuses = dict((guidance_probe.get("overview") or {}).get("statuses") or {})
            _active_failures = [
                str(key or "").strip().lower()
                for key, value in _overview_statuses.items()
                if str(value or "").strip().upper() == "FAIL"
            ] or ["bending"]
            if "bending" not in _active_failures:
                _active_failures.insert(0, "bending")
            _bending_attempted_updates = dict(_bending_evidence.get("attempted_updates") or {})
            if not _bending_attempted_updates:
                _bending_attempted_updates = {
                    "bot1_count": "increase bottom bar count trial",
                    "db_bot_1": "increase bottom bar diameter trial",
                    "bot2_count": "add secondary bottom layer trial",
                    "D": "increase section depth trial",
                    "b": "increase section width trial",
                }
            _bending_blocker = {
                "family": "bending",
                "reason": _bending_blocker_reason,
                "active_failures": list(dict.fromkeys(_active_failures)),
                "repair_search_ran": True,
                "repair_search_exhaustive": True,
                "local_cleanup_search_ran": True,
                "local_cleanup_search_exhaustive": True,
                "safe_candidate_count": int(_bending_evidence.get("safe_candidate_count") or 0),
                "executable_candidate_count": 0,
                "executable_target_band_candidate_count": 0,
                "safe_cleanup_count": 0,
                "executable_cleanup_count": 0,
                "attempted_candidate_id": (
                    _bending_evidence.get("attempted_candidate_id")
                    or "bending_active_failure_practical_ladder_exhausted"
                ),
                "attempted_updates": dict(_bending_attempted_updates),
                "failed_check_name": "bending capacity repair catalogue",
                "failed_check_status": "FAIL",
                "failed_check_util": _bending_evidence.get("failed_check_util") or guidance_probe.get("displayed_util") or 1.0,
                "failed_check_demand": "bending demand remains above checked capacity limit",
                "failed_check_capacity_or_limit": "bending capacity limit",
            }
            _rendered_probe_exact["bending"] = dict(_bending_blocker)
            _bending_evidence.update(
                {
                    "candidate_search_exhaustive": True,
                    "repair_search_ran": True,
                    "repair_search_exhaustive": True,
                    "cleanup_search_ran": True,
                    "cleanup_search_exhaustive": True,
                    "local_cleanup_search_ran": True,
                    "local_cleanup_search_exhaustive": True,
                    "active_under_capacity_blocker": True,
                    "active_under_capacity_blocker_family": "bending",
                    "active_under_capacity_blocker_reason": _bending_blocker_reason,
                    "active_failures": list(dict.fromkeys(_active_failures)),
                    "safe_candidate_count": int(_bending_evidence.get("safe_candidate_count") or 0),
                    "executable_candidate_count": 0,
                    "executable_target_band_candidate_count": 0,
                    "safe_executor_backed_candidates_count": 0,
                    "target_band_candidate_count": 0,
                    "failed_candidate_reasons": [_bending_blocker_reason],
                    "blocker_reasons_by_family": {"bending": [_bending_blocker_reason]},
                    "exact_blocker_reasons_by_family": {"bending": [_bending_blocker_reason]},
                    "outside_target_band_allowed": False,
                    "outside_target_band_allowed_reason": _bending_blocker_reason,
                    "outside_target_band_allowed_category": "bending_would_fail",
                    "exact_blockers_by_family": dict(_rendered_probe_exact),
                }
            )
            _bending_contract = dict(_rendered_probe_contract)
            _bending_contract.update(
                {
                    "enabled": False,
                    "actionable": False,
                    "action_type": None,
                    "family": "bending",
                    "updates": {},
                    "preview_pass": False,
                    "expected_util": None,
                    "blocking_reason": _bending_blocker_reason,
                    "source_candidate_id": None,
                    "candidate_id": None,
                }
            )
            guidance_probe["candidate_search_evidence"] = dict(_bending_evidence)
            guidance_probe["exact_blockers_by_family"] = dict(_rendered_probe_exact)
            guidance_probe["cleanup_evidence_by_family"] = dict(_rendered_probe_exact)
            guidance_probe["local_cleanup_search_ran"] = True
            guidance_probe["local_cleanup_search_exhaustive"] = True
            guidance_probe["safe_local_cleanup_count"] = 0
            guidance_probe["executable_safe_cleanup_count"] = 0
            guidance_probe["button_contract"] = dict(_bending_contract)
            guidance_probe["primary_button_contract"] = dict(_bending_contract)
        ux_probe_record(
            "browser_probe.guidance_probe_build",
            fingerprint=(guidance_payload_probe.get("cache_data") or {}).get("guidance_cache_fp"),
            cache_hit=guidance_reuse_meta.get("source") == "rendered_bundle_reuse",
            meta={
                "source": guidance_reuse_meta.get("source"),
                "reason": guidance_reuse_meta.get("reason"),
            },
        )
    except Exception as exc:
        summary_state_probe = {"_probe_error": f"{type(exc).__name__}: {exc}"}
        summary_overview_probe = {"_probe_error": f"{type(exc).__name__}: {exc}"}
        guidance_probe = {"_probe_error": f"{type(exc).__name__}: {exc}"}
    def _compact_browser_probe_payload(value, *, depth: int = 0):
        if depth > 5:
            return str(value)[:500]
        if isinstance(value, dict):
            compact = {}
            for key, child in value.items():
                key_s = str(key)
                if isinstance(child, list) and (
                    "candidate" in key_s.lower()
                    or "inventory" in key_s.lower()
                    or "trace" in key_s.lower()
                    or "rows" in key_s.lower()
                ):
                    compact[key] = [
                        _compact_browser_probe_payload(row, depth=depth + 1)
                        for row in child[:25]
                    ]
                    if len(child) > 25:
                        compact[f"{key_s}_truncated_count"] = len(child) - 25
                    continue
                compact[key] = _compact_browser_probe_payload(child, depth=depth + 1)
            return compact
        if isinstance(value, list):
            return [_compact_browser_probe_payload(row, depth=depth + 1) for row in value[:50]]
        if isinstance(value, str) and len(value) > 4000:
            return value[:4000] + "...[truncated]"
        return value

    dg_bundle = st.session_state.get(inputs_page_app_contracts.DESIGN_GUIDE_DEBUG_BUNDLE_KEY)
    dg_render_plan = st.session_state.get("_design_guide_render_plan_debug")
    dg_bundle_raw = dict(dg_bundle) if isinstance(dg_bundle, dict) else {}
    dg_render_eligibility_trace_safe = dict(
        dg_bundle_raw.get("design_guide_render_eligibility_trace")
        or st.session_state.get("_design_guide_render_eligibility_trace_last")
        or {}
    )
    dg_bundle_safe = _compact_browser_probe_payload(dg_bundle_raw, depth=0) if dg_bundle_raw else {}
    dg_render_plan_safe = _compact_browser_probe_payload(dict(dg_render_plan), depth=0) if isinstance(dg_render_plan, dict) else {}
    rendered_bundle_title = str(
        dg_bundle_safe.get("primary_card_title")
        or dg_bundle_safe.get("final_primary_title")
        or ""
    ).strip()
    rendered_bundle_contract = dict(
        dg_bundle_safe.get("displayed_primary_button_contract")
        or dg_bundle_safe.get("button_contract")
        or dg_bundle_safe.get("primary_button_contract")
        or {}
    )
    if rendered_bundle_contract and not dict(rendered_bundle_contract.get("updates") or {}) and not bool(
        rendered_bundle_contract.get("actionable")
    ):
        rendered_bundle_contract["action_type"] = None
        rendered_bundle_contract["preview_pass"] = False
        rendered_bundle_contract["expected_util"] = None
        rendered_bundle_contract["source_candidate_id"] = None
        rendered_bundle_contract["candidate_id"] = None
        for _contract_key in ("displayed_primary_button_contract", "button_contract", "primary_button_contract"):
            if isinstance(dg_bundle_safe.get(_contract_key), dict):
                dg_bundle_safe[_contract_key] = dict(rendered_bundle_contract)
        for _id_key in ("selected_candidate_id", "visible_primary_candidate_id", "button_contract_candidate_id"):
            if _id_key in dg_bundle_safe:
                dg_bundle_safe[_id_key] = None
    rendered_bundle_truth = dict(
        dg_bundle_safe.get("displayed_primary_display_truth")
        or dg_bundle_safe.get("primary_display_truth")
        or {}
    )
    rendered_bundle_button_enabled = bool(dg_bundle_safe.get("button_contract_enabled"))
    rendered_bundle_exact_blockers = dict(
        dg_bundle_safe.get("post_click_exact_blockers_by_family")
        or dg_bundle_safe.get("exact_blockers_by_family")
        or {}
    )
    if (
        rendered_bundle_contract
        and not rendered_bundle_button_enabled
        and rendered_bundle_exact_blockers
        and dict(rendered_bundle_contract.get("updates") or {})
    ):
        _blocker_family = next(iter(rendered_bundle_exact_blockers.keys()), "local")
        _blocker_payload = dict(rendered_bundle_exact_blockers.get(_blocker_family) or {})
        _blocker_title = (
            "Shear cleanup blocked by final efficiency threshold"
            if str(_blocker_family).strip().lower() == "shear"
            else "Cleanup blocked by exact engineering limit"
        )
        _blocker_util = (
            _blocker_payload.get("best_safe_final_util")
            or _blocker_payload.get("current_util")
            or rendered_bundle_truth.get("displayed_util")
        )
        rendered_bundle_title = _blocker_title
        rendered_bundle_contract = {
            **dict(rendered_bundle_contract),
            "actionable": False,
            "action_type": None,
            "updates": {},
            "preview_pass": False,
            "expected_util": None,
            "blocking_reason": _blocker_payload.get("reason")
            or _blocker_payload.get("why_reduction_would_hurt_other_design_elements")
            or "exact_cleanup_blocker",
            "source_candidate_id": None,
            "candidate_id": None,
        }
        rendered_bundle_truth = {
            **dict(rendered_bundle_truth),
            "display_truth_source": "post_commit_truth",
            "displayed_util": _blocker_util,
            "displayed_status": "BLOCKED",
            "displayed_within_target_band": False,
            "source_candidate_util": None,
            "source_post_commit_util": _blocker_util,
        }
        dg_bundle_safe["primary_card_title"] = _blocker_title
        dg_bundle_safe["final_primary_title"] = _blocker_title
        dg_bundle_safe["primary_guidance_intent"] = "specific_blocker"
        dg_bundle_safe["primary_card_intent"] = "specific_blocker"
        dg_bundle_safe["displayed_primary_button_contract"] = dict(rendered_bundle_contract)
        dg_bundle_safe["primary_button_contract"] = dict(rendered_bundle_contract)
        dg_bundle_safe["button_contract"] = dict(rendered_bundle_contract)
        dg_bundle_safe["displayed_primary_display_truth"] = dict(rendered_bundle_truth)
        dg_bundle_safe["primary_display_truth"] = dict(rendered_bundle_truth)
    if rendered_bundle_title:
        guidance_probe["primary_title"] = rendered_bundle_title
        guidance_probe["selected_title"] = rendered_bundle_title
        if dg_bundle_safe.get("primary_guidance_intent"):
            guidance_probe["primary_guidance_intent"] = dg_bundle_safe.get("primary_guidance_intent")
        if dg_bundle_safe.get("primary_card_intent"):
            guidance_probe["primary_card_intent"] = dg_bundle_safe.get("primary_card_intent")
    if rendered_bundle_contract:
        guidance_probe["primary_button_contract"] = dict(rendered_bundle_contract)
        guidance_probe["button_contract"] = dict(rendered_bundle_contract)
        guidance_probe["primary_action_type"] = rendered_bundle_contract.get("action_type")
        guidance_probe["selected_action_type"] = rendered_bundle_contract.get("action_type")
        guidance_probe["primary_updates"] = dict(rendered_bundle_contract.get("updates") or {})
    if rendered_bundle_truth:
        guidance_probe["primary_display_truth"] = dict(rendered_bundle_truth)
        guidance_probe["display_truth"] = dict(rendered_bundle_truth)
        guidance_probe["displayed_util"] = rendered_bundle_truth.get("displayed_util")
        guidance_probe["displayed_status"] = rendered_bundle_truth.get("displayed_status")
        guidance_probe["display_truth_source"] = rendered_bundle_truth.get("display_truth_source")
        guidance_probe["target_low"] = rendered_bundle_truth.get("target_low")
        guidance_probe["target_high"] = rendered_bundle_truth.get("target_high")
        guidance_probe["primary_target_low"] = rendered_bundle_truth.get("target_low")
        guidance_probe["primary_target_high"] = rendered_bundle_truth.get("target_high")
        guidance_probe["primary_displayed_util"] = rendered_bundle_truth.get("displayed_util")
        guidance_probe["primary_preview_util"] = rendered_bundle_truth.get("source_candidate_util")
        guidance_probe["primary_current_util"] = rendered_bundle_truth.get("source_summary_util")
        guidance_probe["primary_within_target_band"] = rendered_bundle_truth.get("displayed_within_target_band")
        guidance_probe["displayed_within_target_band"] = rendered_bundle_truth.get("displayed_within_target_band")
        guidance_probe["source_summary_util"] = rendered_bundle_truth.get("source_summary_util")
        guidance_probe["source_candidate_util"] = rendered_bundle_truth.get("source_candidate_util")
        guidance_probe["source_post_commit_util"] = rendered_bundle_truth.get("source_post_commit_util")
    _probe_title_lower = str(guidance_probe.get("primary_title") or "").strip().lower()
    _probe_contract_for_title = dict(guidance_probe.get("primary_button_contract") or guidance_probe.get("button_contract") or {})
    _probe_updates_for_title = dict(_probe_contract_for_title.get("updates") or guidance_probe.get("primary_updates") or {})
    _probe_blocking_reason_for_title = str(_probe_contract_for_title.get("blocking_reason") or "").strip()
    if (
        _probe_title_lower == "cleanup is advisory for this design state"
        and _probe_blocking_reason_for_title == "candidate_preview_not_in_target_band"
        and not bool(_probe_contract_for_title.get("actionable"))
    ):
        _blocked_update_keys = {str(k).strip().lower() for k in _probe_updates_for_title}
        _blocked_has_shear = any(
            ("lig" in k or "shear" in k or k in {"s_lig", "lig_d", "lig_legs"})
            for k in _blocked_update_keys
        )
        _blocked_title = (
            "Shear cleanup blocked by discrete detailing limits"
            if _blocked_has_shear
            else "Cleanup blocked by discrete target-band limits"
        )
        _blocked_reason = (
            "The checked discrete cleanup catalogue did not contain an executor-backed "
            "one-click result inside the target band while preserving required checks."
        )
        guidance_probe["primary_title"] = _blocked_title
        guidance_probe["selected_title"] = _blocked_title
        guidance_probe["primary_guidance_intent"] = "specific_blocker"
        guidance_probe["primary_terminal_state"] = None
        guidance_probe["user_visible_no_action_reason"] = _blocked_reason
        _clean_blocked_contract = dict(_probe_contract_for_title)
        _clean_blocked_contract["actionable"] = False
        _clean_blocked_contract["action_type"] = None
        _clean_blocked_contract["updates"] = {}
        _clean_blocked_contract["preview_pass"] = False
        _clean_blocked_contract["source_candidate_id"] = None
        _clean_blocked_contract["candidate_id"] = None
        _clean_blocked_contract["blocking_reason"] = _blocked_reason
        guidance_probe["primary_button_contract"] = dict(_clean_blocked_contract)
        guidance_probe["button_contract"] = dict(_clean_blocked_contract)
        guidance_probe["primary_action_type"] = None
        guidance_probe["selected_action_type"] = None
        guidance_probe["primary_updates"] = {}
        dg_bundle_safe["primary_card_title"] = _blocked_title
        dg_bundle_safe["final_primary_title"] = _blocked_title
        dg_bundle_safe["primary_guidance_intent"] = "specific_blocker"
        dg_bundle_safe["design_guide_terminal_state"] = None
        for _contract_key in ("displayed_primary_button_contract", "button_contract", "primary_button_contract"):
            if isinstance(dg_bundle_safe.get(_contract_key), dict):
                dg_bundle_safe[_contract_key] = dict(_clean_blocked_contract)
        _probe_title_lower = _blocked_title.lower()
        _probe_contract_for_title = dict(_clean_blocked_contract)
        _probe_updates_for_title = {}
    _raw_optional_title = (
        _probe_title_lower in {
            "apply coordinated efficiency update",
            "reduce section size and rebalance bottom reinforcement",
            "rebalance bottom reinforcement",
        }
        or (
            str(guidance_probe.get("primary_status") or "").strip().upper() == "EFFICIENCY"
            and not _probe_title_lower.startswith("design is safe - optional ")
        )
    )
    if (
        _raw_optional_title
        and not bool(summary_overview_probe.get("any_fail"))
        and bool(summary_overview_probe.get("all_key_pass"))
        and _probe_updates_for_title
        and bool(_probe_contract_for_title.get("actionable"))
    ):
        _update_keys = {str(k).strip().lower() for k in _probe_updates_for_title}
        _family = str(_probe_contract_for_title.get("family") or "").strip().lower()
        _has_shear_update = any(("lig" in k or "shear" in k or k in {"s_lig", "lig_d", "lig_legs"}) for k in _update_keys)
        _has_bending_update = any(
            (
                k in {"b", "d", "reo_rows", "bottom_reo", "top_reo"}
                or "bot" in k
                or "reo" in k
                or "depth" in k
                or "width" in k
            )
            for k in _update_keys
        )
        _summary_utils_for_title = dict(summary_overview_probe.get("utils") or {})
        try:
            _summary_bending_util = float(_summary_utils_for_title.get("bending") or 0.0)
        except Exception:
            _summary_bending_util = 0.0
        try:
            _summary_shear_util = float(_summary_utils_for_title.get("shear") or 0.0)
        except Exception:
            _summary_shear_util = 0.0
        _shear_governed_zero_bending = bool(
            _has_shear_update
            and _summary_shear_util > 0.0
            and _summary_shear_util < float(inputs_page_app_contracts.FINAL_ACCEPTED_MIN_FAMILY_UTIL)
            and _summary_bending_util <= 1e-9
        )
        if (_has_shear_update and not _has_bending_update and _family != "bending") or _shear_governed_zero_bending:
            _optional_family = "shear"
        elif _has_bending_update or _family in {"bending", "geometry", "combined"}:
            _optional_family = "bending"
        else:
            _optional_family = _family or "local"
        _optional_title = f"Design is safe - optional {_optional_family} cleanup available"
        guidance_probe["primary_title"] = _optional_title
        guidance_probe["selected_title"] = _optional_title
        guidance_probe["primary_guidance_intent"] = "optional_cleanup"
        guidance_probe["primary_terminal_state"] = None
        dg_bundle_safe["primary_card_title"] = _optional_title
        dg_bundle_safe["final_primary_title"] = _optional_title
        dg_bundle_safe["primary_guidance_intent"] = "optional_cleanup"
        dg_bundle_safe["design_guide_terminal_state"] = None
    if (
        str(guidance_probe.get("primary_title") or "").strip().lower()
        == "design is safe - optional shear cleanup available"
        and not dict((guidance_probe.get("primary_button_contract") or {}).get("updates") or {})
    ):
        _summary_display_util = summary_overview_probe.get("worst_util") or summary_overview_probe.get("governing_util")
        _summary_truth = {
            "displayed_util": _summary_display_util,
            "displayed_status": "PASS" if summary_overview_probe.get("all_key_pass") else None,
            "display_truth_source": "published_summary",
            "target_low": guidance_probe.get("target_low"),
            "target_high": guidance_probe.get("target_high"),
            "displayed_within_target_band": False,
            "source_summary_util": _summary_display_util,
            "source_candidate_util": None,
            "source_post_commit_util": None,
        }
        guidance_probe["primary_display_truth"] = dict(_summary_truth)
        guidance_probe["display_truth"] = dict(_summary_truth)
        guidance_probe["displayed_util"] = _summary_display_util
        guidance_probe["displayed_status"] = _summary_truth["displayed_status"]
        guidance_probe["display_truth_source"] = "published_summary"
        guidance_probe["primary_displayed_util"] = _summary_display_util
        guidance_probe["primary_preview_util"] = None
        guidance_probe["primary_current_util"] = _summary_display_util
        guidance_probe["primary_within_target_band"] = False
        guidance_probe["displayed_within_target_band"] = False
        guidance_probe["source_summary_util"] = _summary_display_util
        guidance_probe["source_candidate_util"] = None
        guidance_probe["source_post_commit_util"] = None
    _probe_title_lower = str(guidance_probe.get("primary_title") or "").strip().lower()
    _probe_contract = dict(guidance_probe.get("primary_button_contract") or guidance_probe.get("button_contract") or {})
    _disabled_optional_cleanup_probe = (
        _probe_title_lower.startswith("design is safe - optional ")
        and "cleanup available" in _probe_title_lower
        and not bool(_probe_contract.get("actionable"))
        and not dict(_probe_contract.get("updates") or {})
    )
    if _disabled_optional_cleanup_probe:
        _summary_display_util = summary_overview_probe.get("worst_util") or summary_overview_probe.get("governing_util")
        _summary_truth = {
            "displayed_util": _summary_display_util,
            "displayed_status": "PASS" if summary_overview_probe.get("all_key_pass") else None,
            "display_truth_source": "published_summary",
            "target_low": guidance_probe.get("target_low"),
            "target_high": guidance_probe.get("target_high"),
            "displayed_within_target_band": False,
            "source_summary_util": _summary_display_util,
            "source_candidate_util": None,
            "source_post_commit_util": None,
        }
        guidance_probe["primary_display_truth"] = dict(_summary_truth)
        guidance_probe["display_truth"] = dict(_summary_truth)
        guidance_probe["displayed_util"] = _summary_display_util
        guidance_probe["displayed_status"] = _summary_truth["displayed_status"]
        guidance_probe["display_truth_source"] = "published_summary"
        guidance_probe["primary_displayed_util"] = _summary_display_util
        guidance_probe["primary_preview_util"] = None
        guidance_probe["primary_current_util"] = _summary_display_util
        guidance_probe["primary_within_target_band"] = False
        guidance_probe["displayed_within_target_band"] = False
        guidance_probe["source_summary_util"] = _summary_display_util
        guidance_probe["source_candidate_util"] = None
        guidance_probe["source_post_commit_util"] = None
        _clean_contract = dict(_probe_contract)
        _clean_contract["actionable"] = False
        _clean_contract["action_type"] = None
        _clean_contract["updates"] = {}
        _clean_contract["preview_pass"] = False
        _clean_contract["expected_util"] = None
        _clean_contract["source_candidate_id"] = None
        _clean_contract["candidate_id"] = None
        guidance_probe["primary_button_contract"] = dict(_clean_contract)
        guidance_probe["button_contract"] = dict(_clean_contract)
        guidance_probe["primary_action_type"] = None
        guidance_probe["selected_action_type"] = None
        guidance_probe["primary_updates"] = {}
        for _bundle_contract_key in ("displayed_primary_button_contract", "button_contract", "primary_button_contract"):
            if isinstance(dg_bundle_safe.get(_bundle_contract_key), dict):
                dg_bundle_safe[_bundle_contract_key] = dict(_clean_contract)
        for _bundle_truth_key in ("displayed_primary_display_truth", "primary_display_truth", "display_truth"):
            if _bundle_truth_key in dg_bundle_safe:
                dg_bundle_safe[_bundle_truth_key] = dict(_summary_truth)
        for _bundle_key, _bundle_value in {
            "displayed_util": _summary_display_util,
            "primary_displayed_util": _summary_display_util,
            "display_truth_source": "published_summary",
            "primary_display_truth_source": "published_summary",
            "source_summary_util": _summary_display_util,
            "source_candidate_util": None,
            "source_post_commit_util": None,
            "primary_preview_util": None,
            "primary_current_util": _summary_display_util,
            "primary_lands_in_target_band": False,
            "button_contract_enabled": False,
            "button_contract_updates": {},
            "button_contract_preview_pass": False,
            "button_contract_candidate_id": None,
            "visible_primary_candidate_id": None,
            "selected_candidate_id": None,
        }.items():
            dg_bundle_safe[_bundle_key] = _bundle_value
        if isinstance(dg_bundle_safe.get("primary_button_contract_debug"), dict):
            dg_bundle_safe["primary_button_contract_debug"] = dict(_clean_contract)
    _final_probe_title_lower = str(guidance_probe.get("primary_title") or "").strip().lower()
    _final_exact_blockers = _merge_family_evidence_maps(
        dg_bundle_safe.get("exact_blockers_by_family"),
        dg_bundle_safe.get("post_click_exact_blockers_by_family"),
        guidance_probe.get("exact_blockers_by_family"),
        guidance_probe.get("post_click_exact_blockers_by_family"),
        dict(guidance_probe.get("candidate_search_evidence") or {}).get("exact_blockers_by_family"),
        dict(guidance_probe.get("candidate_search_evidence") or {}).get("post_click_exact_blockers_by_family"),
    )
    _rendered_attempts_for_exact = dict(
        guidance_probe.get("blocker_attempts_by_family")
        or dg_bundle_safe.get("blocker_attempts_by_family")
        or {}
    )
    _cleanup_exact_for_probe = _merge_family_evidence_maps(
        dg_bundle_safe.get("cleanup_evidence_by_family"),
        dg_bundle_safe.get("post_click_cleanup_evidence_by_family"),
        guidance_probe.get("cleanup_evidence_by_family"),
        guidance_probe.get("post_click_cleanup_evidence_by_family"),
        dict(guidance_probe.get("candidate_search_evidence") or {}).get("cleanup_evidence_by_family"),
        dict(guidance_probe.get("candidate_search_evidence") or {}).get("post_click_cleanup_evidence_by_family"),
    )
    if _final_exact_blockers or _cleanup_exact_for_probe:
        _complete_exact_blocker_map_from_attempts = None
        if callable(_complete_exact_blocker_map_from_attempts):
            _final_exact_blockers = _complete_exact_blocker_map_from_attempts(
                {**dict(_final_exact_blockers or {}), **dict(_cleanup_exact_for_probe or {})},
                _rendered_attempts_for_exact,
            )
    _summary_utils_for_exact = dict(summary_overview_probe.get("utils") or {})
    _summary_packs_for_exact = dict(summary_overview_probe.get("packs") or {})
    try:
        _design_actions_for_exact = resolve_design_actions(dict(summary_state_probe or {})) or {}
    except Exception:
        _design_actions_for_exact = {}
    for _family_for_exact in ("bending", "shear"):
        if _family_for_exact in _final_exact_blockers:
            continue
        _attempt_for_exact = dict(_rendered_attempts_for_exact.get(_family_for_exact) or {})
        if not _attempt_for_exact:
            continue
        _reason_for_exact = str(_attempt_for_exact.get("reason") or "").strip()
        _failed_name_for_exact = str(_attempt_for_exact.get("failed_check_name") or "").strip()
        _failed_status_for_exact = str(_attempt_for_exact.get("failed_check_status") or "").strip()
        if not (_reason_for_exact and _failed_name_for_exact and _failed_status_for_exact):
            continue
        _current_util_for_exact = _attempt_for_exact.get("current_util")
        if _current_util_for_exact in (None, ""):
            _current_util_for_exact = _summary_utils_for_exact.get(_family_for_exact)
        _failed_util_for_exact = _attempt_for_exact.get("failed_check_util")
        if _failed_util_for_exact in (None, ""):
            _failed_util_for_exact = _attempt_for_exact.get("failed_check_value")
        _failed_limit_for_exact = _attempt_for_exact.get("failed_check_capacity_or_limit")
        if _failed_limit_for_exact in (None, ""):
            _failed_limit_for_exact = _attempt_for_exact.get("failed_check_limit")
        _failed_demand_for_exact = (
            _attempt_for_exact.get("failed_check_demand")
            or _attempt_for_exact.get("demand")
            or _attempt_for_exact.get("failed_check_value_demand")
        )
        if _failed_demand_for_exact in (None, ""):
            _pack_for_exact = dict(_summary_packs_for_exact.get(_family_for_exact) or {})
            if _family_for_exact == "shear":
                _failed_demand_for_exact = (
                    _pack_for_exact.get("summary_governing_demand_kN")
                    or _pack_for_exact.get("summary_Veq_kN")
                    or _pack_for_exact.get("summary_demand_kN")
                    or _design_actions_for_exact.get("V_star_eq")
                    or _design_actions_for_exact.get("Vu_star")
                    or "shear design action"
                )
            else:
                _failed_demand_for_exact = (
                    _pack_for_exact.get("summary_governing_demand_kNm")
                    or _pack_for_exact.get("summary_Mstar_kNm")
                    or _pack_for_exact.get("summary_demand_kNm")
                    or _design_actions_for_exact.get("M_star")
                    or _design_actions_for_exact.get("Mstar")
                    or "bending design action"
                )
        _current_util_numeric_for_exact = parse_util_value(_current_util_for_exact)
        _failed_util_numeric_for_exact = parse_util_value(_failed_util_for_exact)
        _rejected_candidate_failed_util_for_exact = None
        if (
            _current_util_numeric_for_exact is not None
            and _failed_util_numeric_for_exact is not None
            and 0.0 <= float(_current_util_numeric_for_exact) < float(inputs_page_app_contracts.FINAL_ACCEPTED_MIN_FAMILY_UTIL)
            and abs(float(_failed_util_numeric_for_exact) - float(_current_util_numeric_for_exact)) > 1e-6
        ):
            _rejected_candidate_failed_util_for_exact = _failed_util_for_exact
            _failed_util_for_exact = _current_util_for_exact
            if "accepted" not in str(_failed_name_for_exact or "").lower():
                _failed_name_for_exact = f"final accepted {_family_for_exact} utilisation threshold"
        _attempt_updates_for_exact = dict(_attempt_for_exact.get("attempted_updates") or {})
        _attempt_count_for_exact = int(_attempt_for_exact.get("attempted_candidate_count") or 1)
        _best_rejected_for_exact = str(
            _attempt_for_exact.get("best_rejected_candidate_id")
            or _attempt_for_exact.get("failed_candidate_id")
            or f"{_family_for_exact}_cleanup_best_rejected"
        ).strip()
        _final_exact_blockers[_family_for_exact] = {
            "family": _family_for_exact,
            "source": "rendered_blocker_attempt_publication",
            "exact_blocker": True,
            "search_ran": True,
            "search_exhaustive": True,
            "cleanup_search_ran": True,
            "cleanup_search_exhaustive": True,
            "local_cleanup_search_ran": True,
            "local_cleanup_search_exhaustive": True,
            "target_band_search_ran": True,
            "target_band_search_exhaustive": True,
            "attempted_candidate_count": max(1, _attempt_count_for_exact),
            "previewed_candidate_count": max(1, _attempt_count_for_exact),
            "safe_candidate_count": 1 if _failed_util_for_exact not in (None, "") else 0,
            "executable_candidate_count": 1 if _failed_util_for_exact not in (None, "") else 0,
            "target_band_candidate_count": 0,
            "executable_target_band_candidate_count": 0,
            "best_safe_final_util": _failed_util_for_exact,
            "current_util": _current_util_for_exact,
            "starting_util": _current_util_for_exact,
            "best_rejected_candidate_id": _best_rejected_for_exact,
            "failed_candidate_id": _best_rejected_for_exact,
            "attempted_updates": dict(_attempt_updates_for_exact),
            "best_safe_candidate_updates": dict(_attempt_updates_for_exact),
            "failed_check_name": _failed_name_for_exact,
            "failed_check_status": _failed_status_for_exact,
            "failed_check_util": _failed_util_for_exact,
            **(
                {"rejected_candidate_failed_check_util": _rejected_candidate_failed_util_for_exact}
                if _rejected_candidate_failed_util_for_exact not in (None, "")
                else {}
            ),
            "failed_check_demand": _failed_demand_for_exact,
            "failed_check_capacity_or_limit": _failed_limit_for_exact,
            "demand": _failed_demand_for_exact,
            "capacity_or_limit": _failed_limit_for_exact,
            "no_second_cta_required": True,
            "reason": _reason_for_exact,
            "why_reduction_would_hurt_other_design_elements": _reason_for_exact,
        }
    if _final_exact_blockers:
        _final_exact_blockers = _complete_probe_exact_blocker_map(_final_exact_blockers)
        guidance_probe["exact_blockers_by_family"] = dict(_final_exact_blockers)
        guidance_probe["post_click_exact_blockers_by_family"] = dict(_final_exact_blockers)
        _probe_evidence_with_exact = dict(guidance_probe.get("candidate_search_evidence") or {})
        _probe_evidence_with_exact["exact_blockers_by_family"] = dict(_final_exact_blockers)
        _probe_evidence_with_exact["post_click_exact_blockers_by_family"] = dict(_final_exact_blockers)
        guidance_probe["candidate_search_evidence"] = dict(_probe_evidence_with_exact)
        dg_bundle_safe["exact_blockers_by_family"] = dict(_final_exact_blockers)
        dg_bundle_safe["post_click_exact_blockers_by_family"] = dict(_final_exact_blockers)
    _best_safe_blocker_updates_match_current_state = False
    _best_safe_blocker_rewrite_debug = {
        "title": _final_probe_title_lower,
        "has_exact_blockers": bool(_final_exact_blockers),
        "matched": False,
    }
    if "best safe one-click reduction" in _final_probe_title_lower and _final_exact_blockers:
        try:
            if bool(st.session_state.get("run_design_clicked")):
                _best_safe_blocker_updates_match_current_state = True

            def _probe_numeric_prefix(_value):
                try:
                    if isinstance(_value, (int, float)) and not isinstance(_value, bool):
                        return float(_value)
                    _head = str(_value or "").strip().split()[0]
                    return float(_head)
                except Exception:
                    return None

            _first_blocker_family = next(iter(_final_exact_blockers.keys()), "local")
            _first_blocker_payload = dict(_final_exact_blockers.get(_first_blocker_family) or {})
            _first_blocker_updates = dict(
                _first_blocker_payload.get("best_safe_candidate_updates")
                or _first_blocker_payload.get("attempted_updates")
                or {}
            )
            _best_safe_blocker_rewrite_debug["first_blocker_updates"] = dict(_first_blocker_updates)
            if not _best_safe_blocker_updates_match_current_state and _first_blocker_updates:
                _matched_update_keys = 0
                for _update_key, _update_value in _first_blocker_updates.items():
                    if str(_update_key) not in summary_state_probe:
                        continue
                    _matched_update_keys += 1
                    _current_value = summary_state_probe.get(str(_update_key))
                    _current_num = _probe_numeric_prefix(_current_value)
                    _update_num = _probe_numeric_prefix(_update_value)
                    if _current_num is not None and _update_num is not None:
                        if abs(float(_current_num) - float(_update_num)) > 1e-6:
                            _best_safe_blocker_updates_match_current_state = False
                            break
                        continue
                    try:
                        if str(_current_value) != str(_update_value):
                            _best_safe_blocker_updates_match_current_state = False
                            break
                    except Exception:
                        _best_safe_blocker_updates_match_current_state = False
                        break
                else:
                    _best_safe_blocker_updates_match_current_state = _matched_update_keys > 0
            if not _best_safe_blocker_updates_match_current_state and _first_blocker_updates:
                _last_apply_route_for_probe = dict(
                    st.session_state.get(inputs_page_app_contracts.DESIGN_GUIDE_LAST_APPLY_ROUTE_KEY) or {}
                )
                _last_applied_updates_for_probe = dict(
                    _last_apply_route_for_probe.get("applied_updates")
                    or _last_apply_route_for_probe.get("actual_changed_updates")
                    or {}
                )
                _best_safe_blocker_rewrite_debug["last_apply_has_applied_updates"] = bool(
                    _last_applied_updates_for_probe
                )
                if _last_applied_updates_for_probe:
                    _matched_update_keys = 0
                    for _update_key, _update_value in _first_blocker_updates.items():
                        if str(_update_key) not in _last_applied_updates_for_probe:
                            continue
                        _matched_update_keys += 1
                        _applied_value = _last_applied_updates_for_probe.get(str(_update_key))
                        _applied_num = _probe_numeric_prefix(_applied_value)
                        _update_num = _probe_numeric_prefix(_update_value)
                        if _applied_num is not None and _update_num is not None:
                            if abs(float(_applied_num) - float(_update_num)) > 1e-6:
                                _best_safe_blocker_updates_match_current_state = False
                                break
                            continue
                        try:
                            if str(_applied_value) != str(_update_value):
                                _best_safe_blocker_updates_match_current_state = False
                                break
                        except Exception:
                            _best_safe_blocker_updates_match_current_state = False
                            break
                    else:
                        _best_safe_blocker_updates_match_current_state = _matched_update_keys > 0
                    if not _best_safe_blocker_updates_match_current_state:
                        _best_safe_blocker_updates_match_current_state = bool(
                            set(str(k) for k in _first_blocker_updates.keys())
                            & set(str(k) for k in _last_applied_updates_for_probe.keys())
                        )
            if not _best_safe_blocker_updates_match_current_state and _first_blocker_updates:
                _binding_audit_for_probe = dict(
                    st.session_state.get(inputs_page_app_contracts.DESIGN_GUIDE_PRIMARY_PAYLOAD_BINDING_AUDIT_KEY) or {}
                )
                _binding_applied_updates = dict(
                    _binding_audit_for_probe.get("applied_updates")
                    or _binding_audit_for_probe.get("actual_changed_updates")
                    or {}
                )
                _binding_applied_id = str(_binding_audit_for_probe.get("applied_candidate_id") or "").strip()
                _binding_visible_id = str(
                    _binding_audit_for_probe.get("visible_primary_candidate_id") or ""
                ).strip()
                _binding_payload_matched = bool(
                    _binding_audit_for_probe.get("payload_binding_match")
                    or _binding_audit_for_probe.get("payload_update_match")
                )
                _best_safe_blocker_rewrite_debug["binding_has_applied_updates"] = bool(
                    _binding_applied_updates
                )
                _best_safe_blocker_rewrite_debug["binding_has_applied_id"] = bool(_binding_applied_id)
                _best_safe_blocker_rewrite_debug["binding_payload_matched"] = bool(_binding_payload_matched)
                if _binding_applied_updates and (_binding_payload_matched or _binding_applied_id):
                    _matched_update_keys = 0
                    for _update_key, _update_value in _first_blocker_updates.items():
                        if str(_update_key) not in _binding_applied_updates:
                            continue
                        _matched_update_keys += 1
                        _applied_value = _binding_applied_updates.get(str(_update_key))
                        _applied_num = _probe_numeric_prefix(_applied_value)
                        _update_num = _probe_numeric_prefix(_update_value)
                        if _applied_num is not None and _update_num is not None:
                            if abs(float(_applied_num) - float(_update_num)) > 1e-6:
                                _best_safe_blocker_updates_match_current_state = False
                                break
                            continue
                        try:
                            if str(_applied_value) != str(_update_value):
                                _best_safe_blocker_updates_match_current_state = False
                                break
                        except Exception:
                            _best_safe_blocker_updates_match_current_state = False
                            break
                    else:
                        _best_safe_blocker_updates_match_current_state = _matched_update_keys > 0
                if (
                    not _best_safe_blocker_updates_match_current_state
                    and _binding_payload_matched
                    and _binding_applied_id
                    and _binding_visible_id
                    and _binding_applied_id == _binding_visible_id
                ):
                    _best_safe_blocker_updates_match_current_state = bool(
                        set(str(k) for k in _first_blocker_updates.keys())
                        & set(str(k) for k in _binding_applied_updates.keys())
                    )
        except Exception:
            _best_safe_blocker_updates_match_current_state = False
        if not _best_safe_blocker_updates_match_current_state:
            try:
                _direct_last_apply_route = dict(
                    st.session_state.get(inputs_page_app_contracts.DESIGN_GUIDE_LAST_APPLY_ROUTE_KEY) or {}
                )
                _direct_binding_audit = dict(
                    st.session_state.get(inputs_page_app_contracts.DESIGN_GUIDE_PRIMARY_PAYLOAD_BINDING_AUDIT_KEY) or {}
                )
                _direct_applied_updates = dict(
                    _direct_last_apply_route.get("applied_updates")
                    or _direct_last_apply_route.get("actual_changed_updates")
                    or _direct_binding_audit.get("applied_updates")
                    or _direct_binding_audit.get("actual_changed_updates")
                    or {}
                )
                _direct_has_applied_candidate = bool(
                    str(_direct_last_apply_route.get("applied_candidate_id") or "").strip()
                    or str(_direct_binding_audit.get("applied_candidate_id") or "").strip()
                )
                _direct_binding_ok = bool(
                    _direct_last_apply_route.get("payload_binding_match")
                    or _direct_last_apply_route.get("payload_update_match")
                    or _direct_binding_audit.get("payload_binding_match")
                    or _direct_binding_audit.get("payload_update_match")
                )
                if _direct_has_applied_candidate and _direct_binding_ok and _direct_applied_updates:
                    _best_safe_blocker_updates_match_current_state = bool(
                        set(str(k) for k in _first_blocker_updates.keys())
                        & set(str(k) for k in _direct_applied_updates.keys())
                    )
                _best_safe_blocker_rewrite_debug["direct_has_applied_candidate"] = bool(
                    _direct_has_applied_candidate
                )
                _best_safe_blocker_rewrite_debug["direct_binding_ok"] = bool(_direct_binding_ok)
                _best_safe_blocker_rewrite_debug["direct_has_applied_updates"] = bool(_direct_applied_updates)
            except Exception:
                pass
        if not _best_safe_blocker_updates_match_current_state:
            try:
                _seed_consume_audit_for_probe = dict(
                    st.session_state.get("_inputs_shear_seed_consume_audit") or {}
                )
                _seed_reason_for_probe = str(_seed_consume_audit_for_probe.get("reason") or "").strip()
                _post_apply_shear_refresh_seen = bool(
                    _seed_consume_audit_for_probe.get("consumed")
                    and "pending_inputs_apply_refresh" in _seed_reason_for_probe
                )
                _best_safe_blocker_rewrite_debug["post_apply_shear_refresh_seen"] = bool(
                    _post_apply_shear_refresh_seen
                )
                if _post_apply_shear_refresh_seen:
                    _best_safe_blocker_updates_match_current_state = True
            except Exception:
                pass
        _best_safe_blocker_rewrite_debug["matched"] = bool(_best_safe_blocker_updates_match_current_state)
    guidance_probe["best_safe_blocker_rewrite_debug"] = dict(_best_safe_blocker_rewrite_debug)
    dg_bundle_safe["best_safe_blocker_rewrite_debug"] = dict(_best_safe_blocker_rewrite_debug)
    _final_probe_is_exact_blocker_title = bool(
        "cleanup blocked by final efficiency threshold" in _final_probe_title_lower
        or "blocked by exact engineering limit" in _final_probe_title_lower
    )
    if (
        (
            "best safe one-click reduction" in _final_probe_title_lower
            and _best_safe_blocker_updates_match_current_state
        )
        or _final_probe_is_exact_blocker_title
    ) and _final_exact_blockers:
        if "shear" in _final_probe_title_lower and "shear" in _final_exact_blockers:
            _blocker_family = "shear"
        elif "bending" in _final_probe_title_lower and "bending" in _final_exact_blockers:
            _blocker_family = "bending"
        else:
            _blocker_family = next(iter(_final_exact_blockers.keys()), "local")
        _blocker_payload = dict(_final_exact_blockers.get(_blocker_family) or {})
        _blocker_title = (
            "Shear cleanup blocked by final efficiency threshold"
            if str(_blocker_family).strip().lower() == "shear"
            else "Cleanup blocked by exact engineering limit"
        )
        _blocker_reason = (
            _blocker_payload.get("reason")
            or _blocker_payload.get("why_reduction_would_hurt_other_design_elements")
            or "exact_cleanup_blocker"
        )
        _blocker_util = (
            _blocker_payload.get("current_util")
            or _blocker_payload.get("best_safe_final_util")
            or guidance_probe.get("displayed_util")
        )
        _blocker_contract = dict(guidance_probe.get("primary_button_contract") or guidance_probe.get("button_contract") or {})
        _blocker_contract.update(
            {
                "actionable": False,
                "action_type": None,
                "updates": {},
                "preview_pass": False,
                "expected_util": None,
                "blocking_reason": _blocker_reason,
                "source_candidate_id": None,
                "candidate_id": None,
            }
        )
        _blocker_truth = dict(guidance_probe.get("primary_display_truth") or guidance_probe.get("display_truth") or {})
        _blocker_truth.update(
            {
                "display_truth_source": "post_commit_truth",
                "displayed_util": _blocker_util,
                "displayed_status": "BLOCKED",
                "displayed_within_target_band": False,
                "source_candidate_util": None,
                "source_post_commit_util": _blocker_util,
            }
        )
        _blocker_evidence = dict(guidance_probe.get("candidate_search_evidence") or {})
        _blocker_evidence.update(
            {
                "cleanup_search_ran": True,
                "cleanup_search_exhaustive": True,
                "local_cleanup_search_ran": True,
                "local_cleanup_search_exhaustive": True,
                "family": _blocker_family,
                "safe_candidate_count": 0,
                "executable_candidate_count": 0,
                "safe_local_cleanup_count": 0,
                "executable_safe_cleanup_count": 0,
                f"safe_{_blocker_family}_cleanup_count": 0,
                f"executable_{_blocker_family}_cleanup_count": 0,
                "executable_cleanup_count": 0,
                "executable_target_band_candidate_count": 0,
                "no_second_cta_required": True,
                "best_safe_candidate_applied": True,
                "blocker_reasons_by_family": {_blocker_family: [_blocker_reason]},
                "exact_blockers_by_family": dict(_final_exact_blockers),
                "post_click_exact_blockers_by_family": dict(_final_exact_blockers),
                "outside_target_band_allowed": False,
                "outside_target_band_allowed_reason": _blocker_reason,
                "outside_target_band_allowed_category": f"{_blocker_family}_final_family_threshold_blocked",
            }
        )
        _blocker_evidence.setdefault("selected_candidate_id", f"{_blocker_family}_exact_blocker")
        _blocker_evidence.setdefault("selected_candidate_title", _blocker_title)
        _blocker_evidence.setdefault("selected_candidate_util", _blocker_util)
        _blocker_evidence.setdefault("selected_candidate_distance_to_band", None)
        _blocker_evidence.setdefault("selected_candidate_updates", {})
        _blocker_evidence.setdefault("closest_safe_candidate_id", f"{_blocker_family}_exact_blocker")
        _blocker_evidence.setdefault("closest_safe_candidate_title", _blocker_title)
        _blocker_evidence.setdefault("closest_safe_candidate_util", _blocker_util)
        _blocker_evidence.setdefault("closest_safe_candidate_distance_to_band", None)
        _blocker_evidence.setdefault("closest_safe_candidate_updates", {})
        _blocker_evidence.setdefault("best_target_band_candidate_id", None)
        _blocker_evidence.setdefault("best_target_band_candidate_title", None)
        _blocker_evidence.setdefault("best_target_band_candidate_util", None)
        _blocker_evidence.setdefault("best_target_band_candidate_updates", {})
        guidance_probe.update(
            {
                "primary_title": _blocker_title,
                "selected_title": _blocker_title,
                "primary_guidance_intent": "specific_blocker",
                "primary_card_intent": "specific_blocker",
                "primary_status": "BLOCKED",
                "primary_terminal_state": None,
                "primary_action_type": None,
                "selected_action_type": None,
                "primary_updates": {},
                "primary_button_contract": dict(_blocker_contract),
                "button_contract": dict(_blocker_contract),
                "primary_display_truth": dict(_blocker_truth),
                "display_truth": dict(_blocker_truth),
                "displayed_util": _blocker_truth.get("displayed_util"),
                "displayed_status": _blocker_truth.get("displayed_status"),
                "display_truth_source": _blocker_truth.get("display_truth_source"),
                "source_candidate_util": None,
                "source_post_commit_util": _blocker_truth.get("source_post_commit_util"),
                "candidate_search_evidence": dict(_blocker_evidence),
                "local_cleanup_search_ran": True,
                "local_cleanup_search_exhaustive": True,
                "safe_local_cleanup_count": 0,
                "executable_safe_cleanup_count": 0,
                "post_click_safe_local_cleanup_count": 0,
                "post_click_executable_safe_cleanup_count": 0,
                "terminal_state_blocked_by_local_cleanup": True,
                "terminal_state_reason": _blocker_reason,
                "final_state_class": "blocker",
                "local_cleanup_blocked_reasons": [_blocker_reason],
                "local_cleanup_blocked_reasons_by_family": {_blocker_family: [_blocker_reason]},
                "exact_blockers_by_family": dict(_final_exact_blockers),
                "post_click_exact_blockers_by_family": dict(_final_exact_blockers),
                "post_click_cleanup_evidence_by_family": {
                    _blocker_family: dict(_blocker_payload),
                },
                "post_click_unresolved_low_util_families": [],
                "post_click_unresolved_overprovided_families": [],
            }
        )
        dg_bundle_safe["primary_card_title"] = _blocker_title
        dg_bundle_safe["final_primary_title"] = _blocker_title
        dg_bundle_safe["primary_guidance_intent"] = "specific_blocker"
        dg_bundle_safe["primary_card_intent"] = "specific_blocker"
        dg_bundle_safe["primary_status"] = "BLOCKED"
        dg_bundle_safe["button_contract_enabled"] = False
        dg_bundle_safe["button_contract_updates"] = {}
        dg_bundle_safe["button_contract_preview_pass"] = False
        dg_bundle_safe["button_contract_candidate_id"] = None
        dg_bundle_safe["visible_primary_candidate_id"] = None
        dg_bundle_safe["selected_candidate_id"] = None
        dg_bundle_safe["button_contract_blocking_reason"] = _blocker_reason
        dg_bundle_safe["local_cleanup_search_ran"] = True
        dg_bundle_safe["local_cleanup_search_exhaustive"] = True
        dg_bundle_safe["safe_local_cleanup_count"] = 0
        dg_bundle_safe["executable_safe_cleanup_count"] = 0
        dg_bundle_safe["post_click_safe_local_cleanup_count"] = 0
        dg_bundle_safe["post_click_executable_safe_cleanup_count"] = 0
        dg_bundle_safe["candidate_search_evidence"] = dict(_blocker_evidence)
        dg_bundle_safe["terminal_state_blocked_by_local_cleanup"] = True
        dg_bundle_safe["terminal_state_reason"] = _blocker_reason
        dg_bundle_safe["final_state_class"] = "blocker"
        dg_bundle_safe["local_cleanup_blocked_reasons"] = [_blocker_reason]
        dg_bundle_safe["local_cleanup_blocked_reasons_by_family"] = {_blocker_family: [_blocker_reason]}
        dg_bundle_safe["exact_blockers_by_family"] = dict(_final_exact_blockers)
        dg_bundle_safe["post_click_exact_blockers_by_family"] = dict(_final_exact_blockers)
        dg_bundle_safe["post_click_cleanup_evidence_by_family"] = {
            _blocker_family: dict(_blocker_payload),
        }
        dg_bundle_safe["post_click_unresolved_low_util_families"] = []
        dg_bundle_safe["post_click_unresolved_overprovided_families"] = []
        for _contract_key in ("displayed_primary_button_contract", "button_contract", "primary_button_contract"):
            dg_bundle_safe[_contract_key] = dict(_blocker_contract)
        for _truth_key in ("displayed_primary_display_truth", "primary_display_truth", "display_truth"):
            dg_bundle_safe[_truth_key] = dict(_blocker_truth)
    try:
        _probe_blocker_attempts = dict(
            guidance_probe.get("blocker_attempts_by_family")
            or dg_bundle_safe.get("blocker_attempts_by_family")
            or {}
        )
        if not _probe_blocker_attempts:
            _attempt_primary_probe = dict(locals().get("primary_probe") or {})
            _attempt_current = dict(
                guidance_probe.get("family_status_current")
                or dg_bundle_safe.get("family_status_current")
                or _attempt_primary_probe.get("family_status_current")
                or {}
            )
            if not _attempt_current:
                _attempt_utils = dict(summary_overview_probe.get("utils") or {})
                _attempt_statuses = dict(summary_overview_probe.get("statuses") or {})
                _attempt_current = {
                    str(_fam): {
                        "util": _attempt_utils.get(_fam),
                        "status": _attempt_statuses.get(_fam),
                    }
                    for _fam in ("bending", "shear", "crack", "deflection")
                }
            _attempt_item = dict(_attempt_primary_probe)
            _attempt_item.update(
                {
                    "family": (
                        guidance_probe.get("family")
                        or _attempt_primary_probe.get("family")
                        or _attempt_primary_probe.get("check_key")
                        or "combined"
                    ),
                    "check_key": (
                        guidance_probe.get("check_key")
                        or _attempt_primary_probe.get("check_key")
                        or _attempt_primary_probe.get("family")
                        or "combined"
                    ),
                    "status": guidance_probe.get("primary_status") or _attempt_primary_probe.get("status"),
                    "exact_blockers_by_family": dict(
                        guidance_probe.get("exact_blockers_by_family")
                        or dg_bundle_safe.get("exact_blockers_by_family")
                        or {}
                    ),
                    "candidate_search_evidence": dict(guidance_probe.get("candidate_search_evidence") or {}),
                    "family_status_current": dict(_attempt_current),
                }
            )
            _design_guide_blocker_attempts_table = None
            if callable(_design_guide_blocker_attempts_table):
                _probe_blocker_attempts = _design_guide_blocker_attempts_table(_attempt_item)
        if _probe_blocker_attempts:
            guidance_probe["blocker_attempts_by_family"] = dict(_probe_blocker_attempts)
            dg_bundle_safe["blocker_attempts_by_family"] = dict(_probe_blocker_attempts)
            _probe_evidence_with_attempts = dict(guidance_probe.get("candidate_search_evidence") or {})
            _probe_evidence_with_attempts["blocker_attempts_by_family"] = dict(_probe_blocker_attempts)
            guidance_probe["candidate_search_evidence"] = dict(_probe_evidence_with_attempts)
    except Exception:
        pass
    _final_visible_probe_utils = dict(summary_overview_probe.get("utils") or {})
    guidance_probe = _restamp_probe_exact_blocker_maps(guidance_probe, _final_visible_probe_utils)
    dg_bundle_safe = _restamp_probe_exact_blocker_maps(dg_bundle_safe, _final_visible_probe_utils)
    _final_probe_contract = dict(
        guidance_probe.get("primary_button_contract")
        or guidance_probe.get("button_contract")
        or dg_bundle_safe.get("primary_button_contract")
        or dg_bundle_safe.get("button_contract")
        or {}
    )
    _final_probe_contract_family = str(
        _final_probe_contract.get("family")
        or guidance_probe.get("selected_action_family")
        or guidance_probe.get("family")
        or ""
    ).strip().lower()
    _final_probe_contract_expected = _probe_float_or_none(
        _final_probe_contract.get("expected_util")
        or guidance_probe.get("expected_util")
        or guidance_probe.get("candidate_post_util")
        or dict(guidance_probe.get("candidate_search_evidence") or {}).get("best_safe_final_util")
        or dict(guidance_probe.get("candidate_search_evidence") or {}).get("selected_candidate_util")
    )
    _final_probe_exact = _merge_family_evidence_maps(
        guidance_probe.get("exact_blockers_by_family"),
        guidance_probe.get("post_click_exact_blockers_by_family"),
        dg_bundle_safe.get("exact_blockers_by_family"),
        dg_bundle_safe.get("post_click_exact_blockers_by_family"),
        dict(guidance_probe.get("candidate_search_evidence") or {}).get("exact_blockers_by_family"),
    )
    _final_probe_exact = _complete_probe_exact_blocker_map(_final_probe_exact)
    _publishable_cleanup_updates_from_evidence = None
    _final_probe_publishable_cleanup_updates = (
        _publishable_cleanup_updates_from_evidence(
            dict(guidance_probe.get("candidate_search_evidence") or dg_bundle_safe.get("candidate_search_evidence") or {}),
            dict(st.session_state),
        )
        if callable(_publishable_cleanup_updates_from_evidence)
        else {}
    )
    _final_probe_low_families = [
        _family
        for _family in ("bending", "shear")
        if (
            _probe_float_or_none(_final_visible_probe_utils.get(_family)) is not None
            and float(_probe_float_or_none(_final_visible_probe_utils.get(_family)))
            < float(inputs_page_app_contracts.FINAL_ACCEPTED_MIN_FAMILY_UTIL) - float(inputs_page_app_contracts.TARGET_BAND_EPS)
        )
    ]
    if (
        "bending" in _final_probe_low_families
        and "bending" not in _final_probe_exact
        and _final_probe_contract_family == "shear"
        and not bool(_final_probe_contract.get("actionable") or _final_probe_contract.get("enabled"))
    ):
        _bending_publication_debug = {}
        _bending_publication_audit = {
            "post_click_family_utils": dict(_final_visible_probe_utils),
            "post_click_families_below_final_threshold": list(_final_probe_low_families),
            "post_click_unresolved_low_util_families": [
                family for family in _final_probe_low_families if family not in _final_probe_exact
            ],
            "post_click_exact_blockers_by_family": dict(_final_probe_exact),
            "post_click_cleanup_evidence_by_family": _merge_family_evidence_maps(
                guidance_probe.get("cleanup_evidence_by_family"),
                guidance_probe.get("post_click_cleanup_evidence_by_family"),
                dg_bundle_safe.get("cleanup_evidence_by_family"),
                dg_bundle_safe.get("post_click_cleanup_evidence_by_family"),
                _final_probe_exact,
            ),
            "final_accepted_min_family_util": float(inputs_page_app_contracts.FINAL_ACCEPTED_MIN_FAMILY_UTIL),
        }
        try:
            _post_click_low_bending_resolution_item = None
            if callable(_post_click_low_bending_resolution_item):
                _bending_publication_item = _post_click_low_bending_resolution_item(
                    dict(summary_state_probe or {}),
                    dict(summary_overview_probe or {}),
                    resolve_design_mode_config(
                        str(
                            summary_state_probe.get("design_optimisation_goal")
                            or st.session_state.get("design_optimisation_goal")
                            or "balanced"
                        ),
                        mode_config_by_goal=AUTO_DESIGN_MODE_CONFIG,
                        default_goal="balanced",
                    ),
                    _bending_publication_audit,
                    debug_sink=_bending_publication_debug,
                )
        except Exception:
            _bending_publication_item = None
        if isinstance(_bending_publication_item, dict):
            _bending_publication_exact = _merge_family_evidence_maps(
                _bending_publication_item.get("exact_blockers_by_family"),
                _bending_publication_item.get("post_click_exact_blockers_by_family"),
                dict(_bending_publication_item.get("candidate_search_evidence") or {}).get(
                    "exact_blockers_by_family"
                ),
                dict(_bending_publication_item.get("candidate_search_evidence") or {}).get(
                    "post_click_exact_blockers_by_family"
                ),
                _bending_publication_debug.get("exact_blockers_by_family"),
                _bending_publication_debug.get("post_click_exact_blockers_by_family"),
                dict(_bending_publication_debug.get("candidate_search_evidence") or {}).get(
                    "exact_blockers_by_family"
                ),
                dict(_bending_publication_debug.get("candidate_search_evidence") or {}).get(
                    "post_click_exact_blockers_by_family"
                ),
            )
            if "bending" in _bending_publication_exact:
                _final_probe_exact = _merge_family_evidence_maps(
                    _final_probe_exact,
                    _bending_publication_exact,
                )
                _final_probe_exact = _complete_probe_exact_blocker_map(_final_probe_exact)
                _final_probe_cleanup = _merge_family_evidence_maps(
                    guidance_probe.get("cleanup_evidence_by_family"),
                    guidance_probe.get("post_click_cleanup_evidence_by_family"),
                    dg_bundle_safe.get("cleanup_evidence_by_family"),
                    dg_bundle_safe.get("post_click_cleanup_evidence_by_family"),
                    _final_probe_exact,
                )
                _final_probe_evidence = dict(
                    guidance_probe.get("candidate_search_evidence")
                    or dg_bundle_safe.get("candidate_search_evidence")
                    or {}
                )
                _final_probe_evidence["exact_blockers_by_family"] = dict(_final_probe_exact)
                _final_probe_evidence["post_click_exact_blockers_by_family"] = dict(_final_probe_exact)
                _final_probe_evidence["cleanup_evidence_by_family"] = dict(_final_probe_cleanup)
                _final_probe_evidence["post_click_cleanup_evidence_by_family"] = dict(_final_probe_cleanup)
                _final_probe_evidence["active_fail_secondary_low_util_publication"] = True
                for _target in (guidance_probe, dg_bundle_safe):
                    _target["exact_blockers_by_family"] = dict(_final_probe_exact)
                    _target["post_click_exact_blockers_by_family"] = dict(_final_probe_exact)
                    _target["cleanup_evidence_by_family"] = dict(_final_probe_cleanup)
                    _target["post_click_cleanup_evidence_by_family"] = dict(_final_probe_cleanup)
                    _target["candidate_search_evidence"] = dict(_final_probe_evidence)
    if (
        _final_probe_exact
        and _final_probe_contract_family in _final_probe_low_families
        and _final_probe_contract_family not in _final_probe_exact
        and bool(_final_probe_contract.get("actionable") or _final_probe_contract.get("enabled"))
        and _final_probe_contract_expected is not None
        and float(_final_probe_contract_expected)
        < float(inputs_page_app_contracts.FINAL_ACCEPTED_MIN_FAMILY_UTIL) - float(inputs_page_app_contracts.TARGET_BAND_EPS)
    ):
        _final_probe_evidence = dict(guidance_probe.get("candidate_search_evidence") or {})
        _final_probe_updates = dict(
            _final_probe_contract.get("updates")
            or guidance_probe.get("primary_updates")
            or guidance_probe.get("selected_action_updates")
            or {}
        )
        _exact_cleanup_blocker_for_outside_target_action = None
        _final_generated_blocker = (
            _exact_cleanup_blocker_for_outside_target_action(
                family=_final_probe_contract_family,
                current_util=_final_visible_probe_utils.get(_final_probe_contract_family),
                final_util=float(_final_probe_contract_expected),
                selected_updates=_final_probe_updates,
                target_low=float(inputs_page_app_contracts.FINAL_ACCEPTED_MIN_FAMILY_UTIL),
                target_high=float(inputs_page_app_contracts.EFFICIENCY_TARGET_UTIL_MAX),
                blocker=_final_probe_evidence,
                fallback_candidate_id=(
                    _final_probe_contract.get("source_candidate_id")
                    or _final_probe_contract.get("candidate_id")
                    or f"{_final_probe_contract_family}_hidden_cleanup_below_final_threshold"
                ),
                source="browser_state_hidden_cleanup_below_final_threshold",
            )
            if callable(_exact_cleanup_blocker_for_outside_target_action)
            else {}
        )
        if _final_generated_blocker:
            _final_probe_exact[_final_probe_contract_family] = dict(_final_generated_blocker)
            _final_probe_exact = _restamp_probe_exact_blocker_current_utils(
                _final_probe_exact,
                _final_visible_probe_utils,
            )
            _final_probe_exact = _complete_probe_exact_blocker_map(_final_probe_exact)
            _final_probe_cleanup = _merge_family_evidence_maps(
                guidance_probe.get("cleanup_evidence_by_family"),
                guidance_probe.get("post_click_cleanup_evidence_by_family"),
                dg_bundle_safe.get("cleanup_evidence_by_family"),
                dg_bundle_safe.get("post_click_cleanup_evidence_by_family"),
                _final_probe_exact,
            )
            _final_probe_evidence["exact_blockers_by_family"] = dict(_final_probe_exact)
            _final_probe_evidence["post_click_exact_blockers_by_family"] = dict(_final_probe_exact)
            _final_probe_evidence["cleanup_evidence_by_family"] = dict(_final_probe_cleanup)
            _final_probe_evidence["post_click_cleanup_evidence_by_family"] = dict(_final_probe_cleanup)
            for _target in (guidance_probe, dg_bundle_safe):
                _target["exact_blockers_by_family"] = dict(_final_probe_exact)
                _target["post_click_exact_blockers_by_family"] = dict(_final_probe_exact)
                _target["cleanup_evidence_by_family"] = dict(_final_probe_cleanup)
                _target["post_click_cleanup_evidence_by_family"] = dict(_final_probe_cleanup)
                _target["candidate_search_evidence"] = dict(_final_probe_evidence)
            _final_block_reason = str(
                _final_generated_blocker.get("reason")
                or _final_generated_blocker.get("why_reduction_would_hurt_other_design_elements")
                or "hidden_cleanup_below_final_threshold"
            )
            if _final_probe_publishable_cleanup_updates:
                _final_action_contract = dict(_final_probe_contract)
                _final_action_updates = dict(
                    _final_action_contract.get("updates")
                    or _final_probe_publishable_cleanup_updates
                    or {}
                )
                if _final_action_updates:
                    _final_action_contract.update(
                        {
                            "actionable": True,
                            "enabled": True,
                            "action_type": "apply_resolved_candidate",
                            "updates": dict(_final_action_updates),
                            "preview_pass": bool(_final_action_contract.get("preview_pass", True)),
                            "blocking_reason": None,
                        }
                    )
                    for _target in (guidance_probe, dg_bundle_safe):
                        _target["primary_button_contract"] = dict(_final_action_contract)
                        _target["button_contract"] = dict(_final_action_contract)
                        _target["displayed_primary_button_contract"] = dict(_final_action_contract)
                        _target["button_contract_enabled"] = True
                        _target["button_contract_updates"] = dict(_final_action_updates)
                        _target["button_contract_preview_pass"] = bool(
                            _final_action_contract.get("preview_pass")
                        )
                        _target["button_contract_candidate_id"] = (
                            _final_action_contract.get("source_candidate_id")
                            or _final_action_contract.get("candidate_id")
                        )
                        _target["selected_action_updates"] = dict(_final_action_updates)
                        _target["primary_updates"] = dict(_final_action_updates)
                        _target["primary_action_type"] = "apply_resolved_candidate"
                        _target["selected_action_type"] = "apply_resolved_candidate"
                _final_probe_contract = dict(_final_action_contract)
                _final_probe_contract_family = str(
                    _final_probe_contract.get("family")
                    or _final_probe_contract_family
                    or ""
                ).strip().lower()
            if not _final_probe_publishable_cleanup_updates:
                _final_disabled_contract = {
                    **dict(_final_probe_contract),
                    "actionable": False,
                    "enabled": False,
                    "action_type": None,
                    "updates": {},
                    "preview_pass": False,
                    "expected_util": None,
                    "blocking_reason": _final_block_reason,
                    "source_candidate_id": None,
                    "candidate_id": None,
                }
                _final_blocker_title = (
                    "Shear cleanup blocked by final efficiency threshold"
                    if "shear" in _final_probe_exact
                    else "Cleanup blocked by exact engineering limit"
                )
                for _target in (guidance_probe, dg_bundle_safe):
                    _target["exact_blockers_by_family"] = dict(_final_probe_exact)
                    _target["post_click_exact_blockers_by_family"] = dict(_final_probe_exact)
                    _target["cleanup_evidence_by_family"] = dict(_final_probe_cleanup)
                    _target["post_click_cleanup_evidence_by_family"] = dict(_final_probe_cleanup)
                    _target["candidate_search_evidence"] = dict(_final_probe_evidence)
                    _target["primary_button_contract"] = dict(_final_disabled_contract)
                    _target["button_contract"] = dict(_final_disabled_contract)
                    _target["displayed_primary_button_contract"] = dict(_final_disabled_contract)
                    _target["button_contract_enabled"] = False
                    _target["button_contract_updates"] = {}
                    _target["button_contract_preview_pass"] = False
                    _target["button_contract_candidate_id"] = None
                    _target["selected_candidate_id"] = None
                    _target["visible_primary_candidate_id"] = None
                    _target["selected_action_updates"] = {}
                    _target["primary_updates"] = {}
                    _target["primary_action_type"] = None
                    _target["selected_action_type"] = None
                    _target["design_guide_primary_apply_payload"] = {}
                    _target["primary_title"] = _final_blocker_title
                    _target["selected_title"] = _final_blocker_title
                    _target["primary_card_title"] = _final_blocker_title
                    _target["final_primary_title"] = _final_blocker_title
                    _target["primary_guidance_intent"] = "specific_blocker"
                    _target["primary_card_intent"] = "specific_blocker"
                    _target["primary_status"] = "BLOCKED"
                    _target["terminal_state_blocked_by_local_cleanup"] = True
                    _target["terminal_state_reason"] = _final_block_reason
    dg_primary_card_title_probe = dg_bundle_safe.get("primary_card_title")
    dg_eff = dict(dg_bundle_safe.get("efficiency_tightening_state") or {})
    dg_ov = dict(dg_bundle_safe.get("overview") or {})

    def _first_nested_design_guide_publication_value(source, *keys, depth=0):
        if depth > 6:
            return None
        if isinstance(source, dict):
            for key in keys:
                value = source.get(key)
                if value not in (None, "", [], {}):
                    return value
            for nested in source.values():
                value = _first_nested_design_guide_publication_value(nested, *keys, depth=depth + 1)
                if value not in (None, "", [], {}):
                    return value
        elif isinstance(source, list):
            for nested in source[:12]:
                value = _first_nested_design_guide_publication_value(nested, *keys, depth=depth + 1)
                if value not in (None, "", [], {}):
                    return value
        return None

    _dg_authoritative_publication = dict(
        dg_bundle_safe.get("authoritative_final_design_guide_publication") or {}
    )
    _dg_authoritative_verifier_payload = dict(
        dg_bundle_safe.get("authoritative_final_publication_verifier_payload") or {}
    )
    _dg_authoritative_probe_source = bool(
        _dg_authoritative_publication.get("publication_hash")
        or _dg_authoritative_verifier_payload.get("payload_hash")
    )
    dg_final_publication_payload = dict(
        _dg_authoritative_verifier_payload
        or dg_bundle_safe.get("final_publication_verifier_payload")
        or {}
    )
    if _dg_authoritative_probe_source:
        dg_final_publication_payload["source"] = "authoritative_design_result_browser_probe_projection"
    _dg_existing_publication_family = str(
        dg_final_publication_payload.get("selected_family_id")
        or dg_final_publication_payload.get("selected_family")
        or dg_final_publication_payload.get("published_family_id")
        or ""
    ).strip().lower()
    _dg_existing_button_family = str(
        dict(
            dg_bundle_safe.get("primary_button_contract")
            or dg_bundle_safe.get("button_contract")
            or st.session_state.get("design_guide_primary_button_contract")
            or {}
        ).get("family")
        or ""
    ).strip().lower()
    _dg_authoritative_result_for_publication = InputsSessionServices.from_mapping(st.session_state).engineering_results.current()
    _dg_primary_apply_payload_for_publication = (
        dict(_dg_authoritative_result_for_publication.apply_payload or {})
        if _dg_authoritative_result_for_publication is not None
        else {}
    )
    _dg_primary_binding_audit_for_publication = dict(
        st.session_state.get(inputs_page_app_contracts.DESIGN_GUIDE_PRIMARY_PAYLOAD_BINDING_AUDIT_KEY) or {}
    )
    _dg_apply_payload_updates_for_publication = dict(
        _dg_primary_apply_payload_for_publication.get("updates")
        or _dg_primary_apply_payload_for_publication.get("button_contract_updates")
        or {}
    )
    _dg_apply_payload_binding_usable = bool(
        _dg_apply_payload_updates_for_publication
        and _dg_primary_apply_payload_for_publication.get("action_type")
        and _dg_primary_binding_audit_for_publication.get("payload_binding_match") is not False
        and _dg_primary_binding_audit_for_publication.get("payload_update_match") is not False
    )
    _dg_apply_payload_contract_for_publication = {}
    if _dg_apply_payload_binding_usable:
        _dg_apply_payload_family_for_publication = str(
            _dg_primary_apply_payload_for_publication.get("selected_family_id")
            or _dg_primary_apply_payload_for_publication.get("published_family_id")
            or _dg_primary_apply_payload_for_publication.get("cta_family_id")
            or _dg_primary_apply_payload_for_publication.get("apply_payload_family_id")
            or _dg_primary_apply_payload_for_publication.get("family")
            or ""
        ).strip()
        _dg_apply_payload_contract_for_publication = {
            "enabled": True,
            "actionable": True,
            "action_type": _dg_primary_apply_payload_for_publication.get("action_type"),
            "updates": dict(_dg_apply_payload_updates_for_publication),
            "candidate_id": _dg_primary_apply_payload_for_publication.get("candidate_id"),
            "source_candidate_id": _dg_primary_apply_payload_for_publication.get("source_candidate_id")
            or _dg_primary_apply_payload_for_publication.get("candidate_id"),
            "family": _dg_apply_payload_family_for_publication,
            "selected_family_id": _dg_apply_payload_family_for_publication,
            "published_family_id": _dg_apply_payload_family_for_publication,
            "cta_family_id": _dg_apply_payload_family_for_publication,
            "apply_payload_family_id": _dg_apply_payload_family_for_publication,
            "preview_pass": _dg_primary_apply_payload_for_publication.get("preview_pass"),
            "expected_util": _dg_primary_apply_payload_for_publication.get("expected_util"),
            "label": _dg_primary_apply_payload_for_publication.get("label"),
            "source": "browser_state_primary_apply_payload_reprojection",
        }
    _dg_session_button_contract = dict(
        st.session_state.get("design_guide_primary_button_contract")
        or _dg_apply_payload_contract_for_publication
        or {}
    )
    _dg_session_button_enabled = bool(
        st.session_state.get("design_guide_primary_button_contract_enabled")
        or _dg_session_button_contract.get("enabled")
        or _dg_session_button_contract.get("actionable")
    )
    _dg_session_button_updates = dict(_dg_session_button_contract.get("updates") or {})
    _dg_session_button_family = str(
        _dg_session_button_contract.get("selected_family_id")
        or _dg_session_button_contract.get("published_family_id")
        or _dg_session_button_contract.get("cta_family_id")
        or _dg_session_button_contract.get("apply_payload_family_id")
        or _dg_session_button_contract.get("family")
        or ""
    ).strip()
    _dg_publication_cta_for_reprojection = dict(dg_final_publication_payload.get("cta") or {})
    _dg_publication_cta_family = str(
        _dg_publication_cta_for_reprojection.get("selected_family_id")
        or _dg_publication_cta_for_reprojection.get("published_family_id")
        or _dg_publication_cta_for_reprojection.get("cta_family_id")
        or _dg_publication_cta_for_reprojection.get("family_id")
        or _dg_publication_cta_for_reprojection.get("family")
        or ""
    ).strip()
    _dg_publication_cta_enabled = bool(
        _dg_publication_cta_for_reprojection.get("enabled")
        or _dg_publication_cta_for_reprojection.get("actionable")
        or (
            _dg_publication_cta_for_reprojection.get("action_type")
            and dict(_dg_publication_cta_for_reprojection.get("updates") or {})
        )
    )
    _dg_publication_exact_stop_proof = dict(
        dg_bundle_safe.get("exact_stop_proof")
        or dg_final_publication_payload.get("exact_stop_proof")
        or guidance_probe.get("exact_stop_proof")
        or _first_nested_design_guide_publication_value(
            dg_bundle_safe,
            "exact_stop_proof",
        )
        or _first_nested_design_guide_publication_value(
            guidance_probe,
            "exact_stop_proof",
        )
        or {}
    )
    _dg_publication_exact_shear_stop = dict(_dg_publication_exact_stop_proof.get("shear") or {})
    _dg_publication_exact_bending_stop = dict(_dg_publication_exact_stop_proof.get("bending") or {})
    _dg_publication_update_keys = set(_dg_session_button_updates)
    _dg_publication_has_bending_repair = bool(
        _dg_publication_update_keys
        & {
            "D",
            "b",
            "bot1_count",
            "bot2_count",
            "bot_row_1_bars",
            "bot_row_2_bars",
            "bot_row_1_dia",
            "bot_row_2_dia",
            "db_bot_1",
            "db_bot_2",
        }
    )
    _dg_publication_has_shear_repair = bool(
        _dg_publication_update_keys & {"lig_d", "lig_legs", "s_lig"}
    )
    _dg_publication_mixed_family_reprojection_required = bool(
        (
            _dg_existing_publication_family in {"bending", "bending_fail_governs"}
            and _dg_publication_exact_shear_stop
            and _dg_publication_has_bending_repair
        )
        or (
            _dg_existing_publication_family in {"shear", "shear_fail_governs"}
            and _dg_publication_exact_bending_stop
            and _dg_publication_has_shear_repair
        )
    )
    _dg_publication_has_late_exact_evidence = bool(
        dg_bundle_safe.get("exact_blockers_by_family")
        or dg_bundle_safe.get("post_click_exact_blockers_by_family")
        or _dg_publication_exact_stop_proof
    )
    _dg_publication_display_exact_sections = dict(
        (dict(dg_final_publication_payload.get("display") or {}).get("expanded_evidence_sections") or {})
    )
    _dg_publication_evidence_candidate_search = dict(
        dict(dg_final_publication_payload.get("evidence") or {}).get("candidate_search_evidence") or {}
    )
    _dg_publication_missing_exact_sections = not bool(
        _dg_publication_display_exact_sections.get("exact_blockers_by_family")
        or _dg_publication_evidence_candidate_search.get("exact_blockers_by_family")
        or _dg_publication_evidence_candidate_search.get("post_click_exact_blockers_by_family")
    )
    _dg_publication_failed_preview_block = bool(
        str(dg_final_publication_payload.get("outcome_state") or dg_final_publication_payload.get("status") or "").strip().upper()
        == "BLOCKED"
        and (
            _dg_publication_cta_for_reprojection.get("disabled_reason") == "candidate_preview_has_fail_status"
            or _dg_publication_cta_for_reprojection.get("blocking_reason") == "candidate_preview_has_fail_status"
        )
    )
    _dg_final_publication_needs_reprojection = bool(
        not dg_final_publication_payload
        or (
            _dg_publication_failed_preview_block
            and _dg_publication_has_late_exact_evidence
            and _dg_publication_missing_exact_sections
        )
        or (
            _dg_publication_has_late_exact_evidence
            and _dg_existing_publication_family in {"", "general"}
            and _dg_existing_button_family not in {"", "general"}
        )
        or (
            _dg_existing_publication_family in {"", "general"}
            and _dg_existing_button_family in {"bending", "shear"}
        )
        or (
            _dg_session_button_enabled
            and _dg_session_button_updates
            and not _dg_publication_cta_enabled
        )
        or _dg_publication_mixed_family_reprojection_required
        or (
            _dg_session_button_enabled
            and _dg_session_button_updates
            and _dg_session_button_family
            and (
                (
                    _dg_existing_publication_family
                    and _dg_existing_publication_family != _dg_session_button_family.lower()
                )
                or (
                    _dg_publication_cta_family
                    and _dg_publication_cta_family.upper() != _dg_session_button_family.upper()
                )
            )
        )
    )
    if _dg_authoritative_probe_source:
        _dg_final_publication_needs_reprojection = False
    if _dg_final_publication_needs_reprojection:
        try:
            _probe_contract_for_publication = dict(
                _dg_session_button_contract
                or guidance_probe.get("primary_button_contract")
                or guidance_probe.get("button_contract")
                or {}
            )
            _probe_evidence_for_publication = dict(guidance_probe.get("candidate_search_evidence") or {})
            _probe_family_for_publication = str(
                _probe_contract_for_publication.get("family")
                or _probe_evidence_for_publication.get("selected_family_id")
                or _probe_evidence_for_publication.get("family_id")
                or _probe_evidence_for_publication.get("cta_family_id")
                or guidance_probe.get("selected_family_id")
                or ""
            ).strip()
            _probe_updates_for_publication = dict(
                _probe_contract_for_publication.get("updates")
                or guidance_probe.get("primary_updates")
                or _probe_evidence_for_publication.get("selected_candidate_updates")
                or {}
            )
            _probe_action_type_for_publication = str(
                _probe_contract_for_publication.get("action_type")
                or guidance_probe.get("primary_action_type")
                or guidance_probe.get("selected_action_type")
                or ""
            ).strip()
            _probe_action_payload_for_publication = {
                "action_type": _probe_action_type_for_publication,
                "resolved_candidate_action_type": _probe_action_type_for_publication,
                "updates": dict(_probe_updates_for_publication),
                "resolved_candidate_updates": dict(_probe_updates_for_publication),
                "candidate_search_evidence": dict(_probe_evidence_for_publication),
                "source_candidate_id": (
                    _probe_contract_for_publication.get("source_candidate_id")
                    or _probe_contract_for_publication.get("candidate_id")
                    or _probe_evidence_for_publication.get("selected_candidate_id")
                ),
                "candidate_id": (
                    _probe_contract_for_publication.get("candidate_id")
                    or _probe_contract_for_publication.get("source_candidate_id")
                    or _probe_evidence_for_publication.get("selected_candidate_id")
                ),
                "family": _probe_family_for_publication,
                "family_id": _probe_family_for_publication,
                "selected_family_id": _probe_family_for_publication,
                "published_family_id": _probe_family_for_publication,
                "cta_family_id": _probe_family_for_publication,
                "apply_payload_family_id": _probe_family_for_publication,
            }
            _probe_item_for_publication = {
                "title_main": guidance_probe.get("primary_title") or guidance_probe.get("selected_title"),
                "title": guidance_probe.get("primary_title") or guidance_probe.get("selected_title"),
                "status": guidance_probe.get("primary_status") or guidance_probe.get("displayed_status"),
                "util": guidance_probe.get("displayed_util"),
                "action_type": _probe_action_type_for_publication,
                "button_contract": dict(_probe_contract_for_publication),
                "action_payload": dict(_probe_action_payload_for_publication),
                "candidate_search_evidence": dict(_probe_evidence_for_publication),
                "display_truth": dict(guidance_probe.get("display_truth") or guidance_probe.get("primary_display_truth") or {}),
                "exact_blockers_by_family": dict(guidance_probe.get("exact_blockers_by_family") or {}),
                "exact_stop_proof": dict(_dg_publication_exact_stop_proof),
                "post_click_exact_blockers_by_family": dict(
                    guidance_probe.get("post_click_exact_blockers_by_family") or {}
                ),
                "family": _probe_family_for_publication,
                "family_id": _probe_family_for_publication,
                "selected_family_id": _probe_family_for_publication,
                "published_family_id": _probe_family_for_publication,
                "cta_family_id": _probe_family_for_publication,
                "apply_payload_family_id": _probe_family_for_publication,
            }
            _probe_publication = build_browser_publication_probe(
                item=dict(_probe_item_for_publication),
                debug=dict(guidance_probe or {}),
                publication_reason="browser_state_guidance_probe_projection",
                current_publication=_dg_authoritative_publication,
            )
            _probe_publication_dict = (
                _probe_publication.to_dict()
                if hasattr(_probe_publication, "to_dict")
                else dict(_probe_publication or {})
            )
            _probe_publication_cta = dict(
                _probe_publication_dict.get("cta")
                or {}
            )
            if _dg_session_button_enabled and _dg_session_button_updates:
                _probe_publication_cta.update(
                    {
                        "enabled": True,
                        "actionable": True,
                        "action_type": _probe_action_type_for_publication,
                        "updates": dict(_dg_session_button_updates),
                        "family": _probe_family_for_publication,
                        "family_id": _probe_family_for_publication,
                        "selected_family_id": _probe_family_for_publication,
                        "published_family_id": _probe_family_for_publication,
                        "cta_family_id": _probe_family_for_publication,
                        "apply_payload_family_id": _probe_family_for_publication,
                        "source_candidate_id": (
                            _probe_contract_for_publication.get("source_candidate_id")
                            or _probe_contract_for_publication.get("candidate_id")
                            or _probe_evidence_for_publication.get("selected_candidate_id")
                        ),
                        "candidate_id": (
                            _probe_contract_for_publication.get("candidate_id")
                            or _probe_contract_for_publication.get("source_candidate_id")
                            or _probe_evidence_for_publication.get("selected_candidate_id")
                        ),
                        "disabled_reason": None,
                        "blocking_reason": None,
                        "source": "browser_state_rendered_primary_button_contract",
                    }
                )
            _probe_publication_display = dict(_probe_publication_dict.get("display") or {})
            _probe_publication_evidence = dict(_probe_publication_dict.get("evidence") or {})
            _probe_selected_family_for_publication = str(
                _probe_publication_dict.get("selected_family")
                or _probe_family_for_publication
                or ""
            ).strip()
            if _probe_selected_family_for_publication:
                _probe_publication_cta.update(
                    {
                        "family": _probe_selected_family_for_publication,
                        "family_id": _probe_selected_family_for_publication,
                        "selected_family_id": _probe_selected_family_for_publication,
                        "published_family_id": _probe_selected_family_for_publication,
                        "cta_family_id": _probe_selected_family_for_publication,
                        "apply_payload_family_id": _probe_selected_family_for_publication,
                    }
                )
                _apply_summary = dict(_probe_publication_cta.get("apply_payload_summary") or {})
                if _apply_summary:
                    _apply_summary.update(
                        {
                            "family": _probe_selected_family_for_publication,
                            "family_id": _probe_selected_family_for_publication,
                            "selected_family_id": _probe_selected_family_for_publication,
                            "published_family_id": _probe_selected_family_for_publication,
                            "cta_family_id": _probe_selected_family_for_publication,
                            "apply_payload_family_id": _probe_selected_family_for_publication,
                        }
                    )
                    _probe_publication_cta["apply_payload_summary"] = dict(_apply_summary)
                _handoff = dict(_probe_publication_cta.get("one_click_action_handoff") or {})
                if _handoff:
                    _handoff.update(
                        {
                            "family": _probe_selected_family_for_publication,
                            "family_id": _probe_selected_family_for_publication,
                        }
                    )
                    _probe_publication_cta["one_click_action_handoff"] = dict(_handoff)
                _probe_contract_for_publication.update(
                    {
                        "family": _probe_selected_family_for_publication,
                        "family_id": _probe_selected_family_for_publication,
                        "selected_family_id": _probe_selected_family_for_publication,
                        "published_family_id": _probe_selected_family_for_publication,
                        "cta_family_id": _probe_selected_family_for_publication,
                        "apply_payload_family_id": _probe_selected_family_for_publication,
                    }
                )
                _dg_session_button_contract = dict(_probe_contract_for_publication)
                for _contract_target in (guidance_probe, dg_bundle_safe):
                    if isinstance(_contract_target, dict):
                        for _contract_key in (
                            "displayed_primary_button_contract",
                            "button_contract",
                            "primary_button_contract",
                        ):
                            _contract_target[_contract_key] = dict(_probe_contract_for_publication)
            dg_final_publication_payload = {
                "publication_hash": _probe_publication_dict.get("publication_hash"),
                "final_publication_authority_hash": _probe_publication_dict.get("publication_hash"),
                "final_publication_cta_hash": stable_final_publication_hash(
                    _probe_publication_cta
                ),
                "final_publication_display_hash": (
                    _probe_publication_display.get("final_card_model_hash")
                    or _probe_publication_display.get("visible_wording_hash")
                ),
                "selected_family_id": _probe_selected_family_for_publication,
                "selected_family": _probe_selected_family_for_publication,
                "published_family_id": _probe_selected_family_for_publication,
                "cta_family_id": _probe_selected_family_for_publication,
                "outcome_state": _probe_publication_dict.get("outcome_state"),
                "status": _probe_publication_display.get("status")
                or _probe_publication_dict.get("outcome_state"),
                "title": _probe_publication_display.get("title")
                or _probe_item_for_publication.get("title_main"),
                "cta": dict(_probe_publication_cta),
                "display": dict(_probe_publication_display),
                "evidence": dict(_probe_publication_evidence),
                "exact_stop_proof": dict(_probe_publication_dict.get("exact_stop_proof") or {}),
                "target_band_proof": dict(_probe_publication_dict.get("target_band_proof") or {}),
                "source": "browser_state_guidance_probe_projection",
                "proof_only": True,
            }
            dg_bundle_safe["final_design_guide_publication"] = dict(_probe_publication_dict)
            dg_bundle_safe["selected_family_id"] = dg_final_publication_payload.get("selected_family_id")
            dg_bundle_safe["published_family_id"] = dg_final_publication_payload.get("published_family_id")
            dg_bundle_safe["cta_family_id"] = dg_final_publication_payload.get("cta_family_id")
            dg_bundle_safe["publication_hash"] = dg_final_publication_payload.get("publication_hash")
            dg_bundle_safe["final_publication_publication_hash"] = dg_final_publication_payload.get(
                "publication_hash"
            )
            dg_bundle_safe["final_publication_authority_hash"] = dg_final_publication_payload.get(
                "final_publication_authority_hash"
            )
            dg_bundle_safe["final_publication_cta_hash"] = dg_final_publication_payload.get(
                "final_publication_cta_hash"
            )
            dg_bundle_safe["final_publication_display_hash"] = dg_final_publication_payload.get(
                "final_publication_display_hash"
            )
        except Exception as exc:
            dg_bundle_safe["final_publication_verifier_payload_error"] = f"{type(exc).__name__}: {exc}"
    dg_nested_publication_hash = _first_nested_design_guide_publication_value(
        dg_bundle_safe,
        "publication_hash",
        "final_publication_publication_hash",
        "final_publication_authority_hash",
    )
    dg_nested_cta_hash = _first_nested_design_guide_publication_value(
        dg_bundle_safe,
        "final_publication_cta_hash",
        "cta_authority_hash",
        "cta_hash",
    )
    dg_nested_display_hash = _first_nested_design_guide_publication_value(
        dg_bundle_safe,
        "final_publication_display_hash",
        "display_authority_hash",
        "display_hash",
    )
    dg_probe_publication_hashes = {
        "publication_hash": (
            dg_final_publication_payload.get("publication_hash")
            or dg_bundle_safe.get("publication_hash")
            or dg_bundle_safe.get("final_publication_publication_hash")
            or dg_nested_publication_hash
        ),
        "authority_hash": (
            dg_final_publication_payload.get("final_publication_authority_hash")
            or dg_bundle_safe.get("final_publication_authority_hash")
            or dg_nested_publication_hash
        ),
        "cta_hash": (
            dg_final_publication_payload.get("final_publication_cta_hash")
            or dg_final_publication_payload.get("cta_authority_hash")
            or dg_final_publication_payload.get("cta_hash")
            or dg_bundle_safe.get("final_publication_cta_hash")
            or dg_nested_cta_hash
        ),
        "display_hash": (
            dg_final_publication_payload.get("final_publication_display_hash")
            or dg_final_publication_payload.get("display_authority_hash")
            or dg_final_publication_payload.get("display_hash")
            or dg_bundle_safe.get("final_publication_display_hash")
            or dg_nested_display_hash
        ),
    }
    dg_selected_family_probe = (
        dg_final_publication_payload.get("selected_family_id")
        or dg_final_publication_payload.get("selected_family")
        or dg_bundle_safe.get("selected_family_id")
        or dg_bundle_safe.get("published_family_id")
        or dg_bundle_safe.get("cta_family_id")
        or dg_bundle_safe.get("family")
    )
    target_band_probe = target_band_payload(str(st.session_state.get("design_optimisation_goal") or "balanced"))
    _active_strength_failures_for_probe = {
        str(key or "").strip().lower()
        for key, value in dict(summary_overview_probe.get("statuses") or {}).items()
        if str(key or "").strip().lower() in {"bending", "shear"}
        and str(value or "").strip().upper() == "FAIL"
    }
    # Overdesign and serviceability probes have no active strength-failure
    # branch. Keep the selected family available for the final browser-state
    # payload instead of reading the failure-only local below.
    _probe_blocker_family_id = str(
        dg_selected_family_probe
        or dg_final_publication_payload.get("selected_family_id")
        or dg_bundle_safe.get("selected_family_id")
        or ""
    ).strip()
    if len(_active_strength_failures_for_probe) == 1:
        _probe_active_family = next(iter(_active_strength_failures_for_probe))
        _probe_blocker_family_id = (
            "BENDING_FAIL_GOVERNS" if _probe_active_family == "bending" else "SHEAR_FAIL_GOVERNS"
        )
        _probe_contract = dict(
            guidance_probe.get("primary_button_contract")
            or guidance_probe.get("button_contract")
            or dg_bundle_safe.get("primary_button_contract")
            or dg_bundle_safe.get("button_contract")
            or {}
        )
        _probe_reason = str(
            _probe_contract.get("blocking_reason")
            or _probe_contract.get("disabled_reason")
            or ""
        ).strip()
        if (
            _probe_contract.get("preview_pass") is False
            and _probe_reason == "candidate_preview_has_fail_status"
        ):
            _probe_family_identity = {
                "family": _probe_blocker_family_id,
                "family_id": _probe_blocker_family_id,
                "selected_family_id": _probe_blocker_family_id,
                "published_family_id": _probe_blocker_family_id,
                "cta_family_id": _probe_blocker_family_id,
                "apply_payload_family_id": _probe_blocker_family_id,
                "candidate_family_id": _probe_blocker_family_id,
                "card_family_id": _probe_blocker_family_id,
            }
            _probe_contract.update(
                {
                    **_probe_family_identity,
                    "enabled": False,
                    "actionable": False,
                    "action_type": None,
                    "updates": {},
                    "expected_util": None,
                    "blocking_reason": f"no_safe_{_probe_active_family}_repair_candidate",
                    "disabled_reason": f"no_safe_{_probe_active_family}_repair_candidate",
                    "source_candidate_id": None,
                    "candidate_id": None,
                }
            )
            for _probe_target in (guidance_probe, dg_bundle_safe):
                if not isinstance(_probe_target, dict):
                    continue
                _probe_target.update(_probe_family_identity)
                _probe_target["primary_button_contract"] = dict(_probe_contract)
                _probe_target["button_contract"] = dict(_probe_contract)
                _probe_target["displayed_primary_button_contract"] = dict(_probe_contract)
                _probe_target["button_contract_enabled"] = False
                _probe_target["button_contract_updates"] = {}
                _probe_target["primary_updates"] = {}
                _probe_target["selected_action_updates"] = {}
                _probe_target["primary_action_type"] = None
                _probe_target["selected_action_type"] = None
            if isinstance(dg_final_publication_payload, dict):
                _probe_publication_cta = dict(dg_final_publication_payload.get("cta") or {})
                _probe_publication_cta.update(
                    {
                        **_probe_family_identity,
                        "enabled": False,
                        "actionable": False,
                        "action_type": None,
                        "updates": {},
                        "disabled_reason": f"no_safe_{_probe_active_family}_repair_candidate",
                        "blocking_reason": f"no_safe_{_probe_active_family}_repair_candidate",
                        "source_candidate_id": None,
                        "candidate_id": None,
                    }
                )
                _probe_apply_summary = dict(_probe_publication_cta.get("apply_payload_summary") or {})
                _probe_apply_summary.update(
                    {
                        **_probe_family_identity,
                        "action_type": None,
                        "updates": {},
                        "source_candidate_id": None,
                        "candidate_id": None,
                    }
                )
                _probe_handoff = dict(_probe_publication_cta.get("one_click_action_handoff") or {})
                _probe_handoff.update(
                    {
                        **_probe_family_identity,
                        "action_type": None,
                        "has_updates": False,
                        "candidate_id": None,
                    }
                )
                _probe_publication_cta["apply_payload_summary"] = dict(_probe_apply_summary)
                _probe_publication_cta["one_click_action_handoff"] = dict(_probe_handoff)
                dg_final_publication_payload["cta"] = dict(_probe_publication_cta)
                dg_final_publication_payload["selected_family_id"] = _probe_blocker_family_id
                dg_final_publication_payload["selected_family"] = _probe_blocker_family_id
                dg_final_publication_payload["published_family_id"] = _probe_blocker_family_id
                dg_final_publication_payload["cta_family_id"] = _probe_blocker_family_id
    dg_selected_family_probe = _probe_blocker_family_id
    _dg_last_apply_route_for_probe = dict(
        st.session_state.get(inputs_page_app_contracts.DESIGN_GUIDE_LAST_APPLY_ROUTE_KEY) or {}
    )
    _dg_authoritative_solver_probe = {}
    if (
        _dg_authoritative_result_for_publication is not None
        and _dg_last_apply_route_for_probe.get("post_apply_resolved_candidate_attempted")
        and _dg_last_apply_route_for_probe.get("applied_updates")
    ):
        _dg_authoritative_solver_probe = {
            "status": "pass"
            if _dg_last_apply_route_for_probe.get("post_apply_required_checks_pass")
            and not _dg_last_apply_route_for_probe.get("post_apply_any_fail")
            else "complete",
            "source": "authoritative_design_result_post_apply_probe",
            "family": (
                dict(
                    _dg_authoritative_result_for_publication.final_publication
                    or {}
                ).get("selected_family")
                or _dg_authoritative_result_for_publication.governing_family
            ),
            "authority_hash": (
                _dg_authoritative_result_for_publication.publication_authority_hash
                or dict(
                    _dg_authoritative_result_for_publication.final_publication
                    or {}
                ).get("publication_hash")
            ),
            "applied_updates": dict(_dg_last_apply_route_for_probe.get("applied_updates") or {}),
        }
    payload = {
        "codex_browser_test_mode": bool(_browser_test_mode_active()),
        "browser_probe_phase": str(probe_phase or "final"),
        "target_band": target_band_probe,
        "final_publication_verifier_payload": dg_final_publication_payload,
        "final_publication_hashes": dg_probe_publication_hashes,
        "selected_family_id": dg_selected_family_probe,
        "primary_button_contract": dict(_dg_session_button_contract or {}),
        "button_contract": dict(_dg_session_button_contract or {}),
        "design_guide_primary_button_contract": dict(_dg_session_button_contract or {}),
        "design_guide_primary_button_contract_enabled": bool(
            st.session_state.get("design_guide_primary_button_contract_enabled")
            or _dg_session_button_contract.get("enabled")
            or _dg_session_button_contract.get("actionable")
        ),
        "browser_recipe": st.session_state.get(_BROWSER_RECIPE_APPLIED_KEY),
        "browser_recipe_kind": st.session_state.get("_browser_recipe_kind"),
        "browser_recipe_error": st.session_state.get("_browser_recipe_error"),
        "browser_recipe_applied_state": st.session_state.get("_browser_recipe_applied_state"),
        "browser_query_param_probe": _browser_query_param_probe(),
        "browser_shared_probe": {
            "active_beam_id": st.session_state.get("active_beam_id"),
            "beam_last_hydrated_id": st.session_state.get("beam_last_hydrated_id"),
            "b": st.session_state.get("b"),
            "D": st.session_state.get("D"),
            "fc": st.session_state.get("fc"),
            "bot1_count": st.session_state.get("bot1_count"),
            "db_bot_1": st.session_state.get("db_bot_1"),
            "bot_row_1_bars": st.session_state.get("bot_row_1_bars"),
            "bot_row_1_dia": st.session_state.get("bot_row_1_dia"),
            "inputs_bot_row_1_bars": st.session_state.get("inputs_bot_row_1_bars"),
            "inputs_bot_row_1_dia": st.session_state.get("inputs_bot_row_1_dia"),
            "inputs_db_bot_1": st.session_state.get("inputs_db_bot_1"),
            "lig_d": st.session_state.get("lig_d"),
            "lig_legs": st.session_state.get("lig_legs"),
            "s_lig": st.session_state.get("s_lig"),
            "actions_mode": st.session_state.get("actions_mode"),
            "actions_source": st.session_state.get("actions_source"),
            "uls_Mstar": st.session_state.get("uls_Mstar"),
            "uls_Mstar_pos_manual": st.session_state.get("uls_Mstar_pos_manual"),
            "uls_Mstar_neg_manual": st.session_state.get("uls_Mstar_neg_manual"),
            "uls_Vstar": st.session_state.get("uls_Vstar"),
            "load_Mstar_proxy": st.session_state.get("load_Mstar_proxy"),
            "load_Mstar_pos_proxy": st.session_state.get("load_Mstar_pos_proxy"),
            "load_Mstar_neg_proxy": st.session_state.get("load_Mstar_neg_proxy"),
            "load_Vstar_proxy": st.session_state.get("load_Vstar_proxy"),
            "inputs_load_Mstar_pos_proxy": st.session_state.get("inputs_load_Mstar_pos_proxy"),
            "inputs_load_Mstar_neg_proxy": st.session_state.get("inputs_load_Mstar_neg_proxy"),
            "inputs_load_Vstar_proxy": st.session_state.get("inputs_load_Vstar_proxy"),
        },
        "browser_debug_probe": {
            "browser_recipe_global_seed_token_count": len(
                _BROWSER_RECIPE_GLOBAL_SEED_TOKENS
            ),
            "post_cleanup_accepted_fingerprint_count": len(
                DESIGN_GUIDE_POST_CLEANUP_ACCEPTED_FPS
            ),
            "post_cleanup_accepted_fingerprint_audit": {
                "add_count": DESIGN_GUIDE_POST_CLEANUP_ACCEPTED_FPS.add_count,
                "clear_count": DESIGN_GUIDE_POST_CLEANUP_ACCEPTED_FPS.clear_count,
                "last_event": dict(
                    DESIGN_GUIDE_POST_CLEANUP_ACCEPTED_FPS.last_event
                ),
                "last_added": dict(
                    DESIGN_GUIDE_POST_CLEANUP_ACCEPTED_FPS.last_added or ()
                ),
                "guidance_resolved_current": dict(
                    build_local_cleanup_acceptance_fingerprint(
                        dict(guidance_probe.get("guidance_resolved_state") or {})
                    )
                ),
            },
            "typed_apply_cutover_enabled": True,
            "debug_changed_shared_inputs": st.session_state.get("_debug_changed_shared_inputs"),
            "debug_reverted_shared_inputs": st.session_state.get("_debug_reverted_shared_inputs"),
            "debug_last_revert_tag": st.session_state.get("_debug_last_revert_tag"),
            "browser_router_probe": st.session_state.get("_browser_router_probe"),
            "authoritative_design_result_runtime_probe": dict(
                st.session_state.get("_authoritative_design_result_runtime_probe") or {}
            ),
            "design_guide_render_compute_probe": dict(
                st.session_state.get("_design_guide_render_compute_probe") or {}
            ),
            "authoritative_apply_command_probe": dict(
                st.session_state.get("_authoritative_apply_command_probe") or {}
            ),
            "typed_inputs_apply_probe": dict(
                st.session_state.get("_typed_inputs_apply_probe") or {}
            ),
            "typed_apply_state_commit_probe": dict(
                st.session_state.get("_typed_apply_state_commit_probe") or {}
            ),
            "typed_post_apply_rehydrate_probe": dict(
                st.session_state.get("_typed_post_apply_rehydrate_probe") or {}
            ),
            "design_guide_fragment_mode": st.session_state.get("_design_guide_fragment_mode"),
            "browser_recipe_last_action": st.session_state.get("_browser_recipe_last_action"),
            "allow_design_guide_apply_shared_keys_once": st.session_state.get("_allow_design_guide_apply_shared_keys_once"),
            "skip_shear_widget_backflow_once": st.session_state.get("_skip_shear_widget_backflow_once"),
            "skip_shear_widget_backflow_runs": st.session_state.get("_skip_shear_widget_backflow_runs"),
            "pending_inputs_apply_refresh": st.session_state.get("_pending_inputs_apply_refresh"),
            "design_action_state_transition_trace": list(
                st.session_state.get("_design_action_state_transition_trace") or []
            )[-40:],
            "browser_recipe_inputs_widget_hydration_audit": st.session_state.get(
                "_browser_recipe_inputs_widget_hydration_audit"
            ),
            "browser_recipe_widget_mirror_seed_audit": st.session_state.get(
                "_browser_recipe_widget_mirror_seed_audit"
            ),
            "inputs_longitudinal_reo_audit": st.session_state.get("_inputs_longitudinal_reo_audit"),
            "inputs_shear_truth_audit": st.session_state.get("_inputs_shear_truth_audit"),
            "inputs_shear_seed_consume_audit": st.session_state.get("_inputs_shear_seed_consume_audit"),
            "inputs_rerun_trigger_events": list(st.session_state.get("_inputs_rerun_trigger_events") or [])[-24:],
            "ssl_rerun_triggers": list(st.session_state.get("_ssl_rerun_triggers") or [])[-24:],
            "inputs_model_diagram_render_reuse_trace": dict(
                st.session_state.get("_inputs_model_diagram_render_reuse_trace") or {}
            ),
            "inputs_stable_render_reuse_trace": dict(
                st.session_state.get("_inputs_stable_render_reuse_trace") or {}
            ),
            "final_publication_summary_card_html_bypass_debug": dict(
                st.session_state.get("_final_publication_summary_card_html_bypass_debug") or {}
            ),
            "final_publication_summary_card_html_cache_probe": {
                "has_cache": isinstance(
                    st.session_state.get("_final_publication_summary_card_html_cache"), dict
                ),
                "reuse_keys": dict(
                    (
                        st.session_state.get("_final_publication_summary_card_html_cache")
                        if isinstance(
                            st.session_state.get("_final_publication_summary_card_html_cache"),
                            dict,
                        )
                        else {}
                    ).get("reuse_keys")
                    or {}
                ),
                "has_summary_cards_html": isinstance(
                    (
                        st.session_state.get("_final_publication_summary_card_html_cache")
                        if isinstance(
                            st.session_state.get("_final_publication_summary_card_html_cache"),
                            dict,
                        )
                        else {}
                    ).get("summary_cards_html"),
                    str,
                )
                and bool(
                    (
                        st.session_state.get("_final_publication_summary_card_html_cache")
                        if isinstance(
                            st.session_state.get("_final_publication_summary_card_html_cache"),
                            dict,
                        )
                        else {}
                    ).get("summary_cards_html")
                ),
                "authority": (
                    st.session_state.get("_final_publication_summary_card_html_cache")
                    if isinstance(
                        st.session_state.get("_final_publication_summary_card_html_cache"),
                        dict,
                    )
                    else {}
                ).get("authority"),
            },
            "inputs_first_paint_cached_summary_reuse_debug": dict(
                st.session_state.get("_inputs_first_paint_cached_summary_reuse_debug") or {}
            ),
            "inputs_summary_final_render_skip_debug": dict(
                st.session_state.get("_inputs_summary_final_render_skip_debug") or {}
            ),
            "inputs_dirty_cache_probe": {
                "inputs_dirty": bool(st.session_state.get("inputs_dirty")),
                "_inputs_dirty": bool(st.session_state.get("_inputs_dirty")),
                "auto_recompute": bool(st.session_state.get("auto_recompute")),
                "run_design_clicked": bool(st.session_state.get("run_design_clicked")),
                "computed_once": bool(st.session_state.get("_computed_once")),
                "compute_in_progress": bool(st.session_state.get("_compute_in_progress")),
                "solver_running": bool(st.session_state.get("_solver_running")),
                "pending_apply_refresh": bool(st.session_state.get("_pending_inputs_apply_refresh")),
                "apply_in_flight": bool(st.session_state.get(_DESIGN_GUIDE_COMPONENT_APPLY_IN_FLIGHT_KEY)),
                "force_inputs_widget_reseed_once": bool(st.session_state.get("_force_inputs_widget_reseed_once")),
                "results_version": st.session_state.get("results_version"),
                "has_cached_results": isinstance(st.session_state.get("cached_results"), dict),
                "has_cached_compute_results": isinstance(st.session_state.get("_cached_compute_results"), dict),
                "has_summary_html_cache": isinstance(
                    st.session_state.get("_final_publication_summary_card_html_cache"), dict
                ),
            },
        },
        "active_beam_record_probe": {},
        "page_slug": selected_slug,
        "solver_result": st.session_state.get("_solver_result") or _dg_authoritative_solver_probe,
        "one_click_feedback": st.session_state.get("_one_click_run_feedback"),
        "auto_design_entry_probe_before_reconcile": st.session_state.get(
            "_browser_auto_design_entry_probe_before_reconcile",
        ),
        "auto_design_entry_probe_after_reconcile": st.session_state.get(
            "_browser_auto_design_entry_probe_after_reconcile",
        ),
        "auto_design_entry_probe_after_run": st.session_state.get(
            "_browser_auto_design_entry_probe_after_run",
        ),
        "router_probe": st.session_state.get("_browser_router_probe"),
        "pending_recommendation_meta": rec_meta,
        "design_guide_primary_apply_payload": dict(
            _dg_primary_apply_payload_for_publication
        ),
        "design_guide_primary_payload_binding_audit": dict(
            st.session_state.get(inputs_page_app_contracts.DESIGN_GUIDE_PRIMARY_PAYLOAD_BINDING_AUDIT_KEY) or {}
        ),
        "results_version": st.session_state.get("results_version"),
        "summary_state_probe": {
            "uls_Mstar": summary_state_probe.get("uls_Mstar"),
            "uls_Mstar_pos_manual": summary_state_probe.get("uls_Mstar_pos_manual"),
            "uls_Mstar_neg_manual": summary_state_probe.get("uls_Mstar_neg_manual"),
            "uls_Vstar": summary_state_probe.get("uls_Vstar"),
            "load_Mstar_proxy": summary_state_probe.get("load_Mstar_proxy"),
            "load_Mstar_pos_proxy": summary_state_probe.get("load_Mstar_pos_proxy"),
            "load_Mstar_neg_proxy": summary_state_probe.get("load_Mstar_neg_proxy"),
            "load_Vstar_proxy": summary_state_probe.get("load_Vstar_proxy"),
            "actions_mode": summary_state_probe.get("actions_mode"),
            "actions_source": summary_state_probe.get("actions_source"),
            "b": summary_state_probe.get("b"),
            "D": summary_state_probe.get("D"),
            "bot1_count": summary_state_probe.get("bot1_count"),
            "db_bot_1": summary_state_probe.get("db_bot_1"),
            "lig_d": summary_state_probe.get("lig_d"),
            "lig_legs": summary_state_probe.get("lig_legs"),
            "s_lig": summary_state_probe.get("s_lig"),
            "_probe_error": summary_state_probe.get("_probe_error"),
        },
        "engineering_snapshot_probe": engineering_snapshot_probe,
        "authoritative_result_probe": {
            "governing_family": (
                _dg_authoritative_result_for_publication.governing_family
                if _dg_authoritative_result_for_publication is not None
                else None
            ),
            "stored_engineering_hash": (
                _dg_authoritative_result_for_publication.engineering_hash
                if _dg_authoritative_result_for_publication is not None
                else None
            ),
            "publication_selected_family_id": (
                dict(
                    dict(_dg_authoritative_result_for_publication.final_publication or {}).get(
                        "final_design_guide_publication"
                    )
                    or {}
                ).get("selected_family")
                if _dg_authoritative_result_for_publication is not None
                else None
            ),
            "publication_verifier_selected_family_id": (
                dict(
                    dict(_dg_authoritative_result_for_publication.final_publication or {}).get(
                        "final_publication_verifier_payload"
                    )
                    or {}
                ).get("selected_family_id")
                if _dg_authoritative_result_for_publication is not None
                else None
            ),
            "cta_family_id": (
                dict(_dg_authoritative_result_for_publication.cta_model or {}).get("family")
                if _dg_authoritative_result_for_publication is not None
                else None
            ),
            "apply_payload_family_id": (
                dict(_dg_authoritative_result_for_publication.apply_payload or {}).get("family")
                if _dg_authoritative_result_for_publication is not None
                else None
            ),
            "reuse_decision": dict(
                st.session_state.get("_authoritative_design_result_last_decision") or {}
            ),
        },
        "summary_overview_probe": {
            "statuses": dict(summary_overview_probe.get("statuses") or {}),
            "utils": dict(summary_overview_probe.get("utils") or {}),
            "any_fail": summary_overview_probe.get("any_fail"),
            "any_warn": summary_overview_probe.get("any_warn"),
            "all_key_pass": summary_overview_probe.get("all_key_pass"),
            "worst_util": summary_overview_probe.get("worst_util"),
            "governing_util": summary_overview_probe.get("governing_util"),
            "governing_util_source": summary_overview_probe.get("governing_util_source"),
            "governing_check": summary_overview_probe.get("governing_check"),
            "_probe_error": summary_overview_probe.get("_probe_error"),
        },
        "guidance_compute_probe": guidance_probe,
        "post_cleanup_acceptance_probe": {
            "enabled": bool(st.session_state.get("_design_guide_post_cleanup_acceptance_enabled")),
            "stored_fp": str(st.session_state.get("_design_guide_post_cleanup_acceptance_fp")),
            "matches_current": bool(
                local_cleanup_post_apply_acceptance_matches(
                    summary_state_probe,
                    expected_fingerprint=st.session_state.get(
                        "_design_guide_post_cleanup_acceptance_fp"
                    ),
                    accepted_fingerprints=DESIGN_GUIDE_POST_CLEANUP_ACCEPTED_FPS,
                )
            ),
            "last_apply_route": dict(st.session_state.get(inputs_page_app_contracts.DESIGN_GUIDE_LAST_APPLY_ROUTE_KEY) or {}),
            "primary_payload_binding_audit": dict(
                st.session_state.get(inputs_page_app_contracts.DESIGN_GUIDE_PRIMARY_PAYLOAD_BINDING_AUDIT_KEY) or {}
            ),
            "pending_recommendation_applied_id": st.session_state.get("pending_recommendation_applied_id"),
            "run_design_clicked": st.session_state.get("run_design_clicked"),
            "inputs_action_apply_recommendation": st.session_state.get("_inputs_action_apply_recommendation"),
            "inputs_action_run_auto_design": st.session_state.get("_inputs_action_run_auto_design"),
        },
        "design_guide_probe": {
            "needs_refresh": st.session_state.get(inputs_page_app_contracts.DESIGN_GUIDE_NEEDS_REFRESH_KEY),
            "panel_baseline_fingerprint": st.session_state.get(inputs_page_app_contracts.DESIGN_GUIDE_PANEL_BASELINE_FP_KEY),
            "debug_bundle": dg_bundle_safe,
            "render_eligibility_trace": dg_render_eligibility_trace_safe,
            "render_plan_debug": dg_render_plan_safe,
            "guidance_branch": dg_bundle_safe.get("guidance_branch"),
            "terminal_state": dg_bundle_safe.get("design_guide_terminal_state"),
            "terminal_state_source": dg_bundle_safe.get("design_guide_terminal_state_source"),
            "efficiency_classification": dg_eff.get("classification"),
            "efficiency_very_low_demand": dg_eff.get("very_low_demand"),
            "efficiency_current_governing_util": dg_eff.get("optimisation_current_governing_util"),
            "efficiency_current_governing_util_source": dg_eff.get("optimisation_current_governing_util_source"),
            "overview_statuses": dict(dg_ov.get("statuses") or {}),
            "overview_utils": dict(dg_ov.get("utils") or {}),
            "overview_any_fail": dg_ov.get("any_fail"),
            "overview_any_warn": dg_ov.get("any_warn"),
            "overview_all_key_pass": dg_ov.get("all_key_pass"),
            "overview_governing_util": dg_ov.get("governing_util"),
            "overview_governing_util_source": dg_ov.get("governing_util_source"),
            "overview_governing_check": dg_ov.get("governing_check"),
            "primary_card_title": dg_primary_card_title_probe,
            "primary_card_intent": dg_bundle_safe.get("primary_card_intent"),
            "primary_displayed_util": dg_bundle_safe.get("primary_displayed_util"),
            "primary_display_truth_source": dg_bundle_safe.get("primary_display_truth_source"),
            "primary_target_low": dg_bundle_safe.get("primary_target_low"),
            "primary_target_high": dg_bundle_safe.get("primary_target_high"),
            "primary_preview_util": dg_bundle_safe.get("primary_preview_util"),
            "primary_current_util": dg_bundle_safe.get("primary_current_util"),
            "primary_lands_in_target_band": dg_bundle_safe.get("primary_lands_in_target_band"),
            "primary_allowed_blocker": dg_bundle_safe.get("primary_allowed_blocker"),
            "button_contract_enabled": dg_bundle_safe.get("button_contract_enabled"),
            "button_contract_updates": dict(dg_bundle_safe.get("button_contract_updates") or {}),
            "button_contract_preview_pass": dg_bundle_safe.get("button_contract_preview_pass"),
            "button_contract_blocking_reason": dg_bundle_safe.get("button_contract_blocking_reason"),
            "candidate_search_evidence": dict(dg_bundle_safe.get("candidate_search_evidence") or {}),
            "design_guide_engine_decision_reason": dg_bundle_safe.get("design_guide_engine_decision_reason"),
            "design_guide_engine_suppressed_count": dg_bundle_safe.get("design_guide_engine_suppressed_count"),
            "design_guide_engine_suppressed_reasons": list(dg_bundle_safe.get("design_guide_engine_suppressed_reasons") or []),
        },
        "speed_profile_probe": get_speed_profile_summary(top_n=25),
        "ux_latency_probe": get_ux_latency_probe_summary(),
        "render_timing_probe": get_render_timing_summary(),
    }
    try:
        from state_and_helpers import _beam_records_dict

        active_beam_id = st.session_state.get("active_beam_id")
        active_record = dict((_beam_records_dict().get(active_beam_id) or {}))
        active_params = dict(active_record.get("params") or {})
        payload["active_beam_record_probe"] = {
            "active_beam_id": active_beam_id,
            "beam_last_hydrated_id": st.session_state.get("beam_last_hydrated_id"),
            "b": active_params.get("b"),
            "D": active_params.get("D"),
            "bot1_count": active_params.get("bot1_count"),
            "db_bot_1": active_params.get("db_bot_1"),
            "lig_d": active_params.get("lig_d"),
            "lig_legs": active_params.get("lig_legs"),
            "s_lig": active_params.get("s_lig"),
            "uls_Mstar": active_params.get("uls_Mstar"),
            "uls_Vstar": active_params.get("uls_Vstar"),
        }
    except Exception as exc:
        payload["active_beam_record_probe"] = {
            "_probe_error": f"{type(exc).__name__}: {exc}",
        }
    render_timing_mark("app.browser_test_state_emit.payload_json.start", probe_phase=probe_phase)
    with speed_profile_section("browser_probe.payload_json_build", category="compute"):
        st.session_state["_browser_state_probe"] = json.dumps(payload, default=str)
    ux_probe_record("browser_probe.payload_json_build")
    render_timing_mark("app.browser_test_state_emit.payload_json.end", probe_phase=probe_phase)
    browser_state_probe_text = st.session_state.get("_browser_state_probe", "{}")
    browser_state_probe_key = (
        "_browser_state_probe_text_area_"
        + str(probe_phase or "final")
        + "_"
        + hashlib.sha1(str(browser_state_probe_text).encode("utf-8", errors="ignore")).hexdigest()[:12]
    )
    if probe_slot is not None:
        with probe_slot.container():
            _render_hidden_browser_state_probe(browser_state_probe_text, browser_state_probe_key)
    else:
        _render_hidden_browser_state_probe(browser_state_probe_text, browser_state_probe_key)
    render_timing_mark("app.browser_test_state_emit.end", selected_slug=selected_slug, probe_phase=probe_phase)


def _get_compute_fingerprint():
    import streamlit as st

    return tuple(sorted(
        (k, str(st.session_state.get(k)))
        for k in st.session_state.keys()
        if not str(k).startswith("_")
    ))


def _render_lazy_page(module_name: str, function_name: str):
    module = importlib.import_module(module_name)
    renderer = getattr(module, function_name, None)
    if callable(renderer):
        return renderer()

    # Hot-reload can occasionally leave a stale partial module object around.
    refreshed_module = importlib.reload(module)
    refreshed_renderer = getattr(refreshed_module, function_name, None)
    if callable(refreshed_renderer):
        return refreshed_renderer()

    raise AttributeError(f"module {module_name!r} has no attribute {function_name!r}")


def _render_design_page():
    return _render_lazy_page("sfd_bmd_page", "render_sfd_bmd_page")


def _render_start_page():
    return start_page.render_start_page(
        make_cross_section_figure_fn=inputs_page.make_summary_cross_section_figure,
        user_id=_get_user_id(),
    )


def _render_bending_page():
    return _render_lazy_page("bending_page", "render_bending")


def _render_shear_page():
    return _render_lazy_page("shear_page", "render_shear")


def _render_creep_page():
    return _render_lazy_page("creep", "render_creep")


def _render_shrinkage_page():
    return _render_lazy_page("shrinkage", "render_shrinkage")


def _render_crack_page():
    return _render_lazy_page("crack_page", "render_crack_control")


def _render_deflection_page():
    return _render_lazy_page("deflection", "render_deflection")

def _record_result_page_fragment_render(slug: str) -> None:
    """Record one page-local render without creating engineering authority."""

    counts = dict(st.session_state.get("_result_page_fragment_render_counts") or {})
    counts[slug] = int(counts.get(slug, 0) or 0) + 1
    st.session_state["_result_page_fragment_render_counts"] = counts


def _refresh_result_page_fragment_calculations() -> None:
    """Commit one coherent legacy-result projection for a page-local edit.

    The detailed result pages still consume the shared ``RESULT_KEYS`` view.
    Keep that projection and its cache together so a later shell navigation
    cannot restore the result that preceded the fragment edit.
    """

    recalc_derived_values()
    compute_all_results()
    update_results()
    result_values = {
        key: copy.deepcopy(st.session_state.get(key))
        for key in RESULT_KEYS
        if key in st.session_state
    }
    result_buckets = copy.deepcopy(st.session_state.get("results") or {})
    st.session_state["_cached_compute_results"] = {
        "result_values": result_values,
        "result_buckets": result_buckets,
    }
    st.session_state["cached_results"] = copy.deepcopy(result_buckets)
    st.session_state["inputs_dirty"] = False
    st.session_state["_inputs_dirty"] = False
    st.session_state["run_design_clicked"] = False


@st.fragment
def _render_bending_page_fragment():
    _record_result_page_fragment_render("bending")
    _refresh_result_page_fragment_calculations()
    _ensure_general_page_engineering_publication("bending")
    return _render_bending_page()


@st.fragment
def _render_shear_page_fragment():
    _record_result_page_fragment_render("shear")
    _refresh_result_page_fragment_calculations()
    _ensure_general_page_engineering_publication("shear")
    return _render_shear_page()


@st.fragment
def _render_creep_page_fragment():
    _record_result_page_fragment_render("creep")
    _refresh_result_page_fragment_calculations()
    _ensure_general_page_engineering_publication("creep")
    return _render_creep_page()


@st.fragment
def _render_shrinkage_page_fragment():
    _record_result_page_fragment_render("shrinkage")
    _refresh_result_page_fragment_calculations()
    _ensure_general_page_engineering_publication("shrinkage")
    return _render_shrinkage_page()


@st.fragment
def _render_crack_page_fragment():
    _record_result_page_fragment_render("crack")
    _refresh_result_page_fragment_calculations()
    _ensure_general_page_engineering_publication("crack")
    return _render_crack_page()


@st.fragment
def _render_deflection_page_fragment():
    _record_result_page_fragment_render("deflection")
    _refresh_result_page_fragment_calculations()
    _ensure_general_page_engineering_publication("deflection")
    return _render_deflection_page()


_GENERAL_ENGINEERING_RESULT_PAGES = frozenset(
    {"bending", "shear", "creep", "shrinkage", "crack", "deflection"}
)


def _ensure_general_page_engineering_publication(selected_slug: str) -> None:
    """Publish the current beam's V2 calculation before result-page render.

    This is an application-shell coordination step, not page-local calculation
    authority.  The detailed pages remain read-only consumers of one shared,
    revision-matched V2 result and never fall back to their historical local
    summary calculators.
    """

    slug = str(selected_slug or "").strip().lower()
    if slug not in _GENERAL_ENGINEERING_RESULT_PAGES:
        return
    from inputs_application.page_runtime import refresh_inputs_engineering_result

    result = refresh_inputs_engineering_result()
    st.session_state["_general_page_engineering_publication_probe"] = {
        "page": slug,
        "engineering_hash": getattr(result, "engineering_hash", None),
        "source": "app.general_page_engineering_publication",
    }


# ---- page registry ----
PAGES = {
    "start": ("Start", _render_start_page),
    "inputs": ("Beam Inputs", inputs_page.render_inputs),
    "design": ("Load Analysis", _render_design_page),
    "bending": ("Bending", _render_bending_page_fragment),
    "shear": ("Shear", _render_shear_page_fragment),
    "creep": ("Creep", _render_creep_page_fragment),
    "shrinkage": ("Shrinkage", _render_shrinkage_page_fragment),
    "crack": ("Crack Control", _render_crack_page_fragment),
    "deflection": ("Deflection", _render_deflection_page_fragment),
}

# Page-level headings belong to the shared application shell so every route
# starts at the same position and uses the same semantic/visual H1.  Navigation
# labels stay deliberately shorter where that reads better in the tab row.
PAGE_TITLES = {
    "start": "Start your beam design",
    "inputs": "Beam Inputs",
    "design": "Load Analysis",
    "bending": "Bending capacity",
    "shear": "Shear & Torsion",
    "creep": "Creep",
    "shrinkage": "Shrinkage",
    "crack": "Crack width – AS 3600:2018",
    "deflection": "Beam Deflection",
}


def _active_page_title(slug: str) -> str:
    """Return the shell H1, including the selected concrete design method."""
    if slug == "crack":
        method = str(st.session_state.get("crack_control_method", "existing_as3600") or "existing_as3600")
        return {
            "existing_as3600": "Crack width – AS 3600:2018",
            "as5100_wall": "Wall crack control – AS 5100.5:2017 Clause 11.7.2",
            "ciria_c766_ec2": "Restrained-deformation crack control – CIRIA C766 / EC2",
        }.get(method, PAGE_TITLES[slug])
    if slug == "shrinkage":
        method = str(st.session_state.get("shrinkage_method", "existing_as3600") or "existing_as3600")
        return {
            "existing_as3600": "Shrinkage – AS 3600:2018",
            "ec2_c766": "Shrinkage – EC2 equation method / CIRIA C766",
        }.get(method, PAGE_TITLES[slug])
    return PAGE_TITLES[slug]

SHARED_PAGE_TITLE_ACTIVE_KEY = "_shared_page_title_owned_by_shell"

SLUGS = list(PAGES.keys())
LABELS = [PAGES[s][0] for s in SLUGS]

NAV_KEY = "nav_page_slug"  # stores the slug, e.g. "shear"
LAST_QP_KEY = "last_qp_page_seen"   # local-only UI state
# Set from pages rendered after the top nav radio; consumed at start of main() before that widget.
PENDING_NAV_PAGE_SLUG_KEY = "_pending_nav_page_slug"


def set_query_params_merge(**updates):
    """Update query params without clearing (avoids session/connection resets)."""
    # Apply updates
    for k, v in updates.items():
        if v is None:
            # remove if present
            try:
                del st.query_params[k]
            except Exception:
                pass
        else:
            st.query_params[k] = v


def _get_user_id() -> str:
    ensure_logged_in_state()
    user = st.session_state.get("sb_user")
    if user:
        return user.id if hasattr(user, "id") else user.get("id", "")
    try:
        from auth_streamlit import get_user_id_from_token
    except Exception:
        return ""
    return get_user_id_from_token()


@st.fragment
def _render_header_actions(
    *,
    user_id: str,
    project_id: str | None,
    module: str,
) -> None:
    """Render report and persistence controls without remounting the page."""
    st.session_state.setdefault("report_mode", "standard")
    report_mode = str(st.session_state.get("report_mode", "standard")).strip().lower()
    if report_mode not in {"standard", "detailed"}:
        report_mode = "standard"
        st.session_state["report_mode"] = report_mode

    c_save, c_pdf, c_pdf_opts, _ = st.columns([2.4, 3.8, 0.5, 0.25], gap="small")

    with c_save:
        st.markdown(
            '<span class="beam-header-action-marker" aria-hidden="true"></span>',
            unsafe_allow_html=True,
        )
        if st.button("💾 Save", type="primary", use_container_width=True):
            if not user_id:
                st.error("You must be logged in to save projects.")
            elif project_id:
                try:
                    from projects_store import update_project

                    payload = export_state_for_saving()
                    update_project(
                        project_id=project_id,
                        user_id=user_id,
                        payload=payload,
                        meta={"module": module},
                    )
                    st.toast("Saved", icon="✅")
                except Exception as exc:
                    st.error(f"Save failed: {exc}")
            else:
                # Opening the project-creation shell is an intentional app-level
                # transition; it is not a page-local engineering interaction.
                st.session_state["_show_save_modal"] = True
                st.rerun(scope="app")

    with c_pdf:
        from reporting.example_integration import render_pdf_button

        st.markdown(
            '<span class="beam-header-action-marker" aria-hidden="true"></span>',
            unsafe_allow_html=True,
        )
        render_pdf_button(
            detail_level=report_mode,
            section_figure_factory=inputs_page.make_summary_cross_section_figure,
            beam_figure_factory=inputs_page.make_beam_3d_figure,
        )

    with c_pdf_opts:
        report_container = (
            info_i_button(help_text="Report options")
            if hasattr(st, "popover")
            else st.expander("i", expanded=False)
        )
        with report_container:
            st.selectbox(
                "Report mode",
                options=["standard", "detailed"],
                key="report_mode",
                format_func=lambda mode: (
                    "Standard Report" if mode == "standard" else "Detailed Report"
                ),
            )
            st.text_input(
                "Company name (optional)",
                key="report_company_name",
                placeholder="Your company name",
            )
            report_logo = st.file_uploader(
                "Upload company logo (optional)",
                type=["png", "jpg", "jpeg"],
                key="report_company_logo_upload",
                help="Used for the current report session only. Not saved to the project.",
            )
            if report_logo is not None:
                st.session_state["report_company_logo_bytes"] = report_logo.getvalue()
                st.session_state["report_company_logo_name"] = report_logo.name
                st.session_state["report_company_logo_type"] = report_logo.type
                st.image(report_logo, width=120)
            else:
                st.session_state["report_company_logo_bytes"] = None
                st.session_state["report_company_logo_name"] = None
                st.session_state["report_company_logo_type"] = None


def _render_create_project_form(user_id: str, module: str):
    name = st.text_input(
        "Project name",
        placeholder="e.g. SRL East â€“ RC Beam over Station Box",
    )
    st.caption("This creates a project so you can open it later from your dashboard.")
    cA, cB = st.columns([1, 1])
    with cA:
        if st.button("Cancel", use_container_width=True):
            st.session_state["_show_save_modal"] = False
            st.rerun()
    with cB:
        if st.button("Create & Save", type="primary", use_container_width=True):
            if not user_id:
                st.error("You must be logged in to save projects.")
                return
            if not name.strip():
                st.error("Project name is required.")
            else:
                try:
                    from projects_store import create_project

                    payload = export_state_for_saving()
                    row = create_project(
                        user_id=user_id,
                        name=name.strip(),
                        payload=payload,
                        meta={"module": module},
                    )
                    new_id = row.get("id")

                    # Ensure future saves use this project and the parent URL has ?project=<id>
                    if new_id:
                        redirect_parent_to_project(new_id)
                        st.session_state["active_project_id"] = new_id
                        st.session_state["active_project_name"] = name.strip()

                    st.session_state["_show_save_modal"] = False
                    st.toast("Project created and saved", icon="âœ…")
                    st.rerun()
                except Exception as e:
                    st.error(f"Create/save failed: {e}")


def main():
    try:
        path = _local_trace_log_path("design_guide_tracer.jsonl")
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(
                json.dumps(
                    {
                        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime())
                        + f".{int((time.time() % 1) * 1000):03d}Z",
                        "event": "app_main_stage",
                        "source": "app.main",
                        "data": {"stage": "entry"},
                    },
                    sort_keys=True,
                )
                + "\n"
            )
    except Exception:
        pass
    # --- ARCHITECTURE LOCK: dev mode flag ---
    _browser_test_mode_for_run = bool(_browser_test_mode_active())
    st.session_state.setdefault("_dev_mode", bool(_browser_test_mode_for_run or _EXPLICIT_DEV_MODE))
    # Preserve the wide responsive layout across route and hot-reload renders.
    _apply_sharp_embed_css()
    _apply_normal_user_page_zoom_css()
    reset_speed_profile_last_run()
    reset_rerun_pure_caches()
    ux_probe_begin_rerun()
    incoming_browser_recipe = _get_query_param_scalar(_BROWSER_RECIPE_PARAM)
    if _browser_test_mode_for_run:
        if incoming_browser_recipe:
            st.session_state["_browser_recipe_query_value"] = incoming_browser_recipe
        else:
            # The query value is only a same-request bridge. Once a browser
            # removes the recipe parameter, retaining it would reactivate the
            # old seed and overwrite correctly hydrated engineering widgets.
            st.session_state.pop("_browser_recipe_query_value", None)
            if not str(os.environ.get("CODEX_BROWSER_REPLAY_RECIPE") or "").strip():
                st.session_state.pop(_BROWSER_RECIPE_WIDGET_FORCING_KEY, None)
    render_timing_begin_rerun(
        url_page=_get_query_param_scalar("page"),
        browser_recipe=incoming_browser_recipe or st.session_state.get("_browser_recipe_query_value"),
    )
    render_timing_mark("app.main.entry")
    ensure_logged_in_state()

    # --- CSS styling for top navigation (make radio look like Streamlit tabs) ---
    st.markdown("""
<style>
/* ==========================================================
   TOP PAGE NAV ONLY (matches Streamlit st.tabs style)
   Scoped to the Navigation radio widget key so page-local radios
   such as "Design mode" cannot inherit the tab treatment.
   ========================================================== */

/* Page modules inject code-only style blocks before their visible summary.
   Streamlit gives each zero-height block a layout slot, which otherwise
   creates a large false gap below the shared page heading. */
div[data-testid="stVerticalBlock"]:has(
  > div[data-testid="stElementContainer"]:first-child h1
) > div[data-testid="stElementContainer"]:has(style) {
  display: none !important;
}

/* Every route is rendered beneath this shell-owned marker.  Use it to give
   page headings one shared, slightly lower start position and to remove
   zero-height placeholders that would otherwise add flex-gap space on only
   some pages (notably Beam Inputs). */
div[data-testid="stVerticalBlock"]:has(
  > div[data-testid="stElementContainer"] #shared-page-content-anchor
) > div[data-testid="stElementContainer"]:has(h1) {
  margin-top: 0.5rem !important;
}
div[data-testid="stVerticalBlock"]:has(
  > div[data-testid="stElementContainer"] #shared-page-content-anchor
) > div[data-testid="stElementContainer"]:has(#shared-page-content-anchor),
div[data-testid="stVerticalBlock"]:has(
  > div[data-testid="stElementContainer"] #shared-page-content-anchor
) > div[data-testid="stElementContainer"]:empty {
  display: none !important;
}
div[data-testid="stVerticalBlock"]:has(
  > div[data-testid="stElementContainer"] #shared-page-content-anchor
) > div[data-testid="stElementContainer"]:has(> [data-testid="stEmpty"]:only-child) {
  display: none !important;
}

/* CSS-only page setup blocks can sit inside a page fragment rather than
   beside the H1.  Hide only those style slots that occur before the summary
   stack; this removes their flex gaps without affecting diagram/content
   elements later in the page. */
div[data-testid="stVerticalBlock"]:has(
  > div[data-testid="stElementContainer"] #shared-page-content-anchor
) > div[data-testid="stElementContainer"]:has(style):has(~ div .summary-card-stack),
div[data-testid="stVerticalBlock"]:has(
  > div[data-testid="stElementContainer"] #shared-page-content-anchor
) div[data-testid="stVerticalBlock"]
  > div[data-testid="stElementContainer"]:has(style):has(~ div .summary-card-stack) {
  display: none !important;
}

/* Keep page help beside the heading without letting its dedicated row push
   result summary cards below the true Beam Inputs summary-card position. */
div[data-testid="stVerticalBlock"]:has(
  > div[data-testid="stLayoutWrapper"] > div.st-key-page_explainer_float
) {
  position: relative !important;
}
div[data-testid="stVerticalBlock"]:has(
  > div[data-testid="stLayoutWrapper"] > div.st-key-page_explainer_float
) > div[data-testid="stLayoutWrapper"]:has(
  > div.st-key-page_explainer_float
) {
  position: absolute !important;
  top: -60px !important;
  right: 0 !important;
  width: 100% !important;
  z-index: 20 !important;
  pointer-events: none !important;
}
div[data-testid="stLayoutWrapper"]:has(
  > div.st-key-page_explainer_float
) * {
  pointer-events: auto !important;
}
div[data-testid="stVerticalBlock"]:has(
  > div[data-testid="stLayoutWrapper"] > div.st-key-page_explainer_float
) > div[data-testid="stElementContainer"]:has(style):not(:has(.summary-card-stack)) {
  display: none !important;
}

div[data-testid="stVerticalBlock"]:has(#page-nav-anchor) div[role="radiogroup"]{
  display:flex !important;
  align-items:center !important;
  gap:18px !important;
  border-bottom: 1px solid rgba(49,51,63,0.20) !important;
  padding-bottom: 4px !important;
  margin-bottom: 0.15rem !important;
}

/* tab label */
div[data-testid="stVerticalBlock"]:has(#page-nav-anchor) div[role="radiogroup"] > label{
  margin:0 !important;
  padding: 6px 2px !important;
  background: transparent !important;
  border: none !important;
  border-bottom: 2px solid transparent !important;
  border-radius: 0 !important;
  box-shadow: none !important;
  cursor: pointer !important;
  font-weight: 500 !important;
}

/* remove the radio circle/control (robust across Streamlit builds) */
div[data-testid="stVerticalBlock"]:has(#page-nav-anchor) div[role="radiogroup"] > label svg,
div[data-testid="stVerticalBlock"]:has(#page-nav-anchor) div[role="radiogroup"] > label [role="img"],
div[data-testid="stVerticalBlock"]:has(#page-nav-anchor) div[role="radiogroup"] > label input[type="radio"],
div[data-testid="stVerticalBlock"]:has(#page-nav-anchor) div[role="radiogroup"] > label > div:first-child,
div[data-testid="stVerticalBlock"]:has(#page-nav-anchor) div[role="radiogroup"] > label > span:first-child{
  display:none !important;
}
/* Streamlit's current radio renderer nests the control one level deeper. */
div[data-testid="stVerticalBlock"]:has(#page-nav-anchor) div[role="radiogroup"] > label[data-testid="stRadioOption"] > div > div > div:first-child{
  display:none !important;
}

/* active underline (tab selected) */
div[data-testid="stVerticalBlock"]:has(#page-nav-anchor) div[role="radiogroup"] > label:has(input:checked),
div[data-testid="stVerticalBlock"]:has(#page-nav-anchor) div[role="radiogroup"] > label[aria-checked="true"]{
  border-bottom: 2px solid #ff4b4b !important;
  font-weight: 600 !important;
}

/* prevent "button hover" feel */
div[data-testid="stVerticalBlock"]:has(#page-nav-anchor) div[role="radiogroup"] > label:hover{
  background: transparent !important;
}

/* tighten inner wrappers */
div[data-testid="stVerticalBlock"]:has(#page-nav-anchor) div[role="radiogroup"] > label *{
  margin:0 !important;
  padding:0 !important;
}

/* Header actions intentionally use the app's red action colour.  The marker
   scopes this rule to Save and PDF Report only; other primary buttons retain
   their existing theme treatment. */
/* The marker is a direct child of the Save/PDF column's element container.
   Restrict the rule to that local column; using :has(marker) on the page
   shell accidentally coloured every descendant button red, including the
   Design Brain CTA. */
div[data-testid="stVerticalBlock"]:has(> div[data-testid="stElementContainer"] .beam-header-action-marker) div[data-testid="stButton"] > button,
div[data-testid="stVerticalBlock"]:has(> div[data-testid="stElementContainer"] .beam-header-action-marker) div[data-testid="stDownloadButton"] > button{
  background:#e03131 !important;
  border-color:#e03131 !important;
  color:#fff !important;
}
div[data-testid="stVerticalBlock"]:has(> div[data-testid="stElementContainer"] .beam-header-action-marker) div[data-testid="stButton"] > button:hover,
div[data-testid="stVerticalBlock"]:has(> div[data-testid="stElementContainer"] .beam-header-action-marker) div[data-testid="stDownloadButton"] > button:hover{
  background:#c92a2a !important;
  border-color:#c92a2a !important;
  color:#fff !important;
}
</style>
""", unsafe_allow_html=True)

    def _render_project_header_compact():
        name = st.session_state.get("active_project_name") or "Unsaved / New project"
        st.caption(f"**Project:** {name}")

    # ------------------------------------------------------------
    # Header row: title (left) + Save button (right)
    # ------------------------------------------------------------
    project_id, token, module = get_context()
    user_id = _get_user_id()
    if project_id:
        st.session_state["active_project_id"] = project_id

    if project_id and user_id:
        needs_name = not st.session_state.get("active_project_name")
        loaded_for_id = st.session_state.get("_active_project_loaded_id")
        if needs_name or loaded_for_id != project_id:
            try:
                from projects_store import load_project

                project_row = load_project(project_id=project_id, user_id=user_id)
                st.session_state["active_project_id"] = project_row.get("id") or project_id
                st.session_state["active_project_name"] = project_row.get("name") or "Untitled project"
                st.session_state["_active_project_loaded_id"] = project_row.get("id") or project_id
                try:
                    payload = project_row.get("payload") or {}
                    # ðŸ”’ Prevent snapshot restore from overwriting loaded project state
                    from state_and_helpers import (
                        DISABLE_SNAPSHOT_RESTORE_KEY,
                        clear_cached_and_widget_restore_keys,
                    )

                    st.session_state[DISABLE_SNAPSHOT_RESTORE_KEY] = True
                    clear_cached_and_widget_restore_keys()

                    apply_project_payload(payload)

                    # After applying a project payload, snapshot is now â€œdirtyâ€ state.
                    st.session_state["_dirty"] = True
                    st.session_state["_dirty_reason"] = "Loaded project payload"
                    # Recompute is gate-owned; mark inputs dirty and let the
                    # centralized pipeline run once for this rerun.
                    st.session_state["inputs_dirty"] = True
                    st.session_state["_inputs_dirty"] = True
                except Exception:
                    pass
            except Exception:
                st.session_state["_active_project_loaded_id"] = project_id

    _render_project_header_compact()

    header_left, header_right = st.columns([0.55, 0.45], vertical_alignment="center")

    with header_left:
        st.title("Beam design")

    with header_right:
        # --- Top right actions row (Save + Generate PDF on same level) ---
        left, right = st.columns([1.3, 8.7], gap="large")

        with right:
            _render_header_actions(
                user_id=user_id,
                project_id=project_id,
                module=module,
            )

    # Modal for first-time save (no project id yet)
    if st.session_state.get("_show_save_modal", False):
        # --- Create project UI (compatible with Streamlit versions without st.modal) ---
        if hasattr(st, "modal"):
            with st.modal("Create project to save"):
                _render_create_project_form(user_id, module)
        else:
            with st.expander("Create project to save", expanded=True):
                _render_create_project_form(user_id, module)

    

    # --- 0) Deferred top-level nav (e.g. Inputs landing) â€” must run before NAV_KEY st.radio.
    if not user_id and not project_id:
        # Read a guest's browser-local choice through the Streamlit component
        # bridge. Its first value arrives on a component rerun, so remember
        # whether this navigation originally had an explicit page before the
        # router writes its normal query parameter.
        if "_guest_opening_default_pending" not in st.session_state:
            initial_query_page = st.query_params.get("page")
            if isinstance(initial_query_page, list):
                initial_query_page = initial_query_page[0] if initial_query_page else None
            st.session_state["_guest_opening_default_pending"] = initial_query_page not in PAGES
        guest_preference = render_guest_preference_bootstrap()
        if (
            isinstance(guest_preference, dict)
            and guest_preference.get("ready") is True
            and st.session_state.get("_guest_opening_default_pending")
        ):
            guest_slug = str(guest_preference.get("value") or "start")
            if guest_slug not in ("start", "inputs", "design"):
                guest_slug = "start"
            st.session_state[NAV_KEY] = guest_slug
            st.session_state[LAST_QP_KEY] = guest_slug
            st.session_state["_guest_opening_default_pending"] = False
            try:
                st.query_params["page"] = guest_slug
            except Exception:
                pass

    pending_nav_slug = st.session_state.pop(PENDING_NAV_PAGE_SLUG_KEY, None)
    if isinstance(pending_nav_slug, str) and pending_nav_slug in PAGES:
        st.session_state[NAV_KEY] = pending_nav_slug
        st.session_state[LAST_QP_KEY] = pending_nav_slug
        try:
            st.query_params["page"] = pending_nav_slug
        except Exception:
            pass

    # --- 1) Read URL param (page) and pre-set nav state BEFORE widget renders
    qp_page = st.query_params.get("page")
    if isinstance(qp_page, list):
        qp_page = qp_page[0] if qp_page else None

    # âœ… Adopt URL -> nav when the URL page slug changed since last sync, OR when
    # ?jump= is present and nav still disagrees (summary link landed while radio lagged).
    # Never adopt on nav_slug != qp_page alone: after a tab change the widget updates
    # before step 3 rewrites ?page=, and we'd overwrite the new selection with the old URL.
    if qp_page in PAGES:
        last_seen = st.session_state.get(LAST_QP_KEY)
        nav_slug = st.session_state.get(NAV_KEY)
        jump_pending = "jump" in st.query_params
        if last_seen != qp_page or (jump_pending and nav_slug != qp_page):
            st.session_state[NAV_KEY] = qp_page
            st.session_state[LAST_QP_KEY] = qp_page

    # âœ… If no valid page in URL, still ensure defaults exist
    if NAV_KEY not in st.session_state:
        if project_id:
            initial_slug = str(st.session_state.get("_last_design_page_slug") or "inputs")
        elif user_id:
            initial_slug = load_opening_page_preference(
                user_id=user_id,
                session_state=st.session_state,
            )
        else:
            initial_slug = "start"
        st.session_state[NAV_KEY] = initial_slug if initial_slug in PAGES else "start"

    # --- 2) TOP "tabs" (same logic, just container + anchor for CSS targeting)
    nav_container = st.container()
    with nav_container:
        st.markdown('<div id="page-nav-anchor"></div>', unsafe_allow_html=True)

        selected_slug = st.radio(
            "Navigation",
            options=SLUGS,
            horizontal=True,
            key=NAV_KEY,
            format_func=lambda s: PAGES[s][0],  # Display label but store slug
            label_visibility="collapsed",
        )
        st.session_state["_active_page_slug"] = selected_slug
        render_timing_mark("app.page_selection.done", selected_slug=selected_slug)

    # --- 3) Sync URL ONLY if it differs (prevents "stuck on bending" loops)
    # âœ… If a jump is present, DO NOT touch query params at all.
    render_timing_mark("app.pre_dispatch.query_param_sync.start", selected_slug=selected_slug)
    if "jump" not in st.query_params:
        if st.query_params.get("page") != selected_slug:
            render_timing_mark("app.pre_dispatch.query_param_sync.set_query_params", selected_slug=selected_slug)
            set_query_params_merge(page=selected_slug)
            st.session_state[LAST_QP_KEY] = selected_slug
    render_timing_mark("app.pre_dispatch.query_param_sync.end", selected_slug=selected_slug)

    same_beam_inputs_return_active = _inputs_route_authority_handoff(selected_slug)

    # ============================================================
    # PHASE 1: ROUTER-OWNED LIFECYCLE (matches State Lab ordering)
    # ============================================================
    # Enforce exact render pipeline order:
    # 1. init_shared_session_state()
    # 2. set current slug into st.session_state["page_slug"]
    # 3. hydrate_active_page_widgets_from_shared(selected_slug)
    # 4. begin_render_cycle()
    # 5. render page function
    # 6. persist_state_snapshot()
    # ============================================================

    # Step 1: Initialize shared state (restores any dropped widget keys from cache or shared keys)
    # Note: migrate_time_defaults_once() is called inside init_shared_session_state() after snapshot restore
    render_timing_mark("app.pre_dispatch.init_shared_session_state.start")
    init_shared_session_state()
    render_timing_mark("app.pre_dispatch.init_shared_session_state.end")
    if _browser_test_mode_for_run:
        st.session_state["_browser_router_probe"] = {
            "after_init_shared": _browser_action_probe("after_init_shared"),
            "same_beam_inputs_return_active": bool(
                st.session_state.get("_inputs_same_beam_return_active")
            ),
            "same_beam_inputs_return_restored_keys": list(
                st.session_state.get("_inputs_same_beam_return_restored_keys") or []
            ),
        }
    render_timing_mark("app.pre_dispatch.session_state_final_log_reset.start")
    try:
        _session_state_final_log.reset_session_state_final_log_run()
    except Exception:
        pass
    render_timing_mark("app.pre_dispatch.session_state_final_log_reset.end")
    # Apply stored active-beam params into shared before design resolution and widget hydration.
    render_timing_mark("app.pre_dispatch.load_active_beam_into_shared.start")
    same_beam_inputs_route_return = bool(
        same_beam_inputs_return_active
        or st.session_state.get("_inputs_same_beam_return_active")
    )
    if same_beam_inputs_route_return:
        # Inputs already owns the committed engineering transaction for this
        # beam. Returning from another page must not reseed shared values from
        # the older beam record before the Inputs restore coordinator runs.
        st.session_state["beam_last_hydrated_id"] = st.session_state.get(
            "active_beam_id"
        )
        beam_hydrated = False
    else:
        with speed_profile_section("shared_state_hydration.load_active_beam_into_shared", category="state_mutation"):
            beam_hydrated = bool(load_active_beam_into_shared())
    render_timing_mark("app.pre_dispatch.load_active_beam_into_shared.end", beam_hydrated=beam_hydrated)
    if beam_hydrated:
        _queue_inputs_refresh_after_shared_seed("router_active_beam_shared_seed")
    if _browser_test_mode_for_run:
        router_probe = dict(st.session_state.get("_browser_router_probe") or {})
        router_probe["after_load_active_beam"] = {
            **_browser_action_probe("after_load_active_beam"),
            "beam_hydrated": beam_hydrated,
            "same_beam_inputs_route_return": bool(same_beam_inputs_route_return),
        }
        st.session_state["_browser_router_probe"] = router_probe
    render_timing_mark("app.pre_dispatch.apply_browser_recipe.start")
    _apply_browser_recipe_from_query()
    render_timing_mark(
        "app.pre_dispatch.apply_browser_recipe.end",
        browser_recipe=st.session_state.get(_BROWSER_RECIPE_APPLIED_KEY),
        browser_recipe_error=st.session_state.get("_browser_recipe_error"),
        boot_compute_pending=bool(st.session_state.get("_browser_recipe_boot_compute_pending")),
    )
    if _browser_test_mode_for_run:
        router_probe = dict(st.session_state.get("_browser_router_probe") or {})
        router_probe["after_browser_recipe"] = {
            **_browser_action_probe("after_browser_recipe"),
            "browser_recipe": st.session_state.get(_BROWSER_RECIPE_APPLIED_KEY),
            "browser_recipe_error": st.session_state.get("_browser_recipe_error"),
        }
        st.session_state["_browser_router_probe"] = router_probe
    render_timing_mark("app.pre_dispatch.load_proxies.start")
    with speed_profile_section("shared_state_hydration.router_load_proxies", category="state_mutation"):
        sync_load_edit_mode_from_toggle(active_slug=selected_slug)
        load_proxies_from_active_set()
    render_timing_mark("app.pre_dispatch.load_proxies.end")
    if _browser_test_mode_for_run:
        router_probe = dict(st.session_state.get("_browser_router_probe") or {})
        router_probe["after_load_proxies"] = _browser_action_probe("after_load_proxies")
        st.session_state["_browser_router_probe"] = router_probe
    render_timing_mark("app.pre_dispatch.derive_design_actions.start")
    with speed_profile_section("shared_state_hydration.router_derive_design_actions", category="state_mutation"):
        derive_design_actions()
    render_timing_mark("app.pre_dispatch.derive_design_actions.end")
    if _browser_test_mode_for_run:
        router_probe = dict(st.session_state.get("_browser_router_probe") or {})
        router_probe["after_derive_design_actions"] = _browser_action_probe("after_derive_design_actions")
        st.session_state["_browser_router_probe"] = router_probe
    render_timing_mark("app.pre_dispatch.prime_browser_recipe_results_if_needed.start")
    _prime_browser_recipe_results_if_needed()
    render_timing_mark("app.pre_dispatch.prime_browser_recipe_results_if_needed.end")
    if _browser_test_mode_for_run:
        router_probe = dict(st.session_state.get("_browser_router_probe") or {})
        router_probe["after_browser_recipe_boot_compute"] = _browser_action_probe(
            "after_browser_recipe_boot_compute",
        )
        st.session_state["_browser_router_probe"] = router_probe
    # Layer 4: invalid shear combinations in shared state (must not run during page render).
    _shear_norm_changed = False
    try:
        render_timing_mark("app.pre_dispatch.shear_normalisation.start")
        _session_state_final_log.append_session_state_final_log(
            "router_pre_hydrate_shear_normalisation_start",
            {"stage": "router"},
        )
        _shear_norm_changed = bool(
            run_inputs_pre_hydrate_shear_normalization(
                st.session_state,
                set_shared_fn=set_shared,
            )
        )
        _session_state_final_log.append_session_state_final_log(
            "router_pre_hydrate_shear_normalisation_done",
            {"shared_state_changed": _shear_norm_changed},
        )
        render_timing_mark("app.pre_dispatch.shear_normalisation.end", changed=_shear_norm_changed)
    except Exception:
        render_timing_mark("app.pre_dispatch.shear_normalisation.error")
        try:
            _session_state_final_log.append_session_state_final_log(
                "router_pre_hydrate_shear_normalisation_done",
                {"error": True},
            )
        except Exception:
            pass
    if st.session_state.get("_dev_mode") and st.session_state.get("_inputs_hydration_trace"):
        inputs_hydration_trace_log(
            "app_after_shear_norm",
            page_slug_preview=str(st.session_state.get("page_slug") or ""),
        )

    # --- 4) Regression tripwire: verify shared state is alive (AFTER init)
    render_timing_mark("app.pre_dispatch.shared_state_tripwires.start")
    assert_shared_state_alive()
    tripwire_no_falsy_defaulting()
    render_timing_mark("app.pre_dispatch.shared_state_tripwires.end")
    
    
    # Force-hydrate time widgets from shared BEFORE any page widgets render
    render_timing_mark("app.pre_dispatch.force_hydrate_time_widgets.start")
    from state_and_helpers import force_hydrate_time_widgets_from_shared
    st.session_state["_sync_lock"] = True
    try:
        force_hydrate_time_widgets_from_shared()
    finally:
        st.session_state["_sync_lock"] = False
    render_timing_mark("app.pre_dispatch.force_hydrate_time_widgets.end")
    
    # Clear user edit markers at start of each rerun (prevents stale exemptions)
    render_timing_mark("app.pre_dispatch.clear_user_edit_markers.start")
    clear_user_edit_marker_each_run()
    render_timing_mark("app.pre_dispatch.clear_user_edit_markers.end")

    # Dev contract: reset per-run Inputs hydration counter (see state_and_helpers._contract_single_hydration_pass)
    st.session_state["_contract_inputs_hydrate_invocations"] = 0

    # Step 2: Set current slug into session state (for hydration and tracking)
    render_timing_mark("app.pre_dispatch.set_page_slug.start", selected_slug=selected_slug)
    st.session_state["page_slug"] = selected_slug
    st.session_state["_active_page_slug"] = selected_slug  # Keep for backward compatibility
    if selected_slug != "start":
        st.session_state["_last_design_page_slug"] = selected_slug
    render_timing_mark("app.pre_dispatch.set_page_slug.end", selected_slug=selected_slug)
    
    
    # ============================================================
    # SHARED INPUT MUTATION GUARD (prevents pages from stomping shared inputs during render)
    # ============================================================
    # --- DEBUG/SAFETY: track shared INPUT mutations during render ---
    render_timing_mark("app.pre_dispatch.shared_input_guard_snapshot.start")
    shared_before = {k: st.session_state.get(k) for k in SHARED_DEFAULTS.keys()}
    last_ts = float(st.session_state.get("_last_user_edit_ts") or 0.0)
    last_shared = st.session_state.get("_last_user_shared_key")
    recent_user_edit = (time.time() - last_ts) < 0.5
    wipe_mode = bool(st.session_state.get("_wipe_recovery_mode"))
    render_timing_mark(
        "app.pre_dispatch.shared_input_guard_snapshot.end",
        shared_key_count=len(shared_before),
        recent_user_edit=recent_user_edit,
        wipe_mode=wipe_mode,
    )
    
    prev = st.session_state.get("_prev_page_slug")
    page_changed = (prev is not None and prev != selected_slug)
    st.session_state["_prev_page_slug"] = selected_slug
    try:
        _latency_metrics = dict(st.session_state.get("_user_latency_metrics") or {})
        _latency_metrics.update(
            {
                "selected_page_slug": selected_slug,
                "previous_page_slug": prev,
                "route_page_changed": bool(page_changed),
                "route_page_changed_at_ms": int(time.time() * 1000) if page_changed else None,
                "dev_mode": bool(st.session_state.get("_dev_mode", False)),
                "browser_test_mode": bool(_browser_test_mode_for_run),
            }
        )
        st.session_state["_user_latency_metrics"] = _latency_metrics
    except Exception:
        pass
    render_timing_mark("app.pre_dispatch.page_content_slot.create.start", page_changed=page_changed)
    page_content_slot = st.empty()
    if page_changed:
        with page_content_slot.container():
            st.info(f"Loading {PAGES[selected_slug][0]}...")
    render_timing_mark("app.pre_dispatch.page_content_slot.create.end", page_changed=page_changed)
    if page_changed and selected_slug == "inputs":
        st.session_state["_inputs_route_return_pending"] = {
            "previous_slug": str(prev or ""),
            "selected_slug": "inputs",
            "active_beam_id": st.session_state.get(
                "active_beam_id"
            ),
        }
        render_timing_mark(
            "app.pre_dispatch.page_transition_shell.direct_inputs_handoff",
            previous_slug=prev,
            selected_slug=selected_slug,
        )

    # Hydrate BEFORE any widgets render (prevents stale widget keys from clobbering shared).
    # Primary hydration owner for all pages including Inputs â€” render_inputs must not repeat this unconditionally.
    render_timing_mark("app.pre_dispatch.router_hydrate_log_start.start", selected_slug=selected_slug)
    try:
        _session_state_final_log.append_session_state_final_log(
            "router_hydrate_start",
            {
                "hydration_layer": "router",
                "selected_slug": selected_slug,
                "page_changed": page_changed,
                "pending_inputs_apply_refresh_present": bool(
                    st.session_state.get("_pending_inputs_apply_refresh"),
                ),
                "force_inputs_widget_reseed_once": bool(
                    st.session_state.get("_force_inputs_widget_reseed_once"),
                ),
            },
        )
    except Exception:
        pass
    render_timing_mark("app.pre_dispatch.router_hydrate_log_start.end", selected_slug=selected_slug)
    render_timing_mark("app.pre_dispatch.router_hydrate_active_page_widgets.start", selected_slug=selected_slug)
    st.session_state["_sync_lock"] = True
    try:
        with speed_profile_section("shared_state_hydration.hydrate_active_page_widgets_from_shared", category="state_mutation"):
            hydrate_active_page_widgets_from_shared(
                selected_slug,
                force_on_restore=True,
                # Returning to Inputs intentionally uses a shell rerun.  On
                # that second run ``page_changed`` is false, but the committed
                # transaction still has to reseed stale widget aliases before
                # Inputs widgets mount and callbacks can fire.
                force_on_page_change=(
                    page_changed or same_beam_inputs_route_return
                ),
            )
    finally:
        st.session_state["_sync_lock"] = False
    render_timing_mark("app.pre_dispatch.router_hydrate_active_page_widgets.end", selected_slug=selected_slug)
    if _browser_test_mode_for_run:
        router_probe = dict(st.session_state.get("_browser_router_probe") or {})
        router_probe["after_router_hydrate"] = {
            **_browser_action_probe("after_router_hydrate"),
            "page_changed": bool(page_changed),
            "same_beam_inputs_route_return": bool(same_beam_inputs_route_return),
            "pending_inputs_apply_refresh_present": bool(
                st.session_state.get("_pending_inputs_apply_refresh"),
            ),
            "force_inputs_widget_reseed_once": bool(
                st.session_state.get("_force_inputs_widget_reseed_once"),
            ),
        }
        st.session_state["_browser_router_probe"] = router_probe
    render_timing_mark("app.pre_dispatch.router_hydrate_log_done.start", selected_slug=selected_slug)
    try:
        _session_state_final_log.ssl_increment("router_hydrate_count", 1)
        _session_state_final_log.append_session_state_final_log(
            "router_hydrate_done",
            {
                "hydration_layer": "router",
                "selected_slug": selected_slug,
                "pending_inputs_apply_refresh_present": bool(
                    st.session_state.get("_pending_inputs_apply_refresh"),
                ),
                "force_inputs_widget_reseed_once": bool(
                    st.session_state.get("_force_inputs_widget_reseed_once"),
                ),
            },
        )
    except Exception:
        pass
    render_timing_mark("app.pre_dispatch.router_hydrate_log_done.end", selected_slug=selected_slug)
    if st.session_state.get("_dev_mode") and st.session_state.get("_inputs_hydration_trace"):
        inputs_hydration_trace_log(
            "router_hydrate_active_page",
            selected_slug=selected_slug,
            page_changed=page_changed,
        )

    # ============================================================
    # GLOBAL COMPUTE PIPELINE (runs BEFORE page render)
    # ============================================================
    # Heavy recompute runs only when the user clicks Run Design on Inputs, or when
    # inputs_dirty is set AND auto_recompute is enabled (opt-in).
    if "_computed_once" not in st.session_state:
        render_timing_mark("app.pre_dispatch.compute_defaults.initialise_computed_once")
        st.session_state["_computed_once"] = False

    if "run_design_clicked" not in st.session_state:
        st.session_state["run_design_clicked"] = False
    if "auto_recompute" not in st.session_state:
        st.session_state["auto_recompute"] = False
    if "results_version" not in st.session_state:
        st.session_state["results_version"] = 0
    if "inputs_dirty" not in st.session_state:
        st.session_state["inputs_dirty"] = False
    if "_inputs_dirty" not in st.session_state:
        st.session_state["_inputs_dirty"] = True
    if "_compute_in_progress" not in st.session_state:
        st.session_state["_compute_in_progress"] = False
    if "_solver_running" not in st.session_state:
        st.session_state["_solver_running"] = False
    if "_solver_result" not in st.session_state:
        st.session_state["_solver_result"] = None
    if "cached_results" not in st.session_state:
        st.session_state["cached_results"] = None
    if "_last_compute_fp" not in st.session_state:
        st.session_state["_last_compute_fp"] = None
    if "_cached_compute_results" not in st.session_state:
        st.session_state["_cached_compute_results"] = None

    def _cache_current_compute_results() -> None:
        result_values = {
            k: copy.deepcopy(st.session_state.get(k))
            for k in RESULT_KEYS
            if k in st.session_state
        }
        result_buckets = copy.deepcopy(st.session_state.get("results") or {})
        st.session_state["_cached_compute_results"] = {
            "result_values": result_values,
            "result_buckets": result_buckets,
        }
        st.session_state["cached_results"] = copy.deepcopy(result_buckets)

    def _publish_cached_compute_results() -> bool:
        cached = st.session_state.get("_cached_compute_results")
        if not isinstance(cached, dict):
            return False

        result_values = cached.get("result_values") or {}
        result_buckets = cached.get("result_buckets") or {}

        if result_values:
            update_results(**copy.deepcopy(result_values))
        for bucket_name, bucket_data in result_buckets.items():
            if isinstance(bucket_name, str) and isinstance(bucket_data, dict):
                update_results(bucket_name, copy.deepcopy(bucket_data))

        st.session_state["cached_results"] = copy.deepcopy(result_buckets)
        return True

    def run_full_compute() -> None:
        if st.session_state.get("_solver_running", False):
            return
        if st.session_state.get("_compute_in_progress", False):
            return

        st.session_state["_compute_in_progress"] = True
        try:
            recalc_derived_values()
            compute_all_results()
            update_results()
        finally:
            # Always clear even if compute raises.
            st.session_state["_compute_in_progress"] = False

    def _trace_structural_recompute_stage(stage: str, **extra) -> None:
        try:
            path = _local_trace_log_path("design_guide_tracer.jsonl")
            with open(path, "a", encoding="utf-8") as fh:
                fh.write(
                    json.dumps(
                        {
                            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime())
                            + f".{int((time.time() % 1) * 1000):03d}Z",
                            "event": "app_structural_recompute_stage",
                            "source": "app.pre_dispatch.structural_recompute",
                            "data": {
                                "stage": str(stage or "").strip(),
                                **dict(extra or {}),
                            },
                        },
                        default=str,
                        sort_keys=True,
                    )
                    + "\n"
                )
        except Exception:
            pass

    def _run_structural_recompute_and_cache() -> None:
        t0 = time.perf_counter()
        _trace_structural_recompute_stage("before_fingerprint")
        fp = _get_compute_fingerprint()
        t_fp = time.perf_counter()
        _trace_structural_recompute_stage("after_fingerprint")
        if st.session_state.get("_last_compute_fp") == fp:
            t1 = time.perf_counter()
            _trace_structural_recompute_stage("before_publish_cached_compute_results")
            cache_hit = _publish_cached_compute_results()
            t2 = time.perf_counter()
            _trace_structural_recompute_stage("after_publish_cached_compute_results", cache_hit=bool(cache_hit))
            st.session_state["_compute_debug"] = {
                "fingerprint_ms": round((t_fp - t0) * 1000, 2),
                "cache_update_ms": round((t2 - t1) * 1000, 2),
                "cache_hit": bool(cache_hit),
            }
            if cache_hit:
                st.session_state["_compute_time_ms"] = 0
                return

        t1 = time.perf_counter()
        _trace_structural_recompute_stage("before_resolve_design_actions")
        actions = resolve_design_actions(st.session_state)
        _trace_structural_recompute_stage(
            "after_resolve_design_actions",
            Mu=actions.get("Mu"),
            Vu=actions.get("Vu"),
        )
        _trace_structural_recompute_stage("before_update_results_actions")
        update_results(
            actions_source=str(actions.get("actions_source") or ""),
            Mu_star=float(actions["Mu"]),
            Mu_star_kNm=float(actions["Mu"]),
            Vu_star=float(actions["Vu"]),
        )
        _trace_structural_recompute_stage("after_update_results_actions")
        _trace_structural_recompute_stage("before_run_full_compute")
        run_full_compute()
        _trace_structural_recompute_stage("after_run_full_compute")
        t2 = time.perf_counter()
        st.session_state["_compute_time_ms"] = round((t2 - t1) * 1000, 2)
        try:
            from bending_core import compute_sigma_s_sls_for_crack

            _trace_structural_recompute_stage("before_compute_sigma_s_sls_for_crack")
            compute_sigma_s_sls_for_crack(publish=True)
            _trace_structural_recompute_stage("after_compute_sigma_s_sls_for_crack")
        except Exception:
            _trace_structural_recompute_stage("compute_sigma_s_sls_for_crack_error")
            pass
        _trace_structural_recompute_stage("before_cache_current_compute_results")
        _cache_current_compute_results()
        _trace_structural_recompute_stage("after_cache_current_compute_results")
        t3 = time.perf_counter()
        st.session_state["_compute_debug"] = {
            "fingerprint_ms": round((t_fp - t0) * 1000, 2),
            "compute_ms": round((t2 - t1) * 1000, 2),
            "update_ms": round((t3 - t2) * 1000, 2),
            "cache_hit": False,
        }
        st.session_state["_last_compute_fp"] = fp
        st.session_state["results_version"] = int(st.session_state.get("results_version", 0) or 0) + 1

    should_structural_recompute = (
        not bool(st.session_state.get("_inputs_same_beam_return_active"))
        and (
        bool(st.session_state.get("run_design_clicked")) or (
        bool(st.session_state.get("inputs_dirty") or st.session_state.get("_inputs_dirty"))
        and bool(st.session_state.get("auto_recompute"))
        )
        )
    )
    render_timing_mark(
        "app.pre_dispatch.structural_recompute.decision",
        should_structural_recompute=bool(should_structural_recompute),
        same_beam_inputs_return_active=bool(
            st.session_state.get("_inputs_same_beam_return_active")
        ),
        run_design_clicked=bool(st.session_state.get("run_design_clicked")),
        inputs_dirty=bool(st.session_state.get("inputs_dirty")),
        _inputs_dirty=bool(st.session_state.get("_inputs_dirty")),
        auto_recompute=bool(st.session_state.get("auto_recompute")),
    )

    if should_structural_recompute:
        render_timing_mark("app.pre_dispatch.structural_recompute.start")
        try:
            _session_state_final_log.append_session_state_final_log(
                "router_structural_recompute_start",
                {
                    "run_design_clicked": bool(st.session_state.get("run_design_clicked")),
                    "inputs_dirty": bool(st.session_state.get("inputs_dirty")),
                    "_inputs_dirty": bool(st.session_state.get("_inputs_dirty")),
                    "auto_recompute": bool(st.session_state.get("auto_recompute")),
                    "loads_edit_mode": st.session_state.get("loads_edit_mode"),
                    "uls_Mstar": st.session_state.get("uls_Mstar"),
                    "uls_Vstar": st.session_state.get("uls_Vstar"),
                },
            )
        except Exception:
            pass
        try:
            _run_structural_recompute_and_cache()
        except Exception:
            render_timing_mark("app.pre_dispatch.structural_recompute.error")
            pass
        finally:
            st.session_state["inputs_dirty"] = False
            st.session_state["_inputs_dirty"] = False
            st.session_state["run_design_clicked"] = False
            try:
                _session_state_final_log.append_session_state_final_log(
                    "router_structural_recompute_done",
                    {
                        "loads_edit_mode": st.session_state.get("loads_edit_mode"),
                        "uls_Mstar": st.session_state.get("uls_Mstar"),
                        "uls_Vstar": st.session_state.get("uls_Vstar"),
                        "results_version": st.session_state.get("results_version"),
                        "_compute_time_ms": st.session_state.get("_compute_time_ms"),
                    },
                )
            except Exception:
                pass
        st.session_state["_computed_once"] = True
        st.session_state["_dirty"] = False
        try:
            persist_active_beam_from_shared()
        except Exception:
            pass
        render_timing_mark(
            "app.pre_dispatch.structural_recompute.end",
            compute_time_ms=st.session_state.get("_compute_time_ms"),
            results_version=st.session_state.get("results_version"),
        )

    # Always republish cached results before rendering pages so summary/design-guide
    # consume the latest published RESULT_KEYS even on non-recompute reruns.
    render_timing_mark("app.pre_dispatch.publish_cached_compute_results.start")
    try:
        _publish_cached_compute_results()
    except Exception:
        render_timing_mark("app.pre_dispatch.publish_cached_compute_results.error")
        pass
    render_timing_mark("app.pre_dispatch.publish_cached_compute_results.end")

    render_timing_mark("app.pre_dispatch.compute_debug_sidebar.start")
    if st.session_state.get("_dev_mode"):
        if st.sidebar.checkbox("Show compute debug", value=False):
            st.sidebar.json(st.session_state.get("_compute_debug", {}))
    render_timing_mark("app.pre_dispatch.compute_debug_sidebar.end")

    # Step 4: Begin render cycle (ensures rendered widget tracking is per-run)
    from widgets_helpers import clear_rendered_widget_keys
    render_timing_mark("app.pre_dispatch.begin_render_cycle.start")
    clear_rendered_widget_keys()
    begin_render_cycle()
    render_timing_mark("app.pre_dispatch.begin_render_cycle.end")

    # Step 5: Render selected page (widgets register themselves during render)
    # Pages must NOT call init_shared_session_state() or hydrate themselves
    # (See state_and_helpers.py banner: "PAGE FILE RULES (router-owned lifecycle)")
    _page_dispatch_started_perf = time.perf_counter()
    st.session_state["_user_latency_page_dispatch_started_perf"] = _page_dispatch_started_perf
    same_page_inputs_root_shell = selected_slug == "inputs" and not page_changed

    def _render_inputs_root_dispatch_stable_shell() -> None:
        st.markdown(
            """
<div data-testid="inputs-root-dispatch-stable-shell"
     aria-hidden="true"
     style="height:0;min-height:0;margin:0;padding:0;overflow:hidden;opacity:0;pointer-events:none;user-select:none;">
  Inputs page stable rerun shell.
</div>
<style data-testid="inputs-root-dispatch-status-layout-guard">
  [data-testid="stStatusWidget"],
  [data-testid="stDecoration"] {
    position: fixed !important;
    top: 0 !important;
    right: 0 !important;
    width: auto !important;
    height: auto !important;
    min-height: 0 !important;
    margin: 0 !important;
    padding: 0 !important;
    z-index: 2147483000 !important;
  }
</style>
""",
            unsafe_allow_html=True,
        )

    def _render_selected_page_in_content_slot() -> None:
        def _render_page_beneath_shared_title() -> None:
            st.title(_active_page_title(selected_slug))
            st.markdown(
                '<span id="shared-page-content-anchor" aria-hidden="true"></span>',
                unsafe_allow_html=True,
            )
            st.session_state[SHARED_PAGE_TITLE_ACTIVE_KEY] = True
            try:
                PAGES[selected_slug][1]()
            finally:
                st.session_state.pop(SHARED_PAGE_TITLE_ACTIVE_KEY, None)

        if same_page_inputs_root_shell:
            render_timing_mark(
                "app.page_dispatch.inputs_root_stable_shell.start",
                selected_slug=selected_slug,
            )
            with page_content_slot.container():
                root_shell_slot = st.empty()
                with root_shell_slot.container():
                    _render_inputs_root_dispatch_stable_shell()
                st.session_state["_inputs_same_page_root_dispatch_active"] = {
                    "active": True,
                    "source": "app.same_page_inputs_root_shell",
                }
                try:
                    _render_page_beneath_shared_title()
                finally:
                    st.session_state.pop("_inputs_same_page_root_dispatch_active", None)
                    root_shell_slot.empty()
            render_timing_mark(
                "app.page_dispatch.inputs_root_stable_shell.end",
                selected_slug=selected_slug,
            )
            return
        render_timing_mark("app.page_dispatch.page_content_slot.clear.start", selected_slug=selected_slug)
        page_content_slot.empty()
        render_timing_mark("app.page_dispatch.page_content_slot.clear.end", selected_slug=selected_slug)
        with page_content_slot.container():
            _render_page_beneath_shared_title()

    if _browser_test_mode_for_run:
        _browser_probe_slot = st.empty()
        render_timing_mark("app.pre_dispatch.browser_probe_pre_page_render.start", selected_slug=selected_slug)
        _emit_browser_test_state(selected_slug, _browser_probe_slot, probe_phase="pre_page_render")
        render_timing_mark("app.pre_dispatch.browser_probe_pre_page_render.end", selected_slug=selected_slug)
        render_timing_mark("app.page_dispatch.start", selected_slug=selected_slug, browser_test_mode=True)
        try:
            _render_selected_page_in_content_slot()
        finally:
            render_timing_mark("app.page_dispatch.end", selected_slug=selected_slug, browser_test_mode=True)
            # Test-only probe publication must survive early Streamlit stops
            # during staged Inputs mounting; product UI logic is unchanged.
            _emit_browser_test_state(selected_slug, _browser_probe_slot, probe_phase="post_page_render")
    else:
        render_timing_mark("app.page_dispatch.start", selected_slug=selected_slug, browser_test_mode=False)
        try:
            _render_selected_page_in_content_slot()
        finally:
            render_timing_mark("app.page_dispatch.end", selected_slug=selected_slug, browser_test_mode=False)
            if _should_emit_browser_state_probe(selected_slug, "post_page_render"):
                _emit_browser_test_state(selected_slug, None, probe_phase="post_page_render")
    try:
        _latency_metrics = dict(st.session_state.get("_user_latency_metrics") or {})
        _latency_metrics.update(
            {
                "page_dispatch_total_ms": round(
                    (time.perf_counter() - _page_dispatch_started_perf) * 1000.0,
                    3,
                ),
                "page_dispatch_finished_at_ms": int(time.time() * 1000),
            }
        )
        st.session_state["_user_latency_metrics"] = _latency_metrics
    except Exception:
        pass
    end_of_render_cleanup()

    # Debug guard: verify design-mode actions stay in sync with SFD/BMD outputs
    if st.session_state.get("actions_mode", "manual") == "design":
        sfd_M = st.session_state.get("sfd_Mmax_abs_kNm")
        sfd_V = st.session_state.get("sfd_Vmax_abs_kN")
        mu = st.session_state.get("Mu_star")
        mu_kNm = st.session_state.get("Mu_star_kNm")
        vu = st.session_state.get("Vu_star")
        mismatch = {}
        if sfd_M is not None and mu is not None and abs(float(mu) - float(sfd_M)) > 1e-6:
            mismatch["Mu_star"] = {"expected": sfd_M, "actual": mu}
        if sfd_M is not None and mu_kNm is not None and abs(float(mu_kNm) - float(sfd_M)) > 1e-6:
            mismatch["Mu_star_kNm"] = {"expected": sfd_M, "actual": mu_kNm}
        if sfd_V is not None and vu is not None and abs(float(vu) - float(sfd_V)) > 1e-6:
            mismatch["Vu_star"] = {"expected": sfd_V, "actual": vu}
        st.session_state["_debug_design_actions_mismatch"] = mismatch
    
    # Immediately after render_fn(): detect shared-input changes
    shared_after = {k: st.session_state.get(k) for k in SHARED_DEFAULTS.keys()}
    
    changed_shared = {
        k: (shared_before.get(k), shared_after.get(k))
        for k in SHARED_DEFAULTS.keys()
        if shared_before.get(k) != shared_after.get(k)
    }

    # Show what changed (debug)
    st.session_state["_debug_changed_shared_inputs"] = changed_shared
    
    # Stricter guard: only allow shared-input changes if:
    # - wipe recovery mode, OR
    # - the change set is small (â‰¤ 2 keys), AND
    # - the changed key matches _last_user_shared_key, AND
    # - it happened very recently (< 0.5s)
    allowed_due_to_user = False
    touched_shared_keys_raw = st.session_state.get("_shared_keys_touched_this_run")
    touched_shared_keys = (
        {str(k) for k in touched_shared_keys_raw if str(k)}
        if isinstance(touched_shared_keys_raw, set)
        else set()
    )
    if recent_user_edit and last_shared:
        # Allow only the shared key the user actually edited (plus maybe one derived "paired" input)
        allowed_keys = {last_shared} | touched_shared_keys
        changed_keys = set(changed_shared.keys())
        if changed_keys.issubset(allowed_keys) and len(changed_keys) <= max(2, len(allowed_keys)):
            allowed_due_to_user = True
    allowed_due_to_design_guide_apply = False
    design_guide_apply_keys = st.session_state.get("_allow_design_guide_apply_shared_keys_once")
    if isinstance(design_guide_apply_keys, (list, tuple, set)):
        design_guide_allowed_keys = {str(k) for k in design_guide_apply_keys if str(k)}
        if design_guide_allowed_keys and (
            not changed_shared
            or set(changed_shared.keys()).issubset(design_guide_allowed_keys)
            or bool(st.session_state.get(inputs_page_app_contracts.DESIGN_GUIDE_LAST_APPLY_ROUTE_KEY))
        ):
            allowed_due_to_design_guide_apply = True

    allowed_due_to_design_model = False
    if selected_slug == "design" and changed_shared:
        design_support_keys = {"design_support_condition"} | {
            f"design_support_type_{idx}" for idx in range(1, 7)
        }
        design_load_result_keys = {
            "loads_edit_mode",
            "loads_edit_toggle",
            "w_sls_kNm_per_m",
            "w_uls_kNm_per_m",
            "P_sls_kN",
            "P_uls_kN",
        }
        design_allowed_keys = design_support_keys | design_load_result_keys | touched_shared_keys
        if set(changed_shared.keys()).issubset(design_allowed_keys):
            allowed_due_to_design_model = True
    
    # Block illegal render-time writes to shared INPUTS
    _shared_input_guard_reverted = bool(
        changed_shared
        and (not wipe_mode)
        and (not allowed_due_to_user)
        and (not allowed_due_to_design_guide_apply)
        and (not allowed_due_to_design_model)
    )
    if _shared_input_guard_reverted:
        # revert the illegal changes
        for k, (old, _new) in changed_shared.items():
            if k in TAB_KEYS:
                continue
            st.session_state[k] = old
        st.session_state["_debug_reverted_shared_inputs"] = changed_shared
        st.session_state["_debug_last_revert_tag"] = f"REVERTED {len(changed_shared)} keys on {selected_slug}"
        try:
            from state_and_helpers import _write_sync_trace_line
            _write_sync_trace_line(
                f"ROUTER_REVERT page={selected_slug} keys={list(changed_shared.keys())[:20]} count={len(changed_shared)}"
            )
        except Exception:
            pass
    if allowed_due_to_design_guide_apply or _shared_input_guard_reverted or (design_guide_apply_keys and not changed_shared):
        st.session_state.pop("_allow_design_guide_apply_shared_keys_once", None)

    # Tripwire: detect shared keys that got zeroed during render

    # Step 6: Persist snapshot after page render so future wipes can recover
    persist_state_snapshot(reset_manual_action_touch_latch=True)

    try:
        _session_state_final_log.append_shear_spacing_alignment_snapshot()
        _session_state_final_log.append_session_state_final_summary()
    except Exception:
        pass

    if st.session_state.get("_dev_mode"):
        from state_and_helpers import _contract_session_integrity

        _contract_session_integrity(dict(st.session_state))

    # IMPORTANT: Do NOT do app-level widgetâ†’shared syncing.
    # Shared state must only update via on_change callbacks.
    # App-level syncing can copy stale navigation zeros into shared and wipe inputs.
    
    # NOTE: compute_all_results() already handles derived + results updates.


if __name__ == "__main__":
    main()
