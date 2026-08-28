"""Shrinkage engineering orchestration and publication runtime."""

from __future__ import annotations

import streamlit as st

from application.contracts.concrete_crack_shrinkage import (
    CementClass,
    EC2C766ShrinkageInput,
    ShrinkageMethod,
)
from calculations.concrete_crack_shrinkage_methods import (
    calculate_ec2_c766_shrinkage,
)
from calculations.creep_shrinkage import (
    SHRINKAGE_ENV_LABELS as _ENV_LABELS,
    autogenous_shrinkage_final_from_current,
    calc_eps_cse,
    calc_k1_shrinkage,
    exposed_perimeter_geometry_values,
    shrinkage_closest_fc_row as _closest_fc_row,
    shrinkage_closest_th as _closest_th,
    shrinkage_eps_final as _shrinkage_eps_final,
    shrinkage_total_values,
)
from engineering_page_sections.shrinkage_checks import render_shrinkage_checks
from engineering_page_sections.shrinkage_checks_context import (
    ShrinkageChecksSnapshot,
)
from engineering_page_sections.shrinkage_inputs import render_shrinkage_inputs
from engineering_page_sections.shrinkage_page_context import (
    build_shrinkage_page_snapshot,
)
from engineering_page_sections.shrinkage_page_shell import ShrinkagePageShell
from engineering_page_sections.shrinkage_summary import (
    render_shrinkage_explainer,
    render_shrinkage_summary,
)
from engineering_page_sections.shrinkage_visualisation import (
    ShrinkageVisualisationView,
    render_shrinkage_visualisation,
)
from inputs_application.authoritative_check_packs import (
    current_authoritative_family,
)
from inputs_application.time_dependent_engineering_state import (
    resolve_time_dependent_engineering_state,
)
from inputs_application.time_dependent_presentation import (
    resolve_time_dependent_family_values,
)
from reporting.shrinkage_report_projection import (
    build_shrinkage_report_projection,
)
from section_layout import compute_section_layout
from state_runtime_gateway import get_param, get_sync_callbacks, update_results
from ui_seamless_steps import (
    bind_summary_clicks,
    inject_seamless_steps_css,
)
from widgets_helpers import (
    apply_result_page_css,
    page_divider,
    render_page_explainer_expander,
    render_result_page_title,
)
from engineering_page_sections.page_reference_sidebar import (
    build_shrinkage_reference,
    render_page_reference_sidebar,
)


def _inject_calcbox_css() -> None:
    """Preserve the established blue calculation-box presentation."""

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


def _method_metadata(method: str, method_result) -> tuple[str, tuple[str, ...]]:
    if method_result is None:
        return "AS 3600:2018", ()
    return (
        str(method_result.reference.document),
        tuple(str(value) for value in method_result.warnings),
    )


def _publish_shrinkage_values(
    values: dict,
    *,
    method: str,
    method_result,
) -> None:
    reference, warnings = _method_metadata(method, method_result)
    projection = build_shrinkage_report_projection(
        values,
        method=method,
        reference=reference,
        warnings=warnings,
    )
    update_results(**projection.result_updates())
    update_results("shrinkage_method", projection.method_update())


def compute_shrinkage_results(publish: bool = True) -> dict:
    """Compute Shrinkage results without rendering the page."""

    method = str(
        get_param("shrinkage_method", ShrinkageMethod.EXISTING_AS3600.value)
    )
    authoritative = (
        current_authoritative_family(st.session_state, "shrinkage")
        if method == ShrinkageMethod.EXISTING_AS3600.value
        else None
    )
    if authoritative is not None:
        if publish:
            projection = build_shrinkage_report_projection(
                {
                    "eps_cs_total": authoritative.get("eps_cs_total"),
                    "eps_cs_total_micro": authoritative.get(
                        "eps_cs_total_micro"
                    ),
                    "eps_cse": authoritative.get("eps_cse"),
                    "eps_csd_t": authoritative.get("eps_csd_t"),
                    "th_shrinkage": authoritative.get("th_shrinkage_mm"),
                    "k1_shrinkage": authoritative.get("k1_shrinkage"),
                },
                method=method,
                reference="AS 3600:2018",
            )
            update_results(**projection.result_updates())
        return {
            "eps_cs_total": authoritative.get("eps_cs_total"),
            "eps_cs_total_micro": authoritative.get("eps_cs_total_micro"),
            "eps_cse": authoritative.get("eps_cse"),
            "eps_csd_t": authoritative.get("eps_csd_t"),
            "shrinkage_steps": ["Authoritative Inputs V2 calculation"],
        }

    engineering = resolve_time_dependent_engineering_state(
        st.session_state
    ).values
    width = float(engineering.get("b", 300.0) or 300.0)
    depth = float(engineering.get("D", 600.0) or 600.0)
    strength = float(engineering.get("fc", 32.0) or 32.0)
    environment = get_param("shrinkage_env", "Temperate inland environment")
    time_days = get_param("t_shrink", 365.0)
    faces = get_param(
        "member_faces_exposed", "Beam – three faces exposed"
    )
    geometry = exposed_perimeter_geometry_values(width, depth, faces)
    thickness_table = _closest_th(geometry["th_raw"])

    method_result = None
    if method == ShrinkageMethod.EC2_C766.value:
        method_result = calculate_ec2_c766_shrinkage(
            EC2C766ShrinkageInput(
                characteristic_cylinder_strength_mpa=strength,
                relative_humidity_percent=float(
                    get_param("shrinkage_relative_humidity_percent", 51.0)
                ),
                cement_class=CementClass(
                    str(get_param("shrinkage_cement_class", "S"))
                ),
                concrete_area_mm2=float(geometry["Ag"]),
                drying_perimeter_mm=float(geometry["ue"]),
                age_days=float(time_days),
                drying_start_age_days=float(
                    get_param("shrinkage_drying_start_age_days", 7.0)
                ),
            )
        )
        k1 = method_result.drying_time_coefficient
        eps_cse = method_result.autogenous_shrinkage
        eps_csd_t = method_result.drying_shrinkage
        eps_total = method_result.total_shrinkage
        eps_total_micro = eps_total * 1e6
        thickness_table = method_result.notional_size_mm
    else:
        k1 = calc_k1_shrinkage(time_days, thickness_table)
        eps_cse = calc_eps_cse(strength, time_days)
        eps_csd_final = _shrinkage_eps_final(
            strength, environment, thickness_table
        )
        total = shrinkage_total_values(k1, eps_cse, eps_csd_final)
        eps_csd_t = total["eps_csd_t"]
        eps_total = total["eps_cs_total"]
        eps_total_micro = total["eps_cs_total_micro"]

    values = {
        "eps_cs_total": eps_total,
        "eps_cs_total_micro": eps_total_micro,
        "eps_cse": eps_cse,
        "eps_csd_t": eps_csd_t,
        "th_shrinkage": thickness_table,
        "k1_shrinkage": k1,
    }
    if publish:
        _publish_shrinkage_values(
            values,
            method=method,
            method_result=method_result,
        )
    return {
        "eps_cs_total": eps_total,
        "eps_cs_total_micro": eps_total_micro,
        "eps_cse": eps_cse,
        "eps_csd_t": eps_csd_t,
        "shrinkage_steps": [
            "(Detailed steps not available for this module yet)"
        ],
    }


def compute_shrinkage_components_for_crack_control() -> dict:
    """Calculate C766 strain components from the active Shrinkage method."""

    width = float(get_param("b", 300.0))
    depth = float(get_param("D", 600.0))
    strength = float(get_param("fc", 32.0))
    age_days = max(float(get_param("t_shrink", 365.0)), 0.0)
    drying_start = max(
        float(get_param("shrinkage_drying_start_age_days", 7.0)), 0.0
    )
    early_age = min(drying_start, age_days)
    faces = get_param(
        "member_faces_exposed", "Beam – three faces exposed"
    )
    geometry = exposed_perimeter_geometry_values(width, depth, faces)
    method = str(
        get_param("shrinkage_method", ShrinkageMethod.EXISTING_AS3600.value)
    )

    if method == ShrinkageMethod.EC2_C766.value:
        common = dict(
            characteristic_cylinder_strength_mpa=strength,
            relative_humidity_percent=float(
                get_param("shrinkage_relative_humidity_percent", 51.0)
            ),
            cement_class=CementClass(
                str(get_param("shrinkage_cement_class", "S"))
            ),
            concrete_area_mm2=float(geometry["Ag"]),
            drying_perimeter_mm=float(geometry["ue"]),
            drying_start_age_days=drying_start,
        )
        early = calculate_ec2_c766_shrinkage(
            EC2C766ShrinkageInput(age_days=early_age, **common)
        )
        current = calculate_ec2_c766_shrinkage(
            EC2C766ShrinkageInput(age_days=age_days, **common)
        )
        return {
            "method": method,
            "early_age_days": early_age,
            "age_days": age_days,
            "autogenous_early": early.autogenous_shrinkage,
            "autogenous_long_term": current.autogenous_shrinkage,
            "drying_long_term": current.drying_shrinkage,
        }

    thickness_table = _closest_th(float(geometry["th_raw"]))
    k1 = calc_k1_shrinkage(age_days, thickness_table)
    eps_csd_final = _shrinkage_eps_final(
        strength,
        get_param("shrinkage_env", "Temperate inland environment"),
        thickness_table,
    )
    current = shrinkage_total_values(
        k1,
        calc_eps_cse(strength, age_days),
        eps_csd_final,
    )
    return {
        "method": method,
        "early_age_days": early_age,
        "age_days": age_days,
        "autogenous_early": calc_eps_cse(strength, early_age),
        "autogenous_long_term": calc_eps_cse(strength, age_days),
        "drying_long_term": current["eps_csd_t"],
    }


def render_shrinkage():
    title_slot = ShrinkagePageShell.reserve_title(st)
    apply_result_page_css()
    _inject_calcbox_css()
    inject_seamless_steps_css()
    sync_callbacks = get_sync_callbacks()
    engineering = resolve_time_dependent_engineering_state(st.session_state)

    title_slot.render(lambda: render_result_page_title("Shrinkage"))
    summary_values = compute_shrinkage_results(publish=True)
    render_shrinkage_summary(
        summary_values=summary_values,
        bind_clicks=bind_summary_clicks,
    )
    render_page_explainer_expander(
        lambda: render_shrinkage_explainer(st)
    )
    page_divider()
    visualisation_slot = ShrinkagePageShell.reserve_visualisation(st)

    inputs = render_shrinkage_inputs(
        engineering_state=engineering.values,
        sync_callbacks=sync_callbacks,
    )
    page_divider()

    geometry = exposed_perimeter_geometry_values(
        inputs.width_mm,
        inputs.depth_mm,
        inputs.faces_exposed,
    )
    area = float(geometry["Ag"])
    perimeter = float(geometry["ue"])
    thickness_raw = float(geometry["th_raw"])
    thickness_table = _closest_th(thickness_raw)

    method_result = None
    if inputs.method == ShrinkageMethod.EC2_C766.value:
        method_result = calculate_ec2_c766_shrinkage(
            EC2C766ShrinkageInput(
                characteristic_cylinder_strength_mpa=(
                    inputs.concrete_strength_mpa
                ),
                relative_humidity_percent=(
                    inputs.relative_humidity_percent
                ),
                cement_class=CementClass(inputs.cement_class),
                concrete_area_mm2=area,
                drying_perimeter_mm=perimeter,
                age_days=inputs.time_days,
                drying_start_age_days=inputs.drying_start_age_days,
            )
        )
        thickness_table = method_result.notional_size_mm
        k1 = method_result.drying_time_coefficient
        eps_cse = method_result.autogenous_shrinkage
        eps_csd_final = method_result.nominal_drying_shrinkage
        eps_csd_t = method_result.drying_shrinkage
        eps_total = method_result.total_shrinkage
        eps_total_micro = eps_total * 1e6
    else:
        k1 = calc_k1_shrinkage(inputs.time_days, thickness_table)
        eps_cse = calc_eps_cse(
            inputs.concrete_strength_mpa,
            inputs.time_days,
        )
        eps_csd_final = _shrinkage_eps_final(
            inputs.concrete_strength_mpa,
            inputs.environment,
            thickness_table,
        )
        total = shrinkage_total_values(k1, eps_cse, eps_csd_final)
        eps_csd_t = total["eps_csd_t"]
        eps_total = total["eps_cs_total"]
        eps_total_micro = total["eps_cs_total_micro"]

    fallback = {
        "th_shrinkage_mm": thickness_table,
        "k1_shrinkage": k1,
        "eps_cse": eps_cse,
        "eps_csd_final": eps_csd_final,
        "eps_csd_t": eps_csd_t,
        "eps_cs_total": eps_total,
        "eps_cs_total_micro": eps_total_micro,
    }
    displayed = (
        resolve_time_dependent_family_values(
            st.session_state,
            family="shrinkage",
            fallback=fallback,
        )
        if inputs.method == ShrinkageMethod.EXISTING_AS3600.value
        else dict(fallback)
    )
    thickness_table = int(displayed["th_shrinkage_mm"])
    k1 = float(displayed["k1_shrinkage"])
    eps_cse = float(displayed["eps_cse"])
    eps_csd_final = float(displayed["eps_csd_final"])
    eps_csd_t = float(displayed["eps_csd_t"])
    eps_total = float(displayed["eps_cs_total"])
    eps_total_micro = float(displayed["eps_cs_total_micro"])

    publication_values = {
        "eps_cs_total": eps_total,
        "eps_cs_total_micro": eps_total_micro,
        "eps_cse": eps_cse,
        "eps_csd_t": eps_csd_t,
        "th_shrinkage": thickness_table,
        "k1_shrinkage": k1,
    }
    _publish_shrinkage_values(
        publication_values,
        method=inputs.method,
        method_result=method_result,
    )
    page_snapshot = build_shrinkage_page_snapshot(
        engineering_state=engineering.values,
        diagram_state=st.session_state,
        summary_values=summary_values,
        published_results=current_authoritative_family(
            st.session_state, "shrinkage"
        ),
        inputs=inputs,
    )

    shrinkage_reference_values = dict(page_snapshot.engineering_state)
    shrinkage_reference_values.update(
        {
            "b": page_snapshot.inputs.width_mm,
            "D": page_snapshot.inputs.depth_mm,
            "fc": page_snapshot.inputs.concrete_strength_mpa,
            "member_faces_exposed": page_snapshot.inputs.faces_exposed,
            "shrinkage_env": page_snapshot.inputs.environment,
            "shrinkage_method": page_snapshot.inputs.method,
            "t_shrink": page_snapshot.inputs.time_days,
            "shrinkage_relative_humidity_percent": page_snapshot.inputs.relative_humidity_percent,
            "shrinkage_cement_class": page_snapshot.inputs.cement_class,
            "shrinkage_drying_start_age_days": page_snapshot.inputs.drying_start_age_days,
            "A_g": area,
            "ue": perimeter,
            "th_raw": thickness_raw,
            "th_table": thickness_table,
            "reference_source": "Beam Inputs",
        }
    )
    render_page_reference_sidebar(
        build_shrinkage_reference(shrinkage_reference_values)
    )

    visualisation_slot.render(
        lambda: render_shrinkage_visualisation(
            st,
            view=ShrinkageVisualisationView(
                layout=compute_section_layout(),
                faces_exposed=page_snapshot.inputs.faces_exposed,
            ),
        )
    )

    eps_cse_final = (
        autogenous_shrinkage_final_from_current(
            eps_cse,
            inputs.time_days,
        )
        if inputs.method == ShrinkageMethod.EXISTING_AS3600.value
        else eps_cse
    )
    environment_short = (
        _ENV_LABELS[inputs.environment]
        if inputs.method == ShrinkageMethod.EXISTING_AS3600.value
        else inputs.environment
    )
    render_shrinkage_checks(
        ShrinkageChecksSnapshot(
            method=inputs.method,
            method_result=method_result,
            width_mm=inputs.width_mm,
            depth_mm=inputs.depth_mm,
            gross_area_mm2=area,
            faces_exposed=inputs.faces_exposed,
            exposed_perimeter_mm=perimeter,
            notional_thickness_raw_mm=thickness_raw,
            notional_thickness_table_mm=int(thickness_table),
            concrete_strength_mpa=inputs.concrete_strength_mpa,
            concrete_strength_table_mpa=_closest_fc_row(
                inputs.concrete_strength_mpa
            ),
            environment=inputs.environment,
            environment_short_label=environment_short,
            time_days=inputs.time_days,
            k1=k1,
            eps_cse=eps_cse,
            eps_cse_final=eps_cse_final,
            eps_csd_final=eps_csd_final,
            eps_csd_t=eps_csd_t,
            eps_cs_total=eps_total,
        )
    )


__all__ = [
    "compute_shrinkage_components_for_crack_control",
    "compute_shrinkage_results",
    "render_shrinkage",
]
