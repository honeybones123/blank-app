"""Typed preview returned by every Design Brain family pipeline."""

from __future__ import annotations

from dataclasses import dataclass

from inputs_v2.application.design_brain_apply import Candidate
from inputs_v2.domain.engineering_result import EngineeringResult


@dataclass(frozen=True, slots=True)
class DesignBrainPreview:
    candidate: Candidate
    before: EngineeringResult
    after: EngineeringResult
    changed_fields: tuple[str, ...]
    accepted: bool
    reason: str
    target_low: float = 0.85
    target_high: float = 1.0


__all__ = ["DesignBrainPreview"]
