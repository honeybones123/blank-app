"""Shear visualisation layout and support adapters."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import plotly.graph_objects as go

from shear_visuals import BEHAVIOUR_VISUAL_HEIGHT, BEHAVIOUR_VISUAL_WIDTH


SHEAR_VISUAL_HEIGHT_PX = BEHAVIOUR_VISUAL_HEIGHT
SHEAR_BEHAVIOUR_MAX_WIDTH_PX = BEHAVIOUR_VISUAL_WIDTH
MCFT_BEHAVIOUR_MARGIN = dict(l=10, r=10, t=8, b=10)

def _support_pair_from_resolved_support_type(support_type: str | None) -> tuple[str, str] | None:
    raw_label = str(support_type or "").strip()
    label = raw_label.replace("-", "–")
    if not label:
        return None
    if raw_label == "Fixed-ended":
        return ("Fixed", "Fixed")
    if label == "Fixed–Pinned":
        return ("Fixed", "Pinned")
    if label == "Pinned–Fixed":
        return ("Pinned", "Fixed")
    if label in ("Pinned–Pinned", "Continuous – end span", "Continuous – interior span"):
        return ("Pinned", "Pinned")
    if label == "Simply supported":
        return ("Pinned", "Roller")
    return None

def _coalesce_num(v, default: float) -> float:
    """Return default only if v is None (preserves 0)."""
    return default if v is None else float(v)

def _standardise_shear_visual_layout(fig, *, title_pad_t: int = 28):
    fig.update_layout(
        autosize=True,
        height=SHEAR_VISUAL_HEIGHT_PX,
        margin=dict(l=10, r=10, t=title_pad_t, b=10),
    )
    return fig

def _render_plotly_in_mcft_column(
    fig: go.Figure,
    *,
    chart_key: str,
    render_centered_plotly: Callable[..., Any],
) -> None:
    """MCFT static Plotly: same pipeline as side view / cross-section (full-width block)."""
    render_centered_plotly(
        fig,
        chart_key=chart_key,
        max_width_px=SHEAR_BEHAVIOUR_MAX_WIDTH_PX,
        height_px=SHEAR_VISUAL_HEIGHT_PX,
        title_pad_t=int(MCFT_BEHAVIOUR_MARGIN["t"]),
        compact_top=True,
    )

def _render_mcft_behaviour_chart(
    fig: go.Figure,
    *,
    chart_key: str,
    animated: bool,
    render_centered_plotly: Callable[..., Any],
    render_animated_plotly: Callable[..., Any],
    height_px: int | None = None,
) -> None:
    plot_h = int(height_px or fig.layout.height or SHEAR_VISUAL_HEIGHT_PX)
    if animated:
        render_animated_plotly(
            fig,
            height=plot_h,
            centered=True,
            chart_key=chart_key,
            compact_top=True,
            title_pad_t=int(MCFT_BEHAVIOUR_MARGIN["t"]),
            max_width_px=int(BEHAVIOUR_VISUAL_WIDTH),
        )
    else:
        render_centered_plotly(
            fig,
            chart_key=chart_key,
            max_width_px=SHEAR_BEHAVIOUR_MAX_WIDTH_PX,
            height_px=plot_h,
            title_pad_t=int(MCFT_BEHAVIOUR_MARGIN["t"]),
            compact_top=True,
        )


__all__ = [
    "MCFT_BEHAVIOUR_MARGIN",
    "SHEAR_BEHAVIOUR_MAX_WIDTH_PX",
    "SHEAR_VISUAL_HEIGHT_PX",
    "_coalesce_num",
    "_render_mcft_behaviour_chart",
    "_render_plotly_in_mcft_column",
    "_standardise_shear_visual_layout",
    "_support_pair_from_resolved_support_type",
]
