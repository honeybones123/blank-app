"""Correctness and mutation-isolation proof for repeated beam solver reuse."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from beam_diagram_runtime import (
    compute_diagram_arrays,
    diagram_solver_cache_clear,
    diagram_solver_cache_info,
)


def main() -> int:
    case = "Multi-span continuous beam"
    params = {
        "beam_system_mode": "Multi-span",
        "node_positions_m": [0.0, 4.0, 8.0, 12.0],
        "support_types": ["Pinned", "Roller", "Roller", "Pinned"],
        "point_loads": [{"x_m": 2.0, "P_kN": 40.0}],
        "udl_loads": [
            {"x_start_m": 0.0, "x_end_m": 12.0, "w_kN_per_m": 18.0}
        ],
    }
    diagram_solver_cache_clear()
    first = compute_diagram_arrays(case, 12.0, params)
    second = compute_diagram_arrays(case, 12.0, params)
    info = diagram_solver_cache_info()
    assert info.misses == 1 and info.hits == 1
    assert info.maxsize == 128
    for lhs, rhs in zip(first[:3], second[:3]):
        np.testing.assert_allclose(lhs, rhs, rtol=0.0, atol=0.0)

    first[0][0] = 999.0
    first[4]["support_positions"][0] = 999.0
    if first[4].get("reactions"):
        first[4]["reactions"]["mutation_probe"] = 999.0
    third = compute_diagram_arrays(case, 12.0, params)
    assert third[0][0] != 999.0
    assert third[4]["support_positions"][0] != 999.0
    assert "mutation_probe" not in third[4].get("reactions", {})

    changed = dict(params)
    changed["point_loads"] = [{"x_m": 2.0, "P_kN": 41.0}]
    compute_diagram_arrays(case, 12.0, changed)
    assert diagram_solver_cache_info().misses == 2
    print("beam_diagram_solver_cache: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
