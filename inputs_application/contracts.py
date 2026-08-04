"""Stable transaction contracts for the replacement Inputs runtime.

These contracts deliberately contain no Streamlit or legacy bridge imports.
They describe product-level inputs and outputs rather than the old call graph.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Mapping


def _frozen_mapping(value: Mapping[str, Any] | None) -> Mapping[str, Any]:
    return MappingProxyType(dict(value or {}))


@dataclass(frozen=True)
class InputsApplyCommand:
    recommendation_id: str
    payload: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "payload", _frozen_mapping(self.payload))


@dataclass(frozen=True)
class InputsPageRequest:
    engineering_state: Mapping[str, Any]
    session_context: Mapping[str, Any] = field(default_factory=dict)
    apply_command: InputsApplyCommand | None = None
    force_recompute: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "engineering_state", _frozen_mapping(self.engineering_state))
        object.__setattr__(self, "session_context", _frozen_mapping(self.session_context))


@dataclass(frozen=True)
class InputsEngineeringResult:
    engineering_hash: str
    overview: Mapping[str, Any]
    checks: Mapping[str, Any] = field(default_factory=dict)
    snapshot: Any = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "overview", _frozen_mapping(self.overview))
        object.__setattr__(self, "checks", _frozen_mapping(self.checks))


@dataclass(frozen=True)
class InputsPublicationResult:
    publication_hash: str
    outcome: str
    family_id: str | None = None
    cta: Mapping[str, Any] = field(default_factory=dict)
    payload: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "cta", _frozen_mapping(self.cta))
        object.__setattr__(self, "payload", _frozen_mapping(self.payload))


@dataclass(frozen=True)
class InputsSessionMutation:
    updates: Mapping[str, Any] = field(default_factory=dict)
    removals: tuple[str, ...] = ()
    rerun_required: bool = False
    status: str = "dispatch_ok"
    reason: str | None = None

    def __post_init__(self) -> None:
        if self.status not in {"dispatch_ok", "rerun_required", "failed"}:
            raise ValueError(f"unsupported Apply mutation status: {self.status}")
        object.__setattr__(self, "updates", _frozen_mapping(self.updates))
        object.__setattr__(self, "removals", tuple(self.removals))


@dataclass(frozen=True)
class InputsPageResult:
    engineering: InputsEngineeringResult
    publication: InputsPublicationResult
    session_mutation: InputsSessionMutation = field(default_factory=InputsSessionMutation)
    apply_status: str | None = None
    transaction_trace: tuple[str, ...] = ()
