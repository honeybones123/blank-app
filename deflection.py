# deflection_page.py
import math
import numpy as np
import pandas as pd
import streamlit as st
import matplotlib.pyplot as plt

from state_and_helpers import (
    init_shared_session_state,
    get_param,
    get_sync_callbacks,
    update_results,  # kept for contract / future use
)
from widgets_helpers import (
    apply_global_widget_css,
    apply_calcbox_css,
    apply_step_summary_expander_css,
    number_row,
    page_divider,
    calcbox,
    label_with_hover,
    v2_number_input,
    v2_selectbox,
    v2_checkbox,
    v2_radio,
)
from step_ui import init_step_ui_state, render_expandable_step
from ui_seamless_steps import render_clickable_summary_table, bind_summary_clicks


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


def _render_readonly_value(label: str, value, unit: str, help_text: str | None = None):
    """
    Render a read-only value with label and optional help text.
    Uses the same styling as other read-only inputs.
    """
    col1, col2 = st.columns([1, 2])
    with col1:
        label_with_hover(label, help_text)
    with col2:
        if value is None:
            display_value = "—"
            color_style = "color: #999;"
        else:
            if isinstance(value, float):
                if unit == "mm":
                    display_value = f"{value:.0f} {unit}"
                elif unit == "mm²":
                    display_value = f"{value:.0f} {unit}"
                elif unit == "MPa":
                    display_value = f"{value:.2f} {unit}"
                else:
                    display_value = f"{value:.1f} {unit}"
            else:
                display_value = f"{value} {unit}" if unit else str(value)
            color_style = ""
        
        st.markdown(
            f"""
<div class="readonly-param" style="padding: 0.5rem 0.75rem; margin: 0;">
  <div class="readonly-param-value" style="font-size: 1rem; margin: 0; {color_style}">{display_value}</div>
</div>
""",
            unsafe_allow_html=True,
        )






# ------------------------------------------------------------
#  Deflection helper: map load case → closed-form δ formula
# ------------------------------------------------------------
def _deflection_from_sfd_case(
    case: str,
    L: float,
    w_eff: float | None,
    P_sls: float | None,
    E: float,
    I: float,
):
    """
    Returns (delta_max, latex_formula, location_text) for classic SLS load cases.

    Assumes:
      - L in your length unit
      - w_eff in force/length
      - P_sls in force
      - E, I consistent with your deflection units
    """
    delta_max = None
    formula = r"\text{No closed-form deflection linked for this case yet.}"
    location = "—"

    # 1. Simple beam – UDL over entire span
    if case == "Simple beam – UDL over entire span" and w_eff is not None:
        # δ_max = 5 w L^4 / (384 E I) at midspan
        delta_max = 5.0 * w_eff * L**4 / (384.0 * E * I)
        formula = (
            r"\delta_{\max} = \frac{5 w L^4}{384 E I}"
            r"\quad\text{(simply supported, full UDL, midspan)}"
        )
        location = "At midspan (x = L/2)"

    # 2. Simple beam – point load at centre
    elif case == "Simple beam – point load at centre" and P_sls is not None:
        # δ_max = P L^3 / (48 E I)
        delta_max = P_sls * L**3 / (48.0 * E * I)
        formula = (
            r"\delta_{\max} = \frac{P L^3}{48 E I}"
            r"\quad\text{(simply supported, centre point load)}"
        )
        location = "At midspan (x = L/2)"

    # 3. Cantilever – point load at free end
    elif case == "Cantilever – point load at free end" and P_sls is not None:
        # δ_max = P L^3 / (3 E I)
        delta_max = P_sls * L**3 / (3.0 * E * I)
        formula = (
            r"\delta_{\max} = \frac{P L^3}{3 E I}"
            r"\quad\text{(cantilever, end point load)}"
        )
        location = "At free end (x = L)"

    # 4. Cantilever – UDL over entire span
    elif case == "Cantilever – UDL over entire span" and w_eff is not None:
        # δ_max = w L^4 / (8 E I)
        delta_max = w_eff * L**4 / (8.0 * E * I)
        formula = (
            r"\delta_{\max} = \frac{w L^4}{8 E I}"
            r"\quad\text{(cantilever, full UDL)}"
        )
        location = "At free end (x = L)"

    # Other cases (partial UDL, eccentric point load, overhang etc.) can be added later.

    return delta_max, formula, location


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
    if L_m is None:
        return {"ok": False, "error": "Effective span is missing (L_m is None)."}
    try:
        L_m = float(L_m)
    except Exception:
        return {"ok": False, "error": "Effective span is not a valid number."}
    if L_m <= 0:
        return {"ok": False, "error": "Effective span must be > 0."}
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
    # Guard against None values to prevent TypeError
    beff = max(beff if beff is not None else 1.0, 1.0)
    bw = max(bw if bw is not None else 1.0, 1.0)
    d = max(d if d is not None else 1.0, 1.0)
    Ec = max(Ec if Ec is not None else 1.0, 1.0)
    ief = max(ief if ief is not None else 1.0, 1.0)
    fc = fc if fc is not None else 32.0
    Fdef_kNm = Fdef_kNm if Fdef_kNm is not None else 0.0
    defl_limit_ratio = defl_limit_ratio if defl_limit_ratio is not None else 250.0

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
    # MUST be first: guarantees shared keys exist and prevents fallback-default reseeding
    init_shared_session_state()
    sync_callbacks = get_sync_callbacks()
    
    # Handle cross-page navigation from Inputs page
    from jump_nav import get_jump_uid
    get_jump_uid()
    
    apply_global_widget_css()
    apply_calcbox_css()
    apply_step_summary_expander_css()
    sync_callbacks = get_sync_callbacks()  # not used yet but kept for contract
    
    # CSS for readonly-param styling (for linked values)
    st.markdown(
        """
<style>
/* Read-only linked-parameter chips */
.readonly-param {
  border-left: 4px solid #6c757d;
  background-color: rgba(108, 117, 125, 0.08);
  padding: 0.4rem 0.6rem;
  margin-bottom: 0.4rem;
  border-radius: 0 0.35rem 0.35rem 0;
  font-size: 0.85rem;
}
.readonly-param-value {
  font-weight: 500;
}
</style>
""",
        unsafe_allow_html=True,
    )
    
    # Initialize step UI state (matches Shear pattern)
    init_step_ui_state("deflection")

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
    a = get_param("a_m", None)  # Distance a for point loads
    
    # For display in calcbox
    g = get_param("g_udl_kNm_per_m", 0.0)
    q = get_param("q_udl_kNm_per_m", 0.0)
    psi_s = get_param("psi_udl", 0.4)
    G_point = get_param("G_point_kN", 0.0)
    Q_point = get_param("Q_point_kN", 0.0)
    
    # Determine effective load for deflection
    w_eff = w_sls if w_sls is not None else None

    st.markdown("### Design inputs")
    
    # Helper function for label-left / widget-right layout with hover help
    def _input_row(label: str, help_text: str | None, render_widget_fn):
        c1, c2 = st.columns([1.2, 1.0])
        with c1:
            label_with_hover(label, help_text)
        with c2:
            return render_widget_fn()
    
    # 3-column layout matching Shear pattern
    col_geom, col_mats, col_loads = st.columns(3, gap="large")
    
    # ---------- Column 1: Geometry ----------
    with col_geom:
        st.markdown("### Geometry")
        L_seed_mm = _seed_from_param("L", 6000.0)
        L_eff = _input_row(
            "Effective span Lₑf (m)",
            "Effective span length for deflection calculations.",
            lambda: v2_number_input(
                label="",
                key="defl_L_eff",
                default=L_seed_mm / 1000.0,
                step=0.1,
                label_visibility="collapsed",
                on_change=sync_callbacks["defl_L_eff"],
            ),
        )

        support_type = _input_row(
            "Support condition (k₂)",
            (
                "Support condition determines the deflection coefficient k₂\n"
                "used in AS 3600 deflection calculations.\n\n"
                "k₂ is a code-defined coefficient that accounts for\n"
                "restraint and load distribution effects.\n\n"
                "It is not user-editable."
            ),
            lambda: v2_selectbox(
                label="",
                key="defl_support_type",
                options=["Simply supported", "Continuous – end span", "Continuous – interior span"],
                default_index=0,
                label_visibility="collapsed",
                on_change=sync_callbacks["defl_support_type"],
            ),
        )

        bw_seed = _seed_from_param("b", 300.0)
        bw = _input_row(
            "Web / stem width b_w (mm)",
            "Web or stem width of the section.",
            lambda: v2_number_input(
                label="",
                key="defl_bw",
                default=bw_seed,
                step=10.0,
                label_visibility="collapsed",
                on_change=sync_callbacks["defl_bw"],
            ),
        )

        beff = _input_row(
            "Effective flange width bₑf (mm)",
            "Effective flange width for deflection calculations.",
            lambda: v2_number_input(
                label="",
                key="defl_beff",
                default=bw_seed,
                step=10.0,
                label_visibility="collapsed",
                on_change=sync_callbacks["defl_beff"],
            ),
        )

        # Read-only: effective depth (linked from shared state)
        d = _seed_from_param("d", 550.0)
        _render_readonly_value(
            "Effective depth d (mm)",
            d,
            "mm",
            "Linked from shared geometry. Edit on Inputs page.",
        )
    
    # ---------- Column 2: Materials ----------
    with col_mats:
        st.markdown("### Materials")
        
        fc_seed = _seed_from_param("fc", 32.0)
        fc = _input_row(
            "Concrete strength f'c (MPa)",
            "Concrete compressive strength.",
            lambda: v2_number_input(
                label="",
                key="defl_fc",
                default=fc_seed,
                step=1.0,
                label_visibility="collapsed",
                on_change=sync_callbacks["defl_fc"],
            ),
        )

        Ec_seed = _seed_from_param("Ec", 28000.0)
        Ec = _input_row(
            "Eceff (MPa)",
            "Effective concrete modulus for deflection calculations.",
            lambda: v2_number_input(
                label="",
                key="defl_Ec",
                default=Ec_seed,
                step=500.0,
                label_visibility="collapsed",
                on_change=sync_callbacks["defl_Ec"],
            ),
        )

        # Read-only: tension reinforcement area (linked from shared state)
        Ast = _seed_from_param("Ast_bot", 2010.0)
        _render_readonly_value(
            "Tension reinforcement area A_st (mm²)",
            Ast,
            "mm²",
            "Linked from shared reinforcement. Edit on Inputs page.",
        )

        # Read-only: compression reinforcement area (linked from shared state)
        Asc = _seed_from_param("Asc", 0.0)
        _render_readonly_value(
            "Compression reinforcement A_sc (mm²)",
            Asc,
            "mm²",
            "Linked from shared reinforcement. Edit on Inputs page.",
        )
    
    # ---------- Column 3: Serviceability ----------
    with col_loads:
        st.markdown("### Serviceability")
        
        defl_limit_ratio = _input_row(
            "Deflection limit L/Δ (e.g. 250)",
            "Maximum allowed deflection ratio (e.g., 250 for L/250 limit).",
            lambda: v2_number_input(
                label="",
                key="defl_limit_ratio",
                default=250.0,
                step=10.0,
                label_visibility="collapsed",
                on_change=sync_callbacks["defl_limit_ratio"],
            ),
        )
        
        Fdef_kNm = _input_row(
            "Effective design load F_d,ef (kN/m)",
            (
                "Effective design load for span-to-depth check only.\n\n"
                "Used to determine the allowable L/d limit per AS 3600 Cl. 8.5.4.\n\n"
                "Does NOT affect short- or long-term deflection calculations."
            ),
            lambda: v2_number_input(
                label="",
                key="defl_Fdef",
                default=12.0,
                step=0.5,
                label_visibility="collapsed",
                on_change=sync_callbacks["defl_Fdef"],
            ),
        )

    # --------------------------------------------------------
    # SINGLE COMPUTED VALUES BLOCK (compute once, use everywhere)
    # --------------------------------------------------------
    # Compute Ief_selected once based on checkbox state
    use_simplified_ief = st.session_state.get("defl_use_simplified_ief", True)
    try:
        if use_simplified_ief:
            Ief_selected, beta, p, p_lim, Ief_max, k1_from_ief = calc_ief_simplified(
                fc=fc,
                beff=beff,
                bw=bw,
                d=d,
                Ast=Ast,
            )
        else:
            Ief_selected = st.session_state.get("defl_Ief_user", 1.0e11)
            beta = beff / bw if (bw is not None and bw > 0) else 1.0
            p = Ast / (beff * d) if (beff is not None and d is not None and beff * d > 0) else 0.0
            p_lim = 0.0
            Ief_max = Ief_selected
            k1_from_ief = Ief_selected / (beff * (d ** 3)) if (beff is not None and d is not None and beff * d > 0) else 0.0
    except Exception:
        # Fallback if computation fails
        Ief_selected = 1.0e11
        beta = beff / bw if (bw is not None and bw > 0) else 1.0
        p = Ast / (beff * d) if (beff is not None and d is not None and beff * d > 0) else 0.0
        p_lim = 0.0
        Ief_max = Ief_selected
        k1_from_ief = Ief_selected / (beff * (d ** 3)) if (beff is not None and d is not None and beff * d > 0) else 0.0

    # --- hard guard: never let L_m be None (prevents session-killing exception) ---
    L_eff_m = get_param("defl_L_eff")

    if L_eff_m is None:
        # fall back to global span L (mm) -> m
        L_eff_m = float(get_param("L")) / 1000.0

    # still guard: if someone clears it to 0/negative, keep app alive (no crash)
    if L_eff_m <= 0:
        L_eff_m = 0.1

    # Main deflection calculations using Ief_selected
    results = calc_deflection_as3600(
        L_m=L_eff_m,
        Ec=Ec,
        Ief=Ief_selected,
        g_kNm=g,
        q_kNm=q,
        psi_s=psi_s,
        support_type=support_type,
        Ast=Ast,
        Asc=Asc,
    )

    # Handle error return from calc_deflection_as3600
    if results is None or (isinstance(results, dict) and results.get("ok") is False):
        error_msg = results.get("error", "Deflection calculation failed: invalid span length.") if isinstance(results, dict) else "Deflection calculation failed: invalid span length."
        st.warning(error_msg)
        return

    L_mm = results["L_mm"]
    delta_short_total = results["delta_short_total"]
    delta_short_sust = results["delta_short_sust"]
    delta_long_add = results["delta_long_add"]
    delta_total = results["delta_total"]
    kcs = results["kcs"]
    w_total = results["w_total"]
    w_sust = results["w_sust"]
    k2 = results["k2"]

    # --------------------------------------------------------
    # Deflected Shape (moved up, right after inputs)
    # --------------------------------------------------------
    page_divider()
    st.caption("Deflected shape (illustrative, scaled to total deflection)")
    
    if delta_total is None:
        st.info("Provide inputs to view deflected shape.")
    else:
        x = np.linspace(0.0, L_mm, 200)
        xi = x / L_mm
        y_long = -delta_total * 4.0 * xi * (1.0 - xi)

        fig, ax = plt.subplots(figsize=(8, 2.8))
        ax.plot(x, y_long)
        ax.set_xlabel("Span position x (mm)")
        ax.set_ylabel("Deflection (mm)")
        ax.axhline(0.0, linewidth=0.8)
        ax.grid(True)
        ax.set_aspect("auto")
        plt.tight_layout()

        st.pyplot(fig)
    
    page_divider()

    L_over_delta_short = format_L_over_delta(delta_short_total, L_mm)
    L_over_delta_long_add = format_L_over_delta(delta_long_add, L_mm)
    L_over_delta_total = format_L_over_delta(delta_total, L_mm)

    L_over_d = (L_mm / d) if d > 0 else 0.0
    L_over_d_limit, k1_span, k2_span = calc_span_depth_limit(
        ief=Ief_selected,
        beff=beff,
        bw=bw,
        d=d,
        fc=fc,
        Ec=Ec,
        Fdef_kNm=Fdef_kNm,
        support_type=support_type,
        defl_limit_ratio=defl_limit_ratio,
    )

    # Closed-form deflection (with unit fix: convert L to mm, P to N)
    delta_max = None
    formula_latex = None
    delta_loc = None
    if (
        load_case is not None
        and L_sfd is not None
        and Ec is not None
        and Ief_selected is not None
        and L_sfd > 0
        and Ec > 0
        and Ief_selected > 0
    ):
        # Fix units: L in mm, w in N/mm (same as kN/m numerically), P in N, E in MPa (N/mm²), I in mm⁴
        L_mm_sfd = float(L_sfd) * 1000.0  # m → mm
        w_eff_n_per_mm = w_eff if w_eff is not None else None  # kN/m == N/mm numerically
        P_sls_n = P_sls * 1000.0 if P_sls is not None else None  # kN → N
        E_mpa = float(Ec)  # MPa == N/mm²
        I_mm4 = float(Ief_selected)  # mm⁴
        
        delta_max, formula_latex, delta_loc = _deflection_from_sfd_case(
            case=load_case,
            L=L_mm_sfd,
            w_eff=w_eff_n_per_mm,
            P_sls=P_sls_n,
            E=E_mpa,
            I=I_mm4,
        )
        # delta_max is now in mm
    
    # --------------------------------------------------------
    # Tabs in agreed order (Ief, short-term, long-term, span/depth)
    # --------------------------------------------------------
    tab_ief, tab_short, tab_long, tab_span = st.tabs(
        [
            "Iₑf details",
            "Short-term deflection",
            "Long-term deflection",
            "Span/depth check",
        ]
    )

    # ---------- TAB 1: Ief details (display-only, uses already computed Ief_selected) ----------
    with tab_ief:
        st.subheader("Effective stiffness (Iₑf) – input choice")

        use_simplified_ief_checkbox = v2_checkbox(
            label="Use simplified reinforced-member Iₑf (AS 3600 Cl. 8.5.3.1(2),(3))",
            key="defl_use_simplified_ief",
            default=use_simplified_ief,
            on_change=sync_callbacks["defl_use_simplified_ief"],
        )

        # Display-only: show the already computed Ief_selected
        if not use_simplified_ief_checkbox:
            Ief_user_display = v2_number_input(
                label="User-specified Iₑf (mm⁴)",
                key="defl_Ief_user",
                default=Ief_selected,
                step=1.0e10,
                format="%.3e",
            )
            # Note: Changing this will require rerun to update calculations

        # Build 2-line summary for Ief step
        ief_method = "Simplified" if use_simplified_ief_checkbox else "User input"
        # Guard against None values for formatting
        Ief_selected_display = Ief_selected if Ief_selected is not None else 1.0e11
        ief_summary = (
            f"**Effective stiffness $I_{{ef}}$ (AS 3600 Cl. 8.5.3.1)**  \n"
            f"$I_{{ef}} = {Ief_selected_display:,.3e}\\,\\mathrm{{mm}}^4$  ({ief_method.lower()} reinforced-member option)"
        )
        
        # Guard against None values before formatting
        fc_display = fc if fc is not None else 32.0
        bw_display = bw if bw is not None else 300.0
        beff_display = beff if beff is not None else 300.0
        d_display = d if d is not None else 550.0
        Ast_display = Ast if Ast is not None else 2010.0
        beta_display = beta if beta is not None else 1.0
        p_display = p if p is not None else 0.0
        p_lim_display = p_lim if p_lim is not None else 0.0
        Ief_max_display = Ief_max if Ief_max is not None else 1.0e11
        k1_from_ief_display = k1_from_ief if k1_from_ief is not None else 0.0
        
        ief_calc_md = rf"""
*Purpose: Compute the effective second moment of area $I_{{ef}}$ for a reinforced concrete member using the simplified expressions in AS 3600:2018 Cl. 8.5.3.1(2) and (3). This cracked stiffness is then used in all deflection checks.*

**Inputs:**

- Concrete strength: $f'_c = {fc_display:.1f}\,\text{{MPa}}$
- Web / stem width: $b_w = {bw_display:.1f}\,\text{{mm}}$
- Effective flange width: $b_{{ef}} = {beff_display:.1f}\,\text{{mm}}$
- Effective depth: $d = {d_display:.1f}\,\text{{mm}}$
- Tension steel area: $A_{{st}} = {Ast_display:.1f}\,\text{{mm}}^2$

Derived section parameters:

- Width ratio: $\beta = \dfrac{{b_{{ef}}}}{{b_w}} = {beta_display:.3f}$
- Reinforcement ratio: $p = \dfrac{{A_{{st}}}}{{b_{{ef}} d}} = {p_display:.5f}$
- Limit ratio: $p_{{lim}} = {p_lim_display:.5f}$

---

**Formula:**

For reinforced members (AS 3600:2018 Cl. 8.5.3.1):

If $p \ge p_{{lim}}$:

$$
I_{{ef}} = \left[(5 - 0.04 f'_c)\, p + 0.002 \right]\, b_{{ef}} d^3
$$

If $p < p_{{lim}}$:

$$
I_{{ef}} = \left[0.055 (f'_c)^{{1/3}} / \beta^{{2/3}} - 50 p \right]\, b_{{ef}} d^3
$$

Capped by:

$$
I_{{ef}} \le I_{{ef,max}} = {Ief_max_display:,.3e}\,\text{{mm}}^4
$$

and

$$
k_1 = \dfrac{{I_{{ef}}}}{{b_{{ef}} d^3}}
$$

---

**Substitution:**

Using the current inputs:

- Computed $I_{{ef}} \approx {Ief_selected_display:,.3e}\,\text{{mm}}^4$
- $I_{{ef,max}} = {Ief_max_display:,.3e}\,\text{{mm}}^4$
- $k_1 = \dfrac{{I_{{ef}}}}{{b_{{ef}} d^3}} \approx {k1_from_ief_display:.5f}$

---

**Result:**

- $I_{{ef}} = {Ief_selected:,.3e}\,\text{{mm}}^4$
- $k_1 = {k1_from_ief:.5f}$
- (cap) $I_{{ef,max}} = {Ief_max:,.3e}\,\text{{mm}}^4$

_Ref: AS 3600:2018 Cl. 8.5.3.1(2) & (3) – simplified $I_{{ef}}$ for reinforced members._
"""
        
        render_expandable_step(
            page_key="deflection",
            step_id="defl_ief",
            title="Effective stiffness ($I_{ef}$) – input choice",
            summary_md=ief_summary,
            status_kind=None,
            calc_md=ief_calc_md,
            diagram_render_fn=None,
            info_render_fn=None,
        )

    # --------------------------------------------------------
    # TOP SUMMARY TABLE (clickable, matching Shear/Bending)
    # --------------------------------------------------------
    with summary_placeholder.container():
        st.markdown("## Summary")

        limit_delta_mm = L_mm / defl_limit_ratio if defl_limit_ratio > 0 else None
        
        # Build summary rows in format expected by render_clickable_summary_table
        ROWS = []
        
        # Map check names to step IDs (for clickable navigation)
        check_to_step_id = {
            "Short-term deflection (total load)": "defl_short",
            "Additional long-term deflection": "defl_long",
            "Total deflection (short + long-term)": "defl_long",
            "Span-to-depth ratio Lₑf/d": "defl_span_depth",
        }
        
        # 1) Short-term total
        if limit_delta_mm and limit_delta_mm > 0:
            util_short = delta_short_total / limit_delta_mm
            status_short = "OK" if util_short <= 1.0 else "NG"
            limit_str = f"{limit_delta_mm:.2f} mm (L/{defl_limit_ratio:.0f})"
            ok_short = util_short <= 1.0 if util_short is not None else None
        else:
            util_short = None
            status_short = "—"
            limit_str = "—"
            ok_short = None

        ROWS.append({
            "uid": check_to_step_id["Short-term deflection (total load)"],
            "title": "Short-term deflection (total load)",
            "value": f"{delta_short_total:.2f} mm ({L_over_delta_short})",
            "limit": limit_str,
            "util": f"{util_short:.2f}" if util_short is not None else "—",
            "status": status_short,
            "ok": ok_short,
            "tab": "Short-term deflection",
            "anchor_id": "defl_tab_short",
            "is_primary": True,
        })

        # 2) Long-term additional
        if limit_delta_mm and limit_delta_mm > 0:
            util_long = delta_long_add / limit_delta_mm
            status_long = "OK" if util_long <= 1.0 else "NG"
            ok_long = util_long <= 1.0 if util_long is not None else None
        else:
            util_long = None
            status_long = "—"
            ok_long = None

        ROWS.append({
            "uid": check_to_step_id["Additional long-term deflection"],
            "title": "Additional long-term deflection",
            "value": f"{delta_long_add:.2f} mm ({L_over_delta_long_add})",
            "limit": limit_str,
            "util": f"{util_long:.2f}" if util_long is not None else "—",
            "status": status_long,
            "ok": ok_long,
            "tab": "Long-term deflection",
            "anchor_id": "defl_tab_long_add",
            "is_primary": False,
        })

        # 3) Total
        if limit_delta_mm and limit_delta_mm > 0:
            util_total = delta_total / limit_delta_mm
            status_total = "OK" if util_total <= 1.0 else "NG"
            ok_total = util_total <= 1.0 if util_total is not None else None
        else:
            util_total = None
            status_total = "—"
            ok_total = None

        ROWS.append({
            "uid": check_to_step_id["Total deflection (short + long-term)"],
            "title": "Total deflection (short + long-term)",
            "value": f"{delta_total:.2f} mm ({L_over_delta_total})",
            "limit": limit_str,
            "util": f"{util_total:.2f}" if util_total is not None else "—",
            "status": status_total,
            "ok": ok_total,
            "tab": "Long-term deflection",
            "anchor_id": "defl_tab_long_total",
            "is_primary": True,
        })

        # 4) Span/depth
        if L_over_d_limit is not None and L_over_d_limit > 0:
            util_span = L_over_d / L_over_d_limit
            status_span = "OK" if util_span <= 1.0 else "NG"
            limit_span_str = f"{L_over_d_limit:.1f}"
            ok_span = util_span <= 1.0 if util_span is not None else None
        else:
            util_span = None
            status_span = "—"
            limit_span_str = "—"
            ok_span = None

        ROWS.append({
            "uid": check_to_step_id["Span-to-depth ratio Lₑf/d"],
            "title": "Span-to-depth ratio Lₑf/d",
            "value": f"{L_over_d:.1f}",
            "limit": limit_span_str,
            "util": f"{util_span:.2f}" if util_span is not None else "—",
            "status": status_span,
            "ok": ok_span,
            "tab": "Span/depth check",
            "anchor_id": "defl_tab_span",
            "is_primary": False,
        })
        
        render_clickable_summary_table(ROWS, key_prefix="defl_summary")
        bind_summary_clicks()
        
        page_divider()

    # --------------------------------------------------------
    # TABS (one calcbox per tab, no duplicates)
    # --------------------------------------------------------
    
    # TAB 2: Short-term deflection
    with tab_short:
        st.subheader("Short-term deflection – AS 3600 Cl. 8.5.3.1")
        
        # Short-term deflection step
        limit_delta_mm = L_mm / defl_limit_ratio if defl_limit_ratio > 0 else None
        util_short = delta_short_total / limit_delta_mm if limit_delta_mm and limit_delta_mm > 0 else None
        short_status = "pass" if (util_short is not None and util_short <= 1.0) else "fail" if util_short is not None else None
        
        short_summary = (
            f"**Short-term deflection (Cl. 8.5.3.1)**  \n"
            f"$\delta_{{st,total}} = {delta_short_total:.2f}\\,\\mathrm{{mm}}$ ({L_over_delta_short}) | "
            f"Result: {'PASS' if short_status == 'pass' else 'FAIL' if short_status == 'fail' else '—'}"
        )
        
        short_calc_md = rf"""
*Purpose: Determine the short-term midspan deflection under total service load $w = g + q$ using the effective stiffness $I_{{ef}}$ from the Iₑf tab (AS 3600 Cl. 8.5.3.1).*

**Inputs:**

- Effective span: $L_{{eff}} = {L_mm:.0f}\,\text{{mm}}$
- Total service load: $w = g + q = {w_total:.2f}\,\text{{kN/m}}$
- Deflection coefficient (support condition):  
  $k_2 = {k2:.5f}$  
  *(Code-defined coefficient based on support condition per AS 3600 Cl. 8.5.3.1)*
- Effective modulus: $E_{{c,eff}} = {Ec:.0f}\,\text{{MPa}}$
- Effective second moment: $I_{{ef}} = {Ief_selected:,.3e}\,\text{{mm}}^4$

---

**Formula:**

Short-term deflection due to total service load:

$$
\delta_{{st,total}} = k_2 \dfrac{{w\, L_{{eff}}^4}}{{E_{{c,eff}}\, I_{{ef}}}}
$$

where $k_2$ is the deflection coefficient determined by support condition (AS 3600 Cl. 8.5.3.1).

---

**Substitution:**

$$
\delta_{{st,total}}
= ({k2:.5f}) \times ({w_total:.2f})\,
  \dfrac{{({L_mm:.0f})^4}}{{({Ec:.0f}) \times ({Ief_selected:,.3e})}}
\approx {delta_short_total:.2f}\,\text{{mm}}
$$

---

**Result:**

- Short-term deflection (total load):  
  $\delta_{{st,total}} \approx {delta_short_total:.2f}\,\text{{mm}}$
- Deflection ratio:  
  $L/\delta_{{st,total}} \approx {L_over_delta_short}$
{f'- Utilisation: {util_short:.2f} → {"✓ PASS" if short_status == "pass" else "✗ FAIL"}' if util_short is not None else ''}

_Ref: AS 3600:2018 Cl. 8.5.3.1 – deflection using effective stiffness $I_{{ef}}$._
"""
        
        render_expandable_step(
            page_key="deflection",
            step_id="defl_short",
            title="Short-term deflection (Cl. 8.5.3.1)",
            summary_md=short_summary,
            status_kind=short_status,
            calc_md=short_calc_md,
            diagram_render_fn=None,
            info_render_fn=None,
        )

    # TAB 3: Long-term deflection
    with tab_long:
        st.subheader("Long-term deflection – AS 3600 Cl. 8.5.3.2")
        
        # Long-term deflection step
        limit_delta_mm = L_mm / defl_limit_ratio if defl_limit_ratio > 0 else None
        util_long = delta_long_add / limit_delta_mm if limit_delta_mm and limit_delta_mm > 0 else None
        util_total = delta_total / limit_delta_mm if limit_delta_mm and limit_delta_mm > 0 else None
        long_status = "pass" if (util_total is not None and util_total <= 1.0) else "fail" if util_total is not None else None
        
        ratio_Asc_Ast = (Asc / Ast) if Ast > 0 else 0.0
        
        long_summary = (
            f"**Long-term deflection (Cl. 8.5.3.2)**  \n"
            f"$\delta_{{total}} = {delta_total:.2f}\\,\\mathrm{{mm}}$ ({L_over_delta_total}) | "
            f"Includes: Long-term deflection with $k_{{cs}}$; Result: {'PASS' if long_status == 'pass' else 'FAIL' if long_status == 'fail' else '—'}"
        )
        
        long_calc_md = rf"""
*Purpose: Determine the additional long-term deflection due to sustained loading (creep + shrinkage) and the resulting total deflection to AS 3600 Cl. 8.5.3.2.*

**Inputs:**

- Sustained load:
  $$
  w_{{sust}} = g + \psi_s q = {w_sust:.2f}\,\text{{kN/m}}
  $$
- Sustained factor: $\psi_s = {psi_s:.2f}$
- Tension steel: $A_{{st}} = {Ast:.0f}\,\text{{mm}}^2$
- Compression steel: $A_{{sc}} = {Asc:.0f}\,\text{{mm}}^2$
- Steel ratio:
  $$
  \dfrac{{A_{{sc}}}}{{A_{{st}}}} = {ratio_Asc_Ast:.3f}
  $$
- Creep/shrinkage multiplier: $k_{{cs}} = {kcs:.2f}$
- Other parameters as per short-term:
  $k_2 = {k2:.5f},\ L_{{eff}} = {L_mm:.0f}\,\text{{mm}},\
   E_{{c,eff}} = {Ec:.0f}\,\text{{MPa}},\
   I_{{ef}} = {Ief_selected:,.3e}\,\text{{mm}}^4$

---

**Formula:**

Short-term deflection due to **sustained load only**:

$$
\delta_{{st,sust}} = k_2 \dfrac{{w_{{sust}} L_{{eff}}^4}}{{E_{{c,eff}} I_{{ef}}}}
$$

Creep/shrinkage multiplier:

$$
k_{{cs}} = \max\left[ 2 - 1.2 \left(\dfrac{{A_{{sc}}}}{{A_{{st}}}}\right),\, 0.8 \right]
$$

Additional long-term deflection:

$$
\delta_{{LT,add}} = k_{{cs}} \,\delta_{{st,sust}}
$$

Total deflection:

$$
\delta_{{total}} = \delta_{{st,total}} + \delta_{{LT,add}}
$$

---

**Substitution:**

Short-term sustained:

$$
\delta_{{st,sust}}
= ({k2:.5f}) \times ({w_sust:.2f})\,
  \dfrac{{({L_mm:.0f})^4}}{{({Ec:.0f}) \times ({Ief_selected:,.3e})}}
\approx {delta_short_sust:.2f}\,\text{{mm}}
$$

Additional long-term:

$$
\delta_{{LT,add}} = k_{{cs}} \,\delta_{{st,sust}}
= ({kcs:.2f}) \times ({delta_short_sust:.2f})
\approx {delta_long_add:.2f}\,\text{{mm}}
$$

Total:

$$
\delta_{{total}} = \delta_{{st,total}} + \delta_{{LT,add}}
= {delta_short_total:.2f} + {delta_long_add:.2f}
\approx {delta_total:.2f}\,\text{{mm}}
$$

---

**Result:**

- Short-term sustained:  
  $\delta_{{st,sust}} \approx {delta_short_sust:.2f}\,\text{{mm}}$
- Additional long-term:  
  $\delta_{{LT,add}} \approx {delta_long_add:.2f}\,\text{{mm}}$  
  (ratio $\approx {L_over_delta_long_add}$)
- Total deflection:  
  $\delta_{{total}} \approx {delta_total:.2f}\,\text{{mm}}$  
  (ratio $\approx {L_over_delta_total}$)
{f'- Utilisation: {util_total:.2f} → {"✓ PASS" if long_status == "pass" else "✗ FAIL"}' if util_total is not None else ''}

_Ref: AS 3600:2018 Cl. 8.5.3.2 – long-term deflection using $k_{{cs}}$ and sustained loads._
"""
        
        render_expandable_step(
            page_key="deflection",
            step_id="defl_long",
            title="Long-term deflection (Cl. 8.5.3.2)",
            summary_md=long_summary,
            status_kind=long_status,
            calc_md=long_calc_md,
            diagram_render_fn=None,
            info_render_fn=None,
        )

    # TAB 4: Span/depth deemed-to-conform
    with tab_span:
        st.subheader("Deemed-to-conform span-to-depth ratio – AS 3600 Cl. 8.5.4")
        
        # Span/depth check step
        util_span = L_over_d / L_over_d_limit if L_over_d_limit is not None and L_over_d_limit > 0 else None
        span_defl_status = None
        if L_over_d_limit is not None and L_over_d_limit > 0 and L_over_d > 0:
            span_passes = L_over_d <= L_over_d_limit
            span_defl_status = "pass" if span_passes else "fail"
        
        limit_text = f"{L_over_d_limit:.1f}" if L_over_d_limit is not None else "—"
        
        # Guard against None values before formatting
        L_mm_display = L_mm if L_mm is not None else 6000.0
        d_display_span = d if d is not None else 550.0
        L_over_d_display = L_over_d if L_over_d is not None else 0.0
        k1_span_display = k1_span if k1_span is not None else 0.0
        k2_span_display = k2_span if k2_span is not None else 0.013
        defl_limit_ratio_display = defl_limit_ratio if defl_limit_ratio is not None else 250.0
        Fdef_kNm_display = Fdef_kNm if Fdef_kNm is not None else 12.0
        Ec_display_span = Ec if Ec is not None else 28000.0
        beff_display_span = beff if beff is not None else 300.0
        
        span_summary = (
            f"**Span/depth deemed-to-conform check (Cl. 8.5.4)**  \n"
            f"$L_{{ef}}/d = {L_over_d_display:.1f}$ vs limit = {limit_text} | "
            f"Result: {'PASS' if span_defl_status == 'pass' else 'FAIL' if span_defl_status == 'fail' else '—'}"
        )
        
        span_calc_md = rf"""
*Purpose: Check whether the span-to-depth ratio $L_{{ef}}/d$ satisfies the deemed-to-conform limit given in AS 3600:2018 Cl. 8.5.4, using the previously calculated $I_{{ef}}$ (via $k_1$).*

**Inputs:**

- Effective span: $L_{{ef}} = {L_mm_display:.0f}\,\text{{mm}}$
- Effective depth: $d = {d_display_span:.1f}\,\text{{mm}}$  
  ⇒ current ratio:
  $$
  \dfrac{{L_{{ef}}}}{{d}} = {L_over_d_display:.1f}
  $$
- Stiffness factor from Iₑf tab: $k_1 = {k1_span_display:.5f}$
- Deflection constant (support type): $k_2 = {k2_span_display:.5f}$
- Deflection limit:
  $$
  \left(\dfrac{{\Delta}}{{L_{{ef}}}}\right)_{{limit}} = \dfrac{{1}}{{{defl_limit_ratio_display:.0f}}}
  $$
- Effective design load: $F_{{d,ef}} = {Fdef_kNm_display:.2f}\,\text{{kN/m}}$
- Effective modulus: $E_{{c,eff}} = {Ec_display_span:.0f}\,\text{{MPa}}$
- Effective flange width: $b_{{ef}} = {beff_display_span:.1f}\,\text{{mm}}$

---

**Formula:**

Deemed-to-conform span-to-depth limit:

$$
\frac{{L_{{ef}}}}{{d}} \le
\left[
\dfrac{{k_1 \, (\Delta/L_{{ef}}) \, b_{{ef}} E_{{c,eff}}}}{{k_2 F_{{d,ef}}}}
\right]^{{1/3}}
$$

---

**Substitution:**
"""

        if L_over_d_limit is not None:
            span_calc_md += rf"""

Right-hand-side limit:

$$
\left(\frac{{L_{{ef}}}}{{d}}\right)_{{limit}}
=
\left[
\dfrac{{({k1_span_display:.5f}) \times (1/{defl_limit_ratio_display:.0f}) \times ({beff_display_span:.1f}) \times ({Ec_display_span:.0f})}}
      {{({k2_span_display:.5f}) \times ({Fdef_kNm_display:.2f})}}
\right]^{{1/3}}
\approx {L_over_d_limit:.1f}
$$

---

**Result:**

- Allowed ratio:
  $$
  \dfrac{{L_{{ef}}}}{{d}} \le {L_over_d_limit:.1f}
  $$
- Actual ratio:
  $$
  \dfrac{{L_{{ef}}}}{{d}} = {L_over_d:.1f}
  $$

Conclusion: **{"✅ OK – deemed to conform" if span_defl_status == "pass" else "❌ NG – exceeds deemed limit"}**
"""
        else:
            span_calc_md += r"""

No limit could be computed because $F_{d,ef} \le 0$.

---

**Result:**

- Span/depth deemed-to-conform check not applicable for the current inputs.
"""

        span_calc_md += r"""

_Ref: AS 3600:2018 Cl. 8.5.4 – deemed-to-conform span-to-depth limits._
"""
        
        render_expandable_step(
            page_key="deflection",
            step_id="defl_span_depth",
            title="Span/depth deemed-to-conform check (Cl. 8.5.4)",
            summary_md=span_summary,
            status_kind=span_defl_status,
            calc_md=span_calc_md,
            diagram_render_fn=None,
            info_render_fn=None,
        )

    
    # Handle scroll after all content is rendered (for cross-page navigation from Inputs)
    from jump_nav import scroll_to_jump_after_render
    scroll_to_jump_after_render()