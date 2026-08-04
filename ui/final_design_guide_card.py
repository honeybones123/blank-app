"""Pure HTML renderer for clean FinalDesignGuidePublication card formats."""

from __future__ import annotations

import hashlib
import html
import re
from typing import Any

from design_brain.design_guide_card_attrs import FINAL_DESIGN_GUIDE_CARD_DATA_ATTRIBUTE_FIELDS
from design_brain.final_design_guide_formatter import FinalDesignGuideCardFormat


def _escape(value: Any) -> str:
    return html.escape(str(value or ""))


def render_final_design_guide_text_html(text: Any) -> str:
    """Render plain Design Guide copy as safe inline HTML.

    This is a UI text renderer only. It does not read session state, legacy
    guidance item dictionaries, apply routing, or publication truth.
    """
    raw = str(text or "").strip()
    if not raw:
        return ""
    html_lines: list[str] = []
    for line in raw.splitlines():
        stripped = line.strip()
        if not stripped:
            html_lines.append("")
        elif stripped.startswith("- "):
            html_lines.append("&bull; " + html.escape(stripped[2:]))
        else:
            html_lines.append(html.escape(line))
    return "<br>".join(html_lines)


def render_final_design_guide_data_attributes_html(data_attributes: dict) -> str:
    """Render already-resolved Design Guide card data attributes."""
    attrs = dict(data_attributes or {})
    return " ".join(
        f"{html_name}='{_escape(attrs.get(key))}'"
        for html_name, key in FINAL_DESIGN_GUIDE_CARD_DATA_ATTRIBUTE_FIELDS
    )


def _section_rows_html(rows: tuple[dict[str, Any], ...] | list[dict[str, Any]]) -> str:
    parts: list[str] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        label = _escape(row.get("label") or row.get("family") or row.get("title") or "")
        text = _escape(row.get("text") or row.get("value") or "")
        before = _escape(row.get("before") or "")
        after = _escape(row.get("after") or "")
        if before or after:
            text = f"{before} &rarr; {after}"
        if not label and not text:
            label = "Evidence"
            text = _escape(row)
        parts.append(
            "<div class='fdg-row'>"
            f"<span class='fdg-row-label'>{label}</span>"
            f"<span class='fdg-row-text'>{text}</span>"
            "</div>"
        )
    return "".join(parts)


def _status_for_outcome(outcome_state: str) -> str:
    value = str(outcome_state or "PROOF_PENDING").strip().upper()
    if value == "PASS":
        return "pass"
    if value == "ACTION":
        return "action"
    if value == "BLOCKED":
        return "blocked"
    if value == "ERROR":
        return "error"
    return "info"


def _legacy_tone_classes(tone: str) -> str:
    value = str(tone or "grey").strip().lower()
    if value == "green":
        return "pass guidance-success"
    if value == "red":
        return "fail"
    if value == "blue":
        return "efficiency"
    if value == "amber":
        return "warn"
    return "info"


def final_design_guide_action_anchor_bucket(
    model: FinalDesignGuideCardFormat,
    *,
    fallback: str = "pass",
) -> str:
    """Return the legacy CTA anchor bucket from canonical card tone."""

    if not isinstance(model, FinalDesignGuideCardFormat):
        raise TypeError("model must be a FinalDesignGuideCardFormat")
    return {
        "red": "fail",
        "amber": "warn",
        "green": "pass",
        "blue": "efficiency",
        "grey": "start",
    }.get(str(model.tone or "").strip().lower(), str(fallback or "pass"))


def _current_rows_html(section_rows: tuple[dict[str, Any], ...] | list[dict[str, Any]]) -> str:
    marker_by_tone = {"green": "&check;", "amber": "&bull;", "red": "!", "grey": "i", "blue": "i"}
    parts: list[str] = []
    for row in section_rows:
        if not isinstance(row, dict):
            continue
        family = str(row.get("family") or row.get("label") or "").strip().lower()
        label = _escape(row.get("label") or row.get("family") or "")
        value = _escape(row.get("value") or "-")
        row_status = _escape(str(row.get("status") or "-").upper())
        tone = str(row.get("tone") or "grey").strip().lower()
        parts.append(
            f"<div class='dg-current-chip dg-current-chip--{_escape(tone)}' "
            f"data-testid='design-guide-current-{_escape(family)}'>"
            f"<span class='dg-current-marker'>{marker_by_tone.get(tone, 'i')}</span>"
            f"<span><div class='dg-current-main'>{label} {value}</div>"
            f"<div class='dg-current-status'>{row_status}</div></span>"
            "</div>"
        )
    return "".join(parts)


def _preview_rows_html(section_rows: tuple[dict[str, Any], ...] | list[dict[str, Any]]) -> str:
    parts: list[str] = []
    for row in section_rows:
        if not isinstance(row, dict):
            continue
        parts.append(
            f"<div class='dg-preview-row' data-testid='design-guide-preview-{_escape(row.get('family'))}'>"
            f"{_escape(row.get('label') or row.get('family') or '')}: "
            f"{_escape(row.get('before') or '')} &rarr; {_escape(row.get('after') or '')}"
            "</div>"
        )
    return "".join(parts)


def _reason_rows_html(section_rows: tuple[dict[str, Any], ...] | list[dict[str, Any]]) -> str:
    parts: list[str] = []
    for row in section_rows:
        if not isinstance(row, dict):
            continue
        label = _escape(row.get("label") or "Result")
        text = _escape(row.get("text") or row.get("value") or "")
        test_label = _escape(row.get("test_label") or str(row.get("label") or "result").lower().replace(" ", "-"))
        if not text:
            continue
        parts.append(
            f"<div class='dg-reason-row' data-testid='design-guide-reason-{test_label}'>"
            "<span class='dg-reason-icon'>i</span>"
            f"<span class='dg-reason-label'>{label}</span>"
            f"<span class='dg-reason-text'>{text}</span>"
            "</div>"
        )
    return "".join(parts)


def _section_by_title(model: FinalDesignGuideCardFormat, title: str) -> tuple[dict[str, Any], ...]:
    for section in model.sections:
        if section.visible and str(section.title or "").strip().lower() == title.strip().lower():
            return tuple(section.rows or ())
    return ()


def _readability_compare_text(value: Any) -> str:
    text = str(value or "").strip().lower()
    text = re.sub(r"\b(?:why|status)\s*:\s*", " ", text)
    text = re.sub(r"[^a-z0-9.]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _readability_token_overlap(left: str, right: str) -> float:
    left_tokens = {token for token in left.split() if len(token) > 2}
    right_tokens = {token for token in right.split() if len(token) > 2}
    if not left_tokens or not right_tokens:
        return 0.0
    return len(left_tokens & right_tokens) / max(1, min(len(left_tokens), len(right_tokens)))


def _status_rows_repeat_collapsed_card_text(
    model: FinalDesignGuideCardFormat,
    reason_rows: tuple[dict[str, Any], ...] | list[dict[str, Any]],
) -> bool:
    if not reason_rows:
        return False
    collapsed_title = _readability_compare_text(model.title)
    collapsed_reason = _readability_compare_text(
        " ".join(str(part or "") for part in (model.summary, model.blocker_explanation))
    )
    collapsed_text = _readability_compare_text(
        " ".join(
            str(part or "")
            for part in (
                model.title,
                model.summary,
                model.blocker_explanation,
            )
        )
    )
    if not collapsed_text:
        return False
    for row in reason_rows:
        if not isinstance(row, dict):
            return False
        row_label = _readability_compare_text(row.get("label") or row.get("family") or row.get("title"))
        row_value = _readability_compare_text(row.get("text") or row.get("value"))
        row_text = _readability_compare_text(
            " ".join(str(part or "") for part in (row.get("label"), row.get("text"), row.get("value")))
        )
        if not row_text:
            continue
        direct_match = row_text in collapsed_text or collapsed_text in row_text
        title_prefixed_match = bool(
            row_value
            and collapsed_reason
            and (row_value in collapsed_reason or collapsed_reason in row_value)
            and (
                not row_label
                or row_label in {"status", "result", "outcome", "reason"}
                or not collapsed_title
                or row_label in collapsed_title
                or collapsed_title in row_label
            )
        )
        value_has_title_prefix_match = bool(
            row_value
            and collapsed_title
            and collapsed_reason
            and row_value.startswith(collapsed_title)
            and (
                row_value.removeprefix(collapsed_title).strip() in collapsed_reason
                or collapsed_reason in row_value
            )
        )
        row_without_title = row_text
        if collapsed_title and row_without_title.startswith(collapsed_title):
            row_without_title = row_without_title.removeprefix(collapsed_title).strip()
        high_overlap_match = bool(
            row_without_title
            and collapsed_reason
            and _readability_token_overlap(row_without_title, collapsed_reason) >= 0.82
        )
        if not (direct_match or title_prefixed_match or value_has_title_prefix_match or high_overlap_match):
            return False
    return True


def render_final_design_guide_card_html(model: FinalDesignGuideCardFormat) -> str:
    """Render the clean final publication card format.

    This function renders HTML only. It does not read session state, route CTA
    payloads, call Streamlit, or decide engineering/publication truth.
    """

    if not isinstance(model, FinalDesignGuideCardFormat):
        raise TypeError("model must be a FinalDesignGuideCardFormat")

    tone = str(model.tone or "grey").strip().lower()
    status = _status_for_outcome(model.outcome_state)
    cta = dict(model.cta or {})
    current_rows = _section_by_title(model, "Current")
    preview_rows = _section_by_title(model, "Preview after proposed change")
    reason_rows = _section_by_title(model, "Status")
    cleanup_reason_rows = _section_by_title(model, "Why no further cleanup?")
    main_reason_rows = cleanup_reason_rows or reason_rows
    main_reason_title = (
        "Why no further cleanup?"
        if cleanup_reason_rows or status == "pass"
        else "Status"
    )
    show_status_section = bool(main_reason_rows) and (
        bool(cleanup_reason_rows)
        or not _status_rows_repeat_collapsed_card_text(model, main_reason_rows)
    )
    other_sections = [
        section
        for section in model.sections
        if section.visible
        and str(section.title or "").strip()
        not in {
            "Current",
            "Preview after proposed change",
            "Status",
            "Why no further cleanup?",
        }
    ]
    other_section_html = []
    for section in other_sections:
        other_section_html.append(
            f"<div class='dg-section-title'>{_escape(section.title)}</div>"
            f"<div class='fdg-section-rows' data-testid='design-guide-format-section'>"
            f"{_section_rows_html(section.rows)}</div>"
        )
    toggle_id = "fdg-toggle-" + hashlib.sha1(
        f"{status}|{model.badge}|{model.title}|{model.governing_label}|{model.summary}".encode(
            "utf-8", errors="ignore"
        )
    ).hexdigest()[:12]
    card_classes = (
        f"fdg-card fast-guidance-item {_legacy_tone_classes(tone)} "
        f"dg-card dg-card--{_escape(status)}"
    )
    current_section = (
        "<div class='dg-current-title'>Current</div>"
        f"<div class='dg-current-grid' data-testid='design-guide-current-row'>{_current_rows_html(current_rows)}</div>"
        if current_rows
        else ""
    )
    preview_section = (
        "<div class='dg-section-title'>Preview after proposed change</div>"
        f"<div class='dg-preview-grid' data-testid='design-guide-preview-row'>{_preview_rows_html(preview_rows)}</div>"
        if preview_rows
        else ""
    )
    cta_attrs = (
        f"data-cta-enabled='{_escape(bool(cta.get('enabled')))}' "
        f"data-cta-label='{_escape(cta.get('label'))}' "
        f"data-cta-disabled-reason='{_escape(cta.get('disabled_reason'))}' "
        f"data-action-type='{_escape(cta.get('action_type'))}' "
        f"data-apply-payload-fingerprint='{_escape(cta.get('apply_payload_fingerprint'))}'"
    )
    data_attrs = render_final_design_guide_data_attributes_html(model.data_attributes)
    return "".join(
        [
            (
                f"<details class='{card_classes}' data-testid='design-guide-card' "
                f"id='{_escape(toggle_id)}' "
                f"data-publication-hash='{_escape(model.publication_hash)}' "
                f"data-display-hash='{_escape(model.display_hash)}' "
                f"data-cta-hash='{_escape(model.cta_hash)}' "
                f"data-evidence-hash='{_escape(model.evidence_hash)}' "
                f"data-format-hash='{_escape(model.format_hash)}' "
                f"{cta_attrs} {data_attrs}>"
            ),
            "<summary class='dg-header' data-testid='design-guide-collapsible-header'>",
            "<span class='dg-header-top'>",
            "<span class='dg-header-left'>",
            (
                f"<span class='dg-status-pill dg-status-pill--{_escape(status)}' "
                f"data-testid='design-guide-status-pill'>{_escape(model.badge)}</span>"
            ),
            f"<span class='dg-title' data-testid='design-guide-title'>{_escape(model.title)}</span>",
            "</span>",
            "<span class='dg-header-right'>",
            (
                f"<span class='dg-util-pill' data-testid='design-guide-governing-utilisation'>"
                f"{_escape(model.governing_label)}</span>"
            ),
            "<span class='dg-expand-toggle' data-testid='design-guide-expand-toggle' aria-hidden='true'>&rsaquo;</span>",
            "</span>",
            "</span>",
            (
                f"<div class='dg-summary-line' data-testid='design-guide-collapsed-summary'>"
                f"{_escape(model.summary)}</div>"
                if model.summary
                else ""
            ),
            "</summary>",
            "<div class='dg-expanded-body' data-testid='design-guide-expanded-body'>",
            current_section,
            preview_section,
            (
                f"<div class='dg-section-title'>{_escape(main_reason_title)}</div>"
                f"<div class='dg-reason-list' data-testid='design-guide-main-explanation'>{_reason_rows_html(main_reason_rows)}</div>"
                if show_status_section
                else ""
            ),
            "".join(other_section_html),
            "</div>",
            "</details>",
        ]
    )


__all__ = [
    "final_design_guide_action_anchor_bucket",
    "render_final_design_guide_card_html",
    "render_final_design_guide_data_attributes_html",
    "render_final_design_guide_text_html",
]
