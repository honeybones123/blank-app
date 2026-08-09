from __future__ import annotations

import math
from typing import Any

import numpy as np


def resolve_shear_spacing_truth(
    *,
    provided_spacing_mm: float | None,
    required_spacing_mm: float | None,
    effective_spacing_mm: float | None,
    tolerance_mm: float = 0.51,
) -> dict[str, Any]:
    """Classify whether provided or required spacing governs the shear check."""

    def _f(x: Any) -> float | None:
        try:
            if x is None:
                return None
            v = float(x)
            if math.isnan(v):
                return None
            return v
        except Exception:
            return None

    p = _f(provided_spacing_mm)
    r = _f(required_spacing_mm)
    e = _f(effective_spacing_mm)
    tol = float(tolerance_mm)

    out: dict[str, Any] = {
        "provided_spacing_mm": p,
        "required_spacing_mm": r,
        "effective_spacing_mm": e,
        "governing_spacing_source": None,
    }

    if e is None:
        out["governing_spacing_source"] = "provided" if p is not None else None
        return out

    match_p = p is not None and abs(e - p) <= tol
    match_r = r is not None and abs(e - r) <= tol

    if match_p and not match_r:
        src = "provided"
    elif match_r and not match_p:
        src = "required"
    elif match_p and match_r:
        src = "provided"
    else:
        if p is None and r is None:
            src = None
        elif p is None:
            src = "required"
        elif r is None:
            src = "provided"
        else:
            dp = abs(e - p)
            dr = abs(e - r)
            src = "required" if dr + 1e-9 < dp else "provided"

    out["governing_spacing_source"] = src
    return out


def session_final_shear_truth_bundle_complete(state: dict[str, Any] | None) -> bool:
    """
    True when state carries an explicit final shear truth publication slice.
    """
    s = dict(state or {})
    if not str(s.get("final_shear_status_source") or "").strip():
        return False
    if not isinstance(s.get("final_shear_truth_resolved"), bool):
        return False
    if s.get("published_result_spacing_mm") is None:
        return False
    if not str(s.get("published_result_spacing_meaning") or "").strip():
        return False
    return True


def approximate_concrete_tension_area_mm2(b_mm: float, D_mm: float) -> float:
    """Approximate concrete tension area used by the legacy shear state adapter."""
    return float(b_mm or 0.0) * float(D_mm or 0.0) / 2.0


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


def duct_area_mm2(n_ducts: float, duct_dia_mm: float) -> float:
    """Legacy duct area proxy used by the shear page duct input block."""
    n = 0.0 if n_ducts is None else float(n_ducts)
    dia = 0.0 if duct_dia_mm is None else float(duct_dia_mm)
    return n * (dia**2) * 3.14159 / 4.0


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


def web_crushing_fallback_values(
    *,
    V_star_kN: float,
    T_star_kNm: float,
    uh_mm: float,
    A_oh_mm2: float,
    b_v_mm: float,
    d_v_mm: float,
    phi: float,
    Vu_max_kN: float,
) -> dict[str, Any]:
    """Legacy shear-page web-crushing fallback demand/capacity values."""
    Vu_max_N = float(Vu_max_kN or 0.0) * 1e3
    V_star_N = float(V_star_kN or 0.0) * 1e3
    T_star_Nmm = float(T_star_kNm or 0.0) * 1e6
    b_v = float(b_v_mm or 0.0)
    d_v = float(d_v_mm or 0.0)
    uh = float(uh_mm or 0.0)
    A_oh = float(A_oh_mm2 or 0.0)
    phi_value = float(phi or 0.0)

    b_v_d_v = b_v * d_v or 1.0
    term_V = V_star_N / b_v_d_v
    term_T = T_star_Nmm * uh / (1.7 * (A_oh**2 or 1.0))
    lhs = math.sqrt(term_V**2 + term_T**2)
    rhs = phi_value * Vu_max_N / b_v_d_v

    return {
        "Vu_max_N": Vu_max_N,
        "V_star_N": V_star_N,
        "T_star_Nmm": T_star_Nmm,
        "term_V": term_V,
        "term_T": term_T,
        "LHS": lhs,
        "RHS": rhs,
        "web_ok": lhs <= rhs,
    }


def shear_check_display_scalars(
    *,
    T_star_kNm: float,
    D_mm: float,
    d_mm: float,
    fc_mpa: float,
    Vuc_kN: float,
    Vus_kN: float,
    P_v_kN: float,
    phi: float,
    V_eq_kN: float,
) -> dict[str, Any]:
    """Scalar display/fallback values used by the shear check narrative."""
    Vu_total_kN = float(Vuc_kN or 0.0) + float(Vus_kN or 0.0) + float(P_v_kN or 0.0)
    phi_Vu = float(phi or 0.0) * Vu_total_kN
    return {
        "T_star_Nmm": float(T_star_kNm or 0.0) * 1e6,
        "dv_1": 0.72 * float(D_mm or 0.0),
        "dv_2": 0.9 * float(d_mm or 0.0),
        "sqrt_fc_limited": min(math.sqrt(float(fc_mpa or 0.0)), 8.0),
        "Vu_total_kN": Vu_total_kN,
        "phi_Vu": phi_Vu,
        "shear_ok": phi_Vu >= float(V_eq_kN or 0.0),
    }


def longitudinal_strain_fallback_values(
    *,
    M_star_kNm: float,
    V_star_kN: float,
    T_star_kNm: float,
    P_v_kN: float,
    N_star_kN: float,
    d_v_mm: float,
    uh_mm: float,
    Ao_mm2: float,
    Es_mpa: float,
    Ec_mpa: float,
    A_st_mm2: float,
    A_pt_mm2: float,
    f_po_mpa: float,
    A_ct_mm2: float,
    Ep_mpa: float = 195000.0,
) -> dict[str, Any]:
    """Legacy shear-page longitudinal-strain fallback values for check display."""
    M_star_Nmm = abs(float(M_star_kNm or 0.0)) * 1e6
    V_star = float(V_star_kN or 0.0)
    T_star_Nmm = float(T_star_kNm or 0.0) * 1e6
    P_v = float(P_v_kN or 0.0)
    N_star_N = 0.5 * float(N_star_kN or 0.0) * 1e3
    d_v = float(d_v_mm or 0.0)
    uh = float(uh_mm or 0.0)
    Ao = float(Ao_mm2 or 0.0)
    Es = float(Es_mpa or 0.0)
    Ec = float(Ec_mpa or 0.0)
    A_st = float(A_st_mm2 or 0.0)
    A_pt = float(A_pt_mm2 or 0.0)
    f_po = float(f_po_mpa or 0.0)
    A_ct = float(A_ct_mm2 or 0.0)
    Ep = float(Ep_mpa or 0.0)

    term_M = M_star_Nmm / (d_v or 1.0)
    Vprime_kN = abs(V_star) - P_v
    Vprime_N = Vprime_kN * 1e3
    torsion_N = 0.97 * T_star_Nmm * uh / (2.0 * (Ao or 1.0))
    sqrt_inner = math.sqrt(Vprime_N**2 + torsion_N**2)
    A_pt_fpo_N = A_pt * f_po
    numerator_1 = term_M + sqrt_inner + N_star_N - A_pt_fpo_N
    denom1 = 2.0 * (Es * A_st + Ep * A_pt)
    eps_x_1 = numerator_1 / denom1 if denom1 > 0.0 else 0.0
    V_abs_N = abs(V_star) * 1e3
    numerator_2 = term_M + V_abs_N - P_v * 1e3 + N_star_N - A_pt_fpo_N
    denom2 = 2.0 * (Es * A_st + Ep * A_pt + Ec * A_ct)
    eps_x_2 = numerator_2 / denom2 if denom2 > 0.0 else 0.0
    use_equation_1 = eps_x_1 >= 0.0
    eps_x_raw = eps_x_1 if use_equation_1 else eps_x_2
    eps_x = max(-0.0002, min(eps_x_raw, 0.003))

    return {
        "M_star_Nmm": M_star_Nmm,
        "term_M": term_M,
        "Vprime_kN": Vprime_kN,
        "Vprime_N": Vprime_N,
        "T_star_Nmm": T_star_Nmm,
        "torsion_N": torsion_N,
        "sqrt_inner": sqrt_inner,
        "N_star_N": N_star_N,
        "A_pt_fpo_N": A_pt_fpo_N,
        "numerator_1": numerator_1,
        "Ep": Ep,
        "denom1": denom1,
        "eps_x_1": eps_x_1,
        "V_abs_N": V_abs_N,
        "numerator_2": numerator_2,
        "denom2": denom2,
        "eps_x_2": eps_x_2,
        "use_equation_1": use_equation_1,
        "eps_x_raw": eps_x_raw,
        "eps_x": eps_x,
    }


def nonprestressed_longitudinal_strain_display_values(
    *,
    term_M_N: float,
    V_eq_N: float,
    N_star_half_N: float,
    Es_mpa: float,
    A_st_mm2: float,
) -> dict[str, float]:
    """Displayed non-prestressed Check 4 strain form, preserving legacy page math."""
    numerator = float(term_M_N) + float(V_eq_N) + float(N_star_half_N)
    denominator = 2.0 * (float(Es_mpa) * float(A_st_mm2))
    eps_x = numerator / denominator if denominator > 0.0 else 0.0
    return {
        "numerator": numerator,
        "denominator": denominator,
        "eps_x": eps_x,
    }


def shear_capacity_utilisation_values(
    shear_results: Any,
    phi: float,
) -> dict[str, float]:
    """Shared sectional and web-crushing utilisation scalars for shear summaries."""
    V_eq = float(getattr(shear_results, "V_eq", 0.0) or 0.0)
    phi_Vu_cap = float(getattr(shear_results, "phi_Vu", 0.0) or 0.0)
    Vu_max_kN = float(getattr(shear_results, "Vu_max_kN", 0.0) or 0.0)
    phi_Vu_max_kN = float(phi or 0.0) * Vu_max_kN
    util = (V_eq / phi_Vu_cap) if phi_Vu_cap > 0.0 else float("nan")
    web_util = (V_eq / phi_Vu_max_kN) if phi_Vu_max_kN > 0.0 else float("nan")
    return {
        "V_eq": V_eq,
        "phi_Vu_cap": phi_Vu_cap,
        "Vu_max_kN": Vu_max_kN,
        "phi_Vu_max_kN": phi_Vu_max_kN,
        "util": util,
        "web_util": web_util,
    }


def shear_reinforcement_spacing_check_values(
    *,
    Asv_mm2: float,
    s_lig_mm: float | None,
    fc_mpa: float,
    b_v_mm: float,
    f_syv_mpa: float,
    D_mm: float | None,
) -> dict[str, Any]:
    """Minimum shear reinforcement and maximum spacing display/check values."""
    s_lig = s_lig_mm
    Asv_over_s = float(Asv_mm2) / s_lig if s_lig else 0.0
    Asv_min_over_s = minimum_shear_reinforcement_asv_per_s(
        fc_mpa,
        b_v_mm,
        f_syv_mpa,
    )
    max_spacing = maximum_shear_spacing_mm(D_mm)
    spacing_ok = s_lig <= max_spacing if s_lig else False
    return {
        "Asv_over_s": Asv_over_s,
        "Asv_min_over_s": Asv_min_over_s,
        "min_shear_ok": Asv_over_s >= Asv_min_over_s,
        "max_spacing": max_spacing,
        "spacing_ok": spacing_ok,
    }


def maximum_shear_spacing_mm(D_mm: float | None) -> float:
    """AS 3600 maximum shear reinforcement spacing display value."""
    return min(0.75 * float(D_mm), 500.0) if D_mm else 500.0


def compute_canonical_shear_truth_from_bundle(
    st_state: dict[str, Any],
    *,
    bundle: dict[str, Any],
    canonical_shear_truth_input_shape: str,
    zone_payload: dict[str, Any] | None = None,
    provided_spacing_mm: float | None = None,
    required_spacing_mm: float | None = None,
    effective_spacing_mm: float | None = None,
) -> dict[str, Any]:
    """
    Pure canonical shear publication truth from an already-normalised calc bundle.
    """
    zp = dict(zone_payload or {})
    nb = dict(bundle or {})
    res = nb["results"]
    phi = float(nb["phi"])
    inp = nb["inputs"]

    util_sec = (res.V_eq / res.phi_Vu) if res.phi_Vu > 0 else float("nan")
    phi_vu_max = phi * float(res.Vu_max_kN or 0.0)
    util_web = (res.V_eq / phi_vu_max) if phi_vu_max > 0 else float("nan")

    def _f(x: Any) -> float | None:
        try:
            if x is None:
                return None
            v = float(x)
            if math.isnan(v) or math.isinf(v):
                return None
            return v
        except Exception:
            return None

    util_sec_f = _f(util_sec)
    util_web_f = _f(util_web)
    u_env = _f(zp.get("shear_util_min") or st_state.get("shear_util_min"))
    web_util_governing = _f(util_web)

    s_prov = _f(provided_spacing_mm)
    if s_prov is None:
        s_prov = _f(st_state.get("s_lig")) or _f(getattr(inp, "s_lig", None)) or _f(inp.s_lig)
    s_req = _f(required_spacing_mm)
    if s_req is None:
        s_req = _f(st_state.get("shear_required_spacing_mm"))
    if s_req is None and session_final_shear_truth_bundle_complete(st_state):
        s_req = _f(zp.get("shear_spacing_end_mm"))
    s_eff = _f(effective_spacing_mm)
    if s_eff is None:
        s_eff = _f(st_state.get("shear_effective_spacing_mm"))
    if s_eff is None:
        s_sec = st_state.get("shear_sectional_check_spacing_mm")
        s_eff = _f(s_sec) if s_sec is not None else s_prov
    spacing_truth = resolve_shear_spacing_truth(
        provided_spacing_mm=s_prov,
        required_spacing_mm=s_req,
        effective_spacing_mm=s_eff,
    )

    governing_candidates: list[dict[str, Any]] = []
    if util_sec_f is not None:
        governing_candidates.append(
            {
                "name": "Sectional shear capacity",
                "source": "sectional_shear_capacity",
                "util": util_sec_f,
                "demand_kN": _f(res.V_eq),
                "capacity_kN": _f(res.phi_Vu),
                "reason": "sectional_shear_capacity_governs",
            },
        )
    if util_web_f is not None:
        governing_candidates.append(
            {
                "name": "Web-crushing strength",
                "source": "web_crushing_strength",
                "util": util_web_f,
                "demand_kN": _f(res.V_eq),
                "capacity_kN": _f(phi_vu_max),
                "reason": "web_crushing_strength_governs",
            },
        )

    governing = (
        max(
            governing_candidates,
            key=lambda item: (
                float(item.get("util"))
                if item.get("util") is not None
                else float("-inf")
            ),
        )
        if governing_candidates
        else None
    )
    shear_util_governing = _f((governing or {}).get("util"))
    governing_name = str((governing or {}).get("name") or "").strip() or "Final published shear truth"
    governing_source = str((governing or {}).get("source") or "").strip() or "unresolved_governing_shear_truth"
    governing_reason = str((governing or {}).get("reason") or "").strip()
    governing_demand_kN = _f((governing or {}).get("demand_kN"))
    governing_capacity_kN = _f((governing or {}).get("capacity_kN"))

    reasons: list[str] = []
    if governing_reason:
        reasons.append(governing_reason)
    shear_truth_inconsistent_status_override: str | None = None
    env_st = str(zp.get("shear_envelope_status") or st_state.get("shear_envelope_status") or "").strip().upper()

    if shear_util_governing is None:
        status = "FAIL"
        reasons.append("missing_governing_shear_util")
    elif shear_util_governing <= 1.0 + 1e-9:
        status = "PASS"
    else:
        status = "FAIL"
        reasons.append("governing_shear_util_exceeds_unity")

    spacing_override_active = False
    spacing_override_reason = ""

    if env_st and env_st not in {"PASS", "FAIL"}:
        reasons.append(f"raw_envelope_status={env_st.lower()}")

    reason_txt = "; ".join(dict.fromkeys([r for r in reasons if r]))

    return {
        "provided_spacing_mm": s_prov,
        "effective_spacing_mm": s_eff,
        "required_spacing_mm": s_req,
        "shear_provided_spacing_mm": s_prov,
        "shear_effective_spacing_mm": s_eff,
        "shear_required_spacing_mm": s_req,
        "shear_governing_check_name": governing_name,
        "shear_governing_demand_kN": governing_demand_kN,
        "shear_governing_capacity_kN": governing_capacity_kN,
        "shear_governing_util": shear_util_governing,
        "shear_governing_status": status,
        "shear_governing_reason": reason_txt,
        "shear_governing_source": governing_source,
        "shear_util_governing": shear_util_governing,
        "web_util_governing": web_util_governing,
        "shear_truth_status": status,
        "shear_truth_reason": reason_txt,
        "canonical_shear_spacing_override_active": bool(spacing_override_active),
        "canonical_shear_spacing_override_reason": spacing_override_reason,
        "shear_truth_inconsistent_status_override": shear_truth_inconsistent_status_override,
        "shear_spacing_truth": spacing_truth,
        "shear_envelope_util_min": u_env,
        "shear_sectional_util": _f(util_sec),
        "canonical_shear_truth_input_shape": canonical_shear_truth_input_shape,
    }


def format_shear_row_util(value: object) -> str:
    """Format utilisation for summary rows; never raises on None / NaN."""
    if value is None:
        return "—"
    try:
        v = float(value)
    except (TypeError, ValueError):
        return "—"
    if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
        return "—"
    return f"{v:.2f}"


def shear_truth_status_from_util(utilisation: float | None) -> str:
    if utilisation is None or (
        isinstance(utilisation, float)
        and (math.isnan(utilisation) or math.isinf(utilisation))
    ):
        return "—"
    if utilisation <= 1.0:
        return "NEAR LIMIT" if utilisation >= 0.95 else "PASS"
    return "FAIL"


def required_asv_per_s(V, phi, Vuc, fy, dv, *, cot_theta_v: float = 1.0):
    """
    Required A_sv/s (mm^2/mm) from along-span shear demand array.

    Inputs V and Vuc are in kN; fy is in MPa; dv is in mm.
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
        float(fy_mpa or 0.0) * float(dv_mm or 0.0) * cot_safe,
        1e-9,
    )
    s_raw = float(Asv_mm2) / max(asv_s_req, 1e-12)
    s = min(s_raw, s_max_mm)
    s = max(s, float(s_min_mm))
    inc = max(float(increment_mm), 1.0)
    s = max(float(s_min_mm), min(s_max_mm, math.floor(s / inc + 1e-9) * inc))
    s = math.floor(s / 5.0) * 5.0
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
    Required midspan spacing from shear demand at x = L/2.

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


def cotangent(rad: float) -> float:
    return 1.0 / math.tan(float(rad))


def _cot(rad: float) -> float:
    return cotangent(rad)


def stirrup_area_mm2(legs: float, diameter_mm: float) -> float:
    """Effective transverse reinforcement area for identical stirrup legs."""
    legs_eff = 0.0 if float(legs or 0.0) < 2.0 else float(legs or 0.0)
    return legs_eff * math.pi * float(diameter_mm or 0.0) ** 2 / 4.0


def compute_shear_capacity_values(inp: Any) -> dict[str, Any]:
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


def derive_eps_top_bot_for_step4_diagram(
    eps_x: float,
    delta: float = 0.00035,
) -> tuple[float, float]:
    """Create a simple top/bottom strain profile around eps_x for Step 4 diagrams."""
    ex = float(eps_x)
    return ex - float(delta), ex + float(delta)


def build_shear_summary_rows_with_overrides(
    rows_summary: list[dict[str, Any]],
    shear_results: Any,
    phi: float,
) -> dict[str, Any]:
    """
    Pure summary-table values for the specialised shear page.

    The Streamlit page remains responsible for state publication and click wiring;
    this helper owns the derived utilisation/override values only.
    """
    rows_out = [dict(row) for row in (rows_summary or [])]

    utilisation_values = shear_capacity_utilisation_values(shear_results, phi)
    V_eq = utilisation_values["V_eq"]
    phi_Vu = utilisation_values["phi_Vu_cap"]
    Vu_max_kN = utilisation_values["Vu_max_kN"]
    eps_x = float(getattr(shear_results, "eps_x", 0.0) or 0.0)
    k_v = float(getattr(shear_results, "k_v", 0.0) or 0.0)
    theta_v_deg = float(getattr(shear_results, "theta_v_deg", 0.0) or 0.0)
    Vuc_kN = float(getattr(shear_results, "Vuc_kN", 0.0) or 0.0)
    Vus_kN = float(getattr(shear_results, "Vus_kN", 0.0) or 0.0)

    summary_util = utilisation_values["util"]
    summary_phi_vu_max = utilisation_values["phi_Vu_max_kN"]
    summary_web_util = utilisation_values["web_util"]

    dash = "\u2014"
    summary_overrides = {
        "Sectional shear capacity": {
            "capacity": f"\u03c6Vu = {phi_Vu:.1f} kN",
            "action": f"V*eq = {V_eq:.1f} kN",
            "Utilisation": f"{summary_util:.2f}" if not math.isnan(summary_util) else dash,
            "Status": "PASS" if summary_util <= 1.0 else "FAIL",
        },
        "Equivalent design shear": {
            "capacity": dash,
            "action": f"V*eq = {V_eq:.1f} kN",
        },
        "Longitudinal strain": {
            "capacity": dash,
            "action": f"\u03b5x = {eps_x:.5f}",
        },
        "Shear model parameters": {
            "capacity": dash,
            "action": f"k_v = {k_v:.3f}, \u03b8_v = {theta_v_deg:.1f}\u00b0",
        },
        "Concrete shear strength": {
            "capacity": dash,
            "action": f"Vuc = {Vuc_kN:.1f} kN",
        },
        "Steel shear strength": {
            "capacity": dash,
            "action": f"Vs = Vus = {Vus_kN:.1f} kN",
        },
        "Web-crushing strength": {
            "capacity": f"\u03c6Vu,max = {summary_phi_vu_max:.1f} kN",
            "action": f"V*eq = {V_eq:.1f} kN",
            "Utilisation": f"{summary_web_util:.2f}" if not math.isnan(summary_web_util) else dash,
            "Status": "PASS" if summary_web_util <= 1.0 else "FAIL",
        },
    }

    for row in rows_out:
        override = summary_overrides.get(row.get("Check", ""))
        if override:
            row.update(override)

    return {
        "rows_summary": rows_out,
        "summary_util": summary_util,
        "summary_phi_vu_max": summary_phi_vu_max,
        "summary_web_util": summary_web_util,
        "summary_overrides": summary_overrides,
    }
