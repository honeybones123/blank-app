"""Data boundary for Design Brain candidate evaluation.

This module defines the permanent contract shape for candidate evaluation:

    base_state + candidate_update -> BeamCandidateEvaluation

It intentionally does not execute evaluation, read session state, duplicate
engineering formulas, encode lane order, or define recommendation policy.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from hashlib import sha256
from typing import Any


def stable_candidate_evaluation_hash(value: Any) -> str:
    """Return a deterministic hash for candidate-evaluation boundary payloads."""

    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return sha256(payload.encode("utf-8")).hexdigest()


def normalise_candidate_mapping(value: dict[str, Any] | None) -> dict[str, Any]:
    """Return a plain dict copy for boundary fields."""

    return dict(value or {})


@dataclass(frozen=True)
class BeamCandidateInput:
    """Base beam state used as the starting point for candidate evaluation."""

    base_state: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @property
    def state_hash(self) -> str:
        return stable_candidate_evaluation_hash(self.base_state)


@dataclass(frozen=True)
class BeamCandidateUpdate:
    """Proposed candidate update for a copied base state."""

    updates: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @property
    def update_hash(self) -> str:
        return stable_candidate_evaluation_hash(self.updates)


@dataclass(frozen=True)
class BeamCandidateEvaluation:
    """Normalized engineering result for a proposed beam candidate."""

    input_hash: str
    candidate_state_hash: str
    update_hash: str
    bending_utilisation: float | None = None
    shear_utilisation: float | None = None
    serviceability_status: dict[str, Any] = field(default_factory=dict)
    geometry_status: dict[str, Any] = field(default_factory=dict)
    detailing_status: dict[str, Any] = field(default_factory=dict)
    spacing_status: dict[str, Any] = field(default_factory=dict)
    capacity_summary: dict[str, Any] = field(default_factory=dict)
    failure_flags: dict[str, Any] = field(default_factory=dict)
    engineering_status: dict[str, Any] = field(default_factory=dict)
    evaluation_hash: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def with_evaluation_hash(self) -> "BeamCandidateEvaluation":
        """Return a copy with ``evaluation_hash`` populated from stable fields."""

        payload = self.to_dict()
        payload.pop("evaluation_hash", None)
        return BeamCandidateEvaluation(
            **{
                **payload,
                "evaluation_hash": stable_candidate_evaluation_hash(payload),
            }
        )


def build_candidate_state_hash(
    base_state: dict[str, Any] | None,
    candidate_update: dict[str, Any] | None,
) -> str:
    """Hash the future non-mutating merge of base state and candidate update."""

    state = normalise_candidate_mapping(base_state)
    state.update(normalise_candidate_mapping(candidate_update))
    return stable_candidate_evaluation_hash(state)


__all__ = [
    "BeamCandidateEvaluation",
    "BeamCandidateInput",
    "BeamCandidateUpdate",
    "build_candidate_state_hash",
    "normalise_candidate_mapping",
    "stable_candidate_evaluation_hash",
]
