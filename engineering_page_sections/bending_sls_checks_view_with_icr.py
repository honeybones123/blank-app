"""Structured SLS Check 3 presentation for cracked transformed inertia."""
from __future__ import annotations

from contextvars import ContextVar
from typing import Any, Callable, Mapping

import streamlit as st

from engineering_page_sections import bending_sls_checks_view as base
from engineering_page_sections.bending_checks_context import BendingSlsChecksInput
from engineering_page_sections.bending_sls_diagram import make_sls_canonical_section_figure
from widgets_helpers import render_plotly_diagram


_CONTEXT: ContextVar[tuple[BendingSlsChecksInput, Mapping[str, Any]] | None] = ContextVar(
    "sls_check3_structured_context",
    default=None,
)


def _active_layers(result: Mapping[str, Any]) -> tuple[Mapping[str, Any], ...]:
    return tuple(
        layer
        for layer in tuple(result.get("layers", ()) or ())
        if isinstance(layer, Mapping)
        and float(layer.get("area_mm2", 0.0) or 0.0) > 0.0
    )


def _layer_inertia_markdown(
    layers: tuple[Mapping[str, Any], ...],
    dn: float,
) -> str:
    blocks: list[str] = []
    for i, layer in enumerate(layers, start=1):
        label = str(layer.get("label", layer.get("layer_id", f"Layer {i}")))
        y = float(layer.get("depth_from_compression_mm", 0.0) or 0.0)
        area = float(layer.get("area_mm2", 0.0) or 0.0)
        factor = float(layer.get("transformed_factor", 0.0) or 0.0)
        contribution = float(layer.get("inertia_contribution_mm4", 0.0) or 0.0)
        state = str(layer.get("state", "neutral") or "neutral")
        included = bool(layer.get("included", True))
        delta = abs(y - dn)

        if not included:
            blocks.append(
                rf"""**{label} — omitted**

This layer is excluded by the current compression-reinforcement option.

$$
\Delta_{{{i}}}=|y_{{{i}}}-d_n|
=
|{y:.3f}-{dn:.3f}|
=
{delta:.3f}\ \text{{mm}}
$$

$$
\boxed{{I_{{s,{i}}}=0}}
$$"""
            )
            continue

        if state == "tension":
            formula = rf"I_{{s,{i}}}=nA_{{s,{i}}}(y_i-d_n)^2"
            distance_term = rf"({y:.6f}-{dn:.6f})^2"
        elif state == "compression":
            formula = rf"I_{{s,{i}}}=(n-1)A_{{s,{i}}}(d_n-y_i)^2"
            distance_term = rf"({dn:.6f}-{y:.6f})^2"
        else:
            blocks.append(
                rf"""**{label} — approximately at the neutral axis**

$$
\Delta_{{{i}}}=|{y:.3f}-{dn:.3f}|={delta:.3f}\ \text{{mm}}
$$

The parallel-axis contribution is approximately zero:

$$
\boxed{{I_{{s,{i}}}\approx0}}
$$"""
            )
            continue

        blocks.append(
            rf"""**{label} — {state}**

$$
\Delta_{{{i}}}=|y_{{{i}}}-d_n|
=
|{y:.3f}-{dn:.3f}|
=
{delta:.3f}\ \text{{mm}}
$$

$$
{formula}
$$

**For this beam**

$$
I_{{s,{i}}}
=
({factor:.6f})({area:.3f}){distance_term}
=
{contribution:,.3f}\ \text{{mm}}^4
$$

$$
\boxed{{I_{{s,{i}}}={contribution:,.3f}\ \text{{mm}}^4}}
$$"""
        )

    return "\n\n".join(blocks) or "No active reinforcement layers were published."


def _canonical_diagram(
    *,
    result: Mapping[str, Any],
    key: str,
    title: str,
) -> None:
    fig = make_sls_canonical_section_figure(result)
    fig.update_layout(height=340, margin=dict(l=10, r=15, t=40, b=15))
    render_plotly_diagram(
        fig,
        key=key,
        title=title,
        config={"displayModeBar": False},
    )


def _distance_diagram(
    *,
    result: Mapping[str, Any],
    key: str,
    title: str,
) -> None:
    fig = make_sls_canonical_section_figure(result)
    width = float(result.get("width_mm", 0.0) or 0.0)
    if width <= 0.0:
        width = 1.0
    dn = float(result.get("neutral_axis_depth_mm", 0.0) or 0.0)

    for i, layer in enumerate(_active_layers(result), start=1):
        y_from_comp = float(layer.get("depth_from_compression_mm", 0.0) or 0.0)
        y_top = float(layer.get("depth_from_top_mm", 0.0) or 0.0)
        delta = abs(y_from_comp - dn)
        fig.add_annotation(
            x=1.38 * width,
            y=y_top,
            text=(
                f"<b>y<sub>{i}</sub> = {y_from_comp:.1f} mm</b><br>"
                f"Δ<sub>{i}</sub> = |y<sub>{i}</sub> − d<sub>n</sub>| = {delta:.1f} mm"
            ),
            showarrow=False,
            xanchor="left",
            align="left",
            font=dict(size=9, color="#334155"),
            bgcolor="rgba(255,255,255,0.88)",
            borderpad=2,
        )

    fig.update_xaxes(range=[-0.18 * width, 1.95 * width])
    fig.update_layout(height=360, margin=dict(l=10, r=15, t=40, b=15))
    render_plotly_diagram(
        fig,
        key=key,
        title=title,
        config={"displayModeBar": False},
    )


def _check3_payload(
    view: BendingSlsChecksInput,
    result: Mapping[str, Any],
    *,
    ignore_compression: bool,
) -> tuple[str, Callable[[], None]]:
    layers = _active_layers(result)
    dn = float(result.get("neutral_axis_depth_mm", 0.0) or 0.0)
    concrete_i = float(result.get("concrete_inertia_mm4", 0.0) or 0.0)
    steel_i = float(result.get("steel_inertia_mm4", 0.0) or 0.0)
    icr = float(result.get("cracked_inertia_mm4", 0.0) or 0.0)
    shape = str(result.get("section_shape", "RECT") or "RECT")

    purpose = rf"""**Purpose**

Calculate the cracked transformed second moment of area using the converged
neutral axis from Check 2.

**From Check 2**

$$
\boxed{{d_n={dn:.3f}\ \text{{mm}}}}
$$

The cracked transformed inertia is assembled from the active concrete
compression region and the transformed reinforcement layers:

$$
\boxed{{I_{{cr}}=I_c+\sum I_{{s,i}}}}
$$
"""

    if shape == "RECT":
        step1_calc = rf"""
For a rectangular section, the active concrete compression region is measured
about the cracked neutral axis:

$$
I_c=\frac{{b d_n^3}}{{3}}
$$

**For this beam**

$$
I_c
=
\frac{{{float(view.width_mm):.3f}({dn:.6f})^3}}{{3}}
=
{concrete_i:,.3f}\ \text{{mm}}^4
$$
"""
    else:
        step1_calc = rf"""
For this {shape} section, the active concrete compression geometry is integrated
about the cracked neutral axis:

$$
I_c=\int_{{A_c}}(d_n-y)^2\,dA
$$

**For this beam**

$$
I_c={concrete_i:,.3f}\ \text{{mm}}^4
$$
"""

    step1 = rf"""**Step 1 — Concrete compression-region inertia**

Only the active concrete compression region contributes to the cracked-section
concrete inertia. Tensile concrete remains inactive.

{step1_calc}

$$
\boxed{{I_c={concrete_i:,.3f}\ \text{{mm}}^4}}
$$
"""

    step2 = rf"""**Step 2 — Transform each reinforcement layer**

Each included reinforcement layer contributes through the same transformed-area
factor established in Check 2 and the square of its distance from the cracked
neutral axis:

$$
\boxed{{I_{{s,i}}=k_iA_{{s,i}}\Delta_i^2}}
$$

where:

$$
\Delta_i=|y_i-d_n|
$$

For tension reinforcement, $k_i=n$. For included compression reinforcement,
$k_i=n-1$ because the gross concrete compression region already includes the
concrete displaced by the bar.

**For this beam**

{_layer_inertia_markdown(layers, dn)}

The total transformed reinforcement contribution is:

$$
\boxed{{\sum I_{{s,i}}={steel_i:,.3f}\ \text{{mm}}^4}}
$$
"""

    step3 = rf"""**Step 3 — Sum the cracked transformed inertia**

Combine the concrete compression-region inertia with every included transformed
reinforcement contribution:

$$
I_{{cr}}=I_c+\sum I_{{s,i}}
$$

**For this beam**

$$
I_{{cr}}
=
{concrete_i:,.3f}
+
{steel_i:,.3f}
=
{icr:,.3f}\ \text{{mm}}^4
$$

$$
\boxed{{I_{{cr}}={icr:,.3f}\ \text{{mm}}^4}}
$$

This is the cracked transformed stiffness used by Check 4 to calculate service
curvature.
"""

    suffix = "ignore" if ignore_compression else "include"

    def render_steps() -> None:
        st.markdown("#### Cracked transformed inertia")

        base._step_row(
            step_md=step1,
            uid="bending_sls_check3_step_1",
            diagram_fn=lambda: _canonical_diagram(
                result=result,
                key=f"bending_sls_check3_concrete_{suffix}",
                title="Cracked concrete compression region",
            ),
        )
        base._step_row(
            step_md=step2,
            uid="bending_sls_check3_step_2",
            diagram_fn=lambda: _distance_diagram(
                result=result,
                key=f"bending_sls_check3_layers_{suffix}",
                title="Reinforcement distances from the neutral axis",
            ),
        )
        base._step_row(
            step_md=step3,
            uid="bending_sls_check3_step_3",
        )

    return purpose, render_steps


def _install_outer_dispatch() -> None:
    from engineering_page_sections import bending_sls_checks as legacy

    base._install_dispatch(legacy)
    if getattr(legacy, "_structured_sls_check3_outer_step", None) is not None:
        return

    previous = legacy.step_expander_calcbox
    legacy._structured_sls_check3_outer_step = previous

    def outer(*args: Any, **kwargs: Any):
        context = _CONTEXT.get()
        uid = str(kwargs.get("uid", args[0] if args else ""))
        if context is None or uid != "bending_sls_3_3":
            return previous(*args, **kwargs)

        view, top_results = context
        ignore_compression = bool(
            st.session_state.get("sls_ignore_compression_reinforcement", False)
        )
        result = legacy._result_for_option(top_results, ignore_compression)
        if not result:
            return previous(*args, **kwargs)

        purpose, render_steps = _check3_payload(
            view,
            result,
            ignore_compression=ignore_compression,
        )
        revised = dict(kwargs)
        revised["details_md"] = purpose
        revised["diagram_fn"] = None
        revised["content_after"] = render_steps
        revised["progressive_steps"] = None
        return previous(*args, **revised)

    legacy.step_expander_calcbox = outer


def render_bending_sls_checks(view: BendingSlsChecksInput) -> None:
    """Render the structured SLS sequence with step-by-step Check 2 and Check 3."""
    _install_outer_dispatch()
    top_results = view.mutable_results()
    token = _CONTEXT.set((view, top_results))
    try:
        base.render_bending_sls_checks(view)
    finally:
        _CONTEXT.reset(token)


__all__ = ["render_bending_sls_checks"]
