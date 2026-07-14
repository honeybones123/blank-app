from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import shear_core
import shear_checks_helpers
from calculations import shear


def _near(actual: float, expected: float, tol: float = 1e-12) -> None:
    assert abs(float(actual) - float(expected)) <= tol, (actual, expected)


def test_required_asv_per_s_contract() -> None:
    _near(shear.cotangent(np.pi / 4.0), 1.0)
    _near(shear.stirrup_area_mm2(2, 10.0), 157.07963267948966)
    _near(shear.stirrup_area_mm2(3, 12.0), 339.29200658769764)
    assert shear.stirrup_area_mm2(1, 10.0) == 0.0
    _near(shear.approximate_concrete_tension_area_mm2(450.0, 750.0), 168750.0)
    _near(shear.effective_shear_depth_mm(750.0, 690.0), 621.0)
    _near(
        shear.minimum_shear_reinforcement_asv_per_s(40.0, 450.0, 500.0),
        0.45536798306424665,
    )
    _near(shear.maximum_shear_spacing_mm(750.0), 500.0)
    _near(shear.maximum_shear_spacing_mm(400.0), 300.0)
    _near(shear.maximum_shear_spacing_mm(0.0), 500.0)
    display_scalars = shear.shear_check_display_scalars(
        T_star_kNm=12.0,
        D_mm=750.0,
        d_mm=690.0,
        fc_mpa=100.0,
        Vuc_kN=300.0,
        Vus_kN=450.0,
        P_v_kN=6.0,
        phi=0.75,
        V_eq_kN=220.0,
    )
    assert display_scalars == {
        "T_star_Nmm": 12000000.0,
        "dv_1": 540.0,
        "dv_2": 621.0,
        "sqrt_fc_limited": 8.0,
        "Vu_total_kN": 756.0,
        "phi_Vu": 567.0,
        "shear_ok": True,
    }
    _near(shear.duct_area_mm2(2.0, 80.0), 10053.088)
    torsion_geometry = shear.torsion_section_geometry_values(450.0, 750.0)
    assert torsion_geometry == {
        "b_used": 450.0,
        "D_used": 750.0,
        "A_cp": 337500.0,
        "u_c": 2400.0,
        "Ao": 303750.0,
        "uh": 2240.0,
        "A_oh": 291100.0,
    }
    _near(shear.aggregate_size_factor_kdg(40.0, 10.0), 1.2307692307692308)
    _near(shear.aggregate_size_factor_kdg(40.0, 20.0), 1.0)
    _near(shear.aggregate_size_factor_kdg(70.0, 20.0), 2.0)
    mcft = shear.mcft_kv_theta_values(
        use_general_kv=True,
        fc_mpa=40.0,
        d_g_mm=20.0,
        eps_x=0.0005709085577731116,
        Asv_mm2=157.07963267948966,
        s_mm=200.0,
        b_v_mm=450.0,
        f_syv_mpa=500.0,
        d_v_mm=621.0,
    )
    assert mcft["low_stirrup_ratio"] is False
    _near(mcft["Asv_over_s"], 0.7853981633974483)
    _near(mcft["Asv_min_over_s"], 0.45536798306424665)
    _near(mcft["k_dg"], 1.0)
    _near(mcft["k_v"], 0.21547511731044916)
    _near(mcft["theta_v_deg"], 32.99635990441178)
    web_crushing = shear.web_crushing_fallback_values(
        V_star_kN=220.0,
        T_star_kNm=12.0,
        uh_mm=2240.0,
        A_oh_mm2=291100.0,
        b_v_mm=450.0,
        d_v_mm=621.0,
        phi=0.75,
        Vu_max_kN=2808.0341711114456,
    )
    expected_web_crushing = {
        "Vu_max_N": 2808034.1711114454,
        "V_star_N": 220000.0,
        "T_star_Nmm": 12000000.0,
        "term_V": 0.7872606906423332,
        "term_T": 0.18659325129278823,
        "LHS": 0.8090713420080191,
        "RHS": 7.536323593965231,
        "web_ok": True,
    }
    assert web_crushing.keys() == expected_web_crushing.keys()
    for key, expected_value in expected_web_crushing.items():
        if isinstance(expected_value, bool):
            assert web_crushing[key] is expected_value
        else:
            _near(web_crushing[key], expected_value)
    strain = shear.longitudinal_strain_fallback_values(
        M_star_kNm=120.0,
        V_star_kN=220.0,
        T_star_kNm=12.0,
        P_v_kN=0.0,
        N_star_kN=0.0,
        d_v_mm=621.0,
        uh_mm=2240.0,
        Ao_mm2=303750.0,
        Es_mpa=200000.0,
        Ec_mpa=30000.0,
        A_st_mm2=1809.5573684677208,
        A_pt_mm2=0.0,
        f_po_mpa=0.0,
        A_ct_mm2=168750.0,
    )
    expected_strain = {
        "M_star_Nmm": 120000000.0,
        "term_M": 193236.71497584542,
        "Vprime_kN": 220.0,
        "Vprime_N": 220000.0,
        "T_star_Nmm": 12000000.0,
        "torsion_N": 42919.50617283951,
        "sqrt_inner": 224147.46041416665,
        "N_star_N": 0.0,
        "A_pt_fpo_N": 0.0,
        "numerator_1": 417384.1753900121,
        "Ep": 195000.0,
        "denom1": 723822947.3870883,
        "eps_x_1": 0.0005766384955004778,
        "V_abs_N": 220000.0,
        "numerator_2": 413236.7149758454,
        "denom2": 10848822947.387089,
        "eps_x_2": 3.80904653878025e-05,
        "use_equation_1": True,
        "eps_x_raw": 0.0005766384955004778,
        "eps_x": 0.0005766384955004778,
    }
    assert strain.keys() == expected_strain.keys()
    for key, expected_value in expected_strain.items():
        if isinstance(expected_value, bool):
            assert strain[key] is expected_value
        else:
            _near(strain[key], expected_value)

    no_prestress_display = shear.nonprestressed_longitudinal_strain_display_values(
        term_M_N=193236.71497584542,
        V_eq_N=220000.0,
        N_star_half_N=0.0,
        Es_mpa=200000.0,
        A_st_mm2=1809.5573684677208,
    )
    assert no_prestress_display == {
        "numerator": 413236.7149758454,
        "denominator": 723822947.3870883,
        "eps_x": 0.0005709085577731116,
    }
    assert shear.nonprestressed_longitudinal_strain_display_values(
        term_M_N=1.0,
        V_eq_N=2.0,
        N_star_half_N=3.0,
        Es_mpa=0.0,
        A_st_mm2=100.0,
    ) == {
        "numerator": 6.0,
        "denominator": 0.0,
        "eps_x": 0.0,
    }

    utilisation = shear.shear_capacity_utilisation_values(
        SimpleNamespace(V_eq=220.0, phi_Vu=567.3024128706963, Vu_max_kN=2808.0341711114456),
        0.75,
    )
    expected_utilisation = {
        "V_eq": 220.0,
        "phi_Vu_cap": 567.3024128706963,
        "Vu_max_kN": 2808.0341711114456,
        "phi_Vu_max_kN": 2106.0256283335843,
        "util": 0.38780021908728246,
        "web_util": 0.10446216657585378,
    }
    assert utilisation.keys() == expected_utilisation.keys()
    for key, expected_value in expected_utilisation.items():
        _near(utilisation[key], expected_value)

    reinforcement_checks = shear.shear_reinforcement_spacing_check_values(
        Asv_mm2=157.07963267948966,
        s_lig_mm=200.0,
        fc_mpa=40.0,
        b_v_mm=450.0,
        f_syv_mpa=500.0,
        D_mm=750.0,
    )
    expected_reinforcement_checks = {
        "Asv_over_s": 0.7853981633974483,
        "Asv_min_over_s": 0.45536798306424665,
        "min_shear_ok": True,
        "max_spacing": 500.0,
        "spacing_ok": True,
    }
    assert reinforcement_checks.keys() == expected_reinforcement_checks.keys()
    for key, expected_value in expected_reinforcement_checks.items():
        if isinstance(expected_value, bool):
            assert reinforcement_checks[key] is expected_value
        else:
            _near(reinforcement_checks[key], expected_value)
    no_spacing = shear.shear_reinforcement_spacing_check_values(
        Asv_mm2=157.07963267948966,
        s_lig_mm=0.0,
        fc_mpa=40.0,
        b_v_mm=450.0,
        f_syv_mpa=500.0,
        D_mm=0.0,
    )
    assert no_spacing["Asv_over_s"] == 0.0
    assert no_spacing["max_spacing"] == 500.0
    assert no_spacing["spacing_ok"] is False

    expected = np.array([0.0, 0.2564102564102564, 0.811965811965812])
    pure = shear.required_asv_per_s(
        [50.0, 120.0, 250.0],
        0.75,
        80.0,
        500.0,
        520.0,
        cot_theta_v=1.2,
    )
    wrapped = shear_core.required_asv_per_s(
        [50.0, 120.0, 250.0],
        0.75,
        80.0,
        500.0,
        520.0,
        cot_theta_v=1.2,
    )
    assert np.allclose(pure, expected)
    assert np.allclose(wrapped, expected)


def test_spacing_from_demand_contract() -> None:
    args = (250.0, 0.75, 80.0, 500.0, 520.0, 157.08, 750.0, 25.0)
    kwargs = {"cot_theta_v": 1.2, "increment_mm": 25.0}
    _near(shear.spacing_from_demand(*args, **kwargs), 175.0)
    _near(shear_core.spacing_from_demand(*args, **kwargs), 175.0)

    max_spacing_args = (50.0, 0.75, 80.0, 500.0, 520.0, 157.08, 750.0, 25.0)
    _near(shear.spacing_from_demand(*max_spacing_args, **kwargs), 500.0)
    _near(shear_core.spacing_from_demand(*max_spacing_args, **kwargs), 500.0)


def test_midspan_spacing_contract() -> None:
    demand = dict(
        V_mid_kN=250.0,
        phi=0.75,
        Vuc_kN=80.0,
        fy_mpa=500.0,
        dv_mm=520.0,
        Asv_mm2=157.08,
        D_mm=750.0,
        s_min_mm=25.0,
        cot_theta_v=1.2,
        increment_mm=25.0,
    )
    assert shear.compute_midspan_spacing_result(**demand) == (175.0, "shear_demand")
    assert shear_core.compute_midspan_spacing_result(**demand) == (175.0, "shear_demand")

    max_spacing = {**demand, "V_mid_kN": 50.0}
    assert shear.compute_midspan_spacing_result(**max_spacing) == (500.0, "max_spacing")
    assert shear_core.compute_midspan_spacing_result(**max_spacing) == (500.0, "max_spacing")


def test_shear_capacity_values_contract() -> None:
    inp = shear_core.ShearInputs(
        b=450.0,
        D=750.0,
        d=690.0,
        fc=40.0,
        fsy=500.0,
        Ec=30000.0,
        Es=200000.0,
        M_star=120.0,
        V_star=220.0,
        T_star=12.0,
        N_star=0.0,
        P_v=0.0,
        phi=0.75,
        sigma_cp=0.0,
        A_st=1809.5573684677208,
        A_pt=0.0,
        f_po=0.0,
        A_ct=168750.0,
        d_g=20.0,
        lig_d=10.0,
        legs=2.0,
        s_lig=200.0,
        use_general_kv=True,
        sum_duct=0.0,
        k_d=0.5,
    )
    values = shear.compute_shear_capacity_values(inp)
    expected = {
        "b_used": 450.0,
        "D_used": 750.0,
        "A_cp": 337500.0,
        "u_c": 2400.0,
        "Ao": 303750.0,
        "uh": 2240.0,
        "A_oh": 291100.0,
        "Tcr_kNm": 99.05587717535248,
        "torsion_required": False,
        "torsion_required_limit": 18.57297697037859,
        "Vt_eq_kN": 0.0,
        "V_eq": 220.0,
        "b_v": 450.0,
        "d_v": 621.0,
        "Asv": 157.07963267948966,
        "f_syv": 500.0,
        "eps_x": 0.0005709085577731116,
        "term_M": 193236.71497584542,
        "sqrt_inner": 220000.0,
        "numerator": 413236.7149758454,
        "k_v": 0.21547511731044916,
        "theta_v_deg": 32.99635990441178,
        "theta_v_rad": 0.5758951215050271,
        "sqrt_fc_limited": 6.324555320336759,
        "Vuc_kN": 380.8300725193045,
        "Vus_kN": 375.5731446416239,
        "Vu_total_kN": 756.4032171609284,
        "phi_Vu": 567.3024128706963,
        "shear_ok": True,
        "Vu_max_kN": 2808.0341711114456,
        "LHS": 0.7872606906423332,
        "RHS": 7.536323593965231,
        "web_ok": True,
    }
    assert values.keys() == expected.keys()
    for key, expected_value in expected.items():
        if isinstance(expected_value, bool):
            assert values[key] is expected_value
        else:
            _near(values[key], expected_value)

    core_result = shear_core.run_shear_calc(inp)
    assert vars(core_result) == values


def test_shear_spacing_truth_contract() -> None:
    expected_provided = {
        "provided_spacing_mm": 200.0,
        "required_spacing_mm": 150.0,
        "effective_spacing_mm": 200.0,
        "governing_spacing_source": "provided",
    }
    assert (
        shear.resolve_shear_spacing_truth(
            provided_spacing_mm=200.0,
            required_spacing_mm=150.0,
            effective_spacing_mm=200.0,
        )
        == expected_provided
    )
    assert (
        shear_checks_helpers.resolve_shear_spacing_truth(
            provided_spacing_mm=200.0,
            required_spacing_mm=150.0,
            effective_spacing_mm=200.0,
        )
        == expected_provided
    )

    assert shear.resolve_shear_spacing_truth(
        provided_spacing_mm=200.0,
        required_spacing_mm=150.0,
        effective_spacing_mm=150.0,
    ) == {
        "provided_spacing_mm": 200.0,
        "required_spacing_mm": 150.0,
        "effective_spacing_mm": 150.0,
        "governing_spacing_source": "required",
    }
    assert shear.resolve_shear_spacing_truth(
        provided_spacing_mm=None,
        required_spacing_mm=150.0,
        effective_spacing_mm=170.0,
    ) == {
        "provided_spacing_mm": None,
        "required_spacing_mm": 150.0,
        "effective_spacing_mm": 170.0,
        "governing_spacing_source": "required",
    }
    assert shear.resolve_shear_spacing_truth(
        provided_spacing_mm=float("nan"),
        required_spacing_mm=None,
        effective_spacing_mm=None,
    ) == {
        "provided_spacing_mm": None,
        "required_spacing_mm": None,
        "effective_spacing_mm": None,
        "governing_spacing_source": None,
    }


def test_final_shear_truth_bundle_completeness_contract() -> None:
    complete = {
        "final_shear_status_source": "stage_2_final",
        "final_shear_truth_resolved": False,
        "published_result_spacing_mm": 175.0,
        "published_result_spacing_meaning": "effective spacing",
    }
    assert shear.session_final_shear_truth_bundle_complete(complete) is True
    assert shear_checks_helpers.session_final_shear_truth_bundle_complete(complete) is True
    assert shear.session_final_shear_truth_bundle_complete({}) is False
    assert shear.session_final_shear_truth_bundle_complete(
        {**complete, "final_shear_status_source": ""}
    ) is False
    assert shear.session_final_shear_truth_bundle_complete(
        {**complete, "final_shear_truth_resolved": "yes"}
    ) is False
    assert shear.session_final_shear_truth_bundle_complete(
        {**complete, "published_result_spacing_mm": None}
    ) is False
    assert shear.session_final_shear_truth_bundle_complete(
        {**complete, "published_result_spacing_meaning": ""}
    ) is False


def test_shear_truth_formatting_contract() -> None:
    assert shear.format_shear_row_util(None) == "—"
    assert shear.format_shear_row_util(float("nan")) == "—"
    assert shear.format_shear_row_util(float("inf")) == "—"
    assert shear.format_shear_row_util("bad") == "—"
    assert shear.format_shear_row_util(0.955) == "0.95"
    assert shear.format_shear_row_util(1.0) == "1.00"
    assert shear_checks_helpers._fmt_row_util(1.0) == "1.00"

    assert shear.shear_truth_status_from_util(None) == "—"
    assert shear.shear_truth_status_from_util(float("nan")) == "—"
    assert shear.shear_truth_status_from_util(0.5) == "PASS"
    assert shear.shear_truth_status_from_util(0.95) == "NEAR LIMIT"
    assert shear.shear_truth_status_from_util(1.0) == "NEAR LIMIT"
    assert shear.shear_truth_status_from_util(1.01) == "FAIL"
    assert shear_checks_helpers._truth_status_from_util(1.01) == "FAIL"


def test_canonical_shear_truth_bundle_contract() -> None:
    state = {
        "s_lig": 200.0,
        "shear_required_spacing_mm": 150.0,
        "shear_effective_spacing_mm": 200.0,
        "shear_util_min": 0.82,
    }
    bundle = {
        "results": SimpleNamespace(
            V_eq=120.0,
            phi_Vu=100.0,
            Vu_max_kN=180.0,
        ),
        "phi": 0.75,
        "inputs": SimpleNamespace(s_lig=175.0),
    }
    zone_payload = {
        "shear_util_min": 0.84,
        "shear_envelope_status": "WARN",
    }
    expected = {
        "provided_spacing_mm": 200.0,
        "effective_spacing_mm": 200.0,
        "required_spacing_mm": 150.0,
        "shear_provided_spacing_mm": 200.0,
        "shear_effective_spacing_mm": 200.0,
        "shear_required_spacing_mm": 150.0,
        "shear_governing_check_name": "Sectional shear capacity",
        "shear_governing_demand_kN": 120.0,
        "shear_governing_capacity_kN": 100.0,
        "shear_governing_util": 1.2,
        "shear_governing_status": "FAIL",
        "shear_governing_reason": (
            "sectional_shear_capacity_governs; "
            "governing_shear_util_exceeds_unity; raw_envelope_status=warn"
        ),
        "shear_governing_source": "sectional_shear_capacity",
        "shear_util_governing": 1.2,
        "web_util_governing": 120.0 / 135.0,
        "shear_truth_status": "FAIL",
        "shear_truth_reason": (
            "sectional_shear_capacity_governs; "
            "governing_shear_util_exceeds_unity; raw_envelope_status=warn"
        ),
        "canonical_shear_spacing_override_active": False,
        "canonical_shear_spacing_override_reason": "",
        "shear_truth_inconsistent_status_override": None,
        "shear_spacing_truth": {
            "provided_spacing_mm": 200.0,
            "required_spacing_mm": 150.0,
            "effective_spacing_mm": 200.0,
            "governing_spacing_source": "provided",
        },
        "shear_envelope_util_min": 0.84,
        "shear_sectional_util": 1.2,
        "canonical_shear_truth_input_shape": "bundle",
    }
    pure = shear.compute_canonical_shear_truth_from_bundle(
        state,
        bundle=bundle,
        canonical_shear_truth_input_shape="bundle",
        zone_payload=zone_payload,
    )
    wrapped = shear_checks_helpers.compute_canonical_shear_truth(
        state,
        bundle=bundle,
        zone_payload=zone_payload,
    )
    assert pure == expected
    assert wrapped == expected


def test_step4_diagram_strain_profile_contract() -> None:
    assert shear.derive_eps_top_bot_for_step4_diagram(0.001) == (
        0.00065,
        0.00135,
    )
    assert shear.derive_eps_top_bot_for_step4_diagram("0.002", delta="0.0002") == (
        0.0018,
        0.0022,
    )
    assert shear_core.derive_eps_top_bot_for_step4_diagram(0.001) == (
        0.00065,
        0.00135,
    )


def test_shear_summary_rows_with_overrides_contract() -> None:
    rows = [
        {"uid": "s8", "Check": "Sectional shear capacity", "Status": "old"},
        {"uid": "s2", "Check": "Equivalent design shear"},
        {"uid": "s4", "Check": "Longitudinal strain"},
        {"uid": "s5", "Check": "Shear model parameters"},
        {"uid": "s6", "Check": "Concrete shear strength"},
        {"uid": "s7", "Check": "Steel shear strength"},
        {"uid": "s9", "Check": "Web-crushing strength"},
        {"uid": "other", "Check": "Unchanged row", "capacity": "keep"},
    ]
    results = SimpleNamespace(
        V_eq=120.0,
        phi_Vu=160.0,
        Vu_max_kN=200.0,
        eps_x=0.00041,
        k_v=0.152,
        theta_v_deg=31.875,
        Vuc_kN=82.25,
        Vus_kN=151.75,
    )

    out = shear.build_shear_summary_rows_with_overrides(rows, results, 0.75)
    _near(out["summary_util"], 0.75)
    _near(out["summary_phi_vu_max"], 150.0)
    _near(out["summary_web_util"], 0.8)

    assert out["rows_summary"] == [
        {
            "uid": "s8",
            "Check": "Sectional shear capacity",
            "Status": "PASS",
            "capacity": "\u03c6Vu = 160.0 kN",
            "action": "V*eq = 120.0 kN",
            "Utilisation": "0.75",
        },
        {
            "uid": "s2",
            "Check": "Equivalent design shear",
            "capacity": "\u2014",
            "action": "V*eq = 120.0 kN",
        },
        {
            "uid": "s4",
            "Check": "Longitudinal strain",
            "capacity": "\u2014",
            "action": "\u03b5x = 0.00041",
        },
        {
            "uid": "s5",
            "Check": "Shear model parameters",
            "capacity": "\u2014",
            "action": "k_v = 0.152, \u03b8_v = 31.9\u00b0",
        },
        {
            "uid": "s6",
            "Check": "Concrete shear strength",
            "capacity": "\u2014",
            "action": "Vuc = 82.2 kN",
        },
        {
            "uid": "s7",
            "Check": "Steel shear strength",
            "capacity": "\u2014",
            "action": "Vs = Vus = 151.8 kN",
        },
        {
            "uid": "s9",
            "Check": "Web-crushing strength",
            "capacity": "\u03c6Vu,max = 150.0 kN",
            "action": "V*eq = 120.0 kN",
            "Utilisation": "0.80",
            "Status": "PASS",
        },
        {"uid": "other", "Check": "Unchanged row", "capacity": "keep"},
    ]
    assert rows[0]["Status"] == "old"


def test_shear_core_delegates_to_calculation_module() -> None:
    assert shear_core.compute_shear_capacity_values is shear.compute_shear_capacity_values
    assert shear_core.stirrup_area_mm2 is shear.stirrup_area_mm2
    assert (
        shear_core.approximate_concrete_tension_area_mm2
        is shear.approximate_concrete_tension_area_mm2
    )
    assert shear_core._calc_required_asv_per_s is shear.required_asv_per_s
    assert shear_core._calc_spacing_from_demand is shear.spacing_from_demand
    assert shear_core._calc_compute_midspan_spacing_result is shear.compute_midspan_spacing_result
    assert (
        shear_core.derive_eps_top_bot_for_step4_diagram
        is shear.derive_eps_top_bot_for_step4_diagram
    )
    assert shear_checks_helpers.resolve_shear_spacing_truth is shear.resolve_shear_spacing_truth
    assert (
        shear_checks_helpers.compute_canonical_shear_truth_from_bundle
        is shear.compute_canonical_shear_truth_from_bundle
    )
    assert (
        shear_checks_helpers.session_final_shear_truth_bundle_complete
        is shear.session_final_shear_truth_bundle_complete
    )
    assert shear_checks_helpers._fmt_row_util is shear.format_shear_row_util
    assert (
        shear_checks_helpers._truth_status_from_util
        is shear.shear_truth_status_from_util
    )
    assert shear_core.resolve_shear_spacing_truth is shear.resolve_shear_spacing_truth
    checks_source = Path(shear_checks_helpers.__file__).read_text(encoding="utf-8")
    assert "def resolve_shear_spacing_truth(" not in checks_source
    assert "def session_final_shear_truth_bundle_complete(" not in checks_source
    assert "def _fmt_row_util(" not in checks_source
    assert "def _truth_status_from_util(" not in checks_source
    assert "sectional_shear_capacity_governs" not in checks_source
    assert "web_crushing_strength_governs" not in checks_source
    core_source = Path(shear_core.__file__).read_text(encoding="utf-8")
    run_source = core_source.split("def run_shear_calc", 1)[1].split(
        "def compute_shear_zones",
        1,
    )[0]
    assert "compute_shear_capacity_values(inp)" in run_source
    assert "Tcr_Nmm = 0.33 * sqrt_fc" not in run_source
    assert "Asv = legs_eff * math.pi * lig_d**2 / 4.0" not in run_source
    assert "eps_x_1 = numerator / denom1" not in run_source
    assert "Vu_max_N = 0.55 * fc" not in run_source
    assert "asv_for_spacing = legs_disp * math.pi * lig_disp**2 / 4.0" not in core_source
    assert "A_ct = approximate_concrete_tension_area_mm2(b, D)" in core_source
    assert "A_ct = b * D / 2.0" not in core_source
    assert "def derive_eps_top_bot_for_step4_diagram(" not in core_source
    calc_source = Path(shear.__file__).read_text(encoding="utf-8")
    assert "d_v = effective_shear_depth_mm(D, d)" in calc_source
    assert "d_v = max(0.72 * D, 0.9 * d)" not in calc_source
    assert "minimum_shear_reinforcement_asv_per_s(" in calc_source
    assert "mcft = mcft_kv_theta_values(" in calc_source
    assert "def web_crushing_fallback_values(" in calc_source
    assert "def longitudinal_strain_fallback_values(" in calc_source
    assert "def torsion_section_geometry_values(" in calc_source
    assert "def shear_capacity_utilisation_values(" in calc_source
    assert "def shear_reinforcement_spacing_check_values(" in calc_source
    assert "def maximum_shear_spacing_mm(" in calc_source
    assert "def shear_check_display_scalars(" in calc_source
    assert "Asv_min_over_s = 0.08 * math.sqrt(max(fc, 0.1))" not in calc_source
    capacity_source = calc_source.split("def compute_shear_capacity_values", 1)[1].split(
        "def build_shear_summary_rows_with_overrides",
        1,
    )[0]
    assert "utilisation_values = shear_capacity_utilisation_values(shear_results, phi)" in calc_source
    assert "torsion_geometry = torsion_section_geometry_values(b, D)" in capacity_source
    assert "A_cp = b * D" not in capacity_source
    assert "u_c = 2.0 * (b + D)" not in capacity_source
    assert "Ao = 0.9 * A_cp" not in capacity_source
    assert "max(b - cover_t, 0.0)" not in capacity_source
    assert "k_dg = 32.0 / (16.0 + d_g)" not in capacity_source
    assert "k_v = (0.4 / (1.0 + 1500.0 * eps_x))" not in capacity_source
    assert "theta_v_deg = 29.0 + 7000.0 * eps_x" not in capacity_source
    page_source = (ROOT / "shear_page.py").read_text(encoding="utf-8")
    assert "build_shear_summary_rows_with_overrides(" in page_source
    assert "stirrup_area_mm2(legs, lig_d)" in page_source
    assert "duct_area_mm2(n_ducts, duct_dia)" in page_source
    assert "effective_shear_depth_mm(D, d)" in page_source
    assert "mcft = mcft_kv_theta_values(" in page_source
    assert "utilisation_values = shear_capacity_utilisation_values(results, phi)" in page_source
    assert "reinforcement_checks = shear_reinforcement_spacing_check_values(" in page_source
    assert "cotangent as cot" in page_source
    assert "torsion_geometry_fallback = torsion_section_geometry_values(" in page_source
    assert "strain_fallback = longitudinal_strain_fallback_values(" in page_source
    assert "noprestress_display = nonprestressed_longitudinal_strain_display_values(" in page_source
    assert "web_crushing_fallback = web_crushing_fallback_values(" in page_source
    assert "shear_display_scalars = shear_check_display_scalars(" in page_source
    assert "legs * math.pi * lig_d ** 2 / 4.0" not in page_source
    assert "def cot(" not in page_source
    assert "return 1.0 / math.tan(rad)" not in page_source
    assert "n_ducts * (duct_dia ** 2) * 3.14159 / 4.0" not in page_source
    assert "max(0.72 * D, 0.9 * d)" not in page_source
    assert "T_star_Nmm = T_star * 1e6" not in page_source
    assert "dv_1 = 0.72 * D" not in page_source
    assert "dv_2 = 0.9 * d" not in page_source
    assert "min(math.sqrt(fc), 8.0)" not in page_source
    assert "Vu_total_kN = float(getattr(shear_results, \"Vu_total_kN\", Vuc_kN + Vus_kN + P_v)" not in page_source
    assert "phi_Vu = float(getattr(shear_results, \"phi_Vu\", phi * Vu_total_kN)" not in page_source
    assert "b_used * D_used" not in page_source
    assert "2 * (b_used + D_used)" not in page_source
    assert "0.9 * A_cp" not in page_source
    assert "max(b_used - 40, 0)" not in page_source
    assert "0.08 * math.sqrt(fc) * b_v / (f_syv or 1.0)" not in page_source
    assert "Asv_over_s = results.Asv / s_lig if s_lig else 0.0" not in page_source
    assert "max_spacing = min(0.75 * D, 500.0) if D else 500.0" not in page_source
    assert "s_max_code = min(0.75 * D_mm, 500.0) if D_mm > 0.0 else 500.0" not in page_source
    assert "s_max_code = maximum_shear_spacing_mm(D_mm)" in page_source
    assert "Asv_over_s = Asv / s\n" not in page_source
    assert "Asv_over_s_check11 = Asv / s if s > 0 else 0.0" not in page_source
    assert "check11_reinforcement = shear_reinforcement_spacing_check_values(" in page_source
    assert "k_dg = 32.0 / (16.0 + d_g)" not in page_source
    assert "k_v = (0.4 / (1 + 1500 * eps_x))" not in page_source
    assert "theta_v_deg = 29.0 + 7000.0 * eps_x" not in page_source
    assert "term_M = M_star_Nmm / (d_v or 1.0)" not in page_source
    assert "torsion_N = 0.97 * T_star_Nmm * uh / (2.0 * (Ao or 1.0))" not in page_source
    assert "sqrt_inner = math.sqrt(Vprime_N ** 2 + torsion_N ** 2)" not in page_source
    assert "numerator_1 = term_M + sqrt_inner + N_star_N - A_pt_fpo_N" not in page_source
    assert "eps_x_1 = numerator_1 / denom1 if denom1 > 0 else 0.0" not in page_source
    assert "numerator_2 = term_M + V_abs_N - P_v * 1e3 + N_star_N - A_pt_fpo_N" not in page_source
    assert "eps_x_2 = numerator_2 / denom2 if denom2 > 0 else 0.0" not in page_source
    assert "eps_x_noprestress_num = term_M + Veq_term_N + N_star_N" not in page_source
    assert "eps_x_noprestress_den = 2.0 * (Es * A_st)" not in page_source
    assert "eps_x_noprestress = eps_x_noprestress_num / eps_x_noprestress_den if eps_x_noprestress_den > 0 else 0.0" not in page_source
    assert "term_V = V_star_N / (b_v * d_v or 1.0)" not in page_source
    assert "term_T = T_star_Nmm * uh / (1.7 * (A_oh ** 2 or 1.0))" not in page_source
    assert "math.sqrt(term_V ** 2 + term_T ** 2)" not in page_source
    assert "summary_phi_vu_max = phi * shear_results.Vu_max_kN" not in page_source
    assert "summary_web_util = (shear_results.V_eq / summary_phi_vu_max)" not in page_source
    assert "util = results.V_eq / phi_Vu_cap if phi_Vu_cap > 0 else" not in page_source
    assert "phi_Vu_max = phi * results.Vu_max_kN" not in page_source
    assert "Vuc_util = results.V_eq / phi_Vu_max if phi_Vu_max > 0 else" not in page_source


def main() -> int:
    test_required_asv_per_s_contract()
    test_spacing_from_demand_contract()
    test_midspan_spacing_contract()
    test_shear_capacity_values_contract()
    test_shear_spacing_truth_contract()
    test_final_shear_truth_bundle_completeness_contract()
    test_shear_truth_formatting_contract()
    test_canonical_shear_truth_bundle_contract()
    test_step4_diagram_strain_profile_contract()
    test_shear_summary_rows_with_overrides_contract()
    test_shear_core_delegates_to_calculation_module()
    print("shear_calculation_module_parity: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
