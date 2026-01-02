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
from widgets_helpers import apply_global_widget_css, number_row, calcbox, info_i_button, page_divider
from summary_table_ui import render_clickable_summary_table
from ui_seamless_steps import bind_summary_clicks
from jump_nav import scroll_to_jump_after_render
from step_ui import render_expandable_step


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
#  MAIN RENDER FUNCTION
# ------------------------------------------------------------
def render_creep():
    apply_global_widget_css()
    _inject_calcbox_css()
    get_sync_callbacks()  # keeps contract with Inputs page

    # --------------------------------------------------------
    # Page title
    # --------------------------------------------------------
    st.title("Creep – AS 3600:2018 Clause 3.1.8")

    # --------------------------------------------------------
    # Page description (directly under title)
    # --------------------------------------------------------
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

    # --------------------------------------------------------
    # Reserve space for top summary table (will be filled after calculations)
    # --------------------------------------------------------
    summary_placeholder = st.empty()
    
    # --------------------------------------------------------
    # Geometry, exposure & loading
    # --------------------------------------------------------
    st.markdown("### Geometry, exposure & loading")

    col_geom, col_env, col_load = st.columns(3)

    # --- Geometry ---
    with col_geom:
        b_seed = _seed_from_param("b", 300.0)
        D_seed = _seed_from_param("D", 600.0)

        col1, col2 = st.columns([1, 2])
        with col1:
            st.markdown("<div class='sb-label'>Section width b (mm)</div>", unsafe_allow_html=True)
        with col2:
            b = st.number_input(
                "",
                value=b_seed,
                step=10.0,
                key="cr_b",
                label_visibility="collapsed",
            )

        col1, col2 = st.columns([1, 2])
        with col1:
            st.markdown("<div class='sb-label'>Overall depth D (mm)</div>", unsafe_allow_html=True)
        with col2:
            D = st.number_input(
                "",
                value=D_seed,
                step=10.0,
                key="cr_D",
                label_visibility="collapsed",
            )

        col1, col2 = st.columns([1, 2])
        with col1:
            st.markdown("<div class='sb-label'>Member / faces exposed</div>", unsafe_allow_html=True)
        with col2:
            faces_option = st.selectbox(
                "",
                [
                    "Slab – one face exposed",
                    "Slab – two faces exposed",
                    "Beam – three faces exposed",
                    "Column – four faces exposed",
                ],
                index=2,
                key="cr_faces",
                label_visibility="collapsed",
            )

    # --- Environment & material ---
    with col_env:
        fc_seed = _seed_from_param("fc", 32.0)
        Ec_seed = _seed_from_param("Ec", 30000.0)

        col1, col2 = st.columns([1, 2])
        with col1:
            st.markdown("<div class='sb-label'>Concrete strength f'c (MPa)</div>", unsafe_allow_html=True)
        with col2:
            fc = st.number_input(
                "",
                value=fc_seed,
                step=1.0,
                key="cr_fc",
                label_visibility="collapsed",
            )

        col1, col2 = st.columns([1, 2])
        with col1:
            st.markdown("<div class='sb-label'>Concrete modulus Ec (MPa)</div>", unsafe_allow_html=True)
        with col2:
            Ec = st.number_input(
                "",
                value=Ec_seed,
                step=1000.0,
                key="cr_Ec",
                label_visibility="collapsed",
            )

        col1, col2 = st.columns([1, 2])
        with col1:
            st.markdown("<div class='sb-label'>Creep environment (Tables 3.1.8.2 & 3.1.8.3)</div>", unsafe_allow_html=True)
        with col2:
            env_option = st.selectbox(
                "",
                [
                    "Arid environment",
                    "Interior environment",
                    "Temperate inland environment",
                    "Tropical / near-coastal / coastal environment",
                ],
                index=2,
                key="cr_env",
                label_visibility="collapsed",
            )

    # --- Loading data ---
    with col_load:
        col1, col2 = st.columns([1, 2])
        with col1:
            st.markdown("<div class='sb-label'>Time after loading t (days)</div>", unsafe_allow_html=True)
        with col2:
            t_creep = st.number_input(
                "",
                value=365.0,
                step=10.0,
                min_value=1.0,
                key="cr_t_creep",
                label_visibility="collapsed",
            )

        col1, col2 = st.columns([1, 2])
        with col1:
            st.markdown("<div class='sb-label'>Age at loading τ (days)</div>", unsafe_allow_html=True)
        with col2:
            age_at_loading = st.number_input(
                "",
                value=28.0,
                step=1.0,
                min_value=1.0,
                key="cr_tau",
                label_visibility="collapsed",
            )

        col1, col2 = st.columns([1, 2])
        with col1:
            st.markdown("<div class='sb-label'>Sustained stress ratio σ₀ / f'c,mi</div>", unsafe_allow_html=True)
        with col2:
            stress_ratio = st.number_input(
                "",
                value=0.30,
                step=0.05,
                min_value=0.0,
                max_value=0.80,
                key="cr_sigma_ratio",
                label_visibility="collapsed",
            )

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

    sigma0 = stress_ratio * fc  # MPa (approx using f'c,mi ≈ f'c)
    eps_cc = phi_cc_t * sigma0 / Ec  # dimensionless
    eps_cc_micro = eps_cc * 1e6

    # --------------------------------------------------------
    # Top-of-page clickable summary table (render in placeholder)
    # --------------------------------------------------------
    def uid_to_tab_and_step(uid):
        """Map summary row UID to target tab name and step UID."""
        mapping = {
            "creep_phi_cc_t": ("Creep coefficient ϕ_cc(t)", "creep_phi_cc_t"),
            "creep_phi_cc_table": ("Creep coefficient ϕ_cc(t)", "creep_phi_cc_table"),
            "creep_eps_cc": ("Creep strain ε_cc", "creep_eps_cc"),
        }
        return mapping.get(uid, (None, None))
    
    with summary_placeholder.container():
        # Build ROWS for top summary table
        ROWS = [
            {
                "uid": "creep_phi_cc_t",
                "title": "Design creep coefficient ϕ_cc(t)",
                "value": f"ϕ_cc(t) = {phi_cc_t:.2f}",
                "limit": "—",
                "util": "—",
                "status": "—",
                "ok": None,
                "tab": "Creep coefficient ϕ_cc(t)",
            },
            {
                "uid": "creep_phi_cc_table",
                "title": "Final creep coefficient ϕ*cc (30y, table)",
                "value": f"ϕ*cc,table = {phi_cc_star_table:.2f}",
                "limit": "—",
                "util": "—",
                "status": "—",
                "ok": None,
                "tab": "Creep coefficient ϕ_cc(t)",
            },
            {
                "uid": "creep_eps_cc",
                "title": "Creep strain ε_cc(t)",
                "value": f"ε_cc = {eps_cc_micro:.1f} µε",
                "limit": "—",
                "util": "—",
                "status": "—",
                "ok": None,
                "tab": "Creep strain ε_cc",
            },
        ]
        
        # Render top summary table
        st.markdown("## Creep — Summary")
        clicked_uid = render_clickable_summary_table(ROWS, key="creep_page_summary")
        
    # Handle clicked row - set state for expanding step (JavaScript will handle tab switching and scrolling)
    if clicked_uid:
        tab_name, step_uid = uid_to_tab_and_step(clicked_uid)
        if tab_name and step_uid:
            # Set step_open_{step_uid} to True (matches render_expandable_step pattern)
            st.session_state[f"step_open_{step_uid}"] = True
            # Set tab-local pending scroll state
            if tab_name == "Creep coefficient ϕ_cc(t)":
                st.session_state["creep_coeff_pending_scroll_uid"] = step_uid
            elif tab_name == "Creep strain ε_cc":
                st.session_state["creep_strain_pending_scroll_uid"] = step_uid
        
        page_divider()

    # --------------------------------------------------------
    # Tabs: geometry, coefficient, strain
    # --------------------------------------------------------
    tab_geom, tab_coeff, tab_strain = st.tabs(
        [
            "Geometry & tₕ",
            "Creep coefficient ϕ_cc(t)",
            "Creep strain ε_cc",
        ]
    )

    # ---------- Tab 1: Geometry & t_h / k2 ----------
    with tab_geom:
        st.subheader("Notional thickness tₕ & k₂ – AS 3600 (2Aᵍ / uₑ, Fig. 3.1.8.3)")
        
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
        
        render_expandable_step(
            page_key="creep_geom",
            step_id="creep_th_raw",
            title="Notional thickness t_h (raw)",
            summary_md=[
                f"Result: t_h = {th_raw:.1f} mm",
                "Determine notional thickness from section geometry and exposed perimeter"
            ],
            status_kind=None,
            calc_md=render_th_raw(),
        )

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
        
        render_expandable_step(
            page_key="creep_geom",
            step_id="creep_th_table",
            title="Adopted thickness for AS figure/table",
            summary_md=[
                f"Adopted: t_h,AS = {th_table:d} mm",
                "Map raw notional thickness to discrete AS curve thickness"
            ],
            status_kind=None,
            calc_md=render_th_table(),
        )

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
        
        render_expandable_step(
            page_key="creep_geom",
            step_id="creep_k2",
            title="Time-development factor k₂",
            summary_md=[
                f"Result: k₂ = {k2:.3f}",
                "Compute k₂ as a function of time and adopted notional thickness"
            ],
            status_kind=None,
            calc_md=render_k2(),
        )

    # ---------- Tab 2: Creep coefficient ----------
    with tab_coeff:
        st.subheader("Design creep coefficient ϕ_cc(t) – AS 3600 Cl. 3.1.8.3")
        
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
- Sustained stress ratio: $\sigma_0/f'_{{c,mi}} = {stress_ratio:.2f}$  

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
        
        render_expandable_step(
            page_key="creep_coeff",
            step_id="creep_phi_cc_t",
            title="Creep coefficient at time t",
            summary_md=[
                rf"Result: $\varphi_{{cc}}(t) = {phi_cc_t:.2f}$ at $t = {t_creep:.0f}$ days",
                "Compute design creep coefficient from basic coefficient and factors"
            ],
            status_kind=None,
            calc_md=render_phi_cc_t(),
            info_render_fn=phi_cc_t_info_fn,
        )

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
        
        render_expandable_step(
            page_key="creep_coeff",
            step_id="creep_phi_cc_table",
            title="Long-term tabulated creep coefficient (30 years)",
            summary_md=[
                rf"Table value (30 years): $\varphi^*_{{cc,\text{{table}}}} = {phi_cc_star_table:.2f}$",
                "AS table provides long-term value for comparison"
            ],
            status_kind=None,
            calc_md=render_phi_cc_table(),
        )

    # ---------- Tab 3: Creep strain ----------
    with tab_strain:
        st.subheader("Creep strain ε_cc – AS 3600 Cl. 3.1.8.1")

        # Step 1: Sustained stress at loading σ₀
        def render_sigma0():
            return rf"""
**Summary**

| Quantity | Value |
|----------|-------|
| Stress ratio σ₀/f'c,mi | {stress_ratio:.2f} |
| Design strength f'c,mi ≈ f'c | {fc:.1f} MPa |
| **Sustained stress σ₀** | **{sigma0:.2f} MPa** |

**Purpose**

Convert sustained stress ratio into sustained compressive stress $\sigma_0$.

**Inputs**

- Stress ratio: $\sigma_0 / f'_{{c,mi}} = {stress_ratio:.2f}$
- Approximate design strength at loading: $f'_{{c,mi}} \approx f'_c = {fc:.1f}\,\text{{MPa}}$

**Calculation**

\[
\sigma_0 = \frac{{\sigma_0}}{{f'_{{c,mi}}}} \times f'_{{c,mi}}
\]

**Substitution**

\[
\sigma_0 = {stress_ratio:.2f} \times {fc:.1f} \approx {sigma0:.2f}\,\text{{MPa}}
\]

**Result**

\[
\sigma_0 = {sigma0:.2f}\,\text{{MPa}}
\]

_Ref: AS 3600:2018 Cl. 3.1.8.1._
"""
        
        def sigma0_info_fn():
            with info_i_button(help_text="Design strength at loading (f'c,mi)"):
                st.markdown(rf"""
**Design strength at loading ($f'_{{c,mi}}$):**

$f'_{{c,mi}}$ represents the concrete compressive strength at the time of loading. In this calculation, it is approximated as $f'_c$ (the 28-day design strength) for simplicity. This approximation is reasonable when loading occurs near 28 days or when precise loading age data is not available.

The sustained stress $\sigma_0$ is derived from the stress ratio and $f'_{{c,mi}}$ using: $\sigma_0 = (\sigma_0 / f'_{{c,mi}}) \times f'_{{c,mi}}$.

*Note: Compression is taken as positive magnitude in this calculation.*
""")
        
        render_expandable_step(
            page_key="creep_strain",
            step_id="creep_sigma0",
            title="Sustained stress at loading σ₀",
            summary_md=[
                rf"Result: $\sigma_0 = {sigma0:.2f}$ MPa",
                "Convert sustained stress ratio into sustained compressive stress"
            ],
            status_kind=None,
            calc_md=render_sigma0(),
            info_render_fn=sigma0_info_fn,
        )

        # Step 2: Creep strain ε_cc from creep coefficient
        def render_eps_cc():
            return rf"""
**Summary**

| Quantity | Value |
|----------|-------|
| Design creep coefficient φ_cc(t) | {phi_cc_t:.2f} |
| Sustained stress σ₀ | {sigma0:.2f} MPa |
| Modulus of elasticity E_c | {Ec:.0f} MPa |
| **Creep strain ε_cc** | **{eps_cc_micro:.1f} με** |

**Purpose**

Convert creep coefficient $\varphi_{{cc}}(t)$ to creep strain under sustained stress $\sigma_0$.

**Inputs**

- Design creep coefficient at time $t$:  
  \[
  \varphi_{{cc}}(t) \approx {phi_cc_t:.2f}
  \]
- Sustained stress: $\sigma_0 = {sigma0:.2f}\,\text{{MPa}}$ (from previous step)
- Modulus of elasticity: $E_c = {Ec:.0f}\,\text{{MPa}}$

**Calculation**

\[
\varepsilon_{{cc}} = \varphi_{{cc}}(t)\, \frac{{\sigma_0}}{{E_c}}
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
        
        render_expandable_step(
            page_key="creep_strain",
            step_id="creep_eps_cc",
            title="Creep strain ε_cc at time t",
            summary_md=[
                rf"Result: $\varepsilon_{{cc}} = {eps_cc_micro:.1f}$ με",
                "Convert creep coefficient to creep strain under sustained stress"
            ],
            status_kind=None,
            calc_md=render_eps_cc(),
        )
    
    # Handle pending scroll after all tabs have rendered (like bending/shrinkage)
    # This ensures all anchors exist before scrolling
    # Check all tab-specific pending scroll UIDs
    pending_scroll_uid = None
    for tab_key in ["creep_geom_pending_scroll_uid", "creep_coeff_pending_scroll_uid", "creep_strain_pending_scroll_uid"]:
        uid = st.session_state.get(tab_key)
        if uid:
            pending_scroll_uid = uid
            st.session_state[tab_key] = None
            break
    
    if pending_scroll_uid:
        st.session_state["jump_to"] = pending_scroll_uid
        scroll_to_jump_after_render()
    
    bind_summary_clicks()
