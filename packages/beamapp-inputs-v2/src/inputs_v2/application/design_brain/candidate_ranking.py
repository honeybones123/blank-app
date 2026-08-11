"""Safety-first Design Brain candidate ranking policy."""

from __future__ import annotations

from typing import TYPE_CHECKING

from inputs_v2.application.candidate_evaluation import (
    complete_compliance,
    compliance_rejection_codes,
)
from inputs_v2.application.design_brain_apply import Candidate
from inputs_v2.application.ranking_policy import CandidateEvidence
from inputs_v2.domain.beam_inputs import BeamInputs
from inputs_v2.domain.engineering_result import EngineeringResult
from inputs_v2.domain.design_preferences import DesignPreferenceProfile

if TYPE_CHECKING:
    from inputs_v2.application.design_brain.family_owners import FamilyContract


def candidate_evidence(
    current: BeamInputs,
    candidate: Candidate,
    result: EngineeringResult,
    target_distance: float,
    edit_size: float,
    *,
    family_contract: FamilyContract,
    current_result: EngineeringResult,
    preferences: DesignPreferenceProfile,
) -> CandidateEvidence:
    """Build factual evidence using the selected family's explicit policies."""
    congestion = str(
        result.families.get("reinforcement_fit", {}).get(
            "congestion_class", "low"
        )
    ).lower()
    soft_score = {
        "low": 0.0,
        "moderate": preferences.soft_congestion_moderate_penalty,
        "high": preferences.soft_congestion_high_penalty,
    }.get(congestion, 0.0)
    soft_reasons: list[str] = []
    if soft_score > 0.0:
        soft_reasons.append(f"{congestion}_congestion")

    # These are buildability preferences only. They are applied after every
    # mandatory check passes and therefore cannot turn a safe arrangement
    # into a compliance failure.
    bottom_diameter = int(candidate.proposal.bottom_diameter_mm)
    if bottom_diameter in preferences.preferred_longitudinal_diameters:
        diameter_penalty = 0.0
    elif bottom_diameter in preferences.distribution_longitudinal_diameters:
        diameter_penalty = 0.10
    elif bottom_diameter in preferences.heavy_longitudinal_diameters:
        diameter_penalty = 0.20
    elif bottom_diameter in preferences.specialist_longitudinal_diameters:
        diameter_penalty = 0.35
    else:
        diameter_penalty = preferences.soft_congestion_high_penalty
    if diameter_penalty:
        soft_score += diameter_penalty
        soft_reasons.append("nonpreferred_longitudinal_diameter")

    row_counts = candidate.row_counts or (int(candidate.proposal.bottom_bars),)
    if len(row_counts) not in preferences.preferred_layer_counts:
        soft_score += preferences.soft_congestion_moderate_penalty
        soft_reasons.append("nonpreferred_layer_count")
    if any(
        count < preferences.preferred_bars_per_layer_min
        or count > preferences.preferred_bars_per_layer_max
        for count in row_counts
    ):
        soft_score += preferences.soft_congestion_moderate_penalty
        soft_reasons.append("nonpreferred_bars_per_layer")

    link_diameter = int(candidate.proposal.shear_diameter_mm)
    if link_diameter > 0:
        if link_diameter not in (
            preferences.preferred_link_diameters
            + preferences.heavy_link_diameters
            + preferences.exceptional_link_diameters
        ):
            soft_score += preferences.soft_congestion_high_penalty
            soft_reasons.append("nonstandard_ligature_diameter")
        if float(candidate.proposal.shear_spacing_mm) not in preferences.standard_link_spacings_mm:
            soft_score += preferences.soft_congestion_moderate_penalty
            soft_reasons.append("nonstandard_ligature_spacing")
    rejection_codes = compliance_rejection_codes(result)
    hard_congestion = tuple(
        code
        for code in rejection_codes
        if code in {
            "reinforcement_fit_failed",
            "cover_failed",
            "clear_spacing_failed",
            "row_spacing_failed",
            "anchorage_failed",
            "constructability_limit_failed",
        }
    )
    near_limit = family_contract.near_limit_policy.assess(
        current_result,
        result,
        repair_domains=family_contract.improvement_policy.active_domains,
        target_high=family_contract.target_high,
    )
    return CandidateEvidence(
        candidate_id=candidate.candidate_id,
        compliant=complete_compliance(result),
        mandatory_checks_complete=complete_compliance(result),
        edit_count=round(float(edit_size) * 1000),
        constructability_penalty=soft_score,
        hard_congestion_rejection_codes=hard_congestion,
        soft_congestion_score=soft_score,
        soft_congestion_reasons=tuple(soft_reasons),
        near_limit_evidence=near_limit,
        new_near_failure_count=sum(
            1 for event in near_limit if event.penalty_applied
        ),
        geometry_change_penalty=(
            abs(float(candidate.proposal.width_mm) - float(current.width_mm))
            + abs(float(candidate.proposal.depth_mm) - float(current.depth_mm))
        ) / 100.0,
        material_quantity=float(
            candidate.proposal.bottom_bars * candidate.proposal.bottom_diameter_mm**2
        ),
        target_distance=float(target_distance),
    )


def candidate_rank_key(
    current: BeamInputs,
    candidate: Candidate,
    result: EngineeringResult,
    target_distance: float,
    edit_size: float,
    *,
    family_contract: FamilyContract,
    current_result: EngineeringResult,
    preferences: DesignPreferenceProfile,
) -> tuple:
    """Return only the selected family's contract-bound comparison key."""

    evidence = candidate_evidence(
        current,
        candidate,
        result,
        target_distance,
        edit_size,
        family_contract=family_contract,
        current_result=current_result,
        preferences=preferences,
    )
    return family_contract.ranking_policy.rank_key(evidence)


__all__ = ["candidate_evidence", "candidate_rank_key"]
