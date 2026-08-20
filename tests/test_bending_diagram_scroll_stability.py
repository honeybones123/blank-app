from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_bending_views_use_client_side_tabs_without_a_rerun_selector() -> None:
    source = (
        ROOT / "engineering_page_sections" / "bending_diagrams.py"
    ).read_text(encoding="utf-8")

    assert 'section_tab, side_view_tab, moment_tab = render_stable_tabs(' in source
    assert 'key="bending_diagram_view"' not in source
    assert 'if diagram_view == "Section":' not in source


def test_bending_diagrams_use_stable_streamlit_component_keys() -> None:
    diagrams = (
        ROOT / "engineering_page_sections" / "bending_diagrams.py"
    ).read_text(encoding="utf-8")
    side_view = (ROOT / "bending_side_view_diagram.py").read_text(encoding="utf-8")

    assert 'key="bending_section_stress_strain"' in diagrams
    assert 'key="bending_side_view"' in side_view
    assert 'key=f"bending_side_view_' not in side_view
    assert "@st.fragment\ndef render_bending_side_view_diagram(" in side_view


def test_bending_check_tabs_keep_a_stable_container() -> None:
    """A tab click must not replace the detailed-calculation DOM slot."""

    source = (ROOT / "bending_page_runtime.py").read_text(encoding="utf-8")

    assert "calc_blocks_container = st.container()" in source
    assert "with calc_blocks_container:" in source
    assert "calc_blocks_placeholder = st.empty()" not in source


def test_bending_calculation_tabs_are_client_side_and_preserve_scroll() -> None:
    """ULS/SLS selection is view-only and must not remount the page."""

    source = (ROOT / "bending_page_runtime.py").read_text(encoding="utf-8")

    assert "uls_checks_tab, sls_checks_tab, minimum_checks_tab = render_stable_tabs(" in source
    assert "with uls_checks_tab:" in source
    assert "with sls_checks_tab:" in source
    assert "with minimum_checks_tab:" in source
    assert 'scope_id="bending-calculation-checks"' in source
    diagrams = (
        ROOT / "engineering_page_sections" / "bending_diagrams.py"
    ).read_text(encoding="utf-8")
    assert 'scope_id="bending-section-diagrams"' in diagrams
    assert "preserve_scroll_for_preceding_widget" in source
    assert "render_stable_tabs" in source
    assert "render_lazy_check_tab_selector" not in source


def test_bending_state_selector_preserves_main_scroll_during_rerun() -> None:
    runtime = (ROOT / "bending_page_runtime.py").read_text(encoding="utf-8")
    helper = (
        ROOT / "engineering_page_sections" / "stable_tabs.py"
    ).read_text(encoding="utf-8")

    diagrams = (
        ROOT / "engineering_page_sections" / "bending_diagrams.py"
    ).read_text(encoding="utf-8")
    assert "preserve_scroll_for_preceding_widget(" in diagrams
    assert 'scope_id="bending-state-selector"' in diagrams
    assert "data-sb-stable-widget-scroll" in helper
    assert "installParentRuntime" in helper
    assert "sb-stable-widget-scroll-runtime" in helper
    assert "holdPosition(pending)" in helper
    assert "MutationObserver(lockScroll)" in helper
    assert "scroller.scrollTop = pending.top" in helper
    assert "event.preventDefault()" not in helper


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
