"""Canonical Plotly section renderer for the authoritative SLS bending checks."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import plotly.graph_objects as go

from section_layout import compute_section_layout


_STATE_COLOURS = {
    "tension": "#dc2626",
    "compression": "#2563eb",
    "neutral": "#64748b",
}


def _physical_segments(layout: Mapping[str, Any]) -> tuple[tuple[float, float, float, float], ...]:
    """Return section rectangles as (x0, x1, y0, y1) in real section coordinates."""

    shape_name = str(layout.get("shape_name", "Rectangle (b × D)") or "Rectangle (b × D)")
    dims = dict(layout.get("dims", {}) or {})
    depth = float(layout.get("D", dims.get("D", 0.0)) or 0.0)

    if shape_name.startswith("T-Section"):
        flange_width = float(dims.get("bf", layout.get("b", 0.0)) or 0.0)
        flange_thickness = max(0.0, min(depth, float(dims.get("tf", 0.0) or 0.0)))
        web_width = float(dims.get("bw", dims.get("tw", flange_width)) or flange_width)
        centre = flange_width / 2.0
        return (
            (0.0, flange_width, 0.0, flange_thickness),
            (centre - web_width / 2.0, centre + web_width / 2.0, flange_thickness, depth),
        )

    if shape_name.startswith("I-Section"):
        flange_width = float(dims.get("bf", layout.get("b", 0.0)) or 0.0)
        flange_thickness = max(0.0, min(depth / 2.0, float(dims.get("tf", 0.0) or 0.0)))
        web_width = float(dims.get("tw", dims.get("bw", flange_width)) or flange_width)
        centre = flange_width / 2.0
        return (
            (0.0, flange_width, 0.0, flange_thickness),
            (centre - web_width / 2.0, centre + web_width / 2.0, flange_thickness, depth - flange_thickness),
            (0.0, flange_width, depth - flange_thickness, depth),
        )

    width = float(layout.get("b", dims.get("b", 0.0)) or 0.0)
    return ((0.0, width, 0.0, depth),)


def _nearest_layer(layers: tuple[Mapping[str, Any], ...], y_top: float) -> Mapping[str, Any] | None:
    if not layers:
        return None
    return min(
        layers,
        key=lambda layer: abs(float(layer.get("depth_from_top_mm", 0.0) or 0.0) - y_top),
    )


def _bar_points(layout: Mapping[str, Any]) -> tuple[Mapping[str, Any], ...]:
    points = tuple(
        point
        for point in tuple(layout.get("reo_points", ()) or ())
        if isinstance(point, Mapping)
        and float(point.get("db", 0.0) or 0.0) > 0.0
    )
    if points:
        return points

    # Conservative fallback for older rectangle layout publications.
    collected: list[dict[str, Any]] = []
    reo_layout = dict(layout.get("reo_layout", {}) or {})
    for face in ("top", "bottom"):
        for band in tuple(reo_layout.get(face, ()) or ()):
            if not isinstance(band, Mapping):
                continue
            db = float(band.get("db", 0.0) or 0.0)
            xs = tuple(band.get("x", ()) or ())
            ys = band.get("y", 0.0)
            if isinstance(ys, (list, tuple)):
                y_values = tuple(float(y) for y in ys)
            else:
                y_values = tuple(float(ys or 0.0) for _ in xs)
            for x, y in zip(xs, y_values):
                collected.append({"x": float(x), "y": y, "db": db, "layer": face})
    return tuple(collected)


def make_sls_canonical_section_figure(
    result: Mapping[str, Any],
    *,
    layout: Mapping[str, Any] | None = None,
) -> go.Figure:
    """Render one SLS cracked section using the app's canonical section-layout inputs.

    Physical geometry/reinforcement comes from ``compute_section_layout`` (the same
    source used by the other Plotly section diagrams). The authoritative SLS result
    contributes only the converged neutral axis and each layer's SLS state/inclusion.
    """

    canonical = dict(layout or compute_section_layout())
    dims = dict(canonical.get("dims", {}) or {})
    depth = float(canonical.get("D", dims.get("D", result.get("depth_mm", 0.0))) or 0.0)
    width = float(canonical.get("b", dims.get("b", dims.get("bf", result.get("width_mm", 0.0)))) or 0.0)
    if depth <= 0.0:
        depth = max(1.0, float(result.get("depth_mm", 1.0) or 1.0))
    if width <= 0.0:
        width = max(1.0, float(result.get("width_mm", 1.0) or 1.0))

    dn_top = max(
        0.0,
        min(depth, float(result.get("neutral_axis_depth_from_top_mm", 0.0) or 0.0)),
    )
    compression_face = str(result.get("compression_face", "top") or "top").lower()
    if compression_face == "bottom":
        compression_y0, compression_y1 = dn_top, depth
        cracked_y0, cracked_y1 = 0.0, dn_top
    else:
        compression_y0, compression_y1 = 0.0, dn_top
        cracked_y0, cracked_y1 = dn_top, depth

    layers = tuple(
        layer for layer in tuple(result.get("layers", ()) or ()) if isinstance(layer, Mapping)
    )
    segments = _physical_segments(canonical)
    fig = go.Figure()

    for x0, x1, y0, y1 in segments:
        active_y0 = max(y0, compression_y0)
        active_y1 = min(y1, compression_y1)
        if active_y1 > active_y0:
            fig.add_shape(
                type="rect",
                x0=x0,
                x1=x1,
                y0=active_y0,
                y1=active_y1,
                line=dict(width=0),
                fillcolor="rgba(96,165,250,0.22)",
                layer="below",
            )

        cracked_part_y0 = max(y0, cracked_y0)
        cracked_part_y1 = min(y1, cracked_y1)
        if cracked_part_y1 > cracked_part_y0:
            fig.add_shape(
                type="rect",
                x0=x0,
                x1=x1,
                y0=cracked_part_y0,
                y1=cracked_part_y1,
                line=dict(width=0),
                fillcolor="rgba(248,250,252,0.78)",
                layer="below",
            )

        fig.add_shape(
            type="rect",
            x0=x0,
            x1=x1,
            y0=y0,
            y1=y1,
            line=dict(color="#0f172a", width=1.7),
            fillcolor="rgba(255,255,255,0)",
            layer="below",
        )

    # Draw the physical ligature cage when the canonical layout publishes a simple cage.
    lig = dict(canonical.get("lig", {}) or {})
    cage = dict(canonical.get("cage", {}) or {})
    lig_d = float(lig.get("d", 0.0) or 0.0)
    if lig_d > 0.0 and all(key in cage for key in ("x0", "x1", "y0", "y1")):
        fig.add_shape(
            type="rect",
            x0=float(cage["x0"]),
            x1=float(cage["x1"]),
            y0=float(cage["y0"]),
            y1=float(cage["y1"]),
            line=dict(color="#334155", width=max(1.0, min(2.5, lig_d / 5.0))),
            fillcolor="rgba(0,0,0,0)",
        )
        for x in tuple(lig.get("internal_x", ()) or ()):
            fig.add_shape(
                type="line",
                x0=float(x),
                x1=float(x),
                y0=float(cage["y0"]),
                y1=float(cage["y1"]),
                line=dict(color="#334155", width=max(1.0, min(2.5, lig_d / 5.0))),
            )

    # Draw every real longitudinal bar at its real centre and diameter.
    for point in _bar_points(canonical):
        x = float(point.get("x", 0.0) or 0.0)
        y = float(point.get("y", 0.0) or 0.0)
        db = float(point.get("db", 0.0) or 0.0)
        if db <= 0.0:
            continue
        layer = _nearest_layer(layers, y)
        state = str(layer.get("state", "neutral") if layer else "neutral")
        included = bool(layer.get("included", True)) if layer else True
        colour = _STATE_COLOURS.get(state, _STATE_COLOURS["neutral"])
        radius = db / 2.0
        fig.add_shape(
            type="circle",
            x0=x - radius,
            x1=x + radius,
            y0=y - radius,
            y1=y + radius,
            line=dict(color=colour, width=2.0 if included else 1.2, dash="solid" if included else "dot"),
            fillcolor=colour if included else "rgba(255,255,255,0.88)",
        )

    fig.add_shape(
        type="line",
        x0=-0.05 * width,
        x1=1.08 * width,
        y0=dn_top,
        y1=dn_top,
        line=dict(color="#7c3aed", width=2, dash="dash"),
    )
    fig.add_annotation(
        x=1.10 * width,
        y=dn_top,
        text=f"d<sub>n</sub> = {dn_top:.1f} mm",
        showarrow=False,
        xanchor="left",
        font=dict(color="#6d28d9", size=10),
    )

    if compression_y1 - compression_y0 > 0.08 * depth:
        fig.add_annotation(
            x=0.5 * width,
            y=0.5 * (compression_y0 + compression_y1),
            text="Active concrete<br>compression region",
            showarrow=False,
            align="center",
            font=dict(color="#1d4ed8", size=10),
        )
    if cracked_y1 - cracked_y0 > 0.12 * depth:
        fig.add_annotation(
            x=0.5 * width,
            y=0.5 * (cracked_y0 + cracked_y1),
            text="Cracked concrete tension<br>inactive",
            showarrow=False,
            align="center",
            font=dict(color="#64748b", size=9),
        )

    # Keep authoritative SLS layer labels/state beside the real physical bars.
    for layer in layers:
        y = float(layer.get("depth_from_top_mm", 0.0) or 0.0)
        state = str(layer.get("state", "neutral") or "neutral")
        included = bool(layer.get("included", True))
        factor = float(layer.get("transformed_factor", 0.0) or 0.0)
        label = str(layer.get("label", layer.get("layer_id", "Layer")))
        factor_text = "omitted" if not included else f"{factor:.3g} A<sub>s</sub>"
        fig.add_annotation(
            x=1.10 * width,
            y=y,
            text=f"{label} — {state}<br>{factor_text}",
            showarrow=False,
            xanchor="left",
            align="left",
            font=dict(color=_STATE_COLOURS.get(state, _STATE_COLOURS["neutral"]), size=9),
        )

    fig.add_annotation(
        x=0.5 * width,
        y=-0.07 * depth,
        text=f"b = {width:.0f} mm",
        showarrow=False,
        font=dict(color="#475569", size=9),
    )
    fig.add_annotation(
        x=-0.10 * width,
        y=0.5 * depth,
        text=f"D = {depth:.0f} mm",
        textangle=-90,
        showarrow=False,
        font=dict(color="#475569", size=9),
    )

    fig.add_trace(
        go.Scatter(
            x=[0.0],
            y=[0.0],
            mode="markers",
            marker=dict(size=1, color="rgba(0,0,0,0)"),
            hoverinfo="skip",
            showlegend=False,
        )
    )
    fig.update_xaxes(
        range=[-0.18 * width, 1.58 * width],
        visible=False,
        fixedrange=True,
        constrain="domain",
    )
    fig.update_yaxes(
        range=[depth * 1.08, -depth * 0.12],
        visible=False,
        fixedrange=True,
        scaleanchor="x",
        scaleratio=1,
    )
    fig.update_layout(
        height=430,
        margin=dict(l=10, r=15, t=20, b=20),
        plot_bgcolor="#ffffff",
        paper_bgcolor="#ffffff",
        showlegend=False,
        dragmode=False,
    )
    return fig


__all__ = ["make_sls_canonical_section_figure"]
