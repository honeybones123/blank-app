# crack_page.py
# ============================
# CRACK WIDTH – AS 3600:2018 Cl. 8.6.2
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
#  Small helpers / shared styling (same pattern as creep/shrinkage)
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
#  Tables – AS 3600:2018 8.6.2.2(A) & (B)
# ------------------------------------------------------------
# TABLE 8.6.2.2(A) – Maximum steel stress for tension or flexure
# Structure: {db_mm: {wmax_mm: sigma_max_MPa}}
_TABLE_8_6_2_2A = {
    10: {0.2: 190, 0.3: 265, 0.4: 335},
    12: {0.2: 175, 0.3: 245, 0.4: 305},
    16: {0.2: 155, 0.3: 215, 0.4: 270},
    20: {0.2: 140, 0.3: 195, 0.4: 240},
    24: {0.2: 125, 0.3: 175, 0.4: 215},
    28: {0.2: 115, 0.3: 160, 0.4: 200},
    32: {0.2: 105, 0.3: 150, 0.4: 185},
    36: {0.2: 100, 0.3: 140, 0.4: 175},
    40: {0.2: 90,  0.3: 130, 0.4: 165},
}

# TABLE 8.6.2.2(B) – Maximum steel stress for flexure vs spacing
# Structure: {spacing_mm: {wmax_mm: sigma_max_MPa}}
_TABLE_8_6_2_2B = {
    50:  {0.2: 200, 0.3: 300, 0.4: 400},
    100: {0.2: 170, 0.3: 270, 0.4: 360},
    150: {0.2: 155, 0.3: 245, 0.4: 330},
    200: {0.2: 145, 0.3: 225, 0.4: 300},
    250: {0.2: 135, 0.3: 210, 0.4: 280},
    300: {0.2: 125, 0.3: 200, 0.4: 260},
}


def _nearest_key(mapping: dict, value: float) -> int:
    """Return integer key in mapping closest to value."""
    keys = sorted(mapping.keys())
    return min(keys, key=lambda k: abs(k - value))


def table_sigma_max_A(db_mm: float, wmax_mm: float) -> float:
    """Lookup σ_s,max from Table 8.6.2.2(A) (nearest db, w'max)."""
    wopt = min([0.2, 0.3, 0.4], key=lambda x: abs(x - wmax_mm))
    db_key = _nearest_key(_TABLE_8_6_2_2A, db_mm)
    return _TABLE_8_6_2_2A[db_key][wopt]


def table_sigma_max_B(spacing_mm: float, wmax_mm: float) -> float:
    """Lookup σ_s,max from Table 8.6.2.2(B) (nearest spacing, w'max)."""
    wopt = min([0.2, 0.3, 0.4], key=lambda x: abs(x - wmax_mm))
    s_key = _nearest_key(_TABLE_8_6_2_2B, spacing_mm)
    return _TABLE_8_6_2_2B[s_key][wopt]


# ------------------------------------------------------------
#  Direct calculation helpers – 8.6.2.3
# ------------------------------------------------------------
def calc_eps_diff(
    sigma_sr: float,
    Es: float,
    fct_eff: float,
    rho_eff: float,
    ne: float,
    eps_cs: float,
) -> float:
    """
    ε_sm − ε_cm from 8.6.2.3(2):

      ε_sm − ε_cm = σ_sr / Es − 0.6 f_ct,eff / (Es ρ_eff) (1 + n_e ρ_eff) + ε_cs
                  ≥ 0.6 σ_sr / Es

    All strains are dimensionless.
    """
    if rho_eff <= 0:
        return 0.0

    term1 = sigma_sr / Es
    term2 = 0.6 * fct_eff / (Es * rho_eff) * (1.0 + ne * rho_eff)
    eps_diff = term1 - term2 + eps_cs

    # Lower bound 0.6 σ_sr / Es
    eps_min = 0.6 * sigma_sr / Es
    return max(eps_diff, eps_min)


def calc_sr_max(c_mm: float, db_mm: float, rho_eff: float, k1: float, k2: float) -> float:
    """
    Maximum crack spacing  s_r,max  from 8.6.2.3(3):

        s_r,max = 3.4 c + 0.3 k1 k2 d_b / ρ_eff

    Returns s_r,max in mm.
    """
    if rho_eff <= 0:
        return 0.0
    return 3.4 * c_mm + 0.3 * k1 * k2 * db_mm / rho_eff


# ------------------------------------------------------------
#  MAIN RENDER FUNCTION
# ------------------------------------------------------------
def render_crack():
    apply_global_widget_css()
    _inject_calcbox_css()
    get_sync_callbacks()  # keeps contract with Inputs page

    # --------------------------------------------------------
    # Page title
    # --------------------------------------------------------
    st.title("Crack width – AS 3600:2018 Clause 8.6.2")

    # --------------------------------------------------------
    # Page description (directly under title)
    # --------------------------------------------------------
    st.markdown(
        r"""
This page checks **flexural crack control in reinforced concrete beams** in accordance with  
**AS 3600:2018 Clause 8.6.2**, using:

- **Table method (no direct crack width)** — limiting steel stress from Tables 8.6.2.2(A)–(B)  
- **Direct crack-width calculation** — \(w = s_{r,\max} (\varepsilon_{sm} - \varepsilon_{cm}) \le w'_{\max}\) per Cl. 8.6.2.3  

The aim is to verify that cracking is **controlled** so that durability and appearance are not impaired.
"""
    )

    # --------------------------------------------------------
    # Reserve space for top summary
    # --------------------------------------------------------
    summary_placeholder = st.empty()

    # --------------------------------------------------------
    # Inputs – geometry, reinforcement, material, crack limit
    # --------------------------------------------------------
    st.markdown("### Inputs")

    col_geom, col_reo, col_mat, col_crack = st.columns(4)

    with col_geom:
        b_seed = _seed_from_param("b", 300.0)
        D_seed = _seed_from_param("D", 600.0)
        cover_seed = _seed_from_param("cover_bot", 40.0)

        b = st.number_input(
            "Section width b (mm)",
            value=b_seed,
            step=10.0,
            key="crk_b",
        )
        D = st.number_input(
            "Overall depth D (mm)",
            value=D_seed,
            step=10.0,
            key="crk_D",
        )
        c = st.number_input(
            "Clear cover to tensile bars c (mm)",
            value=cover_seed,
            step=5.0,
            key="crk_c",
        )

    with col_reo:
        db = st.number_input(
            "Nominal bar diameter d_b (mm)",
            value=20.0,
            step=2.0,
            min_value=8.0,
            key="crk_db",
        )
        spacing = st.number_input(
            "Centre-to-centre spacing s (mm)",
            value=200.0,
            step=25.0,
            min_value=25.0,
            key="crk_spacing",
        )
        Ast_seed = _seed_from_param("Ast_bot", 3 * math.pi * 20.0**2 / 4.0)
        Ast = st.number_input(
            "Area of tensile steel A_s,t (mm²)",
            value=float(Ast_seed),
            step=50.0,
            min_value=1.0,
            key="crk_Ast",
        )

    with col_mat:
        fc_seed = _seed_from_param("fc", 32.0)
        Ec_seed = _seed_from_param("Ec", 30000.0)

        fc = st.number_input(
            "Concrete strength f'c (MPa)",
            value=fc_seed,
            step=1.0,
            key="crk_fc",
        )
        Ec = st.number_input(
            "Concrete modulus Ec (MPa)",
            value=Ec_seed,
            step=1000.0,
            key="crk_Ec",
        )
        Es = st.number_input(
            "Steel modulus Es (MPa)",
            value=200000.0,
            step=10000.0,
            key="crk_Es",
        )

    with col_crack:
        wmax_choice = st.selectbox(
            "Characteristic crack width limit w'ₘₐₓ (mm)",
            options=[0.2, 0.3, 0.4],
            index=1,
            format_func=lambda x: f"{x:.1f} mm",
            key="crk_wmax",
        )
        member_type = st.selectbox(
            "Resultant action",
            options=["Primarily flexure", "Primarily tension"],
            index=0,
            key="crk_member_type",
        )
        sigma_sr = st.number_input(
            "Steel stress at SLS σ_sr (MPa)",
            value=200.0,
            step=10.0,
            min_value=0.0,
            key="crk_sigma_sr",
        )

    # Effective area in tension (very simplified) and ρ_eff
    d_eff = D - c - db / 2.0
    # Very simple Aceff: use 2.5c × (D − d) but not more than D/2, per definition idea
    height_eff = min(2.5 * c, max(D - d_eff, 0.0), D / 2.0)
    Aceff = b * max(height_eff, 1.0)  # mm²
    rho_eff = Ast / Aceff

    # --------------------------------------------------------
    # 8.6.2.2 – Table-based max steel stress
    # --------------------------------------------------------
    # Table A limit (always applies)
    sigma_table_A = table_sigma_max_A(db, wmax_choice)

    # Table B limit (only for primarily flexure)
    sigma_table_B = table_sigma_max_B(spacing, wmax_choice)

    if member_type == "Primarily tension":
        sigma_table_combined = sigma_table_A
        table_basis = "Table 8.6.2.2(A) – bar diameter"
    else:
        sigma_table_combined = max(sigma_table_A, sigma_table_B)
        table_basis = (
            "Max of Table 8.6.2.2(A) (bar diameter) "
            "and 8.6.2.2(B) (spacing)"
        )

    # 0.8 fsy cap (user will normally choose σ_sr not exceeding this)
    fsy_seed = _seed_from_param("fsy", 500.0)
    fsy = fsy_seed
    sigma_08fsy = 0.8 * fsy

    sigma_allow_table = min(sigma_table_combined, sigma_08fsy)
    utilisation_table = sigma_sr / sigma_allow_table if sigma_allow_table > 0 else 0.0
    passes_table = utilisation_table <= 1.0

    # --------------------------------------------------------
    # 8.6.2.3 – Direct crack width calculation
    # --------------------------------------------------------
    # Effective mean axial tensile strength – allow user override
    fct_default = 0.6 * math.sqrt(max(fc, 1.0))
    fct_eff = st.number_input(
        "Effective mean tensile strength f_ct,eff (MPa)",
        value=float(fct_default),
        step=0.1,
        min_value=0.1,
        key="crk_fct_eff",
    )

    phi_ce = st.number_input(
        "Creep coefficient φ_ce (for crack interval)",
        value=2.0,
        step=0.1,
        min_value=0.0,
        key="crk_phi_ce",
    )

    eps_cs_micro = st.number_input(
        "Final long-term shrinkage strain ε_cs (microstrain)",
        value=300.0,
        step=10.0,
        min_value=0.0,
        key="crk_eps_cs_micro",
    )
    eps_cs = eps_cs_micro * 1e-6

    k1_choice = st.selectbox(
        "k₁ (bond coefficient)",
        options=[
            ("Deformed bars (k₁ = 0.8)", 0.8),
            ("Plain bars (k₁ = 1.6)", 1.6),
        ],
        index=0,
        key="crk_k1",
    )
    k1 = k1_choice[1]

    if member_type == "Primarily flexure":
        k2_default = 0.5
    else:
        k2_default = 1.0

    k2 = st.number_input(
        "k₂ (strain distribution factor)",
        value=float(k2_default),
        step=0.1,
        min_value=0.3,
        max_value=1.5,
        key="crk_k2",
    )

    # Modular ratio for effective stiffness
    ne = (1.0 + phi_ce) * Es / Ec if Ec > 0 else 0.0

    eps_diff = calc_eps_diff(
        sigma_sr=sigma_sr,
        Es=Es,
        fct_eff=fct_eff,
        rho_eff=rho_eff,
        ne=ne,
        eps_cs=eps_cs,
    )

    sr_max = calc_sr_max(c_mm=c, db_mm=db, rho_eff=rho_eff, k1=k1, k2=k2)
    w_calc = sr_max * eps_diff  # mm (since sr_max in mm and strain is unitless)
    utilisation_w = w_calc / wmax_choice if wmax_choice > 0 else 0.0
    passes_w = utilisation_w <= 1.0

    # --------------------------------------------------------
    # TOP SUMMARY TABLE
    # --------------------------------------------------------
    with summary_placeholder.container():
        st.markdown("## Summary")

        rows = [
            {
                "Check": "Table method – max steel stress σ_sr",
                "Result": f"{sigma_sr:.1f} MPa",
                "Limit": f"{sigma_allow_table:.1f} MPa",
                "Utilisation": f"{utilisation_table:.2f}",
                "Pass?": "PASS" if passes_table else "FAIL",
            },
            {
                "Check": "Direct crack width w",
                "Result": f"{w_calc:.3f} mm",
                "Limit": f"{wmax_choice:.3f} mm",
                "Utilisation": f"{utilisation_w:.2f}",
                "Pass?": "PASS" if passes_w else "FAIL",
            },
        ]

        summary_df = pd.DataFrame(rows)

        def _highlight(row):
            color = "#d9ead3" if "PASS" in row.get("Pass?", "") else "#f4cccc"
            return [f"background-color: {color}"] * len(row)

        styled = summary_df.style.apply(_highlight, axis=1)
        st.dataframe(styled, use_container_width=True, hide_index=True)
        st.markdown("---")

    # --------------------------------------------------------
    # Tabs: table method & direct calculation
    # --------------------------------------------------------
    tab_table, tab_calc, tab_flow = st.tabs(
        [
            "Table method (8.6.2.2)",
            "Direct calculation (8.6.2.3)",
            "Workflow / notes",
        ]
    )

    # ---------- Tab 1: Table method ----------
    with tab_table:
        st.subheader("Crack control **without** direct calculation of crack widths – Cl. 8.6.2.2")

        calcbox(
            rf"""
**Concept**

Instead of calculating a crack width directly, Clause 8.6.2.2 limits the **steel stress**
on the cracked section:

- For members **primarily in tension**:  
  \[
  \sigma_{{sr}} \le \sigma_{{\text{{max,A}}}} \quad \text{{(Table 8.6.2.2(A))}}
  \]
- For members **primarily in flexure**:  
  \[
  \sigma_{{sr}} \le \max\left(\sigma_{{\text{{max,A}}}}, \sigma_{{\text{{max,B}}}}\right)
  \]
  where \(\sigma_{{\text{{max,B}}}}\) comes from **Table 8.6.2.2(B)**.

Under direct loading, \(\sigma_{{sr,1}} \le 0.8 f_{{sy}}\).

**Current input**

- Bar diameter: \(d_b = {db:.1f}\,\text{{mm}}\)  
- Spacing: \(s = {spacing:.0f}\,\text{{mm}}\)  
- Crack width limit: \(w'_{{\max}} = {wmax_choice:.1f}\,\text{{mm}}\)  
- SLS steel stress: \(\sigma_{{sr}} = {sigma_sr:.1f}\,\text{{MPa}}\)  
- Yield strength: \(f_{{sy}} \approx {fsy:.0f}\,\text{{MPa}}\)

**From tables**

- Table 8.6.2.2(A): \(\sigma_{{\text{{max,A}}}} \approx {sigma_table_A:.1f}\,\text{{MPa}}\)  
- Table 8.6.2.2(B): \(\sigma_{{\text{{max,B}}}} \approx {sigma_table_B:.1f}\,\text{{MPa}}\)  
- Combined table limit ({table_basis}):  
  \[
  \sigma_{{\text{{table}}}} = {sigma_table_combined:.1f}\,\text{{MPa}}
  \]
- 0.8\(f_{{sy}}\) limit:
  \[
  0.8 f_{{sy}} \approx {sigma_08fsy:.1f}\,\text{{MPa}}
  \]

Overall allowable steel stress:

\[
\sigma_{{\text{{allow}}}} = \min\left(\sigma_{{\text{{table}}}},\,0.8 f_{{sy}}\right)
= {sigma_allow_table:.1f}\,\text{{MPa}}
\]

**Check**

\[
\frac{{\sigma_{{sr}}}}{{\sigma_{{\text{{allow}}}}}}
= \frac{{{sigma_sr:.1f}}}{{{sigma_allow_table:.1f}}}
\approx {utilisation_table:.2f}
\quad\Rightarrow\quad
\text{{{"PASS" if passes_table else "FAIL"}}}
\]
"""
        )

    # ---------- Tab 2: Direct calculation ----------
    with tab_calc:
        st.subheader("Crack control **by calculation of crack widths** – Cl. 8.6.2.3")

        calcbox(
            rf"""
**Concept**

The calculated maximum crack width is:

\[
w = s_{{r,\max}}(\varepsilon_{{sm}} - \varepsilon_{{cm}}) \le w'_{{\max}}
\]

where:

- \(s_{{r,\max}}\) = maximum crack spacing  
- \(\varepsilon_{{sm}}\) = mean strain in reinforcement  
- \(\varepsilon_{{cm}}\) = mean strain in concrete between cracks.

**Step 1 – Effective reinforcement ratio**

Effective area in tension (simplified):

\[
A_{{c,\text{{eff}}}} \approx b \, h_{{\text{{eff}}}}
\quad\Rightarrow\quad
A_{{c,\text{{eff}}}} \approx {Aceff:.0f}\,\text{{mm}}^2
\]

\[
\rho_{{\text{{eff}}}} = \frac{{A_{{s,t}}}}{{A_{{c,\text{{eff}}}}}}
= \frac{{{Ast:.0f}}}{{{Aceff:.0f}}}
\approx {rho_eff:.4f}
\]

**Step 2 – Difference in mean strain** \(\varepsilon_{{sm}} - \varepsilon_{{cm}}\)

From Cl. 8.6.2.3(2):

\[
\varepsilon_{{sm}} - \varepsilon_{{cm}}
= \frac{{\sigma_{{sr}}}}{{E_s}}
- \frac{{0.6 f_{{ct,\text{{eff}}}}}}{{E_s \rho_{{\text{{eff}}}}}}\left(1 + n_e \rho_{{\text{{eff}}}}\right)
+ \varepsilon_{{cs}}
\ge 0.6 \frac{{\sigma_{{sr}}}}{{E_s}}
\]

With:

- \(f_{{ct,\text{{eff}}}} = {fct_eff:.2f}\,\text{{MPa}}\)  
- \(E_s = {Es:.0f}\,\text{{MPa}},\ E_c = {Ec:.0f}\,\text{{MPa}}\)  
- \(\varphi_{{ce}} = {phi_ce:.2f}\)  
- \(n_e = (1 + \varphi_{{ce}}) E_s/E_c \approx {ne:.2f}\)  
- \(\varepsilon_{{cs}} \approx {eps_cs_micro:.1f}\times 10^{{-6}}\)

This gives:

\[
\varepsilon_{{sm}} - \varepsilon_{{cm}} \approx {eps_diff:.3e}
\]

**Step 3 – Maximum crack spacing**

\[
s_{{r,\max}} = 3.4 c + 0.3 k_1 k_2 \frac{{d_b}}{{\rho_{{\text{{eff}}}}}}
\]

Using:

- \(c = {c:.1f}\,\text{{mm}},\ d_b = {db:.1f}\,\text{{mm}}\)  
- \(k_1 = {k1:.2f},\ k_2 = {k2:.2f}\)

\[
s_{{r,\max}} \approx {sr_max:.1f}\,\text{{mm}}
\]

**Step 4 – Crack width**

\[
w = s_{{r,\max}}(\varepsilon_{{sm}} - \varepsilon_{{cm}})
\approx {sr_max:.1f} \times {eps_diff:.3e}
\approx {w_calc:.3f}\,\text{{mm}}
\]

Limit:

\[
w'_{{\max}} = {wmax_choice:.1f}\,\text{{mm}}, \quad
\frac{{w}}{{w'_{{\max}}}} \approx {utilisation_w:.2f}
\Rightarrow\ \text{{{"PASS" if passes_w else "FAIL"}}}
\]
"""
        )

    # ---------- Tab 3: Workflow ----------
    with tab_flow:
        st.subheader("Crack control workflow – AS 3600:2018 Clause 8.6.2")

        st.markdown(
            """
### Step 1 – Minimum reinforcement & detailing

- Check minimum tensile reinforcement per Clause 8.1.6.1  
- Check cover and spacing requirements (≤ 100 mm to nearest bar, ≤ 300 mm spacing, etc.).

---

### Step 2 – Choose crack-control approach

- **Table method (8.6.2.2)** for most beams – simple steel-stress limit.  
- **Direct crack-width calculation (8.6.2.3)** where a more refined check is needed.

---

### Step 3 – Table method

- Determine largest bar diameter and spacing in the tension zone.  
- Choose characteristic crack-width limit \(w'_{\max}\) for the surface.  
- Read off \(\sigma_{\text{max}}\) from Tables 8.6.2.2(A)–(B).  
- Ensure \(\sigma_{sr} \le \min(\sigma_{\text{max}}, 0.8 f_{sy})\).

---

### Step 4 – Direct calculation (if used)

- Compute effective reinforcement ratio \(\rho_{\text{eff}}\).  
- Determine \(k_1, k_2\) based on bond and strain distribution.  
- Obtain \(f_{ct,\text{eff}}, \varphi_{ce}, \varepsilon_{cs}\) (can be linked to your shrinkage/creep pages).  
- Evaluate \(s_{r,\max}\), \(\varepsilon_{sm} - \varepsilon_{cm}\) and \(w\).  
- Check \(w \le w'_{\max}\).

---

This page is intentionally **teaching-focused**: every step is exposed so students can
see how the tables and equations in Clause 8.6.2 relate to each other.
"""
        )


# For compatibility with whatever app.py calls
def render_crack_control():
    """Entry point used by app.py – delegates to render_crack()."""
    render_crack()


# Optional alias if imported elsewhere
def render_crack_page():
    render_crack()
