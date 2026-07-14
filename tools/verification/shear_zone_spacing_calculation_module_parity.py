from __future__ import annotations

import sys
from dataclasses import asdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import shear_zone_spacing
from calculations import shear_zone_spacing as calc_zone


DESIGN_KWARGS = dict(
    L_m=6.0,
    d_mm=650.0,
    D_mm=750.0,
    d_v_mm=600.0,
    b_v_mm=450.0,
    fc_mpa=40.0,
    f_syv_mpa=500.0,
    V_eq_kN=320.0,
    Vuc_kN=120.0,
    theta_v_rad=0.65,
    Asv_mm2=157.08,
    lig_d_mm=10.0,
    legs=2.0,
    is_cantilever=False,
)


def _near(actual: float, expected: float, tol: float = 1e-12) -> None:
    assert abs(float(actual) - float(expected)) <= tol, (actual, expected)


def test_legacy_names_delegate_to_calculation_module() -> None:
    assert shear_zone_spacing.ZoneSpacingSegment is calc_zone.ZoneSpacingSegment
    assert shear_zone_spacing.ZoneSpacingDesign is calc_zone.ZoneSpacingDesign
    assert shear_zone_spacing.asv_over_s_required_mm is calc_zone.asv_over_s_required_mm
    assert shear_zone_spacing.asv_min_over_s_mm is calc_zone.asv_min_over_s_mm
    assert shear_zone_spacing.code_s_max_mm is calc_zone.code_s_max_mm
    assert shear_zone_spacing.practical_s_min_mm is calc_zone.practical_s_min_mm
    assert shear_zone_spacing.snap_spacing_down_mm is calc_zone.snap_spacing_down_mm
    assert shear_zone_spacing.compute_zoned_shear_spacing is calc_zone.compute_zoned_shear_spacing


def test_scalar_helper_contracts() -> None:
    _near(calc_zone.asv_over_s_required_mm(320.0, 120.0, 500.0, 600.0, 1.0), 0.6666666666666666)
    _near(calc_zone.asv_min_over_s_mm(40.0, 450.0, 500.0), 0.4553679830642467)
    _near(calc_zone.code_s_max_mm(650.0), 487.5)
    _near(calc_zone.practical_s_min_mm(10.0), 25.0)
    _near(calc_zone.snap_spacing_down_mm(183.7, 25.0, 25.0, 500.0), 175.0)


def test_zoned_shear_spacing_contract() -> None:
    pure_design = calc_zone.compute_zoned_shear_spacing(**DESIGN_KWARGS)
    legacy_design = shear_zone_spacing.compute_zoned_shear_spacing(**DESIGN_KWARGS)
    assert pure_design is not None
    assert legacy_design is not None
    assert pure_design == legacy_design

    segments = [asdict(segment) for segment in pure_design.segments]
    assert segments == [
        {
            "x0_m": 0.0,
            "x1_m": 0.8999999999999999,
            "label": "Zone 1",
            "s_mm": 300.0,
            "asv_over_s_req_max": 0.5068029327557843,
            "color": "rgba(200,45,45,0.55)",
        },
        {
            "x0_m": 0.8999999999999999,
            "x1_m": 2.3,
            "label": "Zone 2",
            "s_mm": 300.0,
            "asv_over_s_req_max": 0.5068029327557843,
            "color": "rgba(255,152,0,0.50)",
        },
        {
            "x0_m": 2.3,
            "x1_m": 3.7,
            "label": "Zone 3",
            "s_mm": 300.0,
            "asv_over_s_req_max": 0.5068029327557843,
            "color": "rgba(46,125,50,0.45)",
        },
        {
            "x0_m": 3.7,
            "x1_m": 5.1,
            "label": "Zone 2",
            "s_mm": 300.0,
            "asv_over_s_req_max": 0.5068029327557843,
            "color": "rgba(255,152,0,0.50)",
        },
        {
            "x0_m": 5.1,
            "x1_m": 6.0,
            "label": "Zone 1",
            "s_mm": 300.0,
            "asv_over_s_req_max": 0.5068029327557843,
            "color": "rgba(200,45,45,0.55)",
        },
    ]
    assert pure_design.summary_lines == (
        "0\u2013900 mm & mirror (support): 2 legs @ 300 mm",
        "900 mm\u2013$L/2$ & mirror (shear span): 2 legs @ 300 mm",
        "Midspan band: 2 legs @ 300 mm",
    )
    assert pure_design.warnings == ()
    _near(pure_design.s_max_code_mm, 487.5)
    _near(pure_design.s_min_practical_mm, 25.0)
    assert pure_design.envelope_kind == "ss_udl"
    _near(pure_design.legs, 2.0)


def test_no_link_case_contract() -> None:
    assert calc_zone.compute_zoned_shear_spacing(**{**DESIGN_KWARGS, "legs": 1.0}) is None
    assert calc_zone.compute_zoned_shear_spacing(**{**DESIGN_KWARGS, "Asv_mm2": 0.0}) is None


def main() -> int:
    test_legacy_names_delegate_to_calculation_module()
    test_scalar_helper_contracts()
    test_zoned_shear_spacing_contract()
    test_no_link_case_contract()
    print("shear_zone_spacing_calculation_module_parity: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
