from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Any


@dataclass(frozen=True)
class Dim:
    key: str
    label: str
    unit: str = "mm"
    default: float = 100.0
    min_value: float = 0.0
    help: str = ""


# Shape definitions (v1 starter set)
SHAPES = {
    "Rectangle (b × D)": [
        Dim("b", "Width b", default=300, min_value=1),
        Dim("D", "Depth D", default=600, min_value=1),
    ],
    "Hollow Rectangle (b × D, thickness t)": [
        Dim("b", "Outer width b", default=300, min_value=1),
        Dim("D", "Outer depth D", default=600, min_value=1),
        Dim("t", "Wall thickness t", default=50, min_value=1),
    ],
    "Circle (diameter D)": [
        Dim("D", "Diameter D", default=400, min_value=1),
    ],
    "Hollow Circle (diameter D, thickness t)": [
        Dim("D", "Outer diameter D", default=400, min_value=1),
        Dim("t", "Wall thickness t", default=50, min_value=1),
    ],
    "T-Section (bf, tf, bw, D)": [
        Dim("bf", "Flange width bf", default=600, min_value=1),
        Dim("tf", "Flange thickness tf", default=100, min_value=1),
        Dim("bw", "Web width bw", default=250, min_value=1),
        Dim("D", "Overall depth D", default=600, min_value=1),
    ],
    "I-Section (bf, tf, tw, D)": [
        Dim("bf", "Flange width bf", default=600, min_value=1),
        Dim("tf", "Flange thickness tf", default=100, min_value=1),
        Dim("tw", "Web thickness tw", default=200, min_value=1),
        Dim("D", "Overall depth D", default=800, min_value=1),
    ],
}


def get_default_dims(shape_name: str) -> Dict[str, float]:
    dims = {}
    for d in SHAPES[shape_name]:
        dims[d.key] = float(d.default)
    return dims
