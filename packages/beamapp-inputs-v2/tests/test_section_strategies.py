from dataclasses import replace

import pytest

from inputs_v2.application.design_brain.section_strategies import (
    proposal_concrete_area_mm2,
    revise_family_geometry,
)
from inputs_v2.application.design_brain_apply import propose_neutral_candidate
from inputs_v2.domain.beam_inputs import BeamInputs
from inputs_v2.engineering.engineering_calculator import EngineeringCalculator


def _flanged(shape: str) -> BeamInputs:
    return BeamInputs(
        width_mm=300.0,
        depth_mm=650.0,
        section_shape=shape,
        web_width_mm=300.0,
        flange_width_mm=900.0,
        flange_thickness_mm=120.0,
    ).validated()


def test_rectangular_strategy_preserves_existing_proposal_shape() -> None:
    current = BeamInputs().validated()
    seed = propose_neutral_candidate(current)

    revised = revise_family_geometry(current, seed.proposal, width_mm=275.0, depth_mm=350.0)

    assert revised.width_mm == 275.0
    assert revised.depth_mm == 350.0
    assert revised.web_width_mm is None
    assert proposal_concrete_area_mm2(revised) == 96250.0


@pytest.mark.parametrize("shape", ("T", "I"))
def test_flanged_strategy_updates_web_and_compatibility_width_together(shape: str) -> None:
    current = _flanged(shape)
    seed = propose_neutral_candidate(current)

    revised = revise_family_geometry(current, seed.proposal, width_mm=325.0, depth_mm=700.0)

    assert revised.width_mm == 325.0
    assert revised.web_width_mm == 325.0
    assert revised.depth_mm == 700.0
    assert revised.flange_width_mm == 900.0
    assert revised.flange_thickness_mm == 120.0


def test_t_section_area_uses_web_and_flange_not_bounding_rectangle() -> None:
    seed = propose_neutral_candidate(_flanged("T"))

    assert proposal_concrete_area_mm2(seed.proposal) == 267000.0
    assert proposal_concrete_area_mm2(seed.proposal) != 900.0 * 650.0


def test_i_section_area_uses_two_symmetric_flanges() -> None:
    seed = propose_neutral_candidate(_flanged("I"))

    assert proposal_concrete_area_mm2(seed.proposal) == 339000.0


def test_flanged_strategy_rejects_incomplete_geometry() -> None:
    current = _flanged("T")
    seed = propose_neutral_candidate(current)
    incomplete = replace(seed.proposal, flange_width_mm=None)

    with pytest.raises(ValueError, match="complete flange and web geometry"):
        proposal_concrete_area_mm2(incomplete)


def test_t_strategy_keeps_requested_reduction_inside_flange_envelope() -> None:
    current = _flanged("T")
    revised = revise_family_geometry(
        current,
        propose_neutral_candidate(current).proposal,
        width_mm=1000.0,
        depth_mm=100.0,
    )

    assert revised.web_width_mm == 900.0
    assert revised.width_mm == 900.0
    assert revised.depth_mm == 200.0


def test_i_strategy_keeps_positive_web_between_symmetric_flanges() -> None:
    current = _flanged("I")
    revised = revise_family_geometry(
        current,
        propose_neutral_candidate(current).proposal,
        depth_mm=200.0,
    )

    assert revised.depth_mm == 265.0


def test_flanged_inputs_reject_two_competing_web_widths() -> None:
    with pytest.raises(ValueError, match="compatibility width"):
        BeamInputs(
            width_mm=300.0,
            depth_mm=650.0,
            section_shape="T",
            web_width_mm=325.0,
            flange_width_mm=900.0,
            flange_thickness_mm=120.0,
        ).validated()


@pytest.mark.parametrize("shape", ("T", "I"))
def test_flanged_calculation_publishes_one_web_for_fit_and_geometry(shape: str) -> None:
    current = _flanged(shape)
    result = EngineeringCalculator().calculate(current)

    assert result.families["reinforcement_fit"]["cage_width_mm"] == 300.0
    assert result.families["geometry"]["web_width_mm"] == 300.0
    assert result.families["geometry"]["section_shape"] == shape
    assert result.families["geometry"]["concrete_area_mm2"] == pytest.approx(
        current.section_geometry.concrete_area_mm2
    )
