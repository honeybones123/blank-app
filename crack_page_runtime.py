# crack_page_runtime.py
# ============================
# CRACK WIDTH – AS 3600:2018 Cl. 8.6.2
# ============================

import streamlit as st

from state_and_helpers import (
    get_param,
    get_sync_callbacks,
    update_results,  # kept for contract
    render_timing_mark,
)
from widgets_helpers import (
    apply_result_page_css,
    apply_step_summary_expander_css,
    page_divider,
    render_result_page_title,
)
from ui_seamless_steps import inject_seamless_steps_css
from ui.summary_rows import build_crack_summary_rows, mark_primary_summary_row
from crack_checks_helpers import build_crack_check_rows_from_state, pick_governing_check_row
from calculations.crack_control import (
    average_active_bar_spacing_mm,
    compute_crack_control_values,
    microstrain_to_strain,
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
    compact_check_input_regions,
    format_number,
    join_summary,
)
from engineering_page_sections.crack_as3600_checks import (
    render_as3600_crack_checks,
)
from engineering_page_sections.crack_as3600_inputs import render_as3600_inputs
from engineering_page_sections.crack_checks_context import (
    CrackAs3600ChecksSnapshot,
    freeze_expanded_steps,
)
from engineering_page_sections.crack_method_checks import (
    render_as5100_method_checks,
    render_c766_method_checks,
)
from engineering_page_sections.crack_method_inputs import (
    C766EndInputValues,
    CRACK_METHOD_LABELS,
    render_as5100_wall_inputs,
    render_as5100_wall_result_metrics,
    render_c766_inputs,
    render_c766_result_metrics,
    render_crack_method_selector,
)
from engineering_page_sections.crack_page_context import (
    build_crack_page_snapshot,
)
from engineering_page_sections.crack_summary import render_crack_summary
from engineering_page_sections.crack_visualisation import (
    render_as3600_crack_diagrams,
    render_method_crack_diagrams,
)
from reporting.crack_report_projection import (
    project_as3600_results,
    project_as5100_wall_result,
    project_c766_end_result,
    project_c766_result,
)
from engineering_page_sections.page_reference_sidebar import (
    build_crack_reference,
    render_page_reference_sidebar,
)


# ------------------------------------------------------------
#  Small helpers / shared styling (same pattern as creep/shrinkage)
# ------------------------------------------------------------
from engineering_page_sections import crack_inputs as _crack_inputs_section
_seed_from_param = _crack_inputs_section._seed_from_param
_get_bottom_bar_diameter = _crack_inputs_section._get_bottom_bar_diameter
_get_bottom_spacing = _crack_inputs_section._get_bottom_spacing
_inject_calcbox_css = _crack_inputs_section._inject_calcbox_css


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
    
    apply_result_page_css()
    _inject_calcbox_css()
    apply_step_summary_expander_css()
    inject_seamless_steps_css()
    sync_callbacks = get_sync_callbacks()  # keeps contract with Inputs page

    # --------------------------------------------------------
    # Page title
    # --------------------------------------------------------
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
                mount_closed_bodies=True,
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
                render_crack_method_selector(sync_callbacks)
            with wall_region:
                wall_inputs = render_as5100_wall_inputs(sync_callbacks)
                method_result = calculate_as5100_wall_crack_control(
                    AS5100WallCrackControlInput(
                        wall_thickness_mm=wall_inputs.thickness_mm,
                        provided_horizontal_area_per_face_mm2_per_m=(
                            wall_inputs.horizontal_area_per_face_mm2_per_m
                        ),
                        provided_vertical_spacing_mm=(
                            wall_inputs.vertical_spacing_mm
                        ),
                        in_base_zone=wall_inputs.in_base_zone,
                    )
                )
                render_as5100_wall_result_metrics(method_result)
                update_results(
                    "crack_method",
                    project_as5100_wall_result(method_result).result_update(),
                )
        area_status = "PASS" if method_result.area_passes else "FAIL"
        spacing_status = "PASS" if method_result.spacing_passes else "FAIL"
        rows = [
            {"uid": "crk_as5100_area", "title": "Horizontal reinforcement per face", "capacity": f"{method_result.provided_area_per_face_mm2_per_m:,.0f} mm²/m", "action": f"Required ≥ {method_result.required_area_per_face_mm2_per_m:,.0f} mm²/m", "util": f"{(method_result.area_utilisation or 0.0) * 100:.0f}%", "status": area_status, "ok": bool(method_result.area_passes)},
            {"uid": "crk_as5100_spacing", "title": "Reinforcement spacing", "capacity": f"{float(method_result.provided_spacing_mm or 0.0):.0f} mm", "action": f"Maximum {method_result.maximum_spacing_mm:.0f} mm", "util": "", "status": spacing_status, "ok": bool(method_result.spacing_passes)},
        ]
        with summary_placeholder.container():
            render_crack_summary(
                st,
                method=selected_method,
                rows=rows,
                key_prefix="crack_as5100_summary",
                set_step_open=lambda uid: st.session_state.__setitem__(
                    f"step_open_{uid}", True
                ),
            )
        with diagram_placeholder.container():
            method_snapshot = build_crack_page_snapshot(
                method=selected_method,
                engineering_state={},
                diagram_state=st.session_state,
                summary_rows=rows,
                crack_metrics={
                    "sr_max_mm": float(
                        method_result.provided_spacing_mm
                        or method_result.maximum_spacing_mm
                    ),
                    "w_calc_mm": 0.0,
                    "wmax_mm": 0.3,
                },
            )
            render_method_crack_diagrams(
                st,
                diagram_state=method_snapshot.diagram_state,
                crack_metrics=method_snapshot.crack_metrics,
            )
        render_as5100_method_checks(
            st,
            result=method_result,
            expanded_steps={
                "crk_as5100_area": bool(
                    st.session_state.get("step_open_crk_as5100_area", False)
                ),
                "crk_as5100_spacing": bool(
                    st.session_state.get("step_open_crk_as5100_spacing", False)
                ),
            },
        )
        render_page_reference_sidebar(
            build_crack_reference(
                {
                    "crack_control_method": selected_method,
                    "crack_wall_thickness_mm": wall_inputs.thickness_mm,
                    "crack_wall_horizontal_area_per_face": wall_inputs.horizontal_area_per_face_mm2_per_m,
                    "crack_wall_vertical_spacing_mm": wall_inputs.vertical_spacing_mm,
                    "crack_wall_in_base_zone": wall_inputs.in_base_zone,
                    "reference_source": "Beam Inputs",
                }
            )
        )
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
                mount_closed_bodies=True,
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
                render_crack_method_selector(sync_callbacks)
            with restraint_region:
                restraint_seed = str(
                    get_param(
                        "crack_c766_restraint_type",
                        RestraintType.CONTINUOUS_EDGE.value,
                    )
                )
                shrinkage_components = None
                if restraint_seed != RestraintType.END.value:
                    from shrinkage import (
                        compute_shrinkage_components_for_crack_control,
                    )

                    shrinkage_components = (
                        compute_shrinkage_components_for_crack_control()
                    )
                method_inputs = render_c766_inputs(
                    sync_callbacks,
                    shrinkage_components=shrinkage_components,
                )
                if isinstance(method_inputs, C766EndInputValues):
                    method_result = calculate_c766_end_restraint(
                        C766EndRestraintInput(
                            effective_modular_ratio=(
                                method_inputs.effective_modular_ratio
                            ),
                            non_uniform_stress_coefficient_k=(
                                method_inputs.non_uniform_stress_coefficient
                            ),
                            stress_distribution_coefficient_kc=(
                                method_inputs.stress_distribution_coefficient
                            ),
                            characteristic_tensile_strength_at_cracking_mpa=(
                                method_inputs.characteristic_tensile_strength_mpa
                            ),
                            reinforcement_modulus_mpa=(
                                method_inputs.reinforcement_modulus_mpa
                            ),
                            reinforcement_ratio_total_to_tension_area=(
                                method_inputs.total_reinforcement_ratio
                            ),
                            cover_mm=method_inputs.cover_mm,
                            bar_diameter_mm=method_inputs.bar_diameter_mm,
                            effective_reinforcement_ratio=(
                                method_inputs.effective_reinforcement_ratio
                            ),
                        )
                    )
                    projection = project_c766_end_result(
                        method_result,
                        restraint_type=method_inputs.restraint_type,
                    )
                else:
                    method_result = calculate_c766_crack_control(
                        C766CrackControlInput(
                            restraint_type=RestraintType(
                                method_inputs.restraint_type
                            ),
                            temperature_drop_early_c=(
                                method_inputs.temperature_drop_early_c
                            ),
                            temperature_change_long_term_c=(
                                method_inputs.temperature_change_long_term_c
                            ),
                            thermal_expansion_per_c=(
                                method_inputs.thermal_expansion_microstrain_per_c
                                * 1e-6
                            ),
                            autogenous_shrinkage_early=float(
                                method_inputs.shrinkage_components[
                                    "autogenous_early"
                                ]
                            ),
                            autogenous_shrinkage_long_term=float(
                                method_inputs.shrinkage_components[
                                    "autogenous_long_term"
                                ]
                            ),
                            drying_shrinkage=float(
                                method_inputs.shrinkage_components[
                                    "drying_long_term"
                                ]
                            ),
                            restraint_early=method_inputs.restraint_early,
                            restraint_medium=method_inputs.restraint_medium,
                            restraint_long_term=method_inputs.restraint_long,
                            tensile_strain_capacity=(
                                method_inputs.tensile_strain_capacity_microstrain
                                * 1e-6
                            ),
                            cover_mm=method_inputs.cover_mm,
                            bar_diameter_mm=method_inputs.bar_diameter_mm,
                            effective_reinforcement_ratio=(
                                method_inputs.effective_reinforcement_ratio
                            ),
                        )
                    )
                    projection = project_c766_result(
                        method_result,
                        restraint_type=method_inputs.restraint_type,
                        shrinkage_components=method_inputs.shrinkage_components,
                    )
                render_c766_result_metrics(method_result)
                update_results("crack_method", projection.result_update())
        restraint_type = str(method_inputs.restraint_type)
        crack_width = float(method_result.characteristic_crack_width_mm or 0.0)
        rows = [
            {"uid": "crk_c766_strain", "title": "Crack-inducing strain", "capacity": f"{float(method_result.crack_inducing_strain) * 1e6:,.0f} µε", "action": restraint_type.replace("_", " ").title(), "util": "", "status": "INFO", "ok": True, "is_informational": True},
            {"uid": "crk_c766_width", "title": "Characteristic crack width", "capacity": f"{crack_width:.3f} mm", "action": "EC2 equation path", "util": "", "status": "INFO", "ok": True, "is_informational": True},
        ]
        with summary_placeholder.container():
            render_crack_summary(
                st,
                method=selected_method,
                rows=rows,
                key_prefix="crack_c766_summary",
                set_step_open=lambda uid: st.session_state.__setitem__(
                    f"step_open_{uid}", True
                ),
            )
        with diagram_placeholder.container():
            method_snapshot = build_crack_page_snapshot(
                method=selected_method,
                engineering_state={},
                diagram_state=st.session_state,
                summary_rows=rows,
                crack_metrics={
                    "sr_max_mm": float(
                        method_result.maximum_crack_spacing_mm or 0.0
                    ),
                    "w_calc_mm": crack_width,
                    "wmax_mm": 0.3,
                },
            )
            render_method_crack_diagrams(
                st,
                diagram_state=method_snapshot.diagram_state,
                crack_metrics=method_snapshot.crack_metrics,
            )
        render_c766_method_checks(
            st,
            result=method_result,
            restraint_type=restraint_type,
            expanded_steps={
                "crk_c766_strain": bool(
                    st.session_state.get("step_open_crk_c766_strain", False)
                ),
                "crk_c766_width": bool(
                    st.session_state.get("step_open_crk_c766_width", False)
                ),
            },
        )
        crack_reference_values = {
            "crack_control_method": selected_method,
            "crack_c766_restraint_type": method_inputs.restraint_type,
            "crack_c766_cover_mm": method_inputs.cover_mm,
            "crack_c766_bar_diameter_mm": method_inputs.bar_diameter_mm,
            "crack_c766_effective_reinforcement_ratio": method_inputs.effective_reinforcement_ratio,
            "reference_source": "Beam Inputs",
        }
        if isinstance(method_inputs, C766EndInputValues):
            crack_reference_values.update(
                {
                    "crack_c766_modular_ratio": method_inputs.effective_modular_ratio,
                    "crack_c766_non_uniform_k": method_inputs.non_uniform_stress_coefficient,
                    "crack_c766_stress_distribution_kc": method_inputs.stress_distribution_coefficient,
                    "crack_c766_characteristic_tensile_mpa": method_inputs.characteristic_tensile_strength_mpa,
                    "crack_c766_total_reinforcement_ratio": method_inputs.total_reinforcement_ratio,
                    "Es": method_inputs.reinforcement_modulus_mpa,
                }
            )
        else:
            c766_shrinkage = dict(
                method_inputs.shrinkage_components or {}
            )
            crack_reference_values.update(
                {
                    "crack_c766_t1_c": method_inputs.temperature_drop_early_c,
                    "crack_c766_t2_c": method_inputs.temperature_change_long_term_c,
                    "crack_c766_alpha_micro_per_c": method_inputs.thermal_expansion_microstrain_per_c,
                    "crack_c766_restraint_early": method_inputs.restraint_early,
                    "crack_c766_restraint_medium": method_inputs.restraint_medium,
                    "crack_c766_restraint_long": method_inputs.restraint_long,
                    "crack_c766_tensile_capacity_micro": method_inputs.tensile_strain_capacity_microstrain,
                    "crack_c766_autogenous_early_micro": float(
                        c766_shrinkage.get("autogenous_early", 0.0)
                    )
                    * 1e6,
                    "crack_c766_autogenous_long_micro": float(
                        c766_shrinkage.get("autogenous_long_term", 0.0)
                    )
                    * 1e6,
                }
            )
        render_page_reference_sidebar(build_crack_reference(crack_reference_values))
        return

    # --------------------------------------------------------
    # Publish the current authoritative AS 3600 summary before the heavier
    # inputs and diagrams.  The page boundary has already refreshed this pack.
    # --------------------------------------------------------
    crack_pack = build_crack_check_rows_from_state(st.session_state)
    rows = build_crack_summary_rows(crack_pack.get("rows") or [])
    governing_row = pick_governing_check_row(rows)
    rows = mark_primary_summary_row(rows, (governing_row or {}).get("uid"))
    update_results("crack", {"rows": rows})
    render_crack_summary(
        st,
        method=selected_method,
        rows=rows,
        key_prefix="crack_summary",
        set_step_open=lambda uid: st.session_state.__setitem__(
            f"step_open_{uid}", True
        ),
    )
    diagram_placeholder = st.empty()

    # --------------------------------------------------------
    render_timing_mark("crack_page.runtime.inputs.start")
    # Inputs
    # --------------------------------------------------------
    inputs = render_as3600_inputs(
        selected_method=selected_method,
        sync_callbacks=sync_callbacks,
    )
    fc = inputs.concrete_strength_mpa
    Ec = inputs.concrete_modulus_mpa
    Es = inputs.steel_modulus_mpa
    b = inputs.width_mm
    D = inputs.depth_mm
    c = inputs.clear_cover_mm
    member_type = inputs.member_type
    k1 = inputs.bond_coefficient
    k2 = inputs.strain_distribution_factor

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

    with diagram_placeholder.container():
        page_snapshot = build_crack_page_snapshot(
            method=selected_method,
            engineering_state=crack_values,
            diagram_state=st.session_state,
            summary_rows=rows,
            crack_metrics={
                "sr_max_mm": float(sr_max),
                "w_calc_mm": float(w_calc),
                "wmax_mm": float(wmax_choice),
            },
        )
        render_as3600_crack_diagrams(
            st,
            diagram_state=page_snapshot.diagram_state,
            crack_metrics=page_snapshot.crack_metrics,
        )

    # --------------------------------------------------------
    render_timing_mark("crack_page.runtime.checks.start")
    checks_snapshot = CrackAs3600ChecksSnapshot(
        width_limit_mm=float(wmax_choice),
        member_type=str(member_type),
        bar_diameter_mm=float(db),
        bar_spacing_mm=float(spacing),
        steel_stress_mpa=float(sigma_sr),
        steel_yield_strength_mpa=float(fsy),
        table_basis=str(table_basis),
        table_limit_a_mpa=float(sigma_table_A),
        table_limit_b_mpa=float(sigma_table_B),
        table_combined_limit_mpa=float(sigma_table_combined),
        yield_limit_mpa=float(sigma_08fsy),
        allowable_stress_mpa=float(sigma_allow_table),
        table_utilisation=float(utilisation_table),
        table_passes=bool(passes_table),
        effective_tension_area_mm2=float(Aceff),
        tension_steel_area_mm2=float(Ast),
        effective_reinforcement_ratio=float(rho_eff),
        concrete_tensile_strength_mpa=float(fct_eff),
        steel_modulus_mpa=float(Es),
        concrete_modulus_mpa=float(Ec),
        creep_coefficient=float(phi_ce),
        effective_modular_ratio=float(ne),
        shrinkage_microstrain=float(eps_cs_micro),
        strain_difference=float(eps_diff),
        cover_mm=float(c),
        bond_coefficient=float(k1),
        strain_distribution_factor=float(k2),
        maximum_crack_spacing_mm=float(sr_max),
        crack_width_mm=float(w_calc),
        width_utilisation=float(utilisation_w),
        width_passes=bool(passes_w),
        expanded_steps=freeze_expanded_steps(
            {
                uid: bool(st.session_state.get(f"step_open_{uid}", False))
                for uid in (
                    "crk_step_1",
                    "crk_step_2",
                    "crk_step_3",
                    "crk_step_4",
                )
            }
        ),
    )
    crack_reference_values = dict(page_snapshot.engineering_state)
    crack_reference_values.update(
        {
            "crack_control_method": selected_method,
            "sec_shape": get_param("sec_shape", "RECT"),
            "b": b,
            "D": D,
            "bf": get_param("bf", None),
            "tf": get_param("tf", None),
            "bw": get_param("bw", None),
            "tw": get_param("tw", None),
            "fc": fc,
            "Ec": Ec,
            "Es": Es,
            "cover_mm": c,
            "crack_tension_face": tension_face,
            "crack_member_type": member_type,
            "wmax_char_limit": wmax_choice,
            "fsy": fsy,
            "bar_diameter_mm": db,
            "bar_spacing_mm": spacing,
            "Ast": Ast,
            "sigma_sr": sigma_sr,
            "crack_k1": k1,
            "crack_k2": k2,
            "sls_Mstar": get_param("sls_Mstar", None),
            "phi_cc_t": phi_ce,
            "eps_cs_total_micro": eps_cs_micro,
            "reference_source": "Beam Inputs",
        }
    )
    render_page_reference_sidebar(build_crack_reference(crack_reference_values))
    render_as3600_crack_checks(st, checks_snapshot)

    # --------------------------------------------------------
    # Publish crack-control results (optional, for dashboards)
    # --------------------------------------------------------
    report_projection = project_as3600_results(
        {
            "sigma_allow_table": sigma_allow_table,
            "sigma_sr": float(sigma_sr),
            "w_calc": w_calc,
            "wmax_char": wmax_choice,
            "passes_table": passes_table,
            "passes_w": passes_w,
            "crack_width": w_calc,
            "crack_sr_max_mm": float(sr_max),
            "crack_utilisation": utilisation_w,
        }
    )
    update_results(**report_projection.result_update())
    
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
