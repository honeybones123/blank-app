from __future__ import annotations

from dataclasses import replace
import math

import pytest

from inputs_v2.domain.beam_inputs import (
    ActionInputs,
    BeamInputs,
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
            use_general_kv=use_general_kv,
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
        shear=replace(simplified.shear, use_general_kv=True),
    ).validated()

    assert simplified.content_hash != general.content_hash


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
