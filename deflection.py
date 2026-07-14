# deflection_page.py
import math
import pandas as pd
import streamlit as st
from pathlib import Path

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


def _deflection_diagram_reo_layers(D_mm: float) -> dict:
    """Visual-only reo layer metadata for the deflected shape diagram."""
    ss = st.session_state

    def _as_float(value, default: float = 0.0) -> float:
        try:
            out = float(value)
        except (TypeError, ValueError):
            return float(default)
        if not math.isfinite(out):
            return float(default)
        return out

    def _first_number(*keys: str, default: float = 0.0) -> float:
        for key in keys:
            value = ss.get(key)
            if value is None:
                value = get_param(key, None)
            if value is None:
                continue
            return _as_float(value, default)
        return float(default)

    def _layers(section: str) -> list[dict]:
        is_bottom = section == "bot"
        cover_key = "cover_bot" if is_bottom else "cover_top"
        rowgap_key = "defl_rowgap_bot" if is_bottom else "defl_rowgap_top"
        shared_rowgap_key = "rowgap_bot" if is_bottom else "rowgap_top"
        cover = _first_number(cover_key, default=40.0)
        rowgap = _first_number(rowgap_key, shared_rowgap_key, default=60.0)
        row_count = int(
            max(
                min(
                    _first_number(
                        f"defl_{section}_row_count",
                        f"{section}_row_count",
                        default=1.0,
                    ),
                    4.0,
                ),
                0.0,
            )
        )
        layers: list[dict] = []
        previous_y = None
        previous_db = None
        for row_idx in range(1, row_count + 1):
            count = int(
                max(
                    _first_number(
                        f"defl_{section}_row_{row_idx}_bars",
                        f"{section}_row_{row_idx}_bars",
                        f"defl_{section}{row_idx}_count",
                        f"{section}{row_idx}_count",
                        default=0.0,
                    ),
                    0.0,
                )
            )
            spacing = _first_number(
                f"defl_{section}_row_{row_idx}_spacing",
                f"{section}_row_{row_idx}_spacing",
                f"defl_{section}{row_idx}_spacing",
                f"{section}{row_idx}_spacing",
                default=0.0,
            )
            db = _first_number(
                f"defl_{section}_row_{row_idx}_dia",
                f"{section}_row_{row_idx}_dia",
                f"defl_db_{section}_{row_idx}",
                f"db_{section}_{row_idx}",
                default=20.0 if is_bottom else 16.0,
            )
            if db <= 0.0 or (count <= 0 and spacing <= 0.0):
                continue
            if previous_y is None or previous_db is None:
                y_from_top = (
                    float(D_mm) - cover - 0.5 * db
                    if is_bottom
                    else cover + 0.5 * db
                )
            elif is_bottom:
                y_from_top = previous_y - 0.5 * previous_db - rowgap - 0.5 * db
            else:
                y_from_top = previous_y + 0.5 * previous_db + rowgap + 0.5 * db
            previous_y = y_from_top
            previous_db = db
            layers.append(
                {
                    "count": count,
                    "spacing": spacing,
                    "db": db,
                    "y_from_top_mm": max(0.0, min(float(D_mm), y_from_top)),
                }
            )
        return layers

    return {"bottom": _layers("bot"), "top": _layers("top")}


def _refresh_deflection_effective_span_from_mm(
    L_mm,
    fallback_mm: float = 0.0,
) -> float | None:
    """Keep the derived deflection span in metres aligned with the active mm input."""
    try:
        L_current_mm = float(L_mm if L_mm is not None else fallback_mm)
    except (TypeError, ValueError):
        L_current_mm = float(fallback_mm or 0.0)
    if not math.isfinite(L_current_mm) or L_current_mm <= 0.0:
        return None
    L_eff_m = L_current_mm / 1000.0
    st.session_state["defl_L_eff"] = L_eff_m
    return L_eff_m


def seed_design_deflection_support_widget_before_render(widget_key: str, resolved: str) -> None:
    """Seed design-controlled support widgets before Streamlit instantiates them."""
    if str(st.session_state.get("actions_mode", "manual") or "manual") != "design":
        return
    support_type = _normalize_deflection_support_type(resolved)
    try:
        st.session_state["defl_support_type"] = support_type
        if widget_key:
            st.session_state[str(widget_key)] = support_type
    except Exception:
        pass


def _is_design_multispan_mode(state: dict) -> bool:
    return _calc_is_design_multispan_mode(
        state,
        actions_mode_default=get_param("actions_mode", "manual"),
    )


def _multispan_design_elastic_loads(source: dict) -> tuple[list[float], list[str], list[dict], list[dict], list[dict], list[dict]]:
    """
    Design-page multi-span model: characteristic (g+q) and sustained (g + ψ q) SLS loads
    for the same geometry the SFD/BMD page uses with ``solve_beam_structure``.
    """
    return _calc_multispan_design_elastic_loads(
        source,
        psi_point_default=get_param("psi_point", 0.4),
        psi_udl_default=get_param("psi_udl", 0.4),
    )


def _active_multispan_lengths_m(state: dict) -> list[float]:
    return _calc_active_multispan_lengths_m(state)


def compute_and_store_multispan_deflection_metrics(
    *,
    state: dict | None = None,
    Ec: float,
    Ief: float,
    g_kNm: float,
    q_kNm: float,
    psi_s: float,
    defl_limit_ratio: float,
    Ast: float = 0.0,
    Asc: float = 0.0,
) -> dict:
    """
    Canonical multispan governing metrics writer.

    Writes only:
    - defl_span_deflections_mm
    - defl_span_utilisations

    Primary path (design multispan): **elastic line from** ``beam_analysis.solve_beam_structure``
    with the same nodal geometry, support fixities (pinned/roller/fixed), point loads
    (G+Q and sustained G+ψQ), and UDL segments as the Design page — then
    δ(x) ≈ sag_char(x) + kₛₛ·sag_sus(x), and each span stores **max |δ|** within that span.

    Fallback: per-span ``calc_deflection_as3600`` with k₂ end/interior approximation
    if the FEM path fails.
    """
    source = state if isinstance(state, dict) else st.session_state
    try:
        from beam_analysis import solve_beam_structure
    except Exception:
        solve_beam_structure = None

    metrics = multispan_deflection_metric_values(
        state=source,
        Ec=Ec,
        Ief=Ief,
        g_kNm=g_kNm,
        q_kNm=q_kNm,
        psi_s=psi_s,
        defl_limit_ratio=defl_limit_ratio,
        Ast=Ast,
        Asc=Asc,
        actions_mode_default=get_param("actions_mode", "manual"),
        psi_point_default=get_param("psi_point", 0.4),
        psi_udl_default=get_param("psi_udl", 0.4),
        solve_beam_structure_fn=solve_beam_structure,
    )

    if not metrics.get("available"):
        source.pop("defl_span_deflections_mm", None)
        source.pop("defl_span_utilisations", None)
        source.pop("defl_multispan_metrics_source", None)
        return metrics

    span_deflections_mm = metrics["span_deflections_mm"]
    span_utilisations = metrics["span_utilisations"]
    metrics_source = metrics["metrics_source"]

    source["defl_span_deflections_mm"] = span_deflections_mm
    source["defl_span_utilisations"] = span_utilisations
    source["defl_multispan_metrics_source"] = metrics_source
    return {
        "available": True,
        "span_deflections_mm": span_deflections_mm,
        "span_utilisations": span_utilisations,
    }

def get_deflection_diagram_support_condition(state: dict | None = None) -> dict:
    """
    Single source of truth for deflection support (k₂ / F_d,ef / diagrams / summaries).

    - Manual mode: resolved from user ``defl_support_type`` (normalized).
    - Design + multi-span: Continuous end vs interior from controlling span index.
    - Design + single-span: derived from ``sfd_case`` + support condition. Prefer canonical
      ``design_support_condition`` (set_shared) over ``sfd_support_condition`` (widget can lag after edits).
      Beam system uses ``sfd_beam_system_mode`` or ``design_beam_system_mode``.
    """
    source = state if isinstance(state, dict) else st.session_state
    # Avoid treating missing/empty actions_mode as manual: dict.get skips get_param default when key exists.
    _am = source.get("actions_mode")
    if _am is None or (isinstance(_am, str) and _am.strip() == ""):
        _am = get_param("actions_mode", "manual")
    mode = str(_am or "manual").strip().lower()
    if mode not in ("manual", "design"):
        mode = "manual"
    # Early Deflection renders can compute mode as manual before session is consistent; trust global toggle.
    if is_design_governing():
        mode = "design"

    raw_widget = str(
        source.get("defl_support_type")
        or get_param("defl_support_type", "Simply supported")
        or "Simply supported"
    )
    canonical = _normalize_deflection_support_type(raw_widget)

    beam_mode = str(
        source.get("sfd_beam_system_mode")
        or source.get("design_beam_system_mode")
        or ""
    ).strip()
    raw_cf = raw_widget.strip().casefold()
    sfd_case_norm = str(source.get("sfd_case", "") or "").strip()
    # Multispan: prefer current Design-page beam system. Stale defl_support_type == "Continuous beam"
    # must not imply multispan when sfd_beam_system_mode is explicitly Single span.
    # (Manual mode still uses the same rule; resolution ignores is_multi on the manual branch.)
    if beam_mode == "Single span":
        is_multi = False
    elif beam_mode == "Multi-span":
        is_multi = True
    else:
        is_multi = (
            raw_cf == "continuous beam"
            or sfd_case_norm.startswith("Multi-span continuous beam")
        )

    controlling_idx = 0
    controlling_reason = "single-span"

    continuous_end_side = None
    _dbg_branch = ""
    _dbg_derived = None
    if mode == "manual":
        _dbg_branch = "manual"
        resolved = canonical
        controlling_idx, controlling_reason = 0, "manual selection"
    elif mode == "design" and is_multi:
        _dbg_branch = "design_multispan"
        controlling_idx, controlling_reason = _pick_controlling_span_index(source)
        try:
            n_spans = int(float(source.get("sfd_span_count", 0.0) or 0.0))
        except Exception:
            n_spans = 0
        if n_spans >= 2:
            resolved = (
                "Continuous – end span"
                if controlling_idx in (0, n_spans - 1)
                else "Continuous – interior span"
            )
            if controlling_idx == 0:
                continuous_end_side = "right"
            elif controlling_idx == n_spans - 1:
                continuous_end_side = "left"
        else:
            resolved = "Continuous – interior span"
    else:
        _dbg_branch = "design_single_span"
        load_case = str(source.get("sfd_case", "") or "")
        sfd_sup = source.get("sfd_support_condition")
        des_sup = source.get("design_support_condition")
        # Canonical design_* updates first on Design page; sfd_* widget value can stay stale one rerun.
        support_condition = des_sup or sfd_sup
        derived = _defl_support_type_from_design_selection(load_case, support_condition)
        _dbg_derived = derived
        resolved = _normalize_deflection_support_type(derived)
        controlling_idx, controlling_reason = 0, "design single-span (SFD)"

    support_type = _normalize_deflection_support_type(resolved)


    out = {
        "support_type": support_type,
        "mode": mode,
        "canonical_support_type": canonical,
        "multi_span": bool(is_multi),
        "controlling_span_idx": int(max(0, controlling_idx)),
        "controlling_reason": controlling_reason,
        "continuous_end_side": continuous_end_side,
    }
    if _DEBUG_DEFLECTION_SUPPORT_RESOLUTION:
        try:
            print(
                "DEFLECTION_SUPPORT_RESOLUTION",
                {
                    "mode": out["mode"],
                    "actions_source": str(source.get("actions_source", "")),
                    "raw_defl_support_type": str(source.get("defl_support_type", "")),
                    "raw_sfd_beam_system_mode": str(source.get("sfd_beam_system_mode", "")),
                    "raw_sfd_support_condition": str(source.get("sfd_support_condition", "")),
                    "canonical": out["canonical_support_type"],
                    "multi_span": out["multi_span"],
                    "controlling_span_idx": out["controlling_span_idx"],
                    "controlling_reason": out["controlling_reason"],
                    "resolved": out["support_type"],
                },
            )
        except Exception:
            pass
    return out


def get_resolved_deflection_support_type(state: dict | None = None) -> str:
    """Resolved support label for deflection — use instead of raw ``defl_support_type`` in calcs/summaries."""
    return get_deflection_diagram_support_condition(state)["support_type"]


def _seed_from_param(name: str, fallback: float) -> float:
    """Read numeric from shared state with get_param(name), with fallback."""
    try:
        v = get_param(name)
    except TypeError:
        v = None

    try:
        if v is None:
            return float(fallback)
        v = float(v)
        if math.isnan(v):
            return float(fallback)
        return v
    except Exception:
        return float(fallback)


def _render_readonly_value(
    label: str,
    value,
    unit: str,
    help_text: str | None = None,
):
    """
    Render a read-only value with label and optional help text.
    Uses the same styling as other read-only inputs.
    """
    col1, col2 = st.columns([1, 2])
    with col1:
        label_with_hover(label, help_text)
    with col2:
        if value is None:
            display_value = "—"
            color_style = "color: #999;"
        else:
            if isinstance(value, float):
                if unit == "mm":
                    display_value = f"{value:.0f} {unit}"
                elif unit == "mm²":
                    display_value = f"{value:.0f} {unit}"
                elif unit == "MPa":
                    display_value = f"{value:.2f} {unit}"
                else:
                    display_value = f"{value:.1f} {unit}"
            else:
                display_value = f"{value} {unit}" if unit else str(value)
            color_style = ""

        st.markdown(
            f"""
<div class="readonly-param" style="padding: 0.5rem 0.75rem; margin: 0;">
  <div class="readonly-param-value" style="font-size: 1rem; margin: 0; {color_style}">{display_value}</div>
</div>
""",
            unsafe_allow_html=True,
        )


def deflection_has_service_load_for_calc() -> bool:
    """
    True when the resolved service UDL model has positive total load (g_equiv + q_equiv),
    matching ``compute_deflection_results`` / the Deflection page.
    """
    g_udl = get_param("g_udl_kNm_per_m", None)
    q_udl = get_param("q_udl_kNm_per_m", None)
    w_sls = get_param("w_sls_kNm_per_m", None)
    sls_M_kNm = get_param("sls_Mstar", 0.0)
    sls_V_kN = get_param("sls_Vstar", 0.0)
    L = get_param("L", 3000.0)
    L_m = float(L or 0.0) / 1000.0
    L_m_for_fd = get_param("defl_L_eff", L_m)
    if L_m_for_fd is None or L_m_for_fd <= 0:
        L_m_for_fd = get_param("span_L_m", L_m)
    if L_m_for_fd is None:
        L_m_for_fd = 0.0
    support_type = get_deflection_diagram_support_condition(st.session_state).get(
        "support_type", "Simply supported"
    )
    derived = _derive_equiv_udl_from_actions(
        M_kNm=sls_M_kNm,
        V_kN=sls_V_kN,
        L_m=float(L_m_for_fd),
        support_type=str(support_type),
    )
    g_eq, q_eq = resolve_deflection_equiv_loads_from_inputs(
        derived=derived,
        w_sls=w_sls,
        g_udl=g_udl,
        q_udl=q_udl,
    )
    return (float(g_eq) + float(q_eq)) > 1e-12


# ------------------------------------------------------------
#  MAIN RENDER FUNCTION
# ------------------------------------------------------------
def render_deflection():
    """Deflection page – short-term, long-term, span/depth to AS 3600:2018 Cl. 8.5."""
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

    render_result_page_title("Beam Deflection")

    if not deflection_has_service_load_for_calc():
        st.info("No loads applied — deflection not calculated")

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

    # 3-column layout matching Shear pattern
    col_geom, col_mats, col_loads = specialized_widget_rail_columns(
        "deflection_primary_inputs",
        3,
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

    with st.container():
        _defl_sec_shape_ui = str(get_param("sec_shape", "RECT") or "RECT")
        _defl_bot_md, _defl_top_md = main_longitudinal_reo_pair_labels(
            _defl_sec_shape_ui, variant="sentence_lower"
        )
        _reo_pad_l, _reo_mid, _reo_pad_r = st.columns([1, 3, 1])
        with _reo_mid:
            reo_col_left, reo_col_right = st.columns([1, 1], gap="large")
            with reo_col_left:
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
                            rowgap_help_text=(
                                "Clear vertical gap between reinforcement rows (mm)."
                            ),
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

            with reo_col_right:
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
                            rowgap_help_text=(
                                "Clear vertical gap between reinforcement rows (mm)."
                            ),
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

    # Read derived reinforcement areas for calculations (no UI rows)
    Ast = _seed_from_param("Ast_bot", 2010.0)
    Asc = _seed_from_param("Ast_top", 0.0)

    # Always refresh deflection results for summary/reporting.
    from deflection_core import compute_deflection_results
    compute_deflection_results(publish=True)

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
            )
            render_plotly_diagram(
                beam_fig,
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
        )
        # Note: Changing this will require rerun to update calculations

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
