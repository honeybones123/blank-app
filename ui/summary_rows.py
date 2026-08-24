from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from engineering_check_ui import (
    BENDING_ROW_UID_TO_TAB,
    SHEAR_ROW_UID_TO_TAB,
    finalize_bending_check_row,
    resolve_jump_target_id,
    sync_legacy_value_limit,
)


SHEAR_SUMMARY_HEADLINE_CHECKS = {
    "Sectional shear capacity",
    "Torsion cracking check",
    "Web-crushing strength",
}

SHEAR_SUMMARY_MCFT_DETAIL_CHECKS = {
    "Equivalent design shear",
    "Longitudinal strain",
    "Shear model parameters",
    "Concrete shear strength",
    "Steel shear strength",
}

SHEAR_SUMMARY_ROW_PRIORITY = {
    "Sectional shear capacity": 0,
    "Torsion cracking check": 1,
    "Web-crushing strength": 2,
    "Equivalent design shear": 3,
    "Longitudinal strain": 4,
    "Shear model parameters": 5,
    "Concrete shear strength": 6,
    "Steel shear strength": 7,
}


BENDING_SUMMARY_ROW_PRIORITY = {
    "Flexural strength capacity": 0,
    "Positive bending": 0,
    "Negative bending": 1,
    "Minimum tensile reinforcement": 1,
    "Ductility limit": 2,
    "Service bending moment": 3,
}


DEFLECTION_SUMMARY_ROW_PRIORITY = {
    "Total deflection (short + long-term)": 0,
    "Short-term deflection (total load)": 1,
    "Additional long-term deflection": 2,
}


def summary_status_ok(status: object, *, is_informational: bool = False) -> bool | None:
    """Convert a display status into the shared summary-row ok flag."""
    status_str = str(status or "").upper()
    if is_informational or status_str == "INFO":
        return None
    if status_str == "PASS":
        return True
    if status_str in ("FAIL", "NG", "CHECK"):
        return False
    return None


def normalise_summary_row_text(value: object) -> object:
    """Clean legacy display-only mojibake before rows reach the shared card renderer."""
    if value is None:
        return value
    text = str(value)
    return (
        text.replace("\u00ce\u00b4", "&delta;")
        .replace("\u00e2\u20ac\u201d", "&mdash;")
        .replace("\u00e2\u20ac\u0094", "&mdash;")
    )


def legacy_summary_rows_from_check_rows(
    check_rows: Iterable[Mapping[str, Any]],
    *,
    capacity_key: str,
    action_key: str,
    include_moment_sign: bool = False,
) -> list[dict[str, Any]]:
    """Build legacy display rows used by older page-side summary dataframes/overrides."""
    rows: list[dict[str, Any]] = []
    for row in check_rows or []:
        out = {
            "uid": row.get("uid", ""),
            "Check": row.get("title", ""),
            capacity_key: row.get("calculated", row.get("capacity", row.get("value", ""))),
            action_key: row.get("requirement", row.get("action", row.get("limit", ""))),
            "Utilisation": row.get("util", ""),
            "Status": row.get("status", ""),
            "is_informational": bool(row.get("is_informational", False)),
        }
        if include_moment_sign:
            out["moment_sign"] = row.get("moment_sign")
        rows.append(out)
    return rows


def build_bending_legacy_summary_rows(check_rows: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    return legacy_summary_rows_from_check_rows(
        check_rows,
        capacity_key="Calculated capacity",
        action_key="Applied design action",
        include_moment_sign=True,
    )


def build_shear_legacy_summary_rows(check_rows: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    return legacy_summary_rows_from_check_rows(
        check_rows,
        capacity_key="capacity",
        action_key="action",
    )


def build_bending_clickable_summary_rows(check_rows: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in check_rows or []:
        uid = row.get("uid")
        if not uid:
            continue
        status_str = str(row.get("status", "")).upper()
        is_info = bool(row.get("is_informational", False))
        out = finalize_bending_check_row(
            {
                "uid": uid,
                "title": str(row.get("title") or ""),
                "row_type": row.get("row_type", ""),
                "calculated": row.get("calculated", ""),
                "requirement": row.get("requirement", ""),
                "util": row.get("util", ""),
                "status": status_str,
                "ok": summary_status_ok(status_str, is_informational=is_info),
                "tab": BENDING_ROW_UID_TO_TAB.get(str(uid), ""),
                "is_primary": bool(row.get("is_primary", False)),
                "is_informational": is_info,
                "moment_sign": row.get("moment_sign"),
            }
        )
        jump_target = resolve_jump_target_id(out)
        if jump_target != uid:
            out["jump_target_id"] = jump_target
        rows.append(out)
    rows.sort(key=lambda item: BENDING_SUMMARY_ROW_PRIORITY.get(item["title"], 99))
    return rows


def build_shear_clickable_summary_rows(rows_list: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in rows_list or []:
        check = row.get("Check", "")
        uid = str(row.get("uid") or "").strip()
        if not uid:
            continue
        status_str = str(row.get("Status", "")).upper()
        is_info = bool(row.get("is_informational", False))
        out = {
            "uid": uid,
            "title": check,
            "capacity": row.get("capacity", row.get("Value", "")),
            "action": row.get("action", row.get("Limit", "")),
            "util": row.get("Utilisation", ""),
            "status": status_str,
            "ok": summary_status_ok(status_str, is_informational=is_info),
            "tab": SHEAR_ROW_UID_TO_TAB.get(uid, ""),
            "is_primary": check == "Sectional shear capacity",
            "is_informational": is_info,
            "anchor_id": uid,
        }
        jump_target = resolve_jump_target_id(out)
        if jump_target != uid:
            out["jump_target_id"] = jump_target
        rows.append(sync_legacy_value_limit(out))
    rows.sort(key=lambda item: SHEAR_SUMMARY_ROW_PRIORITY.get(item["title"], 99))
    return rows


def filter_shear_summary_rows(
    rows_list: Iterable[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    return [
        dict(row)
        for row in rows_list or []
        if row.get("Check") in SHEAR_SUMMARY_HEADLINE_CHECKS
    ]


def build_crack_summary_rows(check_rows: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in check_rows or []:
        status = row.get("status", "--")
        is_info = bool(row.get("is_informational", False))
        rows.append(
            {
                "uid": row.get("uid", "crk_step_3"),
                "title": row.get("title", ""),
                "capacity": row.get("capacity", row.get("value", "")),
                "action": row.get("action", row.get("limit", "")),
                "value": row.get("value", ""),
                "limit": row.get("limit", ""),
                "util": row.get("util", ""),
                "status": status,
                "ok": summary_status_ok(status, is_informational=is_info),
                "is_informational": is_info,
                "is_primary": False,
            }
        )
    return rows


def mark_primary_summary_row(rows: Iterable[Mapping[str, Any]], primary_uid: object) -> list[dict[str, Any]]:
    uid = str(primary_uid or "")
    return [
        {**dict(row), "is_primary": bool(uid and str(row.get("uid") or "") == uid)}
        for row in rows or []
    ]


def build_deflection_summary_rows(check_rows: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in check_rows or []:
        uid = str(row.get("uid") or "").strip()
        if not uid:
            continue
        status = str(normalise_summary_row_text(row.get("status", ""))).upper()
        is_info = bool(row.get("is_informational", False))
        calculated = normalise_summary_row_text(row.get("calculated", row.get("capacity", row.get("value", ""))))
        requirement = normalise_summary_row_text(row.get("requirement", row.get("action", row.get("limit", ""))))
        out = {
            "uid": uid,
            "title": normalise_summary_row_text(row.get("title", "")),
            "calculated": calculated,
            "requirement": requirement,
            "capacity": calculated,
            "action": requirement,
            "util": normalise_summary_row_text(row.get("util", "")),
            "status": status,
            "ok": summary_status_ok(status, is_informational=is_info),
            "route_page": row.get("route_page", "deflection"),
            "tab": row.get("tab", ""),
            "is_primary": bool(row.get("is_primary", False)),
            "is_informational": is_info,
        }
        jump_target = resolve_jump_target_id(out)
        if jump_target != uid:
            out["jump_target_id"] = jump_target
        rows.append(sync_legacy_value_limit(out))
    rows.sort(key=lambda item: DEFLECTION_SUMMARY_ROW_PRIORITY.get(item["title"], 99))
    return rows


def build_parametric_result_rows(rows: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    return [sync_legacy_value_limit(dict(row)) for row in rows or []]


def build_creep_summary_rows(
    *, phi_cc_t: float, phi_cc_star_table: float, eps_cc_micro: float
) -> list[dict[str, Any]]:
    return build_parametric_result_rows(
        [
            {
                "uid": "creep_phi_cc_t",
                "title": "Design creep coefficient \u03d5_cc(t)",
                "capacity": f"\u03d5_cc(t) = {phi_cc_t:.2f}",
                "action": "\u2014",
                "util": "\u2014",
                "status": "\u2014",
                "ok": None,
                "tab": "Creep coefficient \u03d5_cc(t)",
            },
            {
                "uid": "creep_phi_cc_table",
                "title": "Final creep coefficient \u03d5*cc (30y, table)",
                "capacity": f"\u03d5*cc,table = {phi_cc_star_table:.2f}",
                "action": "\u2014",
                "util": "\u2014",
                "status": "\u2014",
                "ok": None,
                "tab": "Creep coefficient \u03d5_cc(t)",
            },
            {
                "uid": "creep_eps_cc",
                "title": "Creep strain \u03b5_cc(t)",
                "capacity": f"\u03b5_cc = {eps_cc_micro:.1f} \u00b5\u03b5",
                "action": "\u2014",
                "util": "\u2014",
                "status": "\u2014",
                "ok": None,
                "tab": "Creep strain \u03b5_cc",
            },
        ]
    )


def build_shrinkage_summary_rows(
    *, eps_cse: float, eps_csd_t: float, eps_cs_total: float
) -> list[dict[str, Any]]:
    return build_parametric_result_rows(
        [
            {
                "uid": "shrinkage_autogenous",
                "title": "Autogenous shrinkage \u03b5_cse",
                "capacity": f"{eps_cse * 1e6:.1f} \u00b5\u03b5",
                "action": "\u2014",
                "util": "\u2014",
                "status": "\u2014",
                "ok": None,
                "tab": "Autogenous shrinkage \u03b5_cse",
            },
            {
                "uid": "shrinkage_drying",
                "title": "Drying shrinkage \u03b5_csd",
                "capacity": f"{eps_csd_t * 1e6:.1f} \u00b5\u03b5",
                "action": "\u2014",
                "util": "\u2014",
                "status": "\u2014",
                "ok": None,
                "tab": "Drying shrinkage \u03b5_csd",
            },
            {
                "uid": "shrinkage_total",
                "title": "Total shrinkage \u03b5_cs",
                "capacity": f"{eps_cs_total * 1e6:.1f} \u00b5\u03b5",
                "action": "\u2014",
                "util": "\u2014",
                "status": "\u2014",
                "ok": None,
                "tab": "Total shrinkage \u03b5_cs",
            },
        ]
    )
