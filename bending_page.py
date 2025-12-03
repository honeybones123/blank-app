# bending_page.py
# ============================
# BENDING PAGE
# ============================

import math
import numpy as np
import pandas as pd
import streamlit as st
import plotly.graph_objects as go

from state_and_helpers import get_sync_callbacks, get_param, update_results
from widgets_helpers import apply_global_widget_css, apply_calcbox_css, number_row
from bending_core import _fmt, _compute_bending_capacity, _stress_strain_state
from bending_diagrams import _plot_stress_strain_profiles
from bending_tabs import render_uls_tab, render_min_strength_tab, render_sls_tab


def _build_beam_3d_figure(b, D, L, Mu_star, phi_Mu_cap, c, strain_state: str = "ULS"):
    """
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

    # scale by state
    if strain_state == "ULS":
        r = base_r
    elif strain_state == "SLS (cracked)":
        r = 0.6 * base_r
    else:  # "Uncracked"
        r = 0.0

    c0 = D / 2.0  # uncracked NA
    if r <= 0.0:
        phi = 0.0
        c_now = c0
    else:
        phi = r * phi_u
        c_now = (1.0 - r) * c0 + r * c

    st.session_state["bending_phi_current"] = phi
    st.session_state["bending_c_current"] = c_now

    # ---------- Reo + lig data from session state ----------
    nb_bot = int(get_param("nb_bot", 4) or 0)
    db_bot = float(get_param("db_bot", 20.0) or 20.0)
    nb_top = int(get_param("nb_top", 2) or 0)
    db_top = float(get_param("db_top", 16.0) or 16.0)

    cover_bot = float(get_param("cover_bot", 40.0) or 40.0)
    cover_top = float(get_param("cover_top", 40.0) or 40.0)
    cover_side = float(
        st.session_state.get("inputs_cover_side_local", min(cover_top, cover_bot))
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
    #  Helpers for consistent cover
    # =======================================================
    max_bar_d = max(db_bot, db_top, lig_d, 0.0)
    horiz_clear = 0.5 * max_bar_d  # clear from stirrup to bar centre

    def _row_y_positions(nbars: int, bar_dia: float) -> list[float]:
        """
        Evenly space bars in a single row between stirrups with a fixed clear
        distance horiz_clear from the stirrup legs.
        """
        if nbars <= 0 or bar_dia <= 0:
            return []

        # stirrup centre-lines
        y_st_left = cover_side + 0.5 * lig_d
        y_st_right = b - cover_side - 0.5 * lig_d

        y_min = y_st_left + horiz_clear
        y_max = y_st_right - horiz_clear

        if y_max <= y_min:
            mid = 0.5 * b
            return [mid] * nbars

        if nbars == 1:
            return [0.5 * (y_min + y_max)]
        return list(np.linspace(y_min, y_max, nbars))

    def _layer_positions(
        nbars: int, bar_dia: float, cover: float, rowgap: float, is_top: bool
    ) -> list[tuple[float, float]]:
        """
        Up to 2 rows per layer.
        rowgap is treated as a *clear* gap between rows.
        """
        if nbars <= 0 or bar_dia <= 0:
            return []

        max_per_row = 5
        n_row1 = min(nbars, max_per_row)
        n_row2 = nbars - n_row1

        # Row depths – bar centres
        if is_top:
            z1 = cover + 0.5 * bar_dia
            # second row below, with clear gap
            z2 = z1 + (rowgap + bar_dia) if n_row2 > 0 else None
        else:
            z1 = D - (cover + 0.5 * bar_dia)
            # second row above, with clear gap
            z2 = z1 - (rowgap + bar_dia) if n_row2 > 0 else None

        min_z = 0.5 * bar_dia + 5.0
        max_z = D - 0.5 * bar_dia - 5.0

        z1 = float(np.clip(z1, min_z, max_z))
        if z2 is not None:
            z2 = float(np.clip(z2, min_z, max_z))

        ys1 = _row_y_positions(n_row1, bar_dia)
        positions: list[tuple[float, float]] = [(y, z1) for y in ys1]

        if n_row2 > 0 and z2 is not None:
            ys2 = _row_y_positions(n_row2, bar_dia)
            positions += [(y, z2) for y in ys2]

        return positions

    # =======================================================
    #  Longitudinal bars (now with consistent covers)
    # =======================================================
    lw_base = 0.4

    # Bottom layer – red
    bot_positions = _layer_positions(nb_bot, db_bot, cover_bot, rowgap_bot, is_top=False)
    line_w_bot = max(2.0, abs(db_bot) * lw_base)
    for (yy, zz) in bot_positions:
        traces.append(
            go.Scatter3d(
                x=[0, L],
                y=[yy, yy],
                z=[zz, zz],
                mode="lines",
                line=dict(width=line_w_bot, color="red"),
                hoverinfo="skip",
                showlegend=False,
            )
        )

    # Top layer – blue
    top_positions = _layer_positions(nb_top, db_top, cover_top, rowgap_top, is_top=True)
    line_w_top = max(2.0, abs(db_top) * lw_base)
    for (yy, zz) in top_positions:
        traces.append(
            go.Scatter3d(
                x=[0, L],
                y=[yy, yy],
                z=[zz, zz],
                mode="lines",
                line=dict(width=line_w_top, color="blue"),
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

    # ---------------- Top result summary (+ shared 3D NA view data) ----------------
    top_results = _compute_bending_capacity()
    Ast = get_param("Ast_bot")
    Mu_star = get_param("Mu_star")

    phi_Mu_cap_top = top_results["phi_Mu_cap"]
    Mu_util_top = top_results["Mu_util"]
    ku_top = top_results["ku"]
    As_min_top = top_results["As_min"]
    c_top = top_results["c"]

    def _status_colour(flag):
        if flag is None:
            return "Not calculated", "#e0e0e0"
        return ("OK", "#d5f5d5") if flag else ("Check", "#f8d0d0")

    # checks for summary card
    As_ok = None
    if Ast is not None and As_min_top and not math.isnan(As_min_top):
        As_ok = Ast >= As_min_top

    Mu_ok = None
    if phi_Mu_cap_top and phi_Mu_cap_top > 0 and Mu_star is not None:
        Mu_ok = Mu_star <= phi_Mu_cap_top

    ku_ok = None
    if ku_top is not None and not math.isnan(ku_top):
        ku_ok = (0.0 < ku_top <= 0.36)  # teaching limit

    As_status, As_colour = _status_colour(As_ok)
    Mu_status, Mu_colour = _status_colour(Mu_ok)
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
    ku_str = f"{ku_top:.3f}" if ku_top is not None and not math.isnan(ku_top) else "—"

    # Original summary card HTML (kept as a single string)
    summary_html = f"""
    <div style="
        border: 1px solid #cccccc;
        border-radius: 8px;
        padding: 0.5rem 0.75rem;
        margin-bottom: 1rem;
        max-width: 900px;
    ">
      <table style="width: 100%; border-collapse: collapse; font-size: 0.9rem;">
        <thead>
          <tr style="background-color: #f5f5f5;">
            <th style="text-align:left; padding: 4px 6px;">Item</th>
            <th style="text-align:right; padding: 4px 6px;">Value</th>
            <th style="text-align:right; padding: 4px 6px;">Criterion</th>
            <th style="text-align:center; padding: 4px 6px;">Status</th>
          </tr>
        </thead>
        <tbody>
          <tr style="background-color: {As_colour};">
            <td style="padding: 4px 6px;"><strong>Steel area Ast,bot</strong></td>
            <td style="text-align:right; padding: 4px 6px;">{Ast_str}</td>
            <td style="text-align:right; padding: 4px 6px;">≥ As,min = {As_min_str}</td>
            <td style="text-align:center; padding: 4px 6px;"><strong>{As_status}</strong></td>
          </tr>
          <tr style="background-color: {Mu_colour};">
            <td style="padding: 4px 6px;"><strong>Flexural capacity</strong></td>
            <td style="text-align:right; padding: 4px 6px;">ϕM<sub>u,cap</sub> = {phiMu_str}</td>
            <td style="text-align:right; padding: 4px 6px;">M<sub>u</sub>* = {Mu_star_str}</td>
            <td style="text-align:center; padding: 4px 6px;">
              Util = {Mu_util_str}<br><strong>{Mu_status}</strong>
            </td>
          </tr>
          <tr style="background-color: {ku_colour};">
            <td style="padding: 4px 6px;"><strong>Neutral axis ratio k<sub>u</sub></strong></td>
            <td style="text-align:right; padding: 4px 6px;">k<sub>u</sub> = {ku_str}</td>
            <td style="text-align:right; padding: 4px 6px;">Limit (teaching) ≤ 0.36</td>
            <td style="text-align:center; padding: 4px 6px;"><strong>{ku_status}</strong></td>
          </tr>
        </tbody>
      </table>
    </div>
    """

    # ---------------- TOP CONTAINER – Title + summary + 3D (like Inputs page) ----------------
    with top_container:
        left_col, right_col = st.columns([0.55, 0.45])

        with left_col:
            st.title("Bending Capacity")
            st.markdown("### Bending – Result Summary")
            # slightly narrower card so it fits beside the 3D plot
            st.markdown(
                summary_html.replace("max-width: 900px", "max-width: 650px"),
                unsafe_allow_html=True,
            )

        with right_col:
            st.markdown("#### 3D neutral axis view")

            # State selector for NA view (ULS / SLS / Uncracked)
            strain_state = st.radio(
                "State:",
                ["ULS", "SLS (cracked)", "Uncracked"],
                horizontal=True,
                key="bending_strain_state",
            )

            fig3d_top = _build_beam_3d_figure(
                b=get_param("b"),
                D=get_param("D"),
                L=get_param("L"),
                Mu_star=Mu_star,
                phi_Mu_cap=phi_Mu_cap_top,
                c=c_top,
                strain_state=strain_state,
            )
            if fig3d_top is not None:
                st.plotly_chart(fig3d_top, use_container_width=True)
            else:
                st.info(
                    "3D beam view will appear once geometry and moment capacity are defined."
                )

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

    # ---------------- Design actions (interactive, aligned with Geometry column) ----------------
    da_col, _ = st.columns(2)

    with da_col:
        st.subheader("Design Actions for Bending")
        sync = sync_callbacks

        # Ensure bending widgets start from shared design actions
        st.session_state["bending_Mu_star"] = get_param("Mu_star") or 0.0
        st.session_state["bending_N_star"] = get_param("N_star") or 0.0
        st.session_state["bending_P_star"] = get_param("P_star") or 0.0

        number_row(
            "Design moment Mu* (kNm)",
            "bending_Mu_star",
            10.0,
            sync,
            help_text=(
                "Factored design bending moment at the critical section. "
                "Increasing Mu* increases bending demand and utilisation."
            ),
        )
        number_row(
            "Axial force N* (kN)",
            "bending_N_star",
            50.0,
            sync,
            help_text=(
                "Axial force acting with bending. Compression (negative in many "
                "conventions) can reduce tension in the steel; tension increases demand."
            ),
        )
        number_row(
            "Prestress force P* (kN)",
            "bending_P_star",
            50.0,
            sync,
            help_text=(
                "Prestress / pre-compression in the section. Increasing P* typically "
                "reduces tensile demand in the bottom reinforcement."
            ),
        )

    st.markdown("---")

    # ---------------- Main inputs ----------------
    g1, g2 = st.columns(2)

    with g1:
        st.subheader("Geometry")
        number_row(
            "Width b (mm)",
            "bending_b",
            10.0,
            sync,
            help_text=(
                "Section width. Increasing b increases compression block area and "
                "reduces required tensile steel for a given Mu*."
            ),
        )
        number_row(
            "Depth D (mm)",
            "bending_D",
            10.0,
            sync,
            help_text=(
                "Overall section depth. Larger D increases lever arm (d) and "
                "typically increases bending capacity."
            ),
        )
        number_row(
            "Span L (mm)",
            "bending_L",
            100.0,
            sync,
            help_text=(
                "Member span. Used mainly for serviceability checks and linking to "
                "deflection; not directly in φMu,cap here."
            ),
        )

    with g2:
        st.subheader("Materials")
        number_row(
            "Concrete strength f'c (MPa)",
            "bending_fc",
            2.0,
            sync,
            help_text=(
                "Concrete compressive strength. Higher f'c increases compression "
                "capacity and may reduce required steel, but also changes ductility limits."
            ),
        )
        number_row(
            "Steel yield fsy (MPa)",
            "bending_fsy",
            10.0,
            sync,
            help_text=(
                "Yield strength of reinforcing steel. Higher fsy increases the "
                "force carried by a given area of steel."
            ),
        )
        number_row(
            "Ec (MPa)",
            "bending_Ec",
            1000.0,
            sync,
            help_text=(
                "Short-term modulus of concrete. Mainly affects stiffness and "
                "SLS behaviour rather than φMu,cap."
            ),
        )
        number_row(
            "Es (MPa)",
            "bending_Es",
            10000.0,
            sync,
            help_text=(
                "Steel modulus. Typically ~200,000 MPa; affects cracked-section "
                "stiffness and strain calculations."
            ),
        )

    st.markdown("---")

    r1, r2 = st.columns(2)

    with r1:
        st.subheader("Bottom Longitudinal Reinforcement")
        number_row(
            "Number of bottom bars nb_bot",
            "bending_nb_bot",
            1,
            sync,
            help_text=(
                "Number of tension bars at the bottom. Increasing nb_bot increases Ast,bot "
                "and hence bending capacity."
            ),
        )
        number_row(
            "Bottom bar diameter db_bot (mm)",
            "bending_db_bot",
            2.0,
            sync,
            help_text=(
                "Nominal diameter of bottom bars (e.g. N24 = 24 mm). Larger diameter "
                "bars increase Ast,bot but may impact spacing and ductility."
            ),
        )
        number_row(
            "Bottom row gap (mm)",
            "bending_rowgap_bot",
            5.0,
            sync,
            help_text=(
                "Vertical clear gap between bottom bar rows (if 2 rows are used). "
                "This affects the centroid depth d of the tensile reinforcement."
            ),
        )
        number_row(
            "Bottom cover (mm)",
            "bending_cover_bot",
            5.0,
            sync,
            help_text=(
                "Concrete cover to bottom reinforcement. Increasing cover reduces "
                "effective depth d and reduces φMu,cap, but may be required for durability."
            ),
        )

    with r2:
        st.subheader("Top Longitudinal Reinforcement")
        number_row(
            "Number of top bars nb_top",
            "bending_nb_top",
            1,
            sync,
            help_text=(
                "Number of top bars (compression or hanger steel). "
                "Important for negative moment regions and detailing."
            ),
        )
        number_row(
            "Top bar diameter db_top (mm)",
            "bending_db_top",
            2.0,
            sync,
            help_text="Nominal diameter of top bars (e.g. N16 = 16 mm).",
        )
        number_row(
            "Top row gap (mm)",
            "bending_rowgap_top",
            5.0,
            sync,
            help_text=(
                "Vertical gap between top bar rows if more than one row is used."
            ),
        )
        number_row(
            "Top cover (mm)",
            "bending_cover_top",
            5.0,
            sync,
            help_text=(
                "Concrete cover to top reinforcement. Affects effective depth to "
                "compression reinforcement and durability."
            ),
        )

    st.markdown("---")

    # ---------------- Detailed summary table (values only) ----------------
    st.subheader("Bending Capacity – Detailed Summary (values only)")

    rows = [
        {"Parameter": "Minimum steel",          "Symbol": "As,min",   "Value": _fmt(As_min, "{:.1f}"),        "Units": "mm²"},
        {"Parameter": "Cracking moment",        "Symbol": "Mcr",      "Value": _fmt(Mcr, "{:.2f}"),           "Units": "kNm"},
        {"Parameter": "Minimum cracking moment","Symbol": "Mu,min",   "Value": _fmt(Mu_min, "{:.2f}"),        "Units": "kNm"},
        {"Parameter": "Gross Z",                "Symbol": "Zg",       "Value": _fmt(Z_gross, "{:.3e}"),       "Units": "mm³"},
        {"Parameter": "α₂",                     "Symbol": "α2",       "Value": _fmt(alpha2_sb, "{:.3f}"),     "Units": "•"},
        {"Parameter": "γ",                      "Symbol": "γ",        "Value": _fmt(gamma_sb, "{:.3f}"),      "Units": "•"},
        {"Parameter": "Strength reduction",     "Symbol": "φb",       "Value": _fmt(phi_b, "{:.3f}"),         "Units": "•"},
        {"Parameter": "Neutral axis depth",     "Symbol": "c",        "Value": _fmt(c, "{:.2f}"),             "Units": "mm"},
        {"Parameter": "Block depth",            "Symbol": "a = γc",   "Value": _fmt(a, "{:.2f}"),             "Units": "mm"},
        {"Parameter": "Neutral axis ratio",     "Symbol": "ku = c/d", "Value": _fmt(ku_sb, "{:.3f}"),         "Units": "•"},
        {"Parameter": "Lever arm",              "Symbol": "z",        "Value": _fmt(z, "{:.2f}"),             "Units": "mm"},
        {"Parameter": "Nominal moment",         "Symbol": "Mu",       "Value": _fmt(Mu_nom_report, "{:.2f}"), "Units": "kNm"},
        {"Parameter": "Design moment cap.",     "Symbol": "φMu,cap",  "Value": _fmt(phi_Mu_cap, "{:.2f}"),    "Units": "kNm"},
        {"Parameter": "Design moment used",     "Symbol": "Mu*",      "Value": _fmt(Mu_star, "{:.2f}"),       "Units": "kNm"},
    ]

    df_summary = pd.DataFrame(rows)
    st.dataframe(df_summary, hide_index=True, use_container_width=True)

    st.markdown("### Section & stress–strain model")

    # Use the same state as the 3D NA selector
    strain_state = st.session_state.get("bending_strain_state", "ULS")

    ss_state = _stress_strain_state(strain_state)
    fig_ss = _plot_stress_strain_profiles(ss_state)
    st.pyplot(fig_ss, use_container_width=True)

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


# ============================
# MAIN GUARD
# ============================
if __name__ == "__main__":
    render_bending()
