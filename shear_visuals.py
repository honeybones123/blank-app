from __future__ import annotations

import json
import math
import os
import time
from typing import Any

import numpy as np
import plotly.graph_objects as go
import streamlit as st

from section_layout import compute_section_layout
from section_props.plot import plot_shape
from section_props.plotly_section import make_sectionA_figure
from state_and_helpers import get_param
from widgets_helpers import main_longitudinal_reo_pair_labels


VISUAL_HEIGHT = 360
BEHAVIOUR_VISUAL_HEIGHT = 420
BEHAVIOUR_VISUAL_WIDTH = 1120
SIDE_VIEW_VISUAL_HEIGHT = 260
SIDE_VIEW_VISUAL_WIDTH = BEHAVIOUR_VISUAL_WIDTH
_BEAM_VIEWS_LEFT_RATIO = 0.38
_BEAM_VIEWS_RIGHT_RATIO = 0.62
_SIDE_VIEW_BREAK_SLENDERNESS = 10.0
_SHEAR_ZONE_SIDE_VIEW_FILLS = (
    "rgba(255,0,0,0.15)",
    "rgba(255,165,0,0.15)",
    "rgba(0,200,0,0.15)",
)
_BEAM_Y0 = 0.40
_BEAM_Y1 = 0.60
_DEFAULT_LOADING_CASE = "Simple beam – UDL over entire span"
_FIELD_TOP_PAD = 0.012
_FIELD_BOT_PAD = 0.012
_FIELD_SPLINE_SMOOTHING = 0.65


def _dbg_log(message: str, data: dict[str, Any], *, hypothesis_id: str, run_id: str = "ss_psf_debug") -> None:
    return


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
        if math.isnan(number):
            return float(default)
        return number
    except Exception:
        return float(default)


def _active_limit_state_for_visuals() -> str:
    return str(st.session_state.get("loads_edit_mode", get_param("loads_edit_mode", "ULS")) or "ULS").upper()


def _session_or_shared(widget_key: str, shared_key: str, default: Any = None) -> Any:
    widget_val = st.session_state.get(widget_key)
    if widget_val is not None:
        return widget_val
    shared_val = st.session_state.get(shared_key)
    if shared_val is not None:
        return shared_val
    return get_param(shared_key, default)


def _normalise_loading_case(raw_case: Any) -> str:
    case = str(raw_case or "").strip()
    if case.startswith("Simple beam"):
        return case
    if case.startswith("Cantilever"):
        return case
    if case.startswith("Overhanging beam"):
        return case
    return _DEFAULT_LOADING_CASE


def _shared_or_widget(shared_key: str, widget_key: str, default: Any = None) -> Any:
    shared_val = st.session_state.get(shared_key)
    if shared_val not in (None, ""):
        return shared_val
    widget_val = st.session_state.get(widget_key)
    if widget_val not in (None, ""):
        return widget_val
    return get_param(shared_key, default)


def _current_section_x(length_m: float) -> float | None:
    source = str(st.session_state.get("design_actions_source", get_param("design_actions_source", "max")) or "max")
    committed = bool(st.session_state.get("design_section_committed", False))
    design_x = _safe_float(st.session_state.get("design_section_x_m", get_param("design_section_x_m", 0.0)), 0.0)
    preview_x = _safe_float(st.session_state.get("section_cursor_x_m", get_param("section_cursor_x_m", 0.0)), 0.0)

    if source == "section":
        x_val = design_x if committed else preview_x
    elif committed and design_x > 0.0:
        x_val = design_x
    elif preview_x > 0.0:
        x_val = preview_x
    else:
        return None

    return x_val if 0.0 <= x_val <= length_m else None


def _get_canonical_shear_visual_loading_state() -> dict[str, Any]:
    mode = _active_limit_state_for_visuals()
    case = _normalise_loading_case(_shared_or_widget("sfd_case", "load_case", _DEFAULT_LOADING_CASE))
    length_mm = _safe_float(st.session_state.get("L", get_param("L", 3000.0)), 3000.0)
    span_m = max(length_mm / 1000.0, 0.1)
    loading_span_m = _safe_float(_shared_or_widget("span_L_m", "sfd_L_m", span_m), span_m)

    return {
        "mode": mode,
        "case": case,
        "span_m": span_m,
        "loading_span_m": max(loading_span_m, 0.0),
        "a_m": max(_safe_float(_shared_or_widget("a_m", "load_a_point", span_m / 2.0), span_m / 2.0), 0.0),
        "a_udl_m": max(_safe_float(_shared_or_widget("a_udl_m", "sfd_a_udl", span_m / 2.0), span_m / 2.0), 0.0),
        "a_cant_m": max(_safe_float(_shared_or_widget("a_cant_m", "sfd_a_cant", span_m / 2.0), span_m / 2.0), 0.0),
        "a_overhang_m": max(_safe_float(_shared_or_widget("a_overhang_m", "sfd_a_overhang", 0.0), 0.0), 0.0),
        "w_value": max(_safe_float(get_param("w_uls_kNm_per_m" if mode == "ULS" else "w_sls_kNm_per_m", 0.0), 0.0), 0.0),
        "point_value": max(_safe_float(get_param("P_uls_kN" if mode == "ULS" else "P_sls_kN", 0.0), 0.0), 0.0),
    }


def _get_canonical_shear_visual_support_state(loading_state: dict[str, Any] | None = None) -> str:
    support_pair = None
    support_resolution = None
    try:
        from deflection import (
            get_resolved_deflection_support_type,
            get_deflection_diagram_support_condition,
            _governing_span_support_pair,
        )

        support_type = str(get_resolved_deflection_support_type(st.session_state) or "Simply supported").strip()
        support_resolution = get_deflection_diagram_support_condition(st.session_state)
        support_pair = _governing_span_support_pair(st.session_state, support_resolution)
    except Exception:
        support_type = str(
            st.session_state.get(
                "defl_support_type",
                get_param("defl_support_type", "Simply supported"),
            )
            or "Simply supported"
        ).strip()
    if support_type == "Cantilever":
        canonical = "cantilever"
    elif support_type in ("Pinned–Pinned", "Pinned-Pinned"):
        canonical = "pinned_pinned"
    else:
        canonical = "simply_supported"
    # region agent log
    _dbg_log(
        "shear visual support state",
        {
            "resolved_support_type": support_type,
            "canonical_support_condition": canonical,
            "support_pair": list(support_pair) if isinstance(support_pair, tuple) else None,
            "controlling_span_idx": None if not isinstance(support_resolution, dict) else support_resolution.get("controlling_span_idx"),
            "continuous_end_side": None if not isinstance(support_resolution, dict) else support_resolution.get("continuous_end_side"),
        },
        run_id="pre-fix",
        hypothesis_id="V1",
    )
    # endregion
    return canonical


def _support_pair_from_resolved_support_type(support_type: str | None) -> tuple[str, str] | None:
    raw_label = str(support_type or "").strip()
    label = raw_label.replace("-", "–")
    if not label:
        return None
    if raw_label == "Fixed-ended":
        return ("Fixed", "Fixed")
    if label == "Fixed–Pinned":
        return ("Fixed", "Pinned")
    if label == "Pinned–Fixed":
        return ("Pinned", "Fixed")
    if label in ("Pinned–Pinned", "Continuous – end span", "Continuous – interior span"):
        return ("Pinned", "Pinned")
    if label == "Simply supported":
        return ("Pinned", "Roller")
    return None

def _get_canonical_shear_visual_span_state(loading_state: dict[str, Any] | None = None) -> dict[str, float]:
    loading_state = loading_state or _get_canonical_shear_visual_loading_state()
    span_m = max(_safe_float(loading_state.get("span_m", 0.0), 0.0), 0.1)
    overhang_m = max(_safe_float(loading_state.get("a_overhang_m", 0.0), 0.0), 0.0)
    total_length_m = span_m + overhang_m if str(loading_state.get("case", "")).startswith("Overhanging beam") else span_m
    return {
        "span_m": span_m,
        "overhang_m": overhang_m,
        "total_length_m": total_length_m,
    }


def _get_canonical_shear_visual_depth_state() -> dict[str, float]:
    D_m = max(_safe_float(get_param("D", 600.0), 600.0) / 1000.0, 0.1)
    d_m = _safe_float(st.session_state.get("d", get_param("d", 0.0)), 0.0) / 1000.0
    if d_m <= 0.0:
        d_m = D_m
    return {
        "D_m": D_m,
        "d_m": max(d_m, 0.05),
    }


def _get_canonical_shear_visual_section_location(length_m: float) -> float | None:
    return _current_section_x(length_m)


def _beam_model() -> dict[str, Any]:
    loading_state = _get_canonical_shear_visual_loading_state()
    support_condition = _get_canonical_shear_visual_support_state(loading_state)
    support_pair = None
    resolved_support_type = None
    try:
        from deflection import get_deflection_diagram_support_condition, _governing_span_support_pair

        support_resolution = get_deflection_diagram_support_condition(st.session_state)
        resolved_support_type = str(support_resolution.get("support_type") or "")
        support_pair = _governing_span_support_pair(st.session_state, support_resolution)
    except Exception:
        support_pair = None
        resolved_support_type = None
    if not isinstance(support_pair, tuple) or len(support_pair) != 2:
        support_pair = _support_pair_from_resolved_support_type(resolved_support_type)
    span_state = _get_canonical_shear_visual_span_state(loading_state)
    depth_state = _get_canonical_shear_visual_depth_state()
    section_layout = compute_section_layout()
    reo_layout = section_layout.get("reo_layout", {}) if isinstance(section_layout, dict) else {}

    bottom_layers = list(reo_layout.get("bottom", []) or [])
    top_layers = list(reo_layout.get("top", []) or [])

    support_positions = [0.0, span_state["span_m"]]
    if support_condition == "cantilever":
        support_positions = [0.0]
    # region agent log
    _dbg_log(
        "shear visual beam model",
        {
            "case": loading_state.get("case"),
            "span_m": span_state.get("span_m"),
            "total_length_m": span_state.get("total_length_m"),
            "support_condition": support_condition,
            "resolved_support_type": resolved_support_type,
            "support_pair": list(support_pair) if isinstance(support_pair, tuple) else None,
            "support_positions": support_positions,
        },
        run_id="pre-fix",
        hypothesis_id="V2",
    )
    # endregion

    return {
        **loading_state,
        **span_state,
        **depth_state,
        "support_condition": support_condition,
        "support_pair": support_pair,
        "support_positions": support_positions,
        "section_x_m": _get_canonical_shear_visual_section_location(span_state["total_length_m"]),
        "spacing_mm": max(_safe_float(get_param("s_lig", 0.0), 0.0), 0.0),
        "lig_legs": int(max(_safe_float(get_param("lig_legs", 0.0), 0.0), 0.0)),
        "bottom_layers": bottom_layers,
        "top_layers": top_layers,
        "reo_points": section_layout.get("reo_points", []) if isinstance(section_layout, dict) else [],
        "section_layout": section_layout,
    }


def _classify_shear_behaviour_visual_case(model: dict[str, Any]) -> str:
    case = str(model.get("case", "") or "")
    support_condition = str(model.get("support_condition", "simply_supported") or "simply_supported")

    if support_condition == "cantilever":
        if "point load at free end" in case:
            return "cantilever_tip"
        if "point load" in case:
            return "cantilever_eccentric"
        return "cantilever_udl"

    if case == "Simple beam – point load at centre":
        return "ss_midspan_point"
    if case == "Simple beam – point load at distance a from left":
        span_m = max(_safe_float(model.get("span_m", 0.0), 0.0), 0.1)
        load_x = max(0.0, min(_safe_float(model.get("a_m", span_m / 2.0), span_m / 2.0), span_m))
        if min(load_x, span_m - load_x) <= 0.28 * span_m:
            return "ss_near_support_point"
        return "ss_eccentric_point"
    if "UDL" in case:
        return "ss_udl"
    if case.startswith("Overhanging beam"):
        return "ss_near_support_point"
    return "fallback_simple"


def _side_view_y_bounds(
    beam_depth_m: float, support_condition: str
) -> tuple[float, float]:
    """Tight y-range around drawn side-view content (beam, supports, stirrup label)."""
    D = max(beam_depth_m, 0.05)
    support_d = max(0.28 * D, 0.08)
    ground_y = -support_d - 0.08 * D
    stirrup_label_y = -0.26 * D
    pad = max(0.08 * D, 0.025)

    if support_condition == "cantilever":
        min_content = min(-0.55 * D, stirrup_label_y)
        max_content = max(D, 1.55 * D)
    else:
        roller_drop = 0.22 * D if support_condition == "simply_supported" else 0.0
        min_content = min(ground_y - roller_drop, stirrup_label_y)
        max_content = D

    return min_content - pad, max_content + pad


def _build_side_view_figure(length_m: float, beam_depth_m: float, height: int, support_condition: str) -> go.Figure:
    fig = go.Figure()
    pad = max(length_m * 0.06, 0.2)
    y_min, y_max = _side_view_y_bounds(beam_depth_m, support_condition)
    fig.update_layout(
        height=height,
        width=SIDE_VIEW_VISUAL_WIDTH,
        autosize=False,
        margin=dict(l=10, r=10, t=10, b=10),
        paper_bgcolor="white",
        plot_bgcolor="white",
        showlegend=False,
    )
    fig.update_xaxes(visible=False, range=[-pad, length_m + pad], fixedrange=True, showgrid=False, zeroline=False)
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


def _build_behaviour_figure(length_m: float, beam_depth_m: float, height: int) -> go.Figure:
    fig = go.Figure()
    pad = max(length_m * 0.06, 0.2)
    y_min = -0.92 * beam_depth_m
    y_max = 1.9 * beam_depth_m
    fig.update_layout(
        height=height,
        width=BEHAVIOUR_VISUAL_WIDTH,
        autosize=False,
        margin=dict(l=10, r=10, t=8, b=8),
        paper_bgcolor="white",
        plot_bgcolor="white",
        showlegend=False,
    )
    fig.update_xaxes(visible=False, range=[-pad, length_m + pad], fixedrange=True, showgrid=False, zeroline=False)
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


def _cross_section_frame_size(width_mm: float, depth_mm: float) -> float:
    return max(width_mm, depth_mm) * 1.32


def _target_side_display_length(model: dict[str, Any]) -> float:
    beam_depth_m = max(_safe_float(model.get("D_m", 0.0), 0.0), 0.1)
    dims = ((model.get("section_layout") or {}).get("dims") or {})
    width_mm = _safe_float(dims.get("bf", dims.get("b", beam_depth_m * 1000.0)), beam_depth_m * 1000.0)
    cross_frame_m = _cross_section_frame_size(width_mm, beam_depth_m * 1000.0) / 1000.0
    x_range_target = cross_frame_m * (_BEAM_VIEWS_RIGHT_RATIO / _BEAM_VIEWS_LEFT_RATIO)
    return max(x_range_target - 0.4, max(0.85 * beam_depth_m, 0.18))


def _side_view_display_state(model: dict[str, Any]) -> dict[str, float | bool]:
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


def _side_view_display_x(x_real: float, model: dict[str, Any]) -> float:
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


def _side_view_display_positions(values: list[float], model: dict[str, Any], *, min_spacing: float) -> list[float]:
    transformed = sorted(_side_view_display_x(x_val, model) for x_val in values)
    if not transformed:
        return []

    kept = [transformed[0]]
    for x_val in transformed[1:]:
        if x_val - kept[-1] >= min_spacing:
            kept.append(x_val)
    return kept


def _add_side_view_break_marks(fig: go.Figure, model: dict[str, Any]) -> None:
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
            fig.add_shape(type="line", x0=x0, y0=y0, x1=x1, y1=y1, line=dict(color="white", width=5.0))
            fig.add_shape(type="line", x0=x0, y0=y0, x1=x1, y1=y1, line=dict(color="rgba(35,35,35,0.95)", width=1.4))


def _add_beam_band(fig: go.Figure, x_end: float, beam_depth_m: float | None = None) -> None:
    y0 = _BEAM_Y0 if beam_depth_m is None else 0.0
    y1 = _BEAM_Y1 if beam_depth_m is None else beam_depth_m
    fig.add_shape(
        type="rect",
        x0=0.0,
        y0=y0,
        x1=x_end,
        y1=y1,
        line=dict(color="rgba(35,35,35,1.0)", width=2),
        fillcolor="rgba(205,212,220,0.35)",
    )


def _add_pinned_support(
    fig: go.Figure,
    x_pos: float,
    width: float,
    depth: float,
    beam_depth_m: float,
    *,
    roller: bool = False,
) -> None:
    ground_y = -depth - 0.08 * beam_depth_m
    fig.add_shape(
        type="path",
        path=f"M {x_pos - width},{-depth} L {x_pos + width},{-depth} L {x_pos},{0.0} Z",
        line=dict(color="rgba(35,35,35,1.0)", width=1.4),
        fillcolor="rgba(35,35,35,0.12)",
    )
    fig.add_shape(
        type="line",
        x0=x_pos - width * 1.15,
        y0=ground_y,
        x1=x_pos + width * 1.15,
        y1=ground_y,
        line=dict(color="rgba(80,80,80,0.85)", width=1.0),
    )
    if roller:
        roller_r = max(0.04 * depth, 0.028)
        cy = ground_y - roller_r * 1.4
        fig.add_shape(
            type="circle",
            xref="x",
            yref="y",
            x0=x_pos - roller_r,
            y0=cy - roller_r,
            x1=x_pos + roller_r,
            y1=cy + roller_r,
            line=dict(color="rgba(35,35,35,1.0)", width=1.15),
            fillcolor="rgba(255,255,255,0.55)",
        )


def _add_fixed_support(fig: go.Figure, x_pos: float, hatch_dx: float, beam_depth_m: float) -> None:
    y_min = -0.55 * beam_depth_m
    y_max = 1.55 * beam_depth_m
    fig.add_shape(
        type="line",
        x0=x_pos,
        y0=y_min,
        x1=x_pos,
        y1=y_max,
        line=dict(color="rgba(35,35,35,1.0)", width=6),
    )
    for frac in (0.08, 0.28, 0.48, 0.68, 0.88):
        y_val = y_min + frac * (y_max - y_min)
        fig.add_shape(
            type="line",
            x0=x_pos - hatch_dx,
            y0=y_val + 0.10 * beam_depth_m,
            x1=x_pos,
            y1=y_val - 0.04 * beam_depth_m,
            line=dict(color="rgba(80,80,80,0.82)", width=1.0),
        )


def _build_shear_behaviour_support_shapes(fig: go.Figure, model: dict[str, Any]) -> None:
    length_m = model["total_length_m"]
    beam_depth_m = model["D_m"]
    support_w = max(length_m * 0.03, 0.09)
    support_d = max(0.28 * beam_depth_m, 0.08)
    support_pair = model.get("support_pair")

    def _draw_labelled_support(x_pos: float, label: str, *, right_edge: bool = False) -> None:
        lbl = str(label or "Pinned").strip().lower()
        if lbl == "fixed":
            _add_fixed_support(fig, x_pos, max(length_m * 0.02, 0.05), beam_depth_m)
        elif lbl == "roller":
            _add_pinned_support(fig, x_pos, support_w, support_d, beam_depth_m, roller=True)
        else:
            _add_pinned_support(
                fig,
                x_pos,
                support_w,
                support_d,
                beam_depth_m,
                roller=bool(right_edge and str(model.get("support_condition", "")) == "simply_supported"),
            )

    if model["support_condition"] == "cantilever":
        _add_fixed_support(fig, 0.0, max(length_m * 0.02, 0.05), beam_depth_m)
        return
    xs = list(model["support_positions"])
    if isinstance(support_pair, tuple) and len(support_pair) == 2 and len(xs) >= 2:
        _draw_labelled_support(xs[0], str(support_pair[0]), right_edge=False)
        _draw_labelled_support(xs[-1], str(support_pair[1]), right_edge=True)
        return
    if model["support_condition"] == "simply_supported" and len(xs) >= 2:
        _add_pinned_support(fig, xs[0], support_w, support_d, beam_depth_m, roller=False)
        _add_pinned_support(fig, xs[-1], support_w, support_d, beam_depth_m, roller=True)
        return
    for x_pos in xs:
        _add_pinned_support(fig, x_pos, support_w, support_d, beam_depth_m, roller=False)


def _add_udl(fig: go.Figure, x0: float, x1: float, *, beam_depth_m: float, y_top: float, label: str | None = None) -> None:
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
        fig.add_annotation(x=(x0 + x1) / 2.0, y=y_top + 0.18 * beam_depth_m, text=label, showarrow=False, font=dict(size=11, color="rgba(60,60,60,0.9)"))


def _add_point_load(fig: go.Figure, x_pos: float, *, beam_depth_m: float, y_top: float, label: str | None = None) -> None:
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
        fig.add_annotation(x=x_pos, y=y_top + 0.18 * beam_depth_m, text=label, showarrow=False, font=dict(size=11, color="rgba(60,60,60,0.9)"))


def _build_shear_behaviour_load_shapes(fig: go.Figure, model: dict[str, Any], *, show_labels: bool) -> None:
    case = model["case"]
    span_m = model["span_m"]
    total_m = model["total_length_m"]
    beam_depth_m = model["D_m"]
    y_top = 1.42 * beam_depth_m
    point_y_top = 1.75 * beam_depth_m
    label_w = f"{'w*' if model['mode'] == 'ULS' else 'w'} = {model['w_value']:.1f} kN/m" if show_labels else None
    label_p = f"{'P*' if model['mode'] == 'ULS' else 'P'} = {model['point_value']:.1f} kN" if show_labels else None

    if case == "Simple beam – UDL over entire span":
        _add_udl(fig, 0.0, span_m, beam_depth_m=beam_depth_m, y_top=y_top, label=label_w)
    elif case == "Cantilever – UDL over entire span":
        _add_udl(fig, 0.0, span_m, beam_depth_m=beam_depth_m, y_top=y_top, label=label_w)
    elif case == "Simple beam – partial UDL from left (length a)":
        _add_udl(fig, 0.0, max(0.0, min(model["a_udl_m"], span_m)), beam_depth_m=beam_depth_m, y_top=y_top, label=label_w)
    elif case == "Simple beam – point load at centre":
        _add_point_load(fig, span_m / 2.0, beam_depth_m=beam_depth_m, y_top=point_y_top, label=label_p)
    elif case == "Simple beam – point load at distance a from left":
        _add_point_load(fig, max(0.0, min(model["a_m"], span_m)), beam_depth_m=beam_depth_m, y_top=point_y_top, label=label_p)
    elif case == "Cantilever – point load at free end":
        _add_point_load(fig, span_m, beam_depth_m=beam_depth_m, y_top=point_y_top, label=label_p)
    elif case == "Cantilever – point load at distance a from fixed end":
        _add_point_load(fig, max(0.0, min(model["a_cant_m"], span_m)), beam_depth_m=beam_depth_m, y_top=point_y_top, label=label_p)
    elif case.startswith("Overhanging beam"):
        _add_point_load(fig, total_m, beam_depth_m=beam_depth_m, y_top=point_y_top, label=label_p)


def _add_side_view_pinned_support(
    fig: go.Figure,
    x_pos: float,
    width: float,
    depth: float,
    beam_depth_m: float,
    *,
    roller: bool = False,
) -> None:
    ground_y = -depth - 0.08 * beam_depth_m
    fig.add_shape(
        type="path",
        path=f"M {x_pos - width},{-depth} L {x_pos + width},{-depth} L {x_pos},{0.0} Z",
        line=dict(color="rgba(35,35,35,1.0)", width=1.4),
        fillcolor="rgba(35,35,35,0.12)",
    )
    fig.add_shape(
        type="line",
        x0=x_pos - width * 1.15,
        y0=ground_y,
        x1=x_pos + width * 1.15,
        y1=ground_y,
        line=dict(color="rgba(80,80,80,0.85)", width=1.0),
    )
    if roller:
        roller_r = max(0.04 * depth, 0.028)
        cy = ground_y - roller_r * 1.4
        fig.add_shape(
            type="circle",
            xref="x",
            yref="y",
            x0=x_pos - roller_r,
            y0=cy - roller_r,
            x1=x_pos + roller_r,
            y1=cy + roller_r,
            line=dict(color="rgba(35,35,35,1.0)", width=1.15),
            fillcolor="rgba(255,255,255,0.55)",
        )


def _add_side_view_fixed_support(fig: go.Figure, x_pos: float, hatch_dx: float, beam_depth_m: float) -> None:
    y_min = -0.55 * beam_depth_m
    y_max = 1.55 * beam_depth_m
    fig.add_shape(
        type="line",
        x0=x_pos,
        y0=y_min,
        x1=x_pos,
        y1=y_max,
        line=dict(color="rgba(35,35,35,1.0)", width=6),
    )
    for frac in (0.08, 0.28, 0.48, 0.68, 0.88):
        y_val = y_min + frac * (y_max - y_min)
        fig.add_shape(
            type="line",
            x0=x_pos - hatch_dx,
            y0=y_val + 0.10 * beam_depth_m,
            x1=x_pos,
            y1=y_val - 0.04 * beam_depth_m,
            line=dict(color="rgba(80,80,80,0.82)", width=1.0),
        )


def _build_side_view_support_shapes(fig: go.Figure, model: dict[str, Any]) -> None:
    display_length_m = max(_safe_float(model.get("side_view_display", {}).get("display_length_m", model["total_length_m"]), model["total_length_m"]), 0.1)
    beam_depth_m = model["D_m"]
    support_w = max(display_length_m * 0.03, 0.09)
    support_d = max(0.28 * beam_depth_m, 0.08)
    rendered_supports: list[dict[str, Any]] = []
    support_pair = model.get("support_pair")

    def _draw_labelled_support(x_pos: float, label: str, *, right_edge: bool = False) -> None:
        lbl = str(label or "Pinned").strip().lower()
        if lbl == "fixed":
            _add_side_view_fixed_support(fig, x_pos, max(display_length_m * 0.02, 0.05), beam_depth_m)
            rendered_supports.append({"kind": "fixed", "x": x_pos})
        elif lbl == "roller":
            _add_side_view_pinned_support(fig, x_pos, support_w, support_d, beam_depth_m, roller=True)
            rendered_supports.append({"kind": "roller", "x": x_pos})
        else:
            _add_side_view_pinned_support(
                fig,
                x_pos,
                support_w,
                support_d,
                beam_depth_m,
                roller=bool(right_edge and str(model.get("support_condition", "")) == "simply_supported"),
            )
            rendered_supports.append({"kind": "pinned", "x": x_pos})

    if model["support_condition"] == "cantilever":
        _add_side_view_fixed_support(fig, 0.0, max(display_length_m * 0.02, 0.05), beam_depth_m)
        rendered_supports.append({"kind": "fixed", "x": 0.0})
        # region agent log
        _dbg_log(
            "shear visual side-view supports rendered",
            {
                "support_condition": model.get("support_condition"),
                "support_positions": list(model.get("support_positions") or []),
                "rendered_supports": rendered_supports,
            },
            run_id="pre-fix",
            hypothesis_id="V3",
        )
        # endregion
        return
    xs = list(model["support_positions"])
    if isinstance(support_pair, tuple) and len(support_pair) == 2 and len(xs) >= 2:
        _draw_labelled_support(_side_view_display_x(xs[0], model), str(support_pair[0]), right_edge=False)
        _draw_labelled_support(_side_view_display_x(xs[-1], model), str(support_pair[1]), right_edge=True)
        # region agent log
        _dbg_log(
            "shear visual side-view supports rendered",
            {
                "support_condition": model.get("support_condition"),
                "support_pair": list(support_pair),
                "support_positions": xs,
                "rendered_supports": rendered_supports,
            },
            run_id="post-fix",
            hypothesis_id="V3",
        )
        # endregion
        return
    if model["support_condition"] == "simply_supported" and len(xs) >= 2:
        _add_side_view_pinned_support(
            fig, _side_view_display_x(xs[0], model), support_w, support_d, beam_depth_m, roller=False
        )
        rendered_supports.append({"kind": "pinned", "x": xs[0]})
        _add_side_view_pinned_support(
            fig, _side_view_display_x(xs[-1], model), support_w, support_d, beam_depth_m, roller=True
        )
        rendered_supports.append({"kind": "roller", "x": xs[-1]})
        # region agent log
        _dbg_log(
            "shear visual side-view supports rendered",
            {
                "support_condition": model.get("support_condition"),
                "support_pair": list(support_pair) if isinstance(support_pair, tuple) else None,
                "support_positions": xs,
                "rendered_supports": rendered_supports,
            },
            run_id="pre-fix",
            hypothesis_id="V3",
        )
        # endregion
        return
    for x_pos in xs:
        _add_side_view_pinned_support(
            fig, _side_view_display_x(x_pos, model), support_w, support_d, beam_depth_m, roller=False
        )
        rendered_supports.append({"kind": "pinned", "x": x_pos})
    # region agent log
    _dbg_log(
        "shear visual side-view supports rendered",
        {
            "support_condition": model.get("support_condition"),
            "support_pair": list(support_pair) if isinstance(support_pair, tuple) else None,
            "support_positions": xs,
            "rendered_supports": rendered_supports,
        },
        run_id="pre-fix",
        hypothesis_id="V3",
    )
    # endregion


def _add_side_view_udl(fig: go.Figure, x0: float, x1: float, *, beam_depth_m: float, y_top: float, label: str | None = None) -> None:
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
        fig.add_annotation(x=(x0 + x1) / 2.0, y=y_top + 0.18 * beam_depth_m, text=label, showarrow=False, font=dict(size=11, color="rgba(60,60,60,0.9)"))


def _add_side_view_point_load(fig: go.Figure, x_pos: float, *, beam_depth_m: float, y_top: float, label: str | None = None) -> None:
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
        fig.add_annotation(x=x_pos, y=y_top + 0.18 * beam_depth_m, text=label, showarrow=False, font=dict(size=11, color="rgba(60,60,60,0.9)"))


def _build_side_view_load_shapes(fig: go.Figure, model: dict[str, Any], *, show_labels: bool) -> None:
    case = model["case"]
    span_m = model["span_m"]
    total_m = model["total_length_m"]
    beam_depth_m = model["D_m"]
    y_top = 1.65 * beam_depth_m
    point_y_top = 1.75 * beam_depth_m
    label_w = f"{'w*' if model['mode'] == 'ULS' else 'w'} = {model['w_value']:.1f} kN/m" if show_labels else None
    label_p = f"{'P*' if model['mode'] == 'ULS' else 'P'} = {model['point_value']:.1f} kN" if show_labels else None

    if case == "Simple beam – UDL over entire span":
        _add_side_view_udl(fig, 0.0, span_m, beam_depth_m=beam_depth_m, y_top=y_top, label=label_w)
    elif case == "Cantilever – UDL over entire span":
        _add_side_view_udl(fig, 0.0, span_m, beam_depth_m=beam_depth_m, y_top=y_top, label=label_w)
    elif case == "Simple beam – partial UDL from left (length a)":
        _add_side_view_udl(fig, 0.0, max(0.0, min(model["a_udl_m"], span_m)), beam_depth_m=beam_depth_m, y_top=y_top, label=label_w)
    elif case == "Simple beam – point load at centre":
        _add_side_view_point_load(fig, span_m / 2.0, beam_depth_m=beam_depth_m, y_top=point_y_top, label=label_p)
    elif case == "Simple beam – point load at distance a from left":
        _add_side_view_point_load(fig, max(0.0, min(model["a_m"], span_m)), beam_depth_m=beam_depth_m, y_top=point_y_top, label=label_p)
    elif case == "Cantilever – point load at free end":
        _add_side_view_point_load(fig, span_m, beam_depth_m=beam_depth_m, y_top=point_y_top, label=label_p)
    elif case == "Cantilever – point load at distance a from fixed end":
        _add_side_view_point_load(fig, max(0.0, min(model["a_cant_m"], span_m)), beam_depth_m=beam_depth_m, y_top=point_y_top, label=label_p)
    elif case.startswith("Overhanging beam"):
        _add_side_view_point_load(fig, total_m, beam_depth_m=beam_depth_m, y_top=point_y_top, label=label_p)


def _no_shear_steel_inputs() -> bool:
    legs = int(max(_safe_float(get_param("lig_legs", 0.0), 0.0), 0.0))
    ld = _safe_float(get_param("lig_d", 0.0), 0.0)
    return legs < 2 or ld <= 0.0


def _shear_spacing_used_mm_pair(shear_zone_results: dict[str, Any] | None) -> tuple[float, float]:
    """
    Mid / end spacing (mm) for diagrams: calculated envelope values when shear_auto_design is on,
    else shared link spacing s_lig for both (manual).
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


def _zone_label_is_midspan(label: str) -> bool:
    t = str(label or "").strip().lower()
    return "mid" in t


def _zones_metres_scaled_for_side_view(shear_zone_results: dict[str, Any], model: dict[str, Any]) -> list[dict[str, Any]]:
    """Zones in real beam coordinates (m) along side-view span, scaled to total_length_m."""
    length_m = max(_safe_float(model.get("total_length_m", 0.0), 0.0), 0.0)
    L_zone_mm = float(shear_zone_results.get("beam_length_mm") or 0.0)
    L_zone_m = max(L_zone_mm / 1000.0, 1e-12)
    scale = length_m / L_zone_m if L_zone_m > 1e-12 else 1.0
    s_mid_used_mm, s_end_used_mm = _shear_spacing_used_mm_pair(shear_zone_results)

    out: list[dict[str, Any]] = []
    raw = shear_zone_results.get("zones")
    if isinstance(raw, list) and raw:
        for z in raw:
            if not isinstance(z, dict):
                continue
            lbl = str(z.get("label") or "")
            base_m = max(_safe_float(z.get("spacing"), 0.0), 0.0)
            eff_mm = s_mid_used_mm if _zone_label_is_midspan(lbl) else s_end_used_mm
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
                if _zone_label_is_midspan(str(z.get("label", ""))):
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


def _get_bar_positions(x0: float, x1: float, spacing: float) -> list[float]:
    """Distribute stirrup centres evenly within [x0, x1] using nominal spacing (rendering only)."""
    zone_length = x1 - x0
    if zone_length <= 0 or spacing <= 0:
        return []
    n_bars = max(1, int(round(zone_length / spacing)))
    actual_spacing = zone_length / n_bars
    return [x0 + actual_spacing * (i + 0.5) for i in range(n_bars)]


def _stirrup_tuples_from_zones(
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
            positions = _get_bar_positions(x0, x1, spacing_m)

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


def _stirrup_tuples_uniform(model: dict[str, Any]) -> list[tuple[float, float]]:
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
    positions = _get_bar_positions(x0, x1, spacing_m)
    out = [(x, spacing_m) for x in positions]
    if len(out) > 80:
        out = out[:: int(math.ceil(len(out) / 80))]
    return out


def _build_stirrup_markers(fig: go.Figure, model: dict[str, Any], *, shear_fails: bool = False) -> None:
    sz = get_param("shear_zone_results", None)
    asv_absent = _no_shear_steel_inputs()
    has_zone_payload = isinstance(sz, dict) and (bool(sz.get("zones")) or bool(sz.get("strip_segments_mm")))
    zones_enabled = bool(get_param("shear_zone_enabled", True))
    show_zoned_mode = zones_enabled and has_zone_payload
    if shear_fails and not show_zoned_mode:
        diagram_mode_label = "Required shear reinforcement (zoned layout unavailable)"
    elif shear_fails and show_zoned_mode:
        diagram_mode_label = "Required shear reinforcement (zoned)"
    elif show_zoned_mode:
        diagram_mode_label = "Provided shear reinforcement (Check 10 layout)"
    else:
        diagram_mode_label = "Provided shear reinforcement"

    beam_depth_m = model["D_m"]
    y0 = 0.10 * beam_depth_m
    y1 = 0.90 * beam_depth_m
    y_mid = 0.5 * (y0 + y1)
    label_y = -0.26 * beam_depth_m
    note_y = -0.34 * beam_depth_m
    length_m = max(model["total_length_m"], 0.0)

    work_model = dict(model)
    if not work_model.get("side_view_display"):
        work_model["side_view_display"] = _side_view_display_state(model)
    display_length_m = max(
        _safe_float(work_model["side_view_display"].get("display_length_m", model["total_length_m"]), model["total_length_m"]),
        0.1,
    )

    stirrup_tuples: list[tuple[float, float]] = []
    zones_scaled: list[dict[str, Any]] = []

    if show_zoned_mode and isinstance(sz, dict):
        zones_scaled = _zones_metres_scaled_for_side_view(sz, model)
        _s_mm = max(float(model.get("spacing_mm", 0.0) or 0.0), 0.0)
        _s_global_m = _s_mm / 1000.0 if _s_mm > 0.0 else 0.15
        stirrup_tuples = _stirrup_tuples_from_zones(
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
            xa = _side_view_display_x(zs, work_model)
            xb = _side_view_display_x(ze, work_model)
            fill = z.get("fillcolor") or _SHEAR_ZONE_SIDE_VIEW_FILLS[i % len(_SHEAR_ZONE_SIDE_VIEW_FILLS)]
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
            xmid_d = _side_view_display_x(xmid_r, work_model)
            sm_mm = int(round(max(float(z.get("spacing", 0.0) or 0.0), 0.0) * 1000.0))
            zlbl = str(z.get("label") or "").strip()
            ann_txt = f"{zlbl} @ {sm_mm} mm" if zlbl else f"@ {sm_mm} mm"
            fig.add_annotation(
                x=xmid_d,
                y=beam_depth_m + 0.05 * beam_depth_m,
                text=ann_txt,
                showarrow=False,
                font=dict(size=10, color="rgba(40,40,40,0.95)"),
            )
    elif not show_zoned_mode:
        stirrup_tuples = _stirrup_tuples_uniform(model)

    if stirrup_tuples:
        reals = [t[0] for t in stirrup_tuples]
        r2s = {t[0]: t[1] for t in stirrup_tuples}
        min_sp = max(0.025 * display_length_m, 0.06 * beam_depth_m)
        if show_zoned_mode:
            _xd_sorted = sorted(_side_view_display_x(r, work_model) for r in reals)
            eps = max(1e-5 * display_length_m, 1e-6)
            display_xs = []
            for _xd in _xd_sorted:
                if not display_xs or _xd - display_xs[-1] >= eps:
                    display_xs.append(_xd)
        else:
            display_xs = _side_view_display_positions(reals, work_model, min_spacing=min_sp)

        def _spacing_mm_for_display_x(xd: float) -> int:
            best_r = min(reals, key=lambda r: abs(_side_view_display_x(r, work_model) - xd))
            return int(round(max(r2s.get(best_r, 0.0), 0.0) * 1000.0))

        for xd in display_xs:
            fig.add_shape(
                type="line",
                x0=xd,
                y0=y0,
                x1=xd,
                y1=y1,
                line=dict(color="rgba(0,0,0,0.85)", width=1.2),
            )
        fig.add_trace(
            go.Scatter(
                x=display_xs,
                y=[y_mid] * len(display_xs),
                mode="markers",
                marker=dict(size=10, opacity=0, color="rgba(0,0,0,0)"),
                hovertext=[f"Spacing: {_spacing_mm_for_display_x(xd)} mm" for xd in display_xs],
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
                font=dict(size=11, color="rgba(0,0,0,0.95)"),
            )
        else:
            _sub = f"s = {model['spacing_mm']:.0f} mm"
            fig.add_annotation(
                x=display_length_m / 2.0,
                y=label_y,
                text=f"{diagram_mode_label} — {_sub}",
                showarrow=False,
                font=dict(size=11, color="rgba(0,0,0,0.95)"),
            )
    elif show_zoned_mode:
        fig.add_annotation(
            x=display_length_m / 2.0,
            y=label_y,
            text=diagram_mode_label,
            showarrow=False,
            font=dict(size=11, color="rgba(100,100,100,0.9)"),
        )
        fig.add_annotation(
            x=display_length_m / 2.0,
            y=note_y,
            text="No stirrup positions in zone layout — check span and demands",
            showarrow=False,
            font=dict(size=9, color="rgba(70,70,70,0.9)"),
        )
    elif asv_absent:
        fig.add_annotation(
            x=display_length_m / 2.0,
            y=label_y,
            text="No shear reinforcement provided",
            showarrow=False,
            font=dict(size=11, color="rgba(100,100,100,0.85)"),
        )
    else:
        fig.add_annotation(
            x=display_length_m / 2.0,
            y=label_y,
            text="Link spacing not set",
            showarrow=False,
            font=dict(size=11, color="rgba(100,100,100,0.85)"),
        )


def _build_side_view_tension_reo(fig: go.Figure, model: dict[str, Any]) -> None:
    bottom_layers = model.get("bottom_layers", []) or []
    top_layers = model.get("top_layers", []) or []
    if not bottom_layers and not top_layers:
        return
    beam_depth_m = model["D_m"]
    bottom_base_y = 0.11 * beam_depth_m
    top_base_y = 0.89 * beam_depth_m
    x_start = _side_view_display_x(0.05 * model["total_length_m"], model)
    x_end = _side_view_display_x(0.95 * model["total_length_m"], model)

    for idx, layer in enumerate(bottom_layers[:2]):
        db = max(_safe_float(layer.get("db", 20.0), 20.0), 10.0)
        y_val = min(bottom_base_y + idx * 0.07 * beam_depth_m, 0.85 * beam_depth_m)
        fig.add_trace(
            go.Scatter(
                x=[x_start, x_end],
                y=[y_val, y_val],
                mode="lines",
                line=dict(color="rgba(0,90,200,0.95)", width=max(2.0, min(4.5, db / 6.0))),
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
                line=dict(color="rgba(200,45,45,0.95)", width=max(2.0, min(4.5, db / 6.0))),
                hoverinfo="skip",
                showlegend=False,
            )
        )

    if bottom_layers:
        fig.add_annotation(
            x=_side_view_display_x(0.82 * model["total_length_m"], model),
            y=min(bottom_base_y + 0.04 * beam_depth_m, 0.90 * beam_depth_m),
            text="Tension reo",
            showarrow=False,
            font=dict(size=10, color="rgba(0,90,200,0.95)"),
        )
    if top_layers:
        _side_sec = str(st.session_state.get("sec_shape", get_param("sec_shape", "RECT")) or "RECT")
        _, _side_top_lbl = main_longitudinal_reo_pair_labels(_side_sec, variant="inputs_compact")
        fig.add_annotation(
            x=_side_view_display_x(0.22 * model["total_length_m"], model),
            y=max(top_base_y - 0.04 * beam_depth_m, 0.10 * beam_depth_m),
            text=_side_top_lbl,
            showarrow=False,
            font=dict(size=10, color="rgba(200,45,45,0.95)"),
        )


def _add_section_marker(fig: go.Figure, model: dict[str, Any]) -> None:
    x_pos = model.get("section_x_m")
    if x_pos is None:
        return
    beam_depth_m = model["D_m"]
    fig.add_shape(type="line", x0=x_pos, y0=-0.12 * beam_depth_m, x1=x_pos, y1=1.20 * beam_depth_m, line=dict(color="rgba(46,125,50,0.9)", width=1.4, dash="dash"))
    fig.add_annotation(x=x_pos, y=1.25 * beam_depth_m, text="Section", showarrow=False, font=dict(size=10, color="rgba(46,125,50,0.9)"))


def _display_zone_length(model: dict[str, Any]) -> float:
    return max(model["d_m"], 0.0)


def _support_d_region_bounds(model: dict[str, Any]) -> tuple[float, float]:
    beam_length = model["total_length_m"]
    d_region_len = min(max(model["d_m"], 0.0), beam_length * 0.42)
    left_end = min(d_region_len, beam_length)
    right_start = max(beam_length - d_region_len, 0.0)
    return (left_end, right_start)


def _shear_crack_x_band_m(model: dict[str, Any]) -> tuple[float, float]:
    """
    Horizontal band (m) where principal shear cracks should be drawn: flexural–shear zone only,
    outside D-regions (same extent as zone shading from _support_d_region_bounds).
    """
    beam_length = max(_safe_float(model.get("total_length_m", model.get("span_m", 0.0)), 0.0), 0.1)
    d_m = max(_safe_float(model.get("d_m", 0.0), 0.0), 1e-6)
    if d_m < 1e-3:
        d_m = max(0.06 * beam_length, 1e-3)
    m_probe = dict(model)
    m_probe["total_length_m"] = beam_length
    m_probe["d_m"] = d_m
    left_d_end, right_d_start = _support_d_region_bounds(m_probe)
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


# STM inner-node snapping: clean proportions of d_v / D-region width; θ_v remains exact after each adjustment.
_STM_SNAP_X_RATIOS: tuple[float, ...] = (0.6, 0.7, 0.8, 0.9)
_STM_SNAP_Y_DV_FRACS: tuple[float, ...] = (0.85, 0.9, 0.95)


def _stm_snap_ratio_to_grid(r_raw: float) -> float:
    r = min(max(r_raw, 0.55), 0.95)
    return min(_STM_SNAP_X_RATIOS, key=lambda s: abs(s - r))


def _stm_y_snap_levels_dv(
    d_v_m: float,
    beam_depth_m: float,
    bottom_tie_y: float,
) -> list[float]:
    y_hi = beam_depth_m - max(0.004, beam_depth_m * 0.02)
    levels = [frac * d_v_m for frac in _STM_SNAP_Y_DV_FRACS]
    return [y for y in levels if y > bottom_tie_y + 1e-9 and y < y_hi - 1e-9]


def _stm_snap_inner_top_left(
    x_bot: float,
    bottom_tie_y: float,
    d_region_width: float,
    tan_th: float,
    d_v_m: float,
    beam_depth_m: float,
    node_pad: float,
    dy_nom: float,
) -> tuple[float, float]:
    """
    Left support D-region (x_support = 0): snap horizontal fraction of D width, then snap y to d_v grid,
    then re-solve x for θ_v and clamp x to the D boundary (recompute y if clamped).
    """
    D_w = max(float(d_region_width), 1e-12)
    x_top_cand = x_bot + dy_nom / tan_th
    r_raw = (x_top_cand - 0.0) / D_w
    r_snap = _stm_snap_ratio_to_grid(r_raw)
    x_top = min(max(r_snap * D_w, x_bot + node_pad), D_w)
    dy = (x_top - x_bot) * tan_th
    y_top = bottom_tie_y + dy

    y_targets = _stm_y_snap_levels_dv(d_v_m, beam_depth_m, bottom_tie_y)
    if y_targets:
        y_snap = min(y_targets, key=lambda yt: abs(yt - y_top))
        y_top = y_snap
        x_top = x_bot + (y_top - bottom_tie_y) / tan_th
        if x_top > D_w:
            x_top = D_w
            y_top = bottom_tie_y + (x_top - x_bot) * tan_th
        elif x_top < x_bot + node_pad:
            x_top = x_bot + node_pad
            y_top = bottom_tie_y + (x_top - x_bot) * tan_th

    return x_top, y_top


def _stm_snap_inner_top_right(
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
    """Right support D-region measured from span end; same snapping policy as left."""
    D_w = max(span_m - float(right_d_start), 1e-12)
    x_top_cand = x_bot - dy_nom / tan_th
    r_raw = (span_m - x_top_cand) / D_w
    r_snap = _stm_snap_ratio_to_grid(r_raw)
    x_top = max(min(span_m - r_snap * D_w, x_bot - node_pad), right_d_start)
    dy = (x_bot - x_top) * tan_th
    y_top = bottom_tie_y + dy

    y_targets = _stm_y_snap_levels_dv(d_v_m, beam_depth_m, bottom_tie_y)
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


def _build_shear_behaviour_zones(fig: go.Figure, model: dict[str, Any], case_kind: str) -> None:
    beam_length = model["total_length_m"]
    beam_depth_m = model["D_m"]
    left_d_end, right_d_start = _support_d_region_bounds(model)

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


def _sample_beam_y(sample_y: float, beam_depth_scale: float = 1.0) -> float:
    sample_beam_height = 0.30
    return sample_y * (beam_depth_scale / sample_beam_height)


def _beam_depth_scale(model: dict[str, Any]) -> float:
    return max(_safe_float(model.get("D_m", 0.6), 0.6), 0.1)


def _field_y_limits(beam_depth_m: float = 0.6) -> tuple[float, float]:
    pad = max(0.004, beam_depth_m * 0.02)
    return (0.0 + pad, beam_depth_m - pad)


def _clamp_field_points(points: list[tuple[float, float]], beam_depth_m: float = 0.6) -> list[tuple[float, float]]:
    y_min, y_max = _field_y_limits(beam_depth_m)
    return [(x_val, min(max(y_val, y_min), y_max)) for x_val, y_val in points]


def _add_force_line(
    fig: go.Figure,
    points: list[tuple[float, float]],
    color: str,
    width: float,
    label: str | None = None,
    label_pos: tuple[float, float] | None = None,
    opacity: float = 1.0,
    clamp_to_field: bool = True,
    smoothing: float = _FIELD_SPLINE_SMOOTHING,
    beam_depth_m: float = 0.6,
    line_shape: str = "spline",
) -> None:
    plot_points = _clamp_field_points(points, beam_depth_m) if clamp_to_field else points
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


def _field_line_spec(
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


def _mirror_field_line(spec: dict[str, Any], span_m: float) -> dict[str, Any]:
    label_pos = spec.get("label_pos")
    return {
        **spec,
        "points": [(span_m - x_val, y_val) for x_val, y_val in spec["points"]],
        "label_pos": None if label_pos is None else (span_m - label_pos[0], label_pos[1]),
    }


def _build_tension_family(fig: go.Figure, lines: list[dict[str, Any]]) -> None:
    blue = "rgba(0,90,200,0.94)"
    for line in lines:
        _add_force_line(
            fig,
            line["points"],
            blue,
            line["width"],
            label=line.get("label"),
            label_pos=line.get("label_pos"),
            opacity=line.get("opacity", 1.0),
            smoothing=line.get("smoothing", _FIELD_SPLINE_SMOOTHING),
        )


def _build_compression_family(fig: go.Figure, lines: list[dict[str, Any]]) -> None:
    red = "rgba(200,45,45,0.94)"
    for line in lines:
        _add_force_line(
            fig,
            line["points"],
            red,
            line["width"],
            label=line.get("label"),
            label_pos=line.get("label_pos"),
            opacity=line.get("opacity", 1.0),
            smoothing=line.get("smoothing", _FIELD_SPLINE_SMOOTHING),
        )


def _build_crack_cues(fig: go.Figure, cracks: list[dict[str, Any]]) -> None:
    crack_color = "rgba(20,20,20,0.88)"
    for crack in cracks:
        _add_force_line(
            fig,
            crack["points"],
            crack_color,
            crack["width"],
            label=crack.get("label"),
            label_pos=crack.get("label_pos"),
            opacity=crack.get("opacity", 1.0),
            smoothing=crack.get("smoothing", _FIELD_SPLINE_SMOOTHING),
        )


def _add_trajectory_family(
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
        _add_force_line(
            fig,
            pts,
            color,
            width,
            opacity=opacity,
            smoothing=smoothing,
            beam_depth_m=beam_depth_m,
        )


def _scaled_rgba_alpha(color: str, alpha_scale: float) -> str:
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


def _trajectory_visual_weight(line_idx: int, line_count: int) -> tuple[float, float]:
    if line_count <= 1:
        return (1.0, 1.0)
    t = line_idx / (line_count - 1)
    emphasis = t ** 1.15
    opacity_scale = 1.0 - 0.42 * emphasis
    width_scale = 1.02 - 0.08 * (t ** 1.05)
    return (width_scale, opacity_scale)


def _sample_curve_point_and_tangent(
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


def _add_trajectory_direction_arrow(
    fig: go.Figure,
    pts: list[tuple[float, float]],
    color: str,
    *,
    beam_depth_m: float,
    curve_fraction: float,
    alpha_scale: float,
    reverse: bool = False,
) -> None:
    sample = _sample_curve_point_and_tangent(pts, curve_fraction)
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
        arrowcolor=_scaled_rgba_alpha(color, alpha_scale),
    )


def _add_sparse_trajectory_arrows(
    fig: go.Figure,
    lines: list[list[tuple[float, float]]],
    color: str,
    *,
    beam_depth_m: float,
) -> None:
    if not lines:
        return
    line_idx = min(max(1, len(lines) // 3), len(lines) - 1)
    _, opacity_scale = _trajectory_visual_weight(line_idx, len(lines))
    for curve_fraction in (0.34, 0.66):
        _add_trajectory_direction_arrow(
            fig,
            lines[line_idx],
            color,
            beam_depth_m=beam_depth_m,
            curve_fraction=curve_fraction,
            alpha_scale=opacity_scale * 0.72,
        )


def _add_load_flow_overlay(
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
                    color=_scaled_rgba_alpha(color, 0.95),
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
                            color=_scaled_rgba_alpha(color, 1.0),
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
            _add_trajectory_direction_arrow(
                fig,
                pts,
                color,
                beam_depth_m=beam_depth_m,
                curve_fraction=0.30,
                alpha_scale=0.98,
                reverse=True,
            )
            _add_trajectory_direction_arrow(
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
                _add_trajectory_direction_arrow(
                    fig,
                    pts,
                    color,
                    beam_depth_m=beam_depth_m,
                    curve_fraction=curve_fraction,
                    alpha_scale=0.92,
                )


def _stm_visual_context_active(model: dict[str, Any]) -> bool:
    return bool(model.get("show_stm_overlay", False) or model.get("show_stm_flow", False))


def _linear_interpolate_points(
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


def _densify_polyline(
    pts: list[tuple[float, float]],
    *,
    n_per_seg: int = 16,
) -> list[tuple[float, float]]:
    if len(pts) < 2:
        return [(float(a[0]), float(a[1])) for a in pts]
    out: list[tuple[float, float]] = []
    for i in range(len(pts) - 1):
        seg = _linear_interpolate_points(pts[i], pts[i + 1], n=n_per_seg)
        if out:
            out.extend(seg[1:])
        else:
            out.extend(seg)
    return out


def _add_stm_flow_polyline(
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
    dense = _densify_polyline(pts, n_per_seg=18)
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
                color=_scaled_rgba_alpha(color, 0.58),
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
                    color=_scaled_rgba_alpha(color, 0.98),
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
        _add_trajectory_direction_arrow(
            fig,
            dense,
            color,
            beam_depth_m=beam_depth_m,
            curve_fraction=curve_fraction,
            alpha_scale=0.94,
        )


def _render_stm_flow_overlay(fig: go.Figure, model: dict[str, Any], case_kind: str) -> None:
    if not bool(model.get("show_stm_flow", False)):
        return
    beam_depth_m = _beam_depth_scale(model)
    red = "rgba(210,50,50,0.96)"
    blue = "rgba(0,95,215,0.96)"

    def _ss_flow() -> None:
        g = _compute_stm_simply_supported_d_region_nodes(model)
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
        # Compression: flexural region → top inner node, along D-region chord toward bearing, down strut to support.
        _add_stm_flow_polyline(fig, [tli, tlo], red, beam_depth_m=beam_depth_m)
        _add_stm_flow_polyline(fig, [tli, bl], red, beam_depth_m=beam_depth_m)
        _add_stm_flow_polyline(fig, [(bl[0], bottom_tie_y), (bl[0], y_tli)], red, beam_depth_m=beam_depth_m)
        _add_stm_flow_polyline(fig, [tri, tro], red, beam_depth_m=beam_depth_m)
        _add_stm_flow_polyline(fig, [tri, br], red, beam_depth_m=beam_depth_m)
        _add_stm_flow_polyline(fig, [(br[0], bottom_tie_y), (br[0], y_tri)], red, beam_depth_m=beam_depth_m)
        # Tension tie: horizontal pull from each support node along the continuous bottom steel toward midspan.
        _add_stm_flow_polyline(fig, [bl, (mid_x, bottom_tie_y)], blue, beam_depth_m=beam_depth_m)
        _add_stm_flow_polyline(fig, [br, (mid_x, bottom_tie_y)], blue, beam_depth_m=beam_depth_m)

    if case_kind in {
        "ss_midspan_point",
        "ss_udl",
        "ss_near_support_point",
        "ss_eccentric_point",
    }:
        _ss_flow()
        return
    if case_kind in {"cantilever_tip", "cantilever_udl", "cantilever_eccentric"}:
        g = _compute_stm_cantilever_d_region_nodes(model)
        if g is None:
            return
        span_m = float(g["span_m"])
        bottom_tie_y = g["bottom_tie_y"]
        top_y = g["top_y"]
        y_tin = float(g.get("y_top_in", top_y))
        bot = (g["x_bot_out"], bottom_tie_y)
        tout, tin = (g["x_bot_out"], y_tin), (g["x_top_in"], y_tin)
        tie_end = (max(min(span_m * 0.90, span_m - 0.04 * span_m), bot[0] + 0.08 * span_m), bottom_tie_y)
        _add_stm_flow_polyline(fig, [tin, tout], red, beam_depth_m=beam_depth_m)
        _add_stm_flow_polyline(fig, [tin, bot], red, beam_depth_m=beam_depth_m)
        _add_stm_flow_polyline(fig, [(bot[0], bottom_tie_y), (bot[0], y_tin)], red, beam_depth_m=beam_depth_m)
        _add_stm_flow_polyline(fig, [bot, tie_end], blue, beam_depth_m=beam_depth_m)
        return

    _ss_flow()


def _blend_x(span_m: float, frac: float) -> float:
    return frac * span_m


def _parabolic_trajectory(
    x0: float,
    x1: float,
    y_end: float,
    y_peak: float,
    n: int = 9,
) -> list[tuple[float, float]]:
    """
    Symmetric parabola-like trajectory from x0 to x1.
    Ends at y_end, peaks at y_peak at midspan.
    """
    pts: list[tuple[float, float]] = []
    for i in range(n):
        t = i / (n - 1)
        x = x0 + t * (x1 - x0)
        shape = (4.0 * t * (1.0 - t)) ** 0.7
        y = y_end + (y_peak - y_end) * shape
        pts.append((x, y))
    return pts


def _symmetric_arch(
    x0: float,
    x1: float,
    y_end: float,
    y_mid: float,
    *,
    n: int = 21,
    sharpness: float = 0.78,
    end_curvature_boost: float = 1.22,
) -> list[tuple[float, float]]:
    """
    Single smooth symmetric arch from x0 to x1.
    If y_end > y_mid -> upward arch (lowest at midspan).
    If y_end < y_mid -> downward arch (highest at midspan).
    """
    pts: list[tuple[float, float]] = []
    for i in range(n):
        t = i / (n - 1)
        x = x0 + t * (x1 - x0)
        base_shape = (4.0 * t * (1.0 - t)) ** sharpness
        shape = 1.0 - (1.0 - base_shape) ** end_curvature_boost
        y = y_end + (y_mid - y_end) * shape
        pts.append((x, y))
    return pts


def _mirror_trajectory_about_middepth(
    pts: list[tuple[float, float]],
    beam_depth_m: float,
) -> list[tuple[float, float]]:
    return [(x, beam_depth_m - y) for x, y in pts]


def _support_zone_x_left() -> float:
    return 0.0


def _support_zone_x_right(span_m: float) -> float:
    return span_m


def _support_edge_y_top(beam_depth_m: float) -> float:
    return beam_depth_m - max(0.004, beam_depth_m * 0.02)


def _support_edge_y_bot(beam_depth_m: float) -> float:
    return max(0.004, beam_depth_m * 0.02)


def _add_strut_tie_node(fig: go.Figure, x: float, y: float) -> None:
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


def _add_stm_member(
    fig: go.Figure,
    start: tuple[float, float],
    end: tuple[float, float],
    color: str,
    width: float,
    *,
    opacity: float = 1.0,
    beam_depth_m: float = 0.6,
) -> None:
    _add_force_line(
        fig,
        [start, end],
        color,
        width,
        opacity=opacity,
        smoothing=0.0,
        beam_depth_m=beam_depth_m,
        line_shape="linear",
    )


def _add_stm_axis_vertical(
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
    _add_force_line(
        fig,
        [(x, ya), (x, yb)],
        color,
        width,
        opacity=opacity,
        smoothing=0.0,
        beam_depth_m=beam_depth_m,
        line_shape="linear",
    )


def _current_mcft_theta_v_deg() -> float:
    return _safe_float(
        st.session_state.get(
            "crack_theta_deg",
            get_param("crack_theta_deg", st.session_state.get("theta_v_deg", get_param("theta_v_deg", 45.0))),
        ),
        45.0,
    )


def _add_principal_stress_orientation_square(
    fig: go.Figure,
    geometry: dict[str, float],
    *,
    principal_angle_deg: float,
    centre: tuple[float, float] | None = None,
) -> None:
    centre_x = centre[0] if centre is not None else geometry["centre_x"]
    centre_y = centre[1] if centre is not None else 0.52 * geometry["D_plot"]
    flexural_factor = min(max(geometry.get("flexural_width", geometry["L_plot"]) / max(geometry["L_plot"], 1e-9), 0.22), 0.86)
    half_side = (0.056 + 0.024 * flexural_factor) * geometry["D_plot"]
    mask_half_side = 1.22 * half_side
    principal_angle_rad = math.radians(principal_angle_deg)
    square_angle = principal_angle_rad + math.radians(20.0)

    def _rotate_local(dx: float, dy: float) -> tuple[float, float]:
        return (
            centre_x + dx * math.cos(square_angle) - dy * math.sin(square_angle),
            centre_y + dx * math.sin(square_angle) + dy * math.cos(square_angle),
        )

    line_angle_rad = principal_angle_rad + math.radians(20.0)
    sigma1_dir = (math.cos(line_angle_rad), math.sin(line_angle_rad))
    sigma2_dir = (-math.sin(line_angle_rad), math.cos(line_angle_rad))

    mask_pts = [
        _rotate_local(-mask_half_side, -mask_half_side),
        _rotate_local(mask_half_side, -mask_half_side),
        _rotate_local(mask_half_side, mask_half_side),
        _rotate_local(-mask_half_side, mask_half_side),
        _rotate_local(-mask_half_side, -mask_half_side),
    ]
    fig.add_trace(
        go.Scatter(
            x=[pt[0] for pt in mask_pts],
            y=[pt[1] for pt in mask_pts],
            mode="lines",
            line=dict(color="rgba(255,255,255,0.0)", width=0.0, shape="linear"),
            fill="toself",
            fillcolor="rgba(249,249,249,0.88)",
            hoverinfo="skip",
            showlegend=False,
        )
    )

    square_pts = [
        _rotate_local(-half_side, -half_side),
        _rotate_local(half_side, -half_side),
        _rotate_local(half_side, half_side),
        _rotate_local(-half_side, half_side),
        _rotate_local(-half_side, -half_side),
    ]
    fig.add_trace(
        go.Scatter(
            x=[pt[0] for pt in square_pts],
            y=[pt[1] for pt in square_pts],
            mode="lines",
            line=dict(color="rgba(95,95,95,0.90)", width=2.0, shape="linear"),
            hoverinfo="skip",
            showlegend=False,
        )
    )

    line_half_len = 1.38 * half_side
    sigma_specs = [
        (sigma1_dir, "rgba(200,45,45,0.92)"),
        (sigma2_dir, "rgba(0,90,200,0.92)"),
    ]
    for line_dir, color in sigma_specs:
        start_x = centre_x - line_half_len * line_dir[0]
        start_y = centre_y - line_half_len * line_dir[1]
        end_x = centre_x + line_half_len * line_dir[0]
        end_y = centre_y + line_half_len * line_dir[1]
        fig.add_trace(
            go.Scatter(
                x=[start_x, end_x],
                y=[start_y, end_y],
                mode="lines",
                line=dict(color=color, width=2.3, shape="linear"),
                hoverinfo="skip",
                showlegend=False,
            )
        )
        arrow_backoff = 0.10 * half_side
        fig.add_annotation(
            x=end_x,
            y=end_y,
            ax=end_x - arrow_backoff * line_dir[0],
            ay=end_y - arrow_backoff * line_dir[1],
            xref="x",
            yref="y",
            axref="x",
            ayref="y",
            text="",
            showarrow=True,
            arrowhead=2,
            arrowsize=0.95,
            arrowwidth=1.2,
            arrowcolor=color,
            opacity=0.90,
            standoff=0,
        )
        fig.add_annotation(
            x=start_x,
            y=start_y,
            ax=start_x + arrow_backoff * line_dir[0],
            ay=start_y + arrow_backoff * line_dir[1],
            xref="x",
            yref="y",
            axref="x",
            ayref="y",
            text="",
            showarrow=True,
            arrowhead=2,
            arrowsize=0.95,
            arrowwidth=1.2,
            arrowcolor=color,
            opacity=0.90,
            standoff=0,
        )

    marker_len = 0.22 * half_side
    right_angle_pts = [
        (
            centre_x + 0.18 * half_side * sigma1_dir[0],
            centre_y + 0.18 * half_side * sigma1_dir[1],
        ),
        (
            centre_x + 0.18 * half_side * sigma1_dir[0] + marker_len * sigma2_dir[0],
            centre_y + 0.18 * half_side * sigma1_dir[1] + marker_len * sigma2_dir[1],
        ),
        (
            centre_x + 0.18 * half_side * sigma2_dir[0],
            centre_y + 0.18 * half_side * sigma2_dir[1],
        ),
    ]
    fig.add_trace(
        go.Scatter(
            x=[pt[0] for pt in right_angle_pts],
            y=[pt[1] for pt in right_angle_pts],
            mode="lines",
            line=dict(color="rgba(95,95,95,0.56)", width=0.95, shape="linear"),
            hoverinfo="skip",
            showlegend=False,
        )
    )

def _segment_intersection(
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


def _polyline_polyline_best_hit(
    pc: list[tuple[float, float]],
    pt: list[tuple[float, float]],
    x_lo: float,
    x_hi: float,
) -> tuple[float, float, float, float, float, float] | None:
    """Rightmost segment-segment hit between two polylines within x ∈ [x_lo, x_hi]."""
    best_x = -1.0
    best: tuple[float, float, float, float, float, float] | None = None
    for i in range(len(pc) - 1):
        for j in range(len(pt) - 1):
            hit = _segment_intersection(pc[i], pc[i + 1], pt[j], pt[j + 1])
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


def _polyline_y_at_x(poly: list[tuple[float, float]], xq: float) -> float | None:
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


def _polyline_tangent_at_x(poly: list[tuple[float, float]], xq: float) -> tuple[float, float] | None:
    """Unnormalised tangent (dx, dy) on the segment that contains xq."""
    for i in range(len(poly) - 1):
        x0, y0 = poly[i]
        x1, y1 = poly[i + 1]
        xmin, xmax = min(x0, x1), max(x0, x1)
        if xmin - 1e-9 <= xq <= xmax + 1e-9:
            return (x1 - x0, y1 - y0)
    return None


def _polyline_segment_best_hit(
    poly: list[tuple[float, float]],
    s0: tuple[float, float],
    s1: tuple[float, float],
    x_lo: float,
    x_hi: float,
) -> tuple[float, float, float, float] | None:
    """Rightmost intersection of polyline with segment s0–s1 inside x band; returns px, py, tx, ty on poly."""
    best_x = -1.0
    best: tuple[float, float, float, float] | None = None
    for i in range(len(poly) - 1):
        hit = _segment_intersection(poly[i], poly[i + 1], s0, s1)
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


def _cantilever_principal_crack_hits(
    compression: list[list[tuple[float, float]]],
    tension: list[list[tuple[float, float]]],
    span_m: float,
    model: dict[str, Any],
) -> list[dict[str, float]]:
    """
    Cantilever-only: cracks at principal compression (red) × principal tension (blue) crossings
    in the free-end region; fallback to principal compression × STM strut if needed.
    """
    if len(compression) < 2 or len(tension) < 2:
        return []
    band_lo, band_hi = _shear_crack_x_band_m(model)
    x_lo = max(0.28 * span_m, band_lo)
    x_hi = min(0.93 * span_m, band_hi)
    if x_hi <= x_lo:
        x_lo, x_hi = band_lo, band_hi
        if x_hi <= x_lo:
            x_lo = min(band_lo, span_m * 0.92)
            x_hi = max(band_hi, x_lo + 1e-4 * span_m)
    raw: list[dict[str, float]] = []

    def _push_from_comp_tens(pc: list[tuple[float, float]], pt: list[tuple[float, float]]) -> None:
        hit = _polyline_polyline_best_hit(pc, pt, x_lo, x_hi)
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
        g = _compute_stm_cantilever_d_region_nodes(model)
        if g is not None:
            bot_out = (float(g["x_bot_out"]), float(g["bottom_tie_y"]))
            top_in = (float(g["x_top_in"]), float(g.get("y_top_in", g["top_y"])))
            hit = _polyline_segment_best_hit(compression[-1], bot_out, top_in, x_lo, x_hi)
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
        _cantilever_refine_crack_hit_for_compression_field(h, compression, span_m, x_lo=x_lo, x_hi=x_hi)
        for h in deduped[:2]
    ]


def _cantilever_refine_crack_hit_for_compression_field(
    h: dict[str, float],
    compression: list[list[tuple[float, float]]],
    span_m: float,
    *,
    x_lo: float,
    x_hi: float,
) -> dict[str, float]:
    """
    Shift hit right and vertically centre between two adjacent compression trajectories; align crack
    and stress-block rotation with local compression tangent + anti-clockwise offset. Stress block
    applies +20° internally, so principal_deg is reduced by 20° to match net orientation.
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
        yv = _polyline_y_at_x(curve, xq)
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
        t1 = _polyline_tangent_at_x(compression[ia], xq)
        t2 = _polyline_tangent_at_x(compression[ib], xq)
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
        t0 = _polyline_tangent_at_x(outer, xq) if outer else None
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


def _principal_stress_marker_state(
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
    outer_sample = _sample_curve_point_and_tangent(outer_comp, curve_fraction)
    inner_sample = _sample_curve_point_and_tangent(inner_comp, curve_fraction)
    if outer_sample is None or inner_sample is None:
        return None

    (outer_px, outer_py), (outer_tx, outer_ty) = outer_sample
    (inner_px, inner_py), (inner_tx, inner_ty) = inner_sample
    local_centre = (0.5 * (outer_px + inner_px), 0.5 * (outer_py + inner_py))

    support_side_fraction = max(curve_fraction - 0.06, 0.03)
    outer_dir_sample = _sample_curve_point_and_tangent(outer_comp, support_side_fraction)
    inner_dir_sample = _sample_curve_point_and_tangent(inner_comp, support_side_fraction)
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


def _add_principal_shear_crack_example(
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
        outer_sample = _sample_curve_point_and_tangent(outer_comp, curve_fraction)
        inner_sample = _sample_curve_point_and_tangent(inner_comp, curve_fraction)
        if outer_sample is None or inner_sample is None:
            return None

        (outer_px, outer_py), (outer_tx, outer_ty) = outer_sample
        (inner_px, inner_py), (inner_tx, inner_ty) = inner_sample
        px = 0.5 * (outer_px + inner_px)

        is_left_side = px <= beam_mid_x
        support_side_fraction = max(curve_fraction - 0.06, 0.03) if is_left_side else min(curve_fraction + 0.06, 0.97)
        outer_dir_sample = _sample_curve_point_and_tangent(outer_comp, support_side_fraction)
        inner_dir_sample = _sample_curve_point_and_tangent(inner_comp, support_side_fraction)
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
            outer_sample = _sample_curve_point_and_tangent(outer_comp, curve_fraction)
            inner_sample = _sample_curve_point_and_tangent(inner_comp, curve_fraction)
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
            _build_crack_cues(fig, crack_defs)
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
        _build_crack_cues(fig, crack_defs)


def _add_stm_joint_angle_annotation(
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


def _add_ordered_trajectory_family(
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
        width_scale, opacity_scale = _trajectory_visual_weight(idx, len(lines))
        _add_force_line(
            fig,
            pts,
            color,
            width * width_scale,
            opacity=opacity * opacity_scale,
            smoothing=smoothing,
            beam_depth_m=beam_depth_m,
            line_shape=line_shape,
        )


def _compute_stress_field_geometry(model: dict[str, Any]) -> dict[str, float]:
    L_plot = max(_safe_float(model.get("total_length_m", model.get("span_m", 0.0)), 0.0), 0.1)
    D_plot = _beam_depth_scale(model)
    d_plot = max(_safe_float(model.get("d_m", D_plot * 0.9), D_plot * 0.9), 1e-6)
    d6_actual = max(d_plot / 6.0, 0.0)
    zone_len = min(_display_zone_length(model), L_plot * 0.42)
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

    crack_x_lo, crack_x_hi = _shear_crack_x_band_m(model)

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


def _compute_trajectory_count(slenderness: float) -> int:
    unclamped = 4.0 + 1.15 * math.sqrt(max(slenderness - 2.5, 0.0))
    return max(4, min(7, int(round(unclamped))))


def _sample_anchor_band(count: int) -> list[float]:
    if count <= 1:
        return [1.0]
    samples: list[float] = []
    for idx in range(count):
        t = idx / (count - 1)
        eased = t ** 0.90
        relief = 0.05 * (1.0 - t) * t
        samples.append(min(1.0, max(0.0, eased + relief)))
    return samples


def _compute_trajectory_half_widths(geometry: dict[str, float], count: int) -> list[float]:
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

    width_progression = [sample ** 1.75 for sample in _sample_anchor_band(count)]
    return [
        inner_half_width + (outer_half_width - inner_half_width) * sample
        for sample in width_progression
    ]


def _trajectory_bow_scale(geometry: dict[str, float], width_factor: float) -> float:
    slenderness = geometry["slenderness"]
    slenderness_factor = min(max((slenderness - 7.0) / 9.0, 0.0), 1.0)
    outer_family_factor = width_factor ** 1.4
    base_scale = 1.0 - 0.12 * slenderness_factor * outer_family_factor
    return base_scale * geometry.get("bow_gain", 1.0)


def _trajectory_end_curvature_boost(geometry: dict[str, float], width_factor: float) -> float:
    slenderness_factor = min(max((geometry["slenderness"] - 5.5) / 8.5, 0.0), 1.0)
    outer_factor = width_factor ** 1.2
    base_boost = 1.42 + 0.34 * outer_factor + 0.16 * slenderness_factor
    return base_boost * geometry.get("end_curvature_gain", 1.0)


def _build_tensile_trajectories(geometry: dict[str, float], count: int) -> list[list[tuple[float, float]]]:
    widths = _compute_trajectory_half_widths(geometry, count)
    samples = _sample_anchor_band(count)
    lines: list[list[tuple[float, float]]] = []

    for width_factor, half_width in zip(samples, widths):
        x0 = geometry["centre_x"] - half_width
        x1 = geometry["centre_x"] + half_width
        y_end = geometry["top_anchor_y"] - 0.022 * geometry["D_plot"] * (width_factor ** 1.05)
        base_y_mid = geometry["tensile_apex_inner_y"] + (
            geometry["tensile_apex_outer_y"] - geometry["tensile_apex_inner_y"]
        ) * (width_factor ** 0.92)
        y_mid = y_end + (base_y_mid - y_end) * _trajectory_bow_scale(geometry, width_factor)
        sharpness = 1.08 - 0.10 * width_factor
        lines.append(
            _symmetric_arch(
                x0,
                x1,
                y_end,
                y_mid,
                n=25,
                sharpness=sharpness,
                end_curvature_boost=_trajectory_end_curvature_boost(geometry, width_factor),
            )
        )

    return lines


def _build_compressive_trajectories(geometry: dict[str, float], count: int) -> list[list[tuple[float, float]]]:
    widths = _compute_trajectory_half_widths(geometry, count)
    samples = _sample_anchor_band(count)
    lines: list[list[tuple[float, float]]] = []

    for width_factor, half_width in zip(samples, widths):
        x0 = geometry["centre_x"] - half_width
        x1 = geometry["centre_x"] + half_width
        y_end = geometry["bottom_anchor_y"] + 0.022 * geometry["D_plot"] * (width_factor ** 1.05)
        base_y_mid = geometry["compressive_apex_inner_y"] + (
            geometry["compressive_apex_outer_y"] - geometry["compressive_apex_inner_y"]
        ) * (width_factor ** 0.92)
        y_mid = y_end + (base_y_mid - y_end) * _trajectory_bow_scale(geometry, width_factor)
        sharpness = 1.08 - 0.10 * width_factor
        lines.append(
            _symmetric_arch(
                x0,
                x1,
                y_end,
                y_mid,
                n=25,
                sharpness=sharpness,
                end_curvature_boost=_trajectory_end_curvature_boost(geometry, width_factor),
            )
        )

    return lines


def _render_principal_stress_ss_udl(fig: go.Figure, model: dict[str, Any]) -> None:
    span_m = model["span_m"]
    geometry = _compute_stress_field_geometry(model)
    beam_depth_m = geometry["D_plot"]
    count = _compute_trajectory_count(geometry["slenderness"])
    theta_v_deg = _safe_float(model.get("theta_v_deg", _current_mcft_theta_v_deg()), _current_mcft_theta_v_deg())

    red = "rgba(200,45,45,0.82)"
    blue = "rgba(0,90,200,0.68)"
    show_load_flow = bool(model.get("show_load_flow", False))
    show_cracks = bool(model.get("show_cracks", True))
    show_stress_block = bool(model.get("show_stress_block", True))
    field_opacity_scale = 0.64 if _stm_visual_context_active(model) else 1.0

    tension = _build_tensile_trajectories(geometry, count)
    compression = _build_compressive_trajectories(geometry, count)

    # region agent log
    _dbg_log(
        "ss principal field inputs",
        {
            "case": model.get("case"),
            "span_m": round(span_m, 4),
            "beam_depth_m": round(beam_depth_m, 4),
            "slenderness": round(geometry["slenderness"], 4),
            "trajectory_count": count,
            "left_deep_limit": round(geometry["left_deep_limit"], 4),
            "right_deep_limit": round(geometry["right_deep_limit"], 4),
            "flexural_width": round(geometry["flexural_width"], 4),
            "half_widths": [round((curve[-1][0] - curve[0][0]) * 0.5, 4) for curve in tension],
        },
        hypothesis_id="H1",
    )
    _dbg_log(
        "ss principal field compression summary",
        {
            "curves": [
                {
                    "idx": idx,
                    "x0": round(curve[0][0], 4),
                    "xmid": round(curve[len(curve) // 2][0], 4),
                    "x1": round(curve[-1][0], 4),
                    "y0": round(curve[0][1], 4),
                    "ymid": round(curve[len(curve) // 2][1], 4),
                    "y1": round(curve[-1][1], 4),
                    "min_y": round(min(y for _, y in curve), 4),
                    "max_y": round(max(y for _, y in curve), 4),
                    "mid_relation": "mid_lower" if curve[len(curve) // 2][1] < curve[0][1] else "mid_higher",
                }
                for idx, curve in enumerate(compression)
            ]
        },
        hypothesis_id="H2",
    )
    _dbg_log(
        "ss principal field tension summary",
        {
            "curves": [
                {
                    "idx": idx,
                    "x0": round(curve[0][0], 4),
                    "xmid": round(curve[len(curve) // 2][0], 4),
                    "x1": round(curve[-1][0], 4),
                    "y0": round(curve[0][1], 4),
                    "ymid": round(curve[len(curve) // 2][1], 4),
                    "y1": round(curve[-1][1], 4),
                    "min_y": round(min(y for _, y in curve), 4),
                    "max_y": round(max(y for _, y in curve), 4),
                    "mid_relation": "mid_lower" if curve[len(curve) // 2][1] < curve[0][1] else "mid_higher",
                }
                for idx, curve in enumerate(tension)
            ]
        },
        hypothesis_id="H3",
    )
    _dbg_log(
        "ss principal field mirror check",
        {
            "max_abs_mirror_error": round(
                max(
                    abs(cy - (beam_depth_m - ty))
                    for ccurve, tcurve in zip(compression, tension)
                    for (_, cy), (_, ty) in zip(ccurve, tcurve)
                ),
                8,
            ),
            "smoothing": 0.64,
            "render_order": ["compression_red", "tension_blue"],
        },
        hypothesis_id="H4",
    )
    _dbg_log(
        "ss principal field curvature sample",
        {
            "tension": [
                {
                    "idx": idx,
                    "y_end": round(curve[0][1], 4),
                    "y_q1": round(curve[len(curve) // 4][1], 4),
                    "y_mid": round(curve[len(curve) // 2][1], 4),
                    "q1_to_mid_ratio": round(
                        abs(curve[len(curve) // 4][1] - curve[0][1])
                        / max(abs(curve[len(curve) // 2][1] - curve[0][1]), 1e-9),
                        4,
                    ),
                }
                for idx, curve in enumerate(tension)
            ]
        },
        hypothesis_id="H5",
    )
    # endregion

    _add_ordered_trajectory_family(
        fig,
        tension,
        blue,
        width=2.6,
        opacity=(0.46 if show_load_flow else 0.82) * field_opacity_scale,
        smoothing=0.64,
        beam_depth_m=beam_depth_m,
    )
    _add_ordered_trajectory_family(
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
        _add_load_flow_overlay(
            fig,
            compression,
            red,
            beam_depth_m=beam_depth_m,
            line_indices=compression_key_indices,
            outward_from_centre=True,
            animate_motion=True,
        )
        _add_load_flow_overlay(
            fig,
            tension,
            blue,
            beam_depth_m=beam_depth_m,
            line_indices=tension_key_indices,
            outward_from_centre=True,
            animate_motion=True,
        )

    marker_state = _principal_stress_marker_state(tension, compression, geometry)
    if show_stress_block:
        _add_principal_stress_orientation_square(
            fig,
            geometry,
            principal_angle_deg=marker_state[1] if marker_state is not None else theta_v_deg,
            centre=marker_state[0] if marker_state is not None else None,
        )
    if show_cracks:
        _add_principal_shear_crack_example(
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


def _render_principal_stress_ss_midspan_point(fig: go.Figure, model: dict[str, Any]) -> None:
    _render_principal_stress_ss_udl(fig, model)


def _render_principal_stress_ss_eccentric_point(fig: go.Figure, model: dict[str, Any]) -> None:
    _render_principal_stress_ss_udl(fig, model)


def _render_principal_stress_ss_near_support_point(fig: go.Figure, model: dict[str, Any]) -> None:
    _render_principal_stress_ss_udl(fig, model)


def _render_principal_stress_cantilever_tip(fig: go.Figure, model: dict[str, Any]) -> None:
    span_m = model["span_m"]
    depth_scale = _beam_depth_scale(model)
    d_plot = max(_safe_float(model.get("d_m", depth_scale * 0.9), depth_scale * 0.9), 1e-6)
    slenderness = span_m / max(d_plot, 1e-6)
    theta_v_deg = _safe_float(model.get("theta_v_deg", _current_mcft_theta_v_deg()), _current_mcft_theta_v_deg())

    red = "rgba(200,45,45,0.70)"
    blue = "rgba(0,90,200,0.58)"
    show_load_flow = bool(model.get("show_load_flow", False))
    show_cracks = bool(model.get("show_cracks", True))
    show_stress_block = bool(model.get("show_stress_block", True))
    field_opacity_scale = 0.64 if _stm_visual_context_active(model) else 1.0

    x_deep, x_transition = _cantilever_behaviour_zones(model)
    ratio_to_baseline = min(max(slenderness / (2000.0 / 350.0), 0.55), 1.80)
    shortness = min(max(((2000.0 / 350.0) - slenderness) / (2000.0 / 350.0), 0.0), 1.0)
    longness = min(max((slenderness - (2000.0 / 350.0)) / (2000.0 / 350.0), 0.0), 1.0)

    # Stronger support-side disturbed field for short cantilevers, softer for long.
    support_pull = min(max((1.0 / ratio_to_baseline) ** 0.45, 0.78), 1.42)
    support_band = min(max(x_deep * (1.05 + 0.18 * shortness), 0.10 * span_m), 0.42 * span_m)
    transition_span = max(x_transition - support_band, 0.10 * span_m)

    top_pad = _support_edge_y_top(depth_scale)
    bot_pad = _support_edge_y_bot(depth_scale)

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
        y_min, y_max = _field_y_limits(depth_scale)
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

    _add_ordered_trajectory_family(
        fig,
        compression,
        red,
        width=2.5,
        opacity=(0.40 if show_load_flow else 0.70) * field_opacity_scale,
        smoothing=0.0,
        beam_depth_m=depth_scale,
        line_shape="linear",
    )
    _add_ordered_trajectory_family(
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
        _add_load_flow_overlay(
            fig,
            compression,
            red,
            beam_depth_m=depth_scale,
            line_indices=[max(len(compression) - 2, 0), len(compression) - 1],
            outward_from_centre=True,
            animate_motion=True,
        )
        _add_load_flow_overlay(
            fig,
            tension,
            blue,
            beam_depth_m=depth_scale,
            line_indices=[max(len(tension) - 2, 0)],
            outward_from_centre=True,
            animate_motion=True,
        )

    crack_x_lo, crack_x_hi = _shear_crack_x_band_m(model)
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
    cantilever_hits = _cantilever_principal_crack_hits(compression, tension, span_m, model)
    geometry["cantilever_crack_hits"] = cantilever_hits

    marker_state = _principal_stress_marker_state(tension, compression, geometry)
    if show_stress_block:
        if cantilever_hits:
            h_block = cantilever_hits[1] if len(cantilever_hits) > 1 else cantilever_hits[0]
            sq_centre = (float(h_block["x"]), float(h_block["y"]))
            sq_angle = float(h_block["principal_deg"])
        else:
            sq_centre = marker_state[0] if marker_state is not None else None
            sq_angle = marker_state[1] if marker_state is not None else theta_v_deg
        _add_principal_stress_orientation_square(
            fig,
            geometry,
            principal_angle_deg=sq_angle,
            centre=sq_centre,
        )
    if show_cracks:
        _add_principal_shear_crack_example(
            fig,
            tension,
            compression,
            geometry,
            cantilever_mode=True,
        )

    fig.add_annotation(
        x=0.20 * span_m,
        y=_sample_beam_y(0.24, depth_scale),
        text="Compressive trajectories",
        showarrow=False,
        font=dict(size=11, color="rgba(200,45,45,0.95)"),
    )
    fig.add_annotation(
        x=0.24 * span_m,
        y=_sample_beam_y(-0.02, depth_scale),
        text="Tensile trajectories",
        showarrow=False,
        font=dict(size=11, color="rgba(0,90,200,0.95)"),
    )


def _render_principal_stress_cantilever_udl(fig: go.Figure, model: dict[str, Any]) -> None:
    _render_principal_stress_cantilever_tip(fig, model)


def _render_principal_stress_cantilever_eccentric(fig: go.Figure, model: dict[str, Any]) -> None:
    _render_principal_stress_cantilever_tip(fig, model)


def _compute_stm_simply_supported_d_region_nodes(
    model: dict[str, Any],
) -> dict[str, Any] | None:
    """
    D-region STM: bottom tie beam-wide; red struts at each support. Inner top nodes are snapped to
    clean fractions of d_v (vertical) and of D-region width (horizontal), then x/y are reconciled so
    strut angle equals θ_v exactly (clamp to D boundary recomputes the other coordinate).
    """
    span_m = max(_safe_float(model.get("span_m", model.get("total_length_m", 0.0)), 0.0), 0.1)
    beam_depth_m = _beam_depth_scale(model)
    left_d_end, right_d_start = _support_d_region_bounds(model)
    if left_d_end <= 1e-6 or right_d_start >= span_m - 1e-6 or right_d_start <= left_d_end + 1e-6:
        return None
    bottom_tie_y = _sample_beam_y(0.04, beam_depth_m)
    top_y_nom = _sample_beam_y(0.24, beam_depth_m)
    dy_nom = top_y_nom - bottom_tie_y
    if dy_nom <= 1e-12:
        return None

    d_v_m = max(_safe_float(model.get("d_m", beam_depth_m * 0.9), beam_depth_m * 0.9), 1e-6)

    theta_v_deg = _safe_float(model.get("theta_v_deg", _current_mcft_theta_v_deg()), _current_mcft_theta_v_deg())
    th = math.radians(max(1.0, min(float(theta_v_deg), 89.0)))
    tan_th = math.tan(th)
    if tan_th <= 1e-12:
        return None
    node_pad = max(1e-4 * beam_depth_m, 1e-6 * span_m)

    x_bot_out_L = min(0.12 * left_d_end, 0.05 * span_m)
    x_bot_out_L = max(x_bot_out_L, 0.02 * left_d_end)
    x_bot_out_L = min(x_bot_out_L, 0.42 * left_d_end)

    x_bot_out_R = span_m - x_bot_out_L

    x_top_in_L, y_top_in_L = _stm_snap_inner_top_left(
        x_bot_out_L,
        bottom_tie_y,
        float(left_d_end),
        tan_th,
        d_v_m,
        beam_depth_m,
        node_pad,
        dy_nom,
    )
    x_top_in_R, y_top_in_R = _stm_snap_inner_top_right(
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
        "theta_v_deg": float(theta_v_deg),
        "theta_stm_deg": float(theta_v_deg),
    }


def _compute_stm_cantilever_d_region_nodes(model: dict[str, Any]) -> dict[str, Any] | None:
    """D-region STM at fixed support; same d_v / D-width snapping as SS left strut; θ_v exact."""
    span_m = max(_safe_float(model.get("span_m", model.get("total_length_m", 0.0)), 0.0), 0.1)
    beam_depth_m = _beam_depth_scale(model)
    left_d_end, _ = _support_d_region_bounds(model)
    if left_d_end <= 1e-6:
        return None
    bottom_tie_y = _sample_beam_y(0.04, beam_depth_m)
    top_y_nom = _sample_beam_y(0.24, beam_depth_m)
    dy_nom = top_y_nom - bottom_tie_y
    if dy_nom <= 1e-12:
        return None

    d_v_m = max(_safe_float(model.get("d_m", beam_depth_m * 0.9), beam_depth_m * 0.9), 1e-6)

    theta_v_deg = _safe_float(model.get("theta_v_deg", _current_mcft_theta_v_deg()), _current_mcft_theta_v_deg())
    th = math.radians(max(1.0, min(float(theta_v_deg), 89.0)))
    tan_th = math.tan(th)
    if tan_th <= 1e-12:
        return None
    node_pad = max(1e-4 * beam_depth_m, 1e-6 * span_m)

    x_bot_out = min(0.12 * left_d_end, 0.05 * span_m)
    x_bot_out = max(x_bot_out, 0.02 * left_d_end)
    x_bot_out = min(x_bot_out, 0.42 * left_d_end)

    x_top_in, y_top_in = _stm_snap_inner_top_left(
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
        "theta_v_deg": float(theta_v_deg),
        "theta_stm_deg": float(theta_v_deg),
    }


def _render_strut_tie_ss_udl(fig: go.Figure, model: dict[str, Any], *, show_labels: bool = True) -> None:
    g = _compute_stm_simply_supported_d_region_nodes(model)
    if g is None:
        return

    span_m = g["span_m"]
    beam_depth_m = g["beam_depth_m"]
    bottom_tie_y = g["bottom_tie_y"]
    theta_v_lbl = float(g.get("theta_v_deg", g.get("theta_stm_deg", 45.0)))
    theta_text = f"θ<sub>v</sub> = {theta_v_lbl:.1f}°"

    red_main = "rgba(200,45,45,0.92)"
    red_faint = "rgba(200,45,45,0.40)"
    blue = "rgba(0,90,200,0.92)"

    bottom_left = (g["x_bot_out_L"], bottom_tie_y)
    bottom_right = (g["x_bot_out_R"], bottom_tie_y)
    y_top_in_L = float(g["y_top_in_L"])
    y_top_in_R = float(g["y_top_in_R"])
    # Horizontal compression chord meets the top of the vertical leg (same x as vertical, same y as inner).
    top_left_outer = (g["x_bot_out_L"], y_top_in_L)
    top_left_inner = (g["x_top_in_L"], y_top_in_L)
    top_right_inner = (g["x_top_in_R"], y_top_in_R)
    top_right_outer = (g["x_bot_out_R"], y_top_in_R)

    _add_stm_member(
        fig,
        (0.0, bottom_tie_y),
        (span_m, bottom_tie_y),
        blue,
        4.4,
        opacity=1.0,
        beam_depth_m=beam_depth_m,
    )
    _add_stm_axis_vertical(
        fig,
        bottom_left[0],
        bottom_tie_y,
        y_top_in_L,
        red_faint,
        2.8,
        opacity=0.72,
        beam_depth_m=beam_depth_m,
    )
    _add_stm_axis_vertical(
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
        _add_stm_member(fig, start, end, line_color, line_width, opacity=line_opacity, beam_depth_m=beam_depth_m)

    for node_x, node_y in (
        bottom_left,
        bottom_right,
        top_left_outer,
        top_left_inner,
        top_right_inner,
        top_right_outer,
    ):
        _add_strut_tie_node(fig, node_x, node_y)

    if bool(model.get("show_stm_overlay", False)):
        _add_stm_joint_angle_annotation(
            fig,
            bottom_left,
            (g["x_top_in_L"], y_top_in_L),
            theta_text,
            color="rgba(125,40,40,0.90)",
            beam_depth_m=beam_depth_m,
            tie_direction="right",
        )
        _add_stm_joint_angle_annotation(
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
            y=_sample_beam_y(0.31, beam_depth_m),
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


def _render_strut_tie_ss_midspan_point(fig: go.Figure, model: dict[str, Any], *, show_labels: bool = True) -> None:
    _render_strut_tie_ss_udl(fig, model, show_labels=show_labels)


def _render_strut_tie_ss_eccentric_point(fig: go.Figure, model: dict[str, Any], *, show_labels: bool = True) -> None:
    # Illustrative STM is D-region idealisation only (same dual D-region layout as UDL).
    _render_strut_tie_ss_udl(fig, model, show_labels=show_labels)


def _render_strut_tie_ss_near_support_point(fig: go.Figure, model: dict[str, Any], *, show_labels: bool = True) -> None:
    _render_strut_tie_ss_eccentric_point(fig, model, show_labels=show_labels)


def _render_strut_tie_cantilever_tip(fig: go.Figure, model: dict[str, Any], *, show_labels: bool = True) -> None:
    g = _compute_stm_cantilever_d_region_nodes(model)
    if g is None:
        return

    span_m = g["span_m"]
    beam_depth_m = g["beam_depth_m"]
    bottom_tie_y = g["bottom_tie_y"]
    theta_v_lbl = float(g.get("theta_v_deg", g.get("theta_stm_deg", 45.0)))
    theta_text = f"θ<sub>v</sub> = {theta_v_lbl:.1f}°"

    red_main = "rgba(200,45,45,0.92)"
    red_faint = "rgba(200,45,45,0.40)"
    blue = "rgba(0,90,200,0.92)"

    y_top_in = float(g["y_top_in"])
    bot_out = (g["x_bot_out"], bottom_tie_y)
    top_out = (g["x_bot_out"], y_top_in)
    top_in = (g["x_top_in"], y_top_in)

    _add_stm_member(
        fig,
        (0.0, bottom_tie_y),
        (span_m, bottom_tie_y),
        blue,
        4.4,
        opacity=1.0,
        beam_depth_m=beam_depth_m,
    )
    _add_stm_axis_vertical(
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
        _add_stm_member(fig, start, end, line_color, line_width, opacity=line_opacity, beam_depth_m=beam_depth_m)

    for node_x, node_y in (bot_out, top_out, top_in):
        _add_strut_tie_node(fig, node_x, node_y)

    if bool(model.get("show_stm_overlay", False)):
        _add_stm_joint_angle_annotation(
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
            y=_sample_beam_y(0.30, beam_depth_m),
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


def _render_strut_tie_cantilever_udl(fig: go.Figure, model: dict[str, Any], *, show_labels: bool = True) -> None:
    _render_strut_tie_cantilever_tip(fig, model, show_labels=show_labels)


def _render_strut_tie_cantilever_eccentric(fig: go.Figure, model: dict[str, Any], *, show_labels: bool = True) -> None:
    _render_strut_tie_cantilever_tip(fig, model, show_labels=show_labels)


def _render_stm_overlay(fig: go.Figure, model: dict[str, Any], case_kind: str) -> None:
    show_titles = bool(model.get("show_stm_overlay", False))
    if case_kind == "ss_midspan_point":
        _render_strut_tie_ss_midspan_point(fig, model, show_labels=False)
        if show_titles:
            _add_stm_overlay_labels(fig, model, case_kind)
        return
    if case_kind == "ss_udl":
        _render_strut_tie_ss_udl(fig, model, show_labels=False)
        if show_titles:
            _add_stm_overlay_labels(fig, model, case_kind)
        return
    if case_kind == "ss_near_support_point":
        _render_strut_tie_ss_near_support_point(fig, model, show_labels=False)
        if show_titles:
            _add_stm_overlay_labels(fig, model, case_kind)
        return
    if case_kind == "ss_eccentric_point":
        _render_strut_tie_ss_eccentric_point(fig, model, show_labels=False)
        if show_titles:
            _add_stm_overlay_labels(fig, model, case_kind)
        return
    if case_kind == "cantilever_tip":
        _render_strut_tie_cantilever_tip(fig, model, show_labels=False)
        if show_titles:
            _add_stm_overlay_labels(fig, model, case_kind)
        return
    if case_kind == "cantilever_udl":
        _render_strut_tie_cantilever_udl(fig, model, show_labels=False)
        if show_titles:
            _add_stm_overlay_labels(fig, model, case_kind)
        return
    if case_kind == "cantilever_eccentric":
        _render_strut_tie_cantilever_eccentric(fig, model, show_labels=False)
        if show_titles:
            _add_stm_overlay_labels(fig, model, case_kind)
        return
    _render_strut_tie_ss_udl(fig, model, show_labels=False)
    if show_titles:
        _add_stm_overlay_labels(fig, model, case_kind)


def _add_stm_overlay_labels(fig: go.Figure, model: dict[str, Any], case_kind: str) -> None:
    span_m = model["span_m"]
    beam_depth_m = _beam_depth_scale(model)
    red = "rgba(200,45,45,0.96)"
    blue = "rgba(0,90,200,0.96)"

    if case_kind in {
        "ss_midspan_point",
        "ss_udl",
        "ss_near_support_point",
        "ss_eccentric_point",
    }:
        g = _compute_stm_simply_supported_d_region_nodes(model)
        if g:
            bot_sup_L = (g["x_bot_out_L"], g["bottom_tie_y"])
            top_in_L = (g["x_top_in_L"], float(g.get("y_top_in_L", g["top_y"])))
            fig.add_annotation(
                x=0.55 * bot_sup_L[0] + 0.45 * top_in_L[0],
                y=0.55 * bot_sup_L[1] + 0.45 * top_in_L[1] + 0.04 * beam_depth_m,
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
        g = _compute_stm_cantilever_d_region_nodes(model)
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

    g_fallback = _compute_stm_simply_supported_d_region_nodes(model)
    if g_fallback:
        bot_sup_L = (g_fallback["x_bot_out_L"], g_fallback["bottom_tie_y"])
        top_in_L = (g_fallback["x_top_in_L"], float(g_fallback.get("y_top_in_L", g_fallback["top_y"])))
        fig.add_annotation(
            x=0.55 * bot_sup_L[0] + 0.45 * top_in_L[0],
            y=0.55 * bot_sup_L[1] + 0.45 * top_in_L[1] + 0.04 * beam_depth_m,
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
        y=_sample_beam_y(0.24, beam_depth_m),
        text="Compression strut",
        showarrow=False,
        font=dict(size=10, color=red),
        bgcolor="rgba(255,255,255,0.72)",
    )
    fig.add_annotation(
        x=0.50 * span_m,
        y=_sample_beam_y(-0.02, beam_depth_m),
        text="Tension tie",
        showarrow=False,
        font=dict(size=10, color=blue),
        bgcolor="rgba(255,255,255,0.72)",
    )


def _cantilever_behaviour_zones(model: dict[str, Any]) -> tuple[float, float]:
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


def _render_field_ss_midspan_point(fig: go.Figure, model: dict[str, Any]) -> None:
    span_m = model["span_m"]
    px = span_m / 2.0

    def _p(x_frac: float, sample_y: float) -> tuple[float, float]:
        return (span_m * x_frac, _sample_beam_y(sample_y))

    _build_compression_family(
        fig,
        [
            _field_line_spec([_p(0.08, 0.04), _p(0.22, 0.18), _p(0.38, 0.248), _p(0.46, 0.270), _p(0.54, 0.270), _p(0.62, 0.248), _p(0.78, 0.18), _p(0.92, 0.04)], width=3.4, opacity=0.30),
            _field_line_spec([_p(0.14, 0.04), _p(0.24, 0.15), _p(0.36, 0.226), _p(0.46, 0.246), _p(0.54, 0.246), _p(0.64, 0.226), _p(0.76, 0.15), _p(0.86, 0.04)], width=2.4, opacity=0.13),
            _field_line_spec([(px, _sample_beam_y(0.28)), _p(0.47, 0.282), _p(0.40, 0.281), _p(0.32, 0.280), _p(0.24, 0.246), _p(0.14, 0.140), _p(0.08, 0.060), _p(0.00, 0.000)], width=5, label="Compression", label_pos=_p(0.18, 0.44)),
            _field_line_spec([(px, _sample_beam_y(0.28)), _p(0.53, 0.282), _p(0.60, 0.281), _p(0.68, 0.280), _p(0.76, 0.246), _p(0.86, 0.140), _p(0.92, 0.060), _p(1.00, 0.000)], width=5),
            _field_line_spec([_p(0.12, 0.04), _p(0.22, 0.08), _p(0.30, 0.145), _p(0.38, 0.215), _p(0.44, 0.242)], width=2, opacity=0.18),
            _field_line_spec([_p(0.88, 0.04), _p(0.78, 0.08), _p(0.70, 0.145), _p(0.62, 0.215), _p(0.56, 0.242)], width=2, opacity=0.18),
        ],
    )
    _build_tension_family(
        fig,
        [
            _field_line_spec([_p(0.06, 0.230), _p(0.18, 0.072), _p(0.34, 0.042), _p(0.50, 0.054), _p(0.66, 0.042), _p(0.82, 0.072), _p(0.94, 0.230)], width=5, label="Tension", label_pos=_p(0.50, -0.13)),
            _field_line_spec([_p(0.10, 0.250), _p(0.22, 0.102), _p(0.36, 0.084), _p(0.50, 0.096), _p(0.64, 0.084), _p(0.78, 0.102), _p(0.90, 0.250)], width=3, opacity=0.22),
            _field_line_spec([_p(0.14, 0.265), _p(0.26, 0.132), _p(0.38, 0.108), _p(0.50, 0.118), _p(0.62, 0.108), _p(0.74, 0.132), _p(0.86, 0.265)], width=2, opacity=0.14),
        ],
    )
    _build_crack_cues(
        fig,
        [
            _field_line_spec([_p(0.20, 0.04), _p(0.27, 0.08), _p(0.33, 0.13)], width=2.2, opacity=0.86),
            _field_line_spec([_p(0.80, 0.04), _p(0.73, 0.08), _p(0.67, 0.13)], width=2.2, opacity=0.86),
        ],
    )


def _render_field_ss_udl(fig: go.Figure, model: dict[str, Any]) -> None:
    span_m = model["span_m"]

    def _p(x_frac: float, sample_y: float) -> tuple[float, float]:
        return (span_m * x_frac, _sample_beam_y(sample_y))

    _build_compression_family(
        fig,
        [
            _field_line_spec([_p(0.08, 0.05), _p(0.18, 0.215), _p(0.28, 0.262), _p(0.50, 0.276), _p(0.72, 0.262), _p(0.82, 0.215), _p(0.92, 0.05)], width=5, label="Compression", label_pos=_p(0.18, 0.44)),
            _field_line_spec([_p(0.10, 0.05), _p(0.20, 0.19), _p(0.30, 0.215), _p(0.50, 0.242), _p(0.70, 0.215), _p(0.80, 0.19), _p(0.90, 0.05)], width=3.0, opacity=0.24),
            _field_line_spec([_p(0.12, 0.05), _p(0.22, 0.13), _p(0.32, 0.17), _p(0.50, 0.20), _p(0.68, 0.17), _p(0.78, 0.13), _p(0.88, 0.05)], width=1.8, opacity=0.12),
        ],
    )
    _build_tension_family(
        fig,
        [
            _field_line_spec([_p(0.06, 0.015), _p(0.30, 0.022), _p(0.50, 0.034), _p(0.70, 0.022), _p(0.94, 0.015)], width=5, label="Tension", label_pos=_p(0.50, -0.13)),
            _field_line_spec([_p(0.10, 0.034), _p(0.20, 0.028), _p(0.30, 0.034), _p(0.50, 0.050), _p(0.70, 0.034), _p(0.80, 0.028), _p(0.90, 0.034)], width=2.6, opacity=0.22),
            _field_line_spec([_p(0.12, 0.060), _p(0.22, 0.048), _p(0.34, 0.052), _p(0.50, 0.066), _p(0.66, 0.052), _p(0.78, 0.048), _p(0.88, 0.060)], width=1.8, opacity=0.12),
        ],
    )
    _build_crack_cues(
        fig,
        [
            _field_line_spec([_p(0.12, 0.05), _p(0.18, 0.048), _p(0.23, 0.062), _p(0.28, 0.10)], width=2.6, label="Crack", label_pos=_p(0.22, 0.15)),
            _field_line_spec([_p(0.88, 0.05), _p(0.82, 0.047), _p(0.77, 0.060), _p(0.72, 0.10)], width=2.6),
        ],
    )


def _render_field_ss_eccentric_point(fig: go.Figure, model: dict[str, Any]) -> None:
    span_m = model["span_m"]
    load_x = max(0.0, min(model["a_m"], span_m))

    def _p(x_frac: float, sample_y: float) -> tuple[float, float]:
        return (span_m * x_frac, _sample_beam_y(sample_y))

    _build_compression_family(
        fig,
        [
            _field_line_spec([_p(0.08, 0.05), _p(0.18, 0.16), _p(0.26, 0.22), _p(0.46, 0.25), _p(0.72, 0.21), _p(0.82, 0.14), _p(0.92, 0.05)], width=3.0, opacity=0.24),
            _field_line_spec([(load_x, _sample_beam_y(0.28)), _p(0.24, 0.29), _p(0.12, 0.04)], width=5, label="Compression", label_pos=_p(0.18, 0.44)),
            _field_line_spec([(load_x, _sample_beam_y(0.28)), _p(0.58, 0.28), _p(0.84, 0.04)], width=4.2),
            _field_line_spec([_p(0.24, 0.04), _p(0.40, 0.22), (load_x, _sample_beam_y(0.21))], width=2, opacity=0.22),
            _field_line_spec([_p(0.08, 0.04), _p(0.16, 0.06), _p(0.28, 0.12), _p(0.40, 0.18), (load_x, _sample_beam_y(0.24))], width=1.6, opacity=0.14),
        ],
    )
    _build_tension_family(
        fig,
        [
            _field_line_spec([_p(0.06, 0.014), _p(0.24, 0.020), _p(0.46, 0.036), _p(0.72, 0.028), _p(0.94, 0.016)], width=5, label="Tension", label_pos=_p(0.52, -0.13)),
            _field_line_spec([_p(0.09, 0.038), _p(0.18, 0.030), _p(0.28, 0.036), _p(0.48, 0.058), _p(0.72, 0.046), _p(0.82, 0.034), _p(0.92, 0.042)], width=2.6, opacity=0.22),
            _field_line_spec([_p(0.12, 0.068), _p(0.22, 0.052), _p(0.30, 0.058), _p(0.48, 0.078), _p(0.68, 0.060), _p(0.78, 0.050), _p(0.88, 0.062)], width=1.8, opacity=0.12),
        ],
    )
    if load_x <= span_m / 2.0:
        cracks = [
            _field_line_spec([(span_m * 0.08, _sample_beam_y(0.05)), (span_m * 0.17, _sample_beam_y(0.04)), (max(load_x - 0.05 * span_m, span_m * 0.22), _sample_beam_y(0.12))], width=2.6, label="Crack", label_pos=_p(0.18, 0.16)),
            _field_line_spec([_p(0.84, 0.05), _p(0.79, 0.05), _p(0.72, 0.09)], width=1.9, opacity=0.50),
        ]
    else:
        cracks = [
            _field_line_spec([_p(0.16, 0.05), _p(0.21, 0.05), _p(0.28, 0.09)], width=1.9, opacity=0.50),
            _field_line_spec([(span_m * 0.92, _sample_beam_y(0.05)), (span_m * 0.83, _sample_beam_y(0.04)), (min(load_x + 0.05 * span_m, span_m * 0.78), _sample_beam_y(0.12))], width=2.6, label="Crack", label_pos=_p(0.80, 0.16)),
        ]
    _build_crack_cues(fig, cracks)


def _render_field_ss_near_support_point(fig: go.Figure, model: dict[str, Any]) -> None:
    span_m = model["span_m"]
    load_x = max(0.0, min(model["a_m"], span_m))
    load_left = load_x <= span_m / 2.0
    if not load_left:
        load_x = span_m - load_x

    def _p(x_frac: float, sample_y: float) -> tuple[float, float]:
        return (span_m * x_frac, _sample_beam_y(sample_y))

    tension = [
        _field_line_spec([_p(0.04, 0.016), _p(0.14, 0.022), _p(0.24, 0.038), _p(0.40, 0.058), _p(0.68, 0.044), _p(0.94, 0.018)], width=5, label="Tension", label_pos=_p(0.58, -0.13)),
        _field_line_spec([_p(0.06, 0.042), _p(0.16, 0.034), _p(0.28, 0.046), _p(0.44, 0.072), _p(0.66, 0.056), _p(0.90, 0.028)], width=2.6, opacity=0.22),
        _field_line_spec([_p(0.08, 0.070), _p(0.18, 0.054), _p(0.30, 0.064), _p(0.46, 0.090), _p(0.64, 0.066), _p(0.84, 0.040)], width=1.8, opacity=0.12),
    ]
    compression = [
        _field_line_spec([_p(0.06, 0.04), _p(0.16, 0.16), _p(0.26, 0.24), _p(0.46, 0.23), _p(0.72, 0.16), _p(0.92, 0.05)], width=3.0, opacity=0.24),
        _field_line_spec([(load_x, _sample_beam_y(0.28)), _p(0.26, 0.29), _p(0.18, 0.22), _p(0.10, 0.08), _p(0.00, 0.00)], width=5, label="Compression", label_pos=_p(0.18, 0.44)),
        _field_line_spec([(load_x, _sample_beam_y(0.27)), _p(0.40, 0.26), _p(0.60, 0.20), _p(0.86, 0.05)], width=4.0),
        _field_line_spec([_p(0.12, 0.04), _p(0.20, 0.09), _p(0.30, 0.17), (min(load_x, span_m * 0.34), _sample_beam_y(0.24))], width=1.8, opacity=0.18),
    ]
    cracks = [
        _field_line_spec([_p(0.08, 0.05), _p(0.15, 0.07), (max(load_x - 0.04 * span_m, span_m * 0.24), _sample_beam_y(0.13))], width=2.5, label="Crack", label_pos=_p(0.18, 0.16)),
        _field_line_spec([_p(0.78, 0.05), _p(0.72, 0.05), _p(0.64, 0.09)], width=1.8, opacity=0.40),
    ]
    if not load_left:
        tension = [_mirror_field_line(line, span_m) for line in tension]
        compression = [_mirror_field_line(line, span_m) for line in compression]
        cracks = [_mirror_field_line(line, span_m) for line in cracks]

    _build_compression_family(fig, compression)
    _build_tension_family(fig, tension)
    _build_crack_cues(fig, cracks)


def _render_field_cantilever_tip(fig: go.Figure, model: dict[str, Any]) -> None:
    span_m = model["span_m"]
    red = "rgba(200,45,45,0.94)"
    blue = "rgba(0,90,200,0.94)"
    crack_color = "rgba(20,20,20,0.88)"
    # Controlled transition for cantilever tip-load visual:
    # keep deep-beam action near support, then transition gradually.
    x_red_cross_start = 0.30 * span_m
    x_red_cross_end = 0.38 * span_m
    x_blue_cross_start = 0.32 * span_m
    x_blue_cross_end = 0.40 * span_m

    compression_label = (0.21 * span_m, _sample_beam_y(0.285))
    tension_label = (0.22 * span_m, _sample_beam_y(0.020))

    def _trace(points: list[tuple[float, float]], color: str, width: float, *, opacity: float = 1.0, smoothing: float = 0.9) -> None:
        plot_points = _clamp_field_points(points)
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

    # -----------------------------
    # Compression field (top near free end -> diagonal strut region -> softer top field)
    # -----------------------------
    main_red = [
        (0.02 * span_m, _sample_beam_y(0.285)),
        (0.05 * span_m, _sample_beam_y(0.272)),
        (0.09 * span_m, _sample_beam_y(0.248)),
        (0.14 * span_m, _sample_beam_y(0.215)),
        (0.20 * span_m, _sample_beam_y(0.182)),
        (0.27 * span_m, _sample_beam_y(0.165)),
        (x_red_cross_start, _sample_beam_y(0.148)),
        (x_red_cross_end,   _sample_beam_y(0.142)),
        (0.46 * span_m, _sample_beam_y(0.138)),
        (0.60 * span_m, _sample_beam_y(0.122)),
        (0.76 * span_m, _sample_beam_y(0.113)),
        (0.92 * span_m, _sample_beam_y(0.106)),
        (0.98 * span_m, _sample_beam_y(0.103)),
    ]
    comp_upper = [
        (0.03 * span_m, _sample_beam_y(0.255)),
        (0.07 * span_m, _sample_beam_y(0.242)),
        (0.11 * span_m, _sample_beam_y(0.220)),
        (0.17 * span_m, _sample_beam_y(0.190)),
        (0.24 * span_m, _sample_beam_y(0.158)),
        (x_red_cross_start, _sample_beam_y(0.152)),
        (x_red_cross_end,   _sample_beam_y(0.146)),
        (0.48 * span_m, _sample_beam_y(0.138)),
        (0.64 * span_m, _sample_beam_y(0.128)),
        (0.82 * span_m, _sample_beam_y(0.118)),
        (0.96 * span_m, _sample_beam_y(0.111)),
    ]
    comp_inner = [
        (0.04 * span_m, _sample_beam_y(0.228)),
        (0.08 * span_m, _sample_beam_y(0.215)),
        (0.13 * span_m, _sample_beam_y(0.196)),
        (0.19 * span_m, _sample_beam_y(0.176)),
        (0.26 * span_m, _sample_beam_y(0.160)),
        (x_red_cross_start, _sample_beam_y(0.150)),
        (x_red_cross_end,   _sample_beam_y(0.146)),
        (0.50 * span_m, _sample_beam_y(0.142)),
        (0.68 * span_m, _sample_beam_y(0.136)),
        (0.86 * span_m, _sample_beam_y(0.131)),
        (0.96 * span_m, _sample_beam_y(0.128)),
    ]

    # -----------------------------
    # Tension field (tie action near lower zone, developing gradually)
    # -----------------------------
    main_blue = [
        (0.02 * span_m, _sample_beam_y(0.070)),
        (0.05 * span_m, _sample_beam_y(0.078)),
        (0.09 * span_m, _sample_beam_y(0.092)),
        (0.14 * span_m, _sample_beam_y(0.108)),
        (0.20 * span_m, _sample_beam_y(0.124)),
        (0.27 * span_m, _sample_beam_y(0.136)),
        (x_blue_cross_start, _sample_beam_y(0.142)),
        (x_blue_cross_end,   _sample_beam_y(0.148)),
        (0.46 * span_m, _sample_beam_y(0.154)),
        (0.60 * span_m, _sample_beam_y(0.163)),
        (0.76 * span_m, _sample_beam_y(0.171)),
        (0.92 * span_m, _sample_beam_y(0.178)),
        (0.98 * span_m, _sample_beam_y(0.180)),
    ]
    tens_lower = [
        (0.03 * span_m, _sample_beam_y(0.090)),
        (0.07 * span_m, _sample_beam_y(0.098)),
        (0.11 * span_m, _sample_beam_y(0.108)),
        (0.17 * span_m, _sample_beam_y(0.120)),
        (0.24 * span_m, _sample_beam_y(0.138)),
        (x_blue_cross_start, _sample_beam_y(0.142)),
        (x_blue_cross_end,   _sample_beam_y(0.146)),
        (0.48 * span_m, _sample_beam_y(0.156)),
        (0.64 * span_m, _sample_beam_y(0.164)),
        (0.82 * span_m, _sample_beam_y(0.171)),
        (0.96 * span_m, _sample_beam_y(0.174)),
    ]
    tens_inner = [
        (0.04 * span_m, _sample_beam_y(0.110)),
        (0.08 * span_m, _sample_beam_y(0.116)),
        (0.13 * span_m, _sample_beam_y(0.124)),
        (0.19 * span_m, _sample_beam_y(0.132)),
        (0.26 * span_m, _sample_beam_y(0.139)),
        (x_blue_cross_start, _sample_beam_y(0.144)),
        (x_blue_cross_end,   _sample_beam_y(0.148)),
        (0.50 * span_m, _sample_beam_y(0.152)),
        (0.68 * span_m, _sample_beam_y(0.157)),
        (0.86 * span_m, _sample_beam_y(0.161)),
        (0.96 * span_m, _sample_beam_y(0.163)),
    ]

    # draw faint field first
    _trace(comp_upper, red, 2.0, opacity=0.18, smoothing=0.92)
    _trace(comp_inner, red, 2.0, opacity=0.12, smoothing=0.92)
    _trace(tens_lower, blue, 2.0, opacity=0.18, smoothing=0.92)
    _trace(tens_inner, blue, 2.0, opacity=0.12, smoothing=0.92)

    # draw main trajectories on top
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

    # Crack should start near tension face close to support and align with strut region
    crack_points = [
        (0.045 * span_m, _sample_beam_y(0.082)),
        (0.095 * span_m, _sample_beam_y(0.108)),
        (0.125 * span_m, _sample_beam_y(0.126)),
        (0.185 * span_m, _sample_beam_y(0.175)),
    ]
    _trace(crack_points, crack_color, 2.6, opacity=0.92, smoothing=0.55)
    fig.add_annotation(
        x=0.175 * span_m,
        y=_sample_beam_y(0.154),
        text="Crack",
        showarrow=False,
        font=dict(size=11, color=crack_color),
    )


def _render_field_cantilever_udl(fig: go.Figure, model: dict[str, Any]) -> None:
    span_m = model["span_m"]
    y_top = _BEAM_Y1
    y_bot = _BEAM_Y0
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


def _render_field_cantilever_eccentric(fig: go.Figure, model: dict[str, Any]) -> None:
    span_m = model["span_m"]
    load_x = max(0.0, min(model["a_cant_m"], span_m))
    y_top = _BEAM_Y1
    y_bot = _BEAM_Y0
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


def _render_shear_behaviour_field(
    fig: go.Figure,
    model: dict[str, Any],
    case_kind: str,
    visual_mode: str = "Principal stress field",
) -> None:
    if case_kind == "ss_midspan_point":
        _render_principal_stress_ss_midspan_point(fig, model)
    elif case_kind == "ss_udl":
        _render_principal_stress_ss_udl(fig, model)
    elif case_kind == "ss_near_support_point":
        _render_principal_stress_ss_near_support_point(fig, model)
    elif case_kind == "ss_eccentric_point":
        _render_principal_stress_ss_eccentric_point(fig, model)
    elif case_kind == "cantilever_tip":
        _render_principal_stress_cantilever_tip(fig, model)
    elif case_kind == "cantilever_udl":
        _render_principal_stress_cantilever_udl(fig, model)
    elif case_kind == "cantilever_eccentric":
        _render_principal_stress_cantilever_eccentric(fig, model)
    else:
        _render_principal_stress_ss_udl(fig, model)

    if bool(model.get("show_stm_geometry", model.get("show_stm_overlay", False))):
        _render_stm_overlay(fig, model, case_kind)
    if bool(model.get("show_stm_flow", False)):
        _render_stm_flow_overlay(fig, model, case_kind)


def _add_section_reo_overlay(fig: go.Figure, layout: dict[str, Any]) -> None:
    for point in layout.get("reo_points", []) or []:
        x = _safe_float(point.get("x", 0.0), 0.0)
        y = _safe_float(point.get("y", 0.0), 0.0)
        db = max(_safe_float(point.get("db", 20.0), 20.0), 8.0)
        layer = str(point.get("layer", "bottom") or "bottom")
        color = "rgba(0,90,200,0.94)" if layer == "bottom" else "rgba(200,45,45,0.94)"
        fig.add_shape(
            type="circle",
            x0=x - db / 2.0,
            y0=y - db / 2.0,
            x1=x + db / 2.0,
            y1=y + db / 2.0,
            line=dict(color="black", width=1.0),
            fillcolor=color,
        )


def build_shear_cross_section_figure(height: int = VISUAL_HEIGHT) -> go.Figure:
    layout = compute_section_layout()
    shape_name = layout.get("shape_name", "Rectangle (b × D)")
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
            tension_face=st.session_state.get("active_tension_face"),
        )

    width_mm = _safe_float(dims.get("bf", dims.get("b", 300.0)), 300.0)
    depth_mm = _safe_float(dims.get("D", 600.0), 600.0)
    lig_d = _safe_float(reo.get("lig_d", 0.0), 0.0)
    lig_legs = int(_safe_float(reo.get("lig_legs", 0.0), 0.0))
    _sv_sec = str(st.session_state.get("sec_shape", get_param("sec_shape", "RECT")) or "RECT")
    _, _sv_top_reo_lbl = main_longitudinal_reo_pair_labels(_sv_sec, variant="inputs_compact")

    for shape in fig.layout.shapes or []:
        if shape.type == "path" and getattr(shape, "fillcolor", "rgba(0,0,0,0)") == "rgba(0,0,0,0)":
            shape.fillcolor = "rgba(210,216,224,0.30)"
        if (
            shape.type == "rect"
            and abs(float(getattr(shape, "x0", 0.0))) < 1e-9
            and abs(float(getattr(shape, "y0", 0.0))) < 1e-9
            and abs(float(getattr(shape, "x1", width_mm)) - width_mm) < 1e-6
            and abs(float(getattr(shape, "y1", depth_mm)) - depth_mm) < 1e-6
        ):
            shape.fillcolor = "rgba(210,216,224,0.30)"
        if lig_d > 0.0 and lig_legs >= 2 and shape.type in {"rect", "line"}:
            x0 = _safe_float(getattr(shape, "x0", 0.0), 0.0)
            x1 = _safe_float(getattr(shape, "x1", width_mm), width_mm)
            y0 = _safe_float(getattr(shape, "y0", 0.0), 0.0)
            y1 = _safe_float(getattr(shape, "y1", depth_mm), depth_mm)
            is_inner_shape = (x0 > 0.0 or y0 > 0.0) and (x1 < width_mm or y1 < depth_mm)
            if is_inner_shape:
                shape.line.color = "rgba(0,0,0,0.95)"
                shape.line.width = max(_safe_float(getattr(shape.line, "width", 1.5), 1.5), 2.0)

    frame_size = _cross_section_frame_size(width_mm, depth_mm)
    x_c = width_mm / 2.0
    y_c = depth_mm / 2.0
    fig.update_xaxes(visible=False, fixedrange=True, range=[x_c - frame_size / 2.0, x_c + frame_size / 2.0])
    fig.update_yaxes(visible=False, fixedrange=True, range=[y_c + frame_size / 2.0, y_c - frame_size / 2.0], scaleanchor="x", scaleratio=1)
    fig.update_layout(height=height, margin=dict(l=12, r=12, t=12, b=12), paper_bgcolor="white", plot_bgcolor="white", showlegend=False)

    fig.add_annotation(x=width_mm / 2.0, y=-0.10 * depth_mm, text=f"b = {width_mm:.0f} mm", showarrow=False, font=dict(size=11, color="rgba(95,95,95,0.9)"))
    fig.add_annotation(x=-0.14 * width_mm, y=depth_mm / 2.0, text=f"D = {depth_mm:.0f} mm", showarrow=False, textangle=-90, font=dict(size=11, color="rgba(95,95,95,0.9)"))
    if layout.get("reo_layout", {}).get("top", []):
        fig.add_annotation(x=width_mm * 0.30, y=0.07 * depth_mm, text=_sv_top_reo_lbl, showarrow=False, font=dict(size=11, color="rgba(200,45,45,0.95)"))
    if layout.get("reo_layout", {}).get("bottom", []):
        fig.add_annotation(x=width_mm * 0.70, y=depth_mm - 0.07 * depth_mm, text="Tension reo", showarrow=False, font=dict(size=11, color="rgba(0,90,200,0.95)"))
    if lig_d > 0.0 and lig_legs >= 2:
        fig.add_annotation(x=width_mm / 2.0, y=depth_mm + 0.11 * depth_mm, text="Shear reinforcement", showarrow=False, font=dict(size=11, color="rgba(0,0,0,0.95)"))

    return fig


def build_shear_side_view_figure(
    height: int = SIDE_VIEW_VISUAL_HEIGHT,
    *,
    shear_fails: bool = False,
) -> go.Figure:
    model = _beam_model()
    fig = _build_side_view_figure(model["total_length_m"], model["D_m"], height, model["support_condition"])
    _add_beam_band(fig, model["total_length_m"], model["D_m"])
    _build_side_view_support_shapes(fig, model)
    _build_side_view_tension_reo(fig, model)
    _build_stirrup_markers(fig, model, shear_fails=shear_fails)
    return fig


def build_shear_behaviour_figure(
    height: int = BEHAVIOUR_VISUAL_HEIGHT,
    visual_mode: str = "Principal stress field",
    theta_v_deg: float | None = None,
    show_load_flow: bool = False,
    show_cracks: bool = True,
    show_stress_block: bool = True,
    show_stm_overlay: bool = False,
    show_stm_flow: bool = False,
) -> go.Figure:
    model = _beam_model()
    if theta_v_deg is not None:
        model["theta_v_deg"] = theta_v_deg
    model["show_load_flow"] = bool(show_load_flow)
    model["show_cracks"] = bool(show_cracks)
    model["show_stress_block"] = bool(show_stress_block)
    model["show_stm_overlay"] = bool(show_stm_overlay)
    model["show_stm_flow"] = bool(show_stm_flow)
    model["show_stm_geometry"] = bool(show_stm_overlay or show_stm_flow)
    case_kind = _classify_shear_behaviour_visual_case(model)
    fig = _build_behaviour_figure(model["total_length_m"], model["D_m"], height)
    _add_beam_band(fig, model["total_length_m"], model["D_m"])
    _build_shear_behaviour_support_shapes(fig, model)
    _build_shear_behaviour_load_shapes(fig, model, show_labels=False)
    _build_shear_behaviour_zones(fig, model, case_kind)
    _render_shear_behaviour_field(fig, model, case_kind, visual_mode)
    return fig


def build_shrinkage_schematic_plotly(width_px: int = 1100, height_px: int = 420) -> go.Figure:
    rng = np.random.default_rng(42)

    fig = go.Figure()

    # ------------------------------------------------------------------
    # Geometry
    # ------------------------------------------------------------------
    x0, x1 = 8.0, 96.0
    y0, y1 = 4.0, 18.0
    crust_y0 = 17.2

    # Main slab
    fig.add_shape(
        type="rect",
        x0=x0, y0=y0, x1=x1, y1=y1,
        line=dict(color="black", width=2),
        fillcolor="rgb(233,226,214)",
        layer="below",
    )

    # Dry thin crust strip
    fig.add_shape(
        type="rect",
        x0=x0, y0=crust_y0, x1=x1, y1=y1,
        line=dict(color="rgba(0,0,0,0)", width=0),
        fillcolor="rgb(205,189,166)",
        layer="below",
    )

    # ------------------------------------------------------------------
    # Concrete stipple texture
    # ------------------------------------------------------------------
    n_dots = 1800
    dots_x = rng.uniform(x0 + 0.6, x1 - 0.6, n_dots)
    dots_y = rng.uniform(y0 + 0.4, y1 - 0.6, n_dots)

    fig.add_trace(
        go.Scatter(
            x=dots_x,
            y=dots_y,
            mode="markers",
            marker=dict(size=2, color="rgba(120,110,95,0.22)"),
            hoverinfo="skip",
            showlegend=False,
        )
    )

    # ------------------------------------------------------------------
    # Aggregate particles
    # ------------------------------------------------------------------
    n_agg = 70
    agg_x = rng.uniform(x0 + 1.2, x1 - 1.2, n_agg)
    agg_y = rng.uniform(y0 + 1.0, y1 - 0.8, n_agg)
    agg_size = rng.uniform(6, 18, n_agg)

    fig.add_trace(
        go.Scatter(
            x=agg_x,
            y=agg_y,
            mode="markers",
            marker=dict(
                size=agg_size,
                color="rgb(147, 208, 232)",
                line=dict(color="black", width=0.8),
                symbol="circle",
            ),
            hoverinfo="skip",
            showlegend=False,
        )
    )

    # Some larger "stone" pieces near top for visual similarity
    fig.add_trace(
        go.Scatter(
            x=[19, 33, 43, 64, 77, 88],
            y=[16.8, 16.5, 16.3, 16.9, 16.1, 16.7],
            mode="markers",
            marker=dict(
                size=[14, 22, 18, 16, 20, 15],
                color="rgb(147, 208, 232)",
                line=dict(color="black", width=1.0),
            ),
            hoverinfo="skip",
            showlegend=False,
        )
    )

    # ------------------------------------------------------------------
    # Cracks (wavy lines descending from the top surface)
    # ------------------------------------------------------------------
    def add_crack(x_start: float, y_top: float, y_bot: float, amp: float = 0.45, phase: float = 0.0):
        ys = np.linspace(y_top, y_bot, 120)
        t = np.linspace(0, 1, 120)
        xs = x_start + amp * np.sin(2.6 * np.pi * t + phase) * (0.6 + 0.7 * t)
        fig.add_trace(
            go.Scatter(
                x=xs,
                y=ys,
                mode="lines",
                line=dict(color="black", width=2.2),
                hoverinfo="skip",
                showlegend=False,
            )
        )

    add_crack(13.0, 17.9, 12.0, amp=0.38, phase=0.0)
    add_crack(25.5, 17.9, 11.2, amp=0.46, phase=0.6)
    add_crack(38.5, 17.9, 4.3, amp=0.52, phase=1.2)
    add_crack(51.0, 17.9, 13.0, amp=0.36, phase=0.9)
    add_crack(69.5, 17.9, 12.0, amp=0.34, phase=0.4)
    add_crack(79.5, 17.9, 4.4, amp=0.56, phase=1.0)
    add_crack(92.0, 17.9, 10.0, amp=0.34, phase=0.2)

    # ------------------------------------------------------------------
    # Evaporation arrows
    # ------------------------------------------------------------------
    evap_x = [14, 26, 35, 46, 57, 67, 78, 86, 95]
    for xi in evap_x:
        fig.add_annotation(
            x=xi,
            y=25.0,
            ax=xi - 0.8,
            ay=18.6,
            xref="x",
            yref="y",
            axref="x",
            ayref="y",
            text="",
            showarrow=True,
            arrowhead=3,
            arrowsize=1.0,
            arrowwidth=1.8,
            arrowcolor="black",
        )

    # ------------------------------------------------------------------
    # Left dashed bracket for drying shrinkage
    # ------------------------------------------------------------------
    bx = 4.7
    fig.add_shape(
        type="line",
        x0=bx, y0=y0, x1=bx, y1=y1,
        line=dict(color="black", width=2, dash="dash"),
    )
    fig.add_shape(
        type="line",
        x0=bx, y0=y0, x1=x0, y1=y0,
        line=dict(color="black", width=2, dash="dash"),
    )
    fig.add_shape(
        type="line",
        x0=bx, y0=y1, x1=x0, y1=y1,
        line=dict(color="black", width=2, dash="dash"),
    )

    # Little bottom arrows showing inward shrinkage
    fig.add_annotation(
        x=7.4, y=1.3, ax=4.7, ay=1.3,
        xref="x", yref="y", axref="x", ayref="y",
        text="", showarrow=True, arrowhead=2, arrowwidth=1.8, arrowcolor="black"
    )
    fig.add_annotation(
        x=9.1, y=1.3, ax=11.8, ay=1.3,
        xref="x", yref="y", axref="x", ayref="y",
        text="", showarrow=True, arrowhead=2, arrowwidth=1.8, arrowcolor="black"
    )

    # ------------------------------------------------------------------
    # Labels / callouts
    # ------------------------------------------------------------------
    fig.add_annotation(
        x=12.0, y=24.7,
        text="<b>Water loss through<br>evaporation</b>",
        showarrow=False,
        font=dict(size=18, color="black"),
        align="left",
    )

    fig.add_annotation(
        x=39.0, y=18.1,
        ax=49.0, ay=26.4,
        xref="x", yref="y", axref="x", ayref="y",
        text="",
        showarrow=True,
        arrowhead=2,
        arrowwidth=2.0,
        arrowcolor="black",
    )

    fig.add_annotation(
        x=74.0, y=18.1,
        ax=66.0, ay=26.2,
        xref="x", yref="y", axref="x", ayref="y",
        text="",
        showarrow=True,
        arrowhead=2,
        arrowwidth=2.0,
        arrowcolor="black",
    )

    fig.add_annotation(
        x=61.0, y=28.0,
        text="<b>Plastic<br>Shrinkage<br>Cracks</b>",
        showarrow=False,
        font=dict(size=18, color="black"),
        align="center",
    )

    fig.add_annotation(
        x=90.5, y=18.0,
        ax=88.0, ay=26.8,
        xref="x", yref="y", axref="x", ayref="y",
        text="",
        showarrow=True,
        arrowhead=2,
        arrowwidth=2.0,
        arrowcolor="black",
    )

    fig.add_annotation(
        x=87.0, y=28.0,
        text="<b>Dry Thin<br>Crust</b>",
        showarrow=False,
        font=dict(size=18, color="black"),
        align="center",
    )

    fig.add_annotation(
        x=1.6,
        y=(y0 + y1) / 2,
        text="<b>Drying Shrinkage</b>",
        textangle=-90,
        showarrow=False,
        font=dict(size=20, color="black"),
    )

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------
    fig.update_xaxes(
        visible=False,
        range=[0, 100],
        fixedrange=True,
    )
    fig.update_yaxes(
        visible=False,
        range=[0, 30],
        fixedrange=True,
        scaleanchor=None,
    )

    fig.update_layout(
        width=width_px,
        height=height_px,
        margin=dict(l=10, r=10, t=10, b=10),
        paper_bgcolor="white",
        plot_bgcolor="white",
        showlegend=False,
    )

    return fig


def build_creep_schematic_plotly(width_px: int = 1100, height_px: int = 420) -> go.Figure:
    """
    Teaching schematic: concrete prism under sustained compression — elastic + creep shortening.
    Visual language matches build_shrinkage_schematic_plotly (axes 0–100 × 0–30).
    """
    rng = np.random.default_rng(43)

    fig = go.Figure()

    x0 = 8.0
    x_right_ref = 96.0  # original (undeformed) length reference at right
    x_right_elastic = 94.2  # conceptual end after instantaneous elastic shortening
    x_right_curr = 92.4  # end after additional creep over time
    y0, y1 = 4.0, 18.0

    # Ghost outline: original prism (undeformed length)
    fig.add_shape(
        type="rect",
        x0=x0,
        y0=y0,
        x1=x_right_ref,
        y1=y1,
        line=dict(color="rgba(80,80,80,0.55)", width=1.5, dash="dash"),
        fillcolor="rgba(233,226,214,0.18)",
        layer="below",
    )

    # Current prism body (shortened — sustained load + creep)
    fig.add_shape(
        type="rect",
        x0=x0,
        y0=y0,
        x1=x_right_curr,
        y1=y1,
        line=dict(color="black", width=2),
        fillcolor="rgb(233,226,214)",
        layer="below",
    )

    # Subtle “elastic-only” interior hint (slightly darker strip near right end)
    fig.add_shape(
        type="rect",
        x0=x_right_elastic - 0.15,
        y0=y0 + 0.35,
        x1=x_right_curr + 0.08,
        y1=y1 - 0.35,
        line=dict(color="rgba(0,0,0,0)", width=0),
        fillcolor="rgba(205,189,166,0.35)",
        layer="below",
    )

    # Stipple (current volume only)
    n_dots = 1600
    dots_x = rng.uniform(x0 + 0.6, x_right_curr - 0.5, n_dots)
    dots_y = rng.uniform(y0 + 0.4, y1 - 0.6, n_dots)
    fig.add_trace(
        go.Scatter(
            x=dots_x,
            y=dots_y,
            mode="markers",
            marker=dict(size=2, color="rgba(120,110,95,0.22)"),
            hoverinfo="skip",
            showlegend=False,
        )
    )

    n_agg = 65
    agg_x = rng.uniform(x0 + 1.0, x_right_curr - 1.0, n_agg)
    agg_y = rng.uniform(y0 + 1.0, y1 - 0.8, n_agg)
    agg_size = rng.uniform(6, 17, n_agg)
    fig.add_trace(
        go.Scatter(
            x=agg_x,
            y=agg_y,
            mode="markers",
            marker=dict(
                size=agg_size,
                color="rgb(147, 208, 232)",
                line=dict(color="black", width=0.8),
                symbol="circle",
            ),
            hoverinfo="skip",
            showlegend=False,
        )
    )

    # Reference: fixed left face
    fig.add_shape(
        type="line",
        x0=x0,
        y0=y0 - 0.35,
        x1=x0,
        y1=y1 + 0.35,
        line=dict(color="black", width=2, dash="dash"),
        layer="below",
    )

    # Reference: original right face (undeformed end)
    fig.add_shape(
        type="line",
        x0=x_right_ref,
        y0=y0,
        x1=x_right_ref,
        y1=y1,
        line=dict(color="rgba(60,60,60,0.75)", width=2, dash="dash"),
        layer="below",
    )

    # Internal creep / flow cues (gentle curves drifting toward fixed end)
    for i, (xa, xb) in enumerate([(18.0, 78.0), (28.0, 85.0), (22.0, 72.0), (38.0, 88.0)]):
        t = np.linspace(0, 1, 48)
        xs = xa + (xb - xa) * t + 0.55 * np.sin(2.4 * np.pi * t + 0.4 * i)
        ys = (y0 + y1) / 2 + 2.8 * np.sin(1.1 * np.pi * t + i * 0.35)
        fig.add_trace(
            go.Scatter(
                x=xs,
                y=ys,
                mode="lines",
                line=dict(color="rgba(40,40,40,0.45)", width=1.2, dash="dot"),
                hoverinfo="skip",
                showlegend=False,
            )
        )

    # Short internal dashed arrows (delayed strain development), pointing left
    for xi, yi in [(30, 12.5), (48, 9.8), (62, 14.0), (76, 11.2)]:
        fig.add_annotation(
            x=xi - 2.8,
            y=yi,
            ax=xi + 1.4,
            ay=yi,
            xref="x",
            yref="y",
            axref="x",
            ayref="y",
            text="",
            showarrow=True,
            arrowhead=2,
            arrowsize=0.85,
            arrowwidth=1.2,
            arrowcolor="rgba(35,35,35,0.75)",
        )

    # Sustained compression: downward arrows above prism
    for xi in [16, 30, 44, 58, 72, 86]:
        fig.add_annotation(
            x=xi,
            y=24.8,
            ax=xi + 0.35,
            ay=18.35,
            xref="x",
            yref="y",
            axref="x",
            ayref="y",
            text="",
            showarrow=True,
            arrowhead=3,
            arrowsize=1.0,
            arrowwidth=1.8,
            arrowcolor="black",
        )

    # Reactions: upward arrows below
    for xi in [20, 38, 54, 70, 84]:
        fig.add_annotation(
            x=xi,
            y=1.55,
            ax=xi + 0.25,
            ay=3.85,
            xref="x",
            yref="y",
            axref="x",
            ayref="y",
            text="",
            showarrow=True,
            arrowhead=3,
            arrowsize=1.0,
            arrowwidth=1.8,
            arrowcolor="black",
        )

    # Dimension: elastic + creep separation at right (horizontal bracket via line + arrows)
    fig.add_shape(
        type="line",
        x0=x_right_elastic,
        y0=2.35,
        x1=x_right_ref,
        y1=2.35,
        line=dict(color="black", width=1.2, dash="dot"),
        layer="above",
    )
    fig.add_shape(
        type="line",
        x0=x_right_curr,
        y0=2.0,
        x1=x_right_elastic,
        y1=2.0,
        line=dict(color="black", width=1.2),
        layer="above",
    )

    # Labels (minimal set)
    fig.add_annotation(
        x=48.0,
        y=26.8,
        text="<b>Sustained compressive stress</b>",
        showarrow=False,
        font=dict(size=18, color="black"),
        align="center",
    )

    fig.add_annotation(
        x=88.0,
        y=19.8,
        text="<b>Instantaneous<br>elastic strain</b>",
        showarrow=False,
        font=dict(size=14, color="black"),
        align="center",
    )

    fig.add_annotation(
        x=(x_right_curr + x_right_ref) / 2,
        y=1.05,
        text="<b>Additional creep strain over time</b>",
        showarrow=False,
        font=dict(size=14, color="black"),
        align="center",
    )

    fig.add_annotation(
        x=44.0,
        y=11.0,
        text="<b>Time-dependent viscoelastic<br>deformation</b>",
        showarrow=False,
        font=dict(size=14, color="black"),
        align="center",
    )

    fig.add_annotation(
        x=50.0,
        y=28.3,
        text="<i>Deformation increases with time while load is maintained</i>",
        showarrow=False,
        font=dict(size=11, color="#333333"),
        align="center",
    )

    fig.update_xaxes(
        visible=False,
        range=[0, 100],
        fixedrange=True,
    )
    fig.update_yaxes(
        visible=False,
        range=[0, 30],
        fixedrange=True,
        scaleanchor=None,
    )

    fig.update_layout(
        width=width_px,
        height=height_px,
        margin=dict(l=10, r=10, t=10, b=10),
        paper_bgcolor="white",
        plot_bgcolor="white",
        showlegend=False,
    )

    return fig
