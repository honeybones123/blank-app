"""Calculation-check cards for AS 5100 and CIRIA C766 crack methods."""

from __future__ import annotations

from typing import Any, Mapping

from widgets_helpers import calcbox, page_divider, render_jumpable_step, render_section_title


def render_as5100_method_checks(
    st_module: Any,
    *,
    result: Any,
    expanded_steps: Mapping[str, bool],
) -> None:
    page_divider()
    render_section_title("Calculation Checks")
    design_thickness = float(result.calculation_thickness_per_face_mm)
    ratio = float(result.required_ratio)
    area_md = rf"""
**Required horizontal reinforcement per face — AS 5100.5 Clause 11.7.2**

\(t_d = {design_thickness:.0f}\,\text{{mm per face}}\)

\(A_{{s,req}} = {ratio:.3f}\,t_d\,(1000) = {result.required_area_per_face_mm2_per_m:,.0f}\,\text{{mm}}^2/\text{{m per face}}\)

Provided: \({result.provided_area_per_face_mm2_per_m:,.0f}\,\text{{mm}}^2/\text{{m per face}}\)
"""
    render_jumpable_step(
        uid="crk_as5100_area",
        title="Check 1 — Horizontal reinforcement per face",
        summary_md=(
            f"Required {result.required_area_per_face_mm2_per_m:,.0f} mm²/m; "
            f"provided {result.provided_area_per_face_mm2_per_m:,.0f} mm²/m"
        ),
        body_fn=lambda: calcbox(
            area_md, status="pass" if result.area_passes else "fail"
        ),
        expanded=bool(expanded_steps.get("crk_as5100_area", False)),
        status=result.area_passes,
    )
    spacing_md = rf"""
**Spacing check**

Provided vertical spacing: \({float(result.provided_spacing_mm or 0.0):.0f}\,\text{{mm}}\)

Maximum permitted spacing: \({result.maximum_spacing_mm:.0f}\,\text{{mm}}\)
"""
    render_jumpable_step(
        uid="crk_as5100_spacing",
        title="Check 2 — Reinforcement spacing",
        summary_md=(
            f"Provided {float(result.provided_spacing_mm or 0.0):.0f} mm; "
            f"maximum {result.maximum_spacing_mm:.0f} mm"
        ),
        body_fn=lambda: calcbox(
            spacing_md, status="pass" if result.spacing_passes else "fail"
        ),
        expanded=bool(expanded_steps.get("crk_as5100_spacing", False)),
        status=result.spacing_passes,
    )


def render_c766_method_checks(
    st_module: Any,
    *,
    result: Any,
    restraint_type: str,
    expanded_steps: Mapping[str, bool],
) -> None:
    page_divider()
    render_section_title("Calculation Checks")
    crack_width = float(result.characteristic_crack_width_mm or 0.0)
    spacing = float(result.maximum_crack_spacing_mm or 0.0)
    strain = float(getattr(result, "crack_inducing_strain", 0.0) or 0.0)
    strain_md = rf"""
**Restrained-deformation strain — CIRIA C766 ({restraint_type.replace('_', ' ').title()})**

Crack-inducing strain: \(\varepsilon_{{cr}} = {strain * 1e6:,.0f}\,\mu\varepsilon\)

Maximum crack spacing: \(s_{{r,max}} = {spacing:,.0f}\,\text{{mm}}\)
"""
    render_jumpable_step(
        uid="crk_c766_strain",
        title="Check 1 — Restrained-deformation strain",
        summary_md=(
            f"Crack-inducing strain {strain * 1e6:,.0f} µε; "
            f"spacing {spacing:,.0f} mm"
        ),
        body_fn=lambda: calcbox(strain_md, status=None),
        expanded=bool(expanded_steps.get("crk_c766_strain", False)),
        status=None,
    )
    width_md = rf"""
**Characteristic crack width — EC2 equation path**

\(w_k = s_{{r,max}}\,\varepsilon_{{cr}} = {crack_width:.3f}\,\text{{mm}}\)

This is an equation-path result; corrected CIRIA spreadsheet parity is not claimed.
"""
    render_jumpable_step(
        uid="crk_c766_width",
        title="Check 2 — Characteristic crack width",
        summary_md=f"Calculated crack width {crack_width:.3f} mm",
        body_fn=lambda: calcbox(width_md, status=None),
        expanded=bool(expanded_steps.get("crk_c766_width", False)),
        status=None,
    )


__all__ = ["render_as5100_method_checks", "render_c766_method_checks"]
