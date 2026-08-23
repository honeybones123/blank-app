"""AS 3600 crack-control teaching-card presentation."""

from __future__ import annotations

from typing import Any

from engineering_page_sections.crack_checks_context import (
    CrackAs3600ChecksSnapshot,
)
from widgets_helpers import calcbox, page_divider, render_jumpable_step, render_section_title


def render_as3600_crack_checks(
    st_module: Any,
    snapshot: CrackAs3600ChecksSnapshot,
) -> None:
    page_divider()
    render_section_title("Crack Checks")

    limits_md = rf"""
**Crack width limit**

Characteristic crack width limit: \(w'_{{\max}} = {snapshot.width_limit_mm:.3f}\,\text{{mm}}\)

This value is chosen based on:
- Exposure classification
- Surface finish requirements
- Durability considerations

Typical values:
- 0.2 mm for aggressive environments or appearance-critical surfaces
- 0.3 mm for normal exposure
- 0.4 mm for less critical surfaces

**Member type**

Resultant action: **{snapshot.member_type}**

This affects which table method limits apply (Clause 8.6.2.2).
"""
    render_jumpable_step(
        uid="crk_step_1",
        title="Check 1 — Inputs & crack limits",
        summary_md=f"w'max = {snapshot.width_limit_mm:.3f} mm",
        body_fn=lambda: calcbox(limits_md, status=None),
        expanded=bool(snapshot.expanded_steps.get("crk_step_1", False)),
        status=None,
    )

    table_details_md = rf"""
**Concept**

Instead of calculating a crack width directly, Clause 8.6.2.2 limits the **steel stress**
on the cracked section:

- For members **primarily in tension**:
  \[
  \sigma_{{sr}} \le \sigma_{{\text{{max,A}}}} \quad \text{{(Table 8.6.2.2(A))}}
  \]
- For members **primarily in flexure**:
  \[
  \sigma_{{sr}} \le \max\left(\sigma_{{\text{{max,A}}}}, \sigma_{{\text{{max,B}}}}\right)
  \]
  where \(\sigma_{{\text{{max,B}}}}\) comes from **Table 8.6.2.2(B)**.

Under direct loading, \(\sigma_{{sr,1}} \le 0.8 f_{{sy}}\).

**Current input**

- Bar diameter: \(d_b = {snapshot.bar_diameter_mm:.1f}\,\text{{mm}}\) — *Derived on Crack page from reinforcement layout (bar diameter).*
- Spacing: \(s = {snapshot.bar_spacing_mm:.0f}\,\text{{mm}}\) — *Derived on Crack page from reinforcement layout (row spacing \(s_r\)).*
- Crack width limit: \(w'_{{\max}} = {snapshot.width_limit_mm:.1f}\,\text{{mm}}\)
- SLS steel stress: \(\sigma_{{sr}} = {snapshot.steel_stress_mpa:.1f}\,\text{{MPa}}\) — *Source: Bending page (SLS steel stress).*
- Yield strength: \(f_{{sy}} \approx {snapshot.steel_yield_strength_mpa:.0f}\,\text{{MPa}}\)

**From tables**

- Table 8.6.2.2(A): \(\sigma_{{\text{{max,A}}}} \approx {snapshot.table_limit_a_mpa:.1f}\,\text{{MPa}}\)
- Table 8.6.2.2(B): \(\sigma_{{\text{{max,B}}}} \approx {snapshot.table_limit_b_mpa:.1f}\,\text{{MPa}}\)
- Combined table limit ({snapshot.table_basis}):
  \[
  \sigma_{{\text{{table}}}} = {snapshot.table_combined_limit_mpa:.1f}\,\text{{MPa}}
  \]
- 0.8\(f_{{sy}}\) limit:
  \[
  0.8 f_{{sy}} \approx {snapshot.yield_limit_mpa:.1f}\,\text{{MPa}}
  \]

Overall allowable steel stress:

\[
\sigma_{{\text{{allow}}}} = \min\left(\sigma_{{\text{{table}}}},\,0.8 f_{{sy}}\right)
= {snapshot.allowable_stress_mpa:.1f}\,\text{{MPa}}
\]

**Check**

\[
\frac{{\sigma_{{sr}}}}{{\sigma_{{\text{{allow}}}}}}
= \frac{{{snapshot.steel_stress_mpa:.1f}}}{{{snapshot.allowable_stress_mpa:.1f}}}
\approx {snapshot.table_utilisation:.2f}
\quad\Rightarrow\quad
\text{{{"PASS" if snapshot.table_passes else "FAIL"}}}
\]
"""
    render_jumpable_step(
        uid="crk_step_2",
        title="Check 2 — Table method",
        summary_md=(
            f"σ_sr = {snapshot.steel_stress_mpa:.1f} MPa vs "
            f"{snapshot.allowable_stress_mpa:.1f} MPa → "
            f"{'PASS' if snapshot.table_passes else 'FAIL'}"
        ),
        body_fn=lambda: calcbox(
            table_details_md,
            status="pass" if snapshot.table_passes else "fail",
        ),
        expanded=bool(snapshot.expanded_steps.get("crk_step_2", False)),
        status="pass" if snapshot.table_passes else "fail",
    )

    rho_md = rf"""
**Step 1 – Effective reinforcement ratio**

Effective area in tension (simplified):

\[
A_{{c,\text{{eff}}}} \approx b \, h_{{\text{{eff}}}}
\quad\Rightarrow\quad
A_{{c,\text{{eff}}}} \approx {snapshot.effective_tension_area_mm2:.0f}\,\text{{mm}}^2
\]

\[
\rho_{{\text{{eff}}}} = \frac{{A_{{s,t}}}}{{A_{{c,\text{{eff}}}}}}
= \frac{{{snapshot.tension_steel_area_mm2:.0f}}}{{{snapshot.effective_tension_area_mm2:.0f}}}
\approx {snapshot.effective_reinforcement_ratio:.4f}
\]

*Source: \(A_{{s,t}} = {snapshot.tension_steel_area_mm2:.0f}\,\text{{mm}}^2\) — resolved from active tension reinforcement geometry.*
"""
    strain_md = rf"""
**Step 2 – Difference in mean strain** \(\varepsilon_{{sm}} - \varepsilon_{{cm}}\)

From Cl. 8.6.2.3(2):

\[
\varepsilon_{{sm}} - \varepsilon_{{cm}}
= \frac{{\sigma_{{sr}}}}{{E_s}}
- \frac{{0.6 f_{{ct,\text{{eff}}}}}}{{E_s \rho_{{\text{{eff}}}}}}\left(1 + n_e \rho_{{\text{{eff}}}}\right)
+ \varepsilon_{{cs}}
\ge 0.6 \frac{{\sigma_{{sr}}}}{{E_s}}
\]

With:

- \(\sigma_{{sr}} = {snapshot.steel_stress_mpa:.1f}\,\text{{MPa}}\) — *Source: Bending page (SLS steel stress).*
- \(f_{{ct,\text{{eff}}}} = {snapshot.concrete_tensile_strength_mpa:.2f}\,\text{{MPa}}\) — *Source: \(0.6\sqrt{{f'c}}\) from concrete strength used for crack control.*
- \(E_s = {snapshot.steel_modulus_mpa:.0f}\,\text{{MPa}},\ E_c = {snapshot.concrete_modulus_mpa:.0f}\,\text{{MPa}}\)
- \(\varphi_{{ce}} = {snapshot.creep_coefficient:.2f}\) — *Source: Creep page (\(\varphi_{{cc}}(t)\)).*
- \(n_e = (1 + \varphi_{{ce}}) E_s/E_c \approx {snapshot.effective_modular_ratio:.2f}\)
- \(\varepsilon_{{cs}} \approx {snapshot.shrinkage_microstrain:.1f}\times 10^{{-6}}\) — *Source: Shrinkage page (\(\varepsilon_{{cs,total}}\)).*

This gives:

\[
\varepsilon_{{sm}} - \varepsilon_{{cm}} \approx {snapshot.strain_difference:.3e}
\]
"""
    spacing_md = rf"""
**Step 3 – Maximum crack spacing**

\[
s_{{r,\max}} = 3.4 c + 0.3 k_1 k_2 \frac{{d_b}}{{\rho_{{\text{{eff}}}}}}
\]

Using:

- \(c = {snapshot.cover_mm:.1f}\,\text{{mm}},\ d_b = {snapshot.bar_diameter_mm:.1f}\,\text{{mm}}\) — *\(d_b\) from Crack page reinforcement layout.*
- \(k_1 = {snapshot.bond_coefficient:.2f},\ k_2 = {snapshot.strain_distribution_factor:.2f}\)

\[
s_{{r,\max}} \approx {snapshot.maximum_crack_spacing_mm:.1f}\,\text{{mm}}
\]
"""
    width_md = rf"""
**Step 4 – Crack width**

\[
w = s_{{r,\max}}(\varepsilon_{{sm}} - \varepsilon_{{cm}})
\approx {snapshot.maximum_crack_spacing_mm:.1f} \times {snapshot.strain_difference:.3e}
\approx {snapshot.crack_width_mm:.3f}\,\text{{mm}}
\]

Calculated capacity (allowable crack width):

\[
w'_{{\max}} = {snapshot.width_limit_mm:.1f}\,\text{{mm}}, \quad
\frac{{w}}{{w'_{{\max}}}} \approx {snapshot.width_utilisation:.2f}
\Rightarrow\ \text{{{"PASS" if snapshot.width_passes else "FAIL"}}}
\]
"""

    def width_body() -> None:
        calcbox(rho_md, status=None)
        calcbox(strain_md, status=None)
        calcbox(spacing_md, status=None)
        calcbox(width_md, status="pass" if snapshot.width_passes else "fail")

    render_jumpable_step(
        uid="crk_step_3",
        title="Check 3 — Direct crack width",
        summary_md=(
            f"w = {snapshot.crack_width_mm:.3f} mm ≤ "
            f"{snapshot.width_limit_mm:.3f} mm → "
            f"{'PASS' if snapshot.width_passes else 'FAIL'}"
        ),
        body_fn=width_body,
        expanded=bool(snapshot.expanded_steps.get("crk_step_3", False)),
        status="pass" if snapshot.width_passes else "fail",
    )

    overall_passes = snapshot.table_passes and snapshot.width_passes
    governing_md = rf"""
**Governing outcome**

Both checks must pass for crack control to be satisfied:

1. **Table method**: \(\sigma_{{sr}} = {snapshot.steel_stress_mpa:.1f}\,\text{{MPa}} \le {snapshot.allowable_stress_mpa:.1f}\,\text{{MPa}}\) → **{"PASS" if snapshot.table_passes else "FAIL"}**

2. **Direct calculation**: \(w = {snapshot.crack_width_mm:.3f}\,\text{{mm}} \le {snapshot.width_limit_mm:.1f}\,\text{{mm}}\) → **{"PASS" if snapshot.width_passes else "FAIL"}**

**Overall result**: **{"PASS" if overall_passes else "FAIL"}**

Both the table method and direct calculation checks must pass for the crack control requirement to be satisfied.
"""
    render_jumpable_step(
        uid="crk_step_4",
        title="Check 4 — Governing outcome",
        summary_md="Both checks must pass (table stress + direct width)",
        body_fn=lambda: calcbox(governing_md, status=overall_passes),
        expanded=bool(snapshot.expanded_steps.get("crk_step_4", False)),
        status=overall_passes,
    )


__all__ = ["render_as3600_crack_checks"]
