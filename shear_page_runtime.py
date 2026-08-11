import math
import os
import json
import time
import re
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import plotly.graph_objects as go
import streamlit as st
import streamlit.components.v1 as components

from state_and_helpers import (
    get_param,
    get_sync_callbacks,
    resolve_design_actions,
    update_results,
    get_widget_key_for_shared,
    load_proxies_from_active_set,
    save_proxies_to_active_set,
    recalc_derived_values,
    is_design_governing,
    render_timing_mark,
)
from shear_diagrams import (
    build_shear_check6_support_transfer_diagram,
    resolve_check6_support_transfer_context,
    build_torsion_plotly_figure,
    plot_shear_torsion_section_2d,
    plot_shear_step3_section_params_plotly,
    make_mcft_longitudinal_strain_profile_fig,
)
from shear_visuals import (
    BEHAVIOUR_VISUAL_HEIGHT,
    BEHAVIOUR_VISUAL_WIDTH,
    SIDE_VIEW_VISUAL_HEIGHT,
    SIDE_VIEW_VISUAL_WIDTH,
    build_shear_behaviour_figure,
    build_shear_cross_section_figure,
    build_shear_side_view_figure,
)
from ui.diagrams.principal_stress_cue_diagram import (
    PRINCIPAL_STRESS_AXES_CUE_SCALE,
    build_principal_stress_axes_cue,
)
from shear_core import build_shear_zone_layout_strip_figure, derive_eps_top_bot_for_step4_diagram
# Shared helpers (same contract as Inputs/Bending)
from widgets_helpers import apply_global_widget_css, apply_result_page_css, apply_calcbox_css, number_row, select_row, calcbox, clickable_calcbox, render_step, apply_step_summary_expander_css, info_i_button, page_divider, render_page_explainer_expander, render_section_title, render_result_page_title, render_specialized_widget_rail, _register_rendered_key, _wrap_user_edit, render_plotly_diagram, render_image_diagram, render_html_diagram
from step_ui import render_expandable_step
from engineering_check_ui import SHEAR_ROW_UID_TO_TAB
from ui_seamless_steps import render_clickable_summary_table, bind_summary_clicks
from ui.summary_rows import (
    build_shear_clickable_summary_rows,
    build_shear_legacy_summary_rows,
    filter_shear_summary_rows,
)
from shear_checks_helpers import (
    build_shear_calc_bundle_from_state,
    build_shear_check_rows_from_state,
)
from calculations.shear import (
    cotangent as cot,
    duct_area_mm2,
    effective_shear_depth_mm,
    longitudinal_strain_fallback_values,
    maximum_shear_spacing_mm,
    mcft_kv_theta_values,
    nonprestressed_longitudinal_strain_display_values,
    shear_capacity_utilisation_values,
    shear_check_display_scalars,
    shear_reinforcement_spacing_check_values,
    stirrup_area_mm2,
    torsion_section_geometry_values,
    web_crushing_fallback_values,
)


from engineering_page_sections import shear_visualisation as _shear_visualisation_section
_support_pair_from_resolved_support_type = _shear_visualisation_section._support_pair_from_resolved_support_type
_coalesce_num = _shear_visualisation_section._coalesce_num
_standardise_shear_visual_layout = _shear_visualisation_section._standardise_shear_visual_layout
_render_plotly_in_mcft_column = _shear_visualisation_section._render_plotly_in_mcft_column
_render_mcft_behaviour_chart = _shear_visualisation_section._render_mcft_behaviour_chart
_shear_visualisation_section.bind_runtime(globals())

# Keep Shear's existing step renderer available, but suppress the expensive
# detail/diagram branch while an inactive Shear check tab is being assembled.
# The surrounding summary and calculations still run; only non-visible tab
# content is skipped until that tab is selected.
_render_expandable_step = render_expandable_step


def render_expandable_step(*args, **kwargs):
    if (
        kwargs.get("page_key") == "shear"
        and bool(st.session_state.get("_shear_skip_inactive_tab", False))
    ):
        return None
    return _render_expandable_step(*args, **kwargs)



# ------------------------------------------------------------
#  Helper functions for diagrams
# ------------------------------------------------------------

SHEAR_VISUAL_HEIGHT_PX = BEHAVIOUR_VISUAL_HEIGHT
SHEAR_SIDE_VIEW_HEIGHT_PX = SIDE_VIEW_VISUAL_HEIGHT
SHEAR_SIDE_VIEW_MAX_WIDTH_PX = SIDE_VIEW_VISUAL_WIDTH
SHEAR_VISUAL_MAX_WIDTH_PX = 760
SHEAR_BEHAVIOUR_MAX_WIDTH_PX = BEHAVIOUR_VISUAL_WIDTH
# MCFT / principal-stress behaviour diagrams: one canonical pixel frame on every toggle and on both pages.
MCFT_BEHAVIOUR_MARGIN = dict(l=10, r=10, t=8, b=10)
SHEAR_VISUAL_CONFIG = {
    "displayModeBar": False,
    "responsive": True,
}

SHEAR_CHECK_TAB_LABELS = (
    "Torsion + dimensions",
    "MCFT and strength checks",
    "Shear reinforcement checks",
)
SHEAR_CHECK_TAB_KEY = "shear_check_tab"

# Shear link legs: 0 means no links; active closed links start at 2 legs.
REO_SHEAR_LEGS_OPTIONS = [0] + list(range(2, 13))








def _render_centered_shear_plotly(
    fig,
    *,
    chart_key: str,
    max_width_px: int = SHEAR_VISUAL_MAX_WIDTH_PX,
    height_px: int = SHEAR_VISUAL_HEIGHT_PX,
    title_pad_t: int = 28,
    compact_top: bool = False,
    config: dict | None = None,
):
    fig = _standardise_shear_visual_layout(fig, title_pad_t=title_pad_t)
    fig.update_layout(height=int(height_px))
    wrapper_id = f"shear-plot-wrap-{chart_key}"
    compact_top_css = ""
    if compact_top:
        compact_top_css = "margin-top: 0 !important; padding-top: 0 !important;"

    st.markdown(
        f"""
        <style>
        div[data-testid="stVerticalBlock"] div[data-testid="stElementContainer"]:has(#{wrapper_id}) {{
            width: 100%;
        }}
        #{wrapper_id} {{
            width: 100%;
            display: flex;
            justify-content: center;
            align-items: center;
            {compact_top_css}
        }}
        #{wrapper_id} > div {{
            width: min(100%, {max_width_px}px);
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(f'<div id="{wrapper_id}"><div>', unsafe_allow_html=True)
    render_plotly_diagram(
        fig,
        key=chart_key,
        title="Shear diagram",
        center=True,
        config=config or SHEAR_VISUAL_CONFIG,
    )
    st.markdown("</div></div>", unsafe_allow_html=True)


def _safe_float(x, fallback):
    try:
        v = float(x)
        if v != v:  # NaN
            return float(fallback)
        return v
    except Exception:
        return float(fallback)


def _render_shear_cross_section():
    fig = build_shear_cross_section_figure()
    section_fig = _standardise_shear_visual_layout(fig)
    _render_centered_shear_plotly(
        section_fig,
        chart_key="shear_section_diagram",
        max_width_px=SHEAR_VISUAL_MAX_WIDTH_PX,
    )


def _render_shear_side_view():
    try:
        _phi_vu = float(get_param("phi_Vu_cap") or 0.0)
        _v_eq = float(get_param("V_eq_kN") or 0.0)
    except (TypeError, ValueError):
        _phi_vu, _v_eq = 0.0, 0.0
    # Sectional shear check (for caption + diagram title only). Zoned stirrups on the graph
    # follow Check 10 whenever layout data exists — not only when this fails.
    shear_fails = _phi_vu > 0.0 and _v_eq > _phi_vu + 1e-9
    st.caption(
        "Side view: when Check 10 layout exists, stirrups follow required zone spacings from the envelope; "
        "otherwise at provided spacing (input s_lig). φV_u uses effective spacing from results (provided or "
        "required when “Apply auto spacing” is on)."
        if shear_fails
        else "Side view: required zone spacings from Check 10 when available; otherwise provided spacing (s_lig). "
        "φV_u check uses effective spacing (provided unless auto spacing applies envelope spacing)."
    )
    fig = build_shear_side_view_figure(shear_fails=shear_fails)
    _render_centered_shear_plotly(
        fig,
        chart_key="shear_side_view_diagram",
        max_width_px=SHEAR_SIDE_VIEW_MAX_WIDTH_PX,
        height_px=SHEAR_SIDE_VIEW_HEIGHT_PX,
        title_pad_t=10,
    )


def _resolve_shear_visual_supports(length_m: float) -> tuple[list[float], list[str]]:
    from deflection_support import get_deflection_diagram_support_condition, _governing_span_support_pair

    support_positions: list[float] = []
    support_types: list[str] = []
    beam_mode = str(get_param("design_beam_system_mode", "Single span") or "Single span")
    sup_res = get_deflection_diagram_support_condition(st.session_state)
    support_pair = _governing_span_support_pair(st.session_state, sup_res)

    if (
        beam_mode == "Multi-span"
        and isinstance(support_pair, tuple)
        and len(support_pair) == 2
    ):
        try:
            span_count = max(1, int(float(st.session_state.get("sfd_span_count", 0.0) or 0.0)))
        except Exception:
            span_count = 1
        controlling_idx = int(sup_res.get("controlling_span_idx", 0) or 0)
        controlling_idx = max(0, min(controlling_idx, span_count - 1))
        try:
            span_len_m = float(st.session_state.get(f"sfd_span_len_{controlling_idx + 1}", 0.0) or 0.0)
        except Exception:
            span_len_m = 0.0
        if abs(float(span_len_m) - float(length_m)) <= 1e-6:
            support_positions = [0.0, float(length_m)]
            support_types = [str(support_pair[0]), str(support_pair[1])]

    if not support_positions or not support_types:
        sup = str(sup_res.get("support_type") or get_param("defl_support_type", "Simply supported") or "Simply supported")
        support_pair_fallback = _support_pair_from_resolved_support_type(sup)
        if "cantilever" in sup.lower():
            support_positions = [0.0]
            support_types = ["Fixed"]
        elif isinstance(support_pair_fallback, tuple) and len(support_pair_fallback) == 2:
            support_positions = [0.0, float(length_m)]
            support_types = [str(support_pair_fallback[0]), str(support_pair_fallback[1])]
        else:
            support_positions = [0.0, float(length_m)]
            support_types = ["Pinned", "Roller"]

    return support_positions, support_types


def _render_shear_force_diagram():
    from beam_diagram_runtime import plot_sfd_bmd_plotly

    mode = str(get_param("actions_mode", "manual") or "manual").strip().lower()
    L_m = max(float(get_param("L", 3000.0) or 3000.0) / 1000.0, 0.1)
    shear_x_raw = np.asarray(get_param("shear_x", []) or [], dtype=float)
    shear_V_signed_raw = np.asarray(get_param("shear_V_signed", []) or [], dtype=float)
    shear_V_raw = np.asarray(get_param("shear_V", []) or [], dtype=float)
    support_type = str(get_param("support_type", get_param("defl_support_type", "simply_supported")) or "simply_supported").strip().lower()

    if mode == "design" and shear_x_raw.size > 1:
        if shear_V_signed_raw.size == shear_x_raw.size:
            x_plot = shear_x_raw
            V_plot = shear_V_signed_raw
        elif shear_V_raw.size == shear_x_raw.size:
            x_plot = shear_x_raw
            V_plot = shear_V_raw
        else:
            x_plot = np.linspace(0.0, L_m, 100)
            V_plot = np.zeros_like(x_plot, dtype=float)
    else:
        x_plot = np.linspace(0.0, L_m, 100)
        V_star = float(get_param("uls_Vstar", 0.0) or 0.0)
        if "cantilever" in support_type:
            V_plot = V_star * (1.0 - x_plot / max(L_m, 1e-9))
        else:
            V_plot = V_star * (1.0 - 2.0 * x_plot / max(L_m, 1e-9))

    support_positions, support_types = _resolve_shear_visual_supports(L_m)
    fig_sfd, _ = plot_sfd_bmd_plotly(
        x=x_plot,
        V=V_plot,
        M=np.zeros_like(x_plot, dtype=float),
        L=L_m,
        support_positions=support_positions,
        support_types=support_types,
    )
    fig_sfd.update_layout(height=320)
    st.caption("Shear V(x)")
    render_plotly_diagram(
        fig_sfd,
        key="shear_visual_sfd_diagram",
        title="Shear force diagram",
        config=SHEAR_VISUAL_CONFIG,
    )


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


def _render_shear_behaviour_plot(visual_mode: str | None = None, theta_v_deg: float | None = None):
    show_load_flow = bool(st.session_state.get("shear_show_load_flow", False))
    show_cracks = bool(st.session_state.get("shear_show_cracks", True))
    show_stress_block = bool(st.session_state.get("shear_show_stress_block", False))
    show_stm_overlay = bool(st.session_state.get("shear_show_stm_overlay", False))
    show_stm_flow = bool(st.session_state.get("shear_show_stm_flow", False))
    effective_mode = visual_mode or "Principal stress field"
    fig = build_shear_behaviour_figure(
        visual_mode="Principal stress field",
        theta_v_deg=theta_v_deg,
        show_load_flow=show_load_flow,
        show_cracks=show_cracks,
        show_stress_block=show_stress_block,
        show_stm_overlay=show_stm_overlay,
        show_stm_flow=show_stm_flow,
    )
    _render_mcft_behaviour_chart(
        fig,
        chart_key="shear_behaviour_visual_mode",
        animated=bool(effective_mode == "Principal stress field" and (show_load_flow or show_stm_flow)),
    )
    caption = (
        "Illustrative only — schematic principal-stress-style field, not a finite-element stress solution."
        if effective_mode == "Principal stress field"
        else "Illustrative only — idealised strut-and-tie model for conceptual interpretation, not a code design check."
    )
    st.caption(caption)
    if effective_mode == "Principal stress field":
        st.caption("Concrete cannot resist tension -> cracks form perpendicular to σ2.")


def _render_shear_behaviour_diagrams(theta_v_deg: float) -> None:
    with info_i_button(
        help_text=(
            "Strut-and-tie model, strut-and-tie flow along STM members, MCFT trajectory load flow, "
            "cracks, and stress block for this diagram."
        )
    ):
        st.caption("Display options")
        st.toggle("Show strut-and-tie model", value=False, key="shear_show_stm_overlay")
        st.toggle("Show strut-and-tie flow", value=False, key="shear_show_stm_flow")
        st.toggle("Show load flow", value=False, key="shear_show_load_flow")
        st.toggle("Show cracks", value=True, key="shear_show_cracks")
        st.toggle("Show stress block", value=False, key="shear_show_stress_block")

    show_load_flow = bool(st.session_state.get("shear_show_load_flow", False))
    show_cracks = bool(st.session_state.get("shear_show_cracks", True))
    show_stress_block = bool(st.session_state.get("shear_show_stress_block", False))
    show_stm_overlay = bool(st.session_state.get("shear_show_stm_overlay", False))
    show_stm_flow = bool(st.session_state.get("shear_show_stm_flow", False))
    # Anchor for tab2 CSS: remove excess gap between display-options popover and main stress-field chart.
    st.markdown(
        '<div id="mcft-before-stress-plot" style="height:0;line-height:0;font-size:0;margin:0;padding:0;" aria-hidden="true"></div>',
        unsafe_allow_html=True,
    )
    fig = build_shear_behaviour_figure(
        visual_mode="Principal stress field",
        theta_v_deg=theta_v_deg,
        show_load_flow=show_load_flow,
        show_cracks=show_cracks,
        show_stress_block=show_stress_block,
        show_stm_overlay=show_stm_overlay,
        show_stm_flow=show_stm_flow,
    )
    _render_mcft_behaviour_chart(
        fig,
        chart_key="shear_behaviour_mcft_single",
        animated=bool(show_load_flow or show_stm_flow),
    )
    st.caption(
        "Illustrative only — schematic principal-stress-style field with optional strut-and-tie overlay, "
        "not a finite-element stress solution."
    )


# Cumulative scale for principal-stress (A)(B)(C) cue vs original base geometry (two +25% steps).
_PRINCIPAL_STRESS_AXES_CUE_SCALE = PRINCIPAL_STRESS_AXES_CUE_SCALE


def _build_principal_stress_axes_cue() -> go.Figure:
    theta_v_deg = float(
        st.session_state.get(
            "crack_theta_deg",
            get_param("crack_theta_deg", st.session_state.get("theta_v_deg", get_param("theta_v_deg", 45.0))),
        )
        or 45.0
    )
    return build_principal_stress_axes_cue(theta_v_deg)

def _render_principal_stress_directions_explainer() -> None:
    with st.expander("The Stress Field: Explaining the Modified Compression Field Theory and Strut-and-Tie Model"):
        st.markdown(
            r"""
The Modified Compression Field Theory (MCFT) and the strut-and-tie model (STM) are idealisations of the same underlying stress field. In this implementation, both use the same angle $\theta_v$ from the MCFT relationships (see Check 5), ensuring consistency between calculations and the visualised field.
            """
        )
        cue_col, note_col = st.columns([1, 1.5], gap="medium")
        with cue_col:
            _render_centered_shear_plotly(
                _build_principal_stress_axes_cue(),
                chart_key="shear_principal_stress_axes_cue",
                max_width_px=int(540 * _PRINCIPAL_STRESS_AXES_CUE_SCALE),
                height_px=int(190 * _PRINCIPAL_STRESS_AXES_CUE_SCALE),
            )
        with note_col:
            st.markdown(
                r"""
The stress state resolves into principal directions where no shear acts on those planes (see [Mohr's circle](https://www.youtube.com/watch?v=_DH3546mSCM&msockid=3bf4b3e5318911f1b3cda493793b9b56)). Red trajectories show the principal compression $\sigma_1$, and blue trajectories show the principal tension $\sigma_2$.

The stress block diagrams represent a small element of the beam. The shear shown in Diagram (A) is a local stress component within the element and is not the same as the applied shear force $V^*$; the global shear $V^*$ is carried through the member by the combined action of the inclined compression field and associated tensile forces. In Diagram (A), shear is shown by forces acting parallel to the faces of the element, indicating the stresses are not aligned with the principal directions. The element is then rotated (Diagram (B)) to an orientation where the shear components are eliminated, corresponding to the transformation described by Mohr’s circle. In this orientation (Diagram (C)), only the principal stresses remain, shown as $\sigma_1$ (compression) and $\sigma_2$ (tension).

Within about one effective depth $d_v$ of supports, behaviour is a disturbed region (D-region), where stress flow is non-linear and idealised using a strut-and-tie model. The compression strut aligns with $\theta_v$.

Beyond this, in the flexural–shear region, stresses follow the rotating principal field. Cracks form approximately perpendicular to $\sigma_2$, with tensile forces carried by shear reinforcement and longitudinal reinforcement (dowel action).
                """
            )
        # Anchor for tab2 CSS: tighten vertical gap below this expander toward the main MCFT diagram.
        st.markdown(
            '<div id="mcft-theory-expander-tail" style="height:0;line-height:0;font-size:0;margin:0;padding:0;" aria-hidden="true"></div>',
            unsafe_allow_html=True,
        )


def _render_shear_visualisation():
    visual_mode = st.session_state.get("shear_visual_mode", "Side view")
    if visual_mode == "Side view":
        _render_shear_side_view()
    elif visual_mode == "Shear behaviour":
        _render_shear_behaviour_plot()
    else:
        _render_shear_cross_section()


def _render_shear_visualisation_block(theta_v_deg: float | None = None):
    with st.container():
        st.markdown(
            """
<style>
/* Shear page only: anchor is inside this container vertical block */
div[data-testid="stVerticalBlock"]:has(#shear-visuals-block) {
    margin-top: 0.25rem !important;
    padding-top: 0 !important;
}
div[data-testid="stVerticalBlock"]:has(#shear-visuals-block) .section-title {
    margin-bottom: 0.35rem !important;
}
div[data-testid="stVerticalBlock"]:has(#shear-visuals-block) h3,
div[data-testid="stVerticalBlock"]:has(#shear-visuals-block) h4 {
    margin-bottom: 0.35rem !important;
}
div[data-testid="stVerticalBlock"]:has(#shear-visuals-block) [data-testid="stPlotlyChart"] {
    margin-bottom: 0.2rem !important;
}
div[data-testid="stVerticalBlock"]:has(#shear-visuals-block) [data-testid="stTabs"] {
    margin-top: 0.35rem !important;
    padding-top: 0 !important;
}
div[data-testid="stVerticalBlock"]:has(#shear-visuals-block) div[data-testid="stRadio"] {
    margin-top: 0.25rem !important;
    padding-top: 0 !important;
}
div[data-testid="stVerticalBlock"]:has(#shear-visuals-block) label[data-testid="stWidgetLabel"] {
    margin-bottom: 0.2rem !important;
}
</style>
<div id="shear-visuals-block" class="shear-visuals-block" style="display:none;width:0;height:0;overflow:hidden;" aria-hidden="true"></div>
""",
            unsafe_allow_html=True,
        )
        render_section_title("Visualisation")
        current_mode = str(st.session_state.get("shear_visual_diagram_mode", "") or "").strip()
        if current_mode not in {"Side view", "Section", "Shear diagram"}:
            if str(st.session_state.get("shear_visual_panel_mode", "") or "").strip() == "Shear diagram":
                current_mode = "Shear diagram"
            else:
                current_mode = str(st.session_state.get("shear_reo_layout_mode", "Side view") or "Side view").strip()
                if current_mode not in {"Side view", "Section"}:
                    current_mode = "Side view"
            st.session_state["shear_visual_diagram_mode"] = current_mode

        visual_mode = str(st.session_state.get("shear_visual_diagram_mode", "Side view") or "Side view").strip()
        if visual_mode == "Section":
            _render_shear_cross_section()
        elif visual_mode == "Shear diagram":
            _render_shear_force_diagram()
        else:
            _render_shear_side_view()

        controls_col, _ = st.columns([5, 5], gap="small")
        with controls_col:
            st.radio(
                "Visualisation diagram",
                options=["Side view", "Section", "Shear diagram"],
                horizontal=True,
                key="shear_visual_diagram_mode",
            )


def build_reo_circles_from_state(shape_code: str, dims: dict):
    """
    Returns list of circles for reo overlay:
      [{"x":..,"y":..,"r":..}, ...]
    Coordinates are in the same section coordinate system used elsewhere:
      x in [0, W], y in [0, D] (y=0 at TOP)
    """

    recalc_derived_values()
    circles = []
    for coord in st.session_state.get("top_bar_coords", []):
        dia = float(coord.get("db", 0.0) or 0.0)
        if dia > 0.0:
            circles.append({"x": float(coord.get("x", 0.0)), "y": float(coord.get("y", 0.0)), "r": dia / 2.0})
    for coord in st.session_state.get("bot_bar_coords", []):
        dia = float(coord.get("db", 0.0) or 0.0)
        if dia > 0.0:
            circles.append({"x": float(coord.get("x", 0.0)), "y": float(coord.get("y", 0.0)), "r": dia / 2.0})
    return circles

    def _count_from_spacing(width: float, db: float, s: float) -> int:
        # centers must be >= db + s
        c2c = db + s
        if width <= db:
            return 1
        return max(1, int(math.floor((width - db) / c2c)) + 1)

    def _xs_even(x0: float, x1: float, n: int):
        if n <= 0:
            return []
        if n == 1:
            return [(x0 + x1) / 2.0]
        dx = (x1 - x0) / (n - 1)
        return [x0 + i * dx for i in range(n)]

    def _split_flange_outstands(bf: float, web_w: float):
        if web_w >= bf:
            return None
        xL_inner = (bf - web_w) / 2.0
        xR_inner = xL_inner + web_w
        return xL_inner, xR_inner

    def _place_in_outstands(n: int, db: float, bf: float, web_w: float, cover_side: float, min_clear: float):
        """
        Places n bars in flange outstands only, with cover to:
          - outer edge
          - inner web face
        Odd bar tries to go in web zone if it fits.
        """
        if n <= 0:
            return []

        split = _split_flange_outstands(bf, web_w)
        if split is None:
            # treat like full-width rectangle
            x0 = cover_side + db / 2
            x1 = bf - cover_side - db / 2
            return _xs_even(x0, x1, n)

        xL_inner, xR_inner = split

        # usable left outstand
        L0 = cover_side + db / 2
        L1 = xL_inner - cover_side - db / 2

        # usable right outstand
        R0 = xR_inner + cover_side + db / 2
        R1 = bf - cover_side - db / 2

        if L1 <= L0 or R1 <= R0:
            raise ValueError(
                f"No horizontal room in flange outstands after cover. bf={bf:.1f}, web_w={web_w:.1f}, "
                f"cover_side={cover_side:.1f}, db={db:.1f}"
            )

        nL = n // 2
        nR = n // 2
        nC = 0

        if n % 2 == 1:
            # try center bar between inner faces
            C0 = xL_inner + cover_side + db / 2
            C1 = xR_inner - cover_side - db / 2
            if C1 >= C0:
                nC = 1
            else:
                nR += 1  # push extra to right if no web-zone room

        xs = []
        if nL > 0:
            xs += _xs_even(L0, L1, nL)
        if nC == 1:
            xs += [bf / 2.0]
        if nR > 0:
            xs += _xs_even(R0, R1, nR)

        return sorted(xs)

    # -------------------------
    # Read geometry
    # -------------------------
    shape_code = (shape_code or "RECT").upper()
    D = float(dims.get("D", _safe_float(get_param("D"), 600.0)) or 600.0)

    if shape_code == "RECT":
        W = float(dims.get("b", _safe_float(get_param("b"), 300.0)) or 300.0)
    else:
        W = float(dims.get("bf", _safe_float(get_param("bf"), _safe_float(get_param("b"), 300.0))) or 300.0)

    # T/I specifics
    tf = float(dims.get("tf", _safe_float(get_param("tf"), 0.0)) or 0.0)
    bw = float(dims.get("bw", _safe_float(get_param("bw"), 0.0)) or 0.0)
    tw = float(dims.get("tw", _safe_float(get_param("tw"), bw)) or bw)

    # Covers / spacing
    cover_side = _safe_float(get_param("cover_side"), _safe_float(get_param("side_cover"), 25.0))
    cover_top = _safe_float(get_param("cover_top"), _safe_float(get_param("top_cover"), 25.0))
    cover_bot = _safe_float(get_param("cover_bot"), _safe_float(get_param("bottom_cover"), 25.0))
    min_clear = _safe_float(get_param("min_clear_spacing"), 20.0)

    # Row gaps (clear gap between bars)
    rowgap_top = _safe_float(get_param("rowgap_top"), 20.0)
    rowgap_bot = _safe_float(get_param("rowgap_bot"), 20.0)
    rowgap_top = max(rowgap_top, min_clear)
    rowgap_bot = max(rowgap_bot, min_clear)

    # -------------------------
    # Read reinforcement (prefer 2-layer keys; fallback to nb_top/nb_bot)
    # -------------------------
    top1_mode = str(get_param("top1_layout_mode", "Count"))
    top2_mode = str(get_param("top2_layout_mode", "Count"))
    bot1_mode = str(get_param("bot1_layout_mode", "Count"))
    bot2_mode = str(get_param("bot2_layout_mode", "Count"))

    nb_or_s_top_1 = _safe_float(get_param("nb_or_s_top_1"), _safe_float(get_param("nb_top"), 2))
    nb_or_s_top_2 = _safe_float(get_param("nb_or_s_top_2"), 0.0)
    db_top_1 = _safe_float(get_param("db_top_1"), _safe_float(get_param("db_top"), 16.0))
    db_top_2 = _safe_float(get_param("db_top_2"), db_top_1)

    nb_or_s_bot_1 = _safe_float(get_param("nb_or_s_bot_1"), _safe_float(get_param("nb_bot"), 4))
    nb_or_s_bot_2 = _safe_float(get_param("nb_or_s_bot_2"), 0.0)
    db_bot_1 = _safe_float(get_param("db_bot_1"), _safe_float(get_param("db_bot"), 20.0))
    db_bot_2 = _safe_float(get_param("db_bot_2"), db_bot_1)

    # resolve to counts
    def _resolve_n(mode: str, nb_or_s: float, width: float, db: float) -> int:
        if str(mode).lower().startswith("count"):
            return int(nb_or_s)
        # spacing mode
        return _count_from_spacing(width, db, nb_or_s)

    circles = []

    # -------------------------
    # TOP layers
    # -------------------------
    if shape_code == "RECT":
        width_top_1 = (W - 2 * cover_side - db_top_1)
        n_top_1 = _resolve_n(top1_mode, nb_or_s_top_1, width_top_1, db_top_1)
        n_top_2 = _resolve_n(top2_mode, nb_or_s_top_2, width_top_1, db_top_2)
        x0_1 = cover_side + db_top_1 / 2
        x1_1 = W - cover_side - db_top_1 / 2
        y1 = cover_top + db_top_1 / 2
        y2 = y1 + (db_top_1 / 2) + rowgap_top + (db_top_2 / 2)

        if n_top_1 > 0:
            xs = _xs_even(x0_1, x1_1, n_top_1)
            circles += [{"x": x, "y": y1, "r": db_top_1 / 2} for x in xs]

        if n_top_2 > 0:
            x0_2 = cover_side + db_top_2 / 2
            x1_2 = W - cover_side - db_top_2 / 2
            xs = _xs_even(x0_2, x1_2, n_top_2)
            circles += [{"x": x, "y": y2, "r": db_top_2 / 2} for x in xs]

    elif shape_code == "T":
        # top in flange outstands (web width = bw)
        web_w = bw if bw > 0 else max(1.0, W / 3.0)
        # use full flange width for count from spacing
        width_top_1 = (W - 2 * cover_side - db_top_1)
        n_top_1 = _resolve_n(top1_mode, nb_or_s_top_1, width_top_1, db_top_1)
        n_top_2 = _resolve_n(top2_mode, nb_or_s_top_2, width_top_1, db_top_2)

        y1 = cover_top + db_top_1 / 2
        y2 = y1 + (db_top_1 / 2) + rowgap_top + (db_top_2 / 2)

        # flange vertical fit for 2nd layer
        if n_top_2 > 0 and tf > 0:
            if y2 + db_top_2 / 2 > tf + 1e-9:
                raise ValueError(
                    f"Top flange too thin for 2 layers: tf={tf:.1f} needs cover_top+db1+rowgap+db2 <= tf "
                    f"({cover_top:.1f}+{db_top_1:.1f}+{rowgap_top:.1f}+{db_top_2:.1f}="
                    f"{(cover_top + db_top_1 + rowgap_top + db_top_2):.1f})"
                )

        if n_top_1 > 0:
            xs = _place_in_outstands(n_top_1, db_top_1, W, web_w, cover_side, min_clear)
            circles += [{"x": x, "y": y1, "r": db_top_1 / 2} for x in xs]
        if n_top_2 > 0:
            xs = _place_in_outstands(n_top_2, db_top_2, W, web_w, cover_side, min_clear)
            circles += [{"x": x, "y": y2, "r": db_top_2 / 2} for x in xs]

    elif shape_code == "I":
        # top in flange outstands (web width = tw)
        web_w = tw if tw > 0 else max(1.0, W / 3.0)
        width_top_1 = (W - 2 * cover_side - db_top_1)
        n_top_1 = _resolve_n(top1_mode, nb_or_s_top_1, width_top_1, db_top_1)
        n_top_2 = _resolve_n(top2_mode, nb_or_s_top_2, width_top_1, db_top_2)

        y1 = cover_top + db_top_1 / 2
        y2 = y1 + (db_top_1 / 2) + rowgap_top + (db_top_2 / 2)

        if n_top_2 > 0 and tf > 0:
            if y2 + db_top_2 / 2 > tf + 1e-9:
                raise ValueError(
                    f"Top flange too thin for 2 layers: tf={tf:.1f} needs cover_top+db1+rowgap+db2 <= tf "
                    f"({cover_top:.1f}+{db_top_1:.1f}+{rowgap_top:.1f}+{db_top_2:.1f}="
                    f"{(cover_top + db_top_1 + rowgap_top + db_top_2):.1f})"
                )

        if n_top_1 > 0:
            xs = _place_in_outstands(n_top_1, db_top_1, W, web_w, cover_side, min_clear)
            circles += [{"x": x, "y": y1, "r": db_top_1 / 2} for x in xs]
        if n_top_2 > 0:
            xs = _place_in_outstands(n_top_2, db_top_2, W, web_w, cover_side, min_clear)
            circles += [{"x": x, "y": y2, "r": db_top_2 / 2} for x in xs]

    # -------------------------
    # BOTTOM layers
    # -------------------------
    if shape_code == "RECT":
        width_bot_1 = (W - 2 * cover_side - db_bot_1)
        n_bot_1 = _resolve_n(bot1_mode, nb_or_s_bot_1, width_bot_1, db_bot_1)
        n_bot_2 = _resolve_n(bot2_mode, nb_or_s_bot_2, width_bot_1, db_bot_2)

        x0_1 = cover_side + db_bot_1 / 2
        x1_1 = W - cover_side - db_bot_1 / 2
        y1 = D - cover_bot - db_bot_1 / 2
        y2 = y1 - (db_bot_1 / 2) - rowgap_bot - (db_bot_2 / 2)

        if n_bot_1 > 0:
            xs = _xs_even(x0_1, x1_1, n_bot_1)
            circles += [{"x": x, "y": y1, "r": db_bot_1 / 2} for x in xs]
        if n_bot_2 > 0:
            x0_2 = cover_side + db_bot_2 / 2
            x1_2 = W - cover_side - db_bot_2 / 2
            xs = _xs_even(x0_2, x1_2, n_bot_2)
            circles += [{"x": x, "y": y2, "r": db_bot_2 / 2} for x in xs]

    elif shape_code == "T":
        # bottom bars in WEB for T (width = bw)
        web_w = bw if bw > 0 else max(1.0, W / 3.0)
        x_web0 = (W - web_w) / 2.0
        x_web1 = x_web0 + web_w

        width_bot_1 = (web_w - 2 * cover_side - db_bot_1)
        n_bot_1 = _resolve_n(bot1_mode, nb_or_s_bot_1, width_bot_1, db_bot_1)
        n_bot_2 = _resolve_n(bot2_mode, nb_or_s_bot_2, width_bot_1, db_bot_2)

        y1 = D - cover_bot - db_bot_1 / 2
        y2 = y1 - (db_bot_1 / 2) - rowgap_bot - (db_bot_2 / 2)

        if n_bot_1 > 0:
            x0_1 = x_web0 + cover_side + db_bot_1 / 2
            x1_1 = x_web1 - cover_side - db_bot_1 / 2
            xs = _xs_even(x0_1, x1_1, n_bot_1)
            circles += [{"x": x, "y": y1, "r": db_bot_1 / 2} for x in xs]
        if n_bot_2 > 0:
            x0_2 = x_web0 + cover_side + db_bot_2 / 2
            x1_2 = x_web1 - cover_side - db_bot_2 / 2
            xs = _xs_even(x0_2, x1_2, n_bot_2)
            circles += [{"x": x, "y": y2, "r": db_bot_2 / 2} for x in xs]

    elif shape_code == "I":
        # bottom in bottom flange outstands (web width = tw)
        web_w = tw if tw > 0 else max(1.0, W / 3.0)
        width_bot_1 = (W - 2 * cover_side - db_bot_1)
        n_bot_1 = _resolve_n(bot1_mode, nb_or_s_bot_1, width_bot_1, db_bot_1)
        n_bot_2 = _resolve_n(bot2_mode, nb_or_s_bot_2, width_bot_1, db_bot_2)

        y1 = D - cover_bot - db_bot_1 / 2
        y2 = y1 - (db_bot_1 / 2) - rowgap_bot - (db_bot_2 / 2)

        # flange vertical fit for 2nd bottom layer (assume same tf)
        if n_bot_2 > 0 and tf > 0:
            # bottom flange zone is y in [D-tf, D]
            if (y2 - db_bot_2 / 2) < (D - tf) - 1e-9:
                raise ValueError(
                    f"Bottom flange too thin for 2 layers: tf={tf:.1f} needs cover_bot+db1+rowgap+db2 <= tf "
                    f"({cover_bot:.1f}+{db_bot_1:.1f}+{rowgap_bot:.1f}+{db_bot_2:.1f}="
                    f"{(cover_bot + db_bot_1 + rowgap_bot + db_bot_2):.1f})"
                )

        if n_bot_1 > 0:
            xs = _place_in_outstands(n_bot_1, db_bot_1, W, web_w, cover_side, min_clear)
            circles += [{"x": x, "y": y1, "r": db_bot_1 / 2} for x in xs]
        if n_bot_2 > 0:
            xs = _place_in_outstands(n_bot_2, db_bot_2, W, web_w, cover_side, min_clear)
            circles += [{"x": x, "y": y2, "r": db_bot_2 / 2} for x in xs]

    return circles


# ------------------------------------------------------------
#  Shear diagrams – always-on right-hand side per step
# ------------------------------------------------------------

STEP_DIAGRAMS = {
    1: ("shear_step1_torsion_crack.png", "Step 1 – shear + torsion cracking region"),
    2: ("shear_step2_dv_critical_section.png", "Step 2 – critical section at $d_v$"),
    3: ("shear_step3_Veq_shear_demand.png", "Step 3 – equivalent shear $V_{eq}^*$"),
    4: ("shear_step4_epsx.png", "Step 4 – longitudinal strain $\\varepsilon_x$"),
    5: ("shear_step5_kv_theta.png", "Step 5 – $k_v$ and $\\theta_v$"),
    6: ("shear_step6_Vuc_Vus.png", "Step 6 – $V_{uc}$ and $V_s$"),
    7: ("shear_step7_Vumax.png", "Step 9 – web-crushing limit $V_{u,\\max}$"),
    8: ("shear_step8_lig_spacing.png", "Step 8 – ligature spacing and detailing"),
}


def _safe_step_diagram(step_no: int):
    """Always show the diagram for a step on the right; fail gracefully if missing."""
    fname, caption = STEP_DIAGRAMS.get(step_no, (None, None))
    if not fname:
        return
    path = os.path.join("assets", fname)
    
    # Special handling for Step 5: two-column layout with theta.png on the right
    if step_no == 5:
        col_left, col_right = st.columns([1, 1])
        with col_left:
            if os.path.exists(path):
                render_image_diagram(
                    path,
                    key=f"shear_step_{step_no}_diagram",
                    title=caption or f"Shear step {step_no} diagram",
                    caption=caption,
                    use_container_width=True,
                )
            else:
                st.info(f"💡 Add diagram for Step {step_no} at `{path}`.")
        with col_right:
            theta_path = os.path.join("assets", "theta.png")
            if os.path.exists(theta_path):
                render_image_diagram(
                    theta_path,
                    key=f"shear_step_{step_no}_theta_diagram",
                    title="Strut angle",
                    caption="Strut angle $\\theta_v$",
                    use_container_width=True,
                )
            else:
                st.info(f"💡 Add theta diagram at `{theta_path}`.")
        return
    
    # Special handling for Step 9 (step_no == 7 in dict): stack two images vertically
    if step_no == 7:  # This is Step 9 in the display
        if os.path.exists(path):
            render_image_diagram(
                path,
                key=f"shear_step_{step_no}_diagram",
                title=caption or "Shear step diagram",
                caption=caption,
                use_container_width=True,
            )
        else:
            st.info(f"💡 Add diagram for Step 9 at `{path}`.")
        # Add second image below
        vumax2_path = os.path.join("assets", "shear_step7_Vumax2.png")
        if os.path.exists(vumax2_path):
            render_image_diagram(
                vumax2_path,
                key=f"shear_step_{step_no}_vumax2_diagram",
                title="Strut-and-tie behaviour",
                caption="Strut-and-tie / concrete compression strut behaviour in deep beams",
                use_container_width=True,
            )
        else:
            st.info(f"💡 Add Step 9 second diagram at `{vumax2_path}`.")
        return
    
    # Default: single image
    if os.path.exists(path):
        render_image_diagram(
            path,
            key=f"shear_step_{step_no}_diagram",
            title=caption or f"Shear step {step_no} diagram",
            caption=caption,
            use_container_width=True,
        )
    else:
        st.info(f"💡 Add diagram for Step {step_no} at `{path}`.")


# ------------------------------------------------------------
#  Shear theory insights – one toggle per step
# ------------------------------------------------------------

def render_shear_step_insight(step_no: int):
    """Render the theory/insight text for a given shear step inside an expander."""
    if step_no == 1:
        st.markdown("### Check 1 – Shear + torsion cracking region")
        st.markdown(
            r"""
**Why we convert torsion into equivalent shear**



- Torsion produces **diagonal tension** in the beam web, similar to shear-induced diagonal cracking.  

- Treating torsion as an **equivalent shear demand** is conservative and avoids separate iterative torsion-shear coupling.  

- Using an equivalent shear $V_{eq}^*$ means:

  - We track a **single internal force state** through all MCFT steps.  

  - Longitudinal strain $\varepsilon_x$ reflects the combined effect of **shear + torsion + axial**.  

  - We don't under-predict crack width or concrete shear strength.



This step sets up a **consistent load model** that will be used for all subsequent MCFT-based checks.

"""
        )

    elif step_no == 2:
        st.markdown("### Check 2 – Critical section at $d_v$")
        st.markdown(
            r"""
**Why shear is checked at $d_v$**



- Tests show that **peak diagonal cracking** and shear demand occur at about **one effective depth $d_v$** from the support.  

- Around this section:

  - Flexural cracks rotate into steeper **diagonal shear cracks**.  

  - **Aggregate interlock** begins to reduce.  

  - **Concrete compression struts** form between the load and support.  

- AS 3600 takes the design shear at a distance **$d_v$ from the face of the support** and ignores distributed loads between the support and that section.  

- If significant point loads fall within this zone, behaviour is closer to a **deep beam / strut-and-tie** region.



This step identifies **where** to apply the MCFT shear model in the member.

"""
        )

    elif step_no == 3:
        st.markdown("### Check 3 – Equivalent shear $V_{eq}^*$")
        st.markdown(
            r"""
**Why we use $V_{eq}^*$ instead of $V^*$**



- MCFT relies on a **single set of internal forces** to define the strain state.  

- Shear, torsion and axial load all influence the **longitudinal strain $\varepsilon_x$**.  

- Converting to an equivalent shear $V_{eq}^*$ helps to:

  - Keep the strain-based model **simple and conservative**.  

  - Avoid under-estimating crack width and over-estimating concrete shear strength.  

  - Line up with the **CSA 2004 approach** which AS 3600 follows for shear.



This step ensures that all later calculations (εₓ, $k_v$, $\theta_v$, $V_{uc}$, $V_s$) are based on a **consistent combined shear demand**.

"""
        )

    elif step_no == 4:
        st.markdown("### Check 4 – Longitudinal strain $\varepsilon_x$")
        st.markdown(
            r"""
**Why $\varepsilon_x$ controls concrete shear strength**



- In MCFT, **crack width** is tied directly to longitudinal strain and crack spacing:  



  $$w \approx 0.2\ \text{mm} + 1000\,\varepsilon_x$$  



- As $\varepsilon_x$ increases:

  - Crack widths **grow**,  

  - **Aggregate interlock** reduces,  

  - Diagonal **compression struts flatten**,  

  - More shear is forced into **stirrups**.  



- AS 3600 uses two closed-form strain equations:

  - **Equation (1)** – mid-depth in **tension** ($\varepsilon_x \ge 0$)  

  - **Equation (2)** – mid-depth in **slight compression** ($\varepsilon_x < 0$)  



- The selected strain is then **bounded**:  



  $$-2.0\times 10^{-4} \le \varepsilon_x \le 3.0\times 10^{-3}$$  



This step is the **core of the MCFT approach**:  

$\varepsilon_x \rightarrow$ crack width $\rightarrow k_v \rightarrow V_{uc} \rightarrow \theta_v \rightarrow V_s$.

"""
        )

    elif step_no == 5:
        st.markdown("### Check 5 – $k_v$ and $\theta_v$")
        st.markdown(
            r"""
**What $k_v$ represents**



- $k_v$ is a **concrete shear-transfer efficiency factor** in MCFT.  

- It collects the effects of:

  - Residual concrete shear across cracks,  

  - **Aggregate interlock**,  

  - **Dowel action** from longitudinal bars,  

  - Friction along the crack faces.  



- For members with at least minimum shear reinforcement:  



  $$k_v = \frac{0.4}{1 + 1500\varepsilon_x}$$  



- For members with **less than minimum shear reinforcement**, extra modifiers account for **member depth and crack spacing**.



As $\varepsilon_x$ increases, cracks widen and **$k_v$ drops**, reducing the concrete contribution $V_{uc}$.



**What $\theta_v$ represents**



- $\theta_v$ is the **angle of the diagonal compression strut** in the web.  

- AS 3600 uses:



  $$\theta_v = 29^\circ + 7000\varepsilon_x$$  



  with limits of **15° to 50°**.  



- Higher $\varepsilon_x$ → flatter stress field → **larger $\theta_v$**.  

- $\theta_v$ affects both:

  - Concrete contribution $V_{uc}$, and  

  - Steel contribution $V_s$ (via $\cot\theta_v$).



This step converts the strain state into the **geometry and efficiency** of the shear-resisting stress field.

"""
        )

    elif step_no == 6:
        st.markdown("### Check 6 – Concrete shear $V_{uc}$ and steel shear $V_s$")
        st.markdown(
            r"""
**Concrete contribution $V_{uc}$**



- MCFT gives the concrete shear contribution at the critical section as:



  $$V_{uc} = k_v\, b_v\, d_v\, \sqrt{f'_c}$$  



- $V_{uc}$ reduces when:

  - Longitudinal strain $\varepsilon_x$ increases (cracks widen),  

  - Effective shear depth $d_v$ increases,  

  - Effective crack spacing increases,  

  - Aggregate interlock and dowel action become less effective.



**Steel contribution $V_s$**



- Stirrups cross the **inclined crack length**:



  $$\ell_{cr} \approx d_v \cot\theta_v$$  



- Number of stirrup legs crossing the crack within spacing $s$:



  $$n = \frac{d_v \cot\theta_v}{s}$$  



- The shear resisted by stirrups is:



  $$V_s = V_{us} = \frac{A_{sv} f_{sy,v} d_v}{s}\cot\theta_v$$  



- Shear reinforcement:

  - Increases **ultimate shear capacity**,  

  - Provides **ductility and warning**,  

  - Helps **control crack widths**.



This step combines $V_{uc}$ and $V_s$ to give the **total shear resistance** at the critical section.

"""
        )

    elif step_no == 7:
        st.markdown("### Check 9 – Web-crushing limit $V_{u,\\max}$")
        st.markdown(
            r"""
**Why $V_{u,\\max}$ is needed**



- Even with a lot of shear reinforcement, the **concrete web** can only carry a finite **compression strut force**.  

- Once the diagonal concrete strut reaches its **crushing limit**, the failure is **sudden and brittle**.  



- AS 3600 caps the design shear by a web-crushing limit of the form:



  $$V_{u,\\max} = 0.55\, b_v\, d_v\, \sqrt{f'_c}\,(\cot\theta_v + \cot\alpha_v)$$  



  with **$\alpha_v = 90^\circ$** for vertical stirrups.



- If the applied shear demand $V_u^*$ approaches or exceeds $V_{u,\\max}$:

  - Increasing stirrup area **no longer increases capacity**,  

  - Modifying the **geometry** (web thickness, depth, load position) becomes necessary.



This step ensures the design remains within the **concrete web strength** envelope, not just the stirrup capacity.

"""
        )

    elif step_no == 8:
        st.markdown("### Check 8 – Ligature spacing and detailing")
        st.markdown(
            r"""
**Why ligature spacing rules exist**



- Shear demand **varies along the beam**, but cracks localise around the **peak shear region**.  

- If shear reinforcement is not distributed carefully, there can be a **local "weak zone"** where $A_{sv}/s$ is not enough.  



- AS 3600 Cl. 8.2.5.1 assumes:

  - The **required** shear reinforcement ratio $A_{sv}/s$ varies **linearly** over a segment.  

  - The **provided** reinforcement must stay **on or above** that required line.  



- Figure C8.2.5.1 shows recommended detailing arrangements to avoid under-reinforced pockets.



This step checks that the **physical layout of the ligatures** matches the required shear resistance along the span.

"""
        )


# ------------------------------------------------------------
#  Small helpers
# ------------------------------------------------------------
def _fmt(val, decimals=1):
    """Safe number formatter for text in calc boxes."""
    try:
        if val is None:
            return "—"
        return f"{float(val):.{decimals}f}"
    except Exception:
        return "—"


# _inject_calcbox_css() removed - use apply_calcbox_css() from widgets_helpers instead




# ------------------------------------------------------------
#  SHEAR – DRAWINGS + INSIGHT BLOCKS
# ------------------------------------------------------------

def _safe_image(path: str, caption: str | None = None, width: int | None = None, use_container_width: bool | None = None):
    """Tiny helper so missing images don't break the app."""
    candidate_paths = [path]
    if not os.path.isabs(path):
        candidate_paths.append(os.path.join(os.path.dirname(__file__), path))

    resolved_path = next((candidate for candidate in candidate_paths if os.path.exists(candidate)), None)
    if not resolved_path:
        st.info(f"Add image file at `{path}` for: {caption or 'shear illustration'}")
        return

    image_key = "shear_reference_" + re.sub(r"[^A-Za-z0-9_]+", "_", str(resolved_path))
    try:
        if width is not None:
            render_image_diagram(
                resolved_path,
                key=image_key,
                title=caption or "Shear reference diagram",
                caption=caption,
                width=width,
            )
        elif use_container_width is not None:
            render_image_diagram(
                resolved_path,
                key=image_key,
                title=caption or "Shear reference diagram",
                caption=caption,
                use_container_width=use_container_width,
            )
        else:
            render_image_diagram(
                resolved_path,
                key=image_key,
                title=caption or "Shear reference diagram",
                caption=caption,
                use_container_width=True,
            )
    except Exception:
        st.info(f"Unable to open image `{path}` right now.")


def render_shear_mcft_block():
    """
    High-level MCFT / Vuc / kv insight, linked to eps_x.
    Diagram on the right, theory in an ℹ️ popover attached to it.
    """
    st.markdown("### MCFT concrete shear strength – role of εₓ and k_v")

    # Centered diagram taking up most of the width
    col_left, col_center, col_right = st.columns([1, 6, 1])

    with col_center:
        img_col, info_col = st.columns([10, 1])

        # Diagram
        with img_col:
            _safe_image(
                "assets/shear_mcft_principal_struts.png",
                caption="Principal compression struts and diagonal cracking in MCFT.",
            )

        # Info button
        with info_col:
            with info_i_button(use_container_width=True):
                calcbox(
                    r"""
**Concrete contribution $V_{uc}$ in AS 3600**



- In the **Simplified Modified Compression Field Theory (SMCFT)** used by AS 3600,  

  concrete shear strength at the critical section is written as  



  $$V_{uc} = k_v\, b_v\, d_v\, \sqrt{f'_c}$$



- The factor **$k_v$** captures how shear is transferred across **cracked concrete**, combining:  

  - direct concrete shear,  

  - **aggregate interlock**, and  

  - **dowel action** from longitudinal bars.



**Influence of longitudinal strain εₓ**



- The mid-depth longitudinal strain **εₓ** is derived from internal forces (moment, shear, torsion, axial, prestress).  

- As **εₓ increases**, cracks widen and aggregate interlock reduces → **$k_v$ decreases** and the concrete contribution **$V_{uc}$ drops**.  

- Higher εₓ flattens the compression struts (smaller $\theta_v$), increases longitudinal tension forces and raises concrete web compression.

"""
                )

                calcbox(
                    r"""
**Deriving $k_v$ from crack width**



- SMCFT relates **crack width w** to strain and spacing as  



  $$w \approx 0.2\ \text{mm} + 1000\,\varepsilon_x$$



- The constant 0.2 mm represents the **initial crack width** at very small strains.  

- The second term $1000\,\varepsilon_x$ captures **additional widening** as tensile strain grows.  

- This $w$–$\varepsilon_x$ relationship feeds directly into **$k_v$**:  

  - With **minimum or greater shear reinforcement**, a simple form  



    $$k_v = \frac{0.4}{1 + 1500\,\varepsilon_x}$$  



    is used.  

  - With **less than minimum shear reinforcement**, an extra size and spacing factor  



    $$\frac{1300}{1000 + k_{dg} d_v}$$  



    adjusts $k_v$ for effective crack spacing and member depth.

"""
                )


def render_shear_steel_and_spacing_block():
    """
    Ligature spacing / detailing only.
    Steel contribution V_s is now covered in the main Step 7 calc box.
    """
    st.markdown("### Ligature spacing and detailing along the span")

    # Centered diagram taking up most of the width
    col_left, col_center, col_right = st.columns([1, 6, 1])

    with col_center:
        _safe_image(
            "assets/shear_lig_spacing_code_diagram.png",
            caption="Example of varying Asv/s along the span (AS 3600 Fig. C8.2.5.1).",
        )

    # Spacing theory in toggle below
    with st.expander(
        "Show ligature spacing and detailing explanation", expanded=False
    ):
        calcbox(
                r"""
**Ligature spacing (AS 3600 Cl. 8.2.5.1)**





- Where the required shear reinforcement **$A_{sv}/s$ varies** along the member, the code assumes a **linear variation** over each segment.  



- Detailing should follow the **recommended patterns** (e.g. Figure C8.2.5.1), so that provided $A_{sv}/s$ ≥ required $A_{sv}/s$ in the **critical region**.  



- Proper spacing is essential because shear failure due to **yielding of ligatures** tends to occur in a **localized zone** near peak shear.  



- The goal is to avoid "gaps" in shear resistance where the **provided envelope drops below the required line**.



"""
            )


# ------------------------------------------------------------
#  COMPUTE FUNCTION (no UI rendering)
# ------------------------------------------------------------
def compute_shear_results(publish: bool = True) -> dict:
    """
    Compute shear results without UI rendering.
    
    Args:
        publish: If True, publish to results dict for report export.
    
    Returns:
        dict with computed results
    """
    from state_and_helpers import recalc_derived_values
    
    recalc_derived_values()

    shear_bundle = build_shear_calc_bundle_from_state(st.session_state)
    live_shear_state = shear_bundle["live_state"]
    actions = shear_bundle["actions_used"]
    results = shear_bundle["results"]
    phi = float(shear_bundle["phi"])

    # --- Read inputs (shared canonical state) ---
    b = live_shear_state["b"]
    D = live_shear_state["D"]
    d = live_shear_state["d"]
    fc = live_shear_state["fc"]
    fsy = live_shear_state["fsy"]
    Ec = live_shear_state["Ec"]
    Es = live_shear_state["Es"]
    M_star = live_shear_state["Mu"]
    Vu_star = live_shear_state["Vu"]
    Tu_star = live_shear_state["Tu"]
    N_star = live_shear_state["Nu"]
    P_v = live_shear_state["Pu"]

    lig_d = live_shear_state["lig_d"]
    legs = live_shear_state["lig_legs"]
    s_lig = live_shear_state["s_lig"]
    
    # Derived metrics
    utilisation_values = shear_capacity_utilisation_values(results, phi)
    phi_Vu_cap = utilisation_values["phi_Vu_cap"]
    util = utilisation_values["util"]
    phi_Vu_max = utilisation_values["phi_Vu_max_kN"]
    Vuc_util = utilisation_values["web_util"]
    
    # Minimum shear reinforcement + spacing checks
    reinforcement_checks = shear_reinforcement_spacing_check_values(
        Asv_mm2=results.Asv,
        s_lig_mm=s_lig,
        fc_mpa=fc,
        b_v_mm=results.b_v,
        f_syv_mpa=results.f_syv,
        D_mm=D,
    )
    Asv_over_s = reinforcement_checks["Asv_over_s"]
    Asv_min_over_s = reinforcement_checks["Asv_min_over_s"]
    min_shear_ok = reinforcement_checks["min_shear_ok"]
    max_spacing = reinforcement_checks["max_spacing"]
    spacing_ok = reinforcement_checks["spacing_ok"]
    
    # Summary for report
    summary = [
        ("Demand", f"{results.V_eq:.1f} kN"),
        ("Capacity", f"{phi_Vu_cap:.1f} kN"),
        ("Utilisation", f"{util:.2f}" if not math.isnan(util) else "—"),
        ("Outcome", "PASS" if util <= 1.0 else "FAIL"),
    ]
    
    boxes = []
    
    boxes.append({
        "id": "1",
        "title": "Actions",
        "clause": "AS 3600:2018 Cl. 2.3",
        "derivation": "<br/>".join([
            f"V* = {Vu_star:.1f} kN",
            f"T* = {Tu_star:.1f} kNm",
            f"V_eq* = {results.V_eq:.1f} kN",
        ]),
        "result": "",
        "status": None,
        "diagram": None,
    })
    
    boxes.append({
        "id": "2",
        "title": "Effective section + reinforcement",
        "clause": "AS 3600:2018 Cl. 8.2.2",
        "derivation": "<br/>".join([
            f"b_v = {results.b_v:.0f} mm",
            f"d_v = {results.d_v:.0f} mm",
            f"A_sv = {results.Asv:.0f} mm²",
            f"Provided link spacing s = {s_lig:.0f} mm",
        ]),
        "result": "",
        "status": None,
        "diagram": None,
    })
    
    boxes.append({
        "id": "3",
        "title": "MCFT parameters",
        "clause": "AS 3600:2018 Cl. 8.2.4",
        "derivation": "<br/>".join([
            f"εx = {results.eps_x:.5f}",
            f"k_v = {results.k_v:.3f}",
            f"θ_v = {results.theta_v_deg:.1f}°",
        ]),
        "result": "",
        "status": None,
        "diagram": None,
    })
    
    boxes.append({
        "id": "4",
        "title": "Concrete shear capacity",
        "clause": "AS 3600:2018 Cl. 8.2.4.1",
        "derivation": "<br/>".join([
            f"b_v = {results.b_v:.0f} mm",
            f"d_v = {results.d_v:.0f} mm",
            f"V_uc = {results.Vuc_kN:.1f} kN",
        ]),
        "result": f"φV_uc = {(phi * results.Vuc_kN):.1f} kN",
        "status": None,
        "diagram": None,
    })
    
    boxes.append({
        "id": "5",
        "title": "Shear reinforcement contribution",
        "clause": "AS 3600:2018 Cl. 8.2.5",
        "derivation": "<br/>".join([
            f"A_sv = {results.Asv:.0f} mm²",
            f"Provided link spacing s = {s_lig:.0f} mm",
            f"V_us = {results.Vus_kN:.1f} kN",
        ]),
        "result": f"φV_us = {(phi * results.Vus_kN):.1f} kN",
        "status": None,
        "diagram": None,
    })
    
    boxes.append({
        "id": "6",
        "title": "Total shear capacity and utilisation",
        "clause": "AS 3600:2018",
        "derivation": "<br/>".join([
            f"φV_u = {phi_Vu_cap:.1f} kN",
            f"Util = V_eq*/(φV_u) = {util:.2f}" if not math.isnan(util) else "Util = —",
        ]),
        "result": "PASS" if util <= 1.0 else "FAIL",
        "status": "pass" if util <= 1.0 else "fail",
        "diagram": None,
    })
    
    boxes.append({
        "id": "7",
        "title": "Web-crushing limit",
        "clause": "AS 3600:2018 Cl. 8.2.6",
        "derivation": "<br/>".join([
            f"V_u,max = {results.Vu_max_kN:.1f} kN",
            f"Demand = {results.LHS:.1f}",
            f"Capacity = {results.RHS:.1f}",
        ]),
        "result": "PASS" if results.web_ok else "FAIL",
        "status": "pass" if results.web_ok else "fail",
        "diagram": None,
    })
    
    boxes.append({
        "id": "8",
        "title": "Minimum shear reinforcement + spacing",
        "clause": "AS 3600:2018 Cl. 8.2.5",
        "derivation": "<br/>".join([
            f"A_sv/s = {Asv_over_s:.3f} mm²/mm",
            f"(A_sv/s)_min = {Asv_min_over_s:.3f} mm²/mm",
            f"s_max = {max_spacing:.0f} mm",
        ]),
        "result": "PASS" if (min_shear_ok and spacing_ok) else "FAIL",
        "status": "pass" if (min_shear_ok and spacing_ok) else "fail",
        "diagram": None,
    })
    
    shear_report = {
        "module_title": "Shear (ULS)",
        "summary": summary,
        "tabs": [{"tab_title": "ULS Checks", "boxes": boxes}],
    }
    
    if publish:
        update_results(
            phi_Vu_cap=phi_Vu_cap,
            Vu_utilisation=util if not math.isnan(util) else 0.0,
            Vu_max_kN=results.Vu_max_kN,
            phi_Vu_max_kN=phi_Vu_max,
            V_eq_kN=results.V_eq,
            Vuc_utilisation=Vuc_util if not math.isnan(Vuc_util) else None,
        )
        
        st.session_state.setdefault("results", {})
        st.session_state["results"]["shear_report"] = shear_report
    
    return {
        "phi_Vu_cap": phi_Vu_cap,
        "Vu_utilisation": util,
        "V_eq": results.V_eq,
        "Vuc_kN": results.Vuc_kN,
        "Vus_kN": results.Vus_kN,
        "shear_report": shear_report,
    }


# ------------------------------------------------------------
#  MAIN PAGE RENDER FUNCTION
# ------------------------------------------------------------
def render_shear():
    page_title_placeholder = st.container()
    _shear_visualisation_section.bind_runtime(globals())
    render_timing_mark("shear_page.runtime.start")
    # Handle cross-page navigation from Inputs page
    from jump_nav import JUMP_NAV_TAB_KEY, get_jump_uid

    st.session_state["shear_page_auto_spacing_ui_removed"] = True
    st.session_state["shear_page_spacing_mode"] = "manual_provided_only"

    get_jump_uid()
    _jt = st.session_state.get("jump_to")
    if _jt:
        _tab = SHEAR_ROW_UID_TO_TAB.get(str(_jt).strip())
        if _tab:
            st.session_state[JUMP_NAV_TAB_KEY] = _tab
    
    apply_global_widget_css()
    apply_result_page_css()
    apply_calcbox_css()
    apply_step_summary_expander_css()
    
    # Initialize step UI state (always-summary mode - no checkbox)

    def _render_shear_explainer() -> None:
        col_left, col_right = st.columns([1, 1])

        with col_left:
            st.markdown(
                r"""
This page computes **ultimate shear and torsion capacity** outputs in accordance with **AS 3600:2018** using the MCFT-based shear method, and reports the governing utilisation checks.

- **Design shear capacity**  
  $ \phi V_{uc} = \phi(V_c + V_s) $, used for the governing shear strength check.

- **Concrete shear contribution (MCFT)**  
  $ V_c = k_v \cdot b_v \cdot d_v \cdot \sqrt{f'_c} $, depends on $\varepsilon_x$ and $\theta_v$.

- **Torsion and interaction (when applicable)**  
  $ V_{eq}^* = \sqrt{(V^*)^2 + V_{t,eq}^2} $, used for combined shear–torsion checks.

### When to use each method

Use the **simplified method** for typical non-prestressed reinforced concrete beams when the **AS 3600** simplified-method conditions are satisfied.

Use the **general method** when those limits are not met, or when a more rigorous shear check is needed.

The simplified route is for **ordinary beams only** where the standard conditions apply—for example a **non-prestressed** member, **no applied axial tension**, and the **ordinary material and property limits** the code requires for that method.

### Why

The simplified method is a **faster** standard check that uses **fixed code assumptions** (the MCFT-style simplification permitted for qualifying beams).

The general method is **more detailed** because it **calculates shear parameters from the actual section actions and response**. That makes it more suitable when effects such as **axial force**, **torsion**, or other **non-standard conditions** are important.

In short:

- **Simplified** — quicker, standard code-permitted beam check when conditions are met.  
- **General** — more detailed, action-sensitive check.
        """
            )

        with col_right:
            spacer_col, img_col, info_col = st.columns([1, 5, 1])

            with img_col:
                st.markdown("<div style='text-align:center;'>", unsafe_allow_html=True)
                _safe_image(
                    "assets/shear_flexural_cracks_dv.png",
                    caption=None,
                    width=396,
                )
                st.markdown("</div>", unsafe_allow_html=True)

            with info_col:
                with info_i_button(use_container_width=True):
                    calcbox(
                        r"""
**What is shear in a beam?**







- Shear forces act **perpendicular to the beam axis**.  

- You can picture shear as a stack of playing cards where layers **try to slide** past each other.  

- In a beam, one part of the cross-section wants to slide relative to the next, creating **internal shear stresses**.







**Critical section for shear – $d_v$**







- The design shear check is taken at a distance **$d_v$ from the face of the support**.  

- At this section we take the **design shear $V^{\ast}$**, ignoring any distributed load between the support and $d_v$.  

- If significant concentrated loads fall inside this region, the behaviour is closer to a **strut-and-tie / deep beam** and a STM model is required.  

- AS 3600 defines effective shear depth  



  $$d_v = \max\left(0.72D,\;0.9d_0\right)$$  



  where $d_0$ is the depth to the centroid of the **tension reinforcement** in the tensile zone.

"""
                    )

    with page_title_placeholder:
        # This page's runtime shell contributes one additional Streamlit row
        # before its content. Offset that shell row so the visible heading
        # aligns with the Bending-page reference spacing.
        render_result_page_title("Shear & Torsion", top_margin_rem=-1.25)

    debug_mode = st.sidebar.checkbox(
        "Debug session state",
        key=f"debug_state_toggle_{st.session_state.get('page_slug','page')}"
    )
    if debug_mode:
        st.sidebar.markdown("### Debug session state")

        debug_keys = [
            "page_slug",
            "actions_source",
            "inputs_actions_source",
            "loads_edit_mode",

            # load proxies
            "load_Mstar_proxy",
            "load_Vstar_proxy",
            "load_Nstar_proxy",

            # shared actions
            "uls_Mstar",
            "uls_Vstar",
            "uls_Nstar",

            # bending derived
            "Mu_star",
            "Mu_star_kNm",

            # shear derived
            "Vu_star",

            # SFD/BMD outputs
            "sfd_Mmax_abs_kNm",
            "sfd_Vmax_abs_kN",
        ]

        st.sidebar.json({
            k: st.session_state.get(k)
            for k in debug_keys
        })

    sync_callbacks = get_sync_callbacks()

    # Top summary table placeholder (for clickable summary table)
    top_summary_placeholder = st.empty()
    visualisation_placeholder = st.empty()

    render_timing_mark("shear_page.runtime.visualisation.start")
    # --- Shared visualisation viewport ---
    page_divider()

    # =====================================================
    # 1. DESIGN INPUTS (shared + local)  — SAME WIDGET CONTRACT
    # =====================================================
    render_timing_mark("shear_page.runtime.inputs.start")
    actions_mode = get_param("actions_mode", "manual")
    design_controls = is_design_governing()
    is_design_driven = actions_mode == "design"
    support_help_text = "Support condition determines the deflection coefficient k₂ used in AS 3600 deflection calculations."
    support_widget_key = get_widget_key_for_shared("defl_support_type", prefix="shear_") or "shear_defl_support_type"
    from deflection_support import (
        get_deflection_diagram_support_condition,
        _deflection_support_options_for_value,
        _governing_span_support_pair,
    )

    _sup_res = get_deflection_diagram_support_condition(st.session_state)
    support_current = _sup_res["support_type"]
    support_options = _deflection_support_options_for_value(support_current)
    if st.session_state.get(support_widget_key) != support_current:
        st.session_state[support_widget_key] = support_current

    with render_specialized_widget_rail("shear_input_scroll", 4) as (
        col_actions,
        col_geom_mat,
        col_shear_reo,
        col_shear_params,
    ):
        with st.container():
        
            # ---------- 1.1 Design Actions (left column) ----------
            with col_actions:
                prev_mode = st.session_state.get("loads_edit_mode", "ULS")
                selected_mode = st.session_state.get("loads_edit_mode", "ULS")
                selected_prefix = "sls" if selected_mode == "SLS" else "uls"
                toggle_widget_key = get_widget_key_for_shared("loads_edit_toggle", prefix="inputs_") or "inputs_loads_edit_toggle"
        
                col_title, col_info = st.columns([0.92, 0.08], gap="small")
                with col_title:
                    render_section_title("Design Actions")
                with col_info:
                    with info_i_button(
                        help_text="Source of design actions (V*, N*, T*, P*) and optional display of prestress input.",
                    ):
                        st.markdown("Source: Inputs page selection", unsafe_allow_html=True)
                        edit_sls = st.toggle(
                            "View SLS loads",
                            key=toggle_widget_key,
                            help="Toggle which load set is shown below. ULS drives bending/shear; SLS drives crack/deflection.",
                        )
        
                        selected_mode_preview = "SLS" if edit_sls else "ULS"
                        action_verb_preview = "viewing" if is_design_driven else "editing"
        
                        if not is_design_driven:
                            st.caption("Design actions: Manual")
                        else:
                            st.caption("Design actions: From SFD/BMD")
                        st.caption(f"Currently {action_verb_preview}: **{selected_mode_preview}** loads")
        
                        if "shear_include_prestress_effects_ui" not in st.session_state:
                            st.session_state["shear_include_prestress_effects_ui"] = False
                        st.toggle(
                            "Include prestress effects",
                            key="shear_include_prestress_effects_ui",
                            help="Show the P* input in Design Actions. Stored P* is unchanged; this only controls visibility.",
                        )
        
                new_mode = "SLS" if edit_sls else "ULS"
        
                if new_mode != prev_mode:
                    st.session_state["loads_edit_mode"] = prev_mode
                    save_proxies_to_active_set()
                    st.session_state["loads_edit_mode"] = new_mode
                    load_proxies_from_active_set()
                    st.session_state["inputs_load_Vstar_proxy"] = st.session_state.get("load_Vstar_proxy", 0.0)
                    st.session_state["inputs_load_Nstar_proxy"] = st.session_state.get("load_Nstar_proxy", 0.0)
                    st.session_state["inputs_load_Mstar_pos_proxy"] = st.session_state.get("load_Mstar_pos_proxy", 0.0)
                    st.session_state["inputs_load_Mstar_neg_proxy"] = st.session_state.get("load_Mstar_neg_proxy", 0.0)
                    recalc_derived_values()
                    update_results()
                else:
                    st.session_state["loads_edit_mode"] = new_mode
                selected_mode = st.session_state.get("loads_edit_mode", "ULS")
                selected_prefix = "sls" if selected_mode == "SLS" else "uls"
        
                if is_design_driven:
                    st.info("Design actions are currently driven by the Design / Teaching page and are read-only here.")
        
                display_V = float(get_param(f"{selected_prefix}_Vstar", 0.0) or 0.0)
                display_N = float(get_param(f"{selected_prefix}_Nstar", 0.0) or 0.0)
                display_T = float(get_param("Tu_star", 0.0) or 0.0)
                n_proxy_widget_key = get_widget_key_for_shared("load_Nstar_proxy", prefix="inputs_") or "inputs_load_Nstar_proxy"
                m_pos_proxy_widget_key = get_widget_key_for_shared("load_Mstar_pos_proxy", prefix="inputs_") or "inputs_load_Mstar_pos_proxy"
                m_neg_proxy_widget_key = get_widget_key_for_shared("load_Mstar_neg_proxy", prefix="inputs_") or "inputs_load_Mstar_neg_proxy"
        
                display_Mu_pos = get_param(
                    f"{selected_prefix}_Mstar_pos_manual",
                    max(0.0, get_param(f"{selected_prefix}_Mstar", 0.0)),
                )
                display_Mu_neg = get_param(
                    f"{selected_prefix}_Mstar_neg_manual",
                    max(0.0, -get_param(f"{selected_prefix}_Mstar", 0.0)),
                )
                display_P = get_param("P_star", 0.0)
        
                if design_controls:
                    if st.session_state.get("inputs_load_Vstar_proxy") != display_V:
                        st.session_state["inputs_load_Vstar_proxy"] = display_V
                    if st.session_state.get(n_proxy_widget_key) != display_N:
                        st.session_state[n_proxy_widget_key] = display_N
                    if st.session_state.get("shear_Tu_star") != display_T:
                        st.session_state["shear_Tu_star"] = display_T
                    if st.session_state.get(m_pos_proxy_widget_key) != display_Mu_pos:
                        st.session_state[m_pos_proxy_widget_key] = display_Mu_pos
                    if st.session_state.get(m_neg_proxy_widget_key) != display_Mu_neg:
                        st.session_state[m_neg_proxy_widget_key] = display_Mu_neg
                    if st.session_state.get("shear_P_star") != display_P:
                        st.session_state["shear_P_star"] = display_P
        
                Mu_star_pos_val = max(0.0, _coalesce_num(display_Mu_pos, 0.0))
                Mu_star_neg_val = max(0.0, _coalesce_num(display_Mu_neg, 0.0))
                P_star_val = _coalesce_num(display_P, 0.0)
                moment_signed_selected = float(get_param(f"{selected_prefix}_Mstar", 0.0) or 0.0)
                bending_detail_view = str(st.session_state.get("bending_detail_view", "positive") or "positive").strip().lower()
                support_current_text = str(support_current or "").strip().lower()
                show_mu_negative = (
                    ("continuous" in support_current_text)
                    or ("interior" in support_current_text)
                    or (moment_signed_selected < 0.0)
                    or (bending_detail_view == "negative")
                )
                include_prestress_effects_ui = bool(st.session_state.get("shear_include_prestress_effects_ui", False))
        
                number_row(
                    "Design shear V* (kN)",
                    "inputs_load_Vstar_proxy",
                    float(display_V),
                    sync_callbacks,
                    disabled=is_design_driven,
                    help_text="Factored shear at the section.",
                )
                number_row(
                    "Axial force N* (kN, +tension)",
                    n_proxy_widget_key,
                    float(display_N),
                    sync_callbacks,
                    disabled=is_design_driven,
                    help_text="Axial force at the section (+tension, −compression).",
                )
                number_row(
                    "Torsion T* (kNm)",
                    "shear_Tu_star",
                    float(display_T),
                    sync_callbacks,
                    disabled=is_design_driven,
                    help_text="Factored torsion at the section.",
                )
                number_row(
                    "Positive design moment Mu*+ (kNm)",
                    m_pos_proxy_widget_key,
                    Mu_star_pos_val,
                    sync_callbacks,
                    disabled=is_design_driven,
                    help_text=(
                        "Sagging bending demand magnitude. Used with shear for εₓ in the general MCFT route "
                        "(positive bending: top compression, bottom tension)."
                    ),
                )
                if show_mu_negative:
                    number_row(
                        "Negative design moment Mu*- (kNm)",
                        m_neg_proxy_widget_key,
                        Mu_star_neg_val,
                        sync_callbacks,
                        disabled=is_design_driven,
                        help_text=(
                            "Hogging bending demand magnitude. Enter as a positive number for top tension / bottom compression."
                        ),
                    )
                if include_prestress_effects_ui:
                    number_row(
                        "Prestress force P* (kN)",
                        "shear_P_star",
                        P_star_val,
                        sync_callbacks,
                        disabled=is_design_driven,
                        help_text=(
                            "Prestress / effective prestress force in the section (kN). Affects longitudinal strain εₓ in shear."
                        ),
                    )
        
                number_row(
                    "φ – strength reduction for shear",
                    "shear_phi_shear",
                    get_param("phi_shear", 0.75),
                    sync_callbacks,
                    help_text="Strength reduction factor for shear (AS 3600).",
                )
        
            # ---------- 1.2 Geometry (middle column) ----------
            with col_geom_mat:
                render_section_title("Geometry, materials & loading conditions")
        
                shape_options = ["RECT", "T", "I"]
                sec_shape_current = st.session_state.get("sec_shape", "RECT")
                if sec_shape_current not in shape_options:
                    sec_shape_current = "RECT"
        
                select_row(
                    "Section shape",
                    "shear_sec_shape",
                    shape_options,
                    sec_shape_current,
                    sync_callbacks,
                    help_text="Matches Inputs page. Controls which geometry fields are shown.",
                )
        
                # Get current values (widget key takes precedence if exists, otherwise use shared key)
                D_val = _coalesce_num(st.session_state.get("shear_D", get_param("D", 600.0)), 600.0)
                L_val = _coalesce_num(st.session_state.get("shear_L", get_param("L", 3000.0)), 3000.0)
        
                sec_shape = st.session_state.get("shear_sec_shape", st.session_state.get("sec_shape", "RECT"))
        
                if sec_shape == "RECT":
                    b_val = _coalesce_num(st.session_state.get("shear_b", get_param("b", 400.0)), 400.0)
                    number_row(
                        "Width b (mm)",
                        "shear_b",
                        b_val,
                        sync_callbacks,
                        help_text="Shared with Inputs tab.",
                    )
                elif sec_shape == "T":
                    bf_val = _coalesce_num(st.session_state.get("shear_bf", get_param("bf", 600.0)), 600.0)
                    tf_val = _coalesce_num(st.session_state.get("shear_tf", get_param("tf", 120.0)), 120.0)
                    bw_val = _coalesce_num(st.session_state.get("shear_bw", get_param("bw", 300.0)), 300.0)
        
                    number_row("Flange width bf (mm)", "shear_bf", bf_val, sync_callbacks)
                    number_row("Flange thickness tf (mm)", "shear_tf", tf_val, sync_callbacks)
                    number_row("Web width bw (mm)", "shear_bw", bw_val, sync_callbacks)
                elif sec_shape == "I":
                    bf_val = _coalesce_num(st.session_state.get("shear_bf", get_param("bf", 600.0)), 600.0)
                    tf_val = _coalesce_num(st.session_state.get("shear_tf", get_param("tf", 120.0)), 120.0)
                    tw_val = _coalesce_num(st.session_state.get("shear_tw", get_param("tw", 200.0)), 200.0)
        
                    number_row("Top flange width bf (mm)", "shear_bf", bf_val, sync_callbacks)
                    number_row("Top flange thickness tf (mm)", "shear_tf", tf_val, sync_callbacks)
                    number_row("Web thickness tw (mm)", "shear_tw", tw_val, sync_callbacks)
        
                number_row(
                    "Depth D (mm)",
                    "shear_D",
                    D_val,
                    sync_callbacks,
                    help_text="Overall section depth, shared with Inputs.",
                )
                number_row(
                    "Span L (mm)",
                    "shear_L",
                    L_val,
                    sync_callbacks,
                    help_text="Clear span or design span for this section.",
                )
        
                if design_controls:
                    st.info("🔒 Support condition is controlled by the Design page. Edit it there.")
                select_row(
                    "Support condition (k₂)",
                    support_widget_key,
                    support_options,
                    support_current,
                    sync_callbacks,
                    help_text=support_help_text,
                    disabled=design_controls,
                )
        
            # ---------- 1.3 Materials (right column) ----------
            with col_geom_mat:
                number_row(
                    "Concrete strength f'c (MPa)",
                    "shear_fc",
                    get_param("fc", 40.0),
                    sync_callbacks,
                    help_text="Concrete compressive strength (AS 3600).",
                )
                number_row(
                    "Steel yield f_sy (MPa)",
                    "shear_fsy",
                    get_param("fsy", 500.0),
                    sync_callbacks,
                    help_text="Yield stress of longitudinal & shear reinforcement.",
                )
        
        
        
            with col_shear_reo:
                _auto_spacing_mode = bool(get_param("shear_auto_design", False))
                render_section_title("Shear reinforcement & section parameters")
                
                # Widget keys (resolved via TAB_KEYS)
                w_lig_d = get_widget_key_for_shared("lig_d", prefix="shear_") or "shear_lig_d"
                w_lig_legs = get_widget_key_for_shared("lig_legs", prefix="shear_") or "shear_lig_legs"
                w_s_lig = get_widget_key_for_shared("s_lig", prefix="shear_") or "shear_s_lig"
                
                # Read shared values (do NOT write shared keys)
                lig_d_val = float(st.session_state.get("lig_d", 10.0))
                lig_legs_val = float(st.session_state.get("lig_legs", 2))
                canonical_s = float(st.session_state.get("s_lig", 200.0) or 200.0)
                # Keep shear link widget aligned with shared provided spacing (canonical user input; not envelope spacing).
                if _auto_spacing_mode:
                    if st.session_state.get(w_s_lig) != canonical_s:
                        st.session_state[w_s_lig] = float(canonical_s)
                    s_lig_val = float(canonical_s)
                else:
                    s_lig_val = float(st.session_state.get(w_s_lig, canonical_s) or canonical_s)
                
                # Option lists for dropdowns
                REO_BAR_DIAS = [10, 12, 16, 20, 24, 28, 32, 36, 40]
                
                select_row(
                    "Link Ø (mm)",
                    w_lig_d,
                    REO_BAR_DIAS,
                    int(lig_d_val),
                    sync_callbacks,
                    help_text="Nominal diameter of shear links (mm).",
                )
                
                select_row(
                    "No. of legs",
                    w_lig_legs,
                    REO_SHEAR_LEGS_OPTIONS,
                    int(lig_legs_val),
                    sync_callbacks,
                    help_text="Number of legs per shear link. Use 0 for no links; 2 or more for active shear reinforcement.",
                )
                
                number_row(
                    "Provided link spacing (mm)",
                    w_s_lig,
                    s_lig_val,
                    sync_callbacks,
                    help_text="Centre-to-centre spacing of shear links you provide (mm). Envelope-governed spacings for checks appear under Check 10.",
                    disabled=False,
                )
        
            with col_shear_params:
                render_section_title("Ducts & prestress voids")
                
                number_row(
                    "Number of ducts crossing web",
                    "shear_n_ducts",
                    0.0,
                    sync_callbacks,
                    help_text="Number of prestressing ducts crossing the web.",
                )
                
                number_row(
                    "Duct diameter (mm)",
                    "shear_duct_dia",
                    0.0,
                    sync_callbacks,
                    help_text="Diameter of each prestressing duct.",
                )
                
                # Compute sum_duct internally from the two inputs
                n_ducts = get_param("n_ducts", 0.0)
                duct_dia = get_param("duct_dia", 0.0)
        
                sum_duct = duct_area_mm2(n_ducts, duct_dia)
                # Store computed value in session state for use in calculations
                st.session_state["shear_sum_duct"] = sum_duct
                
                # k_d factor options (matching shared state format)
                KD_OPTIONS = [
                    "None (no ducts in web)",
                    "0.5 – steel ducts, grouted",
                    "0.8 – plastic ducts, grouted",
                    "1.2 – ungrouted ducts",
                ]
                # Mapping from option string to numeric k_d value
                KD_VALUE_MAP = {
                    "None (no ducts in web)": 0.0,
                    "0.5 – steel ducts, grouted": 0.5,
                    "0.8 – plastic ducts, grouted": 0.8,
                    "1.2 – ungrouted ducts": 1.2,
                }
                
                # Get widget key for k_d_option
                w_kd = get_widget_key_for_shared("k_d_option", prefix="shear_") or "shear_k_d_option"
                kd_option_val = get_param("k_d_option", "None (no ducts in web)")
                if kd_option_val not in KD_OPTIONS:
                    kd_option_val = "None (no ducts in web)"
                
                select_row(
                    "k_d factor for prestressing ducts",
                    w_kd,
                    KD_OPTIONS,
                    kd_option_val,
                    sync_callbacks,
                    help_text="k_d factor for prestressing ducts (AS 3600).",
                )
                
                # Convert selected option to numeric k_d value for calculations
                kd_option_selected = st.session_state.get(w_kd, kd_option_val)
                k_d = KD_VALUE_MAP.get(kd_option_selected, 0.0)
            
            with col_shear_reo:
                number_row(
                    "Maximum aggregate size d_g (mm)",
                    "shear_d_g",
                    20.0,
                    sync_callbacks,
                    help_text="Maximum aggregate size for k_v calculation.",
                )
                
                # k_v method options
                KV_METHOD_OPTIONS = [
                    "General εₓ-based (Cl. 8.2.4.2)",
                    "Simplified non-prestressed (Cl. 8.2.4.3)",
                ]
                
                # Get widget key for k_v_method
                w_kv_method = get_widget_key_for_shared("k_v_method", prefix="shear_") or "shear_k_v_method"
                kv_method_val = get_param("k_v_method", "General εₓ-based (Cl. 8.2.4.2)")
                if kv_method_val not in KV_METHOD_OPTIONS:
                    kv_method_val = "General εₓ-based (Cl. 8.2.4.2)"
                
                select_row(
                    "k_v method",
                    w_kv_method,
                    KV_METHOD_OPTIONS,
                    kv_method_val,
                    sync_callbacks,
                    help_text=(
                        "Simplified (Cl. 8.2.4.3) vs general εx-based (Cl. 8.2.4.2). "
                        "Open the page ℹ️ INFO expander for when to use each and why."
                    ),
                )
        
                # Determine if general method is used
                method = st.session_state.get(w_kv_method, kv_method_val)
                use_general_kv = method.startswith("General")
        
    page_divider()

    # -------------------------------------------------
    # Pull shared values for calculations
    # -------------------------------------------------
    shear_bundle = build_shear_calc_bundle_from_state(st.session_state)
    live_shear_state = shear_bundle["live_state"]
    shear_results = shear_bundle["results"]
    phi = float(shear_bundle["phi"])
    k_d = float(shear_bundle["k_d"])
    use_general_kv = bool(shear_bundle["use_general_kv"])

    b = live_shear_state["b"]
    D = live_shear_state["D"]
    d = live_shear_state["d"]
    fc = live_shear_state["fc"]
    fsy = live_shear_state["fsy"]
    Ec = live_shear_state["Ec"]
    Es = live_shear_state["Es"]
    M_star = live_shear_state["Mu"]
    V_star = live_shear_state["Vu"]
    T_star = live_shear_state["Tu"]
    N_star = live_shear_state["Nu"]
    P_v = live_shear_state["Pu"]
    lig_d = live_shear_state["lig_d"]
    legs = live_shear_state["lig_legs"]
    s_lig = live_shear_state["s_lig"]
    A_st = live_shear_state["A_st"]
    A_pt = live_shear_state["A_pt"]
    f_po = live_shear_state["f_po"]
    A_ct = live_shear_state["A_ct"]
    d_g = live_shear_state["d_g"]
    sigma_cp = live_shear_state["sigma_cp"]
    sum_duct = live_shear_state["sum_duct"]

    if not (b and D and d):
        st.error("Geometry (b, D, d) not fully defined – check Inputs / Bending tab.")
        return

    # =====================================================
    # 2. COMPUTE ALL VALUES (before tabs, so summary table can access them)
    # =====================================================
    # Read θ from shared state (read-only, no widget)
    theta_deg = float(get_param("crack_theta_deg", 45.0))

    # Pull torsion screening directly from shear_core results
    torsion_required = bool(getattr(shear_results, "torsion_required", False))
    torsion_required_limit = float(getattr(shear_results, "torsion_required_limit", 0.0) or 0.0)
    Tcr_kNm = float(getattr(shear_results, "Tcr_kNm", 0.0) or 0.0)

    b_used = float(getattr(shear_results, "b_used", b) or b)
    D_used = float(getattr(shear_results, "D_used", D) or D)
    torsion_geometry_fallback = torsion_section_geometry_values(b_used, D_used)
    A_cp = float(getattr(shear_results, "A_cp", torsion_geometry_fallback["A_cp"]) or 0.0)
    u_c = float(getattr(shear_results, "u_c", torsion_geometry_fallback["u_c"]) or 0.0)
    Ao = float(getattr(shear_results, "Ao", torsion_geometry_fallback["Ao"]) or 0.0)
    uh = float(getattr(shear_results, "uh", torsion_geometry_fallback["uh"]) or 0.0)
    A_oh = float(getattr(shear_results, "A_oh", torsion_geometry_fallback["A_oh"]) or 0.0)

    step1_req = ">" if torsion_required else "\\le"
    step1_text = (
        "required" if torsion_required else "not required (strength check only)"
    )
    torsion_status = "pass" if not torsion_required else "fail"
    
    # Check 2: Equivalent shear
    torsion_eq_kN = float(getattr(shear_results, "Vt_eq_kN", 0.0) or 0.0)
    V_eq = float(getattr(shear_results, "V_eq", abs(V_star)) or abs(V_star))
    shear_display_scalars = shear_check_display_scalars(
        T_star_kNm=T_star,
        D_mm=D,
        d_mm=d,
        fc_mpa=fc,
        Vuc_kN=float(getattr(shear_results, "Vuc_kN", 0.0) or 0.0),
        Vus_kN=float(getattr(shear_results, "Vus_kN", 0.0) or 0.0),
        P_v_kN=P_v,
        phi=phi,
        V_eq_kN=V_eq,
    )
    T_star_Nmm = shear_display_scalars["T_star_Nmm"]
    
    # Check 3: Effective section parameters
    lig_d = 10.0 if lig_d is None else float(lig_d)
    legs = 2.0 if legs is None else float(legs)
    s = 200.0 if s_lig is None else float(s_lig)
    
    Asv = float(getattr(shear_results, "Asv", stirrup_area_mm2(legs, lig_d)) or 0.0)
    f_syv = fsy

    b_v = float(getattr(shear_results, "b_v", b - k_d * sum_duct) or 0.0)
    d_v = float(getattr(shear_results, "d_v", effective_shear_depth_mm(D, d)) or 0.0)
    
    dv_1 = shear_display_scalars["dv_1"]
    dv_2 = shear_display_scalars["dv_2"]
    
    # Check 4: Longitudinal strain εx
    strain_fallback = longitudinal_strain_fallback_values(
        M_star_kNm=M_star,
        V_star_kN=V_star,
        T_star_kNm=T_star,
        P_v_kN=P_v,
        N_star_kN=N_star,
        d_v_mm=d_v,
        uh_mm=uh,
        Ao_mm2=Ao,
        Es_mpa=Es,
        Ec_mpa=Ec,
        A_st_mm2=A_st,
        A_pt_mm2=A_pt,
        f_po_mpa=f_po,
        A_ct_mm2=A_ct,
    )
    M_star_Nmm = float(strain_fallback["M_star_Nmm"])
    term_M = float(strain_fallback["term_M"])
    Vprime_kN = float(strain_fallback["Vprime_kN"])
    Vprime_N = float(strain_fallback["Vprime_N"])
    torsion_N = float(strain_fallback["torsion_N"])
    sqrt_inner = float(strain_fallback["sqrt_inner"])
    N_star_N = float(strain_fallback["N_star_N"])
    A_pt_fpo_N = float(strain_fallback["A_pt_fpo_N"])
    numerator_1 = float(strain_fallback["numerator_1"])
    Ep = float(strain_fallback["Ep"])
    denom1 = float(strain_fallback["denom1"])
    eps_x_1 = float(strain_fallback["eps_x_1"])
    V_abs_N = float(strain_fallback["V_abs_N"])
    numerator_2 = float(strain_fallback["numerator_2"])
    denom2 = float(strain_fallback["denom2"])
    eps_x_2 = float(strain_fallback["eps_x_2"])
    
    if strain_fallback["use_equation_1"]:
        eps_x_raw = float(strain_fallback["eps_x_raw"])
        eq_used = "Equation (1) – mid-depth in tension"
    else:
        eps_x_raw = float(strain_fallback["eps_x_raw"])
        eq_used = "Equation (2) – mid-depth in slight compression"
    
    eps_x = float(strain_fallback["eps_x"])
    mcft = mcft_kv_theta_values(
        use_general_kv=use_general_kv,
        fc_mpa=fc,
        d_g_mm=d_g,
        eps_x=eps_x,
        Asv_mm2=Asv,
        s_mm=s,
        b_v_mm=b_v,
        f_syv_mpa=f_syv,
        d_v_mm=d_v,
    )
    
    # Check 5: k_v and θ_v
    if use_general_kv:
        if fc <= 65:
            k_dg = float(mcft["k_dg"])
            k_dg = float(mcft["k_dg"])
            if d_g >= 16:
                k_dg = float(mcft["k_dg"])
        else:
            k_dg = float(mcft["k_dg"])
        
        Asv_over_s = float(mcft["Asv_over_s"])
        Asv_min_over_s = float(mcft["Asv_min_over_s"])
        
        if mcft["low_stirrup_ratio"]:
            k_v = float(mcft["k_v"])
            kv_case = "general MCFT with **low stirrup ratio** ($A_{sv}/s < (A_{sv}/s)_{min}$)"
        else:
            k_v = float(mcft["k_v"])
            kv_case = "general MCFT with **adequate stirrup ratio**"
        
        theta_v_deg = float(mcft["theta_v_deg"])
    else:
        if mcft["low_stirrup_ratio"]:
            k_v = float(mcft["k_v"])
            kv_case = "simplified non-prestressed – **low stirrup ratio**"
        else:
            k_v = float(mcft["k_v"])
            kv_case = "simplified non-prestressed – **minimum stirrups provided**"
        theta_v_deg = float(mcft["theta_v_deg"])
        k_dg = float(mcft["k_dg"])
    
    eps_x = float(getattr(shear_results, "eps_x", eps_x) or 0.0)
    k_v = float(getattr(shear_results, "k_v", k_v) or 0.0)
    theta_v_deg = float(getattr(shear_results, "theta_v_deg", theta_v_deg) or 0.0)
    theta_v_rad = float(getattr(shear_results, "theta_v_rad", math.radians(theta_v_deg)) or 0.0)

    # The visualisation placeholder is created before the input rail, but the
    # actual diagram work happens here. Keep a separate measured boundary so
    # route timings do not attribute the widget rail to the diagram.
    render_timing_mark("shear_page.runtime.inputs.end")
    render_timing_mark("shear_page.runtime.visualisation.render.start")
    with visualisation_placeholder.container():
        _render_shear_visualisation_block(theta_v_deg=shear_results.theta_v_deg)
    render_timing_mark("shear_page.runtime.visualisation.render.end")
    
    # Check 6: Concrete shear contribution
    sqrt_fc_limited = float(getattr(shear_results, "sqrt_fc_limited", shear_display_scalars["sqrt_fc_limited"]) or 0.0)
    Vuc_kN = float(getattr(shear_results, "Vuc_kN", 0.0) or 0.0)
    
    # Check 7: Steel shear contribution
    Vus_kN = float(getattr(shear_results, "Vus_kN", 0.0) or 0.0)
    
    # Check 8: Combined shear strength
    Vu_total_kN = float(getattr(shear_results, "Vu_total_kN", shear_display_scalars["Vu_total_kN"]) or 0.0)
    phi_Vu = float(getattr(shear_results, "phi_Vu", shear_display_scalars["phi_Vu"]) or 0.0)
    shear_ok = bool(getattr(shear_results, "shear_ok", shear_display_scalars["shear_ok"]))
    shear_status = "pass" if shear_ok else "fail"
    
    # Check 9: Web crushing
    theta_1_deg = 90.0
    theta_1_rad = math.radians(theta_1_deg)
    cot_theta_v = cot(theta_v_rad)
    cot_theta_1 = cot(theta_1_rad)
    
    Vu_max_kN = float(getattr(shear_results, "Vu_max_kN", 0.0) or 0.0)
    web_crushing_fallback = web_crushing_fallback_values(
        V_star_kN=V_star,
        T_star_kNm=T_star,
        uh_mm=uh,
        A_oh_mm2=A_oh,
        b_v_mm=b_v,
        d_v_mm=d_v,
        phi=phi,
        Vu_max_kN=Vu_max_kN,
    )
    Vu_max_N = float(web_crushing_fallback["Vu_max_N"])
    V_star_N = float(web_crushing_fallback["V_star_N"])
    term_V = float(web_crushing_fallback["term_V"])
    term_T = float(web_crushing_fallback["term_T"])
    
    LHS = float(getattr(shear_results, "LHS", web_crushing_fallback["LHS"]) or 0.0)
    RHS = float(getattr(shear_results, "RHS", web_crushing_fallback["RHS"]) or 0.0)
    
    web_ok = bool(getattr(shear_results, "web_ok", web_crushing_fallback["web_ok"]))
    web_status = "pass" if web_ok else "fail"
    
    # Check 11: Minimum shear reinforcement (tab 3)
    check11_reinforcement = shear_reinforcement_spacing_check_values(
        Asv_mm2=Asv,
        s_lig_mm=s,
        fc_mpa=fc,
        b_v_mm=b_v,
        f_syv_mpa=f_syv,
        D_mm=D,
    )
    Asv_over_s_check11 = check11_reinforcement["Asv_over_s"]
    Asv_min_over_s_check11 = check11_reinforcement["Asv_min_over_s"]
    min_shear_ok = check11_reinforcement["min_shear_ok"]
    min_shear_status = "pass" if min_shear_ok else "fail"

    # =====================================================
    # 3. SHEAR DESIGN CHECKS UI (organized into tabs)
    # =====================================================
    page_divider()
    render_timing_mark("shear_page.runtime.checks.start")
    render_section_title("Shear design checks")
    
    apply_step_summary_expander_css()  # same pattern as bending
    
    # Streamlit st.tabs renders every tab body on every rerun.  Keep the same
    # visible tab treatment, but use a styled radio as the server-side active
    # tab boundary so inactive check diagrams are not assembled at all.
    _jump_tab = st.session_state.get(JUMP_NAV_TAB_KEY)
    if _jump_tab in SHEAR_CHECK_TAB_LABELS:
        st.session_state[SHEAR_CHECK_TAB_KEY] = _jump_tab
    elif st.session_state.get(SHEAR_CHECK_TAB_KEY) not in SHEAR_CHECK_TAB_LABELS:
        st.session_state[SHEAR_CHECK_TAB_KEY] = SHEAR_CHECK_TAB_LABELS[0]

    st.markdown(
        """
<style>
div[data-testid="stVerticalBlock"]:has(#shear-check-tabs-anchor) div[role="radiogroup"] {
    display: flex !important;
    align-items: center !important;
    gap: 18px !important;
    border-bottom: 1px solid rgba(49,51,63,0.20) !important;
    padding-bottom: 4px !important;
    margin-bottom: 0.35rem !important;
}
div[data-testid="stVerticalBlock"]:has(#shear-check-tabs-anchor) div[role="radiogroup"] > label {
    margin: 0 !important;
    padding: 6px 2px !important;
    background: transparent !important;
    border: none !important;
    border-bottom: 2px solid transparent !important;
    border-radius: 0 !important;
    box-shadow: none !important;
    cursor: pointer !important;
    font-weight: 500 !important;
}
div[data-testid="stVerticalBlock"]:has(#shear-check-tabs-anchor) div[role="radiogroup"] > label input[type="radio"],
div[data-testid="stVerticalBlock"]:has(#shear-check-tabs-anchor) div[role="radiogroup"] > label > div:first-child,
div[data-testid="stVerticalBlock"]:has(#shear-check-tabs-anchor) div[role="radiogroup"] > label > span:first-child {
    display: none !important;
}
div[data-testid="stVerticalBlock"]:has(#shear-check-tabs-anchor) div[role="radiogroup"] > label:has(input:checked),
div[data-testid="stVerticalBlock"]:has(#shear-check-tabs-anchor) div[role="radiogroup"] > label[aria-checked="true"] {
    border-bottom: 2px solid #ff4b4b !important;
    font-weight: 600 !important;
}
div[data-testid="stVerticalBlock"]:has(#shear-check-tabs-anchor) div[role="radiogroup"] > label:hover {
    background: transparent !important;
}
div[data-testid="stVerticalBlock"]:has(#shear-check-tabs-anchor) div[role="radiogroup"] > label * {
    margin: 0 !important;
    padding: 0 !important;
}
</style>
""",
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div id="shear-check-tabs-anchor" style="height:0;line-height:0;font-size:0;margin:0;padding:0;" aria-hidden="true"></div>',
        unsafe_allow_html=True,
    )
    active_shear_tab = st.radio(
        "Shear design checks",
        options=SHEAR_CHECK_TAB_LABELS,
        horizontal=True,
        key=SHEAR_CHECK_TAB_KEY,
        label_visibility="collapsed",
    )
    st.session_state.pop(JUMP_NAV_TAB_KEY, None)
    tab1, tab2, tab3 = st.container(), st.container(), st.container()
    
    # =====================================================
    # TAB 1: Torsion + dimensions
    # =====================================================
    render_timing_mark("shear_page.runtime.checks.tab1.start")
    st.session_state["_shear_skip_inactive_tab"] = active_shear_tab != SHEAR_CHECK_TAB_LABELS[0]
    with tab1:
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

    # =====================================================
    render_timing_mark("shear_page.runtime.checks.tab1.end")
    render_timing_mark("shear_page.runtime.checks.tab2.start")
    # TAB 2: MCFT and strength checks
    # =====================================================
    st.session_state["_shear_skip_inactive_tab"] = active_shear_tab != SHEAR_CHECK_TAB_LABELS[1]
    with tab2:
        st.markdown(
            """
<style>
.mcft-compact-block p {
    margin-bottom: 0.2rem;
}
.mcft-compact-block {
    margin-top: 0;
    padding-top: 0;
}
/* MCFT tab: theory expander → subhead + ℹ + principal-stress diagram with ~no vertical gap */
div[data-testid="stExpander"]:has(#mcft-theory-expander-tail) {
    margin-bottom: 0 !important;
}
div[data-testid="stExpander"]:has(#mcft-theory-expander-tail) [data-testid="stExpanderDetails"] {
    padding-top: 0.3rem !important;
    padding-bottom: 0.08rem !important;
}
div[data-testid="stElementContainer"]:has(div.mcft-compact-block) {
    margin-top: 0 !important;
    margin-bottom: 0 !important;
    padding-top: 0 !important;
    padding-bottom: 0 !important;
}
/* Anchor-only block before MCFT diagram (spacing for following popover row) */
div[data-testid="stElementContainer"]:has(#mcft-before-display-popover) {
    margin-top: 0 !important;
    margin-bottom: -0.35rem !important;
    padding-top: 0 !important;
    padding-bottom: 0 !important;
}
div[data-testid="stElementContainer"]:has(#mcft-before-display-popover)
    + div[data-testid="stElementContainer"] {
    margin-top: -1.75rem !important;
    margin-bottom: 0 !important;
    padding-top: 0 !important;
    padding-bottom: 0 !important;
}
div[data-testid="stElementContainer"]:has(#mcft-before-display-popover)
    + div[data-testid="stElementContainer"] [data-testid="stPopover"] {
    margin: 0 !important;
    padding: 0 !important;
}
div[data-testid="stElementContainer"]:has(#mcft-before-display-popover)
    + div[data-testid="stElementContainer"] button {
    margin: 0 !important;
    padding-top: 0 !important;
    padding-bottom: 0 !important;
    min-height: 0 !important;
    line-height: 1 !important;
}
div[data-testid="stElementContainer"]:has(#mcft-before-stress-plot) {
    margin-top: -1.75rem !important;
    margin-bottom: 0 !important;
    padding-top: 0 !important;
    padding-bottom: 0 !important;
}
div[data-testid="stElementContainer"]:has(#mcft-before-stress-plot)
    + div[data-testid="stElementContainer"],
div[data-testid="stElementContainer"]:has(#mcft-before-stress-plot)
    + div + div[data-testid="stElementContainer"] {
    margin-top: 0 !important;
    margin-bottom: 0 !important;
    padding-top: 0 !important;
    padding-bottom: 0 !important;
}
/* _render_centered_shear_plotly: style row + wrapper + plotly */
div[data-testid="stElementContainer"]:has(#mcft-before-stress-plot)
    ~ div[data-testid="stElementContainer"]:has(#shear-plot-wrap-shear_behaviour_mcft_single) {
    margin-top: -1.75rem !important;
    padding-top: 0 !important;
}
div[data-testid="stElementContainer"]:has(#shear-plot-wrap-shear_behaviour_mcft_single) {
    margin-top: -1.75rem !important;
    padding-top: 0 !important;
}
div[data-testid="stElementContainer"]:has(#shear-plot-wrap-shear_behaviour_mcft_single) [data-testid="stPlotlyChart"] {
    margin-top: -0.35rem !important;
    padding-top: 0 !important;
}
#shear-plot-wrap-shear_behaviour_mcft_single {
    margin-top: -0.35rem !important;
    padding-top: 0 !important;
}
</style>
""",
            unsafe_allow_html=True,
        )
        # These explanatory/behaviour diagrams are detailed MCFT content. The
        # existing breakdown toggle is the explicit user-controlled boundary;
        # do not build several Plotly figures on every route render when the
        # detailed view is hidden.
        if active_shear_tab == SHEAR_CHECK_TAB_LABELS[1]:
            st.session_state.setdefault("show_mcft_breakdown", False)
            show_mcft_breakdown = bool(st.session_state.get("show_mcft_breakdown", False))
            if show_mcft_breakdown:
                _render_principal_stress_directions_explainer()
                st.markdown('<div class="mcft-compact-block">', unsafe_allow_html=True)
                # Popover anchor (no visible subhead; layout CSS targets #mcft-before-display-popover).
                st.markdown(
                    """
<div id="mcft-before-display-popover" style="height:0;line-height:0;font-size:0;margin:0;padding:0;" aria-hidden="true"></div>
""",
                    unsafe_allow_html=True,
                )
                _render_shear_behaviour_diagrams(theta_v_deg=shear_results.theta_v_deg)
                st.markdown("</div>", unsafe_allow_html=True)
            else:
                st.caption('Detailed MCFT diagrams are hidden. Enable "Show detailed MCFT breakdown" to display them.')

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

- $E_c = 4700\sqrt{{f'_c}} = 4700\sqrt{{{fc:.1f}}} = {_fmt(Ec,0)}$ MPa  
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
            _render_plotly_in_mcft_column(fig_force, chart_key="shear_mcft_diagram_force")

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
            _render_plotly_in_mcft_column(fig_strain, chart_key="shear_mcft_diagram_strain")

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
        canonical_theta_v_deg = float(getattr(shear_results, "theta_v_deg", theta_v_deg))
        canonical_k_v = float(getattr(shear_results, "k_v", k_v))
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
*Purpose: Combine concrete and steel contributions and check $\phi V_u$ against $V_{{eq}}^*$.*  



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
    render_timing_mark("shear_page.runtime.checks.tab2.end")
    render_timing_mark("shear_page.runtime.checks.tab3.start")
    # TAB 3: Shear reinforcement checks
    # =====================================================
    st.session_state["_shear_skip_inactive_tab"] = active_shear_tab != SHEAR_CHECK_TAB_LABELS[2]
    with tab3:
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

    render_timing_mark("shear_page.runtime.checks.end")

    render_timing_mark("shear_page.runtime.checks.tab3.end")
    st.session_state["_shear_skip_inactive_tab"] = False

    # =======================================================
    # 9. SUMMARY TABLE + PUSH RESULTS
    # =======================================================
    render_timing_mark("shear_page.runtime.summary.start")
    # Note: torsion_required, V_eq, phi_Vu, etc. are computed inside tabs but need to be accessible here
    # They are already computed in tab_dim (torsion_required, V_eq) and tab_reinf (phi_Vu, shear_ok)
    # We need to ensure these are available at module scope or recompute them here
    # For now, we'll use the values computed in the tabs (they should be in scope)
    shear_pack = build_shear_check_rows_from_state(st.session_state)
    rows_summary = build_shear_legacy_summary_rows(shear_pack.get("rows") or [])
    summary_util_raw = shear_pack.get("summary_util")
    try:
        summary_util = float(summary_util_raw)
    except (TypeError, ValueError):
        summary_util = math.nan

    # Publish key shear results for Inputs summary
    shear_util = summary_util
    update_results(
        phi_Vu_cap=float(shear_pack.get("summary_phiVu_kN") or 0.0),
        Vu_utilisation=float(shear_util) if shear_util is not None and not math.isnan(shear_util) else 0.0,
    )

    rows_summary_full = rows_summary
    ROWS_FULL = build_shear_clickable_summary_rows(rows_summary_full)
    update_results("shear", {"rows": ROWS_FULL})

    # Render clickable summary table at the top (using placeholder created early)
    # Note: This renders at the end but the placeholder was created at the top
    with top_summary_placeholder.container():
        render_page_explainer_expander(_render_shear_explainer)
        if "show_mcft_breakdown" not in st.session_state:
            st.session_state["show_mcft_breakdown"] = False
        show_mcft_breakdown = st.toggle(
            "Show detailed MCFT breakdown",
            key="show_mcft_breakdown",
            help="Show intermediate MCFT shear calculation rows such as strain, θ_v, k_v, Vuc and Vus.",
        )
        display_rows = filter_shear_summary_rows(
            rows_summary_full,
            show_mcft_breakdown=show_mcft_breakdown,
        )
        ROWS_DISPLAY = build_shear_clickable_summary_rows(display_rows)
        render_clickable_summary_table(ROWS_DISPLAY, key_prefix="shear_summary")
        if not show_mcft_breakdown:
            st.caption(
                'Intermediate MCFT calculation rows hidden. Enable "Show detailed MCFT breakdown" to view.'
            )
        bind_summary_clicks()

    render_timing_mark("shear_page.runtime.summary.end")

    # Cross-page jump scroll (Inputs summary → shear/torsion calc anchors)
    from jump_nav import scroll_to_jump_after_render

    scroll_to_jump_after_render()
    render_timing_mark("shear_page.runtime.end")


if __name__ == "__main__":
    render_shear()
