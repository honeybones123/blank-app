"""Deflection-page deflected-shape figure builder."""

from __future__ import annotations

import math

import numpy as np
import plotly.graph_objects as go

from .diagram_styles import (
    ANNOTATION_BG,
    ANNOTATION_BORDER,
    ANNOTATION_TEXT,
    CONCRETE_FILL_2D,
    CONCRETE_OUTLINE,
    DEFLECTED_LINE,
    DIAGRAM_BG,
    DIAGRAM_SIZE_LONGITUDINAL,
    DIAGRAM_TRANSPARENT,
    MARKER_OUTLINE,
    MAX_DEFLECTION_MARKER,
    REO_BOTTOM,
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
    TITLE_TEXT,
    UNDEFORMED_FILL,
    UNDEFORMED_LINE,
    diagram_deflection_visual_scale_factor,
)


DEFLECTION_VISUAL_WIDTH = DIAGRAM_SIZE_LONGITUDINAL["width"]
DEFLECTION_VISUAL_HEIGHT = DIAGRAM_SIZE_LONGITUDINAL["height"]
DEFLECTION_VISUAL_MARGIN = {"l": 18, "r": 18, "t": 52, "b": 10}


_SUPPORT_DIAGRAM_KIND = {
    "Simply supported": "simply_supported_udl",
    "Pinned-Pinned": "simply_supported_udl",
    "Continuous - end span": "continuous_span_udl",
    "Continuous - interior span": "continuous_span_udl",
    "Fixed-ended": "fixed_fixed_udl",
    "Fixed-Pinned": "fixed_pinned_udl",
    "Pinned-Fixed": "fixed_pinned_udl",
    "Cantilever": "cantilever_udl",
}


def _normalise_support_label(support_type: str | None) -> str:
    return str(support_type or "").strip().replace("–", "-")


def _support_diagram_kind(support_type: str | None) -> str:
    label = _normalise_support_label(support_type)
    return _SUPPORT_DIAGRAM_KIND.get(label, "simply_supported_udl")


def _deflection_support_y_min(
    support_type: str | None,
    D_mm: float,
    support_pair: tuple[str, str] | None = None,
) -> float:
    """Lowest support glyph coordinate so supports stay inside the clean viewport."""
    return _deflection_support_y_bounds(support_type, D_mm, support_pair=support_pair)[0]


def _deflection_support_y_bounds(
    support_type: str | None,
    D_mm: float,
    support_pair: tuple[str, str] | None = None,
) -> tuple[float, float]:
    """Vertical support glyph bounds in deflection diagram coordinates."""
    D_val = max(float(D_mm), 1.0)
    support_labels: list[str] = [_normalise_support_label(support_type)]
    if isinstance(support_pair, tuple) and len(support_pair) == 2:
        support_labels.extend(_normalise_support_label(label) for label in support_pair)
    has_fixed = any(str(label).lower() == "fixed" for label in support_labels)
    if has_fixed or _normalise_support_label(support_type) in {"Cantilever", "Fixed-ended", "Fixed-Pinned", "Pinned-Fixed"}:
        overhang = SUPPORT_FIXED_OVERHANG_BEAM_RATIO * D_val
        return -D_val - overhang, overhang
    support_d = max(SUPPORT_PIN_DEPTH_BEAM_RATIO * D_val, SUPPORT_PIN_MIN_DEPTH_MM)
    ground_drop = max(SUPPORT_GROUND_DROP_BEAM_RATIO * D_val, SUPPORT_GROUND_MIN_DROP_MM)
    return -D_val - support_d - ground_drop, 0.0


def _add_deflection_supports_plotly(
    fig: go.Figure,
    support_type: str | None,
    L_mm: float,
    D_mm: float,
    support_pair: tuple[str, str] | None = None,
) -> None:
    """
    Illustrative supports under the undeformed beam (bottom fibre y = -D_mm).

    Drawing-only:
    - Simply supported: pin + roller.
    - Cantilever: fixed wall at one end only.
    - Fixed-ended: fixed walls both ends.
    - Fixed-Pinned / Pinned-Fixed: fixed at one end, pin + roller at the other.
    - Continuous spans: pins at both ends; continuity extension is drawn by the
      deflected beam mesh.
    """
    st_val = _normalise_support_label(support_type)
    y_bot = -float(D_mm)
    L_mm = float(L_mm)
    support_w = max(SUPPORT_PIN_WIDTH_SPAN_RATIO * float(L_mm), SUPPORT_PIN_MIN_WIDTH_MM)
    support_d = max(SUPPORT_PIN_DEPTH_BEAM_RATIO * float(D_mm), SUPPORT_PIN_MIN_DEPTH_MM)
    hatch_dx = max(SUPPORT_FIXED_HATCH_SPAN_RATIO * float(L_mm), SUPPORT_FIXED_MIN_HATCH_MM)
    roller_r = max(SUPPORT_ROLLER_RADIUS_BEAM_RATIO * float(D_mm), SUPPORT_ROLLER_MIN_RADIUS_MM)
    ground_drop = max(SUPPORT_GROUND_DROP_BEAM_RATIO * float(D_mm), SUPPORT_GROUND_MIN_DROP_MM)

    def _pinned(x_pos: float, *, roller: bool) -> None:
        y_base = y_bot - support_d
        y_ground = y_base - ground_drop
        fig.add_shape(
            type="path",
            path=(
                f"M {x_pos - support_w},{y_base} L {x_pos + support_w},"
                f"{y_base} L {x_pos},{y_bot} Z"
            ),
            line=dict(color=SUPPORT_OUTLINE, width=1.4),
            fillcolor=SUPPORT_FILL,
            layer="below",
        )
        fig.add_shape(
            type="line",
            x0=x_pos - support_w * 1.15,
            y0=y_ground,
            x1=x_pos + support_w * 1.15,
            y1=y_ground,
            line=dict(color=SUPPORT_GROUND, width=1.0),
            layer="below",
        )
        if roller:
            fig.add_shape(
                type="circle",
                xref="x",
                yref="y",
                x0=x_pos - roller_r,
                y0=y_base - support_d * 0.45 - roller_r,
                x1=x_pos + roller_r,
                y1=y_base - support_d * 0.45 + roller_r,
                line=dict(color=SUPPORT_OUTLINE, width=1.2),
                fillcolor=SUPPORT_ROLLER_FILL,
                layer="below",
            )

    def _fixed(x_pos: float) -> None:
        y_min = y_bot - SUPPORT_FIXED_OVERHANG_BEAM_RATIO * float(D_mm)
        y_max = SUPPORT_FIXED_OVERHANG_BEAM_RATIO * float(D_mm)
        fig.add_shape(
            type="line",
            x0=x_pos,
            y0=y_min,
            x1=x_pos,
            y1=y_max,
            line=dict(color=SUPPORT_OUTLINE, width=6),
            layer="below",
        )
        for frac in (0.08, 0.28, 0.48, 0.68, 0.88):
            y_val = y_min + frac * (y_max - y_min)
            fig.add_shape(
                type="line",
                x0=x_pos - hatch_dx,
                y0=y_val + 0.10 * float(D_mm),
                x1=x_pos,
                y1=y_val - 0.04 * float(D_mm),
                line=dict(color=SUPPORT_GROUND_HATCH, width=1.0),
                layer="below",
            )

    def _draw_support_from_label(x_pos: float, label: str, *, right_edge: bool = False) -> None:
        support_label = _normalise_support_label(label).lower()
        if support_label == "fixed":
            _fixed(x_pos)
        elif support_label == "roller":
            _pinned(x_pos, roller=True)
        else:
            _pinned(x_pos, roller=bool(right_edge and st_val == "Simply supported"))

    if isinstance(support_pair, tuple) and len(support_pair) == 2:
        left_lbl = str(support_pair[0] or "Pinned")
        right_lbl = str(support_pair[1] or "Pinned")
        _draw_support_from_label(0.0, left_lbl, right_edge=False)
        _draw_support_from_label(float(L_mm), right_lbl, right_edge=True)
        return

    if st_val == "Cantilever":
        _fixed(0.0)
    elif st_val == "Fixed-ended":
        _fixed(0.0)
        _fixed(float(L_mm))
    elif st_val == "Fixed-Pinned":
        _fixed(0.0)
        _pinned(float(L_mm), roller=True)
    elif st_val == "Pinned-Fixed":
        _pinned(0.0, roller=False)
        _fixed(float(L_mm))
    elif st_val == "Continuous - end span":
        _pinned(0.0, roller=False)
        _pinned(float(L_mm), roller=False)
    elif st_val == "Continuous - interior span":
        _pinned(0.0, roller=False)
        _pinned(float(L_mm), roller=False)
    elif st_val == "Pinned-Pinned":
        _pinned(0.0, roller=False)
        _pinned(float(L_mm), roller=False)
    else:
        _pinned(0.0, roller=False)
        _pinned(float(L_mm), roller=True)


def _add_deflection_span_marker(fig: go.Figure, L_mm: float, D_mm: float) -> float:
    """Draw a visual-only span marker tied to the active deflection length."""
    L_mm = float(L_mm)
    D_mm = float(D_mm)
    if L_mm <= 0.0 or not math.isfinite(L_mm):
        return -1.34 * D_mm

    y_marker = -1.34 * D_mm
    tick = max(0.055 * D_mm, 10.0)
    fig.add_shape(
        type="line",
        x0=0.0,
        y0=y_marker,
        x1=L_mm,
        y1=y_marker,
        line=dict(color=UNDEFORMED_LINE, width=1.0),
        layer="below",
    )
    for x_pos in (0.0, L_mm):
        fig.add_shape(
            type="line",
            x0=x_pos,
            y0=y_marker - 0.5 * tick,
            x1=x_pos,
            y1=y_marker + 0.5 * tick,
            line=dict(color=UNDEFORMED_LINE, width=1.0),
            layer="below",
        )
    fig.add_annotation(
        x=0.5 * L_mm,
        y=y_marker - 0.045 * D_mm,
        text=f"Span L = {L_mm:.0f} mm",
        showarrow=False,
        font=dict(size=11, color=ANNOTATION_TEXT),
        bgcolor=ANNOTATION_BG,
        bordercolor=ANNOTATION_BORDER,
        borderwidth=1,
        borderpad=3,
    )
    return y_marker - tick


def _add_deflection_depth_marker(fig: go.Figure, L_mm: float, D_mm: float) -> None:
    """Draw a visual-only depth marker tied to the active beam depth."""
    L_mm = float(L_mm)
    D_mm = float(D_mm)
    if L_mm <= 0.0 or D_mm <= 0.0 or not math.isfinite(L_mm) or not math.isfinite(D_mm):
        return

    x_marker = L_mm * 1.018
    tick = max(0.006 * L_mm, 18.0)
    fig.add_shape(
        type="line",
        x0=x_marker,
        y0=0.0,
        x1=x_marker,
        y1=-D_mm,
        line=dict(color=UNDEFORMED_LINE, width=1.0),
        layer="below",
    )
    for y_pos in (0.0, -D_mm):
        fig.add_shape(
            type="line",
            x0=x_marker - 0.5 * tick,
            y0=y_pos,
            x1=x_marker + 0.5 * tick,
            y1=y_pos,
            line=dict(color=UNDEFORMED_LINE, width=1.0),
            layer="below",
        )
    fig.add_annotation(
        x=x_marker + 0.004 * L_mm,
        y=-0.5 * D_mm,
        text=f"Depth D = {D_mm:.0f} mm",
        textangle=-90,
        showarrow=False,
        font=dict(size=11, color=ANNOTATION_TEXT),
        bgcolor=ANNOTATION_BG,
        bordercolor=ANNOTATION_BORDER,
        borderwidth=1,
        borderpad=3,
    )


def _deflection_to_scale_viewport(
    *,
    L_mm: float,
    y_min_needed: float,
    y_max_needed: float,
    width: int = DEFLECTION_VISUAL_WIDTH,
    height: int = DEFLECTION_VISUAL_HEIGHT,
    margin: dict[str, int] | None = None,
) -> tuple[list[float], list[float]]:
    """Return x/y ranges with equal mm-per-pixel scale where possible."""
    L_mm = float(L_mm)
    if L_mm <= 0.0 or not math.isfinite(L_mm):
        return [0.0, 1.0], [float(y_min_needed), float(y_max_needed)]

    margin = margin or DEFLECTION_VISUAL_MARGIN
    x_range = [-0.03 * L_mm, L_mm * 1.03]
    x_span = x_range[1] - x_range[0]
    plot_w = max(float(width - int(margin.get("l", 0)) - int(margin.get("r", 0))), 1.0)
    plot_h = max(float(height - int(margin.get("t", 0)) - int(margin.get("b", 0))), 1.0)
    y_span_to_scale = x_span * plot_h / plot_w
    needed_span = float(y_max_needed) - float(y_min_needed)
    y_span = max(y_span_to_scale, needed_span)
    y_mid = 0.5 * (float(y_min_needed) + float(y_max_needed))
    return x_range, [y_mid - 0.5 * y_span, y_mid + 0.5 * y_span]


def deflected_longitudinal_profile_mm(
    L_mm: float,
    support_type: str | None,
    delta_total: float,
    n_pts: int = 200,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Spanwise mesh and longitudinal deflection w (mm, negative sag), using the
    same normalised curvature template as the Deflection page diagram.
    """
    L_mm = float(L_mm)
    if L_mm <= 0.0 or not math.isfinite(L_mm):
        return np.array([0.0], dtype=float), np.array([0.0], dtype=float)
    delta_total = float(delta_total)
    if not math.isfinite(delta_total):
        delta_total = 0.0
    n_pts = max(2, int(n_pts))
    x = np.linspace(0.0, L_mm, n_pts)
    xi = x / L_mm
    shape_kind = _support_diagram_kind(support_type)
    if shape_kind == "cantilever_udl":
        shape = xi**2 * (3.0 - 2.0 * xi)
    elif shape_kind in (
        "continuous_span_udl",
        "fixed_fixed_udl",
        "fixed_pinned_udl",
    ):
        shape = (4.0 * xi * (1.0 - xi)) ** 2
    else:
        shape = 4.0 * xi * (1.0 - xi)
    shape = shape / max(float(np.max(shape)), 1.0)
    y_long = -delta_total * shape
    return x, y_long


def _safe_float(value, default: float = 0.0) -> float:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return float(default)
    if not math.isfinite(out):
        return float(default)
    return out


def _normalise_reo_layers(layers) -> list[dict]:
    if not isinstance(layers, list):
        return []
    out: list[dict] = []
    for layer in layers:
        if not isinstance(layer, dict):
            continue
        count_value = _safe_float(layer.get("count", layer.get("bars", 0)), 0.0)
        count = int(max(count_value, 0.0))
        spacing = _safe_float(layer.get("spacing", 0.0), 0.0)
        db = max(_safe_float(layer.get("db", layer.get("dia", 0.0)), 0.0), 0.0)
        y_from_top = layer.get("y_from_top_mm")
        y_from_top_val = None if y_from_top is None else _safe_float(y_from_top, float("nan"))
        if db <= 0.0 or (count <= 0 and spacing <= 0.0):
            continue
        out.append(
            {
                "count": count,
                "spacing": spacing,
                "db": db,
                "y_from_top_mm": y_from_top_val if y_from_top_val is not None and math.isfinite(y_from_top_val) else None,
            }
        )
    return out


def _add_deflection_reo_traces(
    fig: go.Figure,
    *,
    x: np.ndarray,
    w_vis: np.ndarray,
    D_mm: float,
    reo_layers: dict | None,
) -> None:
    if not isinstance(reo_layers, dict) or not x.size:
        return

    bottom_layers = _normalise_reo_layers(reo_layers.get("bottom"))
    top_layers = _normalise_reo_layers(reo_layers.get("top"))
    if not bottom_layers and not top_layers:
        return

    def _line_width(db: float, *, top: bool = False) -> float:
        if top:
            return max(2.0, min(4.6, db / 5.8))
        return max(2.3, min(5.2, db / 5.2))

    def _bottom_y(layer: dict, idx: int) -> np.ndarray:
        y_from_top = layer.get("y_from_top_mm")
        if y_from_top is None:
            offset_from_bottom = min(0.12 * D_mm + idx * 0.07 * D_mm, 0.86 * D_mm)
            return w_vis - D_mm + offset_from_bottom
        return w_vis - float(y_from_top)

    def _top_y(layer: dict, idx: int) -> np.ndarray:
        y_from_top = layer.get("y_from_top_mm")
        if y_from_top is None:
            return w_vis - min(0.12 * D_mm + idx * 0.07 * D_mm, 0.86 * D_mm)
        return w_vis - float(y_from_top)

    for idx, layer in enumerate(bottom_layers[:3]):
        fig.add_trace(
            go.Scatter(
                x=x,
                y=_bottom_y(layer, idx),
                mode="lines",
                line=dict(color=REO_BOTTOM, width=_line_width(float(layer["db"]))),
                name="Bottom reo" if idx == 0 else "Bottom reo row",
                hoverinfo="skip",
                showlegend=idx == 0,
                legendgroup="reo_bottom",
            )
        )

    for idx, layer in enumerate(top_layers[:3]):
        fig.add_trace(
            go.Scatter(
                x=x,
                y=_top_y(layer, idx),
                mode="lines",
                line=dict(color=REO_TOP, width=_line_width(float(layer["db"]), top=True)),
                name="Top reo" if idx == 0 else "Top reo row",
                hoverinfo="skip",
                showlegend=idx == 0,
                legendgroup="reo_top",
            )
        )


def build_deflected_shape_figure(
    x_mm,
    w_mm,
    L_mm,
    D_mm,
    support_type: str | None = None,
    continuous_end_side: str | None = None,
    support_pair: tuple[str, str] | None = None,
    *,
    undeformed_fillcolor: str | None = None,
    undeformed_line: dict | None = None,
    deflected_fillcolor: str | None = None,
    deflected_line: dict | None = None,
    reo_layers: dict | None = None,
    height: int = DEFLECTION_VISUAL_HEIGHT,
    show_legend: bool = True,
) -> go.Figure:
    """
    Illustrative deflected beam: undeformed and deflected rectangular bodies
    with vertical exaggeration. Hover on the deflected top fibre shows actual
    (unscaled) deflection from w_mm.
    """
    x = np.asarray(x_mm, dtype=float).reshape(-1)
    w = np.asarray(w_mm, dtype=float).reshape(-1)
    L_mm = float(L_mm)
    D_mm = float(max(D_mm, 1.0))

    st_val = _normalise_support_label(support_type)
    if x.size:
        stub = max(0.025 * L_mm, 20.0)
        if st_val == "Continuous - interior span":
            x0 = float(x[0])
            if x0 > -stub + 1e-6:
                left_pts = np.linspace(-stub, x0, 8, endpoint=False)
                if left_pts.size:
                    x = np.r_[left_pts, x]
                    w = np.r_[np.full_like(left_pts, w[0]), w]
        if st_val == "Continuous - end span" and str(continuous_end_side or "right").lower() == "left":
            x0 = float(x[0])
            if x0 > -stub + 1e-6:
                left_pts = np.linspace(-stub, x0, 8, endpoint=False)
                if left_pts.size:
                    x = np.r_[left_pts, x]
                    w = np.r_[np.full_like(left_pts, w[0]), w]
        if st_val == "Continuous - end span" and str(continuous_end_side or "right").lower() != "left":
            xn = float(x[-1])
            right_pts = np.linspace(xn, xn + stub, 8)[1:]
            if right_pts.size:
                x = np.r_[x, right_pts]
                w = np.r_[w, np.full_like(right_pts, w[-1])]
        if st_val == "Continuous - interior span":
            xn = float(x[-1])
            right_pts = np.linspace(xn, xn + stub, 8)[1:]
            if right_pts.size:
                x = np.r_[x, right_pts]
                w = np.r_[w, np.full_like(right_pts, w[-1])]

    max_abs_defl = float(np.max(np.abs(w))) if w.size else 0.0
    has_visible_deflection = max_abs_defl > 1e-6
    scale_factor = (
        diagram_deflection_visual_scale_factor(max_abs_defl, D_mm)
        if has_visible_deflection
        else 1.0
    )
    w_vis = w * scale_factor

    x_poly = np.r_[x, x[::-1], x[:1]]
    y_undeformed_poly = np.r_[np.zeros_like(x), (-D_mm) * np.ones_like(x)[::-1], [0.0]]
    y_deformed_poly = np.r_[w_vis, (w_vis - D_mm)[::-1], [w_vis[0]]]

    sf_display = f"{scale_factor:g}"

    u_fill = (
        undeformed_fillcolor
        if undeformed_fillcolor is not None
        else DIAGRAM_TRANSPARENT
    )
    u_line = (
        undeformed_line
        if undeformed_line is not None
        else dict(color=UNDEFORMED_LINE, width=1.5, dash="dash")
    )
    d_fill = (
        deflected_fillcolor
        if deflected_fillcolor is not None
        else CONCRETE_FILL_2D
    )
    d_line = (
        deflected_line
        if deflected_line is not None
        else dict(color=CONCRETE_OUTLINE, width=2)
    )

    fig = go.Figure()

    fig.add_trace(
        go.Scatter(
            x=x_poly,
            y=y_undeformed_poly,
            fill="toself",
            mode="lines",
            line=u_line,
            fillcolor=u_fill,
            name="Undeformed beam",
            hoverinfo="skip",
            legendgroup="u",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=x_poly,
            y=y_deformed_poly,
            fill="toself",
            mode="lines",
            line=d_line,
            fillcolor=d_fill,
            name="Deflected beam",
            hoverinfo="skip",
            legendgroup="d",
        )
    )

    _add_deflection_reo_traces(
        fig,
        x=x,
        w_vis=w_vis,
        D_mm=D_mm,
        reo_layers=reo_layers,
    )

    custom = np.column_stack([x, w])
    fig.add_trace(
        go.Scatter(
            x=x,
            y=w_vis,
            mode="lines",
            line=dict(
                color=DEFLECTED_LINE if has_visible_deflection else DIAGRAM_TRANSPARENT,
                width=2.4 if has_visible_deflection else 16,
            ),
            customdata=custom,
            hovertemplate="x = %{customdata[0]:.1f} mm<br>δ (actual) = %{customdata[1]:.2f} mm<extra></extra>",
            name="Deflection (hover)",
            showlegend=False,
        )
    )

    if w.size and has_visible_deflection:
        i_max = int(np.argmax(np.abs(w)))
        dmax_actual = float(w[i_max])
        fig.add_trace(
            go.Scatter(
                x=[x[i_max]],
                y=[w_vis[i_max]],
                mode="markers",
                marker=dict(
                    size=9,
                    color=MAX_DEFLECTION_MARKER,
                    symbol="circle",
                    line=dict(width=1, color=MARKER_OUTLINE),
                ),
                name="Max |δ|",
                hovertemplate=(
                    f"Δmax = {dmax_actual:.2f} mm (actual)<extra></extra>"
                ),
            )
        )
        fig.add_annotation(
            x=x[i_max],
            y=w_vis[i_max],
            text=f"Δmax = {dmax_actual:.2f} mm",
            showarrow=True,
            arrowhead=2,
            arrowsize=1,
            arrowwidth=1,
            axref="pixel",
            ayref="pixel",
            ax=48,
            ay=-42,
            font=dict(size=11, color=ANNOTATION_TEXT),
            bgcolor=ANNOTATION_BG,
            bordercolor=ANNOTATION_BORDER,
            borderwidth=1,
            borderpad=4,
        )

    _add_deflection_supports_plotly(fig, support_type, L_mm, D_mm, support_pair=support_pair)
    support_y_min, support_y_max = _deflection_support_y_bounds(
        support_type,
        D_mm,
        support_pair=support_pair,
    )
    y_min_needed = min(
        float(np.min(w_vis - D_mm)) if w_vis.size else -D_mm,
        support_y_min,
    )
    y_max_needed = max(
        float(np.max(w_vis)) if w_vis.size else 0.0,
        support_y_max,
        0.0,
    )
    layout_margin = dict(DEFLECTION_VISUAL_MARGIN)
    x_range, y_range = _deflection_to_scale_viewport(
        L_mm=L_mm,
        y_min_needed=y_min_needed,
        y_max_needed=y_max_needed,
        height=height,
        margin=layout_margin,
    )

    fig.update_layout(
        title=dict(
            text="",
            x=0.5,
            xanchor="center",
            font=dict(size=13, color=TITLE_TEXT),
        ),
        xaxis_title="",
        yaxis_title="",
        template="simple_white",
        plot_bgcolor=DIAGRAM_BG,
        paper_bgcolor=DIAGRAM_BG,
        width=DEFLECTION_VISUAL_WIDTH,
        height=height,
        margin=layout_margin,
        showlegend=show_legend,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1,
            traceorder="normal",
        ),
        xaxis=dict(
            visible=False,
            showgrid=False,
            showticklabels=False,
            showline=False,
            ticks="",
            zeroline=False,
            fixedrange=True,
            range=x_range,
        ),
        yaxis=dict(
            visible=False,
            showgrid=False,
            showticklabels=False,
            showline=False,
            ticks="",
            zeroline=False,
            fixedrange=True,
            range=y_range,
            scaleanchor="x",
            scaleratio=1,
        ),
        hovermode="closest",
    )
    return fig


build_deflected_beam_plotly = build_deflected_shape_figure
