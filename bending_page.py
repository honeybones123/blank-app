import math
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
            "phi": 0.85,
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

    # ---- Minimum tensile reinforcement (same style as old sheet) ----
    kAst = 1.0
    As_min = kAst * (d / D) ** 2 * (fctf / fsy) * b * D

    # ---- Stress-block factors (kept constant for teaching here) ----
    alpha2 = 0.85
    gamma = 0.85
    phi = 0.85

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
#  DIAGRAM HELPERS (cross-section + stress)
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
):
    """Front cross-section with compression zone + top + bottom bars + labels."""
    if None in (b, D):
        return None

    # Defaults for bottom bars
    if nb_bot is None or nb_bot < 1:
        nb_bot = 3
    if db_bot is None or db_bot <= 0:
        db_bot = 20.0
    if cover_bot is None or cover_bot <= 0:
        cover_bot = 40.0

    # Default values for top bars
    if nb_top is None or nb_top < 1:
        nb_top = 2
    if db_top is None or db_top <= 0:
        db_top = 16.0
    if cover_top is None or cover_top <= 0:
        cover_top = 40.0

    # Safe integer nb's
    nb_bot = max(1, int(round(nb_bot)))
    nb_top = max(1, int(round(nb_top)))

    fig, ax = plt.subplots(figsize=(4.5, 7))

    # Outline
    outline = Rectangle((0, 0), b, D, fill=False, linewidth=2)
    ax.add_patch(outline)

    # Compression block
    if a is None or (isinstance(a, float) and math.isnan(a)) or a <= 0:
        a = 0.15 * D

    comp = Rectangle((0, 0), b, a, facecolor="#c7e3ff", edgecolor="none")
    ax.add_patch(comp)
    ax.text(b / 2, a / 2, "Compression\nzone", ha="center", va="center", fontsize=10)

    # -------------------------
    # Bottom reo
    # -------------------------
    if d is None or (isinstance(d, float) and math.isnan(d)):
        d = 0.9 * D
    y_bot = d

    inner_width_bot = b - 2 * cover_bot
    if inner_width_bot < db_bot:
        inner_width_bot = db_bot

    if nb_bot == 1:
        xs_bot = [b / 2]
    else:
        spacing_bot = inner_width_bot / (nb_bot - 1)
        xs_bot = [cover_bot + i * spacing_bot for i in range(nb_bot)]

    for x in xs_bot:
        ax.add_patch(
            Circle((x, y_bot), radius=db_bot / 2, fill=False, linewidth=1.6)
        )

    # -------------------------
    # TOP reo
    # -------------------------
    y_top = cover_top + db_top / 2

    inner_width_top = b - 2 * cover_top
    if inner_width_top < db_top:
        inner_width_top = db_top

    if nb_top == 1:
        xs_top = [b / 2]
    else:
        spacing_top = inner_width_top / (nb_top - 1)
        xs_top = [cover_top + i * spacing_top for i in range(nb_top)]

    for x in xs_top:
        ax.add_patch(
            Circle(
                (x, y_top),
                radius=db_top / 2,
                fill=False,
                edgecolor="black",
                linewidth=1.6,
            )
        )

    # -------------------------
    # LABELS (c, a, d, z)
    # -------------------------
    # c label
    if c is not None and not (isinstance(c, float) and math.isnan(c)):
        ax.annotate(
            "c",
            xy=(b + 10, c / 2),
            xytext=(b + 40, c / 2),
            arrowprops=dict(arrowstyle="<->"),
            va="center",
        )
        ax.text(b + 45, c / 2, f"{c:.0f} mm", va="center")

    # a label
    if a is not None and not (isinstance(a, float) and math.isnan(a)):
        ax.annotate(
            "a",
            xy=(b + 10, a / 2),
            xytext=(b + 40, a / 2),
            arrowprops=dict(arrowstyle="<->"),
            va="center",
        )

    # d label
    if d is not None and not (isinstance(d, float) and math.isnan(d)):
        ax.annotate(
            "d",
            xy=(b + 10, d / 2),
            xytext=(b + 40, d / 2),
            arrowprops=dict(arrowstyle="<->"),
            va="center",
        )

    # z label
    if (
        z is not None
        and not (isinstance(z, float) and math.isnan(z))
        and a is not None
        and not (isinstance(a, float) and math.isnan(a))
    ):
        ax.annotate(
            "z",
            xy=(b + 10, d - z / 2),
            xytext=(b + 40, d - z / 2),
            arrowprops=dict(arrowstyle="<->"),
            va="center",
        )

    # -------------------------
    # Axes settings
    # -------------------------
    ax.set_xlim(-20, b + 120)
    ax.set_ylim(D + 40, -40)
    ax.set_aspect("equal", "box")
    ax.set_xlabel("Width (mm)")
    ax.set_ylabel("Depth (mm)")
    ax.set_title("ULS SECTION")

    return fig


def _make_stress_figure(fc, fsy, alpha2, D, d, c):
    """Simple ULS stress diagram: α₂ f'c in compression, fsy in steel."""
    if None in (fc, fsy):
        return None

    if alpha2 is None or math.isnan(alpha2):
        alpha2 = 0.85
    if D is None or math.isnan(D):
        D = 600.0
    if d is None or math.isnan(d):
        d = 0.9 * D
    if c is None or math.isnan(c):
        c = 0.2 * D

    fc_comp = alpha2 * fc  # MPa
    x_max = 1.2 * max(fc_comp, fsy)

    fig, ax = plt.subplots()

    # Compression block stress
    comp = Rectangle((0, 0), fc_comp, c, linewidth=0, facecolor="#c7e3ff")
    ax.add_patch(comp)
    ax.text(
        0.5 * fc_comp,
        0.05 * c,
        r"$\alpha_2 f'_c$",
        ha="center",
        va="bottom",
        fontsize=10,
    )

    # Steel stress at depth d (assume yields)
    ax.hlines(d, 0.0, fsy, linewidth=2.5)
    ax.text(
        0.5 * fsy,
        d + 0.04 * D,
        rf"{fsy:.0f} MPa (Steel yields)",
        ha="center",
        va="bottom",
        fontsize=9,
    )

    ax.set_xlim(0.0, x_max)
    ax.set_ylim(D + 0.1 * D, -0.1 * D)  # depth downwards
    ax.set_xlabel("Stress (MPa)")
    ax.set_ylabel("Depth (mm)")
    ax.set_title("ULS STRESS (MPa)")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

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
            **As,min** – Minimum required tensile steel for ductile behaviour.  
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

    # checks
    As_ok = None
    if Ast is not None and As_min_top and not math.isnan(As_min_top):
        As_ok = Ast >= As_min_top

    Mu_ok = None
    if phi_Mu_cap_top and phi_Mu_cap_top > 0 and Mu_star is not None:
        Mu_ok = Mu_star <= phi_Mu_cap_top

    ku_ok = None
    if ku_top is not None and not math.isnan(ku_top):
        # simple teaching limit: ku <= 0.36
        ku_ok = (0.0 < ku_top <= 0.36)

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

    st.markdown("---")

    # ============================================================
    #  DESIGN ACTIONS (Mu*, N*, P*) – WITH INSIGHTS
    # ============================================================
    st.subheader("Design Actions for Bending")

    da1, da2, da3 = st.columns(3)

    with da1:
        number_row(
            "Design moment Mu* (kNm)",
            "bending_Mu_star",
            10.0,
            sync_callbacks,
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
            sync_callbacks,
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
            sync_callbacks,
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
            sync_callbacks,
            help_text=(
                "Section width. Increasing b increases compression block area and "
                "reduces required tensile steel for a given Mu*."
            ),
        )
        number_row(
            "Depth D (mm)",
            "bending_D",
            10.0,
            sync_callbacks,
            help_text=(
                "Overall section depth. Larger D increases lever arm (d) and "
                "typically increases bending capacity."
            ),
        )
        number_row(
            "Span L (mm)",
            "bending_L",
            100.0,
            sync_callbacks,
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
            sync_callbacks,
            help_text=(
                "Concrete compressive strength. Higher f'c increases compression "
                "capacity and may reduce required steel, but also changes ductility limits."
            ),
        )
        number_row(
            "Steel yield fsy (MPa)",
            "bending_fsy",
            10.0,
            sync_callbacks,
            help_text=(
                "Yield strength of reinforcing steel. Higher fsy increases the "
                "force carried by a given area of steel."
            ),
        )
        number_row(
            "Ec (MPa)",
            "bending_Ec",
            1000.0,
            sync_callbacks,
            help_text=(
                "Short-term modulus of concrete. Mainly affects stiffness and "
                "SLS behaviour rather than φMu,cap."
            ),
        )
        number_row(
            "Es (MPa)",
            "bending_Es",
            10000.0,
            sync_callbacks,
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
            sync_callbacks,
            help_text=(
                "Number of tension bars at the bottom. Increasing nb_bot increases Ast,bot "
                "and hence bending capacity."
            ),
        )
        number_row(
            "Bottom bar diameter db_bot (mm)",
            "bending_db_bot",
            2.0,
            sync_callbacks,
            help_text=(
                "Nominal diameter of bottom bars (e.g. N24 = 24 mm). Larger diameter "
                "bars increase Ast,bot but may impact spacing and ductility."
            ),
        )
        number_row(
            "Bottom row gap (mm)",
            "bending_rowgap_bot",
            5.0,
            sync_callbacks,
            help_text=(
                "Vertical gap between bottom bar rows (if 2 rows are used). Increasing "
                "this moves the second row further from the tension face, increasing its lever arm."
            ),
        )
        number_row(
            "Bottom cover (mm)",
            "bending_cover_bot",
            5.0,
            sync_callbacks,
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
            sync_callbacks,
            help_text=(
                "Number of top bars (compression or hanger steel). "
                "Important for negative moment regions and detailing."
            ),
        )
        number_row(
            "Top bar diameter db_top (mm)",
            "bending_db_top",
            2.0,
            sync_callbacks,
            help_text="Nominal diameter of top bars (e.g. N16 = 16 mm).",
        )
        number_row(
            "Top row gap (mm)",
            "bending_rowgap_top",
            5.0,
            sync_callbacks,
            help_text=(
                "Vertical gap between top bar rows if more than one row is used."
            ),
        )
        number_row(
            "Top cover (mm)",
            "bending_cover_top",
            5.0,
            sync_callbacks,
            help_text=(
                "Concrete cover to top reinforcement. Affects effective depth to "
                "compression reinforcement and durability."
            ),
        )

    st.markdown("---")

    # ============================================================
    #  RUN CAPACITY CALC (for detailed report & diagrams)
    # ============================================================
    results = _compute_bending_capacity()
    phi_Mu_cap = results["phi_Mu_cap"]
    Mu_util = results["Mu_util"]
    c = results["c"]
    a = results["a"]
    z = results["z"]
    ku = results["ku"]
    alpha2 = results["alpha2"]
    gamma = results["gamma"]
    phi = results["phi"]
    fctf = results["fctf"]
    I_gross = results["I_gross"]
    Z_gross = results["Z_gross"]
    Mcr = results["Mcr"]
    As_min = results["As_min"]

    # Shared values for reporting / diagrams
    b = get_param("b")
    D = get_param("D")
    d = get_param("d")
    Ast = get_param("Ast_bot")
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

    Mu_min = 1.2 * Mcr if not math.isnan(Mcr) else float("nan")

    # ============================================================
    #  DETAILED SUMMARY – CLEAN TABLE
    # ============================================================
    st.subheader("Bending Capacity – Detailed Summary (values only)")

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

    Mu_nom_report = phi_Mu_cap / phi if phi and phi > 0 else float("nan")

        # ---------- DETAILED SUMMARY TABLE (cleaned) ----------
    rows = [
        {
            "Parameter": "Minimum steel",
            "Symbol": "As,min",
            "Value": _fmt(As_min, "{:.1f}"),
            "Units": "mm²",
        },
        {
            "Parameter": "Cracking moment",
            "Symbol": "Mcr",
            "Value": _fmt(Mcr, "{:.2f}"),
            "Units": "kNm",
        },
        {
            "Parameter": "Minimum cracking moment",
            "Symbol": "Mu,min",
            "Value": _fmt(Mu_min, "{:.2f}"),
            "Units": "kNm",
        },
        {
            "Parameter": "Gross Z",
            "Symbol": "Zg",
            "Value": _fmt(Z_gross, "{:.3e}"),
            "Units": "mm³",
        },
        {
            "Parameter": "α₂",
            "Symbol": "α2",
            "Value": _fmt(alpha2_sb, "{:.3f}"),
            "Units": "•",
        },
        {
            "Parameter": "γ",
            "Symbol": "γ",
            "Value": _fmt(gamma_sb, "{:.3f}"),
            "Units": "•",
        },
        {
            "Parameter": "Strength reduction",
            "Symbol": "φb",
            "Value": _fmt(phi_b, "{:.3f}"),
            "Units": "•",
        },
        {
            "Parameter": "Neutral axis depth",
            "Symbol": "c",
            "Value": _fmt(c, "{:.2f}"),
            "Units": "mm",
        },
        {
            "Parameter": "Block depth",
            "Symbol": "a = γc",
            "Value": _fmt(a, "{:.2f}"),
            "Units": "mm",
        },
        {
            "Parameter": "Neutral axis ratio",
            "Symbol": "ku = c/d",
            "Value": _fmt(ku_sb, "{:.3f}"),
            "Units": "•",
        },
        {
            "Parameter": "Lever arm",
            "Symbol": "z",
            "Value": _fmt(z, "{:.2f}"),
            "Units": "mm",
        },
        {
            "Parameter": "Nominal moment",
            "Symbol": "Mu",
            "Value": _fmt(Mu_nom_report, "{:.2f}"),
            "Units": "kNm",
        },
        {
            "Parameter": "Design moment cap.",
            "Symbol": "φMu,cap",
            "Value": _fmt(phi_Mu_cap, "{:.2f}"),
            "Units": "kNm",
        },
        {
            "Parameter": "Design moment used",
            "Symbol": "Mu*",
            "Value": _fmt(Mu_star, "{:.2f}"),
            "Units": "kNm",
        },
    ]

    df_summary = pd.DataFrame(rows)
    st.table(df_summary)

    st.markdown("---")

    # ============================================================
    #  STEP-BY-STEP TABS (ULS / SLS ONLY)
    # ============================================================
    tab_uls, tab_sls = st.tabs(["ULS step-by-step", "SLS step-by-step"])

    # ----- ULS detailed tab -----
    with tab_uls:
        st.subheader("ULS Calculation (step-by-step)")

        if phi_Mu_cap > 0 and d and Ast:
            # narrower text column, wider diagram column
            col_text, col_fig = st.columns([1.3, 1])

            # ===========================
            #  LEFT: TEXT / CALCS
            # ===========================
            with col_text:
                # 1. REQUIRED CALCULATED INPUTS FOR BENDING
                st.markdown("### 1. Required calculated inputs for bending")

                # 1.1 Effective depth d
                st.markdown("#### 1.1 Effective depth $d$")
                st.latex(r"d = D - \text{cover}_{bot} - \frac{d_{b,bot}}{2}")
                st.latex(
                    rf"d = {D:.1f} - {cover_bot:.1f} - \frac{{{db_bot:.1f}}}{2}"
                )
                st.latex(rf"d = {d:.1f}\,\text{{ mm}}")

                # 1.2 Bottom steel area Ast,bot
                st.markdown("#### 1.2 Bottom steel area $A_{st,bot}$")
                st.latex(r"A_{st,bot} = n_{b,bot}\,\frac{\pi d_{b,bot}^2}{4}")
                st.latex(
                    rf"A_{{st,bot}} = {nb_bot:d}\,\frac{{\pi \times {db_bot:.1f}^2}}{4}"
                )
                st.latex(rf"A_{{st,bot}} = {Ast:.1f}\,\text{{ mm}}^2")

                st.markdown("---")

                # 2. STRESS-BLOCK PARAMETERS (AS 3600:2018 CL. 8.1.3)
                st.markdown(
                    "### 2. Stress-block parameters "
                    "(AS 3600:2018 Cl. 8.1.3)"
                )

                # 2.1 alpha2 factor
                st.markdown("#### 2.1 $\\alpha_2$ factor")
                st.latex(r"\alpha_2 = 0.85 - 0.0015 f'_c \ge 0.67")
                st.latex(
                    rf"\alpha_2 = 0.85 - 0.0015 \times {fc:.1f}"
                    rf" = {alpha2_raw:.3f}"
                )
                st.latex(rf"\Rightarrow \alpha_2 = {alpha2_sb:.3f}")

                # 2.2 gamma factor
                st.markdown("#### 2.2 $\\gamma$ factor")
                st.latex(r"\gamma = 0.97 - 0.0025 f'_c \ge 0.67")
                st.latex(
                    rf"\gamma = 0.97 - 0.0025 \times {fc:.1f}"
                    rf" = {gamma_raw:.3f}"
                )
                st.latex(rf"\Rightarrow \gamma = {gamma_sb:.3f}")

                # 2.3 strength reduction and neutral-axis ratio
                st.markdown("#### 2.3 Strength reduction and NA ratio")
                st.latex(rf"\phi_b = {phi_b:.2f}")
                st.latex(r"k_u = \dfrac{c}{d}")
                st.latex(rf"k_u = \dfrac{{{c:.2f}}}{{{d:.1f}}} = {ku_sb:.3f}")

                st.markdown("---")

                # 3. MINIMUM STRENGTH REQUIREMENTS (AS 3600 CL. 8.1.6)
                st.markdown(
                    "### 3. Minimum strength requirements "
                    "(self-weight check – AS 3600 Cl. 8.1.6)"
                )
                st.markdown(
                    "AS 3600 requires a minimum bending strength so that the beam "
                    "can support its own selfweight without cracking. Here we use "
                    "a teaching model based on concrete flexural tensile strength "
                    "and the gross section modulus."
                )

                # 3.1 Concrete flexural tensile strength f_ct,f
                st.markdown(
                    "#### 3.1 Concrete flexural tensile strength $f_{ct,f}$"
                )
                st.latex(r"f_{ct,f} = c_b (f'_c)^{2/3}")
                st.latex(
                    rf"f_{{ct,f}} = 0.20 \times ({fc:.1f})^{{2/3}}"
                    rf" = {fctf:.3f}\,\text{{ MPa}}"
                )

                # 3.2 Gross section modulus Z_g
                st.markdown("#### 3.2 Gross section modulus $Z_g$")
                st.latex(r"Z_g = \dfrac{b D^2}{6}")
                st.latex(
                    rf"Z_g = \dfrac{{{b:.1f} \times {D:.1f}^2}}{{6}}"
                    rf" = {Z_gross:.3e}\,\text{{ mm}}^3"
                )

                # 3.3 Cracking moment M_cr
                st.markdown("#### 3.3 Cracking moment $M_{cr}$")
                st.latex(r"M_{cr} = \dfrac{f_{ct,f} Z_g}{10^6}")
                st.latex(
                    rf"M_{{cr}} = \dfrac{{{fctf:.3f} \times {Z_gross:.3e}}}{{10^6}}"
                    rf" = {Mcr:.2f}\,\text{{ kNm}}"
                )

                # 3.4 Minimum required ultimate strength (teaching rule)
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

                # 3.5 Minimum tensile reinforcement check
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

                st.markdown("---")

                # 4. ULTIMATE FLEXURAL CAPACITY (φMu,cap)
                st.markdown(
                    "### 4. Ultimate flexural capacity $\\phi M_{u,cap}$"
                )

                # 4.1 Internal forces and neutral-axis depth
                st.markdown(
                    "#### 4.1 Internal forces and neutral-axis depth $c$"
                )
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

                # 4.2 Lever arm and nominal moment
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

                # 4.3 Factored capacity and utilisation
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
                    rf"and $(M_{{uo}})_{{min}} \approx {Muo_min:.2f}\,\text{{ kNm}}$."
                )

            # ===========================
            #  RIGHT: DIAGRAMS
            # ===========================
            with col_fig:
                st.markdown("#### ULS diagrams")

                sec_fig = _make_cross_section_figure(
                    b, D, d, a, nb_bot, db_bot, cover_bot,
                    nb_top=nb_top, db_top=db_top, cover_top=cover_top,
                    c=c, z=z
                )
                if sec_fig is not None:
                    st.pyplot(sec_fig, use_container_width=True)
                    plt.close(sec_fig)

                stress_fig = _make_stress_figure(
                    fc, fsy, alpha2_sb, D, d, c
                )
                if stress_fig is not None:
                    st.pyplot(stress_fig, use_container_width=True)
                    plt.close(stress_fig)

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

    # Debug view of session_state (read-only in UI)
    with st.expander("Debug: raw session_state (optional)"):
        st.write(dict(st.session_state))


if __name__ == "__main__":
    render_bending()

