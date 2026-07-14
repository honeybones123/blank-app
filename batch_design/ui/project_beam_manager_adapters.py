"""Adapters for the retained stored-beam project manager.

These functions keep the old single-beam project schedule/editor behaviour
outside ``inputs_page.py`` while the underlying hydration and save/load
infrastructure remains in ``state_and_helpers``.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pandas as pd
import streamlit as st

from report_helpers import (
    build_beam_schedule_export_rows,
    format_report_status_badge,
    format_report_status_label,
)
from state_and_helpers import (
    SHARED_DEFAULTS,
    build_beam_schedule_rows,
    make_not_run_beam_summary,
)


BEAM_MANAGER_EDITABLE_COLUMNS = [
    "beam_id",
    "beam_label",
    "sec_shape",
    "b",
    "bf",
    "tf",
    "bw",
    "tw",
    "D",
    "L",
    "cover_top",
    "cover_bot",
    "cover_side",
    "fc",
    "fsy",
    "bot1_count",
    "db_bot_1",
    "top1_count",
    "db_top_1",
    "lig_d",
    "lig_legs",
    "s_lig",
]

BEAM_MANAGER_STATUS_COLUMNS = [
    "active",
    "overall_status",
    "bending_status",
    "shear_status",
    "crack_status",
    "deflection_status",
    "last_checked_at",
]

BEAM_MANAGER_TABLE_COLUMNS = [
    "active",
    "beam_id",
    "beam_label",
    "overall_status",
    "bending_status",
    "shear_status",
    "crack_status",
    "deflection_status",
    "last_checked_at",
    "sec_shape",
    "b",
    "bf",
    "tf",
    "bw",
    "tw",
    "D",
    "L",
    "cover_top",
    "cover_bot",
    "cover_side",
    "fc",
    "fsy",
    "bot1_count",
    "db_bot_1",
    "top1_count",
    "db_top_1",
    "lig_d",
    "lig_legs",
    "s_lig",
]

BEAM_MANAGER_NUMERIC_COLUMNS = {
    "b",
    "bf",
    "tf",
    "bw",
    "tw",
    "D",
    "L",
    "cover_top",
    "cover_bot",
    "cover_side",
    "fc",
    "fsy",
    "bot1_count",
    "db_bot_1",
    "top1_count",
    "db_top_1",
    "lig_d",
    "lig_legs",
    "s_lig",
}

BEAM_MANAGER_INT_COLUMNS = {
    "bot1_count",
    "db_bot_1",
    "top1_count",
    "db_top_1",
    "lig_d",
    "lig_legs",
}


def beam_option_labels() -> dict[str, str]:
    labels = {}
    beam_records = st.session_state.get("beam_records", {})
    for beam_id in st.session_state.get("beam_order", []):
        record = beam_records.get(beam_id, {})
        label = str(record.get("beam_label") or beam_id)
        labels[beam_id] = f"{label} ({beam_id})"
    return labels


def format_beam_status(status: str) -> str:
    return format_report_status_label(status)


def format_beam_status_badge(
    status: str,
    *,
    strength_status: str | None = None,
    detailing_status: str | None = None,
) -> str:
    return format_report_status_badge(
        status,
        strength_status=strength_status,
        detailing_status=detailing_status,
    )


def format_last_checked(value) -> str:
    if not value:
        return "Not run"
    text = str(value).strip()
    if "T" in text:
        return text.replace("T", " ")
    return text


def build_beam_schedule_df() -> pd.DataFrame:
    rows = []
    for item in build_beam_schedule_rows():
        params = {key: item.get(key, SHARED_DEFAULTS.get(key)) for key in BEAM_MANAGER_EDITABLE_COLUMNS}
        row = {
            "active": "ACTIVE" if item.get("active") else "",
            "beam_id": item.get("beam_id"),
            "beam_label": item.get("beam_label"),
            "overall_status": format_beam_status_badge(
                item.get("overall_status"),
                strength_status=item.get("strength_status"),
                detailing_status=item.get("detailing_status"),
            ),
            "bending_status": format_beam_status_badge(item.get("bending_status")),
            "shear_status": format_beam_status_badge(item.get("shear_status")),
            "crack_status": format_beam_status_badge(item.get("crack_status")),
            "deflection_status": format_beam_status_badge(item.get("deflection_status")),
            "last_checked_at": format_last_checked(item.get("last_checked_at")),
        }
        for column in BEAM_MANAGER_EDITABLE_COLUMNS:
            if column in row:
                continue
            row[column] = params.get(column)
        rows.append(row)
    return pd.DataFrame(rows, columns=BEAM_MANAGER_TABLE_COLUMNS)


def build_schedule_export_df() -> pd.DataFrame:
    return pd.DataFrame(build_beam_schedule_export_rows())


def build_schedule_preview_df() -> pd.DataFrame:
    rows = []
    for item in build_beam_schedule_export_rows():
        if item.get("sec_shape") == "T":
            geometry_summary = f"T bw {item.get('bw') or 0} / bf {item.get('bf') or 0} / D {item.get('D') or 0} / L {item.get('L') or 0}"
        elif item.get("sec_shape") == "I":
            geometry_summary = f"I tw {item.get('tw') or 0} / bf {item.get('bf') or 0} / D {item.get('D') or 0} / L {item.get('L') or 0}"
        else:
            geometry_summary = f"RECT {item.get('b') or 0} x {item.get('D') or 0} / L {item.get('L') or 0}"
        reo_summary = (
            f"Bottom {int(item.get('bot1_count') or 0)}N{int(item.get('db_bot_1') or 0)} | "
            f"Top {int(item.get('top1_count') or 0)}N{int(item.get('db_top_1') or 0)} | "
            f"Lig N{int(item.get('lig_d') or 0)} @ {int(item.get('s_lig') or 0)}"
        )
        rows.append(
            {
                "Active": "ACTIVE" if item.get("active") else "",
                "Beam ID": item.get("beam_id"),
                "Label": item.get("beam_label"),
                "Geometry": geometry_summary,
                "Reinforcement": reo_summary,
                "Overall": format_beam_status_badge(
                    item.get("overall_status"),
                    strength_status=item.get("strength_status"),
                    detailing_status=item.get("detailing_status"),
                ),
                "Bending": format_beam_status_badge(item.get("bending_status")),
                "Shear": format_beam_status_badge(item.get("shear_status")),
                "Crack": format_beam_status_badge(item.get("crack_status")),
                "Deflection": format_beam_status_badge(item.get("deflection_status")),
                "Last Checked": format_last_checked(item.get("last_checked_at")),
            }
        )
    return pd.DataFrame(rows)


def coerce_beam_schedule_value(column: str, value):
    if pd.isna(value):
        return SHARED_DEFAULTS.get(column)
    if column in BEAM_MANAGER_INT_COLUMNS:
        try:
            return int(value)
        except Exception:
            return int(SHARED_DEFAULTS.get(column, 0) or 0)
    if column in BEAM_MANAGER_NUMERIC_COLUMNS:
        try:
            return float(value)
        except Exception:
            return SHARED_DEFAULTS.get(column)
    if column == "beam_label":
        text = str(value).strip()
        return text or "Beam"
    if column == "sec_shape":
        text = str(value or "RECT").strip().upper()
        return text if text in ("RECT", "T", "I") else "RECT"
    return value


def sync_beam_records_from_schedule_df(schedule_df: pd.DataFrame) -> set[str]:
    changed_beam_ids = set()
    if schedule_df is None or schedule_df.empty:
        return changed_beam_ids

    beam_records = st.session_state.get("beam_records", {})
    for row in schedule_df.to_dict("records"):
        beam_id = row.get("beam_id")
        if beam_id not in beam_records:
            continue

        record = beam_records[beam_id]
        params = dict(record.get("params", {}) or {})
        row_changed = False
        params_changed = False

        new_label = coerce_beam_schedule_value("beam_label", row.get("beam_label"))
        if record.get("beam_label") != new_label:
            record["beam_label"] = new_label
            row_changed = True

        for column in BEAM_MANAGER_EDITABLE_COLUMNS:
            if column in ("beam_id", "beam_label"):
                continue
            new_value = coerce_beam_schedule_value(column, row.get(column))
            if params.get(column) != new_value:
                params[column] = new_value
                row_changed = True
                params_changed = True

        if row_changed:
            meta = record.get("meta") if isinstance(record.get("meta"), dict) else {}
            meta["updated_at"] = datetime.now(UTC).replace(tzinfo=None).isoformat(timespec="seconds")
            record["params"] = params
            record["meta"] = meta
            if params_changed:
                record["summary"] = make_not_run_beam_summary()
            changed_beam_ids.add(beam_id)

    return changed_beam_ids
