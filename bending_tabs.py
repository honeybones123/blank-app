import math
import pandas as pd
import matplotlib.pyplot as plt
import streamlit as st

from bending_diagrams import (
    _plot_strain_profile,
    _make_uls_stress_block_figure,
    _make_uls_force_model_figure,
    _make_sls_stress_block_figure,  # still used elsewhere, untouched
)
from bending_core import _fmt, _layout_bars_in_rows, _stress_strain_state
from state_and_helpers import get_param, update_results
from ui.diagrams.stress_strain_diagram import (
    make_sls_32_stress_block_figure as _shared_make_sls_32_stress_block_figure,
    make_sls_strain_distribution_figure as _shared_make_sls_strain_distribution_figure,
)
from widgets_helpers import calcbox, clickable_calcbox, render_step, render_jumpable_step, apply_step_expander_css, step_expander_calcbox, info_i_button, render_plotly_diagram, render_pyplot_diagram


# ============================================================
#  LOCAL HELPER – CALCBOX WITH LATEX SUPPORT
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
#  LOCAL HELPER – SLS STRESS FIGURE FOR 3.2 ONLY
# ============================================================
def _make_sls_stress_block_figure_32(D_mm, d_mm, dn_mm, layers_tension):
    """Compatibility wrapper for the shared SLS 3.2 stress-block figure."""
    return _shared_make_sls_32_stress_block_figure(D_mm, d_mm, dn_mm, layers_tension)


# ============================================================
#  TAB 1 – ULS (UNCHANGED LOGIC, TIDIED CALC BOXES)
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
    Tab 1 – ULS step-by-step.
    
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

    if phi_Mu_cap > 0 and d and Ast:

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
        Mu_nom_uls = T * z_uls / 1e6
        phi_Mu_cap_uls = phi * Mu_nom_uls

        # Concrete force at ULS (using a = γ d_n)
        C_N = alpha2_uls * fc * b * a_uls  # N

        # --------------------------------------------------
        # 1.1 Stress-block parameters (α2 and γ)
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
$\\alpha_2 = {alpha2_uls:.3f}$, $\\gamma = {gamma_uls:.3f}$ (to be used in Sections 1.2–1.6).
"""
        
        def diagram_1_1():
            info_1_1()
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
            with info_i_button(help_text="Stress block parameters"):
                st.markdown(
                    f"""
**Check 1.1 — Stress Block Parameters α₂ and γ**

This check determines the equivalent rectangular stress block factors α₂ and γ used for Ultimate Limit State flexural design.

At ultimate load, the concrete compression stress is not uniform. The real stress distribution is nonlinear, with high compression near the extreme compression face and reducing stress towards the neutral axis.

AS 3600 simplifies this nonlinear stress distribution into an equivalent rectangular stress block [1].

α₂ adjusts the intensity, or height, of the equivalent compression stress block.

Equivalent stress = α₂ × f'c

γ adjusts the depth of the equivalent compression stress block.

Stress block depth, a = γ × dn

Together, α₂ and γ allow the simplified rectangular block to represent the concrete compression force used in the flexural capacity calculation [1].

References:  
[1] AS 3600:2018, Clause 8.1.3 — Equivalent rectangular stress block.
"""
                )

        step_expander_calcbox(
            uid="bending_uls_1_1",
            summary_line=f"1.1 Stress-block parameters (α₂ and γ) | Result: α₂ = {alpha2_uls:.3f}, γ = {gamma_uls:.3f}",
            details_md=section11_details,
            status=None,
            diagram_fn=diagram_1_1,
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
            with info_i_button(help_text="Concrete compressive force"):
                st.markdown(
                    f"""
**Check 1.4 — Concrete Compressive Force C**

This check calculates the resultant concrete compressive force C developed in the compression zone of the beam at Ultimate Limit State.

The force C acts over the equivalent rectangular stress block area defined using the AS 3600 rectangular stress block model [1].

C = α₂ × f'c × b × a

where:

α₂ × f'c = simplified average concrete compressive stress

b × a = equivalent rectangular stress block area

So the equation can be understood as:

Concrete compressive force = average compressive stress × stress block area

This is a simplified design model, not a literal picture of the exact stress distribution inside the concrete. The actual concrete stress distribution is nonlinear, but AS 3600 permits it to be represented using an equivalent rectangular stress block for design [1].

The concrete compression force is then balanced against the tensile force in the reinforcement to satisfy internal force equilibrium [2].

C = T

Once equilibrium is achieved, the internal force couple is used to determine the section moment capacity [2].

References:  
[1] AS 3600:2018, Clause 8.1.3 — Equivalent rectangular stress block.  
[2] AS 3600:2018, Clause 8.1 — Ultimate strength of members subjected to bending.
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
            with info_i_button(help_text="Steel area and tensile force"):
                st.markdown(
                    f"""
**Check 1.2 — Steel Area and Tensile Force T**

This check calculates the tensile force developed by the longitudinal reinforcement at Ultimate Limit State (ULS).

As the beam bends, the concrete below the neutral axis cracks and is assumed to carry no tensile force. Instead, the entire tensile force is resisted by the reinforcing steel [1].

Provided sufficient ductility is available, AS 3600 assumes the tensile reinforcement reaches its yield strength at ultimate capacity [2]. The tensile force is therefore calculated as:

T = Ast × fsy

where:

Ast = total area of tensile reinforcement

fsy = yield strength of the reinforcing steel

This equation can be understood as:

Tensile force = steel area × steel yield stress

The tensile force acts through the centroid of the tensile reinforcement and forms one half of the internal force couple resisting bending. For equilibrium, the tensile force must balance the concrete compressive force [2]:

T = C

Once equilibrium is achieved, the distance between the concrete compression force and the steel tensile force forms the internal lever arm used to calculate the section's ultimate moment capacity.

References:  
[1] AS 3600:2018, Clause 8.1.1 — Concrete in tension neglected at Ultimate Limit State.  
[2] AS 3600:2018, Clause 8.1 — Ultimate strength of members subjected to bending using internal force equilibrium.
"""
                )
        
        step_expander_calcbox(
            uid="bending_uls_1_3",
            summary_line=f"1.2 Steel area and tension force $T$ | Result: T = {T/1000.0:.1f} kN",
            details_md=section13_details,
            status=None,
            diagram_fn=info_1_3,
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

        step_expander_calcbox(
            uid="bending_uls_1_4",
            summary_line=f"1.3 Neutral axis depth $d_n$ and block depth $a$ | Result: d_n = {dn:.1f} mm, a = {a_uls:.1f} mm",
            details_md=section14_details,
            status=None,
            diagram_fn=diagram_1_4,
        )

        step_expander_calcbox(
            uid="bending_uls_1_2",
            summary_line=f"1.4 Concrete compressive force $C$ | Result: C = {C_kN:.1f} kN",
            details_md=section12_details,
            status=None,
            diagram_fn=info_1_2,
        )

        # --------------------------------------------------
        # 1.5 Strain compatibility (εcu and εs)
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
            else "= \\text{—}"
        )
        result_eps_tex = (
            f"{eps_s_tension:.5f}"
            if not math.isnan(eps_s_tension)
            else r"\text{—}"
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
            with info_i_button(help_text="Strain compatibility and steel yield"):
                st.markdown(
                    """
**Strain Compatibility (εcu and εs) — Why This Calculation Is Required**

This check verifies that the tensile reinforcement has reached its yield strain at the Ultimate Limit State (ULS) using the strain compatibility method required by AS 3600 [1].

At ultimate capacity, AS 3600 assumes the concrete at the extreme compression fibre reaches an ultimate compressive strain of εcu = 0.003 [1]. It is also assumed that plane sections remain plane after bending, meaning the strain varies linearly through the depth of the section [2].

Using the neutral axis depth determined in the previous check, the strain at any point within the section can be determined from the geometry of the strain diagram. The tensile steel strain is therefore calculated as:

εs = εcu × (d − dn) / dn

where:

εcu = ultimate concrete compressive strain  
d = effective depth to the tensile reinforcement  
dn = neutral axis depth

The calculated steel strain is then compared with the steel yield strain:

εsy = fsy / Es

If:

εs ≥ εsy

the reinforcement has reached yield, confirming that the assumption made in the tensile force calculation,

T = Ast × fsy

is valid [2].

If εs < εsy, the reinforcement has not yielded, and the tensile force must instead be determined from the actual steel stress obtained from the steel stress-strain relationship rather than assuming the full yield stress.

This check therefore confirms that the assumed stress distribution and internal force calculations are consistent with the actual strain profile of the section and that the reinforcement has developed its design yield strength before the flexural capacity is calculated.

**References**

[1] AS 3600:2018, Clause 3.1.7 — Ultimate concrete compressive strain (εcu = 0.003).  

[2] AS 3600:2018, Clause 8.1 — Ultimate strength of members subjected to bending using strain compatibility and internal force equilibrium.
"""
                )

        def diagram_1_5():
            info_1_5()
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
                f"1.5 Strain compatibility ($\\varepsilon_{{cu}}$ and $\\varepsilon_s$) | Result: "
                f"$\\varepsilon_s = {eps_s_tension:.5f}$"
                if not math.isnan(eps_s_tension)
                else "1.5 Strain compatibility ($\\varepsilon_{{cu}}$ and $\\varepsilon_s$) | Result: —"
            ),
            details_md=section14a_details,
            status=None,
            diagram_fn=diagram_1_5,
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
                st.markdown("**Info:**")
            with col_ku_info:
                with info_i_button(help_text="What does the neutral-axis ratio mean?"):
                    st.markdown(
                        r"""
### **Neutral-Axis Ratio \(k_u\) — Meaning & Importance**

The ratio  

\[

k_u = \frac{d_n}{d}

\]  

describes **how deep the neutral axis is** relative to the effective depth.

---

#### **1. Indicator of section behaviour**

- **Low \(k_u\)** → shallow neutral axis → large tension zone → *steel governs* → ductile.  

- **High \(k_u\)** → deep neutral axis → large compression zone → *concrete governs* → brittle.

---

#### **2. Direct link to ductility**

Because strain varies linearly:

- Low \(k_u\)** → steel yields first → **ductile, predictable failure**  

- High \(k_u\)** → concrete crushes first → **brittle failure**

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
$k_u = {ku:.3f} \\le {ku_lim:.2f}$ → {"✓ PASS" if ku_ok else "✗ FAIL" if ku_ok is False else "—"}

**Result:**  
Neutral axis ratio $k_u = {ku:.3f}$.
"""
        
        step_expander_calcbox(
            uid="bending_uls_1_5",
            summary_line=f"1.6 Neutral axis ratio $k_u$ | Result: k_u = {ku:.3f} vs k_{{u,lim}} = {ku_lim:.2f} → {'PASS' if ku_ok else 'FAIL' if ku_ok is False else '—'}",
            details_md=section15_details,
            status=ku_status,
            content_before=content_1_5,
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

        step_expander_calcbox(
            uid="bending_uls_1_6",
            summary_line=f"1.7 Lever arm $z$ and moment capacity | Result: φM_{{u,cap}} = {phi_Mu_cap_uls:.2f} kNm",
            details_md=section16_details,
            status=None,
            diagram_fn=diagram_1_6,
        )


        # --------------------------------------------------
        # 1.8 Flexural capacity check (Mu* ≤ φMu,cap)
        # --------------------------------------------------
        Mu_star = float(Mu_star_override) if Mu_star_override is not None else get_param("Mu_star", 0.0)
        if Mu_star is not None and phi_Mu_cap_uls > 0:
            Mu_ok = Mu_star <= phi_Mu_cap_uls
            Mu_status = "pass" if Mu_ok is True else "fail" if Mu_ok is False else None
            
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
{Mu_star:.2f} \\le {phi_Mu_cap_uls:.2f} \\quad \\Rightarrow \\quad \\text{{{"✓ PASS" if Mu_ok else "✗ FAIL"}}}
$$

**Utilisation:**  
$\\text{{Utilisation}} = \\frac{{M_u^*}}{{\\phi M_{{u,cap}}}} = \\frac{{{Mu_star:.2f}}}{{{phi_Mu_cap_uls:.2f}}} = {Mu_star/phi_Mu_cap_uls:.3f}$

---

**Result:**  
{"Design moment is within capacity." if Mu_ok else "Design moment exceeds capacity — increase reinforcement or section size."}
"""
            
            step_expander_calcbox(
                uid="bending_uls_1_7",
                summary_line=f"1.8 Flexural capacity check | Result: M_u* = {Mu_star:.2f} kNm vs φM_{{u,cap}} = {phi_Mu_cap_uls:.2f} kNm → {'PASS' if Mu_ok else 'FAIL'}",
                details_md=section17_details,
                status=Mu_status,
            )

    else:
        st.info("Capacity cannot be evaluated – check geometry / reo inputs.")


# ============================================================
#  TAB 2 – Minimum Strength (UNCHANGED LOGIC, TIDIED TEXT)
# ============================================================
def render_min_strength_tab(top_results, b, D, fc, fsy, Ast, summary_mode: bool = False, jump_uid: str | None = None):
    """Minimum strength requirements (summary_mode parameter ignored, kept for compatibility)."""
    """
    Tab 2 – Minimum strength requirements.
    
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
        summary_line=f"2.1 Concrete flexural tensile strength $f_{{ct,f}}$ | Result: f_{{ct,f}} = {fctf_as:.3f} MPa",
        details_md=section21_details,
        status=None,
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
        summary_line=f"2.2 Gross section modulus $Z_g$ | Result: Z_g = {Zg:,.3e} mm³",
        details_md=section22_details,
        status=None,
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
        summary_line=f"2.3 Cracking moment $M_{{cr}}$ | Result: M_{{cr}} = {Mcr_as:.2f} kNm",
        details_md=section23_details,
        status=None,
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
$\\phi M_{{u,cap}} = {phi_Mu_cap:.2f} \\ge {Mu_min_as:.2f} = (M_{{u,cap}})_{{min}}$ → {"✓ PASS" if Mu_min_ok else "✗ FAIL" if Mu_min_ok is False else "—"}

**Result:**  
Minimum required design capacity $(M_{{u,cap}})_{{min}} = {Mu_min_as:.2f}$ kNm.
"""
    
    step_expander_calcbox(
        uid="bending_min_2_4",
        summary_line=f"2.4 Minimum required design capacity $(M_{{u,cap}})_{{min}}$ | Result: φM_{{u,cap}} = {phi_Mu_cap:.2f} kNm vs (M_{{u,cap}})_{{min}} = {Mu_min_as:.2f} kNm → {'PASS' if Mu_min_ok else 'FAIL' if Mu_min_ok is False else '—'}",
        details_md=section24_details,
        status=Mu_min_status,
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
- Provided area: $A_{{st}} = {Ast:.1f}$ mm²

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
$A_{{st}} = {Ast:.1f} \\ge {Ast_min_as:.1f} = A_{{st,min}}$ → {"✓ PASS" if As_ok else "✗ FAIL" if As_ok is False else "—"}

**Result:**  
Minimum tensile steel area $A_{{st,min}} = {Ast_min_as:.1f}$ mm².
"""
    
    step_expander_calcbox(
        uid="bending_min_2_5",
        summary_line=f"2.5 Minimum tensile reinforcement $A_{{st,min}}$ | Result: A_{{st}} = {Ast:.1f} mm² vs A_{{st,min}} = {Ast_min_as:.1f} mm² → {'PASS' if As_ok else 'FAIL' if As_ok is False else '—'}",
        details_md=section25_details,
        status=As_status,
    )


# ============================================================
#  TAB 3 – SLS (UPDATED WITH LAYERS + COMP STEEL)
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
    Tab 3 – SLS cracked-section teaching model.
    
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

    # --- Bottom tension layers (T1, T2, ...) — sagging ---
    if (not hogging_sls) and nb_bot > 0 and db_bot > 0 and cover_bot > 0:
        # Same helper as section diagram → rows of bars
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
            st.markdown("**Info:**")
        with col_n_info:
            with info_i_button(help_text="What does the modular ratio mean?"):
                st.markdown(
                    r"""
### **Modular Ratio \(n = E_s / E_c\) — What it Means**

The modular ratio

\[
n = \frac{E_s}{E_c}
\]

compares **steel stiffness** to **concrete stiffness**.

---

#### 1. Converts steel into 'equivalent concrete'

Because steel is much stiffer than concrete, one mm² of steel carries
more force than one mm² of concrete at the same strain.

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

so \(n\) is usually in the range **6–10**.
"""
                )

    section31_details = f"""
*Purpose: Compute the modular ratio and transformed steel areas for each layer.*  

**Inputs:**  

- $E_s = {Es:.0f}$ MPa  
- $E_c = {Ec:.0f}$ MPa  
- Concrete modulus derivation:  
  $$
  E_c = 4700\sqrt{{f'_c}}
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
                    "A_s (mm²)": As_i,
                    "n A_s (mm²)": n_sls * As_i,
                }
            )
        if include_comp and comp_layer is not None:
            As_c = comp_layer["As"]
            layer_rows.append(
                {
                    "Layer": comp_layer["name"],
                    "Description": comp_layer["label"],
                    "Depth y (mm)": comp_layer["y"],
                    "A_s (mm²)": As_c,
                    "n A_s (mm²)": n_sls * As_c,
                }
            )
        st.table(pd.DataFrame(layer_rows))
    
    step_expander_calcbox(
        uid="bending_sls_3_1",
        summary_line=f"3.1 Modular ratio $n = E_s / E_c$ | Result: n = {Es/Ec:.2f}",
        details_md=section31_details,
        status=None,
        content_before=content_3_1,
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
    
    step_expander_calcbox(
        uid="bending_sls_3_2",
        summary_line=f"3.2 Neutral axis depth $d_n$ (cracked section) | Result: d_n = {dn_sls:.1f} mm",
        details_md=section32_details,
        status=None,
        diagram_fn=diagram_3_2,
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

    step_expander_calcbox(
        uid="bending_sls_3_3",
        summary_line=f"3.3 Cracked moment of inertia $I_{{cr}}$ | Result: I_cr = {Icr:,.2f} mm⁴",
        details_md=section33_details,
        status=None,
        diagram_fn=None,
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

    step_expander_calcbox(
        uid="bending_sls_3_4",
        summary_line=f"3.4 Curvature at service moment | Result: κ = {kappa:.3e} mm⁻¹",
        details_md=section34_details,
        status=None,
        diagram_fn=None,
    )

    # --------------------------------------------------
    # 3.5 Strain distribution ε(y) = κ (y − d_n)
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
        strain_rows.append({"Layer": name, "Depth y (mm)": yi, "ε": eps})

    df_eps = pd.DataFrame(strain_rows)

    # Find max strain for summary line
    if strain_rows:
        max_strain_abs = max([abs(row["ε"]) for row in strain_rows])
        max_strain_row = next((row for row in strain_rows if abs(row["ε"]) == max_strain_abs), None)
        max_strain_label = max_strain_row["Layer"] if max_strain_row else ""
        max_strain_val = max_strain_row["ε"] if max_strain_row else 0.0
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

    step_expander_calcbox(
        uid="bending_sls_3_5",
        summary_line=f"3.5 Strain distribution ε(y) = κ(y − d_n) | Max strain: {max_strain_label} = {max_strain_val:.5f}",
        details_md=section35_details,
        status=None,
        diagram_fn=_sls_3_5_diagram,
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
                "ε_s": eps_s,
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
                "ε_s": eps_s_c,
                "f_s (MPa)": fs_c,
            }
        )

    df_steel = pd.DataFrame(steel_rows)

    # Example substitution for first tension layer (if available)
    example_eps = ""
    example_fs = ""
    if steel_rows and len(steel_rows) > 0:
        first_row = steel_rows[0]
        example_eps = f"\\varepsilon_{{s,1}} = {first_row['ε_s']:.5f}"
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

    step_expander_calcbox(
        uid="bending_sls_3_6",
        summary_line=f"3.6 Steel stresses at SLS (each layer) | Max stress: {max_fs_label} = {max_fs:.1f} MPa",
        details_md=section36_details,
        status=None,
        diagram_fn=None,
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
    # (no widgets touched – these are read-only “output” values)
    st.session_state["bending_sls_dn"] = float(dn_sls)
    st.session_state["bending_sls_kappa"] = float(kappa)

    if deepest is not None:
        eps_outer = float(deepest["ε_s"])
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
            eps_s_control = float(deepest["ε_s"])
            y_control = float(deepest["Depth y (mm)"])

    # Also compute top-fibre SLS strain from κ and d_n,sls
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
            summary_line=f"3.7 Link to crack-width calculation | f_s,ser ≈ {fs_tension:.1f} MPa",
            details_md=section37_details,
            status=None,
            diagram_fn=None,
        )
        
        # Publish for Crack Width page – service tensile steel stress at SLS
        from bending_core import compute_sigma_s_sls_for_crack
        compute_sigma_s_sls_for_crack(publish=True)
    else:
        st.info(
            "No tension layer found for crack-width link – check the SLS inputs."
        )
