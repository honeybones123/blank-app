from __future__ import annotations

from typing import Dict, Tuple, List


def validate_dims(shape_name: str, dims: Dict[str, float]) -> Tuple[bool, List[str]]:
    """
    Returns (ok, errors).
    """
    errors: List[str] = []

    def req(key: str):
        if key not in dims:
            errors.append(f"Missing input: {key}")

    # Common checks per shape
    if shape_name.startswith("Rectangle"):
        req("b"); req("D")
        if dims.get("b", 0) <= 0: errors.append("b must be > 0")
        if dims.get("D", 0) <= 0: errors.append("D must be > 0")

    elif shape_name.startswith("Hollow Rectangle"):
        req("b"); req("D"); req("t")
        b = dims.get("b", 0); D = dims.get("D", 0); t = dims.get("t", 0)
        if b <= 0 or D <= 0 or t <= 0:
            errors.append("b, D, t must all be > 0")
        if 2*t >= b or 2*t >= D:
            errors.append("Invalid hollow section: need 2t < b and 2t < D")

    elif shape_name.startswith("Circle"):
        req("D")
        if dims.get("D", 0) <= 0: errors.append("D must be > 0")

    elif shape_name.startswith("Hollow Circle"):
        req("D"); req("t")
        D = dims.get("D", 0); t = dims.get("t", 0)
        if D <= 0 or t <= 0:
            errors.append("D and t must be > 0")
        if 2*t >= D:
            errors.append("Invalid hollow circle: need 2t < D")

    elif shape_name.startswith("T-Section"):
        req("bf"); req("tf"); req("bw"); req("D")
        bf = dims.get("bf", 0); tf = dims.get("tf", 0); bw = dims.get("bw", 0); D = dims.get("D", 0)
        if bf <= 0 or tf <= 0 or bw <= 0 or D <= 0:
            errors.append("bf, tf, bw, D must all be > 0")
        if tf >= D:
            errors.append("Invalid T-section: need tf < D")
        if bw > bf:
            errors.append("Invalid T-section: bw should be <= bf")

    elif shape_name.startswith("I-Section"):
        req("bf"); req("tf"); req("tw"); req("D")
        bf = dims.get("bf", 0); tf = dims.get("tf", 0); tw = dims.get("tw", 0); D = dims.get("D", 0)
        if bf <= 0 or tf <= 0 or tw <= 0 or D <= 0:
            errors.append("bf, tf, tw, D must all be > 0")
        if 2*tf >= D:
            errors.append("Invalid I-section: need 2tf < D")
        if tw > bf:
            errors.append("Invalid I-section: tw should be <= bf")

    else:
        errors.append(f"Unknown shape: {shape_name}")

    return (len(errors) == 0), errors
