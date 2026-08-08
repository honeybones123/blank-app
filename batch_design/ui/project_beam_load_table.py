"""Project beam table helpers for Batch Design load entry and assignment."""

from __future__ import annotations

from typing import Any

import pandas as pd

from batch_design.models import BatchBeamCase, BatchBeamSource, BatchBeamTemplate
from batch_design.store import BatchDesignWorkflowState


ACTION_COLUMNS = ("n_star", "vy_star", "vz_star", "mx_star", "my_star", "mz_star")
ACTION_LABELS = {
    "n_star": "N*",
    # This one-axis beam workflow uses the Y shear component as its design
    # shear and the Z bending component as its design moment.  Present the
    # engineering quantities, not the retained import-axis names.
    "vy_star": "Vu*",
    "vz_star": "Vz*",
    "mx_star": "T*",
    "my_star": "My*",
    "mz_star": "Mu*",
}


def _normalise_status_text(value: Any) -> str:
    text = str(value or "").strip().upper()
    if not text:
        return ""
    if "FAIL" in text or text in {"NG", "ERROR"}:
        return "FAIL"
    if "PASS" in text or text == "OK":
        return "PASS"
    if "WARN" in text or "CHECK" in text:
        return "CHECK"
    if "NOT" in text and "RUN" in text:
        return "NOT RUN"
    return text


def _capacity_status(row: dict[str, Any]) -> str:
    for name in ("overall_status", "Overall", "strength_status", "Strength"):
        status = _normalise_status_text(row.get(name))
        if status:
            return status

    strength_statuses = [
        _normalise_status_text(row.get("bending_status") or row.get("Bending")),
        _normalise_status_text(row.get("shear_status") or row.get("Shear")),
    ]
    if any(status == "FAIL" for status in strength_statuses):
        return "FAIL"
    if strength_statuses and all(status == "PASS" for status in strength_statuses if status):
        return "PASS"
    if any(status == "CHECK" for status in strength_statuses):
        return "CHECK"
    return "NOT RUN"


def _first_utilisation(row: dict[str, Any]) -> float | None:
    for name in (
        "design_utilisation",
        "Mu_utilisation",
        "Vu_utilisation",
        "crack_utilisation",
        "deflection_utilisation",
        "utilisation",
        "Utilisation",
    ):
        value = _number_or_original(row.get(name))
        if isinstance(value, (int, float)):
            return float(value)
    return None


def _design_state(row: dict[str, Any]) -> str:
    """A stable, colour-coded project-table state from the cached beam result."""

    status = _capacity_status(row)
    utilisation = _first_utilisation(row)
    if status == "FAIL" or (utilisation is not None and utilisation > 1.0):
        return "🔴 UNDER-DESIGNED"
    if utilisation is None or status == "NOT RUN":
        return "🔵 NOT RUN"
    if utilisation >= 0.85:
        return "🟢 OPTIMAL"
    return "🔵 OVER-DESIGNED"


def _blank(value: Any) -> bool:
    if value is None:
        return True
    try:
        if pd.isna(value):
            return True
    except (TypeError, ValueError):
        pass
    return str(value).strip().lower() in {"", "none", "null", "nan", "<na>", "na", "nat", "-", "—"}


def _number_or_original(value: Any) -> float | Any | None:
    if _blank(value):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return value


def _first_number(row: dict[str, Any], *names: str) -> float | None:
    for name in names:
        value = _number_or_original(row.get(name))
        if isinstance(value, (int, float)):
            return float(value)
    return None


def _section_label(row: dict[str, Any]) -> str | None:
    shape = str(row.get("sec_shape") or "RECT").strip().upper()
    if shape == "T":
        bw = row.get("bw")
        bf = row.get("bf")
        depth = row.get("D")
        return f"T bw {bw} bf {bf} D {depth}"
    if shape == "I":
        tw = row.get("tw")
        bf = row.get("bf")
        depth = row.get("D")
        return f"I tw {tw} bf {bf} D {depth}"
    width = row.get("b")
    depth = row.get("D")
    if _blank(width) and _blank(depth):
        return None
    return f"RECT {width} x {depth}"


def _has_supplied_action(row: dict[str, Any]) -> bool:
    return any(not _blank(row.get(column)) for column in ACTION_COLUMNS)


def project_beam_load_editor_frame(
    schedule_df: pd.DataFrame,
    workflow: BatchDesignWorkflowState,
) -> pd.DataFrame:
    """Return the project beam schedule with editable batch action columns."""

    if schedule_df is None or schedule_df.empty:
        return pd.DataFrame()

    cases_by_member = {str(case.member_id): case for case in workflow.imported_cases}
    rows: list[dict[str, Any]] = []
    for row in schedule_df.to_dict("records"):
        record = dict(row)
        record["capacity_status"] = _capacity_status(record)
        utilisation = _first_utilisation(record)
        # Keep the raw engineering values in the schedule record, but provide
        # a compact read-only value for the table.  A dash is deliberately
        # used before a beam has been run rather than implying zero demand.
        record["utilisation"] = (
            f"{utilisation:.2f}" if utilisation is not None else "—"
        )
        for column in (
            "bending_utilisation",
            "shear_utilisation",
            "crack_utilisation",
            "deflection_utilisation",
        ):
            value = _number_or_original(record.get(column))
            record[column] = f"{value:.2f}" if isinstance(value, (int, float)) else "—"
        record["design_state"] = _design_state(record)
        member_id = str(record.get("beam_id") or "").strip()
        case = cases_by_member.get(member_id)
        for column in ACTION_COLUMNS:
            imported_value = getattr(case, column, None) if case is not None else None
            # Imported actions are intentional overrides.  Otherwise preserve
            # the actions cached with this project's beam record.
            if imported_value is not None:
                record[column] = imported_value
        rows.append(record)
    return pd.DataFrame(rows)


def apply_project_beam_load_editor_rows(
    workflow: BatchDesignWorkflowState,
    edited_df: pd.DataFrame,
) -> None:
    """Replace batch cases with project beams that have supplied design actions."""

    cases: list[BatchBeamCase] = []
    if edited_df is not None and not edited_df.empty:
        for row in edited_df.to_dict("records"):
            member_id = str(row.get("beam_id") or "").strip()
            if not member_id or not _has_supplied_action(row):
                continue
            cases.append(
                BatchBeamCase(
                    member_id=member_id,
                    source=BatchBeamSource.MANUAL,
                    existing_section=_section_label(row),
                    length=_number_or_original(row.get("L")),
                    n_star=_number_or_original(row.get("n_star")),
                    vy_star=_number_or_original(row.get("vy_star")),
                    vz_star=_number_or_original(row.get("vz_star")),
                    mx_star=_number_or_original(row.get("mx_star")),
                    my_star=_number_or_original(row.get("my_star")),
                    mz_star=_number_or_original(row.get("mz_star")),
                    confidence=1.0,
                    governing_metadata={
                        "source_beam_label": row.get("beam_label"),
                        "sec_shape": row.get("sec_shape"),
                        "b": row.get("b"),
                        "D": row.get("D"),
                    },
                )
            )

    validation = workflow.replace_imported_cases(cases)
    workflow.reviewed_member_ids = {str(case.member_id) for case in validation.valid_cases}


def project_beam_templates_from_frame(frame: pd.DataFrame) -> list[BatchBeamTemplate]:
    """Build assignment templates from cached project beam design summaries."""

    templates: list[BatchBeamTemplate] = []
    if frame is None or frame.empty:
        return templates

    for row in frame.to_dict("records"):
        template_id = str(row.get("beam_id") or row.get("Beam ID") or "").strip()
        if not template_id:
            continue
        status = str(row.get("overall_status") or row.get("Overall") or "").upper()
        templates.append(
            BatchBeamTemplate(
                template_id=template_id,
                label=str(row.get("beam_label") or row.get("Label") or template_id),
                source=BatchBeamSource.STRUCTURALBASE_PROJECT,
                section=_section_label(row),
                length=_first_number(row, "L", "length", "Length"),
                capacities={
                    "n_star": _first_number(row, "phi_Nu_cap", "Nu_cap", "N_capacity") or 0.0,
                    "vy_star": _first_number(row, "phi_Vy_cap", "Vy_cap", "Vy_capacity") or 0.0,
                    "vz_star": _first_number(row, "phi_Vu_cap", "phi_Vz_cap", "Vu_cap", "Vz_capacity") or 0.0,
                    "mx_star": _first_number(row, "phi_Tu_cap", "phi_Mx_cap", "Tu_cap", "Mx_capacity") or 0.0,
                    "my_star": _first_number(row, "phi_My_cap", "My_cap", "My_capacity") or 0.0,
                    "mz_star": _first_number(row, "phi_Mu_cap", "phi_Mz_cap", "Mu_cap", "Mz_capacity") or 0.0,
                },
                parameters={key: row.get(key) for key in ("sec_shape", "b", "bf", "tf", "bw", "tw", "D", "L")},
                reinforcement={
                    key: row.get(key)
                    for key in ("bot1_count", "db_bot_1", "top1_count", "db_top_1", "lig_d", "lig_legs", "s_lig")
                },
                passing="PASS" in status,
                utilisation=_first_number(row, "Mu_utilisation", "Vu_utilisation", "utilisation", "Utilisation"),
            )
        )
    return templates
