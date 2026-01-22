from __future__ import annotations
from typing import Dict, Tuple


def stress_block_factors_AS3600(f_c_mpa: float) -> Tuple[float, float]:
    """
    AS3600 rectangular stress-block parameters.
    Returns (alpha2, gamma), each bounded >= 0.67.
    """
    fc = float(f_c_mpa)
    alpha2 = max(0.67, 0.85 - 0.0015 * fc)
    gamma = max(0.67, 0.97 - 0.0025 * fc)
    return alpha2, gamma


def _b_web_from_shape(shape_type: str, dims: Dict[str, float]) -> float:
    """
    Stage-1 shapes:
      - T: b_web = bw
      - I: b_web = tw
    """
    if shape_type.upper().startswith("T"):
        return float(dims["bw"])
    if shape_type.upper().startswith("I"):
        return float(dims["tw"])
    raise ValueError("Only T/I supported for Stage-1 ULS helpers.")


def compression_resultant_T_I(
    *,
    shape_type: str,          # "T" or "I"
    dims: Dict[str, float],   # must include bf, tf, D, and bw or tw
    dn_mm: float,
    f_c_mpa: float,
    alpha2: float,
    gamma: float,
) -> Dict[str, float]:
    """
    Piecewise rectangular stress block for T/I sections.

    Coordinates:
      y measured from top fibre downward.

    Stress-block:
      a = gamma * dn
      concrete stress = alpha2 * f'c over the compression zone.

    Width function:
      - 0..tf: width = bf (top flange)
      - tf..a: width = b_web (web thickness/width), centered, but only width matters for C.

    Returns (units):
      C_N        : concrete compression resultant (N)
      yC_mm      : centroid of C from top (mm)
      a_mm       : stress-block depth (mm)
      dn_mm      : neutral axis depth (mm) (clipped)
      C1_N, C2_N : flange/web contributions (N)
    """
    bf = float(dims["bf"])
    tf = float(dims["tf"])
    D = float(dims["D"])
    b_web = _b_web_from_shape(shape_type, dims)

    dn = max(0.0, min(float(dn_mm), D))
    a = max(0.0, min(float(gamma) * dn, D))

    # If no compression zone
    if a <= 0.0:
        return dict(C_N=0.0, yC_mm=0.0, a_mm=a, dn_mm=dn, C1_N=0.0, C2_N=0.0)

    # Convert MPa -> N/mm^2
    sigma = float(alpha2) * float(f_c_mpa)  # N/mm^2

    # Portion in flange: 0..min(a, gamma*tf) OR more directly 0..min(a, tf)?:
    # The stress block depth 'a' is in mm, and flange thickness is tf in mm.
    # Compression zone within flange is 0..min(a, tf) in geometry terms.
    a1 = min(a, tf)          # depth of block inside flange (mm)
    a2 = max(0.0, a - tf)    # depth of block below flange (mm)

    C1 = sigma * bf * a1     # N
    C2 = sigma * b_web * a2  # N
    C = C1 + C2

    # Centroids from top:
    # flange part: at y = a1/2
    # web part: at y = tf + a2/2
    if C <= 0.0:
        yC = 0.0
    else:
        y1 = a1 / 2.0
        y2 = tf + a2 / 2.0
        yC = (C1 * y1 + C2 * y2) / C

    return dict(C_N=C, yC_mm=yC, a_mm=a, dn_mm=dn, C1_N=C1, C2_N=C2)


def solve_dn_from_T_T_I(
    *,
    shape_type: str,          # "T" or "I"
    dims: Dict[str, float],
    T_N: float,
    f_c_mpa: float,
    alpha2: float,
    gamma: float,
) -> Dict[str, float]:
    """
    Solves dn from equilibrium C(dn) = T for T/I sections using the same piecewise block.

    Because C is linear in 'a' (and a is linear in dn), this has a closed-form solution:
      If a <= tf -> C = sigma * bf * a
      If a > tf  -> C = sigma * (bf*tf + b_web*(a-tf))

    Returns:
      dn_mm, a_mm, C_N, yC_mm, branch ("flange" or "web")
    """
    bf = float(dims["bf"])
    tf = float(dims["tf"])
    D = float(dims["D"])
    b_web = _b_web_from_shape(shape_type, dims)

    T = max(0.0, float(T_N))
    sigma = float(alpha2) * float(f_c_mpa)  # N/mm^2

    if sigma <= 0.0 or gamma <= 0.0 or bf <= 0.0:
        return dict(dn_mm=0.0, a_mm=0.0, C_N=0.0, yC_mm=0.0, branch="invalid")

    # Candidate assuming a <= tf:
    # T = sigma * bf * a  -> a = T/(sigma*bf)
    a_flange = T / (sigma * bf)
    if a_flange <= tf + 1e-9:
        dn = a_flange / float(gamma)
        dn = min(max(dn, 0.0), D)
        res = compression_resultant_T_I(
            shape_type=shape_type, dims=dims, dn_mm=dn,
            f_c_mpa=f_c_mpa, alpha2=alpha2, gamma=gamma
        )
        return dict(dn_mm=res["dn_mm"], a_mm=res["a_mm"], C_N=res["C_N"], yC_mm=res["yC_mm"], branch="flange")

    # Otherwise a > tf:
    # T = sigma * (bf*tf + b_web*(a-tf))
    # => T/sigma = bf*tf + b_web*(a-tf)
    # => b_web*a = (T/sigma) - bf*tf + b_web*tf
    # => a = [(T/sigma) + tf*(b_web - bf)] / b_web
    if b_web <= 0.0:
        return dict(dn_mm=0.0, a_mm=0.0, C_N=0.0, yC_mm=0.0, branch="invalid")

    a_web = ((T / sigma) + tf * (b_web - bf)) / b_web
    a_web = max(a_web, tf)  # ensure in this branch
    a_web = min(a_web, D)
    dn = a_web / float(gamma)
    dn = min(max(dn, 0.0), D)

    res = compression_resultant_T_I(
        shape_type=shape_type, dims=dims, dn_mm=dn,
        f_c_mpa=f_c_mpa, alpha2=alpha2, gamma=gamma
    )
    return dict(dn_mm=res["dn_mm"], a_mm=res["a_mm"], C_N=res["C_N"], yC_mm=res["yC_mm"], branch="web")
