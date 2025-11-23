import math
import numpy as np
import plotly.graph_objects as go
import streamlit as st

from state_and_helpers import (
    get_sync_callbacks,
    get_param,
)

from widgets_helpers import apply_global_widget_css, number_row


# ------------------------------------------------------------
#  GLOBAL PAGE STYLING (margins + compact inputs)
# ------------------------------------------------------------
st.markdown(
    """
    <style>
    .main .block-container {
        padding-left: 3rem;
        padding-right: 3rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# Extra CSS so special widgets (side cover + exposure class)
# use the same effective width as the standard number_row inputs.
st.markdown(
    """
    <style>
    .nr-field select,
    .nr-field input {
        width: 100% !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# ------------------------------------------------------------
#  SHARED HELPERS FOR BAR & LEG LAYOUT
# ------------------------------------------------------------
def _two_row_positions_width(n_bars, bar_dia, w_min, w_max):
    """
    Decide bar positions along width for up to 2 rows.

    Rules:
      - A single row can carry at most `max_single` bars based on min spacing.
      - If n_bars > max_single, we use 2 rows and ensure BOTH rows
        respect the same max bars/spacing rule.
      - Row 2:
          * if 1 bar  -> centred
          * if >=2    -> spaced like row 1 (linspace over width)
    """
    if n_bars <= 0:
        return [], []

    span = w_max - w_min
    if span <= 0:
        return [], []

    # basic spacing rule
    min_pitch = max(bar_dia * 1.6, span / 20.0)
    max_single = max(1, int(span // min_pitch))

    # One row OK
    if n_bars <= max_single:
        xs1 = np.linspace(w_min, w_max, n_bars)
        return xs1.tolist(), []

    # Two rows, each respecting max_single
    n1 = min(max_single, math.ceil(n_bars / 2))
    n2 = n_bars - n1
    if n2 > max_single:
        n2 = max_single
        n1 = n_bars - n2

    xs1 = np.linspace(w_min, w_max, n1)

    if n2 <= 0:
        xs2 = np.array([])
    elif n2 == 1:
        xs2 = np.array([(w_min + w_max) / 2.0])
    else:
        xs2 = np.linspace(w_min, w_max, n2)

    return xs1.tolist(), xs2.tolist()


def _internal_leg_positions(y_min, y_max, n_legs):
    """Internal stirrup leg positions across width."""
    if n_legs <= 2:
        return []
    span = y_max - y_min
    if span <= 0:
        return []
    # equally spaced between outer legs
    return [y_min + span * j / (n_legs - 1) for j in range(1, n_legs - 1)]


# ------------------------------------------------------------
#  MINI 2D CROSS-SECTION  (SECTION A)
# ------------------------------------------------------------
def make_summary_cross_section_figure():
    """
    Tiny 2D cross-section using Plotly (visual only).
    Concrete outline + lig cage + bottom/top bars.

    Uses same two-row and leg layout logic as the 3D model,
    plus top, bottom, and side covers.

    Stirrups sit at least 0.5 * max(long bar dia) outside
    the outermost longitudinal bars horizontally.
    """
    # Geometry
    b = float(get_param("b", 400.0) or 400.0)
    D = float(get_param("D", 600.0) or 600.0)

    # Longitudinal reinforcement
    nb_bot = int(get_param("nb_bot", 4) or 0)
    nb_top = int(get_param("nb_top", 2) or 0)
    db_bot = float(get_param("db_bot", 20.0) or 20.0)
    db_top = float(get_param("db_top", 16.0) or 16.0)

    rowgap_bot = float(get_param("rowgap_bot", 60.0) or 60.0)
    rowgap_top = float(get_param("rowgap_top", 60.0) or 60.0)

    cover_bot = float(get_param("cover_bot", 40.0) or 40.0)
    cover_top = float(get_param("cover_top", 40.0) or 40.0)

    # Local-only side cover value (from this page's widget)
    cover_side = float(
        st.session_state.get("inputs_cover_side_local", min(cover_top, cover_bot))
    )

    # Shear reinforcement
    lig_legs_raw = get_param("lig_legs", 2)
    try:
        lig_legs = int(lig_legs_raw or 0)
    except Exception:
        lig_legs = 0

    lig_d = float(get_param("lig_d", 10.0) or 10.0)
    lig_line_width = max(1.0, min(4.0, abs(lig_d) / 3.0))

    shapes = []
    traces = []

    # Max longitudinal bar dia (for bar → lig clearance)
    max_bar_d = max(db_bot, db_top, 0.0)
    horiz_clear = 0.5 * max_bar_d  # minimum centreline gap between lig and bar

    # ----- outer concrete -----
    shapes.append(
        dict(
            type="rect",
            x0=0,
            y0=0,
            x1=b,
            y1=D,
            line=dict(width=1.2, color="black"),
            fillcolor="rgba(0,0,0,0)",
        )
    )

    # ----- lig cage based on covers -----
    cage_x0 = max(cover_side, 5.0)
    cage_x1 = min(b - cover_side, b - 5.0)
    cage_y0 = max(cover_top, 5.0)
    cage_y1 = min(D - cover_bot, D - 5.0)

    shapes.append(
        dict(
            type="rect",
            x0=cage_x0,
            y0=cage_y0,
            x1=cage_x1,
            y1=cage_y1,
            line=dict(width=lig_line_width, color="black"),
            fillcolor="rgba(0,0,0,0)",
        )
    )

    # Internal vertical ties if specified
    if lig_d > 0 and lig_legs > 2:
        for xt in _internal_leg_positions(cage_x0, cage_x1, lig_legs):
            shapes.append(
                dict(
                    type="line",
                    x0=xt,
                    y0=cage_y0,
                    x1=xt,
                    y1=cage_y1,
                    line=dict(width=lig_line_width * 0.8, color="black"),
                )
            )

    # ----- bar positions -----
    x_min = cage_x0 + horiz_clear
    x_max = cage_x1 - horiz_clear
    if x_max <= x_min:
        # fall-back if covers are too big
        mid = 0.5 * (cage_x0 + cage_x1)
        span = max(10.0, (cage_x1 - cage_x0) * 0.4)
        x_min = mid - span / 2.0
        x_max = mid + span / 2.0

    max_bar_d_vertical = max(db_bot, db_top, max(1.0, abs(lig_d)))
    bar_edge_offset = max_bar_d_vertical * 0.8
    y_min_cage = cage_y0 + bar_edge_offset
    y_max_cage = cage_y1 - bar_edge_offset

    # bottom bars
    y1_bot = D - (cover_bot + 0.5 * db_bot)
    y2_bot = y1_bot - rowgap_bot
    min_z_bot = 0.5 * db_bot + 5.0
    max_z_bot = D - 0.5 * db_bot - 5.0
    y1_bot = float(np.clip(y1_bot, max(y_min_cage, min_z_bot), min(y_max_cage, max_z_bot)))
    y2_bot = float(np.clip(y2_bot, max(y_min_cage, min_z_bot), min(y_max_cage, max_z_bot)))

    bx1, bx2 = _two_row_positions_width(nb_bot, db_bot, x_min, x_max)
    bot_x = bx1 + bx2
    bot_y = [y1_bot] * len(bx1) + [y2_bot] * len(bx2)

    # top bars
    y1_top = cover_top + 0.5 * db_top
    y2_top = y1_top + rowgap_top
    min_z_top = 0.5 * db_top + 5.0
    max_z_top = D - 0.5 * db_top - 5.0
    y1_top = float(np.clip(y1_top, max(y_min_cage, min_z_top), min(y_max_cage, max_z_top)))
    y2_top = float(np.clip(y2_top, max(y_min_cage, min_z_top), min(y_max_cage, max_z_top)))

    tx1, tx2 = _two_row_positions_width(nb_top, db_top, x_min, x_max)
    top_x = tx1 + tx2
    top_y = [y1_top] * len(tx1) + [y2_top] * len(tx2)

    if bot_x:
        traces.append(
            go.Scatter(
                x=bot_x,
                y=bot_y,
                mode="markers",
                marker=dict(color="red", size=7, line=dict(width=0.7, color="black")),
                hoverinfo="skip",
                showlegend=False,
            )
        )

    if top_x:
        traces.append(
            go.Scatter(
                x=top_x,
                y=top_y,
                mode="markers",
                marker=dict(color="blue", size=7, line=dict(width=0.7, color="black")),
                hoverinfo="skip",
                showlegend=False,
            )
        )

    if not traces:
        # invisible marker so Plotly doesn't error if no bars
        traces.append(
            go.Scatter(
                x=[0],
                y=[0],
                mode="markers",
                marker=dict(size=1, color="rgba(0,0,0,0)"),
                showlegend=False,
            )
        )

    fig = go.Figure(data=traces)
    fig.update_xaxes(visible=False)
    fig.update_yaxes(
        visible=False,
        scaleanchor="x",
        scaleratio=1,
        range=[D * 1.02, -0.10 * D],
    )
    fig.update_layout(
        width=260,
        height=300,
        margin=dict(l=5, r=5, t=0, b=0),
        shapes=shapes,
        dragmode=False,
        title="Section A",
        title_x=0.5,
    )
    return fig


# ------------------------------------------------------------
#  3D BEAM – BENDING & SHEAR VISUAL  (SECTION A)
# ------------------------------------------------------------
def make_beam_3d_figure():
    # --- parameters from session state ---
    b = float(get_param("b", 400.0) or 400.0)
    D = float(get_param("D", 600.0) or 600.0)
    L = float(get_param("L", 8000.0) or 8000.0)

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

    traces = []

    max_bar_d = max(db_bot, db_top, 0.0)
    horiz_clear = 0.5 * max_bar_d

    # ----- concrete beam -----
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
        )
    )

    # ----- Section A plane at mid-span -----
    mid_x = 0.5 * L
    Yg, Zg = np.meshgrid(np.linspace(0, b, 2), np.linspace(0, D, 2))
    Xg = np.full_like(Yg, mid_x)
    traces.append(
        go.Surface(
            x=Xg,
            y=Yg,
            z=Zg,
            colorscale=[[0, "#3182bd"], [1, "#3182bd"]],
            showscale=False,
            opacity=0.15,
            name="Section A",
        )
    )

    # ----- longitudinal bar positions -----
    def _bar_positions_3d(nbars, bar_dia, cover, rowgap, is_top):
        if nbars <= 0 or bar_dia <= 0:
            return []

        y_min = cover_side + horiz_clear
        y_max = b - cover_side - horiz_clear
        if y_max <= y_min:
            mid = 0.5 * b
            span = max(10.0, (b - 2 * cover_side) * 0.4)
            y_min = mid - span / 2.0
            y_max = mid + span / 2.0

        if is_top:
            z1 = cover + 0.5 * bar_dia
            z2 = z1 + rowgap
        else:
            z1 = D - (cover + 0.5 * bar_dia)
            z2 = z1 - rowgap

        min_z = 0.5 * bar_dia + 5.0
        max_z = D - 0.5 * bar_dia - 5.0
        z1 = float(np.clip(z1, min_z, max_z))
        z2 = float(np.clip(z2, min_z, max_z))

        xs1, xs2 = _two_row_positions_width(nbars, bar_dia, y_min, y_max)
        pos = [(yy, z1) for yy in xs1] + [(yy, z2) for yy in xs2]
        return pos

    # bottom bars
    bot_positions = _bar_positions_3d(nb_bot, db_bot, cover_bot, rowgap_bot, is_top=False)
    line_w_bot = max(2.0, abs(db_bot) * 0.4)
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

    # top bars
    top_positions = _bar_positions_3d(nb_top, db_top, cover_top, rowgap_top, is_top=True)
    line_w_top = max(2.0, abs(db_top) * 0.4)
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

    # ----- shear ligs -----
    def add_shear_hoop_at_x(x0):
        y_left = cover_side
        y_right = b - cover_side
        z_top = cover_top + max(lig_d, 6.0)
        z_bot = D - (cover_bot + max(lig_d, 6.0))

        min_z = 5.0
        max_z = D - 5.0
        z_top_c = float(np.clip(z_top, min_z, max_z))
        z_bot_c = float(np.clip(z_bot, min_z, max_z))

        Xs = [x0] * 5
        Ys = [y_left, y_right, y_right, y_left, y_left]
        Zs = [z_top_c, z_top_c, z_bot_c, z_bot_c, z_top_c]

        lw = max(1.5, abs(lig_d) * 0.35)
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

        if lig_legs > 2:
            for yi in _internal_leg_positions(y_left, y_right, lig_legs):
                traces.append(
                    go.Scatter3d(
                        x=[x0, x0],
                        y=[yi, yi],
                        z=[z_top_c, z_bot_c],
                        mode="lines",
                        line=dict(width=lw * 0.9, color="black"),
                        hoverinfo="skip",
                        showlegend=False,
                    )
                )

    if lig_d > 0 and s_lig > 0 and lig_legs >= 2:
        s_eff = max(40.0, float(s_lig))
        n_hoops = int(max(1, min(80, round(L / s_eff))))
        xs = np.linspace(s_eff / 2.0, L - s_eff / 2.0, n_hoops)
        for x0 in xs:
            add_shear_hoop_at_x(x0)

    fig = go.Figure(data=traces)
    fig.update_layout(
        height=780,  # roughly fills down to crack inputs
        scene=dict(
            xaxis_title="Length (mm)",
            yaxis_title="Width (mm)",
            zaxis_title="Depth from top (mm)",
            zaxis=dict(autorange="reversed"),
            aspectmode="data",
            camera=dict(eye=dict(x=1.45, y=1.35, z=0.95)),
        ),
        margin=dict(l=0, r=0, t=0, b=0),
        showlegend=False,
        title="Section A",
        title_x=0.5,
    )
    return fig


# ------------------------------------------------------------
#  STATUS HELPER
# ------------------------------------------------------------
def _status_and_colour(util, cap_exists):
    if not cap_exists or util is None or math.isnan(util):
        return "Not calculated", "#e0e0e0"
    if util < 0.95:
        return "PASS", "#d5f5d5"
    if util <= 1.0:
        return "NEAR LIMIT", "#fff4c2"
    return "FAIL", "#f8d0d0"


# ------------------------------------------------------------
#  MAIN INPUT PAGE
# ------------------------------------------------------------
def render_inputs():
    sync_callbacks = get_sync_callbacks()
    apply_global_widget_css()

    # ---------- summary values ----------
    Mu_star = get_param("Mu_star", 0.0)
    Vu_star = get_param("Vu_star", 0.0)

    phi_Mu_cap = get_param("phi_Mu_cap", 0.0)
    Mu_util = get_param("Mu_utilisation", 0.0)

    phi_Vu_cap = get_param("phi_Vu_cap", 0.0)
    Vu_util = get_param("Vu_utilisation", 0.0)

    crack_width = get_param("crack_width", 0.0)
    crack_util = get_param("crack_utilisation", 0.0)

    L = get_param("L", 3000.0)
    b = get_param("b", 400.0)
    D = get_param("D", 600.0)
    Ec = get_param("Ec", 30000.0)

    phi_creep = st.session_state.get("creep_phi_design", None)
    Ec_eff_design = st.session_state.get("Ec_eff_design", None)
    eps_sh_micro = st.session_state.get("shrinkage_eps_design", None)

    if Ec_eff_design is not None and Ec_eff_design > 0:
        k_creep = Ec / Ec_eff_design
    elif phi_creep is not None and phi_creep > 0:
        k_creep = 1.0 + phi_creep
    else:
        k_creep = 1.0

    eps_sh = (eps_sh_micro or 0.0) / 1e6

    if L > 0:
        w_total = 8.0 * Mu_star / (L / 1000.0) ** 2  # kN/m
    else:
        w_total = 0.0

    b_mm = max(1.0, b)
    D_mm = max(1.0, D)
    L_mm = max(1.0, L)
    I_gross = b_mm * D_mm**3 / 12.0 if b_mm > 0 and D_mm > 0 else 1.0

    delta_inst = 5.0 * w_total * L_mm**4 / (384.0 * Ec * I_gross) if Ec > 0 else 0.0
    delta_creep = delta_inst * k_creep
    phi_sh = eps_sh / (0.7 * D_mm) if D_mm > 0 else 0.0
    delta_sh = phi_sh * L_mm**2 / 8.0
    delta_total = delta_creep + delta_sh

    defl_limit = L_mm / 250.0 if L_mm > 0 else 0.0
    defl_util = delta_total / defl_limit if defl_limit > 0 else 0.0

    # ---------- summary strings ----------
    bending_demand = f"{Mu_star:.1f} kNm"
    bending_cap = f"{phi_Mu_cap:.1f} kNm" if phi_Mu_cap > 0 else "—"
    bending_util_str = f"{Mu_util:.2f}" if phi_Mu_cap > 0 else "—"
    bending_status, bending_colour = _status_and_colour(Mu_util, phi_Mu_cap > 0)

    shear_demand = f"{Vu_star:.1f} kN"
    shear_cap = f"{phi_Vu_cap:.1f} kN" if phi_Vu_cap > 0 else "—"
    shear_util_str = f"{Vu_util:.2f}" if phi_Vu_cap > 0 else "—"
    shear_status, shear_colour = _status_and_colour(Vu_util, phi_Vu_cap > 0)

    crack_demand = f"{crack_width:.3f} mm"
    crack_cap = "w_lim" if crack_util > 0 else "—"
    crack_util_str = f"{crack_util:.2f}" if crack_util > 0 else "—"
    crack_status, crack_colour = _status_and_colour(crack_util, crack_util > 0)

    defl_demand = f"{delta_total:.2f} mm"
    defl_cap = f"{defl_limit:.2f} mm" if defl_limit > 0 else "—"
    defl_util_str = f"{defl_util:.2f}" if defl_limit > 0 else "—"
    defl_status, defl_colour = _status_and_colour(defl_util, defl_limit > 0)

    summary_table_html = f"""
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
            <th style="text-align:left; padding: 4px 6px;">Check</th>
            <th style="text-align:right; padding: 4px 6px;">Demand</th>
            <th style="text-align:right; padding: 4px 6px;">Capacity</th>
            <th style="text-align:right; padding: 4px 6px;">Utilisation</th>
            <th style="text-align:center; padding: 4px 6px;">Status</th>
          </tr>
        </thead>
        <tbody>
          <tr style="background-color: {bending_colour};">
            <td style="padding: 4px 6px;"><strong>Bending</strong></td>
            <td style="text-align:right; padding: 4px 6px;">{bending_demand}</td>
            <td style="text-align:right; padding: 4px 6px;">{bending_cap}</td>
            <td style="text-align:right; padding: 4px 6px;">{bending_util_str}</td>
            <td style="text-align:center; padding: 4px 6px;"><strong>{bending_status}</strong></td>
          </tr>
          <tr style="background-color: {shear_colour};">
            <td style="padding: 4px 6px;"><strong>Shear</strong></td>
            <td style="text-align:right; padding: 4px 6px;">{shear_demand}</td>
            <td style="text-align:right; padding: 4px 6px;">{shear_cap}</td>
            <td style="text-align:right; padding: 4px 6px;">{shear_util_str}</td>
            <td style="text-align:center; padding: 4px 6px;"><strong>{shear_status}</strong></td>
          </tr>
          <tr style="background-color: {crack_colour};">
            <td style="padding: 4px 6px;"><strong>Crack control</strong></td>
            <td style="text-align:right; padding: 4px 6px;">{crack_demand}</td>
            <td style="text-align:right; padding: 4px 6px;">{crack_cap}</td>
            <td style="text-align:right; padding: 4px 6px;">{crack_util_str}</td>
            <td style="text-align:center; padding: 4px 6px;"><strong>{crack_status}</strong></td>
          </tr>
          <tr style="background-color: {defl_colour};">
            <td style="padding: 4px 6px;"><strong>Deflection</strong></td>
            <td style="text-align:right; padding: 4px 6px;">{defl_demand}</td>
            <td style="text-align:right; padding: 4px 6px;">{defl_cap}</td>
            <td style="text-align:right; padding: 4px 6px;">{defl_util_str}</td>
            <td style="text-align:center; padding: 4px 6px;"><strong>{defl_status}</strong></td>
          </tr>
        </tbody>
      </table>
    </div>
    """

    # ---------- summary + mini section ----------
    col_left, col_right = st.columns([2, 1])
    with col_left:
        st.title("Inputs")
        st.markdown("### Summary (read-only from design pages)")
        st.markdown(summary_table_html, unsafe_allow_html=True)

    with col_right:
        fig_sec = make_summary_cross_section_figure()
        st.plotly_chart(fig_sec, use_container_width=False, config={"displayModeBar": False})

    st.markdown("---")

    # ---------- inputs + 3D beam ----------
    left_col, right_col = st.columns([1.2, 1.8])

    with left_col:
        st.subheader("Design Actions")
        number_row("Design moment Mu* (kNm)", "inputs_Mu_star", 10.0, sync_callbacks)
        number_row("Applied prestress P* (kN)", "inputs_P_star", 10.0, sync_callbacks)
        number_row("Design torsion Tu* (kNm)", "inputs_Tu_star", 1.0, sync_callbacks)
        number_row("Design shear Vu* (kN)", "inputs_Vu_star", 10.0, sync_callbacks)
        number_row("Axial force N* (kN)", "inputs_N_star", 10.0, sync_callbacks)

        st.markdown("---")

        st.subheader("Geometry")
        number_row("Width b (mm)", "inputs_b", 10.0, sync_callbacks)
        number_row("Depth D (mm)", "inputs_D", 10.0, sync_callbacks)
        number_row("Span L (mm)", "inputs_L", 100.0, sync_callbacks)

        st.markdown("---")

        st.subheader("Materials")
        number_row("Concrete strength f'c (MPa)", "inputs_fc", 2.0, sync_callbacks)
        number_row("Steel yield fsy (MPa)", "inputs_fsy", 10.0, sync_callbacks)
        number_row("Ec (MPa)", "inputs_Ec", 1000.0, sync_callbacks)
        number_row("Es (MPa)", "inputs_Es", 5000.0, sync_callbacks)

    with right_col:
        st.subheader("3D Beam – Bending & Shear Visual (Section A)")
        fig3d = make_beam_3d_figure()
        st.plotly_chart(fig3d, use_container_width=True)

    st.markdown("---")

    # ---------- reo + shear + crack ----------
    reo_col, crack_col = st.columns(2)

    # left column: bottom reo + side cover + shear
    with reo_col:
        st.subheader("Bottom Reinforcement")
        number_row("Number of bottom bars", "inputs_nb_bot", 1, sync_callbacks)
        number_row("Bottom bar diameter db,bot (mm)", "inputs_db_bot", 1.0, sync_callbacks)
        number_row("Bottom row gap (mm)", "inputs_rowgap_bot", 5.0, sync_callbacks)
        number_row("Bottom cover (mm)", "inputs_cover_bot", 5.0, sync_callbacks)

        # side cover – local only, styled like the others
        cover_top_val = float(get_param("cover_top", 40.0) or 40.0)
        cover_bot_val = float(get_param("cover_bot", 40.0) or 40.0)
        default_side_cover = min(cover_top_val, cover_bot_val)

        # NOTE: column split [1.3, 1] to match number_row label/input ratio
        sc_label_col, sc_input_col = st.columns([1.3, 1])
        with sc_label_col:
            st.markdown("Side cover (mm)")
        with sc_input_col:
            # Wrap input in nr-field div so CSS forces same width
            st.markdown('<div class="nr-field">', unsafe_allow_html=True)
            st.number_input(
                "",
                value=float(
                    st.session_state.get("inputs_cover_side_local", default_side_cover)
                ),
                step=1.0,
                key="inputs_cover_side_local",
                label_visibility="collapsed",
            )
            st.markdown("</div>", unsafe_allow_html=True)

        st.subheader("Shear reinforcement")
        number_row("Lig diameter (mm)", "inputs_lig_d", 1.0, sync_callbacks)
        number_row("Lig legs", "inputs_lig_legs", 1, sync_callbacks)
        number_row("Stirrup spacing s_lig (mm)", "inputs_s_lig", 10.0, sync_callbacks)

    # right column: top reo + crack control
    with crack_col:
        st.subheader("Top Reinforcement")
        number_row("Number of top bars", "inputs_nb_top", 1, sync_callbacks)
        number_row("Top bar diameter db,top (mm)", "inputs_db_top", 1.0, sync_callbacks)
        number_row("Top row gap (mm)", "inputs_rowgap_top", 5.0, sync_callbacks)
        number_row("Top cover (mm)", "inputs_cover_top", 5.0, sync_callbacks)

        st.subheader("Crack Control Inputs")

        # Exposure class – same size & alignment as others
        options = ["A1", "A2", "B1", "B2", "C1", "C2"]
        current = get_param("exposure_class", "B1")
        if current not in options:
            current = "B1"

        # NOTE: column split [1.3, 1] to match number_row label/input ratio
        exp_label_col, exp_select_col = st.columns([1.3, 1])
        with exp_label_col:
            st.markdown("Exposure class")
        with exp_select_col:
            st.markdown('<div class="nr-field">', unsafe_allow_html=True)
            if "inputs_exposure_class" in st.session_state:
                st.selectbox(
                    "",
                    options,
                    key="inputs_exposure_class",
                    on_change=sync_callbacks["inputs_exposure_class"],
                    label_visibility="collapsed",
                )
            else:
                st.selectbox(
                    "",
                    options,
                    key="inputs_exposure_class",
                    index=options.index(current),
                    on_change=sync_callbacks["inputs_exposure_class"],
                    label_visibility="collapsed",
                )
            st.markdown("</div>", unsafe_allow_html=True)

        number_row(
            "Bottom bar spacing for crack calc (mm)",
            "inputs_s_bar_bot",
            5.0,
            sync_callbacks,
        )
