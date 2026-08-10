from dataclasses import replace

from inputs_v2.domain.beam_inputs import BeamInputs
from inputs_v2.engineering.reinforcement_fit import evaluate_arrangement, practical_row_counts
from inputs_v2.engineering.engineering_calculator import EngineeringCalculator
from inputs_v2.presentation.view_models.input_diagram import build_input_diagram_view_model
from inputs_v2.application.design_brain_apply import Candidate, apply_candidate, propose_neutral_candidate
from inputs_v2.application.ranking_policy import CandidateEvidence
from inputs_v2.application.design_brain.family_owners import RankingPolicy

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

def test_any_canonical_edit_invalidates_stale_arrangement():
    inputs = BeamInputs(depth_mm=500.0)
    arrangement = evaluate_arrangement(inputs, (3, 3)).arrangement
    stored = replace(inputs, bottom_arrangement=arrangement)
    seed = propose_neutral_candidate(stored)
    proposal = replace(seed.proposal, bottom_bars=stored.bottom.bars + 1)
    changed = apply_candidate(stored, Candidate(seed.candidate_id, stored.revision, stored.content_hash, proposal, seed.rationale))
    assert changed.applied
    assert changed.inputs.bottom_arrangement is None

def test_ranking_rejects_invalid_before_target_distance():
    invalid_near_target = CandidateEvidence("invalid", False, False, target_distance=0.01)
    valid_farther = CandidateEvidence("valid", True, True, target_distance=0.20)
    selected = RankingPolicy().select((invalid_near_target, valid_farther))
    assert selected is not None
    assert selected.candidate_id == "valid"
