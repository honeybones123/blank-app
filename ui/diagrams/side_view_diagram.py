"""Shared side-view diagram primitives for Beam App figures."""

from __future__ import annotations

import math
import os
from typing import Any

import plotly.graph_objects as go
import streamlit as st

from state_runtime_gateway import get_param
from widgets_helpers import main_longitudinal_reo_pair_labels

from .diagram_styles import (
    ANNOTATION_TEXT,
    DIAGRAM_BG,
    DIAGRAM_SIZE_LONGITUDINAL,
    DIAGRAM_TRANSPARENT,
    LINK_STEEL,
    MARKER_OUTLINE,
    REO_BOTTOM,
    REO_INACTIVE,
    REO_TOP,
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

SIDE_VIEW_VISUAL_WIDTH = DIAGRAM_SIZE_LONGITUDINAL["width"]
SIDE_VIEW_VISUAL_HEIGHT = DIAGRAM_SIZE_LONGITUDINAL["height"]
SIDE_VIEW_VISUAL_MARGIN = {"l": 10, "r": 10, "t": 10, "b": 10}
_BEAM_VIEWS_LEFT_RATIO = 0.38
_BEAM_VIEWS_RIGHT_RATIO = 0.62
_SIDE_VIEW_BREAK_SLENDERNESS = 10.0
_SIDE_VIEW_SECTION_MARKER = "rgba(46,125,50,0.9)"
_SIDE_VIEW_LOAD_FILL = "rgba(31,119,180,0.10)"
SHEAR_ZONE_SIDE_VIEW_FILLS = (
    "rgba(229,57,53,0.055)",
    "rgba(251,140,0,0.050)",
    "rgba(30,136,229,0.045)",
    "rgba(67,160,71,0.045)",
)


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
        if number != number:
            return float(default)
        return number
    except Exception:
        return float(default)


def side_view_y_bounds(
    beam_depth_m: float, support_condition: str
) -> tuple[float, float]:
    """Tight y-range around drawn side-view content."""
    depth = max(beam_depth_m, 0.05)
    support_d = max(SUPPORT_PIN_DEPTH_BEAM_RATIO * depth, SUPPORT_PIN_MIN_DEPTH_MM / 1000.0)
    ground_drop = max(SUPPORT_GROUND_DROP_BEAM_RATIO * depth, SUPPORT_GROUND_MIN_DROP_MM / 1000.0)
    ground_y = -support_d - ground_drop
    stirrup_label_y = -0.26 * depth
    pad = max(0.08 * depth, 0.025)

    if support_condition == "cantilever":
        min_content = min(-SUPPORT_FIXED_OVERHANG_BEAM_RATIO * depth, stirrup_label_y)
        max_content = max(depth, depth + SUPPORT_FIXED_OVERHANG_BEAM_RATIO * depth)
    else:
        roller_r = max(SUPPORT_ROLLER_RADIUS_BEAM_RATIO * depth, SUPPORT_ROLLER_MIN_RADIUS_MM / 1000.0)
        roller_drop = max(0.0, (0.45 * support_d + roller_r) - ground_drop) if support_condition == "simply_supported" else 0.0
        min_content = min(ground_y - roller_drop, stirrup_label_y)
        max_content = depth

    return min_content - pad, max_content + pad


def _side_view_axis_length(length_m: float, display_length_m: float | None = None) -> float:
    length = max(_safe_float(length_m, 0.0), 0.1)
    display_length = _safe_float(display_length_m, 0.0) if display_length_m is not None else 0.0
    return max(display_length if display_length > 0.0 else length, 0.1)


def side_view_display_length_from_model(model: dict[str, Any]) -> float:
    state = model.get("side_view_display", {})
    return _side_view_axis_length(
        _safe_float(model.get("total_length_m", 0.0), 0.0),
        _safe_float(state.get("display_length_m", 0.0), 0.0) if isinstance(state, dict) else 0.0,
    )


def side_view_scaled_viewport(
    *,
    length_m: float,
    beam_depth_m: float,
    support_condition: str,
    height: int,
    display_length_m: float | None = None,
    y_min_needed: float | None = None,
    y_max_needed: float | None = None,
) -> tuple[list[float], list[float]]:
    """Return x/y ranges that keep the side-view scale consistent."""
    axis_length = _side_view_axis_length(length_m, display_length_m)
    pad = max(axis_length * 0.06, 0.2)
    x_range = [-pad, axis_length + pad]

    base_y_min, base_y_max = side_view_y_bounds(beam_depth_m, support_condition)
    y_min = min(base_y_min, _safe_float(y_min_needed, base_y_min))
    y_max = max(base_y_max, _safe_float(y_max_needed, base_y_max))

    plot_w = max(
        float(
            SIDE_VIEW_VISUAL_WIDTH
            - int(SIDE_VIEW_VISUAL_MARGIN.get("l", 0))
            - int(SIDE_VIEW_VISUAL_MARGIN.get("r", 0))
        ),
        1.0,
    )
    plot_h = max(
        float(
            int(height)
            - int(SIDE_VIEW_VISUAL_MARGIN.get("t", 0))
            - int(SIDE_VIEW_VISUAL_MARGIN.get("b", 0))
        ),
        1.0,
    )
    x_span = x_range[1] - x_range[0]
    y_span_to_scale = x_span * plot_h / plot_w
    needed_span = y_max - y_min
    y_span = max(y_span_to_scale, needed_span)
    y_mid = 0.5 * (y_min + y_max)
    return x_range, [y_mid - 0.5 * y_span, y_mid + 0.5 * y_span]


def fit_side_view_figure_to_content(
    fig: go.Figure,
    *,
    length_m: float,
    beam_depth_m: float,
    support_condition: str,
    height: int,
    display_length_m: float | None = None,
    y_min_needed: float | None = None,
    y_max_needed: float | None = None,
) -> None:
    x_range, y_range = side_view_scaled_viewport(
        length_m=length_m,
        beam_depth_m=beam_depth_m,
        support_condition=support_condition,
        height=height,
        display_length_m=display_length_m,
        y_min_needed=y_min_needed,
        y_max_needed=y_max_needed,
    )
    fig.update_xaxes(range=x_range)
    fig.update_yaxes(range=y_range)


def build_side_view_figure(
    length_m: float,
    beam_depth_m: float,
    height: int,
    support_condition: str,
    *,
    display_length_m: float | None = None,
) -> go.Figure:
    fig = go.Figure()
    x_range, y_range = side_view_scaled_viewport(
        length_m=length_m,
        beam_depth_m=beam_depth_m,
        support_condition=support_condition,
        height=height,
        display_length_m=display_length_m,
    )
    fig.update_layout(
        height=height,
        width=SIDE_VIEW_VISUAL_WIDTH,
        autosize=False,
        margin=dict(SIDE_VIEW_VISUAL_MARGIN),
        paper_bgcolor=DIAGRAM_BG,
        plot_bgcolor=DIAGRAM_BG,
        showlegend=False,
    )
    fig.update_xaxes(
        visible=False,
        range=x_range,
        fixedrange=True,
        showgrid=False,
        zeroline=False,
    )
    fig.update_yaxes(
        visible=False,
        range=y_range,
        fixedrange=True,
        showgrid=False,
        zeroline=False,
        scaleanchor="x",
        scaleratio=1,
    )
    return fig


def _cross_section_frame_size(width_mm: float, depth_mm: float) -> float:
    return max(width_mm, depth_mm) * 1.32


def _target_side_display_length(model: dict[str, Any]) -> float:
    beam_depth_m = max(_safe_float(model.get("D_m", 0.0), 0.0), 0.1)
    dims = ((model.get("section_layout") or {}).get("dims") or {})
    width_mm = _safe_float(
        dims.get("bf", dims.get("b", beam_depth_m * 1000.0)),
        beam_depth_m * 1000.0,
    )
    cross_frame_m = _cross_section_frame_size(width_mm, beam_depth_m * 1000.0) / 1000.0
    x_range_target = cross_frame_m * (_BEAM_VIEWS_RIGHT_RATIO / _BEAM_VIEWS_LEFT_RATIO)
    return max(x_range_target - 0.4, max(0.85 * beam_depth_m, 0.18))


def side_view_display_state(model: dict[str, Any]) -> dict[str, float | bool]:
    total_length_m = max(_safe_float(model.get("total_length_m", 0.0), 0.0), 0.1)
    beam_depth_m = max(_safe_float(model.get("D_m", 0.0), 0.0), 0.1)
    slenderness = total_length_m / beam_depth_m if beam_depth_m > 0.0 else 0.0
    if slenderness < _SIDE_VIEW_BREAK_SLENDERNESS:
        return {
            "use_break": False,
            "display_length_m": total_length_m,
            "left_keep_m": total_length_m,
            "right_start_m": total_length_m,
            "collapsed_mid_m": 0.0,
            "break_left_display_m": total_length_m * 0.5,
            "break_right_display_m": total_length_m * 0.5,
        }

    left_keep_m = min(max(0.50 * beam_depth_m, 0.025 * total_length_m, 0.12), 0.07 * total_length_m)
    right_start_m = total_length_m - left_keep_m
    hidden_mid_m = max(right_start_m - left_keep_m, 0.0)
    min_collapsed_m = max(0.45 * beam_depth_m, 0.09)
    target_display_length_m = _target_side_display_length(model)
    collapsed_mid_m = min(
        max(target_display_length_m - 2.0 * left_keep_m, min_collapsed_m),
        hidden_mid_m * 0.16 if hidden_mid_m > 0.0 else 0.0,
    )

    if hidden_mid_m <= 0.0 or collapsed_mid_m <= 0.0:
        return {
            "use_break": False,
            "display_length_m": total_length_m,
            "left_keep_m": total_length_m,
            "right_start_m": total_length_m,
            "collapsed_mid_m": 0.0,
            "break_left_display_m": total_length_m * 0.5,
            "break_right_display_m": total_length_m * 0.5,
        }

    return {
        "use_break": True,
        "display_length_m": left_keep_m + collapsed_mid_m + left_keep_m,
        "left_keep_m": left_keep_m,
        "right_start_m": right_start_m,
        "collapsed_mid_m": collapsed_mid_m,
        "break_left_display_m": left_keep_m,
        "break_right_display_m": left_keep_m + collapsed_mid_m,
    }


def side_view_display_x(x_real: float, model: dict[str, Any]) -> float:
    state = model.get("side_view_display", {})
    if not state or not state.get("use_break"):
        return x_real

    left_keep_m = _safe_float(state.get("left_keep_m", 0.0), 0.0)
    right_start_m = _safe_float(state.get("right_start_m", 0.0), 0.0)
    collapsed_mid_m = _safe_float(state.get("collapsed_mid_m", 0.0), 0.0)
    total_length_m = max(_safe_float(model.get("total_length_m", 0.0), 0.0), 0.1)
    hidden_mid_m = max(right_start_m - left_keep_m, 0.0)

    x_real = max(0.0, min(x_real, total_length_m))
    if x_real <= left_keep_m or hidden_mid_m <= 0.0:
        return x_real
    if x_real >= right_start_m:
        return left_keep_m + collapsed_mid_m + (x_real - right_start_m)
    return left_keep_m + ((x_real - left_keep_m) / hidden_mid_m) * collapsed_mid_m


def side_view_display_positions(values: list[float], model: dict[str, Any], *, min_spacing: float) -> list[float]:
    transformed = sorted(side_view_display_x(x_val, model) for x_val in values)
    if not transformed:
        return []

    kept = [transformed[0]]
    for x_val in transformed[1:]:
        if x_val - kept[-1] >= min_spacing:
            kept.append(x_val)
    return kept


def build_side_view_tension_reo(fig: go.Figure, model: dict[str, Any]) -> None:
    bottom_layers = model.get("bottom_layers", []) or []
    top_layers = model.get("top_layers", []) or []
    if not bottom_layers and not top_layers:
        return
    beam_depth_m = model["D_m"]
    bottom_base_y = 0.11 * beam_depth_m
    top_base_y = 0.89 * beam_depth_m
    total_length_m = max(_safe_float(model.get("total_length_m", 0.0), 0.0), 1e-9)
    x_start = side_view_display_x(0.0, model)
    x_end = side_view_display_x(total_length_m, model)

    for idx, layer in enumerate(bottom_layers[:2]):
        db = max(_safe_float(layer.get("db", 20.0), 20.0), 10.0)
        y_val = min(bottom_base_y + idx * 0.07 * beam_depth_m, 0.85 * beam_depth_m)
        fig.add_trace(
            go.Scatter(
                x=[x_start, x_end],
                y=[y_val, y_val],
                mode="lines",
                line=dict(color=REO_BOTTOM, width=max(2.0, min(4.5, db / 6.0))),
                hoverinfo="skip",
                showlegend=False,
            )
        )
    for idx, layer in enumerate(top_layers[:2]):
        db = max(_safe_float(layer.get("db", 20.0), 20.0), 10.0)
        y_val = max(top_base_y - idx * 0.07 * beam_depth_m, 0.15 * beam_depth_m)
        fig.add_trace(
            go.Scatter(
                x=[x_start, x_end],
                y=[y_val, y_val],
                mode="lines",
                line=dict(color=REO_TOP, width=max(2.0, min(4.5, db / 6.0))),
                hoverinfo="skip",
                showlegend=False,
            )
        )

    if bottom_layers:
        fig.add_annotation(
            x=side_view_display_x(0.82 * model["total_length_m"], model),
            y=min(bottom_base_y + 0.04 * beam_depth_m, 0.90 * beam_depth_m),
            text="Tension reo",
            showarrow=False,
            font=dict(size=10, color=REO_BOTTOM),
        )
    if top_layers:
        section_shape = str(st.session_state.get("sec_shape", get_param("sec_shape", "RECT")) or "RECT")
        _, top_label = main_longitudinal_reo_pair_labels(section_shape, variant="inputs_compact")
        fig.add_annotation(
            x=side_view_display_x(0.22 * model["total_length_m"], model),
            y=max(top_base_y - 0.04 * beam_depth_m, 0.10 * beam_depth_m),
            text=top_label,
            showarrow=False,
            font=dict(size=10, color=REO_TOP),
        )


def add_section_marker(fig: go.Figure, model: dict[str, Any]) -> None:
    x_pos = model.get("section_x_m")
    if x_pos is None:
        return
    beam_depth_m = model["D_m"]
    fig.add_shape(
        type="line",
        x0=x_pos,
        y0=-0.12 * beam_depth_m,
        x1=x_pos,
        y1=1.20 * beam_depth_m,
        line=dict(color=_SIDE_VIEW_SECTION_MARKER, width=1.4, dash="dash"),
    )
    fig.add_annotation(
        x=x_pos,
        y=1.25 * beam_depth_m,
        text="Section",
        showarrow=False,
        font=dict(size=10, color=_SIDE_VIEW_SECTION_MARKER),
    )


def add_side_view_udl(
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
            line=dict(width=0, color=DIAGRAM_TRANSPARENT),
            fillcolor=_SIDE_VIEW_LOAD_FILL,
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
            arrowcolor=SUPPORT_OUTLINE,
            text="",
        )
    if label:
        fig.add_annotation(
            x=(x0 + x1) / 2.0,
            y=y_top + 0.18 * beam_depth_m,
            text=label,
            showarrow=False,
            font=dict(size=11, color=ANNOTATION_TEXT),
        )


def add_side_view_point_load(
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
        arrowcolor=SUPPORT_OUTLINE,
        text="",
    )
    if label:
        fig.add_annotation(
            x=x_pos,
            y=y_top + 0.18 * beam_depth_m,
            text=label,
            showarrow=False,
            font=dict(size=11, color=ANNOTATION_TEXT),
        )


def build_side_view_load_shapes(fig: go.Figure, model: dict[str, Any], *, show_labels: bool) -> None:
    case = model["case"]
    span_m = model["span_m"]
    total_m = model["total_length_m"]
    beam_depth_m = model["D_m"]
    y_top = 1.65 * beam_depth_m
    point_y_top = 1.75 * beam_depth_m
    label_w = f"{'w*' if model['mode'] == 'ULS' else 'w'} = {model['w_value']:.1f} kN/m" if show_labels else None
    label_p = f"{'P*' if model['mode'] == 'ULS' else 'P'} = {model['point_value']:.1f} kN" if show_labels else None

    if case == "Simple beam – UDL over entire span":
        add_side_view_udl(fig, 0.0, span_m, beam_depth_m=beam_depth_m, y_top=y_top, label=label_w)
    elif case == "Cantilever – UDL over entire span":
        add_side_view_udl(fig, 0.0, span_m, beam_depth_m=beam_depth_m, y_top=y_top, label=label_w)
    elif case == "Simple beam – partial UDL from left (length a)":
        add_side_view_udl(fig, 0.0, max(0.0, min(model["a_udl_m"], span_m)), beam_depth_m=beam_depth_m, y_top=y_top, label=label_w)
    elif case == "Simple beam – point load at centre":
        add_side_view_point_load(fig, span_m / 2.0, beam_depth_m=beam_depth_m, y_top=point_y_top, label=label_p)
    elif case == "Simple beam – point load at distance a from left":
        add_side_view_point_load(fig, max(0.0, min(model["a_m"], span_m)), beam_depth_m=beam_depth_m, y_top=point_y_top, label=label_p)
    elif case == "Cantilever – point load at free end":
        add_side_view_point_load(fig, span_m, beam_depth_m=beam_depth_m, y_top=point_y_top, label=label_p)
    elif case == "Cantilever – point load at distance a from fixed end":
        add_side_view_point_load(fig, max(0.0, min(model["a_cant_m"], span_m)), beam_depth_m=beam_depth_m, y_top=point_y_top, label=label_p)
    elif case.startswith("Overhanging beam"):
        add_side_view_point_load(fig, total_m, beam_depth_m=beam_depth_m, y_top=point_y_top, label=label_p)


def no_shear_steel_inputs() -> bool:
    legs = int(max(_safe_float(get_param("lig_legs", 0.0), 0.0), 0.0))
    ld = _safe_float(get_param("lig_d", 0.0), 0.0)
    return legs < 2 or ld <= 0.0


def shear_spacing_used_mm_pair(shear_zone_results: dict[str, Any] | None) -> tuple[float, float]:
    """
    Mid / end spacing (mm) for diagrams: governing envelope spacings when shear_auto_design is on,
    else provided link spacing s_lig for both (manual).
    """
    apply_auto = bool(get_param("shear_auto_design", False))
    s_in = max(_safe_float(get_param("s_lig", 0.0), 0.0), 0.0)
    if not apply_auto:
        return s_in, s_in
    sz = shear_zone_results if isinstance(shear_zone_results, dict) else {}
    s_mid_calc = float(sz.get("shear_mid_spacing_calc_mm") or sz.get("shear_spacing_mid_mm") or 0.0)
    s_end_calc = float(sz.get("shear_spacing_end_mm") or 0.0)
    return (
        s_mid_calc if s_mid_calc > 0.0 else s_in,
        s_end_calc if s_end_calc > 0.0 else s_in,
    )


def zone_label_is_midspan(label: str) -> bool:
    t = str(label or "").strip().lower()
    return "mid" in t


def zones_metres_scaled_for_side_view(shear_zone_results: dict[str, Any], model: dict[str, Any]) -> list[dict[str, Any]]:
    """Zones in real beam coordinates (m) along side-view span, scaled to total_length_m."""
    length_m = max(_safe_float(model.get("total_length_m", 0.0), 0.0), 0.0)
    L_zone_mm = float(shear_zone_results.get("beam_length_mm") or 0.0)
    L_zone_m = max(L_zone_mm / 1000.0, 1e-12)
    scale = length_m / L_zone_m if L_zone_m > 1e-12 else 1.0
    s_mid_used_mm, s_end_used_mm = shear_spacing_used_mm_pair(shear_zone_results)

    out: list[dict[str, Any]] = []
    raw = shear_zone_results.get("zones")
    if isinstance(raw, list) and raw:
        for z in raw:
            if not isinstance(z, dict):
                continue
            lbl = str(z.get("label") or "")
            base_m = max(_safe_float(z.get("spacing"), 0.0), 0.0)
            eff_mm = s_mid_used_mm if zone_label_is_midspan(lbl) else s_end_used_mm
            if eff_mm > 0.0:
                sm_m = eff_mm / 1000.0
            else:
                sm_m = base_m
            sm = sm_m * scale
            x0 = max(0.0, min(length_m, _safe_float(z.get("start"), 0.0) * scale))
            x1 = max(0.0, min(length_m, _safe_float(z.get("end"), 0.0) * scale))
            out.append(
                {
                    "start": x0,
                    "end": x1,
                    "spacing": sm,
                    "label": lbl,
                    "fillcolor": z.get("fillcolor"),
                }
            )
        if os.environ.get("DEBUG_SHEAR_SPACING_ASSERT"):
            for z in out:
                if zone_label_is_midspan(str(z.get("label", ""))):
                    _mm = float(z.get("spacing", 0.0) or 0.0) / max(scale, 1e-15) * 1000.0
                    assert abs(_mm - s_mid_used_mm) < 1e-3
        return out

    for seg in list(shear_zone_results.get("strip_segments_mm") or []):
        x0_m = float(seg.get("x0_mm", 0.0) or 0.0) / 1000.0
        x1_m = float(seg.get("x1_mm", 0.0) or 0.0) / 1000.0
        zt = str(seg.get("zone", "") or "")
        eff_mm = s_mid_used_mm if zt == "mid" else s_end_used_mm
        if eff_mm <= 0.0:
            eff_mm = float(seg.get("spacing_mm", 0.0) or 0.0)
        s_m = eff_mm / 1000.0
        zid = str(seg.get("zone", "1") or "1")
        out.append(
            {
                "start": max(0.0, min(length_m, x0_m * scale)),
                "end": max(0.0, min(length_m, x1_m * scale)),
                "spacing": max(s_m * scale, 0.0),
                "label": f"Zone {zid}",
                "fillcolor": None,
            }
        )
    if os.environ.get("DEBUG_SHEAR_SPACING_ASSERT"):
        for seg, row in zip(shear_zone_results.get("strip_segments_mm") or [], out):
            if str(seg.get("zone", "")) == "mid":
                _mm = float(row.get("spacing", 0.0) or 0.0) / max(scale, 1e-15) * 1000.0
                assert abs(_mm - s_mid_used_mm) < 1e-3
                break
    return out


def get_bar_positions(x0: float, x1: float, spacing: float) -> list[float]:
    """Distribute stirrup centres evenly within [x0, x1] using nominal spacing (rendering only)."""
    zone_length = x1 - x0
    if zone_length <= 0 or spacing <= 0:
        return []
    n_bars = max(1, int(round(zone_length / spacing)))
    actual_spacing = zone_length / n_bars
    return [x0 + actual_spacing * (i + 0.5) for i in range(n_bars)]


def stirrup_tuples_from_zones(
    zones: list[dict[str, Any]],
    length_m: float,
    *,
    s_global_m: float,
    support_condition: str = "simply_supported",
) -> list[tuple[float, float]]:
    """(x_m, nominal_spacing_m) per stirrup; zone-based distribution, no cumulative stepping."""
    if not zones or length_m <= 0.0:
        return []
    s_fallback = max(float(s_global_m or 0.0), 1e-12)
    zz = [z for z in zones if isinstance(z, dict)]
    n = len(zz)
    tol_len = max(1e-5 * length_m, 1e-9)
    tol_edge = max(1e-6 * length_m, 1e-9)

    mirror_right_idx: int | None = None
    if str(support_condition or "") == "simply_supported" and n >= 2:
        z0 = zz[0]
        zl = zz[-1]
        x0_s = float(z0.get("start", 0.0) or 0.0)
        x0_e = float(z0.get("end", 0.0) or 0.0)
        xl_s = float(zl.get("start", 0.0) or 0.0)
        xl_e = float(zl.get("end", 0.0) or 0.0)
        s0 = float(z0.get("spacing", 0.0) or 0.0)
        sl = float(zl.get("spacing", 0.0) or 0.0)
        len0 = x0_e - x0_s
        lenl = xl_e - xl_s
        if (
            len0 > tol_len
            and lenl > tol_len
            and abs(len0 - lenl) <= tol_len
            and abs(s0 - sl) <= max(1e-9, 1e-6 * max(s0, sl, 1e-12))
            and x0_s <= tol_edge
            and xl_e >= length_m - tol_edge
        ):
            mirror_right_idx = n - 1

    pos: list[tuple[float, float]] = []
    left_mirror_positions: list[float] | None = None
    max_bars = 500

    for idx, z in enumerate(zz):
        x0 = float(z.get("start", 0.0) or 0.0)
        x1 = float(z.get("end", 0.0) or 0.0)
        if x1 < x0:
            x0, x1 = x1, x0
        spacing_m = float(z.get("spacing", 0.0) or 0.0)
        if spacing_m <= 0.0:
            spacing_m = s_fallback
        nominal_s = spacing_m

        if mirror_right_idx is not None and idx == mirror_right_idx and left_mirror_positions is not None:
            positions = [length_m - x for x in reversed(left_mirror_positions)]
        else:
            positions = get_bar_positions(x0, x1, spacing_m)

        if idx == 0 and mirror_right_idx is not None:
            left_mirror_positions = positions

        for x in positions:
            if len(pos) >= max_bars:
                return pos
            x_clamped = min(max(x, 0.0), length_m)
            pos.append((x_clamped, nominal_s))

    if mirror_right_idx is not None and left_mirror_positions is not None and os.environ.get(
        "DEBUG_STIRRUP_SYMMETRY"
    ):
        _rp = [length_m - x for x in reversed(left_mirror_positions)]
        print("Left bars:", len(left_mirror_positions))
        print("Right bars:", len(_rp))

    return pos


def stirrup_tuples_uniform(model: dict[str, Any]) -> list[tuple[float, float]]:
    spacing_mm = model["spacing_mm"]
    if spacing_mm <= 0.0 or model["lig_legs"] < 2:
        return []
    spacing_m = spacing_mm / 1000.0
    length_m = model["total_length_m"]
    if spacing_m <= 0.0 or length_m <= 0.0:
        return []

    edge_offset = min(max(spacing_m * 0.5, 0.05), max(length_m * 0.08, 0.08))
    x0 = edge_offset
    x1 = length_m - edge_offset
    positions = get_bar_positions(x0, x1, spacing_m)
    out = [(x, spacing_m) for x in positions]
    if len(out) > 80:
        out = out[:: int(math.ceil(len(out) / 80))]
    return out


def build_stirrup_markers(fig: go.Figure, model: dict[str, Any], *, shear_fails: bool = False) -> None:
    sz = get_param("shear_zone_results", None)
    asv_absent = no_shear_steel_inputs()
    has_zone_payload = isinstance(sz, dict) and (bool(sz.get("zones")) or bool(sz.get("strip_segments_mm")))
    zones_enabled = bool(get_param("shear_zone_enabled", True))
    show_zoned_mode = zones_enabled and has_zone_payload
    if shear_fails and not show_zoned_mode:
        diagram_mode_label = "Shear links (required spacings unavailable — layout incomplete)"
    elif shear_fails and show_zoned_mode:
        diagram_mode_label = "Shear links shown at required zone spacings (Check 10; capacity not satisfied)"
    elif show_zoned_mode:
        diagram_mode_label = "Shear links at required zone spacings (Check 10 envelope)"
    else:
        diagram_mode_label = "Shear links at provided spacing (input s_lig)"

    beam_depth_m = model["D_m"]
    y0 = 0.10 * beam_depth_m
    y1 = 0.90 * beam_depth_m
    y_mid = 0.5 * (y0 + y1)
    label_y = -0.26 * beam_depth_m
    note_y = -0.34 * beam_depth_m
    length_m = max(model["total_length_m"], 0.0)

    work_model = dict(model)
    if not work_model.get("side_view_display"):
        work_model["side_view_display"] = side_view_display_state(model)
    display_length_m = max(
        _safe_float(work_model["side_view_display"].get("display_length_m", model["total_length_m"]), model["total_length_m"]),
        0.1,
    )

    stirrup_tuples: list[tuple[float, float]] = []
    zones_scaled: list[dict[str, Any]] = []

    if show_zoned_mode and isinstance(sz, dict):
        zones_scaled = zones_metres_scaled_for_side_view(sz, model)
        _s_mm = max(float(model.get("spacing_mm", 0.0) or 0.0), 0.0)
        _s_global_m = _s_mm / 1000.0 if _s_mm > 0.0 else 0.15
        stirrup_tuples = stirrup_tuples_from_zones(
            zones_scaled,
            length_m,
            s_global_m=_s_global_m,
            support_condition=str(model.get("support_condition", "simply_supported") or "simply_supported"),
        )
        for i, z in enumerate(zones_scaled):
            zs = float(z.get("start", 0.0) or 0.0)
            ze = float(z.get("end", 0.0) or 0.0)
            if ze <= zs + 1e-12:
                continue
            xa = side_view_display_x(zs, work_model)
            xb = side_view_display_x(ze, work_model)
            fill = z.get("fillcolor") or SHEAR_ZONE_SIDE_VIEW_FILLS[i % len(SHEAR_ZONE_SIDE_VIEW_FILLS)]
            fig.add_shape(
                type="rect",
                x0=min(xa, xb),
                x1=max(xa, xb),
                y0=0.0,
                y1=beam_depth_m,
                fillcolor=fill,
                line=dict(width=0),
                layer="below",
            )
            xmid_r = 0.5 * (zs + ze)
            xmid_d = side_view_display_x(xmid_r, work_model)
            sm_mm = int(round(max(float(z.get("spacing", 0.0) or 0.0), 0.0) * 1000.0))
            zlbl = str(z.get("label") or "").strip()
            ann_txt = (
                f"{zlbl} — required {sm_mm} mm" if zlbl else f"Required spacing {sm_mm} mm"
            )
            fig.add_annotation(
                x=xmid_d,
                y=beam_depth_m + 0.05 * beam_depth_m,
                text=ann_txt,
                showarrow=False,
                font=dict(size=10, color=ANNOTATION_TEXT),
            )
    elif not show_zoned_mode:
        stirrup_tuples = stirrup_tuples_uniform(model)

    if stirrup_tuples:
        reals = [t[0] for t in stirrup_tuples]
        r2s = {t[0]: t[1] for t in stirrup_tuples}
        min_sp = max(0.025 * display_length_m, 0.06 * beam_depth_m)
        if show_zoned_mode:
            _xd_sorted = sorted(side_view_display_x(r, work_model) for r in reals)
            eps = max(1e-5 * display_length_m, 1e-6)
            display_xs = []
            for _xd in _xd_sorted:
                if not display_xs or _xd - display_xs[-1] >= eps:
                    display_xs.append(_xd)
        else:
            display_xs = side_view_display_positions(reals, work_model, min_spacing=min_sp)

        def _spacing_mm_for_display_x(xd: float) -> int:
            best_r = min(reals, key=lambda r: abs(side_view_display_x(r, work_model) - xd))
            return int(round(max(r2s.get(best_r, 0.0), 0.0) * 1000.0))

        for xd in display_xs:
            fig.add_shape(
                type="line",
                x0=xd,
                y0=y0,
                x1=xd,
                y1=y1,
                line=dict(color=LINK_STEEL, width=1.2),
            )
        fig.add_trace(
            go.Scatter(
                x=display_xs,
                y=[y_mid] * len(display_xs),
                mode="markers",
                marker=dict(size=10, opacity=0, color=DIAGRAM_TRANSPARENT),
                hovertext=[
                    (
                        f"Required spacing (zone): {_spacing_mm_for_display_x(xd)} mm"
                        if show_zoned_mode
                        else f"Provided spacing: {_spacing_mm_for_display_x(xd)} mm"
                    )
                    for xd in display_xs
                ],
                hoverinfo="text",
                showlegend=False,
            )
        )
        if show_zoned_mode:
            fig.add_annotation(
                x=display_length_m / 2.0,
                y=label_y,
                text=diagram_mode_label,
                showarrow=False,
                font=dict(size=11, color=LINK_STEEL),
            )
        else:
            _sub = f"Provided spacing = {model['spacing_mm']:.0f} mm"
            fig.add_annotation(
                x=display_length_m / 2.0,
                y=label_y,
                text=f"{diagram_mode_label} — {_sub}",
                showarrow=False,
                font=dict(size=11, color=LINK_STEEL),
            )
    elif show_zoned_mode:
        fig.add_annotation(
            x=display_length_m / 2.0,
            y=label_y,
            text=diagram_mode_label,
            showarrow=False,
            font=dict(size=11, color=REO_INACTIVE),
        )
        fig.add_annotation(
            x=display_length_m / 2.0,
            y=note_y,
            text="No stirrup positions in zone layout — check span and demands",
            showarrow=False,
            font=dict(size=9, color=ANNOTATION_TEXT),
        )
    elif asv_absent:
        fig.add_annotation(
            x=display_length_m / 2.0,
            y=label_y,
            text="No shear reinforcement provided",
            showarrow=False,
            font=dict(size=11, color=REO_INACTIVE),
        )
    else:
        fig.add_annotation(
            x=display_length_m / 2.0,
            y=label_y,
            text="Link spacing not set",
            showarrow=False,
            font=dict(size=11, color=REO_INACTIVE),
        )


def add_side_view_break_marks(fig: go.Figure, model: dict[str, Any]) -> None:
    state = model.get("side_view_display", {})
    if not state or not state.get("use_break"):
        return

    beam_depth_m = model["D_m"]
    display_length_m = max(_safe_float(state.get("display_length_m", 0.0), 0.0), 0.1)
    dx = max(0.012 * display_length_m, 0.05)
    y0 = 0.06 * beam_depth_m
    y1 = 0.94 * beam_depth_m

    for x_center in (
        _safe_float(state.get("break_left_display_m", 0.0), 0.0),
        _safe_float(state.get("break_right_display_m", 0.0), 0.0),
    ):
        for offset in (-0.30 * dx, 0.30 * dx):
            x0 = x_center + offset - 0.50 * dx
            x1 = x_center + offset + 0.50 * dx
            fig.add_shape(type="line", x0=x0, y0=y0, x1=x1, y1=y1, line=dict(color=MARKER_OUTLINE, width=5.0))
            fig.add_shape(type="line", x0=x0, y0=y0, x1=x1, y1=y1, line=dict(color=SUPPORT_OUTLINE, width=1.4))


def add_side_view_pinned_support(
    fig: go.Figure,
    x_pos: float,
    width: float,
    depth: float,
    beam_depth_m: float,
    *,
    roller: bool = False,
) -> None:
    ground_drop = max(SUPPORT_GROUND_DROP_BEAM_RATIO * beam_depth_m, SUPPORT_GROUND_MIN_DROP_MM / 1000.0)
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
        roller_r = max(SUPPORT_ROLLER_RADIUS_BEAM_RATIO * beam_depth_m, SUPPORT_ROLLER_MIN_RADIUS_MM / 1000.0)
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


def add_side_view_fixed_support(fig: go.Figure, x_pos: float, hatch_dx: float, beam_depth_m: float) -> None:
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


def build_side_view_support_shapes(fig: go.Figure, model: dict[str, Any]) -> None:
    display_length_m = max(
        _safe_float(
            model.get("side_view_display", {}).get("display_length_m", model["total_length_m"]),
            model["total_length_m"],
        ),
        0.1,
    )
    beam_depth_m = model["D_m"]
    support_w = max(display_length_m * SUPPORT_PIN_WIDTH_SPAN_RATIO, SUPPORT_PIN_MIN_WIDTH_MM / 1000.0)
    support_d = max(beam_depth_m * SUPPORT_PIN_DEPTH_BEAM_RATIO, SUPPORT_PIN_MIN_DEPTH_MM / 1000.0)
    fixed_hatch_dx = max(
        display_length_m * SUPPORT_FIXED_HATCH_SPAN_RATIO,
        SUPPORT_FIXED_MIN_HATCH_MM / 1000.0,
    )
    support_pair = model.get("support_pair")

    def _draw_labelled_support(x_pos: float, label: str, *, right_edge: bool = False) -> None:
        lbl = str(label or "Pinned").strip().lower()
        if lbl == "fixed":
            add_side_view_fixed_support(fig, x_pos, fixed_hatch_dx, beam_depth_m)
        elif lbl == "roller":
            add_side_view_pinned_support(fig, x_pos, support_w, support_d, beam_depth_m, roller=True)
        else:
            add_side_view_pinned_support(
                fig,
                x_pos,
                support_w,
                support_d,
                beam_depth_m,
                roller=bool(right_edge and str(model.get("support_condition", "")) == "simply_supported"),
            )

    if model["support_condition"] == "cantilever":
        add_side_view_fixed_support(fig, 0.0, fixed_hatch_dx, beam_depth_m)
        return
    xs = list(model["support_positions"])
    if isinstance(support_pair, tuple) and len(support_pair) == 2 and len(xs) >= 2:
        _draw_labelled_support(side_view_display_x(xs[0], model), str(support_pair[0]), right_edge=False)
        _draw_labelled_support(side_view_display_x(xs[-1], model), str(support_pair[1]), right_edge=True)
        return
    if model["support_condition"] == "simply_supported" and len(xs) >= 2:
        add_side_view_pinned_support(
            fig, side_view_display_x(xs[0], model), support_w, support_d, beam_depth_m, roller=False
        )
        add_side_view_pinned_support(
            fig, side_view_display_x(xs[-1], model), support_w, support_d, beam_depth_m, roller=True
        )
        return
    for x_pos in xs:
        add_side_view_pinned_support(
            fig, side_view_display_x(x_pos, model), support_w, support_d, beam_depth_m, roller=False
        )


_side_view_y_bounds = side_view_y_bounds
_build_side_view_figure = build_side_view_figure
_side_view_display_state = side_view_display_state
_side_view_display_x = side_view_display_x
_side_view_display_positions = side_view_display_positions
_build_side_view_tension_reo = build_side_view_tension_reo
_add_section_marker = add_section_marker
_add_side_view_udl = add_side_view_udl
_add_side_view_point_load = add_side_view_point_load
_build_side_view_load_shapes = build_side_view_load_shapes
_no_shear_steel_inputs = no_shear_steel_inputs
_shear_spacing_used_mm_pair = shear_spacing_used_mm_pair
_zone_label_is_midspan = zone_label_is_midspan
_zones_metres_scaled_for_side_view = zones_metres_scaled_for_side_view
_get_bar_positions = get_bar_positions
_stirrup_tuples_from_zones = stirrup_tuples_from_zones
_stirrup_tuples_uniform = stirrup_tuples_uniform
_build_stirrup_markers = build_stirrup_markers
_add_side_view_break_marks = add_side_view_break_marks
_add_side_view_pinned_support = add_side_view_pinned_support
_add_side_view_fixed_support = add_side_view_fixed_support
_build_side_view_support_shapes = build_side_view_support_shapes
