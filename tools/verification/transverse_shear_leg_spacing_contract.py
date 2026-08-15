"""Runtime-to-Design-Brain contract for transverse shear-link leg spacing."""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from application.contracts.design_brain import EngineeringInputSnapshot
from inputs_application.v2_engineering_calculation_adapter import (
    _beam_inputs_from_snapshot,
    _v2_api,
)
from inputs_v2.application.candidate_evaluation import (
    complete_compliance,
    compliance_rejection_codes,
)


def _inputs(*, width: float, depth: float, cover_side: float, legs: int):
    snapshot = EngineeringInputSnapshot(
        geometry={"b": width, "D": depth, "L": 2000.0, "sec_shape": "RECT"},
        materials={"fc": 40.0, "fsy": 500.0},
        reinforcement={
            "bot_row_1_bars": 3,
            "bot_row_1_dia": 10,
            "cover_bot": 40.0,
            "cover_top": 40.0,
            "cover_side": cover_side,
            "top_bars": 2,
            "db_top": 10,
            "lig_d": 10,
            "lig_legs": legs,
            "s_lig": 200.0,
        },
        design_actions={"Mu": 0.0, "Vu": 100.0},
    )
    value, _, _ = _beam_inputs_from_snapshot(snapshot, _v2_api(), revision=1)
    return value


def main() -> int:
    api = _v2_api()
    passing = _inputs(width=450.0, depth=825.0, cover_side=40.0, legs=2)
    assert passing.side_cover_mm == 40.0
    pass_result = api["EngineeringCalculator"]().calculate(passing)
    pass_shear = pass_result.families["shear"]
    assert pass_shear["transverse_leg_centres_mm"] == (45.0, 405.0)
    assert pass_shear["transverse_max_leg_spacing_mm"] == 360.0
    assert pass_shear["transverse_spacing_limit_mm"] == 600.0
    assert pass_shear["transverse_minimum_even_legs"] == 2
    assert pass_shear["transverse_spacing_ok"] is True

    failing = _inputs(width=690.0, depth=300.0, cover_side=40.0, legs=2)
    fail_result = api["EngineeringCalculator"]().calculate(failing)
    fail_shear = fail_result.families["shear"]
    assert fail_shear["transverse_max_leg_spacing_mm"] == 600.0
    assert fail_shear["transverse_spacing_limit_mm"] == 300.0
    # Three-leg cages are now an explicitly supported, topology-verified
    # arrangement; the minimum fitted count is therefore three, not the old
    # even-only four-leg fallback.
    assert fail_shear["transverse_minimum_even_legs"] == 3
    assert fail_shear["transverse_spacing_ok"] is False
    assert complete_compliance(fail_result) is False
    assert "transverse_shear_leg_spacing_failed" in compliance_rejection_codes(
        fail_result
    )

    # The theoretical minimum count is three, but this particular cage aligns
    # its internal leg with the longitudinal layout and leaves a 310 mm bay.
    # Four legs are the first fitted arrangement satisfying the 300 mm limit.
    repaired = _inputs(width=690.0, depth=300.0, cover_side=40.0, legs=4)
    repaired_result = api["EngineeringCalculator"]().calculate(repaired)
    assert repaired_result.families["shear"]["transverse_spacing_ok"] is True

    print("transverse_shear_leg_spacing_contract PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
