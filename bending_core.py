# shear_page.py

import math
import pandas as pd
import streamlit as st

from state_and_helpers import (
    get_param,
    get_sync_callbacks,
    update_results,
)

from widgets_helpers import (
    apply_global_widget_css,
    number_row,
)

# ------------------------------------------------------------
#  Small formatting helper for tables
# ------------------------------------------------------------
def _fmt(val, pattern="{:.2f}"):
    """Safe formatter for table values."""
    try:
        if val is None:
            return "—"
        if isinstance(val, float) and math.isnan(val):
            return "—"
        return pattern.format(val)
    except Exception:
        return "—"


# ------------------------------------------------------------
#  Simple calc box helper + CSS (MATCH BENDING PAGE)
# ------------------------------------------------------------
def _inject_calcbox_css():
    st.markdown(
        """
<style>
.calcbox-wrapper {
  margin-top: 0.5rem;
  margin-bottom: 0.5rem;
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


# ------------------------------------------------------------
#  CORE SHEAR + TORSION CALC (simple AS3600-style)
# ------------------------------------------------------------
def _compute_shear_torsion():
    """
    Compute a simple φV_u,cap and φT_u,cap with step values.

    This is intentionally 'teaching style' rather than a full MCFT engine.
    You can later swap the internals out without changing the UI.
    """

    # Basic section + materials
    b = get_param("b")
    D = get_param("D")
    d = get_param("d")  # effective depth to tension steel centroid (from bending)
    fc = get_param("fc")
    fsy = get_param("fsy")

    # Actions
    V_star = get_param("V_star")     # kN
    T_star = get_param("T_star")     # kNm (may be zero)
    N_star = get_param("N_star")     # kN (tension +ve, compression -ve)

    # Shear reinforcement data (you might already store these)
    # For now we read them generically; adjust keys to match your Inputs tab.
    sv = get_param("sv")             # stirrup spacing (mm)
    Av = get_param("Av")             # stirrup area per leg (mm²)
    n_legs = get_param("n_legs")     # number of legs crossing shear crack
    phi_shear = get_param("phi_shear", 0.75)

    # εx support inputs (derived from bending / Inputs)
    Ast = get_param("Ast_bot")       # mm² – non-prestressed tension steel
    Apt = get_param("Apt_ULS")       # mm² – prestressing steel
    f_po = get_param("f_po_ULS")     # MPa – effective tendon stress
    Act = get_param("Act_tension")   # mm² – area of concrete in tension

    # Basic checks + fallbacks
    if d in (None, 0):
        # crude fallback on overall depth if bending hasn't set d yet
        if D not in (None, 0):
            d = 0.9 * D
        else:
            d = None

    if None in (b, D, d, fc, fsy, V_star):
        # Not enough info; return NaNs but still safe
        return dict(
            dv=float("nan"),
            eps_x=float("nan"),
            beta_v=float("nan"),
            theta_deg=float("nan"),
            V_uc=float("nan"),
            V_us=float("nan"),
            V_u_cap=float("nan"),
            phi_V_u_cap=0.0,
            V_util=float("nan"),
            T_u_cap=float("nan"),
            phi_T_u_cap=0.0,
            T_util=float("nan"),
            inputs=dict(
                b=b,
                D=D,
                d=d,
                fc=fc,
                fsy=fsy,
                V_star=V_star,
                T_star=T_star,
            ),
        )

    # --------------------------------------------------------
    # 1. Shear depth dv
    # --------------------------------------------------------
    # dv is usually taken as ~0.9 d and limited by code; we'll keep it simple.
    dv = 0.9 * d
    dv = min(dv, 0.9 * D)

    # --------------------------------------------------------
    # 2. Flexural strain εx at the tension steel (AS3600 MCFT-style)
    # --------------------------------------------------------
    # Very simplified: εx from total tension in bottom fibre.
    # You can replace with your exact AS3600 expression.
    #
    #   εx = ( (M* / (z * Es * As_eq)) + (N* / (Es * As_eq)) - f_po / Es * (Apt/As_eq) )
    #
    # where As_eq = Ast + Apt, N* tension positive.
    Es = get_param("Es") or 200_000.0  # MPa
    Mu_star = get_param("Mu_star")     # kNm (from bending page)
    z = 0.9 * d                        # internal lever arm approximation

    As_eq = (Ast or 0.0) + (Apt or 0.0)
    eps_x = float("nan")

    if As_eq > 0 and Es not in (None, 0):
        term_M = 0.0
        if Mu_star not in (None, 0) and z not in (None, 0):
            # convert Mu* from kNm → Nmm: 1 kNm = 10^6 Nmm
            term_M = (Mu_star * 1e6) / (z * Es * As_eq)

        term_N = 0.0
        if N_star not in (None, 0):
            # N* in kN → N
            term_N = (N_star * 1e3) / (Es * As_eq)

        term_prestress = 0.0
        if f_po not in (None, 0) and Apt not in (None, 0):
            term_prestress = (f_po * Apt) / (Es * As_eq)

        eps_x = term_M + term_N - term_prestress

    # --------------------------------------------------------
    # 3. βv and θ (AS3600 MCFT factors – teaching version)
    # --------------------------------------------------------
    # Common AS3600 / MCFT style:
    #    βv = 1 / (1 + 0.63 * sqrt(500 εx))   (clamped)
    beta_v = float("nan")
    if eps_x not in (None, 0) and eps_x > 0:
        beta_v = 1.0 / (1.0 + 0.63 * math.sqrt(500.0 * eps_x))
        beta_v = max(0.1, min(beta_v, 1.0))

    # Shear crack angle; often taken 30–40°. Use 35° unless you prefer a formula.
    theta_deg = 35.0
    theta_rad = math.radians(theta_deg)

    # --------------------------------------------------------
    # 4. Concrete shear capacity V_uc  (no shear reinforcement)
    # --------------------------------------------------------
    # Example AS3600-style: v_uc = 0.18 * βv * sqrt(fc') (MPa)
    #   → V_uc = v_uc * b * dv  (N) → /1000 = kN
    V_uc = float("nan")
    if beta_v not in (None, 0) and fc not in (None, 0) and b not in (None, 0) and dv not in (None, 0):
        v_uc = 0.18 * beta_v * math.sqrt(fc)  # MPa = N/mm²
        V_uc = v_uc * b * dv / 1000.0        # kN

    # --------------------------------------------------------
    # 5. Shear reinforcement contribution V_us
    # --------------------------------------------------------
    V_us = float("nan")
    if (
        sv not in (None, 0)
        and Av not in (None, 0)
        and n_legs not in (None, 0)
        and fsy not in (None, 0)
        and d not in (None, 0)
    ):
        # V_us = (A_v * f_y * d * n_legs / s_v) / 1000  (kN)
        V_us = (Av * n_legs * fsy * d / sv) / 1000.0

    # --------------------------------------------------------
    # 6. Total shear capacity & utilisation
    # --------------------------------------------------------
    V_u_cap = 0.0
    if V_uc not in (None, float("nan")) and V_us not in (None, float("nan")):
        V_u_cap = V_uc + V_us

    phi_V_u_cap = phi_shear * V_u_cap if V_u_cap not in (None, 0) else 0.0
    V_util = V_star / phi_V_u_cap if phi_V_u_cap > 0 else float("inf")

    # --------------------------------------------------------
    # 7. Torsion (simple teaching placeholder)
    # --------------------------------------------------------
    # For now we use a proportional check only; you can later replace with
    # your full AS3600 torsion expressions.
    phi_T_u_cap = 0.0
    T_u_cap = float("nan")
    T_util = float("nan")
    phi_torsion = get_param("phi_torsion", 0.75)

    if T_star not in (None, 0):
        # crude teaching: assume torsion capacity scales with shear capacity
        # T_u_cap ≈ V_u_cap * (0.5 * D)   (kNm)
        if V_u_cap not in (None, 0) and D not in (None, 0):
            T_u_cap = V_u_cap * (0.5 * D) / 1000.0  # N * mm → kNm approx
            phi_T_u_cap = phi_torsion * T_u_cap
            T_util = T_star / phi_T_u_cap if phi_T_u_cap > 0 else float("inf")

    # Push key results into the shared results dict for the summary page
    update_results(
        phi_Vu_cap=phi_V_u_cap,
        Vu_utilisation=V_util,
        phi_Tu_cap=phi_T_u_cap,
        Tu_utilisation=T_util,
    )

    return dict(
        dv=dv,
        eps_x=eps_x,
        beta_v=beta_v,
        theta_deg=theta_deg,
        V_uc=V_uc,
        V_us=V_us,
        V_u_cap=V_u_cap,
        phi_V_u_cap=phi_V_u_cap,
        V_util=V_util,
        T_u_cap=T_u_cap,
        phi_T_u_cap=phi_T_u_cap,
        T_util=T_util,
        Ast=Ast,
        Apt=Apt,
        f_po=f_po,
        Act=Act,
        inputs=dict(
            b=b,
            D=D,
            d=d,
            fc=fc,
            fsy=fsy,
            V_star=V_star,
            T_star=T_star,
            N_star=N_star,
            sv=sv,
            Av=Av,
            n_legs=n_legs,
            phi_shear=phi_shear,
        ),
    )


# ------------------------------------------------------------
#  MAIN PAGE RENDER FUNCTION
# ------------------------------------------------------------
def render_shear():
    apply_global_widget_css()
    _inject_calcbox_css()

    st.title("Shear & Torsion")

    sync_callbacks = get_sync_callbacks()
    summary_placeholder = st.empty()

    # ========================================================
    # 1. DESIGN INPUTS
    # ========================================================
    st.markdown("## 1. Design Inputs")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("### 1.1 Geometry & materials (linked to Inputs)")

        number_row("b – beam/web width (mm)", "b", col=col1, sync_callbacks=sync_callbacks)
        number_row("D – overall depth (mm)", "D", col=col1, sync_callbacks=sync_callbacks)
        number_row("d – effective depth to tension steel (mm)", "d", col=col1, sync_callbacks=sync_callbacks)
        number_row("f'c (MPa)", "fc", col=col1, sync_callbacks=sync_callbacks)
        number_row("f_sy (MPa)", "fsy", col=col1, sync_callbacks=sync_callbacks)
        number_row("E_s (MPa)", "Es", col=col1, sync_callbacks=sync_callbacks)

    with col2:
        st.markdown("### 1.2 Design actions (linked to Inputs)")

        number_row("V* – design shear (kN)", "V_star", col=col2, sync_callbacks=sync_callbacks)
        number_row("T* – torsion at section (kNm)", "T_star", col=col2, sync_callbacks=sync_callbacks)
        number_row("N* – axial force (kN, +tension)", "N_star", col=col2, sync_callbacks=sync_callbacks)
        number_row("φ_v – strength reduction for shear", "phi_shear", col=col2, sync_callbacks=sync_callbacks)
        number_row("φ_t – strength reduction for torsion", "phi_torsion", col=col2, sync_callbacks=sync_callbacks)

    st.markdown("---")

    # Shear reinforcement inputs
    st.markdown("### 1.3 Shear reinforcement details")

    col3, col4 = st.columns(2)
    with col3:
        number_row("s_v – stirrup spacing (mm)", "sv", col=col3, sync_callbacks=sync_callbacks)
        number_row("A_v – area of one leg (mm²)", "Av", col=col3, sync_callbacks=sync_callbacks)

    with col4:
        number_row("n_legs – legs per stirrup crossing shear crack", "n_legs", col=col4, sync_callbacks=sync_callbacks)

    st.markdown("---")

    # ========================================================
    # 2. εx INPUTS (DERIVED FROM BENDING / INPUTS)
    # ========================================================
    results = _compute_shear_torsion()

    Ast = results["Ast"]
    Apt = results["Apt"]
    f_po = results["f_po"]
    Act = results["Act"]

    calcbox(
        f"""
**2.1 εₓ inputs (from bending / Inputs)**  

- $A_{{st}}$ = {_fmt(Ast)} mm² – non-prestressed tension steel  
- $A_{{pt}}$ = {_fmt(Apt)} mm² – prestressing steel  
- $f_{{po}}$ = {_fmt(f_po)} MPa – effective tendon stress  
- $A_{{ct}}$ = {_fmt(Act)} mm² – area of concrete in tension  

These are derived from the **Bending / Inputs** page and are not editable here.
"""
    )

    calcbox(
        rf"""
**2.2 Flexural strain at the level of tensile steel – $ε_x$**  

Using AS 3600 MCFT-style expression (teaching form):  

- Internal lever arm: $z \approx 0.9 d$  
- Equivalent tensile area: $A_{{s,eq}} = A_{{st}} + A_{{pt}}$  

Result:

- $ε_x = {_fmt(results['eps_x'], '{{:.6f}}')}$  
"""
    )

    st.markdown("---")

    # ========================================================
    # 3. SHEAR CAPACITY CHECK
    # ========================================================
    dv = results["dv"]
    beta_v = results["beta_v"]
    theta_deg = results["theta_deg"]
    V_uc = results["V_uc"]
    V_us = results["V_us"]
    phi_V_u_cap = results["phi_V_u_cap"]
    V_util = results["V_util"]

    calcbox(
        f"""
**3.1 Shear depth $d_v$**  

- $d_v = {_fmt(dv)}$ mm (taken as 0.9 d, limited by code).  
"""
    )

    calcbox(
        f"""
**3.2 Concrete shear contribution $V_{{uc}}$ (AS 3600 MCFT)**  

- $β_v = {_fmt(beta_v, '{{:.3f}}')}$  
- Shear crack angle: $θ = {_fmt(theta_deg, '{{:.1f}}')}^\\circ$ (assumed)  

Concrete shear capacity:  

- $V_{{uc}} = {_fmt(V_uc)}$ kN  
"""
    )

    calcbox(
        f"""
**3.3 Shear reinforcement contribution $V_{{us}}$**  

- $V_{{us}} = {_fmt(V_us)}$ kN  

Total nominal shear capacity:  

- $V_u = V_{{uc}} + V_{{us}} = {_fmt(results['V_u_cap'])}$ kN  

Design capacity:

- $φ V_u = {_fmt(phi_V_u_cap)}$ kN  
- Utilisation: $V^* / (φ V_u) = {_fmt(V_util, '{{:.2f}}')}$  
"""
    )

    st.markdown("---")

    # ========================================================
    # 4. TORSION CHECK (TEACHING)
    # ========================================================
    phi_T_u_cap = results["phi_T_u_cap"]
    T_u_cap = results["T_u_cap"]
    T_util = results["T_util"]

    calcbox(
        f"""
**4. Torsion check (simplified)**  

Nominal torsion capacity (teaching approximation):

- $T_u = {_fmt(T_u_cap)}$ kNm  

Design capacity:

- $φ T_u = {_fmt(phi_T_u_cap)}$ kNm  
- Utilisation: $T^* / (φ T_u) = {_fmt(T_util, '{{:.2f}}')}$  
"""
    )

    st.markdown("---")

    # ========================================================
    # 5. SUMMARY TABLE
    # ========================================================
    st.markdown("## 5. Summary of key parameters")

    df = pd.DataFrame(
        [
            ["Design shear", "V*", _fmt(results["inputs"]["V_star"]), "kN", ""],
            ["Design torsion", "T*", _fmt(results["inputs"]["T_star"]), "kNm", ""],
            ["Shear depth", "d_v", _fmt(dv), "mm", "AS 3600 cl. 8.x"],
            ["Flexural strain", "ε_x", _fmt(results["eps_x"], "{:.6f}"), "–", "AS 3600 MCFT"],
            ["Concrete shear capacity", "V_uc", _fmt(V_uc), "kN", "AS 3600 cl. 8.x"],
            ["Steel shear capacity", "V_us", _fmt(V_us), "kN", "AS 3600 cl. 8.x"],
            ["Design shear capacity", "φV_u", _fmt(phi_V_u_cap), "kN", "φ_v from Inputs"],
            ["Shear utilisation", "V*/(φV_u)", _fmt(V_util), "–", ""],
            ["Design torsion capacity", "φT_u", _fmt(phi_T_u_cap), "kNm", "teaching"],
            ["Torsion utilisation", "T*/(φT_u)", _fmt(T_util), "–", ""],
        ],
        columns=["Quantity", "Symbol", "Value", "Units", "Notes / Reference"],
    )

    summary_placeholder.dataframe(df, use_container_width=True)
