from __future__ import annotations

from pathlib import Path

import pytest

import engineering_page_sections.shear_summary as shear_summary
from engineering_page_sections.shear_page_context import (
    build_shear_page_snapshot,
)


ROOT = Path(__file__).resolve().parents[1]


def _snapshot():
    return build_shear_page_snapshot(
        engineering_state={},
        check_pack={
            "rows": ({"uid": "shear", "label": "Shear"},),
            "summary_phiVu_kN": 180.0,
            "summary_util": 0.75,
        },
        published_results={},
        section_layout=None,
        actions_mode="manual",
    )


def test_summary_preserves_publish_render_bind_explainer_order(monkeypatch) -> None:
    events: list[tuple[str, object]] = []
    legacy_rows = [{"uid": "legacy"}]
    clickable_rows = [{"uid": "clickable"}]
    display_rows = [{"uid": "display"}]

    monkeypatch.setattr(
        shear_summary,
        "build_shear_legacy_summary_rows",
        lambda rows: events.append(("legacy", tuple(rows))) or legacy_rows,
    )
    monkeypatch.setattr(
        shear_summary,
        "build_shear_clickable_summary_rows",
        lambda rows: (
            events.append(("clickable", tuple(row["uid"] for row in rows)))
            or clickable_rows
        ),
    )
    monkeypatch.setattr(
        shear_summary,
        "filter_shear_summary_rows",
        lambda rows: events.append(("filter", None)) or display_rows,
    )
    monkeypatch.setattr(
        shear_summary,
        "render_clickable_summary_table",
        lambda rows, *, key_prefix: events.append(("render", key_prefix)),
    )

    result = shear_summary.render_shear_summary(
        _snapshot(),
        publish_summary=lambda capacity, utilisation: events.append(
            ("publish_summary", (capacity, utilisation))
        ),
        publish_rows=lambda rows: events.append(("publish_rows", tuple(rows))),
        bind_clicks=lambda: events.append(("bind", None)),
        render_explainer_expander=lambda renderer: (
            events.append(("expander", None)), renderer()
        ),
        render_explainer=lambda: events.append(("explainer", None)),
    )

    assert events == [
        ("legacy", ({"uid": "shear", "label": "Shear"},)),
        ("publish_summary", (180.0, 0.75)),
        ("clickable", ("legacy",)),
        ("publish_rows", ({"uid": "clickable"},)),
        ("filter", None),
        ("clickable", ("display",)),
        ("render", "shear_summary"),
        ("bind", None),
        ("expander", None),
        ("explainer", None),
    ]
    assert result.summary_utilisation == pytest.approx(0.75)


def test_invalid_summary_utilisation_publishes_safe_zero() -> None:
    published: list[tuple[float, float]] = []
    snapshot = build_shear_page_snapshot(
        engineering_state={},
        check_pack={"rows": (), "summary_phiVu_kN": 0.0, "summary_util": "bad"},
        published_results={},
        section_layout=None,
        actions_mode="manual",
    )

    result = shear_summary.render_shear_summary(
        snapshot,
        publish_summary=lambda capacity, utilisation: published.append(
            (capacity, utilisation)
        ),
        publish_rows=lambda _rows: None,
        bind_clicks=lambda: None,
        render_explainer_expander=lambda renderer: renderer(),
        render_explainer=lambda: None,
    )

    assert published == [(0.0, 0.0)]
    assert result.summary_utilisation != result.summary_utilisation


def test_runtime_delegates_summary_and_explainer_ownership() -> None:
    runtime = (ROOT / "shear_page_runtime.py").read_text(encoding="utf-8")

    assert "render_shear_summary(" in runtime
    assert "render_shear_explainer(" in runtime
    assert "build_shear_legacy_summary_rows(" not in runtime
    assert "render_clickable_summary_table(" not in runtime
