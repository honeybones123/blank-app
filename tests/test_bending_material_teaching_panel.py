from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_bending_material_lesson_is_an_explicit_non_empty_expander_body() -> None:
    source = (
        ROOT / "engineering_page_sections" / "bending_diagram_bundle.py"
    ).read_text(encoding="utf-8")

    assert "def _render_material_teaching_lesson(runtime:" in source
    assert "render_bending_material_teaching_panel(" in source
    assert "plot_material_curves=runtime.plot_material_stress_strain_curves" in source
    assert "render_plotly_diagram=runtime.render_plotly_diagram" in source
    assert "lambda: _render_material_teaching_lesson(runtime)" in source
    assert "lambda: None" not in source
    assert "_install_material_teaching_override" not in source


def test_material_lesson_matches_the_approved_reading_order() -> None:
    source = (
        ROOT / "engineering_page_sections" / "bending_material_teaching.py"
    ).read_text(encoding="utf-8")

    assert "From strain to stress to internal force" in source
    assert "Determine strain at each location from the linear strain profile." in source
    assert "How does strain become stress?" in source
    assert "From stress to internal force and equilibrium" in source
    assert "Neutral axis → Strain → Stress → Force → Equilibrium" in source
    assert source.index("sb-material-major-one") < source.index("sb-material-major-two")
    assert "grid-template-columns: minmax(0, 3fr) minmax(260px, 1fr)" in source
