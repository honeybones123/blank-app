"""Safety-first Design Brain candidate ranking policy."""

from __future__ import annotations

from typing import TYPE_CHECKING

from inputs_v2.application.candidate_evaluation import complete_compliance
from inputs_v2.application.design_brain_apply import Candidate
from inputs_v2.application.ranking_policy import CandidateEvidence
from inputs_v2.domain.beam_inputs import BeamInputs
from inputs_v2.domain.engineering_result import EngineeringResult

if TYPE_CHECKING:
    from inputs_v2.application.design_brain.family_owners import FamilyContract


def candidate_rank_key(
    current: BeamInputs,
    candidate: Candidate,
    result: EngineeringResult,
    target_distance: float,
    edit_size: float,
    *,
    family_contract: FamilyContract | None = None,
) -> tuple:
    """Return the shared safety-first ordering key for one candidate."""
    evidence = CandidateEvidence(
        candidate_id=candidate.candidate_id,
        compliant=complete_compliance(result),
        mandatory_checks_complete=complete_compliance(result),
        edit_count=round(float(edit_size) * 1000),
        constructability_penalty=0.25 if len(candidate.row_counts) > 1 else 0.0,
        geometry_change_penalty=(
            abs(float(candidate.proposal.width_mm) - float(current.width_mm))
            + abs(float(candidate.proposal.depth_mm) - float(current.depth_mm))
        ) / 100.0,
        material_quantity=float(
            candidate.proposal.bottom_bars * candidate.proposal.bottom_diameter_mm**2
        ),
        target_distance=float(target_distance),
    )
    if family_contract is not None:
        return family_contract.ranking_policy.rank_key(evidence)
    return evidence.rank_key


def bending_candidate_rank_key(
    current: BeamInputs,
    candidate: Candidate,
    result: EngineeringResult,
    target_distance: float,
    edit_size: float,
) -> tuple:
    """Rank a bending candidate using its strength, fit and minimum-steel gates."""
    bending = result.families.get("bending", {})
    bending_util = float(bending.get("util", 0.0) or 0.0)
    fit_ok = bool(result.families.get("reinforcement_fit", {}).get("accepted", False))
    minimum_steel_ok = str(
        bending.get("minimum_tensile_status", "PASS")
    ).upper() != "FAIL"
    evidence = CandidateEvidence(
        candidate_id=candidate.candidate_id,
        compliant=bending_util <= 1.0 and fit_ok and minimum_steel_ok,
        mandatory_checks_complete=fit_ok and minimum_steel_ok,
        new_near_failure_count=0,
        edit_count=round(edit_size * 1000),
        constructability_penalty=0.25 if len(candidate.row_counts) > 1 else 0.0,
        geometry_change_penalty=(
            abs(candidate.proposal.depth_mm - current.depth_mm) / 100.0
        ),
        material_quantity=float(
            candidate.proposal.bottom_bars * candidate.proposal.bottom_diameter_mm**2
        ),
        target_distance=target_distance,
    )
    return evidence.rank_key


__all__ = ["bending_candidate_rank_key", "candidate_rank_key"]
