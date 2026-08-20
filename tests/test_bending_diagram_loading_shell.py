from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_bending_publishes_fixed_diagram_shell_before_calculation_cards() -> None:
    source = (ROOT / "bending_page_runtime.py").read_text(encoding="utf-8-sig")

    shell = source.index("render_bending_diagram_loading_shell")
    checks = source.index('render_timing_mark("bending_page.runtime.checks.start")')
    completed = source.index("with diagram_placeholder.container()")

    assert shell < completed < checks
    assert "if not diagram_rendered_early:" in source


def test_bending_shell_is_published_in_a_stable_container_immediately() -> None:
    source = (ROOT / "bending_page_runtime.py").read_text(encoding="utf-8-sig")

    shell_container = source.index("diagram_shell_container = st.container()")
    first_shell = source.index(
        "render_bending_diagram_loading_shell(\n            diagram_shell_container",
        shell_container,
    )
    slot = source.index("diagram_section_placeholder = st.empty()", first_shell)
    inputs = source.index("inputs_placeholder = st.empty()", slot)
    assert shell_container < first_shell < slot < inputs


def test_bending_diagram_shell_reserves_locked_completed_region_height() -> None:
    source = (
        ROOT / "engineering_page_sections" / "bending_diagrams.py"
    ).read_text(encoding="utf-8")

    assert 'data-testid="bending-diagram-loading-region"' in source
    assert "height: 647.15625px" in source
    assert "Preparing bending diagrams" in source
    assert 'data-bending-diagram-shell="GENERATION"' in source
    assert 'data-bending-diagram-ready="{int(diagram_shell_generation)}"' in source


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
    assert "wait_for_visualization_runtime_warmup()" in diagram_source
    assert diagram_source.index("wait_for_visualization_runtime_warmup()") < diagram_source.index(
        'state_options = ("ULS", "SLS (cracked)", "Uncracked")'
    )
