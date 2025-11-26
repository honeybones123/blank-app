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
#  Helper – bottom tensile centroid depth
# ------------------------------------------------------------
def _effective_depth_centroid():
    """
    Return effective depth d to the CENTROID of bottom tensile reinforcement.

    Uses:
        b, D, nb_bot, db_bot, cover_bot, rowgap_bot

    If anything essential is missing, returns None and the caller can fall back.
    """
    b = get_param("b")
    D = get_param("D")
    nb_bot = get_param("nb_bot")
    db_bot = get_param("db_bot")
    cover_bot = get_param("cover_bot")
    rowgap_bot = get_param("rowgap_bot")

    if b in (None, 0) or D in (None, 0) or nb_bot in (None, 0) or db_bot in (None, 0) or cover_bot in (None, 0):
        return None

    nb_bot = int(nb_bot)
    db_bot = float(db_bot)
    cover_bot = float(cover_bot)
    rowgap_bot = float(rowgap_bot) if rowgap_bot not in (None, 0) else 0.0

    # Bottom row depth (to bar centre) from top fibre
    d_row0 = D - cover_bot - db_bot / 2.0

    # Horizontal layout (how many bars per row)
    min_spacing_bot = 2.0 * db_bot
    layout = _layout_bars_in_rows(
        n_bars=nb_bot,
        b=b,
        cover=cover_bot,
        db=db_bot,
        min_spacing=min_spacing_bot,
        n_rows_max=2,
    )

    if not layout:
        return d_row0

    # Vertical layout: second row sits above first by db + rowgap_bot
    row_pitch_bot = db_bot + rowgap_bot

    y_positions = []
    for _, row_idx in layout:
        y = d_row0 - row_idx * row_pitch_bot
        y_positions.append(y)

    if not y_positions:
        return d_row0

    d_centroid = sum(y_positions) / len(y_positions)
    return d_centroid


# ------------------------------------------------------------
#  BENDING CAPACITY CALC (α2–γ stress block, AS3600 Cl. 8.1.3)
# ------------------------------------------------------------
def _compute_bending_capacity():
    """
    Compute a simple φMu,cap using a rectangular stress block.
    Uses shared session_state values only (via get_param).
    Also returns intermediate values for the step-by-step report.

    IMPORTANT: d is taken as the depth to the CENTROID of the bottom
    tensile reinforcement (using _effective_depth_centroid()).
    """
    # Shared parameters (all from session state)
    b = get_param("b")
    D = get_param("D")
    fc = get_param("fc")
    fsy = get_param("fsy")
    Ast = get_param("Ast_bot")
    Mu_star = get_param("Mu_star")

    # Strength reduction factor from shared state (e.g. Inputs page)
    phi = get_param("phi_bend", 0.85)

    # Effective depth – FIRST choice is centroid of tensile reo
    d_centroid = _effective_depth_centroid()
    d_input = get_param("d")
    d = d_centroid if d_centroid not in (None, 0) else d_input

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
            "d": d,
        }

    # ---- Concrete in tension (for min steel & Mcr) ----
    cb = 0.2
    fc = float(fc)
    fsy = float(fsy)
    fctf = cb * (fc ** (2.0 / 3.0))          # MPa
    I_gross = b * D**3 / 12.0               # mm^4
    Z_gross = b * D**2 / 6.0                # mm^3
    Mcr = fctf * Z_gross / 1e6              # kNm

    # ---- Minimum tensile reinforcement ----
    kAst = 1.0
    As_min = kAst * (d / D) ** 2 * (fctf / fsy) * b * D

    # ---- Stress-block factors (from AS3600-style formulas) ----
    alpha2_raw = 0.85 - 0.0015 * fc
    gamma_raw = 0.97 - 0.0025 * fc
    alpha2 = max(0.67, alpha2_raw)
    gamma = max(0.67, gamma_raw)

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
            "d": d,
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
        "d": d,
    }


# ------------------------------------------------------------
#  DIAGRAM HELPERS (cross-section + schematic stress block)
# ------------------------------------------------------------
def _plot_stress_strain_profiles(state_dict):
    """
    Single-axis figure with three panels laid out in X:

        - Section (ULS view)      – left
        - Strain profile          – centre
        - Stress-block profile    – right

    Uses real geometry / reo from the main app so it updates with inputs.
    d in the state_dict is the depth to the CENTROID of bottom steel.
    """
    # --- unpack state from _stress_strain_state ---
    b = state_dict["b"]
    D = state_dict["D"]
    d = state_dict["d"]          # centroid depth
    c = state_dict["c"]
    eps_c = state_dict["eps_c"]
    eps_s = state_dict["eps_s"]
    gamma = state_dict["gamma"]
    fs_t = state_dict["fs_t"]
    fc = state_dict["fc"]
    alpha2 = state_dict["alpha2"]

    # --- reinforcement & cover from app (with safe fallbacks) ---
    nb_bot = get_param("nb_bot") or 4
    db_bot = get_param("db_bot") or 20.0
    cover_bot = get_param("cover_bot") or 40.0
    nb_top = get_param("nb_top") or 2
    db_top = get_param("db_top") or 16.0
    cover_top = get_param("cover_top") or 40.0
    rowgap_bot = get_param("rowgap_bot") or 25.0
    rowgap_top = get_param("rowgap_top") or 25.0

    nb_bot = int(nb_bot)
    nb_top = int(nb_top)

    # scaling for strain & stress (horizontal only)
    eps_max = max(abs(eps_c), abs(eps_s), 1e-4) * 1.3
    sigma_c = alpha2 * fc           # compression block stress (for label)
    sigma_s = abs(fs_t)             # steel stress (for label & arrow length)
    stress_max = max(sigma_c, sigma_s, 1.0)

    # ----------------- layout in X -----------------
    gap = 150.0

    # section panel (left)
    x0_sec = 0.0
    x1_sec = x0_sec + b + 200.0  # extra for arrows

    # strain panel (centre)
    panel_w_strain = 200.0
    x0_strain = x1_sec + gap
    x1_strain = x0_strain + panel_w_strain
    x_mid_strain = (x0_strain + x1_strain) / 2.0

    # stress panel (right)
    panel_w_stress = 260.0
    x0_stress = x1_strain + gap
    x1_stress = x0_stress + panel_w_stress

    total_x_max = x1_stress + 40.0

    # mapping helpers
    def strain_to_x(eps):
        half_w = panel_w_strain * 0.4
        return x_mid_strain + (eps / eps_max) * half_w

    def stress_to_x(sig):
        return x0_stress + (sig / stress_max) * (panel_w_stress * 0.8)

    fig, ax = plt.subplots(figsize=(9, 3.5))

    # common depth scale
    ax.set_ylim(D, 0)
    ax.set_xlim(0, total_x_max)

    # tidy up axes
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["bottom"].set_visible(False)
    ax.spines["left"].set_visible(False)
    ax.tick_params(left=True, labelleft=True, bottom=False, labelbottom=False)

    # =====================================================
    # 1) CROSS-SECTION (ULS view) – LEFT
    # =====================================================
    # outline
    ax.add_patch(
        Rectangle(
            (x0_sec, 0),
            b,
            D,
            fill=False,
            linewidth=1.5,
            edgecolor="black",
        )
    )

    # compression zone (0 → γc)
    block_depth = max(0.0, min(gamma * c, D))
    ax.add_patch(
        Rectangle(
            (x0_sec, 0),
            b,
            block_depth,
            facecolor="#c7e3ff",
            edgecolor="tab:red",
            linewidth=1.0,
            alpha=0.8,
        )
    )

    # bottom bars (with row wrapping)
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
    row_pitch_bot = db_bot + rowgap_bot
    d_row0 = D - cover_bot - db_bot / 2.0  # depth to first row

    for x_rel, row_idx in bot_layout:
        x = x0_sec + x_rel
        y = d_row0 - row_idx * row_pitch_bot
        ax.add_patch(
            Circle(
                (x, y),
                radius=r_bot,
                facecolor="none",
                edgecolor="tab:blue",
                linewidth=1.3,
            )
        )

    # top bars (with row wrapping)
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
    row_pitch_top = db_top + rowgap_top

    for x_rel, row_idx in top_layout:
        x = x0_sec + x_rel
        y = y_top_base + row_idx * row_pitch_top
        ax.add_patch(
            Circle(
                (x, y),
                radius=r_top,
                facecolor="none",
                edgecolor="tab:red",
                linewidth=1.3,
            )
        )

    # NA arrow & label WITH value (only on section)
    x_na = x0_sec + b + 40.0
    ax.annotate(
        "",
        xy=(x_na, c),
        xytext=(x_na, 0),
        arrowprops=dict(arrowstyle="<->", linewidth=1.0),
    )
    ax.text(
        x_na + 20.0,
        c / 2.0,
        f"NA = {c:.0f} mm",
        va="center",
        fontsize=9,
        color="tab:red",
    )

    # d arrow & label – d is centroid depth
    x_d = x_na + 80.0
    ax.annotate(
        "",
        xy=(x_d, d),
        xytext=(x_d, 0),
        arrowprops=dict(arrowstyle="<->", linewidth=1.0),
    )
    ax.text(
        x_d + 20.0,
        d / 2.0,
        f"d ({d:.0f} mm)",
        va="center",
        fontsize=9,
    )

    # section title
    ax.text(
        x0_sec + b / 2.0,
        -0.13 * D,
        "Section (ULS view)",
        ha="center",
        va="top",
        fontsize=10,
    )

    ax.set_ylabel("Depth (mm)")

    # =====================================================
    # 2) STRAIN PROFILE – MIDDLE
    # =====================================================
    # vertical axis
    ax.plot(
        [x_mid_strain, x_mid_strain],
        [0, D],
        color="black",
        linewidth=1.0,
    )

    # strain line
    y_vals = np.array([0.0, c, d])
    eps_vals = np.array([eps_c, 0.0, eps_s])
    x_vals = [strain_to_x(e) for e in eps_vals]
    ax.plot(x_vals, y_vals, color="black")

    # NA line over strain panel
    ax.hlines(
        c,
        x0_strain - 10.0,
        x1_strain + 10.0,
        colors="black",
        linestyles="--",
        linewidth=0.8,
    )

    # strain labels
    ax.text(
        strain_to_x(eps_c),
        0.0,
        rf"$\varepsilon_c = {eps_c:.4f}$",
        ha="right" if eps_c < 0 else "left",
        va="bottom",
        color="tab:red",
    )
    ax.text(
        strain_to_x(eps_s),
        d,
        rf"$\varepsilon_s = {eps_s:.4f}$",
        ha="left" if eps_s > 0 else "right",
        va="top",
        color="tab:blue",
    )

    ax.text(
        x_mid_strain,
        -0.13 * D,
        "Strain Profile",
        ha="center",
        va="top",
        fontsize=10,
    )
    ax.text(
        x_mid_strain,
        D + 0.14 * D,
        "Strain",
        ha="center",
        va="bottom",
        fontsize=9,
    )

    # =====================================================
    # 3) STRESS-BLOCK PROFILE – RIGHT
    # =====================================================
    # vertical axis
    ax.plot(
        [x0_stress, x0_stress],
        [0, D],
        color="black",
        linewidth=1.0,
    )

    # Steel tension arrow (scaled with σ_s)
    x_T = stress_to_x(sigma_s)
    T_y = d
    ax.annotate(
        "",
        xy=(x_T, T_y),
        xytext=(x0_stress, T_y),
        arrowprops=dict(arrowstyle="->", linewidth=1.4, color="tab:blue"),
    )
    ax.text(
        x_T + 0.02 * panel_w_stress,
        T_y,
        f"T ({sigma_s:.0f} MPa)",
        ha="left",
        va="center",
        color="tab:blue",
    )

    # Compression block width = fixed ratio of steel arrow
    block_ratio = 1.0 / 3.0
    block_width = (x_T - x0_stress) * block_ratio
    x_block_right = x0_stress + block_width

    block_top = 0.0
    block_bottom = gamma * c

    # block outline
    ax.fill_between(
        [x0_stress, x_block_right],
        [block_top, block_top],
        [block_bottom, block_bottom],
        edgecolor="tab:red",
        facecolor="none",
        linewidth=1.5,
    )

    # NA line over stress panel
    ax.hlines(
        c,
        x0_stress - 10.0,
        x1_stress,
        colors="black",
        linestyles="--",
        linewidth=0.8,
    )

    # α2 f'c arrow & label (below arrow)
    y_alpha = c + 0.05 * D
    ax.annotate(
        "",
        xy=(x0_stress, y_alpha),
        xytext=(x_block_right, y_alpha),
        arrowprops=dict(arrowstyle="<->", linewidth=1.2, color="tab:red"),
    )
    ax.text(
        (x0_stress + x_block_right) / 2.0,
        y_alpha + 0.08 * D,
        rf"$\alpha_2 f'_c = {sigma_c:.0f}\ \mathrm{{MPa}}$",
        ha="center",
        va="top",
        color="tab:red",
    )

    # γc arrow + value
    x_gc = x_block_right + 0.12 * panel_w_stress
    ax.annotate(
        "",
        xy=(x_gc, block_bottom),
        xytext=(x_gc, block_top),
        arrowprops=dict(arrowstyle="<->", linewidth=1.2, color="tab:red"),
    )
    val_gammac = gamma * c
    ax.text(
        x_gc + 0.06 * panel_w_stress,
        (block_top + block_bottom) / 2.0,
        rf"$\gamma c = {val_gammac:.0f}\ \mathrm{{mm}}$",
        va="center",
        color="tab:red",
    )

    # internal compression arrows (pointing left)
    for frac in [0.25, 0.5, 0.75]:
        y_mid = block_top + frac * (block_bottom - block_top)
        ax.annotate(
            "",
            xy=(x0_stress + 0.15 * block_width, y_mid),
            xytext=(x_block_right - 0.15 * block_width, y_mid),
            arrowprops=dict(arrowstyle="<-", linewidth=1.0, color="tab:red"),
        )

    ax.text(
        (x0_stress + x1_stress) / 2.0,
        -0.13 * D,
        "Stress-block Profile (AS3600 α₂–γ)",
        ha="center",
        va="top",
        fontsize=10,
    )
    ax.text(
        (x0_stress + x1_stress) / 2.0,
        D + 0.14 * D,
        "Stress (MPa)",
        ha="center",
        va="bottom",
        fontsize=9,
    )

    return fig


# ------------------------------------------------------------
#  STRESS–STRAIN PROFILE HELPERS (AS3600 α2–γ)
# ------------------------------------------------------------
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

    NOTE: for ULS the function reuses the SAME c, d, α2, γ as the
    capacity calc (_compute_bending_capacity), so the diagrams and
    φMu,cap are fully consistent.
    """
    # Try to use real values from the app; fall back to teaching defaults
    b = get_param("b") or 300.0
    D = get_param("D") or 600.0
    fc = get_param("fc")
    fsy = get_param("fsy")
    As = get_param("Ast_bot")
    Ec = get_param("Ec")
    Es = get_param("Es")

    # Fallbacks if missing
    if fc is None:
        fc = 32.0
    if fsy is None:
        fsy = 500.0
    if Ec is None:
        Ec = 4700 * math.sqrt(fc)
    if Es is None:
        Es = 200000.0

    # Effective depth to centroid of bottom steel (base value)
    d_base = _effective_depth_centroid()
    if d_base in (None, 0):
        cover_bot = get_param("cover_bot") or 40.0
        db_bot = get_param("db_bot") or 24.0
        d_base = D - cover_bot - db_bot / 2.0

    # If As missing, estimate from nb_bot & db_bot
    if As is None:
        nb_bot = get_param("nb_bot") or 3
        db_bot = get_param("db_bot") or 24.0
        As = nb_bot * math.pi * db_bot**2 / 4.0

    # Default strains
    eps_cu_uls = 0.003
    eps_c_sls = 0.0008
    eps_ext_unc = 0.0002

    # ----- ULS state: reuse capacity calc -----
    if state == "ULS":
        cap = _compute_bending_capacity()
        c = cap["c"]
        d = cap["d"] if cap["d"] not in (None, 0) else d_base
        gamma = cap["gamma"]
        alpha2 = cap["alpha2"]

        # clamp c for plotting
        c = min(max(c, 1.0), D - 1.0)

        eps_c = -eps_cu_uls
        eps_s = -eps_c * (d - c) / c
        fs_t = fsy  # tension steel assumed at yield

        return dict(
            b=b, D=D, d=d, c=c,
            eps_c=eps_c, eps_s=eps_s,
            gamma=gamma, fs_t=fs_t,
            fc=fc, fsy=fsy, alpha2=alpha2,
        )

    # ----- SLS cracked state -----
    if state == "SLS (cracked)":
        d = d_base
        n = Es / Ec
        # Simple quadratic NA solution (teaching)
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

        # γ here just used for plotting; use 1.0
        gamma = 1.0
        alpha2 = 1.0

        return dict(
            b=b, D=D, d=d, c=c,
            eps_c=eps_c, eps_s=eps_s,
            gamma=gamma, fs_t=fs_t,
            fc=fc, fsy=fsy, alpha2=alpha2,
        )

    # ----- Uncracked state -----
    d = d_base
    c = D / 2.0
    eps_c = -eps_ext_unc
    eps_s = eps_ext_unc * (d - c) / c
    fs_t = Ec * abs(eps_s)

    return dict(
        b=b, D=D, d=d, c=c,
        eps_c=eps_c, eps_s=eps_s,
        gamma=1.0, fs_t=fs_t,
        fc=fc, fsy=fsy, alpha2=1.0,
    )


# ------------------------------------------------------------
#  Simple ULS cross-section figure for step-by-step tabs
# ------------------------------------------------------------
def _make_cross_section_figure(
    b, D, d, a,
    nb_bot, db_bot, cover_bot,
    nb_top=None, db_top=None, cover_top=None,
    c=None, z=None,
    show_compression=True,
    title="ULS cross-section (cracked)",
):
    """
    Step-by-step cross-section diagram.

    Draws only the section and reo – NO outer border/frame – so that
    it visually matches the main ULS section diagram.
    """
    if b is None or D is None:
        return None

    nb_bot = nb_bot or 0
    db_bot = db_bot or 0
    cover_bot = cover_bot or 0
    nb_top = nb_top or 0
    db_top = db_top or 0
    cover_top = cover_top or 0

    # figure
    fig, ax = plt.subplots(figsize=(3, 6))
    ax.set_xlim(0, b)
    ax.set_ylim(D, 0)
    ax.set_aspect("equal")

    # turn off axes box completely
    ax.axis("off")

    # outer concrete section
    ax.add_patch(
        Rectangle(
            (0, 0),
            b,
            D,
            fill=False,
            linewidth=1.5,
            edgecolor="black",
        )
    )

    # compression block at top
    if show_compression and a is not None and c is not None:
        block_depth = max(0.0, min(a, D))
        ax.add_patch(
            Rectangle(
                (0, 0),
                b,
                block_depth,
                facecolor="#c7e3ff",
                edgecolor="tab:red",
                linewidth=1.2,
                alpha=0.8,
            )
        )

        # NA dashed line
        ax.hlines(
            c,
            0,
            b,
            colors="tab:red",
            linestyles="--",
            linewidth=1.0,
        )

    # bottom reo
    if nb_bot > 0 and db_bot > 0:
        r_bot = db_bot / 2.0
        rowgap_bot = get_param("rowgap_bot") or 25.0
        min_spacing_bot = 2.0 * db_bot

        layout_bot = _layout_bars_in_rows(
            n_bars=nb_bot,
            b=b,
            cover=cover_bot,
            db=db_bot,
            min_spacing=min_spacing_bot,
            n_rows_max=2,
        )
        row_pitch_bot = db_bot + rowgap_bot
        d_row0 = D - cover_bot - db_bot / 2.0

        for x_rel, row_idx in layout_bot:
            x = x_rel
            y = d_row0 - row_idx * row_pitch_bot
            ax.add_patch(
                Circle(
                    (x, y),
                    radius=r_bot,
                    facecolor="none",
                    edgecolor="tab:blue",
                    linewidth=1.3,
                )
            )

    # top reo
    if nb_top > 0 and db_top > 0:
        r_top = db_top / 2.0
        rowgap_top = get_param("rowgap_top") or 25.0
        min_spacing_top = 2.0 * db_top

        layout_top = _layout_bars_in_rows(
            n_bars=nb_top,
            b=b,
            cover=cover_top,
            db=db_top,
            min_spacing=min_spacing_top,
            n_rows_max=2,
        )
        y_top_base = cover_top + db_top / 2.0
        row_pitch_top = db_top + rowgap_top

        for x_rel, row_idx in layout_top:
            x = x_rel
            y = y_top_base + row_idx * row_pitch_top
            ax.add_patch(
                Circle(
                    (x, y),
                    radius=r_top,
                    facecolor="none",
                    edgecolor="tab:red",
                    linewidth=1.3,
                )
            )

    # arrows for c and z (optional)
    if c is not None:
        ax.annotate(
            "",
            xy=(b + 10.0, c),
            xytext=(b + 10.0, 0),
            arrowprops=dict(arrowstyle="<->", linewidth=1.0, color="tab:red"),
        )
        ax.text(
            b + 15.0,
            c / 2.0,
            f"c = {c:.0f} mm",
            va="center",
            color="tab:red",
        )

    if z is not None and d is not None:
        ax.annotate(
            "",
            xy=(b + 40.0, d),
            xytext=(b + 40.0, 0),
            arrowprops=dict(arrowstyle="<->", linewidth=1.0),
        )
        ax.text(
            b + 45.0,
            d / 2.0,
            f"z = {z:.0f} mm",
            va="center",
        )

    ax.set_title(title)
    return fig


# ------------------------------------------------------------
#  Simple ULS stress-block figure for step-by-step tabs
# ------------------------------------------------------------
def _make_uls_stress_block_figure(c, d, gamma_sb, fsy, show_lever_arm=False):
    """
    Simple 2D stress-block diagram used in the step-by-step ULS tab.
    """
    if c in (None, 0) or d in (None, 0):
        fig, ax = plt.subplots()
        ax.text(0.5, 0.5, "No data", ha="center")
        ax.axis("off")
        return fig

    fig, ax = plt.subplots(figsize=(3, 6))
    ax.set_ylim(d + 50.0, -50.0)
    ax.set_xlim(0, 1.2)

    ax.axis("off")

    # NA
    ax.hlines(c, 0.0, 1.0, linestyles="--", colors="black", linewidth=1.0)

    # block
    block_top = 0.0
    block_bottom = gamma_sb * c
    ax.fill_between(
        [0.0, 0.5],
        [block_top, block_top],
        [block_bottom, block_bottom],
        facecolor="#c7e3ff",
        edgecolor="tab:red",
        linewidth=1.2,
    )

    # steel force arrow at d
    ax.annotate(
        "",
        xy=(1.0, d),
        xytext=(0.5, d),
        arrowprops=dict(arrowstyle="->", linewidth=1.5, color="tab:blue"),
    )
    ax.text(
        1.02,
        d,
        r"$T = A_{st} f_{sy}$",
        va="center",
        color="tab:blue",
    )

    if show_lever_arm:
        # lever arm z between T and block centroid
        z = d - 0.5 * gamma_sb * c
        ax.annotate(
            "",
            xy=(0.7, d),
            xytext=(0.7, 0.5 * gamma_sb * c),
            arrowprops=dict(arrowstyle="<->", linewidth=1.2),
        )
        ax.text(
            0.72,
            (d + 0.5 * gamma_sb * c) / 2.0,
            "z",
            va="center",
        )

    ax.set_title("ULS stress block")
    return fig


# ------------------------------------------------------------
#  PAGE RENDER
# ------------------------------------------------------------
def render_bending():
    ...
    # (everything from your existing render_bending() function stays
    #  exactly the same as in your last message – no further changes)
    ...
