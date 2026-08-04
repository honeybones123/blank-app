"""Parity lock for the Inputs recommendation cache fingerprint."""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import inputs_page_app_contract_bridge as legacy
from inputs_application.recommendation_cache import recommendation_cache_fingerprint


def main() -> int:
    states = (
        {},
        {"sec_shape": "RECT", "b": 400.0, "D": 600.0},
        {"sec_shape": "T", "bw": 250.0, "uls_Mstar": 350.0},
        {"design_optimisation_goal": "minimum_weight", "lig_legs": 4, "s_lig": 175.0},
    )
    for state in states:
        assert recommendation_cache_fingerprint(state) == legacy._recommendation_cache_fingerprint(state)
    print("PASS: Inputs recommendation cache fingerprint matches the frozen legacy behavior.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
