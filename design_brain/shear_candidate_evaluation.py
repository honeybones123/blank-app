"""Data boundary for shear candidate engineering evaluation."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from hashlib import sha256
from typing import Any


def stable_shear_candidate_hash(value: Any) -> str:
    """Return a deterministic hash for shear-candidate boundary payloads."""

    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return sha256(payload.encode("utf-8")).hexdigest()


def normalise_shear_candidate_mapping(value: dict[str, Any] | None) -> dict[str, Any]:
    """Return a plain dict copy for boundary fields."""

    return dict(value or {})


@dataclass(frozen=True)
class ShearCandidateInput:
    """Base shear design state for candidate evaluation."""

    base_state: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @property
    def input_hash(self) -> str:
        return stable_shear_candidate_hash(self.base_state)


@dataclass(frozen=True)
class ShearCandidateUpdate:
    """Proposed non-committed shear candidate update."""

    updates: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @property
    def update_hash(self) -> str:
        return stable_shear_candidate_hash(self.updates)


@dataclass(frozen=True)
class ShearCandidateEvaluation:
    """Normalized engineering result for a proposed shear candidate."""

    input_hash: str
    update_hash: str
    candidate_state_hash: str
    shear_utilisation: float | None = None
    previous_shear_utilisation: float | None = None
    utilisation_improved: bool | None = None
    code_compliance_status: dict[str, Any] = field(default_factory=dict)
    constructability_status: dict[str, Any] = field(default_factory=dict)
    spacing_status: dict[str, Any] = field(default_factory=dict)
    bar_size_status: dict[str, Any] = field(default_factory=dict)
    leg_count_status: dict[str, Any] = field(default_factory=dict)
    geometry_status: dict[str, Any] = field(default_factory=dict)
    capacity_summary: dict[str, Any] = field(default_factory=dict)
    failure_flags: dict[str, Any] = field(default_factory=dict)
    engineering_status: dict[str, Any] = field(default_factory=dict)
    evaluation_hash: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def with_evaluation_hash(self) -> "ShearCandidateEvaluation":
        """Return a copy with ``evaluation_hash`` populated from stable fields."""

        payload = self.to_dict()
        payload.pop("evaluation_hash", None)
        return ShearCandidateEvaluation(
            **{
                **payload,
                "evaluation_hash": stable_shear_candidate_hash(payload),
            }
        )


def build_shear_candidate_state_hash(
    base_state: dict[str, Any] | None,
    candidate_update: dict[str, Any] | None,
) -> str:
    """Hash the future non-mutating merge of base state and candidate update."""

    state = normalise_shear_candidate_mapping(base_state)
    state.update(normalise_shear_candidate_mapping(candidate_update))
    return stable_shear_candidate_hash(state)


__all__ = [
    "ShearCandidateEvaluation",
    "ShearCandidateInput",
    "ShearCandidateUpdate",
    "build_shear_candidate_state_hash",
    "normalise_shear_candidate_mapping",
    "stable_shear_candidate_hash",
]
