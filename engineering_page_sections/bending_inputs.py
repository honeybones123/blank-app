"""Bending input-card presentation helpers.

This module formats the existing revision-bound input snapshot.  It does not
calculate capacity or publish engineering results.
"""

from __future__ import annotations

from typing import Any, Mapping

from application.bottom_reinforcement_policy import (
    format_longitudinal_reinforcement_rows,
)
from state_and_helpers import (
    get_param,
    get_widget_key_for_shared,
    load_proxies_from_active_set,
    recalc_derived_values,
    render_timing_mark,
    save_proxies_to_active_set,
    update_results,
)
from widgets_helpers import (
    info_i_button,
    main_longitudinal_reo_pair_labels,
    normalized_sec_shape_ui,
    number_row,
    page_divider,
    render_longitudinal_reo_row_config_controls,
    render_longitudinal_reo_rows,
    render_section_title,
    select_row,
    show_reo_message,
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
from inputs_application.action_source_control import uses_load_analysis_actions


REO_BAR_DIAS = [10, 12, 16, 20, 24, 28, 32, 36, 40]
REO_COUNTS_0_12 = list(range(0, 13))
REO_SPACINGS = [75, 100, 125, 150, 175, 200, 225, 250, 275, 300]
REO_LAYOUT_MODE = ["Count", "Spacing"]


def _coalesce_num(value: Any, default: float) -> float:
    """Return ``default`` only for ``None`` while preserving zero."""

    return default if value is None else float(value)


def build_bending_input_panel_config(
    *,
    engineering_state: Mapping[str, Any],
    mu_pos_star_kNm: float,
    mu_neg_star_kNm: float,
    load_analysis_actions: bool,
) -> CheckInputPanelConfig:
    """Build the unchanged three-card Bending input presentation."""

    shape = str(engineering_state.get("sec_shape", "RECT") or "RECT")
    width = float(engineering_state.get("b", 0.0) or 0.0)
    depth = float(engineering_state.get("D", 0.0) or 0.0)
    concrete_strength = float(engineering_state.get("fc", 0.0) or 0.0)
    moment = max(abs(float(mu_pos_star_kNm)), abs(float(mu_neg_star_kNm)))
    axial_force = float(engineering_state.get("P_star", 0.0) or 0.0)
    bottom_summary = format_longitudinal_reinforcement_rows(
        engineering_state, face="bottom"
    )
    top_summary = format_longitudinal_reinforcement_rows(
        engineering_state, face="top"
    )

    return CheckInputPanelConfig(
        page_slug="bending",
        mount_closed_bodies=True,
        categories=(
            CheckInputCategory(
                "design_actions",
                "Design actions",
                join_summary(
                    f"M* {format_number(moment, 'kNm', decimals=1)}",
                    f"N* {format_number(axial_force, 'kN', decimals=1)}",
                ),
                lambda: None,
                source=(
                    InputSource.LOAD_ANALYSIS
                    if load_analysis_actions
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
                "reinforcement",
                "Reinforcement",
                join_summary(
                    f"Bottom {bottom_summary}",
                    f"Top {top_summary}",
                ),
                lambda: None,
                icon="●",
            ),
        ),
    )


def _render_design_actions(st: Any, sync_callbacks: Any) -> None:
    actions_mode = get_param("actions_mode", "manual")
    is_design_driven = actions_mode == "design"
    prev_mode = st.session_state.get("loads_edit_mode", "ULS")
    toggle_widget_key = (
        get_widget_key_for_shared("loads_edit_toggle", prefix="inputs_")
        or "inputs_loads_edit_toggle"
    )

    col_title, col_info = st.columns([0.92, 0.08], gap="small")
    with col_title:
        render_section_title("Design Actions")
    with col_info:
        with info_i_button(help_text="Source of design actions (M*, V*)"):
            st.markdown("Source: Inputs page selection", unsafe_allow_html=True)
            edit_sls = st.toggle(
                "View SLS loads",
                key=toggle_widget_key,
                persist_state="session",
                help=(
                    "Toggle which load set is shown below. ULS drives bending/shear; "
                    "SLS drives crack/deflection."
                ),
            )

            selected_mode_preview = "SLS" if edit_sls else "ULS"
            action_verb_preview = "viewing" if is_design_driven else "editing"

            if not is_design_driven:
                st.caption("Design actions: Manual")
            else:
                st.caption("Design actions: From SFD/BMD")
            st.caption(
                f"Currently {action_verb_preview}: **{selected_mode_preview}** loads"
            )

    new_mode = "SLS" if edit_sls else "ULS"
    if new_mode != prev_mode:
        st.session_state["loads_edit_mode"] = prev_mode
        save_proxies_to_active_set()
        st.session_state["loads_edit_mode"] = new_mode
        load_proxies_from_active_set()
        st.session_state["inputs_load_Mstar_pos_proxy"] = st.session_state.get(
            "load_Mstar_pos_proxy", 0.0
        )
        st.session_state["inputs_load_Mstar_neg_proxy"] = st.session_state.get(
            "load_Mstar_neg_proxy", 0.0
        )
        st.session_state["inputs_load_Nstar_proxy"] = st.session_state.get(
            "load_Nstar_proxy", 0.0
        )
        recalc_derived_values()
        update_results()
    else:
        st.session_state["loads_edit_mode"] = new_mode

    selected_mode = st.session_state.get("loads_edit_mode", "ULS")
    selected_prefix = "sls" if selected_mode == "SLS" else "uls"

    if is_design_driven:
        st.info(
            "Design actions are currently driven by the Design / Teaching page "
            "and are read-only here."
        )

    m_pos_proxy_widget_key = (
        get_widget_key_for_shared("load_Mstar_pos_proxy", prefix="inputs_")
        or "inputs_load_Mstar_pos_proxy"
    )
    m_neg_proxy_widget_key = (
        get_widget_key_for_shared("load_Mstar_neg_proxy", prefix="inputs_")
        or "inputs_load_Mstar_neg_proxy"
    )
    n_proxy_widget_key = (
        get_widget_key_for_shared("load_Nstar_proxy", prefix="inputs_")
        or "inputs_load_Nstar_proxy"
    )

    display_Mu_pos = get_param(
        f"{selected_prefix}_Mstar_pos_manual",
        max(0.0, get_param(f"{selected_prefix}_Mstar", 0.0)),
    )
    display_Mu_neg = get_param(
        f"{selected_prefix}_Mstar_neg_manual",
        max(0.0, -get_param(f"{selected_prefix}_Mstar", 0.0)),
    )
    display_N = get_param(f"{selected_prefix}_Nstar", 0.0)
    display_P = get_param("P_star", 0.0)

    if is_design_driven:
        if st.session_state.get(m_pos_proxy_widget_key) != display_Mu_pos:
            st.session_state[m_pos_proxy_widget_key] = display_Mu_pos
        if st.session_state.get(m_neg_proxy_widget_key) != display_Mu_neg:
            st.session_state[m_neg_proxy_widget_key] = display_Mu_neg
        if st.session_state.get(n_proxy_widget_key) != display_N:
            st.session_state[n_proxy_widget_key] = display_N
        if st.session_state.get("bending_P_star") != display_P:
            st.session_state["bending_P_star"] = display_P

    Mu_star_pos_val = max(0.0, _coalesce_num(display_Mu_pos, 0.0))
    Mu_star_neg_val = max(0.0, _coalesce_num(display_Mu_neg, 0.0))
    N_star_val = _coalesce_num(display_N, 0.0)
    P_star_val = _coalesce_num(display_P, 0.0)
    phi_b_val = _coalesce_num(
        st.session_state.get("bending_phi_b", get_param("phi_bend", 0.85)),
        0.85,
    )

    number_row(
        "Positive design moment Mu*+ (kNm)",
        m_pos_proxy_widget_key,
        Mu_star_pos_val,
        sync_callbacks,
        disabled=is_design_driven,
        help_text=(
            "Sagging bending demand magnitude. Positive bending corresponds to "
            "top compression and bottom tension."
        ),
    )
    number_row(
        "Negative design moment Mu*- (kNm)",
        m_neg_proxy_widget_key,
        Mu_star_neg_val,
        sync_callbacks,
        disabled=is_design_driven,
        help_text=(
            "Hogging bending demand magnitude. Enter as positive magnitude for "
            "top tension / bottom compression."
        ),
    )
    number_row(
        "Axial force N* (kN)",
        n_proxy_widget_key,
        N_star_val,
        sync_callbacks,
        disabled=is_design_driven,
        help_text=(
            "Axial force acting with bending. Compression (negative in many "
            "conventions) can reduce tension in the steel; tension increases demand."
        ),
    )
    number_row(
        "Prestress force P* (kN)",
        "bending_P_star",
        P_star_val,
        sync_callbacks,
        disabled=is_design_driven,
        help_text=(
            "Prestress / pre-compression in the section. Increasing P* typically "
            "reduces tensile demand in the bottom reinforcement."
        ),
    )
    number_row(
        "Maximum bending strength factor phi_b,max",
        "bending_phi_b",
        phi_b_val,
        sync_callbacks,
        help_text=(
            "Upper limit for the AS 3600 bending strength factor. The authoritative "
            "calculation derives phi from the calculated k_u and applies this value "
            "only as a maximum."
        ),
    )


def _render_geometry_material(st: Any, sync_callbacks: Any) -> None:
    render_section_title("Geometry & Materials")
    shape_options = ["RECT", "T", "I"]
    sec_shape_current = st.session_state.get("sec_shape", "RECT")
    if sec_shape_current not in shape_options:
        sec_shape_current = "RECT"

    select_row(
        "Section shape",
        "bending_sec_shape",
        shape_options,
        sec_shape_current,
        sync_callbacks,
        help_text="Matches Inputs page. Controls which geometry fields are shown.",
    )

    D_val = _coalesce_num(
        st.session_state.get("bending_D", get_param("D", 600.0)), 600.0
    )
    L_val = _coalesce_num(
        st.session_state.get("bending_L", get_param("L", 3000.0)), 3000.0
    )
    sec_shape = st.session_state.get(
        "bending_sec_shape", st.session_state.get("sec_shape", "RECT")
    )

    if sec_shape == "RECT":
        b_val = _coalesce_num(
            st.session_state.get("bending_b", get_param("b", 400.0)), 400.0
        )
        number_row(
            "Width b (mm)",
            "bending_b",
            b_val,
            sync_callbacks,
            help_text=(
                "Section width. Increasing b increases compression block area and "
                "reduces required tensile steel for a given Mu*."
            ),
        )
    elif sec_shape == "T":
        bf_val = _coalesce_num(
            st.session_state.get("bending_bf", get_param("bf", 600.0)), 600.0
        )
        tf_val = _coalesce_num(
            st.session_state.get("bending_tf", get_param("tf", 120.0)), 120.0
        )
        bw_val = _coalesce_num(
            st.session_state.get("bending_bw", get_param("bw", 300.0)), 300.0
        )
        number_row("Flange width bf (mm)", "bending_bf", bf_val, sync_callbacks)
        number_row(
            "Flange thickness tf (mm)", "bending_tf", tf_val, sync_callbacks
        )
        number_row("Web width bw (mm)", "bending_bw", bw_val, sync_callbacks)
    elif sec_shape == "I":
        bf_val = _coalesce_num(
            st.session_state.get("bending_bf", get_param("bf", 600.0)), 600.0
        )
        tf_val = _coalesce_num(
            st.session_state.get("bending_tf", get_param("tf", 120.0)), 120.0
        )
        tw_val = _coalesce_num(
            st.session_state.get("bending_tw", get_param("tw", 200.0)), 200.0
        )
        number_row(
            "Top flange width bf (mm)", "bending_bf", bf_val, sync_callbacks
        )
        number_row(
            "Top flange thickness tf (mm)", "bending_tf", tf_val, sync_callbacks
        )
        number_row("Web thickness tw (mm)", "bending_tw", tw_val, sync_callbacks)

    number_row(
        "Depth D (mm)",
        "bending_D",
        D_val,
        sync_callbacks,
        help_text=(
            "Overall section depth. Larger D increases lever arm (d) and typically "
            "increases bending capacity."
        ),
    )
    number_row(
        "Span L (mm)",
        "bending_L",
        L_val,
        sync_callbacks,
        help_text=(
            "Member span. Used mainly for serviceability checks and linking to "
            "deflection; not directly in ϕMu,cap here."
        ),
    )

    fc_val = _coalesce_num(
        st.session_state.get("bending_fc", get_param("fc", 40.0)), 40.0
    )
    fsy_val = _coalesce_num(
        st.session_state.get("bending_fsy", get_param("fsy", 500.0)), 500.0
    )
    number_row(
        "Concrete strength f'c (MPa)",
        "bending_fc",
        fc_val,
        sync_callbacks,
        help_text=(
            "Concrete compressive strength. Higher f'c increases compression "
            "capacity and may reduce required steel, but also changes ductility limits."
        ),
    )
    number_row(
        "Steel yield fsy (MPa)",
        "bending_fsy",
        fsy_val,
        sync_callbacks,
        help_text=(
            "Yield strength of reinforcing steel. Higher fsy increases the force "
            "carried by a given area of steel."
        ),
    )


def _render_reinforcement_face(
    st: Any,
    sync_callbacks: Any,
    *,
    face: str,
    title: str,
    section_shape: str,
    is_t_or_i: bool,
) -> None:
    face_title = "Bottom" if face == "bot" else "Top"
    title_col, info_col = st.columns(
        [0.92, 0.08], vertical_alignment="center"
    )
    with title_col:
        render_section_title(title)

    rowgap_key = f"bending_rowgap_{face}"
    rowgap_val = float(
        st.session_state.get(rowgap_key, get_param(f"rowgap_{face}", 60.0))
    )
    with info_col:
        with info_i_button(
            help_text="Row count and vertical gap between reinforcement layers."
        ):
            render_longitudinal_reo_row_config_controls(
                page_prefix="bending",
                section=face,
                sync_callbacks=sync_callbacks,
                rowgap_widget_key=rowgap_key,
                rowgap_default=rowgap_val,
                rowgap_help_text="Clear vertical gap between reinforcement rows (mm).",
                sec_shape=section_shape,
            )

    st.markdown('<div class="compact-reo">', unsafe_allow_html=True)
    layer_name = f"{face_title} Layer 1"
    transient_messages = (
        (f"_reo_msg_{face}_auto_layer2", "auto_layer2"),
        (f"_reo_msg_{face}_layer2_overwritten", "layer2_overwritten"),
        (f"_reo_error_{face}_1", "layout_invalid"),
    )
    for state_key, message_key in transient_messages:
        if st.session_state.get(state_key, False):
            show_reo_message(message_key, layer=layer_name)
            st.session_state[state_key] = False

    warning_key = f"_reo_warning_{face}_1"
    warning = st.session_state.get(warning_key)
    if warning:
        spacing_key = f"_reo_s_min_{face}_1"
        s_min_val = st.session_state.get(spacing_key, 25.0)
        show_reo_message("spacing_clamped", layer=layer_name, s_min=s_min_val)
        st.session_state[warning_key] = None
        st.session_state[spacing_key] = None

    render_longitudinal_reo_rows(
        page_prefix="bending",
        section=face,
        sync_callbacks=sync_callbacks,
        layout_modes=REO_LAYOUT_MODE,
        count_options=REO_COUNTS_0_12,
        spacing_options=REO_SPACINGS,
        dia_options=REO_BAR_DIAS,
        single_column=True,
        sec_shape=section_shape,
    )

    cover_key = f"bending_cover_{face}"
    cover_val = _coalesce_num(
        st.session_state.get(cover_key, get_param(f"cover_{face}", 40.0)), 40.0
    )
    if face == "bot":
        cover_help = (
            "Concrete cover to bottom web reinforcement (T/I: stem/web, not flange). "
            "Increasing cover reduces effective depth d and reduces ϕMu,cap, but may "
            "be required for durability."
            if is_t_or_i
            else "Concrete cover to bottom reinforcement. Increasing cover reduces "
            "effective depth d and reduces ϕMu,cap, but may be required for durability."
        )
    else:
        cover_help = (
            "Concrete cover to top web reinforcement (T/I: stem/web, not flange). "
            "Affects effective depth to compression reinforcement and durability."
            if is_t_or_i
            else "Concrete cover to top reinforcement. Affects effective depth to "
            "compression reinforcement and durability."
        )

    number_row(
        f"{face_title} cover (mm)",
        cover_key,
        cover_val,
        sync_callbacks,
        help_text=cover_help,
    )
    st.markdown("</div>", unsafe_allow_html=True)


def render_bending_inputs(
    *,
    st: Any,
    engineering_state: Mapping[str, Any],
    mu_pos_star_kNm: float,
    mu_neg_star_kNm: float,
    sync_callbacks: Any,
) -> None:
    """Render the existing Bending input cards inside the shell-owned slot."""

    page_divider()
    config = build_bending_input_panel_config(
        engineering_state=engineering_state,
        mu_pos_star_kNm=mu_pos_star_kNm,
        mu_neg_star_kNm=mu_neg_star_kNm,
        load_analysis_actions=uses_load_analysis_actions(st.session_state),
    )
    render_timing_mark("bending_page.runtime.summary_table.end")

    with compact_check_input_regions(st, config) as (
        col_actions,
        col_geom_mat,
        col_reinforcement,
    ):
        with col_reinforcement:
            with st.container(
                border=False,
                key="compact_check_inputs_full_span_bending_reinforcement",
            ):
                col_bottom, col_top = st.columns(2, gap="medium")

        with st.container():
            with col_actions:
                if col_actions.open:
                    _render_design_actions(st, sync_callbacks)

            with col_geom_mat:
                if col_geom_mat.open:
                    _render_geometry_material(st, sync_callbacks)

            section_shape = str(
                st.session_state.get("bending_sec_shape")
                or st.session_state.get("sec_shape")
                or get_param("sec_shape", "RECT")
                or "RECT"
            )
            is_t_or_i = normalized_sec_shape_ui(section_shape) in ("T", "I")
            bottom_title, top_title = main_longitudinal_reo_pair_labels(
                section_shape, variant="bending"
            )

            with col_bottom:
                if col_reinforcement.open:
                    _render_reinforcement_face(
                        st,
                        sync_callbacks,
                        face="bot",
                        title=bottom_title,
                        section_shape=section_shape,
                        is_t_or_i=is_t_or_i,
                    )

            with col_top:
                if col_reinforcement.open:
                    _render_reinforcement_face(
                        st,
                        sync_callbacks,
                        face="top",
                        title=top_title,
                        section_shape=section_shape,
                        is_t_or_i=is_t_or_i,
                    )


__all__ = ["build_bending_input_panel_config", "render_bending_inputs"]
