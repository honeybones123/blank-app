import math
import streamlit as st

from state_and_helpers import (
    get_sync_callbacks,
)

# Shared helpers (same as Inputs / Bending pages)
from widgets_helpers import apply_global_widget_css, number_row


def render_shear():
    """Shear & Torsion page — WIDGETS ONLY, matching Inputs/Bending contract."""
    # Same global CSS + sync pattern as other pages
    sync_callbacks = get_sync_callbacks()
    apply_global_widget_css()

    st.title("Shear & Torsion")
    st.markdown(
        """
This page will perform an AS 3600 shear + torsion check with a step-by-step ULS calculation.

For now, we are just setting up the **input widgets** so they behave identically to the
Inputs and Bending pages (same layout, same number_row helper, same session-state contract).
"""
    )

    st.markdown("---")
    st.subheader("Design Inputs")

    # Match the "three-block" style: Actions, Geometry, Materials
    col_actions, col_geom, col_mat = st.columns(3)

    # ------------------------------------------------------------
    # 1. Design actions (Vu*, Tu*, N*, P_v) — shared via TAB_KEYS
    # ------------------------------------------------------------
    with col_actions:
        st.subheader("Actions")

        number_row(
            "Design shear Vu* (kN)",
            "shear_Vu_star",
            10.0,
            sync_callbacks,
            help_text="Factored design shear at the critical section.",
        )
        number_row(
            "Design torsion Tu* (kNm)",
            "shear_Tu_star",
            0.0,
            sync_callbacks,
            help_text="Factored torsion at the section.",
        )
        number_row(
            "Axial force N* (kN, +tension)",
            "shear_N_star",
            0.0,
            sync_callbacks,
            help_text="Axial action at the section (+tension / −compression).",
        )
        number_row(
            "Vertical prestress / axial P_v (kN)",
            "shear_P_star",
            0.0,
            sync_callbacks,
            help_text="Prestress or additional vertical axial force assisting shear.",
        )

    # ------------------------------------------------------------
    # 2. Geometry (b, D, L) — shared via TAB_KEYS
    # ------------------------------------------------------------
    with col_geom:
        st.subheader("Geometry")

        number_row(
            "Width b (mm)",
            "shear_b",
            300.0,
            sync_callbacks,
            help_text="Beam/web width used for shear checks.",
        )
        number_row(
            "Depth D (mm)",
            "shear_D",
            600.0,
            sync_callbacks,
            help_text="Overall section depth from compression face to soffit.",
        )
        number_row(
            "Span L (mm)",
            "shear_L",
            6000.0,
            sync_callbacks,
            help_text="Member span (used mainly for linkage to deflection page).",
        )

    # ------------------------------------------------------------
    # 3. Materials (fc, fsy, Ec, Es) — shared via TAB_KEYS
    # ------------------------------------------------------------
    with col_mat:
        st.subheader("Materials")

        number_row(
            "Concrete strength f'c (MPa)",
            "shear_fc",
            40.0,
            sync_callbacks,
            help_text="Characteristic compressive strength of concrete.",
        )
        number_row(
            "Steel yield fsy (MPa)",
            "shear_fsy",
            500.0,
            sync_callbacks,
            help_text="Yield strength of reinforcing steel.",
        )
        number_row(
            "Ec (MPa)",
            "shear_Ec",
            30000.0,
            sync_callbacks,
            help_text="Short-term modulus of elasticity of concrete.",
        )
        number_row(
            "Es (MPa)",
            "shear_Es",
            200000.0,
            sync_callbacks,
            help_text="Elastic modulus of reinforcing steel.",
        )

    st.markdown("---")
    st.subheader("εₓ helper inputs (local to this page)")

    # These are *local-only* for the shear εx calc.
    # Styling is simpler for now; we can upgrade to a number_row-style wrapper later if you want.
    c1, c2 = st.columns(2)
    with c1:
        A_st = st.number_input(
            "A_st (mm²) – non-prestressed tension steel",
            value=float(4 * (math.pi * 20**2 / 4)),
        )
        A_pt = st.number_input(
            "A_pt (mm²) – prestressing steel",
            value=0.0,
        )
    with c2:
        f_po = st.number_input(
            "f_po (MPa) – effective tendon stress",
            value=0.0,
        )
        A_ct = st.number_input(
            "A_ct (mm²) – area of concrete in tension",
            value=400.0 * 300.0,
            help="Approx. b × (effective tension zone depth).",
        )

    st.info(
        "Widgets are now using the same `number_row` helper and layout contract as the "
        "Inputs and Bending pages. Shear/torsion calculations and blue calc boxes will "
        "be wired in next, using these shared values."
    )


if __name__ == "__main__":
    render_shear()
