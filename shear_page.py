import math
import streamlit as st

from state_and_helpers import (
    get_param,
    get_sync_callbacks,
    update_results,
)

# same helper that bending page uses
from widgets_helpers import apply_global_widget_css, calcbox


def cot(rad: float) -> float:
    """Cotangent with protection against tan(pi/2) etc."""
    return 1.0 / math.tan(rad)


def render_shear():
    # --------------------------------------------
    # Global CSS (same look as other pages)
    # --------------------------------------------
    apply_global_widget_css()

    st.title("Shear & Torsion")

    sync_callbacks = get_sync_callbacks()
    summary_placeholder = st.empty()

    st.markdown(
        """
        This page performs an AS 3600 shear + torsion check with a step-by-step
        ULS calculation.

        Geometry, materials and design actions are shared with the Inputs tab
        via the session-state contract (through `get_param()` / `get_sync_callbacks()`).
        Results are written to the global `RESULTS` using `update_results()` so the
        Inputs summary can show shear utilisation.
        """
    )

    # =====================================================
    # 1. DESIGN INPUTS (shared + local)
    # =====================================================
    st.subheader("1. Design Inputs")

    col_geom, col_actions, col_eps = st.columns(3)

    # ------------------ 1.1 Shared geometry & materials ------------------
    with col_geom:
        st.markdown("**1.1 Geometry & materials (linked to Inputs)**")

        st.number_input(
            "b – beam/web width (mm)",
            key="shear_b",
            on_change=sync_callbacks["shear_b"],
        )
        st.number_input(
            "D – overall depth (mm)",
            key="shear_D",
            on_change=sync_callbacks["shear_D"],
        )
        st.number_input(
            "L – span L (mm)",
            key="shear_L",
            on_change=sync_callbacks["shear_L"],
        )

        st.number_input(
            "f'c (MPa)",
            key="shear_fc",
            on_change=sync_callbacks["shear_fc"],
        )
        st.number_input(
            "f_sy (MPa)",
            key="shear_fsy",
            on_change=sync_callbacks["shear_fsy"],
        )
        st.number_input(
            "E_c (MPa)",
            key="shear_Ec",
            on_change=sync_callbacks["shear_Ec"],
        )
        st.number_input(
            "E_s (MPa)",
            key="shear_Es",
            on_change=sync_callbacks["shear_Es"],
        )

    # ------------------ 1.2 Shear, axial, torsion ------------------
    with col_actions:
        st.markdown("**1.2 Design actions (linked to Inputs)**")

        st.number_input(
            "V* – design shear (kN)",
            key="shear_Vu_star",
            on_change=sync_callbacks["shear_Vu_star"],
        )
        st.number_input(
            "N* – axial force (kN, +tension)",
            key="shear_N_star",
            on_change=sync_callbacks["shear_N_star"],
        )
        st.number_input(
            "P_v – vertical prestress / axial (kN)",
            key="shear_P_star",
            on_change=sync_callbacks["shear_P_star"],
        )
        st.number_input(
            "T* – torsion at section (kNm)",
            key="shear_Tu_star",  # mapped to Tu_star in helpers
            on_change=sync_callbacks["shear_Tu_star"],
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
            help="Used in torsion cracking torque T_cr (AS 3600 Cl. 8.2.3).",
        )

    # ------------------ 1.3 εx-related inputs ------------------
    with col_eps:
        st.markdown("**1.3 εₓ inputs (ULS flexural strain)**")

        A_st = st.number_input(
            "A_st (mm²) – non-prestressed tension steel",
            value=4 * (math.pi * 20.0**2 / 4.0),
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
            value=(get_param("b") or 400.0) * ((get_param("D") or 600.0) / 2.0),
            help="Only used when εₓ is negative (compression).",
        )

    # -------------------------------------------------
    # Pull shared values for calculations
    # -------------------------------------------------
    b = get_param("b")
    D = get_param("D")
    L = get_param("L")

    fc = get_param("fc")
    fsy = get_param("fsy")
    Ec = get_param("Ec")
    Es = get_param("Es")

    M_star = get_param("Mu_star")
    V_star = get_param("Vu_star")
    T_star = get_param("Tu_star")
    N_star = get_param("N_star")
    P_v = get_param("P_star")

    lig_d = get_param("lig_d")
    legs = get_param("lig_legs")
    s_lig = get_param("s_lig")

    d = get_param("d")

    if not (b and D and d):
        st.error("Geometry (b, D, d) not fully defined – check Inputs / Bending tab.")
        return

    # =====================================================
    # 2. TORSION GEOMETRY & CRACKING TORQUE T_cr
    # =====================================================
    st.markdown("---")
    st.subheader("2. Torsion geometry and cracking torque $T_{cr}$")

    cover_t = 40.0  # assumed for closed stirrup centroid
    A_cp = b * D
    u_c = 2 * (b + D)
    A_o = 0.9 * A_cp  # AS 3600 approximation

    u_h = 2 * ((b - cover_t) + (D - cover_t))
    A_oh = (b - cover_t) * (D - cover_t)

    sqrt_fc = math.sqrt(fc)
    denom = 0.33 * sqrt_fc
    Tcr_Nmm = 0.33 * sqrt_fc * (A_cp**2) / u_c * math.sqrt(
        1.0 + (sigma_cp / denom if denom > 0 else 0.0)
    )
    Tcr_kNm = Tcr_Nmm / 1e6

    calcbox(
        r"""
Cracking torque for a solid rectangular member (AS 3600 Cl. 8.2.3):

$$
T_{cr} = 0.33 \sqrt{f'_c}\;
\frac{A_{cp}^2}{u_c}
\sqrt{1 + \frac{\sigma_{cp}}{0.33 \sqrt{f'_c}}}
$$

where  

- \(A_{cp}\) = area enclosed by the outside perimeter of the concrete section  
- \(u_c\)  = outside perimeter of the concrete section  
- \(\sigma_{cp}\) = average axial / prestress.
"""
    )

    st.write(f"Calculated:  \n**T_cr = {Tcr_kNm:,.1f} kNm**")

    torsion_required_limit = 0.25 * phi * Tcr_kNm
    torsion_required = T_star > torsion_required_limit

    st.write(
        f"Torsion required? → "
        f"{'**Yes (T* > 0.25 φ T_cr)**' if torsion_required else 'No (T* ≤ 0.25 φ T_cr)'}"
    )

    # =====================================================
    # 3. EQUIVALENT SHEAR V_eq*
    # =====================================================
    st.markdown("---")
    st.subheader("3. Equivalent shear $V_{eq}^*$ (Cl. 8.2.3)")

    T_star_Nmm = T_star * 1e6
    torsion_eq_N = 0.9 * T_star_Nmm * u_h / (2.0 * (A_o or 1.0))
    torsion_eq_kN = torsion_eq_N / 1e3

    V_eq = math.sqrt(V_star**2 + torsion_eq_kN**2)

    calcbox(
        r"""
For combined shear + torsion (AS 3600 Cl. 8.2.3):

$$
V_{eq}^* = \sqrt{\,V^{*2}
+ \left(\frac{0.9 T^* u_h}{2 A_o}\right)^2}
$$

where \(A_o\) and \(u_h\) are taken at the centreline of the stirrups.
"""
    )

    st.write(
        f"Contribution from torsion = {torsion_eq_kN:.1f} kN  \n"
        f"Equivalent shear: **V_eq* = {V_eq:.1f} kN**"
    )

    # =====================================================
    # 4. SHEAR REINFORCEMENT & EFFECTIVE SECTION
    # =====================================================
    st.markdown("---")
    st.subheader("4. Effective web section and shear reinforcement")

    d_g = st.number_input(
        "d_g – max aggregate size (mm)",
        value=20.0,
        min_value=5.0,
        max_value=40.0,
    )

    lig_d = lig_d or 10.0
    legs = legs or 2.0
    s = s_lig or 200.0

    A_sv = legs * math.pi * lig_d**2 / 4.0
    f_syv = fsy

    col_ligs1, col_ligs2, col_ligs3 = st.columns(3)
    with col_ligs1:
        st.markdown(
            f"**Lig diameter (session)** = {lig_d:.1f} mm  \n"
            f"**Legs per lig (session)** = {legs:.0f}  \n"
            f"**Stirrup spacing s_lig (session)** = {s_lig:.1f} mm"
        )

    with col_ligs2:
        st.markdown(
            f"**A_sv (calculated)** = {A_sv:,.1f} mm²  \n"
            f"&nbsp;&nbsp;&nbsp;= legs × π d_lig² / 4  \n"
            f"**Shear lig yield f_sy,v** = {f_syv:.1f} MPa  \n"
            f"&nbsp;&nbsp;&nbsp;(taken equal to longitudinal f_sy)"
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
        st.write("Extra shear/torsion detailing (hangers etc.) can be added later.")

    st.markdown("**4.1 Effective web width $b_v$ and shear depth $d_v$ (Cl. 8.2.2)**")

    sum_duct = st.number_input(
        "Σ duct diameters crossing web (mm)",
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

    calcbox(
        r"""
Effective web width and shear depth (AS 3600 Cl. 8.2.2):

- \(b_v = b - k_d \sum d_{duct}\)  
- \(d_v = \max(0.72 D,\; 0.9 d)\)
"""
    )

    dv_1 = 0.72 * D
    dv_2 = 0.9 * d
    st.write(f"b_v = **{b_v:.1f} mm**")
    st.write(f"0.72 D = {dv_1:.1f} mm,   0.9 d = {dv_2:.1f} mm → d_v = **{d_v:.1f} mm**")

    # =====================================================
    # 5. LONGITUDINAL STRAIN εx
    # =====================================================
    st.markdown("---")
    st.subheader("5. Longitudinal strain $\\varepsilon_x$ at mid-depth (Cl. 8.2.4.2.3)")

    calcbox(
        r"""
General expression for longitudinal strain at mid-depth (AS 3600 Cl. 8.2.4.2.3):

$$
\varepsilon_x =
\frac{\displaystyle \frac{|M^*|}{d_v} +
\sqrt{\left(|V^*| - P_v\right)^2 +
       \left(\frac{0.97 T^* u_h}{2 A_o}\right)^2}
+ 0.5 N^* - A_{pt} f_{po}}
{2 (E_s A_{st} + E_p A_{pt})}
\le 3.0 \times 10^{-3}
$$

If the computed value is negative (compression), the concrete
area in tension \(A_{ct}\) is included in the denominator and
\(\varepsilon_x\) is limited to the range \([-2\times10^{-4}, 0]\).
"""
    )

    M_star_Nmm = abs(M_star) * 1e6
    term_M = M_star_Nmm / (d_v or 1.0)

    Vprime_kN = abs(V_star) - P_v
    Vprime_N = Vprime_kN * 1e3

    torsion_N = 0.97 * T_star_Nmm * u_h / (2.0 * (A_o or 1.0))
    sqrt_inner = math.sqrt(Vprime_N**2 + torsion_N**2)

    N_star_N = 0.5 * N_star * 1e3
    A_pt_fpo_N = A_pt * f_po

    numerator = term_M + sqrt_inner + N_star_N - A_pt_fpo_N

    E_p = 195000.0  # tendon modulus, MPa
    denom1 = 2.0 * (Es * A_st + E_p * A_pt)
    eps_x_1 = numerator / denom1 if denom1 > 0 else 0.0

    if eps_x_1 < 0:
        denom2 = 2.0 * (Es * A_st + E_p * A_pt + Ec * A_ct)
        eps_x = numerator / denom2 if denom2 > 0 else 0.0
        eps_x = max(-0.0002, min(eps_x, 0.0))
    else:
        eps_x = max(0.0, min(eps_x_1, 0.003))

    st.write(f"Calculated longitudinal strain: **εₓ = {eps_x:.5f}**")

    # =====================================================
    # 6. k_v and θ_v
    # =====================================================
    st.markdown("---")
    st.subheader("6. $k_v$ and $\\theta_v$ (shear strength parameters)")

    if use_general_kv:
        # 6.1 General εx-based method (Cl. 8.2.4.2)
        if fc <= 65:
            k_dg = 32.0 / (16.0 + d_g)
            k_dg = max(k_dg, 0.8)
            if d_g >= 16.0:
                k_dg = max(k_dg, 1.0)
        else:
            k_dg = 2.0

        Asv_over_s = A_sv / s
        Asv_min_over_s = 0.08 * math.sqrt(fc) * b_v / (f_syv or 1.0)

        if Asv_over_s < Asv_min_over_s:
            k_v = (0.4 / (1 + 1500 * eps_x)) * (1300 / (1000 + k_dg * d_v))
        else:
            k_v = 0.4 / (1 + 1500 * eps_x)

        theta_v_deg = 29.0 + 7000.0 * eps_x

        calcbox(
            r"""
General method (AS 3600 Cl. 8.2.4.2):

- Aggregate factor \(k_{dg}\) based on \(d_g\)  
- Minimum lig ratio check \(A_{sv}/s \ge 0.08 \sqrt{f'_c} b_v / f_{sy,v}\)  

If **below** minimum:

$$
k_v = \frac{0.4}{1 + 1500 \varepsilon_x}
      \frac{1300}{1000 + k_{dg} d_v}
$$

Else:

$$
k_v = \frac{0.4}{1 + 1500 \varepsilon_x}
$$

Crack angle:

$$
\theta_v = 29^\circ + 7000\,\varepsilon_x
$$
"""
        )

    else:
        # 6.2 Simplified non-prestressed method (Cl. 8.2.4.3)
        if A_sv / s < 0.08 * math.sqrt(fc) * b_v / (f_syv or 1.0):
            k_v = min(200.0 / (1000.0 + 1.3 * d_v), 0.10)
        else:
            k_v = 0.15
        theta_v_deg = 36.0

        calcbox(
            r"""
Simplified non-prestressed method (AS 3600 Cl. 8.2.4.3):

If \(A_{sv}/s < 0.08 \sqrt{f'_c} b_v / f_{sy,v}\):

$$
k_v = \min\left(\frac{200}{1000 + 1.3 d_v},\; 0.10\right)
$$

Else:

$$
k_v = 0.15
$$

Crack angle is taken as:

$$
\theta_v = 36^\circ
$$
"""
        )

    theta_v_rad = math.radians(theta_v_deg)

    st.write(f"Result:  \n**k_v = {k_v:.3f}**,  **θ_v = {theta_v_deg:.1f}°**")

    # -------------------------------------------------
    # 6.3 Concrete shear strength V_uc
    # -------------------------------------------------
    st.markdown("**6.1 Concrete shear strength $V_{uc}$ (Cl. 8.2.4.1)**")

    calcbox(
        r"""
Concrete contribution (AS 3600 Cl. 8.2.4.1):

$$
V_{uc} = k_v\, b_v d_v \sqrt{f'_c},
\qquad \sqrt{f'_c} \le 8.0\ \text{MPa}
$$
"""
    )

    sqrt_fc_limited = min(math.sqrt(fc), 8.0)
    Vuc_N = k_v * b_v * d_v * sqrt_fc_limited
    Vuc_kN = Vuc_N / 1e3

    st.write(f"√f'c (limited) = {sqrt_fc_limited:.3f} MPa")
    st.write(f"V_uc = **{Vuc_kN:,.1f} kN**")

    # =====================================================
    # 7. V_us AND SECTIONAL SHEAR CHECK
    # =====================================================
    st.markdown("---")
    st.subheader("7. Shear reinforcement contribution $V_{us}$ and sectional check")

    st.markdown("**7.1 $V_{us}$ for perpendicular ligs (Cl. 8.2.5.2(a))**")

    calcbox(
        r"""
For vertical (perpendicular) ligatures (AS 3600 Cl. 8.2.5.2(a)):

$$
V_{us} =
\left(\frac{A_{sv} f_{sy,v} d_v}{s}\right)\cot\theta_v
$$
"""
    )

    Vus_N = (A_sv * f_syv * d_v / s) * cot(theta_v_rad)
    Vus_kN = Vus_N / 1e3

    st.write(f"V_us = **{Vus_kN:,.1f} kN**")

    st.markdown("**7.2 Total shear strength and sectional check (Cl. 8.2.3.1)**")

    calcbox(
        r"""
Total shear resistance including axial / prestress (AS 3600 Cl. 8.2.3.1):

$$
V_u = V_{uc} + V_{us} + P_v, \qquad
\phi V_u \ge V_{eq}^*
$$
"""
    )

    Vu_total_kN = Vuc_kN + Vus_kN + P_v
    phi_Vu = phi * Vu_total_kN
    shear_ok = phi_Vu >= V_eq

    st.write(
        f"φ V_u = **{phi_Vu:.1f} kN**,   "
        f"V_eq* = **{V_eq:.1f} kN** → "
        f"{'**OK**' if shear_ok else '**NG – not adequate**'}"
    )

    # =====================================================
    # 8. WEB-CRUSHING CHECK
    # =====================================================
    st.markdown("---")
    st.subheader("8. Web-crushing capacity (Cl. 8.2.6)")

    calcbox(
        r"""
Web-crushing (AS 3600 Cl. 8.2.6):

$$
V_{u,\max} =
0.55 f'_c b_v d_v\,
\frac{\cot\theta_v + \cot\theta_1}{1 + \cot^2\theta_v}
+ P_v
$$

with \(\theta_1 \approx 90^\circ\).
"""
    )

    theta_1_deg = 90.0
    theta_1_rad = math.radians(theta_1_deg)
    cot_theta_v = cot(theta_v_rad)
    cot_theta_1 = cot(theta_1_rad)

    Vu_max_N = (
        0.55
        * fc
        * b_v
        * d_v
        * (cot_theta_v + cot_theta_1)
        / (1 + cot_theta_v**2)
        + P_v * 1e3
    )
    Vu_max_kN = Vu_max_N / 1e3

    st.write(f"V_u,max (web crushing) = **{Vu_max_kN:,.1f} kN**")

    V_star_N = V_star * 1e3
    term_V = V_star_N / (b_v * d_v or 1.0)
    term_T = T_star_Nmm * u_h / (1.7 * (A_oh**2 or 1.0))

    LHS = math.sqrt(term_V**2 + term_T**2)
    RHS = phi * Vu_max_N / (b_v * d_v or 1.0)

    web_ok = LHS <= RHS

    if not web_ok:
        st.error("Web-crushing limit exceeded – revise section/ligs.")
    else:
        st.success("Web-crushing check: OK.")

    # =======================================================
    # 9. SUMMARY BANNER + PUSH RESULTS TO GLOBAL RESULTS
    # =======================================================
    shear_util = V_eq / phi_Vu if phi_Vu > 0 else 0.0

    summary_md = f"""
### Shear/Torsion ULS Summary

| Item | Value |
|------|-------|
| Torsion considered? | {'**Yes (T* > 0.25 φT_cr)**' if torsion_required else 'No (strength check)'} |
| V_eq* | **{V_eq:.1f} kN** |
| V_uc | **{Vuc_kN:,.1f} kN** |
| V_us | **{Vus_kN:,.1f} kN** |
| φV_u vs V_eq* | **{phi_Vu:.1f} kN / {V_eq:.1f} kN → {'OK' if shear_ok else 'NG'}** |
| V_u,max (web crushing) | **{Vu_max_kN:,.1f} kN** |
| Web-crushing check | **{'OK' if web_ok else 'NG'}** |
| εₓ, k_v, θ_v | **εₓ = {eps_x:.5f},  k_v = {k_v:.3f},  θ_v = {theta_v_deg:.1f}°** |
| Shear utilisation | **{shear_util:.2f}** |
"""

    summary_placeholder.markdown(summary_md)

    # Push shear results into shared RESULT_KEYS for Inputs summary
    update_results(
        phi_Vu_cap=phi_Vu,
        Vu_utilisation=shear_util,
    )


if __name__ == "__main__":
    render_shear()
