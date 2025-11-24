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
#  BENDING CAPACITY CALC (α2–γ stress block, teaching model)
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

def _make_cross_section_figure(b, D, d, a, nb_bot, db_bot, cover_bot):
    """Front cross-section with compression zone + bottom bars."""
    if None in (b, D) or math.isnan(b) or math.isnan(D):
        return None

    # Fallbacks for optional reo inputs
    if nb_bot is None or nb_bot < 1:
        nb_bot = 3
    if db_bot is None or db_bot <= 0:
        db_bot = 20.0
    if cover_bot is None or cover_bot < 0:
        cover_bot = 40.0

    # 🔧 Ensure nb_bot is treated as an integer for range()
    try:
        nb_bot_int = max(1, int(round(nb_bot)))
    except (TypeError, ValueError):
        nb_bot_int = 3

    fig, ax = plt.subplots()

    # Outer concrete outline
    outline = Rectangle((0, 0), b, D, fill=False, linewidth=2)
    ax.add_patch(outline)

    # Compression zone (depth "a" from top)
    if a is None or math.isnan(a) or a <= 0:
        a = 0.15 * D
    comp = Rectangle((0, 0), b, a, linewidth=0, facecolor="#c7e3ff")
    ax.add_patch(comp)
    ax.text(
        0.5 * b,
        0.5 * a,
        "Compression\nzone",
        ha="center",
        va="center",
        fontsize=10,
    )

    # Bottom reinforcement row at depth d
    if d is None or math.isnan(d):
        d = 0.9 * D
    y_bar = d

    side_cover = min(cover_bot, 0.4 * b)
    inner_width = max(b - 2 * side_cover, db_bot)

    if nb_bot_int == 1:
        xs = [0.5 * b]
    else:
        spacing = inner_width / (nb_bot_int - 1)
        xs = [side_cover + i * spacing for i in range(nb_bot_int)]

    radius = 0.5 * db_bot
    for x in xs:
        circ = Circle((x, y_bar), radius=radius, fill=False, linewidth=1.8)
        ax.add_patch(circ)

    ax.set_xlim(-0.1 * b, 1.1 * b)
    ax.set_ylim(D + 0.1 * D, -0.1 * D)  # invert y (depth downwards)
    ax.set_xlabel("Width (mm)")
    ax.set_ylabel("Depth (mm)")
    ax.set_title("ULS SECTION")
    ax.set_aspect("equal", "box")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

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
    #  TOP RESULT SUMMARY (Ast, As,min, φMu, ku, utilisation)
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
    As_min_str = f"{As_min_top:.1f} mm²" if As_min_top and not math.isnan(As_min_top) else "—"
    phiMu_str = f"{phi_Mu_cap_top:.2f} kNm" if phi_Mu_cap_top and phi_Mu_cap_top > 0 else "—"
    Mu_star_str = f"{Mu_star:.2f} kNm" if Mu_star not in (None, float("nan")) else "—"
    Mu_util_str = f"{Mu_util_top:.3f}" if phi_Mu_cap_top and phi_Mu_cap_top > 0 else "—"
    ku_str = f"{ku_top:.3f}" if ku_top is not None and not math.isnan(ku_top) else "—"

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
            help_text="Factored design bending moment at the critical section. "
                      "Increasing Mu* increases bending demand and utilisation.",
        )
    with da2:
        number_row(
            "Axial force N* (kN)",
            "bending_N_star",
            50.0,
            sync_callbacks,
            help_text="Axial force acting with bending. Compression (negative in many conventions) "
                      "can reduce tension in the steel; tension increases demand.",
        )
    with da3:
        number_row(
            "Prestress force P* (kN)",
            "bending_P_star",
            50.0,
            sync_callbacks,
            help_text="Prestress / pre-compression in the section. Increasing P* typically "
                      "reduces tensile demand in the bottom reinforcement.",
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
            help_text="Section width. Increasing b increases compression block area and "
                      "reduces required tensile steel for a given Mu*.",
        )
        number_row(
            "Depth D (mm)",
            "bending_D",
            10.0,
            sync_callbacks,
            help_text="Overall section depth. Larger D increases lever arm (d) and "
                      "typically increases bending capacity.",
        )
        number_row(
            "Span L (mm)",
            "bending_L",
            100.0,
            sync_callbacks,
            help_text="Member span. Used mainly for serviceability checks and linking to "
                      "deflection; not directly in φMu,cap here.",
        )

    with g2:
        st.subheader("Materials")
        number_row(
            "Concrete strength f'c (MPa)",
            "bending_fc",
            2.0,
            sync_callbacks,
            help_text="Concrete compressive strength. Higher f'c increases compression "
                      "capacity and may reduce required steel, but also changes ductility limits.",
        )
        number_row(
            "Steel yield fsy (MPa)",
            "bending_fsy",
            10.0,
            sync_callbacks,
            help_text="Yield strength of reinforcing steel. Higher fsy increases the "
                      "force carried by a given area of steel.",
        )
        number_row(
            "Ec (MPa)",
            "bending_Ec",
            1000.0,
            sync_callbacks,
            help_text="Short-term modulus of concrete. Mainly affects stiffness and "
                      "SLS behaviour rather than φMu,cap.",
        )
        number_row(
            "Es (MPa)",
            "bending_Es",
            10000.0,
            sync_callbacks,
            help_text="Steel modulus. Typically ~200,000 MPa; affects cracked-section "
                      "stiffness and strain calculations.",
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
            help_text="Number of tension bars at the bottom. Increasing nb_bot increases Ast,bot "
                      "and hence bending capacity.",
        )
        number_row(
            "Bottom bar diameter db_bot (mm)",
            "bending_db_bot",
            2.0,
            sync_callbacks,
            help_text="Nominal diameter of bottom bars (e.g. N24 = 24 mm). Larger diameter "
                      "bars increase Ast,bot but may impact spacing and ductility.",
        )
        number_row(
            "Bottom row gap (mm)",
            "bending_rowgap_bot",
            5.0,
            sync_callbacks,
            help_text="Vertical gap between bottom bar rows (if 2 rows are used). Increasing "
                      "this moves the second row further from the tension face, increasing its lever arm.",
        )
        number_row(
            "Bottom cover (mm)",
            "bending_cover_bot",
            5.0,
            sync_callbacks,
            help_text="Concrete cover to bottom reinforcement. Increasing cover reduces "
                      "effective depth d and reduces φMu,cap, but may be required for durability.",
        )

    with r2:
        st.subheader("Top Longitudinal Reinforcement")
        number_row(
            "Number of top bars nb_top",
            "bending_nb_top",
            1,
            sync_callbacks,
            help_text="Number of top bars (compression or hanger steel). "
                      "Important for negative moment regions and detailing.",
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
            help_text="Vertical gap between top bar rows if more than one row is used.",
        )
        number_row(
            "Top cover (mm)",
            "bending_cover_top",
            5.0,
            sync_callbacks,
            help_text="Concrete cover to top reinforcement. Affects effective depth to "
                      "compression reinforcement and durability.",
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

    Mu_min = 1.2 * Mcr if not math.isnan(Mcr) else float("nan")

    # ============================================================
    #  EXISTING SUMMARY (more detailed text)
    # ============================================================
    st.subheader("Bending Capacity – Detailed Summary")

    if phi_Mu_cap > 0 and d and Ast:
        Mu_nom = phi_Mu_cap / phi

        if ku is not None and not math.isnan(ku):
            ku_str = f"{ku:.3f}"
        else:
            ku_str = "–"

        summary_md = f"""\
**Section properties**  
- Effective depth: **d = {d:.1f} mm**  
- Bottom steel area: **Ast,bot = {Ast:.1f} mm²**

**Stress-block (teaching model)**  
- α₂ = **{alpha2:.3f}**,  γ = **{gamma:.3f}**,  ϕ = **{phi:.3f}**,  kᵤ = **{ku_str}**

**ULS flexural capacity**  
- Neutral-axis depth: **c = {c:.2f} mm**,  block depth **a = γc = {a:.2f} mm**  
- Lever arm: **z = {z:.2f} mm**  
- Cracking moment: **M_cr = {Mcr:.2f} kNm**,  M_u,min ≈ **{Mu_min:.2f} kNm**  
- Nominal capacity: **M_u = {Mu_nom:.2f} kNm**  
- Design capacity: **ϕM_u,cap = {phi_Mu_cap:.2f} kNm**  
- Utilisation: **M_u*/ϕM_u,cap = {Mu_util:.3f}**  
- Design moment used: **M_u* = {Mu_star:.2f} kNm**
"""
    else:
        summary_md = "Bending capacity cannot be evaluated – check geometry / reo inputs."

    st.markdown(summary_md)

    st.markdown("---")

    # ============================================================
    #  STEP-BY-STEP TABS (ULS / SLS ONLY)
    # ============================================================
    tab_uls, tab_sls = st.tabs(["ULS step-by-step", "SLS step-by-step"])

    # ----- ULS detailed tab -----
    with tab_uls:
        st.subheader("ULS Calculation (step-by-step)")

        if phi_Mu_cap > 0 and d and Ast:
            col_text, col_fig = st.columns([2, 1])

            # ---------- TEXT ----------
            with col_text:
                # 1. Minimum longitudinal tensile reinforcement
                st.markdown("### 1. Minimum longitudinal tensile reinforcement")
                st.markdown(
                    f"Inputs: d = **{d:.1f} mm**, D = **{D:.1f} mm**, "
                    f"f_ct,f = **{fctf:.3f} MPa**, f_sy = **{fsy:.1f} MPa**, "
                    f"b = **{b:.1f} mm**, k_Ast = **1.0**"
                )
                st.latex(
                    r"A_{st,\min} = k_{Ast}\left(\frac{d}{D}\right)^2"
                    r"\frac{f_{ct,f}}{f_{sy}}\,bD"
                )
                st.latex(
                    rf"A_{{st,\min}} = 1.0\left(\frac{{{d:.1f}}}{{{D:.1f}}}\right)^2"
                    rf"\left(\frac{{{fctf:.3f}}}{{{fsy:.1f}}}\right)"
                    rf"{b:.1f}\,{D:.1f} = {As_min:.1f}\,\text{{mm}}^2"
                )

                # 2. Concrete strength in flexure
                st.markdown("### 2. Concrete strength in flexure (before cracking)")
                st.markdown(
                    f"Inputs: f'c = **{fc:.1f} MPa**, c_b = **0.2**"
                )
                st.latex(r"f_{ct,f} = c_b (f'_c)^{2/3}")
                st.latex(
                    rf"f_{{ct,f}} = 0.2({fc:.1f})^{{2/3}}"
                    rf" = {fctf:.3f}\,\text{{MPa}}"
                )

                # 3. Cracking moment
                st.markdown("### 3. Cracking moment")
                st.markdown(
                    f"Inputs: b = **{b:.1f} mm**, D = **{D:.1f} mm**, "
                    f"f_ct,f = **{fctf:.3f} MPa**"
                )
                st.latex(
                    r"I = \frac{bD^3}{12},\quad Z = \frac{bD^2}{6},\quad "
                    r"M_{cr} = f_{ct,f} Z"
                )
                st.latex(
                    rf"I = \frac{{{b:.1f}\times {D:.1f}^3}}{{12}}"
                    rf" = {I_gross:.3e}\,\text{{mm}}^4"
                )
                st.latex(
                    rf"Z = \frac{{{b:.1f}\times {D:.1f}^2}}{{6}}"
                    rf" = {Z_gross:.3e}\,\text{{mm}}^3"
                )
                st.latex(
                    rf"M_{{cr}} = {fctf:.3f}\times {Z_gross:.3e}/10^6"
                    rf" = {Mcr:.2f}\,\text{{kNm}}"
                )

                # 4. Forces and neutral-axis depth
                st.markdown("### 4. Forces and neutral-axis depth")
                st.latex(
                    r"T = A_{st} f_{sy},\quad"
                    r"C = \alpha_2 f'_c b\, \gamma c"
                )
                T = Ast * fsy
                st.latex(
                    rf"T = {Ast:.1f}\times {fsy:.1f}"
                    rf" = {T:,.1f}\,\text{{N}}"
                )
                st.latex(
                    r"C = T \Rightarrow "
                    r"c = \dfrac{T}{\alpha_2 f'_c b \gamma}"
                )
                st.latex(
                    rf"c = \dfrac{{{T:,.1f}}}{{{alpha2:.2f}\times {fc:.1f}"
                    rf"\times {b:.1f}\times {gamma:.2f}}}"
                    rf" = {c:.2f}\,\text{{mm}}"
                )

                # 5. Lever arm and nominal moment
                st.markdown("### 5. Lever arm and nominal moment")
                st.latex(r"a = \gamma c,\quad z = d - a/2")
                st.latex(
                    rf"a = {gamma:.2f}\times {c:.2f}"
                    rf" = {a:.2f}\,\text{{mm}}"
                )
                st.latex(
                    rf"z = {d:.1f} - {a:.2f}/2"
                    rf" = {z:.2f}\,\text{{mm}}"
                )
                Mu_nom = phi_Mu_cap / phi
                st.latex(r"M_u = \dfrac{T z}{10^6}")
                st.latex(
                    rf"M_u = \dfrac{{{T:,.1f}\times {z:.2f}}}{{10^6}}"
                    rf" = {Mu_nom:.2f}\,\text{{kNm}}"
                )

                # 6. Factored capacity and utilisation
                st.markdown("### 6. Factored capacity and utilisation")
                st.latex(r"\phi M_{u,\mathrm{cap}} = \phi M_u")

                phi_str = f"{phi:.2f}"
                Mu_nom_str = f"{Mu_nom:.2f}"
                phiMu_str = f"{phi_Mu_cap:.2f}"
                util_str = f"{Mu_util:.3f}"
                Mu_star_str = f"{Mu_star:.2f}"

                st.latex(
                    r"\phi M_{u,\mathrm{cap}} = "
                    + phi_str
                    + r"\times "
                    + Mu_nom_str
                    + r" = "
                    + phiMu_str
                    + r"\,\text{kNm}"
                )

                st.latex(
                    r"\text{Utilisation} = "
                    r"\dfrac{M_u^*}{\phi M_{u,\mathrm{cap}}}"
                    r" = \dfrac{"
                    + Mu_star_str
                    + r"}{"
                    + phiMu_str
                    + r"} = "
                    + util_str
                )

            # ---------- DIAGRAMS ----------
            with col_fig:
                st.markdown("#### ULS diagrams")

                sec_fig = _make_cross_section_figure(
                    b, D, d, a, nb_bot, db_bot, cover_bot
                )
                if sec_fig is not None:
                    st.pyplot(sec_fig, use_container_width=True)
                    plt.close(sec_fig)

                stress_fig = _make_stress_figure(
                    fc, fsy, alpha2, D, d, c
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
