# bending_page.py
# ============================
# BENDING PAGE
# ============================

import math
import numpy as np
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
import plotly.graph_objects as go

from state_and_helpers import get_sync_callbacks, get_param, update_results
from widgets_helpers import apply_global_widget_css, apply_calcbox_css, number_row, show_reo_message
from bending_core import _fmt, _compute_bending_capacity, _stress_strain_state
from bending_diagrams import (
    _plot_stress_strain_profiles,
    _plot_material_stress_strain_curves,
)
from bending_tabs import render_uls_tab, render_min_strength_tab, render_sls_tab


@st.cache_resource
def _build_beam_3d_figure_pure(b, D, L, Mu_star, phi_Mu_cap, c, strain_state, 
                                reo_layout, cover_bot, cover_top, 
                                cover_side, rowgap_bot, rowgap_top, lig_d, lig_legs, s_lig):
    """
    Pure function version of 3D beam figure generation.
    All inputs must be passed as arguments (no get_param calls).
    
    Args:
        reo_layout: Pre-computed reinforcement layout dict from compute_longitudinal_reo_layout()
    
    3D visualisation:
      - Concrete prism
      - Longitudinal reo with consistent cover (matched to Inputs page intent)
      - Simple stirrups
      - Neutral axis plane
    """

    # ---------- Basic sanity checks ----------
    try:
        vals = [b, D, L, Mu_star, phi_Mu_cap, c]
        if any(v is None for v in vals):
            return None
        b = float(b)
        D = float(D)
        L = float(L)
        Mu_star = float(Mu_star)
        phi_Mu_cap = float(phi_Mu_cap)
        c = float(c)
        if any(math.isnan(v) for v in (b, D, L, Mu_star, phi_Mu_cap, c)):
            return None
    except Exception:
        return None

    if phi_Mu_cap <= 0.0 or D <= 0.0 or b <= 0.0 or L <= 0.0:
        return None

    # ---------- Curvature + NA depth (state-dependent) ----------
    eps_cu = 0.003
    phi_u = eps_cu / max(c, 1e-9)

    # base utilisation
    base_r = Mu_star / phi_Mu_cap if phi_Mu_cap > 0 else 0.0
    base_r = float(max(0.0, min(1.0, base_r)))

    # scale by state (robust to extended labels like "ULS – Parabolic")
    state_low = (strain_state or "").lower()
    if state_low.startswith("uls"):
        r = base_r
    elif state_low.startswith("sls"):
        r = 0.6 * base_r
    else:  # "Uncracked" / anything else
        r = 0.0

    c0 = D / 2.0  # uncracked NA
    if r <= 0.0:
        phi = 0.0
        c_now = c0
    else:
        phi = r * phi_u
        c_now = (1.0 - r) * c0 + r * c

    # Note: phi and c_now are calculated but not stored in session_state here
    # (session_state modifications are done in the wrapper function)

    traces: list[go.BaseTraceType] = []

    # =======================================================
    #  Concrete prism
    # =======================================================
    vx = np.array([0, L, L, 0, 0, L, L, 0])
    vy = np.array([0, 0, b, b, 0, 0, b, b])
    vz = np.array([0, 0, 0, 0, D, D, D, D])
    tri_i = [0, 0, 0, 4, 4, 1, 5, 2, 6, 3, 7, 6]
    tri_j = [1, 2, 3, 5, 7, 5, 6, 6, 7, 7, 4, 2]
    tri_k = [2, 3, 0, 6, 4, 2, 7, 3, 4, 0, 5, 1]

    traces.append(
        go.Mesh3d(
            x=vx,
            y=vy,
            z=vz,
            i=tri_i,
            j=tri_j,
            k=tri_k,
            color="#cccccc",
            opacity=0.25,
            flatshading=True,
            hoverinfo="skip",
            showscale=False,
            name="Concrete",
        )
    )

    # =======================================================
    #  Longitudinal bars - use provided reo_layout
    # =======================================================
    lw_base = 0.4

    # Bottom bars - draw each layer separately
    # BOTTOM reinforcement is BLUE
    for layer_data in reo_layout["bottom"]:
        x_positions = layer_data["x"]
        y_pos = layer_data["y"]  # This is the y coordinate in 2D (section view)
        db = layer_data["db"]
        # Convert 2D y to 3D z (y in 2D section = z in 3D beam)
        z_pos = y_pos
        line_w = max(2.0, abs(db) * lw_base)
        for x_pos in x_positions:
            traces.append(
                go.Scatter3d(
                    x=[0, L],
                    y=[x_pos, x_pos],  # x in 2D section = y in 3D beam
                    z=[z_pos, z_pos],
                    mode="lines",
                    line=dict(width=line_w, color="blue"),
                    hoverinfo="skip",
                    showlegend=False,
                )
            )

    # Top bars - draw each layer separately
    # TOP reinforcement is RED
    for layer_data in reo_layout["top"]:
        x_positions = layer_data["x"]
        y_pos = layer_data["y"]  # This is the y coordinate in 2D (section view)
        db = layer_data["db"]
        # Convert 2D y to 3D z (y in 2D section = z in 3D beam)
        z_pos = y_pos
        line_w = max(2.0, abs(db) * lw_base)
        for x_pos in x_positions:
            traces.append(
                go.Scatter3d(
                    x=[0, L],
                    y=[x_pos, x_pos],  # x in 2D section = y in 3D beam
                    z=[z_pos, z_pos],
                    mode="lines",
                    line=dict(width=line_w, color="red"),
                    hoverinfo="skip",
                    showlegend=False,
                )
            )

    # =======================================================
    #  Stirrups – use same concrete covers as reo
    # =======================================================
    if lig_d > 0 and s_lig > 0 and lig_legs >= 2:
        s_eff = max(40.0, float(s_lig))
        n_hoops = int(max(1, min(80, round(L / s_eff))))
        xs = np.linspace(s_eff / 2.0, L - s_eff / 2.0, n_hoops)

        # stirrup centre lines based on side cover
        y_left = cover_side + 0.5 * lig_d
        y_right = b - cover_side - 0.5 * lig_d

        # vertical: centre lines based on top/bottom cover
        z_top_c = cover_top + 0.5 * lig_d
        z_bot_c = D - (cover_bot + 0.5 * lig_d)

        min_z = 5.0
        max_z = D - 5.0
        z_top_c = float(np.clip(z_top_c, min_z, max_z))
        z_bot_c = float(np.clip(z_bot_c, min_z, max_z))

        lw = max(1.5, abs(lig_d) * 0.35)

        for x0 in xs:
            Xs = [x0] * 5
            Ys = [y_left, y_right, y_right, y_left, y_left]
            Zs = [z_top_c, z_top_c, z_bot_c, z_bot_c, z_top_c]
            traces.append(
                go.Scatter3d(
                    x=Xs,
                    y=Ys,
                    z=Zs,
                    mode="lines",
                    line=dict(width=lw, color="black"),
                    hoverinfo="skip",
                    showlegend=False,
                )
            )

    # =======================================================
    #  Neutral axis plane
    # =======================================================
    Xg, Yg = np.meshgrid(np.linspace(0, L, 2), np.linspace(0, b, 2))
    Zg = np.full_like(Xg, c_now)
    traces.append(
        go.Surface(
            x=Xg,
            y=Yg,
            z=Zg,
            colorscale=[[0, "orange"], [1, "orange"]],
            showscale=False,
            opacity=0.55,
            name="NA",
        )
    )

    # =======================================================
    #  Layout
    # =======================================================
    fig = go.Figure(data=traces)
    fig.update_layout(
        scene=dict(
            xaxis_title="Length (mm)",
            yaxis_title="Width (mm)",
            zaxis_title="Depth from top (mm)",
            zaxis=dict(autorange="reversed"),
            aspectmode="data",
            camera=dict(eye=dict(x=1.45, y=1.35, z=0.95)),
        ),
        margin=dict(l=0, r=0, t=10, b=0),
        height=350,
        showlegend=False,
    )
    return fig


def _build_beam_3d_figure(b, D, L, Mu_star, phi_Mu_cap, c, strain_state: str = "ULS", layout=None):
    """
    Wrapper function that reads from session state and calls the cached pure function.
    
    Args:
        layout: Optional pre-computed section layout dict. If None, will compute from session state.
    """
    # If layout is provided, extract reo_layout from it
    if layout is not None:
        reo_layout = layout.get("reo_layout")
        if reo_layout is None:
            # Fallback to computing from session state
            from section_layout import compute_longitudinal_reo_layout
            cover_bot = float(get_param("cover_bot", 40.0) or 40.0)
            cover_top = float(get_param("cover_top", 40.0) or 40.0)
            cover_side = float(
                get_param("cover_side", min(cover_top, cover_bot)) or min(cover_top, cover_bot)
            )
            nb_or_s_bot_1 = float(get_param("nb_or_s_bot_1", 4.0) or 4.0)
            db_bot_1 = float(get_param("db_bot_1", 20.0) or 20.0)
            nb_or_s_bot_2 = float(get_param("nb_or_s_bot_2", 0.0) or 0.0)
            db_bot_2 = float(get_param("db_bot_2", 20.0) or 20.0)
            nb_or_s_top_1 = float(get_param("nb_or_s_top_1", 2.0) or 2.0)
            db_top_1 = float(get_param("db_top_1", 16.0) or 16.0)
            nb_or_s_top_2 = float(get_param("nb_or_s_top_2", 0.0) or 0.0)
            db_top_2 = float(get_param("db_top_2", 16.0) or 16.0)
            rowgap_bot = float(get_param("rowgap_bot", 60.0) or 60.0)
            rowgap_top = float(get_param("rowgap_top", 60.0) or 60.0)
            reo_layout = compute_longitudinal_reo_layout(
                b=b, D=D,
                cover_bot=cover_bot, cover_top=cover_top, cover_side=cover_side,
                nb_or_s_bot_1=nb_or_s_bot_1, db_bot_1=db_bot_1,
                nb_or_s_bot_2=nb_or_s_bot_2, db_bot_2=db_bot_2,
                nb_or_s_top_1=nb_or_s_top_1, db_top_1=db_top_1,
                nb_or_s_top_2=nb_or_s_top_2, db_top_2=db_top_2,
                rowgap_bot=rowgap_bot, rowgap_top=rowgap_top,
            )
    else:
        # Compute from session state (backward compatibility)
        from section_layout import compute_longitudinal_reo_layout
        cover_bot = float(get_param("cover_bot", 40.0) or 40.0)
        cover_top = float(get_param("cover_top", 40.0) or 40.0)
        cover_side = float(
            get_param("cover_side", min(cover_top, cover_bot)) or min(cover_top, cover_bot)
        )
        nb_or_s_bot_1 = float(get_param("nb_or_s_bot_1", 4.0) or 4.0)
        db_bot_1 = float(get_param("db_bot_1", 20.0) or 20.0)
        nb_or_s_bot_2 = float(get_param("nb_or_s_bot_2", 0.0) or 0.0)
        db_bot_2 = float(get_param("db_bot_2", 20.0) or 20.0)
        nb_or_s_top_1 = float(get_param("nb_or_s_top_1", 2.0) or 2.0)
        db_top_1 = float(get_param("db_top_1", 16.0) or 16.0)
        nb_or_s_top_2 = float(get_param("nb_or_s_top_2", 0.0) or 0.0)
        db_top_2 = float(get_param("db_top_2", 16.0) or 16.0)
        rowgap_bot = float(get_param("rowgap_bot", 60.0) or 60.0)
        rowgap_top = float(get_param("rowgap_top", 60.0) or 60.0)
        reo_layout = compute_longitudinal_reo_layout(
            b=b, D=D,
            cover_bot=cover_bot, cover_top=cover_top, cover_side=cover_side,
            nb_or_s_bot_1=nb_or_s_bot_1, db_bot_1=db_bot_1,
            nb_or_s_bot_2=nb_or_s_bot_2, db_bot_2=db_bot_2,
            nb_or_s_top_1=nb_or_s_top_1, db_top_1=db_top_1,
            nb_or_s_top_2=nb_or_s_top_2, db_top_2=db_top_2,
            rowgap_bot=rowgap_bot, rowgap_top=rowgap_top,
        )
    
    # Get other parameters needed for 3D model
    cover_bot = float(get_param("cover_bot", 40.0) or 40.0)
    cover_top = float(get_param("cover_top", 40.0) or 40.0)
    cover_side = float(
        get_param("cover_side", min(cover_top, cover_bot)) or min(cover_top, cover_bot)
    )
    rowgap_bot = float(get_param("rowgap_bot", 60.0) or 60.0)
    rowgap_top = float(get_param("rowgap_top", 60.0) or 60.0)
    lig_d = float(get_param("lig_d", 10.0) or 10.0)
    lig_legs_raw = get_param("lig_legs", 2)
    try:
        lig_legs = int(lig_legs_raw or 0)
    except Exception:
        lig_legs = 0
    s_lig = float(get_param("s_lig", 200.0) or 200.0)

    return _build_beam_3d_figure_pure(
        b, D, L, Mu_star, phi_Mu_cap, c, strain_state,
        reo_layout, cover_bot, cover_top,
        cover_side, rowgap_bot, rowgap_top, lig_d, lig_legs, s_lig
    )


def render_bending():
    sync_callbacks = get_sync_callbacks()
    apply_global_widget_css()
    apply_calcbox_css()

    # Container so title + summary + 3D sit at the very top (like Inputs page)
    top_container = st.container()

    # ---------------- Sidebar glossary ----------------
    with st.sidebar.expander("📘 Glossary – Bending terms", expanded=False):
        st.markdown(
            """
            **Mu*** – Factored design bending moment at the critical section (kNm).  
            **b** – Beam/web width (mm).  
            **D** – Overall section depth (mm).  
            **d** – Effective depth to **centroid of tension steel** (mm).  
            **Ast,bot** – Area of bottom (tension) reinforcement (mm²).  
            **As_min** – Minimum required tensile steel for ductile behaviour.  
            **f'c** – Concrete cylinder strength (MPa).  
            **fsy** – Steel yield strength (MPa).  
            **Ec, Es** – Elastic moduli of concrete and steel (MPa).  

            **c** – Neutral axis depth from the top fibre (mm).  
            **a = γc** – Equivalent rectangular stress block depth (mm).  
            **kᵤ = c/d** – Neutral axis depth ratio (ductility indicator).  
            **α₂, γ** – AS 3600-style stress block factors.  
            **ϕ** – Strength reduction factor for bending.  

            **M_cr** – Cracking moment (kNm) based on f_ct,f and gross section.  
            **M_u** – Nominal flexural capacity (kNm).  
            **ϕM_u,cap** – Design flexural capacity (kNm).  
            **Utilisation** – M_u* / ϕM_u,cap → should be ≤ 1.0.  
            """
        )

    # Sync Mu_star_manual to Mu_star (contract-compliant via update_results)
    # Both widgets sync to Mu_star_manual, but _compute_bending_capacity() reads Mu_star
    Mu_star_manual_val = get_param("Mu_star_manual")
    if Mu_star_manual_val is not None:
        update_results(Mu_star=float(Mu_star_manual_val), Mu_star_kNm=float(Mu_star_manual_val))

    # ---------------- Top result summary (+ shared 3D NA view data) ----------------
    top_results = _compute_bending_capacity()
    Ast = get_param("Ast_bot")
    Mu_star = get_param("Mu_star")

    phi_Mu_cap_top = top_results["phi_Mu_cap"]
    
    # ============================================================
    # COMPUTE CACHED LAYOUT ONCE - reuse for all diagrams
    # ============================================================
    from section_layout import compute_section_layout_cached
    
    # Get all layout parameters
    b_layout = float(get_param("b", 400.0) or 400.0)
    D_layout = float(get_param("D", 600.0) or 600.0)
    cover_bot_layout = float(get_param("cover_bot", 40.0) or 40.0)
    cover_top_layout = float(get_param("cover_top", 40.0) or 40.0)
    cover_side_layout = float(
        st.session_state.get("inputs_cover_side_local", min(cover_top_layout, cover_bot_layout))
    )
    
    nb_or_s_bot_1_layout = float(get_param("nb_or_s_bot_1", 4.0) or 4.0)
    db_bot_1_layout = float(get_param("db_bot_1", 20.0) or 20.0)
    nb_or_s_bot_2_layout = float(get_param("nb_or_s_bot_2", 0.0) or 0.0)
    db_bot_2_layout = float(get_param("db_bot_2", 20.0) or 20.0)
    
    nb_or_s_top_1_layout = float(get_param("nb_or_s_top_1", 2.0) or 2.0)
    db_top_1_layout = float(get_param("db_top_1", 16.0) or 16.0)
    nb_or_s_top_2_layout = float(get_param("nb_or_s_top_2", 0.0) or 0.0)
    db_top_2_layout = float(get_param("db_top_2", 16.0) or 16.0)
    
    rowgap_bot_layout = float(get_param("rowgap_bot", 60.0) or 60.0)
    rowgap_top_layout = float(get_param("rowgap_top", 60.0) or 60.0)
    
    lig_legs_raw_layout = get_param("lig_legs", 2)
    try:
        lig_legs_layout = int(lig_legs_raw_layout or 0)
    except Exception:
        lig_legs_layout = 0
    lig_d_layout = float(get_param("lig_d", 10.0) or 10.0)
    
    # Compute cached layout once
    cached_layout = compute_section_layout_cached(
        b=b_layout, D=D_layout,
        cover_bot=cover_bot_layout, cover_top=cover_top_layout, cover_side=cover_side_layout,
        nb_or_s_bot_1=nb_or_s_bot_1_layout, db_bot_1=db_bot_1_layout,
        nb_or_s_bot_2=nb_or_s_bot_2_layout, db_bot_2=db_bot_2_layout,
        nb_or_s_top_1=nb_or_s_top_1_layout, db_top_1=db_top_1_layout,
        nb_or_s_top_2=nb_or_s_top_2_layout, db_top_2=db_top_2_layout,
        rowgap_bot=rowgap_bot_layout, rowgap_top=rowgap_top_layout,
        lig_legs=lig_legs_layout, lig_d=lig_d_layout,
    )
    Mu_util_top = top_results["Mu_util"]
    ku_top = top_results["ku"]
    As_min_top = top_results["As_min"]
    c_top = top_results["c"]
    Mcr_top = top_results["Mcr"]
    # Minimum-strength design moment from Tab 2 logic: M_u,min = 1.2 M_cr
    if Mcr_top is not None and not (
        isinstance(Mcr_top, float) and math.isnan(Mcr_top)
    ):
        Mu_min_top = 1.2 * Mcr_top
    else:
        Mu_min_top = float("nan")

    def _status_colour(flag):
        if flag is None:
            return "Not calculated", "#e0e0e0"
        return ("OK", "#d5f5d5") if flag else ("Check", "#f8d0d0")

    # checks for summary card
    As_ok = None
    if Ast is not None and As_min_top and not math.isnan(As_min_top):
        As_ok = Ast >= As_min_top

    # Flexural check: Mu* ≤ ϕMu,cap
    Mu_ok = None
    if phi_Mu_cap_top and phi_Mu_cap_top > 0 and Mu_star is not None:
        Mu_ok = Mu_star <= phi_Mu_cap_top

    # Minimum strength requirement: ϕMu,cap ≥ Mu,min
    Mu_min_ok = None
    Mu_min_util = None
    if (
        phi_Mu_cap_top
        and phi_Mu_cap_top > 0
        and Mu_min_top is not None
        and not (isinstance(Mu_min_top, float) and math.isnan(Mu_min_top))
        and Mu_min_top > 0
    ):
        Mu_min_ok = phi_Mu_cap_top >= Mu_min_top
        Mu_min_util = Mu_min_top / phi_Mu_cap_top

    ku_ok = None
    if ku_top is not None and not math.isnan(ku_top):
        ku_ok = (0.0 < ku_top <= 0.36)  # teaching limit

    As_status, As_colour = _status_colour(As_ok)
    Mu_status, Mu_colour = _status_colour(Mu_ok)
    Mu_min_status, Mu_min_colour = _status_colour(Mu_min_ok)
    ku_status, ku_colour = _status_colour(ku_ok)

    Ast_str = f"{Ast:.1f} mm²" if Ast not in (None, float("nan")) else "—"
    As_min_str = (
        f"{As_min_top:.1f} mm²" if As_min_top and not math.isnan(As_min_top) else "—"
    )
    phiMu_str = (
        f"{phi_Mu_cap_top:.2f} kNm"
        if phi_Mu_cap_top and phi_Mu_cap_top > 0
        else "—"
    )
    Mu_star_str = f"{Mu_star:.2f} kNm" if Mu_star not in (None, float("nan")) else "—"
    Mu_util_str = (
        f"{Mu_util_top:.3f}" if phi_Mu_cap_top and phi_Mu_cap_top > 0 else "—"
    )

    Mu_min_str = (
        f"{Mu_min_top:.2f} kNm"
        if Mu_min_top is not None
        and not (isinstance(Mu_min_top, float) and math.isnan(Mu_min_top))
        else "—"
    )
    Mu_min_util_str = f"{Mu_min_util:.3f}" if Mu_min_util is not None else "—"

    ku_str = f"{ku_top:.3f}" if ku_top is not None and not math.isnan(ku_top) else "—"
    c_str = (
        f"{c_top:.2f} mm" if c_top is not None and not math.isnan(c_top) else "—"
    )
    a_str = (
        f"{(top_results['a'] or float('nan')):.2f} mm"
        if "a" in top_results and not math.isnan(top_results["a"])
        else "—"
    )

    # SLS steel stress string (for summary table; matches Deflection / Crack pages).
    fs_ser = get_param("sigma_s_sls", None)
    try:
        fs_ser_val = float(fs_ser) if fs_ser is not None else float("nan")
    except Exception:
        fs_ser_val = float("nan")

    if math.isnan(fs_ser_val):
        fs_ser_str = "—"
    else:
        fs_ser_str = f"{fs_ser_val:.1f} MPa"

    # Canonical bending state shared by 3D & bottom radios (ULS / SLS / Uncracked)
    state_options = ["ULS", "SLS (cracked)", "Uncracked"]
    canonical_state = st.session_state.get("bending_state", "ULS")
    if canonical_state not in state_options:
        canonical_state = "ULS"

    # Summary rows in deflection-style format
    rows_summary = [
        {
            "Check": "Steel area Ast,bot",
            "Value": Ast_str,
            "Limit": f"As,min = {As_min_str}",
            "Utilisation": "—",
            "Status": As_status,
        },
        {
            "Check": "Flexural capacity",
            "Value": f"ϕM\u2093,cap = {phiMu_str}",
            "Limit": f"M\u2093* = {Mu_star_str}",
            "Utilisation": Mu_util_str,
            "Status": Mu_status,
        },
        {
            "Check": "Minimum strength",
            "Value": f"ϕM\u2093,cap = {phiMu_str}",
            "Limit": f"M\u2093,min = {Mu_min_str}",
            "Utilisation": Mu_min_util_str,
            "Status": Mu_min_status,
        },
        {
            "Check": "Neutral axis ratio k\u2091",
            "Value": f"k\u2091 = {ku_str}",
            "Limit": "AS 3600 limit ≤ 0.36",
            "Utilisation": "—",
            "Status": ku_status,
        },
        {
            "Check": "SLS steel stress f\u209b,ser",
            "Value": fs_ser_str,
            "Limit": "SLS (for crack/deflection)",
            "Utilisation": "—",
            "Status": "—",
        },
        {
            "Check": "Neutral axis depth d\u2099",
            "Value": f"d\u2099 = {c_str}",
            "Limit": "",
            "Utilisation": "—",
            "Status": "—",
        },
        {
            "Check": "Stress block depth a = γc",
            "Value": f"a = {a_str}",
            "Limit": "",
            "Utilisation": "—",
            "Status": "—",
        },
    ]

    summary_df = pd.DataFrame(rows_summary)

    def _highlight_status(row):
        status = row.get("Status", "")
        if status == "OK":
            color = "#d9ead3"
        elif status in ("Check", "NG"):
            color = "#f4cccc"
        else:
            color = ""
        return [f"background-color: {color}"] * len(row)

    styled_summary = summary_df.style.apply(_highlight_status, axis=1)

    # ---------------- TOP CONTAINER – Title + 3D in one row, summary full-width below ----------------
    with top_container:
        top_left, top_right = st.columns([0.58, 0.42])

        with top_left:
            st.title("Bending Capacity")
            st.markdown(
                r"""
This page computes **ultimate flexural capacity**, **strain compatibility**, and
**service-stress outputs** in accordance with **AS 3600:2018 Clause 8**, including:

- **Ultimate moment capacity**  
  $ \phi M_{u,\mathrm{cap}} = \phi\,T\,(d - 0.5\,\gamma x_u) $ — Cl. 8.1.3

- **Steel stress at serviceability**,  
  $ f_{s,\mathrm{ser}} = E_s\,\varepsilon_s $, used in crack-width and deflection checks.
                """
            )

        with top_right:
            # --- Replace old 3D model with curved "2D-looking-3D" diagram ---
            from curved_beam_diagram import render_curved_beam_fig
            
            # Get parameters (convert mm to meters for consistency with function)
            L_m = float(get_param("L", 8000.0) or 8000.0) / 1000.0  # mm -> m
            D_m = float(get_param("D", 600.0) or 600.0) / 1000.0    # mm -> m
            b_m = float(get_param("b", 400.0) or 400.0) / 1000.0    # mm -> m
            # Convert c_top from mm to m (ULS neutral axis depth)
            if c_top is not None and not (isinstance(c_top, float) and math.isnan(c_top)):
                dn_uls_m = float(c_top) / 1000.0  # mm -> m
            else:
                dn_uls_m = 0.21 * D_m  # fallback: 21% of depth (already in meters)
            
            # Draw figure with fixed curvature of 0.4
            if D_m > 0 and L_m > 0 and dn_uls_m > 0:
                fig_beam = render_curved_beam_fig(
                    L=L_m,          # meters
                    D=D_m,          # meters
                    b=b_m,          # meters
                    dn_uls=dn_uls_m,  # meters - ULS neutral axis depth only
                    ts_centroid_y=None,  # leave None if you already compute Ts centroid elsewhere later
                    curvature=0.4,  # fixed curvature
                    title=None,
                )
                st.pyplot(fig_beam, clear_figure=True)
            else:
                st.info(
                    "Curved beam view will appear once geometry and moment capacity are defined."
                )

        # Summary table spans full width under the heading + 3D row (deflection-style)
        st.markdown("### Bending – Summary")
        st.dataframe(styled_summary, use_container_width=True, hide_index=True)

    # Persist canonical bending state for the rest of the page (and next rerun)
    st.session_state["bending_state"] = canonical_state

    # values for later
    phi_Mu_cap = top_results["phi_Mu_cap"]
    c = top_results["c"]
    a = top_results["a"]
    z = top_results["z"]
    ku = top_results["ku"]
    alpha2 = top_results["alpha2"]
    gamma = top_results["gamma"]
    phi = top_results["phi"]
    fctf = top_results["fctf"]
    Z_gross = top_results["Z_gross"]
    Mcr = top_results["Mcr"]
    As_min = top_results["As_min"]
    d = top_results["d"]

    # shared values
    b = get_param("b")
    D = get_param("D")
    fc = get_param("fc")
    fsy = get_param("fsy")
    Ec = get_param("Ec")
    Es = get_param("Es")
    Mu_star = get_param("Mu_star")
    L_shared = get_param("L")
    nb_bot = get_param("nb_bot")
    db_bot = get_param("db_bot")
    cover_bot = get_param("cover_bot")
    nb_top = get_param("nb_top")
    db_top = get_param("db_top")
    cover_top = get_param("cover_top")

    # local copies for table
    fc_local = fc if fc is not None else 40.0
    cover_bot_local = cover_bot if cover_bot is not None else 40.0
    db_bot_local = db_bot if db_bot is not None else 20.0
    nb_bot_local = int(nb_bot) if nb_bot is not None else 4
    D_local = D if D is not None else 600.0

    d_eff = d
    if d_eff is None or (isinstance(d_eff, float) and math.isnan(d_eff)):
        d_eff = D_local - cover_bot_local - 0.5 * db_bot_local

    Ast_bot = Ast
    if Ast_bot is None or (isinstance(Ast_bot, float) and math.isnan(Ast_bot)):
        Ast_bot = nb_bot_local * math.pi * db_bot_local**2 / 4.0

    alpha2_raw = 0.85 - 0.0015 * fc_local
    gamma_raw = 0.97 - 0.0025 * fc_local
    alpha2_sb = max(0.67, alpha2_raw)
    gamma_sb = max(0.67, gamma_raw)
    phi_b = get_param("phi_bend", 0.85)
    ku_sb = ku if ku is not None else float("nan")

    Mu_min = (
        1.2 * Mcr
        if (Mcr is not None and not (isinstance(Mcr, float) and math.isnan(Mcr)))
        else float("nan")
    )
    Mu_nom_report = phi_Mu_cap / phi if phi and phi > 0 else float("nan")

    st.markdown("---")

    # ---------------- 3-column layout for Design Actions + Geometry + Materials ----------------
    col_actions, col_geom, col_mat = st.columns(3)

    with col_actions:
        # Heading row with info popover for source of design actions
        col_title, col_info = st.columns([0.92, 0.08])
        with col_title:
            st.subheader("Design Actions for Bending")
        with col_info:
            with st.popover("ℹ️", help="Source of design actions (M*, V*)"):
                # Initialize session state key if not present
                if "bending_action_source" not in st.session_state:
                    st.session_state["bending_action_source"] = "manual"
                
                action_source = st.radio(
                    "Source of design actions (M, V):",
                    ["Manual design actions (inputs below)", "Teaching SFD/BMD page"],
                    index=0 if st.session_state["bending_action_source"] == "manual" else 1,
                    key="bending_action_source_radio",
                )
                
                # Update session state based on selection
                if action_source == "Manual design actions (inputs below)":
                    st.session_state["bending_action_source"] = "manual"
                else:
                    st.session_state["bending_action_source"] = "sfd_bmd"
        
        # Show caption with current selection
        current_source = st.session_state.get("bending_action_source", "manual")
        if current_source == "manual":
            st.caption("Design actions: Manual")
        else:
            st.caption("Design actions: From SFD/BMD")

        number_row(
            "Design moment Mu* (kNm)",
            "bending_Mu_star",
            10.0,
            sync_callbacks,
            help_text=(
                "Factored design bending moment at the critical section. "
                "Increasing Mu* increases bending demand and utilisation."
            ),
        )
        number_row(
            "Axial force N* (kN)",
            "bending_N_star",
            50.0,
            sync_callbacks,
            help_text=(
                "Axial force acting with bending. Compression (negative in many "
                "conventions) can reduce tension in the steel; tension increases demand."
            ),
        )
        number_row(
            "Prestress force P* (kN)",
            "bending_P_star",
            50.0,
            sync_callbacks,
            help_text=(
                "Prestress / pre-compression in the section. Increasing P* typically "
                "reduces tensile demand in the bottom reinforcement."
            ),
        )
        number_row(
            "Bending strength factor ϕb",
            "bending_phi_b",
            0.01,
            sync_callbacks,
            help_text=(
                "Strength reduction factor for bending (AS 3600 ϕ-factor). "
                "This multiplies the nominal capacity to give ϕM_u,cap."
            ),
        )

    with col_geom:
        st.subheader("Geometry")
        number_row(
            "Width b (mm)",
            "bending_b",
            10.0,
            sync_callbacks,
            help_text=(
                "Section width. Increasing b increases compression block area and "
                "reduces required tensile steel for a given Mu*."
            ),
        )
        number_row(
            "Depth D (mm)",
            "bending_D",
            10.0,
            sync_callbacks,
            help_text=(
                "Overall section depth. Larger D increases lever arm (d) and "
                "typically increases bending capacity."
            ),
        )
        number_row(
            "Span L (mm)",
            "bending_L",
            100.0,
            sync_callbacks,
            help_text=(
                "Member span. Used mainly for serviceability checks and linking to "
                "deflection; not directly in φMu,cap here."
            ),
        )

    with col_mat:
        st.subheader("Materials")
        number_row(
            "Concrete strength f'c (MPa)",
            "bending_fc",
            2.0,
            sync_callbacks,
            help_text=(
                "Concrete compressive strength. Higher f'c increases compression "
                "capacity and may reduce required steel, but also changes ductility limits."
            ),
        )
        number_row(
            "Steel yield fsy (MPa)",
            "bending_fsy",
            10.0,
            sync_callbacks,
            help_text=(
                "Yield strength of reinforcing steel. Higher fsy increases the "
                "force carried by a given area of steel."
            ),
        )
        number_row(
            "Ec (MPa)",
            "bending_Ec",
            1000.0,
            sync_callbacks,
            help_text=(
                "Short-term modulus of concrete. Mainly affects stiffness and "
                "SLS behaviour rather than φMu,cap."
            ),
        )
        number_row(
            "Es (MPa)",
            "bending_Es",
            10000.0,
            sync_callbacks,
            help_text=(
                "Steel modulus. Typically ~200,000 MPa; affects cracked-section "
                "stiffness and strain calculations."
            ),
        )

    st.markdown("---")

    r1, r2 = st.columns(2)

    with r1:
        st.subheader("Bottom Longitudinal Reinforcement")
        
        # Display messages for bottom reinforcement
        if st.session_state.get("_reo_msg_bot_auto_layer2", False):
            show_reo_message("auto_layer2", layer="Bottom Layer 1")
            st.session_state["_reo_msg_bot_auto_layer2"] = False  # Clear after showing
        
        if st.session_state.get("_reo_msg_bot_layer2_overwritten", False):
            show_reo_message("layer2_overwritten", layer="Bottom Layer 1")
            st.session_state["_reo_msg_bot_layer2_overwritten"] = False  # Clear after showing
        
        if st.session_state.get("_reo_error_bot_1", False):
            show_reo_message("layout_invalid", layer="Bottom Layer 1")
            st.session_state["_reo_error_bot_1"] = False  # Clear after showing
        
        warning_bot_1 = st.session_state.get("_reo_warning_bot_1")
        if warning_bot_1:
            # Extract s_min if available
            s_min_val = st.session_state.get("_reo_s_min_bot_1", 25.0)
            show_reo_message("spacing_clamped", layer="Bottom Layer 1", s_min=s_min_val)
            st.session_state["_reo_warning_bot_1"] = None  # Clear after showing
            st.session_state["_reo_s_min_bot_1"] = None
        
        st.markdown("**Layer 1**")
        number_row(
            "Layer 1: bars or spacing (≤30 = bars, ≥30 = mm)",
            "bending_nb_or_s_bot_1",
            1.0,
            sync_callbacks,
            help_text="Enter a number of bars (≤30) or a spacing in mm (≥30).",
        )

        number_row(
            "Layer 1: bar diameter db,bot,1 (mm)",
            "bending_db_bot_1",
            1.0,
            sync_callbacks,
            help_text="Nominal diameter of bottom Layer 1 bars.",
        )
        
        st.markdown("**Layer 2**")
        
        number_row(
            "Layer 2: bars or spacing (≤30 = bars, ≥30 = mm)",
            "bending_nb_or_s_bot_2",
            1.0,
            sync_callbacks,
            help_text="Enter a number of bars (≤30) or a spacing in mm (≥30). Auto-updated if Layer 1 doesn't fit.",
        )

        number_row(
            "Layer 2: bar diameter db,bot,2 (mm)",
            "bending_db_bot_2",
            1.0,
            sync_callbacks,
            help_text="Nominal diameter of bottom Layer 2 bars.",
        )

        number_row(
            "Bottom row gap (mm)",
            "bending_rowgap_bot",
            5.0,
            sync_callbacks,
            help_text="Vertical gap between bottom rows if two layers are used.",
        )
        
        number_row(
            "Bottom cover (mm)",
            "bending_cover_bot",
            5.0,
            sync_callbacks,
            help_text=(
                "Concrete cover to bottom reinforcement. Increasing cover reduces "
                "effective depth d and reduces φMu,cap, but may be required for durability."
            ),
        )

    with r2:
        st.subheader("Top Longitudinal Reinforcement")
        
        # Display messages for top reinforcement
        if st.session_state.get("_reo_msg_top_auto_layer2", False):
            show_reo_message("auto_layer2", layer="Top Layer 1")
            st.session_state["_reo_msg_top_auto_layer2"] = False  # Clear after showing
        
        if st.session_state.get("_reo_msg_top_layer2_overwritten", False):
            show_reo_message("layer2_overwritten", layer="Top Layer 1")
            st.session_state["_reo_msg_top_layer2_overwritten"] = False  # Clear after showing
        
        if st.session_state.get("_reo_error_top_1", False):
            show_reo_message("layout_invalid", layer="Top Layer 1")
            st.session_state["_reo_error_top_1"] = False  # Clear after showing
        
        warning_top_1 = st.session_state.get("_reo_warning_top_1")
        if warning_top_1:
            # Extract s_min if available
            s_min_val = st.session_state.get("_reo_s_min_top_1", 25.0)
            show_reo_message("spacing_clamped", layer="Top Layer 1", s_min=s_min_val)
            st.session_state["_reo_warning_top_1"] = None  # Clear after showing
            st.session_state["_reo_s_min_top_1"] = None
        
        st.markdown("**Layer 1**")
        number_row(
            "Layer 1: bars or spacing (≤30 = bars, ≥30 = mm)",
            "bending_nb_or_s_top_1",
            1.0,
            sync_callbacks,
            help_text="Enter a number of bars (≤30) or a spacing in mm (≥30).",
        )

        number_row(
            "Layer 1: bar diameter db,top,1 (mm)",
            "bending_db_top_1",
            1.0,
            sync_callbacks,
            help_text="Nominal diameter of top Layer 1 bars.",
        )
        
        st.markdown("**Layer 2**")
        
        number_row(
            "Layer 2: bars or spacing (≤30 = bars, ≥30 = mm)",
            "bending_nb_or_s_top_2",
            1.0,
            sync_callbacks,
            help_text="Enter a number of bars (≤30) or a spacing in mm (≥30). Auto-updated if Layer 1 doesn't fit.",
        )

        number_row(
            "Layer 2: bar diameter db,top,2 (mm)",
            "bending_db_top_2",
            1.0,
            sync_callbacks,
            help_text="Nominal diameter of top Layer 2 bars.",
        )

        number_row(
            "Top row gap (mm)",
            "bending_rowgap_top",
            5.0,
            sync_callbacks,
            help_text="Vertical gap between top rows if two layers are used.",
        )
        
        number_row(
            "Top cover (mm)",
            "bending_cover_top",
            5.0,
            sync_callbacks,
            help_text=(
                "Concrete cover to top reinforcement. Affects effective depth to "
                "compression reinforcement and durability."
            ),
        )

    # --- GLOBAL CONCRETE STRESS MODEL (shared across all states) ---
    # Initialize global state key if not present
    if "concrete_stress_model" not in st.session_state:
        st.session_state["concrete_stress_model"] = "rectangular"
    
    # Heading row with info popover
    col_title, col_info = st.columns([0.95, 0.05])
    with col_title:
        st.markdown("### Section & stress–strain model")
    with col_info:
        with st.popover("ℹ️", help="Concrete stress model options"):
            st.markdown("**Concrete stress model**")
            use_parabolic = st.checkbox(
                "Use parabolic (non-linear) stress block",
                value=(st.session_state["concrete_stress_model"] == "parabolic"),
                key="bending_parabolic_toggle",
            )
            if use_parabolic:
                st.session_state["concrete_stress_model"] = "parabolic"
            else:
                st.session_state["concrete_stress_model"] = "rectangular"
            
            st.markdown("""
            **Rectangular (AS 3600):** Standard simplified stress block used in AS 3600 design.
            
            **Parabolic (non-linear):** More accurate representation of concrete stress distribution, 
            showing the non-linear relationship between strain and stress.
            """)
    
    # Show the current model label (always visible)
    current_model = st.session_state.get("concrete_stress_model", "rectangular")
    if current_model == "parabolic":
        model_display = "Parabolic (non-linear)"
    else:
        model_display = "Rectangular (AS 3600)"
    st.markdown(f"**{model_display}**")

    # --- STATE RADIO (ULS / SLS / Uncracked) ---
    state_options = ["ULS", "SLS (cracked)", "Uncracked"]
    main_state = st.radio(
        "State:",
        state_options,
        key="bending_state_main",
        horizontal=True,
        index=state_options.index(canonical_state),
    )

    # --- Build label for the 3-panel diagram using global concrete_stress_model ---
    stress_model = st.session_state.get("concrete_stress_model", "rectangular")
    
    if main_state == "ULS":
        if stress_model == "parabolic":
            diagram_state_label = "uls – parabolic"
        else:
            diagram_state_label = "uls – rectangular"
    elif main_state.startswith("SLS"):
        if stress_model == "parabolic":
            diagram_state_label = "sls – parabolic"
        else:
            diagram_state_label = "sls – linear"
    else:  # Uncracked
        if stress_model == "parabolic":
            diagram_state_label = "uncracked – parabolic"
        else:
            diagram_state_label = "uncracked – linear"

    # Persist for the diagram function
    st.session_state["bending_strain_state_local"] = diagram_state_label

    # --- Placeholders so we can render *after* the tabs but keep them visually above ---
    matcurves_placeholder = st.empty()
    diagram_placeholder = st.empty()

    # Underlying strain-state math uses the solver's labels
    if main_state.startswith("ULS"):
        state_for_math = "ULS"
    elif main_state.startswith("SLS"):
        state_for_math = "SLS"
    else:
        state_for_math = "Uncracked"

    # ---------------- Step-by-step tabs ----------------
    tab_uls, tab_min, tab_sls = st.tabs(
        ["ULS step-by-step", "Section 2 – Minimum strength", "SLS step-by-step"]
    )

    with tab_uls:
        render_uls_tab(top_results, b, D, fc, fsy, Ast_bot, d_eff)

    with tab_min:
        render_min_strength_tab(top_results, b, D, fc, fsy, Ast_bot)

    with tab_sls:
        render_sls_tab(top_results, b, D, d_eff, Ast_bot, Ec, Es, Mu_star)

    # --------------------------------------------------
    # Now build the 3-panel diagram, using the SLS results
    # that render_sls_tab has just written into session_state.
    # --------------------------------------------------
    with diagram_placeholder.container():
        ss_state = _stress_strain_state(state_for_math)
        
        # For SLS, add cracked-section neutral axis from the solve
        if state_for_math == "SLS":
            try:
                dn_cracked = st.session_state.get("bending_sls_dn", None)
                if dn_cracked is not None:
                    # Build nested SLS structure with cracked NA
                    ss_state["sls"] = {
                        "dn_cracked": float(dn_cracked),
                        "dn": float(dn_cracked),  # also set as dn for backward compatibility
                        "eps_c_top": st.session_state.get("bending_sls_eps_top"),
                        "eps_s_layers": [],  # will be populated if available
                        "sig_s_layers": [],
                        "y_layers": [],
                    }
            except Exception:
                pass
        
        fig_ss = _plot_stress_strain_profiles(
            ss_state,
            state_label=diagram_state_label,
            layout=cached_layout,  # Pass cached layout to avoid recomputation
        )
        st.plotly_chart(fig_ss, use_container_width=True, config={"displayModeBar": False})

    # --------------------------------------------------
    # Material stress–strain curves (concrete + steel),
    # rendered *after* SLS tab but shown above it.
    # --------------------------------------------------
    with matcurves_placeholder.container():
        with st.expander("ℹ️ Stress–strain model & material behaviour", expanded=False):
            st.markdown(
                f"""
**Current state:** `{main_state}`  

This diagram shows how **concrete** and **steel** share strain in a reinforced
concrete section, and how we go from **strain → stress → force**:

- In the **elastic range** we use **Hooke's law**  

  - Steel:  $\\sigma_s = E_s \\, \\varepsilon_s$  

  - Concrete (short-term):  $\\sigma_c = E_c \\, \\varepsilon_c$  

- Once we know the **stress** we get the **resultant force** by  

  $$F = \\sigma \\; A$$  

  where $A$ is the relevant steel or concrete area (e.g. $A_{{st}}$ for tension bars,
  $b \\times a$ for the ULS concrete block).

- For **steel** we assume a **linear elastic** branch up to the yield stress
  $f_{{sy}}$ (your session value, typically about 500 MPa), then a near-horizontal
  plastic region with slight hardening and softening – similar to a test curve.

- For **concrete in compression** we use a **non-linear parabolic** stress–strain curve.
  At ULS we replace this with the **AS 3600 rectangular** $\\alpha_2$–$\\gamma$
  stress block, chosen so it has the **same resultant force and lever arm** as
  the underlying parabolic distribution.

- At **SLS** and in the *uncracked* state we still assume a **linear strain profile**,
  but with lower stresses (service-level actions). The vertical dotted lines on
  the plots mark the **SLS** and **ULS** points for concrete and steel.

**Sign convention note**

- In the main section/strain diagrams on this page, **tension steel strains are negative**
  (ε < 0) and compression is positive – this matches typical reinforced concrete
  sign conventions.

- In the **steel material curve below**, we instead plot the **magnitude**
  $|\\varepsilon_s| \\ge 0$ on the x-axis. So any negative steel strains read from the
  ULS/SLS diagrams have been converted to **positive values here**, but they still
  represent the **tension capacity** of the steel.

The difference between the concrete and steel curves – mainly their **slopes**
($E_c$ vs $E_s$) – is what drives the different **forces** that develop at SLS and ULS
for the same strain pattern.

"""
            )
            fig_mat = _plot_material_stress_strain_curves()
            st.plotly_chart(
                fig_mat,
                use_container_width=True,
                config={"displayModeBar": False},
            )


# ============================
# MAIN GUARD
# ============================
if __name__ == "__main__":
    render_bending()
