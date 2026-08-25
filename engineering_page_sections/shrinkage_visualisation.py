"""Shrinkage side-view diagram presentation boundary."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ui.diagrams.creep_shrinkage_diagram import build_shrinkage_side_view_result
from widgets_helpers import (
    COMPACT_SIDE_VIEW_HEIGHT_PX,
    compact_side_view_figure,
    inject_compact_side_view_spacing,
    page_divider,
    render_plotly_diagram,
)


@dataclass(frozen=True, slots=True)
class ShrinkageVisualisationView:
    layout: Any
    faces_exposed: str


def render_shrinkage_visualisation(
    st_module,
    *,
    view: ShrinkageVisualisationView,
) -> None:
    inject_compact_side_view_spacing("shrinkage-side-view-compact")
    st_module.markdown("**Drying shrinkage — beam side view**")
    result = build_shrinkage_side_view_result(
        layout=view.layout,
        faces_option=view.faces_exposed,
        height_px=COMPACT_SIDE_VIEW_HEIGHT_PX,
    )
    if result.error_message:
        st_module.warning(result.error_message)
    if result.figure is not None:
        render_plotly_diagram(
            compact_side_view_figure(result.figure),
            key="shrinkage_side_view_diagram",
            title="Drying shrinkage — beam side view",
            config={"displayModeBar": False},
        )
    page_divider()


__all__ = ["ShrinkageVisualisationView", "render_shrinkage_visualisation"]
