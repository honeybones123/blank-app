# shear_page.py
import math
import streamlit as st

from state_and_helpers import (
    get_param,
    get_sync_callbacks,
    update_results,
)

from widgets_helpers import apply_global_widget_css, number_row

import shear_core
from shear_core import ShearInputs
from shear_steps import (
    _inject_calcbox_css,
    render_step_1,
    render_step_2,
    render_step_3,
    render_step_4,
    render_step_5,
    render_step_6,
    render_step_7,
)


def render_shear():
    # Same global CSS as other pages
    apply_global_widget_css()
    _inject_calcbox_css()

    st.title("Shear & Torsion")

    sync_callbacks = get_sync_callbacks()
    summary_placeholder = st.empty()

    st.markdown(
        """
This page performs an AS 3600 shear + torsion check with a step-by-step ULS calculation.  
Geometry, materials and design actions are shared with the Inputs tab via the session-state
contract. Results are written to the global RESULTS using `update_results()` so the Inputs
summary can show shear utilisation.
"""
    )

    # =====================================================
    # 1. DESIGN INPUTS (same widget contract as Inputs/Bending)
    # =====================================================
    st.subheader("Design Inputs")

    col_geom, col_actions, col_eps = st.columns(3)

    # ---------- 1.1 Geometry & materials ----------
    with col_geom:
        st.markdown("### Geometry & materials")

        number_row(
            "Width b (mm)",
            "shear_b",
            get_param("b", 300.0),
            sync_callbacks,
            help_text="Shared with Inputs tab.",
        )
        number_row(
            "Depth D (mm)",
            "shear_D",
            get_param("D", 600.0),
            sync_callbacks,
            help_text="Overall section depth, shared with Inputs.",
        )
        number_row(
            "Span L (mm)",
            "shear_L",
            get_param("L", 3000.0),
            sync_callbacks,
            help_text="Clear span or design span for this section.",
        )

        number_row(
            "Concrete strength f'c (MPa)",
            "shear_fc",
            get_param("fc", 40.0),
            sync_callbacks,
            help_text="Concrete compressive strength (AS 3600).",
        )
        number_row(
            "Steel yield f_sy (MPa)",
            "shear_fsy",
            get_param("fsy", 500.0),
            sync_callbacks,
            help_text="Yield stress of longitudinal & shear reinforcement.",
        )
        number_row(
            "Concrete modulus Ec (MPa)",
            "shear_Ec",
            get_param("Ec", 30000.0),
            sync_callbacks,
            help_text="Used in εₓ calc when compression develops.",
        )
        number_row(
            "Steel modulus Es (MPa)",
            "shear_Es",
            get_param("Es", 200000.0),
            sync_callbacks,
            help_text="Modulus of non-prestressed reinforcement.",
        )

    # ---------- 1.2 Shear actions & torsion ----------
    with col_actions:
        st.markdown("### Shear action & axial")

        number_row(
            "Design shear V* (kN)",
            "shear_Vu_star",
            get_param("Vu_star", 300.0),
            sync_callbacks,
            help_text="Factored shear at the section.",
        )
        number_row(
            "Axial force N* (kN, +tension)",
            "shear_N_star",
            get_param("N_star", 0.0),
            sync_callbacks,
            help_text="Axial force at the section (+tension, −compression).",
        )
        number_row(
            "Vertical prestress / axial P_v (kN)",
            "shear_P_star",
            get_param("P_star", 0.0),
            sync_callbacks,
            help_text="Prestress or vertical axial force assisting shear.",
        )

        st.markdown("### Torsion & φ")

        number_row(
            "Torsion T* (kNm)",
            "shear_Tu_star",
            get_param("Tu_star", 0.0),
            sync_callbacks,
            help_text="Factored torsion at the section.",
        )

        phi = st.number_input(
            "φ – strength reduction for shear",
            value=0.75,
            min_value=0.5,
            max_value=0.9,
            step=0.05,
        )
        sigma_cp = st.number_input(
            "σ_cp – average prestress (MPa)",
            value=0.0,
            help="Used in torsion cracking torque T_cr (AS 3600 Cl. 8.3.4).",
        )

    # ---------- 1.3 εx + detailing (local) ----------
    with col_eps:
        st.markdown("### εₓ inputs (ULS flexural strain)")

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
            value=float((get_param("b", 300.0)) * (get_param("D", 600.0) / 2.0)),
        )

        st.markdown("### Shear detailing")

        d_g = st.number_input(
            "d_g – max aggregate size (mm)",
            value=20.0,
            min_value=5.0,
            max_value=40.0,
        )

        sum_duct = st.number_input(
            "Sum of duct diameters crossing web (mm)",
            value=0.0,
            min_value=0.0,
        )

        kd_opt = st.selectbox(
            "k_d factor for prestressing ducts",
            (
                ("None (no ducts in web)", 0.0),
                ("0.5 – steel ducts, grouted", 0.5),
                ("0.8 – plastic ducts, grouted", 0.8),
                ("1.2 – ungrouted ducts", 1.2),
            ),
            index=0,
            format_func=lambda kv: kv[0],
        )
        k_d = kd_opt[1]

        method = st.radio(
            "k_v method",
            (
                "General εₓ-based (Cl. 8.2.4.2)",
                "Simplified non-prestressed (Cl. 8.2.4.3)",
            ),
            index=0,
        )
        use_general_kv = method.startswith("General")

    # -------------------------------------------------
    # Shared state used by the engine
    # -------------------------------------------------
    b = get_param("b")
    D = get_param("D")
    d = get_param("d")

    fc = get_param("fc")
    fsy = get_param("fsy")
    Ec = get_param("Ec")
    Es = get_param("Es")

    M_star = get_param("Mu_star") or 0.0
    V_star = get_param("Vu_star") or 0.0
    T_star = get_param("Tu_star") or 0.0
    N_star = get_param("N_star") or 0.0
    P_v = get_param("P_star") or 0.0

    lig_d = get_param("lig_d") or 10.0
    legs = get_param("lig_legs") or 2.0
    s_lig = get_param("s_lig") or 200.0

    if not (b and D and d):
        st.error("Geometry (b, D, d) not fully defined – check Inputs / Bending tab.")
        return

    # Build input dataclass for core calculation
    inp = ShearInputs(
        b=b,
        D=D,
        d=d,
        fc=fc,
        fsy=fsy,
        Ec=Ec,
        Es=Es,
        M_star=M_star,
        V_star=V_star,
        T_star=T_star,
        N_star=N_star,
        P_v=P_v,
        phi=phi,
        sigma_cp=sigma_cp,
        A_st=A_st,
        A_pt=A_pt,
        f_po=f_po,
        A_ct=A_ct,
        d_g=d_g,
        lig_d=lig_d,
        legs=legs,
        s_lig=s_lig,
        use_general_kv=use_general_kv,
        sum_duct=sum_duct,
        k_d=k_d,
    )

    results = shear_core.run_shear_calc(inp)

    # =====================================================
    # 2–7. STEP-BY-STEP CALC BLOCKS (blue boxes)
    # =====================================================
    st.markdown("---")
    st.subheader("Step-by-step ULS shear & torsion check")

    render_step_1(results, T_star=T_star, phi=phi)
    render_step_2(results, V_star=V_star)
    render_step_3(results, b=b, D=D, d=d, b_v=results.b_v, d_v=results.d_v)
    render_step_4(results)
    render_step_5(results)
    render_step_6(results, V_eq=results.V_eq)
    render_step_7(results)

    # =====================================================
    # SUMMARY + push to RESULTS
    # =====================================================
    torsion_label = (
        "**Yes (T* > 0.25 φT_cr)**" if results.torsion_required else "No (strength check)"
    )

    summary_md = f"""
### Shear/Torsion ULS Summary

| Item | Value |
|------|-------|
| Torsion considered? | {torsion_label} |
| V_eq* | **{results.V_eq:.1f} kN** |
| V_uc | **{results.Vuc_kN:,.1f} kN** |
| V_us | **{results.Vus_kN:,.1f} kN** |
| φV_u vs V_eq* | **{results.phi_Vu:,.1f} kN / {results.V_eq:.1f} kN → {"OK" if results.shear_ok else "NG"}** |
| V_u,max (web crushing) | **{results.Vu_max_kN:,.1f} kN** |
| Web-crushing check | **{"OK" if results.web_ok else "NG"}** |
| εₓ, k_v, θ_v | **εₓ = {results.eps_x:.5f},  k_v = {results.k_v:.3f},  θ_v = {results.theta_v_deg:.1f}°** |
"""

    shear_util = results.V_eq / results.phi_Vu if results.phi_Vu > 0 else 0.0
    update_results(
        phi_Vu_cap=results.phi_Vu,
        Vu_utilisation=shear_util,
    )

    summary_placeholder.markdown(summary_md)


if __name__ == "__main__":
    render_shear()
