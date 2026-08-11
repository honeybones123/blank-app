"""Authoritative, presentation-neutral Design Brain decision contract."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from inputs_v2.application.design_brain_apply import Candidate
from inputs_v2.application.design_brain_families import DesignFamily
from inputs_v2.application.engineering_advice import EngineeringAdviceResult
from inputs_v2.application.ranking_policy import CandidateEvidence
from inputs_v2.domain.engineering_result import EngineeringResult


class DecisionStatus(StrEnum):
    ACTION = "ACTION"
    PASS = "PASS"
    BLOCKED = "BLOCKED"
    INPUT_REQUIRED = "INPUT_REQUIRED"
    PROVISIONAL = "PROVISIONAL"


@dataclass(frozen=True, slots=True)
class StageSearchEvidence:
    """Proof that one declared family stage ran or why it could not run."""

    stage_id: str
    candidates_attempted: int = 0
    candidates_calculated: int = 0
    candidates_valid: int = 0
    rejection_counts: tuple[tuple[str, int], ...] = ()
    completed: bool = False
    stop_reason: str | None = None


@dataclass(frozen=True, slots=True)
class SearchEvidence:
    """Auditable proof of what the selected family searched."""

    candidates_attempted: int = 0
    candidates_valid: int = 0
    geometry_attempted: bool = False
    reinforcement_attempted: bool = False
    governing_blocker: str | None = None
    exhausted: bool = False
    declared_stage_ids: tuple[str, ...] = ()
    attempted_stage_ids: tuple[str, ...] = ()
    completed_stage_ids: tuple[str, ...] = ()
    stage_attempt_counts: tuple[tuple[str, int], ...] = ()
    stage_valid_counts: tuple[tuple[str, int], ...] = ()
    rejection_counts: tuple[tuple[str, int], ...] = ()
    improving_rejection_counts: tuple[tuple[str, int], ...] = ()
    stage_rejection_counts: tuple[
        tuple[str, tuple[tuple[str, int], ...]], ...
    ] = ()
    cache_hits: int = 0
    cache_misses: int = 0
    generated_candidates: int = 0
    full_evaluations: int = 0
    preference_profile_id: str = ""
    preference_profile_version: str = ""
    elapsed_ms: float = 0.0
    budget_exhausted: bool = False
    budget_skipped_candidates: int = 0
    candidate_records: tuple[CandidateEvidence, ...] = ()
    stages: tuple[StageSearchEvidence, ...] = ()


@dataclass(frozen=True, slots=True)
class FamilyDecision:
    """The only contract presentation and Apply may consume."""

    family: DesignFamily
    status: DecisionStatus
    display_heading: str
    candidate: Candidate | None
    current_result: EngineeringResult
    proposed_result: EngineeringResult | None
    advice: EngineeringAdviceResult
    apply_allowed: bool
    reason: str
    changed_fields: tuple[str, ...]
    search_evidence: SearchEvidence

    def __post_init__(self) -> None:
        if self.apply_allowed and self.status is not DecisionStatus.ACTION:
            raise ValueError("only ACTION decisions may allow Apply")
        if self.apply_allowed and self.candidate is None:
            raise ValueError("Apply requires the exact displayed candidate")
        if self.status is DecisionStatus.PASS and self.apply_allowed:
            raise ValueError("terminal PASS decisions cannot allow Apply")
        if self.status is DecisionStatus.ACTION and not self.apply_allowed:
            raise ValueError("ACTION decisions must expose the verified Apply action")
        if self.status is DecisionStatus.PASS and self.family not in {
            DesignFamily.TARGET_BAND_REACHED,
            DesignFamily.EXACT_STOP_PROVEN,
        }:
            raise ValueError("PASS requires an authoritative terminal family")
