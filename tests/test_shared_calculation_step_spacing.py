from __future__ import annotations

import widgets_helpers


class _MarkdownCapture:
    def __init__(self) -> None:
        self.values: list[str] = []
        self.session_state: dict[str, object] = {"_rendered_style_keys": set()}

    def markdown(self, value: str, **_kwargs) -> None:
        self.values.append(value)


def test_shared_calculation_stacks_use_one_compact_gap_contract(monkeypatch) -> None:
    capture = _MarkdownCapture()
    monkeypatch.setattr(widgets_helpers, "st", capture)

    widgets_helpers.apply_step_summary_expander_css()

    css = "\n".join(capture.values)
    assert "[data-calc-uid]" in css
    assert "gap: 0 !important" in css
    assert "margin-bottom: 0 !important" in css
    assert "margin-top: 0 !important" in css
    assert "min-height: 42px !important" in css
    assert "font-size: 14px !important" in css


def test_shared_calculation_step_css_is_emitted_once_per_render_cycle(monkeypatch) -> None:
    capture = _MarkdownCapture()
    monkeypatch.setattr(widgets_helpers, "st", capture)

    widgets_helpers.apply_step_summary_expander_css()
    widgets_helpers.apply_step_summary_expander_css()
    assert len(capture.values) == 1

    capture.session_state["_rendered_style_keys"] = set()
    widgets_helpers.apply_step_summary_expander_css()
    assert len(capture.values) == 2
