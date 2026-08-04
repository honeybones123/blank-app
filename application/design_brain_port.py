"""Replaceable Design Brain boundary owned by the application layer."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Protocol

from application.contracts.design_brain import (
    AuthoritativeDesignResult,
    EngineeringInputSnapshot,
)


@dataclass(frozen=True)
class DesignBrainRequest:
    """All application-owned data available to one recommendation run."""

    engineering_snapshot: EngineeringInputSnapshot
    resolved_inputs: Mapping[str, Any] = field(default_factory=dict)
    engineering_calculations: Mapping[str, Any] = field(default_factory=dict)
    family_hint: str | None = None
    debug_enabled: bool = False


@dataclass(frozen=True)
class DesignBrainExecution:
    """Implementation-neutral response returned to application consumers."""

    result: AuthoritativeDesignResult
    stage_trace: tuple[str, ...] = ()
    pipeline_applied: bool = True
    bypass_reason: str | None = None


class DesignBrainPort(Protocol):
    """The only operation a concrete Design Brain must implement."""

    def run(self, request: DesignBrainRequest) -> DesignBrainExecution:
        ...


__all__ = [
    "DesignBrainExecution",
    "DesignBrainPort",
    "DesignBrainRequest",
]
