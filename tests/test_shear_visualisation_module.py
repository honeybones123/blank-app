from __future__ import annotations

from pathlib import Path

import plotly.graph_objects as go

from engineering_page_sections import shear_visualisation


ROOT = Path(__file__).resolve().parents[1]


class _FakeContext:
    def __init__(self, events: list[tuple[str, object]], name: str):
        self.events = events
        self.name = name

    def __enter__(self):
        self.events.append(("enter", self.name))
        return self

    def __exit__(self, *_args):
        self.events.append(("exit", self.name))


class _FakeStreamlit:
    def __init__(self):
        self.events: list[tuple[str, object]] = []

    def container(self):
        self.events.append(("container", "visualisation"))
        return _FakeContext(self.events, "visualisation")

    def markdown(self, body, **kwargs):
        self.events.append(("markdown", "shear-visuals-block" in body))


def test_visualisation_module_has_no_runtime_global_binding() -> None:
    module_source = (
        ROOT / "engineering_page_sections" / "shear_visualisation.py"
    ).read_text(encoding="utf-8")
    runtime_source = (ROOT / "shear_page_runtime.py").read_text(encoding="utf-8")

    assert "def bind_runtime" not in module_source
    assert "globals().update" not in module_source
    assert "bind_runtime(" not in runtime_source
    assert "_shear_visualisation_section" not in runtime_source
    assert "render_centered_plotly=" in runtime_source
    assert "render_animated_plotly=" in runtime_source
    assert "def _render_shear_visualisation_block" not in runtime_source
    assert "def _render_shear_side_view" not in runtime_source
    assert "def _render_shear_cross_section" not in runtime_source
    assert "def _render_shear_force_diagram" not in runtime_source
    assert "def _resolve_shear_visual_supports" not in runtime_source
    assert "ShearVisualisationRuntime(" in runtime_source
    assert "build_cross_section_figure=build_shear_cross_section_figure" in runtime_source
    assert "build_side_view_figure=build_shear_side_view_figure" in runtime_source
    assert "build_sfd_bmd_figure=_build_shear_sfd_bmd_figure" in runtime_source
    assert "lambda: render_shear_visualisation_block(" in runtime_source


def test_visualisation_block_preserves_three_tab_render_order(monkeypatch) -> None:
    fake = _FakeStreamlit()

    def render_tabs(st_module, *, labels, scope_id):
        assert st_module is fake
        fake.events.append(("tabs", (labels, scope_id)))
        return tuple(_FakeContext(fake.events, label) for label in labels)

    monkeypatch.setattr(
        shear_visualisation,
        "_render_shear_side_view",
        lambda _runtime: fake.events.append(("render", "Side view")),
    )
    monkeypatch.setattr(
        shear_visualisation,
        "_render_shear_cross_section",
        lambda _runtime: fake.events.append(("render", "Section")),
    )
    monkeypatch.setattr(
        shear_visualisation,
        "_render_shear_force_diagram",
        lambda _runtime: fake.events.append(("render", "Shear diagram")),
    )

    runtime = shear_visualisation.ShearVisualisationRuntime(
        st=fake,
        get_param=lambda *_args, **_kwargs: None,
        render_timing_mark=lambda *_args, **_kwargs: None,
        render_plotly_diagram=lambda *_args, **_kwargs: None,
        render_centered_plotly=lambda *_args, **_kwargs: None,
        render_section_title=lambda title: fake.events.append(("title", title)),
        render_tabs=render_tabs,
        build_cross_section_figure=lambda **_kwargs: go.Figure(),
        build_side_view_figure=lambda **_kwargs: go.Figure(),
        build_sfd_bmd_figure=lambda **_kwargs: (go.Figure(), go.Figure()),
    )
    shear_visualisation.render_shear_visualisation_block(runtime)

    assert fake.events == [
        ("container", "visualisation"),
        ("enter", "visualisation"),
        ("markdown", True),
        ("title", "Visualisation"),
        (
            "tabs",
            (
                ("Side view", "Section", "Shear diagram"),
                "shear-visualisation-diagrams",
            ),
        ),
        ("enter", "Side view"),
        ("render", "Side view"),
        ("exit", "Side view"),
        ("enter", "Section"),
        ("render", "Section"),
        ("exit", "Section"),
        ("enter", "Shear diagram"),
        ("render", "Shear diagram"),
        ("exit", "Shear diagram"),
        ("exit", "visualisation"),
    ]


def test_static_mcft_renderer_receives_explicit_mount_dependency() -> None:
    events: list[dict[str, object]] = []
    figure = go.Figure()

    shear_visualisation._render_plotly_in_mcft_column(
        figure,
        chart_key="test-static",
        render_centered_plotly=lambda fig, **kwargs: events.append(
            {"figure": fig, **kwargs}
        ),
    )

    assert len(events) == 1
    assert events[0]["figure"] is figure
    assert events[0]["chart_key"] == "test-static"
    assert events[0]["height_px"] == shear_visualisation.SHEAR_VISUAL_HEIGHT_PX
    assert (
        events[0]["max_width_px"]
        == shear_visualisation.SHEAR_BEHAVIOUR_MAX_WIDTH_PX
    )


def test_behaviour_renderer_selects_exact_explicit_mount_dependency() -> None:
    events: list[tuple[str, dict[str, object]]] = []
    figure = go.Figure()
    figure.update_layout(height=301)

    def centered(_fig, **kwargs):
        events.append(("centered", kwargs))

    def animated(_fig, **kwargs):
        events.append(("animated", kwargs))

    shear_visualisation._render_mcft_behaviour_chart(
        figure,
        chart_key="animated-chart",
        animated=True,
        render_centered_plotly=centered,
        render_animated_plotly=animated,
    )
    shear_visualisation._render_mcft_behaviour_chart(
        figure,
        chart_key="static-chart",
        animated=False,
        render_centered_plotly=centered,
        render_animated_plotly=animated,
    )

    assert [event[0] for event in events] == ["animated", "centered"]
    assert events[0][1]["chart_key"] == "animated-chart"
    assert events[0][1]["height"] == 301
    assert events[1][1]["chart_key"] == "static-chart"
    assert events[1][1]["height_px"] == 301


def test_support_pair_adapter_remains_stable() -> None:
    adapter = shear_visualisation._support_pair_from_resolved_support_type

    assert adapter("Simply supported") == ("Pinned", "Roller")
    assert adapter("Fixed-ended") == ("Fixed", "Fixed")
    assert adapter("Fixed-Pinned") == ("Fixed", "Pinned")
    assert adapter("Pinned–Fixed") == ("Pinned", "Fixed")
    assert adapter("Continuous – interior span") == ("Pinned", "Pinned")
    assert adapter(None) is None
