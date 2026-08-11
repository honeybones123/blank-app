from inputs_v2.application.design_brain_families import DesignFamily
from inputs_v2.application.design_brain_decision import DecisionStatus
from dataclasses import replace
import pytest

from inputs_v2.application.design_guide_orchestrator import DesignGuideOrchestrator
from inputs_v2.application.design_brain_service import DesignBrainService
from inputs_v2.application.design_brain.family_owners import FAMILY_OWNERS
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
        width_mm=350.0,
        depth_mm=600.0,
    ).validated()
    result = DesignBrainService()._calculator.calculate_current(base).result
    assert result is not None
    shear_capacity = float(result.families["shear"]["phi_Vu"])
    current = replace(base, actions=ActionInputs(bending_moment_knm=1.0, shear_force_kn=0.96 * shear_capacity)).validated()
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
    assert proposed_bending_util < 0.85
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
    assert 0.85 <= proposed_util <= 1.0
    assert (
        decision.candidate.proposal.width_mm * decision.candidate.proposal.depth_mm
        < current.width_mm * current.depth_mm
    )

    from inputs_v2.application.design_brain_apply import apply_candidate
    applied = apply_candidate(current, decision.candidate)
    assert applied.applied
    terminal = orchestrator.decide(applied.inputs)
    assert terminal.status.value == "PASS"
    assert terminal.family is DesignFamily.TARGET_BAND_REACHED
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
