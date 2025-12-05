# bending_diagrams.py
import math
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, Circle
import streamlit as st

import plotly.graph_objects as go
from plotly.subplots import make_subplots

from state_and_helpers import get_param
from bending_core import _layout_bars_in_rows
from section_layout import compute_section_layout

# ------------------------------------------------------------
# Global styling constants
# ------------------------------------------------------------
LINE_THICK = 1.0   # main outlines
LINE_MED   = 0.8   # normal lines
LINE_THIN  = 0.6   # light lines

FS_TITLE  = 8      # diagram titles
FS_LABEL  = 7      # axis labels / main text
FS_ANNOT  = 5      # small annotations

ARROW_SCALE = 4    # small arrowheads for everything


# ============================================================
#  MAIN 3-PANEL SECTION / STRAIN / STRESS DIAGRAM
# ============================================================
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


# ============================================================
#  ULS STRESS BLOCK FIGURE (1.1 / 1.3 VARIANTS)
# ============================================================
def _make_uls_stress_block_figure(
    b_mm: float,
    D_mm: float,
    d_mm: float,
    dn_mm: float,
    a_mm: float,
    alpha2: float,
    gamma: float,
    fc: float,
    fsy: float,
    show_lever_arm: bool = False,
    show_dn: bool = True,
    show_alpha_label: bool = True,
    show_C: bool = False,
    C_N: float | None = None,
    variant: str = "11",
):
    """
    Warner-style ULS stress block (right-way up)

    Flags:
      - show_lever_arm:   show / hide z arrow
      - show_dn:          show / hide dashed d_n line + label
      - show_alpha_label: show / hide α2 f'c text + width arrow
      - show_C:           show concrete C arrow at centroid (for 1.2)
      - variant: "11" (shorter figure for Section 1.1),
                 "13" (slightly taller for Section 1.3)
    """

    vals = [b_mm, D_mm, d_mm, dn_mm, a_mm, alpha2, gamma, fc, fsy]
    if any(v is None or (isinstance(v, float) and math.isnan(v)) for v in vals):
        fig, ax = plt.subplots()
        ax.axis("off")
        ax.text(0.5, 0.5, "No data", ha="center", va="center")
        return fig

    sigma_c = alpha2 * fc  # MPa

    # Make sure the vertical span always includes d, d_n and a.
    base_span = max(D_mm, d_mm, dn_mm, a_mm)

    if variant == "13":
        D_ref = base_span * 1.05      # axis height
        # 1:1 aspect ratio, same depth as calc box
        fig_width = 3.0
        fig_height = 3.0  # Square figure for 1:1 aspect
        use_equal_aspect = True
    else:  # "11" – 1:1 aspect ratio, same depth as calc box
        D_ref = base_span * 1.05
        # Use square figure size to support 1:1 aspect ratio
        # Match the depth of the calc box by using similar vertical extent
        fig_width = 3.0
        fig_height = 3.0  # Square figure for 1:1 aspect
        use_equal_aspect = True

    fig, ax = plt.subplots(figsize=(fig_width, fig_height))
    # Extend xlim for variants "11" and "13" to accommodate wider stress block and tension arrow (4:1 ratio)
    xlim_max = 320.0 if use_equal_aspect else 100.0
    ax.set_xlim(0.0, xlim_max)
    ax.set_ylim(D_ref, 0.0)  # 0 at top
    if use_equal_aspect:
        ax.set_aspect("equal", adjustable="box")
    ax.axis("off")

    # vertical axis
    x_axis = 20.0
    ax.plot(
        [x_axis, x_axis],
        [0.0, D_ref],
        color="black",
        linewidth=LINE_THICK,
    )

    # block
    block_left = x_axis
    block_width = 88.0  # 4:1 ratio (4x original 22.0)
    block_top = 0.0
    block_bottom = a_mm
    
    # Consistent label spacing from stress block/arrows
    label_spacing = 4.0

    ax.add_patch(
        Rectangle(
            (block_left, block_top),
            block_width,
            block_bottom - block_top,
            fill=False,
            edgecolor="tab:red",
            linewidth=LINE_MED,
        )
    )

    # compression arrows – face LEFT
    block_h = block_bottom - block_top
    if block_h > 0:
        ys = np.linspace(
            block_top + 0.2 * block_h,
            block_bottom - 0.2 * block_h,
            3,
        )
        for yy in ys:
            ax.annotate(
                "",
                xy=(block_left + 2.0, yy),
                xytext=(block_left + block_width - 2.0, yy),
                arrowprops=dict(
                    arrowstyle="->",
                    color="tab:red",
                    linewidth=LINE_MED,
                    mutation_scale=ARROW_SCALE,
                ),
            )

    # α2 f'c width arrow + label (optional)
    if show_alpha_label:
        y_alpha = -0.08 * D_ref
        ax.annotate(
            "",
            xy=(block_left, y_alpha),
            xytext=(block_left + block_width, y_alpha),
            arrowprops=dict(
                arrowstyle="<->",
                linewidth=LINE_THIN,
                color="tab:red",
                mutation_scale=ARROW_SCALE,
            ),
        )
        # α₂ f'c label positioned much closer to the arrow (left side), moved down slightly
        ax.text(
            block_left + 5.0,  # Closer to the arrow start, not far to the left
            y_alpha - 0.03 * D_ref,  # Moved down slightly (reduced from 0.05 to 0.03)
            f"α₂ f'c = {sigma_c:.0f} MPa",
            ha="left",
            va="bottom",
            fontsize=FS_LABEL,
            color="tab:red",
        )

    # dashed d_n line + label (optional)
    if show_dn:
        # Extend dn line much further to avoid overlap with z line
        # Position it well past the "a" label but before z line
        x_dn_end = block_left + block_width + label_spacing + 10.0  # Extended further
        ax.hlines(
            dn_mm,
            x_axis,
            x_dn_end,
            linestyles="--",
            colors="tab:blue",
            linewidth=LINE_MED,
        )
        x_dn_label = x_dn_end
        ax.text(
            x_dn_label + label_spacing,
            dn_mm + 0.03 * D_ref,
            f"dₙ = {dn_mm:.1f} mm",
            ha="left",
            va="bottom",
            fontsize=FS_LABEL,
            color="tab:blue",
        )

    # a label - consistent spacing from stress block
    ax.text(
        block_left + block_width + label_spacing,
        0.5 * a_mm,
        f"a = γ dₙ = {a_mm:.1f} mm",
        ha="left",
        va="center",
        fontsize=FS_LABEL,
        color="tab:blue",
    )

    # bottom tension arrow (now guaranteed to be inside the axes)
    # 4:1 ratio (4x original width)
    tension_arrow_end = x_axis + 4.0 * (90.0 - x_axis)  # 20.0 + 4*70.0 = 300.0
    ax.annotate(
        "",
        xy=(tension_arrow_end, d_mm),
        xytext=(x_axis, d_mm),
        arrowprops=dict(
            arrowstyle="->",
            linewidth=LINE_MED,
            color="tab:blue",
            mutation_scale=ARROW_SCALE,
        ),
    )
    # Consistent spacing from arrow end
    ax.text(
        tension_arrow_end + label_spacing,
        d_mm,
        f"T ({fsy:.0f} MPa)",
        ha="left",
        va="center",
        fontsize=FS_LABEL,
        color="tab:blue",
    )

    # optional C arrow at centroid of block (for 1.2)
    if show_C and C_N is not None:
        y_C = 0.5 * a_mm
        x_C_tail = block_left + block_width + 18.0
        x_C_head = block_left + block_width + label_spacing
        ax.annotate(
            "",
            xy=(x_C_head, y_C),
            xytext=(x_C_tail, y_C),
            arrowprops=dict(
                arrowstyle="->",
                linewidth=LINE_MED,
                color="tab:red",
                mutation_scale=ARROW_SCALE,
            ),
        )
        ax.text(
            x_C_tail + label_spacing,
            y_C,
            f"C = {C_N/1000.0:.1f} kN",
            ha="left",
            va="center",
            fontsize=FS_LABEL,
            color="tab:red",
        )

    # optional lever arm - REMOVED per user request
    # if show_lever_arm:
    #     y_C = 0.5 * a_mm
    #     x_z = block_left + block_width + label_spacing + 5.0
    #     ax.annotate(...)
    #     ax.text(...)

    # Center label based on xlim
    x_center = xlim_max / 2.0
    ax.text(
        x_center,
        D_ref + 0.07 * D_ref,
        "Stress (MPa)",
        ha="center",
        va="bottom",
        fontsize=FS_TITLE,
    )

    return fig


# ============================================================
#  SIMPLE ULS FORCE MODEL FIGURE (1.6)
# ============================================================
def _make_uls_force_model_figure(
    D_mm: float,
    d_mm: float,
    a_mm: float,
    C_N: float | None = None,
    T_N: float | None = None,
):
    """
    Simple C–T–z force model for Section 1.6.
    Matches calc-box height and aligns C/T symmetrically.
    """

    vals = [D_mm, d_mm, a_mm]
    if any(v is None or (isinstance(v, float) and math.isnan(v)) for v in vals):
        fig, ax = plt.subplots()
        ax.axis("off")
        ax.text(0.5, 0.5, "No data", ha="center", va="center")
        return fig

    base_span = max(D_mm, d_mm, a_mm)
    # Add a bit of margin so C, T and z stay visible even for deep beams.
    D_ref = base_span * 1.10

    # 1:1 aspect ratio, same depth as calc box
    fig, ax = plt.subplots(figsize=(3.0, 3.0))
    ax.set_xlim(0.0, 100.0)
    ax.set_ylim(D_ref, 0.0)
    ax.set_aspect("equal", adjustable="box")
    ax.axis("off")

    # Vertical reference line
    x_axis = 20.0
    ax.plot([x_axis, x_axis], [0.0, D_ref], color="black", linewidth=LINE_THICK)

    # Consistent label spacing from arrows
    label_spacing = 4.0

    # Compression C at a/2
    y_C = 0.5 * a_mm
    ARROW_OFFSET = 90.0  # Further increased distance from axis for longer force lines

    x_C_tail = x_axis + ARROW_OFFSET
    x_C_head = x_axis

    ax.annotate(
        "",
        xy=(x_C_head, y_C),
        xytext=(x_C_tail, y_C),
        arrowprops=dict(
            arrowstyle="->",
            linewidth=LINE_MED,
            color="tab:red",
            mutation_scale=ARROW_SCALE,
        ),
    )
    label_C = "C"
    if C_N is not None:
        label_C += f" = {C_N/1000.0:.1f} kN"
    ax.text(
        x_C_tail + label_spacing,
        y_C,
        label_C,
        ha="left",
        va="center",
        fontsize=FS_LABEL,
        color="tab:red",
    )

    # Tension T at depth d
    y_T = d_mm
    x_T_head = x_axis + ARROW_OFFSET
    x_T_tail = x_axis

    # Draw T arrow pointing right from vertical axis
    # Using ax.arrow() for more reliable drawing
    ax.arrow(
        x_T_tail,  # Start x (vertical axis)
        y_T,       # Start y
        x_T_head - x_T_tail,  # dx (length of arrow)
        0,         # dy (horizontal arrow)
        head_width=3.0,
        head_length=3.0,
        fc="tab:blue",
        ec="tab:blue",
        linewidth=LINE_MED,
        length_includes_head=True,
        zorder=2,
    )
    label_T = "T"
    if T_N is not None:
        label_T += f" = {T_N/1000.0:.1f} kN"
    ax.text(
        x_T_head + label_spacing,
        y_T,
        label_T,
        ha="left",
        va="center",
        fontsize=FS_LABEL,
        color="tab:blue",
        zorder=3,  # Ensure label is on top
    )

    # Lever arm z - positioned between the vertical axis and force arrow ends
    x_z = x_axis + ARROW_OFFSET * 0.6  # Positioned between the axis and force arrow ends
    ax.annotate(
        "",
        xy=(x_z, y_T),
        xytext=(x_z, y_C),
        arrowprops=dict(
            arrowstyle="<->",
            linewidth=LINE_MED,
            mutation_scale=ARROW_SCALE,
        ),
    )
    ax.text(
        x_z + label_spacing,
        0.5 * (y_C + y_T),
        "z",
        ha="left",
        va="center",
        fontsize=FS_LABEL,
    )

    ax.text(
        50.0,
        D_ref + 0.08 * D_ref,
        "Force model",
        ha="center",
        va="bottom",
        fontsize=FS_TITLE,
    )

    return fig


# ============================================================
#  NEW: SLS STRESS-BLOCK / SECTION FIGURE FOR 3.3
# ============================================================
def _make_sls_stress_block_figure(
    D_mm: float,
    d_mm: float,
    dn_mm: float,
    include_comp: bool = False,
    d_comp_mm: float | None = None,
):
    """
    Simple SLS cracked-section figure for Step 3.2.

    - Vertical concrete "axis" with neutral axis at d_n
    - Triangular compression stress block above d_n
      (right angle at top-left, matching the main SLS stress panel)
    - Tension steel shown at depth d
    - Optional compression steel shown at depth d_comp_mm
    """

    vals = [D_mm, d_mm, dn_mm]
    if any(v is None or (isinstance(v, float) and math.isnan(v)) for v in vals):
        fig, ax = plt.subplots()
        ax.axis("off")
        ax.text(0.5, 0.5, "No data", ha="center", va="center")
        return fig

    base_span = max(D_mm, d_mm, dn_mm, d_comp_mm or 0.0)
    D_ref = base_span * 1.05

    fig, ax = plt.subplots(figsize=(3.0, 2.6))
    ax.set_xlim(0.0, 100.0)
    ax.set_ylim(D_ref, 0.0)  # 0 at top
    ax.axis("off")

    x_axis = 20.0

    # concrete "section" line
    ax.plot([x_axis, x_axis], [0.0, D_ref], color="black", linewidth=LINE_THICK)

    # neutral axis
    ax.hlines(
        dn_mm,
        x_axis,
        95.0,
        linestyles="--",
        linewidth=LINE_THIN,
        colors="black",
    )

    # triangular compression region (0 → d_n), right angle at top-left
    block_left = x_axis
    block_width = 22.0
    
    # Consistent label spacing from stress block/arrows
    label_spacing = 4.0
    
    ax.fill(
        [block_left, block_left + block_width, block_left],
        [0.0, 0.0, dn_mm],
        fill=False,
        edgecolor="tab:red",
        linewidth=LINE_MED,
    )

    # horizontal width arrow + α2 f'c label (no numeric value needed here)
    y_alpha = -0.08 * D_ref
    ax.annotate(
        "",
        xy=(block_left, y_alpha),
        xytext=(block_left + block_width, y_alpha),
        arrowprops=dict(
            arrowstyle="<->",
            linewidth=LINE_THIN,
            color="tab:red",
            mutation_scale=ARROW_SCALE,
        ),
    )
    # α₂ f'c label positioned at half the spacing distance from stress block (left side)
    ax.text(
        block_left - label_spacing / 2.0,
        y_alpha - 0.05 * D_ref,
        r"$\alpha_2 f'_c$",
        ha="right",
        va="bottom",
        fontsize=FS_LABEL,
        color="tab:red",
    )

    # tension steel marker at depth d
    x_T0 = x_axis + 35.0
    x_T1 = x_axis + 70.0
    ax.plot([x_T0, x_T1], [d_mm, d_mm], color="tab:blue", linewidth=LINE_MED)
    ax.text(
        x_T1 + label_spacing,
        d_mm,
        "T",
        ha="left",
        va="center",
        fontsize=FS_LABEL,
        color="tab:blue",
    )

    # compression steel (optional)
    if include_comp and d_comp_mm is not None:
        x_C0 = x_axis + 35.0
        x_C1 = x_axis + 70.0
        ax.plot(
            [x_C0, x_C1],
            [d_comp_mm, d_comp_mm],
            color="tab:red",
            linewidth=LINE_MED,
        )
        ax.text(
            x_C1 + 4.0,
            d_comp_mm,
            "C_s",
            ha="left",
            va="center",
            fontsize=FS_LABEL,
            color="tab:red",
        )

    ax.text(
        50.0,
        D_ref + 0.08 * D_ref,
        "Stress (MPa)",
        ha="center",
        va="bottom",
        fontsize=FS_TITLE,
    )

    return fig


