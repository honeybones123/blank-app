1. Imports to add at top of bending_diagrams.py
import math
import numpy as np
import matplotlib.pyplot as plt  # you can keep this for other figs if needed
from matplotlib.patches import Rectangle, Circle
import streamlit as st

import plotly.graph_objects as go
from plotly.subplots import make_subplots

from state_and_helpers import get_param
from bending_core import _layout_bars_in_rows
from section_layout import compute_section_layout  # <- from earlier helper


(If you’re not using the Matplotlib bits elsewhere, you can eventually clean them out, but no need right now.)

2. New Plotly version of _plot_stress_strain_profiles

Replace the entire existing _plot_stress_strain_profiles in bending_diagrams.py with this Plotly version:

def _plot_stress_strain_profiles(state_dict, state_label=None):
    """
    Three-panel Plotly figure:

        - Section (left)    – uses same layout as Inputs 2D diagram
        - Strain (centre)
        - Stress (right)

    All rendered with Plotly, no axes/grid, with compression zone
    changing with ULS / SLS / Uncracked.
    """
    if state_label is None:
        try:
            state_label = st.session_state.get(
                "bending_strain_state_local", "ULS"
            )
        except Exception:
            state_label = "ULS"

    # unpack bending state
    b = state_dict["b"]
    D = state_dict["D"]
    d = state_dict["d"]
    c = state_dict["c"]
    eps_c_raw = state_dict["eps_c"]
    eps_s_raw = state_dict["eps_s"]
    gamma = state_dict["gamma"]
    fs_t = state_dict["fs_t"]
    fc = state_dict["fc"]
    alpha2 = state_dict["alpha2"]

    # sign convention – concrete +, steel − (for plotting)
    eps_c = abs(eps_c_raw)
    eps_s = -abs(eps_s_raw)

    # scales
    eps_max = max(abs(eps_c), abs(eps_s), 1e-4) * 1.3
    sigma_c = alpha2 * fc
    sigma_s = abs(fs_t)
    stress_max = max(sigma_c, sigma_s, 1.0)

    # -------------------------------------
    # Create 3-column subplot figure
    # -------------------------------------
    fig = make_subplots(
        rows=1,
        cols=3,
        shared_y=True,
        column_widths=[0.9, 0.9, 1.2],
        horizontal_spacing=0.08,
        specs=[[{"type": "xy"}, {"type": "xy"}, {"type": "xy"}]],
        subplot_titles=("Section", "Strain", "Stress (MPa)"),
    )

    # consistent y-range across panels (0 at top, D at bottom)
    y_range = [D * 1.05, -0.05 * D]

    # hide all axes, no grid / ticks
    for i in range(1, 4):
        fig.update_xaxes(
            visible=False,
            row=1,
            col=i,
            showgrid=False,
            zeroline=False,
        )
        fig.update_yaxes(
            visible=False,
            row=1,
            col=i,
            showgrid=False,
            zeroline=False,
            range=y_range,
        )

    # =====================================================
    # 1) SECTION PANEL – use same layout as Inputs 2D
    # =====================================================
    layout = compute_section_layout()
    b = layout["b"]
    D = layout["D"]
    cage = layout["cage"]
    bot = layout["bot"]
    top = layout["top"]

    # outer concrete
    fig.add_shape(
        type="rect",
        x0=0,
        y0=0,
        x1=b,
        y1=D,
        line=dict(color="black", width=1.2),
        fillcolor="rgba(0,0,0,0)",
        row=1,
        col=1,
    )

    # lig cage (just outline for now – matches Inputs)
    fig.add_shape(
        type="rect",
        x0=cage["x0"],
        y0=cage["y0"],
        x1=cage["x1"],
        y1=cage["y1"],
        line=dict(color="black", width=1.0),
        fillcolor="rgba(0,0,0,0)",
        row=1,
        col=1,
    )

    # compression zone – depth depends on state
    if state_label == "ULS":
        block_depth_sec = max(0.0, min(gamma * c, D))
    else:
        block_depth_sec = max(0.0, min(c, D))

    fig.add_shape(
        type="rect",
        x0=0,
        y0=0,
        x1=b,
        y1=block_depth_sec,
        line=dict(color="red", width=1.0),
        fillcolor="rgba(199,227,255,0.7)",
        row=1,
        col=1,
    )

    # bottom bars
    if bot["x"]:
        fig.add_trace(
            go.Scatter(
                x=bot["x"],
                y=bot["y"],
                mode="markers",
                marker=dict(
                    color="red",
                    size=7,
                    line=dict(width=0.7, color="black"),
                ),
                hoverinfo="skip",
                showlegend=False,
            ),
            row=1,
            col=1,
        )

    # top bars
    if top["x"]:
        fig.add_trace(
            go.Scatter(
                x=top["x"],
                y=top["y"],
                mode="markers",
                marker=dict(
                    color="blue",
                    size=7,
                    line=dict(width=0.7, color="black"),
                ),
                hoverinfo="skip",
                showlegend=False,
            ),
            row=1,
            col=1,
        )

    # keep section 1:1 in x–y (width vs depth)
    fig.update_yaxes(
        scaleanchor="x",
        scaleratio=1,
        row=1,
        col=1,
    )

    # =====================================================
    # 2) STRAIN PANEL
    # =====================================================
    # We work in a [0,1] x [0,D] local panel, map eps → x.
    panel_x_center = 0.5
    half_w = 0.35

    def strain_to_x(eps):
        return panel_x_center + (eps / eps_max) * half_w

    x_c = strain_to_x(eps_c)
    x_s = strain_to_x(eps_s)
    x_mid = panel_x_center

    # strain line (top → NA → steel)
    fig.add_trace(
        go.Scatter(
            x=[x_c, x_mid, x_s],
            y=[0, c, d],
            mode="lines",
            line=dict(color="black", width=1.0),
            hoverinfo="skip",
            showlegend=False,
        ),
        row=1,
        col=2,
    )

    # neutral axis (dashed)
    fig.add_shape(
        type="line",
        x0=panel_x_center - 0.5,
        y0=c,
        x1=panel_x_center + 0.5,
        y1=c,
        line=dict(color="black", width=0.7, dash="dash"),
        row=1,
        col=2,
    )

    # labels for eps_c, eps_s
    fig.add_annotation(
        x=x_c,
        y=0,
        text=f"ε_c = {eps_c:.4f}",
        showarrow=False,
        font=dict(size=9, color="red"),
        yshift=-10,
        row=1,
        col=2,
    )
    fig.add_annotation(
        x=x_s,
        y=d,
        text=f"ε_s = {eps_s:.4f}",
        showarrow=False,
        font=dict(size=9, color="blue"),
        yshift=10,
        row=1,
        col=2,
    )

    # =====================================================
    # 3) STRESS PANEL
    # =====================================================
    # Local panel x ∈ [0,1], y ∈ [0,D]; map stress → width.
    x_axis = 0.1
    usable_width = 0.7

    def stress_to_x(sig):
        return x_axis + (sig / stress_max) * usable_width

    x_T = stress_to_x(sigma_s)
    x_block_right = x_axis + (x_T - x_axis) * (1.0 / 3.0)

    # vertical "axis"
    fig.add_shape(
        type="line",
        x0=x_axis,
        y0=0,
        x1=x_axis,
        y1=D,
        line=dict(color="black", width=1.0),
        row=1,
        col=3,
    )

    # tension arrow (T) at depth d
    fig.add_annotation(
        x=x_T,
        y=d,
        ax=x_axis,
        ay=d,
        xref="x3",
        yref="y3",
        axref="x3",
        ayref="y3",
        text="",
        showarrow=True,
        arrowhead=3,
        arrowsize=1.0,
        arrowwidth=1.2,
        arrowcolor="blue",
        row=1,
        col=3,
    )
    fig.add_annotation(
        x=x_T + 0.04,
        y=d,
        text=f"T ({sigma_s:.0f} MPa)",
        showarrow=False,
        font=dict(size=9, color="blue"),
        xanchor="left",
        row=1,
        col=3,
    )

    # compression block
    if state_label == "ULS":
        block_top = 0
        block_bottom = gamma * c
        # rectangle
        fig.add_shape(
            type="rect",
            x0=x_axis,
            y0=block_top,
            x1=x_block_right,
            y1=block_bottom,
            line=dict(color="red", width=1.0),
            fillcolor="rgba(255,200,200,0.0)",
            row=1,
            col=3,
        )
    else:
        block_top = 0
        block_bottom = c
        # triangular wedge – draw as polygon
        fig.add_trace(
            go.Scatter(
                x=[x_axis, x_axis, x_block_right, x_axis],
                y=[block_bottom, block_top, block_top, block_bottom],
                mode="lines",
                fill="none",
                line=dict(color="red", width=1.0),
                hoverinfo="skip",
                showlegend=False,
            ),
            row=1,
            col=3,
        )

    # dashed NA in stress panel
    fig.add_shape(
        type="line",
        x0=x_axis - 0.05,
        y0=c,
        x1=x_axis + usable_width + 0.05,
        y1=c,
        line=dict(color="black", width=0.7, dash="dash"),
        row=1,
        col=3,
    )

    # α2 f'c arrow + label (approx double-headed)
    y_alpha = -0.07 * D
    fig.add_annotation(
        x=x_block_right,
        y=y_alpha,
        ax=x_axis,
        ay=y_alpha,
        xref="x3",
        yref="y3",
        axref="x3",
        ayref="y3",
        text="",
        showarrow=True,
        arrowhead=3,
        arrowsize=1.0,
        arrowwidth=0.8,
        arrowcolor="red",
        row=1,
        col=3,
    )
    fig.add_annotation(
        x=(x_axis + x_block_right) / 2.0,
        y=y_alpha - 0.03 * D,
        text=f"α₂ f'c = {sigma_c:.0f} MPa",
        showarrow=False,
        font=dict(size=9, color="red"),
        xanchor="center",
        row=1,
        col=3,
    )

    # γ d_n / d_n depth arrow + label
    x_gc = x_block_right + 0.08
    fig.add_annotation(
        x=x_gc,
        y=block_bottom,
        ax=x_gc,
        ay=block_top,
        xref="x3",
        yref="y3",
        axref="x3",
        ayref="y3",
        text="",
        showarrow=True,
        arrowhead=3,
        arrowsize=1.0,
        arrowwidth=0.8,
        arrowcolor="red",
        row=1,
        col=3,
    )
    depth_label = (
        f"γ dₙ = {gamma * c:.0f} mm"
        if state_label == "ULS"
        else f"dₙ = {c:.0f} mm"
    )
    fig.add_annotation(
        x=x_gc + 0.04,
        y=(block_top + block_bottom) / 2.0,
        text=depth_label,
        showarrow=False,
        font=dict(size=9, color="red"),
        xanchor="left",
        row=1,
        col=3,
    )

    # internal compression arrows facing LEFT inside block
    for frac in [0.25, 0.5, 0.75]:
        y_mid = block_top + frac * (block_bottom - block_top)
        fig.add_annotation(
            x=x_axis + 0.15 * (x_block_right - x_axis),
            y=y_mid,
            ax=x_block_right - 0.15 * (x_block_right - x_axis),
            ay=y_mid,
            xref="x3",
            yref="y3",
            axref="x3",
            ayref="y3",
            text="",
            showarrow=True,
            arrowhead=3,
            arrowsize=0.9,
            arrowwidth=0.7,
            arrowcolor="red",
            row=1,
            col=3,
        )

    # -------------------------------------
    # Final layout: no legend, tight margins
    # -------------------------------------
    fig.update_layout(
        showlegend=False,
        margin=dict(l=10, r=10, t=40, b=10),
        height=320,
        width=900,
    )

    return fig

3. How to render it on the bending page

Wherever you currently have something like:

fig_ss = _plot_stress_strain_profiles(ss_state)
st.pyplot(fig_ss)


change to:

fig_ss = _plot_stress_strain_profiles(ss_state)
st.plotly_chart(fig_ss, use_container_width=True)
