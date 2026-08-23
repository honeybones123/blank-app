from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _bundle_source() -> str:
    return (
        ROOT / "engineering_page_sections" / "bending_diagram_bundle.py"
    ).read_text(encoding="utf-8")


def test_bending_views_are_one_native_tab_bundle() -> None:
    source = _bundle_source()

    assert (
        "section_tab, side_view_tab, moment_tab = runtime.render_stable_tabs("
        in source
    )
    assert 'scope_id="bending-section-diagrams"' in source
    assert "with section_tab:" in source
    assert "with side_view_tab:" in source
    assert "with moment_tab:" in source
    assert 'key="bending_diagram_view"' not in source


def test_bundle_uses_one_post_paint_trigger_and_no_per_tab_loader() -> None:
    source = _bundle_source()

    assert 'key="bending_deferred_bundle_button"' in source
    assert "requestBundleAfterPaint" in source
    assert "data-bending-lightweight-ready" in source
    assert "bending-calculation-ready" in source
    assert "pointerdown" not in source
    for obsolete in (
        "bending_deferred_side_button",
        "bending_deferred_moment_button",
        "_bending_side_view_published",
        "_bending_moment_view_published",
        "data-bending-side-view-deferred",
        "data-bending-moment-deferred",
    ):
        assert obsolete not in source


def test_bundle_prepares_all_three_figures_before_native_tab_use() -> None:
    source = _bundle_source()

    assert "def _build_or_load_bundle(" in source
    assert "section_figures = {}" in source
    assert "side_figures = {}" in source
    assert "figure_bmd_from_state(" in source
    assert '"section": section_figures' in source
    assert '"side": side_figures' in source
    assert '"moment": moment_figure' in source
    assert "render_prepared_bending_side_view_diagram(" in source
    assert "render_plotly_diagram(" in source


def test_explicit_state_label_remains_plot_authority() -> None:
    source = _bundle_source()
    diagrams = (
        ROOT / "engineering_page_sections" / "bending_diagrams.py"
    ).read_text(encoding="utf-8")

    assert "def _build_bending_state_projection(" in diagrams
    assert "state_label=projection[\"state_label\"]" in source
    assert 'key="bending_state_main"' in source
    assert "STATE_OPTIONS = (\"ULS\", \"SLS (cracked)\", \"Uncracked\")" in source


def test_bending_state_switch_owns_only_diagram_fragment() -> None:
    runtime = (ROOT / "bending_page_runtime.py").read_text(encoding="utf-8")
    source = _bundle_source()

    assert "_render_bending_diagram_bundle_panel = st.fragment(" in runtime
    assert "_render_bending_state_controls = st.fragment(" in runtime
    assert "_render_bending_state_controls()" in runtime
    assert "def render_bending_diagram_bundle_panel(" in source
    assert "def render_bending_state_controls(" in source
    assert "render_uls_tab(" not in source
    assert "render_sls_tab(" not in source
    assert "scrollTop" not in source
    assert "event.preventDefault()" not in source


def test_bending_state_switch_is_plotly_owned_progressive_enhancement() -> None:
    source = _bundle_source()

    assert 'data-bending-requested-state="' in source
    assert "const applyRequestedState = () =>" in source
    assert "Plotly.react(" in source
    assert "Plotly.relayout(" in source
    assert "update the hidden diagram first" in source.lower()
    assert "keep the last complete" in source.lower()
    assert "node.style.opacity" not in source
    assert "dataset.sbPlotlyState" not in source
    assert "data-sb-preloaded-plotly-state" not in source


def test_default_side_view_updates_only_state_dependent_layout() -> None:
    source = _bundle_source()

    assert "const sideHasOverlay =" in source
    assert "annotations: spec.layout.annotations || []" in source
    assert "shapes: spec.layout.shapes || []" in source
    assert "sideHasOverlay" in source
    assert "|| visible" in source
    assert "Plotly.restyle(" in source


def test_material_lesson_has_an_explicit_real_body() -> None:
    source = _bundle_source()

    assert "def _render_material_teaching_lesson(runtime:" in source
    assert "render_bending_material_teaching_panel(" in source
    assert "plot_material_curves=runtime.plot_material_stress_strain_curves" in source
    assert "runtime.render_lazy_expander(" in source
    assert "lambda: None" not in source


def test_diagram_modules_use_explicit_dependencies_not_runtime_global_binding() -> None:
    source = _bundle_source()
    diagrams = (
        ROOT / "engineering_page_sections" / "bending_diagrams.py"
    ).read_text(encoding="utf-8")
    runtime = (ROOT / "bending_page_runtime.py").read_text(encoding="utf-8")

    assert "class BendingDiagramRuntime:" in source
    assert "runtime: BendingDiagramRuntime" in source
    assert "bind_runtime" not in source
    assert "globals().update" not in source
    assert "bind_runtime" not in diagrams
    assert "_bending_diagram_runtime =" in runtime
    assert "_bending_diagram_bundle.bind_runtime" not in runtime
    assert "_bending_diagrams_section.bind_runtime" not in runtime


def test_stable_tabs_do_not_install_a_prolonged_scroll_lock() -> None:
    helper = (
        ROOT / "engineering_page_sections" / "stable_tabs.py"
    ).read_text(encoding="utf-8")

    assert "cancelPendingScrollPreservation" in helper
    assert "holdPosition" not in helper
    assert "MutationObserver(lockScroll)" not in helper
    assert "3500" not in helper
    assert "event.preventDefault()" not in helper
