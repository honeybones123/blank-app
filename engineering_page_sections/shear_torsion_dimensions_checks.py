"""Torsion and effective-section presentation for Shear Checks 1-3.

The authoritative Shear calculation bundle is resolved before this module is
called. This module owns only the visible teaching cards and their diagrams.
"""

from __future__ import annotations

from dataclasses import dataclass

import streamlit as st

from engineering_page_sections.shear_checks_context import ShearCheckFamilyInput
from engineering_page_sections.shear_visualisation import (
    SHEAR_VISUAL_HEIGHT_PX,
    SHEAR_VISUAL_MAX_WIDTH_PX,
    _render_centered_shear_plotly,
    _standardise_shear_visual_layout,
)
from shear_diagrams import (
    build_torsion_plotly_figure,
    plot_shear_step3_section_params_plotly,
    plot_shear_torsion_section_2d,
)
from state_and_helpers import get_param
from step_ui import render_expandable_step
from widgets_helpers import info_i_button


@dataclass(frozen=True, slots=True)
class ShearTorsionDimensionsView:
    """Resolved, revision-matched display values for Shear Checks 1-3."""

    evidence: ShearCheckFamilyInput
    A_cp: float
    Ao: float
    Asv: float
    D: float
    D_used: float
    T_star: float
    Tcr_kNm: float
    V_eq: float
    V_star: float
    b: float
    b_used: float
    b_v: float
    d: float
    d_v: float
    dv_1: float
    dv_2: float
    f_syv: float
    fc: float
    k_d: float
    legs: float
    lig_d: float
    method: str
    phi: float
    s: float
    sigma_cp: float
    step1_req: str
    step1_text: str
    sum_duct: float
    theta_deg: float
    torsion_eq_kN: float
    torsion_required: bool
    torsion_required_limit: float
    u_c: float
    uh: float


def _fmt(val, decimals=1):
    """Safe number formatter retained from the established Shear cards."""

    try:
        if val is None:
            return "—"
        return f"{float(val):.{decimals}f}"
    except Exception:
        return "—"


def render_shear_torsion_dimensions_checks(
    view: ShearTorsionDimensionsView,
) -> None:
    """Render Shear Checks 1-3 without recomputing engineering results."""

    A_cp = view.A_cp
    Ao = view.Ao
    Asv = view.Asv
    D = view.D
    D_used = view.D_used
    T_star = view.T_star
    Tcr_kNm = view.Tcr_kNm
    V_eq = view.V_eq
    V_star = view.V_star
    b = view.b
    b_used = view.b_used
    b_v = view.b_v
    d = view.d
    d_v = view.d_v
    dv_1 = view.dv_1
    dv_2 = view.dv_2
    f_syv = view.f_syv
    fc = view.fc
    k_d = view.k_d
    legs = view.legs
    lig_d = view.lig_d
    method = view.method
    phi = view.phi
    s = view.s
    sigma_cp = view.sigma_cp
    step1_req = view.step1_req
    step1_text = view.step1_text
    sum_duct = view.sum_duct
    theta_deg = view.theta_deg
    torsion_eq_kN = view.torsion_eq_kN
    torsion_required = view.torsion_required
    torsion_required_limit = view.torsion_required_limit
    u_c = view.u_c
    uh = view.uh

    # =====================================================
    # Check 1 — TORSION CRACKING CHECK (T_cr)
    # =====================================================
    if torsion_required:
        check1_calc_md = f"""
*Purpose: Determine if torsion design is required by checking if $T^* > 0.25 \\phi T_{{cr}}$.*

**Inputs:**

- Section: $b = {b_used:.0f}$ mm, $D = {D_used:.0f}$ mm
- Derived: $A_{{cp}} = {A_cp:.0f}$ mm², $u_c = {u_c:.0f}$ mm
- Concrete: $f'_c = {fc:.1f}$ MPa, $\\sigma_{{cp}} = {sigma_cp:.2f}$ MPa
- Torsion geometry: $A_o = 0.9 A_{{cp}} = {Ao:.0f}$ mm², $u_h = {uh:.0f}$ mm

---

**Formula (AS 3600 Cl. 8.3.4):**

$$\\large T_{{cr}} = 0.33\\sqrt{{f'_c}} \\cdot \\frac{{A_{{cp}}^2}}{{u_c}} \\cdot \\sqrt{{1 + \\frac{{\\sigma_{{cp}}}}{{0.33\\sqrt{{f'_c}}}}}}$$

**Substitution:**

$$\\large T_{{cr}} = 0.33\\sqrt{{{fc:.1f}}} \\cdot \\frac{{{A_cp:.0f}^2}}{{{u_c:.0f}}} \\cdot \\sqrt{{1 + \\frac{{{sigma_cp:.2f}}}{{0.33\\sqrt{{{fc:.1f}}}}}}} = {Tcr_kNm:,.1f}\\ \\text{{kNm}}$$

---

**Result:**

- Limit: $0.25 \\phi T_{{cr}} = 0.25 \\times {phi:.2f} \\times {Tcr_kNm:,.1f} = {torsion_required_limit:,.1f}$ kNm
- Demand: $T^* = {T_star:.1f}$ kNm
- Condition: $T^* {step1_req} 0.25 \\phi T_{{cr}}$
- **Conclusion: torsion design is {step1_text}.**
"""
    else:
        check1_calc_md = f"""
*Purpose: Screen whether torsion must be treated as a design action (AS 3600 Cl. 8.3.4).*

**Inputs (for $T_{{cr}}$):**

- Section: $b = {b_used:.0f}$ mm, $D = {D_used:.0f}$ mm
- Derived: $A_{{cp}} = {A_cp:.0f}$ mm², $u_c = {u_c:.0f}$ mm
- Concrete: $f'_c = {fc:.1f}$ MPa, $\\sigma_{{cp}} = {sigma_cp:.2f}$ MPa

---

**Cracking torque $T_{{cr}}$**

$$\\large T_{{cr}} = 0.33\\sqrt{{f'_c}} \\cdot \\frac{{A_{{cp}}^2}}{{u_c}} \\cdot \\sqrt{{1 + \\frac{{\\sigma_{{cp}}}}{{0.33\\sqrt{{f'_c}}}}}}$$

$$\\large T_{{cr}} = {Tcr_kNm:,.1f}\\ \\text{{kNm}}$$

**Screening limit $0.25 \\phi T_{{cr}}$**

$$0.25 \\phi T_{{cr}} = 0.25 \\times {phi:.2f} \\times {Tcr_kNm:,.1f} = {torsion_required_limit:,.1f}\\ \\text{{kNm}}$$

**Compare demand**

$T^* = {T_star:.1f}$ kNm → $T^* \\le 0.25 \\phi T_{{cr}}$.

**Conclusion**

Torsion design is not required, so torsion is not carried forward as a design action.
"""

    # Diagram render function (native Plotly — same pipeline as MCFT)
    def check1_diagram_fn():
        st.markdown(
            """
            <style>
            .shear-sf-subheading { margin: 0.35rem 0 0.3rem 0; font-size: 0.95rem; font-weight: 600; color: rgba(49,51,63,0.95); }
            </style>
            """,
            unsafe_allow_html=True,
        )
        st.markdown(
            '<p class="shear-sf-subheading">Torsion crack pattern schematic</p>',
            unsafe_allow_html=True,
        )
        L_mm_diagram = float(
            get_param("L", st.session_state.get("shear_L", 8000.0))
        )
        torsion_fig = build_torsion_plotly_figure(
            torsion_design_required=torsion_required,
            L_mm=L_mm_diagram,
            b_mm=b_used,
            D_mm=D_used,
            theta_crack_deg=theta_deg,
        )
        torsion_fig = _standardise_shear_visual_layout(torsion_fig)
        _render_centered_shear_plotly(
            torsion_fig,
            chart_key="torsion_cracking_diagram",
            max_width_px=SHEAR_VISUAL_MAX_WIDTH_PX,
        )

    # Info render function (popover) — trigger on the right (same pattern as Checks 5–9)
    def check1_info_fn():
        _, col_info = st.columns([0.93, 0.07])
        with col_info:
            _info_pad, col_btn = st.columns([0.35, 0.65])
            with col_btn:
                with info_i_button(help_text="Torsion cracking (what this check means)"):
                    st.markdown(r"""
### Torsion cracking behaviour

**What torsion cracking means**

Torsion cracking occurs when the applied torsional moment exceeds the concrete's cracking resistance, causing diagonal cracking around the section perimeter.

Before cracking, torsion is resisted mainly by the concrete acting elastically. After cracking, resistance shifts to a **space-truss mechanism** (diagonal compression struts + transverse reinforcement).

**Why the 0.25·φ·Tcr threshold is used**

AS 3600 uses **0.25·φ·Tcr** to distinguish between:

- **uncracked torsion** (elastic concrete behaviour), and

- **cracked torsion** (truss action governs).

Below this limit, torsion does not significantly change member behaviour and detailed torsion design is not required.

**Key takeaway**

This step only decides whether torsion is **cracked** or **uncracked**.

After this, torsion is treated as a known condition and is not re-explained.
            """)

    # Build summary line (compact wording when screened out)
    if torsion_required:
        check1_summary = (
            "Check 1 — Torsion cracking check | Result: "
            "T* > 0.25 φTcr → torsion design required"
        )
    else:
        check1_summary = (
            "Check 1 — Torsion cracking check | Result: "
            "T* ≤ 0.25 φTcr → torsion design not required"
        )

    # Convert status
    status_kind = "pass" if not torsion_required else "fail"

    render_expandable_step(
        page_key="shear",
        step_id="shear_check1",
        title="Check 1 — Torsion cracking check",
        summary_md=check1_summary,
        status_kind=status_kind,
        calc_md=check1_calc_md,
        diagram_render_fn=check1_diagram_fn,
        info_render_fn=check1_info_fn,
        anchor_id="torsion_considered",
        diagram_outside_expander=False,
    )

    # =====================================================
    # Check 2 — CONVERT TORSION INTO AN EQUIVALENT SHEAR V_eq*
    # =====================================================
    if torsion_required:
        # --- Full equivalent shear including torsion ---
        check2_calc_md = f"""
*Purpose: Convert torsion into an equivalent shear force for combined shear + torsion design.*

**Inputs:**

- Shear demand: $V^* = {V_star:.1f}$ kN
- Torsion: $T^* = {T_star:.1f}$ kNm
- Torsion geometry: $u_h = {uh:.0f}$ mm, $A_o = {Ao:.0f}$ mm²

---

**Formula (AS 3600 Cl. 8.2.3):**

$$\\large V_{{t,eq}} = 0.9 \\cdot \\frac{{T^* u_h}}{{2 A_o}}$$

$$\\large V_{{eq}}^* = \\sqrt{{(V^*)^2 + V_{{t,eq}}^2}}$$

**Substitution:**

$$\\large V_{{t,eq}} = 0.9 \\cdot \\frac{{{T_star:.1f} \\times 10^6 \\times {uh:.0f}}}{{2 \\times {Ao:.0f}}} = {torsion_eq_kN:.1f}\\ \\text{{kN}}$$

$$\\large V_{{eq}}^* = \\sqrt{{({V_star:.1f})^2 + ({torsion_eq_kN:.1f})^2}} = {V_eq:.1f}\\ \\text{{kN}}$$

---

**Result:**

- Torsion is included as an equivalent shear.
- **$V_{{eq}}^* = {V_eq:.1f}$ kN**
"""
    else:
        # --- Compact bypass: V_eq and Vt_eq_kN already from shear_results (unchanged logic) ---
        check2_calc_md = f"""
*Purpose: Carry forward the design shear action when torsion design is not required.*

Since torsion design is not required from Check 1, torsion is not carried forward as a design action.

Take $T^* = 0$ for design, so $V_{{t,eq}} = 0$.

Therefore $V_{{eq}}^* = V^*$ (the general combination $V_{{eq}}^* = \\sqrt{{(V^*)^2 + V_{{t,eq}}^2}}$ reduces to $|V^*|$ here).

---

**Result**

- Torsion not carried forward
- $V_{{eq}}^* = V^* = {V_eq:.1f}$ kN
"""

    # Diagram render function
    def check2_diagram_fn():
        _sf_key = "stress_flow_mode"
        if st.session_state.get(_sf_key) not in ("VT", "V", "T"):
            st.session_state[_sf_key] = "VT"

        _SF_SEG_LABELS = {"VT": "V+T", "V": "V", "T": "T"}
        _SF_HELPER = {
            "VT": "Combined shear + torsion",
            "V": "Shear only",
            "T": "Torsion only",
        }

        st.markdown(
            """
            <style>
            .shear-sf-subheading { margin: 0.35rem 0 0.3rem 0; font-size: 0.95rem; font-weight: 600; color: rgba(49,51,63,0.95); }
            .shear-sf-helper { margin: 0.2rem 0 0.3rem 0; font-size: 0.875rem; color: rgba(49,51,63,0.72); line-height: 1.35; }
            </style>
            """,
            unsafe_allow_html=True,
        )

        _picked = st.segmented_control(
            "Stress flow mode",
            options=["VT", "V", "T"],
            default=st.session_state[_sf_key],
            format_func=lambda m: _SF_SEG_LABELS.get(m, "V+T"),
            key=_sf_key,
            width="stretch",
        )

        mode = _picked if _picked in ("VT", "V", "T") else st.session_state.get(_sf_key, "VT")
        if mode not in ("VT", "V", "T"):
            mode = "VT"
        helper = _SF_HELPER.get(mode)
        if helper:
            st.markdown(
                f'<p class="shear-sf-helper">{helper}</p>',
                unsafe_allow_html=True,
            )

        st.markdown(
            '<p class="shear-sf-subheading">Stress flow schematic</p>',
            unsafe_allow_html=True,
        )

        mode_short = "V+T" if mode == "VT" else mode

        from section_layout import compute_section_layout

        layout = compute_section_layout()
        raw_shape = layout.get("shape_name")
        shape_name = "Rectangle (b × D)"
        if isinstance(raw_shape, str) and raw_shape.strip():
            shape_name = raw_shape.strip()
        dims = layout.get("dims")
        reo = layout.get("reo")
        if not isinstance(dims, dict):
            dims = {}
        if not isinstance(reo, dict):
            reo = {}

        try:
            fig = plot_shear_torsion_section_2d(
                shape_name=shape_name,
                dims=dims,
                reo=reo,
                mode=mode_short,
                show_labels=True,
                compact_stress_labels=True,
                show_schematic_footer=False,
            )
        except ValueError as e:
            st.error(f"Reinforcement layout failed: {e}")
            reo_no_bars = dict(reo)
            reo_no_bars.update({
                "nb_top": 0,
                "db_top": 0.0,
                "nb_bot": 0,
                "db_bot": 0.0,
                "nb_or_s_top_1": 0.0,
                "nb_or_s_top_2": 0.0,
                "nb_or_s_bot_1": 0.0,
                "nb_or_s_bot_2": 0.0,
                "lig_d": 0.0,
                "lig_legs": 0,
            })
            fig = plot_shear_torsion_section_2d(
                shape_name=shape_name,
                dims=dims,
                reo=reo_no_bars,
                mode=mode_short,
                show_labels=True,
                compact_stress_labels=True,
                show_schematic_footer=False,
            )
        _render_centered_shear_plotly(
            fig,
            chart_key="shear_equivalent_shear_stress_flow_diagram",
            max_width_px=SHEAR_VISUAL_MAX_WIDTH_PX,
        )

    # Info render function (popover)
    def check2_info_fn():
        _, col_info = st.columns([0.93, 0.07])
        with col_info:
            _info_pad, col_btn = st.columns([0.35, 0.65])
            with col_btn:
                _c2_help = (
                    "Equivalent shear (combined demand)"
                    if torsion_required
                    else "Equivalent shear when torsion is screened out"
                )
                with info_i_button(help_text=_c2_help):
                    if torsion_required:
                        st.markdown(r"""
### Combined shear demand (Veq*)

**Why torsion is converted to an equivalent shear**

When the section is cracked, torsion introduces longitudinal force components that interact with shear behaviour.

A practical way to capture this is to convert torsion into a **shear-equivalent demand**.

**Vector combination (one idea)**

The combined demand is taken as a vector sum of:

- the applied shear V*, and

- the torsion-equivalent shear component.

This reflects simultaneous actions acting through different internal force components.

**Why it is conservative**

Vector combination slightly overestimates the combined effect when one action dominates.

This conservatism is intentional and consistent with simplified design assumptions.
            """)
                    else:
                        st.markdown(r"""
### Equivalent shear after torsion screening

When Check 1 shows **torsion design is not required**, torsion is not carried into shear design as a separate action.

For the equivalent shear used in later checks, $V_{t,eq} = 0$ and $V_{eq}^* = |V^*|$ in this app’s convention, so downstream shear checks use the applied shear demand magnitude only.
            """)

    # Build summary line
    if torsion_required:
        check2_summary = (
            f"Check 2 — Equivalent shear $V_{{eq}}^*$ | Result: $V_{{eq}}^* = {V_eq:.1f}$ kN"
        )
    else:
        check2_summary = (
            f"Check 2 — Equivalent shear $V_{{eq}}^*$ | "
            f"Torsion not carried forward; $V_{{eq}}^* = V^* = {V_eq:.1f}$ kN"
        )

    render_expandable_step(
        page_key="shear",
        step_id="shear_check2",
        title="Check 2 — Equivalent shear $V_{eq}^*$",
        summary_md=check2_summary,
        status_kind=None,
        calc_md=check2_calc_md,
        diagram_render_fn=check2_diagram_fn if torsion_required else None,
        info_render_fn=check2_info_fn,
        anchor_id="veq",
    )

    # =====================================================
    # Check 3 — EFFECTIVE SECTION & SHEAR REINFORCEMENT
    # =====================================================
    check3_calc_md = f"""
*Purpose: Calculate the shear-resisting section parameters $A_{{sv}}$, $b_v$ and $d_v$ for AS 3600 shear design.*

**Inputs:**

- Section geometry: $b = {_fmt(b)}$ mm, $D = {_fmt(D)}$ mm, $d = {_fmt(d)}$ mm
- Transverse reinforcement: $d_{{lig}} = {_fmt(lig_d)}$ mm, $n_{{legs}} = {_fmt(legs, 0)}$, $s_{{lig}} = {_fmt(s)}$ mm, $f_{{sy,v}} = {_fmt(f_syv)}$ MPa
- Ducts in web: $\\sum d_{{duct}} = {_fmt(sum_duct)}$ mm, $k_d = {_fmt(k_d)}$
- Shear model: $k_v$ method = {method}

---

**Formula (a) – Transverse steel area $A_{{sv}}$:**

$$\\large A_{{sv}} = n_{{legs}} \\cdot \\frac{{\\pi d_{{lig}}^2}}{{4}}$$

**Substitution:**

$$\\large A_{{sv}} = {_fmt(legs, 0)} \\cdot \\frac{{\\pi \\times {_fmt(lig_d)}^2}}{{4}} = {_fmt(Asv)}\\ \\text{{mm}}^2$$

Stirrups at spacing: $s_{{lig}} = {_fmt(s)}$ mm

---

**Formula (b) – Effective web width $b_v$ (AS 3600 Cl. 8.2.2):**

$$\\large b_v = b - k_d \\sum d_{{duct}}$$

**Substitution:**

$$\\large b_v = {_fmt(b)} - {_fmt(k_d)} \\times {_fmt(sum_duct)} = {_fmt(b_v)}\\ \\text{{mm}}$$

---

**Formula (c) – Shear depth $d_v$ (AS 3600 Cl. 8.2.2):**

$$\\large d_v = \\max(0.72D,\\ 0.9d)$$

**Substitution:**

$0.72D = 0.72 \\times {_fmt(D)} = {_fmt(dv_1)}$ mm

$0.9d = 0.9 \\times {_fmt(d)} = {_fmt(dv_2)}$ mm

$$\\large d_v = {_fmt(d_v)}\\ \\text{{mm}}$$

---

**Result:**

- $A_{{sv}} = {_fmt(Asv)}$ mm² with stirrups at $s_{{lig}} = {_fmt(s)}$ mm
- $b_v = {_fmt(b_v)}$ mm, $d_v = {_fmt(d_v)}$ mm
"""

    # Diagram render function
    def check3_diagram_fn():
        # Get section geometry (from shared)
        b_mm = float(b)
        D_mm = float(D)

        # Get Check 3 computed shear parameters
        bv_mm = float(b_v)
        dv_mm = float(d_v)

        # Optional if available
        Asv_mm2 = float(Asv) if Asv else None
        s_lig_mm = float(s) if s else None

        from section_layout import compute_section_layout
        layout = compute_section_layout()
        shape_name = layout.get("shape_name", "Rectangle (b × D)")
        dims = layout.get("dims", {})
        reo = layout.get("reo", {})
        b_plot = float(dims.get("bf", dims.get("b", b_mm)))
        cover_bot = float(reo.get("cover_bot", 40.0))
        cover_top = float(reo.get("cover_top", 40.0))
        cover_side = float(reo.get("cover_side", min(cover_top, cover_bot)) or min(cover_top, cover_bot))

        # Get ligature parameters for drawing stirrups
        lig_d_val = float(lig_d) if lig_d else None
        lig_legs_val = int(legs) if legs else None

        try:
            fig = plot_shear_step3_section_params_plotly(
                b_mm=b_plot,
                D_mm=D_mm,
                bv_mm=bv_mm,
                dv_mm=dv_mm,
                Asv_mm2=Asv_mm2,
                s_lig_mm=s_lig_mm,
                lig_d=lig_d_val,
                lig_legs=lig_legs_val,
                cover_bot=cover_bot,
                cover_top=cover_top,
                cover_side=cover_side,
                height=SHEAR_VISUAL_HEIGHT_PX,
                label_pad=14,
                shape_name=shape_name,
                dims=dims,
                reo=reo,
            )
        except ValueError as e:
            st.error(f"Reinforcement layout failed: {e}")
            reo_no_bars = dict(reo)
            reo_no_bars.update({
                "nb_top": 0,
                "db_top": 0.0,
                "nb_bot": 0,
                "db_bot": 0.0,
                "nb_or_s_top_1": 0.0,
                "nb_or_s_top_2": 0.0,
                "nb_or_s_bot_1": 0.0,
                "nb_or_s_bot_2": 0.0,
                "lig_d": 0.0,
                "lig_legs": 0,
            })
            fig = plot_shear_step3_section_params_plotly(
                b_mm=b_plot,
                D_mm=D_mm,
                bv_mm=bv_mm,
                dv_mm=dv_mm,
                Asv_mm2=Asv_mm2,
                s_lig_mm=s_lig_mm,
                lig_d=lig_d_val,
                lig_legs=lig_legs_val,
                cover_bot=cover_bot,
                cover_top=cover_top,
                cover_side=cover_side,
                height=SHEAR_VISUAL_HEIGHT_PX,
                label_pad=14,
                shape_name=shape_name,
                dims=dims,
                reo=reo_no_bars,
            )
        _render_centered_shear_plotly(
            fig,
            chart_key="shear_effective_section_reinforcement_diagram",
        )

    # Info render function (popover) — trigger on the right
    def check3_info_fn():
        _, col_info = st.columns([0.93, 0.07])
        with col_info:
            _info_pad, col_btn = st.columns([0.35, 0.65])
            with col_btn:
                with info_i_button(help_text="Effective shear geometry (bv, dv)"):
                    st.markdown(r"""
### Effective shear geometry

**bv (effective web width)**

bv is the web width available to resist shear.

It excludes regions that do not participate effectively in shear transfer (e.g., ducts/voids).

**dv (effective shear depth)**

dv is the effective depth used for shear force transfer through the web.

It reflects the shear force path, not just reinforcement location.

**Why dv ≠ flexural depth d**

d is defined by tension reinforcement location (flexure).

dv is defined by shear transfer geometry (shear). They represent different mechanisms.
            """)

    # Build summary line
    if legs == 0:
        check3_summary = f"Check 3 — Shear-resisting section ($b_v$, $d_v$, ligs) | Result: No shear reinforcement provided, $b_v = {_fmt(b_v)}$ mm, $d_v = {_fmt(d_v)}$ mm"
    else:
        check3_summary = f"Check 3 — Shear-resisting section ($b_v$, $d_v$, ligs) | Result: $A_{{sv}} = {_fmt(Asv)}$ mm², $b_v = {_fmt(b_v)}$ mm, $d_v = {_fmt(d_v)}$ mm"

    render_expandable_step(
        page_key="shear",
        step_id="shear_check3",
        title="Check 3 — Shear-resisting section (b_v, d_v, ligs)",
        summary_md=check3_summary,
        status_kind=None,
        calc_md=check3_calc_md,
        diagram_render_fn=check3_diagram_fn,
        info_render_fn=check3_info_fn,
    )


__all__ = [
    "ShearTorsionDimensionsView",
    "render_shear_torsion_dimensions_checks",
]
