"""Shear behaviour diagram frame builders."""

from __future__ import annotations

import math
from typing import Any

import plotly.graph_objects as go

from ui.diagrams.diagram_styles import (
    CONCRETE_FILL_2D,
    CONCRETE_OUTLINE,
    DIAGRAM_BG,
    SUPPORT_FILL,
    SUPPORT_FIXED_HATCH_SPAN_RATIO,
    SUPPORT_FIXED_MIN_HATCH_MM,
    SUPPORT_FIXED_OVERHANG_BEAM_RATIO,
    SUPPORT_GROUND,
    SUPPORT_GROUND_DROP_BEAM_RATIO,
    SUPPORT_GROUND_MIN_DROP_MM,
    SUPPORT_GROUND_HATCH,
    SUPPORT_OUTLINE,
    SUPPORT_PIN_DEPTH_BEAM_RATIO,
    SUPPORT_PIN_MIN_DEPTH_MM,
    SUPPORT_PIN_MIN_WIDTH_MM,
    SUPPORT_PIN_WIDTH_SPAN_RATIO,
    SUPPORT_ROLLER_FILL,
    SUPPORT_ROLLER_MIN_RADIUS_MM,
    SUPPORT_ROLLER_RADIUS_BEAM_RATIO,
)
from ui.diagrams.principal_stress_cue_diagram import add_principal_stress_orientation_square


BEAM_BAND_Y0 = 0.40
BEAM_BAND_Y1 = 0.60
FIELD_SPLINE_SMOOTHING = 0.65
STM_SNAP_X_RATIOS: tuple[float, ...] = (0.6, 0.7, 0.8, 0.9)
STM_SNAP_Y_DV_FRACS: tuple[float, ...] = (0.85, 0.9, 0.95)


def build_shear_behaviour_base_figure(
    *,
    length_m: float,
    beam_depth_m: float,
    height: int,
    width: int,
) -> go.Figure:
    fig = go.Figure()
    pad = max(float(length_m) * 0.06, 0.2)
    y_min = -0.92 * float(beam_depth_m)
    y_max = 1.9 * float(beam_depth_m)
    fig.update_layout(
        height=height,
        width=width,
        autosize=False,
        margin=dict(l=10, r=10, t=8, b=8),
        paper_bgcolor=DIAGRAM_BG,
        plot_bgcolor=DIAGRAM_BG,
        showlegend=False,
    )
    fig.update_xaxes(
        visible=False,
        range=[-pad, float(length_m) + pad],
        fixedrange=True,
        showgrid=False,
        zeroline=False,
    )
    fig.update_yaxes(
        visible=False,
        range=[y_min, y_max],
        fixedrange=True,
        showgrid=False,
        zeroline=False,
        scaleanchor="x",
        scaleratio=1,
    )
    return fig


def add_shear_behaviour_beam_band(
    fig: go.Figure,
    x_end: float,
    beam_depth_m: float | None = None,
) -> None:
    y0 = BEAM_BAND_Y0 if beam_depth_m is None else 0.0
    y1 = BEAM_BAND_Y1 if beam_depth_m is None else beam_depth_m
    fig.add_shape(
        type="rect",
        x0=0.0,
        y0=y0,
        x1=x_end,
        y1=y1,
        line=dict(color=CONCRETE_OUTLINE, width=2),
        fillcolor=CONCRETE_FILL_2D,
    )


def add_shear_behaviour_pinned_support(
    fig: go.Figure,
    x_pos: float,
    width: float,
    depth: float,
    beam_depth_m: float,
    *,
    roller: bool = False,
) -> None:
    ground_drop = max(
        SUPPORT_GROUND_DROP_BEAM_RATIO * beam_depth_m,
        SUPPORT_GROUND_MIN_DROP_MM / 1000.0,
    )
    ground_y = -depth - ground_drop
    fig.add_shape(
        type="path",
        path=f"M {x_pos - width},{-depth} L {x_pos + width},{-depth} L {x_pos},{0.0} Z",
        line=dict(color=SUPPORT_OUTLINE, width=1.4),
        fillcolor=SUPPORT_FILL,
    )
    fig.add_shape(
        type="line",
        x0=x_pos - width * 1.15,
        y0=ground_y,
        x1=x_pos + width * 1.15,
        y1=ground_y,
        line=dict(color=SUPPORT_GROUND, width=1.0),
    )
    if roller:
        roller_r = max(
            SUPPORT_ROLLER_RADIUS_BEAM_RATIO * beam_depth_m,
            SUPPORT_ROLLER_MIN_RADIUS_MM / 1000.0,
        )
        cy = -depth - depth * 0.45
        fig.add_shape(
            type="circle",
            xref="x",
            yref="y",
            x0=x_pos - roller_r,
            y0=cy - roller_r,
            x1=x_pos + roller_r,
            y1=cy + roller_r,
            line=dict(color=SUPPORT_OUTLINE, width=1.15),
            fillcolor=SUPPORT_ROLLER_FILL,
        )


def add_shear_behaviour_fixed_support(
    fig: go.Figure,
    x_pos: float,
    hatch_dx: float,
    beam_depth_m: float,
) -> None:
    y_min = -SUPPORT_FIXED_OVERHANG_BEAM_RATIO * beam_depth_m
    y_max = beam_depth_m + SUPPORT_FIXED_OVERHANG_BEAM_RATIO * beam_depth_m
    fig.add_shape(
        type="line",
        x0=x_pos,
        y0=y_min,
        x1=x_pos,
        y1=y_max,
        line=dict(color=SUPPORT_OUTLINE, width=6),
    )
    for frac in (0.08, 0.28, 0.48, 0.68, 0.88):
        y_val = y_min + frac * (y_max - y_min)
        fig.add_shape(
            type="line",
            x0=x_pos - hatch_dx,
            y0=y_val + 0.10 * beam_depth_m,
            x1=x_pos,
            y1=y_val - 0.04 * beam_depth_m,
            line=dict(color=SUPPORT_GROUND_HATCH, width=1.0),
        )


def build_shear_behaviour_support_shapes(fig: go.Figure, model: dict[str, Any]) -> None:
    length_m = model["total_length_m"]
    beam_depth_m = model["D_m"]
    support_w = max(length_m * SUPPORT_PIN_WIDTH_SPAN_RATIO, SUPPORT_PIN_MIN_WIDTH_MM / 1000.0)
    support_d = max(beam_depth_m * SUPPORT_PIN_DEPTH_BEAM_RATIO, SUPPORT_PIN_MIN_DEPTH_MM / 1000.0)
    fixed_hatch_dx = max(
        length_m * SUPPORT_FIXED_HATCH_SPAN_RATIO,
        SUPPORT_FIXED_MIN_HATCH_MM / 1000.0,
    )
    support_pair = model.get("support_pair")

    def _draw_labelled_support(x_pos: float, label: str, *, right_edge: bool = False) -> None:
        lbl = str(label or "Pinned").strip().lower()
        if lbl == "fixed":
            add_shear_behaviour_fixed_support(fig, x_pos, fixed_hatch_dx, beam_depth_m)
        elif lbl == "roller":
            add_shear_behaviour_pinned_support(fig, x_pos, support_w, support_d, beam_depth_m, roller=True)
        else:
            add_shear_behaviour_pinned_support(
                fig,
                x_pos,
                support_w,
                support_d,
                beam_depth_m,
                roller=bool(right_edge and str(model.get("support_condition", "")) == "simply_supported"),
            )

    if model["support_condition"] == "cantilever":
        add_shear_behaviour_fixed_support(fig, 0.0, fixed_hatch_dx, beam_depth_m)
        return
    xs = list(model["support_positions"])
    if isinstance(support_pair, tuple) and len(support_pair) == 2 and len(xs) >= 2:
        _draw_labelled_support(xs[0], str(support_pair[0]), right_edge=False)
        _draw_labelled_support(xs[-1], str(support_pair[1]), right_edge=True)
        return
    if model["support_condition"] == "simply_supported" and len(xs) >= 2:
        add_shear_behaviour_pinned_support(fig, xs[0], support_w, support_d, beam_depth_m, roller=False)
        add_shear_behaviour_pinned_support(fig, xs[-1], support_w, support_d, beam_depth_m, roller=True)
        return
    for x_pos in xs:
        add_shear_behaviour_pinned_support(fig, x_pos, support_w, support_d, beam_depth_m, roller=False)


def support_d_region_bounds(model: dict[str, Any]) -> tuple[float, float]:
    beam_length = model["total_length_m"]
    d_region_len = min(max(model["d_m"], 0.0), beam_length * 0.42)
    left_end = min(d_region_len, beam_length)
    right_start = max(beam_length - d_region_len, 0.0)
    return (left_end, right_start)


def build_shear_behaviour_zones(fig: go.Figure, model: dict[str, Any], case_kind: str) -> None:
    beam_length = model["total_length_m"]
    beam_depth_m = model["D_m"]
    left_d_end, right_d_start = support_d_region_bounds(model)

    if model["support_condition"] == "cantilever":
        fig.add_shape(type="rect", x0=0.0, y0=0.0, x1=left_d_end, y1=beam_depth_m, line=dict(width=0), fillcolor="rgba(255,193,7,0.14)", layer="below")
    else:
        fig.add_shape(type="rect", x0=0.0, y0=0.0, x1=left_d_end, y1=beam_depth_m, line=dict(width=0), fillcolor="rgba(255,193,7,0.14)", layer="below")
        fig.add_shape(type="rect", x0=right_d_start, y0=0.0, x1=beam_length, y1=beam_depth_m, line=dict(width=0), fillcolor="rgba(255,193,7,0.14)", layer="below")

    zone_y0 = -0.82 * beam_depth_m
    zone_y1 = -0.58 * beam_depth_m
    zone_label_y = zone_y0 + 0.58 * (zone_y1 - zone_y0)

    def _zone(x0: float, x1: float, text: str, fillcolor: str) -> None:
        if x1 <= x0:
            return
        fig.add_shape(type="rect", x0=x0, y0=zone_y0, x1=x1, y1=zone_y1, line=dict(color="rgba(0,0,0,0.14)", width=1), fillcolor=fillcolor)
        fig.add_annotation(x=(x0 + x1) / 2.0, y=zone_label_y, text=text, showarrow=False, font=dict(size=10, color="rgba(60,60,60,0.96)"))

    if model["support_condition"] == "cantilever":
        _zone(0.0, left_d_end, "D-region", "rgba(255,193,7,0.22)")
        _zone(left_d_end, beam_length, "Shear span (flexural-shear behaviour)", "rgba(33,150,243,0.10)")
        return

    _zone(0.0, left_d_end, "D-region", "rgba(255,193,7,0.22)")
    if right_d_start > left_d_end:
        clear_span = right_d_start - left_d_end
        shear_zone_len = min(max(0.24 * clear_span, 0.75 * model["d_m"]), 0.34 * clear_span)
        left_shear_end = min(left_d_end + shear_zone_len, right_d_start)
        right_shear_start = max(right_d_start - shear_zone_len, left_d_end)
        if left_shear_end > left_d_end:
            _zone(left_d_end, left_shear_end, "Shear span", "rgba(33,150,243,0.10)")
        if right_shear_start > left_shear_end:
            _zone(left_shear_end, right_shear_start, "Flexural-dominated region", "rgba(120,170,255,0.06)")
        if right_d_start > right_shear_start:
            _zone(right_shear_start, right_d_start, "Shear span", "rgba(33,150,243,0.10)")
    _zone(right_d_start, beam_length, "D-region", "rgba(255,193,7,0.22)")


def _safe_float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def display_zone_length(model: dict[str, Any]) -> float:
    return max(model["d_m"], 0.0)


def shear_crack_x_band_m(model: dict[str, Any]) -> tuple[float, float]:
    beam_length = max(_safe_float(model.get("total_length_m", model.get("span_m", 0.0)), 0.0), 0.1)
    d_m = max(_safe_float(model.get("d_m", 0.0), 0.0), 1e-6)
    if d_m < 1e-3:
        d_m = max(0.06 * beam_length, 1e-3)
    m_probe = dict(model)
    m_probe["total_length_m"] = beam_length
    m_probe["d_m"] = d_m
    left_d_end, right_d_start = support_d_region_bounds(m_probe)
    inner = max(right_d_start - left_d_end, 0.0)
    margin = min(max(0.035 * d_m, 0.0015 * beam_length), max(0.25 * inner, 0.002 * beam_length, 1e-6))
    if str(model.get("support_condition", "")) == "cantilever":
        x_lo = left_d_end + margin
        x_hi = beam_length * 0.995
        x_lo = min(x_lo, x_hi - 1e-4 * beam_length)
        return (max(x_lo, 0.0), x_hi)
    x_lo = left_d_end + margin
    x_hi = right_d_start - margin
    if x_hi <= x_lo:
        mid = 0.5 * (left_d_end + right_d_start)
        eps = max(0.0005 * beam_length, 1e-6)
        return (mid - eps, mid + eps)
    return (x_lo, x_hi)


def sample_beam_y(sample_y: float, beam_depth_scale: float = 1.0) -> float:
    sample_beam_height = 0.30
    return sample_y * (beam_depth_scale / sample_beam_height)


def beam_depth_scale(model: dict[str, Any]) -> float:
    return max(_safe_float(model.get("D_m", 0.6), 0.6), 0.1)


def compute_stress_field_geometry(model: dict[str, Any]) -> dict[str, float]:
    L_plot = max(_safe_float(model.get("total_length_m", model.get("span_m", 0.0)), 0.0), 0.1)
    D_plot = beam_depth_scale(model)
    d_plot = max(_safe_float(model.get("d_m", D_plot * 0.9), D_plot * 0.9), 1e-6)
    d6_actual = max(d_plot / 6.0, 0.0)
    zone_len = min(display_zone_length(model), L_plot * 0.42)
    end_zone_len = min(d6_actual, L_plot * 0.42) if d6_actual > 0.0 else zone_len

    beam_left = 0.0
    beam_right = L_plot
    beam_bottom = 0.0
    beam_top = D_plot
    centre_x = 0.5 * (beam_left + beam_right)
    left_deep_limit = min(end_zone_len, beam_right)
    right_deep_limit = max(beam_right - end_zone_len, beam_left)
    flexural_width = max(right_deep_limit - left_deep_limit, 0.0)
    field_pad = max(0.004, D_plot * 0.02)

    tensile_apex_inner_y = min(beam_top - 0.12 * D_plot, max(beam_bottom + 0.12 * D_plot, 0.36 * D_plot))
    tensile_apex_outer_y = min(tensile_apex_inner_y - 0.04 * D_plot, max(beam_bottom + 0.08 * D_plot, 0.22 * D_plot))

    crack_x_lo, crack_x_hi = shear_crack_x_band_m(model)

    return {
        "beam_left": beam_left,
        "beam_right": beam_right,
        "beam_bottom": beam_bottom,
        "beam_top": beam_top,
        "L_plot": L_plot,
        "D_plot": D_plot,
        "d_plot": d_plot,
        "slenderness": L_plot / max(d_plot, 1e-6),
        "left_deep_limit": left_deep_limit,
        "right_deep_limit": right_deep_limit,
        "flexural_width": flexural_width,
        "centre_x": centre_x,
        "top_anchor_y": beam_top - field_pad,
        "bottom_anchor_y": beam_bottom + field_pad,
        "tensile_apex_inner_y": tensile_apex_inner_y,
        "tensile_apex_outer_y": tensile_apex_outer_y,
        "compressive_apex_inner_y": beam_top - tensile_apex_inner_y,
        "compressive_apex_outer_y": beam_top - tensile_apex_outer_y,
        "crack_x_lo": crack_x_lo,
        "crack_x_hi": crack_x_hi,
        "crack_marker_cap_at_centre": True,
    }


def cantilever_behaviour_zones(model: dict[str, Any]) -> tuple[float, float]:
    span_m = max(_safe_float(model.get("span_m", 0.0), 0.0), 0.1)
    d_m = max(_safe_float(model.get("d_m", 0.0), 0.0), 0.05)
    x_deep = min(1.0 * d_m, 0.35 * span_m)
    x_transition = min(2.0 * d_m, 0.55 * span_m)
    min_gap = 0.08 * span_m
    if x_transition <= x_deep:
        x_transition = min(max(x_deep + min_gap, 1.25 * x_deep), 0.55 * span_m)
    if x_transition <= x_deep:
        x_transition = min(span_m * 0.50, x_deep + min_gap)
    return (x_deep, x_transition)


def field_y_limits(beam_depth_m: float = 0.6) -> tuple[float, float]:
    pad = max(0.004, beam_depth_m * 0.02)
    return (0.0 + pad, beam_depth_m - pad)


def clamp_field_points(points: list[tuple[float, float]], beam_depth_m: float = 0.6) -> list[tuple[float, float]]:
    y_min, y_max = field_y_limits(beam_depth_m)
    return [(x_val, min(max(y_val, y_min), y_max)) for x_val, y_val in points]


def add_force_line(
    fig: go.Figure,
    points: list[tuple[float, float]],
    color: str,
    width: float,
    label: str | None = None,
    label_pos: tuple[float, float] | None = None,
    opacity: float = 1.0,
    clamp_to_field: bool = True,
    smoothing: float = FIELD_SPLINE_SMOOTHING,
    beam_depth_m: float = 0.6,
    line_shape: str = "spline",
) -> None:
    plot_points = clamp_field_points(points, beam_depth_m) if clamp_to_field else points
    line_kw: dict[str, Any] = dict(color=color, width=width, shape=line_shape)
    if line_shape == "spline":
        line_kw["smoothing"] = smoothing
    fig.add_trace(
        go.Scatter(
            x=[point[0] for point in plot_points],
            y=[point[1] for point in plot_points],
            mode="lines",
            line=line_kw,
            opacity=opacity,
            hoverinfo="skip",
            showlegend=False,
        )
    )
    if label and label_pos is not None:
        fig.add_annotation(
            x=label_pos[0],
            y=label_pos[1],
            text=label,
            showarrow=False,
            font=dict(size=11, color=color),
        )


def field_line_spec(
    points: list[tuple[float, float]],
    *,
    width: float,
    opacity: float = 1.0,
    label: str | None = None,
    label_pos: tuple[float, float] | None = None,
    smoothing: float | None = None,
) -> dict[str, Any]:
    return {
        "points": points,
        "width": width,
        "opacity": opacity,
        "label": label,
        "label_pos": label_pos,
        "smoothing": smoothing,
    }


def mirror_field_line(spec: dict[str, Any], span_m: float) -> dict[str, Any]:
    label_pos = spec.get("label_pos")
    return {
        **spec,
        "points": [(span_m - x_val, y_val) for x_val, y_val in spec["points"]],
        "label_pos": None if label_pos is None else (span_m - label_pos[0], label_pos[1]),
    }


def build_tension_family(fig: go.Figure, lines: list[dict[str, Any]]) -> None:
    blue = "rgba(0,90,200,0.94)"
    for line in lines:
        add_force_line(
            fig,
            line["points"],
            blue,
            line["width"],
            label=line.get("label"),
            label_pos=line.get("label_pos"),
            opacity=line.get("opacity", 1.0),
            smoothing=line.get("smoothing", FIELD_SPLINE_SMOOTHING),
        )


def build_compression_family(fig: go.Figure, lines: list[dict[str, Any]]) -> None:
    red = "rgba(200,45,45,0.94)"
    for line in lines:
        add_force_line(
            fig,
            line["points"],
            red,
            line["width"],
            label=line.get("label"),
            label_pos=line.get("label_pos"),
            opacity=line.get("opacity", 1.0),
            smoothing=line.get("smoothing", FIELD_SPLINE_SMOOTHING),
        )


def build_crack_cues(fig: go.Figure, cracks: list[dict[str, Any]]) -> None:
    crack_color = "rgba(20,20,20,0.88)"
    for crack in cracks:
        add_force_line(
            fig,
            crack["points"],
            crack_color,
            crack["width"],
            label=crack.get("label"),
            label_pos=crack.get("label_pos"),
            opacity=crack.get("opacity", 1.0),
            smoothing=crack.get("smoothing", FIELD_SPLINE_SMOOTHING),
        )


def render_field_ss_midspan_point(fig: go.Figure, model: dict[str, Any]) -> None:
    span_m = model["span_m"]
    px = span_m / 2.0

    def _p(x_frac: float, sample_y: float) -> tuple[float, float]:
        return (span_m * x_frac, sample_beam_y(sample_y))

    build_compression_family(
        fig,
        [
            field_line_spec([_p(0.08, 0.04), _p(0.22, 0.18), _p(0.38, 0.248), _p(0.46, 0.270), _p(0.54, 0.270), _p(0.62, 0.248), _p(0.78, 0.18), _p(0.92, 0.04)], width=3.4, opacity=0.30),
            field_line_spec([_p(0.14, 0.04), _p(0.24, 0.15), _p(0.36, 0.226), _p(0.46, 0.246), _p(0.54, 0.246), _p(0.64, 0.226), _p(0.76, 0.15), _p(0.86, 0.04)], width=2.4, opacity=0.13),
            field_line_spec([(px, sample_beam_y(0.28)), _p(0.47, 0.282), _p(0.40, 0.281), _p(0.32, 0.280), _p(0.24, 0.246), _p(0.14, 0.140), _p(0.08, 0.060), _p(0.00, 0.000)], width=5, label="Compression", label_pos=_p(0.18, 0.44)),
            field_line_spec([(px, sample_beam_y(0.28)), _p(0.53, 0.282), _p(0.60, 0.281), _p(0.68, 0.280), _p(0.76, 0.246), _p(0.86, 0.140), _p(0.92, 0.060), _p(1.00, 0.000)], width=5),
            field_line_spec([_p(0.12, 0.04), _p(0.22, 0.08), _p(0.30, 0.145), _p(0.38, 0.215), _p(0.44, 0.242)], width=2, opacity=0.18),
            field_line_spec([_p(0.88, 0.04), _p(0.78, 0.08), _p(0.70, 0.145), _p(0.62, 0.215), _p(0.56, 0.242)], width=2, opacity=0.18),
        ],
    )
    build_tension_family(
        fig,
        [
            field_line_spec([_p(0.06, 0.230), _p(0.18, 0.072), _p(0.34, 0.042), _p(0.50, 0.054), _p(0.66, 0.042), _p(0.82, 0.072), _p(0.94, 0.230)], width=5, label="Tension", label_pos=_p(0.50, -0.13)),
            field_line_spec([_p(0.10, 0.250), _p(0.22, 0.102), _p(0.36, 0.084), _p(0.50, 0.096), _p(0.64, 0.084), _p(0.78, 0.102), _p(0.90, 0.250)], width=3, opacity=0.22),
            field_line_spec([_p(0.14, 0.265), _p(0.26, 0.132), _p(0.38, 0.108), _p(0.50, 0.118), _p(0.62, 0.108), _p(0.74, 0.132), _p(0.86, 0.265)], width=2, opacity=0.14),
        ],
    )
    build_crack_cues(
        fig,
        [
            field_line_spec([_p(0.20, 0.04), _p(0.27, 0.08), _p(0.33, 0.13)], width=2.2, opacity=0.86),
            field_line_spec([_p(0.80, 0.04), _p(0.73, 0.08), _p(0.67, 0.13)], width=2.2, opacity=0.86),
        ],
    )


def render_field_ss_udl(fig: go.Figure, model: dict[str, Any]) -> None:
    span_m = model["span_m"]

    def _p(x_frac: float, sample_y: float) -> tuple[float, float]:
        return (span_m * x_frac, sample_beam_y(sample_y))

    build_compression_family(
        fig,
        [
            field_line_spec([_p(0.08, 0.05), _p(0.18, 0.215), _p(0.28, 0.262), _p(0.50, 0.276), _p(0.72, 0.262), _p(0.82, 0.215), _p(0.92, 0.05)], width=5, label="Compression", label_pos=_p(0.18, 0.44)),
            field_line_spec([_p(0.10, 0.05), _p(0.20, 0.19), _p(0.30, 0.215), _p(0.50, 0.242), _p(0.70, 0.215), _p(0.80, 0.19), _p(0.90, 0.05)], width=3.0, opacity=0.24),
            field_line_spec([_p(0.12, 0.05), _p(0.22, 0.13), _p(0.32, 0.17), _p(0.50, 0.20), _p(0.68, 0.17), _p(0.78, 0.13), _p(0.88, 0.05)], width=1.8, opacity=0.12),
        ],
    )
    build_tension_family(
        fig,
        [
            field_line_spec([_p(0.06, 0.015), _p(0.30, 0.022), _p(0.50, 0.034), _p(0.70, 0.022), _p(0.94, 0.015)], width=5, label="Tension", label_pos=_p(0.50, -0.13)),
            field_line_spec([_p(0.10, 0.034), _p(0.20, 0.028), _p(0.30, 0.034), _p(0.50, 0.050), _p(0.70, 0.034), _p(0.80, 0.028), _p(0.90, 0.034)], width=2.6, opacity=0.22),
            field_line_spec([_p(0.12, 0.060), _p(0.22, 0.048), _p(0.34, 0.052), _p(0.50, 0.066), _p(0.66, 0.052), _p(0.78, 0.048), _p(0.88, 0.060)], width=1.8, opacity=0.12),
        ],
    )
    build_crack_cues(
        fig,
        [
            field_line_spec([_p(0.12, 0.05), _p(0.18, 0.048), _p(0.23, 0.062), _p(0.28, 0.10)], width=2.6, label="Crack", label_pos=_p(0.22, 0.15)),
            field_line_spec([_p(0.88, 0.05), _p(0.82, 0.047), _p(0.77, 0.060), _p(0.72, 0.10)], width=2.6),
        ],
    )


def render_field_ss_eccentric_point(fig: go.Figure, model: dict[str, Any]) -> None:
    span_m = model["span_m"]
    load_x = max(0.0, min(model["a_m"], span_m))

    def _p(x_frac: float, sample_y: float) -> tuple[float, float]:
        return (span_m * x_frac, sample_beam_y(sample_y))

    build_compression_family(
        fig,
        [
            field_line_spec([_p(0.08, 0.05), _p(0.18, 0.16), _p(0.26, 0.22), _p(0.46, 0.25), _p(0.72, 0.21), _p(0.82, 0.14), _p(0.92, 0.05)], width=3.0, opacity=0.24),
            field_line_spec([(load_x, sample_beam_y(0.28)), _p(0.24, 0.29), _p(0.12, 0.04)], width=5, label="Compression", label_pos=_p(0.18, 0.44)),
            field_line_spec([(load_x, sample_beam_y(0.28)), _p(0.58, 0.28), _p(0.84, 0.04)], width=4.2),
            field_line_spec([_p(0.24, 0.04), _p(0.40, 0.22), (load_x, sample_beam_y(0.21))], width=2, opacity=0.22),
            field_line_spec([_p(0.08, 0.04), _p(0.16, 0.06), _p(0.28, 0.12), _p(0.40, 0.18), (load_x, sample_beam_y(0.24))], width=1.6, opacity=0.14),
        ],
    )
    build_tension_family(
        fig,
        [
            field_line_spec([_p(0.06, 0.014), _p(0.24, 0.020), _p(0.46, 0.036), _p(0.72, 0.028), _p(0.94, 0.016)], width=5, label="Tension", label_pos=_p(0.52, -0.13)),
            field_line_spec([_p(0.09, 0.038), _p(0.18, 0.030), _p(0.28, 0.036), _p(0.48, 0.058), _p(0.72, 0.046), _p(0.82, 0.034), _p(0.92, 0.042)], width=2.6, opacity=0.22),
            field_line_spec([_p(0.12, 0.068), _p(0.22, 0.052), _p(0.30, 0.058), _p(0.48, 0.078), _p(0.68, 0.060), _p(0.78, 0.050), _p(0.88, 0.062)], width=1.8, opacity=0.12),
        ],
    )
    if load_x <= span_m / 2.0:
        cracks = [
            field_line_spec([(span_m * 0.08, sample_beam_y(0.05)), (span_m * 0.17, sample_beam_y(0.04)), (max(load_x - 0.05 * span_m, span_m * 0.22), sample_beam_y(0.12))], width=2.6, label="Crack", label_pos=_p(0.18, 0.16)),
            field_line_spec([_p(0.84, 0.05), _p(0.79, 0.05), _p(0.72, 0.09)], width=1.9, opacity=0.50),
        ]
    else:
        cracks = [
            field_line_spec([_p(0.16, 0.05), _p(0.21, 0.05), _p(0.28, 0.09)], width=1.9, opacity=0.50),
            field_line_spec([(span_m * 0.92, sample_beam_y(0.05)), (span_m * 0.83, sample_beam_y(0.04)), (min(load_x + 0.05 * span_m, span_m * 0.78), sample_beam_y(0.12))], width=2.6, label="Crack", label_pos=_p(0.80, 0.16)),
        ]
    build_crack_cues(fig, cracks)


def render_field_ss_near_support_point(fig: go.Figure, model: dict[str, Any]) -> None:
    span_m = model["span_m"]
    load_x = max(0.0, min(model["a_m"], span_m))
    load_left = load_x <= span_m / 2.0
    if not load_left:
        load_x = span_m - load_x

    def _p(x_frac: float, sample_y: float) -> tuple[float, float]:
        return (span_m * x_frac, sample_beam_y(sample_y))

    tension = [
        field_line_spec([_p(0.04, 0.016), _p(0.14, 0.022), _p(0.24, 0.038), _p(0.40, 0.058), _p(0.68, 0.044), _p(0.94, 0.018)], width=5, label="Tension", label_pos=_p(0.58, -0.13)),
        field_line_spec([_p(0.06, 0.042), _p(0.16, 0.034), _p(0.28, 0.046), _p(0.44, 0.072), _p(0.66, 0.056), _p(0.90, 0.028)], width=2.6, opacity=0.22),
        field_line_spec([_p(0.08, 0.070), _p(0.18, 0.054), _p(0.30, 0.064), _p(0.46, 0.090), _p(0.64, 0.066), _p(0.84, 0.040)], width=1.8, opacity=0.12),
    ]
    compression = [
        field_line_spec([_p(0.06, 0.04), _p(0.16, 0.16), _p(0.26, 0.24), _p(0.46, 0.23), _p(0.72, 0.16), _p(0.92, 0.05)], width=3.0, opacity=0.24),
        field_line_spec([(load_x, sample_beam_y(0.28)), _p(0.26, 0.29), _p(0.18, 0.22), _p(0.10, 0.08), _p(0.00, 0.00)], width=5, label="Compression", label_pos=_p(0.18, 0.44)),
        field_line_spec([(load_x, sample_beam_y(0.27)), _p(0.40, 0.26), _p(0.60, 0.20), _p(0.86, 0.05)], width=4.0),
        field_line_spec([_p(0.12, 0.04), _p(0.20, 0.09), _p(0.30, 0.17), (min(load_x, span_m * 0.34), sample_beam_y(0.24))], width=1.8, opacity=0.18),
    ]
    cracks = [
        field_line_spec([_p(0.08, 0.05), _p(0.15, 0.07), (max(load_x - 0.04 * span_m, span_m * 0.24), sample_beam_y(0.13))], width=2.5, label="Crack", label_pos=_p(0.18, 0.16)),
        field_line_spec([_p(0.78, 0.05), _p(0.72, 0.05), _p(0.64, 0.09)], width=1.8, opacity=0.40),
    ]
    if not load_left:
        tension = [mirror_field_line(line, span_m) for line in tension]
        compression = [mirror_field_line(line, span_m) for line in compression]
        cracks = [mirror_field_line(line, span_m) for line in cracks]

    build_compression_family(fig, compression)
    build_tension_family(fig, tension)
    build_crack_cues(fig, cracks)


def render_field_cantilever_tip(fig: go.Figure, model: dict[str, Any]) -> None:
    span_m = model["span_m"]
    red = "rgba(200,45,45,0.94)"
    blue = "rgba(0,90,200,0.94)"
    crack_color = "rgba(20,20,20,0.88)"
    x_red_cross_start = 0.30 * span_m
    x_red_cross_end = 0.38 * span_m
    x_blue_cross_start = 0.32 * span_m
    x_blue_cross_end = 0.40 * span_m

    compression_label = (0.21 * span_m, sample_beam_y(0.285))
    tension_label = (0.22 * span_m, sample_beam_y(0.020))

    def _trace(
        points: list[tuple[float, float]],
        color: str,
        width: float,
        *,
        opacity: float = 1.0,
        smoothing: float = 0.9,
    ) -> None:
        plot_points = clamp_field_points(points)
        fig.add_trace(
            go.Scatter(
                x=[p[0] for p in plot_points],
                y=[p[1] for p in plot_points],
                mode="lines",
                line=dict(color=color, width=width, shape="spline", smoothing=smoothing),
                opacity=opacity,
                hoverinfo="skip",
                showlegend=False,
            )
        )

    main_red = [
        (0.02 * span_m, sample_beam_y(0.285)),
        (0.05 * span_m, sample_beam_y(0.272)),
        (0.09 * span_m, sample_beam_y(0.248)),
        (0.14 * span_m, sample_beam_y(0.215)),
        (0.20 * span_m, sample_beam_y(0.182)),
        (0.27 * span_m, sample_beam_y(0.165)),
        (x_red_cross_start, sample_beam_y(0.148)),
        (x_red_cross_end, sample_beam_y(0.142)),
        (0.46 * span_m, sample_beam_y(0.138)),
        (0.60 * span_m, sample_beam_y(0.122)),
        (0.76 * span_m, sample_beam_y(0.113)),
        (0.92 * span_m, sample_beam_y(0.106)),
        (0.98 * span_m, sample_beam_y(0.103)),
    ]
    comp_upper = [
        (0.03 * span_m, sample_beam_y(0.255)),
        (0.07 * span_m, sample_beam_y(0.242)),
        (0.11 * span_m, sample_beam_y(0.220)),
        (0.17 * span_m, sample_beam_y(0.190)),
        (0.24 * span_m, sample_beam_y(0.158)),
        (x_red_cross_start, sample_beam_y(0.152)),
        (x_red_cross_end, sample_beam_y(0.146)),
        (0.48 * span_m, sample_beam_y(0.138)),
        (0.64 * span_m, sample_beam_y(0.128)),
        (0.82 * span_m, sample_beam_y(0.118)),
        (0.96 * span_m, sample_beam_y(0.111)),
    ]
    comp_inner = [
        (0.04 * span_m, sample_beam_y(0.228)),
        (0.08 * span_m, sample_beam_y(0.215)),
        (0.13 * span_m, sample_beam_y(0.196)),
        (0.19 * span_m, sample_beam_y(0.176)),
        (0.26 * span_m, sample_beam_y(0.160)),
        (x_red_cross_start, sample_beam_y(0.150)),
        (x_red_cross_end, sample_beam_y(0.146)),
        (0.50 * span_m, sample_beam_y(0.142)),
        (0.68 * span_m, sample_beam_y(0.136)),
        (0.86 * span_m, sample_beam_y(0.131)),
        (0.96 * span_m, sample_beam_y(0.128)),
    ]
    main_blue = [
        (0.02 * span_m, sample_beam_y(0.070)),
        (0.05 * span_m, sample_beam_y(0.078)),
        (0.09 * span_m, sample_beam_y(0.092)),
        (0.14 * span_m, sample_beam_y(0.108)),
        (0.20 * span_m, sample_beam_y(0.124)),
        (0.27 * span_m, sample_beam_y(0.136)),
        (x_blue_cross_start, sample_beam_y(0.142)),
        (x_blue_cross_end, sample_beam_y(0.148)),
        (0.46 * span_m, sample_beam_y(0.154)),
        (0.60 * span_m, sample_beam_y(0.163)),
        (0.76 * span_m, sample_beam_y(0.171)),
        (0.92 * span_m, sample_beam_y(0.178)),
        (0.98 * span_m, sample_beam_y(0.180)),
    ]
    tens_lower = [
        (0.03 * span_m, sample_beam_y(0.090)),
        (0.07 * span_m, sample_beam_y(0.098)),
        (0.11 * span_m, sample_beam_y(0.108)),
        (0.17 * span_m, sample_beam_y(0.120)),
        (0.24 * span_m, sample_beam_y(0.138)),
        (x_blue_cross_start, sample_beam_y(0.142)),
        (x_blue_cross_end, sample_beam_y(0.146)),
        (0.48 * span_m, sample_beam_y(0.156)),
        (0.64 * span_m, sample_beam_y(0.164)),
        (0.82 * span_m, sample_beam_y(0.171)),
        (0.96 * span_m, sample_beam_y(0.174)),
    ]
    tens_inner = [
        (0.04 * span_m, sample_beam_y(0.110)),
        (0.08 * span_m, sample_beam_y(0.116)),
        (0.13 * span_m, sample_beam_y(0.124)),
        (0.19 * span_m, sample_beam_y(0.132)),
        (0.26 * span_m, sample_beam_y(0.139)),
        (x_blue_cross_start, sample_beam_y(0.144)),
        (x_blue_cross_end, sample_beam_y(0.148)),
        (0.50 * span_m, sample_beam_y(0.152)),
        (0.68 * span_m, sample_beam_y(0.157)),
        (0.86 * span_m, sample_beam_y(0.161)),
        (0.96 * span_m, sample_beam_y(0.163)),
    ]

    _trace(comp_upper, red, 2.0, opacity=0.18, smoothing=0.92)
    _trace(comp_inner, red, 2.0, opacity=0.12, smoothing=0.92)
    _trace(tens_lower, blue, 2.0, opacity=0.18, smoothing=0.92)
    _trace(tens_inner, blue, 2.0, opacity=0.12, smoothing=0.92)
    _trace(main_red, red, 5.0, opacity=1.0, smoothing=0.90)
    _trace(main_blue, blue, 5.0, opacity=1.0, smoothing=0.90)

    fig.add_annotation(
        x=compression_label[0],
        y=compression_label[1],
        text="Compression",
        showarrow=False,
        font=dict(size=11, color=red),
    )
    fig.add_annotation(
        x=tension_label[0],
        y=tension_label[1],
        text="Tension",
        showarrow=False,
        font=dict(size=11, color=blue),
    )

    crack_points = [
        (0.045 * span_m, sample_beam_y(0.082)),
        (0.095 * span_m, sample_beam_y(0.108)),
        (0.125 * span_m, sample_beam_y(0.126)),
        (0.185 * span_m, sample_beam_y(0.175)),
    ]
    _trace(crack_points, crack_color, 2.6, opacity=0.92, smoothing=0.55)
    fig.add_annotation(
        x=0.175 * span_m,
        y=sample_beam_y(0.154),
        text="Crack",
        showarrow=False,
        font=dict(size=11, color=crack_color),
    )


def render_field_cantilever_udl(fig: go.Figure, model: dict[str, Any]) -> None:
    span_m = model["span_m"]
    y_top = BEAM_BAND_Y1
    y_bot = BEAM_BAND_Y0
    y_mid = (y_top + y_bot) / 2.0
    red = "rgba(200,45,45,0.94)"
    blue = "rgba(0,90,200,0.94)"
    crack_color = "rgba(20,20,20,0.88)"
    tension_label = (0.20 * span_m, y_bot - 0.055)
    compression_label = (0.24 * span_m, y_top + 0.055)

    red_paths = [
        ([span_m, 0.75 * span_m, 0.40 * span_m, 0.15 * span_m, 0.0], [y_top - 0.005, y_top - 0.012, y_mid + 0.012, y_mid + 0.022, y_mid + 0.030], 5.0, 1.0),
        ([0.96 * span_m, 0.73 * span_m, 0.40 * span_m, 0.17 * span_m, 0.02 * span_m], [y_top - 0.030, y_top - 0.036, y_mid + 0.018, y_mid + 0.028, y_mid + 0.036], 2.6, 0.18),
    ]
    blue_paths = [
        ([span_m, 0.70 * span_m, 0.40 * span_m, 0.20 * span_m, 0.0], [y_bot + 0.005, y_bot + 0.014, y_mid - 0.008, y_mid - 0.013, y_mid - 0.018], 5.0, 1.0),
        ([0.96 * span_m, 0.68 * span_m, 0.40 * span_m, 0.22 * span_m, 0.02 * span_m], [y_bot + 0.025, y_bot + 0.032, y_mid - 0.003, y_mid - 0.008, y_mid - 0.013], 2.6, 0.20),
    ]

    for x_vals, y_vals, width, opacity in red_paths:
        fig.add_trace(go.Scatter(x=x_vals, y=y_vals, mode="lines", line=dict(color=red, width=width, shape="linear"), opacity=opacity, hoverinfo="skip", showlegend=False))
    for x_vals, y_vals, width, opacity in blue_paths:
        fig.add_trace(go.Scatter(x=x_vals, y=y_vals, mode="lines", line=dict(color=blue, width=width, shape="linear"), opacity=opacity, hoverinfo="skip", showlegend=False))

    fig.add_annotation(x=compression_label[0], y=compression_label[1], text="Compression", showarrow=False, font=dict(size=11, color=red))
    fig.add_annotation(x=tension_label[0], y=tension_label[1], text="Tension", showarrow=False, font=dict(size=11, color=blue))
    fig.add_trace(
        go.Scatter(
            x=[0.10 * span_m, 0.15 * span_m, 0.21 * span_m],
            y=[y_bot + 0.050, y_bot + 0.080, y_bot + 0.114],
            mode="lines",
            line=dict(color=crack_color, width=2.4, shape="linear"),
            hoverinfo="skip",
            showlegend=False,
        )
    )
    fig.add_annotation(x=0.16 * span_m, y=y_bot + 0.074, text="Crack", showarrow=False, font=dict(size=11, color=crack_color))


def render_field_cantilever_eccentric(fig: go.Figure, model: dict[str, Any]) -> None:
    span_m = model["span_m"]
    load_x = max(0.0, min(model["a_cant_m"], span_m))
    y_top = BEAM_BAND_Y1
    y_bot = BEAM_BAND_Y0
    y_mid = (y_top + y_bot) / 2.0
    red = "rgba(200,45,45,0.94)"
    blue = "rgba(0,90,200,0.94)"
    crack_color = "rgba(20,20,20,0.88)"
    tension_label = (0.18 * span_m, y_bot - 0.055)
    compression_label = (0.22 * span_m, y_top + 0.055)

    red_paths = [
        ([load_x, 0.72 * span_m, 0.38 * span_m, 0.16 * span_m, 0.0], [y_top, y_top - 0.01, y_mid + 0.01, y_mid + 0.02, y_mid + 0.03], 5.0, 1.0),
        ([load_x, 0.70 * span_m, 0.38 * span_m, 0.18 * span_m, 0.02 * span_m], [y_top - 0.025, y_top - 0.032, y_mid + 0.014, y_mid + 0.024, y_mid + 0.034], 2.4, 0.18),
    ]
    blue_paths = [
        ([load_x, 0.68 * span_m, 0.40 * span_m, 0.20 * span_m, 0.0], [y_bot, y_bot + 0.01, y_mid - 0.01, y_mid - 0.015, y_mid - 0.02], 5.0, 1.0),
        ([load_x, 0.66 * span_m, 0.40 * span_m, 0.22 * span_m, 0.02 * span_m], [y_bot + 0.02, y_bot + 0.028, y_mid - 0.005, y_mid - 0.010, y_mid - 0.015], 2.4, 0.20),
    ]

    for x_vals, y_vals, width, opacity in red_paths:
        fig.add_trace(go.Scatter(x=x_vals, y=y_vals, mode="lines", line=dict(color=red, width=width, shape="linear"), opacity=opacity, hoverinfo="skip", showlegend=False))
    for x_vals, y_vals, width, opacity in blue_paths:
        fig.add_trace(go.Scatter(x=x_vals, y=y_vals, mode="lines", line=dict(color=blue, width=width, shape="linear"), opacity=opacity, hoverinfo="skip", showlegend=False))

    fig.add_annotation(x=compression_label[0], y=compression_label[1], text="Compression", showarrow=False, font=dict(size=11, color=red))
    fig.add_annotation(x=tension_label[0], y=tension_label[1], text="Tension", showarrow=False, font=dict(size=11, color=blue))
    fig.add_trace(
        go.Scatter(
            x=[0.10 * span_m, 0.15 * span_m, 0.22 * span_m],
            y=[y_bot + 0.048, y_bot + 0.076, y_bot + 0.118],
            mode="lines",
            line=dict(color=crack_color, width=2.4, shape="linear"),
            hoverinfo="skip",
            showlegend=False,
        )
    )
    fig.add_annotation(x=0.17 * span_m, y=y_bot + 0.072, text="Crack", showarrow=False, font=dict(size=11, color=crack_color))


def add_trajectory_family(
    fig: go.Figure,
    lines: list[list[tuple[float, float]]],
    color: str,
    *,
    width: float = 2.4,
    opacity: float = 0.62,
    smoothing: float = 0.97,
    beam_depth_m: float = 0.6,
) -> None:
    for pts in lines:
        add_force_line(
            fig,
            pts,
            color,
            width,
            opacity=opacity,
            smoothing=smoothing,
            beam_depth_m=beam_depth_m,
        )


def add_ordered_trajectory_family(
    fig: go.Figure,
    lines: list[list[tuple[float, float]]],
    color: str,
    *,
    width: float = 2.4,
    opacity: float = 0.62,
    smoothing: float = 0.97,
    beam_depth_m: float = 0.6,
    line_shape: str = "spline",
) -> None:
    for idx, pts in enumerate(lines):
        width_scale, opacity_scale = trajectory_visual_weight(idx, len(lines))
        add_force_line(
            fig,
            pts,
            color,
            width * width_scale,
            opacity=opacity * opacity_scale,
            smoothing=smoothing,
            beam_depth_m=beam_depth_m,
            line_shape=line_shape,
        )


def scaled_rgba_alpha(color: str, alpha_scale: float) -> str:
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


def trajectory_visual_weight(line_idx: int, line_count: int) -> tuple[float, float]:
    if line_count <= 1:
        return (1.0, 1.0)
    t = line_idx / (line_count - 1)
    emphasis = t ** 1.15
    opacity_scale = 1.0 - 0.42 * emphasis
    width_scale = 1.02 - 0.08 * (t ** 1.05)
    return (width_scale, opacity_scale)


def sample_curve_point_and_tangent(
    pts: list[tuple[float, float]],
    curve_fraction: float,
) -> tuple[tuple[float, float], tuple[float, float]] | None:
    if len(pts) < 3:
        return None
    idx = min(max(int(round(curve_fraction * (len(pts) - 1))), 1), len(pts) - 2)
    px, py = pts[idx]
    x_prev, y_prev = pts[idx - 1]
    x_next, y_next = pts[idx + 1]
    dx = x_next - x_prev
    dy = y_next - y_prev
    norm = math.hypot(dx, dy)
    if norm <= 1e-9:
        return None
    return ((px, py), (dx / norm, dy / norm))


def add_trajectory_direction_arrow(
    fig: go.Figure,
    pts: list[tuple[float, float]],
    color: str,
    *,
    beam_depth_m: float,
    curve_fraction: float,
    alpha_scale: float,
    reverse: bool = False,
) -> None:
    sample = sample_curve_point_and_tangent(pts, curve_fraction)
    if sample is None:
        return
    (px, py), (tx, ty) = sample
    if reverse:
        tx = -tx
        ty = -ty
    curve_span = abs(pts[-1][0] - pts[0][0])
    arrow_len = min(max(beam_depth_m * 0.16, curve_span * 0.025), beam_depth_m * 0.24)
    x_start = px - 0.5 * arrow_len * tx
    y_start = py - 0.5 * arrow_len * ty
    x_end = px + 0.5 * arrow_len * tx
    y_end = py + 0.5 * arrow_len * ty
    fig.add_annotation(
        x=x_end,
        y=y_end,
        ax=x_start,
        ay=y_start,
        axref="x",
        ayref="y",
        text="",
        showarrow=True,
        arrowhead=2,
        arrowsize=0.72,
        arrowwidth=1.0,
        arrowcolor=scaled_rgba_alpha(color, alpha_scale),
    )


def add_sparse_trajectory_arrows(
    fig: go.Figure,
    lines: list[list[tuple[float, float]]],
    color: str,
    *,
    beam_depth_m: float,
) -> None:
    if not lines:
        return
    line_idx = min(max(1, len(lines) // 3), len(lines) - 1)
    _, opacity_scale = trajectory_visual_weight(line_idx, len(lines))
    for curve_fraction in (0.34, 0.66):
        add_trajectory_direction_arrow(
            fig,
            lines[line_idx],
            color,
            beam_depth_m=beam_depth_m,
            curve_fraction=curve_fraction,
            alpha_scale=opacity_scale * 0.72,
        )


def add_load_flow_overlay(
    fig: go.Figure,
    lines: list[list[tuple[float, float]]],
    color: str,
    *,
    beam_depth_m: float,
    line_indices: list[int],
    outward_from_centre: bool = False,
    animate_motion: bool = False,
) -> None:
    if not lines:
        return

    seen: set[int] = set()
    for raw_idx in line_indices:
        idx = max(0, min(len(lines) - 1, raw_idx))
        if idx in seen:
            continue
        seen.add(idx)
        pts = lines[idx]
        fig.add_trace(
            go.Scatter(
                x=[pt[0] for pt in pts],
                y=[pt[1] for pt in pts],
                mode="lines",
                line=dict(
                    color=scaled_rgba_alpha(color, 0.95),
                    width=3.2,
                    shape="spline",
                    smoothing=0.64,
                    dash="12px,10px",
                ),
                opacity=0.96,
                hoverinfo="skip",
                showlegend=False,
            )
        )

        if animate_motion and len(pts) >= 8:
            mid_idx = len(pts) // 2
            animated_paths = [pts]
            if outward_from_centre:
                animated_paths = [
                    list(reversed(pts[: mid_idx + 1])),
                    pts[mid_idx:],
                ]

            for animated_pts in animated_paths:
                window = max(4, min(7, len(animated_pts) // 2))
                fig.add_trace(
                    go.Scatter(
                        x=[pt[0] for pt in animated_pts[:window]],
                        y=[pt[1] for pt in animated_pts[:window]],
                        mode="lines",
                        line=dict(
                            color=scaled_rgba_alpha(color, 1.0),
                            width=3.8,
                            shape="spline",
                            smoothing=0.64,
                        ),
                        opacity=0.98,
                        hoverinfo="skip",
                        showlegend=False,
                        meta={
                            "animate_flow": True,
                            "flow_x": [pt[0] for pt in animated_pts],
                            "flow_y": [pt[1] for pt in animated_pts],
                            "window": window,
                            "step": 1,
                        },
                    )
                )

        if outward_from_centre:
            add_trajectory_direction_arrow(
                fig,
                pts,
                color,
                beam_depth_m=beam_depth_m,
                curve_fraction=0.30,
                alpha_scale=0.98,
                reverse=True,
            )
            add_trajectory_direction_arrow(
                fig,
                pts,
                color,
                beam_depth_m=beam_depth_m,
                curve_fraction=0.70,
                alpha_scale=0.98,
                reverse=False,
            )
        else:
            for curve_fraction in (0.28, 0.52, 0.76):
                add_trajectory_direction_arrow(
                    fig,
                    pts,
                    color,
                    beam_depth_m=beam_depth_m,
                    curve_fraction=curve_fraction,
                    alpha_scale=0.92,
                )


def linear_interpolate_points(
    p0: tuple[float, float],
    p1: tuple[float, float],
    *,
    n: int,
) -> list[tuple[float, float]]:
    n = max(2, int(n))
    return [
        (
            float(p0[0]) + (float(p1[0]) - float(p0[0])) * (i / (n - 1)),
            float(p0[1]) + (float(p1[1]) - float(p0[1])) * (i / (n - 1)),
        )
        for i in range(n)
    ]


def densify_polyline(
    pts: list[tuple[float, float]],
    *,
    n_per_seg: int = 16,
) -> list[tuple[float, float]]:
    if len(pts) < 2:
        return [(float(a[0]), float(a[1])) for a in pts]
    out: list[tuple[float, float]] = []
    for i in range(len(pts) - 1):
        seg = linear_interpolate_points(pts[i], pts[i + 1], n=n_per_seg)
        if out:
            out.extend(seg[1:])
        else:
            out.extend(seg)
    return out


def add_stm_flow_polyline(
    fig: go.Figure,
    pts: list[tuple[float, float]],
    color: str,
    *,
    beam_depth_m: float,
    animate_motion: bool = True,
) -> None:
    """STM-only load path: faint dashed guide + sliding pulse + direction arrows."""
    if len(pts) < 2:
        return
    dense = densify_polyline(pts, n_per_seg=18)
    if len(dense) < 3:
        return
    xs = [p[0] for p in dense]
    ys = [p[1] for p in dense]
    fig.add_trace(
        go.Scatter(
            x=xs,
            y=ys,
            mode="lines",
            line=dict(
                color=scaled_rgba_alpha(color, 0.58),
                width=2.5,
                shape="linear",
                dash="10px,8px",
            ),
            opacity=0.86,
            hoverinfo="skip",
            showlegend=False,
        )
    )
    if animate_motion and len(dense) >= 8:
        window = max(4, min(8, len(dense) // 2))
        fig.add_trace(
            go.Scatter(
                x=xs[:window],
                y=ys[:window],
                mode="lines",
                line=dict(
                    color=scaled_rgba_alpha(color, 0.98),
                    width=3.9,
                    shape="linear",
                ),
                opacity=0.96,
                hoverinfo="skip",
                showlegend=False,
                meta={
                    "animate_flow": True,
                    "flow_x": xs,
                    "flow_y": ys,
                    "window": window,
                    "step": 1,
                },
            )
        )
    for curve_fraction in (0.34, 0.66):
        add_trajectory_direction_arrow(
            fig,
            dense,
            color,
            beam_depth_m=beam_depth_m,
            curve_fraction=curve_fraction,
            alpha_scale=0.94,
        )


def blend_x(span_m: float, frac: float) -> float:
    return frac * span_m


def parabolic_trajectory(
    x0: float,
    x1: float,
    y_end: float,
    y_peak: float,
    n: int = 9,
) -> list[tuple[float, float]]:
    """Symmetric parabola-like trajectory from x0 to x1."""
    pts: list[tuple[float, float]] = []
    for i in range(n):
        t = i / (n - 1)
        x = x0 + t * (x1 - x0)
        shape = (4.0 * t * (1.0 - t)) ** 0.7
        y = y_end + (y_peak - y_end) * shape
        pts.append((x, y))
    return pts


def symmetric_arch(
    x0: float,
    x1: float,
    y_end: float,
    y_mid: float,
    *,
    n: int = 21,
    sharpness: float = 0.78,
    end_curvature_boost: float = 1.22,
) -> list[tuple[float, float]]:
    """Single smooth symmetric arch from x0 to x1."""
    pts: list[tuple[float, float]] = []
    for i in range(n):
        t = i / (n - 1)
        x = x0 + t * (x1 - x0)
        base_shape = (4.0 * t * (1.0 - t)) ** sharpness
        shape = 1.0 - (1.0 - base_shape) ** end_curvature_boost
        y = y_end + (y_mid - y_end) * shape
        pts.append((x, y))
    return pts


def mirror_trajectory_about_middepth(
    pts: list[tuple[float, float]],
    beam_depth_m: float,
) -> list[tuple[float, float]]:
    return [(x, beam_depth_m - y) for x, y in pts]


def compute_trajectory_count(slenderness: float) -> int:
    unclamped = 4.0 + 1.15 * math.sqrt(max(slenderness - 2.5, 0.0))
    return max(4, min(7, int(round(unclamped))))


def sample_anchor_band(count: int) -> list[float]:
    if count <= 1:
        return [1.0]
    samples: list[float] = []
    for idx in range(count):
        t = idx / (count - 1)
        eased = t ** 0.90
        relief = 0.05 * (1.0 - t) * t
        samples.append(min(1.0, max(0.0, eased + relief)))
    return samples


def compute_trajectory_half_widths(geometry: dict[str, float], count: int) -> list[float]:
    half_span = max(geometry["centre_x"] - geometry["beam_left"], 1e-6)
    half_flexural_width = max(0.5 * geometry["flexural_width"], 0.18 * geometry["d_plot"])
    deep_zone_width = max(geometry["left_deep_limit"] - geometry["beam_left"], 0.0)

    inner_half_width = min(
        half_span * 0.58,
        max(0.22 * half_flexural_width, 0.40 * geometry["d_plot"]),
    )
    outer_half_width = min(
        half_span * 0.985,
        half_flexural_width + 0.92 * deep_zone_width,
    )

    if outer_half_width <= inner_half_width:
        inner_half_width = min(half_span * 0.44, max(0.18 * half_span, 0.36 * geometry["d_plot"]))
        outer_half_width = half_span * 0.985

    width_progression = [sample ** 1.75 for sample in sample_anchor_band(count)]
    return [
        inner_half_width + (outer_half_width - inner_half_width) * sample
        for sample in width_progression
    ]


def trajectory_bow_scale(geometry: dict[str, float], width_factor: float) -> float:
    slenderness = geometry["slenderness"]
    slenderness_factor = min(max((slenderness - 7.0) / 9.0, 0.0), 1.0)
    outer_family_factor = width_factor ** 1.4
    base_scale = 1.0 - 0.12 * slenderness_factor * outer_family_factor
    return base_scale * geometry.get("bow_gain", 1.0)


def trajectory_end_curvature_boost(geometry: dict[str, float], width_factor: float) -> float:
    slenderness_factor = min(max((geometry["slenderness"] - 5.5) / 8.5, 0.0), 1.0)
    outer_factor = width_factor ** 1.2
    base_boost = 1.42 + 0.34 * outer_factor + 0.16 * slenderness_factor
    return base_boost * geometry.get("end_curvature_gain", 1.0)


def build_tensile_trajectories(geometry: dict[str, float], count: int) -> list[list[tuple[float, float]]]:
    widths = compute_trajectory_half_widths(geometry, count)
    samples = sample_anchor_band(count)
    lines: list[list[tuple[float, float]]] = []

    for width_factor, half_width in zip(samples, widths):
        x0 = geometry["centre_x"] - half_width
        x1 = geometry["centre_x"] + half_width
        y_end = geometry["top_anchor_y"] - 0.022 * geometry["D_plot"] * (width_factor ** 1.05)
        base_y_mid = geometry["tensile_apex_inner_y"] + (
            geometry["tensile_apex_outer_y"] - geometry["tensile_apex_inner_y"]
        ) * (width_factor ** 0.92)
        y_mid = y_end + (base_y_mid - y_end) * trajectory_bow_scale(geometry, width_factor)
        sharpness = 1.08 - 0.10 * width_factor
        lines.append(
            symmetric_arch(
                x0,
                x1,
                y_end,
                y_mid,
                n=25,
                sharpness=sharpness,
                end_curvature_boost=trajectory_end_curvature_boost(geometry, width_factor),
            )
        )

    return lines


def build_compressive_trajectories(geometry: dict[str, float], count: int) -> list[list[tuple[float, float]]]:
    widths = compute_trajectory_half_widths(geometry, count)
    samples = sample_anchor_band(count)
    lines: list[list[tuple[float, float]]] = []

    for width_factor, half_width in zip(samples, widths):
        x0 = geometry["centre_x"] - half_width
        x1 = geometry["centre_x"] + half_width
        y_end = geometry["bottom_anchor_y"] + 0.022 * geometry["D_plot"] * (width_factor ** 1.05)
        base_y_mid = geometry["compressive_apex_inner_y"] + (
            geometry["compressive_apex_outer_y"] - geometry["compressive_apex_inner_y"]
        ) * (width_factor ** 0.92)
        y_mid = y_end + (base_y_mid - y_end) * trajectory_bow_scale(geometry, width_factor)
        sharpness = 1.08 - 0.10 * width_factor
        lines.append(
            symmetric_arch(
                x0,
                x1,
                y_end,
                y_mid,
                n=25,
                sharpness=sharpness,
                end_curvature_boost=trajectory_end_curvature_boost(geometry, width_factor),
            )
        )

    return lines


def support_zone_x_left() -> float:
    return 0.0


def support_zone_x_right(span_m: float) -> float:
    return span_m


def support_edge_y_top(beam_depth_m: float) -> float:
    return beam_depth_m - max(0.004, beam_depth_m * 0.02)


def support_edge_y_bot(beam_depth_m: float) -> float:
    return max(0.004, beam_depth_m * 0.02)


def stm_snap_ratio_to_grid(r_raw: float) -> float:
    r = min(max(r_raw, 0.55), 0.95)
    return min(STM_SNAP_X_RATIOS, key=lambda s: abs(s - r))


def stm_y_snap_levels_dv(
    d_v_m: float,
    beam_depth_m: float,
    bottom_tie_y: float,
) -> list[float]:
    y_hi = beam_depth_m - max(0.004, beam_depth_m * 0.02)
    levels = [frac * d_v_m for frac in STM_SNAP_Y_DV_FRACS]
    return [y for y in levels if y > bottom_tie_y + 1e-9 and y < y_hi - 1e-9]


def stm_snap_inner_top_left(
    x_bot: float,
    bottom_tie_y: float,
    d_region_width: float,
    tan_th: float,
    d_v_m: float,
    beam_depth_m: float,
    node_pad: float,
    dy_nom: float,
) -> tuple[float, float]:
    d_region_w = max(float(d_region_width), 1e-12)
    x_top_cand = x_bot + dy_nom / tan_th
    r_raw = (x_top_cand - 0.0) / d_region_w
    r_snap = stm_snap_ratio_to_grid(r_raw)
    x_top = min(max(r_snap * d_region_w, x_bot + node_pad), d_region_w)
    dy = (x_top - x_bot) * tan_th
    y_top = bottom_tie_y + dy

    y_targets = stm_y_snap_levels_dv(d_v_m, beam_depth_m, bottom_tie_y)
    if y_targets:
        y_snap = min(y_targets, key=lambda yt: abs(yt - y_top))
        y_top = y_snap
        x_top = x_bot + (y_top - bottom_tie_y) / tan_th
        if x_top > d_region_w:
            x_top = d_region_w
            y_top = bottom_tie_y + (x_top - x_bot) * tan_th
        elif x_top < x_bot + node_pad:
            x_top = x_bot + node_pad
            y_top = bottom_tie_y + (x_top - x_bot) * tan_th

    return x_top, y_top


def stm_snap_inner_top_right(
    x_bot: float,
    bottom_tie_y: float,
    span_m: float,
    right_d_start: float,
    tan_th: float,
    d_v_m: float,
    beam_depth_m: float,
    node_pad: float,
    dy_nom: float,
) -> tuple[float, float]:
    d_region_w = max(span_m - float(right_d_start), 1e-12)
    x_top_cand = x_bot - dy_nom / tan_th
    r_raw = (span_m - x_top_cand) / d_region_w
    r_snap = stm_snap_ratio_to_grid(r_raw)
    x_top = max(min(span_m - r_snap * d_region_w, x_bot - node_pad), right_d_start)
    dy = (x_bot - x_top) * tan_th
    y_top = bottom_tie_y + dy

    y_targets = stm_y_snap_levels_dv(d_v_m, beam_depth_m, bottom_tie_y)
    if y_targets:
        y_snap = min(y_targets, key=lambda yt: abs(yt - y_top))
        y_top = y_snap
        x_top = x_bot - (y_top - bottom_tie_y) / tan_th
        if x_top < right_d_start:
            x_top = right_d_start
            y_top = bottom_tie_y + (x_bot - x_top) * tan_th
        elif x_top > x_bot - node_pad:
            x_top = x_bot - node_pad
            y_top = bottom_tie_y + (x_bot - x_top) * tan_th

    return x_top, y_top


def compute_stm_simply_supported_d_region_nodes(
    model: dict[str, Any],
    *,
    theta_v_deg: float,
) -> dict[str, Any] | None:
    span_m = max(_safe_float(model.get("span_m", model.get("total_length_m", 0.0)), 0.0), 0.1)
    beam_depth_m = beam_depth_scale(model)
    left_d_end, right_d_start = support_d_region_bounds(model)
    if left_d_end <= 1e-6 or right_d_start >= span_m - 1e-6 or right_d_start <= left_d_end + 1e-6:
        return None
    bottom_tie_y = sample_beam_y(0.04, beam_depth_m)
    top_y_nom = sample_beam_y(0.24, beam_depth_m)
    dy_nom = top_y_nom - bottom_tie_y
    if dy_nom <= 1e-12:
        return None

    d_v_m = max(_safe_float(model.get("d_m", beam_depth_m * 0.9), beam_depth_m * 0.9), 1e-6)

    theta_v = _safe_float(theta_v_deg, 45.0)
    th = math.radians(max(1.0, min(float(theta_v), 89.0)))
    tan_th = math.tan(th)
    if tan_th <= 1e-12:
        return None
    node_pad = max(1e-4 * beam_depth_m, 1e-6 * span_m)

    x_bot_out_L = min(0.12 * left_d_end, 0.05 * span_m)
    x_bot_out_L = max(x_bot_out_L, 0.02 * left_d_end)
    x_bot_out_L = min(x_bot_out_L, 0.42 * left_d_end)

    x_bot_out_R = span_m - x_bot_out_L

    x_top_in_L, y_top_in_L = stm_snap_inner_top_left(
        x_bot_out_L,
        bottom_tie_y,
        float(left_d_end),
        tan_th,
        d_v_m,
        beam_depth_m,
        node_pad,
        dy_nom,
    )
    x_top_in_R, y_top_in_R = stm_snap_inner_top_right(
        x_bot_out_R,
        bottom_tie_y,
        span_m,
        float(right_d_start),
        tan_th,
        d_v_m,
        beam_depth_m,
        node_pad,
        dy_nom,
    )

    y_hi_field = beam_depth_m - max(0.004, beam_depth_m * 0.02)
    top_y = min(
        max(top_y_nom, max(y_top_in_L, y_top_in_R) + 0.022 * beam_depth_m),
        y_hi_field,
    )

    x_top_out_L = min(max(0.05 * left_d_end, 0.20 * x_top_in_L), 0.88 * x_top_in_L)
    x_top_out_L = max(x_top_out_L, 0.04 * left_d_end)
    if x_top_out_L >= x_top_in_L - node_pad:
        x_top_out_L = max(0.04 * left_d_end, x_top_in_L - 4.0 * node_pad)

    x_top_out_R = span_m - x_top_out_L

    return {
        "span_m": span_m,
        "beam_depth_m": beam_depth_m,
        "bottom_tie_y": bottom_tie_y,
        "top_y": top_y,
        "left_d_end": left_d_end,
        "right_d_start": right_d_start,
        "x_bot_out_L": x_bot_out_L,
        "x_top_in_L": x_top_in_L,
        "y_top_in_L": y_top_in_L,
        "x_top_out_L": x_top_out_L,
        "x_bot_out_R": x_bot_out_R,
        "x_top_in_R": x_top_in_R,
        "y_top_in_R": y_top_in_R,
        "x_top_out_R": x_top_out_R,
        "theta_v_deg": float(theta_v),
        "theta_stm_deg": float(theta_v),
    }


def compute_stm_cantilever_d_region_nodes(
    model: dict[str, Any],
    *,
    theta_v_deg: float,
) -> dict[str, Any] | None:
    span_m = max(_safe_float(model.get("span_m", model.get("total_length_m", 0.0)), 0.0), 0.1)
    beam_depth_m = beam_depth_scale(model)
    left_d_end, _ = support_d_region_bounds(model)
    if left_d_end <= 1e-6:
        return None
    bottom_tie_y = sample_beam_y(0.04, beam_depth_m)
    top_y_nom = sample_beam_y(0.24, beam_depth_m)
    dy_nom = top_y_nom - bottom_tie_y
    if dy_nom <= 1e-12:
        return None

    d_v_m = max(_safe_float(model.get("d_m", beam_depth_m * 0.9), beam_depth_m * 0.9), 1e-6)

    theta_v = _safe_float(theta_v_deg, 45.0)
    th = math.radians(max(1.0, min(float(theta_v), 89.0)))
    tan_th = math.tan(th)
    if tan_th <= 1e-12:
        return None
    node_pad = max(1e-4 * beam_depth_m, 1e-6 * span_m)

    x_bot_out = min(0.12 * left_d_end, 0.05 * span_m)
    x_bot_out = max(x_bot_out, 0.02 * left_d_end)
    x_bot_out = min(x_bot_out, 0.42 * left_d_end)

    x_top_in, y_top_in = stm_snap_inner_top_left(
        x_bot_out,
        bottom_tie_y,
        float(left_d_end),
        tan_th,
        d_v_m,
        beam_depth_m,
        node_pad,
        dy_nom,
    )

    y_hi_field = beam_depth_m - max(0.004, beam_depth_m * 0.02)
    top_y = min(max(top_y_nom, y_top_in + 0.022 * beam_depth_m), y_hi_field)

    x_top_out = min(max(0.05 * left_d_end, 0.20 * x_top_in), 0.88 * x_top_in)
    x_top_out = max(x_top_out, 0.04 * left_d_end)
    if x_top_out >= x_top_in - node_pad:
        x_top_out = max(0.04 * left_d_end, x_top_in - 4.0 * node_pad)

    return {
        "span_m": span_m,
        "beam_depth_m": beam_depth_m,
        "bottom_tie_y": bottom_tie_y,
        "top_y": top_y,
        "left_d_end": left_d_end,
        "x_bot_out": x_bot_out,
        "x_top_in": x_top_in,
        "y_top_in": y_top_in,
        "x_top_out": x_top_out,
        "theta_v_deg": float(theta_v),
        "theta_stm_deg": float(theta_v),
    }


def add_strut_tie_node(fig: go.Figure, x: float, y: float) -> None:
    fig.add_trace(
        go.Scatter(
            x=[x],
            y=[y],
            mode="markers",
            marker=dict(size=9, color="rgba(30,30,30,0.95)"),
            hoverinfo="skip",
            showlegend=False,
        )
    )


def add_stm_member(
    fig: go.Figure,
    start: tuple[float, float],
    end: tuple[float, float],
    color: str,
    width: float,
    *,
    opacity: float = 1.0,
    beam_depth_m: float = 0.6,
) -> None:
    add_force_line(
        fig,
        [start, end],
        color,
        width,
        opacity=opacity,
        smoothing=0.0,
        beam_depth_m=beam_depth_m,
        line_shape="linear",
    )


def add_stm_axis_vertical(
    fig: go.Figure,
    x: float,
    y0: float,
    y1: float,
    color: str,
    width: float,
    *,
    opacity: float = 1.0,
    beam_depth_m: float = 0.6,
) -> None:
    """Exactly vertical segment (constant x); not derived from strut direction."""
    ya, yb = (y0, y1) if y1 >= y0 else (y1, y0)
    add_force_line(
        fig,
        [(x, ya), (x, yb)],
        color,
        width,
        opacity=opacity,
        smoothing=0.0,
        beam_depth_m=beam_depth_m,
        line_shape="linear",
    )


def add_stm_joint_angle_annotation(
    fig: go.Figure,
    joint: tuple[float, float],
    strut_end: tuple[float, float],
    text: str,
    *,
    color: str,
    beam_depth_m: float,
    tie_direction: str,
) -> None:
    dx = strut_end[0] - joint[0]
    dy = strut_end[1] - joint[1]
    strut_angle = math.atan2(dy, dx)
    base_angle = 0.0 if tie_direction == "right" else math.pi
    angle_delta = strut_angle - base_angle
    if abs(angle_delta) <= 1e-9:
        return

    radius = 0.10 * beam_depth_m
    arc_pts: list[tuple[float, float]] = []
    steps = 14
    for idx in range(steps):
        t = idx / (steps - 1)
        angle = base_angle + angle_delta * t
        arc_pts.append((joint[0] + radius * math.cos(angle), joint[1] + radius * math.sin(angle)))

    fig.add_trace(
        go.Scatter(
            x=[pt[0] for pt in arc_pts],
            y=[pt[1] for pt in arc_pts],
            mode="lines",
            line=dict(color=color, width=1.4, shape="linear"),
            opacity=0.88,
            hoverinfo="skip",
            showlegend=False,
        )
    )

    bisector_angle = base_angle + 0.52 * angle_delta
    label_radius = 0.18 * beam_depth_m
    fig.add_annotation(
        x=joint[0] + label_radius * math.cos(bisector_angle),
        y=joint[1] + label_radius * math.sin(bisector_angle) - 0.03 * beam_depth_m,
        text=text,
        showarrow=False,
        font=dict(size=10, color=color),
    )


def render_strut_tie_ss_udl(
    fig: go.Figure,
    model: dict[str, Any],
    *,
    theta_v_deg: float,
    show_labels: bool = True,
) -> None:
    g = compute_stm_simply_supported_d_region_nodes(model, theta_v_deg=theta_v_deg)
    if g is None:
        return

    span_m = g["span_m"]
    beam_depth_m = g["beam_depth_m"]
    bottom_tie_y = g["bottom_tie_y"]
    theta_v_lbl = float(g.get("theta_v_deg", g.get("theta_stm_deg", 45.0)))
    theta_text = f"\u03b8<sub>v</sub> = {theta_v_lbl:.1f}\u00b0"

    red_main = "rgba(200,45,45,0.92)"
    red_faint = "rgba(200,45,45,0.40)"
    blue = "rgba(0,90,200,0.92)"

    bottom_left = (g["x_bot_out_L"], bottom_tie_y)
    bottom_right = (g["x_bot_out_R"], bottom_tie_y)
    y_top_in_L = float(g["y_top_in_L"])
    y_top_in_R = float(g["y_top_in_R"])
    top_left_outer = (g["x_bot_out_L"], y_top_in_L)
    top_left_inner = (g["x_top_in_L"], y_top_in_L)
    top_right_inner = (g["x_top_in_R"], y_top_in_R)
    top_right_outer = (g["x_bot_out_R"], y_top_in_R)

    add_stm_member(
        fig,
        (0.0, bottom_tie_y),
        (span_m, bottom_tie_y),
        blue,
        4.4,
        opacity=1.0,
        beam_depth_m=beam_depth_m,
    )
    add_stm_axis_vertical(
        fig,
        bottom_left[0],
        bottom_tie_y,
        y_top_in_L,
        red_faint,
        2.8,
        opacity=0.72,
        beam_depth_m=beam_depth_m,
    )
    add_stm_axis_vertical(
        fig,
        bottom_right[0],
        bottom_tie_y,
        y_top_in_R,
        red_faint,
        2.8,
        opacity=0.72,
        beam_depth_m=beam_depth_m,
    )
    for start, end, line_color, line_width, line_opacity in (
        (top_left_outer, top_left_inner, red_main, 4.2, 1.0),
        (top_right_inner, top_right_outer, red_main, 4.2, 1.0),
        (bottom_left, top_left_inner, red_main, 3.6, 0.88),
        (top_right_inner, bottom_right, red_main, 3.6, 0.88),
    ):
        add_stm_member(fig, start, end, line_color, line_width, opacity=line_opacity, beam_depth_m=beam_depth_m)

    for node_x, node_y in (
        bottom_left,
        bottom_right,
        top_left_outer,
        top_left_inner,
        top_right_inner,
        top_right_outer,
    ):
        add_strut_tie_node(fig, node_x, node_y)

    if bool(model.get("show_stm_overlay", False)):
        add_stm_joint_angle_annotation(
            fig,
            bottom_left,
            (g["x_top_in_L"], y_top_in_L),
            theta_text,
            color="rgba(125,40,40,0.90)",
            beam_depth_m=beam_depth_m,
            tie_direction="right",
        )
        add_stm_joint_angle_annotation(
            fig,
            bottom_right,
            (g["x_top_in_R"], y_top_in_R),
            theta_text,
            color="rgba(125,40,40,0.90)",
            beam_depth_m=beam_depth_m,
            tie_direction="left",
        )

    if show_labels:
        fig.add_annotation(
            x=min(0.5 * g["left_d_end"], 0.16 * span_m),
            y=sample_beam_y(0.31, beam_depth_m),
            text="Compression struts",
            showarrow=False,
            font=dict(size=11, color=red_main),
        )
        fig.add_annotation(
            x=0.50 * span_m,
            y=bottom_tie_y - 0.06 * beam_depth_m,
            text="Tension tie",
            showarrow=False,
            font=dict(size=11, color=blue),
        )


def render_strut_tie_ss_midspan_point(
    fig: go.Figure,
    model: dict[str, Any],
    *,
    theta_v_deg: float,
    show_labels: bool = True,
) -> None:
    render_strut_tie_ss_udl(fig, model, theta_v_deg=theta_v_deg, show_labels=show_labels)


def render_strut_tie_ss_eccentric_point(
    fig: go.Figure,
    model: dict[str, Any],
    *,
    theta_v_deg: float,
    show_labels: bool = True,
) -> None:
    render_strut_tie_ss_udl(fig, model, theta_v_deg=theta_v_deg, show_labels=show_labels)


def render_strut_tie_ss_near_support_point(
    fig: go.Figure,
    model: dict[str, Any],
    *,
    theta_v_deg: float,
    show_labels: bool = True,
) -> None:
    render_strut_tie_ss_eccentric_point(fig, model, theta_v_deg=theta_v_deg, show_labels=show_labels)


def render_strut_tie_cantilever_tip(
    fig: go.Figure,
    model: dict[str, Any],
    *,
    theta_v_deg: float,
    show_labels: bool = True,
) -> None:
    g = compute_stm_cantilever_d_region_nodes(model, theta_v_deg=theta_v_deg)
    if g is None:
        return

    span_m = g["span_m"]
    beam_depth_m = g["beam_depth_m"]
    bottom_tie_y = g["bottom_tie_y"]
    theta_v_lbl = float(g.get("theta_v_deg", g.get("theta_stm_deg", 45.0)))
    theta_text = f"\u03b8<sub>v</sub> = {theta_v_lbl:.1f}\u00b0"

    red_main = "rgba(200,45,45,0.92)"
    red_faint = "rgba(200,45,45,0.40)"
    blue = "rgba(0,90,200,0.92)"

    y_top_in = float(g["y_top_in"])
    bot_out = (g["x_bot_out"], bottom_tie_y)
    top_out = (g["x_bot_out"], y_top_in)
    top_in = (g["x_top_in"], y_top_in)

    add_stm_member(
        fig,
        (0.0, bottom_tie_y),
        (span_m, bottom_tie_y),
        blue,
        4.4,
        opacity=1.0,
        beam_depth_m=beam_depth_m,
    )
    add_stm_axis_vertical(
        fig,
        bot_out[0],
        bottom_tie_y,
        y_top_in,
        red_faint,
        2.8,
        opacity=0.72,
        beam_depth_m=beam_depth_m,
    )
    for start, end, line_color, line_width, line_opacity in (
        (top_out, top_in, red_main, 4.2, 1.0),
        (bot_out, top_in, red_main, 3.6, 0.88),
    ):
        add_stm_member(fig, start, end, line_color, line_width, opacity=line_opacity, beam_depth_m=beam_depth_m)

    for node_x, node_y in (bot_out, top_out, top_in):
        add_strut_tie_node(fig, node_x, node_y)

    if bool(model.get("show_stm_overlay", False)):
        add_stm_joint_angle_annotation(
            fig,
            bot_out,
            top_in,
            theta_text,
            color="rgba(125,40,40,0.90)",
            beam_depth_m=beam_depth_m,
            tie_direction="right",
        )

    if show_labels:
        fig.add_annotation(
            x=min(0.45 * g["left_d_end"], 0.14 * span_m),
            y=sample_beam_y(0.30, beam_depth_m),
            text="Compression strut",
            showarrow=False,
            font=dict(size=11, color=red_main),
        )
        fig.add_annotation(
            x=0.50 * span_m,
            y=bottom_tie_y - 0.06 * beam_depth_m,
            text="Tension tie",
            showarrow=False,
            font=dict(size=11, color=blue),
        )


def render_strut_tie_cantilever_udl(
    fig: go.Figure,
    model: dict[str, Any],
    *,
    theta_v_deg: float,
    show_labels: bool = True,
) -> None:
    render_strut_tie_cantilever_tip(fig, model, theta_v_deg=theta_v_deg, show_labels=show_labels)


def render_strut_tie_cantilever_eccentric(
    fig: go.Figure,
    model: dict[str, Any],
    *,
    theta_v_deg: float,
    show_labels: bool = True,
) -> None:
    render_strut_tie_cantilever_tip(fig, model, theta_v_deg=theta_v_deg, show_labels=show_labels)


def render_stm_overlay(
    fig: go.Figure,
    model: dict[str, Any],
    case_kind: str,
    *,
    theta_v_deg: float,
) -> None:
    show_titles = bool(model.get("show_stm_overlay", False))
    if case_kind == "ss_midspan_point":
        render_strut_tie_ss_midspan_point(fig, model, theta_v_deg=theta_v_deg, show_labels=False)
        if show_titles:
            add_stm_overlay_labels(fig, model, case_kind, theta_v_deg=theta_v_deg)
        return
    if case_kind == "ss_udl":
        render_strut_tie_ss_udl(fig, model, theta_v_deg=theta_v_deg, show_labels=False)
        if show_titles:
            add_stm_overlay_labels(fig, model, case_kind, theta_v_deg=theta_v_deg)
        return
    if case_kind == "ss_near_support_point":
        render_strut_tie_ss_near_support_point(fig, model, theta_v_deg=theta_v_deg, show_labels=False)
        if show_titles:
            add_stm_overlay_labels(fig, model, case_kind, theta_v_deg=theta_v_deg)
        return
    if case_kind == "ss_eccentric_point":
        render_strut_tie_ss_eccentric_point(fig, model, theta_v_deg=theta_v_deg, show_labels=False)
        if show_titles:
            add_stm_overlay_labels(fig, model, case_kind, theta_v_deg=theta_v_deg)
        return
    if case_kind == "cantilever_tip":
        render_strut_tie_cantilever_tip(fig, model, theta_v_deg=theta_v_deg, show_labels=False)
        if show_titles:
            add_stm_overlay_labels(fig, model, case_kind, theta_v_deg=theta_v_deg)
        return
    if case_kind == "cantilever_udl":
        render_strut_tie_cantilever_udl(fig, model, theta_v_deg=theta_v_deg, show_labels=False)
        if show_titles:
            add_stm_overlay_labels(fig, model, case_kind, theta_v_deg=theta_v_deg)
        return
    if case_kind == "cantilever_eccentric":
        render_strut_tie_cantilever_eccentric(fig, model, theta_v_deg=theta_v_deg, show_labels=False)
        if show_titles:
            add_stm_overlay_labels(fig, model, case_kind, theta_v_deg=theta_v_deg)
        return
    render_strut_tie_ss_udl(fig, model, theta_v_deg=theta_v_deg, show_labels=False)
    if show_titles:
        add_stm_overlay_labels(fig, model, case_kind, theta_v_deg=theta_v_deg)


def add_stm_overlay_labels(
    fig: go.Figure,
    model: dict[str, Any],
    case_kind: str,
    *,
    theta_v_deg: float,
) -> None:
    span_m = model["span_m"]
    beam_depth_m = beam_depth_scale(model)
    red = "rgba(200,45,45,0.96)"
    blue = "rgba(0,90,200,0.96)"

    if case_kind in {
        "ss_midspan_point",
        "ss_udl",
        "ss_near_support_point",
        "ss_eccentric_point",
    }:
        g = compute_stm_simply_supported_d_region_nodes(model, theta_v_deg=theta_v_deg)
        if g:
            bot_sup_l = (g["x_bot_out_L"], g["bottom_tie_y"])
            top_in_l = (g["x_top_in_L"], float(g.get("y_top_in_L", g["top_y"])))
            fig.add_annotation(
                x=0.55 * bot_sup_l[0] + 0.45 * top_in_l[0],
                y=0.55 * bot_sup_l[1] + 0.45 * top_in_l[1] + 0.04 * beam_depth_m,
                text="Compression strut",
                showarrow=False,
                font=dict(size=10, color=red),
                bgcolor="rgba(255,255,255,0.72)",
            )
            fig.add_annotation(
                x=0.50 * span_m,
                y=g["bottom_tie_y"] - 0.06 * beam_depth_m,
                text="Tension tie",
                showarrow=False,
                font=dict(size=10, color=blue),
                bgcolor="rgba(255,255,255,0.72)",
            )
        return

    if case_kind in {"cantilever_tip", "cantilever_udl", "cantilever_eccentric"}:
        g = compute_stm_cantilever_d_region_nodes(model, theta_v_deg=theta_v_deg)
        if g:
            fig.add_annotation(
                x=0.52 * g["x_bot_out"] + 0.48 * g["x_top_in"],
                y=0.52 * g["bottom_tie_y"] + 0.48 * float(g.get("y_top_in", g["top_y"])) + 0.03 * beam_depth_m,
                text="Compression strut",
                showarrow=False,
                font=dict(size=10, color=red),
                bgcolor="rgba(255,255,255,0.72)",
            )
            fig.add_annotation(
                x=0.50 * span_m,
                y=g["bottom_tie_y"] - 0.06 * beam_depth_m,
                text="Tension tie",
                showarrow=False,
                font=dict(size=10, color=blue),
                bgcolor="rgba(255,255,255,0.72)",
            )
        return

    g_fallback = compute_stm_simply_supported_d_region_nodes(model, theta_v_deg=theta_v_deg)
    if g_fallback:
        bot_sup_l = (g_fallback["x_bot_out_L"], g_fallback["bottom_tie_y"])
        top_in_l = (g_fallback["x_top_in_L"], float(g_fallback.get("y_top_in_L", g_fallback["top_y"])))
        fig.add_annotation(
            x=0.55 * bot_sup_l[0] + 0.45 * top_in_l[0],
            y=0.55 * bot_sup_l[1] + 0.45 * top_in_l[1] + 0.04 * beam_depth_m,
            text="Compression strut",
            showarrow=False,
            font=dict(size=10, color=red),
            bgcolor="rgba(255,255,255,0.72)",
        )
        fig.add_annotation(
            x=0.50 * span_m,
            y=g_fallback["bottom_tie_y"] - 0.06 * beam_depth_m,
            text="Tension tie",
            showarrow=False,
            font=dict(size=10, color=blue),
            bgcolor="rgba(255,255,255,0.72)",
        )
        return

    load_x = max(0.0, min(model.get("a_m", 0.5 * span_m), span_m))
    fig.add_annotation(
        x=max(0.14 * span_m, load_x * 0.78),
        y=sample_beam_y(0.24, beam_depth_m),
        text="Compression strut",
        showarrow=False,
        font=dict(size=10, color=red),
        bgcolor="rgba(255,255,255,0.72)",
    )
    fig.add_annotation(
        x=0.50 * span_m,
        y=sample_beam_y(-0.02, beam_depth_m),
        text="Tension tie",
        showarrow=False,
        font=dict(size=10, color=blue),
        bgcolor="rgba(255,255,255,0.72)",
    )


def render_stm_flow_overlay(
    fig: go.Figure,
    model: dict[str, Any],
    case_kind: str,
    *,
    theta_v_deg: float,
) -> None:
    if not bool(model.get("show_stm_flow", False)):
        return
    beam_depth_m = beam_depth_scale(model)
    red = "rgba(210,50,50,0.96)"
    blue = "rgba(0,95,215,0.96)"

    def _ss_flow() -> None:
        g = compute_stm_simply_supported_d_region_nodes(model, theta_v_deg=theta_v_deg)
        if g is None:
            return
        bottom_tie_y = g["bottom_tie_y"]
        top_y = g["top_y"]
        y_tli = float(g.get("y_top_in_L", top_y))
        y_tri = float(g.get("y_top_in_R", top_y))
        mid_x = 0.5 * (float(g["left_d_end"]) + float(g["right_d_start"]))
        bl = (g["x_bot_out_L"], bottom_tie_y)
        br = (g["x_bot_out_R"], bottom_tie_y)
        tli, tlo = (g["x_top_in_L"], y_tli), (g["x_bot_out_L"], y_tli)
        tri, tro = (g["x_top_in_R"], y_tri), (g["x_bot_out_R"], y_tri)
        add_stm_flow_polyline(fig, [tli, tlo], red, beam_depth_m=beam_depth_m)
        add_stm_flow_polyline(fig, [tli, bl], red, beam_depth_m=beam_depth_m)
        add_stm_flow_polyline(fig, [(bl[0], bottom_tie_y), (bl[0], y_tli)], red, beam_depth_m=beam_depth_m)
        add_stm_flow_polyline(fig, [tri, tro], red, beam_depth_m=beam_depth_m)
        add_stm_flow_polyline(fig, [tri, br], red, beam_depth_m=beam_depth_m)
        add_stm_flow_polyline(fig, [(br[0], bottom_tie_y), (br[0], y_tri)], red, beam_depth_m=beam_depth_m)
        add_stm_flow_polyline(fig, [bl, (mid_x, bottom_tie_y)], blue, beam_depth_m=beam_depth_m)
        add_stm_flow_polyline(fig, [br, (mid_x, bottom_tie_y)], blue, beam_depth_m=beam_depth_m)

    if case_kind in {
        "ss_midspan_point",
        "ss_udl",
        "ss_near_support_point",
        "ss_eccentric_point",
    }:
        _ss_flow()
        return
    if case_kind in {"cantilever_tip", "cantilever_udl", "cantilever_eccentric"}:
        g = compute_stm_cantilever_d_region_nodes(model, theta_v_deg=theta_v_deg)
        if g is None:
            return
        span_m = float(g["span_m"])
        bottom_tie_y = g["bottom_tie_y"]
        top_y = g["top_y"]
        y_tin = float(g.get("y_top_in", top_y))
        bot = (g["x_bot_out"], bottom_tie_y)
        tout, tin = (g["x_bot_out"], y_tin), (g["x_top_in"], y_tin)
        tie_end = (max(min(span_m * 0.90, span_m - 0.04 * span_m), bot[0] + 0.08 * span_m), bottom_tie_y)
        add_stm_flow_polyline(fig, [tin, tout], red, beam_depth_m=beam_depth_m)
        add_stm_flow_polyline(fig, [tin, bot], red, beam_depth_m=beam_depth_m)
        add_stm_flow_polyline(fig, [(bot[0], bottom_tie_y), (bot[0], y_tin)], red, beam_depth_m=beam_depth_m)
        add_stm_flow_polyline(fig, [bot, tie_end], blue, beam_depth_m=beam_depth_m)
        return

    _ss_flow()


def segment_intersection(
    a0: tuple[float, float],
    a1: tuple[float, float],
    b0: tuple[float, float],
    b1: tuple[float, float],
) -> tuple[float, float, float, float] | None:
    ax = a1[0] - a0[0]
    ay = a1[1] - a0[1]
    bx = b1[0] - b0[0]
    by = b1[1] - b0[1]
    denom = ax * by - ay * bx
    if abs(denom) <= 1e-9:
        return None

    dx = b0[0] - a0[0]
    dy = b0[1] - a0[1]
    t = (dx * by - dy * bx) / denom
    u = (dx * ay - dy * ax) / denom
    if not (0.0 <= t <= 1.0 and 0.0 <= u <= 1.0):
        return None

    return (a0[0] + t * ax, a0[1] + t * ay, t, u)


def polyline_polyline_best_hit(
    pc: list[tuple[float, float]],
    pt: list[tuple[float, float]],
    x_lo: float,
    x_hi: float,
) -> tuple[float, float, float, float, float, float] | None:
    """Rightmost segment-segment hit between two polylines within x in [x_lo, x_hi]."""
    best_x = -1.0
    best: tuple[float, float, float, float, float, float] | None = None
    for i in range(len(pc) - 1):
        for j in range(len(pt) - 1):
            hit = segment_intersection(pc[i], pc[i + 1], pt[j], pt[j + 1])
            if hit is None:
                continue
            px, py = hit[0], hit[1]
            if not (x_lo <= px <= x_hi):
                continue
            if px <= best_x:
                continue
            tcx = pc[i + 1][0] - pc[i][0]
            tcy = pc[i + 1][1] - pc[i][1]
            ttx = pt[j + 1][0] - pt[j][0]
            tty = pt[j + 1][1] - pt[j][1]
            best_x = px
            best = (px, py, tcx, tcy, ttx, tty)
    return best


def polyline_y_at_x(poly: list[tuple[float, float]], xq: float) -> float | None:
    """Linearly interpolated y on polyline at x = xq (first matching segment)."""
    for i in range(len(poly) - 1):
        x0, y0 = poly[i]
        x1, y1 = poly[i + 1]
        xmin, xmax = min(x0, x1), max(x0, x1)
        if xmin - 1e-9 <= xq <= xmax + 1e-9:
            if abs(x1 - x0) < 1e-12:
                return 0.5 * (y0 + y1)
            t = (xq - x0) / (x1 - x0)
            if -1e-6 <= t <= 1.0 + 1e-6:
                return y0 + t * (y1 - y0)
    return None


def polyline_tangent_at_x(poly: list[tuple[float, float]], xq: float) -> tuple[float, float] | None:
    """Unnormalised tangent (dx, dy) on the segment that contains xq."""
    for i in range(len(poly) - 1):
        x0, y0 = poly[i]
        x1, y1 = poly[i + 1]
        xmin, xmax = min(x0, x1), max(x0, x1)
        if xmin - 1e-9 <= xq <= xmax + 1e-9:
            return (x1 - x0, y1 - y0)
    return None


def polyline_segment_best_hit(
    poly: list[tuple[float, float]],
    s0: tuple[float, float],
    s1: tuple[float, float],
    x_lo: float,
    x_hi: float,
) -> tuple[float, float, float, float] | None:
    """Rightmost intersection of polyline with segment s0-s1 inside x band; returns px, py, tx, ty."""
    best_x = -1.0
    best: tuple[float, float, float, float] | None = None
    for i in range(len(poly) - 1):
        hit = segment_intersection(poly[i], poly[i + 1], s0, s1)
        if hit is None:
            continue
        px, py = hit[0], hit[1]
        if not (x_lo <= px <= x_hi):
            continue
        if px <= best_x:
            continue
        tx = poly[i + 1][0] - poly[i][0]
        ty = poly[i + 1][1] - poly[i][1]
        best_x = px
        best = (px, py, tx, ty)
    return best


def cantilever_refine_crack_hit_for_compression_field(
    h: dict[str, float],
    compression: list[list[tuple[float, float]]],
    span_m: float,
    *,
    x_lo: float,
    x_hi: float,
) -> dict[str, float]:
    """
    Shift hit right and vertically centre between two adjacent compression trajectories.
    """
    px = float(h["x"])
    py = float(h["y"])
    x_shift_frac = 0.030
    acw_deg = 4.0
    square_extra_deg = 20.0
    xq = min(px + x_shift_frac * span_m, span_m * 0.97)
    xq = min(max(xq, x_lo), x_hi)

    samples: list[tuple[float, int]] = []
    for idx, curve in enumerate(compression):
        yv = polyline_y_at_x(curve, xq)
        if yv is not None:
            samples.append((yv, idx))
    samples.sort(key=lambda t: -t[0])

    tcx: float
    tcy: float
    y_new: float
    if len(samples) >= 2:
        chosen = 0
        for i in range(len(samples) - 1):
            y_a = samples[i][0]
            y_b = samples[i + 1][0]
            y_top = max(y_a, y_b)
            y_bot = min(y_a, y_b)
            if y_bot <= py <= y_top:
                chosen = i
                break
        y_a, ia = samples[chosen]
        y_b, ib = samples[chosen + 1]
        y_new = 0.5 * (y_a + y_b)
        t1 = polyline_tangent_at_x(compression[ia], xq)
        t2 = polyline_tangent_at_x(compression[ib], xq)
        if t1 is not None and t2 is not None:
            tcx = 0.5 * (t1[0] + t2[0])
            tcy = 0.5 * (t1[1] + t2[1])
        elif t1 is not None:
            tcx, tcy = float(t1[0]), float(t1[1])
        elif t2 is not None:
            tcx, tcy = float(t2[0]), float(t2[1])
        else:
            tcx, tcy = 1.0, -0.35
    else:
        y_new = py
        outer = compression[-1] if compression else []
        t0 = polyline_tangent_at_x(outer, xq) if outer else None
        if t0 is not None:
            tcx, tcy = float(t0[0]), float(t0[1])
        else:
            tcx, tcy = 1.0, -0.35

    nrm = math.hypot(tcx, tcy)
    if nrm > 1e-12:
        tcx, tcy = tcx / nrm, tcy / nrm
    comp_deg = math.degrees(math.atan2(tcy, tcx))
    along_deg = comp_deg + acw_deg
    crack_rad = math.radians(along_deg)
    principal_deg = along_deg - square_extra_deg
    return {
        "x": xq,
        "y": y_new,
        "crack_angle_rad": crack_rad,
        "principal_deg": principal_deg,
    }


def cantilever_principal_crack_hits(
    compression: list[list[tuple[float, float]]],
    tension: list[list[tuple[float, float]]],
    span_m: float,
    model: dict[str, Any],
    *,
    theta_v_deg: float,
) -> list[dict[str, float]]:
    if len(compression) < 2 or len(tension) < 2:
        return []
    band_lo, band_hi = shear_crack_x_band_m(model)
    x_lo = max(0.28 * span_m, band_lo)
    x_hi = min(0.93 * span_m, band_hi)
    if x_hi <= x_lo:
        x_lo, x_hi = band_lo, band_hi
        if x_hi <= x_lo:
            x_lo = min(band_lo, span_m * 0.92)
            x_hi = max(band_hi, x_lo + 1e-4 * span_m)
    raw: list[dict[str, float]] = []

    def _push_from_comp_tens(pc: list[tuple[float, float]], pt: list[tuple[float, float]]) -> None:
        hit = polyline_polyline_best_hit(pc, pt, x_lo, x_hi)
        if hit is None:
            return
        px, py, tcx, tcy, ttx, tty = hit
        nc = math.hypot(tcx, tcy)
        nt = math.hypot(ttx, tty)
        if nc < 1e-12 or nt < 1e-12:
            return
        tcx, tcy = tcx / nc, tcy / nc
        ttx, tty = ttx / nt, tty / nt
        tens_ang = math.atan2(tty, ttx)
        crack_ang = tens_ang + 0.5 * math.pi + math.radians(20.0)
        principal_deg = math.degrees(math.atan2(tcy, tcx))
        raw.append(
            {
                "x": px,
                "y": py,
                "crack_angle_rad": crack_ang,
                "principal_deg": principal_deg,
            }
        )

    _push_from_comp_tens(compression[-1], tension[-1])
    _push_from_comp_tens(compression[-2], tension[-2])

    if not raw:
        g = compute_stm_cantilever_d_region_nodes(model, theta_v_deg=theta_v_deg)
        if g is not None:
            bot_out = (float(g["x_bot_out"]), float(g["bottom_tie_y"]))
            top_in = (float(g["x_top_in"]), float(g.get("y_top_in", g["top_y"])))
            hit = polyline_segment_best_hit(compression[-1], bot_out, top_in, x_lo, x_hi)
            if hit is not None:
                px, py, tx, ty = hit
                nrm = math.hypot(tx, ty)
                if nrm > 1e-12:
                    tx, ty = tx / nrm, ty / nrm
                    sx = top_in[0] - bot_out[0]
                    sy = top_in[1] - bot_out[1]
                    sn = math.hypot(sx, sy)
                    if sn > 1e-12:
                        sx, sy = sx / sn, sy / sn
                        tens_ang = math.atan2(sy, sx)
                        crack_ang = tens_ang + 0.5 * math.pi + math.radians(20.0)
                        raw.append(
                            {
                                "x": px,
                                "y": py,
                                "crack_angle_rad": crack_ang,
                                "principal_deg": math.degrees(math.atan2(ty, tx)),
                            }
                        )

    raw.sort(key=lambda h: -h["x"])
    deduped: list[dict[str, float]] = []
    min_dx = max(0.04 * span_m, 1e-6)
    for h in raw:
        if not deduped or (deduped[-1]["x"] - h["x"]) > min_dx:
            deduped.append(h)
    return [
        cantilever_refine_crack_hit_for_compression_field(h, compression, span_m, x_lo=x_lo, x_hi=x_hi)
        for h in deduped[:2]
    ]


def principal_stress_marker_state(
    tension: list[list[tuple[float, float]]],
    compression: list[list[tuple[float, float]]],
    geometry: dict[str, float] | None = None,
) -> tuple[tuple[float, float], float] | None:
    if len(compression) < 3:
        return None

    outer_comp = compression[-1]
    inner_comp = compression[-2]
    curve_fraction = 0.08
    if geometry is not None and "L_plot" in geometry and "d_plot" in geometry:
        left_d_end = min(max(geometry.get("left_deep_limit", geometry["d_plot"]), 0.0), geometry["L_plot"] * 0.42)
        shortness = geometry.get("shortness", 0.0)
        longness = geometry.get("longness", 0.0)
        marker_offset = (0.20 + 0.08 * longness - 0.06 * shortness) * geometry["d_plot"]
        target_x = min(
            left_d_end + marker_offset,
            geometry["centre_x"] - 0.18 * geometry["d_plot"],
        )
        cx_lo = geometry.get("crack_x_lo")
        cx_hi = geometry.get("crack_x_hi")
        if cx_lo is not None and cx_hi is not None:
            mid_cap = geometry["centre_x"] - 0.18 * geometry["d_plot"]
            upper = min(mid_cap, cx_hi) if geometry.get("crack_marker_cap_at_centre", True) else cx_hi
            target_x = min(max(target_x, cx_lo), upper)
        span_dx = max(outer_comp[-1][0] - outer_comp[0][0], 1e-9)
        curve_fraction = min(max((target_x - outer_comp[0][0]) / span_dx, 0.06), 0.40)
    outer_sample = sample_curve_point_and_tangent(outer_comp, curve_fraction)
    inner_sample = sample_curve_point_and_tangent(inner_comp, curve_fraction)
    if outer_sample is None or inner_sample is None:
        return None

    (outer_px, outer_py), (outer_tx, outer_ty) = outer_sample
    (inner_px, inner_py), (inner_tx, inner_ty) = inner_sample
    local_centre = (0.5 * (outer_px + inner_px), 0.5 * (outer_py + inner_py))

    support_side_fraction = max(curve_fraction - 0.06, 0.03)
    outer_dir_sample = sample_curve_point_and_tangent(outer_comp, support_side_fraction)
    inner_dir_sample = sample_curve_point_and_tangent(inner_comp, support_side_fraction)
    if outer_dir_sample is not None and inner_dir_sample is not None:
        (_, _), (outer_tx, outer_ty) = outer_dir_sample
        (_, _), (inner_tx, inner_ty) = inner_dir_sample

    comp_dx = 0.5 * (outer_tx + inner_tx)
    comp_dy = 0.5 * (outer_ty + inner_ty)
    comp_norm = max(math.hypot(comp_dx, comp_dy), 1e-9)
    comp_dx /= comp_norm
    comp_dy /= comp_norm
    if geometry is not None and "beam_bottom" in geometry:
        local_centre = (local_centre[0], geometry["beam_bottom"] + 0.10 * geometry["D_plot"])

    if comp_dx < 0.0:
        comp_dx *= -1.0
        comp_dy *= -1.0
    local_angle = math.degrees(math.atan2(comp_dy, comp_dx))
    return (local_centre, local_angle)


def add_principal_shear_crack_example(
    fig: go.Figure,
    tension: list[list[tuple[float, float]]],
    compression: list[list[tuple[float, float]]],
    geometry: dict[str, float],
    marker_centre: tuple[float, float] | None = None,
    marker_angle_deg: float | None = None,
    *,
    cantilever_mode: bool = False,
) -> None:
    if len(compression) < 3:
        return

    outer_comp = compression[-1]
    inner_comp = compression[-2]
    crack_len = 0.28 * geometry["D_plot"]
    zig_amp = 0.012 * geometry["D_plot"]
    arrow_gap = 0.040 * geometry["D_plot"]
    arrow_len = 0.085 * geometry["D_plot"]
    arrow_spread = 0.030 * geometry["D_plot"]
    arrow_color = "rgba(0,90,200,0.58)"
    crack_defs: list[dict[str, Any]] = []

    if "L_plot" in geometry and "d_plot" in geometry:
        left_d_end = min(max(geometry.get("left_deep_limit", geometry["d_plot"]), 0.0), geometry["L_plot"] * 0.42)
        shortness = geometry.get("shortness", 0.0)
        longness = geometry.get("longness", 0.0)
        crack_offset = (0.48 + 0.24 * longness - 0.20 * shortness) * geometry["d_plot"]
        left_target_x = min(left_d_end + crack_offset, 0.5 * geometry["L_plot"] - 0.16 * geometry["d_plot"])
        cx_lo = geometry.get("crack_x_lo")
        cx_hi = geometry.get("crack_x_hi")
        if cx_lo is not None and cx_hi is not None:
            half_cap = 0.5 * geometry["L_plot"] - 0.16 * geometry["d_plot"]
            upper = min(half_cap, cx_hi) if geometry.get("crack_marker_cap_at_centre", True) else cx_hi
            left_target_x = min(max(left_target_x, cx_lo), upper)
    else:
        left_target_x = 0.18 * (outer_comp[0][0] + outer_comp[-1][0])

    span_dx = max(outer_comp[-1][0] - outer_comp[0][0], 1e-9)
    beam_mid_x = 0.5 * geometry.get("L_plot", outer_comp[0][0] + outer_comp[-1][0])

    def _resolved_crack_angle(target_x: float, *, rotate_extra_deg: float = 0.0) -> float | None:
        curve_fraction = min(max((target_x - outer_comp[0][0]) / span_dx, 0.06), 0.94)
        outer_sample = sample_curve_point_and_tangent(outer_comp, curve_fraction)
        inner_sample = sample_curve_point_and_tangent(inner_comp, curve_fraction)
        if outer_sample is None or inner_sample is None:
            return None

        (outer_px, _), (outer_tx, outer_ty) = outer_sample
        (inner_px, _), (inner_tx, inner_ty) = inner_sample
        px = 0.5 * (outer_px + inner_px)

        is_left_side = px <= beam_mid_x
        support_side_fraction = max(curve_fraction - 0.06, 0.03) if is_left_side else min(curve_fraction + 0.06, 0.97)
        outer_dir_sample = sample_curve_point_and_tangent(outer_comp, support_side_fraction)
        inner_dir_sample = sample_curve_point_and_tangent(inner_comp, support_side_fraction)
        if outer_dir_sample is not None and inner_dir_sample is not None:
            (_, _), (outer_tx, outer_ty) = outer_dir_sample
            (_, _), (inner_tx, inner_ty) = inner_dir_sample

        crack_dx = 0.5 * (outer_tx + inner_tx)
        crack_dy = 0.5 * (outer_ty + inner_ty)
        crack_norm = max(math.hypot(crack_dx, crack_dy), 1e-9)
        crack_dir = (crack_dx / crack_norm, crack_dy / crack_norm)
        if rotate_extra_deg:
            crack_angle = math.atan2(crack_dir[1], crack_dir[0]) + math.radians(rotate_extra_deg)
            crack_dir = (math.cos(crack_angle), math.sin(crack_angle))
        return math.atan2(crack_dir[1], crack_dir[0])

    def _add_one_crack(
        target_x: float,
        crack_angle_rad: float,
        *,
        centre_override: tuple[float, float] | None = None,
    ) -> None:
        if centre_override is not None:
            px, py = centre_override[0], centre_override[1]
        else:
            curve_fraction = min(max((target_x - outer_comp[0][0]) / span_dx, 0.06), 0.94)
            outer_sample = sample_curve_point_and_tangent(outer_comp, curve_fraction)
            inner_sample = sample_curve_point_and_tangent(inner_comp, curve_fraction)
            if outer_sample is None or inner_sample is None:
                return

            (outer_px, outer_py), _ = outer_sample
            (inner_px, inner_py), _ = inner_sample
            px = 0.5 * (outer_px + inner_px)
            py = 0.5 * (outer_py + inner_py)
        crack_dir = (math.cos(crack_angle_rad), math.sin(crack_angle_rad))
        tension_dir = (-crack_dir[1], crack_dir[0])
        if tension_dir[1] < 0.0:
            tension_dir = (-tension_dir[0], -tension_dir[1])

        if centre_override is None and "beam_bottom" in geometry:
            py = geometry["beam_bottom"] + 0.10 * geometry["D_plot"]

        zig_dir = (-crack_dir[1], crack_dir[0])
        crack_pts: list[tuple[float, float]] = []
        for idx, s in enumerate((-0.50, -0.28, -0.06, 0.14, 0.34, 0.50)):
            base_x = px + s * crack_len * crack_dir[0]
            base_y = py + s * crack_len * crack_dir[1]
            offset_sign = -1.0 if idx % 2 == 0 else 1.0
            crack_pts.append(
                (
                    base_x + offset_sign * zig_amp * zig_dir[0],
                    base_y + offset_sign * zig_amp * zig_dir[1],
                )
            )
        crack_defs.append(
            {
                "points": crack_pts,
                "width": 2.2,
                "opacity": 0.78,
                "smoothing": 0.0,
            }
        )

        for direction in (-1.0, 1.0):
            for offset_sign in (-1.0, 1.0):
                base_x = px + offset_sign * arrow_spread * crack_dir[0]
                base_y = py + offset_sign * arrow_spread * crack_dir[1]
                start_x = base_x + direction * arrow_gap * tension_dir[0]
                start_y = base_y + direction * arrow_gap * tension_dir[1]
                end_x = base_x + direction * (arrow_gap + arrow_len) * tension_dir[0]
                end_y = base_y + direction * (arrow_gap + arrow_len) * tension_dir[1]
                fig.add_annotation(
                    x=end_x,
                    y=end_y,
                    ax=start_x,
                    ay=start_y,
                    xref="x",
                    yref="y",
                    axref="x",
                    ayref="y",
                    text="",
                    showarrow=True,
                    arrowhead=2,
                    arrowsize=0.7,
                    arrowwidth=1.1,
                    arrowcolor=arrow_color,
                    opacity=0.70,
                    standoff=0,
                )

    if cantilever_mode:
        hits = geometry.get("cantilever_crack_hits") or []
        for h in hits:
            _add_one_crack(
                float(h["x"]),
                float(h["crack_angle_rad"]),
                centre_override=(float(h["x"]), float(h["y"])),
            )
        if crack_defs:
            build_crack_cues(fig, crack_defs)
        return

    left_outer_angle = _resolved_crack_angle(left_target_x, rotate_extra_deg=20.0)
    if left_outer_angle is not None:
        _add_one_crack(left_target_x, left_outer_angle)
        if "L_plot" in geometry:
            _add_one_crack(geometry["L_plot"] - left_target_x, math.pi - left_outer_angle)

    if marker_centre is not None and "L_plot" in geometry:
        marker_x = min(max(marker_centre[0], outer_comp[0][0]), outer_comp[-1][0])
        if "crack_x_lo" in geometry and "crack_x_hi" in geometry:
            marker_x = min(max(marker_x, geometry["crack_x_lo"]), geometry["crack_x_hi"])
        marker_angle_rad = math.radians(marker_angle_deg + 20.0) if marker_angle_deg is not None else _resolved_crack_angle(marker_x)
        if marker_angle_rad is not None:
            _add_one_crack(marker_x, marker_angle_rad, centre_override=marker_centre)
            _add_one_crack(
                geometry["L_plot"] - marker_x,
                math.pi - marker_angle_rad,
                centre_override=(geometry["L_plot"] - marker_centre[0], marker_centre[1]),
            )

    if crack_defs:
        build_crack_cues(fig, crack_defs)


def render_principal_stress_ss_udl(
    fig: go.Figure,
    model: dict[str, Any],
    *,
    theta_v_deg: float,
) -> None:
    span_m = model["span_m"]
    geometry = compute_stress_field_geometry(model)
    beam_depth_m = geometry["D_plot"]
    count = compute_trajectory_count(geometry["slenderness"])

    red = "rgba(200,45,45,0.82)"
    blue = "rgba(0,90,200,0.68)"
    show_load_flow = bool(model.get("show_load_flow", False))
    show_cracks = bool(model.get("show_cracks", True))
    show_stress_block = bool(model.get("show_stress_block", True))
    field_opacity_scale = 0.64 if bool(model.get("show_stm_overlay", False) or model.get("show_stm_flow", False)) else 1.0

    tension = build_tensile_trajectories(geometry, count)
    compression = build_compressive_trajectories(geometry, count)

    add_ordered_trajectory_family(
        fig,
        tension,
        blue,
        width=2.6,
        opacity=(0.46 if show_load_flow else 0.82) * field_opacity_scale,
        smoothing=0.64,
        beam_depth_m=beam_depth_m,
    )
    add_ordered_trajectory_family(
        fig,
        compression,
        red,
        width=2.4,
        opacity=(0.36 if show_load_flow else 0.68) * field_opacity_scale,
        smoothing=0.64,
        beam_depth_m=beam_depth_m,
    )
    if show_load_flow:
        compression_key_indices = [max(len(compression) - 3, 0), max(len(compression) - 2, 0), len(compression) - 1]
        tension_key_indices = [max(len(tension) // 2, 0), max(len(tension) - 2, 0)]
        add_load_flow_overlay(
            fig,
            compression,
            red,
            beam_depth_m=beam_depth_m,
            line_indices=compression_key_indices,
            outward_from_centre=True,
            animate_motion=True,
        )
        add_load_flow_overlay(
            fig,
            tension,
            blue,
            beam_depth_m=beam_depth_m,
            line_indices=tension_key_indices,
            outward_from_centre=True,
            animate_motion=True,
        )

    marker_state = principal_stress_marker_state(tension, compression, geometry)
    if show_stress_block:
        add_principal_stress_orientation_square(
            fig,
            geometry,
            principal_angle_deg=marker_state[1] if marker_state is not None else theta_v_deg,
            centre=marker_state[0] if marker_state is not None else None,
        )
    if show_cracks:
        add_principal_shear_crack_example(
            fig,
            tension,
            compression,
            geometry,
            marker_centre=marker_state[0] if marker_state is not None else None,
            marker_angle_deg=marker_state[1] if marker_state is not None else theta_v_deg,
        )

    fig.add_annotation(
        x=0.18 * span_m,
        y=0.90 * beam_depth_m,
        text="Tensile trajectories",
        showarrow=False,
        font=dict(size=11, color="rgba(0,90,200,0.98)"),
    )
    fig.add_annotation(
        x=0.50 * span_m,
        y=0.56 * beam_depth_m,
        text="Compressive trajectories",
        showarrow=False,
        font=dict(size=11, color="rgba(200,45,45,0.98)"),
    )


def render_principal_stress_ss_midspan_point(
    fig: go.Figure,
    model: dict[str, Any],
    *,
    theta_v_deg: float,
) -> None:
    render_principal_stress_ss_udl(fig, model, theta_v_deg=theta_v_deg)


def render_principal_stress_ss_eccentric_point(
    fig: go.Figure,
    model: dict[str, Any],
    *,
    theta_v_deg: float,
) -> None:
    render_principal_stress_ss_udl(fig, model, theta_v_deg=theta_v_deg)


def render_principal_stress_ss_near_support_point(
    fig: go.Figure,
    model: dict[str, Any],
    *,
    theta_v_deg: float,
) -> None:
    render_principal_stress_ss_udl(fig, model, theta_v_deg=theta_v_deg)


def render_principal_stress_cantilever_tip(
    fig: go.Figure,
    model: dict[str, Any],
    *,
    theta_v_deg: float,
) -> None:
    span_m = model["span_m"]
    depth_scale = beam_depth_scale(model)
    d_plot = max(_safe_float(model.get("d_m", depth_scale * 0.9), depth_scale * 0.9), 1e-6)
    slenderness = span_m / max(d_plot, 1e-6)

    red = "rgba(200,45,45,0.70)"
    blue = "rgba(0,90,200,0.58)"
    show_load_flow = bool(model.get("show_load_flow", False))
    show_cracks = bool(model.get("show_cracks", True))
    show_stress_block = bool(model.get("show_stress_block", True))
    field_opacity_scale = 0.64 if bool(model.get("show_stm_overlay", False) or model.get("show_stm_flow", False)) else 1.0

    x_deep, x_transition = cantilever_behaviour_zones(model)
    ratio_to_baseline = min(max(slenderness / (2000.0 / 350.0), 0.55), 1.80)
    shortness = min(max(((2000.0 / 350.0) - slenderness) / (2000.0 / 350.0), 0.0), 1.0)
    longness = min(max((slenderness - (2000.0 / 350.0)) / (2000.0 / 350.0), 0.0), 1.0)

    # Stronger support-side disturbed field for short cantilevers, softer for long.
    support_pull = min(max((1.0 / ratio_to_baseline) ** 0.45, 0.78), 1.42)
    support_band = min(max(x_deep * (1.05 + 0.18 * shortness), 0.10 * span_m), 0.42 * span_m)
    transition_span = max(x_transition - support_band, 0.10 * span_m)

    top_pad = support_edge_y_top(depth_scale)
    bot_pad = support_edge_y_bot(depth_scale)

    def _cantilever_arc(
        x0: float,
        y0: float,
        x1: float,
        y1: float,
        *,
        support_bias: float,
        free_bias: float,
        bow_down: bool,
    ) -> list[tuple[float, float]]:
        """Smooth arc (x0,y0)->(x1,y1). Endpoints exact; x advances with t so ends stay separated along edges."""
        pts: list[tuple[float, float]] = []
        arch = (0.24 + 0.11 * support_bias + 0.09 * free_bias) * depth_scale * support_pull
        arch *= 1.0 - 0.10 * longness
        dx = max(x1 - x0, 1e-9)
        for i in range(41):
            t = i / 40.0
            x = x0 + dx * (t ** 0.92)
            base = y0 + (y1 - y0) * (t ** 0.78)
            bend = arch * (1.0 - t) ** 1.12 * (t ** 0.78)
            y = base - bend if bow_down else base + bend
            pts.append((x, y))
        pts[0] = (x0, y0)
        pts[-1] = (x1, y1)
        return pts

    def _cantilever_compression_horizontal_then_parabola(
        x0: float,
        y0: float,
        x1: float,
        y1: float,
        *,
        alpha_flat: float,
    ) -> list[tuple[float, float]]:
        """
        Compression: horizontal chord near the fixed support, then a smooth sag to the bottom.
        Uses y = y0 + (y1 - y0) * u^p with p > 2 so the drop is gentler mid-span and steeper toward the free end,
        while dy/du|_{u=0} = 0 keeps a smooth horizontal tangent at the start of the dip (cantilever only).
        """
        y_min, y_max = field_y_limits(depth_scale)
        dx = max(x1 - x0, 1e-9)
        alpha = min(max(alpha_flat, 0.06), 0.28)
        x_flat = x0 + alpha * dx
        parab_power = 2.95
        pts: list[tuple[float, float]] = []
        if x_flat > x0 + 1e-9:
            pts.append((x0, min(max(y0, y_min), y_max)))
            pts.append((x_flat, min(max(y0, y_min), y_max)))
        else:
            pts.append((x0, min(max(y0, y_min), y_max)))
        n_parab = 44
        for i in range(1, n_parab + 1):
            u = i / n_parab
            x = x_flat + u * (x1 - x_flat)
            y = y0 + (y1 - y0) * (u ** parab_power)
            pts.append((x, min(max(y, y_min), y_max)))
        pts[0] = (x0, min(max(y0, y_min), y_max))
        pts[-1] = (x1, min(max(y1, y_min), y_max))
        return pts

    # Lane spacing at support (vertical) and along the destination edge (horizontal) so lines never bunch in one corner.
    lane_gap = 0.088 * depth_scale
    x_edge_gap = max(0.064 * span_m, 1.38 * lane_gap)
    # Nudge compression starts slightly down from the top band; tension is mirrored about mid-depth (y' = D - y).
    comp_start_nudge = 0.032 * depth_scale

    comp_y_starts = [
        max(top_pad - comp_start_nudge, bot_pad + 0.16 * depth_scale),
        max(top_pad - lane_gap - comp_start_nudge, bot_pad + 0.13 * depth_scale),
        max(top_pad - 2.0 * lane_gap - comp_start_nudge, bot_pad + 0.10 * depth_scale),
        max(top_pad - 3.0 * lane_gap - comp_start_nudge, bot_pad + 0.085 * depth_scale),
    ]
    # Compression: idx 0 = highest at support -> longest reach along bottom (near tip); idx 3 = shortest reach.
    comp_x_ends = [max(span_m - idx * x_edge_gap, span_m * 0.58) for idx in range(4)]

    compression = [
        _cantilever_compression_horizontal_then_parabola(
            0.0,
            comp_y_starts[idx],
            comp_x_ends[idx],
            bot_pad,
            alpha_flat=0.11 + 0.022 * (idx / 3.0),
        )
        for idx in range(4)
    ]

    # Exact mirror of compression about beam mid-depth: horizontal start low, parabolic rise to top (same x layout).
    tension = [[(xv, depth_scale - yv) for xv, yv in curve] for curve in compression]

    add_ordered_trajectory_family(
        fig,
        compression,
        red,
        width=2.5,
        opacity=(0.40 if show_load_flow else 0.70) * field_opacity_scale,
        smoothing=0.0,
        beam_depth_m=depth_scale,
        line_shape="linear",
    )
    add_ordered_trajectory_family(
        fig,
        tension,
        blue,
        width=2.3,
        opacity=(0.42 if show_load_flow else 0.60) * field_opacity_scale,
        smoothing=0.0,
        beam_depth_m=depth_scale,
        line_shape="linear",
    )
    if show_load_flow:
        add_load_flow_overlay(
            fig,
            compression,
            red,
            beam_depth_m=depth_scale,
            line_indices=[max(len(compression) - 2, 0), len(compression) - 1],
            outward_from_centre=True,
            animate_motion=True,
        )
        add_load_flow_overlay(
            fig,
            tension,
            blue,
            beam_depth_m=depth_scale,
            line_indices=[max(len(tension) - 2, 0)],
            outward_from_centre=True,
            animate_motion=True,
        )

    crack_x_lo, crack_x_hi = shear_crack_x_band_m(model)
    geometry = {
        "beam_left": 0.0,
        "beam_right": span_m,
        "beam_bottom": 0.0,
        "beam_top": depth_scale,
        "L_plot": span_m,
        "D_plot": depth_scale,
        "d_plot": d_plot,
        "slenderness": slenderness,
        "left_deep_limit": x_deep,
        "right_deep_limit": span_m,
        "flexural_width": max(span_m - x_transition, 0.0),
        "centre_x": 0.5 * span_m,
        "crack_x_lo": crack_x_lo,
        "crack_x_hi": crack_x_hi,
        "crack_marker_cap_at_centre": False,
    }
    cantilever_hits = cantilever_principal_crack_hits(
        compression,
        tension,
        span_m,
        model,
        theta_v_deg=theta_v_deg,
    )
    geometry["cantilever_crack_hits"] = cantilever_hits

    marker_state = principal_stress_marker_state(tension, compression, geometry)
    if show_stress_block:
        if cantilever_hits:
            h_block = cantilever_hits[1] if len(cantilever_hits) > 1 else cantilever_hits[0]
            sq_centre = (float(h_block["x"]), float(h_block["y"]))
            sq_angle = float(h_block["principal_deg"])
        else:
            sq_centre = marker_state[0] if marker_state is not None else None
            sq_angle = marker_state[1] if marker_state is not None else theta_v_deg
        add_principal_stress_orientation_square(
            fig,
            geometry,
            principal_angle_deg=sq_angle,
            centre=sq_centre,
        )
    if show_cracks:
        add_principal_shear_crack_example(
            fig,
            tension,
            compression,
            geometry,
            cantilever_mode=True,
        )

    fig.add_annotation(
        x=0.20 * span_m,
        y=sample_beam_y(0.24, depth_scale),
        text="Compressive trajectories",
        showarrow=False,
        font=dict(size=11, color="rgba(200,45,45,0.95)"),
    )
    fig.add_annotation(
        x=0.24 * span_m,
        y=sample_beam_y(-0.02, depth_scale),
        text="Tensile trajectories",
        showarrow=False,
        font=dict(size=11, color="rgba(0,90,200,0.95)"),
    )


def render_principal_stress_cantilever_udl(
    fig: go.Figure,
    model: dict[str, Any],
    *,
    theta_v_deg: float,
) -> None:
    render_principal_stress_cantilever_tip(fig, model, theta_v_deg=theta_v_deg)


def render_principal_stress_cantilever_eccentric(
    fig: go.Figure,
    model: dict[str, Any],
    *,
    theta_v_deg: float,
) -> None:
    render_principal_stress_cantilever_tip(fig, model, theta_v_deg=theta_v_deg)


def add_shear_behaviour_udl(
    fig: go.Figure,
    x0: float,
    x1: float,
    *,
    beam_depth_m: float,
    y_top: float,
    label: str | None = None,
) -> None:
    if x1 <= x0:
        return
    fig.add_trace(
        go.Scatter(
            x=[x0, x1, x1, x0],
            y=[beam_depth_m, beam_depth_m, y_top, y_top],
            mode="lines",
            fill="toself",
            line=dict(width=0, color="rgba(31,119,180,0.0)"),
            fillcolor="rgba(31,119,180,0.10)",
            hoverinfo="skip",
            showlegend=False,
        )
    )
    arrow_count = max(4, min(9, int((x1 - x0) / max((x1 - x0) / 6.0, 0.25))))
    for idx in range(arrow_count):
        x_val = x0 + (idx + 0.5) * (x1 - x0) / arrow_count
        fig.add_annotation(
            x=x_val,
            y=beam_depth_m,
            ax=x_val,
            ay=y_top,
            xref="x",
            yref="y",
            axref="x",
            ayref="y",
            showarrow=True,
            arrowhead=2,
            arrowsize=1.0,
            arrowwidth=1.3,
            arrowcolor="rgba(35,35,35,0.95)",
            text="",
        )
    if label:
        fig.add_annotation(
            x=(x0 + x1) / 2.0,
            y=y_top + 0.18 * beam_depth_m,
            text=label,
            showarrow=False,
            font=dict(size=11, color="rgba(60,60,60,0.9)"),
        )


def add_shear_behaviour_point_load(
    fig: go.Figure,
    x_pos: float,
    *,
    beam_depth_m: float,
    y_top: float,
    label: str | None = None,
) -> None:
    fig.add_annotation(
        x=x_pos,
        y=beam_depth_m,
        ax=x_pos,
        ay=y_top,
        xref="x",
        yref="y",
        axref="x",
        ayref="y",
        showarrow=True,
        arrowhead=2,
        arrowsize=1.1,
        arrowwidth=1.7,
        arrowcolor="rgba(35,35,35,0.95)",
        text="",
    )
    if label:
        fig.add_annotation(
            x=x_pos,
            y=y_top + 0.18 * beam_depth_m,
            text=label,
            showarrow=False,
            font=dict(size=11, color="rgba(60,60,60,0.9)"),
        )


def build_shear_behaviour_load_shapes(
    fig: go.Figure,
    model: dict[str, Any],
    *,
    show_labels: bool,
) -> None:
    case = model["case"]
    span_m = model["span_m"]
    total_m = model["total_length_m"]
    beam_depth_m = model["D_m"]
    y_top = 1.42 * beam_depth_m
    point_y_top = 1.75 * beam_depth_m
    label_w = f"{'w*' if model['mode'] == 'ULS' else 'w'} = {model['w_value']:.1f} kN/m" if show_labels else None
    label_p = f"{'P*' if model['mode'] == 'ULS' else 'P'} = {model['point_value']:.1f} kN" if show_labels else None

    if case == "Simple beam – UDL over entire span":
        add_shear_behaviour_udl(fig, 0.0, span_m, beam_depth_m=beam_depth_m, y_top=y_top, label=label_w)
    elif case == "Cantilever – UDL over entire span":
        add_shear_behaviour_udl(fig, 0.0, span_m, beam_depth_m=beam_depth_m, y_top=y_top, label=label_w)
    elif case == "Simple beam – partial UDL from left (length a)":
        add_shear_behaviour_udl(fig, 0.0, max(0.0, min(model["a_udl_m"], span_m)), beam_depth_m=beam_depth_m, y_top=y_top, label=label_w)
    elif case == "Simple beam – point load at centre":
        add_shear_behaviour_point_load(fig, span_m / 2.0, beam_depth_m=beam_depth_m, y_top=point_y_top, label=label_p)
    elif case == "Simple beam – point load at distance a from left":
        add_shear_behaviour_point_load(fig, max(0.0, min(model["a_m"], span_m)), beam_depth_m=beam_depth_m, y_top=point_y_top, label=label_p)
    elif case == "Cantilever – point load at free end":
        add_shear_behaviour_point_load(fig, span_m, beam_depth_m=beam_depth_m, y_top=point_y_top, label=label_p)
    elif case == "Cantilever – point load at distance a from fixed end":
        add_shear_behaviour_point_load(fig, max(0.0, min(model["a_cant_m"], span_m)), beam_depth_m=beam_depth_m, y_top=point_y_top, label=label_p)
    elif case.startswith("Overhanging beam"):
        add_shear_behaviour_point_load(fig, total_m, beam_depth_m=beam_depth_m, y_top=point_y_top, label=label_p)
