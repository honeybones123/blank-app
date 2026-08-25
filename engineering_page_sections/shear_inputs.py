"""Shear input-card presentation and widget orchestration.

This module owns the existing Shear input rail.  It deliberately preserves
the current widget keys, callback paths, category order, source badges, and
session-state writes.  Engineering calculations remain in the authoritative
Shear calculation/publication layer and run after this presentation boundary.
"""

from __future__ import annotations

from typing import Any

from calculations.shear import duct_area_mm2
from deflection_support import (
    _deflection_support_options_for_value,
    get_deflection_diagram_support_condition,
)
from engineering_page_sections.compact_check_inputs import (
    CheckInputCategory,
    CheckInputPanelConfig,
    InputSource,
    compact_check_input_regions,
    format_dimensions,
    format_number,
    join_summary,
)
from engineering_page_sections.shear_page_context import ShearPageSnapshot
from inputs_application.action_source_control import uses_load_analysis_actions
from state_and_helpers import (
    get_param,
    get_widget_key_for_shared,
    is_design_governing,
    load_proxies_from_active_set,
    recalc_derived_values,
    save_proxies_to_active_set,
    update_results,
)
from widgets_helpers import (
    info_i_button,
    number_row,
    render_section_title,
    select_row,
)


REO_SHEAR_LEGS_OPTIONS = [0] + list(range(2, 13))
REO_BAR_DIAS = [10, 12, 16, 20, 24, 28, 32, 36, 40]

KD_OPTIONS = [
    "None (no ducts in web)",
    "0.5 – steel ducts, grouted",
    "0.8 – plastic ducts, grouted",
    "1.2 – ungrouted ducts",
]
KD_VALUE_MAP = {
    "None (no ducts in web)": 0.0,
    "0.5 – steel ducts, grouted": 0.5,
    "0.8 – plastic ducts, grouted": 0.8,
    "1.2 – ungrouted ducts": 1.2,
}

KV_METHOD_OPTIONS = [
    "General εₓ-based (Cl. 8.2.4.2)",
    "Simplified non-prestressed (Cl. 8.2.4.3)",
]


def _coalesce_num(value: Any, default: float) -> float:
    """Return ``default`` only for ``None`` while preserving zero."""

    return default if value is None else float(value)


def build_shear_input_panel_config(
    *,
    st_module: Any,
) -> CheckInputPanelConfig:
    """Build the unchanged four-card Shear input presentation."""

    shape = str(get_param("sec_shape", "RECT") or "RECT")
    width = float(get_param("b", 0.0) or 0.0)
    depth = float(get_param("D", 0.0) or 0.0)
    concrete_strength = float(get_param("fc", 0.0) or 0.0)
    shear = float(get_param("uls_Vstar", get_param("shear_V", 0.0)) or 0.0)
    torsion = float(get_param("Tu_star", 0.0) or 0.0)
    axial_force = float(get_param("P_star", 0.0) or 0.0)
    link_diameter = float(get_param("lig_d", 0.0) or 0.0)
    link_legs = int(get_param("lig_legs", 0) or 0)
    link_spacing = float(get_param("s_lig", 0.0) or 0.0)
    method = str(get_param("k_v_method", "General method") or "General method")

    return CheckInputPanelConfig(
        page_slug="shear",
        mount_closed_bodies=True,
        categories=(
            CheckInputCategory(
                "design_actions",
                "Design actions",
                join_summary(
                    f"V* {format_number(shear, 'kN', decimals=1)}",
                    f"N* {format_number(axial_force, 'kN', decimals=1)}",
                    f"T* {format_number(torsion, 'kNm', decimals=1)}",
                ),
                lambda: None,
                source=(
                    InputSource.LOAD_ANALYSIS
                    if uses_load_analysis_actions(st_module.session_state)
                    else InputSource.BEAM_INPUTS
                ),
                icon="↧",
            ),
            CheckInputCategory(
                "section_material",
                "Section & material",
                join_summary(
                    format_dimensions(width, depth),
                    shape,
                    f"f'c {format_number(concrete_strength, 'MPa')}",
                ),
                lambda: None,
                icon="▣",
            ),
            CheckInputCategory(
                "shear_reinforcement",
                "Shear reinforcement",
                f"N{link_diameter:.0f} · {link_legs} legs · {link_spacing:.0f} mm spacing",
                lambda: None,
                icon="□",
            ),
            CheckInputCategory(
                "method_parameters",
                "Method & section parameters",
                method,
                lambda: None,
                icon="≡",
            ),
        ),
    )


def _render_design_actions(
    *,
    st: Any,
    sync_callbacks: Any,
    is_design_driven: bool,
    design_controls: bool,
    support_current: Any,
) -> None:
    prev_mode = st.session_state.get("loads_edit_mode", "ULS")
    selected_mode = st.session_state.get("loads_edit_mode", "ULS")
    selected_prefix = "sls" if selected_mode == "SLS" else "uls"
    toggle_widget_key = (
        get_widget_key_for_shared("loads_edit_toggle", prefix="inputs_")
        or "inputs_loads_edit_toggle"
    )

    col_title, col_info = st.columns([0.92, 0.08], gap="small")
    with col_title:
        render_section_title("Design Actions")
    with col_info:
        with info_i_button(
            help_text="Source of design actions (V*, N*, T*, P*) and optional display of prestress input.",
        ):
            st.markdown("Source: Inputs page selection", unsafe_allow_html=True)
            edit_sls = st.toggle(
                "View SLS loads",
                key=toggle_widget_key,
                persist_state="session",
                help="Toggle which load set is shown below. ULS drives bending/shear; SLS drives crack/deflection.",
            )

            selected_mode_preview = "SLS" if edit_sls else "ULS"
            action_verb_preview = "viewing" if is_design_driven else "editing"

            if not is_design_driven:
                st.caption("Design actions: Manual")
            else:
                st.caption("Design actions: From SFD/BMD")
            st.caption(f"Currently {action_verb_preview}: **{selected_mode_preview}** loads")

            if "shear_include_prestress_effects_ui" not in st.session_state:
                st.session_state["shear_include_prestress_effects_ui"] = False
            st.toggle(
                "Include prestress effects",
                key="shear_include_prestress_effects_ui",
                persist_state="session",
                help="Show the P* input in Design Actions. Stored P* is unchanged; this only controls visibility.",
            )

    new_mode = "SLS" if edit_sls else "ULS"

    if new_mode != prev_mode:
        st.session_state["loads_edit_mode"] = prev_mode
        save_proxies_to_active_set()
        st.session_state["loads_edit_mode"] = new_mode
        load_proxies_from_active_set()
        st.session_state["inputs_load_Vstar_proxy"] = st.session_state.get(
            "load_Vstar_proxy", 0.0
        )
        st.session_state["inputs_load_Nstar_proxy"] = st.session_state.get(
            "load_Nstar_proxy", 0.0
        )
        st.session_state["inputs_load_Mstar_pos_proxy"] = st.session_state.get(
            "load_Mstar_pos_proxy", 0.0
        )
        st.session_state["inputs_load_Mstar_neg_proxy"] = st.session_state.get(
            "load_Mstar_neg_proxy", 0.0
        )
        recalc_derived_values()
        update_results()
    else:
        st.session_state["loads_edit_mode"] = new_mode
    selected_mode = st.session_state.get("loads_edit_mode", "ULS")
    selected_prefix = "sls" if selected_mode == "SLS" else "uls"

    if is_design_driven:
        st.info(
            "Design actions are currently driven by the Design / Teaching page and are read-only here."
        )

    display_V = float(get_param(f"{selected_prefix}_Vstar", 0.0) or 0.0)
    display_N = float(get_param(f"{selected_prefix}_Nstar", 0.0) or 0.0)
    display_T = float(get_param("Tu_star", 0.0) or 0.0)
    n_proxy_widget_key = (
        get_widget_key_for_shared("load_Nstar_proxy", prefix="inputs_")
        or "inputs_load_Nstar_proxy"
    )
    m_pos_proxy_widget_key = (
        get_widget_key_for_shared("load_Mstar_pos_proxy", prefix="inputs_")
        or "inputs_load_Mstar_pos_proxy"
    )
    m_neg_proxy_widget_key = (
        get_widget_key_for_shared("load_Mstar_neg_proxy", prefix="inputs_")
        or "inputs_load_Mstar_neg_proxy"
    )

    display_Mu_pos = get_param(
        f"{selected_prefix}_Mstar_pos_manual",
        max(0.0, get_param(f"{selected_prefix}_Mstar", 0.0)),
    )
    display_Mu_neg = get_param(
        f"{selected_prefix}_Mstar_neg_manual",
        max(0.0, -get_param(f"{selected_prefix}_Mstar", 0.0)),
    )
    display_P = get_param("P_star", 0.0)

    if design_controls:
        if st.session_state.get("inputs_load_Vstar_proxy") != display_V:
            st.session_state["inputs_load_Vstar_proxy"] = display_V
        if st.session_state.get(n_proxy_widget_key) != display_N:
            st.session_state[n_proxy_widget_key] = display_N
        if st.session_state.get("shear_Tu_star") != display_T:
            st.session_state["shear_Tu_star"] = display_T
        if st.session_state.get(m_pos_proxy_widget_key) != display_Mu_pos:
            st.session_state[m_pos_proxy_widget_key] = display_Mu_pos
        if st.session_state.get(m_neg_proxy_widget_key) != display_Mu_neg:
            st.session_state[m_neg_proxy_widget_key] = display_Mu_neg
        if st.session_state.get("shear_P_star") != display_P:
            st.session_state["shear_P_star"] = display_P

    mu_star_pos_val = max(0.0, _coalesce_num(display_Mu_pos, 0.0))
    mu_star_neg_val = max(0.0, _coalesce_num(display_Mu_neg, 0.0))
    p_star_val = _coalesce_num(display_P, 0.0)
    moment_signed_selected = float(
        get_param(f"{selected_prefix}_Mstar", 0.0) or 0.0
    )
    bending_detail_view = str(
        st.session_state.get("bending_detail_view", "positive") or "positive"
    ).strip().lower()
    support_current_text = str(support_current or "").strip().lower()
    show_mu_negative = (
        ("continuous" in support_current_text)
        or ("interior" in support_current_text)
        or (moment_signed_selected < 0.0)
        or (bending_detail_view == "negative")
    )
    include_prestress_effects_ui = bool(
        st.session_state.get("shear_include_prestress_effects_ui", False)
    )

    number_row(
        "Design shear V* (kN)",
        "inputs_load_Vstar_proxy",
        float(display_V),
        sync_callbacks,
        disabled=is_design_driven,
        help_text="Factored shear at the section.",
    )
    number_row(
        "Axial force N* (kN, +tension)",
        n_proxy_widget_key,
        float(display_N),
        sync_callbacks,
        disabled=is_design_driven,
        help_text="Axial force at the section (+tension, −compression).",
    )
    number_row(
        "Torsion T* (kNm)",
        "shear_Tu_star",
        float(display_T),
        sync_callbacks,
        disabled=is_design_driven,
        help_text="Factored torsion at the section.",
    )
    number_row(
        "Positive design moment Mu*+ (kNm)",
        m_pos_proxy_widget_key,
        mu_star_pos_val,
        sync_callbacks,
        disabled=is_design_driven,
        help_text=(
            "Sagging bending demand magnitude. Used with shear for εₓ in the general MCFT route "
            "(positive bending: top compression, bottom tension)."
        ),
    )
    if show_mu_negative:
        number_row(
            "Negative design moment Mu*- (kNm)",
            m_neg_proxy_widget_key,
            mu_star_neg_val,
            sync_callbacks,
            disabled=is_design_driven,
            help_text=(
                "Hogging bending demand magnitude. Enter as a positive number for top tension / bottom compression."
            ),
        )
    if include_prestress_effects_ui:
        number_row(
            "Prestress force P* (kN)",
            "shear_P_star",
            p_star_val,
            sync_callbacks,
            disabled=is_design_driven,
            help_text=(
                "Prestress / effective prestress force in the section (kN). Affects longitudinal strain εₓ in shear."
            ),
        )

    number_row(
        "φ – strength reduction for shear",
        "shear_phi_shear",
        get_param("phi_shear", 0.75),
        sync_callbacks,
        help_text="Strength reduction factor for shear (AS 3600).",
    )


def _render_geometry_and_materials(
    *,
    st: Any,
    sync_callbacks: Any,
    design_controls: bool,
    support_widget_key: str,
    support_options: list[str],
    support_current: str,
    support_help_text: str,
) -> None:
    render_section_title("Geometry, materials & loading conditions")

    shape_options = ["RECT", "T", "I"]
    sec_shape_current = st.session_state.get("sec_shape", "RECT")
    if sec_shape_current not in shape_options:
        sec_shape_current = "RECT"

    select_row(
        "Section shape",
        "shear_sec_shape",
        shape_options,
        sec_shape_current,
        sync_callbacks,
        help_text="Matches Inputs page. Controls which geometry fields are shown.",
    )

    depth = _coalesce_num(
        st.session_state.get("shear_D", get_param("D", 600.0)), 600.0
    )
    span = _coalesce_num(
        st.session_state.get("shear_L", get_param("L", 3000.0)), 3000.0
    )
    section_shape = st.session_state.get(
        "shear_sec_shape", st.session_state.get("sec_shape", "RECT")
    )

    if section_shape == "RECT":
        width = _coalesce_num(
            st.session_state.get("shear_b", get_param("b", 400.0)), 400.0
        )
        number_row(
            "Width b (mm)",
            "shear_b",
            width,
            sync_callbacks,
            help_text="Shared with Inputs tab.",
        )
    elif section_shape == "T":
        flange_width = _coalesce_num(
            st.session_state.get("shear_bf", get_param("bf", 600.0)), 600.0
        )
        flange_thickness = _coalesce_num(
            st.session_state.get("shear_tf", get_param("tf", 120.0)), 120.0
        )
        web_width = _coalesce_num(
            st.session_state.get("shear_bw", get_param("bw", 300.0)), 300.0
        )
        number_row("Flange width bf (mm)", "shear_bf", flange_width, sync_callbacks)
        number_row(
            "Flange thickness tf (mm)",
            "shear_tf",
            flange_thickness,
            sync_callbacks,
        )
        number_row("Web width bw (mm)", "shear_bw", web_width, sync_callbacks)
    elif section_shape == "I":
        flange_width = _coalesce_num(
            st.session_state.get("shear_bf", get_param("bf", 600.0)), 600.0
        )
        flange_thickness = _coalesce_num(
            st.session_state.get("shear_tf", get_param("tf", 120.0)), 120.0
        )
        web_thickness = _coalesce_num(
            st.session_state.get("shear_tw", get_param("tw", 200.0)), 200.0
        )
        number_row(
            "Top flange width bf (mm)", "shear_bf", flange_width, sync_callbacks
        )
        number_row(
            "Top flange thickness tf (mm)",
            "shear_tf",
            flange_thickness,
            sync_callbacks,
        )
        number_row(
            "Web thickness tw (mm)", "shear_tw", web_thickness, sync_callbacks
        )

    number_row(
        "Depth D (mm)",
        "shear_D",
        depth,
        sync_callbacks,
        help_text="Overall section depth, shared with Inputs.",
    )
    number_row(
        "Span L (mm)",
        "shear_L",
        span,
        sync_callbacks,
        help_text="Clear span or design span for this section.",
    )

    if design_controls:
        st.info("🔒 Support condition is controlled by the Design page. Edit it there.")
    select_row(
        "Support condition (k₂)",
        support_widget_key,
        support_options,
        support_current,
        sync_callbacks,
        help_text=support_help_text,
        disabled=design_controls,
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


def _render_shear_reinforcement(*, st: Any, sync_callbacks: Any) -> None:
    auto_spacing_mode = bool(get_param("shear_auto_design", False))
    render_section_title("Shear reinforcement & section parameters")

    link_diameter_key = (
        get_widget_key_for_shared("lig_d", prefix="shear_") or "shear_lig_d"
    )
    link_legs_key = (
        get_widget_key_for_shared("lig_legs", prefix="shear_") or "shear_lig_legs"
    )
    link_spacing_key = (
        get_widget_key_for_shared("s_lig", prefix="shear_") or "shear_s_lig"
    )

    link_diameter = float(st.session_state.get("lig_d", 10.0))
    link_legs = float(st.session_state.get("lig_legs", 2))
    canonical_spacing = float(st.session_state.get("s_lig", 200.0) or 200.0)
    if auto_spacing_mode:
        if st.session_state.get(link_spacing_key) != canonical_spacing:
            st.session_state[link_spacing_key] = float(canonical_spacing)
        link_spacing = float(canonical_spacing)
    else:
        link_spacing = float(
            st.session_state.get(link_spacing_key, canonical_spacing)
            or canonical_spacing
        )

    select_row(
        "Link Ø (mm)",
        link_diameter_key,
        REO_BAR_DIAS,
        int(link_diameter),
        sync_callbacks,
        help_text="Nominal diameter of shear links (mm).",
    )
    select_row(
        "No. of legs",
        link_legs_key,
        REO_SHEAR_LEGS_OPTIONS,
        int(link_legs),
        sync_callbacks,
        help_text=(
            "Number of legs per shear link. Use 0 for no links; 2 or more for active shear reinforcement."
        ),
    )
    number_row(
        "Provided link spacing (mm)",
        link_spacing_key,
        link_spacing,
        sync_callbacks,
        help_text=(
            "Centre-to-centre spacing of shear links you provide (mm). Envelope-governed spacings for checks appear under Check 10."
        ),
        disabled=False,
    )


def _render_duct_parameters(*, st: Any, sync_callbacks: Any) -> None:
    render_section_title("Ducts & prestress voids")
    number_row(
        "Number of ducts crossing web",
        "shear_n_ducts",
        0.0,
        sync_callbacks,
        help_text="Number of prestressing ducts crossing the web.",
    )
    number_row(
        "Duct diameter (mm)",
        "shear_duct_dia",
        0.0,
        sync_callbacks,
        help_text="Diameter of each prestressing duct.",
    )

    number_of_ducts = get_param("n_ducts", 0.0)
    duct_diameter = get_param("duct_dia", 0.0)
    st.session_state["shear_sum_duct"] = duct_area_mm2(
        number_of_ducts, duct_diameter
    )

    duct_factor_key = (
        get_widget_key_for_shared("k_d_option", prefix="shear_")
        or "shear_k_d_option"
    )
    duct_factor = get_param("k_d_option", "None (no ducts in web)")
    if duct_factor not in KD_OPTIONS:
        duct_factor = "None (no ducts in web)"

    select_row(
        "k_d factor for prestressing ducts",
        duct_factor_key,
        KD_OPTIONS,
        duct_factor,
        sync_callbacks,
        help_text="k_d factor for prestressing ducts (AS 3600).",
    )
    selected_duct_factor = st.session_state.get(duct_factor_key, duct_factor)
    KD_VALUE_MAP.get(selected_duct_factor, 0.0)


def _render_method_parameters(*, st: Any, sync_callbacks: Any) -> None:
    number_row(
        "Maximum aggregate size d_g (mm)",
        "shear_d_g",
        20.0,
        sync_callbacks,
        help_text="Maximum aggregate size for k_v calculation.",
    )

    method_key = (
        get_widget_key_for_shared("k_v_method", prefix="shear_")
        or "shear_k_v_method"
    )
    method = get_param("k_v_method", "General εₓ-based (Cl. 8.2.4.2)")
    if method not in KV_METHOD_OPTIONS:
        method = "General εₓ-based (Cl. 8.2.4.2)"

    select_row(
        "k_v method",
        method_key,
        KV_METHOD_OPTIONS,
        method,
        sync_callbacks,
        help_text=(
            "Simplified (Cl. 8.2.4.3) vs general εx-based (Cl. 8.2.4.2). "
            "Open the page ℹ️ INFO expander for when to use each and why."
        ),
    )


def render_shear_inputs(
    *,
    st: Any,
    page_snapshot: ShearPageSnapshot,
    sync_callbacks: Any,
) -> None:
    """Render the existing Shear input cards in their established order."""

    design_controls = is_design_governing()
    is_design_driven = page_snapshot.view.actions_mode == "design"
    support_help_text = (
        "Support condition determines the deflection coefficient k₂ used in AS 3600 deflection calculations."
    )
    support_widget_key = (
        get_widget_key_for_shared("defl_support_type", prefix="shear_")
        or "shear_defl_support_type"
    )
    support_result = get_deflection_diagram_support_condition(st.session_state)
    support_current = support_result["support_type"]
    support_options = _deflection_support_options_for_value(support_current)
    if st.session_state.get(support_widget_key) != support_current:
        st.session_state[support_widget_key] = support_current

    config = build_shear_input_panel_config(st_module=st)
    with compact_check_input_regions(st, config) as (
        col_actions,
        col_geom_mat,
        col_shear_reo,
        col_shear_params,
    ):
        with st.container():
            with col_actions:
                if col_actions.open:
                    _render_design_actions(
                        st=st,
                        sync_callbacks=sync_callbacks,
                        is_design_driven=is_design_driven,
                        design_controls=design_controls,
                        support_current=support_current,
                    )

            with col_geom_mat:
                if col_geom_mat.open:
                    _render_geometry_and_materials(
                        st=st,
                        sync_callbacks=sync_callbacks,
                        design_controls=design_controls,
                        support_widget_key=support_widget_key,
                        support_options=support_options,
                        support_current=support_current,
                        support_help_text=support_help_text,
                    )

            with col_shear_reo:
                if col_shear_reo.open:
                    _render_shear_reinforcement(
                        st=st,
                        sync_callbacks=sync_callbacks,
                    )

            with col_shear_params:
                if col_shear_params.open:
                    _render_duct_parameters(
                        st=st,
                        sync_callbacks=sync_callbacks,
                    )

            with col_shear_reo:
                if col_shear_reo.open:
                    _render_method_parameters(
                        st=st,
                        sync_callbacks=sync_callbacks,
                    )


__all__ = ["build_shear_input_panel_config", "render_shear_inputs"]
