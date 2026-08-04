"""Machine-checkable root-cause evidence for behavioral fixes.

This module is intentionally independent of product code.  Verifiers can use
it to reject symptom-only patches before they are treated as fixes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping


ROOT_CAUSE_PROOF_VERSION = "1"


@dataclass(frozen=True)
class RootCauseProof:
    """Evidence that identifies a production cause rather than a symptom."""

    issue_id: str
    reproduction_id: str
    reproduction_recipe: str
    source_hash: str
    verification_run_id: str
    production_path: tuple[str, ...]
    exact_callsites: tuple[str, ...]
    branch_conditions: tuple[str, ...]
    input_fingerprint: str
    first_divergence: str
    output_fingerprint_before: str
    output_fingerprint_after: str
    downstream_effect: str
    alternatives_checked: tuple[str, ...]
    confidence: str
    patch_authorized: bool = False
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "proof_version": ROOT_CAUSE_PROOF_VERSION,
            "issue_id": self.issue_id,
            "reproduction_id": self.reproduction_id,
            "reproduction_recipe": self.reproduction_recipe,
            "source_hash": self.source_hash,
            "verification_run_id": self.verification_run_id,
            "production_path": list(self.production_path),
            "exact_callsites": list(self.exact_callsites),
            "branch_conditions": list(self.branch_conditions),
            "input_fingerprint": self.input_fingerprint,
            "first_divergence": self.first_divergence,
            "output_fingerprint_before": self.output_fingerprint_before,
            "output_fingerprint_after": self.output_fingerprint_after,
            "downstream_effect": self.downstream_effect,
            "alternatives_checked": list(self.alternatives_checked),
            "confidence": self.confidence,
            "patch_authorized": self.patch_authorized,
            "metadata": dict(self.metadata),
        }


REQUIRED_ROOT_CAUSE_FIELDS = (
    "issue_id",
    "reproduction_id",
    "reproduction_recipe",
    "source_hash",
    "verification_run_id",
    "production_path",
    "exact_callsites",
    "branch_conditions",
    "input_fingerprint",
    "first_divergence",
    "output_fingerprint_before",
    "output_fingerprint_after",
    "downstream_effect",
    "alternatives_checked",
    "confidence",
)


def validate_root_cause_proof(proof: RootCauseProof) -> tuple[str, ...]:
    """Return blocking defects; an empty tuple means the proof is complete."""

    defects: list[str] = []
    values = proof.as_dict()
    for field_name in REQUIRED_ROOT_CAUSE_FIELDS:
        value = values.get(field_name)
        if value is None or value == "" or value == []:
            defects.append(f"missing_{field_name}")

    if len(proof.production_path) < 2:
        defects.append("production_path_must_include_two_or_more_stages")
    if not proof.exact_callsites:
        defects.append("exact_production_callsite_required")
    if not proof.branch_conditions:
        defects.append("executed_branch_condition_required")
    if proof.first_divergence in {"unknown", "symptom_only", ""}:
        defects.append("first_divergence_not_identified")
    if proof.output_fingerprint_before == proof.output_fingerprint_after:
        defects.append("before_after_output_fingerprints_do_not_show_effect")
    if proof.confidence not in {"high", "confirmed"}:
        defects.append("root_cause_confidence_not_confirmed")
    if proof.patch_authorized and defects:
        defects.append("patch_authorized_before_root_cause_proof_complete")
    return tuple(dict.fromkeys(defects))


def patch_may_proceed(proof: RootCauseProof) -> bool:
    """Return whether a behavioral patch is authorized by this proof."""

    return proof.patch_authorized and not validate_root_cause_proof(proof)

