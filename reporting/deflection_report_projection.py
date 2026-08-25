"""Pure immutable projection of authoritative Deflection report inputs."""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Mapping


@dataclass(frozen=True, slots=True)
class DeflectionReportProjection:
    values: Mapping[str, Any]

    def report_params(self) -> dict[str, Any]:
        return dict(self.values)


def project_deflection_report_params(
    params: Mapping[str, Any],
) -> DeflectionReportProjection:
    """Detach report presentation from mutable runtime/session dictionaries."""

    return DeflectionReportProjection(MappingProxyType(dict(params)))


__all__ = ["DeflectionReportProjection", "project_deflection_report_params"]
