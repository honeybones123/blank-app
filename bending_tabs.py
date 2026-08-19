import math
from contextlib import contextmanager
import pandas as pd
import matplotlib.pyplot as plt
import streamlit as st

from bending_neutral_axis_teaching import neutral_axis_hand_solution

from bending_diagrams import (
    _plot_strain_profile,
    _make_uls_stress_block_figure,
    _make_uls_force_model_figure,
    _make_sls_stress_block_figure,  # still used elsewhere, untouched
)
from bending_core import _fmt, _layout_bars_in_rows, _stress_strain_state
from state_and_helpers import get_param, update_results, render_timing_mark
from ui.diagrams.stress_strain_diagram import (
    make_sls_32_stress_block_figure as _shared_make_sls_32_stress_block_figure,
    make_sls_strain_distribution_figure as _shared_make_sls_strain_distribution_figure,
)
from widgets_helpers import calcbox, clickable_calcbox, render_step, render_jumpable_step, apply_step_expander_css, step_expander_calcbox, info_i_button, render_plotly_diagram, render_pyplot_diagram


@contextmanager
def _bending_check_info_row(help_text: str):
    """Render the technical-basis button at the calc column's top right."""
    col_info_button, _col_spacer = st.columns([0.28, 0.72])
    with col_info_button:
        with info_i_button(help_text=help_text, use_container_width=True):
            yield


# ============================================================
#  LOCAL HELPER â€“ CALCBOX WITH LATEX SUPPORT
# ============================================================
# Keeping _inject_calcbox_css for backward compatibility if needed elsewhere
def _inject_calcbox_css():
    """Inject CSS for blue blockquote styling."""
    st.markdown(
        """
<style>
blockquote {
  border-left: 4px solid #1f77b4 !important;
  background-color: rgba(31, 119, 180, 0.08) !important;
  padding: 0.75rem 1rem !important;
  margin: 0.5rem 0 0.75rem 0 !important;
  border-radius: 0 6px 6px 0 !important;
  color: #1a1a1a !important;
}
blockquote p, blockquote * { color: #1a1a1a !important; }
</style>
""",
        unsafe_allow_html=True,
    )




# ============================================================
#  LOCAL HELPER â€“ SLS STRESS FIGURE FOR 3.2 ONLY
# ============================================================
def _make_sls_stress_block_figure_32(D_mm, d_mm, dn_mm, layers_tension):
    """Compatibility wrapper for the shared SLS 3.2 stress-block figure."""
    return _shared_make_sls_32_stress_block_figure(D_mm, d_mm, dn_mm, layers_tension)


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
    layer_compatibility_sections = []
    stress_summary_parts = []
    final_layer_table_lines = [
        "| Layer | $A_{s,i}$ (mm²) | $y_i$ (mm) | Relative to NA | $\\varepsilon_{s,i}$ | $f_{s,i}$ (MPa) | State | $F_{s,i}$ (kN) |",
        "|---|---:|---:|---|---:|---:|---|---:|",
    ]
    for index, (area, depth, stress, force) in enumerate(
        zip(layer_areas, steel_depths, stresses, layer_forces), start=1
    ):
        face = layer_faces[index - 1] if index <= len(layer_faces) else "steel"
        label = layer_labels[index - 1] if index <= len(layer_labels) else f"{face.title()} reinforcement"
        role = "tension" if stress < 0.0 else "compression" if stress > 0.0 else "approximately zero stress"
        displayed_force = abs(force) / 1000.0 if role == "tension" else force / 1000.0
        strain = -0.003 * (depth - dn) / dn if abs(dn) > 1e-9 else float("nan")
        yielded = math.isfinite(eps_sy) and abs(strain) >= eps_sy
        if moment_sign == "negative":
            relative_position = "above neutral axis" if depth > dn else "below neutral axis" if depth < dn else "at neutral axis"
        else:
            relative_position = "below neutral axis" if depth > dn else "above neutral axis" if depth < dn else "at neutral axis"
        force_label = "Tension force" if role == "tension" else "Compression force"
        state_label = f"{'Yielded' if yielded else 'Elastic'} {role}"
        relative_to_na = "Below NA" if depth > dn else "Above NA" if depth < dn else "At NA"
        stress_summary_parts.append(f"{label}: {stress:.1f} MPa")
        steel_layer_lines.append(
            f"- {label} ({role}): $A_{{s,{index}}}={area:.1f}\\,\\text{{mm}}^2$, "
            f"$\\sigma_{{s,{index}}}={stress:.1f}\\,\\text{{MPa}}$, "
            f"$F_{{s,{index}}}={displayed_force:.3f}\\,\\text{{kN}}$"
        )
        layer_compatibility_sections.append(rf"""
**{label}**

- Steel area: $A_{{s,{index}}}={area:.2f}\,\text{{mm}}^2$
- Centroid depth: $y_{{{index}}}={depth:.1f}\,\text{{mm}}$
- Position: {relative_position}

$$\varepsilon_{{s,{index}}}=-0.003\frac{{{depth:.1f}-{dn:.3f}}}{{{dn:.3f}}}={strain:.6f}$$

$$\sigma_{{s,{index}}}=\operatorname{{sign}}(\varepsilon_{{s,{index}}})\min\left(E_s|\varepsilon_{{s,{index}}}|,f_{{sy}}\right)={stress:.1f}\,\text{{MPa}}$$

- Stress state: {role}
- Yield status: {"yielded" if yielded else "elastic"}
- {force_label}: ${displayed_force:.3f}\,\text{{kN}}$
""")
        final_layer_table_lines.append(
            f"| {label} | {area:.2f} | {depth:.1f} | {relative_to_na} | {strain:.6f} | "
            f"{stress:.1f} | {state_label} | {force / 1000.0:.3f} |"
        )
    steel_layer_text = "\n".join(steel_layer_lines) or "- Layer areas and forces were not published."
    layer_compatibility_text = "\n".join(layer_compatibility_sections)
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

Determine the method required to find the neutral-axis depth $d_n$ that satisfies:

$$\boxed{{\sum C=\sum T}}$$

**Inputs and symbol meanings**

- $b={b:.1f}\,\text{{mm}}$: beam width; $f'_c={fc:.1f}\,\text{{MPa}}$: concrete strength.
- $\alpha_2={alpha2:.3f}$ and $\gamma={gamma:.3f}$: rectangular stress-block factors.
- $E_s={Es_uls:.0f}\,\text{{MPa}}$; $f_{{sy}}={fsy:.1f}\,\text{{MPa}}$.
- $\varepsilon_{{cu}}=0.003$; $\varepsilon_{{sy}}=f_{{sy}}/E_s={eps_sy:.6f}$.
- $A_{{s,1}}={layer_areas[0]:.2f}\,\text{{mm}}^2$ and $y_1={steel_depths[0]:.1f}\,\text{{mm}}$.
- $d_n$: neutral-axis depth; $a=\gamma d_n$: equivalent stress-block depth.

**Concrete compression relationship**

$$C_c=\alpha_2f'_cba=\alpha_2f'_cb\gamma d_n$$

The concrete compression force increases directly with neutral-axis depth.

**Direct single-layer solution**

One longitudinal reinforcement layer is present. For a yielded tension layer:

$$T=A_{{st}}f_{{sy}}$$

$$\boxed{{d_n=\frac{{A_{{st}}f_{{sy}}}}{{\alpha_2f'_cb\gamma}}}}$$

The neutral-axis depth can therefore be obtained directly from force equilibrium.
The strain state and ductility are verified in the following checks.
"""
    else:
        neutral_axis_method_md = rf"""
**Purpose**

Determine the method required to find the neutral-axis depth $d_n$ that satisfies:

$$\boxed{{\sum C=\sum T}}$$

**Inputs and symbol meanings**

- $b={b:.1f}\,\text{{mm}}$: beam width; $f'_c={fc:.1f}\,\text{{MPa}}$: concrete strength.
- $\alpha_2={alpha2:.3f}$ and $\gamma={gamma:.3f}$: rectangular stress-block factors.
- $E_s={Es_uls:.0f}\,\text{{MPa}}$; $f_{{sy}}={fsy:.1f}\,\text{{MPa}}$.
- $\varepsilon_{{cu}}=0.003$; $\varepsilon_{{sy}}=f_{{sy}}/E_s={eps_sy:.6f}$.
- $d_n$: neutral-axis depth; $a=\gamma d_n$: equivalent stress-block depth.

**Concrete compression relationship**

$$C_c=\alpha_2f'_cba=\alpha_2f'_cb\gamma d_n$$

The concrete compression force increases directly with neutral-axis depth.

**General multi-layer solution**

With multiple reinforcement layers, the force in every layer depends on its
strain relative to the unknown neutral axis. The steel forces therefore cannot
all be known before $d_n$ is known.

{geometry_table_md}

For every layer:

$$\varepsilon_{{s,i}}=\varepsilon_{{cu}}\frac{{y_i-d_n}}{{d_n}}$$

$$f_{{s,i}}=\operatorname{{clip}}\left(E_s\varepsilon_{{s,i}},-f_{{sy}},f_{{sy}}\right)$$

$$F_{{s,i}}=A_{{s,i}}f_{{s,i}}$$

**“Top” and “bottom” describe physical location only. They do not determine
whether a layer is in tension or compression.** With compression at the top face:

$$\boxed{{y_i>d_n\Rightarrow\text{{tension side}}}}$$

$$\boxed{{y_i<d_n\Rightarrow\text{{compression side}}}}$$

Because $d_n$ is not yet known, the final state of an additional layer is not
known in advance.

**Hand-calculation process**

1. Assume a trial $d_n$.
2. Calculate $C_c=\alpha_2f'_cb\gamma d_n$.
3. Calculate strain, clipped stress and force in every reinforcement layer.
4. Compare total compression with total tension.
5. Adjust $d_n$ and repeat until $\boxed{{\sum C\approx\sum T}}$.

$$d_n\rightarrow\text{{steel strains}}\rightarrow\text{{steel stresses}}\rightarrow\text{{steel forces}}\rightarrow R(d_n)\rightarrow\text{{updated }}d_n$$

$$R(d_n)=\sum C-\sum T$$

**The app performs this repeated neutral-axis search automatically, so the user
does not need to keep guessing $d_n$ manually.** The section now proceeds to the
equilibrium check and converged depth.
"""
    neutral_axis_equilibrium_md = rf"""
**Purpose**

Solve the section equilibrium and confirm the neutral-axis depth at which total
compression and total tension balance.

**Authoritative equilibrium iterations**

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

**Layer position after convergence**

{relative_to_na_md}

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

**Authoritative equilibrium iterations**

The app performs the trial-and-update process automatically:

$$d_n\rightarrow\text{{steel strains}}\rightarrow\text{{steel stresses}}\rightarrow\text{{steel forces}}\rightarrow R(d_n)\rightarrow\text{{updated }}d_n$$

{iteration_table_md}

When tension exceeds compression, $d_n$ generally increases; when compression
exceeds tension, $d_n$ generally decreases. The table shows representative
iterations from the authoritative bisection solve, followed by the converged result.

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

**Hand derivation verification**

- Hand-equation result: $d_n={hand_dn:.6f}\,\text{{mm}}$.
- Authoritative production result: $d_n={dn:.6f}\,\text{{mm}}$.
- Difference: ${hand_difference:.9f}\,\text{{mm}}$.
- **Hand derivation verified against authoritative solver — PASS.**

**Authoritative solver verification**

The production section analysis remains the sole source of engineering truth.
It independently solves the actual residual using its existing bracketed
bisection method:

$$R(d_n)=C_c(d_n)+\sum_iF_{{s,i}}(d_n)$$

$$R({dn:.6f})={residual_kn:.9f}\,\text{{kN}}\approx0$$

**Result**

$d_n={dn:.3f}\,\text{{mm}}$ and $a={block_depth:.3f}\,\text{{mm}}$.
The displayed polynomial residual at the authoritative root is
${na_teaching['polynomial_at_dn'] / 1000.0:.6e}\,\text{{kN}}\cdot\text{{mm}}$.

**Force equilibrium is satisfied. The final strain, stress and force in each reinforcement layer are evaluated in Check 3.**
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

**Authoritative solver verification**

The production solver brackets $d_n$ and uses bisection on the actual section residual:

$$R(d_n)=C_c(d_n)+\sum_i F_{{s,i}}(d_n)=0$$

Each trial uses the authoritative section geometry, compatible layer stresses,
yield limits and displaced-concrete correction. No separate teaching solver is used.

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

    def stress_block_diagram(key: str, title: str, *, show_dn: bool, show_lever_arm: bool):
        def render_diagram():
            fig = _make_uls_stress_block_figure(
                b_mm=b, D_mm=D, d_mm=d, dn_mm=dn, a_mm=block_depth,
                alpha2=alpha2, gamma=gamma, fc=fc, fsy=fsy,
                show_lever_arm=show_lever_arm, show_dn=show_dn,
                show_alpha_label=True, show_C=False, C_N=None,
                variant="13" if show_dn else "11", moment_sign=moment_sign,
            )
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

    def strain_diagram():
        state = _stress_strain_state("ULS", moment_sign=moment_sign)
        fig = _plot_strain_profile(state, state_label="ULS", layout=None, moment_sign=moment_sign)
        render_plotly_diagram(
            fig, key=f"bending_uls_authoritative_strain_{moment_sign}",
            title="ULS strain compatibility", config={"displayModeBar": False},
        )

    step_expander_calcbox(
        uid="bending_uls_authoritative_1",
        summary_line=(
            "Check 1 — Stress-block parameters | "
            f"Concrete stress block | alpha2 = {alpha2:.3f}, gamma = {gamma:.3f}"
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
            "Stress-block parameters", "Check 1 — Stress-block parameters",
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
            "bending_uls_authoritative_1_diagram", "Stress-block parameters",
            show_dn=False, show_lever_arm=False,
        ),
    )
    render_check_4 = lambda: step_expander_calcbox(
        uid="bending_uls_authoritative_strains",
        summary_line=(
            "Check 4 — Reinforcement strains and stresses | "
            f"Result: {identified_stress_text}"
        ),
        details_md=rf"""
**Purpose**

Using the converged neutral-axis depth from Check 3, calculate the final strain,
stress and force in every reinforcement layer. This explains what each layer is
actually doing at ULS.

**Inputs**

- Section: $b={b:.1f}\,\text{{mm}}$, $D={D:.1f}\,\text{{mm}}$
- Authoritative neutral-axis depth: $d_n={dn:.3f}\,\text{{mm}}$
- Ultimate concrete strain: $\varepsilon_{{cu}}=0.003$
- Steel yield strength: $f_{{sy}}={fsy:.1f}\,\text{{MPa}}$
- Steel elastic modulus: $E_s={Es_uls:.0f}\,\text{{MPa}}$

**Strain compatibility**

**Step 1 — locate each layer relative to the neutral axis**

For this top-face compression convention, $y_i>d_n$ means the layer is below
the neutral axis and in tension; $y_i<d_n$ means it is above the neutral axis
and in compression. “Top” and “bottom” are physical labels only.

**Step 2 — calculate steel strain**

Negative strain and stress represent tension. For every active layer:

$$\varepsilon_{{s,i}}=-\varepsilon_{{cu}}\frac{{y_i-d_n}}{{d_n}}$$

$$\varepsilon_{{sy}}=\frac{{f_{{sy}}}}{{E_s}}=\frac{{{fsy:.1f}}}{{{Es_uls:.0f}}}={eps_sy:.6f}$$

**Step 3 — calculate steel stress**

$$\sigma_{{s,i}}=\operatorname{{sign}}(\varepsilon_{{s,i}})\min\left(E_s|\varepsilon_{{s,i}}|,f_{{sy}}\right)$$

**Step 4 — calculate the force in each layer**

$$F_{{s,i}}=A_{{s,i}}f_{{s,i}}$$

Layers are classified from their calculated position and stress, not from the
words “top” or “bottom” in their names.

{layer_compatibility_text}

**Final reinforcement table**

{final_layer_table_md}

The converged neutral axis determines every reinforcement layer’s strain state.
Reinforcement labelled “top” or “bottom” is not automatically compression or
tension steel; its stress state depends on its position relative to the neutral axis.

$$\boxed{{T_{{\mathrm{{total}}}}=\sum F_{{s,\mathrm{{tension}}}}={tension_n / 1000.0:.3f}\,\text{{kN}}}}$$

$$\boxed{{C_{{s,\mathrm{{total}}}}=\sum F_{{s,\mathrm{{compression}}}}={compression_steel_n / 1000.0:.3f}\,\text{{kN}}}}$$

**Result:** {identified_stress_text}
""",
        status=None,
        content_before=info_control(
            "Reinforcement strains and stresses", "Check 4 — Reinforcement strains and stresses",
            r"""
This check establishes the linear strain profile and calculates the strain
and stress in every reinforcement layer.

#### Strain assumptions

Plane sections are assumed to remain plane [1], so strain varies linearly from
the extreme compression fibre to each reinforcement layer. Each layer's
strain is converted to stress using the steel stress–strain relationship;
the analysis does not assume that every layer has yielded.

This confirms whether each layer is elastic, yielded in tension or acting in
compression before its force is used in equilibrium [1]. Compression steel is
therefore not incorrectly treated as yielded tension steel.

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
        diagram_fn=strain_diagram,
    )
    render_timing_mark("bending_page.uls_check.1.end")
    step_expander_calcbox(
        uid="bending_uls_authoritative_method",
        summary_line=(
            "Check 2 — Neutral-axis solution method | "
            + ("Direct single-layer solution" if len(layer_areas) == 1 else "General multi-layer equilibrium solution")
        ),
        details_md=neutral_axis_method_md,
        status=None,
        diagram_fn=stress_block_diagram(
            "bending_uls_authoritative_method_diagram", "Concrete stress block",
            show_dn=False, show_lever_arm=False,
        ),
        content_before=info_control(
            "Neutral-axis solution method",
            "Check 2 — Neutral-axis solution method",
            r"""
The neutral axis is the position through the section where longitudinal
bending strain is zero. Concrete on the compression side and reinforcement
on both sides of this position contribute compatible internal forces.

#### How it is found

The authoritative solver moves the neutral axis until total compression and
tension balance [1]. The resulting depth controls the compression zone,
reinforcement strains, ductility and internal lever arm.

The stress-block depth $a$ differs from $d_n$ because it represents the
equivalent rectangular compression block [2]:

$$a=\gamma d_n$$

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
    step_expander_calcbox(
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
    render_check_4()
    step_expander_calcbox(
        uid="bending_uls_authoritative_4",
        summary_line=(
            "Check 5 — Internal force resultants | "
            f"Result: T = {tension_kn:.1f} kN"
        ),
        details_md=rf"""
**Purpose**

Calculate the internal ULS force resultants using the AS 3600 equivalent rectangular concrete stress block and the calculated reinforcement stresses.

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

$$F_{{s,i}}=A_{{s,i}}\sigma_{{s,i}}$$

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
    step_expander_calcbox(
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
    step_expander_calcbox(
        uid="bending_uls_authoritative_7",
        summary_line=(
            "Check 7 — Nominal and design moment capacity | "
            f"Result: Mu = {nominal:.1f} kNm, phi Mu = {capacity:.1f} kNm"
        ),
        details_md=rf"""
**Purpose**

Calculate nominal and design bending capacity from the authoritative
internal-force solution.

**Inputs**

- Concrete resultant position: $y_c=a/2={concrete_centroid:.3f}\,\text{{mm}}$
- Strength-reduction factor: $\phi={phi:.3f}$

**Formula**

$$M_u=\sum F_i z_i$$

Using the final steel forces from Check 5, the authoritative layer force and
lever-arm terms are:

{moment_terms_md}

$$\phi M_u=\phi\,M_u$$

**Substitution**

The authoritative internal-force model gives:

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
    step_expander_calcbox(
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
def render_uls_tab(
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
        # 1.1 Stress-block parameters (Î±2 and Î³)
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
                title="Stress-block parameters",
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
            summary_line=f"Check 1 — Stress-block parameters (alpha2 and gamma) | Result: alpha2 = {alpha2_uls:.3f}, gamma = {gamma_uls:.3f}",
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


# ============================================================
#  TAB 2 â€“ Minimum Strength (UNCHANGED LOGIC, TIDIED TEXT)
# ============================================================
def render_min_strength_tab(top_results, b, D, fc, fsy, Ast, summary_mode: bool = False, jump_uid: str | None = None):
    """Minimum strength requirements (summary_mode parameter ignored, kept for compatibility)."""
    """
    Tab 2 â€“ Minimum strength requirements.
    
    Args:
        summary_mode: If True, all steps are collapsed (expanded=False)
        jump_uid: Deprecated - kept for compatibility, not used anymore
    """
    fctf = top_results["fctf"]
    Z_gross = top_results["Z_gross"]
    Mcr = top_results["Mcr"]
    As_min = top_results["As_min"]

    fctf_as = fctf
    Zg = Z_gross
    Mcr_as = Mcr
    Mu_min_as = (
        1.2 * Mcr_as
        if Mcr_as is not None and not math.isnan(Mcr_as)
        else float("nan")
    )
    Ast_min_as = As_min

    # Apply CSS for compact collapsed steps
    apply_step_expander_css()

    # 2.1 f_ct,f
    section21_details = f"""
*Purpose: Estimate the concrete flexural tensile strength $f_{{ct,f}}$.*  

**Inputs:**  

- $f'_c = {fc:.1f}$ MPa  

---

**Formula (AS 3600 style):**

$$
f_{{ct,f}} \\approx 0.6 \\sqrt{{f'_c}}
$$

**Substitution:**

$$
f_{{ct,f}} \\approx 0.6 \\sqrt{{{fc:.1f}}}
          = {fctf_as:.3f}\\ \\text{{MPa}}
$$

---

**Result:**  
$f_{{ct,f}} \\approx {fctf_as:.3f}$ MPa.
"""
    
    step_expander_calcbox(
        uid="bending_min_2_1",
        summary_line=f"Check 1 — Concrete flexural tensile strength $f_{{ct,f}}$ | Result: f_{{ct,f}} = {fctf_as:.3f} MPa",
        details_md=section21_details,
        status=None,
        render_policy="mounted",
    )

    # 2.2 Z_g
    section22_details = f"""
*Purpose: Calculate the gross section modulus $Z_g$ of the rectangular section.*  

**Inputs:**  

- Width $b = {b:.1f}$ mm  
- Overall depth $D = {D:.1f}$ mm  

---

**Formula:**

$$
Z_g = \\frac{{b D^2}}{{6}}
$$

**Substitution:**

$$
Z_g = \\frac{{{b:.1f} \\times {D:.1f}^2}}{{6}}
    = {Zg:,.3e}\\ \\text{{mm}}^3
$$

---

**Result:**  
$Z_g = {Zg:,.3e}\\ \\text{{mm}}^3$.
"""
    
    step_expander_calcbox(
        uid="bending_min_2_2",
        summary_line=f"Check 2 — Gross section modulus Z_g | Result: Z_g = {Zg:,.3e} mm^3",
        details_md=section22_details,
        status=None,
        render_policy="mounted",
    )

    # 2.3 M_cr
    section23_details = f"""
*Purpose: Determine the cracking moment $M_{{cr}}$ for the section.*  

**Inputs:**  

- $f_{{ct,f}} = {fctf_as:.3f}$ MPa  
- $Z_g = {Zg:,.3e}\\ \\text{{mm}}^3$  

---

**Formula:**

$$
M_{{cr}} = \\frac{{f_{{ct,f}} Z_g}}{{10^6}}
$$

**Substitution:**

$$
M_{{cr}} = \\frac{{{fctf_as:.3f} \\times {Zg:,.3e}}}{{10^6}}
       = {Mcr_as:.2f}\\ \\text{{kNm}}
$$

---

**Result:**  
$M_{{cr}} \\approx {Mcr_as:.2f}$ kNm.
"""
    
    step_expander_calcbox(
        uid="bending_min_2_3",
        summary_line=f"Check 3 — Cracking moment $M_{{cr}}$ | Result: M_{{cr}} = {Mcr_as:.2f} kNm",
        details_md=section23_details,
        status=None,
        render_policy="mounted",
    )

    # 2.4 Minimum required capacity (1.2 Mcr) - PASS/FAIL
    phi_Mu_cap = top_results.get("phi_Mu_cap", 0.0)
    Mu_min_ok = phi_Mu_cap >= Mu_min_as if (phi_Mu_cap > 0 and Mu_min_as > 0) else None
    Mu_min_status = "pass" if Mu_min_ok is True else "fail" if Mu_min_ok is False else None
    
    section24_details = f"""
*Purpose: Check the minimum required design capacity relative to cracking moment.*  

**Inputs:**  

- $M_{{cr}} = {Mcr_as:.2f}$ kNm  
- $\\phi M_{{u,cap}} = {phi_Mu_cap:.2f}$ kNm

---

**Formula:**

$$
(M_{{u,cap}})_{{min}} = 1.2\\, M_{{cr}}
$$

**Substitution:**

$$
(M_{{u,cap}})_{{min}}
= 1.2 \\times {Mcr_as:.2f}
= {Mu_min_as:.2f}\\ \\text{{kNm}}
$$

---

**Check:**  
$\\phi M_{{u,cap}} = {phi_Mu_cap:.2f} \\ge {Mu_min_as:.2f} = (M_{{u,cap}})_{{min}}$ â†’ {"âœ“ PASS" if Mu_min_ok else "âœ— FAIL" if Mu_min_ok is False else "â€”"}

**Result:**  
Minimum required design capacity $(M_{{u,cap}})_{{min}} = {Mu_min_as:.2f}$ kNm.
"""
    
    step_expander_calcbox(
        uid="bending_min_2_4",
        summary_line=f"Check 4 — Minimum required design capacity (M_u,cap)_min | Result: phi_Mu_cap = {phi_Mu_cap:.2f} kNm vs (M_u,cap)_min = {Mu_min_as:.2f} kNm -> {'PASS' if Mu_min_ok else 'FAIL' if Mu_min_ok is False else '-'}",
        details_md=section24_details,
        status=Mu_min_status,
        render_policy="mounted",
    )

    # 2.5 Minimum tensile reinforcement - PASS/FAIL
    As_ok = Ast >= Ast_min_as if (Ast is not None and Ast_min_as is not None and not math.isnan(Ast_min_as)) else None
    As_status = "pass" if As_ok is True else "fail" if As_ok is False else None
    
    section25_details = f"""
*Purpose: Calculate minimum tensile reinforcement according to AS 3600 style rules and check provided area.*  

**Inputs:**  

- $f_{{ct,f}} = {fctf_as:.3f}$ MPa  
- $f_{{sy}} = {fsy:.1f}$ MPa  
- $b = {b:.1f}$ mm  
- Effective depth $d = {top_results['d']:.1f}$ mm  
- Provided area: $A_{{st}} = {Ast:.1f}$ mm^2

---

**Formula:**

$$
A_{{st,min}}
= 0.4\\;\\frac{{f_{{ct,f}}}}{{f_{{sy}}}}\\; b d
$$

**Substitution:**

$$
A_{{st,min}}
= 0.4 \\times \\frac{{{fctf_as:.3f}}}{{{fsy:.1f}}}
\\times {b:.1f} \\times {top_results['d']:.1f}
= {Ast_min_as:.1f}\\ \\text{{mm}}^2
$$

---

**Check:**  
$A_{{st}} = {Ast:.1f} \\ge {Ast_min_as:.1f} = A_{{st,min}}$ â†’ {"âœ“ PASS" if As_ok else "âœ— FAIL" if As_ok is False else "â€”"}

**Result:**  
Minimum tensile steel area $A_{{st,min}} = {Ast_min_as:.1f}$ mm^2.
"""
    
    step_expander_calcbox(
        uid="bending_min_2_5",
        summary_line=f"Check 5 — Minimum tensile reinforcement A_st,min | Result: A_st = {Ast:.1f} mm^2 vs A_st,min = {Ast_min_as:.1f} mm^2 -> {'PASS' if As_ok else 'FAIL' if As_ok is False else '-'}",
        details_md=section25_details,
        status=As_status,
        render_policy="mounted",
    )


# ============================================================
#  TAB 3 â€“ SLS (UPDATED WITH LAYERS + COMP STEEL)
# ============================================================
def render_sls_tab(
    top_results,
    b,
    D,
    d,
    Ast,
    Ec,
    Es,
    Mu_star,
    summary_mode: bool = False,
    jump_uid: str | None = None,
    moment_sign: str = "positive",
):
    """SLS cracked-section (summary_mode parameter ignored, kept for compatibility)."""
    """
    Tab 3 â€“ SLS cracked-section teaching model.
    
    Args:
        summary_mode: If True, all steps are collapsed (expanded=False)
        jump_uid: Deprecated - kept for compatibility, not used anymore

    IMPORTANT:
    - For BENDING capacity we can combine bottom bars to one layer.
    - For CRACK CONTROL (AS 3600) we want stresses in EACH steel layer,
      and the OUTERMOST tension layer controls f_s,ser.

    Here we:
      * Build one layer for each bottom bar ROW (T1, T2, ...)
      * Optionally one compression layer for top bars (C1)
    """
    # Force unique chart key each run (kills any stale/cached render)
    st.session_state["_diag_nonce"] = st.session_state.get("_diag_nonce", 0) + 1
    
    # Apply CSS for compact collapsed steps
    apply_step_expander_css()

    from bending_layer_semantics import resolve_bending_faces
    from state_and_helpers import get_param

    moment_sign = str(moment_sign or "positive").strip().lower()
    _, _, hogging_sls = resolve_bending_faces(moment_sign)
    try:
        st.session_state["bending_sls_hogging"] = bool(hogging_sls)
    except Exception:
        pass

    Ms_service = float(get_param("bending_sls_Ms_used", get_param("sls_Mstar", 0.0)) or 0.0)
    if not (d and Ast and Ec and Es and b and D and Ms_service is not None):
        st.info("Not enough information to run SLS cracked-section example.")
        return

    Ms = Ms_service  # service moment (kNm)

    # --------------------------------------------------
    #  Read bar layout info from session_state
    # --------------------------------------------------
    nb_bot = st.session_state.get("nb_bot", 0) or 0
    db_bot = st.session_state.get("db_bot", 0.0) or 0.0
    cover_bot = st.session_state.get("cover_bot", 0.0) or 0.0
    rowgap_bot = st.session_state.get("rowgap_bot", 0.0) or 0.0

    nb_top = st.session_state.get("nb_top", 0) or 0
    db_top = st.session_state.get("db_top", 0.0) or 0.0
    cover_top = st.session_state.get("cover_top", 0.0) or 0.0
    rowgap_top = float(st.session_state.get("rowgap_top", 0.0) or 0.0)

    # --------------------------------------------------
    #  Build STEEL LAYERS
    # --------------------------------------------------
    layers_tension: list[dict] = []

    # --- Hogging: top tension layers ---
    if hogging_sls and nb_top > 0 and db_top > 0 and cover_top > 0:
        min_spacing_top = 2 * db_top
        layout_top = _layout_bars_in_rows(
            nb_top, b, cover_top, db_top, min_spacing_top, 3
        )
        row_counts_top: dict[int, int] = {}
        for _, row_idx in layout_top:
            row_counts_top[row_idx] = row_counts_top.get(row_idx, 0) + 1
        As_bar_top = math.pi * db_top**2 / 4.0
        r_top = db_top / 2.0
        y_row0_top = cover_top + r_top
        for row_idx in sorted(row_counts_top.keys()):
            n_row = row_counts_top[row_idx]
            if n_row <= 0:
                continue
            As_row = n_row * As_bar_top
            y_row = y_row0_top + row_idx * (db_top + rowgap_top)
            layers_tension.append(
                {
                    "name": f"T{row_idx + 1}",
                    "label": f"Top tension steel (row {row_idx + 1})",
                    "y": y_row,
                    "As": As_row,
                }
            )

    # --- Bottom tension layers (T1, T2, ...) â€” sagging ---
    if (not hogging_sls) and nb_bot > 0 and db_bot > 0 and cover_bot > 0:
        # Same helper as section diagram â†’ rows of bars
        min_spacing_bot = 2 * db_bot
        layout_bot = _layout_bars_in_rows(
            nb_bot, b, cover_bot, db_bot, min_spacing_bot, 3
        )

        # Count bars per row index
        row_counts: dict[int, int] = {}
        for _, row_idx in layout_bot:
            row_counts[row_idx] = row_counts.get(row_idx, 0) + 1

        As_bar_bot = math.pi * db_bot**2 / 4.0
        r_bot = db_bot / 2.0
        y_row0 = D - cover_bot - r_bot  # outermost row depth from top

        for row_idx in sorted(row_counts.keys()):
            n_row = row_counts[row_idx]
            if n_row <= 0:
                continue
            As_row = n_row * As_bar_bot
            y_row = y_row0 - row_idx * (db_bot + rowgap_bot)
            layers_tension.append(
                {
                    "name": f"T{row_idx + 1}",
                    "label": f"Bottom tension steel (row {row_idx + 1})",
                    "y": y_row,
                    "As": As_row,
                }
            )

    # Fallback: if something is missing, use a single equivalent layer
    if not layers_tension:
        layers_tension = [
            {
                "name": "T1",
                "label": (
                    "Top tension steel"
                    if hogging_sls
                    else "Bottom tension steel"
                ),
                "y": d,
                "As": Ast,
            }
        ]

    # --- Compression layer on opposite face (optional) ---
    if hogging_sls:
        As_bot_comp = (
            nb_bot * math.pi * db_bot**2 / 4.0 if nb_bot and db_bot else 0.0
        )
        y_bot_comp = (
            D - cover_bot - db_bot / 2.0 if db_bot and cover_bot else 0.0
        )
        comp_layer = (
            {
                "name": "C1",
                "label": "Bottom steel (compression layer)",
                "y": y_bot_comp,
                "As": As_bot_comp,
            }
            if As_bot_comp > 0 and 0.0 < y_bot_comp < D
            else None
        )
    else:
        As_top = (
            nb_top * math.pi * db_top**2 / 4.0 if nb_top and db_top else 0.0
        )
        y_top = cover_top + db_top / 2.0 if db_top else 0.0
        comp_layer = (
            {
                "name": "C1",
                "label": "Top steel (compression layer)",
                "y": y_top,
                "As": As_top,
            }
            if As_top > 0 and 0.0 < y_top < D
            else None
        )

    include_comp = st.checkbox(
        "Include compression steel in cracked-section analysis",
        value=False,
        key="sls_include_comp",
    )

    # Modular ratio
    n_sls = Es / Ec if Ec else 0.0

    # --------------------------------------------------
    # 3.1 Modular ratio & transformed steel areas
    # --------------------------------------------------
    def content_3_1():
        col_n_title, col_n_info = st.columns([0.9, 0.1])
        with col_n_title:
            pass
        with col_n_info:
            with info_i_button(help_text="What does the modular ratio mean?"):
                st.markdown(
                    r"""
### **Modular Ratio \(n = E_s / E_c\) â€” What it Means**

The modular ratio

\[
n = \frac{E_s}{E_c}
\]

compares **steel stiffness** to **concrete stiffness**.

---

#### 1. Converts steel into 'equivalent concrete'

Because steel is much stiffer than concrete, one mm^2 of steel carries
more force than one mm^2 of concrete at the same strain.

Using \(n\):

- Each steel area \(A_s\) is converted to an **equivalent concrete area** \(n A_s\).

- This lets us do **cracked-section calculations** using a single material (concrete).

---

#### 2. Why it matters in SLS

Once the section cracks, stiffness depends on:

- how much steel you have,

- how far that steel sits from the neutral axis,

- and the **relative stiffness** \(E_s : E_c\).

The modular ratio makes this balance explicit in the
\(I_{cr}\), curvature and steel-stress calculations.

---

#### 3. Typical values

For normal RC beams:

- \(E_c \sim 25{,}000{-}35{,}000\) MPa  

- \(E_s \sim 200{,}000\) MPa  

so \(n\) is usually in the range **6â€“10**.
"""
                )

    section31_details = f"""
*Purpose: Compute the modular ratio and transformed steel areas for each layer.*  

**Inputs:**  

- $E_s = {Es:.0f}$ MPa  
- $E_c = {Ec:.0f}$ MPa  
- Concrete modulus derivation:  
  $$
  E_c = 4700\\sqrt{{f'_c}}
  $$

---

**Formula:**

$$
n = \\frac{{E_s}}{{E_c}}
$$

**Substitution:**

$$
n = \\frac{{{Es:.0f}}}{{{Ec:.0f}}}
  = {Es/Ec:.2f}
$$

The transformed area of each steel layer is $n A_s$.

---

**Result:**  
Modular ratio $n = {Es/Ec:.2f}$ (used to compute $nA_s$ in the table below).
"""

    def info_3_1():
        with _bending_check_info_row(help_text="Modular ratio and transformed steel areas"):
            st.markdown(
                """
## Check 1 - Modular Ratio (n = Es / Ec)

### Why This Calculation Is Required

This check calculates the **modular ratio**, **n**, which is used to transform the reinforcing steel into an equivalent concrete area for Serviceability Limit State (SLS) calculations.

Unlike Ultimate Limit State design, where the steel is assumed to have yielded, SLS analysis assumes both the concrete and reinforcement behave elastically. Because steel is much stiffer than concrete, equal areas of steel and concrete do not carry the same force under the same strain.

The modular ratio accounts for this difference in stiffness and is defined as:

**n = Es / Ec**

where:

* **Es** = modulus of elasticity of reinforcing steel
* **Ec** = modulus of elasticity of concrete

The transformed steel area is then calculated as:

**nAst = n x Ast**

This converts the steel into an equivalent concrete area that has the same axial stiffness under elastic loading.

### Why is transformed section analysis used?

When analysing cracked concrete sections at service loads, the concrete below the neutral axis is assumed to have cracked and therefore contributes negligible tensile stiffness [1].

The reinforcement, however, continues to resist the tensile force. To simplify the analysis, the reinforcement is replaced with an equivalent concrete area having the same stiffness.

This allows the entire cracked section to be analysed using a single material (concrete), making it possible to calculate:

* the cracked neutral axis;
* the cracked second moment of area;
* section stiffness; and
* service stresses and deflections.

### Why is the modular ratio important?

The value of **n** reflects the relative stiffness of steel and concrete.

* A larger modular ratio means the reinforcement contributes proportionally more stiffness to the transformed section.
* A smaller modular ratio means the concrete contributes relatively more stiffness.

Because **Ec** varies with concrete strength while **Es** remains approximately constant, the modular ratio changes with concrete grade.

### Why this check matters

The modular ratio is the foundation of transformed-section analysis. Every subsequent Serviceability Limit State calculation, including cracked neutral axis depth, cracked moment of inertia, stresses and deflections, depends on the transformed reinforcement areas calculated using this ratio.

### References

[1] AS 3600:2018, Clause 8.5 - Serviceability analysis of cracked reinforced concrete sections.

[2] AS 3600:2018, Clause 3.1.2 - Modulus of elasticity of concrete.

[3] AS 3600:2018, Clause 3.2.2 - Modulus of elasticity of reinforcing steel.
"""
            )

    def _sls_3_1_table():
        st.markdown("##### Transformed steel areas")
        layer_rows = []
        for layer in layers_tension:
            As_i = layer["As"]
            layer_rows.append(
                {
                    "Layer": layer["name"],
                    "Description": layer["label"],
                    "Depth y (mm)": layer["y"],
                    "A_s (mm^2)": As_i,
                    "n A_s (mm^2)": n_sls * As_i,
                }
            )
        if include_comp and comp_layer is not None:
            As_c = comp_layer["As"]
            layer_rows.append(
                {
                    "Layer": comp_layer["name"],
                    "Description": comp_layer["label"],
                    "Depth y (mm)": comp_layer["y"],
                    "A_s (mm^2)": As_c,
                    "n A_s (mm^2)": n_sls * As_c,
                }
            )
        st.table(pd.DataFrame(layer_rows))
    
    step_expander_calcbox(
        uid="bending_sls_3_1",
        summary_line=f"Check 1 — Modular ratio $n = E_s / E_c$ | Result: n = {Es/Ec:.2f}",
        details_md=section31_details,
        status=None,
        content_before=info_3_1,
        diagram_fn=None,
        content_after=_sls_3_1_table,
    )

    # --------------------------------------------------
    # 3.2 Neutral axis depth d_n (cracked section) + SLS stress figure
    # --------------------------------------------------
    def equilibrium_residual(dn: float) -> float:
        """C(dn) - T(dn) = 0; dn = neutral axis depth measured from the top fibre."""
        Dv = float(D)
        if hogging_sls:
            Hc = max(0.0, Dv - float(dn))
            C_conc = 0.5 * b * Hc**2
            T_steel = 0.0
            for layer in layers_tension:
                As_i = layer["As"]
                y_i = layer["y"]
                if y_i < dn:
                    T_steel += n_sls * As_i * (dn - y_i)
                else:
                    C_conc += n_sls * As_i * (y_i - dn)
            if include_comp and comp_layer is not None:
                As_c = comp_layer["As"]
                y_c = comp_layer["y"]
                if y_c > dn:
                    C_conc += n_sls * As_c * (y_c - dn)
                else:
                    T_steel += n_sls * As_c * (dn - y_c)
            return C_conc - T_steel

        C_conc = 0.5 * b * dn**2
        T_steel = 0.0
        for layer in layers_tension:
            As_i = layer["As"]
            y_i = layer["y"]
            if y_i > dn:
                T_steel += n_sls * As_i * (y_i - dn)
            else:
                C_conc += n_sls * As_i * (dn - y_i)
        if include_comp and comp_layer is not None:
            As_c = comp_layer["As"]
            y_c = comp_layer["y"]
            if y_c < dn:
                C_conc += n_sls * As_c * (dn - y_c)
            else:
                T_steel += n_sls * As_c * (y_c - dn)
        return C_conc - T_steel

    # Simple bisection between near-top and near-bottom
    dn_low = 1e-6
    dn_high = D - 1e-6
    f_low = equilibrium_residual(dn_low)
    f_high = equilibrium_residual(dn_high)

    if f_low * f_high < 0:
        for _ in range(60):
            dn_mid = 0.5 * (dn_low + dn_high)
            f_mid = equilibrium_residual(dn_mid)
            if f_low * f_mid <= 0:
                dn_high = dn_mid
                f_high = f_mid
            else:
                dn_low = dn_mid
                f_low = f_mid
        dn_sls = 0.5 * (dn_low + dn_high)
    else:
        # Fallback: use the original single-layer quadratic if bracketing fails
        a_quad = 0.5 * b
        b_coef = n_sls * Ast
        c_coef = -n_sls * Ast * d
        dn_sls = float("nan")
        if a_quad != 0:
            disc = b_coef**2 - 4 * a_quad * c_coef
            if disc >= 0:
                roots = [
                    (-b_coef + math.sqrt(disc)) / (2 * a_quad),
                    (-b_coef - math.sqrt(disc)) / (2 * a_quad),
                ]
                roots = [r for r in roots if 0 < r < D]
                if roots:
                    dn_sls = min(roots, key=lambda x: abs(x - d / 2))
        if math.isnan(dn_sls):
            dn_sls = D / 3.0

    # Build LaTeX summaries and substituted-equation terms for step 3.2
    tension_summ_lines = []
    tension_eq_terms = []
    for idx, layer in enumerate(layers_tension, start=1):
        As_i = layer["As"]
        d_i = layer["y"]
        nAs_i = n_sls * As_i
        tension_summ_lines.append(
            rf"d_{idx} = {d_i:.1f}\ \text{{mm}},\quad nA_{{s,{idx}}} = {nAs_i:.1f}\ \text{{mm}}^2"
        )
        tension_eq_terms.append(
            rf"{nAs_i:.1f}\,({d_i:.1f} - d_n)"
        )

    tension_summ_tex = (
        r" \\ ".join(tension_summ_lines)
        if tension_summ_lines
        else r"\text{(no tension layers)}"
    )
    tension_eq_tex = (
        " + ".join(tension_eq_terms) if tension_eq_terms else "0"
    )

    comp_summ_tex = ""
    comp_eq_tex = ""
    if include_comp and comp_layer is not None:
        As_c = comp_layer["As"]
        d_sc = comp_layer["y"]
        nAs_c = n_sls * As_c
        comp_summ_tex = (
            rf"d_{{s,c}} = {d_sc:.1f}\ \text{{mm}},\quad nA_{{s,c}} = {nAs_c:.1f}\ \text{{mm}}^2"
        )
        comp_eq_tex = rf"{nAs_c:.1f}\,(d_n - {d_sc:.1f})"

    b_mm = float(b or 0.0)
    dn_val = float(dn_sls)

    # Build compression steel section separately (to avoid f-string backslash issue)
    comp_section = ""
    if comp_summ_tex:
        comp_section = (
            "Compression steel layer:\n\n"
            "\\[\n\\begin{aligned}\n"
            + comp_summ_tex
            + "\n\\end{aligned}\n\\]\n"
        )

    section32_details = rf"""
**Purpose:** Find the cracked-section neutral axis depth $d_n$ by enforcing
equilibrium of **transformed areas** (tension steel vs concrete + compression steel).

**Concept:**

Tension side (transformed steel):

\[
T = \sum n A_{{s,i}} (d_i - d_n)
\]

Concrete (and any compression steel) provide compression $C$ so that:

\[
\frac{{b d_n^2}}{2} + \sum n A_{{s,c}} (d_n - d_{{s,c}})
=
\sum n A_{{s,i}} (d_i - d_n)
\]

**Substitution (section data):**

\[
b = {b_mm:.0f}\ \text{{mm}}
\]

Tension steel layers:

\[
\begin{{aligned}}
{tension_summ_tex}
\end{{aligned}}
\]

{comp_section}**So that:**

\[
\frac{{{b_mm:.0f}\, d_n^2}}{2}
{(" + " + comp_eq_tex) if comp_eq_tex else ""}
=
{tension_eq_tex}
\]

This equation is then solved **numerically** for $d_n$ on the current section
(using a bisection root-finder).

**Result (this section):**

\[
d_n = {dn_val:.2f}\ \text{{mm}}
\]
"""
    
    def diagram_3_2():
        # Build diagram from fresh calc values (not session_state)
        # Compute preliminary kappa for strain distribution (needed for eps_top)
        if hogging_sls:
            Hp = max(0.0, float(D) - float(dn_sls))
            Icr_prelim = b * Hp**3 / 3.0
        else:
            Icr_prelim = b * dn_sls**3 / 3.0
        for layer in layers_tension:
            As_i = layer["As"]
            y_i = layer["y"]
            if (hogging_sls and y_i < dn_sls) or ((not hogging_sls) and y_i >= dn_sls):
                Icr_prelim += n_sls * As_i * (y_i - dn_sls) ** 2
        if include_comp and comp_layer is not None:
            As_c = comp_layer["As"]
            y_c = comp_layer["y"]
            if hogging_sls:
                if y_c > dn_sls:
                    Icr_prelim += n_sls * As_c * (y_c - dn_sls) ** 2
                else:
                    Icr_prelim += n_sls * As_c * (dn_sls - y_c) ** 2
            elif y_c < dn_sls:
                Icr_prelim += n_sls * As_c * (dn_sls - y_c) ** 2
            else:
                Icr_prelim += n_sls * As_c * (y_c - dn_sls) ** 2
        kappa_prelim = (Ms * 1e6) / (Ec * Icr_prelim) if Ec and Icr_prelim else 0.0
        eps_top_prelim = kappa_prelim * (0.0 - dn_sls)  # eps_top = kappa * (0 - dn)
        
        # Compute eps_s_layers and sig_s_layers for each tension layer
        eps_s_layers = []
        sig_s_layers = []
        y_layers = []
        for layer in layers_tension:
            eps_s_i = kappa_prelim * (layer["y"] - dn_sls)
            sig_s_i = Es * eps_s_i  # MPa
            eps_s_layers.append(eps_s_i)
            sig_s_layers.append(sig_s_i)
            y_layers.append(layer["y"])
        
        # Build state dict for 3-panel plot (if needed)
        sls_state = {
            "dn": dn_sls,
            "eps_c_top": eps_top_prelim,
            "eps_s_layers": eps_s_layers,
            "sig_s_layers": sig_s_layers,
            "y_layers": y_layers,
        }
        
        # Use Plotly function that matches 3-panel diagram conventions
        fig = _make_sls_stress_block_figure(
            D_mm=D or 0.0,
            d_mm=d,
            dn_mm=dn_sls,
            include_comp=(include_comp and comp_layer is not None),
            d_comp_mm=comp_layer["y"] if (include_comp and comp_layer is not None) else None,
            moment_sign="negative" if hogging_sls else "positive",
        )
        render_plotly_diagram(
            fig,
            key=f"sls_3_2_{st.session_state['_diag_nonce']}",
            title="SLS stress block",
            config={"displayModeBar": False},
        )

    def info_3_2():
        with _bending_check_info_row(help_text="Cracked neutral axis depth"):
            st.markdown(
                """
## Check 2 - Cracked Neutral Axis Depth (dn)

### Why This Calculation Is Required

This check determines the location of the **neutral axis** for the cracked concrete section under service loading using the transformed-section method required for elastic cracked-section analysis [1].

After cracking, the concrete below the neutral axis is assumed to carry negligible tensile stress. The tensile force is resisted entirely by the reinforcing steel, while the concrete above the neutral axis remains in compression.

Because the reinforcement has been transformed into an equivalent concrete area using the modular ratio, the cracked section can be analysed as a single transformed concrete section.

### How is the neutral axis determined?

The neutral axis is located by satisfying equilibrium of the transformed areas.

The first moment of the transformed tensile reinforcement about the neutral axis is balanced by the first moment of the concrete compression zone and any transformed compression reinforcement.

The solution therefore satisfies:

**Compression = Tension**

This equation is solved iteratively because the neutral axis depth appears in both the compression and tension terms.

Once equilibrium is achieved, the calculated value is the cracked neutral axis depth.

### Why does the neutral axis move?

The cracked neutral axis is generally deeper than the uncracked neutral axis because:

* the concrete below the neutral axis is no longer effective in tension;
* the transformed reinforcement carries all tensile force;
* the compression zone adjusts until internal equilibrium is restored.

The position of the neutral axis therefore reflects the actual stiffness of the cracked section.

### Why is this check important?

The cracked neutral axis controls almost every subsequent Serviceability Limit State calculation, including:

* the cracked second moment of area;
* section stiffness;
* concrete compression stresses;
* reinforcement stresses;
* crack width calculations;
* deflection calculations.

Even small changes in neutral axis depth can significantly affect the calculated stiffness and long-term deflections of the member.

### Why this check matters

Determining the cracked neutral axis establishes the geometry of the cracked transformed section. It forms the basis for all subsequent serviceability calculations by defining how compression is distributed through the concrete and how the transformed reinforcement contributes to the section stiffness.

### References

[1] AS 3600:2018, Clause 8.5 - Elastic analysis of cracked reinforced concrete sections.

[2] AS 3600:2018, Clause 8.5 - Transformed-section method for cracked section properties.
"""
            )
    
    step_expander_calcbox(
        uid="bending_sls_3_2",
        summary_line=f"Check 2 — Neutral axis depth $d_n$ (cracked section) | Result: d_n = {dn_sls:.1f} mm",
        details_md=section32_details,
        status=None,
        diagram_fn=diagram_3_2,
        content_before=info_3_2,
    )

    # --------------------------------------------------
    # 3.3 Cracked moment of inertia I_cr (CALC BOX ONLY)
    # --------------------------------------------------
    # Classify compression / tension for Icr based on dn_sls
    if hogging_sls:
        Hc_i = max(0.0, float(D) - float(dn_sls))
        I_conc = b * Hc_i**3 / 3.0
    else:
        I_conc = b * dn_sls**3 / 3.0
    I_t = 0.0
    I_c = 0.0

    for layer in layers_tension:
        As_i = layer["As"]
        y_i = layer["y"]
        if hogging_sls:
            if y_i < dn_sls:
                I_t += n_sls * As_i * (dn_sls - y_i) ** 2
            else:
                I_c += n_sls * As_i * (y_i - dn_sls) ** 2
        elif y_i >= dn_sls:
            I_t += n_sls * As_i * (y_i - dn_sls) ** 2
        else:
            I_c += n_sls * As_i * (dn_sls - y_i) ** 2

    if include_comp and comp_layer is not None:
        As_c = comp_layer["As"]
        y_c = comp_layer["y"]
        if hogging_sls:
            if y_c > dn_sls:
                I_c += n_sls * As_c * (y_c - dn_sls) ** 2
            else:
                I_t += n_sls * As_c * (dn_sls - y_c) ** 2
        elif y_c < dn_sls:
            I_c += n_sls * As_c * (dn_sls - y_c) ** 2
        else:
            I_t += n_sls * As_c * (y_c - dn_sls) ** 2

    Icr = I_conc + I_t + I_c

    section33_details = f"""
*Purpose: Compute the cracked transformed moment of inertia $I_{{cr}}$ about the neutral axis.*  

**Formula:**

$$
I_{{cr}} =
\\frac{{b d_n^3}}{{3}}
+ \\sum n A_{{s,i}} (d_i - d_n)^2
+ \\sum n A_{{s,c}} (d_n - d_{{s,c}})^2
$$

For this section:

- Concrete term: $\\dfrac{{b d_n^3}}{{3}} = {_fmt(I_conc)}\\ \\text{{mm}}^4$  
- Steel in tension: $\\sum n A_{{s,i}} (d_i - d_n)^2 = {_fmt(I_t)}\\ \\text{{mm}}^4$  
- Steel in compression: $\\sum n A_{{s,c}} (d_n - d_{{s,c}})^2 = {_fmt(I_c)}\\ \\text{{mm}}^4$  

So:

$$
I_{{cr}} = {Icr:,.2f}\\ \\text{{mm}}^4
$$

---

**Result:**  
Cracked transformed inertia $I_{{cr}} = {Icr:,.2f}\\ \\text{{mm}}^4$.
"""

    def info_3_3():
        with _bending_check_info_row(help_text="Cracked moment of inertia"):
            st.markdown(
                """
### Cracked Moment of Inertia (Icr) - Why This Calculation Is Required

This check calculates the **cracked moment of inertia**, **Icr**, of the transformed reinforced concrete section about the cracked neutral axis.

The moment of inertia is a geometric property that describes **how efficiently the cross-section resists bending**. It depends not only on the amount of material present, but also on **how far that material is located from the neutral axis**. Material located further from the neutral axis contributes significantly more to the section stiffness because its contribution increases with the square of the distance from the neutral axis.

### Why is a cracked moment of inertia required?

Before cracking, the concrete section is assumed to act as a complete solid section, and its stiffness is represented by the **gross moment of inertia (Ig)**.

Once the tensile stress in the concrete exceeds its tensile strength, cracks form in the tension zone. After cracking, the concrete below the neutral axis is assumed to contribute negligible tensile stiffness and is therefore ignored in the transformed section analysis [1].

The beam stiffness is therefore no longer represented by **Ig**, but by the much smaller **cracked moment of inertia (Icr)**.

This reduction in stiffness is one of the primary reasons reinforced concrete beams experience larger deflections after cracking.

### How is Icr calculated?

The cracked section is analysed using the transformed-section method, where the reinforcing steel is converted into an equivalent concrete area using the modular ratio calculated in Check 3.1.

The cracked moment of inertia is then obtained by summing the contributions from:

* the concrete compression zone;
* the transformed tensile reinforcement; and
* any transformed compression reinforcement.

Each component contributes according to the **parallel axis theorem**.

For each component:

**Contribution = Centroidal inertia + Area x (distance to neutral axis)^2**

The total cracked moment of inertia is therefore:

**Icr = Concrete contribution + Transformed tension steel contribution + Transformed compression steel contribution**

The concrete compression block contributes its own geometric inertia, while each transformed reinforcement layer contributes primarily through the **Area x distance^2** term because the bars are located well away from the neutral axis.

### Why does reinforcement contribute so much?

Although the reinforcement occupies only a small area compared with the concrete, it is generally located close to the outer fibres of the beam.

Because the contribution to moment of inertia increases with the **square of the distance from the neutral axis**, reinforcement positioned further from the neutral axis makes a disproportionately large contribution to the cracked stiffness.

This is why increasing the effective depth of reinforcement often produces a much larger increase in stiffness than simply increasing the reinforcement area.

### Why is the neutral axis important?

The cracked moment of inertia is calculated **about the cracked neutral axis**, not the centroid of the original section.

As the neutral axis moves deeper into the section after cracking:

* the concrete compression zone becomes smaller;
* the compression-zone inertia decreases;
* the reinforcement distances to the neutral axis change; and
* the overall section stiffness changes.

For this reason, the cracked neutral axis must always be determined before calculating **Icr**.

### Why is Icr important?

The cracked moment of inertia defines the **flexural stiffness** of the cracked member.

The flexural stiffness is:

**EI = Ec x Icr**

where:

* **Ec** represents the material stiffness of the concrete.
* **Icr** represents the geometric stiffness of the cracked section.

Together they determine how much the beam bends under service loading.

### Why this check matters

The cracked moment of inertia is one of the most important properties calculated during Serviceability Limit State analysis because it is subsequently used to determine:

* service curvature;
* short-term deflections;
* long-term deflections;
* reinforcement stresses;
* concrete compression stresses;
* crack width calculations; and
* overall serviceability performance.

An accurate value of **Icr** is therefore essential for predicting the real behaviour of reinforced concrete members after cracking.

### References

[1] AS 3600:2018, Clause 8.5 - Elastic analysis of cracked reinforced concrete sections.

[2] AS 3600:2018, Clause 8.5 - Transformed-section properties and cracked section stiffness.

[3] AS 3600:2018, Clause 3.1.2 - Modulus of elasticity of concrete (Ec).
"""
            )

    step_expander_calcbox(
        uid="bending_sls_3_3",
        summary_line=f"Check 3 — Cracked moment of inertia I_cr | Result: I_cr = {Icr:,.2f} mm^4",
        details_md=section33_details,
        status=None,
        diagram_fn=None,
        content_before=info_3_3,
    )


    # --------------------------------------------------
    # 3.4 Curvature at service moment
    # --------------------------------------------------
    Ms_Nmm = Ms * 1e6
    kappa = Ms_Nmm / (Ec * Icr) if Ec and Icr else 0.0

    # --- Publish curvature + NA depth for diagrams (SLS) ---
    try:
        st.session_state["bending_sls_dn"] = float(dn_sls)
        st.session_state["bending_sls_kappa"] = float(kappa)
        update_results(
            bending_sls_dn=float(dn_sls),
            bending_sls_kappa=float(kappa),
        )
    except Exception:
        pass

    section34_details = f"""
*Purpose: Evaluate curvature at the service moment using the cracked-section stiffness.*  

**Inputs:**  

- Service moment $M_s = {Ms:.2f}$ kNm  
- $E_c = {Ec:.0f}$ MPa  
- $I_{{cr}} = {Icr:,.2f}\\ \\text{{mm}}^4$  

---

**Formula:**

$$
\\kappa = \\frac{{M_s}}{{E_c I_{{cr}}}}
$$

**Substitution:**

$$
\\kappa = \\frac{{{Ms:.2f}\\times 10^6}}{{{Ec:.0f} \\times {Icr:,.2f}}}
       = {kappa:.3e}\\ \\text{{mm}}^{{-1}}
$$

---

**Result:**  
Curvature at service: $\\kappa = {kappa:.3e}\\ \\text{{mm}}^{{-1}}$.
"""

    def info_3_4():
        with _bending_check_info_row(help_text="Curvature at service moment"):
            st.markdown(
                """
### Curvature at Service Moment (kappa) - Why This Calculation Is Required

This check calculates the **curvature** of the cracked reinforced concrete section under the applied service bending moment.

Curvature describes the rate at which a beam bends under loading and is directly related to the stiffness of the section.

For linear elastic behaviour, curvature is calculated from:

**kappa = Ms / (Ec x Icr)**

where:

* **Ms** = service bending moment;
* **Ec** = modulus of elasticity of concrete; and
* **Icr** = cracked moment of inertia.

This equation shows that curvature increases with applied moment and decreases as section stiffness increases.

### What does curvature represent?

Curvature is the change in rotation per unit length of the member.

* A **small curvature** indicates a stiff section that bends very little.
* A **large curvature** indicates a more flexible section that undergoes greater bending.

Curvature is therefore the fundamental quantity used to determine beam deflections.

### Why is cracked stiffness used?

Under normal service loading, reinforced concrete members generally crack in tension.

Once cracking occurs, the member stiffness reduces from the gross section stiffness to the cracked section stiffness represented by **Ec x Icr**.

Using the cracked stiffness provides a more realistic prediction of service deflections and member behaviour.

### Why this check matters

The calculated curvature forms the basis for the remaining serviceability calculations.

It is used to determine:

* beam deflections;
* long-term deformation;
* member rotations;
* strain distributions under service loading; and
* service stress calculations.

Accurate prediction of curvature is therefore essential for assessing the serviceability performance of reinforced concrete members.

### References

[1] AS 3600:2018, Clause 8.5 - Serviceability analysis using cracked section properties.

[2] AS 3600:2018, Clause 8.5 - Elastic cracked-section stiffness and transformed-section analysis.
"""
            )

    step_expander_calcbox(
        uid="bending_sls_3_4",
        summary_line=f"Check 4 — Curvature at service moment | Result: kappa = {kappa:.3e} mm^-1",
        details_md=section34_details,
        status=None,
        diagram_fn=None,
        content_before=info_3_4,
    )

    # --------------------------------------------------
    # 3.5 Strain distribution epsilon(y) = kappa(y - d_n)
    # --------------------------------------------------
    strain_points = [("Top fibre", 0.0)]
    for layer in layers_tension:
        strain_points.append((layer["label"], layer["y"]))
    if include_comp and comp_layer is not None:
        strain_points.append((comp_layer["label"], comp_layer["y"]))
    strain_points.append(("Bottom fibre", D))

    strain_rows = []
    for name, yi in strain_points:
        eps = kappa * (yi - dn_sls)
        strain_rows.append({"Layer": name, "Depth y (mm)": yi, "epsilon": eps})

    df_eps = pd.DataFrame(strain_rows)

    # Find max strain for summary line
    if strain_rows:
        max_strain_abs = max([abs(row["epsilon"]) for row in strain_rows])
        max_strain_row = next((row for row in strain_rows if abs(row["epsilon"]) == max_strain_abs), None)
        max_strain_label = max_strain_row["Layer"] if max_strain_row else ""
        max_strain_val = max_strain_row["epsilon"] if max_strain_row else 0.0
    else:
        max_strain_label = ""
        max_strain_val = 0.0
    
    section35_details = f"""
*Purpose: Compute the linear strain distribution at SLS for key depths.*  

**Formula:**

Strain at depth $y$ from the top:

$$
\\varepsilon(y) = \\kappa (y - d_n)
$$

For key layers (including each steel layer), the table lists:

- Depth $y$  
- Strain $\\varepsilon(y)$  

---

**Result:**  
See table for $\\varepsilon(y)$ at the top fibre, each steel layer, and bottom fibre.
"""

    def _sls_3_5_diagram():
        fig_eps = _shared_make_sls_strain_distribution_figure(strain_rows, dn_sls)
        render_pyplot_diagram(
            fig_eps,
            key="bending_sls_3_5_strain_distribution",
            title="SLS strain distribution",
            use_container_width=True,
        )
        plt.close(fig_eps)
    
    def _sls_3_5_table():
        st.markdown("##### Strain distribution results")
        st.table(df_eps)

    def info_3_5():
        with _bending_check_info_row(help_text="Strain distribution"):
            st.markdown(
                """
### Strain Distribution - Why This Calculation Is Required

This check calculates the **strain at key locations throughout the cracked concrete section** under the applied service bending moment.

Once the section curvature has been determined in the previous check, the strain at any depth within the section can be calculated using the assumption that **plane sections remain plane after bending** [1]. This means the strain varies linearly through the depth of the member.

The strain at any depth is given by:

**epsilon(y) = kappa(y - dn)**

where:

* **kappa** = section curvature
* **y** = depth measured from the compression face
* **dn** = cracked neutral axis depth

Because the relationship is linear, the strain diagram is represented by a straight line passing through the neutral axis, where the strain is zero.

### Why is the strain distribution important?

The strain distribution describes how much every part of the beam stretches or shortens under service loading.

* Concrete above the neutral axis experiences compressive strain.
* The neutral axis has zero longitudinal strain.
* Reinforcement and concrete below the neutral axis experience tensile strain.

Knowing the strain at any depth allows the corresponding material stresses to be calculated using the appropriate stress-strain relationships.

### Why does the strain vary linearly?

The assumption that **plane sections remain plane** is one of the fundamental principles of reinforced concrete analysis.

As the beam bends:

* fibres near the compression face shorten;
* fibres below the neutral axis lengthen;
* the strain changes uniformly between these locations.

This assumption has been shown experimentally to provide an accurate representation of reinforced concrete behaviour under normal flexural loading and forms the basis of both Ultimate and Serviceability Limit State calculations.

### Why this check matters

The strain distribution links the section geometry with the material behaviour.

It provides the strain at:

* the extreme concrete compression fibre;
* every reinforcement layer;
* the bottom concrete fibre; and
* any other depth within the section.

These calculated strains are then used directly to determine:

* reinforcement stresses;
* concrete stresses;
* crack widths;
* service stress checks; and
* serviceability performance.

### References

[1] AS 3600:2018, Clause 8.5 - Elastic analysis of cracked reinforced concrete sections using strain compatibility.

[2] AS 3600:2018, Clause 8.5 - Serviceability analysis based on transformed cracked-section properties.
"""
            )

    step_expander_calcbox(
        uid="bending_sls_3_5",
        summary_line=f"Check 5 — Strain distribution epsilon(y) = kappa(y - d_n) | Max strain: {max_strain_label} = {max_strain_val:.5f}",
        details_md=section35_details,
        status=None,
        diagram_fn=_sls_3_5_diagram,
        content_before=info_3_5,
        content_after=_sls_3_5_table,
    )


    # --------------------------------------------------
    # 3.6 Steel stresses at SLS (each layer)
    # --------------------------------------------------

    steel_rows = []

    # tension layers
    for layer in layers_tension:
        eps_s = kappa * (layer["y"] - dn_sls)
        fs = Es * eps_s  # MPa
        steel_rows.append(
            {
                "Layer": layer["name"],
                "Description": layer["label"],
                "Depth y (mm)": layer["y"],
                "epsilon_s": eps_s,
                "f_s (MPa)": fs,
            }
        )

    # compression layer (if any)
    if include_comp and comp_layer is not None:
        eps_s_c = kappa * (comp_layer["y"] - dn_sls)
        fs_c = Es * eps_s_c
        steel_rows.append(
            {
                "Layer": comp_layer["name"],
                "Description": comp_layer["label"],
                "Depth y (mm)": comp_layer["y"],
                "epsilon_s": eps_s_c,
                "f_s (MPa)": fs_c,
            }
        )

    df_steel = pd.DataFrame(steel_rows)

    # Example substitution for first tension layer (if available)
    example_eps = ""
    example_fs = ""
    if steel_rows and len(steel_rows) > 0:
        first_row = steel_rows[0]
        example_eps = f"\\varepsilon_{{s,1}} = {first_row['epsilon_s']:.5f}"
        example_fs = f"f_{{s,1}} = {first_row['f_s (MPa)']:.1f} \\text{{ MPa}}"
    else:
        example_eps = "\\varepsilon_{{s,1}} = \\kappa (d_1 - d_n)"
        example_fs = "f_{{s,1}} = E_s \\varepsilon_{{s,1}}"

    # Find max steel stress for summary line
    max_fs = max([row["f_s (MPa)"] for row in steel_rows], default=0.0) if steel_rows else 0.0
    max_fs_row = next((row for row in steel_rows if row["f_s (MPa)"] == max_fs), None) if steel_rows else None
    max_fs_label = max_fs_row["Layer"] if max_fs_row else ""
    
    section36_details = f"""
*Purpose: Derive steel stresses at SLS for each reinforcement layer.*  

**Formula:**

- Hooke's law for each steel layer  

  $f_{{s,i}} = E_s \\varepsilon_{{s,i}}$

- Steel strain in each layer:  

  $\\varepsilon_{{s,i}} = \\kappa (d_i - d_n)$

- Resultant tension:  

  $T = \\sum n A_{{s,i}} f_{{s,i}}$

**Substitution (bottom layer example):**

$E_s = {Es:,.0f} \\text{{ MPa}},\\;
{example_eps}$

$\\Rightarrow
{example_fs}$

The table below lists $\\varepsilon_{{s,i}}$ and $f_{{s,i}}$ for each steel layer.

---

**Result:**  
See table for layer-by-layer SLS steel strains and stresses.
"""
    def _sls_3_6_table():
        st.markdown("##### Steel stress results")
        st.table(df_steel)

    def info_3_6():
        with _bending_check_info_row(help_text="Steel stresses at SLS"):
            st.markdown(
                """
### Steel Stresses at Serviceability Limit State - Why This Calculation Is Required

This check calculates the **stress in each reinforcement layer** under service loading.

The reinforcement stresses are determined directly from the strain distribution calculated in the previous check.

For each reinforcement layer:

1. The steel strain is obtained from the service strain diagram.
2. Hooke's Law is applied to calculate the corresponding steel stress.

The steel stress is therefore:

**fs = Es x epsilon_s**

where:

* **Es** = modulus of elasticity of reinforcing steel
* **epsilon_s** = calculated steel strain

Because Serviceability Limit State analysis assumes elastic behaviour, the reinforcement stress is directly proportional to the calculated strain [1].

### Why are service stresses calculated?

Unlike Ultimate Limit State design, the reinforcement is **not assumed to have yielded**.

Instead, the steel is expected to remain within its elastic range during normal service loading.

Calculating the actual service stress allows the engineer to evaluate:

* reinforcement performance under working loads;
* crack width behaviour;
* long-term durability;
* fatigue performance; and
* compliance with serviceability requirements.

### Why is Hooke's Law used?

At service loads, reinforcing steel behaves almost perfectly elastically.

Within the elastic range:

**Stress = Elastic Modulus x Strain**

This simple linear relationship provides an accurate prediction of reinforcement stresses under normal operating conditions.

Only if the service loading became sufficiently large for the reinforcement to approach yield would a nonlinear material model become necessary.

### Why are stresses calculated for each reinforcement layer?

Different reinforcement layers are located at different depths within the beam.

Since strain varies linearly through the section, each layer experiences a different strain and therefore a different stress.

Calculating the stress in every layer allows the program to accurately assess:

* crack formation;
* reinforcement demand;
* service stress limits; and
* the contribution of each reinforcement layer to the overall section behaviour.

### Why this check matters

The calculated steel stresses form the basis for the remaining Serviceability Limit State calculations.

They are subsequently used to determine:

* crack widths;
* reinforcement stress limits;
* durability checks;
* fatigue assessments; and
* long-term service performance.

Accurate steel stresses are therefore essential for assessing how the reinforced concrete member will perform throughout its service life.

### References

[1] AS 3600:2018, Clause 8.5 - Elastic analysis of cracked reinforced concrete sections.

[2] AS 3600:2018, Clause 3.2.2 - Modulus of elasticity of reinforcing steel (Es).
"""
            )

    step_expander_calcbox(
        uid="bending_sls_3_6",
        summary_line=f"Check 6 — Steel stresses at SLS (each layer) | Max stress: {max_fs_label} = {max_fs:.1f} MPa",
        details_md=section36_details,
        status=None,
        diagram_fn=None,
        content_before=info_3_6,
        content_after=_sls_3_6_table,
    )

    # --------------------------------------------------
    # 3.6a Store cracked SLS state for diagrams (read-only)
    # --------------------------------------------------
    deepest = None
    if steel_rows:
        pos_steel = [row for row in steel_rows if row["f_s (MPa)"] > 0.0]
        if pos_steel:
            deepest = (
                min(pos_steel, key=lambda row: row["Depth y (mm)"])
                if hogging_sls
                else max(pos_steel, key=lambda row: row["Depth y (mm)"])
            )

    # Save cracked-section SLS geometry + steel state to session_state
    # (no widgets touched â€“ these are read-only â€œoutputâ€ values)
    st.session_state["bending_sls_dn"] = float(dn_sls)
    st.session_state["bending_sls_kappa"] = float(kappa)

    if deepest is not None:
        eps_outer = float(deepest["epsilon_s"])
        fs_outer = float(Es * eps_outer)
        st.session_state["bending_sls_y_tension_outer"] = float(
            deepest["Depth y (mm)"]
        )
        st.session_state["bending_sls_eps_s_outer"] = float(eps_outer)
        st.session_state["bending_sls_fs_outer"] = float(fs_outer)
        update_results(
            bending_sls_y_tension_outer=float(deepest["Depth y (mm)"]),
            bending_sls_eps_s_outer=float(eps_outer),
            bending_sls_fs_outer=float(fs_outer),
        )

    # --------------------------------------------------
    # 3.7 Link to crack-width calculation
    # --------------------------------------------------

    fs_tension = None
    eps_s_control = None
    y_control = None

    if steel_rows:
        deepest = (
            min(steel_rows, key=lambda row: float(row["Depth y (mm)"]))
            if hogging_sls
            else max(steel_rows, key=lambda row: float(row["Depth y (mm)"]))
        )
        if deepest is not None:
            fs_tension = abs(float(deepest["f_s (MPa)"]))
            eps_s_control = float(deepest["epsilon_s"])
            y_control = float(deepest["Depth y (mm)"])

    # Also compute top-fibre SLS strain from Îº and d_n,sls
    eps_top_sls = kappa * (0.0 - dn_sls)

    # Publish SLS strain/position data for the main diagrams
    try:
        st.session_state["bending_sls_dn"] = float(dn_sls)
        st.session_state["bending_sls_eps_top"] = float(eps_top_sls)
        if eps_s_control is not None and y_control is not None:
            st.session_state["bending_sls_eps_bot"] = float(eps_s_control)
            st.session_state["bending_sls_y_bot"] = float(y_control)
    except Exception:
        pass

    if fs_tension is not None:
        section37_details = f"""
*Purpose: Identify the controlling SLS steel stress for use in crack-width checks.*  

The **critical tension steel stress** at SLS is taken as the stress in the
**outermost tension layer**.

From the table above, this is approximately:

$$
f_{{s,ser}} \\approx {fs_tension:.1f}\\ \\text{{MPa}}
$$

---

**Result:**  
Use $f_{{s,ser}} \\approx {fs_tension:.1f}$ MPa in crack-width calculations on the Crack Width tab.
"""
        step_expander_calcbox(
            uid="bending_sls_3_7",
            summary_line=f"Check 7 — Link to crack-width calculation | f_s,ser ~= {fs_tension:.1f} MPa",
            details_md=section37_details,
            status=None,
            diagram_fn=None,
        )
        
        # Publish for Crack Width page â€“ service tensile steel stress at SLS
        from bending_core import compute_sigma_s_sls_for_crack
        compute_sigma_s_sls_for_crack(publish=True)
    else:
        st.info(
            "No tension layer found for crack-width link â€“ check the SLS inputs."
        )
