"""Extracted design inputs section helpers."""

from __future__ import annotations


def bind_runtime(namespace: dict) -> None:
    """Bind page dependencies after the coordinator imports all sections."""
    globals().update({key: value for key, value in namespace.items() if not key.startswith("__")})


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
    col_label, col_input = st.columns(
        [label_col_ratio, input_col_ratio], vertical_alignment="center"
    )
    with col_label:
        st.markdown(
            f"<div style=\"padding-top: 0.35rem; padding-bottom: 0.15rem; font-size: 1rem; font-weight: 500;\">{label}</div>",
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
        return st.selectbox(
            label="",
            key=key,
            options=options,
            index=current_index,
            help=help_text,
            disabled=disabled,
            label_visibility="collapsed",
            on_change=on_change_callback,
        )

