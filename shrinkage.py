# shrinkage.py

import math
import numpy as np
import pandas as pd
import streamlit as st
import matplotlib.pyplot as plt


def calc_notional_shrinkage_strain(fc, h_mm, rh):
    """
    Very simplified 'code-like' notional shrinkage strain ε_sh∞ (microstrain).

    Behaviour:
      - higher fc → lower shrinkage
      - higher RH → lower shrinkage
      - thinner members → higher shrinkage
    """
    # Base notional shrinkage (microstrain)
    eps_base = 800.0  # microstrain

    # Strength factor
    k_f = 1.2 / (1.0 + (fc - 25.0) / 50.0)
    k_f = max(0.5, min(k_f, 1.5))

    # Humidity factor
    k_h = 1.0 + (60.0 - rh) / 80.0
    k_h = max(0.5, min(k_h, 1.5))

    # Size factor
    h_m = max(50.0, min(h_mm, 1000.0))
    k_hsize = (200.0 / h_m) ** 0.2

    eps_sh_inf = eps_base * k_f * k_h * k_hsize
    return max(200.0, min(eps_sh_inf, 1200.0))  # limit 200–1200 με


def calc_shrinkage_strain(eps_inf, t, t_s):
    """
    Time development of shrinkage strain ε_sh(t).

    eps_inf in microstrain (με).
    t   = age (days)
    t_s = age at start of drying (days).
    """
    if t <= t_s:
        return 0.0

    dt = t - t_s
    beta_t = dt / (dt + 35.0)

    eps_t = eps_inf * beta_t
    return eps_t


def render_shrinkage():
    st.title("Shrinkage (Time-Dependent)")

    st.markdown(
        """
        ### Required Inputs for Shrinkage

        This page estimates a **notional shrinkage strain** \\( \\varepsilon_{sh,\\infty} \\)
        and its development \\( \\varepsilon_{sh}(t) \\).

        These can later feed into:

        - **Deflection page** → long-term curvature (shrinkage curvature + creep)  
        - **Crack width page** → long-term tension stiffening / strain distributions
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
            key="sh_fc",
        )

        h_mm = st.number_input(
            "Notional member size h (mm)\n(e.g. effective thickness)",
            min_value=50.0,
            max_value=2000.0,
            value=400.0,
            step=25.0,
            key="sh_h_mm",
        )

        rh = st.number_input(
            "Ambient relative humidity RH (%)",
            min_value=40.0,
            max_value=100.0,
            value=70.0,
            step=1.0,
            key="sh_rh",
        )

    with col2:
        t_s = st.number_input(
            "Age at start of drying tₛ (days)",
            min_value=1.0,
            max_value=3650.0,
            value=7.0,
            step=1.0,
            key="sh_ts",
        )

        t_final = st.number_input(
            "Final age t (days) for design shrinkage",
            min_value=7.0,
            max_value=36500.0,
            value=3650.0,
            step=10.0,
            key="sh_t_final",
        )

        # Optional: factor for restrained shrinkage use cases
        k_rest = st.number_input(
            "Restraint factor k_rest (0–1)\n(1 = fully free, 0 = fully restrained)",
            min_value=0.0,
            max_value=1.0,
            value=1.0,
            step=0.05,
            key="sh_k_rest",
        )

    st.markdown("---")

    # --------------------------------------------------
    # Calculations for selected time
    # --------------------------------------------------
    eps_inf = calc_notional_shrinkage_strain(fc, h_mm, rh)  # microstrain
    eps_t = calc_shrinkage_strain(eps_inf, t_final, t_s)    # microstrain

    eps_t_eff = eps_t * k_rest

    # Summary table
    summary_df = pd.DataFrame(
        {
            "Parameter": [
                "f'c",
                "Notional size h",
                "RH",
                "tₛ (start of drying)",
                "t (final age)",
                "ε_sh,∞ (notional)",
                "ε_sh(t)",
                "ε_sh,eff(t) (with k_rest)",
            ],
            "Value": [
                f"{fc:.1f} MPa",
                f"{h_mm:.0f} mm",
                f"{rh:.0f} %",
                f"{t_s:.0f} days",
                f"{t_final:.0f} days",
                f"{eps_inf:.0f} με",
                f"{eps_t:.0f} με",
                f"{eps_t_eff:.0f} με",
            ],
        }
    )

    st.subheader("Shrinkage Summary (Design Point)")
    st.table(summary_df)

    # --------------------------------------------------
    # Graph ε_sh(t) vs time
    # --------------------------------------------------
    st.subheader("Shrinkage Development Over Time")

    t_max_for_plot = max(t_final, t_s + 30.0)
    t_values = np.linspace(t_s, t_max_for_plot, 200)
    eps_values = [calc_shrinkage_strain(eps_inf, t, t_s) for t in t_values]

    fig, ax = plt.subplots()
    ax.plot(t_values, eps_values)
    ax.set_xlabel("Age t (days)")
    ax.set_ylabel("Shrinkage strain ε_sh(t) [με]")
    ax.grid(True)

    st.pyplot(fig)

    st.markdown(
        """
        **Notes (conceptual only):**

        - Shrinkage contributes to **curvature** in statically indeterminate members
          and to **tension stiffening** behaviour in cracked regions.
        - In deflection calculations, you can treat shrinkage as an **imposed strain**
          which, combined with creep, affects long-term curvature.
        """
    )

    # --------------------------------------------------
    # HOOK FOR INTEGRATION (OPTIONAL)
    # --------------------------------------------------
    # For integration with other pages, you can store results in session_state:
    #
    # st.session_state["shrinkage_eps_design"] = eps_t_eff   # microstrain
    # st.session_state["shrinkage_eps_inf"] = eps_inf       # microstrain
    #
    # Then deflection/crack width pages can read them and use them in curvature.
