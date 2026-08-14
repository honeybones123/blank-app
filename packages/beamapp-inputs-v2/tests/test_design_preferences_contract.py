from dataclasses import FrozenInstanceError

import pytest

from inputs_v2.application.design_brain.family_owners import (
    FAMILY_CONTRACTS,
    TERMINAL_FAMILIES,
    NearLimitComparison,
    NearLimitDirection,
    RankingPolicy,
)
from inputs_v2.application.design_brain_families import DesignFamily
from inputs_v2.application.design_brain.search_profile import SearchKind
from inputs_v2.application.design_guide_orchestrator import DesignGuideOrchestrator
from inputs_v2.application.ranking_policy import CandidateEvidence
from inputs_v2.domain.beam_inputs import BeamInputs
from inputs_v2.domain.design_preferences import DesignPreferenceProfile


def test_preference_profile_is_immutable_configuration_only() -> None:
    profile = DesignPreferenceProfile()
    with pytest.raises(FrozenInstanceError):
        profile.dimension_increment_mm = 50.0  # type: ignore[misc]
    assert not hasattr(profile, "rank_key")
    assert not hasattr(profile, "select_family")
    assert not hasattr(profile, "publish")


def test_family_ranking_rejects_hard_congestion_before_soft_preferences() -> None:
    policy = RankingPolicy()
    hard_failure = CandidateEvidence(
        "hard",
        True,
        True,
        target_distance=0.0,
        hard_congestion_rejection_codes=("clear_spacing_failed",),
    )
    soft_but_safe = CandidateEvidence(
        "soft",
        True,
        True,
        target_distance=0.1,
        soft_congestion_score=0.75,
        soft_congestion_reasons=("high_congestion",),
    )
    selected = policy.select((hard_failure, soft_but_safe))
    assert selected is soft_but_safe


def test_family_enforces_width_appropriate_link_count_when_safe_option_exists() -> None:
    policy = RankingPolicy()
    width_appropriate = CandidateEvidence(
        "three-legs",
        True,
        True,
        target_distance=0.15,
    )
    width_inappropriate = CandidateEvidence(
        "six-legs",
        True,
        True,
        target_distance=0.0,
        conditional_preference_violation_codes=(
            "ligature_leg_count_outside_practical_width_range",
        ),
    )
    assert policy.select((width_inappropriate, width_appropriate)) is width_appropriate


def test_family_can_relax_width_leg_preference_when_only_safe_option() -> None:
    policy = RankingPolicy()
    width_inappropriate = CandidateEvidence(
        "six-legs",
        True,
        True,
        conditional_preference_violation_codes=(
            "ligature_leg_count_outside_practical_width_range",
        ),
    )
    failing_preferred = CandidateEvidence("three-legs", False, False)
    assert policy.select((width_inappropriate, failing_preferred)) is width_inappropriate


def test_near_limit_rules_are_explicit_compatible_whitelists() -> None:
    for contract in FAMILY_CONTRACTS.values():
        for rule in contract.near_limit_policy.rules:
            assert rule.direction is NearLimitDirection.UPPER_BOUND
            assert rule.comparison_method is NearLimitComparison.NORMALISED_UTILISATION
            assert rule.threshold == 0.95

    assert not FAMILY_CONTRACTS[
        DesignFamily.COMBINED_OVERDESIGN
    ].near_limit_policy.rules


def test_target_band_is_conditionally_optimising_not_unconditionally_terminal() -> None:
    assert DesignFamily.TARGET_BAND_REACHED not in TERMINAL_FAMILIES
    contract = FAMILY_CONTRACTS[DesignFamily.TARGET_BAND_REACHED]
    assert contract.search_kind is SearchKind.OPTIMISATION
    assert tuple(stage.stage_id for stage in contract.ladder_stages) == (
        "proportion_balance_target_band",
    )


def test_profile_provenance_is_preserved_in_internal_decision_evidence() -> None:
    profile = DesignPreferenceProfile(
        preference_profile_id="project-standard",
        preference_profile_version="2.3",
    )
    decision = DesignGuideOrchestrator(preference_profile=profile).decide(
        BeamInputs().validated()
    )
    assert decision.search_evidence.preference_profile_id == "project-standard"
    assert decision.search_evidence.preference_profile_version == "2.3"
    assert decision.search_evidence.generated_candidates == 0
    assert decision.search_evidence.full_evaluations == 0


def test_current_similarity_is_the_final_engineering_tie_break() -> None:
    criteria = RankingPolicy().criteria
    assert criteria[-2:] == ("fewest_changes", "candidate_id")

