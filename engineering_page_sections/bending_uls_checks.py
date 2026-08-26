"""ULS Bending teaching checks backed by authoritative publications."""

from __future__ import annotations

import math
from contextlib import contextmanager

import streamlit as st

from bending_neutral_axis_teaching import neutral_axis_hand_solution

from bending_diagrams import (
    _plot_strain_profile,
    _make_uls_stress_block_figure,
    _make_uls_force_model_figure,
)
from bending_core import _stress_strain_state
from state_and_helpers import get_param, render_timing_mark
from widgets_helpers import (
    apply_step_expander_css,
    info_i_button,
    render_calculation_display_control,
    render_plotly_diagram,
    step_expander_calcbox,
)


@contextmanager
def _bending_check_info_row(help_text: str):
    """Render the technical-basis button at the calc column's top right."""
    col_info_button, _col_spacer = st.columns([0.28, 0.72])
    with col_info_button:
        with info_i_button(help_text=help_text, use_container_width=True):
            yield


def _render_uls_overview_info() -> None:
    with _bending_check_info_row("What are the ULS checks assessing?"):
        st.markdown(
            r"""### Ultimate Limit State (ULS)

Ultimate Limit State checks determine whether the beam has sufficient strength to resist the design actions without structural failure.

For bending, the section is analysed at its ultimate condition. The extreme compression concrete is assumed to reach its ultimate compressive strain:

$$\varepsilon_{cu}=0.003$$

Strain compatibility is then used to determine the corresponding reinforcement strains and stresses. The internal concrete compression and reinforcement forces are balanced to establish the neutral axis and ultimate moment capacity.

The ULS calculations therefore answer:

$$\boxed{\text{Can this beam safely resist the ultimate design load?}}$$

The calculated design capacity, such as $\phi M_u$, is compared directly with the design action $M^*$. The ULS checks also consider the reinforcement response, concrete compression behaviour, neutral-axis position and ductility requirements needed to establish the ultimate strength of the section.

ULS represents the **strength and collapse-safety side of the design**. Normal-use behaviour such as cracking and deflection is assessed separately at the Serviceability Limit State."""
        )


def _teaching_steel_response_state(
    *, strain: float, final_stress_mpa: float, Es_mpa: float, fsy_mpa: float
) -> tuple[float, bool, str]:
    """Classify a published steel result for the Check 4 teaching display only."""

    elastic_trial_stress = float(Es_mpa) * float(strain)
    yielded = math.isfinite(elastic_trial_stress) and abs(elastic_trial_stress) > float(fsy_mpa) + 1e-9
    role = (
        "tension" if final_stress_mpa < 0.0
        else "compression" if final_stress_mpa > 0.0
        else "approximately zero stress"
    )
    return elastic_trial_stress, yielded, f"{'Yielded' if yielded else 'Elastic'} {role}"


def _render_authoritative_uls_steps(
    *, top_results, b: float, D: float, fc: float, fsy: float,
    demand: float, moment_sign: str,
) -> None:
    """Render the published strain-compatible ULS result without recalculating it."""

    alpha2 = float(top_results.get("alpha2", 0.0) or 0.0)
    gamma = float(top_results.get("gamma", 0.0) or 0.0)
    dn = float(top_results.get("c", 0.0) or 0.0)
    d = float(top_results.get("d", 0.0) or 0.0)
    block_depth = float(top_results.get("a", 0.0) or 0.0)
    ku = float(top_results.get("ku", 0.0) or 0.0)
    phi = float(top_results.get("phi", 0.65) or 0.65)
    nominal = float(top_results.get("Mu_nom", 0.0) or 0.0)
    capacity = float(top_results.get("phi_Mu_cap", 0.0) or 0.0)
    utilisation = demand / capacity if capacity > 0.0 else float("inf")
    tension_kn = float(top_results.get("T_N", 0.0) or 0.0) / 1000.0
    concrete_kn = float(top_results.get("C_concrete_N", 0.0) or 0.0) / 1000.0
    compression_steel_kn = float(top_results.get("C_steel_N", 0.0) or 0.0) / 1000.0
    residual_kn = float(top_results.get("equilibrium_residual_n", 0.0) or 0.0) / 1000.0
    stresses = tuple(float(value) for value in top_results.get("steel_layer_stresses_mpa", ()) or ())
    steel_depths = tuple(float(value) for value in top_results.get("steel_layer_depths_mm", ()) or ())
    limit = float(top_results.get("ductility_limit", 0.36) or 0.36)
    triggered = bool(top_results.get("clause_815_triggered", False))
    clause_status = str(top_results.get("ductility_status", "NOT RUN") or "NOT RUN").upper()
    failed = tuple(top_results.get("clause_815_failed_requirements", ()) or ())
    failed_text = ", ".join(str(value).replace("_", " ") for value in failed) or "None"
    tension_n = float(top_results.get("T_N", 0.0) or 0.0)
    concrete_n = float(top_results.get("C_concrete_N", 0.0) or 0.0)
    compression_steel_n = float(top_results.get("C_steel_N", 0.0) or 0.0)
    layer_areas = tuple(float(value) for value in top_results.get("steel_layer_areas_mm2", ()) or ())
    layer_forces = tuple(float(value) for value in top_results.get("steel_layer_forces_n", ()) or ())
    layer_labels = tuple(str(value) for value in top_results.get("steel_layer_labels", ()) or ())
    layer_faces = tuple(str(value) for value in top_results.get("steel_layer_faces", ()) or ())
    if top_results.get("_authoritative_uls") and layer_areas:
        published_counts = {len(layer_areas), len(steel_depths), len(stresses), len(layer_forces)}
        if len(published_counts) != 1:
            raise RuntimeError(
                "Authoritative bending layer publication mismatch: "
                f"areas={len(layer_areas)}, depths={len(steel_depths)}, "
                f"stresses={len(stresses)}, forces={len(layer_forces)}"
            )
    # A zero-bar top row is a UI configuration aid, not an engineering steel
    # layer.  Keep the teaching path aligned with the solver's physical-layer
    # rule so it switches back to the direct solution as soon as the published
    # top layer has zero area.
    active_indices = tuple(index for index, area in enumerate(layer_areas) if area > 1e-9)
    layer_areas = tuple(layer_areas[index] for index in active_indices)
    steel_depths = tuple(steel_depths[index] for index in active_indices)
    stresses = tuple(stresses[index] for index in active_indices)
    layer_forces = tuple(layer_forces[index] for index in active_indices)
    layer_labels = tuple(
        layer_labels[index] if index < len(layer_labels) else ""
        for index in active_indices
    )
    layer_faces = tuple(
        layer_faces[index] if index < len(layer_faces) else ""
        for index in active_indices
    )
    stress_text = ", ".join(f"{value:.1f} MPa" for value in stresses) or "No steel layers"
    # These are section coordinates from the authoritative solver, measured
    # from the top face.  Use the governing tension layer rather than copying
    # the effective depth ``d`` (which is a design-depth input, not y_s).
    governing_tension_index = next(
        (index for index, value in enumerate(stresses) if value < 0.0),
        0,
    )
    y_s = steel_depths[governing_tension_index] if governing_tension_index < len(steel_depths) else d
    Es_uls = float(get_param("Es") or 200000.0)
    eps_sy = fsy / Es_uls if Es_uls > 0.0 else float("nan")
    steel_layer_lines = []
    stress_summary_parts = []
    final_layer_table_lines = [
        "| Layer | $A_{s,i}$ (mm²) | $y_i$ (mm) | Relative to NA | $\\varepsilon_{s,i}$ | $f_{s,i}$ (MPa) | State | $F_{s,i}$ (kN) |",
        "|---|---:|---:|---|---:|---:|---|---:|",
    ]
    final_layer_table_lines[0] = (
        "| Layer | $y_i$ (mm) | $\\varepsilon_{s,i}$ | "
        "Elastic trial stress (MPa) | "
        "Final steel stress (MPa) | State |"
    )
    final_layer_table_lines[1] = "|---|---:|---:|---:|---:|---|"
    for index, (area, depth, stress, force) in enumerate(
        zip(layer_areas, steel_depths, stresses, layer_forces), start=1
    ):
        face = layer_faces[index - 1] if index <= len(layer_faces) else "steel"
        label = layer_labels[index - 1] if index <= len(layer_labels) else f"{face.title()} reinforcement"
        role = "tension" if stress < 0.0 else "compression" if stress > 0.0 else "approximately zero stress"
        displayed_force = abs(force) / 1000.0 if role == "tension" else force / 1000.0
        strain = -0.003 * (depth - dn) / dn if abs(dn) > 1e-9 else float("nan")
        elastic_trial_stress, yielded, state_label = _teaching_steel_response_state(
            strain=strain, final_stress_mpa=stress, Es_mpa=Es_uls, fsy_mpa=fsy
        )
        stress_summary_parts.append(f"{label}: {stress:.1f} MPa")
        steel_layer_lines.append(
            f"- {label} ({role}): $A_{{s,{index}}}={area:.1f}\\,\\text{{mm}}^2$, "
            f"$\\sigma_{{s,{index}}}={stress:.1f}\\,\\text{{MPa}}$, "
            f"$F_{{s,{index}}}={displayed_force:.3f}\\,\\text{{kN}}$"
        )
        final_layer_table_lines.append(
            f"| {label} | {depth:.1f} | {strain:.6f} | {elastic_trial_stress:.1f} | "
            f"{stress:.1f} | {state_label} |"
        )
    steel_layer_text = "\n".join(steel_layer_lines) or "- Layer areas and forces were not published."
    identified_stress_text = "; ".join(stress_summary_parts) or stress_text
    final_layer_table_md = "\n".join(final_layer_table_lines)
    section_shape = str(top_results.get("section_shape", "RECT") or "RECT").upper()
    if section_shape == "RECT":
        concrete_resultant_md = rf"""
$$A_c=ba$$

$$C_c=\alpha_2f'_cA_c$$

$$C_c=\alpha_2f'_cba$$

The resultant acts at the centroid of the equivalent stress block:

$$y_{{C_c}}=\frac{{a}}{{2}}={block_depth / 2.0:.1f}\,\text{{mm}}$$
"""
    else:
        concrete_area = float(top_results.get("compression_concrete_area_mm2", 0.0) or 0.0)
        concrete_centroid = float(top_results.get("concrete_centroid_mm", 0.0) or 0.0)
        concrete_resultant_md = rf"""
$$C_c=\alpha_2f'_cA_c$$

For this {section_shape} section, the authoritative stress-block area is
$A_c={concrete_area:.1f}\,\text{{mm}}^2$ and its centroid is
$y_{{C_c}}={concrete_centroid:.1f}\,\text{{mm}}$ from the extreme compression face.
"""
    na_teaching = neutral_axis_hand_solution(
        b=b,
        D=D,
        fc=fc,
        fsy=fsy,
        Es=Es_uls,
        alpha2=alpha2,
        gamma=gamma,
        dn=dn,
        block_depth=block_depth,
        layer_areas=layer_areas,
        layer_depths=steel_depths,
        layer_stresses=stresses,
        layer_labels=layer_labels,
        section_shape=section_shape,
    )
    iteration_trace = tuple(top_results.get("neutral_axis_iteration_trace", ()) or ())
    iteration_table_lines = [
        "| Solver step | $d_n$ (mm) | Concrete compression (kN) | Steel tension (kN) | Steel compression (kN) | Residual (kN) |",
        "|---:|---:|---:|---:|---:|---:|",
    ]
    # Keep the teaching table readable: it is evidence of convergence, not a
    # dump of every internal bisection trial.
    trace_indices = tuple(
        index for index in (0, 1, len(iteration_trace) // 2, len(iteration_trace) - 1)
        if 0 <= index < len(iteration_trace)
    )
    for position, index in enumerate(dict.fromkeys(trace_indices)):
        entry = iteration_trace[index]
        label = "Initial" if position == 0 else "Intermediate"
        iteration_table_lines.append(
            f"| {label} | {float(entry.get('dn_mm', 0.0)):.3f} | "
            f"{float(entry.get('concrete_force_n', 0.0)) / 1000.0:.3f} | "
            f"{float(entry.get('tension_force_n', 0.0)) / 1000.0:.3f} | "
            f"{float(entry.get('compression_steel_force_n', 0.0)) / 1000.0:.3f} | "
            f"{float(entry.get('equilibrium_residual_n', 0.0)) / 1000.0:.6f} |"
        )
    iteration_table_lines.append(
        f"| **Converged** | {dn:.3f} | {concrete_n / 1000.0:.3f} | {tension_n / 1000.0:.3f} | "
        f"{compression_steel_n / 1000.0:.3f} | {residual_kn:.6f} |"
    )
    iteration_table_md = "\n".join(iteration_table_lines)
    geometry_table_lines = [
        "| Layer | $A_{s,i}$ (mm²) | $y_i$ (mm) |",
        "|---|---:|---:|",
    ]
    relative_to_na_lines = [
        "| Layer | $y_i$ (mm) | Relative to neutral axis |",
        "|---|---:|---|",
    ]
    for index, (area, depth) in enumerate(zip(layer_areas, steel_depths), start=1):
        label = layer_labels[index - 1] if index <= len(layer_labels) else f"Layer {index}"
        geometry_table_lines.append(f"| {label} | {area:.2f} | {depth:.1f} |")
        side = "Below NA — tension side" if depth > dn else "Above NA — compression side" if depth < dn else "At NA"
        relative_to_na_lines.append(f"| {label} | {depth:.1f} | {side} |")
    geometry_table_md = "\n".join(geometry_table_lines)
    relative_to_na_md = "\n".join(relative_to_na_lines)
    if len(layer_areas) == 1:
        neutral_axis_method_md = rf"""
**Purpose**

Determine how the neutral-axis depth $d_n$ is found from internal force equilibrium.

$$\boxed{{\sum C=\sum T}}$$

$$C_c=\alpha_2f'_cba=\alpha_2f'_cb\gamma d_n$$

**Direct single-layer solution**

$$T=A_{{st}}f_{{sy}}$$

$$C_c=T$$

$$\boxed{{d_n=\frac{{A_{{st}}f_{{sy}}}}{{\alpha_2f'_cb\gamma}}}}$$

With one active yielded tension layer, $d_n$ can be obtained directly from force
equilibrium.
"""
    else:
        neutral_axis_method_md = rf"""
**Purpose**

Determine how the neutral-axis depth $d_n$ is found from internal force equilibrium.

$$\boxed{{\sum C=\sum T}}$$

The app starts with a trial $d_n$, calculates the concrete and reinforcement
forces, checks equilibrium, and adjusts $d_n$ until the section balances.

**Step 1 — Concrete compression**

Calculate the concrete compression force for the trial neutral-axis depth.

$$C_c=\alpha_2 f'_c b\gamma d_n$$

**Step 2 — Reinforcement strain**

Calculate the strain in each reinforcement layer from its position relative to
the neutral axis.

$$\varepsilon_{{s,i}}=-\varepsilon_{{cu}}\frac{{y_i-d_n}}{{d_n}}$$

**Step 3 — Reinforcement stress**

Convert the steel strain into stress and limit it to the steel yield strength.

$$f_{{s,i}}=\operatorname{{sign}}(\varepsilon_{{s,i}})\min\left(E_s|\varepsilon_{{s,i}}|,f_{{sy}}\right)$$

**Step 4 — Reinforcement force**

Convert the steel stress into the force carried by each reinforcement layer.

$$F_{{s,i}}=A_{{s,i}}f_{{s,i}}$$

**Step 5 — Equilibrium residual**

Calculate the difference between total compression and total tension.

$$R(d_n)=\sum C-\sum T$$

**Step 6 — Accept the neutral axis**

Accept the neutral-axis depth when equilibrium is reached.

$$R(d_n)\approx0$$

If $R(d_n)\ne0$, adjust $d_n$ and repeat Steps 1–5 until $R(d_n)\approx0$.
Check 3 shows the converged neutral-axis depth and resulting reinforcement response.
"""
    # These are deliberately authored display blocks, rather than inferred
    # from markdown. Each equation stays with its professional explanation.
    if len(layer_areas) == 1:
        neutral_axis_progressive_steps = (
            rf"""**Purpose**

Determine how the neutral-axis depth $d_n$ is found from internal force equilibrium.

$$\boxed{{\sum C=\sum T}}$$

**Step 1 â€” Concrete compression**

$$C_c=\alpha_2f'_cba=\alpha_2f'_cb\gamma d_n$$""",
            rf"""**Step 2 â€” Tension force**

$$T=A_{{st}}f_{{sy}}$$

At equilibrium, $C_c=T$.""",
            rf"""**Step 3 â€” Solve and accept the neutral axis**

$$\boxed{{d_n=\frac{{A_{{st}}f_{{sy}}}}{{\alpha_2f'_cb\gamma}}}}$$

With one active yielded tension layer, $d_n$ can be obtained directly from force equilibrium.""",
        )
    else:
        neutral_axis_progressive_steps = (
            rf"""**Purpose**

Determine how the neutral-axis depth $d_n$ is found from internal force equilibrium.

$$\boxed{{\sum C=\sum T}}$$

The app starts with a trial $d_n$, calculates the concrete and reinforcement forces,
checks equilibrium, and adjusts $d_n$ until the section balances.

**Step 1 â€” Concrete compression**

Calculate the concrete compression force for the trial neutral-axis depth.

$$C_c=\alpha_2 f'_c b\gamma d_n$$""",
            rf"""**Step 2 â€” Reinforcement strain**

Calculate the strain in each reinforcement layer from its position relative to the neutral axis.

$$\varepsilon_{{s,i}}=-\varepsilon_{{cu}}\frac{{y_i-d_n}}{{d_n}}$$""",
            rf"""**Step 3 â€” Reinforcement stress**

Convert the steel strain into stress and limit it to the steel yield strength.

$$f_{{s,i}}=\operatorname{{sign}}(\varepsilon_{{s,i}})\min\left(E_s|\varepsilon_{{s,i}}|,f_{{sy}}\right)$$""",
            rf"""**Step 4 â€” Reinforcement force**

Convert the steel stress into the force carried by each reinforcement layer.

$$F_{{s,i}}=A_{{s,i}}f_{{s,i}}$$""",
            rf"""**Step 5 â€” Equilibrium residual**

Calculate the difference between total compression and total tension.

$$R(d_n)=\sum C-\sum T$$""",
            rf"""**Step 6 â€” Accept the neutral axis**

Accept the neutral-axis depth when equilibrium is reached.

$$R(d_n)\approx0$$

If $R(d_n)\ne0$, adjust $d_n$ and repeat Steps 1â€“5 until $R(d_n)\approx0$.
Check 3 shows the converged neutral-axis depth and resulting reinforcement response.""",
        )

    neutral_axis_equilibrium_md = rf"""
**Purpose**

Solve the section equilibrium and confirm the neutral-axis depth at which total
compression and total tension balance.

**Representative equilibrium steps**

{iteration_table_md}

If $\sum T>\sum C$, the compression block is insufficient and the solver generally
moves toward a larger $d_n$. If $\sum C>\sum T$, it generally moves toward a
smaller $d_n$.

$$\boxed{{R(d_n)=\sum C-\sum T}}$$

$$\boxed{{R({dn:.6f})={residual_kn:.9f}\,\text{{kN}}\approx0}}$$

**Final neutral-axis depth**

$$\boxed{{d_n={dn:.3f}\,\text{{mm}}}}$$

$$a=\gamma d_n={gamma:.3f}\times{dn:.6f}={block_depth:.3f}\,\text{{mm}}$$

$$\boxed{{a={block_depth:.3f}\,\text{{mm}}}}$$

**Force equilibrium is satisfied. The final reinforcement strains and stresses
are calculated in Check 4 using this converged neutral-axis depth.**
"""
    na_table_lines = [
        "| Layer | $A_{s,i}$ (mm²) | $y_i$ (mm) | Assumed regime | Quadratic contribution |",
        "|---|---:|---:|---|---|",
    ]
    na_q_lines = []
    na_boundary_lines = []
    na_b_terms = []
    na_c_terms = []
    for row in na_teaching["rows"]:
        na_table_lines.append(
            f"| {row['label']} | {row['area']:.2f} | {row['depth']:.1f} | "
            f"{row['state']} | {row['contribution']} |"
        )
        if row["q"] > 0.0:
            na_q_lines.append(
                f"$$Q_{{{row['index']}}}=A_{{s,{row['index']}}}E_s\\varepsilon_{{cu}}="
                f"({row['area']:.2f})({Es_uls:.0f})(0.003)="
                f"{row['q'] / 1000.0:.3f}\\,\\text{{kN}}$$\n\n"
                f"$$Q_{{{row['index']}}}y_{{{row['index']}}}="
                f"({row['q'] / 1000.0:.3f})({row['depth']:.1f})="
                f"{row['qy'] / 1000.0:.3f}\\,\\text{{kN}}\\cdot\\text{{mm}}$$"
            )
            na_b_terms.append(f"+{row['q'] / 1000.0:.6f}")
            na_c_terms.append(f"-({row['q'] / 1000.0:.6f})({row['depth']:.6f})")
        elif row["state"] == "yielded tension":
            na_b_terms.append(f"-{row['area'] * fsy / 1000.0:.6f}")
        elif row["state"] == "yielded compression":
            na_b_terms.append(f"+{row['area'] * fsy / 1000.0:.6f}")
        if row["stress"] < 0.0:
            na_boundary_lines.append(
                f"**{row['label']} — {row['state']}**\n\n"
                f"$$d_{{n,y,{row['index']}}}=\\frac{{y_{{{row['index']}}}}}"
                f"{{1+\\varepsilon_{{sy}}/\\varepsilon_{{cu}}}}="
                f"{row['yield_boundary']:.3f}\\,\\text{{mm}}$$"
            )
    na_table_md = "\n".join(na_table_lines)
    na_q_md = "\n\n".join(na_q_lines) or "No layers remain elastic in the accepted regime, so $\\sum Q_i=0$."
    na_boundary_md = "\n".join(na_boundary_lines) or "No tensile reinforcement layers are present."
    displacement_note = ""
    b_symbolic = r"C_y-T_y+\sum_{\mathrm{elastic}}Q_i"
    if na_teaching["displaced"] > 0.0:
        b_symbolic += r"-\sum_{y_i\leq a}A_{s,i}\alpha_2f'_c"
        displacement_note = rf"""

Because the equivalent concrete block uses gross area, the authoritative
solver removes ${na_teaching['displaced'] / 1000.0:.3f}\,\text{{kN}}$ of displaced
concrete stress at steel layers located inside the block. This correction is
included in $B$ below.
"""
        na_b_terms.append(f"-{na_teaching['displaced'] / 1000.0:.6f}")
    na_b_substitution = " ".join(na_b_terms) or "0"
    na_c_substitution = " ".join(na_c_terms) or "0"
    root_lines = []
    for root, valid in na_teaching["roots"]:
        reason = "physically valid and regime-consistent" if valid else "rejected: outside the section or inconsistent with the assumed regime"
        root_lines.append(f"- $d_n={root:.6f}\\,\\text{{mm}}$: {reason}.")
    roots_md = "\n".join(root_lines) or "The authoritative regime does not produce a real candidate root."
    valid_roots = [root for root, valid in na_teaching["roots"] if valid]
    hand_dn = min(valid_roots, key=lambda value: abs(value - dn)) if valid_roots else float("nan")
    hand_difference = abs(hand_dn - dn) if math.isfinite(hand_dn) else float("nan")
    if section_shape == "RECT" and na_teaching["reproduced"]:
        if na_teaching["linear"]:
            solve_md = rf"""
No layers remain elastic, so the equation reduces to:

$$K_cd_n+C_y-T_y=0$$

$$d_n=\frac{{T_y-C_y}}{{K_c}}={dn:.6f}\,\text{{mm}}$$
"""
        else:
            solve_md = rf"""
The current numerical equation, expressed in kN and mm, is:

$$({na_teaching['A'] / 1000.0:.9f})d_n^2+({na_teaching['B'] / 1000.0:.9f})d_n+({na_teaching['C'] / 1000.0:.9f})=0$$

$$d_n=\frac{{-B\pm\sqrt{{B^2-4AC}}}}{{2A}}$$

Candidate roots:

{roots_md}

The accepted root reproduces the authoritative neutral-axis depth.
"""
        neutral_axis_details_md = rf"""
**Purpose**

Determine the neutral-axis depth $d_n$ that satisfies internal force equilibrium:

$$\boxed{{\sum C=\sum T}}$$

A single yielded tension layer can be solved directly. With multiple layers,
each steel force depends on $d_n$, so the authoritative solver iterates until
the residual is approximately zero.

**Inputs and symbol meanings**

- $b={b:.1f}\,\text{{mm}}$: beam width.
- $f'_c={fc:.1f}\,\text{{MPa}}$: characteristic concrete compressive strength.
- $\alpha_2={alpha2:.3f}$: rectangular stress-block intensity factor.
- $\gamma={gamma:.3f}$: rectangular stress-block depth factor.
- $E_s={Es_uls:.0f}\,\text{{MPa}}$: steel elastic modulus.
- $f_{{sy}}={fsy:.1f}\,\text{{MPa}}$: steel yield stress.
- $\varepsilon_{{cu}}=0.003$: ultimate concrete compression strain.
- $\varepsilon_{{sy}}=f_{{sy}}/E_s={na_teaching['eps_sy']:.6f}$: steel yield strain.
- $A_{{s,i}}$: area of layer $i$; $y_i$: its depth from the compression face.
- $d_n$: neutral-axis depth; $a=\gamma d_n$: equivalent block depth.

**Concrete compression force**

$$C_c=\alpha_2f'_cba=\alpha_2f'_cb\gamma d_n$$

The concrete compression force increases directly with $d_n$.

**Case A — one yielded tension layer**

For a simple beam where the governing tension layer yields:

$$T=A_{{st}}f_{{sy}}$$

$$\boxed{{d_n=\frac{{A_{{st}}f_{{sy}}}}{{\alpha_2f'_cb\gamma}}}}$$

No iteration is required for that simplified case. The resulting $d_n$ is then
checked through strain compatibility and $k_u$.

**Case B — multiple reinforcement layers**

For every layer, strain, stress and force depend on the trial neutral axis:

$$\varepsilon_{{s,i}}=\varepsilon_{{cu}}\frac{{y_i-d_n}}{{d_n}}$$

$$f_{{s,i}}=\operatorname{{clip}}\left(E_s\varepsilon_{{s,i}},-f_{{sy}},f_{{sy}}\right)$$

$$F_{{s,i}}=A_{{s,i}}f_{{s,i}}$$

“Top” and “bottom” describe physical location only. A layer is in tension when
$y_i>d_n$, and in compression when $y_i<d_n$, for this top-face compression case.

**Authoritative reinforcement layers and accepted regimes**

{na_table_md}

**Stress-regime boundaries**

The boundaries divide possible $d_n$ values into piecewise steel regimes. The
authoritative solver selects the equilibrium state; Check 3 verifies its final strains.

{na_boundary_md}

**Representative equilibrium steps**

The app performs the trial-and-update process automatically:

$$d_n\rightarrow\text{{steel strains}}\rightarrow\text{{steel stresses}}\rightarrow\text{{steel forces}}\rightarrow R(d_n)\rightarrow\text{{updated }}d_n$$

{iteration_table_md}

When tension exceeds compression, $d_n$ generally increases; when compression
exceeds tension, $d_n$ generally decreases. The table shows representative
steps from the automatic equilibrium search, followed by the converged result.

**Grouped algebra terms**

$$K_c=\alpha_2f'_cb\gamma=({alpha2:.3f})({fc:.1f})({b:.1f})({gamma:.3f})={na_teaching['kc'] / 1000.0:.6f}\,\text{{kN/mm}}$$

$K_c$ is an algebraic convenience representing concrete compression force per
unit neutral-axis depth; it is not an AS 3600 symbol. Thus $C_c=K_cd_n$.

For each elastic layer, $Q_i=A_{{s,i}}E_s\varepsilon_{{cu}}$ and
$F_{{s,i}}=Q_i(y_i-d_n)/d_n$ in tension-magnitude form. $Q_i$ is also an
internal algebraic convenience, not an AS 3600 symbol.

{na_q_md}

$T_y={na_teaching['ty'] / 1000.0:.3f}\,\text{{kN}}$ is yielded tension steel;
$C_y={na_teaching['cy'] / 1000.0:.3f}\,\text{{kN}}$ is yielded compression steel.
{displacement_note}

**General equilibrium equation for the accepted regime**

$$\sum C=\sum T$$

$$K_cd_n^2+\left({b_symbolic}\right)d_n-\sum_{{\mathrm{{elastic}}}}Q_i y_i=0$$

$$Ad_n^2+Bd_n+C=0$$

$$\boxed{{A=K_c=\alpha_2f'_cb\gamma}}={na_teaching['A'] / 1000.0:.6f}\,\text{{kN/mm}}$$

$$A=({alpha2:.6f})({fc:.6f})({b:.6f})({gamma:.6f})/1000={na_teaching['A'] / 1000.0:.9f}\,\text{{kN/mm}}$$

$A$ represents the concrete compression contribution.

$$\boxed{{B={b_symbolic}}}={na_teaching['B'] / 1000.0:.6f}\,\text{{kN}}$$

$$B={na_b_substitution}={na_teaching['B'] / 1000.0:.9f}\,\text{{kN}}$$

$B$ combines yielded-steel resultants and the $d_n$-dependent part of elastic steel forces.

$$\boxed{{C=-\sum_{{\mathrm{{elastic}}}}Q_i y_i}}={na_teaching['C'] / 1000.0:.6f}\,\text{{kN}}\cdot\text{{mm}}$$

$C$ contains the depth-weighted contribution of every elastic steel layer.

Numerical substitution:

$$C={na_c_substitution}={na_teaching['C'] / 1000.0:.9f}\,\text{{kN\,mm}}$$

**Solve for neutral-axis depth**

{solve_md}

$$a=\gamma d_n={gamma:.3f}\times {dn:.6f}={block_depth:.3f}\,\text{{mm}}$$

**Equilibrium result**

- $d_n={dn:.6f}\,\text{{mm}}$.
- $a={block_depth:.6f}\,\text{{mm}}$.
- $R(d_n)={residual_kn:.9f}\,\text{{kN}}\approx0$.

**Equilibrium method**

The app completes the repeated neutral-axis search using the section residual:

$$R(d_n)=C_c(d_n)+\sum_iF_{{s,i}}(d_n)$$

$$R({dn:.6f})={residual_kn:.9f}\,\text{{kN}}\approx0$$

**Result**

$d_n={dn:.3f}\,\text{{mm}}$ and $a={block_depth:.3f}\,\text{{mm}}$.
**Force equilibrium is satisfied. The final strain, stress and force in each reinforcement layer are evaluated in Check 4.**
"""
    else:
        fallback_reason = (
            f"the authoritative section shape is {section_shape}, so the rectangular "
            "closed-form stress-block equation is not applicable"
            if section_shape != "RECT"
            else "the fixed accepted regime did not reproduce the authoritative neutral-axis depth within numerical tolerance"
        )
        neutral_axis_details_md = rf"""
**Purpose**

Determine $d_n$ from force equilibrium using every authoritative reinforcement layer.

**Why a closed-form hand equation is not displayed**

For this case, {fallback_reason}. Displaying the rectangular quadratic would
therefore be misleading.

{na_table_md}

**Equilibrium result**

The app completes the repeated neutral-axis search using the section residual:

$$R(d_n)=C_c(d_n)+\sum_i F_{{s,i}}(d_n)=0$$

Each trial uses the section geometry, compatible layer stresses, yield limits
and displaced-concrete correction.

The converged residual is ${residual_kn:.6f}\,\text{{kN}}$.

$$a=\gamma d_n={gamma:.3f}\times {dn:.6f}={block_depth:.3f}\,\text{{mm}}$$

**Result:** $d_n={dn:.3f}\,\text{{mm}}$, $a={block_depth:.3f}\,\text{{mm}}$.
"""
    lever_arm = nominal * 1e6 / tension_n if abs(tension_n) > 1e-9 else 0.0
    utilisation_text = f"{utilisation:.3f}" if math.isfinite(utilisation) else "not finite (zero capacity)"
    concrete_centroid = float(top_results.get("concrete_centroid_mm", block_depth / 2.0) or block_depth / 2.0)
    moment_terms = []
    for label, depth, stress, force in zip(layer_labels, steel_depths, stresses, layer_forces):
        if stress < 0.0:
            force_kn = abs(force) / 1000.0
            arm_mm = depth - concrete_centroid
        else:
            force_kn = force / 1000.0
            arm_mm = concrete_centroid - depth
        moment_terms.append(
            rf"- {label}: ${force_kn:.3f}\,\text{{kN}}\times{arm_mm:.3f}\,\text{{mm}}"
        )
    moment_terms_md = "\n".join(moment_terms) or "- No active reinforcement-layer forces were published."

    def info_control(help_text: str, heading: str, body: str):
        def render_info():
            with _bending_check_info_row(help_text=help_text):
                st.markdown(f"### {heading}\n\n{body}")
        return render_info

    def stress_block_diagram(
        key: str,
        title: str,
        *,
        show_dn: bool,
        show_lever_arm: bool,
        trial_neutral_axis: bool = False,
    ):
        def render_diagram():
            # Check 2 teaches the trial-and-balance method. Its diagram must
            # not disclose the converged neutral-axis result shown in Check 3.
            diagram_dn = max(1.0, min(0.35 * D, D - 1.0)) if trial_neutral_axis else dn
            diagram_a = gamma * diagram_dn if trial_neutral_axis else block_depth
            fig = _make_uls_stress_block_figure(
                b_mm=b, D_mm=D, d_mm=d, dn_mm=diagram_dn, a_mm=diagram_a,
                alpha2=alpha2, gamma=gamma, fc=fc, fsy=fsy,
                show_lever_arm=show_lever_arm,
                show_dn=show_dn or trial_neutral_axis,
                show_alpha_label=True, show_C=False, C_N=None,
                variant="13" if (show_dn or trial_neutral_axis) else "11",
                moment_sign=moment_sign,
            )
            if trial_neutral_axis:
                for annotation in fig.layout.annotations or ():
                    label = str(annotation.text or "")
                    colour = str(getattr(annotation.font, "color", "") or "").lower()
                    if colour == "red" and label.lstrip().startswith("a ="):
                        annotation.text = "a = γ d<sub>n</sub>"
                    elif colour == "blue" and "mm" in label:
                        annotation.text = "Trial neutral axis d<sub>n</sub>"
                        annotation.xref = "paper"
                        annotation.x = 0.98
                        annotation.xanchor = "right"
                        annotation.yshift = 14
                    elif colour == "blue" and label.lstrip().startswith("T ("):
                        annotation.text = "f<sub>s</sub> = E<sub>s</sub> ε<sub>s</sub>"
                fig.update_layout(height=320, margin=dict(l=0, r=10, t=45, b=10))
            render_plotly_diagram(fig, key=key, title=title, config={"displayModeBar": False})
        return render_diagram

    def force_diagram(key: str, title: str):
        def render_diagram():
            fig = _make_uls_force_model_figure(
                D_mm=D, d_mm=d, a_mm=block_depth,
                C_N=float(top_results.get("C_concrete_N", 0.0) or 0.0),
                T_N=float(top_results.get("T_N", 0.0) or 0.0),
                moment_sign=moment_sign, dn_mm=dn,
            )
            render_plotly_diagram(fig, key=key, title=title, config={"displayModeBar": False})
        return render_diagram

    def strain_diagram(key: str, *, title: str = "ULS strain compatibility", trial: bool = False):
        state = _stress_strain_state("ULS", moment_sign=moment_sign)
        fig = _plot_strain_profile(state, state_label="ULS", layout=None, moment_sign=moment_sign)
        if trial:
            for annotation in fig.layout.annotations or ():
                colour = str(getattr(annotation.font, "color", "") or "").lower()
                if colour == "red":
                    annotation.text = "ε<sub>cu</sub>"
                elif colour == "blue":
                    annotation.text = "Trial ε<sub>s</sub>"
            fig.update_layout(height=320, margin=dict(l=0, r=10, t=45, b=10))
        render_plotly_diagram(
            fig, key=key,
            title=title, config={"displayModeBar": False},
        )

    def trial_method_diagrams():
        stress_block_diagram(
            "bending_uls_authoritative_method_diagram", "Trial stress block",
            show_dn=False, show_lever_arm=False, trial_neutral_axis=True,
        )()
        strain_diagram(
            f"bending_uls_authoritative_check2_strain_{moment_sign}",
            title="Trial strain compatibility",
            trial=True,
        )

    def render_uls_calcbox(*args, **kwargs):
        """Keep one Bending ULS display preference across every check card."""
        kwargs.setdefault("display_section", "bending_uls")
        return step_expander_calcbox(*args, **kwargs)

    render_uls_calcbox(
        uid="bending_uls_authoritative_1",
        summary_line=(
            "Check 1 — Concrete stress block | "
            f"alpha2 = {alpha2:.3f}, gamma = {gamma:.3f}"
        ),
        details_md=rf"""
**Purpose**

Define the AS 3600 rectangular concrete compression block used by the authoritative ULS section analysis.

**Inputs**

- Concrete strength: $f'_c={fc:.1f}\,\text{{MPa}}$
- Compression-zone width: $b={b:.1f}\,\text{{mm}}$
- Stress-block factors: $\alpha_2={alpha2:.3f}$ and $\gamma={gamma:.3f}$

**Formula**

$$a=\gamma d_n$$

$$C_c=\alpha_2f'_cba=\alpha_2f'_cb\gamma d_n$$

**Substitution**

$$C_c=({alpha2:.3f})({fc:.1f})({b:.1f})({gamma:.3f})d_n$$

$$\boxed{{C_c={alpha2 * fc * b * gamma / 1000.0:.3f}d_n\,\text{{kN}}}}$$

**Result**

Once $d_n$ is known, the concrete compression force is known. Check 2 explains how $d_n$ is found.
""",
        status=None,
        content_before=info_control(
            "Concrete stress block", "Check 1 — Concrete stress block",
            r"""
This check determines the equivalent rectangular stress-block factors
$\alpha_2$ and $\gamma$ used for Ultimate Limit State flexural design.

#### What the factors represent

The actual concrete compression stress is nonlinear. AS 3600 represents it
with an equivalent rectangular block [1] so that the simplified block develops
the appropriate compression resultant and lever arm.

- $\alpha_2 f'_c$ is the equivalent average compression stress.
- $a=\gamma d_n$ is the equivalent stress-block depth.

Together these factors define the concrete compression force used in the
strain-compatible section analysis.

#### Why this check matters

The stress-block intensity and depth control the concrete compression
resultant, its line of action and therefore the section's bending resistance.

#### References

[1] AS 3600:2018, Clause 8.1.3 — equivalent rectangular stress block.
""",
        ),
        diagram_fn=stress_block_diagram(
            "bending_uls_authoritative_1_diagram", "Concrete stress block",
            show_dn=False, show_lever_arm=False,
        ),
    )
    render_uls_calcbox(
        uid="bending_uls_authoritative_strains",
        summary_line=(
            "Check 4 — Reinforcement strains and stresses | "
            f"Result: {identified_stress_text}"
        ),
        details_md=rf"""
**Purpose**

Using the neutral-axis depth from Check 3, calculate the final strain and stress
in each active reinforcement layer.

**Inputs**

- Neutral-axis depth: $d_n={dn:.3f}\,\text{{mm}}$
- Steel elastic modulus: $E_s={Es_uls:.0f}\,\text{{MPa}}$
- Steel yield strength: $f_{{sy}}={fsy:.1f}\,\text{{MPa}}$

Negative stress denotes tension and positive stress denotes compression in this
bending sign convention.

$$\varepsilon_{{s,i}}=-\varepsilon_{{cu}}\frac{{y_i-d_n}}{{d_n}}$$

$$f_{{s,\mathrm{{elastic}},i}}=E_s\varepsilon_{{s,i}}$$

$$f_{{s,i}}=E_s\varepsilon_{{s,i}}\quad\text{{if }}|E_s\varepsilon_{{s,i}}|\leq f_{{sy}}$$

$$f_{{s,i}}=\operatorname{{sign}}(\varepsilon_{{s,i}})f_{{sy}}\quad\text{{if }}|E_s\varepsilon_{{s,i}}|>f_{{sy}}$$

**Final reinforcement strain and stress state**

{final_layer_table_md}

**Result:** {identified_stress_text}
""",
        status=None,
        content_before=info_control(
            "Reinforcement strains and stresses", "Check 4 — Reinforcement strains and stresses",
            r"""
Using the neutral-axis depth already solved in Check 3, this check calculates
the final strain and final steel stress for each active reinforcement layer.

#### Why this check matters

The reinforcement forces used later are valid only when they are derived from
the compatible strain at the actual location of each layer [1]. The concrete
compression block used with those forces follows the equivalent rectangular
stress-block provisions [2].

#### References

[1] AS 3600:2018, Clause 8.1 — strain compatibility and internal equilibrium.
[2] AS 3600:2018, Clause 8.1.3 — equivalent rectangular stress block.
""",
        ),
        diagram_fn=lambda: strain_diagram(
            f"bending_uls_authoritative_check4_strain_{moment_sign}"
        ),
    )
    render_timing_mark("bending_page.uls_check.1.end")

    render_uls_calcbox(
        uid="bending_uls_authoritative_method",
        summary_line=(
            "Check 2 — Neutral-axis solution method | "
            + ("Direct single-layer solution" if len(layer_areas) == 1 else "General multi-layer equilibrium solution")
        ),
        details_md=neutral_axis_method_md,
        status=None,
        diagram_fn=trial_method_diagrams,
        display_section="bending_uls",
        progressive_steps=neutral_axis_progressive_steps,
        content_before=info_control(
            "Neutral-axis solution method",
            "Check 2 — Neutral-axis solution method",
            r"""
The neutral axis is the position through the section where longitudinal
bending strain is zero. Concrete on the compression side and reinforcement
on both sides of this position contribute compatible internal forces.

The neutral-axis depth $d_n$ is the distance from the extreme compression face
to the point in the section where longitudinal strain is zero. It is the key
unknown because changing $d_n$ changes both concrete compression and
reinforcement strain and force.

#### Strain, stress and reinforcement force

At ULS, plane sections are assumed to remain plane, so strain varies linearly
through the section. Once a trial $d_n$ is chosen, the strain at reinforcement
layer $i$, at depth $y_i$, is:

$$\varepsilon_{s,i}=-\varepsilon_{cu}\frac{y_i-d_n}{d_n}$$

where $\varepsilon_{s,i}$ is the layer strain and $\varepsilon_{cu}$ is the
ultimate concrete compressive strain. While the reinforcement remains elastic:

$$f_{s,i}=E_s\varepsilon_{s,i}$$

Its final stress is limited by the yield strength:

$$|f_{s,i}|\leq f_{sy}$$

The force carried by that layer is:

$$F_{s,i}=A_{s,i}f_{s,i}$$

Here $E_s$ is the steel elastic modulus, $f_{sy}$ is the steel yield strength,
and $A_{s,i}$ is the layer area [1].
“Top” and “bottom” are physical locations only: the tension/compression state
depends on the layer's position relative to the solved neutral axis.

#### Concrete compression and equilibrium

The same trial $d_n$ defines the AS 3600 equivalent concrete compression-block
depth [2]:

$$a=\gamma d_n$$

and the concrete compression resultant:

$$C_c=\alpha_2f'_cb\gamma d_n$$

Thus $d_n$ affects both concrete compression and reinforcement response:

$$d_n\rightarrow C_c,\qquad d_n\rightarrow\varepsilon_{s,i}\rightarrow f_{s,i}\rightarrow F_{s,i}$$

The correct value is the one at which internal compression and tension balance:

$$\boxed{\sum C=\sum T}$$

$$\boxed{R(d_n)=\sum C-\sum T=0}$$

With several reinforcement layers, their stresses cannot generally be known
before $d_n$ is known because each layer has a different position and strain.
The app therefore repeats trial values of $d_n$ until equilibrium is reached.

#### Why this check matters

An incorrect neutral-axis depth would invalidate the compatible steel
stresses, compression block, lever arm and calculated capacity.

#### References

[1] AS 3600:2018, Clause 8.1 — strain compatibility and force equilibrium.
[2] AS 3600:2018, Clause 8.1.3 — equivalent rectangular stress block.
""",
        ),
    )
    render_timing_mark("bending_page.uls_check.2.end")
    render_uls_calcbox(
        uid="bending_uls_authoritative_equilibrium",
        summary_line=(
            "Check 3 — Neutral-axis equilibrium | "
            f"Result: dn = {dn:.1f} mm, a = {block_depth:.1f} mm"
        ),
        details_md=neutral_axis_equilibrium_md,
        status=None,
        content_before=info_control(
            "Neutral-axis equilibrium",
            "Check 3 — Neutral-axis equilibrium and converged depth",
            r"""
The authoritative section solver balances concrete compression and the forces
from every reinforcement layer [1]. This check shows representative convergence
evidence and the final neutral-axis depth.

#### References

[1] AS 3600:2018, Clause 8.1 — strain compatibility and internal equilibrium.
""",
        ),
        diagram_fn=stress_block_diagram(
            "bending_uls_authoritative_equilibrium_diagram", "Neutral axis and block depth",
            show_dn=True, show_lever_arm=False,
        ),
    )
    render_uls_calcbox(
        uid="bending_uls_authoritative_4",
        summary_line=(
            "Check 5 — Internal force resultants | "
            f"Result: T = {tension_kn:.1f} kN"
        ),
        details_md=rf"""
**Purpose**

Using the final steel stresses from Check 4, calculate the internal ULS force
resultants.

**Inputs**

- Concrete stress-block factor: $\alpha_2={alpha2:.3f}$
- Equivalent stress-block depth: $a={block_depth:.1f}\,\text{{mm}}=\gamma k_ud={gamma:.3f}\times {ku:.3f}\times {d:.1f}\,\text{{mm}}$
- Concrete compressive strength: $f'_c={fc:.1f}\,\text{{MPa}}$
- Compression-zone width: $b={b:.1f}\,\text{{mm}}$
- Steel yield strength: $f_{{sy}}={fsy:.1f}\,\text{{MPa}}$
- Active longitudinal reinforcement layers: {len(stresses)}

**Concrete compression resultant**

The AS 3600 equivalent stress block applies the uniform design stress
$\alpha_2 f'_c$ over the rectangular compression-block area. No concrete
stress integration is used.

{concrete_resultant_md}

measured from the extreme compression face.

**Reinforcement force resultants**

$$F_{{s,i}}=A_{{s,i}}f_{{s,i}}$$

Using the authoritative calculation sign convention:

$$T=\sum_{{\sigma_{{s,i}}<0}}\left|A_{{s,i}}\sigma_{{s,i}}\right|$$

$$C_s=\sum_{{\sigma_{{s,i}}>0}}A_{{s,i}}\sigma_{{s,i}}$$

{steel_layer_text}

**Calculated resultants**

- Tension-steel resultant: $T={tension_kn:.3f}\,\text{{kN}}$
- Concrete compression resultant: $C_c={concrete_kn:.3f}\,\text{{kN}}$
- Compression-steel resultant: $C_s={compression_steel_kn:.3f}\,\text{{kN}}$
- Total compression: $C=C_c+C_s={concrete_kn + compression_steel_kn:.3f}\,\text{{kN}}$

**Result**

These are the final internal forces used for capacity. Neutral-axis equilibrium
was already established in Check 3; its authoritative residual was
$R={residual_kn:.6f}\,\text{{kN}}$.
""",
        status=None,
        content_before=info_control(
            "Internal force resultants", "Check 5 — Internal force resultants",
            r"""
This check shows the internal forces developed by the solved strain profile.

#### Concrete and reinforcement resultants

The AS 3600 equivalent stress block applies the uniform design stress
$\alpha_2f'_c$ across its rectangular area, so the concrete compression
resultant is $C_c=\alpha_2f'_cba$ and acts at $a/2$ from the compression face
[2]. Reinforcement forces are obtained layer by layer from steel area and the
stress calculated from that layer's compatible strain.

At equilibrium, the total compression and tension resultants balance [1]. Their
different lines of action form the internal resisting couple that provides
the section's bending capacity.

This layer-based treatment is important when compression reinforcement is
present: compression steel is included with its calculated stress and is not
incorrectly treated as yielded tension steel.

#### Why this check matters

These resultants form the internal force couple used to calculate nominal
moment capacity.

#### References

[1] AS 3600:2018, Clause 8.1 — internal force equilibrium and flexural strength.
[2] AS 3600:2018, Clause 8.1.3 — concrete compression resultant.
""",
        ),
        diagram_fn=force_diagram("bending_uls_authoritative_4_diagram", "Internal force resultants"),
    )
    render_timing_mark("bending_page.uls_check.3.end")
    render_uls_calcbox(
        uid="bending_uls_authoritative_6",
        summary_line=(
            "Check 6 — Neutral-axis ratio, ductility and strength factor | "
            f"Result: ku = {ku:.3f}, phi = {phi:.3f}, {clause_status}"
        ),
        details_md=rf"""
**Purpose**

Assess ductility using the neutral-axis ratio and report the authoritative AS 3600 strength-reduction factor.

**Inputs**

- Neutral-axis depth: $d_n={dn:.1f}\,\text{{mm}}$
- Effective depth: $d={d:.1f}\,\text{{mm}}$

**Formula**

$$k_u=\frac{{d_n}}{{d}}$$

**Substitution**

$$k_u=\frac{{{dn:.1f}}}{{{d:.1f}}}={ku:.3f}$$

The production bending calculation publishes $\phi={phi:.3f}$ together with
the applicable ductility and Clause 8.1.5 assessment. This teaching check does
not derive a separate $\phi$ rule.

**Clause 8.1.5 conditional assessment**

The additional assessment is triggered when both:

$$k_u>k_{{u,lim}}$$

$$M_u^*>0.8\phi M_u$$

- Triggered: **{"Yes" if triggered else "No"}**
- Status: **{clause_status}**
- Outstanding requirements: {failed_text}

**Result**

$k_u={ku:.3f}$, $\phi={phi:.3f}$ and the conditional assessment status is
**{clause_status}**.
""",
        status=("PASS" if clause_status == "PASS" else "FAIL" if clause_status == "FAIL" else None),
        content_before=info_control(
            "Neutral-axis ratio, ductility and strength factor",
            "Check 6 — Neutral-axis ratio, ductility and strength factor",
            r"""
The neutral-axis ratio is

$$k_u=\frac{d_n}{d}$$

where $d_n$ is the solved neutral-axis depth and $d$ is the effective depth
to the governing tensile reinforcement.

#### What the ratio means

A smaller $k_u$ generally indicates a shallower compression zone and greater
tensile-steel strain. A larger $k_u$ indicates a deeper compression zone and
reduced ductility. The calculated value therefore links equilibrium, strain
compatibility and the expected failure behaviour.

#### Strength reduction and conditional ductility

The bending strength-reduction factor $\phi$ is derived from the calculated
section behaviour under the strength-reduction provisions [1]; it is not a
fixed user-selected value.

Where Clause 8.1.5 is triggered, its additional ductility requirements [2] are
assessed in this same check. A numerical moment capacity does not override an
unsatisfied authoritative ductility requirement.

#### Why this check matters

It confirms that the capacity calculation uses the correct strength-reduction
factor and that a numerically strong but insufficiently ductile section is not
reported as compliant.

#### References

[1] AS 3600:2018, Clause 2.2.2 — strength-reduction factors.
[2] AS 3600:2018, Clause 8.1.5 — ductility and neutral-axis assessment.
""",
        ),
        diagram_fn=stress_block_diagram(
            "bending_uls_authoritative_6_diagram", "Neutral-axis ratio and lever arm",
            show_dn=True, show_lever_arm=True,
        ),
    )
    render_timing_mark("bending_page.uls_check.5.end")
    capacity_ok = capacity > 0.0 and demand <= capacity
    render_uls_calcbox(
        uid="bending_uls_authoritative_7",
        summary_line=(
            "Check 7 — Nominal and design moment capacity | "
            f"Result: Mu = {nominal:.1f} kNm, phi Mu = {capacity:.1f} kNm"
        ),
        details_md=rf"""
**Purpose**

Calculate nominal and design bending capacity from the final internal forces.

**Inputs**

- Concrete resultant position: $y_c=a/2={concrete_centroid:.3f}\,\text{{mm}}$
- Strength-reduction factor: $\phi={phi:.3f}$

**Formula**

$$M_u=\sum F_i z_i$$

Using the final steel forces from Check 5, the layer force and lever-arm terms are:

{moment_terms_md}

$$\phi M_u=\phi\,M_u$$

**Substitution**

Summing the force-times-lever-arm contributions gives:

$$M_u={nominal:.2f}\,\text{{kNm}}$$

$$\phi M_u={phi:.3f}\times {nominal:.2f}={capacity:.2f}\,\text{{kNm}}$$

**Result**

$M_u={nominal:.2f}\,\text{{kNm}}$ and
$\phi M_u={capacity:.2f}\,\text{{kNm}}$.
""",
        status=None,
        content_before=info_control(
            "Nominal and design moment capacity",
            "Check 7 — Nominal and design moment capacity",
            r"""
The balanced internal compression and tension resultants act at different
locations and form an internal force couple. Their separation is the lever
arm, and the couple produces the nominal moment capacity $M_u$.

#### Lever arm and nominal capacity

The concrete resultant acts through the centroid of the equivalent
compression block [1]. The reinforcement resultant acts through the calculated
centroid of the participating steel forces. Their separation supplies the
lever arm used in the section moment calculation.

#### Design capacity

AS 3600 applies the calculated strength-reduction factor to obtain the design
capacity $\phi M_u$ [2]. The applied design action is deliberately checked in the
next step so the capacity derivation and compliance decision remain distinct.

#### Why this check matters

This converts the verified strain and force solution into the capacity that
can be compared with the applied design action.

#### References

[1] AS 3600:2018, Clause 8.1.3 — compression resultant and equivalent stress block.
[2] AS 3600:2018, Section 2 and Clause 8.1 — design strength and ultimate flexural capacity.
""",
        ),
        diagram_fn=force_diagram("bending_uls_authoritative_7_diagram", "ULS force model and capacity"),
    )
    render_timing_mark("bending_page.uls_check.6.end")
    render_uls_calcbox(
        uid="bending_uls_authoritative_8",
        summary_line=(
            "Check 8 — Final flexural capacity check | "
            f"Result: Mu* = {demand:.1f} kNm vs phi Mu = {capacity:.1f} kNm "
            f"({'PASS' if capacity_ok else 'FAIL'})"
        ),
        details_md=rf"""
**Purpose**

Compare the applied Ultimate Limit State bending moment with the authoritative
design capacity.

**Formula**

$$M_u^*\leq\phi M_u$$

This strength comparison follows the limit-state design requirements [1] and
the flexural member provisions [2].

$$\text{{Utilisation}}=\frac{{M_u^*}}{{\phi M_u}}$$

**Substitution**

- Applied design action: $M_u^*={demand:.2f}\,\text{{kNm}}$
- Design capacity: $\phi M_u={capacity:.2f}\,\text{{kNm}}$
- Utilisation: ${utilisation_text}$

**Result**

$M_u^*={demand:.2f}\,\text{{kNm}}$ versus
$\phi M_u={capacity:.2f}\,\text{{kNm}}$: **{"PASS" if capacity_ok else "FAIL"}**.
""",
        status="PASS" if capacity_ok else "FAIL",
        content_before=info_control(
            "Final flexural capacity check",
            "Check 8 — Final flexural capacity check",
            r"""
This is the final Ultimate Limit State flexural verification. It compares the
applied design bending moment with the design capacity established in the
preceding checks:

$$M_u^*\leq\phi M_u$$

This strength comparison follows the limit-state design requirements [1] and
the flexural member provisions [2].

The comparison brings together the stress block, compatible reinforcement
stresses, force equilibrium, neutral-axis and ductility assessment, strength
reduction and internal lever arm.

A passing numerical strength comparison does not override a failed mandatory
ductility assessment recorded in Check 1.6.

#### Pass and fail meaning

- **PASS:** the authoritative design capacity is not less than the applied
  design moment and every applicable mandatory flexural check is satisfied.
- **FAIL:** the applied action exceeds capacity or an applicable mandatory
  flexural requirement remains unsatisfied.

#### References

[1] AS 3600:2018, Section 2 — design actions, design strengths and strength reduction.
[2] AS 3600:2018, Clause 8.1 — ultimate strength of members subjected to bending.
""",
        ),
        render_policy="mounted",
    )


# ============================================================
#  TAB 1 â€“ ULS (UNCHANGED LOGIC, TIDIED CALC BOXES)
# ============================================================
def render_authoritative_uls_checks(
    top_results,
    b,
    D,
    fc,
    fsy,
    Ast,
    d,
    summary_mode: bool = False,
    jump_uid: str | None = None,
    Mu_star_override: float | None = None,
    moment_sign: str = "positive",
):
    """ULS step-by-step (summary_mode parameter ignored, kept for compatibility)."""
    """
    Tab 1 â€“ ULS step-by-step.
    
    Args:
        summary_mode: If True, all steps are collapsed (expanded=False)
        jump_uid: Deprecated - kept for compatibility, not used anymore
    """
    from bending_layer_semantics import resolve_bending_faces

    phi_Mu_cap = top_results["phi_Mu_cap"]
    phi = top_results["phi"]
    moment_sign = str(moment_sign or "positive").strip().lower()
    tensile_steel_face, _, _ = resolve_bending_faces(moment_sign)

    # Apply CSS for compact collapsed steps
    apply_step_expander_css()
    render_calculation_display_control("bending_uls")
    _render_uls_overview_info()

    if top_results.get("_authoritative_uls"):
        _render_authoritative_uls_steps(
            top_results=top_results,
            b=b,
            D=D,
            fc=fc,
            fsy=fsy,
            demand=float(Mu_star_override or 0.0),
            moment_sign=moment_sign,
        )
        return

    # A zero capacity is an engineering failure result, not a reason to hide
    # the ULS calculation cards, INFO content, and diagrams that explain it.
    if d and Ast and b and fc and fsy:

        # Stress-block factors
        alpha2_raw_uls = 0.85 - 0.0015 * fc
        gamma_raw_uls = 0.97 - 0.0025 * fc
        alpha2_uls = max(0.67, alpha2_raw_uls)
        gamma_uls = max(0.67, gamma_raw_uls)

        # Pre-compute ULS internal forces / geometry once
        T = Ast * fsy  # N
        denom_uls = alpha2_uls * fc * b * gamma_uls
        dn = T / denom_uls if denom_uls > 0 else float("nan")
        a_uls = gamma_uls * dn
        z_uls = d - 0.5 * a_uls
        Mu_nom_raw_uls = T * z_uls / 1e6
        Mu_nom_uls = max(0.0, Mu_nom_raw_uls)
        phi_Mu_cap_uls = phi * Mu_nom_uls

        # Concrete force at ULS (using a = Î³ d_n)
        C_N = alpha2_uls * fc * b * a_uls  # N

        # --------------------------------------------------
        # 1.1 Concrete stress block (Î±2 and Î³)
        # --------------------------------------------------
        # Section 1.1 details
        section11_details = f"""
*Purpose: Determine the ULS rectangular stress-block factors $\\alpha_2$ and $\\gamma$ for the given concrete strength.*  

**Inputs:**  

- Concrete strength: $f'_c = {fc:.1f}$ MPa  

---

**Formula (AS 3600):**

$$
\\alpha_2 = 0.85 - 0.0015 f'_c \\; (\\ge 0.67)
$$

**Substitution:**

$$
\\alpha_2 = 0.85 - 0.0015 \\times {fc:.1f}
         = {alpha2_raw_uls:.3f}
         \\Rightarrow \\alpha_2 = {alpha2_uls:.3f}
$$

---

Similarly,

$$
\\gamma = 0.97 - 0.0025 f'_c \\; (\\ge 0.67)
$$

**Substitution:**

$$
\\gamma = 0.97 - 0.0025 \\times {fc:.1f}
       = {gamma_raw_uls:.3f}
       \\Rightarrow \\gamma = {gamma_uls:.3f}
$$

---

**Result:**  
$\\alpha_2 = {alpha2_uls:.3f}$, $\\gamma = {gamma_uls:.3f}$ (to be used in Sections 1.2â€“1.6).
"""
        
        def diagram_1_1():
            fig_uls_11 = _make_uls_stress_block_figure(
                b_mm=b or 0.0,
                D_mm=D or 0.0,
                d_mm=d,
                dn_mm=dn,
                a_mm=a_uls,
                alpha2=alpha2_uls,
                gamma=gamma_uls,
                fc=fc,
                fsy=fsy,
                show_lever_arm=False,
                show_dn=False,
                show_alpha_label=True,
                show_C=False,
                C_N=None,
                variant="11",
                moment_sign=moment_sign,
            )
            render_plotly_diagram(
                fig_uls_11,
                key="bending_uls_1_1_diagram",
                title="Concrete stress block",
                config={"displayModeBar": False},
            )

        def info_1_1():
            with _bending_check_info_row(help_text="Stress block parameters"):
                st.markdown(
                    f"""
**Check 1.1 â€” Stress Block Parameters Î±â‚‚ and Î³**

This check determines the equivalent rectangular stress block factors Î±â‚‚ and Î³ used for Ultimate Limit State flexural design.

At ultimate load, the concrete compression stress is not uniform. The real stress distribution is nonlinear, with high compression near the extreme compression face and reducing stress towards the neutral axis.

AS 3600 simplifies this nonlinear stress distribution into an equivalent rectangular stress block [1].

Î±â‚‚ adjusts the intensity, or height, of the equivalent compression stress block.

Equivalent stress = Î±â‚‚ Ã— f'c

Î³ adjusts the depth of the equivalent compression stress block.

Stress block depth, a = Î³ Ã— dn

Together, Î±â‚‚ and Î³ allow the simplified rectangular block to represent the concrete compression force used in the flexural capacity calculation [1].

References:  
[1] AS 3600:2018, Clause 8.1.3 â€” Equivalent rectangular stress block.
"""
                )

        step_expander_calcbox(
            uid="bending_uls_1_1",
            summary_line=f"Check 1 — Concrete stress block (alpha2 and gamma) | Result: alpha2 = {alpha2_uls:.3f}, gamma = {gamma_uls:.3f}",
            details_md=section11_details,
            status=None,
            diagram_fn=diagram_1_1,
            content_before=info_1_1,
        )


        # --------------------------------------------------
        # 1.4 Concrete compressive force C  (NO DIAGRAM)
        # --------------------------------------------------
        C_kN = C_N / 1000.0 if C_N is not None else float("nan")
        
        section12_details = f"""
*Purpose: Calculate the resultant concrete compressive force $C$ at ULS.*  

**Inputs:**  

- $\\alpha_2 = {alpha2_uls:.3f}$  
- $f'_c = {fc:.1f}$ MPa  
- Section width $b = {b:.1f}$ mm  
- Compression block depth $a = {a_uls:.1f}$ mm  

---

**Formula:**

$$
C = \\alpha_2 f'_c \\, b \\, a
$$

with block depth

$$
a = \\gamma d_n
$$

---

**Substitution:**

$$
C = \\alpha_2 f'_c \\, b \\, a
  = {alpha2_uls:.3f} \\times {fc:.1f} \\times {b:.1f} \\times {a_uls:.1f}
  = {C_kN:.1f}\\ \\text{{kN}}
$$

---

**Result:**  
Concrete compression resultant $C \\approx {C_kN:.1f}$ kN acting at the centroid of the compression block.
"""

        def info_1_2():
            with _bending_check_info_row(help_text="Concrete compressive force"):
                st.markdown(
                    f"""
**Check 1.4 â€” Concrete Compressive Force C**

This check calculates the resultant concrete compressive force C developed in the compression zone of the beam at Ultimate Limit State.

The force C acts over the equivalent rectangular stress block area defined using the AS 3600 rectangular stress block model [1].

C = Î±â‚‚ Ã— f'c Ã— b Ã— a

where:

Î±â‚‚ Ã— f'c = simplified average concrete compressive stress

b Ã— a = equivalent rectangular stress block area

So the equation can be understood as:

Concrete compressive force = average compressive stress Ã— stress block area

This is a simplified design model, not a literal picture of the exact stress distribution inside the concrete. The actual concrete stress distribution is nonlinear, but AS 3600 permits it to be represented using an equivalent rectangular stress block for design [1].

The concrete compression force is then balanced against the tensile force in the reinforcement to satisfy internal force equilibrium [2].

C = T

Once equilibrium is achieved, the internal force couple is used to determine the section moment capacity [2].

References:  
[1] AS 3600:2018, Clause 8.1.3 â€” Equivalent rectangular stress block.  
[2] AS 3600:2018, Clause 8.1 â€” Ultimate strength of members subjected to bending.
"""
                )
        
        # --------------------------------------------------
        # 1.2 Steel area and steel tension force T (NO DIAGRAM)
        # --------------------------------------------------
        section13_details = f"""
*Purpose: Relate the provided tensile reinforcement area to the tension force $T$ at ULS.*  

**Inputs:**  

- Tensile steel area: $A_{{st}} = {Ast:.1f}\\ \\text{{mm}}^2$  
- Steel yield strength: $f_{{sy}} = {fsy:.1f}$ MPa  

---

**Formula:**

From the section inputs, the total area of {tensile_steel_face} tensile steel is:

$$
A_{{st}} = {Ast:.1f}\\ \\text{{mm}}^2
$$

Assuming the tension steel yields at $f_{{sy}}$:

$$
T = A_{{st}} f_{{sy}}
$$

---

**Substitution:**

$$
T = {Ast:.1f} \\times {fsy:.1f}
  = {T:,.0f}\\ \\text{{N}}
  = {T/1000.0:.1f}\\ \\text{{kN}}
$$

---

**Result:**  
Tension force at ULS: $T \\approx {T/1000.0:.1f}$ kN.
"""

        def info_1_3():
            with _bending_check_info_row(help_text="Steel area and tensile force"):
                st.markdown(
                    f"""
**Check 1.2 â€” Steel Area and Tensile Force T**

This check calculates the tensile force developed by the longitudinal reinforcement at Ultimate Limit State (ULS).

As the beam bends, the concrete below the neutral axis cracks and is assumed to carry no tensile force. Instead, the entire tensile force is resisted by the reinforcing steel [1].

Provided sufficient ductility is available, AS 3600 assumes the tensile reinforcement reaches its yield strength at ultimate capacity [2]. The tensile force is therefore calculated as:

T = Ast Ã— fsy

where:

Ast = total area of tensile reinforcement

fsy = yield strength of the reinforcing steel

This equation can be understood as:

Tensile force = steel area Ã— steel yield stress

The tensile force acts through the centroid of the tensile reinforcement and forms one half of the internal force couple resisting bending. For equilibrium, the tensile force must balance the concrete compressive force [2]:

T = C

Once equilibrium is achieved, the distance between the concrete compression force and the steel tensile force forms the internal lever arm used to calculate the section's ultimate moment capacity.

References:  
[1] AS 3600:2018, Clause 8.1.1 â€” Concrete in tension neglected at Ultimate Limit State.  
[2] AS 3600:2018, Clause 8.1 â€” Ultimate strength of members subjected to bending using internal force equilibrium.
"""
                )
        
        step_expander_calcbox(
            uid="bending_uls_1_3",
            summary_line=f"Check 2 — Steel area and tension force $T$ | Result: T = {T/1000.0:.1f} kN",
            details_md=section13_details,
            status=None,
            content_before=info_1_3,
            render_policy="mounted",
        )


        # --------------------------------------------------
        # 1.3 Neutral axis depth d_n and block depth a
        # --------------------------------------------------
        section14_details = f"""
*Purpose: Determine the neutral axis depth $d_n$ and corresponding block depth $a$ from force equilibrium.*  

**Inputs:**  

- Tension force: $T = {T/1000.0:.1f}$ kN  
- $\\alpha_2 = {alpha2_uls:.3f}$, $\\gamma = {gamma_uls:.3f}$  
- $f'_c = {fc:.1f}$ MPa  
- $b = {b:.1f}$ mm  

---

**Force equilibrium:**  

Internal equilibrium requires:

$$
C = T
$$

Using the rectangular stress block:

$$
C = \\alpha_2 f'_c\\, b\\, \\gamma d_n
$$

So, setting $C = T$:

$$
\\alpha_2 f'_c\\, b\\, \\gamma d_n = T
$$

Rearranging:

$$
d_n = \\frac{{T}}{{\\alpha_2 f'_c\\, b\\, \\gamma}}
$$

---

**Substitution:**

$$
d_n =
\\frac{{{T:,.0f}}}
     {{ {alpha2_uls:.3f} \\times {fc:.1f} \\times {b:.1f} \\times {gamma_uls:.3f} }}
= {dn:.1f}\\ \\text{{mm}}
$$

Block depth:

$$
a = \\gamma d_n = {gamma_uls:.3f} \\times {dn:.1f}
  = {a_uls:.1f}\\ \\text{{mm}}
$$

---

**Result:**  
$ d_n = {dn:.1f}$ mm, $ a = {a_uls:.1f}$ mm.
"""
        
        def diagram_1_4():
            fig_uls_14 = _make_uls_stress_block_figure(
                b_mm=b or 0.0,
                D_mm=D or 0.0,
                d_mm=d,
                dn_mm=dn,
                a_mm=a_uls,
                alpha2=alpha2_uls,
                gamma=gamma_uls,
                fc=fc,
                fsy=fsy,
                show_lever_arm=True,
                show_dn=True,
                show_alpha_label=True,
                show_C=False,
                C_N=None,
                variant="13",
                moment_sign=moment_sign,
            )
            render_plotly_diagram(
                fig_uls_14,
                key="bending_uls_1_4_diagram",
                title="Neutral axis and block depth",
                config={"displayModeBar": False},
            )

        def info_1_4():
            with _bending_check_info_row(help_text="Neutral axis depth and stress-block depth"):
                st.markdown(
                    """
### Neutral Axis Depth dn and Stress-Block Depth a

This check determines the neutral axis depth, **dn**, by balancing the internal concrete compression force with the tensile force developed by the reinforcement.

At ultimate flexural capacity, the beam must satisfy internal force equilibrium:

**C = T**

where:

* **C** = resultant compressive force in the concrete
* **T** = resultant tensile force in the reinforcement

The actual concrete compression stress varies nonlinearly through the compression zone. AS 3600 represents this behaviour using an equivalent rectangular stress block with:

* an effective stress intensity of **alpha2 x f'c**
* a stress-block depth of **a = gamma x dn** [1]

The concrete compression force is therefore:

**C = alpha2 x f'c x b x a**

Substituting **a = gamma x dn** gives:

**C = alpha2 x f'c x b x gamma x dn**

Because equilibrium requires **C = T**, the neutral axis depth can be calculated from:

**dn = T / (alpha2 x f'c x b x gamma)**

Once **dn** has been determined, the corresponding rectangular stress-block depth is:

**a = gamma x dn**

### What is the neutral axis?

The neutral axis is the location through the section where the longitudinal bending strain is zero.

* Concrete above the neutral axis is in compression.
* The cracked concrete below the neutral axis is not relied upon to resist flexural tension.
* The tensile reinforcement below the neutral axis carries the tensile force.

The neutral axis depth controls the extent of the concrete compression zone and directly affects the section's strain distribution, internal lever arm and bending capacity.

### Why is the stress-block depth different from dn?

The neutral axis depth **dn** defines the full depth from the extreme compression face to the point of zero strain.

The stress-block depth **a** is the depth of the simplified rectangular compression block used to represent the actual nonlinear concrete stress distribution.

These values are related by:

**a = gamma x dn**

Because **gamma** is generally less than 1.0, the equivalent rectangular stress block does not extend all the way to the neutral axis.

### Why this check matters

Determining **dn** establishes the strain geometry and compression-zone depth of the section. It is subsequently used to:

* calculate the tensile reinforcement strain
* confirm whether the reinforcement has yielded
* calculate the neutral axis ratio **ku**
* determine the internal lever arm
* calculate the ultimate moment capacity

A deeper neutral axis generally represents a larger compression zone and lower tensile-steel strain. A shallower neutral axis generally produces greater tensile-steel strain and more ductile flexural behaviour.

### References

[1] AS 3600:2018, Clause 8.1.3 - Equivalent rectangular stress block and the parameters alpha2 and gamma.

[2] AS 3600:2018, Clause 8.1 - Ultimate strength of members subjected to bending, including strain compatibility and internal force equilibrium.
"""
                )

        step_expander_calcbox(
            uid="bending_uls_1_4",
            summary_line=f"Check 3 — Neutral axis depth $d_n$ and block depth $a$ | Result: d_n = {dn:.1f} mm, a = {a_uls:.1f} mm",
            details_md=section14_details,
            status=None,
            diagram_fn=diagram_1_4,
            content_before=info_1_4,
        )

        step_expander_calcbox(
            uid="bending_uls_1_2",
            summary_line=f"Check 4 — Concrete compressive force $C$ | Result: C = {C_kN:.1f} kN",
            details_md=section12_details,
            status=None,
            content_before=info_1_2,
            render_policy="mounted",
        )

        # --------------------------------------------------
        # 1.5 Strain compatibility (Îµcu and Îµs)
        # --------------------------------------------------
        eps_cu_uls = 0.003
        try:
            Es_card = float(get_param("Es", 200000.0) or 200000.0)
        except Exception:
            Es_card = 200000.0
        eps_sy = fsy / Es_card if Es_card > 1e-9 else float("nan")
        if dn and dn > 1e-9 and not math.isnan(dn):
            eps_s_tension = eps_cu_uls * (d - dn) / dn
        else:
            eps_s_tension = float("nan")
        eps_s_yield_ok = (
            (not math.isnan(eps_s_tension))
            and (not math.isnan(eps_sy))
            and (eps_s_tension >= eps_sy)
        )

        try:
            nb_top_14a = int(float(get_param("nb_top", 0) or 0))
        except (TypeError, ValueError):
            nb_top_14a = 0
        try:
            cover_top_14a = float(get_param("cover_top", 40.0) or 40.0)
            db_top_14a = float(get_param("db_top", 16.0) or 16.0)
        except Exception:
            cover_top_14a, db_top_14a = 40.0, 16.0
        d_prime_mm = cover_top_14a + 0.5 * db_top_14a
        show_eps_sc = (
            nb_top_14a > 0
            and moment_sign == "positive"
            and dn > 1e-9
            and d_prime_mm < dn - 1e-6
            and not math.isnan(dn)
        )
        eps_sc_comp = (
            eps_cu_uls * (dn - d_prime_mm) / dn if show_eps_sc else float("nan")
        )

        section14a_step2_extra = ""
        section14a_step3_extra = ""
        if show_eps_sc and not math.isnan(eps_sc_comp):
            section14a_step2_extra = """

At the depth $d'$ to the centroid of **compression** reinforcement (linear profile from the compression fibre to the neutral axis):

$$
\\varepsilon_{{sc}} = \\varepsilon_{{cu}} \\, \\frac{{d_n - d'}}{{d_n}}
$$
"""
            section14a_step3_extra = f"""

Compression steel strain (same triangle):

$$
\\varepsilon_{{sc}} = {eps_cu_uls:.3f} \\times \\frac{{{dn:.1f} - {d_prime_mm:.1f}}}{{{dn:.1f}}}
= {eps_sc_comp:.5f}
$$
"""

        yield_compare_md = ""
        if not math.isnan(eps_sy) and not math.isnan(eps_s_tension):
            yield_compare_md = f"""

**Yield reference (same $f_{{sy}}$ and $E_s$ as elsewhere on this page):**

$$
\\varepsilon_{{sy}} = \\frac{{f_{{sy}}}}{{E_s}}
              = \\frac{{{fsy:.1f}}}{{{Es_card:.0f}}}
              = {eps_sy:.5f}
$$

At ULS, $\\varepsilon_s = {eps_s_tension:.5f}$ so $\\varepsilon_s \\ge \\varepsilon_{{sy}}$ is **{"true (tension steel has reached or exceeded yield strain)" if eps_s_yield_ok else "false (strain below yield strain at this idealised compatibility level)"}**.
"""

        sub_tail = (
            f"= {eps_s_tension:.5f}"
            if not math.isnan(eps_s_tension)
            else "= \\text{â€”}"
        )
        result_eps_tex = (
            f"{eps_s_tension:.5f}"
            if not math.isnan(eps_s_tension)
            else r"\text{â€”}"
        )

        section14a_details = (
            f"""
*Purpose: Calculate the tensile reinforcement strain at ULS and compare it with the steel yield strain.*  

**Setup:**  

- Ultimate concrete strain: $\\varepsilon_{{cu}} = 0.003$  
- Effective depth to tensile steel centroid: $d = {d:.1f}$ mm.  
- Neutral axis depth: $d_n = {dn:.1f}$ mm.  
- Steel yield strength: $f_{{sy}} = {fsy:.1f}$ MPa.  
- Steel modulus: $E_s = {Es_card:.0f}$ MPa.  

---

**Formula (tensile steel strain):**

$$
\\varepsilon_s = \\varepsilon_{{cu}} \\, \\frac{{d - d_n}}{{d_n}}
$$
{section14a_step2_extra}
---

**Substitution:**

$$
\\varepsilon_s = {eps_cu_uls:.3f} \\times \\frac{{{d:.1f} - {dn:.1f}}}{{{dn:.1f}}}
{sub_tail}
$$
"""
            + section14a_step3_extra
            + f"""

---

**Result:**  
Tensile reinforcement strain at ULS: **$\\varepsilon_s = {result_eps_tex}$**."""
            + yield_compare_md
        )

        def info_1_5():
            with _bending_check_info_row(help_text="Strain compatibility and steel yield"):
                st.markdown(
                    """
**Strain Compatibility (Îµcu and Îµs) â€” Why This Calculation Is Required**

This check verifies that the tensile reinforcement has reached its yield strain at the Ultimate Limit State (ULS) using the strain compatibility method required by AS 3600 [1].

At ultimate capacity, AS 3600 assumes the concrete at the extreme compression fibre reaches an ultimate compressive strain of Îµcu = 0.003 [1]. It is also assumed that plane sections remain plane after bending, meaning the strain varies linearly through the depth of the section [2].

Using the neutral axis depth determined in the previous check, the strain at any point within the section can be determined from the geometry of the strain diagram. The tensile steel strain is therefore calculated as:

Îµs = Îµcu Ã— (d âˆ’ dn) / dn

where:

Îµcu = ultimate concrete compressive strain  
d = effective depth to the tensile reinforcement  
dn = neutral axis depth

The calculated steel strain is then compared with the steel yield strain:

Îµsy = fsy / Es

If:

Îµs â‰¥ Îµsy

the reinforcement has reached yield, confirming that the assumption made in the tensile force calculation,

T = Ast Ã— fsy

is valid [2].

If Îµs < Îµsy, the reinforcement has not yielded, and the tensile force must instead be determined from the actual steel stress obtained from the steel stress-strain relationship rather than assuming the full yield stress.

This check therefore confirms that the assumed stress distribution and internal force calculations are consistent with the actual strain profile of the section and that the reinforcement has developed its design yield strength before the flexural capacity is calculated.

**References**

[1] AS 3600:2018, Clause 3.1.7 â€” Ultimate concrete compressive strain (Îµcu = 0.003).  

[2] AS 3600:2018, Clause 8.1 â€” Ultimate strength of members subjected to bending using strain compatibility and internal force equilibrium.
"""
                )

        def diagram_1_5():
            ss_state = _stress_strain_state("ULS", moment_sign=moment_sign)
            fig_strain = _plot_strain_profile(
                ss_state,
                state_label="ULS",
                layout=None,
                moment_sign=moment_sign,
            )
            render_plotly_diagram(
                fig_strain,
                key=f"bending_uls_1_5_strain_diagram_{moment_sign}",
                title="Strain diagram",
                config={"displayModeBar": False},
            )

        step_expander_calcbox(
            uid="bending_uls_1_4a",
            summary_line=(
                f"Check 5 — Strain compatibility (epsilon_cu and epsilon_s) | Result: "
                f"epsilon_s = {eps_s_tension:.5f}"
                if not math.isnan(eps_s_tension)
                else "Check 5 — Strain compatibility (epsilon_cu and epsilon_s) | Result: -"
            ),
            details_md=section14a_details,
            status=None,
            diagram_fn=diagram_1_5,
            content_before=info_1_5,
        )

        # --------------------------------------------------
        # 1.6 Neutral axis ratio k_u
        # --------------------------------------------------
        ku = dn / d if d else float("nan")
        ku_lim = 0.36  # Teaching limit (AS 3600 limit for ductile design)
        ku_ok = (0.0 < ku <= ku_lim) if not math.isnan(ku) else None
        ku_status = "pass" if ku_ok is True else "fail" if ku_ok is False else None
        
        def content_1_5():
            col_ku_title, col_ku_info = st.columns([0.9, 0.1])
            with col_ku_title:
                pass
            with col_ku_info:
                with info_i_button(help_text="What does the neutral-axis ratio mean?"):
                    st.markdown(
                        r"""
### **Neutral-Axis Ratio \(k_u\) â€” Meaning & Importance**

The ratio  

\[

k_u = \frac{d_n}{d}

\]  

describes **how deep the neutral axis is** relative to the effective depth.

---

#### **1. Indicator of section behaviour**

- **Low \(k_u\)** â†’ shallow neutral axis â†’ large tension zone â†’ *steel governs* â†’ ductile.  

- **High \(k_u\)** â†’ deep neutral axis â†’ large compression zone â†’ *concrete governs* â†’ brittle.

---

#### **2. Direct link to ductility**

Because strain varies linearly:

- Low \(k_u\)** â†’ steel yields first â†’ **ductile, predictable failure**  

- High \(k_u\)** â†’ concrete crushes first â†’ **brittle failure**

---

#### **3. Why AS 3600 limits \(k_u\)**

The code caps \(k_u\) to maintain:

- warning deformation before failure  

- energy absorption  

- steel yielding rather than sudden concrete crushing  

---

#### **4. Quick performance indicator**

A single value of \(k_u\) tells you:

- the balance between steel & concrete  

- whether the beam is under- or over-reinforced  

- how reinforcement changes shift the NA

"""
                    )

        section15_details = f"""
*Purpose: Express the neutral axis depth as a non-dimensional ratio $k_u$ and check ductility limit.*  

**Inputs:**  

- Neutral axis depth: $d_n = {dn:.1f}$ mm  
- Effective depth: $d = {d:.1f}$ mm  
- Ductility limit: $k_{{u,lim}} = {ku_lim:.2f}$ (AS 3600)

---

**Formula:**

A convenient non-dimensional measure of the neutral axis depth is:

$$
k_u = \\frac{{d_n}}{{d}}
$$

**Substitution:**

$$
k_u = \\frac{{{dn:.1f}}}{{{d:.1f}}}
    = {ku:.3f}
$$

---

**Check:**  
$k_u = {ku:.3f} \\le {ku_lim:.2f}$ â†’ {"âœ“ PASS" if ku_ok else "âœ— FAIL" if ku_ok is False else "â€”"}

**Result:**  
Neutral axis ratio $k_u = {ku:.3f}$.
"""

        def info_1_6():
            with _bending_check_info_row(help_text="Neutral axis ratio and ductility"):
                st.markdown(
                    """
### Neutral Axis Ratio (ku) - Why This Calculation Is Required

This check expresses the neutral axis depth as a **non-dimensional ratio**, **ku**, and verifies that the section satisfies the ductility requirements of AS 3600 [1].

The neutral axis ratio is defined as:

**ku = dn / d**

where:

* **dn** = neutral axis depth
* **d** = effective depth to the tensile reinforcement

Rather than considering the neutral axis depth alone, expressing it as a ratio allows the behaviour of different beam sizes and reinforcement layouts to be compared on a consistent basis.

### Why is ku important?

The neutral axis ratio provides an indication of the section's strain distribution and ductility.

* A **small ku** indicates a relatively shallow compression zone and a large tensile steel strain. These sections are generally more ductile because the reinforcement yields well before the concrete reaches its crushing strain.
* A **large ku** indicates a deeper compression zone and lower tensile steel strain. As **ku** increases, the section becomes progressively less ductile and may approach a compression-controlled failure [2].

For this reason, AS 3600 limits the maximum allowable neutral axis ratio to ensure adequate ductility.

### Ductility check

The calculated neutral axis ratio is compared with the code limit:

**ku <= ku,lim**

where **ku,lim** is determined by AS 3600 based on the reinforcement properties and the assumed ultimate concrete strain [2].

If the calculated **ku** is less than or equal to **ku,lim**, the section satisfies the ductility requirements of the Standard.

If **ku** exceeds the limit, the section is considered insufficiently ductile and the design must be modified by changing the reinforcement, geometry or material properties.

### Why this check matters

The neutral axis ratio is one of the most important parameters in reinforced concrete flexural design because it links equilibrium, strain compatibility and ductility.

It confirms that:

* the tensile reinforcement is capable of developing sufficient strain before concrete crushing;
* the section satisfies the ductility requirements of AS 3600;
* the calculated flexural capacity is valid for a ductile design.

This check is therefore the final verification that the section will fail in the preferred ductile manner rather than by premature concrete compression failure.

### References

[1] AS 3600:2018, Clause 8.1 - Ultimate strength of members subjected to bending.

[2] AS 3600:2018, Clause 8.1.5 - Neutral axis parameter (ku) limits and ductility requirements.
"""
                )

        # Keep the older local callable as an alias so any cached/legacy render
        # path for this check still receives the updated 1.6 info text.
        content_1_5 = info_1_6
        
        step_expander_calcbox(
            uid="bending_uls_1_5",
            summary_line=f"Check 6 — Neutral axis ratio k_u | Result: k_u = {ku:.3f} vs k_u,lim = {ku_lim:.2f} -> {'PASS' if ku_ok else 'FAIL' if ku_ok is False else '-'}",
            details_md=section15_details,
            status=ku_status,
            content_before=info_1_6,
            render_policy="mounted",
        )


        # --------------------------------------------------
        # 1.7 Lever arm z and moment capacity (+ force model)
        # --------------------------------------------------
        section16_details = f"""
*Purpose: Compute the internal lever arm $z$, nominal moment $M_u$ and design moment $\\phi M_{{u,cap}}$.*  

**Inputs:**  

- Effective depth: $d = {d:.1f}$ mm  
- Block depth: $a = {a_uls:.1f}$ mm  
- Tension force: $T = {T:,.0f}$ N  
- Strength reduction factor: $\\phi = {phi:.2f}$  

---

**Lever arm:**  

$$
z = d - \\frac{{a}}{{2}}
$$

**Substitution:**

$$
z = d - \\frac{{a}}{{2}}
  = {d:.1f} - \\frac{{{a_uls:.1f}}}{{2}}
  = {z_uls:.1f}\\ \\text{{mm}}
$$

---

**Nominal moment:**

$$
M_u = \\frac{{T z}}{{10^6}}
$$

$$
M_u = \\frac{{{T:,.0f} \\times {z_uls:.1f}}}{{10^6}}
    = {Mu_nom_uls:.2f}\\ \\text{{kNm}}
$$

---

**Design moment:**

$$
\\phi M_{{u,cap}} = \\phi M_u
               = {phi:.2f} \\times {Mu_nom_uls:.2f}
               = {phi_Mu_cap_uls:.2f}\\ \\text{{kNm}}
$$

---

**Result:**  
Design bending capacity $\\phi M_{{u,cap}} = {phi_Mu_cap_uls:.2f}$ kNm.
"""
        
        def diagram_1_6():
            fig_uls_16 = _make_uls_force_model_figure(
                D_mm=D or 0.0,
                d_mm=d,
                a_mm=a_uls,
                C_N=C_N,
                T_N=T,
                moment_sign=moment_sign,
                dn_mm=dn,
            )
            render_plotly_diagram(
                fig_uls_16,
                key="bending_uls_1_6_diagram",
                title="Force model",
                config={"displayModeBar": False},
            )

        def info_1_7():
            with _bending_check_info_row(help_text="Lever arm and moment capacity"):
                st.markdown(
                    """
### Lever Arm (z) and Moment Capacity - Why This Calculation Is Required

This check calculates the **internal lever arm** between the concrete compression force and the tensile reinforcement force, and uses this to determine the beam's nominal and design bending capacities.

Once internal force equilibrium has been established (**C = T**), the beam resists bending by developing an internal force couple consisting of:

* the concrete compression force **C**, and
* the tensile reinforcement force **T**.

Although these forces are equal in magnitude, they act at different locations within the section. The perpendicular distance between their lines of action is called the **lever arm**, **z**.

The lever arm is calculated as:

**z = d - a / 2**

where:

* **d** = effective depth to the tensile reinforcement
* **a** = equivalent rectangular stress-block depth

The concrete compression force acts through the centroid of the equivalent rectangular stress block, located at **a/2** below the compression face [1]. The tensile force acts through the centroid of the tensile reinforcement.

### Why is the lever arm important?

The internal bending resistance of the section is generated by the force couple formed by **C** and **T**.

The moment produced by this force couple is:

**Mu = T x z**

or equivalently,

**Mu = C x z**

because **C = T**.

Increasing either the internal force or the lever arm increases the bending capacity of the section.

### Design moment capacity

AS 3600 applies a strength reduction factor, **phi**, to the nominal capacity to account for uncertainties in materials, construction tolerances and modelling assumptions [2].

The design bending capacity is therefore:

**phi Mu = phi x Mu**

This is the value that is compared with the applied design bending moment in the final flexural capacity check.

### Why this check matters

This calculation combines all of the preceding checks into the final flexural resistance of the section.

The previous checks established:

* the concrete compression block;
* the tensile reinforcement force;
* internal force equilibrium;
* the neutral axis depth;
* the strain compatibility; and
* compliance with the ductility requirements.

This check converts those internal forces into a bending moment that can be directly compared with the applied design action.

### References

[1] AS 3600:2018, Clause 8.1.3 - Equivalent rectangular stress block and location of the concrete compression resultant.

[2] AS 3600:2018, Section 2 - Design philosophy and strength reduction factors (phi), and Clause 8.1 - Ultimate strength of members subjected to bending.
"""
                )

        step_expander_calcbox(
            uid="bending_uls_1_6",
            summary_line=f"Check 7 — Lever arm z and moment capacity | Result: phi_Mu_cap = {phi_Mu_cap_uls:.2f} kNm",
            details_md=section16_details,
            status=None,
            diagram_fn=diagram_1_6,
            content_before=info_1_7,
        )


        # --------------------------------------------------
        # 1.8 Flexural capacity check (Mu* â‰¤ Ï†Mu,cap)
        # --------------------------------------------------
        Mu_star = float(Mu_star_override) if Mu_star_override is not None else get_param("Mu_star", 0.0)
        if Mu_star is not None:
            Mu_ok = Mu_star <= phi_Mu_cap_uls if phi_Mu_cap_uls > 0 else Mu_star <= 0
            Mu_status = "pass" if Mu_ok is True else "fail" if Mu_ok is False else None
            Mu_utilisation = Mu_star / max(phi_Mu_cap_uls, 1e-9) if Mu_star > 0 else 0.0
            
            section17_details = f"""
*Purpose: Verify that the design moment does not exceed the design capacity.*  

**Inputs:**  

- Design moment: $M_u^* = {Mu_star:.2f}$ kNm  
- Design capacity: $\\phi M_{{u,cap}} = {phi_Mu_cap_uls:.2f}$ kNm  

---

**Check:**  

$$
M_u^* \\le \\phi M_{{u,cap}}
$$

**Substitution:**

$$
{Mu_star:.2f} \\le {phi_Mu_cap_uls:.2f} \\quad \\Rightarrow \\quad \\text{{{"âœ“ PASS" if Mu_ok else "âœ— FAIL"}}}
$$

**Utilisation:**  
$\\text{{Utilisation}} = \\frac{{M_u^*}}{{\\max(\\phi M_{{u,cap}},10^{{-9}})}} = {Mu_utilisation:.3f}$

---

**Result:**  
{"Design moment is within capacity." if Mu_ok else "Design moment exceeds capacity â€” increase reinforcement or section size."}
"""
            
            def info_1_8():
                with _bending_check_info_row(help_text="Flexural capacity check"):
                    st.markdown(
                        """
### Flexural Capacity Check - Why This Calculation Is Required

This is the final verification of the flexural design. It compares the **applied design bending moment**, **M***, with the **design bending capacity**, **phi Mu**, calculated in the preceding checks.

AS 3600 requires the design action to be less than or equal to the design capacity for the member to satisfy the Ultimate Limit State [1].

The check is:

**M* <= phi Mu**

where:

* **M*** = applied design bending moment from the design loading
* **phi Mu** = design bending capacity of the reinforced concrete section

### Why is this comparison made?

Throughout the previous calculations, the flexural resistance of the beam has been determined by:

* establishing the concrete compression block;
* calculating the tensile reinforcement force;
* satisfying internal force equilibrium;
* verifying strain compatibility;
* confirming ductility requirements; and
* calculating the design moment capacity.

This final step compares that calculated capacity with the design demand placed on the member.

### What does the result mean?

* **PASS:** If **M* <= phi Mu**, the section has sufficient flexural capacity to resist the applied design moment in accordance with AS 3600.
* **FAIL:** If **M* > phi Mu**, the section does not have adequate flexural capacity. The design must be revised by increasing the section capacity or reducing the applied bending moment.

### Utilisation Ratio

The utilisation ratio provides a measure of how efficiently the section is being used:

**Utilisation = M* / phi Mu**

A utilisation of:

* **1.00** indicates the section is carrying its full design bending capacity.
* **Less than 1.00** indicates reserve bending capacity remains.
* **Greater than 1.00** indicates the section exceeds its design capacity and does not satisfy the Ultimate Limit State.

The utilisation ratio is also used by the optimisation routines within the Design Brain to determine whether a section is under-designed, within the target design band, or has potential for further optimisation.

### Why this check matters

This is the governing acceptance check for flexural strength. Regardless of the intermediate calculations, the beam only satisfies the Ultimate Limit State when the applied design moment does not exceed the calculated design capacity.

### References

[1] AS 3600:2018, Clause 2.2 - Design for ultimate limit states.

[2] AS 3600:2018, Clause 8.1 - Ultimate strength of members subjected to bending.
"""
                    )

            step_expander_calcbox(
                uid="bending_uls_1_7",
                summary_line=f"Check 8 — Flexural capacity check | Result: M_u* = {Mu_star:.2f} kNm vs phi_Mu_cap = {phi_Mu_cap_uls:.2f} kNm -> {'PASS' if Mu_ok else 'FAIL'}",
                details_md=section17_details,
                status=Mu_status,
                content_before=info_1_8,
                render_policy="mounted",
            )

    else:
        st.info("Capacity cannot be evaluated â€“ check geometry / reo inputs.")
