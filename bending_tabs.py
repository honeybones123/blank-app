# bending_tabs.py
import math
import pandas as pd
import matplotlib.pyplot as plt
import streamlit as st

from widgets_helpers import calcbox
from bending_diagrams import _make_uls_stress_block_figure
from bending_core import _fmt


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
            # 1.1: show α2 f'c, but NO d_n line
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
                show_dn=False,          # hide d_n here
                show_alpha_label=True,  # keep α2 f'c
            )
            st.pyplot(fig_uls_11, use_container_width=True)

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
            # 1.3: geometry figure – show d_n & z, but NO α2 f'c text
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
                show_lever_arm=True,      # shows z
                show_dn=True,             # keep d_n
                show_alpha_label=False,   # remove α2 f'c label
            )
            st.pyplot(fig_uls_13, use_container_width=True)

        st.markdown("---")

        # 1.4 Moment capacity
        st.subheader("1.4 Nominal and design moment capacity")
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
        st.markdown("---")

    else:
        st.info("Capacity cannot be evaluated – check geometry / reo inputs.")


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
$$
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


def render_sls_tab(top_results, b, D, d, Ast, Ec, Es, Mu_star):
    """
    Tab 3 – SLS cracked-section teaching model.
    """
    st.header("3. SLS Bending – Cracked Section (Teaching Model)")

    if d and Ast and Ec and Es and b and D and Mu_star is not None:
        Ms = Mu_star

        # 3.1 Modular ratio
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
$$
"""
        )

        # 3.2 Neutral axis depth
        st.subheader("3.2 Neutral axis depth $d_n$ (cracked section)")
        a_quad = 0.5 * b
        n_sls = Es / Ec if Ec else 0.0
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

$$
\frac{{b d_n^2}}{2} = n A_s (d - d_n)
$$

Solving this quadratic for $d_n$ gives:

$$
d_n = {dn_sls:.2f}\ \text{{mm}}
$$
"""
        )

        # 3.3 Cracked I
        st.subheader("3.3 Cracked moment of inertia $I_{{cr}}$")
        Icr = b * dn_sls**3 / 3.0 + n_sls * Ast * (d - dn_sls) ** 2
        calcbox(
            rf"""
Cracked moment of inertia:

$$
I_{{cr}} = \frac{{b d_n^3}}{3} + n A_s (d - d_n)^2
$$

Substituting:

$$
I_{{cr}} = \frac{{{b:.1f} \times {dn_sls:.2f}^3}}{3}
        + {n_sls:.2f} \times {Ast:.1f} ( {d:.1f} - {dn_sls:.2f} )^2
        = {Icr:,.2f}\ \text{{mm}}^4
$$
"""
        )

        # 3.4 Curvature
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

        # 3.5 Strain distribution + figure on the right
        st.subheader("3.5 Strain distribution $\\varepsilon(y) = \\kappa (y - d_n)$")

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
        df_eps = pd.DataFrame(strain_rows)

        col_sls_calc, col_sls_fig = st.columns([2, 1])

        with col_sls_calc:
            calcbox(
                rf"""
Strain at depth $y$ from the top:

$$
\varepsilon(y) = \kappa (y - d_n)
$$

For key layers:

- Top fibre: $y = 0$  
- Tension steel: $y = d = {d:.1f}\,\text{{mm}}$  
- Bottom fibre: $y = D = {D:.1f}\,\text{{mm}}$

The table below lists the computed strains.
"""
            )
            st.table(df_eps)

        with col_sls_fig:
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
