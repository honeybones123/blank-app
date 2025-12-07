import math
import streamlit as st

# ============================================================
#  SESSION STATE CONTRACT  (READ THIS BEFORE EDITING ANYTHING)
# ============================================================
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


# ============================================
# 1. SHARED DEFAULTS (session_state values)
# ============================================

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

    # Actions
    "Mu_star": 500.0,  # kNm (controlling moment)
    "Vu_star": 300.0,  # kN
    "Tu_star": 0.0,    # kNm
    "P_star": 0.0,     # kN (prestress or axial in bending/shear)
    "N_star": 0.0,     # kN (additional axial)
    "actions_source": "Manual design actions (inputs below)",  # Source of design actions

    # Longitudinal reinforcement
    "nb_bot": 4,       # bottom bars
    "db_bot": 20.0,    # mm
    "nb_top": 2,       # top bars
    "db_top": 16.0,    # mm
    "rowgap_bot": 60.0,
    "rowgap_top": 60.0,

    # Cover (including side cover shared values)
    "cover_bot": 40.0,
    "cover_top": 40.0,
    "side_cover_bot": 40.0,
    "side_cover_top": 40.0,
    "cover_side": 40.0,  # Geometry – side cover (to centroid or clear, whichever convention you use)

    # New "bars or spacing" entries (≤30 = bars, ≥30 = spacing in mm)
    "bot_entry": 4.0,   # bottom layer: 4 bars by default
    "top_entry": 2.0,   # top layer: 2 bars by default

    # Optional derived spacing (you can store these here or in a derived dict)
    "s_bot": 200.0,     # effective bottom spacing (mm)
    "s_top": 200.0,     # effective top spacing (mm)

    # Duct inputs (prestress / voids)
    "n_ducts": 0.0,     # number of ducts crossing the web
    "duct_dia": 0.0,    # nominal duct diameter (mm)

    # Derived duct summary – you'll compute these from n_ducts + duct_dia
    "sum_duct": 0.0,        # ∑ duct diameters crossing web (mm)
    "A_duct_total": 0.0,    # total duct area (mm²)

    # Time-dependent inputs (creep + shrinkage)
    "t_creep": 365.0,       # days after loading
    "age_at_loading": 28.0, # days
    "stress_ratio": 0.3,    # σ0 / f'c,mi
    "t_shrink": 365.0,      # days since drying started

    # Shear reinforcement
    "lig_d": 10.0,     # lig/stirrup diameter (mm)
    "lig_legs": 2,     # legs per stirrup
    "s_lig": 200.0,    # spacing (mm)

    # Crack control inputs
    "exposure_class": "B1",
    "s_bar_bot": 200.0,  # bottom bar spacing for crack calc (mm)

    # Derived (will be recalculated; set initial values)
    "d": 600.0 - 40.0 - 20.0 / 2.0,
    "do": 600.0 - 40.0 - 16.0 / 2.0,
    "Ast_bot": 4 * math.pi * 20.0**2 / 4.0,
    "Ast_top": 2 * math.pi * 16.0**2 / 4.0,

    # Results (placeholders; real calcs later)
    "phi_Mu_cap": 0.0,
    "Mu_utilisation": 0.0,
    "phi_Vu_cap": 0.0,
    "Vu_utilisation": 0.0,
    "phi_Tu_cap": 0.0,
    "Tu_utilisation": 0.0,
    "crack_width": 0.0,
    "crack_utilisation": 0.0,

    # Shrinkage results for reuse (e.g. crack width)
    "eps_cs_total": 0.0,          # total shrinkage strain (dimensionless)
    "eps_cs_total_micro": 300.0,  # microstrain seed
    "eps_cse": 0.0,
    "eps_csd_t": 0.0,
    "th_shrinkage": 100.0,
    "k1_shrinkage": 1.0,

    # Creep results for reuse
    "phi_cc_t": 2.0,
    "phi_cc_star_table": 2.0,
    "k2_creep": 1.0,
    "k3_creep": 1.0,
    "k4_creep": 1.0,
    "k5_creep": 1.0,
    "k6_creep": 1.0,

    # Crack control summary results
    "sigma_sr": 0.0,
    "sigma_allow_table": 0.0,
    "w_calc": 0.0,
    "wmax_char": 0.3,
    "passes_table": True,
    "passes_w": True,
    # Bending SLS → crack link (service steel stress)
    "sigma_s_sls": 200.0,
    
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
    "a_m": None,  # Distance a from left support for point loads (m)
    
    # SFD/BMD results (computed from SLS loads)
    "sfd_Msls_max_kNm": 0.0,  # Maximum absolute bending moment at SLS (kNm)
    "sfd_Vsls_max_kN": 0.0,  # Maximum absolute shear force at SLS (kN)
}

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
}

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

    "inputs_Mu_star": "Mu_star",
    "inputs_Vu_star": "Vu_star",
    "inputs_Tu_star": "Tu_star",
    "inputs_P_star": "P_star",
    "inputs_N_star": "N_star",

    "inputs_nb_bot": "nb_bot",
    "inputs_db_bot": "db_bot",
    "inputs_nb_top": "nb_top",
    "inputs_db_top": "db_top",
    "inputs_rowgap_bot": "rowgap_bot",
    "inputs_rowgap_top": "rowgap_top",

    "inputs_cover_bot": "cover_bot",
    "inputs_cover_top": "cover_top",
    "inputs_side_cover_bot": "side_cover_bot",
    "inputs_side_cover_top": "side_cover_top",
    "inputs_cover_side": "cover_side",  # Geometry – side cover (now a proper shared param)

    # Reo: new bars/spacing entries instead of nb_* for the widgets
    "inputs_bot_entry": "bot_entry",
    "inputs_top_entry": "top_entry",
    # We still keep nb_bot, nb_top etc. as params used by other pages.
    # They will be *derived* from bot_entry/top_entry in recalc_derived_values().
    # No widget keys needed for nb_bot / nb_top.

    "inputs_lig_d": "lig_d",
    "inputs_lig_legs": "lig_legs",
    "inputs_s_lig": "s_lig",

    # Ducts
    "inputs_n_ducts": "n_ducts",
    "inputs_duct_dia": "duct_dia",

    "inputs_exposure_class": "exposure_class",
    "inputs_s_bar_bot": "s_bar_bot",
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

    "bending_Mu_star": "Mu_star",
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

    # ----------------- SHEAR PAGE -----------------
    "shear_b": "b",
    "shear_D": "D",
    "shear_L": "L",

    "shear_fc": "fc",
    "shear_fsy": "fsy",
    "shear_Ec": "Ec",
    "shear_Es": "Es",

    "shear_Vu_star": "Vu_star",
    "shear_Tu_star": "Tu_star",
    "shear_P_star": "P_star",
    "shear_N_star": "N_star",

    "shear_phi_v": "phi_shear",
    "shear_phi_t": "phi_torsion",

    "shear_nb_bot": "nb_bot",
    "shear_db_bot": "db_bot",
    "shear_nb_top": "nb_top",
    "shear_db_top": "db_top",

    "shear_lig_d": "lig_d",
    "shear_lig_legs": "lig_legs",
    "shear_s_lig": "s_lig",

    "shear_cover_bot": "cover_bot",
    "shear_cover_top": "cover_top",

    # ----------------- CRACK CONTROL PAGE -----------------
    "crack_b": "b",
    "crack_D": "D",
    "crack_L": "L",

    "crack_fc": "fc",
    "crack_fsy": "fsy",
    "crack_Ec": "Ec",
    "crack_Es": "Es",

    "crack_Mu_star": "Mu_star",

    "crack_nb_bot": "nb_bot",
    "crack_db_bot": "db_bot",
    "crack_nb_top": "nb_top",
    "crack_db_top": "db_top",

    "crack_exposure_class": "exposure_class",
    "crack_s_bar_bot": "s_bar_bot",

    "crack_cover_bot": "cover_bot",
    "crack_cover_top": "cover_top",
    
    # ----------------- SFD/BMD PAGE (Unified loading) -----------------
    "load_L": "span_L_m",
    "load_g_udl": "g_udl_kNm_per_m",
    "load_q_udl": "q_udl_kNm_per_m",
    "load_psi_udl": "psi_udl",
    "load_G_point": "G_point_kN",
    "load_Q_point": "Q_point_kN",
    "load_psi_point": "psi_point",
    "load_a_point": "a_m",
}

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

    # 3) All result keys must exist in SHARED_DEFAULTS
    missing_results = RESULT_KEYS - shared_keys
    if missing_results:
        raise KeyError(
            "[SESSION STATE CONTRACT] RESULT_KEYS contains items not in "
            f"SHARED_DEFAULTS: {missing_results}"
        )

# Run this once at import
_validate_contract()

# ============================================
# 3. INITIALISATION + DERIVED UPDATES
# ============================================

def init_shared_session_state():
    """
    Initialise all shared keys and tab-widget keys in st.session_state.
    This must be called before any page renders widgets.
    """
    # 1) Shared values
    for key, val in SHARED_DEFAULTS.items():
        st.session_state.setdefault(key, val)

    # 2) Tab-local widget copies – start equal to the shared value
    for widget_key, shared_key in TAB_KEYS.items():
        if shared_key in st.session_state:
            st.session_state.setdefault(widget_key, st.session_state[shared_key])

    # 3) Ensure derived values are up to date
    recalc_derived_values()


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
    """
    D = st.session_state["D"]
    cover_bot = st.session_state["cover_bot"]
    cover_top = st.session_state["cover_top"]
    db_bot = st.session_state["db_bot"]
    db_top = st.session_state["db_top"]
    
    # Get cover_side, with fallback to min of cover_top/cover_bot
    cover_side = st.session_state.get("cover_side", min(
        st.session_state.get("cover_top", 40.0),
        st.session_state.get("cover_bot", 40.0),
    ))

    # ---------- 3.1 Bars vs spacing for bottom + top ----------
    b = st.session_state.get("b", 0.0)
    
    # Bottom layer
    bot_entry = st.session_state.get("bot_entry", st.session_state.get("nb_bot", 0.0))
    mode_bot, nb_bot_eff, s_bot_eff = _decode_bars_or_spacing(
        bot_entry, b, cover_side, db_bot
    )

    # Top layer
    top_entry = st.session_state.get("top_entry", st.session_state.get("nb_top", 0.0))
    mode_top, nb_top_eff, s_top_eff = _decode_bars_or_spacing(
        top_entry, b, cover_side, db_top
    )

    # Write back "canonical" values that the rest of the app uses
    nb_bot = nb_bot_eff
    nb_top = nb_top_eff
    st.session_state["nb_bot"] = nb_bot
    st.session_state["nb_top"] = nb_top
    st.session_state["s_bot"] = s_bot_eff
    st.session_state["s_top"] = s_top_eff

    # Store modes in derived (if you have a derived dict, otherwise skip)
    # For now we'll skip since the current code doesn't use a separate derived dict

    # ---------- 3.2 Duct summary ----------
    n_ducts = float(st.session_state.get("n_ducts", 0.0) or 0.0)
    duct_dia = float(st.session_state.get("duct_dia", 0.0) or 0.0)

    if n_ducts > 0.0 and duct_dia > 0.0:
        sum_duct = n_ducts * duct_dia               # mm
        A_duct_total = n_ducts * math.pi * duct_dia**2 / 4.0  # mm²
    else:
        sum_duct = 0.0
        A_duct_total = 0.0

    st.session_state["sum_duct"] = sum_duct
    st.session_state["A_duct_total"] = A_duct_total

    # ---------- 3.3 Time-dependent inputs ----------
    # For now we only normalise / store them; the creep/shrinkage pages
    # will pick them up via get_param().
    t_creep = float(st.session_state.get("t_creep", 365.0) or 365.0)
    age_at_loading = float(st.session_state.get("age_at_loading", 28.0) or 28.0)
    stress_ratio = float(st.session_state.get("stress_ratio", 0.3) or 0.3)
    t_shrink = float(st.session_state.get("t_shrink", 365.0) or 365.0)

    st.session_state["t_creep"] = t_creep
    st.session_state["age_at_loading"] = age_at_loading
    st.session_state["stress_ratio"] = stress_ratio
    st.session_state["t_shrink"] = t_shrink

    # Effective depths
    st.session_state["d"] = D - cover_bot - db_bot / 2.0
    st.session_state["do"] = D - cover_top - db_top / 2.0

    # Steel areas
    st.session_state["Ast_bot"] = nb_bot * math.pi * db_bot**2 / 4.0
    st.session_state["Ast_top"] = nb_top * math.pi * db_top**2 / 4.0


# ============================================
# 4. SYNC CALLBACKS
# ============================================

_SYNC_CALLBACKS = None  # module-global


def _make_sync_callback(widget_key: str, shared_key: str):
    """
    Callback: widget → shared → all other widgets for that shared key.
    Also updates derived values (RULE 3).
    """
    def _callback():
        # 1) widget → shared
        st.session_state[shared_key] = st.session_state[widget_key]

        # 2) shared → all other widget copies
        for w_key, sh_key in TAB_KEYS.items():
            if sh_key == shared_key and w_key != widget_key:
                st.session_state[w_key] = st.session_state[shared_key]

        # 3) Update derived values whenever anything changes
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
    return _SYNC_CALLBACKS


# ============================================
# 5. RESULT UPDATE HELPER (RULE 4)
# ============================================

def update_results(**kwargs):
    """
    Safely update result / shared values (phi_Mu_cap, Mu_utilisation, shrinkage,
    creep, crack summaries, etc.).

    Originally this helper only allowed keys listed in RESULT_KEYS. To keep the
    teaching pages flexible while still enforcing the core contract, we now:

      - require that any updated key exists in SHARED_DEFAULTS
      - but do NOT require it to be in RESULT_KEYS (RESULT_KEYS is kept mainly
        for documentation and legacy checks).
    """
    for key, value in kwargs.items():
        if key not in SHARED_DEFAULTS:
            raise KeyError(
                f"[SESSION STATE CONTRACT] Tried to update unknown session key '{key}'.\n"
                f"Add it to SHARED_DEFAULTS before using update_results()."
            )
        st.session_state[key] = value


# ============================================
# 6. SMALL HELPERS
# ============================================

def get_param(name: str, default=None):
    """
    Safe accessor for shared parameters from session_state.
    """
    if name in st.session_state:
        return st.session_state[name]
    return SHARED_DEFAULTS.get(name, default)
