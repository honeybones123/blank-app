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
        self.fragment_calls = []
        self.rerun_calls = []

    def markdown(self, *_args, **_kwargs):
        return None

    def fragment(self, func):
        self.fragment_calls.append(func.__name__)
        return func

    def button(self, *_args, **_kwargs):
        return False

    def rerun(self, **kwargs):
        self.rerun_calls.append(kwargs)

    def columns(self, _spec, **_kwargs):
        return (nullcontext(), nullcontext())

    def container(self, **kwargs):
        self.container_calls.append(kwargs)
        return nullcontext()

    def expander(self, label, **kwargs):
        class _FakeExpander:
            def __init__(self, open_state):
                self.open = open_state

            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

        self.expander_calls.append((label, kwargs))
        return _FakeExpander(len(self.expander_calls) == 1)


def test_mounted_renderer_uses_only_visual_shell_state_and_mounts_all_card_bodies():
    rendered = []
    fake = _FakeStreamlit()
    config = CheckInputPanelConfig(
        page_slug="creep",
        mount_closed_bodies=True,
        categories=(
            CheckInputCategory("geometry", "Geometry", "250 × 450 mm", lambda: rendered.append("geometry")),
            CheckInputCategory("time", "Time", "365 days", lambda: rendered.append("time")),
        ),
    )

    render_compact_check_inputs(fake, config)

    assert fake.session_state.writes == 2
    assert set(fake.session_state) == {
        "compact_check_inputs_creep_geometry__open",
        "compact_check_inputs_creep_time__open",
    }
    assert rendered == ["geometry", "time"]
    assert fake.expander_calls == []
    assert fake.fragment_calls == ["_header_fragment", "_header_fragment"]
    assert fake.rerun_calls == []
    assert fake.container_calls == [
        {"border": False, "key": "compact_check_inputs_creep"},
        {"key": "compact_check_inputs_creep_geometry__shell", "border": False},
        {"key": "compact_check_inputs_creep_geometry__body", "border": False},
        {"key": "compact_check_inputs_creep_time__shell", "border": False},
        {"key": "compact_check_inputs_creep_time__body", "border": False},
    ]


def test_heavy_panel_keeps_closed_bodies_lazy_and_fragment_scoped():
    rendered = []
    fake = _FakeStreamlit()
    config = CheckInputPanelConfig(
        page_slug="shear",
        categories=(
            CheckInputCategory("actions", "Actions", "100 kN", lambda: rendered.append("actions")),
            CheckInputCategory("geometry", "Geometry", "300 mm", lambda: rendered.append("geometry")),
        ),
    )

    render_compact_check_inputs(fake, config)

    assert rendered == ["actions"]
    assert all(call[1]["on_change"] == "rerun" for call in fake.expander_calls)


def test_duplicate_category_ids_are_rejected():
    category = CheckInputCategory("same", "One", "", lambda: None)
    with pytest.raises(ValueError, match="category_id"):
        CheckInputPanelConfig(page_slug="creep", categories=(category, category))


def test_missing_summary_values_are_not_rendered_as_zero():
    assert format_number(None, "kN") == NOT_PROVIDED
    assert format_dimensions(None, 450) == NOT_PROVIDED
    assert format_number(0, "kN") == "0 kN"
    assert format_dimensions(250, 450) == "250 × 450 mm"
