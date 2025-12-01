import math
import streamlit as st

from state_and_helpers import (
    get_param,
    get_sync_callbacks,
)
from widgets_helpers import apply_global_widget_css, number_row


def render_shear():
    # Same global styling as Inputs + Bending
    apply_global_widget_css()

    st.title("Shear & Torsion")

    # Same pattern as Inputs/Bending
    sync_callbacks = get_sync_callbacks()

    st.markdown(
        """
This page will perform an AS 3600 shear + torsion check.

For now we are **only setting up the widgets** using the same
session-state contract as the Inputs and Bending pages:
- All shared values live in `state_and_helpers.SHARED_DEFAULTS`
- Widgets use `shear_…` keys
- `sync_callbacks` keeps everything in sync across tabs.
"""
    )

    st.markdown("---")
    st.subheader("Design Inputs")

    # EXACT SAME LAYOUT PATTERN AS INPUTS/BENDING:
    # one st.columns(...) + number_row(...) inside each 'with' block
    col_geom, col_actions, col_eps = st.columns(3)

    # -------------------------------------------------
    # 1. Geometry & materials (shared, like Inputs)
    # -------------------------------------------------
    with col_geom:
        st.subheader("Geometry & materials")

        number_row(
            "b – beam/web width (mm)",
            "shear_b",                        # ← page-local key (mapped in TAB_KEYS)
            get_param("b", 400.0),            # ← shared value
            sync_callbacks,
            help_text="Shared with Inputs/Bending via session-state contract.",
            min_value=100.0,
            max_value=1200.0,
            step=10.0,
        )
        number_row(
            "D – overall depth (mm)",
            "shear_D",
            get_param("D", 600.0),
            sync_callbacks,
            help_text="Overall section depth (shared).",
            min_value=200.0,
            max_value=2000.0,
            step=10.0,
        )
        number_row(
            "L – span / design length (mm)",
            "shear_L",
            get_param("L", 3000.0),
            sync_callbacks,
            help_text="Design span or effective length (shared).",
            min_value=500.0,
            max_value=40000.0,
            step=50.0,
        )

        st.markdown("**Concrete & steel**")

        number_row(
            "f'c (MPa)",
            "shear_fc",
            get_param("fc", 40.0),
            sync_callbacks,
            help_text="Concrete compressive strength (shared).",
            min_value=20.0,
            max_value=100.0,
            step=1.0,
        )
        number_row(
            "f_sy (MPa)",
            "shear_fsy",
            get_param("fsy", 500.0),
            sync_callbacks,
            help_text="Steel yield strength (shared).",
            min_value=300.0,
            max_value=600.0,
            step=10.0,
        )
        number_row(
            "E_c (MPa)",
            "shear_Ec",
            get_param("Ec", 30000.0),
            sync_callbacks,
            help_text="Concrete modulus used in εₓ.",
            min_value=15000.0,
            max_value=45000.0,
            step=500.0,
        )
        number_row(
            "E_s (MPa)",
            "shear_Es",
            get_param("Es", 200000.0),
            sync_callbacks,
            help_text="Steel modulus.",
            min_value=150000.0,
            max_value=220000.0,
            step=5000.0,
        )

    # -------------------------------------------------
    # 2. Shear + axial (shared actions)
    # -------------------------------------------------
    with col_actions:
        st.subheader("Shear action & axial")

        number_row(
            "V* – design shear (kN)",
            "shear_Vu_star",
            get_param("Vu_star", 300.0),
            sync_callbacks,
            help_text="Controlling ultimate shear at the section (shared).",
            min_value=0.0,
            max_value=5000.0,
            step=10.0,
        )
        number_row(
            "N* – axial force (kN, +tension)",
            "shear_N_star",
            get_param("N_star", 0.0),
            sync_callbacks,
            help_text="Axial force at the section (+ tension, shared).",
            min_value=-5000.0,
            max_value=5000.0,
            step=10.0,
        )
        number_row(
            "P_v – vertical prestress / axial (kN)",
            "shear_P_star",
            get_param("P_star", 0.0),
            sync_callbacks,
            help_text="Prestress / axial assisting shear (shared).",
            min_value=-5000.0,
            max_value=5000.0,
            step=10.0,
        )

        st.subheader("Torsion")

        number_row(
            "T* – torsion at section (kNm)",
            "shear_Tu_star",
            get_param("Tu_star", 0.0),
            sync_callbacks,
            help_text="Design torsion at the section (shared).",
            min_value=0.0,
            max_value=5000.0,
            step=10.0,
        )

    # -------------------------------------------------
    # 3. εx helper inputs (LOCAL ONLY – no contract)
    # -------------------------------------------------
    with col_eps:
        st.subheader("εₓ inputs (local to shear page)")

        # These are *not* part of the shared contract; just local helpers.
        A_st = st.number_input(
            "A_st (mm²) – non-prestressed tension steel",
            value=float(4 * (math.pi * 20**2 / 4)),
            help="Used only in the εₓ calculation on this page.",
        )
        A_pt = st.number_input(
            "A_pt (mm²) – prestressing steel",
            value=0.0,
            help="Used only in the εₓ calculation on this page.",
        )
        f_po = st.number_input(
            "f_po (MPa) – effective tendon stress",
            value=0.0,
            help="Used only in the εₓ calculation on this page.",
        )
        A_ct = st.number_input(
            "A_ct (mm²) – area of concrete in tension",
            value=float((get_param("b", 400.0)) * (get_param("D", 600.0) / 2.0)),
            help="Approximate tension zone area used in εₓ.",
        )

        st.subheader("Shear φ, σ_cp (local)")
        phi = st.number_input(
            "φ – strength reduction for shear",
            value=0.75,
            min_value=0.50,
            max_value=0.90,
            step=0.05,
            help="Local factor for this page; not shared.",
        )
        sigma_cp = st.number_input(
            "σ_cp – average prestress (MPa)",
            value=0.0,
            help="Used in torsion cracking torque T_cr.",
        )

        st.info(
            "Once we’re happy with this widget layout, the existing shear/torsion "
            "calculation steps can be plugged in underneath using these inputs."
        )


if __name__ == "__main__":
    render_shear()
