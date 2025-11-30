# bending_diagrams.py
import math
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, Circle
import streamlit as st

from state_and_helpers import get_param
from bending_core import _layout_bars_in_rows

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
    Three-panel figure:

        - Section (left)
        - Strain profile (centre)
        - Stress / stress-block (right)

    Panel positions and axes limits are FIXED so the diagrams
    do not jump around when switching between ULS / SLS / Uncracked.
    """
    if state_label is None:
        try:
            state_label = st.session_state.get("bending_strain_state_local", "ULS")
        except Exception:
            state_label = "ULS"

    # unpack state
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

    # Warner-style sign convention (for this figure only):
    #   concrete strain positive, steel strain negative
    eps_c = abs(eps_c_raw)
    eps_s = -abs(eps_s_raw)

    # reinforcement parameters
    nb_bot = int(get_param("nb_bot") or 4)
    db_bot = get_param("db_bot") or 20.0
    cover_bot = get_param("cover_bot") or 40.0
    rowgap_bot = get_param("rowgap_bot") or 25.0
    nb_top = int(get_param("nb_top") or 2)
    db_top = get_param("db_top") or 16.0
    cover_top = get_param("cover_top") or 40.0
    rowgap_top = get_param("rowgap_top") or 25.0

    sec_title = "Section"

    # -------------------------
    # Scaling
    # -------------------------
    eps_max = max(abs(eps_c), abs(eps_s), 1e-4) * 1.3
    sigma_c = alpha2 * fc
    sigma_s = abs(fs_t)
    stress_max = max(sigma_c, sigma_s, 1.0)

    # -------------------------
    # FIXED panel positions
    # (section moved a bit further left, spacing preserved)
    # -------------------------
    x_center_sec    = 135.0   # was 160
    x_center_strain = 650.0
    x_center_stress = 1140.0

    sec_width = float(b)
    x0_sec = x_center_sec - sec_width / 2.0

    panel_w_strain = 200.0
    x0_strain = x_center_strain - panel_w_strain / 2.0
    x1_strain = x_center_strain + panel_w_strain / 2.0

    panel_w_stress = 260.0
    x0_stress = x_center_stress - panel_w_stress / 2.0
    x1_stress = x_center_stress + panel_w_stress / 2.0

    def strain_to_x(eps):
        half_w = panel_w_strain * 0.4
        return x_center_strain + (eps / eps_max) * half_w

    def stress_to_x(sig):
        return x0_stress + (sig / stress_max) * (panel_w_stress * 0.8)

    fig, ax = plt.subplots(figsize=(9, 3.5))
    fig.subplots_adjust(left=0.02, right=0.98, top=0.98, bottom=0.02)

    # fixed axes → positions frozen across ULS / SLS / Uncracked
    ax.set_ylim(D * 1.2, -0.2 * D)
    ax.set_xlim(-200.0, 1450.0)
    ax.set_aspect("equal", adjustable="box")
    ax.set_xmargin(0)
    ax.set_ymargin(0)

    # remove ticks / axis markings
    for spine in ["top", "right", "bottom", "left"]:
        ax.spines[spine].set_visible(False)
    ax.tick_params(left=False, labelleft=False, bottom=False, labelbottom=False)

    # ====================================================
    # 1) SECTION PANEL
    # ====================================================
    ax.add_patch(
        Rectangle((x0_sec, 0), b, D, fill=False, linewidth=LINE_THICK, edgecolor="black")
    )

    block_depth_sec = max(0.0, min(gamma * c, D))
    ax.add_patch(
        Rectangle(
            (x0_sec, 0),
            b,
            block_depth_sec,
            facecolor="#c7e3ff",
            edgecolor="tab:red",
            linewidth=LINE_MED,
            alpha=0.8,
        )
    )

    # bottom bars
    min_spacing_bot = 2 * db_bot
    bot_layout = _layout_bars_in_rows(nb_bot, b, cover_bot, db_bot, min_spacing_bot, 2)
    r_bot = db_bot / 2.0
    row_pitch_bot = db_bot + rowgap_bot
    d_row0 = D - cover_bot - r_bot

    for x_rel, row_idx in bot_layout:
        ax.add_patch(
            Circle(
                (x0_sec + x_rel, d_row0 - row_idx * row_pitch_bot),
                radius=r_bot,
                fill=False,
                edgecolor="tab:blue",
                linewidth=LINE_MED,
            )
        )

    # top bars
    min_spacing_top = 2 * db_top
    top_layout = _layout_bars_in_rows(nb_top, b, cover_top, db_top, min_spacing_top, 2)
    r_top = db_top / 2.0
    y_top_base = cover_top + r_top
    row_pitch_top = db_top + rowgap_top

    for x_rel, row_idx in top_layout:
        ax.add_patch(
            Circle(
                (x0_sec + x_rel, y_top_base + row_idx * row_pitch_top),
                radius=r_top,
                fill=False,
                edgecolor="tab:red",
                linewidth=LINE_MED,
            )
        )

    # depth arrows next to section only
    beam_right = x0_sec + b

    if d:
        x_d = min(beam_right + 30.0, x0_strain - 40.0)
        ax.annotate(
            "",
            xy=(x_d, d),
            xytext=(x_d, 0),
            arrowprops=dict(
                arrowstyle="<->",
                linewidth=LINE_THIN,
                mutation_scale=ARROW_SCALE,
            ),
        )
        ax.text(
            x_d + 10,
            d / 2,
            f"d = {d:.0f} mm",
            fontsize=FS_ANNOT,
            va="center",
        )

    if c:
        x_dn = min(beam_right + 80.0, x0_strain - 10.0)
        ax.annotate(
            "",
            xy=(x_dn, c),
            xytext=(x_dn, 0),
            arrowprops=dict(
                arrowstyle="<->",
                linewidth=LINE_THIN,
                color="tab:red",
                mutation_scale=ARROW_SCALE,
            ),
        )
        ax.text(
            x_dn + 10,
            c / 2,
            "dₙ = {:.0f} mm".format(c),
            fontsize=FS_ANNOT,
            color="tab:red",
            va="center",
        )

    ax.text(
        x_center_sec,
        D + 0.14 * D,
        sec_title,
        ha="center",
        va="bottom",
        fontsize=FS_TITLE,
    )

    # ====================================================
    # 2) STRAIN PANEL
    # ====================================================
    ax.plot(
        [x_center_strain, x_center_strain],
        [0, D],
        color="black",
        linewidth=LINE_MED,
    )

    y_vals = np.array([0, c, d])
    eps_vals = np.array([eps_c, 0.0, eps_s])
    x_vals = [strain_to_x(e) for e in eps_vals]
    ax.plot(x_vals, y_vals, color="black", linewidth=LINE_MED)

    ax.hlines(
        c,
        x0_strain - 10,
        x1_strain + 10,
        colors="black",
        linestyles="--",
        linewidth=LINE_THIN,
    )

    ax.text(
        strain_to_x(eps_c),
        0,
        rf"$\varepsilon_c = {eps_c:.4f}$",
        fontsize=FS_ANNOT,
        color="tab:red",
        va="bottom",
    )
    ax.text(
        strain_to_x(eps_s),
        d,
        rf"$\varepsilon_s = {eps_s:.4f}$",
        fontsize=FS_ANNOT,
        color="tab:blue",
        va="top",
    )

    ax.text(
        x_center_strain,
        D + 0.14 * D,
        "Strain",
        ha="center",
        va="bottom",
        fontsize=FS_TITLE,
    )

    # ====================================================
    # 3) STRESS PANEL
    # ====================================================
    ax.plot([x0_stress, x0_stress], [0, D], color="black", linewidth=LINE_MED)

    x_T = stress_to_x(sigma_s)
    ax.annotate(
        "",
        xy=(x_T, d),
        xytext=(x0_stress, d),
        arrowprops=dict(
            arrowstyle="->",
            linewidth=LINE_MED,
            color="tab:blue",
            mutation_scale=ARROW_SCALE,
        ),
    )
    ax.text(
        x_T + 8,
        d,
        f"T ({sigma_s:.0f} MPa)",
        fontsize=FS_ANNOT,
        color="tab:blue",
        va="center",
    )

    block_ratio = 1 / 3
    block_width = (x_T - x0_stress) * block_ratio
    x_block_right = x0_stress + block_width

    block_top = 0
    block_bottom = gamma * c if state_label == "ULS" else c

    sigma_c_val = alpha2 * fc

    # compression block outline
    if state_label == "ULS":
        ax.fill(
            [x0_stress, x_block_right, x_block_right, x0_stress],
            [block_top, block_top, block_bottom, block_bottom],
            fill=False,
            edgecolor="tab:red",
            linewidth=LINE_MED,
        )
    else:
        ax.fill(
            [x0_stress, x0_stress, x_block_right],
            [block_bottom, block_top, block_top],
            fill=False,
            edgecolor="tab:red",
            linewidth=LINE_MED,
        )

    ax.hlines(
        c,
        x0_stress - 10,
        x1_stress,
        linestyles="--",
        linewidth=LINE_THIN,
        colors="black",
    )

    # α2 f'c width arrow
    y_alpha = -0.05 * D
    ax.annotate(
        "",
        xy=(x0_stress, y_alpha),
        xytext=(x_block_right, y_alpha),
        arrowprops=dict(
            arrowstyle="<->",
            linewidth=LINE_THIN,
            color="tab:red",
            mutation_scale=ARROW_SCALE,
        ),
    )
    ax.text(
        (x0_stress + x_block_right) / 2,
        y_alpha - 0.04 * D,
        rf"$\alpha_2 f'_c = {sigma_c_val:.0f}\ \mathrm{{MPa}}$",
        fontsize=FS_ANNOT,
        color="tab:red",
        ha="center",
    )

    # γ d_n / d_n depth arrow
    x_gc = x_block_right + 0.12 * panel_w_stress
    ax.annotate(
        "",
        xy=(x_gc, block_bottom),
        xytext=(x_gc, block_top),
        arrowprops=dict(
            arrowstyle="<->",
            color="tab:red",
            linewidth=LINE_THIN,
            mutation_scale=ARROW_SCALE,
        ),
    )

    depth_label = (
        rf"$\gamma d_n = {gamma*c:.0f}\ \mathrm{{mm}}$"
        if state_label == "ULS"
        else rf"$d_n = {c:.0f}\ \mathrm{{mm}}$"
    )

    ax.text(
        x_gc + 10,
        (block_top + block_bottom) / 2,
        depth_label,
        fontsize=FS_ANNOT,
        color="tab:red",
        va="center",
    )

    # internal compression arrows – facing LEFT
    for frac in [0.25, 0.5, 0.75]:
        y_mid = block_top + frac * (block_bottom - block_top)
        ax.annotate(
            "",
            xy=(x0_stress + 0.15 * block_width, y_mid),
            xytext=(x_block_right - 0.15 * block_width, y_mid),
            arrowprops=dict(
                arrowstyle="->",  # arrow head at left
                color="tab:red",
                linewidth=LINE_THIN,
                mutation_scale=ARROW_SCALE,
            ),
        )

    ax.text(
        x_center_stress,
        D + 0.14 * D,
        "Stress (MPa)",
        ha="center",
        va="bottom",
        fontsize=FS_TITLE,
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
    variant: str = "11",
):
    """
    Warner-style ULS stress block (right-way up)

    Flags:
      - show_lever_arm:  show / hide z arrow
      - show_dn:         show / hide dashed d_n line + label
      - show_alpha_label: show / hide α2 f'c text above the block
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

    # Different vertical spans for 1.1 vs 1.3 so the diagrams
    # roughly match the height of their calc boxes.
    if variant == "13":
        D_ref = max(D_mm, d_mm, a_mm, dn_mm) * 1.10
    else:  # "11" by default – more compact (shorter)
        D_ref = max(D_mm, a_mm, d_mm) * 0.65   # was 0.85 → shorten further

    fig, ax = plt.subplots(figsize=(3, 3.2))   # shorter overall
    ax.set_xlim(0.0, 100.0)
    ax.set_ylim(D_ref, 0.0)  # 0 at top
    ax.axis("off")

    # vertical axis
    x_axis = 20.0
    ax.plot([x_axis, x_axis], [0.0, D_ref], color="black", linewidth=LINE_THICK)

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
                    arrowstyle="->",  # leftwards
                    color="tab:red",
                    linewidth=LINE_MED,
                    mutation_scale=ARROW_SCALE,
                ),
            )

    # α2 f'c label (optional)
    if show_alpha_label:
        ax.text(
            block_left,
            -0.08 * D_ref,
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

    # bottom tension arrow
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
