import math
import os
import json
import time
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import streamlit.components.v1 as components

from state_and_helpers import (
    get_param,
    get_sync_callbacks,
    resolve_design_actions,
    update_results,
    get_widget_key_for_shared,
    TAB_KEYS,
    load_proxies_from_active_set,
    save_proxies_to_active_set,
    recalc_derived_values,
    is_design_governing,
)
from shear_diagrams import (
    build_torsion_plotly_figure,
    plot_shear_torsion_section_2d,
    plot_shear_step3_section_params_plotly,
    make_mcft_longitudinal_strain_profile_fig,
)
from shear_visuals import (
    build_shear_behaviour_figure,
    build_shear_cross_section_figure,
    build_shear_side_view_figure,
)
from shear_core import derive_eps_top_bot_for_step4_diagram
from torsion_diagrams import plot_torsion_prism_3d

# Shared helpers (same contract as Inputs/Bending)
from widgets_helpers import apply_global_widget_css, apply_result_page_css, apply_calcbox_css, number_row, select_row, calcbox, clickable_calcbox, render_step, apply_step_summary_expander_css, info_i_button, page_divider, render_page_explainer_expander, render_section_title, render_result_page_title
from step_ui import render_expandable_step
from ui_seamless_steps import render_clickable_summary_table, bind_summary_clicks
from shear_checks_helpers import (
    build_live_canonical_shear_state,
    build_shear_calc_bundle_from_state,
    build_shear_check_rows_from_state,
)

# region agent log
def _dbg_log(payload: dict) -> None:
    try:
        with open(
            "/Users/jonathonleggo/Library/CloudStorage/OneDrive-Personal/Documents/GitHub/blank-app/.cursor/debug.log",
            "a",
            encoding="utf-8",
        ) as _f:
            _f.write(json.dumps(payload) + "\n")
    except Exception:
        pass
# endregion


def _agent_debug_log(message: str, data: dict | None = None, *, location: str, hypothesis_id: str) -> None:
    _dbg_log(
        {
            "sessionId": "debug-session",
            "runId": "live-shear",
            "hypothesisId": hypothesis_id,
            "location": location,
            "message": message,
            "data": data or {},
            "timestamp": int(time.time() * 1000),
        }
    )


def _coalesce_num(v, default: float) -> float:
    """Return default only if v is None (preserves 0)."""
    return default if v is None else float(v)


# ------------------------------------------------------------
#  Helper functions for diagrams
# ------------------------------------------------------------

SHEAR_VISUAL_HEIGHT_PX = 420
SHEAR_VISUAL_MAX_WIDTH_PX = 760
SHEAR_VISUAL_CONFIG = {
    "displayModeBar": False,
    "responsive": True,
}


def _standardise_shear_visual_layout(fig, *, title_pad_t: int = 28):
    fig.update_layout(
        autosize=True,
        height=SHEAR_VISUAL_HEIGHT_PX,
        margin=dict(l=10, r=10, t=title_pad_t, b=10),
    )
    return fig


def _render_centered_shear_plotly(
    fig,
    *,
    chart_key: str,
    max_width_px: int = SHEAR_VISUAL_MAX_WIDTH_PX,
    height_px: int = SHEAR_VISUAL_HEIGHT_PX,
    config: dict | None = None,
):
    fig = _standardise_shear_visual_layout(fig)
    fig.update_layout(height=int(height_px))
    wrapper_id = f"shear-plot-wrap-{chart_key}"

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
        }}
        #{wrapper_id} > div {{
            width: min(100%, {max_width_px}px);
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(f'<div id="{wrapper_id}"><div>', unsafe_allow_html=True)
    st.plotly_chart(
        fig,
        use_container_width=True,
        key=chart_key,
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


def _extract_fingerprint_value(fingerprint, key: str):
    if isinstance(fingerprint, dict):
        return fingerprint.get(key)
    if isinstance(fingerprint, (list, tuple)):
        for item in fingerprint:
            if isinstance(item, (list, tuple)) and len(item) == 2 and item[0] == key:
                return item[1]
    return None


def _render_shear_cross_section():
    fig = build_shear_cross_section_figure()
    section_fig = _standardise_shear_visual_layout(fig)
    _render_centered_shear_plotly(
        section_fig,
        chart_key="shear_section_diagram",
        max_width_px=SHEAR_VISUAL_MAX_WIDTH_PX,
    )


def _render_shear_side_view():
    fig = build_shear_side_view_figure()
    _render_centered_shear_plotly(
        fig,
        chart_key="shear_side_view_diagram",
    )


def _render_animated_plotly_figure(fig: go.Figure, *, height: int | None = None) -> None:
    plot_html = fig.to_html(
        full_html=False,
        include_plotlyjs=True,
        config={"displayModeBar": False, "responsive": True},
        default_width="100%",
        default_height=f"{int(height or fig.layout.height or 420)}px",
        post_script="""
const gd = document.getElementById('{plot_id}');
if (gd && !gd.__loadFlowAnimation) {
  gd.__loadFlowAnimation = true;
  const tick = () => {
    const indices = [];
    const xUpdate = [];
    const yUpdate = [];
    (gd.data || []).forEach((trace, idx) => {
      const meta = trace.meta || {};
      if (!meta.animate_flow) return;
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
        meta._head = head + step;
      } else {
        meta._head = 0;
      }
      indices.push(idx);
      xUpdate.push(segX);
      yUpdate.push(segY);
    });
    if (indices.length) {
      Plotly.restyle(gd, {x: xUpdate, y: yUpdate}, indices);
    }
  };
  tick();
  window.setInterval(tick, 125);
}
""",
    )
    components.html(plot_html, height=int(height or fig.layout.height or 420) + 18)


def _render_shear_behaviour_plot(visual_mode: str | None = None, theta_v_deg: float | None = None):
    show_load_flow = bool(st.session_state.get("shear_show_load_flow", False))
    show_cracks = bool(st.session_state.get("shear_show_cracks", True))
    show_stress_block = bool(st.session_state.get("shear_show_stress_block", True))
    show_stm_overlay = bool(st.session_state.get("shear_show_stm_overlay", False))
    fig = build_shear_behaviour_figure(
        visual_mode="Principal stress field",
        theta_v_deg=theta_v_deg,
        show_load_flow=show_load_flow,
        show_cracks=show_cracks,
        show_stress_block=show_stress_block,
        show_stm_overlay=show_stm_overlay,
    )
    if visual_mode == "Principal stress field" and show_load_flow:
        _render_animated_plotly_figure(fig, height=int(fig.layout.height or SHEAR_VISUAL_HEIGHT_PX))
    else:
        _render_centered_shear_plotly(
            fig,
            chart_key="shear_behaviour_visual_mode",
        )
    caption = (
        "Illustrative only — schematic principal-stress-style field, not a finite-element stress solution."
        if visual_mode == "Principal stress field"
        else "Illustrative only — idealised strut-and-tie model for conceptual interpretation, not a code design check."
    )
    st.caption(caption)
    if visual_mode == "Principal stress field":
        st.caption("Concrete cannot resist tension -> cracks form perpendicular to σ2.")


def _render_shear_behaviour_diagrams(theta_v_deg: float) -> None:
    show_load_flow = False
    show_cracks = True
    show_stress_block = True
    show_stm_overlay = False
    _spacer, info_col = st.columns([0.94, 0.06], gap="small")
    with info_col:
        with info_i_button(help_text="Diagram display options"):
            st.caption("Display options")
            show_stm_overlay = st.toggle("Show strut-and-tie model", value=False, key="shear_show_stm_overlay")
            show_load_flow = st.toggle("Show load flow", value=False, key="shear_show_load_flow")
            show_cracks = st.toggle("Show cracks", value=True, key="shear_show_cracks")
            show_stress_block = st.toggle("Show stress block", value=True, key="shear_show_stress_block")
    fig = build_shear_behaviour_figure(
        visual_mode="Principal stress field",
        theta_v_deg=theta_v_deg,
        show_load_flow=show_load_flow,
        show_cracks=show_cracks,
        show_stress_block=show_stress_block,
        show_stm_overlay=show_stm_overlay,
    )
    if show_load_flow:
        _render_animated_plotly_figure(fig, height=int(fig.layout.height or 420))
    else:
        _render_centered_shear_plotly(
            fig,
            chart_key="shear_behaviour_mcft_single",
        )
    st.caption("Illustrative only — schematic principal-stress-style field with optional STM overlay, not a finite-element stress solution.")


def _build_principal_stress_axes_cue() -> go.Figure:
    fig = go.Figure()
    theta_v_deg = float(
        st.session_state.get(
            "crack_theta_deg",
            get_param("crack_theta_deg", st.session_state.get("theta_v_deg", get_param("theta_v_deg", 45.0))),
        )
        or 45.0
    )
    theta_v_rad = math.radians(max(0.0, min(theta_v_deg, 89.0)))
    half_side = 0.34
    panel_y = 0.0
    panel_centres = [0.0, 2.2, 4.5]

    def _rot(cx: float, cy: float, dx: float, dy: float, angle: float) -> tuple[float, float]:
        return (
            cx + dx * math.cos(angle) - dy * math.sin(angle),
            cy + dx * math.sin(angle) + dy * math.cos(angle),
        )

    def _add_poly(points: list[tuple[float, float]], color: str, width: float, dash: str | None = None, opacity: float = 1.0) -> None:
        fig.add_trace(
            go.Scatter(
                x=[pt[0] for pt in points],
                y=[pt[1] for pt in points],
                mode="lines",
                line=dict(color=color, width=width, dash=dash or "solid"),
                opacity=opacity,
                hoverinfo="skip",
                showlegend=False,
            )
        )

    def _add_square(cx: float, angle: float, *, color: str, width: float, opacity: float = 1.0) -> None:
        pts = [
            _rot(cx, panel_y, -half_side, -half_side, angle),
            _rot(cx, panel_y, half_side, -half_side, angle),
            _rot(cx, panel_y, half_side, half_side, angle),
            _rot(cx, panel_y, -half_side, half_side, angle),
            _rot(cx, panel_y, -half_side, -half_side, angle),
        ]
        _add_poly(pts, color, width, opacity=opacity)

    def _add_arrow(x0: float, y0: float, x1: float, y1: float, *, color: str, width: float = 1.2, dash: str | None = None, opacity: float = 1.0) -> None:
        fig.add_annotation(
            x=x1,
            y=y1,
            ax=x0,
            ay=y0,
            xref="x",
            yref="y",
            axref="x",
            ayref="y",
            text="",
            showarrow=True,
            arrowhead=2,
            arrowsize=0.8,
            arrowwidth=width,
            arrowcolor=color,
            opacity=opacity,
            standoff=0,
        )
        if dash:
            _add_poly([(x0, y0), (x1, y1)], color, width, dash=dash, opacity=opacity * 0.9)

    for cx, label in zip(panel_centres, ["(A) stress state", "(B) rotate by θ", "(C) principal directions"]):
        fig.add_annotation(x=cx, y=0.96, text=label, showarrow=False, font=dict(size=10, color="rgba(85,85,85,0.90)"))

    # A: stress state (σx + τ)
    cx = panel_centres[0]
    top_y = panel_y + half_side
    bot_y = panel_y - half_side
    left_x = cx - half_side
    right_x = cx + half_side
    normal_len = 0.24
    shear_len = 0.24
    _add_square(cx, 0.0, color="rgba(120,120,120,0.65)", width=1.5)
    # Top compression arrows acting into the top face.
    for x_pos in (cx - 0.16, cx + 0.16):
        _add_arrow(
            x_pos,
            top_y + normal_len,
            x_pos,
            top_y + 0.02,
            color="rgba(200,45,45,0.82)",
            width=1.2,
        )
    # Bottom tension arrows acting away from the bottom face.
    for x_pos in (cx - 0.16, cx + 0.16):
        _add_arrow(
            x_pos,
            bot_y - 0.02,
            x_pos,
            bot_y - normal_len,
            color="rgba(0,90,200,0.80)",
            width=1.2,
        )
    # Normal stresses on the side faces.
    _add_arrow(left_x - normal_len, panel_y + 0.14, left_x - 0.02, panel_y + 0.14, color="rgba(200,45,45,0.82)", width=1.2)
    _add_arrow(right_x + normal_len, panel_y + 0.14, right_x + 0.02, panel_y + 0.14, color="rgba(200,45,45,0.82)", width=1.2)
    _add_arrow(left_x + 0.02, panel_y - 0.14, left_x + normal_len, panel_y - 0.14, color="rgba(0,90,200,0.80)", width=1.2)
    _add_arrow(right_x - 0.02, panel_y - 0.14, right_x - normal_len, panel_y - 0.14, color="rgba(0,90,200,0.80)", width=1.2)
    # Shear stresses drawn directly on the faces.
    _add_arrow(cx - 0.14, top_y, cx + 0.14, top_y, color="rgba(110,110,110,0.82)", width=1.05)
    _add_arrow(cx + 0.14, bot_y, cx - 0.14, bot_y, color="rgba(110,110,110,0.82)", width=1.05)
    _add_arrow(left_x, panel_y - 0.14, left_x, panel_y + 0.14, color="rgba(110,110,110,0.82)", width=1.05)
    _add_arrow(right_x, panel_y + 0.14, right_x, panel_y - 0.14, color="rgba(110,110,110,0.82)", width=1.05)
    fig.add_annotation(x=cx, y=0.63, text="σx", showarrow=False, font=dict(size=10, color="rgba(200,45,45,0.84)"))
    fig.add_annotation(x=right_x + 0.26, y=0.50, text="τ", showarrow=False, font=dict(size=10, color="rgba(110,110,110,0.84)"))
    fig.add_annotation(
        x=cx,
        y=-0.90,
        text="Bending creates tension and compression; shear (τ) acts on all faces",
        showarrow=False,
        font=dict(size=8, color="rgba(85,85,85,0.86)"),
    )

    # B: rotated element, shear fading out
    cx = panel_centres[1]
    rot_angle = -0.55 * theta_v_rad
    _add_square(cx, 0.0, color="rgba(150,150,150,0.22)", width=1.2, opacity=0.75)
    _add_square(cx, rot_angle, color="rgba(120,120,120,0.58)", width=1.5)
    _add_arrow(cx - 0.18, panel_y + 0.90, cx + 0.18, panel_y + 0.90, color="rgba(110,110,110,0.42)", width=1.0, dash="dot", opacity=0.70)
    _add_arrow(cx + 0.90, panel_y + 0.18, cx + 0.90, panel_y - 0.18, color="rgba(110,110,110,0.30)", width=1.0, dash="dot", opacity=0.50)
    _add_arrow(cx + 0.18, panel_y - 0.90, cx - 0.06, panel_y - 0.90, color="rgba(110,110,110,0.20)", width=0.9, dash="dot", opacity=0.34)
    _add_arrow(cx - 0.90, panel_y - 0.18, cx - 0.90, panel_y + 0.06, color="rgba(110,110,110,0.16)", width=0.9, dash="dot", opacity=0.28)
    fig.add_annotation(x=cx + 0.78, y=-0.55, text="shear → 0", showarrow=False, font=dict(size=9, color="rgba(100,100,100,0.82)"))
    rot_arc: list[tuple[float, float]] = []
    for idx in range(22):
        t = idx / 21
        ang = rot_angle * t
        rot_arc.append((cx + 0.42 * math.cos(ang), panel_y + 0.42 * math.sin(ang)))
    _add_poly(rot_arc, "rgba(120,120,120,0.76)", 1.2)
    fig.add_annotation(
        x=cx + rot_arc[-1][0] - cx,
        y=panel_y + rot_arc[-1][1] - panel_y,
        ax=cx + rot_arc[-2][0] - cx,
        ay=panel_y + rot_arc[-2][1] - panel_y,
        xref="x",
        yref="y",
        axref="x",
        ayref="y",
        text="",
        showarrow=True,
        arrowhead=2,
        arrowsize=0.7,
        arrowwidth=1.0,
        arrowcolor="rgba(120,120,120,0.72)",
    )
    fig.add_annotation(x=cx + 0.50, y=-0.30, text="θ", showarrow=False, font=dict(size=10, color="rgba(100,100,100,0.88)"))

    # C: final principal directions
    cx = panel_centres[2]
    principal_angle = -theta_v_rad
    _add_square(cx, principal_angle, color="rgba(135,135,135,0.34)", width=1.2, opacity=0.95)
    _add_poly([(cx - 0.82, panel_y), (cx + 0.82, panel_y)], "rgba(120,120,120,0.38)", 1.1, dash="dot")
    sigma_len = 0.90
    sigma1_pts = [
        (cx - sigma_len * math.cos(principal_angle), panel_y - sigma_len * math.sin(principal_angle)),
        (cx + sigma_len * math.cos(principal_angle), panel_y + sigma_len * math.sin(principal_angle)),
    ]
    sigma2_angle = principal_angle + math.pi / 2.0
    sigma2_pts = [
        (cx - sigma_len * math.cos(sigma2_angle), panel_y - sigma_len * math.sin(sigma2_angle)),
        (cx + sigma_len * math.cos(sigma2_angle), panel_y + sigma_len * math.sin(sigma2_angle)),
    ]
    _add_poly(sigma1_pts, "rgba(200,45,45,0.85)", 2.7)
    _add_poly(sigma2_pts, "rgba(0,90,200,0.82)", 2.7)

    face_offset = half_side
    face_arrow_len = 0.18
    # Compression arrows act normal to the principal planes.
    for sign in (-1.0, 1.0):
        face_cx = cx + sign * face_offset * math.cos(principal_angle)
        face_cy = panel_y + sign * face_offset * math.sin(principal_angle)
        _add_arrow(
            face_cx + sign * face_arrow_len * math.cos(principal_angle),
            face_cy + sign * face_arrow_len * math.sin(principal_angle),
            face_cx,
            face_cy,
            color="rgba(200,45,45,0.74)",
            width=1.0,
            opacity=0.82,
        )
    # Tension arrows act normal to the perpendicular pair of principal planes.
    for sign in (-1.0, 1.0):
        face_cx = cx + sign * face_offset * math.cos(sigma2_angle)
        face_cy = panel_y + sign * face_offset * math.sin(sigma2_angle)
        _add_arrow(
            face_cx,
            face_cy,
            face_cx + sign * face_arrow_len * math.cos(sigma2_angle),
            face_cy + sign * face_arrow_len * math.sin(sigma2_angle),
            color="rgba(0,90,200,0.70)",
            width=1.0,
            opacity=0.80,
        )

    final_arc: list[tuple[float, float]] = []
    for idx in range(18):
        t = idx / 17
        ang = -theta_v_rad * t
        final_arc.append((cx + 0.22 * math.cos(ang), panel_y + 0.22 * math.sin(ang)))
    _add_poly(final_arc, "rgba(110,90,90,0.70)", 1.1)
    fig.add_annotation(
        x=cx + 0.78 * math.cos(principal_angle),
        y=panel_y + 0.78 * math.sin(principal_angle),
        text="σ1",
        showarrow=False,
        font=dict(size=11, color="rgba(200,45,45,0.92)"),
    )
    fig.add_annotation(
        x=cx + 0.78 * math.cos(sigma2_angle),
        y=panel_y + 0.78 * math.sin(sigma2_angle),
        text="σ2",
        showarrow=False,
        font=dict(size=11, color="rgba(0,90,200,0.92)"),
    )
    fig.add_annotation(
        x=cx + 0.32 * math.cos(-0.55 * theta_v_rad),
        y=0.32 * math.sin(-0.55 * theta_v_rad) - 0.02,
        text="θv",
        showarrow=False,
        font=dict(size=10, color="rgba(110,90,90,0.82)"),
    )
    fig.add_annotation(x=cx, y=-0.88, text="No shear on principal planes", showarrow=False, font=dict(size=9, color="rgba(90,90,90,0.82)"))
    fig.update_layout(
        width=540,
        height=190,
        margin=dict(l=4, r=4, t=4, b=4),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(visible=False, range=[-1.0, 5.5], fixedrange=True),
        yaxis=dict(visible=False, range=[-1.0, 1.0], scaleanchor="x", scaleratio=1, fixedrange=True),
    )
    return fig


def _render_principal_stress_directions_explainer() -> None:
    with st.expander("What are principal stress directions?"):
        st.markdown(
            """
At any point in a beam, the local stress state can be resolved into two special directions where the material sees **pure normal stress** and **no shear on those planes**. These are the **principal stress directions**.

In the stress-field visual, the **red trajectories** represent the principal compressive direction **σ1**, and the **blue trajectories** represent the principal tensile direction **σ2**.

Within approximately one effective depth (**d**) of supports, behaviour is a **D-region** with disturbed stress flow. Beyond this, in the **shear span**, bending and shear combine to rotate the principal stresses, causing diagonal tension and shear cracking.

At midspan, behaviour is mainly flexural, with bottom tension and top compression dominating. MCFT and STM then act as engineering idealisations of that same underlying stress field.
            """
        )
        cue_col, note_col = st.columns([1, 1.5], gap="medium")
        with cue_col:
            _render_centered_shear_plotly(
                _build_principal_stress_axes_cue(),
                chart_key="shear_principal_stress_axes_cue",
                max_width_px=540,
                height_px=190,
            )
        with note_col:
            st.markdown(
                """
**σ1** is the local principal compression direction, and **σ2** is the local principal tension direction.

**θv** is the angle of the principal compression direction **σ1** measured from the beam axis. It is the rotation required to eliminate shear stress.

The local stress block is shown just outside the support **D-region**, in a representative **shear-span web region** where diagonal cracking is most relevant, not at flexural midspan.

The strut direction in the STM is a simplified representation of this same compression field direction.
                """
            )
        st.markdown("#### What causes shear cracks?")
        st.markdown(
            """
Between concrete compression struts in the **shear span**, the principal tensile direction **σ2** pulls the web apart.  
Because concrete cannot resist much tension, a shear crack forms approximately **perpendicular to σ2**. This is why the crack cue and stress block are shown just beyond the support **D-region**, rather than at the support itself or at midspan.
            """
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
    render_section_title("Visualisation")
    reo_layout_mode = st.session_state.get("shear_reo_layout_mode", "Side view")
    if reo_layout_mode == "Section":
        _render_shear_cross_section()
    else:
        _render_shear_side_view()

    controls_col, _ = st.columns([4, 6], gap="small")
    with controls_col:
        st.radio(
            "Reinforcement layout",
            options=["Section", "Side view"],
            horizontal=True,
            key="shear_reo_layout_mode",
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
                st.image(path, caption=caption, use_container_width=True)
            else:
                st.info(f"💡 Add diagram for Step {step_no} at `{path}`.")
        with col_right:
            theta_path = os.path.join("assets", "theta.png")
            if os.path.exists(theta_path):
                st.image(theta_path, caption="Strut angle $\\theta_v$", use_container_width=True)
            else:
                st.info(f"💡 Add theta diagram at `{theta_path}`.")
        return
    
    # Special handling for Step 9 (step_no == 7 in dict): stack two images vertically
    if step_no == 7:  # This is Step 9 in the display
        if os.path.exists(path):
            st.image(path, caption=caption, use_container_width=True)
        else:
            st.info(f"💡 Add diagram for Step 9 at `{path}`.")
        # Add second image below
        vumax2_path = os.path.join("assets", "shear_step7_Vumax2.png")
        if os.path.exists(vumax2_path):
            st.image(vumax2_path, caption="Strut-and-tie / concrete compression strut behaviour in deep beams", use_container_width=True)
        else:
            st.info(f"💡 Add Step 9 second diagram at `{vumax2_path}`.")
        return
    
    # Default: single image
    if os.path.exists(path):
        st.image(path, caption=caption, use_container_width=True)
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
def cot(rad: float) -> float:
    """Cotangent with protection against tan(pi/2) etc."""
    return 1.0 / math.tan(rad)


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

    try:
        if width is not None:
            st.image(resolved_path, caption=caption, width=width)
        elif use_container_width is not None:
            st.image(resolved_path, caption=caption, use_container_width=use_container_width)
        else:
            st.image(resolved_path, caption=caption, use_container_width=True)
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

    # region agent log
    missing_widget_keys = [k for k in TAB_KEYS.keys() if k not in st.session_state]
    _dbg_log(
        {
            "sessionId": "debug-session",
            "runId": "pre",
            "hypothesisId": "D",
            "location": "shear_page.py:1139",
            "message": "session_state widget inventory snapshot",
            "data": {
                "missing_widget_keys_count": len(missing_widget_keys),
                "missing_widget_keys_sample": missing_widget_keys[:20],
            },
            "timestamp": int(time.time() * 1000),
        }
    )
    # endregion
    
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
    # region agent log
    _dbg_log(
        {
            "sessionId": "debug-session",
            "runId": "pre",
            "hypothesisId": "E",
            "location": "shear_page.py:1156",
            "message": "design action keys snapshot",
            "data": {
                "Tu_star": Tu_star,
                "Mu_star": M_star,
                "Vu_star": Vu_star,
                "Tu_star_state": st.session_state.get("Tu_star"),
                "uls_Mstar_state": st.session_state.get("uls_Mstar"),
                "uls_Vstar_state": st.session_state.get("uls_Vstar"),
                "shear_Tu_star": st.session_state.get("shear_Tu_star"),
                "inputs_Tu_star": st.session_state.get("inputs_Tu_star"),
                "actions_Tu_star": st.session_state.get("actions_Tu_star"),
                "load_Mstar_proxy": st.session_state.get("load_Mstar_proxy"),
                "load_Vstar_proxy": st.session_state.get("load_Vstar_proxy"),
            },
            "timestamp": int(time.time() * 1000),
        }
    )
    # endregion
    # region agent log
    _dbg_log(
        {
            "sessionId": "debug-session",
            "runId": "pre",
            "hypothesisId": "C",
            "location": "shear_page.py:1136",
            "message": "compute_shear_results Tu_star snapshot",
            "data": {
                "Tu_star": Tu_star,
                "Tu_star_state": st.session_state.get("Tu_star"),
                "shear_Tu_star": st.session_state.get("shear_Tu_star"),
                "inputs_Tu_star": st.session_state.get("inputs_Tu_star"),
            },
            "timestamp": int(time.time() * 1000),
        }
    )
    # endregion
    
    lig_d = live_shear_state["lig_d"]
    legs = live_shear_state["lig_legs"]
    s_lig = live_shear_state["s_lig"]
    
    # Derived metrics
    phi_Vu_cap = results.phi_Vu
    util = results.V_eq / phi_Vu_cap if phi_Vu_cap > 0 else float("nan")
    phi_Vu_max = phi * results.Vu_max_kN
    Vuc_util = results.V_eq / phi_Vu_max if phi_Vu_max > 0 else float("nan")
    
    # Minimum shear reinforcement + spacing checks
    Asv_over_s = results.Asv / s_lig if s_lig else 0.0
    Asv_min_over_s = 0.08 * math.sqrt(fc) * results.b_v / (results.f_syv or 1.0)
    min_shear_ok = Asv_over_s >= Asv_min_over_s
    max_spacing = min(0.75 * D, 500.0) if D else 500.0
    spacing_ok = s_lig <= max_spacing if s_lig else False
    
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
            f"s = {s_lig:.0f} mm",
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
            f"s = {s_lig:.0f} mm",
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
    # Handle cross-page navigation from Inputs page
    from jump_nav import get_jump_uid
    get_jump_uid()
    
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

    render_result_page_title("Shear & Torsion")

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

    # region agent log
    missing_widget_keys = [k for k in TAB_KEYS.keys() if k not in st.session_state]
    _dbg_log(
        {
            "sessionId": "debug-session",
            "runId": "pre",
            "hypothesisId": "F",
            "location": "shear_page.py:1460",
            "message": "render_shear widget inventory + actions snapshot",
            "data": {
                "missing_widget_keys_count": len(missing_widget_keys),
                "missing_widget_keys_sample": missing_widget_keys[:20],
                "Tu_star_state": st.session_state.get("Tu_star"),
                "uls_Mstar_state": st.session_state.get("uls_Mstar"),
                "uls_Vstar_state": st.session_state.get("uls_Vstar"),
                "shear_Tu_star": st.session_state.get("shear_Tu_star"),
                "inputs_Tu_star": st.session_state.get("inputs_Tu_star"),
                "actions_Tu_star": st.session_state.get("actions_Tu_star"),
                "load_Mstar_proxy": st.session_state.get("load_Mstar_proxy"),
                "load_Vstar_proxy": st.session_state.get("load_Vstar_proxy"),
                "actions_source": st.session_state.get("actions_source"),
            },
            "timestamp": int(time.time() * 1000),
        }
    )
    # endregion


    # Top summary table placeholder (for clickable summary table)
    top_summary_placeholder = st.empty()
    visualisation_placeholder = st.empty()

    # --- Shared visualisation viewport ---
    page_divider()

    # =====================================================
    # 1. DESIGN INPUTS (shared + local)  — SAME WIDGET CONTRACT
    # =====================================================
    actions_mode = get_param("actions_mode", "manual")
    design_controls = is_design_governing()
    is_design_driven = actions_mode == "design"
    support_options = [
        "Simply supported",
        "Continuous – end span",
        "Continuous – interior span",
        "Cantilever",
    ]
    support_help_text = "Support condition determines the deflection coefficient k₂ used in AS 3600 deflection calculations."
    support_widget_key = get_widget_key_for_shared("defl_support_type", prefix="shear_") or "shear_defl_support_type"
    support_current = get_param("defl_support_type", "Simply supported")
    if support_current not in support_options:
        support_current = "Simply supported"
    if st.session_state.get(support_widget_key) != support_current:
        st.session_state[support_widget_key] = support_current

    col_actions, col_geom, col_mat = st.columns([1, 1, 1], gap="large")

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
            with info_i_button(help_text="Source of design actions (V*, N*, T*)"):
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

        new_mode = "SLS" if edit_sls else "ULS"

        if new_mode != prev_mode:
            st.session_state["loads_edit_mode"] = prev_mode
            save_proxies_to_active_set()
            st.session_state["loads_edit_mode"] = new_mode
            load_proxies_from_active_set()
            st.session_state["inputs_load_Vstar_proxy"] = st.session_state.get("load_Vstar_proxy", 0.0)
            st.session_state["inputs_load_Nstar_proxy"] = st.session_state.get("load_Nstar_proxy", 0.0)
            recalc_derived_values()
            update_results()
            st.rerun()
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

        if design_controls:
            if st.session_state.get("inputs_load_Vstar_proxy") != display_V:
                st.session_state["inputs_load_Vstar_proxy"] = display_V
            if st.session_state.get(n_proxy_widget_key) != display_N:
                st.session_state[n_proxy_widget_key] = display_N
            if st.session_state.get("shear_Tu_star") != display_T:
                st.session_state["shear_Tu_star"] = display_T

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
            "φ – strength reduction for shear",
            "shear_phi_shear",
            get_param("phi_shear", 0.75),
            sync_callbacks,
            help_text="Strength reduction factor for shear (AS 3600).",
        )

    # ---------- 1.2 Geometry (middle column) ----------
    with col_geom:
        render_section_title("Geometry & loading conditions")

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
            b_val = _coalesce_num(st.session_state.get("shear_b", get_param("b", 300.0)), 300.0)
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
    with col_mat:
        render_section_title("Materials")

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
        number_row(
            "Concrete modulus Ec (MPa)",
            "shear_Ec",
            get_param("Ec", 30000.0),
            sync_callbacks,
            help_text="Used in εₓ calc when compression develops.",
        )
        number_row(
            "Steel modulus Es (MPa)",
            "shear_Es",
            get_param("Es", 200000.0),
            sync_callbacks,
            help_text="Modulus of non-prestressed reinforcement.",
        )

    page_divider()

    col_actions, col_geom, col_mat = st.columns([1, 1, 1], gap="large")

    with col_actions:
        render_section_title("Shear reinforcement")
        
        # Widget keys (resolved via TAB_KEYS)
        w_lig_d = get_widget_key_for_shared("lig_d", prefix="shear_") or "shear_lig_d"
        w_lig_legs = get_widget_key_for_shared("lig_legs", prefix="shear_") or "shear_lig_legs"
        w_s_lig = get_widget_key_for_shared("s_lig", prefix="shear_") or "shear_s_lig"
        
        # Read shared values (do NOT write shared keys)
        lig_d_val = float(st.session_state.get("lig_d", 10.0))
        lig_legs_val = float(st.session_state.get("lig_legs", 2))
        s_lig_val = float(st.session_state.get("s_lig", 200.0))
        
        # Option lists for dropdowns
        REO_BAR_DIAS = [10, 12, 16, 20, 24, 28, 32, 36, 40]
        REO_COUNTS_0_12 = list(range(0, 13))  # 0..12 inclusive
        
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
            REO_COUNTS_0_12,
            int(lig_legs_val),
            sync_callbacks,
            help_text="Number of legs per shear link.",
        )
        
        number_row(
            "Link spacing (mm)",
            w_s_lig,
            s_lig_val,
            sync_callbacks,
            help_text="Centre-to-centre spacing of shear links (mm).",
        )

    with col_geom:
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

        n_ducts = 0.0 if n_ducts is None else float(n_ducts)
        duct_dia = 0.0 if duct_dia is None else float(duct_dia)

        sum_duct = n_ducts * (duct_dia ** 2) * 3.14159 / 4.0
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
    
    with col_mat:
        render_section_title("Shear section parameters")
        
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
            help_text="Method for calculating k_v factor (AS 3600 Cl. 8.2.4.2 or 8.2.4.3).",
        )
        
        # Determine if general method is used
        method = st.session_state.get(w_kv_method, kv_method_val)
        use_general_kv = method.startswith("General")

    # -------------------------------------------------
    # Pull shared values for calculations
    # -------------------------------------------------
    live_shear_state = build_live_canonical_shear_state(st.session_state)
    fingerprint_lig_legs = _extract_fingerprint_value(
        st.session_state.get("_auto_design_last_fingerprint"),
        "lig_legs",
    )
    _agent_debug_log(
        "Live shear state cross-check",
        {
            "live_lig_legs": st.session_state.get("lig_legs"),
            "cached_lig_legs": st.session_state.get("_cached_inputs_lig_legs"),
            "hydrated_lig_legs": ((st.session_state.get("_hydrated_from_shared_map") or {}).get("inputs_lig_legs")),
            "fingerprint_lig_legs": fingerprint_lig_legs,
            "live_db_bot": st.session_state.get("db_bot"),
            "cached_db_bot": st.session_state.get("_cached_inputs_db_bot"),
            "live_canonical_state": {
                "Mu": live_shear_state.get("Mu"),
                "Vu": live_shear_state.get("Vu"),
                "Nu": live_shear_state.get("Nu"),
                "lig_d": live_shear_state.get("lig_d"),
                "lig_legs": live_shear_state.get("lig_legs"),
                "s_lig": live_shear_state.get("s_lig"),
                "db_bot_1": live_shear_state.get("db_bot_1"),
                "db_bot_2": live_shear_state.get("db_bot_2"),
            },
        },
        location="shear_page.py",
        hypothesis_id="H71",
    )
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
    A_cp = float(getattr(shear_results, "A_cp", b_used * D_used) or 0.0)
    u_c = float(getattr(shear_results, "u_c", 2 * (b_used + D_used)) or 0.0)
    Ao = float(getattr(shear_results, "Ao", 0.9 * A_cp) or 0.0)
    uh = float(getattr(shear_results, "uh", 2 * (max(b_used - 40, 0) + max(D_used - 40, 0))) or 0.0)
    A_oh = float(getattr(shear_results, "A_oh", max(b_used - 40, 0) * max(D_used - 40, 0)) or 0.0)

    step1_req = ">" if torsion_required else "\\le"
    step1_text = (
        "required" if torsion_required else "not required (strength check only)"
    )
    torsion_status = "pass" if not torsion_required else "fail"
    
    # Check 2: Equivalent shear
    T_star_Nmm = T_star * 1e6
    torsion_eq_kN = float(getattr(shear_results, "Vt_eq_kN", 0.0) or 0.0)
    V_eq = float(getattr(shear_results, "V_eq", abs(V_star)) or abs(V_star))
    
    # Check 3: Effective section parameters
    lig_d = 10.0 if lig_d is None else float(lig_d)
    legs = 2.0 if legs is None else float(legs)
    s = 200.0 if s_lig is None else float(s_lig)
    
    Asv = float(getattr(shear_results, "Asv", legs * math.pi * lig_d ** 2 / 4.0) or 0.0)
    f_syv = fsy

    b_v = float(getattr(shear_results, "b_v", b - k_d * sum_duct) or 0.0)
    d_v = float(getattr(shear_results, "d_v", max(0.72 * D, 0.9 * d)) or 0.0)
    
    dv_1 = 0.72 * D
    dv_2 = 0.9 * d
    
    # Check 4: Longitudinal strain εx
    M_star_Nmm = abs(M_star) * 1e6
    term_M = M_star_Nmm / (d_v or 1.0)
    
    Vprime_kN = abs(V_star) - P_v
    Vprime_N = Vprime_kN * 1e3
    
    torsion_N = 0.97 * T_star_Nmm * uh / (2.0 * (Ao or 1.0))
    sqrt_inner = math.sqrt(Vprime_N ** 2 + torsion_N ** 2)
    
    N_star_N = 0.5 * N_star * 1e3
    A_pt_fpo_N = A_pt * f_po
    
    numerator_1 = term_M + sqrt_inner + N_star_N - A_pt_fpo_N
    
    Ep = 195000.0  # tendon modulus, MPa
    denom1 = 2.0 * (Es * A_st + Ep * A_pt)
    eps_x_1 = numerator_1 / denom1 if denom1 > 0 else 0.0
    
    V_abs_N = abs(V_star) * 1e3
    numerator_2 = term_M + V_abs_N - P_v * 1e3 + N_star_N - A_pt_fpo_N
    denom2 = 2.0 * (Es * A_st + Ep * A_pt + Ec * A_ct)
    eps_x_2 = numerator_2 / denom2 if denom2 > 0 else 0.0
    
    if eps_x_1 >= 0:
        eps_x_raw = eps_x_1
        eq_used = "Equation (1) – mid-depth in tension"
    else:
        eps_x_raw = eps_x_2
        eq_used = "Equation (2) – mid-depth in slight compression"
    
    eps_x = max(-0.0002, min(eps_x_raw, 0.003))
    
    # Check 5: k_v and θ_v
    if use_general_kv:
        if fc <= 65:
            k_dg = 32.0 / (16.0 + d_g)
            k_dg = max(k_dg, 0.8)
            if d_g >= 16:
                k_dg = max(k_dg, 1.0)
        else:
            k_dg = 2.0
        
        Asv_over_s = Asv / s
        Asv_min_over_s = 0.08 * math.sqrt(fc) * b_v / (f_syv or 1.0)
        
        if Asv_over_s < Asv_min_over_s:
            k_v = (0.4 / (1 + 1500 * eps_x)) * (1300 / (1000 + k_dg * d_v))
            kv_case = "general MCFT with **low stirrup ratio** ($A_{sv}/s < (A_{sv}/s)_{min}$)"
        else:
            k_v = 0.4 / (1 + 1500 * eps_x)
            kv_case = "general MCFT with **adequate stirrup ratio**"
        
        theta_v_deg = 29.0 + 7000.0 * eps_x
    else:
        if Asv / s < 0.08 * math.sqrt(fc) * b_v / (f_syv or 1.0):
            k_v = min(200.0 / (1000.0 + 1.3 * d_v), 0.10)
            kv_case = "simplified non-prestressed – **low stirrup ratio**"
        else:
            k_v = 0.15
            kv_case = "simplified non-prestressed – **minimum stirrups provided**"
        theta_v_deg = 36.0
        k_dg = float("nan")
    
    eps_x = float(getattr(shear_results, "eps_x", eps_x) or 0.0)
    k_v = float(getattr(shear_results, "k_v", k_v) or 0.0)
    theta_v_deg = float(getattr(shear_results, "theta_v_deg", theta_v_deg) or 0.0)
    theta_v_rad = float(getattr(shear_results, "theta_v_rad", math.radians(theta_v_deg)) or 0.0)

    with visualisation_placeholder.container():
        _render_shear_visualisation_block(theta_v_deg=shear_results.theta_v_deg)
    
    # Check 6: Concrete shear contribution
    sqrt_fc_limited = float(getattr(shear_results, "sqrt_fc_limited", min(math.sqrt(fc), 8.0)) or 0.0)
    Vuc_kN = float(getattr(shear_results, "Vuc_kN", 0.0) or 0.0)
    
    # Check 7: Steel shear contribution
    Vus_kN = float(getattr(shear_results, "Vus_kN", 0.0) or 0.0)
    
    # Check 8: Combined shear strength
    Vu_total_kN = float(getattr(shear_results, "Vu_total_kN", Vuc_kN + Vus_kN + P_v) or 0.0)
    phi_Vu = float(getattr(shear_results, "phi_Vu", phi * Vu_total_kN) or 0.0)
    shear_ok = bool(getattr(shear_results, "shear_ok", phi_Vu >= V_eq))
    shear_status = "pass" if shear_ok else "fail"
    
    # Check 9: Web crushing
    theta_1_deg = 90.0
    theta_1_rad = math.radians(theta_1_deg)
    cot_theta_v = cot(theta_v_rad)
    cot_theta_1 = cot(theta_1_rad)
    
    Vu_max_kN = float(getattr(shear_results, "Vu_max_kN", 0.0) or 0.0)
    Vu_max_N = Vu_max_kN * 1e3
    
    V_star_N = V_star * 1e3
    term_V = V_star_N / (b_v * d_v or 1.0)
    term_T = T_star_Nmm * uh / (1.7 * (A_oh ** 2 or 1.0))
    
    LHS = float(getattr(shear_results, "LHS", math.sqrt(term_V ** 2 + term_T ** 2)) or 0.0)
    RHS = float(getattr(shear_results, "RHS", phi * Vu_max_N / (b_v * d_v or 1.0)) or 0.0)
    
    web_ok = bool(getattr(shear_results, "web_ok", LHS <= RHS))
    web_status = "pass" if web_ok else "fail"
    
    # Check 10: Minimum shear reinforcement
    Asv_over_s_check10 = Asv / s if s > 0 else 0.0
    Asv_min_over_s_check10 = 0.08 * math.sqrt(fc) * b_v / (f_syv or 1.0)
    min_shear_ok = Asv_over_s_check10 >= Asv_min_over_s_check10
    min_shear_status = "pass" if min_shear_ok else "fail"

    # =====================================================
    # 3. SHEAR DESIGN CHECKS UI (organized into tabs)
    # =====================================================
    page_divider()
    render_section_title("Shear design checks")
    
    apply_step_summary_expander_css()  # same pattern as bending
    
    tab1, tab2, tab3 = st.tabs([
        "Torsion + dimensions",
        "MCFT and strength checks",
        "Shear reinforcement checks",
    ])
    
    # =====================================================
    # TAB 1: Torsion + dimensions
    # =====================================================
    with tab1:
        st.caption("Torsion cracking check, equivalent shear, and effective section parameters (bv, dv).")
        
        # =====================================================
        # Check 1 — TORSION CRACKING CHECK (T_cr)
        # =====================================================
        # Check 1 converted to use render_expandable_step (always-summary mode)
        # Build calc markdown from the existing details
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
            
        # Diagram render function (native Plotly — same pipeline as MCFT)
        def check1_diagram_fn():
            torsion_fig = build_torsion_plotly_figure(
                beam_length=1.0,
                beam_depth=0.34,
                skew_dx=0.16,
                cover_ratio=0.12,
            )
            torsion_fig = _standardise_shear_visual_layout(torsion_fig)
            # Keep torsion and MCFT diagrams on the same centered display frame.
            # Any future sizing change must be made through SHEAR_VISUAL_* constants only.
            _render_centered_shear_plotly(
                torsion_fig,
                chart_key="torsion_cracking_diagram",
                max_width_px=SHEAR_VISUAL_MAX_WIDTH_PX,
            )
        
        # Info render function (popover)
        def check1_info_fn():
            col_info_header, _ = st.columns([0.1, 0.9])
            with col_info_header:
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
        
        # Build summary line
        check1_summary = f"Check 1 — Torsion cracking check | Result: Torsion design is {'NOT REQUIRED' if not torsion_required else 'REQUIRED'}"
        
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
            diagram_above_calc=True,
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
            # --- No torsion design: equivalent shear = shear only ---
            torsion_eq_kN = 0.0
            V_eq = V_star
            check2_calc_md = f"""
*Purpose: Convert torsion into an equivalent shear force (if required).*

**Inputs:**

- Shear demand: $V^* = {V_star:.1f}$ kN  
- Torsion: $T^* = {T_star:.1f}$ kNm (from Check 1, torsion design is not required)  

---

**Formula (AS 3600 Cl. 8.2.3):**

$$\\large V_{{eq}}^* = \\sqrt{{(V^*)^2 + V_{{t,eq}}^2}}$$

Since $V_{{t,eq}} = 0$:

$$\\large V_{{eq}}^* = V^*$$

**Substitution:**

$$\\large V_{{eq}}^* = V^* = {V_eq:.1f}\\ \\text{{kN}}$$

---

**Result:**

- Torsion is not treated as a design action.  
- **$V_{{eq}}^* = {V_eq:.1f}$ kN**
"""
            
        # Diagram render function
        def check2_diagram_fn():
            # Mode selector for diagram - standalone buttons
            st.markdown("**Stress flow mode:**")

            OPTIONS = [
                ("V+T (Combined)", "VT"),
                ("V (Shear only)", "V"),
                ("T (Torsion only)", "T"),
            ]

            key = "stress_flow_mode"
            mode = st.session_state.get(key, "VT")
            if mode not in {"VT", "V", "T"}:
                mode = "VT"
                st.session_state[key] = mode

            st.markdown(
                """
                <style>
                  div[data-testid="column"] > div:has(> div > button) button {
                    width: 100%;
                    border-radius: 10px;
                    padding: 0.55rem 0.75rem;
                    border: 1px solid rgba(49,51,63,0.2);
                  }
                </style>
                """,
                unsafe_allow_html=True,
            )

            c1, c2, c3 = st.columns(3, gap="small")

            def _mode_btn(col, label, value):
                active = (st.session_state.get(key, "VT") == value)
                with col:
                    if st.button(
                        label,
                        key=f"btn_{key}_{value}",
                        use_container_width=True,
                        type="primary" if active else "secondary",
                    ):
                        st.session_state[key] = value

            _mode_btn(c1, OPTIONS[0][0], OPTIONS[0][1])
            _mode_btn(c2, OPTIONS[1][0], OPTIONS[1][1])
            _mode_btn(c3, OPTIONS[2][0], OPTIONS[2][1])

            mode = st.session_state.get(key, "VT")
            mode_short = "V+T" if mode == "VT" else ("V" if mode == "V" else "T")
            
            from section_layout import compute_section_layout
            layout = compute_section_layout()
            shape_name = layout.get("shape_name", "Rectangle (b × D)")
            dims = layout.get("dims", {})
            reo = layout.get("reo", {})

            try:
                fig = plot_shear_torsion_section_2d(
                    shape_name=shape_name,
                    dims=dims,
                    reo=reo,
                    mode=mode_short,
                    show_labels=True,
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
                )
            # Keep torsion and MCFT diagrams on the same centered display frame.
            # Any future sizing change must be made through SHEAR_VISUAL_* constants only.
            torsion_fig = _standardise_shear_visual_layout(fig)
            _render_centered_shear_plotly(
                torsion_fig,
                chart_key="shear_equivalent_shear_stress_flow_diagram",
                max_width_px=SHEAR_VISUAL_MAX_WIDTH_PX,
            )

        # Info render function (popover)
        def check2_info_fn():
            col_info_header, _ = st.columns([0.1, 0.9])
            with col_info_header:
                with info_i_button(help_text="Equivalent shear (combined demand)"):
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
        
        # Build summary line
        check2_summary = f"Check 2 — Equivalent shear $V_{{eq}}^*$ | Result: $V_{{eq}}^* = {V_eq:.1f}$ kN"
        
        render_expandable_step(
            page_key="shear",
            step_id="shear_check2",
            title="Check 2 — Equivalent shear $V_{eq}^*$",
            summary_md=check2_summary,
            status_kind=None,
            calc_md=check2_calc_md,
            diagram_render_fn=check2_diagram_fn,
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

        # Info render function (popover)
        def check3_info_fn():
            col_info_header, _ = st.columns([0.1, 0.9])
            with col_info_header:
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
    # TAB 2: MCFT and strength checks
    # =====================================================
    with tab2:
        st.caption("Longitudinal strain, MCFT parameters, concrete and steel contributions, combined capacity, and web crushing.")
        _render_shear_behaviour_diagrams(theta_v_deg=shear_results.theta_v_deg)
        _render_principal_stress_directions_explainer()

        # =====================================================
        # Check 4 — LONGITUDINAL STRAIN εx
        # =====================================================
        # Build calc markdown
        eq2_note = ""
        if eps_x_1 < 0:
            eq2_note = f"""
**Since the strain from Equation (1) is negative**  
$\\varepsilon_{{x,1}} = {eps_x_1:.5f} < 0$, mid-depth is in slight compression.  
AS 3600 allows εₓ to be taken as 0 or recalculated with **Equation (2)** including the concrete stiffness term:

$$\\large \\varepsilon_{{x,2}} = \\frac{{|M^*|/d_v + |V^*| - P_v + 0.5N^* - A_{{pt}} f_{{po}}}}{{2(E_s A_{{st}} + E_p A_{{pt}} + E_c A_{{ct}})}}$$

Substituting the derived numerator and denominator:

$$\\large \\varepsilon_{{x,2}} = \\frac{{{numerator_2:,.0f}}}{{{denom2:,.0f}}} = {eps_x_2:.5f}$$
"""

        check4_calc_md = f"""
*Purpose: Calculate the longitudinal strain $\\varepsilon_x$ at mid-depth for use in the MCFT shear model.*

**Inputs:**

- Shear depth: $d_v = {_fmt(d_v)}$ mm  
- Actions: $M^* = {_fmt(M_star)}$ kNm, $V^* = {_fmt(V_star)}$ kN, $P_v = {_fmt(P_v)}$ kN, $N^* = {_fmt(N_star)}$ kN, $T^* = {_fmt(T_star)}$ kNm  
- Material stiffness: $E_s = {_fmt(Es,0)}$ MPa, $E_p = {_fmt(Ep,0)}$ MPa  
- Steel areas: $A_{{st}} = {_fmt(A_st,1)}$ mm², $A_{{pt}} = {_fmt(A_pt,1)}$ mm², $f_{{po}} = {_fmt(f_po)}$ MPa  
- Torsion geometry: $u_h = {_fmt(uh)}$ mm, $A_o = {_fmt(Ao)}$ mm²  

---

**Derivation of terms:**

*Moment term:*

$$\\large |M^*|/d_v = \\frac{{|{M_star:.1f}| \\times 10^6}}{{{d_v:.1f}}} = {term_M:,.0f}\\ \\text{{N}}$$

*Shear + torsion term:*

- $V' = |V^*| - P_v = |{V_star:.1f}| - {P_v:.1f} = {Vprime_kN:.1f}$ kN  $= {Vprime_N:,.0f}$ N  
- $0.97 T^* u_h / (2A_o) = {torsion_N:,.0f}$ N  

$$\\large \\sqrt{{V'^{{2}} + (0.97 T^* u_h / 2A_o)^2}} = \\sqrt{{{Vprime_N:,.0f}^2 + {torsion_N:,.0f}^2}} = {sqrt_inner:,.0f}\\ \\text{{N}}$$

*Axial / prestress:*

- $0.5N^* = 0.5 \\times {N_star:.1f} \\times 10^3 = {N_star_N:,.0f}$ N  
- $A_{{pt}} f_{{po}} = {A_pt:.1f} \\times {f_po:.1f} = {A_pt_fpo_N:,.0f}$ N  

---

**Formula (AS 3600 Cl. 8.2.4.2.2(1)) – mid-depth in tension (εₓ ≥ 0):**

$$\\large \\varepsilon_{{x,1}} = \\frac{{|M^*|/d_v + \\sqrt{{V'^{{2}} + (0.97 T^* u_h / 2A_o)^2}} + 0.5N^* - A_{{pt}} f_{{po}}}}{{2(E_s A_{{st}} + E_p A_{{pt}})}}$$

**Substitution:**

$$\\large \\varepsilon_{{x,1}} = \\frac{{{term_M:,.0f} + {sqrt_inner:,.0f} + {N_star_N:,.0f} - {A_pt_fpo_N:,.0f}}}{{2 \\times ({Es:,.0f} \\times {A_st:.1f} + {Ep:,.0f} \\times {A_pt:.1f})}}$$

$$\\large \\varepsilon_{{x,1}} = \\frac{{{numerator_1:,.0f}}}{{{denom1:,.0f}}} = {eps_x_1:.5f}$$

{eq2_note}

---

**Result:**

- Governing equation: **{eq_used}**  
- Raw strain: $\\varepsilon_x = {eps_x_raw:.5f}$  
- After applying AS 3600 limits $[-2.0 \\times 10^{{-4}},\\, 3.0 \\times 10^{{-3}}]$:

$$\\large \\varepsilon_x = {eps_x:.5f}$$

This value is **{"positive (tension at mid-depth)" if eps_x >= 0 else "negative (slight compression at mid-depth)"}**.
"""
            
        # Diagram render function
        def check4_diagram_fn():
            # Diagram with info popover (second info button)
            col_diag_title, col_diag_info = st.columns([1, 0.08])
            with col_diag_title:
                st.markdown("**Longitudinal strain profile**")
            with col_diag_info:
                with info_i_button(help_text="Derivation of εx (conceptual)"):
                    st.markdown(r"""
### Derivation of longitudinal strain εx

**Strain basis**

Hooke's Law links stress and strain:

\[
\varepsilon = \frac{\sigma}{E}
\]

The longitudinal strain corresponds to the average longitudinal force in the member divided by the effective longitudinal stiffness.

**Resolving internal forces**

At a cracked section under M*, V*, and N*, the tensile chord force can be expressed as:

\[
T = \frac{M^*}{d_v} + 0.5N + 0.5V\cot\theta
\]

- \(M^*/d_v\): tension force from flexure  

- \(0.5N\): axial force contribution  

- \(0.5V\cot\theta\): longitudinal component of the diagonal compression strut

**AS 3600 (CSA 2004) simplification**

CSA 2004 (adopted in AS 3600) simplifies by taking:

\[
0.5\cot\theta \approx 1.0
\]

This is conservative and removes θ-dependency so εx can be evaluated without iteration.

**Diagram placeholders**

- [Diagram A] Internal force resolution (M–V–N)  

- [Diagram B] Compression strut angle θ and longitudinal component  

- [Diagram C] Strain profile through depth (top / mid / bottom)
                    """)
            
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
            
            fig_eps = make_mcft_longitudinal_strain_profile_fig(
                eps_top_uls=eps_top_uls,
                eps_x_mcft=eps_x_mcft,
                eps_bot_uls=eps_bot_uls,
                title="Longitudinal strain profile",
                height=SHEAR_VISUAL_HEIGHT_PX,
            )
            mcft_fig = _standardise_shear_visual_layout(fig_eps)
            # Keep MCFT and section diagrams on the same display frame size.
            # Any future sizing change must be made through SHEAR_VISUAL_* constants only.
            _render_centered_shear_plotly(
                mcft_fig,
                chart_key="shear_mcft_diagram",
                max_width_px=SHEAR_VISUAL_MAX_WIDTH_PX,
            )

        # Info render function (popover)
        def check4_info_fn():
            col_info_header, _ = st.columns([0.1, 0.9])
            with col_info_header:
                with info_i_button(help_text="Longitudinal strain εx (MCFT behaviour anchor)"):
                    st.markdown(r"""
### Longitudinal strain εx (MCFT behaviour)

**What MCFT is**

The Modified Compression Field Theory (MCFT) models shear transfer in cracked reinforced concrete using:

- diagonal compression struts,

- cracked concrete shear transfer mechanisms, and

- reinforcement interaction.

AS 3600 adopts a simplified MCFT form so key parameters can be obtained without iteration.

**Why strain governs shear behaviour**

As longitudinal strain increases, cracking and deformation increase, which changes:

- the diagonal crack angle, and

- the effectiveness of concrete in shear transfer.

**Why εx is evaluated at mid-depth**

Mid-depth is representative of the cracked web region where shear transfer is governed.  

εx here acts as a practical "behaviour indicator" for the shear model.

**Sign convention**

Compression strains are negative, tension strains are positive (consistent with bending strain convention).
                    """)

                    st.markdown(
                        r"""
### **How the app uses these equations**

1. Compute εₓ using **Equation (1)**.  
2. If εₓ is **negative**, recompute using **Equation (2)**.  
3. Apply AS 3600 limits:  
   $$-2.0\times10^{-4} \le \varepsilon_x \le 3.0\times10^{-3}$$
4. Use the resulting εₓ to compute $k_v$ in Check 5.
"""
                    )
        
        # Build summary line
        check4_summary = f"Check 4 — Longitudinal strain $\\varepsilon_x$ | Result: $\\varepsilon_x = {eps_x:.5f}$ ({eq_used.split('–')[0].strip()})"
        
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
        Asv_over_s = Asv / s
        Asv_min_over_s = 0.08 * math.sqrt(fc) * b_v / (f_syv or 1.0)
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
            kv_formula_block = f"""
**Governing branch check:**  

$$\\frac{{A_{{sv}}}}{{s}} = {Asv_over_s:.3f}\\ \\text{{mm}}^2/\\text{{mm}} \\ {stirrup_ratio_relation} \\ \\left(\\frac{{A_{{sv}}}}{{s}}\\right)_{{min}} = {Asv_min_over_s:.3f}\\ \\text{{mm}}^2/\\text{{mm}}$$

This gives **{stirrup_ratio_case}**, so the governing branch is: **{kv_case}**.

**Live inputs used:**  

- $\\varepsilon_x = {eps_x:.5f}$  
- $d_v = {d_v:.1f}$ mm  
- $A_{{sv}}/s = {Asv_over_s:.3f}\\ \\text{{mm}}^2/\\text{{mm}}$  
- $(A_{{sv}}/s)_{{min}} = {Asv_min_over_s:.3f}\\ \\text{{mm}}^2/\\text{{mm}}$  
- $k_{{dg}} = {k_dg_display:.3f}$  

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
            theta_sub_block = f"$$\\theta_v = {canonical_theta_v_deg:.1f}^\\circ$$"
            kv_governing_formula = (
                r"$$k_v = \min\left(\frac{200}{1000 + 1.3 d_v}, 0.10\right)$$"
                if Asv_over_s < Asv_min_over_s
                else r"$$k_v = 0.15$$"
            )
            kv_formula_block = f"""
**Governing branch check:**  

$$\\frac{{A_{{sv}}}}{{s}} = {Asv_over_s:.3f}\\ \\text{{mm}}^2/\\text{{mm}} \\ {stirrup_ratio_relation} \\ \\left(\\frac{{A_{{sv}}}}{{s}}\\right)_{{min}} = {Asv_min_over_s:.3f}\\ \\text{{mm}}^2/\\text{{mm}}$$

This gives **{stirrup_ratio_case}**, so the governing branch is: **{kv_case}**.

**Live inputs used:**  

- $\\varepsilon_x = {eps_x:.5f}$  
- $d_v = {d_v:.1f}$ mm  
- $A_{{sv}}/s = {Asv_over_s:.3f}\\ \\text{{mm}}^2/\\text{{mm}}$  
- $(A_{{sv}}/s)_{{min}} = {Asv_min_over_s:.3f}\\ \\text{{mm}}^2/\\text{{mm}}$  

**Formula used for $k_v$ (simplified branch):**

{kv_governing_formula}

$$k_v = {canonical_k_v:.3f}$$

**Formula used for $\\theta_v$ (governing branch):**

{theta_formula_block}

**Numerical substitution:**

{theta_sub_block}
"""

        check5_calc_md = f"""
*Purpose: Determine the shear parameters $k_v$ and $\\theta_v$ for use in $V_{{uc}}$ and web-crushing checks.*

**Inputs:**

- Concrete: $f'_c = {fc:.1f}$ MPa  
- Geometry: $b_v = {b_v:.1f}$ mm, $d_v = {d_v:.1f}$ mm, $d_g = {d_g:.1f}$ mm  
- Transverse steel: $A_{{sv}} = {Asv:.1f}$ mm², spacing $s = {s:.1f}$ mm, $f_{{sy,v}} = {f_syv:.1f}$ MPa  
- Aggregate size factor: {"$k_{{dg}} \\approx " + f"{k_dg_display:.3f}$" if use_general_kv else "not used in simplified branch"}  
- Strain: $\\varepsilon_x = {eps_x:.5f}$  

---

{kv_formula_block}

**Governing result:**  

- $k_v = {canonical_k_v:.3f}$  
- Governing compression field angle: $\\theta_v = {canonical_theta_v_deg:.1f}°$

**Interpretation:**  

This is the MCFT compression field angle used in the shear check.  
The STM strut annotation uses this same representative angle.

"""
            
        # Diagram render function
        def check5_diagram_fn():
            # Theta diagram on the right
            theta_path = os.path.join("assets", "theta.png")
            if os.path.exists(theta_path):
                st.image(theta_path, caption="Strut angle $\\theta_v$", use_container_width=True)
            else:
                st.info(f"💡 Add theta diagram at `{theta_path}`.")

        # Info render function (popover)
        def check5_info_fn():
            col_info_header, _ = st.columns([0.1, 0.9])
            with col_info_header:
                with info_i_button(help_text="MCFT parameters (what kv and θv represent)"):
                    st.markdown(r"""
### MCFT parameters

**kv (concrete effectiveness factor)**

kv represents the effectiveness of cracked concrete in resisting shear.  

Lower kv generally means more cracking/deformation and less concrete shear contribution.

**θv (crack angle)**

θv is the average diagonal crack angle in the web.  

It influences how shear is resolved into diagonal compression and stirrup tension.

These are treated as model parameters obtained directly from AS 3600 relationships.
                    """)
        
        # Build summary line
        check5_summary = f"Check 5 — MCFT parameters ($k_v$ and $\\theta_v$) | Result: $k_v = {k_v:.3f}$, $\\theta_v = {theta_v_deg:.1f}°$"
        
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
        
        # Diagram render function
        def check6_diagram_fn():
            _safe_step_diagram(6)
        
        # Info render function (popover)
        def check6_info_fn():
            col_info_header, _ = st.columns([0.1, 0.9])
            with col_info_header:
                with info_i_button(use_container_width=True):
                    st.markdown("### Check 6 – Concrete contribution $V_{uc}$")
                    st.markdown(
                        r"""
- In the MCFT model used by AS 3600, concrete shear strength at the critical section is

  $$V_{uc} = k_v b_v d_v \sqrt{f'_c}$$  

- The factor $k_v$ depends mainly on **longitudinal strain** $\varepsilon_x$ and crack spacing:  

  higher tensile strain → wider cracks → **smaller $k_v$** → smaller $V_{uc}$.

- $V_{uc}$ represents the combined effect of:  

  - residual shear across cracks,  

  - **aggregate interlock**, and  

  - **dowel action** from longitudinal bars.

This step isolates the **concrete-only** contribution before we add the stirrup shear $V_s$.
"""
                    )
        
        # Build summary line
        check6_summary = f"Check 6 — Concrete shear strength $V_{{uc}}$ | Result: $V_{{uc}} = {Vuc_kN:,.1f}$ kN"
        
        render_expandable_step(
            page_key="shear",
            step_id="shear_check6",
            title="Check 6 — Concrete shear strength V_uc",
            summary_md=check6_summary,
            status_kind=None,
            calc_md=check6_calc_md,
            diagram_render_fn=check6_diagram_fn,
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



- $A_{{sv}} = {Asv:.1f}$ mm², spacing $s = {s:.1f}$ mm  

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
            # Move the steel ligature diagram here
            _safe_image(
                "assets/shear_ligatures_and_crack.png",
                caption="Shear ligatures crossing a diagonal crack over $d_v \\cot\\theta_v$.",
            )

        # Info render function (popover)
        def check7_info_fn():
            col_info_header, _ = st.columns([0.1, 0.9])
            with col_info_header:
                with info_i_button(use_container_width=True):
                    st.markdown("### Check 7 – How stirrups contribute $V_s$")
                    calcbox(
                        r"""
**Steel contribution $V_s$**

- Vertical or inclined shear ligatures cross the **inclined crack length**  

  $$\ell_{cr} \approx d_v \cot\theta_v$$  

- Within a spacing $s$, the amount of steel crossing the crack is  

  $$n = \frac{d_v \cot\theta_v}{s}$$  

- The shear carried by stirrups is  

  $$V_s = V_{us} = \frac{A_{sv} f_{sy,v} d_v}{s}\,\cot\theta_v$$  

- Shear steel **raises total shear capacity**, but more importantly it provides **ductility** and helps control crack widths after concrete has cracked.
"""
                    )
        
        # Build summary line
        check7_summary = f"Check 7 — Steel shear strength $V_s$ | Result: $V_s = V_{{us}} = {Vus_kN:,.1f}$ kN"
        
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
            
        # Diagram render function
        def check8_diagram_fn():
            _safe_step_diagram(6)  # or a new combined diagram if you add one later

        # Info render function (popover)
        def check8_info_fn():
            col_info_header, _ = st.columns([0.1, 0.9])
            with col_info_header:
                with info_i_button(help_text="Sectional shear capacity (Vu components)"):
                    st.markdown(r"""
### Sectional shear capacity

**Concrete contribution (Vuc)**

Vuc is the concrete web contribution to shear resistance (as modified by kv and section geometry).

**Steel contribution (Vus)**

Vus is the stirrup contribution: shear reinforcement crossing diagonal cracks resists shear through tension.

**Why they add**

Concrete and stirrups act together, so the sectional capacity is taken as:

\[
V_u = V_{uc} + V_{us} + P_v
\]

and the design capacity is \( \phi V_u \).

This popover is intentionally capacity-only (no MCFT theory here).
                    """)
        
        # Build summary line
        pass_fail = "PASS" if shear_ok else "FAIL"
        check8_summary = f"Check 8 — Sectional shear capacity check | Result: $\\phi V_u = {phi_Vu:,.1f}$ kN vs $V_{{eq}}^* = {V_eq:.1f}$ kN → **{pass_fail}**"
        
        render_expandable_step(
            page_key="shear",
            step_id="shear_check8",
            title="Check 8 — Sectional shear capacity",
            summary_md=check8_summary,
            status_kind=shear_status,
            calc_md=check8_calc_md,
            diagram_render_fn=check8_diagram_fn,
            info_render_fn=check8_info_fn,
        )

        # =====================================================
        # Check 9 — WEB CRUSHING CHECK
        # =====================================================
        if not web_ok:
            st.error("Web-crushing limit exceeded – revise section/ligs.")

        check9_calc_md = f"""
*Purpose: Check that combined shear + torsion does not exceed the web-crushing limit (Cl. 8.2.6).*  

**Inputs:**  

- $f'_c = {fc:.1f}$ MPa, $b_v = {b_v:.1f}$ mm, $d_v = {d_v:.1f}$ mm  
- $\\theta_v = {theta_v_deg:.1f}^\\circ$, $\\theta_1 = {theta_1_deg:.1f}^\\circ$  
- $P_v = {P_v:.1f}$ kN  
- Actions: $V^* = {V_star:.1f}$ kN, $T^* = {T_star:.1f}$ kNm  
- Torsion geometry: $u_h = {uh:.1f}$ mm, $A_{{oh}} = {A_oh:.1f}$ mm²  

---

**Web-crushing shear capacity (Cl. 8.2.6):**  

$$\\large V_{{u,\\max}} = 0.55 f'_c b_v d_v \\frac{{\\cot\\theta_v + \\cot\\theta_1}}{{1 + \\cot^2\\theta_v}} + P_v$$

**Substitution:**  

$$\\large V_{{u,\\max}} = 0.55 \\times {fc:.1f} \\times {b_v:.1f} \\times {d_v:.1f} \\times \\frac{{\\cot({theta_v_deg:.1f}^\\circ) + \\cot({theta_1_deg:.1f}^\\circ)}}{{1 + \\cot^2({theta_v_deg:.1f}^\\circ)}} + {P_v:.1f} = {Vu_max_kN:,.1f}\\,\\text{{kN}}$$

---

**Combined shear + torsion demand (per unit $b_v d_v$):**  

$$\\large \\text{{Demand}} = \\sqrt{{\\left(\\frac{{V^*}}{{b_v d_v}}\\right)^2 + \\left(\\frac{{T^* u_h}}{{1.7 A_{{oh}}^2}}\\right)^2}}$$

**Substitution:**  

$$\\large \\text{{Demand}} = \\sqrt{{\\left(\\frac{{{V_star:.1f}}}{{{b_v:.1f} \\times {d_v:.1f}}}\\right)^2 + \\left(\\frac{{{T_star:.1f} \\times {uh:.1f}}}{{1.7 \\times {A_oh:.1f}^2}}\\right)^2}} = {LHS:,.1f}$$

---

**Design limit (web-crushing capacity per unit $b_v d_v$):**  

$$\\large \\text{{Capacity}} = \\frac{{\\phi V_{{u,\\max}}}}{{b_v d_v}}$$

**Substitution:**  

$$\\large \\text{{Capacity}} = \\frac{{{phi:.2f} \\times {Vu_max_kN:,.1f}}}{{{b_v:.1f} \\times {d_v:.1f}}} = {RHS:,.1f}$$

---

**Web-crushing check:**  

- Requirement: Demand $\\le$ Capacity  
- Here: {LHS:,.1f} vs {RHS:,.1f} → **{"OK" if web_ok else "NOT OK"}**
"""
            
        # Diagram render function
        def check9_diagram_fn():
            _safe_step_diagram(7)

        # Info render function (popover)
        def check9_info_fn():
            col_info_header, _ = st.columns([0.1, 0.9])
            with col_info_header:
                with info_i_button(help_text="Web crushing (strut failure cap)"):
                    st.markdown(r"""
### Web crushing (strut failure limit)

**What web crushing is**

Web crushing is failure of the diagonal concrete compression struts in a cracked web under high shear.

**Why it is independent of stirrups**

Once the compression struts reach their crushing capacity, adding more shear reinforcement cannot prevent failure.  

The limit is governed by concrete compressive capacity.

**Why it caps shear capacity**

This check provides an upper bound on shear resistance to prevent brittle compression failures.  

Regardless of reinforcement, design shear capacity cannot exceed this limit.
                    """)
        
        # Build summary line
        web_pass_fail = "PASS" if web_ok else "FAIL"
        check9_summary = f"Check 9 — Web-crushing strength check | Result: Demand {LHS:,.1f} vs Capacity {RHS:,.1f} → **{web_pass_fail}**"
        
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
    # TAB 3: Shear reinforcement checks
    # =====================================================
    with tab3:
        st.caption("Minimum shear reinforcement and detailing requirements.")
        st.markdown(
            """
**What this controls**

- Shear links hold diagonal cracks together after the web cracks and help stop a sudden brittle shear failure.
- Reducing spacing usually increases the amount of steel crossing a crack more directly than just increasing bar size.
- Adding more legs helps when one crack needs to be intercepted by more steel across the web width.

**When to change it**

- Tighten spacing first when shear demand is high.
- Increase legs when spacing is already practical but the web still needs more shear steel.
"""
        )

        # =====================================================
        # Check 10 — MINIMUM SHEAR REINFORCEMENT CHECK
        # =====================================================
        check10_calc_md = f"""
*Purpose: Check that provided shear reinforcement meets minimum requirements (AS 3600 Cl. 8.2.5).*

**Inputs:**

- Provided: $A_{{sv}} = {Asv:.1f}$ mm², spacing $s = {s:.1f}$ mm  
- Concrete: $f'_c = {fc:.1f}$ MPa  
- Geometry: $b_v = {b_v:.1f}$ mm  
- Steel: $f_{{sy,v}} = {f_syv:.1f}$ MPa  

---

**Provided reinforcement rate:**

$$\\frac{{A_{{sv}}}}{{s}} = \\frac{{{Asv:.1f}}}{{{s:.1f}}} = {Asv_over_s:.3f}\\ \\text{{mm}}^2/\\text{{mm}}$$

**Minimum required (AS 3600 Cl. 8.2.5):**

$$\\left(\\frac{{A_{{sv}}}}{{s}}\\right)_{{min}} = 0.08\\sqrt{{f'_c}} \\cdot \\frac{{b_v}}{{f_{{sy,v}}}} = 0.08\\sqrt{{{fc:.1f}}} \\cdot \\frac{{{b_v:.1f}}}{{{f_syv:.1f}}} = {Asv_min_over_s:.3f}\\ \\text{{mm}}^2/\\text{{mm}}$$

---

**Check:**

- Requirement: $A_{{sv}}/s \\ge (A_{{sv}}/s)_{{min}}$  
- Here: {Asv_over_s_check10:.3f} vs {Asv_min_over_s_check10:.3f} → **{"OK" if min_shear_ok else "NOT OK"}**
"""
            
        # Diagram render function
        def check10_diagram_fn():
            _safe_step_diagram(8)  # Step 8 diagram (ligature spacing)
        
        # Info render function (popover)
        def check10_info_fn():
            col_info_header, _ = st.columns([0.1, 0.9])
            with col_info_header:
                with info_i_button(help_text="Minimum shear reinforcement (ductility)"):
                    st.markdown(r"""
### Minimum shear reinforcement

**Why minimum stirrups are required**

Even if calculated shear demand is low, minimum transverse reinforcement is required to:

- control crack development,

- provide ductility and robustness, and

- ensure a reliable shear mechanism after cracking.

**What this check is doing**

This compares the provided reinforcement rate \(A_{sv}/s\) against the minimum required by AS 3600 for the given section and material properties.

If the provided rate is below minimum, shear behaviour assumptions become unreliable and detailing must be increased.
                    """)
        
        # Build summary line
        min_pass_fail = "PASS" if min_shear_ok else "FAIL"
        check10_summary = f"Check 10 — Minimum shear reinforcement check | Result: $A_{{sv}}/s = {Asv_over_s_check10:.3f}$ vs $(A_{{sv}}/s)_{{min}} = {Asv_min_over_s_check10:.3f}$ → **{min_pass_fail}**"
        
        render_expandable_step(
            page_key="shear",
            step_id="shear_check10",
            title="Check 10 — Minimum shear reinforcement",
            summary_md=check10_summary,
            status_kind=min_shear_status,
            calc_md=check10_calc_md,
            diagram_render_fn=check10_diagram_fn,
            info_render_fn=check10_info_fn,
        )

        # =====================================================
        # Check 11 — DETAILING AND DEEP BEAM NOTE
        # =====================================================
        check11_calc_md = f"""
*Purpose: Provide guidance on ligature spacing, detailing requirements, and when strut-and-tie analysis is needed.*

**Ligature spacing and detailing along the span (AS 3600 Cl. 8.2.5.1):**

- Where the required shear reinforcement **$A_{{sv}}/s$ varies** along the member, the code assumes a **linear variation** over each segment.  
- Detailing should follow the **recommended patterns** (e.g. Figure C8.2.5.1), so that provided $A_{{sv}}/s$ ≥ required $A_{{sv}}/s$ in the **critical region**.  
- Proper spacing is essential because shear failure due to **yielding of ligatures** tends to occur in a **localized zone** near peak shear.  
- The goal is to avoid "gaps" in shear resistance where the **provided envelope drops below the required line**.

**Detailing requirements:**

- Stirrups must be properly anchored (AS 3600 Cl. 8.2.5)  
- Maximum spacing: $s \\le \\min(0.75D, 500\\ \\text{{mm}})$  
- Minimum spacing: sufficient for concrete placement and consolidation  

**When to use strut-and-tie model:**

- Deep beams (span/depth < 2.5)  
- Disturbed regions (loads within $d_v$ of support)  
- Significant point loads near supports  
- Complex geometry or loading patterns  

**Note:** This step is informational. Detailed strut-and-tie analysis should be performed separately when required.
"""
        
        # Diagram render function
        def check11_diagram_fn():
            # Ligature spacing diagram (moved from standalone section after Check 9)
            col_left, col_center, col_right = st.columns([1, 6, 1])
            with col_center:
                _safe_image(
                    "assets/shear_lig_spacing_code_diagram.png",
                    caption="Example of varying Asv/s along the span (AS 3600 Fig. C8.2.5.1).",
                )
        
        # Info render function (popover)
        def check11_info_fn():
            col_info_header, _ = st.columns([0.1, 0.9])
            with col_info_header:
                with info_i_button(help_text="Detailing + when strut-and-tie governs"):
                    st.markdown(r"""
### Detailing and deep-beam behaviour

**Why detailing matters**

Shear capacity equations assume:

- reinforcement is properly anchored,

- cracks are intercepted by stirrups,

- spacing is not excessive, and

- the shear-resisting zone is well confined.

**When to consider strut-and-tie**

For short shear spans (deep beams / disturbed regions), the stress field is not beam-like.  

In these cases, a strut-and-tie model may govern and web crushing / strut behaviour becomes critical.

**Placeholders for diagrams**

- [Diagram] θ definition / crack angle  

- [Diagram] Strut-and-tie behaviour in deep beams  

- [Diagram] Web crushing mechanism
                    """)

        # Build summary line
        check11_summary = "Check 11 — Detailing and deep-beam considerations | Informational guidance (no pass/fail check)"
        
        render_expandable_step(
            page_key="shear",
            step_id="shear_check11",
            title="Check 11 — Detailing and deep-beam considerations",
            summary_md=check11_summary,
            status_kind=None,
            calc_md=check11_calc_md,
            diagram_render_fn=check11_diagram_fn,
            info_render_fn=check11_info_fn,
        )

    # =======================================================
    # 9. SUMMARY TABLE + PUSH RESULTS
    # =======================================================
    # Note: torsion_required, V_eq, phi_Vu, etc. are computed inside tabs but need to be accessible here
    # They are already computed in tab_dim (torsion_required, V_eq) and tab_reinf (phi_Vu, shear_ok)
    # We need to ensure these are available at module scope or recompute them here
    # For now, we'll use the values computed in the tabs (they should be in scope)
    shear_pack = build_shear_check_rows_from_state(st.session_state)
    rows_summary = [
        {
            "Check": r.get("title", ""),
            "Value": r.get("value", ""),
            "Limit": r.get("limit", ""),
            "Utilisation": r.get("util", ""),
            "Status": r.get("status", ""),
            "is_informational": bool(r.get("is_informational", False)),
        }
        for r in (shear_pack.get("rows") or [])
    ]
    summary_util = (shear_results.V_eq / shear_results.phi_Vu) if shear_results.phi_Vu > 0 else float("nan")
    summary_phi_vu_max = phi * shear_results.Vu_max_kN
    summary_web_util = (shear_results.V_eq / summary_phi_vu_max) if summary_phi_vu_max > 0 else float("nan")

    summary_overrides = {
        "Sectional shear capacity": {
            "Value": f"φVu = {shear_results.phi_Vu:.1f} kN",
            "Limit": f"V*eq = {shear_results.V_eq:.1f} kN",
            "Utilisation": f"{summary_util:.2f}" if not math.isnan(summary_util) else "—",
            "Status": "PASS" if summary_util <= 1.0 else "FAIL",
        },
        "Equivalent design shear": {
            "Value": f"V*eq = {shear_results.V_eq:.1f} kN",
        },
        "Longitudinal strain": {
            "Value": f"εx = {shear_results.eps_x:.5f}",
        },
        "Shear model parameters": {
            "Value": f"k_v = {shear_results.k_v:.3f}, θ_v = {shear_results.theta_v_deg:.1f}°",
        },
        "Concrete shear strength": {
            "Value": f"Vuc = {shear_results.Vuc_kN:.1f} kN",
        },
        "Steel shear strength": {
            "Value": f"Vs = Vus = {shear_results.Vus_kN:.1f} kN",
        },
        "Web-crushing strength": {
            "Value": f"φVu,max = {summary_phi_vu_max:.1f} kN",
            "Limit": f"V*eq = {shear_results.V_eq:.1f} kN",
            "Utilisation": f"{summary_web_util:.2f}" if not math.isnan(summary_web_util) else "—",
            "Status": "PASS" if summary_web_util <= 1.0 else "FAIL",
        },
    }
    for row in rows_summary:
        override = summary_overrides.get(row.get("Check", ""))
        if override:
            row.update(override)

    # Publish key shear results for Inputs summary
    shear_util = summary_util
    update_results(
        phi_Vu_cap=float(shear_results.phi_Vu or 0.0),
        Vu_utilisation=float(shear_util) if shear_util is not None and not math.isnan(shear_util) else 0.0,
    )

    # Map summary rows -> step UIDs and anchor IDs
    check_to_uid = {
        "Torsion cracking check": "shear_check1",
        "Equivalent design shear": "shear_check2",
        "Longitudinal strain": "shear_check4",
        "Shear model parameters": "shear_check5",
        "Concrete shear strength": "shear_check6",
        "Steel shear strength": "shear_check7",
        "Sectional shear capacity": "shear_check8",
        "Web-crushing strength": "shear_check9",
    }

    # Map summary rows -> tab labels (for tab switching on click)
    check_to_tab = {
        "Torsion cracking check": "Torsion + dimensions",
        "Equivalent design shear": "Torsion + dimensions",
        "Longitudinal strain": "MCFT and strength checks",
        "Shear model parameters": "MCFT and strength checks",
        "Concrete shear strength": "MCFT and strength checks",
        "Steel shear strength": "MCFT and strength checks",
        "Sectional shear capacity": "MCFT and strength checks",
        "Web-crushing strength": "MCFT and strength checks",
    }

    _shear_summary_headline_checks = {
        "Sectional shear capacity",
        "Torsion cracking check",
        "Web-crushing strength",
    }
    _shear_summary_mcft_detail_checks = {
        "Equivalent design shear",
        "Longitudinal strain",
        "Shear model parameters",
        "Concrete shear strength",
        "Steel shear strength",
    }

    _shear_summary_row_priority = {
        "Sectional shear capacity": 0,
        "Torsion cracking check": 1,
        "Web-crushing strength": 2,
        "Equivalent design shear": 3,
        "Longitudinal strain": 4,
        "Shear model parameters": 5,
        "Concrete shear strength": 6,
        "Steel shear strength": 7,
    }

    def _clickable_rows_from_shear_summary(rows_list: list[dict]) -> list[dict]:
        out = []
        for row in rows_list:
            check = row["Check"]
            uid = check_to_uid.get(check)
            if not uid:
                continue
            status_str = str(row.get("Status", "")).upper()
            is_info = bool(row.get("is_informational", False))
            ok = None
            if not is_info and status_str != "INFO":
                if status_str == "PASS":
                    ok = True
                elif status_str in ("FAIL", "NG", "CHECK"):
                    ok = False
            tab = check_to_tab.get(check, "")
            out.append(
                {
                    "uid": uid,
                    "title": check,
                    "value": row.get("Value", ""),
                    "limit": row.get("Limit", ""),
                    "util": row.get("Utilisation", ""),
                    "status": status_str,
                    "ok": ok,
                    "tab": tab,
                    "is_primary": (check == "Sectional shear capacity"),
                    "is_informational": is_info,
                    "anchor_id": uid,
                }
            )
        out.sort(key=lambda r: _shear_summary_row_priority.get(r["title"], 99))
        return out

    rows_summary_full = rows_summary
    ROWS_FULL = _clickable_rows_from_shear_summary(rows_summary_full)
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
        display_rows = [
            r
            for r in rows_summary_full
            if r["Check"] in _shear_summary_headline_checks
            or (show_mcft_breakdown and r["Check"] in _shear_summary_mcft_detail_checks)
        ]
        ROWS_DISPLAY = _clickable_rows_from_shear_summary(display_rows)
        render_clickable_summary_table(ROWS_DISPLAY, key_prefix="shear_summary")
        if not show_mcft_breakdown:
            st.caption(
                'Intermediate MCFT calculation rows hidden. Enable "Show detailed MCFT breakdown" to view.'
            )
        bind_summary_clicks()

        page_divider()


if __name__ == "__main__":
    render_shear()
