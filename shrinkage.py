# shrinkage_page.py
# ============================
# SHRINKAGE – AS 3600:2018 Cl. 3.1.7
# ============================

import math
import numpy as np
import pandas as pd
import streamlit as st

from state_runtime_gateway import (
    get_param,
    get_sync_callbacks,
    update_results,  # kept for contract
)
from widgets_helpers import apply_global_widget_css, apply_result_page_css, number_row, v2_number_input, v2_selectbox, v2_checkbox, v2_radio, render_page_explainer_expander, render_result_page_title, render_section_title, page_divider, render_plotly_diagram
from step_ui import render_expandable_step
from engineering_check_ui import PARAMETRIC_RESULT_COLUMNS
from ui.summary_rows import build_shrinkage_summary_rows
from ui_seamless_steps import render_clickable_summary_table, bind_summary_clicks, inject_seamless_steps_css
from jump_nav import scroll_to_jump_after_render
from ui.diagrams.creep_shrinkage_diagram import build_shrinkage_schematic_plotly
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
    # Read geometry from shared state
    b = get_param("b", 300.0)
    D = get_param("D", 600.0)
    
    # Read materials
    fc = get_param("fc", 32.0)
    
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
    
    # Calculate shrinkage components
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
    
    # Build steps list (placeholder)
    steps = ["(Detailed steps not available for this module yet)"]
    
    return {
        "eps_cs_total": eps_cs_total,
        "eps_cs_total_micro": eps_cs_total_micro,
        "eps_cse": eps_cse,
        "eps_csd_t": eps_csd_t,
        "shrinkage_steps": steps,
    }


# ------------------------------------------------------------
#  MAIN RENDER FUNCTION
# ------------------------------------------------------------
def render_shrinkage():
    apply_global_widget_css()
    apply_result_page_css()
    _inject_calcbox_css()
    inject_seamless_steps_css()  # For summary table + scroll functionality
    sync_callbacks = get_sync_callbacks()  # maintains contract with Inputs page

    # --------------------------------------------------------
    # Page title
    # --------------------------------------------------------
    def _render_shrinkage_explainer() -> None:
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

    render_result_page_title("Shrinkage")

    # --------------------------------------------------------
    # Reserve space for the top summary table
    # --------------------------------------------------------
    summary_placeholder = st.empty()

    # --------------------------------------------------------
    col_geom, col_env, col_time = st.columns(3)

    with col_geom:
        st.markdown("**Geometry / member**")
        b_val = float(st.session_state.get("sh_b", get_param("b", 400.0)))
        D_val = float(st.session_state.get("sh_D", get_param("D", 600.0)))

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
        b = float(get_param("b", b_val))
        D = float(get_param("D", D_val))

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

    with col_env:
        st.markdown("**Material / environment**")
        fc_val = float(st.session_state.get("inputs_fc", get_param("fc", 32.0)))

        number_row(
            "Concrete strength f'c (MPa)",
            "inputs_fc",
            fc_val,
            sync_callbacks,
        )
        fc = float(get_param("fc", fc_val))

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
            env_option = v2_selectbox(
                label="Value",
                key="sh_env",
                options=env_options,
                default_index=env_options.index(env_current),
                label_visibility="collapsed",
                on_change=sync_callbacks["sh_env"],
            )

    with col_time:
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
    k1 = calc_k1_shrinkage(t_days, th_table)
    eps_cse = calc_eps_cse(fc, t_days)
    eps_csd_final = _shrinkage_eps_final(fc, env_option, th_table)
    shrinkage_total = shrinkage_total_values(k1, eps_cse, eps_csd_final)
    eps_csd_t = shrinkage_total["eps_csd_t"]
    eps_cs_total = shrinkage_total["eps_cs_total"]
    eps_cs_total_micro = shrinkage_total["eps_cs_total_micro"]

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

    # --------------------------------------------------------
    # TOP SUMMARY TABLE (clickable, like bending/shear)
    # --------------------------------------------------------
    with summary_placeholder.container():
        # Keep only the info control; the page title already provides the heading.
        _, h_right = st.columns([8, 1], vertical_alignment="center")
        with h_right:
            with st.popover("ℹ️ INFO"):
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
        
        ROWS = build_shrinkage_summary_rows(
            eps_cse=eps_cse,
            eps_csd_t=eps_csd_t,
            eps_cs_total=eps_cs_total,
        )

        render_clickable_summary_table(
            ROWS, key_prefix="shrinkage_summary", columns=PARAMETRIC_RESULT_COLUMNS
        )
        bind_summary_clicks()
        page_divider()

        st.markdown("**Shrinkage strain schematic**")
        fig_shrink_schematic = build_shrinkage_schematic_plotly()
        render_plotly_diagram(
            fig_shrink_schematic,
            key="shrinkage_strain_schematic_diagram",
            title="Shrinkage strain schematic",
            config={
                "displayModeBar": False,
                "staticPlot": True,
            },
        )
        page_divider()

    # --------------------------------------------------------
    # Stacked calculation sections
    # --------------------------------------------------------
    render_section_title("Shrinkage checks")

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
