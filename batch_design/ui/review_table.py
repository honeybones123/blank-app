"""Editable Review & Map table for Batch Design rows."""

from __future__ import annotations

from typing import Any

import pandas as pd

from batch_design.models import BatchBeamCase, BatchBeamSource
from batch_design.store import BatchDesignWorkflowState


EDITABLE_COLUMNS = [
    "include",
    "reviewed",
    "member_id",
    "source",
    "existing_section",
    "length",
    "n_star",
    "vy_star",
    "vz_star",
    "mx_star",
    "my_star",
    "mz_star",
    "confidence",
    "warnings",
]

NUMERIC_FIELDS = {
    "length",
    "n_star",
    "vy_star",
    "vz_star",
    "mx_star",
    "my_star",
    "mz_star",
    "confidence",
}


def _member_id(case: BatchBeamCase) -> str:
    return str(case.member_id or "").strip()


def _source_text(case: BatchBeamCase) -> str:
    return str(case.source.value if hasattr(case.source, "value") else case.source)


def _blank_to_none(value: Any) -> Any:
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    if isinstance(value, str) and not value.strip():
        return None
    return value


def _float_or_none(value: Any) -> float | None:
    value = _blank_to_none(value)
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def review_rows(workflow: BatchDesignWorkflowState) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for case in workflow.imported_cases:
        member_id = _member_id(case)
        rows.append(
            {
                "include": member_id not in workflow.excluded_member_ids,
                "reviewed": member_id in workflow.reviewed_member_ids,
                "member_id": case.member_id,
                "source": _source_text(case),
                "existing_section": case.existing_section,
                "length": case.length,
                "n_star": case.n_star,
                "vy_star": case.vy_star,
                "vz_star": case.vz_star,
                "mx_star": case.mx_star,
                "my_star": case.my_star,
                "mz_star": case.mz_star,
                "confidence": case.confidence,
                "warnings": "; ".join(warning.message for warning in case.warnings),
            }
        )
    return pd.DataFrame(rows, columns=EDITABLE_COLUMNS)


def apply_review_rows(workflow: BatchDesignWorkflowState, edited_rows: pd.DataFrame) -> None:
    edited_records = edited_rows.to_dict("records")
    updated_cases: list[BatchBeamCase] = []
    excluded_member_ids: set[str] = set()
    reviewed_member_ids: set[str] = set()

    for index, record in enumerate(edited_records):
        source_case = workflow.imported_cases[index] if index < len(workflow.imported_cases) else None
        member_id = str(_blank_to_none(record.get("member_id")) or "").strip()
        has_values = bool(
            member_id
            or _blank_to_none(record.get("existing_section")) is not None
            or any(_blank_to_none(record.get(field)) is not None for field in NUMERIC_FIELDS)
        )
        if source_case is None and not has_values:
            continue
        updated = BatchBeamCase(
            member_id=member_id,
            source=source_case.source if source_case is not None else BatchBeamSource.MANUAL,
            existing_section=str(_blank_to_none(record.get("existing_section")) or "").strip() or None,
            length=_float_or_none(record.get("length")),
            n_star=_float_or_none(record.get("n_star")),
            vy_star=_float_or_none(record.get("vy_star")),
            vz_star=_float_or_none(record.get("vz_star")),
            mx_star=_float_or_none(record.get("mx_star")),
            my_star=_float_or_none(record.get("my_star")),
            mz_star=_float_or_none(record.get("mz_star")),
            confidence=_float_or_none(record.get("confidence")),
            governing_metadata=dict((source_case.governing_metadata if source_case is not None else {}) or {}),
            warnings=list((source_case.warnings if source_case is not None else []) or []),
        )
        include = bool(record.get("include", True))
        reviewed = bool(record.get("reviewed", False))
        if member_id and not include:
            excluded_member_ids.add(member_id)
            updated.excluded = True
        if member_id and include and reviewed:
            reviewed_member_ids.add(member_id)
        updated_cases.append(updated)

    workflow.imported_cases = updated_cases
    workflow.excluded_member_ids = excluded_member_ids
    workflow.reviewed_member_ids = reviewed_member_ids
    workflow.design_results = []
    workflow.assignment_results = []
    workflow.refresh_validation()


def render_review_table(st, workflow: BatchDesignWorkflowState) -> pd.DataFrame:
    return st.data_editor(
        review_rows(workflow),
        key="batch_design_review_editor",
        hide_index=True,
        use_container_width=True,
        num_rows="dynamic",
        column_config={
            "include": st.column_config.CheckboxColumn("Include"),
            "reviewed": st.column_config.CheckboxColumn("Reviewed"),
            "member_id": st.column_config.TextColumn("Member ID"),
            "source": st.column_config.TextColumn("Source", disabled=True),
            "existing_section": st.column_config.TextColumn("Concrete section"),
            "length": st.column_config.NumberColumn("Length"),
            "n_star": st.column_config.NumberColumn("N*"),
            "vy_star": st.column_config.NumberColumn("Vy*"),
            "vz_star": st.column_config.NumberColumn("Vz*"),
            "mx_star": st.column_config.NumberColumn("Mx*"),
            "my_star": st.column_config.NumberColumn("My*"),
            "mz_star": st.column_config.NumberColumn("Mz*"),
            "confidence": st.column_config.NumberColumn("Confidence"),
            "warnings": st.column_config.TextColumn("Warnings", disabled=True),
        },
    )
