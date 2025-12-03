import math
import pandas as pd
import matplotlib.pyplot as plt
import streamlit as st

from bending_diagrams import (
    _plot_stress_strain_profiles,
    _make_uls_stress_block_figure,
    _make_uls_force_model_figure,
    _make_sls_stress_block_figure,  # still used elsewhere, untouched
)
from bending_core import _fmt, _layout_bars_in_rows  # <-- add _layout_bars_in_rows here


# ============================================================
#  LOCAL HELPER – CALCBOX WITH LATEX SUPPORT
# ============================================================
def calcbox(md: str):
    """
    Render a blue calculation box with proper LaTeX support.
    Uses st.info() styling which supports LaTeX rendering.
    """
    # Convert \[...\] to $$...$$ for display math
    converted = md.replace("\\[", "$$").replace("\\]", "$$")
    # Convert \(...\) to $...$ for inline math
    converted = converted.replace("\\(", "$").replace("\\)", "$")
    
    # Use st.container with custom border styling
    with st.container(border=True):
        st.markdown(converted)


# ============================================================
#  LOCAL HELPER – SLS STRESS FIGURE FOR 3.2 ONLY
# ============================================================
def _make_sls_stress_block_figure_32(D_mm, d_mm, dn_mm, layers_tension):
    """
    Local SLS stress diagram used ONLY in 3.2.

    Matches the style of the main SLS panel:
    - triangular compression block
    - α2 f'c width arrow on top
    - internal compression arrows
    - dashed NA, vertical d_n arrow + label
    - one T arrow for each tension layer (T1, T2, ...)
    """

    if D_mm <= 0 or math.isnan(D_mm):
        D_mm = 600.0
    if dn_mm <= 0 or math.isnan(dn_mm):
        dn_mm = D_mm / 3.0

    # Set some "stress axis" widths in arbitrary units
    x_comp_max = 1.0       # compression extent
    x_T_max = 1.8          # tension arrow extent
    margin_top = 0.3 * D_mm
    margin_bot = 0.3 * D_mm

    y_min = -margin_top
    y_max = D_mm + margin_bot

    fig, ax = plt.subplots(figsize=(3.0, 3.6))

    # Vertical stress axis
    ax.plot([0, 0], [0, D_mm], color="black", linewidth=1.5)

    # Compression triangle (right angle at top-left)
    tri_x = [0, x_comp_max, 0]
    tri_y = [0, 0, dn_mm]
    ax.fill(tri_x, tri_y, color="#ffcccc", alpha=0.7, zorder=1)
    ax.plot(tri_x + [tri_x[0]], tri_y + [tri_y[0]], color="red", linewidth=1.2, zorder=2)

    # Dashed neutral axis at y = dn
    ax.plot(
        [0, x_T_max],
        [dn_mm, dn_mm],
        linestyle="--",
        linewidth=0.8,
        color="black",
    )

    # α2 f'c label and width arrow above triangle
    y_alpha = -0.08 * D_mm
    ax.annotate(
        "",
        xy=(0, y_alpha),
        xytext=(x_comp_max, y_alpha),
        arrowprops=dict(arrowstyle="<->", color="red", linewidth=1.0),
    )
    ax.text(
        x_comp_max / 2.0,
        y_alpha - 0.04 * D_mm,
        r"$\alpha_2 f'_c$",
        color="red",
        ha="center",
        va="top",
        fontsize=9,
    )

    # A few internal compression arrows (pointing left towards the axis)
    for frac in [0.2, 0.5, 0.8]:
        y_i = frac * dn_mm
        ax.annotate(
            "",
            # arrow goes from right (xytext) to left (xy)
            xy=(0.05 * x_comp_max, y_i),      # head (left)
            xytext=(0.9 * x_comp_max, y_i),   # tail (right)
            arrowprops=dict(arrowstyle="->", color="red", linewidth=0.8),
        )

    # d_n arrow + label to the right of the block
    x_dn = x_T_max * 0.9
    ax.annotate(
        "",
        xy=(x_dn, dn_mm),
        xytext=(x_dn, 0),
        arrowprops=dict(arrowstyle="<->", color="red", linewidth=0.9),
    )
    ax.text(
        x_dn + 0.05 * x_T_max,
        dn_mm / 2.0,
        r"$d_n = %.0f\ \text{mm}$" % dn_mm,
        color="red",
        ha="left",
        va="center",
        fontsize=9,
    )

    # Tension arrows for each layer
    if layers_tension:
        # sort by depth from top
        layers_sorted = sorted(layers_tension, key=lambda L: L["y"])
        for i, layer in enumerate(layers_sorted):
            y_layer = layer["y"]
            name = layer["name"]

            # Clamp y within [0, D_mm]
            y_layer = max(0.0, min(D_mm, y_layer))

            ax.annotate(
                "",
                xy=(x_T_max, y_layer),
                xytext=(0, y_layer),
                arrowprops=dict(arrowstyle="->", color="tab:blue", linewidth=1.0),
            )
            # Slight vertical offset per layer so labels don't collide
            ax.text(
                x_T_max + 0.05 * x_T_max,
                y_layer + (i * 0.04 * D_mm),
                name,
                color="tab:blue",
                ha="left",
                va="center",
                fontsize=8,
            )

    # "Stress (MPa)" label at bottom
    ax.text(
        x_T_max / 2.0,
        D_mm + 0.18 * D_mm,
        "Stress (MPa)",
        ha="center",
        va="bottom",
        fontsize=9,
    )

    # Style
    ax.set_xlim(-0.2 * x_comp_max, x_T_max * 1.3)
    ax.set_ylim(y_max, y_min)  # invert so top is visually "up"
    ax.axis("off")

    return fig


# ============================================================
#  TAB 1 – ULS (UNCHANGED LOGIC, TIDIED CALC BOXES)
# ============================================================
def render_uls_tab(top_results, b, D, fc, fsy, Ast, d):
    """
    Tab 1 – ULS step-by-step.
    """
    phi_Mu_cap = top_results["phi_Mu_cap"]
    phi = top_results["phi"]

    st.subheader("ULS Calculation (step-by-step)")

    if phi_Mu_cap > 0 and d and Ast:
        # 1. Ultimate Limit State
        st.header("1. Ultimate Limit State (ULS)")

        # Stress-block factors
        alpha2_raw_uls = 0.85 - 0.0015 * fc
        gamma_raw_uls = 0.97 - 0.0025 * fc
        alpha2_uls = max(0.67, alpha2_raw_uls)
        gamma_uls = max(0.67, gamma_raw_uls)

        # Pre-compute ULS internal forces / geometry once
        T = Ast * fsy  # N
        denom_uls = alpha2_uls * fc * b * gamma_uls
        dn = T / denom_uls if denom_uls > 0 else float("nan")
        a_uls = gamma_uls * dn
        z_uls = d - 0.5 * a_uls
        Mu_nom_uls = T * z_uls / 1e6
        phi_Mu_cap_uls = phi * Mu_nom_uls

        # Concrete force at ULS (using a = γ d_n)
        C_N = alpha2_uls * fc * b * a_uls  # N

        # --------------------------------------------------
        # 1.1 Stress-block parameters (α2 and γ)
        # --------------------------------------------------
        st.subheader("1.1 Stress-block parameters (α₂ and γ)")
        col_calc_11, col_fig_11 = st.columns([2, 1])

        with col_calc_11:
            calcbox(
                f"""
*Purpose: Determine the ULS rectangular stress-block factors $\\alpha_2$ and $\\gamma$ for the given concrete strength.*  

**Inputs:**  

- Concrete strength: $f'_c = {fc:.1f}$ MPa  

---

**Formula (AS 3600):**

$$
\\alpha_2 = 0.85 - 0.0015 f'_c \\; (\\ge 0.67)
$$

**Substitution:**

$$
\\alpha_2 = 0.85 - 0.0015 \\times {fc:.1f}
         = {alpha2_raw_uls:.3f}
         \\Rightarrow \\alpha_2 = {alpha2_uls:.3f}
$$

---

Similarly,

$$
\\gamma = 0.97 - 0.0025 f'_c \\; (\\ge 0.67)
$$

**Substitution:**

$$
\\gamma = 0.97 - 0.0025 \\times {fc:.1f}
       = {gamma_raw_uls:.3f}
       \\Rightarrow \\gamma = {gamma_uls:.3f}
$$

---

**Result:**  
$\\alpha_2 = {alpha2_uls:.3f}$, $\\gamma = {gamma_uls:.3f}$ (to be used in Sections 1.2–1.6).
"""
            )

        with col_fig_11:
            # Variant "11": compact height to match this calc box.
            fig_uls_11 = _make_uls_stress_block_figure(
                b_mm=b or 0.0,
                D_mm=D or 0.0,
                d_mm=d,
                dn_mm=dn,
                a_mm=a_uls,
                alpha2=alpha2_uls,
                gamma=gamma_uls,
                fc=fc,
                fsy=fsy,
                show_lever_arm=False,
                show_dn=False,          # no d_n for 1.1
                show_alpha_label=True,  # α2 f'c width annotation
                show_C=False,           # no C arrow in 1.1
                C_N=None,
                variant="11",
            )
            st.pyplot(fig_uls_11, use_container_width=False)

        st.markdown("---")

        # --------------------------------------------------
        # 1.2 Concrete compressive force C  (NO DIAGRAM)
        # --------------------------------------------------
        st.subheader("1.2 Concrete compressive force $C$")
        C_kN = C_N / 1000.0 if C_N is not None else float("nan")

        calcbox(
            f"""
*Purpose: Calculate the resultant concrete compressive force $C$ at ULS.*  

**Inputs:**  

- $\\alpha_2 = {alpha2_uls:.3f}$  
- $f'_c = {fc:.1f}$ MPa  
- Section width $b = {b:.1f}$ mm  
- Compression block depth $a = {a_uls:.1f}$ mm  

---

**Formula:**

$$
C = \\alpha_2 f'_c \\, b \\, a
$$

with block depth

$$
a = \\gamma d_n
$$

---

**Substitution:**

$$
C = \\alpha_2 f'_c \\, b \\, a
  = {alpha2_uls:.3f} \\times {fc:.1f} \\times {b:.1f} \\times {a_uls:.1f}
  = {C_kN:.1f}\\ \\text{{kN}}
$$

---

**Result:**  
Concrete compression resultant $C \\approx {C_kN:.1f}$ kN acting at the centroid of the compression block.
"""
        )

        st.markdown("---")

        # --------------------------------------------------
        # 1.3 Steel area and steel tension force T (NO DIAGRAM)
        # --------------------------------------------------
        st.subheader("1.3 Steel area and tension force $T$")

        calcbox(
            f"""
*Purpose: Relate the provided tensile reinforcement area to the tension force $T$ at ULS.*  

**Inputs:**  

- Tensile steel area: $A_{{st}} = {Ast:.1f}\\ \\text{{mm}}^2$  
- Steel yield strength: $f_{{sy}} = {fsy:.1f}$ MPa  

---

**Formula:**

From the section inputs, the total area of bottom tensile steel is:

$$
A_{{st}} = {Ast:.1f}\\ \\text{{mm}}^2
$$

Assuming the tension steel yields at $f_{{sy}}$:

$$
T = A_{{st}} f_{{sy}}
$$

---

**Substitution:**

$$
T = {Ast:.1f} \\times {fsy:.1f}
  = {T:,.0f}\\ \\text{{N}}
  = {T/1000.0:.1f}\\ \\text{{kN}}
$$

---

**Result:**  
Tension force at ULS: $T \\approx {T/1000.0:.1f}$ kN.
"""
        )

        st.markdown("---")

        # --------------------------------------------------
        # 1.4 Neutral axis depth d_n and block depth a
        # --------------------------------------------------
        st.subheader("1.4 Neutral axis depth $d_n$ and block depth $a$")

        col_calc_14, col_fig_14 = st.columns([2, 1])

        with col_calc_14:
            calcbox(
                f"""
*Purpose: Determine the neutral axis depth $d_n$ and corresponding block depth $a$ from force equilibrium.*  

**Inputs:**  

- Tension force: $T = {T/1000.0:.1f}$ kN  
- $\\alpha_2 = {alpha2_uls:.3f}$, $\\gamma = {gamma_uls:.3f}$  
- $f'_c = {fc:.1f}$ MPa  
- $b = {b:.1f}$ mm  

---

**Force equilibrium:**  

Internal equilibrium requires:

$$
C = T
$$

Using the rectangular stress block:

$$
C = \\alpha_2 f'_c\\, b\\, \\gamma d_n
$$

So, setting $C = T$:

$$
\\alpha_2 f'_c\\, b\\, \\gamma d_n = T
$$

Rearranging:

$$
d_n = \\frac{{T}}{{\\alpha_2 f'_c\\, b\\, \\gamma}}
$$

---

**Substitution:**

$$
d_n =
\\frac{{{T:,.0f}}}
     {{ {alpha2_uls:.3f} \\times {fc:.1f} \\times {b:.1f} \\times {gamma_uls:.3f} }}
= {dn:.1f}\\ \\text{{mm}}
$$

Block depth:

$$
a = \\gamma d_n = {gamma_uls:.3f} \\times {dn:.1f}
  = {a_uls:.1f}\\ \\text{{mm}}
$$

---

**Result:**  
$ d_n = {dn:.1f}$ mm, $ a = {a_uls:.1f}$ mm.
"""
            )

        with col_fig_14:
            # Variant "13": taller – matches this calc box.
            fig_uls_14 = _make_uls_stress_block_figure(
                b_mm=b or 0.0,
                D_mm=D or 0.0,
                d_mm=d,
                dn_mm=dn,
                a_mm=a_uls,
                alpha2=alpha2_uls,
                gamma=gamma_uls,
                fc=fc,
                fsy=fsy,
                show_lever_arm=True,     # show z
                show_dn=True,            # show d_n
                show_alpha_label=True,   # α2 f'c + width arrow
                show_C=False,
                C_N=None,
                variant="13",
            )
            st.pyplot(fig_uls_14, use_container_width=False)

        st.markdown("---")

        # --------------------------------------------------
        # 1.5 Neutral axis ratio k_u
        # --------------------------------------------------
        st.subheader("1.5 Neutral axis ratio $k_u$")

        ku = dn / d if d else float("nan")

        calcbox(
            f"""
*Purpose: Express the neutral axis depth as a non-dimensional ratio $k_u$.*  

**Inputs:**  

- Neutral axis depth: $d_n = {dn:.1f}$ mm  
- Effective depth: $d = {d:.1f}$ mm  

---

**Formula:**

A convenient non-dimensional measure of the neutral axis depth is:

$$
k_u = \\frac{{d_n}}{{d}}
$$

**Substitution:**

$$
k_u = \\frac{{{dn:.1f}}}{{{d:.1f}}}
    = {ku:.3f}
$$

---

**Result:**  
Neutral axis ratio $k_u = {ku:.3f}$.
"""
        )

        st.markdown("---")

        # --------------------------------------------------
        # 1.6 Lever arm z and moment capacity (+ force model)
        # --------------------------------------------------
        st.subheader("1.6 Lever arm $z$ and moment capacity")

        col_calc_16, col_fig_16 = st.columns([2, 1])

        with col_calc_16:
            calcbox(
                f"""
*Purpose: Compute the internal lever arm $z$, nominal moment $M_u$ and design moment $\\phi M_{{u,cap}}$.*  

**Inputs:**  

- Effective depth: $d = {d:.1f}$ mm  
- Block depth: $a = {a_uls:.1f}$ mm  
- Tension force: $T = {T:,.0f}$ N  
- Strength reduction factor: $\\phi = {phi:.2f}$  

---

**Lever arm:**  

$$
z = d - \\frac{{a}}{{2}}
$$

**Substitution:**

$$
z = d - \\frac{{a}}{{2}}
  = {d:.1f} - \\frac{{{a_uls:.1f}}}{{2}}
  = {z_uls:.1f}\\ \\text{{mm}}
$$

---

**Nominal moment:**

$$
M_u = \\frac{{T z}}{{10^6}}
$$

$$
M_u = \\frac{{{T:,.0f} \\times {z_uls:.1f}}}{{10^6}}
    = {Mu_nom_uls:.2f}\\ \\text{{kNm}}
$$

---

**Design moment:**

$$
\\phi M_{{u,cap}} = \\phi M_u
               = {phi:.2f} \\times {Mu_nom_uls:.2f}
               = {phi_Mu_cap_uls:.2f}\\ \\text{{kNm}}
$$

---

**Result:**  
Design bending capacity $\\phi M_{{u,cap}} = {phi_Mu_cap_uls:.2f}$ kNm.
"""
            )

        with col_fig_16:
            fig_uls_16 = _make_uls_force_model_figure(
                D_mm=D or 0.0,
                d_mm=d,
                a_mm=a_uls,
                C_N=C_N,
                T_N=T,
            )
            st.pyplot(fig_uls_16, use_container_width=False)

        st.markdown("---")

    else:
        st.info("Capacity cannot be evaluated – check geometry / reo inputs.")


# ============================================================
#  TAB 2 – Minimum Strength (UNCHANGED LOGIC, TIDIED TEXT)
# ============================================================
def render_min_strength_tab(top_results, b, D, fc, fsy, Ast):
    """
    Tab 2 – Minimum strength requirements.
    """
    fctf = top_results["fctf"]
    Z_gross = top_results["Z_gross"]
    Mcr = top_results["Mcr"]
    As_min = top_results["As_min"]

    fctf_as = fctf
    Zg = Z_gross
    Mcr_as = Mcr
    Mu_min_as = (
        1.2 * Mcr_as
        if Mcr_as is not None and not math.isnan(Mcr_as)
        else float("nan")
    )
    Ast_min_as = As_min

    st.header("2. Minimum strength requirements (AS 3600)")

    # 2.1 f_ct,f
    st.subheader("2.1 Concrete flexural tensile strength $f_{{ct,f}}$")
    calcbox(
        f"""
*Purpose: Estimate the concrete flexural tensile strength $f_{{ct,f}}$.*  

**Inputs:**  

- $f'_c = {fc:.1f}$ MPa  

---

**Formula (AS 3600 style):**

$$
f_{{ct,f}} \\approx 0.6 \\sqrt{{f'_c}}
$$

**Substitution:**

$$
f_{{ct,f}} \\approx 0.6 \\sqrt{{{fc:.1f}}}
          = {fctf_as:.3f}\\ \\text{{MPa}}
$$

---

**Result:**  
$f_{{ct,f}} \\approx {fctf_as:.3f}$ MPa.
"""
    )
    st.markdown("---")

    # 2.2 Z_g
    st.subheader("2.2 Gross section modulus $Z_g$")
    calcbox(
        f"""
*Purpose: Calculate the gross section modulus $Z_g$ of the rectangular section.*  

**Inputs:**  

- Width $b = {b:.1f}$ mm  
- Overall depth $D = {D:.1f}$ mm  

---

**Formula:**

$$
Z_g = \\frac{{b D^2}}{{6}}
$$

**Substitution:**

$$
Z_g = \\frac{{{b:.1f} \\times {D:.1f}^2}}{{6}}
    = {Zg:,.3e}\\ \\text{{mm}}^3
$$

---

**Result:**  
$Z_g = {Zg:,.3e}\\ \\text{{mm}}^3$.
"""
    )
    st.markdown("---")

    # 2.3 M_cr
    st.subheader("2.3 Cracking moment $M_{{cr}}$")
    calcbox(
        f"""
*Purpose: Determine the cracking moment $M_{{cr}}$ for the section.*  

**Inputs:**  

- $f_{{ct,f}} = {fctf_as:.3f}$ MPa  
- $Z_g = {Zg:,.3e}\\ \\text{{mm}}^3$  

---

**Formula:**

$$
M_{{cr}} = \\frac{{f_{{ct,f}} Z_g}}{{10^6}}
$$

**Substitution:**

$$
M_{{cr}} = \\frac{{{fctf_as:.3f} \\times {Zg:,.3e}}}{{10^6}}
       = {Mcr_as:.2f}\\ \\text{{kNm}}
$$

---

**Result:**  
$M_{{cr}} \\approx {Mcr_as:.2f}$ kNm.
"""
    )
    st.markdown("---")

    # 2.4 Minimum required capacity (1.2 Mcr)
    st.subheader("2.4 Minimum required design capacity $(M_{{u,cap}})_{{min}}$")
    calcbox(
        f"""
*Purpose: Check the minimum required design capacity relative to cracking moment.*  

**Inputs:**  

- $M_{{cr}} = {Mcr_as:.2f}$ kNm  

---

**Formula:**

$$
(M_{{u,cap}})_{{min}} = 1.2\\, M_{{cr}}
$$

**Substitution:**

$$
(M_{{u,cap}})_{{min}}
= 1.2 \\times {Mcr_as:.2f}
= {Mu_min_as:.2f}\\ \\text{{kNm}}
$$

---

**Result:**  
Minimum required design capacity $(M_{{u,cap}})_{{min}} = {Mu_min_as:.2f}$ kNm.
"""
    )
    st.markdown("---")

    # 2.5 Minimum tensile reinforcement
    st.subheader("2.5 Minimum tensile reinforcement $A_{{st,min}}$")
    calcbox(
        f"""
*Purpose: Calculate minimum tensile reinforcement according to AS 3600 style rules.*  

**Inputs:**  

- $f_{{ct,f}} = {fctf_as:.3f}$ MPa  
- $f_{{sy}} = {fsy:.1f}$ MPa  
- $b = {b:.1f}$ mm  
- Effective depth $d = {top_results['d']:.1f}$ mm  

---

**Formula:**

$$
A_{{st,min}}
= 0.4\\;\\frac{{f_{{ct,f}}}}{{f_{{sy}}}}\\; b d
$$

**Substitution:**

$$
A_{{st,min}}
= 0.4 \\times \\frac{{{fctf_as:.3f}}}{{{fsy:.1f}}}
\\times {b:.1f} \\times {top_results['d']:.1f}
= {Ast_min_as:.1f}\\ \\text{{mm}}^2
$$

---

**Result:**  
Minimum tensile steel area $A_{{st,min}} = {Ast_min_as:.1f}$ mm².
"""
    )
    st.markdown("---")


# ============================================================
#  TAB 3 – SLS (UPDATED WITH LAYERS + COMP STEEL)
# ============================================================
def render_sls_tab(top_results, b, D, d, Ast, Ec, Es, Mu_star):
    """
    Tab 3 – SLS cracked-section teaching model.

    IMPORTANT:
    - For BENDING capacity we can combine bottom bars to one layer.
    - For CRACK CONTROL (AS 3600) we want stresses in EACH steel layer,
      and the OUTERMOST tension layer controls f_s,ser.

    Here we:
      * Build one layer for each bottom bar ROW (T1, T2, ...)
      * Optionally one compression layer for top bars (C1)
    """
    st.header("3. SLS Bending – Cracked Section (Teaching Model)")

    if not (d and Ast and Ec and Es and b and D and Mu_star is not None):
        st.info("Not enough information to run SLS cracked-section example.")
        return

    Ms = Mu_star  # service moment (kNm)

    # --------------------------------------------------
    #  Read bar layout info from session_state
    # --------------------------------------------------
    nb_bot = st.session_state.get("nb_bot", 0) or 0
    db_bot = st.session_state.get("db_bot", 0.0) or 0.0
    cover_bot = st.session_state.get("cover_bot", 0.0) or 0.0
    rowgap_bot = st.session_state.get("rowgap_bot", 0.0) or 0.0

    nb_top = st.session_state.get("nb_top", 0) or 0
    db_top = st.session_state.get("db_top", 0.0) or 0.0
    cover_top = st.session_state.get("cover_top", 0.0) or 0.0

    # --------------------------------------------------
    #  Build STEEL LAYERS
    # --------------------------------------------------
    layers_tension: list[dict] = []

    # --- Bottom tension layers (T1, T2, ...) ---
    if nb_bot > 0 and db_bot > 0 and cover_bot > 0:
        # Same helper as section diagram → rows of bars
        min_spacing_bot = 2 * db_bot
        layout_bot = _layout_bars_in_rows(
            nb_bot, b, cover_bot, db_bot, min_spacing_bot, 3
        )

        # Count bars per row index
        row_counts: dict[int, int] = {}
        for _, row_idx in layout_bot:
            row_counts[row_idx] = row_counts.get(row_idx, 0) + 1

        As_bar_bot = math.pi * db_bot**2 / 4.0
        r_bot = db_bot / 2.0
        y_row0 = D - cover_bot - r_bot  # outermost row depth from top

        for row_idx in sorted(row_counts.keys()):
            n_row = row_counts[row_idx]
            if n_row <= 0:
                continue
            As_row = n_row * As_bar_bot
            y_row = y_row0 - row_idx * (db_bot + rowgap_bot)
            layers_tension.append(
                {
                    "name": f"T{row_idx + 1}",
                    "label": f"Bottom tension steel (row {row_idx + 1})",
                    "y": y_row,
                    "As": As_row,
                }
            )

    # Fallback: if something is missing, use a single equivalent layer
    if not layers_tension:
        layers_tension = [
            {
                "name": "T1",
                "label": "Bottom tension steel",
                "y": d,
                "As": Ast,
            }
        ]

    # --- Top compression layer (C1), if present ---
    As_top = (
        nb_top * math.pi * db_top**2 / 4.0 if nb_top and db_top else 0.0
    )
    y_top = cover_top + db_top / 2.0 if db_top else 0.0
    comp_layer = (
        {
            "name": "C1",
            "label": "Top steel (compression layer)",
            "y": y_top,
            "As": As_top,
        }
        if As_top > 0 and 0.0 < y_top < D
        else None
    )

    include_comp = st.checkbox(
        "Include compression steel in cracked-section analysis",
        value=False,
        key="sls_include_comp",
    )

    # Modular ratio
    n_sls = Es / Ec if Ec else 0.0

    # --------------------------------------------------
    # 3.1 Modular ratio & transformed steel areas
    # --------------------------------------------------
    st.subheader("3.1 Modular ratio $n = E_s / E_c$")

    calcbox(
        f"""
*Purpose: Compute the modular ratio and transformed steel areas for each layer.*  

**Inputs:**  

- $E_s = {Es:.0f}$ MPa  
- $E_c = {Ec:.0f}$ MPa  

---

**Formula:**

$$
n = \\frac{{E_s}}{{E_c}}
$$

**Substitution:**

$$
n = \\frac{{{Es:.0f}}}{{{Ec:.0f}}}
  = {Es/Ec:.2f}
$$

The transformed area of each steel layer is $n A_s$.

---

**Result:**  
Modular ratio $n = {Es/Ec:.2f}$ (used to compute $nA_s$ in the table below).
"""
    )

    # Table of steel layers (transformed areas)
    layer_rows = []
    for layer in layers_tension:
        As_i = layer["As"]
        layer_rows.append(
            {
                "Layer": layer["name"],
                "Description": layer["label"],
                "Depth y (mm)": layer["y"],
                "A_s (mm²)": As_i,
                "n A_s (mm²)": n_sls * As_i,
            }
        )

    if include_comp and comp_layer is not None:
        As_c = comp_layer["As"]
        layer_rows.append(
            {
                "Layer": comp_layer["name"],
                "Description": comp_layer["label"],
                "Depth y (mm)": comp_layer["y"],
                "A_s (mm²)": As_c,
                "n A_s (mm²)": n_sls * As_c,
            }
        )

    st.table(pd.DataFrame(layer_rows))
    st.markdown("---")

    # --------------------------------------------------
    # 3.2 Neutral axis depth d_n (cracked section) + SLS stress figure
    # --------------------------------------------------
    st.subheader("3.2 Neutral axis depth $d_n$ (cracked section)")

    def equilibrium_residual(dn: float) -> float:
        """C(dn) - T(dn) = 0 for cracked section."""
        # Concrete compression resultant
        C_conc = 0.5 * b * dn**2

        # Steel contributions (transformed)
        T_steel = 0.0

        # tension layers
        for layer in layers_tension:
            As_i = layer["As"]
            y_i = layer["y"]
            if y_i > dn:
                T_steel += n_sls * As_i * (y_i - dn)
            else:
                # if a "tension" layer ends up above NA, treat as compression
                C_conc += n_sls * As_i * (dn - y_i)

        # optional compression layer
        if include_comp and comp_layer is not None:
            As_c = comp_layer["As"]
            y_c = comp_layer["y"]
            if y_c < dn:
                C_conc += n_sls * As_c * (dn - y_c)
            else:
                T_steel += n_sls * As_c * (y_c - dn)

        return C_conc - T_steel

    # Simple bisection between near-top and near-bottom
    dn_low = 1e-6
    dn_high = D - 1e-6
    f_low = equilibrium_residual(dn_low)
    f_high = equilibrium_residual(dn_high)

    if f_low * f_high < 0:
        for _ in range(60):
            dn_mid = 0.5 * (dn_low + dn_high)
            f_mid = equilibrium_residual(dn_mid)
            if f_low * f_mid <= 0:
                dn_high = dn_mid
                f_high = f_mid
            else:
                dn_low = dn_mid
                f_low = f_mid
        dn_sls = 0.5 * (dn_low + dn_high)
    else:
        # Fallback: use the original single-layer quadratic if bracketing fails
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

    col_32_calc, col_32_fig = st.columns([2, 1])

    with col_32_calc:
        calcbox(
            f"""
*Purpose: Find the cracked-section neutral axis depth $d_n$ by enforcing equilibrium of transformed areas.*  

**Concept:**  

Tension side:

$$
T = \\sum n A_{{s,i}} (d_i - d_n)
$$

Concrete (and any compression steel) provide compression $C$ so that:

$$
\\frac{{b d_n^2}}{{2}} + \\sum n A_{{s,c}} (d_n - d_{{s,c}}) = \\sum n A_{{s,i}} (d_i - d_n)
$$

This equation is solved numerically for $d_n$ using bisection on the current section.

---

**Result (this section):**

$$
d_n = {dn_sls:.2f}\\ \\text{{mm}}
$$
"""
        )

    with col_32_fig:
        # Local, detailed SLS stress diagram (this does NOT touch the main SLS panel)
        fig_sls = _make_sls_stress_block_figure_32(
            D_mm=D or 0.0,
            d_mm=d,
            dn_mm=dn_sls,
            layers_tension=layers_tension,
        )
        st.pyplot(fig_sls, use_container_width=False)
        plt.close(fig_sls)

    st.markdown("---")

    # --------------------------------------------------
    # 3.3 Cracked moment of inertia I_cr (CALC BOX ONLY)
    # --------------------------------------------------
    st.subheader("3.3 Cracked moment of inertia $I_{{cr}}$")

    # Classify compression / tension for Icr based on dn_sls
    I_conc = b * dn_sls**3 / 3.0
    I_t = 0.0
    I_c = 0.0

    for layer in layers_tension:
        As_i = layer["As"]
        y_i = layer["y"]
        if y_i >= dn_sls:
            I_t += n_sls * As_i * (y_i - dn_sls) ** 2
        else:
            I_c += n_sls * As_i * (dn_sls - y_i) ** 2

    if include_comp and comp_layer is not None:
        As_c = comp_layer["As"]
        y_c = comp_layer["y"]
        if y_c < dn_sls:
            I_c += n_sls * As_c * (dn_sls - y_c) ** 2
        else:
            I_t += n_sls * As_c * (y_c - dn_sls) ** 2

    Icr = I_conc + I_t + I_c

    calcbox(
        f"""
*Purpose: Compute the cracked transformed moment of inertia $I_{{cr}}$ about the neutral axis.*  

**Formula:**

$$
I_{{cr}} =
\\frac{{b d_n^3}}{{3}}
+ \\sum n A_{{s,i}} (d_i - d_n)^2
+ \\sum n A_{{s,c}} (d_n - d_{{s,c}})^2
$$

For this section:

- Concrete term: $\\dfrac{{b d_n^3}}{{3}} = {_fmt(I_conc)}\\ \\text{{mm}}^4$  
- Steel in tension: $\\sum n A_{{s,i}} (d_i - d_n)^2 = {_fmt(I_t)}\\ \\text{{mm}}^4$  
- Steel in compression: $\\sum n A_{{s,c}} (d_n - d_{{s,c}})^2 = {_fmt(I_c)}\\ \\text{{mm}}^4$  

So:

$$
I_{{cr}} = {Icr:,.2f}\\ \\text{{mm}}^4
$$

---

**Result:**  
Cracked transformed inertia $I_{{cr}} = {Icr:,.2f}\\ \\text{{mm}}^4$.
"""
    )

    st.markdown("---")

    # --------------------------------------------------
    # 3.4 Curvature at service moment
    # --------------------------------------------------
    st.subheader("3.4 Curvature at service moment")

    Ms_Nmm = Ms * 1e6
    kappa = Ms_Nmm / (Ec * Icr) if Ec and Icr else 0.0

    calcbox(
        f"""
*Purpose: Evaluate curvature at the service moment using the cracked-section stiffness.*  

**Inputs:**  

- Service moment $M_s = {Ms:.2f}$ kNm  
- $E_c = {Ec:.0f}$ MPa  
- $I_{{cr}} = {Icr:,.2f}\\ \\text{{mm}}^4$  

---

**Formula:**

$$
\\kappa = \\frac{{M_s}}{{E_c I_{{cr}}}}
$$

**Substitution:**

$$
\\kappa = \\frac{{{Ms:.2f}\\times 10^6}}{{{Ec:.0f} \\times {Icr:,.2f}}}
       = {kappa:.3e}\\ \\text{{mm}}^{{-1}}
$$

---

**Result:**  
Curvature at service: $\\kappa = {kappa:.3e}\\ \\text{{mm}}^{{-1}}$.
"""
    )
    st.markdown("---")

    # --------------------------------------------------
    # 3.5 Strain distribution ε(y) = κ (y − d_n)
    # --------------------------------------------------
    st.subheader("3.5 Strain distribution $\\varepsilon(y) = \\kappa (y - d_n)$")

    strain_points = [("Top fibre", 0.0)]
    for layer in layers_tension:
        strain_points.append((layer["label"], layer["y"]))
    if include_comp and comp_layer is not None:
        strain_points.append((comp_layer["label"], comp_layer["y"]))
    strain_points.append(("Bottom fibre", D))

    strain_rows = []
    for name, yi in strain_points:
        eps = kappa * (yi - dn_sls)
        strain_rows.append({"Layer": name, "Depth y (mm)": yi, "ε": eps})

    df_eps = pd.DataFrame(strain_rows)

    col_sls_calc, col_sls_fig = st.columns([2, 1])

    with col_sls_calc:
        calcbox(
            f"""
*Purpose: Compute the linear strain distribution at SLS for key depths.*  

**Formula:**

Strain at depth $y$ from the top:

$$
\\varepsilon(y) = \\kappa (y - d_n)
$$

For key layers (including each steel layer), the table lists:

- Depth $y$  
- Strain $\\varepsilon(y)$  

---

**Result:**  
See table for $\\varepsilon(y)$ at the top fibre, each steel layer, and bottom fibre.
"""
        )
        st.table(df_eps)

    with col_sls_fig:
        fig_eps, ax_eps = plt.subplots()
        ys = [row["Depth y (mm)"] for row in strain_rows]
        eps_vals = [row["ε"] for row in strain_rows]
        ax_eps.plot(eps_vals, ys, marker="o")
        ax_eps.axhline(dn_sls, linestyle="--", linewidth=0.8, color="black")
        ax_eps.set_xlabel("Strain ε")
        ax_eps.set_ylabel("Depth from top (mm)")
        ax_eps.set_title("SLS strain distribution")
        ax_eps.invert_yaxis()
        ax_eps.grid(True, linewidth=0.3)
        st.pyplot(fig_eps, use_container_width=True)
        plt.close(fig_eps)

    st.markdown("---")

    # --------------------------------------------------
    # 3.6 Steel stresses at SLS (each layer)
    # --------------------------------------------------
    st.subheader("3.6 Steel stresses at SLS")

    steel_rows = []

    # tension layers
    for layer in layers_tension:
        eps_s = kappa * (layer["y"] - dn_sls)
        fs = Es * eps_s  # MPa
        steel_rows.append(
            {
                "Layer": layer["name"],
                "Description": layer["label"],
                "Depth y (mm)": layer["y"],
                "ε_s": eps_s,
                "f_s (MPa)": fs,
            }
        )

    # compression layer (if any)
    if include_comp and comp_layer is not None:
        eps_s_c = kappa * (comp_layer["y"] - dn_sls)
        fs_c = Es * eps_s_c
        steel_rows.append(
            {
                "Layer": comp_layer["name"],
                "Description": comp_layer["label"],
                "Depth y (mm)": comp_layer["y"],
                "ε_s": eps_s_c,
                "f_s (MPa)": fs_c,
            }
        )

    df_steel = pd.DataFrame(steel_rows)

    calcbox(
        f"""
*Purpose: Derive steel stresses at SLS for each reinforcement layer.*  

**Formulae:**

Steel strain in each layer is:

$$
\\varepsilon_{{s,i}} = \\kappa (d_i - d_n)
$$

and the corresponding stress is:

$$
f_{{s,i}} = E_s\\, \\varepsilon_{{s,i}}
$$

The table below lists $\\varepsilon_{{s,i}}$ and $f_{{s,i}}$ for each steel layer.

---

**Result:**  
See table for layer-by-layer SLS steel strains and stresses.
"""
    )
    st.table(df_steel)
    st.markdown("---")

    # --------------------------------------------------
    # 3.7 Link to crack-width calculation
    # --------------------------------------------------
    st.subheader("3.7 SLS steel stress used in crack-width checks")

    # OUTERMOST tension layer (deepest y) with positive stress
    fs_tension = None
    if steel_rows:
        deepest = max(
            (row for row in steel_rows if row["f_s (MPa)"] > 0.0),
            key=lambda row: row["Depth y (mm)"],
            default=None,
        )
        if deepest is not None:
            fs_tension = deepest["f_s (MPa)"]

    if fs_tension is not None:
        calcbox(
            f"""
*Purpose: Identify the controlling SLS steel stress for use in crack-width checks.*  

The **critical tension steel stress** at SLS is taken as the stress in the
**outermost tension layer**.

From the table above, this is approximately:

$$
f_{{s,ser}} \\approx {fs_tension:.1f}\\ \\text{{MPa}}
$$

---

**Result:**  
Use $f_{{s,ser}} \\approx {fs_tension:.1f}$ MPa in crack-width calculations on the Crack Width tab.
"""
        )
    else:
        st.info(
            "No tension layer found for crack-width link – check the SLS inputs."
        )
