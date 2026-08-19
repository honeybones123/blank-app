"""Styled teaching panel for bending material behaviour.

This module owns presentation only. The caller supplies the existing dynamic
material-curve builder and Plotly renderer so no second engineering model is
introduced.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any
import html

import streamlit as st


_PANEL_CSS = r"""
<style>
.sb-material-lesson {
  --sb-navy: #14233d;
  --sb-muted: #59677b;
  --sb-border: #dbe3ec;
  --sb-blue: #1769d2;
  --sb-blue-soft: #f4f8ff;
  --sb-red: #c63838;
  --sb-red-soft: #fff7f7;
  --sb-green: #268154;
  --sb-green-soft: #f3fbf6;
  --sb-amber: #9b6700;
  --sb-amber-soft: #fffaf0;
  color: var(--sb-navy);
}
.sb-lesson-hero {
  display: grid;
  grid-template-columns: minmax(0, 3fr) minmax(260px, 1fr);
  gap: 16px;
  align-items: stretch;
  margin: 0 0 18px 0;
}
.sb-lesson-title {
  margin: 0 0 6px 0;
  font-size: 1.42rem;
  line-height: 1.2;
  font-weight: 760;
  letter-spacing: -0.02em;
  color: var(--sb-navy);
}
.sb-lesson-lead {
  margin: 0;
  max-width: 930px;
  font-size: 0.98rem;
  line-height: 1.58;
  color: #34425a;
}
.sb-stage-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 11px;
  margin-top: 15px;
}
.sb-stage-card {
  position: relative;
  min-height: 112px;
  padding: 13px 14px 12px 14px;
  border: 1px solid var(--sb-border);
  border-radius: 12px;
  background: #ffffff;
  box-shadow: 0 1px 2px rgba(20, 35, 61, 0.04);
}
.sb-stage-card:not(:last-child)::after {
  content: "→";
  position: absolute;
  right: -10px;
  top: 43%;
  z-index: 3;
  width: 18px;
  height: 18px;
  border-radius: 999px;
  display: grid;
  place-items: center;
  background: #ffffff;
  color: #35689f;
  font-weight: 700;
}
.sb-stage-number {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 23px;
  height: 23px;
  margin-right: 7px;
  border-radius: 999px;
  background: #eef4fb;
  color: #285b95;
  font-size: 0.78rem;
  font-weight: 750;
}
.sb-stage-card:nth-child(2) .sb-stage-number { background: #f3edff; color: #7848c6; }
.sb-stage-card:nth-child(3) .sb-stage-number { background: #fff0f0; color: #b83838; }
.sb-stage-card:nth-child(4) .sb-stage-number { background: #eaf8f0; color: #23764d; }
.sb-stage-title {
  display: inline;
  font-size: 0.96rem;
  font-weight: 730;
  color: var(--sb-navy);
}
.sb-stage-copy {
  margin: 9px 0 0 0;
  font-size: 0.86rem;
  line-height: 1.45;
  color: #4d5a70;
}
.sb-state-panel {
  height: 100%;
  box-sizing: border-box;
  padding: 15px 16px;
  border: 1px solid #e5d7ad;
  border-radius: 12px;
  background: var(--sb-amber-soft);
}
.sb-state-panel.sls { border-color: #cbdcef; background: #f5f9ff; }
.sb-state-panel.uncracked { border-color: #d8dfe8; background: #f8fafc; }
.sb-state-kicker {
  margin: 0 0 8px 0;
  font-size: 0.78rem;
  font-weight: 760;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  color: var(--sb-amber);
}
.sb-state-panel.sls .sb-state-kicker { color: #2e6ea9; }
.sb-state-panel.uncracked .sb-state-kicker { color: #58687a; }
.sb-state-title {
  margin: 0 0 8px 0;
  font-size: 1.02rem;
  font-weight: 750;
  color: var(--sb-navy);
}
.sb-state-copy {
  margin: 0;
  font-size: 0.87rem;
  line-height: 1.48;
  color: #4b586b;
}
.sb-state-equation {
  display: inline-block;
  margin-top: 12px;
  padding: 7px 11px;
  border: 1px solid rgba(155, 103, 0, 0.32);
  border-radius: 8px;
  background: rgba(255,255,255,0.78);
  font-family: Georgia, 'Times New Roman', serif;
  font-size: 1.1rem;
  color: #17305c;
}
.sb-subheading {
  display: flex;
  gap: 9px;
  align-items: center;
  margin: 8px 0 10px 0;
  font-size: 1.08rem;
  line-height: 1.25;
  font-weight: 760;
  color: var(--sb-navy);
}
.sb-subheading-number {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex: 0 0 auto;
  width: 26px;
  height: 26px;
  border-radius: 999px;
  background: #1769d2;
  color: #ffffff;
  font-size: 0.84rem;
  font-weight: 760;
}
.sb-equation-strip {
  display: flex;
  align-items: center;
  justify-content: center;
  flex-wrap: wrap;
  gap: 18px;
  margin: 11px 0 15px 0;
  padding: 12px 14px;
  border: 1px solid #cfddf0;
  border-radius: 11px;
  background: #f7faff;
}
.sb-equation-main {
  padding: 6px 12px;
  border: 1px solid #9fbce3;
  border-radius: 8px;
  background: #ffffff;
  font-family: Georgia, 'Times New Roman', serif;
  font-size: 1.24rem;
  color: #17305c;
}
.sb-equation-defs {
  font-size: 0.88rem;
  color: #536176;
}
.sb-mini-note {
  margin-top: 9px;
  padding: 10px 12px;
  border-left: 3px solid #5a8dcb;
  border-radius: 7px;
  background: #f4f8fd;
  color: #41516a;
  font-size: 0.87rem;
  line-height: 1.45;
}
.sb-equilibrium-strip {
  display: grid;
  grid-template-columns: minmax(0, 1.4fr) auto minmax(0, 1fr);
  gap: 18px;
  align-items: center;
  margin-top: 14px;
  padding: 16px 18px;
  border: 1px solid #bedfca;
  border-radius: 12px;
  background: var(--sb-green-soft);
}
.sb-equilibrium-title {
  margin: 0 0 4px 0;
  font-size: 1rem;
  font-weight: 760;
  color: var(--sb-green);
}
.sb-equilibrium-copy {
  margin: 0;
  font-size: 0.88rem;
  line-height: 1.45;
  color: #405448;
}
.sb-equilibrium-equation {
  padding: 8px 15px;
  border: 1px solid #9dceb0;
  border-radius: 9px;
  background: #ffffff;
  font-family: Georgia, 'Times New Roman', serif;
  font-size: 1.35rem;
  color: #17653f;
  white-space: nowrap;
}
.sb-process-line {
  margin: 0;
  font-size: 0.88rem;
  line-height: 1.48;
  color: #43574a;
}

div[data-testid="stVerticalBlockBorderWrapper"]:has(.sb-material-major-one),
div[data-testid="stVerticalBlockBorderWrapper"]:has(.sb-material-major-two) {
  border: 1px solid #dbe3ec !important;
  border-radius: 14px !important;
  background: #ffffff !important;
  box-shadow: 0 2px 8px rgba(20, 35, 61, 0.035) !important;
  padding: 0.95rem 1.05rem 1.05rem !important;
  margin: 0.55rem 0 !important;
}
div[data-testid="stVerticalBlockBorderWrapper"]:has(.sb-material-card-blue) {
  border: 1px solid #c9dcf5 !important;
  border-radius: 12px !important;
  background: #f8fbff !important;
  padding: 0.75rem 0.85rem !important;
}
div[data-testid="stVerticalBlockBorderWrapper"]:has(.sb-material-card-red) {
  border: 1px solid #f1cccc !important;
  border-radius: 12px !important;
  background: #fffafa !important;
  padding: 0.75rem 0.85rem !important;
}
div[data-testid="stVerticalBlockBorderWrapper"]:has(.sb-material-formula-card) {
  border: 1px solid #d6e1ef !important;
  border-radius: 11px !important;
  background: #fbfdff !important;
  padding: 0.65rem 0.8rem !important;
}
div[data-testid="stVerticalBlockBorderWrapper"]:has(.sb-material-major-one) .katex-display,
div[data-testid="stVerticalBlockBorderWrapper"]:has(.sb-material-major-two) .katex-display,
div[data-testid="stVerticalBlockBorderWrapper"]:has(.sb-material-card-blue) .katex-display,
div[data-testid="stVerticalBlockBorderWrapper"]:has(.sb-material-card-red) .katex-display,
div[data-testid="stVerticalBlockBorderWrapper"]:has(.sb-material-formula-card) .katex-display {
  margin: 0.35rem 0 !important;
}
@media (max-width: 1050px) {
  .sb-lesson-hero { grid-template-columns: 1fr; }
  .sb-stage-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .sb-stage-card::after { display: none !important; }
}
@media (max-width: 650px) {
  .sb-stage-grid { grid-template-columns: 1fr; }
  .sb-equilibrium-strip { grid-template-columns: 1fr; }
  .sb-equilibrium-equation { width: fit-content; }
}
</style>
"""


def _state_content(selected_state: str) -> dict[str, str]:
    state = str(selected_state or "ULS").strip()
    low = state.lower()
    if low.startswith("uls"):
        return {
            "label": state,
            "class": "uls",
            "body": (
                "Ultimate flexural response. The extreme concrete compression strain is "
                "taken as 0.003, steel stress is obtained from strain and limited to the "
                "yield strength, and concrete compression is represented by the AS 3600 "
                "equivalent rectangular stress block."
            ),
            "equation": "ε<sub>cu</sub> = 0.003",
            "concrete": (
                "Concrete is approximately elastic at low stress but becomes increasingly "
                "nonlinear as compression increases. At ULS, AS 3600 uses an equivalent "
                "rectangular stress block for section-strength calculations."
            ),
            "steel": (
                "Reinforcement behaves approximately linear-elastically up to yield. At ULS, "
                "the section calculation limits the final reinforcement stress to the "
                "applicable yield strength."
            ),
        }
    if "sls" in low:
        return {
            "label": state,
            "class": "sls",
            "body": (
                "Cracked service response. Tensile concrete is neglected in the cracked "
                "flexural section analysis, while the compression zone and reinforcement "
                "stresses follow the compatible service strain profile."
            ),
            "equation": "Service-level strain profile",
            "concrete": (
                "Concrete compression stress follows the service strain in the cracked "
                "compression zone; tensile concrete is not included in the cracked flexural model."
            ),
            "steel": (
                "Reinforcement stress is obtained from the compatible service strain using "
                "the elastic steel relationship."
            ),
        }
    return {
        "label": state,
        "class": "uncracked",
        "body": (
            "Uncracked elastic response. The concrete section remains effective in tension "
            "and compression, and compatible strains are converted to material stresses "
            "using the applicable elastic properties."
        ),
        "equation": "Full section effective",
        "concrete": (
            "Concrete remains active in both tension and compression and is represented by "
            "the elastic material relationship for this state."
        ),
        "steel": (
            "Reinforcement stress is obtained directly from the compatible elastic strain."
        ),
    }


def _subheading(number: int, title: str) -> None:
    st.markdown(
        f'<div class="sb-material-lesson sb-subheading">'
        f'<span class="sb-subheading-number">{number}</span>'
        f'<span>{html.escape(title)}</span></div>',
        unsafe_allow_html=True,
    )


def render_bending_material_teaching_panel(
    *,
    selected_state: str,
    plot_material_curves: Callable[[], Any],
    render_plotly_diagram: Callable[..., Any],
) -> None:
    """Render the styled, state-aware material teaching lesson."""

    st.markdown(_PANEL_CSS, unsafe_allow_html=True)
    state = _state_content(selected_state)

    with st.container(border=True):
        st.markdown('<span class="sb-material-major-one"></span>', unsafe_allow_html=True)
        st.markdown(
            f"""
<div class="sb-material-lesson sb-lesson-hero">
  <div>
    <div class="sb-lesson-title">From strain to stress to internal force</div>
    <p class="sb-lesson-lead">
      This section explains how the strain profile through a reinforced-concrete
      section is converted into concrete and reinforcement stresses, and how those
      stresses become the internal forces used in section analysis.
    </p>
    <div class="sb-stage-grid">
      <div class="sb-stage-card">
        <span class="sb-stage-number">1</span><span class="sb-stage-title">Section</span>
        <p class="sb-stage-copy">Define the section geometry and reinforcement locations.</p>
      </div>
      <div class="sb-stage-card">
        <span class="sb-stage-number">2</span><span class="sb-stage-title">Strain</span>
        <p class="sb-stage-copy">Determine strain at each location from the linear strain profile.</p>
      </div>
      <div class="sb-stage-card">
        <span class="sb-stage-number">3</span><span class="sb-stage-title">Stress</span>
        <p class="sb-stage-copy">Convert strain into stress using the material stress–strain relationship.</p>
      </div>
      <div class="sb-stage-card">
        <span class="sb-stage-number">4</span><span class="sb-stage-title">Force</span>
        <p class="sb-stage-copy">Apply stress over the relevant area to determine internal force.</p>
      </div>
    </div>
  </div>
  <div class="sb-state-panel {state['class']}">
    <div class="sb-state-kicker">Selected state</div>
    <div class="sb-state-title">{html.escape(state['label'])}</div>
    <p class="sb-state-copy">{state['body']}</p>
    <span class="sb-state-equation">{state['equation']}</span>
  </div>
</div>
""",
            unsafe_allow_html=True,
        )

        _subheading(1, "Where does the strain come from?")
        strain_text, strain_formula = st.columns([1.35, 1.0], gap="large")
        with strain_text:
            st.markdown(
                "For normal beam bending, **plane sections are assumed to remain plane**. "
                "The longitudinal strain therefore varies linearly through the section depth. "
                "The Section / Strain / Stress diagram immediately above this panel shows the "
                "compatible profile for the selected state."
            )
            st.markdown(
                "Strain is zero at the neutral axis. Once the neutral-axis depth is known, "
                "the strain at any reinforcement depth follows directly from the geometry "
                "of the linear profile."
            )
        with strain_formula:
            with st.container(border=True):
                st.markdown('<span class="sb-material-formula-card"></span>', unsafe_allow_html=True)
                st.markdown("**Reinforcement layer $i$**")
                st.latex(r"\varepsilon_{s,i}=-\varepsilon_{cu}\frac{y_i-d_n}{d_n}")
                st.caption("Strain comes from section geometry and the assumed neutral-axis depth.")

        _subheading(2, "How does strain become stress?")
        st.markdown(
            "Knowing strain does not yet tell us the internal action carried by the material. "
            "We first convert strain into **stress**. Within the elastic range, that link is "
            "Hooke's law."
        )
        st.markdown(
            """
<div class="sb-material-lesson sb-equation-strip">
  <span class="sb-equation-main">σ = Eε</span>
  <span class="sb-equation-defs"><b>σ</b> = stress &nbsp;&nbsp; <b>E</b> = elastic modulus &nbsp;&nbsp; <b>ε</b> = strain</span>
</div>
""",
            unsafe_allow_html=True,
        )
        st.markdown(
            "The elastic modulus $E$ represents material stiffness. For the same strain, a "
            "material with a larger $E$ develops a larger stress. This is why a compatible "
            "strain profile can produce very different concrete and reinforcement stresses."
        )

        fig_mat = plot_material_curves()
        try:
            render_plotly_diagram(
                fig_mat,
                key="bending_material_stress_strain_curves",
                title="Material stress–strain behaviour",
                config={"displayModeBar": False},
            )
        except Exception:
            st.warning("Material curves failed to render. Refresh the page and try again.")

        behaviour_cols = st.columns(2, gap="large")
        with behaviour_cols[0]:
            with st.container(border=True):
                st.markdown('<span class="sb-material-card-blue"></span>', unsafe_allow_html=True)
                st.markdown("**Concrete behaviour**")
                st.markdown(state["concrete"])
                st.latex(r"f_c\approx E_c\varepsilon_c")
                if state["class"] == "uls":
                    st.markdown(
                        '<div class="sb-material-lesson sb-mini-note"><b>Material curve ≠ ULS rectangular stress block.</b><br>'
                        'The curve shows material behaviour; the rectangular block is the code representation used for section strength.</div>',
                        unsafe_allow_html=True,
                    )
        with behaviour_cols[1]:
            with st.container(border=True):
                st.markdown('<span class="sb-material-card-red"></span>', unsafe_allow_html=True)
                st.markdown("**Reinforcement behaviour**")
                st.markdown(state["steel"])
                st.latex(r"f_s=E_s\varepsilon_s")
                if state["class"] == "uls":
                    st.latex(r"|f_s|\leq f_{sy}")

    with st.container(border=True):
        st.markdown('<span class="sb-material-major-two"></span>', unsafe_allow_html=True)
        st.markdown(
            '<div class="sb-material-lesson sb-lesson-title">From stress to internal force and equilibrium</div>',
            unsafe_allow_html=True,
        )
        st.markdown(
            "Stress is force per unit area. Once the stress and the area over which it acts "
            "are known, the corresponding internal force can be calculated."
        )
        st.markdown(
            '<div class="sb-material-lesson sb-equation-strip"><span class="sb-equation-main">F = σA</span>'
            '<span class="sb-equation-defs">General principle: stress acting over area produces force.</span></div>',
            unsafe_allow_html=True,
        )

        force_cols = st.columns(2, gap="large")
        with force_cols[0]:
            with st.container(border=True):
                st.markdown('<span class="sb-material-card-blue"></span>', unsafe_allow_html=True)
                st.markdown("**Concrete compression**")
                if state["class"] == "uls":
                    st.markdown(
                        "The equivalent concrete stress $\alpha_2f'_c$ acts over the rectangular "
                        "compression-block area $ba$, where $a=\gamma d_n$."
                    )
                    st.latex(r"a=\gamma d_n")
                    st.latex(r"C_c=\alpha_2f'_cba")
                else:
                    st.markdown(
                        "The concrete stress distribution acting over the active concrete area "
                        "produces the concrete resultant."
                    )
                    st.latex(r"C_c=\int_{A_c}\sigma_c\,dA")
        with force_cols[1]:
            with st.container(border=True):
                st.markdown('<span class="sb-material-card-red"></span>', unsafe_allow_html=True)
                st.markdown("**Reinforcement layer $i$**")
                st.markdown(
                    "The stress in each reinforcement layer acts over that layer's steel area."
                )
                st.latex(r"F_{s,i}=A_{s,i}f_{s,i}")

        st.markdown(
            """
<div class="sb-material-lesson sb-equilibrium-strip">
  <div>
    <div class="sb-equilibrium-title">Why do we need these forces?</div>
    <p class="sb-equilibrium-copy">The internal concrete and reinforcement forces must balance to satisfy section equilibrium.</p>
  </div>
  <div class="sb-equilibrium-equation">ΣC = ΣT</div>
  <p class="sb-process-line">If the forces do not balance, adjust the section state and repeat:<br><b>Neutral axis → Strain → Stress → Force → Equilibrium</b></p>
</div>
""",
            unsafe_allow_html=True,
        )


__all__ = ["render_bending_material_teaching_panel"]
