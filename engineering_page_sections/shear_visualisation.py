"""Shear visualisation layout and support adapters."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import plotly.graph_objects as go

from shear_visuals import BEHAVIOUR_VISUAL_HEIGHT, BEHAVIOUR_VISUAL_WIDTH


SHEAR_VISUAL_HEIGHT_PX = BEHAVIOUR_VISUAL_HEIGHT
SHEAR_BEHAVIOUR_MAX_WIDTH_PX = BEHAVIOUR_VISUAL_WIDTH
MCFT_BEHAVIOUR_MARGIN = dict(l=10, r=10, t=8, b=10)

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
    *,
    st_module: Any,
    render_section_title: Callable[[str], Any],
    render_tabs: Callable[..., Any],
    render_side_view: Callable[[], Any],
    render_cross_section: Callable[[], Any],
    render_force_diagram: Callable[[], Any],
) -> None:
    """Render the established three-tab Shear diagram viewport.

    Diagram builders and Streamlit mounting remain explicit dependencies.  The
    orchestration module therefore owns layout only and cannot read or mutate
    engineering state behind the caller's back.
    """

    with st_module.container():
        st_module.markdown(
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
        render_section_title("Visualisation")
        side_view_tab, section_tab, shear_diagram_tab = render_tabs(
            st_module,
            labels=("Side view", "Section", "Shear diagram"),
            scope_id="shear-visualisation-diagrams",
        )
        with side_view_tab:
            render_side_view()
        with section_tab:
            render_cross_section()
        with shear_diagram_tab:
            render_force_diagram()


__all__ = [
    "MCFT_BEHAVIOUR_MARGIN",
    "SHEAR_BEHAVIOUR_MAX_WIDTH_PX",
    "SHEAR_VISUAL_HEIGHT_PX",
    "_coalesce_num",
    "_render_mcft_behaviour_chart",
    "_render_plotly_in_mcft_column",
    "_standardise_shear_visual_layout",
    "_support_pair_from_resolved_support_type",
    "render_shear_visualisation_block",
]
