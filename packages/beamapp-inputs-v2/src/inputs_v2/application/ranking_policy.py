"""Shared ranking primitives; family modules remain the decision owners."""
from dataclasses import dataclass

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

    @property
    def rank_key(self) -> tuple:
        """Lexicographic safety-first ordering; lower is better."""
        return (
            0 if self.compliant and self.mandatory_checks_complete else 1,
            self.target_distance,
            self.new_near_failure_count,
            self.edit_count,
            self.constructability_penalty,
            self.geometry_change_penalty,
            self.material_quantity,
            self.candidate_id,
        )

def reject_invalid(evidence: CandidateEvidence) -> bool:
    """Hard exclusion for unsafe or incomplete candidates."""
    return not (evidence.compliant and evidence.mandatory_checks_complete)

def choose_valid(candidates: list[CandidateEvidence]) -> CandidateEvidence | None:
    valid = [candidate for candidate in candidates if not reject_invalid(candidate)]
    return min(valid, key=lambda candidate: candidate.rank_key) if valid else None
