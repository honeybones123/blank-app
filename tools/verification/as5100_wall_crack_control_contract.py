"""Executable contract checks for AS 5100.5:2017 Clause 11.7.2."""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from application.contracts.concrete_crack_shrinkage import (  # noqa: E402
    AS5100WallCrackControlInput,
    CrackControlMethod,
)
from calculations.concrete_crack_shrinkage_methods import dispatch_crack_control  # noqa: E402


def main() -> None:
    general = dispatch_crack_control(
        CrackControlMethod.AS5100_WALL,
        AS5100WallCrackControlInput(
            wall_thickness_mm=600.0,
            provided_horizontal_area_per_face_mm2_per_m=2_000.0,
            provided_vertical_spacing_mm=300.0,
        ),
    )
    assert general.reference.clause == "11.7.2"
    assert general.calculation_thickness_per_face_mm == 250.0
    assert general.required_ratio == 0.008
    assert general.required_area_per_face_mm2_per_m == 2_000.0
    assert general.maximum_spacing_mm == 300.0
    assert general.passes is True

    base = dispatch_crack_control(
        CrackControlMethod.AS5100_WALL,
        AS5100WallCrackControlInput(
            wall_thickness_mm=600.0,
            in_base_zone=True,
            provided_horizontal_area_per_face_mm2_per_m=2_750.0,
            provided_vertical_spacing_mm=150.0,
        ),
    )
    assert base.required_ratio == 0.011
    assert base.required_area_per_face_mm2_per_m == 2_750.0
    assert base.maximum_spacing_mm == 150.0
    assert base.passes is True

    thin = dispatch_crack_control(
        CrackControlMethod.AS5100_WALL,
        AS5100WallCrackControlInput(wall_thickness_mm=300.0),
    )
    assert thin.calculation_thickness_per_face_mm == 150.0
    assert thin.required_area_per_face_mm2_per_m == 1_200.0

    print("PASS: AS 5100.5:2017 Clause 11.7.2 wall crack-control contract")


if __name__ == "__main__":
    main()
