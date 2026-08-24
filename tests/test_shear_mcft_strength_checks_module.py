from __future__ import annotations

from dataclasses import fields
from pathlib import Path

import pytest

from engineering_page_sections import shear_mcft_strength_checks as checks_ui
from engineering_page_sections.shear_checks_context import ShearCheckFamilyInput


ROOT = Path(__file__).resolve().parents[1]


def _view(mcft: dict[str, object] | None = None) -> checks_ui.ShearMcftStrengthView:
    evidence = ShearCheckFamilyInput(
        live_state={"b": 250.0},
        actions={"Vu": 120.0, "Tu": 0.0},
        results={"theta_v_deg": 31.0, "k_v": 0.2},
        published_results={"revision": "beam-7"},
        phi=0.75,
        duct_factor=0.0,
        use_general_kv=True,
        method="General epsilon-x method",
    )
    values: dict[str, object] = {
        field.name: 0.0 for field in fields(checks_ui.ShearMcftStrengthView)
    }
    values.update(
        evidence=evidence,
        eq_used="Equation (1)",
        kv_case="general MCFT",
        mcft=mcft or {"low_stirrup_ratio": False},
        shear_ok=True,
        shear_status="pass",
        use_general_kv=True,
        web_ok=True,
        web_status="pass",
    )
    return checks_ui.ShearMcftStrengthView(**values)


def test_mcft_view_detaches_its_display_mapping() -> None:
    source = {"low_stirrup_ratio": False}
    view = _view(source)

    source["low_stirrup_ratio"] = True
    assert view.mcft["low_stirrup_ratio"] is False
    with pytest.raises(TypeError):
        view.mcft["low_stirrup_ratio"] = True


def test_runtime_delegates_checks_four_to_nine_to_the_module() -> None:
    runtime_source = (ROOT / "shear_page_runtime.py").read_text(encoding="utf-8")
    module_source = (
        ROOT / "engineering_page_sections" / "shear_mcft_strength_checks.py"
    ).read_text(encoding="utf-8")
    teaching_source = (
        ROOT / "engineering_page_sections" / "shear_stress_field.py"
    ).read_text(encoding="utf-8")

    assert "render_shear_mcft_strength_checks(" in runtime_source
    assert "ShearMcftStrengthView(" in runtime_source
    for check_number in range(4, 10):
        step_id = f'step_id="shear_check{check_number}"'
        assert step_id not in runtime_source
        assert step_id in module_source
    assert "def _render_animated_plotly_figure" not in runtime_source
    assert "def _render_shear_behaviour_diagrams" not in runtime_source
    assert "def _render_principal_stress_directions_explainer" not in runtime_source
    assert "def _render_animated_plotly_figure" in module_source
    assert "def _render_shear_behaviour_diagrams" not in module_source
    assert "def _render_principal_stress_directions_explainer" not in module_source
    assert "def render_mcft_stress_field_diagram" in teaching_source
    assert "def render_stress_field_teaching" in teaching_source
    assert "Show detailed MCFT breakdown" not in module_source
    assert "Show detailed MCFT breakdown" not in teaching_source
    assert "build_shear_calc_bundle_from_state" not in module_source
    assert "build_live_canonical_shear_state" not in module_source
