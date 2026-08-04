from __future__ import annotations

import html as html_stdlib
import json
from urllib.parse import urlencode

import streamlit as st

from engineering_check_ui import (
    ENGINEERING_CHECK_COLUMNS,
    resolve_jump_target_id,
    summary_cell_display,
)


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
    if status_text and status_text not in {"â€”", "-"}:
        return status_text.upper()
    return {
        "pass": "PASS",
        "fail": "FAIL",
        "warn": "CHECK",
        "capacity": "CAPACITY",
        "requires-action": "REQUIRES ACTION",
        "info": "INFO",
    }.get(kind, "INFO")


def build_summary_detail_table_html(rows, columns=None, *, route_links: bool = False) -> str:
    rows = [
        dict(row)
        for row in list(rows or [])
        if any(str(value or "").strip() for value in dict(row or {}).values())
    ]
    if not rows:
        return '<div class="summary-detail-empty">Detailed check rows are not available for this summary.</div>'
    if columns is None:
        columns = list(ENGINEERING_CHECK_COLUMNS)
    header_cells = []
    for col in columns:
        label = col.get("label", "")
        if str(label).strip().lower() == "util":
            label = "Utilisation"
        header_cells.append(f"<th>{label}</th>")
    html_parts = [
        '<div class="summary-detail-inner">',
        '<table class="summary-detail-table">',
        "<thead><tr>",
        "".join(header_cells),
        "</tr></thead><tbody>",
    ]
    for r in rows:
        uid = r.get("uid", "")
        jump_id = resolve_jump_target_id(r)
        check = r.get("title") or r.get("check", uid)
        ok = r.get("ok")
        status = r.get("status", "")
        tab = r.get("tab", "")
        is_info = bool(r.get("is_informational")) or str(status).strip().upper() == "INFO"
        kind = _status_kind(status, ok, is_info=is_info)
        primary = "primary" if r.get("is_primary") else ""
        row_class = f"summary-detail-row status-{kind} {primary}".strip()
        route_page = str(r.get("route_page") or "").strip()
        jump_qp = str(jump_id or uid or "").strip()
        query = {"page": route_page, "jump": jump_qp}
        if str(uid) and str(uid) != jump_qp:
            query["jump_row"] = str(uid)
        href = "?" + urlencode(query) if (route_links and route_page) else "#"
        click_attr = ' onclick="event.stopPropagation(); window.location.href=this.href; return false;"' if (route_links and route_page) else ""
        td_click_attr = (
            f' role="link" tabindex="0" onclick="event.stopPropagation(); window.location.href=\'{html_stdlib.escape(href, quote=True)}\';"'
            f' onkeydown="if(event.key===\'Enter\'||event.key===\' \'){{event.preventDefault(); event.stopPropagation(); window.location.href=\'{html_stdlib.escape(href, quote=True)}\';}}"'
            if (route_links and route_page) else ""
        )
        cells = []
        for i, col in enumerate(columns):
            key = col.get("key")
            if i == 0:
                value = r.get(key)
                if value is None and key in ("title", "check"):
                    value = check
                elif value is None:
                    value = check
                cell = f"""
  <td{td_click_attr}>
    <a class="row-link" href="{html_stdlib.escape(href, quote=True)}" data-uid="{html_stdlib.escape(str(uid), quote=True)}" data-jump-target="{html_stdlib.escape(str(jump_id), quote=True)}" data-tab="{html_stdlib.escape(str(tab), quote=True)}"{click_attr}>
      <span>{value}<span class="hint">jump to calc</span></span><span class="summary-row-chevron">&rsaquo;</span>
    </a>
  </td>
"""
            elif key in ("capacity", "action", "calculated", "requirement"):
                cell = f"  <td>{summary_cell_display(r, key)}</td>"
            elif key == "status":
                label = html_stdlib.escape(_status_label(status, kind))
                cell = f'  <td><span class="summary-detail-status-pill">{label}</span></td>'
            else:
                value = r.get(key, "")
                cell = f"  <td>{value}</td>"
            cells.append(cell)
        html_parts.append(f'<tr class="{row_class}" data-tab="{html_stdlib.escape(str(tab), quote=True)}">{"".join(cells)}</tr>')
    html_parts.append("</tbody></table></div>")
    return "".join(line.strip() for line in "".join(html_parts).splitlines())


def _generate_summary_table_html(rows: list[dict]) -> str:
    return build_summary_detail_table_html(rows, route_links=True)


@st.cache_data(show_spinner=False)
def cached_generate_summary_table_html(rows_json: str) -> str:
    return _generate_summary_table_html(json.loads(rows_json))
