import math

import pytest

from inputs_v2.domain.beam_inputs import BeamInputs, TimeDependentInputs
from inputs_v2.engineering.engineering_calculator import EngineeringCalculator
from inputs_v2.engineering.time_dependent import (
    SHRINKAGE_TABLE,
    LoadingAgeFactorInput,
    basic_creep_coeff,
    calc_eps_cse,
    calc_k1_shrinkage,
    calc_k2_creep,
    calc_k3,
    calc_k4,
    calc_k5,
    calc_k6,
    calculate_loading_age_factor,
    creep_closest_th,
    creep_coefficient_value,
    exposed_perimeter_geometry_values,
    shrinkage_closest_th,
    shrinkage_eps_final,
    shrinkage_total_values,
)


def test_shrinkage_reference_table_matches_as3600_table_3_1_7_2() -> None:
    assert SHRINKAGE_TABLE[25]["Interior"] == {50: 760, 100: 670, 200: 550, 400: 440}
    assert SHRINKAGE_TABLE[40]["Tropical"] == {50: 600, 100: 540, 200: 460, 400: 380}
    assert SHRINKAGE_TABLE[100]["Tropical"] == {50: 630, 100: 590, 200: 540, 400: 500}


def test_drying_shrinkage_uses_clause_3_1_7_2_equation_not_total_table() -> None:
    # Cl. 3.1.7.2(4)-(5): eps_csd = k1*k4*(0.9-0.005f'c)*800e-6.
    expected_final_drying = 0.60 * (0.9 - 0.005 * 40.0) * 800e-6
    assert shrinkage_eps_final(
        40.0,
        "Temperate inland environment",
        137.0,
    ) == pytest.approx(expected_final_drying)


def test_authoritative_time_factors_use_unrounded_hypothetical_thickness() -> None:
    time = TimeDependentInputs(
        shrinkage_time_days=730.0,
        creep_time_days=540.0,
        exposed_faces="Beam – three faces exposed",
        creep_environment="Temperate inland environment",
        shrinkage_environment="Temperate inland environment",
    )
    inputs = BeamInputs(width_mm=310.0, depth_mm=610.0, time_dependent=time).validated()
    result = EngineeringCalculator().calculate(inputs)
    raw_th = exposed_perimeter_geometry_values(310.0, 610.0, time.exposed_faces)["th_raw"]

    assert raw_th not in {50.0, 100.0, 200.0, 400.0}
    assert result.families["creep"]["k2_creep"] == pytest.approx(
        calc_k2_creep(time.creep_time_days, raw_th)
    )
    assert result.families["shrinkage"]["k1_shrinkage"] == pytest.approx(
        calc_k1_shrinkage(time.shrinkage_time_days, raw_th)
    )


@pytest.mark.parametrize("age_days", [-20.0, 0.0, 1.0, 3.0, 7.0, 28.0, 365.0, 10_000.0])
def test_loading_age_factor_preserves_snapshot_numerical_parity(age_days: float) -> None:
    result = calculate_loading_age_factor(LoadingAgeFactorInput(age_days))
    assert result.k3 == pytest.approx(calc_k3(age_days), rel=0.0, abs=1e-15)
    assert result.effective_age_days == max(age_days, 1.0)


@pytest.mark.parametrize("age_days", [math.nan, math.inf, -math.inf])
def test_loading_age_factor_rejects_non_finite_age(age_days: float) -> None:
    with pytest.raises(ValueError, match="must be finite"):
        calculate_loading_age_factor(LoadingAgeFactorInput(age_days))


def test_authoritative_calculator_uses_v2_owned_loading_age_component() -> None:
    inputs = BeamInputs(
        time_dependent=TimeDependentInputs(age_at_loading_days=28.0)
    ).validated()
    result = EngineeringCalculator().calculate(inputs)
    expected = calculate_loading_age_factor(LoadingAgeFactorInput(28.0))
    assert result.source_revision == inputs.revision
    assert result.source_hash == inputs.content_hash
    assert result.families["creep_shrinkage"]["k3_age_loading"] == expected.k3


def test_authoritative_calculator_publishes_complete_creep_and_shrinkage_results() -> None:
    time = TimeDependentInputs(
        shrinkage_time_days=730.0,
        creep_time_days=540.0,
        age_at_loading_days=56.0,
        exposed_faces="Beam – three faces exposed",
        creep_environment="Temperate inland environment",
        shrinkage_environment="Temperate inland environment",
        stress_ratio=0.35,
        concrete_modulus_mpa=30000.0,
    )
    inputs = BeamInputs(width_mm=300.0, depth_mm=600.0, time_dependent=time).validated()
    result = EngineeringCalculator().calculate(inputs)
    geometry = exposed_perimeter_geometry_values(300.0, 600.0, time.exposed_faces)
    creep_th = creep_closest_th(geometry["th_raw"])
    shrinkage_th = shrinkage_closest_th(geometry["th_raw"])
    equation_th = geometry["th_raw"]
    expected_phi = creep_coefficient_value(
        k2=calc_k2_creep(time.creep_time_days, equation_th),
        k3=calc_k3(time.age_at_loading_days),
        k4=calc_k4(time.creep_environment),
        k5=calc_k5(40.0, equation_th, calc_k4(time.creep_environment)),
        k6=calc_k6(time.stress_ratio),
        phi_cc_b=basic_creep_coeff(40.0),
    )
    expected_shrinkage = shrinkage_total_values(
        calc_k1_shrinkage(time.shrinkage_time_days, equation_th),
        calc_eps_cse(40.0, time.shrinkage_time_days),
        shrinkage_eps_final(40.0, time.shrinkage_environment, shrinkage_th),
    )

    assert result.families["creep"]["phi_cc_t"] == pytest.approx(expected_phi)
    assert result.families["shrinkage"]["eps_cs_total"] == pytest.approx(
        expected_shrinkage["eps_cs_total"]
    )
    assert result.families["creep"]["check_metadata"]["creep_coefficient"]["clause"] == "3.1.8"
    assert result.families["shrinkage"]["check_metadata"]["shrinkage_strain"]["clause"] == "3.1.7"
