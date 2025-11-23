import math
import numpy as np
import pandas as pd
import streamlit as st
import matplotlib.pyplot as plt

from state_and_helpers import get_param


def render_deflection():
    """
    Deflection page: short-term + long-term (creep + shrinkage).
    This page does NOT write to shared results; it is purely visual.
    Inputs default to shared parameters via get_param().
    """
    st.title("Deflection (Short-Term & Long-Term)")

    st.markdown(
        """
        This page estimates **short-term** and **long-term** deflection
        for a simply supported beam under uniform load.

        It uses:
        - Geometry & materials from the shared inputs (as defaults)
        - Creep coefficient / effective modulus from the Creep page, if available
        - Shrinkage strain from the Shrinkage page, if available

        Results here are **local only** and do not modify shared session state.
        """
    )

    st.markdown("---")

    # --------------------------------------------------
    # Geometry & materials (local widgets)
    # --------------------------------------------------
    col_geom, col_mat = st.columns(2)

    with col_geom:
        st.subheader("Geometry")

        b = st.number_input(
            "Width b (mm)",
            min_value=100.0,
            max_value=3000.0,
            value=float(get_param("b", 400.0)),
            step=10.0,
            key="defl_b",
        )

        D = st.number_input(
            "Overall depth D (mm)",
            min_value=100.0,
            max_value=3000.0,
            value=float(get_param("D", 600.0)),
            step=10.0,
            key="defl_D",
        )

        L = st.number_input(
            "Span L (mm)",
            min_value=1000.0,
            max_value=30000.0,
            value=float(get_param("L", 3000.0)),
            step=100.0,
            key="defl_L",
        )

    with col_mat:
        st.subheader("Materials & Loads")

        Ec = st.number_input(
            "Short-term Ec (MPa)",
            min_value=15000.0,
            max_value=50000.0,
            value=float(get_param("Ec", 30000.0)),
            step=500.0,
            key="defl_Ec",
        )

        q_dead = st.number_input(
            "Service dead load w_g (kN/m)",
            min_value=0.0,
            max_value=100.0,
            value=5.0,
            step=0.5,
            key="defl_q_dead",
        )

        q_live = st.number_input(
            "Service live load w_q (kN/m)",
            min_value=0.0,
            max_value=100.0,
            value=5.0,
            step=0.5,
            key="defl_q_live",
        )

    st.markdown("---")

    # --------------------------------------------------
    # Creep & shrinkage inputs from other pages (if present)
    # --------------------------------------------------
    phi_creep = st.session_state.get("creep_phi_design", None)
    Ec_eff_design = st.session_state.get("Ec_eff_design", None)
    eps_sh_micro = st.session_state.get("shrinkage_eps_design", None)  # microstrain

    if Ec_eff_design is not None and Ec_eff_design > 0:
        k_creep = Ec / Ec_eff_design
    elif phi_creep is not None and phi_creep > 0:
        k_creep = 1.0 + phi_creep
    else:
        k_creep = 1.0  # no creep data → short-term only

    eps_sh = (eps_sh_micro or 0.0) / 1e6  # convert microstrain → strain

    # --------------------------------------------------
    # Section properties & deflection calc
    # --------------------------------------------------
    b_mm = max(1.0, b)
    D_mm = max(1.0, D)
    L_mm = max(1.0, L)

    I_gross = b_mm * D_mm**3 / 12.0  # mm^4
    w_total = q_dead + q_live        # N/mm (same numeric as kN/m)

    # Instantaneous midspan deflection (simply supported, UDL):
    # δ_inst = 5 w L^4 / (384 E I)
    delta_inst = 5.0 * w_total * L_mm**4 / (384.0 * Ec * I_gross)

    # Creep-amplified bending deflection
    delta_creep = delta_inst * k_creep

    # Shrinkage deflection – very simplified:
    # curvature φ_sh ≈ ε_sh / (0.7 D), δ_sh = φ_sh L^2 / 8
    if D_mm > 0:
        phi_sh = eps_sh / (0.7 * D_mm)
    else:
        phi_sh = 0.0

    delta_sh = phi_sh * L_mm**2 / 8.0

    delta_total = delta_creep + delta_sh

    limit_total = L_mm / 250.0
    util_total = delta_total / limit_total if limit_total > 0 else None

    # --------------------------------------------------
    # Summary table
    # --------------------------------------------------
    st.subheader("Deflection Summary")

    util_str = f"{util_total:.2f}" if util_total is not None else "—"

    data = {
        "Quantity": [
            "Dead load w_g",
            "Live load w_q",
            "Instantaneous δ_inst",
            "Creep δ_creep",
            "Shrinkage δ_sh",
            "Total long-term δ_total",
            "Limit L/250",
            "Utilisation δ_total / (L/250)",
        ],
        "Value": [
            f"{q_dead:.2f} kN/m",
            f"{q_live:.2f} kN/m",
            f"{delta_inst:.2f} mm",
            f"{delta_creep:.2f} mm",
            f"{delta_sh:.2f} mm",
            f"{delta_total:.2f} mm",
            f"{limit_total:.2f} mm",
            util_str,
        ],
    }
    summary_df = pd.DataFrame(data)
    st.table(summary_df)

    st.markdown(
        """
        - Utilisation ≤ 1.0 → within a typical L/250 total deflection limit.  
        - Shrinkage & creep terms depend on values from the Creep & Shrinkage pages.
        """
    )

    st.markdown("---")

    # --------------------------------------------------
    # Deflected shape plot
    # --------------------------------------------------
    st.subheader("Deflected Shape (Illustrative)")

    x = np.linspace(0.0, L_mm, 200)
    xi = x / L_mm
    y_long = -delta_total * 4.0 * xi * (1.0 - xi)

    fig, ax = plt.subplots()
    ax.plot(x, y_long)
    ax.set_xlabel("Span position x (mm)")
    ax.set_ylabel("Deflection (mm)")
    ax.grid(True)

    st.pyplot(fig)
