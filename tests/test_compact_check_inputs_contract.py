from __future__ import annotations

from contextlib import nullcontext

import pytest

from engineering_page_sections.compact_check_inputs import (
    CheckInputCategory,
    CheckInputPanelConfig,
    NOT_PROVIDED,
    format_dimensions,
    format_number,
    render_compact_check_inputs,
)


class _State(dict):
    writes = 0

    def __setitem__(self, key, value):
        self.writes += 1
        super().__setitem__(key, value)


class _FakeStreamlit:
    def __init__(self):
        self.session_state = _State()
        self.query_params = {"page": "creep", "cid": "beam-1"}
        self.expander_calls = []
        self.container_calls = []

    def markdown(self, *_args, **_kwargs):
        return None

    def columns(self, _spec, **_kwargs):
        return (nullcontext(), nullcontext())

    def container(self, **kwargs):
        self.container_calls.append(kwargs)
        return nullcontext()

    def expander(self, label, **kwargs):
        self.expander_calls.append((label, kwargs))
        return nullcontext()


def test_renderer_adds_no_component_session_state_and_mounts_every_body():
    rendered = []
    fake = _FakeStreamlit()
    config = CheckInputPanelConfig(
        page_slug="creep",
        categories=(
            CheckInputCategory("geometry", "Geometry", "250 × 450 mm", lambda: rendered.append("geometry")),
            CheckInputCategory("time", "Time", "365 days", lambda: rendered.append("time")),
        ),
    )

    render_compact_check_inputs(fake, config)

    assert fake.session_state.writes == 0
    assert rendered == ["geometry", "time"]
    assert [call[1]["key"] for call in fake.expander_calls] == [
        "compact_check_inputs_creep_geometry",
        "compact_check_inputs_creep_time",
    ]
    assert all(call[1]["on_change"] == "ignore" for call in fake.expander_calls)
    assert fake.container_calls == [
        {"border": False, "key": "compact_check_inputs_creep"}
    ]


def test_duplicate_category_ids_are_rejected():
    category = CheckInputCategory("same", "One", "", lambda: None)
    with pytest.raises(ValueError, match="category_id"):
        CheckInputPanelConfig(page_slug="creep", categories=(category, category))


def test_missing_summary_values_are_not_rendered_as_zero():
    assert format_number(None, "kN") == NOT_PROVIDED
    assert format_dimensions(None, 450) == NOT_PROVIDED
    assert format_number(0, "kN") == "0 kN"
    assert format_dimensions(250, 450) == "250 × 450 mm"
