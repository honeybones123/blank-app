"""Lightweight public boundary types for Design Brain results.

These types intentionally stay permissive during the boundary extraction.  The
existing Design Guide payload remains the source of rendered UI fields; these
objects collect the contract-facing state in one stable place.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class DesignBrainInput:
    state: dict[str, Any] = field(default_factory=dict)
    constraints: dict[str, Any] = field(default_factory=dict)
    contract_config: dict[str, Any] = field(default_factory=dict)
    request_kind: str = "design_guide"
    fingerprint: Any = None


@dataclass
class DesignBrainCTA:
    intent: str | None = None
    enabled: bool = False
    disabled_reason: str | None = None
    executor_backed: bool = False
    action_type: str | None = None
    updates: dict[str, Any] = field(default_factory=dict)
    candidate_id: str | None = None
    preview_pass: bool | None = None


@dataclass
class DesignBrainCandidate:
    candidate_id: str | None = None
    label: str | None = None
    family: str | None = None
    executor_backed: bool = False
    preview_pass: bool | None = None
    expected_utilisation: float | None = None
    updates: dict[str, Any] = field(default_factory=dict)
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class DesignBrainEvidence:
    active_failures: list[str] = field(default_factory=list)
    repair_options: list[dict[str, Any]] = field(default_factory=list)
    optimisation_options: list[dict[str, Any]] = field(default_factory=list)
    candidate_search: dict[str, Any] = field(default_factory=dict)
    safe_combined_cleanup: dict[str, Any] = field(default_factory=dict)
    validation: dict[str, Any] = field(default_factory=dict)


@dataclass
class DesignBrainResult:
    outcome_id: str = "unknown"
    contract_ids: list[str] = field(default_factory=list)
    status: str | None = None
    card_kind: str | None = None
    is_terminal: bool = False
    selected_candidate_id: str | None = None
    selected_candidate_label: str | None = None
    cta: DesignBrainCTA = field(default_factory=DesignBrainCTA)
    active_failures: list[str] = field(default_factory=list)
    repair_options: list[dict[str, Any]] = field(default_factory=list)
    optimisation_options: list[dict[str, Any]] = field(default_factory=list)
    evidence: DesignBrainEvidence = field(default_factory=DesignBrainEvidence)
    fingerprint: Any = None
    raw_payload: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
