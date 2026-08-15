from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_bending_views_use_client_side_tabs_without_a_rerun_selector() -> None:
    source = (ROOT / "bending_page_runtime.py").read_text(encoding="utf-8")

    assert 'section_tab, side_view_tab = st.tabs(diagram_options)' in source
    assert 'key="bending_diagram_view"' not in source
    assert 'if diagram_view == "Section":' not in source


def test_bending_diagrams_use_stable_streamlit_component_keys() -> None:
    runtime = (ROOT / "bending_page_runtime.py").read_text(encoding="utf-8")
    side_view = (ROOT / "bending_side_view_diagram.py").read_text(encoding="utf-8")

    assert 'section_chart_key = "bending_section_stress_strain"' in runtime
    assert 'key="bending_side_view"' in side_view
    assert 'key=f"bending_side_view_' not in side_view
    assert "@st.fragment\ndef render_bending_side_view_diagram(" in side_view
