"""Creep compact input-card presentation.

This module preserves the established widget keys, callback paths, category
order and summaries.  It returns immutable values for the page runtime; it
does not calculate or publish Creep engineering results.
"""

from __future__ import annotations

from typing import Any, Mapping

import streamlit as st

from engineering_page_sections.compact_check_inputs import (
    CheckInputCategory,
    CheckInputPanelConfig,
    format_dimensions,
    format_number,
    join_summary,
    render_compact_check_inputs,
)
from engineering_page_sections.creep_page_context import CreepInputValues
from state_runtime_gateway import get_param
from widgets_helpers import number_row, v2_number_input, v2_selectbox


def render_creep_inputs(
    *,
    engineering_state: Mapping[str, Any],
    sync_callbacks: Mapping[str, Any],
) -> CreepInputValues:
    """Render the existing three Creep input cards and return their values."""

    def engineering_value(name: str, default: Any) -> Any:
        return engineering_state.get(name, get_param(name, default))

    b_val = float(engineering_value("b", 400.0))
    depth_val = float(engineering_value("D", 600.0))
    fc_val = float(engineering_value("fc", 32.0))
    ec_val = float(engineering_value("Ec", 30000.0) or 30000.0)

    width = b_val
    depth = depth_val
    concrete_strength = fc_val
    concrete_modulus = ec_val
    faces_option = str(
        get_param("member_faces_exposed", "Beam – three faces exposed")
    )
    environment = str(
        get_param("env_option", "Temperate inland environment")
    )
    time_after_loading = float(get_param("t_creep", 365.0))
    age_at_loading = float(get_param("age_at_loading", 28.0))

    def _render_geometry_inputs() -> None:
        nonlocal width, depth, faces_option
        st.markdown("**Geometry / member**")
        number_row("Section width b (mm)", "cr_b", b_val, sync_callbacks)
        number_row("Overall depth D (mm)", "cr_D", depth_val, sync_callbacks)
        width = float(engineering_value("b", b_val))
        depth = float(engineering_value("D", depth_val))

        label_col, value_col = st.columns([1, 2])
        with label_col:
            st.markdown(
                "<div class='sb-label'>Member / faces exposed</div>",
                unsafe_allow_html=True,
            )
        with value_col:
            faces_options = [
                "Slab – one face exposed",
                "Slab – two faces exposed",
                "Beam – three faces exposed",
                "Column – four faces exposed",
            ]
            faces_current = get_param(
                "member_faces_exposed", "Beam – three faces exposed"
            )
            if faces_current not in faces_options:
                faces_current = "Beam – three faces exposed"
            faces_option = v2_selectbox(
                label="Value",
                key="cr_faces",
                options=faces_options,
                default_index=faces_options.index(faces_current),
                label_visibility="collapsed",
                on_change=sync_callbacks["cr_faces"],
            )

    def _render_environment_inputs() -> None:
        nonlocal concrete_strength, concrete_modulus, environment
        st.markdown("**Material / environment**")
        number_row(
            "Concrete strength f'c (MPa)",
            "inputs_fc",
            fc_val,
            sync_callbacks,
        )
        concrete_strength = float(engineering_value("fc", fc_val))
        concrete_modulus = float(engineering_value("Ec", ec_val))

        label_col, value_col = st.columns([1, 2])
        with label_col:
            st.markdown(
                "<div class='sb-label'>Creep environment (Tables 3.1.8.2 & 3.1.8.3)</div>",
                unsafe_allow_html=True,
            )
        with value_col:
            environment_options = [
                "Arid environment",
                "Interior environment",
                "Temperate inland environment",
                "Tropical / near-coastal / coastal environment",
            ]
            environment_current = get_param(
                "env_option", "Temperate inland environment"
            )
            if environment_current not in environment_options:
                environment_current = "Temperate inland environment"
            environment = v2_selectbox(
                label="Value",
                key="cr_env",
                options=environment_options,
                default_index=environment_options.index(environment_current),
                label_visibility="collapsed",
                on_change=sync_callbacks["cr_env"],
            )

    def _render_time_inputs() -> None:
        nonlocal time_after_loading, age_at_loading
        st.markdown("**Time / loading**")
        label_col, value_col = st.columns([1, 2])
        with label_col:
            st.markdown(
                "<div class='sb-label'>Time after loading t (days)</div>",
                unsafe_allow_html=True,
            )
        with value_col:
            time_after_loading = v2_number_input(
                label="Value",
                key="inputs_t_creep",
                default=float(get_param("t_creep", 365.0)),
                step=10.0,
                min_value=1.0,
                label_visibility="collapsed",
                on_change=sync_callbacks["inputs_t_creep"],
            )

        label_col, value_col = st.columns([1, 2])
        with label_col:
            st.markdown(
                "<div class='sb-label'>Age at loading τ (days)</div>",
                unsafe_allow_html=True,
            )
        with value_col:
            age_at_loading = v2_number_input(
                label="Value",
                key="inputs_age_at_loading",
                default=float(get_param("age_at_loading", 28.0)),
                step=1.0,
                min_value=1.0,
                label_visibility="collapsed",
                on_change=sync_callbacks["inputs_age_at_loading"],
            )

    render_compact_check_inputs(
        st,
        CheckInputPanelConfig(
            page_slug="creep",
            mount_closed_bodies=True,
            categories=(
                CheckInputCategory(
                    category_id="section_member",
                    label="Section & member",
                    summary=join_summary(
                        format_dimensions(b_val, depth_val),
                        faces_option,
                    ),
                    render_body=_render_geometry_inputs,
                    icon="▣",
                ),
                CheckInputCategory(
                    category_id="material_environment",
                    label="Material & environment",
                    summary=join_summary(
                        f"f'c {format_number(fc_val, 'MPa')}",
                        environment,
                    ),
                    render_body=_render_environment_inputs,
                    icon="◇",
                ),
                CheckInputCategory(
                    category_id="time_loading",
                    label="Time & loading",
                    summary=join_summary(
                        f"t {format_number(time_after_loading, 'days')}",
                        f"loading age {format_number(age_at_loading, 'days')}",
                    ),
                    render_body=_render_time_inputs,
                    icon="◷",
                ),
            ),
        ),
    )

    return CreepInputValues(
        width_mm=width,
        depth_mm=depth,
        concrete_strength_mpa=concrete_strength,
        concrete_modulus_mpa=concrete_modulus,
        faces_exposed=faces_option,
        environment=environment,
        time_after_loading_days=time_after_loading,
        age_at_loading_days=age_at_loading,
    )


__all__ = ["render_creep_inputs"]
