from pathlib import Path

from engineering_page_sections import bending_diagrams


ROOT = Path(__file__).resolve().parents[1]


def test_bending_diagram_runtime_hook_replaces_only_material_lesson() -> None:
    calls = []

    def original(label, render_body, *args, **kwargs):
        calls.append((label, render_body, args, kwargs))
        return "rendered"

    namespace = {
        "render_lazy_expander": original,
        "st": object(),
        "_plot_material_stress_strain_curves": lambda: None,
        "render_plotly_diagram": lambda *args, **kwargs: None,
    }
    bending_diagrams.bind_runtime(namespace)
    wrapped = namespace["render_lazy_expander"]

    ordinary_body = lambda: None
    assert wrapped("Other", ordinary_body, key="other_expander") == "rendered"
    assert calls[-1][0] == "Other"
    assert calls[-1][1] is ordinary_body

    assert (
        wrapped(
            "Old material title",
            ordinary_body,
            key="bending_material_model_expander",
        )
        == "rendered"
    )
    assert calls[-1][0] == "ℹ️ From strain to stress to internal force"
    assert calls[-1][1] is not ordinary_body


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
