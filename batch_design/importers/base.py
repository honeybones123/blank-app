"""Shared importer interface for Batch Design."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from batch_design.models import BatchBeamCase, BatchImportWarning


@dataclass
class BatchImportResult:
    rows: list[BatchBeamCase] = field(default_factory=list)
    warnings: list[BatchImportWarning] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


class BatchImporter(ABC):
    @abstractmethod
    def import_rows(self, source: str | Path | Any) -> BatchImportResult:
        """Return normalized beam rows plus parser warnings."""
