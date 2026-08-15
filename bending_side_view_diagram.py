"""Compatibility wrappers for bending side-view diagrams.

The figure-building implementation lives in ``ui.diagrams.bending_side_view_diagram``.
This root module keeps the Streamlit render wrapper and legacy import surface stable.
"""

from __future__ import annotations

from typing import Any

import plotly.graph_objects as go
import streamlit as st

from ui.diagrams import bending_side_view_diagram as _impl
from ui.diagrams.bending_side_view_diagram import (
    _build_side_view_figure,
    _build_side_view_support_shapes,
    build_bending_side_view_figure,
    build_creep_side_view_figure,
    build_creep_side_view_figures,
)
from widgets_helpers import render_plotly_diagram


def __getattr__(name: str) -> Any:
    return getattr(_impl, name)


@st.fragment
def render_bending_side_view_diagram(
    state: Any,
    *,
    stress_strain_fig: go.Figure | None = None,
) -> None:
    st.markdown("**Beam side view (bending)**")
    st.caption(
        "Shows the beam side view and the current bending critical section. "
        "Toggle to view the strain and stress diagrams at that section."
    )
    ctrl_strain, ctrl_stress = st.columns([0.28, 0.72])
    with ctrl_strain:
        show_strain = st.toggle(
            "Show strain diagram",
            value=False,
            key="bending_side_view_show_strain",
        )
    with ctrl_stress:
        show_stress = st.toggle(
            "Show stress diagram",
            value=False,
            key="bending_side_view_show_stress",
        )
    fig, meta = build_bending_side_view_figure(
        state,
        stress_strain_fig=stress_strain_fig,
        show_strain_diagram=show_strain,
        show_stress_diagram=show_stress,
    )
    render_plotly_diagram(
        fig,
        key="bending_side_view",
        title="Beam side view (bending)",
        config={"displayModeBar": False},
    )
