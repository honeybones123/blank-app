"""Shear reinforcement presentation for Check 10.

The minimum-reinforcement result is resolved by the authoritative Shear
calculation before this renderer receives its frozen presentation projection.
"""

from __future__ import annotations

from dataclasses import dataclass

import streamlit as st

from calculations.shear import maximum_shear_spacing_mm
from engineering_page_sections.shear_checks_context import ShearCheckFamilyInput
from state_and_helpers import get_param
from step_ui import render_expandable_step
from widgets_helpers import info_i_button


@dataclass(frozen=True, slots=True)
class ShearReinforcementView:
    """Resolved, revision-matched display values for Shear Check 10."""

    evidence: ShearCheckFamilyInput
    Asv_min_over_s_check11: float
    Asv_over_s_check11: float
    min_shear_ok: bool
    min_shear_status: str


def render_shear_reinforcement_checks(view: ShearReinforcementView) -> None:
    """Render Shear Check 10 without recomputing its engineering result."""

    Asv_min_over_s_check11 = view.Asv_min_over_s_check11
    Asv_over_s_check11 = view.Asv_over_s_check11
    min_shear_ok = view.min_shear_ok
    min_shear_status = view.min_shear_status

    # =====================================================
    # Check 10 — SHEAR REINFORCEMENT LAYOUT (3 zones)
    # =====================================================
    _sz = get_param("shear_zone_results", None)
    _sz_enabled = bool(get_param("shear_zone_enabled", True))
    _shear_design_status = get_param("shear_design_status", None)
    _auto_sel_d = get_param("shear_auto_selected_lig_d_mm", None)
    _auto_sel_legs = get_param("shear_auto_selected_legs", None)

    _apply_auto_z10 = bool(get_param("shear_auto_design", False))
    _s_in_z10 = float(get_param("s_lig", 0.0) or 0.0)
    _s_mid_calc_z10 = float(get_param("shear_mid_spacing_calc_mm", 0.0) or 0.0)
    _s_mid_mode_z10 = str(get_param("shear_mid_spacing_mode", "") or "")
    _s_end_calc_z10 = float(get_param("shear_spacing_end_mm", 0.0) or 0.0)
    _s_mid_used_z10 = _s_mid_calc_z10 if _apply_auto_z10 else _s_in_z10
    _s_end_used_z10 = _s_end_calc_z10 if _apply_auto_z10 else _s_in_z10

    _midspan_derivation_md = ""
    if _s_mid_calc_z10 > 0.0:
        if _s_mid_mode_z10 == "max_spacing":
            _midspan_derivation_md = f"""

### Midspan spacing derivation

Midspan shear demand is low:

$V^* < \\phi V_{{uc}}$ at midspan

→ Concrete carries shear
→ No shear reinforcement required for strength at midspan

Spacing is therefore governed by maximum spacing:

$s \\le \\min(0.75D, 500\\ \\mathrm{{mm}})$

**Calculated midspan spacing (demand-based):** $s_{{\\mathrm{{mid,calc}}}} = {int(round(_s_mid_calc_z10))}$ mm

**Shown spacing ({'governing envelope' if _apply_auto_z10 else 'provided input'}):** $s = {int(round(_s_mid_used_z10))}$ mm
"""
        else:
            _midspan_derivation_md = f"""

### Midspan spacing derivation

Midspan shear demand requires reinforcement.

Required shear resisted by stirrups:

$$V_{{us}} = V^* - \\phi V_{{uc}}$$

Required reinforcement ratio (truss model, AS 3600):

$$\\frac{{A_{{sv}}}}{{s}} = \\frac{{V_{{us}}}}{{f_{{syv}} d_v \\cot\\theta_v}}$$

Rearranging for spacing with provided $A_{{sv}}$:

$$s = \\frac{{A_{{sv}}}}{{(A_{{sv}}/s)_{{\\mathrm{{req}}}}}}$$

**Calculated midspan spacing (demand-based):** $s_{{\\mathrm{{mid,calc}}}} = {int(round(_s_mid_calc_z10))}$ mm

**Shown spacing ({'governing envelope' if _apply_auto_z10 else 'provided input'}):** $s = {int(round(_s_mid_used_z10))}$ mm
"""

    _as3600_intent_md = """

### Code intent (AS 3600 Cl. 8.2.5.1)

- Shear reinforcement demand varies along the span with $V(x)$
- Provided $A_{sv}/s$ must be $\\ge$ required at all locations
- Detailing should avoid gaps in shear resistance
- Highest demand occurs near supports → tighter spacing is typically required there
"""

    check10_layout_calc_md = f"""
### Shear reinforcement check

**Provided reinforcement:**

$A_{{sv}}/s = {Asv_over_s_check11:.3f}\\ \\mathrm{{mm^2/mm}}$

**Minimum required (AS 3600 Cl. 8.2.5):**

$$\\left(\\frac{{A_{{sv}}}}{{s}}\\right)_{{min}} = 0.08\\sqrt{{f'_c}} \\cdot \\frac{{b_v}}{{f_{{sy}}}}$$

$= {Asv_min_over_s_check11:.3f}\\ \\mathrm{{mm^2/mm}}$

**Result:**

{"PASS" if min_shear_ok else "FAIL"}: {Asv_over_s_check11:.3f} {"≥" if min_shear_ok else "<"} {Asv_min_over_s_check11:.3f}
""" + _midspan_derivation_md + _as3600_intent_md

    def check10_layout_diagram_fn():
        check10_layout_info_fn()
        zones = get_param("shear_zone_results", None)
        status = get_param("shear_design_status", None)
        status_error = get_param("shear_design_error", None)
        check10_ok = bool(min_shear_ok)
        check10_util = (
            float(Asv_over_s_check11) / float(Asv_min_over_s_check11)
            if float(Asv_min_over_s_check11) > 0.0
            else None
        )
        if status == "INVALID" and not check10_ok:
            st.error("Shear design FAILED – detailing invalid")
            if status_error:
                st.caption(f"Reason: {status_error}")
            st.caption("Shear design requires valid V(x) from SFD and full envelope compliance.")
            return
        if not isinstance(zones, dict):
            zones = {}
        has_zones = isinstance(zones, dict) and bool(
            zones.get("summary_lines") or zones.get("strip_segments_mm") or zones.get("zones")
        )
        if not has_zones:
            st.info("Run calculation to generate shear layout")
            return

        s_end = float(get_param("shear_spacing_end_mm", 0.0) or 0.0)
        s_mid = float(get_param("shear_spacing_mid_mm", 0.0) or 0.0)
        util = check10_util

        if util is not None and check10_ok:
            st.success(f"Shear check: PASS (util = {float(util):.2f})")
        elif util is not None:
            st.error(f"Shear check: FAIL (util = {float(util):.2f})")
        elif status == "no_reo":
            st.error("Shear check: FAIL (util = 0.00)")

        _gov_lbl = str(get_param("shear_governing_spacing_source", "") or "").strip().lower()
        _gov_disp = (
            "Provided spacing"
            if _gov_lbl == "provided"
            else ("Required spacing" if _gov_lbl == "required" else "—")
        )
        _s_req_pub = get_param("shear_required_spacing_mm", None)
        _s_eff_pub = get_param("shear_effective_spacing_mm", None)
        _req_disp = (
            f"{float(_s_req_pub):.0f}"
            if _s_req_pub is not None
            else f"{int(round(s_end))}"
        )
        _eff_disp = (
            f"{float(_s_eff_pub):.0f}"
            if _s_eff_pub is not None
            else f"{int(round(float(_s_end_used_z10)))}"
        )
        st.markdown(
            f"""
**Required spacing (end zone, envelope / Check 10):** **{_req_disp} mm** (midspan layout **@ {int(round(s_mid))} mm**)

**Provided spacing (input, s_lig):** **{int(round(float(_s_in_z10)))} mm**

**Effective spacing used in φV_u check:** **{_eff_disp} mm** · **Governing source:** {_gov_disp}
"""
        )
        if abs(float(s_end) - float(_s_in_z10)) > 5.0:
            st.caption(
                "Required envelope spacing can differ from provided s_lig when demand or code limits govern — "
                "expected; shared s_lig is not overwritten."
            )
        no_variation = abs(float(s_end) - float(s_mid)) < 5.0
        D_mm = float(get_param("D", 0.0) or 0.0)
        s_max_code = maximum_shear_spacing_mm(D_mm)
        if no_variation:
            st.info(
                "Spacing is uniform along the span because shear demand is low. "
                "Concrete alone is sufficient (V* < φVuc), so reinforcement spacing is governed by the maximum allowable spacing "
                f"(s ≤ {int(s_max_code)} mm)."
            )
            st.caption(f"Uniform governing spacing = {int(round(s_end))} mm (maximum spacing governs)")
        else:
            st.info(
                "Spacing varies along the span because shear demand is higher near the support. "
                "Tighter spacing is required in the support zone, reducing toward midspan as shear decreases."
            )
            st.caption(
                f"Governing spacing varies from {int(round(s_end))} mm (support) to {int(round(s_mid))} mm (midspan)"
            )

    def check10_layout_info_fn():
        col_info_header, _ = st.columns([0.1, 0.9])
        with col_info_header:
            with info_i_button(help_text="Shear reinforcement spacing and minimum reinforcement check"):
                st.markdown(r"""
### Purpose

Design and verify shear reinforcement spacing along the member in accordance with AS 3600.
Spacing is varied along the span based on shear demand and checked against minimum reinforcement requirements.

### Zoning approach

- **Support zone (0-1.5dᵥ):** highest shear demand -> tighter spacing
- **Midspan region:** lower shear demand -> relaxed spacing
- Cantilever members only have a single support zone at the fixed end

### Behaviour

- Shear reinforcement demand follows the shear force diagram $V(x)$
- Where $V^* < \phi V_{uc}$, spacing is governed by maximum allowable spacing
- Where $V^* > \phi V_{uc}$, spacing is governed by required $A_{sv}/s$

### Detailing requirements (AS 3600 Cl. 8.2.5)

- Maximum spacing: **$s \le \min(0.75D, 500\ \mathrm{mm})$**
- Minimum spacing: sufficient for concrete placement
- Stirrups must be properly anchored

### When strut-and-tie may be required

- Deep beams (span/depth < 2.5)
- Loads applied within $d_v$ of a support
- Significant point loads near supports
- Complex or disturbed regions
                """)

    _z10_parts = []
    _has_layout = isinstance(_sz, dict) and bool(
        _sz.get("summary_lines") or _sz.get("strip_segments_mm") or _sz.get("zones")
    )
    if _has_layout:
        _util = (
            float(Asv_over_s_check11) / float(Asv_min_over_s_check11)
            if float(Asv_min_over_s_check11) > 0.0
            else None
        )
        _s_end = _s_end_used_z10
        _s_mid = _s_mid_used_z10
        _env = "PASS" if min_shear_ok else "FAIL"
        if _shear_design_status == "INVALID" and not min_shear_ok:
            _z10_parts.append("Status: INVALID (detailing blocked)")
            _s_err = get_param("shear_design_error", None)
            if _s_err:
                _z10_parts.append(f"Reason: {_s_err}")
        else:
            if _util is not None:
                _z10_parts.append(
                    f"Result: A_sv/s = {Asv_over_s_check11:.3f} vs min {Asv_min_over_s_check11:.3f} -> {'PASS' if min_shear_ok else 'FAIL'}"
                )
            _z10_parts.append(f"End @ {int(round(_s_end))} mm")
            _z10_parts.append(f"Mid @ {int(round(_s_mid))} mm")
    elif _sz_enabled:
        _z10_parts.append("Run calculation to generate shear layout")
    else:
        _z10_parts.append("Layout disabled")
    check10_layout_summary = "Check 10 — Shear reinforcement (spacing + minimum check) | " + " ".join(_z10_parts)

    render_expandable_step(
        page_key="shear",
        step_id="shear_check10",
        title="Check 10 — Shear reinforcement (spacing + minimum check)",
        summary_md=check10_layout_summary,
        status_kind=min_shear_status,
        calc_md=check10_layout_calc_md,
        diagram_render_fn=check10_layout_diagram_fn,
    )


__all__ = [
    "ShearReinforcementView",
    "render_shear_reinforcement_checks",
]

