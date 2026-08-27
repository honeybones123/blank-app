"""ULS bending presentation with the complete neutral-axis teaching flow in Check 2."""
from __future__ import annotations

import math
from collections.abc import Mapping
from typing import Any, Callable

import streamlit as st

from bending_core import _stress_strain_state
from bending_diagrams import (
    _make_uls_force_model_figure,
    _make_uls_stress_block_figure,
    _plot_strain_profile,
)
from engineering_page_sections import bending_uls_checks_view as base
from engineering_page_sections.bending_checks_context import BendingUlsChecksInput
from state_and_helpers import get_param
from widgets_helpers import calcbox, render_plotly_diagram


def _compression_depth(
    *,
    y_from_top_mm: float,
    overall_depth_mm: float,
    moment_sign: str,
) -> float:
    """Return layer depth measured from the active extreme compression face."""
    sign = str(moment_sign or "positive").strip().lower()
    if sign in {"negative", "hogging", "-", "neg"}:
        return float(overall_depth_mm) - float(y_from_top_mm)
    return float(y_from_top_mm)


def _authoritative_layers(
    view: BendingUlsChecksInput,
    r: Mapping[str, Any],
) -> tuple[dict[str, Any], ...]:
    """Return active physical layers with depth measured from the compression face."""
    rows = []
    for row in base._layers(r):
        item = dict(row)
        item["y_top"] = float(item["y"])
        item["y"] = _compression_depth(
            y_from_top_mm=float(item["y"]),
            overall_depth_mm=float(view.overall_depth_mm),
            moment_sign=str(view.moment_sign or "positive"),
        )
        rows.append(item)
    return tuple(rows)


def _strain_for_depth(y_mm: float, dn_mm: float) -> float:
    return -0.003 * (float(y_mm) - float(dn_mm)) / float(dn_mm) if abs(float(dn_mm)) > 1e-9 else float("nan")


def _state_from_depth(*, y_mm: float, dn_mm: float) -> str:
    if y_mm > dn_mm + 1e-9:
        return "tension"
    if y_mm < dn_mm - 1e-9:
        return "compression"
    return "approximately at the neutral axis"


def _step2_strain_md(rows: tuple[dict[str, Any], ...], dn: float) -> str:
    blocks = []
    for row in rows:
        y = float(row["y"])
        eps = _strain_for_depth(y, dn)
        state = _state_from_depth(y_mm=y, dn_mm=dn)
        relation = ">" if y > dn + 1e-9 else "<" if y < dn - 1e-9 else r"\approx"
        blocks.append(
            rf"""**{row['label']}**

$$y_{{{row['i']}}}={y:.3f}\ \text{{mm}}\ {relation}\ d_n={dn:.3f}\ \text{{mm}}
\quad\Rightarrow\quad
\text{{{state}}}$$

$$
\varepsilon_{{s,{row['i']}}}
=
-0.003
\left(
\frac{{{y:.3f}-{dn:.3f}}}{{{dn:.3f}}}
\right)
=
{eps:.6f}
$$

$$\boxed{{\varepsilon_{{s,{row['i']}}}={eps:.6f}}}$$"""
        )
    return "\n\n".join(blocks) or "No active reinforcement layers were published."


def _step3_stress_md(
    rows: tuple[dict[str, Any], ...],
    dn: float,
    Es: float,
    fsy: float,
) -> str:
    blocks = []
    for row in rows:
        eps = _strain_for_depth(float(row["y"]), dn)
        trial = Es * eps if math.isfinite(eps) else float("nan")
        yielded = math.isfinite(trial) and abs(trial) > fsy + 1e-9
        state = "Yielded" if yielded else "Elastic"
        role = "tension" if float(row["fs"]) < -1e-9 else "compression" if float(row["fs"]) > 1e-9 else "approximately zero stress"
        conclusion = (
            rf"""Since

$$|{trial:.1f}|>{fsy:.1f}\ \text{{MPa}}$$

the layer has yielded and its stress is limited to the yield strength:

$$\boxed{{f_{{s,{row['i']}}}={float(row['fs']):.1f}\ \text{{MPa}}}}$$"""
            if yielded
            else
            rf"""Since

$$|{trial:.1f}|\leq {fsy:.1f}\ \text{{MPa}}$$

the layer remains elastic:

$$\boxed{{f_{{s,{row['i']}}}={float(row['fs']):.1f}\ \text{{MPa}}}}$$"""
        )
        blocks.append(
            rf"""**{row['label']}**

$$
f_{{s,\mathrm{{elastic}},{row['i']}}}
=
E_s\varepsilon_{{s,{row['i']}}}
=
({Es:.0f})({eps:.6f})
=
{trial:.1f}\ \text{{MPa}}
$$

{conclusion}

**State:** {state} {role}."""
        )
    return "\n\n".join(blocks) or "No active reinforcement layers were published."


def _step4_force_md(
    rows: tuple[dict[str, Any], ...],
    tension_kn: float,
    compression_steel_kn: float,
) -> str:
    blocks = []
    for row in rows:
        force_kn = float(row["F"]) / 1000.0
        role = "tension" if float(row["fs"]) < -1e-9 else "compression" if float(row["fs"]) > 1e-9 else "approximately zero stress"
        blocks.append(
            rf"""**{row['label']} — {role}**

$$
F_{{s,{row['i']}}}
=
A_{{s,{row['i']}}}f_{{s,{row['i']}}}
=
({float(row['A']):.2f})({float(row['fs']):.1f})
=
{force_kn:.3f}\ \text{{kN}}
$$"""
        )
    layer_text = "\n\n".join(blocks) or "No active reinforcement layers were published."
    return rf"""$$F_{{s,i}}=A_{{s,i}}f_{{s,i}}$$

**For this beam**

{layer_text}

The tensile-force magnitude is:

$$
\boxed{{\sum T={tension_kn:.3f}\ \text{{kN}}}}
$$

The compression-steel resultant is:

$$
\boxed{{\sum C_s={compression_steel_kn:.3f}\ \text{{kN}}}}
$$"""


def _step5_concrete_md(
    *,
    shape: str,
    b: float,
    alpha2: float,
    fc: float,
    gamma: float,
    dn: float,
    a: float,
    concrete_kn: float,
    r: Mapping[str, Any],
) -> str:
    if shape == "RECT":
        area = b * a
        area_line = rf"""
$$
A_c=ba=({b:.1f})({a:.3f})={area:.3f}\ \text{{mm}}^2
$$
"""
    else:
        area = float(r.get("compression_concrete_area_mm2", 0.0) or 0.0)
        area_line = rf"""
For this {shape} section, the authoritative compression-block area is:

$$
\boxed{{A_c={area:.3f}\ \text{{mm}}^2}}
$$
"""
    return rf"""The same neutral-axis depth defines the equivalent rectangular stress-block depth:

$$
\boxed{{a=\gamma d_n}}
$$

**For this beam**

$$
a=({gamma:.3f})({dn:.3f})={a:.3f}\ \text{{mm}}
$$

$$
\boxed{{a={a:.3f}\ \text{{mm}}}}
$$

{area_line}

The concrete compression resultant is:

$$
\boxed{{C_c=\alpha_2 f'_c A_c}}
$$

$$
C_c
=
({alpha2:.3f})({fc:.1f})({area:.3f})/1000
=
{concrete_kn:.3f}\ \text{{kN}}
$$

$$
\boxed{{C_c={concrete_kn:.3f}\ \text{{kN}}}}
$$"""


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
    view: BendingUlsChecksInput,
    r: Mapping[str, Any],
) -> tuple[str, str, tuple[str, ...], Callable[[], None]]:
    """Build the six-step neutral-axis teaching flow from authoritative publications."""
    b = float(view.width_mm)
    D = float(view.overall_depth_mm)
    fc = float(view.concrete_strength_mpa)
    fsy = float(view.steel_yield_strength_mpa)
    moment_sign = str(view.moment_sign or "positive")
    alpha2 = float(r.get("alpha2", 0.0) or 0.0)
    gamma = float(r.get("gamma", 0.0) or 0.0)
    dn = float(r.get("c", 0.0) or 0.0)
    a = float(r.get("a", 0.0) or 0.0)
    d = float(r.get("d", view.effective_depth_mm) or view.effective_depth_mm)
    concrete_kn = float(r.get("C_concrete_N", 0.0) or 0.0) / 1000.0
    compression_steel_kn = float(r.get("C_steel_N", 0.0) or 0.0) / 1000.0
    tension_kn = float(r.get("T_N", 0.0) or 0.0) / 1000.0
    residual_kn = float(r.get("equilibrium_residual_n", 0.0) or 0.0) / 1000.0
    total_compression_kn = concrete_kn + compression_steel_kn
    Es = float(get_param("Es") or 200000.0)
    shape = str(r.get("section_shape", "RECT") or "RECT").upper()
    rows = _authoritative_layers(view, r)
    trace = tuple(r.get("neutral_axis_iteration_trace", ()) or ())
    initial_dn = (
        float(trace[0].get("dn_mm", dn) or dn)
        if trace and isinstance(trace[0], Mapping)
        else dn
    )
    direct = (
        len(rows) == 1
        and shape == "RECT"
        and abs(abs(float(rows[0]["fs"])) - fsy) <= max(0.5, 0.002 * max(fsy, 1.0))
    )
    method = "Direct single-layer solution" if direct else "General multi-layer equilibrium solution"

    purpose = rf"""**Purpose**

Determine the neutral-axis depth $d_n$ that satisfies strain compatibility and internal force equilibrium:

$$
\boxed{{\sum C=\sum T}}
$$

For multiple reinforcement layers, the steel strain and stress depend on $d_n$, so the neutral axis is generally found by iteration:

$$
\boxed{{
d_n
\rightarrow
\varepsilon_{{s,i}}
\rightarrow
f_{{s,i}}
\rightarrow
F_{{s,i}}
\rightarrow
C_c
\rightarrow
R(d_n)
}}
$$

where

$$
R(d_n)=\sum C-\sum T
$$

If $R(d_n)\neq0$, the trial neutral-axis depth is updated and the process repeats.

**The numerical calculations below show the final converged iteration for this beam.**"""

    if direct:
        step1 = rf"""**Step 1 — Establish the neutral-axis depth**

With one active yielded tension layer, the neutral axis can be obtained directly from equilibrium rather than by iteration.

$$
d_n
=
\frac{{A_{{st}}f_{{sy}}}}{{\alpha_2f'_cb\gamma}}
$$

**For this beam**

$$
\boxed{{d_n={dn:.3f}\ \text{{mm}}}}
$$

Steps 2–6 verify the compatible strain, stress, forces and equilibrium at this depth."""
    else:
        step1 = rf"""**Step 1 — Choose a trial neutral-axis depth**

Start with a trial neutral-axis depth measured from the extreme compression face:

$$
d_n=d_{{n,\mathrm{{trial}}}}
$$

The solver began this search at:

$$
d_n^{{(0)}}={initial_dn:.3f}\ \text{{mm}}
$$

Changing $d_n$ changes the reinforcement strain, steel stress, reinforcement forces and concrete compression force.

After repeating Steps 2–6, the final converged trial for this beam is:

$$
\boxed{{d_n={dn:.3f}\ \text{{mm}}}}
$$

The following steps verify that this value satisfies equilibrium."""

    step2 = rf"""**Step 2 — Reinforcement strain**

Assuming plane sections remain plane, the strain in reinforcement layer $i$ is:

$$
\boxed{{
\varepsilon_{{s,i}}
=
-\varepsilon_{{cu}}
\frac{{y_i-d_n}}{{d_n}}
}}
$$

with:

$$
\varepsilon_{{cu}}=0.003
$$

A layer is on the tension side when $y_i>d_n$, and on the compression side when $y_i<d_n$.

**For this beam**

{_step2_strain_md(rows, dn)}"""

    step3 = rf"""**Step 3 — Reinforcement stress**

First calculate the elastic trial stress:

$$
\boxed{{
f_{{s,\mathrm{{elastic}},i}}
=
E_s\varepsilon_{{s,i}}
}}
$$

Then compare its magnitude with the yield strength $f_{{sy}}={fsy:.1f}\ \text{{MPa}}$.

If $|E_s\varepsilon_{{s,i}}|\leq f_{{sy}}$, the layer remains elastic.  
If $|E_s\varepsilon_{{s,i}}|>f_{{sy}}$, the layer has yielded and $|f_{{s,i}}|=f_{{sy}}$.

**For this beam**

{_step3_stress_md(rows, dn, Es, fsy)}"""

    step4 = rf"""**Step 4 — Reinforcement forces**

Convert the stress in each reinforcement layer into an internal force:

{_step4_force_md(rows, tension_kn, compression_steel_kn)}"""

    step5 = rf"""**Step 5 — Concrete compression**

{_step5_concrete_md(
        shape=shape,
        b=b,
        alpha2=alpha2,
        fc=fc,
        gamma=gamma,
        dn=dn,
        a=a,
        concrete_kn=concrete_kn,
        r=r,
    )}"""

    step6 = rf"""**Step 6 — Check equilibrium**

Now compare total compression with total tension:

$$
\boxed{{
R(d_n)=\sum C-\sum T
}}
$$

**For this beam**

$$
\sum C=C_c+C_s={concrete_kn:.3f}+{compression_steel_kn:.3f}
=
{total_compression_kn:.3f}\ \text{{kN}}
$$

$$
\sum T={tension_kn:.3f}\ \text{{kN}}
$$

$$
R({dn:.3f})
=
{total_compression_kn:.3f}
-
{tension_kn:.3f}
=
{residual_kn:.6f}\ \text{{kN}}
$$

$$
\boxed{{R(d_n)\approx0}}
$$

Therefore the trial neutral axis is accepted:

$$
\boxed{{d_n={dn:.3f}\ \text{{mm}}}}
$$

$$
\boxed{{a={a:.3f}\ \text{{mm}}}}
$$

and the final force balance is:

$$
\boxed{{
{total_compression_kn:.3f}\ \text{{kN compression}}
=
{tension_kn:.3f}\ \text{{kN tension}}
}}
$$"""

    def trial_diagram() -> None:
        trial_dn = max(1.0, min(initial_dn, D - 1.0))
        trial_a = gamma * trial_dn
        fig = _make_uls_stress_block_figure(
            b_mm=b,
            D_mm=D,
            d_mm=d,
            dn_mm=trial_dn,
            a_mm=trial_a,
            alpha2=alpha2,
            gamma=gamma,
            fc=fc,
            fsy=fsy,
            show_lever_arm=False,
            show_dn=True,
            show_alpha_label=True,
            show_C=False,
            C_N=None,
            variant="13",
            moment_sign=moment_sign,
        )
        fig.update_layout(height=250, margin=dict(l=0, r=10, t=35, b=10))
        render_plotly_diagram(
            fig,
            key=f"bending_uls_check2_step1_trial_{moment_sign}",
            title="Trial neutral axis",
            config={"displayModeBar": False},
        )

    def strain_diagram() -> None:
        state = _stress_strain_state("ULS", moment_sign=moment_sign)
        fig = _plot_strain_profile(
            state,
            state_label="ULS",
            layout=None,
            moment_sign=moment_sign,
        )
        fig.update_layout(height=300, margin=dict(l=0, r=10, t=35, b=10))
        render_plotly_diagram(
            fig,
            key=f"bending_uls_check2_step2_strain_{moment_sign}",
            title="Reinforcement strain compatibility",
            config={"displayModeBar": False},
        )

    def force_diagram() -> None:
        fig = _make_uls_force_model_figure(
            D_mm=D,
            d_mm=d,
            a_mm=a,
            C_N=float(r.get("C_concrete_N", 0.0) or 0.0),
            T_N=float(r.get("T_N", 0.0) or 0.0),
            moment_sign=moment_sign,
            dn_mm=dn,
        )
        fig.update_layout(height=320, margin=dict(l=0, r=10, t=35, b=10))
        render_plotly_diagram(
            fig,
            key=f"bending_uls_check2_step4_force_{moment_sign}",
            title="Internal reinforcement and concrete resultants",
            config={"displayModeBar": False},
        )

    def concrete_diagram() -> None:
        fig = _make_uls_stress_block_figure(
            b_mm=b,
            D_mm=D,
            d_mm=d,
            dn_mm=dn,
            a_mm=a,
            alpha2=alpha2,
            gamma=gamma,
            fc=fc,
            fsy=fsy,
            show_lever_arm=False,
            show_dn=True,
            show_alpha_label=True,
            show_C=False,
            C_N=None,
            variant="13",
            moment_sign=moment_sign,
        )
        fig.update_layout(height=300, margin=dict(l=0, r=10, t=35, b=10))
        render_plotly_diagram(
            fig,
            key=f"bending_uls_check2_step5_concrete_{moment_sign}",
            title="Concrete compression block",
            config={"displayModeBar": False},
        )

    def render_steps() -> None:
        st.markdown("#### Neutral-axis calculation")
        _step_row(
            step_md=step1,
            uid="bending_uls_check2_step_1",
            diagram_fn=trial_diagram,
        )
        _step_row(
            step_md=step2,
            uid="bending_uls_check2_step_2",
            diagram_fn=strain_diagram,
        )
        _step_row(
            step_md=step3,
            uid="bending_uls_check2_step_3",
        )
        _step_row(
            step_md=step4,
            uid="bending_uls_check2_step_4",
            diagram_fn=force_diagram,
        )
        _step_row(
            step_md=step5,
            uid="bending_uls_check2_step_5",
            diagram_fn=concrete_diagram,
        )

        calc_col, _diagram_col = st.columns([2.0, 1.0], gap="large")
        with calc_col:
            calcbox(step6, uid="bending_uls_check2_step_6")
            trace_table = base._iteration_table(
                r,
                dn,
                concrete_kn,
                tension_kn,
                compression_steel_kn,
                residual_kn,
            )
            with st.expander("Show solver iterations", expanded=False):
                st.markdown(
                    "Representative trial values from the authoritative neutral-axis solver:"
                )
                st.markdown(trace_table)

    return method, purpose, (step1, step2, step3, step4, step5, step6), render_steps


def render_bending_uls_checks(view: BendingUlsChecksInput) -> None:
    """Render ULS checks with the complete neutral-axis solution consolidated into Check 2."""
    from engineering_page_sections import bending_uls_checks as legacy

    r = view.mutable_results()
    if not r.get("_authoritative_uls"):
        legacy.render_authoritative_uls_checks(
            r,
            view.width_mm,
            view.overall_depth_mm,
            view.concrete_strength_mpa,
            view.steel_yield_strength_mpa,
            view.reinforcement_area_mm2,
            view.effective_depth_mm,
            summary_mode=False,
            Mu_star_override=view.demand_kNm,
            moment_sign=view.moment_sign,
        )
        return

    base._install_dispatch(legacy)
    method, purpose, _steps, render_steps = _check2_payload(view, r)
    deferred: dict[str, Any] | None = None

    def intercept(original: Callable[..., Any], *args: Any, **kwargs: Any):
        nonlocal deferred
        uid = str(kwargs.get("uid", args[0] if args else ""))

        if uid == "bending_uls_authoritative_strains":
            deferred = dict(kwargs)
            return None

        # The old standalone equilibrium and internal-force cards are now
        # entirely explained inside Check 2.
        if uid in {
            "bending_uls_authoritative_equilibrium",
            "bending_uls_authoritative_4",
        }:
            return None

        revised = dict(kwargs)
        if uid == "bending_uls_authoritative_method":
            revised["summary_line"] = (
                f"Check 2 — Neutral-axis solution method | {method}"
            )
            revised["details_md"] = purpose
            revised["diagram_fn"] = None
            revised["content_after"] = render_steps
            revised["progressive_steps"] = None

            result = original(*args, **revised)

            if deferred:
                k = dict(deferred)
                deferred = None
                k["summary_line"] = str(k.get("summary_line", "")).replace(
                    "Check 4", "Check 3"
                )
                k["details_md"] = str(k.get("details_md", "")).replace(
                    "from Check 3", "from Check 2"
                )
                k["content_before"] = base._info(
                    legacy,
                    "Reinforcement strains and stresses",
                    "Check 3 — Reinforcement strains and stresses",
                    "Using the neutral-axis depth solved in Check 2, this check reports the final compatible strain and authoritative steel stress for each active reinforcement layer.",
                )
                st.session_state["_rendering_deferred_bending_uls_check_2"] = True
                try:
                    original(**k)
                finally:
                    st.session_state.pop(
                        "_rendering_deferred_bending_uls_check_2", None
                    )
            return result

        # Standalone internal-force Check 4 has been absorbed into Check 2,
        # so keep the remaining user-facing check numbers contiguous.
        if uid == "bending_uls_authoritative_6":
            revised["summary_line"] = str(
                revised.get("summary_line", "")
            ).replace("Check 6", "Check 4")
        elif uid == "bending_uls_authoritative_7":
            revised["summary_line"] = str(
                revised.get("summary_line", "")
            ).replace("Check 7", "Check 5")
            revised["details_md"] = str(
                revised.get("details_md", "")
            ).replace("from Check 5", "from Check 4")
        elif uid == "bending_uls_authoritative_8":
            revised["summary_line"] = str(
                revised.get("summary_line", "")
            ).replace("Check 8", "Check 6")

        return original(*args, **revised)

    token = base._ACTIVE.set(intercept)
    try:
        legacy.render_authoritative_uls_checks(
            r,
            view.width_mm,
            view.overall_depth_mm,
            view.concrete_strength_mpa,
            view.steel_yield_strength_mpa,
            view.reinforcement_area_mm2,
            view.effective_depth_mm,
            summary_mode=False,
            Mu_star_override=view.demand_kNm,
            moment_sign=view.moment_sign,
        )
    finally:
        base._ACTIVE.reset(token)


__all__ = ["render_bending_uls_checks"]
