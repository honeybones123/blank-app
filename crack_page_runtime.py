# crack_page_runtime.py
# ============================
# CRACK WIDTH – AS 3600:2018 Cl. 8.6.2
# ============================

import math

import streamlit as st

from state_and_helpers import (
    get_param,
    get_sync_callbacks,
    update_results,  # kept for contract
    get_widget_key_for_shared,
    TAB_KEYS,
    render_timing_mark,
)
from widgets_helpers import (
    apply_global_widget_css,
    apply_result_page_css,
    number_row,
    calcbox,
    render_jumpable_step,
    apply_step_summary_expander_css,
    page_divider,
    show_reo_message,
    label_with_hover,
    select_row,
    seed_widget_from_shared,
    render_page_explainer_expander,
    render_section_title,
    render_result_page_title,
    render_longitudinal_reo_rows,
    info_i_button,
    render_longitudinal_reo_row_config_controls,
    main_longitudinal_reo_pair_labels,
)
from ui_seamless_steps import inject_seamless_steps_css, render_clickable_summary_table, bind_summary_clicks
from ui.summary_rows import build_crack_summary_rows, mark_primary_summary_row
from crack_checks_helpers import build_crack_check_rows_from_state, pick_governing_check_row
from crack_side_view_diagram import (
    _resolve_crack_diagram_window,
    render_crack_moment_tab_plotly,
    render_crack_side_view_diagram,
)
from calculations.crack_control import (
    _nearest_key,
    average_active_bar_spacing_mm,
    calc_eps_diff,
    calc_sr_max,
    compute_crack_control_values,
    microstrain_to_strain,
    table_sigma_max_A,
    table_sigma_max_B,
)
from calculations.bending import bar_area_mm2
from application.contracts.concrete_crack_shrinkage import (
    AS5100WallCrackControlInput,
    C766CrackControlInput,
    C766EndRestraintInput,
    CrackControlMethod,
    RestraintType,
)
from calculations.concrete_crack_shrinkage_methods import (
    calculate_as5100_wall_crack_control,
    calculate_c766_crack_control,
    calculate_c766_end_restraint,
)
from engineering_page_sections.compact_check_inputs import (
    CheckInputCategory,
    CheckInputPanelConfig,
    compact_check_input_columns,
    compact_check_input_regions,
    format_dimensions,
    format_number,
    join_summary,
)


CRACK_METHOD_LABELS = {
    CrackControlMethod.EXISTING_AS3600.value: "Existing StructuralBase method (AS 3600:2018)",
    CrackControlMethod.AS5100_WALL.value: "AS 5100.5:2017 restrained wall (Clause 11.7.2)",
    CrackControlMethod.CIRIA_C766_EC2.value: "CIRIA C766 + EC2 equation method",
}

# Safe option lists for reinforcement inputs (same as inputs_page)
REO_BAR_DIAS = [10, 12, 16, 20, 24, 28, 32, 36, 40]
REO_COUNTS_0_12 = list(range(0, 13))  # 0..12 inclusive
REO_SPACINGS = [75, 100, 125, 150, 175, 200, 225, 250, 275, 300]
REO_LAYOUT_MODE = ["Count", "Spacing"]


# ------------------------------------------------------------
#  Small helpers / shared styling (same pattern as creep/shrinkage)
# ------------------------------------------------------------
from engineering_page_sections import crack_inputs as _crack_inputs_section
_seed_from_param = _crack_inputs_section._seed_from_param
_get_bottom_bar_diameter = _crack_inputs_section._get_bottom_bar_diameter
_get_bottom_bar_count = _crack_inputs_section._get_bottom_bar_count
_get_bottom_spacing = _crack_inputs_section._get_bottom_spacing
_col_heading = _crack_inputs_section._col_heading
_inject_calcbox_css = _crack_inputs_section._inject_calcbox_css
_crack_inputs_section.bind_runtime(globals())


def _method_number(label: str, key: str, shared_key: str, default: float, sync_callbacks, **kwargs) -> float:
    if key not in st.session_state:
        st.session_state[key] = float(get_param(shared_key, default))
    return float(st.number_input(label, key=key, on_change=sync_callbacks[key], **kwargs))


def _render_crack_method_selector(sync_callbacks) -> str:
    """Render the existing method widget from the shared compact input owner."""

    method_options = list(CRACK_METHOD_LABELS)
    method_current = str(
        get_param(
            "crack_control_method",
            CrackControlMethod.EXISTING_AS3600.value,
        )
    )
    if method_current not in method_options:
        method_current = CrackControlMethod.EXISTING_AS3600.value
    return str(
        st.selectbox(
            "Calculation method",
            options=method_options,
            index=method_options.index(method_current),
            format_func=lambda value: CRACK_METHOD_LABELS[value],
            key="crack_method",
            on_change=sync_callbacks["crack_method"],
        )
    )


def _render_as5100_wall_method(sync_callbacks):
    st.caption("AS 5100.5:2017 incorporating Amendment No. 1 - Clause 11.7.2")
    c1, c2 = st.columns(2)
    with c1:
        thickness = _method_number(
            "Wall thickness (mm)", "crack_wall_thickness", "crack_wall_thickness_mm", 600.0,
            sync_callbacks, min_value=1.0, step=25.0,
        )
        area = _method_number(
            "Provided horizontal area per face (mm²/m)", "crack_wall_area",
            "crack_wall_horizontal_area_per_face", 2750.0, sync_callbacks, min_value=0.0, step=50.0,
        )
    with c2:
        if "crack_wall_base_zone" not in st.session_state:
            st.session_state["crack_wall_base_zone"] = bool(get_param("crack_wall_in_base_zone", False))
        in_base_zone = st.checkbox(
            "Base zone (height equal to wall thickness)",
            key="crack_wall_base_zone",
            on_change=sync_callbacks["crack_wall_base_zone"],
        )
        spacing = _method_number(
            "Provided vertical spacing (mm)", "crack_wall_spacing",
            "crack_wall_vertical_spacing_mm", 150.0, sync_callbacks, min_value=1.0, step=25.0,
        )
    result = calculate_as5100_wall_crack_control(
        AS5100WallCrackControlInput(
            wall_thickness_mm=thickness,
            provided_horizontal_area_per_face_mm2_per_m=area,
            provided_vertical_spacing_mm=spacing,
            in_base_zone=in_base_zone,
        )
    )
    m1, m2, m3 = st.columns(3)
    m1.metric("Required per face", f"{result.required_area_per_face_mm2_per_m:,.0f} mm²/m")
    m2.metric("Maximum spacing", f"{result.maximum_spacing_mm:,.0f} mm")
    m3.metric("Status", "PASS" if result.passes else "FAIL")
    st.info(result.warnings[0])
    update_results(
        "crack_method",
        {
            "method": result.method.value,
            "reference": f"{result.reference.document} {result.reference.edition}, Clause {result.reference.clause}",
            "required_area_per_face_mm2_per_m": result.required_area_per_face_mm2_per_m,
            "maximum_spacing_mm": result.maximum_spacing_mm,
            "area_utilisation": result.area_utilisation,
            "passes": result.passes,
            "warnings": list(result.warnings),
        },
    )
    return result


def _render_c766_method(sync_callbacks):
    st.caption("CIRIA C766 equation path; temperature and restraint are explicit designer inputs.")
    restraint_options = [
        RestraintType.CONTINUOUS_EDGE.value,
        RestraintType.END.value,
        RestraintType.INTERNAL.value,
    ]
    restraint_current = str(get_param("crack_c766_restraint_type", restraint_options[0]))
    if restraint_current not in restraint_options:
        restraint_current = restraint_options[0]
    restraint = st.selectbox(
        "Restraint type",
        options=restraint_options,
        index=restraint_options.index(restraint_current),
        format_func=lambda value: value.replace("_", " ").title(),
        key="crack_c766_restraint",
        on_change=sync_callbacks["crack_c766_restraint"],
    )
    if restraint == RestraintType.END.value:
        c1, c2, c3 = st.columns(3)
        with c1:
            alpha_e = _method_number("Effective modular ratio αe", "crack_c766_alpha_e", "crack_c766_modular_ratio", 7.0, sync_callbacks, min_value=0.000001)
            coefficient_k = _method_number("Non-uniform stress coefficient k", "crack_c766_k", "crack_c766_non_uniform_k", 0.65, sync_callbacks, min_value=0.000001)
            coefficient_kc = _method_number("Stress-distribution coefficient kc", "crack_c766_kc", "crack_c766_stress_distribution_kc", 1.0, sync_callbacks, min_value=0.000001)
        with c2:
            fctk = _method_number("Characteristic tensile strength at cracking (MPa)", "crack_c766_fctk", "crack_c766_characteristic_tensile_mpa", 2.0, sync_callbacks, min_value=0.000001)
            rho_total = _method_number("Total reinforcement / tension-area ratio", "crack_c766_rho_total", "crack_c766_total_reinforcement_ratio", 0.01, sync_callbacks, min_value=0.000001, format="%.5f")
            es_mpa = float(get_param("Es", 200_000.0))
            st.caption(f"Reinforcement modulus Es = {es_mpa:,.0f} MPa (shared material input)")
        with c3:
            cover = _method_number("Cover (mm)", "crack_c766_cover", "crack_c766_cover_mm", 45.0, sync_callbacks, min_value=0.0)
            diameter = _method_number("Bar diameter (mm)", "crack_c766_db", "crack_c766_bar_diameter_mm", 20.0, sync_callbacks, min_value=1.0)
            rho_eff = _method_number("Effective reinforcement ratio", "crack_c766_rho_eff", "crack_c766_effective_reinforcement_ratio", 0.01, sync_callbacks, min_value=0.000001, format="%.5f")
        end_result = calculate_c766_end_restraint(
            C766EndRestraintInput(
                effective_modular_ratio=alpha_e,
                non_uniform_stress_coefficient_k=coefficient_k,
                stress_distribution_coefficient_kc=coefficient_kc,
                characteristic_tensile_strength_at_cracking_mpa=fctk,
                reinforcement_modulus_mpa=es_mpa,
                reinforcement_ratio_total_to_tension_area=rho_total,
                cover_mm=cover,
                bar_diameter_mm=diameter,
                effective_reinforcement_ratio=rho_eff,
            )
        )
        m1, m2 = st.columns(2)
        m1.metric("Crack-inducing strain", f"{end_result.crack_inducing_strain * 1e6:,.0f} µε")
        m2.metric("Crack width", f"{(end_result.characteristic_crack_width_mm or 0.0):.3f} mm")
        st.warning(end_result.warnings[0])
        update_results(
            "crack_method",
            {
                "method": end_result.method.value,
                "restraint_type": restraint,
                "reference": f"{end_result.reference.document}, Equation 3.12 and Equations 3.21-3.23",
                "crack_inducing_strain": end_result.crack_inducing_strain,
                "maximum_crack_spacing_mm": end_result.maximum_crack_spacing_mm,
                "characteristic_crack_width_mm": end_result.characteristic_crack_width_mm,
                "warnings": list(end_result.warnings),
            },
        )
        return end_result
    from shrinkage import compute_shrinkage_components_for_crack_control

    shrinkage_components = compute_shrinkage_components_for_crack_control()
    epsca_early = float(shrinkage_components["autogenous_early"]) * 1e6
    epsca_long = float(shrinkage_components["autogenous_long_term"]) * 1e6
    drying = float(shrinkage_components["drying_long_term"])
    c1, c2, c3 = st.columns(3)
    with c1:
        t1 = _method_number("Early temperature drop T1 / ΔT (°C)", "crack_c766_t1", "crack_c766_t1_c", 46.1, sync_callbacks, min_value=0.0)
        t2 = _method_number("Long-term temperature change T2 (°C)", "crack_c766_t2", "crack_c766_t2_c", 20.0, sync_callbacks, min_value=0.0)
        alpha_micro = _method_number("Thermal expansion (µε/°C)", "crack_c766_alpha", "crack_c766_alpha_micro_per_c", 12.0, sync_callbacks, min_value=0.0)
    with c2:
        r1 = _method_number("Early restraint R1", "crack_c766_r1", "crack_c766_restraint_early", 0.676, sync_callbacks, min_value=0.0, max_value=1.0)
        r2 = _method_number("Medium-term restraint R2", "crack_c766_r2", "crack_c766_restraint_medium", 0.644, sync_callbacks, min_value=0.0, max_value=1.0)
        r3 = _method_number("Long-term restraint R3", "crack_c766_r3", "crack_c766_restraint_long", 0.644, sync_callbacks, min_value=0.0, max_value=1.0)
    with c3:
        ectu_micro = _method_number("Tensile strain capacity (µε)", "crack_c766_ectu", "crack_c766_tensile_capacity_micro", 70.0, sync_callbacks, min_value=0.0)
        st.metric(
            f"Calculated autogenous shrinkage at {shrinkage_components['early_age_days']:.0f} d",
            f"{epsca_early:.1f} µε",
        )
        st.metric(
            f"Calculated autogenous shrinkage at {shrinkage_components['age_days']:.0f} d",
            f"{epsca_long:.1f} µε",
        )
        st.metric("Calculated drying shrinkage", f"{drying * 1e6:.1f} µε")
        source_label = "EC2/C766" if shrinkage_components["method"] == "ec2_c766" else "AS 3600"
        st.caption(f"Calculated automatically from the Shrinkage page ({source_label} method).")
        st.caption("C766 creep-relaxation factors are applied automatically: K1 = 0.65 and K2 = 0.50.")
    g1, g2, g3 = st.columns(3)
    with g1:
        cover = _method_number("Cover (mm)", "crack_c766_cover", "crack_c766_cover_mm", 45.0, sync_callbacks, min_value=0.0)
    with g2:
        diameter = _method_number("Bar diameter (mm)", "crack_c766_db", "crack_c766_bar_diameter_mm", 20.0, sync_callbacks, min_value=1.0)
    with g3:
        rho_eff = _method_number("Effective reinforcement ratio", "crack_c766_rho_eff", "crack_c766_effective_reinforcement_ratio", 0.01, sync_callbacks, min_value=0.000001, format="%.5f")

    result = calculate_c766_crack_control(
        C766CrackControlInput(
            restraint_type=RestraintType(restraint),
            temperature_drop_early_c=t1,
            temperature_change_long_term_c=t2,
            thermal_expansion_per_c=alpha_micro * 1e-6,
            autogenous_shrinkage_early=epsca_early * 1e-6,
            autogenous_shrinkage_long_term=epsca_long * 1e-6,
            drying_shrinkage=drying,
            restraint_early=r1,
            restraint_medium=r2,
            restraint_long_term=r3,
            tensile_strain_capacity=ectu_micro * 1e-6,
            cover_mm=cover,
            bar_diameter_mm=diameter,
            effective_reinforcement_ratio=rho_eff,
        )
    )
    m1, m2, m3 = st.columns(3)
    m1.metric("Restrained strain", f"{result.restrained_strain * 1e6:,.0f} µε")
    m2.metric("Crack width", f"{(result.characteristic_crack_width_mm or 0.0):.3f} mm")
    m3.metric("Crack initiation", "YES" if result.crack_initiates else "NO")
    st.warning(result.warnings[0])
    update_results(
        "crack_method",
        {
            "method": result.method.value,
            "reference": f"{result.reference.document}, {result.reference.clause}",
            "restrained_strain": result.restrained_strain,
            "crack_initiates": result.crack_initiates,
            "crack_inducing_strain": result.crack_inducing_strain,
            "maximum_crack_spacing_mm": result.maximum_crack_spacing_mm,
            "characteristic_crack_width_mm": result.characteristic_crack_width_mm,
            "shrinkage_source_method": shrinkage_components["method"],
            "autogenous_shrinkage_early": epsca_early * 1e-6,
            "autogenous_shrinkage_long_term": epsca_long * 1e-6,
            "drying_shrinkage": drying,
            "c766_relaxation_factor_early": 0.65,
            "c766_relaxation_factor_long_term": 0.50,
            "warnings": list(result.warnings),
        },
    )
    return result


def _render_retained_crack_diagram(sync_callbacks, crack_metrics) -> None:
    """Keep the standard crack/moment diagram control for every method."""
    st.markdown('<div id="crack-diagram-module" style="height:0;width:0;overflow:hidden;"></div>', unsafe_allow_html=True)
    seed_widget_from_shared("crack_diagram_view", "crack_diagram_panel", "Crack Diagram")
    st.radio(
        "Diagram view",
        options=["Crack Diagram", "Moment Diagram"],
        horizontal=True,
        key="crack_diagram_view",
        on_change=sync_callbacks["crack_diagram_view"],
        label_visibility="collapsed",
    )
    panel = str(st.session_state.get("crack_diagram_view", "Crack Diagram") or "Crack Diagram")
    if panel == "Moment Diagram":
        render_crack_moment_tab_plotly()
    else:
        render_crack_side_view_diagram(st.session_state, crack_metrics=crack_metrics)


def _render_as5100_method_cards(result) -> None:
    page_divider()
    render_section_title("Calculation Checks")
    design_thickness = float(result.calculation_thickness_per_face_mm)
    ratio = float(result.required_ratio)
    area_md = rf"""
**Required horizontal reinforcement per face — AS 5100.5 Clause 11.7.2**

\(t_d = {design_thickness:.0f}\,\text{{mm per face}}\)

\(A_{{s,req}} = {ratio:.3f}\,t_d\,(1000) = {result.required_area_per_face_mm2_per_m:,.0f}\,\text{{mm}}^2/\text{{m per face}}\)

Provided: \({result.provided_area_per_face_mm2_per_m:,.0f}\,\text{{mm}}^2/\text{{m per face}}\)
"""
    render_jumpable_step(
        uid="crk_as5100_area",
        title="Check 1 — Horizontal reinforcement per face",
        summary_md=f"Required {result.required_area_per_face_mm2_per_m:,.0f} mm²/m; provided {result.provided_area_per_face_mm2_per_m:,.0f} mm²/m",
        body_fn=lambda: calcbox(area_md, status="pass" if result.area_passes else "fail"),
        expanded=bool(st.session_state.get("step_open_crk_as5100_area", False)),
        status=result.area_passes,
    )
    spacing_md = rf"""
**Spacing check**

Provided vertical spacing: \({float(result.provided_spacing_mm or 0.0):.0f}\,\text{{mm}}\)

Maximum permitted spacing: \({result.maximum_spacing_mm:.0f}\,\text{{mm}}\)
"""
    render_jumpable_step(
        uid="crk_as5100_spacing",
        title="Check 2 — Reinforcement spacing",
        summary_md=f"Provided {float(result.provided_spacing_mm or 0.0):.0f} mm; maximum {result.maximum_spacing_mm:.0f} mm",
        body_fn=lambda: calcbox(spacing_md, status="pass" if result.spacing_passes else "fail"),
        expanded=bool(st.session_state.get("step_open_crk_as5100_spacing", False)),
        status=result.spacing_passes,
    )


def _render_c766_method_cards(result, restraint_type: str) -> None:
    page_divider()
    render_section_title("Calculation Checks")
    crack_width = float(result.characteristic_crack_width_mm or 0.0)
    spacing = float(result.maximum_crack_spacing_mm or 0.0)
    strain = float(getattr(result, "crack_inducing_strain", 0.0) or 0.0)
    strain_md = rf"""
**Restrained-deformation strain — CIRIA C766 ({restraint_type.replace('_', ' ').title()})**

Crack-inducing strain: \(\varepsilon_{{cr}} = {strain * 1e6:,.0f}\,\mu\varepsilon\)

Maximum crack spacing: \(s_{{r,max}} = {spacing:,.0f}\,\text{{mm}}\)
"""
    render_jumpable_step(
        uid="crk_c766_strain",
        title="Check 1 — Restrained-deformation strain",
        summary_md=f"Crack-inducing strain {strain * 1e6:,.0f} µε; spacing {spacing:,.0f} mm",
        body_fn=lambda: calcbox(strain_md, status=None),
        expanded=bool(st.session_state.get("step_open_crk_c766_strain", False)),
        status=None,
    )
    width_md = rf"""
**Characteristic crack width — EC2 equation path**

\(w_k = s_{{r,max}}\,\varepsilon_{{cr}} = {crack_width:.3f}\,\text{{mm}}\)

This is an equation-path result; corrected CIRIA spreadsheet parity is not claimed.
"""
    render_jumpable_step(
        uid="crk_c766_width",
        title="Check 2 — Characteristic crack width",
        summary_md=f"Calculated crack width {crack_width:.3f} mm",
        body_fn=lambda: calcbox(width_md, status=None),
        expanded=bool(st.session_state.get("step_open_crk_c766_width", False)),
        status=None,
    )


def _render_method_summary(render_explainer, rows, key_prefix: str) -> None:
    render_page_explainer_expander(render_explainer)
    clicked_uid = render_clickable_summary_table(rows, key_prefix=key_prefix)
    if clicked_uid:
        st.session_state[f"step_open_{clicked_uid}"] = True
    bind_summary_clicks()














# ------------------------------------------------------------
#  MAIN RENDER FUNCTION
# ------------------------------------------------------------
def render_crack():
    page_title_placeholder = st.empty()
    render_timing_mark("crack_page.runtime.start")
    # Hydrate widget keys from shared BEFORE rendering widgets (prevents 0/default after restore)
    # Handle cross-page navigation from Inputs page
    from jump_nav import get_jump_uid
    get_jump_uid()
    
    apply_global_widget_css()
    apply_result_page_css()
    _inject_calcbox_css()
    apply_step_summary_expander_css()
    inject_seamless_steps_css()
    sync_callbacks = get_sync_callbacks()  # keeps contract with Inputs page

    # --------------------------------------------------------
    # Page title
    # --------------------------------------------------------
    def _render_crack_explainer() -> None:
        method_current = str(get_param("crack_control_method", CrackControlMethod.EXISTING_AS3600.value))
        if method_current not in CRACK_METHOD_LABELS:
            method_current = CrackControlMethod.EXISTING_AS3600.value
        if method_current == CrackControlMethod.AS5100_WALL.value:
            st.markdown(
                "AS 5100.5:2017 Clause 11.7.2 restrained-wall horizontal reinforcement check. "
                "Strength and Clause 11.7.1 remain separate design gates."
            )
            return
        if method_current == CrackControlMethod.CIRIA_C766_EC2.value:
            st.markdown(
                "CIRIA C766 / EC2 restrained-deformation equation path. Temperature changes and "
                "restraint factors are explicit designer inputs; corrected spreadsheet parity is not claimed."
            )
            return
        st.markdown(
            """
This page checks flexural crack control in reinforced concrete beams in accordance with **AS 3600:2018 Clause 8.6.2**, using:

- **Table method (no direct crack width)** — limiting steel stress from Tables 8.6.2.2(A)–(B)
- **Direct crack-width calculation** — per Clause 8.6.2.3:
"""
        )
        
        st.latex(r"w = s_{r,\max}\left(\varepsilon_{sm}-\varepsilon_{cm}\right)\le w'_{\max}")
        
        st.markdown(
            """
The aim is to verify that cracking is **controlled** so that durability and appearance are not impaired.

You can:

- **See behaviour (cracks)** in the side-view diagram once results are available
- **Inspect cause (moment)** in the moment diagram—SLS bending moment, using the same cached data as Beam Actions when that page has been run
"""
        )

    selected_method = str(get_param("crack_control_method", CrackControlMethod.EXISTING_AS3600.value))

    if selected_method == CrackControlMethod.EXISTING_AS3600.value:
        with page_title_placeholder.container():
            render_result_page_title(
                "Crack width – AS 3600:2018",
                top_margin_rem=-0.80,
            )
    elif selected_method == CrackControlMethod.AS5100_WALL.value:
        with page_title_placeholder.container():
            render_result_page_title(
                "Wall crack control – AS 5100.5:2017",
                top_margin_rem=-0.80,
            )
        summary_placeholder = st.empty()
        diagram_placeholder = st.empty()
        page_divider()
        wall_thickness = get_param("crack_wall_thickness_mm", None)
        wall_area = get_param("crack_wall_horizontal_area_per_face", None)
        wall_spacing = get_param("crack_wall_vertical_spacing_mm", None)
        with compact_check_input_regions(
            st,
            CheckInputPanelConfig(
                page_slug="crack_as5100",
                categories=(
                    CheckInputCategory(
                        "method",
                        "Calculation method",
                        CRACK_METHOD_LABELS[selected_method],
                        lambda: None,
                        icon="≡",
                    ),
                    CheckInputCategory(
                        "wall_reinforcement",
                        "Wall geometry & reinforcement",
                        join_summary(
                            f"thickness {format_number(wall_thickness, 'mm')}",
                            f"area {format_number(wall_area, 'mm²/m')}",
                            f"spacing {format_number(wall_spacing, 'mm')}",
                        ),
                        lambda: None,
                        icon="▣",
                    ),
                ),
            ),
        ) as (method_region, wall_region):
            with method_region:
                _render_crack_method_selector(sync_callbacks)
            with wall_region:
                method_result = _render_as5100_wall_method(sync_callbacks)
        area_status = "PASS" if method_result.area_passes else "FAIL"
        spacing_status = "PASS" if method_result.spacing_passes else "FAIL"
        rows = [
            {"uid": "crk_as5100_area", "title": "Horizontal reinforcement per face", "capacity": f"{method_result.provided_area_per_face_mm2_per_m:,.0f} mm²/m", "action": f"Required ≥ {method_result.required_area_per_face_mm2_per_m:,.0f} mm²/m", "util": f"{(method_result.area_utilisation or 0.0) * 100:.0f}%", "status": area_status, "ok": bool(method_result.area_passes)},
            {"uid": "crk_as5100_spacing", "title": "Reinforcement spacing", "capacity": f"{float(method_result.provided_spacing_mm or 0.0):.0f} mm", "action": f"Maximum {method_result.maximum_spacing_mm:.0f} mm", "util": "", "status": spacing_status, "ok": bool(method_result.spacing_passes)},
        ]
        with summary_placeholder.container():
            _render_method_summary(_render_crack_explainer, rows, "crack_as5100_summary")
        with diagram_placeholder.container():
            _render_retained_crack_diagram(
                sync_callbacks,
                {"sr_max_mm": float(method_result.provided_spacing_mm or method_result.maximum_spacing_mm), "w_calc_mm": 0.0, "wmax_mm": 0.3},
            )
        _render_as5100_method_cards(method_result)
        return
    else:
        with page_title_placeholder.container():
            render_result_page_title(
                "Restrained-deformation crack control – CIRIA C766 / EC2",
                top_margin_rem=-0.80,
            )
        summary_placeholder = st.empty()
        diagram_placeholder = st.empty()
        page_divider()
        restraint_summary = str(
            get_param(
                "crack_c766_restraint_type",
                RestraintType.CONTINUOUS_EDGE.value,
            )
        ).replace("_", " ").title()
        with compact_check_input_regions(
            st,
            CheckInputPanelConfig(
                page_slug="crack_c766",
                categories=(
                    CheckInputCategory(
                        "method",
                        "Calculation method",
                        CRACK_METHOD_LABELS[selected_method],
                        lambda: None,
                        icon="≡",
                    ),
                    CheckInputCategory(
                        "restraint_parameters",
                        "Restraint & crack parameters",
                        restraint_summary,
                        lambda: None,
                        icon="↔",
                    ),
                ),
            ),
        ) as (method_region, restraint_region):
            with method_region:
                _render_crack_method_selector(sync_callbacks)
            with restraint_region:
                method_result = _render_c766_method(sync_callbacks)
        restraint_type = str(get_param("crack_c766_restraint_type", RestraintType.CONTINUOUS_EDGE.value))
        crack_width = float(method_result.characteristic_crack_width_mm or 0.0)
        rows = [
            {"uid": "crk_c766_strain", "title": "Crack-inducing strain", "capacity": f"{float(method_result.crack_inducing_strain) * 1e6:,.0f} µε", "action": restraint_type.replace("_", " ").title(), "util": "", "status": "INFO", "ok": True, "is_informational": True},
            {"uid": "crk_c766_width", "title": "Characteristic crack width", "capacity": f"{crack_width:.3f} mm", "action": "EC2 equation path", "util": "", "status": "INFO", "ok": True, "is_informational": True},
        ]
        with summary_placeholder.container():
            _render_method_summary(_render_crack_explainer, rows, "crack_c766_summary")
        with diagram_placeholder.container():
            _render_retained_crack_diagram(
                sync_callbacks,
                {"sr_max_mm": float(method_result.maximum_crack_spacing_mm or 0.0), "w_calc_mm": crack_width, "wmax_mm": 0.3},
            )
        _render_c766_method_cards(method_result, restraint_type)
        return

    # --------------------------------------------------------
    # Reserve space for top summary then diagram (filled after calculations)
    # --------------------------------------------------------
    summary_placeholder = st.empty()
    diagram_placeholder = st.empty()

    # --------------------------------------------------------
    render_timing_mark("crack_page.runtime.inputs.start")
    # Inputs
    # --------------------------------------------------------
    page_divider()

    _crack_b_summary = get_param("b", None)
    _crack_D_summary = get_param("D", None)
    _crack_fc_summary = get_param("fc", None)
    _crack_cover_summary = get_param("cover_bot", None)
    _crack_bot_count = get_param("nb_or_s_bot_1", get_param("nb_bot", None))
    _crack_bot_dia = get_param("db_bot_1", get_param("db_bot", None))
    _crack_exposure_summary = str(get_param("exposure_class", "Not provided") or "Not provided")
    _crack_member_summary = str(get_param("crack_member_type", "Not provided") or "Not provided")
    top_method, top_c1, top_c2, top_c3 = compact_check_input_columns(
        st,
        CheckInputPanelConfig(
            page_slug="crack",
            categories=(
                CheckInputCategory(
                    "method",
                    "Calculation method",
                    CRACK_METHOD_LABELS.get(selected_method, selected_method),
                    lambda: None,
                    icon="≡",
                ),
                CheckInputCategory(
                    "section_material",
                    "Section & material",
                    join_summary(
                        format_dimensions(_crack_b_summary, _crack_D_summary),
                        f"f'c {format_number(_crack_fc_summary, 'MPa')}",
                        f"cover {format_number(_crack_cover_summary, 'mm')}",
                    ),
                    lambda: None,
                    icon="▣",
                ),
                CheckInputCategory(
                    "reinforcement",
                    "Tension reinforcement",
                    (
                        "Not provided"
                        if _crack_bot_count is None or _crack_bot_dia is None
                        else f"{float(_crack_bot_count):.0f}-N{float(_crack_bot_dia):.0f}"
                    ),
                    lambda: None,
                    icon="●",
                ),
                CheckInputCategory(
                    "criteria",
                    "Crack-control parameters",
                    join_summary(
                        _crack_exposure_summary,
                        _crack_member_summary,
                        CRACK_METHOD_LABELS.get(selected_method, selected_method),
                    ),
                    lambda: None,
                    icon="≡",
                ),
            ),
        ),
    )

    with top_method:
        _render_crack_method_selector(sync_callbacks)

    # --- Materials & Geometry ---
    with top_c1:
        _col_heading("Materials & Geometry")
        
        # Materials first
        fc_seed = _seed_from_param("fc", 32.0)

        fc = number_row(
            "Concrete strength f'c (MPa)",
            "crack_fc",
            fc_seed,
            sync_callbacks,
            help_text="Characteristic compressive strength of concrete at 28 days.",
        )
        Ec = float(get_param("Ec", 30000.0) or 30000.0)
        Es = float(get_param("Es", 200000.0) or 200000.0)
        
        # Then Geometry
        b_seed = _seed_from_param("b", 300.0)
        D_seed = _seed_from_param("D", 600.0)
        cover_seed = _seed_from_param("cover_bot", 40.0)

        b = number_row(
            "Section width b (mm)",
            "crack_b",
            b_seed,
            sync_callbacks,
            help_text="Section width (cross-section dimension perpendicular to bending axis).",
        )
        D = number_row(
            "Overall depth D (mm)",
            "crack_D",
            D_seed,
            sync_callbacks,
            help_text="Overall section depth (cross-section dimension in the direction of loading).",
        )
        c = number_row(
            "Clear cover to tensile bars c (mm)",
            "crack_cover_bot",
            cover_seed,
            sync_callbacks,
            help_text="Clear concrete cover to the centroid of the bottom tensile reinforcement layer.",
        )

    # --- Bottom (web) longitudinal reinforcement ---
    with top_c2:
        _cr_sec_shape_ui = str(get_param("sec_shape", "RECT") or "RECT")
        _cr_bot_heading, _ = main_longitudinal_reo_pair_labels(_cr_sec_shape_ui, variant="sentence_lower")
        w_rowgap_bot = get_widget_key_for_shared("rowgap_bot", prefix="crack_") or "crack_rowgap_bot"
        seed_widget_from_shared(w_rowgap_bot, "rowgap_bot", 60.0)
        rowgap_bot_val = float(st.session_state.get(w_rowgap_bot, get_param("rowgap_bot", 60.0)))

        _crack_bot_title_col, _crack_bot_info_col = st.columns([0.92, 0.08], vertical_alignment="center")
        with _crack_bot_title_col:
            _col_heading(_cr_bot_heading.title())
        with _crack_bot_info_col:
            with info_i_button(help_text="Row count and vertical gap between reinforcement layers."):
                render_longitudinal_reo_row_config_controls(
                    page_prefix="crack",
                    section="bot",
                    sync_callbacks=sync_callbacks,
                    rowgap_widget_key=w_rowgap_bot,
                    rowgap_default=rowgap_bot_val,
                    rowgap_help_text="Clear vertical gap between reinforcement rows (mm).",
                    sec_shape=_cr_sec_shape_ui,
                )

        render_longitudinal_reo_rows(
            page_prefix="crack",
            section="bot",
            sync_callbacks=sync_callbacks,
            layout_modes=REO_LAYOUT_MODE,
            count_options=REO_COUNTS_0_12,
            spacing_options=REO_SPACINGS,
            dia_options=REO_BAR_DIAS,
            single_column=True,
            sec_shape=_cr_sec_shape_ui,
        )

    # --- Crack Criteria ---
    with top_c3:
        _col_heading("Crack criteria")
        
        # Exposure class (shared)
        exp_options = ["A1", "A2", "B1", "B2", "C1", "C2"]
        exp_current = st.session_state.get("exposure_class", "B1")
        if exp_current not in exp_options:
            exp_current = "B1"

        col1, col2 = st.columns([1, 2])
        with col1:
            label_with_hover(
                "Exposure class",
                "Exposure classification to AS 3600 – controls allowable crack width and durability detailing.",
            )
        with col2:
            st.selectbox(
                "",
                options=exp_options,
                index=exp_options.index(exp_current),
                key="crack_exposure_class",
                on_change=sync_callbacks["crack_exposure_class"],
                label_visibility="collapsed",
            )

        col1, col2 = st.columns([1, 2])
        with col1:
            label_with_hover("Resultant action", "Type of loading: primarily flexure (typical beams) or primarily tension (tension members). Affects which table values are used in crack control checks.")
        with col2:
            member_current = st.session_state.get("crack_member_type", "Primarily flexure")
            member_type = st.selectbox(
                "",
                options=["Primarily flexure", "Primarily tension"],
                index=0 if member_current == "Primarily flexure" else 1,
                key="inputs_crack_member_type",
                on_change=sync_callbacks["inputs_crack_member_type"],
                label_visibility="collapsed",
            )
        
        # k1 and k2 parameters (editable, in criteria column)
        col1, col2 = st.columns([1, 2])
        with col1:
            label_with_hover("k₁ (bond coefficient)", "Bond coefficient: 0.8 for deformed bars, 1.6 for plain bars. Used in crack spacing calculations.")
        with col2:
            k1_val = float(st.session_state.get("crack_k1", 0.8))
            k1_options = [0.8, 1.6]
            k1 = st.selectbox(
                "",
                options=k1_options,
                index=k1_options.index(k1_val) if k1_val in k1_options else 0,
                format_func=lambda x: "Deformed bars (k₁ = 0.8)" if abs(x - 0.8) < 1e-9 else "Plain bars (k₁ = 1.6)",
                key="inputs_crack_k1",
                on_change=sync_callbacks["inputs_crack_k1"],
                label_visibility="collapsed",
            )

        # k2 (strain distribution factor) - default follows member type but only as a seed
        k2_seed = 0.5 if member_type == "Primarily flexure" else 1.0
        k2 = number_row(
            "k₂ (strain distribution factor)",
            "crack_k2",
            float(st.session_state.get("crack_k2", k2_seed)),
            sync_callbacks,
            help_text="Strain distribution factor used in crack spacing/width model. Default 0.5 for typical RC flexural members; adjust only if using a different assumed strain distribution per your chosen method.",
        )

    # --------------------------------------------------------
    render_timing_mark("crack_page.runtime.compute.start")
    # Adopted values for crack checks (derived / linked; sources in calc steps below)
    # --------------------------------------------------------
    Ast = _seed_from_param("Ast_bot", bar_area_mm2(3, 20.0))
    db = _get_bottom_bar_diameter()
    spacing = _get_bottom_spacing()

    if spacing is None:
        spacing = 200.0

    # σ_sr from bending page (SLS steel stress)
    # Contract-safe: if missing, trigger bending compute (publishes via update_results only)
    results = st.session_state.get("results", {})
    sec_shape = str(get_param("sec_shape", "RECT") or "RECT")
    tension_face = "bottom"
    # T/I crack checks should use canonical resolved active-bar outputs from crack_core.
    if sec_shape in ("T", "I"):
        Ast = float(st.session_state.get("crack_Ast_active_mm2", Ast) or Ast)
        dias = list(st.session_state.get("crack_active_bar_dias", []) or [])
        db = float(max(dias) if dias else db or 0.0)
        spacing_vals = list(st.session_state.get("crack_active_bar_spacing_mm", []) or [])
        active_spacing = average_active_bar_spacing_mm(spacing_vals)
        if active_spacing is not None:
            spacing = active_spacing
        b = float(st.session_state.get("crack_tension_width_mm", b) or b)
        tension_face = str(st.session_state.get("crack_tension_face", "bottom") or "bottom")
        c = float(get_param("cover_top" if tension_face == "top" else "cover_bot", c) or c)

    sigma_sr_raw = results.get("sigma_s_sls", st.session_state.get("sigma_s_sls", None))

    if sigma_sr_raw is None:
        try:
            from bending_core import (
                _compute_bending_capacity,
                compute_sls_bending_values_from_state,
            )
            from state_and_helpers import recalc_derived_values

            recalc_derived_values()
            _compute_bending_capacity()
            compute_sls_bending_values_from_state(
                publish=True
            )  # publishes sigma_s_sls via update_results
        except Exception:
            pass

    sigma_sr = float(results.get("sigma_s_sls", st.session_state.get("sigma_s_sls", 0.0)))

    if results.get("sigma_s_sls", st.session_state.get("sigma_s_sls", None)) is None:
        st.warning(
            "Crack page could not auto-load SLS steel stress (sigma_s_sls). "
            "Check bending compute pipeline (compute_bending_results / update_results)."
        )

    phi_ce = float(st.session_state.get("phi_cc_t") or 0.0)
    eps_cs_micro = float(st.session_state.get("eps_cs_total_micro") or 0.0)
    eps_cs = microstrain_to_strain(eps_cs_micro)

    # --------------------------------------------------------
    # Effective area in tension and ρ_eff
    # --------------------------------------------------------
    # Get db for calculations (from helper or fallback)
    if db is None:
        db = 20.0  # Fallback

    # --------------------------------------------------------
    # 8.6.2.2 – Table-based max steel stress
    # --------------------------------------------------------
    # Read wmax_char_limit from shared state (widget removed, but value still in shared state)
    wmax_choice = float(get_param("wmax_char_limit", 0.3))

    if member_type == "Primarily tension":
        table_basis = "Table 8.6.2.2(A) – bar diameter"
    else:
        table_basis = (
            "Max of Table 8.6.2.2(A) (bar diameter) "
            "and 8.6.2.2(B) (spacing)"
        )

    fsy_seed = _seed_from_param("fsy", 500.0)
    fsy = fsy_seed
    crack_values = compute_crack_control_values(
        b=b,
        D=D,
        c=c,
        db=db,
        spacing=spacing,
        Ast=Ast,
        fc=fc,
        Ec=Ec,
        Es=Es,
        fsy=fsy,
        wmax_choice=wmax_choice,
        member_type=member_type,
        sigma_sr=sigma_sr,
        phi_ce=phi_ce,
        eps_cs=eps_cs,
        k1=k1,
        k2=k2,
        crack_tension_face=tension_face,
    )
    Aceff = crack_values["Aceff"]
    rho_eff = crack_values["rho_eff"]
    fct_eff = crack_values["fct_eff"]
    ne = crack_values["ne"]
    sigma_table_A = crack_values["sigma_table_A"]
    sigma_table_B = crack_values["sigma_table_B"]
    sigma_table_combined = crack_values["sigma_table_combined"]
    sigma_08fsy = crack_values["sigma_08fsy"]
    sigma_allow_table = crack_values["sigma_allow_table"]
    utilisation_table = crack_values["utilisation_table"]
    passes_table = crack_values["passes_table"]
    eps_diff = crack_values["eps_diff"]
    sr_max = crack_values["sr_max"]
    w_calc = crack_values["w_calc"]
    utilisation_w = crack_values["utilisation_w"]
    passes_w = crack_values["passes_w"]

    # --------------------------------------------------------
    # TOP SUMMARY TABLE
    # --------------------------------------------------------
    with summary_placeholder.container():
        # Same top-of-summary pattern as creep.py: explainer row, then table.
        render_page_explainer_expander(_render_crack_explainer)

        crack_pack = build_crack_check_rows_from_state(st.session_state)
        rows = build_crack_summary_rows(crack_pack.get("rows") or [])
        gov = pick_governing_check_row(rows)
        gov_uid = (gov or {}).get("uid")
        rows = mark_primary_summary_row(rows, gov_uid)
        update_results("crack", {"rows": rows})
        
        clicked_uid = render_clickable_summary_table(rows, key_prefix="crack_summary")
        
        # Handle clicked summary row: expand step and set pending scroll
        if clicked_uid:
            open_key = f"step_open_{clicked_uid}"
            st.session_state[open_key] = True
        
        bind_summary_clicks()

    with diagram_placeholder.container():
        st.markdown(
            """
<style>
div[data-testid="stVerticalBlock"]:has(> div[data-testid="stElementContainer"] #crack-diagram-module) [data-testid="stRadio"] {
    margin-top: 0.15rem !important;
    margin-bottom: 0.4rem !important;
}
div[data-testid="stVerticalBlock"]:has(> div[data-testid="stElementContainer"] #crack-diagram-module) [data-testid="stPlotlyChart"] {
    margin-bottom: 0.1rem !important;
}
</style>
<div id="crack-diagram-module" style="height:0;width:0;overflow:hidden;" aria-hidden="true"></div>
""",
            unsafe_allow_html=True,
        )
        seed_widget_from_shared("crack_diagram_view", "crack_diagram_panel", "Crack Diagram")
        _gov_col, _spacer = st.columns([2.2, 3.0])
        with _gov_col:
            if bool(_resolve_crack_diagram_window(st.session_state).get("multi")):
                st.markdown(
                    '<p style="margin:0 0 0.35rem 0;font-size:0.82rem;color:#6b7280;">'
                    "Displaying governing span"
                    "</p>",
                    unsafe_allow_html=True,
                )
        st.radio(
            "Diagram view",
            options=["Crack Diagram", "Moment Diagram"],
            horizontal=True,
            key="crack_diagram_view",
            on_change=sync_callbacks["crack_diagram_view"],
            label_visibility="collapsed",
        )
        panel = str(st.session_state.get("crack_diagram_view", "Crack Diagram") or "Crack Diagram")
        if panel == "Moment Diagram":
            render_crack_moment_tab_plotly()
        else:
            render_crack_side_view_diagram(
                st.session_state,
                crack_metrics={
                    "sr_max_mm": float(sr_max),
                    "w_calc_mm": float(w_calc),
                    "wmax_mm": float(wmax_choice),
                },
            )

    # --------------------------------------------------------
    render_timing_mark("crack_page.runtime.checks.start")
    # Steps: 4-step format matching bending/shear
    # --------------------------------------------------------
    page_divider()
    
    render_section_title("Crack Checks")
    
    # Check 1 — Inputs & limits
    limits_md = rf"""
**Crack width limit**

Characteristic crack width limit: \(w'_{{\max}} = {wmax_choice:.3f}\,\text{{mm}}\)

This value is chosen based on:
- Exposure classification
- Surface finish requirements
- Durability considerations

Typical values:
- 0.2 mm for aggressive environments or appearance-critical surfaces
- 0.3 mm for normal exposure
- 0.4 mm for less critical surfaces

**Member type**

Resultant action: **{member_type}**

This affects which table method limits apply (Clause 8.6.2.2).
"""
    
    def step_1_body():
        calcbox(limits_md, status=None)
    
    render_jumpable_step(
        uid="crk_step_1",
        title="Check 1 — Inputs & crack limits",
        summary_md=f"w'max = {wmax_choice:.3f} mm",
        body_fn=step_1_body,
        expanded=bool(st.session_state.get("step_open_crk_step_1", False)),
        status=None,
    )
    
    # Step 2 — Table method (σ_sr check)
    table_details_md = rf"""
**Concept**

Instead of calculating a crack width directly, Clause 8.6.2.2 limits the **steel stress**
on the cracked section:

- For members **primarily in tension**:  
  \[
  \sigma_{{sr}} \le \sigma_{{\text{{max,A}}}} \quad \text{{(Table 8.6.2.2(A))}}
  \]
- For members **primarily in flexure**:  
  \[
  \sigma_{{sr}} \le \max\left(\sigma_{{\text{{max,A}}}}, \sigma_{{\text{{max,B}}}}\right)
  \]
  where \(\sigma_{{\text{{max,B}}}}\) comes from **Table 8.6.2.2(B)**.

Under direct loading, \(\sigma_{{sr,1}} \le 0.8 f_{{sy}}\).

**Current input**

- Bar diameter: \(d_b = {db:.1f}\,\text{{mm}}\) — *Derived on Crack page from reinforcement layout (bar diameter).*
- Spacing: \(s = {spacing:.0f}\,\text{{mm}}\) — *Derived on Crack page from reinforcement layout (row spacing \(s_r\)).*
- Crack width limit: \(w'_{{\max}} = {wmax_choice:.1f}\,\text{{mm}}\)  
- SLS steel stress: \(\sigma_{{sr}} = {sigma_sr:.1f}\,\text{{MPa}}\) — *Source: Bending page (SLS steel stress).*
- Yield strength: \(f_{{sy}} \approx {fsy:.0f}\,\text{{MPa}}\)

**From tables**

- Table 8.6.2.2(A): \(\sigma_{{\text{{max,A}}}} \approx {sigma_table_A:.1f}\,\text{{MPa}}\)  
- Table 8.6.2.2(B): \(\sigma_{{\text{{max,B}}}} \approx {sigma_table_B:.1f}\,\text{{MPa}}\)  
- Combined table limit ({table_basis}):  
  \[
  \sigma_{{\text{{table}}}} = {sigma_table_combined:.1f}\,\text{{MPa}}
  \]
- 0.8\(f_{{sy}}\) limit:
  \[
  0.8 f_{{sy}} \approx {sigma_08fsy:.1f}\,\text{{MPa}}
  \]

Overall allowable steel stress:

\[
\sigma_{{\text{{allow}}}} = \min\left(\sigma_{{\text{{table}}}},\,0.8 f_{{sy}}\right)
= {sigma_allow_table:.1f}\,\text{{MPa}}
\]

**Check**

\[
\frac{{\sigma_{{sr}}}}{{\sigma_{{\text{{allow}}}}}}
= \frac{{{sigma_sr:.1f}}}{{{sigma_allow_table:.1f}}}
\approx {utilisation_table:.2f}
\quad\Rightarrow\quad
\text{{{"PASS" if passes_table else "FAIL"}}}
"""
    
    def step_2_body():
        calcbox(table_details_md, status="pass" if passes_table else "fail")
    
    render_jumpable_step(
        uid="crk_step_2",
        title="Check 2 — Table method",
        summary_md=f"σ_sr = {sigma_sr:.1f} MPa vs {sigma_allow_table:.1f} MPa → {'PASS' if passes_table else 'FAIL'}",
        body_fn=step_2_body,
        expanded=bool(st.session_state.get("step_open_crk_step_2", False)),
            status="pass" if passes_table else "fail",
    )
    
    # Check 3 — Direct crack width
    step1_rho_eff_md = rf"""
**Step 1 – Effective reinforcement ratio**

Effective area in tension (simplified):

\[
A_{{c,\text{{eff}}}} \approx b \, h_{{\text{{eff}}}}
\quad\Rightarrow\quad
A_{{c,\text{{eff}}}} \approx {Aceff:.0f}\,\text{{mm}}^2
\]

\[
\rho_{{\text{{eff}}}} = \frac{{A_{{s,t}}}}{{A_{{c,\text{{eff}}}}}}
= \frac{{{Ast:.0f}}}{{{Aceff:.0f}}}
\approx {rho_eff:.4f}
\]

*Source: \(A_{{s,t}} = {Ast:.0f}\,\text{{mm}}^2\) — resolved from active tension reinforcement geometry.*
"""

    step2_eps_md = rf"""
**Step 2 – Difference in mean strain** \(\varepsilon_{{sm}} - \varepsilon_{{cm}}\)

From Cl. 8.6.2.3(2):

\[
\varepsilon_{{sm}} - \varepsilon_{{cm}}
= \frac{{\sigma_{{sr}}}}{{E_s}}
- \frac{{0.6 f_{{ct,\text{{eff}}}}}}{{E_s \rho_{{\text{{eff}}}}}}\left(1 + n_e \rho_{{\text{{eff}}}}\right)
+ \varepsilon_{{cs}}
\ge 0.6 \frac{{\sigma_{{sr}}}}{{E_s}}
\]

With:

- \(\sigma_{{sr}} = {sigma_sr:.1f}\,\text{{MPa}}\) — *Source: Bending page (SLS steel stress).*
- \(f_{{ct,\text{{eff}}}} = {fct_eff:.2f}\,\text{{MPa}}\) — *Source: \(0.6\sqrt{{f'c}}\) from concrete strength used for crack control.*
- \(E_s = {Es:.0f}\,\text{{MPa}},\ E_c = {Ec:.0f}\,\text{{MPa}}\)  
- \(\varphi_{{ce}} = {phi_ce:.2f}\) — *Source: Creep page (\(\varphi_{{cc}}(t)\)).*
- \(n_e = (1 + \varphi_{{ce}}) E_s/E_c \approx {ne:.2f}\)  
- \(\varepsilon_{{cs}} \approx {eps_cs_micro:.1f}\times 10^{{-6}}\) — *Source: Shrinkage page (\(\varepsilon_{{cs,total}}\)).*

This gives:

\[
\varepsilon_{{sm}} - \varepsilon_{{cm}} \approx {eps_diff:.3e}
\]
"""

    step3_srmax_md = rf"""
**Step 3 – Maximum crack spacing**

\[
s_{{r,\max}} = 3.4 c + 0.3 k_1 k_2 \frac{{d_b}}{{\rho_{{\text{{eff}}}}}}
\]

Using:

- \(c = {c:.1f}\,\text{{mm}},\ d_b = {db:.1f}\,\text{{mm}}\) — *\(d_b\) from Crack page reinforcement layout.*
- \(k_1 = {k1:.2f},\ k_2 = {k2:.2f}\)

\[
s_{{r,\max}} \approx {sr_max:.1f}\,\text{{mm}}
\]
"""

    step4_w_md = rf"""
**Step 4 – Crack width**

\[
w = s_{{r,\max}}(\varepsilon_{{sm}} - \varepsilon_{{cm}})
\approx {sr_max:.1f} \times {eps_diff:.3e}
\approx {w_calc:.3f}\,\text{{mm}}
\]

Calculated capacity (allowable crack width):

\[
w'_{{\max}} = {wmax_choice:.1f}\,\text{{mm}}, \quad
\frac{{w}}{{w'_{{\max}}}} \approx {utilisation_w:.2f}
\Rightarrow\ \text{{{"PASS" if passes_w else "FAIL"}}}
"""
    
    def step_3_body():
        calcbox(step1_rho_eff_md, status=None)
        calcbox(step2_eps_md, status=None)
        calcbox(step3_srmax_md, status=None)
        calcbox(step4_w_md, status="pass" if passes_w else "fail")
    
    render_jumpable_step(
        uid="crk_step_3",
        title="Check 3 — Direct crack width",
        summary_md=f"w = {w_calc:.3f} mm ≤ {wmax_choice:.3f} mm → {'PASS' if passes_w else 'FAIL'}",
        body_fn=step_3_body,
        expanded=bool(st.session_state.get("step_open_crk_step_3", False)),
            status="pass" if passes_w else "fail",
    )
    
    # Check 4 — Governing result + interpretation
    governing_md = rf"""
**Governing outcome**

Both checks must pass for crack control to be satisfied:

1. **Table method**: \(\sigma_{{sr}} = {sigma_sr:.1f}\,\text{{MPa}} \le {sigma_allow_table:.1f}\,\text{{MPa}}\) → **{"PASS" if passes_table else "FAIL"}**

2. **Direct calculation**: \(w = {w_calc:.3f}\,\text{{mm}} \le {wmax_choice:.1f}\,\text{{mm}}\) → **{"PASS" if passes_w else "FAIL"}**

**Overall result**: **{"PASS" if (passes_table and passes_w) else "FAIL"}**

Both the table method and direct calculation checks must pass for the crack control requirement to be satisfied.
"""
    
    def step_4_body():
        calcbox(governing_md, status=passes_table and passes_w)
    
    render_jumpable_step(
        uid="crk_step_4",
        title="Check 4 — Governing outcome",
        summary_md="Both checks must pass (table stress + direct width)",
        body_fn=step_4_body,
        expanded=bool(st.session_state.get("step_open_crk_step_4", False)),
        status=passes_table and passes_w,
        )

    # --------------------------------------------------------
    # Publish crack-control results (optional, for dashboards)
    # --------------------------------------------------------
    update_results(
        # keep existing outputs (used by Inputs summary today)
        sigma_allow_table=sigma_allow_table,
        sigma_sr=float(sigma_sr),
        w_calc=w_calc,
        wmax_char=wmax_choice,
        passes_table=passes_table,
        passes_w=passes_w,

        # ALSO publish standardized dashboard keys (already in RESULT_KEYS)
        crack_width=w_calc,
        crack_sr_max_mm=float(sr_max),
        crack_utilisation=utilisation_w,
    )
    
    # Handle scroll after all content is rendered (for cross-page navigation from Inputs)
    from jump_nav import scroll_to_jump_after_render
    scroll_to_jump_after_render()


# For compatibility with whatever app.py calls
def render_crack_control():
    """Entry point used by app.py – delegates to render_crack()."""
    render_crack()


def render_crack_page():
    """Optional alias if imported elsewhere."""
    render_crack()
