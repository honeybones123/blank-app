from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_bending_runtime_delegates_material_lesson_to_styled_component() -> None:
    source = (ROOT / "bending_page_runtime.py").read_text(encoding="utf-8")

    assert (
        "from engineering_page_sections.bending_material_teaching import "
        "render_bending_material_teaching_panel"
    ) in source
    assert "render_bending_material_teaching_panel(" in source
    assert "plot_material_curves=_plot_material_stress_strain_curves" in source
    assert "strain_display" not in source[source.index("def _render_material_model_content"):]


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
