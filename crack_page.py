# crack_page.py
# ============================
# CRACK WIDTH – AS 3600:2018 Cl. 8.6
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
#  Small helpers / shared styling (same pattern as shrinkage/creep)
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
    """
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
#  Tables – AS 3600:2018 8.6.2.2(A) & 8.6.2.2(B)
# ------------------------------------------------------------
# Table 8.6.2.2(A) – Maximum steel stress for tension or flexure (by bar diameter)
# Structure: {db_mm: {w_lim_mm: sigma_s_max_MPa}}
_CRACK_TABLE_DB = {
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

# Table 8.6.2.2(B) – Maximum steel stress for flexure (by bar spacing)
# Structure: {spacing_mm: {w_lim_mm: sigma_s_max_MPa}}
_CRACK_TABLE_SPACING = {
    50:  {0.2: 200, 0.3: 300, 0.4: 400},
    100: {0.2: 170, 0.3: 270, 0.4: 360},
    150: {0.2: 155, 0.3: 245, 0.4: 330},
    200: {0.2: 145, 0.3: 225, 0.4: 300},
    250: {0.2: 135, 0.3: 210, 0.4: 280},
    300: {0.2: 125, 0.3: 200, 0.4: 260},
}


def _closest_key(value: float, table: dict) -> int:
    keys = sorted(table.keys())
    return min(keys, key=lambda k: abs(value - k))


def sigma_limit_from_tables(
    db_mm: float,
    spacing_mm: float,
    w_lim_mm: float,
    fsy: float,
    primary_action: str,
) -> float:
    """
    Return allowable steel stress σ_s,lim from 8.6.2.2 for given bar size, spacing and w'_max.

    - For 'Tension' → Table 8.6.2.2(A) only
    - For 'Flexure' → larger of Table 8.6.2.2(A) and 8.6.2.2(B)
    - Always limited to 0.8 f_sy
    """
    db_key = _closest_key(db_mm, _CRACK_TABLE_DB)
    s_key = _closest_key(spacing_mm, _CRACK_TABLE_SPACING)

    sigma_A = _CRACK_TABLE_DB[db_key][w_lim_mm]

    if primary_action == "Flexure":
        sigma_B = _CRACK_TABLE_SPACING[s_key][w_lim_mm]
        sigma_tables = max(sigma_A, sigma_B)
    else:  # "Tension"
        sigma_tables = sigma_A

    sigma_08fsy = 0.8 * fsy
    return min(sigma_tables, sigma_08fsy)


# ------------------------------------------------------------
#  Functions for calculated crack width – Cl. 8.6.2.3
# ------------------------------------------------------------
def effective_concrete_area(
    b_mm: float,
    D_mm: float,
    d_mm: float,
    kd_mm: float,
) -> float:
    """
    Effective tension area A_c,eff (mm²) around longitudinal bars per Cl. 8.6.2.3:

        h_c,eff = min( 2.5(D - d), (D - k_d)/3, D/2 )
        A_c,eff = b * h_c,eff
    """
    h1 = 2.5 * (D_mm - d_mm)
    h2 = (D_mm - kd_mm) / 3.0
    h3 = 0.5 * D_mm
    h_ceff = max(0.0, min(h1, h2, h3))
    return b_mm * h_ceff


def max_crack_spacing(
    c_mm: float,
    db_mm: float,
    rho_eff: float,
    k1: float,
    k2: float,
) -> float:
    """
    Maximum final crack spacing s_r,max (mm) for bars at 'reasonably close centres':

        s_r,max = 3.4 c + 0.3 k1 k2 d_b / ρ_eff
    """
    if rho_eff <= 0:
        return float("nan")
    return 3.4 * c_mm + 0.3 * k1 * k2 * db_mm / rho_eff


def strain_difference(
    sigma_sr: float,
    f_ct: float,
    rho_eff: float,
    eps_cs: float,
    phi_cc: float,
    Ec: float,
    Es: float = 200000.0,
) -> float:
    """
    ε_sm - ε_cm from 8.6.2.3(2):

        ε_sm - ε_cm = σ_sr / E_s
                      - 0.6 f_ct / (E_s ρ_eff) (1 + n_eff ρ_eff)
                      + ε_cs  ≥  0.6 σ_sr / E_s

    where n_eff = (1 + φ_cc) E_s / E_c.
    All strains returned as dimensionless (not microstrain).
    """
    if rho_eff <= 0 or Ec <= 0 or Es <= 0:
        return float("nan")

    n_eff = (1.0 + phi_cc) * Es / Ec
    term1 = sigma_sr / Es
    term2 = 0.6 * f_ct / (Es * rho_eff) * (1.0 + n_eff * rho_eff)
    raw = term1 - term2 + eps_cs

    # Enforce lower bound 0.6 σ_sr / Es
    lower = 0.6 * sigma_sr / Es
    return max(raw, lower)


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
    st.title("Crack control – AS 3600:2018 Clause 8.6")

    # --------------------------------------------------------
    # Page description (directly under title)
    # --------------------------------------------------------
    st.markdown(
        r"""
This page implements **crack control of reinforced concrete beams** in accordance with  
**AS 3600:2018 Clause 8.6**, including:

- **Table-based crack control** without direct crack-width calculation (Cl. 8.6.2.2; Tables 8.6.2.2(A),(B))  
- **Calculated crack width** for tension/flexure in reinforced beams (Cl. 8.6.2.3)  
- Comparison of **design steel stress** and **crack width** against a selected limit \(w'_{\max}\)

Crack widths are in millimetres; crack strains are reported in microstrain (\(\times 10^{-6}\)).
"""
    )

    # --------------------------------------------------------
    # Reserve space for summary table
    # --------------------------------------------------------
    summary_placeholder = st.empty()

    # --------------------------------------------------------
    # Inputs
    # --------------------------------------------------------
    st.markdown("### Key inputs")

    col_geom, col_steel, col_service = st.columns(3)

    # --- Geometry / reinforcement for calculated method ---
    with col_geom:
        b_seed = _seed_from_param("b", 300.0)
        D_seed = _seed_from_param("D", 600.0)
        d_seed = _seed_from_param("d", 550.0)

        b = st.number_input("Section width b (mm)", value=b_seed, step=10.0, key="crk_b")
        D = st.number_input("Overall depth D (mm)", value=D_seed, step=10.0, key="crk_D")
        d = st.number_input("Effective depth d (mm)", value=d_seed, step=10.0, key="crk_d")

        kd = st.number_input(
            "Neutral axis depth k_d (mm)",
            value=0.4 * D_seed,
            step=10.0,
            min_value=1.0,
            key="crk_kd",
        )

        c = st.number_input(
            "Clear cover to longitudinal bars c (mm)",
            value=40.0,
            step=5.0,
            min_value=5.0,
            key="crk_cover",
        )

        Ast_eff = st.number_input(
            "Area of tension steel crossing cracks A_st,eff (mm² per metre width)",
            value=2000.0,
            step=100.0,
            min_value=1.0,
            key="crk_Ast_eff",
        )

    # --- Steel / exposure / table-based check ---
    with col_steel:
        fsy_seed = _seed_from_param("fsy", 500.0)

        fsy = st.number_input(
            "Steel yield strength fsy (MPa)",
            value=fsy_seed,
            step=10.0,
            min_value=100.0,
            key="crk_fsy",
        )

        db = st.number_input(
            "Largest bar diameter d_b (mm)",
            value=20.0,
            step=2.0,
            min_value=8.0,
            key="crk_db",
        )

        spacing = st.number_input(
            "Centre-to-centre spacing of tensile bars s (mm)",
            value=200.0,
            step=25.0,
            min_value=25.0,
            key="crk_spacing",
        )

        primary_action = st.selectbox(
            "Primary action for crack control",
            ["Flexure", "Tension"],
            index=0,
            key="crk_action",
        )

        w_lim = st.selectbox(
            "Selected characteristic max crack width w'max (mm)",
            [0.2, 0.3, 0.4],
            index=1,
            key="crk_w_lim",
        )

    # --- Service loads / strains for calculated method ---
    with col_service:
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
            step=5000.0,
            key="crk_Es",
        )

        sigma_s = st.number_input(
            "Calculated tensile steel stress σ_sr (MPa) at SLS",
            value=200.0,
            step=10.0,
            min_value=0.0,
            key="crk_sigma_sr",
        )

        f_ct = st.number_input(
            "Mean axial tensile strength f_ct (MPa) at cracking",
            value=2.6,
            step=0.1,
            min_value=0.1,
            key="crk_fct",
        )

        phi_cc = st.number_input(
            "Creep coefficient φ_cc (long-term at cracking)",
            value=2.0,
            step=0.1,
            min_value=0.0,
            key="crk_phi_cc",
        )

        eps_cs_micro = st.number_input(
            "Final shrinkage strain ε_cs (microstrain, +ve in tension)",
            value=600.0,
            step=50.0,
            min_value=0.0,
            key="crk_eps_cs_micro",
        )

        # k1 & k2 for crack spacing – user controlled
        k1 = st.selectbox(
            "k₁ – bond factor",
            options=[
                "0.8 (deformed bars – default)",
                "1.6 (plain / poor bond)",
            ],
            index=0,
            key="crk_k1_choice",
        )
        k1_val = 0.8 if "0.8" in k1 else 1.6

        k2_val = st.number_input(
            "k₂ – strain distribution factor (≈0.5 bending, 1.0 tension)",
            value=0.5,
            step=0.1,
            min_value=0.3,
            max_value=1.0,
            key="crk_k2",
        )

    # --------------------------------------------------------
    #  Derived quantities for calculated method
    # --------------------------------------------------------
    A_ceff = effective_concrete_area(b, D, d, kd)
    rho_eff = Ast_eff / A_ceff if A_ceff > 0 else float("nan")
    eps_cs = eps_cs_micro * 1e-6

    s_r_max = max_crack_spacing(c, db, rho_eff, k1_val, k2_val)
    eps_diff = strain_difference(
        sigma_sr=sigma_s,
        f_ct=f_ct,
        rho_eff=rho_eff,
        eps_cs=eps_cs,
        phi_cc=phi_cc,
        Ec=Ec,
        Es=Es,
    )

    w_calc = s_r_max * eps_diff if (
        not math.isnan(s_r_max) and not math.isnan(eps_diff)
    ) else float("nan")

    # --------------------------------------------------------
    #  Table-based allowable stress
    # --------------------------------------------------------
    sigma_allow_tables = sigma_limit_from_tables(
        db_mm=db,
        spacing_mm=spacing,
        w_lim_mm=w_lim,
        fsy=fsy,
        primary_action=primary_action,
    )

    table_ok = sigma_s <= sigma_allow_tables
    calc_ok = (not math.isnan(w_calc)) and (w_calc <= w_lim)

    # --------------------------------------------------------
    #  SUMMARY TABLE
    # --------------------------------------------------------
    with summary_placeholder.container():
        st.markdown("## Summary")

        rows = [
            {
                "Check": "Table-based steel stress limit (8.6.2.2)",
                "Result": f"σ_sr = {sigma_s:.1f} MPa",
                "Limit": f"σ_lim = {sigma_allow_tables:.1f} MPa",
                "Pass?": "PASS ✅" if table_ok else "FAIL ❌",
            },
            {
                "Check": "Calculated crack width (8.6.2.3)",
                "Result": f"w_calc = {w_calc:.3f} mm" if not math.isnan(w_calc) else "w_calc = —",
                "Limit": f"w'max = {w_lim:.3f} mm",
                "Pass?": "PASS ✅" if calc_ok else ("FAIL ❌" if not math.isnan(w_calc) else "N/A"),
            },
        ]

        summary_df = pd.DataFrame(rows)
        st.dataframe(summary_df, use_container_width=True, hide_index=True)
        st.markdown("---")

    # --------------------------------------------------------
    #  Tabs – table-based method, calculated method, workflow
    # --------------------------------------------------------
    tab_table, tab_calc, tab_flow = st.tabs(
        [
            "Table-based check (8.6.2.2)",
            "Calculated crack width (8.6.2.3)",
            "Workflow / notes",
        ]
    )

    # ---------- Tab 1: Table-based crack control ----------
    with tab_table:
        st.subheader("Crack control without direct calculation – Cl. 8.6.2.2")

        calcbox(
            rf"""
**Purpose**

Check crack control by limiting the **tensile steel stress** on the cracked section,
without explicitly calculating crack widths.

**Inputs**

- Primary action: **{primary_action}**  
- Largest bar diameter in tensile zone: $d_b = {db:.1f}\,\text{{mm}}$  
- Centre-to-centre spacing of bars: $s = {spacing:.1f}\,\text{{mm}}$  
- Selected characteristic max crack width: $w'_{{\max}} = {w_lim:.3f}\,\text{{mm}}$  
- Steel yield strength: $f_{{sy}} = {fsy:.1f}\,\text{{MPa}}$  
- Calculated tensile steel stress at SLS: $\sigma_{{sr}} = {sigma_s:.1f}\,\text{{MPa}}$

**Steel stress limits**

From **Table 8.6.2.2(A)** (by diameter):

\[
\sigma_{{\text{{lim,A}}}} \approx {_CRACK_TABLE_DB[_closest_key(db, _CRACK_TABLE_DB)][w_lim]:.0f}\,\text{{MPa}}
\]

For **flexure** (Cl. 8.6.2.2(b)), the limit is the larger of  
Table 8.6.2.2(A) and **Table 8.6.2.2(B)** (by spacing).  
For **tension** (Cl. 8.6.2.2(a)), only Table 8.6.2.2(A) applies.

The table-based limit is therefore:

\[
\sigma_{{\text{{tables}}}} =
\begin{cases}
\sigma_{{\text{{lim,A}}}}, & \text{{tension}} \\
\max\bigl(\sigma_{{\text{{lim,A}}}}, \sigma_{{\text{{lim,B}}}}\bigr), & \text{{flexure}}
\end{cases}
\]

Additionally, under direct loading:

\[
\sigma_{{sr,1}} \le 0.8 f_{{sy}} = 0.8 \times {fsy:.1f}
= {0.8*fsy:.1f}\,\text{{MPa}}
\]

So the **design limit** is:

\[
\sigma_{{\text{{lim}}}}
= \min\bigl(\sigma_{{\text{{tables}}}}, 0.8 f_{{sy}}\bigr)
\approx {sigma_allow_tables:.1f}\,\text{{MPa}}
\]

**Result**

- Calculated steel stress: $\sigma_{{sr}} = {sigma_s:.1f}\,\text{{MPa}}$  
- Allowable stress from 8.6.2.2: $\sigma_{{\text{{lim}}}} \approx {sigma_allow_tables:.1f}\,\text{{MPa}}$  

This check **{"meets" if table_ok else "exceeds"}** the table-based limit.
"""
        )

    # ---------- Tab 2: Calculated crack width ----------
    with tab_calc:
        st.subheader("Crack control by calculation of crack widths – Cl. 8.6.2.3")

        calcbox(
            rf"""
**Purpose**

Calculate the **maximum crack width** in a reinforced concrete beam:

\[
w = s_{{r,\max}} (\varepsilon_{{sm}} - \varepsilon_{{cm}}) \le w'_{{\max}}
\]

**Effective concrete area and reinforcement ratio**

Effective tension area (Cl. 8.6.2.3):

\[
h_{{c,\text{{eff}}}} = \min\bigl( 2.5(D - d),\, (D - k_d)/3,\, D/2 \bigr)
\]

Using:

- $b = {b:.1f}\,\text{{mm}}$, $D = {D:.1f}\,\text{{mm}}$, $d = {d:.1f}\,\text{{mm}}$, $k_d = {kd:.1f}\,\text{{mm}}$

we obtain:

\[
A_{{c,\text{{eff}}}} = b \, h_{{c,\text{{eff}}}} \approx {A_ceff:.0f}\,\text{{mm}}^2
\]

Reinforcement ratio in the effective area:

\[
\rho_{{\text{{eff}}}} = \frac{{A_{{st,\text{{eff}}}}}}{{A_{{c,\text{{eff}}}}}}
= \frac{{{Ast_eff:.0f}}}{{{A_ceff:.0f}}}
\approx {rho_eff:.4f}
\]

**Maximum crack spacing**

For bars at reasonably close centres (Cl. 8.6.2.3):

\[
s_{{r,\max}} = 3.4 c + 0.3 k_1 k_2 d_b / \rho_{{\text{{eff}}}}
\]

Using:

- $c = {c:.1f}\,\text{{mm}}$  
- $d_b = {db:.1f}\,\text{{mm}}$  
- $k_1 = {k1_val:.2f}$, $k_2 = {k2_val:.2f}$  

gives:

\[
s_{{r,\max}} \approx {s_r_max:.1f}\,\text{{mm}}
\]

(Valid for spacing $s \le 5(c + 0.5 d_b)$.)

**Strain difference $(\varepsilon_{{sm}} - \varepsilon_{{cm}})$**

From Cl. 8.6.2.3(2):

\[
\varepsilon_{{sm}} - \varepsilon_{{cm}}
= \frac{{\sigma_{{sr}}}}{{E_s}}
- \frac{{0.6 f_{{ct}}}}{{E_s \rho_{{\text{{eff}}}}} (1 + n_{{\text{{eff}}}} \rho_{{\text{{eff}}}})
+ \varepsilon_{{cs}} \ge 0.6 \frac{{\sigma_{{sr}}}}{{E_s}}
\]

with

\[
n_{{\text{{eff}}}} = (1 + \varphi_{{cc}}) \frac{{E_s}}{{E_c}}
\]

Using:

- $\sigma_{{sr}} = {sigma_s:.1f}\,\text{{MPa}}$  
- $f_{{ct}} = {f_ct:.2f}\,\text{{MPa}}$  
- $E_s = {Es:.0f}\,\text{{MPa}}$, $E_c = {Ec:.0f}\,\text{{MPa}}$  
- $\varphi_{{cc}} = {phi_cc:.2f}$  
- $\varepsilon_{{cs}} = {eps_cs_micro:.1f}\times 10^{{-6}}$

we obtain:

\[
\varepsilon_{{sm}} - \varepsilon_{{cm}} \approx {eps_diff:.3e}
\]

**Crack width**

\[
w = s_{{r,\max}} (\varepsilon_{{sm}} - \varepsilon_{{cm}})
\approx {s_r_max:.1f} \times {eps_diff:.3e}
\approx {w_calc:.3f}\,\text{{mm}}
\]

**Result**

- Calculated crack width: $w \approx {w_calc:.3f}\,\text{{mm}}$  
- Limit: $w'_{{\max}} = {w_lim:.3f}\,\text{{mm}}$  

Thus this check **{"satisfies" if calc_ok else "does not satisfy"}** the crack-width limit.
"""
        )

    # ---------- Tab 3: Workflow / notes ----------
    with tab_flow:
        st.subheader("Crack control workflow – AS 3600:2018 Clause 8.6")

        st.markdown(
            """
### Step 1 – General crack control requirements (Cl. 8.6.1)

- Ensure minimum reinforcement and bar spacing requirements are met (Cl. 8.1.6.1, 8.6.1(b)).  
- Select a characteristic maximum crack width \(w'_{\max}\) based on exposure and function.

---

### Step 2 – Option A: Table-based crack control (Cl. 8.6.2.2)

- Choose \(w'_{\max}\), largest bar diameter \(d_b\) and bar spacing \(s\).  
- Obtain maximum steel stresses from Tables 8.6.2.2(A) and 8.6.2.2(B).  
- Apply the 0.8\(f_{sy}\) limit under direct loading.  
- Check \(\sigma_{sr} \le \sigma_{\text{lim}}\).

---

### Step 3 – Option B: Calculated crack width (Cl. 8.6.2.3)

1. Determine geometry and reinforcement:
   - \(b, D, d, k_d, c, A_{st,\text{eff}}\).  
   - Compute \(A_{c,\text{eff}}\), \(\rho_{\text{eff}}\), \(s_{r,\max}\).
2. Compute material/time-dependent quantities:
   - \(f_{ct}\), \(\varphi_{cc}\), \(\varepsilon_{cs}\), \(E_c, E_s\).  
   - Evaluate \(\varepsilon_{sm} - \varepsilon_{cm}\) from Cl. 8.6.2.3(2).
3. Evaluate crack width:
   - \(w = s_{r,\max} (\varepsilon_{sm} - \varepsilon_{cm})\).  
   - Check \(w \le w'_{\max}\).

---

### Step 4 – Use in serviceability design

- The more onerous of the table-based and calculated checks can be adopted.  
- Use consistent \(w'_{\max}\) across beams on the same facade or exposure.  
- Document assumptions on \(f_{ct}\), \(\varphi_{cc}\), \(\varepsilon_{cs}\), bar layout and cover.
"""
        )
