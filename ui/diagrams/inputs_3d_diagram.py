"""Inputs-page 3D section diagram builders."""

from __future__ import annotations

from typing import Any

import numpy as np
import plotly.graph_objects as go


def _add_bar_cylinder(traces: list, x0, x1, y0, z0, db, color) -> None:
    r = float(db) / 2.0
    if r <= 0:
        return

    n_theta = 18
    theta = np.linspace(0, 2 * np.pi, n_theta)
    X = np.column_stack([np.full(n_theta, x0), np.full(n_theta, x1)])
    Y = np.column_stack([y0 + r * np.cos(theta), y0 + r * np.cos(theta)])
    Z = np.column_stack([z0 + r * np.sin(theta), z0 + r * np.sin(theta)])

    traces.append(
        go.Surface(
            x=X,
            y=Y,
            z=Z,
            colorscale=[[0, color], [1, color]],
            showscale=False,
            opacity=1.0,
            hoverinfo="skip",
            name="Reo",
        )
    )


def _iter_band_xy(layer_data: dict[str, Any]):
    xs = layer_data.get("x") or []
    y_raw = layer_data.get("y")
    db = float(layer_data.get("db", 0.0) or 0.0)
    if not xs or db <= 0.0:
        return
    if isinstance(y_raw, (int, float)):
        yf = float(y_raw)
        for xp in xs:
            yield float(xp), yf, db
        return
    ys = list(y_raw)
    if len(ys) == len(xs):
        for xp, yp in zip(xs, ys):
            yield float(xp), float(yp), db
    elif len(ys) == 1:
        yf = float(ys[0])
        for xp in xs:
            yield float(xp), yf, db
    else:
        n = min(len(xs), len(ys))
        for i in range(n):
            yield float(xs[i]), float(ys[i]), db


def _internal_leg_positions(y_min, y_max, n_legs):
    if n_legs <= 2:
        return []
    span = y_max - y_min
    if span <= 0:
        return []
    return [y_min + span * j / (n_legs - 1) for j in range(1, n_legs - 1)]


def build_inputs_beam_3d_figure(
    *,
    shape_name: str,
    shape_key: str,
    outline_points: list[tuple[float, float]],
    b_box: float,
    D: float,
    L_plot: float,
    fallback_width: float,
    cover_bot: float,
    cover_top: float,
    cover_side: float,
    lig_d: float,
    lig_legs: int,
    s_lig: float,
    reo_layout: dict[str, Any],
    cage: dict[str, Any] | None = None,
    resolved_bars: list[dict[str, Any]] | None = None,
) -> go.Figure:
    traces: list = []

    if str(shape_name).startswith("Rectangle"):
        x0, x1 = 0.0, float(L_plot)
        y0, y1 = 0.0, float(b_box)
        z0, z1 = 0.0, float(D)
        vx = np.array([x0, x1, x1, x0, x0, x1, x1, x0], dtype=float)
        vy = np.array([y0, y0, y1, y1, y0, y0, y1, y1], dtype=float)
        vz = np.array([z0, z0, z0, z0, z1, z1, z1, z1], dtype=float)
        tri_i = [0, 0, 0, 4, 4, 1, 5, 2, 6, 3, 7, 6]
        tri_j = [1, 2, 3, 5, 7, 5, 6, 6, 7, 7, 4, 2]
        tri_k = [2, 3, 0, 6, 4, 2, 7, 3, 4, 0, 5, 1]
        traces.append(
            go.Mesh3d(
                x=vx,
                y=vy,
                z=vz,
                i=tri_i,
                j=tri_j,
                k=tri_k,
                color="#cccccc",
                opacity=0.18,
                flatshading=True,
                hoverinfo="skip",
                showlegend=False,
            )
        )

    pts = outline_points
    ys = [p[0] for p in pts]
    zs = [p[1] for p in pts]
    traces.append(
        go.Scatter3d(
            x=[0.0] * len(pts),
            y=ys,
            z=zs,
            mode="lines",
            line=dict(width=6, color="rgba(20,20,20,0.95)"),
            hoverinfo="skip",
            showlegend=False,
        )
    )
    traces.append(
        go.Scatter3d(
            x=[L_plot] * len(pts),
            y=ys,
            z=zs,
            mode="lines",
            line=dict(width=6, color="rgba(20,20,20,0.95)"),
            hoverinfo="skip",
            showlegend=False,
        )
    )
    for i in range(len(pts) - 1):
        traces.append(
            go.Scatter3d(
                x=[0.0, L_plot],
                y=[ys[i], ys[i]],
                z=[zs[i], zs[i]],
                mode="lines",
                line=dict(width=6, color="rgba(20,20,20,0.95)"),
                hoverinfo="skip",
                showlegend=False,
            )
        )

    reo_points_3d: list[dict[str, float]] = []
    if shape_key in ("T", "I") and resolved_bars is not None:
        for bar in resolved_bars:
            x_pos = float(bar.get("x_mm", 0.0) or 0.0)
            z_pos = float(bar.get("y_mm", 0.0) or 0.0)
            db = float(bar.get("dia_mm", 0.0) or 0.0)
            face = str(bar.get("face") or "bottom")
            color = "#d62728" if face == "top" else "#1f77b4"
            reo_points_3d.append({"x": x_pos, "y": z_pos, "db": db})
            _add_bar_cylinder(traces, 0.0, L_plot, x_pos, z_pos, db, color)
    else:
        for layer_data in reo_layout.get("bottom", []):
            for x_pos, z_pos, db in _iter_band_xy(layer_data):
                reo_points_3d.append({"x": x_pos, "y": z_pos, "db": db})
                _add_bar_cylinder(traces, 0.0, L_plot, x_pos, z_pos, db, "#1f77b4")
        for layer_data in reo_layout.get("top", []):
            for x_pos, z_pos, db in _iter_band_xy(layer_data):
                reo_points_3d.append({"x": x_pos, "y": z_pos, "db": db})
                _add_bar_cylinder(traces, 0.0, L_plot, x_pos, z_pos, db, "#d62728")

    def add_shear_hoop_at_x(x0):
        cage_data = cage or {}
        ok_cage = (
            cage_data.get("x0") is not None
            and cage_data.get("x1") is not None
            and cage_data.get("y0") is not None
            and cage_data.get("y1") is not None
            and float(cage_data["x1"]) > float(cage_data["x0"])
            and float(cage_data["y1"]) > float(cage_data["y0"])
        )
        if ok_cage:
            y_left = float(cage_data["x0"])
            y_right = float(cage_data["x1"])
            z_top = float(cage_data["y0"])
            z_bot = float(cage_data["y1"])
        elif reo_points_3d:
            y_left = min(pt["x"] - pt["db"] / 2.0 for pt in reo_points_3d)
            y_right = max(pt["x"] + pt["db"] / 2.0 for pt in reo_points_3d)
            z_top = min(pt["y"] - pt["db"] / 2.0 for pt in reo_points_3d)
            z_bot = max(pt["y"] + pt["db"] / 2.0 for pt in reo_points_3d)
        else:
            y_left = cover_side
            y_right = fallback_width - cover_side
            z_top = cover_top + max(lig_d, 6.0)
            z_bot = D - (cover_bot + max(lig_d, 6.0))

        min_z = 5.0
        max_z = D - 5.0
        min_y = 5.0
        max_y = float(b_box) - 5.0
        y_left = float(np.clip(y_left, min_y, max_y))
        y_right = float(np.clip(y_right, min_y, max_y))
        z_top_c = float(np.clip(z_top, min_z, max_z))
        z_bot_c = float(np.clip(z_bot, min_z, max_z))
        lw = max(1.5, abs(lig_d) * 0.35)
        traces.append(
            go.Scatter3d(
                x=[x0] * 5,
                y=[y_left, y_right, y_right, y_left, y_left],
                z=[z_top_c, z_top_c, z_bot_c, z_bot_c, z_top_c],
                mode="lines",
                line=dict(width=lw, color="black"),
                hoverinfo="skip",
                showlegend=False,
            )
        )
        if lig_legs > 2:
            for yi in _internal_leg_positions(y_left, y_right, lig_legs):
                traces.append(
                    go.Scatter3d(
                        x=[x0, x0],
                        y=[yi, yi],
                        z=[z_top_c, z_bot_c],
                        mode="lines",
                        line=dict(width=lw * 0.9, color="black"),
                        hoverinfo="skip",
                        showlegend=False,
                    )
                )

    if lig_d > 0 and s_lig > 0 and lig_legs >= 2:
        s_eff = max(40.0, float(s_lig))
        n_hoops = int(max(1, min(80, round(L_plot / s_eff))))
        xs = np.linspace(s_eff / 2.0, L_plot - s_eff / 2.0, n_hoops)
        for x0 in xs:
            add_shear_hoop_at_x(x0)

    fig = go.Figure(data=traces)
    fig.update_layout(
        autosize=True,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        scene_aspectmode="manual",
        scene_aspectratio=dict(x=2.4, y=max(0.7, b_box / max(D, 1.0)), z=1.0),
        scene_camera=dict(
            eye=dict(x=1.8, y=1.2, z=0.6),
            center=dict(x=0, y=0, z=0),
            up=dict(x=0, y=0, z=1),
        ),
        scene=dict(
            xaxis=dict(range=[0.0, L_plot], visible=False, showgrid=False, zeroline=False, showticklabels=False),
            yaxis=dict(range=[0.0, b_box], visible=False, showgrid=False, zeroline=False, showticklabels=False),
            zaxis=dict(range=[float(D), 0.0], visible=False, showgrid=False, zeroline=False, showticklabels=False),
        ),
        margin=dict(l=8, r=8, t=8, b=8),
        showlegend=False,
    )
    fig.update_scenes(bgcolor="rgba(0,0,0,0)")
    return fig
