from __future__ import annotations

from dataclasses import replace
import math

import pytest

from inputs_v2.domain.beam_inputs import (
    ActionInputs,
    BeamInputs,
    KvMethod,
    LongitudinalReinforcement,
    ShearReinforcement,
)
from inputs_v2.engineering.check_metadata import AS3600_2018_CHECKS
from inputs_v2.engineering.engineering_calculator import EngineeringCalculator


def _calculated(*, use_general_kv: bool):
    current = BeamInputs(
        actions=ActionInputs(bending_moment_knm=100.0, shear_force_kn=100.0),
        shear=ShearReinforcement(
            diameter_mm=10,
            legs=2,
            spacing_mm=200.0,
            kv_method=KvMethod.GENERAL if use_general_kv else KvMethod.SIMPLIFIED,
        ),
    ).validated()
    return EngineeringCalculator().calculate(current)


@pytest.mark.parametrize(
    ("use_general_kv", "expected_id", "unexpected_id"),
    [
        (True, "kv_general_method", "kv_simplified_method"),
        (False, "kv_simplified_method", "kv_general_method"),
    ],
)
def test_shear_method_and_clause_metadata_follow_the_committed_method(
    use_general_kv: bool,
    expected_id: str,
    unexpected_id: str,
) -> None:
    shear = _calculated(use_general_kv=use_general_kv).families["shear"]

    assert expected_id in shear["check_metadata"]
    assert unexpected_id not in shear["check_metadata"]
    assert shear["check_metadata"][expected_id] == AS3600_2018_CHECKS[expected_id]


def test_ductility_check_uses_the_authoritative_neutral_axis_limit() -> None:
    result = _calculated(use_general_kv=False)

    assert result.families["ductility"]["limit"] == pytest.approx(0.36)
    assert result.families["ductility"]["check_metadata"] == {
        "bending_ductility": AS3600_2018_CHECKS["bending_ductility"]
    }


def test_ductility_ku_comes_from_strain_compatible_force_equilibrium() -> None:
    current = BeamInputs().validated()
    result = EngineeringCalculator().calculate(current)
    bending = result.families["bending"]
    ductility = result.families["ductility"]

    assert bending["shape_equilibrium_valid"] is True
    assert abs(bending["equilibrium_residual_n"]) < 1e-6
    assert ductility["ku"] == pytest.approx(
        bending["dn_mm"] / ductility["effective_depth_mm"]
    )
    assert ductility["util"] == pytest.approx(ductility["ku"] / 0.36)


def _high_ku_design(*, demand_fraction: float, verified: bool) -> tuple[dict, dict]:
    base = BeamInputs(
        width_mm=300.0,
        depth_mm=600.0,
        bottom=LongitudinalReinforcement(bars=6, diameter_mm=32, cover_mm=40.0),
        top=LongitudinalReinforcement(bars=4, diameter_mm=20, cover_mm=40.0),
        clause_815_analysis_verified=verified,
        compression_reinforcement_restrained=verified,
    ).validated()
    initial = EngineeringCalculator().calculate(base).families["bending"]
    loaded = replace(
        base,
        actions=replace(
            base.actions,
            bending_moment_knm=demand_fraction * initial["phi_Mu_kNm"],
        ),
    ).validated()
    result = EngineeringCalculator().calculate(loaded)
    return result.families["bending"], result.families["ductility"]


def test_ductility_limit_is_mandatory_even_at_low_demand() -> None:
    bending, ductility = _high_ku_design(demand_fraction=0.70, verified=False)

    assert bending["ku"] > 0.36
    assert ductility["conditional_triggered"] is True
    assert ductility["status"] == "FAIL"
    assert "neutral_axis_limit_exceeded" in ductility["failed_requirements"]


def test_clause_815_requires_all_conditional_evidence_above_eighty_percent() -> None:
    bending, ductility = _high_ku_design(demand_fraction=0.90, verified=False)

    assert bending["ku"] > 0.36
    assert ductility["conditional_triggered"] is True
    assert ductility["compression_steel_requirement_satisfied"] is True
    assert ductility["status"] == "FAIL"
    assert ductility["failed_requirements"] == (
        "neutral_axis_limit_exceeded",
        "clause_815_analysis_not_verified",
        "compression_reinforcement_restraint_not_verified",
    )


def test_verified_conditional_evidence_does_not_override_the_runtime_ku_limit() -> None:
    _bending, ductility = _high_ku_design(demand_fraction=0.90, verified=True)

    assert ductility["conditional_triggered"] is True
    assert ductility["conditional_requirements_satisfied"] is True
    assert ductility["failed_requirements"] == ("neutral_axis_limit_exceeded",)
    assert ductility["status"] == "FAIL"


def test_every_emitted_clause_record_is_complete_and_owned_by_the_check_registry() -> None:
    result = _calculated(use_general_kv=True)

    for family in result.families.values():
        metadata = family.get("check_metadata", {})
        for check_id, reference in metadata.items():
            assert check_id in AS3600_2018_CHECKS
            assert reference == AS3600_2018_CHECKS[check_id]
            assert set(reference) == {"standard", "edition", "clause", "title"}
            assert all(str(value).strip() for value in reference.values())


def test_shear_method_participates_in_the_engineering_content_hash() -> None:
    simplified = BeamInputs().validated()
    general = replace(
        simplified,
        shear=replace(simplified.shear, kv_method=KvMethod.GENERAL),
    ).validated()

    assert simplified.content_hash != general.content_hash


@pytest.mark.parametrize(
    ("use_general_kv", "expected_method", "expected_check_id"),
    [
        (False, "simplified", "kv_simplified_method"),
        (True, "general", "kv_general_method"),
    ],
)
def test_shear_result_explicitly_records_selected_kv_method(
    use_general_kv: bool,
    expected_method: str,
    expected_check_id: str,
) -> None:
    shear = _calculated(use_general_kv=use_general_kv).families["shear"]

    assert shear["kv_method"] == expected_method
    assert shear["kv_check_id"] == expected_check_id
    assert expected_check_id in shear["check_metadata"]


def test_conventional_top_reinforcement_is_not_mapped_as_prestressing_steel() -> None:
    baseline = BeamInputs(
        shear=replace(BeamInputs().shear, kv_method=KvMethod.GENERAL),
        actions=replace(
            BeamInputs().actions,
            bending_moment_knm=180.0,
            shear_force_kn=160.0,
        ),
    ).validated()
    increased_top_steel = replace(
        baseline,
        top=replace(baseline.top, bars=8, diameter_mm=32),
    ).validated()

    baseline_shear = EngineeringCalculator().calculate(baseline).families["shear"]
    increased_shear = EngineeringCalculator().calculate(increased_top_steel).families["shear"]

    assert increased_shear["eps_x"] == pytest.approx(baseline_shear["eps_x"])
    assert increased_shear["phi_Vu"] == pytest.approx(baseline_shear["phi_Vu"])


def test_runtime_applied_prestress_is_mapped_to_general_method_pv_only() -> None:
    baseline = BeamInputs(
        bottom=LongitudinalReinforcement(bars=4, diameter_mm=20),
        shear=ShearReinforcement(
            diameter_mm=10,
            legs=2,
            spacing_mm=150.0,
            kv_method=KvMethod.GENERAL,
        ),
        actions=ActionInputs(
            bending_moment_knm=40.0,
            shear_force_kn=80.0,
        ),
    ).validated()
    prestressed = replace(
        baseline,
        actions=replace(baseline.actions, applied_prestress_kn=20.0),
    ).validated()

    baseline_shear = EngineeringCalculator().calculate(baseline).families["shear"]
    prestressed_shear = EngineeringCalculator().calculate(prestressed).families["shear"]

    assert baseline_shear["P_v"] == pytest.approx(0.0)
    assert prestressed_shear["P_v"] == pytest.approx(20.0)
    assert prestressed_shear["A_pt"] == pytest.approx(0.0)
    assert prestressed_shear["f_po"] == pytest.approx(0.0)
    assert prestressed_shear["eps_x"] < baseline_shear["eps_x"]
    assert prestressed_shear["phi_Vu"] > baseline_shear["phi_Vu"]

    ast = 4.0 * math.pi * 20.0**2 / 4.0
    expected_eps_x = (
        40.0e6 / prestressed_shear["d_v"]
        + abs(80.0 - 20.0) * 1.0e3
    ) / (2.0 * 200000.0 * ast)
    expected_kv = 0.4 / (1.0 + 1500.0 * expected_eps_x)
    assert prestressed_shear["A_st"] == pytest.approx(ast)
    assert prestressed_shear["eps_x"] == pytest.approx(expected_eps_x)
    assert prestressed_shear["k_v"] == pytest.approx(expected_kv)


def test_minimum_tensile_reinforcement_uses_the_accepted_flexural_tensile_strength() -> None:
    current = BeamInputs().validated()
    result = EngineeringCalculator().calculate(current)
    bending = result.families["bending"]
    effective_depth = result.families["ductility"]["effective_depth_mm"]
    expected_fctf = 0.6 * math.sqrt(current.materials.concrete_strength_mpa)
    expected_ast_min = (
        0.4
        * expected_fctf
        * current.width_mm
        * effective_depth
        / current.materials.reinforcement_strength_mpa
    )

    assert bending["Ast_min_mm2"] == pytest.approx(expected_ast_min)


def test_minimum_flexural_capacity_is_published_from_the_authoritative_check() -> None:
    current = BeamInputs().validated()
    bending = EngineeringCalculator().calculate(current).families["bending"]
    expected_fctf = 0.6 * math.sqrt(current.materials.concrete_strength_mpa)
    expected_mcr = (
        expected_fctf
        * current.width_mm
        * current.depth_mm**2
        / 6.0
        / 1_000_000.0
    )
    expected_minimum = 1.2 * expected_mcr

    assert bending["Mcr_kNm"] == pytest.approx(expected_mcr)
    assert bending["minimum_capacity_knm"] == pytest.approx(expected_minimum)
    assert bending["minimum_capacity_util"] == pytest.approx(
        expected_minimum / bending["phi_Mu_kNm"]
    )
    assert bending["minimum_capacity_status"] in {"PASS", "FAIL"}
