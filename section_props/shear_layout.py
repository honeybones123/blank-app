from __future__ import annotations
from typing import Dict, List

from section_props.shape_utils import normalise_shape_name


def _internal_leg_positions(x0: float, x1: float, n_legs: int) -> List[float]:
    if n_legs <= 2:
        return []
    span = x1 - x0
    if span <= 0:
        return []
    return [x0 + span * j / (n_legs - 1) for j in range(1, n_legs - 1)]


def _flatten_reo_points_for_shear(reo_points: List[Dict] | None) -> List[Dict[str, float]]:
    pts: List[Dict[str, float]] = []
    if not reo_points:
        return pts
    for pt in reo_points:
        try:
            db = float(pt.get("db", 0.0) or 0.0)
            x = float(pt.get("x", 0.0) or 0.0)
            y = float(pt.get("y", 0.0) or 0.0)
        except Exception:
            continue
        if db <= 0:
            continue
        pts.append({"x": x, "y": y, "db": db})
    return pts


def _web_zone(shape_name: str, dims: Dict[str, float]) -> Dict[str, float]:
    """
    Returns:
      bf, D, x_web0, x_web1, b_web
    Web zone is centered within bf.
    """
    s = str(shape_name or "").lower()
    if "rectangle" in s or s in ("rect", "rectangular", "rect (bxd)", "rect (b×d)", "rect (b x d)"):
        b = float(dims.get("b", 0.0) or 0.0)
        D = float(dims.get("D", 0.0) or 0.0)
        return {"bf": b, "D": D, "x_web0": 0.0, "x_web1": b, "b_web": b}

    bf = float(dims.get("bf", dims.get("b", 0.0)) or 0.0)
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
    reo_points: List[Dict] | None = None,
) -> Dict:
    """
    IMPORTANT: Cage + legs are constrained to the WEB ZONE so they cannot exit
    the concrete perimeter for T/I sections.

    Returns:
      {"cage": {"x0","y0","x1","y1"}, "stirrups":[{"legs":[{x1,y1,x2,y2},...]}]}
    """
    shape_key = normalise_shape_name(shape_name)
    if shape_key not in ("T", "I"):
        raise ValueError("Shear layout only supported for T/I in Stage 1.")

    shape_name = "T-Section" if shape_key == "T" else "I-Section"

    if lig_d <= 0 or lig_legs < 2:
        return {"cage": None, "stirrups": []}

    wz = _web_zone(shape_name, dims)
    x_web0 = wz["x_web0"]
    x_web1 = wz["x_web1"]
    D = wz["D"]

    visual_clearance = 0.0
    default_x0 = max(x_web0 + cover_side - visual_clearance, x_web0 + 5.0)
    default_x1 = min(x_web1 - cover_side + visual_clearance, x_web1 - 5.0)
    default_y0 = max(cover_top - visual_clearance, 5.0)
    default_y1 = min(D - cover_bot + visual_clearance, D - 5.0)

    pts = [
        pt for pt in _flatten_reo_points_for_shear(reo_points)
        if x_web0 - 1e-9 <= pt["x"] <= x_web1 + 1e-9
    ]
    if pts:
        min_x = min(pt["x"] - pt["db"] / 2.0 for pt in pts) - visual_clearance
        max_x = max(pt["x"] + pt["db"] / 2.0 for pt in pts) + visual_clearance
        min_y = min(pt["y"] - pt["db"] / 2.0 for pt in pts) - visual_clearance
        max_y = max(pt["y"] + pt["db"] / 2.0 for pt in pts) + visual_clearance
        x0 = max(x_web0 + 5.0, min(default_x0, min_x))
        x1 = min(x_web1 - 5.0, max(default_x1, max_x))
        y0 = max(5.0, min(default_y0, min_y))
        y1 = min(D - 5.0, max(default_y1, max_y))
    else:
        x0, x1, y0, y1 = default_x0, default_x1, default_y0, default_y1

    # Guard: if covers too large, don't draw outside — just skip shear drawing
    if x1 <= x0 or y1 <= y0:
        return {"cage": None, "stirrups": []}

    # Legs: outer legs + internal legs uniformly spaced between
    xs = [x0] + _internal_leg_positions(x0, x1, lig_legs) + [x1]
    legs = [{"x1": x, "y1": y0, "x2": x, "y2": y1} for x in xs]

    return {"cage": {"x0": x0, "y0": y0, "x1": x1, "y1": y1}, "stirrups": [{"legs": legs}]}
