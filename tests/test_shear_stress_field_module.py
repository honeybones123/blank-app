from __future__ import annotations

import ast
from pathlib import Path

import plotly.graph_objects as go

from engineering_page_sections import shear_stress_field


ROOT = Path(__file__).resolve().parents[1]


class _FakeStreamlit:
    def __init__(self, state: dict[str, object] | None = None):
        self.session_state = dict(state or {})


def test_mcft_figure_reuses_existing_renderer_and_authoritative_angle(monkeypatch) -> None:
    calls: list[dict[str, object]] = []
    expected = go.Figure()

    def build(**kwargs):
        calls.append(kwargs)
        return expected

    monkeypatch.setattr(shear_stress_field, "build_shear_behaviour_figure", build)
    fake = _FakeStreamlit(
        {
            "shear_show_stm_overlay": True,
            "shear_show_stm_flow": False,
            "shear_show_load_flow": False,
            "shear_show_cracks": True,
            "shear_show_stress_block": False,
        }
    )

    figure, animated = shear_stress_field.build_mcft_stress_field_figure(
        st_module=fake,
        theta_v_deg=31.25,
    )

    assert figure is expected
    assert animated is False
    assert calls == [
        {
            "visual_mode": "Principal stress field",
            "theta_v_deg": 31.25,
            "show_load_flow": False,
            "show_cracks": True,
            "show_stress_block": False,
            "show_stm_overlay": True,
            "show_stm_flow": False,
        }
    ]


def test_stress_field_module_is_presentation_only() -> None:
    source = (
        ROOT / "engineering_page_sections" / "shear_stress_field.py"
    ).read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported_roots = {
        alias.name.split(".", 1)[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    imported_roots.update(
        str(node.module or "").split(".", 1)[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
    )

    assert "shear_core" not in imported_roots
    assert "shear_calculation_runtime" not in imported_roots
    assert "calculations" not in imported_roots


def test_one_shell_owns_three_views_and_teaching_is_outside_selection() -> None:
    source = (
        ROOT / "engineering_page_sections" / "shear_visualisation.py"
    ).read_text(encoding="utf-8")

    assert 'SHEAR_DIAGRAM_VIEWS = ("ULS", "SLS", "MCFT")' in source
    assert source.count("render_mcft_stress_field_diagram(") == 1
    assert source.count("_render_stress_field_teaching(runtime)") == 1
    assert source.index('scope_id="shear-diagram-navigation"') < source.index(
        "_render_stress_field_teaching(runtime)"
    )
    assert "pointer-events: none" in source
    assert "Show detailed MCFT breakdown" not in source


def test_legacy_mcft_toggle_and_standalone_render_path_are_removed() -> None:
    combined = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (
            ROOT / "shear_page_runtime.py",
            ROOT / "engineering_page_sections" / "shear_page_context.py",
            ROOT / "engineering_page_sections" / "shear_mcft_strength_checks.py",
            ROOT / "engineering_page_sections" / "shear_visualisation.py",
            ROOT / "engineering_page_sections" / "shear_stress_field.py",
        )
    )

    assert "show_mcft_breakdown" not in combined
    assert "Show detailed MCFT breakdown" not in combined
    assert "def _render_shear_behaviour_diagrams" not in combined
    assert combined.count('chart_key="shear_behaviour_mcft_shell"') == 1
