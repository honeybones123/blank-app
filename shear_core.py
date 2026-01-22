# shear_core.py
from dataclasses import dataclass
import math
import streamlit as st
from state_and_helpers import get_param, update_results


@dataclass
class ShearInputs:
    b: float
    D: float
    d: float
    fc: float
    fsy: float
    Ec: float
    Es: float
    M_star: float
    V_star: float
    T_star: float
    N_star: float
    P_v: float
    phi: float
    sigma_cp: float
    A_st: float
    A_pt: float
    f_po: float
    A_ct: float
    d_g: float
    lig_d: float
    legs: float
    s_lig: float
    use_general_kv: bool
    sum_duct: float
    k_d: float


@dataclass
class ShearResults:
    # torsion cracking
    b_used: float
    D_used: float
    A_cp: float
    u_c: float
    Ao: float
    uh: float
    A_oh: float
    Tcr_kNm: float
    torsion_required: bool
    torsion_required_limit: float

    # equivalent shear
    Vt_eq_kN: float
    V_eq: float

    # effective web
    b_v: float
    d_v: float
    Asv: float
    f_syv: float

    # strain
    eps_x: float
    term_M: float
    sqrt_inner: float
    numerator: float

    # k_v and theta
    k_v: float
    theta_v_deg: float
    theta_v_rad: float

    # sectional shear
    sqrt_fc_limited: float
    Vuc_kN: float
    Vus_kN: float
    Vu_total_kN: float
    phi_Vu: float
    shear_ok: bool

    # web crushing
    Vu_max_kN: float
    LHS: float
    RHS: float
    web_ok: bool


def cot(rad: float) -> float:
    return 1.0 / math.tan(rad)


def derive_eps_top_bot_for_step4_diagram(eps_x: float, delta: float = 0.00035):
    """
    Diagram-only helper.
    Create a simple linear profile around eps_x so the user can visualize
    top/mid/bottom strain points. Does NOT affect design calcs.
    """
    ex = float(eps_x)
    return ex - float(delta), ex + float(delta)


def run_shear_calc(inp: ShearInputs) -> ShearResults:
    b = inp.b
    D = inp.D
    d = inp.d
    fc = inp.fc
    fsy = inp.fsy
    Ec = inp.Ec
    Es = inp.Es
    M_star = inp.M_star
    V_star = inp.V_star
    T_star = inp.T_star
    N_star = inp.N_star
    P_v = inp.P_v
    phi = inp.phi
    sigma_cp = inp.sigma_cp
    A_st = inp.A_st
    A_pt = inp.A_pt
    f_po = inp.f_po
    A_ct = inp.A_ct
    d_g = inp.d_g
    lig_d = inp.lig_d or 10.0
    legs = 2.0 if inp.legs is None else float(inp.legs)
    s = inp.s_lig or 200.0
    use_general_kv = inp.use_general_kv
    sum_duct = inp.sum_duct
    k_d = inp.k_d

    # ---------------- Torsion geometry & cracking torque ----------------
    cover_t = 40.0
    A_cp = b * D
    u_c = 2 * (b + D)
    Ao = 0.9 * A_cp
    uh = 2 * (max(b - cover_t, 0.0) + max(D - cover_t, 0.0))
    A_oh = max(b - cover_t, 0.0) * max(D - cover_t, 0.0)

    # Safety checks to prevent division by zero
    T_used = T_star
    if u_c <= 0 or A_cp <= 0:
        # Return zero capacity if geometry is invalid
        Tcr_kNm = 0.0
        torsion_required = False
        torsion_required_limit = 0.0
        Vt_eq_kN = 0.0
        V_eq = abs(V_star)
        T_used = 0.0
    else:
        sqrt_fc = math.sqrt(max(fc, 0.1))  # Prevent sqrt of negative
        denom = 0.33 * sqrt_fc
        Tcr_Nmm = 0.33 * sqrt_fc * (A_cp**2) / u_c * math.sqrt(
            1 + (sigma_cp / denom if denom > 0 else 0.0)
        )
        Tcr_kNm = Tcr_Nmm / 1e6
        torsion_required_limit = 0.25 * phi * Tcr_kNm
        torsion_required = T_star > torsion_required_limit
        # If torsion design is NOT required, ignore torsion in subsequent strength checks
        T_used = T_star if torsion_required else 0.0

        # ---------------- Equivalent shear Veq* ----------------
        T_used_Nmm = T_used * 1e6
        Ao_safe = max(Ao, 1.0)  # Prevent division by zero
        uh_safe = max(uh, 1.0)  # Prevent division by zero
        torsion_eq_N = 0.9 * T_used_Nmm * uh_safe / (2.0 * Ao_safe)
        Vt_eq_kN = torsion_eq_N / 1e3
        V_eq = abs(V_star) if not torsion_required else math.sqrt(V_star**2 + Vt_eq_kN**2)

    # ---------------- Shear reinforcement & effective section -----------
    Asv = legs * math.pi * lig_d**2 / 4.0
    if legs == 0:
        Asv = 0.0
    f_syv = fsy

    b_v = b - k_d * sum_duct
    d_v = max(0.72 * D, 0.9 * d)

    # Safety check: prevent division by zero for spacing
    s_safe = max(s, 1.0)  # Minimum 1mm spacing to prevent division by zero

    # ---------------- Longitudinal strain εx ----------------------------
    M_star_Nmm = abs(M_star) * 1e6
    d_v_safe = max(d_v, 1.0)  # Prevent division by zero
    term_M = M_star_Nmm / d_v_safe

    Vprime_kN = abs(V_star) - P_v
    Vprime_N = Vprime_kN * 1e3

    # Use safe values for torsion calculation
    Ao_safe = max(Ao, 1.0)  # Prevent division by zero
    uh_safe = max(uh, 1.0)  # Prevent division by zero
    T_used_Nmm = T_used * 1e6
    torsion_N = 0.97 * T_used_Nmm * uh_safe / (2.0 * Ao_safe)
    sqrt_inner = math.sqrt(Vprime_N**2 + torsion_N**2)

    N_star_N = 0.5 * N_star * 1e3
    A_pt_fpo_N = A_pt * f_po

    numerator = term_M + sqrt_inner + N_star_N - A_pt_fpo_N

    Ep = 195000.0
    denom1 = 2.0 * (Es * A_st + Ep * A_pt)
    eps_x_1 = numerator / denom1 if denom1 > 0 else 0.0

    if eps_x_1 < 0:
        denom2 = 2.0 * (Es * A_st + Ep * A_pt + Ec * A_ct)
        eps_x = numerator / denom2 if denom2 > 0 else 0.0
        eps_x = max(-0.0002, min(eps_x, 0.0))
    else:
        eps_x = max(0.0, min(eps_x_1, 0.003))

    # ---------------- k_v and θ_v ---------------------------------------
    if use_general_kv:
        if fc <= 65:
            k_dg = 32.0 / (16.0 + d_g)
            k_dg = max(k_dg, 0.8)
            if d_g >= 16:
                k_dg = max(k_dg, 1.0)
        else:
            k_dg = 2.0

        Asv_over_s = Asv / s_safe
        Asv_min_over_s = 0.08 * math.sqrt(max(fc, 0.1)) * b_v / (f_syv or 1.0)

        if Asv_over_s < Asv_min_over_s:
            k_v = (0.4 / (1 + 1500 * eps_x)) * (1300 / (1000 + k_dg * d_v_safe))
        else:
            k_v = 0.4 / (1 + 1500 * eps_x)

        theta_v_deg = 29.0 + 7000.0 * eps_x
    else:
        if Asv / s_safe < 0.08 * math.sqrt(max(fc, 0.1)) * b_v / (f_syv or 1.0):
            k_v = min(200.0 / (1000.0 + 1.3 * d_v_safe), 0.10)
        else:
            k_v = 0.15
        theta_v_deg = 36.0

    theta_v_rad = math.radians(theta_v_deg)

    # ---------------- Sectional shear -----------------------------------
    sqrt_fc_limited = min(math.sqrt(max(fc, 0.1)), 8.0)
    Vuc_N = k_v * b_v * d_v_safe * sqrt_fc_limited
    Vuc_kN = Vuc_N / 1e3

    Vus_N = 0.0 if legs == 0 else (Asv * f_syv * d_v_safe / s_safe) * cot(theta_v_rad)
    Vus_kN = Vus_N / 1e3

    Vu_total_kN = Vuc_kN + Vus_kN + P_v
    phi_Vu = phi * Vu_total_kN
    shear_ok = phi_Vu >= V_eq

    # ---------------- Web crushing --------------------------------------
    theta_1_deg = 90.0
    theta_1_rad = math.radians(theta_1_deg)
    cot_theta_v = cot(theta_v_rad)
    cot_theta_1 = cot(theta_1_rad)

    Vu_max_N = 0.55 * fc * b_v * d_v * (cot_theta_v + cot_theta_1) / (
        1 + cot_theta_v**2
    ) + P_v * 1e3
    Vu_max_kN = Vu_max_N / 1e3

    V_star_N = V_star * 1e3
    b_v_d_v_safe = max(b_v * d_v_safe, 1.0)  # Prevent division by zero
    term_V = V_star_N / b_v_d_v_safe
    T_used_Nmm = T_used * 1e6
    A_oh_safe = max(abs(A_oh), 1.0)  # Prevent division by zero
    uh_safe = max(uh, 1.0)  # Prevent division by zero
    term_T = T_used_Nmm * uh_safe / (1.7 * (A_oh_safe**2))

    LHS = math.sqrt(term_V**2 + term_T**2)
    RHS = phi * Vu_max_N / b_v_d_v_safe
    web_ok = LHS <= RHS

    return ShearResults(
        b_used=b,
        D_used=D,
        A_cp=A_cp,
        u_c=u_c,
        Ao=Ao,
        uh=uh,
        A_oh=A_oh,
        Tcr_kNm=Tcr_kNm,
        torsion_required=torsion_required,
        torsion_required_limit=torsion_required_limit,
        Vt_eq_kN=Vt_eq_kN,
        V_eq=V_eq,
        b_v=b_v,
        d_v=d_v,
        Asv=Asv,
        f_syv=f_syv,
        eps_x=eps_x,
        term_M=term_M,
        sqrt_inner=sqrt_inner,
        numerator=numerator,
        k_v=k_v,
        theta_v_deg=theta_v_deg,
        theta_v_rad=theta_v_rad,
        sqrt_fc_limited=sqrt_fc_limited,
        Vuc_kN=Vuc_kN,
        Vus_kN=Vus_kN,
        Vu_total_kN=Vu_total_kN,
        phi_Vu=phi_Vu,
        shear_ok=shear_ok,
        Vu_max_kN=Vu_max_kN,
        LHS=LHS,
        RHS=RHS,
        web_ok=web_ok,
    )


# ------------------------------------------------------------
#  CORE COMPUTE FUNCTION (reads from session state, no UI)
# ------------------------------------------------------------
def _compute_shear_capacity():
    """
    Compute shear capacity using current session state values.
    Reads all inputs from get_param(), calls run_shear_calc(), and updates results.
    No Streamlit UI - pure computation.
    """
    # Read geometry and materials
    b = get_param("b", 300.0)
    D = get_param("D", 600.0)
    d = get_param("d", 560.0)
    fc = get_param("fc", 32.0)
    fsy = get_param("fsy", 500.0)
    Ec = get_param("Ec", 30000.0)
    Es = get_param("Es", 200000.0)
    
    # Read actions
    M_star = get_param("Mu_star", 0.0)
    V_star = get_param("Vu_star", 0.0)
    T_star = get_param("Tu_star", 0.0)
    N_star = get_param("N_star", 0.0)
    P_v = get_param("P_star", 0.0)
    
    # Read reinforcement
    lig_d = get_param("lig_d", 10.0)
    legs = get_param("lig_legs", 2)
    s_lig = get_param("s_lig", 200.0)
    
    # Default values for prestress/ducts (not commonly used)
    A_st = get_param("Ast_bot", 0.0)
    A_pt = 0.0
    f_po = 0.0
    A_ct = b * D / 2.0  # Approximate
    d_g = 20.0  # Default aggregate size
    sum_duct = get_param("n_ducts", 0) * get_param("duct_dia", 0.0) if get_param("n_ducts", 0) > 0 else 0.0
    k_d = 0.0  # No ducts by default
    
    # Shear parameters
    use_general_kv = True  # Use general method by default
    phi = get_param("phi_shear", 0.75)  # Default shear phi
    sigma_cp = 0.0  # No prestress compression by default
    
    # Build shape_name/dims/reo for diagrams (same logic as Inputs/Bending)
    sec_shape = get_param("sec_shape", "RECT")
    if sec_shape == "T":
        shape_name = "T-Section"
        dims = {
            "bf": float(get_param("bf", 600.0)),
            "tf": float(get_param("tf", 120.0)),
            "bw": float(get_param("bw", 300.0)),
            "D":  float(get_param("D", 600.0)),
        }
    elif sec_shape == "I":
        shape_name = "I-Section"
        dims = {
            "bf": float(get_param("bf", 600.0)),
            "tf": float(get_param("tf", 120.0)),
            "tw": float(get_param("tw", 200.0)),
            "D":  float(get_param("D", 600.0)),
        }
    else:
        shape_name = "Rectangle (b × D)"
        dims = {
            "b": float(get_param("b", 300.0)),
            "D": float(get_param("D", 600.0)),
        }

    cover_top = float(get_param("cover_top", 40.0))
    cover_bot = float(get_param("cover_bot", 40.0))
    cover_side = get_param("cover_side", None)
    if cover_side is None:
        cover_side = min(cover_top, cover_bot)
    cover_side = float(cover_side)
    s_min = float(get_param("s_min", 25.0))

    reo = {
        "cover_top": cover_top,
        "cover_bot": cover_bot,
        "cover_side": cover_side,
        # Bottom
        "bot1_layout_mode": st.session_state.get("inputs_bot1_layout_mode", st.session_state.get("bot1_layout_mode", "Count")),
        "nb_or_s_bot_1": float(get_param("nb_or_s_bot_1", 4.0)),
        "db_bot_1": float(get_param("db_bot_1", 20.0)),
        "bot2_layout_mode": st.session_state.get("inputs_bot2_layout_mode", st.session_state.get("bot2_layout_mode", "Count")),
        "nb_or_s_bot_2": float(get_param("nb_or_s_bot_2", 0.0)),
        "db_bot_2": float(get_param("db_bot_2", 20.0)),
        "rowgap_bot": float(get_param("rowgap_bot", 60.0)),
        # Top
        "top1_layout_mode": st.session_state.get("inputs_top1_layout_mode", st.session_state.get("top1_layout_mode", "Count")),
        "nb_or_s_top_1": float(get_param("nb_or_s_top_1", 2.0)),
        "db_top_1": float(get_param("db_top_1", 20.0)),
        "top2_layout_mode": st.session_state.get("inputs_top2_layout_mode", st.session_state.get("top2_layout_mode", "Count")),
        "nb_or_s_top_2": float(get_param("nb_or_s_top_2", 0.0)),
        "db_top_2": float(get_param("db_top_2", 20.0)),
        "rowgap_top": float(get_param("rowgap_top", 60.0)),
        # Backwards-compatible totals
        "nb_top": int(float(get_param("nb_or_s_top_1", 2.0)) + float(get_param("nb_or_s_top_2", 0.0))),
        "db_top": float(get_param("db_top_1", 20.0)),
        "nb_bot": int(float(get_param("nb_or_s_bot_1", 4.0)) + float(get_param("nb_or_s_bot_2", 0.0))),
        "db_bot": float(get_param("db_bot_1", 20.0)),
        "min_clear_spacing": s_min,
        "lig_d": float(get_param("lig_d", 0.0)),
        "lig_legs": int(get_param("lig_legs", 0)),
    }

    # Build input object
    inp = ShearInputs(
        b=b,
        D=D,
        d=d,
        fc=fc,
        fsy=fsy,
        Ec=Ec,
        Es=Es,
        M_star=M_star,
        V_star=V_star,
        T_star=T_star,
        N_star=N_star,
        P_v=P_v,
        phi=phi,
        sigma_cp=sigma_cp,
        A_st=A_st,
        A_pt=A_pt,
        f_po=f_po,
        A_ct=A_ct,
        d_g=d_g,
        lig_d=lig_d,
        legs=legs,
        s_lig=s_lig,
        use_general_kv=use_general_kv,
        sum_duct=sum_duct,
        k_d=k_d,
    )
    
    # Run calculation
    results = run_shear_calc(inp)
    
    # Calculate utilisation
    shear_util = results.V_eq / results.phi_Vu if results.phi_Vu > 0 else float("nan")
    
    # Calculate crushing utilisation (web crushing check)
    # Capacity is phi * Vu_max, demand is V_eq
    phi_Vu_max = phi * results.Vu_max_kN
    Vuc_util = results.V_eq / phi_Vu_max if phi_Vu_max > 0 else float("nan")
    
    # ------------------ Build detailed shear steps (for PDF) ------------------
    shear_steps = [
        {
            "title": "Inputs & actions",
            "clause": "AS 3600:2018 Cl. 8.2",
            "formula": ["Given design inputs"],
            "substitution": [
                f"b = {inp.b:.0f} mm, D = {inp.D:.0f} mm, d = {inp.d:.0f} mm",
                f"f'c = {inp.fc:.1f} MPa, f_sy = {inp.fsy:.0f} MPa",
                f"M* = {inp.M_star:.1f} kNm, V* = {inp.V_star:.1f} kN, T* = {inp.T_star:.2f} kNm",
                f"φ = {inp.phi:.2f}",
            ],
            "equations": [
                f"b = {inp.b:.0f} mm, D = {inp.D:.0f} mm, d = {inp.d:.0f} mm",
                f"f'c = {inp.fc:.1f} MPa, f_sy = {inp.fsy:.0f} MPa",
                f"M* = {inp.M_star:.1f} kNm, V* = {inp.V_star:.1f} kN, T* = {inp.T_star:.2f} kNm",
                f"φ = {inp.phi:.2f}",
            ],
            "result": f"V* = {inp.V_star:.1f} kN",
            "notes": [],
            "status": "info",
            "diagram": None,
        },
        {
            "title": "Torsion cracking check (screening)",
            "clause": "AS 3600:2018 Cl. 8.2.1",
            "formula": [
                "T_cr = 0.33√f'c · A_cp²/u_c · √(1+σ_cp/(0.33√f'c))",
                "T_req?  T* > 0.25φT_cr",
            ],
            "substitution": [
                f"A_cp = b·D = {results.A_cp:.0f} mm²",
                f"u_c = 2(b + D) = {results.u_c:.0f} mm",
                f"T_cr = {results.Tcr_kNm:.2f} kNm",
                f"T* ? 0.25φT_cr ⇒ {inp.T_star:.2f} ? {results.torsion_required_limit:.2f}",
            ],
            "equations": [
                f"A_cp = b·D = {results.A_cp:.0f} mm²",
                f"u_c = 2(b + D) = {results.u_c:.0f} mm",
                f"T_cr = {results.Tcr_kNm:.2f} kNm",
                f"T_req?  T* > 0.25φT_cr  ⇒  {inp.T_star:.2f} > {results.torsion_required_limit:.2f}",
            ],
            "result": f"Torsion required: {results.torsion_required}",
            "notes": [f"Torsion required: {results.torsion_required}"],
            "status": "info",
            "diagram": None,
        },
        {
            "title": "Equivalent shear",
            "clause": "AS 3600:2018 Cl. 8.2.1",
            "formula": [
                "V_t,eq = 0.9·T*·u_h/(2A_o)",
                "V_eq = √(V*² + V_t,eq²)",
            ],
            "substitution": [
                f"V_t,eq = {results.Vt_eq_kN:.1f} kN",
                f"V_eq = √(V*² + V_t,eq²) = {results.V_eq:.1f} kN",
            ],
            "equations": [
                f"V_t,eq = {results.Vt_eq_kN:.1f} kN",
                f"V_eq = √(V*² + V_t,eq²) = {results.V_eq:.1f} kN",
            ],
            "result": f"V_eq = {results.V_eq:.1f} kN",
            "notes": [],
            "status": "info",
            "diagram": None,
        },
        {
            "title": "Effective web section",
            "clause": "AS 3600:2018 Cl. 8.2.4",
            "formula": [
                "b_v = b - k_d·Σduct",
                "d_v = max(0.72D, 0.9d)",
            ],
            "substitution": [
                f"b_v = {results.b_v:.1f} mm",
                f"d_v = max(0.72D, 0.9d) = {results.d_v:.1f} mm",
            ],
            "equations": [
                f"b_v = {results.b_v:.1f} mm",
                f"d_v = max(0.72D, 0.9d) = {results.d_v:.1f} mm",
            ],
            "result": f"b_v={results.b_v:.1f} mm, d_v={results.d_v:.1f} mm",
            "notes": [],
            "status": "info",
            "diagram": None,
        },
        {
            "title": "Longitudinal strain εx",
            "clause": "AS 3600:2018 Cl. 8.2.4",
            "formula": [
                "εx = (|M*|/d_v + √(V'² + T'²) + N* - A_pt f_po) / (2(EsAst + EpApt) ...)",
            ],
            "substitution": [
                f"term_M = |M*|/d_v = {results.term_M:.3e}",
                f"√(V'² + T'²) = {results.sqrt_inner:.3e}",
                f"εx = {results.eps_x:.6f}",
            ],
            "equations": [
                f"term_M = |M*|/d_v = {results.term_M:.3e}",
                f"√(V'² + T'²) = {results.sqrt_inner:.3e}",
                f"εx = {results.eps_x:.6f}",
            ],
            "result": f"εx = {results.eps_x:.6f}",
            "notes": [],
            "status": "info",
            "diagram": None,
        },
        {
            "title": "MCFT parameters (k_v, θ_v)",
            "clause": "AS 3600:2018 Cl. 8.2.4",
            "formula": [
                "k_v = f(εx, d_v, aggregate size)",
                "θ_v = f(εx)",
            ],
            "substitution": [
                f"k_v = {results.k_v:.3f}",
                f"θ_v = {results.theta_v_deg:.1f}°",
            ],
            "equations": [
                f"k_v = {results.k_v:.3f}",
                f"θ_v = {results.theta_v_deg:.1f}°",
            ],
            "result": f"k_v={results.k_v:.3f}, θ_v={results.theta_v_deg:.1f}°",
            "notes": [],
            "status": "info",
            "diagram": None,
        },
        {
            "title": "Concrete shear capacity V_uc",
            "clause": "AS 3600:2018 Cl. 8.2.4.1",
            "formula": [
                "V_uc = k_v · b_v · d_v · min(√f'c, 8)",
                "φV_uc = φ · V_uc",
            ],
            "substitution": [
                f"= {results.k_v:.3f} · {results.b_v:.0f} · {results.d_v:.0f} · min(√{inp.fc:.1f}, 8)",
                f"= {results.Vuc_kN:.1f} kN",
            ],
            "equations": [
                f"V_uc = {results.Vuc_kN:.1f} kN",
            ],
            "result": f"V_uc = {results.Vuc_kN:.1f} kN",
            "notes": [],
            "status": "info",
            "diagram": None,
        },
        {
            "title": "Steel shear capacity V_us",
            "clause": "AS 3600:2018 Cl. 8.2.7",
            "formula": [
                "V_us = (A_sv · f_syv · d_v / s) · cotθ_v",
            ],
            "substitution": [
                f"= ({results.Asv:.1f} · {results.f_syv:.0f} · {results.d_v:.0f} / {inp.s_lig:.0f}) · cot{results.theta_v_deg:.1f}°",
                f"= {results.Vus_kN:.1f} kN",
            ],
            "equations": [
                f"V_us = {results.Vus_kN:.1f} kN",
            ],
            "result": f"V_us = {results.Vus_kN:.1f} kN",
            "notes": [],
            "status": "info",
            "diagram": None,
        },
        {
            "title": "Total shear capacity & utilisation",
            "clause": "AS 3600:2018 Cl. 8.2",
            "formula": [
                "V_u = V_uc + V_us + P_v",
                "φV_u = φ · V_u",
                "Util = V_eq/(φV_u)",
            ],
            "substitution": [
                f"V_u = {results.Vu_total_kN:.1f} kN",
                f"φV_u = {results.phi_Vu:.1f} kN",
                f"Util = {results.V_eq:.1f}/{results.phi_Vu:.1f} = "
                f"{(results.V_eq/results.phi_Vu if results.phi_Vu>0 else 0):.2f}",
            ],
            "equations": [
                f"V_u = V_uc + V_us + P_v = {results.Vu_total_kN:.1f} kN",
                f"φV_u = {results.phi_Vu:.1f} kN",
                f"Util = V_eq/(φV_u) = {results.V_eq:.1f}/{results.phi_Vu:.1f} = "
                f"{(results.V_eq/results.phi_Vu if results.phi_Vu>0 else 0):.2f}",
            ],
            "result": f"φV_u = {results.phi_Vu:.1f} kN",
            "notes": [("PASS" if results.shear_ok else "FAIL")],
            "status": ("pass" if results.shear_ok else "fail"),
            "diagram": None,
        },
        {
            "title": "Web crushing check",
            "clause": "AS 3600:2018 Cl. 8.2.5",
            "formula": [
                "V_u,max = 0.55 f'c b_v d_v (cotθ_v + cotθ_1) / (1 + cot²θ_v) + P_v",
                "Check: LHS ≤ RHS",
            ],
            "substitution": [
                f"V_u,max = {results.Vu_max_kN:.1f} kN",
                f"LHS = {results.LHS:.3e}, RHS = {results.RHS:.3e}",
            ],
            "equations": [
                f"V_u,max = {results.Vu_max_kN:.1f} kN",
                f"LHS = {results.LHS:.3e}, RHS = {results.RHS:.3e}",
            ],
            "result": f"V_u,max = {results.Vu_max_kN:.1f} kN",
            "notes": [("PASS" if results.web_ok else "FAIL")],
            "status": ("pass" if results.web_ok else "fail"),
            "diagram": None,
        },
    ]

    # ------------------ Build bending-style shear_report (tabs/boxes/derivations + diagrams) ------------------
    from reporting.report_content import make_calc_box, make_tab, make_module_report
    from reporting.fig_export import export_box_diagram_png
    try:
        # package form
        from reporting.fig_export import call_with_supported_kwargs
    except Exception:
        # local flat-file fallback
        from fig_export import call_with_supported_kwargs
    from shear_diagrams import (
        plot_shear_torsion_section_2d,
        plot_shear_step1_theta_cracks_3d,
        make_mcft_longitudinal_strain_profile_fig,
    )

    eps_top, eps_bot = derive_eps_top_bot_for_step4_diagram(results.eps_x)

    L_mm = float(get_param("L", 0.0))
    if not L_mm or L_mm <= 0:
        L_mm = float(get_param("span_L_m", 3.0)) * 1000.0

    diag1 = export_box_diagram_png(
        lambda: call_with_supported_kwargs(
            plot_shear_step1_theta_cracks_3d,
            L_mm=L_mm,
            b_mm=inp.b,
            D_mm=inp.D,
            theta_deg=getattr(results, "theta_v_deg", 45.0),
        ),
        key="shear_1_torsion",
        caption="Torsion cracking / diagonal crack field",
        w_mm=65,
        h_mm=40,
    )
    diag2 = export_box_diagram_png(
        lambda: plot_shear_torsion_section_2d(
            shape_name=shape_name,
            dims=dims,
            reo=reo,
            show_labels=True,
        ),
        key="shear_2_section",
        caption="Section + torsion/shear idealisation",
        w_mm=65,
        h_mm=40,
    )
    diag3 = export_box_diagram_png(
        lambda: make_mcft_longitudinal_strain_profile_fig(eps_top, results.eps_x, eps_bot),
        key="shear_4_epsx",
        caption="MCFT longitudinal strain profile",
        w_mm=65,
        h_mm=40,
    )

    def _step_to_box(idx, s, diagram=None):
        eqs = s.get("equations", []) or []
        clause = s.get("clause", "")
        status = s.get("status", None)
        result_line = s.get("result") or (eqs[-1] if eqs else "")

        deriv = []
        formula = s.get("formula") or s.get("formula_lines") or []
        subst = s.get("substitution") or s.get("sub_lines") or []
        if isinstance(formula, str):
            formula = [formula]
        if isinstance(subst, str):
            subst = [subst]

        if formula:
            deriv.append({"label": "Formula", "eq": "", "sub": ""})
            for line in formula:
                deriv.append({"label": "", "eq": line, "sub": ""})

        if subst:
            deriv.append({"label": "Substitution", "eq": "", "sub": ""})
            for line in subst:
                deriv.append({"label": "", "eq": line, "sub": ""})

        for line in eqs:
            deriv.append({"label": "", "eq": line, "sub": ""})

        return make_calc_box(
            id=f"1.{idx}",
            title=s.get("title", f"Shear check {idx}"),
            status=status,
            result=result_line,
            clause=clause,
            derivation=deriv,
            diagram=diagram,
        )

    if len(shear_steps) >= 2:
        shear_steps[1]["diagram"] = diag1
    if len(shear_steps) >= 4:
        shear_steps[3]["diagram"] = diag2
    if len(shear_steps) >= 5:
        shear_steps[4]["diagram"] = diag3

    boxes = []
    for i, s in enumerate(shear_steps, start=1):
        diagram = None
        if i == 2:
            diagram = diag1
        elif i == 4:
            diagram = diag2
        elif i == 5:
            diagram = diag3
        boxes.append(_step_to_box(i, s, diagram=diagram))

    shear_report = make_module_report(
        module_title="Shear (ULS)",
        tabs=[make_tab("ULS Checks", boxes)],
    )

    # Update session state
    update_results(
        phi_Vu_cap=results.phi_Vu,
        Vu_utilisation=shear_util if not math.isnan(shear_util) else 0.0,
        Vu_max_kN=results.Vu_max_kN,
        phi_Vu_max_kN=phi_Vu_max,
        V_eq_kN=results.V_eq,
        Vuc_utilisation=Vuc_util if not math.isnan(Vuc_util) else None,
        shear_steps=shear_steps,
        shear_report=shear_report,
    )
    
    return {
        "phi_Vu_cap": results.phi_Vu,
        "Vu_utilisation": shear_util,
        "V_eq": results.V_eq,
        "Vuc_kN": results.Vuc_kN,
        "Vus_kN": results.Vus_kN,
        "shear_ok": results.shear_ok,
    }
