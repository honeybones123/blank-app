from dataclasses import replace

import pytest

from inputs_v2.domain.beam_inputs import (
    ActionInputs,
    BeamInputs,
    KvMethod,
    ShearReinforcement,
)
from inputs_v2.engineering.reinforcement_fit import evaluate_arrangement, practical_row_counts
from inputs_v2.engineering.engineering_calculator import EngineeringCalculator
from inputs_v2.presentation.view_models.input_diagram import build_input_diagram_view_model
from inputs_v2.application.design_brain_apply import Candidate, apply_candidate, propose_neutral_candidate
from inputs_v2.application.ranking_policy import CandidateEvidence
from inputs_v2.application.design_brain.family_owners import RankingPolicy
from inputs_v2.application.design_guide_orchestrator import DesignGuideOrchestrator

def test_single_row_fit_and_effective_depth():
    result = evaluate_arrangement(BeamInputs(), (3,))
    assert result.accepted
    assert result.arrangement.layer_count == 1
    assert result.arrangement.effective_depth_mm < 300

def test_balanced_two_rows_are_explicit():
    result = evaluate_arrangement(BeamInputs(depth_mm=500.0), (3, 3))
    assert result.accepted
    assert result.arrangement.layer_count == 2
    assert result.arrangement.rows[0].bar_count == 3

def test_row_fails_when_clear_spacing_is_too_small():
    inputs = BeamInputs(width_mm=250.0, bottom=replace(BeamInputs().bottom, bars=8, diameter_mm=32))
    result = evaluate_arrangement(inputs, (8,))
    assert not result.accepted
    assert result.congestion.congestion_class == "invalid"

def test_fit_reports_cover_clearance_contract():
    result = evaluate_arrangement(BeamInputs(), (3,))
    assert result.accepted
    assert result.cover_ok

def test_fit_rejects_negative_aggregate_clearance():
    result = evaluate_arrangement(BeamInputs(), (3,), aggregate_clearance_mm=-1.0)
    assert not result.accepted
    assert not result.aggregate_clearance_ok

def test_ligature_allowance_reduces_available_width():
    plain = evaluate_arrangement(BeamInputs(), (3,))
    with_links = evaluate_arrangement(replace(BeamInputs(), shear=replace(BeamInputs().shear, diameter_mm=20, legs=4)), (3,))
    assert with_links.arrangement.rows[0].clear_spacing_mm < plain.arrangement.rows[0].clear_spacing_mm

def test_calculator_publishes_fit_in_shadow_result():
    result = EngineeringCalculator().calculate(BeamInputs())
    fit = result.families["reinforcement_fit"]
    assert fit["layer_count"] == 1
    assert "effective_depth_mm" in fit

def test_practical_row_generation_is_balanced():
    assert practical_row_counts(6) == ((6,), (3, 3))
    assert practical_row_counts(7) == ((7,), (4, 3))
    assert practical_row_counts(3) == ((3,),)

def test_arrangement_recalculation_uses_centroid_effective_depth():
    inputs = BeamInputs(depth_mm=500.0)
    arrangement = evaluate_arrangement(inputs, (3, 3)).arrangement
    result = EngineeringCalculator().calculate_with_arrangement(inputs, arrangement)
    assert result.families["bending"]["d_mm"] == arrangement.effective_depth_mm
    assert result.families["serviceability"]["effective_depth_mm"] == arrangement.effective_depth_mm
    assert result.families["crack_control"]["effective_depth_mm"] == arrangement.effective_depth_mm

def test_canonical_calculate_route_uses_stored_arrangement():
    base = BeamInputs(depth_mm=500.0)
    arrangement = evaluate_arrangement(base, (3, 3)).arrangement
    stored = replace(base, bottom_arrangement=arrangement)
    result = EngineeringCalculator().calculate(stored)
    assert result.families["bending"]["d_mm"] == arrangement.effective_depth_mm
    assert result.families["reinforcement_fit"]["layer_count"] == 2

def test_diagram_preserves_two_arrangement_rows():
    inputs = BeamInputs(depth_mm=500.0)
    arrangement = evaluate_arrangement(inputs, (3, 3)).arrangement
    view = build_input_diagram_view_model(inputs, arrangement)
    assert tuple(len(row) for row in view.bottom_rows) == (3, 3)
    assert len(view.bars) == 6

def test_apply_persists_exact_two_row_arrangement():
    inputs = BeamInputs(depth_mm=500.0)
    seed = propose_neutral_candidate(inputs)
    candidate = Candidate(seed.candidate_id, inputs.revision, inputs.content_hash, seed.proposal, seed.rationale, (3, 3))
    outcome = apply_candidate(inputs, candidate)
    assert outcome.applied
    assert outcome.inputs.bottom_arrangement is not None
    assert tuple(row.bar_count for row in outcome.inputs.bottom_arrangement.rows) == (3, 3)


def test_apply_persists_exact_mixed_diameter_two_row_arrangement():
    inputs = BeamInputs(depth_mm=500.0)
    seed = propose_neutral_candidate(inputs)
    candidate = Candidate(
        seed.candidate_id,
        inputs.revision,
        inputs.content_hash,
        replace(seed.proposal, bottom_bars=5, bottom_diameter_mm=20),
        seed.rationale,
        (3, 2),
        (20.0, 16.0),
    )
    outcome = apply_candidate(inputs, candidate)
    assert outcome.applied
    assert outcome.inputs.bottom_arrangement is not None
    assert tuple(
        (row.bar_count, row.bar_diameter_mm)
        for row in outcome.inputs.bottom_arrangement.rows
    ) == ((3, 20.0), (2, 16.0))
    result = EngineeringCalculator().calculate(outcome.inputs)
    assert result.families["bending"]["Ast_tension_mm2"] == pytest.approx(
        outcome.inputs.bottom_arrangement.total_steel_area_mm2
    )
    diagram = build_input_diagram_view_model(
        outcome.inputs,
        outcome.inputs.bottom_arrangement,
    )
    assert tuple(
        tuple(bar.diameter_mm for bar in row)
        for row in diagram.bottom_rows
    ) == ((20.0, 20.0, 20.0), (16.0, 16.0))

def test_any_canonical_edit_replaces_stale_arrangement_with_verified_fit():
    inputs = BeamInputs(depth_mm=500.0)
    arrangement = evaluate_arrangement(inputs, (3, 3)).arrangement
    stored = replace(inputs, bottom_arrangement=arrangement)
    seed = propose_neutral_candidate(stored)
    proposal = replace(seed.proposal, bottom_bars=stored.bottom.bars + 1)
    changed = apply_candidate(stored, Candidate(seed.candidate_id, stored.revision, stored.content_hash, proposal, seed.rationale))
    assert changed.applied
    assert changed.inputs.bottom_arrangement is not None
    assert changed.inputs.bottom_arrangement is not arrangement
    assert changed.inputs.bottom_arrangement.total_bar_count == stored.bottom.bars + 1


def test_shear_candidate_preview_matches_fresh_post_apply_calculation():
    current = BeamInputs(
        width_mm=300.0,
        depth_mm=400.0,
        span_mm=2000.0,
        bottom=replace(BeamInputs().bottom, bars=4, diameter_mm=16),
        shear=ShearReinforcement(
            diameter_mm=10,
            legs=2,
            spacing_mm=150.0,
            kv_method=KvMethod.GENERAL,
        ),
        actions=ActionInputs(shear_force_kn=400.0),
    ).validated()
    initial_fit = evaluate_arrangement(current, (4,))
    current = replace(current, bottom_arrangement=initial_fit.arrangement).validated()

    decision = DesignGuideOrchestrator().decide(current)

    assert decision.apply_allowed is True
    assert decision.candidate is not None
    assert decision.proposed_result is not None
    applied = apply_candidate(current, decision.candidate)
    assert applied.applied is True
    assert applied.inputs.bottom_arrangement is not None

    fresh = EngineeringCalculator().calculate(applied.inputs)
    preview_shear = decision.proposed_result.families["shear"]
    fresh_shear = fresh.families["shear"]
    assert preview_shear["kv_method"] == fresh_shear["kv_method"] == "general"
    assert preview_shear["d_v"] == pytest.approx(fresh_shear["d_v"])
    assert preview_shear["phi_Vu"] == pytest.approx(fresh_shear["phi_Vu"])
    assert 400.0 / fresh_shear["phi_Vu"] <= 1.0

def test_ranking_rejects_invalid_before_target_distance():
    invalid_near_target = CandidateEvidence("invalid", False, False, target_distance=0.01)
    valid_farther = CandidateEvidence("valid", True, True, target_distance=0.20)
    selected = RankingPolicy().select((invalid_near_target, valid_farther))
    assert selected is not None
    assert selected.candidate_id == "valid"
