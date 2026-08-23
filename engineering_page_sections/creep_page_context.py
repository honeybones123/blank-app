"""Typed, read-only presentation contracts for the Creep page.

The authoritative time-dependent publication remains the sole engineering
owner.  These snapshots detach the already-resolved values used by page
sections so extracted renderers do not need to recalculate Creep results or
inspect unrelated session-state keys.
"""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Mapping


def _readonly_mapping(value: Mapping[str, Any] | None) -> Mapping[str, Any]:
    return MappingProxyType(dict(value or {}))


@dataclass(frozen=True, slots=True)
class CreepInputValues:
    width_mm: float
    depth_mm: float
    concrete_strength_mpa: float
    concrete_modulus_mpa: float
    faces_exposed: str
    environment: str
    time_after_loading_days: float
    age_at_loading_days: float


@dataclass(frozen=True, slots=True)
class CreepPageSnapshot:
    """One revision-matched, presentation-only Creep page input."""

    engineering_state: Mapping[str, Any]
    diagram_state: Mapping[str, Any]
    summary_values: Mapping[str, Any]
    published_results: Mapping[str, Any]
    inputs: CreepInputValues

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "engineering_state", _readonly_mapping(self.engineering_state)
        )
        object.__setattr__(
            self, "diagram_state", _readonly_mapping(self.diagram_state)
        )
        object.__setattr__(
            self, "summary_values", _readonly_mapping(self.summary_values)
        )
        object.__setattr__(
            self, "published_results", _readonly_mapping(self.published_results)
        )


def build_creep_page_snapshot(
    *,
    engineering_state: Mapping[str, Any],
    diagram_state: Mapping[str, Any],
    summary_values: Mapping[str, Any],
    published_results: Mapping[str, Any] | None,
    inputs: CreepInputValues,
) -> CreepPageSnapshot:
    """Build a detached presentation snapshot without recalculating results."""

    return CreepPageSnapshot(
        engineering_state=engineering_state,
        diagram_state=diagram_state,
        summary_values=summary_values,
        published_results=published_results or {},
        inputs=inputs,
    )


__all__ = [
    "CreepInputValues",
    "CreepPageSnapshot",
    "build_creep_page_snapshot",
]
