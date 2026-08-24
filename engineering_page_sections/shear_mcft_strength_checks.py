"""MCFT and strength presentation for Shear Checks 4-9.

All engineering values arrive through one revision-matched read-only check
snapshot. This module owns the teaching cards and family-specific diagrams only.
"""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Mapping

import plotly.graph_objects as go
import streamlit as st

from calculations.shear import nonprestressed_longitudinal_strain_display_values
from engineering_page_sections.shear_checks_context import ShearCheckFamilyInput
from engineering_page_sections.shear_visualisation import (
    MCFT_BEHAVIOUR_MARGIN,
    SHEAR_VISUAL_CONFIG,
    SHEAR_VISUAL_HEIGHT_PX,
    SHEAR_VISUAL_MAX_WIDTH_PX,
    _render_centered_shear_plotly,
    _render_plotly_in_mcft_column,
    _standardise_shear_visual_layout,
)
from shear_core import derive_eps_top_bot_for_step4_diagram
from shear_diagrams import (
    build_shear_check6_support_transfer_diagram,
    make_mcft_longitudinal_strain_profile_fig,
    resolve_check6_support_transfer_context,
)
from shear_visuals import BEHAVIOUR_VISUAL_WIDTH
from state_and_helpers import get_param, render_timing_mark
from step_ui import render_expandable_step
from widgets_helpers import (
    info_i_button,
    render_html_diagram,
    render_plotly_diagram,
)


@dataclass(frozen=True, slots=True)
class ShearMcftStrengthView:
    """Resolved, revision-matched display values for Shear Checks 4-9."""

    evidence: ShearCheckFamilyInput
    A_ct: float
    A_oh: float
    A_pt: float
    A_pt_fpo_N: float
    A_st: float
    Asv: float
    D: float
    Ec: float
    Ep: float
    Es: float
    LHS: float
    M_star: float
    N_star: float
    N_star_N: float
    P_v: float
    RHS: float
    T_star: float
    V_eq: float
    V_star: float
    Vu_max_kN: float
    Vu_total_kN: float
    Vuc_kN: float
    Vus_kN: float
    b_v: float
    d: float
    d_g: float
    d_v: float
    denom1: float
    denom2: float
    eps_x: float
    eps_x_1: float
    eps_x_2: float
    eps_x_raw: float
    eq_used: str
    f_po: float
    f_syv: float
    fc: float
    fsy: float
    k_dg: float
    k_v: float
    kv_case: str
    legs: float
    lig_d: float
    mcft: Mapping[str, Any]
    numerator_1: float
    numerator_2: float
    phi: float
    phi_Vu: float
    s: float
    shear_ok: bool
    shear_status: str
    sqrt_fc_limited: float
    sqrt_inner: float
    term_M: float
    theta_1_deg: float
    theta_v_deg: float
    uh: float
    use_general_kv: bool
    web_ok: bool
    web_status: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "mcft", MappingProxyType(dict(self.mcft)))


def _fmt(val, decimals=1):
    """Safe number formatter retained from the established Shear cards."""

    try:
        if val is None:
            return "—"
        return f"{float(val):.{decimals}f}"
    except Exception:
        return "—"


def _render_animated_plotly_figure(
    fig: go.Figure,
    *,
    height: int | None = None,
    centered: bool = False,
    animated: bool = True,
    chart_key: str = "shear_animated",
    max_width_px: int = SHEAR_VISUAL_MAX_WIDTH_PX,
    title_pad_t: int = 28,
    compact_top: bool = False,
) -> None:
    # Checks 5, 7 and 9 use this helper for a consistent visual frame, but
    # their figures are static.  Sending static figures through components.html
    # creates a separate iframe and loads a complete Plotly runtime for each
    # chart, including charts inside collapsed/hidden sections.  Keep the
    # existing HTML path for genuinely animated figures, while using the
    # native Plotly renderer for static figures so the visible chart remains
    # identical without the iframe cost.
    if not animated:
        render_plotly_diagram(
            fig,
            key=chart_key,
            title="Shear check diagram",
            config=SHEAR_VISUAL_CONFIG,
            center=centered,
        )
        return

    plot_h = int(height or fig.layout.height or SHEAR_VISUAL_HEIGHT_PX)
    if centered:
        fig = _standardise_shear_visual_layout(fig, title_pad_t=title_pad_t)
        # Match iframe inner max-width so Plotly export is not wider than the wrapper (avoids
        # overflow clipping that makes strut-and-tie / MCFT flow look shifted left).
        fig.update_layout(
            height=plot_h,
            width=int(max_width_px),
            autosize=False,
        )

    plot_html = fig.to_html(
        full_html=False,
        include_plotlyjs=True,
        config={"displayModeBar": False, "responsive": True},
        default_width="100%",
        default_height=f"{plot_h}px",
        post_script="""
const gd = document.getElementById('{plot_id}');
if (gd && !gd.__loadFlowAnimation) {
  gd.__loadFlowAnimation = true;
  const tick = () => {
    const lineIdx = [];
    const lineX = [];
    const lineY = [];
    (gd.data || []).forEach((trace, idx) => {
      const meta = trace.meta || {};
      if (!meta.animate_flow || meta.animate_flow_arrow) return;
      const xs = meta.flow_x || [];
      const ys = meta.flow_y || [];
      const windowSize = Math.max(2, Math.min(meta.window || 5, xs.length));
      if (xs.length < windowSize) return;
      const step = Math.max(1, meta.step || 1);
      const head = meta._head || 0;
      let segX = [];
      let segY = [];
      if (head + windowSize <= xs.length) {
        segX = xs.slice(head, head + windowSize);
        segY = ys.slice(head, head + windowSize);
        meta._flow_lead_index = Math.min(head + windowSize - 1, xs.length - 1);
        meta._head = head + step;
      } else {
        meta._head = 0;
        meta._flow_lead_index = Math.min(windowSize - 1, xs.length - 1);
      }
      lineIdx.push(idx);
      lineX.push(segX);
      lineY.push(segY);
    });
    if (lineIdx.length) {
      Plotly.restyle(gd, {x: lineX, y: lineY}, lineIdx);
    }
    const arIdx = [];
    const arX = [];
    const arY = [];
    const arCol = [];
    const arAng = [];
    (gd.data || []).forEach((trace, idx) => {
      const m = trace.meta || {};
      if (!m.animate_flow_arrow || m.flow_follow_line_index == null) return;
      const lineTr = gd.data[m.flow_follow_line_index];
      if (!lineTr) return;
      const lm = lineTr.meta || {};
      const xs = lm.flow_x || [];
      const ys = lm.flow_y || [];
      const windowSize = Math.max(2, Math.min(lm.window || 5, xs.length));
      if (xs.length < 2 || windowSize < 2) return;
      const lead =
        typeof lm._flow_lead_index === 'number'
          ? Math.min(Math.max(0, lm._flow_lead_index), xs.length - 1)
          : Math.min(windowSize - 1, xs.length - 1);
      let i0 = Math.max(0, lead - 1);
      let dx = xs[lead] - xs[i0];
      let dy = ys[lead] - ys[i0];
      if (Math.abs(dx) + Math.abs(dy) < 1e-9 && lead < xs.length - 1) {
        dx = xs[lead + 1] - xs[lead];
        dy = ys[lead + 1] - ys[lead];
      }
      let ang = Math.atan2(dy, dx) * 180 / Math.PI - 90;
      const er = lm.flow_end_red;
      const eg = lm.flow_end_green;
      const cr = lm.flow_color_red || '#c41e3a';
      const cg = lm.flow_color_green || '#2e7d32';
      const cb = lm.flow_color_blue || '#1565c0';
      let col = cg;
      if (typeof er === 'number' && er >= 0 && lead <= er) col = cr;
      else if (typeof eg === 'number' && eg >= 0 && lead <= eg) col = cg;
      else if (typeof eg === 'number' && eg >= 0) col = cb;
      if (typeof eg === 'number' && eg >= 0 && lead > eg) {
        ang += 180;
      }
      arIdx.push(idx);
      arX.push([xs[lead]]);
      arY.push([ys[lead]]);
      arCol.push(col);
      arAng.push(ang);
    });
    if (arIdx.length) {
      Plotly.restyle(gd, {x: arX, y: arY, 'marker.color': arCol, 'marker.angle': arAng}, arIdx);
    }
  };
  tick();
  window.setInterval(tick, 125);
}
""",
    )

    total_h = plot_h + 18
    if not centered:
        render_html_diagram(
            plot_html,
            key=chart_key,
            title="Animated shear diagram",
            height=total_h,
            fullscreen_height=max(total_h, 820),
            center=False,
        )
        return

    # Iframe-local flex only (parent-page :has(...) never matches nodes inside this document).
    outer_extra = "margin-top:0;padding-top:0;" if compact_top else ""
    outer = (
        "width:100%;margin:0;padding:0;box-sizing:border-box;"
        "display:flex;justify-content:center;align-items:flex-start;"
        f"{outer_extra}"
    )
    inner = (
        f"width:100%;max-width:{int(max_width_px)}px;margin:0 auto;"
        "box-sizing:border-box;display:flex;justify-content:center;"
    )
    wrapped = f"""<style>html,body{{margin:0;padding:0;width:100%;}}
.plotly-graph-div{{margin-left:auto!important;margin-right:auto!important;}}</style>
<div style="{outer}"><div style="{inner}">
{plot_html}
</div></div>"""
    # Full-width iframe (default) so Streamlit aligns like st.plotly_chart; inner div caps
    # and centers the 1120px plot — explicit width=max_width_px was shifting the block right.
    render_html_diagram(
        wrapped,
        key=chart_key,
        title="Animated shear diagram",
        height=total_h,
        fullscreen_height=max(total_h, 820),
        center=True,
    )


def render_shear_mcft_strength_checks(view: ShearMcftStrengthView) -> None:
    """Render Shear Checks 4-9 without recomputing authoritative results."""

    A_ct = view.A_ct
    A_oh = view.A_oh
    A_pt = view.A_pt
    A_pt_fpo_N = view.A_pt_fpo_N
    A_st = view.A_st
    Asv = view.Asv
    D = view.D
    Ec = view.Ec
    Ep = view.Ep
    Es = view.Es
    LHS = view.LHS
    M_star = view.M_star
    N_star = view.N_star
    N_star_N = view.N_star_N
    P_v = view.P_v
    RHS = view.RHS
    T_star = view.T_star
    V_eq = view.V_eq
    V_star = view.V_star
    Vu_max_kN = view.Vu_max_kN
    Vu_total_kN = view.Vu_total_kN
    Vuc_kN = view.Vuc_kN
    Vus_kN = view.Vus_kN
    b_v = view.b_v
    d = view.d
    d_g = view.d_g
    d_v = view.d_v
    denom1 = view.denom1
    denom2 = view.denom2
    eps_x = view.eps_x
    eps_x_1 = view.eps_x_1
    eps_x_2 = view.eps_x_2
    eps_x_raw = view.eps_x_raw
    eq_used = view.eq_used
    f_po = view.f_po
    f_syv = view.f_syv
    fc = view.fc
    fsy = view.fsy
    k_dg = view.k_dg
    k_v = view.k_v
    kv_case = view.kv_case
    legs = view.legs
    lig_d = view.lig_d
    mcft = view.mcft
    numerator_1 = view.numerator_1
    numerator_2 = view.numerator_2
    phi = view.phi
    phi_Vu = view.phi_Vu
    s = view.s
    shear_ok = view.shear_ok
    shear_status = view.shear_status
    sqrt_fc_limited = view.sqrt_fc_limited
    sqrt_inner = view.sqrt_inner
    term_M = view.term_M
    theta_1_deg = view.theta_1_deg
    theta_v_deg = view.theta_v_deg
    uh = view.uh
    use_general_kv = view.use_general_kv
    web_ok = view.web_ok
    web_status = view.web_status

    st.markdown(
        """
<style>
/* Check 1 uses the same compact calc spacing as the other checks. */
div[data-testid="stExpander"]:has(#inner_shear_check1) [data-testid="stExpanderDetails"] {
padding-top: 0 !important;
padding-bottom: 0 !important;
}
div[data-testid="stExpander"]:has(#inner_shear_check1) [data-testid="stExpanderDetails"] > div[data-testid="stVerticalBlock"] {
margin-top: 0 !important;
margin-bottom: 0 !important;
padding-top: 0 !important;
padding-bottom: 0 !important;
}
</style>
""",
        unsafe_allow_html=True,
    )
    # =====================================================
    # Check 4 — LONGITUDINAL STRAIN εx
    # =====================================================
    # Build calc markdown
    check4_without_prestress_display = bool(
        st.session_state.get("shear_check4_without_prestress_display", True)
    )
    check4_display_mode = (
        "Without prestress" if check4_without_prestress_display else "Full expression"
    )

    Veq_term_N = float(sqrt_inner)
    Veq_term_kN = Veq_term_N / 1e3

    _check4_longitudinal_force_terms_md = f"""
**Derivation of longitudinal force terms**

**Longitudinal force from moment:**

$$\\large |M^*|/d_v = \\frac{{|{M_star:.1f}| \\times 10^6}}{{{d_v:.1f}}} = {term_M:,.0f}\\ \\text{{N}}$$

**Longitudinal force from diagonal compression strut:**

The beam shear is carried through the web by a diagonal compression strut, which creates a longitudinal component $V_{{eq}}\\cdot\\cot\\theta_v$ shared equally between the top and bottom flanges. AS 3600 takes $0.5\\cot\\theta_v \\approx 1.0$, so the shear contribution used in this strain equation is $V_{{eq}}$ (here $V_{{eq}} = {Veq_term_kN:,.1f}$ kN, $= {Veq_term_N:,.0f}$ N).

**Longitudinal force from axial load:**

$$0.5N^* = 0.5 \\times {N_star:.1f} \\times 10^3 = {N_star_N:,.0f}\\ \\text{{N}}$$
"""

    _check4_prestress_section_md = f"""
---

**Prestress contribution:**

$$A_{{pt}} f_{{po}} = {A_pt:.1f} \\times {f_po:.1f} = {A_pt_fpo_N:,.0f}\\ \\text{{N}}$$
"""

    if check4_display_mode == "Without prestress":
        noprestress_display = nonprestressed_longitudinal_strain_display_values(
            term_M_N=term_M,
            V_eq_N=Veq_term_N,
            N_star_half_N=N_star_N,
            Es_mpa=Es,
            A_st_mm2=A_st,
        )
        eps_x_noprestress_num = noprestress_display["numerator"]
        eps_x_noprestress_den = noprestress_display["denominator"]
        eps_x_noprestress = noprestress_display["eps_x"]
        _np_note = (
            "Non-prestressed member: prestress-related terms omitted for clarity."
            if (A_pt <= 1e-9 or f_po <= 1e-9)
            else "Non-prestressed display form: prestress-related terms omitted for clarity."
        )
        check4_calc_md = f"""
*Purpose: Calculate the longitudinal strain $\\varepsilon_x$ at mid-depth for use in the MCFT shear model.*

**Inputs:**

**Inputs used directly in this displayed equation:**

- $d_v = {_fmt(d_v)}$ mm
- $M^* = {_fmt(M_star)}$ kNm
- $V_{{eq}} = {Veq_term_kN:,.1f}$ kN $(= {Veq_term_N:,.0f}$ N)
- $N^* = {_fmt(N_star)}$ kN
- $E_s = {_fmt(Es,0)}$ MPa
- $A_{{st}} = {_fmt(A_st,1)}$ mm²

---

**Formula (display mode: without prestress):**

$$\\large \\varepsilon_{{x}} = \\frac{{|M^*|/d_v + V_{{eq}} + 0.5N^*}}{{2E_s A_{{st}}}}$$

---

{_check4_longitudinal_force_terms_md}

<span style='font-size:0.9em;color:#666'>{_np_note}</span>

---

**Substitution:**

$$\\large \\varepsilon_{{x}} = \\frac{{{term_M:,.0f} + {Veq_term_N:,.0f} + {N_star_N:,.0f}}}{{2 \\times ({Es:,.0f} \\times {A_st:.1f})}}$$

$$\\large \\varepsilon_{{x}} = \\frac{{{eps_x_noprestress_num:,.0f}}}{{{eps_x_noprestress_den:,.0f}}} = {eps_x_noprestress:.5f}$$

---

**Result:**

- Governing equation: **{eq_used}**
- Raw strain (solver): $\\varepsilon_x = {eps_x_raw:.5f}$
- Shear contribution term in this derivation: $V_{{eq}} = {Veq_term_kN:,.1f}$ kN
- After applying AS 3600 limits $[-2.0 \\times 10^{{-4}},\\, 3.0 \\times 10^{{-3}}]$:

$$\\large \\varepsilon_x = {eps_x:.5f}$$

This value is **{"positive (tension at mid-depth)" if eps_x >= 0 else "negative (slight compression at mid-depth)"}**.
"""
    else:
        eq2_note = ""
        if eps_x_1 < 0:
            eq2_note = f"""
**Since the strain from Equation (1) is negative**
$\\varepsilon_{{x,1}} = {eps_x_1:.5f} < 0$, mid-depth is in slight compression.
AS 3600 allows εₓ to be taken as 0 or recalculated with **Equation (2)** including the concrete stiffness term:

$$\\large \\varepsilon_{{x,2}} = \\frac{{|M^*|/d_v + V_{{eq}} + 0.5N^* - A_{{pt}} f_{{po}}}}{{2(E_s A_{{st}} + E_p A_{{pt}} + E_c A_{{ct}})}}$$

Substituting the derived numerator and denominator:

$$\\large \\varepsilon_{{x,2}} = \\frac{{{numerator_2:,.0f}}}{{{denom2:,.0f}}} = {eps_x_2:.5f}$$
"""

        check4_calc_md = f"""
*Purpose: Calculate the longitudinal strain $\\varepsilon_x$ at mid-depth for use in the MCFT shear model.*

**Inputs:**

**Inputs used directly in this equation:**

- $d_v = {_fmt(d_v)}$ mm
- $M^* = {_fmt(M_star)}$ kNm
- $V_{{eq}} = {Veq_term_kN:,.1f}$ kN $(= {Veq_term_N:,.0f}$ N)
- $N^* = {_fmt(N_star)}$ kN
- $E_s = {_fmt(Es,0)}$ MPa
- $A_{{st}} = {_fmt(A_st,1)}$ mm²

**Prestress-related inputs:**

- $E_p = {_fmt(Ep,0)}$ MPa
- $A_{{pt}} = {_fmt(A_pt,1)}$ mm²
- $f_{{po}} = {_fmt(f_po)}$ MPa

**Derived material properties:**

- $E_c = 4700\\sqrt{{f'_c}} = 4700\\sqrt{{{fc:.1f}}} = {_fmt(Ec,0)}$ MPa
- $Eceff = \\dfrac{{E_c}}{{1+\\varphi_{{cc}}(t)}} = {_fmt(get_param('Eceff', Ec),0)}$ MPa
- $A_{{ct}} = {_fmt(A_ct,1)}$ mm² (concrete area term in Equation (2) path, when used)

---

**Formula (AS 3600 Cl. 8.2.4.2.2(1)) – mid-depth in tension (εₓ ≥ 0):**

$$\\large \\varepsilon_{{x,1}} = \\frac{{|M^*|/d_v + V_{{eq}} + 0.5N^* - A_{{pt}} f_{{po}}}}{{2(E_s A_{{st}} + E_p A_{{pt}})}}$$

---

{_check4_longitudinal_force_terms_md}
{_check4_prestress_section_md}

---

**Substitution:**

$$\\large \\varepsilon_{{x,1}} = \\frac{{{term_M:,.0f} + {Veq_term_N:,.0f} + {N_star_N:,.0f} - {A_pt_fpo_N:,.0f}}}{{2 \\times ({Es:,.0f} \\times {A_st:.1f} + {Ep:,.0f} \\times {A_pt:.1f})}}$$

$$\\large \\varepsilon_{{x,1}} = \\frac{{{numerator_1:,.0f}}}{{{denom1:,.0f}}} = {eps_x_1:.5f}$$

{eq2_note}

---

**Result:**

- Governing equation: **{eq_used}**
- Raw strain: $\\varepsilon_x = {eps_x_raw:.5f}$
- Shear contribution term in this equation: $V_{{eq}} = {Veq_term_kN:,.1f}$ kN
- After applying AS 3600 limits $[-2.0 \\times 10^{{-4}},\\, 3.0 \\times 10^{{-3}}]$:

$$\\large \\varepsilon_x = {eps_x:.5f}$$

This value is **{"positive (tension at mid-depth)" if eps_x >= 0 else "negative (slight compression at mid-depth)"}**.
"""
    # Diagram render function
    def check4_diagram_fn():
        # Single info control: same right-column placement as before; MCFT note only.
        col_diag_spacer, col_diag_info = st.columns([1, 0.08])
        with col_diag_spacer:
            pass
        with col_diag_info:
            with info_i_button(help_text="Longitudinal strain εx (MCFT)"):
                st.markdown(
                    r"""
### Longitudinal strain $\varepsilon_x$ (MCFT)

Check 4 evaluates the average longitudinal strain in the concrete at mid-height of the section,
$\varepsilon_x$, for use in the Modified Compression Field Theory shear model.
The section shear $V^*$ is assumed to be carried mainly by diagonal compression struts in the web,
inclined at angle $\theta_v$. Because the strut is diagonal, it has both a vertical component, which carries
the shear, and a horizontal component, which introduces a longitudinal compressive force in the web equal to
$V^*\cot\theta_v$.

Only longitudinal force components contribute to the longitudinal strain $\varepsilon_x$.
The vertical component of the diagonal strut is required for shear equilibrium, but it does not directly
contribute to strain in the beam axis direction, so it is not included separately in the strain calculation.
Instead, the strain equation includes the longitudinal effect of carrying the shear through the diagonal
compression field.

This longitudinal component is assumed to be shared equally between the compression and tension flanges,
so each flange resists about $0.5V^*\cot\theta_v$. For design, AS 3600 simplifies this by taking
$0.5\cot\theta_v \approx 1.0$, which is why the shear contribution appears directly as $V^*$ in the strain equation.

The strain $\varepsilon_x$ is taken at mid-height and may be viewed as the average longitudinal strain between
the compression and tension flanges. In practice, the compression-flange strain $\varepsilon_c$ is usually a small
negative value, so it is acceptable and conservative to approximate the mid-height strain as half of the tension-flange
strain, that is:

$$\varepsilon_x \approx \frac{\varepsilon_t}{2}$$

Accordingly, the code equation effectively calculates the tension-side longitudinal strain contribution from bending,
shear, and axial load, and then converts this into the average mid-height concrete strain $\varepsilon_x$ by dividing
by twice the longitudinal reinforcement stiffness.

The resulting value of $\varepsilon_x$ is then used to determine $k_v$ and the compression-field angle $\theta_v$
in the general shear method.
"""
                )

        # Check 4 MCFT εx (AS3600 sign: +tension, -compression)
        eps_x_mcft = eps_x  # Final Check 4 result (after AS3600 limits)

        # Pull ULS top/bot strains from bending page session state
        eps_top_uls = None
        eps_bot_uls = None

        for key in ["eps_c"]:
            val = st.session_state.get(key, None)
            if val is not None:
                try:
                    eps_top_uls = float(val)
                    break
                except Exception:
                    pass

        for key in ["eps_s"]:
            val = st.session_state.get(key, None)
            if val is not None:
                try:
                    eps_bot_uls = float(val)
                    break
                except Exception:
                    pass

        if eps_top_uls is None or eps_bot_uls is None:
            try:
                from bending_core import _stress_strain_state
                state_dict = _stress_strain_state("ULS")
                if eps_top_uls is None and "eps_c" in state_dict:
                    eps_top_uls = float(state_dict["eps_c"])
                if eps_bot_uls is None and "eps_s" in state_dict:
                    eps_bot_uls = float(state_dict["eps_s"])
            except Exception:
                pass

        if eps_top_uls is None or eps_bot_uls is None:
            eps_top_uls, eps_bot_uls = derive_eps_top_bot_for_step4_diagram(eps_x_mcft, delta=0.00035)

        eps_top_uls = float(eps_top_uls)
        eps_bot_uls = float(eps_bot_uls)

        force_geom_kwargs: dict = {}
        _ms = str(st.session_state.get("bending_detail_view", "positive") or "positive").strip().lower()
        try:
            from bending_core import _stress_strain_state

            _uls = _stress_strain_state("ULS", _ms)
            _Dfg = float(_uls.get("D") or 0.0)
            _cfg = float(_uls.get("c") or 0.0)
            _gg = float(_uls.get("gamma") or 0.0)
            _dg = float(_uls.get("d") or 0.0)
            if _Dfg > 1e-6 and _cfg > 1e-6 and _gg > 1e-6:
                force_geom_kwargs = dict(
                    force_section_D_mm=_Dfg,
                    force_section_c_mm=_cfg,
                    force_section_gamma=_gg,
                    force_tension_steel_y_from_top_mm=_dg,
                    force_moment_sign=_ms,
                )
        except Exception:
            force_geom_kwargs = {}

        st.markdown("#### Internal force resolution")
        fig_force = make_mcft_longitudinal_strain_profile_fig(
            eps_top_uls=eps_top_uls,
            eps_x_mcft=eps_x_mcft,
            eps_bot_uls=eps_bot_uls,
            title="Longitudinal strain profile",
            height=SHEAR_VISUAL_HEIGHT_PX,
            force_resolution=True,
            force_theta_deg=float(theta_v_deg),
            **force_geom_kwargs,
        )
        _standardise_shear_visual_layout(fig_force, title_pad_t=int(MCFT_BEHAVIOUR_MARGIN["t"]))
        fig_force.update_layout(
            height=int(SHEAR_VISUAL_HEIGHT_PX),
            width=int(BEHAVIOUR_VISUAL_WIDTH),
        )
        _render_plotly_in_mcft_column(
            fig_force,
            chart_key="shear_mcft_diagram_force",
            render_centered_plotly=_render_centered_shear_plotly,
        )

        st.markdown("#### Longitudinal strain profile")
        fig_strain = make_mcft_longitudinal_strain_profile_fig(
            eps_top_uls=eps_top_uls,
            eps_x_mcft=eps_x_mcft,
            eps_bot_uls=eps_bot_uls,
            title="Longitudinal strain profile",
            height=SHEAR_VISUAL_HEIGHT_PX,
            force_resolution=False,
        )
        _standardise_shear_visual_layout(fig_strain, title_pad_t=int(MCFT_BEHAVIOUR_MARGIN["t"]))
        fig_strain.update_layout(
            height=int(SHEAR_VISUAL_HEIGHT_PX),
            width=int(BEHAVIOUR_VISUAL_WIDTH),
        )
        _render_plotly_in_mcft_column(
            fig_strain,
            chart_key="shear_mcft_diagram_strain",
            render_centered_plotly=_render_centered_shear_plotly,
        )

    # Info render function — only the prestress toggle (single "i" popover lives in diagram column).
    def check4_info_fn():
        st.toggle(
            "Without prestress",
            value=bool(st.session_state.get("shear_check4_without_prestress_display", True)),
            key="shear_check4_without_prestress_display",
            help="Switch displayed Check 4 derivation between full expression and simplified non-prestressed form.",
        )

    # Build summary line
    check4_summary = f"Check 4 — Longitudinal strain $\\varepsilon_x$ | Result: $\\varepsilon_x = {eps_x:.5f}$"

    render_timing_mark("shear_page.runtime.checks.check4.start")
    render_expandable_step(
        page_key="shear",
        step_id="shear_check4",
        title="Check 4 — Longitudinal strain $\\varepsilon_x$",
        summary_md=check4_summary,
        status_kind=None,
        calc_md=check4_calc_md,
        diagram_render_fn=check4_diagram_fn,
        info_render_fn=check4_info_fn,
        anchor_id="mcft_state",
    )

    # =====================================================
    # Check 5 — k_v AND θ_v
    # =====================================================
    # For the summary text inside the calcbox
    Asv_over_s = float(mcft["Asv_over_s"])
    Asv_min_over_s = float(mcft["Asv_min_over_s"])
    k_dg_display = k_dg if use_general_kv else float("nan")
    canonical_theta_v_deg = float(view.evidence.results.get("theta_v_deg", theta_v_deg))
    canonical_k_v = float(view.evidence.results.get("k_v", k_v))
    stirrup_ratio_relation = "<" if Asv_over_s < Asv_min_over_s else "\\ge"
    stirrup_ratio_case = "low stirrup ratio" if Asv_over_s < Asv_min_over_s else "adequate stirrup ratio"

    if use_general_kv:
        theta_formula_block = r"$$\theta_v = 29^\circ + 7000\,\varepsilon_x$$"
        theta_sub_block = (
            f"$$\\theta_v = 29 + 7000 \\times {eps_x:.5f}"
            f" = {canonical_theta_v_deg:.1f}^\\circ$$"
        )
        if Asv_over_s < Asv_min_over_s:
            kv_governing_formula = r"$$k_v = \frac{0.4}{1 + 1500\varepsilon_x} \cdot \frac{1300}{1000 + k_{dg} d_v}$$"
            kv_governing_sub = (
                f"$$k_v = \\frac{{0.4}}{{1 + 1500 \\times {eps_x:.5f}}}"
                f" \\cdot \\frac{{1300}}{{1000 + {k_dg_display:.3f} \\times {d_v:.1f}}}"
                f" = {canonical_k_v:.3f}$$"
            )
        else:
            kv_governing_formula = r"$$k_v = \frac{0.4}{1 + 1500\varepsilon_x}$$"
            kv_governing_sub = (
                f"$$k_v = \\frac{{0.4}}{{1 + 1500 \\times {eps_x:.5f}}}"
                f" = {canonical_k_v:.3f}$$"
            )
        check5_live_cell = (
            f"- $\\varepsilon_x = {eps_x:.5f}$<br>"
            f"- $d_v = {d_v:.1f}$ mm<br>"
            f"- $A_{{sv}}/s = {Asv_over_s:.3f}\\ \\text{{mm}}^2/\\text{{mm}}$<br>"
            f"- $(A_{{sv}}/s)_{{min}} = {Asv_min_over_s:.3f}\\ \\text{{mm}}^2/\\text{{mm}}$<br>"
            f"- $k_{{dg}} = {k_dg_display:.3f}$"
        )
        check5_formulas_md = f"""
**Formula used for $k_v$ (general MCFT, governing branch):**

{kv_governing_formula}

{kv_governing_sub}

**Formula used for $\\theta_v$ (governing branch):**

{theta_formula_block}

**Numerical substitution:**

{theta_sub_block}
"""
    else:
        theta_formula_block = r"$$\theta_v = 36^\circ$$"
        kv_governing_formula = (
            r"$$k_v = \min\left(\frac{200}{1000 + 1.3 d_v}, 0.10\right)$$"
            if Asv_over_s < Asv_min_over_s
            else r"$$k_v = 0.15$$"
        )
        check5_live_cell = (
            f"- $d_v = {d_v:.1f}$ mm<br>"
            f"- $A_{{sv}}/s = {Asv_over_s:.3f}\\ \\text{{mm}}^2/\\text{{mm}}$<br>"
            f"- $(A_{{sv}}/s)_{{min}} = {Asv_min_over_s:.3f}\\ \\text{{mm}}^2/\\text{{mm}}$"
        )
        if Asv_over_s < Asv_min_over_s:
            _check5_simpl_interp_line = (
                f"For the simplified method, AS 3600 uses $k_v = {canonical_k_v:.3f}$ from the "
                f"simplified low-stirrup expression and $\\theta_v = 36^\\circ$ in the shear check."
            )
        else:
            _check5_simpl_interp_line = (
                "For the simplified method, AS 3600 takes $k_v = 0.15$ and "
                "$\\theta_v = 36^\\circ$ directly for use in the shear check."
            )
        check5_formulas_md = f"""
**Formula used for $k_v$ (simplified method):**

{kv_governing_formula}

**Formula used for $\\theta_v$ (simplified method):**

{theta_formula_block}

**Interpretation:**

{_check5_simpl_interp_line}
"""

    _check5_stirrup_compare = (
        f"$$\\frac{{A_{{sv}}}}{{s}} = {Asv_over_s:.3f}\\ \\text{{mm}}^2/\\text{{mm}} \\ {stirrup_ratio_relation} "
        f"\\ \\left(\\frac{{A_{{sv}}}}{{s}}\\right)_{{min}} = {Asv_min_over_s:.3f}\\ \\text{{mm}}^2/\\text{{mm}}$$"
    )
    check5_branch_md = f"""**Governing branch check:**

{_check5_stirrup_compare}

This gives **{stirrup_ratio_case}**, so the governing branch is: **{kv_case}**.
"""
    check5_purpose_md = (
        "*Purpose: Determine the shear parameters $k_v$ and $\\theta_v$ for use in $V_{uc}$ and web-crushing checks.*"
    )
    # Two-column row inside calcbox: markdown table (live column has no section heading).
    _check5_agg_line = (
        f"- Aggregate size factor: $k_{{dg}} \\approx {k_dg_display:.3f}$<br>"
        if use_general_kv
        else ""
    )
    _check5_strain_line = (
        f"- Strain: $\\varepsilon_x = {eps_x:.5f}$" if use_general_kv else ""
    )
    check5_inputs_cell = (
        f"- Concrete: $f'_c = {fc:.1f}$ MPa<br>"
        f"- Geometry: $b_v = {b_v:.1f}$ mm, $d_v = {d_v:.1f}$ mm, $d_g = {d_g:.1f}$ mm<br>"
        f"- Transverse steel: $A_{{sv}} = {Asv:.1f}$ mm², provided spacing $s_{{lig}} = {s:.1f}$ mm, "
        f"$f_{{sy,v}} = {f_syv:.1f}$ MPa<br>"
        f"{_check5_agg_line}"
        f"{_check5_strain_line}"
    )
    check5_io_table_md = (
        "| **Inputs** |  |\n"
        "| :-- | :-- |\n"
        f"| {check5_inputs_cell} | {check5_live_cell} |\n"
    )
    if use_general_kv:
        check5_result_md = f"""
**Governing result:**

- $k_v = {canonical_k_v:.3f}$
- Governing compression field angle: $\\theta_v = {canonical_theta_v_deg:.1f}°$

**Interpretation:**

This is the MCFT compression field angle used in the shear check.
The optional STM overlay uses a **separate** strut angle **θ<sub>STM</sub>** from the D-region node geometry, not **θ<sub>v</sub>**.

"""
    else:
        check5_result_md = ""

    _check5_result_tail = check5_result_md.strip()
    check5_calc_md = (
        f"{check5_purpose_md.strip()}\n\n---\n\n"
        f"{check5_io_table_md.strip()}\n\n---\n\n"
        f"{check5_branch_md.strip()}\n\n---\n\n"
        f"{check5_formulas_md.strip()}"
        + (f"\n\n---\n\n{_check5_result_tail}" if _check5_result_tail else "")
    )

    # Diagram render function — local support-region transfer sketch (canonical layout + reo)
    def check5_diagram_fn():
        from section_layout import compute_section_layout
        from state_and_helpers import resolve_design_actions

        layout_chk5 = compute_section_layout()
        actions_chk5 = resolve_design_actions(st.session_state)
        moment_sign_chk5 = (
            "negative"
            if float(actions_chk5.get("Mu_signed", 0.0) or 0.0) < 0.0
            else "positive"
        )
        chk5_ctx = resolve_check6_support_transfer_context(
            st.session_state, d_mm=float(d)
        )
        # Stirrup lines: use live_state legs/s after _shear_calc_context fix (lig_legs=0 must stay 0).
        legs_chk5 = int(legs) if legs is not None else 0
        fig = build_shear_check6_support_transfer_diagram(
            layout=layout_chk5,
            D_mm=float(D),
            d_mm=float(d),
            moment_sign=moment_sign_chk5,
            support_draw_kind=str(chk5_ctx.get("support_draw_kind") or "pinned"),
            critical_support_side=str(
                chk5_ctx.get("critical_support_side") or "left"
            ),
            s_lig_mm=float(s),
            lig_legs=legs_chk5,
            lig_d_mm=float(lig_d),
            asv_mm2=float(Asv),
            d_v_mm=float(d_v),
            height=320,
            fc_mpa=float(fc),
            fsy_mpa=float(fsy),
            theta_v_deg=float(canonical_theta_v_deg),
            show_mcft_mechanism_labels=True,
        )
        _render_animated_plotly_figure(
            fig,
            height=int(fig.layout.height or 320),
            animated=False,
            chart_key="shear_check5_animated",
        )

    # Info render function (popover) — trigger aligned further right above calc/diagram row
    def check5_info_fn():
        _, col_info = st.columns([0.93, 0.07])
        with col_info:
            _info_pad, col_btn = st.columns([0.35, 0.65])
            with col_btn:
                with info_i_button(
                    help_text="Check 5 — MCFT parameters and shear-transfer diagram"
                ):
                    st.markdown(
                        r"""
This check determines the MCFT parameters used in the later shear and web-crushing checks.

First, the transverse steel ratio $A_{sv}/s$ is compared with the minimum required value $(A_{sv}/s)_{\min}$ to identify the governing MCFT branch. The AS 3600 equations for that branch are then used to calculate:

- $k_v$ — the effectiveness of cracked concrete in carrying shear
- $\theta_v$ — the average diagonal crack angle in the web

A lower $k_v$ means the cracked concrete is less effective in resisting shear. The angle $\theta_v$ controls how shear is resolved into diagonal compression in the concrete and tension in the reinforcement.

### Simplified method

Use for typical non-prestressed beams when there is no applied axial tension,
$f'_c < 65$ MPa, aggregate size $\geq 10$ mm, and longitudinal bar yield strength $\leq 500$ MPa.
It is the quick standard check using fixed code shear parameters, and it is often less conservative than the general method.

### Diagram interpretation

The diagram shows the main shear-transfer mechanisms acting along the diagonal crack at angle $\theta_v$.

- $V_{cc}$ — shear carried by compression in the concrete compression zone
- $V_{cr}$ — residual shear carried across the cracked concrete
- $V_{ca}$ — aggregate interlock along the crack faces
- $V_d$ — dowel action from the longitudinal reinforcement

The blue $A_{st}$ line is the longitudinal tension steel, which helps hold the section together after cracking and supports shear transfer across the crack.
                        """
                    )

    # Build summary line
    check5_summary = f"Check 5 — MCFT parameters ($k_v$ and $\\theta_v$) | Result: $k_v = {k_v:.3f}$, $\\theta_v = {theta_v_deg:.1f}°$"

    render_timing_mark("shear_page.runtime.checks.check5.start")
    render_expandable_step(
        page_key="shear",
        step_id="shear_check5",
        title="Check 5 — MCFT parameters (k_v and θ_v)",
        summary_md=check5_summary,
        status_kind=None,
        calc_md=check5_calc_md,
        diagram_render_fn=check5_diagram_fn,
        info_render_fn=check5_info_fn,
    )

    # =====================================================
    # Check 6 — CONCRETE SHEAR CONTRIBUTION V_uc ONLY
    # =====================================================
    check6_calc_md = f"""
*Purpose: Calculate the concrete shear strength $V_{{uc}}$ at the critical section.*

**Inputs:**

- $k_v = {k_v:.3f}$

- $b_v = {b_v:.1f}$ mm, $d_v = {d_v:.1f}$ mm

- $f'_c = {fc:.1f}$ MPa (limited $\\sqrt{{f'_c}} = {sqrt_fc_limited:.3f}$ MPa)

---

**Formula (AS 3600 Cl. 8.2.4.1):**

$$V_{{uc}} = k_v b_v d_v \\sqrt{{f'_c}}$$

**Substitution:**

$$V_{{uc}} = {k_v:.3f} \\times {b_v:.1f} \\times {d_v:.1f} \\times {sqrt_fc_limited:.3f} = {Vuc_kN:,.1f}\\,\\text{{kN}}$$

---

**Result:**

- **Concrete shear strength:** $V_{{uc}} = {Vuc_kN:,.1f}$ kN

*(Steel contribution $V_s$ is added in the next step.)*

"""

    # Info render function (popover) — trigger on the right, aligned with Check 5
    def check6_info_fn():
        _, col_info = st.columns([0.93, 0.07])
        with col_info:
            _info_pad, col_btn = st.columns([0.35, 0.65])
            with col_btn:
                with info_i_button(
                    help_text="Check 6 — Concrete shear strength $V_{uc}$"
                ):
                    st.markdown(
                        r"""
### Check 6 — Concrete shear strength $V_{uc}$

This check calculates the shear strength carried by the concrete alone at the critical section.

In simplified MCFT, concrete shear strength depends on the effectiveness factor $k_v$, which reflects how cracking reduces the ability of concrete to transfer shear. As tensile strain increases, cracks widen, aggregate interlock reduces, and the concrete contribution decreases.

The simplified crack-width relationship is:

$$w = 0.2 + 1000\,\varepsilon_x$$

where 0.2 mm represents an initial crack width and $1000\,\varepsilon_x$ represents additional widening with strain. This relationship is used to derive $k_v$.

For members with minimum shear reinforcement provided, the simplified method uses fixed assumptions for crack spacing and aggregate effects, giving the standard simplified value of $k_v$. For members with less than minimum shear reinforcement, crack spacing and aggregate interlock have a greater influence, so the concrete shear transfer is reduced accordingly.

The concrete shear strength is then calculated from $k_v$, the beam width $b_v$, the effective shear depth $d_v$, and the limited concrete strength term $\sqrt{f'_c}$.

This step gives the concrete contribution only. The steel contribution $V_s$ is calculated separately and added in the next step.
                        """
                    )

    # Build summary line
    check6_summary = f"Check 6 — Concrete shear strength $V_{{uc}}$ | Result: $V_{{uc}} = {Vuc_kN:,.1f}$ kN"

    render_timing_mark("shear_page.runtime.checks.check6.start")
    render_expandable_step(
        page_key="shear",
        step_id="shear_check6",
        title="Check 6 — Concrete shear strength V_uc",
        summary_md=check6_summary,
        status_kind=None,
        calc_md=check6_calc_md,
        info_render_fn=check6_info_fn,
        anchor_id="vc",
    )

    # =====================================================
    # Check 7 — STEEL SHEAR CONTRIBUTION V_s
    # =====================================================
    # Step 7 details
    step7_details = f"""
*Purpose: Calculate the shear strength provided by ligatures $V_s$.*



**Inputs:**



- $A_{{sv}} = {Asv:.1f}$ mm², provided spacing $s_{{lig}} = {s:.1f}$ mm

- $f_{{sy,v}} = {f_syv:.1f}$ MPa

- $d_v = {d_v:.1f}$ mm, $\\theta_v = {theta_v_deg:.1f}°$



---



**Formula (AS 3600 Cl. 8.2.5.2(a)):**



$$V_{{us}} = \\left(\\frac{{A_{{sv}} f_{{sy,v}} d_v}}{{s}}\\right)\\cot \\theta_v$$



**Substitution:**



$$V_{{us}} = \\left(\\frac{{{Asv:.1f} \\times {f_syv:.1f} \\times {d_v:.1f}}}{{{s:.1f}}}\\right) \\cot {theta_v_deg:.1f}° = {Vus_kN:,.1f}\\,\\text{{kN}}$$



---



**Result:**



- **Steel shear strength:** $V_s = V_{{us}} = {Vus_kN:,.1f}$ kN

*(Concrete shear $V_{{uc}}$ was found in Check 6.)*

"""

    check7_calc_md = step7_details

    # Diagram render function
    def check7_diagram_fn():
        from section_layout import compute_section_layout
        from state_and_helpers import resolve_design_actions

        layout_chk7 = compute_section_layout()
        actions_chk7 = resolve_design_actions(st.session_state)
        moment_sign_chk7 = (
            "negative"
            if float(actions_chk7.get("Mu_signed", 0.0) or 0.0) < 0.0
            else "positive"
        )
        chk7_ctx = resolve_check6_support_transfer_context(
            st.session_state, d_mm=float(d)
        )
        legs_chk7 = int(legs) if legs is not None else 0
        fig = build_shear_check6_support_transfer_diagram(
            layout=layout_chk7,
            D_mm=float(D),
            d_mm=float(d),
            moment_sign=moment_sign_chk7,
            support_draw_kind=str(chk7_ctx.get("support_draw_kind") or "pinned"),
            critical_support_side=str(
                chk7_ctx.get("critical_support_side") or "left"
            ),
            s_lig_mm=float(s),
            lig_legs=legs_chk7,
            lig_d_mm=float(lig_d),
            asv_mm2=float(Asv),
            d_v_mm=float(d_v),
            height=320,
            fc_mpa=float(fc),
            fsy_mpa=float(fsy),
            theta_v_deg=float(canonical_theta_v_deg),
            show_mean_crack_guideline=True,
            show_mean_green_flow_pulse=False,
            show_mean_green_flow_arrows=False,
            show_green_strut_flow=False,
            show_compression_resultant=False,
            show_shear_teaching_overlay=True,
            show_region_labels=False,
        )
        _render_animated_plotly_figure(
            fig,
            height=int(fig.layout.height or 320),
            animated=False,
            chart_key="shear_check7_animated",
        )

    # Info render function (popover) — trigger on the right, aligned with Checks 5–6
    def check7_info_fn():
        _, col_info = st.columns([0.93, 0.07])
        with col_info:
            _info_pad, col_btn = st.columns([0.35, 0.65])
            with col_btn:
                with info_i_button(
                    help_text="Check 7 — Steel shear strength $V_s$"
                ):
                    st.markdown(
                        r"""
### Check 7 — Steel shear strength $V_s$

This check calculates the shear strength provided by the transverse reinforcement.

After diagonal cracking forms, the stirrups cross the crack and develop tension, helping resist shear. The steel contribution depends on:

- transverse steel area $A_{sv}$,
- stirrup spacing $s$,
- stirrup yield strength $f_{sy,v}$,
- effective shear depth $d_v$, and
- crack angle $\theta_v$.

A steeper crack crosses fewer stirrups, while a flatter crack crosses more, which is why $\theta_v$ affects the steel shear contribution through the $\cot\theta_v$ term.

This step gives the steel contribution only. It is then added to the concrete contribution $V_{uc}$ to obtain the sectional shear capacity.
                        """
                    )

    # Build summary line
    check7_summary = f"Check 7 — Steel shear strength $V_s$ | Result: $V_s = V_{{us}} = {Vus_kN:,.1f}$ kN"

    render_timing_mark("shear_page.runtime.checks.check7.start")
    render_expandable_step(
        page_key="shear",
        step_id="shear_check7",
        title="Check 7 — Steel shear strength V_s",
        summary_md=check7_summary,
        status_kind=None,
        calc_md=check7_calc_md,
        diagram_render_fn=check7_diagram_fn,
        info_render_fn=check7_info_fn,
        anchor_id="vs",
    )

    # =====================================================
    # Check 8 — COMBINED SHEAR STRENGTH AND SECTIONAL CHECK
    # =====================================================
    check8_calc_md = f"""
*Purpose: Combine concrete and steel contributions and check $\\phi V_u$ against $V_{{eq}}^*$.*



**Inputs:**



- $V_{{uc}} = {Vuc_kN:,.1f}$ kN (from Check 6)

- $V_s = {Vus_kN:,.1f}$ kN (from Check 7)

- $P_v = {P_v:.1f}$ kN

- Strength reduction: $\\phi = {phi:.2f}$

- Demand: $V_{{eq}}^* = {V_eq:.1f}$ kN



---



**Total sectional shear capacity (AS 3600 Cl. 8.2.3.1):**



$$V_u = V_{{uc}} + V_s + P_v$$



$$V_u = {Vuc_kN:,.1f} + {Vus_kN:,.1f} + {P_v:.1f} = {Vu_total_kN:,.1f}\\,\\text{{kN}}$$



Design strength:



$$\\phi V_u = {phi:.2f} \\times {Vu_total_kN:,.1f} = {phi_Vu:,.1f}\\,\\text{{kN}}$$



---



**Sectional shear check:**



- Requirement: $\\phi V_u \\ge V_{{eq}}^*$

- Here: {phi_Vu:,.1f} kN vs {V_eq:.1f} kN → **{"OK" if shear_ok else "NOT OK"}**

"""

    # Info render function (popover) — right-aligned, matching Checks 5–7
    def check8_info_fn():
        _, col_info = st.columns([0.93, 0.07])
        with col_info:
            _info_pad, col_btn = st.columns([0.35, 0.65])
            with col_btn:
                with info_i_button(
                    help_text="Check 8 — Sectional shear capacity"
                ):
                    st.markdown(
                        r"""
### Check 8 — Sectional shear capacity

This check combines the concrete shear strength $V_{uc}$ from Check 6 and the steel shear strength $V_s$ from Check 7 to give the total sectional shear strength.

The section shear capacity is based on both mechanisms working together after cracking:

- the concrete continues to carry part of the shear through the cracked web, and
- the stirrups carry the remaining shear as they cross the diagonal crack.

This gives the nominal sectional shear strength before any separate governing limit checks are applied. It shows the total shear strength available from the section at the critical location.
                        """
                    )

    # Build summary line
    pass_fail = "PASS" if shear_ok else "FAIL"
    check8_summary = f"Check 8 — Sectional shear capacity check | Result: $\\phi V_u = {phi_Vu:,.1f}$ kN vs $V_{{eq}}^* = {V_eq:.1f}$ kN → **{pass_fail}**"

    render_timing_mark("shear_page.runtime.checks.check8.start")
    render_expandable_step(
        page_key="shear",
        step_id="shear_check8",
        title="Check 8 — Sectional shear capacity",
        summary_md=check8_summary,
        status_kind=shear_status,
        calc_md=check8_calc_md,
        info_render_fn=check8_info_fn,
    )

    # =====================================================
    # Check 9 — WEB CRUSHING CHECK
    # =====================================================
    if not web_ok:
        st.error("Web-crushing limit exceeded – revise section/ligs.")

    _check9_step3_torsion_note = ""
    if abs(float(T_star or 0.0)) < 1e-6:
        _check9_step3_torsion_note = (
            "\n\n*Since $T^* = 0$, the torsion term is zero and the demand reduces to "
            "$V^*/(b_v d_v)$.*\n"
        )

    check9_calc_md = f"""
*Purpose: Check that combined shear + torsion does not exceed the web-crushing limit (Cl. 8.2.6).*

**Inputs:**

- $f'_c = {fc:.1f}$ MPa, $b_v = {b_v:.1f}$ mm, $d_v = {d_v:.1f}$ mm
- $\\theta_v = {theta_v_deg:.1f}^\\circ$, $\\theta_1 = {theta_1_deg:.1f}^\\circ$
- $P_v = {P_v:.1f}$ kN
- Actions: $V^* = {V_star:.1f}$ kN, $T^* = {T_star:.1f}$ kNm
- Torsion geometry: $u_h = {uh:.1f}$ mm, $A_{{oh}} = {A_oh:.1f}$ mm²

---

**Web-crushing force limit, $V_{{u,\\max}}$ (AS 3600 Cl. 8.2.6):**

$$\\large V_{{u,\\max}} = 0.55 f'_c b_v d_v \\frac{{\\cot\\theta_v + \\cot\\theta_1}}{{1 + \\cot^2\\theta_v}} + P_v$$

**Substitution:**

$$\\large V_{{u,\\max}} = 0.55 \\times {fc:.1f} \\times {b_v:.1f} \\times {d_v:.1f} \\times \\frac{{\\cot({theta_v_deg:.1f}^\\circ) + \\cot({theta_1_deg:.1f}^\\circ)}}{{1 + \\cot^2({theta_v_deg:.1f}^\\circ)}} + {P_v:.1f} = {Vu_max_kN:,.1f}\\,\\text{{kN}}$$

---

**Normalized design limit:**

For the final web-crushing check, the limit is compared in **normalized form** by dividing by $b_v d_v$.

*The **normalized** quantities $v_{{\\mathrm{{cap}}}}$ and $v_{{\\mathrm{{dem}}}}$ below are a shear-type stress measure (effectively **MPa** when forces are in **N** and $b_v d_v$ in **mm²**). This is where the check moves from the nominal force $V_{{u,\\max}}$ (kN) to a **per-unit-area** limit comparable to the normalized demand.*

$$v_{{\\mathrm{{cap}}}} = \\frac{{\\phi V_{{u,\\max}}}}{{b_v d_v}}$$

**Substitution:**

$$v_{{\\mathrm{{cap}}}} = \\frac{{{phi:.2f} \\times {Vu_max_kN:,.1f}}}{{{b_v:.1f} \\times {d_v:.1f}}} = {RHS:,.1f}$$

---

**Normalized combined shear + torsion demand:**

$$v_{{\\mathrm{{dem}}}} = \\sqrt{{\\left(\\frac{{V^*}}{{b_v d_v}}\\right)^2 + \\left(\\frac{{T^* u_h}}{{1.7 A_{{oh}}^2}}\\right)^2}}$$

**Substitution:**

$$v_{{\\mathrm{{dem}}}} = \\sqrt{{\\left(\\frac{{{V_star:.1f}}}{{{b_v:.1f} \\times {d_v:.1f}}}\\right)^2 + \\left(\\frac{{{T_star:.1f} \\times {uh:.1f}}}{{1.7 \\times {A_oh:.1f}^2}}\\right)^2}} = {LHS:,.1f}$$
{_check9_step3_torsion_note}
---

**Web-crushing check:**

- Requirement: $v_{{\\mathrm{{dem}}}} \\le v_{{\\mathrm{{cap}}}}$
- Here: {LHS:,.1f} $\\le$ {RHS:,.1f} → **{"OK" if web_ok else "NG"}**
"""

    # Diagram render function — same beam/support family as Checks 5 & 7; D-region STM strut for web crushing
    def check9_diagram_fn():
        from section_layout import compute_section_layout
        from state_and_helpers import resolve_design_actions

        layout_chk9 = compute_section_layout()
        actions_chk9 = resolve_design_actions(st.session_state)
        moment_sign_chk9 = (
            "negative"
            if float(actions_chk9.get("Mu_signed", 0.0) or 0.0) < 0.0
            else "positive"
        )
        chk9_ctx = resolve_check6_support_transfer_context(
            st.session_state, d_mm=float(d)
        )
        legs_chk9 = int(legs) if legs is not None else 0
        fig = build_shear_check6_support_transfer_diagram(
            layout=layout_chk9,
            D_mm=float(D),
            d_mm=float(d),
            moment_sign=moment_sign_chk9,
            support_draw_kind=str(chk9_ctx.get("support_draw_kind") or "pinned"),
            critical_support_side=str(
                chk9_ctx.get("critical_support_side") or "left"
            ),
            s_lig_mm=float(s),
            lig_legs=legs_chk9,
            lig_d_mm=float(lig_d),
            asv_mm2=float(Asv),
            d_v_mm=float(d_v),
            height=320,
            fc_mpa=float(fc),
            fsy_mpa=float(fsy),
            theta_v_deg=float(canonical_theta_v_deg),
            web_crushing_stm=True,
        )
        _render_animated_plotly_figure(
            fig,
            height=int(fig.layout.height or 320),
            animated=False,
            chart_key="shear_check9_animated",
        )

    # Info render function (popover) — right-aligned, matching other shear checks
    def check9_info_fn():
        _, col_info = st.columns([0.93, 0.07])
        with col_info:
            _info_pad, col_btn = st.columns([0.35, 0.65])
            with col_btn:
                with info_i_button(
                    help_text="Check 9 — Web-crushing strength"
                ):
                    st.markdown(
                        r"""
### Check 9 — Web-crushing strength

Checks that the combined shear and torsion demand does not crush the diagonal concrete compression strut in the web.

Use this for combined shear and torsion checks. If $T^* = 0$, it reduces to a shear-only web-crushing check.

The check first calculates the web-crushing limit $V_{u,\max}$, then compares:

- **Normalized applied demand** — the applied shear + torsion effect, written per unit web area
- **Normalized design limit** — the web-crushing capacity, also written per unit web area

Use a strut-and-tie model for deep beams ($\text{span}/\text{depth} < 2.5$), disturbed regions with loads or reactions within about $d_v$ of a support, significant point loads near supports, and members with complex geometry or load paths.

This check provides an upper bound on shear resistance to prevent brittle compression failures.

Regardless of reinforcement, design shear capacity cannot exceed this limit.
                        """
                    )

    # Build summary line
    web_pass_fail = "PASS" if web_ok else "FAIL"
    check9_summary = (
        f"Check 9 — Web-crushing strength check | Result: "
        f"$v_{{\\mathrm{{dem}}}} = {LHS:,.1f}$ vs $v_{{\\mathrm{{cap}}}} = {RHS:,.1f}$ → **{web_pass_fail}**"
    )

    render_timing_mark("shear_page.runtime.checks.check9.start")
    render_expandable_step(
        page_key="shear",
        step_id="shear_check9",
        title="Check 9 — Web-crushing strength",
        summary_md=check9_summary,
        status_kind=web_status,
        calc_md=check9_calc_md,
        diagram_render_fn=check9_diagram_fn,
        info_render_fn=check9_info_fn,
        anchor_id="vu_max",
    )

# =====================================================


__all__ = [
    "ShearMcftStrengthView",
    "render_shear_mcft_strength_checks",
]

