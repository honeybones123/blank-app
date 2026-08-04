"""Inputs-page 2D section diagram figure construction."""

from __future__ import annotations

import math
from typing import Any, Callable

import plotly.graph_objects as go

from section_props.plot import apply_section_axes
from section_props.plotly_section import make_sectionA_figure

from .diagram_styles import (
    ANNOTATION_TEXT,
    CONCRETE_FILL_2D,
    CONCRETE_OUTLINE,
    DIAGRAM_TRANSPARENT,
    LINK_STEEL,
    REO_BOTTOM,
    REO_TOP,
)
from .diagram_models import SectionDiagramResult


SectionFigureBuilder = Callable[..., go.Figure]


def _normalise_section_shape_styles(fig: go.Figure) -> go.Figure:
    """Apply visual style constants without changing section geometry."""
    for shape in fig.layout.shapes or []:
        fill = str(getattr(shape, "fillcolor", "") or "")
        line = getattr(shape, "line", None)
        if fill in {"rgba(0,0,0,0)", "rgba(0, 0, 0, 0)", ""} and shape.type in {"rect", "path"}:
            shape.fillcolor = CONCRETE_FILL_2D
        elif fill in {"rgba(0,0,255,0.9)", "rgba(0, 0, 255, 0.9)", "blue"}:
            shape.fillcolor = REO_BOTTOM
        elif fill in {"rgba(255,0,0,0.9)", "rgba(255, 0, 0, 0.9)", "red"}:
            shape.fillcolor = REO_TOP

        if line is not None and str(getattr(line, "color", "") or "").lower() == "black":
            if shape.type in {"rect", "path"}:
                line.color = CONCRETE_OUTLINE
            else:
                line.color = LINK_STEEL
    return fig


def _section_dim_scale_mm(dims: dict) -> tuple[float, float, float, float, float, float, float, float, float, float]:
    """
    Shared geometry for section dimension overlays (mm).
    Returns (D, bf, tf, bw, tw, x_span, x_off, y_off, ah, aw).
    Keep in sync with _ti_annotation_bounds_for_model_mm.
    """
    D = float(dims.get("D", 0.0) or 0.0)
    bf = float(dims.get("bf", 0.0) or 0.0)
    tf = float(dims.get("tf", 0.0) or 0.0)
    bw = float(dims.get("bw", 0.0) or 0.0)
    tw = float(dims.get("tw", 0.0) or 0.0)
    b = float(dims.get("b", 0.0) or 0.0)
    x_span = max(bf, bw, tw, b, 1.0)
    x_off = 0.08 * x_span
    y_off = 0.08 * max(D, 1.0)
    ah = 0.025 * x_span
    aw = 0.012 * max(D, 1.0)
    return D, bf, tf, bw, tw, x_span, x_off, y_off, ah, aw


def _ti_annotation_bounds_for_model_mm(shape_name: str, dims: dict) -> tuple[float, float, float, float] | None:
    """
    Axis-data bounds (mm) that contain T/I dimension lines, arrowheads, and
    typical label positions. None if this shape does not use the T/I dimension
    overlay.
    """
    sn = str(shape_name or "")
    if not (sn.startswith("T-Section") or sn.startswith("I-Section")):
        return None
    D, bf, _tf, bw, tw, x_span, x_off, y_off, ah, _aw = _section_dim_scale_mm(dims)
    txt = max(12.0, 0.022 * max(x_span, D, 1.0))
    xmin = min(0.0, -1.60 * x_off - ah - txt)
    xmax = max(bf, bf + x_off + ah + txt)
    ymin = min(0.0, -1.45 * y_off - txt)
    ymax = max(D, D + 1.45 * y_off + txt)
    if sn.startswith("T-Section") and bw > 0:
        x_web1 = (bf - bw) / 2.0 + bw
        xmax = max(xmax, x_web1 + txt)
        ymax = max(ymax, D + 0.75 * y_off + txt)
    if sn.startswith("I-Section") and tw > 0:
        x_web1 = (bf - tw) / 2.0 + tw
        xmax = max(xmax, x_web1 + txt)
    return xmin, xmax, ymin, ymax


def add_section_dimension_labels(fig, *, shape_name: str, dims: dict, reo: dict):
    """
    Adds engineering-style dimension labels with double-ended arrows to Plotly
    2D section figure. Coordinates are in mm, with y=0 at top and y increasing
    downward.
    """
    D, bf, tf, bw, tw, x_span, x_off, y_off, ah, _aw = _section_dim_scale_mm(dims)

    cover_top = float(reo.get("cover_top", 0.0) or 0.0)
    cover_bot = float(reo.get("cover_bot", 0.0) or 0.0)
    cover_side = float(reo.get("cover_side", 0.0) or 0.0)

    def _add_line(x0, y0, x1, y1):
        fig.add_shape(
            type="line",
            x0=x0,
            y0=y0,
            x1=x1,
            y1=y1,
            line=dict(width=1, color=LINK_STEEL),
        )

    def _arrowhead_at_point(px, py, angle_rad):
        for sgn in (-1, +1):
            a = angle_rad + sgn * math.radians(25)
            x1 = px - ah * math.cos(a)
            y1 = py - ah * math.sin(a)
            _add_line(px, py, x1, y1)

    def add_dim_x(x0, x1, y, text):
        _add_line(x0, y, x1, y)
        _arrowhead_at_point(x0, y, 0.0)
        _arrowhead_at_point(x1, y, math.pi)
        fig.add_annotation(
            x=(x0 + x1) / 2.0,
            y=y - 0.45 * y_off,
            text=text,
            showarrow=False,
            font=dict(size=12, color=ANNOTATION_TEXT),
        )

    def add_dim_y(x, y0, y1, text):
        _add_line(x, y0, x, y1)
        _arrowhead_at_point(x, y0, math.pi / 2)
        _arrowhead_at_point(x, y1, -math.pi / 2)
        fig.add_annotation(
            x=x - 0.60 * x_off,
            y=(y0 + y1) / 2.0,
            text=text,
            showarrow=False,
            font=dict(size=12, color=ANNOTATION_TEXT),
        )

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

    fig.add_annotation(
        x=0.5 * x_span,
        y=D + 1.45 * y_off,
        text=f"cover(top/bot/side) = {cover_top:.0f}/{cover_bot:.0f}/{cover_side:.0f} mm",
        showarrow=False,
        font=dict(size=12, color=ANNOTATION_TEXT),
    )

    return fig


def _finalize_section_figure(
    fig,
    width_mm: float,
    depth_mm: float,
    *,
    shape_name: str | None = None,
    dims: dict | None = None,
):
    """
    Set axis limits with padding. For T/I, union section [0,W]x[0,D] with
    dimension annotation extents so arrows and labels are not clipped.
    """
    fig.update_layout(
        autosize=True,
        paper_bgcolor=DIAGRAM_TRANSPARENT,
        plot_bgcolor=DIAGRAM_TRANSPARENT,
        margin=dict(l=6, r=6, t=6, b=6),
    )
    gx0, gx1 = 0.0, float(width_mm)
    gy0, gy1 = 0.0, float(depth_mm)
    ext = None
    if shape_name is not None and dims is not None:
        ext = _ti_annotation_bounds_for_model_mm(str(shape_name), dims)
    if ext is not None:
        ex0, ex1, ey0, ey1 = ext
        gx0 = min(gx0, ex0)
        gx1 = max(gx1, ex1)
        gy0 = min(gy0, ey0)
        gy1 = max(gy1, ey1)
    span_x = max(gx1 - gx0, 1e-6)
    span_y = max(gy1 - gy0, 1e-6)
    if ext is not None:
        pad_x = max(0.05 * span_x, 0.03 * max(width_mm, 1.0), 16.0)
        pad_y = max(0.08 * span_y, 0.05 * max(depth_mm, 1.0), 20.0)
    else:
        pad_x = max(25.0, 0.08 * max(width_mm, 1.0))
        pad_y = max(25.0, 0.08 * max(depth_mm, 1.0))
    fig.update_xaxes(
        range=[gx0 - pad_x, gx1 + pad_x],
        showgrid=False,
        zeroline=False,
    )
    fig.update_yaxes(
        range=[gy1 + pad_y, gy0 - pad_y],
        showgrid=False,
        zeroline=False,
        scaleanchor="x",
        scaleratio=1,
    )
    return fig


def _default_section_figure_builder(**kwargs: Any) -> go.Figure:
    return make_sectionA_figure(**kwargs)


def build_summary_cross_section_result(
    *,
    layout: dict[str, Any],
    tension_face: str | None = None,
    fallback_cover_side: float = 40.0,
    fallback_cover_top: float = 40.0,
    fallback_cover_bot: float = 40.0,
    section_figure_builder: SectionFigureBuilder | None = None,
) -> SectionDiagramResult:
    """Build the Inputs-page 2D cross-section diagram from a computed layout."""
    section_figure_builder = section_figure_builder or _default_section_figure_builder
    shape_name = layout.get("shape_name", "Rectangle (b - D)")
    dims = layout.get("dims", {})
    reo = layout.get("reo", {})
    shape_key = str(shape_name).strip().lower()
    is_ti = (
        ("t-section" in shape_key)
        or ("i-section" in shape_key)
        or shape_key.startswith("t")
        or shape_key.startswith("i")
    )
    is_rect = ("rectangle" in shape_key) or (shape_key == "rect")

    if is_ti:
        try:
            fig = section_figure_builder(
                shape_name=shape_name,
                dims=dims,
                reo=reo,
                show_shear=True,
                tension_face=tension_face,
            )
            fig = _normalise_section_shape_styles(fig)
            fig = add_section_dimension_labels(fig, shape_name=shape_name, dims=dims, reo=reo)

            width = float(dims.get("bf", dims.get("b", 0.0)) or 0.0)
            depth = float(dims.get("D", 0.0) or 0.0)
            return SectionDiagramResult(
                _finalize_section_figure(fig, width, depth, shape_name=shape_name, dims=dims)
            )

        except ValueError as exc:
            reo_no_bars = dict(reo)
            reo_no_bars.update(
                {
                    "nb_top": 0,
                    "db_top": 0.0,
                    "nb_bot": 0,
                    "db_bot": 0.0,
                    "lig_d": 0.0,
                    "lig_legs": 0,
                    # The canonical row model is authoritative. Clearing only
                    # legacy counts leaves the same invalid rows active and
                    # makes the intended no-bars fallback fail a second time.
                    "top_rows": [],
                    "bottom_rows": [],
                }
            )

            fig = section_figure_builder(
                shape_name=shape_name,
                dims=dims,
                reo=reo_no_bars,
                show_shear=True,
                tension_face=tension_face,
            )
            fig = _normalise_section_shape_styles(fig)
            fig = add_section_dimension_labels(fig, shape_name=shape_name, dims=dims, reo=reo_no_bars)

            width = float(dims.get("bf", dims.get("b", 0.0)) or 0.0)
            depth = float(dims.get("D", 0.0) or 0.0)
            return SectionDiagramResult(
                _finalize_section_figure(fig, width, depth, shape_name=shape_name, dims=dims),
                error_message=f"Reinforcement layout failed: {exc}",
            )

    if not is_rect:
        return SectionDiagramResult(None)

    b = float(dims.get("b", 0.0) or 0.0)
    D = float(dims.get("D", 0.0) or 0.0)

    fig = go.Figure()
    fig.add_shape(
        type="rect",
        x0=0,
        y0=0,
        x1=b,
        y1=D,
        line=dict(color=CONCRETE_OUTLINE, width=2),
        fillcolor=CONCRETE_FILL_2D,
    )

    reo_layout = layout.get("reo_layout") or {"bottom": [], "top": []}

    def _add_layer_circles(layer, color):
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
                x0=x - r,
                y0=y - r,
                x1=x + r,
                y1=y + r,
                line=dict(color=LINK_STEEL, width=1),
                fillcolor=color,
                opacity=1.0,
            )

    for layer in reo_layout.get("bottom") or []:
        _add_layer_circles(layer, REO_BOTTOM)

    for layer in reo_layout.get("top") or []:
        _add_layer_circles(layer, REO_TOP)

    lig_d = float(reo.get("lig_d", 0.0) or 0.0)
    lig_legs = int(reo.get("lig_legs", 0) or 0)

    if lig_d > 0 and lig_legs >= 2:
        cover_side = float(reo.get("cover_side", fallback_cover_side) or 40.0)
        cover_top = float(reo.get("cover_top", fallback_cover_top) or 40.0)
        cover_bot = float(reo.get("cover_bot", fallback_cover_bot) or 40.0)

        x0, x1 = cover_side, b - cover_side
        y0, y1 = cover_top, D - cover_bot

        if x1 > x0 and y1 > y0:
            fig.add_shape(
                type="rect",
                x0=x0,
                y0=y0,
                x1=x1,
                y1=y1,
                line=dict(color=LINK_STEEL, width=2),
                fillcolor=DIAGRAM_TRANSPARENT,
            )

            if lig_legs > 2:
                span = x1 - x0
                for j in range(1, lig_legs - 1):
                    x = x0 + span * j / (lig_legs - 1)
                    fig.add_shape(
                        type="line",
                        x0=x,
                        y0=y0,
                        x1=x,
                        y1=y1,
                        line=dict(color=LINK_STEEL, width=2),
                    )

    apply_section_axes(fig, W=b, D=D)
    return SectionDiagramResult(_finalize_section_figure(fig, b, D))


def build_summary_cross_section_figure(**kwargs: Any):
    """Compatibility convenience for callers that only need the figure."""
    return build_summary_cross_section_result(**kwargs).figure
