from __future__ import annotations

import ast
from pathlib import Path

from engineering_page_sections import bending_summary
from engineering_page_sections.bending_summary import (
    BendingSummaryInteraction,
    apply_bending_summary_navigation,
)


ROOT = Path(__file__).resolve().parents[1]


def test_summary_publishes_rows_before_rendering_table(monkeypatch) -> None:
    events: list[tuple[str, object]] = []
    row = {"uid": "bending_uls_1", "title": "Capacity"}
    monkeypatch.setattr(
        bending_summary,
        "build_bending_clickable_summary_rows",
        lambda _rows: [row],
    )
    monkeypatch.setattr(
        bending_summary,
        "render_clickable_summary_table",
        lambda rows, **_kwargs: events.append(("render", rows)) or None,
    )

    result = bending_summary.render_bending_summary(
        (row,),
        publish_rows=lambda rows: events.append(("publish", rows)),
    )

    assert [name for name, _ in events] == ["publish", "render"]
    assert result.rows == (row,)
    assert result.interaction.clicked_uid is None


def test_summary_click_returns_navigation_without_mutating_engineering() -> None:
    state: dict[str, object] = {"engineering_value": 42}
    interaction = BendingSummaryInteraction(
        clicked_uid="row-1",
        target_uid="bending_sls_2",
        target_mode="SLS",
        moment_sign="negative",
    )

    apply_bending_summary_navigation(
        state,
        interaction,
        jump_tab_key="jump_tab",
    )

    assert state["engineering_value"] == 42
    assert state["bending_active_mode"] == "SLS"
    assert state["jump_tab"] == "SLS Checks"
    assert state["bending_check_tab"] == "SLS Checks"
    assert state["bending_detail_view"] == "negative"
    assert state["step_open_bending_sls_2"] is True
    assert state["bending_pending_scroll_uid"] == "bending_sls_2"


def test_summary_resolves_clicked_row_target_and_sign(monkeypatch) -> None:
    source_row = {
        "uid": "summary-row",
        "calc_step_id": "bending_min_4",
        "moment_sign": "positive",
    }
    monkeypatch.setattr(
        bending_summary,
        "build_bending_clickable_summary_rows",
        lambda _rows: [source_row],
    )
    monkeypatch.setattr(
        bending_summary,
        "render_clickable_summary_table",
        lambda *_args, **_kwargs: "summary-row",
    )
    monkeypatch.setattr(
        bending_summary,
        "resolve_jump_target_id",
        lambda _row: "bending_min_4",
    )

    result = bending_summary.render_bending_summary(
        (source_row,), publish_rows=lambda _rows: None
    )

    assert result.interaction.target_uid == "bending_min_4"
    assert result.interaction.target_mode == "MIN"
    assert result.interaction.moment_sign == "positive"


def test_summary_module_has_no_solver_or_global_session_dependency() -> None:
    source = (
        ROOT / "engineering_page_sections" / "bending_summary.py"
    ).read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported_roots = {
        alias.name.split(".", 1)[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    imported_roots.update(
        str(node.module or "").split(".", 1)[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
    )

    assert "streamlit" not in imported_roots
    assert "bending_core" not in imported_roots
    assert "calculations" not in imported_roots
    assert "st.session_state" not in source


def test_runtime_delegates_summary_rendering_and_navigation() -> None:
    source = (ROOT / "bending_page_runtime.py").read_text(encoding="utf-8")

    assert "summary_result = render_bending_summary(" in source
    assert "apply_bending_summary_navigation(" in source
    assert "build_bending_clickable_summary_rows(" not in source
