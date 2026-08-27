"""Direct ULS Check 2 strain-diagram annotations for reinforcement layer depth ``y_i``."""
from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass
from typing import Any, Callable

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
    """Convert compression-face depth to the physical top-based Plotly y coordinate."""
    sign = str(moment_sign or "positive").strip().lower()
    if sign in {"negative", "hogging", "-", "neg"}:
        return float(D_mm) - float(depth_from_compression_mm)
    return float(depth_from_compression_mm)


def _annotate_yi(fig, context: _YiDiagramContext):
    """Overlay authoritative y_i levels, layer identity, strain and d_n on the strain plot."""
    D = float(context.overall_depth_mm)
    dn = float(context.dn_mm)
    sign = str(context.moment_sign or "positive")
    y_na_plot = _plot_y_from_top(
        depth_from_compression_mm=dn,
        D_mm=D,
        moment_sign=sign,
    )

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
        bgcolor="rgba(255,255,255,0.88)",
        borderpad=2,
    )

    for row in context.rows:
        depth = float(row.get("y", 0.0) or 0.0)
        y_plot = float(
            row.get(
                "y_top",
                _plot_y_from_top(
                    depth_from_compression_mm=depth,
                    D_mm=D,
                    moment_sign=sign,
                ),
            )
        )
        index = int(row.get("i", 0) or 0)
        label = _compact_layer_label(str(row.get("label", f"Layer {index}")))
        eps = base._strain_for_depth(depth, dn)

        fig.add_shape(
            type="line",
            x0=0.04,
            x1=0.96,
            y0=y_plot,
            y1=y_plot,
            xref="paper",
            yref="y",
            line=dict(color="rgba(70,80,95,0.38)", width=0.9, dash="dot"),
            layer="below",
        )
        fig.add_annotation(
            x=0.02,
            y=y_plot,
            xref="paper",
            yref="y",
            text=(
                f"<b>y<sub>{index}</sub> = {depth:.1f} mm</b><br>"
                f"{label}<br>"
                f"ε<sub>s,{index}</sub> = {eps:.6f}"
            ),
            showarrow=False,
            xanchor="left",
            yanchor="middle",
            font=dict(size=8, color="rgb(45,55,70)"),
            bgcolor="rgba(255,255,255,0.90)",
            borderpad=2,
        )

    fig.update_layout(margin=dict(l=22, r=18, t=40, b=10), height=320)
    return fig


def _render_step2_yi_diagram(context: _YiDiagramContext) -> None:
    """Build the Step 2 strain figure directly, then add y_i annotations before rendering."""
    state = base._stress_strain_state("ULS", moment_sign=context.moment_sign)

    # If a previous hot-reload installed the old plot-builder adapter, bypass it
    # so this path owns the annotations exactly once.
    plot_builder: Callable[..., Any] = getattr(
        base,
        "_uls_yi_original_plot_strain_profile",
        base._plot_strain_profile,
    )
    fig = plot_builder(
        state,
        state_label="ULS",
        layout=None,
        moment_sign=context.moment_sign,
    )
    _annotate_yi(fig, context)
    base.render_plotly_diagram(
        fig,
        key=f"bending_uls_check2_step2_strain_{context.moment_sign}",
        title="Reinforcement strain compatibility",
        config={"displayModeBar": False},
    )


def _install_step_row_dispatch() -> None:
    """Replace only the Step 2 diagram callback at the row-rendering boundary."""
    if getattr(base, "_uls_yi_original_step_row", None) is not None:
        return

    # Undo the previous plot-builder monkey patch if this process was hot-reloaded.
    original_plot = getattr(base, "_uls_yi_original_plot_strain_profile", None)
    if original_plot is not None:
        base._plot_strain_profile = original_plot

    original_step_row = base._step_row
    base._uls_yi_original_step_row = original_step_row

    def dispatch(*, step_md: str, uid: str, diagram_fn=None) -> None:
        context = _YI_CONTEXT.get()
        if uid == "bending_uls_check2_step_2" and context is not None:
            return original_step_row(
                step_md=step_md,
                uid=uid,
                diagram_fn=lambda: _render_step2_yi_diagram(context),
            )
        return original_step_row(step_md=step_md, uid=uid, diagram_fn=diagram_fn)

    base._step_row = dispatch


def render_bending_uls_checks(view: BendingUlsChecksInput) -> None:
    """Render ULS checks with direct y_i annotations on Check 2 Step 2."""
    _install_step_row_dispatch()

    results = view.mutable_results()
    if results.get("_authoritative_uls"):
        context = _YiDiagramContext(
            rows=base._authoritative_layers(view, results),
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
