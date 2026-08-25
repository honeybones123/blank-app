# shrinkage_page.py
# ============================
# SHRINKAGE – AS 3600:2018 Cl. 3.1.7
# ============================

import math
import streamlit as st

from state_runtime_gateway import (
    get_param,
    get_sync_callbacks,
    update_results,  # kept for contract
)
from widgets_helpers import apply_result_page_css, number_row, v2_number_input, v2_selectbox, render_page_explainer_expander, render_result_page_title, render_section_title, page_divider, render_plotly_diagram, COMPACT_SIDE_VIEW_HEIGHT_PX, compact_side_view_figure, inject_compact_side_view_spacing
from step_ui import render_expandable_step
from engineering_check_ui import PARAMETRIC_RESULT_COLUMNS
from ui.summary_rows import build_shrinkage_summary_rows
from ui_seamless_steps import render_clickable_summary_table, bind_summary_clicks, inject_seamless_steps_css
from jump_nav import scroll_to_jump_after_render
from section_layout import compute_section_layout
from ui.diagrams.creep_shrinkage_diagram import build_shrinkage_side_view_result
from calculations.creep_shrinkage import (
    SHRINKAGE_ENV_LABELS as _ENV_LABELS,
    autogenous_shrinkage_final_from_current,
    calc_eps_cse,
    calc_k1_shrinkage,
    exposed_perimeter_geometry_values,
    shrinkage_total_values,
    shrinkage_closest_fc_row as _closest_fc_row,
    shrinkage_closest_th as _closest_th,
    shrinkage_eps_final as _shrinkage_eps_final,
)
from inputs_application.time_dependent_engineering_state import (
    resolve_time_dependent_engineering_state,
)
from inputs_application.authoritative_check_packs import current_authoritative_family
from inputs_application.time_dependent_presentation import (
    resolve_time_dependent_family_values,
)
from engineering_page_sections.compact_check_inputs import (
    CheckInputCategory,
    CheckInputPanelConfig,
    format_dimensions,
    format_number,
    join_summary,
    render_compact_check_inputs,
)
from application.contracts.concrete_crack_shrinkage import (
    CementClass,
    EC2C766ShrinkageInput,
    ShrinkageMethod,
)
from calculations.concrete_crack_shrinkage_methods import calculate_ec2_c766_shrinkage


SHRINKAGE_METHOD_LABELS = {
    ShrinkageMethod.EXISTING_AS3600.value: "Existing StructuralBase method (AS 3600:2018)",
    ShrinkageMethod.EC2_C766.value: "EC2 equation method (CIRIA C766 Appendices A3-A4)",
}


# ------------------------------------------------------------
#  Small helpers / shared styling
# ------------------------------------------------------------
def _seed_from_param(name: str, fallback: float) -> float:
    """Seed default widget values from shared state, with safe fallback."""
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


def _inject_calcbox_css():
    """Style markdown blockquotes as blue calc boxes (same feel as shear/deflection)."""
    st.markdown(
        """
<style>
blockquote {
  border-left: 4px solid #1f77b4 !important;
  background-color: rgba(31, 119, 180, 0.08) !important;
  padding: 0.75rem 1rem !important;
  margin: 0.5rem 0 0.75rem 0 !important;
  border-radius: 0 0.35rem 0.35rem 0 !important;
  color: #1a1a1a !important;
  opacity: 1 !important;
  font-size: 0.9rem !important;
  line-height: 1.35 !important;
}
blockquote * {
  color: #1a1a1a !important;
  opacity: 1 !important;
}
blockquote p {
  margin-bottom: 0.5rem !important;
}
blockquote p:last-child {
  margin-bottom: 0 !important;
}
/* Tight stack: calc section heading → expandable step */
p.calc-section-heading-tight {
  margin: 0.35rem 0 0 0 !important;
  font-weight: 600 !important;
  font-size: 1rem !important;
  line-height: 1.25 !important;
}
div[data-testid="stMarkdownContainer"]:has(p.calc-section-heading-tight) {
  margin-bottom: 0 !important;
}
div.element-container:has(div[data-testid="stMarkdownContainer"]:has(p.calc-section-heading-tight)) {
  margin-bottom: 0 !important;
}
</style>
""",
        unsafe_allow_html=True,
    )




# ------------------------------------------------------------
#  COMPUTE FUNCTION (no UI rendering)
# ------------------------------------------------------------
def compute_shrinkage_results(publish: bool = True) -> dict:
    """
    Compute shrinkage results without UI rendering.
    
    Args:
        publish: If True, update results via update_results(). Always True for now.
    
    Returns:
        dict with computed results
    """
    method = str(get_param("shrinkage_method", ShrinkageMethod.EXISTING_AS3600.value))
    authoritative = (
        current_authoritative_family(st.session_state, "shrinkage")
        if method == ShrinkageMethod.EXISTING_AS3600.value
        else None
    )
    if authoritative is not None:
        if publish:
            update_results(
                eps_cs_total=authoritative.get("eps_cs_total"),
                eps_cs_total_micro=authoritative.get("eps_cs_total_micro"),
                eps_cse=authoritative.get("eps_cse"),
                eps_csd_t=authoritative.get("eps_csd_t"),
                th_shrinkage=authoritative.get("th_shrinkage_mm"),
                k1_shrinkage=authoritative.get("k1_shrinkage"),
            )
        return {
            "eps_cs_total": authoritative.get("eps_cs_total"),
            "eps_cs_total_micro": authoritative.get("eps_cs_total_micro"),
            "eps_cse": authoritative.get("eps_cse"),
            "eps_csd_t": authoritative.get("eps_csd_t"),
            "shrinkage_steps": ["Authoritative Inputs V2 calculation"],
        }

    # Geometry and material strength come from the committed Beam Inputs
    # snapshot so reports and the visible page share one engineering owner.
    committed_engineering = resolve_time_dependent_engineering_state(
        st.session_state
    ).values
    b = float(committed_engineering.get("b", 300.0) or 300.0)
    D = float(committed_engineering.get("D", 600.0) or 600.0)
    fc = float(committed_engineering.get("fc", 32.0) or 32.0)
    
    # Read shrinkage parameters (use defaults if not in shared state)
    env_option = get_param("shrinkage_env", "Temperate inland environment")
    t_days = get_param("t_shrink", 365.0)
    
    # Read faces option (default to beam)
    faces_option = get_param("member_faces_exposed", "Beam – three faces exposed")
    
    # Calculate geometry
    geometry_values = exposed_perimeter_geometry_values(b, D, faces_option)
    Ag = geometry_values["Ag"]
    ue = geometry_values["ue"]
    th_raw = geometry_values["th_raw"]
    th_table = _closest_th(th_raw)
    
    method_result = None
    if method == ShrinkageMethod.EC2_C766.value:
        method_result = calculate_ec2_c766_shrinkage(
            EC2C766ShrinkageInput(
                characteristic_cylinder_strength_mpa=float(fc),
                relative_humidity_percent=float(get_param("shrinkage_relative_humidity_percent", 51.0)),
                cement_class=CementClass(str(get_param("shrinkage_cement_class", "S"))),
                concrete_area_mm2=float(Ag),
                drying_perimeter_mm=float(ue),
                age_days=float(t_days),
                drying_start_age_days=float(get_param("shrinkage_drying_start_age_days", 7.0)),
            )
        )
        k1 = method_result.drying_time_coefficient
        eps_cse = method_result.autogenous_shrinkage
        # Keep the common presentation contract complete for the EC2/C766
        # branch.  This is the un-time-developed drying strain that is
        # equivalent to the AS 3600 branch's ``eps_csd_final`` field.
        eps_csd_final = method_result.nominal_drying_shrinkage
        eps_csd_t = method_result.drying_shrinkage
        eps_cs_total = method_result.total_shrinkage
        eps_cs_total_micro = eps_cs_total * 1e6
        th_table = method_result.notional_size_mm
    else:
        k1 = calc_k1_shrinkage(t_days, th_table)
        eps_cse = calc_eps_cse(fc, t_days)
        eps_csd_final = _shrinkage_eps_final(fc, env_option, th_table)
        shrinkage_total = shrinkage_total_values(k1, eps_cse, eps_csd_final)
        eps_csd_t = shrinkage_total["eps_csd_t"]
        eps_cs_total = shrinkage_total["eps_cs_total"]
        eps_cs_total_micro = shrinkage_total["eps_cs_total_micro"]
    
    # Update results if publish=True
    if publish:
        update_results(
            eps_cs_total=eps_cs_total,
            eps_cs_total_micro=eps_cs_total_micro,
            eps_cse=eps_cse,
            eps_csd_t=eps_csd_t,
            th_shrinkage=th_table,
            k1_shrinkage=k1,
        )
        update_results(
            "shrinkage_method",
            {
                "method": method,
                "reference": (
                    method_result.reference.document if method_result is not None else "AS 3600:2018"
                ),
                "warnings": list(method_result.warnings if method_result is not None else ()),
            },
        )
    
    # Build steps list (placeholder)
    steps = ["(Detailed steps not available for this module yet)"]
    
    return {
        "eps_cs_total": eps_cs_total,
        "eps_cs_total_micro": eps_cs_total_micro,
        "eps_cse": eps_cse,
        "eps_csd_t": eps_csd_t,
        "shrinkage_steps": steps,
    }


def compute_shrinkage_components_for_crack_control() -> dict:
    """Calculate C766 strain components from the active Shrinkage-page method."""
    b = float(get_param("b", 300.0))
    D = float(get_param("D", 600.0))
    fc = float(get_param("fc", 32.0))
    age_days = max(float(get_param("t_shrink", 365.0)), 0.0)
    drying_start = max(float(get_param("shrinkage_drying_start_age_days", 7.0)), 0.0)
    early_age = min(drying_start, age_days)
    faces_option = get_param("member_faces_exposed", "Beam – three faces exposed")
    geometry = exposed_perimeter_geometry_values(b, D, faces_option)
    method = str(get_param("shrinkage_method", ShrinkageMethod.EXISTING_AS3600.value))

    if method == ShrinkageMethod.EC2_C766.value:
        common = dict(
            characteristic_cylinder_strength_mpa=fc,
            relative_humidity_percent=float(get_param("shrinkage_relative_humidity_percent", 51.0)),
            cement_class=CementClass(str(get_param("shrinkage_cement_class", "S"))),
            concrete_area_mm2=float(geometry["Ag"]),
            drying_perimeter_mm=float(geometry["ue"]),
            drying_start_age_days=drying_start,
        )
        early = calculate_ec2_c766_shrinkage(EC2C766ShrinkageInput(age_days=early_age, **common))
        current = calculate_ec2_c766_shrinkage(EC2C766ShrinkageInput(age_days=age_days, **common))
        return {
            "method": method,
            "early_age_days": early_age,
            "age_days": age_days,
            "autogenous_early": early.autogenous_shrinkage,
            "autogenous_long_term": current.autogenous_shrinkage,
            "drying_long_term": current.drying_shrinkage,
        }

    th_table = _closest_th(float(geometry["th_raw"]))
    k1 = calc_k1_shrinkage(age_days, th_table)
    eps_csd_final = _shrinkage_eps_final(
        fc,
        get_param("shrinkage_env", "Temperate inland environment"),
        th_table,
    )
    current = shrinkage_total_values(k1, calc_eps_cse(fc, age_days), eps_csd_final)
    return {
        "method": method,
        "early_age_days": early_age,
        "age_days": age_days,
        "autogenous_early": calc_eps_cse(fc, early_age),
        "autogenous_long_term": calc_eps_cse(fc, age_days),
        "drying_long_term": current["eps_csd_t"],
    }


# ------------------------------------------------------------
#  MAIN RENDER FUNCTION
# ------------------------------------------------------------
def render_shrinkage():
    page_title_placeholder = st.empty()
    apply_result_page_css()
    _inject_calcbox_css()
    inject_seamless_steps_css()  # For summary table + scroll functionality
    sync_callbacks = get_sync_callbacks()  # maintains contract with Inputs page
    committed_engineering = resolve_time_dependent_engineering_state(
        st.session_state
    )
    engineering_values = committed_engineering.values

    def engineering_value(name: str, default):
        return engineering_values.get(name, get_param(name, default))

    # --------------------------------------------------------
    # Page title
    # --------------------------------------------------------
    def _render_shrinkage_explainer() -> None:
        method_current = str(get_param("shrinkage_method", ShrinkageMethod.EXISTING_AS3600.value))
        if method_current not in SHRINKAGE_METHOD_LABELS:
            method_current = ShrinkageMethod.EXISTING_AS3600.value
        if method_current == ShrinkageMethod.EC2_C766.value:
            st.markdown(
                """
This method calculates drying and autogenous shrinkage using the published
equations reproduced in **CIRIA C766 Appendices A3-A4** from
**BS EN 1992-1-1:2004**. Temperature-model spreadsheet parity is not claimed.
"""
            )
            return
        st.markdown(
            r"""
This page computes **concrete shrinkage strain** in accordance with  
**AS 3600:2018 Clause 3.1.7**, consisting of:

- **Autogenous shrinkage** ($\varepsilon_{cse}$) — Cl. 3.1.7.2(2),(3)  
- **Drying shrinkage** ($\varepsilon_{csd}$) — Cl. 3.1.7.2(4),(5)  
- **Notional thickness** ($t_h = 2A_g/u_e$) — used in Fig. 3.1.7.2 and Table 3.1.7.2  
- **Total shrinkage** ($\varepsilon_{cs} = \varepsilon_{cse} + \varepsilon_{csd}$)

All strains are reported in units of microstrain ($\times 10^{-6}$).
"""
        )

    with page_title_placeholder.container():
        render_result_page_title("Shrinkage")
    shrinkage_method = str(get_param("shrinkage_method", ShrinkageMethod.EXISTING_AS3600.value))

    # --------------------------------------------------------
    # Reserve space for the top summary table
    # --------------------------------------------------------
    def _render_shrinkage_explainer() -> None:
        st.markdown(
            """
**What shrinkage is**  
Concrete shrinkage is the time-dependent reduction in volume that occurs mainly due to **loss of moisture** (drying shrinkage) and ongoing hydration/chemical effects. It occurs even with no external load.

**Why it matters in design**  
Shrinkage can cause:
- **Cracking** where restraint exists (reinforcement, supports, joints, composite action, etc.)
- **Additional curvature and long-term deflection**
- **Stress redistribution** in reinforcement where restrained
- **Durability impacts** through crack control requirements

**Units**  
Shrinkage is a **strain** (dimensionless): ΔL/L  
Commonly shown as **microstrain (µε)** where 1 µε = 1×10⁻⁶.

**Effect on design**  
Shrinkage is not a force (kN). It is a time-dependent strain that can cause deformation and cracking in restrained members.
"""
        )

    summary_values = compute_shrinkage_results(publish=True)
    summary_rows = build_shrinkage_summary_rows(
        eps_cse=float(summary_values.get("eps_cse") or 0.0),
        eps_csd_t=float(summary_values.get("eps_csd_t") or 0.0),
        eps_cs_total=float(summary_values.get("eps_cs_total") or 0.0),
    )
    render_clickable_summary_table(
        summary_rows,
        key_prefix="shrinkage_summary",
        columns=PARAMETRIC_RESULT_COLUMNS,
    )
    bind_summary_clicks()
    render_page_explainer_expander(_render_shrinkage_explainer)
    page_divider()
    side_view_placeholder = st.empty()

    # --------------------------------------------------------
    b_val = float(engineering_value("b", 400.0))
    D_val = float(engineering_value("D", 600.0))
    fc_val = float(engineering_value("fc", 32.0))
    b = b_val
    D = D_val
    fc = fc_val
    faces_option = str(get_param("member_faces_exposed", "Slab – one face exposed"))
    env_option = str(get_param("shrinkage_env", "Arid environment"))
    t_days = float(get_param("t_shrink", 365.0))

    def _render_shrinkage_method_inputs() -> None:
        nonlocal shrinkage_method
        method_options = list(SHRINKAGE_METHOD_LABELS)
        method_current = str(get_param("shrinkage_method", ShrinkageMethod.EXISTING_AS3600.value))
        if method_current not in method_options:
            method_current = ShrinkageMethod.EXISTING_AS3600.value
        shrinkage_method = st.selectbox(
            "Calculation method",
            options=method_options,
            index=method_options.index(method_current),
            format_func=lambda value: SHRINKAGE_METHOD_LABELS[value],
            key="sh_method",
            on_change=sync_callbacks["sh_method"],
            persist_state="session",
        )

    def _render_shrinkage_geometry_inputs() -> None:
        nonlocal b, D, faces_option
        st.markdown("**Geometry / member**")
        number_row(
            "Section width b (mm)",
            "sh_b",
            b_val,
            sync_callbacks,
        )

        number_row(
            "Overall depth D (mm)",
            "sh_D",
            D_val,
            sync_callbacks,
        )
        b = float(engineering_value("b", b_val))
        D = float(engineering_value("D", D_val))

        col1, col2 = st.columns([1, 2])
        with col1:
            st.markdown("<div class='sb-label'>Member / faces exposed</div>", unsafe_allow_html=True)
        with col2:
            faces_options = [
                "Slab – one face exposed",
                "Slab – two faces exposed",
                "Beam – three faces exposed",
                "Column – four faces exposed",
            ]
            faces_current = get_param("member_faces_exposed", "Slab – one face exposed")
            if faces_current not in faces_options:
                faces_current = "Slab – one face exposed"
            faces_option = v2_selectbox(
                label="Value",
                key="sh_faces",
                options=faces_options,
                default_index=faces_options.index(faces_current),
                label_visibility="collapsed",
                on_change=sync_callbacks["sh_faces"],
            )

    def _render_shrinkage_environment_inputs() -> None:
        nonlocal fc, env_option
        st.markdown("**Material / environment**")
        number_row(
            "Concrete strength f'c (MPa)",
            "inputs_fc",
            fc_val,
            sync_callbacks,
        )
        fc = float(engineering_value("fc", fc_val))

        col1, col2 = st.columns([1, 2])
        with col1:
            st.markdown("<div class='sb-label'>Shrinkage environment (Table 3.1.7.2)</div>", unsafe_allow_html=True)
        with col2:
            env_options = [
                "Arid environment",
                "Interior environment",
                "Temperate inland environment",
                "Tropical / near-coastal / coastal environment",
            ]
            env_current = get_param("shrinkage_env", "Arid environment")
            if env_current not in env_options:
                env_current = "Arid environment"
            if shrinkage_method == ShrinkageMethod.EXISTING_AS3600.value:
                env_option = v2_selectbox(
                    label="Value",
                    key="sh_env",
                    options=env_options,
                    default_index=env_options.index(env_current),
                    label_visibility="collapsed",
                    on_change=sync_callbacks["sh_env"],
                )
            else:
                env_option = env_current
                v2_number_input(
                    label="Relative humidity (%)",
                    key="sh_rh",
                    default=float(get_param("shrinkage_relative_humidity_percent", 51.0)),
                    step=1.0,
                    min_value=0.0,
                    max_value=100.0,
                    on_change=sync_callbacks["sh_rh"],
                )
                v2_selectbox(
                    label="Cement class",
                    key="sh_cement_class",
                    options=["S", "N", "R"],
                    default_index=["S", "N", "R"].index(str(get_param("shrinkage_cement_class", "S"))),
                    on_change=sync_callbacks["sh_cement_class"],
                )

    def _render_shrinkage_time_inputs() -> None:
        nonlocal t_days
        st.markdown("**Time / drying**")
        col1, col2 = st.columns([1, 2])
        with col1:
            st.markdown("<div class='sb-label'>Time since commencement of drying t (days)</div>", unsafe_allow_html=True)
        with col2:
            t_days = v2_number_input(
                label="Value",
                key="inputs_t_shrink",
                default=float(get_param("t_shrink", 365.0)),
                step=10.0,
                min_value=1.0,
                label_visibility="collapsed",
                on_change=sync_callbacks["inputs_t_shrink"],
            )
            if shrinkage_method == ShrinkageMethod.EC2_C766.value:
                v2_number_input(
                    label="End of curing / start of drying (days)",
                    key="sh_drying_start",
                    default=float(get_param("shrinkage_drying_start_age_days", 7.0)),
                    step=1.0,
                    min_value=0.0,
                    on_change=sync_callbacks["sh_drying_start"],
                )

    method_label = SHRINKAGE_METHOD_LABELS.get(shrinkage_method, shrinkage_method)
    environment_summary = (
        env_option
        if shrinkage_method == ShrinkageMethod.EXISTING_AS3600.value
        else (
            f"RH {float(get_param('shrinkage_relative_humidity_percent', 51.0)):.0f}%"
            f" · cement {str(get_param('shrinkage_cement_class', 'S'))}"
        )
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
                    render_body=_render_shrinkage_method_inputs,
                    icon="≡",
                ),
                CheckInputCategory(
                    category_id="section_member",
                    label="Section & member",
                    summary=join_summary(
                        format_dimensions(b_val, D_val),
                        faces_option,
                    ),
                    render_body=_render_shrinkage_geometry_inputs,
                    icon="▣",
                ),
                CheckInputCategory(
                    category_id="material_environment",
                    label="Material & environment",
                    summary=join_summary(
                        f"f'c {format_number(fc_val, 'MPa')}",
                        environment_summary,
                    ),
                    render_body=_render_shrinkage_environment_inputs,
                    icon="◇",
                ),
                CheckInputCategory(
                    category_id="time_drying",
                    label="Time & drying",
                    summary=f"t {format_number(t_days, 'days')}",
                    render_body=_render_shrinkage_time_inputs,
                    icon="◷",
                ),
            ),
        ),
    )

    page_divider()

    # --------------------------------------------------------
    # Derived geometry: Ag, ue, th
    # --------------------------------------------------------
    geometry_values = exposed_perimeter_geometry_values(b, D, faces_option)
    Ag = geometry_values["Ag"]
    ue = geometry_values["ue"]
    th_raw = geometry_values["th_raw"]
    th_table = _closest_th(th_raw)

    # --------------------------------------------------------
    # Shrinkage components
    # --------------------------------------------------------
    method_result = None
    if shrinkage_method == ShrinkageMethod.EC2_C766.value:
        method_result = calculate_ec2_c766_shrinkage(
            EC2C766ShrinkageInput(
                characteristic_cylinder_strength_mpa=fc,
                relative_humidity_percent=float(get_param("shrinkage_relative_humidity_percent", 51.0)),
                cement_class=CementClass(str(get_param("shrinkage_cement_class", "S"))),
                concrete_area_mm2=Ag,
                drying_perimeter_mm=ue,
                age_days=t_days,
                drying_start_age_days=float(get_param("shrinkage_drying_start_age_days", 7.0)),
            )
        )
        th_table = method_result.notional_size_mm
        k1 = method_result.drying_time_coefficient
        eps_cse = method_result.autogenous_shrinkage
        eps_csd_final = method_result.nominal_drying_shrinkage
        eps_csd_t = method_result.drying_shrinkage
        eps_cs_total = method_result.total_shrinkage
        eps_cs_total_micro = eps_cs_total * 1e6
    else:
        k1 = calc_k1_shrinkage(t_days, th_table)
        eps_cse = calc_eps_cse(fc, t_days)
        eps_csd_final = _shrinkage_eps_final(fc, env_option, th_table)
        shrinkage_total = shrinkage_total_values(k1, eps_cse, eps_csd_final)
        eps_csd_t = shrinkage_total["eps_csd_t"]
        eps_cs_total = shrinkage_total["eps_cs_total"]
        eps_cs_total_micro = shrinkage_total["eps_cs_total_micro"]

    # Use the same current V2 family result for the summary and every detailed
    # value.  Page-local calculation is retained only as an unavailable-result
    # fallback, so navigation cannot leave the card on an older value.
    shrinkage_fallback = {
        "th_shrinkage_mm": th_table,
        "k1_shrinkage": k1,
        "eps_cse": eps_cse,
        "eps_csd_final": eps_csd_final,
        "eps_csd_t": eps_csd_t,
        "eps_cs_total": eps_cs_total,
        "eps_cs_total_micro": eps_cs_total_micro,
    }
    # The installed V2 family currently publishes the AS 3600 shrinkage
    # result.  It must not overwrite a deliberately selected EC2/C766 page
    # calculation with values from a different method.
    displayed = (
        resolve_time_dependent_family_values(
            st.session_state,
            family="shrinkage",
            fallback=shrinkage_fallback,
        )
        if shrinkage_method == ShrinkageMethod.EXISTING_AS3600.value
        else dict(shrinkage_fallback)
    )
    th_table = int(displayed["th_shrinkage_mm"])
    k1 = float(displayed["k1_shrinkage"])
    eps_cse = float(displayed["eps_cse"])
    eps_csd_final = float(displayed["eps_csd_final"])
    eps_csd_t = float(displayed["eps_csd_t"])
    eps_cs_total = float(displayed["eps_cs_total"])
    eps_cs_total_micro = float(displayed["eps_cs_total_micro"])

    # --------------------------------------------------------
    # Publish key shrinkage results to shared state
    #   (so other pages like crack width can reuse them)
    # --------------------------------------------------------
    update_results(
        # total shrinkage strain (dimensionless and microstrain)
        eps_cs_total=eps_cs_total,
        eps_cs_total_micro=eps_cs_total_micro,
        # components if you ever want them downstream
        eps_cse=eps_cse,
        eps_csd_t=eps_csd_t,
        # notional thickness & k1 used for time development
        th_shrinkage=th_table,
        k1_shrinkage=k1,
    )
    update_results(
        "shrinkage_method",
        {
            "method": shrinkage_method,
            "reference": method_result.reference.document if method_result is not None else "AS 3600:2018",
            "warnings": list(method_result.warnings if method_result is not None else ()),
        },
    )

    # --------------------------------------------------------
    # TOP SUMMARY TABLE (clickable, like bending/shear)
    # --------------------------------------------------------
    with side_view_placeholder.container():
        inject_compact_side_view_spacing("shrinkage-side-view-compact")
        st.markdown("**Drying shrinkage — beam side view**")
        shrinkage_section_result = build_shrinkage_side_view_result(
            layout=compute_section_layout(),
            faces_option=faces_option,
            height_px=COMPACT_SIDE_VIEW_HEIGHT_PX,
        )
        if shrinkage_section_result.error_message:
            st.warning(shrinkage_section_result.error_message)
        if shrinkage_section_result.figure is not None:
            render_plotly_diagram(
                compact_side_view_figure(shrinkage_section_result.figure),
                key="shrinkage_side_view_diagram",
                title="Drying shrinkage — beam side view",
                config={"displayModeBar": False},
            )
        page_divider()

    # --------------------------------------------------------
    # Stacked calculation sections
    # --------------------------------------------------------
    render_section_title("Shrinkage checks")

    if shrinkage_method == ShrinkageMethod.EC2_C766.value and method_result is not None:
        render_expandable_step(
            page_key="shrinkage",
            step_id="shrinkage_ec2_drying",
            title="EC2/C766 drying shrinkage",
            summary_md=[
                "Check 1 — Notional size and drying shrinkage",
                rf"Result: $\varepsilon_{{cd}}(t) = {method_result.drying_shrinkage * 1e6:.1f}\,\mu\varepsilon$",
            ],
            status_kind=None,
            calc_md=rf"""
**Notional size**

\[h_0 = \frac{{2A_c}}{{u}} = {method_result.notional_size_mm:.1f}\,\text{{mm}}\]

**Drying shrinkage**

- Nominal drying shrinkage: $\varepsilon_{{cd,0}} = {method_result.nominal_drying_shrinkage * 1e6:.1f}\,\mu\varepsilon$
- Size coefficient: $k_h = {method_result.size_coefficient_kh:.3f}$
- Drying-time coefficient: $\beta_{{ds}} = {method_result.drying_time_coefficient:.3f}$
- Result: $\varepsilon_{{cd}}(t) = {method_result.drying_shrinkage * 1e6:.1f}\,\mu\varepsilon$
""",
        )
        render_expandable_step(
            page_key="shrinkage",
            step_id="shrinkage_ec2_total",
            title="EC2/C766 total shrinkage",
            summary_md=[
                "Check 2 — Drying plus autogenous shrinkage",
                rf"Result: $\varepsilon_{{cs}} = {method_result.total_shrinkage * 1e6:.1f}\,\mu\varepsilon$",
            ],
            status_kind=None,
            calc_md=rf"""
**Autogenous and total shrinkage**

\[\varepsilon_{{cs}} = \varepsilon_{{cd}} + \varepsilon_{{ca}}\]

- Drying shrinkage: $\varepsilon_{{cd}}(t) = {method_result.drying_shrinkage * 1e6:.1f}\,\mu\varepsilon$
- Autogenous shrinkage: $\varepsilon_{{ca}}(t) = {method_result.autogenous_shrinkage * 1e6:.1f}\,\mu\varepsilon$
- **Total shrinkage: $\varepsilon_{{cs}} = {method_result.total_shrinkage * 1e6:.1f}\,\mu\varepsilon$**

Reference: {method_result.reference.document}, {method_result.reference.clause}.
""",
        )
        st.warning(method_result.warnings[0])
        scroll_to_jump_after_render("shrinkage")
        return

    def render_th():
        return rf"""
**Purpose**

Determine the **notional thickness** $t_h$ used in AS 3600 for **creep and shrinkage**.
This thickness controls how quickly the member dries and is used in **Fig. 3.1.7.2**
and **Table 3.1.7.2**.

**Inputs**

- Section width: $b = {b:.1f}\,\text{{mm}}$
- Overall depth: $D = {D:.1f}\,\text{{mm}}$
- Gross area: $A_g = b D = {Ag:.0f}\,\text{{mm}}^2$
- Faces exposed option: **{faces_option}**
- Exposed perimeter: $u_e = {ue:.1f}\,\text{{mm}}$

**Formula**

\[
t_h = \frac{{2 A_g}}{{u_e}}
\]

**Substitution**

\[
t_h = \frac{{2 \times {Ag:.0f}}}{{{ue:.1f}}}
\approx {th_raw:.1f}\,\text{{mm}}
\]

For compatibility with **Fig. 3.1.7.2** and **Table 3.1.7.2**, we adopt
the nearest standard notional thickness:

\[
t_{{h,\text{{table}}}} = {th_table:d}\,\text{{mm}} \quad (\text{{nearest of 50, 100, 200, 400 mm}})
\]

**Result**

- Calculated notional thickness: $t_{{h,\text{{calc}}}} \approx {th_raw:.1f}\,\text{{mm}}$  
- **Adopted for shrinkage checks:** $t_{{h,\text{{table}}}} = {th_table:d}\,\text{{mm}}$

_Ref: AS 3600:2018 definition of notional thickness \(t_h = 2 A_g/u_e\);
Fig. 3.1.7.2 and Table 3.1.7.2._
"""
        
    render_expandable_step(
        page_key="shrinkage",
        step_id="shrinkage_th",
        title="Notional thickness t_h",
        summary_md=[
            "Check 1 — Notional thickness calculation for creep and shrinkage",
            rf"Result: $t_h = {th_table:d}$ mm (adopted from calculated {th_raw:.1f} mm)",
        ],
        status_kind=None,
        calc_md=render_th(),
    )

    eps_cse_final = autogenous_shrinkage_final_from_current(eps_cse, t_days)

    def render_autogenous():
        return rf"""
**Purpose**

Estimate the **autogenous (chemical) shrinkage** strain $\varepsilon_{{cse}}$,
which develops even without drying (mainly due to hydration).

**Inputs**

- Concrete strength: $f'_c = {fc:.1f}\,\text{{MPa}}$
- Time after setting: $t = {t_days:.0f}\,\text{{days}}$

Final autogenous strain $\varepsilon^*_{{cse}}$:

For $f'_c \le 50\ \text{{MPa}}$:

\[
\varepsilon^*_{{cse}} = (0.07 f'_c - 0.5)\times 50\times 10^{-6}
\]

For $f'_c > 50\ \text{{MPa}}$:

\[
\varepsilon^*_{{cse}} = (0.08 f'_c - 1.0)\times 50\times 10^{-6}
\]

Time development (Cl. 3.1.7.2(2)):

\[
\varepsilon_{{cse}}(t) = \varepsilon^*_{{cse}} (1 - e^{{-0.04 t}})
\]

**Substitution**

Using $f'_c = {fc:.1f}$ MPa and $t = {t_days:.0f}$ days:

- Final autogenous strain:
  \[
  \varepsilon^*_{{cse}} \approx {eps_cse_final:.3e}
  \]
- At time $t$:
  \[
  \varepsilon_{{cse}}(t) \approx {eps_cse:.3e}
  \]

**Result**

- Autogenous shrinkage at $t = {t_days:.0f}$ days:
  \[
  \varepsilon_{{cse}} \approx {eps_cse*1e6:.1f}\times 10^{{-6}}
  \]
  (≈ {eps_cse*1e6:.1f} microstrain)

_Ref: AS 3600:2018 Cl. 3.1.7.2(2),(3)._ 
"""
        
    render_expandable_step(
        page_key="shrinkage",
        step_id="shrinkage_autogenous",
        title="Autogenous shrinkage ε_cse",
        summary_md=[
            "Check 2 — Autogenous (chemical) shrinkage strain calculation",
            rf"Result: $\varepsilon_{{cse}} = {eps_cse*1e6:.1f}$ με",
        ],
        status_kind=None,
        calc_md=render_autogenous(),
    )

    env_short = _ENV_LABELS[env_option]

    def render_drying():
        return rf"""
**Purpose**

Estimate the **drying shrinkage** strain $\varepsilon_{{csd}}(t)$, which develops
as moisture is lost from the member.

**Inputs**

- Environment: **{env_option}**  
- Concrete strength: $f'_c = {fc:.1f}\,\text{{MPa}}$  
- Notional thickness for tables: $t_h = {th_table:d}\,\text{{mm}}$  
- Time since commencement of drying: $t = {t_days:.0f}\,\text{{days}}$

From **Table 3.1.7.2**, the **final design drying shrinkage**:

\[
\varepsilon^*_{{csd}} = {eps_csd_final*1e6:.0f}\times 10^{{-6}}
\quad (\text{{for }} f'_c \approx {_closest_fc_row(fc):.0f}\ \text{{MPa}},
\ t_h = {th_table:d}\ \text{{mm}},\ \text{{{env_short}}})
\]

Time development coefficient $k_1$ from **Fig. 3.1.7.2**:

\[
k_1(t, t_h) = \frac{{\alpha_t t^{0.8}}}{{t^{0.8} + 0.15 t_h}},
\quad
\alpha_t = 0.8 + 1.2 e^{{-0.005 t_h}}
\]

Drying shrinkage at time $t$:

\[
\varepsilon_{{csd}}(t) = k_1(t, t_h)\, \varepsilon^*_{{csd}}
\]

**Substitution**

- $\alpha_t \approx 0.8 + 1.2 e^{{-0.005\times {th_table:d}}}$  
- $k_1(t, t_h) \approx {k1:.3f}$  
- Drying shrinkage:
  \[
  \varepsilon_{{csd}}(t)
  = {k1:.3f} \times {eps_csd_final*1e6:.0f}\times 10^{{-6}}
  \approx {eps_csd_t*1e6:.1f}\times 10^{{-6}}
  \]

**Result**

- Drying shrinkage at $t = {t_days:.0f}$ days:
  \[
  \varepsilon_{{csd}} \approx {eps_csd_t*1e6:.1f}\times 10^{{-6}}
  \]
  (≈ {eps_csd_t*1e6:.1f} microstrain)

_Ref: AS 3600:2018 Cl. 3.1.7.2(4),(5); Fig. 3.1.7.2 and Table 3.1.7.2._
"""
        
    render_expandable_step(
        page_key="shrinkage",
        step_id="shrinkage_drying",
        title="Drying shrinkage ε_csd",
        summary_md=[
            "Check 3 — Drying shrinkage strain calculation with time development",
            rf"Result: $\varepsilon_{{csd}} = {eps_csd_t*1e6:.1f}$ με",
        ],
        status_kind=None,
        calc_md=render_drying(),
    )

    def render_total():
        return rf"""
**Purpose**

Combine **autogenous** and **drying** shrinkage to obtain the **total design
shrinkage strain**:

\[
\varepsilon_{{cs}} = \varepsilon_{{cse}} + \varepsilon_{{csd}}
\]

**Inputs**

- Autogenous component:
  \[
  \varepsilon_{{cse}} \approx {eps_cse*1e6:.1f}\times 10^{{-6}}
  \]
- Drying component:
  \[
  \varepsilon_{{csd}} \approx {eps_csd_t*1e6:.1f}\times 10^{{-6}}
  \]

**Formula**

\[
\varepsilon_{{cs}} = \varepsilon_{{cse}} + \varepsilon_{{csd}}
\]

**Substitution**

\[
\varepsilon_{{cs}}
= {eps_cse*1e6:.1f}\times 10^{{-6}}
+ {eps_csd_t*1e6:.1f}\times 10^{{-6}}
\approx {eps_cs_total*1e6:.1f}\times 10^{{-6}}
\]

**Result**

- Total shrinkage at $t = {t_days:.0f}$ days:
  \[
  \varepsilon_{{cs}} \approx {eps_cs_total*1e6:.1f}\times 10^{{-6}}
  \]
  (≈ {eps_cs_total*1e6:.1f} microstrain)

_Ref: AS 3600:2018 Cl. 3.1.7 – total shrinkage._ 
"""
        
    render_expandable_step(
        page_key="shrinkage",
        step_id="shrinkage_total",
        title="Total shrinkage ε_cs",
        summary_md=[
            "Check 4 — Combination of autogenous and drying shrinkage components",
            rf"Result: $\varepsilon_{{cs}} = {eps_cs_total*1e6:.1f}$ με",
        ],
        status_kind=None,
        calc_md=render_total(),
    )

    scroll_to_jump_after_render()
