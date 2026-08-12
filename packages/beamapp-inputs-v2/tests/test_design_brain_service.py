from dataclasses import replace

from inputs_v2.application.design_brain.family_owners import FAMILY_OWNERS
from inputs_v2.application.design_brain_families import DesignFamily, classify_design_family_selection
from inputs_v2.application.design_brain_service import DesignBrainService
from inputs_v2.application.design_brain_apply import apply_candidate
from inputs_v2.application.design_brain.preview import DesignBrainPreview
from inputs_v2.application.design_brain_apply import propose_neutral_candidate
from inputs_v2.domain.beam_inputs import BeamInputs
from inputs_v2.domain.beam_inputs import (
    ActionInputs,
    LongitudinalReinforcement,
    ServiceabilityInputs,
    ShearReinforcement,
)
from inputs_v2.application.design_brain.family_context import FamilyRunContext
from inputs_v2.application.design_brain.search_profile import SearchProfile
from inputs_v2.domain.design_preferences import DEFAULT_DESIGN_PREFERENCES
from inputs_v2.engineering.reinforcement_fit import evaluate_arrangement


def _owned_preview(family: DesignFamily, current: BeamInputs, service: DesignBrainService | None = None):
    service = service or DesignBrainService()
    result = service._calculator.calculate_current(current).result
    assert result is not None
    return FAMILY_OWNERS[family].preview(
        FamilyRunContext(
            current,
            result,
            classify_design_family_selection(result, current),
            DEFAULT_DESIGN_PREFERENCES,
            SearchProfile(),
        ),
        service,
    )


def test_design_brain_preview_is_calculator_backed() -> None:
    current = BeamInputs().validated()
    preview = _owned_preview(DesignFamily.BENDING_FAIL_GOVERNS, current)
    assert preview.accepted is False
    assert preview.reason == "no_bending_demand"
    assert preview.candidate.source_hash == current.content_hash
    assert preview.after.source_revision == current.revision
    assert preview.after.families["bending"]


def test_design_brain_uses_configured_private_sls_proxy_without_publishing_it() -> None:
    current = BeamInputs(
        actions=ActionInputs(bending_moment_knm=10.0, shear_force_kn=5.0),
        serviceability=ServiceabilityInputs(use_uls_fallback=True),
    ).validated()
    service = DesignBrainService()

    canonical = service._calculator.calculate_current(current).result
    provisional = service._calculate_for_design_brain(current)

    assert canonical is not None
    assert provisional is not None
    assert canonical.families["serviceability"]["status"] == "NOT RUN"
    assert canonical.families["crack_control"]["status"] == "NOT RUN"
    assert canonical.families["serviceability"]["action_source"] == "NOT_PROVIDED"
    assert canonical.families["crack_control"]["action_source"] == "NOT_PROVIDED"
    assert provisional.families["serviceability"]["action_source"] == "PROVISIONAL_ULS_RATIO_PROXY"
    assert provisional.families["crack_control"]["action_source"] == "PROVISIONAL_ULS_RATIO_PROXY"
    assert provisional.families["serviceability"]["proxy_ratio"] == 0.60
    assert provisional.source_hash == current.content_hash
    assert service.last_search_metrics["sls_source"] == "PROVISIONAL_ULS_RATIO_PROXY"


def test_actual_sls_actions_replace_the_proxy() -> None:
    current = BeamInputs(
        actions=ActionInputs(bending_moment_knm=10.0),
        serviceability=ServiceabilityInputs(
            moment_knm=6.0,
            use_uls_fallback=True,
        ),
    ).validated()
    service = DesignBrainService()

    result = service._calculate_for_design_brain(current)

    assert result is not None
    assert result.families["serviceability"]["serviceability_loads_present"] is True
    assert result.families["serviceability"]["action_source"] == "ACTUAL_SLS_ACTIONS"
    assert result.families["crack_control"]["action_source"] == "ACTUAL_SLS_ACTIONS"
    assert "sls_source" not in service.last_search_metrics


def test_explicit_sls_publication_preserves_the_family_verified_result() -> None:
    """Publication must not become a second decision centre for real SLS."""

    current = BeamInputs(
        actions=ActionInputs(bending_moment_knm=190.0),
        serviceability=ServiceabilityInputs(moment_knm=150.0),
    ).validated()
    service = DesignBrainService()
    verified = service._calculate_for_design_brain(current)
    assert verified is not None
    preview = DesignBrainPreview(
        propose_neutral_candidate(current),
        verified,
        verified,
        (),
        False,
        "test_verified_explicit_sls",
    )

    class PublicationMustNotRecalculate:
        def calculate_current(self, _inputs):
            raise AssertionError("explicit-SLS publication recalculated the family result")

    service._calculator = PublicationMustNotRecalculate()

    assert service.publish_preview(current, preview) is preview


def test_design_brain_apply_rejects_preview_from_changed_revision() -> None:
    service = DesignBrainService()
    current = BeamInputs().validated()
    preview = service.preview(current)
    changed = current.next_revision(width_mm=current.width_mm, depth_mm=current.depth_mm, bottom=current.bottom)
    outcome = service.apply(changed, preview)
    assert outcome.applied is False
    assert outcome.reason in {"stale_candidate", "candidate_validation_failed"}


def test_bending_ladder_requires_target_band() -> None:
    current = BeamInputs(actions=ActionInputs(bending_moment_knm=20.0)).validated()
    preview = _owned_preview(DesignFamily.BENDING_FAIL_GOVERNS, current)
    assert preview.target_low == 0.85
    assert preview.target_high == 1.0
    if preview.accepted:
        util = preview.after.families["bending"]["util"]
        assert 0.85 <= util <= 1.0


def test_geometry_ladder_never_exceeds_two_to_one_depth_width_ratio() -> None:
    current = BeamInputs(actions=ActionInputs(bending_moment_knm=300.0)).validated()
    preview = _owned_preview(DesignFamily.BENDING_FAIL_GOVERNS, current)
    proposed_depth = preview.candidate.proposal.depth_mm
    assert proposed_depth <= 2.0 * current.width_mm
    if preview.accepted:
        assert 0.85 <= preview.after.families["bending"]["util"] <= 1.0


def test_shear_only_ladder_uses_v1_order_and_target_band() -> None:
    from inputs_v2.domain.beam_inputs import ShearReinforcement

    current = BeamInputs(
        actions=ActionInputs(shear_force_kn=500.0),
        shear=ShearReinforcement(diameter_mm=10, legs=2, spacing_mm=300.0),
    ).validated()
    preview = DesignBrainService().preview_shear_only(current)
    assert preview.candidate.source_hash == current.content_hash
    if preview.accepted:
        family = preview.after.families["shear"]
        util = current.actions.shear_force_kn / family["phi_Vu"]
        assert 0.85 <= util <= 1.0

def test_shear_width_lane_can_progress_beyond_one_hundred_mm_when_needed() -> None:
    current = BeamInputs(width_mm=250.0, actions=ActionInputs(shear_force_kn=300.0)).validated()
    preview = DesignBrainService().preview_shear_only(current)
    # A valid link repair is preferred, but the candidate search must expose
    # the wider geometry envelope instead of hard-stopping at 350 mm.
    assert preview.candidate.proposal.width_mm <= 500.0

def test_shear_width_lane_combines_width_with_link_repair() -> None:
    current = BeamInputs(
        width_mm=250.0,
        depth_mm=400.0,
        bottom=BeamInputs().bottom.__class__(bars=3, diameter_mm=28),
        actions=ActionInputs(bending_moment_knm=200.0, shear_force_kn=300.0),
    ).validated()
    preview = DesignBrainService().preview_shear_only(current)
    assert preview.accepted
    assert preview.candidate.proposal.shear_diameter_mm > 0
    assert preview.candidate.proposal.shear_legs >= 2
    shear_util = 300.0 / float(preview.after.families["shear"]["phi_Vu"])
    assert 0.85 <= shear_util <= 1.0

def test_geometry_locks_are_respected_by_shear_ladder() -> None:
    current = BeamInputs(
        width_mm=250.0, depth_mm=400.0, width_locked=True, depth_locked=True,
        actions=ActionInputs(shear_force_kn=300.0),
    ).validated()
    preview = DesignBrainService().preview_shear_only(current)
    assert preview.candidate.proposal.width_mm == current.width_mm
    assert preview.candidate.proposal.depth_mm == current.depth_mm

def test_bending_ladder_expands_width_when_depth_ratio_is_reached() -> None:
    current = BeamInputs(
        width_mm=250.0,
        depth_mm=300.0,
        actions=ActionInputs(bending_moment_knm=800.0),
    ).validated()
    preview = _owned_preview(DesignFamily.BENDING_FAIL_GOVERNS, current)
    proposal = preview.candidate.proposal
    assert proposal.width_mm > current.width_mm
    assert proposal.depth_mm <= 2.0 * proposal.width_mm
    assert preview.accepted
    assert 0.85 <= preview.after.families["bending"]["util"] <= 1.0

def test_shear_overdesign_does_not_add_unrequested_bottom_bar():
    current = BeamInputs(
        bottom=BeamInputs().bottom.__class__(bars=4),
        actions=ActionInputs(shear_force_kn=0.0),
    ).validated()
    preview = _owned_preview(DesignFamily.SHEAR_OVERDESIGN_GOVERNS, current)
    assert preview.candidate.proposal.bottom_bars == current.bottom.bars

def test_zero_shear_overdesign_can_still_apply_link_removal():
    base = BeamInputs(
        width_mm=300.0,
        depth_mm=500.0,
        bottom=LongitudinalReinforcement(bars=4, diameter_mm=24),
        shear=ShearReinforcement(diameter_mm=16, legs=4, spacing_mm=200.0),
    ).validated()
    service = DesignBrainService()
    result = service._calculator.calculate_current(base).result
    assert result is not None
    current = replace(
        base,
        actions=ActionInputs(
            bending_moment_knm=0.90 * float(result.families["bending"]["phi_Mu_kNm"]),
            shear_force_kn=0.0,
        ),
    ).validated()
    preview = _owned_preview(DesignFamily.SHEAR_OVERDESIGN_GOVERNS, current, service)
    assert preview.accepted
    assert (
        preview.candidate.proposal.shear_diameter_mm != current.shear.diameter_mm
        or preview.candidate.proposal.shear_legs != current.shear.legs
        or preview.candidate.proposal.shear_spacing_mm != current.shear.spacing_mm
    )


def test_combined_failure_ladder_is_atomic() -> None:
    current = BeamInputs(actions=ActionInputs(bending_moment_knm=1000.0, shear_force_kn=300.0)).validated()
    preview = DesignBrainService().preview_combined_failure(current)
    assert preview.candidate.source_revision == current.revision
    if preview.accepted:
        assert "bottom" in preview.changed_fields and "shear" in preview.changed_fields
    else:
        assert preview.changed_fields == ()
        assert preview.reason == "no_valid_combined_repair"


def test_combined_failure_finds_applicable_target_band_repair() -> None:
    current = BeamInputs(
        actions=ActionInputs(bending_moment_knm=300.0, shear_force_kn=300.0)
    ).validated()

    preview = DesignBrainService().preview_combined_failure(current)

    assert preview.accepted
    assert preview.candidate is not None
    assert preview.after is not None
    assert "bottom" in preview.changed_fields
    assert "shear" in preview.changed_fields
    bending_util = float(preview.after.families["bending"]["util"])
    shear_family = preview.after.families["shear"]
    shear_util = abs(current.actions.shear_force_kn) / float(shear_family["phi_Vu"])
    assert 0.85 <= bending_util <= 1.0
    assert 0.85 <= shear_util <= 1.0


def test_overdesign_ladders_only_accept_safe_reductions() -> None:
    from inputs_v2.domain.beam_inputs import ShearReinforcement

    current = BeamInputs(
        bottom=BeamInputs().bottom,
        shear=ShearReinforcement(diameter_mm=16, legs=6, spacing_mm=100.0),
    ).validated()
    service = DesignBrainService()
    bending = _owned_preview(
        DesignFamily.BENDING_OVERDESIGN_GOVERNS, current, service
    )
    shear = _owned_preview(
        DesignFamily.SHEAR_OVERDESIGN_GOVERNS, current, service
    )
    if bending.accepted:
        assert bending.after.families["bending"]["util"] <= 1.0
    if shear.accepted:
        sf = shear.after.families["shear"]
        assert current.actions.shear_force_kn / sf["phi_Vu"] <= 1.0


def test_bending_overdesign_allows_fewer_larger_bars_when_total_steel_reduces() -> None:
    """Regression: a larger diameter remains legal when total steel reduces."""
    current = BeamInputs(
        width_mm=275.0,
        depth_mm=475.0,
        actions=ActionInputs(bending_moment_knm=300.0, shear_force_kn=200.0),
        bottom=LongitudinalReinforcement(bars=4, diameter_mm=28),
        top=LongitudinalReinforcement(bars=2, diameter_mm=10),
        shear=ShearReinforcement(diameter_mm=10, legs=2, spacing_mm=200.0),
    ).validated()

    preview = _owned_preview(DesignFamily.BENDING_OVERDESIGN_GOVERNS, current)

    assert preview.accepted
    assert preview.candidate.proposal.bottom_bars < 4
    assert preview.candidate.proposal.bottom_diameter_mm > 28
    assert preview.candidate.proposal.bottom_bars * preview.candidate.proposal.bottom_diameter_mm**2 < 4 * 28**2
    assert 0.85 <= float(preview.after.families["bending"]["util"]) <= 1.0


def test_bending_overdesign_reaches_terminal_band_in_one_family_apply() -> None:
    """A coordinated two-row cleanup must not require another family run."""
    base = BeamInputs(
        width_mm=275.0,
        depth_mm=475.0,
        actions=ActionInputs(bending_moment_knm=200.0, shear_force_kn=0.0),
        bottom=LongitudinalReinforcement(bars=7, diameter_mm=20),
    ).validated()
    current = replace(
        base,
        bottom_arrangement=evaluate_arrangement(base, (4, 3)).arrangement,
    ).validated()

    preview = _owned_preview(DesignFamily.BENDING_OVERDESIGN_GOVERNS, current)

    assert preview.accepted
    assert 0.85 <= float(preview.after.families["bending"]["util"]) <= 1.0
    applied = apply_candidate(current, preview.candidate)
    assert applied.applied
    result = DesignBrainService()._calculator.calculate_current(applied.inputs).result
    assert result is not None
    assert (
        classify_design_family_selection(result, applied.inputs).selected_family
        is DesignFamily.TARGET_BAND_REACHED
    )


def test_serviceability_ladder_is_safe_when_deflection_fails() -> None:
    current = BeamInputs(actions=ActionInputs(bending_moment_knm=5000.0)).validated()
    preview = DesignBrainService().preview_serviceability(current)
    assert preview.candidate.source_revision == current.revision
    if preview.accepted:
        assert preview.after.families["serviceability"]["deflection_util"] <= 1.0
