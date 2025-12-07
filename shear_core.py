# shear_core.py
from dataclasses import dataclass
import math
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
    legs = inp.legs or 2.0
    s = inp.s_lig or 200.0
    use_general_kv = inp.use_general_kv
    sum_duct = inp.sum_duct
    k_d = inp.k_d

    # ---------------- Torsion geometry & cracking torque ----------------
    cover_t = 40.0
    A_cp = b * D
    u_c = 2 * (b + D)
    Ao = 0.9 * A_cp
    uh = 2 * ((b - cover_t) + (D - cover_t))
    A_oh = (b - cover_t) * (D - cover_t)

    sqrt_fc = math.sqrt(fc)
    denom = 0.33 * sqrt_fc
    Tcr_Nmm = 0.33 * sqrt_fc * (A_cp**2) / u_c * math.sqrt(
        1 + (sigma_cp / denom if denom > 0 else 0.0)
    )
    Tcr_kNm = Tcr_Nmm / 1e6
    torsion_required_limit = 0.25 * phi * Tcr_kNm
    torsion_required = T_star > torsion_required_limit

    # ---------------- Equivalent shear Veq* ----------------
    T_star_Nmm = T_star * 1e6
    torsion_eq_N = 0.9 * T_star_Nmm * uh / (2.0 * (Ao or 1.0))
    Vt_eq_kN = torsion_eq_N / 1e3
    V_eq = math.sqrt(V_star**2 + Vt_eq_kN**2)

    # ---------------- Shear reinforcement & effective section -----------
    Asv = legs * math.pi * lig_d**2 / 4.0
    f_syv = fsy

    b_v = b - k_d * sum_duct
    d_v = max(0.72 * D, 0.9 * d)

    # ---------------- Longitudinal strain εx ----------------------------
    M_star_Nmm = abs(M_star) * 1e6
    term_M = M_star_Nmm / (d_v or 1.0)

    Vprime_kN = abs(V_star) - P_v
    Vprime_N = Vprime_kN * 1e3

    torsion_N = 0.97 * T_star_Nmm * uh / (2.0 * (Ao or 1.0))
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

    # ---------------- Sectional shear -----------------------------------
    sqrt_fc_limited = min(math.sqrt(fc), 8.0)
    Vuc_N = k_v * b_v * d_v * sqrt_fc_limited
    Vuc_kN = Vuc_N / 1e3

    Vus_N = (Asv * f_syv * d_v / s) * cot(theta_v_rad)
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
    term_V = V_star_N / (b_v * d_v or 1.0)
    T_star_Nmm = T_star * 1e6
    term_T = T_star_Nmm * uh / (1.7 * (A_oh**2 or 1.0))

    LHS = math.sqrt(term_V**2 + term_T**2)
    RHS = phi * Vu_max_N / (b_v * d_v or 1.0)
    web_ok = LHS <= RHS

    return ShearResults(
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
    
    # Update session state
    update_results(
        phi_Vu_cap=results.phi_Vu,
        Vu_utilisation=shear_util if not math.isnan(shear_util) else 0.0,
    )
    
    return {
        "phi_Vu_cap": results.phi_Vu,
        "Vu_utilisation": shear_util,
        "V_eq": results.V_eq,
        "Vuc_kN": results.Vuc_kN,
        "Vus_kN": results.Vus_kN,
        "shear_ok": results.shear_ok,
    }
