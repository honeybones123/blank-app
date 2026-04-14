# shear_core.py
from dataclasses import dataclass, replace
import math
import json
import time
import os
import streamlit as st
import numpy as np
from state_and_helpers import (
    get_longitudinal_row_inputs,
    get_param,
    resolve_design_actions,
    apply_auto_design_results,
    update_results,
)

# region agent log
_DEBUG_LOG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "debug-b9a7cf.log")


def _dbg_log(message: str, data: dict, *, run_id: str, hypothesis_id: str) -> None:
    try:
        rec = {
            "sessionId": "b9a7cf",
            "runId": run_id,
            "hypothesisId": hypothesis_id,
            "location": "shear_core.py",
            "message": message,
            "data": data,
            "timestamp": int(time.time() * 1000),
        }
        with open(_DEBUG_LOG_PATH, "a", encoding="utf-8") as _f:
            _f.write(json.dumps(rec, default=str) + "\n")
    except Exception:
        pass


# endregion

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


class ShearLayoutError(ValueError):
    def __init__(self, message: str, *, payload: dict | None = None):
        super().__init__(message)
        self.payload = payload


def cot(rad: float) -> float:
    return 1.0 / math.tan(rad)


def required_asv_per_s(V, phi, Vuc, fy, dv, *, cot_theta_v: float = 1.0):
    """
    Required A_sv/s (mm^2/mm) from along-span shear demand array.
    Inputs V and Vuc in kN; fy in MPa; dv in mm.
    Matches sectional V_us = (A_sv/s)·f_yv·d_v·cot(θ_v) (AS 3600 truss analogy).
    """
    V_arr = np.asarray(V, dtype=float)
    phi_safe = max(float(phi or 0.0), 1e-9)
    fy_safe = max(float(fy or 0.0), 1e-9)
    dv_safe = max(float(dv or 0.0), 1e-9)
    cot_safe = max(float(cot_theta_v or 0.0), 1e-9)
    Vus_req_kN = np.maximum(V_arr - phi_safe * float(Vuc or 0.0), 0.0) / phi_safe
    return (Vus_req_kN * 1000.0) / (fy_safe * dv_safe * cot_safe)


def spacing_from_demand(
    Vi_kN: float,
    phi: float,
    Vuc_kN: float,
    fy_mpa: float,
    dv_mm: float,
    Asv_mm2: float,
    D_mm: float,
    s_min_mm: float,
    *,
    cot_theta_v: float = 1.0,
    increment_mm: float = 10.0,
) -> float:
    """Demand-based spacing from local V(x), clamped to code/practical limits."""
    s_max_mm = min(0.75 * max(float(D_mm), 1e-9), 500.0)
    phi_safe = max(float(phi or 0.0), 1e-9)
    cot_safe = max(float(cot_theta_v or 0.0), 1e-9)
    Vus_req_kN = max(float(Vi_kN) - phi_safe * float(Vuc_kN or 0.0), 0.0) / phi_safe
    if Vus_req_kN <= 1e-12:
        return float(s_max_mm)
    asv_s_req = (Vus_req_kN * 1000.0) / max(
        float(fy_mpa or 0.0) * float(dv_mm or 0.0) * cot_safe, 1e-9
    )
    s_raw = float(Asv_mm2) / max(asv_s_req, 1e-12)
    s = min(s_raw, s_max_mm)
    s = max(s, float(s_min_mm))
    inc = max(float(increment_mm), 1.0)
    # round down to stay conservative
    s = max(float(s_min_mm), min(s_max_mm, math.floor(s / inc + 1e-9) * inc))
    # final detailing round (5 mm increments)
    s = math.floor(s / 5.0) * 5.0
    # enforce limits again
    s = min(s, s_max_mm)
    s = max(s, float(s_min_mm))
    return float(s)


def compute_midspan_spacing_result(
    *,
    V_mid_kN: float,
    phi: float,
    Vuc_kN: float,
    fy_mpa: float,
    dv_mm: float,
    Asv_mm2: float,
    D_mm: float,
    s_min_mm: float,
    cot_theta_v: float,
    increment_mm: float,
) -> tuple[float, str]:
    """
    Required midspan spacing from shear demand at x = L/2 (same physics as spacing_from_demand).
    Returns (s_mm, mode) where mode is max_spacing or shear_demand.
    """
    phi_safe = max(float(phi), 1e-9)
    Vus_req_kN = max(float(V_mid_kN) - phi_safe * float(Vuc_kN), 0.0) / phi_safe
    mode = "max_spacing" if Vus_req_kN <= 1e-9 else "shear_demand"
    s_mm = spacing_from_demand(
        float(V_mid_kN),
        float(phi),
        float(Vuc_kN),
        float(fy_mpa),
        float(dv_mm),
        float(Asv_mm2),
        float(D_mm),
        float(s_min_mm),
        cot_theta_v=float(cot_theta_v),
        increment_mm=float(increment_mm),
    )
    return float(s_mm), str(mode)


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
    lig_d = 10.0 if inp.lig_d is None else float(inp.lig_d)
    legs = 2.0 if inp.legs is None else float(inp.legs)
    legs_eff = 0.0 if legs < 2 else legs
    s = 200.0 if inp.s_lig is None else float(inp.s_lig)
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
    Asv = legs_eff * math.pi * lig_d**2 / 4.0
    if legs_eff <= 0:
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

    Vus_N = 0.0 if legs_eff <= 0 else (Asv * f_syv * d_v_safe / s_safe) * cot(theta_v_rad)
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


def compute_shear_zones(
    *,
    L_mm: float,
    d_mm: float,
    results: ShearResults,
    inp: ShearInputs,
    is_cantilever: bool,
    lig_d_mm: float,
    legs: int,
    spacing_increment_mm: float = 10.0,
) -> dict | None:
    """
    3-zone constructible stirrup spacing layout (support / shear span / midspan).

    Always returns a layout dict when L and d_v are valid (including shear FAIL and
    zero / undefined stirrups — uses a notional bar basis for spacing display only).

    Uses V_eq, V_uc, θ_v, d_v, f_syv from the sectional shear model (unchanged).
    """
    design_governing = str(get_param("actions_mode", "manual") or "manual").strip().lower() == "design"
    L = float(L_mm)
    if L <= 1.0:
        raise ValueError("Shear design requires valid geometry (L and d_v) for detailing")
    L_m = L / 1000.0
    n = 51
    x = np.linspace(0.0, L_m, n)

    if design_governing:
        shear_x_raw = np.asarray(get_param("shear_x") or [], dtype=float)
        shear_V_raw = np.asarray(get_param("shear_V") or [], dtype=float)
        if shear_x_raw.size > 0 and shear_V_raw.size > 0 and shear_x_raw.size == shear_V_raw.size:
            shear_x = x
            shear_V = np.interp(x, shear_x_raw, shear_V_raw)
        else:
            raise ValueError("Design mode requires SFD V(x)")
    else:
        V_star = float(get_param("uls_Vstar") or 0.0)
        shear_x = x
        # Manual mode assumes a simply supported UDL shear diagram:
        # peak shear at supports, reducing linearly to zero at midspan.
        shear_V = V_star * (2.0 * np.abs(x - L_m / 2.0) / max(L_m, 1e-9))
        shear_V = np.maximum(shear_V, 0.0)

    from shear_zone_spacing import asv_min_over_s_mm, code_s_max_mm, practical_s_min_mm

    d_v = float(results.d_v)
    d_eff = float(d_mm)
    b_v = float(results.b_v)
    fc = float(inp.fc)
    Asv = float(results.Asv)
    f_syv = float(results.f_syv)
    V_eq = float(results.V_eq)
    Vuc = float(results.Vuc_kN)
    theta_v_rad = float(results.theta_v_rad)

    if d_v <= 1.0:
        raise ValueError("Shear design requires valid geometry (L and d_v) for detailing")

    cot_t = cot(theta_v_rad)
    if cot_t <= 1e-12:
        cot_t = 1.0

    asv_min = asv_min_over_s_mm(fc, b_v, f_syv)

    legs_i_raw = int(legs) if abs(float(legs) - round(float(legs))) < 0.01 else int(round(float(legs)))
    use_notional = bool(legs_i_raw <= 0 or Asv <= 1e-6)
    if use_notional:
        lig_disp = max(float(lig_d_mm), 10.0)
        legs_disp = 2
        asv_for_spacing = legs_disp * math.pi * lig_disp**2 / 4.0
    else:
        lig_disp = max(float(lig_d_mm), 1.0)
        legs_disp = max(legs_i_raw, 1)
        asv_for_spacing = float(Asv)

    s_max = code_s_max_mm(d_eff)
    s_min_prac = practical_s_min_mm(lig_disp)
    inc = max(float(spacing_increment_mm), 1.0)

    if len(shear_x) != len(shear_V) or len(shear_x) < 2:
        raise ValueError(
            "Shear V(x) is required for zoned shear design. Run SFD/BMD or enable synthetic distribution."
        )
    shear_x = np.asarray(shear_x, dtype=float)
    shear_V = np.abs(np.asarray(shear_V, dtype=float))
    if not np.all(np.isfinite(shear_x)) or not np.all(np.isfinite(shear_V)):
        raise ValueError("Shear distribution V(x) contains non-finite values")

    _mid_idx = int(len(shear_V) // 2) if shear_V.size else 0
    V_mid_kN = float(shear_V[_mid_idx]) if shear_V.size else 0.0
    shear_mid_spacing_calc_mm, shear_mid_spacing_mode = compute_midspan_spacing_result(
        V_mid_kN=V_mid_kN,
        phi=float(inp.phi),
        Vuc_kN=float(Vuc),
        fy_mpa=float(f_syv),
        dv_mm=float(d_v),
        Asv_mm2=float(asv_for_spacing),
        D_mm=float(d_eff),
        s_min_mm=float(s_min_prac),
        cot_theta_v=float(cot_t),
        increment_mm=float(inc),
    )

    req_asv_s = np.maximum(
        required_asv_per_s(shear_V, inp.phi, Vuc, f_syv, d_v, cot_theta_v=cot_t),
        asv_min,
    )
    asv_over_s_req = float(np.max(req_asv_s)) if req_asv_s.size else float(asv_min)
    # region agent log
    _dbg_log(
        "envelope formula snapshot",
        {
            "phi": float(inp.phi),
            "Vuc_kN": float(Vuc),
            "f_syv": float(f_syv),
            "d_v": float(d_v),
            "theta_v_deg": float(results.theta_v_deg),
            "cot_theta_v": float(cot_t),
            "req_asv_s_support": float(req_asv_s[0]) if req_asv_s.size else None,
            "req_asv_s_mid": float(req_asv_s[len(req_asv_s) // 2]) if req_asv_s.size else None,
            "prov_asv_s_at_input": float(asv_for_spacing / max(float(inp.s_lig), 1e-9)),
        },
        run_id="pre-fix",
        hypothesis_id="FORM_B",
    )
    # endregion
    spacing_profile = np.array(
        [
            spacing_from_demand(
                Vi_kN=float(v_i),
                phi=float(inp.phi),
                Vuc_kN=float(Vuc),
                fy_mpa=float(f_syv),
                dv_mm=float(d_v),
                Asv_mm2=float(asv_for_spacing),
                D_mm=float(d_eff),
                s_min_mm=float(s_min_prac),
                cot_theta_v=float(cot_t),
                increment_mm=float(inc),
            )
            for v_i in shear_V
        ],
        dtype=float,
    )
    # region agent log
    _dbg_log(
        "spacing profile after demand+limits",
        {
            "profile_min": float(np.min(spacing_profile)) if spacing_profile.size else None,
            "profile_p10": float(np.percentile(spacing_profile, 10.0)) if spacing_profile.size else None,
            "profile_p50": float(np.percentile(spacing_profile, 50.0)) if spacing_profile.size else None,
            "profile_p90": float(np.percentile(spacing_profile, 90.0)) if spacing_profile.size else None,
            "profile_max": float(np.max(spacing_profile)) if spacing_profile.size else None,
            "v_max": float(np.max(shear_V)) if shear_V.size else None,
            "phi_vuc": float(inp.phi) * float(Vuc),
        },
        run_id="pre-fix",
        hypothesis_id="A",
    )
    # endregion

    z1_end = min(1.5 * d_v, L)
    z2_end = min(0.5 * L, L)
    z1_lo, z1_hi = 0.0, z1_end
    z2_lo, z2_hi = z1_hi, max(z1_hi, z2_end)
    z3_lo, z3_hi = z2_hi, L

    warnings: list[str] = []
    if use_notional:
        warnings.append(
            f"No stirrups defined (or $A_{{sv}}\\approx 0$); zone spacings use a notional "
            f"**N{int(round(lig_disp))}** ({legs_disp}-leg) basis for layout only."
        )

    # Auto-correction: tighten spacing until compliant OR all locations reach minimum spacing.
    prov_asv_s = asv_for_spacing / np.maximum(spacing_profile, 1e-9)
    while True:
        util0 = np.where(req_asv_s > 1e-12, prov_asv_s / req_asv_s, 1e9)
        min_util0 = float(np.min(util0)) if util0.size else float("inf")
        if min_util0 >= 1.0:
            break
        at_min_mask = spacing_profile <= s_min_prac + 1e-9
        fail_mask = (req_asv_s > 1e-12) & (prov_asv_s + 1e-9 < req_asv_s)
        if np.all(~fail_mask | at_min_mask):
            break
        spacing_profile[fail_mask & ~at_min_mask] = np.maximum(
            s_min_prac,
            np.floor((spacing_profile[fail_mask & ~at_min_mask] * 0.9) / inc + 1e-9) * inc,
        )
        spacing_profile = np.minimum(spacing_profile, s_max)
        prov_asv_s = asv_for_spacing / np.maximum(spacing_profile, 1e-9)
    # Practical detailing output: round down to 5 mm increments and re-apply limits.
    spacing_profile = np.clip(
        np.floor(spacing_profile / 5.0 + 1e-9) * 5.0,
        s_min_prac,
        s_max,
    )
    # --- Determine governing behaviour ---
    s_max = min(0.75 * float(d_eff), 500.0)
    profile_min = float(np.min(spacing_profile)) if spacing_profile.size else float(s_max)
    profile_max = float(np.max(spacing_profile)) if spacing_profile.size else float(s_max)
    is_max_governed = abs(profile_min - s_max) < 1e-3 and abs(profile_max - s_max) < 1e-3
    is_varying = (profile_max - profile_min) > 5.0
    _dbg_log(
        "spacing governing mode",
        {
            "is_max_governed": is_max_governed,
            "is_varying": is_varying,
            "s_max": s_max,
            "profile_min": profile_min,
            "profile_max": profile_max,
        },
        run_id="fix",
        hypothesis_id="GOV",
    )

    s_raw_tight = asv_for_spacing / max(asv_over_s_req, 1e-12)
    if s_raw_tight < s_min_prac - 1e-6:
        warnings.append(
            "Required spacing too tight — increase bar size or number of legs."
        )

    shear_x_mm = shear_x * 1000.0
    x_positions_mm = shear_x_mm
    end_limit_mm = min(1.5 * float(d_mm), 0.5 * float(L))
    if is_cantilever:
        end_mask = x_positions_mm <= end_limit_mm + 1e-9
        mid_mask = x_positions_mm > end_limit_mm + 1e-9
    else:
        end_mask = (x_positions_mm <= end_limit_mm + 1e-9) | (
            x_positions_mm >= (float(L) - end_limit_mm - 1e-9)
        )
        mid_mask = ~end_mask
    s_end = float(np.min(spacing_profile[end_mask])) if np.any(end_mask) else float(np.min(spacing_profile))
    s_mid = float(np.min(spacing_profile[mid_mask])) if np.any(mid_mask) else float(s_end)
    # region agent log
    _dbg_log(
        "two-zone spacing computed",
        {
            "s_end": float(s_end),
            "s_mid": float(s_mid),
            "shared_s_lig_at_compute": st.session_state.get("s_lig"),
            "spacing_profile_min": float(np.min(spacing_profile)) if spacing_profile.size else None,
            "spacing_profile_max": float(np.max(spacing_profile)) if spacing_profile.size else None,
        },
        run_id="pre-fix",
        hypothesis_id="ALIGN_A",
    )
    # endregion

    _FILL_RED = "rgba(255,0,0,0.15)"
    _FILL_ORANGE = "rgba(255,165,0,0.15)"
    if is_cantilever:
        strip_segments = [
            {"zone": "support", "x0_mm": 0.0, "x1_mm": end_limit_mm, "spacing_mm": float(s_end), "color": "rgba(220, 75, 75, 0.88)"},
            {"zone": "mid", "x0_mm": end_limit_mm, "x1_mm": float(L), "spacing_mm": float(s_mid), "color": "rgba(255, 155, 60, 0.9)"},
        ]
    else:
        strip_segments = [
            {"zone": "end", "x0_mm": 0.0, "x1_mm": end_limit_mm, "spacing_mm": float(s_end), "color": "rgba(220, 75, 75, 0.88)"},
            {"zone": "mid", "x0_mm": end_limit_mm, "x1_mm": max(end_limit_mm, float(L) - end_limit_mm), "spacing_mm": float(s_mid), "color": "rgba(255, 155, 60, 0.9)"},
            {"zone": "end", "x0_mm": max(end_limit_mm, float(L) - end_limit_mm), "x1_mm": float(L), "spacing_mm": float(s_end), "color": "rgba(220, 75, 75, 0.88)"},
        ]
    strip_segments = [seg for seg in strip_segments if float(seg["x1_mm"]) > float(seg["x0_mm"]) + 1e-9]
    zones_m = [
        {
            "start": float(seg["x0_mm"]) / 1000.0,
            "end": float(seg["x1_mm"]) / 1000.0,
            "spacing": float(seg["spacing_mm"]) / 1000.0,
            "label": (
                "Support zone"
                if str(seg["zone"]) == "support"
                else "End zone" if str(seg["zone"]) == "end" else "Mid span"
            ),
            "fillcolor": _FILL_RED if str(seg["zone"]) in {"support", "end"} else _FILL_ORANGE,
        }
        for seg in strip_segments
    ]

    def _spacing_at_x_mm(x_mm: float) -> float:
        for seg in strip_segments:
            if float(seg["x0_mm"]) - 1e-9 <= x_mm <= float(seg["x1_mm"]) + 1e-9:
                return float(seg["spacing_mm"])
        return float(s_end)

    prov_asv_s = np.array([asv_for_spacing / max(_spacing_at_x_mm(xm), 1e-9) for xm in shear_x_mm], dtype=float)
    util = np.where(req_asv_s > 1e-12, prov_asv_s / req_asv_s, 1e9)
    asv_over_s_provided = float(np.min(prov_asv_s)) if prov_asv_s.size else 0.0
    # region agent log
    _dbg_log(
        "final segment spacing before summary",
        {
            "segment_count": len(strip_segments),
            "segments": [
                {
                    "zone": str(seg.get("zone")),
                    "x0_mm": float(seg.get("x0_mm", 0.0) or 0.0),
                    "x1_mm": float(seg.get("x1_mm", 0.0) or 0.0),
                    "spacing_mm": float(seg.get("spacing_mm", 0.0) or 0.0),
                }
                for seg in strip_segments
            ],
            "min_util": float(np.min(util)) if util.size else None,
        },
        run_id="pre-fix",
        hypothesis_id="D",
    )
    # endregion

    min_index = int(np.argmin(util)) if util.size else 0
    min_util = float(util[min_index]) if util.size else float("inf")
    x_crit = float(shear_x[min_index]) if shear_x.size else 0.0
    envelope_status = "PASS" if min_util >= 1.0 else "FAIL"
    if envelope_status == "FAIL":
        warnings.append("Envelope non-compliance detected: provided A_sv/s is below required at one or more locations.")

    req_end = float(np.max(req_asv_s[end_mask])) if np.any(end_mask) else float(asv_min)
    req_mid = float(np.max(req_asv_s[mid_mask])) if np.any(mid_mask) else float(req_end)

    dia_i = int(round(lig_disp))
    bar_only = f"N{dia_i}"
    bar_label_legs = f"{bar_only} ({legs_disp}-leg)"

    if is_cantilever:
        summary_lines = [
            f"Support zone (0–1.5$d$): {bar_label_legs} @ {s_end:.0f} mm",
            f"Mid span: {bar_only} @ {s_mid:.0f} mm",
        ]
    else:
        summary_lines = [
            f"End zone (0–1.5$d$): {bar_label_legs} @ {s_end:.0f} mm",
            f"Mid span: {bar_only} @ {s_mid:.0f} mm",
            f"End zone (mirror): {bar_only} @ {s_end:.0f} mm",
        ]

    summary_lines.append(f"Envelope check: {envelope_status} (worst {min_util:.2f} @ x={x_crit:.2f} m)")
    payload = {
        "beam_length_mm": L,
        "d_mm": d_eff,
        "d_v_mm": d_v,
        "is_cantilever": bool(is_cantilever),
        "asv_over_s_req": float(asv_over_s_req),
        "asv_over_s_min": float(asv_min),
        "asv_over_s_provided": float(asv_over_s_provided),
        "governing_mode": "SMAX" if is_max_governed else "DEMAND",
        "v_source_mode": "design" if design_governing else "manual",
        "s_max_code_mm": float(s_max),
        "s_max_mm": float(s_max),
        "s_min_practical_mm": float(s_min_prac),
        "spacing_increment_mm": float(inc),
        "lig_d_mm": float(lig_disp),
        "legs": int(legs_disp),
        "legs_input": int(max(legs_i_raw, 0)),
        "spacing_uses_notional_asv": bool(use_notional),
        "bar_label": bar_label_legs,
        "bar_label_short": bar_only,
        "zone_1": {"range": (0.0, end_limit_mm), "spacing": float(s_end), "asv_over_s_demand": float(max(req_end, asv_min))},
        "zone_2": {"range": (end_limit_mm, max(end_limit_mm, float(L) - end_limit_mm)), "spacing": float(s_mid), "asv_over_s_demand": float(max(req_mid, asv_min))},
        "zone_3": (
            None
            if is_cantilever
            else {"range": (max(end_limit_mm, float(L) - end_limit_mm), float(L)), "spacing": float(s_end), "asv_over_s_demand": float(max(req_end, asv_min))}
        ),
        "shear_x": [float(v) for v in shear_x.tolist()],
        "shear_V": [float(v) for v in shear_V.tolist()],
        "V_max": float(np.max(shear_V)) if shear_V.size else 0.0,
        "req_asv_s": [float(v) for v in req_asv_s.tolist()],
        "prov_asv_s": [float(v) for v in prov_asv_s.tolist()],
        "shear_util_min": float(min_util),
        "shear_util_x": float(x_crit),
        "shear_envelope_status": envelope_status,
        "shear_spacing_end_mm": float(s_end),
        "shear_spacing_mid_mm": float(s_mid),
        "shear_spacing_governing": "max" if is_max_governed else "demand",
        "shear_spacing_profile_min": float(profile_min),
        "shear_spacing_profile_max": float(profile_max),
        "shear_s_end": float(s_end),
        "shear_s_mid": float(s_mid),
        "shear_mid_spacing_calc_mm": float(shear_mid_spacing_calc_mm),
        "shear_mid_spacing_mode": str(shear_mid_spacing_mode),
        "V_mid_kN": float(V_mid_kN),
        "strip_segments_mm": strip_segments,
        "zones": zones_m,
        "summary_lines": summary_lines,
        "warnings": list(dict.fromkeys(warnings)),
    }
    if envelope_status != "PASS":
        spacing_at_crit = float(_spacing_at_x_mm(x_crit * 1000.0))
        req_crit = float(req_asv_s[min_index]) if req_asv_s.size else 0.0
        prov_crit = float(prov_asv_s[min_index]) if prov_asv_s.size else 0.0
        suggestions: list[str] = []
        if spacing_at_crit <= s_min_prac + 1e-9:
            suggestions.append("Increase number of ligature legs or bar size")
        else:
            suggestions.append("Reduce spacing near critical region")
        raise ShearLayoutError(
            "Shear design FAILED.\n"
            f"Min utilisation: {min_util:.2f} at x={x_crit:.2f} m\n"
            f"Spacing at critical location: {spacing_at_crit:.0f} mm (minimum practical {s_min_prac:.0f} mm)\n"
            f"Required A_sv/s at critical location: {req_crit:.3f} mm²/mm\n"
            f"Provided A_sv/s at critical location: {prov_crit:.3f} mm²/mm\n"
            f"Suggested fix: {', '.join(suggestions)}",
            payload=payload,
        )

    return payload


def build_shear_zone_layout_strip_figure(
    payload: dict,
    *,
    beam_depth_m: float = 0.18,
    title: str | None = None,
    show_stirrup_marks: bool = True,
    max_stirrup_marks: int = 400,
    reference_width_px: float = 640.0,
    min_tick_spacing_px: float = 6.0,
):
    """
    Plotly horizontal strip for Check 10 (3-zone layout).

    Draws zone colour bands, vertical stirrup ticks at each zone spacing (first tick
    offset by s/2 from the zone start), optional thinning when ticks would crowd in
    pixel space, and @s labels centred under each zone.
    """
    import plotly.graph_objects as go

    segs = list(payload.get("strip_segments_mm") or [])
    L_mm = float(payload.get("beam_length_mm") or 0.0)
    support_type = str(payload.get("support_type") or "")
    is_cantilever = bool(payload.get("is_cantilever", False))
    support_positions_mm = [float(v) for v in (payload.get("support_positions_mm") or [])]
    support_types = [str(v) for v in (payload.get("support_types") or [])]
    # region agent log
    _dbg_log(
        "shear strip figure payload",
        {
            "payload_keys": sorted(str(k) for k in payload.keys()),
            "segment_count": len(segs),
            "beam_length_mm": L_mm,
            "support_type": support_type,
            "is_cantilever": is_cantilever,
            "support_positions_mm": support_positions_mm,
            "support_types": support_types,
        },
        run_id="pre-fix",
        hypothesis_id="H18_H19",
    )
    # endregion
    if L_mm <= 0.0 and segs:
        L_mm = max(float(s.get("x1_mm", 0.0) or 0.0) for s in segs)
    L_m = max(L_mm / 1000.0, 1e-9)

    y0, y1 = 0.0, float(beam_depth_m)
    # Stirrup extent within the beam strip (slight inset from top/bottom)
    inset = 0.06 * (y1 - y0)
    y_bot_reo = y0 + inset
    y_top_reo = y1 - inset

    zone_stirrup_line = {
        "1": "rgba(95, 42, 42, 0.78)",
        "2": "rgba(105, 72, 38, 0.76)",
        "3": "rgba(42, 98, 58, 0.76)",
    }

    fig = go.Figure()

    if not segs:
        fig.add_annotation(
            x=0.5 * L_m,
            y=0.5 * y1,
            text="No shear link spacing set",
            showarrow=False,
            font=dict(size=12, color="rgba(60,60,60,0.9)"),
        )
        fig.update_xaxes(title_text="Distance along member (m)", range=[0.0, max(L_m, 1e-6)])
        fig.update_yaxes(visible=False, range=[-0.05 * beam_depth_m, y1 + 0.2 * beam_depth_m])
        fig.update_layout(
            title=title or "Shear reinforcement layout (3 zones)",
            margin=dict(l=40, r=20, t=50, b=48),
            height=140,
            showlegend=False,
        )
        return fig

    scale_px_per_m = float(reference_width_px) / L_m
    stirrup_count = 0

    for seg in segs:
        x0 = float(seg.get("x0_mm", 0.0) or 0.0) / 1000.0
        x1 = float(seg.get("x1_mm", 0.0) or 0.0) / 1000.0
        sm = float(seg.get("spacing_mm", 0.0) or 0.0)
        color = str(seg.get("color") or "rgba(120,120,120,0.5)")
        zid = str(seg.get("zone", "1") or "1")
        line_col = zone_stirrup_line.get(zid, "rgba(51, 51, 51, 0.72)")

        fig.add_shape(
            type="rect",
            x0=x0,
            x1=x1,
            y0=y0,
            y1=y1,
            fillcolor=color,
            line=dict(width=0),
            layer="below",
        )

        sm_m = max(sm / 1000.0, 1e-9)
        spacing_px = sm_m * scale_px_per_m
        step = 2 if spacing_px < float(min_tick_spacing_px) else 1

        xm = 0.5 * (x0 + x1)
        fig.add_annotation(
            x=xm,
            y=y1 + 0.05 * beam_depth_m,
            text=f"@{sm:.0f}",
            showarrow=False,
            font=dict(size=10, color="rgba(45,45,45,0.92)"),
        )

        if show_stirrup_marks and sm_m > 0.0 and x1 > x0 + 1e-12:
            x_first = x0 + 0.5 * sm_m
            xi = x_first
            idx = 0
            while xi < x1 - 1e-9 and stirrup_count < max_stirrup_marks:
                if idx % step == 0:
                    fig.add_shape(
                        type="line",
                        x0=xi,
                        x1=xi,
                        y0=y_bot_reo,
                        y1=y_top_reo,
                        line=dict(color=line_col, width=1),
                        layer="above",
                    )
                    stirrup_count += 1
                xi += sm_m
                idx += 1

    fig.add_trace(
        go.Scatter(
            x=[0.0, L_m],
            y=[y1 * 0.5, y1 * 0.5],
            mode="lines",
            line=dict(color="rgba(40,40,40,0.85)", width=2),
            hoverinfo="skip",
            showlegend=False,
        )
    )
    rendered_supports = []
    if support_positions_mm and support_types and len(support_positions_mm) == len(support_types):
        support_symbols = {
            "fixed": "⏊",
            "pinned": "▲",
            "roller": "○",
        }
        support_y = y0 - 0.07 * beam_depth_m
        for sx_mm, stype in zip(support_positions_mm, support_types):
            sx_m = float(sx_mm) / 1000.0
            key = str(stype or "").strip().lower()
            symbol = support_symbols.get(key, "▲")
            rendered_supports.append({"x_m": sx_m, "type": stype, "symbol": symbol})
            fig.add_annotation(
                x=sx_m,
                y=support_y,
                text=symbol,
                showarrow=False,
                font=dict(size=14, color="rgba(35,35,35,0.95)"),
            )
    elif is_cantilever:
        rendered_supports.append({"x_m": 0.0, "type": "Fixed", "symbol": "⏊"})
        fig.add_annotation(
            x=0.0,
            y=y0 - 0.07 * beam_depth_m,
            text="⏊",
            showarrow=False,
            font=dict(size=14, color="rgba(35,35,35,0.95)"),
        )
    elif support_type:
        rendered_supports.extend(
            [
                {"x_m": 0.0, "type": "Pinned", "symbol": "▲"},
                {"x_m": L_m, "type": "Roller", "symbol": "○"},
            ]
        )
        fig.add_annotation(
            x=0.0,
            y=y0 - 0.07 * beam_depth_m,
            text="▲",
            showarrow=False,
            font=dict(size=14, color="rgba(35,35,35,0.95)"),
        )
        fig.add_annotation(
            x=L_m,
            y=y0 - 0.07 * beam_depth_m,
            text="○",
            showarrow=False,
            font=dict(size=14, color="rgba(35,35,35,0.95)"),
        )
    # region agent log
    _dbg_log(
        "shear strip figure supports rendered",
        {
            "rendered_supports": rendered_supports,
        },
        run_id="pre-fix",
        hypothesis_id="H19",
    )
    # endregion
    fig.update_xaxes(title_text="Distance along member (m)", range=[0.0, max(L_m, 1e-6)])
    fig.update_yaxes(visible=False, range=[-0.18 * beam_depth_m, y1 + 0.22 * beam_depth_m])
    fig.update_layout(
        title=title or "Shear reinforcement layout (3 zones)",
        margin=dict(l=40, r=20, t=50, b=48),
        height=140,
        showlegend=False,
    )
    return fig


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

    top_rows = get_longitudinal_row_inputs("top")
    bottom_rows = get_longitudinal_row_inputs("bot")
    primary_top_row = next((row for row in top_rows if row.get("active")), None)
    primary_bottom_row = next((row for row in bottom_rows if row.get("active")), None)
    total_top_bars = int(float(get_param("total_top_bars", 0.0) or 0.0))
    total_bottom_bars = int(float(get_param("total_bot_bars", 0.0) or 0.0))
    if total_top_bars <= 0:
        total_top_bars = sum(int(row.get("bars", 0) or 0) for row in top_rows if row.get("active") and row.get("mode") == "Count")
    if total_bottom_bars <= 0:
        total_bottom_bars = sum(int(row.get("bars", 0) or 0) for row in bottom_rows if row.get("active") and row.get("mode") == "Count")

    reo = {
        "cover_top": cover_top,
        "cover_bot": cover_bot,
        "cover_side": cover_side,
        "top_rows": top_rows,
        "bottom_rows": bottom_rows,
        "rowgap_bot": float(get_param("rowgap_bot", 60.0)),
        "rowgap_top": float(get_param("rowgap_top", 60.0)),
        # Backwards-compatible totals
        "nb_top": total_top_bars,
        "db_top": float((primary_top_row or {}).get("dia", get_param("db_top", 16.0)) or 16.0),
        "nb_bot": total_bottom_bars,
        "db_bot": float((primary_bottom_row or {}).get("dia", get_param("db_bot", 20.0)) or 20.0),
        "min_clear_spacing": s_min,
        "lig_d": float(get_param("lig_d", 0.0)),
        "lig_legs": int(get_param("lig_legs", 0)),
        "top_flange_reo_enabled": bool(get_param("top_flange_reo_enabled", False)),
        "bot_flange_reo_enabled": bool(get_param("bot_flange_reo_enabled", False)),
        "top_flange_mirror_lr": bool(get_param("top_flange_mirror_lr", True)),
        "bot_flange_mirror_lr": bool(get_param("bot_flange_mirror_lr", True)),
        "top_flange_left_count": int(get_param("top_flange_left_count", 0) or 0),
        "top_flange_left_dia": float(get_param("top_flange_left_dia", 16.0) or 16.0),
        "top_flange_left_rows": int(get_param("top_flange_left_rows", 1) or 1),
        "top_flange_left_row_spacing": float(get_param("top_flange_left_row_spacing", 60.0) or 60.0),
        "top_flange_right_count": int(get_param("top_flange_right_count", 0) or 0),
        "top_flange_right_dia": float(get_param("top_flange_right_dia", 16.0) or 16.0),
        "top_flange_right_rows": int(get_param("top_flange_right_rows", 1) or 1),
        "top_flange_right_row_spacing": float(get_param("top_flange_right_row_spacing", 60.0) or 60.0),
        "bot_flange_left_count": int(get_param("bot_flange_left_count", 0) or 0),
        "bot_flange_left_dia": float(get_param("bot_flange_left_dia", 20.0) or 20.0),
        "bot_flange_left_rows": int(get_param("bot_flange_left_rows", 1) or 1),
        "bot_flange_left_row_spacing": float(get_param("bot_flange_left_row_spacing", 60.0) or 60.0),
        "bot_flange_right_count": int(get_param("bot_flange_right_count", 0) or 0),
        "bot_flange_right_dia": float(get_param("bot_flange_right_dia", 20.0) or 20.0),
        "bot_flange_right_rows": int(get_param("bot_flange_right_rows", 1) or 1),
        "bot_flange_right_row_spacing": float(get_param("bot_flange_right_row_spacing", 60.0) or 60.0),
        "top_flange_transverse_enabled": bool(get_param("top_flange_transverse_enabled", False)),
        "bot_flange_transverse_enabled": bool(get_param("bot_flange_transverse_enabled", False)),
        "top_flange_transverse_dia": float(get_param("top_flange_transverse_dia", 10.0) or 10.0),
        "bot_flange_transverse_dia": float(get_param("bot_flange_transverse_dia", 10.0) or 10.0),
        "top_flange_transverse_spacing": float(get_param("top_flange_transverse_spacing", 200.0) or 200.0),
        "bot_flange_transverse_spacing": float(get_param("bot_flange_transverse_spacing", 200.0) or 200.0),
        "top_flange_transverse_legs": int(get_param("top_flange_transverse_legs", 2) or 2),
        "bot_flange_transverse_legs": int(get_param("bot_flange_transverse_legs", 2) or 2),
    }

    shear_longitudinal_tension_increment = 0.0
    shear_Ast_required_tension_envelope = float(A_st or 0.0)
    shear_Ast_available_anchored_active = float(A_st or 0.0)
    shear_Ast_available_anchored_web = float(A_st or 0.0)
    shear_Ast_available_anchored_flange = 0.0
    shear_flange_bars_participating = False
    shear_longitudinal_detailing_ok = True
    active_tension_face = "bottom"
    active_tension_width_mm = float(b)
    active_tension_warning = ""
    flange_transverse_detailing_note = ""
    flange_transverse_reo_present_top = bool(get_param("top_flange_transverse_enabled", False))
    flange_transverse_reo_present_bottom = bool(get_param("bot_flange_transverse_enabled", False))
    flange_transverse_spacing_top = float(get_param("top_flange_transverse_spacing", 0.0) or 0.0)
    flange_transverse_spacing_bottom = float(get_param("bot_flange_transverse_spacing", 0.0) or 0.0)

    try:
        from section_layout import compute_section_layout
        from section_props.reo_layout import (
            resolve_longitudinal_bars_from_layout,
            resolve_active_tension_reinforcement,
            resolve_crack_tension_width,
        )
        actions = resolve_design_actions()
        moment_sign = "negative" if float(actions.get("Mu_signed", 0.0) or 0.0) < 0.0 else "positive"
        layout = compute_section_layout()
        dims_resolved = dict(layout.get("dims", {}) or {})
        shape_resolved = str(layout.get("shape_name", sec_shape))
        bars = list(st.session_state.get("resolved_longitudinal_bars", []) or [])
        if not bars:
            bars = resolve_longitudinal_bars_from_layout(
                shape_name=shape_resolved,
                dims=dims_resolved,
                reo_layout=dict(layout.get("reo_layout", {}) or {}),
            )
        active = resolve_active_tension_reinforcement(
            dims_resolved,
            bars,
            moment_sign,
        )
        crack_w = resolve_crack_tension_width(
            sec_shape,
            dims_resolved,
            moment_sign,
            active.get("active_bars", []),
        )
        active_tension_face = str(active.get("tension_face", "bottom"))
        A_st = float(active.get("Ast_active_mm2", A_st) or A_st)
        active_tension_width_mm = float(crack_w.get("crack_tension_width_mm", b) or b)
        shear_Ast_available_anchored_active = sum(
            float(bar.get("area_mm2", 0.0) or 0.0)
            for bar in active.get("active_bars", [])
            if bool(bar.get("anchored", True))
        )
        shear_Ast_available_anchored_web = sum(
            float(bar.get("area_mm2", 0.0) or 0.0)
            for bar in active.get("active_web_bars", [])
            if bool(bar.get("anchored", True))
        )
        shear_Ast_available_anchored_flange = sum(
            float(bar.get("area_mm2", 0.0) or 0.0)
            for bar in active.get("active_flange_bars", [])
            if bool(bar.get("anchored", True))
        )
        shear_flange_bars_participating = shear_Ast_available_anchored_flange > 0.0
        shear_longitudinal_tension_increment = abs(float(V_star or 0.0)) * 1000.0
        shear_Ast_required_increment = shear_longitudinal_tension_increment / max(float(fsy or 0.0), 1.0)
        shear_Ast_required_tension_envelope = max(float(A_st or 0.0), float(shear_Ast_required_increment))
        shear_longitudinal_detailing_ok = shear_Ast_available_anchored_active + 1e-9 >= shear_Ast_required_tension_envelope
        # Flange transverse reinforcement is detailing/distribution only and does not
        # contribute to primary web-based shear capacity (Vu).
        wide_flange = float(dims_resolved.get("bf", 0.0) or 0.0) > 1.6 * max(float(dims_resolved.get("bw", dims_resolved.get("tw", 0.0)) or 0.0), 1.0)
        top_tension = active_tension_face == "top"
        bottom_tension = active_tension_face == "bottom"
        has_flange_longitudinal_active = bool(shear_flange_bars_participating)
        has_transverse_on_active_face = (
            (top_tension and flange_transverse_reo_present_top)
            or (bottom_tension and flange_transverse_reo_present_bottom)
        )
        if sec_shape in ("T", "I") and wide_flange and has_flange_longitudinal_active and not has_transverse_on_active_face:
            flange_transverse_detailing_note = (
                "Wide flange tension region has distributed longitudinal bars but no transverse flange "
                "detailing reinforcement is defined. Consider transverse flange bars/ties for crack "
                "distribution, cage stability, and local detailing."
            )
        if sec_shape in ("T", "I") and active_tension_face == "top" and not shear_flange_bars_participating:
            active_tension_warning = (
                "Top tension reinforcement is concentrated in the web. For wide flanges under hogging, "
                "distributed flange bars may be required for realistic crack control and detailing."
            )
    except Exception:
        pass

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
    
    # Run calculation (session inputs — governs Checks 5–9 and published φVu, etc.)
    results = run_shear_calc(inp)
    # region agent log
    _dbg_log(
        "sectional shear snapshot",
        {
            "phi_Vu": float(results.phi_Vu),
            "V_eq": float(results.V_eq),
            "Vuc_kN": float(results.Vuc_kN),
            "Vus_kN": float(results.Vus_kN),
            "Asv": float(results.Asv),
            "d_v": float(results.d_v),
            "theta_v_deg": float(results.theta_v_deg),
            "s_lig": float(inp.s_lig),
        },
        run_id="pre-fix",
        hypothesis_id="FORM_A",
    )
    # endregion

    L_mm = float(get_param("L", 0.0))
    if not L_mm or L_mm <= 0:
        L_mm = float(get_param("span_L_m", 3.0)) * 1000.0

    _legs_i = int(legs) if abs(legs - round(legs)) < 0.01 else int(round(legs))
    _legs_i = max(_legs_i, 0)

    shear_ok_sectional = bool(float(results.phi_Vu) + 1e-9 >= float(results.V_eq))
    auto_mode = bool(get_param("shear_auto_design", False))
    auto_design_active = bool(get_param("auto_design_active", False))
    # region agent log
    _dbg_log(
        "auto-design gate state",
        {
            "auto_mode": bool(auto_mode),
            "auto_design_active": bool(auto_design_active),
            "shear_ok_sectional": bool(shear_ok_sectional),
            "shared_s_lig": float(s_lig),
            "shared_lig_legs": float(legs),
            "shared_lig_d": float(lig_d),
            "widget_inputs_s_lig": st.session_state.get("inputs_s_lig"),
            "widget_shear_s_lig": st.session_state.get("shear_s_lig"),
        },
        run_id="pre-fix",
        hypothesis_id="A",
    )
    # endregion

    zone_results = results
    zone_inp = inp
    zone_lig_d = float(lig_d)
    zone_legs = max(_legs_i, 0)
    shear_design_status: str | None = None
    sel_lig_d_mm: float | None = None
    sel_legs_f: float | None = None
    extra_zone_warnings: list[str] = []

    if shear_ok_sectional:
        shear_design_status = "PASS"
    else:
        shear_design_status = "FAIL"

    if _legs_i < 2 and shear_design_status != "AUTO-DESIGNED":
        shear_design_status = "no_reo"

    shear_zone_payload: dict | None = None
    shear_design_status_out: str | None = None
    try:
        from deflection import get_deflection_diagram_support_condition

        _sup_lbl = str(
            get_deflection_diagram_support_condition(st.session_state).get("support_type", "") or ""
        )
        _is_cantilever = "cantilever" in _sup_lbl.lower()
        # region agent log
        _dbg_log(
            "about to call compute_shear_zones",
            {
                "L_mm": float(L_mm),
                "d_mm": float(d),
                "is_cantilever": bool(_is_cantilever),
                "zone_lig_d": float(zone_lig_d),
                "zone_legs": int(max(int(zone_legs), 0)),
                "shear_design_status_pre": shear_design_status,
            },
            run_id="pre-fix",
            hypothesis_id="N",
        )
        # endregion
        shear_zone_payload = compute_shear_zones(
            L_mm=L_mm,
            d_mm=float(d),
            results=zone_results,
            inp=zone_inp,
            is_cantilever=_is_cantilever,
            lig_d_mm=float(zone_lig_d),
            legs=max(int(zone_legs), 0),
        )
        # region agent log
        _dbg_log(
            "compute_shear_zones returned payload",
            {
                "payload_is_dict": isinstance(shear_zone_payload, dict),
                "segment_count": len(list((shear_zone_payload or {}).get("strip_segments_mm") or [])),
                "envelope_status": (shear_zone_payload or {}).get("shear_envelope_status"),
            },
            run_id="pre-fix",
            hypothesis_id="N",
        )
        # endregion
        if shear_zone_payload and extra_zone_warnings:
            _w = list(shear_zone_payload.get("warnings") or [])
            _w.extend(extra_zone_warnings)
            shear_zone_payload = {**shear_zone_payload, "warnings": list(dict.fromkeys(_w))}
        shear_design_status_out = shear_design_status
    except Exception as _zone_exc:
        if "Shear distribution V(x) must be defined" in str(_zone_exc):
            raise ValueError(
                "Shear V(x) is required for zoned shear design. Run SFD/BMD or enable synthetic distribution."
            ) from _zone_exc
        else:
            _failed_payload = getattr(_zone_exc, "payload", None)
            # region agent log
            _dbg_log(
                "compute_shear_zones raised exception",
                {
                    "error": str(_zone_exc),
                    "shear_design_status_pre": shear_design_status,
                    "payload_present": isinstance(_failed_payload, dict),
                },
                run_id="pre-fix",
                hypothesis_id="N",
            )
            # endregion
            _phi_vu_current = float(results.phi_Vu or 0.0)
            _vu_util_current = (float(results.V_eq) / _phi_vu_current) if _phi_vu_current > 0.0 else float("nan")
            _phi_vu_max_current = float(inp.phi) * float(results.Vu_max_kN or 0.0)
            update_results(
                phi_Vu_cap=_phi_vu_current,
                Vu_utilisation=_vu_util_current if not math.isnan(_vu_util_current) else 0.0,
                phi_Vu_max_kN=_phi_vu_max_current,
                shear_zone_results=_failed_payload,
                shear_design_status="INVALID",
                shear_design_error=str(_zone_exc),
                shear_x=(_failed_payload or {}).get("shear_x", []),
                shear_V=(_failed_payload or {}).get("shear_V", []),
                V_max=float((_failed_payload or {}).get("V_max", 0.0) or 0.0),
                req_asv_s=(_failed_payload or {}).get("req_asv_s", []),
                prov_asv_s=(_failed_payload or {}).get("prov_asv_s", []),
                shear_util_min=(_failed_payload or {}).get("shear_util_min", None),
                shear_util_x=(_failed_payload or {}).get("shear_util_x", None),
                shear_envelope_status=(_failed_payload or {}).get("shear_envelope_status", "FAIL"),
                shear_k_v=float(results.k_v or 0.0),
                shear_theta_v_deg=float(results.theta_v_deg or 0.0),
                shear_theta_v_rad=float(results.theta_v_rad or 0.0),
                shear_Vuc_kN=float(results.Vuc_kN or 0.0),
                shear_Vus_kN=float(results.Vus_kN or 0.0),
                shear_Vu_total_kN=float(results.Vu_total_kN or 0.0),
                shear_spacing_end_mm=float((_failed_payload or {}).get("shear_spacing_end_mm", 0.0) or 0.0),
                shear_spacing_mid_mm=float((_failed_payload or {}).get("shear_spacing_mid_mm", 0.0) or 0.0),
                shear_s_end=float((_failed_payload or {}).get("shear_s_end", 0.0) or 0.0),
                shear_s_mid=float((_failed_payload or {}).get("shear_s_mid", 0.0) or 0.0),
                shear_mid_spacing_calc_mm=float((_failed_payload or {}).get("shear_mid_spacing_calc_mm", 0.0) or 0.0),
                shear_mid_spacing_mode=str((_failed_payload or {}).get("shear_mid_spacing_mode") or ""),
                V_mid_kN=float((_failed_payload or {}).get("V_mid_kN", 0.0) or 0.0),
                shear_auto_selected_lig_d_mm=None,
                shear_auto_selected_legs=None,
                shear_M_uls_kNm=list(st.session_state.get("shear_M_uls_kNm") or []),
                shear_M_sls_kNm=list(st.session_state.get("shear_M_sls_kNm") or []),
                moment_x=list(st.session_state.get("moment_x") or st.session_state.get("shear_x") or []),
                moment_values=list(
                    st.session_state.get("moment_values") or st.session_state.get("shear_M_sls_kNm") or []
                ),
                crack_bmd_cache_fingerprint=str(st.session_state.get("crack_bmd_cache_fingerprint") or ""),
                bmd_support_positions_m=list(st.session_state.get("bmd_support_positions_m") or []),
                bmd_support_types=list(st.session_state.get("bmd_support_types") or []),
            )
            # region agent log
            _dbg_log(
                "failure path published canonical shear state",
                {
                    "phi_Vu_cap": _phi_vu_current,
                    "Vu_utilisation": _vu_util_current if not math.isnan(_vu_util_current) else None,
                    "phi_Vu_max_kN": _phi_vu_max_current,
                    "shear_k_v": float(results.k_v or 0.0),
                    "shear_theta_v_deg": float(results.theta_v_deg or 0.0),
                    "shear_Vuc_kN": float(results.Vuc_kN or 0.0),
                    "shear_Vus_kN": float(results.Vus_kN or 0.0),
                },
                run_id="post-fix",
                hypothesis_id="UI_FIX2",
            )
            # endregion
            if "V(x)" in str(_zone_exc):
                raise ValueError("Shear design requires valid V(x) from SFD") from _zone_exc
            raise ValueError(str(_zone_exc)) from _zone_exc

    # Align sectional Vus check with detailed spacing by using the end-zone spacing.
    _s_eff_mm = None
    if isinstance(shear_zone_payload, dict):
        _s_eff_mm = float(shear_zone_payload.get("shear_spacing_end_mm", 0.0) or 0.0)
    # Only adopt layout end-zone spacing for sectional φV_u / session s_lig when "Apply auto spacing" is on.
    if auto_mode and _s_eff_mm is not None and _s_eff_mm > 0.0:
        try:
            results = run_shear_calc(replace(inp, s_lig=float(_s_eff_mm)))
            apply_auto_design_results({"s_lig": float(_s_eff_mm)})
        except Exception as _realign_exc:
            # region agent log
            _dbg_log(
                "run_shear_calc realign failed",
                {"error": str(_realign_exc), "s_eff_mm": float(_s_eff_mm)},
                run_id="pre-fix",
                hypothesis_id="H3",
            )
            # endregion
            pass
    # region agent log
    _dbg_log(
        "spacing alignment after writeback",
        {
            "auto_mode": bool(auto_mode),
            "effective_spacing_mm": float(_s_eff_mm) if _s_eff_mm is not None else None,
            "payload_s_end": float((shear_zone_payload or {}).get("shear_spacing_end_mm", 0.0) or 0.0),
            "payload_s_mid": float((shear_zone_payload or {}).get("shear_spacing_mid_mm", 0.0) or 0.0),
            "inp_s_lig": float(inp.s_lig),
            "shared_s_lig_after": st.session_state.get("s_lig"),
            "widget_inputs_s_lig_after": st.session_state.get("inputs_s_lig"),
            "widget_shear_s_lig_after": st.session_state.get("shear_s_lig"),
        },
        run_id="pre-fix",
        hypothesis_id="ALIGN_B",
    )
    # endregion
    if shear_design_status_out == "AUTO-DESIGNED":
        # region agent log
        _dbg_log(
            "auto-designed spacing candidates",
            {
                "input_s_lig_mm": float(inp.s_lig),
                "effective_layout_spacing_mm": float(_s_eff_mm) if _s_eff_mm is not None else None,
                "shared_s_lig_now": st.session_state.get("s_lig"),
                "widget_inputs_s_lig_now": st.session_state.get("inputs_s_lig"),
                "widget_shear_s_lig_now": st.session_state.get("shear_s_lig"),
            },
            run_id="pre-fix",
            hypothesis_id="L",
        )
        # endregion

    # After zoned layout + optional s_lig realignment, align published status with final sectional φV_u check.
    if (
        shear_design_status_out is not None
        and str(shear_design_status_out).strip().upper() != "INVALID"
        and _legs_i >= 2
        and shear_design_status_out != "no_reo"
    ):
        shear_design_status_out = "PASS" if results.shear_ok else "FAIL"

    _s_used_for_vus = (
        float(_s_eff_mm)
        if auto_mode and _s_eff_mm is not None and _s_eff_mm > 0.0
        else float(inp.s_lig)
    )

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
                f"= ({results.Asv:.1f} · {results.f_syv:.0f} · {results.d_v:.0f} / {_s_used_for_vus:.0f}) · cot{results.theta_v_deg:.1f}°",
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
            tension_face=active_tension_face,
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

    # region agent log
    _payload = shear_zone_payload if isinstance(shear_zone_payload, dict) else {}
    _dbg_log(
        "STAT_SYNC pre update_results",
        {
            "shear_design_status_out": shear_design_status_out,
            "results_shear_ok": bool(getattr(results, "shear_ok", False)),
            "results_web_ok": bool(getattr(results, "web_ok", False)),
            "phi_Vu": float(getattr(results, "phi_Vu", 0.0) or 0.0),
            "V_eq": float(getattr(results, "V_eq", 0.0) or 0.0),
            "V_star_inp": float(getattr(inp, "V_star", 0.0) or 0.0),
            "V_max_payload": float((_payload or {}).get("V_max", 0.0) or 0.0),
            "shear_envelope_status": (_payload or {}).get("shear_envelope_status"),
            "shear_util_min": (_payload or {}).get("shear_util_min"),
            "s_eff_mm": float(_s_eff_mm) if _s_eff_mm is not None else None,
            "cot_theta_v": float(cot(float(getattr(results, "theta_v_rad", 0.0) or 0.0))),
        },
        run_id="verify",
        hypothesis_id="H1",
    )
    # endregion

    def _resample_y_on_new_x(old_x: list[float], old_y: list[float], new_x: list[float]) -> list[float]:
        if len(old_x) < 2 or len(new_x) < 2 or len(old_y) != len(old_x):
            return list(old_y)
        if len(old_x) == len(new_x) and max(abs(old_x[i] - new_x[i]) for i in range(len(old_x))) < 1e-9:
            return list(old_y)
        try:
            return [
                float(v)
                for v in np.interp(
                    np.asarray(new_x, dtype=float),
                    np.asarray(old_x, dtype=float),
                    np.asarray(old_y, dtype=float),
                ).tolist()
            ]
        except Exception:
            return list(old_y)

    _sx_new = [float(v) for v in ((shear_zone_payload or {}).get("shear_x", []) or [])]
    _sx_prev = [float(v) for v in (st.session_state.get("shear_x", []) or [])]
    _m_sls_prev = [float(v) for v in (st.session_state.get("shear_M_sls_kNm") or [])]
    _m_uls_prev = [float(v) for v in (st.session_state.get("shear_M_uls_kNm") or [])]
    _m_sls_resampled = _resample_y_on_new_x(_sx_prev, _m_sls_prev, _sx_new)
    _m_uls_resampled = _resample_y_on_new_x(_sx_prev, _m_uls_prev, _sx_new)

    # Update session state
    update_results(
        phi_Vu_cap=results.phi_Vu,
        Vu_utilisation=shear_util if not math.isnan(shear_util) else 0.0,
        Vu_max_kN=results.Vu_max_kN,
        phi_Vu_max_kN=phi_Vu_max,
        V_eq_kN=results.V_eq,
        Vuc_utilisation=Vuc_util if not math.isnan(Vuc_util) else None,
        shear_longitudinal_tension_increment=float(shear_longitudinal_tension_increment),
        shear_Ast_required_tension_envelope=float(shear_Ast_required_tension_envelope),
        shear_Ast_available_anchored_active=float(shear_Ast_available_anchored_active),
        shear_Ast_available_anchored_web=float(shear_Ast_available_anchored_web),
        shear_Ast_available_anchored_flange=float(shear_Ast_available_anchored_flange),
        shear_flange_bars_participating=bool(shear_flange_bars_participating),
        shear_longitudinal_detailing_ok=bool(shear_longitudinal_detailing_ok),
        active_tension_face=active_tension_face,
        active_tension_Ast_mm2=float(A_st or 0.0),
        active_tension_width_mm=float(active_tension_width_mm),
        active_tension_flange_participating=bool(shear_flange_bars_participating),
        active_tension_warning=active_tension_warning,
        flange_transverse_reo_present_top=bool(flange_transverse_reo_present_top),
        flange_transverse_reo_present_bottom=bool(flange_transverse_reo_present_bottom),
        flange_transverse_spacing_top=float(flange_transverse_spacing_top),
        flange_transverse_spacing_bottom=float(flange_transverse_spacing_bottom),
        flange_transverse_detailing_note=flange_transverse_detailing_note,
        shear_steps=shear_steps,
        shear_report=shear_report,
        shear_zone_results=shear_zone_payload,
        shear_design_error=None,
        shear_x=(shear_zone_payload or {}).get("shear_x", []),
        shear_V=(shear_zone_payload or {}).get("shear_V", []),
        V_max=float((shear_zone_payload or {}).get("V_max", 0.0) or 0.0),
        req_asv_s=(shear_zone_payload or {}).get("req_asv_s", []),
        prov_asv_s=(shear_zone_payload or {}).get("prov_asv_s", []),
        shear_util_min=(shear_zone_payload or {}).get("shear_util_min", None),
        shear_util_x=(shear_zone_payload or {}).get("shear_util_x", None),
        shear_envelope_status=(shear_zone_payload or {}).get("shear_envelope_status", None),
        shear_k_v=float(results.k_v),
        shear_theta_v_deg=float(results.theta_v_deg),
        shear_theta_v_rad=float(results.theta_v_rad),
        shear_Vuc_kN=float(results.Vuc_kN),
        shear_Vus_kN=float(results.Vus_kN),
        shear_Vu_total_kN=float(results.Vu_total_kN),
        shear_spacing_end_mm=float((shear_zone_payload or {}).get("shear_spacing_end_mm", 0.0) or 0.0),
        shear_spacing_mid_mm=float((shear_zone_payload or {}).get("shear_spacing_mid_mm", 0.0) or 0.0),
        shear_spacing_governing=(shear_zone_payload or {}).get("shear_spacing_governing"),
        shear_spacing_profile_min=(shear_zone_payload or {}).get("shear_spacing_profile_min"),
        shear_spacing_profile_max=(shear_zone_payload or {}).get("shear_spacing_profile_max"),
        shear_s_end=float((shear_zone_payload or {}).get("shear_s_end", 0.0) or 0.0),
        shear_s_mid=float((shear_zone_payload or {}).get("shear_s_mid", 0.0) or 0.0),
        shear_mid_spacing_calc_mm=float((shear_zone_payload or {}).get("shear_mid_spacing_calc_mm", 0.0) or 0.0),
        shear_mid_spacing_mode=str((shear_zone_payload or {}).get("shear_mid_spacing_mode") or ""),
        V_mid_kN=float((shear_zone_payload or {}).get("V_mid_kN", 0.0) or 0.0),
        shear_design_status=shear_design_status_out,
        shear_auto_selected_lig_d_mm=sel_lig_d_mm,
        shear_auto_selected_legs=sel_legs_f,
        shear_M_uls_kNm=_m_uls_resampled,
        shear_M_sls_kNm=_m_sls_resampled,
        moment_x=_sx_new,
        moment_values=_m_sls_resampled,
        crack_bmd_cache_fingerprint=str(st.session_state.get("crack_bmd_cache_fingerprint") or ""),
        bmd_support_positions_m=list(st.session_state.get("bmd_support_positions_m") or []),
        bmd_support_types=list(st.session_state.get("bmd_support_types") or []),
    )
    # region agent log
    _dbg_log(
        "results published alignment snapshot",
        {
            "result_s_end": st.session_state.get("shear_spacing_end_mm"),
            "result_s_mid": st.session_state.get("shear_spacing_mid_mm"),
            "result_util": st.session_state.get("shear_util_min"),
            "result_env": st.session_state.get("shear_envelope_status"),
            "shared_s_lig_final": st.session_state.get("s_lig"),
        },
        run_id="pre-fix",
        hypothesis_id="ALIGN_C",
    )
    # endregion

    # region agent log
    _dbg_log(
        "compute exits with reinforcement state",
        {
            "shared_s_lig": st.session_state.get("s_lig"),
            "shared_lig_legs": st.session_state.get("lig_legs"),
            "widget_inputs_s_lig": st.session_state.get("inputs_s_lig"),
            "widget_shear_s_lig": st.session_state.get("shear_s_lig"),
            "shear_design_status": shear_design_status_out,
            "auto_design_active": st.session_state.get("auto_design_active"),
        },
        run_id="pre-fix",
        hypothesis_id="E",
    )
    # endregion

    return {
        "phi_Vu_cap": results.phi_Vu,
        "Vu_utilisation": shear_util,
        "V_eq": results.V_eq,
        "Vuc_kN": results.Vuc_kN,
        "Vus_kN": results.Vus_kN,
        "shear_ok": results.shear_ok,
    }
