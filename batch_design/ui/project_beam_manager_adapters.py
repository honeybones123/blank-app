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

# The batch table uses engineering-neutral column names.  A project-beam
# record, however, must store the corresponding canonical shared-input keys
# so selecting that beam hydrates the Inputs workspace, diagrams and V2 Design
# Brain with exactly the actions shown in the table.
BATCH_ACTION_COLUMNS = ("n_star", "vy_star", "vz_star", "mx_star", "my_star", "mz_star")

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
    "use_for_auto_design",
    "n_star",
    "vy_star",
    "vz_star",
    "mx_star",
    "my_star",
    "mz_star",
    "design_utilisation",
    "bending_utilisation",
    "shear_utilisation",
    "crack_utilisation",
    "deflection_utilisation",
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
    *BATCH_ACTION_COLUMNS,
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
            "use_for_auto_design": bool(item.get("use_for_auto_design", False)),
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
            "n_star": item.get("n_star"),
            "vy_star": item.get("vy_star"),
            "vz_star": item.get("vz_star"),
            "mx_star": item.get("mx_star"),
            "my_star": item.get("my_star"),
            "mz_star": item.get("mz_star"),
            "design_utilisation": item.get("design_utilisation"),
            "bending_utilisation": item.get("Mu_utilisation"),
            "shear_utilisation": item.get("Vu_utilisation"),
            "crack_utilisation": item.get("crack_utilisation"),
            "deflection_utilisation": item.get("deflection_utilisation"),
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


def publish_batch_design_results_to_beam_records(results) -> set[str]:
    """Publish completed batch outcomes to the matching stored project beams."""

    beam_records = st.session_state.get("beam_records")
    if not isinstance(beam_records, dict):
        return set()

    updated_beam_ids: set[str] = set()
    timestamp = datetime.now(UTC).replace(tzinfo=None).isoformat(timespec="seconds")
    for result in results or []:
        beam_id = str(getattr(result, "member_id", "") or "").strip()
        record = beam_records.get(beam_id)
        if not isinstance(record, dict):
            continue

        passed = getattr(result, "passed", None)
        status = "PASS" if passed is True else "FAIL" if passed is False else "NOT RUN"
        try:
            utilisation = float(getattr(result, "utilisation", None))
        except (TypeError, ValueError):
            utilisation = None

        summary = make_not_run_beam_summary()
        existing_summary = record.get("summary")
        if isinstance(existing_summary, dict):
            summary.update(existing_summary)
        raw_result = getattr(result, "raw_result", {})
        raw_payload = (
            raw_result.get("design_brain_payload", {})
            if isinstance(raw_result, dict)
            else {}
        )
        raw_debug = raw_payload.get("debug_trace", {}) if isinstance(raw_payload, dict) else {}
        raw_overview = raw_debug.get("overview", {}) if isinstance(raw_debug, dict) else {}
        family_utilisations = (
            raw_overview.get("family_utilisations", {})
            if isinstance(raw_overview, dict)
            else {}
        )

        def _family_utilisation(name: str) -> float | None:
            value = family_utilisations.get(name) if isinstance(family_utilisations, dict) else None
            try:
                return None if value is None else float(value)
            except (TypeError, ValueError):
                return None

        summary["overall_status"] = status
        summary["strength_status"] = status
        summary["batch_design_utilisation"] = utilisation
        # Batch results are authoritative for every check in this row. Clear
        # unavailable SLS values rather than retaining a prior result.
        summary["Mu_utilisation"] = _family_utilisation("bending")
        summary["Vu_utilisation"] = _family_utilisation("shear")
        summary["crack_utilisation"] = _family_utilisation("crack")
        summary["deflection_utilisation"] = _family_utilisation("deflection")
        summary["last_checked_at"] = timestamp
        record["summary"] = summary

        # A passing Batch run is an explicit request to design the project
        # beam. Persist only the V2-approved proposal carried by the neutral
        # batch result; never reconstruct a candidate or apply a failing one.
        design_brain_result = getattr(result, "design_brain_result", {})
        template_params = (
            raw_result.get("auto_design_template_params", {})
            if isinstance(raw_result, dict)
            else {}
        )
        auto_design_source_beam_id = (
            str(raw_result.get("auto_design_source_beam_id") or "").strip()
            if isinstance(raw_result, dict)
            else ""
        )
        if passed is True and isinstance(template_params, dict) and template_params:
            record["params"] = apply_auto_design_template_to_beam_params(
                record.get("params"), template_params
            )
        proposal_updates = (
            dict(design_brain_result.get("selected_updates") or {})
            if isinstance(design_brain_result, dict) and passed is True
            else {}
        )
        if proposal_updates:
            record["params"] = apply_v2_proposal_updates_to_beam_params(
                record.get("params"), proposal_updates
            )

        meta = record.get("meta") if isinstance(record.get("meta"), dict) else {}
        meta["batch_design_published_at"] = timestamp
        if passed is True and auto_design_source_beam_id:
            meta["auto_design_source_beam_id"] = auto_design_source_beam_id
        else:
            meta.pop("auto_design_source_beam_id", None)
        if proposal_updates:
            meta["batch_design_candidate_id"] = str(
                design_brain_result.get("selected_candidate", {}).get("candidate_id")
                if isinstance(design_brain_result.get("selected_candidate"), dict)
                else ""
            )
            meta["batch_design_applied_updates"] = dict(proposal_updates)
        else:
            meta.pop("batch_design_candidate_id", None)
            meta.pop("batch_design_applied_updates", None)
        record["meta"] = meta
        beam_records[beam_id] = record
        updated_beam_ids.add(beam_id)

    return updated_beam_ids


def apply_auto_design_template_to_beam_params(
    current_params: dict | None,
    template_params: dict | None,
) -> dict:
    """Copy one approved beam's complete physical design, never its actions.

    Auto assignment reuses a selected beam's geometry and reinforcement while
    retaining the target beam's own loads and identity.  Keeping this
    projection here means the V2 verification path and the persisted target
    record use the same complete input representation.
    """

    target = dict(current_params or {})
    source = dict(template_params or {})
    # A target's span is part of its own load/serviceability problem, not a
    # reusable section property.
    direct_fields = set(BEAM_MANAGER_EDITABLE_COLUMNS) - {"beam_id", "beam_label", "L"}
    reinforcement_prefixes = (
        "bot_row_",
        "top_row_",
        "bot1_",
        "bot2_",
        "top1_",
        "top2_",
        "db_bot_",
        "db_top_",
        "nb_or_s_bot_",
        "nb_or_s_top_",
    )
    reinforcement_fields = {
        "bot_row_count",
        "top_row_count",
        "top_bars",
        "db_top",
        "top_spacing",
        "lig_d",
        "lig_legs",
        "s_lig",
    }
    for key, value in source.items():
        if (
            key in direct_fields
            or key in reinforcement_fields
            or key.startswith(reinforcement_prefixes)
        ):
            target[key] = value
    return target


def apply_v2_proposal_updates_to_beam_params(
    current_params: dict | None,
    proposal_updates: dict | None,
) -> dict:
    """Project one V2 proposal into the complete stored beam-input contract.

    V2 speaks in row-model fields while older Inputs consumers still read the
    compact layer aliases.  Updating only one representation made a Batch row
    report V2's verified utilisation while the active page rehydrated stale
    reinforcement (for example 3-N10 instead of V2's 3-N40).  This is the
    single compatibility projection for a proposal: the row model and every
    surviving alias are changed together, and unused trailing rows are cleared.
    """

    params = dict(current_params or {})
    updates = dict(proposal_updates or {})
    if not updates:
        return params
    params.update(updates)

    def _integer(value, default=0) -> int:
        try:
            return int(float(value))
        except (TypeError, ValueError):
            return int(default)

    def _number(value, default=0.0) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return float(default)

    bottom_rows = max(1, min(4, _integer(params.get("bot_row_count"), 1)))
    params["bot_row_count"] = bottom_rows
    bottom_diameter = _integer(params.get("bot_row_1_dia"), 0)
    bottom_spacing = _number(params.get("bot_row_1_spacing"), 200.0)
    for index in range(1, 5):
        prefix = f"bot_row_{index}"
        enabled = index <= bottom_rows
        if index == 1:
            bars = _integer(params.get(f"{prefix}_bars"), 0)
            diameter = bottom_diameter
            spacing = bottom_spacing
        elif enabled:
            bars = _integer(params.get(f"{prefix}_bars"), 0)
            diameter = _integer(params.get(f"{prefix}_dia"), bottom_diameter)
            spacing = _number(params.get(f"{prefix}_spacing"), bottom_spacing)
        else:
            bars, diameter, spacing = 0, 0, bottom_spacing
        params[f"{prefix}_mode"] = "Count"
        params[f"{prefix}_bars"] = bars
        params[f"{prefix}_dia"] = diameter
        params[f"{prefix}_spacing"] = spacing
        if index <= 2:
            params[f"bot{index}_layout_mode"] = "Count"
            params[f"bot{index}_count"] = bars
            params[f"bot{index}_spacing"] = spacing
            params[f"db_bot_{index}"] = diameter
            params[f"nb_or_s_bot_{index}"] = bars

    if "top_bars" in params or "db_top" in params or "top_spacing" in params:
        top_bars = _integer(params.get("top_bars"), 0)
        top_diameter = _integer(params.get("db_top"), 0)
        top_spacing = _number(params.get("top_spacing"), 200.0)
        params.update(
            {
                "top_row_count": 1,
                "top_row_1_mode": "Count",
                "top_row_1_bars": top_bars,
                "top_row_1_dia": top_diameter,
                "top_row_1_spacing": top_spacing,
                "top1_layout_mode": "Count",
                "top1_count": top_bars,
                "top1_spacing": top_spacing,
                "db_top_1": top_diameter,
                "nb_or_s_top_1": top_bars,
                "top_row_2_mode": "Count",
                "top_row_2_bars": 0,
                "top_row_2_dia": 0,
                "top_row_2_spacing": top_spacing,
                "top2_layout_mode": "Count",
                "top2_count": 0,
                "top2_spacing": top_spacing,
                "db_top_2": 0,
                "nb_or_s_top_2": 0,
            }
        )
    return params


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


def _optional_action_value(value) -> float | None:
    """Coerce a batch action without replacing an intentionally blank cell."""

    if value is None or pd.isna(value):
        return None
    if isinstance(value, str) and value.strip().lower() in {"", "none", "null", "nan", "-", "—"}:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _sync_batch_actions_into_params(params: dict, row: dict) -> bool:
    """Store project-table actions using the active app's canonical keys."""

    actions = {column: _optional_action_value(row.get(column)) for column in BATCH_ACTION_COLUMNS}
    changed = False

    # Retain every imported/table action for audit/export, including axes that
    # the present one-axis beam model does not consume directly.
    if params.get("batch_design_actions") != actions:
        params["batch_design_actions"] = actions
        changed = True

    mappings = {
        "uls_Nstar": actions["n_star"],
        "N_star": actions["n_star"],
        "uls_Vstar": actions["vy_star"],
        "Tu_star": actions["mx_star"],
        "uls_Mstar": actions["mz_star"],
        "Mu_star_manual": actions["mz_star"],
    }
    moment = actions["mz_star"]
    mappings["uls_Mstar_pos_manual"] = max(moment, 0.0) if moment is not None else None
    mappings["uls_Mstar_neg_manual"] = max(-moment, 0.0) if moment is not None else None

    for key, value in mappings.items():
        if params.get(key) != value:
            params[key] = value
            changed = True

    if params.get("actions_mode") != "manual":
        params["actions_mode"] = "manual"
        changed = True
    if params.get("actions_source") != "batch_design_project_beams":
        params["actions_source"] = "batch_design_project_beams"
        changed = True
    if params.get("design_actions_source") != "batch_design_project_beams":
        params["design_actions_source"] = "batch_design_project_beams"
        changed = True
    return changed


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

        use_for_auto_design = bool(row.get("use_for_auto_design", False))
        meta = record.get("meta") if isinstance(record.get("meta"), dict) else {}
        if bool(meta.get("use_for_auto_design", False)) != use_for_auto_design:
            meta["use_for_auto_design"] = use_for_auto_design
            row_changed = True

        for column in BEAM_MANAGER_EDITABLE_COLUMNS:
            if column in ("beam_id", "beam_label"):
                continue
            new_value = coerce_beam_schedule_value(column, row.get(column))
            if params.get(column) != new_value:
                params[column] = new_value
                row_changed = True
                params_changed = True

        # Actions are not ordinary table geometry fields: map them onto the
        # canonical input snapshot so activation works across every page.
        if _sync_batch_actions_into_params(params, row):
            row_changed = True
            params_changed = True

        if row_changed:
            meta["updated_at"] = datetime.now(UTC).replace(tzinfo=None).isoformat(timespec="seconds")
            record["params"] = params
            record["meta"] = meta
            if params_changed:
                record["summary"] = make_not_run_beam_summary()
            changed_beam_ids.add(beam_id)

    return changed_beam_ids
