
import json
import math
import numpy as np
import plotly.graph_objects as go
import streamlit as st
import streamlit.components.v1 as components

from state_and_helpers import (
    init_shared_session_state,
    get_sync_callbacks,
    get_param,
    update_results,
    recalc_derived_values,
)

from widgets_helpers import apply_global_widget_css, apply_calcbox_css, number_row, calcbox, show_reo_message, label_with_hover, info_i_button, page_divider
from ui_seamless_steps import inject_seamless_steps_css, render_clickable_summary_table

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
    
    /* Remove any container framing around Plotly charts */
    div[data-testid="stPlotlyChart"], 
    div[data-testid="stPlotlyChart"] > div,
    div[data-testid="stPlotlyChart"] > div > div {
        border: none !important;
        box-shadow: none !important;
        outline: none !important;
    }
</style>
""",
    unsafe_allow_html=True,
)

# CSS for seamless steps (summary table styling) is injected via inject_seamless_steps_css()


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
    from state_and_helpers import get_param
    
    # Debug-only triage: show canonical values before building figure
    try:
        from src.debug.debug_flags import is_debug_enabled
        if is_debug_enabled():
            st.caption("🔧 DEBUG: Inputs 2D plot inputs")
            shared_top_l1_n = get_param("nb_or_s_top_1")
            widget_top_l1_n = st.session_state.get("inputs_nb_or_s_top_1")
            results_top_l1_n = st.session_state.get("results", {}).get("nb_or_s_top_1")
            st.write({
                "shared_nb_or_s_top_1": shared_top_l1_n,
                "widget_inputs_nb_or_s_top_1": widget_top_l1_n,
                "results_nb_or_s_top_1": results_top_l1_n,
            })
    except ImportError:
        pass
    
    layout = compute_section_layout()
    
    # Debug: show what was passed to plot builder
    try:
        from src.debug.debug_flags import is_debug_enabled
        if is_debug_enabled():
            reo_layout = layout.get("reo_layout")
            if reo_layout:
                top_layers = reo_layout.get("top", [])
                st.write(f"DEBUG: reo_layout['top'] has {len(top_layers)} layers")
                for i, layer in enumerate(top_layers):
                    st.write(f"  Layer {i}: {len(layer.get('x', []))} bars at y={layer.get('y', 'N/A')}")
            else:
                st.write("DEBUG: reo_layout is None or missing")
    except ImportError:
        pass

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
    # Only draw bars if reo_layout exists and has top layers with bars
    if reo_layout:
        for layer_data in reo_layout.get("top", []):
            x_positions = layer_data.get("x", [])
            # Only add trace if there are actually bars (x_positions is not empty)
            if x_positions and len(x_positions) > 0:
                y_pos = layer_data.get("y", 0.0)
                db = layer_data.get("db", 16.0)
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
        # Fallback to legacy structure (only if reo_layout is missing)
        top = layout.get("top", {})
        top_x = top.get("x", [])
        # Only draw if there are actually bars
        if top_x and len(top_x) > 0:
            traces.append(
                go.Scatter(
                    x=top_x,
                    y=top.get("y", []),
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
    
    # Add "Section A" annotation (fixed position below plot area)
    fig.add_annotation(
        text="<b>Section A</b>",
        x=0.5,
        y=-0.10,              # fixed below plot area
        xref="paper",
        yref="paper",
        showarrow=False,
        xanchor="center",
        yanchor="top",
    )
    
    fig.update_xaxes(
        visible=False,
        constrain="domain",
        constraintoward="center",
    )
    fig.update_yaxes(
        visible=False,
        scaleanchor="x",
        scaleratio=1,
        # Center the constrained domain (diagram sits between margins)
        constrain="domain",
        constraintoward="center",   # centers the plot domain vertically
        range=[D * 1.02, 0],
    )
    fig.update_layout(
        width=345,
        height=450,
        margin=dict(l=0, r=0, t=0, b=70),  # b must be big enough for the annotation
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
    
    # Treat 0 as valid - only use default if value is None
    nb_or_s_top_1_val = get_param("nb_or_s_top_1")
    nb_or_s_top_1 = float(nb_or_s_top_1_val) if nb_or_s_top_1_val is not None else 2.0
    db_top_1_val = get_param("db_top_1")
    db_top_1 = float(db_top_1_val) if db_top_1_val is not None else 16.0
    nb_or_s_top_2_val = get_param("nb_or_s_top_2")
    nb_or_s_top_2 = float(nb_or_s_top_2_val) if nb_or_s_top_2_val is not None else 0.0
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

    fig.update_layout(
        autosize=True,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        scene=dict(
            xaxis_title="Length (mm)",
            yaxis_title="Width (mm)",
            zaxis_title="Depth from top (mm)",
            zaxis=dict(autorange="reversed"),
            aspectmode="data",
            camera=dict(eye=dict(x=1.2, y=1.6, z=0.6)),
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
    )
    
    # Make the 3D background transparent too
    fig.update_scenes(
        bgcolor="rgba(0,0,0,0)",
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
    # MUST be first: guarantees shared keys exist and prevents fallback-default reseeding
    init_shared_session_state()

    sync_callbacks = get_sync_callbacks()
    apply_global_widget_css()
    apply_calcbox_css()

    summary_container = st.container()

    page_divider()

    # ============================
    # 1. MAIN BAND – Design Actions + Geometry/Materials | 3D Model
    # ============================
    main_left, main_right = st.columns([1.05, 1.70], gap="small")

    # --- Left column: Design Actions + Geometry and Materials ---
    with main_left:
        # Design Actions header row (icon sits at top-right of the header INSIDE left column)
        hdr_l, hdr_r = st.columns([0.985, 0.015], gap="small", vertical_alignment="center")
        with hdr_l:
            st.markdown("## Design Actions")
            current_source = st.session_state.get("inputs_actions_source", "Manual design actions (inputs below)")
            if current_source == "Manual design actions (inputs below)":
                st.caption("Design actions: Manual inputs")
            else:
                st.caption("Design actions: From SFD/BMD")
        with hdr_r:
            st.markdown(
                "<div style='display:flex;justify-content:flex-end;align-items:flex-start;margin-top:-6px;'>",
                unsafe_allow_html=True
            )
            with info_i_button(help_text="Source of design actions (M*, V*)"):
                action_source = st.radio(
                    "Source of design actions (M*, V*)",
                    [
                        "Manual design actions (inputs below)",
                        "Teaching SFD/BMD page (|M|max, |V|max)",
                    ],
                    key="inputs_actions_source",
                    on_change=sync_callbacks["inputs_actions_source"],
                    label_visibility="collapsed",
                )
            st.markdown("</div>", unsafe_allow_html=True)
        
        # Teaching values from SFD/BMD page (stored directly in session_state, may be None first time)
        M_sfd = get_param("sfd_Mmax_abs_kNm", None)
        V_sfd = get_param("sfd_Vmax_abs_kN", None)
        L_sfd = get_param("sfd_span_L_m", None)
        # sfd_case is a widget key, read it directly from session_state
        case_sfd = st.session_state.get("sfd_case", None)

        # Get current values (widget key takes precedence if exists, otherwise use shared key)
        Mu_star_val = float(st.session_state.get("inputs_Mu_star", get_param("Mu_star_manual", 500.0)))
        P_star_val = float(st.session_state.get("inputs_P_star", get_param("P_star", 0.0)))
        Tu_star_val = float(st.session_state.get("inputs_Tu_star", get_param("Tu_star", 0.0)))
        Vu_star_val = float(st.session_state.get("inputs_Vu_star", get_param("Vu_star_manual", 300.0)))
        N_star_val = float(st.session_state.get("inputs_N_star", get_param("N_star", 0.0)))

        number_row(
            "Design moment Mu* (kNm)",
            "inputs_Mu_star",
            Mu_star_val,
            sync_callbacks,
            help_text="Factored design bending moment at the critical section.",
        )

        number_row(
            "Applied prestress P* (kN)",
            "inputs_P_star",
            P_star_val,
            sync_callbacks,
            help_text="Net prestress force at the section (compression positive).",
        )

        number_row(
            "Design torsion Tu* (kNm)",
            "inputs_Tu_star",
            Tu_star_val,
            sync_callbacks,
            help_text="Factored torsion; used on torsion page (placeholder here).",
        )

        number_row(
            "Design shear Vu* (kN)",
            "inputs_Vu_star",
            Vu_star_val,
            sync_callbacks,
            help_text="Factored design shear at the critical section.",
        )

        number_row(
            "Axial force N* (kN)",
            "inputs_N_star",
            N_star_val,
            sync_callbacks,
            help_text="Axial action at the section (+compression / −tension).",
        )

        # Geometry and Materials
        st.markdown("## Geometry and Materials")
        
        # Get current values (widget key takes precedence if exists, otherwise use shared key)
        b_val = float(st.session_state.get("inputs_b", get_param("b", 400.0)))
        D_val = float(st.session_state.get("inputs_D", get_param("D", 600.0)))
        L_val = float(st.session_state.get("inputs_L", get_param("L", 3000.0)))
        cover_side_val = float(st.session_state.get("inputs_cover_side", get_param("cover_side", 40.0)))
        fc_val = float(st.session_state.get("inputs_fc", get_param("fc", 40.0)))
        fsy_val = float(st.session_state.get("inputs_fsy", get_param("fsy", 500.0)))
        Ec_val = float(st.session_state.get("inputs_Ec", get_param("Ec", 30000.0)))
        Es_val = float(st.session_state.get("inputs_Es", get_param("Es", 200000.0)))
        
        # Geometry widgets
        number_row(
            "Width b (mm)",
            "inputs_b",
            b_val,
            sync_callbacks,
            help_text="Beam/web width.",
        )

        number_row(
            "Depth D (mm)",
            "inputs_D",
            D_val,
            sync_callbacks,
            help_text="Overall section depth from compression face to soffit.",
        )

        number_row(
            "Span L (mm)",
            "inputs_L",
            L_val,
            sync_callbacks,
            help_text="Clear span used for deflection checks.",
        )

        number_row(
            "Side cover (mm)",
            "inputs_cover_side",
            cover_side_val,
            sync_callbacks,
            help_text="Clear side cover to longitudinal reinforcement and ducts.",
        )

        # Materials widgets
        number_row(
            "Concrete strength f'c (MPa)",
            "inputs_fc",
            fc_val,
            sync_callbacks,
            help_text="Characteristic compressive strength of concrete.",
        )

        number_row(
            "Steel yield fsy (MPa)",
            "inputs_fsy",
            fsy_val,
            sync_callbacks,
            help_text="Yield stress of flexural reinforcement.",
        )

        number_row(
            "Ec (MPa)",
            "inputs_Ec",
            Ec_val,
            sync_callbacks,
            help_text="Short-term modulus of elasticity of concrete.",
        )

        number_row(
            "Es (MPa)",
            "inputs_Es",
            Es_val,
            sync_callbacks,
            help_text="Elastic modulus of reinforcing steel.",
        )

    # --- Right column: 3D Model (no heading, no border) ---
    with main_right:
        fig3d = make_beam_3d_figure()
        st.plotly_chart(
            fig3d,
            use_container_width=True,
            height=640,
            config={"displayModeBar": True}
        )

    page_divider()

    # --- START LONGITUDINAL REINFORCEMENT SECTION ---
    # ============================
    # 2. REINFORCEMENT SECTIONS – Bottom | Top | Shear
    # ============================
    col_bot_reo, col_top_reo, col_shear = st.columns(3)

    # --- Bottom reo ---
    with col_bot_reo:
        st.subheader("Bottom Longitudinal Reinforcement")
        
        # Get current values (widget key takes precedence if exists, otherwise use shared key)
        nb_or_s_bot_1_val = float(st.session_state.get("inputs_nb_or_s_bot_1", get_param("nb_or_s_bot_1", 4.0)))
        db_bot_1_val = float(st.session_state.get("inputs_db_bot_1", get_param("db_bot_1", 20.0)))
        nb_or_s_bot_2_val = float(st.session_state.get("inputs_nb_or_s_bot_2", get_param("nb_or_s_bot_2", 0.0)))
        db_bot_2_val = float(st.session_state.get("inputs_db_bot_2", get_param("db_bot_2", 20.0)))
        rowgap_bot_val = float(st.session_state.get("inputs_rowgap_bot", get_param("rowgap_bot", 60.0)))
        
        number_row(
            "Layer 1 bar spacing",
            "inputs_nb_or_s_bot_1",
            nb_or_s_bot_1_val,
            sync_callbacks,
            help_text="Enter number of bars if value ≤ 30. Enter bar spacing (mm) if value ≥ 30.",
        )

        number_row(
            "Layer 1 bar Ø (mm)",
            "inputs_db_bot_1",
            db_bot_1_val,
            sync_callbacks,
            help_text="Nominal bar diameter for Layer 1 (mm).",
        )
        
        number_row(
            "Layer 2 bar spacing",
            "inputs_nb_or_s_bot_2",
            nb_or_s_bot_2_val,
            sync_callbacks,
            help_text="Enter number of bars if value ≤ 30. Enter bar spacing (mm) if value ≥ 30.",
        )

        number_row(
            "Layer 2 bar Ø (mm)",
            "inputs_db_bot_2",
            db_bot_2_val,
            sync_callbacks,
            help_text="Nominal bar diameter for Layer 2 (mm).",
        )

        number_row(
            "Row gap (mm)",
            "inputs_rowgap_bot",
            rowgap_bot_val,
            sync_callbacks,
            help_text="Clear vertical gap between Layer 1 and Layer 2 (mm).",
        )
        
        # Bottom cover widget (moved from Geometry section)
        cover_bot_val = float(st.session_state.get("inputs_cover_bot", get_param("cover_bot", 40.0)))
        number_row(
            "Bottom cover (mm)",
            "inputs_cover_bot",
            cover_bot_val,
            sync_callbacks,
            help_text="Clear cover to the bottom bars.",
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
        
        # Get current values (widget key takes precedence if exists, otherwise use shared key)
        # Treat 0 as valid - only use default if value is None
        nb_or_s_top_1_shared = get_param("nb_or_s_top_1")
        nb_or_s_top_1_default = float(nb_or_s_top_1_shared) if nb_or_s_top_1_shared is not None else 2.0
        nb_or_s_top_1_val = float(st.session_state.get("inputs_nb_or_s_top_1", nb_or_s_top_1_default))
        db_top_1_val = float(st.session_state.get("inputs_db_top_1", get_param("db_top_1", 16.0)))
        nb_or_s_top_2_val = float(st.session_state.get("inputs_nb_or_s_top_2", get_param("nb_or_s_top_2", 0.0)))
        db_top_2_val = float(st.session_state.get("inputs_db_top_2", get_param("db_top_2", 16.0)))
        rowgap_top_val = float(st.session_state.get("inputs_rowgap_top", get_param("rowgap_top", 60.0)))
        
        number_row(
            "Layer 1 bar spacing",
            "inputs_nb_or_s_top_1",
            nb_or_s_top_1_val,
            sync_callbacks,
            help_text="Enter number of bars if value ≤ 30. Enter bar spacing (mm) if value ≥ 30.",
        )

        number_row(
            "Layer 1 bar Ø (mm)",
            "inputs_db_top_1",
            db_top_1_val,
            sync_callbacks,
            help_text="Nominal bar diameter for Layer 1 (mm).",
        )
        
        number_row(
            "Layer 2 bar spacing",
            "inputs_nb_or_s_top_2",
            nb_or_s_top_2_val,
            sync_callbacks,
            help_text="Enter number of bars if value ≤ 30. Enter bar spacing (mm) if value ≥ 30.",
        )

        number_row(
            "Layer 2 bar Ø (mm)",
            "inputs_db_top_2",
            db_top_2_val,
            sync_callbacks,
            help_text="Nominal bar diameter for Layer 2 (mm).",
        )

        number_row(
            "Row gap (mm)",
            "inputs_rowgap_top",
            rowgap_top_val,
            sync_callbacks,
            help_text="Clear vertical gap between Layer 1 and Layer 2 (mm).",
        )
        
        # Top cover widget (moved from Geometry section)
        cover_top_val = float(st.session_state.get("inputs_cover_top", get_param("cover_top", 40.0)))
        number_row(
            "Top cover (mm)",
            "inputs_cover_top",
            cover_top_val,
            sync_callbacks,
            help_text="Clear cover to the top bars.",
        )

    # --- Shear reo (same row) ---
    with col_shear:
        st.subheader("Shear reinforcement")

        # Get current values (widget key takes precedence if exists, otherwise use shared key)
        lig_d_val = float(st.session_state.get("inputs_lig_d", get_param("lig_d", 10.0)))
        lig_legs_val = float(st.session_state.get("inputs_lig_legs", get_param("lig_legs", 2)))
        s_lig_val = float(st.session_state.get("inputs_s_lig", get_param("s_lig", 200.0)))

        number_row(
            "Link Ø (mm)",
            "inputs_lig_d",
            lig_d_val,
            sync_callbacks,
            help_text="Nominal diameter of shear links (mm).",
        )

        number_row(
            "No. of legs",
            "inputs_lig_legs",
            lig_legs_val,
            sync_callbacks,
            help_text="Number of legs per shear link.",
        )

        number_row(
            "Link spacing (mm)",
            "inputs_s_lig",
            s_lig_val,
            sync_callbacks,
            help_text="Centre-to-centre spacing of shear links along the member (mm).",
        )

    page_divider()

    # ============================
    # Compute results BEFORE rendering diagrams (diagrams depend on computed values)
    # ============================
    # Determine final actions (manual vs teaching) - needed for compute functions
    action_source = st.session_state.get("inputs_actions_source", "Manual design actions (inputs below)")
    M_sfd = get_param("sfd_Mmax_abs_kNm", None)
    V_sfd = get_param("sfd_Vmax_abs_kN", None)
    
    # Read manual values (from Inputs widgets via TAB_KEYS)
    Mu_manual_raw = get_param("Mu_star_manual", None)
    Vu_manual_raw = get_param("Vu_star_manual", None)
    
    # Fall back to existing design values if manual copies are None/0.0
    base_M = get_param("Mu_star", 0.0)
    base_V = get_param("Vu_star", 0.0)
    
    Mu_manual = Mu_manual_raw if (Mu_manual_raw is not None and Mu_manual_raw != 0.0) else base_M
    Vu_manual = Vu_manual_raw if (Vu_manual_raw is not None and Vu_manual_raw != 0.0) else base_V
    
    # Decide if we can use teaching values
    use_sfd = (action_source == "Teaching SFD/BMD page (|M|max, |V|max)" and M_sfd is not None and V_sfd is not None)
    
    if use_sfd:
        Mu_star = float(M_sfd)
        Vu_star = float(V_sfd)
        source_label = "Teaching SFD/BMD page (|M|max, |V|max)"
    else:
        Mu_star = float(Mu_manual)
        Vu_star = float(Vu_manual)
        source_label = "Manual design actions (inputs below)"
    
    # Push final chosen actions into results
    update_results(
        actions_source=source_label,
        Mu_star=float(Mu_star),
        Mu_star_kNm=float(Mu_star),
        Vu_star=float(Vu_star),
        Vu_star_kN=float(Vu_star),
    )
    
    # Ensure derived values are up to date before computing results
    recalc_derived_values()
    
    # Recompute ALL checks using current inputs
    _compute_bending_capacity()
    _compute_shear_capacity()
    _compute_crack_results()
    _compute_deflection_results()

    # ============================
    # 4. REST OF INPUTS (Ducts | Crack | Time)
    # ============================
    ducts_col, crack_col, time_col = st.columns(3, gap="large")

    # --- Ducts / Prestress voids ---
    with ducts_col:
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

    # --- Crack Control Inputs ---
    with crack_col:
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

    # --- Time-dependent inputs ---
    with time_col:
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

    # ============================
    # 4. Rest of inputs (Time | Crack/Ducts) - actions and compute already done above before diagrams
    # ============================
    
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

    # Helper function to convert status string to ok boolean for render_clickable_summary_table
    def _status_to_ok(status_str):
        """Convert status string to ok boolean: True=pass, False=fail, None=neutral"""
        if status_str == "PASS":
            return True
        elif status_str in ("FAIL", "NEAR LIMIT"):
            return False
        else:
            return None

    # Helper function to generate summary table HTML as string (for embedding in details)
    def _generate_summary_table_html(rows):
        """Generate the summary table HTML as a string (same format as render_clickable_summary_table)"""
        html = ['<div class="summary-wrap"><table class="summary-table">']
        html.append(
            """
<thead>
<tr>
  <th style="width:34%">Check</th>
  <th style="width:22%">Value</th>
  <th style="width:26%">Limit</th>
  <th style="width:8%">Util</th>
  <th style="width:10%">Status</th>
</tr>
</thead>
<tbody>
"""
        )
        
        for r in rows:
            uid = r["uid"]
            check = r.get("title") or r.get("check", uid)
            value = r.get("value", "")
            limit = r.get("limit", "")
            util = r.get("util", "")
            status = r.get("status", "")
            ok = r.get("ok")
            tab = r.get("tab", "")
            
            cls = "pass" if ok is True else "fail" if ok is False else ""
            primary = "primary" if r.get("is_primary") else ""
            row_class = f"{cls} {primary}".strip()
            
            html.append(
                f"""
<tr class="{row_class}" data-tab="{tab}">
  <td>
    {check} <span class="hint">↳ jump to calc</span>
    <a class="row-link" href="#" data-uid="{uid}" data-tab="{tab}"></a>
  </td>
  <td>{value}</td>
  <td>{limit}</td>
  <td>{util}</td>
  <td>{status}</td>
</tr>
"""
            )
        
        html.append("</tbody></table></div>")
        return "".join(html)

    # ---------- Build ROWS lists for each section (matching Bending format) ----------
    
    # Bending rows
    BENDING_ROWS = [
        {
            "uid": "bending_min_2_5",
            "title": "Steel area Ast,bot",
            "value": f"{Ast_bot:.1f} mm²",
            "limit": f"As,min = {As_min_str} mm²" if As_min_str != "—" else "—",
            "util": As_util_str,
            "status": As_status,
            "ok": _status_to_ok(As_status),
            "route_page": "bending",
            "tab": "Minimum strength checks",
        },
        {
            "uid": "bending_uls_1_7",
            "title": "Flexural capacity",
            "value": f"ϕMu,cap = {phi_Mu_cap:.2f} kNm",
            "limit": f"M* = {Mu_star:.2f} kNm",
            "util": bending_util_str,
            "status": bending_status,
            "ok": _status_to_ok(bending_status),
            "route_page": "bending",
            "tab": "ULS Checks",
        },
        {
            "uid": "bending_min_2_4",
            "title": "Minimum strength (Tab 2)",
            "value": f"ϕMu,cap = {phi_Mu_cap:.2f} kNm",
            "limit": f"Mx,min = {Mx_min_str} kNm" if Mx_min_str != "—" else "—",
            "util": Mx_min_util_str,
            "status": Mx_min_status,
            "ok": _status_to_ok(Mx_min_status),
            "route_page": "bending",
            "tab": "Minimum strength checks",
        },
        {
            "uid": "bending_uls_1_5",
            "title": "Neutral axis ratio ku",
            "value": k_u_str,
            "limit": f"AS 3600 limit ≤ {k_u_lim_str}" if k_u_lim_str != "—" else "—",
            "util": k_u_util_str,
            "status": k_u_status,
            "ok": _status_to_ok(k_u_status),
            "route_page": "bending",
            "tab": "ULS Checks",
        },
    ]

    # Shear rows
    SHEAR_ROWS = [
        {
            "uid": "shear_check8",
            "title": "Total shear capacity",
            "value": f"ϕVu,cap = {phi_Vu_cap:.2f} kN",
            "limit": f"V* = {Vu_star:.2f} kN",
            "util": shear_util_str,
            "status": shear_status,
            "ok": _status_to_ok(shear_status),
            "route_page": "shear",
        },
        {
            "uid": "shear_check9",
            "title": "Concrete strut crushing",
            "value": f"ϕVuc,cap = {Vuc_cap_str}",
            "limit": f"V* = {Vu_star:.2f} kN",
            "util": Vuc_util_str,
            "status": Vuc_status,
            "ok": _status_to_ok(Vuc_status),
            "route_page": "shear",
        },
    ]

    # Crack rows
    CRACK_ROWS = [
        {
            "uid": "cr_table",
            "title": "Steel stress σsr",
            "value": f"{sigma_sr:.1f} MPa",
            "limit": f"σallow = {sigma_allow:.1f} MPa",
            "util": sigma_util_str,
            "status": sigma_status,
            "ok": _status_to_ok(sigma_status),
            "route_page": "crack",
        },
        {
            "uid": "cr_direct",
            "title": "Crack width",
            "value": f"wcalc = {crack_demand}",
            "limit": f"wlim = {crack_cap}",
            "util": crack_util_str,
            "status": crack_status,
            "ok": _status_to_ok(crack_status),
            "route_page": "crack",
        },
    ]

    # Deflection rows
    DEFLECTION_ROWS = [
        {
            "uid": "defl_total",
            "title": "Total long-term deflection",
            "value": f"δtotal = {delta_total:.2f} mm",
            "limit": f"δlim = {defl_cap}",
            "util": defl_util_str,
            "status": defl_status,
            "ok": _status_to_ok(defl_status),
            "route_page": "deflection",
        },
    ]

    # Render the summary back at the very top (where summary_container was created)
    with summary_container:

        col_left, col_right = st.columns([2, 1])

        with col_left:
            st.title("Inputs")
            st.markdown("### Summary (read-only from design pages)")

            # Inject CSS for seamless steps (summary table styling)
            inject_seamless_steps_css()

            # Custom CSS for top-level expandable rows (matching old design)
            # Includes summary table styling (same as render_clickable_summary_table)
            st.markdown("""
<style>
.inputs-top-level-row {
  border: 1px solid rgba(49,51,63,0.15);
  border-radius: 10px;
  margin-bottom: 0.5rem;
  overflow: hidden;
}

.inputs-top-level-row details {
  margin: 0;
}

.inputs-top-level-row summary {
  padding: 14px;
  cursor: pointer;
  list-style: none;
  font-weight: 600;
  border-bottom: 1px solid rgba(49,51,63,0.1);
  display: grid;
  grid-template-columns: 20% 25% 25% 15% 15%;
  align-items: center;
  gap: 10px;
  user-select: none;
}

.inputs-top-level-row summary::-webkit-details-marker {
  display: none;
}

.inputs-top-level-row summary::marker {
  content: "";
}

.inputs-top-level-row details[open] summary {
  border-bottom: 1px solid rgba(49,51,63,0.1);
}

.inputs-top-level-row .details-content {
  padding: 1rem;
  background: white;
  max-height: 500px;
  overflow-y: auto;
  overflow-x: hidden;
}

.inputs-top-level-row details:not([open]) .details-content {
  display: none;
}

/* Summary table styling (from render_clickable_summary_table) */
.summary-wrap {
  border: 1px solid rgba(49,51,63,0.15);
  border-radius: 10px;
  overflow: hidden;
}

.summary-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 16px;
}

.summary-table th {
  background: rgba(49,51,63,0.05);
  text-align: left;
  padding: 14px;
  color: rgba(49,51,63,0.7);
}

.summary-table td {
  padding: 14px;
  border-top: 1px solid rgba(49,51,63,0.1);
  position: relative;
}

/* Default neutral background (matches calcbox blue) - only for rows without pass/fail/warn classes */
.summary-table tbody tr:not(.pass):not(.fail):not(.warn) td {
  background: rgba(31, 119, 180, 0.08);
}

tr.pass td { background: rgba(0,128,0,0.12); }
tr.fail td { background: rgba(255,0,0,0.12); }
tr.warn td { background: rgba(255,193,7,0.15); }

tr.primary td {
  font-weight: 700;
}

tr:hover td { background: rgba(0,0,0,0.04); }

.row-link {
  position: absolute;
  inset: 0;
  z-index: 5;
  display: block;
  cursor: pointer;
}

.hint {
  opacity: 0;
  font-size: 0.9em;
  margin-left: 6px;
  color: rgba(49,51,63,0.6);
}
tr:hover .hint { opacity: 1; }
</style>
""", unsafe_allow_html=True)

            # Top-level expandable rows with summary results
            # Generate table HTML strings
            bending_table_html = _generate_summary_table_html(BENDING_ROWS)
            shear_table_html = _generate_summary_table_html(SHEAR_ROWS)
            crack_table_html = _generate_summary_table_html(CRACK_ROWS)
            defl_table_html = _generate_summary_table_html(DEFLECTION_ROWS)
            
            # Bending
            st.markdown(
                f"""
<div class="inputs-top-level-row">
<details open>
<summary style="background-color: {bending_colour};">
  <span><strong>Bending</strong></span>
  <span style="text-align:right;">{bending_demand}</span>
  <span style="text-align:right;">{bending_cap}</span>
  <span style="text-align:right;">{bending_util_str}</span>
  <span style="text-align:center;">{bending_status}</span>
    </summary>
<div class="details-content">
{bending_table_html}
</div>
  </details>
      </div>
""",
                unsafe_allow_html=True,
            )

            # Shear
            st.markdown(
                f"""
<div class="inputs-top-level-row">
<details>
<summary style="background-color: {shear_colour};">
  <span><strong>Shear</strong></span>
  <span style="text-align:right;">{shear_demand}</span>
  <span style="text-align:right;">{shear_cap}</span>
  <span style="text-align:right;">{shear_util_str}</span>
  <span style="text-align:center;">{shear_status}</span>
    </summary>
<div class="details-content">
{shear_table_html}
</div>
  </details>
      </div>
""",
                unsafe_allow_html=True,
            )

            # Crack
            st.markdown(
                f"""
<div class="inputs-top-level-row">
<details>
<summary style="background-color: {crack_colour};">
  <span><strong>Crack control</strong></span>
  <span style="text-align:right;">{crack_demand}</span>
  <span style="text-align:right;">{crack_cap}</span>
  <span style="text-align:right;">{crack_util_str}</span>
  <span style="text-align:center;">{crack_status}</span>
    </summary>
<div class="details-content">
{crack_table_html}
</div>
  </details>
      </div>
""",
                unsafe_allow_html=True,
            )

            # Deflection
            st.markdown(
                f"""
<div class="inputs-top-level-row">
<details>
<summary style="background-color: {defl_colour};">
  <span><strong>Deflection</strong></span>
  <span style="text-align:right;">{defl_demand}</span>
  <span style="text-align:right;">{defl_cap}</span>
  <span style="text-align:right;">{defl_util_str}</span>
  <span style="text-align:center;">{defl_status}</span>
    </summary>
<div class="details-content">
{defl_table_html}
</div>
  </details>
</div>
""",
                unsafe_allow_html=True,
            )

            # Add custom JavaScript to handle cross-page navigation from Inputs summary
            all_inputs_rows = BENDING_ROWS + SHEAR_ROWS + CRACK_ROWS + DEFLECTION_ROWS
            rows_json = json.dumps({r["uid"]: r["route_page"] for r in all_inputs_rows})
            
            components.html(
                f"""
<script>
(function () {{
  const doc = window.parent.document;
  const routeMap = {rows_json};
  
  function bindInputsNavigation() {{
    const links = doc.querySelectorAll(".row-link[data-uid]");
    links.forEach((a) => {{
      if (a.dataset.inputsBound === "1") return;
      a.dataset.inputsBound = "1";
      
      const uid = a.dataset.uid;
      const routePage = routeMap[uid];
      
      if (!routePage) return;  // Skip if no route page mapping
      
      a.addEventListener("click", (e) => {{
        e.preventDefault();
        e.stopPropagation();
        
        const url = new URL(window.parent.location.href);
        url.searchParams.set("page", routePage);
        url.searchParams.set("jump", uid);
        window.parent.location.assign(url.toString());
      }}, true);
    }});
  }}
  
  bindInputsNavigation();
  setTimeout(bindInputsNavigation, 300);
  setTimeout(bindInputsNavigation, 1000);
}})();
</script>
""",
                height=0,
            )

        with col_right:
            fig_sec = make_summary_cross_section_figure()
            
            # Compute deterministic key for plotly chart (prevents DOM reuse)
            import hashlib
            # json and get_param are already imported at the top of the file
            sig_payload = {
                "nb_or_s_top_1": get_param("nb_or_s_top_1"),
                "nb_or_s_top_2": get_param("nb_or_s_top_2"),
                "nb_or_s_bot_1": get_param("nb_or_s_bot_1"),
                "nb_or_s_bot_2": get_param("nb_or_s_bot_2"),
                "b": get_param("b"),
                "D": get_param("D"),
                "cover_bot": get_param("cover_bot"),
                "cover_top": get_param("cover_top"),
            }
            diagram_sig = hashlib.sha1(json.dumps(sig_payload, sort_keys=True).encode()).hexdigest()[:10]
            
            pad_left, centre, pad_right = st.columns([0.25, 0.5, 0.25])
            with centre:
                st.plotly_chart(
                    fig_sec,
                    key=f"inputs_2d_{diagram_sig}",
                    use_container_width=False,
                    config={"displayModeBar": False},
                )
