from __future__ import annotations

from pathlib import Path

import plotly.graph_objects as go

from engineering_page_sections import shear_visualisation


ROOT = Path(__file__).resolve().parents[1]


class _FakeStreamlit:
    def __init__(self) -> None:
        self.session_state: dict[str, object] = {}


def _runtime(fake: _FakeStreamlit) -> shear_visualisation.ShearVisualisationRuntime:
    noop = lambda *_args, **_kwargs: None
    return shear_visualisation.ShearVisualisationRuntime(
        st=fake,
        get_param=lambda *_args, **_kwargs: None,
        render_timing_mark=noop,
        render_plotly_diagram=noop,
        render_centered_plotly=noop,
        render_animated_plotly=noop,
        render_section_title=noop,
        info_button=noop,
        render_lazy_expander=noop,
        render_tabs=noop,
        build_cross_section_figure=lambda **_kwargs: go.Figure(),
        build_side_view_figure=lambda **_kwargs: go.Figure(),
        build_sfd_bmd_figure=lambda **_kwargs: (go.Figure(), go.Figure()),
        theta_v_deg=31.0,
    )


def test_bundle_prebuilds_every_mcft_toggle_projection(monkeypatch) -> None:
    fake = _FakeStreamlit()
    runtime = _runtime(fake)
    figure = go.Figure(go.Scatter(x=[0, 1], y=[0, 1]))

    monkeypatch.setattr(
        shear_visualisation,
        "_build_shear_side_view",
        lambda _runtime: go.Figure(figure),
    )
    monkeypatch.setattr(
        shear_visualisation,
        "_build_shear_cross_section",
        lambda _runtime: go.Figure(figure),
    )
    monkeypatch.setattr(
        shear_visualisation,
        "_build_shear_force_diagram",
        lambda _runtime: go.Figure(figure),
    )
    monkeypatch.setattr(
        shear_visualisation,
        "build_mcft_stress_field_figure",
        lambda *, theta_v_deg, options: (
            go.Figure(figure),
            bool(options["show_load_flow"] or options["show_stm_flow"]),
        ),
    )

    bundle = shear_visualisation._build_shear_diagram_bundle(runtime, "beam-1")

    assert len(bundle["mcft"]) == 32
    assert len(set(bundle["mcft"])) == 32
    assert all("figure" in projection for projection in bundle["mcft"].values())
    assert (
        len(
            fake.session_state[
                shear_visualisation.SHEAR_DIAGRAM_BUNDLE_CACHE_KEY
            ]["entries"]["beam-1"]["mcft"]
        )
        == 32
    )


def test_bundle_cache_is_bounded(monkeypatch) -> None:
    fake = _FakeStreamlit()
    runtime = _runtime(fake)
    figure = go.Figure(go.Scatter(x=[0], y=[0]))
    monkeypatch.setattr(
        shear_visualisation,
        "_build_shear_side_view",
        lambda _runtime: go.Figure(figure),
    )
    monkeypatch.setattr(
        shear_visualisation,
        "_build_shear_cross_section",
        lambda _runtime: go.Figure(figure),
    )
    monkeypatch.setattr(
        shear_visualisation,
        "_build_shear_force_diagram",
        lambda _runtime: go.Figure(figure),
    )
    monkeypatch.setattr(
        shear_visualisation,
        "build_mcft_stress_field_figure",
        lambda *, theta_v_deg, options: (go.Figure(figure), False),
    )

    for fingerprint in ("beam-1", "beam-2", "beam-3"):
        shear_visualisation._build_shear_diagram_bundle(runtime, fingerprint)

    cache = fake.session_state[shear_visualisation.SHEAR_DIAGRAM_BUNDLE_CACHE_KEY]
    assert cache["order"] == ["beam-2", "beam-3"]
    assert set(cache["entries"]) == {"beam-2", "beam-3"}


def test_lightweight_page_triggers_one_bundle_only_after_page_ready() -> None:
    visual_source = (
        ROOT / "engineering_page_sections" / "shear_visualisation.py"
    ).read_text(encoding="utf-8")
    runtime_source = (ROOT / "shear_page_runtime.py").read_text(encoding="utf-8")

    assert 'key="shear_deferred_bundle_button"' in visual_source
    assert "data-shear-lightweight-ready" in visual_source
    assert "data-shear-page-lightweight-ready" in runtime_source
    assert "requestAnimationFrame(() => window.requestAnimationFrame" in visual_source
    assert "}}, 150);" in visual_source
    assert visual_source.count("button.click()") == 1
    assert 'addEventListener("wheel"' not in visual_source
    assert "scrollTop" not in visual_source
    assert "touchmove" not in visual_source


def test_native_bending_pattern_mounts_the_complete_prepared_bundle() -> None:
    source = (
        ROOT / "engineering_page_sections" / "shear_visualisation.py"
    ).read_text(encoding="utf-8")

    for view in ("side", "section", "force", "mcft"):
        assert f".st-key-shear_{view}_diagram_live" in source
        assert f'key="shear_{view}_diagram_shell"' in source
    assert "_render_shear_bundle_canvas(" not in source
    assert "Plotly.react(" not in source
    assert "plotly-basic-2.35.2.min.js" not in source
    assert 'scope_id="shear-diagram-navigation"' in source
    assert "completePlot('.st-key-shear_side_diagram_live" in source
    assert "completePlot('.st-key-shear_section_diagram_live" in source
    assert "completePlot('.st-key-shear_force_diagram_live" in source
    assert "completeMcft()" in source
    assert "data-shear-mcft-projection-count" in source
    assert "data-shear-mcft-option-key" in source


def test_shell_and_live_canvas_share_the_bending_height_token() -> None:
    source = (
        ROOT / "engineering_page_sections" / "shear_visualisation.py"
    ).read_text(encoding="utf-8")

    assert 'data-shear-diagram-geometry-token="--sb-bending-diagram-plot-height"' in source
    assert source.count("var(--sb-bending-diagram-plot-height, 320px)") >= 5
    assert "pointer-events: none !important" in source
    assert "background: #f8fafc" in source
    assert "Shear diagrams loading" in source
    assert "Preparing MCFT stress field" not in source
    assert "data-stale=\"true\"" not in source
    assert "scrollTop" not in source
