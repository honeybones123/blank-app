# bending_diagrams.py
import math
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, Circle
import streamlit as st

from state_and_helpers import get_param
from bending_core import _layout_bars_in_rows


def _plot_stress_strain_profiles(state_dict, state_label=None):
    """
    Single-axis figure with three panels laid out in X:

        - Section view (left)
        - Strain profile (centre)
        - Stress-block / steel stress profile (right)

    Panel positions are FIXED so they don't jump between ULS / SLS / Uncracked.
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

    # ------------------------------------------------------------
    # SIGN CONVENTION FOR THIS FIGURE (Warner-style):
    #   • Concrete strain positive (compression)
    #   • Steel strain negative (tension)
    # We only flip for plotting – calculations elsewhere unchanged.
    # ------------------------------------------------------------
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

    # dynamic section heading
    if state_label == "ULS":
        sec_title = "Section (ULS view)"
    elif "SLS" in state_label:
        sec_title = "Section (SLS cracked view)"
    else:
        sec_title = "Section (uncracked elastic view)"

    # -------------------------
    # SCALING
    # -------------------------
    eps_max = max(abs(eps_c), abs(eps_s), 1e-4) * 1.3
    sigma_c = alpha2 * fc
    sigma_s = abs(fs_t)
    stress_max = max(sigma_c, sigma_s, 1.0)

    # -------------------------
    # FIXED PANEL POSITIONS (no jumping)
    #   centres:  section @ 200, strain @ 650, stress @ 1100
    # -------------------------
    x_center_sec = 200.0
    x_center_strain = 650.0
    x_center_stress = 1100.0

    # section width = actual beam width (keeps 1:1 geometry in x vs D)
    sec_width = float(b)
    x0_sec = x_center_sec - sec_width / 2.0
    x1_sec = x_center_sec + sec_width / 2.0

    # strain panel
    panel_w_strain = 200.0
    x0_strain = x_center_strain - panel_w_strain / 2.0
    x1_strain = x_center_strain + panel_w_strain / 2.0

    # stress panel
    panel_w_stress = 260.0
    x0_stress = x_center_stress - panel_w_stress / 2.0
    x1_stress = x_center_stress + panel_w_stress / 2.0

    def strain_to_x(eps):
        half_w = panel_w_strain * 0.4
        return x_center_strain + (eps / eps_max) * half_w

    def stress_to_x(sig):
        return x0_stress + (sig / stress_max) * (panel_w_stress * 0.8)

    fig, ax = plt.subplots(figsize=(9, 3.5))

    ax.set_ylim(D * 1.2, -0.2 * D)
    ax.set_xlim(0.0, 1350.0)   # FIXED X-LIMITS → no horizontal jumping
    ax.set_aspect("equal", adjustable="box")

    # remove ticks / axis markings
    for spine in ["top", "right", "bottom", "left"]:
        ax.spines[spine].set_visible(False)
    ax.tick_params(left=False, labelleft=False, bottom=False, labelbottom=False)

    # 1) SECTION PANEL
    ax.add_patch(
        Rectangle((x0_sec, 0), b, D, fill=False, linewidth=1.5, edgecolor="black")
    )

    block_depth_sec = max(0.0, min(gamma * c, D))
    ax.add_patch(
        Rectangle(
            (x0_sec, 0),
            b,
            block_depth_sec,
            facecolor="#c7e3ff",
            edgecolor="tab:red",
            linewidth=1.0,
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
                linewidth=1.2,
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
                linewidth=1.2,
            )
        )

    # ---- d & NA arrows: kept near the SECTION only ----
    beam_right = x0_sec + b

    if d:
        x_d = min(beam_right + 30.0, x0_strain - 40.0)
        ax.annotate(
            "",
            xy=(x_d, d),
            xytext=(x_d, 0),
            arrowprops=dict(
                arrowstyle="<->",
                linewidth=1.0,
                mutation_scale=8,  # smaller arrow heads
            ),
        )
        ax.text(x_d + 10, d / 2, f"d = {d:.0f} mm", fontsize=6, va="center")

    if c:
        x_na = min(beam_right + 80.0, x0_strain - 10.0)
        ax.annotate(
            "",
            xy=(x_na, c),
            xytext=(x_na, 0),
            arrowprops=dict(
                arrowstyle="<->",
                linewidth=1.0,
                color="tab:red",
                mutation_scale=8,
            ),
        )
        ax.text(
            x_na + 10,
            c / 2,
            f"NA = {c:.0f} mm",
            fontsize=6,
            color="tab:red",
            va="center",
        )

    ax.text(
        x_center_sec,
        D + 0.14 * D,
        sec_title,
        ha="center",
        va="bottom",
        fontsize=10,
    )

    # 2) STRAIN PANEL
    ax.plot([x_center_strain, x_center_strain], [0, D], color="black", linewidth=1)

    y_vals = np.array([0, c, d])
    eps_vals = np.array([eps_c, 0.0, eps_s])
    x_vals = [strain_to_x(e) for e in eps_vals]
    ax.plot(x_vals, y_vals, color="black")

    ax.hlines(c, x0_strain - 10, x1_strain + 10, colors="black", linestyles="--")

    ax.text(
        strain_to_x(eps_c),
        0,
        rf"$\varepsilon_c = {eps_c:.4f}$",
        fontsize=6,
        color="tab:red",
        va="bottom",
    )
    ax.text(
        strain_to_x(eps_s),
        d,
        rf"$\varepsilon_s = {eps_s:.4f}$",
        fontsize=6,
        color="tab:blue",
        va="top",
    )

    ax.text(
        x_center_strain,
        D + 0.14 * D,
        "Strain",
        ha="center",
        va="bottom",
        fontsize=9,
    )

    # 3) STRESS PANEL
    ax.plot([x0_stress, x0_stress], [0, D], color="black", linewidth=1)

    x_T = stress_to_x(sigma_s)
    ax.annotate(
        "",
        xy=(x_T, d),
        xytext=(x0_stress, d),
        arrowprops=dict(
            arrowstyle="->",
            linewidth=1.4,
            color="tab:blue",
            mutation_scale=8,
        ),
    )
    ax.text(
        x_T + 8,
        d,
        f"T ({sigma_s:.0f} MPa)",
        fontsize=6,
        color="tab:blue",
        va="center",
    )

    block_ratio = 1 / 3
    block_width = (x_T - x0_stress) * block_ratio
    x_block_right = x0_stress + block_width

    block_top = 0
    block_bottom = gamma * c if state_label == "ULS" else c

    sigma_c_val = alpha2 * fc

    # ULS: rectangular block
    if state_label == "ULS":
        ax.fill(
            [x0_stress, x_block_right, x_block_right, x0_stress],
            [block_top, block_top, block_bottom, block_bottom],
            fill=False,
            edgecolor="tab:red",
            linewidth=1.5,
        )
    else:
        ax.fill(
            [x0_stress, x0_stress, x_block_right],
            [block_bottom, block_top, block_top],
            fill=False,
            edgecolor="tab:red",
            linewidth=1.5,
        )

    ax.hlines(c, x0_stress - 10, x1_stress, linestyles="--")

    # α2 f'c width arrow
    y_alpha = -0.05 * D
    ax.annotate(
        "",
        xy=(x0_stress, y_alpha),
        xytext=(x_block_right, y_alpha),
        arrowprops=dict(
            arrowstyle="<->",
            linewidth=1.2,
            color="tab:red",
            mutation_scale=8,
        ),
    )
    ax.text(
        (x0_stress + x_block_right) / 2,
        y_alpha - 0.04 * D,
        rf"$\alpha_2 f'_c = {sigma_c_val:.0f}\ \mathrm{{MPa}}$",
        fontsize=6,
        color="tab:red",
        ha="center",
    )

    # γc / NA depth arrow
    x_gc = x_block_right + 0.12 * panel_w_stress
    ax.annotate(
        "",
        xy=(x_gc, block_bottom),
        xytext=(x_gc, block_top),
        arrowprops=dict(
            arrowstyle="<->",
            color="tab:red",
            mutation_scale=8,
        ),
    )

    depth_label = (
        rf"$\gamma c = {gamma*c:.0f}\ \mathrm{{mm}}$"
        if state_label == "ULS"
        else rf"$NA = {c:.0f}\ \mathrm{{mm}}$"
    )

    ax.text(
        x_gc + 10,
        (block_top + block_bottom) / 2,
        depth_label,
        fontsize=6,
        color="tab:red",
        va="center",
    )

    # internal compression arrows – face LEFT
    for frac in [0.25, 0.5, 0.75]:
        y_mid = block_top + frac * (block_bottom - block_top)
        ax.annotate(
            "",
            xy=(x0_stress + 0.15 * block_width, y_mid),
            xytext=(x_block_right - 0.15 * block_width, y_mid),
            arrowprops=dict(
                arrowstyle="->",          # arrow head at left
                color="tab:red",
                linewidth=0.9,
                mutation_scale=8,
            ),
        )

    ax.text(
        x_center_stress,
        D + 0.14 * D,
        "Stress (MPa)",
        ha="center",
        va="bottom",
        fontsize=9,
    )

    return fig


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
):
    """
    Warner-style ULS stress block (right-way up)
    """

    vals = [b_mm, D_mm, d_mm, dn_mm, a_mm, alpha2, gamma, fc, fsy]
    if any(v is None or (isinstance(v, float) and math.isnan(v)) for v in vals):
        fig, ax = plt.subplots()
        ax.axis("off")
        ax.text(0.5, 0.5, "No data", ha="center", va="center")
        return fig

    sigma_c = alpha2 * fc  # MPa
    D_ref = max(D_mm, d_mm, dn_mm, a_mm) * 1.05

    fig, ax = plt.subplots(figsize=(3, 5))

    ax.set_xlim(0.0, 100.0)
    ax.set_ylim(D_ref, 0.0)  # 0 at top
    ax.axis("off")

    # vertical axis
    x_axis = 20.0
    ax.plot([x_axis, x_axis], [0.0, D_ref], color="black", linewidth=2.0)

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
            linewidth=2.0,
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
                    arrowstyle="->",        # leftwards
                    color="tab:red",
                    linewidth=1.6,
                    mutation_scale=8,
                ),
            )

    # α2 f'c label
    ax.text(
        block_left,
        -0.06 * D_ref,
        f"α₂ f'c = {sigma_c:.0f} MPa",
        ha="left",
        va="bottom",
        fontsize=10,
        color="tab:red",
    )

    # dashed NA line
    ax.hlines(
        dn_mm,
        x_axis,
        95.0,
        linestyles="--",
        colors="tab:blue",
        linewidth=2.0,
    )
    ax.text(
        (x_axis + 95.0) / 2.0,
        dn_mm + 0.04 * D_ref,
        f"dₙ = {dn_mm:.1f} mm",
        ha="center",
        va="bottom",
        fontsize=10,
        color="tab:blue",
    )

    # a label
    ax.text(
        block_left + block_width + 4.0,
        0.5 * a_mm,
        f"a = γ dₙ = {a_mm:.1f} mm",
        ha="left",
        va="center",
        fontsize=10,
        color="tab:blue",
    )

    # bottom tension arrow
    ax.annotate(
        "",
        xy=(90.0, d_mm),
        xytext=(x_axis, d_mm),
        arrowprops=dict(
            arrowstyle="->",
            linewidth=2.0,
            color="tab:blue",
            mutation_scale=8,
        ),
    )
    ax.text(
        92.0,
        d_mm,
        f"T ({fsy:.0f} MPa)",
        ha="left",
        va="center",
        fontsize=10,
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
                linewidth=1.6,
                mutation_scale=8,
            ),
        )
        ax.text(
            x_z + 3.0,
            0.5 * (d_mm + y_C),
            "z",
            ha="left",
            va="center",
            fontsize=9,
        )

    ax.text(
        50.0,
        D_ref + 0.07 * D_ref,
        "Stress (MPa)",
        ha="center",
        va="bottom",
        fontsize=11,
    )

    return fig
