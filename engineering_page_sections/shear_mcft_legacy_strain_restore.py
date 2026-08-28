"""Restore the older Check 4 MCFT longitudinal strain profile presentation.

This is presentation-only.  The current Check 4 location/wrapper and the force-resolution
figure remain unchanged.  Only the non-force longitudinal strain profile is replaced with
the older full top-to-bottom strain model, using the same authoritative strains already
resolved by the Shear page.
"""

from __future__ import annotations

from typing import Any

import plotly.graph_objects as go


_COLOURED_STRAIN_LINE_WIDTH = 2.6


def _legacy_mcft_strain_profile_fig(
    eps_top_uls: float,
    eps_x_mcft: float,
    eps_bot_uls: float,
    *,
    height: int = 430,
) -> go.Figure:
    """Older full-depth ULS strain profile with MCFT eps_x at mid-depth."""

    def _safe(value: Any) -> float:
        try:
            return float(value)
        except Exception:
            return 0.0

    eps_top_uls = _safe(eps_top_uls)
    eps_x_mcft = _safe(eps_x_mcft)
    eps_bot_uls = _safe(eps_bot_uls)

    y_top = 0.0
    y_mid = 0.5
    y_bot = 1.0

    fig = go.Figure()

    # Older diagram model: zero-strain axis ends exactly at the top and bottom fibres.
    fig.add_shape(
        type="line",
        x0=0,
        x1=0,
        y0=y_top,
        y1=y_bot,
        line=dict(width=4, color="black"),
        layer="below",
    )

    # Full calculated ULS top-to-bottom strain profile.
    fig.add_trace(
        go.Scatter(
            x=[eps_top_uls, eps_bot_uls],
            y=[y_top, y_bot],
            mode="lines",
            line=dict(width=3, color="black"),
            hoverinfo="skip",
            showlegend=False,
        )
    )

    emax_temp = max(abs(eps_top_uls), abs(eps_x_mcft), abs(eps_bot_uls), 1e-6)

    # Mid-depth MCFT reference guide.
    fig.add_shape(
        type="line",
        x0=-0.5 * emax_temp,
        y0=y_mid,
        x1=0.5 * emax_temp,
        y1=y_mid,
        line=dict(width=1, color="grey", dash="dash"),
        layer="below",
    )

    # Neutral axis from the full ULS profile.
    eps_diff = eps_bot_uls - eps_top_uls
    y_na = None
    if abs(eps_diff) > 1e-9:
        y_na = y_top + (y_bot - y_top) * (0.0 - eps_top_uls) / eps_diff
        y_na = max(y_top, min(y_bot, y_na))

    if y_na is not None and y_top <= y_na <= y_bot:
        fig.add_shape(
            type="line",
            x0=-0.5 * emax_temp,
            y0=y_na,
            x1=0.5 * emax_temp,
            y1=y_na,
            line=dict(width=1, color="rgba(100,100,100,0.5)", dash="dot"),
            layer="below",
        )
        fig.add_trace(
            go.Scatter(
                x=[0.0],
                y=[y_na],
                mode="markers",
                marker=dict(size=10, color="black", symbol="diamond"),
                hoverinfo="skip",
                showlegend=False,
            )
        )
        fig.add_annotation(
            x=0.0,
            y=y_na,
            text="ε=0 (ULS)",
            showarrow=False,
            font=dict(size=10, color="rgba(70,70,90,0.8)"),
            xanchor="left",
            xshift=8,
            bgcolor="rgba(255,255,255,0.8)",
        )

    color_top = "red" if eps_top_uls <= 0.0 else "blue"
    color_mid = "red" if eps_x_mcft < 0.0 else "blue"
    color_bot = "red" if eps_bot_uls < 0.0 else "blue"

    # Reinstate the older coloured top / mid / bottom strain ticks, just slightly thicker.
    for y, eps, colour in (
        (y_top, eps_top_uls, color_top),
        (y_mid, eps_x_mcft, color_mid),
        (y_bot, eps_bot_uls, color_bot),
    ):
        fig.add_shape(
            type="line",
            x0=0,
            y0=y,
            x1=eps,
            y1=y,
            line=dict(color=colour, width=_COLOURED_STRAIN_LINE_WIDTH),
            layer="above",
        )

    # MCFT point at mid-depth.
    fig.add_trace(
        go.Scatter(
            x=[eps_x_mcft],
            y=[y_mid],
            mode="markers",
            marker=dict(size=14, color=color_mid, line=dict(width=2, color="black")),
            hoverinfo="skip",
            showlegend=False,
        )
    )

    emax = max(abs(eps_top_uls), abs(eps_x_mcft), abs(eps_bot_uls), 1e-6)
    label_offset = 0.05 * emax

    def _label_position(eps: float) -> tuple[float, str, str]:
        if eps < 0.0:
            return eps - label_offset, "right", "(compression)"
        return eps + label_offset, "left", "(tension)"

    label_x_top, xanchor_top, state_top = _label_position(eps_top_uls)
    fig.add_annotation(
        x=label_x_top,
        y=y_top,
        text=(
            f"ε<sub>top</sub> = {eps_top_uls:.5f}"
            f"<br><span style='font-size:10px'>{state_top}</span>"
        ),
        showarrow=False,
        font=dict(size=12, color=color_top),
        xanchor=xanchor_top,
        yshift=-12,
        bgcolor="rgba(255,255,255,0.85)",
    )

    label_x_mid, xanchor_mid, state_mid = _label_position(eps_x_mcft)
    fig.add_annotation(
        x=label_x_mid,
        y=y_mid,
        text=(
            f"ε<sub>x</sub> = {eps_x_mcft:.5f}"
            "<br><span style='font-size:11px'>mid-depth (MCFT)</span>"
            f"<br><span style='font-size:10px'>{state_mid}</span>"
        ),
        showarrow=False,
        font=dict(size=12, color=color_mid),
        xanchor=xanchor_mid,
        bgcolor="rgba(255,255,255,0.85)",
    )

    label_x_bot, xanchor_bot, state_bot = _label_position(eps_bot_uls)
    fig.add_annotation(
        x=label_x_bot,
        y=y_bot,
        text=(
            f"ε<sub>bot</sub> = {eps_bot_uls:.5f}"
            f"<br><span style='font-size:10px'>{state_bot}</span>"
        ),
        showarrow=False,
        font=dict(size=12, color=color_bot),
        xanchor=xanchor_bot,
        yshift=12,
        bgcolor="rgba(255,255,255,0.85)",
    )

    xmin = min(eps_top_uls, eps_bot_uls, eps_x_mcft, 0.0) - label_offset
    xmax = max(eps_top_uls, eps_bot_uls, eps_x_mcft, 0.0) + label_offset
    span = xmax - xmin
    if span < 1e-6:
        span = 1e-4
    x_pad = 0.20 * span

    # Match the old model's small 5% top/bottom fibre clearance.  The current
    # Streamlit side-by-side wrapper still owns where and how large this figure is displayed.
    fig.update_layout(
        width=640,
        height=int(height),
        margin=dict(t=20, b=20, l=60, r=20),
        xaxis=dict(
            visible=False,
            range=[xmin - x_pad, xmax + x_pad],
            fixedrange=True,
            zeroline=False,
            showgrid=False,
        ),
        yaxis=dict(
            visible=False,
            showticklabels=False,
            showgrid=False,
            autorange=False,
            range=[y_bot + 0.05, y_top - 0.05],
            zeroline=False,
        ),
        paper_bgcolor="white",
        plot_bgcolor="white",
        showlegend=False,
    )

    return fig


def install_legacy_mcft_strain_profile() -> None:
    """Replace only the non-force Check 4 strain figure with the older diagram model."""

    from engineering_page_sections import shear_mcft_strength_checks as mcft_module

    if getattr(mcft_module, "_legacy_mcft_strain_profile_installed", False):
        return

    original_builder = mcft_module.make_mcft_longitudinal_strain_profile_fig

    def restored_builder(*args: Any, **kwargs: Any):
        if bool(kwargs.get("force_resolution", False)):
            return original_builder(*args, **kwargs)

        eps_top = kwargs.get("eps_top_uls", args[0] if len(args) > 0 else 0.0)
        eps_x = kwargs.get("eps_x_mcft", args[1] if len(args) > 1 else 0.0)
        eps_bot = kwargs.get("eps_bot_uls", args[2] if len(args) > 2 else 0.0)
        height = int(kwargs.get("height", 430) or 430)
        return _legacy_mcft_strain_profile_fig(
            eps_top,
            eps_x,
            eps_bot,
            height=height,
        )

    mcft_module.make_mcft_longitudinal_strain_profile_fig = restored_builder
    mcft_module._legacy_mcft_strain_profile_installed = True


__all__ = ["install_legacy_mcft_strain_profile"]
