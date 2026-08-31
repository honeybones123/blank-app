"""Structured SLS bending-check presentation with a ULS-style Check 2 teaching flow."""
from __future__ import annotations

from contextvars import ContextVar
from typing import Any, Callable, Mapping

import streamlit as st

from bending_diagrams import _make_sls_stress_block_figure
from engineering_page_sections.bending_checks_context import BendingSlsChecksInput
from engineering_page_sections.bending_sls_diagram import make_sls_canonical_section_figure
from engineering_page_sections.bending_sls_transformed_diagram import (
    make_sls_transformed_section_figure,
)
from widgets_helpers import calcbox, render_plotly_diagram


_ACTIVE: ContextVar[Callable[..., Any] | None] = ContextVar(
    "sls_check2_structured_adapter",
    default=None,
)


def _layers(result: Mapping[str, Any]) -> tuple[Mapping[str, Any], ...]:
    return tuple(
        layer
        for layer in tuple(result.get("layers", ()) or ())
        if isinstance(layer, Mapping)
        and float(layer.get("area_mm2", 0.0) or 0.0) > 0.0
    )


def _classification_markdown(
    layers: tuple[Mapping[str, Any], ...],
    dn: float,
) -> str:
    blocks: list[str] = []
    for i, layer in enumerate(layers, start=1):
        label = str(layer.get("label", layer.get("layer_id", f"Layer {i}")))
        y = float(layer.get("depth_from_compression_mm", 0.0) or 0.0)
        state = str(layer.get("state", "neutral") or "neutral")
        if y < dn - 1e-9:
            relation = "<"
        elif y > dn + 1e-9:
            relation = ">"
        else:
            relation = r"\approx"
        included = bool(layer.get("included", True))
        omitted = (
            "\n\n**Contribution:** omitted by the current compression-reinforcement option."
            if not included
            else ""
        )
        blocks.append(
            rf"""**{label}**

$$
y_{{{i}}}={y:.3f}\ \text{{mm}}\ {relation}\ d_n={dn:.3f}\ \text{{mm}}
$$

$$
\boxed{{\text{{{state}}}}}
$$
{omitted}"""
        )
    return "\n\n".join(blocks) or "No active reinforcement layers were published."


def _transformed_area_markdown(
    layers: tuple[Mapping[str, Any], ...],
) -> str:
    """Explain steel-to-concrete area transformation before any first moments."""

    blocks: list[str] = []
    for i, layer in enumerate(layers, start=1):
        label = str(layer.get("label", layer.get("layer_id", f"Layer {i}")))
        area = float(layer.get("area_mm2", 0.0) or 0.0)
        state = str(layer.get("state", "neutral") or "neutral")
        included = bool(layer.get("included", True))
        factor = float(layer.get("transformed_factor", 0.0) or 0.0)
        equivalent_area = factor * area

        if not included:
            blocks.append(
                rf"""**{label}**

This physical steel layer is omitted by the current compression-reinforcement option.

$$
\boxed{{A'_{{s,{i}}}=0}}
$$"""
            )
            continue

        if state == "tension":
            blocks.append(
                rf"""**{label} — tension**

Because concrete is the reference material, replace the physical steel area by:

$$
A'_{{s,t,{i}}}=nA_{{s,{i}}}
$$

**For this beam**

$$
A'_{{s,t,{i}}}
=
({factor:.6f})({area:.3f})
=
{equivalent_area:,.3f}\ \text{{mm}}^2
$$

$$
\boxed{{A'_{{s,t,{i}}}={equivalent_area:,.3f}\ \text{{mm}}^2}}
$$"""
            )
        elif state == "compression":
            blocks.append(
                rf"""**{label} — compression**

The gross concrete compression area already contains the concrete displaced by this
steel, so only the additional equivalent area is added:

$$
A'_{{s,c,{i}}}=(n-1)A_{{s,{i}}}
$$

**For this beam**

$$
A'_{{s,c,{i}}}
=
({factor:.6f})({area:.3f})
=
{equivalent_area:,.3f}\ \text{{mm}}^2
$$

$$
\boxed{{A'_{{s,c,{i}}}={equivalent_area:,.3f}\ \text{{mm}}^2}}
$$"""
            )
        else:
            blocks.append(
                rf"""**{label} — neutral-axis layer**

The layer is approximately at the neutral axis. Its transformed area may still exist,
but its first-moment lever arm is approximately zero.

$$
A'_{{s,{i}}}={equivalent_area:,.3f}\ \text{{mm}}^2
$$"""
            )

    return "\n\n".join(blocks) or "No active reinforcement layers were published."


def _first_moment_markdown(
    layers: tuple[Mapping[str, Any], ...],
    dn: float,
) -> str:
    """Take first moments only after the equivalent transformed areas are known."""

    blocks: list[str] = []
    for i, layer in enumerate(layers, start=1):
        label = str(layer.get("label", layer.get("layer_id", f"Layer {i}")))
        y = float(layer.get("depth_from_compression_mm", 0.0) or 0.0)
        area = float(layer.get("area_mm2", 0.0) or 0.0)
        state = str(layer.get("state", "neutral") or "neutral")
        included = bool(layer.get("included", True))
        factor = float(layer.get("transformed_factor", 0.0) or 0.0)
        equivalent_area = factor * area
        contribution = float(layer.get("first_moment_mm3", 0.0) or 0.0)

        if not included:
            continue

        if state == "tension":
            blocks.append(
                rf"""**{label} — tension first moment**

$$
Q_{{s,t,{i}}}=A'_{{s,t,{i}}}(y_i-d_n)
$$

$$
Q_{{s,t,{i}}}
=
({equivalent_area:,.3f})({y:.3f}-{dn:.3f})
=
{contribution:,.3f}\ \text{{mm}}^3
$$

$$
\boxed{{Q_{{s,t,{i}}}={contribution:,.3f}\ \text{{mm}}^3}}
$$"""
            )
        elif state == "compression":
            blocks.append(
                rf"""**{label} — compression first moment**

$$
Q_{{s,c,{i}}}=A'_{{s,c,{i}}}(d_n-y_i)
$$

$$
Q_{{s,c,{i}}}
=
({equivalent_area:,.3f})({dn:.3f}-{y:.3f})
=
{contribution:,.3f}\ \text{{mm}}^3
$$

$$
\boxed{{Q_{{s,c,{i}}}={contribution:,.3f}\ \text{{mm}}^3}}
$$"""
            )
        else:
            blocks.append(
                rf"""**{label} — neutral-axis layer**

Its lever arm is approximately zero, so:

$$
\boxed{{Q_{{s,{i}}}\approx0}}
$$"""
            )

    return "\n\n".join(blocks) or "No included reinforcement first moments are required."


def _step_row(
    *,
    step_md: str,
    uid: str,
    diagram_fn: Callable[[], None] | None = None,
) -> None:
    calc_col, diagram_col = st.columns([2.0, 1.0], gap="large")
    with calc_col:
        calcbox(step_md, uid=uid)
    with diagram_col:
        if diagram_fn:
            diagram_fn()


def _check2_payload(
    view: BendingSlsChecksInput,
    result: Mapping[str, Any],
    *,
    ignore_compression: bool,
    legacy: Any,
) -> tuple[str, Callable[[], None]]:
    layers = _layers(result)
    n = float(result.get("modular_ratio", 0.0) or 0.0)
    dn = float(result.get("neutral_axis_depth_mm", 0.0) or 0.0)
    residual = float(result.get("equilibrium_residual_mm3", 0.0) or 0.0)
    tolerance = float(result.get("solver_tolerance_mm3", 0.0) or 0.0)
    concrete_q = float(result.get("concrete_first_moment_mm3", 0.0) or 0.0)
    shape = str(result.get("section_shape", "RECT") or "RECT")
    compression_face = str(result.get("compression_face", "top") or "top")

    q_compression = sum(
        float(layer.get("first_moment_mm3", 0.0) or 0.0)
        for layer in layers
        if bool(layer.get("included", True))
        and str(layer.get("state", "neutral") or "neutral") == "compression"
    )
    q_tension = sum(
        float(layer.get("first_moment_mm3", 0.0) or 0.0)
        for layer in layers
        if bool(layer.get("included", True))
        and str(layer.get("state", "neutral") or "neutral") == "tension"
    )

    if shape == "RECT":
        concrete_formula = r"Q_c=\frac{b d_n^2}{2}"
        concrete_sub = rf"""
$$
Q_c
=
\frac{{{float(view.width_mm):.3f}({dn:.6f})^2}}{{2}}
=
{concrete_q:,.3f}\ \text{{mm}}^3
$$
"""
    else:
        concrete_formula = r"Q_c(d_n)=\int_{A_c}(d_n-y)\,dA"
        concrete_sub = rf"""
$$
Q_c({dn:.6f})
=
{concrete_q:,.3f}\ \text{{mm}}^3
$$
"""

    purpose = rf"""**From Check 1**

$$
\boxed{{n={n:.6f}}}
$$

**Purpose**

Determine the cracked-section neutral-axis depth $d_n$, measured from the
current **{compression_face} compression face**, using elastic transformed-section
equilibrium:

$$
\boxed{{Q_c+Q_{{s,c}}=Q_{{s,t}}}}
$$

The solver varies $d_n$ until the first moments of the active concrete and the
**equivalent transformed steel areas** balance. The calculations below show the
final converged evaluation for this beam.
"""

    step1 = rf"""**Step 1 — Define the unknown neutral axis**

The cracked neutral-axis depth is initially unknown:

$$
d_n=\text{{unknown}}
$$

The solver varies $d_n$ from the active compression face. Each candidate value changes:

- the active concrete compression region;
- whether each physical steel layer is in tension or compression; and
- the lever arm used when the transformed areas are checked for equilibrium.

The diagram alongside this step shows the **final converged section for reference**.
The converged value itself is accepted in Step 6.
"""

    step2 = rf"""**Step 2 — Ignore tensile concrete**

Concrete on the tension side of the cracked neutral axis is cracked and is not included
in the transformed-section equilibrium.

For this {shape} section:

$$
{concrete_formula}
$$

**For the final converged evaluation**

{concrete_sub}

$$
\boxed{{Q_c={concrete_q:,.3f}\ \text{{mm}}^3}}
$$
"""

    step3 = rf"""**Step 3 — Classify every physical reinforcement layer**

For each physical reinforcement layer:

$$
y_i<d_n\Rightarrow\text{{compression}}
$$

$$
y_i>d_n\Rightarrow\text{{tension}}
$$

$$
y_i\approx d_n\Rightarrow\text{{approximately zero first-moment contribution}}
$$

Physical names such as “top” and “bottom” do not set the engineering state.

**For the final converged evaluation**

{_classification_markdown(layers, dn)}
"""

    step4 = rf"""**Step 4 — Transform physical steel into equivalent concrete area**

The transformed-section method uses concrete as the reference material. The physical
steel area is therefore replaced by an equivalent area using the modular ratio from
Check 1:

$$
\boxed{{n={n:.6f}}}
$$

For tension reinforcement in the cracked concrete region:

$$
A'_{{s,t,i}}=nA_{{s,i}}
$$

For compression reinforcement already inside the gross concrete compression area:

$$
A'_{{s,c,i}}=(n-1)A_{{s,i}}
$$

The $(n-1)$ factor avoids counting the concrete displaced by compression steel twice.
At this step we are calculating **areas only** — the first-moment lever arms are applied
in Step 5.

**For this beam**

{_transformed_area_markdown(layers)}
"""

    step5 = rf"""**Step 5 — Take first moments and enforce transformed-section equilibrium**

Now multiply each equivalent transformed area from Step 4 by its distance from the
candidate neutral axis.

{_first_moment_markdown(layers, dn)}

The equilibrium condition is:

$$
Q_c+Q_{{s,c}}=Q_{{s,t}}
$$

**For the final converged evaluation**

$$
{concrete_q:,.3f}
+
{q_compression:,.3f}
=
{q_tension:,.3f}\ \text{{mm}}^3
$$

Equivalently, form the residual:

$$
R(d_n)=Q_c(d_n)+Q_{{s,c}}(d_n)-Q_{{s,t}}(d_n)
$$

$$
R({dn:.6f})={residual:.6g}\ \text{{mm}}^3
$$

$$
\boxed{{R(d_n)\approx0}}
$$
"""

    step6 = rf"""**Step 6 — Accept the converged cracked neutral axis**

The solver accepts a candidate neutral axis when:

$$
|R(d_n)|\leq R_{{\mathrm{{tol}}}}
$$

**For this beam**

$$
|{residual:.6g}|
\leq
{tolerance:.6g}\ \text{{mm}}^3
$$

Therefore the converged cracked neutral axis is:

$$
\boxed{{d_n={dn:.3f}\ \text{{mm}}}}
$$

Check 3 uses this converged $d_n$ to calculate $I_{{cr}}$.
"""

    suffix = "ignore" if ignore_compression else "include"

    def canonical_diagram(title: str, key_suffix: str) -> None:
        fig = make_sls_canonical_section_figure(result)
        fig.update_layout(height=320, margin=dict(l=10, r=10, t=40, b=10))
        render_plotly_diagram(
            fig,
            key=f"bending_sls_check2_{key_suffix}_{suffix}",
            title=title,
            config={"displayModeBar": False},
        )

    def transformed_diagram() -> None:
        fig = make_sls_transformed_section_figure(result)
        render_plotly_diagram(
            fig,
            key=f"bending_sls_check2_transformed_layers_{suffix}",
            title="Cracked transformed section (SLS)",
            config={"displayModeBar": False},
        )

    def stress_block_diagram(title: str, key_suffix: str) -> None:
        include_comp = any(
            bool(layer.get("included", True))
            and str(layer.get("state", "neutral") or "neutral") == "compression"
            for layer in layers
        )
        d_comp = next(
            (
                float(layer.get("depth_from_compression_mm", 0.0) or 0.0)
                for layer in layers
                if bool(layer.get("included", True))
                and str(layer.get("state", "neutral") or "neutral") == "compression"
            ),
            None,
        )
        fig = _make_sls_stress_block_figure(
            D_mm=float(view.overall_depth_mm),
            d_mm=float(view.effective_depth_mm),
            dn_mm=dn,
            include_comp=include_comp,
            d_comp_mm=d_comp,
            moment_sign=str(view.moment_sign or "positive"),
        )
        fig.update_layout(height=300, margin=dict(l=10, r=10, t=40, b=10))
        render_plotly_diagram(
            fig,
            key=f"bending_sls_check2_{key_suffix}_{suffix}",
            title=title,
            config={"displayModeBar": False},
        )

    def render_steps() -> None:
        st.markdown("#### Cracked neutral-axis calculation")

        _step_row(
            step_md=step1,
            uid="bending_sls_check2_step_1",
            diagram_fn=lambda: canonical_diagram(
                "Cracked section and neutral axis",
                "trial_section",
            ),
        )
        _step_row(
            step_md=step2,
            uid="bending_sls_check2_step_2",
            diagram_fn=lambda: stress_block_diagram(
                "Active concrete compression region",
                "concrete_region",
            ),
        )
        _step_row(
            step_md=step3,
            uid="bending_sls_check2_step_3",
            diagram_fn=lambda: canonical_diagram(
                "Reinforcement layer classification",
                "layer_classification",
            ),
        )

        # Step 4 needs a wide teaching canvas: the calculation stays intact and
        # the approved section + right-hand callout layout renders full-width
        # below it so the text cannot overlap the section diagram.
        calcbox(step4, uid="bending_sls_check2_step_4")
        transformed_diagram()

        _step_row(
            step_md=step5,
            uid="bending_sls_check2_step_5",
            diagram_fn=lambda: stress_block_diagram(
                "Transformed-section equilibrium",
                "equilibrium",
            ),
        )
        _step_row(
            step_md=step6,
            uid="bending_sls_check2_step_6",
        )

    return purpose, render_steps


def _install_dispatch(legacy: Any) -> None:
    if getattr(legacy, "_structured_sls_check2_original_step", None) is not None:
        return

    original = legacy.step_expander_calcbox
    legacy._structured_sls_check2_original_step = original

    def dispatch(*args: Any, **kwargs: Any):
        fn = _ACTIVE.get()
        return fn(original, *args, **kwargs) if fn else original(*args, **kwargs)

    legacy.step_expander_calcbox = dispatch


def render_bending_sls_checks(view: BendingSlsChecksInput) -> None:
    """Render SLS checks with Check 2 presented in the same step-by-step layout as ULS."""
    from engineering_page_sections import bending_sls_checks as legacy

    _install_dispatch(legacy)
    top_results = view.mutable_results()

    def intercept(original: Callable[..., Any], *args: Any, **kwargs: Any):
        uid = str(kwargs.get("uid", args[0] if args else ""))
        if uid != "bending_sls_3_2":
            return original(*args, **kwargs)

        ignore_compression = bool(
            st.session_state.get("sls_ignore_compression_reinforcement", False)
        )
        result = legacy._result_for_option(top_results, ignore_compression)
        if not result:
            return original(*args, **kwargs)

        purpose, render_steps = _check2_payload(
            view,
            result,
            ignore_compression=ignore_compression,
            legacy=legacy,
        )

        revised = dict(kwargs)
        revised["details_md"] = purpose
        revised["diagram_fn"] = None
        revised["content_after"] = render_steps
        revised["progressive_steps"] = None
        return original(*args, **revised)

    token = _ACTIVE.set(intercept)
    try:
        legacy.render_authoritative_sls_checks(
            top_results=top_results,
            b=view.width_mm,
            D=view.overall_depth_mm,
            d=view.effective_depth_mm,
            Ast=view.reinforcement_area_mm2,
            Ec=view.concrete_modulus_mpa,
            Es=view.steel_modulus_mpa,
            Mu_star=view.demand_kNm,
            moment_sign=view.moment_sign,
        )
    finally:
        _ACTIVE.reset(token)


__all__ = ["render_bending_sls_checks"]