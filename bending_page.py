import math
import numpy as np
import pandas as pd
import streamlit as st
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, Circle

from state_and_helpers import (
    get_sync_callbacks,
    get_param,
    update_results,
)

# NEW: shared widget helpers (same as Inputs page)
from widgets_helpers import apply_global_widget_css, number_row


# ------------------------------------------------------------
#  Small formatting helper for tables
# ------------------------------------------------------------
def _fmt(val, pattern="{:.2f}"):
    """Safe formatter for table values."""
    try:
        if val is None:
            return "—"
        if isinstance(val, float) and math.isnan(val):
            return "—"
        return pattern.format(val)
    except Exception:
        return "—"


# ------------------------------------------------------------
#  BENDING CAPACITY CALC (α2–γ stress block, AS3600 Cl. 8.1.3)
# ------------------------------------------------------------
def _compute_bending_capacity():
    """
    Compute a simple φMu,cap using a rectangular stress block.
    Uses shared session_state values only (via get_param).
    Also returns intermediate values for the step-by-step report.
    """
    # Shared parameters (all from session state)
    b = get_param("b")
    D = get_param("D")
    d = get_param("d")
    fc = get_param("fc")
    fsy = get_param("fsy")
    Ast = get_param("Ast_bot")
    Mu_star = get_param("Mu_star")
    # Strength reduction factor from shared state (e.g. Inputs page)
    phi = get_param("phi_bend", 0.85)

    if None in (b, D, d, fc, fsy, Ast, Mu_star):
        return {
            "phi_Mu_cap": 0.0,
            "Mu_util": float("nan"),
            "c": float("nan"),
            "a": float("nan"),
            "z": float("nan"),
            "ku": float("nan"),
            "alpha2": 0.85,
            "gamma": 0.85,
            "phi": phi,
            "fctf": float("nan"),
            "I_gross": float("nan"),
            "Z_gross": float("nan"),
            "Mcr": float("nan"),
            "As_min": float("nan"),
        }

    # ---- Concrete in tension (for min steel & Mcr) ----
    cb = 0.2
    fctf = cb * (fc ** (2.0 / 3.0))          # MPa
    I_gross = b * D**3 / 12.0               # mm^4
    Z_gross = b * D**2 / 6.0                # mm^3
    Mcr = fctf * Z_gross / 1e6              # kNm

    # ---- Minimum tensile reinforcement ----
    kAst = 1.0
    As_min = kAst * (d / D) ** 2 * (fctf / fsy) * b * D

    # ---- Stress-block factors (teaching) ----
    alpha2 = 0.85
    gamma = 0.85

    # ---- Flexural capacity ----
    T = Ast * fsy                              # N (Ast mm², fsy MPa = N/mm²)
    denom = alpha2 * fc * b * gamma
    if denom <= 0:
        return {
            "phi_Mu_cap": 0.0,
            "Mu_util": float("nan"),
            "c": float("nan"),
            "a": float("nan"),
            "z": float("nan"),
            "ku": float("nan"),
            "alpha2": alpha2,
            "gamma": gamma,
            "phi": phi,
            "fctf": fctf,
            "I_gross": I_gross,
            "Z_gross": Z_gross,
            "Mcr": Mcr,
            "As_min": As_min,
        }

    c = T / denom                             # NA depth
    a = gamma * c                             # block depth
    z = d - 0.5 * a                           # lever arm
    Mu_nom = T * z / 1e6                      # kNm (N·mm → kNm)
    phi_Mu_cap = phi * Mu_nom
    Mu_util = Mu_star / phi_Mu_cap if phi_Mu_cap > 0 else float("inf")

    # k_u = c/d
    ku = c / d if d not in (None, 0) else float("nan")

    # Store in shared "results" dict via helpers (SESSION-STATE SAFE)
    update_results(phi_Mu_cap=phi_Mu_cap, Mu_utilisation=Mu_util)

    return {
        "phi_Mu_cap": phi_Mu_cap,
        "Mu_util": Mu_util,
        "c": c,
        "a": a,
        "z": z,
        "ku": ku,
        "alpha2": alpha2,
        "gamma": gamma,
        "phi": phi,
        "fctf": fctf,
        "I_gross": I_gross,
        "Z_gross": Z_gross,
        "Mcr": Mcr,
        "As_min": As_min,
    }


# ------------------------------------------------------------
#  DIAGRAM HELPERS (cross-section + schematic stress block)
# ------------------------------------------------------------
def _make_cross_section_figure(
    b,
    D,
    d,
    a,
    nb_bot,
    db_bot,
    cover_bot,
    nb_top=None,
    db_top=None,
    cover_top=None,
    c=None,
    z=None,
    show_compression=True,
    title="ULS SECTION",
):
    """
    Front cross-section with compression zone + top + bottom bars + labels.
    Smaller figure, thinner lines; c on far right, d on right, z on left.

    show_compression = False → draws an 'uncracked' elastic section
    (no shaded compression block).
    """
    if None in (b, D):
        return None

    # Defaults for bottom bars
    if nb_bot is None or nb_bot < 1:
        nb_bot = 3
    if db_bot is None or db_bot <= 0:
        db_bot = 20.0
    if cover_bot is None or cover_bot <= 0:
        cover_bot = 40.0

    # Default top reo
    if nb_top is None or nb_top < 1:
        nb_top = 2
    if db_top is None or db_top <= 0:
        db_top = 16.0
    if cover_top is None or cover_top <= 0:
        cover_top = 40.0

    nb_bot = int(nb_bot)
    nb_top = int(nb_top)

    fig, ax = plt.subplots(figsize=(2.3, 3.3))

    # Outline
    ax.add_patch(
        Rectangle(
            (0, 0), b, D,
            fill=False,
            linewidth=0.9,
        )
    )

    # Compression block (optional – for ULS cracked picture)
    if show_compression:
        if a is None or (isinstance(a, float) and math.isnan(a)) or a <= 0:
            a = 0.15 * D

        ax.add_patch(
            Rectangle(
                (0, 0), b, a,
                facecolor="#c7e3ff",
                edgecolor="none",
                alpha=0.9,
            )
        )
        ax.text(
            b / 2,
            a / 2,
            "Compression\nzone",
            ha="center",
            va="center",
            fontsize=8,
        )

    # Bottom reo
    if d is None or (isinstance(d, float) and math.isnan(d)):
        d = 0.9 * D
    y_bot = d

    inner_width_bot = max(b - 2 * cover_bot, db_bot)
    if nb_bot == 1:
        xs_bot = [b / 2]
    else:
        spacing = inner_width_bot / (nb_bot - 1)
        xs_bot = [cover_bot + spacing * i for i in range(nb_bot)]

    for x in xs_bot:
        ax.add_patch(
            Circle(
                (x, y_bot),
                radius=db_bot / 2,
                fill=False,
                linewidth=1.0,
            )
        )

    # Top reo
    y_top = cover_top + db_top / 2
    inner_width_top = max(b - 2 * cover_top, db_top)

    if nb_top == 1:
        xs_top = [b / 2]
    else:
        spacing_t = inner_width_top / (nb_top - 1)
        xs_top = [cover_top + spacing_t * i for i in range(nb_top)]

    for x in xs_top:
        ax.add_patch(
            Circle(
                (x, y_top),
                radius=db_top / 2,
                fill=False,
                linewidth=1.0,
            )
        )

    # LABELS: z LEFT, d RIGHT, c FAR RIGHT
    x_z = b * 0.23
    x_d = b + 15
    x_c = b + 45

    # c (far right)
    if c is not None and not (isinstance(c, float) and math.isnan(c)):
        ax.annotate(
            "",
            xy=(x_c, c),
            xytext=(x_c, 0),
            arrowprops=dict(arrowstyle="<->", linewidth=0.8),
        )
        ax.text(x_c + 3, c / 2, "c", fontsize=7, ha="left", va="center")

    # d (right)
    if d is not None and not (isinstance(d, float) and math.isnan(d)):
        ax.annotate(
            "",
            xy=(x_d, d),
            xytext=(x_d, 0),
            arrowprops=dict(arrowstyle="<->", linewidth=0.8),
        )
        ax.text(x_d + 3, d / 2, "d", fontsize=7, ha="left", va="center")

    # z (left)
    if (
        z is not None
        and not (isinstance(z, float) and math.isnan(z))
        and d is not None
        and not (isinstance(d, float) and math.isnan(d))
    ):
        y_top_z = d - z
        ax.annotate(
            "",
            xy=(x_z, d),
            xytext=(x_z, y_top_z),
            arrowprops=dict(arrowstyle="<->", linewidth=0.8),
        )
        ax.text(
            x_z - 4,
            (d + y_top_z) / 2,
            "z",
            fontsize=7,
            ha="right",
            va="center",
        )

    ax.set_xlim(-10, b + 70)
    ax.set_ylim(D + 10, -20)
    ax.set_aspect("equal")
    ax.set_xlabel("Width (mm)", fontsize=8)
    ax.set_ylabel("Depth (mm)", fontsize=8)
    ax.set_title(title, fontsize=9)
    ax.tick_params(labelsize=7)

    return fig


def _make_stress_figure(alpha2_val, gamma_val):
    """
    Static schematic stress/force diagram (teaching).
    (Still used as a small teaching figure if you want elsewhere.)
    """
    fig, ax = plt.subplots(figsize=(2.2, 4.0))

    ax.set_xlim(0, 10)
    ax.set_ylim(0, 10)
    ax.axis("off")

    x_line = 4.0
    y_bot = 1.2
    y_top = 9.0
    ax.plot([x_line, x_line], [y_bot, y_top], color="black", linewidth=2.2)

    # Compression block
    y_c_top = 8.2
    y_c_bot = 5.8
    block_x_left = x_line
    block_width = 3.0

    ax.add_patch(
        Rectangle(
            (block_x_left, y_c_bot),
            block_width,
            y_c_top - y_c_bot,
            fill=False,
            edgecolor="#4c6faf",
            linewidth=1.2,
        )
    )

    arrow_x_start = block_x_left + block_width - 0.2
    arrow_x_end = block_x_left + 0.1
    arrow_ys = [7.9, 7.0, 6.1]

    for y in arrow_ys:
        ax.annotate(
            "",
            xy=(arrow_x_end, y),
            xytext=(arrow_x_start, y),
            arrowprops=dict(arrowstyle="->", linewidth=1.2, color="#4c6faf"),
        )

    ax.text(
        (block_x_left + block_x_left + block_width) / 2,
        y_c_top + 0.4,
        r"$\alpha_2 f'_c$",
        ha="center",
        va="bottom",
        fontsize=9,
    )

    ax.text(
        block_x_left + block_width + 0.3,
        (y_c_top + y_c_bot) / 2,
        r"$C_c$",
        ha="left",
        va="center",
        fontsize=9,
    )

    x_g = x_line - 0.9
    ax.annotate(
        "",
        xy=(x_g, y_c_top),
        xytext=(x_g, y_c_bot),
        arrowprops=dict(arrowstyle="<->", linewidth=1.1),
    )
    ax.text(
        x_g - 0.3,
        (y_c_top + y_c_bot) / 2,
        r"$\gamma k_u d$",
        ha="right",
        va="center",
        fontsize=9,
        rotation=90,
    )

    y_ts = 2.0
    ax.annotate(
        "",
        xy=(7.0, y_ts),
        xytext=(x_line, y_ts),
        arrowprops=dict(arrowstyle="->", linewidth=1.2, color="#4c6faf"),
    )
    ax.text(
        7.0 + 0.3,
        y_ts,
        r"$T_s$",
        ha="left",
        va="center",
        fontsize=9,
    )

    return fig


def _make_uls_stress_block_figure(c, d, gamma, fs_t, show_lever_arm=False):
    """
    ULS stress-block profile using real c, d, γ from the section.
    If show_lever_arm=True, also draws the lever arm z between C and T.
    """
    D = get_param("D") or 600.0

    if c is None or (isinstance(c, float) and math.isnan(c)):
        c = 0.15 * D
    if d is None or (isinstance(d, float) and math.isnan(d)):
        # simple fallback
        cover_bot = get_param("cover_bot") or 40.0
        db_bot = get_param("db_bot") or 24.0
        d = D - cover_bot - db_bot / 2.0

    # nice scaling for tension arrow length
    steel_len = max(abs(fs_t), 1.0)
    block_width = steel_len / 3.0

    fig, ax = plt.subplots(figsize=(3.0, 4.0))

    # vertical axis
    ax.axvline(0, color="black", linewidth=1)

    # compression block
    block_top = 0.0
    block_depth = gamma * c
    block_depth = max(0.0, min(block_depth, D))
    block_bottom = block_top + block_depth
    x_left = 0.0
    x_right = block_width

    ax.fill_between(
        [x_left, x_right],
        [block_top, block_top],
        [block_bottom, block_bottom],
        edgecolor="tab:red",
        facecolor="none",
        linewidth=1.5,
    )

    # neutral axis
    ax.axhline(c, color="black", linestyle="--", linewidth=0.8)

    # α2 f'c label just below NA
    y_alpha = c + 0.05 * D
    ax.annotate(
        "",
        xy=(x_left, y_alpha),
        xytext=(x_right, y_alpha),
        arrowprops=dict(arrowstyle="<->", linewidth=1.3, color="tab:red"),
    )
    ax.text(
        (x_left + x_right) / 2.0,
        y_alpha - 0.04 * D,
        r"$\alpha_2 f'_c$",
        ha="center",
        va="top",
        color="tab:red",
    )

    # γc vertical arrow
    x_gc = x_right + 0.15 * x_right
    ax.annotate(
        "",
        xy=(x_gc, block_bottom),
        xytext=(x_gc, block_top),
        arrowprops=dict(arrowstyle="<->", linewidth=1.2, color="tab:red"),
    )
    ax.text(
        x_gc + 0.05 * x_right,
        (block_top + block_bottom) / 2,
        r"$\gamma c$",
        va="center",
        color="tab:red",
    )

    # compression arrows inside block
    for frac in [0.25, 0.5, 0.75]:
        y_mid = block_top + frac * block_depth
        ax.annotate(
            "",
            xy=(x_left + 0.1 * block_width, y_mid),
            xytext=(x_right - 0.1 * block_width, y_mid),
            arrowprops=dict(arrowstyle="->", linewidth=1.0, color="tab:red"),
        )

    # resultant C
    C_y = (block_top + block_bottom) / 2
    ax.annotate(
        "",
        xy=(x_left, C_y),
        xytext=(x_right * 0.8, C_y),
        arrowprops=dict(arrowstyle="->", linewidth=1.5, color="tab:red"),
    )
    ax.text(
        x_left - 0.08 * block_width,
        C_y,
        "C",
        ha="right",
        va="center",
        color="tab:red",
    )

    # tension arrow at depth d
    T_y = d
    ax.annotate(
        "",
        xy=(steel_len, T_y),
        xytext=(0.0, T_y),
        arrowprops=dict(arrowstyle="->", linewidth=1.6, color="tab:blue"),
    )
    ax.text(
        steel_len * 1.02,
        T_y,
        f"T ({fs_t:.0f} MPa)",
        ha="left",
        va="center",
        color="tab:blue",
    )

    # optional lever arm z between C and T
    if show_lever_arm:
        z = d - C_y
        x_z = steel_len * 1.15
        ax.annotate(
            "",
            xy=(x_z, d),
            xytext=(x_z, C_y),
            arrowprops=dict(arrowstyle="<->", linewidth=1.2, color="black"),
        )
        ax.text(
            x_z + 0.05 * x_right,
            (d + C_y) / 2.0,
            "z",
            va="center",
            color="black",
        )

    x_max = steel_len * 1.3
    ax.set_xlim(-0.15 * x_max, x_max)
    ax.set_xticks([])
    ax.set_ylim(D, 0)
    ax.set_xlabel("Stress (MPa)")
    title = "ULS Stress-block Profile"
    if show_lever_arm:
        title += " (showing lever arm z)"
    ax.set_title(title, pad=18)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    return fig


# ------------------------------------------------------------
#  STRESS–STRAIN PROFILE HELPERS (AS3600 α2–γ)
# ------------------------------------------------------------
# -----------------------------
# Helper: lay out bars in rows (for section diagram)
# -----------------------------
def _layout_bars_in_rows(n_bars, b, cover, db, min_spacing, n_rows_max=2):
    """
    Return a list of (x_rel, row_index) for bars.
    row_index = 0 for first row (bottom or top, depending on caller),
                1 for row above/below, etc.

    If spacing is too tight for a single row, bars are wrapped into a new row.
    """
    if n_bars is None or n_bars <= 0:
        return []

    n_bars = int(n_bars)
    inner = max(b - 2 * cover, db)

    # Try to fit in 1 row
    if n_bars == 1:
        n_per_row = [1]
    else:
        spacing_1row = inner / (n_bars - 1)
        if spacing_1row >= min_spacing or n_rows_max == 1:
            n_per_row = [n_bars]
        else:
            # Simple 2-row layout: round up into first row, rest in second
            n1 = math.ceil(n_bars / 2)
            n2 = n_bars - n1
            n_per_row = [n1, n2]

    coords = []
    bar_index = 0
    for row_idx, n_in_row in enumerate(n_per_row):
        if n_in_row <= 0:
            continue
        if n_in_row == 1:
            xs = [b / 2.0]
        else:
            inner = max(b - 2 * cover, db)
            spacing_row = inner / (n_in_row - 1)
            spacing_row = max(spacing_row, min_spacing)
            xs = [cover + spacing_row * i for i in range(n_in_row)]
        for x in xs:
            coords.append((x, row_idx))
            bar_index += 1
            if bar_index >= n_bars:
                break
        if bar_index >= n_bars:
            break
    return coords

def _stress_strain_state(state: str):
    """
    Compute neutral axis and strain/stress info for the demo diagram.
    Uses:
        b, D, d, fc, fsy, Ast_bot from shared parameters.
    Treats Ast_bot & d as the resultant bottom steel layer.
    """
    b = get_param("b")
    D = get_param("D")
    d = get_param("d")
    fc = get_param("fc")
    fsy = get_param("fsy")
    As = get_param("Ast_bot")
    Ec = get_param("Ec")
    Es = get_param("Es")

    if fc is None:
        fc = 32.0
    if Ec is None:
        Ec = 4700 * math.sqrt(fc)
    if Es is None:
        Es = 200000.0

    # AS3600 α2–γ
    alpha2_raw = 0.85 - 0.0015 * fc
    gamma_raw = 0.97 - 0.0025 * fc
    alpha2 = max(0.67, alpha2_raw)
    gamma = max(0.67, gamma_raw)

    # Default strains
    eps_cu_uls = 0.003
    eps_c_sls = 0.0008
    eps_ext_unc = 0.0002

    # Fallback geometry
    ...
    # (rest of your existing code from here down)

# -----------------------------
# Helper: lay out bars in rows (for section diagram)
# -----------------------------
def _layout_bars_in_rows(n_bars, b, cover, db, min_spacing, n_rows_max=2):
    """
    Return a list of (x_rel, row_index) for bars.
    row_index = 0 for first row (bottom or top, depending on caller),
                1 for row above/below, etc.

    If spacing is too tight for a single row, bars are wrapped into a new row.
    """
    if n_bars is None or n_bars <= 0:
        return []

    n_bars = int(n_bars)
    inner = max(b - 2 * cover, db)

    # Try to fit in 1 row
    if n_bars == 1:
        n_per_row = [1]
    else:
        spacing_1row = inner / (n_bars - 1)
        if spacing_1row >= min_spacing or n_rows_max == 1:
            n_per_row = [n_bars]
        else:
            # Simple 2-row layout: round up into first row, rest in second
            n1 = math.ceil(n_bars / 2)
            n2 = n_bars - n1
            n_per_row = [n1, n2]

    coords = []
    bar_index = 0
    for row_idx, n_in_row in enumerate(n_per_row):
        if n_in_row <= 0:
            continue
        if n_in_row == 1:
            xs = [b / 2.0]
        else:
            inner = max(b - 2 * cover, db)
            spacing_row = inner / (n_in_row - 1)
            spacing_row = max(spacing_row, min_spacing)
            xs = [cover + spacing_row * i for i in range(n_in_row)]
        for x in xs:
            coords.append((x, row_idx))
            bar_index += 1
            if bar_index >= n_bars:
                break
        if bar_index >= n_bars:
            break
    return coords

    
    # Default strains
    eps_cu_uls = 0.003
    eps_c_sls = 0.0008
    eps_ext_unc = 0.0002

    # Fallback geometry
    if D is None:
        D = 600.0
    if d is None:
        d = 0.9 * D
    if b is None:
        b = 300.0
    if As is None:
        As = 500.0

    if state == "ULS":
        denom = alpha2 * fc * b * gamma
        c = As * fsy / denom if denom > 0 else D / 2.0
        c = min(max(c, 1.0), D - 1.0)
        eps_c = -eps_cu_uls
        eps_s = -eps_c * (d - c) / c
        fs_t = fsy
        return dict(c=c, eps_c=eps_c, eps_s=eps_s, gamma=gamma, fs_t=fs_t)

    if state == "SLS (cracked)":
        n = Es / Ec
        a = b / 2.0
        bq = n * As
        cq = -n * As * d
        discr = bq ** 2 - 4 * a * cq
        if discr < 0:
            c = D / 2.0
        else:
            r1 = (-bq + math.sqrt(discr)) / (2 * a)
            r2 = (-bq - math.sqrt(discr)) / (2 * a)
            cands = [r for r in (r1, r2) if 0 < r < D]
            c = cands[0] if cands else D / 2.0
        c = min(max(c, 1.0), D - 1.0)
        eps_c = -eps_c_sls
        eps_s = -eps_c * (d - c) / c
        fs_t = Es * eps_s
        return dict(c=c, eps_c=eps_c, eps_s=eps_s, gamma=0.8, fs_t=fs_t)

    # Uncracked
    c = D / 2.0
    eps_c = -eps_ext_unc
    eps_s = eps_ext_unc * (d - c) / c
    fs_t = Ec * abs(eps_s)
    return dict(c=c, eps_c=eps_c, eps_s=eps_s, gamma=1.0, fs_t=fs_t)


def _plot_stress_strain_profiles(state_dict):
    """
    Draw SECTION + strain profile + AS3600 α2–γ stress block side-by-side.
    Order (left → right):
        1) ULS cross-section (real b, D, d, c, reo circles; multi-row if needed)
        2) Strain profile
        3) Stress-block profile
    All share the same vertical depth axis so they line up nicely.
    """
    c = state_dict["c"]
    eps_c = state_dict["eps_c"]
    eps_s = state_dict["eps_s"]
    gamma = state_dict["gamma"]
    fs_t = state_dict["fs_t"]

    # --- geometry & reo from session state (with safe fallbacks) ---
    b = get_param("b") or 300.0
    D = get_param("D") or 600.0
    d = get_param("d")
    nb_bot = get_param("nb_bot")
    db_bot = get_param("db_bot")
    cover_bot = get_param("cover_bot")
    rowgap_bot = get_param("rowgap_bot")
    nb_top = get_param("nb_top")
    db_top = get_param("db_top")
    cover_top = get_param("cover_top")
    rowgap_top = get_param("rowgap_top")
    fc = get_param("fc") or 32.0

    # stress-block value α2 f'c (for label only – width is fixed visually)
    alpha2_raw = 0.85 - 0.0015 * fc
    alpha2_sb = max(0.67, alpha2_raw)
    sigma_c = alpha2_sb * fc  # MPa

    # fallbacks so figure always draws
    if cover_bot is None or cover_bot <= 0:
        cover_bot = 40.0
    if cover_top is None or cover_top <= 0:
        cover_top = 40.0
    if db_bot is None or db_bot <= 0:
        db_bot = 24.0
    if db_top is None or db_top <= 0:
        db_top = 16.0
    if nb_bot is None or nb_bot < 1:
        nb_bot = 3
    if nb_top is None or nb_top < 1:
        nb_top = 2

    nb_bot = int(nb_bot)
    nb_top = int(nb_top)

    if d is None or (isinstance(d, float) and math.isnan(d)):
        d = D - cover_bot - db_bot / 2.0

    if c is None or (isinstance(c, float) and math.isnan(c)):
        c = 0.15 * D

    # horizontal scaling
    eps_max = max(abs(eps_c), abs(eps_s)) * 1.3 or 1e-4
    steel_len = max(abs(fs_t), 1.0)           # arrow length for T (MPa → “mm”)
    block_width = steel_len / 3.0             # visual rule: always 1/3 of T arrow

    # 3 panels: section, strain, stress – share y (depth) axis
    fig, (ax_sec, ax_strain, ax_stress) = plt.subplots(
        1, 3, figsize=(8.5, 3.0), sharey=True
    )
    fig.subplots_adjust(wspace=0.4)

    # -------------------------------------------------
    # 1) ULS CROSS-SECTION (left)
    # -------------------------------------------------
    ax_sec.add_patch(
        Rectangle((0, 0), b, D, fill=False, linewidth=1.5, edgecolor="black")
    )

    # compression block (0 → γc)
    block_depth = max(0.0, min(gamma * c, D))
    ax_sec.add_patch(
        Rectangle(
            (0, 0),
            b,
            block_depth,
            facecolor="#c7e3ff",
            edgecolor="tab:red",
            linewidth=1.0,
            alpha=0.8,
        )
    )

    # ---------- bottom bars with row wrapping ----------
    min_spacing_bot = 2.0 * db_bot
    bot_layout = _layout_bars_in_rows(
        n_bars=nb_bot,
        b=b,
        cover=cover_bot,
        db=db_bot,
        min_spacing=min_spacing_bot,
        n_rows_max=2,
    )
    r_bot = db_bot / 2.0
    default_pitch_bot = db_bot + 15.0
    row_pitch_bot = rowgap_bot if rowgap_bot not in (None, 0) else default_pitch_bot

    for x_rel, row_idx in bot_layout:
        x = x_rel
        y = d - row_idx * row_pitch_bot   # higher rows move up
        ax_sec.add_patch(
            Circle(
                (x, y),
                radius=r_bot,
                facecolor="none",
                edgecolor="tab:blue",
                linewidth=1.4,
            )
        )

    # ---------- top bars with row wrapping ----------
    min_spacing_top = 2.0 * db_top
    top_layout = _layout_bars_in_rows(
        n_bars=nb_top,
        b=b,
        cover=cover_top,
        db=db_top,
        min_spacing=min_spacing_top,
        n_rows_max=2,
    )
    r_top = db_top / 2.0
    y_top_base = cover_top + db_top / 2.0
    default_pitch_top = db_top + 15.0
    row_pitch_top = rowgap_top if rowgap_top not in (None, 0) else default_pitch_top

    for x_rel, row_idx in top_layout:
        x = x_rel
        y = y_top_base + row_idx * row_pitch_top   # extra rows move downward
        ax_sec.add_patch(
            Circle(
                (x, y),
                radius=r_top,
                facecolor="none",
                edgecolor="tab:red",
                linewidth=1.4,
            )
        )

    # NA arrow & label WITH value (only on section view)
    x_na = b + 0.18 * b
    ax_sec.annotate(
        "",
        xy=(x_na, c),
        xytext=(x_na, 0),
        arrowprops=dict(arrowstyle="<->", linewidth=1.0),
    )
    ax_sec.text(
        x_na + 0.05 * b,
        c / 2.0,
        f"NA = {c:.0f} mm",
        va="center",
        fontsize=9,
        color="tab:red",
    )

    # d arrow & label
    x_d = b + 0.45 * b
    ax_sec.annotate(
        "",
        xy=(x_d, d),
        xytext=(x_d, 0),
        arrowprops=dict(arrowstyle="<->", linewidth=1.0),
    )
    ax_sec.text(
        x_d + 0.05 * b,
        d / 2.0,
        f"d ({d:.0f} mm)",
        va="center",
        fontsize=9,
    )

    ax_sec.set_xlim(-0.1 * b, 1.8 * b)
    ax_sec.set_xlabel("Section")
    ax_sec.set_ylabel("Depth (mm)")
    ax_sec.set_title("Section (ULS view)", pad=20)
    ax_sec.spines["top"].set_visible(False)
    ax_sec.spines["right"].set_visible(False)

    # -------------------------------------------------
    # 2) STRAIN PROFILE (middle)
    # -------------------------------------------------
    y_vals = np.array([0.0, c, d])
    eps_vals = np.array([eps_c, 0.0, eps_s])

    ax_strain.axvline(0, color="black", linewidth=1)
    ax_strain.plot(eps_vals, y_vals, color="black")
    ax_strain.axhline(c, color="black", linestyle="--", linewidth=0.8)

    ax_strain.text(
        eps_c,
        0.0,
        rf"$\varepsilon_c = {eps_c:.4f}$",
        ha="right" if eps_c < 0 else "left",
        va="bottom",
        color="tab:red",
    )
    ax_strain.text(
        eps_s,
        d,
        rf"$\varepsilon_s = {eps_s:.4f}$",
        ha="left" if eps_s > 0 else "right",
        va="top",
        color="tab:blue",
    )

    ax_strain.set_xticks([])
    ax_strain.set_xlim(-eps_max, eps_max)
    ax_strain.set_xlabel("Strain")
    ax_strain.set_title("Strain Profile", pad=20)
    ax_strain.spines["top"].set_visible(False)
    ax_strain.spines["right"].set_visible(False)

    # -------------------------------------------------
    # 3) STRESS-BLOCK PROFILE (right)
    # -------------------------------------------------
    ax_stress.axvline(0, color="black", linewidth=1)

    block_top = 0.0
    block_depth_sb = gamma * c
    block_bottom = block_top + block_depth_sb
    x_left = 0.0
    x_right = block_width

    # block outline
    ax_stress.fill_between(
        [x_left, x_right],
        [block_top, block_top],
        [block_bottom, block_bottom],
        edgecolor="tab:red",
        facecolor="none",
        linewidth=1.5,
    )

    # NA line (no label here – only on section)
    ax_stress.axhline(c, color="black", linestyle="--", linewidth=0.8)

    # α2 f'c arrow & label (below the arrow)
    y_alpha = c + 0.05 * D
    ax_stress.annotate(
        "",
        xy=(x_left, y_alpha),
        xytext=(x_right, y_alpha),
        arrowprops=dict(arrowstyle="<->", linewidth=1.3, color="tab:red"),
    )
    ax_stress.text(
        (x_left + x_right) / 2.0,
        y_alpha + 0.08 * D,   # below, since y increases downward
        rf"$\alpha_2 f'_c = {sigma_c:.0f}\ \mathrm{{MPa}}$",
        ha="center",
        va="top",
        color="tab:red",
    )

    # γc vertical arrow & value
    x_gc = x_right + 0.20 * x_right
    ax_stress.annotate(
        "",
        xy=(x_gc, block_bottom),
        xytext=(x_gc, block_top),
        arrowprops=dict(arrowstyle="<->", linewidth=1.2, color="tab:red"),
    )
    val_gammac = gamma * c
    ax_stress.text(
        x_gc + 0.08 * x_right,
        (block_top + block_bottom) / 2.0,
        rf"$\gamma c = {val_gammac:.0f}\ \mathrm{{mm}}$",
        va="center",
        color="tab:red",
    )

    # internal compression arrows – now flipped (pointing LEFT)
    for frac in [0.25, 0.5, 0.75]:
        y_mid = block_top + frac * block_depth_sb
        ax_stress.annotate(
            "",
            xy=(x_left + 0.15 * block_width, y_mid),          # arrow head
            xytext=(x_right - 0.15 * block_width, y_mid),     # tail
            arrowprops=dict(arrowstyle="->", linewidth=1.0, color="tab:red"),
        )

    # resultant C – also pointing LEFT
    C_y = (block_top + block_bottom) / 2.0
    ax_stress.annotate(
        "",
        xy=(x_left, C_y),                     # head at left
        xytext=(x_right * 0.8, C_y),         # tail inside block
        arrowprops=dict(arrowstyle="->", linewidth=1.5, color="tab:red"),
    )
    ax_stress.text(
        x_left - 0.08 * block_width,
        C_y,
        "C",
        ha="right",
        va="center",
        color="tab:red",
    )

    # tension arrow at depth d (unchanged)
    T_y = d
    ax_stress.annotate(
        "",
        xy=(steel_len, T_y),
        xytext=(0.0, T_y),
        arrowprops=dict(arrowstyle="->", linewidth=1.6, color="tab:blue"),
    )
    ax_stress.text(
        steel_len * 1.02,
        T_y,
        f"T ({fs_t:.0f} MPa)",
        ha="left",
        va="center",
        color="tab:blue",
    )

    x_max = steel_len * 1.3
    ax_stress.set_xlim(-0.15 * x_max, x_max)
    ax_stress.set_xticks([])
    ax_stress.set_xlabel("Stress (MPa)")
    ax_stress.set_title("Stress-block Profile (AS3600 α₂–γ)", pad=20)
    ax_stress.spines["top"].set_visible(False)
    ax_stress.spines["right"].set_visible(False)

    # enforce common vertical scale
    for ax in (ax_sec, ax_strain, ax_stress):
        ax.set_ylim(D, 0)

    return fig



# ------------------------------------------------------------
#  PAGE RENDER
# ------------------------------------------------------------
def render_bending():
    st.title("Bending Capacity")

    sync_callbacks = get_sync_callbacks()
    apply_global_widget_css()  # same styling as Inputs page

    # ============================================================
    #  SIDEBAR GLOSSARY (BENDING TERMS)
    # ============================================================
    with st.sidebar.expander("📘 Glossary – Bending terms", expanded=False):
        st.markdown(
            """
            **Mu*** – Factored design bending moment at the critical section (kNm).  
            **b** – Beam/web width (mm).  
            **D** – Overall section depth (mm).  
            **d** – Effective depth to tension steel (mm).  
            **Ast,bot** – Area of bottom (tension) reinforcement (mm²).  
            **As_min** – Minimum required tensile steel for ductile behaviour.  
            **f'c** – Concrete cylinder strength (MPa).  
            **fsy** – Steel yield strength (MPa).  
            **Ec, Es** – Elastic moduli of concrete and steel (MPa).  

            **c** – Neutral axis depth from the top fibre (mm).  
            **a = γc** – Equivalent rectangular stress block depth (mm).  
            **kᵤ = c/d** – Neutral axis depth ratio (ductility indicator).  
            **α₂, γ** – AS 3600-style stress block factors (teaching values).  
            **ϕ** – Strength reduction factor for bending.  

            **M_cr** – Cracking moment (kNm) based on f_ct,f and gross section.  
            **M_u** – Nominal flexural capacity (kNm).  
            **ϕM_u,cap** – Design flexural capacity (kNm).  
            **Utilisation** – M_u* / ϕM_u,cap → should be ≤ 1.0.  
            """
        )

    # ============================================================
    #  TOP RESULT SUMMARY (Ast, As_min, φMu, ku, utilisation)
    # ============================================================
    top_results = _compute_bending_capacity()
    Ast = get_param("Ast_bot")
    Mu_star = get_param("Mu_star")

    phi_Mu_cap_top = top_results["phi_Mu_cap"]
    Mu_util_top = top_results["Mu_util"]
    ku_top = top_results["ku"]
    As_min_top = top_results["As_min"]

    def _status_colour(flag):
        if flag is None:
            return "Not calculated", "#e0e0e0"
        return ("OK", "#d5f5d5") if flag else ("Check", "#f8d0d0")

    # checks for summary card
    As_ok = None
    if Ast is not None and As_min_top and not math.isnan(As_min_top):
        As_ok = Ast >= As_min_top

    Mu_ok = None
    if phi_Mu_cap_top and phi_Mu_cap_top > 0 and Mu_star is not None:
        Mu_ok = Mu_star <= phi_Mu_cap_top

    ku_ok = None
    if ku_top is not None and not math.isnan(ku_top):
        ku_ok = (0.0 < ku_top <= 0.36)  # teaching limit

    As_status, As_colour = _status_colour(As_ok)
    Mu_status, Mu_colour = _status_colour(Mu_ok)
    ku_status, ku_colour = _status_colour(ku_ok)

    Ast_str = f"{Ast:.1f} mm²" if Ast not in (None, float("nan")) else "—"
    As_min_str = (
        f"{As_min_top:.1f} mm²" if As_min_top and not math.isnan(As_min_top) else "—"
    )
    phiMu_str = (
        f"{phi_Mu_cap_top:.2f} kNm"
        if phi_Mu_cap_top and phi_Mu_cap_top > 0
        else "—"
    )
    Mu_star_str = f"{Mu_star:.2f} kNm" if Mu_star not in (None, float("nan")) else "—"
    Mu_util_str = (
        f"{Mu_util_top:.3f}" if phi_Mu_cap_top and phi_Mu_cap_top > 0 else "—"
    )
    ku_str = (
        f"{ku_top:.3f}"
        if ku_top is not None and not math.isnan(ku_top)
        else "—"
    )

    summary_html = f"""
    <div style="
        border: 1px solid #cccccc;
        border-radius: 8px;
        padding: 0.5rem 0.75rem;
        margin-bottom: 1rem;
        max-width: 900px;
    ">
      <table style="width: 100%; border-collapse: collapse; font-size: 0.9rem;">
        <thead>
          <tr style="background-color: #f5f5f5;">
            <th style="text-align:left; padding: 4px 6px;">Item</th>
            <th style="text-align:right; padding: 4px 6px;">Value</th>
            <th style="text-align:right; padding: 4px 6px;">Criterion</th>
            <th style="text-align:center; padding: 4px 6px;">Status</th>
          </tr>
        </thead>
        <tbody>
          <tr style="background-color: {As_colour};">
            <td style="padding: 4px 6px;"><strong>Steel area Ast,bot</strong></td>
            <td style="text-align:right; padding: 4px 6px;">{Ast_str}</td>
            <td style="text-align:right; padding: 4px 6px;">≥ As,min = {As_min_str}</td>
            <td style="text-align:center; padding: 4px 6px;"><strong>{As_status}</strong></td>
          </tr>
          <tr style="background-color: {Mu_colour};">
            <td style="padding: 4px 6px;"><strong>Flexural capacity</strong></td>
            <td style="text-align:right; padding: 4px 6px;">ϕM<sub>u,cap</sub> = {phiMu_str}</td>
            <td style="text-align:right; padding: 4px 6px;">M<sub>u</sub>* = {Mu_star_str}</td>
            <td style="text-align:center; padding: 4px 6px;">
              Util = {Mu_util_str}<br><strong>{Mu_status}</strong>
            </td>
          </tr>
          <tr style="background-color: {ku_colour};">
            <td style="padding: 4px 6px;"><strong>Neutral axis ratio k<sub>u</sub></strong></td>
            <td style="text-align:right; padding: 4px 6px;">k<sub>u</sub> = {ku_str}</td>
            <td style="text-align:right; padding: 4px 6px;">Limit (teaching) ≤ 0.36</td>
            <td style="text-align:center; padding: 4px 6px;"><strong>{ku_status}</strong></td>
          </tr>
        </tbody>
      </table>
    </div>
    """

    st.markdown("### Bending – Result Summary")
    st.markdown(summary_html, unsafe_allow_html=True)

    # ------------------------------------------------------------------
    #  Values we need later for the table, diagrams and step-by-step
    # ------------------------------------------------------------------
    phi_Mu_cap = top_results["phi_Mu_cap"]
    Mu_util = top_results["Mu_util"]
    c = top_results["c"]
    a = top_results["a"]
    z = top_results["z"]
    ku = top_results["ku"]
    alpha2 = top_results["alpha2"]
    gamma = top_results["gamma"]
    phi = top_results["phi"]
    fctf = top_results["fctf"]
    I_gross = top_results["I_gross"]
    Z_gross = top_results["Z_gross"]
    Mcr = top_results["Mcr"]
    As_min = top_results["As_min"]

    # Shared values for reporting / diagrams
    b = get_param("b")
    D = get_param("D")
    d = get_param("d")
    fc = get_param("fc")
    fsy = get_param("fsy")
    Ec = get_param("Ec")
    Es = get_param("Es")
    Mu_star = get_param("Mu_star")
    N_star = get_param("N_star")
    P_star = get_param("P_star")
    nb_bot = get_param("nb_bot")
    db_bot = get_param("db_bot")
    cover_bot = get_param("cover_bot")
    nb_top = get_param("nb_top")
    db_top = get_param("db_top")
    cover_top = get_param("cover_top")

    # Local copies for stress-block per code (for the table & ULS tab)
    fc_local = fc if fc is not None else 40.0
    D_local = D if D is not None else 600.0
    cover_bot_local = cover_bot if cover_bot is not None else 40.0
    db_bot_local = db_bot if db_bot is not None else 20.0
    nb_bot_local = int(nb_bot) if nb_bot is not None else 4

    d_eff = d
    if d_eff is None or (isinstance(d_eff, float) and math.isnan(d_eff)):
        d_eff = D_local - cover_bot_local - 0.5 * db_bot_local

    Ast_bot = Ast
    if Ast_bot is None or (isinstance(Ast_bot, float) and math.isnan(Ast_bot)):
        Ast_bot = nb_bot_local * math.pi * db_bot_local**2 / 4.0

    alpha2_raw = 0.85 - 0.0015 * fc_local
    gamma_raw = 0.97 - 0.0025 * fc_local
    alpha2_sb = max(0.67, alpha2_raw)
    gamma_sb = max(0.67, gamma_raw)
    phi_b = get_param("phi_bend", 0.85)
    ku_sb = ku if ku is not None else float("nan")

    Mu_min = (
        1.2 * Mcr
        if (Mcr is not None and not (isinstance(Mcr, float) and math.isnan(Mcr)))
        else float("nan")
    )

    Mu_nom_report = phi_Mu_cap / phi if phi and phi > 0 else float("nan")

    st.markdown("---")

    # ============================================================
    #  DESIGN ACTIONS (Mu*, N*, P*) – WITH INSIGHTS
    # ============================================================
    st.subheader("Design Actions for Bending")

    da1, da2, da3 = st.columns(3)
    sync = sync_callbacks

    with da1:
        number_row(
            "Design moment Mu* (kNm)",
            "bending_Mu_star",
            10.0,
            sync,
            help_text=(
                "Factored design bending moment at the critical section. "
                "Increasing Mu* increases bending demand and utilisation."
            ),
        )
    with da2:
        number_row(
            "Axial force N* (kN)",
            "bending_N_star",
            50.0,
            sync,
            help_text=(
                "Axial force acting with bending. Compression (negative in many "
                "conventions) can reduce tension in the steel; tension increases demand."
            ),
        )
    with da3:
        number_row(
            "Prestress force P* (kN)",
            "bending_P_star",
            50.0,
            sync,
            help_text=(
                "Prestress / pre-compression in the section. Increasing P* typically "
                "reduces tensile demand in the bottom reinforcement."
            ),
        )

    st.markdown("---")

    # ============================================================
    #  MAIN INPUTS (GEOMETRY, MATERIALS, REO) – WITH INSIGHTS
    # ============================================================
    g1, g2 = st.columns(2)

    with g1:
        st.subheader("Geometry")
        number_row(
            "Width b (mm)",
            "bending_b",
            10.0,
            sync,
            help_text=(
                "Section width. Increasing b increases compression block area and "
                "reduces required tensile steel for a given Mu*."
            ),
        )
        number_row(
            "Depth D (mm)",
            "bending_D",
            10.0,
            sync,
            help_text=(
                "Overall section depth. Larger D increases lever arm (d) and "
                "typically increases bending capacity."
            ),
        )
        number_row(
            "Span L (mm)",
            "bending_L",
            100.0,
            sync,
            help_text=(
                "Member span. Used mainly for serviceability checks and linking to "
                "deflection; not directly in φMu,cap here."
            ),
        )

    with g2:
        st.subheader("Materials")
        number_row(
            "Concrete strength f'c (MPa)",
            "bending_fc",
            2.0,
            sync,
            help_text=(
                "Concrete compressive strength. Higher f'c increases compression "
                "capacity and may reduce required steel, but also changes ductility limits."
            ),
        )
        number_row(
            "Steel yield fsy (MPa)",
            "bending_fsy",
            10.0,
            sync,
            help_text=(
                "Yield strength of reinforcing steel. Higher fsy increases the "
                "force carried by a given area of steel."
            ),
        )
        number_row(
            "Ec (MPa)",
            "bending_Ec",
            1000.0,
            sync,
            help_text=(
                "Short-term modulus of concrete. Mainly affects stiffness and "
                "SLS behaviour rather than φMu,cap."
            ),
        )
        number_row(
            "Es (MPa)",
            "bending_Es",
            10000.0,
            sync,
            help_text=(
                "Steel modulus. Typically ~200,000 MPa; affects cracked-section "
                "stiffness and strain calculations."
            ),
        )

    st.markdown("---")

    r1, r2 = st.columns(2)

    with r1:
        st.subheader("Bottom Longitudinal Reinforcement")
        number_row(
            "Number of bottom bars nb_bot",
            "bending_nb_bot",
            1,
            sync,
            help_text=(
                "Number of tension bars at the bottom. Increasing nb_bot increases Ast,bot "
                "and hence bending capacity."
            ),
        )
        number_row(
            "Bottom bar diameter db_bot (mm)",
            "bending_db_bot",
            2.0,
            sync,
            help_text=(
                "Nominal diameter of bottom bars (e.g. N24 = 24 mm). Larger diameter "
                "bars increase Ast,bot but may impact spacing and ductility."
            ),
        )
        number_row(
            "Bottom row gap (mm)",
            "bending_rowgap_bot",
            5.0,
            sync,
            help_text=(
                "Vertical gap between bottom bar rows (if 2 rows are used). Increasing "
                "this moves the second row further from the tension face, increasing its lever arm."
            ),
        )
        number_row(
            "Bottom cover (mm)",
            "bending_cover_bot",
            5.0,
            sync,
            help_text=(
                "Concrete cover to bottom reinforcement. Increasing cover reduces "
                "effective depth d and reduces φMu,cap, but may be required for durability."
            ),
        )

    with r2:
        st.subheader("Top Longitudinal Reinforcement")
        number_row(
            "Number of top bars nb_top",
            "bending_nb_top",
            1,
            sync,
            help_text=(
                "Number of top bars (compression or hanger steel). "
                "Important for negative moment regions and detailing."
            ),
        )
        number_row(
            "Top bar diameter db_top (mm)",
            "bending_db_top",
            2.0,
            sync,
            help_text="Nominal diameter of top bars (e.g. N16 = 16 mm).",
        )
        number_row(
            "Top row gap (mm)",
            "bending_rowgap_top",
            5.0,
            sync,
            help_text=(
                "Vertical gap between top bar rows if more than one row is used."
            ),
        )
        number_row(
            "Top cover (mm)",
            "bending_cover_top",
            5.0,
            sync,
            help_text=(
                "Concrete cover to top reinforcement. Affects effective depth to "
                "compression reinforcement and durability."
            ),
        )

    st.markdown("---")

    # ============================================================
    #  DETAILED SUMMARY (TABLE) + SECTION & STRESS–STRAIN DIAGRAMS
    # ============================================================
    st.subheader("Bending Capacity – Detailed Summary (values only)")

    rows = [
        {"Parameter": "Minimum steel",          "Symbol": "As,min",   "Value": _fmt(As_min, "{:.1f}"),        "Units": "mm²"},
        {"Parameter": "Cracking moment",        "Symbol": "Mcr",      "Value": _fmt(Mcr, "{:.2f}"),           "Units": "kNm"},
        {"Parameter": "Minimum cracking moment","Symbol": "Mu,min",   "Value": _fmt(Mu_min, "{:.2f}"),        "Units": "kNm"},
        {"Parameter": "Gross Z",                "Symbol": "Zg",       "Value": _fmt(Z_gross, "{:.3e}"),       "Units": "mm³"},
        {"Parameter": "α₂",                     "Symbol": "α2",       "Value": _fmt(alpha2_sb, "{:.3f}"),     "Units": "•"},
        {"Parameter": "γ",                      "Symbol": "γ",        "Value": _fmt(gamma_sb, "{:.3f}"),      "Units": "•"},
        {"Parameter": "Strength reduction",     "Symbol": "φb",       "Value": _fmt(phi_b, "{:.3f}"),         "Units": "•"},
        {"Parameter": "Neutral axis depth",     "Symbol": "c",        "Value": _fmt(c, "{:.2f}"),             "Units": "mm"},
        {"Parameter": "Block depth",            "Symbol": "a = γc",   "Value": _fmt(a, "{:.2f}"),             "Units": "mm"},
        {"Parameter": "Neutral axis ratio",     "Symbol": "ku = c/d", "Value": _fmt(ku_sb, "{:.3f}"),         "Units": "•"},
        {"Parameter": "Lever arm",              "Symbol": "z",        "Value": _fmt(z, "{:.2f}"),             "Units": "mm"},
        {"Parameter": "Nominal moment",         "Symbol": "Mu",       "Value": _fmt(Mu_nom_report, "{:.2f}"), "Units": "kNm"},
        {"Parameter": "Design moment cap.",     "Symbol": "φMu,cap",  "Value": _fmt(phi_Mu_cap, "{:.2f}"),    "Units": "kNm"},
        {"Parameter": "Design moment used",     "Symbol": "Mu*",      "Value": _fmt(Mu_star, "{:.2f}"),       "Units": "kNm"},
    ]

    df_summary = pd.DataFrame(rows)
    st.dataframe(df_summary, hide_index=True, use_container_width=True)

    # --- Diagrams: section + strain + stress-block in ONE figure ---
    st.markdown("### Section & stress–strain model")

    strain_state = st.radio(
        "State:",
        ["ULS", "SLS (cracked)", "Uncracked"],
        horizontal=True,
        key="bending_strain_state_local",
    )

    ss_state = _stress_strain_state(strain_state)
    fig_ss = _plot_stress_strain_profiles(ss_state)
    st.pyplot(fig_ss, use_container_width=True)

       # ============================================================
    #  STEP-BY-STEP TABS (ULS / SLS)
    # ============================================================
    tab_uls, tab_sls = st.tabs(["ULS step-by-step", "SLS step-by-step"])

    # ----- ULS detailed tab -----
    with tab_uls:
        st.subheader("ULS Calculation (step-by-step)")

        if phi_Mu_cap > 0 and d and Ast:

            # =======================
            # Section 1 – inputs + ULS cross-section
            # =======================
            st.markdown("### 1. Required calculated inputs for bending")
            col1_text, col1_fig = st.columns([3, 2])

            with col1_text:
                st.markdown("#### 1.1 Effective depth $d$")
                st.latex(r"d = D - \text{cover}_{bot} - \frac{d_{b,bot}}{2}")
                st.latex(
                    rf"d = {D:.1f} - {cover_bot:.1f} - "
                    rf"\frac{{{db_bot:.1f}}}{2}"
                )
                st.latex(rf"d = {d:.1f}\,\text{{ mm}}")

                st.markdown("#### 1.2 Bottom steel area $A_{st,bot}$")
                st.latex(r"A_{st,bot} = n_{b,bot}\,\frac{\pi d_{b,bot}^2}{4}")
                st.latex(
                    rf"A_{{st,bot}} = {int(nb_bot):d}\,"
                    rf"\frac{{\pi \times {db_bot:.1f}^2}}{4}"
                )
                st.latex(rf"A_{{st,bot}} = {Ast:.1f}\,\text{{ mm}}^2")

            with col1_fig:
                fig_uls_sec1 = _make_cross_section_figure(
                    b or 300.0,
                    D or 600.0,
                    d,
                    a,
                    nb_bot,
                    db_bot,
                    cover_bot,
                    nb_top=nb_top,
                    db_top=db_top,
                    cover_top=cover_top,
                    c=c,
                    z=z,
                    show_compression=True,
                    title="ULS cross-section (cracked)",
                )
                if fig_uls_sec1 is not None:
                    st.pyplot(fig_uls_sec1, use_container_width=True)
                    plt.close(fig_uls_sec1)

            st.markdown("---")

            # =======================
            # Section 2 – stress-block parameters + ULS stress block
            # =======================
            st.markdown(
                "### 2. Stress-block parameters "
                "(AS 3600:2018 Cl. 8.1.3)"
            )
            col2_text, col2_fig = st.columns([3, 2])

            with col2_text:
                st.markdown("#### 2.1 $\\alpha_2$ factor")
                st.latex(r"\alpha_2 = 0.85 - 0.0015 f'_c \ge 0.67")
                st.latex(
                    rf"\alpha_2 = 0.85 - 0.0015 \times {fc:.1f}"
                    rf" = {alpha2_raw:.3f}"
                )
                st.latex(rf"\Rightarrow \alpha_2 = {alpha2_sb:.3f}")

                st.markdown("#### 2.2 $\\gamma$ factor")
                st.latex(r"\gamma = 0.97 - 0.0025 f'_c \ge 0.67")
                st.latex(
                    rf"\gamma = 0.97 - 0.0025 \times {fc:.1f}"
                    rf" = {gamma_raw:.3f}"
                )
                st.latex(rf"\Rightarrow \gamma = {gamma_sb:.3f}")

                st.markdown("#### 2.3 $k_u$ value")
                st.latex(rf"\phi_b = {phi_b:.2f}")
                st.latex(r"k_u = \dfrac{c}{d}")
                st.latex(
                    rf"k_u = \dfrac{{{c:.2f}}}{{{d:.1f}}} = {ku_sb:.3f}"
                )

            with col2_fig:
                fig_uls_sb_plain = _make_uls_stress_block_figure(
                    c, d, gamma_sb, fsy, show_lever_arm=False
                )
                st.pyplot(fig_uls_sb_plain, use_container_width=True)
                plt.close(fig_uls_sb_plain)

            st.markdown("---")

            # =======================
            # Section 3 – minimum strength + uncracked section
            # =======================
            st.markdown(
                "### 3. Minimum strength requirements "
                "(self-weight check – AS 3600 Cl. 8.1.6)"
            )
            col3_text, col3_fig = st.columns([3, 2])

            with col3_text:
                st.markdown(
                    "AS 3600 requires a minimum bending strength so that the beam "
                    "can support its own selfweight without cracking. Here we use "
                    "a teaching model based on concrete flexural tensile strength "
                    "and the gross section modulus."
                )

                st.markdown("#### 3.1 Concrete flexural tensile strength $f_{ct,f}$")
                st.latex(r"f_{ct,f} = c_b (f'_c)^{2/3}")
                st.latex(
                    rf"f_{{ct,f}} = 0.20 \times ({fc:.1f})^{{2/3}}"
                    rf" = {fctf:.3f}\,\text{{ MPa}}"
                )

                st.markdown("#### 3.2 Gross section modulus $Z_g$")
                st.latex(r"Z_g = \dfrac{b D^2}{6}")
                st.latex(
                    rf"Z_g = \dfrac{{{b:.1f} \times {D:.1f}^2}}{{6}}"
                    rf" = {Z_gross:.3e}\,\text{{ mm}}^3"
                )

                st.markdown("#### 3.3 Cracking moment $M_{cr}$")
                st.latex(r"M_{cr} = \dfrac{f_{ct,f} Z_g}{10^6}")
                st.latex(
                    rf"M_{{cr}} = \dfrac{{{fctf:.3f} \times {Z_gross:.3e}}}{{10^6}}"
                    rf" = {Mcr:.2f}\,\text{{ kNm}}"
                )

                Muo_min = Mu_min
                st.markdown(
                    "#### 3.4 Minimum required ultimate strength "
                    "$(M_{uo})_{min}$ (teaching simplification)"
                )
                st.markdown(
                    "For a non-prestressed member, we compare against "
                    "a teaching minimum moment based on the cracking moment:"
                )
                st.latex(r"(M_{uo})_{min} \approx 1.2\,M_{cr}")
                st.latex(
                    rf"(M_{{uo}})_{{min}} \approx 1.2 \times {Mcr:.2f}"
                    rf" = {Muo_min:.2f}\,\text{{ kNm}}"
                )

                st.markdown("#### 3.5 Minimum tensile reinforcement check")
                st.latex(
                    r"A_{st,\min} = k_{Ast}\left(\frac{d}{D}\right)^2 "
                    r"\frac{f_{ct,f}}{f_{sy}}\,bD"
                )
                st.latex(
                    rf"A_{{st,\min}} = 1.0 \left(\frac{{{d:.1f}}}{{{D:.1f}}}\right)^2"
                    rf"\left(\frac{{{fctf:.3f}}}{{{fsy:.1f}}}\right)"
                    rf"{b:.1f}\,{D:.1f} = {As_min:.1f}\,\text{{ mm}}^2"
                )
                st.markdown(
                    rf"Check: $A_{{st,bot}} = {Ast:.1f}\,\text{{ mm}}^2 "
                    rf"\;\ge\; A_{{st,\min}} = {As_min:.1f}\,\text{{ mm}}^2$"
                )
                st.markdown(
                    rf"Teaching minimum moment: "
                    rf"$M_{{u,\min}} \approx 1.2\,M_{{cr}} = {Muo_min:.2f}$ kNm."
                )

            with col3_fig:
                fig_uls_uncracked = _make_cross_section_figure(
                    b or 300.0,
                    D or 600.0,
                    d,
                    a,
                    nb_bot,
                    db_bot,
                    cover_bot,
                    nb_top=nb_top,
                    db_top=db_top,
                    cover_top=cover_top,
                    c=None,
                    z=None,
                    show_compression=False,
                    title="Uncracked elastic section (self-weight)",
                )
                if fig_uls_uncracked is not None:
                    st.pyplot(fig_uls_uncracked, use_container_width=True)
                    plt.close(fig_uls_uncracked)

            st.markdown("---")

            # =======================
            # Section 4 – φMu,cap + stress block with lever arm
            # =======================
            st.markdown("### 4. Ultimate flexural capacity $\\phi M_{u,cap}$")
            col4_text, col4_fig = st.columns([3, 2])

            with col4_text:
                st.markdown("#### 4.1 Internal forces and neutral-axis depth $c$")
                st.latex(
                    r"T = A_{st} f_{sy},\quad C = \alpha_2 f'_c b\, \gamma c"
                )
                T = Ast * fsy
                st.latex(
                    rf"T = {Ast:.1f} \times {fsy:.1f}"
                    rf" = {T:,.1f}\,\text{{ N}}"
                )
                st.latex(
                    r"C = T \Rightarrow "
                    r"c = \dfrac{T}{\alpha_2 f'_c b \gamma}"
                )
                st.latex(
                    rf"c = \dfrac{{{T:,.1f}}}{{{alpha2_sb:.2f} \times {fc:.1f}"
                    rf" \times {b:.1f} \times {gamma_sb:.2f}}}"
                    rf" = {c:.2f}\,\text{{ mm}}"
                )

                st.markdown("#### 4.2 Lever arm and nominal moment $M_u$")
                st.latex(r"a = \gamma c,\quad z = d - \dfrac{a}{2}")
                st.latex(
                    rf"a = {gamma_sb:.2f} \times {c:.2f}"
                    rf" = {a:.2f}\,\text{{ mm}}"
                )
                st.latex(
                    rf"z = {d:.1f} - \dfrac{{{a:.2f}}}{{2}}"
                    rf" = {z:.2f}\,\text{{ mm}}"
                )
                Mu_nom = phi_Mu_cap / phi
                st.latex(r"M_u = \dfrac{T z}{10^6}")
                st.latex(
                    rf"M_u = \dfrac{{{T:,.1f} \times {z:.2f}}}{{10^6}}"
                    rf" = {Mu_nom:.2f}\,\text{{ kNm}}"
                )

                st.markdown("#### 4.3 Factored capacity and utilisation")
                phiMu_str2 = f"{phi_Mu_cap:.2f}"
                Mu_star_str2 = f"{Mu_star:.2f}"
                util_str = f"{Mu_util:.3f}"

                st.latex(r"\phi M_{u,\mathrm{cap}} = \phi M_u")
                st.latex(
                    r"\phi M_{u,\mathrm{cap}} = "
                    + f"{phi:.2f}"
                    + r"\times "
                    + f"{Mu_nom:.2f}"
                    + r" = "
                    + phiMu_str2
                    + r"\,\text{kNm}"
                )
                st.latex(
                    r"\text{Utilisation} = "
                    r"\dfrac{M_u^*}{\phi M_{u,\mathrm{cap}}}"
                    r" = \dfrac{"
                    + Mu_star_str2
                    + r"}{"
                    + phiMu_str2
                    + r"} = "
                    + util_str
                )

                st.markdown(
                    rf"Check: $M_u^* = {Mu_star:.2f}\,\text{{ kNm}}$ "
                    rf"vs. $\phi M_{{u,cap}} = {phi_Mu_cap:.2f}\,\text{{ kNm}}$ "
                    rf"and $(M_{{uo}})_{{min}} \approx {Mu_min:.2f}\,\text{{ kNm}}$."
                )

            with col4_fig:
                fig_uls_sb_z = _make_uls_stress_block_figure(
                    c, d, gamma_sb, fsy, show_lever_arm=True
                )
                st.pyplot(fig_uls_sb_z, use_container_width=True)
                plt.close(fig_uls_sb_z)

        else:
            st.info("Capacity cannot be evaluated – check geometry / reo inputs.")

    # ----- SLS detailed tab (unchanged) -----
    with tab_sls:
        st.subheader("SLS Bending – Cracked Section (Teaching Model)")
        # ... keep your existing SLS code here ...


    # ----- SLS detailed tab -----
    with tab_sls:
        st.subheader("SLS Bending – Cracked Section (Teaching Model)")

        if d and Ast and Ec and Es and b and D:
            Ms = Mu_star
            st.markdown(f"Using service moment **Ms = Mu* = {Ms:.1f} kNm**.")

            n_sls = Es / Ec if Ec else 0.0
            st.markdown(
                f"**1. Modular ratio:**  n = Es / Ec = {Es:.0f} / {Ec:.0f} = {n_sls:.2f}"
            )

            st.markdown("**2. Neutral axis depth dₙ** (from equilibrium of areas):")
            st.latex(r"\frac{b d_n^2}{2} = n A_s (d - d_n)")
            a_quad = 0.5 * b
            b_coef = n_sls * Ast
            c_coef = -n_sls * Ast * d
            dn = float("nan")
            if a_quad != 0:
                disc = b_coef**2 - 4 * a_quad * c_coef
                if disc >= 0:
                    roots = [
                        (-b_coef + math.sqrt(disc)) / (2 * a_quad),
                        (-b_coef - math.sqrt(disc)) / (2 * a_quad),
                    ]
                    roots = [r for r in roots if 0 < r < D]
                    if roots:
                        dn = min(roots, key=lambda x: abs(x - d / 2))
            if math.isnan(dn):
                dn = D / 3.0

            st.markdown(f"Computed **dₙ = {dn:.2f} mm**.")

            st.markdown("**3. Cracked moment of inertia I_cr**:")
            st.latex(r"I_{cr} = \tfrac13 b d_n^3 + n A_s (d - d_n)^2")
            Icr = b * dn**3 / 3.0 + n_sls * Ast * (d - dn) ** 2
            st.markdown(f"I_cr = {Icr:,.2f} mm⁴")

            st.markdown("**4. Curvature κ at service moment**:")
            st.latex(r"\kappa = M_s / (E_c I_{cr})")
            Ms_Nmm = Ms * 1e6
            kappa = Ms_Nmm / (Ec * Icr) if Ec and Icr else 0.0
            st.markdown(f"κ = {kappa:.3e} mm⁻¹")

            st.markdown("**5. Strain distribution ε(y) = κ (y − dₙ)**:")
            layers = [
                ("Top fibre", 0.0),
                ("Tension steel (d)", d),
                ("Bottom fibre", D),
            ]
            strain_rows = []
            for name, yi in layers:
                eps = kappa * (yi - dn)
                strain_rows.append(
                    {"Layer": name, "Depth y (mm)": yi, "ε": eps}
                )
            st.table(pd.DataFrame(strain_rows))

            fig_eps, ax_eps = plt.subplots()
            ys = [0.0, dn, D]
            eps_vals = [kappa * (y - dn) for y in ys]
            ax_eps.plot(eps_vals, ys, marker="o")
            ax_eps.axhline(dn, linestyle="--", linewidth=0.8)
            ax_eps.set_xlabel("Strain ε")
            ax_eps.set_ylabel("Depth from top (mm)")
            ax_eps.set_title("SLS strain distribution")
            ax_eps.invert_yaxis()
            st.pyplot(fig_eps, use_container_width=True)
            plt.close(fig_eps)
        else:
            st.info("Not enough information to run SLS cracked-section example.")

    # Optional debug
    with st.expander("Debug: raw session_state (optional)"):
        st.write(dict(st.session_state))


if __name__ == "__main__":
    render_bending()


