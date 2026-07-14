"""Bending page 3D beam diagram builders."""

from __future__ import annotations

import math

import numpy as np
import plotly.graph_objects as go


def build_beam_3d_figure_pure(
    b,
    D,
    L,
    Mu_star,
    phi_Mu_cap,
    c,
    strain_state,
    reo_layout,
    cover_bot,
    cover_top,
    cover_side,
    rowgap_bot,
    rowgap_top,
    lig_d,
    lig_legs,
    s_lig,
    debug_bust=None,
):
    """
    Pure function version of 3D beam figure generation.

    All inputs must be passed as arguments; ``debug_bust`` is accepted only to
    preserve the legacy cached-call signature.
    """
    try:
        vals = [b, D, L, Mu_star, phi_Mu_cap, c]
        if any(v is None for v in vals):
            return None
        b = float(b)
        D = float(D)
        L = float(L)
        Mu_star = float(Mu_star)
        phi_Mu_cap = float(phi_Mu_cap)
        c = float(c)
        if any(math.isnan(v) for v in (b, D, L, Mu_star, phi_Mu_cap, c)):
            return None
    except Exception:
        return None

    if phi_Mu_cap <= 0.0 or D <= 0.0 or b <= 0.0 or L <= 0.0:
        return None

    eps_cu = 0.003
    phi_u = eps_cu / max(c, 1e-9)

    base_r = Mu_star / phi_Mu_cap if phi_Mu_cap > 0 else 0.0
    base_r = float(max(0.0, min(1.0, base_r)))

    state_low = (strain_state or "").lower()
    if state_low.startswith("uls"):
        r = base_r
    elif state_low.startswith("sls"):
        r = 0.6 * base_r
    else:
        r = 0.0

    c0 = D / 2.0
    if r <= 0.0:
        c_now = c0
    else:
        c_now = (1.0 - r) * c0 + r * c

    traces: list[go.BaseTraceType] = []

    def _add_bar_cylinder(traces, x0, x1, y0, z0, db, color):
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

    vx = np.array([0, L, L, 0, 0, L, L, 0])
    vy = np.array([0, 0, b, b, 0, 0, b, b])
    vz = np.array([0, 0, 0, 0, D, D, D, D])
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
            opacity=0.25,
            flatshading=True,
            hoverinfo="skip",
            showscale=False,
            name="Concrete",
        )
    )

    for layer_data in reo_layout["bottom"]:
        x_positions = layer_data["x"]
        y_pos = layer_data["y"]
        db = layer_data["db"]
        z_pos = y_pos
        for x_pos in x_positions:
            _add_bar_cylinder(traces, 0.0, L, float(x_pos), float(z_pos), float(db), "#1f77b4")

    for layer_data in reo_layout["top"]:
        x_positions = layer_data["x"]
        y_pos = layer_data["y"]
        db = layer_data["db"]
        z_pos = y_pos
        for x_pos in x_positions:
            _add_bar_cylinder(traces, 0.0, L, float(x_pos), float(z_pos), float(db), "#d62728")

    if lig_d > 0 and s_lig > 0 and lig_legs >= 2:
        s_eff = max(40.0, float(s_lig))
        n_hoops = int(max(1, min(80, round(L / s_eff))))
        xs = np.linspace(s_eff / 2.0, L - s_eff / 2.0, n_hoops)

        y_left = cover_side + 0.5 * lig_d
        y_right = b - cover_side - 0.5 * lig_d

        z_top_c = cover_top + 0.5 * lig_d
        z_bot_c = D - (cover_bot + 0.5 * lig_d)

        min_z = 5.0
        max_z = D - 5.0
        z_top_c = float(np.clip(z_top_c, min_z, max_z))
        z_bot_c = float(np.clip(z_bot_c, min_z, max_z))

        lw = max(1.5, abs(lig_d) * 0.35)

        for x0 in xs:
            Xs = [x0] * 5
            Ys = [y_left, y_right, y_right, y_left, y_left]
            Zs = [z_top_c, z_top_c, z_bot_c, z_bot_c, z_top_c]
            traces.append(
                go.Scatter3d(
                    x=Xs,
                    y=Ys,
                    z=Zs,
                    mode="lines",
                    line=dict(width=lw, color="black"),
                    hoverinfo="skip",
                    showlegend=False,
                )
            )

    Xg, Yg = np.meshgrid(np.linspace(0, L, 2), np.linspace(0, b, 2))
    Zg = np.full_like(Xg, c_now)
    traces.append(
        go.Surface(
            x=Xg,
            y=Yg,
            z=Zg,
            colorscale=[[0, "orange"], [1, "orange"]],
            showscale=False,
            opacity=0.55,
            name="NA",
        )
    )

    fig = go.Figure(data=traces)
    k = max(2.2, float(L) / 2000.0)
    fig.update_layout(
        scene_camera=dict(
            eye=dict(x=k, y=k, z=k * 0.6),
            center=dict(x=0, y=0, z=0),
            up=dict(x=0, y=0, z=1),
        ),
        scene=dict(
            xaxis_title="Length (mm)",
            yaxis_title="Width (mm)",
            zaxis_title="Depth from top (mm)",
            zaxis=dict(autorange="reversed"),
            aspectmode="data",
        ),
        margin=dict(l=0, r=0, t=10, b=0),
        height=350,
        showlegend=False,
    )
    return fig
