"""Authoritative six-check SLS bending teaching sequence."""

from __future__ import annotations

import math
from typing import Any, Mapping

import pandas as pd
import streamlit as st

from engineering_page_sections.bending_sls_diagram import make_sls_canonical_section_figure
from state_and_helpers import update_results
from widgets_helpers import (
    apply_step_expander_css,
    info_i_button,
    render_plotly_diagram,
    step_expander_calcbox,
)


def _info_button(help_text: str, markdown: str) -> None:
    col, _spacer = st.columns([0.28, 0.72])
    with col:
        with info_i_button(help_text=help_text, use_container_width=True):
            st.markdown(markdown)


def _result_for_option(top_results: Mapping[str, Any], ignore: bool) -> dict[str, Any]:
    key = (
        "sls_cracked_section_ignore_compression"
        if ignore
        else "sls_cracked_section"
    )
    value = top_results.get(key)
    return dict(value) if isinstance(value, Mapping) else {}


def _layer_frame(layers: tuple[Mapping[str, Any], ...]) -> pd.DataFrame:
    rows = []
    for layer in layers:
        factor = float(layer.get("transformed_factor", 0.0) or 0.0)
        state = str(layer.get("state", "neutral") or "neutral")
        included = bool(layer.get("included", True))
        if not included:
            contribution = "omitted"
        elif state == "tension":
            contribution = "n A_s (y_i - d_n)"
        elif state == "compression":
            contribution = "(n - 1) A_s (d_n - y_i)"
        else:
            contribution = "approximately zero"
        rows.append(
            {
                "Layer": str(layer.get("label", layer.get("layer_id", "Layer"))),
                "A_s (mm²)": float(layer.get("area_mm2", 0.0) or 0.0),
                "y_i from compression face (mm)": float(
                    layer.get("depth_from_compression_mm", 0.0) or 0.0
                ),
                "Final state": state,
                "Factor": factor,
                "Transformed contribution": contribution,
            }
        )
    return pd.DataFrame(rows)


def _equilibrium_substitution(result: Mapping[str, Any]) -> str:
    concrete_q = float(result.get("concrete_first_moment_mm3", 0.0) or 0.0)
    compression_terms = []
    tension_terms = []
    for layer in tuple(result.get("layers", ()) or ()):
        state = str(layer.get("state", "neutral") or "neutral")
        if not bool(layer.get("included", True)) or state == "neutral":
            continue
        value = float(layer.get("first_moment_mm3", 0.0) or 0.0)
        term = f"{value:,.3f}"
        if state == "compression":
            compression_terms.append(term)
        elif state == "tension":
            tension_terms.append(term)
    left = " + ".join([f"{concrete_q:,.3f}", *compression_terms])
    right = " + ".join(tension_terms) or "0"
    return rf"{left} = {right}\ \text{{mm}}^3"


def _equilibrium_assembly(result: Mapping[str, Any]) -> str:
    """Return the published layer-by-layer numerical residual equation."""

    dn = float(result.get("neutral_axis_depth_mm", 0.0) or 0.0)
    shape = str(result.get("section_shape", "RECT") or "RECT")
    if shape == "RECT":
        width = float(result.get("width_mm", 0.0) or 0.0)
        concrete = rf"\frac{{{width:.3f}({dn:.6f})^2}}{{2}}"
    else:
        concrete_q = float(result.get("concrete_first_moment_mm3", 0.0) or 0.0)
        concrete = rf"Q_c({dn:.6f})={concrete_q:,.3f}"
    compression_terms = []
    tension_terms = []
    for layer in tuple(result.get("layers", ()) or ()):
        state = str(layer.get("state", "neutral") or "neutral")
        if not bool(layer.get("included", True)) or state == "neutral":
            continue
        factor = float(layer.get("transformed_factor", 0.0) or 0.0)
        area = float(layer.get("area_mm2", 0.0) or 0.0)
        y = float(layer.get("depth_from_compression_mm", 0.0) or 0.0)
        if state == "compression":
            compression_terms.append(
                rf"({factor:.4f})({area:.3f})({dn:.6f}-{y:.3f})"
            )
        elif state == "tension":
            tension_terms.append(
                rf"({factor:.4f})({area:.3f})({y:.3f}-{dn:.6f})"
            )
    left = " + ".join([concrete, *compression_terms])
    right = " + ".join(tension_terms) or "0"
    return f"{left} = {right}"


def render_authoritative_sls_checks(
    *,
    top_results: Mapping[str, Any],
    b: float,
    D: float,
    d: float,
    Ast: float,
    Ec: float,
    Es: float,
    Mu_star: float,
    moment_sign: str,
) -> None:
    """Render SLS Checks 1-6 from one authoritative cracked-section result."""

    del d, Ast, Mu_star, moment_sign  # Values are already bound into the publication.
    apply_step_expander_css()
    ignore_compression = st.checkbox(
        "Ignore compression reinforcement",
        value=False,
        key="sls_ignore_compression_reinforcement",
        help=(
            "Excludes reinforcement located on the compression side of the cracked "
            "neutral axis. Reinforcement on the tension side remains included "
            "regardless of whether it is physically labelled top or bottom."
        ),
    )
    result = _result_for_option(top_results, ignore_compression)
    if not result:
        st.warning(
            "The revision-matched authoritative SLS cracked-section result is not "
            "available yet. Refresh the current beam calculation before opening these checks."
        )
        return

    layers = tuple(
        layer for layer in tuple(result.get("layers", ()) or ())
        if isinstance(layer, Mapping) and float(layer.get("area_mm2", 0.0) or 0.0) > 0.0
    )
    n = float(result.get("modular_ratio", 0.0) or 0.0)
    dn = float(result.get("neutral_axis_depth_mm", 0.0) or 0.0)
    dn_top = float(result.get("neutral_axis_depth_from_top_mm", dn) or dn)
    icr = float(result.get("cracked_inertia_mm4", 0.0) or 0.0)
    kappa = float(result.get("curvature_per_mm", 0.0) or 0.0)
    residual = float(result.get("equilibrium_residual_mm3", 0.0) or 0.0)
    tolerance = float(result.get("solver_tolerance_mm3", 0.0) or 0.0)
    concrete_q = float(result.get("concrete_first_moment_mm3", 0.0) or 0.0)
    concrete_i = float(result.get("concrete_inertia_mm4", 0.0) or 0.0)
    steel_i = float(result.get("steel_inertia_mm4", 0.0) or 0.0)
    service_moment = float(result.get("service_moment_knm", 0.0) or 0.0)
    shape = str(result.get("section_shape", "RECT") or "RECT")
    compression_face = str(result.get("compression_face", "top") or "top")

    expected_n = float(Es) / float(Ec) if float(Ec) else 0.0
    if not math.isclose(n, expected_n, rel_tol=1e-10, abs_tol=1e-12):
        st.error("The published SLS modular ratio does not match the current elastic moduli.")
        return

    check1_details = rf"""
**Purpose**

Determine the modular ratio used to transform reinforcement into an equivalent
concrete area for cracked-section analysis.

**Inputs**

- $E_s = {float(Es):,.0f}\ \text{{MPa}}$
- $E_c = {float(Ec):,.0f}\ \text{{MPa}}$

**Calculation**

$$n=\frac{{E_s}}{{E_c}}$$

$$n=\frac{{{float(Es):,.0f}}}{{{float(Ec):,.0f}}}={n:.4f}$$

The modular ratio converts each reinforcement area into an equivalent concrete
area for elastic transformed-section analysis.

**Result**

$$\boxed{{n={n:.4f}}}$$

Check 2 uses this modular ratio to determine the cracked neutral-axis depth.
"""
    def check1_diagram() -> None:
        render_plotly_diagram(
            make_sls_canonical_section_figure(result),
            key=(
                "bending_sls_canonical_section_check1_ignore"
                if ignore_compression
                else "bending_sls_canonical_section_check1"
            ),
            title="SLS cracked section",
            config={"displayModeBar": False},
        )

    step_expander_calcbox(
        uid="bending_sls_3_1",
        summary_line=f"Check 1 — Modular ratio | Result: n = {n:.3f}",
        details_md=check1_details,
        status=None,
        diagram_fn=check1_diagram,
        content_before=lambda: _info_button(
            "Modular ratio",
            "The modular ratio is the elastic stiffness ratio $n=E_s/E_c$. "
            "Check 1 owns its calculation; later checks only reference the published value.",
        ),
    )

    layer_table = _layer_frame(layers)
    if shape == "RECT":
        concrete_formula = r"Q_c=\frac{b d_n^2}{2}"
        concrete_substitution = rf"Q_c=\frac{{{float(b):.3f}({dn:.6f})^2}}{{2}}={concrete_q:,.3f}\ \text{{mm}}^3"
    else:
        concrete_formula = r"Q_c(d_n)=\int_{A_c}(d_n-y)\,dA"
        concrete_substitution = rf"Q_c({dn:.6f})={concrete_q:,.3f}\ \text{{mm}}^3"
    check2_details = rf"""
**From Check 1**

$$n={n:.4f}$$

**Purpose**

Determine the cracked-section neutral-axis depth $d_n$, measured from the
current {compression_face} compression face, using elastic transformed-section equilibrium.

**Step 1 — Assume a trial neutral axis**

Start with a trial $d_n$.

**Step 2 — Ignore tensile concrete**

Concrete on the tension side is inactive. For this {shape} section:

$${concrete_formula}$$

$${concrete_substitution}$$

**Step 3 — Classify every physical reinforcement layer**

For every trial, $y_i<d_n$ is compression, $y_i>d_n$ is tension and
$y_i\approx d_n$ has approximately zero contribution. Physical names do not
set the engineering state.

**Step 4 — Transform reinforcement using Check 1**

$$Q_{{s,t,i}}=nA_{{s,i}}(y_i-d_n)$$

$$Q_{{s,c,i}}=(n-1)A_{{s,i}}(d_n-y_i)$$

The $(n-1)$ compression factor is used because the gross concrete compression
area already includes the concrete displaced by the reinforcement.

**Step 5 — Form the equilibrium residual**

$$R(d_n)=Q_c(d_n)+Q_{{s,c}}(d_n)-Q_{{s,t}}(d_n)$$

For the converged section, the numerical equilibrium is:

$${_equilibrium_assembly(result)}$$

$${_equilibrium_substitution(result)}$$

$$R({dn:.6f})={residual:.6g}\ \text{{mm}}^3$$

**Step 6 — Adjust $d_n$ and repeat**

The bracketed solver reclassifies all layers and repeats the transformed-area
calculation until $|R(d_n)|\leq {tolerance:.6g}\ \text{{mm}}^3$.

**Result**

$$\boxed{{d_n={dn:.3f}\ \text{{mm}}}}$$

Check 3 uses the converged cracked neutral axis to calculate $I_{{cr}}$.
"""

    def check2_table() -> None:
        st.markdown("##### Authoritative reinforcement layers and final states")
        st.table(layer_table)

    step_expander_calcbox(
        uid="bending_sls_3_2",
        summary_line=f"Check 2 — Cracked neutral-axis depth | Result: d_n = {dn:.1f} mm",
        details_md=check2_details,
        status=None,
        diagram_fn=None,
        content_before=lambda: _info_button(
            "Cracked neutral-axis depth",
            "SLS Check 2 uses elastic transformed areas. It does not use the ULS "
            "strain-compatible yielding and concrete stress-block procedure.",
        ),
        content_after=check2_table,
    )

    inertia_lines = []
    for layer in layers:
        inertia_lines.append(
            f"- {layer.get('label', layer.get('layer_id', 'Layer'))}: "
            f"{float(layer.get('inertia_contribution_mm4', 0.0) or 0.0):,.3f} mm^4"
        )
    check3_details = rf"""
**Purpose**

Calculate the cracked transformed second moment of area using the converged
neutral axis from Check 2.

**From Check 2**

$$d_n={dn:.3f}\ \text{{mm}}$$

**Calculation**

The concrete compression region contributes {concrete_i:,.3f} mm^4. The same
transformed-layer convention used by Check 2 contributes:

{chr(10).join(inertia_lines)}

$$I_{{cr}}=I_c+\sum I_{{s,i}}$$

$$I_{{cr}}={concrete_i:,.3f}+{steel_i:,.3f}={icr:,.3f}\ \text{{mm}}^4$$

**Result**

$$\boxed{{I_{{cr}}={icr:,.3f}\ \text{{mm}}^4}}$$
"""
    step_expander_calcbox(
        uid="bending_sls_3_3",
        summary_line=f"Check 3 — Cracked second moment of area I_cr | Result: I_cr = {icr:,.2f} mm^4",
        details_md=check3_details,
        status=None,
        content_before=lambda: _info_button(
            "Cracked second moment of area",
            "Check 3 uses the Check 2 neutral axis and the same transformed layer factors; it does not solve the neutral axis again.",
        ),
    )

    check4_details = rf"""
**Purpose**

Calculate service curvature from the cracked-section stiffness.

**From Check 3**

$$I_{{cr}}={icr:,.3f}\ \text{{mm}}^4$$

$$\kappa=\frac{{M_s}}{{E_c I_{{cr}}}}$$

$$\kappa=\frac{{{service_moment:.3f}\times10^6}}{{{float(Ec):,.0f}\times {icr:,.3f}}}
={kappa:.6e}\ \text{{mm}}^{{-1}}$$

**Result**

$$\boxed{{\kappa={kappa:.6e}\ \text{{mm}}^{{-1}}}}$$
"""
    step_expander_calcbox(
        uid="bending_sls_3_4",
        summary_line=f"Check 4 — Curvature | Result: kappa = {kappa:.3e} mm^-1",
        details_md=check4_details,
        status=None,
        content_before=lambda: _info_button(
            "Curvature",
            "Curvature is calculated only after the cracked neutral axis and cracked inertia have been established.",
        ),
    )

    strain_rows = [
        {
            "Location": f"Extreme {compression_face} compression fibre",
            "y from compression face (mm)": 0.0,
            "Strain": -kappa * dn,
        }
    ]
    for layer in layers:
        strain_rows.append(
            {
                "Location": str(layer.get("label", layer.get("layer_id", "Layer"))),
                "y from compression face (mm)": float(layer.get("depth_from_compression_mm", 0.0) or 0.0),
                "Strain": float(layer.get("strain", 0.0) or 0.0),
            }
        )
    strain_rows.append(
        {
            "Location": "Extreme tension fibre",
            "y from compression face (mm)": float(D),
            "Strain": kappa * (float(D) - dn),
        }
    )
    strain_frame = pd.DataFrame(strain_rows)
    check5_details = rf"""
**Purpose**

Use the Check 4 curvature to calculate the linear strain distribution.

**From Checks 2 and 4**

$$d_n={dn:.3f}\ \text{{mm}},\qquad \kappa={kappa:.6e}\ \text{{mm}}^{{-1}}$$

$$\varepsilon_i=\kappa(y_i-d_n)$$

Positive strain denotes tension and negative strain denotes compression in
this SLS teaching convention.
"""

    def check5_table() -> None:
        st.markdown("##### Strain distribution")
        st.table(strain_frame)

    step_expander_calcbox(
        uid="bending_sls_3_5",
        summary_line="Check 5 — Strain distribution | Result: layer strains calculated from curvature",
        details_md=check5_details,
        status=None,
        content_before=lambda: _info_button(
            "Strain distribution",
            "Plane sections remain plane, so the Check 4 curvature produces a linear strain profile through the cracked section.",
        ),
        content_after=check5_table,
    )

    stress_rows = []
    for layer in layers:
        stress_rows.append(
            {
                "Layer": str(layer.get("label", layer.get("layer_id", "Layer"))),
                "State": str(layer.get("state", "neutral")),
                "Strain": float(layer.get("strain", 0.0) or 0.0),
                "Steel stress f_s (MPa)": float(layer.get("stress_mpa", 0.0) or 0.0),
            }
        )
    concrete_strain = float(result.get("concrete_extreme_strain", 0.0) or 0.0)
    concrete_stress = float(result.get("concrete_extreme_stress_mpa", 0.0) or 0.0)
    stress_frame = pd.DataFrame(stress_rows)
    max_steel = max((abs(row["Steel stress f_s (MPa)"]) for row in stress_rows), default=0.0)
    check6_details = rf"""
**Purpose**

Convert the Check 5 strains into elastic concrete and reinforcement stresses.

**Concrete at the extreme compression fibre**

$$f_c=E_c\varepsilon_c={float(Ec):,.0f}({concrete_strain:.8f})={concrete_stress:.3f}\ \text{{MPa}}$$

**Each reinforcement layer**

$$f_{{s,i}}=E_s\varepsilon_{{s,i}}$$

No steel-yield cap or ULS rectangular stress-block factor is used in this
elastic cracked-section stress calculation.
"""

    def check6_table() -> None:
        st.markdown("##### Concrete and reinforcement stresses")
        st.table(stress_frame)

    step_expander_calcbox(
        uid="bending_sls_3_6",
        summary_line=f"Check 6 — Concrete and reinforcement stresses | Max |f_s| = {max_steel:.1f} MPa",
        details_md=check6_details,
        status=None,
        content_before=lambda: _info_button(
            "Concrete and reinforcement stresses",
            "Only Check 6 converts the established SLS strain distribution into elastic material stresses.",
        ),
        content_after=check6_table,
    )

    tension_layers = tuple(layer for layer in layers if layer.get("state") == "tension")
    outer = max(
        tension_layers,
        key=lambda layer: float(layer.get("depth_from_compression_mm", 0.0) or 0.0),
        default=None,
    )
    st.session_state["bending_sls_dn"] = dn_top
    st.session_state["bending_sls_kappa"] = kappa
    st.session_state["bending_sls_eps_top"] = (
        concrete_strain if compression_face == "top" else kappa * (0.0 - dn_top)
    )
    if outer is not None:
        y_top = float(outer.get("depth_from_top_mm", 0.0) or 0.0)
        strain = float(outer.get("strain", 0.0) or 0.0)
        stress = float(outer.get("stress_mpa", 0.0) or 0.0)
        st.session_state["bending_sls_y_tension_outer"] = y_top
        st.session_state["bending_sls_eps_s_outer"] = strain
        st.session_state["bending_sls_fs_outer"] = stress
        st.session_state["bending_sls_eps_bot"] = strain
        st.session_state["bending_sls_y_bot"] = y_top
        update_results(
            bending_sls_dn_mm=dn_top,
            bending_sls_y_tension_outer=y_top,
            bending_sls_eps_s_outer=strain,
            bending_sls_fs_outer=stress,
            sigma_s_sls=abs(stress),
        )


__all__ = ["render_authoritative_sls_checks"]
