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


# ------------------------------------------------------------
# Helper: parabolic concrete stress (for Parabolic view)
# ------------------------------------------------------------
def _sigma_c_parabolic(eps, sigma_peak, eps0=0.002, eps_cu=0.003):
    """
    Simple Hognestad-style parabolic + linear softening model.

    eps        : compressive strain (>= 0, concrete)
    sigma_peak : peak compressive stress used for this diagram (MPa)
                 (we use alpha2 * f'c so the scale matches the ULS block)
    """
    if eps <= 0.0:
        return 0.0
    if eps <= eps0:
        x = eps / eps0
        return sigma_peak * (2.0 * x - x**2)
    if eps <= eps_cu:
        return sigma_peak * (eps_cu - eps) / (eps_cu - eps0)
    return 0.0


# ============================================================
#  MAIN 3-PANEL SECTION / STRAIN / STRESS DIAGRAM
# ============================================================
def _plot_stress_strain_profiles(state_dict, state_label=None):
    """
    Three-panel Plotly figure:
        - Section (left)
        - Strain (centre)
        - Stress (right)
    """
    # ------------------------------------
    # Decide which "state" we're in:
    #   1) explicit argument from the tab
    #   2) otherwise fall back to session
    #   3) otherwise default to ULS
    # ------------------------------------
    label_from_call = state_label

    try:
        label_from_session = st.session_state.get(
            "bending_strain_state_local", None
        )
    except Exception:
        label_from_session = None

    if label_from_call is not None:
        state_label = label_from_call
    elif label_from_session:
        state_label = label_from_session
    else:
        state_label = "ULS"

    # Normalise for logic (robust to different display text)
    label_str = str(state_label or "ULS").strip()
    label_low = label_str.lower()
    # True only for ULS state
    # Explicitly check: must start with "uls" and NOT contain "sls" or "uncracked" or "parabolic"
    is_uls = (
        label_low.startswith("uls")
        and "sls" not in label_low
        and "uncracked" not in label_low
        and "parabolic" not in label_low
    )
    # New: parabolic visual state
    is_parabolic = "parabolic" in label_low

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
        shared_yaxes=True,
        horizontal_spacing=0.08,
        specs=[[{"type": "xy"}, {"type": "xy"}, {"type": "xy"}]],
        subplot_titles=["Section", "Strain", "Stress (MPa)"],
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

    # ----------------------------------------
    # Compression region in SECTION panel
    #   ULS         → rectangular block to γ c
    #   SLS/Uncr    → rectangular block to d_n
    #   Parabolic   → also to d_n (we're just showing compression zone)
    # ----------------------------------------
    if is_uls:
        block_depth_sec = max(0.0, min(gamma * c, D))
    else:
        # SLS, Uncracked, Parabolic all use d_n depth in SECTION panel
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

    # ----------------------------------------
    # Depth labels next to section: d and d_n
    # ----------------------------------------
    beam_right = b  # section goes from x = 0 → b

    # position of d arrow (just to the right of the section)
    x_d = beam_right + 0.12 * b
    if d:
        # arrow from top fibre (0) down to depth d
        fig.add_annotation(
            x=x_d,
            y=d,
            ax=x_d,
            ay=0,
            xref="x1",
            yref="y1",
            axref="x1",
            ayref="y1",
            text="",
            showarrow=True,
            arrowhead=3,
            arrowsize=1.0,
            arrowwidth=1.0,
            arrowcolor="black",
            row=1,
            col=1,
        )
        # label for d (placed mid-depth)
        fig.add_annotation(
            x=x_d + 0.04 * b,
            y=d / 2.0,
            text=f"d = {d:.0f} mm",
            showarrow=False,
            font=dict(size=9, color="black"),
            xanchor="left",
            row=1,
            col=1,
        )

    # position of d_n arrow (a bit further right, in red)
    x_dn = beam_right + 0.30 * b
    if c:
        fig.add_annotation(
            x=x_dn,
            y=c,
            ax=x_dn,
            ay=0,
            xref="x1",
            yref="y1",
            axref="x1",
            ayref="y1",
            text="",
            showarrow=True,
            arrowhead=3,
            arrowsize=1.0,
            arrowwidth=1.0,
            arrowcolor="red",
            row=1,
            col=1,
        )
        fig.add_annotation(
            x=x_dn + 0.04 * b,
            y=c / 2.0,
            text=f"dₙ = {c:.0f} mm",
            showarrow=False,
            font=dict(size=9, color="red"),
            xanchor="left",
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

    # vertical depth line at ε = 0 (concrete depth axis)
    fig.add_shape(
        type="line",
        x0=panel_x_center,
        y0=0,
        x1=panel_x_center,
        y1=D,
        line=dict(color="black", width=1.0),
        row=1,
        col=2,
    )

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

    # -----------------------------
    # Compression block in STRESS
    # -----------------------------
    if is_uls:
        # rectangular ULS block (unchanged)
        block_top = 0.0
        block_bottom = gamma * c
        fig.add_shape(
            type="rect",
            x0=x_axis,
            y0=block_top,
            x1=x_block_right,
            y1=block_bottom,
            line=dict(color="red", width=1.0),
            fillcolor="rgba(255,200,200,0.2)",
            row=1,
            col=3,
        )

    elif is_parabolic:
        # NEW: parabolic block from top fibre down to d_n
        block_top = 0.0
        block_bottom = c if c else 0.0

        if block_bottom > block_top:
            n_pts = 60
            ys = np.linspace(block_top, block_bottom, n_pts)

            # Dimensionless depth from NA (0 at NA, 1 at top fibre)
            # z = 1 at top (y=0), z = 0 at neutral axis (y=c)
            z = 1.0 - ys / max(block_bottom, 1e-6)

            # Textbook parabolic stress: 0 at NA, sigma_c at top
            sigma_profile = sigma_c * (2.0 * z - z**2)
            sigma_profile = np.clip(sigma_profile, 0.0, None)

            x_profile = [stress_to_x(s) for s in sigma_profile]

            # Build a closed polygon that fills back to the vertical axis x_axis
            polygon_x = [x_axis] + x_profile + [x_axis]
            polygon_y = [block_top] + list(ys) + [block_bottom]

            fig.add_trace(
                go.Scatter(
                    x=polygon_x,
                    y=polygon_y,
                    mode="lines",
                    fill="toself",
                    fillcolor="rgba(255,200,200,0.3)",
                    line=dict(color="red", width=1.5),
                    hoverinfo="skip",
                    showlegend=False,
                ),
                row=1,
                col=3,
            )
            
        else:
            block_bottom = block_top  # safe fallback

        else:
            block_bottom = block_top  # safe fallback

    else:
        # TRIANGULAR SLS / UNCRACKED block (unchanged)
        block_top = 0.0
        block_bottom = c
        triangle_x = [x_axis, x_axis, x_block_right, x_axis]
        triangle_y = [block_bottom, block_top, block_top, block_bottom]
        fig.add_trace(
            go.Scatter(
                x=triangle_x,
                y=triangle_y,
                mode="lines",
                fill="toself",
                fillcolor="rgba(255,200,200,0.3)",
                line=dict(color="red", width=1.5),
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

    # α2 f'c arrow + label (still uses sigma_c as the reference)
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
        if is_uls
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

    # internal compression arrows – always inside whatever block we drew
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
        fig_height = 3.2              # visually a bit taller
    else:  # "11" – same axis height, but shorter figure
        D_ref = base_span * 1.05
        fig_height = 2.4

    fig, ax = plt.subplots(figsize=(3.0, fig_height))
    ax.set_xlim(0.0, 100.0)
    ax.set_ylim(D_ref, 0.0)  # 0 at top
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
    block_width = 22.0
    block_top = 0.0
    block_bottom = a_mm

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
        ax.text(
            block_left,
            y_alpha - 0.05 * D_ref,
            f"α₂ f'c = {sigma_c:.0f} MPa",
            ha="left",
            va="bottom",
            fontsize=FS_LABEL,
            color="tab:red",
        )

    # dashed d_n line + label (optional)
    if show_dn:
        ax.hlines(
            dn_mm,
            x_axis,
            95.0,
            linestyles="--",
            colors="tab:blue",
            linewidth=LINE_MED,
        )
        x_dn_label = 95.0
        ax.text(
            x_dn_label + 2.0,
            dn_mm + 0.03 * D_ref,
            f"dₙ = {dn_mm:.1f} mm",
            ha="left",
            va="bottom",
            fontsize=FS_LABEL,
            color="tab:blue",
        )

    # a label
    ax.text(
        block_left + block_width + 4.0,
        0.5 * a_mm,
        f"a = γ dₙ = {a_mm:.1f} mm",
        ha="left",
        va="center",
        fontsize=FS_LABEL,
        color="tab:blue",
    )

    # bottom tension arrow (now guaranteed to be inside the axes)
    ax.annotate(
        "",
        xy=(90.0, d_mm),
        xytext=(x_axis, d_mm),
        arrowprops=dict(
            arrowstyle="->",
            linewidth=LINE_MED,
            color="tab:blue",
            mutation_scale=ARROW_SCALE,
        ),
    )
    ax.text(
        92.0,
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
        x_C_head = block_left + block_width + 4.0
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
            x_C_tail + 3.0,
            y_C,
            f"C = {C_N/1000.0:.1f} kN",
            ha="left",
            va="center",
            fontsize=FS_LABEL,
            color="tab:red",
        )

    # optional lever arm
    if show_lever_arm:
        y_C = 0.5 * a_mm
        x_z = block_left + block_width + 8.0
        ax.annotate(
            "",
            xy=(x_z, d_mm),
            xytext=(x_z, y_C),
            arrowprops=dict(
                arrowstyle="<->",
                linewidth=LINE_MED,
                mutation_scale=ARROW_SCALE,
            ),
        )
        ax.text(
            x_z + 3.0,
            0.5 * (d_mm + y_C),
            "z",
            ha="left",
            va="center",
            fontsize=FS_LABEL,
        )

    ax.text(
        50.0,
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

    fig, ax = plt.subplots(figsize=(3.6, 2.7))
    ax.set_xlim(0.0, 100.0)
    ax.set_ylim(D_ref, 0.0)
    ax.axis("off")

    # Vertical reference line
    x_axis = 20.0
    ax.plot([x_axis, x_axis], [0.0, D_ref], color="black", linewidth=LINE_THICK)

    # Compression C at a/2
    y_C = 0.5 * a_mm
    ARROW_OFFSET = 35.0  # distance from axis, matched to T

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
        x_C_tail + 6.0,
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

    ax.annotate(
        "",
        xy=(x_T_head, y_T),
        xytext=(x_T_tail, y_T),
        arrowprops=dict(
            arrowstyle="->",
            linewidth=LINE_MED,
            color="tab:blue",
            mutation_scale=ARROW_SCALE,
        ),
    )
    label_T = "T"
    if T_N is not None:
        label_T += f" = {T_N/1000.0:.1f} kN"
    ax.text(
        x_T_head + 6.0,
        y_T,
        label_T,
        ha="left",
        va="center",
        fontsize=FS_LABEL,
        color="tab:blue",
    )

    # Lever arm z
    x_z = x_axis + ARROW_OFFSET + 25.0
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
        x_z + 4.0,
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
    ax.text(
        block_left,
        y_alpha - 0.05 * D_ref,
        r"$\alpha_2 f'_c$",
        ha="left",
        va="bottom",
        fontsize=FS_LABEL,
        color="tab:red",
    )

    # tension steel marker at depth d
    x_T0 = x_axis + 35.0
    x_T1 = x_axis + 70.0
    ax.plot([x_T0, x_T1], [d_mm, d_mm], color="tab:blue", linewidth=LINE_MED)
    ax.text(
        x_T1 + 4.0,
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
