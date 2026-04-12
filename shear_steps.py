# shear_steps.py
import streamlit as st
from shear_core import ShearResults
from widgets_helpers import calcbox


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




# ---------------- Step 1 – torsion cracking ----------------
def render_step_1(results: ShearResults, T_star: float, phi: float):
    step1_req = ">" if results.torsion_required else "\\le"
    step1_text = "required" if results.torsion_required else "not required (strength check only)"
    # Green if torsion NOT required (T* <= 0.25φTcr), red if required (T* > 0.25φTcr)
    torsion_status = "pass" if not results.torsion_required else "fail"

    md = (
        "**Step 1 – Does torsion crack the section? (AS 3600 Cl. 8.3.4)**  \n\n"
        "Given: gross area and perimeter of the torsion box:  \n\n"
        f"- $A_{{cp}} = {results.A_cp:.0f}\\ \\text{{mm}}^2$  \n"
        f"- $u_c = {results.u_c:.0f}\\ \\text{{mm}}$  \n\n"
        "Assume an effective torsion area and stirrup path:  \n\n"
        f"- $A_o = {results.Ao:.0f}\\ \\text{{mm}}^2$  \n"
        f"- $u_h = {results.uh:.0f}\\ \\text{{mm}}$  \n\n"
        f"Cracking torque: $T_{{cr}} = {results.Tcr_kNm:,.1f}\\ \\text{{kNm}}$  \n\n"
        "Check if torsion needs full design:  \n\n"
        f"- Requirement: $T^* {step1_req} 0.25\\, φ T_{{cr}}$  \n"
        f"- Here: $T^* = {T_star:.1f}\\ \\text{{kNm}}$, "
        f"$0.25 φ T_{{cr}} = {results.torsion_required_limit:,.1f}\\ \\text{{kNm}}$  \n\n"
        f"**Conclusion:** torsion design is **{step1_text}**.\n"
    )
    calcbox(md, status=torsion_status, uid="shear_step1_torsion")


# ---------------- Step 2 – equivalent shear ----------------
def render_step_2(results: ShearResults, V_star: float):
    md = (
        "**Step 2 – Convert torsion into an equivalent shear (AS 3600 Cl. 8.2.3)**  \n\n"
        "We convert torsion to an equivalent shear acting with $V^*$:  \n\n"
        f"- Design shear: $V^* = {V_star:.1f}\\ \\text{{kN}}$  \n"
        f"- Torsion-equivalent shear: $V_{{t,eq}} = {results.Vt_eq_kN:.1f}\\ \\text{{kN}}$  \n\n"
        "Using $V_{eq}^* = \\sqrt{V^{*2} + V_{t,eq}^{2}}$ gives:  \n\n"
        f"- $V_{{eq}}^* = {results.V_eq:.1f}\\ \\text{{kN}}$  \n\n"
        "This $V_{eq}^*$ is used for the sectional shear and web-crushing checks.\n"
    )
    calcbox(md)


# ---------------- Step 3 – shear-resisting section ---------
def render_step_3(results: ShearResults, b: float, D: float, d: float, b_v: float, d_v: float):
    md = (
        "**Step 3 – Determine shear-resisting section $(b_v, d_v)$ and ligs "
        "(AS 3600 Cl. 8.2.2)**  \n\n"
        "Start from the gross rectangle:  \n\n"
        f"- Width: $b = {b:.1f}\\ \\text{{mm}}$  \n"
        f"- Depth: $D = {D:.1f}\\ \\text{{mm}}$  \n"
        f"- Effective depth to tension steel: $d = {d:.1f}\\ \\text{{mm}}$  \n\n"
        "Allow for ducts to get the effective web:  \n\n"
        f"- $b_v = {b_v:.1f}\\ \\text{{mm}}$  \n\n"
        "Depth for shear is the larger of $0.72D$ and $0.9d$:  \n\n"
        f"- $0.72D = {0.72 * D:.1f}\\ \\text{{mm}}$  \n"
        f"- $0.9d  = {0.9 * d:.1f}\\ \\text{{mm}}$  \n"
        f"- Therefore $d_v = {d_v:.1f}\\ \\text{{mm}}$  \n\n"
        "Stirrups crossing this web provide the shear steel area:  \n\n"
        f"- $A_{{sv}} = {results.Asv:,.1f}\\ \\text{{mm}}^2$  \n\n"
        "These values define the concrete “shear zone” used in the MCFT shear model.\n"
    )
    calcbox(md)


# ---------------- Step 4 – longitudinal strain -------------
def render_step_4(results: ShearResults):
    md = (
        "**Step 4 – Calculate longitudinal strain $\\varepsilon_x$ for MCFT "
        "(AS 3600 Cl. 8.2.4.2.3)**  \n\n"
        "Using the MCFT-based expression for strain at mid-depth:  \n\n"
        f"- Resulting strain: $\\varepsilon_x = {results.eps_x:.5f}$  \n\n"
        "This strain is then used to determine $k_v$ and $\\theta_v$ for shear.\n"
    )
    calcbox(md)


# ---------------- Step 5 – MCFT parameters -----------------
def render_step_5(results: ShearResults):
    md = (
        "**Step 5 – Compression field (MCFT: $k_v$ and $\\theta_v$) "
        "(AS 3600 Cl. 8.2.4)**  \n\n"
        "**1. Determine governing expression**  \n\n"
        "Adequate stirrup ratio -> general MCFT formulation applies.  \n\n"
        "**2. Calculate concrete effectiveness factor $k_v$**  \n\n"
        f"$k_v = \\dfrac{{0.4}}{{1 + 1500\\varepsilon_x}}$  \n\n"
        f"$= \\dfrac{{0.4}}{{1 + 1500 \\times {results.eps_x:.5f}}}$  \n\n"
        f"$= {results.k_v:.3f}$  \n\n"
        "**3. Determine compression field angle $\\theta_v$**  \n\n"
        "From MCFT empirical relationship:  \n\n"
        "$\\theta_v = 29^\\circ + 7000\\,\\varepsilon_x$  \n\n"
        f"$= 29 + 7000 \\times {results.eps_x:.5f}$  \n\n"
        f"$= {results.theta_v_deg:.1f}^\\circ$  \n\n"
        "**Interpretation:**  \n"
        "$\\theta_v$ defines the angle of the concrete compression struts "
        "used in both the shear model and strut-and-tie visualisation.\n"
    )
    calcbox(md)


# ---------------- Step 6 – sectional shear -----------------
def render_step_6(results: ShearResults, V_eq: float):
    status = ":green[OK]" if results.shear_ok else ":red[NOT OK]"
    shear_status = "pass" if results.shear_ok else "fail"
    md = (
        "**Step 6 – Calculate concrete + steel shear strength and check "
        "(AS 3600 Cl. 8.2.3 & 8.2.4)**  \n\n"
        "Concrete shear capacity:  \n\n"
        f"- Limited $\\sqrt{{f'_c}} = {results.sqrt_fc_limited:.3f}\\ \\text{{MPa}}$  \n"
        f"- $V_{{uc}} = {results.Vuc_kN:,.1f}\\ \\text{{kN}}$  \n\n"
        "Steel shear contribution from stirrups:  \n\n"
        f"- $V_{{us}} = {results.Vus_kN:,.1f}\\ \\text{{kN}}$  \n\n"
        "Total shear resistance including axial/vertical force:  \n\n"
        f"- $V_u = V_{{uc}} + V_{{us}} + P_v = {results.Vu_total_kN:,.1f}\\ \\text{{kN}}$  \n"
        f"- $φV_u = {results.phi_Vu:,.1f}\\ \\text{{kN}}$  \n\n"
        "Demand from combined shear + torsion:  \n\n"
        f"- $V_{{eq}}^* = {V_eq:.1f}\\ \\text{{kN}}$  \n\n"
        f"**Sectional shear check:** {status}.\n"
    )
    calcbox(md, status=shear_status, uid="shear_step6_capacity")


# ---------------- Step 7 – web crushing --------------------
def render_step_7(results: ShearResults):
    status = ":green[OK]" if results.web_ok else ":red[NOT OK]"
    web_status = "pass" if results.web_ok else "fail"
    md = (
        "**Step 7 – Check web-crushing strength (AS 3600 Cl. 8.2.6)**  \n\n"
        "Web-crushing shear capacity:  \n\n"
        f"- $V_{{u,\\max}} = {results.Vu_max_kN:,.1f}\\ \\text{{kN}}$  \n\n"
        "Combined shear + torsion demand term:  \n\n"
        f"- LHS $= {results.LHS:,.1f}$  \n\n"
        "Limit from $φV_{u,\\max} / (b_v d_v)$:  \n\n"
        f"- RHS $= {results.RHS:,.1f}$  \n\n"
        f"**Web-crushing check:** {status}.\n"
    )
    calcbox(md, status=web_status, uid="shear_step7_web_crushing")
