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
        )

    # Force consistent layout (schematic style)
    fig.update_layout(
        title=None,
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

        if show_labels:
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

        if show_labels:
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

    if show_labels:
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
        
        shear_layout = compute_shear_reo_layout_pure(
            b=b, D=D,
            cover_bot=float(cover_bot), cover_top=float(cover_top), cover_side=float(cover_side),
            lig_d=float(lig_d), lig_legs=int(lig_legs),
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


def make_mcft_longitudinal_strain_profile_fig(
    eps_top_uls: float,
    eps_x_mcft: float,
    eps_bot_uls: float,
    title: str = "Longitudinal strain profile",
    height: int = 840,  # Doubled from 420
):
    """
    Bending-style strain profile diagram for Step 4 MCFT.
    Shows ULS linear strain distribution from top to bottom, with MCFT ε_x at mid-depth.
    
    AS 3600 sign convention: ε < 0 = compression (red), ε > 0 = tension (blue).
    
    Args:
        eps_top_uls: Top fiber strain from ULS bending (compression, negative)
        eps_x_mcft: Mid-depth strain from MCFT (AS 3600 Cl. 8.2.4.2.2)
        eps_bot_uls: Bottom fiber strain from ULS bending (tension, positive)
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

    # Vertical ε=0 axis line (explicitly at x=0)
    # Ends exactly at top and bottom horizontal strain lines
    fig.add_shape(
        type="line",
        x0=0, x1=0,
        y0=y_top, y1=y_bot,  # Starts at top strain line, ends at bottom strain line
        line=dict(width=4, color="black"),
        layer="below",
    )

    # Compute neutral axis depth where ε=0 (ULS linear profile)
    # y_NA = y_top + (y_bot - y_top) * (0 - eps_top) / (eps_bot - eps_top)
    eps_diff = eps_bot_uls - eps_top_uls
    if abs(eps_diff) > 1e-9:
        y_na = y_top + (y_bot - y_top) * (0.0 - eps_top_uls) / eps_diff
        y_na = max(y_top, min(y_bot, y_na))  # Clamp to valid range (y_top=0.0, y_bot=1.0)
    else:
        y_na = None  # No crossing if strains are equal

    # Draw ULS strain profile line: ONLY from top to bottom (two points)
    fig.add_trace(go.Scatter(
        x=[eps_top_uls, eps_bot_uls],
        y=[y_top, y_bot],
        mode="lines",
        line=dict(width=3, color="black"),
        hoverinfo="skip",
        showlegend=False,
    ))

    # Plot MCFT ε_x at mid-depth as a separate marker
    color_mid = "red" if eps_x_mcft < 0 else "blue"
    fig.add_trace(go.Scatter(
        x=[eps_x_mcft],
        y=[y_mid],
        mode="markers",
        marker=dict(size=14, color=color_mid, line=dict(width=2, color="black")),
        hoverinfo="skip",
        showlegend=False,
    ))

    # Dashed horizontal line at mid-depth (MCFT reference depth)
    emax_temp = max(abs(eps_top_uls), abs(eps_x_mcft), abs(eps_bot_uls), 1e-6)
    fig.add_shape(
        type="line",
        x0=-0.5 * emax_temp, y0=y_mid, x1=0.5 * emax_temp, y1=y_mid,
        line=dict(width=1, color="grey", dash="dash"),
        layer="below",
    )

    # Neutral axis marker and label (if it exists within the section)
    if y_na is not None and y_top <= y_na <= y_bot:
        # Faint dashed horizontal line through NA
        fig.add_shape(
            type="line",
            x0=-0.5 * emax_temp, y0=y_na, x1=0.5 * emax_temp, y1=y_na,
            line=dict(width=1, color="rgba(100,100,100,0.5)", dash="dot"),
            layer="below",
        )
        # NA marker at (x=0, y=y_na)
        fig.add_trace(go.Scatter(
            x=[0.0],
            y=[y_na],
            mode="markers",
            marker=dict(size=10, color="black", symbol="diamond"),
            hoverinfo="skip",
            showlegend=False,
        ))
        # NA label
        fig.add_annotation(
            x=0.0, y=y_na,
            text="ε=0 (ULS)",
            showarrow=False,
            font=dict(size=10, color="rgba(70,70,90,0.8)"),
            xanchor="left",
            xshift=8,
            bgcolor="rgba(255,255,255,0.8)",
        )

    # Horizontal depth guides from ε=0 axis to each strain value
    # Color rules: red if compression (ε < 0), blue if tension (ε > 0)
    # Top tick: always red (compression in ULS sagging)
    color_top = "red"
    fig.add_shape(
        type="line",
        x0=0, y0=y_top, x1=eps_top_uls, y1=y_top,
        line=dict(color=color_top, width=2.0),
    )
    
    # Mid-depth tick: red if compression, blue if tension
    color_mid_tick = "red" if eps_x_mcft < 0 else "blue"
    fig.add_shape(
        type="line",
        x0=0, y0=y_mid, x1=eps_x_mcft, y1=y_mid,
        line=dict(color=color_mid_tick, width=2.0),
    )
    
    # Bottom tick: always blue (tension in ULS sagging)
    color_bot = "blue"
    fig.add_shape(
        type="line",
        x0=0, y0=y_bot, x1=eps_bot_uls, y1=y_bot,
        line=dict(color=color_bot, width=2.0),
    )

    # Labels with increased spacing
    emax = max(abs(eps_top_uls), abs(eps_x_mcft), abs(eps_bot_uls), 1e-6)
    label_offset = 0.05 * emax  # Increased from 0.02

    # Top strain label (compression, negative) - red
    if eps_top_uls < 0.0:  # compression (negative) - to the left
        label_x_top = eps_top_uls - label_offset
        xanchor_top = "right"
        state_top = "(compression)"
    else:  # tension (positive) - to the right
        label_x_top = eps_top_uls + label_offset
        xanchor_top = "left"
        state_top = "(tension)"
    fig.add_annotation(
        x=label_x_top, y=y_top,
        text=f"ε<sub>top</sub> = {eps_top_uls:.5f}<br><span style='font-size:10px'>{state_top}</span>",
        showarrow=False,
        font=dict(size=12, color=color_top),
        xanchor=xanchor_top,
        yshift=-14,  # Increased spacing
        bgcolor="rgba(255,255,255,0.85)",  # Increased opacity
    )

    # Mid-depth strain label (MCFT governing value)
    if eps_x_mcft < 0.0:  # compression (negative) - to the left
        label_x_mid = eps_x_mcft - label_offset
        xanchor_mid = "right"
        state_mid = "(compression)"
    else:  # tension (positive) - to the right
        label_x_mid = eps_x_mcft + label_offset
        xanchor_mid = "left"
        state_mid = "(tension)"
    fig.add_annotation(
        x=label_x_mid, y=y_mid,
        text=f"ε<sub>x</sub> = {eps_x_mcft:.5f}<br><span style='font-size:11px'>mid-depth (MCFT)</span><br><span style='font-size:10px'>{state_mid}</span>",
        showarrow=False,
        font=dict(size=12, color=color_mid_tick),
        xanchor=xanchor_mid,
        yshift=0,
        bgcolor="rgba(255,255,255,0.85)",  # Increased opacity
    )

    # Bottom strain label (tension, positive) - blue
    if eps_bot_uls < 0.0:  # compression (negative) - to the left
        label_x_bot = eps_bot_uls - label_offset
        xanchor_bot = "right"
        state_bot = "(compression)"
    else:  # tension (positive) - to the right
        label_x_bot = eps_bot_uls + label_offset
        xanchor_bot = "left"
        state_bot = "(tension)"
    fig.add_annotation(
        x=label_x_bot, y=y_bot,
        text=f"ε<sub>bot</sub> = {eps_bot_uls:.5f}<br><span style='font-size:10px'>{state_bot}</span>",
        showarrow=False,
        font=dict(size=12, color=color_bot),
        xanchor=xanchor_bot,
        yshift=14,  # Increased spacing
        bgcolor="rgba(255,255,255,0.85)",  # Increased opacity
    )

    # Title
    fig.add_annotation(
        xref="paper", yref="paper",
        x=0.5, y=1.06,
        text="<b>Longitudinal strain profile</b>",
        showarrow=False,
        font=dict(size=18, color="rgba(70,70,90,0.85)"),
        align="center",
    )

    # Subtitle (small) - gap doubled from title
    fig.add_annotation(
        xref="paper", yref="paper",
        x=0.5, y=0.98,  # Moved down from 1.02 (doubled gap: 1.06 - 0.08 = 0.98)
        text="<span style='font-size:12px'>ε<sub>x</sub> evaluated at mid-depth (MCFT – AS 3600 Cl. 8.2.4.2.2)</span>",
        showarrow=False,
        font=dict(size=12, color="rgba(70,70,90,0.75)"),
        align="center",
    )

    # AS 3600 limits annotation (context only, no bounding boxes) - gap doubled from subtitle
    fig.add_annotation(
        xref="paper", yref="paper",
        x=0.5, y=0.90,  # Moved down from 0.98 (doubled gap: 0.98 - 0.08 = 0.90)
        text="<span style='font-size:11px'>AS 3600 limits: −2.0×10⁻⁴ ≤ ε<sub>x</sub> ≤ 3.0×10⁻³</span>",
        showarrow=False,
        font=dict(size=11, color="rgba(70,70,90,0.7)"),
        align="center",
    )

    # Axis framing: ensure x=0 is always visible and centered
    # Include space for labels (especially compression labels that extend left)
    # label_offset is already calculated above (line ~464)
    xmin = min(eps_top_uls, eps_bot_uls, eps_x_mcft, 0.0) - label_offset  # Extra space for left-side labels
    xmax = max(eps_top_uls, eps_bot_uls, eps_x_mcft, 0.0) + label_offset  # Extra space for right-side labels
    span = xmax - xmin
    if span < 1e-6:
        span = 1e-4  # Force minimum span if all values are tiny
    pad = 0.20 * span  # 20% padding

    fig.update_layout(
        width=640,  # Reduced by 0.8 (800 * 0.8 = 640)
        height=height,  # Use parameter (default 840, doubled from 420)
        margin=dict(t=100, b=20, l=60, r=20),  # Increased left margin to prevent compression label cutoff
        xaxis=dict(
            visible=False,
            range=[xmin - pad, xmax + pad],
        ),
        yaxis=dict(
            visible=False,
            showticklabels=False,
            showgrid=False,
            autorange="reversed",  # Reversed so y=0 (top) appears at top, y=1 (bottom) appears at bottom
            range=[y_bot + 0.05, y_top - 0.05],  # Small padding to ensure line endpoints are visible
        ),
        paper_bgcolor="white",
        plot_bgcolor="white",
        showlegend=False,
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

    def strain_to_x(eps_true: float) -> float:
        """Map signed ε → x position. Centre = 0, right = compression (ε > 0), left = tension (ε < 0)."""
        if eps_true >= 0.0:
            return panel_x_center + (abs(eps_true) / eps_max) * half_w
        else:
            return panel_x_center - (abs(eps_true) / eps_max) * half_w

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
    fig.add_shape(
        type="line",
        x0=panel_x_center,
        y0=y_mid,
        x1=x_epsx,
        y1=y_mid,
        line=dict(color="red", width=2.0),
        row=1, col=2,
    )
    
    # Label for ε_x
    if epsx >= 0.0:  # tension (to the left)
        label_x = x_epsx - 0.02
        xanchor = "right"
    else:  # compression (to the right)
        label_x = x_epsx + 0.02
        xanchor = "left"
    
    fig.add_annotation(
        x=label_x,
        y=y_mid,
        text=rf"$\varepsilon_x$ = {epsx:.5f}<br><span style='font-size:11px'>{strain_state}</span>",
        showarrow=False,
        font=dict(size=12, color="red"),
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
    Bending-style strain profile diagram for Step 4 MCFT.
    Uses bending-page sign convention: compression positive (right), tension negative (left).
    Shows linear strain distribution from top to bottom with ε_x highlighted at mid-depth.
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

    # Horizontal lines from zero axis to strain values (like bending page)
    # Color based on sign: red if compression (>=0), blue if tension (<0)
    emax = max(abs(e_top), abs(e_mid), abs(e_bot), 1e-6)
    offset = 0.02 * emax
    
    # Top strain horizontal line and label
    color_top = "red" if e_top >= 0 else "blue"
    fig.add_shape(
        type="line",
        x0=0, y0=y_top, x1=e_top, y1=y_top,
        line=dict(color=color_top, width=2.0),
    )
    if e_top >= 0.0:  # compression (to the right)
        label_x_top = e_top + offset
        xanchor_top = "left"
        state_top = "(compression)"
    else:  # tension (to the left)
        label_x_top = e_top - offset
        xanchor_top = "right"
        state_top = "(tension)"
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
    color_mid = "red" if e_mid >= 0 else "blue"
    fig.add_shape(
        type="line",
        x0=0, y0=y_mid, x1=e_mid, y1=y_mid,
        line=dict(color=color_mid, width=2.0),
    )
    if e_mid >= 0.0:  # compression (to the right)
        label_x_mid = e_mid + offset
        xanchor_mid = "left"
        state_mid = "(compression)"
    else:  # tension (to the left)
        label_x_mid = e_mid - offset
        xanchor_mid = "right"
        state_mid = "(tension)"
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
    color_bot = "red" if e_bot >= 0 else "blue"
    fig.add_shape(
        type="line",
        x0=0, y0=y_bot, x1=e_bot, y1=y_bot,
        line=dict(color=color_bot, width=2.0),
    )
    if e_bot >= 0.0:  # compression (to the right)
        label_x_bot = e_bot + offset
        xanchor_bot = "left"
        state_bot = "(compression)"
    else:  # tension (to the left)
        label_x_bot = e_bot - offset
        xanchor_bot = "right"
        state_bot = "(tension)"
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
    Step 4 diagram: longitudinal strain profile for MCFT (bending-style).
    Shows eps_top, eps_x(mid-depth), eps_bot on a linear profile.
    Styling matches bending page strain panel (big, clean, red top/blue bottom, horizontal ticks).
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

    # Horizontal "ticks" from zero axis to each strain value (like bending)
    # Top strain horizontal line (red)
    fig.add_shape(
        type="line",
        x0=0, y0=y_top, x1=eps_top, y1=y_top,
        line=dict(color="red", width=2.0),
    )
    # Mid-depth strain horizontal line (red)
    fig.add_shape(
        type="line",
        x0=0, y0=y_mid, x1=eps_x, y1=y_mid,
        line=dict(color="red", width=2.0),
    )
    # Bottom strain horizontal line (blue)
    fig.add_shape(
        type="line",
        x0=0, y0=y_bot, x1=eps_bot, y1=y_bot,
        line=dict(color="blue", width=2.0),
    )

    # Labels (use plain text, not raw LaTeX strings)
    # Top strain label (red)
    if eps_top >= 0.0:  # compression (to the right)
        label_x_top = eps_top + 0.02 * max(abs(eps_top), abs(eps_x), abs(eps_bot), 1e-6)
        xanchor_top = "left"
    else:  # tension (to the left)
        label_x_top = eps_top - 0.02 * max(abs(eps_top), abs(eps_x), abs(eps_bot), 1e-6)
        xanchor_top = "right"
    fig.add_annotation(
        x=label_x_top, y=y_top,
        text=f"ε<sub>top</sub> = {eps_top:.5f}",
        showarrow=False,
        font=dict(size=12, color="red"),
        xanchor=xanchor_top,
        yshift=-10,
    )

    # Mid-depth strain label (red, highlighted)
    if eps_x >= 0.0:  # compression (to the right)
        label_x_mid = eps_x + 0.02 * max(abs(eps_top), abs(eps_x), abs(eps_bot), 1e-6)
        xanchor_mid = "left"
    else:  # tension (to the left)
        label_x_mid = eps_x - 0.02 * max(abs(eps_top), abs(eps_x), abs(eps_bot), 1e-6)
        xanchor_mid = "right"
    fig.add_annotation(
        x=label_x_mid, y=y_mid,
        text=f"ε<sub>x</sub> = {eps_x:.5f}<br><span style='font-size:11px'>mid-depth (MCFT)</span>",
        showarrow=False,
        font=dict(size=12, color="red"),
        xanchor=xanchor_mid,
        yshift=0,
    )

    # Bottom strain label (blue)
    if eps_bot >= 0.0:  # compression (to the right)
        label_x_bot = eps_bot + 0.02 * max(abs(eps_top), abs(eps_x), abs(eps_bot), 1e-6)
        xanchor_bot = "left"
    else:  # tension (to the left)
        label_x_bot = eps_bot - 0.02 * max(abs(eps_top), abs(eps_x), abs(eps_bot), 1e-6)
        xanchor_bot = "right"
    fig.add_annotation(
        x=label_x_bot, y=y_bot,
        text=f"ε<sub>bot</sub> = {eps_bot:.5f}",
        showarrow=False,
        font=dict(size=12, color="blue"),
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

