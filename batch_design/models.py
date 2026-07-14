"""Pure data structures for Batch Design.

These models intentionally contain no Streamlit, SPACEGASS, or Design Brain
business logic. They are the normalized contract between import, validation,
batch running, assignment, and UI preview/export.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any


class BatchBeamSource(str, Enum):
    MANUAL = "manual"
    SPACEGASS_EXCEL = "spacegass_excel"
    SPACEGASS_PDF = "spacegass_pdf"
    STRUCTURALBASE_PROJECT = "structuralbase_project"
    TEMPLATE = "template"


@dataclass
class BatchImportWarning:
    row_number: int | None
    member_id: str | None
    message: str
    field: str | None = None
    severity: str = "warning"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class BatchBeamCase:
    member_id: str
    source: BatchBeamSource | str = BatchBeamSource.MANUAL
    existing_section: str | None = None
    length: float | None = None
    n_star: float | None = None
    vy_star: float | None = None
    vz_star: float | None = None
    mx_star: float | None = None
    my_star: float | None = None
    mz_star: float | None = None
    confidence: float | None = None
    governing_metadata: dict[str, Any] = field(default_factory=dict)
    warnings: list[BatchImportWarning] = field(default_factory=list)
    excluded: bool = False

    def demand_vector(self) -> dict[str, float]:
        return {
            key: float(value or 0.0)
            for key, value in {
                "n_star": self.n_star,
                "vy_star": self.vy_star,
                "vz_star": self.vz_star,
                "mx_star": self.mx_star,
                "my_star": self.my_star,
                "mz_star": self.mz_star,
            }.items()
        }

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["source"] = str(self.source.value if isinstance(self.source, BatchBeamSource) else self.source)
        return data


@dataclass
class BatchBeamTemplate:
    template_id: str
    label: str
    source: BatchBeamSource | str = BatchBeamSource.TEMPLATE
    section: str | None = None
    length: float | None = None
    capacities: dict[str, float] = field(default_factory=dict)
    parameters: dict[str, Any] = field(default_factory=dict)
    reinforcement: dict[str, Any] = field(default_factory=dict)
    passing: bool = True
    utilisation: float | None = None

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["source"] = str(self.source.value if isinstance(self.source, BatchBeamSource) else self.source)
        return data


@dataclass
class BatchProject:
    project_id: str
    name: str
    beam_cases: list[BatchBeamCase] = field(default_factory=list)
    beam_templates: list[BatchBeamTemplate] = field(default_factory=list)
    assumptions: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class BatchValidationResult:
    valid: bool
    valid_cases: list[BatchBeamCase] = field(default_factory=list)
    invalid_cases: list[BatchBeamCase] = field(default_factory=list)
    warnings: list[BatchImportWarning] = field(default_factory=list)
    errors: list[BatchImportWarning] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class BatchDesignResult:
    member_id: str
    input_case: BatchBeamCase
    passed: bool | None = None
    selected_section: str | None = None
    utilisation: float | None = None
    design_brain_result: dict[str, Any] = field(default_factory=dict)
    raw_result: dict[str, Any] = field(default_factory=dict)
    warnings: list[BatchImportWarning] = field(default_factory=list)
    error: str | None = None

    def to_template(self, *, template_id: str | None = None, label: str | None = None) -> BatchBeamTemplate:
        capacities = dict(self.raw_result.get("capacities") or self.design_brain_result.get("capacities") or {})
        return BatchBeamTemplate(
            template_id=template_id or self.member_id,
            label=label or self.selected_section or self.member_id,
            section=self.selected_section,
            length=self.input_case.length,
            capacities=capacities,
            parameters=dict(self.raw_result.get("parameters") or {}),
            reinforcement=dict(self.raw_result.get("reinforcement") or {}),
            passing=bool(self.passed),
            utilisation=self.utilisation,
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class BatchAssignmentResult:
    member_id: str
    assigned_template_id: str | None
    assigned_label: str | None
    passed: bool
    reason: str
    utilisation: float | None = None
    rejected_candidates: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
