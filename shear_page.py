import math
import streamlit as st

from state_and_helpers import (
    get_param,
    get_sync_callbacks,
)

# Shared helpers (same as Inputs / Bending)
from widgets_helpers import apply_global_widget_css, number_row


def render_shear():
    # Same global CSS + layout as other pages
    apply_global_widget_css()

    st.title("Shear & Torsion")

    # One shared callback dict for ALL widgets (contract)
    sync_callbacks = get_sync_callbacks()

    st.markdown(
        """
This page will perform an AS 3600 shear + torsion check.
For now, we're just wiring the **Design Inputs** so they behave
identically to the Inputs and Bending pages (same widget contract and layout).
"""
    )

    # =====================================================
    # 1. DESIGN INPUTS (shared + local)
    # =====================================================
    st.subheader("Design Inputs")

    # EXACT same pattern as Inputs/Bending:
    #   - number_row(...)
    #   - widget keys: shear_* (mapped in TAB_KEYS)
    #   - values pulled via get_param(...)
    #   - sync_callbacks passed through
    col_geom, col_actions, col_eps = st.columns(3)

    # ------------------ 1.1 Shared geometry & materials ------------------
    with col_geom:
        st.markdown("**Shared geometry & materials (linked to Inputs tab)**")

        number_row(
            "b – beam/web width (mm)",
            "shear_b",
            get_param("b", 400.0),
            sync_callbacks,
            help_text="Shared with Inputs tab.",
            min_value=100.0,
            max_value=1200.0,
            step=10.0,
        )
        number_row(
            "D – overall depth (mm)",
            "shear_D",
            get_param("D", 600.0),
            sync_callbacks,
            help_text="Shared with Inputs tab.",
            min_value=200.0,
            max_value=2000.0,
            step=10.0,
        )
        number_row(
            "L – span L (mm)",
            "shear_L",
            get_param("L", 3000.0),
            sync_callbacks,
            help_text="Shared with Inputs tab.",
            min_value=500.0,
            max_value=30000.0,
            step=50.0,
        )

        number_row(
            "f'c (MPa)",
            "shear_fc",
            get_param("fc", 40.0),
            sync_callbacks,
            help_text="Concrete compressive strength (AS 3600).",
            min_value=20.0,
            max_value=100.0,
            step=1.0,
        )
        number_row(
            "f_sy (MPa)",
            "shear_fsy",
            get_param("fsy", 500.0),
            sync_callbacks,
            help_text="Steel yield strength.",
            min_value=300.0,
            max_value=600.0,
            step=10.0,
        )
        number_row(
            "E_c (MPa)",
            "shear_Ec",
            get_param("Ec", 30000.0),
            sync_callbacks,
            help_text="Concrete modulus (used in εₓ calc).",
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

    # ------------------ 1.2 Shear / axial / torsion (shared) -------------
    with col_actions:
        st.markdown("**Shear, axial & torsion (linked to Inputs tab)**")

        number_row(
            "V* – design shear (kN)",
            "shear_Vu_star",
            get_param("Vu_star", 300.0),
            sync_callbacks,
            help_text="Controlling ultimate shear at the section.",
            min_value=0.0,
            max_value=5000.0,
            step=10.0,
        )
        number_row(
            "N* – axial force (kN, +tension)",
            "shear_N_star",
            get_param("N_star", 0.0),
            sync_callbacks,
            help_text="Axial force at the section (+tension).",
            min_value=-5000.0,
            max_value=5000.0,
            step=10.0,
        )
        number_row(
            "P_v – vertical prestress / axial (kN)",
            "shear_P_star",
            get_param("P_star", 0.0),
            sync_callbacks,
            help_text="Prestress or additional vertical axial force assisting shear.",
            min_value=-5000.0,
            max_value=5000.0,
            step=10.0,
        )
        number_row(
            "T* – torsion at section (kNm)",
            "shear_Tu_star",
            get_param("Tu_star", 0.0),
            sync_callbacks,
            help_text="Design torsion at the section.",
            min_value=0.0,
            max_value=5000.0,
            step=10.0,
        )

    # ------------------ 1.3 εx helper inputs (LOCAL ONLY) ----------------
    # These are not part of the shared contract (no TAB_KEYS mapping), so
    # we *deliberately* use plain st.number_input, just like any local
    # widget on Bending/Inputs.
    with col_eps:
        st.markdown("**εₓ helper inputs (local to this page)**")

        A_st = st.number_input(
            "A_st (mm²) – non-prestressed tension steel",
            value=float(4 * (math.pi * 20**2 / 4)),
        )
        A_pt = st.number_input(
            "A_pt (mm²) – prestressing steel",
            value=0.0,
        )
        f_po = st.number_input(
            "f_po (MPa) – effective tendon stress",
            value=0.0,
        )
        A_ct = st.number_input(
            "A_ct (mm²) – area of concrete in tension",
            value=float((get_param("b", 400.0)) * (get_param("D", 600.0) / 2.0)),
        )

        st.info(
            "These εₓ helper inputs are local to the Shear page. "
            "Shared geometry/materials/actions above are fully synced with Inputs/Bending."
        )

    # Placeholder so the page doesn’t feel “unfinished”
    st.markdown("---")
    st.markdown(
        "_Shear & torsion calculations, step-by-step boxes, and utilisation summary "
        "will plug in **below** this line once we’re happy with the widget contract._"
    )


if __name__ == "__main__":
    render_shear()
