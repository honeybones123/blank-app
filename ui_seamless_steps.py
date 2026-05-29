import html as html_stdlib
import re
import streamlit as st
import streamlit.components.v1 as components
from urllib.parse import urlencode

from engineering_check_ui import (
    DEFLECTION_CHECK_SUMMARY_COLUMNS,
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


def _summary_card_css() -> str:
    return """
<style>
.summary-card-stack { display: grid; gap: 0.55rem; margin: 0.4rem 0 1rem; }
.summary-check-card {
  --accent: #64748b;
  --accent-soft: rgba(100,116,139,0.08);
  --accent-border: rgba(100,116,139,0.20);
  --metric-color: #0f172a;
  --metric-label-color: #64748b;
  position: relative;
  border: 1px solid rgba(49,51,63,0.12);
  border-radius: 18px;
  background: var(--accent-soft);
  box-shadow: 0 10px 30px rgba(15,23,42,0.04);
  overflow: hidden;
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
  border-radius: 14px;
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
  border-radius: 10px;
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
  border-radius: 10px;
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
@media (max-width: 960px) {
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


def inject_seamless_steps_css():
    st.markdown(
        """
<style>
/* flash animation */
@keyframes flash {
  0% { box-shadow: none; }
  15% { box-shadow: 0 0 0 6px rgba(255,193,7,0.6); }
  100% { box-shadow: none; }
}
.flash-target {
  animation: flash 1.25s ease-in-out 1;
  border-radius: 8px;
}

/* step wrapper spacing */
.step-wrap { margin: 10px 0; }

/* Make scroll land nicely below the header */
[id^="calc_"] {
  scroll-margin-top: 96px;
}

/* expander styling to match test app */
div[data-testid="stExpander"] {
  margin: 0.15rem 0 !important;
}

div[data-testid="stExpander"] details {
  border: 1px solid rgba(49,51,63,0.15) !important;
  border-radius: 10px !important;
  overflow: hidden !important;
}

div[data-testid="stExpander"] summary {
  background: rgba(49,51,63,0.03) !important;
  padding: 0.65rem 0.85rem !important;
  font-weight: 600 !important;
  cursor: pointer;
}

div[data-testid="stExpander"] .stMarkdown,
div[data-testid="stExpander"] .stAlert {
  padding-left: 0.85rem !important;
  padding-right: 0.85rem !important;
}
</style>
""",
        unsafe_allow_html=True,
    )


def _render_clickable_summary_table_legacy(rows, key_prefix="summary", columns=None):
    """
    Render summary table matching the test app style.
    Uses HTML table with clickable row links.
    """
    st.markdown("""
<style>
.summary-wrap {
  border: 1px solid rgba(49,51,63,0.15);
  border-radius: 10px;
  overflow: hidden;
}

.summary-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 16px;
}

.summary-table th {
  background: rgba(49,51,63,0.05);
  text-align: left;
  padding: 14px;
  color: rgba(49,51,63,0.7);
}

.summary-table td {
  padding: 14px;
  border-top: 1px solid rgba(49,51,63,0.1);
  position: relative;
}

/* Default neutral background (matches calcbox blue) - only for rows without pass/fail/warn classes */
.summary-table tbody tr:not(.pass):not(.fail):not(.warn) td {
  background: rgba(31, 119, 180, 0.08);
}

tr.pass td { background: rgba(0,128,0,0.12); }
tr.fail td { background: rgba(255,0,0,0.12); }
tr.warn td { background: rgba(255,193,7,0.15); }

tr.primary td {
  font-weight: 700;
}

tr:hover td { background: rgba(0,0,0,0.04); }

.row-link {
  position: absolute;
  inset: 0;
  z-index: 5;
  display: block;
  cursor: pointer;
}

.hint {
  opacity: 0;
  font-size: 0.9em;
  margin-left: 6px;
  color: rgba(49,51,63,0.6);
}
tr:hover .hint { opacity: 1; }
</style>
""", unsafe_allow_html=True)

    # Build HTML table exactly like test app (avoid name "html" — shadows stdlib html module)
    html_parts = ['<div class="summary-wrap"><table class="summary-table">']
    if columns is None:
        columns = list(ENGINEERING_CHECK_COLUMNS)

    header_cells = []
    for col in columns:
        width = col.get("width")
        width_attr = f' style="width:{width}"' if width else ""
        header_cells.append(f"<th{width_attr}>{col.get('label','')}</th>")

    html_parts.append(
        f"""
<thead>
<tr>
  {''.join(header_cells)}
</tr>
</thead>
<tbody>
"""
    )

    for r in rows:
        uid = r["uid"]
        jump_id = resolve_jump_target_id(r)
        # Support both "title" and "check" for the check name
        check = r.get("title") or r.get("check", uid)
        ok = r.get("ok")
        tab = r.get("tab", "")
        status = r.get("status", "")
        
        status_norm = str(status).upper()
        if r.get("is_informational") or status_norm == "INFO":
            cls = ""
        else:
            cls = (
                "pass" if ok is True
                else "fail" if ok is False
                else "warn" if status_norm in ("NEAR LIMIT", "WARN", "CHECK")
                else ""
            )
        primary = "primary" if r.get("is_primary") else ""
        row_class = f"{cls} {primary}".strip()
        
        cells = []
        for i, col in enumerate(columns):
            key = col.get("key")
            if i == 0:
                text = r.get(key)
                if text is None and key in ("title", "check"):
                    text = check
                elif text is None:
                    text = check
                cell = f"""
  <td>
    {text} <span class="hint">↳ jump to calc</span>
    <a class="row-link" href="#" data-uid="{html_stdlib.escape(str(uid), quote=True)}" data-jump-target="{html_stdlib.escape(str(jump_id), quote=True)}" data-tab="{html_stdlib.escape(str(tab), quote=True)}"></a>
  </td>
"""
            else:
                if key in ("capacity", "action", "calculated", "requirement"):
                    val = summary_cell_display(r, key)
                else:
                    val = r.get(key, "")
                cell = f"  <td>{val}</td>"
            cells.append(cell)

        html_parts.append(
            f"""
<tr class="{row_class}" data-tab="{tab}">
{''.join(cells)}
</tr>
"""
        )

    html_parts.append("</tbody></table></div>")
    st.markdown("".join(html_parts), unsafe_allow_html=True)


def render_clickable_summary_table(rows, key_prefix="summary", columns=None):
    """
    Render the modern expandable summary card with clickable detailed rows.
    """
    rows = [
        dict(row)
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

    st.markdown(_summary_card_css(), unsafe_allow_html=True)
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
        open_by_default=kind in {"fail", "warn", "requires-action"},
        route_links=False,
        threshold_text="SLS load not supplied" if (meta["family"] == "deflection" and status == "NOT RUN") else "",
        capacity_label="Design limit" if meta["family"] == "deflection" else "Capacity",
        action_label="Calculated deflection" if meta["family"] == "deflection" else "Applied",
    )
    st.markdown(f'<div class="summary-card-stack">{card_html}</div>', unsafe_allow_html=True)
    return None


def bind_summary_clicks():
    """
    Binds JavaScript to handle opening expanders and smooth scrolling when summary rows are clicked.
    Finds expanders by searching all expanders and picking the one that comes after the marker in document order.
    """
    components.html(
        r"""
<script>
(function() {
  const doc = window.parent.document;

  function isScrollable(el) {
    if (!el) return false;
    const style = window.getComputedStyle(el);
    const oy = style.overflowY;
    const canScroll = (oy === "auto" || oy === "scroll");
    return canScroll && el.scrollHeight > el.clientHeight + 2;
  }

  function findBestScroller() {
    const candidates = [
      doc.querySelector('section.main'),
      doc.querySelector('[data-testid="stAppViewContainer"]'),
      doc.querySelector('[data-testid="stMain"]'),
      doc.querySelector('.main'),
    ].filter(Boolean);

    for (const c of candidates) {
      if (isScrollable(c)) return c;
      if (isScrollable(c.parentElement)) return c.parentElement;
    }
    if (isScrollable(doc.body)) return doc.body;
    if (isScrollable(doc.documentElement)) return doc.documentElement;
    return null;
  }

  function scrollToAnchor(anchor) {
    const scroller = findBestScroller();
    if (!scroller) {
      const y = anchor.getBoundingClientRect().top + window.parent.scrollY - 12;
      window.parent.scrollTo({ top: y, behavior: "smooth" });
      return;
    }

    const aRect = anchor.getBoundingClientRect();
    const sRect = scroller.getBoundingClientRect ? scroller.getBoundingClientRect() : { top: 0 };
    const targetTop = (scroller.scrollTop || 0) + (aRect.top - sRect.top) - 12;

    try { scroller.scrollTo({ top: targetTop, behavior: "smooth" }); }
    catch (e) { scroller.scrollTop = targetTop; }
  }

  function switchToTab(tabName) {
    if (!tabName) return Promise.resolve();
    
    // Try to find Streamlit tabs (rendered as buttons with data-baseweb="tab")
    const tabButtons = doc.querySelectorAll('button[data-baseweb="tab"]');
    for (const button of tabButtons) {
      const buttonText = button.textContent.trim();
      if (buttonText === tabName) {
        // Check if tab is already selected (has aria-selected="true")
        if (button.getAttribute('aria-selected') !== 'true') {
          console.log("Switching to tab:", tabName);
          button.click();
          // Wait a bit for tab to switch
          return new Promise(resolve => setTimeout(resolve, 300));
        }
        return Promise.resolve();
      }
    }
    
    // Fallback: try to find radio buttons (for backward compatibility)
    const radios = doc.querySelectorAll('input[type="radio"]');
    for (const radio of radios) {
      const label = radio.closest('label') || radio.parentElement?.querySelector('label');
      if (label && label.textContent.trim() === tabName) {
        if (!radio.checked) {
          console.log("Switching to tab (radio):", tabName);
          radio.click();
          return new Promise(resolve => setTimeout(resolve, 300));
        }
        return Promise.resolve();
      }
    }
    return Promise.resolve();
  }

  function findExpanderForUid(uid) {
    console.log("=== Finding expander for uid:", uid, "===");
    
    // First, try to find custom details element from clickable_calcbox (id="cb-{uid}")
    const customDetails = doc.getElementById(`cb-${uid}`);
    if (customDetails) {
      console.log("Found custom details element for uid:", uid);
      return customDetails;
    }
    
    // Find the marker
    const marker = doc.querySelector(`[data-calc-uid="${uid}"]`);
    if (!marker) {
      console.warn("Marker not found for uid:", uid);
      return null;
    }
    console.log("Found marker:", marker);
    
    // Streamlit expanders are wrapped in div[data-testid="stExpander"] which contains a <details> element
    // Find ALL expander divs, then get their details children
    const expanderDivs = Array.from(doc.querySelectorAll('div[data-testid="stExpander"]'));
    console.log("Found", expanderDivs.length, "total expander divs on page");
    
    // Extract the details elements from each expander div
    const allDetails = expanderDivs.map(div => div.querySelector('details')).filter(Boolean);
    console.log("Found", allDetails.length, "details elements in expanders");
    
    // Find the first details element that comes after the marker in document order
    for (const details of allDetails) {
      // Check if this expander comes after the marker in document order
      const position = marker.compareDocumentPosition(details);
      const isAfter = (position & Node.DOCUMENT_POSITION_FOLLOWING) !== 0;
      
      if (isAfter) {
        // Found an expander after the marker
        // Check if they're reasonably close by finding common ancestor depth
        let commonAncestor = null;
        let m = marker.parentElement;
        let d = details.parentElement;
        let depth = 0;
        
        // Climb up to find common ancestor
        while (m && d && depth < 20) {
          if (m === d) {
            commonAncestor = m;
            break;
          }
          m = m.parentElement;
          d = d.parentElement;
          depth++;
        }
        
        if (commonAncestor && depth < 20) {
          // They're reasonably close in the tree, this is likely the right expander
          console.log("Found expander (shared ancestor at depth", depth, ") for uid:", uid);
          return details;
        }
        
        // If depth is reasonable or we're at the first one, use it
        // (sometimes the marker and expander are in different containers but still related)
        if (depth < 25) {
          console.log("Found expander (after marker, depth", depth, ") for uid:", uid);
          return details;
        }
      }
    }
    
    // Fallback: If no expander found after marker, try finding the first expander
    // that's visible in the current tab context
    if (allDetails.length > 0) {
      console.log("Using fallback: first visible expander");
      return allDetails[0];
    }
    
    console.error("Could not find expander for uid:", uid);
    return null;
  }

  function openExpander(details) {
    if (!details) {
      console.warn("openExpander: details is null");
      return false;
    }
    
    console.log("Opening expander, currently open:", details.open);
    
    if (details.open) {
      console.log("Expander already open");
      return true;
    }

    // Try multiple methods to open
    const summary = details.querySelector("summary");
    
    if (summary) {
      console.log("Found summary element, attempting to open...");
      
      // Method 1: Direct click on summary
      try {
        summary.click();
        console.log("Clicked summary");
        
        // Check if it opened after a brief delay
        setTimeout(() => {
          if (!details.open) {
            console.log("Click didn't open, trying attribute...");
            details.open = true;
            
            // Also try a mouse event
            const clickEvent = new MouseEvent('click', {
              bubbles: true,
              cancelable: true,
              view: window
            });
            summary.dispatchEvent(clickEvent);
          } else {
            console.log("✓ Expander opened successfully via click!");
          }
        }, 50);
        
        return true;
      } catch (e) {
        console.error("Error clicking summary:", e);
      }
    }
    
    // Method 2: Set open attribute directly
    console.log("Setting open attribute directly");
    details.open = true;
    
    // Method 3: Dispatch toggle event
    try {
      const toggleEvent = new Event('toggle', { bubbles: true });
      details.dispatchEvent(toggleEvent);
      console.log("Dispatched toggle event");
    } catch (e) {
      console.error("Error dispatching toggle:", e);
    }
    
    return true;
  }

  function flash(uid) {
    const inner = doc.getElementById("inner_" + uid);
    if (!inner) {
      console.warn("Flash target not found for uid:", uid);
      return;
    }
    inner.classList.add("flash-target");
    setTimeout(() => inner.classList.remove("flash-target"), 1200);
  }

  async function openAndScroll(jumpId, tabName) {
    console.log("=== openAndScroll: jumpId=", jumpId, "tab=", tabName, "===");
    
    // Step 1: Switch tab if needed
    if (tabName) {
      await switchToTab(tabName);
      // Wait a bit longer for tab content to fully render
      await new Promise(resolve => setTimeout(resolve, 300));
    }
    
    // Step 2: Find anchor (for scrolling)
    const anchor = doc.getElementById("calc_" + jumpId);
    if (!anchor) {
      console.error("Anchor not found for jumpId:", jumpId);
      return;
    }
    console.log("Found anchor:", anchor);
    
    // Step 3: Find expander (with retries)
    let details = null;
    for (let attempt = 0; attempt < 5; attempt++) {
      details = findExpanderForUid(jumpId);
      if (details) {
        console.log("✓ Found expander on attempt", attempt + 1);
        break;
      }
      console.log("Retry finding expander, attempt", attempt + 1);
      await new Promise(resolve => setTimeout(resolve, 200));
    }
    
    // Step 4: Open expander
    if (details) {
      console.log("Attempting to open expander...");
      const opened = openExpander(details);
      
      // Wait for expander animation
      await new Promise(resolve => setTimeout(resolve, 300));
      
      if (details.open) {
        console.log("✓ Expander is now open!");
      } else {
        console.warn("⚠ Expander still not open after attempts");
      }
    } else {
      console.error("✗ Could not find expander for uid:", uid);
    }
    
    // Step 5: Scroll (this part works)
    console.log("Scrolling to anchor...");
    scrollToAnchor(anchor);
    
    // Step 6: Flash after delay
    setTimeout(() => {
      flash(jumpId);
    }, 400);
  }

  function bind() {
    const links = doc.querySelectorAll(".row-link[data-uid]");
    console.log("=== Binding", links.length, "row links ===");
    
    links.forEach((a, index) => {
      if (a.dataset.bound === "1") {
        return;
      }
      a.dataset.bound = "1";
      const uid = a.dataset.uid;
      const jumpId = (a.dataset.jumpTarget || "").trim() || uid;
      const tab = a.dataset.tab || "";
      console.log(`Binding link ${index}: uid=${uid}, jumpId=${jumpId}, tab=${tab}`);

      a.addEventListener("click", async (e) => {
        e.preventDefault();
        e.stopPropagation();
        const clickedUid = a.dataset.uid;
        const clickedJump = (a.dataset.jumpTarget || "").trim() || clickedUid;
        const clickedTab = a.dataset.tab || "";
        
        if (!clickedUid) {
          console.warn("No uid found for row link");
          return;
        }
        
        console.log("=== Row clicked: uid=", clickedUid, "jumpId=", clickedJump, "tab=", clickedTab, "===");
        await openAndScroll(clickedJump, clickedTab);
      });
    });
  }

  // Bind immediately and retry (Streamlit can re-render)
  console.log("=== Initial bind attempt ===");
  bind();
  setTimeout(() => {
    console.log("=== Retry bind (300ms) ===");
    bind();
  }, 300);
  setTimeout(() => {
    console.log("=== Retry bind (1000ms) ===");
    bind();
  }, 1000);
  setTimeout(() => {
    console.log("=== Retry bind (2000ms) ===");
    bind();
  }, 2000);
})();
</script>
""",
        height=0,
    )


def step_card(uid: str, title: str, summary: str = "", status: str | None = None):
    """
    Deterministic expandable step:
    - always uses st.session_state[f"step_open_{uid}"] as the single source of truth
    - can be forced open by code (summary click)
    """
    # Anchor for scrolling
    st.markdown(f"<div id='calc_{uid}'></div>", unsafe_allow_html=True)

    open_key = f"step_open_{uid}"
    is_open = bool(st.session_state.get(open_key, False))

    # Header row as a button (toggle)
    header = title if not summary else f"{title} — {summary}"

    def _toggle():
        st.session_state[open_key] = not bool(st.session_state.get(open_key, False))

    # Make it look like a row
    st.button(header, key=f"step_btn_{uid}", on_click=_toggle)

    # Body container
    body = st.container()
    if is_open:
        return body  # caller writes into this container
    return None
