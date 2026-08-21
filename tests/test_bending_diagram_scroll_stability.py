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

    assert 'key=f"bending_section_stress_strain_{option_key}"' in diagrams
    assert 'key=f"bending_state_plot_{option_key}"' in diagrams
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


def test_bending_state_selector_uses_cancellable_one_shot_scroll_correction() -> None:
    diagrams = (
        ROOT / "engineering_page_sections" / "bending_diagrams.py"
    ).read_text(encoding="utf-8")
    helper = (
        ROOT / "engineering_page_sections" / "stable_tabs.py"
    ).read_text(encoding="utf-8")

    assert "preserve_scroll_for_preceding_widget(" in diagrams
    assert 'scope_id="bending-state-selector"' in diagrams
    assert "data-sb-stable-widget-scroll" in helper
    assert "sawReadyRemoval" in helper
    assert "scroller.scrollTop = pending.top" in helper
    assert "clearWidgetRestore();" in helper
    assert "cancelPendingScrollPreservation" in helper
    assert "holdPosition" not in helper
    assert "MutationObserver(lockScroll)" not in helper
    assert "3500" not in helper
    assert "event.preventDefault()" not in helper


def test_bending_mounts_complete_independent_state_figures() -> None:
    diagrams = (
        ROOT / "engineering_page_sections" / "bending_diagrams.py"
    ).read_text(encoding="utf-8")

    assert 'state_options = ("ULS", "SLS (cracked)", "Uncracked")' in diagrams
    assert "state_figures = {main_state: selected_fig_ss}" in diagrams
    assert "state_figures[option] = _plot_stress_strain_profiles(" in diagrams
    assert 'state_label=option_label' in diagrams
    assert "bending_state_plot_" in diagrams
    assert "display:none!important" in diagrams
    assert "display:block!important" in diagrams
    assert "combined_fig" not in diagrams
    assert "trace_groups" not in diagrams
    assert "shape_groups" not in diagrams
    assert "annotation_groups" not in diagrams
    assert "data-sb-preloaded-plotly-state" not in diagrams


def test_explicit_state_label_remains_plot_authority() -> None:
    diagrams = (
        ROOT / "engineering_page_sections" / "bending_diagrams.py"
    ).read_text(encoding="utf-8")

    assert "diagram_state_label, _ = state_projection(main_state)" in diagrams
    assert "state_label=diagram_state_label" in diagrams
    assert "option_label, option_state = state_projection(option)" in diagrams
    assert "state_label=option_label" in diagrams


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
    assert runtime.index('render_timing_mark("bending_page.runtime.checks.end")') < runtime.rindex(
        "_render_bending_state_panel("
    )


def test_material_lesson_has_an_explicit_real_body() -> None:
    diagrams = (
        ROOT / "engineering_page_sections" / "bending_diagrams.py"
    ).read_text(encoding="utf-8")

    assert "def render_material_teaching_lesson()" in diagrams
    assert "render_bending_material_teaching_panel(" in diagrams
    assert "plot_material_curves=_plot_material_stress_strain_curves" in diagrams
    assert "render_lazy_expander(" in diagrams
    assert "lambda: None" not in diagrams
