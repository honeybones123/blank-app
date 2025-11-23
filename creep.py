# creep.py

import math
import numpy as np
import pandas as pd
import streamlit as st
import matplotlib.pyplot as plt


def calc_notional_creep_coefficient(fc, h_mm, rh):
    """
    Very simplified 'code-like' notional creep coefficient φ_0.
    This is NOT a literal AS3600 implementation, but behaves similarly:
      - higher fc → smaller φ_0
      - higher humidity → smaller φ_0
      - thinner members (smaller h_mm) → larger φ_0
    """
    # Basic strength factor (higher strength = lower creep)
    k_f = 1.5 / (1.0 + (fc - 20.0) / 60.0)
    k_f = max(0.3, min(k_f, 1.5))

    # Humidity factor (70% ≈ 1.0)
    k_h = 1.0 + (80.0 - rh) / 100.0
    k_h = max(0.6, min(k_h, 1.6))

    # Size factor (notional size: larger → more creep)
    h_m = max(50.0, min(h_mm, 1000.0))
    k_hsize = (h_m / 200.0) ** 0.3

    phi_0 = 1.5 * k_f * k_h * k_hsize
    return max(0.5, min(phi_0, 4.0))


def calc_creep_coefficient(phi_0, t, t0):
    """
    Time development of creep coefficient φ(t, t0).
    Uses a simple hyperbolic/exponential-type function.

    t  = final age (days)
    t0 = age at loading (days)
    """
    if t <= t0:
        return 0.0

    # Time factor (allows φ(t, t0) → φ_0 as t → ∞)
    dt = t - t0
    beta_t = dt / (dt + 30.0)

    phi_t = phi_0 * beta_t
    return max(0.0, phi_t)


def render_creep():
    st.title("Creep (Long-Term Behaviour)")

    st.markdown(
        """
        ### Required Inputs for Creep

        This page estimates a **creep coefficient** \\( \\varphi(t, t_0) \\)
        and an **effective modulus** \\( E_{c,\\text{eff}} = \\frac{E_c}{1 + \\varphi} \\).

        These can later be used in:

        - **Deflection page** → long-term deflection (creep amplification of elastic deflection)  
        - **Crack width page** → reduced stiffness / increased curvature at SLS
        """
    )

    # --------------------------------------------------
    # Inputs
    # --------------------------------------------------
    col1, col2 = st.columns(2)

    with col1:
        fc = st.number_input(
            "Concrete strength f'c (MPa)",
            min_value=20.0,
            max_value=100.0,
            value=40.0,
            step=1.0,
            key="creep_fc",
        )

        Ec = st.number_input(
            "Short-term elastic modulus Ec (MPa)",
            min_value=15000.0,
            max_value=45000.0,
            value=30000.0,
            step=500.0,
            key="creep_Ec",
        )

        h_mm = st.number_input(
            "Notional member size h (mm)\n(e.g. effective thickness)",
            min_value=50.0,
            max_value=2000.0,
            value=400.0,
            step=25.0,
            key="creep_h_mm",
        )

    with col2:
        rh = st.number_input(
            "Ambient relative humidity RH (%)",
            min_value=40.0,
            max_value=100.0,
            value=70.0,
            step=1.0,
            key="creep_rh",
        )

        t0 = st.number_input(
            "Age at loading t₀ (days)",
            min_value=1.0,
            max_value=3650.0,
            value=28.0,
            step=1.0,
            key="creep_t0",
        )

        t_final = st.number_input(
            "Final age t (days) for design creep",
            min_value=7.0,
            max_value=36500.0,
            value=3650.0,
            step=10.0,
            key="creep_t_final",
        )

    st.markdown("---")

    # --------------------------------------------------
    # Calculations for selected time
    # --------------------------------------------------
    phi_0 = calc_notional_creep_coefficient(fc, h_mm, rh)
    phi_t = calc_creep_coefficient(phi_0, t_final, t0)

    if phi_t < 0.0:
        phi_t = 0.0

    Ec_eff = Ec / (1.0 + phi_t)

    # Summary table
    summary_df = pd.DataFrame(
        {
            "Parameter": [
                "f'c",
                "Ec (short-term)",
                "Notional size h",
                "RH",
                "t₀ (age at loading)",
                "t (final age)",
                "φ₀ (notional)",
                "φ(t, t₀)",
                "Ec,eff",
            ],
            "Value": [
                f"{fc:.1f} MPa",
                f"{Ec:.0f} MPa",
                f"{h_mm:.0f} mm",
                f"{rh:.0f} %",
                f"{t0:.0f} days",
                f"{t_final:.0f} days",
                f"{phi_0:.3f}",
                f"{phi_t:.3f}",
                f"{Ec_eff:.0f} MPa",
            ],
        }
    )

    st.subheader("Creep Summary (Design Point)")
    st.table(summary_df)

    # --------------------------------------------------
    # Graph φ(t, t0) vs time
    # --------------------------------------------------
    st.subheader("Creep Development Over Time")

    t_max_for_plot = max(t_final, t0 + 30.0)
    t_values = np.linspace(t0, t_max_for_plot, 200)
    phi_values = [calc_creep_coefficient(phi_0, t, t0) for t in t_values]

    fig, ax = plt.subplots()
    ax.plot(t_values, phi_values)
    ax.set_xlabel("Age t (days)")
    ax.set_ylabel("Creep coefficient φ(t, t₀)")
    ax.grid(True)

    st.pyplot(fig)

    st.markdown(
        """
        **Notes (conceptual only):**

        - For long-term deflection, you typically multiply the **short-term elastic deflection**
          by an amplification factor based on \\( \\varphi(t, t_0) \\).
        - For crack width calculations at SLS, the **curvature** can be increased
          using an appropriate effective modulus \\( E_{c,\\text{eff}} \\).
        """
    )

    # --------------------------------------------------
    # HOOK FOR INTEGRATION (OPTIONAL)
    # --------------------------------------------------
    # If you want this page to talk to your deflection / crack width pages,
    # you can store these in st.session_state under agreed keys, e.g.:
    #
    # st.session_state["creep_phi_design"] = phi_t
    # st.session_state["Ec_eff_design"] = Ec_eff
    #
    # Then, in your deflection/crack pages, you can read and use them if present.
