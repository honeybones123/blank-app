"""Shrinkage compact input-card presentation."""

from __future__ import annotations

from typing import Any, Mapping

import streamlit as st

from application.contracts.concrete_crack_shrinkage import ShrinkageMethod
from engineering_page_sections.compact_check_inputs import (
    CheckInputCategory,
    CheckInputPanelConfig,
    format_dimensions,
    format_number,
    join_summary,
    render_compact_check_inputs,
)
from engineering_page_sections.shrinkage_page_context import ShrinkageInputValues
from state_runtime_gateway import get_param
from widgets_helpers import number_row, v2_number_input, v2_selectbox


SHRINKAGE_METHOD_LABELS = {
    ShrinkageMethod.EXISTING_AS3600.value: (
        "Existing StructuralBase method (AS 3600:2018)"
    ),
    ShrinkageMethod.EC2_C766.value: (
        "EC2 equation method (CIRIA C766 Appendices A3-A4)"
    ),
}


def render_shrinkage_inputs(
    *,
    engineering_state: Mapping[str, Any],
    sync_callbacks: Mapping[str, Any],
) -> ShrinkageInputValues:
    """Render the established four input cards and return detached values."""

    def engineering_value(name: str, default: Any) -> Any:
        return engineering_state.get(name, get_param(name, default))

    width_default = float(engineering_value("b", 400.0))
    depth_default = float(engineering_value("D", 600.0))
    strength_default = float(engineering_value("fc", 32.0))

    method = str(
        get_param("shrinkage_method", ShrinkageMethod.EXISTING_AS3600.value)
    )
    width = width_default
    depth = depth_default
    concrete_strength = strength_default
    faces_option = str(
        get_param("member_faces_exposed", "Slab – one face exposed")
    )
    environment = str(get_param("shrinkage_env", "Arid environment"))
    time_days = float(get_param("t_shrink", 365.0))
    relative_humidity = float(
        get_param("shrinkage_relative_humidity_percent", 51.0)
    )
    cement_class = str(get_param("shrinkage_cement_class", "S"))
    drying_start = float(get_param("shrinkage_drying_start_age_days", 7.0))

    def _render_method_inputs() -> None:
        nonlocal method
        method_options = list(SHRINKAGE_METHOD_LABELS)
        method_current = str(
            get_param(
                "shrinkage_method", ShrinkageMethod.EXISTING_AS3600.value
            )
        )
        if method_current not in method_options:
            method_current = ShrinkageMethod.EXISTING_AS3600.value
        method = st.selectbox(
            "Calculation method",
            options=method_options,
            index=method_options.index(method_current),
            format_func=lambda value: SHRINKAGE_METHOD_LABELS[value],
            key="sh_method",
            on_change=sync_callbacks["sh_method"],
            persist_state="session",
        )

    def _render_geometry_inputs() -> None:
        nonlocal width, depth, faces_option
        st.markdown("**Geometry / member**")
        number_row(
            "Section width b (mm)",
            "sh_b",
            width_default,
            sync_callbacks,
        )
        number_row(
            "Overall depth D (mm)",
            "sh_D",
            depth_default,
            sync_callbacks,
        )
        width = float(engineering_value("b", width_default))
        depth = float(engineering_value("D", depth_default))

        label_col, value_col = st.columns([1, 2])
        with label_col:
            st.markdown(
                "<div class='sb-label'>Member / faces exposed</div>",
                unsafe_allow_html=True,
            )
        with value_col:
            face_options = [
                "Slab – one face exposed",
                "Slab – two faces exposed",
                "Beam – three faces exposed",
                "Column – four faces exposed",
            ]
            face_current = get_param(
                "member_faces_exposed", "Slab – one face exposed"
            )
            if face_current not in face_options:
                face_current = "Slab – one face exposed"
            faces_option = v2_selectbox(
                label="Value",
                key="sh_faces",
                options=face_options,
                default_index=face_options.index(face_current),
                label_visibility="collapsed",
                on_change=sync_callbacks["sh_faces"],
            )

    def _render_environment_inputs() -> None:
        nonlocal concrete_strength, environment
        nonlocal relative_humidity, cement_class
        st.markdown("**Material / environment**")
        number_row(
            "Concrete strength f'c (MPa)",
            "inputs_fc",
            strength_default,
            sync_callbacks,
        )
        concrete_strength = float(engineering_value("fc", strength_default))

        environment_options = [
            "Arid environment",
            "Interior environment",
            "Temperate inland environment",
            "Tropical / near-coastal / coastal environment",
        ]
        environment_current = get_param(
            "shrinkage_env", "Arid environment"
        )
        if environment_current not in environment_options:
            environment_current = "Arid environment"

        label_col, value_col = st.columns([1, 2])
        with label_col:
            st.markdown(
                "<div class='sb-label'>Shrinkage environment (Table 3.1.7.2)</div>",
                unsafe_allow_html=True,
            )
        with value_col:
            if method == ShrinkageMethod.EXISTING_AS3600.value:
                environment = v2_selectbox(
                    label="Value",
                    key="sh_env",
                    options=environment_options,
                    default_index=environment_options.index(
                        environment_current
                    ),
                    label_visibility="collapsed",
                    on_change=sync_callbacks["sh_env"],
                )
            else:
                environment = str(environment_current)
                relative_humidity = v2_number_input(
                    label="Relative humidity (%)",
                    key="sh_rh",
                    default=float(
                        get_param(
                            "shrinkage_relative_humidity_percent", 51.0
                        )
                    ),
                    step=1.0,
                    min_value=0.0,
                    max_value=100.0,
                    on_change=sync_callbacks["sh_rh"],
                )
                cement_options = ["S", "N", "R"]
                cement_current = str(
                    get_param("shrinkage_cement_class", "S")
                )
                if cement_current not in cement_options:
                    cement_current = "S"
                cement_class = v2_selectbox(
                    label="Cement class",
                    key="sh_cement_class",
                    options=cement_options,
                    default_index=cement_options.index(cement_current),
                    on_change=sync_callbacks["sh_cement_class"],
                )

    def _render_time_inputs() -> None:
        nonlocal time_days, drying_start
        st.markdown("**Time / drying**")
        label_col, value_col = st.columns([1, 2])
        with label_col:
            st.markdown(
                "<div class='sb-label'>Time since commencement of drying t (days)</div>",
                unsafe_allow_html=True,
            )
        with value_col:
            time_days = v2_number_input(
                label="Value",
                key="inputs_t_shrink",
                default=float(get_param("t_shrink", 365.0)),
                step=10.0,
                min_value=1.0,
                label_visibility="collapsed",
                on_change=sync_callbacks["inputs_t_shrink"],
            )
            if method == ShrinkageMethod.EC2_C766.value:
                drying_start = v2_number_input(
                    label="End of curing / start of drying (days)",
                    key="sh_drying_start",
                    default=float(
                        get_param("shrinkage_drying_start_age_days", 7.0)
                    ),
                    step=1.0,
                    min_value=0.0,
                    on_change=sync_callbacks["sh_drying_start"],
                )

    method_label = SHRINKAGE_METHOD_LABELS.get(method, method)
    environment_summary = (
        environment
        if method == ShrinkageMethod.EXISTING_AS3600.value
        else f"RH {relative_humidity:.0f}% · cement {cement_class}"
    )
    render_compact_check_inputs(
        st,
        CheckInputPanelConfig(
            page_slug="shrinkage",
            mount_closed_bodies=True,
            categories=(
                CheckInputCategory(
                    category_id="method",
                    label="Calculation method",
                    summary=method_label,
                    render_body=_render_method_inputs,
                    icon="≡",
                ),
                CheckInputCategory(
                    category_id="section_member",
                    label="Section & member",
                    summary=join_summary(
                        format_dimensions(width_default, depth_default),
                        faces_option,
                    ),
                    render_body=_render_geometry_inputs,
                    icon="▣",
                ),
                CheckInputCategory(
                    category_id="material_environment",
                    label="Material & environment",
                    summary=join_summary(
                        f"f'c {format_number(strength_default, 'MPa')}",
                        environment_summary,
                    ),
                    render_body=_render_environment_inputs,
                    icon="◇",
                ),
                CheckInputCategory(
                    category_id="time_drying",
                    label="Time & drying",
                    summary=f"t {format_number(time_days, 'days')}",
                    render_body=_render_time_inputs,
                    icon="◷",
                ),
            ),
        ),
    )

    return ShrinkageInputValues(
        method=method,
        width_mm=width,
        depth_mm=depth,
        concrete_strength_mpa=concrete_strength,
        faces_exposed=faces_option,
        environment=environment,
        time_days=time_days,
        relative_humidity_percent=relative_humidity,
        cement_class=cement_class,
        drying_start_age_days=drying_start,
    )


__all__ = ["SHRINKAGE_METHOD_LABELS", "render_shrinkage_inputs"]
