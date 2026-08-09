"""V2-owned AS 3600 bending capacity calculation."""

from __future__ import annotations

from dataclasses import dataclass

def resolve_bending_faces(moment_sign: str) -> tuple[str, str, bool]:
    """
    From the active bending case (display / demand sign).

    Returns:
        tension_face: "bottom" | "top"
        compression_face: "top" | "bottom"
        is_hogging: True if moment_sign is negative (hogging)
    """
    sign = str(moment_sign or "positive").strip().lower()
    is_hogging = sign == "negative"
    if is_hogging:
        return "top", "bottom", True
    return "bottom", "top", False

def stress_block_factors(fc_mpa: float) -> tuple[float, float]:
    """AS 3600 rectangular stress-block factors (alpha2, gamma)."""
    fc = float(fc_mpa or 0.0)
    alpha2 = max(0.67, 0.85 - 0.0015 * fc)
    gamma = max(0.67, 0.97 - 0.0025 * fc)
    return float(alpha2), float(gamma)

def compression_block_lever_arm_values(
    *,
    dn_mm: float,
    gamma: float,
    d_mm: float,
) -> dict[str, float]:
    """Rectangular compression-block depth and internal lever arm."""
    dn = float(dn_mm or 0.0)
    gamma_value = float(gamma or 0.0)
    d = float(d_mm or 0.0)
    a = gamma_value * dn
    z = d - 0.5 * a
    return {
        "a": a,
        "z": z,
    }

def hogging_tension_effective_depth_mm(D: float, do_mm: float) -> float:
    """
    Hogging effective depth d: distance from the bottom compression fibre to the
    centroid of top tension steel.
    """
    df = float(D or 0.0)
    do_v = float(do_mm or 0.0)
    if df <= 0.0:
        return max(0.0, do_v)
    if do_v <= 0.0:
        return 0.0
    if do_v >= 0.35 * df:
        return do_v
    return max(0.0, df - do_v)

def solve_bending_capacity(moment_sign: str, M_star_kNm: float, inputs: dict) -> dict:
    """Solve signed flexural capacity for sagging/hogging demand."""
    sign = str(moment_sign or "positive").strip().lower()
    if sign not in {"positive", "negative"}:
        sign = "positive"

    tension_face, compression_face, _is_hog = resolve_bending_faces(sign)

    b = float(inputs.get("b", 0.0) or 0.0)
    D = float(inputs.get("D", 0.0) or 0.0)
    fc = float(inputs.get("fc", 0.0) or 0.0)
    fsy = float(inputs.get("fsy", 0.0) or 0.0)
    phi = float(inputs.get("phi_bend", 0.85) or 0.85)

    if tension_face == "bottom":
        Ast = float(inputs.get("Ast_bot", 0.0) or 0.0)
        d_mm = float(inputs.get("d", 0.0) or 0.0)
        tension_steel_label = "Bottom reinforcement"
    else:
        Ast = float(inputs.get("Ast_top", 0.0) or 0.0)
        do_mm = float(inputs.get("do", 0.0) or 0.0)
        d_mm = hogging_tension_effective_depth_mm(D, do_mm)
        tension_steel_label = "Top reinforcement"

    alpha2, gamma = stress_block_factors(fc)

    if min(b, D, fc, fsy, phi, Ast, d_mm) <= 0.0:
        return {
            "moment_sign": sign,
            "M_star_kNm": float(max(0.0, M_star_kNm)),
            "phi_Mu_kNm": 0.0,
            "Mu_nom_kNm": 0.0,
            "util": 0.0 if float(max(0.0, M_star_kNm)) <= 0.0 else float("inf"),
            "status": "\u2014",
            "dn_mm": float("nan"),
            "ku": float("nan"),
            "phi": phi,
            "tension_face": tension_face,
            "compression_face": compression_face,
            "tension_steel_label": tension_steel_label,
            "alpha2": alpha2,
            "gamma": gamma,
            "d_mm": d_mm,
            "Ast_tension_mm2": Ast,
        }

    T = Ast * fsy
    denom = alpha2 * fc * b * gamma
    c = T / denom if denom > 0 else float("nan")
    lever_arm = compression_block_lever_arm_values(dn_mm=c, gamma=gamma, d_mm=d_mm)
    a = lever_arm["a"] if c == c else float("nan")
    z = lever_arm["z"] if a == a else float("nan")
    Mu_nom = T * z / 1e6 if z == z else 0.0
    phi_Mu = phi * Mu_nom
    M_star = float(max(0.0, M_star_kNm))
    util = M_star / phi_Mu if phi_Mu > 0 else (0.0 if M_star <= 0 else float("inf"))
    ku = c / d_mm if d_mm > 0 else float("nan")

    if M_star <= 1e-9:
        status = "INFO"
    elif util <= 1.0:
        status = "PASS"
    else:
        status = "FAIL"

    return {
        "moment_sign": sign,
        "M_star_kNm": M_star,
        "phi_Mu_kNm": float(phi_Mu),
        "Mu_nom_kNm": float(Mu_nom),
        "util": float(util),
        "status": status,
        "dn_mm": float(c),
        "ku": float(ku),
        "phi": float(phi),
        "tension_face": tension_face,
        "compression_face": compression_face,
        "tension_steel_label": tension_steel_label,
        "alpha2": float(alpha2),
        "gamma": float(gamma),
        "d_mm": float(d_mm),
        "Ast_tension_mm2": float(Ast),
    }

@dataclass(frozen=True)
class BendingCapacityInput:
    width_mm: float
    depth_mm: float
    concrete_strength_mpa: float
    reinforcement_strength_mpa: float
    capacity_factor: float
    bottom_steel_area_mm2: float
    top_steel_area_mm2: float
    positive_effective_depth_mm: float
    top_steel_depth_mm: float


def calculate_bending_capacity(
    *, moment_sign: str, demand_knm: float, values: BendingCapacityInput,
) -> dict:
    payload = {
        "b": values.width_mm, "D": values.depth_mm,
        "fc": values.concrete_strength_mpa,
        "fsy": values.reinforcement_strength_mpa,
        "phi_bend": values.capacity_factor,
        "Ast_bot": values.bottom_steel_area_mm2,
        "Ast_top": values.top_steel_area_mm2,
        "d": values.positive_effective_depth_mm,
        "do": values.top_steel_depth_mm,
    }
    return solve_bending_capacity(moment_sign, demand_knm, payload)


__all__ = ["BendingCapacityInput", "calculate_bending_capacity"]
