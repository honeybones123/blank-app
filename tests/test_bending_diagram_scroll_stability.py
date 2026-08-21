from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_bending_views_use_client_side_tabs_without_a_rerun_selector() -> None:
    source = (
        ROOT / "engineering_page_sections" / "bending_diagrams.py"
    ).read_text(encoding="utf-8")

    assert "section_tab, side_view_tab, moment_tab = render_stable_tabs(" in source
    assert 'key="bending_diagram_view"' not in source
    assert 'if diagram_view == "Section":' not in source


def test_bending_diagrams_use_stable_component_keys() -> None:
    diagrams = (
        ROOT / "engineering_page_sections" / "bending_diagrams.py"
    ).read_text(encoding="utf-8")
    side_view = (ROOT / "bending_side_view_diagram.py").read_text(encoding="utf-8")

    assert 'key=f"bending_section_stress_strain_{state_key}_chart"' in diagrams
    assert 'key="bending_primary_plot_frame"' in diagrams
    assert 'key="bending_side_view"' in side_view
    assert 'key=f"bending_side_view_' not in side_view
    assert "@st.fragment\ndef render_bending_side_view_diagram(" in side_view


def test_bending_check_tabs_keep_a_stable_container() -> None:
    source = (ROOT / "bending_page_runtime.py").read_text(encoding="utf-8")

    assert "calc_blocks_container = st.container()" in source
    assert "with calc_blocks_container:" in source
    assert "calc_blocks_placeholder = st.empty()" not in source


def test_bending_calculation_tabs_are_client_side_and_preserve_scroll() -> None:
    runtime = (ROOT / "bending_page_runtime.py").read_text(encoding="utf-8")
    diagrams = (
        ROOT / "engineering_page_sections" / "bending_diagrams.py"
    ).read_text(encoding="utf-8")

    assert "uls_checks_tab, sls_checks_tab, minimum_checks_tab = render_stable_tabs(" in runtime
    assert "with uls_checks_tab:" in runtime
    assert "with sls_checks_tab:" in runtime
    assert "with minimum_checks_tab:" in runtime
    assert 'scope_id="bending-calculation-checks"' in runtime
    assert 'scope_id="bending-section-diagrams"' in diagrams
    assert "render_lazy_check_tab_selector" not in runtime


def test_cold_bending_state_panel_does_not_install_scroll_correction() -> None:
    diagrams = (
        ROOT / "engineering_page_sections" / "bending_diagrams.py"
    ).read_text(encoding="utf-8")
    helper = (
        ROOT / "engineering_page_sections" / "stable_tabs.py"
    ).read_text(encoding="utf-8")

    assert "preserve_scroll_for_preceding_widget(" not in diagrams
    assert "scrollTop" not in diagrams
    assert "requestAnimationFrame(() => window.requestAnimationFrame" in diagrams
    assert "data-bending-lightweight-ready" in diagrams
    assert "bending-calculation-ready" in diagrams
    assert "preserve_scroll_for_preceding_widget" not in helper
    assert "data-sb-stable-widget-scroll" not in helper
    assert "sawReadyRemoval" not in helper
    assert "pendingWidgetRestore" not in helper
    assert "bending_state_plot_" not in helper
    assert "cancelPendingScrollPreservation" in helper
    assert "holdPosition" not in helper
    assert "MutationObserver(lockScroll)" not in helper
    assert "3500" not in helper
    assert "event.preventDefault()" not in helper


def test_bending_mounts_only_the_selected_state_figure() -> None:
    diagrams = (
        ROOT / "engineering_page_sections" / "bending_diagrams.py"
    ).read_text(encoding="utf-8")

    assert 'state_options = ("ULS", "SLS (cracked)", "Uncracked")' in diagrams
    assert "selected_fig_ss = None" in diagrams
    assert "if primary_published:" in diagrams
    assert diagrams.count("st.plotly_chart(") == 1
    assert "key=f\"bending_section_stress_strain_{state_key}_chart\"" in diagrams
    assert "state_figures" not in diagrams
    assert "bending_state_plot_" not in diagrams
    assert "display:none!important" not in diagrams
    assert "combined_fig" not in diagrams
    assert "trace_groups" not in diagrams
    assert "shape_groups" not in diagrams
    assert "annotation_groups" not in diagrams
    assert "data-sb-preloaded-plotly-state" not in diagrams


def test_explicit_state_label_remains_plot_authority() -> None:
    diagrams = (
        ROOT / "engineering_page_sections" / "bending_diagrams.py"
    ).read_text(encoding="utf-8")

    assert "diagram_state_label = _bending_state_label(" in diagrams
    assert "state_label=diagram_state_label" in diagrams
    assert "def _build_bending_state_projection(" in diagrams
    assert '"bending_state_main"' in diagrams


def test_lightweight_stage_does_not_build_or_warm_plotting_state() -> None:
    diagrams = (
        ROOT / "engineering_page_sections" / "bending_diagrams.py"
    ).read_text(encoding="utf-8")

    assert "def _bending_state_label(" in diagrams
    assert "if primary_published:\n        start_v2_runtime_warmup()" in diagrams
    assert "start_visualization_runtime_warmup()\n        wait_for_visualization_runtime_warmup()" in diagrams
    label_body = diagrams.split("def _bending_state_label(", 1)[1].split(
        "\ndef _build_bending_state_projection", 1
    )[0]
    assert "_stress_strain_state(" not in label_body


def test_inactive_states_are_cached_after_primary_paint_without_mounting() -> None:
    runtime = (ROOT / "bending_page_runtime.py").read_text(encoding="utf-8")
    diagrams = (
        ROOT / "engineering_page_sections" / "bending_diagrams.py"
    ).read_text(encoding="utf-8")

    assert "_render_bending_secondary_state_cache = st.fragment(" in runtime
    assert "def render_bending_secondary_state_cache(" in diagrams
    cache_body = diagrams.split(
        "def render_bending_secondary_state_cache(", 1
    )[1].split("\ndef _coalesce_num", 1)[0]
    assert "_build_bending_state_projection(" in cache_body
    assert "_plot_stress_strain_profiles(" in cache_body
    assert "st.plotly_chart(" not in cache_body
    assert "render_plotly_diagram(" not in cache_body
    assert "requestIdleCallback" in cache_body
    assert "scatterlayer .trace" in cache_body
    assert "shapelayer .shape-group" in cache_body
    assert ".annotation" in cache_body
    assert "data-bending-secondary-diagrams-ready" in cache_body


def test_bending_state_switch_owns_only_state_dependent_diagrams() -> None:
    runtime = (ROOT / "bending_page_runtime.py").read_text(encoding="utf-8")
    diagrams = (
        ROOT / "engineering_page_sections" / "bending_diagrams.py"
    ).read_text(encoding="utf-8")

    assert "_render_bending_state_panel = st.fragment(" in runtime
    assert "def render_bending_state_panel(" in diagrams
    assert 'key="bending_state_main"' in diagrams
    assert "render_uls_tab(" not in diagrams
    assert "render_sls_tab(" not in diagrams
    containers = runtime.index(
        'diagram_frame_container = st.container(key="bending_diagram_frame")'
    )
    panel = runtime.index("_render_bending_state_panel(", containers)
    checks = runtime.index('render_timing_mark("bending_page.runtime.checks.end")')
    assert panel < checks


def test_inactive_diagram_tabs_are_deferred_until_first_selection() -> None:
    diagrams = (
        ROOT / "engineering_page_sections" / "bending_diagrams.py"
    ).read_text(encoding="utf-8")

    assert 'key="bending_deferred_side_button"' in diagrams
    assert 'key="bending_deferred_moment_button"' in diagrams
    assert "if side_published:" in diagrams
    assert "if moment_published:" in diagrams
    assert 'data-bending-side-view-deferred="1"' in diagrams
    assert 'data-bending-moment-deferred="1"' in diagrams


def test_material_lesson_has_an_explicit_real_body() -> None:
    diagrams = (
        ROOT / "engineering_page_sections" / "bending_diagrams.py"
    ).read_text(encoding="utf-8")

    assert "def render_material_teaching_lesson()" in diagrams
    assert "render_bending_material_teaching_panel(" in diagrams
    assert "plot_material_curves=_plot_material_stress_strain_curves" in diagrams
    assert "render_lazy_expander(" in diagrams
    assert "lambda: None" not in diagrams
