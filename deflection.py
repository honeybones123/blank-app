# deflection_page.py

import math
import numpy as np
import pandas as pd
import streamlit as st
import matplotlib.pyplot as plt

from state_and_helpers import (
    get_param,
    get_sync_callbacks,
    update_results,  # kept for contract / future use
)
from widgets_helpers import apply_global_widget_css, number_row


# ------------------------------------------------------------
#  Shared helpers
# ------------------------------------------------------------
def _seed_from_param(name: str, fallback: float) -> float:
    """Read numeric from shared state with get_param(name), with fallback."""
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
    """Style markdown blockquotes as blue calc boxes – same feel as shear page."""
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
#  Core deflection helpers (AS 3600:2018 Cl. 8.5)
# ------------------------------------------------------------
def calc_ief_simplified(fc, beff, bw, d, Ast):
    """
    AS 3600:2018 Cl. 8.5.3.1(2),(3) simplified Ief for reinforced members.
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
        ief = k1 * beff * (d ** 3)
        ief_max = (0.1 / (beta ** (2.0 / 3.0))) * beff * (d ** 3)
    else:
        # Eqn (8.5.3.1(3)) type
        k1 = (0.055 * (fc ** (1.0 / 3.0)) / (beta ** (2.0 / 3.0))) - 50.0 * p
        ief = k1 * beff * (d ** 3)
        ief_max = (0.06 / (beta ** (2.0 / 3.0))) * beff * (d ** 3)

    ief = min(ief, ief_max)
    return max(ief, 0.0), beta, p, p_lim, max(ief_max, 0.0), max(k1, 0.0)


def calc_deflection_as3600(L_m, Ec, Ief, g_kNm, q_kNm, psi_s, support_type, Ast, Asc):
    """Return dict with short-term, long-term components and total deflection (mm)."""
    L_mm = L_m * 1000.0
    L4 = L_mm ** 4
    Ief = max(Ief, 1.0)
    Ec = max(Ec, 1.0)

    k2_map = {
        "Simply supported": 5.0 / 384.0,
        "Continuous – end span": 2.4 / 384.0,
        "Continuous – interior span": 1.5 / 384.0,
    }
    k2 = k2_map[support_type]

    # kN/m → N/mm (1 kN/m = 1 N/mm numerically)
    w_total = g_kNm + q_kNm
    w_sust = g_kNm + psi_s * q_kNm

    delta_short_total = k2 * w_total * L4 / (Ec * Ief)
    delta_short_sust = k2 * w_sust * L4 / (Ec * Ief)

    ratio_Asc_Ast = (Asc / Ast) if Ast > 0 else 0.0
    kcs = 2.0 - 1.2 * ratio_Asc_Ast
    kcs = max(kcs, 0.8)

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
    Deemed-to-conform span/depth ratio from AS 3600:2018 Cl. 8.5.4.
    Returns (L_over_d_limit, k1, k2).
    """
    beff = max(beff, 1.0)
    bw = max(bw, 1.0)
    d = max(d, 1.0)
    Ec = max(Ec, 1.0)
    ief = max(ief, 1.0)

    k1 = ief / (beff * (d ** 3))

    k2_map = {
        "Simply supported": 5.0 / 384.0,
        "Continuous – end span": 2.4 / 384.0,
        "Continuous – interior span": 1.5 / 384.0,
    }
    k2 = k2_map[support_type]

    delta_over_L = 1.0 / defl_limit_ratio if defl_limit_ratio > 0 else 0.0
    Fdef = Fdef_kNm

    if Fdef <= 0 or delta_over_L <= 0:
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
    """Deflection page – short-term, long-term, span/depth to AS 3600:2018 Cl. 8.5."""
    apply_global_widget_css()
    _inject_calcbox_css()
    sync_callbacks = get_sync_callbacks()  # not used yet but kept for contract

    st.title("Beam Deflection – AS 3600:2018 Clause 8.5")

    st.markdown(
        """
This page checks **reinforced concrete beam deflections** to AS 3600:2018:

- Short-term deflection (Cl. 8.5.3.1)  
- Long-term deflection using **kₛₛ** (Cl. 8.5.3.2)  
- Deemed-to-conform **span-to-depth ratio** (Cl. 8.5.4)  
- **Simplified effective stiffness** \(I_{ef}\) for reinforced members

Deflection is linked to the **Design / SFD-BMD** page – you must define a
service load case there first.
        """
    )

    # Reserve space for the top summary table
    summary_placeholder = st.empty()

    # ---------- Actions from Inputs page ----------
    action_source = get_param("actions_source", "Manual design actions (inputs below)")
    Mu_star = get_param("Mu_star", 0.0)
    Vu_star = get_param("Vu_star", 0.0)

    # ---------- Unified loading from SFD/BMD page ----------
    load_case = st.session_state.get("load_case", None)
    L_sfd = get_param("span_L_m", None)  # span in m

    # Get SLS loads (either UDL or point load depending on case)
    w_sls = get_param("w_sls_kNm_per_m", None)  # SLS UDL if applicable
    P_sls = get_param("P_sls_kN", None)  # SLS point load if applicable
    a = get_param("a_m", None)  # distance a for point loads (if used)

    # For display in calcbox (these come from Inputs / Design)
    g = get_param("g_udl_kNm_per_m", 0.0)
    q = get_param("q_udl_kNm_per_m", 0.0)
    psi_s = get_param("psi_udl", 0.4)
    G_point = get_param("G_point_kN", 0.0)
    Q_point = get_param("Q_point_kN", 0.0)
    psi_s_point = get_param("psi_point", 0.4)

    # ---- Require the Design / SFD tab to be used first ----
    if load_case is None or (w_sls is None and P_sls is None):
        st.warning(
            "Deflection is driven by the **Design / SFD-BMD** load case.\n\n"
            "- Go to the Design / SFD-BMD page\n"
            "- Define an SLS load case (UDL or point load)\n"
            "- Save / apply it so that `load_case` and SLS loads are stored\n\n"
            "Once a load case is defined, return here to run the deflection checks."
        )
        return

    # --------------------------------------------------------
    # Design inputs (geometry / materials / loads)
    # --------------------------------------------------------
    st.markdown("### Design inputs")

    col_geom, col_mat, col_load = st.columns(3)

    with col_geom:
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
        st.markdown("**Serviceability limits / design load for span–depth**")

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
    # Effective stiffness Ief – single source of truth
    # (choice driven by Ief tab via session_state keys)
    # --------------------------------------------------------
    use_simplified_ief_state = st.session_state.get("defl_use_simplified_ief", True)
    user_Ief_state = float(st.session_state.get("defl_Ief_user", 1.0e11))

    if use_simplified_ief_state:
        Ief, beta, p, p_lim, Ief_max, k1_from_ief = calc_ief_simplified(
            fc=fc,
            beff=beff,
            bw=bw,
            d=d,
            Ast=Ast,
        )
    else:
        Ief = max(user_Ief_state, 1.0)
        beta = beff / bw if bw > 0 else 1.0
        p = Ast / (beff * d) if beff * d > 0 else 0.0
        p_lim = 0.0
        Ief_max = Ief
        k1_from_ief = Ief / (beff * (d ** 3))

    # --------------------------------------------------------
    # Main deflection calculations (single engine)
    # --------------------------------------------------------
    results = calc_deflection_as3600(
        L_m=L_eff,
        Ec=Ec,
        Ief=Ief,
        g_kNm=g,
        q_kNm=q,
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
    w_total = results["w_total"]
    w_sust = results["w_sust"]
    k2_main = results["k2"]

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

    # Limiting deflection in mm for summary / Step 4
    limit_delta_mm = L_mm / defl_limit_ratio if defl_limit_ratio > 0 else None

    # --------------------------------------------------------
    # 4-STEP CALC NARRATIVE (using single AS 3600 result)
    # --------------------------------------------------------
    # Step 1 – design actions
    calcbox(
        f"""
**Step 1 – Adopt design actions**

- Source: `{action_source}`
- Bending moment M*: `{Mu_star:.3g}` kNm  
- Shear force V*: `{Vu_star:.3g}` kN  

These come from the **Inputs** / **Design** toggle: either manual M*, V* or
scaled SFD/BMD diagrams.
"""
    )

    # Step 2 – service load for deflection (from Design / SFD-BMD)
    if w_sls is not None:
        # UDL case
        calcbox(
            f"""
**Step 2 – Service UDL for deflection**

From the **Design / SFD-BMD** page:

- Dead UDL: `g = {g:.3g}` kN/m  
- Live UDL: `q = {q:.3g}` kN/m  
- Sustained factor: `ψ_s = {psi_s:.3g}`  

Effective SLS UDL used for deflection:

\\[
w_{{\\text{{sls}}}} = g + ψ_s q = {w_sls:.3g}\\;\\text{{kN/m}}
\\]
"""
        )
    elif P_sls is not None:
        # Point load case – still report, even though AS 3600 engine uses g, q
        calcbox(
            f"""
**Step 2 – Service point load for deflection**

From the **Design / SFD-BMD** page:

- Dead point load: `G = {G_point:.3g}` kN  
- Live point load: `Q = {Q_point:.3g}` kN  
- Sustained factor: `ψ_s = {psi_s_point:.3g}`  

Effective SLS point load:

\\[
P_{{\\text{{sls}}}} = G + ψ_s Q = {P_sls:.3g}\\;\\text{{kN}}
\\]

(Current AS 3600 deflection engine uses an equivalent UDL from `g` and `q`.)
"""
        )
    else:
        # Shouldn't happen because of gate, but keep a safe message
        calcbox(
            """
**Step 2 – Service load for deflection**

No SLS load has been defined. Please set up an SLS load case on the
**Design / SFD-BMD** page.
"""
        )

    # Step 3 – short-term deflection formula (single engine)
    calcbox(
        f"""
**Step 3 – Short-term deflection using Iₑf (AS 3600 Cl. 8.5.3.1)**

Deflection constant from support type:

- `k₂ = {k2_main:.5f}` for `{support_type}`  

Total service UDL:

- `w = g + q = {w_total:.3g}` kN/m  

Effective stiffness from Iₑf:

- \(E_{{c,eff}} = {Ec:.0f}\\,\\text{{MPa}}\)  
- \(I_{{ef}} = {Ief:,.3e}\\,\\text{{mm}}^4\)  

Short-term midspan deflection under total service load:

\\[
\\delta_{{st,total}}
= k_2 \\dfrac{{w L_{{eff}}^4}}{{E_{{c,eff}} I_{{ef}}}}
\\]

With substitution:

\\[
\\delta_{{st,total}}
\\approx {delta_short_total:.2f}\\,\\text{{mm}}
\\]
"""
    )

    # Step 4 – long-term + SLS check (single engine)
    if limit_delta_mm and limit_delta_mm > 0:
        util_total = delta_total / limit_delta_mm
        util_text = f"`{util_total:.3g}`"
        limit_text = f"`{limit_delta_mm:.3g}` mm (L/{defl_limit_ratio:.0f})"
    else:
        util_total = None
        util_text = "`—`"
        limit_text = "`—`"

    calcbox(
        f"""
**Step 4 – Long-term deflection and SLS check (AS 3600 Cl. 8.5.3.2)**

Additional long-term deflection due to sustained load:

\\[
\\delta_{{LT,add}} = k_{{cs}} \\delta_{{st,sust}}
\\]

Total deflection:

\\[
\\delta_{{total}} = \\delta_{{st,total}} + \\delta_{{LT,add}}
\\approx {delta_total:.2f}\\,\\text{{mm}}
\\]

Serviceability limit:

- User limit: `L/Δ = {defl_limit_ratio:.0f}`  
- Allowable deflection ≈ {limit_text}  

Utilisation:

- \(\\delta_{{total}} / \\delta_{{limit}} \\approx {util_text}\)

(Ensure units of δ and L are consistent in your stiffness setup.)
"""
    )

    # --------------------------------------------------------
    # TOP SUMMARY TABLE (bending-style rows)
    # --------------------------------------------------------
    with summary_placeholder.container():
        st.markdown("## Summary")

        rows = []

        if limit_delta_mm and limit_delta_mm > 0:
            limit_str = f"{limit_delta_mm:.2f} mm (L/{defl_limit_ratio:.0f})"
        else:
            limit_str = "—"

        # 1) Short-term total
        if limit_delta_mm and limit_delta_mm > 0:
            util_short = delta_short_total / limit_delta_mm
            status_short = "OK" if util_short <= 1.0 else "NG"
        else:
            util_short = None
            status_short = "—"

        rows.append(
            dict(
                Check="Short-term deflection (total load)",
                Value=f"{delta_short_total:.2f} mm ({L_over_delta_short})",
                Limit=limit_str,
                Utilisation=f"{util_short:.2f}" if util_short is not None else "—",
                Status=status_short,
            )
        )

        # 2) Long-term additional
        if limit_delta_mm and limit_delta_mm > 0:
            util_long = delta_long_add / limit_delta_mm
            status_long = "OK" if util_long <= 1.0 else "NG"
        else:
            util_long = None
            status_long = "—"

        rows.append(
            dict(
                Check="Additional long-term deflection",
                Value=f"{delta_long_add:.2f} mm ({L_over_delta_long_add})",
                Limit=limit_str,
                Utilisation=f"{util_long:.2f}" if util_long is not None else "—",
                Status=status_long,
            )
        )

        # 3) Total
        if limit_delta_mm and limit_delta_mm > 0:
            util_total_summary = delta_total / limit_delta_mm
            status_total = "OK" if util_total_summary <= 1.0 else "NG"
        else:
            util_total_summary = None
            status_total = "—"

        rows.append(
            dict(
                Check="Total deflection (short + long-term)",
                Value=f"{delta_total:.2f} mm ({L_over_delta_total})",
                Limit=limit_str,
                Utilisation=f"{util_total_summary:.2f}" if util_total_summary is not None else "—",
                Status=status_total,
            )
        )

        # 4) Span/depth
        if L_over_d_limit is not None and L_over_d_limit > 0:
            util_span = L_over_d / L_over_d_limit
            status_span = "OK" if util_span <= 1.0 else "NG"
            limit_span_str = f"{L_over_d_limit:.1f}"
        else:
            util_span = None
            status_span = "—"
            limit_span_str = "—"

        rows.append(
            dict(
                Check="Span-to-depth ratio Lₑf/d",
                Value=f"{L_over_d:.1f}",
                Limit=limit_span_str,
                Utilisation=f"{util_span:.2f}" if util_span is not None else "—",
                Status=status_span,
            )
        )

        summary_df = pd.DataFrame(rows)

        def _highlight_status(row):
            status = row.get("Status", "")
            if status == "OK":
                color = "#d9ead3"
            elif status == "NG":
                color = "#f4cccc"
            else:
                color = ""
            return [f"background-color: {color}"] * len(row)

        styled = summary_df.style.apply(_highlight_status, axis=1)
        st.dataframe(styled, use_container_width=True)
        st.markdown("---")

    # --------------------------------------------------------
    # Tabs in agreed order (Ief, short-term, long-term, span/depth, flow, shape)
    # --------------------------------------------------------
    tab_ief, tab_short, tab_long, tab_span, tab_flow, tab_shape = st.tabs(
        [
            "Iₑf details",
            "Short-term deflection",
            "Long-term deflection",
            "Span/depth check",
            "Flow chart",
            "Deflected shape",
        ]
    )

    # TAB 1: Ief details + input choice
    with tab_ief:
        st.subheader("Effective stiffness (Iₑf) – input choice")

        use_simplified_ief = st.checkbox(
            "Use simplified reinforced-member Iₑf (AS 3600 Cl. 8.5.3.1(2),(3))",
            value=use_simplified_ief_state,
            key="defl_use_simplified_ief",
        )

        if use_simplified_ief:
            # Show the simplified result (already used in main calc)
            Ief_tab = Ief
            k1_from_ief_tab = k1_from_ief
            Ief_max_tab = Ief_max
        else:
            Ief_tab = st.number_input(
                "User-specified Iₑf (mm⁴)",
                value=user_Ief_state,
                step=1.0e10,
                format="%.3e",
                key="defl_Ief_user",
            )
            # Update local copies used in explanatory text
            Ief_tab = max(Ief_tab, 1.0)
            Ief_tab = float(Ief_tab)
            Ief_max_tab = Ief_tab
            k1_from_ief_tab = Ief_tab / (beff * (d ** 3))

        text = rf"""
**Purpose**

Compute the effective second moment of area $I_{{ef}}$ for a reinforced concrete member
using the simplified expressions in AS 3600:2018 Cl. 8.5.3.1(2) and (3). This cracked
stiffness is then used in all deflection checks.

**Inputs**

- Concrete strength: $f'_c = {fc:.1f}\,\text{{MPa}}$
- Web / stem width: $b_w = {bw:.1f}\,\text{{mm}}$
- Effective flange width: $b_{{ef}} = {beff:.1f}\,\text{{mm}}$
- Effective depth: $d = {d:.1f}\,\text{{mm}}$
- Tension steel area: $A_{{st}} = {Ast:.1f}\,\text{{mm}}^2$

Derived section parameters:

- Width ratio: $\beta = \dfrac{{b_{{ef}}}}{{b_w}} = {beta:.3f}$
- Reinforcement ratio: $p = \dfrac{{A_{{st}}}}{{b_{{ef}} d}} = {p:.5f}$
- Limit ratio: $p_{{lim}} = {p_lim:.5f}$

**Formula**

For reinforced members (AS 3600:2018 Cl. 8.5.3.1):

If $p \ge p_{{lim}}$:

\\[
I_{{ef}} = \left[(5 - 0.04 f'_c)\, p + 0.002 \right]\, b_{{ef}} d^3
\\]

If $p < p_{{lim}}$:

\\[
I_{{ef}} = \left[0.055 (f'_c)^{{1/3}} / \beta^{{2/3}} - 50 p \right]\, b_{{ef}} d^3
\\]

Capped by:

\\[
I_{{ef}} \le I_{{ef,max}}
= {Ief_max_tab:,.3e}\,\text{{mm}}^4
\\]

and

\\[
k_1 = \dfrac{{I_{{ef}}}}{{b_{{ef}} d^3}}
\\]

**Substitution**

Using the current inputs:

- Computed $I_{{ef}} \approx {Ief_tab:,.3e}\,\text{{mm}}^4$
- $I_{{ef,max}} = {Ief_max_tab:,.3e}\,\text{{mm}}^4$
- $k_1 = \dfrac{{I_{{ef}}}}{{b_{{ef}} d^3}} \approx {k1_from_ief_tab:.5f}$

**Result**

- $I_{{ef}} = {Ief_tab:,.3e}\,\text{{mm}}^4$
- $k_1 = {k1_from_ief_tab:.5f}$
- (cap) $I_{{ef,max}} = {Ief_max_tab:,.3e}\,\text{{mm}}^4$

_Ref: AS 3600:2018 Cl. 8.5.3.1(2) & (3) – simplified $I_{{ef}}$ for reinforced members._
"""
        calcbox(text)

    # TAB 2: Short-term
    with tab_short:
        st.subheader("Short-term deflection – AS 3600 Cl. 8.5.3.1")

        text = rf"""
**Purpose**

Determine the **short-term midspan deflection** under **total service load**
$w = g + q$ using the effective stiffness $I_{{ef}}$ from the Iₑf tab
(AS 3600 Cl. 8.5.3.1).

**Inputs**

- Effective span: $L_{{eff}} = {L_mm:.0f}\,\text{{mm}}$
- Total service load: $w = g + q = {w_total:.2f}\,\text{{kN/m}}$
- Deflection constant (support condition): $k_2 = {k2_main:.5f}$
- Effective modulus: $E_{{c,eff}} = {Ec:.0f}\,\text{{MPa}}$
- Effective second moment: $I_{{ef}} = {Ief:,.3e}\,\text{{mm}}^4$

**Formula**

Short-term deflection due to total service load:

\\[
\\delta_{{st,total}} = k_2 \\dfrac{{w\, L_{{eff}}^4}}{{E_{{c,eff}}\, I_{{ef}}}}
\\]

**Substitution**

\\[
\\delta_{{st,total}}
= ({k2_main:.5f}) \times ({w_total:.2f})\,
  \\dfrac{{({L_mm:.0f})^4}}{{({Ec:.0f}) \times ({Ief:,.3e})}}
\\approx {delta_short_total:.2f}\,\text{{mm}}
\\]

**Result**

- Short-term deflection (total load):  
  $\\delta_{{st,total}} \approx {delta_short_total:.2f}\,\text{{mm}}$
- Deflection ratio:  
  $L/\\delta_{{st,total}} \approx {L_over_delta_short}$

_Ref: AS 3600:2018 Cl. 8.5.3.1 – deflection using effective stiffness $I_{{ef}}$._
"""
        calcbox(text)

    # TAB 3: Long-term
    with tab_long:
        st.subheader("Long-term deflection – AS 3600 Cl. 8.5.3.2")

        ratio_Asc_Ast = (Asc / Ast) if Ast > 0 else 0.0

        text = rf"""
**Purpose**

Determine the **additional long-term deflection** due to sustained loading
(creep + shrinkage) and the resulting **total deflection** to AS 3600 Cl. 8.5.3.2.

**Inputs**

- Sustained load:
  \\[
  w_{{sust}} = g + \\psi_s q = {w_sust:.2f}\,\text{{kN/m}}
  \\]
- Sustained factor: $\\psi_s = {psi_s:.2f}$
- Tension steel: $A_{{st}} = {Ast:.0f}\,\text{{mm}}^2$
- Compression steel: $A_{{sc}} = {Asc:.0f}\,\text{{mm}}^2$
- Steel ratio:
  \\[
  \\dfrac{{A_{{sc}}}}{{A_{{st}}}} = {ratio_Asc_Ast:.3f}
  \\]
- Creep/shrinkage multiplier: $k_{{cs}} = {kcs:.2f}$
- Other parameters as per short-term:
  $k_2 = {k2_main:.5f},\ L_{{eff}} = {L_mm:.0f}\,\text{{mm}},\
   E_{{c,eff}} = {Ec:.0f}\,\text{{MPa}},\
   I_{{ef}} = {Ief:,.3e}\,\text{{mm}}^4$

**Formula**

Short-term deflection due to **sustained load only**:

\\[
\\delta_{{st,sust}} = k_2 \\dfrac{{w_{{sust}} L_{{eff}}^4}}{{E_{{c,eff}} I_{{ef}}}}
\\]

Creep/shrinkage multiplier:

\\[
k_{{cs}} = \\max\\left[ 2 - 1.2 \\left(\\dfrac{{A_{{sc}}}}{{A_{{st}}}}\\right),\, 0.8 \\right]
\\]

Additional long-term deflection:

\\[
\\delta_{{LT,add}} = k_{{cs}} \\,\\delta_{{st,sust}}
\\]

Total deflection:

\\[
\\delta_{{total}} = \\delta_{{st,total}} + \\delta_{{LT,add}}
\\]

**Substitution**

Short-term sustained:

\\[
\\delta_{{st,sust}}
= ({k2_main:.5f}) \times ({w_sust:.2f})\,
  \\dfrac{{({L_mm:.0f})^4}}{{({Ec:.0f}) \times ({Ief:,.3e})}}
\\approx {delta_short_sust:.2f}\,\text{{mm}}
\\]

Additional long-term:

\\[
\\delta_{{LT,add}} = k_{{cs}} \\,\\delta_{{st,sust}}
= ({kcs:.2f}) \times ({delta_short_sust:.2f})
\\approx {delta_long_add:.2f}\,\text{{mm}}
\\]

Total:

\\[
\\delta_{{total}} = \\delta_{{st,total}} + \\delta_{{LT,add}}
= {delta_short_total:.2f} + {delta_long_add:.2f}
\\approx {delta_total:.2f}\,\text{{mm}}
\\]

**Result**

- Short-term sustained:  
  $\\delta_{{st,sust}} \approx {delta_short_sust:.2f}\,\text{{mm}}$
- Additional long-term:  
  $\\delta_{{LT,add}} \approx {delta_long_add:.2f}\,\text{{mm}}$  
  (ratio $\\approx {L_over_delta_long_add}$)
- Total deflection:  
  $\\delta_{{total}} \approx {delta_total:.2f}\,\text{{mm}}$  
  (ratio $\\approx {L_over_delta_total}$)

_Ref: AS 3600:2018 Cl. 8.5.3.2 – long-term deflection using $k_{{cs}}$ and sustained loads._
"""
        calcbox(text)

    # TAB 4: Span/depth deemed-to-conform
    with tab_span:
        st.subheader("Deemed-to-conform span-to-depth ratio – AS 3600 Cl. 8.5.4")

        span_text = rf"""
**Purpose**

Check whether the **span-to-depth ratio** $L_{{ef}}/d$ satisfies the
**deemed-to-conform** limit given in AS 3600:2018 Cl. 8.5.4, using the previously
calculated $I_{{ef}}$ (via $k_1$).

**Inputs**

- Effective span: $L_{{ef}} = {L_mm:.0f}\,\text{{mm}}$
- Effective depth: $d = {d:.1f}\,\text{{mm}}$  
  ⇒ current ratio:
  \\[
  \\dfrac{{L_{{ef}}}}{{d}} = {L_over_d:.1f}
  \\]
- Stiffness factor from Iₑf tab: $k_1 = {k1_span:.5f}$
- Deflection constant (support type): $k_2 = {k2_span:.5f}$
- Deflection limit:
  \\[
  \\left(\\dfrac{{\\Delta}}{{L_{{ef}}}}\\right)_{{limit}} = \\dfrac{{1}}{{{defl_limit_ratio:.0f}}}
  \\]
- Effective design load: $F_{{d,ef}} = {Fdef_kNm:.2f}\,\text{{kN/m}}$
- Effective modulus: $E_{{c,eff}} = {Ec:.0f}\,\text{{MPa}}$
- Effective flange width: $b_{{ef}} = {beff:.1f}\,\text{{mm}}$

**Formula**

Deemed-to-conform span-to-depth limit:

\\[
\\frac{{L_{{ef}}}}{{d}} \\le
\\left[
\\dfrac{{k_1 \\, (\\Delta/L_{{ef}}) \\, b_{{ef}} E_{{c,eff}}}}{{k_2 F_{{d,ef}}}}
\\right]^{{1/3}}
\\]

**Substitution**
"""

        if L_over_d_limit is not None:
            span_text += rf"""

Right-hand-side limit:

\\[
\\left(\\frac{{L_{{ef}}}}{{d}}\\right)_{{limit}}
=
\\left[
\\dfrac{{({k1_span:.5f}) \\times (1/{defl_limit_ratio:.0f}) \\times ({beff:.1f}) \\times ({Ec:.0f})}}
      {{({k2_span:.5f}) \\times ({Fdef_kNm:.2f})}}
\\right]^{{1/3}}
\\approx {L_over_d_limit:.1f}
\\]

**Result**

- Allowed ratio:
  \\[
  \\dfrac{{L_{{ef}}}}{{d}} \\le {L_over_d_limit:.1f}
  \\]
- Actual ratio:
  \\[
  \\dfrac{{L_{{ef}}}}{{d}} = {L_over_d:.1f}
  \\]

Conclusion: **{"✅ OK – deemed to conform" if L_over_d <= L_over_d_limit else "❌ NG – exceeds deemed limit"}**
"""
        else:
            span_text += r"""

No limit could be computed because \(F_{d,ef} \le 0\).

**Result**

- Span/depth deemed-to-conform check not applicable for the current inputs.
"""

        span_text += r"""

_Ref: AS 3600:2018 Cl. 8.5.4 – deemed-to-conform span-to-depth limits._
"""
        calcbox(span_text)

    # TAB 5: Flow chart
    with tab_flow:
        st.subheader("Flow chart – Deflection check to AS 3600")

        st.markdown(
            """
### Step 1 – Define section, materials & loads
- Geometry: \(L_{ef}, b_w, b_{ef}, d\)  
- Materials: \(f'_c, E_{c,eff}, A_{st}, A_{sc}\)  
- Loads: \(g, q, \\psi_s, F_{d,ef}\), deflection limit \(L/Δ\)  
- Define SLS load case on **Design / SFD-BMD** (UDL or point load)

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

    # TAB 6: Deflected shape
    with tab_shape:
        st.subheader("Deflected Shape (Illustrative – scaled to δ_total)")

        x = np.linspace(0.0, L_mm, 200)
        xi = x / L_mm
        # Simple parabolic shape scaled to δ_total
        y_long = -delta_total * 4.0 * xi * (1.0 - xi)

        fig, ax = plt.subplots()
        ax.plot(x, y_long)
        ax.set_xlabel("Span position x (mm)")
        ax.set_ylabel("Deflection (mm)")
        ax.axhline(0.0, linewidth=0.8)
        ax.grid(True)

        st.pyplot(fig)
