
import math
import numpy as np
import plotly.graph_objects as go
import streamlit as st
import streamlit.components.v1 as components

from state_and_helpers import (
    get_sync_callbacks,
    get_param,
    update_results,
)

from widgets_helpers import apply_global_widget_css, apply_calcbox_css, number_row, calcbox, show_reo_message, label_with_hover

# --- Pure compute functions from design core (no circular imports)
from bending_core import _compute_bending_capacity
from shear_core import _compute_shear_capacity
from crack_core import _compute_crack_results
from deflection_core import _compute_deflection_results
from section_layout import compute_section_layout
# from deflection import _compute_deflection_results  # TODO: add later


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

# CSS for clickable summary rows (details + CSS grid)
st.markdown(
    """
<style>
/* Remove gaps around <details> blocks and their summary */
.inputs-summary-details {
  margin: 0;
  padding: 0;
}

/* Make summary a normal block container */
.inputs-summary-details > summary {
  cursor: pointer;
  margin: 0;
  padding: 0;
  display: block;
  list-style: none;  /* for some browsers */
}

/* Hide the default arrow/marker in ALL browsers */
.inputs-summary-details > summary::-webkit-details-marker {
  display: none;
}

.inputs-summary-details > summary::marker {
  content: "";
  display: none;
}

/* Outer container */
.inputs-summary-container {
  border: 1px solid #cccccc;
  border-radius: 8px;
  padding: 0.5rem 0.75rem 0.4rem 0.75rem;
  margin-bottom: 1rem;
  max-width: 900px;
  font-size: 0.9rem;
}

/* Shared 5-column grid for header + rows */
.inputs-summary-grid {
  display: grid;
  grid-template-columns: 30% 20% 20% 15% 15%;
  align-items: center;
}

/* Header row */
.inputs-summary-header {
  background-color: #f5f5f5;
  font-weight: 600;
  padding: 4px 6px;
  border-bottom: 1px solid #e0e0e0;
}
.inputs-summary-header div {
  padding: 4px 6px;
}

/* Banner rows (Bending/Shear/Crack/Deflection) */
.inputs-summary-row {
  padding: 4px 6px;
}

/* Children inside the row (now spans, not divs) */
.inputs-summary-row > * {
  padding: 4px 6px;
}

.inputs-summary-row .col-check {
  text-align: left;
}
.inputs-summary-row .col-demand,
.inputs-summary-row .col-cap,
.inputs-summary-row .col-util {
  text-align: right;
}
.inputs-summary-row .col-status {
  text-align: center;
  font-weight: 600;
}

/* Box for the drop-down detail table */
.inputs-summary-detail-wrapper {
  margin: 0;
  padding: 0.35rem 0.5rem 0.6rem 0.5rem;
  background-color: #fafafa;
  border-top: 1px solid #e0e0e0;
}

/* Hide any escaped closing tags that Streamlit might render as inline code
   inside this container (defensive only) */
.inputs-summary-container code {
  display: none !important;
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

    NOW uses compute_longitudinal_reo_layout() as single source of truth.
    """
    from section_layout import compute_longitudinal_reo_layout
    
    layout = compute_section_layout()

    b = layout["b"]
    D = layout["D"]
    cage = layout["cage"]
    lig = layout["lig"]
    reo_layout = layout.get("reo_layout")  # Get 2-layer structure

    lig_d = lig["d"]
    lig_legs = lig["legs"]
    lig_line_width = max(1.0, min(4.0, abs(lig_d) / 3.0))

    shapes = []
    traces = []

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

    # ----- Shear reinforcement (stirrups/ties) - only draw when present -----
    # Only draw shear reinforcement if it's actually specified
    has_shear = lig_d > 0 and lig_legs >= 2
    
    if has_shear:
        from section_layout import compute_shear_reo_layout_pure
        
        cover_bot = float(get_param("cover_bot", 40.0) or 40.0)
        cover_top = float(get_param("cover_top", 40.0) or 40.0)
        cover_side = float(
            st.session_state.get("inputs_cover_side_local", min(cover_top, cover_bot))
        )
        
        shear_layout = compute_shear_reo_layout_pure(
            b=b, D=D,
            cover_bot=cover_bot, cover_top=cover_top, cover_side=cover_side,
            lig_d=lig_d, lig_legs=lig_legs,
        )
        
        # Draw cage outline (only when shear reo is present)
        cage_shear = shear_layout.get("cage", cage)
        shapes.append(
            dict(
                type="rect",
                x0=cage_shear["x0"],
                y0=cage_shear["y0"],
                x1=cage_shear["x1"],
                y1=cage_shear["y1"],
                line=dict(width=lig_line_width, color="black"),
                fillcolor="rgba(0,0,0,0)",
            )
        )
        
        # Draw stirrup legs in black
        for stirrup in shear_layout.get("stirrups", []):
            for leg in stirrup.get("legs", []):
                shapes.append(
                    dict(
                        type="line",
                        x0=leg["x1"],
                        y0=leg["y1"],
                        x1=leg["x2"],
                        y1=leg["y2"],
                        line=dict(width=lig_line_width * 0.8, color="black"),
                    )
                )

    # ----- bottom bars - use 2-layer structure -----
    # BOTTOM reinforcement is BLUE
    if reo_layout:
        for layer_data in reo_layout["bottom"]:
            x_positions = layer_data["x"]
            y_pos = layer_data["y"]
            db = layer_data["db"]
            # Marker size based on bar diameter
            marker_size = max(5, min(10, db * 0.35))
            traces.append(
                go.Scatter(
                    x=x_positions,
                    y=[y_pos] * len(x_positions),
                    mode="markers",
                    marker=dict(
                        color="blue", size=marker_size, line=dict(width=0.7, color="black")
                    ),
                    hoverinfo="skip",
                    showlegend=False,
                )
            )
    else:
        # Fallback to legacy structure
        bot = layout.get("bot", {})
        if bot.get("x"):
            traces.append(
                go.Scatter(
                    x=bot["x"],
                    y=bot["y"],
                    mode="markers",
                    marker=dict(
                        color="blue", size=7, line=dict(width=0.7, color="black")
                    ),
                    hoverinfo="skip",
                    showlegend=False,
                )
            )

    # ----- top bars - use 2-layer structure -----
    # TOP reinforcement is RED
    if reo_layout:
        for layer_data in reo_layout["top"]:
            x_positions = layer_data["x"]
            y_pos = layer_data["y"]
            db = layer_data["db"]
            # Marker size based on bar diameter
            marker_size = max(5, min(10, db * 0.35))
            traces.append(
                go.Scatter(
                    x=x_positions,
                    y=[y_pos] * len(x_positions),
                    mode="markers",
                    marker=dict(
                        color="red", size=marker_size, line=dict(width=0.7, color="black")
                    ),
                    hoverinfo="skip",
                    showlegend=False,
                )
            )
    else:
        # Fallback to legacy structure
        top = layout.get("top", {})
        if top.get("x"):
            traces.append(
                go.Scatter(
                    x=top["x"],
                    y=top["y"],
                    mode="markers",
                    marker=dict(
                        color="red", size=7, line=dict(width=0.7, color="black")
                    ),
                    hoverinfo="skip",
                    showlegend=False,
                )
            )

    if not traces:
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
        width=345,
        height=450,
        margin=dict(l=0, r=0, t=0, b=40),
        shapes=shapes,
        dragmode=False,
        # no title – label is added in Streamlit below the figure
    )
    return fig


# ------------------------------------------------------------
#  3D BEAM – BENDING & SHEAR VISUAL  (SECTION A)
# ------------------------------------------------------------
def make_beam_3d_figure():
    # --- parameters from session state ---
    # Use cached layout for performance
    from section_layout import compute_section_layout_cached
    
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

    # ----- longitudinal bar positions - use cached layout function -----
    # Get 2-layer parameters
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
    
    cover_bot = float(get_param("cover_bot", 40.0) or 40.0)
    cover_top = float(get_param("cover_top", 40.0) or 40.0)
    cover_side = float(
        get_param("cover_side", min(cover_top, cover_bot)) or min(cover_top, cover_bot)
    )
    
    # Get layout from cached function
    cached_layout = compute_section_layout_cached(
        b=b, D=D,
        cover_bot=cover_bot, cover_top=cover_top, cover_side=cover_side,
        nb_or_s_bot_1=nb_or_s_bot_1, db_bot_1=db_bot_1,
        nb_or_s_bot_2=nb_or_s_bot_2, db_bot_2=db_bot_2,
        nb_or_s_top_1=nb_or_s_top_1, db_top_1=db_top_1,
        nb_or_s_top_2=nb_or_s_top_2, db_top_2=db_top_2,
        rowgap_bot=rowgap_bot, rowgap_top=rowgap_top,
        lig_legs=lig_legs, lig_d=lig_d,
    )
    reo_layout = cached_layout.get("reo_layout")
    
    # Bottom bars - draw each layer separately
    # BOTTOM reinforcement is BLUE
    for layer_data in reo_layout["bottom"]:
        x_positions = layer_data["x"]
        y_pos = layer_data["y"]  # This is the y coordinate in 2D (section view)
        db = layer_data["db"]
        # Convert 2D y to 3D z (y in 2D section = z in 3D beam)
        z_pos = y_pos
        line_w = max(2.0, abs(db) * 0.4)
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
        line_w = max(2.0, abs(db) * 0.4)
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

    # Subtle frame around the whole plotting area (this figure only)
    fig.add_shape(
        type="rect",
        x0=0, y0=0, x1=1, y1=1,
        xref="paper", yref="paper",
        line=dict(color="#999999", width=2),
    )

    fig.update_layout(
        height=480,     # was 780 → now much shorter
        paper_bgcolor="white",
        plot_bgcolor="white",
        scene=dict(
            xaxis_title="Length (mm)",
            yaxis_title="Width (mm)",
            zaxis_title="Depth from top (mm)",
            zaxis=dict(autorange="reversed"),
            aspectmode="data",
            camera=dict(eye=dict(x=1.45, y=1.35, z=0.95)),
            annotations=[
                dict(
                    x=mid_x,
                    y=0.5 * b,
                    z=0.5 * D,
                    text="Section A",
                    showarrow=True,
                    arrowhead=2,
                    arrowsize=1.4,
                    arrowwidth=2,
                    arrowcolor="black",
                    ax=80,
                    ay=-80,
                    font=dict(size=16, color="black"),
                )
            ],
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
def _safe_ratio(num, den):
    """
    Return num/den, but:
      - if den is 0, None or NaN -> return None (treated as 'Not calculated').
    """
    try:
        if den is None:
            return None
        # protect against NaN
        if isinstance(den, float) and math.isnan(den):
            return None
        if den == 0:
            return None
        return num / den
    except Exception:
        return None


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
    apply_calcbox_css()

    summary_container = st.container()

    st.markdown("---")

    # ============================
    # 1. TOP ROW – Actions | Geometry | Materials
    # ============================
    col_actions, col_geom, col_mat = st.columns(3)

    # --- Design actions ---
    with col_actions:
        # Heading row with info popover for source of design actions
        col_title, col_info = st.columns([0.92, 0.08])
        with col_title:
            st.subheader("Design Actions")
        with col_info:
            with st.popover("ℹ️", help="Source of design actions (M*, V*)"):
                action_source = st.radio(
                    "Source of design actions (M*, V*)",
                    [
                        "Manual design actions (inputs below)",
                        "Teaching SFD/BMD page (|M|max, |V|max)",
                    ],
                    key="inputs_actions_source",
                    on_change=sync_callbacks["inputs_actions_source"],
                )
        
        # Show caption with current mode
        current_source = st.session_state.get("inputs_actions_source", "Manual design actions (inputs below)")
        if current_source == "Manual design actions (inputs below)":
            st.caption("Design actions: Manual inputs")
        else:
            st.caption("Design actions: From SFD/BMD")
        
        # Teaching values from SFD/BMD page (stored directly in session_state, may be None first time)
        M_sfd = get_param("sfd_Mmax_abs_kNm", None)
        V_sfd = get_param("sfd_Vmax_abs_kN", None)
        L_sfd = get_param("sfd_span_L_m", None)
        # sfd_case is a widget key, read it directly from session_state
        case_sfd = st.session_state.get("sfd_case", None)

        number_row(
            "Design moment Mu* (kNm)",
            "inputs_Mu_star",
            10.0,
            sync_callbacks,
            help_text="Factored design bending moment at the critical section.",
        )

        number_row(
            "Applied prestress P* (kN)",
            "inputs_P_star",
            10.0,
            sync_callbacks,
            help_text="Net prestress force at the section (compression positive).",
        )

        number_row(
            "Design torsion Tu* (kNm)",
            "inputs_Tu_star",
            1.0,
            sync_callbacks,
            help_text="Factored torsion; used on torsion page (placeholder here).",
        )

        number_row(
            "Design shear Vu* (kN)",
            "inputs_Vu_star",
            10.0,
            sync_callbacks,
            help_text="Factored design shear at the critical section.",
        )

        number_row(
            "Axial force N* (kN)",
            "inputs_N_star",
            10.0,
            sync_callbacks,
            help_text="Axial action at the section (+compression / −tension).",
        )

    # --- Geometry ---
    with col_geom:
        st.subheader("Geometry")

        number_row(
            "Width b (mm)",
            "inputs_b",
            10.0,
            sync_callbacks,
            help_text="Beam/web width.",
        )

        number_row(
            "Depth D (mm)",
            "inputs_D",
            10.0,
            sync_callbacks,
            help_text="Overall section depth from compression face to soffit.",
        )

        number_row(
            "Span L (mm)",
            "inputs_L",
            100.0,
            sync_callbacks,
            help_text="Clear span used for deflection checks.",
        )

        number_row(
            "Bottom cover (mm)",
            "inputs_cover_bot",
            5.0,
            sync_callbacks,
            help_text="Clear cover to the bottom bars.",
        )

        number_row(
            "Top cover (mm)",
            "inputs_cover_top",
            5.0,
            sync_callbacks,
            help_text="Clear cover to the top bars.",
        )

        number_row(
            "Side cover (mm)",
            "inputs_cover_side",
            5.0,
            sync_callbacks,
            help_text="Clear side cover to longitudinal reinforcement and ducts.",
        )

    # --- Materials ---
    with col_mat:
        st.subheader("Materials")

        number_row(
            "Concrete strength f'c (MPa)",
            "inputs_fc",
            2.0,
            sync_callbacks,
            help_text="Characteristic compressive strength of concrete.",
        )

        number_row(
            "Steel yield fsy (MPa)",
            "inputs_fsy",
            10.0,
            sync_callbacks,
            help_text="Yield stress of flexural reinforcement.",
        )

        number_row(
            "Ec (MPa)",
            "inputs_Ec",
            1000.0,
            sync_callbacks,
            help_text="Short-term modulus of elasticity of concrete.",
        )

        number_row(
            "Es (MPa)",
            "inputs_Es",
            5000.0,
            sync_callbacks,
            help_text="Elastic modulus of reinforcing steel.",
        )

    st.markdown("---")

    # ============================
    # 2. SECOND ROW – Bottom | Top | Shear
    # ============================
    col_bot_reo, col_top_reo, col_shear = st.columns(3)

    # --- Bottom reo ---
    with col_bot_reo:
        st.subheader("Bottom Longitudinal Reinforcement")
        
        number_row(
            "Layer 1: bars or spacing (≤30 = bars, ≥30 = mm)",
            "inputs_nb_or_s_bot_1",
            1.0,
            sync_callbacks,
            help_text="Enter a number of bars (≤30) or a spacing in mm (≥30).",
        )

        number_row(
            "Layer 1: bar diameter db,bot,1 (mm)",
            "inputs_db_bot_1",
            1.0,
            sync_callbacks,
            help_text="Nominal diameter of bottom Layer 1 bars.",
        )
        
        number_row(
            "Layer 2: bars or spacing (≤30 = bars, ≥30 = mm)",
            "inputs_nb_or_s_bot_2",
            1.0,
            sync_callbacks,
            help_text="Enter a number of bars (≤30) or a spacing in mm (≥30). Auto-updated if Layer 1 doesn't fit.",
        )

        number_row(
            "Layer 2: bar diameter db,bot,2 (mm)",
            "inputs_db_bot_2",
            1.0,
            sync_callbacks,
            help_text="Nominal diameter of bottom Layer 2 bars.",
        )

        number_row(
            "Bottom row gap (mm)",
            "inputs_rowgap_bot",
            5.0,
            sync_callbacks,
            help_text="Vertical gap between bottom rows if two layers are used.",
        )

    # --- Top reo ---
    with col_top_reo:
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
        
        number_row(
            "Layer 1: bars or spacing (≤30 = bars, ≥30 = mm)",
            "inputs_nb_or_s_top_1",
            1.0,
            sync_callbacks,
            help_text="Enter a number of bars (≤30) or a spacing in mm (≥30).",
        )

        number_row(
            "Layer 1: bar diameter db,top,1 (mm)",
            "inputs_db_top_1",
            1.0,
            sync_callbacks,
            help_text="Nominal diameter of top Layer 1 bars.",
        )
        
        number_row(
            "Layer 2: bars or spacing (≤30 = bars, ≥30 = mm)",
            "inputs_nb_or_s_top_2",
            1.0,
            sync_callbacks,
            help_text="Enter a number of bars (≤30) or a spacing in mm (≥30). Auto-updated if Layer 1 doesn't fit.",
        )

        number_row(
            "Layer 2: bar diameter db,top,2 (mm)",
            "inputs_db_top_2",
            1.0,
            sync_callbacks,
            help_text="Nominal diameter of top Layer 2 bars.",
        )

        number_row(
            "Top row gap (mm)",
            "inputs_rowgap_top",
            5.0,
            sync_callbacks,
            help_text="Vertical gap between top rows if two layers are used.",
        )

    # --- Shear reo (same row) ---
    with col_shear:
        st.subheader("Shear reinforcement")

        number_row(
            "Lig diameter (mm)",
            "inputs_lig_d",
            1.0,
            sync_callbacks,
            help_text="Nominal diameter of shear ligatures.",
        )

        number_row(
            "Lig legs",
            "inputs_lig_legs",
            1,
            sync_callbacks,
            help_text="Number of legs in each ligature crossing the web.",
        )

        number_row(
            "Stirrup spacing s_lig (mm)",
            "inputs_s_lig",
            10.0,
            sync_callbacks,
            help_text="Centre-to-centre spacing of shear ligatures along the span.",
        )

    st.markdown("---")

    # ============================
    # 3. THIRD ROW – 3D beam (centred, narrower, with frame from Plotly)
    # ============================
    st.subheader("3D Beam – Bending & Shear Visual (Section A)")

    fig3d = make_beam_3d_figure()

    # centre the model and make it a bit narrower than full page
    c_left, c_mid, c_right = st.columns([0.2, 0.6, 0.2])
    with c_mid:
        st.plotly_chart(fig3d, use_container_width=True)

    st.markdown("---")

    # ============================
    # 4. FOURTH ROW – Rest of inputs (Time | Crack/Ducts)
    # ============================
    col_time, col_right = st.columns(2)

    # --- Time-dependent inputs ---
    with col_time:
        st.subheader("Time-dependent inputs")

        number_row(
            "Creep time after loading t (days)",
            "inputs_t_creep",
            1.0,
            sync_callbacks,
            help_text="Time after loading used for creep coefficient φ_cc,t.",
        )

        number_row(
            "Age at loading τ (days)",
            "inputs_age_at_loading",
            1.0,
            sync_callbacks,
            help_text="Concrete age at application of sustained load.",
        )

        number_row(
            "Sustained stress ratio σ₀ / f'c,mi",
            "inputs_stress_ratio",
            0.01,
            sync_callbacks,
            help_text="Ratio of sustained stress to mean in-situ strength.",
        )

        number_row(
            "Shrinkage time since drying t (days)",
            "inputs_t_shrink",
            1.0,
            sync_callbacks,
            help_text="Duration of drying used in shrinkage calculation.",
        )

    # --- Crack control + Ducts ---
    with col_right:
        st.subheader("Crack Control Inputs")

        options = ["A1", "A2", "B1", "B2", "C1", "C2"]

        current = get_param("exposure_class", "B1")

        if current not in options:
            current = "B1"

        col_exp_label, col_exp_input = st.columns([1, 2])
        with col_exp_label:
            label_with_hover("Exposure class", "Exposure classification to AS 3600 – controls allowable crack width.")
        with col_exp_input:
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

        number_row(
            "Bottom bar spacing for crack calc (mm)",
            "inputs_s_bar_bot",
            5.0,
            sync_callbacks,
            help_text="Centre-to-centre spacing of bottom bars used in crack-width check.",
        )

        st.subheader("Ducts / Prestress voids")

        number_row(
            "Number of ducts crossing web",
            "inputs_n_ducts",
            1.0,
            sync_callbacks,
            help_text="Total number of ducts crossing the web in the shear zone.",
        )

        number_row(
            "Duct diameter (mm)",
            "inputs_duct_dia",
            1.0,
            sync_callbacks,
            help_text="Nominal diameter of each duct.",
        )

    # ============================
    # 4. Determine final actions (manual vs teaching)
    # ============================
    # Read manual values (from Inputs widgets via TAB_KEYS)
    Mu_manual_raw = get_param("Mu_star_manual", None)
    Vu_manual_raw = get_param("Vu_star_manual", None)

    # Fall back to the existing design values if the manual copies
    # are still None/0.0 (e.g. old sessions or before first edit)
    base_M = get_param("Mu_star", 0.0)
    base_V = get_param("Vu_star", 0.0)

    Mu_manual = (
        Mu_manual_raw
        if (Mu_manual_raw is not None and Mu_manual_raw != 0.0)
        else base_M
    )
    Vu_manual = (
        Vu_manual_raw
        if (Vu_manual_raw is not None and Vu_manual_raw != 0.0)
        else base_V
    )

    # Decide if we can actually use teaching values
    use_sfd = (
        action_source == "Teaching SFD/BMD page (|M|max, |V|max)"
        and M_sfd is not None
        and V_sfd is not None
    )

    if use_sfd:
        Mu_star = float(M_sfd)
        Vu_star = float(V_sfd)
        source_label = "Teaching SFD/BMD page (|M|max, |V|max)"
        extra_note = ""
    else:
        # Either manual selected, or teaching has no results yet
        Mu_star = float(Mu_manual)
        Vu_star = float(Vu_manual)
        source_label = "Manual design actions (inputs below)"
        extra_note = ""
        if (
            action_source == "Teaching SFD/BMD page (|M|max, |V|max)"
            and (M_sfd is None or V_sfd is None)
        ):
            extra_note = (
                " (Teaching SFD/BMD selected, but no SFD/BMD "
                "results found yet – using manual actions until you "
                "visit the SFD/BMD page.)"
            )


    # Push final chosen actions into results for all downstream pages
    update_results(
        actions_source=source_label,
        Mu_star=float(Mu_star),
        Mu_star_kNm=float(Mu_star),
        Vu_star=float(Vu_star),
        Vu_star_kN=float(Vu_star),
    )

    # ============================
    # 5. Recompute + Summary (read from all design pages)
    # ============================
    # Recompute ALL checks using current inputs (ensures consistent snapshot)
    _compute_bending_capacity()
    _compute_shear_capacity()
    _compute_crack_results()
    _compute_deflection_results()

    # Read all results (now freshly computed above)
    
    # --- Bending (from bending_core.py via _compute_bending_capacity) ---
    phi_Mu_cap = get_param("phi_Mu_cap", 0.0)
    Mu_util = get_param("Mu_utilisation", 0.0)

    # --- Shear (from shear_core.py via _compute_shear_capacity) ---
    phi_Vu_cap = get_param("phi_Vu_cap", 0.0)
    Vu_util = get_param("Vu_utilisation", 0.0)
    
    # Concrete strut / crushing check (from shear_core.py)
    phi_Vuc_cap = get_param("phi_Vu_max_kN", None)  # kN, capacity of compression strut
    Vuc_util = get_param("Vuc_utilisation", None)  # utilisation for crushing
    Vuc_cap_str = f"{phi_Vuc_cap:.2f} kN" if phi_Vuc_cap not in (None, 0) else "—"
    Vuc_util_str = f"{Vuc_util:.3f}" if Vuc_util is not None else "—"
    Vuc_status, Vuc_colour = _status_and_colour(
        Vuc_util, Vuc_util is not None
    )

    # --- Crack control (from crack_page.py) ---
    # Crack page stores w_calc and wmax_char, not crack_width
    w_calc = get_param("w_calc", 0.0)
    wmax_char = get_param("wmax_char", 0.3)  # Default 0.3 mm if not set
    crack_util = _safe_ratio(w_calc, wmax_char)

    # --- Deflection (from deflection_core.py via _compute_deflection_results) ---
    delta_total = get_param("deflection_total_mm", 0.0)
    defl_limit = get_param("deflection_limit_mm", 0.0)
    defl_util = get_param("deflection_utilisation", None)

    bending_demand = f"{Mu_star:.1f} kNm"

    bending_cap = f"{phi_Mu_cap:.1f} kNm" if phi_Mu_cap > 0 else "—"

    bending_util_str = f"{Mu_util:.2f}" if phi_Mu_cap > 0 else "—"

    bending_status, bending_colour = _status_and_colour(Mu_util, phi_Mu_cap > 0)

    shear_demand = f"{Vu_star:.1f} kN"

    shear_cap = f"{phi_Vu_cap:.1f} kN" if phi_Vu_cap > 0 else "—"

    shear_util_str = f"{Vu_util:.2f}" if phi_Vu_cap > 0 else "—"

    shear_status, shear_colour = _status_and_colour(Vu_util, phi_Vu_cap > 0)

    crack_demand = f"{w_calc:.3f} mm" if w_calc > 0 else "—"

    crack_cap = f"{wmax_char:.3f} mm" if wmax_char > 0 else "—"

    crack_util_str = f"{crack_util:.2f}" if crack_util is not None else "—"

    crack_status, crack_colour = _status_and_colour(
        crack_util, crack_util is not None
    )

    defl_demand = f"{delta_total:.2f} mm"

    defl_cap = f"{defl_limit:.2f} mm" if defl_limit > 0 else "—"

    defl_util_str = f"{defl_util:.2f}" if defl_util is not None and defl_limit > 0 else "—"

    defl_status, defl_colour = _status_and_colour(
        defl_util, defl_util is not None and defl_limit > 0
    )

    # ---------- Bending detail numbers ----------
    Ast_bot = get_param("Ast_bot", 0.0)

    As_min_req = get_param("As_min_req", None)   # from bending page Tab 2 (if available)
    
    # Utilisation = required / provided  → FAIL if > 1
    As_util = _safe_ratio(As_min_req, Ast_bot)
    As_status, As_colour = _status_and_colour(
        As_util, As_util is not None
    )

    Mx_min_req = get_param("Mx_min_req", None)   # minimum required moment from Tab 2
    Mx_min_util = _safe_ratio(Mx_min_req, phi_Mu_cap)
    Mx_min_status, Mx_min_colour = _status_and_colour(
        Mx_min_util, Mx_min_util is not None
    )

    k_u = get_param("k_u", None)
    k_u_lim = get_param("k_u_lim", None)
    k_u_util = _safe_ratio(k_u, k_u_lim)
    k_u_status, k_u_colour = _status_and_colour(
        k_u_util, k_u_util is not None
    )

    # Preformatted strings (for cleaner HTML)
    As_min_str       = f"{As_min_req:.1f}"  if As_min_req not in (None, 0) else "—"
    As_util_str      = f"{As_util:.3f}"     if As_util is not None else "—"
    Mx_min_str       = f"{Mx_min_req:.2f}"  if Mx_min_req not in (None, 0) else "—"
    Mx_min_util_str  = f"{Mx_min_util:.3f}" if Mx_min_util is not None else "—"
    k_u_str          = f"{k_u:.3f}"         if k_u is not None else "—"
    k_u_lim_str      = f"{k_u_lim:.3f}"     if k_u_lim is not None else "—"
    k_u_util_str     = f"{k_u_util:.3f}"    if k_u_util is not None else "—"

    # Crack detail helper
    sigma_sr = get_param("sigma_sr", 0.0)
    sigma_allow = get_param("sigma_allow_table", 0.0)
    sigma_util = _safe_ratio(sigma_sr, sigma_allow)
    sigma_status, sigma_colour = _status_and_colour(
        sigma_util, sigma_util is not None
    )
    sigma_util_str = f"{sigma_util:.3f}" if sigma_util is not None else "—"

    # ---------- Detail HTML blocks (NO leading spaces) ----------
    bending_detail_html = f"""<table style="width: 100%; border-collapse: collapse; font-size: 0.9rem; max-width: 900px;">
<tbody>
<tr style="background-color: {As_colour};">
<td style="padding: 4px 6px;"><strong>Steel area A<sub>st,bot</sub></strong></td>
<td style="text-align:right; padding: 4px 6px;">{Ast_bot:.1f} mm²</td>
<td style="text-align:right; padding: 4px 6px;">A<sub>s,min</sub> = {As_min_str} mm²</td>
<td style="text-align:right; padding: 4px 6px;">{As_util_str}</td>
<td style="text-align:center; padding: 4px 6px;">{As_status}</td>
</tr>
<tr style="background-color: {bending_colour};">
<td style="padding: 4px 6px;"><strong>Flexural capacity</strong></td>
<td style="text-align:right; padding: 4px 6px;">ϕM<sub>u,cap</sub> = {phi_Mu_cap:.2f} kNm</td>
<td style="text-align:right; padding: 4px 6px;">M* = {Mu_star:.2f} kNm</td>
<td style="text-align:right; padding: 4px 6px;">{bending_util_str}</td>
<td style="text-align:center; padding: 4px 6px;">{bending_status}</td>
</tr>
<tr style="background-color: {Mx_min_colour};">
<td style="padding: 4px 6px;"><strong>Minimum strength (Tab 2)</strong></td>
<td style="text-align:right; padding: 4px 6px;">ϕM<sub>u,cap</sub> = {phi_Mu_cap:.2f} kNm</td>
<td style="text-align:right; padding: 4px 6px;">M<sub>x,min</sub> = {Mx_min_str} kNm</td>
<td style="text-align:right; padding: 4px 6px;">{Mx_min_util_str}</td>
<td style="text-align:center; padding: 4px 6px;">{Mx_min_status}</td>
</tr>
<tr style="background-color: {k_u_colour};">
<td style="padding: 4px 6px;"><strong>Neutral axis ratio k<sub>u</sub></strong></td>
<td style="text-align:right; padding: 4px 6px;">{k_u_str}</td>
<td style="text-align:right; padding: 4px 6px;">AS 3600 limit ≤ {k_u_lim_str}</td>
<td style="text-align:right; padding: 4px 6px;">{k_u_util_str}</td>
<td style="text-align:center; padding: 4px 6px;">{k_u_status}</td>
</tr>
</tbody>
</table>
"""

    shear_detail_html = f"""<table style="width: 100%; border-collapse: collapse; font-size: 0.9rem; max-width: 900px;">
<tbody>
<tr style="background-color: {shear_colour};">
  <td style="padding: 4px 6px;"><strong>Total shear capacity</strong></td>
  <td style="text-align:right; padding: 4px 6px;">ϕV<sub>u,cap</sub> = {phi_Vu_cap:.2f} kN</td>
  <td style="text-align:right; padding: 4px 6px;">V* = {Vu_star:.2f} kN</td>
  <td style="text-align:right; padding: 4px 6px;">{shear_util_str}</td>
  <td style="text-align:center; padding: 4px 6px;">{shear_status}</td>
</tr>

<tr style="background-color: {Vuc_colour};">
  <td style="padding: 4px 6px;"><strong>Concrete strut crushing</strong></td>
  <td style="text-align:right; padding: 4px 6px;">ϕV<sub>uc,cap</sub> = {Vuc_cap_str}</td>
  <td style="text-align:right; padding: 4px 6px;">V* = {Vu_star:.2f} kN</td>
  <td style="text-align:right; padding: 4px 6px;">{Vuc_util_str}</td>
  <td style="text-align:center; padding: 4px 6px;">{Vuc_status}</td>
</tr>

</tbody>
</table>
"""

    crack_detail_html = f"""<table style="width: 100%; border-collapse: collapse; font-size: 0.9rem; max-width: 900px;">
<tbody>
<tr style="background-color: {sigma_colour};">
<td style="padding: 4px 6px;"><strong>Steel stress σ<sub>sr</sub></strong></td>
<td style="text-align:right; padding: 4px 6px;">{sigma_sr:.1f} MPa</td>
<td style="text-align:right; padding: 4px 6px;">σ<sub>allow</sub> = {sigma_allow:.1f} MPa</td>
<td style="text-align:right; padding: 4px 6px;">{sigma_util_str}</td>
<td style="text-align:center; padding: 4px 6px;">{sigma_status}</td>
</tr>
<tr style="background-color: {crack_colour};">
<td style="padding: 4px 6px;"><strong>Crack width</strong></td>
<td style="text-align:right; padding: 4px 6px;">w<sub>calc</sub> = {crack_demand}</td>
<td style="text-align:right; padding: 4px 6px;">w<sub>lim</sub> = {crack_cap}</td>
<td style="text-align:right; padding: 4px 6px;">{crack_util_str}</td>
<td style="text-align:center; padding: 4px 6px;">{crack_status}</td>
</tr>
</tbody>
</table>
"""

    defl_detail_html = f"""<table style="width: 100%; border-collapse: collapse; font-size: 0.9rem; max-width: 900px;">
<tbody>
<tr style="background-color: {defl_colour};">
<td style="padding: 4px 6px;"><strong>Total long-term deflection</strong></td>
<td style="text-align:right; padding: 4px 6px;">δ<sub>total</sub> = {delta_total:.2f} mm</td>
<td style="text-align:right; padding: 4px 6px;">δ<sub>lim</sub> = {defl_cap}</td>
<td style="text-align:right; padding: 4px 6px;">{defl_util_str}</td>
<td style="text-align:center; padding: 4px 6px;">{defl_status}</td>
</tr>
</tbody>
</table>
"""

    # ---------- Main summary (header + collapsible rows using <details>) ----------
    summary_table_html = f"""
<style>
/* All styling lives INSIDE the iframe now */

/* Outer container */
.inputs-summary-container {{
  border: 1px solid #cccccc;
  border-radius: 8px;
  padding: 0.5rem 0.75rem 0.4rem 0.75rem;
  margin-bottom: 1rem;
  max-width: 900px;
  font-size: 0.9rem;
}}

/* Shared 5-column grid for header + rows */
.inputs-summary-grid {{
  display: grid;
  grid-template-columns: 30% 20% 20% 15% 15%;
  align-items: center;
}}

/* Header row */
.inputs-summary-header {{
  background-color: #f5f5f5;
  font-weight: 600;
  padding: 4px 6px;
  border-bottom: 1px solid #e0e0e0;
}}
.inputs-summary-header div {{
  padding: 4px 6px;
}}

/* Banner rows (Bending/Shear/Crack/Deflection) */
.inputs-summary-row {{
  padding: 4px 6px;
}}
.inputs-summary-row > * {{
  padding: 4px 6px;
}}
.inputs-summary-row .col-check {{ text-align: left; }}
.inputs-summary-row .col-demand,
.inputs-summary-row .col-cap,
.inputs-summary-row .col-util {{ text-align: right; }}
.inputs-summary-row .col-status {{
  text-align: center;
  font-weight: 600;
}}

/* details + summary reset */
.inputs-summary-details {{
  margin: 0;
  padding: 0;
  border: none;
}}
.inputs-summary-details > summary {{
  cursor: pointer;
  margin: 0;
  padding: 0;
  display: block;
  list-style: none;
}}
.inputs-summary-details > summary::-webkit-details-marker {{
  display: none;
}}
.inputs-summary-details > summary::marker {{
  content: "";
  display: none;
}}

/* Box for the drop-down detail table */
.inputs-summary-detail-wrapper {{
  margin: 0;
  padding: 0.35rem 0.5rem 0.6rem 0.5rem;
  background-color: #fafafa;
  border-top: 1px solid #e0e0e0;
}}

/* Just in case anything renders as inline code inside */
.inputs-summary-container code {{
  display: none !important;
}}
</style>

<div class="inputs-summary-container">

  <!-- Header row -->
  <div class="inputs-summary-grid inputs-summary-header">
    <div>Check</div>
    <div style="text-align:right;">Demand</div>
    <div style="text-align:right;">Capacity</div>
    <div style="text-align:right;">Utilisation</div>
    <div style="text-align:center;">Status</div>
  </div>

  <!-- BENDING ---------------------------------------------------------->
  <details class="inputs-summary-details" open>
    <summary>
      <div class="inputs-summary-grid inputs-summary-row" style="background-color: {bending_colour};">
        <span class="col-check"><strong>Bending</strong></span>
        <span class="col-demand">{bending_demand}</span>
        <span class="col-cap">{bending_cap}</span>
        <span class="col-util">{bending_util_str}</span>
        <span class="col-status">{bending_status}</span>
      </div>
    </summary>
    <div class="inputs-summary-detail-wrapper">{bending_detail_html}</div>
  </details>

  <!-- SHEAR ------------------------------------------------------------>
  <details class="inputs-summary-details">
    <summary>
      <div class="inputs-summary-grid inputs-summary-row" style="background-color: {shear_colour};">
        <span class="col-check"><strong>Shear</strong></span>
        <span class="col-demand">{shear_demand}</span>
        <span class="col-cap">{shear_cap}</span>
        <span class="col-util">{shear_util_str}</span>
        <span class="col-status">{shear_status}</span>
      </div>
    </summary>
    <div class="inputs-summary-detail-wrapper">{shear_detail_html}</div>
  </details>

  <!-- CRACK CONTROL ---------------------------------------------------->
  <details class="inputs-summary-details">
    <summary>
      <div class="inputs-summary-grid inputs-summary-row" style="background-color: {crack_colour};">
        <span class="col-check"><strong>Crack control</strong></span>
        <span class="col-demand">{crack_demand}</span>
        <span class="col-cap">{crack_cap}</span>
        <span class="col-util">{crack_util_str}</span>
        <span class="col-status">{crack_status}</span>
      </div>
    </summary>
    <div class="inputs-summary-detail-wrapper">{crack_detail_html}</div>
  </details>

  <!-- DEFLECTION ------------------------------------------------------->
  <details class="inputs-summary-details">
    <summary>
      <div class="inputs-summary-grid inputs-summary-row" style="background-color: {defl_colour};">
        <span class="col-check"><strong>Deflection</strong></span>
        <span class="col-demand">{defl_demand}</span>
        <span class="col-cap">{defl_cap}</span>
        <span class="col-util">{defl_util_str}</span>
        <span class="col-status">{defl_status}</span>
      </div>
    </summary>
    <div class="inputs-summary-detail-wrapper">{defl_detail_html}</div>
  </details>

</div>
"""

    # Render the summary back at the very top (where summary_container was created)
    with summary_container:

        col_left, col_right = st.columns([2, 1])

        with col_left:
            st.title("Inputs")
            st.markdown("### Summary (read-only from design pages)")

            components.html(
                summary_table_html,
                height=280,   # was 420 – reduces the white gap
                scrolling=False,
            )

        with col_right:
            fig_sec = make_summary_cross_section_figure()
            pad_left, centre, pad_right = st.columns([0.25, 0.5, 0.25])
            with centre:
                st.plotly_chart(
                    fig_sec,
                    use_container_width=False,
                    config={"displayModeBar": False},
                )
                st.markdown(
                    """
                    <div style="text-align:center; margin-top:0.25rem;">
                        <span style="font-weight:600; font-size:1.1rem;">Section A</span>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
