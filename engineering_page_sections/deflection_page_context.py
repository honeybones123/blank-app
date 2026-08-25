"""Immutable presentation contracts for the Deflection page."""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Mapping, Sequence


def _freeze_mapping(values: Mapping[str, Any]) -> Mapping[str, Any]:
    return MappingProxyType(dict(values))


def _freeze_reo_layers(
    values: Mapping[str, Sequence[Mapping[str, Any]]],
) -> Mapping[str, tuple[Mapping[str, Any], ...]]:
    return MappingProxyType(
        {
            str(key): tuple(_freeze_mapping(layer) for layer in layers)
            for key, layers in values.items()
        }
    )


@dataclass(frozen=True, slots=True)
class DeflectionPageSnapshot:
    """Detached page-level publication consumed by summary presentation."""

    summary_pack: Mapping[str, Any]
    summary_rows: tuple[Mapping[str, Any], ...]


@dataclass(frozen=True, slots=True)
class DeflectionDiagramSnapshot:
    """Read-only inputs required by the deflected-shape presentation."""

    span_mm: float
    depth_mm: float
    total_deflection_mm: float | None
    support_type: str
    continuous_end_side: str | None
    support_pair: tuple[str, str] | None
    multi_span: bool
    controlling_span_idx: int
    controlling_reason: str
    reo_layers: Mapping[str, tuple[Mapping[str, Any], ...]]


def build_deflection_page_snapshot(
    *,
    summary_pack: Mapping[str, Any],
    summary_rows: Sequence[Mapping[str, Any]],
) -> DeflectionPageSnapshot:
    return DeflectionPageSnapshot(
        summary_pack=_freeze_mapping(summary_pack),
        summary_rows=tuple(_freeze_mapping(row) for row in summary_rows),
    )


def build_deflection_diagram_snapshot(
    *,
    span_mm: float,
    depth_mm: float,
    total_deflection_mm: float | None,
    support_type: str,
    continuous_end_side: str | None,
    support_pair: Sequence[str] | None,
    support_resolution: Mapping[str, Any],
    reo_layers: Mapping[str, Sequence[Mapping[str, Any]]],
) -> DeflectionDiagramSnapshot:
    pair = tuple(str(value) for value in support_pair) if support_pair else None
    if pair is not None and len(pair) != 2:
        pair = None
    return DeflectionDiagramSnapshot(
        span_mm=float(span_mm),
        depth_mm=float(depth_mm),
        total_deflection_mm=(
            None if total_deflection_mm is None else float(total_deflection_mm)
        ),
        support_type=str(support_type),
        continuous_end_side=(
            None if continuous_end_side is None else str(continuous_end_side)
        ),
        support_pair=pair,  # type: ignore[arg-type]
        multi_span=bool(support_resolution.get("multi_span", False)),
        controlling_span_idx=int(
            support_resolution.get("controlling_span_idx", 0) or 0
        ),
        controlling_reason=str(
            support_resolution.get("controlling_reason", "fallback")
            or "fallback"
        ),
        reo_layers=_freeze_reo_layers(reo_layers),
    )


__all__ = [
    "DeflectionDiagramSnapshot",
    "DeflectionPageSnapshot",
    "build_deflection_diagram_snapshot",
    "build_deflection_page_snapshot",
]
