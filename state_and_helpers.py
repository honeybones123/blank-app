import json
import math
import os
import uuid
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
#
#  PAGE FILE RULES (copy this banner to the top of every page file)
#  ============================================================
#  Every page render function MUST:
#  1) Call init_shared_session_state() as the FIRST line
#  2) Never write directly to shared keys (b, D, fc, etc.)
#  3) Only update shared keys via sync callbacks
#  4) Never clear query params globally
#
#  Example:
#      def render_mypage():
#          init_shared_session_state()  # MUST be first
#          sync_callbacks = get_sync_callbacks()
#          # ... rest of page code ...
#
# ============================================================


# ============================================
# 1. SHARED DEFAULTS (session_state values)
# ============================================

def _coalesce_num(v, default: float) -> float:
    """Return default only if v is None (preserves 0)."""
    return default if v is None else float(v)

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
    "Mu_star": 500.0,        # kNm (final chosen value used by design pages)
    "Mu_star_kNm": 500.0,    # kNm (alternative naming for compatibility)
    "Vu_star": 300.0,        # kN (final chosen value used by design pages)
    "Vu_star_kN": 300.0,     # kN (alternative naming for compatibility)

    # Manual copies – start equal to the same seeds so manual mode
    # behaves identically until the user edits the inputs.
    "Mu_star_manual": 500.0,  # kNm
    "Vu_star_manual": 300.0,  # kN
    "Tu_star": 0.0,    # kNm
    "P_star": 0.0,     # kN (prestress or axial in bending/shear)
    "N_star": 0.0,     # kN (additional axial)
    "actions_source": "Manual design actions (inputs below)",  # Source of design actions

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

    # Crack / torsion sketch control
    "crack_theta_deg": 45.0,  # physical crack angle (degrees)

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
    "Vu_max_kN": 0.0,  # Web crushing capacity (nominal, before phi)
    "phi_Vu_max_kN": 0.0,  # Web crushing capacity (design, with phi)
    "V_eq_kN": 0.0,  # Equivalent shear demand
    "Vuc_utilisation": None,  # Web crushing utilisation
    "phi_Tu_cap": 0.0,
    "Tu_utilisation": 0.0,
    "crack_width": 0.0,
    "crack_utilisation": 0.0,
    
    # Bending detail values (for Inputs page summary)
    "As_min_req": None,  # Minimum required steel area (mm²)
    "Mx_min_req": None,  # Minimum required moment = 1.2 * Mcr (kNm)
    "k_u": None,         # Neutral axis ratio c/d
    "k_u_lim": 0.36,     # AS 3600 limit for ductile design

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
    
    # Deflection results
    "deflection_total_mm": 0.0,
    "deflection_limit_mm": 0.0,
    "deflection_utilisation": 0.0,
    
    # Deflection page inputs (never None — None causes Streamlit widget + calc crashes)
    "defl_beff": 400.0,   # mm
    "defl_bw": 400.0,     # mm
    "defl_L_eff": 3.0,    # m  (default from L=3000mm)
    "defl_support_type": "Simply supported",  # Support condition for k₂ coefficient
    "defl_limit_ratio": 250.0,  # Deflection limit ratio (L/Δ, e.g. 250 for L/250)
    "defl_Fdef": 12.0,  # Effective design load (kN/m) for span/depth check
    "defl_use_simplified_ief": True,  # Use simplified I_ef calculation (checkbox)
    
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
    "a_m": 0.0,  # Distance a from left support for point loads (m)
    
    # SFD/BMD results (computed from SLS loads)
    "sfd_Msls_max_kNm": 0.0,  # Maximum absolute bending moment at SLS (kNm) - legacy
    "sfd_Vsls_max_kN": 0.0,  # Maximum absolute shear force at SLS (kN) - legacy
    "sfd_span_L_m": 6.0,  # Span length for SFD/deflection pages (m)
    "sfd_case": "Simple beam – UDL over entire span",  # Current teaching case
    "sfd_Mmax_abs_kNm": 0.0,  # Maximum absolute bending moment at SLS (kNm) - for Inputs page
    "sfd_Vmax_abs_kN": 0.0,  # Maximum absolute shear force at SLS (kN) - for Inputs page
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

# Explicit set of derived keys (for RULE 3 checks and debug guards)
# These are keys written ONLY inside recalc_derived_values()
DERIVED_KEYS = {
    "d", "do",
    "Ast_bot", "Ast_top",
    "nb_bot", "nb_top",
    "db_bot", "db_top",
    "s_bot", "s_top",
    "bot_entry", "top_entry",
    "sum_duct", "A_duct_total",
    "t_creep", "age_at_loading", "stress_ratio", "t_shrink",
    # Layer 2 keys (may be auto-updated by recalc_derived_values)
    "nb_or_s_bot_2", "db_bot_2",
    "nb_or_s_top_2", "db_top_2",
}

# Shared keys that should never be driven by stale widget zeros on navigation
# Shared keys that should never be driven by stale widget zeros on navigation
FORCE_HYDRATE_SHARED_KEYS = {
    # Geometry
    "b", "D", "L",

    # Materials
    "fc", "fsy", "Ec", "Es",

    # Design actions (manual)
    "Mu_star_manual", "Vu_star_manual", "Tu_star", "P_star", "N_star",

    # Longitudinal reinforcement (layer 1 + layer 2 + spacing outputs)
    "nb_or_s_bot_1", "db_bot_1", "nb_or_s_bot_2", "db_bot_2",
    "nb_or_s_top_1", "db_top_1", "nb_or_s_top_2", "db_top_2",
    "rowgap_bot", "rowgap_top",
    "s_bot", "s_top",

    # Cover (if any of these ever appear as 0, it breaks everything visually)
    "cover_bot", "cover_top", "cover_side",
    "side_cover_bot", "side_cover_top",

    # Shear reinforcement
    "lig_d", "lig_legs", "s_lig",
}


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

    # ----------------- ACTIONS ALIASES (V* vs Vu*, T* vs Tu*) -----------------
    # Treat any page's alternate naming as the same underlying shared parameters.
    "inputs_V_star": "Vu_star_manual",
    "shear_V_star": "Vu_star_manual",
    "shear_Vu_star": "Vu_star_manual",
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

    # ----------------- SHEAR PAGE -----------------
    "shear_b": "b",
    "shear_D": "D",
    "shear_L": "L",

    "shear_fc": "fc",
    "shear_fsy": "fsy",
    "shear_Ec": "Ec",
    "shear_Es": "Es",

    "shear_Vu_star": "Vu_star_manual",
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

    "crack_cover_bot": "cover_bot",
    "crack_cover_top": "cover_top",
    
    # Crack page 2-layer bottom reinforcement (same pattern as inputs/bending)
    "crk_nb_or_s_bot_1": "nb_or_s_bot_1",
    "crk_db_bot_1": "db_bot_1",
    "crk_nb_or_s_bot_2": "nb_or_s_bot_2",
    "crk_db_bot_2": "db_bot_2",
    "crk_rowgap_bot": "rowgap_bot",
    "crk_cover_bot": "cover_bot",
    
    # ----------------- SFD/BMD PAGE (Unified loading) -----------------
    "load_L": "span_L_m",
    "load_g_udl": "g_udl_kNm_per_m",
    "load_q_udl": "q_udl_kNm_per_m",
    "load_psi_udl": "psi_udl",
    "load_G_point": "G_point_kN",
    "load_Q_point": "Q_point_kN",
    "load_psi_point": "psi_point",
    "load_a_point": "a_m",
    
    # ----------------- DEFLECTION PAGE -----------------
    "defl_L_eff": "defl_L_eff",
    "defl_bw": "defl_bw",
    "defl_beff": "defl_beff",
    "defl_support_type": "defl_support_type",
    "defl_limit_ratio": "defl_limit_ratio",
    "defl_Fdef": "defl_Fdef",
    "defl_use_simplified_ief": "defl_use_simplified_ief",
    
    # Deflection page uses the same concrete props as global materials
    "defl_fc": "fc",
    "defl_Ec": "Ec",
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


def _get_disk_snapshot_path():
    """Get the path to the disk snapshot file."""
    repo_root = os.path.dirname(os.path.abspath(__file__))
    snapshot_dir = os.path.join(repo_root, ".blank_app_state")
    os.makedirs(snapshot_dir, exist_ok=True)
    return os.path.join(snapshot_dir, "shared_snapshot.json")


def _save_shared_to_disk():
    """
    Save the full shared dict to disk snapshot.
    Called after every successful callback update of a shared key.
    """
    try:
        snapshot_path = _get_disk_snapshot_path()
        shared_dict = {}
        for k in SHARED_DEFAULTS.keys():
            if k in st.session_state:
                shared_dict[k] = st.session_state[k]
        
        with open(snapshot_path, "w") as f:
            json.dump(shared_dict, f, indent=2)
    except Exception as e:
        # Silently fail - disk persistence is best-effort
        pass


def _load_shared_from_disk():
    """
    Load shared dict from disk snapshot if available.
    Returns True if loaded, False otherwise.
    """
    try:
        snapshot_path = _get_disk_snapshot_path()
        if not os.path.exists(snapshot_path):
            return False
        
        with open(snapshot_path, "r") as f:
            shared_dict = json.load(f)
        
        # Restore shared keys from disk snapshot
        for k, v in shared_dict.items():
            if k in SHARED_DEFAULTS:
                st.session_state[k] = v
        
        return True
    except Exception:
        # Silently fail - disk persistence is best-effort
        return False


def persist_state_snapshot():
    """
    Persist ALL shared keys + ALL inputs_* widget keys + caches used for restores.
    """
    cid = get_client_id()
    store = _persistent_store()

    # Persist shared
    shared = {}
    for k in SHARED_DEFAULTS.keys():
        if k in st.session_state:
            shared[k] = st.session_state[k]

    # Persist widget values that matter most (inputs_ + caches)
    widgets = {}
    for widget_key in TAB_KEYS.keys():
        if widget_key.startswith("inputs_") and widget_key in st.session_state:
            widgets[widget_key] = st.session_state[widget_key]

        cached_key = f"_cached_{widget_key}"
        if cached_key in st.session_state:
            widgets[cached_key] = st.session_state[cached_key]

    store[cid] = {"shared": shared, "widgets": widgets}
    
    # Also save to disk for durable persistence across session restarts
    _save_shared_to_disk()


def restore_state_snapshot_if_available(force: bool = False) -> bool:
    """
    If session_state wiped, restore from persisted snapshot.
    Returns True if restored anything.
    
    Args:
        force: If True, overwrite existing keys. If False, only restore missing keys.
    """
    cid = get_client_id()
    store = _persistent_store()
    snap = store.get(cid)
    if not snap:
        return False

    restored_any = False

    # Restore shared first
    for k, v in snap.get("shared", {}).items():
        if force or (k not in st.session_state):
            st.session_state[k] = v
            restored_any = True

    # Restore inputs_ widgets and caches
    for k, v in snap.get("widgets", {}).items():
        if force or (k not in st.session_state):
            st.session_state[k] = v
            restored_any = True

    return restored_any


def begin_render_cycle():
    """
    MUST be called once per run (in app.py before rendering any page).
    Ensures rendered widget gating is per-run, not cumulative across runs.
    """
    st.session_state["_rendered_widget_keys"] = set()


def debug_log(tag: str, data: dict):
    """Helper to write debug logs in consistent format."""
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


def _is_invalid_shared_value(val):
    """Check if a shared value is invalid (None or 0)."""
    return val is None or (isinstance(val, (int, float)) and val == 0)


def repair_inputs_shared_from_widgets():
    """
    Contract-safe fallback:
    If Inputs widget exists and shared is invalid (0/None),
    copy widget → shared ONCE to repair poisoned shared state.
    """
    repaired = {}

    for widget_key, shared_key in TAB_KEYS.items():
        if not widget_key.startswith("inputs_"):
            continue

        if widget_key not in st.session_state:
            continue

        wval = st.session_state.get(widget_key, None)
        sval = st.session_state.get(shared_key, None)

        if _is_invalid_shared_value(sval) and wval not in (None, 0, 0.0, ""):
            st.session_state[shared_key] = wval
            repaired[shared_key] = {"from_widget": widget_key, "widget_value": wval}

    if repaired:
        debug_log("repair_inputs_shared_from_widgets", repaired)


# REMOVED: force_inputs_to_shared_after_wipe()
# This function was causing real inputs to be overwritten with 0s.
# Shared state should only be updated via callbacks, not during init/wipe recovery.


def init_shared_session_state():
    """
    Initialise all shared keys and tab-widget keys in st.session_state.
    This must be called before any page renders widgets.
    
    IMPORTANT: This function only sets defaults when keys are missing.
    It NEVER overwrites existing user values.
    
    Always backfills missing widget keys (even after initialization) to prevent
    widgets from resetting when Streamlit drops widget state.
    """
    # #region agent log
    import json
    import os
    log_path = "/Users/jonathonleggo/Library/CloudStorage/OneDrive-Personal/Documents/GitHub/blank-app/.cursor/debug.log"
    try:
        with open(log_path, "a") as f:
            f.write(json.dumps({"location": "state_and_helpers.py:590", "message": "init_shared_session_state ENTRY", "data": {"already_init": st.session_state.get("_shared_state_initialized", False)}, "timestamp": __import__("time").time() * 1000, "sessionId": "debug-session", "runId": "run1", "hypothesisId": "A"}) + "\n")
    except: pass
    # #endregion
    
    # Watchdog: log shared key changes at entry
    log_shared_diff("init_entry_shared_diff")
    
    already_initialized = st.session_state.get("_shared_state_initialized", False)
    
    # Detect wipe recovery mode
    WIPED = not already_initialized
    
    if WIPED:
        st.session_state["_wipe_recovery_mode"] = True
        debug_log("WIPE_RECOVERY_MODE_ENABLED", {})
    else:
        st.session_state["_wipe_recovery_mode"] = False
    
    # Session wipe: restore FIRST (force overwrite), then seed anything still missing
    restored = False
    if not already_initialized:
        # #region agent log - wipe detector
        try:
            with open(log_path, "a") as f:
                f.write(json.dumps({
                    "location": "state_and_helpers.py:init_shared_session_state",
                    "message": "Detected missing _shared_initialized (session wipe). Will attempt restore.",
                    "data": {"cid": get_client_id()},
                    "timestamp": __import__("time").time() * 1000
                }) + "\n")
        except:
            pass
        # #endregion
        
        # FIRST: Try to restore from disk snapshot (durable persistence)
        disk_restored = _load_shared_from_disk()
        if disk_restored:
            restored = True
        
        # THEN: Try in-memory snapshot restore (fallback)
        if not restored:
            restored = restore_state_snapshot_if_available(force=True)
        
        # After restoring, recompute the flag (it may have come back via snapshot)
        already_initialized = st.session_state.get("_shared_state_initialized", False)

        # If we restored shared keys, we can safely set initialized now
        if restored and not already_initialized:
            st.session_state["_shared_state_initialized"] = True
            already_initialized = True
    
    # NOW seed defaults only for anything still missing (after restore)
    for key, val in SHARED_DEFAULTS.items():
        if key not in st.session_state:
            st.session_state[key] = val
    
    # Ensure sentinel exists once we have a valid state
    if not st.session_state.get("_shared_state_initialized", False):
        st.session_state["_shared_state_initialized"] = True
    
    # 1) Shared values: only set if missing (never overwrite)
    # Only run once.
    if not already_initialized:
        for key, val in SHARED_DEFAULTS.items():
            if key not in st.session_state:
                st.session_state[key] = val

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
        
        # #region agent log
        try:
            with open(log_path, "a") as f:
                f.write(json.dumps({"location": "state_and_helpers.py:init_widget_check", "message": "Widget key check in init", "data": {"widget_key": widget_key, "shared_key": shared_key, "widget_exists": widget_exists, "widget_value": widget_value, "shared_exists": shared_exists, "shared_value": shared_value}, "timestamp": __import__("time").time() * 1000, "sessionId": "debug-session", "runId": "run1", "hypothesisId": "H"}) + "\n")
        except: pass
        # #endregion
        
        # #region agent log
        try:
            with open(log_path, "a") as f:
                f.write(json.dumps({"location": "state_and_helpers.py:624", "message": "Widget key check", "data": {"widget_key": widget_key, "shared_key": shared_key, "widget_exists": widget_exists, "shared_exists": shared_exists, "widget_value": widget_value, "shared_value": shared_value}, "timestamp": __import__("time").time() * 1000, "sessionId": "debug-session", "runId": "run1", "hypothesisId": "E"}) + "\n")
        except: pass
        # #endregion
        
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
                # #region agent log
                try:
                    with open(log_path, "a") as f:
                        f.write(json.dumps({"location": "state_and_helpers.py:cache_restore", "message": "Restored from cache", "data": {"widget_key": widget_key, "shared_key": shared_key, "cached_value": cached_value, "default_value": default_value}, "timestamp": __import__("time").time() * 1000, "sessionId": "debug-session", "runId": "run1", "hypothesisId": "I"}) + "\n")
                except: pass
                # #endregion
            else:
                # Cache is stale (0 when it shouldn't be) - skip cache restoration, fall through to other sources
                # #region agent log
                try:
                    with open(log_path, "a") as f:
                        f.write(json.dumps({"location": "state_and_helpers.py:cache_restore", "message": "Skipped stale cache (0 value)", "data": {"widget_key": widget_key, "shared_key": shared_key, "cached_value": cached_value, "default_value": default_value}, "timestamp": __import__("time").time() * 1000, "sessionId": "debug-session", "runId": "run1", "hypothesisId": "I"}) + "\n")
                except: pass
                # #endregion

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
                    # #region agent log
                    try:
                        with open(log_path, "a") as f:
                            f.write(json.dumps({"location": "state_and_helpers.py:restore", "message": "About to restore widget key from inputs", "data": {"widget_key": widget_key, "shared_key": shared_key, "restored_value": restored_value, "inputs_widget_key": inputs_widget_key, "widget_value_before": st.session_state.get(widget_key)}, "timestamp": __import__("time").time() * 1000, "sessionId": "debug-session", "runId": "run1", "hypothesisId": "G"}) + "\n")
                    except: pass
                    # #endregion
                    st.session_state[widget_key] = restored_value
                    # Update the cache to keep it current with the actual inputs_* widget value
                    cached_inputs_key = f"_cached_{inputs_widget_key}"
                    st.session_state[cached_inputs_key] = restored_value
                    # #region agent log
                    try:
                        with open(log_path, "a") as f:
                            f.write(json.dumps({"location": "state_and_helpers.py:667", "message": "Restored from existing inputs widget", "data": {"widget_key": widget_key, "shared_key": shared_key, "restored_value": restored_value, "inputs_widget_key": inputs_widget_key, "cache_updated": st.session_state[cached_inputs_key], "widget_value_after": st.session_state.get(widget_key)}, "timestamp": __import__("time").time() * 1000, "sessionId": "debug-session", "runId": "run1", "hypothesisId": "E"}) + "\n")
                    except: pass
                    # #endregion
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
                    
                    # #region agent log
                    try:
                        with open(log_path, "a") as f:
                            f.write(json.dumps({"location": "state_and_helpers.py:restore", "message": "About to restore widget key from shared", "data": {"widget_key": widget_key, "shared_key": shared_key, "restored_value": shared_value, "default_value": default_value, "widget_value_before": st.session_state.get(widget_key), "should_restore": should_restore}, "timestamp": __import__("time").time() * 1000, "sessionId": "debug-session", "runId": "run1", "hypothesisId": "G"}) + "\n")
                    except: pass
                    # #endregion
                    
                    if should_restore:
                        restored_value = shared_value
                        st.session_state[widget_key] = restored_value
                    else:
                        # Skip restoring from shared (stale 0 value) BUT DO NOT write None into the widget.
                        # Instead fall back to the default value immediately.
                        restored_value = SHARED_DEFAULTS.get(shared_key, None)

                        # Only set if we actually have a default; otherwise leave missing
                        if restored_value is not None:
                            st.session_state[widget_key] = restored_value
                        # #region agent log
                        try:
                            with open(log_path, "a") as f:
                                f.write(json.dumps({"location": "state_and_helpers.py:restore", "message": "Skipped restoring from shared (stale 0 value)", "data": {"widget_key": widget_key, "shared_key": shared_key, "shared_value": shared_value, "default_value": default_value, "restored_value": restored_value}, "timestamp": __import__("time").time() * 1000, "sessionId": "debug-session", "runId": "run1", "hypothesisId": "G"}) + "\n")
                        except: pass
                        # #endregion
                else:
                    # Final fallback to defaults
                    restored_value = SHARED_DEFAULTS.get(shared_key, None)
                    # #region agent log
                    try:
                        with open(log_path, "a") as f:
                            f.write(json.dumps({"location": "state_and_helpers.py:restore", "message": "About to restore widget key from defaults", "data": {"widget_key": widget_key, "shared_key": shared_key, "restored_value": restored_value, "widget_value_before": st.session_state.get(widget_key)}, "timestamp": __import__("time").time() * 1000, "sessionId": "debug-session", "runId": "run1", "hypothesisId": "G"}) + "\n")
                    except: pass
                    # #endregion
                    st.session_state[widget_key] = restored_value
            
            # #region agent log
            try:
                with open(log_path, "a") as f:
                    f.write(json.dumps({"location": "state_and_helpers.py:690", "message": "Widget key restored (final)", "data": {"widget_key": widget_key, "shared_key": shared_key, "restored_value": restored_value, "shared_exists": shared_exists, "shared_value_before": shared_value, "widget_value_after": st.session_state.get(widget_key)}, "timestamp": __import__("time").time() * 1000, "sessionId": "debug-session", "runId": "run1", "hypothesisId": "E"}) + "\n")
            except: pass
            # #endregion
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
    # CRITICAL RULES:
    # 1) Never write shared from widgets during init
    #    - Shared can ONLY be changed by callbacks / explicit sync, not by navigation/init
    #    - This prevents stale widget zeros from overwriting shared state on navigation
    # 2) Only hydrate page widgets from shared (shared → widget)
    #    - Non-inputs page widgets (bending_*, shear_*, etc.) are hydrated from shared
    #    - This ensures page widgets start from correct shared values
    # 3) Inputs page widgets still update shared via callbacks only
    #    - inputs_* widgets update shared through on_change callbacks
    #    - Never sync inputs_* → shared during init
    
    # Hydrate all NON-input widget copies from shared (so page navigation never seeds 0s into shared)
    for widget_key, shared_key in TAB_KEYS.items():
        if widget_key.startswith("inputs_"):
            continue
        if shared_key in st.session_state and widget_key in st.session_state:
            st.session_state[widget_key] = st.session_state[shared_key]
            # #region agent log
            try:
                with open(log_path, "a") as f:
                    f.write(json.dumps({"location": "state_and_helpers.py:safe_hydrate", "message": "Hydrated page widget from shared", "data": {"widget_key": widget_key, "shared_key": shared_key, "value": st.session_state[shared_key]}, "timestamp": __import__("time").time() * 1000, "sessionId": "debug-session", "runId": "run1", "hypothesisId": "P"}) + "\n")
            except: pass
            # #endregion
    
    # Keep inputs_* cache current, BUT do not poison it with stale navigation zeros.
    # This cache is used for widget restoration, but we never sync inputs_* → shared during init.
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
            is_stale_zero = (
                (widget_val == 0 or widget_val == 0.0)
                and (shared_key in FORCE_HYDRATE_SHARED_KEYS)
                and (shared_val not in (None, 0, 0.0))
                and (default_value not in (None, 0, 0.0))
            )

            if not is_stale_zero:
                st.session_state[cached_key] = widget_val
            # else: do NOT overwrite cache; keep the last known good value
    
    # #region agent log
    try:
        with open(log_path, "a") as f:
            f.write(json.dumps({"location": "state_and_helpers.py:627", "message": "init_shared_session_state EXIT", "data": {"restored_count": len(restored_widgets), "sample_restored": restored_widgets[:5] if restored_widgets else []}, "timestamp": __import__("time").time() * 1000, "sessionId": "debug-session", "runId": "run1", "hypothesisId": "A"}) + "\n")
    except: pass
    # #endregion
    
    # Only attempt repair if we did NOT successfully restore from snapshot
    # This prevents "repair" logic from stomping restored state
    if not restored:
        repair_inputs_shared_from_widgets()
    
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
    
    # Persist snapshot after init/restore so future wipes recover correctly
    persist_state_snapshot()


def hydrate_active_page_widgets_from_shared(active_slug: str) -> None:
    """
    Prevent stale page widget keys (often 0) from overwriting shared values on navigation.
    Runs BEFORE rendering the active page so widgets start from shared values.
    Only force-hydrates keys whose shared values should not be clobbered by zeros.
    
    CRITICAL: Also hydrates inputs_* widgets (they're global and should always be hydrated
    from shared state to prevent stale zeros from syncing back into shared).
    """
    # #region agent log
    import json
    import os
    log_path = "/Users/jonathonleggo/Library/CloudStorage/OneDrive-Personal/Documents/GitHub/blank-app/.cursor/debug.log"
    try:
        with open(log_path, "a") as f:
            f.write(json.dumps({"location": "state_and_helpers.py:hydrate_entry", "message": "Hydrate function entry", "data": {"active_slug": active_slug}, "timestamp": __import__("time").time() * 1000, "sessionId": "debug-session", "runId": "run1", "hypothesisId": "K"}) + "\n")
    except: pass
    # #endregion
    
    prefix = f"{active_slug}_"
    hydrated_count = 0
    
    # CRITICAL: Always hydrate inputs_* widgets from shared state (they're global)
    # This prevents stale inputs_* zeros from syncing back into shared state
    for widget_key, shared_key in TAB_KEYS.items():
        if not widget_key.startswith("inputs_"):
            continue
        if shared_key not in st.session_state:
            continue
        if shared_key not in FORCE_HYDRATE_SHARED_KEYS:
            continue  # Only hydrate critical keys for inputs_*
            
        shared_val = st.session_state.get(shared_key)
        widget_val = st.session_state.get(widget_key)
        
        is_stale_zero = (widget_val is None) or (widget_val == 0) or (widget_val == 0.0) or (widget_val == "")
        shared_is_meaningful = shared_val not in (None, "", 0, 0.0)
        
        if is_stale_zero and shared_is_meaningful:
            # #region agent log
            try:
                with open(log_path, "a") as f:
                    f.write(json.dumps({"location": "state_and_helpers.py:hydrate", "message": "Force-hydrating inputs_* stale zero", "data": {"widget_key": widget_key, "shared_key": shared_key, "widget_val_before": widget_val, "shared_val": shared_val}, "timestamp": __import__("time").time() * 1000, "sessionId": "debug-session", "runId": "run1", "hypothesisId": "K"}) + "\n")
            except: pass
            # #endregion
            st.session_state[widget_key] = shared_val
            hydrated_count += 1
    
    # Hydrate active page's widgets (e.g., bending_*, shear_*)
    for widget_key, shared_key in TAB_KEYS.items():
        if not widget_key.startswith(prefix):
            continue
        if shared_key not in st.session_state:
            continue

        shared_val = st.session_state.get(shared_key)

        # Always seed missing widget keys
        if widget_key not in st.session_state:
            st.session_state[widget_key] = shared_val
            hydrated_count += 1
            # #region agent log
            try:
                with open(log_path, "a") as f:
                    f.write(json.dumps({"location": "state_and_helpers.py:hydrate", "message": "Seeded missing widget key", "data": {"widget_key": widget_key, "shared_key": shared_key, "shared_val": shared_val}, "timestamp": __import__("time").time() * 1000, "sessionId": "debug-session", "runId": "run1", "hypothesisId": "K"}) + "\n")
            except: pass
            # #endregion
            continue

        # Force-hydrate only for critical shared keys if widget is "stale zero"
        if shared_key in FORCE_HYDRATE_SHARED_KEYS:
            widget_val = st.session_state.get(widget_key)

            is_stale_zero = (widget_val is None) or (widget_val == 0) or (widget_val == 0.0) or (widget_val == "")
            shared_is_meaningful = shared_val not in (None, "", 0, 0.0)

            if is_stale_zero and shared_is_meaningful:
                # #region agent log
                try:
                    with open(log_path, "a") as f:
                        f.write(json.dumps({"location": "state_and_helpers.py:hydrate", "message": "Force-hydrating stale zero", "data": {"widget_key": widget_key, "shared_key": shared_key, "widget_val_before": widget_val, "shared_val": shared_val}, "timestamp": __import__("time").time() * 1000, "sessionId": "debug-session", "runId": "run1", "hypothesisId": "K"}) + "\n")
                except: pass
                # #endregion
                st.session_state[widget_key] = shared_val
                hydrated_count += 1
    
    # #region agent log
    try:
        with open(log_path, "a") as f:
            f.write(json.dumps({"location": "state_and_helpers.py:hydrate_exit", "message": "Hydrate function exit", "data": {"active_slug": active_slug, "hydrated_count": hydrated_count}, "timestamp": __import__("time").time() * 1000, "sessionId": "debug-session", "runId": "run1", "hypothesisId": "K"}) + "\n")
    except: pass
    # #endregion


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
    PROTECTED_FROM_ZERO_SHARED_KEYS = FORCE_HYDRATE_SHARED_KEYS
    
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
            st.session_state[shared_key] = widget_value
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
            if shared_key in PROTECTED_FROM_ZERO_SHARED_KEYS:
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
            if old_shared_value not in (None, "", 0, 0.0) and widget_value in (0, 0.0) and shared_key in PROTECTED_FROM_ZERO_SHARED_KEYS:
                # #region agent log
                try:
                    with open(log_path, "a") as f:
                        f.write(json.dumps({"location": "state_and_helpers.py:sync_write", "message": "WARNING: About to overwrite meaningful shared with zero", "data": {"widget_key": widget_key, "shared_key": shared_key, "old_shared": old_shared_value, "new_widget_value": widget_value}, "timestamp": __import__("time").time() * 1000, "sessionId": "debug-session", "runId": "run1", "hypothesisId": "O"}) + "\n")
                except: pass
                # #endregion
            st.session_state[shared_key] = widget_value
            
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

    # ---------- 3.2 Duct summary ----------
    n_ducts = _coalesce_num(st.session_state.get("n_ducts", 0.0), 0.0)
    duct_dia = _coalesce_num(st.session_state.get("duct_dia", 0.0), 0.0)

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
    t_creep = _coalesce_num(st.session_state.get("t_creep", 365.0), 365.0)
    age_at_loading = _coalesce_num(st.session_state.get("age_at_loading", 28.0), 28.0)
    stress_ratio = _coalesce_num(st.session_state.get("stress_ratio", 0.3), 0.3)
    t_shrink = _coalesce_num(st.session_state.get("t_shrink", 365.0), 365.0)

    st.session_state["t_creep"] = t_creep
    st.session_state["age_at_loading"] = age_at_loading
    st.session_state["stress_ratio"] = stress_ratio
    st.session_state["t_shrink"] = t_shrink

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
        
        # DURABLE PERSISTENCE: Save shared state to disk after every callback update
        # This ensures state survives even if Streamlit session genuinely restarts
        _save_shared_to_disk()
        
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
    # Wrap with debug guard in debug mode
    try:
        from src.debug.state_debug import guard_session_writes, is_debug_enabled
        if is_debug_enabled():
            with guard_session_writes(allowed_keys=set(SHARED_DEFAULTS.keys()), context="update_results"):
                _update_results_impl(**kwargs)
        else:
            _update_results_impl(**kwargs)
    except (ImportError, NameError):
        # Debug module not available, use normal path
        _update_results_impl(**kwargs)


def _update_results_impl(**kwargs):
    """Internal implementation of update_results (separated for debug guard wrapping)."""
    for key, value in kwargs.items():
        if key not in SHARED_DEFAULTS:
            raise KeyError(
                f"[SESSION STATE CONTRACT] Tried to update unknown session key '{key}'.\n"
                f"Add it to SHARED_DEFAULTS before using update_results()."
            )
        st.session_state[key] = value
    
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
