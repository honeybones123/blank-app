"""Typed read-only presentation contracts for the Shrinkage page."""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Mapping


def _readonly_mapping(value: Mapping[str, Any] | None) -> Mapping[str, Any]:
    return MappingProxyType(dict(value or {}))


@dataclass(frozen=True, slots=True)
class ShrinkageInputValues:
    method: str
    width_mm: float
    depth_mm: float
    concrete_strength_mpa: float
    faces_exposed: str
    environment: str
    time_days: float
    relative_humidity_percent: float
    cement_class: str
    drying_start_age_days: float


@dataclass(frozen=True, slots=True)
class ShrinkagePageSnapshot:
    """One revision-matched presentation-only Shrinkage page input."""

    engineering_state: Mapping[str, Any]
    diagram_state: Mapping[str, Any]
    summary_values: Mapping[str, Any]
    published_results: Mapping[str, Any]
    inputs: ShrinkageInputValues

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


def build_shrinkage_page_snapshot(
    *,
    engineering_state: Mapping[str, Any],
    diagram_state: Mapping[str, Any],
    summary_values: Mapping[str, Any],
    published_results: Mapping[str, Any] | None,
    inputs: ShrinkageInputValues,
) -> ShrinkagePageSnapshot:
    return ShrinkagePageSnapshot(
        engineering_state=engineering_state,
        diagram_state=diagram_state,
        summary_values=summary_values,
        published_results=published_results or {},
        inputs=inputs,
    )


__all__ = [
    "ShrinkageInputValues",
    "ShrinkagePageSnapshot",
    "build_shrinkage_page_snapshot",
]
