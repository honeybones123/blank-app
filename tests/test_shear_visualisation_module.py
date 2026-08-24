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
        self.session_state: dict[str, object] = {}

    def button(self, label, *, key):
        self.events.append(("button", (label, key)))
        return False

    def container(self, *, key=None):
        name = key or "visualisation"
        self.events.append(("container", name))
        return _FakeContext(self.events, name)

    def markdown(self, body, **kwargs):
        self.events.append(("markdown", "shear-visuals-block" in body))

    def caption(self, body):
        self.events.append(("caption", body))


def test_visualisation_module_has_no_runtime_global_binding() -> None:
    module_source = (
        ROOT / "engineering_page_sections" / "shear_visualisation.py"
    ).read_text(encoding="utf-8")
    mcft_source = (
        ROOT / "engineering_page_sections" / "shear_mcft_strength_checks.py"
    ).read_text(encoding="utf-8")
    runtime_source = (ROOT / "shear_page_runtime.py").read_text(encoding="utf-8")

    assert "def bind_runtime" not in module_source
    assert "globals().update" not in module_source
    assert "bind_runtime(" not in runtime_source
    assert "_shear_visualisation_section" not in runtime_source
    assert "render_centered_plotly=" in runtime_source
    assert "render_animated_plotly=" in runtime_source
    assert "synchronize_tabs=synchronize_stable_tab_scopes" in runtime_source
    assert "def _render_animated_plotly_figure" not in runtime_source
    assert "def _render_shear_visualisation_block" not in runtime_source
    assert "def _render_shear_side_view" not in runtime_source
    assert "def _render_shear_cross_section" not in runtime_source
    assert "def _render_shear_force_diagram" not in runtime_source
    assert "def _resolve_shear_visual_supports" not in runtime_source
    assert "ShearVisualisationRuntime(" in runtime_source
    assert "build_cross_section_figure=build_shear_cross_section_figure" in runtime_source
    assert "build_side_view_figure=build_shear_side_view_figure" in runtime_source
    assert "build_sfd_bmd_figure=plot_sfd_bmd_plotly" in runtime_source
    assert "Show detailed MCFT breakdown" not in mcft_source
    assert "_render_shear_diagram_bundle_panel = st.fragment(" in runtime_source
    assert "lambda: _render_shear_diagram_bundle_panel(" in runtime_source
    assert "_render_shear_mcft_panel = st.fragment(" in module_source


def test_mcft_display_toggles_rerun_only_the_visualisation_fragment() -> None:
    runtime_source = (ROOT / "shear_page_runtime.py").read_text(encoding="utf-8")
    visualisation_source = (
        ROOT / "engineering_page_sections" / "shear_visualisation.py"
    ).read_text(encoding="utf-8")
    stress_field_source = (
        ROOT / "engineering_page_sections" / "shear_stress_field.py"
    ).read_text(encoding="utf-8")

    assert runtime_source.count("render_shear_visualisation_block(") == 1
    assert "_render_shear_mcft_panel = st.fragment(" in visualisation_source
    assert "_render_shear_mcft_panel(runtime, fingerprint)" in visualisation_source
    assert "option_key = _mcft_option_key(options)" in visualisation_source
    assert "selectedOption = () =>" in visualisation_source
    assert "Plotly.react(" in visualisation_source
    for key in (
        "shear_show_stm_overlay",
        "shear_show_stm_flow",
        "shear_show_load_flow",
        "shear_show_cracks",
        "shear_show_stress_block",
    ):
        assert f'key="{key}"' in stress_field_source


def test_visualisation_block_preserves_four_view_render_order(monkeypatch) -> None:
    fake = _FakeStreamlit()

    def render_tabs(st_module, *, labels, scope_id, install_runtime=True):
        assert st_module is fake
        fake.events.append(("tabs", (labels, scope_id, install_runtime)))
        return tuple(_FakeContext(fake.events, label) for label in labels)

    monkeypatch.setattr(
        shear_visualisation,
        "_render_shear_bundle_canvas",
        lambda _runtime, **_kwargs: fake.events.append(("render", "Diagram bundle")),
    )
    monkeypatch.setattr(
        shear_visualisation,
        "_render_shear_mcft_panel",
        lambda _runtime, _fingerprint: fake.events.append(
            ("render", "MCFT options")
        ),
    )
    monkeypatch.setattr(
        shear_visualisation,
        "_render_stress_field_teaching",
        lambda _runtime: fake.events.append(("render", "Stress field teaching")),
    )
    monkeypatch.setattr(
        shear_visualisation,
        "_shear_diagram_bundle_fingerprint",
        lambda _runtime: "bundle-fingerprint",
    )
    monkeypatch.setattr(
        shear_visualisation,
        "_load_shear_diagram_bundle",
        lambda _runtime, _fingerprint: {
            "fingerprint": "bundle-fingerprint",
            "side": go.Figure(),
            "section": go.Figure(),
            "force": go.Figure(),
            "mcft": {"01000": {"figure": go.Figure().to_json(), "animated": False}},
        },
    )
    monkeypatch.setattr("streamlit.components.v1.html", lambda *_args, **_kwargs: None)

    runtime = shear_visualisation.ShearVisualisationRuntime(
        st=fake,
        get_param=lambda *_args, **_kwargs: None,
        render_timing_mark=lambda *_args, **_kwargs: None,
        render_plotly_diagram=lambda *_args, **_kwargs: None,
        render_centered_plotly=lambda *_args, **_kwargs: None,
        render_animated_plotly=lambda *_args, **_kwargs: None,
        render_section_title=lambda title: fake.events.append(("title", title)),
        info_button=lambda *_args, **_kwargs: _FakeContext(fake.events, "info"),
        render_tabs=render_tabs,
        synchronize_tabs=lambda _st, **kwargs: fake.events.append(
            ("sync", kwargs)
        ),
        build_cross_section_figure=lambda **_kwargs: go.Figure(),
        build_side_view_figure=lambda **_kwargs: go.Figure(),
        build_sfd_bmd_figure=lambda **_kwargs: (go.Figure(), go.Figure()),
        theta_v_deg=31.0,
    )
    shear_visualisation.render_shear_visualisation_block(
        runtime,
        diagram_shell_generation=1,
    )

    assert ("title", "Visualisation") in fake.events
    assert (
        "tabs",
        (
            ("Side view", "Section", "Shear diagram", "MCFT"),
            "shear-diagram-navigation",
            True,
        ),
    ) in fake.events
    assert [event for event in fake.events if event[0] == "render"] == [
        ("render", "Diagram bundle"),
        ("render", "MCFT options"),
        ("render", "Stress field teaching"),
    ]
    assert not [event for event in fake.events if event[0] == "sync"]


def test_shear_force_view_reuses_existing_vx_builder(monkeypatch) -> None:
    events: list[tuple[str, object]] = []
    state = {
        "actions_mode": "manual",
        "L": 6000.0,
        "uls_Vstar": 120.0,
        "support_type": "simply_supported",
    }

    class FakeSt:
        session_state: dict[str, object] = {}

    def get_param(name, default=None):
        return state.get(name, default)

    def build_sfd_bmd_figure(**kwargs):
        events.append(("builder", kwargs))
        return go.Figure(), go.Figure()

    def render_plotly_diagram(_figure, **kwargs):
        events.append(("plot", kwargs))

    monkeypatch.setattr(
        shear_visualisation,
        "_resolve_shear_visual_supports",
        lambda _runtime, length_m: ([0.0, length_m], ["Pinned", "Roller"]),
    )
    runtime = shear_visualisation.ShearVisualisationRuntime(
        st=FakeSt(),
        get_param=get_param,
        render_timing_mark=lambda *_args, **_kwargs: None,
        render_plotly_diagram=render_plotly_diagram,
        render_centered_plotly=lambda *_args, **_kwargs: None,
        render_animated_plotly=lambda *_args, **_kwargs: None,
        render_section_title=lambda *_args, **_kwargs: None,
        info_button=lambda *_args, **_kwargs: None,
        render_tabs=lambda *_args, **_kwargs: None,
        synchronize_tabs=lambda *_args, **_kwargs: None,
        build_cross_section_figure=lambda **_kwargs: go.Figure(),
        build_side_view_figure=lambda **_kwargs: go.Figure(),
        build_sfd_bmd_figure=build_sfd_bmd_figure,
        theta_v_deg=31.0,
    )

    shear_visualisation._render_shear_force_diagram(runtime)

    builder = next(value for name, value in events if name == "builder")
    assert builder["L"] == 6.0
    assert builder["support_positions"] == [0.0, 6.0]
    assert builder["support_types"] == ["Pinned", "Roller"]
    assert builder["V"][0] == 120.0
    assert builder["V"][-1] == -120.0
    plot = next(value for name, value in events if name == "plot")
    assert plot["key"] == "shear_visual_sfd_diagram"
    assert plot["title"] == "Shear force diagram"


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


def test_shear_shell_uses_the_bending_canvas_geometry_contract() -> None:
    source = (
        ROOT / "engineering_page_sections" / "shear_visualisation.py"
    ).read_text(encoding="utf-8")

    assert "SHEAR_DIAGRAM_PLOT_HEIGHT_PX = BENDING_DIAGRAM_PLOT_HEIGHT_PX" in source
    assert 'data-shear-diagram-geometry-token="--sb-bending-diagram-plot-height"' in source
    assert "height: var(--sb-bending-diagram-plot-height, 320px)" in source
