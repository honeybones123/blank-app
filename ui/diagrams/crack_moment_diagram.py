"""Crack-page moment diagram builders."""

from __future__ import annotations

import numpy as np
import plotly.graph_objects as go

from ui.diagrams.moment_shear_diagram import _add_plotly_support_markers_aligned


def build_crack_moment_diagram_figure(
    *,
    x_values,
    moment_values,
    L: float,
    support_positions: list[float],
    support_types: list[str],
    support_type_fallback: str,
    uirevision: str = "crack_diagram_suite_v2",
) -> go.Figure:
    """
    Build the SLS crack-page moment diagram.

    Ordinate is ``-M`` so sagging is drawn below the baseline and hogging above,
    matching the Beam Actions & Diagrams sign display.
    """
    x_plot = np.asarray(list(x_values), dtype=float)
    M_adj = np.asarray(list(moment_values), dtype=float).copy()
    L = max(float(L), 1e-9)

    mabs = float(np.max(np.abs(M_adj))) if M_adj.size else 1e-9
    if mabs > 1e-12:
        if abs(float(x_plot[0])) <= 1e-7 * max(L, 1.0) and abs(float(M_adj[0])) < 0.07 * mabs:
            M_adj[0] = 0.0
        if abs(float(x_plot[-1]) - L) <= 1e-7 * max(L, 1.0) and abs(float(M_adj[-1])) < 0.07 * mabs:
            M_adj[-1] = 0.0

    M_disp = (-M_adj).tolist()
    x_list = [float(v) for v in x_plot.tolist()]
    M_raw_list = [float(v) for v in M_adj.tolist()]

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=[float(x_list[0]), float(x_list[-1])],
            y=[0.0, 0.0],
            mode="lines",
            line=dict(color="rgba(0,0,0,0.40)", width=1.35),
            hoverinfo="skip",
            showlegend=False,
        )
    )
    fig.add_trace(
        go.Scatter(
            x=x_list,
            y=M_disp,
            mode="lines",
            showlegend=False,
            fill="tozeroy",
            fillcolor="rgba(31, 119, 180, 0.22)",
            line=dict(color="rgba(31, 119, 180, 0.95)", width=2),
            customdata=M_raw_list,
            hovertemplate="x = %{x:.3f} m<br>M = %{customdata:.3f} kNm<extra></extra>",
        )
    )
    for sx in support_positions:
        fig.add_vline(x=float(sx), line_width=1, line_color="rgba(0,0,0,0.06)")
    x_pad = max(float(L or 0.0) * 0.06, 0.08)
    M_min = float(min(M_disp))
    M_max = float(max(M_disp))
    M_abs = max(abs(M_min), abs(M_max), 1e-6)
    M_pad = max(0.12 * M_abs, 1e-6)
    y_range = [M_min - M_pad, M_max + M_pad]

    try:
        idx_peak = int(np.argmax(np.abs(M_adj)))
        x_pk = float(x_list[idx_peak])
        M_pk = float(M_adj[idx_peak])
        y_pk = float(M_disp[idx_peak])
        fig.add_trace(
            go.Scatter(
                x=[x_pk],
                y=[y_pk],
                mode="markers",
                marker=dict(size=7, color="rgba(214, 39, 40, 0.88)"),
                showlegend=False,
                customdata=[M_pk],
                hovertemplate="Peak |M| at x = %{x:.3f} m, M = %{customdata:.3f} kNm<extra></extra>",
            )
        )
    except Exception:
        pass

    fig.update_layout(
        title_text="",
        yaxis_title="",
        plot_bgcolor="white",
        margin=dict(l=16, r=16, t=12, b=52),
        height=260,
        uirevision=uirevision,
    )
    fig.update_xaxes(
        range=[-x_pad, float(L) + x_pad],
        title="x (m)",
        showgrid=True,
        gridcolor="rgba(0,0,0,0.05)",
        zeroline=False,
    )
    fig.update_yaxes(
        range=y_range,
        showgrid=True,
        gridcolor="rgba(0,0,0,0.05)",
        zeroline=False,
    )
    _add_plotly_support_markers_aligned(
        fig,
        support_positions_plot=[float(v) for v in support_positions],
        support_types_plot=list(support_types or []),
        y_min=float(y_range[0]),
        y_max=float(y_range[1]),
        L=L,
        support_type_fallback=support_type_fallback,
    )
    return fig
