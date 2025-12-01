# bending_tabs.py
import math
import pandas as pd
import matplotlib.pyplot as plt
import streamlit as st

from widgets_helpers import calcbox
from bending_diagrams import (
    _make_uls_stress_block_figure,
    _make_uls_force_model_figure,
    _make_sls_stress_block_figure,
)
from bending_core import _fmt
from state_and_helpers import get_param


# ============================================================
#  TAB 1 – ULS STEP-BY-STEP
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

        # --------------------------------------------------
        # 1.1 Stress-block parameters (α2 and γ)
        # --------------------------------------------------
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
                show_dn=False,          # no d_n for 1.1
                show_alpha_label=True,  # α2 f'c width annotation
                variant="11",
            )
            st.pyplot(fig_uls_11, use_container_width=False)

        st.markdown("---")

        # --------------------------------------------------
        # 1.2 Steel force
        # --------------------------------------------------
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

        # --------------------------------------------------
        # 1.3 Neutral axis depth and lever arm
        # --------------------------------------------------
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
                show_lever_arm=True,     # show z
                show_dn=True,            # show d_n
                show_alpha_label=True,   # add back width / α2 f'c annotation
                variant="13",
            )
            st.pyplot(fig_uls_13, use_container_width=False)

        st.markdown("---")

        # --------------------------------------------------
        # 1.4 Moment capacity + force model figure
        # --------------------------------------------------
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
#  TAB 2 – MINIMUM STRENGTH / DESIGN ACTION CHECK
# ============================================================
def render_min_strength_tab(top_results, b, D, fc, fsy, Ast):
    """
    Tab 2 – simple minimum-strength / design-action summary.
    Can be expanded later; kept light so it doesn't clash with other logic.
    """
    st.header("2. Minimum Strength / Design Action")

    Mu_star = top_results.get("Mu_star", None)
    phi_Mu_cap = top_results.get("phi_Mu_cap", None)
    phi = top_results.get("phi", None)

    if Mu_star is None or phi_Mu_cap is None or phi is None:
        st.info("Not enough information to summarise minimum strength check.")
        return

    util = Mu_star / phi_Mu_cap if phi_Mu_cap > 0 else float("inf")

    st.subheader("2.1 Action vs Capacity")

    calcbox(
        rf"""
Factored design moment:

$$
M_u^* = {Mu_star:.2f}\ \text{{kNm}}
$$

Design capacity:

$$
\phi M_{{u,cap}} = {phi_Mu_cap:.2f}\ \text{{kNm}}
$$

Utilisation:

$$
\eta = \frac{{M_u^*}}{{\phi M_{{u,cap}}}}
     = \frac{{{Mu_star:.2f}}}{{{phi_Mu_cap:.2f}}}
     = {util:.2f}
$$
"""
    )

    status = "OK (capacity ≥ action)" if util <= 1.0 else "NG (capacity < action)"

    df = pd.DataFrame(
        {
            "Quantity": [
                "Factored moment $M_u^*$",
                "Design capacity $\phi M_{u,cap}$",
                "Utilisation $\eta$",
                "Status",
            ],
            "Value": [
                f"{Mu_star:.2f} kNm",
                f"{phi_Mu_cap:.2f} kNm",
                f"{util:.2f}",
                status,
            ],
        }
    )
    st.table(df)


# ============================================================
#  TAB 3 – SLS CRACKED-SECTION TEACHING MODEL
# ============================================================
def render_sls_tab(top_results, b, D, d, Ast, Ec, Es, Mu_star):
    """
    Tab 3 – SLS cracked-section teaching model.
    Uses tension steel at depth d and optional compression steel near the top.
    """
    st.header("3. SLS Bending – Cracked Section (Teaching Model)")

    if not (d and Ast and Ec and Es and b and D and Mu_star is not None):
        st.info("Not enough information to run SLS cracked-section example.")
        return

    Ms = Mu_star

    # --------------------------------------------------
    # Steel layer data (bottom tension + optional compression)
    # --------------------------------------------------
    Ast_t = Ast or 0.0  # bottom/tension steel (from caller)

    # Compression steel from shared state (if present)
    Ast_comp = float(get_param("Ast_top", 0.0) or 0.0)

    cover_top = float(get_param("cover_top", 40.0) or 40.0)
    db_top = float(get_param("db_top", 16.0) or 16.0)
    d_comp = cover_top + db_top / 2.0  # depth of compression steel from top

    # Toggle: include / ignore compression steel in cracked-section calcs
    include_comp = st.checkbox(
        "Include compression steel in SLS cracked-section analysis",
        value=False,
        key="sls_include_comp",
    )

    # --------------------------------------------------
    # 3.1 Modular ratio & transformed steel areas
    # --------------------------------------------------
    st.subheader("3.1 Modular ratio and transformed steel areas")

    n_sls = Es / Ec if Ec else 0.0
    Ast_t_tr = n_sls * Ast_t
    Ast_c_tr = n_sls * Ast_comp if include_comp and Ast_comp > 0.0 else 0.0

    # Table of layers
    rows = [
        {
            "Layer": "Tension steel (bottom)",
            "Depth y (mm)": d,
            "A_s (mm²)": Ast_t,
            "n A_s (mm²)": Ast_t_tr,
        }
    ]
    if include_comp and Ast_comp > 0.0:
        rows.insert(
            0,
            {
                "Layer": "Compression steel (top)",
                "Depth y (mm)": d_comp,
                "A_s (mm²)": Ast_comp,
                "n A_s (mm²)": Ast_c_tr,
            },
        )

    df_layers = pd.DataFrame(rows)

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

Each steel layer is converted to an equivalent concrete area:

$$
A_s' = n A_s
$$
"""
    )
    st.table(df_layers)

    # --------------------------------------------------
    # 3.2 Neutral axis depth d_n (cracked section)
    # --------------------------------------------------
    st.subheader("3.2 Neutral axis depth $d_n$ (cracked section)")

    a_quad = 0.5 * b
    dn_sls = float("nan")

    if a_quad > 0.0 and n_sls > 0.0 and Ast_t > 0.0:
        if include_comp and Ast_comp > 0.0:
            # b/2 * d_n^2 + n(Ast + Asc) d_n - n(Ast d + Asc d_comp) = 0
            b_coef = n_sls * (Ast_t + Ast_comp)
            c_coef = -n_sls * (Ast_t * d + Ast_comp * d_comp)
        else:
            # b/2 * d_n^2 = n Ast (d - d_n)
            # ⇒ b/2 d_n^2 + n Ast d_n - n Ast d = 0
            b_coef = n_sls * Ast_t
            c_coef = -n_sls * Ast_t * d

        disc = b_coef**2 - 4.0 * a_quad * c_coef
        if disc >= 0.0:
            r1 = (-b_coef + math.sqrt(disc)) / (2.0 * a_quad)
            r2 = (-b_coef - math.sqrt(disc)) / (2.0 * a_quad)
            roots = [r for r in (r1, r2) if 0.0 < r < D]
            if roots:
                # pick the root closest to mid-depth
                dn_sls = min(roots, key=lambda x: abs(x - D / 2.0))

    if math.isnan(dn_sls):
        dn_sls = D / 3.0  # modest fallback

    if include_comp and Ast_comp > 0.0:
        eqn_text = (
            r"""
From equilibrium of transformed areas and forces:

$$
\frac{b d_n^2}{2} + n A_{sc}(d_n - d_{sc})
= n A_{st}(d - d_n)
$$
"""
        )
    else:
        eqn_text = (
            r"""
From equilibrium of transformed areas:

$$
\frac{b d_n^2}{2} = n A_s (d - d_n)
$$
"""
        )

    calcbox(
        rf"""
{eqn_text}

Solving for $d_n$ gives:

$$
d_n = {dn_sls:.2f}\ \text{{mm}}
$$
"""
    )

    # --------------------------------------------------
    # 3.3 Cracked moment of inertia + SLS stress-block figure
    # --------------------------------------------------
    st.subheader("3.3 Cracked moment of inertia $I_{{cr}}$")

    Icr_conc = b * dn_sls**3 / 3.0
    Icr_tens = n_sls * Ast_t * (d - dn_sls) ** 2
    Icr_comp = (
        n_sls * Ast_comp * (dn_sls - d_comp) ** 2
        if include_comp and Ast_comp > 0.0
        else 0.0
    )
    Icr = Icr_conc + Icr_tens + Icr_comp

    col_I_calc, col_I_fig = st.columns([2, 1])

    with col_I_calc:
        if include_comp and Ast_comp > 0.0:
            calcbox(
                rf"""
Cracked moment of inertia:

$$
I_{{cr}} = \frac{{b d_n^3}}{3}
        + n A_{{st}} (d - d_n)^2
        + n A_{{sc}} (d_n - d_{{sc}})^2
$$

Substituting:

$$
I_{{cr}} =
\frac{{{b:.1f} \times {dn_sls:.2f}^3}}{3}
+ {n_sls:.2f} \times {Ast_t:.1f} ( {d:.1f} - {dn_sls:.2f} )^2
+ {n_sls:.2f} \times {Ast_comp:.1f} ( {dn_sls:.2f} - {d_comp:.1f} )^2
= {Icr:,.2f}\ \text{{mm}}^4
$$
"""
            )
        else:
            calcbox(
                rf"""
Cracked moment of inertia (no compression steel):

$$
I_{{cr}} = \frac{{b d_n^3}}{3} + n A_s (d - d_n)^2
$$

Substituting:

$$
I_{{cr}} =
\frac{{{b:.1f} \times {dn_sls:.2f}^3}}{3}
+ {n_sls:.2f} \times {Ast_t:.1f} ( {d:.1f} - {dn_sls:.2f} )^2
= {Icr:,.2f}\ \text{{mm}}^4
$$
"""
            )

    with col_I_fig:
        fig_sls = _make_sls_stress_block_figure(
            D_mm=D or 0.0,
            d_mm=d,
            dn_mm=dn_sls,
            include_comp=include_comp and Ast_comp > 0.0,
            d_comp_mm=d_comp if include_comp and Ast_comp > 0.0 else None,
        )
        st.pyplot(fig_sls, use_container_width=False)

    # --------------------------------------------------
    # 3.4 Curvature at service moment
    # --------------------------------------------------
    st.subheader("3.4 Curvature at service moment")

    Ms_Nmm = Ms * 1e6
    kappa = Ms_Nmm / (Ec * Icr) if Ec and Icr > 0.0 else 0.0

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

    # --------------------------------------------------
    # 3.5 Strain distribution and steel stresses
    # --------------------------------------------------
    st.subheader("3.5 Strain and steel stresses at key layers")

    layers = [
        ("Top fibre", 0.0),
    ]
    if include_comp and Ast_comp > 0.0:
        layers.append(("Compression steel", d_comp))
    layers.append(("Tension steel (d)", d))
    layers.append(("Bottom fibre", D))

    rows_eps = []
    for name, yi in layers:
        eps = kappa * (yi - dn_sls)
        fs = Es * eps  # MPa, since Es is MPa and strain is dimensionless
        rows_eps.append(
            {
                "Layer": name,
                "Depth y (mm)": yi,
                "ε": eps,
                "f_s (MPa)": fs,
            }
        )

    df_eps = pd.DataFrame(rows_eps)

    calcbox(
        rf"""
Strain at depth $y$ from the top:

$$
\varepsilon(y) = \kappa (y - d_n)
$$

Steel stress in each layer:

$$
f_s = E_s \varepsilon
$$

The table below lists the strain and stress at the top fibre, each steel layer
(and the bottom fibre).
"""
    )
    st.table(df_eps)
