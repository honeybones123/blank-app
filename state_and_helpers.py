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

    "inputs_lig_d": "lig_d",
    "inputs_lig_legs": "lig_legs",
    "inputs_s_lig": "s_lig",

    "inputs_exposure_class": "exposure_class",
    "inputs_s_bar_bot": "s_bar_bot",

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
    nb_bot = st.session_state["nb_bot"]
    nb_top = st.session_state["nb_top"]

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
    Safely update result values (phi_Mu_cap, Mu_utilisation, etc.).
    RULE 4: Only keys listed in RESULT_KEYS are allowed.

    Usage from a page:
        update_results(phi_Mu_cap=123.4, Mu_utilisation=0.85)
    """
    for key, value in kwargs.items():
        if key not in RESULT_KEYS:
            raise KeyError(
                f"[SESSION STATE CONTRACT] Tried to update unknown result key '{key}'.\n"
                f"Add it to RESULT_KEYS + SHARED_DEFAULTS before using update_results()."
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
