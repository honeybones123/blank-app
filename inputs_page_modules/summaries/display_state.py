"""Inputs summary display-state coordination."""

from __future__ import annotations

from typing import Any, Callable


def render_inputs_summary_display_state(
    *,
    st_module: Any,
    summary_state: dict,
    shear_pack,
    BENDING_ROWS,
    SHEAR_ROWS,
    CRACK_ROWS,
    DEFLECTION_ROWS,
    primary_row_fn: Callable[..., dict | None],
    pick_governing_check_row_fn: Callable[..., dict | None],
    overall_status_from_rows_fn: Callable[..., tuple[str, str]],
    parse_util_value_fn: Callable[..., float | None],
):
    uls_m = abs(float(summary_state.get("Mu_star", summary_state.get("uls_Mstar", 0.0)) or 0.0))
    uls_v = abs(float(summary_state.get("Vu_star", summary_state.get("uls_Vstar", 0.0)) or 0.0))
    uls_t = abs(float(summary_state.get("Tu_star", 0.0) or 0.0))
    sls_m = abs(float(summary_state.get("sls_Mstar", 0.0) or 0.0))
    sls_v = abs(float(summary_state.get("sls_Vstar", 0.0) or 0.0))
    no_loads_bending = uls_m == 0.0
    no_loads_shear = uls_v == 0.0 and uls_t == 0.0
    no_loads_crack = sls_m == 0.0 and sls_v == 0.0
    no_loads_deflection = sls_m == 0.0 and sls_v == 0.0

    bending_primary = primary_row_fn(BENDING_ROWS) or {}
    shear_primary = primary_row_fn(SHEAR_ROWS) or {}
    crack_primary = pick_governing_check_row_fn(CRACK_ROWS) or next(
        (row for row in CRACK_ROWS if not row.get("is_informational")),
        {},
    ) or {}
    defl_primary = primary_row_fn(DEFLECTION_ROWS) or {}

    bending_cap = bending_primary.get("capacity") or bending_primary.get("value", "\u2014")
    bending_demand = bending_primary.get("action") or bending_primary.get("limit", "\u2014")
    bending_util_str = bending_primary.get("util", "\u2014")
    bending_status, bending_colour = overall_status_from_rows_fn(BENDING_ROWS)

    def _status_colour_from_summary(status: str) -> str:
        status_upper = str(status or "").upper()
        if "FAIL" in status_upper or status_upper == "NG":
            return "rgba(255,0,0,0.12)"
        if "WARN" in status_upper or "NEAR LIMIT" in status_upper or status_upper == "CHECK":
            return "rgba(255,193,7,0.15)"
        if "PASS" in status_upper or status_upper == "OK":
            return "rgba(0,128,0,0.12)"
        return "rgba(31, 119, 180, 0.08)"

    shear_pack_summary = shear_pack or {}
    def _complete_summary_text(preferred, fallback) -> str:
        preferred_text = str(preferred or "").strip()
        if (
            preferred_text
            and "\u2014" not in preferred_text
            and "â€”" not in preferred_text
        ):
            return preferred_text
        fallback_text = str(fallback or "").strip()
        return fallback_text or "\u2014"

    shear_cap = _complete_summary_text(
        shear_pack_summary.get("summary_display_capacity"),
        shear_pack_summary.get("summary_capacity"),
    )
    shear_demand = _complete_summary_text(
        shear_pack_summary.get("summary_display_demand"),
        shear_pack_summary.get("summary_demand"),
    )
    shear_util_value = parse_util_value_fn(shear_pack_summary.get("summary_util"))
    shear_display_source = str(shear_pack_summary.get("summary_display_source") or "").strip()
    if shear_display_source == "sectional_required_shear":
        try:
            phi_vu_display = float(shear_pack_summary.get("summary_phiVu_kN") or 0.0)
            veq_display = float(shear_pack_summary.get("summary_Veq_kN") or 0.0)
            if phi_vu_display > 0.0 and veq_display >= 0.0:
                shear_util_value = veq_display / phi_vu_display
        except Exception:
            pass
    shear_util_str = "\u2014" if shear_util_value is None else f"{shear_util_value:.2f}"
    shear_status = str(shear_pack_summary.get("summary_status") or "").strip()
    shear_reason = str(shear_pack_summary.get("summary_reason") or "").strip()
    shear_governing_name = str(shear_pack_summary.get("summary_governing_check_name") or "").strip()
    shear_governing_source = str(shear_pack_summary.get("summary_governing_source") or "").strip()
    visible_shear_check_rows = [
        row for row in (SHEAR_ROWS or [])
        if isinstance(row, dict) and not row.get("is_informational")
    ]
    visible_shear_statuses = {
        str(row.get("status") or "").strip().upper()
        for row in visible_shear_check_rows
    }
    visible_shear_has_fail = any(status in {"FAIL", "NG"} for status in visible_shear_statuses)
    visible_shear_has_near = any(status == "NEAR LIMIT" for status in visible_shear_statuses)
    visible_shear_has_pass = any(status == "PASS" for status in visible_shear_statuses)
    shear_header_inconsistent_with_rows = (
        str(shear_status or "").strip().upper() in {"FAIL", "NG"}
        and not visible_shear_has_fail
        and not visible_shear_has_near
        and visible_shear_has_pass
        and shear_util_value is not None
        and shear_util_value <= 1.0
    )
    if shear_header_inconsistent_with_rows:
        shear_status = "PASS"
        shear_reason = ""
        shear_governing_name = "Sectional shear capacity"
        shear_governing_source = "visible_row_consistency_override"
    shear_status_upper = shear_status.upper()
    shear_governing_spacing_fail = bool(
        shear_status_upper not in ("", "PASS", "OK")
        and (
            "spacing" in shear_governing_name.lower()
            or "spacing" in shear_reason.lower()
            or "link spacing" in shear_governing_name.lower()
            or "link spacing" in shear_reason.lower()
        )
    )
    shear_summary_status_note = (
        "Fails on governing link spacing, not sectional shear"
        if shear_governing_spacing_fail else ""
    )
    visible_shear_summary_source = "canonical_pack_summary"
    if not shear_status:
        shear_cap = shear_primary.get("capacity") or shear_primary.get("value", "\u2014")
        shear_demand = shear_primary.get("action") or shear_primary.get("limit", "\u2014")
        shear_util_str = shear_primary.get("util", "\u2014")
        shear_status, _ = overall_status_from_rows_fn(SHEAR_ROWS)
        visible_shear_summary_source = "primary_row_fallback"
    shear_colour = _status_colour_from_summary(shear_status)
    st_module.session_state["_inputs_visible_shear_summary_debug"] = {
        "visible_shear_summary_source": visible_shear_summary_source,
        "visible_shear_summary_display_source": str(shear_pack_summary.get("summary_display_source") or "").strip(),
        "visible_shear_summary_governing_check_name": shear_governing_name,
        "visible_shear_summary_governing_source": shear_governing_source,
        "visible_shear_summary_reason": shear_reason,
        "visible_shear_summary_status_note": shear_summary_status_note,
    }

    crack_cap = crack_primary.get("capacity") or crack_primary.get("limit", "\u2014")
    crack_demand = crack_primary.get("action") or crack_primary.get("value", "\u2014")
    crack_util_str = crack_primary.get("util", "\u2014")
    crack_status, crack_colour = overall_status_from_rows_fn(CRACK_ROWS)

    defl_cap = defl_primary.get("capacity") or defl_primary.get("limit", "\u2014")
    defl_demand = defl_primary.get("action") or defl_primary.get("value", "\u2014")
    defl_util_str = defl_primary.get("util", "\u2014")
    defl_status, defl_colour = overall_status_from_rows_fn(DEFLECTION_ROWS)

    def _apply_neutral_override(rows, *, clear_values: bool = False):
        for row in rows:
            if not isinstance(row, dict):
                continue
            if row.get("is_informational"):
                continue
            row["status"] = "\u2014"
            row["ok"] = None
            row["util"] = "\u2014"
            if clear_values:
                for key in (
                    "capacity",
                    "action",
                    "calculated",
                    "requirement",
                    "value",
                    "limit",
                ):
                    row[key] = "\u2014"

    if no_loads_bending:
        _apply_neutral_override(BENDING_ROWS)
        bending_status = "\u2014"
        bending_colour = "rgba(31, 119, 180, 0.08)"
        bending_util_str = "\u2014"
    if no_loads_shear:
        _apply_neutral_override(SHEAR_ROWS)
        shear_status = "\u2014"
        shear_colour = "rgba(31, 119, 180, 0.08)"
        shear_util_str = "\u2014"
        shear_summary_status_note = ""
    if no_loads_crack:
        _apply_neutral_override(CRACK_ROWS, clear_values=True)
        crack_status = "\u2014"
        crack_colour = "rgba(31, 119, 180, 0.08)"
        crack_util_str = "\u2014"
        crack_cap = "\u2014"
        crack_demand = "\u2014"
    if no_loads_deflection:
        _apply_neutral_override(DEFLECTION_ROWS, clear_values=True)
        defl_status = "\u2014"
        defl_colour = "rgba(31, 119, 180, 0.08)"
        defl_util_str = "\u2014"
        defl_cap = "\u2014"
        defl_demand = "\u2014"

    return (
        bending_cap,
        bending_demand,
        bending_util_str,
        bending_status,
        bending_colour,
        shear_cap,
        shear_demand,
        shear_util_str,
        shear_status,
        shear_colour,
        shear_summary_status_note,
        shear_governing_name,
        shear_governing_source,
        shear_reason,
        crack_cap,
        crack_demand,
        crack_util_str,
        crack_status,
        crack_colour,
        defl_cap,
        defl_demand,
        defl_util_str,
        defl_status,
        defl_colour,
    )


__all__ = ["render_inputs_summary_display_state"]
