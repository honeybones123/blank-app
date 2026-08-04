"""SPACEGASS Excel/CSV final member-action importer."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pandas as pd

from batch_design.importers.base import BatchImporter, BatchImportResult
from batch_design.models import BatchBeamCase, BatchBeamSource, BatchImportWarning
from batch_design.sections import normalise_concrete_section_label


COLUMN_ALIASES = {
    "member_id": {"member", "member id", "memberid", "member_id", "member no", "member number", "id"},
    "existing_section": {"section", "member size", "existing section", "existing_section", "size"},
    "length": {"length", "length m", "length_mm", "length mm", "l"},
    "n_star": {"n", "n*", "n star", "axial", "n_star", "n* kn"},
    "vy_star": {"vy", "vy*", "vy star", "vy_star", "vy* kn", "shear y"},
    "vz_star": {"vz", "vz*", "vz star", "vz_star", "vz* kn", "shear z", "v", "v*"},
    "mx_star": {"mx", "mx*", "mx star", "mx_star", "torsion", "t*", "tu*"},
    "my_star": {"my", "my*", "my star", "my_star", "moment y"},
    "mz_star": {"mz", "mz*", "mz star", "mz_star", "moment z", "m", "m*"},
    "confidence": {"confidence", "confidence_score"},
    "governing_metadata": {"governing", "governing combo", "governing combination", "case", "combo"},
    "governing_location": {"governing location", "location", "station", "x"},
    "source_metadata": {"source", "source report", "source file"},
}


NUMERIC_COLUMNS = {
    "length",
    "n_star",
    "vy_star",
    "vz_star",
    "mx_star",
    "my_star",
    "mz_star",
    "confidence",
}


def _normalise_header(value: object) -> str:
    text = str(value or "").strip().lower()
    text = text.replace("\n", " ")
    text = re.sub(r"\s+", " ", text)
    return text


def _canonical_column(name: object) -> str | None:
    normalised = _normalise_header(name)
    compact = normalised.replace("_", " ")
    compact_no_space = compact.replace(" ", "")
    for canonical, aliases in COLUMN_ALIASES.items():
        if normalised in aliases or compact in aliases or compact_no_space in aliases:
            return canonical
    return None


def _number(value: object) -> float | None:
    if value is None or pd.isna(value):
        return None
    if isinstance(value, str):
        cleaned = value.strip().replace(",", "")
        if not cleaned:
            return None
        value = cleaned
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _is_missing(value: object) -> bool:
    if value is None:
        return True
    try:
        if pd.isna(value):
            return True
    except (TypeError, ValueError):
        pass
    return isinstance(value, str) and not value.strip()


def _member_id_text(value: object) -> str:
    if _is_missing(value):
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()


class SpaceGassExcelImporter(BatchImporter):
    """Import final member design actions from SPACEGASS-like Excel or CSV output."""

    def import_rows(self, source: str | Path | Any) -> BatchImportResult:
        path = Path(source) if isinstance(source, (str, Path)) else None
        source_name = str(path or getattr(source, "name", "") or "").lower()
        if hasattr(source, "seek"):
            source.seek(0)
        if path is not None and path.suffix.lower() == ".csv":
            frame = pd.read_csv(path)
        elif path is not None:
            frame = pd.read_excel(path)
        elif source_name.endswith(".csv"):
            frame = pd.read_csv(source)
        else:
            frame = pd.read_excel(source)

        column_map: dict[str, str] = {}
        warnings: list[BatchImportWarning] = []
        for column in frame.columns:
            canonical = _canonical_column(column)
            if canonical and canonical not in column_map:
                column_map[canonical] = column

        if "member_id" not in column_map:
            warnings.append(
                BatchImportWarning(
                    row_number=None,
                    member_id=None,
                    field="member_id",
                    severity="error",
                    message="SPACEGASS import did not contain a recognizable member ID column.",
                )
            )

        rows: list[BatchBeamCase] = []
        for row_index, row in frame.iterrows():
            excel_row_number = int(row_index) + 2
            member_value = row.get(column_map.get("member_id")) if column_map.get("member_id") else None
            member_id = _member_id_text(member_value)
            metadata: dict[str, Any] = {"source_row_number": excel_row_number}
            if column_map.get("governing_metadata"):
                metadata["governing"] = row.get(column_map["governing_metadata"])
            if column_map.get("governing_location"):
                metadata["governing_location"] = row.get(column_map["governing_location"])
            if column_map.get("source_metadata"):
                metadata["source"] = row.get(column_map["source_metadata"])

            row_warnings: list[BatchImportWarning] = []
            numeric_values: dict[str, float | None] = {}
            for field in NUMERIC_COLUMNS:
                source_column = column_map.get(field)
                if not source_column:
                    numeric_values[field] = None
                    continue
                raw_value = row.get(source_column)
                numeric_values[field] = _number(raw_value)
                if numeric_values[field] is None and not _is_missing(raw_value):
                    row_warnings.append(
                        BatchImportWarning(
                            row_number=excel_row_number,
                            member_id=member_id or None,
                            field=field,
                            severity="error",
                            message=f"{field} value {raw_value!r} is not numeric.",
                        )
                    )
            raw_existing_section = (
                str(row.get(column_map["existing_section"]) or "").strip()
                if column_map.get("existing_section")
                else ""
            )
            existing_section = normalise_concrete_section_label(raw_existing_section)
            if raw_existing_section and existing_section is None:
                row_warnings.append(
                    BatchImportWarning(
                        row_number=excel_row_number,
                        member_id=member_id or None,
                        field="existing_section",
                        severity="warning",
                        message=(
                            f"Ignored non-concrete member size {raw_existing_section!r}; "
                            "Batch Design will use imported design actions with project concrete assumptions."
                        ),
                    )
                )

            case = BatchBeamCase(
                member_id=member_id,
                source=BatchBeamSource.SPACEGASS_EXCEL,
                existing_section=existing_section,
                length=numeric_values["length"],
                n_star=numeric_values["n_star"],
                vy_star=numeric_values["vy_star"],
                vz_star=numeric_values["vz_star"],
                mx_star=numeric_values["mx_star"],
                my_star=numeric_values["my_star"],
                mz_star=numeric_values["mz_star"],
                confidence=numeric_values["confidence"],
                governing_metadata=metadata,
                warnings=row_warnings,
            )
            if not member_id:
                case.warnings.append(
                    BatchImportWarning(
                        row_number=excel_row_number,
                        member_id=None,
                        field="member_id",
                        severity="error",
                        message="Member ID is blank.",
                    )
                )
            rows.append(case)

        return BatchImportResult(
            rows=rows,
            warnings=warnings,
            metadata={"source_type": "spacegass_excel", "columns": dict(column_map)},
        )
