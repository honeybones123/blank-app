"""Minimal revision-tagged result contract for the isolated proof."""

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class EngineeringResult:
    source_revision: int
    source_hash: str
    status: str
    summary: str
    families: dict[str, dict[str, Any]] = field(default_factory=dict)
    warnings: tuple[str, ...] = ()
