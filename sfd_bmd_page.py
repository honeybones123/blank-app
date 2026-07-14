# sfd_bmd_page.py
# ==========================================
# SFD & BMD teaching page for beam app
# ==========================================

import math
import time
from pathlib import Path
import numpy as np
import matplotlib.pyplot as plt
import plotly.graph_objects as go
import streamlit as st
from streamlit_plotly_events import plotly_events
from ui.diagrams.moment_shear_diagram import (
    _add_plotly_support_markers_aligned as _shared_add_plotly_support_markers_aligned,
    figure_bmd_from_state as _shared_figure_bmd_from_state,
    figure_sfd_from_state as _shared_figure_sfd_from_state,
    plot_load_diagram_plotly as _shared_plot_load_diagram_plotly,
    plot_section_locator_plotly as _shared_plot_section_locator_plotly,
)

from state_and_helpers import (
    get_sync_callbacks,
    get_param,
    is_design_governing,
    set_shared,
    update_results,
)
from widgets_helpers import (
    apply_global_widget_css,
    apply_result_page_css,
    apply_calcbox_css,
    render_result_page_title,
    render_section_title,
    render_page_explainer_expander,
    number_row,
    calcbox,
    page_divider,
    step_expander_calcbox,
    apply_step_summary_expander_css,
    v2_checkbox,
    v2_radio,
    _register_rendered_key,
    _wrap_user_edit,
    info_i_button,
    render_plotly_diagram,
    render_plotly_fullscreen_control,
)
from engineering_check_ui import DESIGN_ACTION_SUMMARY_COLUMNS, sync_legacy_value_limit
from ui_seamless_steps import render_clickable_summary_table, bind_summary_clicks

from beam_analysis import (
    build_beam_model_from_legacy_case,
    legacy_results_local_from_result,
    solve_beam_structure,
    solve_single_span_beam,
    solve_beam_model,
)
from calculations.deflection import (
    defl_support_type_from_design_selection as _calc_defl_support_type_from_design_selection,
)


def _agent_debug_log(message: str, data: dict, *, run_id: str, hypothesis_id: str, location: str) -> None:
    try:
        payload = {
            "sessionId": "b9a7cf",
            "runId": run_id,
            "hypothesisId": hypothesis_id,
            "location": location,
            "message": message,
            "data": data,
            "timestamp": int(time.time() * 1000),
        }
        with (Path(__file__).resolve().with_name("debug-b9a7cf.log")).open("a", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=True) + "\n")
    except Exception:
        pass


def _label_with_hover(label: str, help_text: str) -> None:
    """Hover tooltip on the label text itself (no visible paragraph)."""
    safe = (help_text or "").replace('"', "&quot;")
    st.markdown(f'<span title="{safe}">{label}</span>', unsafe_allow_html=True)


# ---------------------------------------------------
# Helper: get span from Inputs page
# ---------------------------------------------------
def _span_from_inputs(fallback: float = 6.0) -> float:
    """Read span L from Inputs page; safe fallback if missing."""
    try:
        L_val = get_param("L")
    except TypeError:
        L_val = None

    try:
        if L_val is None:
            return float(fallback)
        return float(L_val) / 1000.0
    except (TypeError, ValueError):
        return float(fallback)


def _support_type_from_load_case(load_case: str) -> str:
    text = (load_case or "").strip()
    if text.startswith("Cantilever"):
        return "Cantilever"
    if text.startswith("Simple beam"):
        return "Simply supported"
    if text.startswith("Overhanging beam"):
        return "Simply supported"
    return "Simply supported"


def _defl_support_type_from_selection(load_case: str, support_condition: str | None) -> str:
    return _calc_defl_support_type_from_design_selection(load_case, support_condition)


def _sync_design_shared_value(shared_key: str, value, *, source: str) -> None:
    """Keep Design/SFD shared state aligned when this page resolves a support value."""
    try:
        set_shared(shared_key, value, source=source)
    except Exception:
        pass
    if st.session_state.get(shared_key) != value:
        st.session_state[shared_key] = value


def _format_solver_vector(name: str, values: list[float], units: str = "") -> str:
    vals = [float(v) for v in (values or [])]
    if not vals:
        return f"\\[{name} = [\\ ]\\]"
    vec = ",\\ ".join(f"{v:.3g}" for v in vals)
    unit_text = f"\\,\\text{{{units}}}" if units else ""
    return f"\\[{name} = [{vec}]{unit_text}\\]"


def _format_solver_matrix(name: str, matrix: list[list[float]], max_rows: int = 4, max_cols: int = 4) -> str:
    mat = matrix or []
    n_rows = len(mat)
    n_cols = len(mat[0]) if n_rows > 0 else 0
    if n_rows == 0 or n_cols == 0:
        return f"\\[{name} = [\\ ]\\]"
    r_show = min(max_rows, n_rows)
    c_show = min(max_cols, n_cols)
    rows_txt = []
    for i in range(r_show):
        row_vals = [float(v) for v in mat[i][:c_show]]
        row_txt = " & ".join(f"{v:.3g}" for v in row_vals)
        if c_show < n_cols:
            row_txt += " & \\cdots"
        rows_txt.append(row_txt)
    if r_show < n_rows:
        rows_txt.append("\\vdots & \\vdots & \\ddots")
    body = " \\\\ ".join(rows_txt)
    return (
        f"\\[{name}\\in\\mathbb{{R}}^{{{n_rows}\\times {n_cols}}},\\quad "
        f"{name} \\approx \\begin{{bmatrix}}{body}\\end{{bmatrix}}\\]"
    )


def _format_support_restraints(metadata: dict) -> str:
    restrained = [int(v) for v in list(metadata.get("restrained_dofs") or [])]
    free = [int(v) for v in list(metadata.get("free_dofs") or [])]
    r_txt = ", ".join(str(v) for v in restrained[:10]) + (", \\ldots" if len(restrained) > 10 else "")
    f_txt = ", ".join(str(v) for v in free[:10]) + (", \\ldots" if len(free) > 10 else "")
    return (
        f"\\[\\text{{Restrained DOFs}} = [{r_txt}],\\qquad "
        f"\\text{{Free DOFs}} = [{f_txt}]\\]"
    )


def _clean_sfd_deriv_lines(items) -> list[str]:
    out: list[str] = []
    for item in items:
        if item is None or item == "":
            continue
        if isinstance(item, (list, tuple)):
            out.extend(_clean_sfd_deriv_lines(item))
        else:
            out.append(str(item))
    return out


def _get_beam_analysis_case_label(case: str, support_condition_active: str) -> str:
    sc = (support_condition_active or "").strip().replace("-", "–")
    if case == "Multi-span continuous beam":
        return "Multi-span continuous beam (numerical beam model)"
    if case == "Overhanging beam – right overhang with point load at free end":
        return "Overhanging beam — pinned supports with right overhang"
    if case.startswith("Cantilever"):
        return "Cantilever (fixed–free)"
    if case.startswith("Simple beam"):
        if sc in {"Fixed–Pinned", "Pinned–Fixed", "Fixed–Fixed"}:
            return f"Single span — {sc} (statically indeterminate; numerical beam solver)"
        if sc == "Simply supported":
            return "Simply supported (pin + roller)"
        if sc == "Pinned–Pinned":
            return "Pinned–pinned (double pin)"
        if sc == "":
            return "Simply supported (pin + roller)"
        return f"Single span — {sc}"
    return sc or "Beam model"


def _is_closed_form_sfd_case(case: str, fixed_end_indeterminate: bool) -> bool:
    if case == "Multi-span continuous beam":
        return False
    if case.startswith("Simple beam") and fixed_end_indeterminate:
        return False
    return True


def _build_solver_explanation_lines(*, kind: str, design_actions_source: str) -> list[str]:
    lines = [
        "The beam model is formed from the span, support conditions, and applied design loads.",
        "The solver applies the selected boundary conditions and solves for the restrained response that satisfies equilibrium and compatibility.",
    ]
    if kind == "shear":
        lines.append(
            "The beam model is analysed numerically using the selected support conditions and applied loads."
        )
        lines.append(
            "The solver enforces equilibrium together with the support restraints to recover the internal shear response along the span."
        )
        lines.append(
            "Once the beam response is solved, the internal shear force $V(x)$ is recovered along the span."
        )
    else:
        lines.append(
            "The beam model is analysed numerically using the selected support conditions and applied loads."
        )
        lines.append(
            "The solved beam response is used to recover the bending moment distribution $M(x)$ along the span."
        )
    if design_actions_source == "section":
        lines.append(
            "The design action is then taken at the committed design section location rather than from the global maximum along the span."
        )
    else:
        if kind == "shear":
            lines.append(
                "The governing design shear is taken from the solved SFD as the maximum absolute value along the span."
            )
        else:
            lines.append(
                "The governing design moment is taken from the solved BMD as the maximum absolute value along the span."
            )
    return lines


def _strip_sfd_step4_title_line(md: str) -> str:
    m = (md or "").strip()
    if m.startswith("**Step 4"):
        nl = m.find("\n")
        if nl != -1:
            m = m[nl + 1 :].lstrip()
    return m


def _strip_leading_load_intro(md: str, load_intro: str) -> str:
    if load_intro and md.startswith(load_intro):
        return md[len(load_intro) :].lstrip()
    return md


def _governing_shear_star_value(
    *,
    active_mode: str,
    design_actions_source: str,
    section_committed: bool,
    V_array,
) -> float:
    if design_actions_source == "section" and section_committed:
        key = "design_V_uls_kN" if active_mode == "ULS" else "design_V_sls_kN"
        return float(get_param(key, 0.0) or 0.0)
    if V_array is not None and len(V_array):
        return float(np.max(np.abs(V_array)))
    return 0.0


def _governing_moment_star_value(
    *,
    active_mode: str,
    design_actions_source: str,
    section_committed: bool,
    M_array,
) -> float:
    if design_actions_source == "section" and section_committed:
        key = "design_M_uls_kNm" if active_mode == "ULS" else "design_M_sls_kNm"
        return abs(float(get_param(key, 0.0) or 0.0))
    if M_array is not None and len(M_array):
        return float(np.max(np.abs(M_array)))
    return 0.0


def _format_sfd_shear_derivation_panel_md(
    *,
    load_intro: str,
    active_mode: str,
    case: str,
    support_condition_active: str,
    fixed_end_indeterminate: bool,
    span_m: float,
    design_actions_source: str,
    section_committed: bool,
    design_x_m: float,
    V_array,
    case_specific_md: str,
) -> str:
    is_cf = _is_closed_form_sfd_case(case, fixed_end_indeterminate)
    support_line = _get_beam_analysis_case_label(case, support_condition_active)
    inner = _strip_leading_load_intro((case_specific_md or "").strip(), load_intro)

    parts: list[str] = []
    parts.append(
        "**Purpose**  \n"
        "Determine the beam shear response along the span and extract the governing design shear for the active load case."
    )
    parts.append(
        "**1) Inputs / model**  \n"
        f"- Support condition: {support_line}  \n"
        f"- Span (analysis length): $L = {float(span_m):.3g}\\,\\mathrm{{m}}$  \n"
        f"- Beam response uses the resolved {active_mode} combined loading from Step 0."
    )
    parts.append("**2) Governing relation / solver statement**  \n")
    if is_cf:
        parts.append(
            "For this idealisation, $V(x)$ is obtained from conventional section equilibrium (free-body cuts to the left or right of the section) using the support actions from Step 2 "
            "and the applied load pattern. Piecewise closed-form expressions are stated below where they apply."
        )
    else:
        parts.append(
            "The internal shear distribution $V(x)$ is obtained from the numerical beam model: form the element system, impose the selected supports and applied loads, "
            "then recover internal shears along the member axis from the solved displacements and end forces."
        )
        for line in _build_solver_explanation_lines(kind="shear", design_actions_source=design_actions_source):
            parts.append(f"- {line}")

    parts.append("**3) Response along the span**  \n")
    if inner:
        parts.append(inner)
    else:
        parts.append(
            "Shear ordinates follow the solved SFD for the active load case (see diagram above), consistent with Step 2 reactions and the load model."
        )

    parts.append("**4) Design-action extraction**  \n")
    if design_actions_source == "section":
        parts.append("For design-section mode:")
        parts.append(r"$$V^* = \left|V(x_{\mathrm{design}})\right|$$")
        x_show = (
            float(design_x_m)
            if section_committed
            else float(get_param("section_cursor_x_m", design_x_m) or 0.0)
        )
        parts.append(f"with $x_{{\\mathrm{{design}}}} = {x_show:.3f}\\,\\mathrm{{m}}$.")
    else:
        parts.append("For governing maxima along the span:")
        parts.append(r"$$V^* = \max_x \left|V(x)\right|$$")

    v_star = _governing_shear_star_value(
        active_mode=active_mode,
        design_actions_source=design_actions_source,
        section_committed=section_committed,
        V_array=V_array,
    )
    vp = float(np.max(V_array)) if V_array is not None and len(V_array) else None
    vn = float(np.min(V_array)) if V_array is not None and len(V_array) else None
    res_lines = _clean_sfd_deriv_lines(
        [
            f"- $V_{{\\max,+}} = {vp:.3g}\\,\\mathrm{{kN}}$" if vp is not None else None,
            f"- $V_{{\\max,-}} = {vn:.3g}\\,\\mathrm{{kN}}$" if vn is not None else None,
            f"- Governing design shear ({active_mode}): $V^* = {v_star:.3g}\\,\\mathrm{{kN}}$",
        ]
    )
    parts.append("**5) Published extremes and governing value**  \n" + "\n".join(res_lines))
    return "\n\n".join(parts)


def _format_sfd_moment_derivation_panel_md(
    *,
    load_intro: str,
    active_mode: str,
    case: str,
    support_condition_active: str,
    fixed_end_indeterminate: bool,
    span_m: float,
    design_actions_source: str,
    section_committed: bool,
    design_x_m: float,
    M_array,
    case_specific_md: str,
) -> str:
    is_cf = _is_closed_form_sfd_case(case, fixed_end_indeterminate)
    support_line = _get_beam_analysis_case_label(case, support_condition_active)
    inner = _strip_sfd_step4_title_line(case_specific_md or "")
    inner = _strip_leading_load_intro(inner.strip(), load_intro)

    parts: list[str] = []
    parts.append(
        "**Purpose**  \n"
        "Determine the beam bending-moment response along the span and extract the governing design moment for the active load case."
    )
    parts.append(
        "**1) Inputs / model**  \n"
        f"- Support condition: {support_line}  \n"
        f"- Span (analysis length): $L = {float(span_m):.3g}\\,\\mathrm{{m}}$  \n"
        f"- Beam response uses the resolved {active_mode} combined loading from Step 0."
    )
    parts.append("**2) Governing relation / solver statement**  \n")
    if is_cf:
        parts.append(
            "For this idealisation, $M(x)$ follows from integrating shear (where continuous), direct equilibrium of free bodies, or known closed-form beam expressions "
            "for the selected load case. Piecewise expressions below are consistent with the sign convention used in the diagrams."
        )
    else:
        parts.append(
            "The bending moment distribution $M(x)$ is recovered from the numerical beam solution (internal forces / element end actions) after imposing supports and loads."
        )
        for line in _build_solver_explanation_lines(kind="moment", design_actions_source=design_actions_source):
            parts.append(f"- {line}")

    parts.append("**3) Response along the span**  \n")
    if inner:
        parts.append(inner)
    else:
        parts.append(
            "Moment ordinates follow the solved BMD for the active load case (see diagram above), consistent with the shear diagram and support fixity."
        )

    parts.append("**4) Design-action extraction**  \n")
    if design_actions_source == "section":
        parts.append("For design-section mode:")
        parts.append(r"$$M^* = \left|M(x_{\mathrm{design}})\right|$$")
        x_show = (
            float(design_x_m)
            if section_committed
            else float(get_param("section_cursor_x_m", design_x_m) or 0.0)
        )
        parts.append(f"with $x_{{\\mathrm{{design}}}} = {x_show:.3f}\\,\\mathrm{{m}}$.")
    else:
        parts.append("For governing maxima along the span:")
        parts.append(r"$$M^* = \max_x \left|M(x)\right|$$")

    m_star = _governing_moment_star_value(
        active_mode=active_mode,
        design_actions_source=design_actions_source,
        section_committed=section_committed,
        M_array=M_array,
    )
    mp = float(np.max(M_array)) if M_array is not None and len(M_array) else None
    mn = float(np.min(M_array)) if M_array is not None and len(M_array) else None
    res_lines = _clean_sfd_deriv_lines(
        [
            f"- $M_{{\\max,+}} = {mp:.3g}\\,\\mathrm{{kNm}}$" if mp is not None else None,
            f"- $M_{{\\max,-}} = {mn:.3g}\\,\\mathrm{{kNm}}$" if mn is not None else None,
            f"- Governing design moment magnitude ({active_mode}): $M^* = {m_star:.3g}\\,\\mathrm{{kNm}}$",
        ]
    )
    parts.append("**5) Published extremes and governing value**  \n" + "\n".join(res_lines))
    return "\n\n".join(parts)


def render_inline_number_row(
    label: str,
    key: str,
    value,
    *,
    min_value=None,
    max_value=None,
    step=0.01,
    format="%.2f",
    help_text=None,
    label_col_ratio=1.15,
    input_col_ratio=1.0,
    disabled=False,
    sync_callbacks=None,
    on_change=None,
):
    """
    Render one input row with label on the left and widget on the right.
    This prevents widgets from dropping below labels when branch layout
    contexts differ across loading conditions.
    """
    col_label, col_input = st.columns([label_col_ratio, input_col_ratio], vertical_alignment="center")

    with col_label:
        st.markdown(
            f"""
            <div style="
                padding-top: 0.35rem;
                padding-bottom: 0.15rem;
                font-size: 1rem;
                font-weight: 500;
            ">
                {label}
            </div>
            """,
            unsafe_allow_html=True,
        )

    with col_input:
        _register_rendered_key(key)

        def _clamp_widget_num(v, lo, hi):
            try:
                v = float(v)
            except (TypeError, ValueError):
                v = 0.0 if lo is None else float(lo)
            if lo is not None:
                v = max(float(lo), v)
            if hi is not None:
                v = min(float(hi), v)
            return v

        if key not in st.session_state:
            st.session_state[key] = _clamp_widget_num(value, min_value, max_value)
        else:
            st.session_state[key] = _clamp_widget_num(
                st.session_state[key], min_value, max_value
            )

        on_change_callback = on_change
        if on_change_callback is None and sync_callbacks and isinstance(sync_callbacks, dict):
            on_change_callback = sync_callbacks.get(key)
        if on_change_callback is not None:
            on_change_callback = _wrap_user_edit(key, on_change_callback)
        return st.number_input(
            label="",
            key=key,
            value=st.session_state.get(key, value),
            min_value=min_value,
            max_value=max_value,
            step=step,
            format=format,
            help=help_text,
            disabled=disabled,
            label_visibility="collapsed",
            on_change=on_change_callback,
        )


def render_inline_select_row(
    label: str,
    key: str,
    options,
    index=0,
    *,
    help_text=None,
    label_col_ratio=1.15,
    input_col_ratio=1.0,
    disabled=False,
    sync_callbacks=None,
    on_change=None,
):
    col_label, col_input = st.columns([label_col_ratio, input_col_ratio], vertical_alignment="center")

    with col_label:
        st.markdown(
            f"""
            <div style="
                padding-top: 0.35rem;
                padding-bottom: 0.15rem;
                font-size: 1rem;
                font-weight: 500;
            ">
                {label}
            </div>
            """,
            unsafe_allow_html=True,
        )

    with col_input:
        _register_rendered_key(key)
        if key not in st.session_state:
            st.session_state[key] = options[index]
        on_change_callback = on_change
        if on_change_callback is None and sync_callbacks and isinstance(sync_callbacks, dict):
            on_change_callback = sync_callbacks.get(key)
        if on_change_callback is not None:
            on_change_callback = _wrap_user_edit(key, on_change_callback)
        current_value = st.session_state.get(key, options[index])
        current_index = options.index(current_value) if current_value in options else index
        value = st.selectbox(
            label="",
            key=key,
            options=options,
            index=current_index,
            help=help_text,
            disabled=disabled,
            label_visibility="collapsed",
            on_change=on_change_callback,
        )
        return value


# ---------------------------------------------------
# Helper: draw support symbols
# ---------------------------------------------------
def draw_support(ax, x_pos, kind="pinned", size=0.18):
    """
    Draws a support symbol at x_pos on the x-axis.
    kind: "pinned", "roller", "fixed"
    Designed so the triangle POINTS UP to the beam (beam is along y = 0).
    """
    y_beam = 0.0
    apex_y = y_beam - 0.01          # just under the beam line
    base_y = apex_y - size          # bottom of triangle

    if kind in ("pinned", "roller"):
        half_base = size * 0.8

        # upright triangle (point up touching the beam underside)
        ax.plot(
            [x_pos - half_base, x_pos, x_pos + half_base, x_pos - half_base],
            [base_y, apex_y, base_y, base_y],
            "k", linewidth=1.5
        )

        # hinge dot right at the contact
        ax.plot(x_pos, apex_y, "ko", markersize=3)

        if kind == "roller":
            # roller circle below the triangle
            roller_y = base_y - size * 0.4
            ax.plot(x_pos, roller_y, "ko", markersize=4)

    elif kind == "fixed":
        # thick vertical wall at x_pos
        wall_height = size * 3
        ax.plot(
            [x_pos, x_pos],
            [y_beam - wall_height, y_beam + wall_height],
            "k",
            linewidth=4
        )
        # hatching into wall (left side)
        n_hatch = 5
        for i in range(n_hatch):
            yy = y_beam - wall_height + i * (2 * wall_height / max(n_hatch - 1, 1))
            ax.plot(
                [x_pos - size * 0.7, x_pos],
                [yy - size * 0.4, yy],
                "k",
                linewidth=1
            )


def _add_plotly_support_markers_aligned(
    fig: go.Figure,
    *,
    support_positions_plot: list[float],
    support_types_plot: list[str],
    y_min: float,
    y_max: float,
    L: float | None,
    support_type_fallback: str,
) -> None:
    _shared_add_plotly_support_markers_aligned(
        fig,
        support_positions_plot=support_positions_plot,
        support_types_plot=support_types_plot,
        y_min=y_min,
        y_max=y_max,
        L=L,
        support_type_fallback=support_type_fallback,
    )


# ---------------------------------------------------
# Helper: plot load diagram
# ---------------------------------------------------
def plot_load_diagram_plotly(
    case,
    L,
    params,
    preview_x_m: float | None = None,
    design_x_m: float | None = None,
    support_condition: str | None = None,
    support_positions: list[float] | None = None,
    support_types: list[str] | None = None,
    point_loads: list[dict] | None = None,
    udl_loads: list[dict] | None = None,
):
    return _shared_plot_load_diagram_plotly(
        case=case,
        L=L,
        params=params,
        preview_x_m=preview_x_m,
        design_x_m=design_x_m,
        support_condition=support_condition,
        support_positions=support_positions,
        support_types=support_types,
        point_loads=point_loads,
        udl_loads=udl_loads,
    )


# ---------------------------------------------------
# Helper: plot SFD and BMD (Plotly version)
# ---------------------------------------------------
def _prepare_sfd_bmd_plot_state(
    x,
    V,
    M,
    case: str | None = None,
    L: float | None = None,
    support_positions: list[float] | None = None,
    support_types: list[str] | None = None,
    preview_x_m: float | None = None,
    design_x_m: float | None = None,
    preview_V: float | None = None,
    preview_M: float | None = None,
) -> dict:
    """Shared numeric layout for SFD/BMD figures (supports, pads, series)."""
    if L is None and x is not None and len(x) > 0:
        L = float(x[-1])
    sp_raw: list[float] = [] if support_positions is None else [float(v) for v in support_positions]
    if not sp_raw and case and L is not None:
        if str(case).startswith("Simple beam"):
            sp_raw = [0.0, float(L)]
        elif str(case).startswith("Cantilever"):
            sp_raw = [0.0]
    support_positions_plot = [float(v) for v in sp_raw]
    support_types_plot = list(support_types or [])

    x_plot = x.tolist() if hasattr(x, "tolist") else list(x) if x is not None else []
    V_plot = V.tolist() if hasattr(V, "tolist") else list(V) if V is not None else []
    M_plot = M.tolist() if hasattr(M, "tolist") else list(M) if M is not None else []
    x_pad = max(float(L or 0.0) * 0.08, 0.12) if L is not None else 0.12
    support_type = str(get_param("support_type", "simply_supported") or "simply_supported").strip().lower()
    design_mode_active = bool(is_design_governing())
    d_v_mm = float(get_param("d_v", 0.0) or 0.0)
    zone_limit_m = 1.5 * d_v_mm / 1000.0
    return {
        "L": L,
        "case": case,
        "x_plot": x_plot,
        "V_plot": V_plot,
        "M_plot": M_plot,
        "support_positions_plot": support_positions_plot,
        "support_types_plot": support_types_plot,
        "preview_x_m": preview_x_m,
        "design_x_m": design_x_m,
        "preview_V": preview_V,
        "preview_M": preview_M,
        "x_pad": x_pad,
        "support_type": support_type,
        "design_mode_active": design_mode_active,
        "zone_limit_m": zone_limit_m,
        "d_v_mm": d_v_mm,
        "critical_shear_x": get_param("critical_shear_x"),
        "critical_shear_V": get_param("critical_shear_V"),
        "shear_spacing_end_mm": get_param("shear_spacing_end_mm"),
        "shear_spacing_mid_mm": get_param("shear_spacing_mid_mm"),
    }


def _figure_sfd_from_state(st: dict) -> go.Figure:
    if st["design_mode_active"] and st["L"] is not None and st["support_positions_plot"]:
        support_positions_plot = st["support_positions_plot"]
        support_types_plot = st["support_types_plot"]
        support_symbols = []
        for idx, sx in enumerate(support_positions_plot):
            stype = str(support_types_plot[idx] if idx < len(support_types_plot) else "").strip().lower()
            symbol = "\u23ca" if stype == "fixed" else "\u25b2"
            support_symbols.append({"x": float(sx), "type": stype, "symbol": symbol})
        _agent_debug_log(
            "plot_sfd_supports_rendered",
            {"support_symbols": support_symbols},
            run_id="pre-fix",
            hypothesis_id="H7",
            location="sfd_bmd_page.py:plot_sfd_supports_meta",
        )
    return _shared_figure_sfd_from_state(st)


def _figure_bmd_from_state(st: dict, *, show_m_peak: bool = False) -> go.Figure:
    return _shared_figure_bmd_from_state(st, show_m_peak=show_m_peak)

def plot_sfd_bmd_plotly(
    x,
    V,
    M,
    case: str | None = None,
    L: float | None = None,
    support_positions: list[float] | None = None,
    support_types: list[str] | None = None,
    preview_x_m: float | None = None,
    design_x_m: float | None = None,
    preview_V: float | None = None,
    preview_M: float | None = None,
    *,
    show_m_peak: bool = False,
):
    """Return Plotly figures for SFD and BMD.

    BMD ordinates use the structural convention **ordinate = −M** so hogging (M < 0)
    appears above the baseline; hover still reports the true M value.
    """
    st = _prepare_sfd_bmd_plot_state(
        x,
        V,
        M,
        case=case,
        L=L,
        support_positions=support_positions,
        support_types=support_types,
        preview_x_m=preview_x_m,
        design_x_m=design_x_m,
        preview_V=preview_V,
        preview_M=preview_M,
    )
    return _figure_sfd_from_state(st), _figure_bmd_from_state(st, show_m_peak=show_m_peak)


def plot_section_locator_plotly(
    L: float,
    preview_x_m: float | None = None,
    design_x_m: float | None = None,
) -> go.Figure:
    return _shared_plot_section_locator_plotly(
        L=L,
        preview_x_m=preview_x_m,
        design_x_m=design_x_m,
    )


def _clamp_x(x_m: float, max_x: float) -> float:
    return max(0.0, min(float(x_m), float(max_x)))


def _clamp_x_to_span(x_val, L):
    try:
        x = float(x_val)
    except (TypeError, ValueError):
        return None
    return max(0.0, min(float(L), x))


def _extract_clicked_x_from_plotly_event(event_data):
    """
    Safely extract x from a Plotly click-event payload.
    Returns None if no valid x is present.
    """
    if not event_data:
        return None

    if isinstance(event_data, list) and len(event_data) > 0:
        pt = event_data[0]
        if isinstance(pt, dict) and "x" in pt:
            return pt["x"]

    if isinstance(event_data, dict):
        if "x" in event_data:
            return event_data["x"]
        pts = event_data.get("points")
        if isinstance(pts, list) and len(pts) > 0 and isinstance(pts[0], dict):
            return pts[0].get("x")

    return None


def _interp_at_x(x_vals, y_vals, x_m: float) -> float:
    if x_vals is None or y_vals is None or len(x_vals) == 0 or len(y_vals) == 0:
        return 0.0
    x_eval = _clamp_x(x_m, float(x_vals[-1]))
    return float(np.interp(x_eval, x_vals, y_vals))


def diagram_cache_fingerprint(
    case: str,
    L_uls: float,
    p_uls: dict,
    L_sls: float,
    p_sls: dict,
) -> str:
    """Stable hash of beam case + ULS/SLS load/support inputs (invalidates crack moment cache)."""
    import hashlib
    import json

    def _pack(L: float, p: dict) -> dict:
        p = dict(p or {})
        keys = (
            "support_condition",
            "beam_system_mode",
            "node_positions_m",
            "support_types",
            "w",
            "P",
            "point_loads",
            "udl_loads",
            "L_main",
            "a_overhang",
            "a",
            "a_udl",
            "a_cant",
        )
        return {"L": round(float(L), 9), **{k: p.get(k) for k in keys}}

    blob = {
        "case": str(case),
        "uls": _pack(L_uls, p_uls),
        "sls": _pack(L_sls, p_sls),
    }
    return hashlib.sha256(
        json.dumps(blob, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()[:48]


def _compute_diagram_arrays(case_name: str, span_L: float, p: dict):
    """
    Compatibility wrapper: builds a BeamModel from the legacy named case, runs the shared
    determinate solver, and returns the same tuple shape as the original implementation.
    """
    params = dict(p or {})
    L = float(span_L)
    if str(params.get("beam_system_mode", "Single span")) == "Multi-span":
        node_positions = [float(v) for v in (params.get("node_positions_m") or [0.0, L])]
        support_types = [str(v) for v in (params.get("support_types") or ["Pinned", "Pinned"])]
        solved = solve_beam_structure(
            node_positions_m=node_positions,
            support_types=support_types,
            point_loads=list(params.get("point_loads") or []),
            udl_loads=list(params.get("udl_loads") or []),
            n_points_per_span=120,
        )
        x = np.asarray(solved["x"], dtype=float)
        V = np.asarray(solved["V"], dtype=float)
        M = np.asarray(solved["M"], dtype=float)
        beam_length = float(node_positions[-1] - node_positions[0]) if len(node_positions) > 1 else L
        results_local = {
            "support_positions": list(solved.get("support_positions", node_positions)),
            "support_types": list(support_types),
            "reactions": dict(solved.get("reactions", {})),
            "analysis_note": "continuous multi-span beam solved via stiffness-based beam-analysis backend",
            "beam_system_mode": "Multi-span",
            "solver_metadata": dict(solved.get("metadata", {})),
        }
        return x, V, M, beam_length, results_local

    support_condition = str(params.get("support_condition", "Simply supported")).replace("-", "–")
    fixed_end_conditions = {"Fixed–Pinned", "Pinned–Fixed", "Fixed–Fixed"}
    is_overhang = case_name == "Overhanging beam – right overhang with point load at free end"
    is_cantilever = case_name.startswith("Cantilever")
    is_single_span = not is_overhang

    if is_single_span and support_condition in fixed_end_conditions:
        point_loads = list(params.get("point_loads") or [])
        if not point_loads and "P" in params:
            if case_name == "Simple beam – point load at centre":
                point_loads = [{"x_m": L / 2.0, "P_kN": float(params.get("P", 0.0) or 0.0)}]
            elif case_name == "Simple beam – point load at distance a from left":
                a_local = _clamp_x(float(params.get("a", L / 3.0) or (L / 3.0)), L)
                point_loads = [{"x_m": a_local, "P_kN": float(params.get("P", 0.0) or 0.0)}]
            elif case_name == "Cantilever – point load at free end":
                point_loads = [{"x_m": L, "P_kN": float(params.get("P", 0.0) or 0.0)}]
            elif case_name == "Cantilever – point load at distance a from fixed end":
                a_local = _clamp_x(float(params.get("a_cant", L / 2.0) or (L / 2.0)), L)
                point_loads = [{"x_m": a_local, "P_kN": float(params.get("P", 0.0) or 0.0)}]

        udl_loads = list(params.get("udl_loads") or [])
        if not udl_loads and "w" in params:
            w_local = float(params.get("w", 0.0) or 0.0)
            if case_name in ["Simple beam – UDL over entire span", "Cantilever – UDL over entire span"]:
                udl_loads = [{"x_start_m": 0.0, "x_end_m": L, "w_kN_per_m": w_local}]
            elif case_name == "Simple beam – partial UDL from left (length a)":
                a_udl = _clamp_x(float(params.get("a_udl", L / 2.0) or (L / 2.0)), L)
                udl_loads = [{"x_start_m": 0.0, "x_end_m": a_udl, "w_kN_per_m": w_local}]

        solved = solve_single_span_beam(
            L_m=L,
            support_condition=support_condition,
            point_loads=point_loads,
            udl_loads=udl_loads,
            n_points=400,
        )
        x = np.asarray(solved["x"], dtype=float)
        V = np.asarray(solved["V"], dtype=float)
        M = np.asarray(solved["M"], dtype=float)
        reactions = solved.get("reactions", {})
        results_local = {
            "R1": float(reactions.get("R_left", 0.0)),
            "R2": float(reactions.get("R_right", 0.0)),
            "M_left": float(reactions.get("M_left", 0.0)),
            "M_right": float(reactions.get("M_right", 0.0)),
            "reactions": {
                "R1": float(reactions.get("R_left", 0.0)),
                "R2": float(reactions.get("R_right", 0.0)),
                "M1": float(reactions.get("M_left", 0.0)),
                "M2": float(reactions.get("M_right", 0.0)),
            },
            "support_positions": list(solved.get("support_positions", [0.0, L])),
            "support_condition": support_condition,
            "analysis_note": "statically indeterminate solved via beam-analysis backend",
            "solver_metadata": dict(solved.get("metadata", {})),
        }
        return x, V, M, L, results_local

    if is_cantilever:
        params["support_condition"] = "Fixed–Free"

    model = build_beam_model_from_legacy_case(case_name, L, params)
    result = solve_beam_model(model, n_points=400)
    x = np.asarray(result.x, dtype=float)
    V = np.asarray(result.V, dtype=float)
    M = np.asarray(result.M, dtype=float)
    beam_length = float(model.length_m)
    results_local = legacy_results_local_from_result(case_name, model, result)
    if is_overhang:
        results_local["support_positions"] = [0.0, float(params.get("L_main", L))]
    elif case_name.startswith("Cantilever"):
        results_local["support_positions"] = [0.0]
    else:
        results_local["support_positions"] = [0.0, beam_length]
    results_local["support_condition"] = str(params.get("support_condition", support_condition))
    return x, V, M, beam_length, results_local


def _compute_actions_at_x(case, L, params, x_m, w, P):
    local_params = dict(params)
    if w is not None:
        local_params["w"] = float(w)
    if P is not None:
        local_params["P"] = float(P)
    x_vals, V_vals, M_vals, beam_length, _ = _compute_diagram_arrays(case, L, local_params)
    x_eval = _clamp_x(x_m, beam_length)
    return {
        "x_m": x_eval,
        "V_kN": _interp_at_x(x_vals, V_vals, x_eval),
        "M_kNm": _interp_at_x(x_vals, M_vals, x_eval),
        "beam_length_m": beam_length,
    }


# ---------------------------------------------------
# Helper: derivation text inside expander
# ---------------------------------------------------
def render_derivation(case, L, params, results):
    """
    Writes full equilibrium derivation for each case.
    Uses st.latex and st.markdown.
    """
    with st.expander("Show full equilibrium derivation (reactions, V(x), M(x))"):
        st.markdown("### Step 1 – Support conditions")

        if case.startswith("Simple beam"):
            st.markdown("- Left support: **pinned**  \n- Right support: **pinned**")
        elif case.startswith("Cantilever"):
            st.markdown("- Left support: **fixed**  \n- Right end: **free**")
        elif case == "Overhanging beam – right overhang with point load at free end":
            st.markdown(
                "- Left support A: **pinned**  \n"
                "- Right support B: **pinned** (internal)  \n"
                "- Right overhang end: **free**"
            )

        st.markdown("### Step 2 – Reaction forces")

        if case == "Simple beam – UDL over entire span":
            w = params.get("w", 0.0)
            R = results.get("R", w * L / 2.0)
            st.latex(r"\Sigma M_A = 0: \quad R_2 L - wL \cdot \frac{L}{2} = 0")
            st.latex(r"R_2 = \frac{wL}{2}")
            st.latex(r"\Sigma V = 0: \quad R_1 + R_2 - wL = 0")
            st.latex(r"R_1 = \frac{wL}{2}")
            st.markdown(f"Numerically, R₁ = R₂ = `{R:.3g}` kN")

        elif case == "Simple beam – partial UDL from left (length a)":
            w = params.get("w", 0.0)
            a = params["a_udl"]
            a = max(0.0, min(a, L))
            R1 = results.get("R1", 0.0)
            R2 = results.get("R2", 0.0)
            st.latex(r"w \text{ over } 0 \le x \le a,\quad 0 \le a \le L")
            st.latex(r"\Sigma M_A = 0: \quad R_2 L - w a \cdot \frac{a}{2} = 0")
            st.latex(r"R_2 = \dfrac{w a^2}{2L}")
            st.latex(r"\Sigma V = 0: \quad R_1 + R_2 - w a = 0")
            st.latex(r"R_1 = w a - \dfrac{w a^2}{2L}")
            st.markdown(
                f"With L = `{L:.3g}` m, a = `{a:.3g}` m, w = `{w:.3g}` kN/m:"
            )
            st.markdown(f"- R₁ = `{R1:.3g}` kN  \n- R₂ = `{R2:.3g}` kN")

        elif case == "Simple beam – point load at centre":
            P = params.get("P", 0.0)
            R1 = results["R1"]
            st.latex(r"a = \frac{L}{2}")
            st.latex(r"\Sigma M_A = 0: \quad R_2 L - P \cdot \frac{L}{2} = 0")
            st.latex(r"R_2 = \frac{P}{2}")
            st.latex(r"\Sigma V = 0: \quad R_1 + R_2 - P = 0")
            st.latex(r"R_1 = \frac{P}{2}")
            st.markdown(f"With P = `{P:.3g}` kN: R₁ = R₂ = `{R1:.3g}` kN")

        elif case == "Simple beam – point load at distance a from left":
            P = params.get("P", 0.0)
            a = float(params["a"])
            b = L - a
            R1 = results.get("R1", 0.0)
            R2 = results.get("R2", 0.0)
            st.latex(r"a = a,\quad b = L-a")
            st.latex(r"\Sigma M_A = 0: \quad R_2 L - P a = 0")
            st.latex(r"R_2 = \dfrac{Pa}{L}")
            st.latex(r"\Sigma V = 0: \quad R_1 + R_2 - P = 0")
            st.latex(r"R_1 = \dfrac{Pb}{L}")
            st.markdown(
                f"With L = `{L:.3g}` m, a = `{a:.3g}` m, b = `{b:.3g}` m, P = `{P:.3g}` kN:"
            )
            st.markdown(f"- R₁ = `{R1:.3g}` kN  \n- R₂ = `{R2:.3g}` kN")

        elif case == "Cantilever – point load at free end":
            P = params.get("P", 0.0)
            st.latex(r"\Sigma V = 0: \quad V_{\text{fixed}} - P = 0")
            st.latex(r"V_{\text{fixed}} = P")
            st.latex(r"\Sigma M_{\text{fixed}} = 0: \quad M_{\text{fixed}} - P L = 0")
            st.latex(r"M_{\text{fixed}} = P L")
            st.markdown(
                f"At the fixed support, shear = `{P:.3g}` kN (up), "
                f"hogging moment = `{P*L:.3g}` kNm."
            )

        elif case == "Cantilever – point load at distance a from fixed end":
            P = params.get("P", 0.0)
            a = params["a_cant"]
            a = max(0.0, min(a, L))
            st.latex(r"\Sigma V = 0: \quad V_{\text{fixed}} - P = 0")
            st.latex(r"V_{\text{fixed}} = P")
            st.latex(r"\Sigma M_{\text{fixed}} = 0: \quad M_{\text{fixed}} - P a = 0")
            st.latex(r"M_{\text{fixed}} = P a")
            st.markdown(
                f"At the fixed support, shear = `{P:.3g}` kN (up), "
                f"hogging moment = `{P*a:.3g}` kNm."
            )

        elif case == "Cantilever – UDL over entire span":
            w = params.get("w", 0.0)
            st.latex(r"\Sigma V = 0: \quad V_{\text{fixed}} - wL = 0")
            st.latex(r"V_{\text{fixed}} = wL")
            st.latex(
                r"\Sigma M_{\text{fixed}} = 0: \quad "
                r"M_{\text{fixed}} - wL \cdot \frac{L}{2} = 0"
            )
            st.latex(r"M_{\text{fixed}} = \frac{wL^2}{2}")
            st.markdown(
                f"At the fixed support, shear = `{w*L:.3g}` kN (up), "
                f"hogging moment = `{0.5*w*L**2:.3g}` kNm."
            )

        elif case == "Overhanging beam – right overhang with point load at free end":
            P = params.get("P", 0.0)
            L_main = params["L_main"]
            a_over = params["a_overhang"]
            RA = results.get("RA", 0.0)
            RB = results.get("RB", 0.0)
            st.latex(r"L = \text{distance between supports}, \quad a = \text{overhang}")
            st.latex(r"\Sigma M_A = 0: \quad R_B L - P(L+a) = 0")
            st.latex(r"R_B = \dfrac{P(L+a)}{L}")
            st.latex(r"\Sigma V = 0: \quad R_A + R_B - P = 0")
            st.latex(r"R_A = P - R_B = -\dfrac{Pa}{L}")
            st.markdown(
                f"With L = `{L_main:.3g}` m, a = `{a_over:.3g}` m, P = `{P:.3g}` kN:"
            )
            st.markdown(f"- R_A = `{RA:.3g}` kN (down)  \n- R_B = `{RB:.3g}` kN (up)")

        st.markdown("### Step 3 – Shear function \(V(x)\)")

        if case == "Simple beam – UDL over entire span":
            st.latex(
                r"V(x) = R_1 - wx = \frac{wL}{2} - wx,\quad 0 \le x \le L"
            )

        elif case == "Simple beam – partial UDL from left (length a)":
            st.latex(
                r"V(x) = \begin{cases}"
                r"R_1 - w x & 0 \le x \le a \\"
                r"R_1 - w a & a \le x \le L"
                r"\end{cases}"
            )

        elif case == "Simple beam – point load at centre":
            st.latex(
                r"a = \frac{L}{2}"
            )
            st.latex(
                r"V(x) = \begin{cases}"
                r"R_1 & 0 \le x < a \\"
                r"R_1 - P & a < x \le L"
                r"\end{cases}"
            )

        elif case == "Simple beam – point load at distance a from left":
            st.latex(
                r"V(x) = \begin{cases}"
                r"R_1 & 0 \le x < a \\"
                r"R_1 - P & a < x \le L"
                r"\end{cases}"
            )

        elif case == "Cantilever – point load at free end":
            st.latex(
                r"V(x) = -P,\quad 0 \le x \le L"
            )

        elif case == "Cantilever – point load at distance a from fixed end":
            st.latex(
                r"V(x) = \begin{cases}"
                r"-P & 0 \le x \le a \\"
                r"0 & a \le x \le L"
                r"\end{cases}"
            )

        elif case == "Cantilever – UDL over entire span":
            st.latex(
                r"V(x) = -w(L - x),\quad 0 \le x \le L"
            )

        elif case == "Overhanging beam – right overhang with point load at free end":
            st.latex(
                r"V(x) = \begin{cases}"
                r"R_A & 0 \le x < L \\"
                r"R_A + R_B & L < x \le L+a"
                r"\end{cases}"
            )

        st.markdown("### Step 4 – Moment function \(M(x)\)")

        if case == "Simple beam – UDL over entire span":
            st.latex(
                r"M(x) = R_1 x - \frac{w x^2}{2},\quad 0 \le x \le L"
            )
            st.latex(
                r"M_{\max} = \frac{wL^2}{8} \text{ at } x = \frac{L}{2}"
            )

        elif case == "Simple beam – partial UDL from left (length a)":
            st.latex(
                r"M(x) = \begin{cases}"
                r"R_1 x - \dfrac{w x^2}{2} & 0 \le x \le a \\[6pt]"
                r"R_1 x - w a\left(x - \dfrac{a}{2}\right) & a \le x \le L"
                r"\end{cases}"
            )

        elif case == "Simple beam – point load at centre":
            st.latex(
                r"M(x) = \begin{cases}"
                r"R_1 x & 0 \le x \le a \\"
                r"R_1 x - P(x-a) & a \le x \le L"
                r"\end{cases}"
            )
            st.latex(
                r"M_{\max} = \frac{PL}{4} \text{ at } x = \frac{L}{2}"
            )

        elif case == "Simple beam – point load at distance a from left":
            st.latex(
                r"M(x) = \begin{cases}"
                r"R_1 x & 0 \le x \le a \\"
                r"R_1 x - P(x-a) & a \le x \le L"
                r"\end{cases}"
            )
            st.latex(
                r"M_{\max} = R_1 a = \dfrac{Pab}{L} \text{ at } x = a"
            )

        elif case == "Cantilever – point load at free end":
            st.latex(
                r"M(x) = -P(L-x),\quad 0 \le x \le L"
            )
            st.latex(r"M_{\max} = PL \text{ (hogging at fixed end)}")

        elif case == "Cantilever – point load at distance a from fixed end":
            st.latex(
                r"M(x) = \begin{cases}"
                r"-P(a-x) & 0 \le x \le a \\"
                r"0 & a \le x \le L"
                r"\end{cases}"
            )
            st.latex(r"M_{\max} = P a \text{ at the fixed end}")

        elif case == "Cantilever – UDL over entire span":
            st.latex(
                r"M(x) = -\frac{w}{2}(L-x)^2,\quad 0 \le x \le L"
            )
            st.latex(r"M_{\max} = \frac{wL^2}{2} \text{ (hogging at fixed end)}")

        elif case == "Overhanging beam – right overhang with point load at free end":
            st.latex(
                r"M(x) = \begin{cases}"
                r"R_A x & 0 \le x \le L \\"
                r"R_A x + R_B(x-L) & L \le x \le L+a"
                r"\end{cases}"
            )
            st.latex(
                r"M_B = R_A L = -Pa \text{ (hogging at support B)}"
            )


# ---------------------------------------------------
# MAIN PAGE RENDER FUNCTION
# ---------------------------------------------------
def render_sfd_bmd_page():
    """
    Standalone SFD/BMD teaching page in the beam app.

    - Same visual style as other pages (title, blurb, summary placeholder)
    - No sidebar, no set_page_config
    - Publishes span + |M|max + |V|max to results:
          sfd_case
          sfd_Mmax_abs_kNm
          sfd_Vmax_abs_kN
    """

    # Handle cross-page navigation from Inputs page
    from jump_nav import get_jump_uid
    get_jump_uid()

    apply_global_widget_css()
    apply_result_page_css()
    apply_calcbox_css()
    
    # Override global widget max-width so selectboxes can fill their column
    st.markdown(
        """
        <style>
        /* Override global widget max-width so selectboxes can fill their column */
        body div[data-testid="stSelectbox"],
        body div[data-testid="stSelectbox"] > div {
            width: 100% !important;
            max-width: none !important;
        }

        body div[data-testid="stSelectbox"] div[data-baseweb="select"] {
            width: 100% !important;
            max-width: none !important;
        }

        /* Let selected option text wrap instead of ellipsis */
        body div[data-testid="stSelectbox"] div[data-baseweb="select"] span {
            white-space: normal !important;
            overflow: visible !important;
            text-overflow: clip !important;
            line-height: 1.2em !important;
        }

        /* Ensure nested elements also allow wrapping */
        body div[data-testid="stSelectbox"] div[data-baseweb="select"] * {
            white-space: normal !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
    
    sync_callbacks = get_sync_callbacks()

    # Define stable UIDs for each calc box (step)
    EQ_SLS_UID = {
        "step0": "eq_sls_step0_load_combo",
        "step1": "eq_sls_step1_support",
        "step2": "eq_sls_step2_reactions",
        "step2a": "eq_sls_step2a_model_restraints",
        "step2b": "eq_sls_step2b_element_stiffness",
        "step2c": "eq_sls_step2c_equivalent_nodal_loads",
        "step2d": "eq_sls_step2d_global_stiffness",
        "step2e": "eq_sls_step2e_solved_dofs",
        "step2f": "eq_sls_step2f_recovered_actions",
        "step3": "eq_sls_step3_shear_vx",
        "step4": "eq_sls_step4_moment_mx",
    }

    def _render_sfd_bmd_explainer() -> None:
        st.markdown(
            """
This module generates the **load diagram**, **shear force diagram (SFD)** and **bending moment diagram (BMD)** for statically determinate beams.

Adjust the **support condition, span, and applied loads** to see how they influence the resulting shear forces and bending moments.

Loads are automatically converted into **ULS and SLS combinations**, allowing you to inspect both **design actions** and **service actions** with full equilibrium derivations.

**Sign convention**

• **Shear V(x):** upward positive  
• **Moment M(x):** sagging positive  
  (cantilever hogging appears negative)
"""
        )

    render_result_page_title("Beam Actions & Diagrams (SFD / BMD)")

    # App-wide design-action source (same canonical keys as Inputs page)
    _LEGACY_ACTIONS_MANUAL = "Manual design actions (inputs below)"
    _LEGACY_ACTIONS_DESIGN = "Teaching SFD/BMD page (|M|max, |V|max)"

    def _norm_actions_source_label(raw) -> str:
        s = str(raw or _LEGACY_ACTIONS_MANUAL)
        if s == "Manual design actions":
            return _LEGACY_ACTIONS_MANUAL
        if s == "Calculated design actions (from SFD/BMD)":
            return _LEGACY_ACTIONS_DESIGN
        return s

    _src_canon = _norm_actions_source_label(st.session_state.get("actions_source", _LEGACY_ACTIONS_MANUAL))
    _wk_sfd_actions = "inputs_use_calculated_actions"
    _beam_page_selected = _src_canon == _LEGACY_ACTIONS_DESIGN
    if _wk_sfd_actions not in st.session_state:
        st.session_state[_wk_sfd_actions] = _beam_page_selected

    st.caption("Design-action source (synced with **Inputs → Design Actions**)")
    _use_beam_page = st.toggle(
        "Use design actions from this page (Beam Actions & Diagrams)",
        key=_wk_sfd_actions,
        help=(
            "When enabled, ULS/SLS demands follow this beam model and stay linked to the same toggle on the Inputs page. "
            "When disabled, demands follow manual actions entered on Inputs."
        ),
    )
    _mapped_src = _LEGACY_ACTIONS_DESIGN if _use_beam_page else _LEGACY_ACTIONS_MANUAL
    _mapped_mode = "design" if _use_beam_page else "manual"
    if (
        _norm_actions_source_label(st.session_state.get("actions_source")) != _mapped_src
        or str(st.session_state.get("actions_mode", "manual") or "manual") != _mapped_mode
    ):
        st.session_state["actions_source"] = _mapped_src
        st.session_state["actions_mode"] = _mapped_mode
        try:
            set_shared("actions_source", _mapped_src, source="sfd_bmd:actions_toggle")
            set_shared("actions_mode", _mapped_mode, source="sfd_bmd:actions_toggle")
        except Exception:
            pass
        st.rerun()

    summary_placeholder = st.empty()
    st.divider()
    # =========================================================
    # BEAM LOADING CONDITION
    # =========================================================
    load_toggle_key = "design_loads_edit_toggle"
    def _on_design_load_mode_change() -> None:
        use_sls_now = bool(st.session_state.get(load_toggle_key, False))
        mode_now = "SLS" if use_sls_now else "ULS"
        st.session_state["loads_edit_mode"] = mode_now
        try:
            set_shared("loads_edit_toggle", use_sls_now, source=f"callback:{load_toggle_key}")
            set_shared("loads_edit_mode", mode_now, source=f"callback:{load_toggle_key}")
        except Exception:
            pass

    heading_l, heading_r = st.columns([6, 2], gap="small")
    with heading_l:
        render_section_title("Beam loading condition")
    with heading_r:
        controls_info, controls_toggle = st.columns([1, 5], gap="small")
        with controls_info:
            with info_i_button(help_text="Beam loading inputs define the response shown in the diagrams below."):
                st.markdown("Adjust support conditions, span, and loads to update the load, SFD, and BMD plots.")
        with controls_toggle:
            use_sls = st.toggle(
                "Diagram/action state: SLS",
                key=load_toggle_key,
                on_change=_on_design_load_mode_change,
                help="Toggle which limit state response to display (ULS or SLS). Base loads remain unchanged.",
            )
            mode_from_toggle = "SLS" if bool(use_sls) else "ULS"
            st.session_state["loads_edit_toggle"] = bool(use_sls)
            st.session_state["loads_edit_mode"] = mode_from_toggle
            try:
                set_shared("loads_edit_toggle", bool(use_sls), source="sfd_bmd_page:load_mode_toggle")
                set_shared("loads_edit_mode", mode_from_toggle, source="sfd_bmd_page:load_mode_toggle")
            except Exception:
                pass

    # Standardized row grid widths (label col + input col)
    ROW_COLS = [1.0, 3.0]
    
    # Force all inputs in the input column to start at the same left edge
    st.markdown("""
    <style>
    /* Make every widget in the loading section fill its column starting at the same left edge */
    .loading-grid [data-testid="stSelectbox"],
    .loading-grid [data-testid="stSelectbox"] > div,
    .loading-grid [data-testid="stSelectbox"] div[data-baseweb="select"],
    .loading-grid [data-testid="stNumberInput"],
    .loading-grid [data-testid="stNumberInput"] > div {
      width: 100% !important;
      max-width: 100% !important;
      margin-left: 0 !important;
    }

    /* Cap loading selectbox size but keep left edge aligned */
    .loading-grid .loading-select [data-testid="stSelectbox"],
    .loading-grid .loading-select [data-testid="stSelectbox"] > div,
    .loading-grid .loading-select div[data-baseweb="select"] {
      width: 100% !important;
      max-width: 620px !important;
    }
    </style>
    """, unsafe_allow_html=True)
    
    # Wrap the entire loading section in a container
    st.markdown("<div class='loading-grid'>", unsafe_allow_html=True)

    beam_system_mode = render_inline_select_row(
        "Beam system mode",
        key="sfd_beam_system_mode",
        options=["Single span", "Multi-span"],
        index=0,
        sync_callbacks=sync_callbacks,
        help_text="Choose single-span legacy workflow or multi-span continuous beam workflow.",
    )

    # Loading condition dropdown as a row (label left, widget right, hover help)
    LOADING_OPTIONS = [
        "Simple beam – UDL over entire span",
        "Simple beam – partial UDL from left (length a)",
        "Simple beam – multiple point loads",
        "Cantilever – multiple point loads",
        "Cantilever – UDL over entire span",
        "Overhanging beam – right overhang with point load at free end",
    ]
    
    def _on_design_span_change() -> None:
        span_sync_callback = sync_callbacks.get("sfd_L_m")
        if span_sync_callback:
            span_sync_callback()
        try:
            span_m = max(0.1, float(st.session_state.get("sfd_L_m", 0.1)))
        except (TypeError, ValueError):
            span_m = 0.1
        set_shared("L", span_m * 1000.0, source="callback:sfd_L_m")
    
    load_case = "Multi-span continuous beam"
    support_condition = "Multi-span continuous"
    is_overhang_case = False
    is_cantilever_case = False

    if beam_system_mode == "Single span":
        # Get current selection index
        current_case = st.session_state.get("load_case", st.session_state.get("sfd_case", LOADING_OPTIONS[0]))
        loading_index = LOADING_OPTIONS.index(current_case) if current_case in LOADING_OPTIONS else 0
        load_case = render_inline_select_row(
            "Loading condition",
            key="load_case",
            options=LOADING_OPTIONS,
            index=loading_index,
            sync_callbacks=sync_callbacks,
            help_text=(
                "Choose the beam support and load case used to derive reactions, SFD and BMD. "
                "This is the single source of truth for bending and shear demand used elsewhere in the app."
            ),
        )
        is_overhang_case = load_case == "Overhanging beam – right overhang with point load at free end"
        is_cantilever_case = load_case.startswith("Cantilever")
        support_condition = "Simply supported"
        if not is_overhang_case:
            if is_cantilever_case:
                if st.session_state.get("sfd_support_condition") != "Fixed–Free":
                    st.session_state["sfd_support_condition"] = "Fixed–Free"
                support_condition = render_inline_select_row(
                    "Support condition",
                    key="sfd_support_condition",
                    options=["Fixed–Free"],
                    index=0,
                    sync_callbacks=sync_callbacks,
                    disabled=True,
                    help_text="Cantilever load families are analysed as fixed at left and free at right.",
                )
            else:
                support_opts = [
                    "Simply supported",
                    "Pinned–Pinned",
                    "Fixed–Pinned",
                    "Pinned–Fixed",
                    "Fixed–Fixed",
                ]
                if st.session_state.get("sfd_support_condition") not in support_opts:
                    st.session_state["sfd_support_condition"] = support_opts[0]
                current_support = str(st.session_state.get("sfd_support_condition", support_opts[0]) or support_opts[0])
                default_support = current_support if current_support in support_opts else support_opts[0]
                support_condition = render_inline_select_row(
                    "Support condition",
                    key="sfd_support_condition",
                    options=support_opts,
                    index=support_opts.index(default_support),
                    sync_callbacks=sync_callbacks,
                    help_text="Support condition used for the single-span beam analysis model.",
                )

    if beam_system_mode == "Single span":
        _sync_design_shared_value(
            "design_support_condition",
            support_condition,
            source="sfd_bmd_page:single_span_support_condition",
        )

    design_governing = is_design_governing()
    if design_governing:
        # Do not write defl_support_type directly from this page.
        # Deflection/Inputs resolve support from design model fields
        # (sfd_beam_system_mode, sfd_case, sfd_support_condition, spans/supports).
        # Direct writes here were causing router reverts and snap-back loops.
        pass
    else:
        pass

    node_positions_multi: list[float] | None = None
    support_types_multi: list[str] | None = None
    if beam_system_mode == "Single span":
        # -------- span as editable widget (canonical L in mm) --------
        L_seed = max(0.1, float(get_param("L", 3000.0)) / 1000.0)
        L = render_inline_number_row(
            "Span L (m)",
            key="sfd_L_m",
            value=L_seed,
            min_value=0.1,
            step=0.5,
            format="%.2f",
            help_text="Beam span used for reactions, SFD and BMD.",
            on_change=_on_design_span_change,
        )
        L_mm_new = float(L) * 1000.0
        # Always read from shared span (single source of truth, in mm)
        L = float(get_param("L", L_mm_new)) / 1000.0
    else:
        if "sfd_span_count" not in st.session_state:
            st.session_state["sfd_span_count"] = 2.0
        else:
            st.session_state["sfd_span_count"] = float(st.session_state.get("sfd_span_count", 2.0) or 2.0)
        n_spans = int(
            render_inline_number_row(
                "Number of spans",
                key="sfd_span_count",
                value=float(st.session_state.get("sfd_span_count", 2.0)),
                min_value=2.0,
                max_value=5.0,
                step=1.0,
                format="%.0f",
                sync_callbacks=sync_callbacks,
            )
        )
        span_lengths: list[float] = []
        for i in range(1, n_spans + 1):
            len_i = float(
                render_inline_number_row(
                    f"Span {i} length (m)",
                    key=f"sfd_span_len_{i}",
                    value=float(st.session_state.get(f"sfd_span_len_{i}", 4.0)),
                    min_value=0.2,
                    step=0.1,
                    format="%.2f",
                    sync_callbacks=sync_callbacks,
                )
            )
            span_lengths.append(max(0.2, len_i))
        node_positions_multi = [0.0]
        for li in span_lengths:
            node_positions_multi.append(node_positions_multi[-1] + float(li))
        L = float(node_positions_multi[-1])

        support_types_multi = []
        for i in range(1, n_spans + 2):
            if i == 1:
                opts = ["Pinned", "Fixed"]
            elif i == n_spans + 1:
                opts = ["Pinned", "Roller", "Fixed"]
            else:
                opts = ["Pinned", "Roller"]
            key = f"sfd_support_type_{i}"
            cur = str(st.session_state.get(key, opts[0]) or opts[0])
            if cur not in opts:
                st.session_state[key] = opts[0]
                cur = opts[0]
            support_value = render_inline_select_row(
                f"Support {i}",
                key=key,
                options=opts,
                index=opts.index(cur),
                sync_callbacks=sync_callbacks,
            )
            support_types_multi.append(support_value)
            _sync_design_shared_value(
                f"design_support_type_{i}",
                support_value,
                source=f"sfd_bmd_page:multi_span_support_{i}",
            )

    # Track load combos for later selection
    w_sls = None
    w_uls = None
    P_sls = None
    P_uls = None
    P_sls_total = None
    P_uls_total = None
    point_loads_sls = None
    point_loads_uls = None
    base_g = None
    base_q = None
    base_psi = None
    base_G = None
    base_Q = None
    base_psi_point = None
    gamma_g = 1.2
    gamma_q = 1.5

    # Conditional loads based on load case type
    params: dict = {}
    results_local: dict = {}
    a = None
    if beam_system_mode == "Multi-span":
        params["beam_system_mode"] = "Multi-span"
        params["node_positions_m"] = list(node_positions_multi or [0.0, float(L)])
        params["support_types"] = list(support_types_multi or ["Pinned", "Pinned"])
        params["support_positions"] = list(params["node_positions_m"])

        psi_point = float(
            render_inline_number_row(
                "Sustained factor ψ_s for point load",
                key="load_psi_point",
                value=float(st.session_state.get("load_psi_point", get_param("psi_point", 0.4))),
                min_value=0.0,
                max_value=1.0,
                step=0.05,
                format="%.2f",
                sync_callbacks=None,
            )
        )
        psi_udl = float(
            render_inline_number_row(
                "Sustained factor ψ_s for UDL",
                key="load_psi_udl",
                value=float(st.session_state.get("load_psi_udl", get_param("psi_udl", 0.4))),
                min_value=0.0,
                max_value=1.0,
                step=0.05,
                format="%.2f",
                sync_callbacks=None,
            )
        )
        base_psi_point = psi_point
        base_psi = psi_udl

        if "sfd_ms_point_count" not in st.session_state:
            st.session_state["sfd_ms_point_count"] = 2.0
        else:
            st.session_state["sfd_ms_point_count"] = float(st.session_state.get("sfd_ms_point_count", 2.0) or 2.0)
        n_point = int(
            render_inline_number_row(
                "Number of point loads",
                key="sfd_ms_point_count",
                value=float(st.session_state.get("sfd_ms_point_count", 2.0)),
                min_value=0.0,
                max_value=8.0,
                step=1.0,
                format="%.0f",
                sync_callbacks=sync_callbacks,
            )
        )
        ms_rows = []
        for i in range(1, n_point + 1):
            g_i = float(
                render_inline_number_row(
                    f"Point {i}: dead load G_{i} (kN)",
                    key=f"load_ms_G_{i}",
                    value=float(st.session_state.get(f"load_ms_G_{i}", 30.0)),
                    min_value=0.0,
                    step=5.0,
                    format="%.2f",
                    sync_callbacks=sync_callbacks,
                )
            )
            q_i = float(
                render_inline_number_row(
                    f"Point {i}: live load Q_{i} (kN)",
                    key=f"load_ms_Q_{i}",
                    value=float(st.session_state.get(f"load_ms_Q_{i}", 20.0)),
                    min_value=0.0,
                    step=5.0,
                    format="%.2f",
                    sync_callbacks=sync_callbacks,
                )
            )
            x_i_raw = float(
                render_inline_number_row(
                    f"Point {i}: position x_{i} (m)",
                    key=f"load_ms_x_{i}",
                    value=float(st.session_state.get(f"load_ms_x_{i}", float(L) * i / max(1, n_point + 1))),
                    min_value=0.0,
                    max_value=float(L),
                    step=0.1,
                    format="%.2f",
                    sync_callbacks=sync_callbacks,
                )
            )
            x_i = _clamp_x(x_i_raw, float(L))
            ms_rows.append(
                {
                    "x_m": x_i,
                    "G": g_i,
                    "Q": q_i,
                    "P_sls": g_i + psi_point * q_i,
                    "P_uls": gamma_g * g_i + gamma_q * q_i,
                }
            )

        if "sfd_ms_udl_count" not in st.session_state:
            st.session_state["sfd_ms_udl_count"] = 1.0
        else:
            st.session_state["sfd_ms_udl_count"] = float(st.session_state.get("sfd_ms_udl_count", 1.0) or 1.0)
        n_udl = int(
            render_inline_number_row(
                "Number of UDL segments",
                key="sfd_ms_udl_count",
                value=float(st.session_state.get("sfd_ms_udl_count", 1.0)),
                min_value=0.0,
                max_value=8.0,
                step=1.0,
                format="%.0f",
                sync_callbacks=sync_callbacks,
            )
        )
        ms_udl_rows = []
        for i in range(1, n_udl + 1):
            g_i = float(
                render_inline_number_row(
                    f"UDL {i}: dead g_{i} (kN/m)",
                    key=f"load_ms_g_{i}",
                    value=float(st.session_state.get(f"load_ms_g_{i}", 5.0)),
                    min_value=0.0,
                    step=0.5,
                    format="%.2f",
                    sync_callbacks=sync_callbacks,
                )
            )
            q_i = float(
                render_inline_number_row(
                    f"UDL {i}: live q_{i} (kN/m)",
                    key=f"load_ms_q_{i}",
                    value=float(st.session_state.get(f"load_ms_q_{i}", 3.0)),
                    min_value=0.0,
                    step=0.5,
                    format="%.2f",
                    sync_callbacks=sync_callbacks,
                )
            )
            x0_raw = float(
                render_inline_number_row(
                    f"UDL {i}: start x_start_{i} (m)",
                    key=f"load_ms_x0_{i}",
                    value=float(st.session_state.get(f"load_ms_x0_{i}", 0.0)),
                    min_value=0.0,
                    max_value=float(L),
                    step=0.1,
                    format="%.2f",
                    sync_callbacks=sync_callbacks,
                )
            )
            x1_raw = float(
                render_inline_number_row(
                    f"UDL {i}: end x_end_{i} (m)",
                    key=f"load_ms_x1_{i}",
                    value=float(st.session_state.get(f"load_ms_x1_{i}", float(L))),
                    min_value=0.0,
                    max_value=float(L),
                    step=0.1,
                    format="%.2f",
                    sync_callbacks=sync_callbacks,
                )
            )
            x0 = _clamp_x(min(x0_raw, x1_raw), float(L))
            x1 = _clamp_x(max(x0_raw, x1_raw), float(L))
            if x1 <= x0:
                continue
            ms_udl_rows.append(
                {
                    "x_start_m": x0,
                    "x_end_m": x1,
                    "g": g_i,
                    "q": q_i,
                    "w_sls": g_i + psi_udl * q_i,
                    "w_uls": gamma_g * g_i + gamma_q * q_i,
                }
            )

        ms_rows = sorted(ms_rows, key=lambda r: r["x_m"])
        ms_udl_rows = sorted(ms_udl_rows, key=lambda r: r["x_start_m"])
        point_loads_sls = [{"x_m": r["x_m"], "P_kN": r["P_sls"]} for r in ms_rows]
        point_loads_uls = [{"x_m": r["x_m"], "P_kN": r["P_uls"]} for r in ms_rows]
        params["point_loads_preview"] = list(point_loads_sls)
        params["udl_loads_preview"] = [{"x_start_m": r["x_start_m"], "x_end_m": r["x_end_m"], "w_kN_per_m": r["w_sls"]} for r in ms_udl_rows]
        params["udl_loads_sls"] = [{"x_start_m": r["x_start_m"], "x_end_m": r["x_end_m"], "w_kN_per_m": r["w_sls"]} for r in ms_udl_rows]
        params["udl_loads_uls"] = [{"x_start_m": r["x_start_m"], "x_end_m": r["x_end_m"], "w_kN_per_m": r["w_uls"]} for r in ms_udl_rows]
        P_sls_total = float(sum(r["P_sls"] for r in ms_rows))
        P_uls_total = float(sum(r["P_uls"] for r in ms_rows))
        base_G = float(sum(r["G"] for r in ms_rows))
        base_Q = float(sum(r["Q"] for r in ms_rows))
        base_g = float(sum(r["g"] for r in ms_udl_rows))
        base_q = float(sum(r["q"] for r in ms_udl_rows))
        update_results(
            psi_point=float(psi_point),
            psi_udl=float(psi_udl),
            P_sls_kN=float(P_sls_total),
            P_uls_kN=float(P_uls_total),
        )
        st.markdown(
            f"**Multi-span summary:** spans={len(params['node_positions_m'])-1}, "
            f"supports={len(params['support_types'])}, point loads={len(ms_rows)}, UDL segments={len(ms_udl_rows)}"
        )
    elif not is_overhang_case:
        params["support_condition"] = support_condition

    # UDL-type cases
    if beam_system_mode != "Multi-span" and load_case in [
        "Simple beam – UDL over entire span",
        "Simple beam – partial UDL from left (length a)",
        "Cantilever – UDL over entire span",
    ]:
        g = render_inline_number_row(
            "Dead UDL g (kN/m)",
            key="load_g_udl",
            value=float(st.session_state.get("load_g_udl", get_param("g_udl_kNm_per_m", 0.0))),
            min_value=0.0,
            step=1.0,
            format="%.1f",
            help_text="Permanent action line load used for SFD/BMD demand derivation.",
            sync_callbacks=sync_callbacks,
        )
        
        q = render_inline_number_row(
            "Live UDL q (kN/m)",
            key="load_q_udl",
            value=float(st.session_state.get("load_q_udl", get_param("q_udl_kNm_per_m", 0.0))),
            min_value=0.0,
            step=1.0,
            format="%.1f",
            help_text="Imposed action line load used for SFD/BMD demand derivation.",
            sync_callbacks=sync_callbacks,
        )
        
        psi_s = render_inline_number_row(
            "Sustained factor ψ_s",
            key="load_psi_udl",
            value=float(st.session_state.get("load_psi_udl", get_param("psi_udl", 0.4))),
            min_value=0.0,
            max_value=1.0,
            step=0.05,
            format="%.2f",
            help_text="Portion of variable action treated as sustained for long-term effects (used by deflection/creep logic).",
            sync_callbacks=sync_callbacks,
        )

        g_shared = float(g)
        q_shared = float(q)
        psi_shared = float(psi_s)

        # SLS + ULS equivalents
        w_sls = g_shared + psi_shared * q_shared  # for deflection and SLS diagrams
        w_uls = gamma_g * g_shared + gamma_q * q_shared  # for ULS design M*, V*
        base_g = g_shared
        base_q = q_shared
        base_psi = psi_shared

        # Defer selection until limit-state toggle
        pass

        # Optional: partial UDL length
        if load_case == "Simple beam – partial UDL from left (length a)":
            a_udl_shared = float(get_param("a_udl_m", L / 2))
            params["a_udl"] = render_inline_number_row(
                "UDL length a from left (m)",
                key="sfd_a_udl",
                value=a_udl_shared,
                min_value=0.0,
                step=0.1,
                format="%.2f",
                sync_callbacks=sync_callbacks,
            )

        update_results(
            g_udl_kNm_per_m=float(g_shared),
            q_udl_kNm_per_m=float(q_shared),
            psi_udl=float(psi_shared),
            w_sls_kNm_per_m=float(w_sls),
            w_uls_kNm_per_m=float(w_uls),
        )

    # Point-load cases
    elif beam_system_mode != "Multi-span" and load_case in [
        "Simple beam – multiple point loads",
        "Cantilever – multiple point loads",
        "Simple beam – point load at centre",
        "Simple beam – point load at distance a from left",
        "Cantilever – point load at free end",
        "Cantilever – point load at distance a from fixed end",
        "Overhanging beam – right overhang with point load at free end",
    ]:
        multi_point_case = load_case in [
            "Simple beam – multiple point loads",
            "Cantilever – multiple point loads",
        ]

        psi_s = render_inline_number_row(
            "Sustained factor ψ_s for point load",
            key="load_psi_point",
            value=float(st.session_state.get("load_psi_point", get_param("psi_point", 0.4))),
            min_value=0.0,
            max_value=1.0,
            step=0.05,
            format="%.2f",
            sync_callbacks=sync_callbacks,
        )
        psi_shared = float(psi_s)
        base_psi_point = psi_shared

        if multi_point_case:
            if "sfd_point_load_count" not in st.session_state:
                st.session_state["sfd_point_load_count"] = 2.0
            else:
                try:
                    st.session_state["sfd_point_load_count"] = float(
                        st.session_state.get("sfd_point_load_count", 2.0)
                    )
                except (TypeError, ValueError):
                    st.session_state["sfd_point_load_count"] = 2.0
            n_loads_raw = render_inline_number_row(
                "Number of point loads",
                key="sfd_point_load_count",
                value=float(st.session_state.get("sfd_point_load_count", 2.0)),
                min_value=1.0,
                max_value=6.0,
                step=1.0,
                format="%.0f",
                sync_callbacks=sync_callbacks,
            )
            n_point_loads = int(max(1, min(6, round(float(n_loads_raw)))))

            point_load_rows = []
            for i in range(1, n_point_loads + 1):
                default_x = (i / (n_point_loads + 1.0)) * float(L)
                g_i = render_inline_number_row(
                    f"Dead point load G_{i} (kN)",
                    key=f"load_G_point_{i}",
                    value=float(st.session_state.get(f"load_G_point_{i}", 50.0)),
                    min_value=0.0,
                    step=5.0,
                    format="%.2f",
                    sync_callbacks=sync_callbacks,
                )
                q_i = render_inline_number_row(
                    f"Live point load Q_{i} (kN)",
                    key=f"load_Q_point_{i}",
                    value=float(st.session_state.get(f"load_Q_point_{i}", 30.0)),
                    min_value=0.0,
                    step=5.0,
                    format="%.2f",
                    sync_callbacks=sync_callbacks,
                )
                x_i = render_inline_number_row(
                    f"Position x_{i} (m)",
                    key=f"load_x_point_{i}",
                    value=float(st.session_state.get(f"load_x_point_{i}", default_x)),
                    min_value=0.0,
                    max_value=float(L),
                    step=0.1,
                    format="%.2f",
                    sync_callbacks=sync_callbacks,
                )

                x_clamped = _clamp_x(float(x_i), float(L))
                g_val = float(g_i)
                q_val = float(q_i)
                p_sls_i = g_val + psi_shared * q_val
                p_uls_i = gamma_g * g_val + gamma_q * q_val
                point_load_rows.append(
                    {
                        "index": i,
                        "x_m": x_clamped,
                        "G_kN": g_val,
                        "Q_kN": q_val,
                        "P_sls_kN": p_sls_i,
                        "P_uls_kN": p_uls_i,
                    }
                )

            point_load_rows = sorted(point_load_rows, key=lambda row: row["x_m"])
            point_loads_sls = [{"x_m": row["x_m"], "P_kN": row["P_sls_kN"]} for row in point_load_rows]
            point_loads_uls = [{"x_m": row["x_m"], "P_kN": row["P_uls_kN"]} for row in point_load_rows]
            P_sls_total = float(sum(row["P_sls_kN"] for row in point_load_rows))
            P_uls_total = float(sum(row["P_uls_kN"] for row in point_load_rows))
            base_G = float(sum(row["G_kN"] for row in point_load_rows))
            base_Q = float(sum(row["Q_kN"] for row in point_load_rows))

            st.markdown("**Point-load summary**")
            summary_lines = [
                "| Load | x (m) | SLS P (kN) | ULS P* (kN) |",
                "|---:|---:|---:|---:|",
            ]
            for row in point_load_rows:
                summary_lines.append(
                    f"| {row['index']} | {row['x_m']:.2f} | {row['P_sls_kN']:.2f} | {row['P_uls_kN']:.2f} |"
                )
            st.markdown("\n".join(summary_lines))
        else:
            # Keep legacy single-point widgets for cases no longer exposed in dropdown.
            G_point = render_inline_number_row(
                "Dead point load G (kN)",
                key="load_G_point",
                value=50.0,
                min_value=0.0,
                step=5.0,
                format="%.2f",
                sync_callbacks=sync_callbacks,
            )
            Q_point = render_inline_number_row(
                "Live point load Q (kN)",
                key="load_Q_point",
                value=30.0,
                min_value=0.0,
                step=5.0,
                format="%.2f",
                sync_callbacks=sync_callbacks,
            )

            G_shared = float(G_point)
            Q_shared = float(Q_point)
            P_sls = G_shared + psi_shared * Q_shared
            P_uls = gamma_g * G_shared + gamma_q * Q_shared
            base_G = G_shared
            base_Q = Q_shared

            if load_case == "Simple beam – point load at distance a from left":
                a_seed = float(get_param("a_m", L / 3.0))
                a = render_inline_number_row(
                    "Distance a from left support (m)",
                    key="load_a_point",
                    value=a_seed,
                    min_value=0.0,
                    step=0.1,
                    format="%.2f",
                    sync_callbacks=sync_callbacks,
                )
                params["a"] = float(a)
            elif load_case == "Cantilever – point load at distance a from fixed end":
                a_cant_shared = float(get_param("a_cant_m", L / 2))
                a = render_inline_number_row(
                    "Distance a from fixed end (m)",
                    key="sfd_a_cant",
                    value=a_cant_shared,
                    min_value=0.0,
                    step=0.1,
                    format="%.2f",
                    sync_callbacks=sync_callbacks,
                )
                params["a_cant"] = float(get_param("a_cant_m", a))
            elif load_case == "Overhanging beam – right overhang with point load at free end":
                L_main = L  # span between supports from Inputs
                a_over_shared = float(get_param("a_overhang_m", 2.0))
                a_over = render_inline_number_row(
                    "Overhang length a (m)",
                    key="sfd_a_overhang",
                    value=a_over_shared,
                    min_value=0.0,
                    step=0.5,
                    format="%.2f",
                    sync_callbacks=sync_callbacks,
                )
                params["L_main"] = L_main
                params["a_overhang"] = float(get_param("a_overhang_m", a_over))

        update_results(
            G_point_kN=float(base_G or 0.0),
            Q_point_kN=float(base_Q or 0.0),
            psi_point=float(psi_shared),
            P_sls_kN=float(P_sls_total if P_sls_total is not None else (P_sls or 0.0)),
            P_uls_kN=float(P_uls_total if P_uls_total is not None else (P_uls or 0.0)),
        )

    # Close the loading-grid container
    st.markdown("</div>", unsafe_allow_html=True)
    st.divider()

    st.session_state["loads_edit_mode"] = "SLS" if use_sls else "ULS"
    active_mode = st.session_state.get("loads_edit_mode", "ULS")
    case = load_case
    beam_length_seed = float(params.get("L_main", L) + params.get("a_overhang", 0.0)) if case == "Overhanging beam – right overhang with point load at free end" else float(L)

    def _on_design_actions_source_change() -> None:
        source_value = str(st.session_state.get("design_actions_source_selector", "max") or "max")
        set_shared("design_actions_source", source_value, source="callback:design_actions_source_selector")
        if source_value != "section":
            return
        committed_x = float(st.session_state.get("design_section_x_m", 0.0) or 0.0)
        current_x = float(st.session_state.get("section_cursor_x_m", 0.0) or 0.0)
        if bool(st.session_state.get("design_section_committed")) and 0.0 <= committed_x <= beam_length_seed:
            init_x = committed_x
        elif 0.0 < current_x <= beam_length_seed:
            init_x = current_x
        else:
            init_x = beam_length_seed / 2.0 if beam_length_seed > 0 else 0.0
        init_x = _clamp_x(init_x, beam_length_seed) if beam_length_seed > 0 else 0.0
        st.session_state["design_section_x_slider"] = init_x
        st.session_state["design_section_x_input"] = init_x
        set_shared("section_cursor_x_m", init_x, source="callback:design_actions_source_selector")

    source_options = ["max", "section"]
    current_source = str(get_param("design_actions_source", "max") or "max")
    if current_source not in source_options:
        current_source = "max"
    v2_radio(
        label="Design actions source",
        key="design_actions_source_selector",
        options=source_options,
        default_index=source_options.index(current_source),
        format_func=lambda v: "Absolute maxima" if v == "max" else "Design section",
        horizontal=True,
        on_change=_on_design_actions_source_change,
    )
    design_actions_source = str(st.session_state.get("design_actions_source_selector", current_source) or "max")

    params_uls = dict(params)
    params_sls = dict(params)
    if w_sls is not None and w_uls is not None:
        params_uls["w"] = float(w_uls)
        params_sls["w"] = float(w_sls)
    if P_sls is not None and P_uls is not None:
        params_uls["P"] = float(P_uls)
        params_sls["P"] = float(P_sls)
    if point_loads_sls is not None and point_loads_uls is not None:
        params_uls["point_loads"] = point_loads_uls
        params_sls["point_loads"] = point_loads_sls
    if "udl_loads_uls" in params and "udl_loads_sls" in params:
        params_uls["udl_loads"] = list(params.get("udl_loads_uls") or [])
        params_sls["udl_loads"] = list(params.get("udl_loads_sls") or [])

    # Combined load label for calc boxes
    load_label = None
    load_value = None
    load_units = ""
    if w_sls is not None and w_uls is not None:
        load_label = "w*" if active_mode == "ULS" else "w"
        load_value = float(params_uls.get("w", 0.0) if active_mode == "ULS" else params_sls.get("w", 0.0))
        load_units = "kN/m"
    elif point_loads_sls is not None and point_loads_uls is not None:
        load_label = "ΣP*" if active_mode == "ULS" else "ΣP"
        load_value = float(P_uls_total if active_mode == "ULS" else P_sls_total)
        load_units = "kN"
    elif P_sls is not None and P_uls is not None:
        load_label = "P*" if active_mode == "ULS" else "P"
        load_value = float(params_uls.get("P", 0.0) if active_mode == "ULS" else params_sls.get("P", 0.0))
        load_units = "kN"
    load_intro = ""
    if load_label is not None:
        load_intro = f"**Combined load used ({active_mode}):** {load_label} = {load_value:.3g}\\,{load_units}\n\n"
    if beam_system_mode == "Multi-span":
        n_pts = len(params_uls.get("point_loads", [])) if active_mode == "ULS" else len(params_sls.get("point_loads", []))
        n_udls = len(params_uls.get("udl_loads", [])) if active_mode == "ULS" else len(params_sls.get("udl_loads", []))
        load_intro = (
            f"**Combined loads used ({active_mode}):** point loads = {n_pts}, "
            f"UDL segments = {n_udls}\n\n"
        )

    x_uls, V_uls_vals, M_uls_vals, beam_length_uls, results_local_uls = _compute_diagram_arrays(case, L, params_uls)
    x_sls, V_sls_vals, M_sls_vals, beam_length_sls, results_local_sls = _compute_diagram_arrays(case, L, params_sls)

    if active_mode == "ULS":
        x, V, M = x_uls, V_uls_vals, M_uls_vals
        beam_length = beam_length_uls
        results_local = results_local_uls
        active_params = params_uls
    else:
        x, V, M = x_sls, V_sls_vals, M_sls_vals
        beam_length = beam_length_sls
        results_local = results_local_sls
        active_params = params_sls
    params = active_params

    V_uls = float(np.max(np.abs(V_uls_vals))) if V_uls_vals is not None else 0.0
    M_uls = float(np.max(np.abs(M_uls_vals))) if M_uls_vals is not None else 0.0
    V_sls = float(np.max(np.abs(V_sls_vals))) if V_sls_vals is not None else 0.0
    M_sls = float(np.max(np.abs(M_sls_vals))) if M_sls_vals is not None else 0.0
    M_pos_max_uls = float(max(0.0, float(np.max(M_uls_vals)))) if M_uls_vals is not None else 0.0
    M_neg_min_uls = float(min(0.0, float(np.min(M_uls_vals)))) if M_uls_vals is not None else 0.0
    M_pos_max_sls = float(max(0.0, float(np.max(M_sls_vals)))) if M_sls_vals is not None else 0.0
    M_neg_min_sls = float(min(0.0, float(np.min(M_sls_vals)))) if M_sls_vals is not None else 0.0
    M_max_abs = float(np.max(np.abs(M))) if M is not None else 0.0
    V_max_abs = float(np.max(np.abs(V))) if V is not None else 0.0
    if V_uls_vals is not None and len(V_uls_vals) and x_uls is not None and len(x_uls):
        _crit_idx = int(np.argmax(np.abs(V_uls_vals)))
        x_crit = float(x_uls[_crit_idx])
        V_crit = float(V_uls_vals[_crit_idx])
    else:
        x_crit = None
        V_crit = None
    support_type_resolved = _defl_support_type_from_selection(case, str(params.get("support_condition", "") or ""))
    support_type_key = "cantilever" if support_type_resolved == "Cantilever" else "simply_supported"
    x_uls_list = [float(v) for v in (x_uls.tolist() if hasattr(x_uls, "tolist") else list(x_uls))]
    xu = np.asarray(x_uls_list, dtype=float)
    Mu = np.asarray(
        M_uls_vals.tolist() if hasattr(M_uls_vals, "tolist") else list(M_uls_vals or []),
        dtype=float,
    )
    xs = np.asarray(x_sls.tolist() if hasattr(x_sls, "tolist") else list(x_sls or []), dtype=float)
    Ms = np.asarray(
        M_sls_vals.tolist() if hasattr(M_sls_vals, "tolist") else list(M_sls_vals or []),
        dtype=float,
    )
    if xu.size >= 2 and Mu.size == xu.size and Ms.size == xs.size:
        if xs.shape == xu.shape and float(np.max(np.abs(xs - xu))) <= 1e-6 * max(1.0, float(xu[-1])):
            M_sls_on_xu = Ms
        else:
            M_sls_on_xu = np.interp(xu, xs, Ms, left=float(Ms[0]), right=float(Ms[-1]))
    else:
        M_sls_on_xu = np.array([], dtype=float)

    sup_pos = [float(v) for v in (results_local_uls.get("support_positions") or [])]
    sup_types = [str(v) for v in (results_local_uls.get("support_types") or [])]
    if not sup_types and len(sup_pos) >= 2:
        sup_types = ["Pinned", "Roller"]
    elif not sup_types and len(sup_pos) == 1:
        sup_types = ["Fixed"]

    _fp = diagram_cache_fingerprint(
        str(case),
        float(beam_length_uls),
        dict(params_uls or {}),
        float(beam_length_sls),
        dict(params_sls or {}),
    )

    preview_x_m = None
    preview_V_active = None
    preview_M_active = None
    committed_x_m = None

    def _on_design_section_slider_change() -> None:
        x_new = _clamp_x(float(st.session_state.get("design_section_x_slider", 0.0) or 0.0), beam_length)
        st.session_state["design_section_x_slider"] = x_new
        st.session_state["design_section_x_input"] = x_new
        set_shared("section_cursor_x_m", x_new, source="callback:design_section_x_slider")

    def _on_design_section_input_change() -> None:
        x_new = _clamp_x(float(st.session_state.get("design_section_x_input", 0.0) or 0.0), beam_length)
        st.session_state["design_section_x_input"] = x_new
        st.session_state["design_section_x_slider"] = x_new
        set_shared("section_cursor_x_m", x_new, source="callback:design_section_x_input")

    def _commit_design_section() -> None:
        x_commit = _clamp_x(float(st.session_state.get("design_section_x_slider", 0.0) or 0.0), beam_length)
        set_shared("design_section_x_m", x_commit, source="callback:use_design_section_btn")
        set_shared("design_section_committed", True, source="callback:use_design_section_btn")
        update_results(
            design_M_uls_kNm=float(st.session_state.get("preview_M_uls_kNm", 0.0) or 0.0),
            design_M_uls_kNm_signed=float(st.session_state.get("preview_M_uls_kNm", 0.0) or 0.0),
            design_V_uls_kN=float(st.session_state.get("preview_V_uls_kN", 0.0) or 0.0),
            design_M_sls_kNm=float(st.session_state.get("preview_M_sls_kNm", 0.0) or 0.0),
            design_M_sls_kNm_signed=float(st.session_state.get("preview_M_sls_kNm", 0.0) or 0.0),
            design_V_sls_kN=float(st.session_state.get("preview_V_sls_kN", 0.0) or 0.0),
        )
        st.session_state["_design_section_commit_msg"] = f"Design actions set from x = {x_commit:.3f} m"

    if design_actions_source == "section" and beam_length > 0:
        initial_cursor_x = float(get_param("section_cursor_x_m", 0.0) or 0.0)
        if initial_cursor_x <= 0.0:
            committed_seed = float(get_param("design_section_x_m", 0.0) or 0.0)
            if bool(get_param("design_section_committed", False)) and 0.0 <= committed_seed <= beam_length:
                initial_cursor_x = committed_seed
            else:
                initial_cursor_x = beam_length / 2.0
        initial_cursor_x = _clamp_x(initial_cursor_x, beam_length)
        st.session_state.setdefault("design_section_x_slider", initial_cursor_x)
        st.session_state.setdefault("design_section_x_input", initial_cursor_x)

        render_section_title("Design section")
        st.caption("Click a diagram or drag the slider to inspect actions along the beam.")

        sec_l, sec_r = st.columns([6, 1], gap="small")
        with sec_l:
            st.markdown("Section location x (m)")

        preview_x_m = _clamp_x(float(st.session_state.get("design_section_x_slider", initial_cursor_x) or 0.0), beam_length)
        preview_V_uls = _interp_at_x(x_uls, V_uls_vals, preview_x_m)
        preview_M_uls = _interp_at_x(x_uls, M_uls_vals, preview_x_m)
        preview_V_sls = _interp_at_x(x_sls, V_sls_vals, preview_x_m)
        preview_M_sls = _interp_at_x(x_sls, M_sls_vals, preview_x_m)
        update_results(
            preview_M_uls_kNm=float(preview_M_uls),
            preview_V_uls_kN=float(preview_V_uls),
            preview_M_sls_kNm=float(preview_M_sls),
            preview_V_sls_kN=float(preview_V_sls),
        )
        preview_V_active = preview_V_uls if active_mode == "ULS" else preview_V_sls
        preview_M_active = preview_M_uls if active_mode == "ULS" else preview_M_sls
        committed_x_m = None
        if bool(get_param("design_section_committed", False)):
            committed_x_m = _clamp_x(float(get_param("design_section_x_m", 0.0) or 0.0), beam_length)

        with sec_r:
            with info_i_button(help_text="Preview actions and committed design section"):
                st.markdown(f"**x = {preview_x_m:.3f} m** from left support")
                st.caption(f"ULS: M* = {preview_M_uls:.3f} kNm, V* = {preview_V_uls:.3f} kN")
                st.caption(f"SLS: M = {preview_M_sls:.3f} kNm, V = {preview_V_sls:.3f} kN")
                if committed_x_m is not None:
                    st.caption(f"Committed design section: x = {committed_x_m:.3f} m")
                else:
                    st.caption("No design section committed yet.")

        # Keep hidden numeric state in sync without rendering the input widget.
        st.session_state["design_section_x_input"] = float(
            st.session_state.get("design_section_x_slider", initial_cursor_x)
        )

        slider_left, slider_mid, slider_right = st.columns([0.08, 0.84, 0.08], gap=None)
        with slider_mid:
            st.slider(
                "Section location x (m)",
                min_value=0.0,
                max_value=float(beam_length),
                value=float(st.session_state.get("design_section_x_slider", initial_cursor_x)),
                step=0.01,
                key="design_section_x_slider",
                on_change=_on_design_section_slider_change,
                label_visibility="collapsed",
            )
        st.button("Use this section for design", key="use_design_section_btn", on_click=_commit_design_section)
        commit_msg = st.session_state.get("_design_section_commit_msg")
        if commit_msg:
            st.success(commit_msg)
    # Determine support type for summary
    support_type = "—"
    if case == "Overhanging beam – right overhang with point load at free end":
        support_type = "Pinned–Pinned (overhang)"
    else:
        support_type = str(
            params.get(
                "support_condition",
                support_condition if "support_condition" in locals() else "Simply supported",
            )
        )

    # Get capacity values for limit display (reuse existing computed values)
    phi_Mu_cap = get_param("phi_Mu_cap", None)
    phi_Vu_cap = get_param("phi_Vu_cap", None)
    
    # Determine limit strings for derivation rows
    shear_limit = "—"
    if phi_Vu_cap is not None and not (isinstance(phi_Vu_cap, float) and math.isnan(phi_Vu_cap)) and phi_Vu_cap > 0:
        shear_limit = f"φV_u,cap = {phi_Vu_cap:.1f} kN"
    
    moment_limit = "—"
    if phi_Mu_cap is not None and not (isinstance(phi_Mu_cap, float) and math.isnan(phi_Mu_cap)) and phi_Mu_cap > 0:
        moment_limit = f"φM_u = {phi_Mu_cap:.1f} kNm"

    # Build summary rows for clickable table (capacity = reference strength; action = derived demand)
    rows_summary = [
        {"Check": "Support conditions", "capacity": support_type, "action": "—", "Utilisation": "—", "Status": "OK"},
        {"Check": "Reactions", "capacity": "Derived from model", "action": "—", "Utilisation": "—", "Status": "OK"},
        {"Check": "Shear derivation", "capacity": shear_limit, "action": f"|V|_max = {V_max_abs:.2f} kN", "Utilisation": "—", "Status": "OK"},
        {"Check": "Moment derivation", "capacity": moment_limit, "action": f"|M|_max = {M_max_abs:.2f} kNm", "Utilisation": "—", "Status": "OK"},
    ]

    support_condition_summary = str(params.get("support_condition", "")).replace("-", "–")
    solver_case_summary = (
        case == "Multi-span continuous beam"
        or (
            case.startswith("Simple beam")
            and support_condition_summary in {"Fixed–Pinned", "Pinned–Fixed", "Fixed–Fixed"}
        )
    )
    check_to_uid = {
        "Support conditions": EQ_SLS_UID["step1"],
        "Reactions": EQ_SLS_UID["step2f"] if solver_case_summary else EQ_SLS_UID["step2"],
        "Shear derivation": EQ_SLS_UID["step3"],
        "Moment derivation": EQ_SLS_UID["step4"],
    }

    check_to_tab = {
        "Support conditions": "SLS",
        "Reactions": "SLS",
        "Shear derivation": "SLS",
        "Moment derivation": "SLS",
    }

    ROWS = []
    for r in rows_summary:
        check = r.get("Check", "")
        cap_cell = r.get("capacity", r.get("Value", "—"))
        act_cell = r.get("action", r.get("Limit", "—"))
        util_str = r.get("Utilisation", "—")
        status_str = r.get("Status", "")
        
        # Explicitly set capacity + demand for derivation rows (util = demand / capacity)
        if check == "Shear derivation":
            cap_cell = shear_limit
            act_cell = f"|V|_max = {V_max_abs:.2f} kN"
            if phi_Vu_cap not in (0, None) and not (isinstance(phi_Vu_cap, float) and math.isnan(phi_Vu_cap)):
                util_val = V_max_abs / phi_Vu_cap
                util_str = str(round(util_val, 3)) if util_val is not None else "—"
                status_str = "OK" if (util_val is not None and util_val <= 1.0) else "NG"
                ok = True if status_str == "OK" else False
            else:
                util_str = "—"
                status_str = "—"
                ok = None
        elif check == "Moment derivation":
            cap_cell = moment_limit
            act_cell = f"|M|_max = {M_max_abs:.2f} kNm"
            if phi_Mu_cap not in (0, None) and not (isinstance(phi_Mu_cap, float) and math.isnan(phi_Mu_cap)):
                util_val = M_max_abs / phi_Mu_cap
                util_str = str(round(util_val, 3)) if util_val is not None else "—"
                status_str = "OK" if (util_val is not None and util_val <= 1.0) else "NG"
                ok = True if status_str == "OK" else False
            else:
                util_str = "—"
                status_str = "—"
                ok = None
        
        # Determine if this is a check row (has numeric utilisation for pass/fail)
        # A row is a check row only if it has a numeric utilisation (not just a limit)
        is_check_row = util_str not in ("", "—", None)
        
        # Force derivation rows to be treated as check rows
        if check in ("Shear derivation", "Moment derivation"):
            is_check_row = True
        
        # Determine ok status for styling (True=pass/green, False=fail/red, None=neutral-blue)
        if not is_check_row:
            # No utilisation check → neutral blue styling
            util_str = "—"
            ok = None
        else:
            # Has utilisation check → derive ok from status (if not already set above)
            if ok is None:
                if status_str == "OK":
                    ok = True
                elif status_str in ("NG", "Fail", "Not OK"):
                    ok = False
                else:
                    # For rows with utilisation, derive status from util if status is not explicitly set
                    if util_str != "—" and status_str == "":
                        try:
                            util_val = float(util_str)
                            if not math.isnan(util_val):
                                status_str = "OK" if util_val <= 1.0 else "NG"
                                ok = True if util_val <= 1.0 else False
                            else:
                                ok = None
                        except (ValueError, TypeError):
                            ok = None
                    else:
                        ok = None

        ROWS.append(
            sync_legacy_value_limit(
                {
                    "title": check,
                    "capacity": cap_cell,
                    "action": act_cell,
                    "util": util_str,
                    "status": status_str,
                    "ok": ok,
                    "uid": check_to_uid.get(check, ""),
                    "tab": check_to_tab.get(check, "SLS"),
                }
            )
        )

    # Render design actions summary table (SLS + ULS + strength/utilisation)
    with summary_placeholder.container():
        render_page_explainer_expander(_render_sfd_bmd_explainer)
        phi_Vu_cap = get_param("phi_Vu_cap", None)
        phi_Mu_cap = get_param("phi_Mu_cap", None)

        def _strength_display(value: float | None, units: str) -> str:
            if value is None or (isinstance(value, float) and math.isnan(value)) or value <= 0:
                return "—"
            return f"{value:.2f} {units}"

        def _util_status(uls_value: float, strength_value: float | None) -> tuple[str, str, bool | None]:
            if strength_value is None or (isinstance(strength_value, float) and math.isnan(strength_value)) or strength_value <= 0:
                return "—", "Not checked", None
            util_val = uls_value / strength_value
            util_str = f"{util_val:.3f}"
            if util_val > 1.0:
                return util_str, "FAIL", False
            if util_val >= 0.9:
                return util_str, "NEAR LIMIT", None
            return util_str, "PASS", True

        use_committed_section_actions = (
            design_actions_source == "section"
            and bool(get_param("design_section_committed", False))
        )
        summary_V_uls = float(get_param("design_V_uls_kN", 0.0) or 0.0) if use_committed_section_actions else float(V_uls)
        summary_V_sls = float(get_param("design_V_sls_kN", 0.0) or 0.0) if use_committed_section_actions else float(V_sls)

        if use_committed_section_actions:
            M_uls_signed = float(
                get_param("design_M_uls_kNm_signed", get_param("design_M_uls_kNm", 0.0)) or 0.0
            )
            M_sls_signed = float(
                get_param("design_M_sls_kNm_signed", get_param("design_M_sls_kNm", 0.0)) or 0.0
            )
            sag_M_uls = max(0.0, M_uls_signed)
            sag_M_sls = max(0.0, M_sls_signed)
            hog_M_uls = abs(min(0.0, M_uls_signed))
            hog_M_sls = abs(min(0.0, M_sls_signed))
            M_neg_min_uls_for_rule = M_uls_signed
        else:
            sag_M_uls = float(M_pos_max_uls)
            sag_M_sls = float(M_pos_max_sls)
            hog_M_uls = abs(float(M_neg_min_uls))
            hog_M_sls = abs(float(M_neg_min_sls))
            M_neg_min_uls_for_rule = float(M_neg_min_uls)

        shear_strength = None if phi_Vu_cap is None else float(phi_Vu_cap)
        shear_util, shear_status, shear_ok = _util_status(summary_V_uls, shear_strength)

        phi_mu_pos_cap = get_param("phi_Mu_pos_kNm", None)
        phi_mu_neg_cap = get_param("phi_Mu_neg_kNm", None)
        if phi_mu_pos_cap is None or (isinstance(phi_mu_pos_cap, float) and math.isnan(phi_mu_pos_cap)):
            phi_mu_pos_cap = None
        else:
            phi_mu_pos_cap = float(phi_mu_pos_cap)
        if phi_mu_neg_cap is None or (isinstance(phi_mu_neg_cap, float) and math.isnan(phi_mu_neg_cap)):
            phi_mu_neg_cap = None
        else:
            phi_mu_neg_cap = float(phi_mu_neg_cap)
        if phi_mu_pos_cap is None or phi_mu_pos_cap <= 0:
            _fb = None if phi_Mu_cap is None else float(phi_Mu_cap)
            phi_mu_pos_cap = _fb if _fb is not None and _fb > 0 else None
        if phi_mu_neg_cap is None or phi_mu_neg_cap <= 0:
            phi_mu_neg_cap = None

        has_sagging_case = True
        has_hogging_case = M_neg_min_uls_for_rule is not None and float(M_neg_min_uls_for_rule) < -1e-9

        sag_util, sag_status, sag_ok = _util_status(sag_M_uls, phi_mu_pos_cap)
        hog_util, hog_status, hog_ok = _util_status(hog_M_uls, phi_mu_neg_cap)

        summary_rows = [
            {
                "name": "Shear V",
                "sls": f"{summary_V_sls:.2f} kN",
                "uls": f"{summary_V_uls:.2f} kN",
                "strength": _strength_display(shear_strength, "kN"),
                "util": shear_util,
                "status": shear_status,
                "uid": EQ_SLS_UID["step3"],
                "tab": "SLS",
                "ok": shear_ok,
            },
        ]
        if has_sagging_case:
            summary_rows.append(
                {
                    "name": "Sagging moment M+",
                    "sls": f"{sag_M_sls:.2f} kNm",
                    "uls": f"{sag_M_uls:.2f} kNm",
                    "strength": _strength_display(phi_mu_pos_cap, "kNm"),
                    "util": sag_util,
                    "status": sag_status,
                    "uid": EQ_SLS_UID["step4"],
                    "tab": "SLS",
                    "ok": sag_ok,
                }
            )
        if has_hogging_case:
            summary_rows.append(
                {
                    "name": "Hogging moment M−",
                    "sls": f"{hog_M_sls:.2f} kNm",
                    "uls": f"{hog_M_uls:.2f} kNm",
                    "strength": _strength_display(phi_mu_neg_cap, "kNm"),
                    "util": hog_util,
                    "status": hog_status,
                    "uid": EQ_SLS_UID["step4"],
                    "tab": "SLS",
                    "ok": hog_ok,
                }
            )
        render_clickable_summary_table(
            summary_rows,
            key_prefix="design_actions_summary",
            columns=DESIGN_ACTION_SUMMARY_COLUMNS,
        )

    st.markdown('<div id="shear-analysis-section"></div>', unsafe_allow_html=True)

    debug_sfd_bmd = False
    if debug_sfd_bmd:
        st.write("design_actions_source:", design_actions_source)
        st.write("beam_length:", beam_length)
        st.write(
            "len(x), len(V), len(M):",
            len(x) if x is not None else None,
            len(V) if V is not None else None,
            len(M) if M is not None else None,
        )
        st.write(
            "V min/max:",
            float(np.min(V)) if V is not None and len(V) else None,
            float(np.max(V)) if V is not None and len(V) else None,
        )
        st.write(
            "M min/max:",
            float(np.min(M)) if M is not None and len(M) else None,
            float(np.max(M)) if M is not None and len(M) else None,
        )
        st.write("preview_x_m:", preview_x_m)
        st.write("preview_V_active:", preview_V_active)
        st.write("preview_M_active:", preview_M_active)

    fig_load = plot_load_diagram_plotly(
        case,
        beam_length,
        params,
        preview_x_m=preview_x_m,
        design_x_m=committed_x_m,
        support_condition=params.get("support_condition"),
        support_positions=results_local.get("support_positions") if isinstance(results_local, dict) else None,
        support_types=results_local.get("support_types") if isinstance(results_local, dict) else None,
        point_loads=params.get("point_loads"),
        udl_loads=params.get("udl_loads"),
    )

    support_positions = results_local.get("support_positions") if isinstance(results_local, dict) else None
    if not support_positions:
        if case == "Overhanging beam – right overhang with point load at free end":
            support_positions = [0.0, float(params.get("L_main", L))]
        elif case.startswith("Cantilever"):
            support_positions = [0.0]
        else:
            support_positions = [0.0, float(beam_length)]
    sfd_bmd_plot_st = _prepare_sfd_bmd_plot_state(
        x,
        V,
        M,
        case=case,
        L=beam_length,
        support_positions=support_positions,
        support_types=results_local.get("support_types") if isinstance(results_local, dict) else None,
        preview_x_m=preview_x_m,
        design_x_m=committed_x_m,
        preview_V=preview_V_active,
        preview_M=preview_M_active,
    )
    fig_sfd = _figure_sfd_from_state(sfd_bmd_plot_st)

    use_plotly_event_component = design_actions_source == "section"

    # ===== STACKED DIAGRAM LAYOUT =====
    render_section_title(f"Load diagram ({active_mode} loads)")
    st.caption("Loads")
    if use_plotly_event_component:
        render_plotly_fullscreen_control(
            fig_load,
            key="design_load_plot_chart",
            title="Load diagram",
        )
        load_click = plotly_events(
            fig_load,
            click_event=True,
            hover_event=False,
            select_event=False,
            override_height=170,
            override_width="100%",
            key="design_load_plot_click",
        )
    else:
        render_plotly_diagram(
            fig_load,
            key="design_load_plot_chart",
            title="Load diagram",
        )
        load_click = None

    st.markdown("<div style='height:2px'></div>", unsafe_allow_html=True)

    render_section_title("Shear Force Diagram (SFD)")
    st.caption("Shear V(x)")
    if use_plotly_event_component:
        render_plotly_fullscreen_control(
            fig_sfd,
            key="design_sfd_plot_chart",
            title="Shear force diagram",
        )
        sfd_click = plotly_events(
            fig_sfd,
            click_event=True,
            hover_event=False,
            select_event=False,
            override_height=300,
            override_width="100%",
            key="design_sfd_plot_click",
        )
    else:
        render_plotly_diagram(
            fig_sfd,
            key="design_sfd_plot_chart",
            title="Shear force diagram",
        )
        sfd_click = None

    st.markdown("<div style='height:2px'></div>", unsafe_allow_html=True)

    st.markdown('<div id="moment-analysis-section"></div>', unsafe_allow_html=True)
    bmd_head_l, bmd_head_r = st.columns([3, 2], gap="small")
    with bmd_head_l:
        render_section_title("Bending Moment Diagram (BMD)")
    with bmd_head_r:
        show_m_peak_marker = v2_checkbox(
            label="Show |M|max",
            key="sfd_bmd_show_m_peak_marker",
            default=False,
            help="Marker at the station of maximum |M| along the span.",
        )
    fig_bmd = _figure_bmd_from_state(sfd_bmd_plot_st, show_m_peak=bool(show_m_peak_marker))
    st.caption("Moment M(x); hogging (M < 0) is drawn above the baseline (ordinate −M).")
    if use_plotly_event_component:
        render_plotly_fullscreen_control(
            fig_bmd,
            key="design_bmd_plot_chart",
            title="Bending moment diagram",
        )
        bmd_click = plotly_events(
            fig_bmd,
            click_event=True,
            hover_event=False,
            select_event=False,
            override_height=300,
            override_width="100%",
            key="design_bmd_plot_click",
        )
    else:
        render_plotly_diagram(
            fig_bmd,
            key="design_bmd_plot_chart",
            title="Bending moment diagram",
        )
        bmd_click = None

    if design_actions_source == "section" and use_plotly_event_component and float(beam_length) > 0:
        clicked_x = None

        for event_data in (load_click, sfd_click, bmd_click):
            if event_data is None:
                continue
            raw_x = _extract_clicked_x_from_plotly_event(event_data)
            if raw_x is not None:
                clicked_x = _clamp_x_to_span(raw_x, beam_length)
                if clicked_x is not None:
                    break

        if clicked_x is not None:
            set_shared("section_cursor_x_m", float(clicked_x), source="sfd_bmd_page")
            st.rerun()

    st.divider()
    # ---------------------------------------------------
    # Full equilibrium derivation – 4 blue calc boxes
    # ---------------------------------------------------
    render_section_title(f"Equilibrium derivation ({active_mode})")

    # STEP 0 – load combination (expandable)
    step0_md = ""
    w_used = float(params.get("w", 0.0))
    P_used = float(params.get("P", 0.0))
    g_val = 0.0 if base_g is None else float(base_g)
    q_val = 0.0 if base_q is None else float(base_q)
    psi_val = 0.0 if base_psi is None else float(base_psi)
    G_val = 0.0 if base_G is None else float(base_G)
    Q_val = 0.0 if base_Q is None else float(base_Q)
    psi_pt_val = 0.0 if base_psi_point is None else float(base_psi_point)

    if w_sls is not None and w_uls is not None:
        if active_mode == "ULS":
            step0_md = f"""
**Step 0 – Load combination ({active_mode})**

**1) Inputs**  \n
- Dead UDL: $g = {g_val:.3g}\\, \\text{{kN/m}}$  \n
- Live UDL: $q = {q_val:.3g}\\, \\text{{kN/m}}$  \n
- Factors: $\\gamma_g = {gamma_g:.2g}$, $\\gamma_q = {gamma_q:.2g}$  \n\n
**2) Governing equation**  \n
- $w^* = \\gamma_g g + \\gamma_q q$  \n\n
**3) Substitute / derive**  \n
- $w^* = {gamma_g:.2g} \\times {g_val:.3g} + {gamma_q:.2g} \\times {q_val:.3g}$  \n\n
**4) Result**  \n
- $w^* = {w_used:.3g}\\, \\text{{kN/m}}$
"""
        else:
            step0_md = f"""
**Step 0 – Load combination ({active_mode})**

**1) Inputs**  \n
- Dead UDL: $g = {g_val:.3g}\\, \\text{{kN/m}}$  \n
- Live UDL: $q = {q_val:.3g}\\, \\text{{kN/m}}$  \n
- Sustained factor: $\\psi_s = {psi_val:.3g}$  \n\n
**2) Governing equation**  \n
- $w = g + \\psi_s q$  \n\n
**3) Substitute / derive**  \n
- $w = {g_val:.3g} + {psi_val:.3g} \\times {q_val:.3g}$  \n\n
**4) Result**  \n
- $w = {w_used:.3g}\\, \\text{{kN/m}}$
"""
    elif point_loads_sls is not None and point_loads_uls is not None:
        total_sls = float(P_sls_total or 0.0)
        total_uls = float(P_uls_total or 0.0)
        if active_mode == "ULS":
            step0_md = f"""
**Step 0 – Load combination ({active_mode})**

**1) Inputs**  \n
- Number of point loads: $n = {len(point_loads_uls)}$  \n
- Factors: $\\gamma_g = {gamma_g:.2g}$, $\\gamma_q = {gamma_q:.2g}$  \n\n
**2) Governing equation (per load)**  \n
- $P_i^* = \\gamma_g G_i + \\gamma_q Q_i$  \n\n
**3) Aggregate**  \n
- $\\sum P_i^* = {total_uls:.3g}\\,\\text{{kN}}$  \n\n
**4) Result**  \n
- ULS point-load list is passed to solver as `params[\"point_loads\"]`.
"""
        else:
            step0_md = f"""
**Step 0 – Load combination ({active_mode})**

**1) Inputs**  \n
- Number of point loads: $n = {len(point_loads_sls)}$  \n
- Sustained factor: $\\psi_s = {psi_pt_val:.3g}$  \n\n
**2) Governing equation (per load)**  \n
- $P_i = G_i + \\psi_s Q_i$  \n\n
**3) Aggregate**  \n
- $\\sum P_i = {total_sls:.3g}\\,\\text{{kN}}$  \n\n
**4) Result**  \n
- SLS point-load list is passed to solver as `params[\"point_loads\"]`.
"""
    elif P_sls is not None and P_uls is not None:
        if active_mode == "ULS":
            step0_md = f"""
**Step 0 – Load combination ({active_mode})**

**1) Inputs**  \n
- Dead point load: $G = {G_val:.3g}\\, \\text{{kN}}$  \n
- Live point load: $Q = {Q_val:.3g}\\, \\text{{kN}}$  \n
- Factors: $\\gamma_g = {gamma_g:.2g}$, $\\gamma_q = {gamma_q:.2g}$  \n\n
**2) Governing equation**  \n
- $P^* = \\gamma_g G + \\gamma_q Q$  \n\n
**3) Substitute / derive**  \n
- $P^* = {gamma_g:.2g} \\times {G_val:.3g} + {gamma_q:.2g} \\times {Q_val:.3g}$  \n\n
**4) Result**  \n
- $P^* = {P_used:.3g}\\, \\text{{kN}}$
"""
        else:
            step0_md = f"""
**Step 0 – Load combination ({active_mode})**

**1) Inputs**  \n
- Dead point load: $G = {G_val:.3g}\\, \\text{{kN}}$  \n
- Live point load: $Q = {Q_val:.3g}\\, \\text{{kN}}$  \n
- Sustained factor: $\\psi_s = {psi_pt_val:.3g}$  \n\n
**2) Governing equation**  \n
- $P = G + \\psi_s Q$  \n\n
**3) Substitute / derive**  \n
- $P = {G_val:.3g} + {psi_pt_val:.3g} \\times {Q_val:.3g}$  \n\n
**4) Result**  \n
- $P = {P_used:.3g}\\, \\text{{kN}}$
"""

    if step0_md:
        step0_summary = f"Step 0 – Load combination ({active_mode}) | Combine base loads to get {load_label or 'load'}"
        step0_uid = EQ_SLS_UID["step0"]
        step_expander_calcbox(
            uid=step0_uid,
            summary_line=step0_summary,
            details_md=step0_md,
            status=None,
            accent="load",
        )

    # STEP 1 – Support conditions (expandable)
    step1_md = ""
    step1_summary = ""
    support_condition_active = str(params.get("support_condition", support_condition if "support_condition" in locals() else "")).replace("-", "–")
    fixed_end_indeterminate = support_condition_active in {"Fixed–Pinned", "Pinned–Fixed", "Fixed–Fixed"}
    
    if case == "Multi-span continuous beam":
        nodes = list(params.get("node_positions_m") or [])
        spans = [nodes[i + 1] - nodes[i] for i in range(len(nodes) - 1)] if len(nodes) >= 2 else []
        supports_txt = ", ".join(str(s) for s in (params.get("support_types") or [])) or "—"
        step1_summary = f"Step 1 – Beam system | Multi-span continuous beam with {max(0, len(nodes)-1)} spans"
        step1_md = f"""
**1) Inputs**  \n
- Span lengths (m): {", ".join(f"{v:.3g}" for v in spans) if spans else "—"}  \n
- Support types: {supports_txt}  \n
- Total length: $L = {L:.3g}\\,\\text{{m}}$  \n\n
**2) Analysis model**  \n
- Continuous Euler-Bernoulli beam discretised by spans between supports.  \n
- Supports enforce vertical/fixity constraints by type (Pinned/Roller/Fixed).  \n\n
**3) Solver**  \n
- Reactions and internal actions are obtained from the beam-analysis backend (stiffness method).  \n\n
**4) Result**  \n
- Use solved arrays for SFD/BMD, maxima, and design-section actions.
"""
    elif case.startswith("Simple beam") and fixed_end_indeterminate:
        left_desc = "fixed" if support_condition_active.startswith("Fixed") else "pinned"
        right_desc = "fixed" if support_condition_active.endswith("Fixed") else "pinned"
        step1_summary = (
            f"Step 1 – Support conditions | {support_condition_active} single-span beam "
            f"of span $L = {L:.1f}$ m"
        )
        step1_md = f"""
**1) Inputs**  \n
- Left support: {left_desc}  \n
- Right support: {right_desc}  \n
- Span: $L = {L:.3g}\\, \\text{{m}}$  \n\n
**2) Governing equations**  \n
- Global equilibrium: $\\sum V = 0$, $\\sum M = 0$  \n
- Compatibility from end fixity (statically indeterminate system)  \n\n
**3) Analysis method**  \n
- Reactions and end moments are obtained from the beam-analysis solver for the selected support condition.  \n\n
**4) Result**  \n
- Use solver output reactions/end moments for SFD and BMD construction.
"""
    elif case.startswith("Simple beam"):
        if support_condition_active == "Simply supported":
            step1_summary = (
                f"Step 1 – Support conditions | Simply supported (pin + roller) beam of span $L = {L:.1f}$ m"
            )
            left_txt, right_txt = "pinned", "roller"
        elif support_condition_active == "Pinned–Pinned":
            step1_summary = (
                f"Step 1 – Support conditions | Pinned–pinned (double pin) beam of span $L = {L:.1f}$ m"
            )
            left_txt, right_txt = "pinned", "pinned"
        else:
            step1_summary = (
                f"Step 1 – Support conditions | Determinate single-span beam ($L = {L:.1f}$ m)"
            )
            left_txt, right_txt = "pinned", "pinned"
        step1_md = f"""
**1) Inputs**  \n
- Left support: {left_txt}  \n
- Right support: {right_txt}  \n
- Span: $L = {L:.3g}\\, \\text{{m}}$  \n\n
**2) Governing equations**  \n
- $\\sum V = 0$  \n
- $\\sum M = 0$  \n\n
**3) Substitute / derive**  \n
- Vertical reactions at each support (standard simply supported idealisation for internal actions).  \n\n
**4) Result**  \n
- Proceed to solve for $R_A$ and $R_B$ from equilibrium.
"""
    elif case.startswith("Cantilever"):
        step1_summary = f"Step 1 – Support conditions | Cantilever (fixed–free) beam of span $L = {L:.1f}$ m → fixed end moment and shear at support, zero reactions at free end"
        step1_md = f"""
**1) Inputs**  \n
- Left support: fixed  \n
- Right end: free  \n
- Span: $L = {L:.3g}\\, \\text{{m}}$  \n\n
**2) Governing equations**  \n
- $\\sum V = 0$  \n
- $\\sum M = 0$  \n\n
**3) Substitute / derive**  \n
- A cantilever has a fixed end moment and shear at the support and zero reactions at the free end.  \n\n
**4) Result**  \n
- Proceed to solve for reactions at the fixed end.
"""
    elif case == "Overhanging beam – right overhang with point load at free end":
        L_main = params.get("L_main", L)
        step1_summary = f"Step 1 – Support conditions | Overhanging beam with pinned supports (span $L = {L_main:.1f}$ m) and free overhang end → reactions at pinned supports"
        step1_md = f"""
**1) Inputs**  \n
- Support A (left): pinned  \n
- Support B (internal): pinned at distance $L = {L_main:.3g}\\, \\text{{m}}$ from A  \n
- Right overhang end: free at $x = L + a$  \n\n
**2) Governing equations**  \n
- $\\sum V = 0$  \n
- $\\sum M = 0$  \n\n
**3) Substitute / derive**  \n
- Reactions act at the pinned supports.  \n\n
**4) Result**  \n
- Proceed to solve for $R_A$ and $R_B$ from equilibrium.
"""
    else:
        step1_md = ""
        step1_summary = ""
    
    if step1_md and step1_summary:
        step1_uid = EQ_SLS_UID["step1"]
        step_expander_calcbox(
            uid=step1_uid,
            summary_line=step1_summary,
            details_md=step1_md,
            status=None,
            accent="support",
        )

    solver_case = (
        case == "Multi-span continuous beam"
        or (case.startswith("Simple beam") and fixed_end_indeterminate)
    )
    solver_md = dict(results_local.get("solver_metadata", {})) if isinstance(results_local, dict) else {}
    if solver_case:
        node_positions = [float(v) for v in list(solver_md.get("node_positions_m") or params.get("node_positions_m") or [0.0, float(L)])]
        element_lengths = [float(v) for v in list(solver_md.get("element_lengths_m") or ([node_positions[i + 1] - node_positions[i] for i in range(len(node_positions) - 1)] if len(node_positions) > 1 else []))]
        support_types_solver = list(solver_md.get("support_types") or results_local.get("support_types") or [support_condition_active])
        n_nodes = len(node_positions)
        n_elems = max(0, n_nodes - 1)
        node_text = ",\\ ".join(f"{v:.3g}" for v in node_positions)
        span_text = ",\\ ".join(f"{v:.3g}" for v in element_lengths) if element_lengths else "—"
        support_text = ",\\ ".join(str(s) for s in support_types_solver) if support_types_solver else support_condition_active

        step2a_summary = "Step 2a – Beam model and restraints | Define nodes, spans, supports, and restrained DOFs"
        step2a_md = f"""
{load_intro}\\[
\\text{{Nodes}} = {n_nodes}, \\qquad \\text{{Elements}} = {n_elems}
\\]

\\[
x = [{node_text}]\\,\\text{{m}}, \\qquad L_e = [{span_text}]\\,\\text{{m}}
\\]

\\[
\\text{{Supports}} = [{support_text}]
\\]

{_format_support_restraints(solver_md)}
"""
        step_expander_calcbox(
            uid=EQ_SLS_UID["step2a"],
            summary_line=step2a_summary,
            details_md=step2a_md,
            status=None,
            accent="fe",
        )

        ex_le = float(element_lengths[0]) if element_lengths else float(L)
        step2b_summary = "Step 2b – Element stiffness matrices | Form local beam stiffness for each span"
        step2b_md = f"""
\\[
k_e =
\\frac{{EI}}{{L_e^3}}
\\begin{{bmatrix}}
12 & 6L_e & -12 & 6L_e \\\\
6L_e & 4L_e^2 & -6L_e & 2L_e^2 \\\\
-12 & -6L_e & 12 & -6L_e \\\\
6L_e & 2L_e^2 & -6L_e & 4L_e^2
\\end{{bmatrix}}
\\]

\\[
L_e^{{(example)}} = {ex_le:.3g}\\,\\text{{m}}
\\]
"""
        step_expander_calcbox(
            uid=EQ_SLS_UID["step2b"],
            summary_line=step2b_summary,
            details_md=step2b_md,
            status=None,
            accent="fe",
        )

        gF = list(solver_md.get("global_F", solver_md.get("global_F_preview", [])) or [])
        rF = list(solver_md.get("reduced_F", solver_md.get("reduced_F_preview", [])) or [])
        step2c_summary = "Step 2c – Equivalent nodal actions | Convert applied loads into element load vectors"
        step2c_md = f"""
Applied loads are converted to equivalent nodal actions and assembled.

{_format_solver_vector("F", gF[:10], "kN")}

{_format_solver_vector("F_r", rF[:10], "kN")}
"""
        step_expander_calcbox(
            uid=EQ_SLS_UID["step2c"],
            summary_line=step2c_summary,
            details_md=step2c_md,
            status=None,
            accent="fe",
        )

        rK = solver_md.get("reduced_K", solver_md.get("reduced_K_preview", [])) or []
        rsize = int(solver_md.get("reduced_size", len(rF)))
        step2d_summary = "Step 2d – Global stiffness system | Assemble and reduce the beam stiffness equations"
        step2d_md = f"""
\\[
K u = F, \\qquad K_r u_r = F_r
\\]

\\[
\\dim(K_r) = {rsize}\\times {rsize}
\\]

{_format_solver_matrix("K_r", rK)}

<details>
<summary>Advanced detail: show assembled matrices</summary>

{_format_solver_matrix("K_r", rK, max_rows=8, max_cols=8)}

</details>
"""
        step_expander_calcbox(
            uid=EQ_SLS_UID["step2d"],
            summary_line=step2d_summary,
            details_md=step2d_md,
            status=None,
            accent="fe",
        )

        ru = list(solver_md.get("reduced_u", solver_md.get("reduced_u_preview", [])) or [])
        step2e_summary = "Step 2e – Solved DOFs | Solve nodal rotations/displacements of the restrained beam"
        step2e_md = f"""
{_format_solver_vector("u_r", ru[:12])}

These solved DOFs are used to recover support actions and element-end forces.
"""
        step_expander_calcbox(
            uid=EQ_SLS_UID["step2e"],
            summary_line=step2e_summary,
            details_md=step2e_md,
            status=None,
            accent="fe",
        )

        reactions_solver = dict(results_local.get("reactions", {}))
        if not reactions_solver:
            reactions_solver = {
                "R1": float(results_local.get("R1", 0.0)),
                "R2": float(results_local.get("R2", 0.0)),
                "M1": float(results_local.get("M_left", 0.0)),
                "M2": float(results_local.get("M_right", 0.0)),
            }
        r_terms = []
        m_terms = []
        for key in sorted(reactions_solver.keys()):
            val = float(reactions_solver[key])
            if key.startswith("R"):
                r_terms.append(f"{key} = {val:.3g}\\,\\text{{kN}}")
            elif key.startswith("M") and abs(val) > 1e-9:
                m_terms.append(f"{key} = {val:.3g}\\,\\text{{kNm}}")
        r_line = ", \\qquad ".join(r_terms) if r_terms else "R = 0"
        m_line = ", \\qquad ".join(m_terms)
        step2f_summary = "Step 2f – Recovered reactions and end moments | Recover support actions from the solved beam state"
        step2f_md = f"""
\\[
{r_line}
\\]
{f"\\n\\[{m_line}\\]\\n" if m_line else ""}
Recovered support actions define the final SFD/BMD response.
"""
        step_expander_calcbox(
            uid=EQ_SLS_UID["step2f"],
            summary_line=step2f_summary,
            details_md=step2f_md,
            status=None,
            accent="fe",
        )

    # STEP 2 – reactions (case-by-case)
    step2_md = ""

    if not solver_case and case == "Simple beam – UDL over entire span":
        w = params.get("w", 0.0)
        R = results_local.get("R", w * L / 2.0)
        wL_val = w * L
        
        step2_summary = f"Step 2 – Reactions from equilibrium | Use $\\sum V=0$ and $\\sum M=0$: $R_1 = R_2 = {R:.1f}$ kN"
        step2_md = f"""
{load_intro}**1) Inputs**  \n
- UDL: $w = {w:.3g}\\, \\text{{kN/m}}$  \n
- Span: $L = {L:.3g}\\, \\text{{m}}$  \n
- Total load: $wL = {wL_val:.3g}\\, \\text{{kN}}$  \n\n
**2) Governing equations**  \n
- $\\sum V = 0: \\quad R_1 + R_2 - wL = 0$  \n
- $\\sum M_A = 0: \\quad R_2 L - wL \\cdot \\frac{{L}}{{2}} = 0$  \n\n
**3) Substitute / derive**  \n
From moment equilibrium about A:  \n
$$R_2 = \\frac{{wL}}{{2}} = \\frac{{{w:.3g} \\times {L:.3g}}}{{2}} = \\frac{{{wL_val:.3g}}}{{2}} = {R:.3g}\\, \\text{{kN}}$$  \n
Substituting into vertical equilibrium:  \n
$$R_1 = wL - R_2 = {wL_val:.3g} - {R:.3g} = {R:.3g}\\, \\text{{kN}}$$  \n\n
**4) Result**  \n
$R_1 = R_2 = {R:.3g}\\, \\text{{kN}}$ (both reactions equal for symmetric loading).
"""

    elif case == "Simple beam – point load at centre":
        P = params.get("P", 0.0)
        R1 = results_local.get("R1", P / 2.0)
        
        step2_summary = f"Step 2 – Reactions from equilibrium | Point load $P = {P:.1f}$ kN at midspan: $R_1 = R_2 = {R1:.1f}$ kN"
        step2_md = f"""
{load_intro}**1) Inputs**  \n
- Point load: $P = {P:.3g}\\, \\text{{kN}}$  \n
- Span: $L = {L:.3g}\\, \\text{{m}}$  \n
- Load position: $a = L/2 = {L/2:.3g}\\, \\text{{m}}$ (midspan)  \n\n
**2) Governing equations**  \n
- $\\sum V = 0: \\quad R_1 + R_2 - P = 0$  \n
- $\\sum M_A = 0: \\quad R_2 L - P \\cdot \\frac{{L}}{{2}} = 0$  \n\n
**3) Substitute / derive**  \n
From moment equilibrium about A:  \n
$$R_2 = \\frac{{P}}{{2}} = \\frac{{{P:.3g}}}{{2}} = {R1:.3g}\\, \\text{{kN}}$$  \n
Substituting into vertical equilibrium:  \n
$$R_1 = P - R_2 = {P:.3g} - {R1:.3g} = {R1:.3g}\\, \\text{{kN}}$$  \n\n
**4) Result**  \n
$R_1 = R_2 = {R1:.3g}\\, \\text{{kN}}$ (equal reactions for symmetric loading).
"""

    elif case == "Simple beam – point load at distance a from left":
        P = params.get("P", 0.0)
        a_val = params.get("a")
        if a_val is None:
            a_val = L / 3
        else:
            a_val = float(a_val)
        R1 = results_local.get("R1", P * (L - a_val) / L)
        R2 = results_local.get("R2", P * a_val / L)
        b_val = L - a_val
        
        step2_summary = f"Step 2 – Reactions from equilibrium | Point load $P = {P:.1f}$ kN at $a = {a_val:.1f}$ m: $R_1 = {R1:.1f}$ kN, $R_2 = {R2:.1f}$ kN"
        step2_md = f"""
{load_intro}**1) Inputs**  \n
- Point load: $P = {P:.3g}\\, \\text{{kN}}$  \n
- Span: $L = {L:.3g}\\, \\text{{m}}$  \n
- Distance from left: $a = {a_val:.3g}\\, \\text{{m}}$  \n
- Distance from right: $b = L - a = {b_val:.3g}\\, \\text{{m}}$  \n\n
**2) Governing equations**  \n
- $\\sum V = 0: \\quad R_1 + R_2 - P = 0$  \n
- $\\sum M_A = 0: \\quad R_2 L - P a = 0$  \n\n
**3) Substitute / derive**  \n
From moment equilibrium about A:  \n
$$R_2 = \\frac{{Pa}}{{L}} = \\frac{{{P:.3g} \\times {a_val:.3g}}}{{{L:.3g}}} = \\frac{{{P*a_val:.3g}}}{{{L:.3g}}} = {R2:.3g}\\, \\text{{kN}}$$  \n
Substituting into vertical equilibrium:  \n
$$R_1 = P - R_2 = {P:.3g} - {R2:.3g} = {R1:.3g}\\, \\text{{kN}}$$  \n
Alternatively: $R_1 = \\frac{{Pb}}{{L}} = \\frac{{{P:.3g} \\times {b_val:.3g}}}{{{L:.3g}}} = {R1:.3g}\\, \\text{{kN}}$  \n\n
**4) Result**  \n
$R_1 = {R1:.3g}\\, \\text{{kN}}$, $R_2 = {R2:.3g}\\, \\text{{kN}}$.
"""

    elif case == "Simple beam – partial UDL from left (length a)":
        w = params.get("w", 0.0)
        a_udl = params["a_udl"]
        wa_val = w * a_udl
        R2 = results_local.get("R2", w * a_udl**2 / (2 * L))
        R1 = results_local.get("R1", wa_val - R2)
        
        step2_summary = f"Step 2 – Reactions from equilibrium | Partial UDL $w = {w:.1f}$ kN/m over $a = {a_udl:.1f}$ m: $R_1 = {R1:.1f}$ kN, $R_2 = {R2:.1f}$ kN"
        step2_md = f"""
{load_intro}**1) Inputs**  \n
- UDL: $w = {w:.3g}\\, \\text{{kN/m}}$  \n
- Span: $L = {L:.3g}\\, \\text{{m}}$  \n
- UDL length: $a = {a_udl:.3g}\\, \\text{{m}}$  \n
- Total partial load: $wa = {wa_val:.3g}\\, \\text{{kN}}$  \n\n
**2) Governing equations**  \n
- $\\sum V = 0: \\quad R_1 + R_2 - wa = 0$  \n
- $\\sum M_A = 0: \\quad R_2 L - wa \\cdot \\frac{{a}}{{2}} = 0$  \n\n
**3) Substitute / derive**  \n
From moment equilibrium about A:  \n
$$R_2 = \\frac{{wa^2}}{{2L}} = \\frac{{{w:.3g} \\times {a_udl:.3g}^2}}{{2 \\times {L:.3g}}} = \\frac{{{w*a_udl**2:.3g}}}{{{2*L:.3g}}} = {R2:.3g}\\, \\text{{kN}}$$  \n
Substituting into vertical equilibrium:  \n
$$R_1 = wa - R_2 = {wa_val:.3g} - {R2:.3g} = {R1:.3g}\\, \\text{{kN}}$$  \n\n
**4) Result**  \n
$R_1 = {R1:.3g}\\, \\text{{kN}}$, $R_2 = {R2:.3g}\\, \\text{{kN}}$.
"""

    elif case == "Simple beam – multiple point loads":
        point_loads = list(params.get("point_loads") or [])
        point_loads = sorted(point_loads, key=lambda row: float(row.get("x_m", 0.0)))
        total_P = sum(float(row.get("P_kN", 0.0) or 0.0) for row in point_loads)
        total_MA = sum(
            float(row.get("P_kN", 0.0) or 0.0) * _clamp_x(float(row.get("x_m", 0.0) or 0.0), float(L))
            for row in point_loads
        )
        R1 = results_local.get("R1", 0.0)
        R2 = results_local.get("R2", 0.0)
        step2_summary = (
            f"Step 2 – Reactions from equilibrium | {len(point_loads)} point loads: "
            f"$R_1 = {R1:.1f}$ kN, $R_2 = {R2:.1f}$ kN"
        )
        rows_md = "\n".join(
            f"- P{i}: $P_{{{i}}} = {float(row.get('P_kN', 0.0) or 0.0):.3g}\\,\\text{{kN}}$ at "
            f"$x_{{{i}}} = {_clamp_x(float(row.get('x_m', 0.0) or 0.0), float(L)):.3g}\\,\\text{{m}}$"
            for i, row in enumerate(point_loads, start=1)
        ) or "- No point loads defined."
        step2_md = f"""
{load_intro}**1) Inputs**  \n
{rows_md}  \n
- Span: $L = {L:.3g}\\,\\text{{m}}$  \n
- Total point load: $\\sum P_i = {total_P:.3g}\\,\\text{{kN}}$  \n
- Moment of loads about A: $\\sum P_i x_i = {total_MA:.3g}\\,\\text{{kNm}}$  \n\n
**2) Governing equations**  \n
- $\\sum V = 0: \\quad R_1 + R_2 - \\sum P_i = 0$  \n
- $\\sum M_A = 0: \\quad R_2 L - \\sum(P_i x_i) = 0$  \n\n
**3) Numerical result**  \n
- $R_1 = {R1:.3g}\\,\\text{{kN}}$  \n
- $R_2 = {R2:.3g}\\,\\text{{kN}}$  \n\n
**4) Note**  \n
Detailed symbolic expansion for arbitrary point-load lists is omitted in this phase.
"""

    elif case == "Cantilever – point load at free end":
        P = params.get("P", 0.0)
        V_fixed = P
        M_fixed = P * L
        
        step2_summary = f"Step 2 – Reactions from equilibrium | Point load $P = {P:.1f}$ kN at free end: $V = {V_fixed:.1f}$ kN, $M = {M_fixed:.1f}$ kNm (hogging)"
        step2_md = f"""
{load_intro}**1) Inputs**  \n
- Point load: $P = {P:.3g}\\, \\text{{kN}}$  \n
- Span: $L = {L:.3g}\\, \\text{{m}}$  \n\n
**2) Governing equations**  \n
- $\\sum V = 0: \\quad V_{{\\text{{fixed}}}} - P = 0$  \n
- $\\sum M_{{\\text{{fixed}}}} = 0: \\quad M_{{\\text{{fixed}}}} - P L = 0$  \n\n
**3) Substitute / derive**  \n
From vertical equilibrium:  \n
$$V_{{\\text{{fixed}}}} = P = {P:.3g}\\, \\text{{kN}}$$  \n
From moment equilibrium:  \n
$$M_{{\\text{{fixed}}}} = P L = {P:.3g} \\times {L:.3g} = {M_fixed:.3g}\\, \\text{{kNm}}$$  \n\n
**4) Result**  \n
At the fixed support: shear = $V = {V_fixed:.3g}\\, \\text{{kN}}$ (upward), hogging moment = $M = {M_fixed:.3g}\\, \\text{{kNm}}$.
"""

    elif case == "Cantilever – point load at distance a from fixed end":
        P = params.get("P", 0.0)
        a_cant = params["a_cant"]
        V_fixed = P
        M_fixed = P * a_cant
        
        step2_summary = f"Step 2 – Reactions from equilibrium | Point load $P = {P:.1f}$ kN at $a = {a_cant:.1f}$ m: $V = {V_fixed:.1f}$ kN, $M = {M_fixed:.1f}$ kNm (hogging)"
        step2_md = f"""
{load_intro}**1) Inputs**  \n
- Point load: $P = {P:.3g}\\, \\text{{kN}}$  \n
- Span: $L = {L:.3g}\\, \\text{{m}}$  \n
- Distance from fixed end: $a = {a_cant:.3g}\\, \\text{{m}}$  \n\n
**2) Governing equations**  \n
- $\\sum V = 0: \\quad V_{{\\text{{fixed}}}} - P = 0$  \n
- $\\sum M_{{\\text{{fixed}}}} = 0: \\quad M_{{\\text{{fixed}}}} - P a = 0$  \n\n
**3) Substitute / derive**  \n
From vertical equilibrium:  \n
$$V_{{\\text{{fixed}}}} = P = {P:.3g}\\, \\text{{kN}}$$  \n
From moment equilibrium:  \n
$$M_{{\\text{{fixed}}}} = P a = {P:.3g} \\times {a_cant:.3g} = {M_fixed:.3g}\\, \\text{{kNm}}$$  \n\n
**4) Result**  \n
At the fixed support: shear = $V = {V_fixed:.3g}\\, \\text{{kN}}$ (upward), hogging moment = $M = {M_fixed:.3g}\\, \\text{{kNm}}$.
"""

    elif case == "Cantilever – multiple point loads":
        point_loads = list(params.get("point_loads") or [])
        point_loads = sorted(point_loads, key=lambda row: float(row.get("x_m", 0.0)))
        total_P = sum(float(row.get("P_kN", 0.0) or 0.0) for row in point_loads)
        total_M_fixed = sum(
            float(row.get("P_kN", 0.0) or 0.0) * _clamp_x(float(row.get("x_m", 0.0) or 0.0), float(L))
            for row in point_loads
        )
        V_fixed = results_local.get("V_fixed", total_P)
        M_fixed = results_local.get("M_fixed", total_M_fixed)
        step2_summary = (
            f"Step 2 – Reactions from equilibrium | {len(point_loads)} point loads: "
            f"$V_{{fixed}} = {V_fixed:.1f}$ kN, $M_{{fixed}} = {M_fixed:.1f}$ kNm"
        )
        rows_md = "\n".join(
            f"- P{i}: $P_{{{i}}} = {float(row.get('P_kN', 0.0) or 0.0):.3g}\\,\\text{{kN}}$ at "
            f"$x_{{{i}}} = {_clamp_x(float(row.get('x_m', 0.0) or 0.0), float(L)):.3g}\\,\\text{{m}}$"
            for i, row in enumerate(point_loads, start=1)
        ) or "- No point loads defined."
        step2_md = f"""
{load_intro}**1) Inputs**  \n
{rows_md}  \n
- Span: $L = {L:.3g}\\,\\text{{m}}$  \n
- Total point load: $\\sum P_i = {total_P:.3g}\\,\\text{{kN}}$  \n
- Total moment about fixed end: $\\sum(P_i x_i) = {total_M_fixed:.3g}\\,\\text{{kNm}}$  \n\n
**2) Governing equations**  \n
- $\\sum V = 0: \\quad V_{{fixed}} - \\sum P_i = 0$  \n
- $\\sum M_{{fixed}} = 0: \\quad M_{{fixed}} - \\sum(P_i x_i) = 0$  \n\n
**3) Numerical result**  \n
- $V_{{fixed}} = {V_fixed:.3g}\\,\\text{{kN}}$  \n
- $M_{{fixed}} = {M_fixed:.3g}\\,\\text{{kNm}}$ (hogging)  \n\n
**4) Note**  \n
Detailed symbolic expansion for arbitrary point-load lists is omitted in this phase.
"""

    elif case == "Cantilever – UDL over entire span":
        w = params.get("w", 0.0)
        wL_val = w * L
        V_fixed = wL_val
        M_fixed = w * L**2 / 2.0
        
        step2_summary = f"Step 2 – Reactions from equilibrium | UDL $w = {w:.1f}$ kN/m over $L = {L:.1f}$ m: $V = {V_fixed:.1f}$ kN, $M = {M_fixed:.1f}$ kNm (hogging)"
        step2_md = f"""
{load_intro}**1) Inputs**  \n
- UDL: $w = {w:.3g}\\, \\text{{kN/m}}$  \n
- Span: $L = {L:.3g}\\, \\text{{m}}$  \n
- Total load: $wL = {wL_val:.3g}\\, \\text{{kN}}$  \n\n
**2) Governing equations**  \n
- $\\sum V = 0: \\quad V_{{\\text{{fixed}}}} - wL = 0$  \n
- $\\sum M_{{\\text{{fixed}}}} = 0: \\quad M_{{\\text{{fixed}}}} - wL \\cdot \\frac{{L}}{{2}} = 0$  \n\n
**3) Substitute / derive**  \n
From vertical equilibrium:  \n
$$V_{{\\text{{fixed}}}} = wL = {w:.3g} \\times {L:.3g} = {V_fixed:.3g}\\, \\text{{kN}}$$  \n
From moment equilibrium:  \n
$$M_{{\\text{{fixed}}}} = \\frac{{wL^2}}{{2}} = \\frac{{{w:.3g} \\times {L:.3g}^2}}{{2}} = \\frac{{{w*L**2:.3g}}}{{2}} = {M_fixed:.3g}\\, \\text{{kNm}}$$  \n\n
**4) Result**  \n
At the fixed support: shear = $V = {V_fixed:.3g}\\, \\text{{kN}}$ (upward), hogging moment = $M = {M_fixed:.3g}\\, \\text{{kNm}}$.
"""

    elif case == "Overhanging beam – right overhang with point load at free end":
        P = params.get("P", 0.0)
        L_main = params.get("L_main", L)
        a_over = params.get("a_overhang", 0.0)
        RA = results_local.get("RA", -P * a_over / L_main)
        RB = results_local.get("RB", P * (L_main + a_over) / L_main)
        L_plus_a = L_main + a_over
        
        step2_summary = f"Step 2 – Reactions from equilibrium | Point load $P = {P:.1f}$ kN on overhang: $R_A = {RA:.1f}$ kN, $R_B = {RB:.1f}$ kN"
        step2_md = f"""
{load_intro}**1) Inputs**  \n
- Point load: $P = {P:.3g}\\, \\text{{kN}}$  \n
- Span between supports: $L = {L_main:.3g}\\, \\text{{m}}$  \n
- Overhang length: $a = {a_over:.3g}\\, \\text{{m}}$  \n
- Total distance: $L + a = {L_plus_a:.3g}\\, \\text{{m}}$  \n\n
**2) Governing equations**  \n
- $\\sum V = 0: \\quad R_A + R_B - P = 0$  \n
- $\\sum M_A = 0: \\quad R_B L - P(L+a) = 0$  \n\n
**3) Substitute / derive**  \n
From moment equilibrium about A:  \n
$$R_B = \\frac{{P(L+a)}}{{L}} = \\frac{{{P:.3g} \\times {L_plus_a:.3g}}}{{{L_main:.3g}}} = \\frac{{{P*L_plus_a:.3g}}}{{{L_main:.3g}}} = {RB:.3g}\\, \\text{{kN}}$$  \n
Substituting into vertical equilibrium:  \n
$$R_A = P - R_B = {P:.3g} - {RB:.3g} = {RA:.3g}\\, \\text{{kN}}$$  \n
Note: $R_A$ is negative (downward) when the overhang load creates upward reaction at B.  \n\n
**4) Result**  \n
$R_A = {RA:.3g}\\, \\text{{kN}}$ (downward), $R_B = {RB:.3g}\\, \\text{{kN}}$ (upward).
"""

    # STEP 2 – Reactions (expandable)
    step2_summary_exists = False
    try:
        _ = step2_summary
        step2_summary_exists = True
    except NameError:
        pass
    
    if step2_md and step2_summary_exists:
        step2_uid = EQ_SLS_UID["step2"]
        # Remove any summary line from details if present
        step2_details = step2_md
        if "*Two-line summary:*" in step2_details or "**Step 2 – Reactions from equilibrium**" in step2_details.split("\n")[0]:
            lines = step2_details.split("\n")
            new_lines = []
            skip_next = False
            for i, line in enumerate(lines):
                if "*Two-line summary:*" in line or (i == 0 and "**Step 2" in line):
                    skip_next = True
                    continue
                if skip_next and line.strip() == "":
                    skip_next = False
                    continue
                if not skip_next:
                    new_lines.append(line)
            step2_details = "\n".join(new_lines).strip()
        
        step_expander_calcbox(
            uid=step2_uid,
            summary_line=step2_summary,
            details_md=step2_details,
            status=None,
            accent="reaction",
        )

    # STEP 3 – shear function V(x)
    step3_md = ""

    if case == "Multi-span continuous beam":
        step3_summary = (
            "Step 3 – Shear function $V(x)$ | Build $V(x)$ from solved reactions and applied loads"
        )
        step3_md = """
\\[
V(x) = V_{\\mathrm{solver}}(x)
\\]

Internal shears are recovered at the same stations as the plotted SFD from the multi-span numerical beam solution.
"""
    elif case.startswith("Simple beam") and fixed_end_indeterminate:
        step3_summary = (
            "Step 3 – Shear function $V(x)$ | Build $V(x)$ from solved reactions and applied loads"
        )
        step3_md = f"""
\\[
V(x) = V_{{\\mathrm{{solver}}}}(x)
\\]

For the {support_condition_active.lower()} indeterminate support layout, $V(x)$ is **not** a single textbook closed form for arbitrary loads; ordinates come from the numerical beam solver and match the SFD plot.
"""
    elif case == "Simple beam – UDL over entire span":
        w = float(params.get("w", 0.0) or 0.0)
        R = float(results_local.get("R", w * L / 2.0))
        V_at_0 = R
        V_at_L = -R
        if abs(w) < 1e-9:
            x_zero_crossing = None
        else:
            x_zero_crossing = R / w

        if x_zero_crossing is not None:
            zero_crossing_md = (
                f"Zero crossing at: $x = \\frac{{R_1}}{{w}} = \\frac{{{R:.3g}}}{{{w:.3g}}} = "
                f"{x_zero_crossing:.3g}\\, \\text{{m}}$ (midspan)  \n\n"
            )
            step3_summary = (
                f"Step 3 – Shear function $V(x)$ | UDL $w = {w:.1f}$ kN/m: "
                f"$V(0) = {V_at_0:.1f}$ kN, $V(L) = {V_at_L:.1f}$ kN, zero at midspan"
            )
            result_shear_md = (
                f"$V(x) = {R:.3g} - {w:.3g}x$ for $0 \\le x \\le L$. "
                f"Linear diagram crossing zero at midspan."
            )
        else:
            zero_crossing_md = (
                "**No zero crossing** ($w \\approx 0$): with no distributed load, "
                "$V(x)=R_1$ is **constant**, $M(x)$ is **linear**, and there is no parabolic "
                "shear contribution from a UDL.  \n\n"
                "*No distributed load $\\rightarrow$ no parabolic shear diagram.*  \n\n"
            )
            step3_summary = (
                f"Step 3 – Shear function $V(x)$ | $w \\approx 0$: "
                f"$V(0) = {V_at_0:.1f}$ kN, $V(L) = {V_at_L:.1f}$ kN (constant shear)"
            )
            result_shear_md = (
                f"$V(x) = {R:.3g}$ for $0 \\le x \\le L$ (constant shear; $w \\approx 0$)."
            )

        step3_md = f"""
{load_intro}**1) Inputs**  \n
- Reactions: $R_1 = R_2 = {R:.3g}\\, \\text{{kN}}$  \n
- UDL: $w = {w:.3g}\\, \\text{{kN/m}}$  \n
- Span: $L = {L:.3g}\\, \\text{{m}}$  \n\n
**2) Governing equations**  \n
- $\\frac{{\\mathrm{{d}}V}}{{\\mathrm{{d}}x}} = -w(x)$  \n
- For UDL: $V(x) = R_1 - wx$  \n\n
**3) Substitute / derive**  \n
Taking sections from the left:  \n
$$V(x) = R_1 - wx = {R:.3g} - {w:.3g} x, \\quad 0 \\le x \\le L$$  \n
At $x = 0$: $V(0) = {R:.3g} - 0 = {V_at_0:.3g}\\, \\text{{kN}}$  \n
At $x = L$: $V(L) = {R:.3g} - {w:.3g} \\times {L:.3g} = {R:.3g} - {w*L:.3g} = {V_at_L:.3g}\\, \\text{{kN}}$  \n
{zero_crossing_md}**4) Result**  \n
{result_shear_md}
"""

    elif case == "Simple beam – point load at centre":
        P = params.get("P", 0.0)
        R1 = results_local.get("R1", P / 2.0)
        step3_md = f"""
{load_intro}Let \\(a = L/2\\). For a centre point load:

\\[
V(x) = 
\\begin{{cases}}
R_1 & 0 \\le x < a\\\\
R_1 - P & a < x \\le L
\\end{{cases}}
\\]

with \\(R_1 = P/2 = {R1:.3g}\\,\\text{{kN}}\\).
"""

    elif case == "Simple beam – point load at distance a from left":
        P = params.get("P", 0.0)
        a_val = params.get("a")
        if a_val is None:
            a_val = L / 3
        else:
            a_val = float(a_val)
        R1 = results_local.get("R1", 0.0)
        step3_md = f"""
{load_intro}\\[
V(x) = 
\\begin{{cases}}
R_1 & 0 \\le x < a\\\\
R_1 - P & a < x \\le L
\\end{{cases}}
\\]

with \\(R_1 = {R1:.3g}\\,\\text{{kN}}\\) and \\(a = {a_val:.3g}\\,\\text{{m}}\\).
"""

    elif case == "Simple beam – multiple point loads":
        point_loads = list(params.get("point_loads") or [])
        point_loads = sorted(point_loads, key=lambda row: float(row.get("x_m", 0.0)))
        R1 = results_local.get("R1", 0.0)
        point_list = ", ".join(
            f"({float(row.get('x_m', 0.0) or 0.0):.2f} m, {float(row.get('P_kN', 0.0) or 0.0):.2f} kN)"
            for row in point_loads
        ) or "none"
        step3_summary = (
            f"Step 3 – Shear function $V(x)$ | Piecewise constant with jumps at each point load "
            f"(R1 = {R1:.1f} kN)"
        )
        step3_md = f"""
{load_intro}For multiple concentrated loads on a simply supported beam:

- Start from left reaction $R_1 = {R1:.3g}\\,\\text{{kN}}$.
- At each point load location, $V(x)$ drops by that load magnitude.
- Between load points, $V(x)$ is constant.

Load set \\((x_i, P_i)\\): {point_list}.
"""

    elif case == "Simple beam – partial UDL from left (length a)":
        w = params.get("w", 0.0)
        a_udl = params["a_udl"]
        R1 = results_local.get("R1", 0.0)
        step3_md = f"""
{load_intro}\\[
V(x) = 
\\begin{{cases}}
R_1 - w x & 0 \\le x \\le a\\\\
R_1 - w a & a \\le x \\le L
\\end{{cases}}
\\]

with \\(R_1 = {R1:.3g}\\,\\text{{kN}}\\), \\(w = {w:.3g}\\,\\text{{kN/m}}\\), and \\(a = {a_udl:.3g}\\,\\text{{m}}\\).
"""

    elif case == "Cantilever – point load at free end":
        P = params.get("P", 0.0)
        step3_md = f"""
{load_intro}\\[
V(x) = -P, \\quad 0 \\le x \\le L
\\]

The shear is constant (negative, indicating downward) along the entire length.
"""

    elif case == "Cantilever – point load at distance a from fixed end":
        P = params.get("P", 0.0)
        a_cant = params["a_cant"]
        step3_md = f"""
{load_intro}\\[
V(x) = 
\\begin{{cases}}
-P & 0 \\le x \\le a\\\\
0 & a \\le x \\le L
\\end{{cases}}
\\]

The shear is constant (negative) from the fixed end to the load position, then zero beyond.
"""

    elif case == "Cantilever – multiple point loads":
        point_loads = list(params.get("point_loads") or [])
        point_loads = sorted(point_loads, key=lambda row: float(row.get("x_m", 0.0)))
        point_list = ", ".join(
            f"({float(row.get('x_m', 0.0) or 0.0):.2f} m, {float(row.get('P_kN', 0.0) or 0.0):.2f} kN)"
            for row in point_loads
        ) or "none"
        step3_summary = (
            "Step 3 – Shear function $V(x)$ | Built from right-side load resultant for each section"
        )
        step3_md = f"""
{load_intro}For a cantilever with multiple point loads:

- At any section $x$, shear equals the negative of the total downward point load to the right of the cut.
- Therefore, $V(x)$ is piecewise constant and steps upward toward zero as you move to the free end.

Load set \\((x_i, P_i)\\): {point_list}.
"""

    elif case == "Cantilever – UDL over entire span":
        w = params.get("w", 0.0)
        step3_md = f"""
{load_intro}\\[
V(x) = -w(L-x), \\quad 0 \\le x \\le L
\\]

The shear increases linearly from \\(-wL\\) at the fixed end to zero at the free end.
"""

    # STEP 3 – Shear function (expandable)
    _vm_section_committed = bool(get_param("design_section_committed", False))
    _vm_design_x_m = float(get_param("design_section_x_m", 0.0) or 0.0)
    step3_summary_exists = False
    try:
        _ = step3_summary
        step3_summary_exists = True
    except NameError:
        step3_summary = (
            "Step 3 – Shear function $V(x)$ | Build $V(x)$ from solved reactions and applied loads"
        )
        step3_summary_exists = True

    if step3_summary_exists:
        step3_uid = EQ_SLS_UID["step3"]
        step3_details = _format_sfd_shear_derivation_panel_md(
            load_intro=load_intro,
            active_mode=active_mode,
            case=case,
            support_condition_active=support_condition_active,
            fixed_end_indeterminate=fixed_end_indeterminate,
            span_m=float(beam_length),
            design_actions_source=design_actions_source,
            section_committed=_vm_section_committed,
            design_x_m=_vm_design_x_m,
            V_array=V,
            case_specific_md=step3_md or "",
        )
        step_expander_calcbox(
            uid=step3_uid,
            summary_line=step3_summary,
            details_md=step3_details,
            status=None,
            accent="shear",
        )

    # STEP 4 – moment function M(x)
    step4_md = ""

    if case == "Multi-span continuous beam":
        step4_summary = (
            "Step 4 – Moment function $M(x)$ | Recover $M(x)$ from the solved beam response"
        )
        step4_md = """
\\[
M(x) = M_{\\mathrm{solver}}(x)
\\]

Internal bending moments are recovered at the same stations as the plotted BMD from the multi-span numerical beam solution.
"""
    elif case.startswith("Simple beam") and fixed_end_indeterminate:
        step4_summary = (
            "Step 4 – Moment function $M(x)$ | Recover $M(x)$ from the solved beam response"
        )
        step4_md = f"""
\\[
M(x) = M_{{\\mathrm{{solver}}}}(x)
\\]

For the {support_condition_active.lower()} indeterminate layout, $M(x)$ is obtained from the numerical beam solution (not a single closed-form expression for arbitrary loads); ordinates match the BMD plot.
"""
    elif case == "Simple beam – UDL over entire span":
        w = params.get("w", 0.0)
        R = results_local.get("R", w * L / 2.0)
        M_max = w * L**2 / 8.0
        step4_md = f"""
**Step 4 – Moment function \\(M(x)\\)**
{load_intro}Integrating the shear:

\\[
M(x) = R_1 x - \\frac{{w x^2}}{{2}},
\\quad 0 \\le x \\le L
\\]

Maximum sagging moment occurs at midspan:

\\[
M_{{\\max}} = \\frac{{wL^2}}{{8}} = {M_max:.3g}\\,\\text{{kNm}} \\text{{ at }} x = \\frac{{L}}{{2}}
\\]
"""

    elif case == "Simple beam – point load at centre":
        P = params.get("P", 0.0)
        M_max = P * L / 4.0
        step4_md = f"""
**Step 4 – Moment function \\(M(x)\\)**
{load_intro}\\[
M(x) = 
\\begin{{cases}}
R_1 x & 0 \\le x \\le a\\\\
R_1 x - P(x-a) & a \\le x \\le L
\\end{{cases}}
\\]

with \\(R_1 = P/2\\), so \\(M_{{\\max}} = PL/4 = {M_max:.3g}\\,\\text{{kNm}}\\) at midspan.
"""

    elif case == "Simple beam – point load at distance a from left":
        P = params.get("P", 0.0)
        a_val = params.get("a")
        if a_val is None:
            a_val = L / 3
        else:
            a_val = float(a_val)
        R1 = results_local.get("R1", 0.0)
        M_max = R1 * a_val
        step4_md = f"""
**Step 4 – Moment function \\(M(x)\\)**
{load_intro}\\[
M(x) = 
\\begin{{cases}}
R_1 x & 0 \\le x \\le a\\\\
R_1 x - P(x-a) & a \\le x \\le L
\\end{{cases}}
\\]

Maximum moment occurs at the load position:

\\[
M_{{\\max}} = R_1 a = {M_max:.3g}\\,\\text{{kNm}} \\text{{ at }} x = {a_val:.3g}\\,\\text{{m}}
\\]
"""

    elif case == "Simple beam – multiple point loads":
        point_loads = list(params.get("point_loads") or [])
        point_loads = sorted(point_loads, key=lambda row: float(row.get("x_m", 0.0)))
        point_list = ", ".join(
            f"({float(row.get('x_m', 0.0) or 0.0):.2f} m, {float(row.get('P_kN', 0.0) or 0.0):.2f} kN)"
            for row in point_loads
        ) or "none"
        step4_summary = (
            "Step 4 – Moment function $M(x)$ | Piecewise linear from integrating piecewise-constant shear"
        )
        step4_md = f"""
**Step 4 – Moment function \\(M(x)\\)**
{load_intro}For multiple point loads, the bending moment is obtained by integrating the piecewise-constant shear:

- $M(x)$ is linear between adjacent load positions.
- Slope changes occur at each point load location.
- The maximum absolute moment is read directly from the solved diagram arrays.

Load set \\((x_i, P_i)\\): {point_list}.
"""

    elif case == "Simple beam – partial UDL from left (length a)":
        w = params.get("w", 0.0)
        a_udl = params["a_udl"]
        R1 = results_local.get("R1", 0.0)
        step4_md = f"""
**Step 4 – Moment function \\(M(x)\\)**
{load_intro}\\[
M(x) = 
\\begin{{cases}}
R_1 x - \\frac{{w x^2}}{{2}} & 0 \\le x \\le a\\\\
R_1 x - w a \\left(x - \\frac{{a}}{{2}}\\right) & a \\le x \\le L
\\end{{cases}}
\\]

Maximum moment occurs within the loaded region or at the end of the UDL.
"""

    elif case == "Cantilever – point load at free end":
        P = params.get("P", 0.0)
        M_max = P * L
        step4_md = f"""
**Step 4 – Moment function \\(M(x)\\)**
{load_intro}\\[
M(x) = -P(L-x), \\quad 0 \\le x \\le L
\\]

Maximum hogging moment occurs at the fixed end:

\\[
M_{{\\max}} = PL = {M_max:.3g}\\,\\text{{kNm}} \\text{{ (hogging at fixed end)}}
\\]
"""

    elif case == "Cantilever – point load at distance a from fixed end":
        P = params.get("P", 0.0)
        a_cant = params["a_cant"]
        M_max = P * a_cant
        step4_md = f"""
**Step 4 – Moment function \\(M(x)\\)**
{load_intro}\\[
M(x) = 
\\begin{{cases}}
-P(a-x) & 0 \\le x \\le a\\\\
0 & a \\le x \\le L
\\end{{cases}}
\\]

Maximum hogging moment occurs at the fixed end:

\\[
M_{{\\max}} = P a = {M_max:.3g}\\,\\text{{kNm}} \\text{{ (hogging at fixed end)}}
\\]
"""

    elif case == "Cantilever – multiple point loads":
        point_loads = list(params.get("point_loads") or [])
        point_loads = sorted(point_loads, key=lambda row: float(row.get("x_m", 0.0)))
        point_list = ", ".join(
            f"({float(row.get('x_m', 0.0) or 0.0):.2f} m, {float(row.get('P_kN', 0.0) or 0.0):.2f} kN)"
            for row in point_loads
        ) or "none"
        step4_summary = (
            "Step 4 – Moment function $M(x)$ | Right-side section equilibrium gives piecewise-linear hogging moment"
        )
        step4_md = f"""
**Step 4 – Moment function \\(M(x)\\)**
{load_intro}For a cantilever with multiple point loads:

- At section $x$, moment equals the negative moment of all right-side loads about that section.
- $M(x)$ is piecewise linear and tends to zero at the free end.
- Maximum absolute moment typically occurs near the fixed end and is taken from the solved arrays.

Load set \\((x_i, P_i)\\): {point_list}.
"""

    elif case == "Cantilever – UDL over entire span":
        w = params.get("w", 0.0)
        M_max = w * L**2 / 2.0
        step4_md = f"""
**Step 4 – Moment function \\(M(x)\\)**
{load_intro}\\[
M(x) = -\\frac{{w}}{{2}}(L-x)^2, \\quad 0 \\le x \\le L
\\]

Maximum hogging moment occurs at the fixed end:

\\[
M_{{\\max}} = \\frac{{wL^2}}{{2}} = {M_max:.3g}\\,\\text{{kNm}} \\text{{ (hogging at fixed end)}}
\\]
"""

    # STEP 4 – Moment function (expandable)
    step4_summary_exists = False
    try:
        _ = step4_summary
        step4_summary_exists = True
    except NameError:
        step4_summary = (
            "Step 4 – Moment function $M(x)$ | Recover $M(x)$ from the solved beam response"
        )
        step4_summary_exists = True

    if step4_summary_exists:
        step4_uid = EQ_SLS_UID["step4"]
        step4_details = _format_sfd_moment_derivation_panel_md(
            load_intro=load_intro,
            active_mode=active_mode,
            case=case,
            support_condition_active=support_condition_active,
            fixed_end_indeterminate=fixed_end_indeterminate,
            span_m=float(beam_length),
            design_actions_source=design_actions_source,
            section_committed=_vm_section_committed,
            design_x_m=_vm_design_x_m,
            M_array=M,
            case_specific_md=step4_md or "",
        )
        step_expander_calcbox(
            uid=step4_uid,
            summary_line=step4_summary,
            details_md=step4_details,
            status=None,
            accent="moment",
        )

    # Push SFD/BMD results into shared state
    # (use key names expected by Inputs page)
    update_results(
        sfd_case=case,                  # store current teaching case
        sfd_Msls_max_kNm=float(M_sls),
        sfd_Vsls_max_kN=float(V_sls),
        sfd_Mmax_abs_kNm=float(M_uls),
        sfd_Vmax_abs_kN=float(V_uls),
        M_pos_max_uls_kNm=float(M_pos_max_uls),
        M_neg_min_uls_kNm=float(M_neg_min_uls),
        M_pos_max_sls_kNm=float(M_pos_max_sls),
        M_neg_min_sls_kNm=float(M_neg_min_sls),
        shear_x=x_uls_list,
        shear_V=[float(abs(v)) for v in (V_uls_vals.tolist() if hasattr(V_uls_vals, "tolist") else list(V_uls_vals))],
        shear_V_signed=[float(v) for v in (V_uls_vals.tolist() if hasattr(V_uls_vals, "tolist") else list(V_uls_vals))],
        shear_M_uls_kNm=[float(v) for v in Mu.tolist()],
        shear_M_sls_kNm=[float(v) for v in M_sls_on_xu.tolist()] if M_sls_on_xu.size == xu.size else [],
        moment_x=x_uls_list,
        moment_values=[float(v) for v in M_sls_on_xu.tolist()] if M_sls_on_xu.size == xu.size else [],
        crack_bmd_cache_fingerprint=_fp,
        bmd_support_positions_m=sup_pos,
        bmd_support_types=sup_types,
        support_type=support_type_key,
        critical_shear_x=x_crit,
        critical_shear_V=V_crit,
        V_max=float(np.max(np.abs(V_uls_vals))) if V_uls_vals is not None and len(V_uls_vals) else 0.0,
    )

    # Bind JS click/scroll after all steps render
    bind_summary_clicks()
