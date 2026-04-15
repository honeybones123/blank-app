# shear_diagrams.py
# ==========================================
# Shear diagram generation functions
# ==========================================

import math
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, FancyArrowPatch, Circle
from mpl_toolkits.mplot3d import Axes3D
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
import plotly.graph_objects as go
from plotly.subplots import make_subplots

import strain_display
from bending_layer_semantics import resolve_bending_layer_geometry
from section_layout import compute_shear_reo_layout_pure
from section_props.plotly_section import make_sectionA_figure
from section_props.plot import plot_shape, apply_section_axes


def _arrow(ax, p0, p1, lw=2.0, ms=14, color="k"):
    ax.add_patch(
        FancyArrowPatch(
            p0, p1,
            arrowstyle="-|>",
            mutation_scale=ms,
            linewidth=lw,
            color=color,
        )
    )


def plot_shear_torsion_section_2d(
    *,
    shape_name: str,
    dims: dict,
    reo: dict,
    mode: str = "V+T",  # "V", "T", "V+T"
    show_labels: bool = True,
    tension_face: str | None = None,
    compact_stress_labels: bool = False,
    show_schematic_footer: bool = True,
):
    # ---------------------------------------------------------------------
    # Base figure: use the SAME section engine as Inputs/Bending
    # ---------------------------------------------------------------------
    if shape_name.startswith("Rectangle"):
        rect_reo = {
            "cover_top": float(reo.get("cover_top", 40.0)),
            "cover_bot": float(reo.get("cover_bot", 40.0)),
            "cover_side": float(reo.get("cover_side", 40.0)),
            "n_top": int(reo.get("nb_top", 0)),
            "db_top": float(reo.get("db_top", 0.0)),
            "n_bot": int(reo.get("nb_bot", 0)),
            "db_bot": float(reo.get("db_bot", 0.0)),
            "s_min": float(reo.get("min_clear_spacing", 20.0)),
            "rowgap_top": float(reo.get("rowgap_top", 60.0)),
            "rowgap_bot": float(reo.get("rowgap_bot", 60.0)),
            "lig_d": float(reo.get("lig_d", 0.0)),
            "lig_legs": int(reo.get("lig_legs", 0)),
        }
        fig = plot_shape(shape_name, dims, reo=rect_reo)
    else:
        fig = make_sectionA_figure(
            shape_name=shape_name,
            dims=dims,
            reo=reo,
            show_shear=True,
            tension_face=tension_face,
        )

    # Force consistent layout (schematic style).
    # Use title text="" (not None): empty {} in figure JSON makes Streamlit show the word "undefined".
    fig.update_layout(
        title=dict(text=""),
        showlegend=False,
        margin=dict(l=5, r=5, t=20, b=5),
    )

    # ---------------------------------------------------------------------
    # Determine section bounds for arrow positioning
    # ---------------------------------------------------------------------
    D = float(dims.get("D", 0.0) or 0.0)

    if shape_name.startswith("Rect"):
        W = float(dims.get("b", 0.0) or 0.0)
    else:
        W = float(dims.get("bf", dims.get("b", 0.0)) or 0.0)

    W = max(W, 1.0)
    D = max(D, 1.0)

    x_pad = 0.12 * W
    y_pad = 0.12 * D

    # helpers
    def _arrow(x0, y0, x1, y1, color="black", width=2):
        fig.add_annotation(
            x=x1,
            y=y1,
            ax=x0,
            ay=y0,
            xref="x",
            yref="y",
            axref="x",
            ayref="y",
            showarrow=True,
            arrowhead=2,
            arrowsize=1.0,
            arrowwidth=width,
            arrowcolor=color,
            text="",
        )

    inset = max(min(0.12 * min(W, D), 0.25 * min(W, D)), 12.0)
    xL = inset
    xR = W - inset
    yT = inset
    yB = D - inset

    # -------------------------
    # SHEAR τv (RED) – vertical arrows inside
    # -------------------------
    if "V" in mode:
        for y in [0.30 * D, 0.55 * D, 0.80 * D]:
            _arrow(xL, y, xL, y + 0.15 * D, color="red", width=2)
            _arrow(xR, y, xR, y + 0.15 * D, color="red", width=2)

        if show_labels and not compact_stress_labels:
            fig.add_annotation(
                x=W / 2,
                y=-0.06 * D,
                text="tau_v (shear)",
                showarrow=False,
                font=dict(size=11, color="red"),
            )

    # -------------------------
    # TORSION τT (BLUE) — clockwise shear flow:
    #   RIGHT face = DOWN (adds with shear-down)
    #   LEFT  face = UP   (opposes shear-down)
    # -------------------------
    if "T" in mode:
        # Top edge: →
        for x in [0.25 * W, 0.50 * W, 0.75 * W]:
            _arrow(x - 0.10 * W, yT, x + 0.10 * W, yT, color="rgb(31,119,180)", width=2)

        # Right edge: ↓ (ADDS)
        for y in [0.25 * D, 0.50 * D, 0.75 * D]:
            _arrow(xR, y, xR, y + 0.10 * D, color="rgb(31,119,180)", width=2)

        # Bottom edge: ←
        for x in [0.25 * W, 0.50 * W, 0.75 * W]:
            _arrow(x + 0.10 * W, yB, x - 0.10 * W, yB, color="rgb(31,119,180)", width=2)

        # Left edge: ↑ (OPPOSES)
        for y in [0.25 * D, 0.50 * D, 0.75 * D]:
            _arrow(xL, y + 0.10 * D, xL, y - 0.10 * D, color="rgb(31,119,180)", width=2)

        if show_labels and not compact_stress_labels:
            fig.add_annotation(
                x=W / 2,
                y=-0.12 * D,
                text="tau_T (torsion shear flow)",
                showarrow=False,
                font=dict(size=9, color="rgb(31,119,180)"),
            )
            fig.add_annotation(
                x=-0.08 * W,
                y=D / 2,
                text="opposes",
                showarrow=False,
                textangle=90,
                font=dict(size=8, color="rgb(51,51,51)"),
            )
            fig.add_annotation(
                x=W + 0.08 * W,
                y=D / 2,
                text="adds",
                showarrow=False,
                textangle=90,
                font=dict(size=8, color="rgb(51,51,51)"),
            )

    if show_labels and show_schematic_footer:
        fig.add_annotation(
            x=W / 2,
            y=D + 0.12 * D,
            text="Section + reinforcement (schematic)",
            showarrow=False,
            font=dict(size=9, color="rgb(51,51,51)"),
        )

    # expand axes for labels/arrows (shared helper for consistency)
    apply_section_axes(fig, W=W, D=D)
    fig.update_xaxes(visible=False)
    fig.update_yaxes(visible=False)

    return fig


# ------------------------------------------------------------
#  Plotly Section Diagrams
# ------------------------------------------------------------

def plot_shear_step3_section_params_plotly(
    b_mm: float,
    D_mm: float,
    bv_mm: float,
    dv_mm: float,
    Asv_mm2: float | None = None,
    s_lig_mm: float | None = None,
    reo_shapes: list[dict] | None = None,
    lig_d: float | None = None,
    lig_legs: int | None = None,
    cover_bot: float | None = None,
    cover_top: float | None = None,
    cover_side: float | None = None,
    height: int = 850,  # 2.5x bigger (340 * 2.5 = 850)
    label_pad: int = 14,
    # NEW (optional): shape-aware mode
    shape_name: str | None = None,
    dims: dict | None = None,
    reo: dict | None = None,
):
    """
    Plotly section diagram styled like Bending page section panel,
    but annotated for Shear Step 3: bv and dv.
    """
    b = float(b_mm)
    D = float(D_mm)
    bv = float(bv_mm)
    dv = float(dv_mm)
    shape_aware = bool(shape_name and dims and reo)

    # ---------------------------------------
    # Consistent plot frame so shapes scale similarly
    # Use flange width for T/I, width b for rectangles
    # ---------------------------------------
    if shape_aware:
        if str(shape_name).lower().startswith("rect"):
            W = float(dims.get("b", b))
        else:
            W = float(dims.get("bf", b))
    else:
        W = float(b)

    # Use real plotted width if shape-aware
    if shape_name and dims and reo:
        if str(shape_name).lower().startswith("rect"):
            b = float(dims.get("b", b))
        else:
            b = float(dims.get("bf", b))

    # Basic guard
    bv = max(0.0, min(bv, b))
    dv = max(0.0, min(dv, D))

    # Center bv within b
    xL = (b - bv) / 2.0
    xR = xL + bv

    # dv line: measured from top face downward
    y_top = D
    y_dv = D - dv  # plot y origin at 0 bottom; so top is D

    # ------------------------------------------------------------
    # Base figure: if shape_name/dims/reo provided, draw real shape
    # ------------------------------------------------------------
    if shape_aware:
        if str(shape_name).lower().startswith("rect"):
            rect_reo = {
                "cover_top": float(reo.get("cover_top", 40.0)),
                "cover_bot": float(reo.get("cover_bot", 40.0)),
                "cover_side": float(reo.get("cover_side", 40.0)),
                "n_top": int(reo.get("nb_top", 0)),
                "db_top": float(reo.get("db_top", 0.0)),
                "n_bot": int(reo.get("nb_bot", 0)),
                "db_bot": float(reo.get("db_bot", 0.0)),
                "s_min": float(reo.get("min_clear_spacing", 20.0)),
                "rowgap_top": float(reo.get("rowgap_top", 60.0)),
                "rowgap_bot": float(reo.get("rowgap_bot", 60.0)),
                "lig_d": float(reo.get("lig_d", 0.0)),
                "lig_legs": int(reo.get("lig_legs", 0)),
            }
            fig = plot_shape(str(shape_name), dims, reo=rect_reo)
        else:
            fig = make_sectionA_figure(
                shape_name=shape_name,
                dims=dims,
                reo=reo,
                show_shear=True,
            )
        # Ensure section fill is visible (in case the base figure uses no fill)
        for s in fig.layout.shapes or []:
            if getattr(s, "type", None) == "path" and (not getattr(s, "fillcolor", None) or s.fillcolor == "rgba(0,0,0,0)"):
                s.fillcolor = "rgba(220,220,220,0.35)"
    else:
        fig = go.Figure()
        # fallback (old behaviour): rectangle only
        fig.add_shape(
            type="rect",
            x0=0, y0=0, x1=b, y1=D,
            line=dict(color="black", width=4),
            fillcolor="rgba(245,245,245,1.0)",
        )

    # ------------------------------------------------------------
    # Reo overlay (same look as bending: bottom=red, top=blue)
    # reo_shapes items: {"x":..,"y":..,"r":..,"fill":"rgba(...)","line":"rgba(...)"}
    # ------------------------------------------------------------
    if (not shape_aware) and reo_shapes:
        for s in reo_shapes:
            cx = float(s["x"])
            cy = float(s["y"])
            r  = float(s["r"])
            fill = s.get("fill", "rgba(80,80,80,0.90)")
            line = s.get("line", "rgba(30,30,30,1.00)")

            fig.add_shape(
                type="circle",
                x0=cx - r, y0=cy - r,
                x1=cx + r, y1=cy + r,
                line=dict(width=1.2, color=line),
                fillcolor=fill,
                layer="above",
            )

    # --- bv highlight (two vertical lines + light fill) ---
    if not shape_aware:
        fig.add_shape(
            type="rect",
            x0=xL, y0=0, x1=xR, y1=D,
            line=dict(width=0),
            fillcolor="rgba(0,0,0,0.04)",
            layer="below",
        )

    # --- dv marker line (horizontal) ---
    fig.add_shape(type="line", x0=0, y0=y_dv, x1=b, y1=y_dv, line=dict(width=2))

    # ------------------------------------------------------------
    # Shear ligs (stirrups) - same as input page 2D model
    # ------------------------------------------------------------
    if (not shape_aware) and lig_d and lig_legs and cover_bot is not None and cover_top is not None and cover_side is not None:
        from section_layout import compute_shear_reo_layout_pure
        reo_points = []
        for s in reo_shapes or []:
            try:
                r = float(s.get("r", 0.0) or 0.0)
                x = float(s.get("x", 0.0) or 0.0)
                y = float(s.get("y", 0.0) or 0.0)
            except Exception:
                continue
            if r <= 0:
                continue
            reo_points.append({"x": x, "y": y, "db": 2.0 * r})
        
        shear_layout = compute_shear_reo_layout_pure(
            b=b, D=D,
            cover_bot=float(cover_bot), cover_top=float(cover_top), cover_side=float(cover_side),
            lig_d=float(lig_d), lig_legs=int(lig_legs),
            reo_points=reo_points,
        )
        
        # Draw stirrup legs in black
        for stirrup in shear_layout.get("stirrups", []):
            for leg in stirrup.get("legs", []):
                fig.add_shape(
                    type="line",
                    x0=float(leg["x1"]), y0=float(leg["y1"]),
                    x1=float(leg["x2"]), y1=float(leg["y2"]),
                    line=dict(width=1.2, color="rgba(0,0,0,0.85)"),
                    layer="above",
                )

    # --- bv dimension annotation (top) ---
    BV_TEXT_Y = D + 0.12 * D
    BV_ARROW_Y = D + 0.04 * D

    def _add_dim_label(x, y, text, angle_deg=0, xanchor="center", yanchor="middle"):
        fig.add_annotation(
            x=x,
            y=y,
            text=text,
            showarrow=False,
            textangle=angle_deg,
            xanchor=xanchor,
            yanchor=yanchor,
            font=dict(size=18, color="rgb(120,120,140)"),
        )

    _add_dim_label(
        x=(xL + xR) / 2.0,
        y=BV_TEXT_Y,
        text=f"b<sub>v</sub> = {bv:.1f} mm",
        angle_deg=0,
    )
    # --- bv arrows: point to the two dotted bv boundary lines ---
    fig.add_annotation(
        x=xL, y=BV_ARROW_Y, text="",
        showarrow=True, arrowhead=2,
        axref="x", ayref="y",
        ax=xL + 0.20 * bv, ay=BV_ARROW_Y,   # arrow tail to the right, head at xL
        standoff=label_pad,
    )
    fig.add_annotation(
        x=xR, y=BV_ARROW_Y, text="",
        showarrow=True, arrowhead=2,
        axref="x", ayref="y",
        ax=xR - 0.20 * bv, ay=BV_ARROW_Y,   # arrow tail to the left, head at xR
        standoff=label_pad,
    )

    # --- dv dimension annotation (left side) ---
    DV_TEXT_X = -0.18 * b
    DV_ARROW_X = -0.06 * b
    DV_TEXT_Y = (y_top + y_dv) / 2.0

    _add_dim_label(
        x=DV_TEXT_X,
        y=DV_TEXT_Y,
        text=f"d<sub>v</sub> = {dv:.1f} mm",
        angle_deg=-90,
        xanchor="center",
        yanchor="middle",
    )
    # --- dv arrows: point to top face and dv marker line (left side) ---
    fig.add_annotation(
        x=DV_ARROW_X, y=y_top, text="",
        showarrow=True, arrowhead=2,
        axref="x", ayref="y",
        ax=DV_ARROW_X, ay=y_top - 0.25 * dv,   # tail below, head at top
        standoff=label_pad,
    )
    fig.add_annotation(
        x=DV_ARROW_X, y=y_dv, text="",
        showarrow=True, arrowhead=2,
        axref="x", ayref="y",
        ax=DV_ARROW_X, ay=y_dv + 0.25 * dv,    # tail above, head at dv line
        standoff=label_pad,
    )

    # Optional: show Asv only (s_lig removed per user request)
    if Asv_mm2 is not None:
        fig.add_annotation(
            x=0.02 * b, y=0.02 * D,
            xanchor="left", yanchor="bottom",
            text=f"A<sub>sv</sub> = {float(Asv_mm2):.1f} mm²",
            showarrow=False,
            font=dict(size=11),
            bgcolor="rgba(255,255,255,0.7)",
            xshift=label_pad,  # More spacing from edge
            yshift=label_pad,  # More spacing from bottom
        )

    # --- Layout: match Bending page "section panel" feel ---
    # Bigger section + less dead space, model shifted further right
    apply_section_axes(fig, W=W, D=D)
    fig.update_xaxes(visible=False)
    fig.update_yaxes(visible=False)
    # Ensure consistent section coordinate system: y=0 at TOP, y increases downward
    fig.update_yaxes(autorange=False)

    fig.update_layout(
        margin=dict(l=10, r=10, t=20, b=10),
        height=height,
        paper_bgcolor="white",
        plot_bgcolor="white",
        showlegend=False,
    )

    return fig


# Check 4 longitudinal diagram: fixed symmetric x-range so the internal beam face (x = 0) is
# identical in stress–strain and force-resolution modes (same scale, margins, extents).
MCFT_CHECK4_FACE_X_HALF = 1.15
# Extra y-axis extent (fraction of depth) so the shared beam-face line is not clipped at plot edges.
MCFT_CHECK4_Y_PAD = 0.045
# Pull display x toward the beam face (x=0) for the MCFT point/tick/labels only — not a calc change.
MCFT_CHECK4_EPSX_VISUAL_INWARD = 0.40
# Small compression cue at top (display x < 0); tension at bottom (x > 0). Keeps a shallow C→T line through x_vis.
MCFT_CHECK4_SCHEMATIC_TREND_COMP_TOP = 0.10
# Short horizontal stub at top fibre: strain magnitude as fraction of emax (display x, compression left).
MCFT_CHECK4_TOP_COMP_CUE_FRAC = 0.22
# Layout: shift Check 4 diagram down slightly (strain + force modes); extra band for force column headings.
MCFT_CHECK4_TOP_MARGIN_SHIFT_PX = 44
MCFT_CHECK4_TOP_MARGIN_FORCE_HEADINGS_PX = 92
# Force-resolution only: extra normalized depth above y=0 so the sketch sits lower; headings stay in top margin.
MCFT_CHECK4_FORCE_DIAGRAM_AXIS_TOP_GAP = 0.11


def _mcft_schematic_strain_trend_endpoints(x_vis: float) -> tuple[float, float]:
    """
    Indicative strain trend (display x): conventional sketch — compression left of the beam face at top,
    tension right at bottom, single crossing of x=0. Straight line through (x_vis, y_mid) at y=0.5
    so (x_top + x_bot) / 2 = x_vis. Teaching only — not from analysis.
    """
    m = MCFT_CHECK4_SCHEMATIC_TREND_COMP_TOP
    if x_vis < 0.0:
        m = max(m, -2.0 * x_vis + 0.05)
    x_top = -m
    x_bot = 2.0 * x_vis + m
    return x_top, x_bot


def _compute_mcft_strain_symmetric_half_range_eps_x(eps_x_mcft: float) -> float:
    """Half-width in strain units for symmetric framing (MCFT εx only; no flexural top/bot labels)."""
    emax = max(abs(eps_x_mcft), 1e-6)
    label_offset = 0.05 * emax
    left_extents: list[float] = []
    right_extents: list[float] = []
    if eps_x_mcft < 0.0:
        left_extents.append(abs(eps_x_mcft) + label_offset)
    elif eps_x_mcft > 0.0:
        right_extents.append(eps_x_mcft + label_offset)
    if eps_x_mcft < 0.0:
        label_x_mid = eps_x_mcft - label_offset
    else:
        label_x_mid = eps_x_mcft + label_offset
    callout_x = label_x_mid + (0.12 * emax if eps_x_mcft >= 0.0 else -0.12 * emax)
    if callout_x < 0.0:
        left_extents.append(abs(callout_x))
    else:
        right_extents.append(callout_x)
    L = max(left_extents) if left_extents else 0.0
    R = max(right_extents) if right_extents else 0.0
    half_core = max(L, R)
    if half_core < 1e-6:
        half_core = 1e-4
    span_sym = 2.0 * half_core
    pad = 0.20 * span_sym
    half_range = half_core + pad
    if half_range < 1e-4:
        half_range = 1e-4
    return half_range


def _add_mcft_shared_beam_face(fig: go.Figure, y_top: float, y_bot: float) -> None:
    """Single shared internal web face at x = 0 (same geometry in both Check 4 modes)."""
    fig.add_shape(
        type="line",
        x0=0,
        x1=0,
        y0=y_top,
        y1=y_bot,
        line=dict(width=4, color="black"),
        layer="below",
    )


def _apply_mcft_check4_layout(
    fig: go.Figure,
    height: int,
    y_top: float,
    y_bot: float,
    *,
    extra_top_margin: int = 0,
    extend_y_top_norm: float = 0.0,
) -> None:
    """Identical frame for strain and force-resolution views (face registers at x = 0).

    extend_y_top_norm: extra headroom in normalized depth above y_top (force mode only), lowers sketch in the axes.
    """
    pad = MCFT_CHECK4_Y_PAD
    # Widen plot bounds in y only; beam face stays y_top..y_bot in data space (unchanged geometry).
    _y_top_axis = y_top - pad - max(0.0, float(extend_y_top_norm))
    y_axis_range = [y_bot + pad, _y_top_axis]
    fig.update_layout(
        width=640,
        height=int(height),
        margin=dict(t=16 + int(extra_top_margin), b=40, l=60, r=20),
        xaxis=dict(
            visible=False,
            range=[-MCFT_CHECK4_FACE_X_HALF, MCFT_CHECK4_FACE_X_HALF],
            fixedrange=True,
            zeroline=False,
            showgrid=False,
        ),
        yaxis=dict(
            visible=False,
            showticklabels=False,
            showgrid=False,
            autorange=False,
            range=y_axis_range,
            zeroline=False,
        ),
        paper_bgcolor="white",
        plot_bgcolor="white",
        showlegend=False,
    )


def _mcft_bending_zone_mid_depths(
    eps_top_uls: float,
    eps_bot_uls: float,
    *,
    y_top: float = 0.0,
    y_bot: float = 1.0,
) -> tuple[float, float]:
    """
    Mid-depth of compression and tension zones from ULS linear strains (same NA as strain diagram).
    y is normalized depth: 0 = top, 1 = bottom (bending page convention).
    """
    eps_diff = eps_bot_uls - eps_top_uls
    if abs(eps_diff) < 1e-9:
        return 0.5 * (y_top + y_bot), 0.5 * (y_top + y_bot)

    y_na = y_top + (y_bot - y_top) * (0.0 - eps_top_uls) / eps_diff
    y_na = max(y_top, min(y_bot, y_na))

    if eps_top_uls < 0.0 and eps_bot_uls > 0.0:
        # Sagging: compression above NA, tension below
        y_mid_comp = 0.5 * (y_top + y_na)
        y_mid_ten = 0.5 * (y_na + y_bot)
        return y_mid_comp, y_mid_ten
    if eps_top_uls > 0.0 and eps_bot_uls < 0.0:
        # Hogging: tension above NA, compression below
        y_mid_ten = 0.5 * (y_top + y_na)
        y_mid_comp = 0.5 * (y_na + y_bot)
        return y_mid_comp, y_mid_ten
    # Same sign (no NA in section): schematic placement
    if eps_top_uls < 0.0:
        return 0.5 * (y_top + y_bot), 0.85 * y_bot + 0.15 * y_top
    return 0.15 * y_bot + 0.85 * y_top, 0.5 * (y_top + y_bot)


def _mcft_force_resultant_depths_norm(
    *,
    D_mm: float,
    c_mm: float,
    gamma: float,
    tension_steel_y_from_top_mm: float,
    moment_sign: str,
    y_top: float = 0.0,
    y_bot: float = 1.0,
) -> tuple[float, float] | None:
    """
    Normalized depths (0 = top, 1 = bottom) for illustrative C and T on the Check 4 force diagram.

    C: centroid of the equivalent rectangular compression block (mid-depth of the block), using
    block depth a = gamma * c with c measured from the compression face (same convention as
    bending_core._stress_strain_state ULS).

    T: depth to the tensile steel centroid from the top fibre (d_plot from _stress_strain_state).

    Returns None if geometry is unusable; caller should fall back to _mcft_bending_zone_mid_depths.
    """
    D = float(D_mm)
    if D <= 1e-6:
        return None
    c = max(0.0, float(c_mm))
    g = float(gamma)
    if g <= 1e-9:
        return None
    a = min(g * c, D - 1e-6)
    if a <= 1e-6:
        return None

    sign = str(moment_sign or "positive").strip().lower()
    hogging = sign in ("negative", "hogging")

    if not hogging:
        y_c = 0.5 * a / D
    else:
        y_c = 1.0 - 0.5 * a / D

    y_t = float(tension_steel_y_from_top_mm) / D
    y_t = max(y_top, min(y_bot, y_t))

    margin = 0.018
    y_c = max(y_top + margin, min(y_bot - margin, y_c))
    y_t = max(y_top + margin, min(y_bot - margin, y_t))
    return y_c, y_t


def _add_mcft_force_resolution_overlay(
    fig: go.Figure,
    *,
    y_mid_compression: float,
    y_mid_tension: float,
    theta_deg: float | None = None,
) -> None:
    """
    Illustrative internal forces on the shared ε=0 beam face (Check 4).
    Mixed coordinates: schematic x in [-1, 1] for C/T; legacy 0–10 sketch mapping for other cues.
    Depth y in [0, 1] (0 = top).

    Diagonal compression strut plus flange C/T resultants; N*, V*, M* cues on the left.
    Adds paper-space column headings (section actions vs internal resolution); does not move force geometry.
    """
    ox = lambda v: (float(v) - 5.0) / 5.0
    oy = lambda v: 1.0 - (float(v) / 10.0)
    y_to_legacy_y = lambda y_norm: 10.0 * (1.0 - float(y_norm))

    lo_y = min(y_mid_compression, y_mid_tension)
    hi_y = max(y_mid_compression, y_mid_tension)
    mid_y = 0.5 * (lo_y + hi_y)
    # Same depth as strut head / internal face (y_head) — legacy sketch y for N* / V* alignment.
    _legacy_y_face_mid = y_to_legacy_y(mid_y)

    def _ann_arrow(
        ax0: float,
        ay0: float,
        x0: float,
        y0: float,
        *,
        color: str = "rgba(45,45,45,0.88)",
        width: float = 1.35,
        xref: str = "x",
        yref: str = "y",
    ) -> None:
        fig.add_annotation(
            x=x0,
            y=y0,
            ax=ax0,
            ay=ay0,
            xref=xref,
            yref=yref,
            axref=xref,
            ayref=yref,
            text="",
            showarrow=True,
            arrowhead=2,
            arrowsize=0.65,
            arrowwidth=width,
            arrowcolor=color,
            standoff=0,
            startstandoff=0,
        )

    def _ann_arrow_legacy(
        ax0: float,
        ay0: float,
        x0: float,
        y0: float,
        *,
        color: str = "rgba(45,45,45,0.88)",
        width: float = 1.35,
    ) -> None:
        _ann_arrow(ox(ax0), oy(ay0), ox(x0), oy(y0), color=color, width=width)

    y_face_hi = lo_y + 0.04
    y_face_lo = hi_y - 0.04
    if y_face_hi >= y_face_lo:
        y_face_hi, y_face_lo = mid_y - 0.18, mid_y + 0.18
    # N* — horizontal axial left of V*, toward the face (same height as red V_eq cue on the right)
    _n_tail_x, _n_head_x = 1.05, 2.18
    _ann_arrow_legacy(_n_tail_x, _legacy_y_face_mid, _n_head_x, _legacy_y_face_mid)
    fig.add_annotation(
        x=ox(0.5 * (_n_tail_x + _n_head_x)),
        y=oy(_legacy_y_face_mid + 0.06),
        text="N*",
        showarrow=False,
        yanchor="bottom",
        font=dict(size=11, color="rgba(35,35,35,0.92)"),
    )

    # M* — semicircular internal couple (left of N* / V*; CCW with C into face, T outward at tension level)
    r_m = max(0.085, 0.5 * (hi_y - lo_y))
    xc_m = -0.58
    mid_m = mid_y
    moment_arc_x: list[float] = []
    moment_arc_y: list[float] = []
    # Sweep 3π/2 → π/2: arc runs compression level → bulge left → tension level (counterclockwise couple).
    for i in range(33):
        t = 1.5 * math.pi - math.pi * (i / 32.0)
        moment_arc_x.append(xc_m + r_m * math.cos(t))
        moment_arc_y.append(mid_m + r_m * math.sin(t))
    fig.add_trace(
        go.Scatter(
            x=moment_arc_x,
            y=moment_arc_y,
            mode="lines",
            line=dict(color="rgba(45,45,45,0.9)", width=1.85),
            hoverinfo="skip",
            showlegend=False,
        )
    )
    fig.add_annotation(
        x=max(-0.92, xc_m - r_m - 0.06),
        y=mid_m,
        xref="x",
        yref="y",
        text="M*",
        showarrow=False,
        font=dict(size=11, color="rgba(35,35,35,0.92)"),
    )

    # V* geometry (norm x/y) — defined before strut so the diagonal can be shifted to intersect the vertical V*.
    _half_y_v = 0.058
    _vstar_leg_x = 3.12
    _vstar_xn = ox(_vstar_leg_x)
    _vstar_y_axis = mid_y - 0.048

    # Diagonal compression strut: top-right near C → face at mid-depth at MCFT θ (inward; not toward T).
    _th = float(theta_deg) if theta_deg is not None else 36.0
    _th = max(1.0, min(89.0, _th))
    theta_r = math.radians(_th)
    y_t = float(y_mid_tension)
    y_c = float(y_mid_compression)
    tan_t = math.tan(theta_r)
    if abs(tan_t) < 1e-5:
        tan_t = 1e-5

    x_head, y_head = 0.0, float(mid_y)
    if y_c < y_t:
        y_tail = float(y_c)
        d_run = max(y_head - y_tail, 1e-6)
        x_tail = d_run / tan_t
        if x_tail > 0.92:
            x_tail = 0.92
            y_tail = y_head - x_tail * tan_t
        if y_tail > y_c:
            y_tail = float(y_c)
            x_tail = max((y_head - y_tail) / tan_t, 1e-6)
    else:
        y_tail = float(y_c)
        d_run = max(y_tail - y_head, 1e-6)
        x_tail = d_run / tan_t
        if x_tail > 0.92:
            x_tail = 0.92
            y_tail = y_head + x_tail * tan_t
        if y_tail < y_c:
            y_tail = float(y_c)
            x_tail = max((y_tail - y_head) / tan_t, 1e-6)

    _strut_len_scale = 0.24
    x_tail = x_head + _strut_len_scale * (x_tail - x_head)
    y_tail = y_head + _strut_len_scale * (y_tail - y_head)

    _strut_h_cc_shift = 0.042
    x_head = x_head + _strut_h_cc_shift
    x_tail = x_tail + _strut_h_cc_shift
    # Slide strut: inboard end on V* — diagonal crosses shear.
    _dx_strut_to_vstar = _vstar_xn - x_head
    x_head_strut = x_head + _dx_strut_to_vstar
    x_tail_strut = x_tail + _dx_strut_to_vstar

    # θ label: mid-depth of beam (mid_y); x kept near diagonal strut.
    _xm_strut = 0.5 * (x_tail_strut + x_head_strut)
    _tsx = x_head_strut - x_tail_strut
    _tsy = y_head - y_tail
    _tsl = math.hypot(_tsx, _tsy) or 1.0
    _tnx = _tsy / _tsl
    _ax_ang = _xm_strut + 0.10 * _tnx + 0.004
    _ay_ang = float(mid_y) - 0.012
    _ax_ang = max(-0.90, min(0.92, _ax_ang))
    _ay_ang = max(0.04, min(0.96, _ay_ang))

    # Diagonal strut: dark translucent line.
    _strut_diag_line = "rgba(28,28,28,0.30)"

    fig.add_annotation(
        x=x_head_strut,
        y=y_head,
        ax=x_tail_strut,
        ay=y_tail,
        xref="x",
        yref="y",
        axref="x",
        ayref="y",
        text="",
        showarrow=True,
        arrowhead=2,
        arrowsize=0.72,
        arrowwidth=1.55,
        arrowcolor=_strut_diag_line,
        standoff=0,
        startstandoff=0,
    )

    # MCFT θ — dotted segment just under label (trace drawn first so text stays on top).
    _theta_dot_y = _ay_ang + 0.019
    fig.add_trace(
        go.Scatter(
            x=[_ax_ang - 0.195, _ax_ang + 0.058],
            y=[_theta_dot_y, _theta_dot_y],
            mode="lines",
            line=dict(color="rgba(55,55,55,0.82)", width=1.1, dash="dot"),
            showlegend=False,
            hoverinfo="skip",
        )
    )
    fig.add_annotation(
        x=_ax_ang,
        y=_ay_ang,
        xref="x",
        yref="y",
        text=f"θ = {_th:.1f}°",
        showarrow=False,
        xanchor="center",
        yanchor="middle",
        font=dict(size=9, color="rgba(55,55,55,0.92)"),
    )

    # C — horizontal into the face at compression resultant (stress-block centroid when section data supplied)
    _ann_arrow(
        0.88,
        y_mid_compression,
        0.06,
        y_mid_compression,
        color="rgba(180,55,55,0.88)",
        width=1.25,
    )
    fig.add_annotation(
        x=0.16,
        y=y_mid_compression + 0.07,
        xref="x",
        yref="y",
        text="C = −|M*/d_v| + 0.5N* + 0.5V_eq·cot θ",
        showarrow=False,
        xanchor="left",
        yanchor="middle",
        font=dict(size=10, color="rgba(180,55,55,0.82)"),
        bgcolor="rgba(255,255,255,0.68)",
    )

    # V* — vertical shear (x/y defined above with strut so they intersect).
    _ann_arrow(
        _vstar_xn,
        _vstar_y_axis - _half_y_v,
        _vstar_xn,
        _vstar_y_axis + _half_y_v,
        color="rgba(45,45,45,0.88)",
        width=1.35,
    )
    fig.add_annotation(
        x=min(0.92, _vstar_xn + 0.012),
        y=mid_y - 0.082,
        xref="x",
        yref="y",
        text="V*",
        showarrow=False,
        xanchor="left",
        yanchor="middle",
        font=dict(size=11, color="rgba(35,35,35,0.92)"),
    )

    # T — horizontal outward at tensile steel centroid (when section data supplied)
    _ann_arrow(
        0.06,
        y_mid_tension,
        0.88,
        y_mid_tension,
        color="rgba(30,90,180,0.88)",
        width=1.25,
    )
    fig.add_annotation(
        x=0.16,
        y=y_mid_tension + 0.075,
        xref="x",
        yref="y",
        text="T = |M*/d_v| + 0.5N* + 0.5V_eq·cot θ",
        showarrow=False,
        xanchor="left",
        yanchor="middle",
        font=dict(size=10, color="rgba(30,90,180,0.82)"),
        bgcolor="rgba(255,255,255,0.68)",
    )

    # Tangential arrowhead at the arc start (lo_y chord end); flipped to point opposite to CCW sweep.
    if len(moment_arc_x) >= 2:
        xe, ye = moment_arc_x[0], moment_arc_y[0]
        xp, yp = moment_arc_x[1], moment_arc_y[1]
        tx, ty = xp - xe, yp - ye
        tlen = math.hypot(tx, ty) or 1.0
        tx, ty = tx / tlen, ty / tlen
        ah = 0.038
        fig.add_annotation(
            x=xe,
            y=ye,
            ax=xe + ah * tx,
            ay=ye + ah * ty,
            xref="x",
            yref="y",
            axref="x",
            ayref="y",
            text="",
            showarrow=True,
            arrowhead=2,
            arrowsize=0.75,
            arrowwidth=1.65,
            arrowcolor="rgba(45,45,45,0.92)",
            standoff=0,
            startstandoff=0,
        )

    # Mid-depth note: two lines, left edge just right of the vertical face (C/T arrows at x ≈ 0.06).
    fig.add_annotation(
        xref="x",
        yref="y",
        x=0.10,
        y=mid_y,
        xanchor="left",
        yanchor="middle",
        text="Axial, moment and shear effects are resolved into flange forces<br>shared between the top and bottom flanges.",
        showarrow=False,
        font=dict(size=8, color="rgba(95,95,95,0.92)"),
    )

    # Column headings (paper coords — no change to data positions of forces / strut / arcs)
    _hdr_title = "rgba(35,35,35,0.96)"
    _hdr_sub = "rgba(105,105,105,0.95)"
    # Plotly: positive yshift moves the annotation up (toward the top of the figure).
    _hdr_y_title_px = 6
    _hdr_y_sub_px = -14
    fig.add_annotation(
        xref="paper",
        yref="paper",
        x=0.30,
        y=1.0,
        xanchor="center",
        yanchor="top",
        yshift=_hdr_y_title_px,
        text="<b>Section actions</b>",
        showarrow=False,
        font=dict(size=12, color=_hdr_title),
    )
    fig.add_annotation(
        xref="paper",
        yref="paper",
        x=0.30,
        y=1.0,
        xanchor="center",
        yanchor="top",
        yshift=_hdr_y_sub_px,
        text="Design actions at the section",
        showarrow=False,
        font=dict(size=9, color=_hdr_sub),
    )
    fig.add_annotation(
        xref="paper",
        yref="paper",
        x=0.74,
        y=1.0,
        xanchor="center",
        yanchor="top",
        yshift=_hdr_y_title_px,
        text="<b>Internal force resolution</b>",
        showarrow=False,
        font=dict(size=12, color=_hdr_title),
    )
    fig.add_annotation(
        xref="paper",
        yref="paper",
        x=0.74,
        y=1.0,
        xanchor="center",
        yanchor="top",
        yshift=_hdr_y_sub_px,
        text="Equivalent internal resisting forces<br>on the beam face",
        showarrow=False,
        font=dict(size=9, color=_hdr_sub),
    )


def make_mcft_longitudinal_strain_profile_fig(
    eps_top_uls: float,
    eps_x_mcft: float,
    eps_bot_uls: float,
    title: str = "Longitudinal strain profile",
    height: int = 430,
    *,
    force_resolution: bool = False,
    force_section_D_mm: float | None = None,
    force_section_c_mm: float | None = None,
    force_section_gamma: float | None = None,
    force_tension_steel_y_from_top_mm: float | None = None,
    force_moment_sign: str = "positive",
    force_theta_deg: float | None = None,
):
    """
    Check 4 MCFT longitudinal strain: mid-depth ε_x at the internal beam face (primary); short red stub
    at top (compression), horizontal cue at bottom from the face to the grey dashed trend endpoint (intersection),
    mid-depth tick for ε_x; optional faint grey dashed indicative trend. Same shared beam face as the
    force-resolution toggle.

    AS 3600 sign convention: ε < 0 = compression (red, left of face), ε > 0 = tension (blue, right).

    Args:
        eps_top_uls: Fallback for force diagram C/T depths when section geometry kwargs are omitted.
        eps_x_mcft: Governing longitudinal strain from MCFT (AS 3600 Cl. 8.2.4.2.2).
        eps_bot_uls: Fallback for force diagram C/T depths when section geometry kwargs are omitted.
        force_resolution: If True, show illustrative internal forces on the same ε=0 beam face.
        force_section_D_mm, force_section_c_mm, force_section_gamma, force_tension_steel_y_from_top_mm,
        force_moment_sign: Optional section data (same convention as bending_core._stress_strain_state ULS)
            so C is drawn at the rectangular stress-block centroid and T at the tensile steel centroid.
            If any required piece is missing, C/T fall back to mid-depths from eps_top_uls / eps_bot_uls.
        force_theta_deg: Strut angle θ (degrees) for the red diagonal strut; defaults in the overlay if omitted.
    """
    def _safe(v):
        try:
            return float(v)
        except Exception:
            return 0.0

    # AS 3600 sign convention: compression negative, tension positive
    eps_top_uls = _safe(eps_top_uls)
    eps_x_mcft = _safe(eps_x_mcft)
    eps_bot_uls = _safe(eps_bot_uls)

    # Depth coordinates: top at y=0.0, bottom at y=1.0 (normalized)
    # With autorange="reversed", y=0 appears at top, y=1 appears at bottom
    y_top = 0.0
    y_mid = 0.5
    y_bot = 1.0

    fig = go.Figure()

    _add_mcft_shared_beam_face(fig, y_top, y_bot)

    if force_resolution:
        y_mid_comp, y_mid_ten = _mcft_bending_zone_mid_depths(
            eps_top_uls,
            eps_bot_uls,
            y_top=y_top,
            y_bot=y_bot,
        )
        try:
            Df = float(force_section_D_mm) if force_section_D_mm is not None else None
            cf = float(force_section_c_mm) if force_section_c_mm is not None else None
            gf = float(force_section_gamma) if force_section_gamma is not None else None
            d_steel = (
                float(force_tension_steel_y_from_top_mm)
                if force_tension_steel_y_from_top_mm is not None
                else None
            )
            if Df is not None and cf is not None and gf is not None and d_steel is not None:
                res = _mcft_force_resultant_depths_norm(
                    D_mm=Df,
                    c_mm=cf,
                    gamma=gf,
                    tension_steel_y_from_top_mm=d_steel,
                    moment_sign=force_moment_sign,
                    y_top=y_top,
                    y_bot=y_bot,
                )
                if res is not None:
                    y_mid_comp, y_mid_ten = res
        except Exception:
            pass
        _add_mcft_force_resolution_overlay(
            fig,
            y_mid_compression=y_mid_comp,
            y_mid_tension=y_mid_ten,
            theta_deg=force_theta_deg,
        )
    else:
        half_range_eps = _compute_mcft_strain_symmetric_half_range_eps_x(eps_x_mcft)
        sx_scale = MCFT_CHECK4_FACE_X_HALF / half_range_eps

        def sx(eps: float) -> float:
            return float(eps) * sx_scale

        emax_temp = max(abs(eps_x_mcft), 1e-6)
        color_mid_tick = "red" if eps_x_mcft < 0 else "blue"
        vis_scale = 1.0 - MCFT_CHECK4_EPSX_VISUAL_INWARD
        x_vis = sx(eps_x_mcft) * vis_scale

        # Indicative strain trend (teaching only): compression above / tension below ε=0, through (x_vis, y_mid).
        _x_trend_top, _x_trend_bot = _mcft_schematic_strain_trend_endpoints(x_vis)
        fig.add_trace(
            go.Scatter(
                x=[_x_trend_top, _x_trend_bot],
                y=[y_top, y_bot],
                mode="lines",
                line=dict(
                    width=0.85,
                    color="rgba(120,120,120,0.32)",
                    dash="dash",
                ),
                hoverinfo="skip",
                showlegend=False,
            )
        )

        # Reference cue: compression at top fibre (short stub left of beam face — not a full profile).
        x_top_comp = sx(-MCFT_CHECK4_TOP_COMP_CUE_FRAC * emax_temp) * vis_scale
        x_top_comp = max(x_top_comp, -0.88 * MCFT_CHECK4_FACE_X_HALF)
        fig.add_shape(
            type="line",
            x0=0,
            y0=y_top,
            x1=x_top_comp,
            y1=y_top,
            line=dict(width=1.35, color="rgba(200,50,50,0.9)"),
            layer="below",
        )

        # Bottom fibre cue: beam face → same x as dashed schematic at y_bot (intersects the dashed line).
        x_end_bot = float(_x_trend_bot)
        bot_cue_color = (
            "rgba(30,100,200,0.55)"
            if x_end_bot > 1e-9
            else ("rgba(200,50,50,0.9)" if x_end_bot < -1e-9 else "rgba(90,90,90,0.75)")
        )
        if abs(x_end_bot) > 1e-9:
            _bot_cue_width = 1.0 if x_end_bot > 1e-9 else 1.35
            fig.add_shape(
                type="line",
                x0=0,
                y0=y_bot,
                x1=x_end_bot,
                y1=y_bot,
                line=dict(width=_bot_cue_width, color=bot_cue_color),
                layer="above",
            )

        # Mid-depth: strain level used for MCFT (beam face → ε_x); matches point colour (blue tension / red compression).
        fig.add_shape(
            type="line",
            x0=0,
            y0=y_mid,
            x1=x_vis,
            y1=y_mid,
            line=dict(
                color=color_mid_tick,
                width=1.55,
            ),
            layer="below",
        )
        fig.add_trace(
            go.Scatter(
                x=[x_vis],
                y=[y_mid],
                mode="markers",
                marker=dict(size=20, color=color_mid_tick, line=dict(width=2.4, color="black")),
                hoverinfo="skip",
                showlegend=False,
            )
        )

        emax = max(abs(eps_x_mcft), 1e-6)
        label_offset = 0.05 * emax
        if eps_x_mcft < 0.0:
            label_x_mid = eps_x_mcft - label_offset
            xanchor_mid = "right"
            state_mid = "(compression)"
        else:
            label_x_mid = eps_x_mcft + label_offset
            xanchor_mid = "left"
            state_mid = "(tension)"
        fig.add_annotation(
            x=sx(label_x_mid) * vis_scale + 0.11,
            y=y_mid + 0.06 * (y_bot - y_top),
            text=f"ε<sub>x</sub> = {eps_x_mcft:.5f}<br><span style='font-size:11px'>mid-depth (MCFT)</span><br><span style='font-size:10px'>{state_mid}</span>",
            showarrow=False,
            font=dict(size=12, color=color_mid_tick),
            xanchor=xanchor_mid,
            yshift=0,
            bgcolor="rgba(255,255,255,0.85)",
        )
        fig.add_annotation(
            x=0.0,
            y=y_bot + 0.028 * (y_bot - y_top),
            text="Indicative strain trend only — not a calculated full-depth strain profile.",
            showarrow=False,
            font=dict(size=9, color="rgba(95,95,95,0.98)"),
            xanchor="center",
        )

    _apply_mcft_check4_layout(
        fig,
        height,
        y_top,
        y_bot,
        extra_top_margin=MCFT_CHECK4_TOP_MARGIN_SHIFT_PX
        + (MCFT_CHECK4_TOP_MARGIN_FORCE_HEADINGS_PX if force_resolution else 0),
        extend_y_top_norm=MCFT_CHECK4_FORCE_DIAGRAM_AXIS_TOP_GAP if force_resolution else 0.0,
    )
    return fig


def plot_shear_step4_middepth_strain_diagram(
    b_mm: float,
    D_mm: float,
    eps_x: float,
    *,
    title: str = "Mid-depth longitudinal strain",
):
    """
    Bending-style strain diagram for Step 4.
    Shows section rectangle + strain panel with linear profile and εx at mid-depth.
    """
    b = float(b_mm)
    D = float(D_mm)
    epsx = float(eps_x)

    # Interpretation based on sign
    if epsx >= 0:
        strain_state = "tension at mid-depth"
    else:
        strain_state = "compression at mid-depth"

    # Create subplots: Section (left) and Strain (right)
    fig = make_subplots(
        rows=1, cols=2,
        column_widths=[0.4, 0.6],
        horizontal_spacing=0.15,
        subplot_titles=["Section", "Strain"],
    )

    # =====================================================
    # 1) SECTION PANEL (left)
    # =====================================================
    # Outer section rectangle
    fig.add_shape(
        type="rect",
        x0=0, y0=0, x1=b, y1=D,
        line=dict(width=3, color="black"),
        fillcolor="white",
        layer="below",
        row=1, col=1,
    )

    # Mid-depth line (y = D/2) - dashed
    y_mid = 0.5 * D
    fig.add_shape(
        type="line",
        x0=0, y0=y_mid, x1=b, y1=y_mid,
        line=dict(width=2, color="black", dash="dash"),
        layer="above",
        row=1, col=1,
    )

    # Small marker point at mid-depth (center)
    fig.add_trace(
        go.Scatter(
            x=[0.5 * b],
            y=[y_mid],
            mode="markers",
            marker=dict(size=10, color="black"),
            hoverinfo="skip",
            showlegend=False,
        ),
        row=1, col=1,
    )

    # Section axes setup
    fig.update_xaxes(visible=False, range=[-0.08*b, 1.08*b], row=1, col=1)
    fig.update_yaxes(visible=False, range=[-0.06*D, 1.06*D], scaleanchor="x1", scaleratio=1, row=1, col=1)

    # =====================================================
    # 2) STRAIN PANEL (right) - matching bending style
    # =====================================================
    panel_x_center = 0.5
    half_w = 0.35
    eps_max = max(abs(epsx), 1e-4) * 1.3

    def strain_to_x(eps_display: float) -> float:
        """Map display ε (compression < 0 left, tension > 0 right) → panel x."""
        return strain_display.strain_display_to_panel_x(
            eps_display,
            panel_x_center=panel_x_center,
            half_w=half_w,
            eps_scale_max=eps_max,
        )

    x_mid = panel_x_center  # neutral axis (ε = 0)
    x_epsx = strain_to_x(epsx)

    # Vertical depth line at ε = 0 (strain axis)
    fig.add_shape(
        type="line",
        x0=panel_x_center,
        y0=0,
        x1=panel_x_center,
        y1=D,
        line=dict(color="black", width=1.0),
        row=1, col=2,
    )

    # Simplified linear strain profile: assume linear from top to bottom through mid-depth
    # For visualization, create a reasonable profile that passes through εx at mid-depth
    # Linear interpolation: eps = eps_top + (eps_bot - eps_top) * (y / D)
    # At y = D/2: epsx = eps_top + (eps_bot - eps_top) * 0.5
    # Solve: eps_top = 2*epsx - eps_bot
    # Use reasonable estimates for visualization
    if epsx >= 0:
        # Tension at mid-depth: assume less tension at top, more at bottom
        eps_bot_est = epsx * 1.8
        eps_top_est = 2.0 * epsx - eps_bot_est
    else:
        # Compression at mid-depth: assume more compression at top, less at bottom
        eps_bot_est = epsx * 0.2
        eps_top_est = 2.0 * epsx - eps_bot_est

    x_top = strain_to_x(eps_top_est)
    x_bot = strain_to_x(eps_bot_est)

    # Strain line (top → mid → bottom)
    fig.add_trace(
        go.Scatter(
            x=[x_top, x_epsx, x_bot],
            y=[0, y_mid, D],
            mode="lines",
            line=dict(color="black", width=1.5),
            hoverinfo="skip",
            showlegend=False,
        ),
        row=1, col=2,
    )

    # Mid-depth horizontal line and label (ε_x) - the key value
    tick_color = "blue" if epsx >= 0.0 else "red"
    fig.add_shape(
        type="line",
        x0=panel_x_center,
        y0=y_mid,
        x1=x_epsx,
        y1=y_mid,
        line=dict(color=tick_color, width=2.0),
        row=1, col=2,
    )

    label_x, xanchor = strain_display.strain_label_anchor_display(
        epsx, x_epsx, offset=0.02
    )

    fig.add_annotation(
        x=label_x,
        y=y_mid,
        text=rf"$\varepsilon_x$ = {epsx:.5f}<br><span style='font-size:11px'>{strain_state}</span>",
        showarrow=False,
        font=dict(size=12, color=tick_color),
        yshift=0,
        xanchor=xanchor,
        row=1, col=2,
    )

    # Strain panel axes setup
    fig.update_xaxes(visible=False, range=[0.0, 1.0], row=1, col=2)
    fig.update_yaxes(visible=False, range=[-0.06*D, 1.06*D], scaleanchor="x2", scaleratio=1, row=1, col=2)

    # AS 3600 strain limits note (small, non-dominant)
    fig.add_annotation(
        x=0.5,
        y=-0.12 * D,
        xref="x2", yref="y2",
        text=r"AS 3600 limits: $-2.0\times10^{-4} \le \varepsilon_x \le 3.0\times10^{-3}$",
        showarrow=False,
        font=dict(size=11, color="rgba(60,60,60,0.85)"),
        row=1, col=2,
    )

    # Overall layout
    fig.update_layout(
        margin=dict(l=6, r=6, t=40, b=6),
        height=420,
        paper_bgcolor="white",
        plot_bgcolor="white",
        showlegend=False,
    )

    return fig


def plot_step4_mcft_strain_diagram(
    D_mm: float,
    eps_mid: float,
    eps_top: float,
    eps_bot: float,
    *,
    title: str = "Longitudinal strain profile",
):
    """
    Longitudinal strain profile for Step 4 MCFT (display convention: compression ε < 0 left, tension ε > 0 right).
    """
    D = float(D_mm)
    e_mid = float(eps_mid)
    e_top = float(eps_top)
    e_bot = float(eps_bot)

    # y=0 top, y=D bottom
    y_top, y_mid, y_bot = 0.0, 0.5 * D, D

    # Build a simple linear profile line through the three points
    fig = go.Figure()

    # Vertical ε=0 axis (explicitly at x=0)
    fig.add_shape(
        type="line",
        x0=0, x1=0,
        y0=-0.05*D, y1=1.05*D,
        line=dict(width=4, color="black"),
        layer="below",
    )

    # Profile line (top -> mid -> bottom)
    fig.add_trace(go.Scatter(
        x=[e_top, e_mid, e_bot],
        y=[y_top, y_mid, y_bot],
        mode="lines+markers",
        line=dict(width=3, color="black"),
        marker=dict(size=12, color="black"),
        hoverinfo="skip",
        showlegend=False,
    ))

    # Horizontal lines from zero axis to strain values (display AS 3600 sense)
    emax = max(abs(e_top), abs(e_mid), abs(e_bot), 1e-6)
    offset = 0.02 * emax

    # Top strain horizontal line and label
    color_top = strain_display.strain_color_display(e_top)
    fig.add_shape(
        type="line",
        x0=0, y0=y_top, x1=e_top, y1=y_top,
        line=dict(color=color_top, width=2.0),
    )
    label_x_top, xanchor_top = strain_display.strain_label_anchor_display(
        e_top, e_top, offset=offset
    )
    state_top = "(compression)" if e_top < 0.0 else "(tension)"
    fig.add_annotation(
        x=label_x_top, y=y_top,
        text=f"ε<sub>top</sub> = {e_top:.5f}<br><span style='font-size:10px'>{state_top}</span>",
        showarrow=False,
        font=dict(size=12, color=color_top),
        xanchor=xanchor_top,
        yshift=-12,
        bgcolor="rgba(255,255,255,0.7)",
    )
    
    # Mid-depth strain horizontal line and label (ε_x) - highlighted
    color_mid = strain_display.strain_color_display(e_mid)
    fig.add_shape(
        type="line",
        x0=0, y0=y_mid, x1=e_mid, y1=y_mid,
        line=dict(color=color_mid, width=2.0),
    )
    label_x_mid, xanchor_mid = strain_display.strain_label_anchor_display(
        e_mid, e_mid, offset=offset
    )
    state_mid = "(compression)" if e_mid < 0.0 else "(tension)"
    fig.add_annotation(
        x=label_x_mid, y=y_mid,
        text=f"ε<sub>x</sub> = {e_mid:.5f}<br><span style='font-size:11px'>mid-depth (MCFT)</span><br><span style='font-size:10px'>{state_mid}</span>",
        showarrow=False,
        font=dict(size=12, color=color_mid),
        xanchor=xanchor_mid,
        yshift=0,
        bgcolor="rgba(255,255,255,0.7)",
    )
    
    # Bottom strain horizontal line and label
    color_bot = strain_display.strain_color_display(e_bot)
    fig.add_shape(
        type="line",
        x0=0, y0=y_bot, x1=e_bot, y1=y_bot,
        line=dict(color=color_bot, width=2.0),
    )
    label_x_bot, xanchor_bot = strain_display.strain_label_anchor_display(
        e_bot, e_bot, offset=offset
    )
    state_bot = "(compression)" if e_bot < 0.0 else "(tension)"
    fig.add_annotation(
        x=label_x_bot, y=y_bot,
        text=f"ε<sub>bot</sub> = {e_bot:.5f}<br><span style='font-size:10px'>{state_bot}</span>",
        showarrow=False,
        font=dict(size=12, color=color_bot),
        xanchor=xanchor_bot,
        yshift=12,
        bgcolor="rgba(255,255,255,0.7)",
    )

    # Title
    fig.add_annotation(
        xref="paper", yref="paper",
        x=0.5, y=1.06,
        text=f"<b>{title}</b>",
        showarrow=False,
        font=dict(size=18, color="rgba(70,70,90,0.85)"),
        align="center",
    )

    # Subtitle (small)
    fig.add_annotation(
        xref="paper", yref="paper",
        x=0.5, y=1.02,
        text="<span style='font-size:12px'>ε<sub>x</sub> evaluated at mid-depth (MCFT – AS 3600 Cl. 8.2.4.2.2)</span>",
        showarrow=False,
        font=dict(size=12, color="rgba(70,70,90,0.75)"),
        align="center",
    )

    # AS 3600 limits annotation (context only, no bounding boxes)
    fig.add_annotation(
        xref="paper", yref="paper",
        x=0.5, y=0.98,
        text="<span style='font-size:11px'>AS 3600 limits: −2.0×10⁻⁴ ≤ ε<sub>x</sub> ≤ 3.0×10⁻³</span>",
        showarrow=False,
        font=dict(size=11, color="rgba(70,70,90,0.7)"),
        align="center",
    )

    # Axes formatting: ensure x=0 is always visible
    xmin = min(e_top, e_mid, e_bot, 0.0)
    xmax = max(e_top, e_mid, e_bot, 0.0)
    pad = 0.15 * (xmax - xmin if (xmax - xmin) > 0 else 1.0e-4)
    
    fig.update_xaxes(visible=False, range=[xmin - pad, xmax + pad])
    fig.update_yaxes(visible=False, range=[-0.10*D, 1.25*D])

    fig.update_layout(
        margin=dict(l=10, r=10, t=80, b=10),
        height=420,
        paper_bgcolor="white",
        plot_bgcolor="white",
        showlegend=False,
    )

    return fig


def make_step4_longitudinal_strain_diagram(
    D_mm: float,
    eps_x: float,
    eps_top: float,
    eps_bot: float,
    eps_min: float = -2.0e-4,
    eps_max: float = 3.0e-3,
    height_px: int = 540,
):
    """
    Step 4 diagram: longitudinal strain profile for MCFT.
    Display: compression ε < 0 left, tension ε > 0 right (same as bending strain panel).
    """
    # Guardrails
    def _safe(v):
        try:
            return float(v)
        except Exception:
            return 0.0

    D = float(D_mm)
    eps_x = _safe(eps_x)
    eps_top = _safe(eps_top)
    eps_bot = _safe(eps_bot)

    # y-coordinates: top, mid, bottom (real depth coordinates like bending)
    y_top = 0.0
    y_mid = 0.5 * D
    y_bot = D

    # Build figure
    fig = go.Figure()

    # Vertical reference axis (zero strain line, like bending strain panel)
    fig.add_shape(
        type="line",
        x0=0, y0=y_top - 0.05*D, x1=0, y1=y_bot + 0.05*D,
        line=dict(width=3, color="black"),
        layer="below",
    )

    # Strain profile line: connect (eps_top,y_top) -> (eps_x,y_mid) -> (eps_bot,y_bot)
    # This is the main strain distribution line (like bending strain panel)
    # Shows the linear strain profile from top to bottom
    fig.add_trace(go.Scatter(
        x=[eps_top, eps_x, eps_bot],
        y=[y_top, y_mid, y_bot],
        mode="lines+markers",
        line=dict(width=3.5, color="black"),
        marker=dict(size=12, color="black"),
        hoverinfo="skip",
        showlegend=False,
    ))

    lo = 0.02 * max(abs(eps_top), abs(eps_x), abs(eps_bot), 1e-6)
    color_top = strain_display.strain_color_display(eps_top)
    color_mid = strain_display.strain_color_display(eps_x)
    color_bot = strain_display.strain_color_display(eps_bot)

    # Horizontal "ticks" from zero axis to each strain value (display convention)
    fig.add_shape(
        type="line",
        x0=0, y0=y_top, x1=eps_top, y1=y_top,
        line=dict(color=color_top, width=2.0),
    )
    fig.add_shape(
        type="line",
        x0=0, y0=y_mid, x1=eps_x, y1=y_mid,
        line=dict(color=color_mid, width=2.0),
    )
    fig.add_shape(
        type="line",
        x0=0, y0=y_bot, x1=eps_bot, y1=y_bot,
        line=dict(color=color_bot, width=2.0),
    )

    label_x_top, xanchor_top = strain_display.strain_label_anchor_display(
        eps_top, eps_top, offset=lo
    )
    fig.add_annotation(
        x=label_x_top, y=y_top,
        text=f"ε<sub>top</sub> = {eps_top:.5f}",
        showarrow=False,
        font=dict(size=12, color=color_top),
        xanchor=xanchor_top,
        yshift=-10,
    )

    label_x_mid, xanchor_mid = strain_display.strain_label_anchor_display(
        eps_x, eps_x, offset=lo
    )
    fig.add_annotation(
        x=label_x_mid, y=y_mid,
        text=f"ε<sub>x</sub> = {eps_x:.5f}<br><span style='font-size:11px'>mid-depth (MCFT)</span>",
        showarrow=False,
        font=dict(size=12, color=color_mid),
        xanchor=xanchor_mid,
        yshift=0,
    )

    label_x_bot, xanchor_bot = strain_display.strain_label_anchor_display(
        eps_bot, eps_bot, offset=lo
    )
    fig.add_annotation(
        x=label_x_bot, y=y_bot,
        text=f"ε<sub>bot</sub> = {eps_bot:.5f}",
        showarrow=False,
        font=dict(size=12, color=color_bot),
        xanchor=xanchor_bot,
        yshift=10,
    )

    # Title (match bending style - subtle grey, paper coordinates)
    fig.add_annotation(
        xref="paper", yref="paper",
        x=0.5, y=1.06,
        text="<b>Longitudinal strain profile</b>",
        showarrow=False,
        font=dict(size=18, color="rgba(70,70,90,0.85)"),
        align="center",
    )

    # Limits annotation (top caption, paper coordinates)
    fig.add_annotation(
        xref="paper", yref="paper",
        x=0.5, y=1.12,
        text="AS 3600 limits: -2.0×10⁻⁴ ≤ ε<sub>x</sub> ≤ 3.0×10⁻³",
        showarrow=False,
        font=dict(size=13, color="rgba(70,70,90,0.85)"),
        align="center",
    )

    # Axis framing: big, clean, no clutter
    # Keep x-range tight around values, but include limits so users "see" the clamp region
    x_lo = min(eps_top, eps_x, eps_bot, eps_min)
    x_hi = max(eps_top, eps_x, eps_bot, eps_max)
    pad = 0.12 * (x_hi - x_lo if (x_hi - x_lo) > 0 else 1.0)

    # y-range like bending: range=[D*1.05, -0.18*D] (so "top" appears at top)
    fig.update_layout(
        margin=dict(l=10, r=10, t=70, b=10),
        height=height_px,
        xaxis=dict(
            visible=False,
            range=[x_lo - pad, x_hi + pad],
        ),
        yaxis=dict(
            visible=False,
            range=[D * 1.05, -0.18 * D],  # Inverted so top appears at top
            scaleanchor="x",
            scaleratio=1,
        ),
        paper_bgcolor="white",
        plot_bgcolor="white",
        showlegend=False,
    )

    return fig


# ------------------------------------------------------------
#  3D Torsion/Shear Crack Helix Diagram (Unwrapped Surface)
# ------------------------------------------------------------

def proj(P, a=-0.65, b=0.28):
    """Project 3D point to 2D using camera parameters."""
    x, y, z = P
    u = x + a * y
    v = z + b * y
    return np.array([u, v], dtype=float)


def clamp_inside(val, lo, hi, eps=1e-6):
    """
    Clamp scalar OR numpy array into (lo+eps, hi-eps).
    Returns same type shape as input.
    """
    if np.isscalar(val):
        return max(lo + eps, min(hi - eps, float(val)))
    arr = np.asarray(val, dtype=float)
    return np.clip(arr, lo + eps, hi - eps)


def ray_rect_hit_2d(p, d, umin, umax, vmin, vmax, eps=1e-9):
    """
    Intersect ray p + t d (t>0) with axis-aligned rectangle [umin,umax]x[vmin,vmax].
    Returns nearest hit (t, hit_point), else (None, None).
    """
    p = np.asarray(p, float)
    d = np.asarray(d, float)

    hits = []

    # u = umin / umax
    if abs(d[0]) > eps:
        for u in (umin, umax):
            t = (u - p[0]) / d[0]
            if t > eps:
                v = p[1] + t * d[1]
                if vmin - 1e-9 <= v <= vmax + 1e-9:
                    hits.append((t, np.array([u, v], float)))

    # v = vmin / vmax
    if abs(d[1]) > eps:
        for v in (vmin, vmax):
            t = (v - p[1]) / d[1]
            if t > eps:
                u = p[0] + t * d[0]
                if umin - 1e-9 <= u <= umax + 1e-9:
                    hits.append((t, np.array([u, v], float)))

    if not hits:
        return None, None

    hits.sort(key=lambda x: x[0])
    return hits[0][0], hits[0][1]


def surface_point(x, s, B, D):
    """
    Map (x, s%P3) to 3D point on unwrapped surface.
    P3 = 2*B + D is the 3-face perimeter (roof + far wall + bottom).
    Unwrapping order: roof (0..B) -> far wall (B..B+D) -> bottom (B+D..2*B+D)
    NO near wall (Y=0) - closure is via front end face (X=0).
    Returns (x, y, z, face_name) where face_name is one of: 'roof', 'far', 'bottom'
    """
    P3 = 2.0 * B + D
    s_mod = float(s % P3)
    if s_mod < 0:
        s_mod += P3
    
    if s_mod < B:
        # (A) Roof (Z=D), from near edge to far edge
        y = s_mod
        z = D
        return np.array([x, y, z], float), 'roof'
    elif s_mod < B + D:
        # (B) Far wall (Y=B), go down
        y = B
        z = D - (s_mod - B)
        return np.array([x, y, z], float), 'far'
    else:
        # (C) Bottom (Z=0), go back toward near
        y = B - (s_mod - (B + D))
        z = 0.0
        return np.array([x, y, z], float), 'bottom'


def draw_face_label_debug(cam_a=-0.65, cam_b=0.28, L=10.0, B=3.2, D=2.4, fs=10, show_corners=True,
                           n_cracks=3, start_t_min=0.1, start_t_span=0.3, crack_lw=4.0, show_cracks=False,
                           k_slope=0.5, s0_min=0.1, theta_deg=45.0):
    """
    Draw the 3D torsion prism with unwrapped surface crack helixes.
    Uses 2D projection (not 3D matplotlib).
    """
    # 8 corners in 3D
    FBR = np.array([0, 0, 0])
    FBL = np.array([0, B, 0])
    FTR = np.array([0, 0, D])
    FTL = np.array([0, B, D])

    BBR = np.array([L, 0, 0])
    BBL = np.array([L, B, 0])
    BTR = np.array([L, 0, D])
    BTL = np.array([L, B, D])

    def P2D(P3):
        return proj(P3, a=cam_a, b=cam_b)

    # Only the 3 faces you want visible
    faces_3d = {
        "SIDE WALL (Y=0)":    [FBL, FTL, FTR, FBR],  # SAME polygon as before, NEW label
        "ROOF (Z=D)":         [FTL, BTL, BTR, FTR],  # unchanged
        "END FACE (X=0)":     [FTR, BTR, BBR, FBR],  # SAME polygon as before, NEW label
    }

    faces_2d = {name: np.array([P2D(p) for p in pts], float) for name, pts in faces_3d.items()}

    fig, ax = plt.subplots(figsize=(9, 5))

    # Draw SOLID filled faces (white, no transparency)
    for name in ["END FACE (X=0)", "ROOF (Z=D)", "SIDE WALL (Y=0)"]:
        poly = faces_2d[name]
        ax.fill(poly[:, 0], poly[:, 1], color='white', alpha=1.0, zorder=1)  # solid white
        P = np.vstack([poly, poly[0]])
        ax.plot(P[:, 0], P[:, 1], linewidth=2.2, zorder=2)

    # ------------------------------------------------------------
    # Torsion arrows on END FACE (always visible)
    # ------------------------------------------------------------
    # Always show arrows regardless of cracks
    end_poly = faces_2d["END FACE (X=0)"]  # 4 points in 2D
    cx = float(np.mean(end_poly[:, 0]))
    cy = float(np.mean(end_poly[:, 1]))

    # Use a radius based on face size
    span_u = float(np.max(end_poly[:, 0]) - np.min(end_poly[:, 0]))
    span_v = float(np.max(end_poly[:, 1]) - np.min(end_poly[:, 1]))
    r = 0.18 * min(span_u, span_v)

    def arc_arrow_ccw(a0, a1, lw=2.4):
        # CCW arc from angle a0 to a1 around centroid
        x0 = cx + r * math.cos(a0)
        y0 = cy + r * math.sin(a0)
        x1 = cx + r * math.cos(a1)
        y1 = cy + r * math.sin(a1)

        arr = FancyArrowPatch(
            (x0, y0), (x1, y1),
            arrowstyle="-|>",
            mutation_scale=14,
            linewidth=lw,
            color="black",
            connectionstyle="arc3,rad=0.35",  # curved arc
            zorder=80,
        )
        ax.add_patch(arr)

    # Two CCW curved arrows (counter-clockwise)
    arc_arrow_ccw(a0=math.radians(-30), a1=math.radians(80))
    arc_arrow_ccw(a0=math.radians(150), a1=math.radians(260))

    # Optional label
    ax.text(cx, cy, "T", ha="center", va="center", fontsize=10, zorder=85)

    # Crack generation: unwrapped surface helix approach (3-face only)
    if show_cracks:
        P3_perimeter = float(2.0 * B + D)  # 3-face perimeter: roof + far wall + bottom (ensure Python float)
        epsx = 1e-3 * L
        eps = 1e-6
        
        # Sample start s0 values
        tmax = min(0.98, start_t_min + start_t_span)
        ts = np.linspace(start_t_min, tmax, max(1, int(n_cracks)))
        s0_values = [float(t * P3_perimeter) for t in ts]  # Convert to Python floats
        
        # Sample points along x for each crack
        n_samples = 200  # Number of points to sample along x
        x_samples = np.linspace(0.0, L - epsx, n_samples)
        
        def plot_seg(Pa3, Pb3, face_name, lw):
            """Plot segment with guard against forbidden Y=0 wall"""
            if Pa3 is None or Pb3 is None:
                return
            
            # Hard filter: reject ONLY pure vertical segments on the near wall (Y=0)
            # (i.e. x ~ constant but z changes). We DO want sloped drops where x changes.
            ya = abs(float(Pa3[1]))
            yb = abs(float(Pb3[1]))
            xa = float(Pa3[0])
            xb = float(Pb3[0])
            za = float(Pa3[2])
            zb = float(Pb3[2])
            
            dx = abs(xa - xb)
            dz = abs(za - zb)
            
            # If it's on y=0 AND basically no x movement AND it drops in z => reject
            if (ya < eps and yb < eps and dx < (2.0 * epsx) and dz > eps):
                return
            
            a2 = P2D(Pa3)
            b2 = P2D(Pb3)
            
            # Check if segment is on visible face
            # Visible: roof and side wall (green face x=0)
            # Green face segments have x=0, so check for that
            xa_abs = abs(float(Pa3[0]))
            xb_abs = abs(float(Pb3[0]))
            on_green_face = (xa_abs < epsx and xb_abs < epsx)
            is_visible = (face_name in ('roof', 'side') or on_green_face)
            
            if is_visible:
                ax.plot(
                    [a2[0], b2[0]],
                    [a2[1], b2[1]],
                    linewidth=lw,
                    solid_capstyle="round",
                    zorder=50,
                    color='black',
                )
            else:
                # Hidden faces: dashed line
                ax.plot(
                    [a2[0], b2[0]],
                    [a2[1], b2[1]],
                    linewidth=lw * 0.6,
                    linestyle='--',
                    alpha=0.4,
                    zorder=45,
                    color='gray',
                )
        
        for s0 in s0_values:
            # Define crack path: s(x) = s0 + k*x
            # Convert to Python floats to avoid numpy type issues
            s_values = [float(s0 + k_slope * x) for x in x_samples]
            
            # Map to 3D points and track face changes
            points_3d = []
            face_names = []
            s_mod_values = []
            
            for i, x in enumerate(x_samples):
                s = s_values[i]  # Already a Python float
                P3, face = surface_point(x, s, B, D)
                points_3d.append(P3)
                face_names.append(face)
                
                # Track s_mod to detect wraps (ensure all are Python floats)
                s_mod = float(s) % P3_perimeter
                if s_mod < 0:
                    s_mod = s_mod + P3_perimeter
                s_mod_values.append(s_mod)
            
            # Store original points_3d for this crack before building segments
            crack_points_3d = points_3d.copy()
            crack_face_names = face_names.copy()
            
            # Build polyline segments, inserting side wall continuation at wraps
            segments = []  # List of (points, face_name) tuples
            
            current_segment = [points_3d[0]]
            current_face = face_names[0]
            prev_s_mod = s_mod_values[0]
            
            for i in range(1, len(points_3d)):
                s_mod = s_mod_values[i]
                
                # Check for wrap (more bulletproof: check if integer part of s/P3 changed)
                wrap_detected = False
                prev_wrap_count = int(s_values[i-1] / P3_perimeter)
                curr_wrap_count = int(s_values[i] / P3_perimeter)
                wrap_detected = (prev_wrap_count != curr_wrap_count)
                
                if wrap_detected:
                    # Finish current segment
                    if len(current_segment) > 1:
                        segments.append((current_segment, current_face))
                    
                    # Add side wall continuation on Y=0 when wrapping
                    # Get the bottom point (last point of current segment)
                    P_bottom = current_segment[-1].copy()
                    x_bottom = float(P_bottom[0])
                    # Clamp x away from end face to ensure it stays on side wall
                    x_bottom = float(clamp_inside(x_bottom, epsx, L - epsx, eps=1e-6))
                    
                    # Get the roof point (next point after wrap)
                    P_roof_next = points_3d[i].copy()
                    x_roof = float(P_roof_next[0])
                    # Clamp x away from end face to ensure it stays on side wall
                    x_roof = float(clamp_inside(x_roof, epsx, L - epsx, eps=1e-6))
                    
                    # Continue on side wall (Y=0): slanted line from bottom to roof
                    # Start at bottom edge of side wall: (x_bottom, 0, 0)
                    # End at roof edge of side wall: (x_roof, 0, D)
                    # This creates a slanted continuation on the side wall
                    P_side_start = np.array([x_bottom, 0.0, 0.0], float)
                    P_side_end = np.array([x_roof, 0.0, D], float)
                    segments.append(([P_side_start, P_side_end], 'side'))
                    
                    # Start new segment from side wall end to next roof point
                    current_segment = [P_side_end, P_roof_next]
                    current_face = face_names[i]
                elif face_names[i] != current_face:
                    # Face boundary crossed (not a wrap): finish current segment and start new one
                    if len(current_segment) > 1:
                        segments.append((current_segment, current_face))
                    # Start new segment (include last point of previous segment for continuity)
                    current_segment = [current_segment[-1], points_3d[i]]
                    current_face = face_names[i]
                else:
                    # Same face: continue segment
                    current_segment.append(points_3d[i])
                
                prev_s_mod = s_mod
            
            # Add remaining segment
            if len(current_segment) > 1:
                segments.append((current_segment, current_face))
            
            # --- Extend each roof crack down the GREEN face (x=0) as a continuation ---
            # Green face = x=0 = "SIDE WALL (Y=0)" label (but actually x=0 plane)
            # Use the original crack_points_3d to find where roof crack hits x=0
            
            # θ is now the true physical crack angle
            theta = math.radians(theta_deg)
            tan_t = math.tan(theta)
            
            wall_drops = []
            
            # Find where this roof crack (from original points) intersects x=0
            # This ensures wall drops are directly linked to roof cracks
            roof_pts = [p for p, f in zip(crack_points_3d, crack_face_names) if f == "roof"]
            
            if len(roof_pts) >= 2:
                # Find where the roof crack crosses x=0
                hit_point = None
                
                # Search through roof points to find where it crosses x=0
                for k in range(len(roof_pts) - 1):
                    P0 = roof_pts[k]
                    P1 = roof_pts[k + 1]
                    x0, x1 = float(P0[0]), float(P1[0])
                    
                    # Check if this segment crosses x=0
                    if (x0 <= 0.0 + 1e-9 and x1 >= 0.0 - 1e-9) or (x1 <= 0.0 + 1e-9 and x0 >= 0.0 - 1e-9):
                        # Segment crosses x=0, interpolate to find exact intersection
                        if abs(x1 - x0) > 1e-12:
                            t = (0.0 - x0) / (x1 - x0)
                            t = float(np.clip(t, 0.0, 1.0))
                            y_hit = float(P0[1] + t * (P1[1] - P0[1]))
                            z_hit = float(P0[2] + t * (P1[2] - P0[2]))
                        else:
                            # Points are at same x, use the one closer to x=0
                            if abs(x0) < abs(x1):
                                y_hit = float(P0[1])
                                z_hit = float(P0[2])
                            else:
                                y_hit = float(P1[1])
                                z_hit = float(P1[2])
                        
                        hit_point = np.array([0.0, y_hit, z_hit], float)
                        break
                
                # If no crossing found, use the roof point closest to x=0
                if hit_point is None:
                    Pmin = min(roof_pts, key=lambda p: abs(float(p[0])))
                    y_min = float(Pmin[1])
                    z_min = float(Pmin[2])
                    hit_point = np.array([0.0, y_min, z_min], float)
                
                # Use the exact hit point as the start of the wall drop
                y0 = float(clamp_inside(hit_point[1], 0.0, B, eps=1e-6))
                z0 = float(clamp_inside(hit_point[2], 0.0, D, eps=1e-6))
                P_top = np.array([0.0, y0, z0], float)
                
                # Drop down green face (x=0) at angle theta: from P_top to bottom edge
                # In y-z plane: z = z0 - (y-y0)*tan(theta)  [going from y0 away from end wall, towards y=B]
                # To reach z=0: y_end = y0 + z0/tan(theta)  [moving towards y=B, away from end wall]
                if tan_t < 1e-9:
                    y_end = y0  # almost vertical
                else:
                    y_end = y0 + (z0 / tan_t)  # move towards y=B, away from end wall
                
                # Clamp y_end to stay within beam [0, B]
                y_end = float(clamp_inside(y_end, 0.0, B, eps=1e-6))
                z_end = float(max(0.0, z0 - (y_end - y0) * tan_t))
                
                P_bot = np.array([0.0, y_end, z_end], float)
                
                # Continue back up at the same angle, still moving away from end wall (toward y=B)
                # From P_bot (0, y_end, z_end) go up at angle theta
                # z = z_end + (y - y_end)*tan(theta), moving toward y=B
                # To reach z=D: y_up = y_end + (D - z_end)/tan(theta)
                if tan_t < 1e-9:
                    y_up = y_end  # almost vertical
                else:
                    y_up = y_end + ((D - z_end) / tan_t)  # continue toward y=B, away from end wall
                
                # Clamp y_up to stay within beam [0, B]
                y_up = float(clamp_inside(y_up, 0.0, B, eps=1e-6))
                z_up = float(min(D, z_end + (y_up - y_end) * tan_t))
                
                P_up = np.array([0.0, y_up, z_up], float)
                
                # Add the angled drop and rise on green face (x=0) - directly linked to roof crack
                # First segment: down from roof to bottom
                wall_drops.append(([P_top, P_bot], "side"))
                # Second segment: back up from bottom
                wall_drops.append(([P_bot, P_up], "side"))
                
                # Extend back onto roof at the same angle magnitude but away from end wall
                # The roof crack follows s(x) = s0 + k*x, so we continue from x=0
                # Find where we are in the s parameter space when we hit x=0
                # On the roof edge at x=0, y determines s: s = y (since roof is s_mod < B)
                s_at_x0 = float(y_up)  # On roof, s_mod = y
                
                # Use the same angle magnitude (abs(k_slope)) but ensure direction is away from end wall
                # Since we're at y_up (away from y=0), we want to continue increasing y (positive direction)
                # So use positive k_slope magnitude
                k_extend = abs(k_slope)  # Use absolute value to move away from end wall
                
                # Continue the roof crack by sampling x values from 0 to L (BTR/BTL edge)
                # Use k_extend to continue: s(x) = s_at_x0 + k_extend * x (moving away from end wall)
                # Sample points to extend the roof crack all the way to x=L
                n_roof_extend = 100
                x_extend = np.linspace(epsx, L - epsx, n_roof_extend)  # Extend all the way to back edge
                roof_extend_points = []
                
                for x_ext in x_extend:
                    s_ext = s_at_x0 + k_extend * x_ext  # Positive k ensures movement away from end wall
                    P_roof, face_roof = surface_point(x_ext, s_ext, B, D)
                    if face_roof == 'roof':
                        roof_extend_points.append(P_roof)
                    else:
                        # If we've left the roof, we've reached the edge - find the intersection
                        # The last roof point should be close to the edge
                        if len(roof_extend_points) > 0:
                            break
                
                # Ensure we reach the back edge (x=L)
                # Find the last point and extend it to x=L if needed
                if len(roof_extend_points) >= 2:
                    last_roof_pt = roof_extend_points[-1]
                    x_last = float(last_roof_pt[0])
                    
                    # If we haven't reached x=L, add a point at the back edge
                    if x_last < L - epsx:
                        # Interpolate to find y at x=L
                        if len(roof_extend_points) >= 2:
                            P0 = roof_extend_points[-2]
                            P1 = roof_extend_points[-1]
                            x0, x1 = float(P0[0]), float(P1[0])
                            if abs(x1 - x0) > 1e-12:
                                t = (L - epsx - x0) / (x1 - x0)
                                t = float(np.clip(t, 0.0, 1.0))
                                y_edge = float(P0[1] + t * (P1[1] - P0[1]))
                                y_edge = float(clamp_inside(y_edge, 0.0, B, eps=1e-6))
                            else:
                                y_edge = float(clamp_inside(float(P1[1]), 0.0, B, eps=1e-6))
                        else:
                            y_edge = float(clamp_inside(float(last_roof_pt[1]), 0.0, B, eps=1e-6))
                        
                        P_edge = np.array([L - epsx, y_edge, D], float)
                        roof_extend_points.append(P_edge)
                
                if len(roof_extend_points) >= 2:
                    # Create roof continuation segment starting from P_up (projected to roof)
                    P_roof_start = np.array([0.0, y_up, D], float)  # Start at roof edge where we came up
                    roof_segment = [P_roof_start] + roof_extend_points
                    wall_drops.append((roof_segment, "roof"))
                    
                    # Extend back to the top of green wall using the same angle as first roof cracks (k_slope)
                    # Start from the back edge (last point of roof extension)
                    P_back_edge = roof_extend_points[-1]
                    x_back = float(P_back_edge[0])
                    y_back = float(P_back_edge[1])
                    
                    # Use original k_slope (which may be negative) to go back toward x=0
                    # s(x) = s_back + k_slope * (x - x_back)
                    # At x=L, s = y_back (on roof, s = y)
                    s_at_back = float(y_back)
                    
                    # Sample x values going back from L to 0
                    n_roof_return = 100
                    x_return = np.linspace(L - epsx, epsx, n_roof_return)  # From back edge to front edge
                    roof_return_points = []
                    
                    for x_ret in x_return:
                        # Use original k_slope to go back (negative k_slope will make it go back)
                        s_ret = s_at_back + k_slope * (x_ret - x_back)
                        P_roof_ret, face_roof_ret = surface_point(x_ret, s_ret, B, D)
                        if face_roof_ret == 'roof':
                            roof_return_points.append(P_roof_ret)
                        else:
                            # If we've left the roof, we've reached the edge
                            if len(roof_return_points) > 0:
                                break
                    
                    # Ensure we reach the front edge (x=0)
                    if len(roof_return_points) >= 2:
                        last_return_pt = roof_return_points[-1]
                        x_last_ret = float(last_return_pt[0])
                        
                        # If we haven't reached x=0, add a point at the front edge
                        if x_last_ret > epsx:
                            # Interpolate to find y at x=0
                            if len(roof_return_points) >= 2:
                                P0_ret = roof_return_points[-2]
                                P1_ret = roof_return_points[-1]
                                x0_ret, x1_ret = float(P0_ret[0]), float(P1_ret[0])
                                if abs(x1_ret - x0_ret) > 1e-12:
                                    t = (epsx - x0_ret) / (x1_ret - x0_ret)
                                    t = float(np.clip(t, 0.0, 1.0))
                                    y_front = float(P0_ret[1] + t * (P1_ret[1] - P0_ret[1]))
                                    y_front = float(clamp_inside(y_front, 0.0, B, eps=1e-6))
                                else:
                                    y_front = float(clamp_inside(float(P1_ret[1]), 0.0, B, eps=1e-6))
                            else:
                                y_front = float(clamp_inside(float(last_return_pt[1]), 0.0, B, eps=1e-6))
                            
                            P_front_edge = np.array([epsx, y_front, D], float)
                            roof_return_points.append(P_front_edge)
                        
                        # Create roof return segment
                        roof_return_segment = roof_return_points
                        wall_drops.append((roof_return_segment, "roof"))
                        
                        # Add another down segment on green wall from the front edge
                        # Start point is where we hit x=0 on the roof
                        P_top2 = roof_return_points[-1].copy()
                        P_top2[0] = 0.0  # Ensure x=0
                        y0_2 = float(clamp_inside(P_top2[1], 0.0, B, eps=1e-6))
                        z0_2 = float(clamp_inside(P_top2[2], 0.0, D, eps=1e-6))
                        P_top2 = np.array([0.0, y0_2, z0_2], float)
                        
                        # Drop down green face (x=0) at angle theta, away from end wall
                        if tan_t < 1e-9:
                            y_end2 = y0_2  # almost vertical
                        else:
                            y_end2 = y0_2 + (z0_2 / tan_t)  # move towards y=B, away from end wall
                        
                        # Clamp y_end2 to stay within beam [0, B]
                        y_end2 = float(clamp_inside(y_end2, 0.0, B, eps=1e-6))
                        z_end2 = float(max(0.0, z0_2 - (y_end2 - y0_2) * tan_t))
                        
                        P_bot2 = np.array([0.0, y_end2, z_end2], float)
                        
                        # Add the second angled drop on green face (x=0)
                        wall_drops.append(([P_top2, P_bot2], "side"))
            
            segments.extend(wall_drops)
            
            # Plot all segments
            for segment_points, seg_face in segments:
                for j in range(len(segment_points) - 1):
                    plot_seg(segment_points[j], segment_points[j+1], seg_face, crack_lw)

    ax.set_aspect("equal", adjustable="box")
    ax.axis("off")
    ax.margins(0.10)
    return fig


def plot_shear_step1_theta_cracks_3d(
    L_mm: float,
    b_mm: float,
    D_mm: float,
    theta_deg: float = 45.0,
    cam_a: float = -0.65,
    cam_b: float = 0.28,
    n_cracks: int = 3,
    start_t_min: float = 0.10,
    start_t_span: float = 0.06,
    crack_lw: float = 4.0,
    show_cracks: bool = True,
):
    """
    Step 1 Shear diagram: 3D 'unwrapped helix' crack sketch as a pure matplotlib figure.
    
    Uses θ (degrees) as the physical crack angle; internally k = -tan(θ).
    
    Note: Geometry mapping matches torsion app:
      - model_L (X axis) = b_mm (breadth)
      - model_B (Y axis) = L_mm (length) 
      - model_D (Z axis) = D_mm (depth)
    
    Args:
        L_mm: Beam length in mm (maps to model_B, Y axis)
        b_mm: Beam width (breadth) in mm (maps to model_L, X axis)
        D_mm: Beam depth in mm (maps to model_D, Z axis)
        theta_deg: Physical crack angle in degrees (default 45.0)
        cam_a: Camera horizontal rotation parameter (default -0.65)
        cam_b: Camera vertical elevation parameter (default 0.28)
        n_cracks: Number of crack helixes to draw
        start_t_min: Starting position for first crack (normalized 0-1)
        start_t_span: Span between crack starts (normalized 0-1)
        crack_lw: Crack line width
        show_cracks: Whether to show cracks
    
    Returns:
        matplotlib.figure.Figure: The 3D diagram figure
    """
    # Scale mm -> meters so the drawing stays numerically sane
    # Swap L and B to match torsion app mapping:
    # model_L (X) = b_mm, model_B (Y) = L_mm, model_D (Z) = D_mm
    L = float(b_mm) / 1000.0  # model length axis X = breadth
    B = float(L_mm) / 1000.0   # model breadth axis Y = length
    D = float(D_mm) / 1000.0   # model depth axis Z = depth
    
    theta_deg = float(theta_deg)
    k_slope = -math.tan(math.radians(theta_deg))
    
    fig = draw_face_label_debug(
        cam_a=float(cam_a),
        cam_b=float(cam_b),
        L=float(L),
        B=float(B),
        D=float(D),
        fs=9,
        show_corners=False,
        n_cracks=int(n_cracks),
        start_t_min=float(start_t_min),
        start_t_span=float(start_t_span),
        crack_lw=float(crack_lw),
        show_cracks=bool(show_cracks),
        k_slope=float(k_slope),
        s0_min=float(start_t_min),
        theta_deg=float(theta_deg),
    )
    return fig


def _torsion_section_perimeter(L: float, D: float) -> float:
    """Rectangular section perimeter in the x–z plane (breadth L, depth D)."""
    return 2.0 * float(L) + 2.0 * float(D)


def _torsion_xz_from_unwrapped_s(s: float, L: float, D: float) -> tuple[float, float]:
    """
    Map unwrapped perimeter coordinate s onto the section outline in the x–z plane.

    Origin s = 0 at (0, 0); trace: bottom z=0 from x=0→L, far vertical x=L z=0→D,
    top z=D from x=L→0, near vertical x=0 z=D→0. Period P = 2L + 2D.
    """
    L = float(L)
    D = float(D)
    P = _torsion_section_perimeter(L, D)
    u = float(s) % P
    if u < 0:
        u += P
    if u < L:
        return u, 0.0
    u -= L
    if u < D:
        return L, u
    u -= L
    if u < L:
        return L - u, D
    u -= L
    return 0.0, D - u


def _torsion_on_visible_skin(
    x: float,
    y: float,
    z: float,
    L: float,
    B: float,
    D: float,
    tol: float,
) -> bool:
    """Point on union of drawn faces: roof z=D, end y=0, near lateral x=0."""
    if (
        abs(z - D) <= tol
        and -tol <= x <= L + tol
        and -tol <= y <= B + tol
    ):
        return True
    if (
        abs(y) <= tol
        and -tol <= x <= L + tol
        and -tol <= z <= D + tol
    ):
        return True
    if (
        abs(x) <= tol
        and -tol <= y <= B + tol
        and -tol <= z <= D + tol
    ):
        return True
    return False


def _bisect_first_visible_y(
    y_a: float,
    y_b: float,
    vis_at,
    *,
    max_iter: int = 56,
) -> float:
    """
    Assume vis_at(y_a) is False and vis_at(y_b) is True (or y_a already visible).
    Return the infimum y in [y_a, y_b] where the band becomes visible — i.e. the
    true left boundary of a visible run (face edge / occlusion boundary).
    """
    if vis_at(y_a):
        return float(y_a)
    if not vis_at(y_b):
        return float(y_b)
    lo, hi = float(y_a), float(y_b)
    for _ in range(max_iter):
        mid = 0.5 * (lo + hi)
        if vis_at(mid):
            hi = mid
        else:
            lo = mid
    return float(hi)


def _bisect_last_visible_y(
    y_a: float,
    y_b: float,
    vis_at,
    *,
    max_iter: int = 56,
) -> float:
    """
    Assume vis_at(y_a) is True and vis_at(y_b) is False.
    Return the supremum y in [y_a, y_b] where the band stays visible — i.e. the
    true right boundary of a visible run.
    """
    if vis_at(y_b):
        return float(y_b)
    if not vis_at(y_a):
        return float(y_a)
    lo, hi = float(y_a), float(y_b)
    for _ in range(max_iter):
        mid = 0.5 * (lo + hi)
        if vis_at(mid):
            lo = mid
        else:
            hi = mid
    return float(lo)


def _torsion_band_projected_polyline(
    L: float,
    B: float,
    D: float,
    c: float,
    m: float,
    cam_a: float,
    cam_b: float,
    *,
    n_samples: int = 520,
    stylize_strength: float = 1.0,
    band_phase: float = 0.0,
    end_trim_frac: float = 0.0,
) -> tuple[list[float | None], list[float | None]]:
    """
    One developed-surface band: unwrapped law s = m*y + c (y = beam length),
    mapped to skin (x,z) = f(s mod P), kept only where the union of visible
    faces is hit. Endpoints of each visible run are refined by bisection to the
    exact visibility boundary (no inset from discrete sampling). None breaks
    runs across hidden bottom/far faces only (not at face changes). A tiny,
    deterministic in-plane jitter is applied to interior points only so traces
    read as cracks while preserving edge hits and wrapped continuity.
    """
    B = float(B)
    y0 = min(max(0.0, float(end_trim_frac)) * B, 0.08 * B)
    ys = np.linspace(y0, B, int(max(48, n_samples)))
    tol = max(1e-12, min(L, D, B if B > 1e-12 else L) * 6e-6)

    def vis_at(yv: float) -> bool:
        s_lin = m * float(yv) + float(c)
        x, z = _torsion_xz_from_unwrapped_s(s_lin, L, D)
        return _torsion_on_visible_skin(x, float(yv), z, L, B, D, tol)

    def proj_y(yv: float) -> tuple[float, float]:
        s_lin = m * float(yv) + float(c)
        x, z = _torsion_xz_from_unwrapped_s(s_lin, L, D)
        p2 = proj(np.array([x, float(yv), z], dtype=float), a=cam_a, b=cam_b)
        return float(p2[0]), float(p2[1])

    vis = np.array([vis_at(float(y)) for y in ys], dtype=bool)
    runs: list[tuple[int, int]] = []
    k = 0
    n = len(ys)
    while k < n:
        if not vis[k]:
            k += 1
            continue
        k0 = k
        while k + 1 < n and vis[k + 1]:
            k += 1
        runs.append((k0, k))
        k += 1

    ydup = max(1e-12, B * 1e-10)
    crack_jitter_amp = min(L, D) * 0.0062 * max(0.0, float(stylize_strength))

    xs_out: list[float | None] = []
    ys_out: list[float | None] = []
    for ri, (i, j) in enumerate(runs):
        # Refined span along beam axis (exact visibility boundaries).
        if i > 0:
            y_left = _bisect_first_visible_y(float(ys[i - 1]), float(ys[i]), vis_at)
        else:
            y_left = 0.0 if vis_at(0.0) else _bisect_first_visible_y(0.0, float(ys[0]), vis_at)

        if j + 1 < n:
            y_right = _bisect_last_visible_y(float(ys[j]), float(ys[j + 1]), vis_at)
        else:
            y_right = B if vis_at(B) else _bisect_last_visible_y(float(ys[j]), B, vis_at)

        if y_right < y_left:
            y_left, y_right = y_right, y_left

        y_seq: list[float] = [y_left]
        for idx in range(i, j + 1):
            yy = float(ys[idx])
            if yy > y_left + ydup and yy < y_right - ydup:
                if not y_seq or abs(yy - y_seq[-1]) > ydup:
                    y_seq.append(yy)
        if not y_seq or abs(y_right - y_seq[-1]) > ydup:
            y_seq.append(y_right)
        else:
            y_seq[-1] = y_right

        merged: list[float] = []
        for yy in y_seq:
            if not merged or abs(yy - merged[-1]) > ydup * 0.5:
                merged.append(yy)
            else:
                merged[-1] = yy

        run_xy: list[tuple[float, float]] = []
        for yy in merged:
            run_xy.append(proj_y(yy))

        if len(run_xy) >= 3 and crack_jitter_amp > 1e-12:
            # Cumulative arclength lets jitter follow local line direction.
            s_acc = [0.0]
            for kk in range(1, len(run_xy)):
                dx = run_xy[kk][0] - run_xy[kk - 1][0]
                dy = run_xy[kk][1] - run_xy[kk - 1][1]
                s_acc.append(s_acc[-1] + math.hypot(dx, dy))
            s_tot = max(s_acc[-1], 1e-12)
            stylized: list[tuple[float, float]] = [run_xy[0]]
            for kk in range(1, len(run_xy) - 1):
                x0, y0 = run_xy[kk]
                x_prev, y_prev = run_xy[kk - 1]
                x_next, y_next = run_xy[kk + 1]
                tx = x_next - x_prev
                ty = y_next - y_prev
                lt = math.hypot(tx, ty)
                if lt < 1e-12:
                    stylized.append((x0, y0))
                    continue
                nx = -ty / lt
                ny = tx / lt
                t = s_acc[kk] / s_tot
                # Envelope is zero at both ends to keep exact face-edge endpoints.
                env = math.sin(math.pi * t)
                wav = 0.58 * math.sin(2.0 * math.pi * (1.12 * t + 0.17 * band_phase))
                wav += 0.34 * math.sin(2.0 * math.pi * (2.85 * t + 0.31 * band_phase + 0.18))
                wav += 0.18 * math.sin(2.0 * math.pi * (4.15 * t + 0.08 * band_phase + 0.41))
                off = crack_jitter_amp * env * wav
                stylized.append((x0 + off * nx, y0 + off * ny))
            stylized.append(run_xy[-1])
            run_xy = stylized

        for uu, vv in run_xy:
            xs_out.append(uu)
            ys_out.append(vv)

        if ri < len(runs) - 1:
            xs_out.append(None)
            ys_out.append(None)

    while xs_out and xs_out[-1] is None:
        xs_out.pop()
        ys_out.pop()
    return xs_out, ys_out


def _torsion_y_interval_near_lateral_leg(
    c: float,
    m: float,
    L: float,
    B: float,
    D: float,
) -> tuple[float, float] | None:
    """y-range with s=m*y+c on fourth perimeter leg [2L+D, P]."""
    if m <= 1e-15:
        return None
    P = _torsion_section_perimeter(L, D)
    y_lo = max(0.0, (2 * L + D - c) / m)
    y_hi = min(float(B), (P - c) / m)
    if y_hi - y_lo <= max(1e-9 * B, 1e-10):
        return None
    return (y_lo, y_hi)


def _torsion_dxz_ds(s: float, L: float, D: float) -> tuple[float, float]:
    """Derivative (dx/ds, dz/ds) along the rectangular perimeter path (unit speed in s)."""
    L = float(L)
    D = float(D)
    P = _torsion_section_perimeter(L, D)
    u = float(s) % P
    if u < 0:
        u += P
    eps = 1e-12
    if u < L - eps:
        return 1.0, 0.0
    if u < L + D - eps:
        return 0.0, 1.0
    if u < 2 * L + D - eps:
        return -1.0, 0.0
    return 0.0, -1.0


def _torsion_theta_marker_on_lateral(
    L: float,
    B: float,
    D: float,
    c_band: float,
    m: float,
    theta_deg: float,
    cam_a: float,
    cam_b: float,
    *,
    y_frac: float = 0.42,
) -> tuple[list[go.Scatter] | None, list[dict] | None]:
    """
    θ on near lateral (x≈0): developed law s = m*y + c_band; axis vs crack tangent.
    """
    iv = _torsion_y_interval_near_lateral_leg(c_band, m, L, B, D)
    if iv is None:
        return None, None
    y1, y2 = iv
    y0 = y1 + (y2 - y1) * y_frac
    s = m * y0 + c_band
    x, z = _torsion_xz_from_unwrapped_s(s, L, D)
    if abs(x) > max(1e-6, 2e-4 * L):
        return None, None
    dz_dy = -m
    len_ref = min(B, D) * 0.165
    p0 = np.array([0.0, y0, z], dtype=float)
    p_axis = np.array([0.0, y0 + len_ref, z], dtype=float)
    p_crack = np.array([0.0, y0 + len_ref, z + len_ref * dz_dy], dtype=float)

    v0 = proj(p0, a=cam_a, b=cam_b)
    va = proj(p_axis, a=cam_a, b=cam_b)
    vc = proj(p_crack, a=cam_a, b=cam_b)
    ex = np.array([va[0] - v0[0], va[1] - v0[1]], dtype=float)
    ec = np.array([vc[0] - v0[0], vc[1] - v0[1]], dtype=float)
    le = math.hypot(ex[0], ex[1])
    lc = math.hypot(ec[0], ec[1])
    if le < 1e-12 or lc < 1e-12:
        return None, None
    ex /= le
    ec /= lc
    ang0 = math.atan2(ex[1], ex[0])
    ang1 = math.atan2(ec[1], ec[0])
    d_ang = ang1 - ang0
    while d_ang <= -math.pi:
        d_ang += 2 * math.pi
    while d_ang > math.pi:
        d_ang -= 2 * math.pi
    if abs(d_ang) < 0.04:
        return None, None

    r_arc = min(B, D) * 0.095
    n_arc = 40
    arc_x: list[float] = []
    arc_y: list[float] = []
    for i in range(n_arc + 1):
        t = i / n_arc
        ang = ang0 + t * d_ang
        arc_x.append(float(v0[0]) + r_arc * math.cos(ang))
        arc_y.append(float(v0[1]) + r_arc * math.sin(ang))

    traces = [
        go.Scatter(
            x=[float(v0[0]), float(va[0])],
            y=[float(v0[1]), float(va[1])],
            mode="lines",
            line=dict(width=1.45, color="rgba(45,45,45,0.82)", dash="dot"),
            hoverinfo="skip",
            showlegend=False,
        ),
        go.Scatter(
            x=[float(v0[0]), float(vc[0])],
            y=[float(v0[1]), float(vc[1])],
            mode="lines",
            line=dict(width=1.55, color="rgba(25,25,25,0.92)"),
            hoverinfo="skip",
            showlegend=False,
        ),
        go.Scatter(
            x=arc_x,
            y=arc_y,
            mode="lines",
            line=dict(width=1.5, color="rgba(30,30,30,0.9)"),
            hoverinfo="skip",
            showlegend=False,
        ),
    ]
    bis = ang0 + 0.5 * d_ang
    off = r_arc * 1.75
    lx = float(v0[0]) + off * math.cos(bis)
    ly = float(v0[1]) + off * math.sin(bis)
    ann = [
        dict(
            x=lx,
            y=ly,
            text="θ",
            showarrow=False,
            font=dict(size=15, color="rgba(20,20,20,0.98)"),
            xref="x",
            yref="y",
        )
    ]
    return traces, ann


def _torsion_theta_marker_on_bottom_edge(
    L: float,
    B: float,
    D: float,
    c_band: float,
    m: float,
    cam_a: float,
    cam_b: float,
    *,
    subdued: bool = False,
) -> tuple[list[go.Scatter] | None, list[dict] | None]:
    """
    θ at the projected corner wedge where the representative crack meets the
    bottom outline: 3D vertex (0, y_edge, 0) with s = m*y + c = P (wrap onto
    bottom at x=0). Edge ray = beam axis along the visible bottom front (x=0,
    z=0, +y); crack ray = bottom-face tangent (dx/dy=m, +y). Arc and label sit
    in the acute wedge in projection (engineering angle style).
    """
    if m <= 1e-15:
        return None, None
    P = _torsion_section_perimeter(L, D)
    y_raw = (P - c_band) / m
    # Clamp to visible bottom front edge so θ still draws if (P−c)/m is off-span.
    y_edge = min(float(B), max(0.0, float(y_raw)))
    len_base = max(min(B, D) * 0.13, 0.07 * min(B, D), 1e-4)
    span_up = max(0.0, float(B) - y_edge)
    span_dn = max(0.0, y_edge)
    # Avoid degenerate rays when y_edge sits at an end of the beam (was hiding θ).
    if span_up >= span_dn:
        h_edge = min(len_base, max(1e-5, span_up) * 0.92)
        p0 = np.array([0.0, y_edge, 0.0], dtype=float)
        p_edge = np.array([0.0, y_edge + h_edge, 0.0], dtype=float)
        h_c = min(len_base, max(1e-5, span_up) * 0.92)
        p_crack = np.array([0.78 * h_c * m, y_edge + h_c, 0.0], dtype=float)
    else:
        h_edge = min(len_base, max(1e-5, span_dn) * 0.92)
        p0 = np.array([0.0, y_edge, 0.0], dtype=float)
        p_edge = np.array([0.0, y_edge - h_edge, 0.0], dtype=float)
        h_c = min(len_base, max(1e-5, span_dn) * 0.92)
        p_crack = np.array([-0.78 * h_c * m, y_edge - h_c, 0.0], dtype=float)

    v0 = proj(p0, a=cam_a, b=cam_b)
    va = proj(p_edge, a=cam_a, b=cam_b)
    vc = proj(p_crack, a=cam_a, b=cam_b)
    ex = np.array([va[0] - v0[0], va[1] - v0[1]], dtype=float)
    ec = np.array([vc[0] - v0[0], vc[1] - v0[1]], dtype=float)
    le = math.hypot(ex[0], ex[1])
    lc = math.hypot(ec[0], ec[1])
    if le < 1e-12 or lc < 1e-12:
        return None, None
    ex /= le
    ec /= lc
    ang_edge = math.atan2(ex[1], ex[0])
    ang_crack = math.atan2(ec[1], ec[0])
    d_ang = ang_crack - ang_edge
    while d_ang <= -math.pi:
        d_ang += 2 * math.pi
    while d_ang > math.pi:
        d_ang -= 2 * math.pi
    # Smaller (acute) wedge between the two rays in the corner.
    if abs(d_ang) > 0.5 * math.pi + 1e-6:
        d_ang = math.copysign(math.pi - abs(d_ang), d_ang)
    cross_z = ex[0] * ec[1] - ex[1] * ec[0]
    if abs(d_ang) < 0.04:
        # Nearly parallel in projection: still show a readable wedge.
        d_ang = math.copysign(max(0.14, math.radians(10.0)), cross_z if abs(cross_z) > 1e-9 else 1.0)

    ang0 = ang_edge
    r_arc = min(B, D) * (0.078 if subdued else 0.09)
    bis = ang0 + 0.5 * d_ang
    off = r_arc * (1.36 if subdued else 1.42)
    lx = float(v0[0]) + off * math.cos(bis)
    ly = float(v0[1]) + off * math.sin(bis)
    # Other side of the representative crack line (reflect across ray along ec).
    wx, wy = lx - float(v0[0]), ly - float(v0[1])
    proj_len = wx * ec[0] + wy * ec[1]
    lx = float(v0[0]) + 2.0 * proj_len * ec[0] - wx
    ly = float(v0[1]) + 2.0 * proj_len * ec[1] - wy
    # Slight push toward +u (to the right in the figure).
    nudge_u = min(B, D) * (0.032 if subdued else 0.038)
    lx += nudge_u
    # θ label: farther right and lower (projection coords: +x right, −y down).
    _scale = min(B, D)
    lx += _scale * (0.118 if subdued else 0.136)
    ly -= _scale * (0.088 if subdued else 0.104)

    tf = 15 if subdued else 20
    # θ only: no arc, edge ray, or crack tick (avoids stray segments at the beam corner).
    traces = [
        go.Scatter(
            x=[lx],
            y=[ly],
            mode="text",
            text=["\u03b8"],
            textposition="middle center",
            textfont=dict(
                size=tf,
                color="rgba(70,70,70,0.95)" if subdued else "rgba(8,8,8,1)",
                family="Arial, DejaVu Sans, sans-serif",
            ),
            hoverinfo="skip",
            showlegend=False,
            cliponaxis=False,
        ),
    ]
    return traces, None


def infer_shear_check6_critical_support_side(state: dict) -> str:
    """
    Heuristic governing support for the local Check 6 transfer sketch (left | right).
    Uses resolved deflection/support type, design section position, or eccentric point-load reactions.
    """
    try:
        from deflection import get_resolved_deflection_support_type

        stype = str(get_resolved_deflection_support_type(state) or "").strip()
    except Exception:
        stype = ""
    if stype == "Cantilever":
        return "left"

    try:
        from state_and_helpers import get_param

        L_mm = float(state.get("L") or get_param("L", 3000.0))
    except Exception:
        L_mm = 3000.0
    span_m = max(L_mm / 1000.0, 1e-6)

    design_source = str(
        state.get("design_actions_source") or state.get("actions_source") or "max"
    ).strip().lower()
    if design_source == "section":
        try:
            x_m = float(state.get("design_section_x_m", 0.0) or 0.0)
        except Exception:
            x_m = 0.0
        return "left" if x_m < 0.5 * span_m else "right"

    case = str(state.get("sfd_case") or state.get("load_case") or "").lower()
    if "from left" in case and "point" in case:
        try:
            from state_and_helpers import get_param

            a_m = float(
                state.get("a_m")
                or state.get("load_a_point")
                or state.get("sfd_a_udl")
                or get_param("a_m", span_m * 0.5)
            )
        except Exception:
            a_m = span_m * 0.5
        a_m = max(0.0, min(a_m, span_m))
        r_left = 1.0 - a_m / span_m
        r_right = a_m / span_m
        return "left" if r_left >= r_right else "right"

    return "left"


def _check6_float(state: dict, key: str, default: float) -> float:
    try:
        v = state.get(key, default)
        if v is None:
            return float(default)
        return float(v)
    except Exception:
        return float(default)


def _check6_clamp_mm(x: float, lo: float, hi: float) -> float:
    return max(lo, min(float(x), hi))


def _check6_build_sfd_params_uls(state: dict) -> tuple[str, float, dict] | None:
    """Rebuild ULS-equivalent params for ``_compute_diagram_arrays`` from shared/session keys."""
    try:
        from state_and_helpers import get_param
    except Exception:
        return None

    mode = str(state.get("sfd_beam_system_mode") or get_param("sfd_beam_system_mode", "Single span"))
    L_m = state.get("sfd_L_m")
    try:
        L_m = float(L_m) if L_m is not None else float(get_param("L", 3000.0)) / 1000.0
    except Exception:
        L_m = float(get_param("L", 3000.0)) / 1000.0
    L_m = max(L_m, 0.1)

    gamma_g = 1.2
    gamma_q = 1.5

    if mode.strip().lower() == "multi-span":
        try:
            n_spans = int(float(state.get("sfd_span_count") or get_param("sfd_span_count", 2) or 2))
        except Exception:
            n_spans = 2
        n_spans = max(2, min(n_spans, 5))
        nodes: list[float] = [0.0]
        for i in range(1, n_spans + 1):
            Li = state.get(f"sfd_span_len_{i}")
            if Li is None:
                Li = get_param(f"sfd_span_len_{i}", None)
            if Li is None:
                Li = max(0.2, L_m / max(n_spans, 1))
            nodes.append(nodes[-1] + max(0.2, float(Li)))
        L_tot = float(nodes[-1])
        types: list[str] = []
        for j in range(1, n_spans + 2):
            tj = state.get(f"sfd_support_type_{j}") or get_param(f"sfd_support_type_{j}", "Pinned")
            types.append(str(tj))

        psi_p = _check6_float(state, "load_psi_point", float(get_param("psi_point", 0.4)))
        n_point = int(_check6_float(state, "sfd_ms_point_count", 2.0))
        point_loads: list[dict] = []
        for i in range(1, max(0, n_point) + 1):
            G = _check6_float(state, f"load_ms_G_{i}", 30.0)
            Q = _check6_float(state, f"load_ms_Q_{i}", 20.0)
            x_i = _check6_clamp_mm(
                _check6_float(state, f"load_ms_x_{i}", L_tot * 0.25 * i),
                0.0,
                L_tot,
            )
            point_loads.append(
                {"x_m": x_i, "P_kN": max(1e-6, gamma_g * G + gamma_q * Q)}
            )

        n_udl = int(_check6_float(state, "sfd_ms_udl_count", 1.0))
        udl_loads: list[dict] = []
        for i in range(1, max(0, n_udl) + 1):
            g_i = _check6_float(state, f"load_ms_g_{i}", 5.0)
            q_i = _check6_float(state, f"load_ms_q_{i}", 3.0)
            x0 = _check6_float(state, f"load_ms_x0_{i}", 0.0)
            x1 = _check6_float(state, f"load_ms_x1_{i}", L_tot)
            xa, xb = (min(x0, x1), max(x0, x1))
            xa = _check6_clamp_mm(xa, 0.0, L_tot)
            xb = _check6_clamp_mm(xb, 0.0, L_tot)
            if xb > xa + 1e-9:
                udl_loads.append(
                    {
                        "x_start_m": xa,
                        "x_end_m": xb,
                        "w_kN_per_m": max(0.0, gamma_g * g_i + gamma_q * q_i),
                    }
                )

        params = {
            "beam_system_mode": "Multi-span",
            "node_positions_m": nodes,
            "support_types": types,
            "point_loads": point_loads,
            "udl_loads": udl_loads,
        }
        return "Multi-span continuous beam", L_tot, params

    case = str(
        state.get("load_case")
        or state.get("sfd_case")
        or get_param("sfd_case", "Simple beam – UDL over entire span")
    ).strip()
    if "Multi-span" not in case:
        case = case.replace("-", "–")
    sc = str(
        state.get("sfd_support_condition")
        or get_param("sfd_support_condition", "Simply supported")
    ).replace("-", "–")
    params: dict[str, object] = {"support_condition": sc, "beam_system_mode": "Single span"}

    if case in (
        "Simple beam – UDL over entire span",
        "Simple beam – partial UDL from left (length a)",
        "Cantilever – UDL over entire span",
    ):
        wu = state.get("w_uls_kNm_per_m")
        try:
            wu = float(wu) if wu is not None else None
        except Exception:
            wu = None
        if wu is None or wu <= 0:
            g = float(get_param("g_udl_kNm_per_m", 0.0) or 0.0)
            q = float(get_param("q_udl_kNm_per_m", 0.0) or 0.0)
            wu = gamma_g * g + gamma_q * q
        params["w"] = max(float(wu), 1e-6)
        if case == "Simple beam – partial UDL from left (length a)":
            params["a_udl"] = _check6_clamp_mm(
                _check6_float(state, "sfd_a_udl", L_m * 0.5),
                0.0,
                L_m,
            )
    elif case == "Simple beam – point load at centre":
        params["P"] = max(
            1e-6,
            _check6_float(state, "P_uls_kN", float(get_param("P_uls_kN", 100.0) or 100.0)),
        )
    elif case == "Simple beam – point load at distance a from left":
        params["P"] = max(
            1e-6,
            _check6_float(state, "P_uls_kN", float(get_param("P_uls_kN", 100.0) or 100.0)),
        )
        params["a"] = _check6_clamp_mm(
            _check6_float(state, "load_a_point", _check6_float(state, "a_m", L_m / 3.0)),
            0.0,
            L_m,
        )
    elif case == "Cantilever – point load at free end":
        params["P"] = max(
            1e-6,
            _check6_float(state, "P_uls_kN", float(get_param("P_uls_kN", 80.0) or 80.0)),
        )
    elif case == "Cantilever – point load at distance a from fixed end":
        params["P"] = max(
            1e-6,
            _check6_float(state, "P_uls_kN", float(get_param("P_uls_kN", 80.0) or 80.0)),
        )
        params["a_cant"] = _check6_clamp_mm(
            _check6_float(state, "sfd_a_cant", float(get_param("a_cant_m", L_m * 0.5))),
            0.0,
            L_m,
        )
    elif case == "Overhanging beam – right overhang with point load at free end":
        L_main = _check6_float(state, "sfd_L_m", L_m)
        params["L_main"] = max(0.1, L_main)
        params["a_overhang"] = max(
            0.0,
            _check6_float(state, "sfd_a_overhang", float(get_param("a_overhang_m", 2.0))),
        )
        params["P"] = max(
            1e-6,
            _check6_float(state, "P_uls_kN", float(get_param("P_uls_kN", 100.0) or 100.0)),
        )
    elif case in ("Simple beam – multiple point loads", "Cantilever – multiple point loads"):
        return None
    else:
        _g = float(get_param("g_udl_kNm_per_m", 0.0) or 0.0)
        _q = float(get_param("q_udl_kNm_per_m", 0.0) or 0.0)
        params.setdefault("w", max(1e-6, gamma_g * _g + gamma_q * _q))

    return case, L_m, params


def _check6_govern_from_sfd(
    state: dict, *, d_mm: float
) -> tuple[str, str, dict] | None:
    """
    Returns (critical_side, support_draw_kind, meta) using the same SFD backend as the beam diagrams,
    or None if analysis cannot be run.
    critical_side: "left" | "right" | "internal"
    """
    try:
        from sfd_bmd_page import _compute_diagram_arrays
    except Exception:
        return None

    built = _check6_build_sfd_params_uls(state)
    if not built:
        return None
    case, L_m, params = built
    try:
        x_arr, V_arr, _M_arr, blen, meta = _compute_diagram_arrays(case, L_m, params)
    except Exception:
        return None

    x = np.asarray(x_arr, dtype=float)
    V = np.asarray(V_arr, dtype=float)
    if x.size < 2 or not math.isfinite(blen) or blen <= 0:
        return None

    d_m = max(float(d_mm), 1.0) / 1000.0
    probe = max(0.05 * blen, min(2.0 * d_m, 0.22 * blen))

    sup_x = [float(s) for s in (meta.get("support_positions") or [0.0, blen])]
    sup_x = sorted({max(0.0, min(blen, sx)) for sx in sup_x})

    if len(sup_x) <= 1 or case.startswith("Cantilever"):
        kind = _check6_support_kind_at_index(
            str(params.get("support_condition", "")),
            sup_x,
            [],
            0,
        )
        return "left", kind, meta

    if str(params.get("beam_system_mode")) == "Multi-span" and len(sup_x) >= 3:
        best_i = 0
        best_v = -1.0
        for i, xs in enumerate(sup_x):
            lo = max(0.0, xs - probe)
            hi = min(blen, xs + probe)
            mask = (x >= lo) & (x <= hi)
            vv = float(np.max(np.abs(V[mask]))) if np.any(mask) else 0.0
            if vv > best_v + 1e-9:
                best_v = vv
                best_i = i
        types = [str(t) for t in (meta.get("support_types") or [])]
        kind = _check6_support_kind_at_index("", sup_x, types, best_i)
        if best_i == 0:
            side = "left"
        elif best_i == len(sup_x) - 1:
            side = "right"
        else:
            side = "internal"
        meta = {**meta, "_check6_critical_support_index": best_i, "_check6_support_x_m": sup_x[best_i]}
        return side, kind, meta

    left_mask = x <= probe + 1e-9
    right_mask = x >= blen - probe - 1e-9
    v_left = float(np.max(np.abs(V[left_mask]))) if np.any(left_mask) else 0.0
    v_right = float(np.max(np.abs(V[right_mask]))) if np.any(right_mask) else 0.0
    if v_right > v_left + 1e-6:
        idx = len(sup_x) - 1
    else:
        idx = 0
    types = [str(t) for t in (meta.get("support_types") or [])]
    kind = _check6_support_kind_at_index(
        str(params.get("support_condition", "")),
        sup_x,
        types,
        idx,
    )
    side = "right" if idx > 0 else "left"
    return side, kind, meta


def _check6_norm_support_token(raw: str) -> str:
    return str(raw or "").strip().lower()


def _check6_support_kind_at_index(
    support_condition: str,
    support_x: list[float],
    support_types: list[str],
    index: int,
) -> str:
    """Return draw kind: pinned | roller | fixed | internal."""
    if support_types and len(support_types) == len(support_x) and 0 <= index < len(support_types):
        t = _check6_norm_support_token(support_types[index])
        if t == "fixed":
            return "fixed"
        if t == "roller":
            return "roller"
        if t == "pinned":
            return "pinned"
        return "pinned"

    sc = str(support_condition or "").replace("-", "–")
    end_right = index > 0 and index == len(support_x) - 1
    end_left = index == 0

    if sc == "Fixed–Free":
        return "fixed" if end_left else "free"
    if sc == "Simply supported":
        if end_left:
            return "pinned"
        if end_right:
            return "roller"
    if sc == "Pinned–Pinned":
        return "pinned"
    if sc == "Fixed–Pinned":
        return "fixed" if end_left else "pinned"
    if sc == "Pinned–Fixed":
        return "pinned" if end_left else "fixed"
    if sc == "Fixed–Fixed":
        return "fixed"

    if len(support_x) >= 3 and 0 < index < len(support_x) - 1:
        return "internal"

    return "pinned" if end_left else "roller"


def _check6_support_kind_match_session_visual(state: dict, side: str) -> str:
    """
    Pinned / roller / fixed / free to match ``shear_visuals`` side-view / behaviour supports
    (canonical deflection + load case), not a loose SFD string mismatch.
    """
    sn = str(side or "left").strip().lower()
    if sn == "internal":
        return "internal"
    try:
        from shear_visuals import (
            _get_canonical_shear_visual_loading_state,
            _get_canonical_shear_visual_support_state,
        )

        canon = _get_canonical_shear_visual_support_state(
            _get_canonical_shear_visual_loading_state()
        )
    except Exception:
        canon = "simply_supported"
    if canon == "cantilever":
        return "fixed" if sn == "left" else "free"
    if canon == "pinned_pinned":
        return "pinned"
    if sn == "left":
        return "pinned"
    if sn == "right":
        return "roller"
    return "pinned"


def resolve_check6_support_transfer_context(state: dict, *, d_mm: float) -> dict:
    """
    Governing support for Check 6 sketch: side, icon kind, optional SFD metadata.
    Draw kind matches session-wide shear visuals (simply supported → pinned left / roller right).
    """
    g = _check6_govern_from_sfd(state, d_mm=float(d_mm))
    if g:
        side, kind, meta = g
        if str(side) == "internal":
            kind = "internal"
        else:
            kind = _check6_support_kind_match_session_visual(state, side)
        return {
            "critical_support_side": side,
            "support_draw_kind": kind,
            "sfd_meta": meta,
        }
    side = infer_shear_check6_critical_support_side(state)
    kind = _check6_support_kind_match_session_visual(state, str(side))
    return {
        "critical_support_side": side,
        "support_draw_kind": kind,
        "sfd_meta": {},
    }


def _check6_stirrup_xs_mm(*, L_seg_mm: float, s_mm: float, max_lines: int = 14) -> list[float]:
    s = max(float(s_mm), 1.0)
    L = max(float(L_seg_mm), s * 0.5)
    xs: list[float] = []
    x = 0.5 * s
    while x <= L - 1e-6 and len(xs) < max_lines:
        xs.append(x)
        x += s
    return xs


def _check6_crack_ray_hits_vertical_stirrup(
    xd: float,
    x0: float,
    y0: float,
    ux: float,
    uy: float,
    y_stirr_bot: float,
    y_stirr_top: float,
    t_max: float,
) -> bool:
    """True if the crack ray from (x0,y0) with unit-ish (ux,uy) crosses x=xd within stirrup height."""
    if abs(ux) < 1e-9:
        return False
    t = (float(xd) - float(x0)) / float(ux)
    if t < -1e-5 or t > float(t_max) + 1e-4:
        return False
    yi = float(y0) + t * float(uy)
    y_lo = min(float(y_stirr_bot), float(y_stirr_top))
    y_hi = max(float(y_stirr_bot), float(y_stirr_top))
    return y_lo - 1e-3 <= yi <= y_hi + 1e-3


def _check6_shear_cage_y_range_mm(
    *,
    layout: dict | None,
    shape_kind: str,
    dims: dict,
    reo: dict,
    D: float,
    lig_d: float,
    lig_legs: int,
) -> tuple[float, float]:
    reo_pts = (layout or {}).get("reo_points") if layout else None
    cover_bot = float(reo.get("cover_bot", 40.0))
    cover_top = float(reo.get("cover_top", 40.0))
    cover_side = float(reo.get("cover_side", min(cover_top, cover_bot)))
    if shape_kind == "RECT":
        b = float(dims.get("b", 300.0))
        sl = compute_shear_reo_layout_pure(
            b,
            D,
            cover_bot,
            cover_top,
            cover_side,
            float(lig_d),
            int(max(0, lig_legs)),
            list(reo_pts or []),
        )
        cg = sl.get("cage") or {}
    else:
        cg = (layout or {}).get("cage") or {}
    y0 = float(cg.get("y0", cover_top + 5.0))
    y1 = float(cg.get("y1", D - cover_bot - 5.0))
    if y1 <= y0:
        y0, y1 = cover_top + 5.0, D - cover_bot - 5.0
    return y0, y1


def _check6_draw_support_symbol(
    fig: go.Figure,
    *,
    x_ref: float,
    y_beam_bottom: float,
    D: float,
    kind: str,
    L_seg_mm: float,
) -> tuple[float, float]:
    """
    Draw support at plot x = x_ref (mm, same coords as beam). Styling matches
    ``shear_visuals._add_side_view_pinned_support`` / ``_add_side_view_fixed_support``.
    Returns (y_ground, node_x_display).
    """
    xc = float(x_ref)
    outline = "rgba(35,35,35,1.0)"
    fill_tri = "rgba(35,35,35,0.12)"
    ground_col = "rgba(80,80,80,0.85)"
    fill_wall = "rgba(45,45,45,0.15)"
    # Smaller than full shear side-view proportions so the sketch stays compact.
    _s6 = 0.68
    tri_depth = max(0.28 * D, 80.0) * _s6
    tri_hw = max(0.03 * float(L_seg_mm), 90.0) * _s6
    y_ground = y_beam_bottom - tri_depth - 0.08 * D

    k = _check6_norm_support_token(kind)

    if k == "free":
        tick = max(0.02 * D, 5.0) * _s6
        fig.add_shape(
            type="line",
            x0=xc - tick,
            y0=y_beam_bottom,
            x1=xc + tick,
            y1=y_beam_bottom,
            line=dict(color=outline, width=1.4),
        )
        return y_beam_bottom - 0.06 * D, xc

    if k == "fixed":
        hatch_dx = max(0.02 * float(L_seg_mm), 50.0) * _s6
        y_min = y_beam_bottom - 0.55 * D
        y_max = y_beam_bottom + 1.55 * D
        fig.add_shape(
            type="line",
            x0=xc,
            y0=y_min,
            x1=xc,
            y1=y_max,
            line=dict(color=outline, width=5),
        )
        for frac in (0.08, 0.28, 0.48, 0.68, 0.88):
            y_val = y_min + frac * (y_max - y_min)
            fig.add_shape(
                type="line",
                x0=xc - hatch_dx,
                y0=y_val + 0.10 * D,
                x1=xc,
                y1=y_val - 0.04 * D,
                line=dict(color="rgba(80,80,80,0.82)", width=1.0),
            )
        return y_ground, xc

    if k == "internal":
        pad_w = tri_hw * 1.85
        rx0 = x_ref - pad_w
        rx1 = x_ref + pad_w
        fig.add_shape(
            type="rect",
            x0=min(rx0, rx1),
            y0=y_ground - 0.04 * D,
            x1=max(rx0, rx1),
            y1=y_beam_bottom,
            line=dict(color="rgba(31,42,68,0)", width=0),
            fillcolor=fill_wall,
        )
        a0, a1 = x_ref - pad_w * 0.55, x_ref
        fig.add_shape(
            type="line",
            x0=min(a0, a1),
            y0=y_beam_bottom,
            x1=max(a0, a1),
            y1=y_ground - 0.02 * D,
            line=dict(color=outline, width=1.2),
        )
        b0, b1 = x_ref + pad_w * 0.55, x_ref
        fig.add_shape(
            type="line",
            x0=min(b0, b1),
            y0=y_beam_bottom,
            x1=max(b0, b1),
            y1=y_ground - 0.02 * D,
            line=dict(color=outline, width=1.2),
        )
        h0, h1 = x_ref - pad_w * 1.1, x_ref + pad_w * 1.1
        fig.add_shape(
            type="line",
            x0=min(h0, h1),
            y0=y_ground - 0.02 * D,
            x1=max(h0, h1),
            y1=y_ground - 0.02 * D,
            line=dict(color=ground_col, width=1.0),
        )
        return y_ground - 0.02 * D, xc

    # pinned / roller: triangle (apex at soffit, base below) — same geometry as side view
    tri = (
        f"M {xc - tri_hw:.4f},{y_beam_bottom - tri_depth:.4f} "
        f"L {xc + tri_hw:.4f},{y_beam_bottom - tri_depth:.4f} "
        f"L {xc:.4f},{y_beam_bottom:.4f} Z"
    )
    fig.add_shape(
        type="path",
        path=tri,
        line=dict(color=outline, width=1.4),
        fillcolor=fill_tri,
    )
    fig.add_shape(
        type="line",
        x0=xc - tri_hw * 1.15,
        y0=y_ground,
        x1=xc + tri_hw * 1.15,
        y1=y_ground,
        line=dict(color=ground_col, width=1.0),
    )
    if k == "roller":
        roller_r = max(0.04 * tri_depth, 28.0)
        cy = y_ground - roller_r * 1.4
        fig.add_shape(
            type="circle",
            xref="x",
            yref="y",
            x0=xc - roller_r,
            y0=cy - roller_r,
            x1=xc + roller_r,
            y1=cy + roller_r,
            line=dict(color=outline, width=1.15),
            fillcolor="rgba(255,255,255,0.55)",
        )
    return y_ground, xc


def _check6_shape_kind_and_dims(layout: dict | None) -> tuple[str, dict]:
    layout = layout or {}
    dims = dict(layout.get("dims") or {})
    sn = str(layout.get("shape_name") or "")
    if sn.startswith("T-Section"):
        return "T", dims
    if sn.startswith("I-Section"):
        return "I", dims
    Dv = float(layout.get("D") or dims.get("D") or 600.0)
    dims.setdefault("b", float(layout.get("b") or 300.0))
    dims.setdefault("D", Dv)
    return "RECT", dims


def _check6_section_inset_polygon_uv(shape_kind: str, dims: dict) -> tuple[list[tuple[float, float]], float]:
    """Section polygon in (u,v): u horizontal, v down from top; returns (points, width_u)."""
    if shape_kind == "T":
        bf = float(dims["bf"])
        tf = float(dims["tf"])
        bw = float(dims["bw"])
        D = float(dims["D"])
        x0 = (bf - bw) / 2.0
        x1 = x0 + bw
        pts = [
            (0.0, 0.0),
            (bf, 0.0),
            (bf, tf),
            (x1, tf),
            (x1, D),
            (x0, D),
            (x0, tf),
            (0.0, tf),
            (0.0, 0.0),
        ]
        return pts, bf
    if shape_kind == "I":
        bf = float(dims["bf"])
        tf = float(dims["tf"])
        tw = float(dims["tw"])
        D = float(dims["D"])
        x0 = (bf - tw) / 2.0
        x1 = x0 + tw
        pts = [
            (0.0, 0.0),
            (bf, 0.0),
            (bf, tf),
            (x1, tf),
            (x1, D - tf),
            (bf, D - tf),
            (bf, D),
            (0.0, D),
            (0.0, D - tf),
            (x0, D - tf),
            (x0, tf),
            (0.0, tf),
            (0.0, 0.0),
        ]
        return pts, bf
    b = float(dims["b"])
    D = float(dims["D"])
    return [(0.0, 0.0), (b, 0.0), (b, D), (0.0, D), (0.0, 0.0)], b


def _check6_y_display(D_mm: float, v_from_top: float) -> float:
    """Map section v (0=top) to display y (0=soffit, D=top)."""
    return float(D_mm) - float(v_from_top)


def _check6_tension_ast_mm2(layout: dict | None, tension_face: str) -> float:
    """Sum tension steel area (mm²) from layout reo_points, else reo counts."""
    pts = (layout or {}).get("reo_points") or []
    s = 0.0
    for p in pts:
        if str(p.get("layer")) != str(tension_face):
            continue
        try:
            db = float(p.get("db", 0.0) or 0.0)
        except (TypeError, ValueError):
            continue
        if db > 0:
            s += math.pi * (db**2) / 4.0
    if s > 1e-6:
        return float(s)
    reo = (layout or {}).get("reo") or {}
    try:
        if tension_face == "bottom":
            n = int(float(reo.get("nb_bot", 0) or 0))
            db = float(reo.get("db_bot", reo.get("db_bot_1", 0.0)) or 0.0)
        else:
            n = int(float(reo.get("nb_top", 0) or 0))
            db = float(reo.get("db_top", reo.get("db_top_1", 0.0)) or 0.0)
    except (TypeError, ValueError):
        n, db = 0, 0.0
    if n > 0 and db > 0:
        return float(n) * math.pi * (db**2) / 4.0
    return 0.0


def _check6_uls_dn_mm(*, fc_mpa: float, b_mm: float, fsy_mpa: float, Ast_mm2: float) -> float:
    """Rectangular stress-block neutral axis depth d_n (mm), same ULS factors as bending tab 1.4."""
    fc = max(float(fc_mpa), 1e-6)
    b = max(float(b_mm), 1e-6)
    fsy = max(float(fsy_mpa), 1e-6)
    Ast = max(float(Ast_mm2), 0.0)
    if Ast <= 1e-6:
        return float("nan")
    alpha2_raw = 0.85 - 0.0015 * fc
    gamma_raw = 0.97 - 0.0025 * fc
    alpha2 = max(0.67, alpha2_raw)
    gamma = max(0.67, gamma_raw)
    T = Ast * fsy
    denom = alpha2 * fc * b * gamma
    if denom <= 1e-12:
        return float("nan")
    return T / denom


def _check6_v_na_from_dn_mm(*, D: float, dn_mm: float, compression_face: str) -> float:
    """Distance from top fibre to NA (mm, v coordinate) from d_n and compression face."""
    Df = max(float(D), 1e-6)
    dn = float(dn_mm)
    if not math.isfinite(dn) or dn <= 0:
        return 0.5 * Df
    dn = max(1e-6, min(dn, Df - 1e-6))
    if str(compression_face) == "bottom":
        return Df - dn
    return dn


def _check6_crack_bezier_setup(
    xa: float,
    ya: float,
    xb: float,
    yb: float,
    *,
    tension_face: str,
    D_mm: float,
    bulge_scale: float = 1.0,
) -> tuple[
    float,
    float,
    float,
    float,
    float,
    float,
    float,
    float,
    float,
    float,
    float,
] | None:
    """
    Cubic geometry for the crack **mean line**: same toe/tip anchors as the θ_v chord, with a mild
    arch toward compression. The jagged black crack and the smooth backbone for the green offset
    both sample this curve; ``bulge_scale`` scales the arch (historical default ≈1.28 → ~0.155 arch).
    """
    bs = max(0.55, min(2.2, float(bulge_scale)))
    arch_scale = 0.155 * (bs / 1.28)
    arch_scale = max(0.075, min(0.215, float(arch_scale)))
    geom = _check6_arched_transfer_bezier_geom(
        float(xa),
        float(ya),
        float(xb),
        float(yb),
        tension_face=str(tension_face),
        D_mm=float(D_mm),
        arch_scale=arch_scale,
    )
    if geom is None:
        return _check6_collinear_bezier_geom_from_chord(
            float(xa), float(ya), float(xb), float(yb)
        )
    return geom


def _check6_bezier_der_at_t(
    xa: float,
    ya: float,
    cx1: float,
    cy1: float,
    cx2: float,
    cy2: float,
    xb: float,
    yb: float,
    t: float,
) -> tuple[float, float]:
    u = 1.0 - t
    ddx = 3.0 * u * u * (cx1 - xa) + 6.0 * u * t * (cx2 - cx1) + 3.0 * t * t * (xb - cx2)
    ddy = 3.0 * u * u * (cy1 - ya) + 6.0 * u * t * (cy2 - cy1) + 3.0 * t * t * (yb - cy2)
    return ddx, ddy


def _check6_bezier_unit_tangents_at_ends(
    geom: tuple[float, ...],
) -> tuple[tuple[float, float], tuple[float, float]]:
    xa, ya, cx1, cy1, cx2, cy2, xb, yb = geom[:8]

    def _unit(t: float) -> tuple[float, float]:
        ddx, ddy = _check6_bezier_der_at_t(xa, ya, cx1, cy1, cx2, cy2, xb, yb, t)
        Ln = math.hypot(ddx, ddy)
        if Ln < 1e-12:
            return (1.0, 0.0)
        return ddx / Ln, ddy / Ln

    return _unit(0.0), _unit(1.0)


def _check6_unit_toe_to_tip_crack(
    *,
    support_side: str,
    tension_face: str,
    theta_v_rad: float,
) -> tuple[float, float]:
    """
    Unit vector **toe → crack tip** with **θ_v** = angle from **horizontal** (into-span, +x display)
    to the crack, CCW positive. Matches ``cot θ_v`` shear-steel geometry (mean line, not strut normal).

    Bottom tension: ``(|cos θ|, |sin θ|)`` with into-span horizontal sign; top tension: downward legs.
    """
    th = max(math.radians(1.0), min(theta_v_rad, math.radians(89.0)))
    cx, sy = math.cos(th), math.sin(th)
    sn = str(support_side or "left").strip().lower()
    tf = str(tension_face or "bottom").strip().lower()
    if tf == "bottom":
        if sn == "right":
            return -cx, sy
        if sn == "internal":
            return -cx, sy
        return cx, sy
    if sn == "right":
        return -cx, -sy
    if sn == "internal":
        return -cx, -sy
    return cx, -sy


def _check6_collinear_bezier_geom_from_chord(
    xa: float,
    ya: float,
    xb: float,
    yb: float,
) -> tuple[float, float, float, float, float, float, float, float, float, float, float] | None:
    """Cubic control points on the chord so Bézier derivatives match the straight θ crack."""
    xa, ya, xb, yb = float(xa), float(ya), float(xb), float(yb)
    dx, dy = xb - xa, yb - ya
    L = math.hypot(dx, dy)
    if L < 1e-9:
        return None
    t1, t2 = 1.0 / 3.0, 2.0 / 3.0
    nx, ny = -dy / L, dx / L
    cx1 = xa + t1 * dx
    cy1 = ya + t1 * dy
    cx2 = xa + t2 * dx
    cy2 = ya + t2 * dy
    return (xa, ya, cx1, cy1, cx2, cy2, xb, yb, nx, ny, L)


def _check6_arched_transfer_bezier_geom(
    xa: float,
    ya: float,
    xb: float,
    yb: float,
    *,
    tension_face: str,
    D_mm: float,
    arch_scale: float = 0.050,
) -> tuple[float, float, float, float, float, float, float, float, float, float, float] | None:
    """
    Mild cubic arch between endpoints (same tangents as gentle transfer curve).
    Bow lifts slightly toward the compression zone for bottom tension (readable, compact).
    """
    xa, ya, xb, yb = float(xa), float(ya), float(xb), float(yb)
    dx, dy = xb - xa, yb - ya
    L = math.hypot(dx, dy)
    if L < 1e-9:
        return None
    D = max(float(D_mm), 1.0)
    nx, ny = -dy / L, dx / L
    bulge = float(arch_scale) * min(L, 0.85 * D)
    if str(tension_face).strip().lower() == "bottom":
        if ny < 0:
            nx, ny = -nx, -ny
    else:
        if ny > 0:
            nx, ny = -nx, -ny
    ox, oy = nx * bulge, ny * bulge
    t1, t2 = 1.0 / 3.0, 2.0 / 3.0
    cx1 = xa + t1 * dx + ox
    cy1 = ya + t1 * dy + oy
    cx2 = xa + t2 * dx + ox
    cy2 = ya + t2 * dy + oy
    return (xa, ya, cx1, cy1, cx2, cy2, xb, yb, nx, ny, L)


def _check6_soft_jagged_on_bezier(
    geom: tuple[float, ...],
    *,
    D_mm: float,
    n: int = 44,
) -> list[tuple[float, float]]:
    """Jagged crack with smooth cubic centerline (same jitter style as straight chord)."""
    if geom is None or len(geom) < 11:
        return []
    xa, ya, cx1, cy1, cx2, cy2, xb, yb, _, _, L = geom[:11]
    L = max(float(L), 1e-9)
    D = max(float(D_mm), 1.0)
    arch_len = float(
        math.hypot(xb - xa, yb - ya) + 0.35 * math.hypot(cx2 - cx1, cy2 - cy1)
    )

    def _bez(t: float) -> tuple[float, float]:
        u = 1.0 - t
        uu, tt = u * u, t * t
        b0, b1, b2, b3 = u * uu, 3.0 * uu * t, 3.0 * u * tt, t * tt
        return (
            b0 * xa + b1 * cx1 + b2 * cx2 + b3 * xb,
            b0 * ya + b1 * cy1 + b2 * cy2 + b3 * yb,
        )

    def _dbez(t: float) -> tuple[float, float]:
        u = 1.0 - t
        ddx = 3.0 * u * u * (cx1 - xa) + 6.0 * u * t * (cx2 - cx1) + 3.0 * t * t * (xb - cx2)
        ddy = 3.0 * u * u * (cy1 - ya) + 6.0 * u * t * (cy2 - cy1) + 3.0 * t * t * (yb - cy2)
        return ddx, ddy

    jag_amp = max(3.2, 0.035 * min(arch_len, 0.52 * D))
    jag_amp = min(jag_amp, 0.060 * D)
    salt = 0.0017 * (xa + 2.3 * ya + 1.1 * xb + yb)
    out: list[tuple[float, float]] = []
    nn = max(12, int(n))
    for i in range(nn + 1):
        t = i / nn
        bx, by = _bez(t)
        ddx, ddy = _dbez(t)
        tlen = math.hypot(ddx, ddy)
        if tlen < 1e-9:
            px, py = 0.0, 1.0
        else:
            px, py = -ddy / tlen, ddx / tlen
        taper = math.sin(math.pi * t) ** 0.82
        if i == 0 or i == nn:
            off = 0.0
        else:
            j = float(i)
            wobble = math.sin(15.2 * j + salt) * math.cos(7.1 * j + 0.41 * salt)
            wobble += 0.45 * math.sin(27.0 * j * j / (nn + 1.0) + 1.3 * salt)
            wobble += 0.28 * math.sin(31.0 * j + 0.9 * salt)
            off = jag_amp * taper * max(-1.0, min(1.0, wobble))
        bx += off * px
        by += off * py
        out.append((bx, by))
    return out


def _check6_bezier_to_smooth_path_svg(
    geom: tuple[float, ...],
    *,
    n: int = 56,
) -> str:
    """Dense polyline approximating the cubic (for mean green / smooth crack paths)."""
    if geom is None or len(geom) < 8:
        return ""
    xa, ya, cx1, cy1, cx2, cy2, xb, yb = geom[:8]

    def _bez(t: float) -> tuple[float, float]:
        u = 1.0 - t
        uu, tt = u * u, t * t
        b0, b1, b2, b3 = u * uu, 3.0 * uu * t, 3.0 * u * tt, t * tt
        return (
            b0 * xa + b1 * cx1 + b2 * cx2 + b3 * xb,
            b0 * ya + b1 * cy1 + b2 * cy2 + b3 * yb,
        )

    nn = max(16, int(n))
    parts: list[str] = []
    for i in range(nn + 1):
        bx, by = _bez(i / nn)
        parts.append(f"{'M' if i == 0 else 'L'} {bx:.4f},{by:.4f}")
    return " ".join(parts)


def _check6_smooth_bezier_polyline_list(
    geom: tuple[float, ...],
    *,
    n: int = 72,
) -> list[tuple[float, float]]:
    if geom is None or len(geom) < 8:
        return []
    xa, ya, cx1, cy1, cx2, cy2, xb, yb = geom[:8]

    def _bez(t: float) -> tuple[float, float]:
        u = 1.0 - t
        uu, tt = u * u, t * t
        b0, b1, b2, b3 = u * uu, 3.0 * uu * t, 3.0 * u * tt, t * tt
        return (
            b0 * xa + b1 * cx1 + b2 * cx2 + b3 * xb,
            b0 * ya + b1 * cy1 + b2 * cy2 + b3 * yb,
        )

    nn = max(16, int(n))
    return [_bez(i / nn) for i in range(nn + 1)]


def _check6_soft_jagged_chord(
    xa: float,
    ya: float,
    xb: float,
    yb: float,
    *,
    D_mm: float,
    jag_scale: float = 0.78,
) -> list[tuple[float, float]]:
    """Straight crack chord with mild jagged styling (centered on θ_v mean line)."""
    xa, ya, xb, yb = float(xa), float(ya), float(xb), float(yb)
    dx, dy = xb - xa, yb - ya
    L = math.hypot(dx, dy)
    if L < 1e-6:
        return []
    nx, ny = -dy / L, dx / L
    D = max(float(D_mm), 1.0)
    n = 40
    jag_amp = max(2.8, 0.030 * min(L, 0.52 * D)) * float(jag_scale)
    jag_amp = min(jag_amp, 0.052 * D)
    salt = 0.0017 * (xa + 2.3 * ya + 1.1 * xb + yb)
    out: list[tuple[float, float]] = []
    for i in range(n + 1):
        t = i / n
        bx = xa + t * dx
        by = ya + t * dy
        taper = math.sin(math.pi * t) ** 0.82
        if i == 0 or i == n:
            off = 0.0
        else:
            j = float(i)
            wobble = math.sin(15.2 * j + salt) * math.cos(7.1 * j + 0.41 * salt)
            wobble += 0.45 * math.sin(27.0 * j * j / (n + 1.0) + 1.3 * salt)
            wobble += 0.28 * math.sin(31.0 * j + 0.9 * salt)
            off = jag_amp * taper * max(-1.0, min(1.0, wobble))
        bx += off * nx
        by += off * ny
        out.append((bx, by))
    return out


def _check6_soft_crack_polyline(
    xa: float,
    ya: float,
    xb: float,
    yb: float,
    *,
    tension_face: str,
    D_mm: float,
    bulge_scale: float = 1.0,
    jag_scale: float = 1.0,
) -> list[tuple[float, float]]:
    """
    Same geometry as the black crack: Bézier + jagged samples. Empty if degenerate chord.
    """
    geom = _check6_crack_bezier_setup(
        xa, ya, xb, yb, tension_face=tension_face, D_mm=D_mm, bulge_scale=bulge_scale
    )
    if geom is None:
        return []
    xa, ya, cx1, cy1, cx2, cy2, xb, yb, nx, ny, L = geom
    D = max(float(D_mm), 1.0)

    def _bez(t: float) -> tuple[float, float]:
        u = 1.0 - t
        uu, tt = u * u, t * t
        b0, b1, b2, b3 = u * uu, 3.0 * uu * t, 3.0 * u * tt, t * tt
        return (
            b0 * xa + b1 * cx1 + b2 * cx2 + b3 * xb,
            b0 * ya + b1 * cy1 + b2 * cy2 + b3 * yb,
        )

    def _dbez(t: float) -> tuple[float, float]:
        u = 1.0 - t
        ddx = 3.0 * u * u * (cx1 - xa) + 6.0 * u * t * (cx2 - cx1) + 3.0 * t * t * (xb - cx2)
        ddy = 3.0 * u * u * (cy1 - ya) + 6.0 * u * t * (cy2 - cy1) + 3.0 * t * t * (yb - cy2)
        return ddx, ddy

    n = 40
    js = max(0.0, float(jag_scale))
    jag_amp = max(3.5, 0.038 * min(L, 0.52 * D)) * js
    jag_amp *= max(0.72, min(1.45, float(bulge_scale)))
    jag_amp = min(jag_amp, 0.065 * D * js)
    salt = 0.0017 * (xa + 2.3 * ya + 1.1 * xb + yb)
    out: list[tuple[float, float]] = []
    for i in range(n + 1):
        t = i / n
        bx, by = _bez(t)
        ddx, ddy = _dbez(t)
        tlen = math.hypot(ddx, ddy)
        if tlen < 1e-9:
            px, py = nx, ny
        else:
            px, py = -ddy / tlen, ddx / tlen
        taper = math.sin(math.pi * t) ** 0.82
        if i == 0 or i == n:
            off = 0.0
        else:
            j = float(i)
            wobble = math.sin(15.2 * j + salt) * math.cos(7.1 * j + 0.41 * salt)
            wobble += 0.45 * math.sin(27.0 * j * j / (n + 1.0) + 1.3 * salt)
            wobble += 0.28 * math.sin(31.0 * j + 0.9 * salt)
            off = jag_amp * taper * max(-1.0, min(1.0, wobble))
        bx += off * px
        by += off * py
        out.append((bx, by))
    return out


def _check6_smooth_crack_polyline(
    xa: float,
    ya: float,
    xb: float,
    yb: float,
    *,
    tension_face: str,
    D_mm: float,
    n: int = 64,
    bulge_scale: float = 1.0,
) -> list[tuple[float, float]]:
    """Same Bézier backbone as the black crack, sampled smoothly (no perpendicular jag)."""
    geom = _check6_crack_bezier_setup(
        xa, ya, xb, yb, tension_face=tension_face, D_mm=D_mm, bulge_scale=bulge_scale
    )
    if geom is None:
        return []
    xa, ya, cx1, cy1, cx2, cy2, xb, yb, _, _, _ = geom

    def _bez(t: float) -> tuple[float, float]:
        u = 1.0 - t
        uu, tt = u * u, t * t
        b0, b1, b2, b3 = u * uu, 3.0 * uu * t, 3.0 * u * tt, t * tt
        return (
            b0 * xa + b1 * cx1 + b2 * cx2 + b3 * xb,
            b0 * ya + b1 * cy1 + b2 * cy2 + b3 * yb,
        )

    nn = max(16, int(n))
    return [_bez(i / nn) for i in range(nn + 1)]


def _check6_soft_crack_path_svg(
    xa: float,
    ya: float,
    xb: float,
    yb: float,
    *,
    tension_face: str,
    D_mm: float,
) -> str:
    """
    Cubic Bézier backbone from A to B (bow toward compression), then sampled to a polyline with
    subtle perpendicular jitter so it reads as a slightly jagged crack (stable, not random per frame).
    """
    pts = _check6_soft_crack_polyline(
        xa, ya, xb, yb, tension_face=tension_face, D_mm=D_mm
    )
    if not pts:
        return ""
    parts: list[str] = []
    for i, (bx, by) in enumerate(pts):
        parts.append(f"{'M' if i == 0 else 'L'} {bx:.4f},{by:.4f}")
    return " ".join(parts)


def _check6_polyline_to_path_svg(pts: list[tuple[float, float]]) -> str:
    if len(pts) < 2:
        return ""
    parts: list[str] = []
    for i, (bx, by) in enumerate(pts):
        parts.append(f"{'M' if i == 0 else 'L'} {bx:.4f},{by:.4f}")
    return " ".join(parts)


def _check6_scaled_rgba_alpha(color: str, alpha_scale: float) -> str:
    """Match ``shear_visuals._scaled_rgba_alpha`` for MCFT flow pulse styling."""
    if not color.startswith("rgba(") or not color.endswith(")"):
        return color
    parts = [part.strip() for part in color[5:-1].split(",")]
    if len(parts) != 4:
        return color
    try:
        alpha = float(parts[3])
    except ValueError:
        return color
    scaled_alpha = max(0.0, min(1.0, alpha * alpha_scale))
    return f"rgba({parts[0]},{parts[1]},{parts[2]},{scaled_alpha:.3f})"


def _check6_append_points_min_sep(
    acc: list[tuple[float, float]],
    pts: list[tuple[float, float]],
    *,
    min_sep: float = 0.18,
) -> None:
    for px, py in pts:
        if not acc:
            acc.append((float(px), float(py)))
            continue
        lx, ly = acc[-1]
        if math.hypot(float(px) - lx, float(py) - ly) >= float(min_sep):
            acc.append((float(px), float(py)))


def _check6_linear_sample(
    x0: float, y0: float, x1: float, y1: float, *, n: int
) -> list[tuple[float, float]]:
    n = max(2, int(n))
    out: list[tuple[float, float]] = []
    for i in range(n):
        t = i / (n - 1) if n > 1 else 0.0
        out.append((x0 + t * (x1 - x0), y0 + t * (y1 - y0)))
    return out


def _check6_tie_x_toward_support(
    *,
    tie_xa: float,
    tie_xb: float,
    support_face_x: float,
) -> float:
    ta, tb = (tie_xa, tie_xb) if tie_xa <= tie_xb else (tie_xb, tie_xa)
    return ta if abs(ta - support_face_x) <= abs(tb - support_face_x) else tb


def _check6_build_shear_transfer_flow_combined_pts(
    *,
    cx_c: float,
    y_c_top: float,
    y_c_bottom: float,
    mean_green_pts: list[tuple[float, float]],
    y_steel: float,
    tie_xa: float,
    tie_xb: float,
    support_face_x: float,
    D: float,
    L_seg: float,
) -> tuple[list[tuple[float, float]], tuple[int, int]]:
    """
    One polyline: top of C → down C → crack tip on green path → along green toward Ast →
    along tie toward the support (matches Check 5 load-transfer read).

    Returns ``(points, (end_red_incl, end_green_incl))`` where inclusive indices mark the last
    vertex of the red (vertical C), green (bridge + transfer + drop to Ast), and blue is the remainder.
    """
    if len(mean_green_pts) < 2:
        return [], (0, 0)
    D = max(float(D), 1.0)
    Ls = max(float(L_seg), 1.0)
    gtip = mean_green_pts[-1]
    gtoe = mean_green_pts[0]
    acc: list[tuple[float, float]] = []
    n_vert = max(10, min(48, int(abs(y_c_top - y_c_bottom) / max(0.012 * D, 4.0)) + 4))
    _check6_append_points_min_sep(
        acc, _check6_linear_sample(cx_c, y_c_top, cx_c, y_c_bottom, n=n_vert)
    )
    end_red = max(0, len(acc) - 1)
    bridge_n = max(
        2,
        min(
            16,
            int(
                math.hypot(float(gtip[0]) - cx_c, float(gtip[1]) - y_c_bottom)
                / max(0.015 * Ls, 5.0)
            )
            + 2,
        ),
    )
    _check6_append_points_min_sep(
        acc,
        _check6_linear_sample(cx_c, y_c_bottom, float(gtip[0]), float(gtip[1]), n=bridge_n),
    )
    for k in range(len(mean_green_pts) - 1, -1, -1):
        _check6_append_points_min_sep(acc, [mean_green_pts[k]])
    gx0, gy0 = float(gtoe[0]), float(gtoe[1])
    if abs(gy0 - float(y_steel)) > 0.8:
        _check6_append_points_min_sep(
            acc, _check6_linear_sample(gx0, gy0, gx0, float(y_steel), n=4)
        )
    end_green = max(end_red, len(acc) - 1)
    x_tie_goal = _check6_tie_x_toward_support(
        tie_xa=float(tie_xa),
        tie_xb=float(tie_xb),
        support_face_x=float(support_face_x),
    )
    t_lo, t_hi = (tie_xa, tie_xb) if tie_xa <= tie_xb else (tie_xb, tie_xa)
    x_on = min(max(gx0, t_lo), t_hi)
    n_tie = max(
        6,
        min(
            40,
            int(abs(x_on - x_tie_goal) / max(0.018 * Ls, 6.0)) + 4,
        ),
    )
    _check6_append_points_min_sep(
        acc,
        _check6_linear_sample(x_on, float(y_steel), x_tie_goal, float(y_steel), n=n_tie),
    )
    return acc, (end_red, end_green)


def _check6_add_mcft_style_flow_pulse(
    fig: go.Figure,
    pts: list[tuple[float, float]],
    *,
    color: str = "rgba(46,125,50,0.95)",
    reverse_along_path: bool = True,
    flow_segment_ends: tuple[int, int] | None = None,
    flow_arrowhead: bool = False,
    flow_colors_rgb: tuple[str, str, str] = ("#c41e3a", "#2e7d32", "#1565c0"),
    line_shape: str = "spline",
) -> None:
    """
    Dashed path + sliding ``meta.animate_flow`` window (same pattern as MCFT principal-stress
    diagrams). Default ``line_shape="spline"`` smooths along the polyline; use ``"linear"`` when
    the path mixes straight legs (e.g. vertical **C** + diagonal bridge) so Plotly does not bow the
    bridge segment to meet the next curve.
    """
    if len(pts) < 3:
        return
    ls = str(line_shape or "spline").strip().lower()
    use_spline = ls == "spline"
    xs = [float(p[0]) for p in pts]
    ys = [float(p[1]) for p in pts]
    line_kw: dict = dict(
        color=_check6_scaled_rgba_alpha(color, 0.95),
        width=3.2,
        dash="12px,10px",
    )
    if use_spline:
        line_kw["shape"] = "spline"
        line_kw["smoothing"] = 0.64
    else:
        line_kw["shape"] = "linear"
    fig.add_trace(
        go.Scatter(
            x=xs,
            y=ys,
            mode="lines",
            line=line_kw,
            opacity=0.96,
            hoverinfo="skip",
            showlegend=False,
        )
    )
    path_pts = list(reversed(pts)) if reverse_along_path else list(pts)
    if len(path_pts) < 5:
        return
    window = max(3, min(7, max(4, len(path_pts) // 2)))
    fx = [float(p[0]) for p in path_pts]
    fy = [float(p[1]) for p in path_pts]
    npath = len(fx)
    cr, cg, cb = flow_colors_rgb
    er, eg = -1, max(0, npath - 1)
    if flow_segment_ends is not None:
        er0, eg0 = int(flow_segment_ends[0]), int(flow_segment_ends[1])
        if reverse_along_path:
            er = max(0, npath - 1 - eg0)
            eg = max(0, npath - 1 - er0)
        else:
            er, eg = er0, eg0
    pulse_meta: dict = {
        "animate_flow": True,
        "flow_x": fx,
        "flow_y": fy,
        "window": window,
        "step": 1,
    }
    if flow_arrowhead:
        pulse_meta["flow_end_red"] = er
        pulse_meta["flow_end_green"] = eg
        pulse_meta["flow_color_red"] = cr
        pulse_meta["flow_color_green"] = cg
        pulse_meta["flow_color_blue"] = cb
    line_trace_index = len(fig.data)
    pulse_line_kw: dict = dict(
        color=_check6_scaled_rgba_alpha(color, 1.0),
        width=3.8,
    )
    if use_spline:
        pulse_line_kw["shape"] = "spline"
        pulse_line_kw["smoothing"] = 0.64
    else:
        pulse_line_kw["shape"] = "linear"
    fig.add_trace(
        go.Scatter(
            x=fx[:window],
            y=fy[:window],
            mode="lines",
            line=pulse_line_kw,
            opacity=0.98,
            hoverinfo="skip",
            showlegend=False,
            meta=pulse_meta,
        )
    )
    if flow_arrowhead and len(fx) >= 2:
        lead = min(max(window - 1, 0), npath - 1)
        lx0 = max(0, lead - 1)
        dx = float(fx[lead] - fx[lx0]) if lead > lx0 else float(fx[min(1, npath - 1)] - fx[0])
        dy = float(fy[lead] - fy[lx0]) if lead > lx0 else float(fy[min(1, npath - 1)] - fy[0])
        if abs(dx) + abs(dy) < 1e-9 and lead < npath - 1:
            dx = float(fx[lead + 1] - fx[lead])
            dy = float(fy[lead + 1] - fy[lead])
        ang0 = math.degrees(math.atan2(dy, dx)) - 90.0
        col0 = cg
        if flow_segment_ends is not None:
            if er >= 0 and lead <= er:
                col0 = cr
            elif lead <= eg:
                col0 = cg
            else:
                col0 = cb
        if col0 == cb:
            ang0 += 180.0
        fig.add_trace(
            go.Scatter(
                x=[fx[lead]],
                y=[fy[lead]],
                mode="markers",
                marker=dict(
                    symbol="triangle-up",
                    size=9,
                    angle=ang0,
                    color=col0,
                    line=dict(width=0.5, color="rgba(255,255,255,0.92)"),
                ),
                hoverinfo="skip",
                showlegend=False,
                meta={
                    "animate_flow_arrow": True,
                    "flow_follow_line_index": line_trace_index,
                },
            )
        )


def _check6_trim_polyline_at_ast_elevation(
    pts: list[tuple[float, float]],
    *,
    y_ast: float,
    tension_face: str,
) -> tuple[list[tuple[float, float]], float, int]:
    """
    Drop the tension-side tail: keep only the polyline from the Ast horizontal (y_ast) toward
    compression. Display y increases toward the top fibre; bottom tension → keep y >= y_ast.

    Returns (trimmed_points, t_index_offset, n_orig) so Bézier normals use
    t = (t_index_offset + k) / max(1, n_orig - 1) for trimmed index k.
    """
    n_orig = len(pts)
    if n_orig < 2:
        return (list(pts), 0.0, n_orig)
    y_s = float(y_ast)
    bottom_tension = str(tension_face).strip().lower() == "bottom"
    eps = 1e-6
    for i in range(n_orig - 1):
        x0, y0 = float(pts[i][0]), float(pts[i][1])
        x1, y1 = float(pts[i + 1][0]), float(pts[i + 1][1])
        if bottom_tension:
            if y0 >= y_s - eps:
                out = [(x0, y0)] + [
                    (float(pts[j][0]), float(pts[j][1])) for j in range(i + 1, n_orig)
                ]
                return (out, float(i), n_orig)
            if y0 < y_s - eps and y1 >= y_s - eps and abs(y1 - y0) > 1e-12:
                tseg = (y_s - y0) / (y1 - y0)
                if 0.0 <= tseg <= 1.0:
                    xi = x0 + tseg * (x1 - x0)
                    out = [(xi, y_s)] + [
                        (float(pts[j][0]), float(pts[j][1])) for j in range(i + 1, n_orig)
                    ]
                    return (out, float(i) + tseg, n_orig)
        else:
            if y0 <= y_s + eps:
                out = [(x0, y0)] + [
                    (float(pts[j][0]), float(pts[j][1])) for j in range(i + 1, n_orig)
                ]
                return (out, float(i), n_orig)
            if y0 > y_s + eps and y1 <= y_s + eps and abs(y1 - y0) > 1e-12:
                tseg = (y_s - y0) / (y1 - y0)
                if 0.0 <= tseg <= 1.0:
                    xi = x0 + tseg * (x1 - x0)
                    out = [(xi, y_s)] + [
                        (float(pts[j][0]), float(pts[j][1])) for j in range(i + 1, n_orig)
                    ]
                    return (out, float(i) + tseg, n_orig)
    return ([], 0.0, n_orig)


def _check6_add_green_ccw_flow_on_polyline(
    fig: go.Figure,
    pts: list[tuple[float, float]],
    *,
    x_shift_mm: float,
    D_mm: float,
    L_seg_mm: float,
    y_bot: float,
    y_top: float,
    green: str = "#2e7d32",
    crack_bezier_geom: tuple[float, ...] | None = None,
    wall_x_mm: float | None = None,
    wall_at_start: bool = False,
    suppress_wall_extension_at_tension: bool = False,
    bezier_t_index_offset: float = 0.0,
    bezier_n_orig: int | None = None,
    y_ast_clip: float | None = None,
    ast_clip_tension_face: str | None = None,
) -> None:
    """
    Smooth crack backbone offset by a constant perpendicular distance (same side as +x) so the
    green–crack gap reads even top vs bottom; clamped inside the beam. If needed, drops points from
    the compression end; extends along the Bézier tangent to the wall; arrows reversed along path.
    When the polyline is trimmed at Ast, set suppress_wall_extension_at_tension so the tension-side
    wall stub is not redrawn below that cut. y_ast_clip + ast_clip_tension_face keep the offset path
    and arrows on the compression side of the blue Ast (offset can otherwise cross y_steel).
    """
    if len(pts) < 4:
        return
    Ls = max(float(L_seg_mm), 1.0)
    D = max(float(D_mm), 1.0)
    x_m = max(0.018 * Ls, 0.022 * D, 12.0)
    y_m = max(0.014 * D, 8.0)
    x_lo_b = x_m
    x_hi_b = Ls - x_m
    y_lo_b = float(y_bot) + y_m
    y_hi_b = float(y_top) - y_m
    if x_hi_b <= x_lo_b or y_hi_b <= y_lo_b:
        return

    y_ast = float(y_ast_clip) if y_ast_clip is not None else None
    ast_tf = str(ast_clip_tension_face or "").strip().lower()
    ast_bottom = y_ast is not None and ast_tf == "bottom"
    ast_top = y_ast is not None and ast_tf == "top"

    desired = float(x_shift_mm)
    gap_min = max(0.022 * Ls, 0.026 * D, 18.0)
    n_param = int(bezier_n_orig) if bezier_n_orig is not None else len(pts)
    t_idx0 = float(bezier_t_index_offset)
    geom = crack_bezier_geom
    xa_g, ya_g, cx1_g, cy1_g, cx2_g, cy2_g, xb_g, yb_g = (
        (geom[:8] if geom is not None else (0.0,) * 8)
    )

    def _offset_normal_at_t(t: float) -> tuple[float, float]:
        if geom is None:
            return (1.0, 0.0)
        ddx, ddy = _check6_bezier_der_at_t(
            xa_g, ya_g, cx1_g, cy1_g, cx2_g, cy2_g, xb_g, yb_g, t
        )
        ln = math.hypot(ddx, ddy)
        if ln < 1e-12:
            return (1.0, 0.0)
        nx_n, ny_n = -ddy / ln, ddx / ln
        if nx_n < 0.0:
            nx_n, ny_n = -nx_n, -ny_n
        return nx_n, ny_n

    def _max_feasible_gap(pts_work: list[tuple[float, float]]) -> float:
        if geom is None:
            mx = max(float(x) for x, _ in pts_work)
            return min(desired, max(0.0, x_hi_b - mx))
        g = desired
        for i, (x, y) in enumerate(pts_work):
            t = min(1.0, max(0.0, (t_idx0 + i) / max(1, n_param - 1)))
            nx_n, ny_n = _offset_normal_at_t(t)
            x, y = float(x), float(y)
            if nx_n > 1e-9:
                g = min(g, (x_hi_b - x) / nx_n)
            elif nx_n < -1e-9:
                g = min(g, (x - x_lo_b) / (-nx_n))
            if ny_n > 1e-9:
                g = min(g, (y_hi_b - y) / ny_n)
            elif ny_n < -1e-9:
                g = min(g, (y - y_lo_b) / (-ny_n))
        return max(0.0, min(desired, g))

    pts_work = list(pts)
    while True:
        if len(pts_work) < 4:
            return
        gap_try = _max_feasible_gap(pts_work)
        if gap_try >= gap_min or len(pts_work) == 4:
            break
        pts_work.pop(-1)

    gap = _max_feasible_gap(pts_work)

    shifted: list[tuple[float, float]] = []
    for i, (x, y) in enumerate(pts_work):
        x, y = float(x), float(y)
        if geom is None:
            xr, yr = x + gap, y
        else:
            t = min(1.0, max(0.0, (t_idx0 + i) / max(1, n_param - 1)))
            nx_n, ny_n = _offset_normal_at_t(t)
            xr, yr = x + gap * nx_n, y + gap * ny_n
        if ast_bottom:
            yr = max(yr, y_ast)
        elif ast_top:
            yr = min(yr, y_ast)
        xr = min(max(xr, x_lo_b), x_hi_b)
        yr = min(max(yr, y_lo_b), y_hi_b)
        if ast_bottom:
            yr = max(yr, y_ast)
        elif ast_top:
            yr = min(yr, y_ast)
        shifted.append((xr, yr))

    wx = float(wall_x_mm) if wall_x_mm is not None and crack_bezier_geom is not None else None
    if wx is not None and len(shifted) >= 2:
        tan0, tan1 = _check6_bezier_unit_tangents_at_ends(crack_bezier_geom)
        if wall_at_start and not suppress_wall_extension_at_tension:
            px, py = shifted[0]
            dx, dy = -tan0[0], -tan0[1]
            if abs(dx) > 1e-6:
                s = (wx - px) / dx
                if s > 0.0 and math.isfinite(s):
                    ny = py + s * dy
                    ny = min(max(ny, y_lo_b), y_hi_b)
                    if ast_bottom:
                        ny = max(ny, y_ast)
                    elif ast_top:
                        ny = min(ny, y_ast)
                    shifted.insert(0, (wx, ny))
        else:
            px, py = shifted[-1]
            dx, dy = tan1[0], tan1[1]
            if abs(dx) > 1e-6:
                s = (wx - px) / dx
                if s > 0.0 and math.isfinite(s):
                    ny = py + s * dy
                    ny = min(max(ny, y_lo_b), y_hi_b)
                    if ast_bottom:
                        ny = max(ny, y_ast)
                    elif ast_top:
                        ny = min(ny, y_ast)
                    shifted.append((wx, ny))

    if y_ast is not None and ast_tf in ("bottom", "top"):
        shifted_t, _, _ = _check6_trim_polyline_at_ast_elevation(
            shifted, y_ast=y_ast, tension_face=ast_tf
        )
        if len(shifted_t) < 2:
            return
        shifted = shifted_t

    path_g = _check6_polyline_to_path_svg(shifted)
    if path_g:
        fig.add_shape(
            type="path",
            path=path_g,
            line=dict(color=green, width=2),
        )
    x_lo_arr = min(x_lo_b, wx) if wx is not None else x_lo_b
    x_hi_arr = max(x_hi_b, wx) if wx is not None else x_hi_b
    y_lo_arr = max(y_lo_b, y_ast) if ast_bottom else y_lo_b
    y_hi_arr = min(y_hi_b, y_ast) if ast_top else y_hi_b
    half = max(0.024 * D, 10.0)
    n = len(shifted)
    n_arrows = 8
    step = max(1, (n - 4) // max(n_arrows, 1))
    arrow_indices = list(range(2, n - 2, step))
    if arrow_indices:
        arrow_indices.pop(0)
    for i in arrow_indices:
        px, py = shifted[i]
        qx, qy = shifted[i + 1]
        rx, ry = shifted[i - 1]
        tx, ty = qx - rx, qy - ry
        tlen = math.hypot(tx, ty)
        if tlen < 1e-9:
            continue
        tx, ty = tx / tlen, ty / tlen
        # Reversed along path: arrowhead toward decreasing arc-length (support / tension end)
        x_tip = min(max(px - tx * half, x_lo_arr), x_hi_arr)
        y_tip = min(max(py - ty * half, y_lo_arr), y_hi_arr)
        x_tail = min(max(px + tx * half, x_lo_arr), x_hi_arr)
        y_tail = min(max(py + ty * half, y_lo_arr), y_hi_arr)
        fig.add_annotation(
            x=x_tip,
            y=y_tip,
            ax=x_tail,
            ay=y_tail,
            xref="x",
            yref="y",
            axref="x",
            ayref="y",
            text="",
            showarrow=True,
            arrowhead=2,
            arrowsize=0.78,
            arrowwidth=1.85,
            arrowcolor=green,
        )

    i_start = 2
    if n > i_start + 1:
        px, py = shifted[i_start]
        qx, qy = shifted[i_start + 1]
        rx, ry = shifted[i_start - 1]
        tx, ty = qx - rx, qy - ry
        tlen = math.hypot(tx, ty)
        if tlen >= 1e-9:
            tx, ty = tx / tlen, ty / tlen
            x_tip = min(max(px - tx * half, x_lo_arr), x_hi_arr)
            y_tip = min(max(py - ty * half, y_lo_arr), y_hi_arr)
            x_tail = min(max(px + tx * half, x_lo_arr), x_hi_arr)
            y_tail = min(max(py + ty * half, y_lo_arr), y_hi_arr)
            fig.add_annotation(
                x=x_tip,
                y=y_tip,
                ax=x_tail,
                ay=y_tail,
                xref="x",
                yref="y",
                axref="x",
                ayref="y",
                text="",
                showarrow=True,
                arrowhead=2,
                arrowsize=0.78,
                arrowwidth=1.85,
                arrowcolor=green,
            )

    # Three black arrows: normal to the path, along the green offset direction (into the web /
    # away from the crack); anchor shifted slightly along that normal so they clear the green stroke.
    lo_i, hi_i = 2, n - 3
    if n >= 4 and hi_i >= lo_i:
        black_half = max(0.034 * D, 15.0)
        seen_bi: set[int] = set()
        for frac in (0.30, 0.5, 0.8):
            bi = lo_i + int(round((hi_i - lo_i) * frac))
            bi = min(max(bi, lo_i), hi_i)
            if bi in seen_bi:
                continue
            seen_bi.add(bi)
            px, py = shifted[bi]
            t_b = min(1.0, max(0.0, (t_idx0 + bi) / max(1, n_param - 1)))
            if geom is not None:
                ox, oy = _offset_normal_at_t(t_b)
            else:
                qx, qy = shifted[bi + 1]
                rx, ry = shifted[bi - 1]
                ttx, tty = qx - rx, qy - ry
                tl = math.hypot(ttx, tty)
                if tl < 1e-9:
                    continue
                ttx, tty = ttx / tl, tty / tl
                crx, cry = tty, -ttx
                if crx > 0.0:
                    crx, cry = -tty, ttx
                tl2 = math.hypot(crx, cry)
                if tl2 < 1e-9:
                    continue
                ox, oy = -crx / tl2, -cry / tl2
            bx, by = -ox, -oy
            sep_mm = max(0.038 * D, 15.0)
            cx = px + ox * sep_mm
            cy = py + oy * sep_mm
            x_tip = min(max(cx - bx * black_half, x_lo_arr), x_hi_arr)
            y_tip = min(max(cy - by * black_half, y_lo_arr), y_hi_arr)
            x_tail = min(max(cx + bx * black_half, x_lo_arr), x_hi_arr)
            y_tail = min(max(cy + by * black_half, y_lo_arr), y_hi_arr)
            fig.add_annotation(
                x=x_tip,
                y=y_tip,
                ax=x_tail,
                ay=y_tail,
                xref="x",
                yref="y",
                axref="x",
                ayref="y",
                text="",
                showarrow=True,
                arrowhead=2,
                arrowsize=0.72,
                arrowwidth=1.9,
                arrowcolor="#111111",
            )


def _check6_polyline_unit_tangent(
    pts: list[tuple[float, float]], i: int
) -> tuple[float, float]:
    n = len(pts)
    if n < 2:
        return (1.0, 0.0)
    if i <= 0:
        dx = float(pts[1][0]) - float(pts[0][0])
        dy = float(pts[1][1]) - float(pts[0][1])
    elif i >= n - 1:
        dx = float(pts[n - 1][0]) - float(pts[n - 2][0])
        dy = float(pts[n - 1][1]) - float(pts[n - 2][1])
    else:
        dx = float(pts[i + 1][0]) - float(pts[i - 1][0])
        dy = float(pts[i + 1][1]) - float(pts[i - 1][1])
    ln = math.hypot(dx, dy)
    if ln < 1e-12:
        return (1.0, 0.0)
    return dx / ln, dy / ln


def _check6_unit_normal_from_tangent_toward_compression(
    tx: float, ty: float, compression_face: str
) -> tuple[float, float]:
    n0x, n0y = -float(ty), float(tx)
    refy = 1.0 if str(compression_face).strip().lower() == "top" else -1.0
    if n0y * refy < 0.0:
        n0x, n0y = -n0x, -n0y
    return n0x, n0y


def _check6_polyline_offset_toward_compression(
    pts: list[tuple[float, float]],
    *,
    gap_mm: float,
    compression_face: str,
    D_mm: float,
    L_seg_mm: float,
    y_bot: float,
    y_top: float,
    normal_sign: float = 1.0,
) -> list[tuple[float, float]]:
    if len(pts) < 2 or float(gap_mm) <= 0:
        return []
    Ls = max(float(L_seg_mm), 1.0)
    D = max(float(D_mm), 1.0)
    x_m = max(0.018 * Ls, 0.022 * D, 12.0)
    y_m = max(0.014 * D, 8.0)
    x_lo, x_hi = x_m, Ls - x_m
    y_lo, y_hi = float(y_bot) + y_m, float(y_top) - y_m
    if x_hi <= x_lo or y_hi <= y_lo:
        return []
    g = float(gap_mm)
    sgn = float(normal_sign)
    out: list[tuple[float, float]] = []
    n = len(pts)
    for i in range(n):
        tx, ty = _check6_polyline_unit_tangent(pts, i)
        nx, ny = _check6_unit_normal_from_tangent_toward_compression(
            tx, ty, compression_face
        )
        x = float(pts[i][0]) + g * nx * sgn
        y = float(pts[i][1]) + g * ny * sgn
        x = min(max(x, x_lo), x_hi)
        y = min(max(y, y_lo), y_hi)
        out.append((x, y))
    return out


def _check6_add_green_black_flow_arrows_on_polyline(
    fig: go.Figure,
    pts: list[tuple[float, float]],
    *,
    D_mm: float,
    L_seg_mm: float,
    y_bot: float,
    y_top: float,
    green: str = "#2e7d32",
    show_green_tangent_arrows: bool = True,
) -> None:
    """Green arrows along local tangent (toward toe); black perpendicular, open end left of green, head right (L→R)."""
    if len(pts) < 5:
        return
    Ls = max(float(L_seg_mm), 1.0)
    D = max(float(D_mm), 1.0)
    x_m = max(0.018 * Ls, 0.022 * D, 12.0)
    y_m = max(0.014 * D, 8.0)
    x_lo_arr = x_m
    x_hi_arr = Ls - x_m
    y_lo_arr = float(y_bot) + y_m
    y_hi_arr = float(y_top) - y_m
    if x_hi_arr <= x_lo_arr or y_hi_arr <= y_lo_arr:
        return

    half = max(0.024 * D, 10.0)
    n_pts = len(pts)
    if show_green_tangent_arrows:
        n_arrows = 8
        step = max(1, (n_pts - 4) // max(n_arrows, 1))
        arrow_indices = list(range(2, n_pts - 2, step))
        if arrow_indices:
            arrow_indices.pop(0)
        for i in arrow_indices:
            if i <= 0 or i >= n_pts - 1:
                continue
            px, py = pts[i]
            tx, ty = _check6_polyline_unit_tangent(pts, i)
            if math.hypot(tx, ty) < 1e-12:
                continue
            gx_tip = min(max(px - tx * half, x_lo_arr), x_hi_arr)
            gy_tip = min(max(py - ty * half, y_lo_arr), y_hi_arr)
            gx_tail = min(max(px + tx * half, x_lo_arr), x_hi_arr)
            gy_tail = min(max(py + ty * half, y_lo_arr), y_hi_arr)
            fig.add_annotation(
                x=gx_tip,
                y=gy_tip,
                ax=gx_tail,
                ay=gy_tail,
                xref="x",
                yref="y",
                axref="x",
                ayref="y",
                text="",
                showarrow=True,
                arrowhead=2,
                arrowsize=0.78,
                arrowwidth=1.85,
                arrowcolor=green,
            )

        i_start = 2
        if n_pts > i_start + 1:
            px, py = pts[i_start]
            tx, ty = _check6_polyline_unit_tangent(pts, i_start)
            if math.hypot(tx, ty) >= 1e-12:
                gx_tip = min(max(px - tx * half, x_lo_arr), x_hi_arr)
                gy_tip = min(max(py - ty * half, y_lo_arr), y_hi_arr)
                gx_tail = min(max(px + tx * half, x_lo_arr), x_hi_arr)
                gy_tail = min(max(py + ty * half, y_lo_arr), y_hi_arr)
                fig.add_annotation(
                    x=gx_tip,
                    y=gy_tip,
                    ax=gx_tail,
                    ay=gy_tail,
                    xref="x",
                    yref="y",
                    axref="x",
                    ayref="y",
                    text="",
                    showarrow=True,
                    arrowhead=2,
                    arrowsize=0.78,
                    arrowwidth=1.85,
                    arrowcolor=green,
                )

    lo_i, hi_i = 2, n_pts - 3
    if hi_i >= lo_i:
        sep_tail = max(0.052 * D, 20.0)
        sep_head = max(0.041 * D, 16.0)
        gap_from_green = max(0.034 * D, 15.0)
        # Parallel offset (+n_r): arrow line does not pass through the green polyline (clear gap).
        seen_bi: set[int] = set()
        for frac in (0.30, 0.5, 0.8):
            bi = lo_i + int(round((hi_i - lo_i) * frac))
            bi = min(max(bi, lo_i), hi_i)
            if bi in seen_bi:
                continue
            seen_bi.add(bi)
            px, py = pts[bi]
            tx, ty = _check6_polyline_unit_tangent(pts, bi)
            if math.hypot(tx, ty) < 1e-12:
                continue
            # Right-hand normal to forward tangent (toe → tip): tail on +n_r, head on −n_r.
            rx, ry = float(ty), -float(tx)
            rlen = math.hypot(rx, ry)
            if rlen < 1e-12:
                continue
            rx, ry = rx / rlen, ry / rlen
            tail_x = px + (sep_tail + gap_from_green) * rx
            tail_y = py + (sep_tail + gap_from_green) * ry
            head_x = px + (gap_from_green - sep_head) * rx
            head_y = py + (gap_from_green - sep_head) * ry
            tail_x = min(max(tail_x, x_lo_arr), x_hi_arr)
            tail_y = min(max(tail_y, y_lo_arr), y_hi_arr)
            head_x = min(max(head_x, x_lo_arr), x_hi_arr)
            head_y = min(max(head_y, y_lo_arr), y_hi_arr)
            # Plotly: arrow from (ax,ay) to (x,y); arrowhead at (x,y). Open end left, head right of green.
            fig.add_annotation(
                x=tail_x,
                y=tail_y,
                ax=head_x,
                ay=head_y,
                xref="x",
                yref="y",
                axref="x",
                ayref="y",
                text="",
                showarrow=True,
                arrowhead=2,
                arrowsize=0.72,
                arrowwidth=1.9,
                arrowcolor="#111111",
            )


def _check6_shear_ligatures_active(
    *, s_mm: float, lig_legs: int, asv_mm2: float | None = None
) -> bool:
    """True only when current shear ligatures are present (no placeholder stirrups)."""
    if float(s_mm) <= 1e-6:
        return False
    if int(lig_legs) < 2:
        return False
    if asv_mm2 is not None and float(asv_mm2) <= 1e-6:
        return False
    return True


def _check6_add_mcft_mechanism_labels(
    fig: go.Figure,
    *,
    D: float,
    L_seg: float,
    L_d_core: float,
    crack_pts: list[tuple[float, float]],
    mean_green_pts: list[tuple[float, float]],
    theta_lbl_x: float,
    theta_lbl_y: float,
    cx_c: float,
    y_c_top: float,
    y_c_bot: float,
    y_steel: float,
    ast_lbl_x: float,
    ast_arrow_x0: float,
    ast_arrow_x1: float,
    tension_face: str,
    side_n: str,
    y_bot_beam: float,
    y_top_beam: float,
    y_stirr_bot: float,
    y_stirr_top: float,
    stirrup_xds: list[float],
    show_region_labels: bool,
    support_X: float,
    x_disp,
) -> None:
    """
    Check 5 only: V_cr / V_ca / V_cc / V_d beside crack, green strut, compression block, and tie.
    Positions are nudged to reduce overlap with linework and each other (no geometry changes).
    """
    if len(crack_pts) < 3 or len(mean_green_pts) < 2:
        return
    Df = max(float(D), 1.0)
    Ls = max(float(L_seg), 1.0)
    tf = str(tension_face).strip().lower()
    sn = str(side_n).strip().lower()

    t_samp = 0.46
    nc, ng = len(crack_pts), len(mean_green_pts)
    ic = min(max(int(round(t_samp * (nc - 1))), 1), nc - 2)
    ig = min(max(int(round(t_samp * (ng - 1))), 1), ng - 2)
    crx, cry = float(crack_pts[ic][0]), float(crack_pts[ic][1])
    gpx, gpy = float(mean_green_pts[ig][0]), float(mean_green_pts[ig][1])
    dgx, dgy = gpx - crx, gpy - cry
    glen = math.hypot(dgx, dgy)
    if glen < 1e-6:
        return
    ux, uy = dgx / glen, dgy / glen
    off_cr = max(0.026 * Df, 16.0)
    off_ca = max(0.028 * Df, 17.0)
    vcr_x, vcr_y = crx - ux * off_cr, cry - uy * off_cr
    vca_x, vca_y = gpx + ux * off_ca, gpy + uy * off_ca

    # V_cc: compression-side block (top fibre for sagging, bottom for hogging)
    c_hw = max(0.028 * Df, 11.0)
    if tf == "bottom":
        y_cc = float(y_c_top) - max(0.022 * Df, 10.0)
        vcc_y = min(max(y_cc, float(y_c_bot) + c_hw), float(y_c_top) - 0.012 * Df)
    else:
        y_cc = float(y_c_bot) + max(0.022 * Df, 10.0)
        vcc_y = min(max(y_cc, float(y_c_bot) + 0.012 * Df), float(y_c_top) - c_hw)
    if sn == "right":
        vcc_x = float(cx_c) - max(0.055 * Df, 22.0)
        vcc_ax = "right"
    elif sn == "internal":
        vcc_x = float(cx_c) - max(0.048 * Df, 20.0)
        vcc_ax = "right"
    else:
        vcc_x = float(cx_c) + max(0.055 * Df, 22.0)
        vcc_ax = "left"

    # V_d: beside blue Ast / crack crossing — offset up and to the span-ward side in x
    ys = float(y_steel)
    ast_lo = min(float(ast_arrow_x0), float(ast_arrow_x1))
    ast_hi = max(float(ast_arrow_x0), float(ast_arrow_x1))
    crack_cross: list[tuple[float, float]] = []
    for k in range(len(crack_pts) - 1):
        x0, y0 = float(crack_pts[k][0]), float(crack_pts[k][1])
        x1, y1 = float(crack_pts[k + 1][0]), float(crack_pts[k + 1][1])
        if abs(y1 - y0) < 1e-9:
            continue
        y_lo, y_hi = (y0, y1) if y0 <= y1 else (y1, y0)
        if y_lo - 1e-6 <= ys <= y_hi + 1e-6:
            t = (ys - y0) / (y1 - y0)
            if -1e-5 <= t <= 1.0 + 1e-5:
                xi = x0 + t * (x1 - x0)
                crack_cross.append((xi, ys))
    if crack_cross:
        in_ast = [
            p
            for p in crack_cross
            if ast_lo - 0.12 * Ls <= p[0] <= ast_hi + 0.12 * Ls
        ]
        pool = in_ast if in_ast else crack_cross
        if sn == "right":
            ix, iy = min(pool, key=lambda p: p[0])
        else:
            ix, iy = max(pool, key=lambda p: p[0])
    else:
        ast_mid = 0.5 * (ast_lo + ast_hi)
        ix, iy = ast_mid, ys
        best_d = 1e18
        best_xy = (ix, iy)
        for k in range(len(crack_pts) - 1):
            x0, y0 = float(crack_pts[k][0]), float(crack_pts[k][1])
            x1, y1 = float(crack_pts[k + 1][0]), float(crack_pts[k + 1][1])
            abx, aby = x1 - x0, y1 - y0
            al = abx * abx + aby * aby
            if al < 1e-18:
                continue
            t = max(0.0, min(1.0, ((ast_mid - x0) * abx + (ys - y0) * aby) / al))
            qx, qy = x0 + t * abx, y0 + t * aby
            d = math.hypot(ast_mid - qx, ys - qy)
            if d < best_d:
                best_d = d
                best_xy = (qx, qy)
        ix, iy = best_xy
    step_x = max(0.030 * Df, 16.0)
    step_y = max(0.032 * Df, 17.0)
    dir_x = -1.0 if sn == "right" else 1.0
    vd_x = ix + dir_x * step_x
    vd_y = iy + step_y
    vd_yanchor = "bottom"
    vd_xanchor = "left" if dir_x > 0 else "right"
    vd_x = min(max(vd_x, 0.05 * Ls), Ls - 0.05 * Ls)
    vd_y = min(max(vd_y, float(y_bot_beam) + 0.04 * Df), float(y_top_beam) - 0.04 * Df)

    # Region label apertures (below soffit)
    reg_y: float | None = None
    reg_x1: float | None = None
    reg_x2: float | None = None
    if show_region_labels:
        reg_y = float(y_bot_beam) - max(0.056 * Df, 28.0)
        L_rem = max(L_seg - L_d_core, 0.08 * L_seg)
        if sn == "right":
            reg_x1 = float(x_disp(0.52 * L_d_core))
            reg_x2 = float(x_disp(L_d_core + 0.50 * L_rem))
        elif sn == "internal":
            reg_x1 = float(support_X) + 0.42 * min(
                L_d_core, max(L_seg - support_X, 1.0) * 0.92
            )
            reg_x2 = max(0.06 * L_seg, support_X * 0.42)
        else:
            reg_x1 = float(x_disp(0.48 * L_d_core))
            reg_x2 = float(x_disp(L_d_core + 0.50 * L_rem))

    min_l = max(0.048 * Df, 26.0)
    pts: list[list[float]] = [
        [vcr_x, vcr_y],
        [vca_x, vca_y],
        [vcc_x, vcc_y],
        [vd_x, vd_y],
    ]

    def _too_close_stirrup(px: float, py: float) -> bool:
        ys_lo = min(float(y_stirr_bot), float(y_stirr_top))
        ys_hi = max(float(y_stirr_bot), float(y_stirr_top))
        vm = max(0.02 * Df, 6.0)
        for xv in stirrup_xds:
            if abs(float(px) - float(xv)) < max(0.018 * Df, 7.0):
                if ys_lo - vm <= py <= ys_hi + vm:
                    return True
        return False

    def _dist_to_seg(
        px: float, py: float, ax: float, ay: float, bx: float, by: float
    ) -> float:
        abx, aby = bx - ax, by - ay
        t = ((px - ax) * abx + (py - ay) * aby) / max(abx * abx + aby * aby, 1e-12)
        t = max(0.0, min(1.0, t))
        qx, qy = ax + t * abx, ay + t * aby
        return math.hypot(px - qx, py - qy)

    def _min_dist_polyline(px: float, py: float, poly: list[tuple[float, float]]) -> float:
        m = 1e18
        for k in range(len(poly) - 1):
            m = min(
                m,
                _dist_to_seg(
                    px,
                    py,
                    float(poly[k][0]),
                    float(poly[k][1]),
                    float(poly[k + 1][0]),
                    float(poly[k + 1][1]),
                ),
            )
        return m

    def _repel_from_features(
        px: float, py: float, *, vd_label: bool = False
    ) -> tuple[float, float]:
        x, y = float(px), float(py)
        # Theta label
        dth = math.hypot(x - float(theta_lbl_x), y - float(theta_lbl_y))
        if dth < max(0.10 * Df, 36.0):
            s = max(0.10 * Df, 36.0) - dth + 4.0
            if dth > 1e-6:
                x += s * (x - theta_lbl_x) / dth
                y += s * (y - theta_lbl_y) / dth
            else:
                x += s
        # Vertical compression resultant
        if abs(x - float(cx_c)) < max(0.032 * Df, 14.0):
            if float(y_c_bot) - 0.02 * Df <= y <= float(y_c_top) + 0.02 * Df:
                step = max(0.042 * Df, 18.0)
                x += step if x >= float(cx_c) else -step
        # Ast horizontal bar (keep V_d readable beside crack–Ast crossing)
        if not vd_label and abs(y - float(y_steel)) < max(0.022 * Df, 10.0):
            lo, hi = (
                (min(ast_arrow_x0, ast_arrow_x1), max(ast_arrow_x0, ast_arrow_x1))
                if ast_arrow_x0 <= ast_arrow_x1
                else (min(ast_arrow_x1, ast_arrow_x0), max(ast_arrow_x1, ast_arrow_x0))
            )
            if lo - 0.03 * Ls <= x <= hi + 0.03 * Ls:
                y += max(0.034 * Df, 14.0) if y >= float(y_steel) else -max(0.034 * Df, 14.0)
        # Crack / green polylines
        if not vd_label:
            if _min_dist_polyline(x, y, crack_pts) < max(0.018 * Df, 9.0):
                x -= ux * max(0.022 * Df, 10.0)
                y -= uy * max(0.022 * Df, 10.0)
            if _min_dist_polyline(x, y, mean_green_pts) < max(0.018 * Df, 9.0):
                x += ux * max(0.022 * Df, 10.0)
                y += uy * max(0.022 * Df, 10.0)
        if _too_close_stirrup(x, y):
            x += max(0.035 * Df, 14.0) * (1.0 if x < 0.5 * Ls else -1.0)
        if reg_y is not None and reg_x1 is not None and reg_x2 is not None:
            if abs(y - reg_y) < max(0.05 * Df, 22.0):
                rx_lo = min(reg_x1, reg_x2) - 0.06 * Ls
                rx_hi = max(reg_x1, reg_x2) + 0.06 * Ls
                if rx_lo <= x <= rx_hi:
                    y = reg_y + max(0.08 * Df, 30.0)
        x = min(max(x, 0.04 * Ls), Ls - 0.04 * Ls)
        y = min(max(y, float(y_bot_beam) + 0.03 * Df), float(y_top_beam) - 0.03 * Df)
        return x, y

    for _ in range(14):
        for i in range(len(pts)):
            pts[i][0], pts[i][1] = _repel_from_features(
                pts[i][0], pts[i][1], vd_label=(i == 3)
            )
        moved = False
        for i in range(len(pts)):
            for j in range(i + 1, len(pts)):
                dx = pts[j][0] - pts[i][0]
                dy = pts[j][1] - pts[i][1]
                d = math.hypot(dx, dy)
                if d < min_l and d > 1e-9:
                    push = 0.52 * (min_l - d)
                    fx, fy = dx / d, dy / d
                    pts[i][0] -= fx * push
                    pts[i][1] -= fy * push
                    pts[j][0] += fx * push
                    pts[j][1] += fy * push
                    moved = True
        if not moved:
            break
        for i in range(len(pts)):
            pts[i][0], pts[i][1] = _repel_from_features(
                pts[i][0], pts[i][1], vd_label=(i == 3)
            )

    halo = dict(
        bgcolor="rgba(255,255,255,0.90)",
        borderpad=3,
        bordercolor="rgba(255,255,255,0)",
    )
    col_cr = "rgba(38,40,44,0.96)"
    col_ca = "#1b5e20"
    col_cc = "#c41e3a"
    col_vd = "#1565c0"

    fig.add_annotation(
        x=pts[0][0],
        y=pts[0][1],
        text="<i>V</i><sub>cr</sub>",
        showarrow=False,
        font=dict(size=10, color=col_cr),
        xref="x",
        yref="y",
        xanchor="center",
        yanchor="middle",
        **halo,
    )
    fig.add_annotation(
        x=pts[1][0],
        y=pts[1][1],
        text="<i>V</i><sub>ca</sub>",
        showarrow=False,
        font=dict(size=10, color=col_ca),
        xref="x",
        yref="y",
        xanchor="center",
        yanchor="middle",
        **halo,
    )
    fig.add_annotation(
        x=pts[2][0],
        y=pts[2][1],
        text="<i>V</i><sub>cc</sub>",
        showarrow=False,
        font=dict(size=10, color=col_cc),
        xref="x",
        yref="y",
        xanchor=vcc_ax,
        yanchor="middle",
        **halo,
    )
    fig.add_annotation(
        x=pts[3][0],
        y=pts[3][1],
        text="<i>V</i><sub>d</sub>",
        showarrow=False,
        font=dict(size=10, color=col_vd),
        xref="x",
        yref="y",
        xanchor=vd_xanchor,
        yanchor=vd_yanchor,
        **halo,
    )


def _check6_add_web_crushing_stm_overlay(
    fig: go.Figure,
    *,
    D: float,
    L_seg: float,
    support_face_x: float,
    x_toe: float,
    y_toe: float,
    y_steel: float,
    y_top_beam: float,
    y_bot_beam: float,
    tension_face: str,
    side_n: str,
    theta_v_deg: float,
    pad_x_toe: float,
) -> None:
    """
    D-region strut-and-tie sketch for web-crushing: red diagonal strut at governing **θ_v**
    (same convention as ``_check6_unit_toe_to_tip_crack`` / MCFT crack), tie cue at Ast,
    d_v bracket, and V_u,max label.
    """
    Df = max(float(D), 1.0)
    Ls = max(float(L_seg), 1.0)
    pad = max(float(pad_x_toe), 6.0)
    tf = str(tension_face).strip().lower()
    sn = str(side_n or "left").strip().lower()
    if tf == "bottom":
        y_comp = float(y_top_beam) - max(0.042 * Df, 13.0)
    else:
        y_comp = float(y_bot_beam) + max(0.042 * Df, 13.0)

    lo = min(float(support_face_x), float(x_toe))
    hi = max(float(support_face_x), float(x_toe))
    tie_inset = max(0.026 * Ls, 11.0)
    x_tie0 = lo + tie_inset
    x_tie1 = hi - tie_inset
    if x_tie1 <= x_tie0 + 2.0:
        x_tie0, x_tie1 = lo, hi

    x_strut_bot = min(max(float(support_face_x), x_tie0), x_tie1)

    x0, y0 = float(x_strut_bot), float(y_steel)
    y_lo = float(y_bot_beam) + 0.018 * Df
    y_hi = float(y_top_beam) - 0.018 * Df

    th = math.radians(max(1.0, min(float(theta_v_deg), 89.0)))
    uxn, uyn = _check6_unit_toe_to_tip_crack(
        support_side=sn,
        tension_face=tf,
        theta_v_rad=th,
    )
    uln = math.hypot(uxn, uyn)
    if uln > 1e-9:
        uxn, uyn = uxn / uln, uyn / uln
    # Half-line from tie toward compression (same θ; flip 180° if needed).
    if (float(y_comp) - y0) * uyn < 0:
        uxn, uyn = -uxn, -uyn

    # End on compression band so strut lies exactly at θ_v (slope dy/dx = uyn/uxn).
    if abs(uyn) > 1e-6:
        t_ray = (float(y_comp) - y0) / uyn
        x1 = x0 + uxn * t_ray
        y1 = float(y_comp)
    elif abs(uxn) > 1e-6:
        t_ray = max(0.2 * Ls, 40.0)
        x1 = x0 + uxn * t_ray
        y1 = y0
    else:
        x1, y1 = x0 + 0.25 * Ls, y_comp

    def _clip_preserving_slope() -> None:
        nonlocal x1, y1
        if x1 < pad or x1 > Ls - pad:
            x1 = min(max(x1, pad), Ls - pad)
            if abs(uxn) > 1e-6:
                y1 = y0 + (uyn / uxn) * (x1 - x0)
        if y1 < y_lo or y1 > y_hi:
            y1 = min(max(y1, y_lo), y_hi)
            if abs(uyn) > 1e-6:
                x1 = x0 + (uxn / uyn) * (y1 - y0)

    _clip_preserving_slope()
    _clip_preserving_slope()

    c_red = "#c41e3a"
    ast_blue = "#1565c0"
    teach_col = "rgba(55,71,79,0.78)"

    fig.add_trace(
        go.Scatter(
            x=[x0, x1],
            y=[y0, y1],
            mode="lines",
            line=dict(color=c_red, width=3.6),
            hoverinfo="skip",
            showlegend=False,
        )
    )

    xm, ym = 0.5 * (x0 + x1), 0.5 * (y0 + y1)
    # θ label: just above the blue Ast line (y_steel); x biased left (support-ward).
    theta_x = 0.58 * float(x0) + 0.42 * float(x_toe)
    theta_x -= max(0.030 * Ls, 20.0)
    theta_x = min(max(theta_x, pad + max(0.02 * Ls, 10.0)), Ls - pad - max(0.02 * Ls, 10.0))
    if tf == "bottom":
        theta_y = float(y_steel) + max(0.007 * Df, 5.0)
        theta_yanchor = "bottom"
    else:
        theta_y = float(y_steel) - max(0.007 * Df, 5.0)
        theta_yanchor = "top"
    span_sign = 1.0 if uxn >= 0.0 else -1.0
    theta_xanchor = "right" if span_sign > 0 else "left"
    fig.add_annotation(
        x=theta_x,
        y=theta_y,
        text=f"θ = {float(theta_v_deg):.1f}°",
        showarrow=False,
        font=dict(size=8, color="rgba(31,42,68,0.90)"),
        xref="x",
        yref="y",
        xanchor=theta_xanchor,
        yanchor=theta_yanchor,
    )
    fig.add_annotation(
        x=xm - 0.012 * Ls * uxn,
        y=ym - 0.020 * Df * abs(uyn) - 0.012 * Df,
        text="<i>Diagonal compression strut</i>",
        showarrow=False,
        font=dict(size=8, color="rgba(196,30,58,0.92)"),
        xref="x",
        yref="y",
    )
    # Tie (Ast): span-ward of θ (same text row); anchors keep a gap for left vs right support.
    tie_ast_x = float(theta_x) + span_sign * max(0.048 * Ls, 36.0)
    tie_ast_x = min(max(tie_ast_x, pad + max(0.015 * Ls, 10.0)), Ls - pad - max(0.015 * Ls, 10.0))
    tie_xanchor = "left" if span_sign > 0 else "right"
    fig.add_annotation(
        x=tie_ast_x,
        y=theta_y,
        text="<i>Tie (</i><b>Ast</b><i>)</i>",
        showarrow=False,
        font=dict(size=8, color=ast_blue),
        xref="x",
        yref="y",
        xanchor=tie_xanchor,
        yanchor=theta_yanchor,
    )

    x_dv = float(x_toe) - max(0.016 * Ls, 9.0)
    x_dv = max(pad, min(x_dv, Ls - pad))
    y_lo_dv = min(float(y_steel), float(y_comp))
    y_hi_dv = max(float(y_steel), float(y_comp))
    if y_hi_dv - y_lo_dv > max(0.05 * Df, 14.0):
        fig.add_shape(
            type="line",
            x0=x_dv,
            y0=y_lo_dv,
            x1=x_dv,
            y1=y_hi_dv,
            line=dict(color=teach_col, width=1.25, dash="dot"),
        )
        fig.add_annotation(
            x=x_dv - max(0.014 * Ls, 8.0),
            y=0.5 * (y_lo_dv + y_hi_dv),
            text="<i>d<sub>v</sub></i>",
            showarrow=False,
            font=dict(size=8, color=teach_col),
            xref="x",
            yref="y",
            xanchor="right",
            yanchor="middle",
        )

    fig.add_annotation(
        x=0.5 * (lo + hi),
        y=float(y_bot_beam) - max(0.048 * Df, 24.0),
        text="<i>V</i><sub>u,max</sub> web-crushing limit",
        showarrow=False,
        font=dict(size=9, color="rgba(31,42,68,0.88)"),
        xref="x",
        yref="y",
        xanchor="center",
        yanchor="top",
    )


def build_shear_check6_support_transfer_diagram(
    *,
    layout: dict | None,
    D_mm: float,
    d_mm: float,
    moment_sign: str,
    support_draw_kind: str,
    critical_support_side: str,
    s_lig_mm: float,
    lig_legs: int,
    lig_d_mm: float = 10.0,
    asv_mm2: float | None = None,
    height: int = 320,
    fc_mpa: float | None = None,
    fsy_mpa: float | None = None,
    theta_v_deg: float | None = None,
    d_v_mm: float | None = None,
    show_mean_crack_guideline: bool = True,
    show_mean_green_flow_pulse: bool = True,
    show_mean_green_flow_arrows: bool = True,
    show_green_strut_flow: bool = False,
    show_compression_resultant: bool = True,
    show_shear_teaching_overlay: bool = False,
    show_region_labels: bool = True,
    show_mcft_mechanism_labels: bool = False,
    crack_bulge_scale: float = 1.28,
    crack_jag_scale: float = 0.88,
    web_crushing_stm: bool = False,
) -> go.Figure:
    """
    Local support-region schematic: ~1.5d–2d D-region from the critical support plus ~0.5d–1.0d
    into the adjacent shear span. L_d_core is unchanged from the band formulas; the flexural-shear
    run uses the same nominal L_span_extra scaled by flex_leg_scale (no cap that re-balances D vs flex).
    x_fs = distance from the governing support face into the span (mm);
    display X places the support on the window boundary (left end → X=0, right end → X=L_seg).

    Optional display variants (Check 5 vs Check 7): omit mean crack guideline, strut-flow overlay,
    compression ``C``, green/black load-path arrows (``show_mean_green_flow_arrows``), and teaching
    geometry via the ``show_*`` flags. Check 5 defaults omit the
    grey ``d_v`` / ``d_v cot θ_v`` teaching overlay; Step 7 passes ``show_shear_teaching_overlay=True``
    for that construction only. When the mean crack guideline is enabled, the green path is a
    parallel offset (normal to the path) of the crack’s smooth arched Bézier centreline (same
    backbone as the black crack, without jag). With ``show_mean_green_flow_pulse`` and
    ``show_compression_resultant``, the pulse follows one
    continuous path: top of **C** → down **C** → green transfer curve (tip to Ast) → **Ast** tie
    toward the support (same MCFT dashed + sliding-window animation). Otherwise the pulse is green-only
    or hidden when the pulse flag is off (solid green + optional tangent arrows). Black normal arrows
    are unchanged. The θ marker at the
    toe shows the angle from the bottom beam edge to the *drawn* crack tangent (not the nominal MCFT
    input). All stirrups render as one dark grey.

    ``show_mcft_mechanism_labels`` (Check 5): adds italic subscript labels ``V_cr``, ``V_ca``,
    ``V_cc``, ``V_d`` beside the crack, green strut, compression block, and tie; geometry unchanged.

    ``web_crushing_stm`` (Check 9): same beam/support/inset/stirrups/Ast as Checks 5/7, but omits the
    MCFT crack/green path and draws a D-region strut-and-tie overlay (red strut, tie at Ast) for the
    web-crushing schematic.
    """
    fig = go.Figure()
    mean_green_for_flow: list[tuple[float, float]] = []
    flow_c_cx: float | None = None
    flow_c_y_top: float | None = None
    flow_c_y_bot: float | None = None
    shape_kind, dims = _check6_shape_kind_and_dims(layout)
    D = max(float(D_mm), 1.0)
    d_use = max(float(d_mm), 0.01 * D)
    d_v_use = float(d_v_mm) if d_v_mm is not None else d_use
    d_v_use = max(d_v_use, 0.05 * D, 1.0)
    L_d_core = max(1.5 * d_use, min(2.0 * d_use, 0.52 * D))
    L_span_extra = max(0.5 * d_use, min(1.0 * d_use, 0.30 * D))
    # D-depth stays per formulas; flexural-shear leg lengthened by a fixed factor (no L_seg squeeze).
    flex_leg_scale = 2.75
    L_raw = float(L_d_core) + float(L_span_extra) * flex_leg_scale
    L_seg_cap = max(4.25 * d_use, 1.22 * D, L_raw)
    L_seg = max(2.0 * d_use, min(L_raw, L_seg_cap))

    inset_pts_uv, width_sec = _check6_section_inset_polygon_uv(shape_kind, dims)
    width_sec = max(float(width_sec), 1.0)
    inset_span_mm = min(
        width_sec,
        max(0.52 * L_seg, 0.45 * d_use, 0.30 * D, 200.0),
    )
    inset_span_mm *= 0.5
    # Slightly wider grey band toward the span (left when inset is on the right, etc.).
    grey_extend_mm = max(0.062 * L_seg, 0.09 * D, 32.0)
    grey_span_mm = min(inset_span_mm + grey_extend_mm, 0.90 * L_seg)

    reo = (layout or {}).get("reo") or {}
    try:
        cover_bot = float(reo.get("cover_bot", 40.0))
        cover_top = float(reo.get("cover_top", 40.0))
        db_bot = float(reo.get("db_bot", reo.get("db_bot_1", 20.0)))
        db_top = float(reo.get("db_top", reo.get("db_top_1", 16.0)))
    except Exception:
        cover_bot, cover_top, db_bot, db_top = 40.0, 40.0, 20.0, 16.0

    ms = str(moment_sign or "positive").strip().lower()
    fallback_y = (
        D - cover_bot - 0.5 * db_bot if ms != "negative" else cover_top + 0.5 * db_top
    )
    layer_geom = resolve_bending_layer_geometry(
        layout,
        moment_sign=str(moment_sign or "positive"),
        D=D,
        fallback_y_tension=fallback_y,
    )
    y_tension_v = float(layer_geom["y_tension_centroid"])
    tension_face = str(layer_geom["tension_face"])
    compression_face = str(layer_geom["compression_face"])

    y_steel = _check6_y_display(D, y_tension_v)

    side_n = str(critical_support_side or "left").strip().lower()
    if side_n not in ("left", "right", "internal"):
        side_n = "left"

    # x_fs: 0 at support face, increases into the governing shear span (same convention for all cases).
    if side_n == "internal":
        x_sup_disp = 0.5 * L_seg

        def x_disp(x_fs: float) -> float:
            return x_sup_disp + float(x_fs)

        support_X = x_sup_disp
        inset_on_right = True
    elif side_n == "right":

        def x_disp(x_fs: float) -> float:
            return L_seg - float(x_fs)

        support_X = L_seg
        inset_on_right = False
    else:

        def x_disp(x_fs: float) -> float:
            return float(x_fs)

        support_X = 0.0
        inset_on_right = True

    yt = _check6_y_display(D, 0.0)
    yb = _check6_y_display(D, D)
    y_top_beam, y_bot_beam = yt, yb

    # Flexural-shear fill: vertical leading edge at crack toe x (same x as crack origin below).
    pad_x_toe = max(0.012 * L_seg, 0.04 * d_use, 8.0)
    margin_y = max(0.006 * D, 1.5)
    x_fs_boundary = float(L_d_core)
    if str(tension_face).strip().lower() == "bottom":
        y_toe = float(y_bot_beam) + margin_y
    else:
        y_toe = float(y_top_beam) - margin_y
    if side_n == "internal":
        x_toe = float(support_X) - x_fs_boundary
    else:
        x_toe = float(x_disp(x_fs_boundary))
    x_toe = min(max(x_toe, pad_x_toe), float(L_seg) - pad_x_toe)

    if inset_on_right:
        flex_x0 = float(x_toe)
        flex_span = max(float(L_seg) - flex_x0, max(0.02 * float(L_seg), 1.0))
    else:
        flex_x0 = 0.0
        flex_span = float(grey_span_mm)

    def xf_sect(u: float) -> float:
        return flex_x0 + (float(u) / width_sec) * flex_span

    def add_path_raw(path: str, *, width: float = 2, color: str = "#1f2a44", fill: str = "rgba(0,0,0,0)"):
        fig.add_shape(
            type="path",
            path=path,
            line=dict(color=color, width=width),
            fillcolor=fill,
        )

    def path_from_points_disp(xy: list[tuple[float, float]], close: bool = False) -> str:
        parts: list[str] = []
        for i, (xa, ya) in enumerate(xy):
            parts.append(f"{'M' if i == 0 else 'L'} {float(xa):.4f},{ya:.4f}")
        if close:
            parts.append("Z")
        return " ".join(parts)

    inset_xy_disp = [(xf_sect(u), _check6_y_display(D, v)) for u, v in inset_pts_uv]
    # Filled section only — no stroked outline (avoids vertical web / flange lines in the sketch).
    add_path_raw(
        path_from_points_disp(inset_xy_disp, close=True),
        width=0,
        color="rgba(0,0,0,0)",
        fill="rgba(31,42,68,0.10)",
    )

    beam_outline = "#1f2a44"
    add_path_raw(
        path_from_points_disp([(0.0, yt), (L_seg, yt), (L_seg, yb), (0.0, yb)], close=True),
        width=2,
        color=beam_outline,
        fill="rgba(0,0,0,0)",
    )

    if shape_kind == "T":
        tf = float(dims["tf"])
        y_int = _check6_y_display(D, tf)
        fig.add_shape(
            type="line",
            x0=0.0,
            y0=y_int,
            x1=L_seg,
            y1=y_int,
            line=dict(color="rgba(31,42,68,0.35)", width=1, dash="dot"),
        )
    elif shape_kind == "I":
        tf = float(dims["tf"])
        y_top_int = _check6_y_display(D, tf)
        y_bot_int = _check6_y_display(D, D - tf)
        fig.add_shape(
            type="line",
            x0=0.0,
            y0=y_top_int,
            x1=L_seg,
            y1=y_top_int,
            line=dict(color="rgba(31,42,68,0.35)", width=1, dash="dot"),
        )
        fig.add_shape(
            type="line",
            x0=0.0,
            y0=y_bot_int,
            x1=L_seg,
            y1=y_bot_int,
            line=dict(color="rgba(31,42,68,0.35)", width=1, dash="dot"),
        )

    cage_y0, cage_y1 = _check6_shear_cage_y_range_mm(
        layout=layout,
        shape_kind=shape_kind,
        dims=dims,
        reo=reo,
        D=D,
        lig_d=float(lig_d_mm),
        lig_legs=int(lig_legs),
    )
    y_stirr_top = _check6_y_display(D, cage_y0)
    y_stirr_bot = _check6_y_display(D, cage_y1)
    stirrup_color = "rgba(52,52,56,0.92)"
    draw_stirrups = _check6_shear_ligatures_active(
        s_mm=float(s_lig_mm), lig_legs=int(lig_legs), asv_mm2=asv_mm2
    )

    ast_blue = "#1565c0"
    tie_x0_fs = max(0.06 * L_seg, 0.05 * d_use)
    tie_x1_fs = min(0.94 * L_seg, L_seg - 0.04 * d_use)
    fig.add_shape(
        type="line",
        x0=x_disp(tie_x0_fs),
        y0=y_steel,
        x1=x_disp(tie_x1_fs),
        y1=y_steel,
        line=dict(color=ast_blue, width=3),
    )

    # ULS d_n for NA / small C marker only (crack does not terminate at C or the support face).
    b_mm = float(dims.get("b", width_sec))
    Ast_t = _check6_tension_ast_mm2(layout, tension_face)
    dn_mm: float
    if (
        fc_mpa is not None
        and fsy_mpa is not None
        and Ast_t > 1e-6
        and math.isfinite(float(fc_mpa))
        and math.isfinite(float(fsy_mpa))
    ):
        dn_mm = _check6_uls_dn_mm(
            fc_mpa=float(fc_mpa),
            b_mm=b_mm,
            fsy_mpa=float(fsy_mpa),
            Ast_mm2=Ast_t,
        )
    else:
        dn_mm = float("nan")
    if not math.isfinite(dn_mm) or dn_mm <= 0:
        dn_mm = max(0.12 * D, 0.35 * min(d_use, D))
    dn_mm = max(1.0, min(float(D) - 1.0, float(dn_mm)))
    v_na = _check6_v_na_from_dn_mm(D=D, dn_mm=dn_mm, compression_face=compression_face)
    c_y_line = _check6_y_display(D, v_na)
    delta_cz = max(0.012 * D, 3.0)

    if side_n == "right":
        support_face_x = float(L_seg)
    elif side_n == "internal":
        support_face_x = float(support_X)
    else:
        support_face_x = 0.0

    # x_toe / y_toe: same as above (crack origin at D-region boundary).

    theta_use_deg = float(theta_v_deg) if theta_v_deg is not None else 36.0
    theta_use_rad = math.radians(max(1.0, min(theta_use_deg, 89.0)))
    ux, uy = _check6_unit_toe_to_tip_crack(
        support_side=side_n,
        tension_face=tension_face,
        theta_v_rad=theta_use_rad,
    )

    if compression_face == "top":
        y_tip_tgt = min(
            y_top_beam - 0.035 * D,
            c_y_line + 1.35 * max(delta_cz, 0.01 * D),
        )
    else:
        y_tip_tgt = max(
            y_bot_beam + 0.035 * D,
            c_y_line - 1.35 * max(delta_cz, 0.01 * D),
        )
    y_tip_tgt = min(
        max(y_tip_tgt, y_bot_beam + 0.04 * D),
        y_top_beam - 0.04 * D,
    )

    if abs(uy) > 1e-6:
        t_geom = (float(y_tip_tgt) - float(y_toe)) / uy
        x_tip = float(x_toe) + t_geom * ux
        y_tip = float(y_toe) + t_geom * uy
    else:
        x_tip = float(x_toe) + 0.45 * float(L_seg) * (1.0 if ux > 0 else -1.0)
        y_tip = float(y_tip_tgt)

    pad_span = max(0.035 * L_seg, 0.05 * d_use, 8.0)
    if side_n == "left":
        x_tip = min(max(x_tip, x_toe + pad_span), L_seg - pad_span)
    elif side_n == "right":
        x_tip = max(min(x_tip, x_toe - pad_span), pad_span)
    else:
        if ux < -1e-9:
            x_tip = max(pad_span, min(x_tip, x_toe - pad_span))
        else:
            x_tip = min(L_seg - pad_span, max(x_tip, x_toe + pad_span))

    if abs(ux) > 1e-9:
        y_tip = float(y_toe) + (float(x_tip) - float(x_toe)) / ux * uy
        y_tip = min(max(y_tip, y_bot_beam + 0.02 * D), y_top_beam - 0.02 * D)

    x_toe = float(x_toe)
    y_toe = float(y_toe)
    x_tip = float(x_tip)
    y_tip = float(y_tip)

    uln = math.hypot(ux, uy)
    if uln > 1e-9:
        ux, uy = ux / uln, uy / uln

    web_stm = bool(web_crushing_stm)
    if web_stm:
        show_mean_crack_guideline = False
        show_mean_green_flow_pulse = False
        show_mean_green_flow_arrows = False
        show_green_strut_flow = False
        show_compression_resultant = False
        show_shear_teaching_overlay = False
        show_mcft_mechanism_labels = False
        show_region_labels = False

    crack_geom = None
    crack_pts: list[tuple[float, float]] = []
    if not web_stm:
        crack_geom = _check6_crack_bezier_setup(
            x_toe,
            y_toe,
            x_tip,
            y_tip,
            tension_face=tension_face,
            D_mm=D,
            bulge_scale=float(crack_bulge_scale),
        )
        if crack_geom is None:
            crack_geom = _check6_collinear_bezier_geom_from_chord(
                x_toe, y_toe, x_tip, y_tip
            )

        crack_pts = _check6_soft_crack_polyline(
            x_toe,
            y_toe,
            x_tip,
            y_tip,
            tension_face=tension_face,
            D_mm=D,
            bulge_scale=float(crack_bulge_scale),
            jag_scale=float(crack_jag_scale),
        )
    # θ arc/label: governing θ_v from check (toe→tip unit vector), not the jagged polyline.
    theta_lbl_x = float(x_toe)
    theta_lbl_y = float(y_toe)
    if not web_stm:
        tdx, tdy = float(ux), float(uy)
        if str(tension_face).strip().lower() == "bottom":
            if side_n == "right":
                edx, edy = -1.0, 0.0
            elif side_n == "internal" and float(ux) < -1e-9:
                edx, edy = -1.0, 0.0
            else:
                edx, edy = 1.0, 0.0
        else:
            if side_n == "right":
                edx, edy = -1.0, 0.0
            elif side_n == "internal" and float(ux) < -1e-9:
                edx, edy = -1.0, 0.0
            else:
                edx, edy = 1.0, 0.0
        a_edge = math.atan2(edy, edx)
        a_tan = math.atan2(tdy, tdx)
        da = (a_tan - a_edge + math.pi) % (2 * math.pi) - math.pi
        if da > math.pi / 2:
            da -= 2 * math.pi
        elif da < -math.pi / 2:
            da += 2 * math.pi
        a_arc0 = a_edge
        a_arc1 = a_edge + da
        r_arc = max(0.036 * D, 0.026 * L_seg, 12.0)
        n_theta = 10
        arc_pts_theta: list[tuple[float, float]] = []
        for i in range(n_theta + 1):
            tt = i / n_theta
            aa = a_arc0 + tt * (a_arc1 - a_arc0)
            arc_pts_theta.append(
                (x_toe + r_arc * math.cos(aa), y_toe + r_arc * math.sin(aa))
            )
        arc_path = _check6_polyline_to_path_svg(arc_pts_theta)
        if arc_path:
            fig.add_shape(
                type="path",
                path=arc_path,
                line=dict(color="rgba(46,105,65,0.58)", width=1.35),
            )
        am = a_arc0 + 0.34 * (a_arc1 - a_arc0)
        r_lbl = r_arc * 1.45
        theta_shift_x = max(0.058 * D, 40.0)
        theta_lbl_x = x_toe + r_lbl * math.cos(am) + theta_shift_x
        theta_lbl_y = y_toe + r_lbl * math.sin(am)
        theta_lbl_x = min(float(theta_lbl_x), float(L_seg) - max(0.018 * L_seg, 10.0))
        fig.add_annotation(
            x=theta_lbl_x,
            y=theta_lbl_y,
            text=f"θ = {float(theta_use_deg):.1f}°",
            showarrow=False,
            font=dict(size=8, color="rgba(20,70,35,0.92)"),
            xref="x",
            yref="y",
        )

    if not web_stm:
        crack_d = _check6_polyline_to_path_svg(crack_pts)
        if crack_d:
            fig.add_shape(
                type="path",
                path=crack_d,
                line=dict(color="#111111", width=2),
            )

    t_ray = math.hypot(x_tip - x_toe, y_tip - y_toe)
    stirrup_xs_hit: list[float] = []
    stirrup_xd_list: list[float] = []
    if draw_stirrups:
        for xs_fs in _check6_stirrup_xs_mm(
            L_seg_mm=float(L_seg), s_mm=float(s_lig_mm), max_lines=28
        ):
            xd = x_disp(xs_fs)
            stirrup_xd_list.append(float(xd))
            if show_shear_teaching_overlay:
                hit = _check6_crack_ray_hits_vertical_stirrup(
                    xd,
                    x_toe,
                    y_toe,
                    ux,
                    uy,
                    y_stirr_bot,
                    y_stirr_top,
                    t_ray,
                )
                if hit:
                    stirrup_xs_hit.append(xd)
            fig.add_shape(
                type="line",
                x0=xd,
                y0=y_stirr_bot,
                x1=xd,
                y1=y_stirr_top,
                line=dict(color=stirrup_color, width=1.25),
            )

    if show_mean_crack_guideline:
        smooth_backbone = _check6_smooth_crack_polyline(
            x_toe,
            y_toe,
            x_tip,
            y_tip,
            tension_face=tension_face,
            D_mm=D,
            n=80,
            bulge_scale=float(crack_bulge_scale),
        )
        mean_green_offset_pts = []
        if smooth_backbone:
            ggap = max(0.026 * D, 17.0, 0.0095 * float(L_seg))
            mean_green_offset_pts = _check6_polyline_offset_toward_compression(
                smooth_backbone,
                gap_mm=ggap,
                compression_face=compression_face,
                D_mm=D,
                L_seg_mm=float(L_seg),
                y_bot=y_bot_beam,
                y_top=y_top_beam,
                normal_sign=-1.0,
            )
        if len(mean_green_offset_pts) >= 2:
            mean_tr, _, _ = _check6_trim_polyline_at_ast_elevation(
                mean_green_offset_pts,
                y_ast=float(y_steel),
                tension_face=tension_face,
            )
            if len(mean_tr) >= 2:
                mean_green_offset_pts = mean_tr
        if len(mean_green_offset_pts) >= 2:
            mean_green_for_flow = list(mean_green_offset_pts)
            use_pulse = bool(show_mean_green_flow_pulse)
            if not use_pulse:
                pg_mean = _check6_polyline_to_path_svg(mean_green_offset_pts)
                if pg_mean:
                    fig.add_shape(
                        type="path",
                        path=pg_mean,
                        line=dict(
                            color="#2e7d32",
                            width=2.1,
                            dash="12px,10px",
                        ),
                    )
            if (
                bool(show_mean_green_flow_arrows)
                and len(mean_green_offset_pts) >= 5
            ):
                _check6_add_green_black_flow_arrows_on_polyline(
                    fig,
                    mean_green_offset_pts,
                    D_mm=D,
                    L_seg_mm=float(L_seg),
                    y_bot=y_bot_beam,
                    y_top=y_top_beam,
                    show_green_tangent_arrows=not use_pulse,
                )

    if not web_stm:
        green_pts = [
            (
                x_toe + (x_tip - x_toe) * (i / 72.0),
                y_toe + (y_tip - y_toe) * (i / 72.0),
            )
            for i in range(73)
        ]
        green_pts, green_t0, green_n = _check6_trim_polyline_at_ast_elevation(
            green_pts, y_ast=y_steel, tension_face=tension_face
        )
    else:
        green_pts = []
        green_t0, green_n = 0.0, 1.0
    green_shift = max(0.088 * D, 58.0)
    if (
        show_green_strut_flow
        and len(green_pts) >= 4
        and crack_geom is not None
    ):
        _check6_add_green_ccw_flow_on_polyline(
            fig,
            green_pts,
            x_shift_mm=green_shift,
            D_mm=D,
            L_seg_mm=float(L_seg),
            y_bot=y_bot_beam,
            y_top=y_top_beam,
            crack_bezier_geom=crack_geom,
            wall_x_mm=None,
            wall_at_start=False,
            suppress_wall_extension_at_tension=True,
            bezier_t_index_offset=green_t0,
            bezier_n_orig=green_n,
            y_ast_clip=float(y_steel),
            ast_clip_tension_face=tension_face,
        )

    teach_col = "rgba(55,71,79,0.85)"
    if (
        show_shear_teaching_overlay
        and draw_stirrups
        and str(tension_face).strip().lower() == "bottom"
        and math.tan(theta_use_rad) > 1e-6
    ):
        cot_t = 1.0 / math.tan(theta_use_rad)
        k_fit = 1.0
        horiz_need = float(d_v_use) * cot_t
        if horiz_need > 0.46 * float(L_seg):
            k_fit = (0.46 * float(L_seg)) / horiz_need
        dvv = float(d_v_use) * k_fit
        horiz_run_mm = dvv * cot_t
        xh_dir = 1.0 if ux >= 0.0 else -1.0
        beam_h = abs(y_bot_beam - y_top_beam)
        sign_up = -1.0 if y_top_beam < y_toe else 1.0
        step_v = min((dvv / D) * beam_h, abs(y_toe - y_top_beam) * 0.88)
        x_v1, y_v1 = x_toe, y_toe + sign_up * step_v
        x_h1, y_h1 = x_v1 + xh_dir * horiz_run_mm, y_v1
        fig.add_shape(
            type="line",
            x0=x_toe,
            y0=y_toe,
            x1=x_v1,
            y1=y_v1,
            line=dict(color=teach_col, width=1.25, dash="dot"),
        )
        fig.add_shape(
            type="line",
            x0=x_v1,
            y0=y_v1,
            x1=x_h1,
            y1=y_h1,
            line=dict(color=teach_col, width=1.25, dash="dot"),
        )
        fig.add_annotation(
            x=0.5 * (x_toe + x_v1) - 0.018 * D,
            y=0.5 * (y_toe + y_v1),
            text="<i>d<sub>v</sub></i>",
            showarrow=False,
            font=dict(size=8, color=teach_col),
        )
        fig.add_annotation(
            x=0.5 * (x_v1 + x_h1),
            y=y_v1 + (0.022 * D if sign_up < 0 else -0.022 * D),
            text="<i>d<sub>v</sub> cot θ<sub>v</sub></i>",
            showarrow=False,
            font=dict(size=8, color=teach_col),
        )
        n_pred = float(d_v_use) * cot_t / max(float(s_lig_mm), 1.0)
        n_hit = len(stirrup_xs_hit)
        n_line = (
            f"<i>n</i> ≈ <i>d<sub>v</sub> cot θ<sub>v</sub> / s</i> "
            f"≈ {n_pred:.1f} stirrup sets &nbsp;|&nbsp; crossed: {n_hit}"
        )
        fig.add_annotation(
            x=0.5 * (x_toe + x_tip),
            y=float(y_bot_beam) - max(0.044 * D, 22.0),
            text=n_line + "<br><span style=\"font-size:8px\">"
            "<i>V</i><sub>s</sub> ∝ <i>A</i><sub>sv</sub> <i>f</i><sub>sy</sub> "
            "(<i>d</i><sub>v</sub> cot θ<sub>v</sub> / <i>s</i>) — schematic</span>",
            showarrow=False,
            font=dict(size=9, color="rgba(31,42,68,0.80)"),
            xanchor="center",
            yanchor="top",
            align="center",
        )

    sup_kind_raw = str(support_draw_kind or "pinned")
    y_ground, node_x = _check6_draw_support_symbol(
        fig,
        x_ref=support_X,
        y_beam_bottom=y_bot_beam,
        D=D,
        kind=sup_kind_raw,
        L_seg_mm=float(L_seg),
    )
    # Compression C: starts at top fibre (sagging) or bottom fibre (hogging); lower/upper end ties to crack tip
    # where possible; span-ward x from crack tip.
    c_red = "#c41e3a"
    c_span_x = max(0.024 * L_seg, 13.0)
    min_c_depth = max(0.040 * D, 14.0)
    min_gap = max(0.018 * D, 8.0)
    y_tip_f = float(y_tip)
    if show_compression_resultant:
        if tension_face == "bottom":
            y_c_top = y_top_beam - max(0.015 * D, 5.0)
            if y_c_top - y_tip_f >= min_gap:
                y_c_bot = max(y_bot_beam + 0.02 * D, y_tip_f)
            else:
                y_c_bot = y_c_top - min_c_depth
                y_c_bot = max(y_bot_beam + 0.02 * D, y_c_bot)
            if side_n == "right":
                cx_c = max(pad_x_toe, float(x_tip) - c_span_x)
                c_lbl_x = cx_c - 0.078 * D
                c_xanchor = "right"
            elif side_n == "internal":
                cx_c = max(pad_x_toe, float(x_tip) - 0.68 * c_span_x)
                c_lbl_x = cx_c - 0.078 * D
                c_xanchor = "right"
            else:
                cx_c = min(float(L_seg) - pad_x_toe, float(x_tip) + c_span_x)
                c_lbl_x = cx_c - 0.078 * D
                c_xanchor = "right"
        else:
            y_c_bot = y_bot_beam + max(0.015 * D, 5.0)
            y_c_top = max(y_c_bot + min_gap, y_tip_f)
            y_c_top = min(y_c_top, y_top_beam - max(0.015 * D, 5.0))
            if y_c_top - y_c_bot < min_c_depth:
                y_c_top = y_c_bot + min_c_depth
                y_c_top = min(y_c_top, y_top_beam - max(0.012 * D, 4.0))
            if side_n == "right":
                cx_c = max(pad_x_toe, float(x_tip) - c_span_x)
                c_lbl_x = cx_c - 0.078 * D
                c_xanchor = "right"
            elif side_n == "internal":
                cx_c = max(pad_x_toe, float(x_tip) - 0.68 * c_span_x)
                c_lbl_x = cx_c - 0.078 * D
                c_xanchor = "right"
            else:
                cx_c = min(float(L_seg) - pad_x_toe, float(x_tip) + c_span_x)
                c_lbl_x = cx_c - 0.078 * D
                c_xanchor = "right"
        if y_c_bot >= y_c_top - 1e-6:
            y_c_bot = min(y_c_top - min_c_depth, y_c_top - 0.015 * D)
            y_c_bot = max(y_bot_beam + 0.02 * D, y_c_bot)
        flow_c_cx = float(cx_c)
        flow_c_y_top = float(y_c_top)
        flow_c_y_bot = float(y_c_bot)
        fig.add_shape(
            type="line",
            x0=cx_c,
            y0=y_c_bot,
            x1=cx_c,
            y1=y_c_top,
            line=dict(color=c_red, width=2.2),
        )
        fig.add_annotation(
            x=c_lbl_x,
            y=0.5 * (y_c_top + y_c_bot),
            text="<b>C</b>",
            showarrow=False,
            font=dict(size=11, color=c_red),
            xanchor=c_xanchor,
        )
        # Horizontal compression-direction cue (+x), upper part of the compression block
        _cz_top = float(y_c_top)
        _cz_bot = float(y_c_bot)
        _arr_y = _cz_top - max(0.026 * D, 10.0)
        _arr_y = min(
            max(_arr_y, _cz_bot + max(0.016 * D, 6.0)),
            _cz_top - max(0.006 * D, 2.5),
        )
        _arr_len = max(0.11 * L_seg, 0.21 * D, 38.0)
        _x_head = min(
            float(L_seg) - max(0.055 * L_seg, pad_x_toe),
            max(float(cx_c) + 0.14 * L_seg, 0.24 * L_seg),
        )
        _x_tail = max(float(pad_x_toe), _x_head - _arr_len)
        if _x_head > _x_tail + 1.0:
            fig.add_annotation(
                x=_x_head,
                y=_arr_y,
                ax=_x_tail,
                ay=_arr_y,
                xref="x",
                yref="y",
                axref="x",
                ayref="y",
                text="",
                showarrow=True,
                arrowhead=2,
                arrowsize=1.05,
                arrowwidth=2.8,
                arrowcolor=c_red,
            )
    fig.add_annotation(
        x=x_disp(min(0.20 * L_d_core, 0.14 * L_seg)),
        y=y_steel,
        ax=x_disp(min(0.88 * L_seg, L_seg - 0.06 * d_use)),
        ay=y_steel,
        xref="x",
        yref="y",
        axref="x",
        ayref="y",
        text="",
        showarrow=True,
        arrowhead=2,
        arrowsize=1.0,
        arrowwidth=2.5,
        arrowcolor=ast_blue,
    )
    ast_inset_fs = max(0.07 * L_seg, 0.06 * d_use, 22.0)
    if side_n == "right":
        ast_lbl_x = x_disp(L_seg - ast_inset_fs)
    elif side_n == "internal":
        ast_lbl_x = x_disp(-min(0.13 * L_seg, 0.42 * L_seg))
    else:
        ast_lbl_x = x_disp(ast_inset_fs)
    if not web_stm:
        fig.add_annotation(
            x=ast_lbl_x,
            y=y_steel + (0.05 * D if tension_face == "bottom" else -0.05 * D),
            text="<b>Ast</b>",
            showarrow=False,
            font=dict(size=13, color=ast_blue),
            xanchor="left",
        )

    if web_stm:
        _check6_add_web_crushing_stm_overlay(
            fig,
            D=D,
            L_seg=float(L_seg),
            support_face_x=float(support_face_x),
            x_toe=float(x_toe),
            y_toe=float(y_toe),
            y_steel=float(y_steel),
            y_top_beam=float(y_top_beam),
            y_bot_beam=float(y_bot_beam),
            tension_face=str(tension_face),
            side_n=str(side_n),
            theta_v_deg=float(theta_use_deg),
            pad_x_toe=float(pad_x_toe),
        )

    if (
        show_mean_crack_guideline
        and bool(show_mean_green_flow_pulse)
        and len(mean_green_for_flow) >= 2
    ):
        if (
            show_compression_resultant
            and flow_c_cx is not None
            and flow_c_y_top is not None
            and flow_c_y_bot is not None
        ):
            flow_combined, flow_seg = _check6_build_shear_transfer_flow_combined_pts(
                cx_c=float(flow_c_cx),
                y_c_top=float(flow_c_y_top),
                y_c_bottom=float(flow_c_y_bot),
                mean_green_pts=mean_green_for_flow,
                y_steel=float(y_steel),
                tie_xa=float(x_disp(tie_x0_fs)),
                tie_xb=float(x_disp(tie_x1_fs)),
                support_face_x=float(support_face_x),
                D=float(D),
                L_seg=float(L_seg),
            )
            if len(flow_combined) >= 3:
                _check6_add_mcft_style_flow_pulse(
                    fig,
                    flow_combined,
                    color="rgba(46,125,50,0.95)",
                    reverse_along_path=False,
                    flow_segment_ends=flow_seg,
                    flow_arrowhead=True,
                    line_shape="linear",
                )
        else:
            _check6_add_mcft_style_flow_pulse(
                fig,
                mean_green_for_flow,
                color="rgba(46,125,50,0.95)",
                reverse_along_path=True,
                flow_arrowhead=True,
            )

    # Region labels below the beam soffit (display y < y_bot_beam; y increases upward).
    if show_region_labels:
        y_reg_lbl = float(y_bot_beam) - max(0.056 * D, 28.0)
        reg_font = dict(size=10, color="rgba(31,42,68,0.88)")
        L_rem = max(L_seg - L_d_core, 0.08 * L_seg)
        if side_n == "right":
            x_d_reg = x_disp(0.52 * L_d_core)
            x_f_reg = x_disp(L_d_core + 0.50 * L_rem)
        elif side_n == "internal":
            x_d_reg = support_X + 0.42 * min(L_d_core, max(L_seg - support_X, 1.0) * 0.92)
            x_f_reg = max(0.06 * L_seg, support_X * 0.42)
        else:
            x_d_reg = x_disp(0.48 * L_d_core)
            x_f_reg = x_disp(L_d_core + 0.50 * L_rem)
        fig.add_annotation(
            x=x_d_reg,
            y=y_reg_lbl,
            text="D-region",
            showarrow=False,
            font=reg_font,
            xanchor="center",
            yanchor="top",
        )
        fig.add_annotation(
            x=x_f_reg,
            y=y_reg_lbl,
            text="Flexural shear<br>region",
            showarrow=False,
            font=reg_font,
            xanchor="center",
            yanchor="top",
        )

    if (
        bool(show_mcft_mechanism_labels)
        and bool(show_compression_resultant)
        and bool(show_mean_crack_guideline)
        and len(mean_green_for_flow) >= 2
        and len(crack_pts) >= 3
        and flow_c_cx is not None
        and flow_c_y_top is not None
        and flow_c_y_bot is not None
    ):
        _check6_add_mcft_mechanism_labels(
            fig,
            D=float(D),
            L_seg=float(L_seg),
            L_d_core=float(L_d_core),
            crack_pts=crack_pts,
            mean_green_pts=list(mean_green_for_flow),
            theta_lbl_x=float(theta_lbl_x),
            theta_lbl_y=float(theta_lbl_y),
            cx_c=float(flow_c_cx),
            y_c_top=float(flow_c_y_top),
            y_c_bot=float(flow_c_y_bot),
            y_steel=float(y_steel),
            ast_lbl_x=float(ast_lbl_x),
            ast_arrow_x0=float(x_disp(min(0.20 * L_d_core, 0.14 * L_seg))),
            ast_arrow_x1=float(x_disp(min(0.88 * L_seg, L_seg - 0.06 * d_use))),
            tension_face=str(tension_face),
            side_n=str(side_n),
            y_bot_beam=float(y_bot_beam),
            y_top_beam=float(y_top_beam),
            y_stirr_bot=float(y_stirr_bot),
            y_stirr_top=float(y_stirr_top),
            stirrup_xds=stirrup_xd_list,
            show_region_labels=bool(show_region_labels),
            support_X=float(support_X),
            x_disp=x_disp,
        )

    ymin = y_ground - 0.14 * D
    ymax = y_top_beam + 0.22 * D
    xpad = 0.06 * (L_seg + 0.12 * D)
    xmin_plot = min(-0.10 * D, x_toe - 0.10 * D)
    if show_compression_resultant and side_n != "right":
        xmin_plot = min(xmin_plot, float(c_lbl_x) - 0.06 * D)
    if web_stm:
        flow_pad = max(0.18 * D, 0.06 * float(L_seg))
    else:
        flow_pad = (
            max(float(green_shift), 0.22 * D)
            if (show_green_strut_flow or show_mean_crack_guideline)
            else max(0.18 * D, 0.06 * float(L_seg))
        )
    xmax_plot = L_seg + flow_pad + 0.16 * D
    if side_n == "right":
        if show_compression_resultant:
            xmax_plot = max(xmax_plot, float(c_lbl_x) + 0.12 * D, x_tip + 0.10 * D)
        else:
            xmax_plot = max(xmax_plot, x_tip + 0.10 * D)
    xpad_right = xpad + 0.038 * D
    fig.update_xaxes(
        visible=False,
        range=[xmin_plot - xpad, xmax_plot + xpad_right],
        fixedrange=True,
    )
    fig.update_yaxes(
        visible=False,
        range=[ymin - 0.03 * D, ymax + 0.04 * D],
        fixedrange=True,
    )
    fig.update_layout(
        height=height,
        margin=dict(l=0, r=0, t=0, b=0),
        paper_bgcolor="white",
        plot_bgcolor="white",
        showlegend=False,
    )
    return fig


def build_torsion_plotly_figure(
    *,
    torsion_design_required: bool = True,
    L_mm: float | None = None,
    b_mm: float | None = None,
    D_mm: float | None = None,
    theta_crack_deg: float = 45.0,
    cam_a: float = -0.65,
    cam_b: float = 0.28,
) -> go.Figure:
    """
    Pseudo-3D torsion schematic using the same oblique ``proj`` as
    ``draw_face_label_debug`` / ``plot_shear_step1_theta_cracks_3d``.

    Parallel bands ``s = m·y + c`` on the developed strip (``y`` = beam length,
    ``m = tan θ``): each band is sampled along ``y``, mapped with ``(x,z) = f(s mod P)``,
    and only visible stretches are drawn as one polyline—no per-face stitching.

    Model axes (metres): x = breadth *b*, y = span *L*, z = depth *D*.

    When torsion design is not required, keep a lighter/fewer wrapped crack set
    for schematic continuity, with a subdued θ marker.
    """
    L_span_mm = float(L_mm if L_mm is not None else 8000.0)
    b_use_mm = float(b_mm if b_mm is not None else 400.0)
    D_use_mm = float(D_mm if D_mm is not None else 600.0)

    L = b_use_mm / 1000.0
    B = L_span_mm / 1000.0
    D = D_use_mm / 1000.0

    theta_use = min(55.0, max(30.0, float(theta_crack_deg)))
    slope_ds_dy = math.tan(math.radians(theta_use))

    if torsion_design_required:
        n_bands = 5
        crack_lw = 1.85
        crack_color = "rgba(14,14,14,0.94)"
        crack_stylize_strength = 1.0
    else:
        n_bands = 3
        crack_lw = 1.12
        crack_color = "rgba(70,70,70,0.42)"
        crack_stylize_strength = 0.55

    # Visible faces (same corner semantics as draw_face_label_debug in this module).
    faces_3d = {
        "end_x0": np.array([[0, B, 0], [0, B, D], [0, 0, D], [0, 0, 0]], dtype=float),
        "roof": np.array([[0, B, D], [L, B, D], [L, 0, D], [0, 0, D]], dtype=float),
        "side_y0": np.array([[0, 0, D], [L, 0, D], [L, 0, 0], [0, 0, 0]], dtype=float),
    }
    draw_order = ["end_x0", "roof", "side_y0"]

    faces_2d = {
        name: np.array([proj(p, a=cam_a, b=cam_b) for p in pts], dtype=float)
        for name, pts in faces_3d.items()
    }

    fig = go.Figure()
    xs_all: list[float] = []
    ys_all: list[float] = []

    edge_color = "#222222"
    for name in draw_order:
        poly = faces_2d[name]
        xs = np.append(poly[:, 0], poly[0, 0])
        ys = np.append(poly[:, 1], poly[0, 1])
        xs_all.extend(xs.tolist())
        ys_all.extend(ys.tolist())
        fig.add_trace(
            go.Scatter(
                x=xs,
                y=ys,
                fill="toself",
                fillcolor="rgba(255,255,255,1)",
                mode="lines",
                line=dict(color=edge_color, width=2.2),
                hoverinfo="skip",
                showlegend=False,
            )
        )

    P = _torsion_section_perimeter(L, D)

    if n_bands > 0:
        for i in range(n_bands):
            c = (i + 0.5) * P / n_bands
            tx, ty = _torsion_band_projected_polyline(
                L,
                B,
                D,
                c,
                slope_ds_dy,
                cam_a,
                cam_b,
                n_samples=560,
                stylize_strength=crack_stylize_strength,
                band_phase=c / max(P, 1e-12),
                end_trim_frac=0.016 if torsion_design_required else 0.012,
            )
            if not tx or all(v is None for v in tx):
                continue
            xs_all.extend([v for v in tx if v is not None])
            ys_all.extend([v for v in ty if v is not None])
            fig.add_trace(
                go.Scatter(
                    x=tx,
                    y=ty,
                    mode="lines",
                    line=dict(width=crack_lw, color=crack_color),
                    hoverinfo="skip",
                    showlegend=False,
                )
            )

        c_theta = None
        best_c: float | None = None
        best_pen = float("inf")
        for i in range(n_bands):
            c = (i + 0.5) * P / n_bands
            y_bot = (P - c) / max(slope_ds_dy, 1e-12)
            if 0.0 <= y_bot <= B:
                c_theta = c
                break
            if y_bot < 0.0:
                pen = -y_bot
            else:
                pen = max(0.0, y_bot - B)
            if pen < best_pen:
                best_pen = pen
                best_c = c
        if c_theta is None and best_c is not None:
            c_theta = best_c
        if c_theta is not None:
            tr_th, ann_th = _torsion_theta_marker_on_bottom_edge(
                L,
                B,
                D,
                c_theta,
                slope_ds_dy,
                cam_a,
                cam_b,
                subdued=not torsion_design_required,
            )
            if tr_th:
                for t in tr_th:
                    fig.add_trace(t)
                    xs_all.extend([v for v in t.x if v is not None])
                    ys_all.extend([v for v in t.y if v is not None])
            if ann_th:
                for ad in ann_th:
                    fig.add_annotation(ad)
                    if ad.get("x") is not None and ad.get("y") is not None:
                        xs_all.append(float(ad["x"]))
                        ys_all.append(float(ad["y"]))

    # Torsion symbol on right visible face (y = 0), in the x–z plane.
    cx_face, cz_face = 0.52 * L, 0.48 * D
    r = 0.145 * min(L, D)
    # Two compact curved arrows wrapped around T (no detached semicircle).
    arc_specs = [(0.35, 2.45), (3.55, 5.65)]
    arr_lw = 2.4 if torsion_design_required else 1.5
    arr_color = "#1a1a1a" if torsion_design_required else "rgba(60,60,60,0.55)"
    ah_len = 0.055 * min(B, D)
    ah_ang = 0.55
    for a0, a1 in arc_specs:
        ang = np.linspace(float(a0), float(a1), max(16, int(24 * (a1 - a0))))
        arc_pts = []
        for t in ang:
            xp = cx_face + r * math.cos(t)
            zp = cz_face + r * math.sin(t)
            p2 = proj(np.array([xp, 0.0, zp], dtype=float), a=cam_a, b=cam_b)
            arc_pts.append((float(p2[0]), float(p2[1])))
        xs_a = [p[0] for p in arc_pts]
        ys_a = [p[1] for p in arc_pts]
        xs_all.extend(xs_a)
        ys_all.extend(ys_a)
        fig.add_trace(
            go.Scatter(
                x=xs_a,
                y=ys_a,
                mode="lines",
                line=dict(width=arr_lw, color=arr_color),
                hoverinfo="skip",
                showlegend=False,
            )
        )
        # Arrowhead at arc end using two short wing segments (engineering-clean).
        x_end = cx_face + r * math.cos(a1)
        z_end = cz_face + r * math.sin(a1)
        # Tangent direction for increasing angle.
        tx = -math.sin(a1)
        tz = math.cos(a1)
        tnorm = max(math.hypot(tx, tz), 1e-12)
        tx /= tnorm
        tz /= tnorm
        for sgn in (-1.0, 1.0):
            wx = x_end - ah_len * (tx * math.cos(ah_ang) + sgn * math.sin(ah_ang))
            wz = z_end - ah_len * (tz * math.cos(ah_ang) + sgn * math.sin(ah_ang))
            p_tip = proj(np.array([x_end, 0.0, z_end], dtype=float), a=cam_a, b=cam_b)
            p_wng = proj(np.array([wx, 0.0, wz], dtype=float), a=cam_a, b=cam_b)
            xh = [float(p_wng[0]), float(p_tip[0])]
            yh = [float(p_wng[1]), float(p_tip[1])]
            xs_all.extend(xh)
            ys_all.extend(yh)
            fig.add_trace(
                go.Scatter(
                    x=xh,
                    y=yh,
                    mode="lines",
                    line=dict(width=max(1.0, arr_lw * 0.9), color=arr_color),
                    hoverinfo="skip",
                    showlegend=False,
                )
            )

    c2 = proj(np.array([cx_face, 0.0, cz_face], dtype=float), a=cam_a, b=cam_b)
    cx, cxy = float(c2[0]), float(c2[1])
    xs_all.append(cx)
    ys_all.append(cxy)
    t_font_color = "#1a1a1a" if torsion_design_required else "#666666"
    fig.add_annotation(
        x=cx,
        y=cxy,
        text="T",
        showarrow=False,
        font=dict(size=20 if torsion_design_required else 16, color=t_font_color),
        xref="x",
        yref="y",
    )

    if xs_all:
        xmin, xmax = min(xs_all), max(xs_all)
        ymin, ymax = min(ys_all), max(ys_all)
        dx = max(xmax - xmin, 1e-6)
        dy = max(ymax - ymin, 1e-6)
        pad = 0.1 * max(dx, dy)
        fig.update_xaxes(
            visible=False,
            showgrid=False,
            zeroline=False,
            scaleanchor="y",
            scaleratio=1,
            range=[xmin - pad, xmax + pad],
        )
        fig.update_yaxes(
            visible=False,
            showgrid=False,
            zeroline=False,
            range=[ymin - pad, ymax + pad],
        )

    fig.update_layout(
        paper_bgcolor="white",
        plot_bgcolor="white",
        margin=dict(l=10, r=10, t=10, b=10),
        hovermode=False,
    )
    return fig

