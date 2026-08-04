from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import creep
import shrinkage
from calculations import creep_shrinkage


def _near(actual: float, expected: float, tol: float = 1e-12) -> None:
    assert abs(float(actual) - float(expected)) <= tol, (actual, expected)


def test_creep_page_names_delegate_to_shared_module() -> None:
    assert creep._closest_fc_row is creep_shrinkage.creep_closest_fc_row
    assert creep._closest_th is creep_shrinkage.creep_closest_th
    assert creep.creep_alpha2_from_th is creep_shrinkage.creep_alpha2_from_th
    assert creep.calc_k2_creep is creep_shrinkage.calc_k2_creep
    assert creep.calc_k3 is creep_shrinkage.calc_k3
    assert creep.calc_k4 is creep_shrinkage.calc_k4
    assert creep.calc_k5 is creep_shrinkage.calc_k5
    assert creep.calc_k6 is creep_shrinkage.calc_k6
    assert creep.creep_coefficient_value is creep_shrinkage.creep_coefficient_value
    assert creep.sustained_creep_stress_mpa is creep_shrinkage.sustained_creep_stress_mpa
    assert creep.creep_strain_values is creep_shrinkage.creep_strain_values
    assert creep.basic_creep_coeff is creep_shrinkage.basic_creep_coeff
    assert creep.final_creep_coeff_table is creep_shrinkage.final_creep_coeff_table
    assert creep.exposed_perimeter_geometry_values is creep_shrinkage.exposed_perimeter_geometry_values


def test_shrinkage_page_names_delegate_to_shared_module() -> None:
    assert (
        shrinkage.autogenous_shrinkage_final_from_current
        is creep_shrinkage.autogenous_shrinkage_final_from_current
    )
    assert shrinkage._closest_fc_row is creep_shrinkage.shrinkage_closest_fc_row
    assert shrinkage._closest_th is creep_shrinkage.shrinkage_closest_th
    assert shrinkage._shrinkage_eps_final is creep_shrinkage.shrinkage_eps_final
    assert shrinkage.calc_k1_shrinkage is creep_shrinkage.calc_k1_shrinkage
    assert shrinkage.calc_eps_cse is creep_shrinkage.calc_eps_cse
    assert shrinkage.exposed_perimeter_geometry_values is creep_shrinkage.exposed_perimeter_geometry_values
    assert shrinkage.shrinkage_total_values is creep_shrinkage.shrinkage_total_values
    creep_source = Path(creep.__file__).read_text(encoding="utf-8")
    shrinkage_source = Path(shrinkage.__file__).read_text(encoding="utf-8")
    assert creep_source.count("geometry_values = exposed_perimeter_geometry_values(") >= 2
    assert shrinkage_source.count("geometry_values = exposed_perimeter_geometry_values(") >= 2
    assert creep_source.count("creep_strain = creep_strain_values(") >= 2
    assert shrinkage_source.count("shrinkage_total = shrinkage_total_values(") >= 2
    assert "th_raw = 2.0 * Ag / ue if ue > 0 else 0.0" not in creep_source
    assert "th_raw = 2.0 * Ag / ue if ue > 0 else 0.0" not in shrinkage_source
    assert "eps_cc = phi_cc_t * sigma0 / Ec" not in creep_source
    assert "eps_cc_micro = eps_cc * 1e6" not in creep_source
    assert "phi_cc_t = k2 * k3 * k4 * k5 * k6 * phi_cc_b" not in creep_source
    assert "sigma0 = stress_ratio * fc" not in creep_source
    assert "sigma0 = sustained_sigma_cs if sustained_sigma_cs > 0 else (stress_ratio * fc)" not in creep_source
    assert "alpha2 = 1.0 + 1.12 * math.exp(-0.008 * th_table)" not in creep_source
    assert "eps_csd_t = k1 * eps_csd_final" not in shrinkage_source
    assert "eps_cs_total = eps_cse + eps_csd_t" not in shrinkage_source
    assert "eps_cse / (1.0 - math.exp(-0.04 * t_days))" not in shrinkage_source


def test_creep_table_and_factor_contracts() -> None:
    en_dash = chr(8211)
    assert creep_shrinkage.exposed_perimeter_geometry_values(
        300.0,
        600.0,
        "Beam – three faces exposed",
    ) == {
        "Ag": 180000.0,
        "ue": 1500.0,
        "th_raw": 240.0,
    }
    assert creep_shrinkage.exposed_perimeter_geometry_values(
        300.0,
        600.0,
        "Column – four faces exposed",
    ) == {
        "Ag": 180000.0,
        "ue": 1800.0,
        "th_raw": 200.0,
    }
    assert creep_shrinkage.creep_closest_fc_row(37.0) == 40
    assert creep_shrinkage.creep_closest_th(155.0) == 200
    _near(creep_shrinkage.creep_alpha2_from_th(200.0), 1.226124100154014)
    _near(creep_shrinkage.basic_creep_coeff(37.0), 2.8)
    _near(
        creep_shrinkage.final_creep_coeff_table(
            37.0,
            "Temperate inland environment",
            155.0,
        ),
        2.23,
    )
    _near(creep_shrinkage.calc_k2_creep(365.0, 200.0), 0.967373601708651)
    _near(creep_shrinkage.calc_k3(28.0), 0.6232392754447333)
    _near(creep_shrinkage.calc_k4("Temperate inland environment"), 0.6)
    _near(creep_shrinkage.calc_k5(65.0, 200.0, 0.6), 0.9854523452854702)
    _near(creep_shrinkage.calc_k6(0.6), 1.2523227161918642)
    _near(creep_shrinkage.calc_k6(0.45), 1.0)
    _near(
        creep_shrinkage.creep_coefficient_value(
            k2=0.9,
            k3=0.8,
            k4=0.7,
            k5=0.6,
            k6=0.5,
            phi_cc_b=4.0,
        ),
        0.6048,
    )
    _near(
        creep_shrinkage.sustained_creep_stress_mpa(
            sustained_sigma_cs_mpa=None,
            stress_ratio=0.25,
            fc_mpa=40.0,
        ),
        10.0,
    )
    _near(
        creep_shrinkage.sustained_creep_stress_mpa(
            sustained_sigma_cs_mpa=8.5,
            stress_ratio=0.25,
            fc_mpa=40.0,
        ),
        8.5,
    )
    assert creep_shrinkage.creep_strain_values(2.0, 6.0, 30000.0) == {
        "eps_cc": 0.0004,
        "eps_cc_micro": 400.0,
    }
    assert creep_shrinkage.creep_strain_values(2.0, 6.0, 0.0) == {
        "eps_cc": 0.0,
        "eps_cc_micro": 0.0,
    }


def test_shrinkage_table_and_factor_contracts() -> None:
    assert creep_shrinkage.shrinkage_closest_fc_row(37.0) == 40
    assert creep_shrinkage.shrinkage_closest_th(155.0) == 200
    _near(
        creep_shrinkage.shrinkage_eps_final(
            37.0,
            "Temperate inland environment",
            155.0,
        ),
        0.00053,
    )
    _near(creep_shrinkage.calc_k1_shrinkage(365.0, 200.0), 0.979469462525669)
    _near(creep_shrinkage.calc_eps_cse(40.0, 365.0), 0.00011499994751944679)
    _near(
        creep_shrinkage.autogenous_shrinkage_final_from_current(
            0.00011499994751944679,
            365.0,
        ),
        0.000115,
    )
    _near(creep_shrinkage.autogenous_shrinkage_final_from_current(0.0001, 0.0), 0.0001)
    assert creep_shrinkage.shrinkage_total_values(0.5, 100e-6, 400e-6) == {
        "eps_csd_t": 0.0002,
        "eps_cs_total": 0.00030000000000000003,
        "eps_cs_total_micro": 300.0,
    }


def main() -> int:
    test_creep_page_names_delegate_to_shared_module()
    test_shrinkage_page_names_delegate_to_shared_module()
    test_creep_table_and_factor_contracts()
    test_shrinkage_table_and_factor_contracts()
    print("creep_shrinkage_calculation_module_parity: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
