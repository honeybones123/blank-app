# creep_page.py
# ============================
# CREEP – AS 3600:2018 Cl. 3.1.8
# ============================

import math
import pandas as pd
import streamlit as st

from state_and_helpers import (
    get_param,
    get_sync_callbacks,
    update_results,  # kept for contract
)
from widgets_helpers import (
    apply_global_widget_css,
    apply_result_page_css,
    number_row,
    info_i_button,
    v2_number_input,
    v2_selectbox,
    v2_checkbox,
    v2_radio,
    render_page_explainer_expander,
    render_result_page_title,
    render_section_title,
    page_divider,
)
from engineering_check_ui import PARAMETRIC_RESULT_COLUMNS, sync_legacy_value_limit
from ui_seamless_steps import render_clickable_summary_table, bind_summary_clicks
from jump_nav import scroll_to_jump_after_render
from step_ui import render_expandable_step
from shear_visuals import build_creep_schematic_plotly


# ------------------------------------------------------------
#  Small helpers / shared styling (same as shrinkage_page)
# ------------------------------------------------------------
def _seed_from_param(name: str, fallback: float) -> float:
    """Seed default widget values from shared state, with safe fallback."""
    try:
        v = get_param(name)
    except TypeError:
        v = None

    try:
        if v is None:
            return float(fallback)
        v = float(v)
        if math.isnan(v):
            return float(fallback)
        return v
    except Exception:
        return float(fallback)


def _inject_calcbox_css():
    """Style markdown blockquotes as blue calc boxes (same feel as shear/deflection)."""
    st.markdown(
        """
<style>
blockquote {
  border-left: 4px solid #1f77b4 !important;
  background-color: rgba(31, 119, 180, 0.08) !important;
  padding: 0.75rem 1rem !important;
  margin: 0.5rem 0 0.75rem 0 !important;
  border-radius: 0 0.35rem 0.35rem 0 !important;
  color: #1a1a1a !important;
  opacity: 1 !important;
  font-size: 0.9rem !important;
  line-height: 1.35 !important;
}
blockquote * {
  color: #1a1a1a !important;
  opacity: 1 !important;
}
blockquote p {
  margin-bottom: 0.5rem !important;
}
blockquote p:last-child {
  margin-bottom: 0 !important;
}
/* Tight stack: calc section heading → expandable step */
p.calc-section-heading-tight {
  margin: 0.35rem 0 0 0 !important;
  font-weight: 600 !important;
  font-size: 1rem !important;
  line-height: 1.25 !important;
}
div[data-testid="stMarkdownContainer"]:has(p.calc-section-heading-tight) {
  margin-bottom: 0 !important;
}
div.element-container:has(div[data-testid="stMarkdownContainer"]:has(p.calc-section-heading-tight)) {
  margin-bottom: 0 !important;
}
</style>
""",
        unsafe_allow_html=True,
    )




# ------------------------------------------------------------
#  Tables – AS 3600:2018 3.1.8.2 & 3.1.8.3
# ------------------------------------------------------------
# Table 3.1.8.2 – Basic creep coefficient φ_cc,b
_BASIC_CREEP_COEFF = {
    20: 5.2,
    25: 4.2,
    32: 3.4,
    40: 2.8,
    50: 2.4,
    65: 2.0,
    80: 1.7,
    100: 1.5,
}

# Table 3.1.8.3 – Final creep coefficient φ*_cc after 30 years
# Structure: {fc: {Env: {th_mm: phi_star}}}
_CREEP_FINAL_TABLE = {
    25: {
        "Arid":      {100: 4.82, 200: 3.90, 400: 3.27},
        "Interior":  {100: 4.48, 200: 3.62, 400: 3.03},
        "Temperate": {100: 4.13, 200: 3.34, 400: 2.80},
        "Tropical":  {100: 3.44, 200: 2.78, 400: 2.33},
    },
    32: {
        "Arid":      {100: 3.90, 200: 3.15, 400: 2.64},
        "Interior":  {100: 3.62, 200: 2.93, 400: 2.46},
        "Temperate": {100: 3.34, 200: 2.70, 400: 2.27},
        "Tropical":  {100: 2.79, 200: 2.25, 400: 1.90},
    },
    40: {
        "Arid":      {100: 3.21, 200: 2.60, 400: 2.18},
        "Interior":  {100: 2.98, 200: 2.41, 400: 2.02},
        "Temperate": {100: 2.75, 200: 2.23, 400: 1.87},
        "Tropical":  {100: 2.30, 200: 1.86, 400: 1.56},
    },
    50: {
        "Arid":      {100: 2.75, 200: 2.23, 400: 1.89},
        "Interior":  {100: 2.56, 200: 2.07, 400: 1.73},
        "Temperate": {100: 2.36, 200: 1.91, 400: 1.60},
        "Tropical":  {100: 1.97, 200: 1.59, 400: 1.33},
    },
    65: {
        "Arid":      {100: 2.07, 200: 1.75, 400: 1.53},
        "Interior":  {100: 1.95, 200: 1.66, 400: 1.46},
        "Temperate": {100: 1.84, 200: 1.59, 400: 1.38},
        "Tropical":  {100: 1.61, 200: 1.38, 400: 1.23},
    },
    80: {
        "Arid":      {100: 1.56, 200: 1.40, 400: 1.29},
        "Interior":  {100: 1.50, 200: 1.36, 400: 1.25},
        "Temperate": {100: 1.45, 200: 1.32, 400: 1.22},
        "Tropical":  {100: 1.33, 200: 1.23, 400: 1.14},
    },
    100: {
        "Arid":      {100: 1.15, 200: 1.14, 400: 1.11},
        "Interior":  {100: 1.15, 200: 1.14, 400: 1.11},
        "Temperate": {100: 1.15, 200: 1.14, 400: 1.11},
        "Tropical":  {100: 1.15, 200: 1.14, 400: 1.11},
    },
}

_ENV_LABELS = {
    "Arid environment": "Arid",
    "Interior environment": "Interior",
    "Temperate inland environment": "Temperate",
    "Tropical / near-coastal / coastal environment": "Tropical",
}


def _closest_fc_row(fc: float) -> int:
    keys = sorted(_CREEP_FINAL_TABLE.keys())
    return min(keys, key=lambda k: abs(fc - k))


def _closest_th(th: float) -> int:
    options = [100, 200, 400]
    return min(options, key=lambda x: abs(th - x))


# ------------------------------------------------------------
#  Factor functions – k2, k3, k4, k5, k6
# ------------------------------------------------------------
def calc_k2_creep(t_days: float, th_mm: float) -> float:
    """
    k2(t, th) from Fig. 3.1.8.3:

        k2 = α2 t^0.8 / (t^0.8 + 0.15 th)
        α2 = 1.0 + 1.12 e^(-0.008 th)
    """
    t = max(t_days, 0.1)
    th = max(th_mm, 1.0)
    alpha2 = 1.0 + 1.12 * math.exp(-0.008 * th)
    num = alpha2 * (t ** 0.8)
    den = (t ** 0.8) + 0.15 * th
    return num / den


def calc_k3(age_at_loading_days: float) -> float:
    """k3 – loading age factor (Cl. 3.1.8.3): 2.7 / [1 + log(τ)] for τ ≥ 1 day."""
    tau = max(age_at_loading_days, 1.0)
    return 2.7 / (1.0 + math.log(tau))


def calc_k4(environment_label: str) -> float:
    """k4 – environment factor (Cl. 3.1.8.3)."""
    short = _ENV_LABELS[environment_label]
    if short == "Arid":
        return 0.70
    if short == "Interior":
        return 0.65
    if short == "Temperate":
        return 0.60
    # Tropical / coastal
    return 0.50


def calc_k5(fc: float, th_mm: float, k4: float) -> float:
    """
    k5 – modification factor for high strength concrete (Cl. 3.1.8.3).

        k5 = 1.0                      for f'c ≤ 50 MPa
        k5 = (2.0 − α3) − 0.02(1 − α3) f'c    for 50 < f'c ≤ 100 MPa
        α3 = 0.7 / (k4 α2)
        α2 = 1.0 + 1.12 e^(−0.008 th)
    """
    if fc <= 50.0:
        return 1.0

    fc_lim = min(fc, 100.0)
    alpha2 = 1.0 + 1.12 * math.exp(-0.008 * th_mm)
    alpha3 = 0.7 / (k4 * alpha2)
    return (2.0 - alpha3) - 0.02 * (1.0 - alpha3) * fc_lim


def calc_k6(stress_ratio: float) -> float:
    """
    k6 – non-linear creep factor for σ₀ > 0.45 f'c,mi (Cl. 3.1.8.3):

        k6 = 1.0                          when σ₀ ≤ 0.45 f'c,mi
        k6 = exp[1.5 (σ₀ / f'c,mi − 0.45)] when σ₀ > 0.45 f'c,mi

    stress_ratio = σ₀ / f'c,mi
    """
    r = max(stress_ratio, 0.0)
    if r <= 0.45:
        return 1.0
    return math.exp(1.5 * (r - 0.45))


def basic_creep_coeff(fc: float) -> float:
    """φ_cc,b from Table 3.1.8.2."""
    keys = sorted(_BASIC_CREEP_COEFF.keys())
    fc_key = min(keys, key=lambda k: abs(fc - k))
    return _BASIC_CREEP_COEFF[fc_key]


def final_creep_coeff_table(fc: float, env_label: str, th_table: float) -> float:
    """φ*_cc (30-year final creep coefficient) from Table 3.1.8.3."""
    fc_key = _closest_fc_row(fc)
    env_key = _ENV_LABELS[env_label]
    th_key = _closest_th(th_table)
    return _CREEP_FINAL_TABLE[fc_key][env_key][th_key]


# ------------------------------------------------------------
#  COMPUTE FUNCTION (no UI rendering)
# ------------------------------------------------------------
def compute_creep_results(publish: bool = True) -> dict:
    """
    Compute creep results without UI rendering.
    
    Args:
        publish: If True, update results via update_results(). Always True for now.
    
    Returns:
        dict with computed results
    """
    # Read geometry from shared state
    b = get_param("b", 300.0)
    D = get_param("D", 600.0)
    
    # Read materials
    fc = get_param("fc", 32.0)
    Ec = get_param("Ec", 30000.0)
    
    # Read creep parameters (use defaults if not in shared state)
    env_option = get_param("env_option", "Temperate inland environment")
    t_creep = get_param("t_creep", 365.0)
    age_at_loading = get_param("age_at_loading", 28.0)
    stress_ratio = get_param("stress_ratio", 0.0)
    sigma0 = get_param("sustained_sigma_cs_mpa", None)
    
    # Read faces option (default to beam)
    faces_option = get_param("member_faces_exposed", "Beam – three faces exposed")
    
    # Calculate geometry
    Ag = b * D  # mm²
    
    if faces_option == "Slab – one face exposed":
        ue = b
    elif faces_option == "Slab – two faces exposed":
        ue = 2.0 * b
    elif faces_option == "Beam – three faces exposed":
        ue = b + 2.0 * D
    else:  # "Column – four faces exposed"
        ue = 2.0 * (b + D)
    
    th_raw = 2.0 * Ag / ue if ue > 0 else 0.0
    th_table = _closest_th(th_raw)
    
    # Calculate creep coefficients
    phi_cc_b = basic_creep_coeff(fc)
    k2 = calc_k2_creep(t_creep, th_table)
    k3 = calc_k3(age_at_loading)
    k4 = calc_k4(env_option)
    k5 = calc_k5(fc, th_table, k4)
    k6 = calc_k6(stress_ratio)
    
    phi_cc_t = k2 * k3 * k4 * k5 * k6 * phi_cc_b
    phi_cc_star_table = final_creep_coeff_table(fc, env_option, th_table)
    
    # Calculate strain (stress ratio is derived from sustained action and section modulus)
    if sigma0 is None:
        sigma0 = stress_ratio * fc
    eps_cc = phi_cc_t * sigma0 / Ec if Ec > 0 else 0.0  # dimensionless
    eps_cc_micro = eps_cc * 1e6
    
    # Update results if publish=True
    if publish:
        update_results(
            phi_cc_t=phi_cc_t,
            phi_cc_star_table=phi_cc_star_table,
            k2_creep=k2,
            k3_creep=k3,
            k4_creep=k4,
            k5_creep=k5,
            k6_creep=k6,
        )
    
    # Build steps list (placeholder)
    steps = ["(Detailed steps not available for this module yet)"]
    
    return {
        "phi_cc_t": phi_cc_t,
        "phi_cc_star_table": phi_cc_star_table,
        "eps_cc_micro": eps_cc_micro,
        "creep_steps": steps,
    }


# ------------------------------------------------------------
#  MAIN RENDER FUNCTION
# ------------------------------------------------------------
def render_creep():
    apply_global_widget_css()
    apply_result_page_css()
    _inject_calcbox_css()
    sync_callbacks = get_sync_callbacks()  # keeps contract with Inputs page

    # --------------------------------------------------------
    # Page title
    # --------------------------------------------------------
    def _render_creep_explainer() -> None:
        st.markdown(
            r"""
This page computes **concrete creep coefficient** and **creep strain** in accordance with  
**AS 3600:2018 Clause 3.1.8**, including:

- **Basic creep coefficient** ($\varphi_{cc,b}$) — Table 3.1.8.2  
- **Design creep coefficient** at time $t$, $\varphi_{cc}(t) = k_2 k_3 k_4 k_5 k_6 \, \varphi_{cc,b}$ — Cl. 3.1.8.3  
- **Final creep coefficient** after 30 years, $\varphi^{\*}_{cc}$ — Table 3.1.8.3  
- **Creep strain** at time $t$, $\varepsilon_{cc} = \varphi_{cc}(t)\, \sigma_0 / E_c$ — Cl. 3.1.8.1

Creep coefficients are dimensionless; creep strains are reported in microstrain ($\times 10^{-6}$).
"""
        )

    render_result_page_title("Creep")

    # --------------------------------------------------------
    # Reserve space for top summary table (will be filled after calculations)
    # --------------------------------------------------------
    summary_placeholder = st.empty()
    
    # --------------------------------------------------------
    col_geom, col_env, col_load = st.columns(3)

    # --- Geometry ---
    with col_geom:
        st.markdown("**Geometry / member**")
        b_val = float(st.session_state.get("inputs_b", get_param("b", 400.0)))
        D_val = float(st.session_state.get("inputs_D", get_param("D", 600.0)))

        number_row(
            "Section width b (mm)",
            "inputs_b",
            b_val,
            sync_callbacks,
        )

        number_row(
            "Overall depth D (mm)",
            "inputs_D",
            D_val,
            sync_callbacks,
        )
        b = float(get_param("b", b_val))
        D = float(get_param("D", D_val))

        col1, col2 = st.columns([1, 2])
        with col1:
            st.markdown("<div class='sb-label'>Member / faces exposed</div>", unsafe_allow_html=True)
        with col2:
            faces_options = [
                "Slab – one face exposed",
                "Slab – two faces exposed",
                "Beam – three faces exposed",
                "Column – four faces exposed",
            ]
            faces_current = get_param("member_faces_exposed", "Beam – three faces exposed")
            if faces_current not in faces_options:
                faces_current = "Beam – three faces exposed"
            faces_option = v2_selectbox(
                label="Value",
                key="cr_faces",
                options=faces_options,
                default_index=faces_options.index(faces_current),
                label_visibility="collapsed",
                on_change=sync_callbacks["cr_faces"],
            )

    # --- Environment & material ---
    with col_env:
        st.markdown("**Material / environment**")
        fc_val = float(st.session_state.get("inputs_fc", get_param("fc", 32.0)))
        Ec_val = float(get_param("Ec", 30000.0) or 30000.0)

        number_row(
            "Concrete strength f'c (MPa)",
            "inputs_fc",
            fc_val,
            sync_callbacks,
        )

        fc = float(get_param("fc", fc_val))
        Ec = float(get_param("Ec", Ec_val))

        col1, col2 = st.columns([1, 2])
        with col1:
            st.markdown("<div class='sb-label'>Creep environment (Tables 3.1.8.2 & 3.1.8.3)</div>", unsafe_allow_html=True)
        with col2:
            env_options = [
                "Arid environment",
                "Interior environment",
                "Temperate inland environment",
                "Tropical / near-coastal / coastal environment",
            ]
            env_current = get_param("env_option", "Temperate inland environment")
            if env_current not in env_options:
                env_current = "Temperate inland environment"
            env_option = v2_selectbox(
                label="Value",
                key="cr_env",
                options=env_options,
                default_index=env_options.index(env_current),
                label_visibility="collapsed",
                on_change=sync_callbacks["cr_env"],
            )

    # --- Loading data ---
    with col_load:
        st.markdown("**Time / loading**")
        col1, col2 = st.columns([1, 2])
        with col1:
            st.markdown("<div class='sb-label'>Time after loading t (days)</div>", unsafe_allow_html=True)
        with col2:
            t_creep = v2_number_input(
                label="Value",
                key="inputs_t_creep",
                default=float(get_param("t_creep", 365.0)),
                step=10.0,
                min_value=1.0,
                label_visibility="collapsed",
                on_change=sync_callbacks["inputs_t_creep"],
            )

        col1, col2 = st.columns([1, 2])
        with col1:
            st.markdown("<div class='sb-label'>Age at loading τ (days)</div>", unsafe_allow_html=True)
        with col2:
            age_at_loading = v2_number_input(
                label="Value",
                key="inputs_age_at_loading",
                default=float(get_param("age_at_loading", 28.0)),
                step=1.0,
                min_value=1.0,
                label_visibility="collapsed",
                on_change=sync_callbacks["inputs_age_at_loading"],
            )


    page_divider()

    # --------------------------------------------------------
    # Derived geometry: Ag, u_e, t_h
    # --------------------------------------------------------
    Ag = b * D  # mm²

    if faces_option == "Slab – one face exposed":
        ue = b
    elif faces_option == "Slab – two faces exposed":
        ue = 2.0 * b
    elif faces_option == "Beam – three faces exposed":
        ue = b + 2.0 * D
    else:  # "Column – four faces exposed"
        ue = 2.0 * (b + D)

    th_raw = 2.0 * Ag / ue if ue > 0 else 0.0
    # For Fig. 3.1.8.3 & Table 3.1.8.3, th is rounded to 100 / 200 / 400 mm
    th_table = _closest_th(th_raw)

    # --------------------------------------------------------
    # Creep coefficients & strain
    # --------------------------------------------------------
    stress_ratio = float(get_param("stress_ratio", 0.0) or 0.0)
    sustained_mstar = float(get_param("sustained_Mstar_kNm", 0.0) or 0.0)
    sustained_sigma_cs = float(get_param("sustained_sigma_cs_mpa", 0.0) or 0.0)
    sustained_z = float(get_param("sustained_section_modulus_mm3", 0.0) or 0.0)
    sustained_fibre = str(get_param("sustained_compression_fibre", "top") or "top")

    phi_cc_b = basic_creep_coeff(fc)
    k2 = calc_k2_creep(t_creep, th_table)
    k3 = calc_k3(age_at_loading)
    k4 = calc_k4(env_option)
    k5 = calc_k5(fc, th_table, k4)
    k6 = calc_k6(stress_ratio)

    phi_cc_t = k2 * k3 * k4 * k5 * k6 * phi_cc_b
    phi_cc_star_table = final_creep_coeff_table(fc, env_option, th_table)

    # --------------------------------------------------------
    # Publish key creep results to shared state
    #   (for reuse in crack-width page etc.)
    # --------------------------------------------------------
    update_results(
        phi_cc_t=phi_cc_t,  # design creep coeff at t
        phi_cc_star_table=phi_cc_star_table,  # 30-year table value
        k2_creep=k2,
        k3_creep=k3,
        k4_creep=k4,
        k5_creep=k5,
        k6_creep=k6,
    )

    sigma0 = sustained_sigma_cs if sustained_sigma_cs > 0 else (stress_ratio * fc)
    # Safety check: prevent division by zero if Ec is 0 (shouldn't happen, but protect against stale state)
    if Ec == 0 or Ec is None:
        Ec = 30000.0  # Default value from SHARED_DEFAULTS
    eps_cc = phi_cc_t * sigma0 / Ec  # dimensionless
    eps_cc_micro = eps_cc * 1e6

    # --------------------------------------------------------
    # Top-of-page clickable summary table (render in placeholder)
    # --------------------------------------------------------
    with summary_placeholder.container():
        # Build ROWS for top summary table
        ROWS = [
            sync_legacy_value_limit({
                "uid": "creep_phi_cc_t",
                "title": "Design creep coefficient ϕ_cc(t)",
                "capacity": f"ϕ_cc(t) = {phi_cc_t:.2f}",
                "action": "—",
                "util": "—",
                "status": "—",
                "ok": None,
                "tab": "Creep coefficient ϕ_cc(t)",
            }),
            sync_legacy_value_limit({
                "uid": "creep_phi_cc_table",
                "title": "Final creep coefficient ϕ*cc (30y, table)",
                "capacity": f"ϕ*cc,table = {phi_cc_star_table:.2f}",
                "action": "—",
                "util": "—",
                "status": "—",
                "ok": None,
                "tab": "Creep coefficient ϕ_cc(t)",
            }),
            sync_legacy_value_limit({
                "uid": "creep_eps_cc",
                "title": "Creep strain ε_cc(t)",
                "capacity": f"ε_cc = {eps_cc_micro:.1f} µε",
                "action": "—",
                "util": "—",
                "status": "—",
                "ok": None,
                "tab": "Creep strain ε_cc",
            }),
        ]

        render_page_explainer_expander(_render_creep_explainer)
        render_clickable_summary_table(
            ROWS, key_prefix="creep_page_summary", columns=PARAMETRIC_RESULT_COLUMNS
        )
        bind_summary_clicks()
        page_divider()

        st.markdown("**Concrete creep under sustained load**")
        fig_creep_schematic = build_creep_schematic_plotly()
        _creep_l, _creep_c, _creep_r = st.columns([1, 8, 1])
        with _creep_c:
            st.plotly_chart(
                fig_creep_schematic,
                use_container_width=True,
                config={
                    "displayModeBar": False,
                    "staticPlot": True,
                },
            )
        page_divider()

    # --------------------------------------------------------
    # Calculation sections — three tabs (t_h + k₂ merged; ϕ_cc; ε_cc)
    # --------------------------------------------------------
    render_section_title("Creep checks")

    st.markdown(
        """
<style>
/* Tighten gap between tab labels and first calc card (creep page only) */
div[data-testid="stTabs"] [data-baseweb="tab-panel"] {
  padding-top: 0.35rem !important;
}
</style>
""",
        unsafe_allow_html=True,
    )

    tab_th_k2, tab_phi, tab_eps = st.tabs(
        [
            "Notional thickness t_h and k₂",
            "Creep coefficient ϕ_cc(t)",
            "Creep strain ε_cc",
        ]
    )

    # Calculate alpha2 for display in k2 calc box
    alpha2 = 1.0 + 1.12 * math.exp(-0.008 * th_table)

    # Step 1: Notional thickness t_h (raw)
    def render_th_raw():
        return f"""
**Summary**

| Quantity | Value |
|----------|-------|
| Section width b | {b:.1f} mm |
| Overall depth D | {D:.1f} mm |
| Gross area A_g | {Ag:.0f} mm² |
| Faces exposed | {faces_option} |
| Exposed perimeter u_e | {ue:.1f} mm |
| **Notional thickness t_h** | **{th_raw:.1f} mm** |

**Purpose**

Determine notional thickness t_h from section geometry and exposed perimeter.

**Inputs**

- Section width: b = {b:.1f} mm
- Overall depth: D = {D:.1f} mm
- Gross area: A_g = b·D = {Ag:.0f} mm²
- Faces exposed: {faces_option}
- Exposed perimeter: u_e = {ue:.1f} mm

**Calculation**

t_h = 2·A_g / u_e

**Substitution**

t_h = 2 × {Ag:.0f} / {ue:.1f} ≈ {th_raw:.1f} mm

**Result**

t_h = {th_raw:.1f} mm

_Ref: AS 3600:2018 definition of notional thickness (t_h = 2 A_g/u_e)._
"""

    # Step 2: Adopted thickness for AS figure/table
    def render_th_table():
        return f"""
**Summary**

| Quantity | Value |
|----------|-------|
| Raw notional thickness t_h | {th_raw:.1f} mm |
| **Adopted thickness t_h,AS** | **{th_table:d} mm** |

**Purpose**

Map the raw notional thickness to the discrete AS curve thickness used in the figure/table.

**Inputs**

- Raw notional thickness: t_h = {th_raw:.1f} mm (from previous step)
- Discrete curve options: 100, 200, 400 mm

**Decision rule**

The raw notional thickness is mapped to the nearest standard value from the set {{100, 200, 400}} mm for compatibility with Fig. 3.1.8.3 and Table 3.1.8.3.

**Calculation**

Raw value: t_h = {th_raw:.1f} mm

Nearest standard value: t_h,AS = {th_table:d} mm

**Result**

Adopted notional thickness: t_h,AS = {th_table:d} mm

_Ref: AS 3600:2018 Fig. 3.1.8.3 and Table 3.1.8.3 use discrete thickness values._
"""

    # Step 3: Time-development factor k2
    def render_k2():
        return f"""
**Summary**

| Quantity | Value |
|----------|-------|
| Time after loading t | {t_creep:.0f} days |
| Adopted thickness t_h,AS | {th_table:d} mm |
| Parameter α₂ | {alpha2:.4f} |
| **Time-development factor k₂** | **{k2:.3f}** |

**Purpose**

Compute k₂ as a function of time and adopted notional thickness.

**Inputs**

- Time after loading: t = {t_creep:.0f} days
- Adopted notional thickness: t_h,AS = {th_table:d} mm (from previous step)

**Calculation**

k₂(t, t_h) = α₂ · t^0.8 / ( t^0.8 + 0.15·t_h )

where:

α₂ = 1.0 + 1.12·exp( −0.008·t_h )

**Substitution**

α₂ = 1.0 + 1.12·exp( −0.008 × {th_table:d} ) ≈ {alpha2:.4f}

For t = {t_creep:.0f} days and t_h = {th_table:d} mm:

k₂ = {alpha2:.4f} × {t_creep:.0f}^0.8 / ( {t_creep:.0f}^0.8 + 0.15 × {th_table:d} )

k₂ ≈ {k2:.3f}

**Result**

k₂ = {k2:.3f}

_Ref: AS 3600:2018 Cl. 3.1.8.3 and Fig. 3.1.8.3._
"""

    with tab_th_k2:
        render_expandable_step(
            page_key="creep_geom",
            step_id="creep_th_raw",
            title="Notional thickness t_h (raw)",
            summary_md=[
                "Check 1.1 — Determine notional thickness from section geometry and exposed perimeter",
                f"Result: t_h = {th_raw:.1f} mm",
            ],
            status_kind=None,
            calc_md=render_th_raw(),
        )
        render_expandable_step(
            page_key="creep_geom",
            step_id="creep_th_table",
            title="Adopted thickness for AS figure/table",
            summary_md=[
                "Check 1.2 — Map raw notional thickness to discrete AS curve thickness",
                f"Adopted: t_h,AS = {th_table:d} mm",
            ],
            status_kind=None,
            calc_md=render_th_table(),
        )
        render_expandable_step(
            page_key="creep_geom",
            step_id="creep_k2",
            title="Time-development factor k₂",
            summary_md=[
                "Check 1.3 — Compute k₂ as a function of time and adopted notional thickness",
                f"Result: k₂ = {k2:.3f}",
            ],
            status_kind=None,
            calc_md=render_k2(),
        )

    # Step 1: Creep coefficient at time t
    def render_phi_cc_t():
        return rf"""
**Summary**

| Quantity | Value |
|----------|-------|
| Basic creep coefficient φ_cc,b | {phi_cc_b:.2f} |
| Time-development factor k₂ | {k2:.3f} |
| Age-at-loading factor k₃ | {k3:.3f} |
| Environment factor k₄ | {k4:.2f} |
| High-strength factor k₅ | {k5:.3f} |
| Non-linear creep factor k₆ | {k6:.3f} |
| **Design creep coefficient φ_cc(t)** | **{phi_cc_t:.2f}** |

**Purpose**

Compute the **design creep coefficient** at time $t$:

\[
\varphi_{{cc}}(t) = k_2 k_3 k_4 k_5 k_6 \, \varphi_{{cc,b}}
\]

**Inputs**

- Concrete strength: $f'_c = {fc:.1f}\,\text{{MPa}}$  
- Environment: **{env_option}**  
- Age at loading: $\tau = {age_at_loading:.0f}\,\text{{days}}$  
- Time after loading: $t = {t_creep:.0f}\,\text{{days}}$  
- Notional thickness for tables: $t_h = {th_table:d}\,\text{{mm}}$  
- Governing sustained SLS moment: $M_{{sust}} = {sustained_mstar:.2f}\,\text{{kNm}}$  
- Concrete compression fibre: {sustained_fibre}  
- Section modulus at compression fibre: $Z_{{comp}} = {sustained_z:.2e}\,\text{{mm}}^3$  
- Sustained concrete stress: $\sigma_{{cs}} = {sigma0:.2f}\,\text{{MPa}}$  
- Sustained stress ratio (derived): $\sigma_{{cs}}/f'_{{c}} = {stress_ratio:.3f}$  

**Basic creep coefficient** (Table 3.1.8.2)

\[
\varphi_{{cc,b}} \approx {phi_cc_b:.2f}
\]

**Factors**

- $k_2(t, t_h) \approx {k2:.3f}$  (Fig. 3.1.8.3)  
- $k_3(\tau) = 2.7/[1 + \ln(\tau)] \approx {k3:.3f}$  
- $k_4$ (environment factor) $= {k4:.2f}$  
- $k_5$ (high-strength modification) $= {k5:.3f}$  
- $k_6$ (non-linear creep for high stress) $= {k6:.3f}$  

**Substitution**

\[
\varphi_{{cc}}(t)
= {k2:.3f} \times {k3:.3f} \times {k4:.2f} \times {k5:.3f} \times {k6:.3f}
\times {phi_cc_b:.2f}
\approx {phi_cc_t:.2f}
\]

**Result**

Design creep coefficient at $t = {t_creep:.0f}$ days:

\[
\varphi_{{cc}}(t) \approx {phi_cc_t:.2f}
\]

_Ref: AS 3600:2018 Cl. 3.1.8.3; Tables 3.1.8.2 & 3.1.8.3; Fig. 3.1.8.3._
"""
    
    def phi_cc_t_info_fn():
        with info_i_button(help_text="Factor explanations"):
            st.markdown(rf"""
**Factor explanations:**

• **k₄ (environment factor):** Comes from selected environment class per AS 3600 tables. Not user-entered directly.

• **k₅ (high-strength modification):** Derived from concrete strength f'c. Often equals 1.0 for normal-strength concrete.

• **k₆ (non-linear creep factor):** Derived from sustained stress ratio σ₀ over f'c. Equals 1.0 unless high sustained stress.

*These are code-defined modifiers derived from other inputs.*
""")

    # Step 2: Long-term tabulated creep coefficient (30 years)
    def render_phi_cc_table():
        return rf"""
**Summary**

| Quantity | Value |
|----------|-------|
| Computed value at t = {t_creep:.0f} days | φ_cc(t) = {phi_cc_t:.2f} |
| **Tabulated 30-year value** | **φ*_cc,table = {phi_cc_star_table:.2f}** |

**Purpose**

AS 3600:2018 Table 3.1.8.3 provides the **final 30-year creep coefficient**
for comparison with the computed value at time $t$.

**Table value**

For the same $f'_c$, environment and $t_h$, the **final 30-year coefficient**
from Table 3.1.8.3 is:

\[
\varphi^*_{{cc,\text{{table}}}} \approx {phi_cc_star_table:.2f}
\]

**Comparison**

- Computed value at $t = {t_creep:.0f}$ days: $\varphi_{{cc}}(t) \approx {phi_cc_t:.2f}$  
- Tabulated long-term value (30 years): $\varphi^*_{{cc,\text{{table}}}} \approx {phi_cc_star_table:.2f}$

_Ref: AS 3600:2018 Table 3.1.8.3._
"""

    with tab_phi:
        render_expandable_step(
            page_key="creep_coeff",
            step_id="creep_phi_cc_t",
            title="Creep coefficient at time t",
            summary_md=[
                "Check 2 — Compute design creep coefficient from basic coefficient and factors",
                rf"Result: $\varphi_{{cc}}(t) = {phi_cc_t:.2f}$ at $t = {t_creep:.0f}$ days",
            ],
            status_kind=None,
            calc_md=render_phi_cc_t(),
            info_render_fn=phi_cc_t_info_fn,
        )
        render_expandable_step(
            page_key="creep_coeff",
            step_id="creep_phi_cc_table",
            title="Long-term tabulated creep coefficient (30 years)",
            summary_md=[
                "Check 3 — AS table provides long-term value for comparison",
                rf"Table value (30 years): $\varphi^*_{{cc,\text{{table}}}} = {phi_cc_star_table:.2f}$",
            ],
            status_kind=None,
            calc_md=render_phi_cc_table(),
        )

    # Step 1: Sustained stress at loading σ₀
    def render_sigma0():
        return rf"""
**Summary**

| Quantity | Value |
|----------|-------|
| Governing sustained SLS moment M_sust | {sustained_mstar:.2f} kNm |
| Compression fibre | {sustained_fibre} |
| Section modulus at compression fibre Z_comp | {sustained_z:.2e} mm³ |
| **Sustained concrete stress σ_cs** | **{sigma0:.2f} MPa** |

**Purpose**

Derive sustained concrete compressive stress from the governing sustained SLS action and section response.

**Inputs**

- Governing sustained SLS moment: $M_{{sust}} = {sustained_mstar:.2f}\,\text{{kNm}}$
- Compression fibre section modulus: $Z_{{comp}} = {sustained_z:.2e}\,\text{{mm}}^3$

**Calculation**

\[
\sigma_{{cs}} = \frac{{M_{{sust}} \times 10^6}}{{Z_{{comp}}}}
\]

**Substitution**

\[
\sigma_{{cs}} = \frac{{{sustained_mstar:.2f}\times 10^6}}{{{sustained_z:.2e}}} \approx {sigma0:.2f}\,\text{{MPa}}
\]

**Result**

\[
\sigma_{{cs}} = {sigma0:.2f}\,\text{{MPa}}
\]

_Ref: AS 3600:2018 Cl. 3.1.8.1._
"""
    
    def sigma0_info_fn():
        with info_i_button(help_text="Design strength at loading (f'c,mi)"):
            st.markdown(rf"""
**Design strength at loading ($f'_{{c,mi}}$):**

$f'_{{c,mi}}$ represents the concrete compressive strength at the time of loading. In this calculation, it is approximated as $f'_c$ (the 28-day design strength) for simplicity. This approximation is reasonable when loading occurs near 28 days or when precise loading age data is not available.

In this app flow, sustained stress is derived from sustained action and section response:
$\sigma_{{cs}} = M_{{sust}}/Z_{{comp}}$, then the stress ratio is obtained from $\sigma_{{cs}}/f'_c$.

*Note: Compression is taken as positive magnitude in this calculation.*
""")

    # Step 2: Sustained stress ratio (derived)
    def render_stress_ratio():
        return rf"""
**Summary**

| Quantity | Value |
|----------|-------|
| Sustained concrete stress σ_cs | {sigma0:.2f} MPa |
| Concrete strength f'c | {fc:.1f} MPa |
| **Sustained stress ratio (derived)** | **{stress_ratio:.3f}** |

**Purpose**

Express sustained compressive stress as a ratio of concrete strength for use in the k₆ non-linear creep factor.

**Calculation**

\[
\text{{stress\_ratio}} = \frac{{\sigma_{{cs}}}}{{f'_c}}
\]

**Substitution**

\[
\text{{stress\_ratio}} = \frac{{{sigma0:.2f}}}{{{fc:.1f}}} = {stress_ratio:.3f}
\]

**Result**

\[
\text{{stress\_ratio}} = {stress_ratio:.3f}
\]
"""

    # Step 3: Creep strain ε_cc from creep coefficient
    def render_eps_cc():
        return rf"""
**Summary**

| Quantity | Value |
|----------|-------|
| Design creep coefficient φ_cc(t) | {phi_cc_t:.2f} |
| Sustained stress σ_cs | {sigma0:.2f} MPa |
| Modulus of elasticity E_c | {Ec:.0f} MPa |
| **Creep strain ε_cc** | **{eps_cc_micro:.1f} με** |

**Purpose**

Convert creep coefficient $\varphi_{{cc}}(t)$ to creep strain under sustained stress $\sigma_{{cs}}$.

**Inputs**

- Design creep coefficient at time $t$:  
  \[
  \varphi_{{cc}}(t) \approx {phi_cc_t:.2f}
  \]
- Sustained stress: $\sigma_{{cs}} = {sigma0:.2f}\,\text{{MPa}}$ (from previous step)
- Modulus of elasticity: $E_c = {Ec:.0f}\,\text{{MPa}}$

**Calculation**

\[
\varepsilon_{{cc}} = \varphi_{{cc}}(t)\, \frac{{\sigma_{{cs}}}}{{E_c}}
\]

**Substitution**

\[
\varepsilon_{{cc}}
= {phi_cc_t:.2f} \times \frac{{{sigma0:.2f}}}{{{Ec:.0f}}}
\approx {eps_cc:.3e}
\]

Expressed in microstrain:

\[
\varepsilon_{{cc}} \approx {eps_cc_micro:.1f} \times 10^{{-6}} = {eps_cc_micro:.1f}\,\mu\varepsilon
\]

**Result**

\[
\varepsilon_{{cc}} = {eps_cc_micro:.1f}\,\mu\varepsilon
\]

_Ref: AS 3600:2018 Cl. 3.1.8.1._
"""

    with tab_eps:
        render_expandable_step(
            page_key="creep_strain",
            step_id="creep_sigma0",
            title="Sustained stress at loading σ₀",
            summary_md=[
                "Check 4.1 — Derive sustained concrete compressive stress from sustained action and section modulus",
                rf"Result: $\sigma_{{cs}} = {sigma0:.2f}$ MPa",
            ],
            status_kind=None,
            calc_md=render_sigma0(),
            info_render_fn=sigma0_info_fn,
        )
        render_expandable_step(
            page_key="creep_strain",
            step_id="creep_stress_ratio",
            title="Sustained stress ratio (derived)",
            summary_md=[
                "Check 4.2 — Derive sustained stress ratio from sustained stress and concrete strength",
                rf"Result: stress_ratio = {stress_ratio:.3f}",
            ],
            status_kind=None,
            calc_md=render_stress_ratio(),
        )
        render_expandable_step(
            page_key="creep_strain",
            step_id="creep_eps_cc",
            title="Creep strain ε_cc at time t",
            summary_md=[
                "Check 4.3 — Convert creep coefficient to creep strain under sustained stress",
                rf"Result: $\varepsilon_{{cc}} = {eps_cc_micro:.1f}$ με",
            ],
            status_kind=None,
            calc_md=render_eps_cc(),
        )

    scroll_to_jump_after_render()

