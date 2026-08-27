"""ULS Bending-check presentation boundary."""
from __future__ import annotations

import math
from collections.abc import Mapping
from contextvars import ContextVar
from typing import Any, Callable

import streamlit as st

from bending_diagrams import _make_uls_stress_block_figure
from engineering_page_sections.bending_checks_context import BendingUlsChecksInput
from state_and_helpers import get_param
from widgets_helpers import calcbox, render_plotly_diagram

_ACTIVE: ContextVar[Callable[..., Any] | None] = ContextVar("uls_check2_adapter", default=None)


def _layers(r: Mapping[str, Any]) -> tuple[dict[str, Any], ...]:
    areas = tuple(float(v) for v in r.get("steel_layer_areas_mm2", ()) or ())
    depths = tuple(float(v) for v in r.get("steel_layer_depths_mm", ()) or ())
    stresses = tuple(float(v) for v in r.get("steel_layer_stresses_mpa", ()) or ())
    forces = tuple(float(v) for v in r.get("steel_layer_forces_n", ()) or ())
    labels = tuple(str(v) for v in r.get("steel_layer_labels", ()) or ())
    n = min(len(areas), len(depths), len(stresses), len(forces))
    return tuple(
        {
            "i": i + 1,
            "A": areas[i],
            "y": depths[i],
            "fs": stresses[i],
            "F": forces[i],
            "label": labels[i] if i < len(labels) and labels[i] else f"Layer {i + 1}",
        }
        for i in range(n)
        if areas[i] > 1e-9
    )


def _eps(y: float, dn: float) -> float:
    return -0.003 * (y - dn) / dn if abs(dn) > 1e-9 else float("nan")


def _role(fs: float) -> str:
    return "tension" if fs < -1e-9 else "compression" if fs > 1e-9 else "neutral"


def _layer_strains(rows: tuple[dict[str, Any], ...], dn: float) -> str:
    return "\n\n".join(
        rf"""**{x['label']}**

$$\varepsilon_{{s,{x['i']}}}=-0.003\frac{{{x['y']:.3f}-{dn:.3f}}}{{{dn:.3f}}}={_eps(x['y'], dn):.6f}$$"""
        for x in rows
    ) or "No active reinforcement layers were published."


def _layer_stresses(rows: tuple[dict[str, Any], ...], dn: float, Es: float, fsy: float) -> str:
    out = []
    for x in rows:
        e = _eps(x["y"], dn)
        trial = Es * e if math.isfinite(e) else float("nan")
        state = "Yielded" if math.isfinite(trial) and abs(trial) > fsy + 1e-9 else "Elastic"
        out.append(
            rf"""**{x['label']}**

$$f_{{s,elastic,{x['i']}}}=({Es:.0f})({e:.6f})={trial:.1f}\ \text{{MPa}}$$

$$f_{{s,{x['i']}}}=\operatorname{{clip}}({trial:.1f},-{fsy:.1f},{fsy:.1f})={x['fs']:.1f}\ \text{{MPa}}$$

**State:** {state} {_role(x['fs'])}."""
        )
    return "\n\n".join(out) or "No active reinforcement layers were published."


def _layer_forces(rows: tuple[dict[str, Any], ...]) -> str:
    return "\n\n".join(
        rf"""**{x['label']} — {_role(x['fs'])}**

$$F_{{s,{x['i']}}}=A_{{s,{x['i']}}}f_{{s,{x['i']}}}=({x['A']:.2f})({x['fs']:.1f})={x['F']/1000.0:.3f}\ \text{{kN}}$$"""
        for x in rows
    ) or "No active reinforcement layers were published."


def _iteration_table(
    r: Mapping[str, Any], dn: float, cc: float, t: float, cs: float, residual: float
) -> str:
    trace = tuple(r.get("neutral_axis_iteration_trace", ()) or ())
    lines = [
        "| Solver step | $d_n$ (mm) | $C_c$ (kN) | $T$ (kN) | $C_s$ (kN) | Residual (kN) |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    seen: list[int] = []
    for idx in (0, 1, len(trace) // 2, len(trace) - 1):
        if 0 <= idx < len(trace) and idx not in seen:
            seen.append(idx)
    for pos, idx in enumerate(seen):
        x = trace[idx]
        if not isinstance(x, Mapping):
            continue
        lines.append(
            f"| {'Initial' if pos == 0 else 'Intermediate'} | {float(x.get('dn_mm', 0) or 0):.3f} | "
            f"{float(x.get('concrete_force_n', 0) or 0) / 1000:.3f} | "
            f"{float(x.get('tension_force_n', 0) or 0) / 1000:.3f} | "
            f"{float(x.get('compression_steel_force_n', 0) or 0) / 1000:.3f} | "
            f"{float(x.get('equilibrium_residual_n', 0) or 0) / 1000:.6f} |"
        )
    lines.append(
        f"| **Converged** | **{dn:.3f}** | **{cc:.3f}** | **{t:.3f}** | "
        f"**{cs:.3f}** | **{residual:.6f}** |"
    )
    return "\n".join(lines)


def _check2_payload(
    view: BendingUlsChecksInput,
    r: Mapping[str, Any],
) -> tuple[str, str, tuple[str, ...], str, Callable[[], None]]:
    b, D = float(view.width_mm), float(view.overall_depth_mm)
    fc, fsy = float(view.concrete_strength_mpa), float(view.steel_yield_strength_mpa)
    alpha2, gamma = float(r.get("alpha2", 0) or 0), float(r.get("gamma", 0) or 0)
    dn, a = float(r.get("c", 0) or 0), float(r.get("a", 0) or 0)
    d = float(r.get("d", view.effective_depth_mm) or view.effective_depth_mm)
    cc, cs, t = (
        float(r.get(k, 0) or 0) / 1000
        for k in ("C_concrete_N", "C_steel_N", "T_N")
    )
    residual = float(r.get("equilibrium_residual_n", 0) or 0) / 1000
    Es = float(get_param("Es") or 200000.0)
    shape = str(r.get("section_shape", "RECT") or "RECT").upper()
    rows = _layers(r)
    direct = (
        len(rows) == 1
        and shape == "RECT"
        and abs(abs(rows[0]["fs"]) - fsy) <= max(0.5, 0.002 * max(fsy, 1.0))
    )

    purpose = r"""**Purpose**

Determine the neutral-axis depth from strain compatibility and internal force equilibrium.

$$\boxed{\sum C=\sum T}$$

The trial diagrams illustrate the method. The calculation boxes below show every equation with the current beam values substituted immediately underneath it."""

    if direct:
        x = rows[0]
        steps = (
            rf"""**Step 1 — Concrete compression and steel tension**

$$C_c=\alpha_2f'_cb\gamma d_n$$

**For this beam**

$$C_c=({alpha2:.3f})({fc:.1f})({b:.1f})({gamma:.3f})d_n={alpha2 * fc * b * gamma / 1000:.3f}d_n\ \text{{kN}}$$

$$T=A_{{st}}f_{{sy}}=({x['A']:.2f})({fsy:.1f})={x['A'] * fsy / 1000:.3f}\ \text{{kN}}$$

$$\boxed{{T={t:.3f}\ \text{{kN}}}}$$""",
            rf"""**Step 2 — Apply force equilibrium**

$$C_c=T$$

**For this beam**

$$({alpha2 * fc * b * gamma / 1000:.6f})d_n={t:.6f}$$""",
            rf"""**Step 3 — Solve and accept the neutral axis**

$$d_n=\frac{{A_{{st}}f_{{sy}}}}{{\alpha_2f'_cb\gamma}}$$

**For this beam**

$$d_n=\frac{{({x['A']:.2f})({fsy:.1f})}}{{({alpha2:.3f})({fc:.1f})({b:.1f})({gamma:.3f})}}={dn:.3f}\ \text{{mm}}$$

$$a=\gamma d_n=({gamma:.3f})({dn:.3f})={a:.3f}\ \text{{mm}}$$

$$\boxed{{d_n={dn:.3f}\ \text{{mm}}}},\qquad\boxed{{a={a:.3f}\ \text{{mm}}}}$$

$$R(d_n)={residual:.6f}\ \text{{kN}}\approx0$$""",
        )
        method = "Direct single-layer solution"
    else:
        if shape == "RECT":
            cc_formula = r"C_c=\alpha_2f'_cb\gamma d_n"
            cc_sub = (
                rf"C_c=({alpha2:.3f})({fc:.1f})({b:.1f})({gamma:.3f})"
                rf"({dn:.3f})={cc:.3f}\ \text{{kN}}"
            )
        else:
            Ac = float(r.get("compression_concrete_area_mm2", 0) or 0)
            cc_formula = r"C_c=\alpha_2f'_cA_c"
            cc_sub = rf"C_c=({alpha2:.3f})({fc:.1f})({Ac:.2f})/1000={cc:.3f}\ \text{{kN}}"
        steps = (
            rf"""**Step 1 — Concrete compression**

$${cc_formula}$$

**For this beam**

$${cc_sub}$$

$$\boxed{{C_c={cc:.3f}\ \text{{kN}}}}$$""",
            rf"""**Step 2 — Reinforcement strain**

$$\varepsilon_{{s,i}}=-\varepsilon_{{cu}}\frac{{y_i-d_n}}{{d_n}},\qquad\varepsilon_{{cu}}=0.003$$

**For this beam**

{_layer_strains(rows, dn)}""",
            rf"""**Step 3 — Reinforcement stress**

$$f_{{s,i}}=\operatorname{{sign}}(\varepsilon_{{s,i}})\min(E_s|\varepsilon_{{s,i}}|,f_{{sy}})$$

**For this beam**

{_layer_stresses(rows, dn, Es, fsy)}""",
            rf"""**Step 4 — Reinforcement force**

$$F_{{s,i}}=A_{{s,i}}f_{{s,i}}$$

**For this beam**

{_layer_forces(rows)}

$$\boxed{{\sum T={t:.3f}\ \text{{kN}}}},\qquad\boxed{{\sum C_s={cs:.3f}\ \text{{kN}}}}$$""",
            rf"""**Step 5 — Equilibrium residual**

$$R(d_n)=\sum C-\sum T=C_c+C_s-T$$

**For this beam**

$$R({dn:.3f})={cc:.3f}+{cs:.3f}-{t:.3f}={residual:.6f}\ \text{{kN}}$$

$$\boxed{{R(d_n)={residual:.6f}\ \text{{kN}}}}$$""",
            rf"""**Step 6 — Accept the neutral axis**

$$R(d_n)\approx0$$

**For this beam**

$$\boxed{{d_n={dn:.3f}\ \text{{mm}}}}$$

$$a=\gamma d_n=({gamma:.3f})({dn:.3f})={a:.3f}\ \text{{mm}}$$

$$\boxed{{a={a:.3f}\ \text{{mm}}}}$$""",
        )
        method = "General multi-layer equilibrium solution"

    convergence = rf"""**Convergence evidence**

{_iteration_table(r, dn, cc, t, cs, residual)}

**Final result:** $d_n={dn:.3f}\,\text{{mm}}$, $a={a:.3f}\,\text{{mm}}$, $R={residual:.6f}\,\text{{kN}}$."""

    def final_diagram() -> None:
        st.markdown("#### Converged neutral axis and block depth")
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
            moment_sign=str(view.moment_sign or "positive"),
        )
        render_plotly_diagram(
            fig,
            key=f"bending_uls_equilibrium_in_check2_{view.moment_sign}",
            title="Neutral axis and block depth",
            config={"displayModeBar": False},
        )

    return method, purpose, steps, convergence, final_diagram


def _info(legacy: Any, help_text: str, heading: str, body: str) -> Callable[[], None]:
    def render() -> None:
        with legacy._bending_check_info_row(help_text=help_text):
            st.markdown(f"### {heading}\n\n{body}")

    return render


def _install_dispatch(legacy: Any) -> None:
    if getattr(legacy, "_uls_check2_original_step", None) is not None:
        return
    original = legacy.step_expander_calcbox

    def dispatch(*args: Any, **kwargs: Any):
        fn = _ACTIVE.get()
        return fn(original, *args, **kwargs) if fn else original(*args, **kwargs)

    legacy._uls_check2_original_step = original
    legacy.step_expander_calcbox = dispatch


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

    _install_dispatch(legacy)
    method, purpose, steps, convergence, final_diagram = _check2_payload(view, r)
    deferred: dict[str, Any] | None = None

    def intercept(original: Callable[..., Any], *args: Any, **kwargs: Any):
        nonlocal deferred
        uid = str(kwargs.get("uid", args[0] if args else ""))
        if uid == "bending_uls_authoritative_strains":
            deferred = dict(kwargs)
            return None
        if uid == "bending_uls_authoritative_equilibrium":
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
                for i, md in enumerate(steps, 1):
                    calcbox(md, uid=f"bending_uls_check2_step_{i}")

            def right_column_diagrams() -> None:
                if old_diagram:
                    old_diagram()
                final_diagram()

            revised["details_md"] = convergence
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
                k["content_before"] = _info(
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

        if uid == "bending_uls_authoritative_4":
            revised["summary_line"] = str(revised.get("summary_line", "")).replace("Check 5", "Check 4")
            revised["details_md"] = (
                str(revised.get("details_md", ""))
                .replace("from Check 4", "from Check 3")
                .replace("established in Check 3", "established in Check 2")
            )
        elif uid == "bending_uls_authoritative_6":
            revised["summary_line"] = str(revised.get("summary_line", "")).replace("Check 6", "Check 5")
        elif uid == "bending_uls_authoritative_7":
            revised["summary_line"] = str(revised.get("summary_line", "")).replace("Check 7", "Check 6")
            revised["details_md"] = str(revised.get("details_md", "")).replace("from Check 5", "from Check 4")
        elif uid == "bending_uls_authoritative_8":
            revised["summary_line"] = str(revised.get("summary_line", "")).replace("Check 8", "Check 7")
        return original(*args, **revised)

    token = _ACTIVE.set(intercept)
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
        _ACTIVE.reset(token)


__all__ = ["render_bending_uls_checks"]
