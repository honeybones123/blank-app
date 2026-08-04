from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class FamilyResult:
    """Shared result shape for governing-family public APIs."""

    family_id: str
    is_applicable: bool
    governing_score: float | None = None
    status: str | None = None
    selected_candidate: dict[str, Any] | None = None
    updates: dict[str, Any] = field(default_factory=dict)
    blockers: list[dict[str, Any]] = field(default_factory=list)
    evidence: dict[str, Any] = field(default_factory=dict)
    publication: dict[str, Any] = field(default_factory=dict)
    cta_contract: dict[str, Any] = field(default_factory=dict)
    lock_proof: dict[str, Any] = field(default_factory=dict)

