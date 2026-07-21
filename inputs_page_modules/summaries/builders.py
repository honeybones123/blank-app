from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from typing import Any

from ui.summary_sections import (
    build_final_summary_check_card_html,
    build_final_summary_check_card_model,
)

from .contracts import CARD_ORDER
from .models import (
    InputsSummaryCardSource,
    InputsSummarySectionViewModel,
    InputsSummarySourceSnapshot,
    SummaryCardViewModel,
)


def stable_summary_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def stable_summary_hash(value: Any) -> str:
    return hashlib.sha256(stable_summary_json(value).encode("utf-8")).hexdigest()


def summary_tone_for_status(status: str) -> str:
    text = str(status or "").strip().upper()
    if text in {"PASS", "OK"}:
        return "pass"
    if text in {"FAIL", "NG"}:
        return "fail"
    if text in {"WARN", "WARNING", "NEAR LIMIT", "CHECK"}:
        return "warn"
    if text == "CAPACITY":
        return "capacity"
    if text in {"REQUIRES ACTION", "ACTION REQUIRED"}:
        return "requires-action"
    if text in {"NOT RUN", "INPUT REQUIRED"}:
        return "neutral"
    if text == "INFO":
        return "info"
    return "neutral"


def visible_text_from_summary_model(model: dict[str, Any]) -> tuple[str, ...]:
    text: list[str] = [
        str(model.get("title") or ""),
        str(model.get("action_label") or ""),
        str(model.get("action") or ""),
        str(model.get("capacity_label") or ""),
        str(model.get("capacity") or ""),
        "Utilisation",
        str(model.get("utilisation") or ""),
        str(model.get("status") or ""),
        str(model.get("threshold_text") or ""),
    ]
    for row in model.get("rows") or []:
        if not isinstance(row, dict):
            continue
        for key in (
            "title",
            "check",
            "action",
            "capacity",
            "calculated",
            "requirement",
            "value",
            "limit",
            "util",
            "status",
        ):
            if key in row:
                text.append(str(row.get(key) or ""))
    return tuple(part for part in text if part)


def card_source_to_summary_kwargs(card: InputsSummaryCardSource) -> dict[str, Any]:
    kwargs: dict[str, Any] = {
        "title": card.title,
        "description": "",
        "family": card.family,
        "capacity": card.capacity,
        "action": card.action,
        "utilisation": card.utilisation,
        "status": card.status,
        "rows": [dict(row) for row in card.rows],
        "open_by_default": False,
        "route_links": True,
        "threshold_text": "",
        "capacity_label": card.capacity_label,
        "action_label": card.action_label,
        "status_note_html": card.status_note_html,
    }
    if card.columns:
        kwargs["columns"] = list(card.columns)
    return kwargs


def build_summary_card_view_model(card: InputsSummaryCardSource) -> SummaryCardViewModel:
    kwargs = card_source_to_summary_kwargs(card)
    model = build_final_summary_check_card_model(**kwargs)
    html = build_final_summary_check_card_html(**kwargs)
    payload = {
        "check_id": card.family,
        "title": model["title"],
        "applied_label": model["action_label"],
        "applied_value": model["action"],
        "capacity_label": model["capacity_label"],
        "capacity_value": model["capacity"],
        "utilisation": model["utilisation"],
        "status": model["status"],
        "tone": summary_tone_for_status(model["status"]),
        "expanded_rows": tuple(dict(row) for row in model["rows"]),
        "visible_text": visible_text_from_summary_model(model),
        "html_hash": stable_summary_hash(html),
    }
    return SummaryCardViewModel(display_hash=stable_summary_hash(payload), **payload)


def build_inputs_summary_view_model(
    source: InputsSummarySourceSnapshot,
) -> InputsSummarySectionViewModel:
    cards = tuple(
        build_summary_card_view_model(getattr(source, family))
        for family in CARD_ORDER
    )
    return InputsSummarySectionViewModel(
        scenario_id=source.scenario_id,
        cards=cards,
        display_hash=stable_summary_hash([asdict(card) for card in cards]),
    )


def build_inputs_summary_html(
    source: InputsSummarySourceSnapshot,
    *,
    shear_detail_note_html: str = "",
) -> str:
    """Build summary card HTML from the extracted source snapshot.

    This deliberately reuses the existing shared summary renderer. It does not
    recalculate engineering truth and does not own Streamlit rendering.
    """
    html_parts: list[str] = []
    for family in CARD_ORDER:
        card = getattr(source, family)
        html = build_final_summary_check_card_html(**card_source_to_summary_kwargs(card))
        if family == "shear" and shear_detail_note_html:
            html = html.replace(
                '<div class="summary-detail-title">Detailed checks</div>',
                f'<div class="summary-detail-title">Detailed checks</div>{shear_detail_note_html}',
            )
        html_parts.append(html)
    return "".join(html_parts)
