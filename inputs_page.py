
import json
import os
import time
from datetime import datetime
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
    load_proxies_from_active_set,
    save_proxies_to_active_set,
    get_widget_key_for_shared,
    TAB_KEYS,
    hc_log,
    hc_try,
)

from widgets_helpers import apply_global_widget_css, apply_calcbox_css, number_row, select_row, calcbox, show_reo_message, label_with_hover, info_i_button, page_divider, seed_widget_from_shared

try:
    from ui_seamless_steps import inject_seamless_steps_css, render_clickable_summary_table
except Exception:
    def inject_seamless_steps_css():
        return None

    def render_clickable_summary_table(*args, **kwargs):
        return ""
from deflection_checks_helpers import build_deflection_check_rows_from_state
from bending_checks_helpers import build_bending_check_rows_from_state
from shear_checks_helpers import build_shear_check_rows_from_state
from crack_checks_helpers import build_crack_check_rows_from_state

# --- Pure compute functions from design core (no circular imports)
# NOTE: Heavy imports are deferred inside render_inputs() to avoid
# startup timeouts on networked/OneDrive filesystems.
from section_layout import compute_section_layout
from section_props.plotly_section import make_sectionA_figure
from section_props.plotly_3d import make_section_3d_figure
from section_props.reo_layout import compute_longitudinal_reo_layout_T_I
# from deflection import _compute_deflection_results  # TODO: add later


def apply_inputs_page_css():
    # Global page styling (margins + compact inputs)
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


def _get_cached_results(bucket: str):
    results = st.session_state.get("results", {})
    return results.get(bucket)


def _get_results_updated_at(bucket: str):
    meta = st.session_state.get("results_meta", {})
    return (meta.get(bucket) or {}).get("updated_at")


def _overall_status_from_rows(rows):
    if not rows:
        return "—", "rgba(31, 119, 180, 0.08)"
    statuses = [str(r.get("status", "")).upper() for r in rows]
    if any("FAIL" in s or s == "NG" for s in statuses):
        return "FAIL", "rgba(255,0,0,0.12)"
    if any("WARN" in s or "NEAR LIMIT" in s or s == "CHECK" for s in statuses):
        return "NEAR LIMIT", "rgba(255,193,7,0.15)"
    if any("PASS" in s or s == "OK" for s in statuses):
        return "PASS", "rgba(0,128,0,0.12)"
    return "—", "rgba(31, 119, 180, 0.08)"


def _primary_row(rows):
    if not rows:
        return None
    for r in rows:
        if r.get("is_primary"):
            return r
    return rows[0]


def _pack_meta(name, pack):
    rows = (pack or {}).get("rows") or []
    return {
        "rows_n": len(rows),
        "uids": [r.get("uid") for r in rows][:30],
        "statuses": [r.get("status") for r in rows][:30],
    }


def _normalise_row(r: dict, route_page: str) -> dict:
    status = r.get("status", "—")
    ok = r.get("ok", None)
    if ok is None:
        if status == "PASS":
            ok = True
        elif status == "FAIL":
            ok = False
        elif status in ("NEAR LIMIT", "WARN", "CHECK"):
            ok = None

    return {
        "uid": r.get("uid", ""),
        "title": r.get("title", ""),
        "value": r.get("value", "—"),
        "limit": r.get("limit", "—"),
        "util": r.get("util", "—"),
        "status": status,
        "ok": ok,
        "route_page": r.get("route_page", route_page),
    }




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
#  SHAPE-AWARE OUTLINE + CLAMP HELPERS (Section A)
# ------------------------------------------------------------
def _get_sec_shape():
    # Prefer shared value; fall back safely
    s = st.session_state.get("sec_shape", "RECT")
    if s not in ("RECT", "T", "I"):
        s = "RECT"
    return s


def _get_outline_points_and_bbox():
    """
    Returns:
      pts: list[(x, y)] closed polygon (y downwards)
      b_box: overall width used for layout/axes (max width)
      D: overall depth
    """
    sec_shape = _get_sec_shape()
    D = float(get_param("D", 600.0))

    if sec_shape == "RECT":
        b = float(get_param("b", 400.0))
        pts = [(0, 0), (b, 0), (b, D), (0, D), (0, 0)]
        return pts, b, D

    if sec_shape == "T":
        bf = float(get_param("bf", 600.0))
        tf = float(get_param("tf", 120.0))
        bw = float(get_param("bw", 300.0))

        # Sanity clamps
        tf = max(1.0, min(tf, D))
        bw = max(1.0, min(bw, bf))

        x_web0 = 0.5 * (bf - bw)
        x_web1 = x_web0 + bw

        pts = [
            (0, 0), (bf, 0), (bf, tf),
            (x_web1, tf), (x_web1, D),
            (x_web0, D), (x_web0, tf),
            (0, tf),
            (0, 0),
        ]
        return pts, bf, D

    # sec_shape == "I"
    bf = float(get_param("bf", 600.0))
    tf = float(get_param("tf", 120.0))
    tw = float(get_param("tw", 200.0))

    tf = max(1.0, min(tf, 0.5 * D))
    tw = max(1.0, min(tw, bf))

    x_web0 = 0.5 * (bf - tw)
    x_web1 = x_web0 + tw
    y_bot_flange_top = D - tf

    pts = [
        (0, 0), (bf, 0), (bf, tf),
        (x_web1, tf), (x_web1, y_bot_flange_top),
        (bf, y_bot_flange_top), (bf, D),
        (0, D), (0, y_bot_flange_top),
        (x_web0, y_bot_flange_top), (x_web0, tf),
        (0, tf),
        (0, 0),
    ]
    return pts, bf, D


def _xspan_at_y(pts, y):
    """Return (xmin, xmax) of polygon intersection with horizontal line y."""
    xs = []
    for (x1, y1), (x2, y2) in zip(pts[:-1], pts[1:]):
        # ignore horizontal edges
        if y1 == y2:
            continue
        # check if y is within edge range (half-open to avoid double counts)
        if (y1 <= y < y2) or (y2 <= y < y1):
            t = (y - y1) / (y2 - y1)
            x = x1 + t * (x2 - x1)
            xs.append(x)
    if len(xs) < 2:
        return None
    xs.sort()
    return xs[0], xs[-1]


def _clamp_bar_xs_to_outline(xs, y, pts, bar_d):
    span = _xspan_at_y(pts, y)
    if not span:
        return xs
    xmin, xmax = span
    r = 0.5 * max(0.0, float(bar_d))
    xmin += r
    xmax -= r
    if xmax <= xmin:
        # too tight: collapse to centre
        xc = 0.5 * (span[0] + span[1])
        return [xc for _ in xs]
    return [min(max(x, xmin), xmax) for x in xs]


# ------------------------------------------------------------
#  MINI 2D CROSS-SECTION LABELS (SECTION A)
# ------------------------------------------------------------
def _add_section_dimension_labels(fig, *, shape_name: str, dims: dict, reo: dict):
    """
    Adds engineering-style dimension labels with double-ended arrows to Plotly 2D section figure.
    Coordinates are in mm, with y=0 at top and y increasing downward.
    """
    # NOTE: Plotly doesn't have "double arrow" lines as a primitive,
    # so we draw the dimension line + small V-shaped arrowheads at BOTH ends.
    import math

    D = float(dims.get("D", 0.0) or 0.0)
    bf = float(dims.get("bf", 0.0) or 0.0)
    tf = float(dims.get("tf", 0.0) or 0.0)
    bw = float(dims.get("bw", 0.0) or 0.0)
    tw = float(dims.get("tw", 0.0) or 0.0)

    cover_top = float(reo.get("cover_top", 0.0) or 0.0)
    cover_bot = float(reo.get("cover_bot", 0.0) or 0.0)
    cover_side = float(reo.get("cover_side", 0.0) or 0.0)

    # scale for offsets and arrowheads
    x_span = max(bf, bw, tw, 1.0)
    x_off = 0.08 * x_span
    y_off = 0.08 * max(D, 1.0)

    ah = 0.025 * x_span          # arrowhead length
    aw = 0.012 * max(D, 1.0)     # arrowhead width component

    def _add_line(x0, y0, x1, y1):
        fig.add_shape(type="line", x0=x0, y0=y0, x1=x1, y1=y1,
                      line=dict(width=1, color="black"))

    def _arrowhead_at_point(px, py, angle_rad):
        """
        Draws a small 'V' arrowhead centered at (px,py) pointing along angle_rad.
        """
        # two legs at +/- 25 degrees
        for sgn in (-1, +1):
            a = angle_rad + sgn * math.radians(25)
            x1 = px - ah * math.cos(a)
            y1 = py - ah * math.sin(a)
            _add_line(px, py, x1, y1)

    def add_dim_x(x0, x1, y, text):
        # dimension line
        _add_line(x0, y, x1, y)
        # arrowheads (pointing inward)
        _arrowhead_at_point(x0, y, 0.0)          # points to +x
        _arrowhead_at_point(x1, y, math.pi)      # points to -x
        # text
        fig.add_annotation(
            x=(x0 + x1) / 2.0,
            y=y - 0.45 * y_off,
            text=text,
            showarrow=False,
            font=dict(size=12, color="black"),
        )

    def add_dim_y(x, y0, y1, text):
        # dimension line
        _add_line(x, y0, x, y1)
        # arrowheads (pointing inward)
        _arrowhead_at_point(x, y0, math.pi/2)        # points down
        _arrowhead_at_point(x, y1, -math.pi/2)       # points up
        # text
        fig.add_annotation(
            x=x - 0.60 * x_off,
            y=(y0 + y1) / 2.0,
            text=text,
            showarrow=False,
            font=dict(size=12, color="black"),
        )

    # ----- Dimension labels per shape -----
    if shape_name.startswith("T-Section"):
        add_dim_x(0.0, bf, -y_off, f"bf = {bf:.0f} mm")
        add_dim_y(-x_off, 0.0, D, f"D = {D:.0f} mm")
        add_dim_y(bf + x_off, 0.0, tf, f"tf = {tf:.0f} mm")

        if bw > 0:
            x_web0 = (bf - bw) / 2.0
            x_web1 = x_web0 + bw
            add_dim_x(x_web0, x_web1, D + 0.75 * y_off, f"bw = {bw:.0f} mm")

    elif shape_name.startswith("I-Section"):
        add_dim_x(0.0, bf, -y_off, f"bf = {bf:.0f} mm")
        add_dim_y(-x_off, 0.0, D, f"D = {D:.0f} mm")
        add_dim_y(bf + x_off, 0.0, tf, f"tf = {tf:.0f} mm")

        if tw > 0:
            x_web0 = (bf - tw) / 2.0
            x_web1 = x_web0 + tw
            add_dim_x(x_web0, x_web1, D / 2.0, f"tw = {tw:.0f} mm")

    else:
        if D > 0:
            add_dim_y(-x_off, 0.0, D, f"D = {D:.0f} mm")

    # Covers note
    fig.add_annotation(
        x=0.5 * x_span,
        y=D + 1.45 * y_off,
        text=f"cover(top/bot/side) = {cover_top:.0f}/{cover_bot:.0f}/{cover_side:.0f} mm",
        showarrow=False,
        font=dict(size=12, color="black"),
    )

    return fig


# ------------------------------------------------------------
#  MINI 2D CROSS-SECTION  (SECTION A)
# ------------------------------------------------------------
def make_summary_cross_section_figure():
    import streamlit as st
    import plotly.graph_objects as go
    from section_props.plot import apply_section_axes
    from section_layout import compute_section_layout

    layout = compute_section_layout()
    shape_name = str(layout.get("shape_name", "Rectangle (b × D)"))
    shape_name = layout.get("shape_name", "Rectangle (b × D)")
    dims = layout.get("dims", {})
    reo = layout.get("reo", {})
    shape_key = str(shape_name).strip().lower()
    is_ti = ("t-section" in shape_key) or ("i-section" in shape_key) or shape_key.startswith("t") or shape_key.startswith("i")
    is_rect = ("rectangle" in shape_key) or (shape_key == "rect")

    if is_ti:
        try:
            fig = make_sectionA_figure(
                shape_name=shape_name,
                dims=dims,
                reo=reo,
                show_shear=True,
            )
            fig = _add_section_dimension_labels(fig, shape_name=shape_name, dims=dims, reo=reo)

            W = float(dims.get("bf", dims.get("b", 0.0)) or 0.0)
            D = float(dims.get("D", 0.0) or 0.0)
            apply_section_axes(fig, W=W, D=D)
            return fig

        except ValueError as e:
            st.error(f"Reinforcement layout failed: {e}")

            # Fall back to diagram with ligs disabled (still shows section outline + dims)
            reo_no_bars = dict(reo)
            reo_no_bars.update({
                "nb_top": 0,
                "db_top": 0.0,
                "nb_bot": 0,
                "db_bot": 0.0,
                "lig_d": 0.0,
                "lig_legs": 0,
            })

            fig = make_sectionA_figure(
                shape_name=shape_name,
                dims=dims,
                reo=reo_no_bars,
                show_shear=True,
            )
            fig = _add_section_dimension_labels(fig, shape_name=shape_name, dims=dims, reo=reo_no_bars)

            W = float(dims.get("bf", dims.get("b", 0.0)) or 0.0)
            D = float(dims.get("D", 0.0) or 0.0)
            apply_section_axes(fig, W=W, D=D)
            return fig

    if not is_rect:
        return None

    # --- Unified 2D reo: draw from canonical layout["reo_layout"] (same as 3D) ---
    b = float(dims.get("b", 0.0) or 0.0)
    D = float(dims.get("D", 0.0) or 0.0)

    fig = go.Figure()
    fig.add_shape(
        type="rect",
        x0=0, y0=0, x1=b, y1=D,
        line=dict(color="black", width=2),
        fillcolor="rgba(0,0,0,0)",
    )

    reo_layout = layout.get("reo_layout") or {"bottom": [], "top": []}

    def _add_layer_circles(fig, layer, color):
        xs = layer.get("x", []) or []
        y = float(layer.get("y", 0.0) or 0.0)
        db = float(layer.get("db", 0.0) or 0.0)
        if (not xs) or (db <= 0):
            return

        r = db / 2.0
        for x in xs:
            x = float(x)
            fig.add_shape(
                type="circle",
                x0=x - r, y0=y - r,
                x1=x + r, y1=y + r,
                line=dict(color="black", width=1),
                fillcolor=color,
                opacity=1.0,
            )

    for layer in (reo_layout.get("bottom") or []):
        _add_layer_circles(fig, layer, "rgba(0,0,255,0.9)")

    for layer in (reo_layout.get("top") or []):
        _add_layer_circles(fig, layer, "rgba(255,0,0,0.9)")

    lig_d = float(reo.get("lig_d", 0.0) or 0.0)
    lig_legs = int(reo.get("lig_legs", 0) or 0)

    if lig_d > 0 and lig_legs >= 2:
        # covers (use whatever your reo dict uses; fall back to session state)
        cover_side = float(reo.get("cover_side", st.session_state.get("cover_side", 40.0)) or 40.0)
        cover_top = float(reo.get("cover_top", st.session_state.get("cover_top", 40.0)) or 40.0)
        cover_bot = float(reo.get("cover_bot", st.session_state.get("cover_bot", 40.0)) or 40.0)

        x0, x1 = cover_side, b - cover_side
        y0, y1 = cover_top, D - cover_bot

        if x1 > x0 and y1 > y0:
            # closed stirrup outline
            fig.add_shape(
                type="rect",
                x0=x0, y0=y0, x1=x1, y1=y1,
                line=dict(color="black", width=2),
                fillcolor="rgba(0,0,0,0)",
            )

            # internal legs if any
            if lig_legs > 2:
                span = x1 - x0
                for j in range(1, lig_legs - 1):
                    x = x0 + span * j / (lig_legs - 1)
                    fig.add_shape(
                        type="line",
                        x0=x, y0=y0, x1=x, y1=y1,
                        line=dict(color="black", width=2),
                    )

    apply_section_axes(fig, W=b, D=D)
    return fig

# -------------------------------------------------------------------
# Backwards-compatible entrypoint expected by app.py
# Do not remove: app.py routes to inputs_page.render_inputs
# -------------------------------------------------------------------
def render_inputs():
    """
    Stable alias for the Inputs page renderer.

    Some versions of app.py call inputs_page.render_inputs.
    If the internal renderer is renamed, keep this alias so routing never breaks.
    """
    # Try common renderer names in order of preference
    if "render_inputs_page" in globals():
        return globals()["render_inputs_page"]()
    if "render_page" in globals():
        return globals()["render_page"]()
    if "render" in globals():
        return globals()["render"]()
    if "page" in globals():
        return globals()["page"]()

    raise AttributeError(
        "inputs_page.py: No Inputs renderer found. Expected one of: "
        "render_inputs_page(), render_page(), render(), page()."
    )


# ------------------------------------------------------------
#  3D BEAM – BENDING & SHEAR VISUAL  (SECTION A)
# ------------------------------------------------------------
def make_beam_3d_figure():
    # --- parameters from session state ---
    from section_layout import compute_section_layout
    
    layout = compute_section_layout()
    if st.session_state.get("_debug_reo_layout", False):
        st.write("3D reo_layout:", (layout.get("reo_layout") if isinstance(layout, dict) else None))
    shape_name = str(layout.get("shape_name", "Rectangle (b × D)"))
    dims = layout.get("dims", {})
    reo = layout.get("reo", {})
    b = float(dims.get("b", get_param("b", 400.0)))
    D = float(dims.get("D", get_param("D", 600.0)))
    L = float(get_param("L", 8000.0))

    cover_bot = float(reo.get("cover_bot", 40.0))
    cover_top = float(reo.get("cover_top", 40.0))
    cover_side = reo.get("cover_side")
    if cover_side is None:
        cover_side = min(cover_top, cover_bot)
    cover_side = float(cover_side)

    lig_d = float(st.session_state.get("inputs_lig_d", reo.get("lig_d", 0.0)) or 0.0)
    lig_legs = int(st.session_state.get("inputs_lig_legs", reo.get("lig_legs", 0)) or 0)
    s_lig = float(get_param("s_lig", 200.0))

    traces = []

    # ----- section outline wireframe extruded along length -----
    pts, b_box, D = _get_outline_points_and_bbox()

    # --- RECT concrete body (faint) so outline never "disappears" visually ---
    # We only add this for RECT (T/I use other 3D viewer)
    if shape_name.startswith("Rectangle"):
        # Simple box mesh (x = length, y = width, z = depth from top)
        x0, x1 = 0.0, float(L)
        y0, y1 = 0.0, float(b_box)
        z0, z1 = 0.0, float(D)

        vx = np.array([x0, x1, x1, x0, x0, x1, x1, x0], dtype=float)
        vy = np.array([y0, y0, y1, y1, y0, y0, y1, y1], dtype=float)
        vz = np.array([z0, z0, z0, z0, z1, z1, z1, z1], dtype=float)

        # Triangulated faces
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
                opacity=0.18,
                flatshading=True,
                hoverinfo="skip",
                showlegend=False,
            )
        )

    # Map 2D (x,y) -> 3D (y,z) because x in section = width (3D y), y in section = depth (3D z)
    ys = [p[0] for p in pts]
    zs = [p[1] for p in pts]

    # outline at x=0 and x=L
    traces.append(go.Scatter3d(
        x=[0.0] * len(pts),
        y=ys,
        z=zs,
        mode="lines",
        line=dict(width=6, color="rgba(20,20,20,0.95)"),
        hoverinfo="skip",
        showlegend=False,
    ))
    traces.append(go.Scatter3d(
        x=[L] * len(pts),
        y=ys,
        z=zs,
        mode="lines",
        line=dict(width=6, color="rgba(20,20,20,0.95)"),
        hoverinfo="skip",
        showlegend=False,
    ))

    # connect corresponding vertices to show extrusion
    for i in range(len(pts) - 1):
        traces.append(go.Scatter3d(
            x=[0.0, L],
            y=[ys[i], ys[i]],
            z=[zs[i], zs[i]],
            mode="lines",
            line=dict(width=6, color="rgba(20,20,20,0.95)"),
            hoverinfo="skip",
            showlegend=False,
        ))

    # ----- Section A plane at mid-span -----
    mid_x = 0.5 * L
    Yg, Zg = np.meshgrid(np.linspace(0, b_box, 2), np.linspace(0, D, 2))
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

    # ----- longitudinal bar positions - use canonical layout -----
    reo_layout = layout.get("reo_layout") or {"bottom": [], "top": []}

    def _add_bar_cylinder(traces, x0, x1, y0, z0, db, color):
        """Add a true-scale cylinder from x0->x1 with radius=db/2 in data units (mm)."""
        r = float(db) / 2.0
        if r <= 0:
            return

        n_theta = 18  # balance quality vs performance
        theta = np.linspace(0, 2 * np.pi, n_theta)

        # Surface grids (n_theta x 2)
        X = np.column_stack([np.full(n_theta, x0), np.full(n_theta, x1)])
        Y = np.column_stack([y0 + r * np.cos(theta), y0 + r * np.cos(theta)])
        Z = np.column_stack([z0 + r * np.sin(theta), z0 + r * np.sin(theta)])

        traces.append(
            go.Surface(
                x=X, y=Y, z=Z,
                colorscale=[[0, color], [1, color]],
                showscale=False,
                opacity=1.0,
                hoverinfo="skip",
                name="Reo",
            )
        )

    max_bar_d = 0.0
    for layer_list in (reo_layout.get("bottom", []), reo_layout.get("top", [])):
        for layer_data in layer_list:
            max_bar_d = max(max_bar_d, float(layer_data.get("db", 0.0)))
    horiz_clear = 0.5 * max_bar_d
    
    # Bottom bars - draw each layer separately
    # BOTTOM reinforcement is BLUE
    for layer_data in reo_layout["bottom"]:
        x_positions = layer_data["x"]
        y_pos = layer_data["y"]  # This is the y coordinate in 2D (section view)
        db = layer_data["db"]
        # Convert 2D y to 3D z (y in 2D section = z in 3D beam)
        z_pos = y_pos
        for x_pos in x_positions:
            _add_bar_cylinder(traces, 0.0, L, float(x_pos), float(z_pos), float(db), "#1f77b4")

    # Top bars - draw each layer separately
    # TOP reinforcement is RED
    for layer_data in reo_layout["top"]:
        x_positions = layer_data["x"]
        y_pos = layer_data["y"]  # This is the y coordinate in 2D (section view)
        db = layer_data["db"]
        # Convert 2D y to 3D z (y in 2D section = z in 3D beam)
        z_pos = y_pos
        for x_pos in x_positions:
            _add_bar_cylinder(traces, 0.0, L, float(x_pos), float(z_pos), float(db), "#d62728")

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

    k = max(2.2, float(L) / 2000.0)
    fig.update_layout(
        autosize=True,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        scene_camera=dict(
            eye=dict(x=k, y=k, z=k * 0.6),
            center=dict(x=0, y=0, z=0),
            up=dict(x=0, y=0, z=1),
        ),
        scene=dict(
            xaxis_title="Length (mm)",
            yaxis_title="Width (mm)",
            zaxis_title="Depth from top (mm)",
            zaxis=dict(autorange="reversed"),
            aspectmode="data",
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
# Safe option lists for reinforcement inputs
REO_BAR_DIAS = [10, 12, 16, 20, 24, 28, 32, 36, 40]
REO_COUNTS_0_12 = list(range(0, 13))  # 0..12 inclusive
REO_SPACINGS = [75, 100, 125, 150, 175, 200, 225, 250, 275, 300]
REO_LAYOUT_MODE = ["Count", "Spacing"]

K_D_OPTIONS = [
    "None (no ducts in web)",
    "Prestressing ducts present (apply k_d)",
]

K_V_METHOD_OPTIONS = [
    "General εx-based (Cl. 8.2.4.2)",
    "Simplified non-prestressed (Cl. 8.2.4.3)",
]


def _render_ducts_prestress_voids_inputs(sync_callbacks):
    """Render Ducts / Prestress voids section widgets (UI-only, no logic changes)."""
    st.subheader("Ducts / Prestress voids")

    n_ducts_val = float(st.session_state.get("inputs_n_ducts", get_param("n_ducts", 0.0)))
    duct_dia_val = float(st.session_state.get("inputs_duct_dia", get_param("duct_dia", 0.0)))

    number_row(
        "Number of ducts crossing web",
        "inputs_n_ducts",
        n_ducts_val,
        sync_callbacks,
        help_text="Number of ducts/voids crossing the web (set 0 for none).",
    )

    number_row(
        "Duct diameter (mm)",
        "inputs_duct_dia",
        duct_dia_val,
        sync_callbacks,
        help_text="Nominal duct/void diameter (mm).",
    )

    # k_d dropdown
    w_k_d_option = get_widget_key_for_shared("k_d_option", prefix="inputs_") or "inputs_k_d_option"
    k_d_val = st.session_state.get("k_d_option", "None (no ducts in web)")
    select_row(
        "k_d factor for prestressing ducts",
        w_k_d_option,
        K_D_OPTIONS,
        k_d_val,
        sync_callbacks,
        help_text="Select whether ducts are present in the web (affects k_d factor).",
    )


def _render_serviceability_shrinkage_inputs(sync_callbacks):
    """Render Loading conditions section widgets (UI-only, no logic changes)."""
    st.subheader("Loading conditions")
    
    # Support condition (k2) dropdown
    support_options = ["Simply supported", "Continuous – end span", "Continuous – interior span"]
    support_current = st.session_state.get("defl_support_type", "Simply supported")
    if support_current not in support_options:
        support_current = "Simply supported"
    
    w_support = get_widget_key_for_shared("defl_support_type", prefix="inputs_") or "inputs_defl_support_type"
    select_row(
        "Support condition (k₂)",
        w_support,
        support_options,
        support_current,
        sync_callbacks,
        help_text="Support condition determines the deflection coefficient k₂ used in AS 3600 deflection calculations.",
    )
    
    # Deflection limit L/Δ
    w_defl_limit = get_widget_key_for_shared("defl_limit_ratio", prefix="inputs_") or "inputs_defl_limit_ratio"
    defl_limit_val = float(st.session_state.get("defl_limit_ratio", 250.0))
    number_row(
        "Deflection limit L/Δ",
        w_defl_limit,
        defl_limit_val,
        sync_callbacks,
        help_text="Deflection limit ratio (e.g. 250 for L/250).",
    )
    

def _render_time_dependent_inputs(sync_callbacks):
    """Render time-dependent inputs (creep/shrinkage) widgets."""
    st.subheader("Time-dependent inputs")

    # Shrinkage time (days)
    t_shrink_val = float(st.session_state.get("inputs_t_shrink", get_param("t_shrink", 365.0)))
    number_row(
        "Shrinkage time t (days)",
        "inputs_t_shrink",
        t_shrink_val,
        sync_callbacks,
        help_text="Time since commencement of drying (days).",
    )

    # Creep time (days)
    t_creep_val = float(st.session_state.get("inputs_t_creep", get_param("t_creep", 365.0)))
    number_row(
        "Creep time t (days)",
        "inputs_t_creep",
        t_creep_val,
        sync_callbacks,
        help_text="Time after loading (days).",
    )

    # Age at loading (days)
    tau_val = float(st.session_state.get("inputs_age_at_loading", get_param("age_at_loading", 28.0)))
    number_row(
        "Age at loading τ (days)",
        "inputs_age_at_loading",
        tau_val,
        sync_callbacks,
        help_text="Age of concrete at loading (days).",
    )

    # Stress ratio
    w_stress_ratio = get_widget_key_for_shared("stress_ratio", prefix="inputs_") or "inputs_stress_ratio"
    stress_ratio_val = float(st.session_state.get(w_stress_ratio, get_param("stress_ratio", 0.30)))
    number_row(
        "Sustained stress ratio σ₀ / f'c,mi",
        w_stress_ratio,
        stress_ratio_val,
        sync_callbacks,
        step=0.01,
        help_text="Sustained stress ratio for creep (dimensionless).",
    )


def _render_materials_and_sectionA_2d(sync_callbacks):
    """Render Materials section widgets and 2D Section A diagram (UI-only, no logic changes)."""
    mat_col, sec2d_col = st.columns([1, 1], gap="large")
    
    with mat_col:
        st.subheader("Materials")

        # Get current values (widget takes precedence; else shared)
        fc_val  = float(st.session_state.get("inputs_fc",  get_param("fc", 40.0)))
        fsy_val = float(st.session_state.get("inputs_fsy", get_param("fsy", 500.0)))
        Ec_val  = float(st.session_state.get("inputs_Ec",  get_param("Ec", 30000.0)))
        Es_val  = float(st.session_state.get("inputs_Es",  get_param("Es", 200000.0)))

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
            help_text="Yield strength of reinforcement.",
        )

        number_row(
            "Ec (MPa)",
            "inputs_Ec",
            Ec_val,
            sync_callbacks,
            help_text="Elastic modulus of concrete.",
        )

        number_row(
            "Es (MPa)",
            "inputs_Es",
            Es_val,
            sync_callbacks,
            help_text="Elastic modulus of reinforcing steel.",
        )

        # --- Support conditions ---
        st.subheader("Support conditions")
        
        # Member / faces exposed dropdown
        faces_options = [
            "Slab – one face exposed",
            "Slab – two faces exposed",
            "Beam – three faces exposed",
            "Column – four faces exposed",
        ]
        faces_current = st.session_state.get("member_faces_exposed", "Beam – three faces exposed")
        if faces_current not in faces_options:
            faces_current = "Beam – three faces exposed"
        
        w_faces = get_widget_key_for_shared("member_faces_exposed", prefix="inputs_") or "inputs_member_faces_exposed"
        select_row(
            "Member / faces exposed",
            w_faces,
            faces_options,
            faces_current,
            sync_callbacks,
            help_text="Number of faces exposed to drying environment (affects shrinkage calculations).",
        )
        
        # Shrinkage environment dropdown
        env_options = [
            "Arid environment",
            "Interior environment",
            "Temperate inland environment",
            "Tropical / near-coastal / coastal environment",
        ]
        env_current = st.session_state.get("shrinkage_env", "Temperate inland environment")
        if env_current not in env_options:
            env_current = "Temperate inland environment"
        
        w_env = get_widget_key_for_shared("shrinkage_env", prefix="inputs_") or "inputs_shrinkage_env"
        select_row(
            "Shrinkage environment (Table 3.1.7.2)",
            w_env,
            env_options,
            env_current,
            sync_callbacks,
            help_text="Shrinkage environment classification per AS 3600 Table 3.1.7.2.",
        )
        
        # Creep environment dropdown
        creep_env_options = [
            "Arid environment",
            "Interior environment",
            "Temperate inland environment",
            "Tropical / near-coastal / coastal environment",
        ]
        creep_env_current = st.session_state.get("env_option", "Temperate inland environment")
        if creep_env_current not in creep_env_options:
            creep_env_current = "Temperate inland environment"
        
        w_creep_env = get_widget_key_for_shared("env_option", prefix="inputs_") or "inputs_env_option"
        select_row(
            "Creep environment (Tables 3.1.8.2 & 3.1.8.3)",
            w_creep_env,
            creep_env_options,
            creep_env_current,
            sync_callbacks,
            help_text="Creep environment classification per AS 3600 Tables 3.1.8.2 & 3.1.8.3.",
        )
        
        # Support condition (k2) dropdown
        support_options = ["Simply supported", "Continuous – end span", "Continuous – interior span"]
        support_current = st.session_state.get("defl_support_type", "Simply supported")
        if support_current not in support_options:
            support_current = "Simply supported"
        
        w_support = get_widget_key_for_shared("defl_support_type", prefix="inputs_") or "inputs_defl_support_type"
        select_row(
            "Support condition (k₂)",
            w_support,
            support_options,
            support_current,
            sync_callbacks,
            help_text="Support condition determines the deflection coefficient k₂ used in AS 3600 deflection calculations.",
        )
        
        # Deflection limit L/Δ
        w_defl_limit = get_widget_key_for_shared("defl_limit_ratio", prefix="inputs_") or "inputs_defl_limit_ratio"
        defl_limit_val = float(st.session_state.get("defl_limit_ratio", 250.0))
        number_row(
            "Deflection limit L/Δ",
            w_defl_limit,
            defl_limit_val,
            sync_callbacks,
            help_text="Deflection limit ratio (e.g. 250 for L/250).",
        )
    
    with sec2d_col:
        st.markdown(
            "<div style='text-align:center; font-weight:700; font-size:22px; margin: 0 0 10px 0;'>Section A</div>",
            unsafe_allow_html=True,
        )
        # --- Section A figure (safe render) ---
        sec_shape = st.session_state.get("sec_shape", "RECT")

        if sec_shape == "RECT":
            _required = ["b", "D"]
        elif sec_shape == "T":
            _required = ["bf", "tf", "bw", "D"]
        else:  # "I"
            _required = ["bf", "tf", "tw", "D"]

        _missing = [k for k in _required if st.session_state.get(k) in (None, "", 0)]
        if _missing:
            st.info("Section A diagram not available right now (inputs are still saved).")
            return

        fig_sec = None
        try:
            fig_sec = make_summary_cross_section_figure()
            if fig_sec is None:
                raise ValueError("Section A diagram function returned None (fig is None)")
        except Exception as e:
            st.warning(f"Section A diagram failed: {e}")
            with st.expander("Diagram debug details"):
                st.exception(e)
            return

        if fig_sec is not None:
            try:
                fig_sec.update_layout(
                    autosize=True,
                    height=620,
                    margin=dict(l=10, r=10, t=10, b=10),
                )
            except Exception:
                # ultra-safe: even if fig is a dict-like, don't crash
                pass
            st.plotly_chart(
                fig_sec,
                use_container_width=True,
                config={"displayModeBar": False},
            )


def render_inputs():
    # NOTE: init_shared_session_state() is called by app.py router before this function runs.
    # Pages must NOT call init/hydrate themselves - the router owns the lifecycle.
    
    from state_and_helpers import _write_sync_trace_line
    _write_sync_trace_line("\n=== PAGE RENDER: inputs ===")

    # Defer heavy imports until runtime to avoid OneDrive filesystem timeouts
    from bending_core import _compute_bending_capacity
    from shear_core import _compute_shear_capacity
    from crack_core import _compute_crack_results
    from deflection_core import _compute_deflection_results
    
    sync_callbacks = get_sync_callbacks()
    apply_inputs_page_css()
    apply_global_widget_css()
    apply_calcbox_css()

    summary_container = st.container()


    page_divider()

    # ============================
    # 1. TOP ROW – Left stacked inputs | Right 3D model (wide)
    # ============================
    left_inputs, right_3d = st.columns([1, 2], gap="large")

    with left_inputs:
        # --- Design Actions (top of left column) ---
        # Design Actions header row (icon sits at top-right of the header INSIDE middle column)
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

        # --- Loads edit mode toggle (ULS/SLS) ---
        prev_mode = st.session_state.get("loads_edit_mode", "ULS")

        toggle_widget_key = get_widget_key_for_shared("loads_edit_toggle", prefix="inputs_") or "inputs_loads_edit_toggle"
        edit_sls = st.toggle(
            "Edit SLS loads",
            key=toggle_widget_key,
            help="Toggle which load set the widgets below are editing. ULS drives bending/shear; SLS drives crack/deflection.",
        )

        new_mode = "SLS" if edit_sls else "ULS"

        # IMPORTANT: only run mode-change logic when the mode actually changes
        if new_mode != prev_mode:
            # 1) Force mode to OLD mode so save goes to the correct prefix
            st.session_state["loads_edit_mode"] = prev_mode
            save_proxies_to_active_set()

            # 2) Flip mode
            st.session_state["loads_edit_mode"] = new_mode

            # 3) Load proxies from the NEW mode store
            load_proxies_from_active_set()
            st.session_state["inputs_load_Mstar_proxy"] = st.session_state.get("load_Mstar_proxy", 0.0)
            st.session_state["inputs_load_Vstar_proxy"] = st.session_state.get("load_Vstar_proxy", 0.0)
            st.session_state["inputs_load_Nstar_proxy"] = st.session_state.get("load_Nstar_proxy", 0.0)

            # 4) Recompute once, rerun once
            recalc_derived_values()
            update_results()
            st.rerun()
        else:
            # keep mode consistent on normal renders
            st.session_state["loads_edit_mode"] = new_mode

        st.caption(f"Currently editing: **{st.session_state['loads_edit_mode']}** loads")
        # ----------------------------------------
        
        # Teaching values from SFD/BMD page (stored directly in session_state, may be None first time)
        M_sfd = get_param("sfd_Mmax_abs_kNm", None)
        V_sfd = get_param("sfd_Vmax_abs_kN", None)
        L_sfd = get_param("sfd_span_L_m", None)
        # sfd_case is a widget key, read it directly from session_state
        case_sfd = st.session_state.get("sfd_case", None)

        # Get current values using TAB_KEYS lookup (not hardcoded widget keys)
        # This ensures the widget key matches the shared key mapping
        m_proxy_widget_key = get_widget_key_for_shared("load_Mstar_proxy", prefix="inputs_")
        if m_proxy_widget_key is None:
            m_proxy_widget_key = "inputs_load_Mstar_proxy"
        v_proxy_widget_key = get_widget_key_for_shared("load_Vstar_proxy", prefix="inputs_")
        if v_proxy_widget_key is None:
            v_proxy_widget_key = "inputs_load_Vstar_proxy"
        n_proxy_widget_key = get_widget_key_for_shared("load_Nstar_proxy", prefix="inputs_")
        if n_proxy_widget_key is None:
            n_proxy_widget_key = "inputs_load_Nstar_proxy"
        
        Mu_star_val = float(st.session_state.get(m_proxy_widget_key, get_param("load_Mstar_proxy", 500.0)))
        P_star_val = float(st.session_state.get("inputs_P_star", get_param("P_star", 0.0)))
        Tu_star_val = float(st.session_state.get("inputs_Tu_star", get_param("Tu_star", 0.0)))
        Vu_star_val = float(st.session_state.get(v_proxy_widget_key, get_param("load_Vstar_proxy", 300.0)))
        N_star_val = float(st.session_state.get(n_proxy_widget_key, get_param("load_Nstar_proxy", 0.0)))

        number_row(
            "Design moment Mu* (kNm)",
            m_proxy_widget_key,
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
            v_proxy_widget_key,
            Vu_star_val,
            sync_callbacks,
            help_text="Factored design shear at the critical section.",
        )

        number_row(
            "Axial force N* (kN)",
            n_proxy_widget_key,
            N_star_val,
            sync_callbacks,
            help_text="Axial action at the section (+compression / −tension).",
        )

        # --- Geometry (below Design Actions) ---
        st.markdown("## Geometry")

        # ---- Shape selector (shared) ----
        shape_options = ["RECT", "T", "I"]
        sec_shape_current = st.session_state.get("sec_shape", "RECT")
        if sec_shape_current not in shape_options:
            sec_shape_current = "RECT"

        select_row(
            "Section shape",
            "inputs_sec_shape",
            shape_options,
            sec_shape_current,
            sync_callbacks,
            help_text="Select section type. Geometry inputs below update based on this selection.",
        )

        # Get current values (widget key takes precedence if exists, otherwise use shared key)
        D_val = float(st.session_state.get("inputs_D", get_param("D", 600.0)))
        L_val = float(st.session_state.get("inputs_L", get_param("L", 3000.0)))
        cover_side_val = float(st.session_state.get("inputs_cover_side", get_param("cover_side", 40.0)))
        
        # Determine selected shape (prefer widget if present, else shared)
        sec_shape = st.session_state.get("inputs_sec_shape", st.session_state.get("sec_shape", "RECT"))

        if sec_shape == "RECT":
            b_val = float(st.session_state.get("inputs_b", get_param("b", 400.0)))
            number_row(
                "Width b (mm)",
                "inputs_b",
                b_val,
                sync_callbacks,
                help_text="Rectangular section width.",
            )

        elif sec_shape == "T":
            bf_val = float(st.session_state.get("inputs_bf", get_param("bf", 600.0)))
            tf_val = float(st.session_state.get("inputs_tf", get_param("tf", 120.0)))
            bw_val = float(st.session_state.get("inputs_bw", get_param("bw", 300.0)))

            number_row("Flange width bf (mm)", "inputs_bf", bf_val, sync_callbacks)
            number_row("Flange thickness tf (mm)", "inputs_tf", tf_val, sync_callbacks)
            number_row("Web width bw (mm)", "inputs_bw", bw_val, sync_callbacks, help_text="Stem/web width for T section.")

        elif sec_shape == "I":
            bf_val = float(st.session_state.get("inputs_bf", get_param("bf", 600.0)))
            tf_val = float(st.session_state.get("inputs_tf", get_param("tf", 120.0)))
            tw_val = float(st.session_state.get("inputs_tw", get_param("tw", 200.0)))

            number_row("Top flange width bf (mm)", "inputs_bf", bf_val, sync_callbacks)
            number_row("Top flange thickness tf (mm)", "inputs_tf", tf_val, sync_callbacks)
            number_row("Web thickness tw (mm)", "inputs_tw", tw_val, sync_callbacks)

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

    with right_3d:
        layout = compute_section_layout()
        shape_name = layout.get("shape_name", "Rectangle (b × D)")
        dims = layout.get("dims", {})
        reo = dict(layout.get("reo", {}))
        reo["lig_d"] = float(st.session_state.get("inputs_lig_d", reo.get("lig_d", 0.0)) or 0.0)
        reo["lig_legs"] = int(st.session_state.get("inputs_lig_legs", reo.get("lig_legs", 0)) or 0)
        reo_layout = layout.get("reo_layout", {})

        st.markdown(
            """
            <style>
            div[data-testid="stPlotlyChart"] {
              border: 1px solid rgba(0,0,0,0.12);
              border-radius: 8px;
              background: #fff;
              overflow: hidden;
            }
            </style>
            """,
            unsafe_allow_html=True,
        )

        if shape_name.startswith(("T-Section", "I-Section")):
            reo_err = None
            if not isinstance(reo_layout, dict):
                reo_layout = {"top": [], "bottom": []}

            fig3d = make_section_3d_figure(
                shape_name=shape_name,
                dims=dims,
                reo_layout=reo_layout,
                reo_inputs=reo,
                show_shear=True,
                L_vis=900.0,
            )
            # Slightly reduce 3D viewport height
            BASE_H = 520
            fig3d.update_layout(
                height=int(BASE_H * 7 / 5),
                margin=dict(l=10, r=10, t=10, b=10),
            )
            st.plotly_chart(
                fig3d,
                use_container_width=True,
                config={"displayModeBar": False}
            )
        else:
            fig3d = make_beam_3d_figure()
            # Slightly reduce 3D viewport height
            BASE_H = 640
            fig3d.update_layout(
                height=int(BASE_H * 7 / 5),
                margin=dict(l=10, r=10, t=10, b=10),
            )
            st.plotly_chart(
                fig3d,
                width="stretch",
                height=int(BASE_H * 7 / 5),
                config={"displayModeBar": True}
            )

    page_divider()

    # ============================
    # 2. REINFORCEMENT SECTIONS – Bottom | Top | Shear (full-width)
    # ============================
    col_bot_reo, col_top_reo, col_shear_reo = st.columns(3, gap="large")

    # --- Bottom reo ---
    with col_bot_reo:
        st.subheader("Bottom Longitudinal Reinforcement")
        
        # Always seed from shared (single source of truth)
        db_bot_1_val      = float(get_param("db_bot_1", 20.0))
        db_bot_2_val      = float(get_param("db_bot_2", 20.0))
        rowgap_bot_val    = float(get_param("rowgap_bot", 60.0))
    
        # Layer 1 mode
        select_row(
            "Layer 1 layout mode",
            "inputs_bot1_layout_mode",
            REO_LAYOUT_MODE,
            st.session_state.get("bot1_layout_mode", "Count"),
            sync_callbacks,
            help_text="Choose whether Layer 1 is defined by bar count or bar spacing.",
        )

        mode = st.session_state.get("inputs_bot1_layout_mode", st.session_state.get("bot1_layout_mode", "Count"))

        if mode == "Count":
            select_row(
            "Layer 1 bars (count)",
            "inputs_bot1_count",
            REO_COUNTS_0_12,
            int(st.session_state.get("bot1_count", 4)),
            sync_callbacks,
            help_text="Number of bars in bottom Layer 1 (0–12).",
            )
        else:
            select_row(
            "Layer 1 bar spacing (mm)",
            "inputs_bot1_spacing",
            REO_SPACINGS,
            int(st.session_state.get("bot1_spacing", 200)),
            sync_callbacks,
            help_text="Centre-to-centre spacing for bottom Layer 1 (mm).",
            )

        select_row(
            "Layer 1 bar Ø (mm)",
            "inputs_db_bot_1",
            REO_BAR_DIAS,
            int(db_bot_1_val),
            sync_callbacks,
            help_text="Nominal bar diameter for Layer 1 (mm).",
        )
    
        # Layer 2 mode
        select_row(
            "Layer 2 layout mode",
            "inputs_bot2_layout_mode",
            REO_LAYOUT_MODE,
            st.session_state.get("bot2_layout_mode", "Count"),
            sync_callbacks,
            help_text="Choose whether Layer 2 is defined by bar count or bar spacing.",
        )

        mode2 = st.session_state.get("inputs_bot2_layout_mode", st.session_state.get("bot2_layout_mode", "Count"))

        if mode2 == "Count":
            select_row(
            "Layer 2 bars (count)",
            "inputs_bot2_count",
            REO_COUNTS_0_12,
            int(st.session_state.get("bot2_count", 0)),
            sync_callbacks,
            help_text="Number of bars in bottom Layer 2 (0–12).",
            )
        else:
            select_row(
            "Layer 2 bar spacing (mm)",
            "inputs_bot2_spacing",
            REO_SPACINGS,
            int(st.session_state.get("bot2_spacing", 200)),
            sync_callbacks,
            help_text="Centre-to-centre spacing for bottom Layer 2 (mm).",
            )

        select_row(
            "Layer 2 bar Ø (mm)",
            "inputs_db_bot_2",
            REO_BAR_DIAS,
            int(db_bot_2_val),
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

        _layout_dbg = compute_section_layout()
        top_rows = [
            {"n_bars": len(r.get("x", []) or [])}
            for r in _layout_dbg.get("reo_layout", {}).get("top", [])
        ]
        # --- Banner: only show if a 2nd top row was actually auto-created this run ---
        auto_added_second_row = False
        try:
            if isinstance(top_rows, (list, tuple)):
                auto_added_second_row = (len(top_rows) >= 2) and ((top_rows[1] or 0) > 0)
        except Exception:
            auto_added_second_row = False

        # Prevent sticky banners across reruns
        st.session_state["top_auto_msg"] = None
        st.session_state["auto_top_layer1_added"] = auto_added_second_row

        if auto_added_second_row:
            st.info("💡 Auto-placed Top Layer 1: The second layer was automatically added to meet spacing requirements.")
            st.session_state["_reo_msg_top_auto_layer2"] = False
    
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
    
        # Get widget keys from TAB_KEYS (not hardcoded)
        w_db_top_1 = get_widget_key_for_shared("db_top_1", prefix="inputs_") or "inputs_db_top_1"
        w_db_top_2 = get_widget_key_for_shared("db_top_2", prefix="inputs_") or "inputs_db_top_2"
        w_rowgap_top = get_widget_key_for_shared("rowgap_top", prefix="inputs_") or "inputs_rowgap_top"
    
        # Seed widget keys from shared state (only if missing)
        seed_widget_from_shared(w_db_top_1, "db_top_1", 16.0)
        seed_widget_from_shared(w_db_top_2, "db_top_2", 16.0)
        seed_widget_from_shared(w_rowgap_top, "rowgap_top", 60.0)
    
        # Read widget state first (so user edits persist), fall back to shared defaults
        db_top_1_val      = float(st.session_state.get(w_db_top_1,      st.session_state.get("db_top_1", 16.0)))
        db_top_2_val      = float(st.session_state.get(w_db_top_2,      st.session_state.get("db_top_2", 16.0)))
        rowgap_top_val    = float(st.session_state.get(w_rowgap_top,    st.session_state.get("rowgap_top", 60.0)))
    
        # Layer 1 mode
        select_row(
            "Layer 1 layout mode",
            "inputs_top1_layout_mode",
            REO_LAYOUT_MODE,
            st.session_state.get("top1_layout_mode", "Count"),
            sync_callbacks,
            help_text="Choose whether Layer 1 is defined by bar count or bar spacing.",
        )

        mode = st.session_state.get("inputs_top1_layout_mode", st.session_state.get("top1_layout_mode", "Count"))

        if mode == "Count":
            select_row(
            "Layer 1 bars (count)",
            "inputs_top1_count",
            REO_COUNTS_0_12,
            int(st.session_state.get("top1_count", 2)),
            sync_callbacks,
            help_text="Number of bars in top Layer 1 (0–12).",
            )
        else:
            select_row(
            "Layer 1 bar spacing (mm)",
            "inputs_top1_spacing",
            REO_SPACINGS,
            int(st.session_state.get("top1_spacing", 200)),
            sync_callbacks,
            help_text="Centre-to-centre spacing for top Layer 1 (mm).",
            )

        select_row(
            "Layer 1 bar Ø (mm)",
            w_db_top_1,
            REO_BAR_DIAS,
            int(db_top_1_val),
            sync_callbacks,
            help_text="Nominal bar diameter for Layer 1 (mm).",
        )
    
        # Layer 2 mode
        select_row(
            "Layer 2 layout mode",
            "inputs_top2_layout_mode",
            REO_LAYOUT_MODE,
            st.session_state.get("top2_layout_mode", "Count"),
            sync_callbacks,
            help_text="Choose whether Layer 2 is defined by bar count or bar spacing.",
        )

        mode2 = st.session_state.get("inputs_top2_layout_mode", st.session_state.get("top2_layout_mode", "Count"))

        if mode2 == "Count":
            select_row(
            "Layer 2 bars (count)",
            "inputs_top2_count",
            REO_COUNTS_0_12,
            int(st.session_state.get("top2_count", 0)),
            sync_callbacks,
            help_text="Number of bars in top Layer 2 (0–12).",
            )
        else:
            select_row(
            "Layer 2 bar spacing (mm)",
            "inputs_top2_spacing",
            REO_SPACINGS,
            int(st.session_state.get("top2_spacing", 200)),
            sync_callbacks,
            help_text="Centre-to-centre spacing for top Layer 2 (mm).",
            )

        select_row(
            "Layer 2 bar Ø (mm)",
            w_db_top_2,
            REO_BAR_DIAS,
            int(db_top_2_val),
            sync_callbacks,
            help_text="Nominal bar diameter for Layer 2 (mm).",
        )

        number_row(
            "Row gap (mm)",
            w_rowgap_top,
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
    with col_shear_reo:
        # --- Shear section parameters ---
        st.subheader("Shear section parameters")

        # Widget keys (resolved via TAB_KEYS)
        w_d_g = get_widget_key_for_shared("d_g", prefix="inputs_") or "inputs_d_g"
        w_k_v_method = get_widget_key_for_shared("k_v_method", prefix="inputs_") or "inputs_k_v_method"

        # Read shared values (do NOT write shared keys)
        d_g_val = float(st.session_state.get("d_g", 20.0))
        k_v_val = st.session_state.get("k_v_method", "General εx-based (Cl. 8.2.4.2)")

        number_row(
            "Maximum aggregate size d_g (mm)",
            w_d_g,
            d_g_val,
            sync_callbacks,
            help_text="Maximum aggregate size used in shear provisions (mm).",
        )

        # k_v method dropdown
        select_row(
            "k_v method",
            w_k_v_method,
            K_V_METHOD_OPTIONS,
            k_v_val,
            sync_callbacks,
            help_text="Select the k_v method for shear capacity (AS 3600 8.2.4.2 vs 8.2.4.3).",
        )

        st.subheader("Shear reinforcement")

        # Get widget keys from TAB_KEYS (not hardcoded)
        w_lig_d = get_widget_key_for_shared("lig_d", prefix="inputs_") or "inputs_lig_d"
        w_lig_legs = get_widget_key_for_shared("lig_legs", prefix="inputs_") or "inputs_lig_legs"
        w_s_lig = get_widget_key_for_shared("s_lig", prefix="inputs_") or "inputs_s_lig"
    
        # Seed widget keys from shared state (only if missing)
        seed_widget_from_shared(w_lig_d, "lig_d", 10.0)
        seed_widget_from_shared(w_lig_legs, "lig_legs", 2)
        seed_widget_from_shared(w_s_lig, "s_lig", 200.0)
    
        # Read widget state first (so user edits persist), fall back to shared defaults
        lig_d_val = float(st.session_state.get(w_lig_d, st.session_state.get("lig_d", 10.0)))
        lig_legs_val = float(st.session_state.get(w_lig_legs, st.session_state.get("lig_legs", 2)))
        s_lig_val = float(st.session_state.get(w_s_lig, st.session_state.get("s_lig", 200.0)))

        select_row(
            "Link Ø (mm)",
            w_lig_d,
            REO_BAR_DIAS,
            int(lig_d_val),
            sync_callbacks,
            help_text="Nominal diameter of shear reinforcement links (mm).",
        )

        select_row(
            "No. of legs",
            w_lig_legs,
            REO_COUNTS_0_12,
            int(lig_legs_val),
            sync_callbacks,
            help_text="Number of legs per shear link (0–12).",
        )

        number_row(
            "Link spacing (mm)",
            w_s_lig,
            s_lig_val,
            sync_callbacks,
            help_text="Centre-to-centre spacing of shear links along the member (mm).",
        )

    page_divider()

    # ============================
    # 3. Materials + 2D Section A (below Reo section)
    # ============================
    _render_materials_and_sectionA_2d(sync_callbacks)

    page_divider()

    # ============================
    # Compute results BEFORE rendering diagrams (diagrams depend on computed values)
    # ============================
    # Determine final actions (manual vs teaching) - needed for compute functions
    action_source = st.session_state.get("inputs_actions_source", "Manual design actions (inputs below)")
    M_sfd = get_param("sfd_Mmax_abs_kNm", None)
    V_sfd = get_param("sfd_Vmax_abs_kN", None)
    
    # Read manual ULS values (from Inputs widgets via proxies)
    # Manual actions must read from manual shared keys (contract-safe)
    Mu_manual_raw = get_param("Mu_star_manual", None)
    Vu_manual_raw = get_param("Vu_star_manual", None)
    
    # Fall back to existing design values only if manual copies are None
    base_M = get_param("Mu_star", 0.0)
    base_V = get_param("Vu_star", 0.0)
    
    Mu_manual = Mu_manual_raw if (Mu_manual_raw is not None) else base_M
    Vu_manual = Vu_manual_raw if (Vu_manual_raw is not None) else base_V
    
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
    )
    
    # Ensure derived values are up to date before computing results
    recalc_derived_values()
    
    # Recompute ALL checks using current inputs
    _compute_bending_capacity()
    from bending_page import _compute_sls_bending_values
    _compute_sls_bending_values()
    from bending_core import compute_sigma_s_sls_for_crack
    compute_sigma_s_sls_for_crack(publish=True)
    _compute_shear_capacity()

    # FIRST: creep + shrinkage (crack/deflection depend on these SLS effects)
    try:
        from creep import compute_creep_results
        compute_creep_results(publish=True)
    except Exception:
        pass

    try:
        from shrinkage import compute_shrinkage_results
        compute_shrinkage_results(publish=True)
    except Exception:
        pass

    # THEN: crack + deflection
    _compute_crack_results()
    _compute_deflection_results()
    

    # ============================
    # 2. LOWER ROW – Time-dependent | Ducts / Prestress voids | Crack control
    # ============================
    col_td, col_ducts, col_crack = st.columns([1, 1, 1], gap="large")

    with col_td:
        _render_time_dependent_inputs(sync_callbacks)

    with col_ducts:
        _render_ducts_prestress_voids_inputs(sync_callbacks)

    # --- Column 3: Crack Control Inputs ---
    with col_crack:
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
                    "Exposure class",
                    options,
                    key="inputs_exposure_class",
                    on_change=sync_callbacks["inputs_exposure_class"],
                    label_visibility="collapsed",
                )
            else:
                st.selectbox(
                    "Exposure class",
                    options,
                    key="inputs_exposure_class",
                    index=options.index(current),
                    on_change=sync_callbacks["inputs_exposure_class"],
                    label_visibility="collapsed",
                )

        # ----------------------------
        # Crack criteria (shared inputs)
        # ----------------------------
        
        # Resultant action / member type
        member_options = ["Primarily flexure", "Primarily tension"]
        member_current = st.session_state.get("crack_member_type", "Primarily flexure")

        col1, col2 = st.columns([1, 2])
        with col1:
            label_with_hover(
                "Resultant action",
                "Affects default k₂ assumption and crack model interpretation.",
            )
        with col2:
            st.selectbox(
                "Resultant action",
                options=member_options,
                index=member_options.index(member_current) if member_current in member_options else 0,
                key="inputs_crack_member_type",
                on_change=sync_callbacks["inputs_crack_member_type"],
                label_visibility="collapsed",
            )

        # k1 (bond coefficient)
        k1_options = [0.8, 1.6]
        k1_current = float(st.session_state.get("crack_k1", 0.8))

        col1, col2 = st.columns([1, 2])
        with col1:
            label_with_hover(
                "k₁ (bond coefficient)",
                "0.8 for deformed bars, 1.6 for plain bars.",
            )
        with col2:
            st.selectbox(
                "k1",
                options=k1_options,
                index=k1_options.index(k1_current) if k1_current in k1_options else 0,
                format_func=lambda x: "Deformed bars (k₁ = 0.8)" if abs(x - 0.8) < 1e-9 else "Plain bars (k₁ = 1.6)",
                key="inputs_crack_k1",
                on_change=sync_callbacks["inputs_crack_k1"],
                label_visibility="collapsed",
            )

        # k2 (strain distribution factor) – keep editable
        # default follows member type but only as a seed (State-Lab handles persistence)
        k2_seed = 0.5 if member_current == "Primarily flexure" else 1.0
        number_row(
            "k₂ (strain distribution factor)",
            "inputs_crack_k2",
            float(st.session_state.get("crack_k2", k2_seed)),
            sync_callbacks,
            help_text="Default 0.5 for flexure, 1.0 for tension. Adjust only if using a different assumed strain distribution.",
        )

        # Note: Ducts / Prestress voids section moved alongside Crack control
        # Note: Serviceability + Shrinkage split between Support conditions and Time-dependent inputs

    # ============================
    # 4. Rest of inputs (Time | Crack/Ducts) - actions and compute already done above before diagrams
    # ============================
    
    # --- Auto-computed summary rows (deflection-style) ---
    bend_pack = hc_try("summary.build_bending_pack", lambda: build_bending_check_rows_from_state(st.session_state))
    shear_pack = hc_try("summary.build_shear_pack", lambda: build_shear_check_rows_from_state(st.session_state))
    crack_pack = hc_try("summary.build_crack_pack", lambda: build_crack_check_rows_from_state(st.session_state))
    defl_pack = hc_try("summary.build_deflection_pack", lambda: build_deflection_check_rows_from_state(st.session_state))

    hc_log(
        "summary.pack_meta",
        bending=_pack_meta("bending", bend_pack),
        shear=_pack_meta("shear", shear_pack),
        crack=_pack_meta("crack", crack_pack),
        deflection=_pack_meta("deflection", defl_pack),
    )

    hc_log(
        "state.snapshot",
        keys_count=len(st.session_state.keys()),
        has_actions_uls=isinstance(st.session_state.get("actions_uls"), dict),
        sample_keys=sorted(list(st.session_state.keys()))[:120],
    )

    bend_err = bend_pack is None
    shear_err = shear_pack is None
    crack_err = crack_pack is None
    defl_err = defl_pack is None

    BENDING_ROWS = [_normalise_row(r, "bending") for r in (bend_pack or {}).get("rows") or []]
    SHEAR_ROWS = [_normalise_row(r, "shear") for r in (shear_pack or {}).get("rows") or []]
    CRACK_ROWS = [_normalise_row(r, "crack") for r in (crack_pack or {}).get("rows") or []]
    if bend_err:
        BENDING_ROWS = [{
            "uid": "bend_error",
            "title": "Bending checks failed",
            "value": "—",
            "limit": "—",
            "util": "—",
            "status": "—",
            "route_page": "bending",
        }]
    if shear_err:
        SHEAR_ROWS = [{
            "uid": "shear_error",
            "title": "Shear checks failed",
            "value": "—",
            "limit": "—",
            "util": "—",
            "status": "—",
            "route_page": "shear",
        }]
    if crack_err:
        CRACK_ROWS = [{
            "uid": "crack_error",
            "title": "Crack checks failed",
            "value": "—",
            "limit": "—",
            "util": "—",
            "status": "—",
            "route_page": "crack",
        }]

    DEFLECTION_ROWS = [_normalise_row(r, "deflection") for r in (defl_pack or {}).get("rows") or []]

    if defl_err:
        DEFLECTION_ROWS = [{
            "uid": "defl_error",
            "title": "Deflection checks failed",
            "value": "—",
            "limit": "—",
            "util": "—",
            "status": "—",
            "route_page": "deflection",
        }]
        delta_total = 0.0
        defl_limit = 0.0
        defl_util = None
    else:
        defl_summary = defl_pack or {}
        delta_total = float(defl_summary.get("summary_delta_total_mm") or 0.0)
        defl_limit = float(defl_summary.get("summary_defl_limit_mm") or 0.0)
        defl_util = defl_summary.get("summary_util_total")

    bending_primary = _primary_row(BENDING_ROWS) or {}
    shear_primary = _primary_row(SHEAR_ROWS) or {}
    crack_primary = _primary_row(CRACK_ROWS) or {}
    defl_primary = _primary_row(DEFLECTION_ROWS) or {}

    bending_demand = bending_primary.get("value", "—")
    bending_cap = bending_primary.get("limit", "—")
    bending_util_str = bending_primary.get("util", "—")
    bending_status, bending_colour = _overall_status_from_rows(BENDING_ROWS)

    shear_demand = shear_primary.get("value", "—")
    shear_cap = shear_primary.get("limit", "—")
    shear_util_str = shear_primary.get("util", "—")
    shear_status, shear_colour = _overall_status_from_rows(SHEAR_ROWS)

    crack_demand = crack_primary.get("value", "—")
    crack_cap = crack_primary.get("limit", "—")
    crack_util_str = crack_primary.get("util", "—")
    crack_status, crack_colour = _overall_status_from_rows(CRACK_ROWS)

    defl_demand = defl_primary.get("value", "—")
    defl_cap = defl_primary.get("limit", "—")
    defl_util_str = defl_primary.get("util", "—")
    defl_status, defl_colour = _overall_status_from_rows(DEFLECTION_ROWS)

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
            
            status_norm = str(status).upper()
            cls = "pass" if ok is True else "fail" if ok is False else "warn" if status_norm in ("NEAR LIMIT", "WARN", "CHECK") else ""
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

    # Map helper titles to existing step UIDs for navigation
    bending_uid_map = {
        "Flexural strength": "bending_uls_1_7",
        "Minimum tensile steel": "bending_min_2_5",
        "Minimum required design capacity (Mu,cap)_min": "bending_min_2_4",
        "Ductility (k_u limit)": "bending_uls_1_5",
        "Steel stresses at SLS (each layer)": "bending_sls_3_6",
    }
    shear_uid_map = {
        "Torsion cracking check": "shear_check1",
        "Equivalent shear $V_{eq}^*$": "shear_check2",
        "Longitudinal strain $\\varepsilon_x$": "shear_check4",
        "MCFT parameters (k_v and θ_v)": "shear_check5",
        "Concrete shear strength V_uc": "shear_check6",
        "Steel shear strength V_s": "shear_check7",
        "Sectional shear capacity": "shear_check8",
        "Web-crushing strength": "shear_check9",
    }
    crack_uid_map = {
        "Governing outcome": "crk_step_4",
        "Table method (Cl. 8.6.2.2)": "crk_step_2",
        "Direct crack width (Cl. 8.6.2.3)": "crk_step_3",
    }

    for rows, route, uid_map in (
        (BENDING_ROWS, "bending", bending_uid_map),
        (SHEAR_ROWS, "shear", shear_uid_map),
        (CRACK_ROWS, "crack", crack_uid_map),
        (DEFLECTION_ROWS, "deflection", {}),
    ):
        for r in rows:
            if "ok" not in r:
                status = r.get("status", "—")
                r["ok"] = True if status == "PASS" else False if status in ("FAIL", "NG", "NEAR LIMIT") else None
            r.setdefault("route_page", route)
            if uid_map and r.get("title") in uid_map:
                r["uid"] = uid_map.get(r.get("title"))

    # Render the summary back at the very top (where summary_container was created)
    with summary_container:
        st.title("Inputs")
        st.markdown("### Summary (click to expand)")

        # Inject CSS for seamless steps (summary table styling)
        inject_seamless_steps_css()

        if not BENDING_ROWS:
            st.info("Bending results not available yet. Check inputs or visit Bending page for details.")
        if not SHEAR_ROWS:
            st.info("Shear results not available yet. Check inputs or visit Shear page for details.")
        if not CRACK_ROWS:
            st.info("Crack results not available yet. Check inputs or visit Crack Control page for details.")
        if not DEFLECTION_ROWS:
            st.info("Deflection results not available yet. Check inputs or visit Deflection page for details.")

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
        defl_summary = defl_pack or {}
        defl_table_html = _generate_summary_table_html(DEFLECTION_ROWS)
        
        # Bending
        st.markdown(
            f"""
<div class="inputs-top-level-row">
<details>
<summary style="background-color: {bending_colour};">
  <span><strong>Bending — ULS check</strong></span>
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
  <span><strong>Shear — ULS check</strong></span>
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
  <span><strong>Crack control — SLS check</strong></span>
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
  <span><strong>Deflection — SLS check</strong></span>
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

