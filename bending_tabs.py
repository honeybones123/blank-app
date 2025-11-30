import math
import pandas as pd
import matplotlib.pyplot as plt
import streamlit as st
from matplotlib.patches import Rectangle, Circle   # ⬅️ ADD THIS LINE

from widgets_helpers import calcbox
from bending_diagrams import (
    _make_uls_stress_block_figure,
    _make_uls_force_model_figure,
    get_sls_steel_layers,
)
from bending_core import _fmt
from state_and_helpers import get_param


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
                show_dn=False,          # no d_n for 1.1
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
                show_lever_arm=True,     # show z
                show_dn=True,            # show d_n
                show_alpha_label=True,   # add back width / α2 f'c annotation
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


# ----------------------------------------------------------------------
#  SIMPLE MINIMUM-STRENGTH TAB (keeps imports happy)
# ----------------------------------------------------------------------
def render_min_strength_tab(top_results, b, D, fc, fsy, Ast):
    """
    Tab 2 – Minimum strength / code check.

    NOTE: This is a lightweight version so the module always
    defines render_min_strength_tab (avoids ImportError).
    It just summarises the key bending results.
    """
    st.header("2. Minimum strength check")

    phi_Mu_cap = top_results.get("phi_Mu_cap")
    Mu_star = top_results.get("Mu_star") or get_param("Mu_star")

    calcbox(
        rf"""
Design capacity from ULS bending check:

- Section width: $b = {b:.1f}\ \text{{mm}}$
- Overall depth: $D = {D:.1f}\ \text{{mm}}$
- Steel yield strength: $f_{{sy}} = {fsy:.0f}\ \text{{MPa}}$

If $M^*$ is the applied design moment and
$\phi M_{{u,cap}}$ is the design bending capacity:

$$
\phi M_{{u,cap}} = {phi_Mu_cap:.2f}\ \text{{kNm}}
$$

Applied design moment:

$$
M^* = {Mu_star if Mu_star is not None else 0:.2f}\ \text{{kNm}}
$$

This tab simply compares demand and capacity; a more detailed
code-min check can be added later.
"""
    )

    data = [
        {"Quantity": "φMu,cap (kNm)", "Value": phi_Mu_cap},
        {"Quantity": "Mu* (kNm)", "Value": Mu_star},
        {"Quantity": "b (mm)", "Value": b},
        {"Quantity": "D (mm)", "Value": D},
        {"Quantity": "Ast (mm²)", "Value": Ast},
        {"Quantity": "fsy (MPa)", "Value": fsy},
        {"Quantity": "fc' (MPa)", "Value": fc},
    ]
    df = pd.DataFrame(data)
    st.table(df)


# ----------------------------------------------------------------------
#  SLS TAB – MULTI-LAYER CRACKED SECTION
# ----------------------------------------------------------------------
def render_sls_tab(top_results, b, D, d, Ast, Ec, Es, Mu_star):
    """
    Tab 3 – SLS cracked-section teaching model (multi-layer).
    """
    st.header("3. SLS Bending – Cracked Section (Teaching Model)")

    if not (d and Ast and Ec and Es and b and D and Mu_star is not None):
        st.info("Not enough information to run SLS cracked-section example.")
        return

    Ms = Mu_star

    # Steel layout from the shared bar-layout engine
    tension_layers, comp_layers_all = get_sls_steel_layers(b, D)

    # Toggle – include compression steel in section properties?
    include_comp_steel = bool(get_param("include_comp_steel") or False)
    comp_layers = comp_layers_all if include_comp_steel else []

    # Convenience – combined list for tables/plots
    all_layers = tension_layers + comp_layers

    # ------------------------------------------------------------------
    # 3.1 Service moment & section steel layout
    # ------------------------------------------------------------------
    st.subheader("3.1 Service moment and steel layout")

    col31_calc, col31_fig = st.columns([2, 1])

    with col31_calc:
        calcbox(
            rf"""
Service design moment from the main bending check:

$$
M_s = M^* = {Ms:.2f}\ \text{{kNm}}
$$

Section properties used for the cracked-section model:

- Width: $b = {b:.1f}\ \text{{mm}}$  
- Overall depth: $D = {D:.1f}\ \text{{mm}}$  

The steel is grouped into layers (rows of bars) using the same
geometry as the main section diagram.
"""
        )

        if all_layers:
            rows = []
            for layer in all_layers:
                rows.append(
                    {
                        "Layer": layer["name"],
                        "Face": "Bottom" if layer["face"] == "bottom" else "Top",
                        "Depth y (mm)": layer["y"],
                        "Bar dia (mm)": layer["db"],
                        "Count": layer["count"],
                        "A_s (mm²)": layer["As"],
                    }
                )
            df_layout = pd.DataFrame(rows)
            st.table(df_layout)
        else:
            st.info("No reinforcement layers found from current inputs.")

    with col31_fig:
        # Simple section sketch with layers (no NA yet)
        if all_layers:
            fig_sec, ax_sec = plt.subplots(figsize=(3.0, 2.8))
            ax_sec.set_xlim(0, b)
            ax_sec.set_ylim(D, 0)
            ax_sec.axis("off")

            # section
            ax_sec.add_patch(
                Rectangle((0, 0), b, D, fill=False, linewidth=1.0, edgecolor="black")
            )

            # plot layers as circles along centreline
            x_mid = 0.5 * b
            for layer in all_layers:
                y = layer["y"]
                db = layer["db"]
                count = layer["count"]
                r = db / 2.0
                if count == 1:
                    xs = [x_mid]
                else:
                    spacing = 1.2 * db
                    start = x_mid - 0.5 * (count - 1) * spacing
                    xs = [start + i * spacing for i in range(count)]
                for x in xs:
                    ax_sec.add_patch(
                        Circle(
                            (x, y),
                            radius=r,
                            fill=False,
                            linewidth=0.8,
                            edgecolor="tab:blue"
                            if layer["face"] == "bottom"
                            else "tab:red",
                        )
                    )
                ax_sec.text(
                    x_mid + 0.15 * b,
                    y,
                    layer["name"],
                    fontsize=5,
                    va="center",
                )

            ax_sec.set_title("Steel layout (SLS)", fontsize=8)
            st.pyplot(fig_sec, use_container_width=False)
            plt.close(fig_sec)

    st.markdown("---")

    # ------------------------------------------------------------------
    # 3.2 Modular ratio & transformed areas
    # ------------------------------------------------------------------
    st.subheader("3.2 Modular ratio and transformed steel areas")

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

Each steel layer is transformed to an equivalent concrete area:

$$
A'_s = n A_s
$$
"""
    )

    if all_layers:
        rows_tr = []
        for layer in all_layers:
            As = layer["As"]
            As_tr = n_sls * As
            rows_tr.append(
                {
                    "Layer": layer["name"],
                    "Face": "Bottom" if layer["face"] == "bottom" else "Top",
                    "Depth y (mm)": layer["y"],
                    "A_s (mm²)": As,
                    "A_s' = n A_s (mm²)": As_tr,
                }
            )
        df_tr = pd.DataFrame(rows_tr)
        st.table(df_tr)

    st.markdown("---")

    # ------------------------------------------------------------------
    # 3.3 Neutral axis depth d_n (multi-layer)
    # ------------------------------------------------------------------
    st.subheader("3.3 Neutral axis depth $d_n$ (cracked section)")

    # Helper: residual of force equilibrium at a trial d_n
    def _equilibrium_residual(dn_trial: float):
        # concrete compression (triangular)
        C_conc = 0.5 * b * dn_trial**2

        # compression steel contribution (if enabled)
        C_s = 0.0
        if include_comp_steel:
            for layer in comp_layers:
                if dn_trial > layer["y"]:
                    C_s += n_sls * layer["As"] * (dn_trial - layer["y"])

        # tension steel
        T_tot = 0.0
        for layer in tension_layers:
            if layer["y"] > dn_trial:
                T_tot += n_sls * layer["As"] * (layer["y"] - dn_trial)

        # equilibrium: C_conc + C_s = T_tot
        return C_conc + C_s - T_tot

    # Bisection search for root of residual = 0
    dn_sls = float("nan")
    try:
        y_min = 1e-6
        y_max = min(D - 1e-3, max([ly["y"] for ly in tension_layers] + [D]))

        f_min = _equilibrium_residual(y_min)
        f_max = _equilibrium_residual(y_max)

        if f_min * f_max < 0:
            a = y_min
            b_hi = y_max
            for _ in range(60):
                mid = 0.5 * (a + b_hi)
                f_mid = _equilibrium_residual(mid)
                if f_min * f_mid <= 0:
                    b_hi = mid
                    f_max = f_mid
                else:
                    a = mid
                    f_min = f_mid
            dn_sls = 0.5 * (a + b_hi)
        else:
            dn_sls = D / 3.0
    except Exception:
        dn_sls = D / 3.0

    ku_sls = dn_sls / d if d else float("nan")

    # Build a small forces table at the converged d_n
    C_conc = 0.5 * b * dn_sls**2
    C_s = 0.0
    if include_comp_steel:
        for layer in comp_layers:
            if dn_sls > layer["y"]:
                C_s += n_sls * layer["As"] * (dn_sls - layer["y"])
    T_tot = 0.0
    for layer in tension_layers:
        if layer["y"] > dn_sls:
            T_tot += n_sls * layer["As"] * (layer["y"] - dn_sls)

    calcbox(
        rf"""
For equilibrium of transformed forces:

- Concrete compression (triangular block):  
  $C_c = \dfrac{{b d_n^2}}{2}$

- Tension steel (sum of layers):  
  $T = \sum n A_{{s,i}} (d_i - d_n)$

If compression steel is included, additional compression is:

$$
C_s = \sum n A_{{sc,j}} (d_n - d_{{sc,j}})
$$

Equilibrium condition:

$$
C_c + C_s = T
$$

Solving numerically for $d_n$ gives:

$$
d_n = {dn_sls:.2f}\ \text{{mm}}, \qquad
k_u = \frac{{d_n}}{{d}} = {ku_sls:.3f}
$$

At this neutral axis depth:

- $C_c = {C_conc:,.0f}$ (transformed units)  
- $C_s = {C_s:,.0f}$ (if included)  
- $T   = {T_tot:,.0f}$
"""
    )

    st.markdown("---")

    # ------------------------------------------------------------------
    # 3.4 Cracked moment of inertia I_cr
    # ------------------------------------------------------------------
    st.subheader("3.4 Cracked moment of inertia $I_{{cr}}$")

    # concrete part
    I_conc = b * dn_sls**3 / 3.0

    # steel parts (about neutral axis)
    I_tension = 0.0
    for layer in tension_layers:
        if layer["y"] > dn_sls:
            I_tension += n_sls * layer["As"] * (layer["y"] - dn_sls) ** 2

    I_comp = 0.0
    if include_comp_steel:
        for layer in comp_layers:
            if dn_sls > layer["y"]:
                I_comp += n_sls * layer["As"] * (dn_sls - layer["y"]) ** 2

    Icr = I_conc + I_tension + I_comp

    calcbox(
        rf"""
Cracked moment of inertia about the neutral axis:

$$
I_{{cr}} = \frac{{b d_n^3}}{3}
         + \sum_{{\text{{tension}}}} n A_{{s,i}} (d_i - d_n)^2
         + \sum_{{\text{{compression}}}} n A_{{sc,j}} (d_n - d_{{sc,j}})^2
$$

Substituting for this section:

- $I_c = \dfrac{{{b:.1f} \times {dn_sls:.2f}^3}}{3}
      = {I_conc:,.2f}$
- Steel in tension: $I_t = {I_tension:,.2f}$
- Steel in compression: $I_c^s = {I_comp:,.2f}$

$$
I_{{cr}} = {Icr:,.2f}\ \text{{mm}}^4
$$
"""
    )

    st.markdown("---")

    # ------------------------------------------------------------------
    # 3.5 Curvature at service moment
    # ------------------------------------------------------------------
    st.subheader("3.5 Curvature at service moment")

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

    # ------------------------------------------------------------------
    # 3.6 Strain and stress in each steel layer
    # ------------------------------------------------------------------
    st.subheader("3.6 Steel strains and stresses at SLS")

    rows_eps = []

    # Top and bottom fibres (for context)
    eps_top = kappa * (0.0 - dn_sls)
    eps_bot = kappa * (D - dn_sls)

    rows_eps.append(
        {
            "Point": "Top fibre",
            "Depth y (mm)": 0.0,
            "ε": eps_top,
            "f_s (MPa)": Es * eps_top,
        }
    )

    for layer in all_layers:
        eps_i = kappa * (layer["y"] - dn_sls)
        fs_i = Es * eps_i  # MPa if Es in MPa
        rows_eps.append(
            {
                "Point": layer["name"],
                "Depth y (mm)": layer["y"],
                "ε": eps_i,
                "f_s (MPa)": fs_i,
            }
        )

    rows_eps.append(
        {
            "Point": "Bottom fibre",
            "Depth y (mm)": D,
            "ε": eps_bot,
            "f_s (MPa)": Es * eps_bot,
        }
    )

    df_eps = pd.DataFrame(rows_eps)
    st.table(df_eps)

    # Simple strain diagram with points at each steel layer
    fig_eps, ax_eps = plt.subplots(figsize=(3.0, 3.0))
    ys_plot = [0.0, dn_sls, D]
    eps_plot = [kappa * (y - dn_sls) for y in ys_plot]
    ax_eps.plot(eps_plot, ys_plot, "k-")

    for layer in all_layers:
        eps_i = kappa * (layer["y"] - dn_sls)
        ax_eps.plot(
            eps_i,
            layer["y"],
            "o",
            color="tab:blue" if layer["face"] == "bottom" else "tab:red",
        )
        ax_eps.text(
            eps_i,
            layer["y"],
            f" {layer['name']}",
            va="center",
            fontsize=5,
        )

    ax_eps.axhline(dn_sls, linestyle="--", linewidth=0.8, color="grey")
    ax_eps.set_xlabel("Strain ε")
    ax_eps.set_ylabel("Depth from top (mm)")
    ax_eps.set_title("SLS strain distribution")
    ax_eps.invert_yaxis()
    st.pyplot(fig_eps, use_container_width=False)
    plt.close(fig_eps)
