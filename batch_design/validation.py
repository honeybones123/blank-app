"""Validation for normalized Batch Design rows."""

from __future__ import annotations

import math
from collections.abc import Iterable

from batch_design.models import BatchBeamCase, BatchImportWarning, BatchValidationResult


DEMAND_FIELDS = ("n_star", "vy_star", "vz_star", "mx_star", "my_star", "mz_star")


def _is_number(value: object) -> bool:
    if value is None:
        return False
    try:
        number = float(value)
    except (TypeError, ValueError):
        return False
    return math.isfinite(number)


def validate_beam_case(case: BatchBeamCase, *, row_number: int | None = None) -> tuple[list[BatchImportWarning], list[BatchImportWarning]]:
    errors: list[BatchImportWarning] = [
        warning
        for warning in list(case.warnings or [])
        if str(warning.severity or "").strip().lower() == "error"
    ]
    warnings: list[BatchImportWarning] = [
        warning
        for warning in list(case.warnings or [])
        if str(warning.severity or "").strip().lower() != "error"
    ]

    member_id = str(case.member_id or "").strip()
    if not member_id:
        errors.append(
            BatchImportWarning(
                row_number=row_number,
                member_id=None,
                field="member_id",
                severity="error",
                message="Member ID is required.",
            )
        )

    if case.length is not None and (not _is_number(case.length) or float(case.length) <= 0.0):
        errors.append(
            BatchImportWarning(
                row_number=row_number,
                member_id=member_id or None,
                field="length",
                severity="error",
                message="Length must be a positive number when supplied.",
            )
        )

    numeric_actions = [
        float(getattr(case, field) or 0.0)
        for field in DEMAND_FIELDS
        if _is_number(getattr(case, field))
    ]
    if not any(abs(value) > 0.0 for value in numeric_actions):
        warnings.append(
            BatchImportWarning(
                row_number=row_number,
                member_id=member_id or None,
                field="demands",
                message="All final member design actions are zero or missing; row is not design-ready.",
            )
        )
        errors.append(
            BatchImportWarning(
                row_number=row_number,
                member_id=member_id or None,
                field="demands",
                severity="error",
                message="At least one final member design action is required.",
            )
        )

    for field in DEMAND_FIELDS:
        value = getattr(case, field)
        if value is not None and not _is_number(value):
            errors.append(
                BatchImportWarning(
                    row_number=row_number,
                    member_id=member_id or None,
                    field=field,
                    severity="error",
                    message=f"{field} must be numeric when supplied.",
                )
            )

    confidence = case.confidence
    if confidence is not None:
        if not _is_number(confidence):
            warnings.append(
                BatchImportWarning(
                    row_number=row_number,
                    member_id=member_id or None,
                    field="confidence",
                    message="Confidence was not numeric and will be ignored by UI filtering.",
                )
            )
        elif not 0.0 <= float(confidence) <= 1.0:
            warnings.append(
                BatchImportWarning(
                    row_number=row_number,
                    member_id=member_id or None,
                    field="confidence",
                    message="Confidence should be between 0 and 1.",
                )
            )

    return errors, warnings


def validate_batch_cases(cases: Iterable[BatchBeamCase]) -> BatchValidationResult:
    valid_cases: list[BatchBeamCase] = []
    invalid_cases: list[BatchBeamCase] = []
    all_errors: list[BatchImportWarning] = []
    all_warnings: list[BatchImportWarning] = []

    seen_member_ids: dict[str, int] = {}
    for index, case in enumerate(cases, start=1):
        errors, warnings = validate_beam_case(case, row_number=index)
        member_key = str(case.member_id or "").strip()
        if member_key:
            if member_key in seen_member_ids:
                errors.append(
                    BatchImportWarning(
                        row_number=index,
                        member_id=member_key,
                        field="member_id",
                        severity="error",
                        message=f"Duplicate member ID also appears on row {seen_member_ids[member_key]}.",
                    )
                )
            else:
                seen_member_ids[member_key] = index
        all_errors.extend(errors)
        all_warnings.extend(warnings)
        if case.excluded:
            all_warnings.append(
                BatchImportWarning(
                    row_number=index,
                    member_id=case.member_id,
                    message="Row is excluded from design.",
                )
            )
            invalid_cases.append(case)
        elif errors:
            invalid_cases.append(case)
        else:
            valid_cases.append(case)

    return BatchValidationResult(
        valid=not all_errors and not invalid_cases,
        valid_cases=valid_cases,
        invalid_cases=invalid_cases,
        warnings=all_warnings,
        errors=all_errors,
    )
