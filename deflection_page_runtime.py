# deflection_page.py
import math
import streamlit as st

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
    apply_result_page_css,
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
    render_plotly_diagram,
    COMPACT_SIDE_VIEW_HEIGHT_PX,
    compact_side_view_figure,
    inject_compact_side_view_spacing,
)
from engineering_page_sections.page_reference_sidebar import (
    build_deflection_reference,
    render_page_reference_sidebar,
)
from step_ui import init_step_ui_state
from ui.summary_rows import build_deflection_summary_rows
from deflection_checks_helpers import build_deflection_check_rows_from_state
from engineering_page_sections.compact_check_inputs import (
    CheckInputCategory,
    CheckInputPanelConfig,
    InputSource,
    compact_check_input_columns,
    format_dimensions,
    format_number,
    join_summary,
)
from inputs_application.action_source_control import uses_load_analysis_actions
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

    active_beam_id = str(st.session_state.get("active_beam_id") or "").strip()
    revision = int(
        InputsSessionServices.from_mapping(st.session_state)
        .input_snapshots.current_for_beam(active_beam_id)
        .revision
        or 0
    )
    return revision, tuple(values)


# Extracted section owners; the runtime below retains ordered page composition only.
from engineering_page_sections import deflection_support as _deflection_support_section
from engineering_page_sections import deflection_inputs as _deflection_inputs_section
from engineering_page_sections.deflection_checks import (
    render_deflection_checks,
)
from engineering_page_sections.deflection_checks_context import (
    build_deflection_checks_snapshot,
)
from engineering_page_sections.deflection_diagrams import (
    deflection_diagram_reo_layers,
)
from engineering_page_sections.deflection_page_context import (
    build_deflection_diagram_snapshot,
    build_deflection_page_snapshot,
)
from engineering_page_sections.deflection_summary import render_deflection_summary
from engineering_page_sections.deflection_visualisation import (
    render_deflection_diagram,
)

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

    apply_result_page_css()
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


    with page_title_placeholder.container():
        render_result_page_title("Beam Deflection")

    # Render the current authoritative summary first.  The application
    # boundary has already refreshed this publication, so delaying it until
    # after diagrams and local calculations only makes the page feel slower.
    render_timing_mark("deflection_page.runtime.summary_checks.start")
    defl_pack = build_deflection_check_rows_from_state(st.session_state)
    rows = build_deflection_summary_rows(defl_pack.get("rows", []))
    page_snapshot = build_deflection_page_snapshot(
        summary_pack=defl_pack,
        summary_rows=rows,
    )
    render_deflection_summary(
        page_snapshot,
        publish_results=lambda values: update_results("deflection", values),
    )
    page_divider()
    render_timing_mark("deflection_page.runtime.summary_checks.end")

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

    _defl_b_summary = get_param("b", None)
    _defl_D_summary = get_param("D", None)
    _defl_L_summary = get_param("L", None)
    _defl_fc_summary = get_param("fc", None)
    _defl_ec_summary = get_param("Ec", None)
    _defl_sls_m_summary = get_param("sls_Mstar", get_param("Ms", None))
    _defl_sls_v_summary = get_param("sls_Vstar", None)
    _defl_bot_count = get_param("nb_or_s_bot_1", get_param("nb_bot", None))
    _defl_bot_dia = get_param("db_bot_1", get_param("db_bot", None))
    _defl_top_count = get_param("nb_or_s_top_1", get_param("nb_top", None))
    _defl_top_dia = get_param("db_top_1", get_param("db_top", None))

    def _deflection_reference_row_projection() -> dict[str, object]:
        """Project the active row editor values without creating new state."""

        projected: dict[str, object] = {}
        for face in ("bot", "top"):
            row_count_key = f"{face}_row_count"
            projected[row_count_key] = get_param(
                row_count_key,
                st.session_state.get(f"defl_{row_count_key}", 1),
            )
            for row in range(1, 5):
                for field in ("mode", "bars", "spacing", "dia"):
                    key = f"{face}_row_{row}_{field}"
                    projected[key] = get_param(
                        key,
                        st.session_state.get(f"defl_{key}"),
                    )
        return projected

    col_geom, col_mats, col_loads, col_reo_bot, col_reo_top = compact_check_input_columns(
        st,
        CheckInputPanelConfig(
            page_slug="deflection",
            mount_closed_bodies=True,
            categories=(
                CheckInputCategory(
                    "section_geometry",
                    "Section & geometry",
                    join_summary(
                        format_dimensions(_defl_b_summary, _defl_D_summary),
                        f"L {format_number(_defl_L_summary, 'mm')}",
                    ),
                    lambda: None,
                    icon="▣",
                ),
                CheckInputCategory(
                    "material_long_term",
                    "Material & long-term properties",
                    join_summary(
                        f"f'c {format_number(_defl_fc_summary, 'MPa')}",
                        f"Ec {format_number(_defl_ec_summary, 'MPa')}",
                    ),
                    lambda: None,
                    icon="◇",
                ),
                CheckInputCategory(
                    "serviceability_actions",
                    "Serviceability actions & limits",
                    join_summary(
                        f"M_s {format_number(_defl_sls_m_summary, 'kNm', decimals=1)}",
                        f"V_s {format_number(_defl_sls_v_summary, 'kN', decimals=1)}",
                    ),
                    lambda: None,
                    source=(
                        InputSource.LOAD_ANALYSIS
                        if uses_load_analysis_actions(st.session_state)
                        else InputSource.BEAM_INPUTS
                    ),
                    icon="↧",
                ),
                CheckInputCategory(
                    "bottom_reinforcement",
                    "Bottom reinforcement",
                    (
                        "Not provided"
                        if _defl_bot_count is None or _defl_bot_dia is None
                        else f"{float(_defl_bot_count):.0f}-N{float(_defl_bot_dia):.0f}"
                    ),
                    lambda: None,
                    icon="●",
                ),
                CheckInputCategory(
                    "top_reinforcement",
                    "Top reinforcement",
                    (
                        "Not provided"
                        if _defl_top_count is None or _defl_top_dia is None
                        else f"{float(_defl_top_count):.0f}-N{float(_defl_top_dia):.0f}"
                    ),
                    lambda: None,
                    icon="●",
                ),
            ),
        ),
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
    # The application result-page boundary refreshes Deflection authoritatively
    # before this renderer is entered.  If that publication is present, reuse
    # it rather than rebuilding the same report because this page-local cache
    # has not yet been seeded in a fresh browser session.  The fallback remains
    # for isolated/defensive renderer use where no authoritative publication
    # exists.
    if not _deflection_params_present or not _deflection_report_present:
        compute_deflection_results(publish=True)
    st.session_state["_deflection_core_cache_key"] = _deflection_cache_key
    render_timing_mark("deflection_page.runtime.compute.publication.end")

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
    render_timing_mark("deflection_page.runtime.compute.multispan.end")
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
    render_timing_mark("deflection_page.runtime.compute.as3600.end")

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
        render_page_reference_sidebar(
            build_deflection_reference(
                {
                    "b": b,
                    "D": D,
                    "L": L,
                    "sec_shape": get_param("sec_shape", "RECT"),
                    "bf": get_param("bf", None),
                    "tf": get_param("tf", None),
                    "fc": fc,
                    "Ec": Ec,
                    "Ec_short": Ec_short,
                    "Eceff": Ec,
                    "Es": get_param("Es", None),
                    "d": d,
                    "bw": bw,
                    "beff": beff,
                    "Ast": Ast,
                    "Asc": Asc,
                    "nb_or_s_bot_1": _defl_bot_count,
                    "db_bot_1": _defl_bot_dia,
                    "nb_or_s_top_1": _defl_top_count,
                    "db_top_1": _defl_top_dia,
                    "rowgap_bot": rowgap_bot_val,
                    "rowgap_top": rowgap_top_val,
                    "defl_support_type": support_type,
                    "defl_limit_ratio": defl_limit_ratio,
                    "defl_Fdef": Fdef_kNm,
                    "defl_use_simplified_ief": use_simplified_ief,
                    "defl_Ief_user": st.session_state.get("defl_Ief_user"),
                    "sls_Mstar": M_used,
                    "sls_Vstar": V_used,
                    "load_case": load_case,
                    "beam_system_mode": st.session_state.get(
                        "sfd_beam_system_mode",
                        get_param("beam_system_mode", None),
                    ),
                    "span_L_m": L_sfd,
                    "w_sls_kNm_per_m": w_sls,
                    "P_sls_kN": P_sls,
                    "a_m": a,
                    "actions_source": actions_source,
                    "g_udl_kNm_per_m": g,
                    "q_udl_kNm_per_m": q,
                    "psi_udl": psi_s,
                    "G_point_kN": G_point,
                    "Q_point_kN": Q_point,
                    "psi_point": get_param("psi_point", psi_s),
                    **_deflection_reference_row_projection(),
                    "defl_L_eff": L_eff_m,
                    "phi_cc_t": phi_cc_t,
                    "stress_ratio": stress_ratio,
                    "sustained_Mstar_kNm": sustained_mstar,
                    "sustained_sigma_cs_mpa": sustained_sigma_cs,
                    "reference_source": (
                        "Load Analysis" if is_design_driven else "Beam Inputs"
                    ),
                }
            )
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
    render_timing_mark("deflection_page.runtime.diagram.start")
    with diagram_placeholder.container():
        support_pair = _governing_span_support_pair(
            st.session_state, support_resolution
        )
        diagram_snapshot = build_deflection_diagram_snapshot(
            span_mm=L_mm,
            depth_mm=float(D) if D is not None else 600.0,
            total_deflection_mm=delta_total,
            support_type=support_type,
            continuous_end_side=support_resolution.get("continuous_end_side"),
            support_pair=support_pair,
            support_resolution=support_resolution,
            reo_layers=deflection_diagram_reo_layers(
                float(D) if D is not None else 600.0,
                state=st.session_state,
                get_parameter=get_param,
            ),
        )
        render_deflection_diagram(st, diagram_snapshot)
    render_timing_mark("deflection_page.runtime.diagram.end")

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
    render_timing_mark("deflection_page.runtime.post_diagram_compute.end")

    # --------------------------------------------------------
    checks_snapshot = build_deflection_checks_snapshot(
        {
            "Asc": Asc,
            "Ast": Ast,
            "Ec": Ec,
            "Ec_short": Ec_short,
            "Fdef_kNm": Fdef_kNm,
            "Ief_max": Ief_max,
            "Ief_selected": Ief_selected,
            "L_m_for_fd": L_m_for_fd,
            "L_mm": L_mm,
            "L_over_d": L_over_d,
            "L_over_d_limit": L_over_d_limit,
            "L_over_delta_long_add": L_over_delta_long_add,
            "L_over_delta_short": L_over_delta_short,
            "L_over_delta_total": L_over_delta_total,
            "beff": beff,
            "beta": beta,
            "bw": bw,
            "d": d,
            "defl_limit_label": defl_limit_label,
            "defl_limit_ratio": defl_limit_ratio,
            "delta_long_add": delta_long_add,
            "delta_short_sust": delta_short_sust,
            "delta_short_total": delta_short_total,
            "delta_total": delta_total,
            "derived": derived if isinstance(derived, dict) else {},
            "fc": fc,
            "fd_ef_meta": fd_ef_meta or {},
            "fd_ef_source_branch": fd_ef_source_branch,
            "fd_ef_used": fd_ef_used,
            "g_used": g_used,
            "is_design_driven": is_design_driven,
            "k1_from_ief": k1_from_ief,
            "k1_span": k1_span,
            "k2": k2,
            "k2_span": k2_span,
            "kcs": kcs,
            "p": p,
            "p_lim": p_lim,
            "phi_cc_t": phi_cc_t,
            "psi_s": psi_s,
            "q_used": q_used,
            "stress_ratio": stress_ratio,
            "support_type": support_type,
            "sustained_mstar": sustained_mstar,
            "sustained_sigma_cs": sustained_sigma_cs,
            "sustained_z_comp": sustained_z_comp,
            "use_simplified_ief": use_simplified_ief,
            "value_source_text": value_source_text,
            "w_source": w_source,
            "w_sust": w_sust,
            "w_total": w_total,
        }
    )
    deflection_reference_values = dict(checks_snapshot.values)
    deflection_reference_values.update(
        {
            "b": b,
            "D": D,
            "L": L,
            "sec_shape": get_param("sec_shape", "RECT"),
            "bf": get_param("bf", None),
            "tf": get_param("tf", None),
            "fc": fc,
            "Ec": Ec,
            "Ec_short": Ec_short,
            "Eceff": Ec,
            "Es": get_param("Es", None),
            "d": d,
            "bw": bw,
            "beff": beff,
            "Ast": Ast,
            "Asc": Asc,
            "nb_or_s_bot_1": _defl_bot_count,
            "db_bot_1": _defl_bot_dia,
            "nb_or_s_top_1": _defl_top_count,
            "db_top_1": _defl_top_dia,
            "rowgap_bot": rowgap_bot_val,
            "rowgap_top": rowgap_top_val,
            "defl_support_type": support_type,
            "defl_limit_ratio": defl_limit_ratio,
            "defl_Fdef": Fdef_kNm,
            "defl_use_simplified_ief": use_simplified_ief,
            "defl_Ief_user": st.session_state.get("defl_Ief_user"),
            "sls_Mstar": M_used,
            "sls_Vstar": V_used,
            "load_case": load_case,
            "beam_system_mode": st.session_state.get(
                "sfd_beam_system_mode",
                get_param("beam_system_mode", None),
            ),
            "span_L_m": L_sfd,
            "w_sls_kNm_per_m": w_sls,
            "P_sls_kN": P_sls,
            "a_m": a,
            "actions_source": actions_source,
            "g_udl_kNm_per_m": g,
            "q_udl_kNm_per_m": q,
            "psi_udl": psi_s,
            "G_point_kN": G_point,
            "Q_point_kN": Q_point,
            "psi_point": get_param("psi_point", psi_s),
            **_deflection_reference_row_projection(),
            "defl_L_eff": L_eff_m,
            "phi_cc_t": phi_cc_t,
            "stress_ratio": stress_ratio,
            "sustained_Mstar_kNm": sustained_mstar,
            "sustained_sigma_cs_mpa": sustained_sigma_cs,
            "reference_source": (
                "Load Analysis" if is_design_driven else "Beam Inputs"
            ),
        }
    )
    render_page_reference_sidebar(
        build_deflection_reference(deflection_reference_values)
    )
    render_deflection_checks(
        checks_snapshot,
        sync_callbacks=sync_callbacks,
        get_parameter=get_param,
    )

    
    # Handle scroll after all content is rendered (for cross-page navigation from Inputs)
    from jump_nav import scroll_to_jump_after_render
    scroll_to_jump_after_render()
