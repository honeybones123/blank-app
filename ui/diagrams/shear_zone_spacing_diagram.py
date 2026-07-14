"""Shear link spacing zone strip diagram builders."""

from __future__ import annotations

from typing import Any

import plotly.graph_objects as go


def build_zone_spacing_strip_figure(
    design: Any,
    *,
    beam_depth_m: float = 0.25,
    title: str | None = None,
) -> go.Figure:
    """Plotly figure: horizontal strip under a notional beam axis."""
    L = 0.0
    for seg in design.segments:
        L = max(L, seg.x1_m)

    fig = go.Figure()
    y0, y1 = 0.0, beam_depth_m
    for seg in design.segments:
        fig.add_shape(
            type="rect",
            x0=seg.x0_m,
            x1=seg.x1_m,
            y0=y0,
            y1=y1,
            fillcolor=seg.color,
            line=dict(width=0),
            layer="below",
        )
        xm = 0.5 * (seg.x0_m + seg.x1_m)
        fig.add_annotation(
            x=xm,
            y=y1 + 0.06 * beam_depth_m,
            text=f"s = {seg.s_mm:.0f} mm",
            showarrow=False,
            font=dict(size=10, color="rgba(45,45,45,0.92)"),
        )
    fig.add_trace(
        go.Scatter(
            x=[0.0, L],
            y=[y1 * 0.5, y1 * 0.5],
            mode="lines",
            line=dict(color="rgba(40,40,40,0.85)", width=2),
            hoverinfo="skip",
            showlegend=False,
        )
    )
    fig.update_xaxes(title_text="Distance along member (m)", range=[0.0, max(L, 1e-6)])
    fig.update_yaxes(visible=False, range=[-0.05 * beam_depth_m, y1 + 0.22 * beam_depth_m])
    fig.update_layout(
        title=title or "Shear link spacing zones (detailing envelope)",
        margin=dict(l=40, r=20, t=50, b=40),
        height=140,
        showlegend=False,
    )
    return fig
