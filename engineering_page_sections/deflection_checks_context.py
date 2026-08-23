"""Immutable inputs consumed by the Deflection check presentation."""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Mapping


def _freeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        return MappingProxyType({str(key): _freeze(item) for key, item in value.items()})
    if isinstance(value, list):
        return tuple(_freeze(item) for item in value)
    if isinstance(value, tuple):
        return tuple(_freeze(item) for item in value)
    return value


@dataclass(frozen=True, slots=True)
class DeflectionChecksSnapshot:
    values: Mapping[str, Any]

    def __getitem__(self, key: str) -> Any:
        return self.values[key]


def build_deflection_checks_snapshot(
    values: Mapping[str, Any],
) -> DeflectionChecksSnapshot:
    return DeflectionChecksSnapshot(_freeze(dict(values)))


__all__ = ["DeflectionChecksSnapshot", "build_deflection_checks_snapshot"]
