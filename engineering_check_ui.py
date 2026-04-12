"""
Shared labels and cell resolution for engineering check / summary tables.

Convention (ultimate/service checks):
  - Calculated capacity: code resistance / allowable (what the member can sustain).
  - Applied design action: demand being checked.
  - Utilisation = applied design action / calculated capacity (demand / capacity).

Rows may use canonical keys ``capacity`` and ``action``, with optional legacy
``value`` / ``limit`` mirrors for older call sites.
"""

from __future__ import annotations

from typing import Any

# Standard 5-column layout for capacity vs demand checks
ENGINEERING_CHECK_COLUMNS: list[dict[str, Any]] = [
    {"label": "Check", "key": "title", "width": "30%"},
    {"label": "Calculated capacity", "key": "capacity", "width": "24%"},
    {"label": "Applied design action", "key": "action", "width": "24%"},
    {"label": "Util", "key": "util", "width": "8%"},
    {"label": "Status", "key": "status", "width": "14%"},
]

# Deflection serviceability summary: demand vs allowable (not strength-style capacity/action wording)
DEFLECTION_CHECK_SUMMARY_COLUMNS: list[dict[str, Any]] = [
    {"label": "Check", "key": "title", "width": "26%"},
    {"label": "Calculated deflection", "key": "calculated", "width": "24%"},
    {"label": "Allowable limit", "key": "requirement", "width": "26%"},
    {"label": "Util", "key": "util", "width": "10%"},
    {"label": "Status", "key": "status", "width": "14%"},
]

# Derived actions / design summary (SFD/BMD): not a pure capacity column but same Util = ULS / strength
DESIGN_ACTION_SUMMARY_COLUMNS: list[dict[str, Any]] = [
    {"label": "Action", "key": "name", "width": "22%"},
    {"label": "SLS", "key": "sls", "width": "14%"},
    {"label": "ULS (design)", "key": "uls", "width": "14%"},
    {"label": "Calculated capacity (φ)", "key": "strength", "width": "22%"},
    {"label": "Util", "key": "util", "width": "10%"},
    {"label": "Status", "key": "status", "width": "18%"},
]

# Parametric / informational pages (shrinkage, creep, etc.): no demand vs capacity framing
PARAMETRIC_RESULT_COLUMNS: list[dict[str, Any]] = [
    {"label": "Check", "key": "title", "width": "30%"},
    {"label": "Result", "key": "capacity", "width": "28%"},
    {"label": "Notes", "key": "action", "width": "24%"},
    {"label": "Util", "key": "util", "width": "8%"},
    {"label": "Status", "key": "status", "width": "10%"},
]

# Bending page detailed check table (mixed row semantics — not all rows are “capacity vs design action”)
BENDING_DETAIL_CHECK_COLUMNS: list[dict[str, Any]] = [
    {"label": "Check", "key": "title", "width": "28%"},
    {"label": "Calculated value", "key": "calculated", "width": "24%"},
    {"label": "Requirement / reference", "key": "requirement", "width": "26%"},
    {"label": "Util", "key": "util", "width": "8%"},
    {"label": "Status", "key": "status", "width": "14%"},
]

# Summary row ``uid`` (canonical) vs calc block ``step_id`` (anchor id="calc_<step_id>") when they differ.
BENDING_ROW_UID_TO_CALC_STEP_ID: dict[str, str] = {
    "bend_strength_pos": "bending_uls_1_7",
    "bend_strength_neg": "bending_uls_1_7",
    "bend_strength": "bending_uls_1_7",
    "bend_Asmin": "bending_min_2_5",
    "bend_min_strength": "bending_min_2_4",
    "bend_duct": "bending_uls_1_5",
    "bend_service_moment": "bending_sls_3_4",
}

# Tab labels for Streamlit tab switching on summary row click (canonical uid -> tab label).
BENDING_ROW_UID_TO_TAB: dict[str, str] = {
    "bend_strength_pos": "ULS Checks",
    "bend_strength_neg": "ULS Checks",
    "bend_strength": "ULS Checks",
    "bend_Asmin": "Minimum strength checks",
    "bend_min_strength": "Minimum strength checks",
    "bend_duct": "ULS Checks",
    "bend_service_moment": "SLS Checks",
}

SHEAR_ROW_UID_TO_TAB: dict[str, str] = {
    "shear_check1": "Torsion + dimensions",
    "shear_check2": "Torsion + dimensions",
    "shear_check4": "MCFT and strength checks",
    "shear_check5": "MCFT and strength checks",
    "shear_check6": "MCFT and strength checks",
    "shear_check7": "MCFT and strength checks",
    "shear_check8": "MCFT and strength checks",
    "shear_check9": "MCFT and strength checks",
}

DEFLECTION_ROW_UID_TO_CALC_STEP_ID: dict[str, str] = {
    "defl_total": "defl_long",
    "defl_long_add": "defl_long",
}


def resolve_jump_target_id(row: dict[str, Any]) -> str:
    """
    Resolve the calc step id to scroll to / open (id=\"calc_<id>\"), not the canonical summary row uid.

    Order: explicit ``jump_target_id`` on the row, central uid→step mapping (bending/deflection),
    else ``uid`` (shear/crack rows typically match calc step ids already).
    """
    explicit = row.get("jump_target_id")
    if explicit is not None and str(explicit).strip() != "":
        return str(explicit).strip()
    uid = str(row.get("uid") or "").strip()
    if not uid:
        return ""
    if uid in BENDING_ROW_UID_TO_CALC_STEP_ID:
        return BENDING_ROW_UID_TO_CALC_STEP_ID[uid]
    if uid in DEFLECTION_ROW_UID_TO_CALC_STEP_ID:
        return DEFLECTION_ROW_UID_TO_CALC_STEP_ID[uid]
    return uid


def summary_cell_display(row: dict[str, Any], col_key: str) -> str:
    """Resolve a table cell from a summary row; supports legacy value/limit."""
    if col_key == "calculated":
        for k in ("calculated", "capacity", "value"):
            v = row.get(k)
            if v is not None and str(v).strip() != "":
                return str(v)
        return ""
    if col_key == "requirement":
        for k in ("requirement", "action", "limit"):
            v = row.get(k)
            if v is not None and str(v).strip() != "":
                return str(v)
        return ""
    if col_key == "capacity":
        for k in ("capacity", "calculated", "value"):
            v = row.get(k)
            if v is not None and str(v).strip() != "":
                return str(v)
        return ""
    if col_key == "action":
        for k in ("action", "requirement", "limit"):
            v = row.get(k)
            if v is not None and str(v).strip() != "":
                return str(v)
        return ""
    if col_key in ("title", "check"):
        return str(row.get(col_key) or row.get("title") or row.get("check") or "")
    v = row.get(col_key)
    return "" if v is None else str(v)


def finalize_bending_check_row(row: dict[str, Any]) -> dict[str, Any]:
    """
    Bending summary rows: canonical ``calculated`` / ``requirement`` for the detail table.
    Mirrors to ``capacity`` / ``action`` / ``value`` / ``limit`` for Inputs banner and legacy code.
    """
    calc = row.get("calculated")
    req = row.get("requirement")
    if calc is None or str(calc).strip() == "":
        calc = row.get("capacity") or row.get("value") or ""
    if req is None or str(req).strip() == "":
        req = row.get("action") or row.get("limit") or ""
    row["calculated"] = calc
    row["requirement"] = req
    row["capacity"] = calc
    row["action"] = req
    row["value"] = calc
    row["limit"] = req
    return row


def sync_legacy_value_limit(row: dict[str, Any]) -> dict[str, Any]:
    """
    After setting capacity/action, mirror to value/limit for code that still
    reads legacy keys (value = capacity column, limit = action column).
    """
    cap = row.get("capacity")
    act = row.get("action")
    if cap is not None and str(cap).strip() != "":
        row["value"] = cap
    if act is not None and str(act).strip() != "":
        row["limit"] = act
    return row
