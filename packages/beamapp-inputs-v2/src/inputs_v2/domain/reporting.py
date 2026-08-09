"""Typed report/export records owned by the domain boundary."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


ReportFormat = Literal["html", "pdf", "csv"]


@dataclass(frozen=True, slots=True)
class ReportRequest:
    beam_id: str
    source_revision: int
    source_hash: str
    format: ReportFormat

    def __post_init__(self) -> None:
        if not self.beam_id.strip():
            raise ValueError("beam_id is required")
        if self.source_revision < 0:
            raise ValueError("source_revision must be non-negative")
        if len(self.source_hash) < 8:
            raise ValueError("source_hash is required")


@dataclass(frozen=True, slots=True)
class ReportArtifact:
    request: ReportRequest
    media_type: str
    filename: str
    content: bytes

