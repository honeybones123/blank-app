"""Creep and shrinkage teaching schematic figure builders."""

from __future__ import annotations

import numpy as np
import plotly.graph_objects as go


_SHRINKAGE_EVAPORATION_BLUE = "#1f77b4"


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
            arrowcolor=_SHRINKAGE_EVAPORATION_BLUE,
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
        font=dict(size=18, color=_SHRINKAGE_EVAPORATION_BLUE),
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
