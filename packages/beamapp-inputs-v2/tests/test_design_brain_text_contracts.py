from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from inputs_v2.application.design_brain.text_contracts import FAMILY_TEXT_CONTRACTS
from inputs_v2.application.design_brain_families import DesignFamily
from inputs_v2.application.design_brain_service import DesignBrainService
from inputs_v2.application.engineering_advice import (
    DesignChange,
    authoritative_checks,
    clause_references_from_checks,
    effects_for_changes,
    format_engineering_advice,
    verified_changes,
    EngineeringAdviceResult,
    EngineeringCheck,
)
from inputs_v2.domain.beam_inputs import BeamInputs, ShearReinforcement
from inputs_v2.application.design_brain_decision import DecisionStatus
from inputs_v2.application.design_guide_orchestrator import DesignGuideOrchestrator
from inputs_v2.domain.beam_inputs import ActionInputs
from inputs_v2.presentation.view_models.design_brain_card import build_design_brain_card_view_model
from inputs_v2.application.design_brain.family_owners import FAMILY_OWNERS
from inputs_v2.application.input_commands import UpdateFirstSlice


EXPECTED = {
    DesignFamily.INPUT_REQUIRED: ("Design actions required", "Design actions required", "Design actions required", ("reinforcement_fit",)),
    DesignFamily.GEOMETRY_DETAILING_GOVERNS: ("Verified geometry and detailing revision", "Geometry and detailing review required", "Geometry and detailing verified", ("geometry", "reinforcement_fit")),
    DesignFamily.SERVICEABILITY_GOVERNS: ("Verified serviceability revision", "Serviceability revision required", "Serviceability checks verified", ("crack_control", "serviceability", "bending", "shear", "reinforcement_fit")),
    DesignFamily.COMBINED_OVERDESIGN: ("Verified combined optimisation", "Combined optimisation review required", "Compliant combined design retained", ("bending", "shear", "ductility", "reinforcement_fit")),
    DesignFamily.BENDING_AND_SHEAR_FAIL_GOVERN: ("Verified combined strength revision", "Combined strength revision required", "Combined strength checks verified", ("bending", "shear", "ductility", "reinforcement_fit")),
    DesignFamily.SHEAR_FAIL_GOVERNS: ("Verified shear revision", "Shear design revision required", "Shear design verified", ("shear", "bending", "ductility", "reinforcement_fit")),
    DesignFamily.SHEAR_FAIL_BENDING_OPTIMISE_GOVERNS: ("Verified shear and bending revision", "Shear and bending revision required", "Shear and bending design verified", ("shear", "bending", "ductility", "reinforcement_fit")),
    DesignFamily.BENDING_FAIL_GOVERNS: ("Verified bending revision", "Bending design revision required", "Bending design verified", ("bending", "ductility", "minimum_tensile", "reinforcement_fit")),
    DesignFamily.BENDING_FAIL_SHEAR_OVERDESIGN_GOVERNS: ("Verified bending and shear revision", "Bending and shear revision required", "Bending and shear design verified", ("bending", "shear", "ductility", "minimum_tensile", "reinforcement_fit")),
    DesignFamily.BENDING_OVERDESIGN_GOVERNS: ("Verified bending optimisation", "Bending optimisation review required", "Compliant bending design retained", ("bending", "shear", "ductility", "minimum_tensile", "reinforcement_fit")),
    DesignFamily.SHEAR_OVERDESIGN_GOVERNS: ("Verified shear optimisation", "Shear optimisation review required", "Compliant shear design retained", ("shear", "bending", "ductility", "reinforcement_fit")),
    DesignFamily.TARGET_BAND_REACHED: ("Target band reached", "Target-band verification required", "Target band reached", ("bending", "shear", "serviceability", "crack_control", "reinforcement_fit")),
    DesignFamily.EXACT_STOP_PROVEN: ("Verified exact stop", "Exact-stop verification required", "Compliant design retained", ("bending", "shear", "ductility", "minimum_tensile", "serviceability", "crack_control", "reinforcement_fit")),
    DesignFamily.LOCKED_NO_REPAIR: ("Verified constrained revision", "Further design review required", "Locked design verified", ("geometry", "bending", "shear", "ductility", "minimum_tensile", "serviceability", "crack_control", "reinforcement_fit")),
}

CHECK_IDS_BY_GROUP = {
    "geometry": {"geometry_proportion"},
    "reinforcement_fit": {"reinforcement_fit", "durability_cover"},
    "bending": {"bending_capacity"},
    "ductility": {"bending_ductility"},
    "minimum_tensile": {"minimum_flexural_strength"},
    "shear": {"shear_strength", "shear_web_crushing", "concrete_shear_capacity", "transverse_reinforcement_required", "minimum_shear_reinforcement", "shear_reinforcement_capacity"},
    "serviceability": {"short_term_deflection", "long_term_deflection", "span_depth_check"},
    "crack_control": {"general_crack_control", "crack_table_method", "direct_crack_width"},
}


@pytest.mark.parametrize("family", tuple(DesignFamily))
def test_every_family_has_a_golden_visible_text_and_detail_contract(family: DesignFamily) -> None:
    contract = FAMILY_TEXT_CONTRACTS[family]
    action, blocked, passed, groups = EXPECTED[family]
    assert (contract.action_title, contract.blocked_title, contract.pass_title, contract.required_checks) == (action, blocked, passed, groups)
    assert contract.engineering_purpose.endswith(".")
    for visible in (action, blocked, passed, contract.engineering_purpose):
        assert family.value not in visible
        assert "_GOVERNS" not in visible


def test_nonterminal_text_details_match_the_family_required_check_contract() -> None:
    for family, owner in FAMILY_OWNERS.items():
        assert FAMILY_TEXT_CONTRACTS[family].required_checks == owner.contract.required_checks


@pytest.mark.parametrize("family", tuple(DesignFamily))
def test_every_family_has_complete_golden_current_and_proposed_check_ids(family: DesignFamily) -> None:
    inputs = BeamInputs().validated()
    result = DesignBrainService()._calculator.calculate_current(inputs).result
    assert result is not None
    groups = FAMILY_TEXT_CONTRACTS[family].required_checks
    expected_ids = set().union(*(CHECK_IDS_BY_GROUP[group] for group in groups))
    current = authoritative_checks(inputs, result, groups)
    proposed = authoritative_checks(inputs, result, groups)
    assert {check.check_id for check in current} == expected_ids
    assert {check.check_id for check in proposed} == expected_ids
    assert all(check.status in {"pass", "fail", "overdesigned", "not_checked", "info", "provisional"} for check in current + proposed)
    assert all(not check.standard or check.clause_reference is not None for check in current + proposed)
    for current_check, proposed_check in zip(current, proposed, strict=True):
        if current_check.clause_reference is not None:
            assert current_check.clause_reference == proposed_check.clause_reference
            assert current_check.clause_reference is not proposed_check.clause_reference


def test_required_checks_and_clauses_are_calculation_owned() -> None:
    inputs = BeamInputs().validated()
    result = DesignBrainService()._calculator.calculate_current(inputs).result
    assert result is not None
    groups = tuple(dict.fromkeys(group for contract in FAMILY_TEXT_CONTRACTS.values() for group in contract.required_checks))
    checks = authoritative_checks(inputs, result, groups)
    ids = {check.check_id for check in checks}
    assert {"bending_capacity", "bending_ductility", "minimum_flexural_strength", "shear_strength", "shear_web_crushing", "short_term_deflection", "direct_crack_width", "reinforcement_fit"} <= ids
    references = clause_references_from_checks(checks)
    assert references
    assert all(reference.standard == "AS 3600" and reference.edition == "2018" for reference in references)
    source = Path("src/inputs_v2/application/engineering_advice.py").read_text(encoding="utf-8")
    assert "AS3600_CLAUSES" not in source
    assert '"8.1.3"' not in source


def test_grouped_changes_render_as_natural_engineering_wording() -> None:
    changes = (
        DesignChange("depth_mm", "beam depth 300.0", "beam depth 450.0", "verified_family_change"),
        DesignChange("bottom_bars", "bottom bar count 3", "bottom bar count 4", "verified_family_change"),
        DesignChange("bottom_diameter_mm", "bottom bar diameter 10", "bottom bar diameter 24", "verified_family_change"),
        DesignChange("shear_diameter_mm", "shear link diameter 0", "shear link diameter 12", "verified_family_change"),
        DesignChange("shear_legs", "shear link legs 0", "shear link legs 2", "verified_family_change"),
        DesignChange("shear_spacing_mm", "shear link spacing 200.0", "shear link spacing 125.0", "verified_family_change"),
    )
    advice = EngineeringAdviceResult((), (), changes, effects_for_changes(changes), "diagnostic", (), True, True, None, "action")
    text = format_engineering_advice(advice)
    assert "Increase the beam depth from 300 mm to 450 mm" in text
    assert "3-N10 to 4-N24 bars" in text
    assert "introduce N12 2-leg closed ligatures at 125 mm centres" in text
    assert "beam depth 300.0 to beam depth 450.0" not in text


def test_clause_metadata_remains_typed_but_is_not_repeated_in_compact_card() -> None:
    missing = EngineeringCheck("unverified", "Unverified code check", standard="AS 3600", status="not_checked")
    advice = EngineeringAdviceResult((missing,), (missing,), (), (), "diagnostic", (), False, False, None, "blocked")
    rendered = format_engineering_advice(advice)
    assert "References:" not in rendered
    assert "Clause reference unavailable" not in rendered
    assert missing.standard == "AS 3600"


def test_coordinated_reinforcement_changes_have_one_explanation_per_system() -> None:
    changes = (
        DesignChange("bottom_bars", "bottom bar count 3", "bottom bar count 4", "verified_family_change"),
        DesignChange("bottom_diameter_mm", "bottom bar diameter 20", "bottom bar diameter 24", "verified_family_change"),
        DesignChange("shear_diameter_mm", "shear link diameter 10", "shear link diameter 12", "verified_family_change"),
        DesignChange("shear_legs", "shear link legs 2", "shear link legs 4", "verified_family_change"),
        DesignChange("shear_spacing_mm", "shear link spacing 200", "shear link spacing 125", "verified_family_change"),
    )
    effects = effects_for_changes(changes, "Repair bending and shear together.")
    assert len(effects) == 2
    assert sum("bottom reinforcement" in effect for effect in effects) == 1
    assert sum("ligature arrangement" in effect for effect in effects) == 1
    assert "Repair bending and shear together." not in effects


def test_single_row_bar_count_change_does_not_repeat_row_layout() -> None:
    current = BeamInputs().validated()
    proposal = UpdateFirstSlice(
        width_mm=current.width_mm,
        depth_mm=current.depth_mm,
        bottom_mode=current.bottom.mode,
        bottom_bars=4,
        bottom_spacing_mm=current.bottom.spacing_mm,
        bottom_diameter_mm=current.bottom.diameter_mm,
        bottom_cover_mm=current.bottom.cover_mm,
        shear_diameter_mm=current.shear.diameter_mm,
        shear_legs=current.shear.legs,
        shear_spacing_mm=current.shear.spacing_mm,
    )
    changes = verified_changes(current, proposal, (4,))
    assert "bottom_bars" in {change.change_type for change in changes}
    assert "layer_count" not in {change.change_type for change in changes}


def test_mandatory_bending_failure_is_not_hidden_by_two_low_summary_utilisations() -> None:
    current = BeamInputs(
        width_mm=500.0,
        actions=ActionInputs(bending_moment_knm=20.0, shear_force_kn=10.0),
        shear=ShearReinforcement(12, 2, 100.0),
    ).validated()
    decision = DesignGuideOrchestrator().decide(current)
    assert decision.current_result.families["bending"]["minimum_tensile_status"] == "FAIL"
    assert decision.family is DesignFamily.BENDING_FAIL_SHEAR_OVERDESIGN_GOVERNS


@pytest.mark.parametrize("family", tuple(DesignFamily))
def test_every_family_compact_card_omits_reference_section(family: DesignFamily) -> None:
    contract = FAMILY_TEXT_CONTRACTS[family]
    advice = EngineeringAdviceResult(
        (), (), (), (contract.engineering_purpose,), family.value, (),
        verified_compliance=True, apply_allowed=False, blocked_reason=None, outcome_type=family.value,
    )
    assert "References:" not in format_engineering_advice(advice)


def test_all_known_blocked_reason_codes_have_specific_family_text() -> None:
    known = {
        "no_bending_demand", "no_valid_bending_candidate", "no_improving_target_band_candidate",
        "no_safe_bending_cleanup", "no_improving_bending_cleanup", "minimum_reinforcement_geometry_exhausted",
        "ductility_geometry_exhausted", "shear_not_failed", "no_valid_shear_repair",
        "no_improving_shear_target_band_candidate", "no_safe_shear_cleanup", "no_improving_shear_cleanup",
        "minimum_shear_reinforcement_exhausted", "no_valid_combined_repair", "no_combined_target_band_candidate",
        "no_safe_combined_cleanup", "no_improving_combined_cleanup", "serviceability_not_failed",
        "serviceability_repair_blocked", "geometry_already_compliant", "geometry_candidate_validation_failed",
    }
    mapped = {blocker.reason_code for contract in FAMILY_TEXT_CONTRACTS.values() for blocker in contract.blockers}
    assert known <= mapped


def test_real_blocked_decision_exposes_typed_specific_blocker_without_raw_code() -> None:
    current = BeamInputs(
        width_locked=True,
        depth_locked=True,
        actions=ActionInputs(bending_moment_knm=1000.0, shear_force_kn=300.0),
    ).validated()
    decision = DesignGuideOrchestrator().decide(current)
    assert decision.status is DecisionStatus.BLOCKED
    assert decision.advice.blocker is not None
    assert decision.advice.blocker.governing_requirement.endswith(".")
    rendered = format_engineering_advice(decision.advice)
    assert decision.reason not in rendered
    assert "beam-width and beam-depth revisions are locked by the user" in rendered
    assert "because No coordinated" not in rendered
    assert "because the required beam-width and beam-depth revisions" in rendered


def test_real_repair_keeps_independent_current_and_proposed_check_results() -> None:
    current = BeamInputs(actions=ActionInputs(bending_moment_knm=1000.0)).validated()
    decision = DesignGuideOrchestrator().decide(current)
    assert decision.status is DecisionStatus.ACTION
    current_bending = next(check for check in decision.advice.current_checks if check.check_id == "bending_capacity")
    proposed_bending = next(check for check in decision.advice.proposed_checks if check.check_id == "bending_capacity")
    assert current_bending.status == "fail"
    assert proposed_bending.status == "pass"
    assert current_bending.clause_reference == proposed_bending.clause_reference
    assert current_bending.clause_reference is not proposed_bending.clause_reference
    assert decision.advice.apply_allowed is True


def test_verified_safe_cleanup_below_target_band_remains_applicable() -> None:
    current = BeamInputs(actions=ActionInputs(bending_moment_knm=1.0)).validated()
    decision = DesignGuideOrchestrator().decide(current)
    assert decision.status is DecisionStatus.ACTION
    assert decision.reason == "safe_overdesign_cleanup"
    assert decision.advice.blocker is None
    assert decision.advice.apply_allowed is True
    assert decision.proposed_result is not None
    assert decision.proposed_result.families["bending"]["util"] < 0.85


def test_blocked_card_labels_trial_as_assessed_and_shows_failed_proposed_result() -> None:
    failed_current = EngineeringCheck(
        "shear_strength", "Overall design shear strength",
        status="fail", utilisation=2.10,
    )
    failed_proposed = EngineeringCheck(
        "shear_strength", "Overall design shear strength",
        status="fail", utilisation=1.34,
    )
    change = DesignChange("width_mm", "beam width 250", "beam width 275", "verified_family_change")
    advice = EngineeringAdviceResult(
        (failed_current,), (failed_proposed,), (change,),
        ("The wider web increases the concrete shear-resisting area.",),
        "diagnostic", (), False, False,
        "No verified shear candidate improved the design into the target band.",
        "blocked",
    )
    rendered = format_engineering_advice(advice)
    assert "Current: Overall design shear strength fails at 2.10 utilisation." in rendered
    assert "Assessed revision: Increase the beam width from 250 mm to 275 mm." in rendered
    assert "Assessed result: Overall design shear strength fails at 1.34 utilisation." in rendered
    assert "Recommended revision:" not in rendered


@pytest.mark.parametrize("family", tuple(DesignFamily))
def test_every_family_preserves_blocked_apply_and_wording_invariant(family: DesignFamily) -> None:
    contract = FAMILY_TEXT_CONTRACTS[family]
    failed = EngineeringCheck("governing", "Governing engineering check", status="fail", utilisation=1.25)
    change = DesignChange("depth_mm", "beam depth 300", "beam depth 350", "verified_family_change")
    advice = EngineeringAdviceResult(
        (failed,), (failed,), (change,), (contract.engineering_purpose,),
        family.value, (), False, False, "the assessed revision remains non-compliant", family.value,
    )
    rendered = format_engineering_advice(advice)
    assert "Assessed revision:" in rendered
    assert "Assessed result:" in rendered
    assert "Recommended revision:" not in rendered
    assert advice.apply_allowed is False


@pytest.mark.parametrize("family", tuple(DesignFamily))
def test_every_family_has_a_golden_card_status_and_apply_projection(family: DesignFamily) -> None:
    contract = FAMILY_TEXT_CONTRACTS[family]
    if family is DesignFamily.INPUT_REQUIRED:
        status, apply_allowed = DecisionStatus.INPUT_REQUIRED, False
    elif family in {DesignFamily.TARGET_BAND_REACHED, DesignFamily.EXACT_STOP_PROVEN}:
        status, apply_allowed = DecisionStatus.PASS, False
    elif family is DesignFamily.LOCKED_NO_REPAIR:
        status, apply_allowed = DecisionStatus.BLOCKED, False
    else:
        status, apply_allowed = DecisionStatus.ACTION, True
    decision = SimpleNamespace(
        status=status,
        apply_allowed=apply_allowed,
        display_heading=contract.title_for(status.value),
        advice=SimpleNamespace(current_checks=()),
    )
    card = build_design_brain_card_view_model(decision, BeamInputs())
    assert card.badge == ("NO LOADS" if status is DecisionStatus.INPUT_REQUIRED else status.value)
    assert card.heading == (
        "Design Brain waiting for actions"
        if status is DecisionStatus.INPUT_REQUIRED
        else contract.title_for(status.value)
    )
    assert card.show_apply is apply_allowed
    assert card.state_class == {
        DecisionStatus.PASS: "pass",
        DecisionStatus.ACTION: "optimise",
        DecisionStatus.BLOCKED: "optimise",
        DecisionStatus.INPUT_REQUIRED: "empty",
    }[status]


@pytest.mark.parametrize(
    ("status", "check_status", "apply_allowed", "expected_colour"),
    (
        (DecisionStatus.ACTION, "fail", True, "fail"),
        (DecisionStatus.BLOCKED, "fail", False, "fail"),
        (DecisionStatus.ACTION, "pass", True, "optimise"),
        (DecisionStatus.BLOCKED, "pass", False, "optimise"),
        (DecisionStatus.PASS, "pass", False, "pass"),
    ),
)
def test_card_colour_describes_current_engineering_state_not_apply_state(
    status: DecisionStatus,
    check_status: str,
    apply_allowed: bool,
    expected_colour: str,
) -> None:
    decision = SimpleNamespace(
        status=status,
        apply_allowed=apply_allowed,
        display_heading="Visible engineering outcome",
        advice=SimpleNamespace(current_checks=(SimpleNamespace(
            status=check_status,
            utilisation=1.2 if check_status == "fail" else 0.5,
            check_id="bending_capacity",
        ),)),
    )
    card = build_design_brain_card_view_model(
        decision,
        BeamInputs(actions=ActionInputs(bending_moment_knm=100.0)),
    )
    assert card.state_class == expected_colour
    assert card.show_apply is apply_allowed


@pytest.mark.parametrize("family", tuple(DesignFamily))
def test_every_family_publishes_its_own_engineering_purpose(family: DesignFamily) -> None:
    contract = FAMILY_TEXT_CONTRACTS[family]
    advice = EngineeringAdviceResult(
        (), (), (), (contract.engineering_purpose,), family.value, (),
        verified_compliance=True, apply_allowed=False, blocked_reason=None, outcome_type=family.value,
    )
    rendered = format_engineering_advice(advice)
    assert contract.engineering_purpose in rendered
    assert family.value not in rendered
