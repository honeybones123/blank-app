from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_bending_views_use_client_side_tabs_without_a_rerun_selector() -> None:
    source = (ROOT / "bending_page_runtime.py").read_text(encoding="utf-8")

    assert 'section_tab, side_view_tab = render_stable_tabs(' in source
    assert 'key="bending_diagram_view"' not in source
    assert 'if diagram_view == "Section":' not in source


def test_bending_diagrams_use_stable_streamlit_component_keys() -> None:
    runtime = (ROOT / "bending_page_runtime.py").read_text(encoding="utf-8")
    side_view = (ROOT / "bending_side_view_diagram.py").read_text(encoding="utf-8")

    assert 'section_chart_key = "bending_section_stress_strain"' in runtime
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
    assert 'scope_id="bending-section-diagrams"' in source
    assert "from engineering_page_sections.stable_tabs import render_stable_tabs" in source
    assert "render_lazy_check_tab_selector" not in source
