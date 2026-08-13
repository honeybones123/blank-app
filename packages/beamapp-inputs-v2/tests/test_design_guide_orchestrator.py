from inputs_v2.application.design_brain_families import DesignFamily
from inputs_v2.application.design_brain_decision import DecisionStatus
from dataclasses import replace
import pytest

from inputs_v2.application.design_guide_orchestrator import DesignGuideOrchestrator
from inputs_v2.application.design_brain_service import DesignBrainService
from inputs_v2.application.design_brain_apply import apply_candidate
from inputs_v2.application.design_brain.family_owners import FAMILY_OWNERS
from inputs_v2.application.design_brain.search_profile import SearchProfile
from inputs_v2.application.engineering_advice import format_engineering_advice
from inputs_v2.presentation.view_models.design_brain_card import (
    build_design_brain_card_view_model,
)
from inputs_v2.domain.beam_inputs import (
    ActionInputs,
    BeamInputs,
    LongitudinalReinforcement,
    ServiceabilityInputs,
    ShearReinforcement,
)
from inputs_v2.engineering.reinforcement_fit import evaluate_arrangement


def test_orchestrator_routes_combined_failure_to_one_atomic_ladder() -> None:
    current = BeamInputs(actions=ActionInputs(bending_moment_knm=1000.0, shear_force_kn=300.0)).validated()
    decision = DesignGuideOrchestrator().preview(current)
    assert decision.family is DesignFamily.BENDING_AND_SHEAR_FAIL_GOVERN
    assert decision.preview.candidate.source_revision == current.revision


def test_combined_failure_accepts_safe_repair_when_explicit_sls_prevents_uls_target_band() -> None:
    current = BeamInputs(
        width_mm=150.0,
        depth_mm=200.0,
        span_mm=2000.0,
        bottom=LongitudinalReinforcement(bars=2, diameter_mm=12, cover_mm=40.0),
        top=LongitudinalReinforcement(bars=2, diameter_mm=10, cover_mm=40.0),
        shear=ShearReinforcement(diameter_mm=0, legs=0, spacing_mm=200.0),
        actions=ActionInputs(bending_moment_knm=60.0, shear_force_kn=120.0),
        serviceability=ServiceabilityInputs(
            moment_knm=50.0,
            shear_kn=100.0,
            permanent_udl_knm_per_m=100.0,
            equivalent_udl_knm_per_m=100.0,
        ),
    ).validated()

    decision = DesignGuideOrchestrator().decide(current)
    bending_util = float(decision.proposed_result.families["bending"]["util"])
    shear_util = 120.0 / float(decision.proposed_result.families["shear"]["phi_Vu"])

    assert decision.family is DesignFamily.BENDING_AND_SHEAR_FAIL_GOVERN
    assert decision.status.value == "ACTION"
    assert decision.apply_allowed
    assert decision.reason == "safe_combined_failure_repair"
    assert bending_util <= 1.0
    assert shear_util <= 1.0
    assert decision.proposed_result.families["serviceability"]["status"] == "PASS"
    assert decision.proposed_result.families["crack_control"]["status"] == "PASS"


@pytest.mark.parametrize(
    "family",
    (
        DesignFamily.BENDING_OVERDESIGN_GOVERNS,
        DesignFamily.SHEAR_OVERDESIGN_GOVERNS,
        DesignFamily.COMBINED_OVERDESIGN,
    ),
)
def test_optimisation_exhaustion_without_exact_stop_evidence_is_blocked(family: DesignFamily) -> None:
    contract = FAMILY_OWNERS[family].contract

    outcome = contract.resolve_outcome(
        current_failed=False,
        current_compliant=True,
        current_in_band=False,
        preview_accepted=False,
        proposed_in_band=False,
        exact_stop_proven=False,
        preview_reason="proposal_outside_target_band",
    )

    assert outcome.status == "BLOCKED"
    assert outcome.final_family is family
    assert outcome.cta_intent.value == "review_blocker"


def test_failed_design_without_verified_repair_remains_blocked() -> None:
    contract = FAMILY_OWNERS[DesignFamily.BENDING_AND_SHEAR_FAIL_GOVERN].contract

    outcome = contract.resolve_outcome(
        current_failed=True,
        current_compliant=False,
        current_in_band=False,
        preview_accepted=False,
        proposed_in_band=False,
        exact_stop_proven=False,
        preview_reason="no_compliant_candidate",
    )

    assert outcome.status == "BLOCKED"


def test_exact_stop_requires_every_declared_family_stage() -> None:
    contract = FAMILY_OWNERS[DesignFamily.BENDING_OVERDESIGN_GOVERNS].contract
    reason = contract.exact_stop_policy.reason_codes[0]
    stages = contract.exact_stop_policy.required_stage_ids

    assert not contract.proves_exact_stop(
        preview_accepted=False,
        preview_reason=reason,
        candidates_attempted=100,
        completed_stage_ids=stages[:-1],
        stage_stop_reasons={stage: "search_space_enumerated" for stage in stages[:-1]},
    )
    assert contract.proves_exact_stop(
        preview_accepted=False,
        preview_reason=reason,
        candidates_attempted=100,
        completed_stage_ids=stages,
        stage_stop_reasons={stage: "search_space_enumerated" for stage in stages},
    )


def test_exact_stop_rejects_completed_stage_without_stop_evidence() -> None:
    contract = FAMILY_OWNERS[DesignFamily.BENDING_OVERDESIGN_GOVERNS].contract
    stages = contract.exact_stop_policy.required_stage_ids

    assert not contract.proves_exact_stop(
        preview_accepted=False,
        preview_reason=contract.exact_stop_policy.reason_codes[0],
        candidates_attempted=100,
        completed_stage_ids=stages,
        stage_stop_reasons={},
    )


def test_orchestrator_routes_shear_failure_to_shear_ladder() -> None:
    current = BeamInputs(actions=ActionInputs(shear_force_kn=300.0)).validated()
    decision = DesignGuideOrchestrator().preview(current)
    assert decision.family is DesignFamily.SHEAR_FAIL_BENDING_OPTIMISE_GOVERNS


def test_inactive_shear_domain_cannot_select_mixed_bending_shear_family() -> None:
    current = BeamInputs(
        shear=ShearReinforcement(diameter_mm=0, legs=0, spacing_mm=200.0),
        actions=ActionInputs(bending_moment_knm=1000.0, shear_force_kn=0.0),
    ).validated()

    decision = DesignGuideOrchestrator().decide(current)

    assert decision.family is DesignFamily.BENDING_FAIL_GOVERNS
    assert decision.status.value == "ACTION"
    assert decision.apply_allowed


def test_orchestrator_routes_geometry_violation_to_geometry_repair() -> None:
    current = BeamInputs(
        width_mm=200.0,
        depth_mm=450.0,
        actions=ActionInputs(bending_moment_knm=10.0),
    ).validated()
    decision = DesignGuideOrchestrator().preview(current)
    assert decision.family is DesignFamily.GEOMETRY_DETAILING_GOVERNS
    assert (
        decision.preview.candidate.proposal.depth_mm
        <= 2.0 * decision.preview.candidate.proposal.width_mm
    )


def test_orchestrator_registers_every_contract_family() -> None:
    assert set(DesignGuideOrchestrator.registered_families()) == set(DesignFamily)


def test_no_design_actions_are_owned_by_typed_terminal_family_without_search() -> None:
    decision = DesignGuideOrchestrator().decide(BeamInputs().validated())

    assert decision.family is DesignFamily.INPUT_REQUIRED
    assert decision.status is DecisionStatus.INPUT_REQUIRED
    assert not decision.apply_allowed
    assert decision.reason == "design_actions_required"
    assert decision.search_evidence.candidates_attempted == 0
    assert decision.search_evidence.cache_misses == 0


def test_shear_in_band_does_not_hide_mandatory_bending_failure() -> None:
    base = BeamInputs(
        width_mm=250.0,
        depth_mm=500.0,
        bottom=LongitudinalReinforcement(bars=2, diameter_mm=10),
    ).validated()
    result = DesignBrainService()._calculator.calculate_current(base).result
    assert result is not None
    shear_capacity = float(result.families["shear"]["phi_Vu"])
    current = replace(base, actions=ActionInputs(bending_moment_knm=10.0, shear_force_kn=0.85 * shear_capacity)).validated()
    decision = DesignGuideOrchestrator().decide(current)
    assert decision.current_result.families["bending"]["minimum_tensile_status"] == "FAIL"
    assert decision.family is DesignFamily.BENDING_FAIL_GOVERNS
    assert decision.status.value == "ACTION"
    assert decision.apply_allowed


def test_in_band_bending_does_not_hide_zero_demand_shear_cleanup() -> None:
    base = BeamInputs(
        width_mm=300.0,
        depth_mm=500.0,
        bottom=BeamInputs().bottom.__class__(bars=4, diameter_mm=24),
        shear=ShearReinforcement(diameter_mm=10, legs=2, spacing_mm=200),
    ).validated()
    calculated = DesignBrainService()._calculator.calculate_current(base).result
    assert calculated is not None
    bending_capacity = float(calculated.families["bending"]["phi_Mu_kNm"])
    current = replace(
        base,
        actions=ActionInputs(bending_moment_knm=0.95 * bending_capacity, shear_force_kn=0.0),
    ).validated()
    decision = DesignGuideOrchestrator().decide(current)
    assert decision.family is DesignFamily.SHEAR_OVERDESIGN_GOVERNS
    assert decision.status.value == "ACTION"
    assert decision.apply_allowed
    assert decision.candidate.proposal.shear_diameter_mm == 0
    assert decision.candidate.proposal.shear_legs == 0


def test_action_status_always_has_an_applyable_verified_candidate() -> None:
    current = BeamInputs(actions=ActionInputs(bending_moment_knm=1000.0)).validated()
    decision = DesignGuideOrchestrator().decide(current)
    if decision.status.value == "ACTION":
        assert decision.apply_allowed
        assert decision.candidate is not None


def test_severe_shear_failure_searches_geometry_links_and_longitudinal_steel_together() -> None:
    base = BeamInputs(actions=ActionInputs(bending_moment_knm=10.0, shear_force_kn=600.0))
    current = replace(
        base,
        bottom=replace(base.bottom, bars=2, diameter_mm=12),
    ).validated()
    decision = DesignGuideOrchestrator().decide(current)
    proposed_shear = decision.proposed_result.families["shear"]
    proposed_utilisation = current.actions.shear_force_kn / float(proposed_shear["phi_Vu"])

    assert decision.status.value == "ACTION"
    assert decision.apply_allowed
    assert decision.reason == "shear_target_band_candidate"
    assert 0.85 <= proposed_utilisation <= 1.0
    assert decision.candidate.proposal.depth_mm > current.depth_mm
    assert decision.candidate.proposal.shear_legs > 0
    assert decision.candidate.proposal.bottom_diameter_mm >= current.bottom.diameter_mm


def test_shear_repair_apply_does_not_require_preserved_bending_to_enter_target_band() -> None:
    base = BeamInputs()
    base = replace(
        base,
        bottom=replace(base.bottom, bars=3, diameter_mm=20),
    ).validated()
    calculated = DesignBrainService()._calculator.calculate_current(base).result
    assert calculated is not None
    current = replace(
        base,
        actions=ActionInputs(
            bending_moment_knm=0.75 * float(calculated.families["bending"]["phi_Mu_kNm"]),
            shear_force_kn=15.62 * float(calculated.families["shear"]["phi_Vu"]),
        ),
    ).validated()

    decision = DesignGuideOrchestrator().decide(current)
    proposed_shear_util = current.actions.shear_force_kn / float(
        decision.proposed_result.families["shear"]["phi_Vu"]
    )
    proposed_bending_util = float(decision.proposed_result.families["bending"]["util"])

    assert decision.family is DesignFamily.SHEAR_FAIL_BENDING_OPTIMISE_GOVERNS
    assert decision.status.value == "ACTION"
    assert decision.apply_allowed
    assert 0.85 <= proposed_shear_util <= 1.0
    assert proposed_bending_util <= 1.0
    assert decision.candidate is not None


def test_marginal_shear_failure_finds_coordinated_target_band_repair() -> None:
    base = BeamInputs(
        width_mm=250.0,
        depth_mm=300.0,
        # Keep this fixture inside the authoritative k_u <= 0.36 ductility
        # limit so it isolates the intended marginal shear repair path.
        bottom=LongitudinalReinforcement(bars=4, diameter_mm=16),
        shear=ShearReinforcement(diameter_mm=10, legs=2, spacing_mm=250.0),
    ).validated()
    calculated = DesignBrainService()._calculator.calculate_current(base).result
    assert calculated is not None
    shear_capacity = float(calculated.families["shear"]["phi_Vu"])
    current = replace(
        base,
        actions=ActionInputs(
            bending_moment_knm=1.0,
            shear_force_kn=1.01 * shear_capacity,
        ),
    ).validated()

    decision = DesignGuideOrchestrator().decide(current)
    proposed_shear_util = current.actions.shear_force_kn / float(
        decision.proposed_result.families["shear"]["phi_Vu"]
    )

    assert decision.family is DesignFamily.SHEAR_FAIL_BENDING_OPTIMISE_GOVERNS
    assert decision.status.value == "ACTION"
    assert decision.apply_allowed
    assert decision.reason == "safe_shear_repair_bending_optimised"
    assert 0.85 <= proposed_shear_util <= 1.0
    assert decision.proposed_result.families["shear"]["shear_ok"] is True


def test_combined_overdesign_reaches_both_target_bands_in_one_apply() -> None:
    base = BeamInputs(
        width_mm=300.0,
        depth_mm=500.0,
        bottom=LongitudinalReinforcement(bars=4, diameter_mm=24),
        shear=ShearReinforcement(diameter_mm=12, legs=2, spacing_mm=200.0),
    ).validated()
    calculated = DesignBrainService()._calculator.calculate_current(base).result
    assert calculated is not None
    current = replace(
        base,
        actions=ActionInputs(
            bending_moment_knm=0.40 * float(calculated.families["bending"]["phi_Mu_kNm"]),
            shear_force_kn=0.40 * float(calculated.families["shear"]["phi_Vu"]),
        ),
    ).validated()

    orchestrator = DesignGuideOrchestrator()
    decision = orchestrator.decide(current)
    proposed_bending = float(decision.proposed_result.families["bending"]["util"])
    proposed_shear = current.actions.shear_force_kn / float(
        decision.proposed_result.families["shear"]["phi_Vu"]
    )

    assert decision.family is DesignFamily.COMBINED_OVERDESIGN
    assert decision.status.value == "ACTION"
    assert decision.apply_allowed
    assert 0.85 <= proposed_bending <= 1.0
    assert 0.85 <= proposed_shear <= 1.0
    assert decision.search_evidence.completed_stage_ids == (
        "reduce_shear_reinforcement",
        "reduce_bending_reinforcement",
        "reduce_geometry_and_redesign",
    )
    assert decision.search_evidence.candidates_attempted < 1000


def test_fast_combined_overdesign_continues_to_the_bounded_exact_stop_in_one_apply() -> None:
    """A shallow first frontier must not force a second cleanup Apply."""

    base = BeamInputs(
        width_mm=250.0,
        depth_mm=400.0,
        bottom=LongitudinalReinforcement(bars=3, diameter_mm=16),
        shear=ShearReinforcement(diameter_mm=10, legs=2, spacing_mm=125.0),
    ).validated()
    calculated = DesignBrainService()._calculator.calculate_current(base).result
    assert calculated is not None
    current = replace(
        base,
        actions=ActionInputs(
            bending_moment_knm=0.15 * float(calculated.families["bending"]["phi_Mu_kNm"]),
            shear_force_kn=0.15 * float(calculated.families["shear"]["phi_Vu"]),
        ),
    ).validated()

    profile = SearchProfile.for_mode("Fast")
    decision = DesignGuideOrchestrator(search_profile=profile).decide(current)

    assert decision.family is DesignFamily.COMBINED_OVERDESIGN
    assert decision.apply_allowed
    assert decision.search_evidence.cache_misses <= profile.max_full_evaluations

    outcome = DesignBrainService(search_profile=profile).apply_decision(current, decision)
    assert outcome.applied

    follow_up = DesignGuideOrchestrator(search_profile=profile).decide(outcome.inputs)
    assert follow_up.family is DesignFamily.EXACT_STOP_PROVEN
    assert not follow_up.apply_allowed


def test_fast_combined_low_demand_live_shape_reaches_target_in_one_apply() -> None:
    """Regression for the live 225x425, 5-N12, low-demand two-Apply case."""

    current = BeamInputs(
        width_mm=225.0,
        depth_mm=425.0,
        bottom=LongitudinalReinforcement(bars=5, diameter_mm=12),
        shear=ShearReinforcement(diameter_mm=0, legs=0, spacing_mm=300.0),
        actions=ActionInputs(bending_moment_knm=10.0, shear_force_kn=10.0),
    ).validated()
    profile = SearchProfile.for_mode("Fast")

    decision = DesignGuideOrchestrator(search_profile=profile).decide(current)

    assert decision.family is DesignFamily.COMBINED_OVERDESIGN
    assert decision.apply_allowed
    assert decision.search_evidence.cache_misses <= profile.max_full_evaluations

    outcome = DesignBrainService(search_profile=profile).apply_decision(current, decision)
    assert outcome.applied

    follow_up = DesignGuideOrchestrator(search_profile=profile).decide(outcome.inputs)
    # The corrected strain-compatible capacity proves that this low-load case
    # reaches the bounded safe floor rather than fabricating a target-band hit.
    assert follow_up.family is DesignFamily.EXACT_STOP_PROVEN
    assert not follow_up.apply_allowed


def test_fast_combined_continuation_adds_no_work_when_first_frontier_finds_target() -> None:
    base = BeamInputs(
        width_mm=300.0,
        depth_mm=500.0,
        bottom=LongitudinalReinforcement(bars=4, diameter_mm=24),
        shear=ShearReinforcement(diameter_mm=12, legs=2, spacing_mm=200.0),
    ).validated()
    calculated = DesignBrainService()._calculator.calculate_current(base).result
    assert calculated is not None
    current = replace(
        base,
        actions=ActionInputs(
            bending_moment_knm=0.40 * float(calculated.families["bending"]["phi_Mu_kNm"]),
            shear_force_kn=0.40 * float(calculated.families["shear"]["phi_Vu"]),
        ),
    ).validated()

    one_frontier = SearchProfile(max_combined_continuation_rounds=1)
    continued = SearchProfile()
    baseline = DesignGuideOrchestrator(search_profile=one_frontier).decide(current)
    decision = DesignGuideOrchestrator(search_profile=continued).decide(current)

    assert decision.apply_allowed
    assert decision.candidate == baseline.candidate
    assert (
        decision.search_evidence.candidates_attempted
        == baseline.search_evidence.candidates_attempted
    )


def test_shear_overdesign_with_no_remaining_legal_move_is_a_verified_exact_stop() -> None:
    base = BeamInputs(
        width_mm=150.0,
        depth_mm=225.0,
        bottom=LongitudinalReinforcement(bars=4, diameter_mm=10),
        shear=ShearReinforcement(diameter_mm=0, legs=0, spacing_mm=200.0),
        actions=ActionInputs(bending_moment_knm=10.0, shear_force_kn=10.0),
    ).validated()
    fit = evaluate_arrangement(base, (2, 2))
    assert fit.accepted
    arranged = replace(base, bottom_arrangement=fit.arrangement).validated()
    calculated = DesignBrainService()._calculator.calculate_current(arranged).result
    assert calculated is not None
    current = replace(
        arranged,
        actions=ActionInputs(
            bending_moment_knm=0.90 * float(calculated.families["bending"]["phi_Mu_kNm"]),
            shear_force_kn=0.40 * float(calculated.families["shear"]["phi_Vu"]),
        ),
    ).validated()

    decision = DesignGuideOrchestrator().decide(current)

    assert decision.classification.selected_family is DesignFamily.SHEAR_OVERDESIGN_GOVERNS
    assert decision.family is DesignFamily.EXACT_STOP_PROVEN
    assert decision.status.value == "PASS"
    assert not decision.apply_allowed
    assert decision.search_evidence.exhausted


def test_shear_overdesign_selects_nearest_minimum_reinforcement_compliant_cleanup() -> None:
    base = BeamInputs(
        shear=ShearReinforcement(diameter_mm=16, legs=2, spacing_mm=175),
    )
    # N24 made the original fixture fail the authoritative k_u <= 0.36
    # check, which routes to a mixed bending/shear family.  N20 preserves the
    # shear-only cleanup scenario this test owns.
    base = replace(base, bottom=replace(base.bottom, bars=3, diameter_mm=20)).validated()
    calculated = DesignBrainService()._calculator.calculate_current(base).result
    assert calculated is not None
    current = replace(
        base,
        actions=ActionInputs(
            bending_moment_knm=0.94 * float(calculated.families["bending"]["phi_Mu_kNm"]),
            shear_force_kn=0.40 * float(calculated.families["shear"]["phi_Vu"]),
        ),
        serviceability=ServiceabilityInputs(
            moment_knm=10.0,
            permanent_udl_knm_per_m=5.0,
            equivalent_udl_knm_per_m=5.0,
        ),
    ).validated()

    decision = DesignGuideOrchestrator().decide(current)
    proposed_shear = decision.proposed_result.families["shear"]

    assert decision.family is DesignFamily.SHEAR_OVERDESIGN_GOVERNS
    assert decision.status.value == "ACTION"
    assert decision.apply_allowed
    assert proposed_shear["min_shear_ok"] is True
    assert proposed_shear["spacing_ok"] is True
    assert decision.candidate.proposal.shear_spacing_mm == 200.0
    assert decision.candidate.proposal.shear_spacing_mm != 600.0


def test_mandatory_bending_repair_reaches_available_target_band_in_one_decision() -> None:
    current = BeamInputs(
        width_mm=450.0,
        depth_mm=825.0,
        actions=ActionInputs(bending_moment_knm=50.0),
    ).validated()
    decision = DesignGuideOrchestrator().decide(current)
    proposed_utilisation = float(decision.proposed_result.families["bending"]["util"])

    assert decision.current_result.families["bending"]["minimum_tensile_status"] == "FAIL"
    assert decision.family is DesignFamily.BENDING_FAIL_GOVERNS
    assert decision.status.value == "ACTION"
    assert decision.apply_allowed
    assert proposed_utilisation > float(decision.current_result.families["bending"]["util"])
    assert proposed_utilisation <= 1.0
    assert decision.proposed_result.families["serviceability"]["status"] == "NOT RUN"
    assert decision.proposed_result.families["crack_control"]["status"] == "NOT RUN"


def test_bending_overdesign_preserves_near_limit_shear_in_one_decision() -> None:
    """Regression for the 0.77 bending / 0.99 shear no-Apply case."""
    from inputs_v2.domain.beam_inputs import LongitudinalReinforcement, ShearReinforcement

    current = BeamInputs(
        width_mm=325.0,
        depth_mm=450.0,
        bottom=LongitudinalReinforcement(bars=7, diameter_mm=12),
        shear=ShearReinforcement(diameter_mm=10, legs=2, spacing_mm=250.0),
        actions=ActionInputs(bending_moment_knm=100.0, shear_force_kn=200.0),
    ).validated()
    decision = DesignGuideOrchestrator().decide(current)
    proposed_bending = float(decision.proposed_result.families["bending"]["util"])
    proposed_shear = decision.proposed_result.families["shear"]
    proposed_shear_util = 200.0 / float(proposed_shear["phi_Vu"])

    assert decision.family is DesignFamily.BENDING_OVERDESIGN_GOVERNS
    assert decision.status.value == "ACTION"
    assert decision.apply_allowed
    assert 0.85 <= proposed_bending <= 1.0
    assert proposed_shear_util <= 1.0
    assert decision.candidate.proposal.shear_spacing_mm < current.shear.spacing_mm


def test_bending_cleanup_uses_newly_available_compliant_geometry_candidate() -> None:
    """A real compliant reduction must be actionable rather than called an exact stop."""

    base = BeamInputs(
        width_mm=200.0,
        depth_mm=300.0,
        bottom=LongitudinalReinforcement(bars=2, diameter_mm=16),
        shear=ShearReinforcement(diameter_mm=10, legs=2, spacing_mm=150.0),
    ).validated()
    baseline = DesignBrainService()._calculator.calculate_current(base).result
    current = replace(
        base,
        actions=ActionInputs(
            bending_moment_knm=(
                0.74 * float(baseline.families["bending"]["phi_Mu_kNm"])
            ),
            shear_force_kn=0.98 * float(baseline.families["shear"]["phi_Vu"]),
        ),
    ).validated()

    decision = DesignGuideOrchestrator().decide(current)
    card = build_design_brain_card_view_model(decision, current)
    assert decision.family is DesignFamily.BENDING_OVERDESIGN_GOVERNS
    assert decision.status is DecisionStatus.ACTION
    assert decision.apply_allowed
    assert decision.candidate is not None
    assert decision.candidate.proposal.depth_mm == 400.0
    assert decision.candidate.proposal.bottom_diameter_mm == 12
    assert card.state_class == "optimise"
    assert card.badge == "ACTION"


def test_locked_geometry_still_allows_compliant_reinforcement_cleanup() -> None:
    """Geometry locks must not suppress a valid reinforcement-only cleanup."""

    base = BeamInputs(
        width_mm=300.0,
        depth_mm=500.0,
        width_locked=True,
        depth_locked=True,
        bottom=LongitudinalReinforcement(bars=4, diameter_mm=16),
        shear=ShearReinforcement(diameter_mm=10, legs=2, spacing_mm=300.0),
    ).validated()
    baseline = DesignBrainService()._calculator.calculate_current(base).result
    assert baseline is not None
    current = replace(
        base,
        actions=ActionInputs(
            bending_moment_knm=0.40 * float(baseline.families["bending"]["phi_Mu_kNm"]),
            shear_force_kn=0.40 * float(baseline.families["shear"]["phi_Vu"]),
        ),
    ).validated()

    decision = DesignGuideOrchestrator().decide(current)
    card = build_design_brain_card_view_model(decision, current)

    assert decision.family is DesignFamily.COMBINED_OVERDESIGN
    assert decision.status is DecisionStatus.ACTION
    assert decision.apply_allowed
    assert decision.candidate is not None
    assert decision.candidate.proposal.width_mm == current.width_mm
    assert decision.candidate.proposal.depth_mm == current.depth_mm
    assert decision.candidate.proposal.bottom_diameter_mm == 12
    assert card.state_class == "optimise"
    assert card.badge == "ACTION"


def test_exhausted_shear_cleanup_is_green_pass_with_verified_blockers() -> None:
    """Minimum links/locked width are a verified stop, not a failed design."""

    base = BeamInputs(
        width_mm=300.0,
        depth_mm=500.0,
        width_locked=True,
        depth_locked=True,
        bottom=LongitudinalReinforcement(bars=4, diameter_mm=24),
        shear=ShearReinforcement(diameter_mm=10, legs=2, spacing_mm=300.0),
    ).validated()
    baseline = DesignBrainService()._calculator.calculate_current(base).result
    assert baseline is not None
    current = replace(
        base,
        actions=ActionInputs(
            bending_moment_knm=0.90 * float(baseline.families["bending"]["phi_Mu_kNm"]),
            shear_force_kn=0.40 * float(baseline.families["shear"]["phi_Vu"]),
        ),
    ).validated()

    decision = DesignGuideOrchestrator().decide(current)
    card = build_design_brain_card_view_model(decision, current)

    assert decision.family is DesignFamily.EXACT_STOP_PROVEN
    assert decision.status is DecisionStatus.PASS
    assert not decision.apply_allowed
    assert decision.candidate is None
    assert decision.search_evidence.exhausted
    assert decision.search_evidence.completed_stage_ids == decision.search_evidence.declared_stage_ids
    assert card.state_class == "pass"
    assert card.badge == "PASS"
    assert decision.search_evidence.governing_blocker


@pytest.mark.parametrize(
    ("bending_utilisation", "expected_family"),
    (
        (0.90, DesignFamily.SHEAR_FAIL_GOVERNS),
        (0.40, DesignFamily.SHEAR_FAIL_BENDING_OPTIMISE_GOVERNS),
    ),
)
def test_minimum_shear_failure_below_capacity_runs_the_repair_ladder(
    bending_utilisation: float,
    expected_family: DesignFamily,
) -> None:
    """Detailed shear failures cannot be dismissed by headline utilisation."""

    base = BeamInputs(
        width_mm=300.0,
        depth_mm=500.0,
        bottom=LongitudinalReinforcement(bars=4, diameter_mm=24),
        shear=ShearReinforcement(diameter_mm=10, legs=2, spacing_mm=600.0),
    ).validated()
    baseline = DesignBrainService()._calculator.calculate_current(base).result
    assert baseline is not None
    current = replace(
        base,
        actions=ActionInputs(
            bending_moment_knm=(
                bending_utilisation
                * float(baseline.families["bending"]["phi_Mu_kNm"])
            ),
            shear_force_kn=0.40 * float(baseline.families["shear"]["phi_Vu"]),
        ),
    ).validated()

    decision = DesignGuideOrchestrator().decide(current)

    assert decision.current_result.families["shear"]["min_shear_ok"] is False
    assert decision.family is expected_family
    assert decision.status is DecisionStatus.ACTION
    assert decision.apply_allowed
    assert decision.reason != "shear_not_failed"
    assert decision.proposed_result.families["shear"]["min_shear_ok"] is True
    assert decision.proposed_result.families["shear"]["spacing_ok"] is True


def test_bending_overdesign_reaches_final_safe_floor_without_incremental_loop() -> None:
    current = BeamInputs(
        width_mm=350.0,
        depth_mm=600.0,
        actions=ActionInputs(bending_moment_knm=10.0),
    ).validated()
    orchestrator = DesignGuideOrchestrator()
    decision = orchestrator.decide(current)

    assert decision.status.value == "ACTION"
    proposed_util = float(decision.proposed_result.families["bending"]["util"])
    assert 0.0 < proposed_util <= 1.0
    assert (
        decision.candidate.proposal.width_mm * decision.candidate.proposal.depth_mm
        < current.width_mm * current.depth_mm
    )

    from inputs_v2.application.design_brain_apply import apply_candidate
    applied = apply_candidate(current, decision.candidate)
    assert applied.applied
    terminal = orchestrator.decide(applied.inputs)
    if terminal.apply_allowed:
        # A mandatory k_u repair may be followed by one separate efficiency
        # cleanup; neither decision is allowed to bypass the ductility limit.
        assert terminal.proposed_result.families["ductility"]["status"] == "PASS"
        applied = apply_candidate(applied.inputs, terminal.candidate)
        assert applied.applied
        terminal = orchestrator.decide(applied.inputs)
    assert terminal.status.value == "PASS"
    assert terminal.family is DesignFamily.EXACT_STOP_PROVEN
    assert not terminal.apply_allowed


@pytest.mark.parametrize("moment_knm", (45.0, 55.0))
def test_frozen_bending_overdesign_recipes_complete_in_one_apply(
    moment_knm: float,
) -> None:
    """The R4 live recipes must finish bending and zero-shear cleanup atomically."""

    current = BeamInputs(
        width_mm=300.0,
        depth_mm=400.0,
        bottom=LongitudinalReinforcement(bars=4, diameter_mm=16),
        shear=ShearReinforcement(diameter_mm=10, legs=2, spacing_mm=150.0),
        actions=ActionInputs(
            bending_moment_knm=moment_knm,
            shear_force_kn=0.0,
        ),
    ).validated()
    profile = SearchProfile.for_mode("Fast")
    orchestrator = DesignGuideOrchestrator(search_profile=profile)

    decision = orchestrator.decide(current)

    assert decision.status.value == "ACTION"
    assert decision.apply_allowed
    assert decision.candidate.proposal.shear_diameter_mm == 0
    assert decision.candidate.proposal.shear_legs == 0
    outcome = DesignBrainService(search_profile=profile).apply_decision(
        current,
        decision,
    )
    assert outcome.applied

    terminal = orchestrator.decide(outcome.inputs)
    assert terminal.status.value == "PASS"
    assert not terminal.apply_allowed


def test_bending_only_current_target_band_is_terminal_pass() -> None:
    base = replace(
        BeamInputs(),
        bottom=LongitudinalReinforcement(bars=3, diameter_mm=16),
    ).validated()
    calculated = DesignBrainService()._calculator.calculate_current(base).result
    assert calculated is not None
    current = replace(
        base,
        actions=ActionInputs(
            bending_moment_knm=0.89 * float(calculated.families["bending"]["phi_Mu_kNm"]),
        ),
    ).validated()

    decision = DesignGuideOrchestrator().decide(current)

    assert decision.family is DesignFamily.TARGET_BAND_REACHED
    assert decision.status.value == "PASS"
    assert decision.apply_allowed is False


def test_target_band_does_not_require_passing_sls_checks_to_be_near_failure() -> None:
    """The 0.85--1.00 efficiency band applies to ULS strength, not SLS."""

    base = BeamInputs(
        width_mm=325.0,
        depth_mm=525.0,
        bottom=LongitudinalReinforcement(bars=6, diameter_mm=16),
        shear=ShearReinforcement(diameter_mm=10, legs=2, spacing_mm=300.0),
        serviceability=ServiceabilityInputs(moment_knm=20.0),
    ).validated()
    calculated = DesignBrainService()._calculator.calculate_current(base).result
    assert calculated is not None
    current = replace(
        base,
        actions=ActionInputs(
            bending_moment_knm=(
                0.89 * float(calculated.families["bending"]["phi_Mu_kNm"])
            ),
            shear_force_kn=(
                0.95 * float(calculated.families["shear"]["phi_Vu"])
            ),
        ),
    ).validated()

    current_result = DesignBrainService()._calculator.calculate_current(current).result
    assert current_result is not None
    assert float(current_result.families["crack_control"]["util"]) < 0.85
    assert float(current_result.families["serviceability"]["deflection_util"]) < 0.85

    decision = DesignGuideOrchestrator().decide(current)

    assert decision.family is DesignFamily.TARGET_BAND_REACHED
    assert decision.status.value == "PASS"
    assert not decision.apply_allowed


def test_target_band_retains_current_when_balancing_preview_falls_outside_band(
    monkeypatch,
) -> None:
    """An inferior optional preview cannot turn a verified current design red."""

    base = BeamInputs(
        width_mm=300.0,
        depth_mm=400.0,
        bottom=LongitudinalReinforcement(bars=3, diameter_mm=16),
        shear=ShearReinforcement(diameter_mm=10, legs=2, spacing_mm=200.0),
    ).validated()
    calculated = DesignBrainService()._calculator.calculate_current(base).result
    assert calculated is not None
    current = replace(
        base,
        actions=ActionInputs(
            bending_moment_knm=0.90 * float(calculated.families["bending"]["phi_Mu_kNm"]),
            shear_force_kn=0.90 * float(calculated.families["shear"]["phi_Vu"]),
        ),
    ).validated()

    service = DesignBrainService()
    result = service._calculator.calculate_current(current).result
    assert result is not None
    from inputs_v2.application.design_brain.preview import DesignBrainPreview
    from inputs_v2.application.design_brain_apply import propose_neutral_candidate
    from inputs_v2.application.design_brain.family_owners import FAMILY_OWNERS

    owner = FAMILY_OWNERS[DesignFamily.TARGET_BAND_REACHED]
    inferior = DesignBrainPreview(
        candidate=propose_neutral_candidate(current),
        before=result,
        after=replace(
            result,
            families={
                **result.families,
                "bending": {**result.families["bending"], "util": 0.62},
            },
        ),
        changed_fields=("width_mm",),
        accepted=True,
        reason="safe_overdesign_cleanup",
    )
    monkeypatch.setattr(type(owner), "preview", lambda self, context, service: inferior)

    decision = DesignGuideOrchestrator().decide(current)

    assert decision.status.value == "PASS"
    assert decision.family is DesignFamily.TARGET_BAND_REACHED
    assert not decision.apply_allowed


def test_no_op_preview_cannot_publish_action_without_apply_payload(monkeypatch) -> None:
    """A family-selected current design must never become a fake ACTION."""

    current = BeamInputs(
        actions=ActionInputs(bending_moment_knm=10.0),
    ).validated()
    service = DesignBrainService()
    result = service._calculator.calculate_current(current).result
    assert result is not None

    from inputs_v2.application.design_brain.preview import DesignBrainPreview
    from inputs_v2.application.design_brain_apply import propose_neutral_candidate
    from inputs_v2.application.design_brain.family_context import FamilyRunContext
    from inputs_v2.application.design_brain.family_owners import FAMILY_OWNERS
    from inputs_v2.application.design_brain_families import classify_design_family_selection
    from inputs_v2.domain.design_preferences import DEFAULT_DESIGN_PREFERENCES

    owner = FAMILY_OWNERS[DesignFamily.BENDING_OVERDESIGN_GOVERNS]
    no_op = DesignBrainPreview(
        candidate=propose_neutral_candidate(current),
        before=result,
        after=result,
        changed_fields=("bottom",),
        accepted=True,
        reason="safe_overdesign_cleanup",
    )
    monkeypatch.setattr(type(owner), "preview", lambda self, context, service: no_op)

    decision = owner.decide(
        FamilyRunContext(
            current=current,
            current_result=result,
            classification=classify_design_family_selection(result, current),
            preferences=DEFAULT_DESIGN_PREFERENCES,
            search_profile=service.search_profile,
        ),
        service,
    )

    assert decision.status is not DecisionStatus.ACTION
    assert decision.apply_allowed is False
    assert decision.candidate is no_op.candidate


def test_severe_bending_failure_finds_verified_repair_without_exhausting_budget() -> None:
    """Regression for the repair that previously consumed all 12,000 calculations."""

    current = BeamInputs(
        actions=ActionInputs(bending_moment_knm=1000.0, shear_force_kn=0.0)
    ).validated()

    decision = DesignGuideOrchestrator().decide(current)
    evidence = decision.search_evidence

    assert decision.family is DesignFamily.BENDING_FAIL_GOVERNS
    assert decision.status.value == "ACTION"
    assert decision.apply_allowed
    assert 0.85 <= float(decision.proposed_result.families["bending"]["util"]) <= 1.0
    assert evidence.budget_exhausted is False
    assert evidence.candidates_attempted < 4000
    assert evidence.cache_misses < 4000
    assert evidence.geometry_attempted
    assert evidence.reinforcement_attempted


def test_severe_combined_failure_uses_capacity_probe_before_full_enumeration() -> None:
    current = BeamInputs(
        actions=ActionInputs(bending_moment_knm=1000.0, shear_force_kn=300.0)
    ).validated()

    decision = DesignGuideOrchestrator().decide(current)
    evidence = decision.search_evidence
    proposed_shear = 300.0 / float(
        decision.proposed_result.families["shear"]["phi_Vu"]
    )

    assert decision.family is DesignFamily.BENDING_AND_SHEAR_FAIL_GOVERN
    assert decision.status.value == "ACTION"
    assert decision.apply_allowed
    assert 0.85 <= float(decision.proposed_result.families["bending"]["util"]) <= 1.0
    assert 0.85 <= proposed_shear <= 1.0
    assert evidence.budget_exhausted is False
    assert evidence.candidates_attempted < 1500
    assert evidence.cache_misses < 500
    assert evidence.geometry_attempted
    assert evidence.reinforcement_attempted


@pytest.mark.parametrize(
    ("shear", "shear_force_kn", "expected_family"),
    (
        (ShearReinforcement(), 0.0, DesignFamily.BENDING_FAIL_GOVERNS),
        (
            ShearReinforcement(diameter_mm=10, legs=4, spacing_mm=175.0),
            0.0,
            DesignFamily.BENDING_FAIL_SHEAR_OVERDESIGN_GOVERNS,
        ),
        (
            ShearReinforcement(diameter_mm=10, legs=4, spacing_mm=175.0),
            360.0,
            DesignFamily.BENDING_AND_SHEAR_FAIL_GOVERN,
        ),
    ),
)
def test_all_bending_failure_families_accept_verified_ductility_repair(
    shear: ShearReinforcement,
    shear_force_kn: float,
    expected_family: DesignFamily,
) -> None:
    """A ductility failure is repairable even when flexural capacity passes."""

    from inputs_v2.domain.reinforcement_arrangement import (
        ReinforcementArrangement,
        ReinforcementRow,
    )

    arrangement = ReinforcementArrangement(
        total_bar_count=4,
        bar_diameter_mm=28.0,
        rows=(
            ReinforcementRow(0, 2, 66.0, 64.0, 28.0),
            ReinforcementRow(1, 2, 66.0, 112.0, 28.0),
        ),
        layer_count=2,
        clear_row_gap_mm=20.0,
        reinforcement_centroid_mm=88.0,
        effective_depth_mm=362.0,
    )
    current = BeamInputs(
        width_mm=225.0,
        depth_mm=450.0,
        span_mm=2000.0,
        bottom=LongitudinalReinforcement(bars=4, diameter_mm=28),
        bottom_arrangement=arrangement,
        top=LongitudinalReinforcement(bars=2, diameter_mm=10),
        shear=shear,
        actions=ActionInputs(
            bending_moment_knm=200.0,
            shear_force_kn=shear_force_kn,
        ),
        serviceability=ServiceabilityInputs(moment_knm=100.0),
    ).validated()

    decision = DesignGuideOrchestrator().decide(current)

    assert decision.family is expected_family
    assert decision.status.value == "ACTION"
    assert decision.apply_allowed
    assert decision.proposed_result.families["ductility"]["status"] == "PASS"
    assert float(decision.proposed_result.families["ductility"]["ku"]) <= 0.36
    assert decision.proposed_result.families["bending"]["status"] == "PASS"
    assert (
        decision.candidate.proposal.depth_mm
        <= 2.0 * decision.candidate.proposal.width_mm
    )
    assert decision.search_evidence.budget_exhausted is False


def test_serviceability_failure_uses_verified_repair_not_uls_target_band_gate() -> None:
    """A passing SLS repair must not be rejected for being below 0.85."""

    current = BeamInputs(
        width_mm=300.0,
        depth_mm=500.0,
        bottom=LongitudinalReinforcement(bars=4, diameter_mm=24),
        actions=ActionInputs(bending_moment_knm=100.0),
        serviceability=ServiceabilityInputs(
            moment_knm=500.0,
            permanent_udl_knm_per_m=1.0,
            equivalent_udl_knm_per_m=1.0,
        ),
    ).validated()

    decision = DesignGuideOrchestrator().decide(current)
    evidence = decision.search_evidence
    serviceability = decision.proposed_result.families["serviceability"]
    crack = decision.proposed_result.families["crack_control"]

    assert decision.family is DesignFamily.SERVICEABILITY_GOVERNS
    assert decision.status.value == "ACTION"
    assert decision.apply_allowed
    assert serviceability["status"] == "PASS"
    assert crack["status"] == "PASS"
    assert max(
        float(serviceability["deflection_util"]),
        float(crack["util"]),
    ) <= 1.0
    assert evidence.candidates_attempted < 2000
    assert evidence.budget_exhausted is False


def test_serviceability_repair_preserves_committed_two_row_gap_and_is_applyable() -> None:
    """A candidate cannot gain effective depth from an unpublished row-gap change."""

    base = BeamInputs(
        width_mm=250.0,
        depth_mm=450.0,
        span_mm=2000.0,
        bottom=LongitudinalReinforcement(bars=9, diameter_mm=16, cover_mm=40.0),
        top=LongitudinalReinforcement(bars=2, diameter_mm=10, cover_mm=40.0),
        shear=ShearReinforcement(diameter_mm=0, legs=0, spacing_mm=200.0),
        actions=ActionInputs(bending_moment_knm=190.0),
        serviceability=ServiceabilityInputs(moment_knm=180.0),
    ).validated()
    committed = evaluate_arrangement(base, (5, 4), min_row_gap_mm=60.0)
    assert committed.accepted
    current = replace(base, bottom_arrangement=committed.arrangement).validated()

    decision = DesignGuideOrchestrator().decide(current)
    applied = apply_candidate(current, decision.candidate)

    assert decision.family is DesignFamily.SERVICEABILITY_GOVERNS
    assert decision.status.value == "ACTION"
    assert decision.apply_allowed
    assert decision.changed_fields
    assert applied.applied
    assert applied.inputs.bottom_arrangement is not None
    assert applied.inputs.bottom_arrangement.clear_row_gap_mm == 60.0
    assert decision.proposed_result.families["crack_control"]["status"] == "PASS"
    assert decision.proposed_result.families["serviceability"]["status"] == "PASS"


def test_geometry_failure_returns_one_verified_atomic_repair() -> None:
    current = BeamInputs(
        width_mm=200.0,
        depth_mm=450.0,
        actions=ActionInputs(bending_moment_knm=10.0),
    ).validated()

    decision = DesignGuideOrchestrator().decide(current)

    assert decision.family is DesignFamily.GEOMETRY_DETAILING_GOVERNS
    assert decision.status.value == "ACTION"
    assert decision.apply_allowed
    assert decision.candidate.proposal.depth_mm <= 2.0 * decision.candidate.proposal.width_mm
    assert decision.proposed_result.families["geometry"]["status"] == "PASS"
    assert decision.proposed_result.families["reinforcement_fit"]["accepted"] is True


def test_terminal_execution_uses_the_terminal_family_declared_stage() -> None:
    base = replace(
        BeamInputs(),
        bottom=LongitudinalReinforcement(bars=3, diameter_mm=16),
    ).validated()
    calculated = DesignBrainService()._calculator.calculate_current(base).result
    assert calculated is not None
    current = replace(
        base,
        actions=ActionInputs(
            bending_moment_knm=0.9 * float(calculated.families["bending"]["phi_Mu_kNm"])
        ),
    ).validated()

    decision = DesignGuideOrchestrator().decide(current)

    assert decision.family is DesignFamily.TARGET_BAND_REACHED
    assert decision.search_evidence.generated_candidates == 0
    assert decision.search_evidence.completed_stage_ids == ()
