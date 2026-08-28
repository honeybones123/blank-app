# creep_page_runtime.py
# ============================
# CREEP – AS 3600:2018 Cl. 3.1.8
# ============================

import streamlit as st

from state_runtime_gateway import (
    get_param,
    get_sync_callbacks,
    update_results,  # kept for contract
)
from widgets_helpers import (
    apply_result_page_css,
    render_page_explainer_expander,
    render_result_page_title,
    page_divider,
)
from ui_seamless_steps import bind_summary_clicks
from jump_nav import scroll_to_jump_after_render
from calculations.creep_shrinkage import (
    basic_creep_coeff,
    calc_k2_creep,
    calc_k3,
    calc_k4,
    calc_k5,
    calc_k6,
    creep_alpha2_from_th,
    creep_coefficient_value,
    creep_strain_values,
    creep_closest_th as _closest_th,
    exposed_perimeter_geometry_values,
    final_creep_coeff_table,
    sustained_creep_stress_mpa,
)
from inputs_application.time_dependent_engineering_state import (
    resolve_time_dependent_engineering_state,
)
from inputs_application.authoritative_check_packs import current_authoritative_family
from inputs_application.time_dependent_presentation import (
    resolve_time_dependent_family_values,
)
from engineering_page_sections.creep_inputs import render_creep_inputs
from engineering_page_sections.creep_visualisation import (
    CreepVisualisationView,
    render_creep_visualisation,
)
from engineering_page_sections.creep_summary import (
    render_creep_explainer,
    render_creep_summary,
)
from engineering_page_sections.creep_page_shell import CreepPageShell
from engineering_page_sections.creep_page_context import build_creep_page_snapshot
from reporting.creep_report_projection import build_creep_report_projection
from engineering_page_sections.creep_checks_context import CreepChecksSnapshot
from engineering_page_sections.creep_checks import render_creep_checks
from engineering_page_sections.page_reference_sidebar import (
    build_creep_reference,
    render_page_reference_sidebar,
)


def _inject_calcbox_css():
    """Style markdown blockquotes as blue calc boxes (same feel as shear/deflection)."""
    st.markdown(
        """
<style>
blockquote {
  border-left: 4px solid #1f77b4 !important;
  background-color: rgba(31, 119, 180, 0.08) !important;
  padding: 0.75rem 1rem !important;
  margin: 0.5rem 0 0.75rem 0 !important;
  border-radius: 0 0.35rem 0.35rem 0 !important;
  color: #1a1a1a !important;
  opacity: 1 !important;
  font-size: 0.9rem !important;
  line-height: 1.35 !important;
}
blockquote * {
  color: #1a1a1a !important;
  opacity: 1 !important;
}
blockquote p {
  margin-bottom: 0.5rem !important;
}
blockquote p:last-child {
  margin-bottom: 0 !important;
}
/* Tight stack: calc section heading → expandable step */
p.calc-section-heading-tight {
  margin: 0.35rem 0 0 0 !important;
  font-weight: 600 !important;
  font-size: 1rem !important;
  line-height: 1.25 !important;
}
div[data-testid="stMarkdownContainer"]:has(p.calc-section-heading-tight) {
  margin-bottom: 0 !important;
}
div.element-container:has(div[data-testid="stMarkdownContainer"]:has(p.calc-section-heading-tight)) {
  margin-bottom: 0 !important;
}
</style>
""",
        unsafe_allow_html=True,
    )




# ------------------------------------------------------------
#  COMPUTE FUNCTION (no UI rendering)
# ------------------------------------------------------------
def compute_creep_results(publish: bool = True) -> dict:
    """
    Compute creep results without UI rendering.

    Args:
        publish: If True, update results via update_results(). Always True for now.

    Returns:
        dict with computed results
    """
    authoritative = current_authoritative_family(st.session_state, "creep")
    if authoritative is not None:
        if publish:
            update_results(
                **build_creep_report_projection(authoritative).result_updates(
                    include_strain=False
                )
            )
        return {
            "phi_cc_t": authoritative.get("phi_cc_t"),
            "phi_cc_star_table": authoritative.get("phi_cc_star_table"),
            "eps_cc_micro": authoritative.get("eps_cc_micro"),
            "creep_steps": ["Authoritative Inputs V2 calculation"],
        }

    # Geometry, materials and sustained actions must come from the committed
    # Beam Inputs snapshot.  Session mirrors can be stale after fragment edits
    # or Design Brain Apply and are not an engineering authority.
    committed_engineering = resolve_time_dependent_engineering_state(
        st.session_state
    ).values
    b = float(committed_engineering.get("b", 300.0) or 300.0)
    D = float(committed_engineering.get("D", 600.0) or 600.0)
    fc = float(committed_engineering.get("fc", 32.0) or 32.0)
    Ec = float(committed_engineering.get("Ec", 30000.0) or 30000.0)

    # Read creep parameters (use defaults if not in shared state)
    env_option = get_param("env_option", "Temperate inland environment")
    t_creep = get_param("t_creep", 365.0)
    age_at_loading = get_param("age_at_loading", 28.0)
    stress_ratio = float(committed_engineering.get("stress_ratio", 0.0) or 0.0)
    sigma0 = committed_engineering.get("sustained_sigma_cs_mpa")

    # Read faces option (default to beam)
    faces_option = get_param("member_faces_exposed", "Beam – three faces exposed")

    # Calculate geometry
    geometry_values = exposed_perimeter_geometry_values(b, D, faces_option)
    Ag = geometry_values["Ag"]
    ue = geometry_values["ue"]
    th_raw = geometry_values["th_raw"]
    th_table = _closest_th(th_raw)

    # Calculate creep coefficients
    phi_cc_b = basic_creep_coeff(fc)
    k2 = calc_k2_creep(t_creep, th_table)
    k3 = calc_k3(age_at_loading)
    k4 = calc_k4(env_option)
    k5 = calc_k5(fc, th_table, k4)
    k6 = calc_k6(stress_ratio)

    phi_cc_t = creep_coefficient_value(
        k2=k2,
        k3=k3,
        k4=k4,
        k5=k5,
        k6=k6,
        phi_cc_b=phi_cc_b,
    )
    phi_cc_star_table = final_creep_coeff_table(fc, env_option, th_table)

    authoritative = current_authoritative_family(st.session_state, "creep")
    if authoritative is not None:
        phi_cc_b = float(authoritative["phi_cc_b"])
        k2 = float(authoritative["k2_creep"])
        k3 = float(authoritative["k3_creep"])
        k4 = float(authoritative["k4_creep"])
        k5 = float(authoritative["k5_creep"])
        k6 = float(authoritative["k6_creep"])
        phi_cc_t = float(authoritative["phi_cc_t"])
        phi_cc_star_table = float(authoritative["phi_cc_star_table"])

    # Calculate strain (stress ratio is derived from sustained action and section modulus)
    sigma0 = sustained_creep_stress_mpa(
        sustained_sigma_cs_mpa=sigma0,
        stress_ratio=stress_ratio,
        fc_mpa=fc,
    )
    creep_strain = creep_strain_values(phi_cc_t, sigma0, Ec)
    eps_cc = creep_strain["eps_cc"]
    eps_cc_micro = creep_strain["eps_cc_micro"]

    if authoritative is not None:
        sigma0 = float(authoritative["sustained_sigma_cs_mpa"])
        eps_cc = float(authoritative["eps_cc"])
        eps_cc_micro = float(authoritative["eps_cc_micro"])

    # Update results if publish=True
    if publish:
        update_results(
            **build_creep_report_projection(
                {
                    "phi_cc_t": phi_cc_t,
                    "phi_cc_star_table": phi_cc_star_table,
                    "k2_creep": k2,
                    "k3_creep": k3,
                    "k4_creep": k4,
                    "k5_creep": k5,
                    "k6_creep": k6,
                }
            ).result_updates(include_strain=False)
        )

    # Build steps list (placeholder)
    steps = ["(Detailed steps not available for this module yet)"]

    return {
        "phi_cc_t": phi_cc_t,
        "phi_cc_star_table": phi_cc_star_table,
        "eps_cc_micro": eps_cc_micro,
        "creep_steps": steps,
    }


# ------------------------------------------------------------
#  MAIN RENDER FUNCTION
# ------------------------------------------------------------
def render_creep():
    creep_page_title = CreepPageShell.reserve_title(st)
    apply_result_page_css()
    _inject_calcbox_css()
    sync_callbacks = get_sync_callbacks()  # keeps contract with Inputs page
    committed_engineering = resolve_time_dependent_engineering_state(
        st.session_state
    )
    engineering_values = committed_engineering.values

    def engineering_value(name: str, default):
        return engineering_values.get(name, get_param(name, default))

    creep_page_title.render(lambda: render_result_page_title("Creep"))

    # --------------------------------------------------------
    # Reserve space for top summary table (will be filled after calculations)
    # --------------------------------------------------------
    summary_values = compute_creep_results(publish=True)
    render_creep_summary(
        summary_values=summary_values,
        bind_clicks=bind_summary_clicks,
    )
    render_page_explainer_expander(lambda: render_creep_explainer(st))
    page_divider()
    creep_visualisation_slot = CreepPageShell.reserve_visualisation(st)

    # --------------------------------------------------------
    creep_inputs = render_creep_inputs(
        engineering_state=engineering_values,
        sync_callbacks=sync_callbacks,
    )
    creep_page_snapshot = build_creep_page_snapshot(
        engineering_state=engineering_values,
        diagram_state=st.session_state,
        summary_values=summary_values,
        published_results=st.session_state.get("results") or {},
        inputs=creep_inputs,
    )
    b = creep_page_snapshot.inputs.width_mm
    D = creep_page_snapshot.inputs.depth_mm
    fc = creep_page_snapshot.inputs.concrete_strength_mpa
    Ec = creep_page_snapshot.inputs.concrete_modulus_mpa
    faces_option = creep_page_snapshot.inputs.faces_exposed
    env_option = creep_page_snapshot.inputs.environment
    t_creep = creep_page_snapshot.inputs.time_after_loading_days
    age_at_loading = creep_page_snapshot.inputs.age_at_loading_days


    page_divider()

    # --------------------------------------------------------
    # Derived geometry: Ag, u_e, t_h
    # --------------------------------------------------------
    geometry_values = exposed_perimeter_geometry_values(b, D, faces_option)
    Ag = geometry_values["Ag"]
    ue = geometry_values["ue"]
    th_raw = geometry_values["th_raw"]
    # For Fig. 3.1.8.3 & Table 3.1.8.3, th is rounded to 100 / 200 / 400 mm
    th_table = _closest_th(th_raw)

    # --------------------------------------------------------
    # Creep coefficients & strain
    # --------------------------------------------------------
    stress_ratio = float(engineering_value("stress_ratio", 0.0) or 0.0)
    sustained_mstar = float(
        engineering_value("sustained_Mstar_kNm", 0.0) or 0.0
    )
    sustained_sigma_cs = float(
        engineering_value("sustained_sigma_cs_mpa", 0.0) or 0.0
    )
    sustained_z = float(
        engineering_value("sustained_section_modulus_mm3", 0.0) or 0.0
    )
    sustained_fibre = str(
        engineering_value("sustained_compression_fibre", "top") or "top"
    )

    phi_cc_b = basic_creep_coeff(fc)
    k2 = calc_k2_creep(t_creep, th_table)
    k3 = calc_k3(age_at_loading)
    k4 = calc_k4(env_option)
    k5 = calc_k5(fc, th_table, k4)
    k6 = calc_k6(stress_ratio)

    phi_cc_t = creep_coefficient_value(
        k2=k2,
        k3=k3,
        k4=k4,
        k5=k5,
        k6=k6,
        phi_cc_b=phi_cc_b,
    )
    phi_cc_star_table = final_creep_coeff_table(fc, env_option, th_table)

    sigma0 = sustained_creep_stress_mpa(
        sustained_sigma_cs_mpa=sustained_sigma_cs,
        stress_ratio=stress_ratio,
        fc_mpa=fc,
    )
    # Safety check: prevent division by zero if Ec is 0 (shouldn't happen, but protect against stale state)
    if Ec == 0 or Ec is None:
        Ec = 30000.0  # Default value from SHARED_DEFAULTS
    creep_strain = creep_strain_values(phi_cc_t, sigma0, Ec)
    eps_cc = creep_strain["eps_cc"]
    eps_cc_micro = creep_strain["eps_cc_micro"]

    # The visible summary and detailed calculations must use the same
    # revision-matched V2 family result as Inputs and Design Brain.  The local
    # calculation above remains an explicit fallback only while no current
    # authoritative publication exists.
    displayed = resolve_time_dependent_family_values(
        st.session_state,
        family="creep",
        fallback={
            "phi_cc_b": phi_cc_b,
            "k2_creep": k2,
            "k3_creep": k3,
            "k4_creep": k4,
            "k5_creep": k5,
            "k6_creep": k6,
            "phi_cc_t": phi_cc_t,
            "phi_cc_star_table": phi_cc_star_table,
            "sustained_sigma_cs_mpa": sigma0,
            "eps_cc": eps_cc,
            "eps_cc_micro": eps_cc_micro,
        },
    )
    phi_cc_b = float(displayed["phi_cc_b"])
    k2 = float(displayed["k2_creep"])
    k3 = float(displayed["k3_creep"])
    k4 = float(displayed["k4_creep"])
    k5 = float(displayed["k5_creep"])
    k6 = float(displayed["k6_creep"])
    phi_cc_t = float(displayed["phi_cc_t"])
    phi_cc_star_table = float(displayed["phi_cc_star_table"])
    sigma0 = float(displayed["sustained_sigma_cs_mpa"])
    eps_cc = float(displayed["eps_cc"])
    eps_cc_micro = float(displayed["eps_cc_micro"])

    # Publish only the same resolved values displayed by this page.  Other
    # pages therefore cannot receive a page-local value while this summary is
    # showing the authoritative V2 result.
    update_results(
        **build_creep_report_projection(
            {
                "phi_cc_t": phi_cc_t,
                "phi_cc_star_table": phi_cc_star_table,
                "k2_creep": k2,
                "k3_creep": k3,
                "k4_creep": k4,
                "k5_creep": k5,
                "k6_creep": k6,
                "eps_cc": eps_cc,
                "eps_cc_micro": eps_cc_micro,
            }
        ).result_updates(include_strain=True)
    )

    # --------------------------------------------------------
    # Top-of-page clickable summary table (render in placeholder)
    # --------------------------------------------------------
    creep_visualisation_slot.render(
        lambda: render_creep_visualisation(
            st,
            view=CreepVisualisationView(
                state=creep_page_snapshot.diagram_state,
                phi_cc_t=phi_cc_t,
            ),
        )
    )

    # --------------------------------------------------------
    # Calculation sections — three tabs (t_h + k₂ merged; ϕ_cc; ε_cc)
    # --------------------------------------------------------
    creep_checks_snapshot = CreepChecksSnapshot(
        width_mm=b,
        depth_mm=D,
        gross_area_mm2=Ag,
        faces_exposed=faces_option,
        exposed_perimeter_mm=ue,
        notional_thickness_raw_mm=th_raw,
        notional_thickness_table_mm=th_table,
        time_after_loading_days=t_creep,
        age_at_loading_days=age_at_loading,
        concrete_strength_mpa=fc,
        concrete_modulus_mpa=Ec,
        environment=env_option,
        alpha2=creep_alpha2_from_th(th_table),
        phi_cc_b=phi_cc_b,
        k2=k2,
        k3=k3,
        k4=k4,
        k5=k5,
        k6=k6,
        phi_cc_t=phi_cc_t,
        phi_cc_star_table=phi_cc_star_table,
        sustained_moment_knm=sustained_mstar,
        sustained_compression_fibre=sustained_fibre,
        sustained_section_modulus_mm3=sustained_z,
        sustained_stress_mpa=sigma0,
        sustained_stress_ratio=stress_ratio,
        eps_cc=eps_cc,
        eps_cc_micro=eps_cc_micro,
    )
    creep_reference_values = dict(creep_page_snapshot.engineering_state)
    creep_reference_values.update(
        {
            "b": creep_checks_snapshot.width_mm,
            "D": creep_checks_snapshot.depth_mm,
            "fc": creep_checks_snapshot.concrete_strength_mpa,
            "Ec": creep_checks_snapshot.concrete_modulus_mpa,
            "member_faces_exposed": creep_checks_snapshot.faces_exposed,
            "env_option": creep_checks_snapshot.environment,
            "t_creep": creep_checks_snapshot.time_after_loading_days,
            "age_at_loading": creep_checks_snapshot.age_at_loading_days,
            "sustained_Mstar_kNm": creep_checks_snapshot.sustained_moment_knm,
            "sls_Mstar": creep_page_snapshot.engineering_state.get(
                "sls_Mstar",
                creep_page_snapshot.engineering_state.get("SLS_M_pos"),
            ),
            "sustained_sigma_cs_mpa": creep_checks_snapshot.sustained_stress_mpa,
            "sustained_section_modulus_mm3": creep_checks_snapshot.sustained_section_modulus_mm3,
            "stress_ratio": creep_checks_snapshot.sustained_stress_ratio,
            "sustained_compression_fibre": creep_checks_snapshot.sustained_compression_fibre,
            "A_g": creep_checks_snapshot.gross_area_mm2,
            "ue": creep_checks_snapshot.exposed_perimeter_mm,
            "th_raw": creep_checks_snapshot.notional_thickness_raw_mm,
            "th_table": creep_checks_snapshot.notional_thickness_table_mm,
            "reference_source": "Beam Inputs",
        }
    )
    render_page_reference_sidebar(build_creep_reference(creep_reference_values))
    render_creep_checks(st, creep_checks_snapshot)

    scroll_to_jump_after_render()
