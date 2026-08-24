"""Shear visualisation layout and support adapters."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import plotly.graph_objects as go
import streamlit as st

from shear_visuals import (
    BEHAVIOUR_VISUAL_HEIGHT,
    BEHAVIOUR_VISUAL_WIDTH,
    SIDE_VIEW_VISUAL_WIDTH,
)
from ui.design_tokens import BENDING_DIAGRAM_PLOT_HEIGHT_PX
from widgets_helpers import (
    compact_side_view_figure,
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
SHEAR_DIAGRAM_VIEWS = ("ULS", "SLS", "MCFT")
SHEAR_DIAGRAM_PLOT_HEIGHT_PX = BENDING_DIAGRAM_PLOT_HEIGHT_PX
SHEAR_SIDE_VIEW_CAPTION = (
    "Side view: required zone spacings from Check 10 when available; otherwise "
    "provided spacing (s_lig). φV_u check uses effective spacing (provided "
    "unless auto spacing applies envelope spacing)."
)


@dataclass(frozen=True)
class ShearVisualisationRuntime:
    """Explicit application dependencies for the Shear diagram viewport."""

    st: Any
    get_param: Callable[..., Any]
    render_timing_mark: Callable[[str], None]
    render_plotly_diagram: Callable[..., Any]
    render_centered_plotly: Callable[..., Any]
    render_animated_plotly: Callable[..., Any]
    render_section_title: Callable[[str], Any]
    render_tabs: Callable[..., Any]
    synchronize_tabs: Callable[..., Any]
    build_cross_section_figure: Callable[..., go.Figure]
    build_side_view_figure: Callable[..., go.Figure]
    theta_v_deg: float

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
    figure = runtime.build_cross_section_figure(
        height=SHEAR_DIAGRAM_PLOT_HEIGHT_PX
    )
    figure = compact_side_view_figure(
        _standardise_shear_visual_layout(figure, title_pad_t=8),
        height_px=SHEAR_DIAGRAM_PLOT_HEIGHT_PX,
    )
    runtime.render_timing_mark("shear.visualisation.section.build.end")
    runtime.render_timing_mark("shear.visualisation.section.mount.start")
    runtime.render_plotly_diagram(
        figure,
        key="shear_section_diagram",
        title="SLS shear section",
        center=True,
        config=SHEAR_VISUAL_CONFIG,
    )
    runtime.render_timing_mark("shear.visualisation.section.mount.end")


def _render_shear_side_view(runtime: ShearVisualisationRuntime) -> None:
    runtime.render_timing_mark("shear.visualisation.side.build.start")
    try:
        phi_vu = float(runtime.get_param("phi_Vu_cap") or 0.0)
        v_eq = float(runtime.get_param("V_eq_kN") or 0.0)
    except (TypeError, ValueError):
        phi_vu, v_eq = 0.0, 0.0
    shear_fails = phi_vu > 0.0 and v_eq > phi_vu + 1e-9
    figure = compact_side_view_figure(
        runtime.build_side_view_figure(
            shear_fails=shear_fails,
            height=SHEAR_DIAGRAM_PLOT_HEIGHT_PX,
        ),
        height_px=SHEAR_DIAGRAM_PLOT_HEIGHT_PX,
    )
    runtime.render_timing_mark("shear.visualisation.side.build.end")
    runtime.render_timing_mark("shear.visualisation.side.mount.start")
    runtime.render_plotly_diagram(
        figure,
        key="shear_side_view_diagram",
        title="ULS shear side view",
        center=True,
        config=SHEAR_VISUAL_CONFIG,
    )
    runtime.render_timing_mark("shear.visualisation.side.mount.end")


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


def _render_shear_diagram_loading_shell(
    runtime: ShearVisualisationRuntime,
    *,
    view_key: str,
    label: str,
) -> None:
    """Reserve the same 320 px canvas used by every live Shear diagram."""

    runtime.st.markdown(
        '<div class="shear-diagram-loading-region" '
        f'data-shear-diagram-shell="{view_key}" '
        'data-shear-diagram-geometry-token="--sb-bending-diagram-plot-height" '
        'role="status" aria-live="polite">'
        '<div class="shear-diagram-loading-shell">'
        '<span class="shear-diagram-loading-icon" aria-hidden="true">&#9711;</span>'
        f'<span class="shear-diagram-loading-copy">Preparing {label}</span>'
        '</div></div>',
        unsafe_allow_html=True,
    )


def _render_shear_uls_view(runtime: ShearVisualisationRuntime) -> None:
    """Render the established ULS reinforcement/side-view diagram."""

    _render_shear_side_view(runtime)


def _render_shear_sls_view(runtime: ShearVisualisationRuntime) -> None:
    """Render the established service section view without recalculation."""

    _render_shear_cross_section(runtime)


def _render_shear_mcft_view(runtime: ShearVisualisationRuntime) -> None:
    """Render the existing MCFT projection inside the shared diagram shell."""

    from engineering_page_sections.shear_stress_field import (
        render_mcft_stress_field_diagram,
    )

    render_mcft_stress_field_diagram(
        st_module=runtime.st,
        theta_v_deg=float(runtime.theta_v_deg),
        render_plotly_diagram=runtime.render_plotly_diagram,
        render_animated_plotly=runtime.render_animated_plotly,
        height_px=SHEAR_DIAGRAM_PLOT_HEIGHT_PX,
    )


def _render_stress_field_teaching(runtime: ShearVisualisationRuntime) -> None:
    from engineering_page_sections.shear_stress_field import (
        render_stress_field_teaching,
    )

    render_stress_field_teaching(
        st_module=runtime.st,
        theta_v_deg=float(runtime.theta_v_deg),
        render_centered_plotly=runtime.render_centered_plotly,
    )


def render_shear_visualisation_block(
    runtime: ShearVisualisationRuntime,
) -> None:
    """Render one stable ULS/SLS/MCFT Shear diagram viewport.

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
[data-testid="stTabs"][data-sb-tab-scope="shear-diagram-panels"] > [role="tablist"] {
    display: none !important;
}
[data-testid="stTabs"][data-sb-tab-scope="shear-diagram-panels"] [role="tabpanel"] {
    height: calc(var(--sb-bending-diagram-plot-height, 320px) + 4.75rem);
    min-height: calc(var(--sb-bending-diagram-plot-height, 320px) + 4.75rem);
    overflow: hidden;
}
[data-testid="stTabs"][data-sb-tab-scope="shear-diagram-navigation"] [role="tabpanel"] {
    display: none !important;
    height: 0 !important;
    min-height: 0 !important;
    margin: 0 !important;
    padding: 0 !important;
}
.st-key-shear_uls_plot_frame,
.st-key-shear_sls_plot_frame,
.st-key-shear_mcft_plot_frame {
    display: grid !important;
    grid-template-columns: minmax(0, 1fr) !important;
    width: 100%;
    min-height: var(--sb-bending-diagram-plot-height, 320px);
}
.st-key-shear_uls_plot_frame > div[data-testid="stLayoutWrapper"],
.st-key-shear_sls_plot_frame > div[data-testid="stLayoutWrapper"],
.st-key-shear_mcft_plot_frame > div[data-testid="stLayoutWrapper"] {
    grid-area: 1 / 1 !important;
    width: 100%;
    min-width: 0 !important;
    max-width: 100% !important;
}
.st-key-shear_uls_diagram_shell,
.st-key-shear_sls_diagram_shell,
.st-key-shear_mcft_diagram_shell {
    z-index: 2;
    height: var(--sb-bending-diagram-plot-height, 320px);
}
.st-key-shear_uls_diagram_live,
.st-key-shear_sls_diagram_live,
.st-key-shear_mcft_diagram_live {
    z-index: 1;
    height: var(--sb-bending-diagram-plot-height, 320px);
    min-height: var(--sb-bending-diagram-plot-height, 320px);
    overflow: hidden;
    gap: 0 !important;
}
.st-key-shear_uls_diagram_live [data-testid="stPlotlyChart"],
.st-key-shear_sls_diagram_live [data-testid="stPlotlyChart"],
.st-key-shear_mcft_diagram_live [data-testid="stPlotlyChart"],
.st-key-shear_mcft_diagram_live iframe {
    height: var(--sb-bending-diagram-plot-height, 320px) !important;
    min-height: var(--sb-bending-diagram-plot-height, 320px) !important;
    margin: 0 auto !important;
}
.st-key-shear_sls_diagram_live [data-testid="stPlotlyChart"] {
    max-width: 760px;
}
.st-key-shear_uls_diagram_live [data-testid="stPlotlyChart"],
.st-key-shear_mcft_diagram_live [data-testid="stPlotlyChart"],
.st-key-shear_mcft_diagram_live iframe {
    max-width: 1200px;
}
.st-key-shear_uls_diagram_caption,
.st-key-shear_sls_diagram_caption,
.st-key-shear_mcft_diagram_caption {
    box-sizing: border-box;
    height: 3rem;
    min-height: 3rem;
    overflow: hidden;
    margin: 0 !important;
    padding: .25rem 0 0 !important;
}
.st-key-shear_uls_diagram_caption [data-testid="stCaptionContainer"],
.st-key-shear_sls_diagram_caption [data-testid="stCaptionContainer"],
.st-key-shear_mcft_diagram_caption [data-testid="stCaptionContainer"] {
    margin: 0 !important;
}
.shear-diagram-loading-region {
    box-sizing: border-box;
    width: 100%;
    height: var(--sb-bending-diagram-plot-height, 320px);
    overflow: hidden;
    background: #fff;
    color: #10234a;
    pointer-events: none;
}
.shear-diagram-loading-shell {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: .7rem;
    height: 100%;
    padding: .85rem 1rem;
    border: 1px solid #cbd5e1;
    border-radius: 10px;
    background: #f8fafc;
    color: #475569;
}
.shear-diagram-loading-copy {
    font-size: .92rem;
    font-weight: 600;
    line-height: 1.4;
}
html:has(.st-key-shear_uls_diagram_live .js-plotly-plot)
.st-key-shear_uls_plot_frame > div[data-testid="stLayoutWrapper"]:has(> .st-key-shear_uls_diagram_shell),
html:has(.st-key-shear_sls_diagram_live .js-plotly-plot)
.st-key-shear_sls_plot_frame > div[data-testid="stLayoutWrapper"]:has(> .st-key-shear_sls_diagram_shell),
html:has(.st-key-shear_mcft_diagram_live .js-plotly-plot)
.st-key-shear_mcft_plot_frame > div[data-testid="stLayoutWrapper"]:has(> .st-key-shear_mcft_diagram_shell),
html:has(.st-key-shear_mcft_diagram_live iframe)
.st-key-shear_mcft_plot_frame > div[data-testid="stLayoutWrapper"]:has(> .st-key-shear_mcft_diagram_shell) {
    display: none !important;
    height: 0 !important;
    min-height: 0 !important;
    margin: 0 !important;
    padding: 0 !important;
}
</style>
<div id="shear-visuals-block" class="shear-visuals-block" style="display:none;width:0;height:0;overflow:hidden;" aria-hidden="true"></div>
""",
            unsafe_allow_html=True,
        )
        runtime.render_section_title("Visualisation")
        uls_panel, sls_panel, mcft_panel = runtime.render_tabs(
            st,
            labels=SHEAR_DIAGRAM_VIEWS,
            scope_id="shear-diagram-panels",
        )
        with uls_panel:
            with st.container(key="shear_uls_plot_frame"):
                with st.container(key="shear_uls_diagram_shell"):
                    _render_shear_diagram_loading_shell(
                        runtime,
                        view_key="uls",
                        label="ULS shear diagram",
                    )
                with st.container(key="shear_uls_diagram_live"):
                    _render_shear_uls_view(runtime)
            with st.container(key="shear_uls_diagram_caption"):
                st.caption(SHEAR_SIDE_VIEW_CAPTION)
        with sls_panel:
            with st.container(key="shear_sls_plot_frame"):
                with st.container(key="shear_sls_diagram_shell"):
                    _render_shear_diagram_loading_shell(
                        runtime,
                        view_key="sls",
                        label="SLS shear diagram",
                    )
                with st.container(key="shear_sls_diagram_live"):
                    _render_shear_sls_view(runtime)
            with st.container(key="shear_sls_diagram_caption"):
                st.caption("\u00a0")
        with mcft_panel:
            with st.container(key="shear_mcft_plot_frame"):
                with st.container(key="shear_mcft_diagram_shell"):
                    _render_shear_diagram_loading_shell(
                        runtime,
                        view_key="mcft",
                        label="MCFT stress field",
                    )
                with st.container(key="shear_mcft_diagram_live"):
                    _render_shear_mcft_view(runtime)
            with st.container(key="shear_mcft_diagram_caption"):
                from engineering_page_sections.shear_stress_field import (
                    MCFT_ILLUSTRATION_DISCLAIMER,
                )

                st.caption(MCFT_ILLUSTRATION_DISCLAIMER)

        # A second native tab list is the user-facing bottom selector.  It
        # controls the already-mounted panels above entirely in the browser,
        # so changing diagrams cannot rerun engineering or remount the page.
        runtime.render_tabs(
            st,
            labels=SHEAR_DIAGRAM_VIEWS,
            scope_id="shear-diagram-navigation",
            install_runtime=False,
        )
        runtime.synchronize_tabs(
            st,
            source_scope_id="shear-diagram-navigation",
            target_scope_id="shear-diagram-panels",
            hide_target_tablist=True,
            storage_key="sb-tab-sync::shear-diagram-view",
        )
        _render_stress_field_teaching(runtime)


__all__ = [
    "MCFT_BEHAVIOUR_MARGIN",
    "SHEAR_SIDE_VIEW_MAX_WIDTH_PX",
    "SHEAR_BEHAVIOUR_MAX_WIDTH_PX",
    "SHEAR_VISUAL_CONFIG",
    "SHEAR_DIAGRAM_PLOT_HEIGHT_PX",
    "SHEAR_DIAGRAM_VIEWS",
    "SHEAR_VISUAL_HEIGHT_PX",
    "SHEAR_VISUAL_MAX_WIDTH_PX",
    "ShearVisualisationRuntime",
    "_render_centered_shear_plotly",
    "_render_mcft_behaviour_chart",
    "_render_plotly_in_mcft_column",
    "_render_shear_cross_section",
    "_render_shear_side_view",
    "_render_shear_uls_view",
    "_render_shear_sls_view",
    "_render_shear_mcft_view",
    "_standardise_shear_visual_layout",
    "render_shear_visualisation_block",
]
