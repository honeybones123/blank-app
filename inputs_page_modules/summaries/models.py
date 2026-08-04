from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class InputsSummaryCardSource:
    family: str
    title: str
    capacity: str
    action: str
    utilisation: str
    status: str
    rows: tuple[dict[str, Any], ...]
    capacity_label: str
    action_label: str
    status_note_html: str = ""
    columns: tuple[str, ...] = ()


@dataclass(frozen=True)
class InputsSummarySourceSnapshot:
    scenario_id: str
    scenario_label: str
    bending: InputsSummaryCardSource
    shear: InputsSummaryCardSource
    crack: InputsSummaryCardSource
    deflection: InputsSummaryCardSource
    geometry: dict[str, Any]
    actions: dict[str, Any]
    run_state: dict[str, Any]


@dataclass(frozen=True)
class SummaryCardViewModel:
    check_id: str
    title: str
    applied_label: str
    applied_value: str
    capacity_label: str
    capacity_value: str
    utilisation: str
    status: str
    tone: str
    expanded_rows: tuple[dict[str, Any], ...]
    visible_text: tuple[str, ...]
    html_hash: str
    display_hash: str


@dataclass(frozen=True)
class InputsSummarySectionViewModel:
    scenario_id: str
    cards: tuple[SummaryCardViewModel, ...]
    display_hash: str
