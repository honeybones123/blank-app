"""Inputs summary row assembly from check packs."""

from __future__ import annotations

from typing import Any


def _normalise_row(row: dict, route_page: str) -> dict:
    status = row.get("status", "\u2014")
    is_informational = bool(row.get("is_informational", False))
    ok = row.get("ok", None)
    if is_informational or str(status).upper() == "INFO":
        ok = None
    elif ok is None:
        if status == "PASS":
            ok = True
        elif status == "FAIL":
            ok = False
        elif status in ("NEAR LIMIT", "WARN", "CHECK"):
            ok = None

    capacity = row.get("capacity")
    action = row.get("action")
    explicit_capacity_action = bool(
        capacity is not None
        and str(capacity).strip() != ""
        and action is not None
        and str(action).strip() != ""
    )
    calculated = row.get("calculated")
    requirement = row.get("requirement")
    value = row.get("value", "\u2014")
    limit = row.get("limit", "\u2014")
    if capacity is None or str(capacity).strip() == "":
        capacity = calculated if calculated is not None and str(calculated).strip() != "" else value
    if action is None or str(action).strip() == "":
        action = requirement if requirement is not None and str(requirement).strip() != "" else limit
    if calculated is None or str(calculated).strip() == "":
        calculated = capacity
    if requirement is None or str(requirement).strip() == "":
        requirement = action
    if route_page in {"crack", "deflection"} and not explicit_capacity_action:
        # Authoritative serviceability packs use value/calculated for the
        # response and limit/requirement for the allowable threshold. Adapt
        # that legacy shape once so downstream cards have one meaning.
        response = (
            calculated
            if calculated is not None and str(calculated).strip() != ""
            else value
        )
        allowable = (
            requirement
            if requirement is not None and str(requirement).strip() != ""
            else limit
        )
        capacity = allowable
        action = response
        calculated = response
        requirement = allowable

    return {
        "uid": row.get("uid", ""),
        "title": row.get("title", ""),
        "row_type": row.get("row_type", ""),
        "calculated": calculated,
        "requirement": requirement,
        "capacity": capacity,
        "action": action,
        "value": value,
        "limit": limit,
        "util": row.get("util") if row.get("util") is not None else "\u2014",
        "status": status,
        "ok": ok,
        "is_informational": is_informational,
        "is_primary": bool(row.get("is_primary", False)),
        "route_page": row.get("route_page", route_page),
        "tab": row.get("tab", ""),
    }


def render_inputs_summary_rows_from_packs(
    *,
    st_module: Any,
    bend_pack,
    shear_pack,
    crack_pack,
    defl_pack,
):
    bend_err = bend_pack is None
    shear_err = shear_pack is None
    crack_err = crack_pack is None
    defl_err = defl_pack is None

    BENDING_ROWS = [_normalise_row(row, "bending") for row in (bend_pack or {}).get("rows") or []]
    shear_pack_d = shear_pack or {}
    shear_summary_src = shear_pack_d.get("summary_rows")
    shear_mcft_src = shear_pack_d.get("mcft_detail_rows")
    if shear_summary_src is not None and shear_mcft_src is not None:
        shear_display_list = list(shear_summary_src)
        if st_module.session_state.get("show_mcft_breakdown", False):
            shear_display_list.extend(shear_mcft_src)
        SHEAR_ROWS = [_normalise_row(row, "shear") for row in shear_display_list]
    else:
        SHEAR_ROWS = [_normalise_row(row, "shear") for row in shear_pack_d.get("rows") or []]
    CRACK_ROWS = [_normalise_row(row, "crack") for row in (crack_pack or {}).get("rows") or []]
    if bend_err:
        BENDING_ROWS = [{
            "uid": "bend_error",
            "title": "Bending checks failed",
            "value": "\u2014",
            "limit": "\u2014",
            "util": "\u2014",
            "status": "\u2014",
            "route_page": "bending",
        }]
    if shear_err:
        SHEAR_ROWS = [{
            "uid": "shear_error",
            "title": "Shear checks failed",
            "value": "\u2014",
            "limit": "\u2014",
            "util": "\u2014",
            "status": "\u2014",
            "route_page": "shear",
        }]
    if crack_err:
        CRACK_ROWS = [{
            "uid": "crack_error",
            "title": "Crack checks failed",
            "value": "\u2014",
            "limit": "\u2014",
            "util": "\u2014",
            "status": "\u2014",
            "route_page": "crack",
        }]

    DEFLECTION_ROWS = [_normalise_row(row, "deflection") for row in (defl_pack or {}).get("rows") or []]

    if defl_err:
        DEFLECTION_ROWS = [{
            "uid": "defl_error",
            "title": "Deflection checks failed",
            "value": "\u2014",
            "limit": "\u2014",
            "util": "\u2014",
            "status": "\u2014",
            "route_page": "deflection",
        }]
        delta_total = 0.0
        defl_limit = 0.0
        defl_util = None
    else:
        defl_summary = defl_pack or {}
        delta_total = float(defl_summary.get("summary_delta_total_mm") or 0.0)
        defl_limit = float(defl_summary.get("summary_defl_limit_mm") or 0.0)
        defl_util = defl_summary.get("summary_util_total")

    return (
        BENDING_ROWS,
        SHEAR_ROWS,
        CRACK_ROWS,
        DEFLECTION_ROWS,
        bend_err,
        shear_err,
        crack_err,
        defl_err,
        delta_total,
        defl_limit,
        defl_util,
    )


__all__ = ["render_inputs_summary_rows_from_packs"]
