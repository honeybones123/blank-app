"""Moment, shear, and beam-action diagram builders."""

from __future__ import annotations

import numpy as np
import plotly.graph_objects as go


def _clamp_x(x_m: float, max_x: float) -> float:
    return max(0.0, min(float(x_m), float(max_x)))



def _add_plotly_support_markers_aligned(
    fig: go.Figure,
    *,
    support_positions_plot: list[float],
    support_types_plot: list[str],
    y_min: float,
    y_max: float,
    L: float | None,
    support_type_fallback: str,
) -> None:
    """
    Support symbols in **data coordinates** at the foot of the diagram so they line up
    in x with the load diagram and stay aligned when V/M scales change.
    """
    span = max(float(y_max) - float(y_min), 1e-9)
    y_tri = float(y_min) + 0.040 * span
    y_roller = float(y_min) + 0.018 * span
    y_wall_lo = float(y_min) + 0.012 * span
    y_wall_hi = float(y_min) + 0.24 * span
    tri_marker = dict(symbol="triangle-up", size=14, color="rgba(35,35,35,0.9)", line=dict(width=1, color="rgba(35,35,35,1)"))

    positions = [float(v) for v in support_positions_plot]
    types_list = [str(t or "") for t in (support_types_plot or [])]

    if not positions and L is not None:
        fb = str(support_type_fallback or "simply_supported").strip().lower()
        Lf = float(L)
        if fb == "cantilever":
            positions = [0.0]
            types_list = ["fixed"]
        elif fb == "simply_supported":
            positions = [0.0, Lf]
            types_list = ["pinned", "roller"]
        else:
            positions = [0.0, Lf]
            types_list = ["pinned", "pinned"]

    if not positions:
        return

    pinned_x: list[float] = []
    roller_x: list[float] = []
    fixed_x: list[float] = []

    for idx, sx in enumerate(positions):
        stype = str(types_list[idx] if idx < len(types_list) else "").strip().lower()
        if stype == "fixed":
            fixed_x.append(float(sx))
        elif stype == "roller":
            roller_x.append(float(sx))
            pinned_x.append(float(sx))
        else:
            pinned_x.append(float(sx))

    if pinned_x:
        fig.add_trace(
            go.Scatter(
                x=pinned_x,
                y=[y_tri] * len(pinned_x),
                mode="markers",
                marker=tri_marker,
                showlegend=False,
            )
        )
    for sx in roller_x:
        fig.add_trace(
            go.Scatter(
                x=[sx],
                y=[y_roller],
                mode="markers",
                marker=dict(symbol="circle", size=9, color="rgba(35,35,35,0.85)", line=dict(width=1, color="rgba(35,35,35,1)")),
                showlegend=False,
            )
        )
    for sx in fixed_x:
        fig.add_shape(
            type="line",
            x0=float(sx),
            x1=float(sx),
            y0=y_wall_lo,
            y1=y_wall_hi,
            line=dict(width=8, color="rgba(35,35,35,1)"),
        )

def plot_load_diagram_plotly(
    case,
    L,
    params,
    preview_x_m: float | None = None,
    design_x_m: float | None = None,
    support_condition: str | None = None,
    support_positions: list[float] | None = None,
    support_types: list[str] | None = None,
    point_loads: list[dict] | None = None,
    udl_loads: list[dict] | None = None,
):
    """
    Plotly version of the qualitative load diagram.
    Much simpler visually, but interactive.
    """
    fig = go.Figure()

    # Beam line
    fig.add_trace(
        go.Scatter(
            x=[0, L],
            y=[0, 0],
            mode="lines",
            line=dict(width=4),
            showlegend=False,
        )
    )

    support_positions_plot = list(support_positions or params.get("support_positions") or [])
    support_types_plot = list(support_types or params.get("support_types") or [])
    point_loads_plot = list(point_loads or params.get("point_loads") or [])
    udl_loads_plot = list(udl_loads or params.get("udl_loads") or [])
    generic_multi_span = (
        case == "Multi-span continuous beam"
        and len(support_positions_plot) >= 2
        and len(support_positions_plot) == len(support_types_plot)
    )

    # --- Supports ---
    if generic_multi_span:
        pinned_x = []
        fixed_x = []
        for sx, stype in zip(support_positions_plot, support_types_plot):
            t = str(stype or "").strip().lower()
            if t in {"pinned", "roller"}:
                pinned_x.append(float(sx))
            elif t == "fixed":
                fixed_x.append(float(sx))
                fig.add_shape(
                    type="line",
                    x0=float(sx),
                    x1=float(sx),
                    y0=-0.4,
                    y1=0.4,
                    line=dict(width=8),
                )
        if pinned_x:
            fig.add_trace(
                go.Scatter(
                    x=pinned_x,
                    y=[-0.1 for _ in pinned_x],
                    mode="markers",
                    marker=dict(symbol="triangle-up", size=14),
                    showlegend=False,
                )
            )
    elif case == "Overhanging beam – right overhang with point load at free end":
        L_main = params.get("L_main", L)
        fig.add_trace(
            go.Scatter(
                x=[0, L_main],
                y=[-0.1, -0.1],
                mode="markers",
                marker=dict(symbol="triangle-up", size=14),
                showlegend=False,
            )
        )
    else:
        cond = str(support_condition or "").strip().replace("-", "–")
        if not cond:
            cond = "Fixed–Free" if case.startswith("Cantilever") else "Simply supported"

        if cond == "Simply supported":
            fig.add_trace(
                go.Scatter(
                    x=[0.0, float(L)],
                    y=[-0.1, -0.1],
                    mode="markers",
                    marker=dict(symbol="triangle-up", size=14),
                    showlegend=False,
                )
            )
            fig.add_trace(
                go.Scatter(
                    x=[float(L)],
                    y=[-0.24],
                    mode="markers",
                    marker=dict(symbol="circle", size=9, color="rgba(35,35,35,0.85)", line=dict(width=1, color="rgba(35,35,35,1)")),
                    showlegend=False,
                )
            )
        elif cond == "Pinned–Pinned":
            fig.add_trace(
                go.Scatter(
                    x=[0.0, float(L)],
                    y=[-0.1, -0.1],
                    mode="markers",
                    marker=dict(symbol="triangle-up", size=14),
                    showlegend=False,
                )
            )
        elif cond in {"Pinned–Fixed", "Fixed–Pinned"}:
            pinned_x = []
            if cond.startswith("Pinned"):
                pinned_x.append(0.0)
            if cond.endswith("Pinned"):
                pinned_x.append(float(L))
            if pinned_x:
                fig.add_trace(
                    go.Scatter(
                        x=pinned_x,
                        y=[-0.1 for _ in pinned_x],
                        mode="markers",
                        marker=dict(symbol="triangle-up", size=14),
                        showlegend=False,
                    )
                )

        if cond in {"Fixed–Free", "Fixed–Pinned", "Fixed–Fixed", "Pinned–Fixed"}:
            if cond.startswith("Fixed"):
                fig.add_shape(
                    type="line",
                    x0=0,
                    x1=0,
                    y0=-0.4,
                    y1=0.4,
                    line=dict(width=8),
                )
            if cond.endswith("Fixed"):
                fig.add_shape(
                    type="line",
                    x0=float(L),
                    x1=float(L),
                    y0=-0.4,
                    y1=0.4,
                    line=dict(width=8),
                )

    # --- Loads ---
    if generic_multi_span:
        point_loads_plot = sorted(point_loads_plot, key=lambda item: float(item.get("x_m", 0.0)))
        udl_loads_plot = sorted(udl_loads_plot, key=lambda item: float(item.get("x_start_m", 0.0)))
        for j, udl in enumerate(udl_loads_plot, start=1):
            xs = _clamp_x(float(udl.get("x_start_m", 0.0) or 0.0), float(L))
            xe = _clamp_x(float(udl.get("x_end_m", 0.0) or 0.0), float(L))
            if xe <= xs:
                continue
            wj = float(udl.get("w_kN_per_m", 0.0) or 0.0)
            fig.add_trace(
                go.Scatter(
                    x=[xs, xe],
                    y=[0.38, 0.38],
                    mode="lines",
                    line=dict(width=0),
                    fill="tozeroy",
                    opacity=0.25,
                    showlegend=False,
                )
            )
            for xi in np.linspace(xs + 0.08 * (xe - xs), xe - 0.08 * (xe - xs), 4):
                fig.add_annotation(
                    x=xi,
                    y=0,
                    ax=xi,
                    ay=0.43,
                    xref="x",
                    yref="y",
                    axref="x",
                    ayref="y",
                    showarrow=True,
                    arrowhead=2,
                    arrowwidth=1.2,
                    arrowcolor="black",
                )
            fig.add_annotation(x=(xs + xe) / 2.0, y=0.52, text=f"w{j}={wj:.2f}", showarrow=False, font=dict(size=10))

        for i, row in enumerate(point_loads_plot, start=1):
            x_i = _clamp_x(float(row.get("x_m", 0.0) or 0.0), float(L))
            p_i = float(row.get("P_kN", 0.0) or 0.0)
            text_y = 0.56 + 0.08 * ((i - 1) % 2)
            fig.add_annotation(
                x=x_i,
                y=0,
                ax=x_i,
                ay=0.5,
                xref="x",
                yref="y",
                axref="x",
                ayref="y",
                showarrow=True,
                arrowhead=2,
                arrowwidth=2,
                arrowsize=1.1,
                arrowcolor="black",
            )
            fig.add_annotation(
                x=x_i,
                y=text_y,
                text=f"P{i} = {p_i:.2f} kN",
                showarrow=False,
                font=dict(size=11),
            )
    elif case in ["Simple beam – multiple point loads", "Cantilever – multiple point loads"]:
        point_loads = list(params.get("point_loads") or [])
        point_loads = sorted(point_loads, key=lambda item: float(item.get("x_m", 0.0)))
        n_loads = max(1, len(point_loads))
        for i, row in enumerate(point_loads, start=1):
            x_i = _clamp_x(float(row.get("x_m", 0.0) or 0.0), float(L))
            p_i = float(row.get("P_kN", 0.0) or 0.0)
            # Stagger text y-values to reduce overlap for nearby loads.
            text_y = 0.56 + 0.08 * ((i - 1) % 2)
            fig.add_annotation(
                x=x_i,
                y=0,
                ax=x_i,
                ay=0.5,
                xref="x",
                yref="y",
                axref="x",
                ayref="y",
                showarrow=True,
                arrowhead=2,
                arrowwidth=2,
                arrowsize=1.1,
                arrowcolor="black",
            )
            fig.add_annotation(
                x=x_i,
                y=text_y,
                text=f"P{i} = {p_i:.2f} kN",
                showarrow=False,
                font=dict(size=11),
            )
        if point_loads:
            x_span_mid = sum(float(row.get("x_m", 0.0)) for row in point_loads) / n_loads
            p_total = sum(float(row.get("P_kN", 0.0) or 0.0) for row in point_loads)
            fig.add_annotation(
                x=_clamp_x(x_span_mid, float(L)),
                y=0.68,
                text=f"Total P = {p_total:.2f} kN",
                showarrow=False,
                font=dict(size=11),
            )

    elif case == "Simple beam – UDL over entire span":
        w = params.get("w", 0.0)
        xs = [0, L]
        ys = [0.4, 0.4]
        fig.add_trace(
            go.Scatter(
                x=xs,
                y=ys,
                mode="lines",
                line=dict(width=0),
                fill="tozeroy",
                opacity=0.3,
                showlegend=False,
            )
        )
        # arrows
        for xi in np.linspace(0.1 * L, 0.9 * L, 7):
            fig.add_annotation(
                x=xi,
                y=0,
                ax=xi,
                ay=0.45,
                xref="x",
                yref="y",
                axref="x",
                ayref="y",
                showarrow=True,
                arrowhead=2,
                arrowwidth=1.5,
                arrowcolor="black",
            )
        fig.add_annotation(
            x=L / 2,
            y=0.55,
            text=f"w = {w:.2f} kN/m",
            showarrow=False,
        )

    elif case == "Simple beam – point load at centre":
        P = params.get("P", 0.0)
        a = L / 2
        # Arrow points downward: (x, y) is arrow tip at beam, (ax, ay) is arrow start above
        fig.add_annotation(
            x=a,
            y=0,
            ax=a,
            ay=0.5,
            xref="x",
            yref="y",
            axref="x",
            ayref="y",
            showarrow=True,
            arrowhead=2,
            arrowwidth=2,
            arrowsize=1.2,
            arrowcolor="black",
        )
        fig.add_annotation(
            x=a,
            y=0.6,
            text=f"P = {P:.2f} kN",
            showarrow=False,
            font=dict(size=12),
        )

    elif case == "Simple beam – point load at distance a from left":
        P = params.get("P", 0.0)
        a_val = params.get("a")
        if a_val is None:
            a = L / 3
        else:
            a = float(a_val)
        a = max(0.0, min(a, L))
        # Arrow points downward: (x, y) is arrow tip at beam, (ax, ay) is arrow start above
        fig.add_annotation(
            x=a,
            y=0,
            ax=a,
            ay=0.5,
            xref="x",
            yref="y",
            axref="x",
            ayref="y",
            showarrow=True,
            arrowhead=2,
            arrowwidth=2,
            arrowsize=1.2,
            arrowcolor="black",
        )
        fig.add_annotation(
            x=a,
            y=0.6,
            text=f"P = {P:.2f} kN",
            showarrow=False,
            font=dict(size=12),
        )

    elif case == "Cantilever – point load at free end":
        P = params.get("P", 0.0)
        # Arrow points downward: (x, y) is arrow tip at beam, (ax, ay) is arrow start above
        fig.add_annotation(
            x=L,
            y=0,
            ax=L,
            ay=0.5,
            xref="x",
            yref="y",
            axref="x",
            ayref="y",
            showarrow=True,
            arrowhead=2,
            arrowwidth=2,
            arrowsize=1.2,
            arrowcolor="black",
        )
        fig.add_annotation(
            x=L,
            y=0.6,
            text=f"P = {P:.2f} kN",
            showarrow=False,
            font=dict(size=12),
        )

    elif case == "Cantilever – point load at distance a from fixed end":
        P = params.get("P", 0.0)
        a_val = params.get("a_cant")
        if a_val is None:
            a = L / 2
        else:
            a = float(a_val)
        a = max(0.0, min(a, L))
        # Arrow points downward: (x, y) is arrow tip at beam, (ax, ay) is arrow start above
        fig.add_annotation(
            x=a,
            y=0,
            ax=a,
            ay=0.5,
            xref="x",
            yref="y",
            axref="x",
            ayref="y",
            showarrow=True,
            arrowhead=2,
            arrowwidth=2,
            arrowsize=1.2,
            arrowcolor="black",
        )
        fig.add_annotation(
            x=a,
            y=0.6,
            text=f"P = {P:.2f} kN",
            showarrow=False,
            font=dict(size=12),
        )

    elif case == "Cantilever – UDL over entire span":
        w = params.get("w", 0.0)
        xs = [0, L]
        ys = [0.4, 0.4]
        fig.add_trace(
            go.Scatter(
                x=xs,
                y=ys,
                mode="lines",
                line=dict(width=0),
                fill="tozeroy",
                opacity=0.3,
                showlegend=False,
            )
        )
        # arrows
        for xi in np.linspace(0.1 * L, 0.9 * L, 7):
            fig.add_annotation(
                x=xi,
                y=0,
                ax=xi,
                ay=0.45,
                xref="x",
                yref="y",
                axref="x",
                ayref="y",
                showarrow=True,
                arrowhead=2,
                arrowwidth=1.5,
                arrowcolor="black",
            )
        fig.add_annotation(
            x=L / 2,
            y=0.55,
            text=f"w = {w:.2f} kN/m",
            showarrow=False,
        )

    elif case == "Simple beam – partial UDL from left (length a)":
        w = params.get("w", 0.0)
        a = params["a_udl"]
        a = max(0.0, min(a, L))
        xs = [0, a]
        ys = [0.4, 0.4]
        fig.add_trace(
            go.Scatter(
                x=xs,
                y=ys,
                mode="lines",
                line=dict(width=0),
                fill="tozeroy",
                opacity=0.3,
                showlegend=False,
            )
        )
        # arrows
        for xi in np.linspace(0.1 * a, 0.9 * a, 5):
            fig.add_annotation(
                x=xi,
                y=0,
                ax=xi,
                ay=0.45,
                xref="x",
                yref="y",
                axref="x",
                ayref="y",
                showarrow=True,
                arrowhead=2,
                arrowwidth=1.5,
                arrowcolor="black",
            )
        fig.add_annotation(
            x=a / 2,
            y=0.55,
            text=f"w = {w:.2f} kN/m",
            showarrow=False,
        )

    elif case == "Overhanging beam – right overhang with point load at free end":
        P = params.get("P", 0.0)
        L_main = params.get("L_main", L)
        a_over = params.get("a_overhang", 0.0)
        L_total = L_main + a_over
        # Arrow points downward: (x, y) is arrow tip at beam, (ax, ay) is arrow start above
        fig.add_annotation(
            x=L_total,
            y=0,
            ax=L_total,
            ay=0.5,
            xref="x",
            yref="y",
            axref="x",
            ayref="y",
            showarrow=True,
            arrowhead=2,
            arrowwidth=2,
            arrowsize=1.2,
            arrowcolor="black",
        )
        fig.add_annotation(
            x=L_total,
            y=0.6,
            text=f"P = {P:.2f} kN",
            showarrow=False,
            font=dict(size=12),
        )

    if design_x_m is not None:
        fig.add_vline(x=float(design_x_m), line_width=2, line_dash="dash", line_color="green")
    if preview_x_m is not None:
        fig.add_vline(x=float(preview_x_m), line_width=2, line_color="red")

    x_pad = max(float(L or 0.0) * 0.08, 0.12) if L is not None else 0.12

    fig.update_layout(
        title_text="",
        yaxis_title="",
        plot_bgcolor="white",
        margin=dict(l=16, r=16, t=28, b=64),
        height=170,
    )

    fig.update_xaxes(
        range=[-x_pad, float(L) + x_pad],
        title="x (m)",
        domain=[0.0, 1.0],
        showgrid=False,
        zeroline=False,
    )

    fig.update_yaxes(
        range=[-0.28, 0.68],
        visible=False,
        showgrid=False,
        zeroline=False,
    )
    return fig


def figure_sfd_from_state(state: dict) -> go.Figure:
    """Build the shear-force diagram from page-prepared numeric state."""
    x_plot = state["x_plot"]
    V_plot = state["V_plot"]
    support_positions_plot = state["support_positions_plot"]
    support_types_plot = state["support_types_plot"]
    L = state["L"]
    preview_x_m = state["preview_x_m"]
    design_x_m = state["design_x_m"]
    preview_V = state["preview_V"]
    x_pad = state["x_pad"]
    support_type = state["support_type"]
    design_mode_active = state["design_mode_active"]
    zone_limit_m = state["zone_limit_m"]

    fig_sfd = go.Figure()
    fig_sfd.add_trace(
        go.Scatter(
            x=x_plot,
            y=V_plot,
            mode="lines",
            name="V(x)",
            showlegend=False,
            fill="tozeroy",
            fillcolor="rgba(31, 119, 180, 0.15)",
        )
    )
    fig_sfd.add_hline(y=0, line_width=2, line_color="rgba(0,0,0,0.20)")
    for x_support in support_positions_plot:
        fig_sfd.add_vline(x=x_support, line_width=1, line_color="rgba(0,0,0,0.12)")
    if design_mode_active and L is not None and zone_limit_m > 0.0:
        fig_sfd.add_vrect(
            x0=0.0,
            x1=min(zone_limit_m, float(L)),
            fillcolor="red",
            opacity=0.05,
            line_width=0,
        )
        if support_type != "cantilever":
            fig_sfd.add_vrect(
                x0=max(0.0, float(L) - zone_limit_m),
                x1=float(L),
                fillcolor="red",
                opacity=0.05,
                line_width=0,
            )
    if design_x_m is not None:
        fig_sfd.add_vline(x=float(design_x_m), line_width=2, line_dash="dash", line_color="green")
    if preview_x_m is not None:
        fig_sfd.add_vline(x=float(preview_x_m), line_width=2, line_color="red")
    if preview_x_m is not None and preview_V is not None:
        fig_sfd.add_trace(
            go.Scatter(
                x=[float(preview_x_m)],
                y=[float(preview_V)],
                mode="markers",
                marker=dict(size=8, color="rgba(214, 39, 40, 0.95)"),
                showlegend=False,
            )
        )
    x_crit = state.get("critical_shear_x")
    V_crit = state.get("critical_shear_V")
    s_end = state.get("shear_spacing_end_mm")
    s_mid = state.get("shear_spacing_mid_mm")
    if design_mode_active and x_crit is not None and V_crit is not None:
        x_crit_f = float(x_crit)
        V_crit_f = float(V_crit)
        fig_sfd.add_trace(
            go.Scatter(
                x=[x_crit_f],
                y=[V_crit_f],
                mode="markers+text",
                text=[f"V* = {abs(V_crit_f):.1f} kN"],
                textposition="top center",
                marker=dict(size=10, color="rgba(31, 119, 180, 0.95)"),
                name="Critical shear",
                showlegend=False,
                cliponaxis=False,
            )
        )
        nearest_support_idx = None
        nearest_support_dist = None
        if support_positions_plot:
            nearest_support_idx = int(np.argmin([abs(x_crit_f - sx) for sx in support_positions_plot]))
            nearest_support_dist = abs(x_crit_f - support_positions_plot[nearest_support_idx])
        in_end_zone = bool(
            zone_limit_m > 0.0
            and nearest_support_dist is not None
            and nearest_support_dist <= zone_limit_m + 1e-9
        )
        if zone_limit_m <= 0.0 and nearest_support_dist is not None and nearest_support_dist <= 1e-6:
            in_end_zone = True
        s_used = s_end if in_end_zone else s_mid
        if in_end_zone and nearest_support_idx is not None:
            if support_positions_plot and len(support_positions_plot) >= 2:
                if nearest_support_idx == 0:
                    label = "Support 1 / Span 1"
                elif nearest_support_idx == len(support_positions_plot) - 1:
                    label = (
                        f"Support {nearest_support_idx + 1} / "
                        f"Span {len(support_positions_plot) - 1}"
                    )
                else:
                    label = (
                        f"Support {nearest_support_idx + 1} / "
                        f"Spans {nearest_support_idx}-{nearest_support_idx + 1}"
                    )
            else:
                label = f"Support {nearest_support_idx + 1}"
        elif support_positions_plot and len(support_positions_plot) >= 2:
            span_label = "Beam"
            for i in range(len(support_positions_plot) - 1):
                x0 = support_positions_plot[i]
                x1 = support_positions_plot[i + 1]
                if x0 - 1e-9 <= x_crit_f <= x1 + 1e-9:
                    span_label = f"Span {i + 1}"
                    break
            label = span_label
        else:
            label = "Midspan"
        if s_used is not None:
            annotation_text = f"{label}: governing s = {int(float(s_used))} mm"
            fig_sfd.add_annotation(
                x=x_crit_f,
                y=V_crit_f,
                text=annotation_text,
                showarrow=True,
                arrowhead=2,
                yshift=40,
            )
    fig_sfd.update_layout(
        title_text="",
        yaxis_title="",
        plot_bgcolor="white",
        margin=dict(l=16, r=16, t=28, b=64),
        height=300,
    )
    fig_sfd.update_xaxes(
        range=[-x_pad, float(L) + x_pad],
        title="x (m)",
        domain=[0.0, 1.0],
        showgrid=True,
        gridcolor="rgba(0,0,0,0.08)",
    )
    sfd_y_range = None
    if V_plot:
        V_min = float(np.min(V_plot))
        V_max = float(np.max(V_plot))
        V_abs = max(abs(V_min), abs(V_max), 1e-6)
        V_pad = max(0.15 * V_abs, 1e-6)
        sfd_y_range = [V_min - V_pad, V_max + V_pad]
    if sfd_y_range is None:
        sfd_y_range = [-1.0, 1.0]
    fig_sfd.update_yaxes(
        showgrid=True,
        gridcolor="rgba(0,0,0,0.08)",
        range=sfd_y_range,
    )
    _add_plotly_support_markers_aligned(
        fig_sfd,
        support_positions_plot=support_positions_plot,
        support_types_plot=support_types_plot,
        y_min=float(sfd_y_range[0]),
        y_max=float(sfd_y_range[1]),
        L=L,
        support_type_fallback=support_type,
    )
    return fig_sfd


def figure_bmd_from_state(state: dict, *, show_m_peak: bool = False) -> go.Figure:
    """Build the bending-moment diagram from page-prepared numeric state."""
    x_plot = state["x_plot"]
    M_plot = state["M_plot"]
    support_positions_plot = state["support_positions_plot"]
    support_types_plot = state["support_types_plot"]
    L = state["L"]
    preview_x_m = state["preview_x_m"]
    design_x_m = state["design_x_m"]
    preview_M = state["preview_M"]
    x_pad = state["x_pad"]
    support_type = state["support_type"]

    M_arr = np.asarray(M_plot, dtype=float) if M_plot else np.array([], dtype=float)
    M_disp = (-M_arr).tolist() if M_plot else []
    custom_m = M_arr.tolist() if M_plot else []
    bmd_line_kw: dict = {}
    if custom_m and len(custom_m) == len(x_plot):
        bmd_line_kw["customdata"] = np.asarray(custom_m, dtype=float)
        bmd_line_kw["hovertemplate"] = "x = %{x:.3f} m<br>M = %{customdata:.3f} kNm<extra></extra>"

    fig_bmd = go.Figure()
    fig_bmd.add_trace(
        go.Scatter(
            x=x_plot,
            y=M_disp,
            mode="lines",
            name="M(x)",
            showlegend=False,
            fill="tozeroy",
            fillcolor="rgba(31, 119, 180, 0.15)",
            **bmd_line_kw,
        )
    )
    fig_bmd.add_hline(y=0, line_width=2, line_color="rgba(0,0,0,0.20)")
    for x_support in support_positions_plot:
        fig_bmd.add_vline(x=x_support, line_width=1, line_color="rgba(0,0,0,0.12)")
    if design_x_m is not None:
        fig_bmd.add_vline(x=float(design_x_m), line_width=2, line_dash="dash", line_color="green")
    if preview_x_m is not None:
        fig_bmd.add_vline(x=float(preview_x_m), line_width=2, line_color="red")
    if preview_x_m is not None and preview_M is not None:
        fig_bmd.add_trace(
            go.Scatter(
                x=[float(preview_x_m)],
                y=[-float(preview_M)],
                mode="markers",
                marker=dict(size=8, color="rgba(214, 39, 40, 0.95)"),
                showlegend=False,
                customdata=[float(preview_M)],
                hovertemplate="x = %{x:.3f} m<br>M = %{customdata:.3f} kNm<extra></extra>",
            )
        )
    if show_m_peak and x_plot and M_plot and len(x_plot) == len(M_plot):
        idx_peak = int(np.argmax(np.abs(M_plot)))
        x_peak = float(x_plot[idx_peak])
        M_peak = float(M_plot[idx_peak])
        y_peak = -M_peak
        fig_bmd.add_trace(
            go.Scatter(
                x=[x_peak],
                y=[y_peak],
                mode="markers+text",
                marker=dict(size=8, color="rgba(31, 119, 180, 0.9)"),
                text=[f"|M|max = {abs(M_peak):.2f} kNm"],
                textposition="top center",
                cliponaxis=False,
                showlegend=False,
                customdata=[M_peak],
                hovertemplate="x = %{x:.3f} m<br>M = %{customdata:.3f} kNm<extra></extra>",
            )
        )
    bmd_y_range = None
    if M_plot:
        M_disp_min = float(np.min(M_disp))
        M_disp_max = float(np.max(M_disp))
        M_disp_abs = max(abs(M_disp_min), abs(M_disp_max), 1e-6)
        M_pad = max(0.15 * M_disp_abs, 1e-6)
        bmd_y_range = [M_disp_min - M_pad, M_disp_max + M_pad]
    if bmd_y_range is None:
        bmd_y_range = [-1.0, 1.0]

    fig_bmd.update_layout(
        title_text="",
        yaxis_title="",
        plot_bgcolor="white",
        margin=dict(l=16, r=16, t=28, b=64),
        height=300,
    )
    fig_bmd.update_xaxes(
        range=[-x_pad, float(L) + x_pad],
        title="x (m)",
        domain=[0.0, 1.0],
        showgrid=True,
        gridcolor="rgba(0,0,0,0.08)",
    )
    fig_bmd.update_yaxes(
        showgrid=True,
        gridcolor="rgba(0,0,0,0.08)",
        range=bmd_y_range,
    )
    _add_plotly_support_markers_aligned(
        fig_bmd,
        support_positions_plot=support_positions_plot,
        support_types_plot=support_types_plot,
        y_min=float(bmd_y_range[0]),
        y_max=float(bmd_y_range[1]),
        L=L,
        support_type_fallback=support_type,
    )
    return fig_bmd


def plot_section_locator_plotly(
    L: float,
    preview_x_m: float | None = None,
    design_x_m: float | None = None,
) -> go.Figure:
    """Compact locator line aligned to the same x-domain as the diagrams."""
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=[0, L],
            y=[0, 0],
            mode="lines",
            line=dict(width=4, color="rgba(220, 220, 228, 1.0)"),
            showlegend=False,
        )
    )
    if design_x_m is not None:
        fig.add_vline(x=float(design_x_m), line_width=2, line_dash="dash", line_color="green")
    if preview_x_m is not None:
        fig.add_trace(
            go.Scatter(
                x=[float(preview_x_m)],
                y=[0],
                mode="markers+text",
                marker=dict(size=8, color="rgba(255, 75, 75, 0.95)"),
                text=[f"{float(preview_x_m):.2f}"],
                textposition="top center",
                showlegend=False,
            )
        )

    x_pad = max(float(L or 0.0) * 0.08, 0.12) if L is not None else 0.12
    fig.update_layout(
        title_text="",
        yaxis_title="",
        plot_bgcolor="white",
        margin=dict(l=40, r=24, t=10, b=8),
        height=70,
    )
    fig.update_xaxes(
        range=[-x_pad, float(L) + x_pad],
        domain=[0.085, 1.0],
        showgrid=False,
        zeroline=False,
        visible=False,
    )
    fig.update_yaxes(
        range=[-0.08, 0.08],
        visible=False,
        showgrid=False,
        zeroline=False,
    )
    return fig
