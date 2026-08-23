"""Bending engineering-summary presentation and navigation contract."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Mapping, MutableMapping, Sequence

from engineering_check_ui import ENGINEERING_CHECK_COLUMNS, resolve_jump_target_id
from ui.summary_rows import build_bending_clickable_summary_rows
from ui_seamless_steps import render_clickable_summary_table


@dataclass(frozen=True, slots=True)
class BendingSummaryInteraction:
    """Presentation command produced by a clicked summary row."""

    clicked_uid: str | None
    target_uid: str | None = None
    target_mode: str | None = None
    moment_sign: str | None = None


@dataclass(frozen=True, slots=True)
class BendingSummaryResult:
    rows: tuple[Mapping[str, Any], ...]
    interaction: BendingSummaryInteraction


def _mode_for_target(target_uid: str) -> str:
    if target_uid.startswith("bending_sls_"):
        return "SLS"
    if target_uid.startswith("bending_min_"):
        return "MIN"
    return "ULS"


def render_bending_summary(
    check_rows: Sequence[Mapping[str, Any]],
    *,
    publish_rows: Callable[[list[dict[str, Any]]], None],
) -> BendingSummaryResult:
    """Render the existing summary table from canonical check-pack rows."""

    rows = build_bending_clickable_summary_rows(check_rows)
    publish_rows(rows)
    clicked_uid = render_clickable_summary_table(
        rows,
        key_prefix="bend_summary",
        columns=ENGINEERING_CHECK_COLUMNS,
    )
    if not clicked_uid:
        return BendingSummaryResult(
            rows=tuple(rows),
            interaction=BendingSummaryInteraction(clicked_uid=None),
        )

    clicked_row = next(
        (row for row in rows if row.get("uid") == clicked_uid),
        None,
    )
    target_uid = (
        resolve_jump_target_id(clicked_row)
        if clicked_row
        else str(clicked_uid)
    )
    moment_sign = (clicked_row or {}).get("moment_sign")
    if moment_sign not in {"positive", "negative"}:
        moment_sign = None
    return BendingSummaryResult(
        rows=tuple(rows),
        interaction=BendingSummaryInteraction(
            clicked_uid=str(clicked_uid),
            target_uid=str(target_uid),
            target_mode=_mode_for_target(str(target_uid)),
            moment_sign=moment_sign,
        ),
    )


def apply_bending_summary_navigation(
    state: MutableMapping[str, Any],
    interaction: BendingSummaryInteraction,
    *,
    jump_tab_key: str,
) -> None:
    """Apply summary navigation to presentation state only."""

    if not interaction.clicked_uid or not interaction.target_uid:
        return

    target_mode = interaction.target_mode or "ULS"
    state["bending_active_mode"] = target_mode
    state[jump_tab_key] = {
        "ULS": "ULS Checks",
        "SLS": "SLS Checks",
        "MIN": "Minimum strength checks",
    }.get(target_mode, "ULS Checks")
    state["bending_check_tab"] = state[jump_tab_key]
    if interaction.moment_sign in {"positive", "negative"}:
        state["bending_detail_view"] = interaction.moment_sign
    state[f"step_open_{interaction.target_uid}"] = True
    state["bending_pending_scroll_uid"] = interaction.target_uid


__all__ = [
    "BendingSummaryInteraction",
    "BendingSummaryResult",
    "apply_bending_summary_navigation",
    "render_bending_summary",
]
