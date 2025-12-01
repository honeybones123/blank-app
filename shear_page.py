# shear_page.py
# ============================
# SHEAR & TORSION – WIDGET SHELL ONLY
# (matching Inputs/Bending widget contract)
# ============================

import math
import streamlit as st

from state_and_helpers import (
    get_sync_callbacks,
    get_param,
)

from widgets_helpers import (
    apply_global_widget_css,
    apply_calcbox_css,   # ready for later when we add calc boxes
    number_row,
)


def render_shear():
    """Shear & torsion page – for now only the input widgets.

    Widget behaviour & layout are IDENTICAL to Inputs/Bending:
      - uses number_row(label, key, default, sync_callbacks, help_text=...)
      - no extra kwargs (no min_value, max_value, step, etc.)
      - same label-on-left / input-on-right style via number_row + CSS.
    """
    sync_callbacks = get_sync_callbacks()
    apply_global_widget_css()
    apply_calcbox_css()  # harmless even though we’re not using calc boxes yet

    st.title("Shear & Torsion")

    st.markdown(
        """
This page will perform an AS 3600 shear + torsion check using the **same
widget contract** as the Inputs and Bending pages.

For now we’re just wiring the inputs so that all tabs share geometry,
materials and design actions consistently.
"""
    )

    st.markdown("---")
    st.subheader("Design Inputs")

    # 3 columns like Inputs/Bending style
    col_geom, col_actions, col_torsion = st.columns(3)

    # -------------------------------------------------
    # Geometry & materials  (shared via TAB_KEYS mapping)
    # -------------------------------------------------
    with col_geom:
        st.subheader("Geometry & materials")

        number_row(
            "Width b (mm)",
            "shear_b",
            10.0,
            sync_callbacks,
            help_text="Beam/web width. Shared with Inputs/Bending.",
        )
        number_row(
            "Depth D (mm)",
            "shear_D",
            10.0,
            sync_callbacks,
            help_text="Overall section depth from compression face to soffit.",
        )
        number_row(
            "Span L (mm)",
            "shear_L",
            100.0,
            sync_callbacks,
            help_text="Clear span used for shear/torsion checks.",
        )

        st.markdown("---")

        st.subheader("Materials")
        number_row(
            "Concrete strength f'c (MPa)",
            "shear_fc",
            2.0,
            sync_callbacks,
            help_text="Characteristic compressive strength of concrete.",
        )
        number_row(
            "Steel yield fsy (MPa)",
            "shear_fsy",
            10.0,
            sync_callbacks,
            help_text="Yield stress of shear reinforcement.",
        )
        number_row(
            "Ec (MPa)",
            "shear_Ec",
            1000.0,
            sync_callbacks,
            help_text="Short-term modulus of elasticity of concrete.",
        )
        number_row(
            "Es (MPa)",
            "shear_Es",
            5000.0,
            sync_callbacks,
            help_text="Elastic modulus of reinforcing steel.",
        )

    # -------------------------------------------------
    # Shear actions (shared)
    # -------------------------------------------------
    with col_actions:
        st.subheader("Shear action & axial")

        number_row(
            "Design shear Vu* (kN)",
            "shear_Vu_star",
            10.0,
            sync_callbacks,
            help_text="Factored design shear at the critical section.",
        )
        number_row(
            "Axial force N* (kN)",
            "shear_N_star",
            10.0,
            sync_callbacks,
            help_text="Axial action at the section (+compression / −tension).",
        )
        number_row(
            "Prestress / vertical axial P_v (kN)",
            "shear_P_star",
            0.0,
            sync_callbacks,
            help_text="Prestress or additional vertical axial force assisting shear.",
        )

    # -------------------------------------------------
    # Torsion & local εx inputs (local to this page)
    # -------------------------------------------------
    with col_torsion:
        st.subheader("Torsion & local εₓ inputs")

        number_row(
            "Design torsion Tu* (kNm)",
            "shear_Tu_star",
            1.0,
            sync_callbacks,
            help_text="Factored torsion at the section.",
        )

        # Local-only helpers (not using number_row on purpose – same as Inputs)
        st.markdown("#### εₓ helper parameters (local only)")

        Ast_default = 4 * (math.pi * 20.0**2 / 4.0)
        st.number_input(
            "A_st (mm²) – non-prestressed tension steel",
            key="shear_A_st_local",
            value=float(Ast_default),
        )
        st.number_input(
            "A_pt (mm²) – prestressing steel",
            key="shear_A_pt_local",
            value=0.0,
        )
        st.number_input(
            "f_po (MPa) – effective tendon stress",
            key="shear_f_po_local",
            value=0.0,
        )
        b_val = float(get_param("b", 400.0) or 400.0)
        D_val = float(get_param("D", 600.0) or 600.0)
        st.number_input(
            "A_ct (mm²) – area of concrete in tension",
            key="shear_A_ct_local",
            value=float(b_val * (D_val / 2.0)),
        )

    # For now we stop here – once the widgets are behaving perfectly,
    # we’ll plug the full shear/torsion calculations back in underneath.


if __name__ == "__main__":
    render_shear()
