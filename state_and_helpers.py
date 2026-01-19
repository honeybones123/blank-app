import math
import uuid
import time
import json
import os
import inspect
import traceback
from pathlib import Path
from datetime import datetime
import streamlit as st

# ============================================================
#  SESSION STATE CONTRACT  (READ THIS BEFORE EDITING ANYTHING)
# ============================================================

# Debug output directory (for sync trace files)
DEBUG_OUT_DIR = Path(".")  # app root; same place your other audits are being written

# Global debug toggle
DEBUG_MODE = False  # set True only when debugging


def debug_print(*args, **kwargs):
    """Central debug logger. Use this instead of print()."""
    if DEBUG_MODE:
        print(*args, **kwargs)


def _debug_docs_dir() -> str:
    """User Documents folder (macOS-friendly)."""
    return os.path.expanduser("~/Documents")


def _debug_log_path() -> str:
    return os.path.join(_debug_docs_dir(), "blank_app_state_tripwire.log")


def _debug_snapshot_path() -> str:
    return os.path.join(_debug_docs_dir(), "blank_app_shared_snapshot.json")


def _append_debug_log(line: str) -> None:
    if not DEBUG_MODE:
        return
    try:
        path = _debug_log_path()
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(path, "a", encoding="utf-8") as f:
            f.write(f"[{ts}] {line}\n")
    except Exception:
        # Never break the app due to debug logging
        pass


def write_final_session_state_check(path: str = "final_session_state_check.json") -> str:
    """
    Writes a JSON snapshot to a visible location so it can be uploaded for debugging.
    Never raises (fails silently but tries hard).
    Returns the output path (best effort).
    """
    try:
        out_path = os.path.join(os.path.expanduser("~"), "Documents", path)
        ss = dict(st.session_state)

        payload = {
            "ts": time.time(),
            "active_slug": ss.get("page_slug") or ss.get("_active_page_slug"),
            "keys": sorted(list(ss.keys())),
            "shared_subset": {k: ss.get(k) for k in [
                "b", "D", "fc", "Ec", "L",
                "t_creep", "age_at_loading", "stress_ratio", "t_shrink", "shrinkage_env",
                "defl_limit_ratio", "defl_support_type", "defl_use_simplified_ief",
                "sigma_sr",
            ]},
            "rendered_widget_keys": ss.get("_rendered_widget_keys", []),
            "last_user_widget_key": ss.get("_last_user_widget_key"),
            "last_user_shared_key": ss.get("_last_user_shared_key"),
            "stray_prefixed_keys": [
                str(k) for k in ss.keys()
                if str(k).startswith(("defl_", "cr_", "sh_", "design_"))
            ],
            "blocked_sync_attempts": ss.get("_blocked_sync_attempts", [])[-50:],
        }

        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, default=str)

        return out_path
    except Exception:
        try:
            tb = traceback.format_exc()
            out_path = os.path.join(os.path.expanduser("~"), "Documents", "final_session_state_check.json")
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump({"error": "write_final_session_state_check_failed", "traceback": tb}, f, indent=2)
            return out_path
        except Exception:
            return ""


def mark_dirty(reason: str = ""):
    st.session_state["_dirty"] = True
    if reason:
        st.session_state["_dirty_reason"] = reason


WATCH_SHARED_KEYS = [
    "sfd_case",
    "defl_support_type",
    "crack_k1",
    "crack_member_type",
]


def _short_stack(skip: int = 0, limit: int = 8) -> list[str]:
    try:
        stack = traceback.format_stack()
        # Remove last frames in this helper + logger itself
        stack = stack[: -(2 + skip)] if len(stack) > (2 + skip) else stack
        return [ln.strip("\n") for ln in stack[-limit:]]
    except Exception:
        return []


def watch_shared_key_writes(tag: str = "", page: str | None = None) -> None:
    """
    Debug-only: detects changes in selected shared keys and logs stack trace.
    Does not block writes.
    """
    if not st.session_state.get("_debug_state_tripwire", False):
        return

    # Init last-values store
    if st.session_state.get("_debug_last_watch") is None:
        st.session_state["_debug_last_watch"] = {}

    last = st.session_state["_debug_last_watch"]
    for k in WATCH_SHARED_KEYS:
        cur = st.session_state.get(k, None)
        prev = last.get(k, None)

        # First time: just seed baseline
        if k not in last:
            last[k] = cur
            continue

        # Change detected
        if cur != prev:
            payload = {
                "event": "WATCH_CHANGE",
                "key": k,
                "from": prev,
                "to": cur,
                "tag": tag,
                "page": page or st.session_state.get("active_page", ""),
                "boot": st.session_state.get("_boot_id", ""),
                "stack": _short_stack(limit=10),
            }
            _append_debug_log(json.dumps(payload, default=str)[:8000])
            last[k] = cur


# These are normal internal keys in your app; do not treat as rogue.
ALLOWED_SESSION_PREFIXES = (
    "_",               # allow all private/internal keys
)

# Results / derived keys should NOT be treated as rogue.
# (You can add to this later if needed; keep minimal now.)
ALLOWED_EXPLICIT_NONCONTRACT_KEYS = {
    "results",
    "passes_table",
    "passes_w",
    "phi_Mu_cap",
    "phi_Vu_cap",
    "phi_Tu_cap",
    "deflection_total_mm",
    "deflection_limit_mm",
    "deflection_utilisation",
    # Load actions by module (derived wiring)
    "actions_bending",
    "actions_shear",
    "actions_crack",
    "actions_deflection",
    "actions_uls",
    "actions_sls",
    "crack_width",
    "crack_utilisation",
}
#
#  RULE 1 – SINGLE SOURCE OF TRUTH
#  --------------------------------
#  • All shared design values (geometry, materials, actions,
#    reo, covers, crack inputs, results) MUST be defined here
#    in SHARED_DEFAULTS.
#  • No other file is allowed to invent new shared keys like
#      st.session_state["b_new"] = ...
#    without first adding them to SHARED_DEFAULTS.
#
#  RULE 2 – WIDGET KEYS VS SHARED KEYS
#  -----------------------------------
#  • Pages use widget keys like "inputs_b", "bending_b",
#    "shear_b", "crack_b".
#  • Each widget key MUST be mapped to a shared key using TAB_KEYS:
#      TAB_KEYS["inputs_b"] = "b"
#  • Pages must NOT write directly to shared keys.
#    They only:
#      - define widgets with key="<page>_<name>"
#      - use on_change=sync_callbacks["<page>_<name>"]
#
#  RULE 3 – DERIVED VALUES
#  ------------------------
#  • Derived values (d, do, Ast_bot, Ast_top, etc.) are ONLY
#    recalculated inside recalc_derived_values().
#  • Pages must NEVER manually modify these, only read them via:
#        get_param("d"), get_param("Ast_bot"), etc.
#
#  RULE 4 – RESULTS / CAPACITIES
#  ------------------------------
#  • Bending, Shear, Crack pages must write design results using
#    update_results(), NOT raw st.session_state assignments.
#  • Allowed result keys are listed in RESULT_KEYS. If you try
#    to write anything else, update_results() raises an error.
#
#  RULE 5 – ADDING NEW SHARED THINGS
#  ----------------------------------
#  If you add a new shared quantity:
#    (1) Add default to SHARED_DEFAULTS.
#    (2) If it has widgets, add widget→shared mapping into TAB_KEYS.
#    (3) If it is derived, update recalc_derived_values().
#    (4) If it is a result, add to RESULT_KEYS and use update_results().
#
#  If any of these rules are broken, _validate_contract() will raise.
#
# ============================================================
#
# ============================================================
#
#  PAGE FILE RULES (router-owned lifecycle)
#  =======================================
#  IMPORTANT: app.py owns the lifecycle:
#    1) init_shared_session_state()
#    2) set st.session_state["page_slug"]
#    3) hydrate_active_page_widgets_from_shared(active_slug)
#    4) begin_render_cycle()
#    5) render page function
#    6) persist_state_snapshot()
#
#  Therefore, every page render function MUST:
#    1) NOT call init_shared_session_state() (router already did)
#    2) NOT call hydrate_active_page_widgets_from_shared() (router already did)
#    3) NEVER write directly to shared keys (b, D, fc, etc.)
#    4) Only update shared keys via on_change sync callbacks:
#         key="<page>_<name>"
#         on_change=sync_callbacks["<page>_<name>"]
#    5) Never clear query params globally
#
#  Example:
#      def render_mypage():
#          sync_callbacks = get_sync_callbacks()
#          st.number_input("b (mm)", key="bending_b", on_change=sync_callbacks["bending_b"])
#          # ... rest of page code ...
#
# ============================================================


# ============================================
# 1. SHARED DEFAULTS (session_state values)
# ============================================

def _audit(event: str, shared_key: str, widget_key: str = "", old=None, new=None, extra: dict | None = None):
    """Tiny audit trail for state writes (debug only)."""
    rec = {
        "ts_ms": int(time.time() * 1000),
        "event": event,
        "shared_key": shared_key,
        "widget_key": widget_key,
        "old": old,
        "new": new,
        "page_slug": st.session_state.get("page_slug"),
        "boot_id": st.session_state.get("_boot_id"),
        "wipe_mode": st.session_state.get("_wipe_recovery_mode"),
    }
    if extra:
        rec.update(extra)
    st.session_state["_audit_tail"] = (st.session_state.get("_audit_tail") or [])[-200:] + [rec]


def _coalesce_num(v, default: float) -> float:
    """Return default only if v is None (preserves 0)."""
    return default if v is None else float(v)

def _get_hydrated_map() -> dict:
    m = st.session_state.get("_hydrated_from_shared_map")
    if not isinstance(m, dict):
        m = {}
        st.session_state["_hydrated_from_shared_map"] = m
    return m

def safe_hydrate(widget_key: str, shared_key: str, value, *, force: bool = False) -> None:
    """Seed widget from shared using sticky hydration rules."""
    hydrated_map = _get_hydrated_map()

    if force:
        st.session_state[widget_key] = value
        hydrated_map[widget_key] = value
        return

    if widget_key not in st.session_state:
        st.session_state[widget_key] = value
        hydrated_map[widget_key] = value
        return

    last_h = hydrated_map.get(widget_key, "__NOHYDRATE__")
    cur = st.session_state.get(widget_key)
    if last_h != "__NOHYDRATE__" and cur == last_h:
        st.session_state[widget_key] = value
        hydrated_map[widget_key] = value
        return

    try:
        _write_sync_trace_line(
            f"SAFE_HYDRATE widget={widget_key} shared={shared_key}"
        )
    except Exception:
        pass


def _shared_zero_tripwire(tag: str, keys: list[str] | None = None):
    """
    Tripwire: detect when shared keys get zeroed (debug only).
    Stores result in st.session_state["_tripwire_last"] for display in sidebar.
    """
    keys = keys or [k for k in st.session_state.keys() if k in SHARED_DEFAULTS]
    # Count how many shared keys are now 0/None
    bad = []
    for k in keys:
        if k not in SHARED_DEFAULTS:
            continue
        v = st.session_state.get(k)
        if v is None:
            if k in ("top2_count", "bot2_count"):
                try:
                    _write_sync_trace_line(f"TRIPWIRE_ZERO key={k} val={v} tag={tag}")
                except Exception:
                    pass
            bad.append((k, v))
        elif isinstance(v, (int, float)) and float(v) == 0.0 and (not zero_allowed(k)):
            if k in ("top2_count", "bot2_count"):
                try:
                    _write_sync_trace_line(f"TRIPWIRE_ZERO key={k} val={v} tag={tag}")
                except Exception:
                    pass
            bad.append((k, v))
    st.session_state["_tripwire_last"] = {"tag": tag, "bad_count": len(bad), "sample": bad[:25]}

SHARED_DEFAULTS = {
    # Geometry
    "b": 400.0,     # beam width (mm)
    "D": 600.0,     # overall depth (mm)
    "L": 3000.0,    # span/effective length (mm)

    # Materials
    "fc": 40.0,     # MPa
    "fsy": 500.0,   # MPa
    "Ec": 30000.0,  # MPa
    "Es": 200000.0, # MPa
    "phi_bend": 0.85,  # ← strength reduction factor for bending

    # Shear & torsion strength reduction factors
    "phi_shear": 0.75,
    "phi_torsion": 0.75,

    # Actions (manual inputs - these are the user-controlled shared inputs)
    # NOTE: Mu_star/Mu_star_kNm/Vu_star are RESULTS (computed outputs), not shared inputs.
    # They are written by update_results() and should NOT be in SHARED_DEFAULTS.

    # Manual copies – start equal to the same seeds so manual mode
    # behaves identically until the user edits the inputs.
    "Mu_star_manual": 500.0,  # kNm (legacy ULS manual)
    "Vu_star_manual": 300.0,  # kN (legacy ULS manual)
    "Tu_star": 0.0,    # kNm
    "P_star": 0.0,     # kN (prestress or axial in bending/shear)
    "N_star": 0.0,     # kN (legacy ULS axial)
    "actions_source": "Manual design actions (inputs below)",  # Source of design actions

    # --- Load inputs (store both ULS and SLS separately) ---
    "uls_Mstar": 500.0,
    "uls_Vstar": 300.0,
    "uls_Nstar": 0.0,

    "sls_Mstar": 500.0,
    "sls_Vstar": 300.0,
    "sls_Nstar": 0.0,

    # Which set the Inputs-page load widgets are currently editing
    "loads_edit_mode": "ULS",  # "ULS" or "SLS"
    "loads_edit_toggle": False,  # False=ULS, True=SLS

    # Proxies used ONLY by the widgets (never used by calculations)
    "load_Mstar_proxy": 500.0,
    "load_Vstar_proxy": 300.0,
    "load_Nstar_proxy": 0.0,

    # Longitudinal reinforcement - 2-layer system
    # Bottom Layer 1
    "nb_or_s_bot_1": 4.0,   # bars or spacing (≤30 = bars, ≥30 = spacing in mm)
    "db_bot_1": 20.0,       # mm
    # Bottom Layer 2
    "nb_or_s_bot_2": 0.0,   # bars or spacing (≤30 = bars, ≥30 = spacing in mm)
    "db_bot_2": 20.0,       # mm
    "rowgap_bot": 60.0,     # vertical gap between bottom rows (mm)
    
    # Top Layer 1
    "nb_or_s_top_1": 2.0,   # bars or spacing (≤30 = bars, ≥30 = spacing in mm)
    "db_top_1": 16.0,       # mm
    # Top Layer 2
    "nb_or_s_top_2": 0.0,   # bars or spacing (≤30 = bars, ≥30 = spacing in mm)
    "db_top_2": 16.0,       # mm
    "rowgap_top": 60.0,     # vertical gap between top rows (mm)
    
    # Legacy parameters (derived from layers, kept for backward compatibility)
    "nb_bot": 4,            # bottom bars (derived)
    "db_bot": 20.0,         # mm (derived from layer 1)
    "nb_top": 2,            # top bars (derived)
    "db_top": 16.0,         # mm (derived from layer 1)
    
    # Legacy "bars or spacing" entries (kept for migration)
    "bot_entry": 4.0,       # bottom layer: 4 bars by default (maps to nb_or_s_bot_1)
    "top_entry": 2.0,       # top layer: 2 bars by default (maps to nb_or_s_top_1)
    
    # Optional derived spacing (you can store these here or in a derived dict)
    "s_bot": 200.0,         # effective bottom spacing (mm)
    "s_top": 200.0,         # effective top spacing (mm)

    # Cover (including side cover shared values)
    "cover_bot": 40.0,
    "cover_top": 40.0,
    "side_cover_bot": 40.0,
    "side_cover_top": 40.0,
    "cover_side": 40.0,  # Geometry – side cover (to centroid or clear, whichever convention you use)

    # Duct inputs (prestress / voids)
    "n_ducts": 0.0,     # number of ducts crossing the web
    "duct_dia": 0.0,    # nominal duct diameter (mm)

    # Shear section parameters (AS 3600)
    "d_g": 20.0,          # maximum aggregate size (mm)
    "k_d_option": "None (no ducts in web)",  # dropdown string
    "k_v_method": "General εx-based (Cl. 8.2.4.2)",  # dropdown string

    # --- Time-dependent inputs (realistic defaults) ---
    "t_creep": 365,          # days after loading
    "age_at_loading": 28,    # days
    "stress_ratio": 0.20,    # σo / f'c,mi
    "t_shrink": 365,         # days since drying

    # Bottom layer 1 (explicit layout mode)
    "bot1_layout_mode": "Count",
    "bot1_count": 4,
    "bot1_spacing": 200,

    # Bottom layer 2 (explicit layout mode)
    "bot2_layout_mode": "Count",
    "bot2_count": 0,
    "bot2_spacing": 200,

    # Top layer 1 (explicit layout mode)
    "top1_layout_mode": "Count",
    "top1_count": 2,
    "top1_spacing": 200,

    # Top layer 2 (explicit layout mode)
    "top2_layout_mode": "Count",
    "top2_count": 0,
    "top2_spacing": 200,

    # Shear reinforcement
    "lig_d": 10.0,     # lig/stirrup diameter (mm)
    "lig_legs": 2,     # legs per stirrup
    "s_lig": 200.0,    # spacing (mm)

    # Crack control inputs
    "exposure_class": "B1",
    "s_bar_bot": 200.0,  # bottom bar spacing for crack calc (mm)
    
    # Crack criteria (inputs)
    "wmax_char_limit": 0.3,                 # mm (user-selected limit)
    "crack_member_type": "Primarily flexure",
    "crack_k1": 0.8,                        # deformed bars
    "crack_k2": 0.5,                        # default for flexure

    # Crack / torsion sketch control
    "crack_theta_deg": 45.0,  # physical crack angle (degrees)

    # Derived (will be recalculated; set initial values)
    "d": 600.0 - 40.0 - 20.0 / 2.0,
    "do": 600.0 - 40.0 - 16.0 / 2.0,
    "Ast_bot": 4 * math.pi * 20.0**2 / 4.0,
    "Ast_top": 2 * math.pi * 16.0**2 / 4.0,

    # Deflection page inputs (never None — None causes Streamlit widget + calc crashes)
    "defl_beff": 400.0,   # mm
    "defl_bw": 400.0,     # mm (derived from b; no direct widget)
    "defl_L_eff": 3.0,    # m  (default from L=3000mm)
    "defl_support_type": "Simply supported",  # Support condition for k₂ coefficient
    "defl_limit_ratio": 250.0,  # Deflection limit ratio (L/Δ, e.g. 250 for L/250)
    "defl_Fdef": 12.0,  # Effective design load (kN/m) for span/depth check
    "defl_use_simplified_ief": True,  # Use simplified I_ef calculation (checkbox)
    
    # Shrinkage page inputs
    "member_faces_exposed": "Beam – three faces exposed",  # Member / faces exposed for shrinkage
    "shrinkage_env": "Temperate inland environment",  # Shrinkage environment (Table 3.1.7.2)
    
    # Creep page inputs
    "env_option": "Temperate inland environment",  # Creep environment (Tables 3.1.8.2 & 3.1.8.3)
    
    # Unified beam loading (single source of truth on SFD/BMD page)
    # Note: load_case is a widget key (st.selectbox), so it's managed by Streamlit, not stored here
    "span_L_m": 6.0,  # Span length (m) - default must be >= 0.1 for widget constraint
    
    # UDL loads
    "g_udl_kNm_per_m": 8.0,  # Dead UDL (kN/m)
    "q_udl_kNm_per_m": 4.0,  # Live UDL (kN/m)
    "psi_udl": 0.4,  # Sustained factor for UDL
    "w_sls_kNm_per_m": 9.6,  # SLS UDL: g + psi_s * q (kN/m)
    "w_uls_kNm_per_m": 13.2,  # ULS UDL: γ_G * g + γ_Q * q (kN/m)
    
    # Point loads
    "G_point_kN": 50.0,  # Dead point load (kN)
    "Q_point_kN": 30.0,  # Live point load (kN)
    "psi_point": 0.4,  # Sustained factor for point load
    "P_sls_kN": 62.0,  # SLS point load: G + psi_s * Q (kN)
    "P_uls_kN": 105.0,  # ULS point load: γ_G * G + γ_Q * Q (kN)
    "a_m": 0.0,  # Distance a from left support for point loads (m) - user input, 0 is valid
    
    # SFD/BMD inputs (kept as inputs, not results)
    "sfd_span_L_m": 6.0,  # Span length for SFD/deflection pages (m)
    "sfd_case": "Simple beam – UDL over entire span",  # Current teaching case
}

# UI-only session state defaults (not shared, not synced)
UI_STATE_DEFAULTS = {
    "_reo_msg_top_auto_layer2": "",
    "_reo_msg_top_layer2_overwritten": "",
    "_reo_error_top_1": "",
    "_reo_warning_top_1": "",
    "_reo_s_min_top_1": "",
}


def _active_load_prefix() -> str:
    mode = st.session_state.get("loads_edit_mode", "ULS")
    return "uls" if mode == "ULS" else "sls"


def load_proxies_from_active_set():
    p = _active_load_prefix()
    st.session_state["load_Nstar_proxy"] = float(st.session_state.get(f"{p}_Nstar", 0.0) or 0.0)
    st.session_state["load_Vstar_proxy"] = float(st.session_state.get(f"{p}_Vstar", 0.0) or 0.0)
    st.session_state["load_Mstar_proxy"] = float(st.session_state.get(f"{p}_Mstar", 0.0) or 0.0)


def save_proxies_to_active_set():
    p = _active_load_prefix()
    other = "sls" if p == "uls" else "uls"
    before_other = (
        st.session_state.get(f"{other}_Nstar"),
        st.session_state.get(f"{other}_Vstar"),
        st.session_state.get(f"{other}_Mstar"),
    )

    st.session_state[f"{p}_Nstar"] = float(st.session_state.get("load_Nstar_proxy", 0.0) or 0.0)
    st.session_state[f"{p}_Vstar"] = float(st.session_state.get("load_Vstar_proxy", 0.0) or 0.0)
    st.session_state[f"{p}_Mstar"] = float(st.session_state.get("load_Mstar_proxy", 0.0) or 0.0)

    after_other = (
        st.session_state.get(f"{other}_Nstar"),
        st.session_state.get(f"{other}_Vstar"),
        st.session_state.get(f"{other}_Mstar"),
    )

    if before_other != after_other:
        debug_print("[TRIPWIRE] Cross-write detected! save_proxies_to_active_set modified BOTH ULS and SLS.")


def _allowed_shared_keys() -> set[str]:
    return set(SHARED_DEFAULTS.keys())


def _allowed_widget_keys() -> set[str]:
    # TAB_KEYS maps widget_key -> shared_key
    return set(TAB_KEYS.keys())


def _allowed_ui_keys() -> set[str]:
    try:
        return set(UI_STATE_DEFAULTS.keys())
    except Exception:
        return set()


def allowed_session_state_keys() -> set[str]:
    # Keys we consider "contract-approved"
    return _allowed_shared_keys() | _allowed_widget_keys() | _allowed_ui_keys()


def audit_session_state_keys(tag: str = "", page: str | None = None) -> dict:
    """
    Debug tripwire: detect rogue keys and likely collisions.
    Does NOT raise; returns dict and optionally logs.
    """
    allowed = allowed_session_state_keys()
    current = set(st.session_state.keys())

    def _is_allowed_noncontract_key(k: str) -> bool:
        if k in ALLOWED_EXPLICIT_NONCONTRACT_KEYS:
            return True
        return any(k.startswith(p) for p in ALLOWED_SESSION_PREFIXES)

    rogue = sorted(
        k for k in current
        if (k not in allowed)
        and (not _is_allowed_noncontract_key(k))
    )

    # Widget/shared collision risk: any widget key equals a shared key
    shared = _allowed_shared_keys()
    widget = _allowed_widget_keys()
    collisions = sorted(shared.intersection(widget))

    info = {
        "tag": tag,
        "page": page or st.session_state.get("active_page", ""),
        "rogue_count": len(rogue),
        "rogue_keys": rogue[:50],
        "collisions_count": len(collisions),
        "collisions": collisions[:50],
    }
    return info


def _shared_state_payload() -> dict:
    """Return current shared state values only (safe serializable snapshot)."""
    payload = {}
    for k in SHARED_DEFAULTS.keys():
        payload[k] = st.session_state.get(k, None)
    return payload


def snapshot_shared_state(tag: str = "", page: str | None = None) -> dict:
    """
    Capture SHARED_DEFAULTS values into a snapshot file.
    Returns snapshot dict.
    """
    snap = {
        "tag": tag,
        "page": page or st.session_state.get("active_page", ""),
        "t": time.time(),
        "shared": _shared_state_payload(),
    }
    try:
        with open(_debug_snapshot_path(), "w", encoding="utf-8") as f:
            json.dump(snap, f, indent=2, default=str)
    except Exception:
        pass
    return snap


def diff_shared_state(prev: dict | None, curr: dict | None) -> list[dict]:
    """
    Compare two snapshots and return list of changes for shared keys.
    """
    if not prev or not curr:
        return []
    prev_shared = prev.get("shared", {}) if isinstance(prev, dict) else {}
    curr_shared = curr.get("shared", {}) if isinstance(curr, dict) else {}

    changes = []
    for k in SHARED_DEFAULTS.keys():
        a = prev_shared.get(k, None)
        b = curr_shared.get(k, None)
        if a != b:
            changes.append({"key": k, "from": a, "to": b})
    return changes


def load_last_snapshot() -> dict | None:
    try:
        with open(_debug_snapshot_path(), "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def debug_tripwire_hook(tag: str = "", page: str | None = None) -> None:
    """
    Debug hook: log only SHARED changes + DEFAULT resets.
    Writes to ~/Documents/blank_app_state_tripwire.log and snapshot json.
    """
    if not st.session_state.get("_debug_state_tripwire", False):
        return

    try:
        prev = load_last_snapshot()

        curr = {
            "tag": tag,
            "page": page or st.session_state.get("page_slug", st.session_state.get("active_page", "")),
            "t": time.time(),
            "shared": _shared_state_payload(),
        }

        changes = diff_shared_state(prev, curr)

        # Log all shared changes (optional but useful)
        if changes:
            _append_debug_log(
                f"SHARED_CHANGED tag={tag} page={curr.get('page','')} changes={json.dumps(changes, default=str)[:5000]}"
            )

        # Log default resets ONLY (this is the key signal)
        default_resets = []
        for ch in changes:
            k = ch["key"]
            default = SHARED_DEFAULTS.get(k, None)
            if default is not None and ch["to"] == default and ch["from"] != default:
                default_resets.append({"key": k, "from": ch["from"], "to": ch["to"], "default": default})

            if default_resets and st.session_state.get("_wipe_recovery_mode", False):
                _append_debug_log(
                    f"DEFAULT_RESET tag={tag} page={curr.get('page','')} resets={json.dumps(default_resets, default=str)[:5000]}"
                )

        # Update snapshot for next run
        try:
            with open(_debug_snapshot_path(), "w", encoding="utf-8") as f:
                json.dump(curr, f, indent=2, default=str)
        except Exception:
            pass

    except Exception:
        _append_debug_log("TRIPWIRE_EXCEPTION " + traceback.format_exc())

# Explicit set of result keys (for RULE 4 checks)
RESULT_KEYS = {
    "phi_Mu_cap",
    "Mu_utilisation",
    "phi_Vu_cap",
    "Vu_utilisation",
    "phi_Tu_cap",
    "Tu_utilisation",
    "crack_width",
    "crack_utilisation",
    # Shrinkage
    "eps_cs_total",
    "eps_cs_total_micro",
    "eps_cse",
    "eps_csd_t",
    "th_shrinkage",
    "k1_shrinkage",
    # Creep
    "phi_cc_t",
    "phi_cc_star_table",
    "k2_creep",
    "k3_creep",
    "k4_creep",
    "k5_creep",
    "k6_creep",
    # Crack control summary
    "sigma_sr",
    "sigma_allow_table",
    "w_calc",
    "wmax_char",
    "passes_table",
    "passes_w",
    # Bending SLS → crack link
    "sigma_s_sls",
    # SFD/BMD computed results
    "sfd_Msls_max_kNm",
    "sfd_Vsls_max_kN",
    "sfd_Mmax_abs_kNm",
    "sfd_Vmax_abs_kN",
    "sfd_span_L_m",  # Span length for SFD/deflection pages (m)
    "sfd_case",  # Current teaching case (string)
    # SFD/BMD loading results (computed from UDL inputs)
    "g_udl_kNm_per_m",
    "q_udl_kNm_per_m",
    "psi_udl",
    "w_sls_kNm_per_m",
    "w_uls_kNm_per_m",
    # SFD/BMD point load results (computed from point load inputs)
    "G_point_kN",
    "Q_point_kN",
    "psi_point",
    "P_sls_kN",
    "P_uls_kN",
    # Deflection computed results
    "deflection_total_mm",
    "deflection_limit_mm",
    "deflection_utilisation",
    # Load actions by module (derived wiring)
    "actions_bending",
    "actions_shear",
    "actions_crack",
    "actions_deflection",
    # Other computed results
    "Vu_max_kN",
    "phi_Vu_max_kN",
    "V_eq_kN",
    "Vuc_utilisation",
    # Selected / final design actions (chosen from manual or SFD/BMD page)
    "actions_source",
    "Mu_star",
    "Mu_star_kNm",
    "Vu_star",
    # Bending min requirements / neutral axis checks
    "Mx_min_req",
    "As_min_req",
    "k_u",
    "k_u_lim",
    # Duct totals (computed from n_ducts + duct_dia)
    "A_duct_total",
    "sum_duct",
    # SFD/BMD span length (computed result)
    "span_L_m",
    # Deflection: computed effective design load (from V, L, support type)
    "fd_ef_calc_kNm",
}

# ---- REQUIRED RESULT KEYS (actions selection) ----
# These are derived outputs written via update_results() from Inputs/Bending.
_RESULT_KEYS_REQUIRED = {
    "actions_source",
    "Mu_star",
    "Mu_star_kNm",
    "Vu_star",
}
RESULT_KEYS |= _RESULT_KEYS_REQUIRED

# Safety check (fail fast if something later overwrites RESULT_KEYS)
_missing = _RESULT_KEYS_REQUIRED - RESULT_KEYS
if _missing:
    raise KeyError(f"[SESSION STATE CONTRACT] RESULT_KEYS missing required keys: {_missing}")

# Defaults for derived outputs (results). These are NOT user inputs.
RESULT_DEFAULTS = {k: 0.0 for k in RESULT_KEYS}
# If any results are non-numeric, set them explicitly:
RESULT_DEFAULTS.update({
    "passes_table": False,
    "passes_w": False,
    "Vuc_utilisation": None,  # Can be None
    # Action result keys
    "actions_source": "",
    "Mu_star": 0.0,
    "Mu_star_kNm": 0.0,
    "Vu_star": 0.0,
    # Load actions by module (derived wiring)
    "actions_bending": {},
    "actions_shear": {},
    "actions_crack": {},
    "actions_deflection": {},
    # SFD/BMD result keys
    "sfd_case": "",  # Current teaching case (string)
    "sfd_span_L_m": 0.0,  # Span length for SFD/deflection pages (m)
    # Bending min requirements / neutral axis checks
    "Mx_min_req": 0.0,
    "As_min_req": 0.0,
    "k_u": 0.0,
    "k_u_lim": 0.0,
    # Duct totals (computed from n_ducts + duct_dia)
    "A_duct_total": 0.0,
    "sum_duct": 0.0,
    # SFD/BMD span length (computed result)
    "span_L_m": 0.0,
    # Deflection: computed effective design load
    "fd_ef_calc_kNm": 0.0,
})

# Explicit set of derived keys (for RULE 3 checks and debug guards)
# These are keys written ONLY inside recalc_derived_values()
DERIVED_KEYS = {
    "d", "do",
    "Ast_bot", "Ast_top",
    "nb_bot", "nb_top",
    "db_bot", "db_top",
    "s_bot", "s_top",
    "bot_entry", "top_entry",
    "t_creep", "age_at_loading", "stress_ratio", "t_shrink",
    # Layer 2 keys (may be auto-updated by recalc_derived_values)
    "nb_or_s_bot_2", "db_bot_2",
    "nb_or_s_top_2", "db_top_2",
}

# Keys that are logically required to be > 0 and must NOT be overwritten by stale widget zeros.
# IMPORTANT: Reinforcement COUNTS/SPACINGS CAN be 0 (e.g. top layer absent), so they must NOT live here.
# NOTE: Do NOT add reinforcement COUNT/OPTIONAL keys (e.g. nb_or_s_*) to stale-zero protection.
# 0 is a valid design state for these keys. Use ZERO_ALLOWED_SHARED_KEYS instead.
NONZERO_REQUIRED_SHARED_KEYS = {
    # Geometry (cannot be 0)
    "b", "D", "L",

    # Materials (cannot be 0)
    "fc", "fsy", "Ec", "Es",

    # Covers (cannot be 0)
    "cover_bot", "cover_top", "cover_side",
    "side_cover_bot", "side_cover_top",
    
    # Reinforcement spacings / layout inputs (must not be clobbered to 0)
    "s_bar_bot",
    "s_bar_top",
    "s_lig",
    "rowgap_bot",
    "rowgap_top",

    # Time inputs (must not be clobbered to 0)
    "t_creep",
    "t_shrink",
    "age_at_loading",
    
    # NOTE: Reinforcement keys (bar diameters, counts, legs) are NOT in this set
    # because 0 is a valid user intent (e.g., no layer, no shear links).
    # Use zero_allowed() to check if 0 is allowed for a given key.
}

# Keys where 0 is a legitimate user input (must NOT be treated as missing/stale/corrupt)
ZERO_ALLOWED_SHARED_KEYS = {
    "nb_or_s_bot_1", "nb_or_s_bot_2",
    "nb_or_s_top_1", "nb_or_s_top_2",
    # Explicit layout-mode count inputs (0 is valid = layer disabled)
    "bot1_count", "bot2_count",
    "top1_count", "top2_count",
    # Manual design actions can be legitimately 0
    "Mu_star_manual",
    "Vu_star_manual",
}

def zero_allowed(shared_key: str) -> bool:
    """Keys where 0 is a legitimate user value (e.g. no layer, no shear links)."""
    # Explicit allow-list
    if shared_key in ZERO_ALLOWED_SHARED_KEYS:
        return True

    # Point load distance can be 0 (load at support)
    if shared_key == "a_m":
        return True

    k = shared_key.lower()

    # Reinforcement diameter / detailing keys can be 0 (meaning "not used")
    if k.startswith("db_") or k.startswith("lig_"):
        return True
    
    # Also include diameter patterns if they exist in naming
    if k.startswith("d_") or "diam" in k or k.endswith("_dia"):
        return True
    
    # Explicitly allow the three keys shown in tripwire (safety check)
    if shared_key in {"db_top_2", "db_bot_2", "lig_d"}:
        return True

    # Reinforcement patterns where 0 is legitimately "not used"
    # NOTE: DO NOT blanket-allow s_* (spacing keys like s_bar_bot must not become 0 by accident)
    if any(k.startswith(p) for p in ("nb_", "n_", "as_", "ast_", "top_", "bot_", "bottom_")):
        return True

    # Token-based allow. Exclude "spacing" to avoid allowing s_bar_bot/s_lig etc.
    if any(token in k for token in ("reo", "link", "leg", "layer", "stirrup", "bar", "dia", "diam")):
        return True

    # Actions: loads can be 0
    if k.endswith("_star") or k in ("p_star", "n_star", "tu_star", "mu_star", "vu_star"):
        return True

    # NOTE: rowgap_bot and rowgap_top are in NONZERO_REQUIRED_SHARED_KEYS, so they are NOT zero_allowed
    # (removed the rowgap_* check to prevent conflict)

    return False

# Aliases for backward compatibility
ALLOW_ZERO_SHARED_KEYS = ZERO_ALLOWED_SHARED_KEYS
ZERO_VALID_SHARED_KEYS = ZERO_ALLOWED_SHARED_KEYS


def validate_session_state_contract(context: str = "") -> None:
    """
    Debug-only validator for session-state contract.
    Raises fast with a clear message (prevents silent drift).
    Does not modify UI/diagrams.
    """
    import streamlit as st

    missing_shared = [k for k in SHARED_DEFAULTS.keys() if k not in st.session_state]
    if missing_shared:
        raise RuntimeError(
            f"[SessionStateContract] Missing shared keys ({context}): {missing_shared}"
        )

    # Ensure every widget key in TAB_KEYS exists (so sync can safely operate)
    missing_widget_keys = []
    for widget_key, shared_key in TAB_KEYS.items():
        if widget_key not in st.session_state:
            missing_widget_keys.append((widget_key, shared_key))

    if missing_widget_keys:
        # Keep message compact but actionable
        preview = missing_widget_keys[:10]
        raise RuntimeError(
            "[SessionStateContract] Missing widget keys ({ctx}). "
            "Example missing (widget_key, shared_key): {preview} "
            "(first 10 shown; ensure init_shared_session_state initializes TAB_KEYS widget keys)."
            .format(ctx=context, preview=preview)
        )

    # Optional: sanity check for None where defaults exist (None often causes cascades)
    none_shared = [k for k, v in SHARED_DEFAULTS.items() if st.session_state.get(k) is None and v is not None]
    if none_shared:
        raise RuntimeError(
            f"[SessionStateContract] Shared keys became None unexpectedly ({context}): {none_shared}"
        )

# =====================================================
# 2. MAPPING: widget keys → shared session_state keys
# =====================================================

TAB_KEYS = {
    # ----------------- INPUTS PAGE -----------------
    "inputs_b": "b",
    "inputs_D": "D",
    "inputs_L": "L",

    "inputs_fc": "fc",
    "inputs_fsy": "fsy",
    "inputs_Ec": "Ec",
    "inputs_Es": "Es",

    "inputs_Mu_star": "Mu_star_manual",
    "inputs_Vu_star": "Vu_star_manual",
    "inputs_Tu_star": "Tu_star",
    "inputs_P_star": "P_star",
    "inputs_N_star": "N_star",
    "inputs_load_Mstar_proxy": "load_Mstar_proxy",
    "inputs_load_Vstar_proxy": "load_Vstar_proxy",
    "inputs_load_Nstar_proxy": "load_Nstar_proxy",
    "inputs_loads_edit_mode": "loads_edit_mode",
    "inputs_loads_edit_toggle": "loads_edit_toggle",

    # ----------------- ACTIONS ALIASES (V* vs Vu*, T* vs Tu*) -----------------
    # Treat any page's alternate naming as the same underlying shared parameters.
    "inputs_V_star": "Vu_star_manual",
    "shear_V_star": "load_Vstar_proxy",
    "shear_Vu_star": "load_Vstar_proxy",
    "actions_V_star": "Vu_star_manual",
    "actions_Vu_star": "Vu_star_manual",

    "inputs_T_star": "Tu_star",
    "shear_T_star": "Tu_star",
    "shear_Tu_star": "Tu_star",
    "actions_T_star": "Tu_star",
    "actions_Tu_star": "Tu_star",

    "shear_N_star": "N_star",
    "actions_N_star": "N_star",

    "shear_P_star": "P_star",
    "actions_P_star": "P_star",

    # strength reduction factors commonly edited near action inputs
    "shear_phi_shear": "phi_shear",
    "actions_phi_shear": "phi_shear",
    "shear_phi_torsion": "phi_torsion",
    "actions_phi_torsion": "phi_torsion",

    "inputs_rowgap_bot": "rowgap_bot",
    "inputs_rowgap_top": "rowgap_top",

    "inputs_cover_bot": "cover_bot",
    "inputs_cover_top": "cover_top",
    "inputs_side_cover_bot": "side_cover_bot",
    "inputs_side_cover_top": "side_cover_top",
    "inputs_cover_side": "cover_side",  # Geometry – side cover (now a proper shared param)

    # Reo: 2-layer bars/spacing entries
    "inputs_nb_or_s_bot_1": "nb_or_s_bot_1",
    "inputs_db_bot_1": "db_bot_1",
    "inputs_nb_or_s_bot_2": "nb_or_s_bot_2",
    "inputs_db_bot_2": "db_bot_2",
    "inputs_nb_or_s_top_1": "nb_or_s_top_1",
    "inputs_db_top_1": "db_top_1",
    "inputs_nb_or_s_top_2": "nb_or_s_top_2",
    "inputs_db_top_2": "db_top_2",
    
    # Bottom layer 1 (explicit layout mode)
    "inputs_bot1_layout_mode": "bot1_layout_mode",
    "inputs_bot1_count": "bot1_count",
    "inputs_bot1_spacing": "bot1_spacing",
    
    # Bottom layer 2 (explicit layout mode)
    "inputs_bot2_layout_mode": "bot2_layout_mode",
    "inputs_bot2_count": "bot2_count",
    "inputs_bot2_spacing": "bot2_spacing",
    
    # Top layer 1 (explicit layout mode)
    "inputs_top1_layout_mode": "top1_layout_mode",
    "inputs_top1_count": "top1_count",
    "inputs_top1_spacing": "top1_spacing",
    
    # Top layer 2 (explicit layout mode)
    "inputs_top2_layout_mode": "top2_layout_mode",
    "inputs_top2_count": "top2_count",
    "inputs_top2_spacing": "top2_spacing",
    # Bending page widgets - map to same shared parameters
    "bending_nb_or_s_bot_1": "nb_or_s_bot_1",
    "bending_db_bot_1": "db_bot_1",
    "bending_nb_or_s_bot_2": "nb_or_s_bot_2",
    "bending_db_bot_2": "db_bot_2",
    "bending_nb_or_s_top_1": "nb_or_s_top_1",
    "bending_db_top_1": "db_top_1",
    "bending_nb_or_s_top_2": "nb_or_s_top_2",
    "bending_db_top_2": "db_top_2",
    "bending_rowgap_bot": "rowgap_bot",
    "bending_rowgap_top": "rowgap_top",
    "bending_cover_bot": "cover_bot",
    "bending_cover_top": "cover_top",
    
    # Legacy entries (for backward compatibility during migration)
    "inputs_bot_entry": "bot_entry",
    "inputs_top_entry": "top_entry",
    "inputs_nb_bot": "nb_bot",
    "inputs_db_bot": "db_bot",
    "inputs_nb_top": "nb_top",
    "inputs_db_top": "db_top",
    # We still keep nb_bot, nb_top etc. as params used by other pages.
    # They will be *derived* from the 2-layer system in recalc_derived_values().

    "inputs_lig_d": "lig_d",
    "inputs_lig_legs": "lig_legs",
    "inputs_s_lig": "s_lig",

    # Ducts
    "inputs_n_ducts": "n_ducts",
    "inputs_duct_dia": "duct_dia",
    
    # Shear section parameters (Inputs)
    "inputs_d_g": "d_g",
    "inputs_k_d_option": "k_d_option",
    "inputs_k_v_method": "k_v_method",

    "inputs_exposure_class": "exposure_class",
    "inputs_env_option": "env_option",
    "inputs_s_bar_bot": "s_bar_bot",
    
    # Crack criteria (Inputs page)
    "inputs_wmax_char_limit": "wmax_char_limit",
    "inputs_crack_member_type": "crack_member_type",
    "inputs_crack_k1": "crack_k1",
    "inputs_crack_k2": "crack_k2",
    "inputs_actions_source": "actions_source",  # Source of design actions (manual vs teaching)

    # Time-dependent inputs
    "inputs_t_creep": "t_creep",
    "inputs_age_at_loading": "age_at_loading",
    "inputs_stress_ratio": "stress_ratio",
    "inputs_t_shrink": "t_shrink",

    # ----------------- BENDING PAGE -----------------
    "bending_b": "b",
    "bending_D": "D",
    "bending_L": "L",

    "bending_fc": "fc",
    "bending_fsy": "fsy",
    "bending_Ec": "Ec",
    "bending_Es": "Es",
    # Legacy key plus new explicit bending phi widget
    "bending_phi_b": "phi_bend",
    "bending_phi_bend": "phi_bend",

    "bending_Mu_star": "Mu_star_manual",
    "bending_P_star": "P_star",
    "bending_N_star": "N_star",

    "bending_nb_bot": "nb_bot",
    "bending_db_bot": "db_bot",
    "bending_nb_top": "nb_top",
    "bending_db_top": "db_top",
    "bending_rowgap_bot": "rowgap_bot",
    "bending_rowgap_top": "rowgap_top",

    "bending_cover_bot": "cover_bot",
    "bending_cover_top": "cover_top",
    "bending_side_cover_bot": "side_cover_bot",
    "bending_side_cover_top": "side_cover_top",

    # --- Bending page: explicit reo mode/count/spacing widgets ---
    "bending_bot1_layout_mode": "bot1_layout_mode",
    "bending_bot1_count": "bot1_count",
    "bending_bot1_spacing": "bot1_spacing",

    "bending_bot2_layout_mode": "bot2_layout_mode",
    "bending_bot2_count": "bot2_count",
    "bending_bot2_spacing": "bot2_spacing",

    "bending_top1_layout_mode": "top1_layout_mode",
    "bending_top1_count": "top1_count",
    "bending_top1_spacing": "top1_spacing",

    "bending_top2_layout_mode": "top2_layout_mode",
    "bending_top2_count": "top2_count",
    "bending_top2_spacing": "top2_spacing",

    # ----------------- SHEAR PAGE -----------------
    "shear_b": "b",
    "shear_D": "D",
    "shear_L": "L",

    "shear_fc": "fc",
    "shear_fsy": "fsy",
    "shear_Ec": "Ec",
    "shear_Es": "Es",

    "shear_Vu_star": "load_Vstar_proxy",
    "shear_Tu_star": "Tu_star",
    "shear_P_star": "P_star",
    "shear_N_star": "N_star",

    "shear_phi_v": "phi_shear",
    "shear_phi_shear": "phi_shear",
    "shear_phi_t": "phi_torsion",

    "shear_nb_bot": "nb_bot",
    "shear_db_bot": "db_bot",
    "shear_nb_top": "nb_top",
    "shear_db_top": "db_top",

    "shear_lig_d": "lig_d",
    "shear_lig_legs": "lig_legs",
    "shear_s_lig": "s_lig",
    
    # Shear section parameters
    "shear_d_g": "d_g",
    "shear_n_ducts": "n_ducts",
    "shear_duct_dia": "duct_dia",
    "shear_k_d_option": "k_d_option",
    "shear_k_v_method": "k_v_method",

    "shear_cover_bot": "cover_bot",
    "shear_cover_top": "cover_top",

    # ----------------- TORSION / SKETCH PAGE -----------------
    "torsion_theta_deg": "crack_theta_deg",

    # ----------------- CRACK CONTROL PAGE -----------------
    "crack_b": "b",
    "crack_D": "D",
    "crack_L": "L",

    "crack_fc": "fc",
    "crack_fsy": "fsy",
    "crack_Ec": "Ec",
    "crack_Es": "Es",

    "crack_Mu_star": "Mu_star_manual",

    "crack_nb_bot": "nb_bot",
    "crack_db_bot": "db_bot",
    "crack_nb_top": "nb_top",
    "crack_db_top": "db_top",

    "crack_exposure_class": "exposure_class",
    "crack_s_bar_bot": "s_bar_bot",
    
    # Crack criteria (Crack page)
    "crack_wmax": "wmax_char_limit",
    "crack_member_type": "crack_member_type",
    "crack_k1": "crack_k1",
    "crack_k2": "crack_k2",

    "crack_cover_bot": "cover_bot",
    "crack_cover_top": "cover_top",
    
    # Crack page 2-layer bottom reinforcement (standardized to crack_ prefix)
    "crack_nb_or_s_bot_1": "nb_or_s_bot_1",
    "crack_db_bot_1": "db_bot_1",
    "crack_nb_or_s_bot_2": "nb_or_s_bot_2",
    "crack_db_bot_2": "db_bot_2",
    "crack_rowgap_bot": "rowgap_bot",
    
    # Crack page: Bottom longitudinal reinforcement (explicit mode/count/spacing)
    "crack_bot1_layout_mode": "bot1_layout_mode",
    "crack_bot1_count": "bot1_count",
    "crack_bot1_spacing": "bot1_spacing",
    "crack_bot2_layout_mode": "bot2_layout_mode",
    "crack_bot2_count": "bot2_count",
    "crack_bot2_spacing": "bot2_spacing",
    
    # ----------------- SFD/BMD PAGE (Unified loading) -----------------
    "load_L": "span_L_m",
    "load_g_udl": "g_udl_kNm_per_m",
    "load_q_udl": "q_udl_kNm_per_m",
    "load_psi_udl": "psi_udl",
    "load_case": "sfd_case",
    "load_G_point": "G_point_kN",
    "load_Q_point": "Q_point_kN",
    "load_psi_point": "psi_point",
    "load_a_point": "a_m",
    
    # ----------------- DEFLECTION PAGE -----------------
    "defl_beff": "defl_beff",
    "defl_b": "b",
    "defl_D": "D",
    "defl_support_type": "defl_support_type",
    "defl_limit_ratio": "defl_limit_ratio",
    "defl_Fdef": "defl_Fdef",
    "defl_use_simplified_ief": "defl_use_simplified_ief",
    
    # Deflection page uses the same concrete props as global materials
    "defl_fc": "fc",
    "defl_Ec": "Ec",
    
    # ----------------- INPUTS PAGE: Serviceability + Shrinkage -----------------
    "inputs_defl_support_type": "defl_support_type",
    "inputs_defl_limit_ratio": "defl_limit_ratio",
    "inputs_defl_Fdef": "defl_Fdef",
    "inputs_member_faces_exposed": "member_faces_exposed",
    "inputs_shrinkage_env": "shrinkage_env",
    
    # ----------------- SHRINKAGE PAGE -----------------
    "sh_faces": "member_faces_exposed",
    "sh_env": "shrinkage_env",
    "sh_t_days": "t_shrink",
    
    # ----------------- CREEP PAGE -----------------
    "cr_faces": "member_faces_exposed",
    "cr_env": "env_option",
    "cr_t_creep": "t_creep",
    "cr_tau": "age_at_loading",
    "cr_sigma_ratio": "stress_ratio",
}

# Page-level TAB_KEYS mapping (derived from TAB_KEYS; does NOT change the contract)
TAB_KEYS_BY_PAGE = {
    "creep": {sk: wk for wk, sk in TAB_KEYS.items() if wk.startswith("cr_")},
    "shrinkage": {sk: wk for wk, sk in TAB_KEYS.items() if wk.startswith("sh_")},
    "deflection": {sk: wk for wk, sk in TAB_KEYS.items() if wk.startswith("defl_")},
    "design": {sk: wk for wk, sk in TAB_KEYS.items() if wk.startswith("load_")},
}

# =========================
# V2: Canonical key resolver
# =========================

CANONICAL_PREFIX = "inputs_"

# Build: shared_key -> canonical widget key (prefer inputs_*)
_SHARED_TO_CANONICAL_WIDGET: dict[str, str] = {}
for wk, sk in TAB_KEYS.items():
    if wk.startswith(CANONICAL_PREFIX):
        _SHARED_TO_CANONICAL_WIDGET.setdefault(sk, wk)

# Fallback: if a shared key has no inputs_* mapping, pick the first mapping (should be rare)
for wk, sk in TAB_KEYS.items():
    _SHARED_TO_CANONICAL_WIDGET.setdefault(sk, wk)

# Build alias map: any non-canonical widget key that targets a shared key becomes an alias to the canonical key
WIDGET_KEY_ALIASES: dict[str, str] = {}
for wk, sk in TAB_KEYS.items():
    canonical = _SHARED_TO_CANONICAL_WIDGET.get(sk, wk)
    if wk != canonical:
        WIDGET_KEY_ALIASES[wk] = canonical


def resolve_widget_key(widget_key: str) -> str:
    # Keep widget keys distinct across pages (contract rule).
    return widget_key


def get_widget_key_for_shared(shared_key: str, prefix: str = "inputs_") -> str | None:
    """
    Find the widget key that maps to a given shared key (with optional prefix filter).
    Returns None if not found.
    """
    for wk, sk in TAB_KEYS.items():
        if sk == shared_key and wk.startswith(prefix):
            return wk
    return None

# ============================================
# 2b. CONTRACT VALIDATION
# ============================================

def _validate_contract():
    """
    Internal sanity checks to enforce the rules:
    - Every TAB_KEYS target must exist in SHARED_DEFAULTS.
    - No duplicate widget keys.
    - All RESULT_KEYS exist in SHARED_DEFAULTS.
    """
    # Shared keys
    shared_keys = set(SHARED_DEFAULTS.keys())

    # 1) Every widget→shared mapping must point to a defined shared key
    for widget_key, shared_key in TAB_KEYS.items():
        if shared_key not in shared_keys:
            raise KeyError(
                f"[SESSION STATE CONTRACT] TAB_KEYS['{widget_key}'] "
                f"points to unknown shared key '{shared_key}'.\n"
                f"Add it to SHARED_DEFAULTS or fix the mapping."
            )

    # 2) No duplicate widget keys (dict already enforces this,
    #    but we keep this here as a comment-style guard)
    if len(TAB_KEYS) != len(set(TAB_KEYS.keys())):
        raise RuntimeError(
            "[SESSION STATE CONTRACT] Duplicate widget keys detected in TAB_KEYS."
        )

    # 3) RESULT_KEYS are derived outputs and do NOT need to exist in SHARED_DEFAULTS.
    # Validate they have defaults in RESULT_DEFAULTS instead.
    missing_result_defaults = set(RESULT_KEYS) - set(RESULT_DEFAULTS.keys())
    if missing_result_defaults:
        raise KeyError(
            f"[SESSION STATE CONTRACT] RESULT_KEYS missing defaults in RESULT_DEFAULTS: {missing_result_defaults}"
        )

# Run this once at import
_validate_contract()

# ============================================
# 3. INITIALISATION + DERIVED UPDATES
# ============================================

@st.cache_resource
def _persistent_store():
    """
    Server-process persistent dict, survives reruns and accidental session_state wipes.
    Keyed by a stable client id we keep in query params.
    """
    return {}


def get_client_id() -> str:
    """
    Stable per-browser identifier stored in query params (not session_state).
    Prevents losing the key when session_state wipes.
    """
    import uuid
    cid = st.query_params.get("cid")
    if isinstance(cid, list):
        cid = cid[0] if cid else None
    if not cid:
        cid = str(uuid.uuid4())
        st.query_params["cid"] = cid
    return cid


# File-based snapshot (survives server restarts)
SNAPSHOT_PATH = os.path.join(os.path.dirname(__file__), "shared_snapshot.json")


def load_shared_snapshot() -> dict:
    """Load shared inputs snapshot from JSON file."""
    if not os.path.exists(SNAPSHOT_PATH):
        return {}
    try:
        with open(SNAPSHOT_PATH, "r") as f:
            return json.load(f) or {}
    except Exception:
        return {}


def save_shared_snapshot(shared: dict):
    """Save shared inputs snapshot to JSON file."""
    try:
        with open(SNAPSHOT_PATH, "w") as f:
            json.dump(shared, f, indent=2)
    except Exception:
        pass


def persist_state_snapshot():
    """
    Persist ALL shared keys + ALL inputs_* widget keys + caches used for restores.
    Uses file-based snapshot (survives server restarts).
    """
    # Persist shared inputs only (not results, not derived)
    shared = {}
    for k in SHARED_DEFAULTS.keys():
        if k in st.session_state:
            shared[k] = st.session_state[k]
    
    # Save to file (survives server restarts)
    save_shared_snapshot(shared)
    
    # Also persist to in-memory store (for backward compatibility)
    cid = get_client_id()
    store = _persistent_store()

    # Persist widget values that matter most (inputs_ + caches)
    widgets = {}
    for widget_key in TAB_KEYS.keys():
        if widget_key.startswith("inputs_") and widget_key in st.session_state:
            widgets[widget_key] = st.session_state[widget_key]

        cached_key = f"_cached_{widget_key}"
        if cached_key in st.session_state:
            widgets[cached_key] = st.session_state[cached_key]

    store[cid] = {"shared": shared, "widgets": widgets}


def restore_state_snapshot_if_available(force: bool = False) -> bool:
    """
    If session_state wiped, restore from persisted snapshot.
    Returns True if restored anything.
    
    Args:
        force: If True, overwrite existing keys. If False, only restore missing keys.
    """
    # Never overwrite live session state after user interaction
    if st.session_state.get("_user_has_edited_anything", False):
        return False
    
    # Prevent repeated restore loops
    if st.session_state.get("_snapshot_restore_complete", False):
        return False
    
    # Try file-based snapshot first (survives server restarts)
    snap = load_shared_snapshot()
    restored_any = False
    
    if snap:
        # Restore shared inputs from file snapshot
        for k in SHARED_DEFAULTS.keys():
            if k in snap:
                if force or (k not in st.session_state):
                    set_shared(k, snap[k], source="restore_snapshot")
                    restored_any = True
    
    # Also try in-memory store (for backward compatibility)
    cid = get_client_id()
    store = _persistent_store()
    mem_snap = store.get(cid)
    
    if mem_snap and not restored_any:
        # Restore shared first
        for k, v in mem_snap.get("shared", {}).items():
            if k in SHARED_DEFAULTS:  # Only restore shared inputs
                if force or (k not in st.session_state):
                    set_shared(k, v, source="restore_snapshot")
                    restored_any = True

        # Restore inputs_ widgets and caches
        for k, v in mem_snap.get("widgets", {}).items():
            if force or (k not in st.session_state):
                st.session_state[k] = v
                restored_any = True
    
    if restored_any:
        st.session_state["_snapshot_restore_complete"] = True

    return restored_any


def begin_render_cycle():
    """
    MUST be called once per run (in app.py before rendering any page).
    Ensures rendered widget gating is per-run, not cumulative across runs.
    """
    st.session_state["_rendered_widget_keys"] = set()


def debug_log(tag: str, data: dict):
    """Helper to write debug logs in consistent format."""
    if not DEBUG_MODE:
        return
    import json
    log_path = "/Users/jonathonleggo/Library/CloudStorage/OneDrive-Personal/Documents/GitHub/blank-app/.cursor/debug.log"
    try:
        with open(log_path, "a") as f:
            f.write(json.dumps({
                "location": f"state_and_helpers.py:{tag}",
                "message": tag,
                "data": data,
                "timestamp": __import__("time").time() * 1000,
                "sessionId": "debug-session",
                "runId": "run1",
                "hypothesisId": "watchdog"
            }) + "\n")
    except:
        pass


def log_shared_diff(tag: str):
    """Log any changes to shared keys since last run."""
    prev = st.session_state.get("_prev_shared_snapshot", {})
    now = {k: st.session_state.get(k) for k in SHARED_DEFAULTS.keys()}

    diffs = {}
    for k, v in now.items():
        if prev.get(k) != v:
            diffs[k] = {"prev": prev.get(k), "now": v}

    st.session_state["_prev_shared_snapshot"] = now

    if diffs:
        debug_log(tag, {"changed_shared": diffs})


def _is_invalid_shared_value(shared_key: str, val) -> bool:
    """Shared is invalid if None, or (==0 and zero is NOT allowed for this key)."""
    if val is None:
        return True
    if isinstance(val, (int, float)) and float(val) == 0.0 and not zero_allowed(shared_key):
        return True
    return False


def repair_inputs_shared_from_widgets():
    """
    Deprecated.
    Shared inputs are the source of truth and must not be reconstructed
    from widgets on other pages.
    """
    return


def force_inputs_to_shared_after_wipe():
    """After wipe restore: treat inputs_* widget values as the only truth."""
    if not st.session_state.get("_wipe_recovery_mode", False):
        return

    repaired = {}
    for widget_key, shared_key in TAB_KEYS.items():
        if not widget_key.startswith("inputs_"):
            continue
        if widget_key not in st.session_state:
            continue

        wv = st.session_state.get(widget_key)
        sv = st.session_state.get(shared_key)

        # Never overwrite crack inputs or deflection support type during wipe recovery
        if shared_key in ("crack_k1", "crack_member_type", "defl_support_type"):
            continue

        # always force (even if nonzero mismatch)
        if sv != wv:
            set_shared(shared_key, wv, source="wipe_recovery")
            repaired[shared_key] = {"from": widget_key, "old": sv, "new": wv}

    if repaired:
        debug_log("WIPE_RECOVERY_FORCED_INPUTS_TO_SHARED", repaired)


def init_shared_session_state():
    """
    Initialise all shared keys and tab-widget keys in st.session_state.
    This must be called before any page renders widgets.
    
    IMPORTANT: This function only sets defaults when keys are missing.
    It NEVER overwrites existing user values.
    
    Always backfills missing widget keys (even after initialization) to prevent
    widgets from resetting when Streamlit drops widget state.
    """
    # Debug boot id: helps detect when the whole session got rebuilt
    if st.session_state.get("_boot_id") is None:
        st.session_state["_boot_id"] = f"boot_{int(time.time())}"
    
    # Watchdog: log shared key changes at entry
    log_shared_diff("init_entry_shared_diff")
    
    # Detect fresh boot
    if "_boot_id" not in st.session_state:
        st.session_state["_boot_id"] = str(uuid.uuid4())
        st.session_state["_fresh_boot"] = True
    else:
        st.session_state["_fresh_boot"] = False
    
    already_initialized = st.session_state.get("_shared_state_initialized", False)
    
    # Detect wipe recovery mode
    WIPED = not already_initialized
    
    if WIPED:
        st.session_state["_wipe_recovery_mode"] = True
        debug_log("WIPE_RECOVERY_MODE_ENABLED", {})
    else:
        st.session_state["_wipe_recovery_mode"] = False
    
    # Never overwrite live session state after user interaction
    restored = False
    restored_from_snapshot = False
    
    if not st.session_state.get("_user_has_edited_anything", False):
        # On fresh boot, restore snapshot BEFORE seeding defaults
        if st.session_state.get("_fresh_boot", False):
            # Prevent repeated restore loops
            if not st.session_state.get("_snapshot_restore_complete", False):
                snap = load_shared_snapshot()
                if snap:
                    # Restore only known shared input keys
                    for k in SHARED_DEFAULTS.keys():
                        if k in snap:
                            set_shared(k, snap[k], source="wipe_recovery")
                            restored_from_snapshot = True
                    restored = restored_from_snapshot
                st.session_state["_restored_from_snapshot"] = restored_from_snapshot
                st.session_state["_snapshot_restore_complete"] = restored_from_snapshot
                # Set restore guard flags to prevent callbacks from overwriting restored values
                if restored_from_snapshot:
                    st.session_state["_restore_guard_active"] = True
                    st.session_state["_restore_guard_ts"] = time.time()
                    # After snapshot restore, force one deterministic derived-values pass
                    # This ensures derived values (d, Ast_bot, etc.) are recalculated from restored inputs
                    recalc_derived_values()
    # Session wipe: restore FIRST (force overwrite), then seed anything still missing
    # Skip if we already restored from file snapshot on fresh boot
    # Also skip if user has interacted (never overwrite after user edits)
    if not already_initialized and not restored and not st.session_state.get("_user_has_edited_anything", False):
        # Prevent repeated restore loops
        if not st.session_state.get("_snapshot_restore_complete", False):
            # Force restore: overwrite any defaults that were seeded
            restored = restore_state_snapshot_if_available(force=True)
            
            # Set restore guard flags to prevent callbacks from overwriting restored values
            if restored:
                st.session_state["_restored_from_snapshot"] = True
                st.session_state["_snapshot_restore_complete"] = True
                st.session_state["_restore_guard_active"] = True
                st.session_state["_restore_guard_ts"] = time.time()
                # After snapshot restore, force one deterministic derived-values pass
                # This ensures derived values (d, Ast_bot, etc.) are recalculated from restored inputs
                recalc_derived_values()
        
        # After restoring, recompute the flag (it may have come back via snapshot)
        already_initialized = st.session_state.get("_shared_state_initialized", False)

        # If we restored shared keys, we can safely set initialized now
        if restored and not already_initialized:
            st.session_state["_shared_state_initialized"] = True
            already_initialized = True
    
    # Migrate old time defaults after snapshot restore (before seeding defaults)
    migrate_time_defaults_once()
    
    # NOW seed defaults only for anything still missing (after restore)
    for key, val in SHARED_DEFAULTS.items():
        if key not in st.session_state:
            set_shared(key, val, source="seed_defaults")
    
    # Ensure load proxies match the active edit mode on init
    load_proxies_from_active_set()

    # --- Backward-compat alias: shear key rename ---
    old_k = "Vu_star_manual"
    new_k = "load_Vstar_proxy"
    if old_k in st.session_state and new_k in st.session_state:
        if st.session_state.get(new_k) in (None, 0, 0.0, "") and st.session_state.get(old_k) not in (None, ""):
            st.session_state[new_k] = st.session_state[old_k]
    
    # Seed UI-only defaults (not shared, not synced)
    for k, v in UI_STATE_DEFAULTS.items():
        if k not in st.session_state:
            st.session_state[k] = v
    
    # Debug: confirm shared keys are fully present after init
    if st.session_state.get("_debug_state_tripwire", False):
        missing_shared = [k for k in SHARED_DEFAULTS.keys() if k not in st.session_state]
        if missing_shared:
            _append_debug_log(
                f"MISSING_SHARED_AFTER_INIT boot={st.session_state.get('_boot_id')} "
                f"count={len(missing_shared)} sample={missing_shared[:25]}"
            )
        else:
            _append_debug_log(
                f"INIT_OK boot={st.session_state.get('_boot_id')} shared_count={len(SHARED_DEFAULTS)}"
            )
    
    # Ensure sentinel exists once we have a valid state
    if not st.session_state.get("_shared_state_initialized", False):
        st.session_state["_shared_state_initialized"] = True
    
    # 1) Shared values: only set if missing (never overwrite)
    # Only run once.
    if not already_initialized:
        for key, val in SHARED_DEFAULTS.items():
            if key not in st.session_state:
                set_shared(key, val, source="seed_defaults")
    
    # Seed result defaults (derived outputs). Do not overwrite if already present.
    for k, v in RESULT_DEFAULTS.items():
        if k not in st.session_state:
            st.session_state[k] = v

    # 2) Tab-widget keys - ALWAYS ensure widget keys exist (only seed if missing).
    # This prevents "Inputs resets when returning" if widget keys were dropped between pages.
    # CRITICAL: Only restore widget keys if they are TRULY missing (not just None/0).
    # If a widget key exists in session_state (even if value is 0), do NOT overwrite it.
    restored_widgets = []
    for widget_key, shared_key in TAB_KEYS.items():
        widget_exists = widget_key in st.session_state
        shared_exists = shared_key in st.session_state
        widget_value = st.session_state.get(widget_key) if widget_exists else None
        shared_value = st.session_state.get(shared_key) if shared_exists else None
        
        
        # Check if widget key exists but differs from cache.
        # IMPORTANT: if the widget exists, the widget value is authoritative (user input).
        # Cache is ONLY used to restore if Streamlit dropped the widget key.
        cached_key = f"_cached_{widget_key}"
        widget_missing = (widget_key not in st.session_state) or (st.session_state.get(widget_key) is None)

        # ONLY restore from cache if Streamlit dropped the widget key
        # CRITICAL: Always prefer cache over shared state for inputs_* widgets
        # Cache preserves the actual user input, while shared state might be stale
        restored_value = None
        if widget_missing and widget_key.startswith("inputs_") and cached_key in st.session_state:
            cached_value = st.session_state[cached_key]
            # Only restore from cache if cache value is not 0 (or if 0 is the default)
            default_value = SHARED_DEFAULTS.get(shared_key, None)
            cache_is_valid = (cached_value != 0) or (cached_value == 0 and default_value == 0)
            
            if cache_is_valid:
                restored_value = cached_value
                st.session_state[widget_key] = restored_value
                st.session_state[cached_key] = restored_value
            else:
                # Cache is stale (0 when it shouldn't be) - skip cache restoration, fall through to other sources
                pass

        if widget_missing:
            # When restoring widget keys, prefer inputs_* widget values if they exist
            # (they're the primary source and more likely to be up-to-date)
            # Check in this order:
            # 1) Cached inputs_* widget value (preserved from last sync) - already handled above
            # 2) Existing inputs_* widget in session_state (if not dropped)
            # 3) Shared state value
            # 4) Defaults
            
            # Skip cache restoration (already handled above), check for other sources
            if restored_value is None:
                # Check if there's an inputs_* widget for this shared key that still exists
                inputs_widget_key = None
                for wk, sk in TAB_KEYS.items():
                    if sk == shared_key and wk.startswith("inputs_") and wk in st.session_state:
                        inputs_widget_key = wk
                        break
                
                if inputs_widget_key:
                    # Prefer the inputs_* widget value (it's more authoritative)
                    restored_value = st.session_state[inputs_widget_key]
                    st.session_state[widget_key] = restored_value
                    # Update the cache to keep it current with the actual inputs_* widget value
                    cached_inputs_key = f"_cached_{inputs_widget_key}"
                    st.session_state[cached_inputs_key] = restored_value
                elif shared_key in st.session_state:
                    # Fall back to shared value if no inputs_* widget exists
                    shared_value = st.session_state[shared_key]
                    default_value = SHARED_DEFAULTS.get(shared_key, None)
                    
                    # CRITICAL FIX: Don't restore from shared state if shared is 0 and default is not 0
                    # This prevents restoring widgets to 0 when shared state is stale/uninitialized
                    # Only restore if:
                    # 1) Shared value is not 0, OR
                    # 2) Shared value is 0 AND default is also 0 (0 is legitimate)
                    should_restore = (shared_value != 0) or (shared_value == 0 and default_value == 0)
                    
                    
                    if should_restore:
                        restored_value = shared_value
                        old_widget_value = st.session_state.get(widget_key)
                        st.session_state[widget_key] = restored_value
                        # Log overwrite
                        if old_widget_value != restored_value:
                            pass
                    else:
                        # Skip restoring from shared (stale 0 value) BUT DO NOT write None into the widget.
                        # Instead fall back to the default value immediately.
                        restored_value = SHARED_DEFAULTS.get(shared_key, None)

                        # Only set if we actually have a default; otherwise leave missing
                        if restored_value is not None:
                            old_widget_value = st.session_state.get(widget_key)
                            st.session_state[widget_key] = restored_value
                            # Log overwrite with default
                            if old_widget_value != restored_value:
                                pass
                else:
                    # Final fallback to defaults
                    restored_value = SHARED_DEFAULTS.get(shared_key, None)
                    st.session_state[widget_key] = restored_value
            
            restored_widgets.append((widget_key, shared_key, restored_value))

    # 3) Only run your "snippet defaults" guard / snapshot ONCE
    if not already_initialized:
        if _is_snippet_defaults_state(st.session_state):
            _restore_last_good_inputs()
        else:
            _snapshot_last_good_inputs()

        st.session_state["_shared_state_initialized"] = True
        st.session_state["_shared_inited"] = True  # Keep legacy flag for compatibility
    
    # Keep global snapshot fresh on every run IF values look sane.
    # (No overwrites when we're in a bogus defaults state.)
    if not _is_snippet_defaults_state(st.session_state):
        _snapshot_last_good_inputs()
    
    # ============================
    # SAFE HYDRATION (NO widget→shared here)
    # ============================
    # CRITICAL: Only sync via on_change callbacks, never during init.
    # This prevents stale widget zeros from overwriting shared state on navigation.
    
    # NOTE:
    # Do NOT sync shared <- inputs_* here.
    # Shared must only be updated by on_change callbacks (or explicit sync functions),
    # otherwise stale navigation zeros can overwrite shared state.

    # 2) Hydrate ONLY the active page's widget keys, and only if missing.
    active_slug = st.session_state.get("page_slug") or st.session_state.get("_active_page_slug")
    if active_slug:
        prefix = f"{active_slug}_"
        for widget_key, shared_key in TAB_KEYS.items():
            if not widget_key.startswith(prefix):
                continue
            safe_hydrate(widget_key, shared_key, st.session_state.get(shared_key))
    
    # Keep inputs_* cache current, BUT do not poison it with stale navigation zeros.
    for widget_key, shared_key in TAB_KEYS.items():
        if widget_key.startswith("inputs_") and widget_key in st.session_state:
            widget_val = st.session_state[widget_key]
            cached_key = f"_cached_{widget_key}"

            default_value = SHARED_DEFAULTS.get(shared_key, None)
            shared_val = st.session_state.get(shared_key, None)

            # Detect "stale zero" (navigation glitch) for keys we must never let go stale:
            # - widget is 0
            # - shared has a meaningful non-zero value
            # - default is meaningful non-zero
            # - key is protected (geometry/materials/actions)
            # BUT: skip zero-allowed keys (where 0 is legitimate)
            is_stale_zero = (
                (widget_val == 0 or widget_val == 0.0)
                and (shared_key in NONZERO_REQUIRED_SHARED_KEYS)
                and (not zero_allowed(shared_key))
                and (shared_val not in (None, 0, 0.0))
                and (default_value not in (None, 0, 0.0))
            )

            if not is_stale_zero:
                st.session_state[cached_key] = widget_val
            # else: do NOT overwrite cache; keep the last known good value
    
    # Only attempt repair if we did NOT successfully restore from snapshot
    # This prevents "repair" logic from stomping restored state
    # NOTE: repair_inputs_shared_from_widgets() is disabled - shared inputs are the source of truth
    # and must not be reconstructed from widgets on other pages.
    if not restored:
        # repair_inputs_shared_from_widgets()  # DISABLED - see note above
        pass
    
    # Wipe Recovery Mode: force Inputs -> shared after wipe restore
    force_inputs_to_shared_after_wipe()
    
    # After wipe restore, Inputs are the canonical truth
    # This removes any lingering "shared disagrees with inputs" states
    if st.session_state.get("_wipe_recovery_mode", False):
        for widget_key, shared_key in TAB_KEYS.items():
            if widget_key.startswith("inputs_") and widget_key in st.session_state:
                set_shared(shared_key, st.session_state[widget_key], source="wipe_recovery")
    
    # Watchdog: log shared key changes at exit
    log_shared_diff("init_exit_shared_diff")
    
    # Debug-only: validate contract after initialization
    try:
        from src.debug.state_debug import is_debug_enabled
        if is_debug_enabled():
            validate_session_state_contract(context="after init_shared_session_state")
    except (ImportError, NameError):
        # Debug module not available, skip validation
        pass
    
    # Tripwire: detect shared keys that got zeroed during init
    _shared_zero_tripwire("AFTER init_shared_session_state")
    
    # Persist snapshot after init/restore so future wipes recover correctly
    persist_state_snapshot()
    
    if st.session_state.get("_debug_state_tripwire", False):
        _append_debug_log(f"INIT_DONE boot={st.session_state.get('_boot_id')}")


def hydrate_tab_widgets_from_shared(tab_name: str):
    """
    If widget keys are missing, seed them from shared values BEFORE rendering widgets.
    This prevents widgets coming up as 0/default after snapshot restore.
    
    Args:
        tab_name: Tab/page prefix (e.g., "inputs", "bending", "crack", "shear")
    """
    prefix = f"{tab_name}_"
    hydrated_count = 0
    
    for widget_key, shared_key in TAB_KEYS.items():
        if not widget_key.startswith(prefix):
            continue
        
        # Only seed widget key if truly missing
        if widget_key not in st.session_state:
            shared_val = st.session_state.get(shared_key)
            if shared_val is not None:
                st.session_state[widget_key] = shared_val
                hydrated_count += 1
    
    return hydrated_count


def force_hydrate_time_widgets_from_shared():
    """
    Force-hydrate the time-dependent INPUTS widgets from shared if the widgets are still at stale defaults (0/1).
    This prevents sync_callback from clobbering shared values (365/28/365) with widget value 1.
    """
    pairs = [
        ("inputs_t_creep", "t_creep"),
        ("inputs_age_at_loading", "age_at_loading"),
        ("inputs_t_shrink", "t_shrink"),
        ("inputs_stress_ratio", "stress_ratio"),
    ]

    for widget_key, shared_key in pairs:
        # shared value
        sv = st.session_state.get(shared_key, SHARED_DEFAULTS.get(shared_key))
        # widget value
        wv = st.session_state.get(widget_key, None)

        try:
            svf = float(sv) if sv is not None else None
        except Exception:
            svf = None
        try:
            wvf = float(wv) if wv is not None else None
        except Exception:
            wvf = None

        # Only force-hydrate if:
        # - shared is meaningful (>1 for time keys; stress_ratio >0)
        # - widget is missing OR still at stale default 0/1
        if shared_key in {"t_creep", "age_at_loading", "t_shrink"}:
            if svf is not None and svf > 1 and (wvf is None or wvf in (0.0, 1.0)):
                st.session_state[widget_key] = svf
        elif shared_key == "stress_ratio":
            if svf is not None and svf > 0 and (wvf is None or wvf in (0.0, 0.01)):
                st.session_state[widget_key] = svf


def hydrate_active_page_widgets_from_shared(
    active_slug: str,
    force_on_restore: bool = False,
    force_on_page_change: bool = False,
) -> None:
    """
    Prevent stale page widget keys (often 0) from overwriting shared values on navigation.
    Runs BEFORE rendering the active page so widgets start from shared values.
    Only force-hydrates keys whose shared values should not be clobbered by zeros.
    
    CRITICAL: Also hydrates inputs_* widgets (they're global and should always be hydrated
    from shared state to prevent stale zeros from syncing back into shared).
    
    Args:
        active_slug: Page slug (e.g., "bending", "crack", "inputs")
        force_on_restore: If True and snapshot was restored, force-overwrite stale widget values (0/1)
    """
    
    page_map = TAB_KEYS_BY_PAGE.get(active_slug)
    if page_map:
        wmap = {wk: sk for sk, wk in page_map.items()}
    else:
        prefix = f"{active_slug}_"
        wmap = {wk: sk for wk, sk in TAB_KEYS.items() if wk.startswith(prefix)}

    # Always include canonical inputs_* keys (global, should never go stale)
    for wk, sk in TAB_KEYS.items():
        if wk.startswith("inputs_"):
            wmap.setdefault(wk, sk)

    if not wmap:
        return
    _write_sync_trace_line(f"HYDRATE_ACTIVE_PAGE slug={active_slug} keys={len(wmap)}")

    # Seed only missing widget keys for this page
    hydrated_count = 0
    for widget_key, shared_key in wmap.items():
        if shared_key not in st.session_state:
            continue
        force = bool(force_on_page_change)
        safe_hydrate(widget_key, shared_key, st.session_state.get(shared_key), force=force)
        if widget_key in st.session_state:
            hydrated_count += 1
    
    # Tripwire: detect shared keys that got zeroed during hydrate
    _shared_zero_tripwire("AFTER hydrate_active_page_widgets_from_shared")


def sync_shared_from_widgets_once_per_run():
    """
    App-level sync: Copy widget values to shared keys (one-way: widget → shared).
    
    This ensures that when you navigate away from a page, the widget values
    (which persist in session_state) are copied to shared keys so other
    pages see consistent values.
    
    CRITICAL: Syncs when widget values differ from shared values (recently changed).
    When multiple widgets map to the same shared key, prefers inputs_* widgets.
    This prevents stale widgets from overwriting recently changed values.
    
    Rules (SESSION STATE CONTRACT COMPLIANT):
    - Only syncs INPUT parameters (those in SHARED_DEFAULTS that have widget mappings)
    - Never touches derived values (d, Ast_bot, etc.) - those are handled by recalc_derived_values()
    - Never touches result values (phi_Mu_cap, etc.)
    - Only syncs if widget key exists and widget value differs from shared value
    - When multiple widgets map to same shared key, prefers inputs_* widgets among differing ones
    - Never creates new keys beyond SHARED_DEFAULTS
    - Never modifies widget keys
    - Only writes to shared keys defined in SHARED_DEFAULTS (RULE 1 compliant)
    """
    # Only sync input parameters (not derived, not results)
    # We identify inputs by checking if they're in SHARED_DEFAULTS and have widget mappings
    input_keys = set(SHARED_DEFAULTS.keys())
    
    # Exclude derived values (these are recalculated, not synced from widgets)
    # Use DERIVED_KEYS constant for consistency (defined after RESULT_KEYS)
    derived_keys = DERIVED_KEYS
    
    # Exclude result values (these are computed, not synced from widgets)
    result_keys = RESULT_KEYS
    
    # Only sync input keys (not derived, not results)
    syncable_keys = input_keys - derived_keys - result_keys
    
    # Active page gating:
    # - Always allow inputs_* (global)
    # - Only allow the current active page prefix (e.g. bending_*) to sync shared keys
    active_slug = st.session_state.get("_active_page_slug", "inputs")
    active_prefix = f"{active_slug}_"
    
    # #region agent log
    import json
    import os
    log_path = "/Users/jonathonleggo/Library/CloudStorage/OneDrive-Personal/Documents/GitHub/blank-app/.cursor/debug.log"
    sync_operations = []
    # #endregion
    
    # Shared keys that must NEVER be overwritten by other pages' defaults.
    # Authority order for these: inputs_* first, then bending_*.
    LOCKED_REO_SHARED_KEYS = {
        "nb_or_s_bot_1", "db_bot_1", "nb_or_s_bot_2", "db_bot_2",
        "nb_or_s_top_1", "db_top_1", "nb_or_s_top_2", "db_top_2",
        "rowgap_bot", "rowgap_top",
        "cover_bot", "cover_top",
        # Shear reinforcement (locked to inputs_* only)
        "lig_d", "lig_legs", "s_lig",
    }
    
    # Shared keys that should NEVER be overwritten with 0 if they have meaningful values
    # This prevents stale widget zeros from clobbering shared state
    PROTECTED_FROM_ZERO_SHARED_KEYS = NONZERO_REQUIRED_SHARED_KEYS
    
    # Group widgets by shared key to handle conflicts
    # V2: Only canonical widget keys rendered THIS RUN are allowed to author shared keys
    widgets_by_shared = {}

    rendered = st.session_state.get("_rendered_widget_keys")
    if not isinstance(rendered, set):
        rendered = set()
    
    # #region agent log - Track sync entry
    import json
    import os
    log_path = "/Users/jonathonleggo/Library/CloudStorage/OneDrive-Personal/Documents/GitHub/blank-app/.cursor/debug.log"
    rendered_list = list(rendered) if isinstance(rendered, set) else []
    sample_widgets = ["inputs_b", "inputs_D", "inputs_fc", "inputs_fsy", "bending_nb_or_s_bot_1", "shear_lig_d"]
    widget_values_at_sync_start = {k: st.session_state.get(k) for k in sample_widgets if k in st.session_state}
    try:
        with open(log_path, "a") as f:
            f.write(json.dumps({"location": "state_and_helpers.py:sync_entry", "message": "Sync function entry", "data": {"rendered_count": len(rendered_list), "rendered_sample": rendered_list[:10], "widget_values": widget_values_at_sync_start}, "timestamp": __import__("time").time() * 1000, "sessionId": "debug-session", "runId": "run1", "hypothesisId": "F"}) + "\n")
    except: pass
    # #endregion

    for widget_key, shared_key in TAB_KEYS.items():
        if shared_key not in syncable_keys:
            continue

        # Only sync widgets that were rendered THIS RUN
        if widget_key not in rendered:
            # #region agent log
            try:
                with open(log_path, "a") as f:
                    f.write(json.dumps({"location": "state_and_helpers.py:sync", "message": "Skipped non-rendered key", "data": {"widget_key": widget_key, "shared_key": shared_key, "rendered_keys_count": len(rendered)}, "timestamp": __import__("time").time() * 1000, "sessionId": "debug-session", "runId": "run1", "hypothesisId": "C"}) + "\n")
            except: pass
            # #endregion
            continue

        # REO LOCK: Only inputs_* is allowed to author reinforcement shared keys
        if shared_key in LOCKED_REO_SHARED_KEYS and not widget_key.startswith("inputs_"):
            # #region agent log
            try:
                with open(log_path, "a") as f:
                    f.write(json.dumps({"location": "state_and_helpers.py:sync", "message": "Skipped non-inputs widget for locked reo key", "data": {"widget_key": widget_key, "shared_key": shared_key}, "timestamp": __import__("time").time() * 1000, "sessionId": "debug-session", "runId": "run1", "hypothesisId": "R"}) + "\n")
            except: pass
            # #endregion
            continue

        widget_value = st.session_state.get(widget_key)
        if widget_value is None:
            # #region agent log
            try:
                with open(log_path, "a") as f:
                    f.write(json.dumps({"location": "state_and_helpers.py:sync", "message": "Skipped missing key", "data": {"widget_key": widget_key, "shared_key": shared_key}, "timestamp": __import__("time").time() * 1000, "sessionId": "debug-session", "runId": "run1", "hypothesisId": "A"}) + "\n")
            except: pass
            # #endregion
            continue

        # #region agent log
        try:
            with open(log_path, "a") as f:
                f.write(json.dumps({"location": "state_and_helpers.py:sync", "message": "Adding widget to sync", "data": {"widget_key": widget_key, "shared_key": shared_key, "widget_value": widget_value}, "timestamp": __import__("time").time() * 1000, "sessionId": "debug-session", "runId": "run1", "hypothesisId": "A"}) + "\n")
        except: pass
        # #endregion

        widgets_by_shared.setdefault(shared_key, []).append((widget_key, widget_value))
    
    # For each shared key, sync the "most authoritative" widget value
    # Priority: 
    # 1) Widgets that differ from current shared value (recently changed)
    # 2) Among differing widgets, prefer inputs_* widgets (they're the primary source)
    # 3) If all widgets match shared value, no sync needed
    for shared_key, widget_list in widgets_by_shared.items():
        current_shared = st.session_state.get(shared_key)
        
        # #region agent log
        try:
            with open(log_path, "a") as f:
                f.write(json.dumps({"location": "state_and_helpers.py:742", "message": "Processing shared key", "data": {"shared_key": shared_key, "current_shared": current_shared, "widget_list": widget_list}, "timestamp": __import__("time").time() * 1000, "sessionId": "debug-session", "runId": "run1", "hypothesisId": "D"}) + "\n")
        except: pass
        # #endregion
        
        # Find widgets that differ from current shared value (these are "recently changed")
        differing_widgets = [(wk, wv) for wk, wv in widget_list if current_shared != wv]
        
        # Note: Locked reo keys are already filtered earlier - only inputs_* widgets
        # are allowed to sync for LOCKED_REO_SHARED_KEYS (see REO LOCK check above)
        
        # #region agent log
        try:
            with open(log_path, "a") as f:
                f.write(json.dumps({"location": "state_and_helpers.py:750", "message": "Differing widgets found", "data": {"shared_key": shared_key, "differing_widgets": differing_widgets}, "timestamp": __import__("time").time() * 1000, "sessionId": "debug-session", "runId": "run1", "hypothesisId": "D"}) + "\n")
        except: pass
        # #endregion
        
        if current_shared is None:
            # Shared key missing - prefer inputs_* widget if available, otherwise use first
            inputs_widgets = [(wk, wv) for wk, wv in widget_list if wk.startswith("inputs_")]
            if inputs_widgets:
                widget_key, widget_value = inputs_widgets[0]
            else:
                widget_key, widget_value = widget_list[0]
            set_shared(shared_key, widget_value, source="sync_init")
            # #region agent log
            try:
                with open(log_path, "a") as f:
                    f.write(json.dumps({"location": "state_and_helpers.py:sync", "message": "Initialized shared key", "data": {"widget_key": widget_key, "shared_key": shared_key, "value": widget_value}, "timestamp": __import__("time").time() * 1000, "sessionId": "debug-session", "runId": "run1", "hypothesisId": "A"}) + "\n")
            except: pass
            sync_operations.append((widget_key, shared_key, widget_value, "init", None))
            # #endregion
        elif differing_widgets:
            # At least one widget differs - prefer inputs_* widgets among the differing ones
            inputs_differing = [(wk, wv) for wk, wv in differing_widgets if wk.startswith("inputs_")]
            
            # CRITICAL: Prevent overwriting meaningful shared values with 0
            # If shared key is protected and has a meaningful value, don't allow 0 to overwrite it
            # BUT: allow 0 for zero-allowed keys (where 0 is legitimate)
            if shared_key in PROTECTED_FROM_ZERO_SHARED_KEYS and not zero_allowed(shared_key):
                shared_is_meaningful = current_shared not in (None, "", 0, 0.0)
                if shared_is_meaningful:
                    # Filter out widgets with value 0 - they're stale and shouldn't overwrite meaningful shared values
                    filtered_differing = [(wk, wv) for wk, wv in differing_widgets 
                                         if wv not in (None, "", 0, 0.0)]
                    if filtered_differing:
                        differing_widgets = filtered_differing
                        # Recompute inputs_differing after filtering
                        inputs_differing = [(wk, wv) for wk, wv in differing_widgets if wk.startswith("inputs_")]
                        # #region agent log
                        try:
                            with open(log_path, "a") as f:
                                f.write(json.dumps({"location": "state_and_helpers.py:protect_zero", "message": "Filtered out zero widgets from protected key", "data": {"shared_key": shared_key, "current_shared": current_shared, "filtered_count": len(filtered_differing), "original_count": len(differing_widgets)}, "timestamp": __import__("time").time() * 1000, "sessionId": "debug-session", "runId": "run1", "hypothesisId": "L"}) + "\n")
                        except: pass
                        # #endregion
                    else:
                        # All widgets are 0 - skip sync to preserve meaningful shared value
                        # #region agent log
                        try:
                            with open(log_path, "a") as f:
                                f.write(json.dumps({"location": "state_and_helpers.py:protect_zero", "message": "Skipped sync - all widgets are zero for protected key", "data": {"shared_key": shared_key, "current_shared": current_shared}, "timestamp": __import__("time").time() * 1000, "sessionId": "debug-session", "runId": "run1", "hypothesisId": "L"}) + "\n")
                        except: pass
                        # #endregion
                        continue
            
            # Check if there's a cached inputs_* value for this shared key
            # If so, only allow non-inputs_* widgets to sync if they match the cached value
            # This prevents stale widgets from overwriting values set by inputs_* widgets
            # IMPORTANT: Check cache even if inputs_* widget isn't in the current widget list
            # (it might have been dropped by Streamlit)
            cached_inputs_value = None
            for wk, sk in TAB_KEYS.items():
                if sk == shared_key and wk.startswith("inputs_"):
                    cached_key = f"_cached_{wk}"
                    if cached_key in st.session_state:
                        cached_inputs_value = st.session_state[cached_key]
                        # #region agent log
                        try:
                            with open(log_path, "a") as f:
                                f.write(json.dumps({"location": "state_and_helpers.py:815", "message": "Found cached inputs value", "data": {"shared_key": shared_key, "cached_key": cached_key, "cached_value": cached_inputs_value}, "timestamp": __import__("time").time() * 1000, "sessionId": "debug-session", "runId": "run1", "hypothesisId": "D"}) + "\n")
                        except: pass
                        # #endregion
                        break
            
            # Filter out non-inputs_* widgets that would overwrite a cached inputs_* value
            if cached_inputs_value is not None:
                # Only allow non-inputs_* widgets to sync if they match the cached value
                # This prevents stale widgets from overwriting the correct value
                filtered_differing = [(wk, wv) for wk, wv in differing_widgets 
                                     if wk.startswith("inputs_") or wv == cached_inputs_value]
                if filtered_differing != differing_widgets:
                    differing_widgets = filtered_differing
                    # Recompute inputs_differing after filtering
                    inputs_differing = [(wk, wv) for wk, wv in differing_widgets if wk.startswith("inputs_")]
                    
                    # #region agent log
                    try:
                        with open(log_path, "a") as f:
                            f.write(json.dumps({"location": "state_and_helpers.py:825", "message": "Filtered out stale widgets", "data": {"shared_key": shared_key, "cached_value": cached_inputs_value, "filtered_count": len(filtered_differing), "original_count": len(differing_widgets)}, "timestamp": __import__("time").time() * 1000, "sessionId": "debug-session", "runId": "run1", "hypothesisId": "D"}) + "\n")
                    except: pass
                    # #endregion
            
            # #region agent log
            try:
                with open(log_path, "a") as f:
                    f.write(json.dumps({"location": "state_and_helpers.py:768", "message": "Selecting widget to sync", "data": {"shared_key": shared_key, "inputs_differing": inputs_differing, "all_differing": differing_widgets, "cached_inputs_value": cached_inputs_value}, "timestamp": __import__("time").time() * 1000, "sessionId": "debug-session", "runId": "run1", "hypothesisId": "D"}) + "\n")
            except: pass
            # #endregion
            
            if inputs_differing:
                widget_key, widget_value = inputs_differing[0]
                # Cache inputs_* widget values so we can restore them later if Streamlit drops the widget key
                if widget_key.startswith("inputs_"):
                    st.session_state[f"_cached_{widget_key}"] = widget_value
            elif differing_widgets:
                widget_key, widget_value = differing_widgets[0]
            else:
                # All differing widgets were filtered out - skip sync
                continue
            old_shared_value = current_shared
            # CRITICAL: Log when we're about to overwrite a meaningful shared value with 0
            # BUT allow 0 for zero-allowed keys
            widget_is_zero = widget_value in (0, 0.0)
            shared_is_meaningful = old_shared_value not in (None, "", 0, 0.0)
            if shared_is_meaningful and widget_is_zero and shared_key in PROTECTED_FROM_ZERO_SHARED_KEYS and not zero_allowed(shared_key):
                # #region agent log
                try:
                    with open(log_path, "a") as f:
                        f.write(json.dumps({"location": "state_and_helpers.py:sync_write", "message": "WARNING: About to overwrite meaningful shared with zero", "data": {"widget_key": widget_key, "shared_key": shared_key, "old_shared": old_shared_value, "new_widget_value": widget_value}, "timestamp": __import__("time").time() * 1000, "sessionId": "debug-session", "runId": "run1", "hypothesisId": "O"}) + "\n")
                except: pass
                # #endregion
            set_shared(shared_key, widget_value, source="sync_update")
            
            # #region agent log
            try:
                with open(log_path, "a") as f:
                    f.write(json.dumps({"location": "state_and_helpers.py:sync", "message": "Wrote to shared key", "data": {"widget_key": widget_key, "shared_key": shared_key, "old_value": old_shared_value, "new_value": widget_value}, "timestamp": __import__("time").time() * 1000, "sessionId": "debug-session", "runId": "run1", "hypothesisId": "A"}) + "\n")
            except: pass
            # #endregion
            
            # --- MINIMAL FIX: If a bending_* reinforcement widget updates a shared key,
            # also update the cached inputs_* value for the same shared key.
            # Otherwise the cached inputs_* value blocks bending_* changes on the next navigation.
            BENDING_REO_SHARED_KEYS = {
                "nb_or_s_bot_1", "db_bot_1", "nb_or_s_bot_2", "db_bot_2",
                "nb_or_s_top_1", "db_top_1", "nb_or_s_top_2", "db_top_2",
                "rowgap_bot", "rowgap_top", "cover_bot", "cover_top",
            }
            
            if widget_key.startswith("bending_") and shared_key in BENDING_REO_SHARED_KEYS:
                for wk, sk in TAB_KEYS.items():
                    if sk == shared_key and wk.startswith("inputs_"):
                        st.session_state[f"_cached_{wk}"] = widget_value
            
            # #region agent log
            sync_operations.append((widget_key, shared_key, widget_value, "update", old_shared_value))
            # #endregion
        # else: all widgets match shared value, no sync needed
    
    # #region agent log
    if sync_operations:
        try:
            with open(log_path, "a") as f:
                f.write(json.dumps({"location": "state_and_helpers.py:688", "message": "sync_shared_from_widgets sync operations", "data": {"sync_count": len(sync_operations), "sample_syncs": sync_operations[:5]}, "timestamp": __import__("time").time() * 1000, "sessionId": "debug-session", "runId": "run1", "hypothesisId": "D"}) + "\n")
        except: pass
    
    # Summary log - track widget values after sync completes
    sample_widgets = ["inputs_b", "inputs_D", "inputs_fc", "inputs_fsy", "bending_nb_or_s_bot_1", "shear_lig_d"]
    widget_values_at_sync_end = {k: st.session_state.get(k) for k in sample_widgets if k in st.session_state}
    try:
        with open(log_path, "a") as f:
            f.write(json.dumps({"location": "state_and_helpers.py:sync_exit", "message": "Sync function exit", "data": {"widget_values": widget_values_at_sync_end, "sync_operations_count": len(sync_operations)}, "timestamp": __import__("time").time() * 1000, "sessionId": "debug-session", "runId": "run1", "hypothesisId": "F"}) + "\n")
    except: pass
    # #endregion


def _decode_bars_or_spacing(entry, b, cover_side, bar_dia):
    """
    Interpret entry as:
      - ≤ 30 => number of bars
      - > 30 => spacing in mm

    Returns (mode, n_eff, s_eff):
      mode = "N" or "S"
      n_eff = effective number of bars (int)
      s_eff = effective spacing (mm) (float)
    """
    try:
        val = float(entry)
    except Exception:
        return "N", 0, 0.0

    # Fallbacks
    try:
        b_val = float(b)
    except Exception:
        b_val = 0.0
    try:
        cs_val = float(cover_side)
    except Exception:
        cs_val = 0.0

    # width between bar centroids
    L_centroid = max(0.0, b_val - 2.0 * cs_val)

    if val <= 0.0 or L_centroid <= 0.0:
        return "N", 0, 0.0

    # Case 1: small value => number of bars
    if val < 30.0:
        n = int(round(val))
        n = max(1, n)

        if n == 1:
            # single bar – spacing is not really defined, use L_centroid as a proxy
            s_eff = L_centroid
        else:
            s_eff = L_centroid / (n - 1)

        return "N", n, s_eff

    # Case 2: large value => spacing in mm
    s_target = val
    # max(i) such that cover + (i-1)*s ≤ b-cover  → i ≤ L_centroid/s + 1
    n = int(L_centroid // s_target) + 1
    n = max(1, n)

    return "S", n, s_target


def recalc_derived_values():
    """
    Update derived geometry/reo values in session_state based on the
    current shared inputs (b, D, covers, bar sizes, etc.).
    RULE 3: This is the ONLY place derived values are written.
    
    Now handles 2-layer reinforcement system with auto-splitting.
    """
    from section_layout import compute_bar_layout_pure
    
    # Bridge explicit layout mode inputs back to legacy nb_or_s_* keys
    def _mode_value(mode_key, count_key, spacing_key, fallback):
        mode = st.session_state.get(mode_key, "Count")
        if mode == "Spacing":
            return float(st.session_state.get(spacing_key, fallback))
        return float(st.session_state.get(count_key, fallback))
    
    # Bridge into legacy nb_or_s_* keys used elsewhere
    st.session_state["nb_or_s_bot_1"] = _mode_value("bot1_layout_mode", "bot1_count", "bot1_spacing", 4)
    st.session_state["nb_or_s_bot_2"] = _mode_value("bot2_layout_mode", "bot2_count", "bot2_spacing", 0)
    st.session_state["nb_or_s_top_1"] = _mode_value("top1_layout_mode", "top1_count", "top1_spacing", 2)
    st.session_state["nb_or_s_top_2"] = _mode_value("top2_layout_mode", "top2_count", "top2_spacing", 0)
    
    D = st.session_state["D"]
    cover_bot = st.session_state["cover_bot"]
    cover_top = st.session_state["cover_top"]
    
    # Get cover_side, with fallback to min of cover_top/cover_bot
    cover_side = st.session_state.get("cover_side", min(
        st.session_state.get("cover_top", 40.0),
        st.session_state.get("cover_bot", 40.0),
    ))

    b = st.session_state.get("b", 0.0)
    rowgap_bot = st.session_state.get("rowgap_bot", 60.0)
    rowgap_top = st.session_state.get("rowgap_top", 60.0)

    # --- Derived geometry: bw is always derived from b ---
    if b is not None:
        st.session_state["defl_bw"] = b

    # --- Derived: effective span for deflection ---
    L_val = st.session_state.get("L")
    if L_val is not None:
        st.session_state["defl_L_eff"] = float(L_val) / 1000.0
    
    # Minimum spacing (AS 3600 typical: max(bar_dia, 25mm) for clear spacing)
    # We'll use a conservative default
    s_min_default = 25.0  # mm minimum clear spacing
    
    # ---------- 3.1 Process 2-layer system for BOTTOM ----------
    # Get Layer 1 values
    nb_or_s_bot_1 = st.session_state.get("nb_or_s_bot_1", 4.0)
    db_bot_1 = st.session_state.get("db_bot_1", 20.0)
    
    # Get Layer 2 values (may be auto-updated)
    nb_or_s_bot_2 = st.session_state.get("nb_or_s_bot_2", 0.0)
    db_bot_2 = st.session_state.get("db_bot_2", db_bot_1)  # Default to Layer 1 diameter
    
    # Compute layout for Layer 1
    s_min_bot = max(db_bot_1, s_min_default)
    layout_bot_1 = compute_bar_layout_pure(
        b=b, cover_side=cover_side, nb_or_s=nb_or_s_bot_1,
        db=db_bot_1, s_min=s_min_bot, rowgap=rowgap_bot
    )
    
    # Auto-update Layer 2 if Layer 1 doesn't fit in single row
    bot_layer2_was_auto = False
    bot_layer2_was_manual = st.session_state.get("nb_or_s_bot_2", 0.0) > 0
    
    if layout_bot_1["auto_split"] and layout_bot_1["n_row2"] > 0:
        n_spill = layout_bot_1["n_row2"]

        bot_layer2_locked = st.session_state.get("_lock_reo_bot_layer2", False)

        if bot_layer2_locked:
            # User has explicitly controlled Layer 2 (including setting it to 0). Do not overwrite.
            st.session_state["_reo_msg_bot_layer2_overwritten"] = True
        else:
            # Layer 1 forced a split - auto-update Layer 2
            if bot_layer2_was_manual:
                st.session_state["_reo_msg_bot_layer2_overwritten"] = True
            else:
                st.session_state["_reo_msg_bot_auto_layer2"] = True

            st.session_state["nb_or_s_bot_2"] = float(n_spill)
            st.session_state["db_bot_2"] = db_bot_1
            nb_or_s_bot_2 = float(n_spill)
            db_bot_2 = db_bot_1
            bot_layer2_was_auto = True
    # Otherwise, Layer 2 remains as user-defined (or 0)
    
    # Track warnings from layout
    if layout_bot_1.get("warning"):
        st.session_state["_reo_warning_bot_1"] = layout_bot_1["warning"]
    if layout_bot_1.get("warning") and "cannot fit" in layout_bot_1["warning"].lower():
        st.session_state["_reo_error_bot_1"] = True
    
    # Compute layout for Layer 2 (if it has bars)
    layout_bot_2 = None
    if nb_or_s_bot_2 > 0:
        s_min_bot_2 = max(db_bot_2, s_min_default)
        layout_bot_2 = compute_bar_layout_pure(
            b=b, cover_side=cover_side, nb_or_s=nb_or_s_bot_2,
            db=db_bot_2, s_min=s_min_bot_2, rowgap=rowgap_bot
        )
    
    # Total bottom bars = Layer 1 + Layer 2
    n_bot_total = layout_bot_1["n_total"]
    if layout_bot_2:
        n_bot_total += layout_bot_2["n_total"]
    
    # ---------- 3.2 Process 2-layer system for TOP ----------
    # Get Layer 1 values - treat 0 as valid (no falsy fallbacks)
    nb_or_s_top_1_val = st.session_state.get("nb_or_s_top_1")
    nb_or_s_top_1 = float(nb_or_s_top_1_val) if nb_or_s_top_1_val is not None else 2.0
    db_top_1 = st.session_state.get("db_top_1", 16.0)
    
    # Get Layer 2 values (may be auto-updated)
    nb_or_s_top_2 = st.session_state.get("nb_or_s_top_2", 0.0)
    db_top_2 = st.session_state.get("db_top_2", db_top_1)  # Default to Layer 1 diameter
    
    # Compute layout for Layer 1
    s_min_top = max(db_top_1, s_min_default)
    layout_top_1 = compute_bar_layout_pure(
        b=b, cover_side=cover_side, nb_or_s=nb_or_s_top_1,
        db=db_top_1, s_min=s_min_top, rowgap=rowgap_top
    )
    
    # Auto-update Layer 2 if Layer 1 doesn't fit in single row
    top_layer2_was_auto = False
    top_layer2_was_manual = st.session_state.get("nb_or_s_top_2", 0.0) > 0
    
    if layout_top_1["auto_split"] and layout_top_1["n_row2"] > 0:
        n_spill = layout_top_1["n_row2"]

        top_layer2_locked = st.session_state.get("_lock_reo_top_layer2", False)

        if top_layer2_locked:
            # User has explicitly controlled Layer 2 (including setting it to 0). Do not overwrite.
            st.session_state["_reo_msg_top_layer2_overwritten"] = True
        else:
            # Layer 1 forced a split - auto-update Layer 2
            if top_layer2_was_manual:
                st.session_state["_reo_msg_top_layer2_overwritten"] = True
            else:
                st.session_state["_reo_msg_top_auto_layer2"] = True

            st.session_state["nb_or_s_top_2"] = float(n_spill)
            st.session_state["db_top_2"] = db_top_1
            nb_or_s_top_2 = float(n_spill)
            db_top_2 = db_top_1
            top_layer2_was_auto = True
    # Otherwise, Layer 2 remains as user-defined (or 0)
    
    # Track warnings from layout
    if layout_top_1.get("warning"):
        if "cannot fit" in layout_top_1["warning"].lower() or "invalid" in layout_top_1["warning"].lower():
            st.session_state["_reo_error_top_1"] = True
        elif "spacing" in layout_top_1["warning"].lower():
            st.session_state["_reo_warning_top_1"] = layout_top_1["warning"]
            st.session_state["_reo_s_min_top_1"] = layout_top_1.get("s_min", s_min_top)
    
    # Compute layout for Layer 2 (if it has bars)
    layout_top_2 = None
    if nb_or_s_top_2 > 0:
        s_min_top_2 = max(db_top_2, s_min_default)
        layout_top_2 = compute_bar_layout_pure(
            b=b, cover_side=cover_side, nb_or_s=nb_or_s_top_2,
            db=db_top_2, s_min=s_min_top_2, rowgap=rowgap_top
        )
    
    # Total top bars = Layer 1 + Layer 2
    n_top_total = layout_top_1["n_total"]
    if layout_top_2:
        n_top_total += layout_top_2["n_total"]
    
    # ---------- 3.3 Write back legacy derived values (for backward compatibility) ----------
    st.session_state["nb_bot"] = n_bot_total
    st.session_state["nb_top"] = n_top_total
    st.session_state["db_bot"] = db_bot_1  # Use Layer 1 diameter as primary
    st.session_state["db_top"] = db_top_1  # Use Layer 1 diameter as primary
    
    # Legacy spacing values
    st.session_state["s_bot"] = layout_bot_1.get("s_actual", 200.0)
    st.session_state["s_top"] = layout_top_1.get("s_actual", 200.0)
    
    # Legacy bot_entry/top_entry for migration
    st.session_state["bot_entry"] = nb_or_s_bot_1
    st.session_state["top_entry"] = nb_or_s_top_1

    # Store modes in derived (if you have a derived dict, otherwise skip)
    # For now we'll skip since the current code doesn't use a separate derived dict

    # ---------- 3.2 Duct summary (results, not derived) ----------
    n_ducts = _coalesce_num(st.session_state.get("n_ducts", 0.0), 0.0)
    duct_dia = _coalesce_num(st.session_state.get("duct_dia", 0.0), 0.0)

    if n_ducts > 0.0 and duct_dia > 0.0:
        sum_duct = n_ducts * duct_dia               # mm
        A_duct_total = n_ducts * math.pi * duct_dia**2 / 4.0  # mm²
    else:
        sum_duct = 0.0
        A_duct_total = 0.0

    update_results(sum_duct=sum_duct, A_duct_total=A_duct_total)

    # ---------- 3.3 Time-dependent inputs ----------
    # For now we only normalise / store them; the creep/shrinkage pages
    # will pick them up via get_param().
    t_creep = _coalesce_num(st.session_state.get("t_creep", 365.0), 365.0)
    age_at_loading = _coalesce_num(st.session_state.get("age_at_loading", 28.0), 28.0)
    stress_ratio = _coalesce_num(st.session_state.get("stress_ratio", 0.3), 0.3)
    t_shrink = _coalesce_num(st.session_state.get("t_shrink", 365.0), 365.0)

    st.session_state["t_creep"] = t_creep
    st.session_state["age_at_loading"] = age_at_loading
    st.session_state["stress_ratio"] = stress_ratio
    st.session_state["t_shrink"] = t_shrink

    # ---------- 3.3 Actions wiring (ULS vs SLS) ----------
    actions_source = st.session_state.get("actions_source", "")
    M_sfd = st.session_state.get("sfd_Mmax_abs_kNm", None)
    V_sfd = st.session_state.get("sfd_Vmax_abs_kN", None)
    use_sfd = (
        actions_source == "Teaching SFD/BMD page (|M|max, |V|max)"
        and M_sfd is not None
        and V_sfd is not None
    )
    if use_sfd:
        uls_M = float(M_sfd)
        uls_V = float(V_sfd)
    else:
        uls_M = float(st.session_state.get("uls_Mstar", 0.0) or 0.0)
        uls_V = float(st.session_state.get("uls_Vstar", 0.0) or 0.0)
    uls_N = float(st.session_state.get("uls_Nstar", 0.0) or 0.0)

    sls_M = float(st.session_state.get("sls_Mstar", 0.0) or 0.0)
    sls_V = float(st.session_state.get("sls_Vstar", 0.0) or 0.0)
    sls_N = float(st.session_state.get("sls_Nstar", 0.0) or 0.0)

    actions_uls = {"N": uls_N, "V": uls_V, "M": uls_M}
    actions_sls = {"N": sls_N, "V": sls_V, "M": sls_M}

    st.session_state["actions_uls"] = dict(actions_uls)
    st.session_state["actions_sls"] = dict(actions_sls)

    # --- DEBUG: Confirm ULS/SLS separation ---
    debug_print(
        "[DEBUG ACTION KEYS] ULS:",
        st.session_state.get("uls_Nstar"),
        st.session_state.get("uls_Vstar"),
        st.session_state.get("uls_Mstar"),
    )

    debug_print(
        "[DEBUG ACTION KEYS] SLS:",
        st.session_state.get("sls_Nstar"),
        st.session_state.get("sls_Vstar"),
        st.session_state.get("sls_Mstar"),
    )

    debug_print(
        "[DEBUG ACTION IDS]",
        "actions_uls id =", id(st.session_state.get("actions_uls")),
        "| actions_sls id =", id(st.session_state.get("actions_sls")),
    )
    # ----------------------------------------

    update_results(
        actions_bending=actions_uls,
        actions_shear=actions_uls,
        actions_crack=actions_sls,
        actions_deflection=actions_sls,
    )

    try:
        debug_print("[ACTIONS IDS]", id(st.session_state["actions_uls"]), id(st.session_state["actions_sls"]))
        if (
            st.session_state.get("uls_Mstar") == st.session_state.get("sls_Mstar")
            and (
                st.session_state.get("uls_Nstar") != 0
                or st.session_state.get("sls_Nstar") != 0
                or st.session_state.get("uls_Vstar") != 0
                or st.session_state.get("sls_Vstar") != 0
                or st.session_state.get("uls_Mstar") != 0
                or st.session_state.get("sls_Mstar") != 0
            )
        ):
            debug_print("[WARN] ULS and SLS actions are identical. Check mapping if unexpected.")
    except Exception:
        pass

    # Effective depths (to centroid of Layer 1 bars)
    st.session_state["d"] = D - cover_bot - db_bot_1 / 2.0
    st.session_state["do"] = D - cover_top - db_top_1 / 2.0

    # Steel areas - sum both layers
    Ast_bot_1 = layout_bot_1["n_total"] * math.pi * db_bot_1**2 / 4.0
    Ast_bot_2 = layout_bot_2["n_total"] * math.pi * db_bot_2**2 / 4.0 if layout_bot_2 else 0.0
    Ast_bot_total = Ast_bot_1 + Ast_bot_2
    
    Ast_top_1 = layout_top_1["n_total"] * math.pi * db_top_1**2 / 4.0
    Ast_top_2 = layout_top_2["n_total"] * math.pi * db_top_2**2 / 4.0 if layout_top_2 else 0.0
    Ast_top_total = Ast_top_1 + Ast_top_2
    
    st.session_state["Ast_bot"] = Ast_bot_total
    st.session_state["Ast_top"] = Ast_top_total
    
    # ---------- 3.4 Compute effective design load F_d,ef from V, L, support type (Manual inputs only) ----------
    actions_source = st.session_state.get("actions_source", "")
    if actions_source == "Manual design actions (inputs below)":
        # Get design shear V (kN)
        V_kN = st.session_state.get("Vu_star", 0.0)
        if V_kN is None:
            V_kN = 0.0
        
        # Get span L (m) - prefer defl_L_eff, fallback to span_L_m
        L_m = st.session_state.get("defl_L_eff", 0.0)
        if L_m is None or L_m <= 0:
            L_m = st.session_state.get("span_L_m", 0.0)
            if L_m is None:
                L_m = 0.0
        
        # Get support type
        support_type = st.session_state.get("defl_support_type", "Simply supported")
        
        # Compute equivalent UDL w (kN/m) based on support type
        w_kNm = None
        if L_m > 0 and V_kN > 0:
            if support_type == "Simply supported":
                # For simply supported beam with UDL: V_max = wL/2, so w = 2V/L
                w_kNm = 2.0 * V_kN / L_m
            elif support_type == "Cantilever":
                # For cantilever with UDL: V_max = wL, so w = V/L
                w_kNm = V_kN / L_m
            # For other support types, keep as None (not yet implemented)
        
        # Store computed value (use update_results to maintain contract)
        if w_kNm is not None:
            update_results(fd_ef_calc_kNm=w_kNm)
        else:
            update_results(fd_ef_calc_kNm=0.0)
    else:
        # Not in manual mode - clear computed value
        update_results(fd_ef_calc_kNm=0.0)


def reset_results_state():
    """Reset derived outputs to defaults (safe, does not touch inputs)."""
    for k, v in RESULT_DEFAULTS.items():
        st.session_state[k] = v


# ============================================
# 4. SYNC CALLBACKS
# ============================================

# Shared keys that must ONLY be written by INPUTS page widgets (inputs_* keys)
# Keep this list *small* and limited to "Inputs owns this" selectors.
# Shared keys that must remain Inputs-owned (avoid accidental overwrite during restore)
# Keep this list SMALL (only mode selectors / time-dependent inputs).
PROTECTED_SHARED_KEYS = {
    "t_creep", "age_at_loading", "stress_ratio", "t_shrink",
    "actions_source",
    "loads_edit_mode",
}

_SYNC_CALLBACKS = None  # module-global


def _make_sync_callback(widget_key: str, shared_key: str):
    """
    Callback: widget → shared → all other widgets for that shared key.
    Also updates derived values (RULE 3).
    """
    # Capture filename for audit trail
    _this_file = os.path.basename(__file__)
    
    def _callback():
        # 0) SYNC LOCK: Do not push widget → shared during hydration / render
        if st.session_state.get("_sync_lock", False):
            try:
                _write_sync_trace_line(
                    f"BLOCKED callback (sync_lock) widget={widget_key} -> shared={shared_key}"
                )
            except Exception:
                pass
            _sync_trace_file("return:sync_locked", widget_key, shared_key, None, None)
            _sync_trace("sync_locked", widget_key, shared_key)
            return

        # Safety check: validate shared_key exists in TAB_KEYS (should never fail, but catch programming errors)
        if shared_key is None:
            _sync_trace_file("return:no_tab_keys_mapping", widget_key, None, None, None)
            return

        # Guard: only allow sync from known TAB_KEYS widget keys
        if widget_key not in TAB_KEYS:
            try:
                blocked = st.session_state.get("_blocked_sync_attempts", [])
                blocked.append({
                    "widget_key": widget_key,
                    "shared_key": shared_key,
                    "page": st.session_state.get("page_slug"),
                    "ts": time.time(),
                    "reason": "widget_key_not_allowed",
                })
                st.session_state["_blocked_sync_attempts"] = blocked[-100:]
            except Exception:
                pass
            _sync_trace_file("return:widget_key_not_allowed", widget_key, shared_key, None, None)
            return
        
        # Read widget and shared values early for tracing
        widget_val = st.session_state.get(widget_key)
        shared_val = st.session_state.get(shared_key, None)
        # #region agent log
        if shared_key in ("Mu_star_manual", "Vu_star_manual"):
            try:
                import json
                log_path = "/Users/jonathonleggo/Library/CloudStorage/OneDrive-Personal/Documents/GitHub/blank-app/.cursor/debug.log"
                with open(log_path, "a", encoding="utf-8") as f:
                    f.write(json.dumps({
                        "location": "state_and_helpers.py:sync_callback_entry",
                        "message": "Sync entry for manual actions",
                        "data": {
                            "widget_key": widget_key,
                            "shared_key": shared_key,
                            "widget_val": widget_val,
                            "shared_val": shared_val,
                            "last_user_widget": st.session_state.get("_last_user_widget_key"),
                            "rendered": widget_key in st.session_state.get("_rendered_widget_keys", set()),
                        },
                        "timestamp": int(time.time() * 1000),
                        "sessionId": "debug-session",
                        "runId": st.session_state.get("_boot_id", "run"),
                        "hypothesisId": "H2",
                    }) + "\n")
            except Exception:
                pass
        # #endregion
        
        # 0.5) RESTORE GUARD: briefly block widget→shared right after restore
        if st.session_state.get("_restored_from_snapshot") and st.session_state.get("_restore_guard_active"):
            ts = st.session_state.get("_restore_guard_ts")
            # If no timestamp, set one now (first hit)
            if ts is None:
                st.session_state["_restore_guard_ts"] = time.time()
                _sync_trace_file("return:restore_guard", widget_key, shared_key, widget_val, shared_val)
                _sync_trace("restore_guard_active", widget_key, shared_key)
                return

            # Block only during grace window
            if (time.time() - float(ts)) < 0.75:
                _sync_trace_file("return:restore_guard", widget_key, shared_key, widget_val, shared_val)
                _sync_trace("restore_guard_active", widget_key, shared_key)
                return

            # Grace window passed → permanently release guard
            st.session_state["_restore_guard_active"] = False
        
        # --- hard gate: only accept callback if user actually edited this widget ---
        last_widget = st.session_state.get("_last_user_widget_key")
        if last_widget is not None and last_widget != widget_key:
            # This callback was triggered by programmatic widget key reset / rerender.
            # Never push to shared.
            _sync_trace_file("return:not_last_user_widget", widget_key, shared_key, widget_val, shared_val)
            _sync_trace("not_user_edit", widget_key, shared_key)
            return
        
        # Guard B: Only sync if widget was rendered this run
        rendered = st.session_state.get("_rendered_widget_keys", set())
        if widget_key not in rendered:
            _sync_trace_file("return:widget_not_rendered", widget_key, shared_key, widget_val, shared_val)
            _sync_trace("widget_not_rendered", widget_key, shared_key)
            return
        
        # Guard B: Only sync if widget value differs from shared value (prevents spam)
        if widget_val is None:
            _sync_trace_file("return:widget_val_none", widget_key, shared_key, widget_val, shared_val)
            _sync_trace("widget_val_is_none", widget_key, shared_key)
            return
        
        # Normalize types for common int-like reo inputs (prevents float/int mismatch noise)
        INT_SHARED_KEYS = {
            "db_bot_1", "db_bot_2", "db_top_1", "db_top_2",
            "lig_d", "lig_legs",
            "top1_count", "top2_count", "bot1_count", "bot2_count",
            "top1_spacing", "top2_spacing", "bot1_spacing", "bot2_spacing",
        }
        
        if shared_key in INT_SHARED_KEYS and widget_val is not None:
            try:
                widget_val = int(widget_val)
            except Exception:
                pass
        
        if widget_val == shared_val:
            _sync_trace_file("return:widget_equals_shared", widget_key, shared_key, widget_val, shared_val)
            _sync_trace("no_change", widget_key, shared_key)
            return  # No change, skip sync
        
        # --- Guard: prevent default zeros overwriting meaningful shared values ---
        # IMPORTANT: for many design inputs, 0 is a valid user choice (e.g. 0 bars, 0 legs, 0 ducts)
        ZERO_ALLOWED_SHARED_KEYS = {
            # Reinforcement layer counts (0 = layer off)
            "bot1_count", "bot2_count", "top1_count", "top2_count",
            # Shear links (0 legs may be valid during setup)
            "lig_legs",
            # Prestressing ducts (0 = none)
            "n_ducts", "duct_dia",
            # Manual design actions can be 0
            "Mu_star_manual", "Vu_star_manual",
        }
        
        if widget_val == 0 and shared_val not in (None, 0) and shared_key not in ZERO_ALLOWED_SHARED_KEYS:
            # #region agent log
            if shared_key in ("Mu_star_manual", "Vu_star_manual"):
                try:
                    import json
                    log_path = "/Users/jonathonleggo/Library/CloudStorage/OneDrive-Personal/Documents/GitHub/blank-app/.cursor/debug.log"
                    with open(log_path, "a", encoding="utf-8") as f:
                        f.write(json.dumps({
                            "location": "state_and_helpers.py:sync_callback_guard",
                            "message": "Blocked zero write to shared",
                            "data": {
                                "widget_key": widget_key,
                                "shared_key": shared_key,
                                "widget_val": widget_val,
                                "shared_val": shared_val,
                                "guard_list": list(ZERO_ALLOWED_SHARED_KEYS),
                            },
                            "timestamp": int(time.time() * 1000),
                            "sessionId": "debug-session",
                            "runId": st.session_state.get("_boot_id", "run"),
                            "hypothesisId": "H2",
                        }) + "\n")
                except Exception:
                    pass
            # #endregion
            _sync_trace_file("return:widget_default_zero", widget_key, shared_key, widget_val, shared_val)
            return

            # Time-dependent protection (1 default)
            if shared_key in {"t_creep", "age_at_loading", "t_shrink"}:
                try:
                    wv = float(widget_val)
                    sv = float(shared_val)
                except Exception:
                    wv, sv = None, None

                # If widget is still at stale default 0/1 but shared is meaningful (>1), do not overwrite
                if wv in (0.0, 1.0) and (sv is not None and sv not in (0.0, 1.0)):
                    _sync_trace_file("return:time_default_stale", widget_key, shared_key, widget_val, shared_val)
                    _sync_trace("time_default_stale", widget_key, shared_key)
                    return
        
        # 1) If the widget key isn't present, do NOT write anything.
        if widget_key not in st.session_state:
            _sync_trace_file("return:widget_key_missing", widget_key, shared_key, None, shared_val)
            # Audit why we skipped (optional)
            tail = st.session_state.get("_shared_write_audit", [])
            frame = inspect.currentframe()
            lineno = frame.f_lineno if frame else 0
            tail.append({
                "t": round(time.time(), 3),
                "key": shared_key,
                "val": "<SKIPPED: widget missing>",
                "source": "sync_callback_skip",
                "where": f"{_this_file}:{lineno} _callback",
                "widget_key": widget_key,
            })
            st.session_state["_shared_write_audit"] = tail[-50:]
            
            # Debug: store sync attempt info
            st.session_state["_debug_last_sync"] = {
                "shared_key": shared_key,
                "widget_key": widget_key,
                "widget_present": False,
                "widget_val": None,
            }
            return
        
        # 2) Read the widget value as-is (do not coerce falsy to 0)
        widget_val = st.session_state[widget_key]
        # Update shared_val now that we have the actual widget value
        shared_val = st.session_state.get(shared_key, None)
        
        # Normalize types for common int-like reo inputs (prevents float/int mismatch noise)
        INT_SHARED_KEYS = {
            "db_bot_1", "db_bot_2", "db_top_1", "db_top_2",
            "lig_d", "lig_legs",
            "top1_count", "top2_count", "bot1_count", "bot2_count",
            "top1_spacing", "top2_spacing", "bot1_spacing", "bot2_spacing",
        }
        
        if shared_key in INT_SHARED_KEYS and widget_val is not None:
            try:
                widget_val = int(widget_val)
            except Exception:
                pass
        
        # Debug: store sync attempt info
        st.session_state["_debug_last_sync"] = {
            "shared_key": shared_key,
            "widget_key": widget_key,
            "widget_present": True,
            "widget_val": widget_val,
        }
        
        # NOTE: User edit marker is set by widget wrapper, not here
        # (prevents callbacks from marking themselves as user edits)
        
        # 3) widget → shared
        widget_value = widget_val
        current_shared = st.session_state.get(shared_key)
        
        # ---- HARD GUARD: time inputs must not be clobbered by stale widget defaults ----
        if shared_key in {"t_creep", "age_at_loading", "t_shrink"}:
            try:
                wv = float(widget_value) if widget_value is not None else None
                sv0 = st.session_state.get(shared_key)
                sv = float(sv0) if sv0 is not None else None
            except Exception:
                wv, sv = None, None

            # If widget is still at 0/1 but shared is meaningful (>1), do not overwrite shared
            if wv in (0.0, 1.0) and (sv is not None and sv not in (0.0, 1.0)):
                _sync_trace_file("return:time_stale_hard_guard", widget_key, shared_key, widget_value, current_shared)
                _audit("sync_callback_blocked", shared_key, widget_key, old=current_shared, new=widget_value, extra={"where": "sync_callback"})
                return
        
        # Block overwrite-to-zero for protected keys (but allow 0 for zero-allowed keys)
        protected = (shared_key in NONZERO_REQUIRED_SHARED_KEYS) and (not zero_allowed(shared_key))
        if protected:
            shared_is_meaningful = current_shared not in (None, "", 0, 0.0)
            widget_is_zero = widget_value in (None, "", 0, 0.0)
            if shared_is_meaningful and widget_is_zero:
                # Block: don't overwrite meaningful shared value with zero
                _sync_trace_file("return:protected_from_zero", widget_key, shared_key, widget_value, current_shared)
                _audit("SYNC BLOCKED zero", shared_key, widget_key, old=current_shared, new=widget_value, extra={"reason": "protected_from_zero"})
                return
        
        # Always allow core geometry/material keys to be edited from any page
        ALWAYS_EDITABLE_SHARED_KEYS = {"b", "bw", "D", "fc", "fsy", "L", "cover_top", "cover_bot"}
        if shared_key not in ALWAYS_EDITABLE_SHARED_KEYS:
            # Prevent non-input pages from clobbering protected shared inputs
            if shared_key in PROTECTED_SHARED_KEYS and not str(widget_key).startswith("inputs_"):
                _sync_trace_file("return:protected_shared_key", widget_key, shared_key, widget_value, current_shared)
                return

        TIME_STALE_KEYS = {"t_creep", "age_at_loading", "t_shrink"}

        # If we restored from snapshot, never let a stale widget value (1) overwrite a meaningful shared value
        if st.session_state.get("_restored_from_snapshot", False) and shared_key in TIME_STALE_KEYS:
            try:
                current_shared = st.session_state.get(shared_key)
                wv = widget_value
                if (wv == 1 or wv == 1.0) and (current_shared not in (None, 0, 0.0, 1, 1.0, "")):
                    _sync_trace_file("return:restore_stale_time", widget_key, shared_key, widget_value, current_shared)
                    _audit("SYNC blocked stale time overwrite", shared_key, widget_key, old=current_shared, new=wv)
                return
            except Exception:
                pass
        
        old_shared = current_shared
        _sync_trace_file("write:widget_to_shared", widget_key, shared_key, widget_value, old_shared)
        set_shared(shared_key, widget_value, source=f"callback:{widget_key}")
        _audit("SYNC widget->shared", shared_key, widget_key, old=old_shared, new=widget_value)
        mark_dirty("widget_sync")

        if shared_key in ("load_Mstar_proxy", "load_Vstar_proxy", "load_Nstar_proxy"):
            save_proxies_to_active_set()
        
        if shared_key in ("Mu_star_manual", "Vu_star_manual", "N_star"):
            if shared_key == "Mu_star_manual":
                set_shared("uls_Mstar", float(widget_value or 0.0), source="uls_mirror")
                if st.session_state.get("loads_edit_mode", "ULS") == "ULS":
                    st.session_state["load_Mstar_proxy"] = float(widget_value or 0.0)
            elif shared_key == "Vu_star_manual":
                set_shared("uls_Vstar", float(widget_value or 0.0), source="uls_mirror")
                if st.session_state.get("loads_edit_mode", "ULS") == "ULS":
                    st.session_state["load_Vstar_proxy"] = float(widget_value or 0.0)
            elif shared_key == "N_star":
                set_shared("uls_Nstar", float(widget_value or 0.0), source="uls_mirror")
                if st.session_state.get("loads_edit_mode", "ULS") == "ULS":
                    st.session_state["load_Nstar_proxy"] = float(widget_value or 0.0)
        
        # Cache inputs_* widget values immediately when user changes them
        # AND also keep the "inputs_* cache" fresh even when the user edits the same
        # shared value from other pages (bending_*, shear_*, etc.).
        if widget_key.startswith("inputs_"):
            st.session_state[f"_cached_{widget_key}"] = st.session_state[widget_key]

        # NEW: mirror the latest shared value into ALL inputs_* caches for this shared_key.
        # This prevents stale cached inputs values from re-seeding as 0 after page swaps.
        for w_key, sh_key in TAB_KEYS.items():
            if sh_key == shared_key and w_key.startswith("inputs_"):
                st.session_state[f"_cached_{w_key}"] = st.session_state[shared_key]

        # Mark Layer-2 reo inputs as user-controlled once the user touches them.
        # This prevents recalc_derived_values() from auto-overwriting them later.
        if shared_key in ("nb_or_s_bot_2", "db_bot_2"):
            st.session_state["_lock_reo_bot_layer2"] = True
        if shared_key in ("nb_or_s_top_2", "db_top_2"):
            st.session_state["_lock_reo_top_layer2"] = True

        # NOTE: We do NOT mirror shared → all other widget copies here.
        # Other pages will pick up the shared value via hydrate_active_page_widgets_from_shared()
        # when they render. This prevents callback cascades and phantom zeros.

        # 2) Update derived values whenever anything changes
        recalc_derived_values()

    return _callback


def get_sync_callbacks():
    """
    Return the dict {widget_key: callback} for use in on_change=...
    Ensures a single shared set of callbacks for the whole app.
    """
    global _SYNC_CALLBACKS

    # Rebuild if not yet created or if TAB_KEYS has changed (e.g. new widget keys added)
    if (
        _SYNC_CALLBACKS is None
        or len(_SYNC_CALLBACKS) != len(TAB_KEYS)
        or any(w_key not in _SYNC_CALLBACKS for w_key in TAB_KEYS.keys())
    ):
        _SYNC_CALLBACKS = {
            w_key: _make_sync_callback(w_key, sh_key)
            for w_key, sh_key in TAB_KEYS.items()
        }
    
    # Debug-only: validate contract after building callbacks
    try:
        from src.debug.state_debug import is_debug_enabled
        if is_debug_enabled():
            validate_session_state_contract(context="inside get_sync_callbacks")
    except (ImportError, NameError):
        # Debug module not available, skip validation
        pass
    
    return _SYNC_CALLBACKS


# ============================================
# 5. RESULT UPDATE HELPER (RULE 4)
# ============================================

def update_results(*args, **kwargs):
    """
    Safely update result values (phi_Mu_cap, Mu_utilisation, shrinkage,
    creep, crack summaries, etc.).

    Only accepts keys listed in RESULT_KEYS (computed outputs, not user inputs).
    For updating shared inputs, use widget callbacks or direct session_state writes
    (inputs are managed via TAB_KEYS and sync callbacks).
    """
    if args:
        if len(args) != 2 or not isinstance(args[0], str) or not isinstance(args[1], dict):
            raise TypeError("update_results(bucket: str, data: dict) expects (str, dict)")
        _store_results_bucket(args[0], args[1])
        return

    # Wrap with debug guard in debug mode
    try:
        from src.debug.state_debug import guard_session_writes, is_debug_enabled
        if is_debug_enabled():
            with guard_session_writes(allowed_keys=RESULT_KEYS, context="update_results"):
                _update_results_impl(**kwargs)
        else:
            _update_results_impl(**kwargs)
    except (ImportError, NameError):
        # Debug module not available, use normal path
        _update_results_impl(**kwargs)


def compute_all_results() -> None:
    """
    Compute ALL derived + result outputs in one place.
    This is the single source of truth for results freshness.

    RULES:
    - Derived values ONLY updated via recalc_derived_values()
    - Results ONLY published via update_results() (called inside core compute fns)
    """
    # 1) Derived values (d, Ast, layouts, etc.)
    recalc_derived_values()

    # 2) Core checks (ULS/SLS)
    # Prefer design-core modules (no UI / no render side-effects)
    try:
        from bending_core import _compute_bending_capacity
        _compute_bending_capacity()
    except Exception:
        pass

    try:
        from shear_core import _compute_shear_capacity
        _compute_shear_capacity()
    except Exception:
        pass

    # SLS steel stress feeding crack/deflection
    # (Currently lives in bending_page; keep it here to avoid waiting for Bending page)
    try:
        from bending_page import _compute_sls_bending_values
        _compute_sls_bending_values()
    except Exception:
        pass

    # Time-dependent inputs feeding crack/deflection
    try:
        from creep import compute_creep_results
        compute_creep_results(publish=True)
    except Exception:
        pass

    try:
        from shrinkage import compute_shrinkage_results
        compute_shrinkage_results(publish=True)
    except Exception:
        pass

    # Crack + deflection (depend on sigma_s_sls / creep / shrinkage)
    try:
        from crack_core import _compute_crack_results
        _compute_crack_results()
    except Exception:
        pass

    try:
        from deflection_core import _compute_deflection_results
        _compute_deflection_results()
    except Exception:
        pass


def _update_results_impl(**kwargs):
    """Internal implementation of update_results (separated for debug guard wrapping)."""
    global RESULT_KEYS, RESULT_DEFAULTS
    
    # Backward-compat: fold Vu_star_kN into Vu_star and remove the legacy key
    if "Vu_star_kN" in kwargs:
        if "Vu_star" not in kwargs:
            kwargs["Vu_star"] = kwargs.get("Vu_star_kN")
        del kwargs["Vu_star_kN"]

    # Debug: prove action keys are present at runtime
    st.session_state["_debug_actions_keys_in_RESULT_KEYS"] = all(
        k in RESULT_KEYS for k in ("actions_source", "Mu_star", "Mu_star_kNm", "Vu_star")
    )
    
    allowed = RESULT_KEYS
    unknown = set(kwargs.keys()) - allowed
    if unknown:
        # Auto-register unknown keys in debug mode only (prevents whack-a-mole during development)
        try:
            from src.debug.state_debug import is_debug_enabled
            if is_debug_enabled():
                # Auto-register in debug only
                RESULT_KEYS |= unknown
                for k in unknown:
                    if k not in RESULT_DEFAULTS:
                        RESULT_DEFAULTS[k] = 0.0
                    if k not in st.session_state:
                        st.session_state[k] = RESULT_DEFAULTS[k]
                st.session_state["_debug_auto_registered_results"] = sorted(list(unknown))
                # Log the auto-registration
                import json
                import os
                log_path = "/Users/jonathonleggo/Library/CloudStorage/OneDrive-Personal/Documents/GitHub/blank-app/.cursor/debug.log"
                try:
                    with open(log_path, "a") as f:
                        f.write(json.dumps({
                            "location": "state_and_helpers.py:_update_results_impl",
                            "message": "Auto-registered unknown result keys (debug mode)",
                            "data": {"unknown_keys": sorted(list(unknown))},
                            "timestamp": __import__("time").time() * 1000,
                            "sessionId": "debug-session",
                            "runId": "run1",
                            "hypothesisId": "AUTO_REGISTER"
                        }) + "\n")
                except:
                    pass
            else:
                raise KeyError(
                    f"[SESSION STATE CONTRACT] Tried to update unknown RESULT key(s) {unknown}.\n"
                    f"Add them to RESULT_KEYS/RESULT_DEFAULTS before using update_results()."
                )
        except (ImportError, NameError):
            # Debug module not available, use strict mode
            raise KeyError(
                f"[SESSION STATE CONTRACT] Tried to update unknown RESULT key(s) {unknown}.\n"
                f"Add them to RESULT_KEYS/RESULT_DEFAULTS before using update_results()."
            )
    
    # Update session_state with the provided values
    for k, v in kwargs.items():
        st.session_state[k] = v

    # Cleanup legacy key if present in session state
    if "Vu_star_kN" in st.session_state:
        try:
            del st.session_state["Vu_star_kN"]
        except Exception:
            pass
    
    # --- ARCHITECTURE LOCK: ensure results pipeline exists ---
    _assert_results_pipeline()


# ============================================
# 6. SMALL HELPERS
# ============================================

def _assert_results_pipeline():
    """Dev-only assertion: ensure results dict exists (initialize if needed)."""
    if not st.session_state.get("_dev_mode", False):
        return
    # Initialize results dict if it doesn't exist
    if "results" not in st.session_state:
        st.session_state["results"] = {}


def _store_results_bucket(bucket: str, data: dict) -> None:
    """Store cached results and update metadata timestamp."""
    st.session_state.setdefault("results", {})
    st.session_state.setdefault("results_meta", {})
    st.session_state["results"][bucket] = data
    st.session_state["results_meta"][bucket] = {"updated_at": time.time()}

def get_param(name: str, default=None):
    """
    Safe accessor for shared parameters from session_state.
    Treats None as "not set" and returns the default instead.
    """
    if name in st.session_state:
        value = st.session_state[name]
        # Treat None as "not set" - return default instead
        if value is not None:
            return value
    
    # Key not in session_state, or value is None - check SHARED_DEFAULTS
    shared_default = SHARED_DEFAULTS.get(name, default)
    # If SHARED_DEFAULTS also has None, treat it as "not set" and use the provided default
    if shared_default is not None:
        return shared_default
    return default


def _critical_input_keys():
    """List of critical input keys that must never be overwritten with snippet defaults."""
    return [
        "b", "D", "L",
        "fc", "fsy", "Ec", "Es",

        # Design actions (manual inputs)
        "actions_source",
        "Mu_star_manual", "Vu_star_manual", "Tu_star",
        "P_star", "N_star",

        # Covers / geometry-related
        "cover_bot", "cover_top", "cover_side",

        # Shear reinforcement inputs
        "lig_d", "lig_legs", "s_lig",

        # Ducts / voids
        "n_ducts", "duct_dia",

        # Time-dependent inputs
        "t_creep", "t_shrink",
    ]


def _is_snippet_defaults_state(ss) -> bool:
    """
    Detect the exact bogus 'snippet defaults' state we keep seeing.
    We use BOTH a signature match and a sanity-range check.
    """
    def f(k, d=0.0):
        try:
            return float(ss.get(k, d))
        except Exception:
            return d

    b  = f("b")
    D  = f("D")
    L  = f("L")
    fc = f("fc")
    fsy = f("fsy")
    Ec = f("Ec")
    Es = f("Es")

    # Exact signature (from your screenshot)
    signature = (
        abs(b - 10.0) < 1e-9 and
        abs(D - 10.0) < 1e-9 and
        abs(L - 100.0) < 1e-9 and
        abs(fc - 2.0) < 1e-9 and
        abs(fsy - 10.0) < 1e-9 and
        abs(Ec - 1000.0) < 1e-9 and
        abs(Es - 10000.0) < 1e-9
    )

    # Sanity check for mm/MPa typical ranges (detect impossible values)
    # Values that are too small to be realistic engineering inputs
    impossible = (b < 50) or (D < 50) or (L < 200) or (fc < 10) or (fsy < 200) or (Ec < 10000) or (Es < 100000)

    # Return True if we match the exact signature OR if values are impossibly small
    return signature or impossible


@st.cache_resource
def _global_state_store() -> dict:
    """
    Server-side singleton store. Survives per-user session resets
    as long as the server process stays alive.
    """
    return {}


def _snapshot_last_good_inputs():
    """Snapshot current input values as 'last good' state (session + global store)."""
    snap = {k: st.session_state.get(k) for k in _critical_input_keys()}
    st.session_state["_last_good_inputs"] = snap
    try:
        _global_state_store()["last_good_inputs"] = snap
    except Exception:
        pass


def _restore_last_good_inputs():
    """Restore shared and widget keys from last known good snapshot (session or global store)."""
    snap = st.session_state.get("_last_good_inputs")
    if not isinstance(snap, dict):
        try:
            snap = _global_state_store().get("last_good_inputs")
        except Exception:
            snap = None
    if not isinstance(snap, dict):
        return

    # Restore shared keys
    for k, v in snap.items():
        if v is not None:
            st.session_state[k] = v

    # Restore ALL widget keys mapped to these shared keys
    for widget_key, shared_key in TAB_KEYS.items():
        if shared_key in snap and snap[shared_key] is not None:
            st.session_state[widget_key] = snap[shared_key]


# ============================================
# SYNC LOCK (prevents mass-zero writes during render)
# ============================================

def is_sync_locked() -> bool:
    """Check if sync callbacks are locked (prevents widget→shared writes during hydration/render)."""
    return bool(st.session_state.get("_sync_lock", False))


# ============================================
# AUDIT TRAIL FOR SHARED INPUT WRITES
# ============================================

def mark_user_edit(widget_key: str, shared_key: str | None = None):
    """Mark that a user edited a widget (for mutation guard exemption)."""
    st.session_state["_last_user_edit_ts"] = time.time()
    st.session_state["_last_user_widget_key"] = widget_key
    # Latch: once user edits anything, never restore snapshot over live state again
    st.session_state["_user_has_edited_anything"] = True
    if shared_key:
        st.session_state["_last_user_shared_key"] = shared_key


def clear_user_edit_marker_each_run():
    """Clear user edit markers at the start of each rerun (prevents stale exemptions)."""
    st.session_state["_last_user_widget_key"] = None
    st.session_state["_last_user_shared_key"] = None
    st.session_state["_last_user_edit_ts"] = 0.0


def end_of_render_cleanup(active_page: str | None = None) -> None:
    """
    Called once at the end of app.py's render loop.

    Must be SAFE:
    - no shared writes
    - no widget seeding
    - only diagnostics / snapshot persistence if you already do that
    """
    # If you already have snapshot persistence / debug hooks, call them here.
    # Keep this function NO-OP safe for now.
    return


def _safe_repr(v):
    """Safe representation for debug dumps (rounds floats, handles exceptions)."""
    try:
        if isinstance(v, float):
            return round(v, 6)
        return v
    except Exception:
        return str(v)


def dump_session_state_inventory(page_name: str, sync_callbacks: dict | None = None, out_dir: str = "."):
    """
    Debug-only: dump actual session-state and widget/shared mapping consistency.
    Does not write to any shared keys.
    """
    import json
    from pathlib import Path
    from datetime import datetime
    from widgets_helpers import get_rendered_widget_keys

    rendered = get_rendered_widget_keys()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Collect session keys
    sess_keys = sorted(list(st.session_state.keys()))

    # Build widget->shared pairs
    pairs = []
    missing_shared = []
    for wk in rendered:
        sk = TAB_KEYS.get(wk)
        wv = st.session_state.get(wk, None)
        sv = st.session_state.get(sk, None) if sk else None

        pairs.append({
            "widget_key": wk,
            "widget_val": _safe_repr(wv),
            "widget_type": type(wv).__name__,
            "shared_key": sk,
            "shared_val": _safe_repr(sv),
            "shared_type": type(sv).__name__ if sk else None,
        })

        if sk and sk not in st.session_state:
            missing_shared.append(sk)

    # Detect unknown/stray keys
    shared_defaults = set(SHARED_DEFAULTS.keys())
    mapped_shared = set([p["shared_key"] for p in pairs if p["shared_key"]])

    stray_session_keys = [
        k for k in sess_keys
        if k not in shared_defaults
        and k not in rendered
        and k not in mapped_shared
        and not k.startswith("_")  # ignore internal
    ]

    # Text report
    report = {
        "timestamp": now,
        "page": page_name,
        "boot_id": st.session_state.get("_boot_id"),
        "fresh_boot": st.session_state.get("_fresh_boot"),
        "restored_from_snapshot": st.session_state.get("_restored_from_snapshot"),
        "rendered_widget_count": len(rendered),
        "session_key_count": len(sess_keys),
        "missing_shared_for_rendered": sorted(list(set(missing_shared))),
        "stray_session_keys": stray_session_keys[:200],  # cap output
        "pairs": pairs,
    }

    # Write txt + csv-like pairs
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    txt_path = out_dir / f"session_state_inventory_{page_name}.txt"
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write(json.dumps(report, indent=2, ensure_ascii=False))

    csv_path = out_dir / f"widget_shared_pairs_{page_name}.csv"
    with open(csv_path, "w", encoding="utf-8") as f:
        f.write("widget_key,widget_val,widget_type,shared_key,shared_val,shared_type\n")
        for p in pairs:
            f.write(
                f"{p['widget_key']},{p['widget_val']},{p['widget_type']},"
                f"{p['shared_key']},{p['shared_val']},{p['shared_type']}\n"
            )

    return str(txt_path), str(csv_path)


def _write_sync_trace_line(line: str, filename: str = "sync_callback_trace.txt") -> None:
    """Append one line to sync trace file (debug only)."""
    if not DEBUG_MODE:
        return
    try:
        path = DEBUG_OUT_DIR / filename
        with open(path, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def _sync_trace_file(
    reason: str,
    widget_key: str,
    shared_key: str | None,
    widget_val=None,
    shared_val=None,
):
    """Debug-only: record why a sync callback returned or wrote."""
    if not DEBUG_MODE:
        return
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    try:
        widget_type = type(widget_val).__name__ if widget_val is not None else "None"
        shared_type = type(shared_val).__name__ if shared_val is not None else "None"
        line = (
            f"{ts} | {reason} | "
            f"wk={widget_key} | sk={shared_key} | "
            f"wv={repr(widget_val)} ({widget_type}) | "
            f"sv={repr(shared_val)} ({shared_type}) | "
            f"last_user={st.session_state.get('_last_user_widget_key')} | "
            f"sync_lock={bool(st.session_state.get('_sync_lock', False))} | "
            f"restore_guard={bool(st.session_state.get('_restore_guard_active', False))} | "
            f"restored={bool(st.session_state.get('_restored_from_snapshot', False))}"
        )
        _write_sync_trace_line(line)
    except Exception:
        pass


def _sync_trace(reason: str, widget_key: str, shared_key: str | None = None):
    """Debug-only: record why sync callback returned (in-memory version)."""
    try:
        trace = st.session_state.get("_sync_trace", [])
        trace.append({
            "reason": reason,
            "widget_key": widget_key,
            "shared_key": shared_key,
            "sync_lock": bool(st.session_state.get("_sync_lock", False)),
            "restore_guard": bool(st.session_state.get("_restore_guard_active", False)),
            "restored_from_snapshot": bool(st.session_state.get("_restored_from_snapshot", False)),
            "last_user_widget": st.session_state.get("_last_user_widget_key"),
        })
        st.session_state["_sync_trace"] = trace[-200:]  # cap
    except Exception:
        pass


def widget_contract_audit(sync_callbacks: dict | None = None) -> dict:
    """Return audit info: rendered widget keys missing TAB_KEYS or missing callbacks."""
    from widgets_helpers import get_rendered_widget_keys
    
    rendered = get_rendered_widget_keys()

    missing_tab_keys = [k for k in rendered if k not in TAB_KEYS]
    missing_callbacks = []
    if sync_callbacks is not None:
        missing_callbacks = [k for k in rendered if k in TAB_KEYS and k not in sync_callbacks]

    return {
        "rendered_count": len(rendered),
        "missing_tab_keys": missing_tab_keys,
        "missing_callbacks": missing_callbacks,
    }


def write_widget_contract_audit_to_file(sync_callbacks: dict | None = None, filename: str = "widget_contract_audit.txt") -> str:
    """
    Write widget contract audit results to a debug file in the user's Documents folder.
    Returns the file path.
    """
    import os
    from pathlib import Path
    from datetime import datetime
    
    # Get user's Documents folder
    documents_path = Path.home() / "Documents"
    if not documents_path.exists():
        # Fallback: try OneDrive Documents
        documents_path = Path("/Users/jonathonleggo/Library/CloudStorage/OneDrive-Personal/Documents")
    
    audit_file = documents_path / filename
    
    # Get audit results
    audit = widget_contract_audit(sync_callbacks)
    
    # Get all rendered keys for reference
    from widgets_helpers import get_rendered_widget_keys
    rendered = get_rendered_widget_keys()
    
    # Write to file
    with open(audit_file, "w") as f:
        f.write("=" * 60 + "\n")
        f.write("Widget Contract Audit Report\n")
        f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write("=" * 60 + "\n\n")
        f.write(f"Total rendered widgets: {audit['rendered_count']}\n\n")
        
        if audit["missing_tab_keys"]:
            f.write(f"❌ Missing TAB_KEYS mappings: {len(audit['missing_tab_keys'])}\n")
            f.write("Keys:\n")
            for key in audit["missing_tab_keys"]:
                f.write(f"  - {key}\n")
            f.write("\n")
        else:
            f.write("✅ All rendered widget keys are in TAB_KEYS\n\n")
        
        if audit["missing_callbacks"]:
            f.write(f"❌ Missing sync callbacks: {len(audit['missing_callbacks'])}\n")
            f.write("Keys:\n")
            for key in audit["missing_callbacks"]:
                f.write(f"  - {key}\n")
            f.write("\n")
        else:
            f.write("✅ All rendered widgets have sync callbacks\n\n")
        
        # Also list all rendered keys for reference
        if rendered:
            f.write("All rendered widget keys:\n")
            for key in rendered:
                f.write(f"  - {key}\n")
    
    return str(audit_file)


def migrate_time_defaults_once():
    """
    One-time repair for historically-buggy time inputs that get restored as 0/1
    (snippet values) and then overwrite shared state via sync callbacks.

    We intentionally prefer realistic engineering defaults over stale snapshot
    values that were created by the old bug.
    """
    if st.session_state.get("_time_defaults_migrated_once", False):
        return

    # Realistic defaults (match AS3600 practice / typical design assumptions)
    DEFAULTS = {
        "t_creep": 365.0,         # days after loading
        "age_at_loading": 28.0,   # days (28-day strength basis)
        "stress_ratio": 0.30,     # sustained stress ratio (typical service range)
        "t_shrink": 365.0,        # days since drying
    }

    # Widget keys used on Inputs page (your TAB_KEYS maps these to shared keys)
    LEGACY_WIDGET_KEYS = {
        # Inputs page (legacy)
        "inputs_t_creep": "t_creep",
        "inputs_age_at_loading": "age_at_loading",
        "inputs_stress_ratio": "stress_ratio",
        "inputs_t_shrink": "t_shrink",

        # Creep page widgets
        "cr_t_creep": "t_creep",
        "cr_tau": "age_at_loading",
        "cr_sigma_ratio": "stress_ratio",

        # Shrinkage page widget
        "sh_t_days": "t_shrink",
    }

    def _is_stale_snippet(v) -> bool:
        # Old bug commonly restored these as 0 or 1 (or None/NaN)
        try:
            if v is None:
                return True
            fv = float(v)
            if math.isnan(fv):
                return True
            return fv in (0.0, 1.0)
        except Exception:
            return True

    # 1) Repair shared values first
    for sk, dv in DEFAULTS.items():
        if sk not in st.session_state or _is_stale_snippet(st.session_state.get(sk)):
            st.session_state[sk] = float(dv)

    # 2) Repair legacy widget keys if they exist in session_state
    #    (prevents widgets showing 1/0 and then syncing back into shared)
    for wk, sk in LEGACY_WIDGET_KEYS.items():
        if wk in st.session_state and _is_stale_snippet(st.session_state.get(wk)):
            st.session_state[wk] = float(st.session_state[sk])

    # 3) Repair common creep/shrinkage page widgets that sometimes restore as 0
    #    (b, D, fc, Ec) – only if 0 is clearly stale and shared has a real value.
    STICKY_WIDGETS = {
        "cr_b": "b",
        "cr_D": "D",
        "cr_fc": "fc",
        "cr_Ec": "Ec",
        "sh_b": "b",
        "sh_D": "D",
        "sh_fc": "fc",
    }

    for wk, sk in STICKY_WIDGETS.items():
        if wk in st.session_state:
            try:
                wv = st.session_state.get(wk)
                sv = st.session_state.get(sk)
                dv = DEFAULTS.get(sk, SHARED_DEFAULTS.get(sk, None))

                # treat 0/1/None/NaN as stale (same as _is_stale_snippet)
                if _is_stale_snippet(wv):
                    # only overwrite if the shared value is not stale
                    if not _is_stale_snippet(sv):
                        st.session_state[wk] = sv
                    # else fall back to default if available
                    elif dv is not None:
                        st.session_state[wk] = float(dv)
            except Exception:
                pass

    st.session_state["_time_defaults_migrated_once"] = True


def set_shared(key: str, value, *, source: str = "") -> None:
    """
    The only allowed way to write shared inputs (SHARED_DEFAULTS keys).
    All writes are audited for debugging.
    """
    # HARD GUARD: block render-time writes
    if st.session_state.get("_sync_lock", False):
        try:
            _write_sync_trace_line(
                f"BLOCKED set_shared (sync_lock) key={key} val={value} source={source}"
            )
        except Exception:
            pass
        return

    if key not in SHARED_DEFAULTS:
        raise KeyError(f"set_shared: '{key}' not in SHARED_DEFAULTS (source={source})")

    old = st.session_state.get(key)
    if old == value:
        return

    # Write the value
    st.session_state[key] = value
    st.session_state["_dirty"] = True
    st.session_state["_last_user_shared_key"] = key
    ts_now = time.time()
    st.session_state["_last_user_edit_ts"] = ts_now
    st.session_state["_last_user_shared_ts"] = ts_now
    try:
        _write_sync_trace_line(
            f"SET_SHARED key={key} old={old} new={value} source={source}"
        )
    except Exception:
        pass
    try:
        debug_log("SET_SHARED", {"shared_key": key, "value": value, "from": st.session_state.get("page_slug")})
    except Exception:
        pass
    try:
        widget_key = None
        if isinstance(source, str) and source.startswith("callback:"):
            widget_key = source.split("callback:", 1)[1]
        log_path = os.path.join(os.path.dirname(__file__), ".blank_app_runtime", "blank_app_debug.log")
        with open(log_path, "a") as f:
            f.write(json.dumps({
                "event": "SET_SHARED",
                "ts": ts_now,
                "shared_key": key,
                "widget_key": widget_key,
                "old": old,
                "new": value,
                "source": source,
                "page": st.session_state.get("page_slug"),
            }) + "\n")
    except Exception:
        pass
    
    # Audit trail (keep last 50)
    tail = st.session_state.get("_shared_write_audit", [])
    caller = inspect.stack()[1]
    tail.append({
        "t": round(time.time(), 3),
        "key": key,
        "val": value,
        "source": source,
        "where": f"{caller.filename.split('/')[-1]}:{caller.lineno} {caller.function}",
    })
    st.session_state["_shared_write_audit"] = tail[-50:]


def set_ui(key: str, value, *, source: str = "") -> None:
    if key not in UI_STATE_DEFAULTS:
        raise KeyError(f"set_ui: '{key}' not in UI_STATE_DEFAULTS (source={source})")
    st.session_state[key] = value


# ============================================
# REGRESSION TRIPWIRE
# ============================================

def assert_shared_state_alive():
    """
    Regression tripwire: checks that critical shared state keys exist.
    If this fails, shared state was lost (bug detection).
    Call this after routing in app.py to catch state loss immediately.
    """
    required = ["b", "D", "L", "fc", "fsy", "Ec", "Es"]
    if any(k not in st.session_state for k in required):
        st.error("Shared session state was lost. This is a bug.")
