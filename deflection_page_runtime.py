# deflection_page.py
import math
import pandas as pd
import streamlit as st
from pathlib import Path

from inputs_application.session_services import InputsSessionServices

from state_and_helpers import (
    init_shared_session_state,
    get_param,
    get_sync_callbacks,
    get_widget_key_for_shared,
    is_design_governing,
    resolve_design_actions,
    update_results,  # kept for contract / future use
    DEFLECTION_LIMIT_OPTIONS,
    DEFLECTION_LIMIT_HELP_TEXT,
    get_deflection_limit_ratio,
    get_deflection_limit_label_from_ratio,
    TAB_KEYS,
    render_timing_mark,
)
from widgets_helpers import (
    apply_global_widget_css,
    apply_result_page_css,
    apply_calcbox_css,
    apply_step_summary_expander_css,
    render_result_page_title,
    render_page_explainer_expander,
    number_row,
    calcbox,
    label_with_hover,
    v2_number_input,
    v2_selectbox,
    v2_checkbox,
    v2_radio,
    info_i_button,
    page_divider,
    render_longitudinal_reo_rows,
    render_longitudinal_reo_row_config_controls,
    main_longitudinal_reo_pair_labels,
    specialized_widget_rail_columns,
    render_plotly_diagram,
    COMPACT_SIDE_VIEW_HEIGHT_PX,
    compact_side_view_figure,
    inject_compact_side_view_spacing,
)
from step_ui import init_step_ui_state, render_expandable_step
from engineering_check_ui import DEFLECTION_CHECK_SUMMARY_COLUMNS
from ui_seamless_steps import render_clickable_summary_table, bind_summary_clicks
from ui.summary_rows import build_deflection_summary_rows
from deflection_checks_helpers import build_deflection_check_rows_from_state
from ui.diagrams.deflection_diagram import (
    build_deflected_beam_plotly,
    build_deflected_shape_figure,
    deflected_longitudinal_profile_mm,
)
from calculations.deflection import (
    DEFLECTION_SUPPORT_OPTIONS_BASE,
    SUPPORT_DEFLECTION_MAP,
    active_multispan_lengths_m as _calc_active_multispan_lengths_m,
    calc_deflection_as3600,
    calc_ief_simplified,
    calc_span_depth_limit,
    compression_to_tension_steel_ratio,
    deflection_sustained_load_factor,
    deflection_limit_check_values,
    effective_flexural_rigidity_kNm2,
    effective_stiffness_coefficient_k1,
    defl_support_type_from_design_selection as _defl_support_type_from_design_selection,
    deflection_from_sfd_case as _deflection_from_sfd_case,
    design_multispan_mode_from_state as _calc_is_design_multispan_mode,
    deflection_support_options_for_value as _deflection_support_options_for_value,
    derive_equiv_udl_from_actions as _derive_equiv_udl_from_actions,
    effective_design_load_from_shear,
    effective_flange_width_ratio,
    deflection_multispan_load_split_values,
    format_L_over_delta,
    governing_span_support_pair as _governing_span_support_pair,
    has_udl_line_loads,
    multispan_design_elastic_loads as _calc_multispan_design_elastic_loads,
    multispan_deflection_metric_values,
    normalize_deflection_support_type as _normalize_deflection_support_type,
    pick_controlling_span_index as _pick_controlling_span_index,
    resolve_deflection_equiv_loads_from_inputs,
    simplified_ief_k1_factor,
    span_depth_display_values,
    span_deflection_utilisation_values,
    span_to_depth_ratio,
    support_props as _support_props,
    support_type_from_sfd_case as _support_type_from_sfd_case,
    tension_reinforcement_ratio,
)


# Standard reinforcement lists (shared with Inputs page patterns)
REO_BAR_DIAS = [10, 12, 16, 20, 24, 28, 32, 36, 40]
REO_COUNTS_0_12 = list(range(0, 13))
REO_SPACINGS = [75, 100, 125, 150, 175, 200, 225, 250, 275, 300]
REO_LAYOUT_MODE = ["Count", "Spacing"]


_DEBUG_DEFLECTION_SUPPORT_RESOLUTION = False


# ``compute_deflection_results`` publishes the shared report used by other
# pages, while this renderer performs its own display calculation below.  The
# published calculation used to run on every Streamlit rerun, including
# reruns caused only by navigation or expander interaction.  Keep a narrow,
# state-based cache boundary here so a changed input can never reuse an old
# publication, without changing the visible page or calculation formulas.
_DEFLECTION_CORE_CACHE_KEYS = (
    "b",
    "D",
    "L",
    "fc",
    "Ec",
    "Eceff",
    "Ast_bot",
    "Ast_top",
    "d",
    "sfd_case",
    "g_udl_kNm_per_m",
    "q_udl_kNm_per_m",
    "w_sls_kNm_per_m",
    "P_sls_kN",
    "psi_udl",
    "psi_point",
    "defl_beff",
    "defl_bw",
    "defl_L_eff",
    "defl_limit_ratio",
    "defl_Fdef",
    "actions_source",
    "sls_Mstar",
    "sls_Vstar",
    "span_L_m",
    "actions_mode",
    "defl_support_type",
    "sfd_beam_system_mode",
    "design_beam_system_mode",
    "sfd_support_condition",
    "design_support_condition",
    "defl_use_simplified_ief",
    "defl_Ief_user",
)
_DEFLECTION_CORE_CACHE_PREFIXES = (
    "sfd_span_",
    "load_ms_",
)


def _deflection_core_cache_key() -> tuple:
    """Return a deterministic key for the published Deflection computation."""

    values: list[tuple[str, str]] = []
    for key in _DEFLECTION_CORE_CACHE_KEYS:
        try:
            value = get_param(key, None)
        except Exception:
            value = st.session_state.get(key)
        if value is None:
            value = st.session_state.get(key)
        values.append((key, repr(value)))

    # Multi-span metrics read indexed keys, so include those without making
    # the cache depend on unrelated session-state/UI bookkeeping keys.
    for key in sorted(st.session_state.keys()):
        if key.startswith(_DEFLECTION_CORE_CACHE_PREFIXES):
            values.append((key, repr(st.session_state.get(key))))

    revision = int(
        InputsSessionServices.from_mapping(st.session_state)
        .input_snapshots.current()
        .revision
        or 0
    )
    return revision, tuple(values)


# Extracted section owners; the runtime below retains ordered page composition only.
from engineering_page_sections import deflection_diagrams as _deflection_diagrams_section
from engineering_page_sections import deflection_support as _deflection_support_section
from engineering_page_sections import deflection_inputs as _deflection_inputs_section

_deflection_diagram_reo_layers = _deflection_diagrams_section._deflection_diagram_reo_layers
_refresh_deflection_effective_span_from_mm = _deflection_support_section._refresh_deflection_effective_span_from_mm
seed_design_deflection_support_widget_before_render = _deflection_support_section.seed_design_deflection_support_widget_before_render
_is_design_multispan_mode = _deflection_support_section._is_design_multispan_mode
_multispan_design_elastic_loads = _deflection_support_section._multispan_design_elastic_loads
_active_multispan_lengths_m = _deflection_support_section._active_multispan_lengths_m
compute_and_store_multispan_deflection_metrics = _deflection_support_section.compute_and_store_multispan_deflection_metrics
get_deflection_diagram_support_condition = _deflection_support_section.get_deflection_diagram_support_condition
get_resolved_deflection_support_type = _deflection_support_section.get_resolved_deflection_support_type
_seed_from_param = _deflection_inputs_section._seed_from_param
_render_readonly_value = _deflection_inputs_section._render_readonly_value

_PAGE_SECTION_MODULES = (
    _deflection_diagrams_section,
    _deflection_support_section,
    _deflection_inputs_section,
)
for _page_section_module in _PAGE_SECTION_MODULES:
    _page_section_module.bind_runtime(globals())

def render_deflection():
    page_title_placeholder = st.empty()
    """Deflection page – short-term, long-term, span/depth to AS 3600:2018 Cl. 8.5."""
    render_timing_mark("deflection_page.runtime.start")
    # NOTE: init_shared_session_state() is called by app.py router before this
    # function runs.

    # Pages must NOT call init/hydrate themselves - the router owns the
    # lifecycle.

    sync_callbacks = get_sync_callbacks()

    # Handle cross-page navigation from Inputs page
    from jump_nav import get_jump_uid
    get_jump_uid()

    apply_global_widget_css()
    apply_result_page_css()
    apply_calcbox_css()
    apply_step_summary_expander_css()
    sync_callbacks = get_sync_callbacks()  # not used yet but kept for contract

    # CSS for readonly-param styling (for linked values)
    st.markdown(
        """
<style>
/* Read-only linked-parameter chips */
.readonly-param {
  border-left: 4px solid #6c757d;
  background-color: rgba(108, 117, 125, 0.08);
  padding: 0.4rem 0.6rem;
  margin-bottom: 0.4rem;
  border-radius: 0 0.35rem 0.35rem 0;
  font-size: 0.85rem;
}
.readonly-param-value {
  font-weight: 500;
}
</style>
""",
        unsafe_allow_html=True,
    )

    # Initialize step UI state (matches Shear pattern)
    init_step_ui_state("deflection")

    def _render_deflection_explainer() -> None:
        st.markdown(
            """
This page checks **reinforced concrete beam deflections** to AS 3600:2018:

- Short-term deflection
- Long-term deflection using **kₛₛ**
- Deemed-to-conform **span-to-depth ratio**
- **Simplified effective stiffness** \\(I_{ef}\\) for reinforced members
            """
        )

    with page_title_placeholder.container():
        render_result_page_title("Beam Deflection")

    # Reserve space for the top summary table
    summary_placeholder = st.empty()

    # --- Hydrate deflection page widget keys from shared (only if missing/None) ---
    def _seed_widget_from_shared(
        widget_key: str,
        shared_key: str,
        fallback: float = 0.0,
    ):
        if widget_key not in st.session_state or st.session_state[widget_key] is None:
            v = get_param(shared_key, fallback)
            st.session_state[widget_key] = fallback if v is None else v

    _seed_widget_from_shared("defl_b", "b", 0.0)
    _seed_widget_from_shared("defl_D", "D", 0.0)
    _seed_widget_from_shared("defl_L", "L", 0.0)
    _seed_widget_from_shared("defl_fc", "fc", 0.0)
    defl_support_widget_key = (
        get_widget_key_for_shared("defl_support_type", prefix="defl_")
        or "defl_defl_support_type"
    )
    _seed_widget_from_shared(defl_support_widget_key, "defl_support_type", "Simply supported")
    defl_limit_widget_key = (
        get_widget_key_for_shared("defl_limit_ratio", prefix="defl_")
        or "defl_defl_limit_ratio"
    )
    _seed_widget_from_shared(defl_limit_widget_key, "defl_limit_ratio", 250.0)
    # ---------- Actions from Inputs page ----------
    actions_source = get_param(
        "actions_source",
        "Manual design actions (inputs below)",
    )
    is_design_driven = (
        "Teaching" in actions_source
        or actions_source == "Teaching SFD/BMD page (|M|max, |V|max)"
    )

    # Deflection always uses SLS actions (manual inputs)
    M_used = get_param("sls_Mstar", 0.0)
    V_used = get_param("sls_Vstar", 0.0)

    # Also get the final chosen values (SLS actions for display/other uses)
    Mu_star = get_param("sls_Mstar", 0.0)
    Vu_star = get_param("sls_Vstar", 0.0)

    # ---------- Unified loading from SFD/BMD page ----------
    load_case = st.session_state.get("load_case", None)
    L_sfd = get_param("span_L_m", None)  # span in m

    # Get SLS loads (either UDL or point load depending on case)
    w_sls = get_param("w_sls_kNm_per_m", None)  # SLS UDL if applicable
    P_sls = get_param("P_sls_kN", None)  # SLS point load if applicable
    a = get_param("a_m", None)  # Distance a for point loads

    # For display in calcbox (fallback values)
    g = get_param("g_udl_kNm_per_m", 0.0)
    q = get_param("q_udl_kNm_per_m", 0.0)
    psi_s = get_param("psi_udl", 0.4)
    G_point = get_param("G_point_kN", 0.0)
    Q_point = get_param("Q_point_kN", 0.0)

    # Determine effective load for deflection
    w_eff = w_sls if w_sls is not None else None

    # Deflected shape slot (filled after inputs + reo + compute in this run).
    diagram_placeholder = st.empty()

    render_timing_mark("deflection_page.runtime.inputs.start")
    st.markdown("**Design inputs**")

    # Helper function for label-left / widget-right layout with hover help
    def _input_row(label: str, help_text: str | None, render_widget_fn):
        c1, c2 = st.columns([1.2, 1.0])
        with c1:
            label_with_hover(label, help_text)
        with c2:
            return render_widget_fn()

    def _derive_fd_ef(
        actions_source: str,
        support_type_value: str,
        L_m_value: float | None,
        V_manual_kN: float | None,
        V_design_kN: float | None,
        fallback_value: float,
    ) -> tuple[float, str, str, dict]:
        """Derive F_d,ef from action source with explicit branch tracking."""
        is_manual = actions_source == "Manual design actions (inputs below)"
        is_design = (
            "Teaching" in actions_source
            or actions_source == "Teaching SFD/BMD page (|M|max, |V|max)"
        )

        branch = "fallback"
        source_text = "Fallback value used because derivation inputs were unavailable."
        meta = {
            "V_kN": None,
            "L_m": L_m_value,
            "support_type": support_type_value,
            "formula_label": None,
            "actions_source": actions_source,
        }

        V_kN = V_manual_kN if is_manual else V_design_kN if is_design else None
        fd_ef_derived, derived_formula_label = effective_design_load_from_shear(
            V_kN=V_kN,
            L_m=L_m_value,
            support_type=support_type_value,
        )
        if (
            L_m_value is not None
            and L_m_value > 0
            and V_kN is not None
            and V_kN > 0
        ):
            if support_type_value in ("Simply supported", "Pinned–Pinned"):
                fd_ef_used = fd_ef_derived
                formula_label = derived_formula_label
            elif support_type_value == "Cantilever":
                fd_ef_used = fd_ef_derived
                formula_label = derived_formula_label
            else:
                fd_ef_used = fd_ef_derived
                formula_label = derived_formula_label

            if is_manual:
                branch = "manual_actions"
                source_text = "Derived from manual Inputs-page actions."
            elif is_design:
                branch = "design_actions"
                source_text = "Derived from Teaching / design actions."
            else:
                branch = "fallback"
                source_text = (
                    "Fallback value used because derivation inputs were unavailable."
                )

            meta.update({"V_kN": V_kN, "formula_label": formula_label})
            return fd_ef_used, branch, source_text, meta

        return fallback_value, branch, source_text, meta

    # One shared rail: three visible columns, with reinforcement continuing
    # horizontally to the right in the same three-row shell.
    col_geom, col_mats, col_loads, col_reo_bot, col_reo_top = specialized_widget_rail_columns(
        "deflection_primary_inputs",
        5,
        gap="large",
    )

    # ---------- Column 1: Geometry ----------
    with col_geom:
        st.markdown("**Geometry**")
        L_seed_mm = _seed_from_param("L", 3000.0)
        L_eff = st.session_state.get("defl_L_eff", L_seed_mm / 1000.0)

        b_seed = _seed_from_param("b", 300.0)
        b = _input_row(
            "Beam width b (mm)",
            "Beam width of the section.",
            lambda: v2_number_input(
                label="Value",
                key="defl_b",
                default=b_seed,
                step=10.0,
                label_visibility="collapsed",
                on_change=sync_callbacks["defl_b"],
            ),
        )

        # Beam depth D (mm)
        D_seed = _seed_from_param("D", 600.0)
        D = _input_row(
            "Beam depth D (mm)",
            "Overall beam depth from compression face to soffit.",
            lambda: v2_number_input(
                label="Value",
                key="defl_D",
                default=D_seed,
                step=10.0,
                label_visibility="collapsed",
                on_change=sync_callbacks.get("defl_D") or (lambda: None),
            ),
        )
        # Ensure D is a float for calculations
        if D is None:
            D = D_seed
        else:
            D = float(D)

        # Span L (mm)
        L_seed = _seed_from_param("L", 3000.0)
        L = _input_row(
            "Span L (mm)",
            "Clear span used for deflection checks.",
            lambda: v2_number_input(
                label="Value",
                key="defl_L",
                default=L_seed,
                step=100.0,
                label_visibility="collapsed",
                on_change=sync_callbacks["defl_L"],
            ),
        )
        _refresh_deflection_effective_span_from_mm(L, fallback_mm=L_seed)

        # Derived: web width (for calculations; shown in calc box)
        bw = st.session_state.get("defl_bw", b)

        # Read-only: effective flange width (computed/derived)
        beff_widget = st.session_state.get("defl_beff", None)
        if beff_widget is not None:
            beff = float(beff_widget)
        else:
            beff = _seed_from_param("defl_beff", b_seed)

        # Derived: effective depth (for calculations; shown in calc box)
        d = _seed_from_param("d", 550.0)

    # ---------- Column 2: Materials ----------
    with col_mats:
        st.markdown("**Materials**")

        fc_seed = _seed_from_param("fc", 32.0)
        fc = _input_row(
            "Concrete strength f'c (MPa)",
            "Concrete compressive strength.",
            lambda: v2_number_input(
                label="Value",
                key="defl_fc",
                default=fc_seed,
                step=1.0,
                label_visibility="collapsed",
                on_change=sync_callbacks["defl_fc"],
            ),
        )

        Ec_short = float(get_param("Ec", 30000.0) or 30000.0)
        phi_cc_t = float(get_param("phi_cc_t", 2.0) or 0.0)
        Ec = float(get_param("Eceff", Ec_short) or Ec_short)
        stress_ratio = float(get_param("stress_ratio", 0.0) or 0.0)
        sustained_sigma_cs = float(get_param("sustained_sigma_cs_mpa", 0.0) or 0.0)
        sustained_mstar = float(get_param("sustained_Mstar_kNm", 0.0) or 0.0)
        sustained_z_comp = float(get_param("sustained_section_modulus_mm3", 0.0) or 0.0)

    # ---------- Column 3: Serviceability ----------
    with col_loads:
        st.markdown("**Serviceability**")
        # Governing multispan metrics come from compute_all_results / final compute below
        # (not an early preview write) so support resolution matches per-span loads.
        support_resolution = get_deflection_diagram_support_condition(st.session_state)
        design_controls = is_design_governing()
        w_support = (
            defl_support_widget_key
        )
        current_support_type = support_resolution["support_type"]
        support_options = _deflection_support_options_for_value(current_support_type)
        support_help_text = (
            "Support condition determines the deflection coefficient k₂ used in "
            "AS 3600 deflection calculations."
        )
        default_idx = (
            support_options.index(current_support_type)
            if current_support_type in support_options
            else 0
        )

        if design_controls:
            seed_design_deflection_support_widget_before_render(w_support, current_support_type)

        if design_controls:
            st.info(
                "🔒 Support condition (k₂) is **auto-derived** from the Design / SFD model. "
                "It stays aligned with the value used in calculations."
            )
        support_type_widget = _input_row(
            "Support condition (k₂)",
            support_help_text,
            lambda: v2_selectbox(
                label="Value",
                key=w_support,
                options=support_options,
                default_index=default_idx,
                label_visibility="collapsed",
                disabled=design_controls,
                on_change=sync_callbacks[w_support],
            ),
        )
        support_type = (
            support_resolution["support_type"]
            if design_controls
            else _normalize_deflection_support_type(support_type_widget)
        )

        defl_limit_default = get_deflection_limit_ratio(get_param("defl_limit_ratio", 250.0))
        defl_limit_ratio = _input_row(
            "Deflection limit L/Δ",
            DEFLECTION_LIMIT_HELP_TEXT,
            lambda: v2_selectbox(
                label="Value",
                key=defl_limit_widget_key,
                options=list(DEFLECTION_LIMIT_OPTIONS.values()),
                default_index=list(DEFLECTION_LIMIT_OPTIONS.values()).index(defl_limit_default),
                format_func=lambda v: get_deflection_limit_label_from_ratio(v),
                label_visibility="collapsed",
                on_change=sync_callbacks[defl_limit_widget_key],
            ),
        )

    _defl_sec_shape_ui = str(get_param("sec_shape", "RECT") or "RECT")
    _defl_bot_md, _defl_top_md = main_longitudinal_reo_pair_labels(
        _defl_sec_shape_ui, variant="sentence_lower"
    )

    # ---------- Column 4: Bottom reinforcement ----------
    with col_reo_bot:
        _defl_bot_title_col, _defl_bot_info_col = st.columns(
            [0.92, 0.08], vertical_alignment="center"
        )
        with _defl_bot_title_col:
            st.markdown(f"**{_defl_bot_md.title()}**")
        rowgap_bot_val = float(
            st.session_state.get(
                "defl_rowgap_bot", get_param("rowgap_bot", 60.0)
            )
            or 60.0
        )
        with _defl_bot_info_col:
            with info_i_button(
                help_text="Row count and vertical gap between reinforcement layers."
            ):
                render_longitudinal_reo_row_config_controls(
                    page_prefix="defl",
                    section="bot",
                    sync_callbacks=sync_callbacks,
                    rowgap_widget_key="defl_rowgap_bot",
                    rowgap_default=rowgap_bot_val,
                    rowgap_help_text="Clear vertical gap between reinforcement rows (mm).",
                    sec_shape=_defl_sec_shape_ui,
                )
        render_longitudinal_reo_rows(
            page_prefix="defl",
            section="bot",
            sync_callbacks=sync_callbacks,
            layout_modes=REO_LAYOUT_MODE,
            count_options=REO_COUNTS_0_12,
            spacing_options=REO_SPACINGS,
            dia_options=REO_BAR_DIAS,
            single_column=True,
            sec_shape=_defl_sec_shape_ui,
        )

    # ---------- Column 5: Top reinforcement ----------
    with col_reo_top:
        _defl_top_title_col, _defl_top_info_col = st.columns(
            [0.92, 0.08], vertical_alignment="center"
        )
        with _defl_top_title_col:
            st.markdown(f"**{_defl_top_md.title()}**")
        rowgap_top_val = float(
            st.session_state.get(
                "defl_rowgap_top", get_param("rowgap_top", 60.0)
            )
            or 60.0
        )
        with _defl_top_info_col:
            with info_i_button(
                help_text="Row count and vertical gap between reinforcement layers."
            ):
                render_longitudinal_reo_row_config_controls(
                    page_prefix="defl",
                    section="top",
                    sync_callbacks=sync_callbacks,
                    rowgap_widget_key="defl_rowgap_top",
                    rowgap_default=rowgap_top_val,
                    rowgap_help_text="Clear vertical gap between reinforcement rows (mm).",
                    sec_shape=_defl_sec_shape_ui,
                )
        render_longitudinal_reo_rows(
            page_prefix="defl",
            section="top",
            sync_callbacks=sync_callbacks,
            layout_modes=REO_LAYOUT_MODE,
            count_options=REO_COUNTS_0_12,
            spacing_options=REO_SPACINGS,
            dia_options=REO_BAR_DIAS,
            single_column=True,
            sec_shape=_defl_sec_shape_ui,
        )

    page_divider()

    # Derive F_d,ef from Inputs / Teaching actions (after column inputs)
    V_design_kN = get_param("Vu_star", 0.0) or 0.0
    V_manual_kN = get_param("Vu_star_manual", 0.0) or 0.0

    L_m_for_fd = get_param("defl_L_eff", 0.0)
    if L_m_for_fd is None or L_m_for_fd <= 0:
        L_m_for_fd = get_param("span_L_m", 0.0)
        if L_m_for_fd is None:
            L_m_for_fd = 0.0

    fd_fallback = get_param("defl_Fdef", 12.0)

    defl_limit_ratio = float(get_deflection_limit_ratio(defl_limit_ratio))
    defl_limit_label = get_deflection_limit_label_from_ratio(defl_limit_ratio)

    fd_ef_used, fd_ef_source_branch, value_source_text, fd_ef_meta = _derive_fd_ef(
        actions_source=actions_source,
        support_type_value=support_type,
        L_m_value=L_m_for_fd,
        V_manual_kN=V_manual_kN,
        V_design_kN=V_design_kN,
        fallback_value=fd_fallback,
    )

    Fdef_kNm = fd_ef_used

    # Read derived reinforcement areas for calculations (no UI rows)
    Ast = _seed_from_param("Ast_bot", 2010.0)
    Asc = _seed_from_param("Ast_top", 0.0)

    render_timing_mark("deflection_page.runtime.compute.start")
    # Refresh the published report only when its input state has changed.  The
    # page-local display calculation below still runs from the current inputs;
    # this guard removes the duplicate publication/report build on idle
    # reruns, navigation, and expander interactions.
    from deflection_core import compute_deflection_results
    _deflection_cache_key = _deflection_core_cache_key()
    _deflection_results_state = st.session_state.get("results")
    _deflection_params_present = isinstance(_deflection_results_state, dict) and isinstance(
        _deflection_results_state.get("_deflection_params"), dict
    )
    _deflection_report_present = isinstance(_deflection_results_state, dict) and (
        "deflection_report" in _deflection_results_state
        or "deflection_report_error" in _deflection_results_state
    )
    if (
        st.session_state.get("_deflection_core_cache_key") != _deflection_cache_key
        or not _deflection_params_present
        or not _deflection_report_present
    ):
        compute_deflection_results(publish=True)
        st.session_state["_deflection_core_cache_key"] = _deflection_cache_key

    # --------------------------------------------------------
    # SINGLE COMPUTED VALUES BLOCK (compute once, use everywhere)
    # --------------------------------------------------------
    # Compute Ief_selected once based on checkbox state
    use_simplified_ief = st.session_state.get("defl_use_simplified_ief", True)
    try:
        if use_simplified_ief:
            Ief_selected, beta, p, p_lim, Ief_max, k1_from_ief = calc_ief_simplified(
                fc=fc,
                beff=beff,
                bw=bw,
                d=d,
                Ast=Ast,
            )
        else:
            Ief_selected = st.session_state.get("defl_Ief_user", 1.0e11)
            beta = effective_flange_width_ratio(beff, bw)
            p = tension_reinforcement_ratio(Ast, beff, d)
            p_lim = 0.0
            Ief_max = Ief_selected
            k1_from_ief = effective_stiffness_coefficient_k1(Ief_selected, beff, d)
    except Exception:
        Ief_selected = 1.0e11
        beta = effective_flange_width_ratio(beff, bw)
        p = tension_reinforcement_ratio(Ast, beff, d)
        p_lim = 0.0
        Ief_max = Ief_selected
        k1_from_ief = effective_stiffness_coefficient_k1(Ief_selected, beff, d)

    # --- hard guard: never let L_m be None (prevents session-killing exception) ---
    L_eff_m = get_param("defl_L_eff")

    if L_eff_m is None:
        L_eff_m = float(get_param("L")) / 1000.0

    if L_eff_m <= 0:
        L_eff_m = 0.1

    L_eff_m = float(L_eff_m) if L_eff_m is not None else None
    derived = _derive_equiv_udl_from_actions(
        M_kNm=M_used,
        V_kN=V_used,
        L_m=L_eff_m,
        support_type=support_type,
    )
    load_split = deflection_multispan_load_split_values(
        derived=derived,
        g_kNm=g,
        q_kNm=q,
    )
    w_used = load_split["w_used"]
    w_source = load_split["w_source"]
    g_used = load_split["g_used"]
    q_used = load_split["q_used"]

    compute_and_store_multispan_deflection_metrics(
        state=st.session_state,
        Ec=float(Ec),
        Ief=float(Ief_selected),
        g_kNm=float(g_used),
        q_kNm=float(q_used),
        psi_s=float(psi_s),
        defl_limit_ratio=float(defl_limit_ratio),
        Ast=float(Ast),
        Asc=float(Asc),
    )
    support_resolution = get_deflection_diagram_support_condition(st.session_state)
    support_type = support_resolution["support_type"]

    try:
        from src.debug.debug_flags import is_debug_enabled as _is_dbg_defl
    except Exception:
        def _is_dbg_defl():
            return False
    if _is_dbg_defl() and _is_design_multispan_mode(st.session_state):
        try:
            _n_dbg = int(float(st.session_state.get("sfd_span_count", 0) or 0))
        except Exception:
            _n_dbg = 0
        _lens_dbg = [
            float(st.session_state.get(f"sfd_span_len_{i}", 0) or 0)
            for i in range(1, max(0, _n_dbg) + 1)
        ]
        _g_dbg = [
            float(st.session_state.get(f"load_ms_g_{i}", 0) or 0)
            for i in range(1, max(0, _n_dbg) + 1)
        ]
        _q_dbg = [
            float(st.session_state.get(f"load_ms_q_{i}", 0) or 0)
            for i in range(1, max(0, _n_dbg) + 1)
        ]
        _sup_dbg = [
            "Continuous – end span"
            if _i in (0, max(0, _n_dbg - 1))
            else "Continuous – interior span"
            for _i in range(max(0, _n_dbg))
        ]
        with st.expander("Debug: multispan governing-span inputs (final)", expanded=True):
            st.write("**controlling_span_idx (0-based):**", support_resolution.get("controlling_span_idx"))
            st.write("**controlling_reason:**", support_resolution.get("controlling_reason"))
            st.write("**sfd_span_len_i (m):**", _lens_dbg)
            st.write("**load_ms_g_i (kN/m):**", _g_dbg)
            st.write("**load_ms_q_i (kN/m):**", _q_dbg)
            st.write("**defl_span_deflections_mm:**", st.session_state.get("defl_span_deflections_mm"))
            st.write("**defl_span_utilisations:**", st.session_state.get("defl_span_utilisations"))
            st.write("**per-span support class (metric loop):**", _sup_dbg)

    # Passive display only (no widget mutation): when support is design-governed,
    # show the governing support condition used by calculations and plots.
    if str(support_resolution.get("mode", "")).strip().lower() == "design":
        st.caption(f"Governing support condition (from Design/SFD): **{support_type}**")
    # Keep F_d,ef and downstream span/depth expressions aligned with the final
    # governing support_type selected after multispan metrics are refreshed.
    fd_ef_used, fd_ef_source_branch, value_source_text, fd_ef_meta = _derive_fd_ef(
        actions_source=actions_source,
        support_type_value=support_type,
        L_m_value=L_m_for_fd,
        V_manual_kN=V_manual_kN,
        V_design_kN=V_design_kN,
        fallback_value=fd_fallback,
    )
    Fdef_kNm = fd_ef_used

    results = calc_deflection_as3600(
        L_m=L_eff_m,
        Ec=Ec,
        Ief=Ief_selected,
        g_kNm=g_used,
        q_kNm=q_used,
        psi_s=psi_s,
        support_type=support_type,
        Ast=Ast,
        Asc=Asc,
    )

    if results is None or (
        isinstance(results, dict) and results.get("ok") is False
    ):
        error_msg = (
            results.get(
                "error",
                "Deflection calculation failed: invalid span length.",
            )
            if isinstance(results, dict)
            else "Deflection calculation failed: invalid span length."
        )
        st.warning(error_msg)
        return

    L_mm = results["L_mm"]
    delta_short_total = results["delta_short_total"]
    delta_short_sust = results["delta_short_sust"]
    delta_long_add = results["delta_long_add"]
    delta_total = results["delta_total"]
    kcs = results["kcs"]
    w_total = w_used  # Use computed w_used instead of g + q
    w_sust = results["w_sust"]
    k2 = results["k2"]

    # Deflected shape (rendered in slot above reinforcement; same computed values)
    with diagram_placeholder.container():
        inject_compact_side_view_spacing("deflection-side-view-compact")
        st.markdown("**Deflected shape**")
        st.caption("Illustrative — see figure title for vertical exaggeration")
        st.caption(
            f"Resolved support condition for governing span: {support_type}"
        )
        support_pair = _governing_span_support_pair(st.session_state, support_resolution)
        if support_resolution.get("multi_span"):
            _span_no = int(support_resolution.get("controlling_span_idx", 0)) + 1
            _reason = str(support_resolution.get("controlling_reason", "fallback") or "fallback")
            if _reason in ("highest deflection utilisation", "largest absolute deflection"):
                _basis = f"selected from calculated per-span deflection results ({_reason})"
            elif _reason == "longest active span":
                _basis = "selected by longest active span"
            else:
                _basis = "selected by fallback"
            st.caption(
                f"Governing span: Span {_span_no}, {_basis}. "
                f"The displayed support condition and sketch follow this governing span."
            )

        if delta_total is None:
            st.info("Provide inputs to view deflected shape.")
        else:
            x, y_long = deflected_longitudinal_profile_mm(
                L_mm, support_type, float(delta_total), n_pts=200
            )

            D_mm = float(D) if D is not None else 600.0
            beam_fig = build_deflected_beam_plotly(
                x_mm=x,
                w_mm=y_long,
                L_mm=L_mm,
                D_mm=D_mm,
                support_type=support_type,
                continuous_end_side=support_resolution.get("continuous_end_side"),
                support_pair=support_pair,
                reo_layers=_deflection_diagram_reo_layers(D_mm),
                height=COMPACT_SIDE_VIEW_HEIGHT_PX,
            )
            render_plotly_diagram(
                compact_side_view_figure(beam_fig),
                key="deflection_deflected_shape_diagram",
                title="Deflected shape",
                center=True,
                allow_fullscreen=True,
                preserve_figure_width=True,
                config={"displayModeBar": False},
            )
        page_divider()

    L_over_delta_short = format_L_over_delta(delta_short_total, L_mm)
    L_over_delta_long_add = format_L_over_delta(delta_long_add, L_mm)
    L_over_delta_total = format_L_over_delta(delta_total, L_mm)

    L_over_d = span_to_depth_ratio(L_mm, d)
    L_over_d_limit, k1_span, k2_span = calc_span_depth_limit(
        ief=Ief_selected,
        beff=beff,
        bw=bw,
        d=d,
        fc=fc,
        Ec=Ec,
        Fdef_kNm=Fdef_kNm,
        support_type=support_type,
        defl_limit_ratio=defl_limit_ratio,
    )

    # Closed-form deflection (with unit fix: convert L to mm, P to N)
    delta_max = None
    formula_latex = None
    delta_loc = None
    if (
        load_case is not None
        and L_sfd is not None
        and Ec is not None
        and Ief_selected is not None
        and L_sfd > 0
        and Ec > 0
        and Ief_selected > 0
    ):
        L_mm_sfd = float(L_sfd) * 1000.0
        w_eff_n_per_mm = w_eff if w_eff is not None else None
        P_sls_n = P_sls * 1000.0 if P_sls is not None else None
        E_mpa = float(Ec)
        I_mm4 = float(Ief_selected)

        delta_max, formula_latex, delta_loc = _deflection_from_sfd_case(
            case=load_case,
            L=L_mm_sfd,
            w_eff=w_eff_n_per_mm,
            P_sls=P_sls_n,
            E=E_mpa,
            I=I_mm4,
        )

    # --------------------------------------------------------
    render_timing_mark("deflection_page.runtime.summary_checks.start")
    # Summary + stacked calculation sections (Crack-style vertical flow)
    # --------------------------------------------------------
    with summary_placeholder.container():
        render_page_explainer_expander(_render_deflection_explainer)
        defl_pack = build_deflection_check_rows_from_state(st.session_state)
        ROWS = build_deflection_summary_rows(defl_pack.get("rows", []))
        update_results("deflection", {"rows": ROWS, "summary": defl_pack})
        render_clickable_summary_table(
            ROWS,
            key_prefix="defl_summary",
            columns=DEFLECTION_CHECK_SUMMARY_COLUMNS,
        )
        bind_summary_clicks()
        page_divider()

    use_simplified_ief_checkbox = v2_checkbox(
        label="Use simplified reinforced-member Iₑf (AS 3600 Cl. 8.5.3.1(2),(3))",
        key="defl_use_simplified_ief",
        default=use_simplified_ief,
        on_change=sync_callbacks["defl_use_simplified_ief"],
    )

    # Display-only: show the already computed Ief_selected
    if not use_simplified_ief_checkbox:
        Ief_user_display = v2_number_input(
            label="User-specified Iₑf (mm⁴)",
            key="defl_Ief_user",
            default=Ief_selected,
            step=1.0e10,
            format="%.3e",
            on_change=sync_callbacks["defl_Ief_user"],
        )

    # Build 2-line summary for Ief step
    ief_method = "Simplified" if use_simplified_ief_checkbox else "User input"
    # Guard against None values for formatting
    Ief_selected_display = Ief_selected if Ief_selected is not None else 1.0e11
    ief_summary = (
        f"**Check 1 — Effective stiffness $I_{{ef}}$**  \n"
        f"$I_{{ef}} = {Ief_selected_display:,.3e}\\,\\mathrm{{mm}}^4$  "
        f"({ief_method.lower()} reinforced-member option)"
    )

    # Guard against None values before formatting
    fc_display = fc if fc is not None else 32.0
    bw_display = bw if bw is not None else 300.0
    beff_display = beff if beff is not None else 300.0
    d_display = d if d is not None else 550.0
    Ast_display = Ast if Ast is not None else 2010.0
    beta_display = beta if beta is not None else 1.0
    p_display = p if p is not None else 0.0
    p_lim_display = p_lim if p_lim is not None else 0.0
    Ief_max_display = Ief_max if Ief_max is not None else 1.0e11
    k1_from_ief_display = k1_from_ief if k1_from_ief is not None else 0.0
    use_high_branch = p_display >= p_lim_display
    if use_high_branch:
        ief_branch_label = "p ≥ p_lim"
        k1_expr = simplified_ief_k1_factor(fc_display, beta_display, p_display, p_lim_display)
        k1_expr_md = (
            rf"(5 - 0.04\ \times\ {fc_display:.1f})\ \times\ "
            rf"{p_display:.5f} + 0.002"
        )
    else:
        ief_branch_label = "p < p_lim"
        k1_expr = simplified_ief_k1_factor(fc_display, beta_display, p_display, p_lim_display)
        k1_expr_md = (
            rf"0.055\ \times\ ({fc_display:.1f})^{{1/3}}/({beta_display:.3f})^{{2/3}} "
            rf"- 50\ \times\ {p_display:.5f}"
        )

    ief_calc_md = rf"""
*Purpose: Compute the effective second moment of area $I_{{ef}}$ for a reinforced concrete member using the simplified expressions in AS 3600:2018 Cl. 8.5.3.1(2) and (3). This cracked stiffness is then used in all deflection checks.*

**Inputs:**

- Concrete strength: $f'_c = {fc_display:.1f}\,\text{{MPa}}$
- Web / stem width (derived): $b_w = {bw_display:.1f}\,\text{{mm}}$
- Effective flange width (derived): $b_{{ef}} = {beff_display:.1f}\,\text{{mm}}$
- Effective depth (derived): $d = {d_display:.1f}\,\text{{mm}}$
- Tension steel area (derived): $A_{{st}} = {Ast_display:.1f}\,\text{{mm}}^2$

Derived section parameters:

- Width ratio:
  $$
  \beta = \dfrac{{b_{{ef}}}}{{b_w}} = \dfrac{{{beff_display:.1f}}}{{{bw_display:.1f}}} = {beta_display:.3f}
  $$
- Reinforcement ratio:
  $$
  p = \dfrac{{A_{{st}}}}{{b_{{ef}} d}} = \dfrac{{{Ast_display:.1f}}}{{{beff_display:.1f}\times {d_display:.1f}}} = {p_display:.5f}
  $$
- Limit ratio:
  $$
  p_{{lim}} = 0.001 \dfrac{{(f'_c)^{{1/3}}}}{{\beta^{{2/3}}}}
  = 0.001 \dfrac{{({fc_display:.1f})^{{1/3}}}}{{({beta_display:.3f})^{{2/3}}}}
  = {p_lim_display:.5f}
  $$

---

**Formula:**

For reinforced members (AS 3600:2018 Cl. 8.5.3.1):

If $p \ge p_{{lim}}$:

$$
I_{{ef}} = \left[(5 - 0.04 f'_c)\, p + 0.002 \right]\, b_{{ef}} d^3
$$

If $p < p_{{lim}}$:

$$
I_{{ef}} = \left[0.055 (f'_c)^{{1/3}} / \beta^{{2/3}} - 50 p \right]\, b_{{ef}} d^3
$$

Capped by:

$$
I_{{ef}} \le I_{{ef,max}} = {Ief_max_display:,.3e}\,\text{{mm}}^4
$$

and

$$
k_1 = \dfrac{{I_{{ef}}}}{{b_{{ef}} d^3}}
$$

---

**Substitution:**

Using the current inputs:

- Branch used: {ief_branch_label}
- Coefficient:
  $$
  k_1 = {k1_expr_md} = {k1_expr:.5f}
  $$
- Effective stiffness:
  $$
  I_{{ef}} = k_1\, b_{{ef}} d^3 = {k1_expr:.5f}\times {beff_display:.1f}\times ({d_display:.1f})^3
  \approx {Ief_selected_display:,.3e}\,\text{{mm}}^4
  $$
- Cap check:
  $$
  I_{{ef}} \le I_{{ef,max}} = {Ief_max_display:,.3e}\,\text{{mm}}^4
  $$

---

**Result:**

- $I_{{ef}} = {Ief_selected:,.3e}\,\text{{mm}}^4$
- $k_1 = {k1_from_ief:.5f}$
- (cap) $I_{{ef,max}} = {Ief_max:,.3e}\,\text{{mm}}^4$

_Ref: AS 3600:2018 Cl. 8.5.3.1(2) & (3) – simplified $I_{{ef}}$ for reinforced members._
"""

    render_expandable_step(
        page_key="deflection",
        step_id="defl_ief",
        title="Effective stiffness ($I_{ef}$) – input choice",
        summary_md=ief_summary,
        status_kind=None,
        calc_md=ief_calc_md,
        diagram_render_fn=None,
        info_render_fn=None,
    )

    # Short-term deflection step
    short_limit_check = deflection_limit_check_values(
        delta_short_total,
        L_mm,
        defl_limit_ratio,
    )
    limit_delta_mm = short_limit_check["limit_delta_mm"]
    util_short = short_limit_check["utilisation"]
    short_status = short_limit_check["status"]

    _short_res = short_limit_check["result_text"]
    short_summary = (
        f"**Check 2 — Short-term deflection**  \n"
        f"$\\delta_{{st,total}} = {delta_short_total:.2f}\\,\\mathrm{{mm}}$ "
        f"({L_over_delta_short}) | Result: {_short_res}"
    )

    # Determine source label for display
    source_label = "Teaching SFD/BMD page" if is_design_driven else "Manual design actions"
    w_from_M = derived.get("w_from_M") if isinstance(derived, dict) else None
    w_from_V = derived.get("w_from_V") if isinstance(derived, dict) else None
    if w_source == "actions" and derived.get("w_kN_per_m") is not None:
        wM_str = f"{w_from_M:.2f}" if w_from_M is not None else "—"
        wV_str = f"{w_from_V:.2f}" if w_from_V is not None else "—"
        load_line = (
            f"- Total service load: $w = {w_total:.2f}\\,\\text{{kN/m}}$ "
            f"(from actions; $w_M={wM_str}$, $w_V={wV_str}$)"
        )
    else:
        load_line = (
            f"- Total service load: $w = g + q = {w_total:.2f}\\,\\text{{kN/m}}$"
        )

    short_calc_md = rf"""
*Purpose: Determine the short-term midspan deflection under total service load $w$ using the effective stiffness $I_{{ef}}$ from the Iₑf step (AS 3600 Cl. 8.5.3.1).*

**Inputs:**

- Actions source: {source_label}
- Effective span (derived):
  $$
  L_{{eff}} = \dfrac{{L}}{{1000}} = {L_mm / 1000.0:.3f}\,\text{{m}} = {L_mm:.0f}\,\text{{mm}}
  $$
{load_line}
- Support condition: {support_type}
- Deflection coefficient (support condition):  
  $k_2 = {k2:.5f}$  
  *(Code-defined coefficient based on support condition per AS 3600 Cl. 8.5.3.1)*
- Concrete modulus (derived): $E_c = 4700\sqrt{{f'_c}} = {Ec_short:.0f}\,\text{{MPa}}$
- Effective modulus (derived): $E_{{c,eff}} = \dfrac{{E_c}}{{1+\varphi_{{cc}}(t)}} = {Ec:.0f}\,\text{{MPa}}$
- Effective second moment: $I_{{ef}} = {Ief_selected:,.3e}\,\text{{mm}}^4$

---

**Formula:**

Short-term deflection due to total service load:

$$
\delta_{{st,total}} = k_2 \dfrac{{w\, L_{{eff}}^4}}{{E_{{c,eff}}\, I_{{ef}}}}
$$

where $k_2$ is the deflection coefficient determined by support condition (AS 3600 Cl. 8.5.3.1).

---

**Substitution:**

$$
\delta_{{st,total}}
= ({k2:.5f}) \times ({w_total:.2f})\,
  \dfrac{{({L_mm:.0f})^4}}{{({Ec:.0f}) \times ({Ief_selected:,.3e})}}
\approx {delta_short_total:.2f}\,\text{{mm}}
$$

---

**Result:**

- Short-term deflection (total load):  
  $\delta_{{st,total}} \approx {delta_short_total:.2f}\,\text{{mm}}$
- Deflection ratio:  
  $L/\delta_{{st,total}} \approx {L_over_delta_short}$
{f'- Utilisation: {util_short:.2f} → {"✓ PASS" if short_status == "pass" else "✗ FAIL"}' if util_short is not None else ''}

_Ref: AS 3600:2018 Cl. 8.5.3.1 – deflection using effective stiffness $I_{{ef}}$._
"""
    render_expandable_step(
        page_key="deflection",
        step_id="defl_short",
        title="Short-term deflection",
        summary_md=short_summary,
        status_kind=short_status,
        calc_md=short_calc_md,
        diagram_render_fn=None,
        info_render_fn=None,
    )

    long_add_limit_check = deflection_limit_check_values(
        delta_long_add,
        L_mm,
        defl_limit_ratio,
    )
    total_limit_check = deflection_limit_check_values(
        delta_total,
        L_mm,
        defl_limit_ratio,
    )
    limit_delta_mm = total_limit_check["limit_delta_mm"]
    util_long = long_add_limit_check["utilisation"]
    util_total = total_limit_check["utilisation"]
    long_status = total_limit_check["status"]

    limit_delta_mm_display = total_limit_check["limit_delta_mm_display"]
    util_total_display = total_limit_check["utilisation_display"]

    ratio_Asc_Ast = compression_to_tension_steel_ratio(Asc, Ast)

    _long_res = total_limit_check["result_text"]
    long_summary = (
        f"**Check 3 — Long-term deflection**  \n"
        f"$\\delta_{{total}} = {delta_total:.2f}\\,\\mathrm{{mm}}$ "
        f"({L_over_delta_total}) | Includes: Long-term deflection with "
        f"$k_{{cs}}$; Result: {_long_res}"
    )

    source_label = "Teaching SFD/BMD page" if is_design_driven else "Manual design actions"

    long_calc_md = rf"""
*Purpose: Determine the additional long-term deflection due to sustained loading (creep + shrinkage) and the resulting total deflection to AS 3600 Cl. 8.5.3.2.*

**Inputs:**

- Actions source: {source_label}
- Effective span (derived):
  $$
  L_{{eff}} = \dfrac{{L}}{{1000}} = {L_mm / 1000.0:.3f}\,\text{{m}} = {L_mm:.0f}\,\text{{mm}}
  $$
- Support condition: {support_type}
- Sustained load:
  $$
  w_{{sust}} = g + \psi_s q = {g_used:.2f} + {psi_s:.2f}\times {q_used:.2f} = {w_sust:.2f}\,\text{{kN/m}}
  $$
- Sustained factor: $\psi_s = {psi_s:.2f}$
- Tension steel: $A_{{st}} = {Ast:.0f}\,\text{{mm}}^2$
- Compression steel: $A_{{sc}} = {Asc:.0f}\,\text{{mm}}^2$
- Steel ratio:
  $$
  \dfrac{{A_{{sc}}}}{{A_{{st}}}} = \dfrac{{{Asc:.0f}}}{{{Ast:.0f}}} = {ratio_Asc_Ast:.3f}
  $$
- Creep/shrinkage multiplier:
  $$
  k_{{cs}} = \max\left[ 2 - 1.2 \left(\dfrac{{A_{{sc}}}}{{A_{{st}}}}\right),\, 0.8 \right]
  = \max\left[ 2 - 1.2 \times {ratio_Asc_Ast:.3f},\, 0.8 \right] = {kcs:.2f}
  $$
- Sustained concrete stress path (from creep workflow):
  $$
  \sigma_{{cs}} = \dfrac{{M_{{sust}}\times10^6}}{{Z_{{comp}}}}
  = \dfrac{{{sustained_mstar:.2f}\times10^6}}{{{sustained_z_comp:.2e}}}
  \approx {sustained_sigma_cs:.2f}\,\text{{MPa}}
  $$
  $$
  \text{{stress\_ratio}} = \dfrac{{\sigma_{{cs}}}}{{f'_c}}
  = \dfrac{{{sustained_sigma_cs:.2f}}}{{{fc:.1f}}}
  = {stress_ratio:.3f}
  $$
- Effective modulus path used in deflection:
  $$
  E_{{c,eff}} = \dfrac{{E_c}}{{1+\phi_{{cc}}(t)}}
  = \dfrac{{{Ec_short:.0f}}}{{1+{phi_cc_t:.2f}}}
  = {Ec:.0f}\,\text{{MPa}}
  $$
- Other parameters as per short-term:
  $k_2 = {k2:.5f},\ L_{{eff}} = {L_mm:.0f}\,\text{{mm}},\
   I_{{ef}} = {Ief_selected:,.3e}\,\text{{mm}}^4$

---

**Formula:**

Short-term deflection due to **sustained load only**:

$$
\delta_{{st,sust}} = k_2 \dfrac{{w_{{sust}} L_{{eff}}^4}}{{E_{{c,eff}} I_{{ef}}}}
$$

Creep/shrinkage multiplier:

$$
k_{{cs}} = \max\left[ 2 - 1.2 \left(\dfrac{{A_{{sc}}}}{{A_{{st}}}}\right),\, 0.8 \right]
$$

Additional long-term deflection:

$$
\delta_{{LT,add}} = k_{{cs}} \,\delta_{{st,sust}}
$$

Total deflection:

$$
\delta_{{total}} = \delta_{{st,total}} + \delta_{{LT,add}}
$$

Adopted limit ratio: **{defl_limit_label}**

Deflection limit:

$$
\delta_{{limit}} = \dfrac{{L_{{eff}}}}{{(L/\Delta)}} = \dfrac{{{L_mm:.0f}}}{{{defl_limit_ratio:.0f}}}
$$

---

**Substitution:**

Short-term sustained:

$$
\delta_{{st,sust}}
= ({k2:.5f}) \times ({w_sust:.2f})\,
  \dfrac{{({L_mm:.0f})^4}}{{({Ec:.0f}) \times ({Ief_selected:,.3e})}}
\approx {delta_short_sust:.2f}\,\text{{mm}}
$$

Additional long-term:

$$
\delta_{{LT,add}} = k_{{cs}} \,\delta_{{st,sust}}
= ({kcs:.2f}) \times ({delta_short_sust:.2f})
\approx {delta_long_add:.2f}\,\text{{mm}}
$$

Total:

$$
\delta_{{total}} = \delta_{{st,total}} + \delta_{{LT,add}}
= {delta_short_total:.2f} + {delta_long_add:.2f}
\approx {delta_total:.2f}\,\text{{mm}}
$$

Adopted limit ratio: **{defl_limit_label}**

Deflection limit and utilisation:

$$
\delta_{{limit}} = \dfrac{{L_{{eff}}}}{{(L/\Delta)}} = \dfrac{{{L_mm:.0f}}}{{{defl_limit_ratio:.0f}}}
 = {limit_delta_mm_display:.2f}\,\text{{mm}}
$$

$$
\text{{Utilisation}} = \dfrac{{\delta_{{total}}}}{{\delta_{{limit}}}}
 = \dfrac{{{delta_total:.2f}}}{{{limit_delta_mm_display:.2f}}} = {util_total_display:.2f}
$$

---

**Result:**

- Short-term sustained:  
  $\delta_{{st,sust}} \approx {delta_short_sust:.2f}\,\text{{mm}}$
- Additional long-term:  
  $\delta_{{LT,add}} \approx {delta_long_add:.2f}\,\text{{mm}}$  
  (ratio $\approx {L_over_delta_long_add}$)
- Total deflection:  
  $\delta_{{total}} \approx {delta_total:.2f}\,\text{{mm}}$  
  (ratio $\approx {L_over_delta_total}$)
{f'- Utilisation: {util_total:.2f} → {"✓ PASS" if long_status == "pass" else "✗ FAIL"}' if util_total is not None else ''}

_Ref: AS 3600:2018 Cl. 8.5.3.2 – long-term deflection using $k_{{cs}}$ and sustained loads._
"""

    render_expandable_step(
        page_key="deflection",
        step_id="defl_long",
        title="Long-term deflection",
        summary_md=long_summary,
        status_kind=long_status,
        calc_md=long_calc_md,
        diagram_render_fn=None,
        info_render_fn=None,
    )

    L_m = L_m_for_fd
    if L_m is None or L_m <= 0:
        L_m = float(get_param("span_L_m", 0.0) or 0.0)

    support_type_display = support_type

    value_source = value_source_text
    fd_ef_meta_used = fd_ef_meta or {}

    # Determine loading condition description
    if fd_ef_source_branch in ("manual_actions", "design_actions"):
        if support_type == "Simply supported":
            loading_condition = "Simply supported, UDL over full span"
        elif support_type == "Cantilever":
            loading_condition = "Cantilever, UDL over full span"
        else:
            loading_condition = f"{support_type}, UDL over full span"
    else:
        loading_condition = "Fallback value"

    # Build summary
    fd_ef_summary = (
        f"**Check 4 — Effective design load F_d,ef**  \n"
        f"$F_{{d,ef}} = {fd_ef_used:.2f}\\,\\mathrm{{kN/m}}$ | "
        f"Source: {value_source}"
    )

    if (
        fd_ef_source_branch in ("manual_actions", "design_actions")
        and fd_ef_meta_used.get("V_kN", 0.0) > 0
        and L_m > 0
    ):
        V_kN = fd_ef_meta_used.get("V_kN", 0.0)
        if support_type == "Simply supported":
            equation_latex = r"V_{\max} = \frac{wL}{2} \quad \Rightarrow \quad w = \frac{2V_{\max}}{L}"
            substitution_latex = (
                rf"F_{{d,ef}} = \frac{{2 \times {V_kN:.1f}}}{{{L_m:.2f}}} = "
                rf"{fd_ef_used:.2f}\,\text{{kN/m}}"
            )
        elif support_type == "Cantilever":
            equation_latex = r"V_{\max} = wL \quad \Rightarrow \quad w = \frac{V_{\max}}{L}"
            substitution_latex = (
                rf"F_{{d,ef}} = \frac{{{V_kN:.1f}}}{{{L_m:.2f}}} = "
                rf"{fd_ef_used:.2f}\,\text{{kN/m}}"
            )
        else:
            equation_latex = r"w = \frac{V_{\max}}{L} \quad \text{(approximate)}"
            substitution_latex = (
                rf"F_{{d,ef}} = \frac{{{V_kN:.1f}}}{{{L_m:.2f}}} = "
                rf"{fd_ef_used:.2f}\,\text{{kN/m}}"
            )

        source_label = (
            "Manual inputs"
            if fd_ef_source_branch == "manual_actions"
            else "Teaching SFD/BMD"
        )

        fd_ef_calc_md = rf"""
*Purpose: Determine the equivalent uniform distributed load $F_{{d,ef}}$ used for span-to-depth ratio checks per AS 3600 Cl. 8.5.4. This value is reverse-engineered from the design shear force $V^*$ and span length $L$ based on the support condition and loading pattern.*

**Step 1 – Inputs:**

- Source: {source_label}
- Design shear: $V^* = {V_kN:.1f}\,\text{{kN}}$
- Effective span: $L = {L_m:.2f}\,\text{{m}}$
- Support condition: {support_type_display}
- Loading condition: {loading_condition}

---

**Step 2 – Model / equations:**

For {loading_condition}:

$$
{equation_latex}
$$

---

**Step 3 – Substitution:**

$$
{substitution_latex}
$$

---

**Step 4 – Result:**

- Effective design load:
  $F_{{d,ef}} = {fd_ef_used:.2f}\,\text{{kN/m}}$

*Note: This equivalent UDL is used for serviceability deflection checks and span-to-depth ratio calculations per AS 3600 Cl. 8.5.4.*

_Ref: AS 3600:2018 Cl. 8.5.4 – deemed-to-conform span-to-depth limits.*
"""
    else:
        fd_ef_calc_md = rf"""
*Purpose: The effective design load $F_{{d,ef}}$ is used for span-to-depth ratio checks per AS 3600 Cl. 8.5.4. This value represents an equivalent uniform distributed load used in serviceability calculations.*

**Step 1 – Inputs:**

- Effective design load: $F_{{d,ef}} = {fd_ef_used:.2f}\,\text{{kN/m}}$
- Effective span: $L = {L_m:.2f}\,\text{{m}}$
- Support condition: {support_type_display}
- Source: {value_source}

---

**Step 2 – Model / equations:**

Derivation inputs were unavailable; using the stored fallback value.

---

**Step 3 – Substitution:**

$$
F_{{d,ef}} = {fd_ef_used:.2f}\,\text{{kN/m}}
$$

---

**Step 4 – Result:**

- Effective design load:
  $F_{{d,ef}} = {fd_ef_used:.2f}\,\text{{kN/m}}$

*Note: This value is used for span-to-depth ratio calculations per AS 3600 Cl. 8.5.4.*

_Ref: AS 3600:2018 Cl. 8.5.4 – deemed-to-conform span-to-depth limits._
"""

    render_expandable_step(
        page_key="deflection",
        step_id="defl_effective_load",
        title="Effective design load F_d,ef",
        summary_md=fd_ef_summary,
        status_kind=None,
        calc_md=fd_ef_calc_md,
        diagram_render_fn=None,
        info_render_fn=None,
    )

    span_depth_display = span_depth_display_values(L_over_d, L_over_d_limit)
    util_span = span_depth_display["util_span"]
    span_defl_status = span_depth_display["span_defl_status"]
    limit_text = span_depth_display["limit_text"]

    # Guard against None values before formatting
    L_mm_display = L_mm if L_mm is not None else 6000.0
    d_display_span = d if d is not None else 550.0
    L_over_d_display = L_over_d if L_over_d is not None else 0.0
    k1_span_display = k1_span if k1_span is not None else 0.0
    k2_span_display = k2_span if k2_span is not None else 0.013
    defl_limit_ratio_display = defl_limit_ratio if defl_limit_ratio is not None else 250.0
    Fdef_kNm_display = Fdef_kNm if Fdef_kNm is not None else 12.0
    Ec_display_span = Ec if Ec is not None else 10000.0
    beff_display_span = beff if beff is not None else 300.0
    value_source_text_display = (
        value_source_text or "See Effective design load section above."
    )

    _span_res = span_depth_display["result_text"]
    span_summary = (
        f"**Check 5 — Span/depth deemed-to-conform check**  \n"
        f"$L_{{ef}}/d = {L_over_d_display:.1f}$ vs limit = {limit_text} | "
        f"Result: {_span_res}"
    )

    span_calc_md = rf"""
*Purpose: Check whether the span-to-depth ratio $L_{{ef}}/d$ satisfies the deemed-to-conform limit given in AS 3600:2018 Cl. 8.5.4, using the previously calculated $I_{{ef}}$ (via $k_1$).*

**Inputs:**

- Effective span (derived):
  $$
  L_{{eff}} = \dfrac{{L}}{{1000}} = {L_mm_display / 1000.0:.3f}\,\text{{m}} = {L_mm_display:.0f}\,\text{{mm}}
  $$
- Effective depth (derived): $d = {d_display_span:.1f}\,\text{{mm}}$
  ⇒ current ratio:
  $$
  \dfrac{{L_{{ef}}}}{{d}} = {L_over_d_display:.1f}
  $$
- Support condition: {support_type}
- Stiffness factor from Iₑf step: $k_1 = {k1_span_display:.5f}$
- Deflection constant (support type): $k_2 = {k2_span_display:.5f}$
- Deflection limit (adopted: {defl_limit_label}):
  $$
  \left(\dfrac{{\Delta}}{{L_{{ef}}}}\right)_{{limit}} = \dfrac{{1}}{{{defl_limit_ratio_display:.0f}}}
  $$
- Effective design load (derived for span/depth): $F_{{d,ef}} = {Fdef_kNm_display:.2f}\,\text{{kN/m}}$
  *{value_source_text_display}*
- Concrete modulus (derived): $E_c = 4700\sqrt{{f'_c}} = {Ec_short:.0f}\,\text{{MPa}}$
- Effective modulus (derived): $E_{{c,eff}} = \dfrac{{E_c}}{{1+\varphi_{{cc}}(t)}} = {Ec_display_span:.0f}\,\text{{MPa}}$
- Effective flange width: $b_{{ef}} = {beff_display_span:.1f}\,\text{{mm}}$

---

**Formula:**

Deemed-to-conform span-to-depth limit:

$$
\frac{{L_{{ef}}}}{{d}} \le
\left[
\dfrac{{k_1 \, (\Delta/L_{{ef}}) \, b_{{ef}} E_{{c,eff}}}}{{k_2 F_{{d,ef}}}}
\right]^{{1/3}}
$$

---

**Substitution:**
"""
    if L_over_d_limit is not None:
        span_calc_md += rf"""

Right-hand-side limit:

$$
\left(\frac{{L_{{ef}}}}{{d}}\right)_{{limit}}
=
\left[
\dfrac{{({k1_span_display:.5f}) \times (1/{defl_limit_ratio_display:.0f}) \times ({beff_display_span:.1f}) \times ({Ec_display_span:.0f})}}
      {{({k2_span_display:.5f}) \times ({Fdef_kNm_display:.2f})}}
\right]^{{1/3}}
\approx {L_over_d_limit:.1f}
$$

---

**Result:**

- Allowed ratio:
  $$
  \dfrac{{L_{{ef}}}}{{d}} \le {L_over_d_limit:.1f}
  $$
- Actual ratio:
  $$
  \dfrac{{L_{{ef}}}}{{d}} = {L_over_d:.1f}
  $$

Conclusion: **{"✅ OK – deemed to conform" if span_defl_status == "pass" else "❌ NG – exceeds deemed limit"}**
"""
    else:
        span_calc_md += r"""

No limit could be computed because $F_{d,ef} \le 0$.

---

**Result:**

- Span/depth deemed-to-conform check not applicable for the current inputs.
"""

    span_calc_md += r"""

_Ref: AS 3600:2018 Cl. 8.5.4 – deemed-to-conform span-to-depth limits._
"""

    render_expandable_step(
        page_key="deflection",
        step_id="defl_span_depth",
        title="Span/depth deemed-to-conform check",
        summary_md=span_summary,
        status_kind=span_defl_status,
        calc_md=span_calc_md,
        diagram_render_fn=None,
        info_render_fn=None,
    )

    
    # Handle scroll after all content is rendered (for cross-page navigation from Inputs)
    from jump_nav import scroll_to_jump_after_render
    scroll_to_jump_after_render()
