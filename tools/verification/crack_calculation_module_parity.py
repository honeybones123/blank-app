from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import crack_page
import crack_checks_helpers
import crack_core
from calculations import bending
from calculations import crack_control


def _near(actual: float, expected: float, tol: float = 1e-12) -> None:
    assert abs(float(actual) - float(expected)) <= tol, (actual, expected)


def test_legacy_page_names_delegate_to_shared_module() -> None:
    assert crack_page.table_sigma_max_A is crack_control.table_sigma_max_A
    assert crack_page.table_sigma_max_B is crack_control.table_sigma_max_B
    assert crack_page.calc_eps_diff is crack_control.calc_eps_diff
    assert crack_page.calc_sr_max is crack_control.calc_sr_max
    assert crack_page._nearest_key is crack_control._nearest_key
    assert crack_page.average_active_bar_spacing_mm is crack_control.average_active_bar_spacing_mm
    assert crack_page.microstrain_to_strain is crack_control.microstrain_to_strain
    assert crack_page.compute_crack_control_values is crack_control.compute_crack_control_values
    assert crack_page.bar_area_mm2 is bending.bar_area_mm2
    assert crack_core.compute_crack_control_values is crack_control.compute_crack_control_values
    assert crack_checks_helpers.pick_governing_check_row is crack_control.pick_governing_check_row
    checks_source = Path(crack_checks_helpers.__file__).read_text(encoding="utf-8")
    assert "def pick_governing_check_row(" not in checks_source
    core_source = Path(crack_core.__file__).read_text(encoding="utf-8")
    compute_source = core_source.split("def compute_crack_results", 1)[1].split(
        "def build_crack_report", 1
    )[0]
    assert "compute_crack_control_values(" in compute_source
    assert "sigma_table_A = table_sigma_max_A(" not in compute_source
    assert "fct_eff = 0.6 * math.sqrt" not in compute_source
    assert "sr_max = calc_sr_max(" not in compute_source
    page_source = Path(crack_page.__file__).read_text(encoding="utf-8")
    render_source = page_source.split("def render_crack(", 1)[1].split(
        "def render_crack_control", 1
    )[0]
    assert "compute_crack_control_values(" in render_source
    assert "sigma_table_A = table_sigma_max_A(" not in render_source
    assert "fct_eff = 0.6 * math.sqrt" not in render_source
    assert "sr_max = calc_sr_max(" not in render_source
    assert "rho_eff = Ast / Aceff" not in render_source
    assert "bar_area_mm2(3, 20.0)" in render_source
    assert "active_spacing = average_active_bar_spacing_mm(spacing_vals)" in render_source
    assert "eps_cs = microstrain_to_strain(eps_cs_micro)" in render_source
    assert "3 * math.pi * 20.0**2 / 4.0" not in render_source
    assert "sum(float(v) for v in spacing_vals)" not in render_source
    assert "eps_cs = eps_cs_micro * 1e-6" not in render_source


def test_table_lookup_contracts() -> None:
    assert crack_control.table_sigma_max_A(20, 0.3) == 195
    assert crack_control.table_sigma_max_A(21, 0.31) == 195
    assert crack_control.table_sigma_max_B(200, 0.3) == 225
    assert crack_control.table_sigma_max_B(210, 0.39) == 300
    assert crack_control._nearest_key({10: "a", 20: "b", 40: "c"}, 27) == 20


def test_direct_crack_formula_contracts() -> None:
    _near(crack_control.average_active_bar_spacing_mm([150.0, "200", 250]), 200.0)
    assert crack_control.average_active_bar_spacing_mm([]) is None
    assert crack_control.average_active_bar_spacing_mm(None) is None
    _near(crack_control.microstrain_to_strain(300.0), 0.0003)

    eps = crack_control.calc_eps_diff(
        sigma_sr=150.0,
        Es=200000.0,
        fct_eff=3.0,
        rho_eff=0.015,
        ne=20.0,
        eps_cs=0.0003,
    )
    _near(eps, 0.00045)
    assert crack_control.calc_eps_diff(150.0, 200000.0, 3.0, 0.0, 20.0, 0.0003) == 0.0

    sr = crack_control.calc_sr_max(c_mm=40.0, db_mm=20.0, rho_eff=0.015, k1=0.8, k2=0.5)
    _near(sr, 296.0)
    assert crack_control.calc_sr_max(40.0, 20.0, 0.0, 0.8, 0.5) == 0.0


def test_crack_control_value_bundle_contract() -> None:
    result = crack_control.compute_crack_control_values(
        b=450.0,
        D=750.0,
        c=40.0,
        db=20.0,
        spacing=200.0,
        Ast=1200.0,
        fc=40.0,
        Ec=30000.0,
        Es=200000.0,
        fsy=500.0,
        wmax_choice=0.3,
        member_type="Primarily flexure",
        sigma_sr=180.0,
        phi_ce=2.0,
        eps_cs=300e-6,
        k1=0.8,
        k2=0.5,
        crack_tension_face="bottom",
    )
    expected = {
        "d_eff": 700.0,
        "height_eff": 50.0,
        "Aceff": 22500.0,
        "rho_eff": 0.05333333333333334,
        "sigma_table_A": 195,
        "sigma_table_B": 225,
        "sigma_table_combined": 225,
        "sigma_08fsy": 400.0,
        "sigma_allow_table": 225,
        "utilisation_table": 0.8,
        "passes_table": True,
        "fct_eff": 3.794733192202055,
        "ne": 20.0,
        "eps_diff": 0.0007588622664065111,
        "sr_max": 181.0,
        "w_calc": 0.13735407021957852,
        "utilisation_w": 0.4578469007319284,
        "passes_w": True,
    }
    assert result.keys() == expected.keys()
    for key, expected_value in expected.items():
        if isinstance(expected_value, float):
            _near(result[key], expected_value)
        else:
            assert result[key] == expected_value

    tension = crack_control.compute_crack_control_values(
        b=450.0,
        D=750.0,
        c=45.0,
        db=16.0,
        spacing=120.0,
        Ast=900.0,
        fc=32.0,
        Ec=27000.0,
        Es=200000.0,
        fsy=500.0,
        wmax_choice=0.2,
        member_type="Primarily tension",
        sigma_sr=120.0,
        phi_ce=1.5,
        eps_cs=250e-6,
        k1=0.8,
        k2=0.5,
        crack_tension_face="top",
    )
    assert tension["sigma_table_combined"] == tension["sigma_table_A"]
    _near(tension["d_eff"], 53.0)


def test_crack_core_state_adapter_output_contract() -> None:
    params = {
        "b_crack": 450.0,
        "b": 300.0,
        "D": 750.0,
        "cover_bot": 40.0,
        "db_bot": 20.0,
        "s_bar_bot": 200.0,
        "Ast_bot": 1200.0,
        "fc": 40.0,
        "Ec": 30000.0,
        "Es": 200000.0,
        "fsy": 500.0,
        "wmax_char_limit": 0.3,
        "crack_member_type": "Primarily flexure",
        "sigma_sr": 180.0,
        "phi_cc_t": 2.0,
        "eps_cs_total_micro": 300.0,
        "crack_k1": 0.8,
        "crack_k2": 0.5,
        "sec_shape": "RECT",
    }
    updates: dict = {}
    original_get_param = crack_core.get_param
    original_update_results = crack_core.update_results
    original_resolve_design_actions = crack_core.resolve_design_actions

    def fake_get_param(name: str, default=None):
        return params.get(name, default)

    def fake_update_results(**kwargs):
        updates.update(kwargs)

    try:
        crack_core.get_param = fake_get_param
        crack_core.update_results = fake_update_results
        crack_core.resolve_design_actions = lambda: {"SLS_M_signed": 50.0, "Mu_signed": 50.0}
        out = crack_core.compute_crack_results(publish=False)
    finally:
        crack_core.get_param = original_get_param
        crack_core.update_results = original_update_results
        crack_core.resolve_design_actions = original_resolve_design_actions

    expected = {
        "sigma_sr": 180.0,
        "sigma_allow_table": 225,
        "w_calc": 0.13735407021957852,
        "wmax_char": 0.3,
        "passes_table": True,
        "passes_w": True,
        "crack_width": 0.13735407021957852,
        "crack_sr_max_mm": 181.0,
        "crack_utilisation": 0.4578469007319284,
        "crack_tension_face": "bottom",
        "crack_active_bar_count": 0.0,
        "crack_active_bar_dias": [],
        "crack_active_bar_spacing_mm": [],
        "crack_tension_width_mm": 450.0,
        "crack_Ast_active_mm2": 1200.0,
        "crack_flange_participation_used": False,
        "crack_web_participation_used": True,
        "crack_detailing_warning": "",
        "active_tension_face": "bottom",
        "active_tension_Ast_mm2": 1200.0,
        "active_tension_width_mm": 450.0,
        "active_tension_flange_participating": False,
        "active_tension_warning": "",
    }
    assert out.keys() == expected.keys()
    assert updates == out
    for key, expected_value in expected.items():
        if isinstance(expected_value, float):
            _near(out[key], expected_value)
        else:
            assert out[key] == expected_value


def test_governing_check_row_selection_contract() -> None:
    rows = [
        {"uid": "info", "util": "999.0", "is_informational": True},
        {"uid": "missing", "util": "—"},
        {"uid": "low", "util": "0.40"},
        {"uid": "bad", "util": "not-a-number"},
        {"uid": "governing", "util": "1.20"},
        {"uid": "mid", "util": 0.95},
    ]
    assert crack_control.pick_governing_check_row(rows) == {"uid": "governing", "util": "1.20"}
    assert crack_checks_helpers.pick_governing_check_row(rows) == {"uid": "governing", "util": "1.20"}
    assert crack_control.pick_governing_check_row([{"uid": "info", "util": "2.0", "is_informational": True}]) is None
    assert crack_control.pick_governing_check_row(None) is None


def main() -> int:
    test_legacy_page_names_delegate_to_shared_module()
    test_table_lookup_contracts()
    test_direct_crack_formula_contracts()
    test_crack_control_value_bundle_contract()
    test_crack_core_state_adapter_output_contract()
    test_governing_check_row_selection_contract()
    print("crack_calculation_module_parity: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
