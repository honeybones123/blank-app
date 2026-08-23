from __future__ import annotations

from pathlib import Path

import plotly.graph_objects as go

from engineering_page_sections import shear_visualisation


ROOT = Path(__file__).resolve().parents[1]


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

