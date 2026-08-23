"""Creep side-view diagram presentation boundary."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from engineering_page_sections.stable_tabs import render_stable_tabs
from ui.diagrams.bending_side_view_diagram import build_creep_side_view_figures
from widgets_helpers import (
    compact_side_view_figure,
    inject_compact_side_view_spacing,
    page_divider,
    render_plotly_diagram,
)


@dataclass(frozen=True, slots=True)
class CreepVisualisationView:
    state: Any
    phi_cc_t: float


def render_creep_visualisation(
    st_module,
    *,
    view: CreepVisualisationView,
) -> None:
    """Render the established immediate/long-term Creep diagram tabs."""

    inject_compact_side_view_spacing("creep-side-view-compact")
    st_module.markdown("**Concrete creep under sustained load**")
    st_module.markdown(
        """
<style>
div[data-testid="stElementContainer"]:has(#creep-side-view-tabs-anchor)
  + div[data-testid="stTabs"] [data-baseweb="tab-list"],
div[data-testid="stElementContainer"]:has(#creep-side-view-tabs-anchor)
  + div[data-testid="stTabs"] [role="tablist"] {
    display: inline-flex !important;
    width: fit-content !important;
    max-width: 100% !important;
    border-bottom: 0 !important;
    box-shadow: none !important;
}
div[data-testid="stElementContainer"]:has(#creep-side-view-tabs-anchor)
  + div[data-testid="stTabs"] [data-baseweb="tab-list"] button,
div[data-testid="stElementContainer"]:has(#creep-side-view-tabs-anchor)
  + div[data-testid="stTabs"] [role="tablist"] button {
    flex: 0 0 auto !important;
}
div[data-testid="stElementContainer"]:has(#creep-side-view-tabs-anchor)
  + div[data-testid="stTabs"] [data-baseweb="tab-border"] {
    display: none !important;
}
</style>
<div id="creep-side-view-tabs-anchor"></div>
""",
        unsafe_allow_html=True,
    )
    immediate, long_term, _meta = build_creep_side_view_figures(
        view.state,
        phi_cc_t=view.phi_cc_t,
    )
    immediate = compact_side_view_figure(immediate)
    long_term = compact_side_view_figure(long_term)
    immediate_tab, long_term_tab = render_stable_tabs(
        st_module,
        labels=("Immediate / cracked state", "After creep / long-term"),
        scope_id="creep-side-view-diagrams",
    )
    with immediate_tab:
        render_plotly_diagram(
            immediate,
            key="creep_immediate_cracked_state_diagram",
            title="Immediate cracked state",
            config={"displayModeBar": False, "staticPlot": True},
        )
    with long_term_tab:
        render_plotly_diagram(
            long_term,
            key="creep_long_term_diagram",
            title="After creep / long-term",
            config={"displayModeBar": False, "staticPlot": True},
        )
    page_divider()


__all__ = ["CreepVisualisationView", "render_creep_visualisation"]
