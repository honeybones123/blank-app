# =====================================================================
#  INTERNAL FUNCTIONS — PART 1
#  (Weighted centroid d, layout, bending capacity, stress-strain state)
# =====================================================================

import math
import numpy as np
from state_and_helpers import get_param, update_results


# ---------------------------------------------------------------------
# 1. BAR LAYOUT (unchanged from your version)
# ---------------------------------------------------------------------
def _layout_bars_in_rows(n_bars, b, cover, db, min_spacing, n_rows_max=2):
    """
    Lay out bars in 1–2 rows and return list of (x_rel, row_idx).
    Same behaviour as your existing layout engine.
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
            # 2-row fallback
            n1 = math.ceil(n_bars / 2)
            n2 = n_bars - n1
            n_per_row = [n1, n2]

    coords = []
    count = 0
    for row_idx, nrow in enumerate(n_per_row):
        if nrow <= 0:
            continue

        if nrow == 1:
            xs = [b / 2.0]
        else:
            inner = max(b - 2 * cover, db)
            spacing = max(inner / (nrow - 1), min_spacing)
            xs = [cover + spacing * i for i in range(nrow)]

        for x in xs:
            coords.append((x, row_idx))
            count += 1
            if count >= n_bars:
                return coords

    return coords


# ---------------------------------------------------------------------
# 2. TRUE WEIGHTED CENTROID OF BOTTOM REINFORCEMENT (OPTION B)
# ---------------------------------------------------------------------
def _compute_d_centroid_weighted():
    """
    Computes *true weighted centroid* depth d for the bottom tensile bars:
        d = Σ(As_i * y_i) / Σ(As_i)

    y_i measured from top fibre.
    """

    # Pull parameters
    D = get_param("D")
    b = get_param("b")
    nb = get_param("nb_bot")
    db = get_param("db_bot")
    cover = get_param("cover_bot")
    rowgap = get_param("rowgap_bot") or 0.0

    # Basic input validation
    if any(v in (None, 0) for v in [D, b, nb, db, cover]):
        return None

    nb = int(nb)
    db = float(db)
    cover = float(cover)
    rowgap = float(rowgap)

    # Layout bars horizontally
    min_spacing = 2.0 * db
    layout = _layout_bars_in_rows(nb, b, cover, db, min_spacing, n_rows_max=2)

    # If layout fails → fallback single-row approximation
    if not layout:
        return D - cover - db / 2.0

    # Now compute centroid
    As_single = math.pi * db**2 / 4.0
    d1 = D - cover - db / 2.0     # depth to row 0
    pitch = db + rowgap           # vertical gap between rows

    As_total = 0.0
    moment_sum = 0.0

    for _, row_idx in layout:
        y = d1 - row_idx * pitch  # mm from top fibre
        As_total += As_single
        moment_sum += As_single * y

    if As_total <= 0:
        return None

    return moment_sum / As_total


# ---------------------------------------------------------------------
# 3. BENDING CAPACITY USING THE NEW CENTROIDAL d
# ---------------------------------------------------------------------
def _compute_bending_capacity():
    """
    Computes φMu,cap with weighted centroid d (consistent everywhere).
    Also produces intermediate results for summaries and diagrams.
    """

    b = get_param("b")
    D = get_param("D")
    fc = get_param("fc")
    fsy = get_param("fsy")
    Ast = get_param("Ast_bot")
    Mu_star = get_param("Mu_star")
    phi = get_param("phi_bend", 0.85)

    # Weighted centroid d
    d = _compute_d_centroid_weighted()

    # Fallback if centroid fails
    if d in (None, 0):
        cover = get_param("cover_bot") or 40.0
        db = get_param("db_bot") or 20.0
        d = (get_param("D") or 0) - cover - db / 2.0

    # Guard against missing inputs
    def bad(v):
        return v is None or v == 0 or (isinstance(v, float) and math.isnan(v))

    if any(bad(v) for v in [b, D, fc, fsy, Ast, d]) or Mu_star is None:
        update_results(phi_Mu_cap=0.0, Mu_utilisation=float("nan"))
        return {
            "phi_Mu_cap": 0.0,
            "Mu_util": float("nan"),
            "c": float("nan"),
            "a": float("nan"),
            "z": float("nan"),
            "ku": float("nan"),
            "d": d,
            "alpha2": 0.85,
            "gamma": 0.85,
            "fctf": float("nan"),
            "I_gross": float("nan"),
            "Z_gross": float("nan"),
            "Mcr": float("nan"),
            "As_min": float("nan"),
            "phi": phi,
        }

    # ------------------------------------------------------------------
    # Section properties for minimum steel and cracking
    # ------------------------------------------------------------------
    cb = 0.2
    fctf = cb * (fc ** (2.0 / 3.0))
    I_gross = b * D**3 / 12.0
    Z_gross = b * D**2 / 6.0
    Mcr = fctf * Z_gross / 1e6

    # Min steel
    As_min = 1.0 * (d / D) ** 2 * (fctf / fsy) * b * D

    # Stress-block factors (AS3600)
    alpha2 = max(0.67, 0.85 - 0.0015 * fc)
    gamma = max(0.67, 0.97 - 0.0025 * fc)

    # ------------------------------------------------------------------
    # ULS Capacity
    # ------------------------------------------------------------------
    T = Ast * fsy                                  # N
    denom = alpha2 * fc * b * gamma

    if denom <= 0:
        update_results(phi_Mu_cap=0.0, Mu_utilisation=float("nan"))
        return {
            "phi_Mu_cap": 0.0,
            "Mu_util": float("nan"),
            "c": float("nan"),
            "a": float("nan"),
            "z": float("nan"),
            "ku": float("nan"),
            "d": d,
            "alpha2": alpha2,
            "gamma": gamma,
            "fctf": fctf,
            "I_gross": I_gross,
            "Z_gross": Z_gross,
            "Mcr": Mcr,
            "As_min": As_min,
            "phi": phi,
        }

    c = T / denom                   # neutral axis depth
    a = gamma * c
    z = d - 0.5 * a
    Mu_nom = T * z / 1e6            # kNm
    phi_Mu_cap = phi * Mu_nom
    Mu_util = Mu_star / phi_Mu_cap if phi_Mu_cap > 0 else float("inf")
    ku = c / d

    # Write to session
    update_results(phi_Mu_cap=phi_Mu_cap, Mu_utilisation=Mu_util)

    return {
        "phi_Mu_cap": phi_Mu_cap,
        "Mu_util": Mu_util,
        "c": c,
        "a": a,
        "z": z,
        "ku": ku,
        "d": d,
        "alpha2": alpha2,
        "gamma": gamma,
        "fctf": fctf,
        "I_gross": I_gross,
        "Z_gross": Z_gross,
        "Mcr": Mcr,
        "As_min": As_min,
        "phi": phi,
    }


# ---------------------------------------------------------------------
# 4. STRESS–STRAIN STATE (uses new weighted centroid d)
# ---------------------------------------------------------------------
def _stress_strain_state(state: str):
    """
    Produces strain + stress info for the diagram using the new d.
    """

    b = get_param("b") or 300.0
    D = get_param("D") or 600.0
    fc = get_param("fc") or 32.0
    fsy = get_param("fsy") or 500.0
    Es = get_param("Es") or 200000.0
    Ec = get_param("Ec") or (4700 * math.sqrt(fc))

    # Effective centroid
    d = _compute_d_centroid_weighted()
    if d in (None, 0):
        cover = get_param("cover_bot") or 40.0
        db = get_param("db_bot") or 24.0
        d = D - cover - db / 2.0

    # Steel area
    Ast = get_param("Ast_bot")
    if Ast is None:
        nb = get_param("nb_bot") or 2
        db = get_param("db_bot") or 20.0
        Ast = nb * math.pi * db**2 / 4.0

    # AS3600 stress block
    alpha2 = max(0.67, 0.85 - 0.0015 * fc)
    gamma = max(0.67, 0.97 - 0.0025 * fc)

    # Default strain limits
    eps_cu = 0.003
    eps_sls = 0.0008
    eps_unc = 0.0002

    # --------------------------------------------------------------
    # ULS
    # --------------------------------------------------------------
    if state == "ULS":
        denom = alpha2 * fc * b * gamma
        c = Ast * fsy / denom if denom > 0 else D / 2.0
        c = min(max(c, 1.0), D - 1.0)

        eps_c = -eps_cu
        eps_s = -eps_c * (d - c) / c
        fs_t = fsy

        return dict(
            b=b, D=D, d=d, c=c,
            eps_c=eps_c, eps_s=eps_s,
            gamma=gamma, fs_t=fs_t,
            fc=fc, fsy=fsy, alpha2=alpha2
        )

    # --------------------------------------------------------------
    # SLS (cracked)
    # --------------------------------------------------------------
    if state == "SLS (cracked)":
        n = Es / Ec
        a = b / 2.0
        bq = n * Ast
        cq = -n * Ast * d
        disc = bq**2 - 4 * a * cq

        if disc < 0:
            c = D / 2.0
        else:
            r1 = (-bq + math.sqrt(disc)) / (2 * a)
            r2 = (-bq - math.sqrt(disc)) / (2 * a)
            roots = [r for r in (r1, r2) if 0 < r < D]
            c = roots[0] if roots else D / 2.0

        eps_c = -eps_sls
        eps_s = -eps_c * (d - c) / c
        fs_t = Es * eps_s

        return dict(
            b=b, D=D, d=d, c=c,
            eps_c=eps_c, eps_s=eps_s,
            gamma=gamma, fs_t=fs_t,
            fc=fc, fsy=fsy, alpha2=alpha2
        )

    # --------------------------------------------------------------
    # Uncracked
    # --------------------------------------------------------------
    c = D / 2.0
    eps_c = -eps_unc
    eps_s = eps_unc * (d - c) / c
    fs_t = Ec * abs(eps_s)

    return dict(
        b=b, D=D, d=d, c=c,
        eps_c=eps_c, eps_s=eps_s,
        gamma=1.0, fs_t=fs_t,
        fc=fc, fsy=fsy, alpha2=alpha2
    )
# =====================================================================
# PART 2 — DIAGRAM HELPERS
# =====================================================================

import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, Circle
import numpy as np
import math


# ------------------------------------------------------------
# BAR LAYOUT (shared helper)
# ------------------------------------------------------------
def _layout_bars_in_rows(n_bars, b, cover, db, min_spacing, n_rows_max=2):
    """
    Lay out bars in 1–2 rows and return a list of (x_rel, row_idx).

    x_rel = horizontal position relative to left edge of section
    row_idx = 0 (bottom row), 1 (second row)
    """
    if n_bars is None or n_bars <= 0:
        return []

    n_bars = int(n_bars)

    # inner clear width
    inner = max(b - 2 * cover, db)

    # Try 1 row
    if n_bars == 1:
        n_per_row = [1]
    else:
        spacing_row = inner / (n_bars - 1)
        if spacing_row >= min_spacing or n_rows_max == 1:
            n_per_row = [n_bars]      # all in one row
        else:
            # Two rows
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
            spacing = inner / (n_in_row - 1)
            spacing = max(spacing, min_spacing)
            xs = [cover + spacing * i for i in range(n_in_row)]

        for x in xs:
            coords.append((x, row_idx))
            bar_index += 1
            if bar_index >= n_bars:
                break
        if bar_index >= n_bars:
            break

    return coords


# ------------------------------------------------------------
# CROSS-SECTION DIAGRAM (for step-by-step)
# ------------------------------------------------------------
def _make_cross_section_figure(
    b,
    D,
    d_eff,
    a,
    nb_bot,
    db_bot,
    cover_bot,
    nb_top=0,
    db_top=0,
    cover_top=40,
    c=None,
    z=None,
    show_compression=True,
    title="Cross-section",
):
    """
    Draws a clean ULS/SLS section diagram:
    - concrete outline
    - compression block (optional)
    - bottom bars + top bars (multi-row)
    """

    fig, ax = plt.subplots(figsize=(3.5, 7))

    # Axes setup
    ax.set_ylim(D + 40, -40)
    ax.set_xlim(-40, b + 140)
    ax.axis("off")

    # ------------------------------------------------------
    # Concrete outline
    # ------------------------------------------------------
    ax.add_patch(
        Rectangle((0, 0), b, D, fill=False, linewidth=1.4, edgecolor="black")
    )

    # ------------------------------------------------------
    # Compression block (optional)
    # ------------------------------------------------------
    if show_compression and c is not None:
        block_depth = min(a, D)
        ax.add_patch(
            Rectangle(
                (0, 0),
                b,
                block_depth,
                facecolor="#c7e3ff",
                edgecolor="tab:red",
                linewidth=1.2,
                alpha=0.75,
            )
        )

        # NA line
        ax.hlines(c, -10, b + 10, linestyles="--", colors="red", linewidth=1)

    # ------------------------------------------------------
    # Bottom bars
    # ------------------------------------------------------
    if nb_bot and db_bot:
        min_spacing = 2 * db_bot
        bot_layout = _layout_bars_in_rows(
            nb_bot, b, cover_bot, db_bot, min_spacing, n_rows_max=2
        )

        r = db_bot / 2
        pitch = db_bot + 25   # vertical row gap, approx; real value comes from Inputs page
        y0 = D - cover_bot - r

        for x_rel, row_idx in bot_layout:
            y = y0 - row_idx * pitch
            ax.add_patch(
                Circle(
                    (x_rel, y),
                    r,
                    fill=False,
                    edgecolor="tab:blue",
                    linewidth=1.3,
                )
            )

    # ------------------------------------------------------
    # Top bars
    # ------------------------------------------------------
    if nb_top and db_top:
        min_spacing_top = 2 * db_top
        top_layout = _layout_bars_in_rows(
            nb_top, b, cover_top, db_top, min_spacing_top, n_rows_max=2
        )

        r = db_top / 2
        pitch = db_top + 25
        y0 = cover_top + r

        for x_rel, row_idx in top_layout:
            y = y0 + row_idx * pitch
            ax.add_patch(
                Circle(
                    (x_rel, y),
                    r,
                    fill=False,
                    edgecolor="tab:red",
                    linewidth=1.3,
                )
            )

    # ------------------------------------------------------
    # Dimension arrows
    # ------------------------------------------------------
    if c is not None:
        ax.text(
            b + 20,
            c,
            f"NA = {c:.0f} mm",
            color="tab:red",
            va="center",
        )

    if d_eff:
        ax.text(
            b + 20,
            d_eff,
            f"d = {d_eff:.0f} mm",
            va="center",
        )

    ax.set_title(title)

    return fig


# ------------------------------------------------------------
# FULL STRESS–STRAIN + SECTION DIAGRAM (three panels)
# ------------------------------------------------------------
def _plot_stress_strain_profiles(state):
    """
    Creates THREE SIDE-BY-SIDE PANELS:
        1) ULS section (with bars + compression)
        2) Strain profile
        3) Stress block (α2γ)
    """
    b = state["b"]
    D = state["D"]
    d = state["d"]
    c = state["c"]
    eps_c = state["eps_c"]
    eps_s = state["eps_s"]
    gamma = state["gamma"]
    fs_t = state["fs_t"]
    fc = state["fc"]
    alpha2 = state["alpha2"]

    fig, ax = plt.subplots(figsize=(9, 3.8))

    # Layout
    ax.set_xlim(0, b + 450)
    ax.set_ylim(D, 0)
    ax.axis("off")

    x_section = 0
    x_strain = b + 120
    x_stress = b + 300

    # =====================================================
    # 1) SECTION PANEL
    # =====================================================
    ax.add_patch(Rectangle((x_section, 0), b, D, fill=False, lw=1.4))

    # compression
    block = min(gamma * c, D)
    ax.add_patch(
        Rectangle(
            (x_section, 0),
            b,
            block,
            facecolor="#c7e3ff",
            edgecolor="tab:red",
            alpha=0.75,
        )
    )

    # bars
    nb_bot = state.get("nb_bot", 0)
    db_bot = state.get("db_bot", 0)
    cover_bot = state.get("cover_bot", 40)

    min_spacing = 2 * db_bot
    bot_layout = _layout_bars_in_rows(nb_bot, b, cover_bot, db_bot, min_spacing)

    r = db_bot / 2
    pitch = db_bot + 25
    y0 = D - cover_bot - r

    for x_rel, row_idx in bot_layout:
        x = x_section + x_rel
        y = y0 - row_idx * pitch
        ax.add_patch(Circle((x, y), r, fill=False, edgecolor="tab:blue"))

    # NA
    ax.hlines(c, x_section - 10, x_section + b + 10, colors="black", ls="--")

    ax.text(x_section + b / 2, -0.07 * D, "ULS Section", ha="center")

   # =====================================================
# 2) STRAIN PANEL
# =====================================================
x_c = x_strain + eps_c * 12000
x_s = x_strain - eps_s * 12000

ax.plot([x_c, x_s], [0, d], color="black")

ax.text(x_c, 0, f"εc={eps_c:.4f}", color="tab:red")
ax.text(x_s, d, f"εs={eps_s:.4f}", color="tab:blue")

ax.text(x_strain, -0.07 * D, "Strain Profile", ha="center")

# =====================================================
# 3) STRESS PANEL
# =====================================================
ax.plot([x_stress, x_stress], [0, D], color="black", lw=1)

# steel arrow
ax.annotate(
    "",
    xy=(x_stress + fs_t / 4, d),
    xytext=(x_stress, d),
    arrowprops=dict(arrowstyle="->", color="tab:blue", lw=1.3),
)
ax.text(x_stress + fs_t / 3, d, f"T={fs_t:.0f} MPa", color="tab:blue")

# compression block
block_w = fs_t / 8
ax.add_patch(
    Rectangle(
        (x_stress, 0),
        block_w,
        gamma * c,
        fill=False,
        edgecolor="tab:red",
        lw=1.3,
    )
)

ax.hlines(c, x_stress - 10, x_stress + block_w + 20, ls="--")
ax.text(x_stress, -0.07 * D, "Stress Block", ha="left")

return fig


# ------------------------------------------------------------
# SIMPLE α2–γ ULS STRESS BLOCK (for step-by-step)
# ------------------------------------------------------------
def _make_uls_stress_block_figure(c, d, gamma_sb, fsy, show_lever_arm=False):
    if c in (None, 0) or d in (None, 0):
        fig, ax = plt.subplots()
        ax.text(0.5, 0.5, "No data", ha="center")
        ax.axis("off")
        return fig

    fig, ax = plt.subplots(figsize=(3, 6))
    ax.set_ylim(d + 50, -50)
    ax.set_xlim(0, 1.3)
    ax.axis("off")

    # NA
    ax.hlines(c, 0, 1, ls="--", lw=1)

    # block
    block_top = 0
    block_bottom = gamma_sb * c

    ax.fill_between(
        [0, 0.45],
        [block_top, block_top],
        [block_bottom, block_bottom],
        facecolor="#c7e3ff",
        edgecolor="tab:red",
        lw=1.3,
        alpha=0.8,
    )

    # tension steel
    ax.annotate(
        "",
        xy=(1.0, d),
        xytext=(0.45, d),
        arrowprops=dict(arrowstyle="->", color="tab:blue", lw=1.4),
    )
    ax.text(1.02, d, "T = Ast fsy", color="tab:blue", va="center")

    if show_lever_arm:
        z = d - 0.5 * gamma_sb * c
        ax.annotate(
            "",
            xy=(0.7, d),
            xytext=(0.7, 0.5 * gamma_sb * c),
            arrowprops=dict(arrowstyle="<->", lw=1.2),
        )
        ax.text(0.72, (d + 0.5 * gamma_sb * c) / 2, "z")

    ax.set_title("ULS Stress Block")
    return fig


