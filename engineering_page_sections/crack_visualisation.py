"""Crack Control diagram presentation shared by all calculation methods."""

from __future__ import annotations

from typing import Any, Mapping

from crack_side_view_diagram import (
    _resolve_crack_diagram_window,
    render_crack_moment_tab_plotly,
    render_crack_side_view_diagram,
)
from engineering_page_sections.stable_tabs import render_stable_tabs


def render_method_crack_diagrams(
    st_module: Any,
    *,
    diagram_state: Mapping[str, Any],
    crack_metrics: Mapping[str, Any],
) -> None:
    st_module.markdown(
        '<div id="crack-diagram-module" '
        'style="height:0;width:0;overflow:hidden;"></div>',
        unsafe_allow_html=True,
    )
    crack_tab, moment_tab = render_stable_tabs(
        st_module,
        labels=("Crack Diagram", "Moment Diagram"),
        scope_id="crack-method-diagrams",
    )
    with crack_tab:
        render_crack_side_view_diagram(
            diagram_state,
            crack_metrics=crack_metrics,
        )
    with moment_tab:
        render_crack_moment_tab_plotly()


def render_as3600_crack_diagrams(
    st_module: Any,
    *,
    diagram_state: Mapping[str, Any],
    crack_metrics: Mapping[str, Any],
) -> None:
    st_module.markdown(
        """
<style>
div[data-testid="stVerticalBlock"]:has(> div[data-testid="stElementContainer"] #crack-diagram-module) [data-testid="stRadio"] {
    margin-top: 0.15rem !important;
    margin-bottom: 0.4rem !important;
}
div[data-testid="stVerticalBlock"]:has(> div[data-testid="stElementContainer"] #crack-diagram-module) [data-testid="stPlotlyChart"] {
    margin-bottom: 0.1rem !important;
}
</style>
<div id="crack-diagram-module" style="height:0;width:0;overflow:hidden;" aria-hidden="true"></div>
""",
        unsafe_allow_html=True,
    )
    governing_col, _spacer = st_module.columns([2.2, 3.0])
    with governing_col:
        if bool(_resolve_crack_diagram_window(diagram_state).get("multi")):
            st_module.markdown(
                '<p style="margin:0 0 0.35rem 0;font-size:0.82rem;'
                'color:#6b7280;">Displaying governing span</p>',
                unsafe_allow_html=True,
            )
    crack_tab, moment_tab = render_stable_tabs(
        st_module,
        labels=("Crack Diagram", "Moment Diagram"),
        scope_id="crack-as5100-method-diagrams",
    )
    with crack_tab:
        render_crack_side_view_diagram(
            diagram_state,
            crack_metrics=crack_metrics,
        )
    with moment_tab:
        render_crack_moment_tab_plotly()


__all__ = ["render_as3600_crack_diagrams", "render_method_crack_diagrams"]
