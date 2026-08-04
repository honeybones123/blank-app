# bending_side_view_diagram.py
# Beam side elevation for the Bending page. Reuses the Crack side-view
# scaffold and re-renders the existing bending stress/strain Plotly panels
# at the current bending critical section.

from __future__ import annotations

import copy
import math
from typing import Any

import numpy as np
import plotly.graph_objects as go
import streamlit as st

from state_runtime_gateway import get_param
from shear_visuals import _beam_model
from ui.diagrams.side_view_diagram import (
    SIDE_VIEW_VISUAL_HEIGHT,
    build_side_view_tension_reo as _build_side_view_tension_reo,
    fit_side_view_figure_to_content as _fit_side_view_figure_to_content,
    build_side_view_figure as _build_side_view_figure,
    build_side_view_support_shapes as _build_side_view_support_shapes,
    side_view_display_length_from_model as _side_view_display_length_from_model,
    side_view_display_state as _side_view_display_state,
    side_view_display_x as _side_view_display_x,
)
from ui.diagrams.crack_side_view_diagram import (
    _add_deflected_beam_polygon_trace,
    _add_flexural_cracks_on_deflected_shape,
    _add_flexural_cracks_straight,
    _add_tension_reo_on_deflected_shape,
    _crack_diagram_metrics_from_shared,
    _diagram_kind,
    _resolve_crack_diagram_window,
    _shift_longitudinal_layer_stations_mm,
    _slice_rebase_deflection_mesh,
    _support_resolution,
    _total_structural_length_m,
    compute_crack_diagram_deflection_mesh,
)
from ui.diagrams.diagram_styles import (
    ANNOTATION_BG,
    ANNOTATION_BORDER,
    ANNOTATION_TEXT,
    COMPRESSION,
    CONCRETE_FILL_2D,
    CONCRETE_OUTLINE,
    DEFLECTED_FILL,
    DEFLECTED_LINE,
    DIAGRAM_TRANSPARENT,
    REO_BOTTOM,
    REO_INACTIVE,
    REO_TOP,
    UNDEFORMED_FILL,
    UNDEFORMED_LINE,
)


_COMPRESSION_ZONE_FILL = "rgba(200,45,45,0.14)"
_COMPRESSION_ZONE_BORDER = "rgba(200,45,45,0.36)"


def _as_float(v: Any) -> float | None:
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    return x if math.isfinite(x) else None


def _resolved_uls_moment_arrays_global() -> tuple[np.ndarray, np.ndarray] | None:
    x_raw = list(get_param("moment_x", []) or get_param("shear_x", []) or [])
    m_raw = list(get_param("shear_M_uls_kNm", []) or [])
    x = np.asarray(x_raw, dtype=float).reshape(-1)
    m = np.asarray(m_raw, dtype=float).reshape(-1)
    if x.size < 2 or m.size != x.size or not np.all(np.isfinite(x)) or not np.all(np.isfinite(m)):
        return None
    return x, m


def _current_design_section_x_m(length_m: float) -> float | None:
    source = str(
        st.session_state.get(
            "design_actions_source",
            get_param("design_actions_source", "max"),
        )
        or "max"
    )
    committed = bool(st.session_state.get("design_section_committed", False))
    design_x = _as_float(
        st.session_state.get("design_section_x_m", get_param("design_section_x_m", 0.0))
    )
    preview_x = _as_float(
        st.session_state.get("section_cursor_x_m", get_param("section_cursor_x_m", 0.0))
    )

    x_val: float | None
    if source == "section":
        x_val = design_x if committed and design_x is not None else preview_x
    elif committed and design_x is not None and design_x > 0.0:
        x_val = design_x
    elif preview_x is not None and preview_x > 0.0:
        x_val = preview_x
    else:
        x_val = None

    if x_val is None or x_val < 0.0 or x_val > length_m:
        return None
    return float(x_val)


def _critical_bending_x_m(
    *,
    window_x0_m: float,
    window_L_m: float,
    selected_sign: str,
) -> tuple[float | None, str]:
    """
    Return local x within the displayed side-view window.

    Section-mode actions use the committed/preview design section. Max-mode
    actions use the ULS moment array that feeds the current bending demand.
    Manual actions have no physical x unless a design/preview section exists.
    """
    L_total = max(_total_structural_length_m(), window_x0_m + window_L_m, window_L_m)
    design_source = str(
        st.session_state.get(
            "design_actions_source",
            get_param("design_actions_source", "max"),
        )
        or "max"
    )
    section_x = _current_design_section_x_m(L_total)
    if design_source == "section" and section_x is not None:
        return float(np.clip(section_x - window_x0_m, 0.0, window_L_m)), "selected section"

    ms = _resolved_uls_moment_arrays_global()
    if ms is not None:
        xg, m = ms
        x0 = float(window_x0_m)
        x1 = x0 + float(window_L_m)
        mask = (xg >= x0 - 1e-9) & (xg <= x1 + 1e-9)
        if np.any(mask):
            xw = np.asarray(xg[mask] - x0, dtype=float)
            mw = np.asarray(m[mask], dtype=float)
            if selected_sign == "negative":
                useful = mw < -1e-12
                if np.any(useful):
                    idx_local = int(np.argmin(mw))
                    return float(np.clip(xw[idx_local], 0.0, window_L_m)), "peak hogging ULS moment"
            else:
                useful = mw > 1e-12
                if np.any(useful):
                    idx_local = int(np.argmax(mw))
                    return float(np.clip(xw[idx_local], 0.0, window_L_m)), "peak sagging ULS moment"
            if float(np.max(np.abs(mw))) > 1e-12:
                idx_abs = int(np.argmax(np.abs(mw)))
                return float(np.clip(xw[idx_abs], 0.0, window_L_m)), "peak ULS moment"

    if section_x is not None:
        return float(np.clip(section_x - window_x0_m, 0.0, window_L_m)), "selected section"

    # Manual bending actions are section actions: there is no BMD-derived
    # longitudinal station in state. Use the active bending check's conventional
    # section location so the side-view still anchors the live section diagrams
    # instead of hiding them behind an unavailable message.
    if selected_sign == "negative":
        return 0.0, "manual hogging section"
    return 0.50 * float(window_L_m), "manual sagging section"


def _deflected_y_bounds_at_x(defl: dict[str, Any] | None, x_m: float, D_m: float) -> tuple[float, float]:
    if defl is None:
        return 0.0, float(D_m)
    xm = np.asarray(defl.get("x_m", []), dtype=float)
    wm = np.asarray(defl.get("w_m", []), dtype=float)
    if xm.size >= 2 and wm.size == xm.size:
        w0 = float(np.interp(float(x_m), xm, wm, left=float(wm[0]), right=float(wm[-1])))
    else:
        w0 = 0.0
    return w0, w0 + float(D_m)


def _add_critical_section_marker(
    fig: go.Figure,
    *,
    model: dict[str, Any],
    defl: dict[str, Any] | None,
    x_m: float | None,
    x_source: str,
    D_m: float,
) -> float | None:
    work = defl["work"] if defl is not None else dict(model, side_view_display=_side_view_display_state(model))
    if x_m is None:
        L_m = max(float(model.get("total_length_m", 0.0) or 0.0), 1e-9)
        fig.add_annotation(
            x=_side_view_display_x(0.50 * L_m, work),
            y=0.50 * D_m,
            text="Critical section unavailable",
            showarrow=False,
            bgcolor=ANNOTATION_BG,
            bordercolor=ANNOTATION_BORDER,
            borderwidth=1,
            font=dict(size=11, color=REO_INACTIVE),
        )
        return None

    xd = float(_side_view_display_x(float(x_m), work))
    y0, y1 = _deflected_y_bounds_at_x(defl, float(x_m), D_m)
    fig.add_shape(
        type="line",
        x0=xd,
        y0=y0 - 0.06 * D_m,
        x1=xd,
        y1=y1 + 0.08 * D_m,
        line=dict(color=COMPRESSION, width=2.2, dash="dash"),
    )
    fig.add_annotation(
        x=xd,
        y=y1 + 0.10 * D_m,
        text=f"Bending critical section<br><span style='font-size:10px'>{x_source}</span>",
        showarrow=False,
        bgcolor=ANNOTATION_BG,
        bordercolor=_COMPRESSION_ZONE_BORDER,
        borderwidth=1,
        borderpad=3,
        font=dict(size=11, color=COMPRESSION),
        xanchor="center",
    )
    return xd


def _layout_axis_range(src_fig: go.Figure, axis_name: str, fallback: tuple[float, float]) -> tuple[float, float]:
    axis = getattr(src_fig.layout, axis_name, None)
    rng = getattr(axis, "range", None) if axis is not None else None
    if rng is not None and len(rng) >= 2:
        a = _as_float(rng[0])
        b = _as_float(rng[1])
        if a is not None and b is not None and abs(b - a) > 1e-12:
            return a, b
    return fallback


def _trace_axis_name(trace: Any) -> str:
    return str(getattr(trace, "xaxis", None) or "x")


def _shape_xref(shape: Any) -> str:
    return str(getattr(shape, "xref", None) or (shape.get("xref", "x") if isinstance(shape, dict) else "x"))


def _annotation_xref(ann: Any) -> str:
    return str(getattr(ann, "xref", None) or (ann.get("xref", "x") if isinstance(ann, dict) else "x"))


def _get_attr(obj: Any, key: str, default: Any = None) -> Any:
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _set_attr(obj: Any, key: str, value: Any) -> None:
    if isinstance(obj, dict):
        obj[key] = value
    else:
        setattr(obj, key, value)


def _mapped_value(value: Any, mapper) -> Any:
    x = _as_float(value)
    return mapper(x) if x is not None else value


def _add_existing_stress_strain_overlay(
    fig: go.Figure,
    *,
    source_fig: go.Figure,
    model: dict[str, Any],
    defl: dict[str, Any] | None,
    critical_x_m: float,
    D_m: float,
    show_strain: bool = True,
    show_stress: bool = True,
) -> bool:
    """Clone the existing bending strain/stress panels into the side-view figure."""
    L_m = max(float(model.get("total_length_m", 0.0) or 0.0), 1e-9)
    work = defl["work"] if defl is not None else dict(model, side_view_display=_side_view_display_state(model))
    x_crit_disp = float(_side_view_display_x(float(critical_x_m), work))
    x0_disp = float(_side_view_display_x(0.0, work))
    x1_disp = float(_side_view_display_x(L_m, work))
    disp_span = max(abs(x1_disp - x0_disp), 1e-9)

    y_bot, y_top = _deflected_y_bounds_at_x(defl, float(critical_x_m), D_m)
    D_src = max(float(get_param("D", 600.0) or 600.0), 1.0)

    def y_map(y_mm: float) -> float:
        # Existing bending panel coordinates use y=0 at the compression/top
        # fibre and y=D at the bottom. Map that exact section depth to the
        # full side-view beam depth at the critical section.
        y_clamped = float(np.clip(float(y_mm), 0.0, D_src))
        return y_top - (y_clamped / D_src) * (y_top - y_bot)

    axis_ranges = {
        "x2": _layout_axis_range(source_fig, "xaxis2", (0.0, 1.0)),
        "x3": _layout_axis_range(source_fig, "xaxis3", (0.0, 1.0)),
    }
    axis_anchor = {
        "x2": 0.50,  # strain zero/depth axis in bending_diagrams.py
        "x3": 0.10,  # stress axis in bending_diagrams.py
    }
    requested_axes = {
        "x2": bool(show_strain),
        "x3": bool(show_stress),
    }

    def _axis_scale(axis: str) -> float:
        xr0, xr1 = axis_ranges.get(axis, (0.0, 1.0))
        anchor = axis_anchor[axis]
        if axis == "x3":
            target_right = min(0.72 * D_m, 0.22 * disp_span)
            return target_right / max(abs(xr1 - anchor), 1e-9)
        target_span = min(0.62 * D_m, 0.18 * disp_span)
        return target_span / max(abs(xr1 - xr0), 1e-9)

    def x_map(axis: str, x_val: float) -> float:
        xr0, xr1 = axis_ranges.get(axis, (0.0, 1.0))
        _ = (xr0, xr1)
        return x_crit_disp + (float(x_val) - axis_anchor[axis]) * _axis_scale(axis)

    added = False
    for trace in source_fig.data:
        axis = _trace_axis_name(trace)
        if not requested_axes.get(axis, False):
            continue
        new_trace = copy.deepcopy(trace)
        raw_x = getattr(trace, "x", None)
        raw_y = getattr(trace, "y", None)
        xs = list(raw_x) if raw_x is not None else []
        ys = list(raw_y) if raw_y is not None else []
        if not xs or not ys:
            continue
        new_trace.x = [_mapped_value(v, lambda q, a=axis: x_map(a, q)) for v in xs]
        new_trace.y = [_mapped_value(v, y_map) for v in ys]
        new_trace.xaxis = "x"
        new_trace.yaxis = "y"
        new_trace.showlegend = False
        new_trace.hoverinfo = "skip"
        fig.add_trace(new_trace)
        added = True

    for shape in list(source_fig.layout.shapes or []):
        axis = _shape_xref(shape)
        if not requested_axes.get(axis, False):
            continue
        new_shape = copy.deepcopy(shape)
        _set_attr(new_shape, "xref", "x")
        _set_attr(new_shape, "yref", "y")
        for key in ("x0", "x1"):
            _set_attr(new_shape, key, _mapped_value(_get_attr(shape, key), lambda q, a=axis: x_map(a, q)))
        for key in ("y0", "y1"):
            _set_attr(new_shape, key, _mapped_value(_get_attr(shape, key), y_map))
        fig.add_shape(new_shape)
        added = True

    for ann in list(source_fig.layout.annotations or []):
        axis = _annotation_xref(ann)
        if not requested_axes.get(axis, False):
            continue
        # Keep arrow-only annotations because the stress diagram uses Plotly
        # annotations for force arrows. Drop text labels for the side-view
        # overlay so the beam stays uncluttered.
        if str(_get_attr(ann, "text", "") or "").strip():
            continue
        new_ann = copy.deepcopy(ann)
        _set_attr(new_ann, "xref", "x")
        _set_attr(new_ann, "yref", "y")
        _set_attr(new_ann, "x", _mapped_value(_get_attr(ann, "x"), lambda q, a=axis: x_map(a, q)))
        _set_attr(new_ann, "y", _mapped_value(_get_attr(ann, "y"), y_map))
        if _get_attr(ann, "axref") == axis:
            _set_attr(new_ann, "axref", "x")
            _set_attr(new_ann, "ax", _mapped_value(_get_attr(ann, "ax"), lambda q, a=axis: x_map(a, q)))
        if _get_attr(ann, "ayref") in ("y2", "y3"):
            _set_attr(new_ann, "ayref", "y")
            _set_attr(new_ann, "ay", _mapped_value(_get_attr(ann, "ay"), y_map))
        font = copy.deepcopy(_get_attr(new_ann, "font", {}) or {})
        if isinstance(font, dict):
            font["size"] = min(float(font.get("size", 9) or 9), 8)
            _set_attr(new_ann, "font", font)
        fig.add_annotation(new_ann)
        added = True

    return added


def _make_bending_beam_fill_white(fig: go.Figure) -> None:
    """Keep the side-view beam on the shared concrete fill/outline contract."""
    for trace in fig.data:
        if str(getattr(trace, "fill", "") or "").lower() == "toself":
            line = getattr(trace, "line", None)
            width = _as_float(getattr(line, "width", None)) if line is not None else None
            if width is not None and width >= 1.5:
                trace.fillcolor = CONCRETE_FILL_2D
                if line is not None:
                    line.color = CONCRETE_OUTLINE


def _finite_deflection_arrays(defl: dict[str, Any] | None) -> tuple[np.ndarray, np.ndarray, np.ndarray] | None:
    if defl is None:
        return None
    try:
        x_m = np.asarray(defl.get("x_m", []), dtype=float).reshape(-1)
        w_m = np.asarray(defl.get("w_m", []), dtype=float).reshape(-1)
        x_disp = np.asarray(defl.get("x_disp", []), dtype=float).reshape(-1)
    except (TypeError, ValueError):
        return None
    if x_m.size < 2 or w_m.size != x_m.size or x_disp.size != x_m.size:
        return None
    if not (np.all(np.isfinite(x_m)) and np.all(np.isfinite(w_m)) and np.all(np.isfinite(x_disp))):
        return None
    if float(np.max(np.abs(w_m))) <= 1e-12:
        return None
    return x_m, w_m, x_disp


def _fit_deflected_side_view_to_mesh(
    fig: go.Figure,
    *,
    model: dict[str, Any],
    defl: dict[str, Any] | None,
    D_m: float,
    extra_w_m: np.ndarray | None = None,
) -> None:
    arrays = _finite_deflection_arrays(defl)
    if arrays is None or defl is None:
        return
    _x_m, w_m, _x_disp = arrays
    if extra_w_m is not None:
        try:
            extra = np.asarray(extra_w_m, dtype=float).reshape(-1)
            if extra.size:
                w_m = np.r_[w_m, extra[np.isfinite(extra)]]
        except (TypeError, ValueError):
            pass
    if w_m.size == 0:
        return
    L_m = max(float(defl.get("L_m", model.get("total_length_m", 0.0)) or 0.0), 0.1)
    _fit_side_view_figure_to_content(
        fig,
        length_m=L_m,
        beam_depth_m=D_m,
        support_condition=str(model.get("support_condition", "simply_supported") or "simply_supported"),
        height=SIDE_VIEW_VISUAL_HEIGHT,
        display_length_m=_side_view_display_length_from_model(model),
        y_min_needed=float(np.min(w_m)),
        y_max_needed=float(np.max(w_m)) + D_m,
    )


def _add_undeformed_beam_reference(fig: go.Figure, *, model: dict[str, Any], D_m: float) -> None:
    work = dict(model)
    work["side_view_display"] = _side_view_display_state(work)
    L_m = max(float(work.get("total_length_m", 0.0) or 0.0), 1e-9)
    x0 = float(_side_view_display_x(0.0, work))
    x1 = float(_side_view_display_x(L_m, work))
    fig.add_trace(
        go.Scatter(
            x=[x0, x1, x1, x0, x0],
            y=[D_m, D_m, 0.0, 0.0, D_m],
            mode="lines",
            fill="toself",
            fillcolor=UNDEFORMED_FILL,
            line=dict(color=UNDEFORMED_LINE, width=1.5, dash="dot"),
            hoverinfo="skip",
            showlegend=False,
        )
    )


def _style_recent_deflected_beam_trace(
    fig: go.Figure,
    *,
    start_idx: int,
    fillcolor: str,
    line_color: str,
    line_width: float,
    line_dash: str | None = None,
) -> None:
    if len(fig.data) <= start_idx:
        return
    tr = fig.data[-1]
    tr.fillcolor = fillcolor
    tr.line.color = line_color
    tr.line.width = line_width
    if line_dash:
        tr.line.dash = line_dash


def _add_creep_secondary_reo(
    fig: go.Figure,
    *,
    model: dict[str, Any],
    defl: dict[str, Any],
) -> None:
    trace_start = len(fig.data)
    _add_tension_reo_on_deflected_shape(fig, model, defl)

    for tr in list(fig.data)[trace_start:]:
        line = getattr(tr, "line", None)
        if line is None:
            continue
        current_colour = str(getattr(line, "color", "") or "")
        if "200,45,45" in current_colour or current_colour == REO_TOP:
            line.color = REO_TOP
        else:
            line.color = REO_BOTTOM
        line.width = max(2.0, min(float(getattr(line, "width", 1.2) or 1.2), 4.8))


def _add_creep_deflection_overlay(
    fig: go.Figure,
    *,
    model: dict[str, Any],
    defl: dict[str, Any] | None,
    creep_multiplier: float,
    D_m: float,
    label_prefix: str = "",
    creep_delta_mm: float | None = None,
) -> bool:
    arrays = _finite_deflection_arrays(defl)
    if arrays is None or defl is None:
        return False

    x_m, w_i, x_disp = arrays
    multiplier = _as_float(creep_multiplier)
    if multiplier is None:
        return False
    multiplier = float(np.clip(multiplier, 1.0, 5.0))

    _fit_deflected_side_view_to_mesh(fig, model=model, defl=defl, D_m=D_m)

    immediate_trace_start = len(fig.data)
    _add_deflected_beam_polygon_trace(fig, defl)
    _style_recent_deflected_beam_trace(
        fig,
        start_idx=immediate_trace_start,
        fillcolor=CONCRETE_FILL_2D,
        line_color=CONCRETE_OUTLINE,
        line_width=1.3,
    )
    L_m = max(float(defl.get("L_m", model.get("total_length_m", 0.0)) or 0.0), 1e-9)
    x_i_lbl = float(np.clip(0.28 * L_m, float(x_m[0]), float(x_m[-1])))

    if multiplier <= 1.01:
        fig.add_annotation(
            x=float(_side_view_display_x(x_i_lbl, defl["work"])),
            y=float(np.interp(x_i_lbl, x_m, w_i)) - 0.08 * D_m,
            text=f"{label_prefix}Immediate deflection, δ<sub>i</sub>",
            showarrow=False,
            bgcolor=ANNOTATION_BG,
            bordercolor=ANNOTATION_BORDER,
            borderwidth=1,
            borderpad=3,
            font=dict(size=12, color=ANNOTATION_TEXT),
        )
        return True

    defl_lt = copy.deepcopy(defl)
    defl_lt["w_m"] = np.asarray(w_i * multiplier, dtype=float)
    defl_lt["x_m"] = np.asarray(x_m, dtype=float)
    defl_lt["x_disp"] = np.asarray(x_disp, dtype=float)
    _fit_deflected_side_view_to_mesh(
        fig,
        model=model,
        defl=defl,
        D_m=D_m,
        extra_w_m=np.asarray(defl_lt["w_m"], dtype=float),
    )

    before = len(fig.data)
    _add_deflected_beam_polygon_trace(fig, defl_lt)
    _style_recent_deflected_beam_trace(
        fig,
        start_idx=before,
        fillcolor=DEFLECTED_FILL,
        line_color=DEFLECTED_LINE,
        line_width=1.6,
        line_dash="dash",
    )

    w_lt = np.asarray(defl_lt["w_m"], dtype=float)
    y_min = min(float(np.min(w_i)), float(np.min(w_lt))) - 0.18 * D_m
    y_max = max(float(np.max(w_i + D_m)), float(np.max(w_lt + D_m)), D_m) + 0.16 * D_m
    rng = getattr(fig.layout.yaxis, "range", None)
    if rng is not None and len(rng) >= 2:
        y_min = min(y_min, float(rng[0]))
        y_max = max(y_max, float(rng[1]))
    if math.isfinite(y_min) and math.isfinite(y_max) and y_max > y_min:
        fig.update_yaxes(range=[y_min, y_max])

    fig.add_trace(
        go.Scatter(
            x=x_disp,
            y=w_i,
            mode="lines",
            line=dict(color=UNDEFORMED_LINE, width=1.7, dash="dash"),
            hoverinfo="skip",
            showlegend=False,
        )
    )
    fig.add_trace(
        go.Scatter(
            x=x_disp,
            y=w_lt,
            mode="lines",
            line=dict(color=DEFLECTED_LINE, width=2.5, dash="dash"),
            hoverinfo="skip",
            showlegend=False,
        )
    )

    x_lt_lbl = float(np.clip(0.72 * L_m, float(x_m[0]), float(x_m[-1])))
    fig.add_annotation(
        x=float(_side_view_display_x(x_i_lbl, defl["work"])),
        y=float(np.interp(x_i_lbl, x_m, w_i)) + 0.02 * D_m,
        text=f"{label_prefix}Immediate deflection, δ<sub>i</sub>",
        showarrow=False,
        bgcolor=ANNOTATION_BG,
        bordercolor=ANNOTATION_BORDER,
        borderwidth=1,
        borderpad=4,
        font=dict(size=14, color=ANNOTATION_TEXT),
    )
    fig.add_annotation(
        x=float(_side_view_display_x(x_lt_lbl, defl["work"])),
        y=float(np.interp(x_lt_lbl, x_m, w_lt)) - 0.14 * D_m,
        text=f"{label_prefix}Long-term deflection, δ<sub>lt</sub>",
        showarrow=False,
        bgcolor=ANNOTATION_BG,
        bordercolor=DEFLECTED_LINE,
        borderwidth=1,
        borderpad=4,
        font=dict(size=14, color=DEFLECTED_LINE),
    )

    delta = w_lt - w_i
    if multiplier <= 1.01 or float(np.max(np.abs(delta))) <= 1e-9:
        return True

    idx = int(np.argmax(np.abs(delta)))
    x_arrow_m = float(x_m[idx])
    xd = float(_side_view_display_x(x_arrow_m, defl["work"]))
    yi = float(w_i[idx])
    ylt = float(w_lt[idx])
    label = f"{label_prefix}δ<sub>creep</sub>"
    creep_delta_val = _as_float(creep_delta_mm)
    if creep_delta_val is not None and abs(creep_delta_val) > 1e-9:
        label += f" = {abs(creep_delta_val):.1f} mm"

    fig.add_annotation(
        x=xd,
        y=ylt,
        ax=xd,
        ay=yi,
        xref="x",
        yref="y",
        axref="x",
        ayref="y",
        text="",
        showarrow=True,
        arrowhead=3,
        arrowsize=1.18,
        arrowwidth=2.75,
        arrowcolor=COMPRESSION,
    )
    fig.add_annotation(
        x=xd,
        y=0.5 * (yi + ylt),
        xshift=48 if x_arrow_m < 0.78 * L_m else -48,
        text=label,
        showarrow=False,
        bgcolor=ANNOTATION_BG,
        bordercolor=_COMPRESSION_ZONE_BORDER,
        borderwidth=1,
        borderpad=5,
        font=dict(size=16, color=COMPRESSION),
    )
    return True


def _state_float(state: Any, key: str) -> float | None:
    val = state.get(key) if hasattr(state, "get") else None
    out = _as_float(val)
    if out is not None:
        return out
    return _as_float(get_param(key, None))


def _resolve_creep_deflection_visual_multiplier(
    state: Any,
    *,
    phi_cc_t: float | None = None,
) -> tuple[float, float | None, str, bool]:
    delta_i = _state_float(state, "delta_short_total")
    delta_lt = _state_float(state, "delta_total")
    if delta_i is not None and delta_lt is not None and delta_lt >= 0.0:
        if abs(delta_i) <= 1e-9:
            if abs(delta_lt) <= 1e-9:
                delta_i = None
            else:
                return 1.0, float(max(delta_lt - delta_i, 0.0)), "delta_total / delta_short_total", False
        else:
            return float(delta_lt / max(delta_i, 1e-9)), float(delta_lt - delta_i), "delta_total / delta_short_total", False

    delta_add = _state_float(state, "delta_long_add")
    if delta_i is not None and delta_add is not None and delta_add >= 0.0:
        if abs(delta_i) <= 1e-9:
            if abs(delta_add) <= 1e-9:
                delta_i = None
            else:
                return 1.0, float(delta_add), "delta_short_total + delta_long_add", False
        else:
            return float((delta_i + delta_add) / max(delta_i, 1e-9)), float(delta_add), "delta_short_total + delta_long_add", False

    for key in ("creep_multiplier", "deflection_creep_multiplier", "long_term_deflection_multiplier"):
        mult = _state_float(state, key)
        if mult is not None and mult > 0.0:
            return float(mult), None, key, False

    phi = _as_float(phi_cc_t)
    if phi is None:
        phi = _state_float(state, "phi_cc_t")
    if phi is not None:
        visual_only_multiplier_from_phi = float(np.clip(1.0 + max(float(phi), 0.0), 1.2, 2.2))
        return visual_only_multiplier_from_phi, None, "visual-only 1 + phi_cc_t", True

    return 1.8, None, "visual-only fallback multiplier", True


def _compression_zone_span_from_stress_figure(
    source_fig: go.Figure | None,
    *,
    D_src: float,
) -> tuple[float, float] | None:
    if source_fig is None:
        return None

    spans: list[tuple[float, float]] = []
    for shape in list(source_fig.layout.shapes or []):
        if _shape_xref(shape) != "x3":
            continue
        fill = str(_get_attr(shape, "fillcolor", "") or "").lower()
        line = _get_attr(shape, "line", {}) or {}
        line_color = str(_get_attr(line, "color", "") or "").lower()
        if (
            "red" not in fill
            and "255,200,200" not in fill
            and "200,45,45" not in fill
            and "red" not in line_color
            and "200,45,45" not in line_color
        ):
            continue
        y0 = _as_float(_get_attr(shape, "y0"))
        y1 = _as_float(_get_attr(shape, "y1"))
        if y0 is None or y1 is None:
            continue
        lo = float(np.clip(min(y0, y1), 0.0, D_src))
        hi = float(np.clip(max(y0, y1), 0.0, D_src))
        if hi - lo > 1e-9:
            spans.append((lo, hi))

    for trace in source_fig.data:
        if _trace_axis_name(trace) != "x3":
            continue
        fill = str(getattr(trace, "fill", "") or "").lower()
        fillcolor = str(getattr(trace, "fillcolor", "") or "").lower()
        line = getattr(trace, "line", None)
        line_color = str(getattr(line, "color", "") or "").lower() if line is not None else ""
        if (
            fill != "toself"
            and "red" not in fillcolor
            and "200,45,45" not in fillcolor
            and "red" not in line_color
            and "200,45,45" not in line_color
        ):
            continue
        raw_y = getattr(trace, "y", None)
        ys = [_as_float(v) for v in (list(raw_y) if raw_y is not None else [])]
        vals = [float(v) for v in ys if v is not None]
        if not vals:
            continue
        lo = float(np.clip(min(vals), 0.0, D_src))
        hi = float(np.clip(max(vals), 0.0, D_src))
        if hi - lo > 1e-9:
            spans.append((lo, hi))

    if not spans:
        return None
    return min(lo for lo, _hi in spans), max(hi for _lo, hi in spans)


def _add_compression_zone_highlight(
    fig: go.Figure,
    *,
    source_fig: go.Figure | None,
    model: dict[str, Any],
    defl: dict[str, Any] | None,
    critical_x_m: float | None,
    D_m: float,
) -> bool:
    D_src = max(float(get_param("D", 600.0) or 600.0), 1.0)
    span = _compression_zone_span_from_stress_figure(source_fig, D_src=D_src)
    if span is None:
        return False

    y0_src, y1_src = span
    work = defl["work"] if defl is not None else dict(model, side_view_display=_side_view_display_state(model))
    L_m = max(float(model.get("total_length_m", 0.0) or 0.0), 1e-9)
    zone_depth_m = max((float(y1_src) - float(y0_src)) / D_src * D_m, 0.0)
    if zone_depth_m <= 1e-9:
        return False

    compression_at_top = 0.50 * (y0_src + y1_src) <= 0.50 * D_src
    fill = _COMPRESSION_ZONE_FILL
    if defl is not None:
        x_disp = np.asarray(defl.get("x_disp", []), dtype=float)
        w_m = np.asarray(defl.get("w_m", []), dtype=float)
        if x_disp.size >= 2 and w_m.size == x_disp.size:
            y_bot = w_m
            y_top = w_m + D_m
            if compression_at_top:
                y_outer = y_top
                y_inner = y_top - zone_depth_m
            else:
                y_outer = y_bot
                y_inner = y_bot + zone_depth_m
            fig.add_trace(
                go.Scatter(
                    x=np.r_[x_disp, x_disp[::-1], x_disp[:1]],
                    y=np.r_[y_outer, y_inner[::-1], y_outer[:1]],
                    fill="toself",
                    mode="lines",
                    fillcolor=fill,
                    line=dict(width=0),
                    hoverinfo="skip",
                    showlegend=False,
                )
            )
            return True

    x0_disp = float(_side_view_display_x(0.0, work))
    x1_disp = float(_side_view_display_x(L_m, work))
    if compression_at_top:
        y0, y1 = D_m - zone_depth_m, D_m
    else:
        y0, y1 = 0.0, zone_depth_m
    fig.add_shape(
        type="rect",
        x0=x0_disp,
        x1=x1_disp,
        y0=y0,
        y1=y1,
        line=dict(width=0),
        fillcolor=fill,
    )
    return True


def _creep_side_view_context(state: Any) -> dict[str, Any]:
    window = _resolve_crack_diagram_window(state)
    L_win = max(float(window["L_m"]), 0.1)
    x0 = float(window["x0_m"])
    wx, wM = window.get("x_m"), window.get("M_m")
    moment_series: tuple[np.ndarray, np.ndarray] | None = None
    if isinstance(wx, np.ndarray) and isinstance(wM, np.ndarray) and wx.size >= 2 and wM.size == wx.size:
        moment_series = (wx, wM)

    model = _beam_model()
    D_mm = float(get_param("D", 600.0) or 600.0)
    D_m = max(D_mm / 1000.0, 0.05)
    model["D_m"] = D_m

    L_total_m = max(_total_structural_length_m(), L_win)
    model_mesh = dict(model)
    model_mesh["total_length_m"] = L_total_m
    model_mesh["span_m"] = L_total_m

    model_disp = dict(model)
    model_disp["total_length_m"] = L_win
    model_disp["span_m"] = L_win
    model_disp["D_m"] = D_m
    if str(model_disp.get("support_condition")) != "cantilever":
        model_disp["support_positions"] = [0.0, L_win]
    model_disp["side_view_display"] = _side_view_display_state(model_disp)
    sec = model.get("section_x_m")
    if sec is not None and bool(window.get("multi")):
        try:
            model_disp["section_x_m"] = float(
                np.clip(float(sec) - x0, 0.02 * L_win, 0.98 * L_win)
            )
        except (TypeError, ValueError):
            pass
    _shift_longitudinal_layer_stations_mm(model_disp, x0)

    sup_res = _support_resolution(state)
    support_lbl = str(sup_res.get("support_type") or "Simply supported")
    defl_full = compute_crack_diagram_deflection_mesh(
        model_mesh,
        L_total_m * 1000.0,
        D_mm,
        sup_res,
    )
    defl = _slice_rebase_deflection_mesh(defl_full, x0, L_win, model_disp)

    return {
        "window": window,
        "L_win": L_win,
        "x0": x0,
        "D_mm": D_mm,
        "D_m": D_m,
        "model_disp": model_disp,
        "support_lbl": support_lbl,
        "diagram_kind": _diagram_kind(support_lbl),
        "moment_series": moment_series,
        "defl": defl,
    }


def _new_creep_base_side_view_fig(ctx: dict[str, Any]) -> go.Figure:
    model_disp = ctx["model_disp"]
    fig = _build_side_view_figure(
        float(ctx["L_win"]),
        float(ctx["D_m"]),
        SIDE_VIEW_VISUAL_HEIGHT,
        str(model_disp.get("support_condition", "simply_supported") or "simply_supported"),
        display_length_m=_side_view_display_length_from_model(model_disp),
    )
    _add_undeformed_beam_reference(fig, model=model_disp, D_m=float(ctx["D_m"]))
    return fig


def _add_creep_unavailable_note(
    fig: go.Figure,
    *,
    model: dict[str, Any],
    L_m: float,
    D_m: float,
    text: str,
) -> None:
    work = dict(model, side_view_display=_side_view_display_state(model))
    fig.add_annotation(
        x=_side_view_display_x(0.50 * L_m, work),
        y=0.50 * D_m,
        text=text,
        showarrow=False,
        bgcolor=ANNOTATION_BG,
        bordercolor=ANNOTATION_BORDER,
        borderwidth=1,
        borderpad=3,
        font=dict(size=11, color=REO_INACTIVE),
    )


def _add_immediate_deflection_label(fig: go.Figure, *, defl: dict[str, Any], D_m: float) -> bool:
    arrays = _finite_deflection_arrays(defl)
    if arrays is None:
        return False
    x_m, w_i, _x_disp = arrays
    L_m = max(float(defl.get("L_m", 0.0) or 0.0), 1e-9)
    x_lbl = float(np.clip(0.34 * L_m, float(x_m[0]), float(x_m[-1])))
    fig.add_annotation(
        x=float(_side_view_display_x(x_lbl, defl["work"])),
        y=float(np.interp(x_lbl, x_m, w_i)) + 0.05 * D_m,
        text="Immediate deflection, δ<sub>i</sub>",
        showarrow=False,
        bgcolor=ANNOTATION_BG,
        bordercolor=ANNOTATION_BORDER,
        borderwidth=1,
        borderpad=4,
        font=dict(size=12, color=ANNOTATION_TEXT),
    )
    return True


def _style_recent_creep_crack_traces(fig: go.Figure, *, start_idx: int, muted: bool) -> None:
    if not muted:
        return
    for trace in list(fig.data)[start_idx:]:
        line = getattr(trace, "line", None)
        if line is not None:
            try:
                trace.line.color = REO_INACTIVE
                trace.line.width = min(float(trace.line.width or 1.0), 1.0)
            except (TypeError, ValueError):
                trace.line.color = REO_INACTIVE
        if hasattr(trace, "fillcolor"):
            try:
                trace.fillcolor = UNDEFORMED_FILL
            except ValueError:
                pass


def _add_creep_flexural_crack_label(
    fig: go.Figure,
    *,
    ctx: dict[str, Any],
    x_m: float | None,
    text: str,
    muted: bool = False,
) -> None:
    L_m = max(float(ctx["L_win"]), 1e-9)
    D_m = max(float(ctx["D_m"]), 1e-9)
    x_anchor = float(np.clip(x_m if x_m is not None else 0.48 * L_m, 0.08 * L_m, 0.92 * L_m))
    defl = ctx.get("defl")
    y_base = 0.18 * D_m
    work = dict(ctx["model_disp"], side_view_display=_side_view_display_state(ctx["model_disp"]))
    if defl is not None:
        arrays = _finite_deflection_arrays(defl)
        if arrays is not None:
            x_arr, w_arr, _x_disp = arrays
            y_base = float(np.interp(x_anchor, x_arr, w_arr)) + 0.18 * D_m
            work = defl["work"]
    x_text = float(np.clip(0.24 * L_m, 0.08 * L_m, 0.92 * L_m))
    y_text = max(0.56 * D_m, y_base + 0.58 * D_m)
    color = REO_INACTIVE if muted else ANNOTATION_TEXT
    border = ANNOTATION_BORDER
    fig.add_annotation(
        x=float(_side_view_display_x(x_text, work)),
        y=y_text,
        ax=float(_side_view_display_x(x_anchor, work)),
        ay=y_base,
        xref="x",
        yref="y",
        axref="x",
        ayref="y",
        text=text,
        showarrow=False,
        bgcolor=ANNOTATION_BG,
        bordercolor=border,
        borderwidth=1,
        borderpad=3,
        font=dict(size=11, color=color),
    )


def _add_flexural_cracks_on_creep_side_view(
    fig: go.Figure,
    *,
    ctx: dict[str, Any],
    height_scale: float = 1.45,
    label_text: str | None = None,
    muted: bool = False,
) -> float | None:
    try:
        mets = _crack_diagram_metrics_from_shared(None)
        sr_mm = float(mets["sr_max_mm"])
        w_mm = float(mets["w_calc_mm"])
        wmax_mm: float | None = float(mets["wmax_mm"])
    except Exception:
        return None

    defl = ctx.get("defl")
    model_disp = ctx["model_disp"]
    before = len(fig.data)
    if defl is not None:
        best_x = _add_flexural_cracks_on_deflected_shape(
            fig,
            defl,
            support_type_label=str(ctx["support_lbl"]),
            sr_max_mm=sr_mm,
            w_mm=w_mm,
            wmax_mm=wmax_mm,
            model=model_disp,
            moment_series=ctx.get("moment_series"),
            height_scale=height_scale,
        )
        _style_recent_creep_crack_traces(fig, start_idx=before, muted=muted)
        if label_text:
            _add_creep_flexural_crack_label(fig, ctx=ctx, x_m=best_x, text=label_text, muted=muted)
        return best_x

    best_x = _add_flexural_cracks_straight(
        fig,
        model_disp,
        support_type_label=str(ctx["support_lbl"]),
        sr_max_mm=sr_mm,
        w_mm=w_mm,
        wmax_mm=wmax_mm,
        moment_series=ctx.get("moment_series"),
        height_scale=height_scale,
    )
    _style_recent_creep_crack_traces(fig, start_idx=before, muted=muted)
    if label_text:
        _add_creep_flexural_crack_label(fig, ctx=ctx, x_m=best_x, text=label_text, muted=muted)
    return best_x


def _build_immediate_cracked_state_figure(state: Any) -> tuple[go.Figure, dict[str, Any]]:
    ctx = _creep_side_view_context(state)
    fig = _new_creep_base_side_view_fig(ctx)
    model_disp = ctx["model_disp"]
    defl = ctx.get("defl")
    D_m = float(ctx["D_m"])
    L_win = float(ctx["L_win"])

    overlay_added = False
    if defl is not None and _finite_deflection_arrays(defl) is not None:
        _fit_deflected_side_view_to_mesh(fig, model=model_disp, defl=defl, D_m=D_m)
        before = len(fig.data)
        _add_deflected_beam_polygon_trace(fig, defl)
        _style_recent_deflected_beam_trace(
            fig,
            start_idx=before,
            fillcolor=CONCRETE_FILL_2D,
            line_color=CONCRETE_OUTLINE,
            line_width=1.7,
        )
        overlay_added = _add_immediate_deflection_label(fig, defl=defl, D_m=D_m)
        _build_side_view_support_shapes(fig, model_disp)
        _add_creep_secondary_reo(fig, model=model_disp, defl=defl)
        _add_flexural_cracks_on_creep_side_view(
            fig,
            ctx=ctx,
            height_scale=1.45,
            label_text="Flexural cracks",
        )
    else:
        _build_side_view_support_shapes(fig, model_disp)
        _build_side_view_tension_reo(fig, model_disp)
        _add_creep_unavailable_note(
            fig,
            model=model_disp,
            L_m=L_win,
            D_m=D_m,
            text="Immediate cracked-state visual unavailable - deflection data not available.",
        )

    fig.update_layout(
        showlegend=False,
        margin=dict(t=8, b=8, l=8, r=8),
    )
    return fig, {"immediate_overlay_added": overlay_added}


def _build_long_term_creep_figure(
    state: Any,
    *,
    phi_cc_t: float | None = None,
) -> tuple[go.Figure, dict[str, Any]]:
    ctx = _creep_side_view_context(state)
    fig = _new_creep_base_side_view_fig(ctx)
    model_disp = ctx["model_disp"]
    defl = ctx.get("defl")
    D_m = float(ctx["D_m"])
    L_win = float(ctx["L_win"])

    creep_multiplier, creep_delta_mm, multiplier_source, fallback_used = _resolve_creep_deflection_visual_multiplier(
        state,
        phi_cc_t=phi_cc_t,
    )
    overlay_added = _add_creep_deflection_overlay(
        fig,
        model=model_disp,
        defl=defl,
        creep_multiplier=creep_multiplier,
        D_m=D_m,
        creep_delta_mm=creep_delta_mm,
    )

    _build_side_view_support_shapes(fig, model_disp)
    if overlay_added and defl is not None:
        _add_creep_secondary_reo(fig, model=model_disp, defl=defl)
        _add_flexural_cracks_on_creep_side_view(
            fig,
            ctx=ctx,
            height_scale=1.45,
            label_text="Flexural cracks may widen",
            muted=True,
        )
    else:
        _build_side_view_tension_reo(fig, model_disp)
        _add_creep_unavailable_note(
            fig,
            model=model_disp,
            L_m=L_win,
            D_m=D_m,
            text="Long-term creep overlay unavailable - deflection data not available.",
        )

    fig.update_layout(
        showlegend=False,
        margin=dict(t=8, b=8, l=8, r=8),
    )
    return fig, {
        "overlay_added": overlay_added,
        "creep_multiplier": float(np.clip(creep_multiplier, 1.0, 5.0)),
        "creep_multiplier_source": multiplier_source,
        "creep_visual_fallback_used": fallback_used,
        "creep_delta_mm": creep_delta_mm,
    }


def build_creep_side_view_figures(
    state: Any,
    *,
    phi_cc_t: float | None = None,
) -> tuple[go.Figure, go.Figure, dict[str, Any]]:
    fig_immediate, meta_immediate = _build_immediate_cracked_state_figure(state)
    fig_long_term, meta_long_term = _build_long_term_creep_figure(state, phi_cc_t=phi_cc_t)
    return fig_immediate, fig_long_term, {**meta_immediate, **meta_long_term}


def build_bending_side_view_figure(
    state: Any,
    *,
    stress_strain_fig: go.Figure | None = None,
    show_section_diagrams: bool = False,
    show_strain_diagram: bool = False,
    show_stress_diagram: bool = False,
) -> tuple[go.Figure, dict[str, Any]]:
    window = _resolve_crack_diagram_window(state)
    L_win = max(float(window["L_m"]), 0.1)
    x0 = float(window["x0_m"])

    model = _beam_model()
    D_mm = float(get_param("D", 600.0) or 600.0)
    D_m = max(D_mm / 1000.0, 0.05)
    model["D_m"] = D_m

    L_total_m = max(_total_structural_length_m(), L_win)
    model_mesh = dict(model)
    model_mesh["total_length_m"] = L_total_m
    model_mesh["span_m"] = L_total_m

    model_disp = dict(model)
    model_disp["total_length_m"] = L_win
    model_disp["span_m"] = L_win
    model_disp["D_m"] = D_m
    if str(model_disp.get("support_condition")) != "cantilever":
        model_disp["support_positions"] = [0.0, L_win]
    model_disp["side_view_display"] = _side_view_display_state(model_disp)

    fig = _build_side_view_figure(
        L_win,
        D_m,
        SIDE_VIEW_VISUAL_HEIGHT,
        str(model_disp.get("support_condition", "simply_supported") or "simply_supported"),
        display_length_m=_side_view_display_length_from_model(model_disp),
    )
    show_strain = bool(show_strain_diagram or show_section_diagrams)
    show_stress = bool(show_stress_diagram or show_section_diagrams)
    show_any_diagram = show_strain or show_stress

    sup_res = _support_resolution(state)
    defl_full = compute_crack_diagram_deflection_mesh(
        model_mesh,
        L_total_m * 1000.0,
        D_mm,
        sup_res,
    )
    defl = _slice_rebase_deflection_mesh(defl_full, x0, L_win, model_disp)
    if defl is not None:
        _fit_deflected_side_view_to_mesh(fig, model=model_disp, defl=defl, D_m=D_m)
        _add_deflected_beam_polygon_trace(fig, defl)
        _make_bending_beam_fill_white(fig)
        _build_side_view_support_shapes(fig, model_disp)
        if not show_any_diagram:
            _add_tension_reo_on_deflected_shape(fig, model_disp, defl)
    else:
        _build_side_view_support_shapes(fig, model_disp)
        if not show_any_diagram:
            _build_side_view_tension_reo(fig, model_disp)

    selected_sign = str(st.session_state.get("bending_detail_view", "positive") or "positive")
    critical_x, x_source = _critical_bending_x_m(
        window_x0_m=x0,
        window_L_m=L_win,
        selected_sign=selected_sign,
    )
    _add_compression_zone_highlight(
        fig,
        source_fig=stress_strain_fig,
        model=model_disp,
        defl=defl,
        critical_x_m=critical_x,
        D_m=D_m,
    )

    overlay_added = False
    if show_any_diagram:
        if critical_x is not None and stress_strain_fig is not None:
            try:
                overlay_added = _add_existing_stress_strain_overlay(
                    fig,
                    source_fig=stress_strain_fig,
                    model=model_disp,
                    defl=defl,
                    critical_x_m=critical_x,
                    D_m=D_m,
                    show_strain=show_strain,
                    show_stress=show_stress,
                )
            except Exception:
                overlay_added = False
        if not overlay_added:
            work = defl["work"] if defl is not None else dict(model_disp, side_view_display=_side_view_display_state(model_disp))
            fig.add_annotation(
                x=_side_view_display_x(float(critical_x if critical_x is not None else 0.5 * L_win), work),
                y=0.48 * D_m,
                text="Stress/strain diagram unavailable",
                showarrow=False,
                bgcolor=ANNOTATION_BG,
                bordercolor=ANNOTATION_BORDER,
                borderwidth=1,
                font=dict(size=11, color=REO_INACTIVE),
            )

    if not show_any_diagram:
        _add_critical_section_marker(
            fig,
            model=model_disp,
            defl=defl,
            x_m=critical_x,
            x_source=x_source,
            D_m=D_m,
        )

    fig.update_layout(
        showlegend=False,
        margin=dict(t=8, b=8, l=8, r=8),
    )
    return fig, {
        "critical_x_m": critical_x,
        "critical_x_source": x_source,
        "section_diagram_overlay_added": overlay_added,
        "strain_diagram_requested": show_strain,
        "stress_diagram_requested": show_stress,
    }


def build_creep_side_view_figure(
    state: Any,
    *,
    phi_cc_t: float | None = None,
) -> tuple[go.Figure, dict[str, Any]]:
    return _build_long_term_creep_figure(state, phi_cc_t=phi_cc_t)
