"""Preview table helpers for normalized Batch Design rows."""

from __future__ import annotations

import pandas as pd

from batch_design.models import BatchBeamCase


PREVIEW_COLUMNS = [
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


def preview_rows(cases: list[BatchBeamCase]) -> pd.DataFrame:
    rows = []
    for case in cases:
        rows.append(
            {
                "member_id": case.member_id,
                "source": str(case.source.value if hasattr(case.source, "value") else case.source),
                "existing_section": case.existing_section,
                "length": case.length,
                "n_star": case.n_star,
                "vy_star": case.vy_star,
                "vz_star": case.vz_star,
                "mx_star": case.mx_star,
                "my_star": case.my_star,
                "mz_star": case.mz_star,
                "confidence": case.confidence,
                "warnings": "; ".join(w.message for w in case.warnings),
            }
        )
    return pd.DataFrame(rows, columns=PREVIEW_COLUMNS)


def render_preview_table(st, cases: list[BatchBeamCase]) -> None:
    st.dataframe(preview_rows(cases), hide_index=True, width="stretch")
