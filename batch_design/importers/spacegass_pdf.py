"""SPACEGASS PDF importer boundary.

PDF extraction is intentionally not implemented in the first cutover. The
boundary exists so PDF parsing cannot bypass normalization, validation, preview,
and the Design Brain runner.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from batch_design.importers.base import BatchImporter, BatchImportResult
from batch_design.models import BatchImportWarning


class SpaceGassPdfImporter(BatchImporter):
    def import_rows(self, source: str | Path | Any) -> BatchImportResult:
        return BatchImportResult(
            rows=[],
            warnings=[
                BatchImportWarning(
                    row_number=None,
                    member_id=None,
                    severity="warning",
                    message="SPACEGASS PDF import is reserved for a later parser; use Excel/CSV for this cutover.",
                )
            ],
            metadata={"source_type": "spacegass_pdf", "implemented": False},
        )
