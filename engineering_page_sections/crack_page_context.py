"""Immutable presentation contracts for the Crack Control page."""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Mapping, Sequence


def _freeze_mapping(values: Mapping[str, Any]) -> Mapping[str, Any]:
    return MappingProxyType(dict(values))


@dataclass(frozen=True, slots=True)
class CrackPageSnapshot:
    method: str
    engineering_state: Mapping[str, Any]
    diagram_state: Mapping[str, Any]
    summary_rows: tuple[Mapping[str, Any], ...]
    crack_metrics: Mapping[str, Any]


def build_crack_page_snapshot(
    *,
    method: str,
    engineering_state: Mapping[str, Any],
    diagram_state: Mapping[str, Any],
    summary_rows: Sequence[Mapping[str, Any]],
    crack_metrics: Mapping[str, Any],
) -> CrackPageSnapshot:
    """Detach mutable runtime dictionaries before presentation consumes them."""

    return CrackPageSnapshot(
        method=str(method),
        engineering_state=_freeze_mapping(engineering_state),
        diagram_state=_freeze_mapping(diagram_state),
        summary_rows=tuple(_freeze_mapping(row) for row in summary_rows),
        crack_metrics=_freeze_mapping(crack_metrics),
    )


__all__ = ["CrackPageSnapshot", "build_crack_page_snapshot"]
