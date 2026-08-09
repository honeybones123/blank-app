"""Application-owned seams for isolated lab persistence and report output."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from inputs_v2.domain.beam_inputs import BeamInputs
from inputs_v2.domain.engineering_result import EngineeringResult
from inputs_v2.domain.reporting import ReportArtifact, ReportRequest
from inputs_v2.infrastructure.fixture_report_exporter import FixtureReportExporter
from inputs_v2.infrastructure.json_repository import JsonBeamInputsRepository
from inputs_v2.infrastructure.memory_repository import InMemoryBeamInputsRepository


class BeamInputsRepository(Protocol):
    def save(self, beam_id: str, inputs: BeamInputs) -> None: ...
    def load(self, beam_id: str) -> BeamInputs | None: ...


def new_memory_repository() -> BeamInputsRepository:
    return InMemoryBeamInputsRepository()


def new_json_repository(root: Path) -> BeamInputsRepository:
    return JsonBeamInputsRepository(root)


def export_fixture_report(request: ReportRequest, inputs: BeamInputs, result: EngineeringResult) -> ReportArtifact:
    return FixtureReportExporter().export(request, inputs, result)
