"""Data boundary for serviceability candidate engineering evaluation.

This module defines the permanent contract shape:

    base_state + candidate_update -> ServiceabilityCandidateEvaluation

It intentionally does not execute crack/deflection formulas, read session
state, encode ladder order, or own app orchestration behavior.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from hashlib import sha256
from typing import Any


def stable_serviceability_candidate_hash(value: Any) -> str:
    """Return a deterministic hash for serviceability boundary payloads."""

    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return sha256(payload.encode("utf-8")).hexdigest()


def normalise_serviceability_candidate_mapping(value: dict[str, Any] | None) -> dict[str, Any]:
    """Return a plain dict copy for boundary fields."""

    return dict(value or {})


@dataclass(frozen=True)
class ServiceabilityCandidateInput:
    """Base serviceability design state for candidate evaluation."""

    base_state: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @property
    def input_hash(self) -> str:
        return stable_serviceability_candidate_hash(self.base_state)


@dataclass(frozen=True)
class ServiceabilityCandidateUpdate:
    """Proposed non-committed serviceability candidate update."""

    updates: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @property
    def update_hash(self) -> str:
        return stable_serviceability_candidate_hash(self.updates)


@dataclass(frozen=True)
class ServiceabilityCandidateEvaluation:
    """Normalized engineering result for a proposed serviceability candidate."""

    input_hash: str
    update_hash: str
    candidate_state_hash: str
    serviceability_utilisation: float | None = None
    previous_serviceability_utilisation: float | None = None
    serviceability_improved: bool | None = None
    serviceability_compliant: bool | None = None
    deflection_status: dict[str, Any] = field(default_factory=dict)
    crack_control_status: dict[str, Any] = field(default_factory=dict)
    strength_status: dict[str, Any] = field(default_factory=dict)
    code_compliance_status: dict[str, Any] = field(default_factory=dict)
    constructability_status: dict[str, Any] = field(default_factory=dict)
    geometry_status: dict[str, Any] = field(default_factory=dict)
    reinforcement_status: dict[str, Any] = field(default_factory=dict)
    blocker_status: dict[str, Any] = field(default_factory=dict)
    capacity_summary: dict[str, Any] = field(default_factory=dict)
    failure_flags: dict[str, Any] = field(default_factory=dict)
    engineering_status: dict[str, Any] = field(default_factory=dict)
    evaluation_hash: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def with_evaluation_hash(self) -> "ServiceabilityCandidateEvaluation":
        """Return a copy with ``evaluation_hash`` populated from stable fields."""

        payload = self.to_dict()
        payload.pop("evaluation_hash", None)
        return ServiceabilityCandidateEvaluation(
            **{
                **payload,
                "evaluation_hash": stable_serviceability_candidate_hash(payload),
            }
        )


def build_serviceability_candidate_state_hash(
    base_state: dict[str, Any] | None,
    candidate_update: dict[str, Any] | None,
) -> str:
    """Hash the future non-mutating merge of base state and candidate update."""

    state = normalise_serviceability_candidate_mapping(base_state)
    state.update(normalise_serviceability_candidate_mapping(candidate_update))
    return stable_serviceability_candidate_hash(state)


__all__ = [
    "ServiceabilityCandidateEvaluation",
    "ServiceabilityCandidateInput",
    "ServiceabilityCandidateUpdate",
    "build_serviceability_candidate_state_hash",
    "normalise_serviceability_candidate_mapping",
    "stable_serviceability_candidate_hash",
]
