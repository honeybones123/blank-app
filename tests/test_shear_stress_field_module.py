from __future__ import annotations

import ast
from pathlib import Path

import plotly.graph_objects as go

from engineering_page_sections import shear_stress_field


ROOT = Path(__file__).resolve().parents[1]


class _FakeStreamlit:
    def __init__(self, state: dict[str, object] | None = None):
        self.session_state = dict(state or {})


class _FakeOptionsStreamlit(_FakeStreamlit):
    def __init__(self):
        super().__init__()
        self.captions: list[str] = []
        self.toggles: list[tuple[str, str, bool]] = []

    def caption(self, value: str) -> None:
        self.captions.append(value)

    def toggle(self, label: str, *, value: bool, key: str) -> None:
        self.toggles.append((label, key, value))
        self.session_state.setdefault(key, value)


def test_mcft_figure_reuses_existing_renderer_and_authoritative_angle(monkeypatch) -> None:
    calls: list[dict[str, object]] = []
    expected = go.Figure()

    def build(**kwargs):
        calls.append(kwargs)
        return expected

    monkeypatch.setattr(shear_stress_field, "build_shear_behaviour_figure", build)
    figure, animated = shear_stress_field.build_mcft_stress_field_figure(
        theta_v_deg=31.25,
        options={
            "show_stm_overlay": True,
            "show_stm_flow": False,
            "show_load_flow": False,
            "show_cracks": True,
            "show_stress_block": False,
        },
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


def test_one_shell_owns_four_views_and_teaching_is_outside_selection() -> None:
    source = (
        ROOT / "engineering_page_sections" / "shear_visualisation.py"
    ).read_text(encoding="utf-8")

    assert (
        'SHEAR_DIAGRAM_VIEWS = ("Side view", "Section", "Shear diagram", "MCFT")'
        in source
    )
    assert source.count("render_mcft_stress_field_diagram(") == 1
    assert source.count("_render_stress_field_teaching(runtime)") == 1
    assert source.index('scope_id="shear-diagram-navigation"') < source.index(
        "_render_stress_field_teaching(runtime)"
    )
    assert "pointer-events: none" in source
    assert "Show detailed MCFT breakdown" not in source


def test_mcft_display_options_keep_canonical_session_keys() -> None:
    fake = _FakeOptionsStreamlit()

    options = shear_stress_field.render_mcft_display_options(fake)

    assert fake.captions == ["MCFT diagram display options"]
    assert [key for _label, key, _value in fake.toggles] == [
        "shear_show_stm_overlay",
        "shear_show_stm_flow",
        "shear_show_load_flow",
        "shear_show_cracks",
        "shear_show_stress_block",
    ]
    assert options == {
        "show_load_flow": False,
        "show_cracks": True,
        "show_stress_block": False,
        "show_stm_overlay": False,
        "show_stm_flow": False,
    }


def test_mcft_options_are_directly_associated_with_diagram_not_teaching() -> None:
    visual_source = (
        ROOT / "engineering_page_sections" / "shear_visualisation.py"
    ).read_text(encoding="utf-8")
    teaching_source = (
        ROOT / "engineering_page_sections" / "shear_stress_field.py"
    ).read_text(encoding="utf-8")

    assert "_render_mcft_display_options(runtime)" in visual_source
    assert "with runtime.info_button(" in visual_source
    teaching_body = teaching_source.split("def render_stress_field_teaching", 1)[1]
    assert "render_mcft_display_options(" not in teaching_body


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
    assert (
        combined.count(
            'MCFT_STRESS_FIELD_CHART_KEY = "shear_behaviour_mcft_shell"'
        )
        == 1
    )
    assert combined.count('"shear_behaviour_mcft_shell"') == 1
