"""AS 3600 Crack Control compact input-card presentation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

import streamlit as st

from engineering_page_sections.compact_check_inputs import (
    CheckInputCategory,
    CheckInputPanelConfig,
    compact_check_input_columns,
    format_dimensions,
    format_number,
    join_summary,
)
from engineering_page_sections.crack_inputs import _col_heading, _seed_from_param
from engineering_page_sections.crack_method_inputs import (
    CRACK_METHOD_LABELS,
    render_crack_method_selector,
)
from state_and_helpers import get_param, get_widget_key_for_shared
from widgets_helpers import (
    info_i_button,
    label_with_hover,
    main_longitudinal_reo_pair_labels,
    number_row,
    page_divider,
    render_longitudinal_reo_row_config_controls,
    render_longitudinal_reo_rows,
    seed_widget_from_shared,
)


REO_BAR_DIAS = [10, 12, 16, 20, 24, 28, 32, 36, 40]
REO_COUNTS_0_12 = list(range(0, 13))
REO_SPACINGS = [75, 100, 125, 150, 175, 200, 225, 250, 275, 300]
REO_LAYOUT_MODE = ["Count", "Spacing"]


@dataclass(frozen=True, slots=True)
class CrackAs3600InputValues:
    concrete_strength_mpa: float
    concrete_modulus_mpa: float
    steel_modulus_mpa: float
    width_mm: float
    depth_mm: float
    clear_cover_mm: float
    member_type: str
    bond_coefficient: float
    strain_distribution_factor: float


def render_as3600_inputs(
    *,
    selected_method: str,
    sync_callbacks: Mapping[str, Any],
) -> CrackAs3600InputValues:
    page_divider()

    width_summary = get_param("b", None)
    depth_summary = get_param("D", None)
    strength_summary = get_param("fc", None)
    cover_summary = get_param("cover_bot", None)
    bottom_count = get_param("nb_or_s_bot_1", get_param("nb_bot", None))
    bottom_diameter = get_param("db_bot_1", get_param("db_bot", None))
    exposure_summary = str(
        get_param("exposure_class", "Not provided") or "Not provided"
    )
    member_summary = str(
        get_param("crack_member_type", "Not provided") or "Not provided"
    )
    method_region, section_region, reinforcement_region, criteria_region = (
        compact_check_input_columns(
            st,
            CheckInputPanelConfig(
                page_slug="crack",
                mount_closed_bodies=True,
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
                            format_dimensions(width_summary, depth_summary),
                            f"f'c {format_number(strength_summary, 'MPa')}",
                            f"cover {format_number(cover_summary, 'mm')}",
                        ),
                        lambda: None,
                        icon="▣",
                    ),
                    CheckInputCategory(
                        "reinforcement",
                        "Tension reinforcement",
                        (
                            "Not provided"
                            if bottom_count is None or bottom_diameter is None
                            else f"{float(bottom_count):.0f}-N{float(bottom_diameter):.0f}"
                        ),
                        lambda: None,
                        icon="●",
                    ),
                    CheckInputCategory(
                        "criteria",
                        "Crack-control parameters",
                        join_summary(
                            exposure_summary,
                            member_summary,
                            CRACK_METHOD_LABELS.get(
                                selected_method, selected_method
                            ),
                        ),
                        lambda: None,
                        icon="≡",
                    ),
                ),
            ),
        )
    )

    with method_region:
        render_crack_method_selector(sync_callbacks)

    with section_region:
        _col_heading("Materials & Geometry")
        strength = number_row(
            "Concrete strength f'c (MPa)",
            "crack_fc",
            _seed_from_param("fc", 32.0),
            sync_callbacks,
            help_text=(
                "Characteristic compressive strength of concrete at 28 days."
            ),
        )
        concrete_modulus = float(get_param("Ec", 30000.0) or 30000.0)
        steel_modulus = float(get_param("Es", 200000.0) or 200000.0)
        width = number_row(
            "Section width b (mm)",
            "crack_b",
            _seed_from_param("b", 300.0),
            sync_callbacks,
            help_text=(
                "Section width (cross-section dimension perpendicular to "
                "bending axis)."
            ),
        )
        depth = number_row(
            "Overall depth D (mm)",
            "crack_D",
            _seed_from_param("D", 600.0),
            sync_callbacks,
            help_text=(
                "Overall section depth (cross-section dimension in the "
                "direction of loading)."
            ),
        )
        cover = number_row(
            "Clear cover to tensile bars c (mm)",
            "crack_cover_bot",
            _seed_from_param("cover_bot", 40.0),
            sync_callbacks,
            help_text=(
                "Clear concrete cover to the centroid of the bottom tensile "
                "reinforcement layer."
            ),
        )

    with reinforcement_region:
        section_shape = str(get_param("sec_shape", "RECT") or "RECT")
        bottom_heading, _ = main_longitudinal_reo_pair_labels(
            section_shape, variant="sentence_lower"
        )
        rowgap_key = (
            get_widget_key_for_shared("rowgap_bot", prefix="crack_")
            or "crack_rowgap_bot"
        )
        seed_widget_from_shared(rowgap_key, "rowgap_bot", 60.0)
        rowgap_value = float(
            st.session_state.get(
                rowgap_key, get_param("rowgap_bot", 60.0)
            )
        )
        title_col, info_col = st.columns(
            [0.92, 0.08], vertical_alignment="center"
        )
        with title_col:
            _col_heading(bottom_heading.title())
        with info_col:
            with info_i_button(
                help_text=(
                    "Row count and vertical gap between reinforcement layers."
                )
            ):
                render_longitudinal_reo_row_config_controls(
                    page_prefix="crack",
                    section="bot",
                    sync_callbacks=sync_callbacks,
                    rowgap_widget_key=rowgap_key,
                    rowgap_default=rowgap_value,
                    rowgap_help_text=(
                        "Clear vertical gap between reinforcement rows (mm)."
                    ),
                    sec_shape=section_shape,
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
            sec_shape=section_shape,
        )

    with criteria_region:
        _col_heading("Crack criteria")
        exposure_options = ["A1", "A2", "B1", "B2", "C1", "C2"]
        exposure_current = st.session_state.get("exposure_class", "B1")
        if exposure_current not in exposure_options:
            exposure_current = "B1"
        label_col, value_col = st.columns([1, 2])
        with label_col:
            label_with_hover(
                "Exposure class",
                "Exposure classification to AS 3600 – controls allowable "
                "crack width and durability detailing.",
            )
        with value_col:
            st.selectbox(
                "",
                options=exposure_options,
                index=exposure_options.index(exposure_current),
                key="crack_exposure_class",
                on_change=sync_callbacks["crack_exposure_class"],
                label_visibility="collapsed",
            )

        label_col, value_col = st.columns([1, 2])
        with label_col:
            label_with_hover(
                "Resultant action",
                "Type of loading: primarily flexure (typical beams) or "
                "primarily tension (tension members). Affects which table "
                "values are used in crack control checks.",
            )
        with value_col:
            member_current = st.session_state.get(
                "crack_member_type", "Primarily flexure"
            )
            member_type = st.selectbox(
                "",
                options=["Primarily flexure", "Primarily tension"],
                index=0 if member_current == "Primarily flexure" else 1,
                key="inputs_crack_member_type",
                on_change=sync_callbacks["inputs_crack_member_type"],
                label_visibility="collapsed",
            )

        label_col, value_col = st.columns([1, 2])
        with label_col:
            label_with_hover(
                "k₁ (bond coefficient)",
                "Bond coefficient: 0.8 for deformed bars, 1.6 for plain "
                "bars. Used in crack spacing calculations.",
            )
        with value_col:
            k1_value = float(st.session_state.get("crack_k1", 0.8))
            k1_options = [0.8, 1.6]
            k1 = st.selectbox(
                "",
                options=k1_options,
                index=(
                    k1_options.index(k1_value)
                    if k1_value in k1_options
                    else 0
                ),
                format_func=lambda value: (
                    "Deformed bars (k₁ = 0.8)"
                    if abs(value - 0.8) < 1e-9
                    else "Plain bars (k₁ = 1.6)"
                ),
                key="inputs_crack_k1",
                on_change=sync_callbacks["inputs_crack_k1"],
                label_visibility="collapsed",
            )
        k2_seed = 0.5 if member_type == "Primarily flexure" else 1.0
        k2 = number_row(
            "k₂ (strain distribution factor)",
            "crack_k2",
            float(st.session_state.get("crack_k2", k2_seed)),
            sync_callbacks,
            help_text=(
                "Strain distribution factor used in crack spacing/width "
                "model. Default 0.5 for typical RC flexural members; adjust "
                "only if using a different assumed strain distribution per "
                "your chosen method."
            ),
        )

    return CrackAs3600InputValues(
        concrete_strength_mpa=float(strength),
        concrete_modulus_mpa=concrete_modulus,
        steel_modulus_mpa=steel_modulus,
        width_mm=float(width),
        depth_mm=float(depth),
        clear_cover_mm=float(cover),
        member_type=str(member_type),
        bond_coefficient=float(k1),
        strain_distribution_factor=float(k2),
    )


__all__ = ["CrackAs3600InputValues", "render_as3600_inputs"]
