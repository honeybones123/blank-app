"""Deflection summary-first presentation owner."""

from __future__ import annotations

from typing import Any, Callable

from engineering_check_ui import DEFLECTION_CHECK_SUMMARY_COLUMNS
from engineering_page_sections.deflection_page_context import DeflectionPageSnapshot
from ui_seamless_steps import bind_summary_clicks, render_clickable_summary_table
from widgets_helpers import render_page_explainer_expander


def render_deflection_explainer(st_module: Any) -> None:
    st_module.markdown(
        r"""
This page checks **reinforced concrete beam deflections** to AS 3600:2018:

- Short-term deflection
- Long-term deflection using **kₛₛ**
- Deemed-to-conform **span-to-depth ratio**
- **Simplified effective stiffness** \(I_{ef}\) for reinforced members
        """
    )


def render_deflection_summary(
    snapshot: DeflectionPageSnapshot,
    *,
    publish_results: Callable[[dict[str, Any]], None],
) -> None:
    rows = [dict(row) for row in snapshot.summary_rows]
    publish_results(
        {"rows": rows, "summary": dict(snapshot.summary_pack)}
    )
    render_clickable_summary_table(
        rows,
        key_prefix="defl_summary",
        columns=DEFLECTION_CHECK_SUMMARY_COLUMNS,
    )
    bind_summary_clicks()
    render_page_explainer_expander(render_deflection_explainer)


__all__ = ["render_deflection_explainer", "render_deflection_summary"]
