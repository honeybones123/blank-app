"""Shrinkage calculation-card presentation boundary."""

from __future__ import annotations

from application.contracts.concrete_crack_shrinkage import ShrinkageMethod
from engineering_page_sections.shrinkage_checks_context import (
    ShrinkageChecksSnapshot,
)
from jump_nav import scroll_to_jump_after_render
from step_ui import render_expandable_step
from widgets_helpers import render_section_title


def render_shrinkage_checks(snapshot: ShrinkageChecksSnapshot) -> None:
    """Render AS 3600 or EC2/C766 checks from one complete snapshot."""

    render_section_title("Shrinkage checks")
    method_result = snapshot.method_result
    if snapshot.method == ShrinkageMethod.EC2_C766.value and method_result:
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
        if method_result.warnings:
            import streamlit as st

            st.warning(method_result.warnings[0])
        scroll_to_jump_after_render("shrinkage")
        return

    b = snapshot.width_mm
    depth = snapshot.depth_mm
    area = snapshot.gross_area_mm2
    faces = snapshot.faces_exposed
    perimeter = snapshot.exposed_perimeter_mm
    thickness_raw = snapshot.notional_thickness_raw_mm
    thickness_table = snapshot.notional_thickness_table_mm
    strength = snapshot.concrete_strength_mpa
    environment = snapshot.environment
    environment_short = snapshot.environment_short_label
    time_days = snapshot.time_days
    k1 = snapshot.k1
    eps_cse = snapshot.eps_cse
    eps_cse_final = snapshot.eps_cse_final
    eps_csd_final = snapshot.eps_csd_final
    eps_csd_t = snapshot.eps_csd_t
    eps_total = snapshot.eps_cs_total

    def render_th() -> str:
        return rf"""
**Purpose**

Determine the **notional thickness** $t_h$ used in AS 3600 for **creep and shrinkage**.
This thickness controls how quickly the member dries and is used in **Fig. 3.1.7.2**
and **Table 3.1.7.2**.

**Inputs**

- Section width: $b = {b:.1f}\,\text{{mm}}$
- Overall depth: $D = {depth:.1f}\,\text{{mm}}$
- Gross area: $A_g = b D = {area:.0f}\,\text{{mm}}^2$
- Faces exposed option: **{faces}**
- Exposed perimeter: $u_e = {perimeter:.1f}\,\text{{mm}}$

**Formula**

\[
t_h = \frac{{2 A_g}}{{u_e}}
\]

**Substitution**

\[
t_h = \frac{{2 \times {area:.0f}}}{{{perimeter:.1f}}}
\approx {thickness_raw:.1f}\,\text{{mm}}
\]

For compatibility with **Fig. 3.1.7.2** and **Table 3.1.7.2**, we adopt
the nearest standard notional thickness:

\[
t_{{h,\text{{table}}}} = {thickness_table:d}\,\text{{mm}} \quad (\text{{nearest of 50, 100, 200, 400 mm}})
\]

**Result**

- Calculated notional thickness: $t_{{h,\text{{calc}}}} \approx {thickness_raw:.1f}\,\text{{mm}}$
- **Adopted for shrinkage checks:** $t_{{h,\text{{table}}}} = {thickness_table:d}\,\text{{mm}}$

_Ref: AS 3600:2018 definition of notional thickness \(t_h = 2 A_g/u_e\);
Fig. 3.1.7.2 and Table 3.1.7.2._
"""

    render_expandable_step(
        page_key="shrinkage",
        step_id="shrinkage_th",
        title="Notional thickness t_h",
        summary_md=[
            "Check 1 — Notional thickness calculation for creep and shrinkage",
            rf"Result: $t_h = {thickness_table:d}$ mm (adopted from calculated {thickness_raw:.1f} mm)",
        ],
        status_kind=None,
        calc_md=render_th(),
    )

    def render_autogenous() -> str:
        return rf"""
**Purpose**

Estimate the **autogenous (chemical) shrinkage** strain $\varepsilon_{{cse}}$,
which develops even without drying (mainly due to hydration).

**Inputs**

- Concrete strength: $f'_c = {strength:.1f}\,\text{{MPa}}$
- Time after setting: $t = {time_days:.0f}\,\text{{days}}$

Final autogenous strain $\varepsilon^*_{{cse}}$:

For $f'_c \le 50\ \text{{MPa}}$:

\[
\varepsilon^*_{{cse}} = (0.07 f'_c - 0.5)\times 50\times 10^{{-6}}
\]

For $f'_c > 50\ \text{{MPa}}$:

\[
\varepsilon^*_{{cse}} = (0.08 f'_c - 1.0)\times 50\times 10^{{-6}}
\]

Time development (Cl. 3.1.7.2(2)):

\[
\varepsilon_{{cse}}(t) = \varepsilon^*_{{cse}} (1 - e^{{-0.04 t}})
\]

**Substitution**

Using $f'_c = {strength:.1f}$ MPa and $t = {time_days:.0f}$ days:

- Final autogenous strain:
  \[
  \varepsilon^*_{{cse}} \approx {eps_cse_final:.3e}
  \]
- At time $t$:
  \[
  \varepsilon_{{cse}}(t) \approx {eps_cse:.3e}
  \]

**Result**

- Autogenous shrinkage at $t = {time_days:.0f}$ days:
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

    def render_drying() -> str:
        return rf"""
**Purpose**

Estimate the **drying shrinkage** strain $\varepsilon_{{csd}}(t)$, which develops
as moisture is lost from the member.

**Inputs**

- Environment: **{environment}**
- Concrete strength: $f'_c = {strength:.1f}\,\text{{MPa}}$
- Notional thickness for tables: $t_h = {thickness_table:d}\,\text{{mm}}$
- Time since commencement of drying: $t = {time_days:.0f}\,\text{{days}}$

From **Table 3.1.7.2**, the **final design drying shrinkage**:

\[
\varepsilon^*_{{csd}} = {eps_csd_final*1e6:.0f}\times 10^{{-6}}
\quad (\text{{for }} f'_c \approx {snapshot.concrete_strength_table_mpa:.0f}\ \text{{MPa}},
\ t_h = {thickness_table:d}\ \text{{mm}},\ \text{{{environment_short}}})
\]

Time development coefficient $k_1$ from **Fig. 3.1.7.2**:

\[
k_1(t, t_h) = \frac{{\alpha_t t^{{0.8}}}}{{t^{{0.8}} + 0.15 t_h}},
\quad
\alpha_t = 0.8 + 1.2 e^{{-0.005 t_h}}
\]

Drying shrinkage at time $t$:

\[
\varepsilon_{{csd}}(t) = k_1(t, t_h)\, \varepsilon^*_{{csd}}
\]

**Substitution**

- $\alpha_t \approx 0.8 + 1.2 e^{{-0.005\times {thickness_table:d}}}$
- $k_1(t, t_h) \approx {k1:.3f}$
- Drying shrinkage:
  \[
  \varepsilon_{{csd}}(t)
  = {k1:.3f} \times {eps_csd_final*1e6:.0f}\times 10^{{-6}}
  \approx {eps_csd_t*1e6:.1f}\times 10^{{-6}}
  \]

**Result**

- Drying shrinkage at $t = {time_days:.0f}$ days:
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

    def render_total() -> str:
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
\approx {eps_total*1e6:.1f}\times 10^{{-6}}
\]

**Result**

- Total shrinkage at $t = {time_days:.0f}$ days:
  \[
  \varepsilon_{{cs}} \approx {eps_total*1e6:.1f}\times 10^{{-6}}
  \]
  (≈ {eps_total*1e6:.1f} microstrain)

_Ref: AS 3600:2018 Cl. 3.1.7 – total shrinkage._
"""

    render_expandable_step(
        page_key="shrinkage",
        step_id="shrinkage_total",
        title="Total shrinkage ε_cs",
        summary_md=[
            "Check 4 — Combination of autogenous and drying shrinkage components",
            rf"Result: $\varepsilon_{{cs}} = {eps_total*1e6:.1f}$ με",
        ],
        status_kind=None,
        calc_md=render_total(),
    )
    scroll_to_jump_after_render()


__all__ = ["render_shrinkage_checks"]
