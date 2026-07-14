"""Principal-stress cue diagrams for the shear page."""

from __future__ import annotations

import math

import plotly.graph_objects as go


PRINCIPAL_STRESS_AXES_CUE_SCALE = 1.25**2


def add_principal_stress_orientation_square(
    fig: go.Figure,
    geometry: dict[str, float],
    *,
    principal_angle_deg: float,
    centre: tuple[float, float] | None = None,
) -> None:
    centre_x = centre[0] if centre is not None else geometry["centre_x"]
    centre_y = centre[1] if centre is not None else 0.52 * geometry["D_plot"]
    flexural_factor = min(max(geometry.get("flexural_width", geometry["L_plot"]) / max(geometry["L_plot"], 1e-9), 0.22), 0.86)
    half_side = (0.056 + 0.024 * flexural_factor) * geometry["D_plot"]
    mask_half_side = 1.22 * half_side
    principal_angle_rad = math.radians(principal_angle_deg)
    square_angle = principal_angle_rad + math.radians(20.0)

    def _rotate_local(dx: float, dy: float) -> tuple[float, float]:
        return (
            centre_x + dx * math.cos(square_angle) - dy * math.sin(square_angle),
            centre_y + dx * math.sin(square_angle) + dy * math.cos(square_angle),
        )

    line_angle_rad = principal_angle_rad + math.radians(20.0)
    sigma1_dir = (math.cos(line_angle_rad), math.sin(line_angle_rad))
    sigma2_dir = (-math.sin(line_angle_rad), math.cos(line_angle_rad))

    mask_pts = [
        _rotate_local(-mask_half_side, -mask_half_side),
        _rotate_local(mask_half_side, -mask_half_side),
        _rotate_local(mask_half_side, mask_half_side),
        _rotate_local(-mask_half_side, mask_half_side),
        _rotate_local(-mask_half_side, -mask_half_side),
    ]
    fig.add_trace(
        go.Scatter(
            x=[pt[0] for pt in mask_pts],
            y=[pt[1] for pt in mask_pts],
            mode="lines",
            line=dict(color="rgba(255,255,255,0.0)", width=0.0, shape="linear"),
            fill="toself",
            fillcolor="rgba(249,249,249,0.88)",
            hoverinfo="skip",
            showlegend=False,
        )
    )

    square_pts = [
        _rotate_local(-half_side, -half_side),
        _rotate_local(half_side, -half_side),
        _rotate_local(half_side, half_side),
        _rotate_local(-half_side, half_side),
        _rotate_local(-half_side, -half_side),
    ]
    fig.add_trace(
        go.Scatter(
            x=[pt[0] for pt in square_pts],
            y=[pt[1] for pt in square_pts],
            mode="lines",
            line=dict(color="rgba(95,95,95,0.90)", width=2.0, shape="linear"),
            hoverinfo="skip",
            showlegend=False,
        )
    )

    line_half_len = 1.38 * half_side
    sigma_specs = [
        (sigma1_dir, "rgba(200,45,45,0.92)"),
        (sigma2_dir, "rgba(0,90,200,0.92)"),
    ]
    for line_dir, color in sigma_specs:
        start_x = centre_x - line_half_len * line_dir[0]
        start_y = centre_y - line_half_len * line_dir[1]
        end_x = centre_x + line_half_len * line_dir[0]
        end_y = centre_y + line_half_len * line_dir[1]
        fig.add_trace(
            go.Scatter(
                x=[start_x, end_x],
                y=[start_y, end_y],
                mode="lines",
                line=dict(color=color, width=2.3, shape="linear"),
                hoverinfo="skip",
                showlegend=False,
            )
        )
        arrow_backoff = 0.10 * half_side
        fig.add_annotation(
            x=end_x,
            y=end_y,
            ax=end_x - arrow_backoff * line_dir[0],
            ay=end_y - arrow_backoff * line_dir[1],
            xref="x",
            yref="y",
            axref="x",
            ayref="y",
            text="",
            showarrow=True,
            arrowhead=2,
            arrowsize=0.95,
            arrowwidth=1.2,
            arrowcolor=color,
            opacity=0.90,
            standoff=0,
        )
        fig.add_annotation(
            x=start_x,
            y=start_y,
            ax=start_x + arrow_backoff * line_dir[0],
            ay=start_y + arrow_backoff * line_dir[1],
            xref="x",
            yref="y",
            axref="x",
            ayref="y",
            text="",
            showarrow=True,
            arrowhead=2,
            arrowsize=0.95,
            arrowwidth=1.2,
            arrowcolor=color,
            opacity=0.90,
            standoff=0,
        )

    marker_len = 0.22 * half_side
    right_angle_pts = [
        (
            centre_x + 0.18 * half_side * sigma1_dir[0],
            centre_y + 0.18 * half_side * sigma1_dir[1],
        ),
        (
            centre_x + 0.18 * half_side * sigma1_dir[0] + marker_len * sigma2_dir[0],
            centre_y + 0.18 * half_side * sigma1_dir[1] + marker_len * sigma2_dir[1],
        ),
        (
            centre_x + 0.18 * half_side * sigma2_dir[0],
            centre_y + 0.18 * half_side * sigma2_dir[1],
        ),
    ]
    fig.add_trace(
        go.Scatter(
            x=[pt[0] for pt in right_angle_pts],
            y=[pt[1] for pt in right_angle_pts],
            mode="lines",
            line=dict(color="rgba(95,95,95,0.56)", width=0.95, shape="linear"),
            hoverinfo="skip",
            showlegend=False,
        )
    )


def build_principal_stress_axes_cue(
    theta_v_deg: float,
    *,
    scale: float = PRINCIPAL_STRESS_AXES_CUE_SCALE,
) -> go.Figure:
    fig = go.Figure()
    theta_v_rad = math.radians(max(0.0, min(theta_v_deg, 89.0)))
    D = scale
    half_side = 0.34 * D
    panel_y = 0.0
    panel_centres = [0.0, 2.2, 4.5]

    def _rot(cx: float, cy: float, dx: float, dy: float, angle: float) -> tuple[float, float]:
        return (
            cx + dx * math.cos(angle) - dy * math.sin(angle),
            cy + dx * math.sin(angle) + dy * math.cos(angle),
        )

    def _add_poly(points: list[tuple[float, float]], color: str, width: float, dash: str | None = None, opacity: float = 1.0) -> None:
        fig.add_trace(
            go.Scatter(
                x=[pt[0] for pt in points],
                y=[pt[1] for pt in points],
                mode="lines",
                line=dict(color=color, width=width, dash=dash or "solid"),
                opacity=opacity,
                hoverinfo="skip",
                showlegend=False,
            )
        )

    def _add_square(cx: float, angle: float, *, color: str, width: float, opacity: float = 1.0) -> None:
        pts = [
            _rot(cx, panel_y, -half_side, -half_side, angle),
            _rot(cx, panel_y, half_side, -half_side, angle),
            _rot(cx, panel_y, half_side, half_side, angle),
            _rot(cx, panel_y, -half_side, half_side, angle),
            _rot(cx, panel_y, -half_side, -half_side, angle),
        ]
        _add_poly(pts, color, width, opacity=opacity)

    def _add_arrow(x0: float, y0: float, x1: float, y1: float, *, color: str, width: float = 1.2, dash: str | None = None, opacity: float = 1.0) -> None:
        fig.add_annotation(
            x=x1,
            y=y1,
            ax=x0,
            ay=y0,
            xref="x",
            yref="y",
            axref="x",
            ayref="y",
            text="",
            showarrow=True,
            arrowhead=2,
            arrowsize=0.8,
            arrowwidth=width,
            arrowcolor=color,
            opacity=opacity,
            standoff=0,
        )
        if dash:
            _add_poly([(x0, y0), (x1, y1)], color, width, dash=dash, opacity=opacity * 0.9)

    def _add_double_arrow_line(
        x0: float, y0: float, x1: float, y1: float, *, color: str, width: float, opacity: float = 1.0
    ) -> None:
        fig.add_annotation(
            x=x1,
            y=y1,
            ax=x0,
            ay=y0,
            xref="x",
            yref="y",
            axref="x",
            ayref="y",
            text="",
            showarrow=True,
            arrowside="end+start",
            arrowhead=2,
            startarrowhead=2,
            arrowsize=0.65,
            arrowwidth=width,
            arrowcolor=color,
            opacity=opacity,
            standoff=0,
        )

    for cx, label in zip(panel_centres, ["(A) stress state", "(B) rotate by θ", "(C) principal directions"]):
        fig.add_annotation(x=cx, y=0.96, text=label, showarrow=False, font=dict(size=10, color="rgba(85,85,85,0.90)"))

    # A: stress state — complementary shear τ (outside) + face-centre resultants (wholly outside square outline)
    cx = panel_centres[0]
    top_y = panel_y + half_side
    bot_y = panel_y - half_side
    left_x = cx - half_side
    right_x = cx + half_side
    tau_blue = "rgba(0,90,200,0.80)"
    tau_red = "rgba(200,45,45,0.82)"
    shear_gap = 0.088 * D
    tau_half = 0.14 * D
    y_top_tau = top_y + shear_gap
    y_bot_tau = bot_y - shear_gap
    x_left_tau = left_x - shear_gap
    x_right_tau = right_x + shear_gap
    out_gap = 0.03 * D
    out_len = 0.12 * D
    _add_square(cx, 0.0, color="rgba(120,120,120,0.65)", width=1.5)
    _add_arrow(cx - tau_half, y_top_tau, cx + tau_half, y_top_tau, color=tau_blue, width=1.05)
    _add_arrow(cx + tau_half, y_bot_tau, cx - tau_half, y_bot_tau, color=tau_blue, width=1.05)
    _add_arrow(x_left_tau, panel_y + tau_half, x_left_tau, panel_y - tau_half, color=tau_red, width=1.05)
    _add_arrow(x_right_tau, panel_y - tau_half, x_right_tau, panel_y + tau_half, color=tau_red, width=1.05)
    _add_arrow(cx, top_y + out_gap, cx, top_y + out_gap + out_len, color=tau_blue, width=1.05)
    _add_arrow(cx, bot_y - out_gap, cx, bot_y - out_gap - out_len, color=tau_blue, width=1.05)
    _add_arrow(left_x - out_gap, panel_y, left_x - out_gap - out_len, panel_y, color=tau_red, width=1.05)
    _add_arrow(right_x + out_gap, panel_y, right_x + out_gap + out_len, panel_y, color=tau_red, width=1.05)
    fig.add_annotation(x=x_right_tau + 0.22 * D, y=0.50, text="τ", showarrow=False, font=dict(size=10, color="rgba(85,85,85,0.86)"))
    fig.add_annotation(
        x=cx,
        y=-0.90,
        text="Complementary shear (τ) on opposite faces; face-centre resultants illustrative",
        showarrow=False,
        font=dict(size=8, color="rgba(85,85,85,0.86)"),
    )

    # B: rotated element, shear fading out
    cx = panel_centres[1]
    rot_angle = -0.55 * theta_v_rad
    _add_square(cx, 0.0, color="rgba(150,150,150,0.22)", width=1.2, opacity=0.75)
    _add_square(cx, rot_angle, color="rgba(120,120,120,0.58)", width=1.5)
    b_off = 0.18 * D
    b_ext = 0.90 * D
    b_trim = 0.06 * D
    _add_arrow(cx - b_off, panel_y + b_ext, cx + b_off, panel_y + b_ext, color="rgba(110,110,110,0.42)", width=1.0, dash="dot", opacity=0.70)
    _add_arrow(cx + b_ext, panel_y + b_off, cx + b_ext, panel_y - b_off, color="rgba(110,110,110,0.30)", width=1.0, dash="dot", opacity=0.50)
    _add_arrow(cx + b_off, panel_y - b_ext, cx - b_trim, panel_y - b_ext, color="rgba(110,110,110,0.20)", width=0.9, dash="dot", opacity=0.34)
    _add_arrow(cx - b_ext, panel_y - b_off, cx - b_ext, panel_y + b_trim, color="rgba(110,110,110,0.16)", width=0.9, dash="dot", opacity=0.28)
    fig.add_annotation(x=cx + 0.78 * D, y=-0.55 * D, text="shear → 0", showarrow=False, font=dict(size=9, color="rgba(100,100,100,0.82)"))
    rot_arc: list[tuple[float, float]] = []
    rot_r = 0.42 * D
    for idx in range(22):
        t = idx / 21
        ang = rot_angle * t
        rot_arc.append((cx + rot_r * math.cos(ang), panel_y + rot_r * math.sin(ang)))
    _add_poly(rot_arc, "rgba(120,120,120,0.76)", 1.2)
    fig.add_annotation(
        x=cx + rot_arc[-1][0] - cx,
        y=panel_y + rot_arc[-1][1] - panel_y,
        ax=cx + rot_arc[-2][0] - cx,
        ay=panel_y + rot_arc[-2][1] - panel_y,
        xref="x",
        yref="y",
        axref="x",
        ayref="y",
        text="",
        showarrow=True,
        arrowhead=2,
        arrowsize=0.7,
        arrowwidth=1.0,
        arrowcolor="rgba(120,120,120,0.72)",
    )
    fig.add_annotation(x=cx + 0.50 * D, y=-0.30 * D, text="θ", showarrow=False, font=dict(size=10, color="rgba(100,100,100,0.88)"))

    # C: final principal directions
    cx = panel_centres[2]
    principal_angle = -theta_v_rad
    _add_square(cx, principal_angle, color="rgba(135,135,135,0.34)", width=1.2, opacity=0.95)
    c_axis = 0.82 * D
    _add_poly([(cx - c_axis, panel_y), (cx + c_axis, panel_y)], "rgba(120,120,120,0.38)", 1.1, dash="dot")
    sigma_len = 0.38 * D
    sigma1_pts = [
        (cx - sigma_len * math.cos(principal_angle), panel_y - sigma_len * math.sin(principal_angle)),
        (cx + sigma_len * math.cos(principal_angle), panel_y + sigma_len * math.sin(principal_angle)),
    ]
    sigma2_angle = principal_angle + math.pi / 2.0
    sigma2_pts = [
        (cx - sigma_len * math.cos(sigma2_angle), panel_y - sigma_len * math.sin(sigma2_angle)),
        (cx + sigma_len * math.cos(sigma2_angle), panel_y + sigma_len * math.sin(sigma2_angle)),
    ]
    _add_double_arrow_line(
        sigma1_pts[0][0],
        sigma1_pts[0][1],
        sigma1_pts[1][0],
        sigma1_pts[1][1],
        color="rgba(200,45,45,0.85)",
        width=2.4,
    )
    _add_double_arrow_line(
        sigma2_pts[0][0],
        sigma2_pts[0][1],
        sigma2_pts[1][0],
        sigma2_pts[1][1],
        color="rgba(0,90,200,0.82)",
        width=2.4,
    )

    final_arc: list[tuple[float, float]] = []
    fa_r = 0.22 * D
    for idx in range(18):
        t = idx / 17
        ang = -theta_v_rad * t
        final_arc.append((cx + fa_r * math.cos(ang), panel_y + fa_r * math.sin(ang)))
    _add_poly(final_arc, "rgba(110,90,90,0.70)", 1.1)
    # Place σ labels outside the square and past the principal double-arrow tips
    lbl_pad = 0.08 * D
    lbl_r = max(sigma_len, half_side) + lbl_pad
    fig.add_annotation(
        x=cx + lbl_r * math.cos(principal_angle),
        y=panel_y + lbl_r * math.sin(principal_angle),
        text="σ1",
        showarrow=False,
        font=dict(size=11, color="rgba(200,45,45,0.92)"),
    )
    fig.add_annotation(
        x=cx + lbl_r * math.cos(sigma2_angle),
        y=panel_y + lbl_r * math.sin(sigma2_angle),
        text="σ2",
        showarrow=False,
        font=dict(size=11, color="rgba(0,90,200,0.92)"),
    )
    th_r = 0.32 * D
    fig.add_annotation(
        x=cx + th_r * math.cos(-0.55 * theta_v_rad),
        y=th_r * math.sin(-0.55 * theta_v_rad) - 0.02 * D,
        text="θv",
        showarrow=False,
        font=dict(size=10, color="rgba(110,90,90,0.82)"),
    )
    fig.add_annotation(x=cx, y=-0.88, text="No shear on principal planes", showarrow=False, font=dict(size=9, color="rgba(90,90,90,0.82)"))
    fig.update_layout(
        width=int(540 * D),
        height=int(190 * D),
        margin=dict(l=4, r=4, t=4, b=4),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(visible=False, range=[-1.0, 6.25], fixedrange=True),
        yaxis=dict(visible=False, range=[-1.05, 1.05], scaleanchor="x", scaleratio=1, fixedrange=True),
    )
    return fig

