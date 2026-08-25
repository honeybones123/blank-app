"""Deflection diagram presentation using immutable calculated inputs."""

from __future__ import annotations

from typing import Any

from engineering_page_sections.deflection_page_context import DeflectionDiagramSnapshot
from ui.diagrams.deflection_diagram import (
    build_deflected_beam_plotly,
    deflected_longitudinal_profile_mm,
)
from widgets_helpers import (
    COMPACT_SIDE_VIEW_HEIGHT_PX,
    compact_side_view_figure,
    inject_compact_side_view_spacing,
    page_divider,
    render_plotly_diagram,
)


def render_deflection_diagram(
    st_module: Any,
    snapshot: DeflectionDiagramSnapshot,
) -> None:
    inject_compact_side_view_spacing("deflection-side-view-compact")
    st_module.markdown("**Deflected shape**")
    st_module.caption("Illustrative — see figure title for vertical exaggeration")
    st_module.caption(
        f"Resolved support condition for governing span: {snapshot.support_type}"
    )
    if snapshot.multi_span:
        span_no = snapshot.controlling_span_idx + 1
        reason = snapshot.controlling_reason
        if reason in ("highest deflection utilisation", "largest absolute deflection"):
            basis = f"selected from calculated per-span deflection results ({reason})"
        elif reason == "longest active span":
            basis = "selected by longest active span"
        else:
            basis = "selected by fallback"
        st_module.caption(
            f"Governing span: Span {span_no}, {basis}. "
            "The displayed support condition and sketch follow this governing span."
        )

    if snapshot.total_deflection_mm is None:
        st_module.info("Provide inputs to view deflected shape.")
    else:
        x, y_long = deflected_longitudinal_profile_mm(
            snapshot.span_mm,
            snapshot.support_type,
            snapshot.total_deflection_mm,
            n_pts=200,
        )
        beam_fig = build_deflected_beam_plotly(
            x_mm=x,
            w_mm=y_long,
            L_mm=snapshot.span_mm,
            D_mm=snapshot.depth_mm,
            support_type=snapshot.support_type,
            continuous_end_side=snapshot.continuous_end_side,
            support_pair=snapshot.support_pair,
            reo_layers={
                key: [dict(layer) for layer in layers]
                for key, layers in snapshot.reo_layers.items()
            },
            height=COMPACT_SIDE_VIEW_HEIGHT_PX,
        )
        render_plotly_diagram(
            compact_side_view_figure(beam_fig),
            key="deflection_deflected_shape_diagram",
            title="Deflected shape",
            center=True,
            allow_fullscreen=True,
            preserve_figure_width=True,
            config={"displayModeBar": False},
        )
    page_divider()


__all__ = ["render_deflection_diagram"]
