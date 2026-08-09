"""V2-owned AS 3600 shear and torsion capacity calculation."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ShearCapacityInput:
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
    lig_d: float | None
    legs: float | None
    s_lig: float | None
    use_general_kv: bool
    sum_duct: float
    k_d: float

def effective_shear_depth_mm(D_mm: float, d_mm: float) -> float:
    """AS 3600 shear effective depth dv = max(0.72D, 0.9d)."""
    return max(0.72 * float(D_mm or 0.0), 0.9 * float(d_mm or 0.0))

def minimum_shear_reinforcement_asv_per_s(
    fc_mpa: float,
    b_v_mm: float,
    f_syv_mpa: float,
    *,
    fc_floor: float = 0.0,
) -> float:
    """Minimum shear reinforcement ratio Asv/s in mm2/mm."""
    fc = max(float(fc_mpa or 0.0), float(fc_floor))
    return 0.08 * math.sqrt(fc) * float(b_v_mm or 0.0) / (float(f_syv_mpa or 0.0) or 1.0)

def torsion_section_geometry_values(
    b_mm: float,
    D_mm: float,
    *,
    cover_t_mm: float = 40.0,
) -> dict[str, float]:
    """Torsion section geometry values used by shear capacity and check displays."""
    b = float(b_mm or 0.0)
    D = float(D_mm or 0.0)
    cover_t = float(cover_t_mm or 0.0)
    b_inside = max(b - cover_t, 0.0)
    D_inside = max(D - cover_t, 0.0)
    A_cp = b * D
    return {
        "b_used": b,
        "D_used": D,
        "A_cp": A_cp,
        "u_c": 2.0 * (b + D),
        "Ao": 0.9 * A_cp,
        "uh": 2.0 * (b_inside + D_inside),
        "A_oh": b_inside * D_inside,
    }

def aggregate_size_factor_kdg(fc_mpa: float, d_g_mm: float) -> float:
    """Aggregate-size factor kdg used by the general MCFT shear branch."""
    fc = float(fc_mpa or 0.0)
    d_g = float(d_g_mm or 0.0)
    if fc <= 65.0:
        k_dg = 32.0 / (16.0 + d_g)
        k_dg = max(k_dg, 0.8)
        if d_g >= 16.0:
            k_dg = max(k_dg, 1.0)
        return k_dg
    return 2.0

def mcft_kv_theta_values(
    *,
    use_general_kv: bool,
    fc_mpa: float,
    d_g_mm: float,
    eps_x: float,
    Asv_mm2: float,
    s_mm: float,
    b_v_mm: float,
    f_syv_mpa: float,
    d_v_mm: float,
    fc_floor: float = 0.0,
) -> dict[str, Any]:
    """MCFT k_v/theta branch values used by shear capacity and check displays."""
    eps = float(eps_x or 0.0)
    Asv = float(Asv_mm2 or 0.0)
    s = float(s_mm or 0.0)
    d_v = float(d_v_mm or 0.0)
    Asv_over_s = Asv / s
    Asv_min_over_s = minimum_shear_reinforcement_asv_per_s(
        fc_mpa,
        b_v_mm,
        f_syv_mpa,
        fc_floor=fc_floor,
    )
    low_stirrup_ratio = Asv_over_s < Asv_min_over_s

    if use_general_kv:
        k_dg = aggregate_size_factor_kdg(fc_mpa, d_g_mm)
        if low_stirrup_ratio:
            k_v = (0.4 / (1.0 + 1500.0 * eps)) * (1300.0 / (1000.0 + k_dg * d_v))
        else:
            k_v = 0.4 / (1.0 + 1500.0 * eps)
        theta_v_deg = 29.0 + 7000.0 * eps
    else:
        k_dg = float("nan")
        k_v = min(200.0 / (1000.0 + 1.3 * d_v), 0.10) if low_stirrup_ratio else 0.15
        theta_v_deg = 36.0

    return {
        "Asv_over_s": Asv_over_s,
        "Asv_min_over_s": Asv_min_over_s,
        "low_stirrup_ratio": low_stirrup_ratio,
        "k_dg": k_dg,
        "k_v": k_v,
        "theta_v_deg": theta_v_deg,
    }

def cotangent(rad: float) -> float:
    return 1.0 / math.tan(float(rad))

def _cot(rad: float) -> float:
    return cotangent(rad)

def stirrup_area_mm2(legs: float, diameter_mm: float) -> float:
    """Effective transverse reinforcement area for identical stirrup legs."""
    legs_eff = 0.0 if float(legs or 0.0) < 2.0 else float(legs or 0.0)
    return legs_eff * math.pi * float(diameter_mm or 0.0) ** 2 / 4.0

def compute_shear_capacity_values(inp: ShearCapacityInput) -> dict[str, Any]:
    """
    Pure AS 3600 shear/torsion capacity values from a ShearInputs-like object.

    The caller owns dataclass construction, Streamlit state, publication, and
    profiling. This function owns only the numerical result fields.
    """
    b = float(inp.b)
    D = float(inp.D)
    d = float(inp.d)
    fc = float(inp.fc)
    fsy = float(inp.fsy)
    Ec = float(inp.Ec)
    Es = float(inp.Es)
    M_star = float(inp.M_star)
    V_star = float(inp.V_star)
    T_star = float(inp.T_star)
    N_star = float(inp.N_star)
    P_v = float(inp.P_v)
    phi = float(inp.phi)
    sigma_cp = float(inp.sigma_cp)
    A_st = float(inp.A_st)
    A_pt = float(inp.A_pt)
    f_po = float(inp.f_po)
    A_ct = float(inp.A_ct)
    d_g = float(inp.d_g)
    lig_d = 10.0 if inp.lig_d is None else float(inp.lig_d)
    legs = 2.0 if inp.legs is None else float(inp.legs)
    legs_eff = 0.0 if legs < 2 else legs
    s = 200.0 if inp.s_lig is None else float(inp.s_lig)
    use_general_kv = bool(inp.use_general_kv)
    sum_duct = float(inp.sum_duct)
    k_d = float(inp.k_d)

    torsion_geometry = torsion_section_geometry_values(b, D)
    A_cp = torsion_geometry["A_cp"]
    u_c = torsion_geometry["u_c"]
    Ao = torsion_geometry["Ao"]
    uh = torsion_geometry["uh"]
    A_oh = torsion_geometry["A_oh"]

    T_used = T_star
    if u_c <= 0.0 or A_cp <= 0.0:
        Tcr_kNm = 0.0
        torsion_required = False
        torsion_required_limit = 0.0
        Vt_eq_kN = 0.0
        V_eq = abs(V_star)
        T_used = 0.0
    else:
        sqrt_fc = math.sqrt(max(fc, 0.1))
        denom = 0.33 * sqrt_fc
        Tcr_Nmm = 0.33 * sqrt_fc * (A_cp**2) / u_c * math.sqrt(
            1.0 + (sigma_cp / denom if denom > 0.0 else 0.0)
        )
        Tcr_kNm = Tcr_Nmm / 1e6
        torsion_required_limit = 0.25 * phi * Tcr_kNm
        torsion_required = T_star > torsion_required_limit
        T_used = T_star if torsion_required else 0.0

        T_used_Nmm = T_used * 1e6
        Ao_safe = max(Ao, 1.0)
        uh_safe = max(uh, 1.0)
        torsion_eq_N = 0.9 * T_used_Nmm * uh_safe / (2.0 * Ao_safe)
        Vt_eq_kN = torsion_eq_N / 1e3
        V_eq = abs(V_star) if not torsion_required else math.sqrt(V_star**2 + Vt_eq_kN**2)

    Asv = stirrup_area_mm2(legs_eff, lig_d)
    f_syv = fsy

    b_v = b - k_d * sum_duct
    d_v = effective_shear_depth_mm(D, d)
    s_safe = max(s, 1.0)

    M_star_Nmm = abs(M_star) * 1e6
    d_v_safe = max(d_v, 1.0)
    term_M = M_star_Nmm / d_v_safe

    Vprime_kN = abs(V_star) - P_v
    Vprime_N = Vprime_kN * 1e3
    Ao_safe = max(Ao, 1.0)
    uh_safe = max(uh, 1.0)
    T_used_Nmm = T_used * 1e6
    torsion_N = 0.97 * T_used_Nmm * uh_safe / (2.0 * Ao_safe)
    sqrt_inner = math.sqrt(Vprime_N**2 + torsion_N**2)

    N_star_N = 0.5 * N_star * 1e3
    A_pt_fpo_N = A_pt * f_po
    numerator = term_M + sqrt_inner + N_star_N - A_pt_fpo_N

    Ep = 195000.0
    denom1 = 2.0 * (Es * A_st + Ep * A_pt)
    eps_x_1 = numerator / denom1 if denom1 > 0.0 else 0.0
    if eps_x_1 < 0.0:
        denom2 = 2.0 * (Es * A_st + Ep * A_pt + Ec * A_ct)
        eps_x = numerator / denom2 if denom2 > 0.0 else 0.0
        eps_x = max(-0.0002, min(eps_x, 0.0))
    else:
        eps_x = max(0.0, min(eps_x_1, 0.003))

    mcft = mcft_kv_theta_values(
        use_general_kv=use_general_kv,
        fc_mpa=fc,
        d_g_mm=d_g,
        eps_x=eps_x,
        Asv_mm2=Asv,
        s_mm=s_safe,
        b_v_mm=b_v,
        f_syv_mpa=f_syv,
        d_v_mm=d_v_safe,
        fc_floor=0.1,
    )
    k_v = float(mcft["k_v"])
    theta_v_deg = float(mcft["theta_v_deg"])

    theta_v_rad = math.radians(theta_v_deg)

    sqrt_fc_limited = min(math.sqrt(max(fc, 0.1)), 8.0)
    Vuc_N = k_v * b_v * d_v_safe * sqrt_fc_limited
    Vuc_kN = Vuc_N / 1e3
    Vus_N = 0.0 if legs_eff <= 0.0 else (Asv * f_syv * d_v_safe / s_safe) * _cot(theta_v_rad)
    Vus_kN = Vus_N / 1e3
    Vu_total_kN = Vuc_kN + Vus_kN + P_v
    phi_Vu = phi * Vu_total_kN
    shear_ok = phi_Vu >= V_eq

    theta_1_rad = math.radians(90.0)
    cot_theta_v = _cot(theta_v_rad)
    cot_theta_1 = _cot(theta_1_rad)
    Vu_max_N = 0.55 * fc * b_v * d_v * (cot_theta_v + cot_theta_1) / (
        1.0 + cot_theta_v**2
    ) + P_v * 1e3
    Vu_max_kN = Vu_max_N / 1e3

    V_star_N = V_star * 1e3
    b_v_d_v_safe = max(b_v * d_v_safe, 1.0)
    term_V = V_star_N / b_v_d_v_safe
    T_used_Nmm = T_used * 1e6
    A_oh_safe = max(abs(A_oh), 1.0)
    uh_safe = max(uh, 1.0)
    term_T = T_used_Nmm * uh_safe / (1.7 * (A_oh_safe**2))
    LHS = math.sqrt(term_V**2 + term_T**2)
    RHS = phi * Vu_max_N / b_v_d_v_safe
    web_ok = LHS <= RHS

    return {
        "b_used": b,
        "D_used": D,
        "A_cp": A_cp,
        "u_c": u_c,
        "Ao": Ao,
        "uh": uh,
        "A_oh": A_oh,
        "Tcr_kNm": Tcr_kNm,
        "torsion_required": torsion_required,
        "torsion_required_limit": torsion_required_limit,
        "Vt_eq_kN": Vt_eq_kN,
        "V_eq": V_eq,
        "b_v": b_v,
        "d_v": d_v,
        "Asv": Asv,
        "f_syv": f_syv,
        "eps_x": eps_x,
        "term_M": term_M,
        "sqrt_inner": sqrt_inner,
        "numerator": numerator,
        "k_v": k_v,
        "theta_v_deg": theta_v_deg,
        "theta_v_rad": theta_v_rad,
        "sqrt_fc_limited": sqrt_fc_limited,
        "Vuc_kN": Vuc_kN,
        "Vus_kN": Vus_kN,
        "Vu_total_kN": Vu_total_kN,
        "phi_Vu": phi_Vu,
        "shear_ok": shear_ok,
        "Vu_max_kN": Vu_max_kN,
        "LHS": LHS,
        "RHS": RHS,
        "web_ok": web_ok,
    }

__all__ = ["ShearCapacityInput", "compute_shear_capacity_values"]
