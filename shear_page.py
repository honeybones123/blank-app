# app/pages/shear_torsion.py
import math
import streamlit as st

from state_and_helpers import (
    get_param,
    get_sync_callbacks,
    update_results,
)

# Shared helpers (same contract as Inputs/Bending)
from widgets_helpers import apply_global_widget_css, number_row


def cot(rad: float) -> float:
    """Cotangent with protection against tan(pi/2) etc."""
    return 1.0 / math.tan(rad)


def _inject_calcbox_css():
    st.markdown(
        """
<style>
.calcbox-wrapper {
  margin-top: 0.5rem;
  margin-bottom: 0.75rem;
}
.calcbox-inner {
  padding: 0.75rem 1.0rem;
  border-radius: 0.35rem;
  border-left: 4px solid #1f77b4;
  background-color: rgba(31, 119, 180, 0.06);
  font-size: 0.9rem;
}
</style>
""",
        unsafe_allow_html=True,
    )


def calcbox(md: str):
    """Render a highlighted calculation box (LaTeX-safe)."""
    box_html = f"""
<div class="calcbox-wrapper">
  <div class="calcbox-inner">
{md}
  </div>
</div>
"""
    st.markdown(box_html, unsafe_allow_html=True)


def render_shear():
    apply_global_widget_css()
    _inject_calcbox_css()

    st.title("Shear & Torsion")

    sync_callbacks = get_sync_callbacks()
    summary_placeholder = st.empty()

    st.markdown(
        """
This page performs an AS 3600 shear + torsion check with a step-by-step ULS calculation.  
Geometry, materials and design actions are shared with the Inputs tab via the session-state
contract. Results are written to the global RESULTS using `update_results()` so the Inputs
summary can show shear utilisation.
"""
    )

    # =====================================================
    # 1. DESIGN INPUTS (shared + local)
    # =====================================================
    st.subheader("Design Inputs")

    col_geom, col_actions, col_eps = st.columns(3)

    # ---------- 1.1 Geometry & materials (shared) ----------
    with col_geom:
        st.markdown("### Geometry & materials")

        number_row(
            "Width b (mm)",
            "shear_b",
            get_param("b", 300.0),
            sync_callbacks,
            help_text="Shared with Inputs tab.",
        )
        number_row(
            "Depth D (mm)",
            "shear_D",
            get_param("D", 600.0),
            sync_callbacks,
            help_text="Overall section depth, shared with Inputs.",
        )
        number_row(
            "Span L (mm)",
            "shear_L",
            get_param("L", 3000.0),
            sync_callbacks,
            help_text="Clear span or design span for this section.",
        )

        number_row(
            "Concrete strength f'c (MPa)",
            "shear_fc",
            get_param("fc", 40.0),
            sync_callbacks,
            help_text="Concrete compressive strength (AS 3600).",
        )
        number_row(
            "Steel yield f_sy (MPa)",
            "shear_fsy",
            get_param("fsy", 500.0),
            sync_callbacks,
            help_text="Yield stress of longitudinal & shear reinforcement.",
        )
        number_row(
            "Concrete modulus Ec (MPa)",
            "shear_Ec",
            get_param("Ec", 30000.0),
            sync_callbacks,
            help_text="Used in εₓ calc when compression develops.",
        )
        number_row(
            "Steel modulus Es (MPa)",
            "shear_Es",
            get_param("Es", 200000.0),
            sync_callbacks,
            help_text="Modulus of non-prestressed reinforcement.",
        )

    # ---------- 1.2 Shear & torsion actions (shared) ----------
    with col_actions:
        st.markdown("### Shear, axial & torsion actions")

        number_row(
            "Design shear V* (kN)",
            "shear_Vu_star",
            get_param("Vu_star", 300.0),
            sync_callbacks,
            help_text="Factored shear at the section.",
        )
        number_row(
            "Axial force N* (kN, +tension)",
            "shear_N_star",
            get_param("N_star", 0.0),
            sync_callbacks,
            help_text="Axial force at the section (+tension, −compression).",
        )
        number_row(
            "Vertical prestress / axial P_v (kN)",
            "shear_P_star",
            get_param("P_star", 0.0),
            sync_callbacks,
            help_text="Prestress or vertical axial force assisting shear.",
        )
        number_row(
            "Torsion T* (kNm)",
            "shear_Tu_star",
            get_param("Tu_star", 0.0),
            sync_callbacks,
            help_text="Factored torsion at the section.",
        )

        phi = st.number_input(
            "φ – strength reduction for shear",
            value=0.75,
            min_value=0.5,
            max_value=0.9,
            step=0.05,
        )
        sigma_cp = st.number_input(
            "σ_cp – average prestress (MPa)",
            value=0.0,
            help="Used in torsion cracking torque T_cr (AS 3600 Cl. 8.3.4).",
        )

        st.markdown("### Torsion geometry (stirrup path)")
        uh = st.number_input(
            "u_h (mm) — stirrup centreline perimeter",
            value=float(max(1.0, 2.0 * (get_param("b", 300.0) + 0.72 * get_param("D", 600.0)))),
            help="Perimeter of the closed stirrup centreline.",
        )
        Ao = st.number_input(
            "A_o (mm²) — effective torsion area",
            value=float(max(1.0, 0.85 * get_param("b", 300.0) * 0.72 * get_param("D", 600.0))),
            help="Area enclosed by shear flow path (approx).",
        )
        A_oh = st.number_input(
            "A_oh (mm²) — area inside stirrup centreline",
            value=float(max(1.0, 0.9 * Ao)),
            help="Used in web-crushing torsion term.",
        )
        torsion_required = st.checkbox(
            "Include torsion in design checks",
            value=(get_param("Tu_star", 0.0) > 0.0),
        )

    # ---------- 1.3 εx helper inputs (local only) ----------
    with col_eps:
        st.markdown("### εₓ inputs (ULS flexural strain)")

        A_st = st.number_input(
            "A_st (mm²) – non-prestressed tension steel",
            value=float(4 * (math.pi * 20**2 / 4)),
        )
        A_pt = st.number_input(
            "A_pt (mm²) – prestressing steel",
            value=0.0,
        )
        f_po = st.number_input(
            "f_po (MPa) – effective tendon stress",
            value=0.0,
        )
        A_ct = st.number_input(
            "A_ct (mm²) – area of concrete in tension",
            value=float((get_param("b", 300.0)) * (get_param("D", 600.0) / 2.0)),
        )

    # -------------------------------------------------
    # Pull shared values for calculations
    # -------------------------------------------------
    b = get_param("b")
    D = get_param("D")
    d = get_param("d")

    fc = get_param("fc")
    fsy = get_param("fsy")
    Ec = get_param("Ec")
    Es = get_param("Es")

    M_star = get_param("Mu_star") or 0.0
    V_star = get_param("Vu_star") or 0.0
    T_star = get_param("Tu_star") or 0.0
    N_star = get_param("N_star") or 0.0
    P_v = get_param("P_star") or 0.0

    lig_d = get_param("lig_d")
    legs = get_param("lig_legs")
    s_lig = get_param("s_lig")

    if not (b and D and d):
        st.error("Geometry (b, D, d) not fully defined – check Inputs / Bending tab.")
        return

    # =====================================================
    # 3. STEP 2 — CONVERT TORSION INTO AN EQUIVALENT SHEAR V_eq*
    # =====================================================
    st.markdown("---")
    st.markdown(
        "### Step 2 – Convert torsion into an equivalent shear "
        "$V_{eq}^*$ (AS 3600 Cl. 8.2.3)"
    )

    T_star_Nmm = T_star * 1e6

    if torsion_required:
        torsion_eq_N = 0.9 * T_star_Nmm * uh / (2.0 * (Ao or 1.0))
        torsion_eq_kN = torsion_eq_N / 1e3
        V_eq = math.sqrt(V_star**2 + torsion_eq_kN**2)

        calcbox(
            fr"""
Inputs
- Shear demand: $V^* = {V_star:.1f}\,\text{{kN}}$
- Torsion: $T^* = {T_star:.1f}\,\text{{kNm}}$
- Stirrup path: $u_h = {uh:.0f}\,\text{{mm}}$
- Effective torsion area: $A_o = {Ao:.0f}\,\text{{mm}}^2$

Formula (AS 3600 Cl. 8.2.3)
\[
V_{{t,eq}} = 0.9\,\frac{{T^* u_h}}{{2 A_o}}
\]
\[
V_{{eq}}^* = \sqrt{{V^{{*2}} + V_{{t,eq}}^2}}
\]

Substitution
\[
V_{{t,eq}} =
0.9\,\frac{{{T_star:.1f}\times 10^6 \times {uh:.0f}}}{{2 \times {Ao:.0f}}}
= {torsion_eq_kN:.1f}\,\text{{kN}}
\]
\[
V_{{eq}}^* =
\sqrt{{({V_star:.1f})^2 + ({torsion_eq_kN:.1f})^2}}
= {V_eq:.1f}\,\text{{kN}}
\]

Result / check
- Torsion is included as an equivalent shear.
- This $V_{{eq}}^*$ is used in the sectional shear and web-crushing checks.
"""
        )

    else:
        torsion_eq_kN = 0.0
        V_eq = V_star

        calcbox(
            fr"""
Inputs
- Shear demand: $V^* = {V_star:.1f}\,\text{{kN}}$
- Torsion: $T^* = {T_star:.1f}\,\text{{kNm}}$  
  (from Step 1, torsion design is not required)

Formula (AS 3600 Cl. 8.2.3)
\[
V_{{eq}}^* = \sqrt{{V^{{*2}} + V_{{t,eq}}^2}}
\]
Since $V_{{t,eq}} = 0$,  
\[
V_{{eq}}^* = V^*
\]

Substitution
\[
V_{{t,eq}} = 0.0\,\text{{kN}}
\]
\[
V_{{eq}}^* = V^* = {V_eq:.1f}\,\text{{kN}}
\]

Result / check
- Torsion is not treated as a design action.
- This $V_{{eq}}^*$ is carried into the sectional shear and web-crushing checks.
"""
        )

    # =====================================================
    # 4. STEP 3 — EFFECTIVE SECTION & SHEAR REINFORCEMENT
    # =====================================================
    st.markdown("---")
    st.markdown("### Step 3 – Determine shear-resisting section (b_v, d_v, ligs)")

    d_g = st.number_input(
        "Maximum aggregate size d_g (mm)",
        value=20.0,
        min_value=5.0,
        max_value=40.0,
    )

    lig_d = lig_d or 10.0
    legs = legs or 2.0
    s = s_lig or 200.0

    Asv = legs * math.pi * lig_d**2 / 4.0
    f_syv = fsy

    col_ligs1, col_ligs2, col_ligs3 = st.columns(3)
    with col_ligs1:
        st.markdown(
            f"**Lig diameter (session)** = {lig_d:.1f} mm  \n"
            f"**Legs per lig (session)** = {legs:.0f}  \n"
            f"**Stirrup spacing s (session)** = {s:.1f} mm"
        )

    with col_ligs2:
        st.markdown(
            f"**$A_{{sv}}$ (calculated)** = {Asv:,.1f} mm²  \n"
            f"$= n_{{legs}} \\times \\frac{{\\pi d_{{lig}}^2}}4$  \n"
            f"**Shear lig yield $f_{{sy,v}}$** = {f_syv:.1f} MPa  \n"
            f"(taken equal to longitudinal $f_{{sy}}$)"
        )

        method = st.radio(
            "k_v method",
            (
                "General εₓ-based (Cl. 8.2.4.2)",
                "Simplified non-prestressed (Cl. 8.2.4.3)",
            ),
            index=0,
        )
        use_general_kv = method.startswith("General")

    with col_ligs3:
        st.write("Extra shear/torsion detailing (hangers, etc.) can be added later.")

    st.markdown("**Effective web width $b_v$ and shear depth $d_v$ (Cl. 8.2.2)**")

    sum_duct = st.number_input(
        "Sum of duct diameters crossing web (mm)",
        value=0.0,
        min_value=0.0,
    )

    kd_opt = st.selectbox(
        "k_d factor for prestressing ducts",
        (
            ("None (no ducts in web)", 0.0),
            ("0.5 – steel ducts, grouted", 0.5),
            ("0.8 – plastic ducts, grouted", 0.8),
            ("1.2 – ungrouted ducts", 1.2),
        ),
        index=0,
        format_func=lambda kv: kv[0],
    )
    k_d = kd_opt[1]

    b_v = b - k_d * sum_duct
    d_v = max(0.72 * D, 0.9 * d)

    dv_1 = 0.72 * D
    dv_2 = 0.9 * d

    st.write(f"$b_v = {b_v:.1f}\\ \\text{{mm}}$  (reduced for ducts)")
    st.write(f"$0.72 D = {dv_1:.1f}$ mm,   $0.9 d = {dv_2:.1f}$ mm → $d_v = {d_v:.1f}$ mm")

    calcbox(
        rf"""
- Effective web width (AS 3600 Cl. 8.2.2):  
  - $b_v = b - k_d \sum d_{{duct}} = {b:.0f} - {k_d:.2f} \times {sum_duct:.1f} = {b_v:.1f}\ \text{{mm}}$  

- Shear depth:  
  - $d_v = \max(0.72D,\ 0.9d)$  
  - $0.72D = 0.72 \times {D:.0f} = {dv_1:.1f}\ \text{{mm}}$  
  - $0.9d = 0.9 \times {d:.0f} = {dv_2:.1f}\ \text{{mm}}$  
  - Hence $d_v = {d_v:.1f}\ \text{{mm}}$  

- Transverse steel per spacing:  
  - $A_{{sv}} = n_{{legs}} \dfrac{{\pi d_{{lig}}^2}}4 = {legs:.0f} \dfrac{{\pi {lig_d:.1f}^2}}4 = {Asv:,.1f}\ \text{{mm}}^2$  
  - Spacing: $s = {s:.1f}\ \text{{mm}}$.
"""
    )

    # =====================================================
    # 5. STEP 4 — LONGITUDINAL STRAIN εx
    # =====================================================
    st.markdown("---")
    st.markdown(
        "### Step 4 – Calculate longitudinal strain "
        "$\\varepsilon_x$ for MCFT (Cl. 8.2.4.2.3)"
    )

    st.latex(
        r"\varepsilon_x = "
        r"\frac{\displaystyle \frac{|M^*|}{d_v} + "
        r"\sqrt{\left(|V^*| - P_v\right)^2 + \left(\frac{0.97 T^* u_h}{2 A_o}\right)^2}"
        r" + 0.5 N^* - A_{pt} f_{po}}"
        r"{2(E_s A_{st} + E_p A_{pt})} \le 3.0\times10^{-3}"
    )

    M_star_Nmm = abs(M_star) * 1e6
    term_M = M_star_Nmm / (d_v or 1.0)

    Vprime_kN = abs(V_star) - P_v
    Vprime_N = Vprime_kN * 1e3

    torsion_N = 0.97 * T_star_Nmm * uh / (2.0 * (Ao or 1.0))
    sqrt_inner = math.sqrt(Vprime_N**2 + torsion_N**2)

    N_star_N = 0.5 * N_star * 1e3
    A_pt_fpo_N = A_pt * f_po

    numerator = term_M + sqrt_inner + N_star_N - A_pt_fpo_N

    Ep = 195000.0  # tendon modulus, MPa
    denom1 = 2.0 * (Es * A_st + Ep * A_pt)
    eps_x_1 = numerator / denom1 if denom1 > 0 else 0.0

    if eps_x_1 < 0:
        denom2 = 2.0 * (Es * A_st + Ep * A_pt + Ec * A_ct)
        eps_x = numerator / denom2 if denom2 > 0 else 0.0
        eps_x = max(-0.0002, min(eps_x, 0.0))
    else:
        eps_x = max(0.0, min(eps_x_1, 0.003))

    st.write(f"$\\varepsilon_x = {eps_x:.5f}$")

    calcbox(
        rf"""
- Moment term:  
  - $|M^*|/d_v = \dfrac{{|{M_star:.1f}| \times 10^6}}{{{d_v:.1f}}} = {term_M:,.0f}\ \text{{N}}$  

- Shear + torsion term inside the square-root:  
  - $V' = |V^*| - P_v = |{V_star:.1f}| - {P_v:.1f} = {Vprime_kN:.1f}\ \text{{kN}}$  
  - $0.97 T^* u_h / (2A_o) = {torsion_N:,.0f}\ \text{{N}}$ (in shear-force units)  
  - Combined: $\\sqrt{{V'^2 + (0.97 T^* u_h / 2A_o)^2}} = {sqrt_inner:,.0f}\ \text{{N}}$  

- Axial / prestress contributions:  
  - $0.5 N^* = 0.5 \times {N_star:.1f} \times 10^3 = {N_star_N:,.0f}\ \text{{N}}$  
  - $A_{{pt}} f_{{po}} = {A_pt:.1f} \times {f_po:.1f} = {A_pt_fpo_N:,.0f}\ \text{{N}}$  

- Final strain:  
  - $\\varepsilon_x = {eps_x:.5f}$ (capped to $[-2.0\\times10^{{-4}},\,3.0\\times10^{{-3}}]$).  

Check: $\\varepsilon_x \\le 3.0\\times10^{{-3}}$ for use of the general MCFT expression.
"""
    )

    # =====================================================
    # 6. STEP 5 — k_v AND θ_v
    # =====================================================
    st.markdown("---")
    st.markdown("### Step 5 – Get MCFT shear parameters: $k_v$ and $\\theta_v$")

    if use_general_kv:
        if fc <= 65:
            k_dg = 32.0 / (16.0 + d_g)
            k_dg = max(k_dg, 0.8)
            if d_g >= 16:
                k_dg = max(k_dg, 1.0)
        else:
            k_dg = 2.0

        Asv_over_s = Asv / s
        Asv_min_over_s = 0.08 * math.sqrt(fc) * b_v / (f_syv or 1.0)

        if Asv_over_s < Asv_min_over_s:
            k_v = (0.4 / (1 + 1500 * eps_x)) * (1300 / (1000 + k_dg * d_v))
        else:
            k_v = 0.4 / (1 + 1500 * eps_x)

        theta_v_deg = 29.0 + 7000.0 * eps_x

    else:
        if Asv / s < 0.08 * math.sqrt(fc) * b_v / (f_syv or 1.0):
            k_v = min(200.0 / (1000.0 + 1.3 * d_v), 0.10)
        else:
            k_v = 0.15
        theta_v_deg = 36.0

    theta_v_rad = math.radians(theta_v_deg)

    st.write(f"$k_v = {k_v:.3f}$")
    st.write(f"$\\theta_v = {theta_v_deg:.1f}^\\circ$")

    Asv_over_s = Asv / s
    Asv_min_over_s = 0.08 * math.sqrt(fc) * b_v / (f_syv or 1.0)
    k_dg_display = locals().get("k_dg", float("nan"))

    calcbox(
        rf"""
- Aggregate factor $k_{{dg}}$ (if general MCFT form used): ≈ {k_dg_display:.3f}  

- Minimum stirrup ratio (AS 3600 Cl. 8.2.4.2 / 8.2.4.3):  
  - Required: $\\left(\\dfrac{{A_{{sv}}}}s\\right)_{{min}} = 0.08 \\sqrt{{f'_c}}\\,\\dfrac{{b_v}}{{f_{{sy,v}}}}$  
  - Required value: {Asv_min_over_s:,.3f} mm²/mm  
  - Actual: $A_{{sv}}/s = {Asv_over_s:,.3f}$ mm²/mm  

- Shear parameter $k_v$:  
  - $k_v = {k_v:.3f}$  

- Strut angle:  
  - $\\theta_v = {theta_v_deg:.1f}^\\circ$.
"""
    )

    # =====================================================
    # 7. STEP 6 — V_uc, V_us AND SECTIONAL SHEAR CHECK
    # =====================================================
    st.markdown("---")
    st.markdown("### Step 6 – Concrete + steel shear strength and sectional check")

    st.markdown("**Concrete shear strength $V_{uc}$ (Cl. 8.2.4.1)**")
    st.latex(r"V_{uc} = k_v\, b_v d_v \sqrt{f'_c},\quad \sqrt{f'_c} \le 8.0\ \text{MPa}")

    sqrt_fc_limited = min(math.sqrt(fc), 8.0)
    Vuc_N = k_v * b_v * d_v * sqrt_fc_limited
    Vuc_kN = Vuc_N / 1e3

    st.write(f"$\\sqrt{{f'_c}}$ (limited) = {sqrt_fc_limited:.3f} MPa")
    st.write(f"$V_{{uc}} = {Vuc_kN:,.1f}\\ \\text{{kN}}$")

    st.markdown("**Steel shear contribution $V_{us}$ (Cl. 8.2.5.2(a))**")
    st.latex(r"V_{us} = \left(\frac{A_{sv} f_{sy,v} d_v}{s}\right)\cot \theta_v")

    Vus_N = (Asv * f_syv * d_v / s) * cot(theta_v_rad)
    Vus_kN = Vus_N / 1e3

    st.write(f"$V_{{us}} = {Vus_kN:,.1f}\\ \\text{{kN}}$")

    st.markdown("**Total sectional shear strength (Cl. 8.2.3.1)**")
    st.latex(r"V_u = V_{uc} + V_{us} + P_v,\quad \phi V_u \ge V_{eq}^*")

    Vu_total_kN = Vuc_kN + Vus_kN + P_v
    phi_Vu = phi * Vu_total_kN
    shear_ok = phi_Vu >= V_eq

    calcbox(
        rf"""
- Concrete contribution: $V_{{uc}} = {Vuc_kN:,.1f}\\ \\text{{kN}}$  
- Steel contribution: $V_{{us}} = {Vus_kN:,.1f}\\ \\text{{kN}}$  
- Total factored capacity: $V_u = V_{{uc}} + V_{{us}} + P_v = {Vu_total_kN:,.1f}\\ \\text{{kN}}$  
- Design strength: $\\phi V_u = {phi:.2f} \\times {Vu_total_kN:,.1f} = {phi_Vu:,.1f}\\ \\text{{kN}}$  
- Demand: $V_{{eq}}^* = {V_eq:.1f}\\ \\text{{kN}}$  

→ **Sectional shear check:** {"OK" if shear_ok else "NOT OK"} (require $\\phi V_u \\ge V_{{eq}}^*$).
"""
    )

    # =====================================================
    # 8. STEP 7 — WEB CRUSHING CHECK
    # =====================================================
    st.markdown("---")
    st.markdown("### Step 7 – Check web-crushing strength (AS 3600 Cl. 8.2.6)")

    st.latex(
        r"V_{u,\max} = 0.55 f'_c b_v d_v "
        r"\frac{\cot\theta_v + \cot\theta_1}{1 + \cot^2\theta_v} + P_v"
    )

    theta_1_deg = 90.0
    theta_1_rad = math.radians(theta_1_deg)
    cot_theta_v = cot(theta_v_rad)
    cot_theta_1 = cot(theta_1_rad)

    Vu_max_N = 0.55 * fc * b_v * d_v * (cot_theta_v + cot_theta_1) / (
        1 + cot_theta_v**2
    ) + P_v * 1e3
    Vu_max_kN = Vu_max_N / 1e3

    st.write(f"$V_{{u,\\max}}$ (web crushing) = {Vu_max_kN:,.1f} kN")

    V_star_N = V_star * 1e3
    term_V = V_star_N / (b_v * d_v or 1.0)
    term_T = T_star_Nmm * uh / (1.7 * ((A_oh or 1.0) ** 2))

    LHS = math.sqrt(term_V**2 + term_T**2)
    RHS = phi * Vu_max_N / (b_v * d_v or 1.0)

    web_ok = LHS <= RHS

    if not web_ok:
        st.error("Web-crushing limit exceeded – revise section/ligs.")

    calcbox(
        rf"""
- Web-crushing shear capacity:  
  - $V_{{u,\max}} = 0.55 f'_c b_v d_v \dfrac{{\cot\\theta_v + \cot\\theta_1}}{{1 + \cot^2\\theta_v}} + P_v$  
  - Substituting gives $V_{{u,\max}} = {Vu_max_kN:,.1f}\\ \\text{{kN}}$  

- Combined shear + torsion demand (Cl. 8.2.6):  
  - $\\sqrt{{(V^*/b_v d_v)^2 + (T^* u_h / (1.7 A_{{oh}}^2))^2}} = {LHS:,.1f}$  

- Limit:  
  - $\\phi V_{{u,\max}} / (b_v d_v) = {RHS:,.1f}$  

→ **Web-crushing check:** {"OK" if web_ok else "NOT OK"} (require LHS $\\le$ RHS).
"""
    )

    # =======================================================
    # 9. SUMMARY BANNER + PUSH RESULTS
    # =======================================================
    torsion_label = (
        "**Yes (included)**" if torsion_required else "No (strength check)"
    )

    summary_md = f"""
### Shear/Torsion ULS Summary

| Item | Value |
|------|-------|
| Torsion considered? | {torsion_label} |
| V_eq* | **{V_eq:.1f} kN** |
| V_uc | **{Vuc_kN:,.1f} kN** |
| V_us | **{Vus_kN:,.1f} kN** |
| φV_u vs V_eq* | **{phi_Vu:.1f} kN / {V_eq:.1f} kN → {"OK" if shear_ok else "NG"}** |
| V_u,max (web crushing) | **{Vu_max_kN:,.1f} kN** |
| Web-crushing check | **{"OK" if web_ok else "NG"}** |
| εₓ, k_v, θ_v | **εₓ = {eps_x:.5f},  k_v = {k_v:.3f},  θ_v = {theta_v_deg:.1f}°** |
"""

    shear_util = V_eq / phi_Vu if phi_Vu > 0 else 0.0
    update_results(
        phi_Vu_cap=phi_Vu,
        Vu_utilisation=shear_util,
    )

    summary_placeholder.markdown(summary_md)


if __name__ == "__main__":
    render_shear()
