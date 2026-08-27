"""ULS Check 2 strain-diagram annotations for reinforcement layer depth ``y_i``."""
from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass
from typing import Any

from engineering_page_sections import bending_uls_checks_view_embedded_force as base
from engineering_page_sections.bending_checks_context import BendingUlsChecksInput


@dataclass(frozen=True)
class _YiDiagramContext:
    rows: tuple[dict[str, Any], ...]
    dn_mm: float
    overall_depth_mm: float
    moment_sign: str


_YI_CONTEXT: ContextVar[_YiDiagramContext | None] = ContextVar(
    "bending_uls_check2_yi_diagram_context",
    default=None,
)


def _compact_layer_label(label: str) -> str:
    """Keep layer identity readable in the narrow Step 2 diagram column."""
    text = str(label or "Layer").strip()
    text = text.replace(" reinforcement — ", " · ")
    text = text.replace(" reinforcement - ", " · ")
    text = text.replace(" reinforcement", "")
    return text


def _plot_y_from_top(*, depth_from_compression_mm: float, D_mm: float, moment_sign: str) -> float:
    """Convert compression-face depth back to the section y-coordinate used by Plotly."""
    sign = str(moment_sign or "positive").strip().lower()
    if sign in {"negative", "hogging", "-", "neg"}:
        return float(D_mm) - float(depth_from_compression_mm)
    return float(depth_from_compression_mm)


def _annotate_yi(fig, context: _YiDiagramContext):
    """Overlay authoritative ``y_i`` levels and the solved ``d_n`` on the Step 2 strain plot."""
    D = float(context.overall_depth_mm)
    dn = float(context.dn_mm)
    sign = str(context.moment_sign or "positive")

    # The strain builder plots section coordinates from the physical top face.
    # Convert the compression-face neutral-axis depth to the same coordinate.
    y_na_plot = _plot_y_from_top(
        depth_from_compression_mm=dn,
        D_mm=D,
        moment_sign=sign,
    )

    # The existing dashed line shows the neutral axis; this label makes its
    # relationship to y_i explicit without adding another competing line.
    fig.add_annotation(
        x=0.98,
        y=y_na_plot,
        xref="paper",
        yref="y",
        text=f"<b>d<sub>n</sub> = {dn:.1f} mm</b>",
        showarrow=False,
        xanchor="right",
        yanchor="bottom",
        yshift=4,
        font=dict(size=9, color="black"),
        bgcolor="rgba(255,255,255,0.82)",
        borderpad=2,
    )

    for row in context.rows:
        depth = float(row.get("y", 0.0) or 0.0)
        y_plot = float(row.get("y_top", _plot_y_from_top(
            depth_from_compression_mm=depth,
            D_mm=D,
            moment_sign=sign,
        )))
        index = int(row.get("i", 0) or 0)
        label = _compact_layer_label(str(row.get("label", f"Layer {index}")))

        # A light guide across the panel lets the viewer read y_i as an actual
        # reinforcement elevation while keeping the compatibility line dominant.
        fig.add_shape(
            type="line",
            x0=0.06,
            x1=0.94,
            y0=y_plot,
            y1=y_plot,
            xref="paper",
            yref="y",
            line=dict(color="rgba(70,80,95,0.32)", width=0.8, dash="dot"),
            layer="below",
        )
        fig.add_annotation(
            x=0.02,
            y=y_plot,
            xref="paper",
            yref="y",
            text=f"<b>y<sub>{index}</sub> = {depth:.1f} mm</b><br>{label}",
            showarrow=False,
            xanchor="left",
            yanchor="middle",
            font=dict(size=8, color="rgb(55,65,80)"),
            bgcolor="rgba(255,255,255,0.82)",
            borderpad=2,
        )

    # Give the labels a little more horizontal breathing room without changing
    # the physical y-coordinate geometry or the authoritative strain profile.
    fig.update_layout(margin=dict(l=18, r=18, t=40, b=10))
    return fig


def _install_yi_dispatch() -> None:
    """Install one context-local annotation adapter around the existing Step 2 plot builder."""
    if getattr(base, "_uls_yi_original_plot_strain_profile", None) is not None:
        return

    original = base._plot_strain_profile
    base._uls_yi_original_plot_strain_profile = original

    def dispatch(*args: Any, **kwargs: Any):
        fig = original(*args, **kwargs)
        context = _YI_CONTEXT.get()
        if context is None:
            return fig

        state_label = kwargs.get("state_label")
        if state_label is None and len(args) > 1:
            state_label = args[1]
        if state_label is not None and not str(state_label).upper().startswith("ULS"):
            return fig
        return _annotate_yi(fig, context)

    base._plot_strain_profile = dispatch


def render_bending_uls_checks(view: BendingUlsChecksInput) -> None:
    """Render the established ULS sequence with y_i annotations on Check 2 Step 2."""
    _install_yi_dispatch()

    results = view.mutable_results()
    if results.get("_authoritative_uls"):
        rows = base._authoritative_layers(view, results)
        context = _YiDiagramContext(
            rows=rows,
            dn_mm=float(results.get("c", 0.0) or 0.0),
            overall_depth_mm=float(view.overall_depth_mm),
            moment_sign=str(view.moment_sign or "positive"),
        )
    else:
        context = None

    token = _YI_CONTEXT.set(context)
    try:
        base.render_bending_uls_checks(view)
    finally:
        _YI_CONTEXT.reset(token)


__all__ = ["render_bending_uls_checks"]
