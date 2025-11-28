# ============================
# PART 1 — IMPORTS + HELPERS + BENDING CAPACITY
# ============================

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
from widgets_helpers import (
    apply_global_widget_css,
    apply_calcbox_css,
    number_row,
    calcbox,
)


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
#  BAR LAYOUT HELPER (used by several figures)
# ------------------------------------------------------------
def _layout_bars_in_rows(n_bars, b, cover, db, min_spacing, n_rows_max=2):
    """
    Lay out bars in 1–2 rows and return a list of (x_rel, row_index).
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
            # Simple 2-row layout
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

    # Horizontal layout (bars per row)
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

    # Vertical layout (row spacing)
    row_pitch_bot = db_bot + rowgap_bot

    y_positions = []
    for _, row_idx in layout:
        y_positions.append(d_row0 - row_idx * row_pitch_bot)

    if not y_positions:
        return d_row0

    return sum(y_positions) / len(y_positions)


# ------------------------------------------------------------
#  BENDING CAPACITY CALC (α2–γ stress block, AS3600 Cl. 8.1.3)
# ------------------------------------------------------------
def _compute_bending_capacity():
    """
    Compute a simple φMu,cap using a rectangular stress block.

    IMPORTANT:
      • d is depth to CENTROID of tensile reo
      • fctf, Mcr and As_min follow AS 3600-style expressions
    """
    # Shared parameters
    b = get_param("b")
    D = get_param("D")
    fc = get_param("fc")
    fsy = get_param("fsy")
    Ast = get_param("Ast_bot")
    Mu_star = get_param("Mu_star")

    phi = get_param("phi_bend", 0.85)

    # Effective depth
    d_centroid = _effective_depth_centroid()
    d_input = get_param("d")
    d = d_centroid if d_centroid not in (None, 0) else d_input

    # Missing-info fallback
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

    # Concrete flexural tensile strength (AS 3600-style)
    # f_ctf ≈ 0.6 * sqrt(fc)  [MPa] for normal-weight concrete
    fctf = 0.6 * math.sqrt(fc)

    # Gross section properties and cracking moment
    I_gross = b * D**3 / 12.0
    Z_gross = b * D**2 / 6.0
    Mcr = fctf * Z_gross / 1e6  # kNm

    # ---- As_min per AS 3600-style expression ----
    # As_min = 0.4 * fctf * b * d / fsy
    As_min = float("nan")
    if (
        d not in (None, 0)
        and fsy not in (None, 0)
        and b not in (None, 0)
        and fctf not in (None, 0)
    ):
        As_min = 0.4 * fctf * b * d / fsy

    # Stress-block factors
    alpha2_raw = 0.85 - 0.0015 * fc
    gamma_raw = 0.97 - 0.0025 * fc
    alpha2 = max(0.67, alpha2_raw)
    gamma = max(0.67, gamma_raw)

    # Flexural capacity
    T = Ast * fsy
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

    c = T / denom
    a = gamma * c
    z = d - 0.5 * a
    Mu_nom = T * z / 1e6
    phi_Mu_cap = phi * Mu_nom
    Mu_util = Mu_star / phi_Mu_cap if phi_Mu_cap > 0 else float("inf")
    ku = c / d if d not in (None, 0) else float("nan")

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

    # Concrete flexural tensile strength (AS 3600-style)
    # f_ctf ≈ 0.6 * sqrt(fc)  [MPa] for normal-weight concrete
    fctf = 0.6 * math.sqrt(fc)

    # Gross section properties and cracking moment
    I_gross = b * D**3 / 12.0
    Z_gross = b * D**2 / 6.0
    Mcr = fctf * Z_gross / 1e6  # kNm

    # ---- As_min per AS 3600-style expression ----
    # As_min = 0.4 * fctf * b * d / fsy
    As_min = float("nan")
    if (
        d not in (None, 0)
        and fsy not in (None, 0)
        and b not in (None, 0)
        and fctf not in (None, 0)
    ):
        As_min = 0.4 * fctf * b * d / fsy

    # Stress-block factors
    alpha2_raw = 0.85 - 0.0015 * fc
    gamma_raw = 0.97 - 0.0025 * fc
    alpha2 = max(0.67, alpha2_raw)
    gamma = max(0.67, gamma_raw)

    # Flexural capacity
    T = Ast * fsy
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

    c = T / denom
    a = gamma * c
    z = d - 0.5 * a
    Mu_nom = T * z / 1e6
    phi_Mu_cap = phi * Mu_nom
    Mu_util = Mu_star / phi_Mu_cap if phi_Mu_cap > 0 else float("inf")
    ku = c / d if d not in (None, 0) else float("nan")

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


    c = T / denom
    a = gamma * c
    z = d - 0.5 * a
    Mu_nom = T * z / 1e6
    phi_Mu_cap = phi * Mu_nom
    Mu_util = Mu_star / phi_Mu_cap if phi_Mu_cap > 0 else float("inf")
    ku = c / d if d not in (None, 0) else float("nan")

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

# ===== END PART 1 =====


# ============================
# PART 2 — STRESS–STRAIN STATE + MAIN 3-PANEL FIGURE
# ============================

def _stress_strain_state(state: str):
    """
    Compute neutral axis and strain/stress info for the demo diagram.
    Uses real shared parameters where possible, but returns a complete
    dict with geometry and materials so the plotting helper doesn't
    need to call get_param again.

    NOTE: d here is the depth to the CENTROID of the bottom tensile
    reinforcement, consistent with the capacity calculation.
    """
    # Try to use real values from the app; fall back to teaching defaults
    b = get_param("b") or 300.0
    D = get_param("D") or 600.0
    fc = get_param("fc")
    fsy = get_param("fsy")
    As = get_param("Ast_bot")
    Ec = get_param("Ec")
    Es = get_param("Es")

    # Fallbacks if missing / zero
    if fc is None:
        fc = 32.0
    if fsy is None or fsy == 0:
        fsy = 500.0
    if Ec is None or Ec == 0:
        Ec = 4700 * math.sqrt(fc)
    if Es is None or Es == 0:
        Es = 200000.0

    # Effective depth to centroid of bottom steel
    d = _effective_depth_centroid()
    if d in (None, 0):
        cover_bot = get_param("cover_bot") or 40.0
        db_bot = get_param("db_bot") or 24.0
        d = D - cover_bot - db_bot / 2.0

    # If As missing or zero, estimate from nb_bot & db_bot
    if As is None or As == 0:
        nb_bot = get_param("nb_bot") or 3
        db_bot = get_param("db_bot") or 24.0
        As = nb_bot * math.pi * db_bot**2 / 4.0

    # AS3600 α2–γ
    alpha2_raw = 0.85 - 0.0015 * fc
    gamma_raw = 0.97 - 0.0025 * fc
    alpha2 = max(0.67, alpha2_raw)
    gamma = max(0.67, gamma_raw)

    # Default strains
    eps_cu_uls = 0.003
    eps_c_sls = 0.0008
    eps_ext_unc = 0.0002

    # ----- ULS state -----
    if state == "ULS":
        denom = alpha2 * fc * b * gamma
        if denom > 0:
            c = As * fsy / denom
        else:
            c = D / 2.0

        c = min(max(c, 1.0), D - 1.0)

        eps_c = -eps_cu_uls
        eps_s = -eps_c * (d - c) / c
        fs_t = fsy  # tension steel at approx. yield

        return dict(
            b=b, D=D, d=d, c=c,
            eps_c=eps_c, eps_s=eps_s,
            gamma=gamma, fs_t=fs_t,
            fc=fc, fsy=fsy, alpha2=alpha2,
        )

    # ----- SLS cracked state -----
    if state == "SLS (cracked)":
        n = Es / Ec if Ec not in (None, 0) else 0.0

        if n == 0.0 or As in (None, 0) or b in (None, 0):
            c = D / 2.0
        else:
            a_quad = 0.5 * b
            b_coef = n * As
            c_coef = -n * As * d

            if a_quad == 0:
                c = D / 2.0
            else:
                discr = b_coef ** 2 - 4 * a_quad * c_coef
                if discr < 0:
                    c = D / 2.0
                else:
                    r1 = (-b_coef + math.sqrt(discr)) / (2 * a_quad)
                    r2 = (-b_coef - math.sqrt(discr)) / (2 * a_quad)
                    cands = [r for r in (r1, r2) if 0 < r < D]
                    c = cands[0] if cands else D / 2.0

        c = min(max(c, 1.0), D - 1.0)

        eps_c = -eps_c_sls
        eps_s = -eps_c * (d - c) / c
        fs_t = Es * eps_s

        return dict(
            b=b, D=D, d=d, c=c,
            eps_c=eps_c, eps_s=eps_s,
            gamma=gamma, fs_t=fs_t,
            fc=fc, fsy=fsy, alpha2=alpha2,
        )

    # ----- Uncracked state -----
    c = D / 2.0
    eps_c = -eps_ext_unc
    eps_s = eps_ext_unc * (d - c) / c
    fs_t = Ec * abs(eps_s)

    return dict(
        b=b, D=D, d=d, c=c,
        eps_c=eps_c, eps_s=eps_s,
        gamma=1.0, fs_t=fs_t,
        fc=fc, fsy=fsy, alpha2=alpha2,
    )


def _plot_stress_strain_profiles(state_dict, state_label=None):
    """
    Single-axis figure with three panels laid out in X:

        - Section view (left)
        - Strain profile (centre)
        - Stress-block / steel stress profile (right)

    All three share the same vertical (depth) axis so that the
    geometry remains to scale.
    """
    # --- work out state label if not explicitly passed ---
    if state_label is None:
        try:
            state_label = st.session_state.get("bending_strain_state_local", "ULS")
        except Exception:
            state_label = "ULS"

    # --- unpack state ---
    b = state_dict["b"]
    D = state_dict["D"]
    d = state_dict["d"]
    c = state_dict["c"]
    eps_c = state_dict["eps_c"]
    eps_s = state_dict["eps_s"]
    gamma = state_dict["gamma"]
    fs_t = state_dict["fs_t"]
    fc = state_dict["fc"]
    alpha2 = state_dict["alpha2"]

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

    # scaling
    eps_max = max(abs(eps_c), abs(eps_s), 1e-4) * 1.3
    sigma_c = alpha2 * fc
    sigma_s = abs(fs_t)
    stress_max = max(sigma_c, sigma_s, 1.0)

    # ----------------- layout in X -----------------
    gap = 220.0

    x0_sec = 0.0
    x1_sec = x0_sec + b + 200.0

    panel_w_strain = 200.0
    x0_strain = x1_sec + gap
    x1_strain = x0_strain + panel_w_strain
    x_mid_strain = (x0_strain + x1_strain) / 2.0

    panel_w_stress = 260.0
    x0_stress = x1_strain + gap
    x1_stress = x0_stress + panel_w_stress

    total_x_max = x1_stress + 40.0

    def strain_to_x(eps):
        half_w = panel_w_strain * 0.4
        return x_mid_strain + (eps / eps_max) * half_w

    def stress_to_x(sig):
        return x0_stress + (sig / stress_max) * (panel_w_stress * 0.8)

    fig, ax = plt.subplots(figsize=(9, 3.5))

    # depth scale (to scale but no ticks)
    ax.set_ylim(D * 1.2, -0.2 * D)
    ax.set_xlim(0, total_x_max)
    ax.set_aspect("equal", adjustable="box")

    # remove ticks / axis markings
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["bottom"].set_visible(False)
    ax.spines["left"].set_visible(False)
    ax.tick_params(left=False, labelleft=False, bottom=False, labelbottom=False)

    # =====================================================
    # 1) SECTION PANEL
    # =====================================================
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

    # d arrow
    if d:
        x_d = x0_sec + b + 30
        ax.annotate(
            "",
            xy=(x_d, d),
            xytext=(x_d, 0),
            arrowprops=dict(arrowstyle="<->", linewidth=1.0),
        )
        ax.text(x_d + 10, d / 2, f"d = {d:.0f} mm", fontsize=6, va="center")

    # NA arrow
    if c:
        x_na = x0_sec + b + 80
        ax.annotate(
            "",
            xy=(x_na, c),
            xytext=(x_na, 0),
            arrowprops=dict(arrowstyle="<->", linewidth=1.0, color="tab:red"),
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
        x0_sec + b / 2,
        D + 0.14 * D,
        sec_title,
        ha="center",
        va="bottom",
        fontsize=10,
    )

    # =====================================================
    # 2) STRAIN PANEL
    # =====================================================
    ax.plot([x_mid_strain, x_mid_strain], [0, D], color="black", linewidth=1)

    y_vals = np.array([0, c, d])
    eps_vals = np.array([eps_c, 0, eps_s])
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
        x_mid_strain,
        D + 0.14 * D,
        "Strain",
        ha="center",
        va="bottom",
        fontsize=9,
    )

    # =====================================================
    # 3) STRESS PANEL
    # =====================================================
    ax.plot([x0_stress, x0_stress], [0, D], color="black", linewidth=1)

    x_T = stress_to_x(sigma_s)
    ax.annotate(
        "",
        xy=(x_T, d),
        xytext=(x0_stress, d),
        arrowprops=dict(arrowstyle="->", linewidth=1.4, color="tab:blue"),
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

    sigma_c = alpha2 * fc

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
        arrowprops=dict(arrowstyle="<->", linewidth=1.2, color="tab:red"),
    )
    ax.text(
        (x0_stress + x_block_right) / 2,
        y_alpha - 0.04 * D,
        rf"$\alpha_2 f'_c = {sigma_c:.0f}\ \mathrm{{MPa}}$",
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
        arrowprops=dict(arrowstyle="<->", color="tab:red"),
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

    # internal compression arrows
    for frac in [0.25, 0.5, 0.75]:
        y_mid = block_top + frac * (block_bottom - block_top)
        ax.annotate(
            "",
            xy=(x0_stress + 0.15 * block_width, y_mid),
            xytext=(x_block_right - 0.15 * block_width, y_mid),
            arrowprops=dict(arrowstyle="<-", color="tab:red", linewidth=0.9),
        )

    ax.text(
        (x0_stress + x1_stress) / 2,
        D + 0.14 * D,
        "Stress (MPa)",
        ha="center",
        va="bottom",
        fontsize=9,
    )

    return fig

# ===== END PART 2 =====


# ============================
# PART 3 — WARNER-STYLE ULS STRESS-BLOCK FIGURE
# ============================

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
    Warner-style ULS stress block (right-way up):

    • Vertical 'Stress (MPa)' axis on the left
    • Rectangular compression block from TOP fibre (0 mm) down to a = γ d_n
    • Dashed line at neutral axis depth d_n (below the block)
    • LEFT-pointing compression arrows inside the block
    • Bottom tension arrow T (fsy) at depth d
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

       # compression arrows (RIGHT pointing towards the block)
    block_h = block_bottom - block_top
    if block_h > 0:
        ys = np.linspace(block_top + 0.2 * block_h,
                         block_bottom - 0.2 * block_h, 3)
        for yy in ys:
            ax.annotate(
                "",
                xy=(block_left + block_width - 2.0, yy),   # arrow head at right
                xytext=(block_left + 2.0, yy),
                arrowprops=dict(
                    arrowstyle="->",
                    color="tab:red",
                    linewidth=1.6,
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
        arrowprops=dict(arrowstyle="->", linewidth=2.0, color="tab:blue"),
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
            arrowprops=dict(arrowstyle="<->", linewidth=1.6),
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

# ===== END PART 3 =====


# ============================
# PART 4 — PAGE RENDER (FULL render_bending FUNCTION)
# ============================

def render_bending():
    st.title("Bending Capacity")

    sync_callbacks = get_sync_callbacks()
    apply_global_widget_css()
    apply_calcbox_css()

    # ============================================================
    #  SIDEBAR GLOSSARY (BENDING TERMS)
    # ============================================================
    with st.sidebar.expander("📘 Glossary – Bending terms", expanded=False):
        st.markdown(
            """
            **Mu*** – Factored design bending moment at the critical section (kNm).  
            **b** – Beam/web width (mm).  
            **D** – Overall section depth (mm).  
            **d** – Effective depth to **centroid of tension steel** (mm).  
            **Ast,bot** – Area of bottom (tension) reinforcement (mm²).  
            **As_min** – Minimum required tensile steel for ductile behaviour.  
            **f'c** – Concrete cylinder strength (MPa).  
            **fsy** – Steel yield strength (MPa).  
            **Ec, Es** – Elastic moduli of concrete and steel (MPa).  

            **c** – Neutral axis depth from the top fibre (mm).  
            **a = γc** – Equivalent rectangular stress block depth (mm).  
            **kᵤ = c/d** – Neutral axis depth ratio (ductility indicator).  
            **α₂, γ** – AS 3600-style stress block factors.  
            **ϕ** – Strength reduction factor for bending.  

            **M_cr** – Cracking moment (kNm) based on f_ct,f and gross section.  
            **M_u** – Nominal flexural capacity (kNm).  
            **ϕM_u,cap** – Design flexural capacity (kNm).  
            **Utilisation** – M_u* / ϕM_u,cap → should be ≤ 1.0.  
            """
        )

    # ============================================================
    #  TOP RESULT SUMMARY
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
    c = top_results["c"]
    a = top_results["a"]
    z = top_results["z"]
    ku = top_results["ku"]
    alpha2 = top_results["alpha2"]
    gamma = top_results["gamma"]
    phi = top_results["phi"]
    fctf = top_results["fctf"]
    Z_gross = top_results["Z_gross"]
    Mcr = top_results["Mcr"]
    As_min = top_results["As_min"]
    d = top_results["d"]

    # Shared values for reporting / diagrams
    b = get_param("b")
    D = get_param("D")
    fc = get_param("fc")
    fsy = get_param("fsy")
    Ec = get_param("Ec")
    Es = get_param("Es")
    Mu_star = get_param("Mu_star")
    nb_bot = get_param("nb_bot")
    db_bot = get_param("db_bot")
    cover_bot = get_param("cover_bot")
    nb_top = get_param("nb_top")
    db_top = get_param("db_top")
    cover_top = get_param("cover_top")

    # Local copies for table
    fc_local = fc if fc is not None else 40.0
    cover_bot_local = cover_bot if cover_bot is not None else 40.0
    db_bot_local = db_bot if db_bot is not None else 20.0
    nb_bot_local = int(nb_bot) if nb_bot is not None else 4
    D_local = D if D is not None else 600.0

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
    #  DESIGN ACTIONS
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
    #  MAIN INPUTS
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
                "Vertical clear gap between bottom bar rows (if 2 rows are used). "
                "This affects the centroid depth d of the tensile reinforcement."
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
    #  DETAILED SUMMARY TABLE + MAIN 3-PANEL FIGURE
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

            # ----------------------------------------------------
            # 1. ULTIMATE LIMIT STATE (ULS)
            # ----------------------------------------------------
            st.header("1. Ultimate Limit State (ULS)")

            alpha2_raw_uls = 0.85 - 0.0015 * fc
            gamma_raw_uls = 0.97 - 0.0025 * fc
            alpha2_uls = max(0.67, alpha2_raw_uls)
            gamma_uls = max(0.67, gamma_raw_uls)

            # 1.1 Stress-block parameters
            st.subheader("1.1 Stress-block parameters (α₂ and γ)")
            calcbox(
                rf"""
From AS 3600 rectangular stress block:

$$
\alpha_2 = 0.85 - 0.0015 f'_c \;(\ge 0.67)
$$

Substituting:

$$
\alpha_2 = 0.85 - 0.0015 \times {fc:.1f}
         = {alpha2_raw_uls:.3f}
         \Rightarrow \alpha_2 = {alpha2_uls:.3f}
$$

Similarly,

$$
\gamma = 0.97 - 0.0025 f'_c \;(\ge 0.67)
$$

$$
\gamma = 0.97 - 0.0025 \times {fc:.1f}
       = {gamma_raw_uls:.3f}
       \Rightarrow \gamma = {gamma_uls:.3f}
$$
"""
            )
            st.markdown("---")

            # 1.2 Steel force
            st.subheader("1.2 Steel force in tension")

            T = Ast * fsy
            calcbox(
                rf"""
Assuming the tension steel yields:

$$
T = A_{st} f_{sy}
$$

Substituting:

$$
T = {Ast:.1f} \times {fsy:.1f}
  = {T:,.0f}\ \text{{N}}
$$
"""
            )
            st.markdown("---")

            # 1.3 Neutral axis depth
            st.subheader("1.3 Neutral axis depth $d_n$")

            denom = alpha2_uls * fc * b * gamma_uls
            dn = T / denom if denom > 0 else float("nan")
            a_uls = gamma_uls * dn
            z_uls = d - 0.5 * a_uls
            Mu_nom_uls = T * z_uls / 1e6
            phi_Mu_cap_uls = phi * Mu_nom_uls

            calcbox(
                rf"""
Equilibrium of internal forces:

$$
\alpha_2 f'_c\, b\, \gamma d_n = T
$$

So:

$$
d_n = \frac{T}{\alpha_2 f'_c\, b\, \gamma}
$$

Substituting:

$$
d_n =
\frac{{{T:,.0f}}}
     {{ {alpha2_uls:.3f} \times {fc:.1f} \times {b:.1f} \times {gamma_uls:.3f} }}
= {dn:.1f}\ \text{{mm}}
$$
"""
            )
            st.markdown("---")

            # 1.4 Block depth, lever arm, capacity
            st.subheader("1.4 Block depth, lever arm, and moment capacity")

            calcbox(
                rf"""
Block depth:

$$
a = \gamma d_n = {gamma_uls:.3f} \times {dn:.1f}
  = {a_uls:.1f}\ \text{{mm}}
$$

Lever arm:

$$
z = d - \frac{a}{2}
$$

$$
z = {d:.1f} - \frac{{{a_uls:.1f}}}{2}
  = {z_uls:.1f}\ \text{{mm}}
$$

Nominal moment:

$$
M_u = \frac{T z}{10^6}
$$

$$
M_u = \frac{{{T:,.0f} \times {z_uls:.1f}}}{10^6}
    = {Mu_nom_uls:.2f}\ \text{{kNm}}
$$

Design moment:

$$
\phi M_{u,cap} = \phi M_u
               = {phi:.2f} \times {Mu_nom_uls:.2f}
               = {phi_Mu_cap_uls:.2f}\ \text{{kNm}}
$$
"""
            )
            st.markdown("---")

            # ----------------------------------------------------
            # 2. MINIMUM STRENGTH REQUIREMENTS (AS 3600)
            # ----------------------------------------------------
            st.header("2. Minimum strength requirements (AS 3600)")

            fctf_as = fctf
            Zg = Z_gross
            Mcr_as = Mcr
            Mu_min_as = (
                1.2 * Mcr_as
                if Mcr_as is not None and not math.isnan(Mcr_as)
                else float("nan")
            )
            Ast_min_as = As_min

            # 2.1 f_ct,f
            st.subheader("2.1 Concrete flexural tensile strength $f_{ct,f}$")
            calcbox(
                rf"""
AS 3600-style expression for flexural tensile strength:

$$
f_{ct,f} \approx 0.6 \sqrt{{f'_c}}
$$

Substituting:

$$
f_{ct,f} \approx 0.6 \sqrt{{{fc:.1f}}}
          = {fctf_as:.3f}\ \text{{MPa}}
$$
"""
            )
            st.markdown("---")

            # 2.2 Z_g
            st.subheader("2.2 Gross section modulus $Z_g$")
            calcbox(
                rf"""
Gross section modulus:

$$
Z_g = \frac{{b D^2}}{6}
$$

Substituting:

$$
Z_g = \frac{{{b:.1f} \times {D:.1f}^2}}{6}
    = {Zg:,.3e}\ \text{{mm}}^3
$$
"""
            )
            st.markdown("---")

            # 2.3 M_cr
            st.subheader("2.3 Cracking moment $M_{cr}$")
            calcbox(
                rf"""
Cracking moment:

$$
M_{cr} = \frac{{f_{ct,f} Z_g}}{{10^6}}
$$

Substituting:

$$
M_{cr} = \frac{{{fctf_as:.3f} \times {Zg:,.3e}}}{{10^6}}
       = {Mcr_as:.2f}\ \text{{kNm}}
$$
"""
            )
            st.markdown("---")

            # 2.4 Minimum required capacity (1.2 Mcr)
            st.subheader("2.4 Minimum required design capacity $(M_{u,cap})_{min}$")
            calcbox(
                rf"""
To ensure post-cracking behaviour:

$$
(M_{u,cap})_{min} = 1.2\, M_{cr}
$$

Substituting:

$$
(M_{u,cap})_{min}
= 1.2 \times {Mcr_as:.2f}
= {Mu_min_as:.2f}\ \text{{kNm}}
$$

Meaning the design ultimate strength must exceed
**1.2 × cracking moment**.
"""
            )
            st.markdown("---")

            # 2.5 Minimum tensile reinforcement
            st.subheader("2.5 Minimum tensile reinforcement $A_{st,min}$")
            calcbox(
                rf"""
AS 3600-style minimum tensile reinforcement:

$$
A_{st,min}
= 0.4\;\frac{{f_{ct,f}}}{{f_{sy}}}\; b d
$$

Substituting:

$$
A_{st,min}
= 0.4 \times \frac{{{fctf_as:.3f}}}{{{fsy:.1f}}}
\times {b:.1f} \times {d:.1f}
= {Ast_min_as:.1f}\ \text{{mm}}^2
$$

Compare:

$$
A_{st} = {Ast:.1f}\ \text{{mm}}^2
\qquad\text{vs.}\qquad
A_{st,min} = {Ast_min_as:.1f}\ \text{{mm}}^2
$$
"""
            )
            st.markdown("---")

        else:
            st.info("Capacity cannot be evaluated – check geometry / reo inputs.")
  

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
            dn_sls = float("nan")
            if a_quad != 0:
                disc = b_coef**2 - 4 * a_quad * c_coef
                if disc >= 0:
                    roots = [
                        (-b_coef + math.sqrt(disc)) / (2 * a_quad),
                        (-b_coef - math.sqrt(disc)) / (2 * a_quad),
                    ]
                    roots = [r for r in roots if 0 < r < D]
                    if roots:
                        dn_sls = min(roots, key=lambda x: abs(x - d / 2))
            if math.isnan(dn_sls):
                dn_sls = D / 3.0

            st.markdown(f"Computed **dₙ = {dn_sls:.2f} mm**.")

            st.markdown("**3. Cracked moment of inertia I_cr**:")
            st.latex(r"I_{cr} = \tfrac13 b d_n^3 + n A_s (d - d_n)^2")
            Icr = b * dn_sls**3 / 3.0 + n_sls * Ast * (d - dn_sls) ** 2
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
                eps = kappa * (yi - dn_sls)
                strain_rows.append(
                    {"Layer": name, "Depth y (mm)": yi, "ε": eps}
                )
            st.table(pd.DataFrame(strain_rows))

            fig_eps, ax_eps = plt.subplots()
            ys = [0.0, dn_sls, D]
            eps_vals = [kappa * (y - dn_sls) for y in ys]
            ax_eps.plot(eps_vals, ys, marker="o")
            ax_eps.axhline(dn_sls, linestyle="--", linewidth=0.8)
            ax_eps.set_xlabel("Strain ε")
            ax_eps.set_ylabel("Depth from top (mm)")
            ax_eps.set_title("SLS strain distribution")
            ax_eps.invert_yaxis()
            st.pyplot(fig_eps, use_container_width=True)
            plt.close(fig_eps)
        else:
            st.info("Not enough information to run SLS cracked-section example.")

# ===== END PART 4 =====


# ============================
# PART 5 — MAIN GUARD
# ============================

if __name__ == "__main__":
    render_bending()

# ===== END PART 5 =====
















