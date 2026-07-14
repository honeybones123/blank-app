"""Shear-specific figure builders."""

from __future__ import annotations

from typing import Any

import plotly.graph_objects as go

from section_props.plot import apply_section_axes, plot_shape
from section_props.plotly_section import make_sectionA_figure

from .diagram_styles import (
    ANNOTATION_BG,
    ANNOTATION_TEXT,
    CONCRETE_FILL_2D,
    CONCRETE_OUTLINE,
    DIAGRAM_BG,
    DIAGRAM_TRANSPARENT,
    LINK_STEEL,
    REO_BOTTOM,
    REO_INACTIVE,
    REO_TOP,
)


SHEAR_FLOW_COLOUR = "red"
TORSION_FLOW_COLOUR = "rgb(31,119,180)"
SHEAR_EFFECTIVE_WIDTH_FILL = "rgba(0,0,0,0.04)"


def _normalise_reo_fill(fill: Any) -> Any:
    fill_text = str(fill or "")
    if fill_text in {"rgba(0,90,200,0.94)", "rgba(0,90,200,0.95)", "rgba(0,0,255,0.9)"}:
        return REO_BOTTOM
    if fill_text in {"rgba(200,45,45,0.94)", "rgba(200,45,45,0.95)", "rgba(255,0,0,0.9)"}:
        return REO_TOP
    if fill_text in {"rgba(80,80,80,0.90)", "rgba(136,136,136,0.92)"}:
        return REO_INACTIVE
    return fill


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
        if number != number:
            return float(default)
        return number
    except Exception:
        return float(default)


def _normalise_shear_section_shape_styles(
    fig: go.Figure,
    *,
    width_mm: float,
    depth_mm: float,
    lig_d: float = 0.0,
    lig_legs: int = 0,
) -> None:
    """Apply visual contract colours to existing section geometry."""
    for shape in fig.layout.shapes or []:
        shape_type = getattr(shape, "type", None)
        if shape_type == "circle":
            shape.fillcolor = _normalise_reo_fill(getattr(shape, "fillcolor", None))
            shape.line.color = LINK_STEEL
            continue

        if shape_type == "path":
            shape.line.color = CONCRETE_OUTLINE
            if not getattr(shape, "fillcolor", None) or shape.fillcolor == DIAGRAM_TRANSPARENT:
                shape.fillcolor = CONCRETE_FILL_2D
            continue

        x0 = _safe_float(getattr(shape, "x0", 0.0), 0.0)
        x1 = _safe_float(getattr(shape, "x1", width_mm), width_mm)
        y0 = _safe_float(getattr(shape, "y0", 0.0), 0.0)
        y1 = _safe_float(getattr(shape, "y1", depth_mm), depth_mm)
        is_outer_rect = (
            shape_type == "rect"
            and abs(x0) < 1e-9
            and abs(y0) < 1e-9
            and abs(x1 - width_mm) < 1e-6
            and abs(y1 - depth_mm) < 1e-6
        )
        is_inner_ligature = (
            lig_d > 0.0
            and lig_legs >= 2
            and shape_type in {"rect", "line"}
            and (x0 > 0.0 or y0 > 0.0)
            and (x1 < width_mm or y1 < depth_mm)
        )

        if is_outer_rect:
            shape.line.color = CONCRETE_OUTLINE
            shape.fillcolor = CONCRETE_FILL_2D
        elif is_inner_ligature:
            shape.line.color = LINK_STEEL
            shape.line.width = max(_safe_float(getattr(shape.line, "width", 1.5), 1.5), 2.0)
        elif shape_type == "line" and getattr(shape.line, "color", None) in {None, "black", "rgba(0,0,0,0.85)"}:
            shape.line.color = LINK_STEEL


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

    lig_d = float(reo.get("lig_d", 0.0) or 0.0)
    lig_legs = int(reo.get("lig_legs", 0) or 0)
    _normalise_shear_section_shape_styles(fig, width_mm=W, depth_mm=D, lig_d=lig_d, lig_legs=lig_legs)

    # helpers
    def _arrow(x0, y0, x1, y1, color=LINK_STEEL, width=2):
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
            _arrow(xL, y, xL, y + 0.15 * D, color=SHEAR_FLOW_COLOUR, width=2)
            _arrow(xR, y, xR, y + 0.15 * D, color=SHEAR_FLOW_COLOUR, width=2)

        if show_labels and not compact_stress_labels:
            fig.add_annotation(
                x=W / 2,
                y=-0.06 * D,
                text="tau_v (shear)",
                showarrow=False,
                font=dict(size=11, color=SHEAR_FLOW_COLOUR),
            )

    # -------------------------
    # TORSION τT (BLUE) — clockwise shear flow:
    #   RIGHT face = DOWN (adds with shear-down)
    #   LEFT  face = UP   (opposes shear-down)
    # -------------------------
    if "T" in mode:
        # Top edge: →
        for x in [0.25 * W, 0.50 * W, 0.75 * W]:
            _arrow(x - 0.10 * W, yT, x + 0.10 * W, yT, color=TORSION_FLOW_COLOUR, width=2)

        # Right edge: ↓ (ADDS)
        for y in [0.25 * D, 0.50 * D, 0.75 * D]:
            _arrow(xR, y, xR, y + 0.10 * D, color=TORSION_FLOW_COLOUR, width=2)

        # Bottom edge: ←
        for x in [0.25 * W, 0.50 * W, 0.75 * W]:
            _arrow(x + 0.10 * W, yB, x - 0.10 * W, yB, color=TORSION_FLOW_COLOUR, width=2)

        # Left edge: ↑ (OPPOSES)
        for y in [0.25 * D, 0.50 * D, 0.75 * D]:
            _arrow(xL, y + 0.10 * D, xL, y - 0.10 * D, color=TORSION_FLOW_COLOUR, width=2)

        if show_labels and not compact_stress_labels:
            fig.add_annotation(
                x=W / 2,
                y=-0.12 * D,
                text="tau_T (torsion shear flow)",
                showarrow=False,
                font=dict(size=9, color=TORSION_FLOW_COLOUR),
            )
            fig.add_annotation(
                x=-0.08 * W,
                y=D / 2,
                text="opposes",
                showarrow=False,
                textangle=90,
                font=dict(size=8, color=ANNOTATION_TEXT),
            )
            fig.add_annotation(
                x=W + 0.08 * W,
                y=D / 2,
                text="adds",
                showarrow=False,
                textangle=90,
                font=dict(size=8, color=ANNOTATION_TEXT),
            )

    if show_labels and show_schematic_footer:
        fig.add_annotation(
            x=W / 2,
            y=D + 0.12 * D,
            text="Section + reinforcement (schematic)",
            showarrow=False,
            font=dict(size=9, color=ANNOTATION_TEXT),
        )

    # expand axes for labels/arrows (shared helper for consistency)
    apply_section_axes(fig, W=W, D=D)
    fig.update_xaxes(visible=False)
    fig.update_yaxes(visible=False)

    return fig



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
            if getattr(s, "type", None) == "path" and (not getattr(s, "fillcolor", None) or s.fillcolor == DIAGRAM_TRANSPARENT):
                s.fillcolor = CONCRETE_FILL_2D
        _normalise_shear_section_shape_styles(
            fig,
            width_mm=float(W),
            depth_mm=float(D),
            lig_d=float(reo.get("lig_d", 0.0) or 0.0),
            lig_legs=int(reo.get("lig_legs", 0) or 0),
        )
    else:
        fig = go.Figure()
        # fallback (old behaviour): rectangle only
        fig.add_shape(
            type="rect",
            x0=0, y0=0, x1=b, y1=D,
            line=dict(color=CONCRETE_OUTLINE, width=4),
            fillcolor=CONCRETE_FILL_2D,
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
            fill = _normalise_reo_fill(s.get("fill", REO_INACTIVE))
            line = s.get("line", LINK_STEEL)
            if line in {"rgba(30,30,30,1.00)", "black"}:
                line = LINK_STEEL

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
            fillcolor=SHEAR_EFFECTIVE_WIDTH_FILL,
            layer="below",
        )

    # --- dv marker line (horizontal) ---
    fig.add_shape(type="line", x0=0, y0=y_dv, x1=b, y1=y_dv, line=dict(width=2, color=LINK_STEEL))

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
        
        # Draw stirrup legs using the shared link/stirrup style.
        for stirrup in shear_layout.get("stirrups", []):
            for leg in stirrup.get("legs", []):
                fig.add_shape(
                    type="line",
                    x0=float(leg["x1"]), y0=float(leg["y1"]),
                    x1=float(leg["x2"]), y1=float(leg["y2"]),
                    line=dict(width=1.2, color=LINK_STEEL),
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
            font=dict(size=18, color=ANNOTATION_TEXT),
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
        arrowcolor=ANNOTATION_TEXT,
        axref="x", ayref="y",
        ax=xL + 0.20 * bv, ay=BV_ARROW_Y,   # arrow tail to the right, head at xL
        standoff=label_pad,
    )
    fig.add_annotation(
        x=xR, y=BV_ARROW_Y, text="",
        showarrow=True, arrowhead=2,
        arrowcolor=ANNOTATION_TEXT,
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
        arrowcolor=ANNOTATION_TEXT,
        axref="x", ayref="y",
        ax=DV_ARROW_X, ay=y_top - 0.25 * dv,   # tail below, head at top
        standoff=label_pad,
    )
    fig.add_annotation(
        x=DV_ARROW_X, y=y_dv, text="",
        showarrow=True, arrowhead=2,
        arrowcolor=ANNOTATION_TEXT,
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
            font=dict(size=11, color=ANNOTATION_TEXT),
            bgcolor=ANNOTATION_BG,
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
        paper_bgcolor=DIAGRAM_BG,
        plot_bgcolor=DIAGRAM_BG,
        showlegend=False,
    )

    return fig


def _cross_section_frame_size(width_mm: float, depth_mm: float) -> float:
    return max(width_mm, depth_mm) * 1.32


def _add_section_reo_overlay(fig: go.Figure, layout: dict[str, Any]) -> None:
    for point in layout.get("reo_points", []) or []:
        x = _safe_float(point.get("x", 0.0), 0.0)
        y = _safe_float(point.get("y", 0.0), 0.0)
        db = max(_safe_float(point.get("db", 20.0), 20.0), 8.0)
        layer = str(point.get("layer", "bottom") or "bottom")
        color = REO_BOTTOM if layer == "bottom" else REO_TOP
        fig.add_shape(
            type="circle",
            x0=x - db / 2.0,
            y0=y - db / 2.0,
            x1=x + db / 2.0,
            y1=y + db / 2.0,
            line=dict(color=LINK_STEEL, width=1.0),
            fillcolor=color,
        )


def build_shear_cross_section_figure_from_layout(
    *,
    layout: dict[str, Any],
    height: int,
    active_tension_face: str | None = None,
    top_reo_label: str = "Top reo",
) -> go.Figure:
    """Build the shear page cross-section figure from an already-computed layout."""
    shape_name = layout.get("shape_name", "Rectangle (b x D)")
    dims = layout.get("dims", {})
    reo = layout.get("reo", {})

    if str(shape_name).startswith("Rectangle"):
        fig = plot_shape(
            shape_name,
            dims,
            reo={
                "cover_top": float(reo.get("cover_top", 40.0)),
                "cover_bot": float(reo.get("cover_bot", 40.0)),
                "cover_side": float(reo.get("cover_side", 40.0)),
                "n_top": 0,
                "db_top": 0.0,
                "n_bot": 0,
                "db_bot": 0.0,
                "s_min": float(reo.get("min_clear_spacing", 20.0)),
                "rowgap_top": float(reo.get("rowgap_top", 60.0)),
                "rowgap_bot": float(reo.get("rowgap_bot", 60.0)),
                "lig_d": float(reo.get("lig_d", 0.0)),
                "lig_legs": int(reo.get("lig_legs", 0)),
            },
        )
        _add_section_reo_overlay(fig, layout)
    else:
        fig = make_sectionA_figure(
            shape_name=shape_name,
            dims=dims,
            reo=reo,
            show_shear=True,
            tension_face=active_tension_face,
        )

    width_mm = _safe_float(dims.get("bf", dims.get("b", 300.0)), 300.0)
    depth_mm = _safe_float(dims.get("D", 600.0), 600.0)
    lig_d = _safe_float(reo.get("lig_d", 0.0), 0.0)
    lig_legs = int(_safe_float(reo.get("lig_legs", 0.0), 0.0))

    for shape in fig.layout.shapes or []:
        if shape.type == "path" and getattr(shape, "fillcolor", DIAGRAM_TRANSPARENT) == DIAGRAM_TRANSPARENT:
            shape.fillcolor = CONCRETE_FILL_2D
    _normalise_shear_section_shape_styles(
        fig,
        width_mm=width_mm,
        depth_mm=depth_mm,
        lig_d=lig_d,
        lig_legs=lig_legs,
    )

    frame_size = _cross_section_frame_size(width_mm, depth_mm)
    x_c = width_mm / 2.0
    y_c = depth_mm / 2.0
    fig.update_xaxes(
        visible=False,
        fixedrange=True,
        range=[x_c - frame_size / 2.0, x_c + frame_size / 2.0],
    )
    fig.update_yaxes(
        visible=False,
        fixedrange=True,
        range=[y_c + frame_size / 2.0, y_c - frame_size / 2.0],
        scaleanchor="x",
        scaleratio=1,
    )
    fig.update_layout(
        height=height,
        margin=dict(l=12, r=12, t=12, b=12),
        paper_bgcolor=DIAGRAM_BG,
        plot_bgcolor=DIAGRAM_BG,
        showlegend=False,
    )

    fig.add_annotation(
        x=width_mm / 2.0,
        y=-0.10 * depth_mm,
        text=f"b = {width_mm:.0f} mm",
        showarrow=False,
        font=dict(size=11, color=ANNOTATION_TEXT),
    )
    fig.add_annotation(
        x=-0.14 * width_mm,
        y=depth_mm / 2.0,
        text=f"D = {depth_mm:.0f} mm",
        showarrow=False,
        textangle=-90,
        font=dict(size=11, color=ANNOTATION_TEXT),
    )
    if layout.get("reo_layout", {}).get("top", []):
        fig.add_annotation(
            x=width_mm * 0.30,
            y=0.07 * depth_mm,
            text=top_reo_label,
            showarrow=False,
            font=dict(size=11, color=REO_TOP),
        )
    if layout.get("reo_layout", {}).get("bottom", []):
        fig.add_annotation(
            x=width_mm * 0.70,
            y=depth_mm - 0.07 * depth_mm,
            text="Tension reo",
            showarrow=False,
            font=dict(size=11, color=REO_BOTTOM),
        )
    if lig_d > 0.0 and lig_legs >= 2:
        fig.add_annotation(
            x=width_mm / 2.0,
            y=depth_mm + 0.11 * depth_mm,
            text="Shear reinforcement",
            showarrow=False,
            font=dict(size=11, color=LINK_STEEL),
        )

    return fig
