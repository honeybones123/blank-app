from __future__ import annotations

import html as html_stdlib
import re

import streamlit as st

from engineering_check_ui import (
    DEFLECTION_CHECK_SUMMARY_COLUMNS,
    ENGINEERING_CHECK_COLUMNS,
    summary_cell_display,
)
from ui.summary_cards import build_summary_detail_table_html


SUMMARY_DASH = "&mdash;"
_MOJIBAKE_MARKERS = ("\u00c3", "\ufffd")
_DASH_EQUIVALENTS = {
    "",
    "-",
    "\u2014",
    "\u2013",
    "&mdash;",
    "\u00e2\u20ac\u201d",
    "\u00e2\u20ac\u0094",
    "\u00c3\u00a2\u00e2\u201a\u00ac\u00e2\u20ac\u009d",
    "\u00c3\u0192\u00c2\u00a2\u00c3\u00a2\u00e2\u20ac\u0161\u00c2\u00ac\u00c3\u00a2\u00e2\u201a\u00ac\u00c2\u009d",
}



def _is_mojibake_text(value: object) -> bool:
    text = str(value or "")
    return any(marker in text for marker in _MOJIBAKE_MARKERS)


def normalise_summary_display_value(value: object, fallback: str = SUMMARY_DASH) -> str:
    """Normalise final-card display fallbacks without changing real numeric/text values."""
    text = str(value if value is not None else "").strip()
    if text in _DASH_EQUIVALENTS or _is_mojibake_text(text):
        return fallback
    return text


def _normalise_summary_status(status: object) -> str:
    text = normalise_summary_display_value(status, "")
    return text.upper() if text else ""


def _normalise_summary_row(row: dict) -> dict:
    normalised = dict(row or {})
    for key in (
        "capacity",
        "action",
        "calculated",
        "requirement",
        "value",
        "limit",
        "util",
        "status",
    ):
        if key in normalised:
            fallback = "" if key == "status" else SUMMARY_DASH
            normalised[key] = normalise_summary_display_value(normalised.get(key), fallback)
    return normalised


def _status_kind(status: object, ok: object = None, *, is_info: bool = False) -> str:
    if is_info:
        return "info"
    status_upper = str(status or "").strip().upper()
    if ok is True or status_upper in {"PASS", "OK"}:
        return "pass"
    if ok is False or status_upper in {"FAIL", "NG"}:
        return "fail"
    if status_upper in {"WARN", "WARNING", "NEAR LIMIT", "CHECK"}:
        return "warn"
    if status_upper == "CAPACITY":
        return "capacity"
    if status_upper in {"REQUIRES ACTION", "ACTION REQUIRED"}:
        return "requires-action"
    if status_upper == "INFO":
        return "info"
    if status_upper in {"NOT RUN", "INPUT REQUIRED"}:
        return "neutral"
    return "neutral"


def _status_label(status: object, kind: str) -> str:
    status_text = str(status or "").strip()
    if status_text and status_text not in {"—", "-"}:
        return status_text.upper()
    return {
        "pass": "PASS",
        "fail": "FAIL",
        "warn": "CHECK",
        "capacity": "CAPACITY",
        "requires-action": "REQUIRES ACTION",
        "info": "INFO",
    }.get(kind, "INFO")


def _threshold_text(kind: str) -> str:
    if kind == "fail":
        return "&gt; 1.00"
    if kind == "pass":
        return "&le; 1.00"
    if kind == "capacity":
        return "No pass/fail check run"
    if kind == "requires-action":
        return "Applied actions required"
    if kind == "warn":
        return "Review required"
    return "Reference"


def _summary_icon_svg(kind: str) -> str:
    if kind == "bending":
        return """
<svg viewBox="0 0 64 64" aria-hidden="true">
  <path d="M14 42 Q32 52 50 42" fill="none" stroke="currentColor" stroke-width="4" stroke-linecap="round"/>
  <path d="M32 12 V32" fill="none" stroke="currentColor" stroke-width="4" stroke-linecap="round"/>
  <path d="M24 26 L32 34 L40 26" fill="none" stroke="currentColor" stroke-width="4" stroke-linecap="round" stroke-linejoin="round"/>
</svg>
"""
    if kind == "shear":
        return """
<svg viewBox="0 0 64 64" aria-hidden="true">
  <rect x="10" y="16" width="44" height="32" fill="none" stroke="currentColor" stroke-width="3"/>
  <path d="M22 48 L44 16" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round"/>
</svg>
"""
    if kind == "crack":
        return """
<svg viewBox="0 0 64 64" aria-hidden="true">
  <path d="M40 8 L30 18 L36 27 L24 36 L28 45 L16 56" fill="none" stroke="currentColor" stroke-width="4" stroke-linecap="round" stroke-linejoin="round"/>
</svg>
"""
    if kind == "deflection":
        return """
<svg viewBox="0 0 64 64" aria-hidden="true">
  <path d="M12 42 Q32 54 52 42" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-dasharray="6 5"/>
  <path d="M14 30 V50 M50 30 V50" fill="none" stroke="currentColor" stroke-width="4" stroke-linecap="round"/>
  <path d="M14 30 L22 36 M50 30 L42 36" fill="none" stroke="currentColor" stroke-width="4" stroke-linecap="round"/>
</svg>
"""
    return """
<svg viewBox="0 0 64 64" aria-hidden="true">
  <path d="M16 18 H48 M16 32 H48 M16 46 H36" fill="none" stroke="currentColor" stroke-width="4" stroke-linecap="round"/>
</svg>
"""


def summary_card_css() -> str:
    return """
<style>
.summary-card-stack { display: grid; gap: 0.55rem; margin: 0.18rem 0 1rem; contain: layout paint; }
.summary-card-stack,
.summary-card-stack * { font-family: inherit; }
.summary-check-card {
  --accent: #64748b;
  --accent-soft: rgba(100,116,139,0.08);
  --accent-border: rgba(100,116,139,0.20);
  --metric-color: #0f172a;
  --metric-label-color: #64748b;
  position: relative;
  border: 1px solid rgba(49,51,63,0.12);
  border-radius: 8px;
  background: var(--accent-soft);
  box-shadow: 0 10px 30px rgba(15,23,42,0.04);
  overflow: hidden;
  contain: layout paint;
}
.summary-check-card::before {
  content: "";
  position: absolute;
  inset: 0 auto 0 0;
  width: 6px;
  background: var(--accent);
}
.summary-check-card.status-pass { --accent: #2f9e44; --accent-soft: rgba(47,158,68,0.08); --accent-border: rgba(47,158,68,0.28); }
.summary-check-card.status-fail { --accent: #e03131; --accent-soft: rgba(224,49,49,0.08); --accent-border: rgba(224,49,49,0.28); }
.summary-check-card.status-warn,
.summary-check-card.status-requires-action { --accent: #f08c00; --accent-soft: rgba(240,140,0,0.08); --accent-border: rgba(240,140,0,0.28); }
.summary-check-card.status-info { --accent: #4263eb; --accent-soft: rgba(66,99,235,0.08); --accent-border: rgba(66,99,235,0.28); }
.summary-check-card.status-capacity,
.summary-check-card.status-neutral { --accent: #2563eb; --accent-soft: rgba(37,99,235,0.07); --accent-border: rgba(37,99,235,0.23); }
.summary-check-card details { margin: 0; }
.summary-check-card summary {
  list-style: none;
  cursor: pointer;
  display: grid;
  grid-template-columns: minmax(260px, 1.45fr) repeat(3, minmax(140px, 0.7fr)) minmax(118px, 0.5fr) 24px;
  gap: 0.95rem;
  align-items: center;
  min-height: 92px;
  padding: 0.9rem 1.1rem 0.9rem 1.45rem;
  user-select: none;
}
.summary-check-card summary::-webkit-details-marker { display: none; }
.summary-check-card summary::marker { content: ""; }
.summary-title-block { display: flex; align-items: center; gap: 1rem; min-width: 0; }
.summary-icon-tile {
  width: 56px;
  height: 56px;
  border-radius: 8px;
  background: rgba(255,255,255,0.6);
  border: 1px solid var(--accent-border);
  color: var(--accent);
  display: grid;
  place-items: center;
  flex: 0 0 auto;
}
.summary-icon-tile svg { width: 40px; height: 40px; }
.summary-check-title { font-size: 1.18rem; line-height: 1.18; font-weight: 800; color: #0f172a; }
.summary-metric { border-left: 1px solid rgba(148,163,184,0.32); padding-left: 0.95rem; min-width: 0; }
.summary-metric-label { color: var(--metric-label-color); font-size: 0.84rem; line-height: 1.18; margin-bottom: 0.34rem; }
.summary-metric-value { color: var(--metric-color); font-weight: 800; font-size: 1.08rem; line-height: 1.2; overflow-wrap: anywhere; }
.summary-util .summary-metric-value { font-size: 1.18rem; }
.summary-status-wrap { display: grid; justify-items: center; gap: 0.25rem; border-left: 1px solid rgba(148,163,184,0.32); padding-left: 0.95rem; }
.summary-status-pill {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 96px;
  border-radius: 999px;
  padding: 0.52rem 0.82rem;
  font-size: 0.84rem;
  font-weight: 800;
  letter-spacing: 0.01em;
  color: #fff;
  background: var(--accent);
}
.summary-status-threshold { color: var(--accent); font-weight: 800; font-size: 0.76rem; text-align: center; }
.summary-status-threshold:empty { display: none; }
.summary-card-chevron { color: #0f172a; font-size: 1.1rem; transition: transform 0.18s ease; justify-self: center; }
.summary-check-card details[open] .summary-card-chevron { transform: rotate(180deg); }
.summary-detail-shell { padding: 0 1.25rem 1.15rem 1.6rem; }
.summary-detail-inner {
  background: rgba(255,255,255,0.82);
  border: 1px solid rgba(148,163,184,0.22);
  border-radius: 8px;
  box-shadow: inset 0 1px 0 rgba(255,255,255,0.8);
  overflow-x: auto;
}
.summary-detail-title { font-weight: 800; color: #0f172a; margin: 0 0 0.65rem; }
.summary-detail-table { width: 100%; border-collapse: collapse; min-width: 760px; font-size: 0.95rem; }
.summary-detail-table th {
  background: rgba(248,250,252,0.96);
  color: #334155;
  text-align: left;
  padding: 0.86rem 0.95rem;
  border-bottom: 1px solid rgba(148,163,184,0.22);
  border-right: 1px solid rgba(148,163,184,0.18);
}
.summary-detail-table th:last-child,
.summary-detail-table td:last-child { border-right: 0; }
.summary-detail-table td {
  position: relative;
  padding: 0.82rem 0.95rem;
  border-bottom: 1px solid rgba(148,163,184,0.18);
  border-right: 1px solid rgba(148,163,184,0.14);
  color: #0f172a;
}
.summary-detail-table tr:last-child td { border-bottom: 0; }
.summary-detail-row.status-pass td { background: rgba(47,158,68,0.055); }
.summary-detail-row.status-fail td { background: rgba(224,49,49,0.075); }
.summary-detail-row.status-warn td,
.summary-detail-row.status-requires-action td { background: rgba(240,140,0,0.06); }
.summary-detail-row.status-info td { background: rgba(66,99,235,0.04); }
.summary-detail-row.status-capacity td,
.summary-detail-row.status-neutral td { background: rgba(37,99,235,0.035); }
.summary-detail-row.primary td:first-child { font-weight: 800; }
.summary-detail-row:hover td { background: rgba(15,23,42,0.045); }
.summary-detail-row .hint { opacity: 0; margin-left: 0.35rem; color: #64748b; font-size: 0.82rem; }
.summary-detail-row:hover .hint { opacity: 1; }
.summary-row-chevron { float: right; color: #0f172a; font-weight: 800; }
.summary-detail-status-pill {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: 1px solid currentColor;
  border-radius: 5px;
  padding: 0.12rem 0.46rem;
  font-size: 0.78rem;
  font-weight: 800;
  color: var(--accent);
  background: rgba(255,255,255,0.74);
}
.summary-detail-row.status-pass .summary-detail-status-pill { color: #2f9e44; }
.summary-detail-row.status-fail .summary-detail-status-pill { color: #e03131; }
.summary-detail-row.status-warn .summary-detail-status-pill,
.summary-detail-row.status-requires-action .summary-detail-status-pill { color: #f08c00; }
.summary-detail-row.status-info .summary-detail-status-pill { color: #4263eb; }
.summary-detail-row.status-capacity .summary-detail-status-pill,
.summary-detail-row.status-neutral .summary-detail-status-pill { color: #2563eb; }
.row-link { position: absolute; inset: 0; z-index: 5; display: block; cursor: pointer; }
.summary-detail-table .row-link {
  position: static;
  inset: auto;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.45rem;
  color: inherit;
  text-decoration: none;
  width: 100%;
}
@media (max-width: 720px) {
  .summary-check-card summary {
    grid-template-columns: 1fr 24px;
    gap: 0.8rem;
  }
  .summary-title-block,
  .summary-metric,
  .summary-status-wrap { grid-column: 1 / 2; }
  .summary-card-chevron { grid-column: 2 / 3; grid-row: 1; align-self: start; margin-top: 1rem; }
  .summary-metric,
  .summary-status-wrap { border-left: 0; padding-left: 0; }
  .summary-status-wrap { justify-items: start; }
  .summary-util .summary-metric-value { font-size: 1.2rem; }
}
</style>
"""


def _infer_card_meta(rows, key_prefix: str) -> dict[str, str]:
    key = str(key_prefix or "").lower()
    titles = " ".join(str((r or {}).get("title") or (r or {}).get("check") or "") for r in rows).lower()
    probe = f"{key} {titles}"
    if "bend" in probe or "flexural" in probe:
        return {
            "family": "bending",
            "title": "Bending &mdash; ULS",
            "description": "",
        }
    if "shear" in probe or "mcft" in probe:
        return {
            "family": "shear",
            "title": "Shear &mdash; ULS",
            "description": "",
        }
    if "crack" in probe:
        return {
            "family": "crack",
            "title": "Crack control &mdash; SLS",
            "description": "",
        }
    if "defl" in probe:
        return {
            "family": "deflection",
            "title": "Deflection &mdash; SLS",
            "description": "",
        }
    return {
        "family": "generic",
        "title": "Summary checks",
        "description": "",
    }


def _overall_status_from_rows(rows) -> tuple[str, str]:
    non_info = [
        r for r in rows
        if not bool((r or {}).get("is_informational"))
        and str((r or {}).get("status", "")).strip().upper() != "INFO"
    ]
    if any(_status_kind(r.get("status"), r.get("ok")) == "fail" for r in non_info):
        return "FAIL", "fail"
    if any(_status_kind(r.get("status"), r.get("ok")) in {"warn", "requires-action"} for r in non_info):
        return "CHECK", "warn"
    if any(_status_kind(r.get("status"), r.get("ok")) == "pass" for r in non_info):
        return "PASS", "pass"
    return "INFO", "info"


def _primary_summary_row(rows, family: str = "") -> dict:
    if family == "crack":
        for row in rows:
            uid = str((row or {}).get("uid") or "").lower()
            title = str((row or {}).get("title") or "").lower()
            if uid == "crk_step_3" or "direct crack width" in title:
                return row
    for row in rows:
        if isinstance(row, dict) and row.get("is_primary"):
            return row
    for row in rows:
        if isinstance(row, dict) and not row.get("is_informational"):
            return row
    return rows[0] if rows else {}


def _numeric_prefix(value: object) -> float | None:
    text = str(value or "").strip().replace(",", "")
    match = re.search(r"[-+]?\d+(?:\.\d+)?", text)
    if not match:
        return None
    try:
        return float(match.group(0))
    except Exception:
        return None


def _is_zero_or_missing_action(action: object) -> bool:
    text = str(action or "").strip().lower()
    if not text or text in {"—", "-", "&mdash;", "not supplied"}:
        return True
    value = _numeric_prefix(text)
    return value is not None and abs(value) <= 1e-12


def _capacity_only_status_for_family(family: str, action: object, util: object, status: object) -> str | None:
    if str(status or "").strip().upper() not in {"PASS", "OK", "CAPACITY", "REQUIRES ACTION"}:
        return None
    util_value = _numeric_prefix(util)
    if util_value is not None and abs(util_value) > 1e-12:
        return None
    if not _is_zero_or_missing_action(action):
        return None
    return "NOT RUN" if family == "deflection" else "CAPACITY"


def build_final_summary_check_card_model(
    *,
    family: str,
    rows,
    key_prefix: str = "",
    title: str | None = None,
    description: str = "",
    capacity: object = None,
    action: object = None,
    utilisation: object = None,
    status: object = None,
    columns=None,
    open_by_default: bool = False,
    route_links: bool = True,
    threshold_text: str | None = None,
    status_note_html: str = "",
    capacity_label: str | None = None,
    action_label: str | None = None,
) -> dict:
    """
    Build the Inputs/final-summary card model using the same display rules as
    specialised summary tables.

    Inputs may pass raw-ish override values, but dash fallbacks, capacity-only
    rows, primary-row selection, deflection NOT RUN handling, and value/limit
    mapping are resolved here.
    """
    display_rows = [
        _normalise_summary_row(dict(row))
        for row in list(rows or [])
        if isinstance(row, dict) and any(str(value or "").strip() for value in dict(row).values())
    ]
    meta = _infer_card_meta(display_rows, key_prefix or family)
    family_name = str(family or meta["family"] or "").strip().lower()
    if not family_name:
        family_name = meta["family"]
    if columns is None:
        columns = (
            list(DEFLECTION_CHECK_SUMMARY_COLUMNS)
            if family_name == "deflection"
            else list(ENGINEERING_CHECK_COLUMNS)
        )

    primary = _primary_summary_row(display_rows, family_name)
    row_status, kind = _overall_status_from_rows(display_rows)
    if primary:
        primary_kind = _status_kind(
            primary.get("status"),
            primary.get("ok"),
            is_info=bool(primary.get("is_informational")),
        )
        if primary_kind in {"fail", "warn", "pass", "capacity", "requires-action"} or str(primary.get("status") or "").strip().upper() in {"NOT RUN", "INPUT REQUIRED"}:
            row_status = primary.get("status") or row_status
            kind = primary_kind

    if family_name == "deflection":
        row_action = summary_cell_display(primary, "calculated") if primary else SUMMARY_DASH
        row_capacity = summary_cell_display(primary, "requirement") if primary else SUMMARY_DASH
    else:
        row_capacity = summary_cell_display(primary, "capacity") if primary else SUMMARY_DASH
        row_action = summary_cell_display(primary, "action") if primary else "Not supplied"
    row_util = primary.get("util", SUMMARY_DASH) if primary else SUMMARY_DASH

    model_capacity = normalise_summary_display_value(capacity, "") or normalise_summary_display_value(row_capacity)
    model_action = normalise_summary_display_value(action, "") or normalise_summary_display_value(row_action, "Not supplied")
    model_util = normalise_summary_display_value(utilisation, "") or normalise_summary_display_value(row_util)
    model_status = _normalise_summary_status(status) or _normalise_summary_status(row_status)

    capacity_only_probe = (
        summary_cell_display(primary, "action")
        if family_name == "deflection" and primary
        else model_action
    )
    capacity_only_status = _capacity_only_status_for_family(
        family_name,
        normalise_summary_display_value(capacity_only_probe, ""),
        model_util,
        model_status,
    )
    if capacity_only_status:
        model_status = capacity_only_status
        kind = _status_kind(model_status)
        if family_name != "deflection":
            model_action = "Not supplied"
        model_util = SUMMARY_DASH
        overridden_rows = []
        for row in display_rows:
            display_row = dict(row)
            if not display_row.get("is_informational"):
                display_row["status"] = capacity_only_status
                display_row["ok"] = None
                display_row["util"] = SUMMARY_DASH
                if family_name != "deflection":
                    display_row["action"] = "Not supplied"
            overridden_rows.append(display_row)
        display_rows = overridden_rows
    else:
        kind = _status_kind(model_status)

    if kind in {"capacity", "requires-action"}:
        model_util = SUMMARY_DASH

    final_threshold = threshold_text
    if final_threshold is None:
        final_threshold = ""

    return {
        "title": title if title is not None else meta["title"],
        "description": description,
        "family": family_name,
        "capacity": model_capacity,
        "action": model_action,
        "utilisation": model_util,
        "status": model_status,
        "rows": display_rows,
        "columns": columns,
        "open_by_default": open_by_default,
        "route_links": route_links,
        "threshold_text": final_threshold,
        "status_note_html": status_note_html,
        "capacity_label": capacity_label or ("Design limit" if family_name == "deflection" else "Capacity"),
        "action_label": action_label or ("Calculated deflection" if family_name == "deflection" else "Applied"),
    }


def build_final_summary_check_card_html(**kwargs) -> str:
    model = build_final_summary_check_card_model(**kwargs)
    return build_summary_check_card_html(**model)


def build_summary_check_card_html(
    *,
    title: str,
    description: str,
    family: str,
    capacity: object,
    action: object,
    utilisation: object,
    status: object,
    rows,
    columns=None,
    open_by_default: bool = False,
    route_links: bool = False,
    threshold_text: str | None = None,
    status_note_html: str = "",
    capacity_label: str = "Calculated capacity",
    action_label: str = "Applied design action",
) -> str:
    title = str(title or "").strip()
    has_header_content = bool(title)
    has_metric_content = any(
        str(value or "").strip()
        and str(value or "").strip() not in {"-", "&mdash;", "—"}
        for value in (capacity, action, utilisation, status, threshold_text, status_note_html)
    )
    has_detail_rows = any(
        any(str(value or "").strip() for value in dict(row or {}).values())
        for row in list(rows or [])
        if isinstance(row, dict)
    )
    if not has_header_content and not has_metric_content and not has_detail_rows:
        return ""
    if not title:
        title = f"{str(family or 'Design').strip().title()} check"
    if str(family or "").strip().lower() == "shear":
        numeric_rows = []
        for row in list(rows or []):
            if not isinstance(row, dict) or row.get("is_informational"):
                continue
            row_status = str(row.get("status") or "").strip().upper()
            if row_status in {"INFO", "-", "—"}:
                continue
            row_util = _numeric_prefix(row.get("util"))
            if row_util is None:
                continue
            numeric_rows.append((row_util, row))
        if numeric_rows:
            governing_util, governing_row = max(numeric_rows, key=lambda item: item[0])
            header_util = _numeric_prefix(utilisation)
            if header_util is None or abs(float(header_util) - float(governing_util)) > 1e-9:
                utilisation = f"{governing_util:.2f}"
                capacity = governing_row.get("capacity") or governing_row.get("value") or capacity
                action = governing_row.get("action") or governing_row.get("limit") or action
                status = governing_row.get("status") or status
    kind = _status_kind(status)
    label = _status_label(status, kind)
    threshold = _threshold_text(kind) if threshold_text is None else threshold_text
    capacity_text = str(capacity if capacity not in (None, "") else "&mdash;")
    action_text = str(action if action not in (None, "") else "Not supplied")
    util_text = str(utilisation if utilisation not in (None, "") else "&mdash;")
    if kind in {"capacity", "requires-action"}:
        util_text = "&mdash;"
    detail_html = build_summary_detail_table_html(rows, columns=columns, route_links=route_links)
    open_attr = " open" if open_by_default else ""
    icon_html = " ".join(_summary_icon_svg(family).split())
    card_html = f"""
<div class="summary-check-card status-{kind}">
  <details{open_attr}>
    <summary>
      <div class="summary-title-block">
        <div class="summary-icon-tile">{icon_html}</div>
        <div>
          <div class="summary-check-title">{title}</div>
        </div>
      </div>
      <div class="summary-metric">
        <div class="summary-metric-label">{html_stdlib.escape(str(action_label))}</div>
        <div class="summary-metric-value">{action_text}</div>
      </div>
      <div class="summary-metric">
        <div class="summary-metric-label">{html_stdlib.escape(str(capacity_label))}</div>
        <div class="summary-metric-value">{capacity_text}</div>
      </div>
      <div class="summary-metric summary-util">
        <div class="summary-metric-label">Utilisation</div>
        <div class="summary-metric-value">{util_text}</div>
      </div>
      <div class="summary-status-wrap">
        <div class="summary-status-pill">{html_stdlib.escape(label)}</div>
        <div class="summary-status-threshold">{threshold}</div>
        {status_note_html}
      </div>
      <div class="summary-card-chevron">&#8964;</div>
    </summary>
    <div class="summary-detail-shell">
      <div class="summary-detail-title">Detailed checks</div>
      {detail_html}
    </div>
  </details>
</div>
"""
    return "".join(line.strip() for line in card_html.splitlines())


def render_clickable_summary_table(rows, key_prefix="summary", columns=None):
    """
    Render the modern expandable summary card with clickable detailed rows.
    """
    rows = [
        _normalise_summary_row(dict(row))
        for row in list(rows or [])
        if isinstance(row, dict) and any(str(value or "").strip() for value in dict(row).values())
    ]
    if not rows:
        return None

    meta = _infer_card_meta(rows, key_prefix)
    if columns is None:
        columns = (
            list(DEFLECTION_CHECK_SUMMARY_COLUMNS)
            if meta["family"] == "deflection"
            else list(ENGINEERING_CHECK_COLUMNS)
        )
    primary = _primary_summary_row(rows, meta["family"])
    status, kind = _overall_status_from_rows(rows)
    if primary:
        primary_kind = _status_kind(
            primary.get("status"),
            primary.get("ok"),
            is_info=bool(primary.get("is_informational")),
        )
        if primary_kind in {"fail", "warn", "pass", "capacity", "requires-action"} or str(primary.get("status") or "").strip().upper() in {"NOT RUN", "INPUT REQUIRED"}:
            status = primary.get("status") or status
            kind = primary_kind

    if meta["family"] == "deflection":
        action = summary_cell_display(primary, "calculated") if primary else "&mdash;"
        capacity = summary_cell_display(primary, "requirement") if primary else "&mdash;"
    else:
        capacity = summary_cell_display(primary, "capacity") if primary else "&mdash;"
        action = summary_cell_display(primary, "action") if primary else "Not supplied"
    util = primary.get("util", "&mdash;") if primary else "&mdash;"
    capacity_only_probe = summary_cell_display(primary, "action") if meta["family"] == "deflection" and primary else action
    capacity_only_status = _capacity_only_status_for_family(meta["family"], capacity_only_probe, util, status)
    display_rows = rows
    if capacity_only_status:
        status = capacity_only_status
        kind = _status_kind(status)
        if meta["family"] != "deflection":
            action = "Not supplied"
        util = "&mdash;"
        display_rows = []
        for row in rows:
            display_row = dict(row)
            if not display_row.get("is_informational"):
                display_row["status"] = capacity_only_status
                display_row["ok"] = None
                display_row["util"] = "&mdash;"
                if meta["family"] != "deflection":
                    display_row["action"] = "Not supplied"
            display_rows.append(display_row)
    if kind in {"capacity", "requires-action"}:
        util = "&mdash;"

    st.markdown(summary_card_css(), unsafe_allow_html=True)
    card_html = build_summary_check_card_html(
        title=meta["title"],
        description=meta["description"],
        family=meta["family"],
        capacity=capacity,
        action=action,
        utilisation=util,
        status=status,
        rows=display_rows,
        columns=columns,
        open_by_default=True,
        route_links=False,
        threshold_text="",
        capacity_label="Design limit" if meta["family"] == "deflection" else "Capacity",
        action_label="Calculated deflection" if meta["family"] == "deflection" else "Applied",
    )
    st.markdown(f'<div class="summary-card-stack">{card_html}</div>', unsafe_allow_html=True)
    return None


# Backwards-compatible private alias for legacy imports from ui_seamless_steps.
_summary_card_css = summary_card_css
