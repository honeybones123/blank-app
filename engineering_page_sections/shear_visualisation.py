"""Shear visualisation layout and support adapters."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import numpy as np
import plotly.graph_objects as go
import streamlit as st

from shear_visuals import (
    BEHAVIOUR_VISUAL_HEIGHT,
    BEHAVIOUR_VISUAL_WIDTH,
    SIDE_VIEW_VISUAL_WIDTH,
)
from widgets_helpers import (
    COMPACT_SIDE_VIEW_HEIGHT_PX,
    compact_side_view_figure,
    inject_compact_side_view_spacing,
    render_plotly_diagram,
)


SHEAR_VISUAL_HEIGHT_PX = BEHAVIOUR_VISUAL_HEIGHT
SHEAR_BEHAVIOUR_MAX_WIDTH_PX = BEHAVIOUR_VISUAL_WIDTH
SHEAR_SIDE_VIEW_MAX_WIDTH_PX = SIDE_VIEW_VISUAL_WIDTH
SHEAR_VISUAL_MAX_WIDTH_PX = 760
SHEAR_VISUAL_CONFIG = {
    "displayModeBar": False,
    "responsive": True,
}
MCFT_BEHAVIOUR_MARGIN = dict(l=10, r=10, t=8, b=10)


@dataclass(frozen=True)
class ShearVisualisationRuntime:
    """Explicit application dependencies for the Shear diagram viewport."""

    st: Any
    get_param: Callable[..., Any]
    render_timing_mark: Callable[[str], None]
    render_plotly_diagram: Callable[..., Any]
    render_centered_plotly: Callable[..., Any]
    render_section_title: Callable[[str], Any]
    render_tabs: Callable[..., Any]
    build_cross_section_figure: Callable[..., go.Figure]
    build_side_view_figure: Callable[..., go.Figure]
    build_sfd_bmd_figure: Callable[..., tuple[go.Figure, go.Figure]]

def _support_pair_from_resolved_support_type(support_type: str | None) -> tuple[str, str] | None:
    raw_label = str(support_type or "").strip()
    label = raw_label.replace("-", "–")
    if not label:
        return None
    if raw_label == "Fixed-ended":
        return ("Fixed", "Fixed")
    if label == "Fixed–Pinned":
        return ("Fixed", "Pinned")
    if label == "Pinned–Fixed":
        return ("Pinned", "Fixed")
    if label in ("Pinned–Pinned", "Continuous – end span", "Continuous – interior span"):
        return ("Pinned", "Pinned")
    if label == "Simply supported":
        return ("Pinned", "Roller")
    return None

def _coalesce_num(v, default: float) -> float:
    """Return default only if v is None (preserves 0)."""
    return default if v is None else float(v)

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
    title_pad_t: int = 28,
    compact_top: bool = False,
    config: dict | None = None,
):
    """Mount a Shear Plotly figure in the established centered frame."""

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


def _render_shear_cross_section(runtime: ShearVisualisationRuntime) -> None:
    runtime.render_timing_mark("shear.visualisation.section.build.start")
    inject_compact_side_view_spacing("shear-section-compact")
    figure = runtime.build_cross_section_figure(
        height=COMPACT_SIDE_VIEW_HEIGHT_PX
    )
    figure = compact_side_view_figure(
        _standardise_shear_visual_layout(figure, title_pad_t=8)
    )
    runtime.render_timing_mark("shear.visualisation.section.build.end")
    runtime.render_timing_mark("shear.visualisation.section.mount.start")
    runtime.render_centered_plotly(
        figure,
        chart_key="shear_section_diagram",
        max_width_px=SHEAR_VISUAL_MAX_WIDTH_PX,
        height_px=COMPACT_SIDE_VIEW_HEIGHT_PX,
        title_pad_t=8,
    )
    runtime.render_timing_mark("shear.visualisation.section.mount.end")


def _render_shear_side_view(runtime: ShearVisualisationRuntime) -> None:
    runtime.render_timing_mark("shear.visualisation.side.build.start")
    inject_compact_side_view_spacing("shear-side-view-compact")
    try:
        phi_vu = float(runtime.get_param("phi_Vu_cap") or 0.0)
        v_eq = float(runtime.get_param("V_eq_kN") or 0.0)
    except (TypeError, ValueError):
        phi_vu, v_eq = 0.0, 0.0
    shear_fails = phi_vu > 0.0 and v_eq > phi_vu + 1e-9
    runtime.st.caption(
        "Side view: when Check 10 layout exists, stirrups follow required zone spacings from the envelope; "
        "otherwise at provided spacing (input s_lig). \u03c6V_u uses effective spacing from results (provided or "
        "required when \u201cApply auto spacing\u201d is on)."
        if shear_fails
        else "Side view: required zone spacings from Check 10 when available; otherwise provided spacing (s_lig). "
        "\u03c6V_u check uses effective spacing (provided unless auto spacing applies envelope spacing)."
    )
    figure = compact_side_view_figure(
        runtime.build_side_view_figure(
            shear_fails=shear_fails,
            height=COMPACT_SIDE_VIEW_HEIGHT_PX,
        )
    )
    runtime.render_timing_mark("shear.visualisation.side.build.end")
    runtime.render_timing_mark("shear.visualisation.side.mount.start")
    runtime.render_centered_plotly(
        figure,
        chart_key="shear_side_view_diagram",
        max_width_px=SHEAR_SIDE_VIEW_MAX_WIDTH_PX,
        height_px=COMPACT_SIDE_VIEW_HEIGHT_PX,
        title_pad_t=8,
    )
    runtime.render_timing_mark("shear.visualisation.side.mount.end")


def _resolve_shear_visual_supports(
    runtime: ShearVisualisationRuntime,
    length_m: float,
) -> tuple[list[float], list[str]]:
    from deflection_support import (
        _governing_span_support_pair,
        get_deflection_diagram_support_condition,
    )

    support_positions: list[float] = []
    support_types: list[str] = []
    beam_mode = str(
        runtime.get_param("design_beam_system_mode", "Single span") or "Single span"
    )
    support_resolution = get_deflection_diagram_support_condition(
        runtime.st.session_state
    )
    support_pair = _governing_span_support_pair(
        runtime.st.session_state,
        support_resolution,
    )

    if (
        beam_mode == "Multi-span"
        and isinstance(support_pair, tuple)
        and len(support_pair) == 2
    ):
        try:
            span_count = max(
                1,
                int(
                    float(
                        runtime.st.session_state.get("sfd_span_count", 0.0)
                        or 0.0
                    )
                ),
            )
        except Exception:
            span_count = 1
        controlling_index = int(
            support_resolution.get("controlling_span_idx", 0) or 0
        )
        controlling_index = max(0, min(controlling_index, span_count - 1))
        try:
            span_length_m = float(
                runtime.st.session_state.get(
                    f"sfd_span_len_{controlling_index + 1}", 0.0
                )
                or 0.0
            )
        except Exception:
            span_length_m = 0.0
        if abs(float(span_length_m) - float(length_m)) <= 1e-6:
            support_positions = [0.0, float(length_m)]
            support_types = [str(support_pair[0]), str(support_pair[1])]

    if not support_positions or not support_types:
        support_label = str(
            support_resolution.get("support_type")
            or runtime.get_param("defl_support_type", "Simply supported")
            or "Simply supported"
        )
        support_pair_fallback = _support_pair_from_resolved_support_type(
            support_label
        )
        if "cantilever" in support_label.lower():
            support_positions = [0.0]
            support_types = ["Fixed"]
        elif (
            isinstance(support_pair_fallback, tuple)
            and len(support_pair_fallback) == 2
        ):
            support_positions = [0.0, float(length_m)]
            support_types = [
                str(support_pair_fallback[0]),
                str(support_pair_fallback[1]),
            ]
        else:
            support_positions = [0.0, float(length_m)]
            support_types = ["Pinned", "Roller"]

    return support_positions, support_types


def _render_shear_force_diagram(runtime: ShearVisualisationRuntime) -> None:
    runtime.render_timing_mark("shear.visualisation.force.build.start")
    mode = str(
        runtime.get_param("actions_mode", "manual") or "manual"
    ).strip().lower()
    length_m = max(
        float(runtime.get_param("L", 3000.0) or 3000.0) / 1000.0,
        0.1,
    )
    shear_x_raw = np.asarray(
        runtime.get_param("shear_x", []) or [],
        dtype=float,
    )
    shear_v_signed_raw = np.asarray(
        runtime.get_param("shear_V_signed", []) or [],
        dtype=float,
    )
    shear_v_raw = np.asarray(
        runtime.get_param("shear_V", []) or [],
        dtype=float,
    )
    support_type = str(
        runtime.get_param(
            "support_type",
            runtime.get_param("defl_support_type", "simply_supported"),
        )
        or "simply_supported"
    ).strip().lower()

    if mode == "design" and shear_x_raw.size > 1:
        if shear_v_signed_raw.size == shear_x_raw.size:
            x_plot = shear_x_raw
            v_plot = shear_v_signed_raw
        elif shear_v_raw.size == shear_x_raw.size:
            x_plot = shear_x_raw
            v_plot = shear_v_raw
        else:
            x_plot = np.linspace(0.0, length_m, 100)
            v_plot = np.zeros_like(x_plot, dtype=float)
    else:
        x_plot = np.linspace(0.0, length_m, 100)
        v_star = float(runtime.get_param("uls_Vstar", 0.0) or 0.0)
        if "cantilever" in support_type:
            v_plot = v_star * (1.0 - x_plot / max(length_m, 1e-9))
        else:
            v_plot = v_star * (1.0 - 2.0 * x_plot / max(length_m, 1e-9))

    support_positions, support_types = _resolve_shear_visual_supports(
        runtime,
        length_m,
    )
    figure, _ = runtime.build_sfd_bmd_figure(
        x=x_plot,
        V=v_plot,
        M=np.zeros_like(x_plot, dtype=float),
        L=length_m,
        support_positions=support_positions,
        support_types=support_types,
    )
    figure.update_layout(height=320)
    runtime.render_timing_mark("shear.visualisation.force.build.end")
    runtime.st.caption("Shear V(x)")
    runtime.render_timing_mark("shear.visualisation.force.mount.start")
    runtime.render_plotly_diagram(
        figure,
        key="shear_visual_sfd_diagram",
        title="Shear force diagram",
        config=SHEAR_VISUAL_CONFIG,
    )
    runtime.render_timing_mark("shear.visualisation.force.mount.end")

def _render_plotly_in_mcft_column(
    fig: go.Figure,
    *,
    chart_key: str,
    render_centered_plotly: Callable[..., Any],
) -> None:
    """MCFT static Plotly: same pipeline as side view / cross-section (full-width block)."""
    render_centered_plotly(
        fig,
        chart_key=chart_key,
        max_width_px=SHEAR_BEHAVIOUR_MAX_WIDTH_PX,
        height_px=SHEAR_VISUAL_HEIGHT_PX,
        title_pad_t=int(MCFT_BEHAVIOUR_MARGIN["t"]),
        compact_top=True,
    )

def _render_mcft_behaviour_chart(
    fig: go.Figure,
    *,
    chart_key: str,
    animated: bool,
    render_centered_plotly: Callable[..., Any],
    render_animated_plotly: Callable[..., Any],
    height_px: int | None = None,
) -> None:
    plot_h = int(height_px or fig.layout.height or SHEAR_VISUAL_HEIGHT_PX)
    if animated:
        render_animated_plotly(
            fig,
            height=plot_h,
            centered=True,
            chart_key=chart_key,
            compact_top=True,
            title_pad_t=int(MCFT_BEHAVIOUR_MARGIN["t"]),
            max_width_px=int(BEHAVIOUR_VISUAL_WIDTH),
        )
    else:
        render_centered_plotly(
            fig,
            chart_key=chart_key,
            max_width_px=SHEAR_BEHAVIOUR_MAX_WIDTH_PX,
            height_px=plot_h,
            title_pad_t=int(MCFT_BEHAVIOUR_MARGIN["t"]),
            compact_top=True,
        )


def render_shear_visualisation_block(
    runtime: ShearVisualisationRuntime,
) -> None:
    """Render the established three-tab Shear diagram viewport.

    Diagram builders and Streamlit mounting remain explicit dependencies.  The
    orchestration module therefore owns layout only and cannot read or mutate
    engineering state behind the caller's back.
    """

    st = runtime.st
    with st.container():
        st.markdown(
            """
<style>
/* Shear page only: anchor is inside this container vertical block */
div[data-testid="stVerticalBlock"]:has(> div[data-testid="stElementContainer"] #shear-visuals-block) {
    margin-top: 0.25rem !important;
    padding-top: 0 !important;
}
div[data-testid="stVerticalBlock"]:has(> div[data-testid="stElementContainer"] #shear-visuals-block) .section-title {
    margin-bottom: 0.35rem !important;
}
div[data-testid="stVerticalBlock"]:has(> div[data-testid="stElementContainer"] #shear-visuals-block) h3,
div[data-testid="stVerticalBlock"]:has(> div[data-testid="stElementContainer"] #shear-visuals-block) h4 {
    margin-bottom: 0.35rem !important;
}
div[data-testid="stVerticalBlock"]:has(> div[data-testid="stElementContainer"] #shear-visuals-block) [data-testid="stPlotlyChart"] {
    margin-bottom: 0.2rem !important;
}
div[data-testid="stVerticalBlock"]:has(> div[data-testid="stElementContainer"] #shear-visuals-block) [data-testid="stTabs"] {
    margin-top: 0.35rem !important;
    padding-top: 0 !important;
}
div[data-testid="stVerticalBlock"]:has(> div[data-testid="stElementContainer"] #shear-visuals-block) div[data-testid="stRadio"] {
    margin-top: 0.25rem !important;
    padding-top: 0 !important;
}
div[data-testid="stVerticalBlock"]:has(> div[data-testid="stElementContainer"] #shear-visuals-block) label[data-testid="stWidgetLabel"] {
    margin-bottom: 0.2rem !important;
}
</style>
<div id="shear-visuals-block" class="shear-visuals-block" style="display:none;width:0;height:0;overflow:hidden;" aria-hidden="true"></div>
""",
            unsafe_allow_html=True,
        )
        runtime.render_section_title("Visualisation")
        side_view_tab, section_tab, shear_diagram_tab = runtime.render_tabs(
            st,
            labels=("Side view", "Section", "Shear diagram"),
            scope_id="shear-visualisation-diagrams",
        )
        with side_view_tab:
            _render_shear_side_view(runtime)
        with section_tab:
            _render_shear_cross_section(runtime)
        with shear_diagram_tab:
            _render_shear_force_diagram(runtime)


__all__ = [
    "MCFT_BEHAVIOUR_MARGIN",
    "SHEAR_SIDE_VIEW_MAX_WIDTH_PX",
    "SHEAR_BEHAVIOUR_MAX_WIDTH_PX",
    "SHEAR_VISUAL_CONFIG",
    "SHEAR_VISUAL_HEIGHT_PX",
    "SHEAR_VISUAL_MAX_WIDTH_PX",
    "ShearVisualisationRuntime",
    "_coalesce_num",
    "_render_centered_shear_plotly",
    "_render_mcft_behaviour_chart",
    "_render_plotly_in_mcft_column",
    "_render_shear_cross_section",
    "_render_shear_force_diagram",
    "_render_shear_side_view",
    "_resolve_shear_visual_supports",
    "_standardise_shear_visual_layout",
    "_support_pair_from_resolved_support_type",
    "render_shear_visualisation_block",
]
