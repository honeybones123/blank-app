"""Creep calculation-card presentation.

All values arrive through an immutable, calculation-complete snapshot.  This
module owns no engineering calculation or publication state.
"""

from __future__ import annotations

from engineering_page_sections.creep_checks_context import CreepChecksSnapshot
from engineering_page_sections.stable_tabs import render_stable_tabs
from step_ui import render_expandable_step
from widgets_helpers import info_i_button, render_section_title


def render_creep_checks(st, checks: CreepChecksSnapshot) -> None:
    b = checks.width_mm
    D = checks.depth_mm
    Ag = checks.gross_area_mm2
    faces_option = checks.faces_exposed
    ue = checks.exposed_perimeter_mm
    th_raw = checks.notional_thickness_raw_mm
    th_table = checks.notional_thickness_table_mm
    t_creep = checks.time_after_loading_days
    age_at_loading = checks.age_at_loading_days
    fc = checks.concrete_strength_mpa
    Ec = checks.concrete_modulus_mpa
    env_option = checks.environment
    phi_cc_b = checks.phi_cc_b
    k2 = checks.k2
    k3 = checks.k3
    k4 = checks.k4
    k5 = checks.k5
    k6 = checks.k6
    phi_cc_t = checks.phi_cc_t
    phi_cc_star_table = checks.phi_cc_star_table
    sustained_mstar = checks.sustained_moment_knm
    sustained_fibre = checks.sustained_compression_fibre
    sustained_z = checks.sustained_section_modulus_mm3
    sigma0 = checks.sustained_stress_mpa
    stress_ratio = checks.sustained_stress_ratio
    eps_cc = checks.eps_cc
    eps_cc_micro = checks.eps_cc_micro

    render_section_title("Creep checks")

    st.markdown(
        """
<style>
/* Tighten gap between tab labels and first calc card (creep page only) */
div[data-testid="stTabs"] [data-baseweb="tab-panel"] {
  padding-top: 0.35rem !important;
}
</style>
""",
        unsafe_allow_html=True,
    )

    _creep_tab_labels = (
        "Notional thickness t_h and k₂",
        "Creep coefficient ϕ_cc(t)",
        "Creep strain ε_cc",
    )
    creep_geometry_tab, creep_coefficient_tab, creep_strain_tab = render_stable_tabs(
        st,
        labels=_creep_tab_labels,
        scope_id="creep-calculation-checks",
    )

    # Calculate alpha2 for display in k2 calc box
    alpha2 = checks.alpha2

    # Step 1: Notional thickness t_h (raw)
    def render_th_raw():
        return f"""
**Summary**

| Quantity | Value |
|----------|-------|
| Section width b | {b:.1f} mm |
| Overall depth D | {D:.1f} mm |
| Gross area A_g | {Ag:.0f} mm² |
| Faces exposed | {faces_option} |
| Exposed perimeter u_e | {ue:.1f} mm |
| **Notional thickness t_h** | **{th_raw:.1f} mm** |

**Purpose**

Determine notional thickness t_h from section geometry and exposed perimeter.

**Inputs**

- Section width: b = {b:.1f} mm
- Overall depth: D = {D:.1f} mm
- Gross area: A_g = b·D = {Ag:.0f} mm²
- Faces exposed: {faces_option}
- Exposed perimeter: u_e = {ue:.1f} mm

**Calculation**

t_h = 2·A_g / u_e

**Substitution**

t_h = 2 × {Ag:.0f} / {ue:.1f} ≈ {th_raw:.1f} mm

**Result**

t_h = {th_raw:.1f} mm

_Ref: AS 3600:2018 definition of notional thickness (t_h = 2 A_g/u_e)._
"""

    # Step 2: Adopted thickness for AS figure/table
    def render_th_table():
        return f"""
**Summary**

| Quantity | Value |
|----------|-------|
| Raw notional thickness t_h | {th_raw:.1f} mm |
| **Adopted thickness t_h,AS** | **{th_table:d} mm** |

**Purpose**

Map the raw notional thickness to the discrete AS curve thickness used in the figure/table.

**Inputs**

- Raw notional thickness: t_h = {th_raw:.1f} mm (from previous step)
- Discrete curve options: 100, 200, 400 mm

**Decision rule**

The raw notional thickness is mapped to the nearest standard value from the set {{100, 200, 400}} mm for compatibility with Fig. 3.1.8.3 and Table 3.1.8.3.

**Calculation**

Raw value: t_h = {th_raw:.1f} mm

Nearest standard value: t_h,AS = {th_table:d} mm

**Result**

Adopted notional thickness: t_h,AS = {th_table:d} mm

_Ref: AS 3600:2018 Fig. 3.1.8.3 and Table 3.1.8.3 use discrete thickness values._
"""

    # Step 3: Time-development factor k2
    def render_k2():
        return f"""
**Summary**

| Quantity | Value |
|----------|-------|
| Time after loading t | {t_creep:.0f} days |
| Adopted thickness t_h,AS | {th_table:d} mm |
| Parameter α₂ | {alpha2:.4f} |
| **Time-development factor k₂** | **{k2:.3f}** |

**Purpose**

Compute k₂ as a function of time and adopted notional thickness.

**Inputs**

- Time after loading: t = {t_creep:.0f} days
- Adopted notional thickness: t_h,AS = {th_table:d} mm (from previous step)

**Calculation**

k₂(t, t_h) = α₂ · t^0.8 / ( t^0.8 + 0.15·t_h )

where:

α₂ = 1.0 + 1.12·exp( −0.008·t_h )

**Substitution**

α₂ = 1.0 + 1.12·exp( −0.008 × {th_table:d} ) ≈ {alpha2:.4f}

For t = {t_creep:.0f} days and t_h = {th_table:d} mm:

k₂ = {alpha2:.4f} × {t_creep:.0f}^0.8 / ( {t_creep:.0f}^0.8 + 0.15 × {th_table:d} )

k₂ ≈ {k2:.3f}

**Result**

k₂ = {k2:.3f}

_Ref: AS 3600:2018 Cl. 3.1.8.3 and Fig. 3.1.8.3._
"""

    with creep_geometry_tab:
        render_expandable_step(
            page_key="creep_geom",
            step_id="creep_th_raw",
            title="Notional thickness t_h (raw)",
            summary_md=[
                "Check 1.1 — Determine notional thickness from section geometry and exposed perimeter",
                f"Result: t_h = {th_raw:.1f} mm",
            ],
            status_kind=None,
            calc_md=render_th_raw(),
        )
        render_expandable_step(
            page_key="creep_geom",
            step_id="creep_th_table",
            title="Adopted thickness for AS figure/table",
            summary_md=[
                "Check 1.2 — Map raw notional thickness to discrete AS curve thickness",
                f"Adopted: t_h,AS = {th_table:d} mm",
            ],
            status_kind=None,
            calc_md=render_th_table(),
        )
        render_expandable_step(
            page_key="creep_geom",
            step_id="creep_k2",
            title="Time-development factor k₂",
            summary_md=[
                "Check 1.3 — Compute k₂ as a function of time and adopted notional thickness",
                f"Result: k₂ = {k2:.3f}",
            ],
            status_kind=None,
            calc_md=render_k2(),
        )

    # Step 1: Creep coefficient at time t
    def render_phi_cc_t():
        return rf"""
**Summary**

| Quantity | Value |
|----------|-------|
| Basic creep coefficient φ_cc,b | {phi_cc_b:.2f} |
| Time-development factor k₂ | {k2:.3f} |
| Age-at-loading factor k₃ | {k3:.3f} |
| Environment factor k₄ | {k4:.2f} |
| High-strength factor k₅ | {k5:.3f} |
| Non-linear creep factor k₆ | {k6:.3f} |
| **Design creep coefficient φ_cc(t)** | **{phi_cc_t:.2f}** |

**Purpose**

Compute the **design creep coefficient** at time $t$:

\[
\varphi_{{cc}}(t) = k_2 k_3 k_4 k_5 k_6 \, \varphi_{{cc,b}}
\]

**Inputs**

- Concrete strength: $f'_c = {fc:.1f}\,\text{{MPa}}$
- Environment: **{env_option}**
- Age at loading: $\tau = {age_at_loading:.0f}\,\text{{days}}$
- Time after loading: $t = {t_creep:.0f}\,\text{{days}}$
- Notional thickness for tables: $t_h = {th_table:d}\,\text{{mm}}$
- Governing sustained SLS moment: $M_{{sust}} = {sustained_mstar:.2f}\,\text{{kNm}}$
- Concrete compression fibre: {sustained_fibre}
- Section modulus at compression fibre: $Z_{{comp}} = {sustained_z:.2e}\,\text{{mm}}^3$
- Sustained concrete stress: $\sigma_{{cs}} = {sigma0:.2f}\,\text{{MPa}}$
- Sustained stress ratio (derived): $\sigma_{{cs}}/f'_{{c}} = {stress_ratio:.3f}$

**Basic creep coefficient** (Table 3.1.8.2)

\[
\varphi_{{cc,b}} \approx {phi_cc_b:.2f}
\]

**Factors**

- $k_2(t, t_h) \approx {k2:.3f}$ (Fig. 3.1.8.3)
- $k_3(\tau) = 2.7/[1 + \ln(\tau)] \approx {k3:.3f}$
- $k_4$ (environment factor) $= {k4:.2f}$
- $k_5$ (high-strength modification) $= {k5:.3f}$
- $k_6$ (non-linear creep for high stress) $= {k6:.3f}$

**Substitution**

\[
\varphi_{{cc}}(t)
= {k2:.3f} \times {k3:.3f} \times {k4:.2f} \times {k5:.3f} \times {k6:.3f}
\times {phi_cc_b:.2f}
\approx {phi_cc_t:.2f}
\]

**Result**

Design creep coefficient at $t = {t_creep:.0f}$ days:

\[
\varphi_{{cc}}(t) \approx {phi_cc_t:.2f}
\]

_Ref: AS 3600:2018 Cl. 3.1.8.3; Tables 3.1.8.2 & 3.1.8.3; Fig. 3.1.8.3._
"""

    def phi_cc_t_info_fn():
        with info_i_button(help_text="Factor explanations"):
            st.markdown(rf"""
**Factor explanations:**

• **k₄ (environment factor):** Comes from selected environment class per AS 3600 tables. Not user-entered directly.

• **k₅ (high-strength modification):** Derived from concrete strength f'c. Often equals 1.0 for normal-strength concrete.

• **k₆ (non-linear creep factor):** Derived from sustained stress ratio σ₀ over f'c. Equals 1.0 unless high sustained stress.

*These are code-defined modifiers derived from other inputs.*
""")

    # Step 2: Long-term tabulated creep coefficient (30 years)
    def render_phi_cc_table():
        return rf"""
**Summary**

| Quantity | Value |
|----------|-------|
| Computed value at t = {t_creep:.0f} days | φ_cc(t) = {phi_cc_t:.2f} |
| **Tabulated 30-year value** | **φ*_cc,table = {phi_cc_star_table:.2f}** |

**Purpose**

AS 3600:2018 Table 3.1.8.3 provides the **final 30-year creep coefficient**
for comparison with the computed value at time $t$.

**Table value**

For the same $f'_c$, environment and $t_h$, the **final 30-year coefficient**
from Table 3.1.8.3 is:

\[
\varphi^*_{{cc,\text{{table}}}} \approx {phi_cc_star_table:.2f}
\]

**Comparison**

- Computed value at $t = {t_creep:.0f}$ days: $\varphi_{{cc}}(t) \approx {phi_cc_t:.2f}$
- Tabulated long-term value (30 years): $\varphi^*_{{cc,\text{{table}}}} \approx {phi_cc_star_table:.2f}$

_Ref: AS 3600:2018 Table 3.1.8.3._
"""

    with creep_coefficient_tab:
        render_expandable_step(
            page_key="creep_coeff",
            step_id="creep_phi_cc_t",
            title="Creep coefficient at time t",
            summary_md=[
                "Check 2 — Compute design creep coefficient from basic coefficient and factors",
                rf"Result: $\varphi_{{cc}}(t) = {phi_cc_t:.2f}$ at $t = {t_creep:.0f}$ days",
            ],
            status_kind=None,
            calc_md=render_phi_cc_t(),
            info_render_fn=phi_cc_t_info_fn,
        )
        render_expandable_step(
            page_key="creep_coeff",
            step_id="creep_phi_cc_table",
            title="Long-term tabulated creep coefficient (30 years)",
            summary_md=[
                "Check 3 — AS table provides long-term value for comparison",
                rf"Table value (30 years): $\varphi^*_{{cc,\text{{table}}}} = {phi_cc_star_table:.2f}$",
            ],
            status_kind=None,
            calc_md=render_phi_cc_table(),
        )

    # Step 1: Sustained stress at loading σ₀
    def render_sigma0():
        return rf"""
**Summary**

| Quantity | Value |
|----------|-------|
| Governing sustained SLS moment M_sust | {sustained_mstar:.2f} kNm |
| Compression fibre | {sustained_fibre} |
| Section modulus at compression fibre Z_comp | {sustained_z:.2e} mm³ |
| **Sustained concrete stress σ_cs** | **{sigma0:.2f} MPa** |

**Purpose**

Derive sustained concrete compressive stress from the governing sustained SLS action and section response.

**Inputs**

- Governing sustained SLS moment: $M_{{sust}} = {sustained_mstar:.2f}\,\text{{kNm}}$
- Compression fibre section modulus: $Z_{{comp}} = {sustained_z:.2e}\,\text{{mm}}^3$

**Calculation**

\[
\sigma_{{cs}} = \frac{{M_{{sust}} \times 10^6}}{{Z_{{comp}}}}
\]

**Substitution**

\[
\sigma_{{cs}} = \frac{{{sustained_mstar:.2f}\times 10^6}}{{{sustained_z:.2e}}} \approx {sigma0:.2f}\,\text{{MPa}}
\]

**Result**

\[
\sigma_{{cs}} = {sigma0:.2f}\,\text{{MPa}}
\]

_Ref: AS 3600:2018 Cl. 3.1.8.1._
"""

    def sigma0_info_fn():
        with info_i_button(help_text="Design strength at loading (f'c,mi)"):
            st.markdown(rf"""
**Design strength at loading ($f'_{{c,mi}}$):**

$f'_{{c,mi}}$ represents the concrete compressive strength at the time of loading. In this calculation, it is approximated as $f'_c$ (the 28-day design strength) for simplicity. This approximation is reasonable when loading occurs near 28 days or when precise loading age data is not available.

In this app flow, sustained stress is derived from sustained action and section response:
$\sigma_{{cs}} = M_{{sust}}/Z_{{comp}}$, then the stress ratio is obtained from $\sigma_{{cs}}/f'_c$.

*Note: Compression is taken as positive magnitude in this calculation.*
""")

    # Step 2: Sustained stress ratio (derived)
    def render_stress_ratio():
        return rf"""
**Summary**

| Quantity | Value |
|----------|-------|
| Sustained concrete stress σ_cs | {sigma0:.2f} MPa |
| Concrete strength f'c | {fc:.1f} MPa |
| **Sustained stress ratio (derived)** | **{stress_ratio:.3f}** |

**Purpose**

Express sustained compressive stress as a ratio of concrete strength for use in the k₆ non-linear creep factor.

**Calculation**

\[
\text{{stress\_ratio}} = \frac{{\sigma_{{cs}}}}{{f'_c}}
\]

**Substitution**

\[
\text{{stress\_ratio}} = \frac{{{sigma0:.2f}}}{{{fc:.1f}}} = {stress_ratio:.3f}
\]

**Result**

\[
\text{{stress\_ratio}} = {stress_ratio:.3f}
\]
"""

    # Step 3: Creep strain ε_cc from creep coefficient
    def render_eps_cc():
        return rf"""
**Summary**

| Quantity | Value |
|----------|-------|
| Design creep coefficient φ_cc(t) | {phi_cc_t:.2f} |
| Sustained stress σ_cs | {sigma0:.2f} MPa |
| Modulus of elasticity E_c | {Ec:.0f} MPa |
| **Creep strain ε_cc** | **{eps_cc_micro:.1f} με** |

**Purpose**

Convert creep coefficient $\varphi_{{cc}}(t)$ to creep strain under sustained stress $\sigma_{{cs}}$.

**Inputs**

- Design creep coefficient at time $t$:

  \[
  \varphi_{{cc}}(t) \approx {phi_cc_t:.2f}
  \]
- Sustained stress: $\sigma_{{cs}} = {sigma0:.2f}\,\text{{MPa}}$ (from previous step)
- Modulus of elasticity: $E_c = {Ec:.0f}\,\text{{MPa}}$

**Calculation**

\[
\varepsilon_{{cc}} = \varphi_{{cc}}(t)\, \frac{{\sigma_{{cs}}}}{{E_c}}
\]

**Substitution**

\[
\varepsilon_{{cc}}
= {phi_cc_t:.2f} \times \frac{{{sigma0:.2f}}}{{{Ec:.0f}}}
\approx {eps_cc:.3e}
\]

Expressed in microstrain:

\[
\varepsilon_{{cc}} \approx {eps_cc_micro:.1f} \times 10^{{-6}} = {eps_cc_micro:.1f}\,\mu\varepsilon
\]

**Result**

\[
\varepsilon_{{cc}} = {eps_cc_micro:.1f}\,\mu\varepsilon
\]

_Ref: AS 3600:2018 Cl. 3.1.8.1._
"""

    with creep_strain_tab:
        render_expandable_step(
            page_key="creep_strain",
            step_id="creep_sigma0",
            title="Sustained stress at loading σ₀",
            summary_md=[
                "Check 4.1 — Derive sustained concrete compressive stress from sustained action and section modulus",
                rf"Result: $\sigma_{{cs}} = {sigma0:.2f}$ MPa",
            ],
            status_kind=None,
            calc_md=render_sigma0(),
            info_render_fn=sigma0_info_fn,
        )
        render_expandable_step(
            page_key="creep_strain",
            step_id="creep_stress_ratio",
            title="Sustained stress ratio (derived)",
            summary_md=[
                "Check 4.2 — Derive sustained stress ratio from sustained stress and concrete strength",
                rf"Result: stress_ratio = {stress_ratio:.3f}",
            ],
            status_kind=None,
            calc_md=render_stress_ratio(),
        )
        render_expandable_step(
            page_key="creep_strain",
            step_id="creep_eps_cc",
            title="Creep strain ε_cc at time t",
            summary_md=[
                "Check 4.3 — Convert creep coefficient to creep strain under sustained stress",
                rf"Result: $\varepsilon_{{cc}} = {eps_cc_micro:.1f}$ με",
            ],
            status_kind=None,
            calc_md=render_eps_cc(),
        )


__all__ = ["render_creep_checks"]
