"""Shear zone layout strip diagram builders."""

from __future__ import annotations

import plotly.graph_objects as go


def build_shear_zone_layout_strip_figure(
    payload: dict,
    *,
    beam_depth_m: float = 0.18,
    title: str | None = None,
    show_stirrup_marks: bool = True,
    max_stirrup_marks: int = 400,
    reference_width_px: float = 640.0,
    min_tick_spacing_px: float = 6.0,
) -> go.Figure:
    """
    Plotly horizontal strip for Check 10 (3-zone layout).

    Draws zone colour bands, vertical stirrup ticks at each zone spacing (first tick
    offset by s/2 from the zone start), optional thinning when ticks would crowd in
    pixel space, and @s labels centred under each zone.
    """
    segs = list(payload.get("strip_segments_mm") or [])
    L_mm = float(payload.get("beam_length_mm") or 0.0)
    support_type = str(payload.get("support_type") or "")
    is_cantilever = bool(payload.get("is_cantilever", False))
    support_positions_mm = [float(v) for v in (payload.get("support_positions_mm") or [])]
    support_types = [str(v) for v in (payload.get("support_types") or [])]
    if L_mm <= 0.0 and segs:
        L_mm = max(float(s.get("x1_mm", 0.0) or 0.0) for s in segs)
    L_m = max(L_mm / 1000.0, 1e-9)

    y0, y1 = 0.0, float(beam_depth_m)
    inset = 0.06 * (y1 - y0)
    y_bot_reo = y0 + inset
    y_top_reo = y1 - inset

    zone_stirrup_line = {
        "1": "rgba(95, 42, 42, 0.78)",
        "2": "rgba(105, 72, 38, 0.76)",
        "3": "rgba(42, 98, 58, 0.76)",
    }

    fig = go.Figure()

    if not segs:
        fig.add_annotation(
            x=0.5 * L_m,
            y=0.5 * y1,
            text="No shear link spacing set",
            showarrow=False,
            font=dict(size=12, color="rgba(60,60,60,0.9)"),
        )
        fig.update_xaxes(title_text="Distance along member (m)", range=[0.0, max(L_m, 1e-6)])
        fig.update_yaxes(visible=False, range=[-0.05 * beam_depth_m, y1 + 0.2 * beam_depth_m])
        fig.update_layout(
            title=title or "Shear layout (required zone spacings from envelope / Check 10)",
            margin=dict(l=40, r=20, t=50, b=48),
            height=140,
            showlegend=False,
        )
        return fig

    scale_px_per_m = float(reference_width_px) / L_m
    stirrup_count = 0

    for seg in segs:
        x0 = float(seg.get("x0_mm", 0.0) or 0.0) / 1000.0
        x1 = float(seg.get("x1_mm", 0.0) or 0.0) / 1000.0
        sm = float(seg.get("spacing_mm", 0.0) or 0.0)
        color = str(seg.get("color") or "rgba(120,120,120,0.5)")
        zid = str(seg.get("zone", "1") or "1")
        line_col = zone_stirrup_line.get(zid, "rgba(51, 51, 51, 0.72)")

        fig.add_shape(
            type="rect",
            x0=x0,
            x1=x1,
            y0=y0,
            y1=y1,
            fillcolor=color,
            line=dict(width=0),
            layer="below",
        )

        sm_m = max(sm / 1000.0, 1e-9)
        spacing_px = sm_m * scale_px_per_m
        step = 2 if spacing_px < float(min_tick_spacing_px) else 1

        xm = 0.5 * (x0 + x1)
        fig.add_annotation(
            x=xm,
            y=y1 + 0.05 * beam_depth_m,
            text=f"req. @{sm:.0f} mm",
            showarrow=False,
            font=dict(size=10, color="rgba(45,45,45,0.92)"),
        )

        if show_stirrup_marks and sm_m > 0.0 and x1 > x0 + 1e-12:
            x_first = x0 + 0.5 * sm_m
            xi = x_first
            idx = 0
            while xi < x1 - 1e-9 and stirrup_count < max_stirrup_marks:
                if idx % step == 0:
                    fig.add_shape(
                        type="line",
                        x0=xi,
                        x1=xi,
                        y0=y_bot_reo,
                        y1=y_top_reo,
                        line=dict(color=line_col, width=1),
                        layer="above",
                    )
                    stirrup_count += 1
                xi += sm_m
                idx += 1

    fig.add_trace(
        go.Scatter(
            x=[0.0, L_m],
            y=[y1 * 0.5, y1 * 0.5],
            mode="lines",
            line=dict(color="rgba(40,40,40,0.85)", width=2),
            hoverinfo="skip",
            showlegend=False,
        )
    )
    if support_positions_mm and support_types and len(support_positions_mm) == len(support_types):
        support_symbols = {
            "fixed": "\u23ca",
            "pinned": "\u25b2",
            "roller": "\u25cb",
        }
        support_y = y0 - 0.07 * beam_depth_m
        for sx_mm, stype in zip(support_positions_mm, support_types):
            sx_m = float(sx_mm) / 1000.0
            key = str(stype or "").strip().lower()
            symbol = support_symbols.get(key, "\u25b2")
            fig.add_annotation(
                x=sx_m,
                y=support_y,
                text=symbol,
                showarrow=False,
                font=dict(size=14, color="rgba(35,35,35,0.95)"),
            )
    elif is_cantilever:
        fig.add_annotation(
            x=0.0,
            y=y0 - 0.07 * beam_depth_m,
            text="\u23ca",
            showarrow=False,
            font=dict(size=14, color="rgba(35,35,35,0.95)"),
        )
    elif support_type:
        fig.add_annotation(
            x=0.0,
            y=y0 - 0.07 * beam_depth_m,
            text="\u25b2",
            showarrow=False,
            font=dict(size=14, color="rgba(35,35,35,0.95)"),
        )
        fig.add_annotation(
            x=L_m,
            y=y0 - 0.07 * beam_depth_m,
            text="\u25cb",
            showarrow=False,
            font=dict(size=14, color="rgba(35,35,35,0.95)"),
        )
    fig.update_xaxes(title_text="Distance along member (m)", range=[0.0, max(L_m, 1e-6)])
    fig.update_yaxes(visible=False, range=[-0.18 * beam_depth_m, y1 + 0.22 * beam_depth_m])
    fig.update_layout(
        title=title or "Shear reinforcement layout (3 zones)",
        margin=dict(l=40, r=20, t=50, b=48),
        height=140,
        showlegend=False,
    )
    return fig
