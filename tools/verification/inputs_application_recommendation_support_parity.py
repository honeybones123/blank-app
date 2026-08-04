"""Parity lock for pure Inputs recommendation presentation support."""

from __future__ import annotations

import math
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import inputs_page_app_contract_bridge as legacy
from inputs_application.recommendation_support import (
    design_optimisation_goal_label,
    resolve_geometry_width_context,
    severe_shear_failure,
    shear_severity_band,
)


def main() -> int:
    states = (
        {},
        {"design_optimisation_goal": "balanced"},
        {"design_optimisation_goal": "minimum_weight"},
        {"sec_shape": "RECT", "b": 425.0},
        {"sec_shape": "T", "b": 425.0, "bw": 275.0},
        {"sec_shape": "I", "b": 425.0, "tw": 180.0},
    )
    for state in states:
        assert design_optimisation_goal_label(state) == legacy._design_optimisation_goal_label(state)
        assert resolve_geometry_width_context(state) == legacy._resolve_geometry_width_context(state)

    utilis = (None, 0.0, 1.149999, 1.15, 1.749999, 1.75, 2.999999, 3.0, math.inf)
    for util in utilis:
        assert shear_severity_band(util) == legacy._shear_severity_band(util)
        assert severe_shear_failure(util) == legacy._severe_shear_failure(util)

    print("PASS: Inputs recommendation support matches the frozen legacy behavior.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
