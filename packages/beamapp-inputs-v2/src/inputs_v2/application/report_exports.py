"""Report/export application boundary; UI and file systems stay outside it."""

from __future__ import annotations

from typing import Protocol

from inputs_v2.domain.beam_inputs import BeamInputs
from inputs_v2.domain.engineering_result import EngineeringResult
from inputs_v2.domain.reporting import ReportArtifact, ReportRequest


class ReportExporter(Protocol):
    def export(self, request: ReportRequest, inputs: BeamInputs, result: EngineeringResult) -> ReportArtifact:
        """Export a revision-tagged report without mutating canonical inputs."""


def request_for_current(beam_id: str, inputs: BeamInputs, format: str) -> ReportRequest:
    if format not in {"html", "pdf", "csv"}:
        raise ValueError("unsupported report format")
    return ReportRequest(beam_id, inputs.revision, inputs.content_hash, format)  # type: ignore[arg-type]

