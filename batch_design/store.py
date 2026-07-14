"""Workflow state helpers for Batch Design."""

from __future__ import annotations

from dataclasses import dataclass, field

from typing import Any

from batch_design.models import (
    BatchAssignmentResult,
    BatchBeamCase,
    BatchBeamSource,
    BatchBeamTemplate,
    BatchDesignResult,
    BatchValidationResult,
)
from batch_design.validation import validate_batch_cases


def _member_id(case: BatchBeamCase) -> str:
    return str(case.member_id or "").strip()


@dataclass
class BatchDesignStore:
    imported_cases: list[BatchBeamCase] = field(default_factory=list)
    templates: list[BatchBeamTemplate] = field(default_factory=list)
    results: list[BatchDesignResult] = field(default_factory=list)
    assignment_results: list[BatchAssignmentResult] = field(default_factory=list)

    def replace_cases(self, cases: list[BatchBeamCase]) -> None:
        self.imported_cases = list(cases)

    def replace_templates(self, templates: list[BatchBeamTemplate]) -> None:
        self.templates = list(templates)

    def replace_results(self, results: list[BatchDesignResult]) -> None:
        self.results = list(results)

    def replace_assignment_results(self, results: list[BatchAssignmentResult]) -> None:
        self.assignment_results = list(results)


@dataclass
class BatchDesignWorkflowState:
    """Module-owned state for the Excel/CSV -> review -> run -> assign workflow."""

    imported_cases: list[BatchBeamCase] = field(default_factory=list)
    validation: BatchValidationResult = field(default_factory=lambda: BatchValidationResult(valid=True))
    excluded_member_ids: set[str] = field(default_factory=set)
    reviewed_member_ids: set[str] = field(default_factory=set)
    design_results: list[BatchDesignResult] = field(default_factory=list)
    assignment_results: list[BatchAssignmentResult] = field(default_factory=list)
    assumptions: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def replace_imported_cases(self, cases: list[BatchBeamCase]) -> BatchValidationResult:
        self.imported_cases = list(cases)
        self.excluded_member_ids = {
            member_id for member_id in self.excluded_member_ids if member_id in self.member_ids()
        }
        self.reviewed_member_ids = {
            member_id for member_id in self.reviewed_member_ids if member_id in self.member_ids()
        }
        self.design_results = []
        self.assignment_results = []
        return self.refresh_validation()

    def add_manual_case(self, *, member_id: str | None = None) -> BatchBeamCase:
        existing = self.member_ids()
        resolved_member_id = str(member_id or "").strip()
        if not resolved_member_id:
            index = len(existing) + 1
            resolved_member_id = f"M{index}"
            while resolved_member_id in existing:
                index += 1
                resolved_member_id = f"M{index}"
        case = BatchBeamCase(member_id=resolved_member_id, source=BatchBeamSource.MANUAL)
        self.imported_cases.append(case)
        self.design_results = []
        self.assignment_results = []
        self.refresh_validation()
        return case

    def member_ids(self) -> set[str]:
        return {_member_id(case) for case in self.imported_cases if _member_id(case)}

    def set_excluded(self, member_id: str, excluded: bool = True) -> None:
        key = str(member_id or "").strip()
        if not key:
            return
        if excluded:
            self.excluded_member_ids.add(key)
            self.reviewed_member_ids.discard(key)
        else:
            self.excluded_member_ids.discard(key)
        self.refresh_validation()

    def set_reviewed(self, member_id: str, reviewed: bool = True) -> None:
        key = str(member_id or "").strip()
        if not key or key in self.excluded_member_ids:
            return
        if reviewed:
            self.reviewed_member_ids.add(key)
        else:
            self.reviewed_member_ids.discard(key)

    def mark_all_valid_reviewed(self) -> None:
        self.refresh_validation()
        for case in self.validation.valid_cases:
            member_id = _member_id(case)
            if member_id and member_id not in self.excluded_member_ids:
                self.reviewed_member_ids.add(member_id)

    def refresh_validation(self) -> BatchValidationResult:
        validation_cases = []
        for case in self.imported_cases:
            case.excluded = _member_id(case) in self.excluded_member_ids
            validation_cases.append(case)
        self.validation = validate_batch_cases(validation_cases)
        return self.validation

    def included_cases(self) -> list[BatchBeamCase]:
        return [
            case
            for case in self.imported_cases
            if _member_id(case) not in self.excluded_member_ids
        ]

    def included_validation(self) -> BatchValidationResult:
        for case in self.imported_cases:
            case.excluded = _member_id(case) in self.excluded_member_ids
        return validate_batch_cases(self.included_cases())

    def runnable_cases(self) -> list[BatchBeamCase]:
        validation = self.included_validation()
        return [
            case
            for case in validation.valid_cases
            if _member_id(case) in self.reviewed_member_ids
            and _member_id(case) not in self.excluded_member_ids
        ]

    def blocked_run_reasons(self) -> list[str]:
        self.refresh_validation()
        included_validation = self.included_validation()
        reasons: list[str] = []
        if not self.imported_cases:
            reasons.append("No imported rows are available.")
        if included_validation.errors:
            reasons.append("Included rows contain validation errors.")
        valid_unexcluded = [
            case for case in included_validation.valid_cases if _member_id(case) not in self.excluded_member_ids
        ]
        unreviewed = [
            _member_id(case)
            for case in valid_unexcluded
            if _member_id(case) not in self.reviewed_member_ids
        ]
        if unreviewed:
            reasons.append("Valid rows must be reviewed before design.")
        if not valid_unexcluded:
            reasons.append("No valid, included rows are available to design.")
        return reasons

    def can_run_design(self) -> bool:
        return not self.blocked_run_reasons()

    def replace_design_results(self, results: list[BatchDesignResult]) -> None:
        self.design_results = list(results)
        self.assignment_results = []

    def replace_assignment_results(self, results: list[BatchAssignmentResult]) -> None:
        self.assignment_results = list(results)

    def preview_summary(self) -> dict[str, int]:
        self.refresh_validation()
        return {
            "imported": len(self.imported_cases),
            "valid": len(self.validation.valid_cases),
            "invalid": len(self.validation.invalid_cases),
            "excluded": len(self.excluded_member_ids),
            "reviewed": len(self.reviewed_member_ids),
            "runnable": len(self.runnable_cases()),
            "design_results": len(self.design_results),
            "assignment_results": len(self.assignment_results),
        }
