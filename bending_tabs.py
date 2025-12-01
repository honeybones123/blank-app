import math
import pandas as pd
import matplotlib.pyplot as plt
import streamlit as st

from widgets_helpers import calcbox
from bending_diagrams import (
    _plot_stress_strain_profiles,
    _make_uls_stress_block_figure,
    _make_uls_force_model_figure,
    _make_sls_stress_block_figure,
)
from bending_core import _fmt

# ============================================================
#  TAB 1 – ULS (UNCHANGED)
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
        # 1.2 Concrete compressive force C
        # --------------------------------------------------
        st.subheader("1.2 Concrete compressive force $C$")
        C_kN = C_N / 1000.0 if C_N is not None else float("nan")

        col_calc_12, col_fig_12 = st.columns([2, 1])

        with col_calc_12:
            calcbox(
                rf"""
Resultant concrete compression is taken as:

$$
C = \alpha_2 f'_c \, b \, a
$$

with block depth

$$
a = \gamma d_n
$$

Using the ULS stress-block parameters:

$$
C = \alpha_2 f'_c \, b \, a
  = {alpha2_uls:.3f} \times {fc:.1f} \times {b:.1f} \times {a_uls:.1f}
  = {C_kN:.1f}\ \text{{kN}}
$$

This force acts at the centroid of the compression block.
"""
            )

        # SAME stress-block diagram as 1.1, but now with C arrow at the centroid
        with col_fig_12:
            fig_uls_12 = _make_uls_stress_block_figure(
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
                show_dn=False,
                show_alpha_label=True,
                show_C=True,        # show C arrow in 1.2
                C_N=C_N,
                variant="11",
            )
            st.pyplot(fig_uls_12, use_container_width=False)

        st.markdown("---")

        # --------------------------------------------------
        # 1.3 Steel area and steel tension force T
        # --------------------------------------------------
        st.subheader("1.3 Steel area and tension force $T$")

        col_calc_13, col_fig_13 = st.columns([2, 1])

        with col_calc_13:
            calcbox(
                rf"""
From the section inputs, the total area of bottom tensile steel is:

$$
A_{{st}} = {Ast:.1f}\ \text{{mm}}^2
$$

Assuming the tension steel yields at $f_{{sy}}$:

$$
T = A_{{st}} f_{{sy}}
$$

Substituting:

$$
T = {Ast:.1f} \times {fsy:.1f}
  = {T:,.0f}\ \text{{N}}
  = {T/1000.0:.1f}\ \text{{kN}}
"""
            )

        # SAME style stress-block diagram as 1.1 (no C arrow here)
        with col_fig_13:
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
                show_lever_arm=False,
                show_dn=False,
                show_alpha_label=True,
                show_C=False,   # no C arrow in 1.3, just like 1.1
                C_N=None,
                variant="11",
            )
            st.pyplot(fig_uls_13, use_container_width=False)

        st.markdown("---")

        # --------------------------------------------------
        # 1.4 Neutral axis depth d_n and block depth a
        # --------------------------------------------------
        st.subheader("1.4 Neutral axis depth $d_n$ and block depth $a$")

        col_calc_14, col_fig_14 = st.columns([2, 1])

        with col_calc_14:
            calcbox(
                rf"""
Equilibrium of internal forces requires:

$$
C = T
$$

Using the rectangular stress block:

$$
C = \alpha_2 f'_c\, b\, \gamma d_n
$$

So, setting $C = T$:

$$
\alpha_2 f'_c\, b\, \gamma d_n = T
$$

Rearranging:

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
            rf"""
A convenient non-dimensional measure of the neutral axis depth is:

$$
k_u = \frac{{d_n}}{{d}}
$$

Substituting:

$$
k_u = \frac{{{dn:.1f}}}{{{d:.1f}}}
    = {ku:.3f}
$$

This ratio shows how deep the neutral axis is relative to the
effective depth of the tension steel.
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
                rf"""
Lever arm between compression and tension resultants:

$$
z = d - \frac{{a}}{2}
$$

Substituting:

$$
z = d - \frac{{a}}{{2}}
  = {d:.1f} - \frac{{{a_uls:.1f}}}{{2}}
  = {z_uls:.1f}\ \text{{mm}}
$$

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
#  TAB 2 – Minimum Strength (UNCHANGED)
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
        rf"""
AS 3600-style expression for flexural tensile strength:

$$
f_{{ct,f}} \approx 0.6 \sqrt{{f'_c}}
$$

Substituting:

$$
f_{{ct,f}} \approx 0.6 \sqrt{{{fc:.1f}}}
          = {fctf_as:.3f}\ \text{{MPa}}
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
"""
    )
    st.markdown("---")


# ============================================================
#  TAB 3 – SLS (UPDATED WITH 3.6 & 3.7, LAYERS, COMP STEEL)
# ============================================================
def render_sls_tab(top_results, b, D, d, Ast, Ec, Es, Mu_star):
    """
    Tab 3 – SLS cracked-section teaching model.
    Uses a layered steel model (bottom layer + optional compression steel).
    """
    st.header("3. SLS Bending – Cracked Section (Teaching Model)")

    if not (d and Ast and Ec and Es and b and D and Mu_star is not None):
        st.info("Not enough information to run SLS cracked-section example.")
        return

    Ms = Mu_star  # service moment (kNm)

    # --------------------------------------------------
    #  Build steel layers
    # --------------------------------------------------
    # Bottom tension layer (always present)
    layers_tension = [
        {
            "name": "T1",
            "label": "Bottom tension steel",
            "y": d,
            "As": Ast,
        }
    ]

    # Candidate compression layer from top bars (if present in session_state)
    nb_top = st.session_state.get("nb_top", 0) or 0
    db_top = st.session_state.get("db_top", 0.0) or 0.0
    cover_top = st.session_state.get("cover_top", 0.0) or 0.0

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
        rf"""
Modular ratio:

$$
n = \frac{{E_s}}{{E_c}}
$$

Substituting:

$$
n = \frac{{{Es:.0f}}}{{{Ec:.0f}}}
  = {Es/Ec:.2f}
"""
    )

    # Table of steel layers (transformed areas)
    layer_rows = []
    for layer in layers_tension:
        As = layer["As"]
        layer_rows.append(
            {
                "Layer": layer["name"],
                "Description": layer["label"],
                "Depth y (mm)": layer["y"],
                "A_s (mm²)": As,
                "n A_s (mm²)": n_sls * As,
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
    # 3.2 Neutral axis depth d_n (cracked section)
    # --------------------------------------------------
    st.subheader("3.2 Neutral axis depth $d_n$ (cracked section)")

    def equilibrium_residual(dn: float) -> float:
        """C(dn) - T(dn) = 0 for cracked section."""
        # Concrete compression resultant
        C_conc = 0.5 * b * dn**2  # mm² * mm → N / n factor is outside

        # Steel contributions (transformed)
        T_steel = 0.0
        # tension layers
        for layer in layers_tension:
            As = layer["As"]
            y = layer["y"]
            if y > dn:
                T_steel += n_sls * As * (y - dn)
            else:
                # if a "tension" layer ever ends up above NA, treat as compression
                C_conc += n_sls * As * (dn - y)

        # optional compression layer
        if include_comp and comp_layer is not None:
            As_c = comp_layer["As"]
            y_c = comp_layer["y"]
            if y_c < dn:
                C_conc += n_sls * As_c * (dn - y_c)
            else:
                T_steel += n_sls * As_c * (y_c - dn)

        # Concrete is already in N-equivalent units under transformed method
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

    calcbox(
        rf"""
From equilibrium of transformed areas:

Tension side:

$$
T = \sum n A_{{s,i}} (d_i - d_n)
$$

Concrete (and any compression steel) provide compression $C$ so that:

$$
\frac{{b d_n^2}}{2} + \sum n A_{{s,c}} (d_n - d_{{s,c}}) = \sum n A_{{s,i}} (d_i - d_n)
$$

Solving this equilibrium numerically for this section gives:

$$
d_n = {dn_sls:.2f}\ \text{{mm}}
$$
"""
    )

    st.markdown("---")

    # --------------------------------------------------
    # 3.3 Cracked moment of inertia I_cr + SLS section figure
    # --------------------------------------------------
    st.subheader("3.3 Cracked moment of inertia $I_{{cr}}$")

    # Classify compression / tension for Icr based on dn_sls
    I_conc = b * dn_sls**3 / 3.0
    I_t = 0.0
    I_c = 0.0

    for layer in layers_tension:
        As = layer["As"]
        y = layer["y"]
        if y >= dn_sls:
            I_t += n_sls * As * (y - dn_sls) ** 2
        else:
            I_c += n_sls * As * (dn_sls - y) ** 2

    if include_comp and comp_layer is not None:
        As_c = comp_layer["As"]
        y_c = comp_layer["y"]
        if y_c < dn_sls:
            I_c += n_sls * As_c * (dn_sls - y_c) ** 2
        else:
            I_t += n_sls * As_c * (y_c - dn_sls) ** 2

    Icr = I_conc + I_t + I_c

    col_I_calc, col_I_fig = st.columns([2, 1])

    with col_I_calc:
        calcbox(
            rf"""
Cracked moment of inertia (transformed section):

$$
I_{{cr}} =
\frac{{b d_n^3}}{3}
+ \sum n A_{{s,i}} (d_i - d_n)^2
+ \sum n A_{{s,c}} (d_n - d_{{s,c}})^2
$$

For this section:

- Concrete term: $\dfrac{{b d_n^3}}{3} = {_fmt(I_conc)}\ \text{{mm}}^4$  
- Steel in tension: $\sum n A_{{s,i}} (d_i - d_n)^2 = {_fmt(I_t)}\ \text{{mm}}^4$  
- Steel in compression: $\sum n A_{{s,c}} (d_n - d_{{s,c}})^2 = {_fmt(I_c)}\ \text{{mm}}^4$

So:

$$
I_{{cr}} = {Icr:,.2f}\ \text{{mm}}^4
$$
"""
        )

    with col_I_fig:
        # Simple cracked-section figure with NA, block, and steel layers
        fig_sec, ax_sec = plt.subplots(figsize=(3.0, 2.6))
        ax_sec.set_xlim(0.0, b * 1.3 if b > 0 else 100.0)
        ax_sec.set_ylim(D * 1.05, -0.05 * D)
        ax_sec.axis("off")

        # Section outline
        ax_sec.plot([0, b, b, 0, 0], [0, 0, D, D, 0], "k-", linewidth=1.0)

        # NA line
        ax_sec.axhline(dn_sls, linestyle="--", linewidth=0.8, color="black")

        # Simple triangular compression block above d_n (elastic SLS idea)
        ax_sec.fill(
            [0, 0, b],
            [dn_sls, 0.0, dn_sls],
            facecolor="#c7e3ff",
            edgecolor="tab:red",
            linewidth=0.8,
            alpha=0.6,
        )

        # Plot steel layers
        for layer in layers_tension:
            y = layer["y"]
            ax_sec.plot(
                [0.15 * b, 0.85 * b],
                [y, y],
                color="tab:blue",
                linewidth=1.2,
            )
            ax_sec.text(
                0.9 * b,
                y,
                layer["name"],
                fontsize=7,
                va="center",
                color="tab:blue",
            )

        if include_comp and comp_layer is not None:
            y_c = comp_layer["y"]
            ax_sec.plot(
                [0.15 * b, 0.85 * b],
                [y_c, y_c],
                color="tab:red",
                linewidth=1.2,
            )
            ax_sec.text(
                0.9 * b,
                y_c,
                comp_layer["name"],
                fontsize=7,
                va="center",
                color="tab:red",
            )

        ax_sec.set_title("Cracked SLS section", fontsize=8)
        st.pyplot(fig_sec, use_container_width=False)
        plt.close(fig_sec)

    st.markdown("---")

    # --------------------------------------------------
    # 3.4 Curvature at service moment
    # --------------------------------------------------
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
            rf"""
Strain at depth $y$ from the top:

$$
\varepsilon(y) = \kappa (y - d_n)
$$

For key layers (including each steel layer), the table lists:

- Depth $y$  
- Strain $\varepsilon(y)$
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
    # 3.6 Steel stresses at SLS
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
        rf"""
Steel strain in each layer is:

$$
\varepsilon_{{s,i}} = \kappa (d_i - d_n)
$$

and the corresponding stress is:

$$
f_{{s,i}} = E_s\, \varepsilon_{{s,i}}
$$

The table below lists $\varepsilon_{{s,i}}$ and $f_{{s,i}}$ for each steel layer.
"""
    )
    st.table(df_steel)
    st.markdown("---")

    # --------------------------------------------------
    # 3.7 Link to crack-width calculation
    # --------------------------------------------------
    st.subheader("3.7 SLS steel stress used in crack-width checks")

    # Take the bottom-most tension layer as the controlling one for cracking
    fs_tension = None
    if steel_rows:
        # sort by depth; deepest layer is usually crack-critical
        deepest = max(
            steel_rows,
            key=lambda row: row["Depth y (mm)"],
        )
        fs_tension = deepest["f_s (MPa)"]

    if fs_tension is not None:
        calcbox(
            rf"""
For crack-width calculations, the **critical tension steel stress** at SLS
is typically taken as the stress in the deepest tension layer.

From the table above, this is approximately:

$$
f_{{s,ser}} \approx {fs_tension:.1f}\ \text{{MPa}}
$$

This is the value you would use in the crack-control checks
(e.g. on the Crack Width tab) when relating steel stress to crack width.
"""
        )
    else:
        st.info(
            "No tension layer found for crack-width link – check the SLS inputs."
        )
