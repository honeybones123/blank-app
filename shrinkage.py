# shrinkage_page.py
# ============================
# SHRINKAGE – AS 3600:2018 Cl. 3.1.7
# ============================

import math
import numpy as np
import pandas as pd
import streamlit as st

from state_and_helpers import (
    get_param,
    get_sync_callbacks,
    update_results,  # kept for contract
)
from widgets_helpers import apply_global_widget_css, number_row, calcbox, page_divider
from step_ui import render_expandable_step
from summary_table_ui import render_clickable_summary_table
from ui_seamless_steps import bind_summary_clicks, inject_seamless_steps_css
from jump_nav import scroll_to_jump_after_render


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
</style>
""",
        unsafe_allow_html=True,
    )




# ------------------------------------------------------------
#  Table 3.1.7.2 – final design drying shrinkage ε*csd (×10⁻⁶)
# ------------------------------------------------------------
_SHRINKAGE_TABLE = {
    25: {
        "Arid":      {50: 810, 100: 720, 200: 590, 400: 470},
        "Interior":  {50: 780, 100: 670, 200: 550, 400: 440},
        "Temperate": {50: 740, 100: 630, 200: 520, 400: 410},
        "Tropical":  {50: 610, 100: 530, 200: 440, 400: 350},
    },
    32: {
        "Arid":      {50: 800, 100: 720, 200: 590, 400: 470},
        "Interior":  {50: 770, 100: 670, 200: 560, 400: 440},
        "Temperate": {50: 730, 100: 620, 200: 520, 400: 420},
        "Tropical":  {50: 600, 100: 520, 200: 440, 400: 360},
    },
    40: {
        "Arid":      {50: 790, 100: 710, 200: 590, 400: 480},
        "Interior":  {50: 740, 100: 670, 200: 560, 400: 450},
        "Temperate": {50: 700, 100: 620, 200: 530, 400: 420},
        "Tropical":  {50: 580, 100: 500, 200: 440, 400: 360},
    },
    50: {
        "Arid":      {50: 780, 100: 700, 200: 590, 400: 490},
        "Interior":  {50: 730, 100: 660, 200: 560, 400: 460},
        "Temperate": {50: 690, 100: 620, 200: 530, 400: 440},
        "Tropical":  {50: 570, 100: 490, 200: 430, 400: 370},
    },
    65: {
        "Arid":      {50: 770, 100: 700, 200: 600, 400: 510},
        "Interior":  {50: 730, 100: 650, 200: 570, 400: 490},
        "Temperate": {50: 690, 100: 610, 200: 530, 400: 450},
        "Tropical":  {50: 560, 100: 490, 200: 420, 400: 390},
    },
    80: {
        "Arid":      {50: 750, 100: 690, 200: 610, 400: 530},
        "Interior":  {50: 720, 100: 660, 200: 590, 400: 510},
        "Temperate": {50: 680, 100: 630, 200: 550, 400: 470},
        "Tropical":  {50: 560, 100: 520, 200: 470, 400: 390},
    },
    100: {
        "Arid":      {50: 740, 100: 690, 200: 620, 400: 560},
        "Interior":  {50: 710, 100: 660, 200: 600, 400: 540},
        "Temperate": {50: 680, 100: 640, 200: 580, 400: 520},
        "Tropical":  {50: 560, 100: 530, 200: 490, 400: 420},
    },
}

_ENV_LABELS = {
    "Arid environment": "Arid",
    "Interior environment": "Interior",
    "Temperate inland environment": "Temperate",
    "Tropical / near-coastal / coastal environment": "Tropical",
}


def _closest_fc_row(fc: float) -> int:
    keys = sorted(_SHRINKAGE_TABLE.keys())
    return min(keys, key=lambda k: abs(fc - k))


def _closest_th(th: float) -> int:
    options = [50, 100, 200, 400]
    return min(options, key=lambda x: abs(th - x))


def _shrinkage_eps_final(fc: float, env_label: str, th_table: float) -> float:
    """Return ε*csd (final design drying shrinkage) as strain (not microstrain)."""
    fc_key = _closest_fc_row(fc)
    env_key = _ENV_LABELS[env_label]
    th_key = _closest_th(th_table)
    microstrain = _SHRINKAGE_TABLE[fc_key][env_key][th_key]
    return microstrain * 1e-6  # convert ×10⁻⁶ to strain


def calc_k1_shrinkage(t_days: float, th_mm: float) -> float:
    """
    k1(t, th) from Fig. 3.1.7.2:

        k1 = α_t t^0.8 / (t^0.8 + 0.15 th)
        α_t = 0.8 + 1.2 e^(-0.005 th)
    """
    t = max(t_days, 0.1)
    th = max(th_mm, 1.0)
    alpha_t = 0.8 + 1.2 * math.exp(-0.005 * th)
    num = alpha_t * (t ** 0.8)
    den = (t ** 0.8) + 0.15 * th
    return num / den


def calc_eps_cse(fc: float, t_days: float) -> float:
    """
    Autogenous (chemical) shrinkage ε_cse(t)
    Cl. 3.1.7.2(2),(3). Returns strain (not microstrain).
    """
    if fc <= 50.0:
        eps_final = (0.07 * fc - 0.5) * 50e-6
    else:
        eps_final = (0.08 * fc - 1.0) * 50e-6

    t = max(t_days, 0.0)
    return eps_final * (1.0 - math.exp(-0.04 * t))


# ------------------------------------------------------------
#  MAIN RENDER FUNCTION
# ------------------------------------------------------------
def render_shrinkage():
    apply_global_widget_css()
    _inject_calcbox_css()
    inject_seamless_steps_css()  # For summary table + scroll functionality
    get_sync_callbacks()  # maintains contract with Inputs page

    # --------------------------------------------------------
    # Page title
    # --------------------------------------------------------
    st.title("Shrinkage – AS 3600:2018 Clause 3.1.7")

    # --------------------------------------------------------
    # Page description (directly under title)
    #   → all bullets are single-line with inline LaTeX ($...$)
    # --------------------------------------------------------
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

    # --------------------------------------------------------
    # Reserve space for the top summary table
    # --------------------------------------------------------
    summary_placeholder = st.empty()

    # --------------------------------------------------------
    # Geometry & Exposure
    # --------------------------------------------------------
    st.markdown("### Geometry & exposure")

    col_geom, col_env = st.columns(2)

    with col_geom:
        b_seed = _seed_from_param("b", 300.0)
        D_seed = _seed_from_param("D", 600.0)

        col1, col2 = st.columns([1, 2])
        with col1:
            st.markdown("<div class='sb-label'>Section width b (mm)</div>", unsafe_allow_html=True)
        with col2:
            b = st.number_input(
                "",
                value=b_seed,
                step=10.0,
                key="sh_b",
                label_visibility="collapsed",
            )

        col1, col2 = st.columns([1, 2])
        with col1:
            st.markdown("<div class='sb-label'>Overall depth D (mm)</div>", unsafe_allow_html=True)
        with col2:
            D = st.number_input(
                "",
                value=D_seed,
                step=10.0,
                key="sh_D",
                label_visibility="collapsed",
            )

        col1, col2 = st.columns([1, 2])
        with col1:
            st.markdown("<div class='sb-label'>Member / faces exposed</div>", unsafe_allow_html=True)
        with col2:
            faces_option = st.selectbox(
                "",
                [
                    "Slab – one face exposed",
                    "Slab – two faces exposed",
                    "Beam – three faces exposed",
                    "Column – four faces exposed",
                ],
                index=1,
                key="sh_faces",
                label_visibility="collapsed",
            )

    with col_env:
        fc_seed = _seed_from_param("fc", 32.0)

        col1, col2 = st.columns([1, 2])
        with col1:
            st.markdown("<div class='sb-label'>Concrete strength f'c (MPa)</div>", unsafe_allow_html=True)
        with col2:
            fc = st.number_input(
                "",
                value=fc_seed,
                step=1.0,
                key="sh_fc",
                label_visibility="collapsed",
            )

        col1, col2 = st.columns([1, 2])
        with col1:
            st.markdown("<div class='sb-label'>Shrinkage environment (Table 3.1.7.2)</div>", unsafe_allow_html=True)
        with col2:
            env_option = st.selectbox(
                "",
                [
                    "Arid environment",
                    "Interior environment",
                    "Temperate inland environment",
                    "Tropical / near-coastal / coastal environment",
                ],
                index=2,
                key="sh_env",
                label_visibility="collapsed",
            )

        col1, col2 = st.columns([1, 2])
        with col1:
            st.markdown("<div class='sb-label'>Time since commencement of drying t (days)</div>", unsafe_allow_html=True)
        with col2:
            t_days = st.number_input(
                "",
                value=365.0,
                step=10.0,
                min_value=1.0,
                key="sh_t_days",
                label_visibility="collapsed",
            )

    # --------------------------------------------------------
    # Derived geometry: Ag, ue, th
    # --------------------------------------------------------
    Ag = b * D  # mm²

    if faces_option == "Slab – one face exposed":
        ue = b
    elif faces_option == "Slab – two faces exposed":
        ue = 2.0 * b
    elif faces_option == "Beam – three faces exposed":
        ue = b + 2.0 * D
    else:  # "Column – four faces exposed"
        ue = 2.0 * (b + D)

    th_raw = 2.0 * Ag / ue if ue > 0 else 0.0
    th_table = _closest_th(th_raw)

    # --------------------------------------------------------
    # Shrinkage components
    # --------------------------------------------------------
    k1 = calc_k1_shrinkage(t_days, th_table)
    eps_cse = calc_eps_cse(fc, t_days)
    eps_csd_final = _shrinkage_eps_final(fc, env_option, th_table)
    eps_csd_t = k1 * eps_csd_final
    eps_cs_total = eps_cse + eps_csd_t

    # --------------------------------------------------------
    # Publish key shrinkage results to shared state
    #   (so other pages like crack width can reuse them)
    # --------------------------------------------------------
    update_results(
        # total shrinkage strain (dimensionless and microstrain)
        eps_cs_total=eps_cs_total,
        eps_cs_total_micro=eps_cs_total * 1e6,
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
        st.markdown("## Shrinkage — Summary")
        
        # Build ROWS for clickable summary table
        ROWS = [
            {
                "uid": "shrinkage_autogenous",
                "title": "Autogenous shrinkage ε_cse",
                "value": f"{eps_cse*1e6:.1f} µε",
                "limit": "—",
                "util": "—",
                "status": "—",
                "ok": None,
                "tab": "Autogenous shrinkage ε_cse",
            },
            {
                "uid": "shrinkage_drying",
                "title": "Drying shrinkage ε_csd",
                "value": f"{eps_csd_t*1e6:.1f} µε",
                "limit": "—",
                "util": "—",
                "status": "—",
                "ok": None,
                "tab": "Drying shrinkage ε_csd",
            },
            {
                "uid": "shrinkage_total",
                "title": "Total shrinkage ε_cs",
                "value": f"{eps_cs_total*1e6:.1f} µε",
                "limit": "—",
                "util": "—",
                "status": "—",
                "ok": None,
                "tab": "Total shrinkage ε_cs",
            },
        ]
        
        clicked_uid = render_clickable_summary_table(ROWS, key="shrinkage_summary")
        
        # Handle clicked row - set state for expanding step
        if clicked_uid:
            # Set step_open_{step_id} to True (matches render_expandable_step pattern)
            st.session_state[f"step_open_{clicked_uid}"] = True
            st.session_state["shrinkage_pending_scroll_uid"] = clicked_uid
        
        page_divider()

    # --------------------------------------------------------
    # Tabs (5): geometry, autogenous, drying, total, flow chart
    # --------------------------------------------------------
    tab_geom, tab_auto, tab_dry, tab_total, tab_flow = st.tabs(
        [
            "Geometry & tₕ",
            "Autogenous shrinkage ε_cse",
            "Drying shrinkage ε_csd",
            "Total shrinkage ε_cs",
            "Flow chart / references",
        ]
    )

    # ---------- Tab 1: Geometry & t_h ----------
    with tab_geom:
        st.subheader("Notional thickness tₕ – AS 3600 (2Aᵍ / uₑ)")

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
                rf"Result: $t_h = {th_table:d}$ mm (adopted from calculated {th_raw:.1f} mm)",
                "Notional thickness calculation for creep and shrinkage"
            ],
            status_kind=None,
            calc_md=render_th(),
        )

    # ---------- Tab 2: Autogenous shrinkage ----------
    with tab_auto:
        st.subheader("Autogenous shrinkage ε_cse – AS 3600 Cl. 3.1.7.2(2),(3)")

        if t_days > 0:
            eps_cse_final = eps_cse / (1.0 - math.exp(-0.04 * t_days))
        else:
            eps_cse_final = eps_cse

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
                rf"Result: $\varepsilon_{{cse}} = {eps_cse*1e6:.1f}$ με",
                "Autogenous (chemical) shrinkage strain calculation"
            ],
            status_kind=None,
            calc_md=render_autogenous(),
        )

    # ---------- Tab 3: Drying shrinkage ----------
    with tab_dry:
        st.subheader("Drying shrinkage ε_csd – AS 3600 Cl. 3.1.7.2(4),(5)")
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
                rf"Result: $\varepsilon_{{csd}} = {eps_csd_t*1e6:.1f}$ με",
                "Drying shrinkage strain calculation with time development"
            ],
            status_kind=None,
            calc_md=render_drying(),
        )

    # ---------- Tab 4: Total shrinkage ----------
    with tab_total:
        st.subheader("Total shrinkage ε_cs = ε_cse + ε_csd")

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
                rf"Result: $\varepsilon_{{cs}} = {eps_cs_total*1e6:.1f}$ με",
                "Combination of autogenous and drying shrinkage components"
            ],
            status_kind=None,
            calc_md=render_total(),
        )

    # ---------- Tab 5: Flow chart / references ----------
    with tab_flow:
        st.subheader("Shrinkage workflow – AS 3600:2018 Cl. 3.1.7")

        st.markdown(
            """
### Step 1 – Geometry & exposure

- Choose section dimensions \\(b, D\\)  
- Select faces exposed → exposed perimeter \\(u_e\\)  
- Compute gross area \\(A_g = bD\\) and notional thickness \\(t_h = 2 A_g / u_e\\)  
- Snap \\(t_h\\) to **50, 100, 200 or 400 mm** for use with Fig. 3.1.7.2 and Table 3.1.7.2.

---

### Step 2 – Environment & strength

- Environment: arid / interior / temperate inland / tropical & coastal  
- Concrete strength \\(f'_c\\)  
- Time since commencement of drying \\(t\\).

---

### Step 3 – Autogenous shrinkage \\(\\varepsilon_{cse}\\)

- Compute final \\(\\varepsilon^*_{cse}\\) from \\(f'_c\\) (Cl. 3.1.7.2(3))  
- Apply time function  
  \\(\\varepsilon_{cse}(t) = \\varepsilon^*_{cse}(1 - e^{-0.04 t})\\).

---

### Step 4 – Drying shrinkage \\(\\varepsilon_{csd}\\)

1. From **Table 3.1.7.2**, obtain final drying strain \\(\\varepsilon^*_{csd}\\)  
   for \\(f'_c\\), environment and \\(t_h\\).  
2. Compute \\(k_1(t, t_h)\\) from **Fig. 3.1.7.2**.  
3. Calculate drying shrinkage at time \\(t\\):  
   \\[
   \\varepsilon_{csd}(t) = k_1(t, t_h)\\, \\varepsilon^*_{csd}
   \\]

---

### Step 5 – Total shrinkage & use in design

- Sum components: \\(\\varepsilon_{cs} = \\varepsilon_{cse} + \\varepsilon_{csd}\\).  
- Use \\(\\varepsilon_{cs}\\) in **deflection**, **crack width** and other
  **serviceability** checks.
"""
        )
    
    # Handle pending scroll after all tabs have rendered (like bending)
    # This ensures all anchors exist before scrolling
    pending_scroll_uid = st.session_state.get("shrinkage_pending_scroll_uid")
    if pending_scroll_uid:
        st.session_state["jump_to"] = pending_scroll_uid
        scroll_to_jump_after_render()
        st.session_state["shrinkage_pending_scroll_uid"] = None
    
    bind_summary_clicks()


