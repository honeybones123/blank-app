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
from widgets_helpers import apply_global_widget_css, number_row


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


def calcbox(md: str):
    r"""
    Render a highlighted calculation box with LaTeX-enabled markdown inside.

    - Converts \[ \] → $$ $$ for display math
    - Converts \( \) → $ $ for inline math
    - Wraps everything in a markdown blockquote (>) so CSS turns it blue
    """
    converted = md.replace("\\[", "$$").replace("\\]", "$$")
    converted = converted.replace("\\(", "$").replace("\\)", "$")
    lines = converted.strip().split("\n")
    blockquote = "\n".join("> " + line for line in lines)
    st.markdown(blockquote)


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
    # Reserve space for the top summary table
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

        b = st.number_input(
            "Section width b (mm)",
            value=b_seed,
            step=10.0,
            key="cr_b",
        )

        D = st.number_input(
            "Overall depth D (mm)",
            value=D_seed,
            step=10.0,
            key="cr_D",
        )

        faces_option = st.selectbox(
            "Member / faces exposed",
            [
                "Slab – one face exposed",
                "Slab – two faces exposed",
                "Beam – three faces exposed",
                "Column – four faces exposed",
            ],
            index=2,
            key="cr_faces",
        )

    # --- Environment & material ---
    with col_env:
        fc_seed = _seed_from_param("fc", 32.0)
        Ec_seed = _seed_from_param("Ec", 30000.0)

        fc = st.number_input(
            "Concrete strength f'c (MPa)",
            value=fc_seed,
            step=1.0,
            key="cr_fc",
        )

        Ec = st.number_input(
            "Concrete modulus Ec (MPa)",
            value=Ec_seed,
            step=1000.0,
            key="cr_Ec",
        )

        env_option = st.selectbox(
            "Creep environment (Tables 3.1.8.2 & 3.1.8.3)",
            [
                "Arid environment",
                "Interior environment",
                "Temperate inland environment",
                "Tropical / near-coastal / coastal environment",
            ],
            index=2,
            key="cr_env",
        )

    # --- Loading data ---
    with col_load:
        t_creep = st.number_input(
            "Time after loading t (days)",
            value=365.0,
            step=10.0,
            min_value=1.0,
            key="cr_t_creep",
        )

        age_at_loading = st.number_input(
            "Age at loading τ (days)",
            value=28.0,
            step=1.0,
            min_value=1.0,
            key="cr_tau",
        )

        stress_ratio = st.number_input(
            "Sustained stress ratio σ₀ / f'c,mi",
            value=0.30,
            step=0.05,
            min_value=0.0,
            max_value=0.80,
            key="cr_sigma_ratio",
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

    sigma0 = stress_ratio * fc  # MPa (approx using f'c,mi ≈ f'c)
    eps_cc = phi_cc_t * sigma0 / Ec  # dimensionless
    eps_cc_micro = eps_cc * 1e6

    # --------------------------------------------------------
    # TOP SUMMARY TABLE
    # --------------------------------------------------------
    with summary_placeholder.container():
        st.markdown("## Summary")

        rows = [
            {
                "Quantity": "Basic creep coefficient ϕ_cc,b",
                "Value": f"{phi_cc_b:.2f}",
                "Comment": "Table 3.1.8.2 – function of f'c",
            },
            {
                "Quantity": "Design creep coefficient ϕ_cc(t)",
                "Value": f"{phi_cc_t:.2f}",
                "Comment": "k₂k₃k₄k₅k₆ · ϕ_cc,b at time t",
            },
            {
                "Quantity": "Final creep coefficient ϕ*cc (30 years, table)",
                "Value": f"{phi_cc_star_table:.2f}",
                "Comment": "Table 3.1.8.3 – for check/comparison",
            },
            {
                "Quantity": "Creep strain ε_cc(t)",
                "Value": f"{eps_cc_micro:.1f} μɛ",
                "Comment": "ε_cc = ϕ_cc(t) σ₀ / Ec",
            },
        ]

        summary_df = pd.DataFrame(rows)

        def _highlight_strain(row):
            if "Creep strain" in str(row.get("Quantity", "")):
                return ["background-color: #d9ead3"] * len(row)  # light green
            return [""] * len(row)

        styled = summary_df.style.apply(_highlight_strain, axis=1)
        st.dataframe(styled, use_container_width=True, hide_index=True)
        st.markdown("---")

    # --------------------------------------------------------
    # Tabs: geometry, coefficient, strain, flow chart
    # --------------------------------------------------------
    tab_geom, tab_coeff, tab_strain, tab_flow = st.tabs(
        [
            "Geometry & tₕ",
            "Creep coefficient ϕ_cc(t)",
            "Creep strain ε_cc",
            "Flow chart / references",
        ]
    )

    # ---------- Tab 1: Geometry & t_h / k2 ----------
    with tab_geom:
        st.subheader("Notional thickness tₕ & k₂ – AS 3600 (2Aᵍ / uₑ, Fig. 3.1.8.3)")

        calcbox(
            rf"""
**Purpose**

Determine the **notional thickness** \(t_h\) and the **time-development factor** \(k_2\)
used in AS 3600 for **creep**.

**Inputs**

- Section width: \(b = {b:.1f}\,\text{{mm}}\)
- Overall depth: \(D = {D:.1f}\,\text{{mm}}\)
- Gross area: \(A_g = bD = {Ag:.0f}\,\text{{mm}}^2\)
- Faces exposed: **{faces_option}**
- Exposed perimeter: \(u_e = {ue:.1f}\,\text{{mm}}\)
- Time after loading: \(t = {t_creep:.0f}\,\text{{days}}\)

**Notional thickness**

\[
t_h = \frac{{2 A_g}}{{u_e}}
\]

With \(A_g = {Ag:.0f}\,\text{{mm}}^2\) and \(u_e = {ue:.1f}\,\text{{mm}}\):

\[
t_h \approx {th_raw:.1f}\,\text{{mm}}
\]

For compatibility with **Fig. 3.1.8.3** and **Table 3.1.8.3**, adopt the nearest
standard value:

\[
t_{{h,\text{{table}}}} = {th_table:d}\,\text{{mm}} \quad (\text{{nearest of 100, 200, 400 mm}})
\]

**Time-development factor** \(k_2\) (Fig. 3.1.8.3)

Creep development is modelled by

\[
k_2(t, t_h) = \frac{{\alpha_2 t^{0.8}}}{{t^{0.8} + 0.15 t_h}}, \qquad
\alpha_2 = 1.0 + 1.12\,e^{-0.008 t_h}
\]

At \(t = {t_creep:.0f}\) days and \(t_h = {th_table:d}\,\text{{mm}}\):

\[
k_2 \approx {k2:.3f}
\]

**Result**

- Adopted notional thickness: \(t_{{h,\text{{table}}}} = {th_table:d}\,\text{{mm}}\)  
- Time-development factor: \(k_2 \approx {k2:.3f}\)

_Ref: AS 3600:2018 Cl. 3.1.8.3 and Fig. 3.1.8.3._ 
"""
        )

    # ---------- Tab 2: Creep coefficient ----------
    with tab_coeff:
        st.subheader("Design creep coefficient ϕ_cc(t) – AS 3600 Cl. 3.1.8.3")

        calcbox(
            rf"""
**Purpose**

Compute the **design creep coefficient** at time \(t\):

\[
\varphi_{{cc}}(t) = k_2 k_3 k_4 k_5 k_6 \, \varphi_{{cc,b}}
\]

**Inputs**

- Concrete strength: \(f'_c = {fc:.1f}\,\text{{MPa}}\)  
- Environment: **{env_option}**  
- Age at loading: \(\tau = {age_at_loading:.0f}\,\text{{days}}\)  
- Time after loading: \(t = {t_creep:.0f}\,\text{{days}}\)  
- Notional thickness for tables: \(t_h = {th_table:d}\,\text{{mm}}\)  
- Sustained stress ratio: \(\sigma_0/f'_{{c,mi}} = {stress_ratio:.2f}\)  

**Basic creep coefficient** (Table 3.1.8.2)

\[
\varphi_{{cc,b}} \approx {phi_cc_b:.2f}
\]

**Factors**

- \(k_2(t, t_h) \approx {k2:.3f}\)  (Fig. 3.1.8.3)  
- \(k_3(\tau) = 2.7/[1 + \ln(\tau)] \approx {k3:.3f}\)  
- \(k_4\) (environment factor) \(= {k4:.2f}\)  
- \(k_5\) (high-strength modification) \(= {k5:.3f}\)  
- \(k_6\) (non-linear creep for high stress) \(= {k6:.3f}\)  

**Substitution**

\[
\varphi_{{cc}}(t)
= {k2:.3f} \times {k3:.3f} \times {k4:.2f} \times {k5:.3f} \times {k6:.3f}
\times {phi_cc_b:.2f}
\approx {phi_cc_t:.2f}
\]

**Comparison with Table 3.1.8.3**

For the same \(f'_c\), environment and \(t_h\), the **final 30-year coefficient**
from Table 3.1.8.3 is

\[
\varphi^*_{{cc,\text{{table}}}} \approx {phi_cc_star_table:.2f}
\]

**Result**

- Design creep coefficient at \(t = {t_creep:.0f}\) days:
  \[
  \varphi_{{cc}}(t) \approx {phi_cc_t:.2f}
  \]
- Tabulated long-term value (30 years):
  \[
  \varphi^*_{{cc,\text{{table}}}} \approx {phi_cc_star_table:.2f}
  \]

_Ref: AS 3600:2018 Cl. 3.1.8.3; Tables 3.1.8.2 & 3.1.8.3; Fig. 3.1.8.3._ 
"""
        )

    # ---------- Tab 3: Creep strain ----------
    with tab_strain:
        st.subheader("Creep strain ε_cc – AS 3600 Cl. 3.1.8.1")

        calcbox(
            rf"""
**Purpose**

Convert the **creep coefficient** to a **creep strain** under sustained
compressive stress \(\sigma_0\).

**Inputs**

- Design creep coefficient at time \(t\):  
  \[
  \varphi_{{cc}}(t) \approx {phi_cc_t:.2f}
  \]
- Sustained stress ratio:
  \[
  \frac{{\sigma_0}}{{f'_{{c,mi}}}} = {stress_ratio:.2f}
  \]
- Approximate design strength at loading: \(f'_{{c,mi}} \approx f'_c = {fc:.1f}\,\text{{MPa}}\)  
  so:
  \[
  \sigma_0 \approx {stress_ratio:.2f} \times {fc:.1f}
  \approx {sigma0:.2f}\,\text{{MPa}}
  \]
- Modulus of elasticity: \(E_c = {Ec:.0f}\,\text{{MPa}}\)

**Formula**

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
\varepsilon_{{cc}} \approx {eps_cc_micro:.1f}\times 10^{{-6}}
\]

**Result**

- Creep strain at \(t = {t_creep:.0f}\) days under \(\sigma_0 \approx {sigma0:.2f}\) MPa:  
  \[
  \varepsilon_{{cc}} \approx {eps_cc_micro:.1f}\,\mu\varepsilon
  \]

_Ref: AS 3600:2018 Cl. 3.1.8.1._ 
"""
        )

    # ---------- Tab 4: Flow chart / references ----------
    with tab_flow:
        st.subheader("Creep workflow – AS 3600:2018 Clause 3.1.8")

        st.markdown(
            """
### Step 1 – Geometry & notional thickness

- Choose section dimensions \(b, D\) and exposed faces → \(u_e\)  
- Compute gross area \(A_g = bD\) and notional thickness \(t_h = 2A_g/u_e\)  
- Snap \(t_h\) to **100, 200 or 400 mm** for use in Fig. 3.1.8.3 and Table 3.1.8.3.

---

### Step 2 – Material, environment & loading

- Select concrete strength \(f'_c\) and modulus \(E_c\)  
- Choose environment (arid / interior / temperate inland / tropical & coastal)  
- Choose age at loading \(\tau\) and time after loading \(t\)  
- Estimate sustained stress ratio \(\sigma_0 / f'_{c,mi}\).

---

### Step 3 – Creep coefficient

- Obtain \(\varphi_{cc,b}\) from Table 3.1.8.2  
- Compute \(k_2(t, t_h)\) from Fig. 3.1.8.3  
- Compute \(k_3(\tau)\), \(k_4\) (environment), \(k_5\) (high strength), \(k_6\) (stress level)  
- Evaluate \(\varphi_{cc}(t) = k_2 k_3 k_4 k_5 k_6 \varphi_{cc,b}\)  
- Optionally compare with \(\varphi^*_{cc}\) from Table 3.1.8.3.

---

### Step 4 – Creep strain

- Compute sustained stress \(\sigma_0\)  
- Evaluate creep strain \(\varepsilon_{cc} = \varphi_{cc}(t)\, \sigma_0 / E_c\)  
- Use \(\varepsilon_{cc}\) in **deflection** and other **serviceability** checks.
"""
        )
