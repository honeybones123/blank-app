"""ULS bending presentation with Check 4 force resultants embedded into Check 2."""
from __future__ import annotations

from typing import Any, Callable

import streamlit as st

from bending_diagrams import _make_uls_force_model_figure
from engineering_page_sections.bending_checks_context import BendingUlsChecksInput
from engineering_page_sections import bending_uls_checks_view as base
from widgets_helpers import calcbox, render_plotly_diagram


def _force_resultants_payload(view: BendingUlsChecksInput, r: dict[str, Any]) -> tuple[str, Callable[[], None]]:
    alpha2 = float(r.get("alpha2", 0.0) or 0.0)
    fc = float(view.concrete_strength_mpa)
    b = float(view.width_mm)
    a = float(r.get("a", 0.0) or 0.0)
    dn = float(r.get("c", 0.0) or 0.0)
    d = float(r.get("d", view.effective_depth_mm) or view.effective_depth_mm)
    cc = float(r.get("C_concrete_N", 0.0) or 0.0) / 1000.0
    cs = float(r.get("C_steel_N", 0.0) or 0.0) / 1000.0
    tension = float(r.get("T_N", 0.0) or 0.0) / 1000.0
    residual = float(r.get("equilibrium_residual_n", 0.0) or 0.0) / 1000.0
    shape = str(r.get("section_shape", "RECT") or "RECT").upper()
    rows = base._layers(r)

    if shape == "RECT":
        concrete_md = rf"""
$$A_c=ba=({b:.1f})({a:.3f})={b*a:.3f}\ \text{{mm}}^2$$

$$C_c=\alpha_2f'_cA_c=({alpha2:.3f})({fc:.1f})({b*a:.3f})/1000={cc:.3f}\ \text{{kN}}$$
"""
    else:
        area = float(r.get("compression_concrete_area_mm2", 0.0) or 0.0)
        concrete_md = rf"""
$$C_c=\alpha_2f'_cA_c$$

$$C_c=({alpha2:.3f})({fc:.1f})({area:.3f})/1000={cc:.3f}\ \text{{kN}}$$
"""

    layer_md = base._layer_forces(rows)
    total_compression = cc + cs
    md = rf"""**Step 4 — Internal force resultants**

Use the final compatible reinforcement stresses and the concrete compression block to form the internal ULS force resultants.

**Concrete compression**

{concrete_md}

**Reinforcement resultants**

$$F_{{s,i}}=A_{{s,i}}f_{{s,i}}$$

**For this beam**

{layer_md}

$$\boxed{{\sum T={tension:.3f}\ \text{{kN}}}}$$

$$\boxed{{\sum C_s={cs:.3f}\ \text{{kN}}}}$$

$$\boxed{{\sum C=C_c+C_s={cc:.3f}+{cs:.3f}={total_compression:.3f}\ \text{{kN}}}}$$

**Equilibrium confirmation**

$$R(d_n)=\sum C-\sum T={total_compression:.3f}-{tension:.3f}={residual:.6f}\ \text{{kN}}\approx0$$

$$\boxed{{d_n={dn:.3f}\ \text{{mm}}}},\qquad\boxed{{a={a:.3f}\ \text{{mm}}}}$$
"""

    def diagram() -> None:
        fig = _make_uls_force_model_figure(
            D_mm=float(view.overall_depth_mm),
            d_mm=d,
            a_mm=a,
            C_N=float(r.get("C_concrete_N", 0.0) or 0.0),
            T_N=float(r.get("T_N", 0.0) or 0.0),
            moment_sign=str(view.moment_sign or "positive"),
            dn_mm=dn,
        )
        render_plotly_diagram(
            fig,
            key=f"bending_uls_check2_internal_force_{view.moment_sign}",
            title="Internal force resultants",
            config={"displayModeBar": False},
        )

    return md, diagram


def render_bending_uls_checks(view: BendingUlsChecksInput) -> None:
    """Render ULS checks with neutral-axis solving and force resultants consolidated in Check 2."""
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
    method, purpose, steps, _convergence, final_diagram = base._check2_payload(view, r)
    force_md, force_diagram = _force_resultants_payload(view, r)
    deferred: dict[str, Any] | None = None

    def intercept(original: Callable[..., Any], *args: Any, **kwargs: Any):
        nonlocal deferred
        uid = str(kwargs.get("uid", args[0] if args else ""))

        if uid == "bending_uls_authoritative_strains":
            deferred = dict(kwargs)
            return None
        if uid in {"bending_uls_authoritative_equilibrium", "bending_uls_authoritative_4"}:
            return None

        revised = dict(kwargs)
        if uid == "bending_uls_authoritative_method":
            revised["summary_line"] = f"Check 2 — Neutral-axis solution method | {method}"
            old_before = revised.get("content_before")
            old_diagram = revised.get("diagram_fn")

            def left_column_content() -> None:
                if old_before:
                    old_before()
                calcbox(purpose, uid="bending_uls_check2_purpose")
                st.markdown("#### Neutral-axis calculation")
                for i, md in enumerate(tuple(steps)[:3], 1):
                    calcbox(md, uid=f"bending_uls_check2_step_{i}")
                calcbox(force_md, uid="bending_uls_check2_internal_force")

            def right_column_diagrams() -> None:
                if old_diagram:
                    old_diagram()
                final_diagram()
                force_diagram()

            revised["details_md"] = ""
            revised["content_before"] = left_column_content
            revised["diagram_fn"] = right_column_diagrams
            revised["content_after"] = None
            revised["progressive_steps"] = None

            result = original(*args, **revised)
            if deferred:
                k = dict(deferred)
                deferred = None
                k["summary_line"] = str(k.get("summary_line", "")).replace("Check 4", "Check 3")
                k["details_md"] = str(k.get("details_md", "")).replace("from Check 3", "from Check 2")
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
                    st.session_state.pop("_rendering_deferred_bending_uls_check_2", None)
            return result

        # Standalone internal-force Check 4 has been absorbed into Check 2,
        # so keep the remaining user-facing check numbers contiguous.
        if uid == "bending_uls_authoritative_6":
            revised["summary_line"] = str(revised.get("summary_line", "")).replace("Check 6", "Check 4")
        elif uid == "bending_uls_authoritative_7":
            revised["summary_line"] = str(revised.get("summary_line", "")).replace("Check 7", "Check 5")
            revised["details_md"] = str(revised.get("details_md", "")).replace("from Check 5", "from Check 4")
        elif uid == "bending_uls_authoritative_8":
            revised["summary_line"] = str(revised.get("summary_line", "")).replace("Check 8", "Check 6")

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
