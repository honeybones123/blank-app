from __future__ import annotations

import widgets_helpers


class _MarkdownCapture:
    def __init__(self) -> None:
        self.values: list[str] = []

    def markdown(self, value: str, **_kwargs) -> None:
        self.values.append(value)


def test_shared_calculation_stacks_use_one_compact_gap_contract(monkeypatch) -> None:
    capture = _MarkdownCapture()
    monkeypatch.setattr(widgets_helpers, "st", capture)

    widgets_helpers.apply_step_summary_expander_css()

    css = "\n".join(capture.values)
    assert "[data-calc-uid]" in css
    assert "gap: 0 !important" in css
    assert "margin-bottom: 2.3rem !important" in css
    assert "margin-top: 0 !important" in css

