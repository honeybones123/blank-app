"""Structured SLS Check 4 curvature presentation and active service-response projection."""
from __future__ import annotations

from contextvars import ContextVar
from typing import Any, Callable, Mapping

import streamlit as st

from engineering_page_sections import bending_sls_checks_view_with_icr as base
from engineering_page_sections.bending_checks_context import BendingSlsChecksInput
from engineering_page_sections.bending_sls_diagram import make_sls_canonical_section_figure
from widgets_helpers import render_plotly_diagram


_CONTEXT: ContextVar[tuple[BendingSlsChecksInput, Mapping[str, Any]] | None] = ContextVar(
    "sls_check4_curvature_context",
    default=None,
)

_SERVICE_MOMENT_EPS = 1.0e-9


def _project_service_response(
    result: Mapping[str, Any],
    view: BendingSlsChecksInput,
) -> dict[str, Any]:
    """Bind the selected revision's resolved SLS moment to its cracked section.

    The cracked neutral axis and I_cr remain the published authoritative section
    properties. This projection only applies the current selected SLS moment to
    those linear-elastic properties so curvature/strain/stress cannot replay a
    zero or stale service moment from a different publication context.
    """
    projected = dict(result)
    layers = [
        dict(layer)
        for layer in tuple(result.get("layers", ()) or ())
        if isinstance(layer, Mapping)
    ]

    service_moment = abs(float(view.demand_kNm or 0.0))
    Ec = float(view.concrete_modulus_mpa or 0.0)
    Es = float(view.steel_modulus_mpa or 0.0)
    icr = float(result.get("cracked_inertia_mm4", 0.0) or 0.0)
    dn = float(result.get("neutral_axis_depth_mm", 0.0) or 0.0)

    denominator = Ec * icr
    if service_moment > _SERVICE_MOMENT_EPS and denominator > 0.0:
        kappa = service_moment * 1.0e6 / denominator
    else:
        kappa = 0.0

    for layer in layers:
        y = float(layer.get("depth_from_compression_mm", 0.0) or 0.0)
        strain = kappa * (y - dn) if kappa > 0.0 else 0.0
        layer["strain"] = strain
        layer["stress_mpa"] = Es * strain if Es > 0.0 else 0.0

    concrete_strain = -kappa * dn if kappa > 0.0 else 0.0
    projected.update(
        {
            "service_moment_knm": service_moment,
            "curvature_per_mm": kappa,
            "concrete_extreme_strain": concrete_strain,
            "concrete_extreme_stress_mpa": Ec * concrete_strain if Ec > 0.0 else 0.0,
            "layers": tuple(layers),
        }
    )
    return projected


def _project_top_results(view: BendingSlsChecksInput) -> dict[str, Any]:
    top_results = view.mutable_results()
    for key in ("sls_cracked_section", "sls_cracked_section_ignore_compression"):
        value = top_results.get(key)
        if isinstance(value, Mapping):
            top_results[key] = _project_service_response(value, view)
    return top_results


def _canonical_stiffness_diagram(
    *,
    result: Mapping[str, Any],
    key: str,
) -> None:
    fig = make_sls_canonical_section_figure(result)
    fig.update_layout(height=330, margin=dict(l=10, r=15, t=40, b=15))
    render_plotly_diagram(
        fig,
        key=key,
        title="Cracked section used for service stiffness",
        config={"displayModeBar": False},
    )


def _check4_payload(
    view: BendingSlsChecksInput,
    result: Mapping[str, Any],
    *,
    ignore_compression: bool,
) -> tuple[str, str, Callable[[], None]]:
    icr = float(result.get("cracked_inertia_mm4", 0.0) or 0.0)
    Ec = float(view.concrete_modulus_mpa or 0.0)
    service_moment = float(result.get("service_moment_knm", 0.0) or 0.0)
    kappa = float(result.get("curvature_per_mm", 0.0) or 0.0)
    stiffness = Ec * icr
    has_service_moment = service_moment > _SERVICE_MOMENT_EPS
    suffix = "ignore" if ignore_compression else "include"

    purpose = rf"""**Purpose**

Calculate service curvature from the cracked-section flexural stiffness and the
resolved SLS bending moment for the currently selected bending case.

**From Check 3**

$$
\boxed{{I_{{cr}}={icr:,.3f}\ \text{{mm}}^4}}
$$

Curvature is calculated only when a non-zero service bending moment is available.
"""

    step1 = rf"""**Step 1 — Cracked flexural stiffness**

The cracked-section flexural stiffness is:

$$
E_c I_{{cr}}
$$

**For this beam**

$$
E_c={Ec:,.0f}\ \text{{MPa}}
$$

$$
I_{{cr}}={icr:,.3f}\ \text{{mm}}^4
$$

$$
E_c I_{{cr}}
=
({Ec:,.0f})({icr:,.3f})
=
{stiffness:.6e}\ \text{{N mm}}^2
$$

$$
\boxed{{E_c I_{{cr}}={stiffness:.6e}\ \text{{N mm}}^2}}
$$
"""

    if has_service_moment:
        step2 = rf"""**Step 2 — Service curvature**

For linear-elastic cracked-section behaviour:

$$
\kappa=\frac{{M_s}}{{E_c I_{{cr}}}}
$$

The current resolved service moment is:

$$
\boxed{{M_s={service_moment:.3f}\ \text{{kNm}}}}
$$

Convert the service moment to Nmm and substitute the current beam values:

$$
\kappa
=
\frac{{({service_moment:.3f})(10^6)}}{{({Ec:,.0f})({icr:,.3f})}}
=
{kappa:.6e}\ \text{{mm}}^{{-1}}
$$

$$
\boxed{{\kappa={kappa:.6e}\ \text{{mm}}^{{-1}}}}
$$

Check 5 uses this curvature to calculate the linear SLS strain distribution.
"""
        summary = f"Check 4 — Curvature | Result: kappa = {kappa:.3e} mm^-1"
    else:
        step2 = rf"""**Step 2 — Service curvature**

Curvature requires a service bending moment:

$$
\kappa=\frac{{M_s}}{{E_c I_{{cr}}}}
$$

For the currently selected bending case:

$$
\boxed{{M_s=0.000\ \text{{kNm}}}}
$$

**Service moment required.** No meaningful curvature, strain distribution or
elastic SLS stress result is reported until a non-zero SLS bending moment is
available for this case.
"""
        summary = "Check 4 — Curvature | Service moment required"

    def render_steps() -> None:
        st.markdown("#### Service curvature")
        base.base._step_row(
            step_md=step1,
            uid="bending_sls_check4_step_1",
            diagram_fn=lambda: _canonical_stiffness_diagram(
                result=result,
                key=f"bending_sls_check4_stiffness_{suffix}",
            ),
        )
        base.base._step_row(
            step_md=step2,
            uid="bending_sls_check4_step_2",
        )

    return summary, purpose, render_steps


def _missing_service_details(*, check_number: int, quantity: str) -> str:
    return rf"""**Service moment required**

The currently selected bending case has no non-zero SLS bending moment.

$$
\boxed{{M_s=0.000\ \text{{kNm}}}}
$$

Check {check_number} does not report a zero {quantity} as though it were a
completed serviceability calculation. Enter or generate an SLS bending moment,
then the cracked-section response will update automatically.
"""


def _install_curvature_dispatch() -> None:
    from engineering_page_sections import bending_sls_checks as legacy

    base._install_outer_dispatch()
    if getattr(legacy, "_structured_sls_check4_outer_step", None) is not None:
        return

    previous = legacy.step_expander_calcbox
    legacy._structured_sls_check4_outer_step = previous

    def outer(*args: Any, **kwargs: Any):
        context = _CONTEXT.get()
        uid = str(kwargs.get("uid", args[0] if args else ""))
        if context is None:
            return previous(*args, **kwargs)

        view, top_results = context
        ignore_compression = bool(
            st.session_state.get("sls_ignore_compression_reinforcement", False)
        )
        result = legacy._result_for_option(top_results, ignore_compression)
        if not result:
            return previous(*args, **kwargs)

        service_moment = float(result.get("service_moment_knm", 0.0) or 0.0)
        has_service_moment = service_moment > _SERVICE_MOMENT_EPS

        if uid == "bending_sls_3_4":
            summary, purpose, render_steps = _check4_payload(
                view,
                result,
                ignore_compression=ignore_compression,
            )
            revised = dict(kwargs)
            revised["summary_line"] = summary
            revised["details_md"] = purpose
            revised["diagram_fn"] = None
            revised["content_after"] = render_steps
            revised["progressive_steps"] = None
            return previous(*args, **revised)

        if not has_service_moment and uid == "bending_sls_3_5":
            revised = dict(kwargs)
            revised["summary_line"] = "Check 5 — Strain distribution | Service moment required"
            revised["details_md"] = _missing_service_details(
                check_number=5,
                quantity="strain distribution",
            )
            revised["diagram_fn"] = None
            revised["content_after"] = None
            revised["progressive_steps"] = None
            return previous(*args, **revised)

        if not has_service_moment and uid == "bending_sls_3_6":
            revised = dict(kwargs)
            revised["summary_line"] = "Check 6 — Concrete and reinforcement stresses | Service moment required"
            revised["details_md"] = _missing_service_details(
                check_number=6,
                quantity="stress result",
            )
            revised["diagram_fn"] = None
            revised["content_after"] = None
            revised["progressive_steps"] = None
            return previous(*args, **revised)

        return previous(*args, **kwargs)

    legacy.step_expander_calcbox = outer


def render_bending_sls_checks(view: BendingSlsChecksInput) -> None:
    """Render SLS Checks 2-4 with the active resolved SLS demand bound consistently."""
    _install_curvature_dispatch()
    projected_results = _project_top_results(view)
    projected_view = BendingSlsChecksInput(
        results=projected_results,
        width_mm=view.width_mm,
        overall_depth_mm=view.overall_depth_mm,
        effective_depth_mm=view.effective_depth_mm,
        reinforcement_area_mm2=view.reinforcement_area_mm2,
        concrete_modulus_mpa=view.concrete_modulus_mpa,
        steel_modulus_mpa=view.steel_modulus_mpa,
        demand_kNm=view.demand_kNm,
        moment_sign=view.moment_sign,
    )
    token = _CONTEXT.set((projected_view, projected_results))
    try:
        base.render_bending_sls_checks(projected_view)
    finally:
        _CONTEXT.reset(token)


__all__ = ["render_bending_sls_checks"]
