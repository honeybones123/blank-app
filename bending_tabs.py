# bending_tabs.py
import math
import pandas as pd
import matplotlib.pyplot as plt
import streamlit as st

from widgets_helpers import calcbox
from bending_diagrams import (
    _make_uls_stress_block_figure,
    _make_uls_force_model_figure,
)
from bending_core import _fmt, _layout_bars_in_rows
from state_and_helpers import get_param


# ============================================================
#  HELPERS FOR SLS (multi-layer steel, up to 2 rows each face)
# ============================================================


def _build_sls_steel_layers(b: float, D: float):
    """
    Build steel layers (up to 2 rows top + 2 rows bottom) using the
    SAME geometry rules as the section diagram.

    Returns a list of dicts:
        {
          "label": "Bottom row 1",
          "As":    <mm^2>,
          "y":     <depth from top in mm>,
        }
    """

    layers = []

    # -----------------------
    # Bottom steel (tension)
    # -----------------------
    nb_bot = int(get_param("nb_bot") or 0)
    db_bot = get_param("db_bot") or 0.0
    cover_bot = get_param("cover_bot") or 0.0
    rowgap_bot = get_param("rowgap_bot") or 25.0

    if nb_bot > 0 and db_bot > 0 and b and D:
        area_bar_bot = math.pi * (db_bot**2) / 4.0
        min_spacing_bot = 2.0 * db_bot

        layout_bot = _layout_bars_in_rows(
            nb_bot, b, cover_bot, db_bot, min_spacing_bot, 2
        )
        # Count bars per row index (0, 1)
        row_counts_bot = {}
        for _, row_idx in layout_bot:
            row_counts_bot[row_idx] = row_counts_bot.get(row_idx, 0) + 1

        r_bot = db_bot / 2.0
        row_pitch_bot = db_bot + rowgap_bot
        y_row0 = D - cover_bot - r_bot

        for row_idx, count in row_counts_bot.items():
            y_layer = y_row0 - row_idx * row_pitch_bot
            As_layer = count * area_bar_bot
            layers.append(
                {
                    "label": f"Bottom row {row_idx + 1}",
                    "As": As_layer,
                    "y": y_layer,
                }
            )

    # -----------------------
    # Top steel (compression side)
    # -----------------------
    nb_top = int(get_param("nb_top") or 0)
    db_top = get_param("db_top") or 0.0
    cover_top = get_param("cover_top") or 0.0
    rowgap_top = get_param("rowgap_top") or 25.0

    if nb_top > 0 and db_top > 0 and b and D:
        area_bar_top = math.pi * (db_top**2) / 4.0
        min_spacing_top = 2.0 * db_top

        layout_top = _layout_bars_in_rows(
            nb_top, b, cover_top, db_top, min_spacing_top, 2
        )
        row_counts_top = {}
        for _, row_idx in layout_top:
            row_counts_top[row_idx] = row_counts_top.get(row_idx, 0) + 1

        r_top = db_top / 2.0
        row_pitch_top = db_top + rowgap_top
        y_top0 = cover_top + r_top

        for row_idx, count in row_counts_top.items():
            y_layer = y_top0 + row_idx * row_pitch_top
            As_layer = count * area_bar_top
            layers.append(
                {
                    "label": f"Top row {row_idx + 1}",
                    "As": As_layer,
                    "y": y_layer,
                }
            )

    # Sort by depth from top (just for neatness)
    layers.sort(key=lambda L: L["y"])
    return layers


def _solve_dn_sls(b: float, D: float, layers, n_sls: float, include_comp: bool):
    """
    Solve for SLS neutral axis depth d_n using transformed-section equilibrium:

        0.5 * b * d_n^2
      + Σ (n A_s,comp (d_n - y_i))
      = Σ (n A_s,tens (y_i - d_n))

    If include_comp=False, compression steel is ignored.
    """

    if not layers or n_sls <= 0.0 or b <= 0.0 or D <= 0.0:
        return None

    def F(dn):
        # guard
        if dn <= 1e-6 or dn >= D - 1e-6:
            return 1e9

        # concrete triangle (area b*dn, centroid at dn/2)
        C_conc = 0.5 * b * dn**2

        C_steel = 0.0
        T_steel = 0.0

        for layer in layers:
            As = layer["As"]
            y = layer["y"]
            if y < dn:
                # compression steel
                if include_comp:
                    C_steel += n_sls * As * (dn - y)
            elif y > dn:
                # tension steel
                T_steel += n_sls * As * (y - dn)
            # y == dn → zero force / moment contribution

        return C_conc + C_steel - T_steel

    # Bisection between small >0 and just below D
    lo = 1e-6
    hi = D - 1e-6
    flo = F(lo)
    fhi = F(hi)

    # If no sign change, bail out → caller will fall back
    if flo * fhi > 0:
        return None

    for _ in range(60):
        mid = 0.5 * (lo + hi)
        fmid = F(mid)
        if abs(fmid) < 1e-6:
            return mid
        if flo * fmid <= 0:
            hi, fhi = mid, fmid
        else:
            lo, flo = mid, fmid

    return 0.5 * (lo + hi)


# ============================================================
#  ULS TAB
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
        T = Ast * fsy
        denom_uls = alpha2_uls * fc * b * gamma_uls
        dn = T / denom_uls if denom_uls > 0 else float("nan")
        a_uls = gamma_uls * dn
        z_uls = d - 0.5 * a_uls
        Mu_nom_uls = T * z_uls / 1e6
        phi_Mu_cap_uls = phi * Mu_nom_uls

        # 1.1 Stress-block parameters (α2 and γ) + FIGURE ON RIGHT
        st.subheader("1.1 Stress-block parameters (α₂ and γ)")
        col_calc, col_fig = st.columns([2, 1])

        with col_calc:
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

        with col_fig:
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
                show_dn=False,  # no d_n for 1.1
                show_alpha_label=True,  # α2 f'c width annotation
                variant="11",
            )
            st.pyplot(fig_uls_11, use_container_width=False)

        st.markdown("---")

        # 1.2 Steel force
        st.subheader("1.2 Steel force in tension")
        calcbox(
            rf"""
Assuming the tension steel yields:

$$
T = A_{{st}} f_{{sy}}
$$

Substituting:

$$
T = {Ast:.1f} \times {fsy:.1f}
  = {T:,.0f}\ \text{{N}}
$$
"""
        )
        st.markdown("---")

        # 1.3 Neutral axis depth + FIGURE ON RIGHT (with z)
        st.subheader("1.3 Neutral axis depth $d_n$ and lever arm $z$")

        col_calc_13, col_fig_13 = st.columns([2, 1])

        with col_calc_13:
            calcbox(
                rf"""
Equilibrium of internal forces:

$$
\alpha_2 f'_c\, b\, \gamma d_n = T
$$

So:

$$
d_n = \frac{{T}}{{\alpha_2 f'_c\, b\, \gamma}}
$$

Substituting:

$$
d_n =
\frac{{{T:,.0f}}}
     {{ {alpha2_uls:.3f} \times {fc:.1f} \times {b:.1f} \times {gamma_uls:.3f} }}
= {dn:.1f}\ \text{{mm}}
$$

Block depth:

$$
a = \gamma d_n = {gamma_uls:.3f} \times {dn:.1f}
  = {a_uls:.1f}\ \text{{mm}}
$$

Lever arm:

$$
z = d - \frac{{a}}{2}
  = {d:.1f} - \frac{{{a_uls:.1f}}}{2}
  = {z_uls:.1f}\ \text{{mm}}
$$
"""
            )

        with col_fig_13:
            # Variant "13": taller to match this calc box.
            fig_uls_13 = _make_uls_stress_block_figure(
                b_mm=b or 0.0,
                D_mm=D or 0.0,
                d_mm=d,
                dn_mm=dn,
                a_mm=a_uls,
                alpha2=alpha2_uls,
                gamma=gamma_uls,
                fc=fc,
                fsy=fsy,
                show_lever_arm=True,   # show z
                show_dn=True,          # show d_n
                show_alpha_label=True,  # α2 f'c annotation
                variant="13",
            )
            st.pyplot(fig_uls_13, use_container_width=False)

        st.markdown("---")

        # 1.4 Moment capacity + force model figure
        st.subheader("1.4 Nominal and design moment capacity")

        col_calc_14, col_fig_14 = st.columns([2, 1])

        with col_calc_14:
            calcbox(
                rf"""
Nominal moment:

$$
M_u = \frac{{T z}}{{10^6}}
$$

$$
M_u = \frac{{{T:,.0f} \times {z_uls:.1f}}}{{10^6}}
    = {Mu_nom_uls:.2f}\ \text{{kNm}}
$$

Design moment:

$$
\phi M_{{u,cap}} = \phi M_u
               = {phi:.2f} \times {Mu_nom_uls:.2f}
               = {phi_Mu_cap_uls:.2f}\ \text{{kNm}}
$$
"""
            )

        with col_fig_14:
            fig_uls_14 = _make_uls_force_model_figure(
                D_mm=D or 0.0,
                d_mm=d,
                a_mm=a_uls,
            )
            st.pyplot(fig_uls_14, use_container_width=False)

        st.markdown("---")

    else:
        st.info("Capacity cannot be evaluated – check geometry / reo inputs.")


# ============================================================
#  MINIMUM STRENGTH TAB (unchanged – fill with your existing code)
# ============================================================


def render_min_strength_tab(top_results, b, D, fc, fsy, Ast):
    """
    Tab 2 – Minimum strength requirements.
    (Keep your existing implementation here.)
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
        rf"""
AS 3600-style expression for flexural tensile strength:

$$
f_{{ct,f}} \approx 0.6 \sqrt{{f'_c}}
$$

Substituting:

$$
f_{{ct,f}} \approx 0.6 \sqrt{{{fc:.1f}}}
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
Z_g = \frac{{b D^2}}{{6}}
$$

Substituting:

$$
Z_g = \frac{{{b:.1f} \times {D:.1f}^2}}{{6}}
    = {Zg:,.3e}\ \text{{mm}}^3
$$
"""
    )
    st.markdown("---")

    # 2.3 M_cr
    st.subheader("2.3 Cracking moment $M_{{cr}}$")
    calcbox(
        rf"""
Cracking moment:

$$
M_{{cr}} = \frac{{f_{{ct,f}} Z_g}}{{10^6}}
$$

Substituting:

$$
M_{{cr}} = \frac{{{fctf_as:.3f} \times {Zg:,.3e}}}{{10^6}}
       = {Mcr_as:.2f}\ \text{{kNm}}
"""
    )
    st.markdown("---")

    # 2.4 Minimum required capacity (1.2 Mcr)
    st.subheader("2.4 Minimum required design capacity $(M_{{u,cap}})_{{min}}$")
    calcbox(
        rf"""
To ensure post-cracking behaviour:

$$
(M_{{u,cap}})_{{min}} = 1.2\, M_{{cr}}
$$

Substituting:

$$
(M_{{u,cap}})_{{min}}
= 1.2 \times {Mcr_as:.2f}
= {Mu_min_as:.2f}\ \text{{kNm}}
$$

Meaning the design ultimate strength must exceed
**1.2 × cracking moment**.
"""
    )
    st.markdown("---")

    # 2.5 Minimum tensile reinforcement
    st.subheader("2.5 Minimum tensile reinforcement $A_{{st,min}}$")
    calcbox(
        rf"""
AS 3600-style minimum tensile reinforcement:

$$
A_{{st,min}}
= 0.4\;\frac{{f_{{ct,f}}}}{{f_{{sy}}}}\; b d
$$

Substituting:

$$
A_{{st,min}}
= 0.4 \times \frac{{{fctf_as:.3f}}}{{{fsy:.1f}}}
\times {b:.1f} \times {top_results['d']:.1f}
= {Ast_min_as:.1f}\ \text{{mm}}^2
$$

Compare:

$$
A_{{st}} = {Ast:.1f}\ \text{{mm}}^2
\qquad\text{{vs.}}\qquad
A_{{st,min}} = {Ast_min_as:.1f}\ \text{{mm}}^2
$$
"""
    )
    st.markdown("---")


# ============================================================
#  SLS TAB – upgraded multi-layer logic
# ============================================================


def render_sls_tab(top_results, b, D, d, Ast, Ec, Es, Mu_star):
    """
    Tab 3 – SLS cracked-section teaching model.
    """
    st.header("3. SLS Bending – Cracked Section (Teaching Model)")

    if not (d and Ast and Ec and Es and b and D and Mu_star is not None):
        st.info("Not enough information to run SLS cracked-section example.")
        return

    Ms = Mu_star

    # Option to include or ignore compression steel
    include_comp = st.checkbox(
        "Include compression steel in SLS equilibrium?",
        value=False,
        help="Tick to include top steel rows in SLS cracked-section calculations.",
    )

    # -------------------------------
    # 3.1 Modular ratio
    # -------------------------------
    st.subheader("3.1 Modular ratio $n = E_s / E_c$")
    n_sls = Es / Ec if Ec else 0.0

    calcbox(
        rf"""
Modular ratio:

$$
n = \frac{{E_s}}{{E_c}}
$$

Substituting:

$$
n = \frac{{{Es:.0f}}}{{{Ec:.0f}}}
  = {n_sls:.2f}
$$
"""
    )
    st.markdown("---")

    # -------------------------------
    # 3.2 Neutral axis depth with multi-layer steel
    # -------------------------------
    st.subheader("3.2 Neutral axis depth $d_n$ (cracked section)")

    # Build steel layers (up to 2 rows each face)
    layers = _build_sls_steel_layers(b, D)

    dn_sls = _solve_dn_sls(b, D, layers, n_sls, include_comp)

    # Fallback: old single-layer formula if solver fails
    if dn_sls is None:
        a_quad = 0.5 * b
        b_coef = n_sls * Ast
        c_coef = -n_sls * Ast * d
        dn_sls = float("nan")
        if a_quad != 0.0:
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

        dn_text = rf"""
Using classical single-layer equilibrium:

$$
\frac{{b d_n^2}}{2} = n A_s (d - d_n)
$$

Solving gives:

$$
d_n = {dn_sls:.2f}\ \text{{mm}}
$$
"""
    else:
        dn_text = rf"""
From equilibrium of transformed areas:

$$
\frac{{b d_n^2}}{2}
+ \sum (n A_{{s,\mathrm{{comp}}}} (d_n - y_i))
= \sum (n A_{{s,\mathrm{{tens}}}} (y_i - d_n))
$$

Solving this numerically for the actual steel layers gives:

$$
d_n = {dn_sls:.2f}\ \text{{mm}}
$$
"""

    calcbox(dn_text)
    st.markdown("---")

    # -------------------------------
    # 3.3 Cracked moment of inertia I_cr
    # -------------------------------
    st.subheader("3.3 Cracked moment of inertia $I_{{cr}}$")

    # Concrete part
    Icr_conc = b * dn_sls**3 / 3.0

    # Steel contributions
    Icr_steel = 0.0
    for layer in layers:
        As_i = layer["As"]
        y_i = layer["y"]
        # tension always included; compression only if toggle is on
        if y_i > dn_sls or (include_comp and y_i < dn_sls):
            Icr_steel += n_sls * As_i * (y_i - dn_sls) ** 2

    Icr = Icr_conc + Icr_steel

    calcbox(
        rf"""
Cracked moment of inertia (transformed section):

$$
I_{{cr}} = \frac{{b d_n^3}}{3}
        + \sum \left( n A_s (y_i - d_n)^2 \right)
$$

Substituting:

$$
I_{{cr}} = \frac{{{b:.1f} \times {dn_sls:.2f}^3}}{3}
        + \sum \left( {n_sls:.2f} A_s (y_i - {dn_sls:.2f})^2 \right)
        = {Icr:,.2f}\ \text{{mm}}^4
$$
"""
    )
    st.markdown("---")

    # -------------------------------
    # 3.4 Curvature
    # -------------------------------
    st.subheader("3.4 Curvature at service moment")
    Ms_Nmm = Ms * 1e6
    kappa = Ms_Nmm / (Ec * Icr) if Ec and Icr else 0.0

    calcbox(
        rf"""
Using $M_s$ as the service moment:

$$
\kappa = \frac{{M_s}}{{E_c I_{{cr}}}}
$$

Substituting:

$$
\kappa = \frac{{{Ms:.2f}\times 10^6}}{{{Ec:.0f} \times {Icr:,.2f}}}
       = {kappa:.3e}\ \text{{mm}}^{{-1}}
$$
"""
    )
    st.markdown("---")

    # -------------------------------
    # 3.5 Strain distribution + figure
    # -------------------------------
    st.subheader("3.5 Strain distribution $\\varepsilon(y) = \\kappa (y - d_n)$")

    # Build table of key layers
    strain_rows = []

    # Top fibre
    eps_top = kappa * (0.0 - dn_sls)
    strain_rows.append(
        {
            "Layer": "Top fibre",
            "Depth y (mm)": 0.0,
            "ε": eps_top,
            "Role": "Concrete (top)",
        }
    )

    # Steel layers
    for layer in layers:
        y_i = layer["y"]
        eps_i = kappa * (y_i - dn_sls)
        role = "Tension steel" if y_i > dn_sls else "Compression steel"
        if role == "Compression steel" and not include_comp:
            role += " (ignored in equilibrium)"
        strain_rows.append(
            {
                "Layer": layer["label"],
                "Depth y (mm)": y_i,
                "ε": eps_i,
                "Role": role,
            }
        )

    # Bottom fibre
    eps_bot = kappa * (D - dn_sls)
    strain_rows.append(
        {
            "Layer": "Bottom fibre",
            "Depth y (mm)": D,
            "ε": eps_bot,
            "Role": "Concrete (bottom)",
        }
    )

    df_eps = pd.DataFrame(strain_rows)

    col_sls_calc, col_sls_fig = st.columns([2, 1])

    with col_sls_calc:
        calcbox(
            rf"""
Strain at depth $y$ from the top:

$$
\varepsilon(y) = \kappa (y - d_n)
$$

- Neutral axis at $d_n = {dn_sls:.2f}\,\text{{mm}}$  
- Steel layers taken from the actual reinforcement layout  
- Compression steel {'is' if include_comp else 'is not'} included in equilibrium

The table below lists the computed strains.
"""
        )
        st.table(df_eps)

    with col_sls_fig:
        # Simple linear profile plus markers for each steel layer
        fig_eps, ax_eps = plt.subplots(figsize=(3.0, 3.0))
        ys = [0.0, dn_sls, D]
        eps_vals = [kappa * (y - dn_sls) for y in ys]

        ax_eps.plot(eps_vals, ys, marker="o")
        ax_eps.axhline(dn_sls, linestyle="--", linewidth=0.8)

        # Mark steel layers
        for layer in layers:
            y_i = layer["y"]
            eps_i = kappa * (y_i - dn_sls)
            ax_eps.plot([eps_i], [y_i], marker="s")
            ax_eps.text(
                eps_i,
                y_i,
                layer["label"],
                fontsize=6,
                va="bottom",
                ha="left",
            )

        ax_eps.set_xlabel("Strain ε")
        ax_eps.set_ylabel("Depth from top (mm)")
        ax_eps.set_title("SLS strain distribution")
        ax_eps.invert_yaxis()
        st.pyplot(fig_eps, use_container_width=True)
        plt.close(fig_eps)
