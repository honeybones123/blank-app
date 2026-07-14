from __future__ import annotations

import math
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import beam_analysis
import bending_core
import crack_core
import deflection_core
import shear_core
import uls_flexure


def _near(actual: float, expected: float, tol: float = 1e-6) -> None:
    assert abs(float(actual) - float(expected)) <= tol, (actual, expected)


def test_beam_analysis_simple_support_contract() -> None:
    model = beam_analysis.BeamModel(
        length_m=10.0,
        supports=[
            beam_analysis.Support(0.0, "pinned"),
            beam_analysis.Support(10.0, "roller"),
        ],
        point_loads=[beam_analysis.PointLoad(5.0, 10.0)],
    )
    result = beam_analysis.solve_beam_model(model, n_points=101)
    _near(result.reactions["R@0"], 5.0)
    _near(result.reactions["R@10"], 5.0)
    _near(max(result.M), 25.0)
    assert result.metadata["mode"] == "two_support"
    validation = beam_analysis.validate_beam_result(result)
    assert validation["all_finite_x"] is True
    assert validation["all_finite_V"] is True
    assert validation["all_finite_M"] is True
    assert validation["supports_inside_or_at_ends"] is True


def test_bending_core_geometry_contract() -> None:
    assert bending_core.hogging_tension_effective_depth_mm(750, 60) == 690
    assert bending_core.hogging_tension_effective_depth_mm(750, 690) == 690
    assert bending_core.hogging_tension_effective_depth_mm(0, 50) == 50

    one_row = bending_core._layout_bars_in_rows(3, 450, 40, 20, 60)
    assert len(one_row) == 3
    assert all(row_index == 0 for _, row_index in one_row)

    split_rows = bending_core._layout_bars_in_rows(6, 260, 45, 20, 80)
    assert len(split_rows) == 6
    assert {row_index for _, row_index in split_rows} == {0, 1}


def test_shear_core_formula_contract() -> None:
    _near(shear_core.cot(math.pi / 4.0), 1.0)
    asv_per_s = shear_core.required_asv_per_s(
        [200.0],
        phi=0.7,
        Vuc=100.0,
        fy=500.0,
        dv=600.0,
    )[0]
    _near(asv_per_s, 0.6190476190476191)

    assert shear_core.spacing_from_demand(
        Vi_kN=50.0,
        phi=0.7,
        Vuc_kN=100.0,
        fy_mpa=500.0,
        dv_mm=600.0,
        Asv_mm2=200.0,
        D_mm=750.0,
        s_min_mm=100.0,
    ) == 500.0


def test_deflection_core_report_shape_contract() -> None:
    report = deflection_core.build_deflection_report({})
    assert report["module_title"] == "Deflection (SLS)"
    assert isinstance(report["summary"], list)
    assert all(isinstance(row, tuple) and len(row) == 2 for row in report["summary"])
    assert isinstance(report["tabs"], list)
    assert report["tabs"]


def test_crack_core_compute_contract() -> None:
    state = {
        "b": 300.0,
        "b_crack": 300.0,
        "D": 600.0,
        "cover_bot": 40.0,
        "db_bot": 20.0,
        "s_bar_bot": 200.0,
        "Ast_bot": 1200.0,
        "fc": 40.0,
        "Ec": 30000.0,
        "Es": 200000.0,
        "fsy": 500.0,
        "sec_shape": "RECT",
        "sigma_sr": 150.0,
        "phi_cc_t": 2.0,
        "eps_cs_total_micro": 300.0,
        "crack_k1": 0.8,
        "crack_k2": 0.5,
        "wmax_char_limit": 0.3,
        "crack_member_type": "Primarily flexure",
    }
    captured: dict[str, object] = {}
    original_get_param = crack_core.get_param
    original_update_results = crack_core.update_results
    original_resolve_design_actions = crack_core.resolve_design_actions
    try:
        crack_core.get_param = lambda key, default=None: state.get(key, default)
        crack_core.update_results = lambda **kwargs: captured.update(kwargs)
        crack_core.resolve_design_actions = lambda: {"SLS_M_signed": 50.0}
        out = crack_core.compute_crack_results(publish=False)
    finally:
        crack_core.get_param = original_get_param
        crack_core.update_results = original_update_results
        crack_core.resolve_design_actions = original_resolve_design_actions

    for key in (
        "sigma_sr",
        "sigma_allow_table",
        "w_calc",
        "wmax_char",
        "passes_table",
        "passes_w",
        "crack_width",
        "crack_utilisation",
        "crack_tension_face",
    ):
        assert key in out
        assert key in captured
    assert out["sigma_sr"] == 150.0
    assert out["wmax_char"] == 0.3
    assert out["crack_tension_face"] == "bottom"
    assert isinstance(out["passes_table"], bool)
    assert isinstance(out["passes_w"], bool)
    assert float(out["w_calc"]) >= 0.0


def test_uls_flexure_wrapper_contract() -> None:
    exported = {name for name in dir(uls_flexure) if not name.startswith("_")}
    assert exported, "uls_flexure wrapper should expose section_props.uls_flexure API"


def main() -> int:
    test_beam_analysis_simple_support_contract()
    test_bending_core_geometry_contract()
    test_shear_core_formula_contract()
    test_deflection_core_report_shape_contract()
    test_crack_core_compute_contract()
    test_uls_flexure_wrapper_contract()
    print("engineering_core_contract: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
