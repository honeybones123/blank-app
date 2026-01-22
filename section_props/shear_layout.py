from __future__ import annotations
from typing import Dict, List


def _internal_leg_positions(x0: float, x1: float, n_legs: int) -> List[float]:
    if n_legs <= 2:
        return []
    span = x1 - x0
    if span <= 0:
        return []
    return [x0 + span * j / (n_legs - 1) for j in range(1, n_legs - 1)]


def _web_zone(shape_name: str, dims: Dict[str, float]) -> Dict[str, float]:
    """
    Returns:
      bf, D, x_web0, x_web1, b_web
    Web zone is centered within bf.
    """
    bf = float(dims["bf"])
    D = float(dims["D"])

    if shape_name.startswith("T-Section"):
        b_web = float(dims["bw"])
    elif shape_name.startswith("I-Section"):
        b_web = float(dims["tw"])
    else:
        raise ValueError("Shear layout only supported for T/I in Stage 1.")

    x_web0 = (bf - b_web) / 2.0
    x_web1 = x_web0 + b_web
    return {"bf": bf, "D": D, "x_web0": x_web0, "x_web1": x_web1, "b_web": b_web}


def compute_shear_reo_layout_T_I(
    *,
    shape_name: str,
    dims: Dict[str, float],
    cover_side: float,
    cover_top: float,
    cover_bot: float,
    lig_d: float,
    lig_legs: int,
) -> Dict:
    """
    IMPORTANT: Cage + legs are constrained to the WEB ZONE so they cannot exit
    the concrete perimeter for T/I sections.

    Returns:
      {"cage": {"x0","y0","x1","y1"}, "stirrups":[{"legs":[{x1,y1,x2,y2},...]}]}
    """
    if lig_d <= 0 or lig_legs < 2:
        return {"cage": None, "stirrups": []}

    wz = _web_zone(shape_name, dims)
    x_web0 = wz["x_web0"]
    x_web1 = wz["x_web1"]
    D = wz["D"]

    r = lig_d / 2.0

    # Cage rectangle inside WEB zone, inset by cover + link radius
    x0 = x_web0 + cover_side + r
    x1 = x_web1 - cover_side - r
    y0 = cover_top + r
    y1 = D - cover_bot - r

    # Guard: if covers too large, don't draw outside — just skip shear drawing
    if x1 <= x0 or y1 <= y0:
        return {"cage": None, "stirrups": []}

    # Legs: outer legs + internal legs uniformly spaced between
    xs = [x0] + _internal_leg_positions(x0, x1, lig_legs) + [x1]
    legs = [{"x1": x, "y1": y0, "x2": x, "y2": y1} for x in xs]

    return {"cage": {"x0": x0, "y0": y0, "x1": x1, "y1": y1}, "stirrups": [{"legs": legs}]}
