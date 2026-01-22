# bending_diagrams.py
import math
import numpy as np
import streamlit as st

import plotly.graph_objects as go
from plotly.subplots import make_subplots

from state_and_helpers import get_param
from bending_core import _layout_bars_in_rows, _stress_strain_state
from section_layout import compute_section_layout
from plotly_section import make_sectionA_figure
from section_props.plot import apply_section_axes

# ------------------------------------------------------------
# Global styling constants
# ------------------------------------------------------------
LINE_THICK = 1.0   # main outlines
LINE_MED   = 0.8   # normal lines
LINE_THIN  = 0.6   # light lines

FS_TITLE  = 8      # diagram titles
FS_LABEL  = 7      # axis labels / main text
FS_ANNOT  = 5      # small annotations

ARROW_SCALE = 4    # small arrowheads for everything

def _inject_figure_into_subplot(parent_fig, child_fig, *, row: int, col: int, xref: str, yref: str):
    """
    Copy traces + shapes + annotations from child_fig into a subplot
    of parent_fig (created by make_subplots).
    """
    # Traces
    for tr in child_fig.data:
        parent_fig.add_trace(tr, row=row, col=col)

    # Shapes
    if getattr(child_fig.layout, "shapes", None):
        for sh in child_fig.layout.shapes:
            shd = sh.to_plotly_json()
            shd["xref"] = xref
            shd["yref"] = yref
            parent_fig.add_shape(shd, row=row, col=col)

    # Annotations
    if getattr(child_fig.layout, "annotations", None):
        for ann in child_fig.layout.annotations:
            ad = ann.to_plotly_json()
            ad["xref"] = xref
            ad["yref"] = yref
            parent_fig.add_annotation(ad, row=row, col=col)


def _norm_shape_name(s: str) -> str:
    """Normalise shape names across the app so diagrams behave consistently."""
    s = (s or "").strip()
    lo = s.lower()

    # Rect
    if "rectangle" in lo or lo == "rect":
        return "Rectangular"

    # T / I
    if lo in {"t", "t section", "t-section", "t beam"} or lo.startswith("t"):
        return "T-Section"
    if lo in {"i", "i section", "i-section", "i beam"} or lo.startswith("i"):
        return "I-Section"

    # Already normalised?
    if "t-section" in lo:
        return "T-Section"
    if "i-section" in lo:
        return "I-Section"
    if "rectangular" in lo:
        return "Rectangular"

    # Fallback – return as-is
    return s


def _get_current_shape_from_session() -> str:
    """Best-effort read of current shape selection from session state."""
    import streamlit as st
    raw = (
        st.session_state.get("shape_name")
        or st.session_state.get("sec_shape")
        or st.session_state.get("section_shape")
        or st.session_state.get("geometry_section_shape")
        or "Rectangular"
    )
    return _norm_shape_name(str(raw))


def _get_layers(reo_layout: dict, side: str):
    if not reo_layout:
        return []
    keys = []
    if side == "top":
        keys = ["top", "top_flange", "top_web", "top_left", "top_right"]
    else:
        keys = ["bottom", "bottom_flange", "bottom_web", "bottom_left", "bottom_right"]

    out = []
    for k in keys:
        v = reo_layout.get(k)
        if not v:
            continue
        out += v if isinstance(v, list) else [v]
    return out

# ============================================================
# Shared stress-panel geometry (USED BY 3-PANEL + STEP FIGS)
# ============================================================
STRESS_X_AXIS = 0.10
STRESS_USABLE_W = 0.70
STRESS_MIN_VIS = 0.18   # same "minimum visible" rule as main 3-panel
STRESS_BOOST = 1.75     # tweak this globally (1.75 as requested)

def _stress_panel_x_positions(sigma_c: float, sigma_s: float):
    """
    Return (stress_max, x_axis, x_block_right, x_T)
    using the SAME scaling conventions as the 3-panel Stress diagram.
    """
    sigma_c = float(max(0.0, sigma_c))
    sigma_s = float(max(0.0, sigma_s))
    stress_max = max(sigma_c, sigma_s, 1.0)

    x_axis = STRESS_X_AXIS
    usable_width = STRESS_USABLE_W

    # concrete width (boosted for readability, clamped)
    ratio_c = sigma_c / stress_max if stress_max > 0 else 0.0
    block_width_vis = ratio_c * usable_width * STRESS_BOOST
    block_width_vis = max(STRESS_MIN_VIS, block_width_vis)
    block_width_vis = min(usable_width, block_width_vis)
    x_block_right = x_axis + block_width_vis

    # steel to-scale (NO boost)
    x_T = x_axis + (sigma_s / stress_max) * usable_width
    return stress_max, x_axis, x_block_right, x_T


# ------------------------------------------------------------
# Helper: parabolic concrete stress (for Parabolic view)
# (kept for possible future use – current parabolic block
#  uses a simple textbook 2z − z² profile directly)
# ------------------------------------------------------------
def _sigma_c_parabolic(eps, sigma_peak, eps0=0.002, eps_cu=0.003):
    """
    Simple Hognestad-style parabolic + linear softening model.

    eps        : compressive strain (>= 0, concrete)
    sigma_peak : peak compressive stress used for this diagram (MPa)
                 (we use alpha2 * f'c so the scale matches the ULS block)
    """
    if eps <= 0.0:
        return 0.0
    if eps <= eps0:
        x = eps / eps0
        return sigma_peak * (2.0 * x - x**2)
    if eps <= eps_cu:
        return sigma_peak * (eps_cu - eps) / (eps_cu - eps0)
    return 0.0


# ------------------------------------------------------------
# DIAGRAM LAYOUT / LABEL SPACING CONVENTIONS
# ------------------------------------------------------------
# We keep all labels a consistent distance from each diagram so
# the 3 panels look aligned and clean. Rules:
#
# 1) SECTION PANEL (col 1)
#    - Section rectangle spans x = 0 → b, y = 0 → D.
#    - All vertical depth arrows (d, d_n, etc.) sit on the SAME
#      vertical line, a fixed distance to the right of the beam:
#
#        margin_right_section = 0.20 * b      # arrow line
#        text_dx_section      = 0.04 * b      # extra for label text
#
#      So:
#        x_d  = b + margin_right_section
#        x_dn = b + margin_right_section
#
#      Labels:
#        d-label   at (x_d  + text_dx_section,  d  / 2)
#        d_n-label at (x_dn + text_dx_section,  c  / 2)
#
#    - NO other "magic" x-offsets should be used for depth labels
#      in this panel – they must all derive from these margins.
#
# 2) STRAIN PANEL (col 2)
#    - Depth axis runs y = 0 → D.
#    - We keep labels close to their points using a fixed pixel
#      y-shift rather than ad-hoc coordinates:
#
#        eps_label_shift = 12  # pixels
#
#      So:
#        ε_c label: yshift = -eps_label_shift  (above top fibre)
#        ε_s label: yshift = +eps_label_shift  (below steel point)
#
#    - Any other strain labels should reuse this same yshift
#      pattern (above = -shift, below = +shift).
#
# 3) STRESS PANEL (col 3)
#    - Compression region for concrete sits between:
#        x = x_axis → x_block_right
#        y = block_top → block_bottom
#    - Top stress width arrow + label (α₂ f'c or E_c ε_c)
#      sit in a fixed "top band" above the block:
#
#        top_band_arrow_y = -0.06 * D   # arrow line
#        top_band_label_y = -0.12 * D   # label text
#
#      The width arrow is centred between x_axis and x_block_right,
#      and the label is centred at the same x, at top_band_label_y.
#
#    - Depth arrow on the right (γ d_n or d_n) uses a single
#      horizontal margin beyond the block:
#
#        margin_right_stress = 0.08 * D
#        text_dx_stress      = 0.04 * D
#
#      So:
#        x_gc (depth arrow line) = x_block_right + margin_right_stress
#        depth label text at x = x_gc + text_dx_stress,
#        y = 0.5 * (block_top + block_bottom).
#
#    - All right-hand labels in this panel (depth labels) should
#      reuse these margins, not introduce new offsets.
#
# 4) SLS STRESS-BLOCK FIGURES
#    - For _make_sls_stress_block_figure and related SLS figures,
#      we mirror the stress panel conventions using D_ref instead
#      of D:
#
#        top_band_arrow_y = -0.06 * D_ref
#        top_band_label_y = -0.12 * D_ref
#
#      The "E_c ε_c" arrow + label must use those y-positions so
#      they visually line up with the main stress panel.
#
# Summary:
#   - Section panel → 0.20b arrow, 0.24b labels (to the right).
#   - Strain panel → fixed ±eps_label_shift yshift.
#   - Stress panels → 0.06D arrow band, 0.12D label band above,
#     0.08D right margin + 0.04D label offset for depth labels.
#   - Do NOT add new arbitrary offsets; reuse these margins.
# ------------------------------------------------------------

# ============================================================
#  MAIN 3-PANEL SECTION / STRAIN / STRESS DIAGRAM
# ============================================================
def _plot_stress_strain_profiles(state_dict, state_label=None, layout=None):
    """
    Three-panel Plotly figure:
        - Section (left)
        - Strain (centre)
        - Stress (right)
    
    Args:
        state_dict: State dictionary with strain/stress values
        state_label: Optional explicit state label
        layout: Optional pre-computed section layout dict. If None, will compute from session state.
    """
    # ------------------------------------
    # Decide which "state" we're in:
    #   1) explicit argument from the tab
    #   2) otherwise fall back to session
    #   3) otherwise default to ULS
    # ------------------------------------
    label_from_call = state_label

    try:
        label_from_session = st.session_state.get(
            "bending_strain_state_local", None
        )
    except Exception:
        label_from_session = None

    # IMPORTANT: strain state (ULS / SLS / Uncracked) comes from session.
    # The function argument is only a fallback, so the concrete
    # stress-model radio ("Rectangular", "Parabolic" etc.) can't override it.
    if label_from_session:
        state_label = label_from_session
    elif label_from_call is not None:
        state_label = label_from_call
    else:
        state_label = "ULS"

    # Normalise for logic (robust to different display text)
    label_str = str(state_label or "ULS").strip()
    label_low = label_str.lower()

    is_uls = label_low.startswith("uls")
    is_sls = ("sls" in label_low)
    is_uncracked = ("uncracked" in label_low)

    is_parabolic = ("parabolic" in label_low)

    # Only default to ULS if we truly don't recognise the state
    if (not is_uls) and (not is_sls) and (not is_uncracked):
        is_uls = True

    # unpack bending state
    b = state_dict["b"]
    D = state_dict["D"]
    d = state_dict["d"]
    c = state_dict["c"]
    eps_c_raw = state_dict["eps_c"]
    eps_s_raw = state_dict["eps_s"]
    gamma = state_dict["gamma"]
    fs_t = state_dict["fs_t"]
    fc = state_dict["fc"]
    alpha2 = state_dict["alpha2"]

    # ------------------------------------------
    # SLS override: use exact values from SLS tab
    # (bending_sls_dn, bending_sls_eps_top, bending_sls_eps_bot, bending_sls_y_bot)
    # ------------------------------------------
    eps_top_sls = None
    eps_bot_sls = None
    y_bot_sls = None
    y_s = d  # Default to d, will be overridden for SLS in strain panel
    
    if is_sls:
        # Override neutral axis depth from SLS tab
        dn_sls = st.session_state.get("bending_sls_dn", None)
        if dn_sls is not None:
            try:
                c = float(dn_sls)
            except Exception:
                pass
        
        # Get exact strains and steel depth from SLS tab (solver sign convention:
        # compression negative, tension positive)
        eps_top_sls = st.session_state.get("bending_sls_eps_top", None)
        eps_bot_sls = st.session_state.get("bending_sls_eps_bot", None)
        y_bot_sls = st.session_state.get("bending_sls_y_bot", None)
        
        # Override y_s for SLS if available
        if y_bot_sls is not None:
            try:
                y_s = float(y_bot_sls)
            except Exception:
                pass

    # -----------------------------
    # Concrete + steel stress scales
    # -----------------------------
    # Steel (kept to scale)
    sigma_s = abs(fs_t)

    if is_sls:
        try:
            fs_ser = get_param("sigma_s_sls", None)
        except Exception:
            fs_ser = None
        try:
            if fs_ser is not None:
                val = float(fs_ser)
                if not math.isnan(val) and abs(val) > 0.0:
                    sigma_s = abs(val)
        except Exception:
            pass

    # Concrete "width stress":
    # - ULS: alpha2 * f'c
    # - SLS/Uncracked: Ec * eps_c (elastic top fibre)
    try:
        Ec = float(get_param("Ec", 30000.0))
    except Exception:
        Ec = 30000.0

    # best-available compression strain for scaling (compression plotted as +)
    if is_sls and (eps_top_sls is not None):
        try:
            eps_c_for_scale = abs(float(eps_top_sls))  # solver may store compression as negative
        except Exception:
            eps_c_for_scale = abs(float(eps_c_raw))
    else:
        eps_c_for_scale = abs(float(eps_c_raw))

    if is_uls:
        sigma_c = alpha2 * fc
        label_text_top = f"α₂ f'c = {sigma_c:.0f} MPa"
    else:
        sigma_c = abs(Ec * eps_c_for_scale)
        label_text_top = f"E_c ε_c = {sigma_c:.0f} MPa"

    # Fixed reference stress so SLS/Uncracked don't blow up visually
    try:
        fsy = float(get_param("fsy", 500.0))
    except Exception:
        fsy = 500.0
    stress_ref = max(alpha2 * fc, fsy, 1.0)

    # -------------------------------------
    # Create 3-column subplot figure
    # -------------------------------------
    fig = make_subplots(
        rows=1,
        cols=3,
        shared_yaxes=True,
        horizontal_spacing=0.08,
        specs=[[{"type": "xy"}, {"type": "xy"}, {"type": "xy"}]],
        subplot_titles=["Section", "Strain", "Stress (MPa)"],
    )

    # consistent y-range across panels (0 at top, D at bottom)
    # Give extra headroom so the top-band label at -0.12D is visible
    y_range = [D * 1.05, -0.18 * D]

    # hide all axes, no grid / ticks
    for i in range(1, 4):
        fig.update_xaxes(
            visible=False,
            row=1,
            col=i,
            showgrid=False,
            zeroline=False,
        )
        fig.update_yaxes(
            visible=False,
            row=1,
            col=i,
            showgrid=False,
            zeroline=False,
            range=y_range,
        )

    # =====================================================
    # 1) SECTION PANEL – Rect stays legacy, I/T uses mini-app
    # =====================================================
    from section_layout import compute_section_layout

    current_shape = _get_current_shape_from_session()

    # If caller didn't supply layout, compute it.
    if layout is None:
        layout = compute_section_layout()
    else:
        # If caller supplied a stale layout (common), refresh it when shape changed.
        layout_shape = _norm_shape_name(str(layout.get("shape_name", "")))
        if layout_shape != current_shape:
            layout = compute_section_layout()

    # Determine shape
    shape_name_str = _norm_shape_name(str(layout.get("shape_name", "Rectangular")))
    is_T = shape_name_str == "T-Section"
    is_I = shape_name_str == "I-Section"

    if is_T or is_I:
        # Build the exact mini-app figure
        dims = dict(layout.get("dims", {}))
        reo = dict(layout.get("reo", {}))
        lig = layout.get("lig", {})

        # Neutral axis depth for shading (use c as dn)
        dn = float(state_dict.get("c", 0.0) or 0.0)

        reo_err = None
        try:
            sec_fig = make_sectionA_figure(
                shape_name=shape_name_str,
                dims=dims,
                reo=reo,
                show_shear=bool(lig.get("d", 0.0) or 0.0),
                dn=dn,
                show_dn=True,
            )
            W = float(dims.get("bf", dims.get("b", 0.0)) or 0.0)
            D = float(dims.get("D", 0.0) or 0.0)
            apply_section_axes(sec_fig, W=W, D=D)
        except ValueError as e:
            reo_err = str(e)

        if reo_err:
            st.error(reo_err)
            reo_no_bars = dict(reo)
            reo_no_bars.update({
                "nb_top": 0,
                "db_top": 0.0,
                "nb_bot": 0,
                "db_bot": 0.0,
                "lig_d": 0.0,
                "lig_legs": 0,
            })
            sec_fig = make_sectionA_figure(
                shape_name=shape_name_str,
                dims=dims,
                reo=reo_no_bars,
                show_shear=False,
                dn=dn,
                show_dn=True,
            )
            W = float(dims.get("bf", dims.get("b", 0.0)) or 0.0)
            D = float(dims.get("D", 0.0) or 0.0)
            apply_section_axes(sec_fig, W=W, D=D)

        _inject_figure_into_subplot(fig, sec_fig, row=1, col=1, xref="x1", yref="y1")

        # Enforce 1:1 aspect like your current plots
        fig.update_yaxes(scaleanchor="x", scaleratio=1, row=1, col=1)

    else:
        # ---- legacy rectangular section panel (keep EXACTLY as before) ----
        b = layout["b"]
        D = layout["D"]
        
        # Lock panel x-ranges so blocks/labels don't get squeezed by autorange/aspect effects
        fig.update_xaxes(range=[-0.05, b + 0.35 * b], row=1, col=1)  # section
        fig.update_xaxes(range=[0.0, 1.0], row=1, col=2)             # strain (panel coords)
        # Stress panel x-range will be set dynamically after computing x_T, x_block_right, x_gc
        cage = layout["cage"]
        reo_layout = layout.get("reo_layout")  # Get 2-layer structure

        # outer concrete
        fig.add_shape(
            type="rect",
            x0=0,
            y0=0,
            x1=b,
            y1=D,
            line=dict(color="black", width=1.2),
            fillcolor="rgba(0,0,0,0)",
            row=1,
            col=1,
        )

        # Shear reinforcement (stirrups/ties) - only draw when present
        lig = layout.get("lig", {})
        lig_d = lig.get("d", 0.0)
        lig_legs = lig.get("legs", 2)
        
        # Only draw shear reinforcement if it's actually specified
        has_shear = lig_d > 0 and lig_legs >= 2
        
        if has_shear:
            # Compute shear reinforcement layout using values from layout dict
            from section_layout import compute_shear_reo_layout_pure
            
            # Extract cover values from cage position (layout already computed with correct covers)
            cover_side_est = max(5.0, cage["x0"])  # approximate from cage
            cover_top_est = max(5.0, cage["y0"])
            cover_bot_est = max(5.0, D - cage["y1"])
            
            # Compute shear layout with same covers as used for cage
            shear_layout = compute_shear_reo_layout_pure(
                b=b, D=D,
                cover_bot=cover_bot_est, cover_top=cover_top_est, cover_side=cover_side_est,
                lig_d=lig_d, lig_legs=lig_legs,
            )
            
            # Draw cage outline (only when shear reo is present)
            cage_shear = shear_layout.get("cage", cage)
            fig.add_shape(
                type="rect",
                x0=cage_shear["x0"],
                y0=cage_shear["y0"],
                x1=cage_shear["x1"],
                y1=cage_shear["y1"],
                line=dict(color="black", width=1.0),
                fillcolor="rgba(0,0,0,0)",
                row=1,
                col=1,
            )
            
            # Draw stirrup legs in black
            lig_line_width = max(1.0, min(4.0, abs(lig_d) / 3.0))
            for stirrup in shear_layout.get("stirrups", []):
                for leg in stirrup.get("legs", []):
                    fig.add_shape(
                        type="line",
                        x0=leg["x1"],
                        y0=leg["y1"],
                        x1=leg["x2"],
                        y1=leg["y2"],
                        line=dict(color="black", width=lig_line_width),
                        row=1,
                        col=1,
                    )

        # ----------------------------------------
        # Compression region in SECTION panel
        #   ULS Rectangular → block to γ c
        #   ULS Parabolic   → block to d_n
        #   SLS/Uncracked   → block to d_n
        # ----------------------------------------
        if is_uls and not is_parabolic:
            block_depth_sec = max(0.0, min(gamma * c, D))
        else:
            block_depth_sec = max(0.0, min(c, D))

        fig.add_shape(
            type="rect",
            x0=0,
            y0=0,
            x1=b,
            y1=block_depth_sec,
            line=dict(color="red", width=1.0),
            fillcolor="rgba(199,227,255,0.7)",
            row=1,
            col=1,
        )

        # bottom/top bars - prefer canonical reo_points
        reo_points = layout.get("reo_points") or []
        if reo_points:
            for p in reo_points:
                layer = p.get("layer")
                color = "blue" if layer == "bottom" else ("red" if layer == "top" else None)
                if not color:
                    continue
                db = float(p.get("db", 0.0))
                marker_size = max(5, min(10, db * 0.35))
                fig.add_trace(
                    go.Scatter(
                        x=[float(p["x"])],
                        y=[float(p["y"])],
                        mode="markers",
                        marker=dict(
                            color=color,
                            size=marker_size,
                            line=dict(width=0.7, color="black"),
                        ),
                        hoverinfo="skip",
                        showlegend=False,
                    ),
                    row=1,
                    col=1,
                )
        elif reo_layout:
            # Fallback to legacy 2-layer structure
            for layer_data in reo_layout["bottom"]:
                x_positions = layer_data["x"]
                y_pos = layer_data["y"]
                db = layer_data["db"]
                marker_size = max(5, min(10, db * 0.35))
                fig.add_trace(
                    go.Scatter(
                        x=x_positions,
                        y=[y_pos] * len(x_positions),
                        mode="markers",
                        marker=dict(color="blue", size=marker_size, line=dict(width=0.7, color="black")),
                        hoverinfo="skip",
                        showlegend=False,
                    ),
                    row=1,
                    col=1,
                )
            for layer_data in reo_layout["top"]:
                x_positions = layer_data["x"]
                y_pos = layer_data["y"]
                db = layer_data["db"]
                marker_size = max(5, min(10, db * 0.35))
                fig.add_trace(
                    go.Scatter(
                        x=x_positions,
                        y=[y_pos] * len(x_positions),
                        mode="markers",
                        marker=dict(color="red", size=marker_size, line=dict(width=0.7, color="black")),
                        hoverinfo="skip",
                        showlegend=False,
                    ),
                    row=1,
                    col=1,
                )
        else:
            # Fallback to legacy flattened structure
            bot = layout.get("bot", {})
            if bot.get("x"):
                fig.add_trace(
                    go.Scatter(
                        x=bot["x"],
                        y=bot["y"],
                        mode="markers",
                        marker=dict(color="blue", size=7, line=dict(width=0.7, color="black")),
                        hoverinfo="skip",
                        showlegend=False,
                    ),
                    row=1,
                    col=1,
                )
            top = layout.get("top", {})
            if top.get("x"):
                fig.add_trace(
                    go.Scatter(
                        x=top["x"],
                        y=top["y"],
                        mode="markers",
                        marker=dict(color="red", size=7, line=dict(width=0.7, color="black")),
                        hoverinfo="skip",
                        showlegend=False,
                    ),
                    row=1,
                    col=1,
                )

        # ----------------------------------------
        # Depth labels next to section: d and d_n
        # ----------------------------------------
        beam_right = b  # section goes from x = 0 → b

        # SECTION PANEL: Consistent margins for depth arrows and labels
        margin_right_section = 0.20 * b
        text_dx_section = 0.04 * b
        
        # position of d arrow (aligned with d_n arrow)
        x_d = beam_right + margin_right_section
        if d:
            # double-ended depth arrow for d (two overlapping arrows)
            # top → bottom
            fig.add_annotation(
                x=x_d,
                y=d,
                ax=x_d,
                ay=0,
                xref="x1",
                yref="y1",
                axref="x1",
                ayref="y1",
                text="",
                showarrow=True,
                arrowhead=3,
                arrowsize=1.0,
                arrowwidth=1.0,
                arrowcolor="black",
                row=1,
                col=1,
            )
            # bottom → top
            fig.add_annotation(
                x=x_d,
                y=0,
                ax=x_d,
                ay=d,
                xref="x1",
                yref="y1",
                axref="x1",
                ayref="y1",
                text="",
                showarrow=True,
                arrowhead=3,
                arrowsize=1.0,
                arrowwidth=1.0,
                arrowcolor="black",
                row=1,
                col=1,
            )
            # label for d (placed mid-depth)
            fig.add_annotation(
                x=x_d + text_dx_section,
                y=d / 2.0,
                text=f"d = {d:.0f} mm",
                showarrow=False,
                font=dict(size=9, color="black"),
                xanchor="left",
                row=1,
                col=1,
            )

        # position of d_n arrow (moved right to align with label, in red)
        x_dn = beam_right + margin_right_section
        x_dn_arrow = x_dn + 0.40 * b  # move arrows right to align with label
        if c:
            # double-ended depth arrow for d_n
            # top → NA
            fig.add_annotation(
                x=x_dn_arrow,
                y=c,
                ax=x_dn_arrow,
                ay=0,
                xref="x1",
                yref="y1",
                axref="x1",
                ayref="y1",
                text="",
                showarrow=True,
                arrowhead=3,
                arrowsize=1.0,
                arrowwidth=1.0,
                arrowcolor="red",
                row=1,
                col=1,
            )
            # NA → top
            fig.add_annotation(
                x=x_dn_arrow,
                y=0,
                ax=x_dn_arrow,
                ay=c,
                xref="x1",
                yref="y1",
                axref="x1",
                ayref="y1",
                text="",
                showarrow=True,
                arrowhead=3,
                arrowsize=1.0,
                arrowwidth=1.0,
                arrowcolor="red",
                row=1,
                col=1,
            )
            # Move text to the right to avoid overlap with d = ... label
            fig.add_annotation(
                x=x_dn + text_dx_section + 0.40 * b,
                y=c / 2.0,
                text=f"dₙ = {c:.0f} mm",
                showarrow=False,
                font=dict(size=9, color="red"),
                xanchor="left",
                row=1,
                col=1,
            )

        # keep section 1:1 in x–y (width vs depth)
        fig.update_yaxes(
            scaleanchor="x",
            scaleratio=1,
            row=1,
            col=1,
        )

    # =====================================================
    # 2) STRAIN PANEL – **fixed sign convention**
    # =====================================================
    panel_x_center = 0.5
    half_w = 0.35

    if is_sls and eps_top_sls is not None and eps_bot_sls is not None and y_bot_sls is not None:
        # Solver uses compression negative, tension positive.
        # For the diagram we flip so compression > 0, tension < 0.
        eps_c_true = -float(eps_top_sls)   # top fibre (compression) → positive
        eps_s_true = -float(eps_bot_sls)   # bottom tension steel → negative
        y_s = float(y_bot_sls)
    else:
        # ULS / Uncracked: use state_dict values with same flip
        eps_s_source = state_dict.get("eps_s", 0.0)

        for key in [
            "eps_s_sls_bot",
            "eps_s_sls_bottom",
            "eps_s_bottom_sls",
        ]:
            try:
                val = st.session_state.get(key, None)
            except Exception:
                val = None
            if val is not None:
                eps_s_source = float(val)
                break

        # Flip so compression > 0, tension < 0
        eps_c_true = -float(eps_c_raw)
        eps_s_true = -float(eps_s_source)
        y_s = float(d)

    # ------------------------------------------------------------
    # Multi-layer steel stresses for the 3-panel STRESS diagram
    # (so it matches Step 3.2)
    # ------------------------------------------------------------
    try:
        Es = float(get_param("Es", 200000.0))  # MPa
    except Exception:
        Es = 200000.0

    def _eps_at_depth(y_layer: float) -> float:
        """
        Return signed strain at depth y_layer (same sign convention as eps_*_true):
          compression > 0, tension < 0
        Uses the two-segment linear strain profile:
          (0, eps_c_true) -> (c, 0) -> (y_s, eps_s_true)
        """
        y_layer = float(y_layer)

        if c <= 1e-9:
            # degenerate, just scale to bottom point
            if y_s <= 1e-9:
                return eps_s_true
            return eps_s_true * (y_layer / y_s)

        if y_layer <= c:
            # top segment (compression zone)
            return eps_c_true * (1.0 - y_layer / c)

        # bottom segment (tension zone)
        denom = (y_s - c)
        if abs(denom) <= 1e-9:
            return eps_s_true
        return eps_s_true * ((y_layer - c) / denom)

    # Magnitudes and scaling
    eps_c_mag = abs(eps_c_true)
    eps_s_mag = abs(eps_s_true)
    eps_max = max(eps_c_mag, eps_s_mag, 1e-4) * 1.3

    def strain_to_x(eps_true: float) -> float:
        """
        Map signed ε → x position.
        Centre = 0, right = compression (ε > 0), left = tension (ε < 0).
        """
        if eps_true >= 0.0:
            return panel_x_center + (abs(eps_true) / eps_max) * half_w
        else:
            return panel_x_center - (abs(eps_true) / eps_max) * half_w

    x_c = strain_to_x(eps_c_true)
    x_s = strain_to_x(eps_s_true)
    x_mid = panel_x_center  # neutral axis (ε = 0)

    # vertical depth line at ε = 0 (concrete depth axis)
    fig.add_shape(
        type="line",
        x0=panel_x_center,
        y0=0,
        x1=panel_x_center,
        y1=D,
        line=dict(color="black", width=1.0),
        row=1,
        col=2,
    )

    # strain line (top → NA → steel)
    fig.add_trace(
        go.Scatter(
            x=[x_c, x_mid, x_s],
            y=[0, c, y_s],
            mode="lines",
            line=dict(color="black", width=1.0),
            hoverinfo="skip",
            showlegend=False,
        ),
        row=1,
        col=2,
    )

    # neutral axis (dashed)
    fig.add_shape(
        type="line",
        x0=panel_x_center - 0.5,
        y0=c,
        x1=panel_x_center + 0.5,
        y1=c,
        line=dict(color="black", width=0.7, dash="dash"),
        row=1,
        col=2,
    )

    # STRAIN PANEL: Horizontal value lines with labels (not on diagonal)
    # Collect steel layers for multi-layer display (SLS/cracked) or single (ULS)
    steel_layers = []  # list of (y, eps_value)
    
    if is_sls and eps_top_sls is not None and eps_bot_sls is not None and y_bot_sls is not None:
        # SLS: collect all tension layers from reo_layout
        if reo_layout and isinstance(reo_layout, dict):
            for layer_data in _get_layers(reo_layout, "bottom"):
                try:
                    y_layer = float(layer_data["y"])
                    if y_layer > c + 1e-6:  # below NA (tension)
                        eps_layer = _eps_at_depth(y_layer)
                        steel_layers.append((y_layer, eps_layer))
                except Exception:
                    pass
        # Fallback: use single layer
        if not steel_layers:
            steel_layers = [(y_s, eps_s_true)]
    else:
        # ULS/Uncracked: single steel reference (resultant level)
        steel_layers = [(y_s, eps_s_true)]
    
    # Top fibre horizontal line and label (ε_c)
    # Line from zero-strain axis to strain value
    x_c_end = strain_to_x(eps_c_true)
    fig.add_shape(
        type="line",
        x0=panel_x_center,
        y0=0,
        x1=x_c_end,
        y1=0,
        line=dict(color="red", width=1.5),
        row=1,
        col=2,
    )
    # Label just beyond line end (right if compression, left if tension) with small yshift
    if eps_c_true >= 0.0:  # compression (to the right)
        label_x = x_c_end + 0.02
        xanchor = "left"
    else:  # tension (to the left)
        label_x = x_c_end - 0.02
        xanchor = "right"
    fig.add_annotation(
        x=label_x,
        y=0,
        text=f"ε_c = {eps_c_true:.4f}",
        showarrow=False,
        font=dict(size=9, color="red"),
        yshift=-8,  # pixels up
        xanchor=xanchor,
        row=1,
        col=2,
    )
    
    # Steel layer horizontal lines and labels (ε_s)
    for y_layer, eps_layer in steel_layers:
        # Line from zero-strain axis to strain value
        x_s_end = strain_to_x(eps_layer)
        fig.add_shape(
            type="line",
            x0=panel_x_center,
            y0=y_layer,
            x1=x_s_end,
            y1=y_layer,
            line=dict(color="blue", width=1.5),
            row=1,
            col=2,
        )
        # Label just past line end with yshift=+10 (down) so it's clear of diagonal
        if eps_layer >= 0.0:  # compression (to the right)
            label_x = x_s_end + 0.02
            xanchor = "left"
        else:  # tension (to the left)
            label_x = x_s_end - 0.02
            xanchor = "right"
        fig.add_annotation(
            x=label_x,
            y=y_layer,
            text=f"ε_s = {eps_layer:.4f}",
            showarrow=False,
            font=dict(size=9, color="blue"),
            yshift=10,  # pixels down
            xanchor=xanchor,
            row=1,
            col=2,
        )

    # (optional but nice) clarify sign convention for this panel
    fig.update_xaxes(
        title_text="Strain ε (tension ε < 0, compression ε > 0)",
        row=1,
        col=2,
        visible=False,
    )

    # =====================================================
    # 3) STRESS PANEL – uses σ_s,ser at SLS
    # =====================================================
    # Horizontal layout (0–1 in panel coords)
    x_axis = 0.10
    usable_width = 0.70  # max span to the right we ever use

    def stress_to_x(sig: float) -> float:
        """Map a stress σ → x position along the stress axis."""
        return x_axis + (sig / stress_ref) * usable_width

    # Steel tension stress (still drawn to scale but with a minimum visual width)
    x_T = stress_to_x(sigma_s)

    # Guarantee a *visible* horizontal steel width even if σ_s ≈ 0
    min_steel_gap = 0.18  # in panel x-coords
    if abs(x_T - x_axis) < min_steel_gap:
        x_T = x_axis + min_steel_gap

    # Concrete block width based on σ_c but with a minimum visual size
    if stress_ref > 0.0:
        ratio_c = max(0.0, sigma_c) / stress_ref
    else:
        ratio_c = 0.0

    # ----------------------------
    # Visual width tuning by state
    # ----------------------------
    if is_uncracked:
        # Uncracked: keep it close to true scale (no exaggeration)
        min_vis = 0.06
        scale_boost = 1.00
        max_frac = 0.25
    elif is_sls:
        # SLS cracked: readability boost
        min_vis = 0.12
        scale_boost = 1.75
        max_frac = 0.45
    else:
        # ULS: readability boost
        min_vis = 0.12
        scale_boost = 1.75
        max_frac = 0.45

    block_width_vis = ratio_c * usable_width * scale_boost
    block_width_vis = max(min_vis, block_width_vis)
    block_width_vis = min(usable_width * max_frac, block_width_vis)

    x_block_right = x_axis + block_width_vis

    # Vertical stress axis
    fig.add_shape(
        type="line",
        x0=x_axis,
        y0=0,
        x1=x_axis,
        y1=D,
        line=dict(color="black", width=1.0),
        row=1,
        col=3,
    )

    # Tension arrows (steel) - SLS: per-layer, ULS: single resultant
    if is_sls:
        # SLS: draw one arrow per tension layer (same layers as strain panel)
        x_T_max = x_T  # track max x for x_right calculation
        for i, (y_layer, eps_layer) in enumerate(steel_layers, start=1):
            # Calculate stress for this layer (elastic: σ = Es * |ε|)
            sig_layer = Es * abs(eps_layer)  # MPa
            x_T_layer = stress_to_x(sig_layer)
            
            # Apply minimum visual width
            if abs(x_T_layer - x_axis) < min_steel_gap:
                x_T_layer = x_axis + min_steel_gap
            
            # Draw arrow for this layer
            fig.add_annotation(
                x=x_T_layer,
                y=y_layer,
                ax=x_axis,
                ay=y_layer,
                xref="x3",
                yref="y3",
                axref="x3",
                ayref="y3",
                text="",
                showarrow=True,
                arrowhead=3,
                arrowsize=1.0,
                arrowwidth=1.2,
                arrowcolor="blue",
                row=1,
                col=3,
            )
            # Label: T1, T2, etc.
            fig.add_annotation(
                x=x_T_layer + 0.04,
                y=y_layer,
                text=f"T{i} ({sig_layer:.0f} MPa)",
                showarrow=False,
                font=dict(size=9, color="blue"),
                xanchor="left",
                row=1,
                col=3,
            )
            x_T_max = max(x_T_max, x_T_layer)
        
        # Update x_T for x_right calculation
        x_T = x_T_max
    else:
        # ULS/Uncracked: single resultant arrow
        y_steel = y_s if (is_sls and y_bot_sls is not None) else d
        fig.add_annotation(
            x=x_T,
            y=y_steel,
            ax=x_axis,
            ay=y_steel,
            xref="x3",
            yref="y3",
            axref="x3",
            ayref="y3",
            text="",
            showarrow=True,
            arrowhead=3,
            arrowsize=1.0,
            arrowwidth=1.2,
            arrowcolor="blue",
            row=1,
            col=3,
        )
        fig.add_annotation(
            x=x_T + 0.04,
            y=y_steel,
            text=f"T ({sigma_s:.0f} MPa)",
            showarrow=False,
            font=dict(size=9, color="blue"),
            xanchor="left",
            row=1,
            col=3,
        )

    # -----------------------------
    # Compression block in STRESS
    # -----------------------------
    if is_uls and not is_parabolic:
        # ULS rectangular block
        block_top = 0.0
        block_bottom = gamma * c
        fig.add_shape(
            type="rect",
            x0=x_axis,
            y0=block_top,
            x1=x_block_right,
            y1=block_bottom,
            line=dict(color="red", width=1.0),
            fillcolor="rgba(255,200,200,0.2)",
            row=1,
            col=3,
        )

    elif is_parabolic:
        # Parabolic block from top fibre down to d_n
        block_top = 0.0
        block_bottom = c if c else 0.0

        if block_bottom > block_top:
            n_pts = 60
            ys = np.linspace(block_top, block_bottom, n_pts)

            # Dimensionless depth from NA (0 at NA, 1 at top fibre):
            z = 1.0 - ys / max(block_bottom, 1e-6)

            # Simple parabolic profile: 0 at NA, σ_c at top (shape only)
            sigma_profile = (2.0 * z - z**2)
            sigma_profile = np.clip(sigma_profile, 0.0, None)

            sigma_ref = max(np.max(sigma_profile), 1e-6)
            x_profile = [
                x_axis + (s / sigma_ref) * block_width_vis for s in sigma_profile
            ]

            polygon_x = [x_axis] + x_profile + [x_axis]
            polygon_y = [block_top] + list(ys) + [block_bottom]

            fig.add_trace(
                go.Scatter(
                    x=polygon_x,
                    y=polygon_y,
                    mode="lines",
                    fill="toself",
                    fillcolor="rgba(255,200,200,0.3)",
                    line=dict(color="red", width=1.5),
                    hoverinfo="skip",
                    showlegend=False,
                ),
                row=1,
                col=3,
            )
        else:
            block_bottom = block_top

    else:
        # TRIANGULAR SLS / UNCRACKED block
        block_top = 0.0
        block_bottom = c
        triangle_x = [x_axis, x_axis, x_block_right, x_axis]
        triangle_y = [block_bottom, block_top, block_top, block_bottom]
        fig.add_trace(
            go.Scatter(
                x=triangle_x,
                y=triangle_y,
                mode="lines",
                fill="toself",
                fillcolor="rgba(255,200,200,0.3)",
                line=dict(color="red", width=1.5),
                hoverinfo="skip",
                showlegend=False,
            ),
            row=1,
            col=3,
        )

    # dashed NA in stress panel
    fig.add_shape(
        type="line",
        x0=x_axis - 0.05,
        y0=c,
        x1=x_axis + usable_width + 0.05,
        y1=c,
        line=dict(color="black", width=0.7, dash="dash"),
        row=1,
        col=3,
    )

    # -------------------------------------------------
    # Top-band width arrow + depth arrow – ALL states
    # -------------------------------------------------
    top_band_arrow_y = -0.06 * D
    top_band_label_y = -0.12 * D

    label_text = label_text_top

    # width arrow – double-ended via two arrows
    fig.add_annotation(
        x=x_block_right,
        y=top_band_arrow_y,
        ax=x_axis,
        ay=top_band_arrow_y,
        xref="x3",
        yref="y3",
        axref="x3",
        ayref="y3",
        text="",
        showarrow=True,
        arrowhead=3,
        arrowsize=1.0,
        arrowwidth=0.8,
        arrowcolor="red",
        row=1,
        col=3,
    )
    fig.add_annotation(
        x=x_axis,
        y=top_band_arrow_y,
        ax=x_block_right,
        ay=top_band_arrow_y,
        xref="x3",
        yref="y3",
        axref="x3",
        ayref="y3",
        text="",
        showarrow=True,
        arrowhead=3,
        arrowsize=1.0,
        arrowwidth=0.8,
        arrowcolor="red",
        row=1,
        col=3,
    )

    # label centred above the arrow
    fig.add_annotation(
        x=(x_axis + x_block_right) / 2.0,
        y=top_band_label_y,
        text=label_text,
        showarrow=False,
        font=dict(size=9, color="red"),
        xanchor="center",
        row=1,
        col=3,
    )

    # STRESS PANEL: Right-side margins for depth arrow and label
    # NOTE: stress-panel x is normalised (0..1), so keep these as panel-units (NOT mm).
    margin_right_stress = 0.06
    text_dx_stress = 0.03

    # γ d_n / d_n depth arrow + label (double-headed)
    x_gc = x_block_right + margin_right_stress
    # top→bottom arrow
    fig.add_annotation(
        x=x_gc,
        y=block_bottom,
        ax=x_gc,
        ay=block_top,
        xref="x3",
        yref="y3",
        axref="x3",
        ayref="y3",
        text="",
        showarrow=True,
        arrowhead=2,
        arrowsize=1.0,
        arrowwidth=0.8,
        arrowcolor="red",
        row=1,
        col=3,
    )
    # bottom→top arrow (double-headed)
    fig.add_annotation(
        x=x_gc,
        y=block_top,
        ax=x_gc,
        ay=block_bottom,
        xref="x3",
        yref="y3",
        axref="x3",
        ayref="y3",
        text="",
        showarrow=True,
        arrowhead=2,
        arrowsize=1.0,
        arrowwidth=0.8,
        arrowcolor="red",
        row=1,
        col=3,
    )

    if is_uls and not is_parabolic:
        depth_label = f"γ dₙ = {gamma * c:.0f} mm"
    else:
        depth_label = f"dₙ = {c:.0f} mm"

    fig.add_annotation(
        x=x_gc + text_dx_stress,
        y=(block_top + block_bottom) / 2.0,
        text=depth_label,
        showarrow=False,
        font=dict(size=9, color="red"),
        xanchor="left",
        row=1,
        col=3,
    )

    # Dynamic x-axis range for stress panel to prevent clipping
    # (x_T, x_block_right, and x_gc are now all computed)
    x_right = max(
        1.0,  # minimum range
        x_T + 0.18,  # steel arrow + label clearance
        x_gc + text_dx_stress + 0.10,  # depth label clearance
        x_block_right + 0.20  # block + comfort margin
    )
    fig.update_xaxes(range=[0.0, x_right], row=1, col=3)

    # internal compression arrows – keep them inside the block/triangle
    for frac in [0.25, 0.5, 0.75]:
        y_mid = block_top + frac * (block_bottom - block_top)

        if is_parabolic:
            # At each depth, compute the local parabolic stress
            if block_bottom > block_top:
                z_mid = 1.0 - y_mid / max(block_bottom, 1e-6)
                sigma_mid = sigma_c * (2.0 * z_mid - z_mid**2)
                sigma_mid = max(0.0, sigma_mid)
            else:
                sigma_mid = 0.0

            if sigma_mid <= 0.0:
                continue  # nothing to draw here

            sigma_ref = max(sigma_c, 1e-6)
            x_max = x_axis + (sigma_mid / sigma_ref) * (x_block_right - x_axis)

            x_tail = x_axis + 0.20 * (x_max - x_axis)
            x_head = x_axis + 0.75 * (x_max - x_axis)

        elif is_uls:
            # Rectangular ULS block – constant width
            x_tail = x_axis + 0.15 * (x_block_right - x_axis)
            x_head = x_block_right - 0.15 * (x_block_right - x_axis)

        else:
            # TRIANGULAR SLS / UNCRACKED:
            # triangle vertices: (x_axis, block_bottom), (x_axis, block_top), (x_block_right, block_top)
            if block_bottom > block_top:
                rel = (y_mid - block_top) / (block_bottom - block_top)
                rel = max(0.0, min(1.0, rel))
                x_max = x_axis + (1.0 - rel) * (x_block_right - x_axis)
            else:
                x_max = x_axis
            x_tail = x_axis + 0.20 * (x_max - x_axis)
            x_head = x_axis + 0.75 * (x_max - x_axis)

        fig.add_annotation(
            x=x_tail,
            y=y_mid,
            ax=x_head,
            ay=y_mid,
            xref="x3",
            yref="y3",
            axref="x3",
            ayref="y3",
            text="",
            showarrow=True,
            arrowhead=3,
            arrowsize=0.9,
            arrowwidth=0.7,
            arrowcolor="red",
            row=1,
            col=3,
        )

    # -------------------------------------
    # Final layout: no legend, tight margins
    # -------------------------------------
    fig.update_layout(
        showlegend=False,
        margin=dict(l=10, r=10, t=40, b=10),
        height=320,
        width=900,
    )

    return fig


# ============================================================
#  MATERIAL STRESS-STRAIN CURVES (for info box)
# ============================================================
def _plot_material_stress_strain_curves():
    """
    Plot concrete and steel stress–strain curves:

      - Concrete: simplified parabolic + tail (Hognestad-style)
      - Steel: tension side only, ε >= 0 (magnitude of strain)

    Steel SLS / ULS points come directly from the **bottom steel fibre**
    in the bending solution via _stress_strain_state() and the SLS tab
    (render_sls_tab), so that the material curves are consistent with
    the section / strain diagrams.
    """
    # --------- Material properties from shared state (safe fallbacks) ----------
    try:
        fc = float(get_param("fc", 40.0))          # MPa
        fsy = float(get_param("fsy", 500.0))      # MPa
        Ec = float(get_param("Ec", 30000.0))    # MPa
        Es = float(get_param("Es", 200000.0))  # MPa
    except Exception:
        fc, fsy, Ec, Es = 40.0, 500.0, 30000.0, 200000.0

    # =====================================================
    # STEEL CURVE – tension side, ε >= 0
    # =====================================================
    # Yield strain (for reference only – actual ULS/SLS points come from state)
    eps_y_ref = fsy / Es
    eps_u = min(25 * eps_y_ref, 0.025)  # plotting window

    # Plot ONLY the magnitude |ε| for steel
    eps_s = np.linspace(0.0, eps_u, 400)

    sig_s = []
    for e_abs in eps_s:
        # Piecewise shape: elastic → mild hardening → softening → tail
        if e_abs <= eps_y_ref:
            sig = Es * e_abs                          # Hooke's law
        elif e_abs <= 4 * eps_y_ref:
            factor = (e_abs - eps_y_ref) / (3 * eps_y_ref)
            sig = fsy * (1.0 + 0.1 * factor)         # gentle hardening up to ~1.1 fsy
        elif e_abs <= 10 * eps_y_ref:
            factor = (e_abs - 4 * eps_y_ref) / (6 * eps_y_ref)
            sig = fsy * (1.1 - 0.3 * factor)         # softening towards ~0.8 fsy
        else:
            sig = 0.8 * fsy                          # long plastic tail
        sig_s.append(sig)

    sig_s = np.array(sig_s)

    # ===== Bottom steel fibre at SLS & ULS from bending solution =====
    # We want the SLS point to match the *controlling tension layer* used
    # in the SLS tab + crack-width link.

    # ---------- SLS STEEL (strain + stress) ----------
    eps_s_sls = None   # signed strain from SLS section analysis
    fs_s_sls = None    # stress in MPa

    # (a) try to get strain from SLS tab (outermost tension layer)
    try:
        eps_s_from_state = st.session_state.get("bending_sls_eps_bot", None)
        if eps_s_from_state is not None:
            eps_s_sls = float(eps_s_from_state)
    except Exception:
        pass

    # (b) try to get stress from shared results: sigma_s_sls (controlling tension stress)
    try:
        fs_ser_shared = get_param("sigma_s_sls", None)
        if fs_ser_shared is not None:
            fs_s_sls = float(fs_ser_shared)
    except Exception:
        fs_ser_shared = None

    # (c) fall back to SLS internal state if anything missing
    try:
        sls_state = _stress_strain_state("SLS")
    except Exception:
        sls_state = None

    if sls_state is not None:
        if eps_s_sls is None:
            try:
                eps_s_sls = float(sls_state.get("eps_s", 0.0))
            except Exception:
                pass
        if fs_s_sls is None:
            try:
                fs_s_sls = float(sls_state.get("fs_t", 0.0))
            except Exception:
                pass

    # (d) if we still don't have a consistent pair, derive one from the other using Es
    if eps_s_sls is None and fs_s_sls is not None:
        eps_s_sls = fs_s_sls / Es
    if fs_s_sls is None and eps_s_sls is not None:
        fs_s_sls = Es * eps_s_sls

    # As a last resort, use an elastic point at ~0.6 fsy
    if eps_s_sls is None or fs_s_sls is None:
        fs_s_sls = 0.6 * fsy
        eps_s_sls = fs_s_sls / Es

    # Work with magnitudes on the plot
    eps_s_sls = min(max(0.0, abs(eps_s_sls)), eps_u)
    fs_s_sls = abs(fs_s_sls)

    # ---------- ULS STEEL (for reference point) ----------
    try:
        uls_state = _stress_strain_state("ULS")
    except Exception:
        uls_state = None

    if uls_state is not None:
        try:
            eps_s_uls = float(uls_state.get("eps_s", eps_y_ref))
        except Exception:
            eps_s_uls = eps_y_ref
        try:
            fs_s_uls = float(uls_state.get("fs_t", fsy))
        except Exception:
            fs_s_uls = fsy
    else:
        eps_s_uls = eps_y_ref
        fs_s_uls = fsy

    eps_s_uls = min(max(0.0, abs(eps_s_uls)), eps_u)
    fs_s_uls = abs(fs_s_uls)

    # =====================================================
    # CONCRETE – compression curve
    # =====================================================
    eps0 = 0.002              # strain at peak
    eps_cu = 0.003            # ultimate comp. strain
    sigma_peak = 0.85 * fc    # peak stress

    eps_c = np.linspace(0.0, 0.0035, 200)
    sig_c = np.array([
        _sigma_c_parabolic(eps, sigma_peak, eps0=eps0, eps_cu=eps_cu)
        for eps in eps_c
    ])

    # ---------- SLS concrete point – use actual top-fibre strain if available ----------
    eps_c_sls = None
    sig_c_sls = None

    try:
        eps_top_state = st.session_state.get("bending_sls_eps_top", None)
        if eps_top_state is not None:
            eps_c_sls = float(eps_top_state)
    except Exception:
        pass

    if eps_c_sls is not None:
        # use magnitude for plotting (compression > 0)
        eps_c_sls = abs(eps_c_sls)
        sig_c_sls = Ec * eps_c_sls
    else:
        # fallback to previous approximate point ~0.45 f'c
        sig_c_sls = 0.45 * fc
        eps_c_sls = sig_c_sls / Ec

    # ULS concrete point at peak of the parabola
    eps_c_uls = eps0
    sig_c_uls = sigma_peak

    # =====================================================
    # 2-panel figure
    # =====================================================
    fig = make_subplots(
        rows=1,
        cols=2,
        shared_yaxes=False,
        horizontal_spacing=0.12,
        subplot_titles=["Concrete – compression", "Steel – tension (|ε|)"],
    )

    # ----- Concrete panel ---------------------------------
    fig.add_trace(
        go.Scatter(
            x=eps_c,
            y=sig_c,
            mode="lines",
            line=dict(width=2),
            name="Concrete",
            hoverinfo="x+y",
        ),
        row=1,
        col=1,
    )

    # SLS & ULS markers for concrete (now consistent with SLS strain state)
    fig.add_trace(
        go.Scatter(
            x=[eps_c_sls],
            y=[sig_c_sls],
            mode="markers+text",
            marker=dict(size=7),
            text=["SLS"],
            textposition="top center",
            name="Concrete SLS",
            hoverinfo="x+y+text",
        ),
        row=1,
        col=1,
    )
    fig.add_trace(
        go.Scatter(
            x=[eps_c_uls],
            y=[sig_c_uls],
            mode="markers+text",
            marker=dict(size=7),
            text=["ULS"],
            textposition="top center",
            name="Concrete ULS",
            hoverinfo="x+y+text",
        ),
        row=1,
        col=1,
    )

    fig.update_xaxes(
        title_text="Strain ε (compression > 0)",
        row=1,
        col=1,
        zeroline=True,
        zerolinewidth=1,
    )
    fig.update_yaxes(
        title_text="Stress σ (MPa)",
        row=1,
        col=1,
        zeroline=True,
        zerolinewidth=1,
    )

    # ----- Steel panel (bottom steel fibre, tension, |ε|) ----
    fig.add_trace(
        go.Scatter(
            x=eps_s,
            y=sig_s,
            mode="lines",
            line=dict(width=2),
            name="Steel",
            hoverinfo="x+y",
        ),
        row=1,
        col=2,
    )

    # ULS point for bottom steel fibre
    fig.add_trace(
        go.Scatter(
            x=[eps_s_uls],
            y=[fs_s_uls],
            mode="markers+text",
            marker=dict(size=7, color="blue"),
            text=["ULS"],
            textposition="top center",
            name="Steel ULS",
            hoverinfo="x+y+text",
        ),
        row=1,
        col=2,
    )

    # SLS point for controlling SLS tension layer
    fig.add_trace(
        go.Scatter(
            x=[eps_s_sls],
            y=[fs_s_sls],
            mode="markers+text",
            marker=dict(size=7, color="deepskyblue"),
            text=["SLS"],
            textposition="top center",
            name="Steel SLS",
            hoverinfo="x+y+text",
        ),
        row=1,
        col=2,
    )

    # Vertical guides at |ε_s,ULS| and |ε_s,SLS|
    y_guide_max = max(fs_s_uls, fs_s_sls) * 1.15
    for x_val, colr, dash in [
        (eps_s_uls, "blue", "dash"),
        (eps_s_sls, "deepskyblue", "dot"),
    ]:
        fig.add_shape(
            type="line",
            x0=x_val,
            y0=0,
            x1=x_val,
            y1=y_guide_max,
            line=dict(color=colr, width=1, dash=dash),
            row=1,
            col=2,
        )

    fig.update_xaxes(
        title_text="Strain ε (tension, magnitude |ε_s| ≥ 0)",
        row=1,
        col=2,
        zeroline=True,
        zerolinewidth=1,
        range=[0, eps_u],
    )
    fig.update_yaxes(
        title_text="Stress σ (MPa, magnitude)",
        row=1,
        col=2,
        zeroline=True,
        zerolinewidth=1,
        range=[0, y_guide_max],
    )

    fig.update_layout(
        showlegend=False,
        margin=dict(l=40, r=20, t=40, b=40),
        height=320,
    )

    return fig


# ============================================================
#  ULS STRESS BLOCK FIGURE (1.1 / 1.3 VARIANTS)
# ============================================================
#  ULS STRESS BLOCK FIGURE (1.1 / 1.4 VARIANTS)
# ============================================================
def _make_uls_stress_block_figure(
    b_mm: float,
    D_mm: float,
    d_mm: float,
    dn_mm: float,
    a_mm: float,
    alpha2: float,
    gamma: float,
    fc: float,
    fsy: float,
    show_lever_arm: bool = False,  # kept for API, not used
    show_dn: bool = True,
    show_alpha_label: bool = True,
    show_C: bool = False,
    C_N: float | None = None,
    variant: str = "11",
):
    """
    ORIGINAL hand-drawn-style ULS stress block using Plotly.
    
    This function does NOT use the 3-panel diagram spacing conventions.
    It maintains its own fixed-position layout for the hand-sketch style.

    variant = "11" → Step 1.1 simple block (plus bottom steel stress line)
    variant = "13" → Step 1.4 full block (with d_n, T, etc.)

    All variants use a *normalised display depth* so all diagrams
    are the same size and sit centrally in their calc boxes.
    """
    vals = [D_mm, d_mm, dn_mm, a_mm, alpha2, gamma, fc, fsy]
    if any(v is None or (isinstance(v, float) and math.isnan(v)) for v in vals):
        fig = go.Figure()
        fig.update_xaxes(visible=False)
        fig.update_yaxes(visible=False)
        fig.add_annotation(text="No data", x=0.5, y=0.5, xref="paper", yref="paper")
        return fig

    if D_mm is None or D_mm <= 0:
        D_mm = 600.0

    # Normalised depth (keep your existing behaviour)
    D_disp = 300.0
    scale = D_disp / float(D_mm)
    a_disp = a_mm * scale
    dn_disp = dn_mm * scale
    d_disp = d_mm * scale

    sigma_c = float(alpha2) * float(fc)     # α2 f'c
    sigma_s = float(abs(fsy))               # show T at fsy for the step figs

    # === SAME scaling as 3-panel stress diagram ===
    stress_max, x_axis, x_block_right, x_T = _stress_panel_x_positions(sigma_c, sigma_s)

    # Top-band + right-margin conventions (same as 3-panel)
    top_band_arrow_y = -0.06 * D_disp
    top_band_label_y = -0.12 * D_disp
    # IMPORTANT: x is normalised (0..1) in this figure, so margins must be panel-units (NOT mm)
    margin_right_stress = 0.06
    text_dx_stress = 0.03

    block_top = 0.0
    block_bottom = a_disp

    fig = go.Figure()

    # Vertical stress axis
    fig.add_shape(
        type="line",
        x0=x_axis,
        y0=0.0,
        x1=x_axis,
        y1=D_disp,
        line=dict(color="black", width=2),
    )

    # Compression block (ULS rectangular)
    fig.add_shape(
        type="rect",
        x0=x_axis,
        y0=block_top,
        x1=x_block_right,
        y1=block_bottom,
        line=dict(color="red", width=2),
        fillcolor="rgba(255, 200, 200, 0.12)",
    )

    # Internal compression arrows (kept inside)
    block_h = max(block_bottom - block_top, 1.0)
    ys = np.linspace(block_top + 0.2 * block_h, block_bottom - 0.2 * block_h, 3)
    for yy in ys:
        fig.add_annotation(
            x=x_axis + 0.15 * (x_block_right - x_axis),
            y=yy,
            ax=x_block_right - 0.15 * (x_block_right - x_axis),
            ay=yy,
            xref="x",
            yref="y",
            axref="x",
            ayref="y",
            showarrow=True,
            arrowhead=3,
            arrowsize=1.0,
            arrowwidth=1.5,
            arrowcolor="red",
        )

    # α2 f'c width arrow + label (same "top band" placement as 3-panel)
    if show_alpha_label:
        # left → right
        fig.add_annotation(
            x=x_block_right,
            y=top_band_arrow_y,
            ax=x_axis,
            ay=top_band_arrow_y,
            xref="x",
            yref="y",
            axref="x",
            ayref="y",
            showarrow=True,
            arrowhead=3,
            arrowwidth=1.0,
            arrowcolor="red",
        )
        # right → left
        fig.add_annotation(
            x=x_axis,
            y=top_band_arrow_y,
            ax=x_block_right,
            ay=top_band_arrow_y,
            xref="x",
            yref="y",
            axref="x",
            ayref="y",
            showarrow=True,
            arrowhead=3,
            arrowwidth=1.0,
            arrowcolor="red",
        )
        fig.add_annotation(
            x=(x_axis + x_block_right) / 2.0,
            y=top_band_label_y,
            text=f"α₂ f'c = {sigma_c:.0f} MPa",
            showarrow=False,
            xanchor="center",
            font=dict(size=11, color="red"),
        )

    # Depth arrow + label on the right (same right-margin placement as 3-panel)
    x_a = x_block_right + margin_right_stress
    # top→bottom arrow
    fig.add_annotation(
        x=x_a,
        y=block_bottom,
        ax=x_a,
        ay=block_top,
        xref="x",
        yref="y",
        axref="x",
        ayref="y",
        showarrow=True,
        arrowhead=2,
        arrowwidth=1.0,
        arrowcolor="red",
    )
    # bottom→top arrow (double-headed)
    fig.add_annotation(
        x=x_a,
        y=block_top,
        ax=x_a,
        ay=block_bottom,
        xref="x",
        yref="y",
        axref="x",
        ayref="y",
        showarrow=True,
        arrowhead=2,
        arrowwidth=1.0,
        arrowcolor="red",
    )
    fig.add_annotation(
        x=x_a + text_dx_stress,
        y=0.5 * (block_top + block_bottom),
        text=f"a = γ dₙ = {a_mm:.1f} mm",
        showarrow=False,
        xanchor="left",
        font=dict(size=11, color="red"),
    )

    # Extra features for variant "13"
    if variant == "13":
        if show_dn and dn_mm is not None and not math.isnan(dn_mm):
            fig.add_shape(type="line", x0=x_axis - 0.05, y0=dn_disp, x1=x_axis + STRESS_USABLE_W + 0.05, y1=dn_disp,
                          line=dict(color="blue", width=1, dash="dash"))
            fig.add_annotation(
                x=x_axis + STRESS_USABLE_W + 0.06, y=dn_disp,
                text=f"dₙ = {dn_mm:.1f} mm",
                showarrow=False,
                xanchor="left",
                font=dict(size=11, color="blue"),
            )

        # Tension arrow at depth d (steel to-scale)
        fig.add_annotation(
            x=x_T, y=d_disp, ax=x_axis, ay=d_disp,
            xref="x", yref="y", axref="x", ayref="y",
            showarrow=True, arrowhead=3, arrowwidth=1.5, arrowcolor="blue",
        )
        fig.add_annotation(
            x=x_T + 0.04, y=d_disp,
            text=f"T ({sigma_s:.0f} MPa)",
            showarrow=False, xanchor="left",
            font=dict(size=11, color="blue"),
        )

    # Variant "11": show T line near bottom (still to-scale)
    if variant == "11":
        y_T = D_disp * 0.80
        fig.add_annotation(
            x=x_T, y=y_T, ax=x_axis, ay=y_T,
            xref="x", yref="y", axref="x", ayref="y",
            showarrow=True, arrowhead=3, arrowwidth=1.5, arrowcolor="blue",
        )
        fig.add_annotation(
            x=x_T + 0.04, y=y_T,
            text=f"T ({sigma_s:.0f} MPa)",
            showarrow=False, xanchor="left",
            font=dict(size=11, color="blue"),
        )

    # Title (paper coords) + extra headroom so it never clips
    fig.add_annotation(
        x=0.5, y=1.10, xref="paper", yref="paper",
        text="Stress (MPa)", showarrow=False, font=dict(size=12)
    )

    # --- Ensure x-range includes right-side depth label + steel label ---
    x_right_needed = max(
        x_a + text_dx_stress + 0.08,   # depth label
        x_T + 0.15,                    # steel label
        x_block_right + 0.20           # comfort
    )

    fig.update_xaxes(range=[0.0, x_right_needed], visible=False)
    fig.update_yaxes(range=[D_disp * 1.05, -0.30 * D_disp], visible=False)
    fig.update_layout(margin=dict(l=0, r=10, t=55, b=20), height=540, showlegend=False)

    return fig


# ============================================================
#  SIMPLE ULS FORCE MODEL FIGURE (1.6)
# ============================================================
def _make_uls_force_model_figure(
    D_mm: float,
    d_mm: float,
    a_mm: float,
    C_N: float | None = None,
    T_N: float | None = None,
):
    """
    Simple C–T–z force model using Plotly (Step 1.6).

    Uses the same normalised depth as the ULS stress-block figures so
    the model is the same visual size and sits centrally in the calc box.
    """
    vals = [D_mm, d_mm, a_mm]
    if any(v is None or (isinstance(v, float) and math.isnan(v)) for v in vals):
        fig = go.Figure()
        fig.update_xaxes(visible=False)
        fig.update_yaxes(visible=False)
        fig.add_annotation(text="No data", x=0.5, y=0.5, xref="paper", yref="paper")
        return fig

    if D_mm is None or D_mm <= 0:
        D_mm = 600.0

    # Normalised depth to match stress-block figure (bigger: 1.5×)
    D_disp = 300.0
    scale = D_disp / float(D_mm)

    a_disp = a_mm * scale
    d_disp = d_mm * scale

    # Physical lever arm for label
    z_mm = d_mm - 0.5 * a_mm

    x_axis = 70.0
    ARROW_OFFSET = 60.0
    fig = go.Figure()

    # Vertical reference line
    fig.add_shape(
        type="line",
        x0=x_axis,
        y0=0.0,
        x1=x_axis,
        y1=D_disp,
        line=dict(color="black", width=2),
    )

    # Compression C at a/2
    y_C = 0.5 * a_disp
    x_C_tail = x_axis + ARROW_OFFSET
    x_C_head = x_axis
    fig.add_annotation(
        x=x_C_head,
        y=y_C,
        ax=x_C_tail,
        ay=y_C,
        xref="x",
        yref="y",
        axref="x",
        ayref="y",
        showarrow=True,
        arrowhead=3,
        arrowwidth=1.5,
        arrowcolor="red",
    )
    label_C = "C"
    if C_N is not None:
        label_C += f" = {C_N/1000.0:.1f} kN"
    fig.add_annotation(
        x=x_C_tail + 6.0,
        y=y_C,
        text=label_C,
        showarrow=False,
        xanchor="left",
        font=dict(size=11, color="red"),
    )

    # Tension T at depth d
    y_T = d_disp
    x_T_head = x_axis + ARROW_OFFSET
    x_T_tail = x_axis
    fig.add_annotation(
        x=x_T_head,
        y=y_T,
        ax=x_T_tail,
        ay=y_T,
        xref="x",
        yref="y",
        axref="x",
        ayref="y",
        showarrow=True,
        arrowhead=3,
        arrowwidth=1.5,
        arrowcolor="blue",
    )
    label_T = "T"
    if T_N is not None:
        label_T += f" = {T_N/1000.0:.1f} kN"
    fig.add_annotation(
        x=x_T_head + 6.0,
        y=y_T,
        text=label_T,
        showarrow=False,
        xanchor="left",
        font=dict(size=11, color="blue"),
    )

    # Lever arm z between C and T (double-headed)
    x_z = x_axis + ARROW_OFFSET / 2.0
    # T→C arrow
    fig.add_annotation(
        x=x_z,
        y=y_T,
        ax=x_z,
        ay=y_C,
        xref="x",
        yref="y",
        axref="x",
        ayref="y",
        showarrow=True,
        arrowhead=2,
        startarrowhead=2,
        arrowwidth=1.5,
    )
    # C→T arrow (double-headed)
    fig.add_annotation(
        x=x_z,
        y=y_C,
        ax=x_z,
        ay=y_T,
        xref="x",
        yref="y",
        axref="x",
        ayref="y",
        showarrow=True,
        arrowhead=2,
        startarrowhead=2,
        arrowwidth=1.5,
    )
    fig.add_annotation(
        x=x_z + 4.0,
        y=0.5 * (y_C + y_T),
        text=f"z = {z_mm:.1f} mm",
        showarrow=False,
        xanchor="left",
        font=dict(size=11),
    )

    # Layout
    fig.add_annotation(
        x=0.5,
        y=1.12,                 # higher so it clears the plot area
        xref="paper",
        yref="paper",
        text="Force model",
        showarrow=False,
        font=dict(size=12),
    )

    fig.update_xaxes(range=[0, 230], visible=False)
    fig.update_yaxes(range=[D_disp * 1.05, -0.20 * D_disp], visible=False)
    fig.update_layout(
        margin=dict(l=0, r=0, t=60, b=20),   # more top margin so it doesn't clip
        height=540,          # matches the stress-block figures
        showlegend=False,
    )

    return fig


# ============================================================
#  NEW: SLS STRESS-BLOCK / SECTION FIGURE FOR 3.3
# ============================================================
def _make_sls_stress_block_figure(
    D_mm: float,
    d_mm: float,
    dn_mm: float,
    include_comp: bool = False,
    d_comp_mm: float | None = None,
):
    """
    SLS stress-block figure for Step 3.2 (cracked section), rebuilt to MATCH the
    main 3-panel Stress diagram conventions:

    - Same axis layout (x_axis=0.1, usable_width=0.7)
    - Same top-band arrow + label positions (-0.06D, -0.12D)
    - Same right-side depth arrow spacing concept
    - Triangular compression block to d_n
    - Multiple tension layers shown automatically (T1, T2, ...) with stress in MPa

    Uses session_state:
      bending_sls_dn, bending_sls_eps_top, bending_sls_eps_bot, bending_sls_y_bot
    and section_layout.compute_section_layout() for bar layer depths.
    """

    # -------------------------
    # Pull layout (bar layers)
    # -------------------------
    try:
        layout = compute_section_layout()
        D = float(layout.get("D", D_mm))
        reo_layout = layout.get("reo_layout", None)
    except Exception:
        D = float(D_mm if D_mm else 600.0)
        reo_layout = None

    if not D or D <= 0:
        D = 600.0

    # -------------------------
    # Pull SLS state (preferred)
    # -------------------------
    try:
        dn_sls = st.session_state.get("bending_sls_dn", None)
        eps_top_sls = st.session_state.get("bending_sls_eps_top", None)  # solver: compression negative
        # (eps_bot_sls and y_bot_sls exist but we don't need them if we have dn + eps_top)
    except Exception:
        dn_sls, eps_top_sls = None, None

    # Neutral axis depth
    try:
        c = float(dn_sls) if dn_sls is not None else float(dn_mm)
    except Exception:
        c = float(dn_mm)

    c = max(1e-6, min(float(D), float(c)))

    # Material props (elastic SLS)
    try:
        Ec = float(get_param("Ec", 30000.0))  # MPa
        Es = float(get_param("Es", 200000.0))  # MPa
    except Exception:
        Ec, Es = 30000.0, 200000.0

    # Top concrete stress at SLS (elastic)
    # solver uses compression negative -> use magnitude
    try:
        eps_top = float(eps_top_sls) if eps_top_sls is not None else -0.0002
    except Exception:
        eps_top = -0.0002

    sigma_c_top = Ec * abs(eps_top)  # MPa

    # -------------------------
    # Helper: strain at depth y
    # -------------------------
    # linear strain: ε(y) = ε_top * (1 - y/c), with ε(c)=0
    def eps_at_y(y: float) -> float:
        return eps_top * (1.0 - float(y) / float(c))

    # -------------------------
    # Collect tension layers
    # -------------------------
    tension_layers = []  # list of (y, label, sigma_MPa)

    if reo_layout and isinstance(reo_layout, dict):
        # bottom layers are stored as a list of layer dicts, each with "y"
        ys = []
        bottom_layers = _get_layers(reo_layout, "bottom")

        for layer in bottom_layers:
            try:
                ys.append(float(layer["y"]))
            except Exception:
                pass

        # tension layers = below NA
        ys_t = [y for y in ys if y > c + 1e-6]
        # order: deepest first -> T1 at bottom like your screenshot
        ys_t.sort(reverse=True)

        for i, y in enumerate(ys_t, start=1):
            sig = Es * eps_at_y(y)  # MPa (tension should be +)
            tension_layers.append((y, f"T{i}", float(sig)))

    else:
        # fallback: just one layer at d_mm (old behaviour)
        try:
            y = float(d_mm)
        except Exception:
            y = float(D * 0.9)
        sig = Es * eps_at_y(y)
        tension_layers.append((y, "T1", float(sig)))

    # optional compression steel arrow (if requested)
    comp_layer = None
    if include_comp and d_comp_mm is not None:
        try:
            ycs = float(d_comp_mm)
            sigcs = Es * eps_at_y(ycs)  # likely compression negative
            comp_layer = (ycs, "Cₛ", float(sigcs))
        except Exception:
            comp_layer = None

    # ------------------------------------------------------------
    # Match the SAME coordinate system + scaling as the 3-panel stress diagram
    # (so Step-by-step figures look identical)
    # ------------------------------------------------------------
    base_span = max(D_mm, d_mm, dn_mm, d_comp_mm or 0.0)
    D_ref = base_span * 1.05

    # Match ULS/3-panel stress layout geometry (not the old hand-sketch one)
    x_axis = 70.0
    block_left = x_axis
    block_width = 40.0 * 1.75  # same readability boost used elsewhere

    # Keep room above for the title/labels so nothing clips
    Y_TOP_PAD = 0.20 * D_ref
    Y_BOT_PAD = 0.20 * D_ref

    # -------------------------
    # Scaling (match main stress panel behaviour)
    # -------------------------
    # Steel stresses (magnitudes)
    steel_max = 0.0
    for _, _, sig in tension_layers:
        steel_max = max(steel_max, abs(sig))
    if comp_layer is not None:
        steel_max = max(steel_max, abs(comp_layer[2]))

    stress_max = max(sigma_c_top, steel_max, 1.0)

    # Stress-to-x mapping (absolute coordinates)
    usable_width = 100.0  # absolute width for stress arrows
    def stress_to_x(sig_abs: float) -> float:
        return x_axis + (float(sig_abs) / float(stress_max)) * usable_width

    # Use fixed block width (matching ULS figure style)
    x_block_right = x_axis + block_width

    # -------------------------
    # Build figure
    # -------------------------
    fig = go.Figure()

    # vertical axis
    fig.add_shape(
        type="line",
        x0=x_axis,
        y0=0,
        x1=x_axis,
        y1=D_ref,
        line=dict(color="black", width=2),
    )

    # neutral axis (dashed)
    fig.add_shape(
        type="line",
        x0=x_axis - 5.0,
        y0=c,
        x1=x_axis + usable_width + 10.0,
        y1=c,
        line=dict(color="black", width=1, dash="dash"),
    )

    # triangular compression block (TOP -> d_n)
    tri_x = [x_axis, x_axis, x_block_right, x_axis]
    tri_y = [c, 0.0, 0.0, c]
    fig.add_trace(
        go.Scatter(
            x=tri_x,
            y=tri_y,
            mode="lines",
            fill="toself",
            fillcolor="rgba(255,200,200,0.20)",
            line=dict(color="red", width=2),
            hoverinfo="skip",
            showlegend=False,
        )
    )

    # internal compression arrows inside triangle
    if c > 0:
        for frac in [0.25, 0.5, 0.75]:
            y_mid = frac * c
            rel = max(0.0, min(1.0, y_mid / c))
            x_max = x_axis + (1.0 - rel) * (x_block_right - x_axis)
            x_tail = x_axis + 0.20 * (x_max - x_axis)
            x_head = x_axis + 0.75 * (x_max - x_axis)
            fig.add_annotation(
                x=x_tail,
                y=y_mid,
                ax=x_head,
                ay=y_mid,
                xref="x",
                yref="y",
                axref="x",
                ayref="y",
                text="",
                showarrow=True,
                arrowhead=3,
                arrowsize=1.0,
                arrowwidth=1.0,
                arrowcolor="red",
            )

    # top width arrow + label (MATCH main 3-panel placement)
    top_band_arrow_y = -0.06 * D_ref
    top_band_label_y = -0.12 * D_ref

    fig.add_annotation(
        x=x_block_right,
        y=top_band_arrow_y,
        ax=x_axis,
        ay=top_band_arrow_y,
        xref="x",
        yref="y",
        axref="x",
        ayref="y",
        text="",
        showarrow=True,
        arrowhead=3,
        arrowwidth=1.0,
        arrowcolor="red",
    )
    fig.add_annotation(
        x=x_axis,
        y=top_band_arrow_y,
        ax=x_block_right,
        ay=top_band_arrow_y,
        xref="x",
        yref="y",
        axref="x",
        ayref="y",
        text="",
        showarrow=True,
        arrowhead=3,
        arrowwidth=1.0,
        arrowcolor="red",
    )

    fig.add_annotation(
        x=(x_axis + x_block_right) / 2.0,
        y=top_band_label_y,
        text=f"E_c ε_c = {sigma_c_top:.0f} MPa",
        showarrow=False,
        font=dict(size=11, color="red"),
        xanchor="center",
    )

    # right-side depth arrow + label (d_n)
    x_dn = x_block_right + 10.0
    fig.add_annotation(
        x=x_dn,
        y=c,
        ax=x_dn,
        ay=0.0,
        xref="x",
        yref="y",
        axref="x",
        ayref="y",
        text="",
        showarrow=True,
        arrowhead=2,
        arrowwidth=1.0,
        arrowcolor="red",
    )
    fig.add_annotation(
        x=x_dn,
        y=0.0,
        ax=x_dn,
        ay=c,
        xref="x",
        yref="y",
        axref="x",
        ayref="y",
        text="",
        showarrow=True,
        arrowhead=2,
        arrowwidth=1.0,
        arrowcolor="red",
    )
    fig.add_annotation(
        x=x_dn + 4.0,
        y=0.5 * c,
        text=f"dₙ = {c:.0f} mm",
        showarrow=False,
        font=dict(size=12, color="red"),
        xanchor="left",
    )

    # steel tension arrows (multiple layers)
    for (y, lab, sig) in tension_layers:
        sig_t = max(0.0, float(sig))  # tension only for arrow length
        x_t = stress_to_x(abs(sig_t))

        fig.add_annotation(
            x=x_t,
            y=y,
            ax=x_axis,
            ay=y,
            xref="x",
            yref="y",
            axref="x",
            ayref="y",
            text="",
            showarrow=True,
            arrowhead=3,
            arrowwidth=2.0,
            arrowcolor="blue",
        )
        fig.add_annotation(
            x=x_t + 4.0,
            y=y,
            text=f"{lab} ({abs(sig):.0f} MPa)",
            showarrow=False,
            font=dict(size=11, color="blue"),
            xanchor="left",
        )

    # optional compression steel
    if comp_layer is not None:
        ycs, lab, sigcs = comp_layer
        # show compression arrow to the LEFT if negative
        x_mag = stress_to_x(abs(sigcs))
        if sigcs < 0:
            # arrow left: from x_axis to (x_axis - len)
            x_left = max(2.0, x_axis - (x_mag - x_axis))
            fig.add_annotation(
                x=x_left,
                y=ycs,
                ax=x_axis,
                ay=ycs,
                xref="x",
                yref="y",
                axref="x",
                ayref="y",
                text="",
                showarrow=True,
                arrowhead=3,
                arrowwidth=2.0,
                arrowcolor="red",
            )
            fig.add_annotation(
                x=x_left - 2.0,
                y=ycs,
                text=f"{lab} ({abs(sigcs):.0f} MPa)",
                showarrow=False,
                font=dict(size=11, color="red"),
                xanchor="right",
            )
        else:
            fig.add_annotation(
                x=x_mag,
                y=ycs,
                ax=x_axis,
                ay=ycs,
                xref="x",
                yref="y",
                axref="x",
                ayref="y",
                text="",
                showarrow=True,
                arrowhead=3,
                arrowwidth=2.0,
                arrowcolor="red",
            )
            fig.add_annotation(
                x=x_mag + 4.0,
                y=ycs,
                text=f"{lab} ({abs(sigcs):.0f} MPa)",
                showarrow=False,
                font=dict(size=11, color="red"),
                xanchor="left",
            )

    # Title (prevents the "Stress (MPa)" heading being clipped)
    fig.add_annotation(
        x=0.5,
        y=1.08,
        xref="paper",
        yref="paper",
        text="Stress (MPa)",
        showarrow=False,
        font=dict(size=12),
    )

    fig.update_xaxes(range=[0, 230], visible=False)
    fig.update_yaxes(range=[D_ref + Y_TOP_PAD, -Y_BOT_PAD], visible=False)

    fig.update_layout(
        margin=dict(l=0, r=0, t=45, b=20),
        height=540,
        showlegend=False,
    )

    return fig