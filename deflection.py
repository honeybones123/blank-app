# deflection_page.py
# ============================
# DEFLECTION – AS 3600:2018 Cl. 8.5
# ============================

import math
import numpy as np
import pandas as pd
import streamlit as st
import matplotlib.pyplot as plt

from state_and_helpers import get_param, get_sync_callbacks, update_results  # update_results not used but kept for contract
from widgets_helpers import apply_global_widget_css, number_row


# ------------------------------------------------------------
#  Shared helpers
# ------------------------------------------------------------
def _seed_from_param(name: str, fallback: float) -> float:
    """
    Read a numeric value from shared state with get_param(name).
    If missing / NaN / non-numeric, return fallback.
    (Same idea as your current deflection page.)
    """
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
    """Blue calc box styling – same as shear page."""
    st.markdown(
        """
<style>
.calcbox-wrapper {
  margin-top: 0.5rem;
  margin-bottom: 0.75rem;
}
.calcbox-inner {
  padding: 0.75rem 1.0rem;
  border-radius: 0.35rem;
  border-left: 4px solid #1f77b4;
  background-color: rgba(31, 119, 180, 0.06);
  font-size: 0.9rem;
}
</style>
""",
        unsafe_allow_html=True,
    )


def calcbox(md: str):
    """
    Render a highlighted calculation box (LaTeX-safe).
    Use for 'formula + numbers in one place', same as shear.
    """
    html = f"""
<div class="calcbox-wrapper">
  <div class="calcbox-inner">
{md}
  </div>
</div>
"""
    st.markdown(html, unsafe_allow_html=True)


# ------------------------------------------------------------
#  Core deflection helpers (from your standalone script)
# ------------------------------------------------------------
def calc_ief_simplified(fc, beff, bw, d, Ast):
    """
    AS 3600:2018 Cl. 8.5.3.1(2),(3) simplified Ief for reinforced members.
    fc   : f'c in MPa
    beff : effective flange width (mm)
    bw   : web width (mm)
    d    : effective depth (mm)
    Ast  : tension steel area at midspan (mm2)
    """
    beff = max(beff, 1.0)
    bw = max(bw, 1.0)
    d = max(d, 1.0)
    fc = max(fc, 1.0)

    beta = beff / bw
    p = Ast / (beff * d) if beff * d > 0 else 0.0  # reinforcement ratio
    p_lim = 0.001 * (fc ** (1.0 / 3.0)) / (beta ** (2.0 / 3.0))

    if p >= p_lim:
        # Eqn (8.5.3.1(2)) type
        k1 = (5.0 - 0.04 * fc) * p + 0.002
        ief = k1 * beff * d ** 3
        ief_max = (0.1 / (beta ** (2.0 / 3.0))) * beff * d ** 3
    else:
        # Eqn (8.5.3.1(3)) type
        k1 = (0.055 * (fc ** (1.0 / 3.0)) / (beta ** (2.0 / 3.0))) - 50.0 * p
        ief = k1 * beff * d ** 3
        ief_max = (0.06 / (beta ** (2.0 / 3.0))) * beff * d ** 3

    ief = min(ief, ief_max)
    return max(ief, 0.0), beta, p, p_lim, max(ief_max, 0.0), max(k1, 0.0)


def calc_deflection_as3600(L_m, Ec, Ief, g_kNm, q_kNm, psi_s, support_type, Ast, Asc):
    """
    Returns:
        dict with short-term, long-term components and total deflection (mm)
    """
    L_mm = L_m * 1000.0
    L4 = L_mm ** 4
    Ief = max(Ief, 1.0)
    Ec = max(Ec, 1.0)

    # k2 from AS 3600 Cl. 8.5.4
    k2_map = {
        "Simply supported": 5.0 / 384.0,
        "Continuous – end span": 2.4 / 384.0,
        "Continuous – interior span": 1.5 / 384.0,
    }
    k2 = k2_map[support_type]

    # Convert kN/m to N/mm (1 kN/m = 1 N/mm)
    w_total = g_kNm + q_kNm
    w_sust = g_kNm + psi_s * q_kNm

    # Short-term components
    delta_short_total = k2 * w_total * L4 / (Ec * Ief)
    delta_short_sust = k2 * w_sust * L4 / (Ec * Ief)

    # k_cs from Cl. 8.5.3.2
    ratio_Asc_Ast = (Asc / Ast) if Ast > 0 else 0.0
    kcs = 2.0 - 1.2 * ratio_Asc_Ast
    kcs = max(kcs, 0.8)

    # "Additional long-term deflection" due to sustained loads
    delta_long_add = kcs * delta_short_sust

    delta_total = delta_short_total + delta_long_add

    return dict(
        L_mm=L_mm,
        k2=k2,
        w_total=w_total,
        w_sust=w_sust,
        delta_short_total=delta_short_total,
        delta_short_sust=delta_short_sust,
        kcs=kcs,
        delta_long_add=delta_long_add,
        delta_total=delta_total,
    )


def calc_span_depth_limit(ief, beff, bw, d, fc, Ec, Fdef_kNm, support_type, defl_limit_ratio):
    """
    Deemed-to-conform span/depth ratio from AS 3600:2018 Cl. 8.5.4

        L_eff / d <= [ k1 (Δ/L) beff Ec / (k2 Fd,ef) ]^(1/3)

    Returns:
        (L_over_d_limit, k1, k2)
    """
    beff = max(beff, 1.0)
    bw = max(bw, 1.0)
    d = max(d, 1.0)
    Ec = max(Ec, 1.0)
    ief = max(ief, 1.0)

    beta = beff / bw
    # k1 = Ief / (beff d^3)
    k1 = ief / (beff * d ** 3)

    # k2 from Cl. 8.5.4
    k2_map = {
        "Simply supported": 5.0 / 384.0,
        "Continuous – end span": 2.4 / 384.0,
        "Continuous – interior span": 1.5 / 384.0,
    }
    k2 = k2_map[support_type]

    # Deflection limit Δ/L (e.g. 1/250)
    delta_over_L = 1.0 / defl_limit_ratio

    # Fd,ef in kN/m → N/mm (same numeric)
    Fdef = Fdef_kNm

    if Fdef <= 0:
        return None, k1, k2

    inside = (k1 * delta_over_L * beff * Ec) / (k2 * Fdef)
    if inside <= 0:
        return None, k1, k2

    L_over_d_limit = inside ** (1.0 / 3.0)
    return L_over_d_limit, k1, k2


def format_L_over_delta(delta_mm, L_mm):
    if delta_mm <= 0:
        return "–"
    ratio = L_mm / delta_mm
    if ratio <= 0:
        return "–"
    return f"L/{ratio:,.0f}"


# ------------------------------------------------------------
#  MAIN RENDER FUNCTION
# ------------------------------------------------------------
def render_deflection():
    """
    Deflection page: short-term + long-term (creep + shrinkage)
    with AS 3600 Cl. 8.5 formatting, matching shear-page style.
    """
    apply_global_widget_css()
    _inject_calcbox_css()
    sync_callbacks = get_sync_callbacks()

    st.title("Beam Deflection – AS 3600:2018 Clause 8.5")

    st.markdown(
        """
This page checks **reinforced concrete beam deflections** to AS 3600:2018:

- Short-term deflection (Cl. 8.5.3.1)  
- Long-term deflection using **kₛₛ** (Cl. 8.5.3.2)  
- Deemed-to-conform **span-to-depth ratio** (Cl. 8.5.4)  
- **Simplified effective stiffness** \(I_{ef}\) for reinforced members
        """
    )

    st.markdown("### Design inputs")

    # --------------------------------------------------------
    # Inputs – seeded from shared state where possible
    # --------------------------------------------------------
    col_geom, col_mat, col_load = st.columns(3)

    with col_geom:
        # L from shared (mm) → m
        L_seed_mm = _seed_from_param("L", 6000.0)
        L_eff = st.number_input(
            "Effective span Lₑf (m)",
            value=L_seed_mm / 1000.0,
            step=0.1,
            key="defl_L_eff",
        )

        support_type = st.selectbox(
            "Support condition (k₂)",
            ["Simply supported", "Continuous – end span", "Continuous – interior span"],
            index=0,
            key="defl_support_type",
        )

        bw_seed = _seed_from_param("b", 300.0)
        bw = st.number_input(
            "Web / stem width b_w (mm)",
            value=bw_seed,
            step=10.0,
            key="defl_bw",
        )

        beff = st.number_input(
            "Effective flange width bₑf (mm)",
            value=bw_seed,
            step=10.0,
            key="defl_beff",
        )

        d_seed = _seed_from_param("d", 550.0)
        d = st.number_input(
            "Effective depth d (mm)",
            value=d_seed,
            step=10.0,
            key="defl_d",
        )

    with col_mat:
        fc_seed = _seed_from_param("fc", 32.0)
        fc = st.number_input(
            "Concrete strength f'c (MPa)",
            value=fc_seed,
            step=1.0,
            key="defl_fc",
        )

        Ec_seed = _seed_from_param("Ec", 28000.0)
        Ec = st.number_input(
            "Eceff (MPa)",
            value=Ec_seed,
            step=500.0,
            key="defl_Ec",
        )

        Ast_seed = _seed_from_param("Ast_bot", 2010.0)
        Ast = st.number_input(
            "Tension reinforcement area A_st (mm²)",
            value=Ast_seed,
            step=10.0,
            key="defl_Ast",
        )

        Asc = st.number_input(
            "Compression reinforcement A_sc (mm²)",
            value=0.0,
            step=10.0,
            key="defl_Asc",
        )

    with col_load:
        st.markdown("**Service loads (per metre of span)**")

        # service dead/live – these may or may not exist in shared state,
        # so just local here
        g_kNm = st.number_input(
            "Dead load g (kN/m)",
            value=8.0,
            step=0.5,
            key="defl_g",
        )
        q_kNm = st.number_input(
            "Live load q (kN/m)",
            value=4.0,
            step=0.5,
            key="defl_q",
        )
        psi_s = st.number_input(
            "Sustained live-load factor ψₛ",
            value=0.4,
            step=0.05,
            min_value=0.0,
            key="defl_psi_s",
        )
        defl_limit_ratio = st.number_input(
            "Deflection limit L/Δ (e.g. 250)",
            value=250.0,
            step=10.0,
            key="defl_limit_ratio",
        )
        Fdef_kNm = st.number_input(
            "F_d,ef for span-depth check (kN/m)",
            value=12.0,
            step=0.5,
            help="Effective design load per unit length for Cl. 8.5.4",
            key="defl_Fdef",
        )

    # --------------------------------------------------------
    # Effective stiffness Ief
    # --------------------------------------------------------
    st.markdown("### Effective stiffness \(I_{ef}\)")

    col_ief_left, col_ief_right = st.columns([2, 1])

    with col_ief_left:
        use_simplified_ief = st.checkbox(
            "Use simplified reinforced-member Iₑf (AS 3600 Cl. 8.5.3.1(2),(3))",
            value=True,
            key="defl_use_simplified_ief",
        )

        if use_simplified_ief:
            Ief, beta, p, p_lim, Ief_max, k1_from_ief = calc_ief_simplified(
                fc=fc,
                beff=beff,
                bw=bw,
                d=d,
                Ast=Ast,
            )

            calcbox(
                r"""
**Reinforcement & section parameters**

- \(\beta = \dfrac{b_{ef}}{b_w} = %.3f\)  
- \(p = \dfrac{A_{st}}{b_{ef} d} = %.5f\)  
- \(p_{lim} = %.5f\)  
- \(I_{ef,max} = %.3e \text{ mm}^4\)  
- \(k_1 = \dfrac{I_{ef}}{b_{ef} d^3} = %.5f\)
"""
                % (beta, p, p_lim, Ief_max, k1_from_ief)
            )
        else:
            Ief = st.number_input(
                "User-specified Iₑf (mm⁴)",
                value=1.0e11,
                step=1.0e10,
                format="%.3e",
                key="defl_Ief_user",
            )
            beta = beff / bw if bw > 0 else 1.0
            p = Ast / (beff * d) if beff * d > 0 else 0.0
            p_lim = 0.0
            Ief_max = Ief
            k1_from_ief = Ief / (beff * d ** 3)

    with col_ief_right:
        st.metric("Effective second moment Iₑf", f"{Ief:,.3e} mm⁴")
        st.metric("k₁ = Iₑf / (bₑf d³)", f"{k1_from_ief:.4f}")

    # --------------------------------------------------------
    # Main AS 3600 deflection calculations
    # --------------------------------------------------------
    results = calc_deflection_as3600(
        L_m=L_eff,
        Ec=Ec,
        Ief=Ief,
        g_kNm=g_kNm,
        q_kNm=q_kNm,
        psi_s=psi_s,
        support_type=support_type,
        Ast=Ast,
        Asc=Asc,
    )

    L_mm = results["L_mm"]
    delta_short_total = results["delta_short_total"]
    delta_short_sust = results["delta_short_sust"]
    delta_long_add = results["delta_long_add"]
    delta_total = results["delta_total"]
    kcs = results["kcs"]

    L_over_delta_short = format_L_over_delta(delta_short_total, L_mm)
    L_over_delta_long_add = format_L_over_delta(delta_long_add, L_mm)
    L_over_delta_total = format_L_over_delta(delta_total, L_mm)

    L_over_d = (L_mm / d) if d > 0 else 0.0
    L_over_d_limit, k1_span, k2_span = calc_span_depth_limit(
        ief=Ief,
        beff=beff,
        bw=bw,
        d=d,
        fc=fc,
        Ec=Ec,
        Fdef_kNm=Fdef_kNm,
        support_type=support_type,
        defl_limit_ratio=defl_limit_ratio,
    )

    # --------------------------------------------------------
    # Summary banner (similar to shear summary row)
    # --------------------------------------------------------
    st.markdown("## Summary")

    col_s1, col_s2, col_s3, col_s4 = st.columns(4)

    with col_s1:
        st.metric(
            "Short-term deflection (total load)",
            f"{delta_short_total:.2f} mm",
            L_over_delta_short,
        )

    with col_s2:
        st.metric(
            "Additional long-term deflection",
            f"{delta_long_add:.2f} mm",
            L_over_delta_long_add,
        )

    with col_s3:
        util_text = ""
        if delta_total > 0:
            limit_delta = L_mm / defl_limit_ratio
            util = delta_total / limit_delta if limit_delta > 0 else 0.0
            util_text = f"Utilisation: {util:.2f}"
        st.metric(
            "Total deflection (short + long-term)",
            f"{delta_total:.2f} mm",
            L_over_delta_total + ("" if util_text == "" else f" ({util_text})"),
        )

    with col_s4:
        if L_over_d_limit is not None:
            ok_span = L_over_d <= L_over_d_limit
            st.metric(
                "Span-to-depth check Lₑf/d",
                f"{L_over_d:.1f}",
                f"Limit ≈ {L_over_d_limit:.1f} → {'OK' if ok_span else 'NG'}",
            )
        else:
            st.metric("Span-to-depth check Lₑf/d", f"{L_over_d:.1f}", "No limit computed")

    st.markdown("---")

    # --------------------------------------------------------
    # Tabs for step-by-step calcs (shear-style)
    # --------------------------------------------------------
    tab_short, tab_long, tab_ief, tab_span, tab_flow, tab_shape = st.tabs(
        [
            "Short-term deflection",
            "Long-term deflection",
            "Iₑf details",
            "Span/depth check",
            "Flow chart",
            "Deflected shape",
        ]
    )

    # ---------- Short-term ----------
    with tab_short:
        st.subheader("Short-term deflection – AS 3600 Cl. 8.5.3.1")

        calcbox(
            r"""
**Formula**

\[
\delta_{st} = k_2 \frac{w L_{eff}^4}{E_{c,eff} I_{ef}}
\]

**With numbers**

\[
\delta_{st,total}
= (%.5f) \times (%.2f)\, \frac{(%.0f)^4}{(%.0f) \times (%.3e)}
\approx %.2f \text{ mm}
\]

where \(w = g + q = %.2f \text{ kN/m}\).
"""
            % (
                results["k2"],
                results["w_total"],
                L_mm,
                Ec,
                Ief,
                delta_short_total,
                results["w_total"],
            )
        )

        st.markdown("#### Key inputs")

        st.write(rf"- $L_{{eff}}$ = **{L_mm:.0f} mm**")
        st.write(rf"- $w = g + q$ = **{results['w_total']:.2f} kN/m**")
        st.write(rf"- $k_2$ (from support type) = **{results['k2']:.5f}**")
        st.write(rf"- $E_{{c,eff}}$ = **{Ec:.0f} MPa**")
        st.write(rf"- $I_{{ef}}$ = **{Ief:,.3e} \,\text{{mm}}^4$**")

    # ---------- Long-term ----------
    with tab_long:
        st.subheader("Long-term deflection – AS 3600 Cl. 8.5.3.2")

        calcbox(
            r"""
**Key relationships**

\[
k_{cs} = \max\left[\,2 - 1.2 \left(\frac{A_{sc}}{A_{st}}\right),\, 0.8 \right]
\]

\[
\delta_{st,sust} = k_2 \frac{w_{sust} L_{eff}^4}{E_{c,eff} I_{ef}}
\]

\[
\delta_{LT,add} = k_{cs} \, \delta_{st,sust}
\quad\text{and}\quad
\delta_{total} = \delta_{st,total} + \delta_{LT,add}
\]
"""
        )

        st.markdown("#### Inputs for long-term component")

        st.write(
            f"- Sustained load \(w_{{sust}} = g + \\psi_s q\) = **{results['w_sust']:.2f} kN/m**"
        )
        st.write(f"- ψₛ = **{psi_s:.2f}**")
        st.write(f"- A_st = **{Ast:.0f} mm²**,  A_sc = **{Asc:.0f} mm²**")
        st.write(f"- A_sc / A_st = **{(Asc / Ast if Ast > 0 else 0.0):.3f}**")
        st.write(f"- → k_cs = **{kcs:.2f}**")

        st.markdown("#### Results")

        st.write("Short-term deflection due to **sustained load** only:")
        st.write(f"- δ_st,sust = **{delta_short_sust:.2f} mm**")

        st.write("Additional long-term deflection due to creep + shrinkage:")
        st.write(
            f"- δ_LT,add = k_cs × δ_st,sust = **{delta_long_add:.2f} mm**  →  {L_over_delta_long_add}"
        )

        st.write("Total deflection (short-term + long-term):")
        st.write(f"- **δ_total = {delta_total:.2f} mm**  →  {L_over_delta_total}")

    # ---------- Ief details ----------
    with tab_ief:
        st.subheader("Effective second moment of area Iₑf – AS 3600 Cl. 8.5.3.1")

        calcbox(
            r"""
For **reinforced members**, the simplified expressions for \(I_{ef}\) are:

- When \(p \ge p_{lim}\):

\[
I_{ef} = \left[(5 - 0.04 f'_c) p + 0.002 \right] b_{ef} d^3
\]

- When \(p < p_{lim}\):

\[
I_{ef} = \left[0.055 (f'_c)^{1/3} / \beta^{2/3} - 50 p \right] b_{ef} d^3
\]

with caps on \(I_{ef,max}\) depending on \(\beta\).
"""
        )

        st.markdown("#### Section & reinforcement parameters")

        st.write(f"b_w = **{bw:.1f} mm**,  bₑf = **{beff:.1f} mm**,  β = **{beta:.3f}**")
        st.write(f"d = **{d:.1f} mm**")
        st.write(f"A_st = **{Ast:.1f} mm²**")
        st.write(f"p = A_st / (bₑf d) = **{p:.5f}**")
        st.write(f"p_lim = **{p_lim:.5f}**")

        st.markdown("#### Output")

        st.write(f"Iₑf = **{Ief:,.3e} mm⁴**")
        st.write(f"Iₑf,max = **{Ief_max:,.3e} mm⁴**")
        st.write(f"k₁ = Iₑf / (bₑf d³) = **{k1_from_ief:.5f}**")

    # ---------- Span/depth ----------
    with tab_span:
        st.subheader("Deemed-to-conform span-to-depth ratio – AS 3600 Cl. 8.5.4")

        calcbox(
            r"""
\[
\frac{L_{ef}}{d} \le 
\left[
\dfrac{k_1 \, (\Delta/L_{ef}) \, b_{ef} E_{c,eff}}{k_2 F_{d,ef}}
\right]^{1/3}
\]
"""
        )

        st.markdown("#### Inputs")

        st.write(f"- k₁ = **{k1_span:.5f}** (from Iₑf)")
        st.write(f"- k₂ = **{k2_span:.5f}** (from support type)")
        st.write(f"- Δ/L limit = **1/{defl_limit_ratio:.0f}**")
        st.write(f"- F_d,ef = **{Fdef_kNm:.2f} kN/m**")
        st.write(f"- Lₑf = **{L_mm:.0f} mm**,  d = **{d:.1f} mm** → Lₑf/d = **{L_over_d:.1f}**")

        st.markdown("#### Check")

        if L_over_d_limit is None:
            st.warning("Could not compute Lₑf/d limit (F_d,ef ≤ 0).")
        else:
            ok_span = L_over_d <= L_over_d_limit
            st.write(
                f"Allowed \(Lₑf/d\) ≤ **{L_over_d_limit:.1f}** → "
                f"{'✅ OK – deemed to conform' if ok_span else '❌ NG – exceeds deemed limit'}"
            )

    # ---------- Flow chart / explanation ----------
    with tab_flow:
        st.subheader("Flow chart – Deflection check to AS 3600")

        st.markdown(
            """
### Step 1 – Define section, materials & loads
- Geometry: \(L_{ef}, b_w, b_{ef}, d\)  
- Materials: \(f'_c, E_{c,eff}, A_{st}, A_{sc}\)  
- Loads: \(g, q, \\psi_s, F_{d,ef}\), deflection limit \(L/Δ\)

---

### Step 2 – Effective stiffness Iₑf (Cl. 8.5.3.1)

1. Compute  
   - \(\\beta = b_{ef} / b_w\)  
   - \(p = A_{st} / (b_{ef} d)\)  
   - \(p_{lim}\) from AS 3600  

2. Use appropriate simplified expression to obtain \(I_{ef}\)  
3. Cap at \(I_{ef,max}\) as per AS 3600  

---

### Step 3 – Short-term deflection (Cl. 8.5.3.1)

1. Select \(k_2\) from support type  
2. Compute total service load \(w = g + q\)  
3. Evaluate  

   \\[
   \\delta_{st,total} = k_2 \\dfrac{w L_{eff}^4}{E_{c,eff} I_{ef}}
   \\]

---

### Step 4 – Long-term deflection (Cl. 8.5.3.2)

1. Sustained load  
   \\(w_{sust} = g + \\psi_s q\\)  

2. Short-term deflection from sustained load  

   \\[
   \\delta_{st,sust} = k_2 \\dfrac{w_{sust} L_{eff}^4}{E_{c,eff} I_{ef}}
   \\]

3. Creep/shrinkage multiplier  

   \\[
   k_{cs} = \\max[2 - 1.2(A_{sc}/A_{st}), 0.8]
   \\]

4. Additional long-term deflection  

   \\[
   \\delta_{LT,add} = k_{cs} \\delta_{st,sust}
   \\]

5. Total deflection  

   \\[
   \\delta_{total} = \\delta_{st,total} + \\delta_{LT,add}
   \\]

---

### Step 5 – Serviceability checks

1. Compare total deflection to limit:

   \\[
   \\delta_{total} \\le \\dfrac{L_{eff}}{(L/\\Delta)_{limit}}
   \\]

2. Optionally check deemed-to-conform span-depth ratio:

   \\[
   \\frac{L_{ef}}{d} \\le
   \\left[
   \\dfrac{k_1 (\\Delta/L_{ef}) b_{ef} E_{c,eff}}{k_2 F_{d,ef}}
   \\right]^{1/3}
   \\]

3. Report **utilisation** and whether the span is **deemed to conform**.
        """
        )

    # ---------- Deflected shape (like your original page) ----------
    with tab_shape:
        st.subheader("Deflected Shape (Illustrative – uses δ_total)")

        x = np.linspace(0.0, L_mm, 200)
        xi = x / L_mm
        # simple parabolic shape scaled to δ_total
        y_long = -delta_total * 4.0 * xi * (1.0 - xi)

        fig, ax = plt.subplots()
        ax.plot(x, y_long)
        ax.set_xlabel("Span position x (mm)")
        ax.set_ylabel("Deflection (mm)")
        ax.axhline(0.0, linewidth=0.8)
        ax.grid(True)

        st.pyplot(fig)


    # ---------- Long-term ----------
    with tab_long:
        st.subheader("Long-term deflection – AS 3600 Cl. 8.5.3.2")

        calcbox(
            r"""
**Key relationships**

\[
k_{cs} = \max\left[\,2 - 1.2 \left(\frac{A_{sc}}{A_{st}}\right),\, 0.8 \right]
\]

\[
\delta_{st,sust} = k_2 \frac{w_{sust} L_{eff}^4}{E_{c,eff} I_{ef}}
\]

\[
\delta_{LT,add} = k_{cs} \, \delta_{st,sust}
\quad\text{and}\quad
\delta_{total} = \delta_{st,total} + \delta_{LT,add}
\]
"""
        )

        st.markdown("#### Inputs for long-term component")

        st.write(
            f"- Sustained load \(w_{{sust}} = g + \\psi_s q\) = **{results['w_sust']:.2f} kN/m**"
        )
        st.write(f"- ψₛ = **{psi_s:.2f}**")
        st.write(f"- A_st = **{Ast:.0f} mm²**,  A_sc = **{Asc:.0f} mm²**")
        st.write(f"- A_sc / A_st = **{(Asc / Ast if Ast > 0 else 0.0):.3f}**")
        st.write(f"- → k_cs = **{kcs:.2f}**")

        st.markdown("#### Results")

        st.write("Short-term deflection due to **sustained load** only:")
        st.write(f"- δ_st,sust = **{delta_short_sust:.2f} mm**")

        st.write("Additional long-term deflection due to creep + shrinkage:")
        st.write(
            f"- δ_LT,add = k_cs × δ_st,sust = **{delta_long_add:.2f} mm**  →  {L_over_delta_long_add}"
        )

        st.write("Total deflection (short-term + long-term):")
        st.write(f"- **δ_total = {delta_total:.2f} mm**  →  {L_over_delta_total}")

    # ---------- Ief details ----------
    with tab_ief:
        st.subheader("Effective second moment of area Iₑf – AS 3600 Cl. 8.5.3.1")

        calcbox(
            r"""
For **reinforced members**, the simplified expressions for \(I_{ef}\) are:

- When \(p \ge p_{lim}\):

\[
I_{ef} = \left[(5 - 0.04 f'_c) p + 0.002 \right] b_{ef} d^3
\]

- When \(p < p_{lim}\):

\[
I_{ef} = \left[0.055 (f'_c)^{1/3} / \beta^{2/3} - 50 p \right] b_{ef} d^3
\]

with caps on \(I_{ef,max}\) depending on \(\beta\).
"""
        )

        st.markdown("#### Section & reinforcement parameters")

        st.write(f"b_w = **{bw:.1f} mm**,  bₑf = **{beff:.1f} mm**,  β = **{beta:.3f}**")
        st.write(f"d = **{d:.1f} mm**")
        st.write(f"A_st = **{Ast:.1f} mm²**")
        st.write(f"p = A_st / (bₑf d) = **{p:.5f}**")
        st.write(f"p_lim = **{p_lim:.5f}**")

        st.markdown("#### Output")

        st.write(f"Iₑf = **{Ief:,.3e} mm⁴**")
        st.write(f"Iₑf,max = **{Ief_max:,.3e} mm⁴**")
        st.write(f"k₁ = Iₑf / (bₑf d³) = **{k1_from_ief:.5f}**")

    # ---------- Span/depth ----------
    with tab_span:
        st.subheader("Deemed-to-conform span-to-depth ratio – AS 3600 Cl. 8.5.4")

        calcbox(
            r"""
\[
\frac{L_{ef}}{d} \le 
\left[
\dfrac{k_1 \, (\Delta/L_{ef}) \, b_{ef} E_{c,eff}}{k_2 F_{d,ef}}
\right]^{1/3}
\]
"""
        )

        st.markdown("#### Inputs")

        st.write(f"- k₁ = **{k1_span:.5f}** (from Iₑf)")
        st.write(f"- k₂ = **{k2_span:.5f}** (from support type)")
        st.write(f"- Δ/L limit = **1/{defl_limit_ratio:.0f}**")
        st.write(f"- F_d,ef = **{Fdef_kNm:.2f} kN/m**")
        st.write(f"- Lₑf = **{L_mm:.0f} mm**,  d = **{d:.1f} mm** → Lₑf/d = **{L_over_d:.1f}**")

        st.markdown("#### Check")

        if L_over_d_limit is None:
            st.warning("Could not compute Lₑf/d limit (F_d,ef ≤ 0).")
        else:
            ok_span = L_over_d <= L_over_d_limit
            st.write(
                f"Allowed \(Lₑf/d\) ≤ **{L_over_d_limit:.1f}** → "
                f"{'✅ OK – deemed to conform' if ok_span else '❌ NG – exceeds deemed limit'}"
            )

    # ---------- Flow chart / explanation ----------
    with tab_flow:
        st.subheader("Flow chart – Deflection check to AS 3600")

        st.markdown(
            """
### Step 1 – Define section, materials & loads
- Geometry: \(L_{ef}, b_w, b_{ef}, d\)  
- Materials: \(f'_c, E_{c,eff}, A_{st}, A_{sc}\)  
- Loads: \(g, q, \\psi_s, F_{d,ef}\), deflection limit \(L/Δ\)

---

### Step 2 – Effective stiffness Iₑf (Cl. 8.5.3.1)

1. Compute  
   - \(\\beta = b_{ef} / b_w\)  
   - \(p = A_{st} / (b_{ef} d)\)  
   - \(p_{lim}\) from AS 3600  

2. Use appropriate simplified expression to obtain \(I_{ef}\)  
3. Cap at \(I_{ef,max}\) as per AS 3600  

---

### Step 3 – Short-term deflection (Cl. 8.5.3.1)

1. Select \(k_2\) from support type  
2. Compute total service load \(w = g + q\)  
3. Evaluate  

   \\[
   \\delta_{st,total} = k_2 \\dfrac{w L_{eff}^4}{E_{c,eff} I_{ef}}
   \\]

---

### Step 4 – Long-term deflection (Cl. 8.5.3.2)

1. Sustained load  
   \\(w_{sust} = g + \\psi_s q\\)  

2. Short-term deflection from sustained load  

   \\[
   \\delta_{st,sust} = k_2 \\dfrac{w_{sust} L_{eff}^4}{E_{c,eff} I_{ef}}
   \\]

3. Creep/shrinkage multiplier  

   \\[
   k_{cs} = \\max[2 - 1.2(A_{sc}/A_{st}), 0.8]
   \\]

4. Additional long-term deflection  

   \\[
   \\delta_{LT,add} = k_{cs} \\delta_{st,sust}
   \\]

5. Total deflection  

   \\[
   \\delta_{total} = \\delta_{st,total} + \\delta_{LT,add}
   \\]

---

### Step 5 – Serviceability checks

1. Compare total deflection to limit:

   \\[
   \\delta_{total} \\le \\dfrac{L_{eff}}{(L/\\Delta)_{limit}}
   \\]

2. Optionally check deemed-to-conform span-depth ratio:

   \\[
   \\frac{L_{ef}}{d} \\le
   \\left[
   \\dfrac{k_1 (\\Delta/L_{ef}) b_{ef} E_{c,eff}}{k_2 F_{d,ef}}
   \\right]^{1/3}
   \\]

3. Report **utilisation** and whether the span is **deemed to conform**.
        """
        )

    # ---------- Deflected shape (like your original page) ----------
    with tab_shape:
        st.subheader("Deflected Shape (Illustrative – uses δ_total)")

        x = np.linspace(0.0, L_mm, 200)
        xi = x / L_mm
        # simple parabolic shape scaled to δ_total
        y_long = -delta_total * 4.0 * xi * (1.0 - xi)

        fig, ax = plt.subplots()
        ax.plot(x, y_long)
        ax.set_xlabel("Span position x (mm)")
        ax.set_ylabel("Deflection (mm)")
        ax.axhline(0.0, linewidth=0.8)
        ax.grid(True)

        st.pyplot(fig)


