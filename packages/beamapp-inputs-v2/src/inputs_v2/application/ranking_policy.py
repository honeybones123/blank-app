"""Factual ranking evidence; family contracts remain the decision owners."""
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class NearLimitEvidence:
    """One explicitly whitelisted family near-limit comparison."""

    check_id: str
    current_value: float
    proposed_value: float
    direction: str
    threshold: float
    comparison_method: str
    penalty_applied: bool

@dataclass(frozen=True, slots=True)
class CandidateEvidence:
    """Safety-first ranking values plus immutable candidate audit evidence.

    The optional audit fields are populated by the shared validation gateway.
    They deliberately contain calculation facts only: no family, terminal
    status, blocker wording, colour or CTA decision belongs here.
    """

    candidate_id: str
    compliant: bool
    mandatory_checks_complete: bool
    new_near_failure_count: int = 0
    edit_count: int = 0
    constructability_penalty: float = 0.0
    hard_congestion_rejection_codes: tuple[str, ...] = ()
    soft_congestion_score: float = 0.0
    soft_congestion_reasons: tuple[str, ...] = ()
    conditional_preference_violation_codes: tuple[str, ...] = ()
    near_limit_evidence: tuple[NearLimitEvidence, ...] = ()
    geometry_change_penalty: float = 0.0
    material_quantity: float = 0.0
    target_distance: float = 0.0
    stage_id: str = ""
    proposed_changes: tuple[str, ...] = ()
    row_counts: tuple[int, ...] = ()
    calculated_checks: tuple[tuple[str, str], ...] = ()
    accepted_by_mandatory_checks: bool = False
    rejection_codes: tuple[str, ...] = ()
    elapsed_ms: float = 0.0


__all__ = ["CandidateEvidence", "NearLimitEvidence"]
