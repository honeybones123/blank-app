from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_bending_publishes_fixed_diagram_shell_before_calculation_cards() -> None:
    source = (ROOT / "bending_page_runtime.py").read_text(encoding="utf-8-sig")

    containers = source.index(
        'diagram_frame_container = st.container(key="bending_diagram_frame")'
    )
    lightweight_panel = source.index("_render_bending_state_panel(", containers)
    inputs = source.index("with inputs_placeholder.container():", lightweight_panel)
    checks = source.index('render_timing_mark("bending_page.runtime.checks.start")')

    assert containers < lightweight_panel < inputs < checks
    assert "diagram_rendered_early" not in source


def test_bending_shells_publish_back_to_back_after_stable_positions_exist() -> None:
    source = (ROOT / "bending_page_runtime.py").read_text(encoding="utf-8-sig")

    frame = source.index(
        'diagram_frame_container = st.container(key="bending_diagram_frame")'
    )
    options = source.index("diagram_options_placeholder = st.empty()", frame)
    slot = source.index("diagram_section_placeholder = st.empty()", options)
    inputs = source.index("inputs_placeholder = st.empty()", slot)
    calculation_container = source.index("calc_blocks_container = st.container()", inputs)
    calculation_shell = source.index(
        "render_bending_calculation_loading_shell(\n            calc_blocks_container",
        calculation_container,
    )
    lightweight_panel = source.index("_render_bending_state_panel(", calculation_shell)
    assert (
        frame < options < slot < inputs
        < calculation_container
        < calculation_shell < lightweight_panel
    )


def test_bending_diagram_shell_reserves_locked_completed_region_height() -> None:
    source = (
        ROOT / "engineering_page_sections" / "bending_diagrams.py"
    ).read_text(encoding="utf-8")

    assert 'data-testid="bending-diagram-loading-region"' in source
    assert "height: var(--sb-bending-diagram-plot-height, 320px)" in source
    assert "min-height: var(--sb-bending-diagram-plot-height, 320px)" in source
    assert ".st-key-bending_primary_plot_frame" in source
    assert "grid-template-columns: minmax(0, 1fr) !important" in source
    assert "min-width: 0 !important" in source
    assert "> .st-key-bending_diagram_shell" in source
    assert "647.15625px" not in source
    assert "780px" not in source
    assert "Preparing section stress and strain" in source
    assert 'data-bending-diagram-shell="GENERATION"' in source
    assert 'data-bending-diagram-ready="{generation}"' in source
    assert "pointer-events: none" in source
    assert source.count('.js-plotly-plot .scatterlayer .trace') == 1
    assert source.count('.js-plotly-plot g.shapelayer .shape-group') == 1
    assert source.count('.js-plotly-plot .annotation') == 1
    assert 'data-sb-bending-plot-ready' not in source
    assert source.count(
        'data-bending-diagram-geometry-token="--sb-bending-diagram-plot-height"'
    ) == 2
    assert '> div[data-testid="stElementContainer"] {' in source
    assert "margin-bottom: 0 !important" in source


def test_bending_diagram_geometry_uses_shared_tokens() -> None:
    tokens = (ROOT / "ui" / "design_tokens.py").read_text(encoding="utf-8")
    figure = (
        ROOT / "ui" / "diagrams" / "stress_strain_diagram.py"
    ).read_text(encoding="utf-8")

    assert "BENDING_DIAGRAM_PLOT_HEIGHT_PX = 320" in tokens
    assert "BENDING_DIAGRAM_REGION_HEIGHT_PX" not in tokens
    assert "bending-diagram-region-height" not in tokens
    assert "height=BENDING_DIAGRAM_PLOT_HEIGHT_PX" in figure


def test_bending_browser_regression_measures_live_geometry_and_blank_hosts() -> None:
    verifier = (
        ROOT / "tools" / "verification" / "helpers" / "bending_diagram_regression.py"
    ).read_text(encoding="utf-8")

    assert "layout_delta_px" in verifier
    assert "geometry_delta_px" in verifier
    assert "shell_width_delta_px" in verifier
    assert "live_width_delta_px" in verifier
    assert "loading shell did not fill its frame" in verifier
    assert "live diagram did not fill its frame" in verifier
    assert "abs(geometry_delta) > 2" in verifier
    assert "cold shell blocked downward scrolling" in verifier
    assert "scroll position was forced after user input" in verifier
    assert "mixed or blank state frame" in verifier
    assert "partial Plotly host escaped the loading shell" in verifier
    assert "incomplete visible state host" in verifier
    assert "cold_paint_frames" in verifier
    assert 'state="hidden"' in verifier
    assert '"switches": 20' in verifier
    assert '"SLS (cracked)": "sls-cracked"' in verifier
    assert '"Uncracked": "uncracked"' in verifier
    assert "Material lesson live Plotly chart did not mount" in verifier


def test_bending_calculation_shell_reserves_the_measured_collapsed_region() -> None:
    runtime = (ROOT / "bending_page_runtime.py").read_text(encoding="utf-8-sig")
    source = (
        ROOT / "engineering_page_sections" / "bending_diagrams.py"
    ).read_text(encoding="utf-8")

    assert "render_bending_calculation_loading_shell(" in runtime
    assert 'data-testid="bending-calculation-loading-region"' in source
    assert "height: 869.21875px" in source
    assert source.count('class="bending-calculation-loading-card"') == 8
    assert 'data-testid="bending-calculation-ready"' in runtime


def test_bending_defers_visualisation_wait_until_diagram_boundary() -> None:
    app_source = (ROOT / "app.py").read_text(encoding="utf-8-sig")
    diagram_source = (
        ROOT / "engineering_page_sections" / "bending_diagrams.py"
    ).read_text(encoding="utf-8")

    assert 'if _opening_page_slug != "bending":' in app_source
    assert app_source.index('if _opening_page_slug != "bending":') < app_source.index(
        "start_v2_runtime_warmup()"
    )
    assert app_source.index('if _opening_page_slug != "bending":') < app_source.index(
        "start_visualization_runtime_warmup()"
    )
    assert "start_v2_runtime_warmup()" in diagram_source
    assert "start_visualization_runtime_warmup()" in diagram_source
    wait = diagram_source.index("wait_for_visualization_runtime_warmup()")
    guard = diagram_source.index("if primary_published:", 0, wait)
    assert guard < wait < diagram_source.index(
        'state_options = ("ULS", "SLS (cracked)", "Uncracked")'
    )
