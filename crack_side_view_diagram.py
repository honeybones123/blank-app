"""Compatibility wrappers for crack side-view diagrams.

The figure-building implementation lives in ``ui.diagrams.crack_side_view_diagram``.
This root module keeps page rendering and legacy private-helper imports stable.
"""

from __future__ import annotations

from typing import Any, Mapping

import numpy as np
import streamlit as st

from state_and_helpers import get_param
from ui.diagrams import crack_side_view_diagram as _impl
from ui.diagrams.crack_side_view_diagram import (
    _add_deflected_beam_polygon_trace,
    _add_flexural_cracks_on_deflected_shape,
    _add_flexural_cracks_straight,
    _add_tension_reo_on_deflected_shape,
    _build_side_view_figure,
    _crack_diagram_metrics_from_shared,
    _diagram_kind,
    _resolve_crack_diagram_window,
    _shift_longitudinal_layer_stations_mm,
    _slice_rebase_deflection_mesh,
    _support_resolution,
    _total_structural_length_m,
    build_crack_moment_diagram_figure,
    build_crack_side_view_figure,
    compute_crack_diagram_deflection_mesh,
)
from widgets_helpers import (
    compact_side_view_figure,
    inject_compact_side_view_spacing,
    render_plotly_diagram,
)


def __getattr__(name: str) -> Any:
    return getattr(_impl, name)


def render_crack_moment_tab_plotly() -> None:
    """
    SLS bending moment diagram from shared ``moment_x`` / ``moment_values``.

    Ordinate = -M so sagging (M > 0) is below the baseline and hogging
    (M < 0) is above, matching the Beam Actions & Diagrams sign display.
    """
    win = _resolve_crack_diagram_window(st.session_state)

    wx, wM = win["x_m"], win["M_m"]
    if not isinstance(wx, np.ndarray) or not isinstance(wM, np.ndarray) or wx.size < 2 or wM.size != wx.size:
        st.info("SLS moment diagram is not available yet - beam results will populate after the next global update.")
        return
    L = max(float(win["L_m"]), 1e-9)
    x0 = float(win["x0_m"])
    x1 = x0 + L
    sup_x_global = [float(v) for v in (get_param("bmd_support_positions_m", []) or [])]
    sup_ty = [str(v) for v in (get_param("bmd_support_types", []) or [])]
    sup_x: list[float] = []
    for sx in sup_x_global:
        if x0 - 1e-9 <= sx <= x1 + 1e-9:
            sup_x.append(sx - x0)
    for edge in (0.0, L):
        if not any(abs(edge - s) < 1e-6 * max(L, 1.0) for s in sup_x):
            if any(abs(edge - sg) < 1e-6 * max(L, 1.0) for sg in sup_x_global):
                sup_x.append(edge)
    sup_x = sorted(set(round(s, 6) for s in sup_x))

    fallback = str(get_param("support_type", "simply_supported") or "simply_supported").strip().lower()
    fig = build_crack_moment_diagram_figure(
        x_values=wx.tolist(),
        moment_values=wM.tolist(),
        L=L,
        support_positions=sup_x,
        support_types=sup_ty,
        support_type_fallback=fallback,
    )

    render_plotly_diagram(
        fig,
        key="crack_moment_diagram",
        title="Crack moment diagram",
        config={"displayModeBar": False},
    )


def render_crack_side_view_diagram(
    state: Any,
    crack_metrics: Mapping[str, Any] | None = None,
) -> None:
    inject_compact_side_view_spacing("crack-side-view-compact")
    st.markdown("**Beam side view (flexural cracking)**")
    fig = compact_side_view_figure(
        build_crack_side_view_figure(state, crack_metrics=crack_metrics)
    )
    render_plotly_diagram(
        fig,
        key="crack_side_view_diagram",
        title="Beam side view (flexural cracking)",
        config={"displayModeBar": False},
    )
