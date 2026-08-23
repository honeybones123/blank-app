from __future__ import annotations

import ast
from pathlib import Path

from engineering_page_sections import shear_inputs
from engineering_page_sections.compact_check_inputs import InputSource


ROOT = Path(__file__).resolve().parents[1]


class _FakeStreamlit:
    def __init__(self):
        self.session_state: dict[str, object] = {}


def test_input_panel_config_preserves_card_order_summaries_and_source(monkeypatch) -> None:
    values = {
        "sec_shape": "T",
        "b": 300.0,
        "D": 600.0,
        "fc": 40.0,
        "uls_Vstar": 125.0,
        "Tu_star": 18.0,
        "P_star": -50.0,
        "lig_d": 12.0,
        "lig_legs": 4,
        "s_lig": 175.0,
        "k_v_method": "General εₓ-based (Cl. 8.2.4.2)",
    }

    def fake_get_param(key, default=None):
        return values.get(key, default)

    monkeypatch.setattr(shear_inputs, "get_param", fake_get_param)
    monkeypatch.setattr(shear_inputs, "uses_load_analysis_actions", lambda _state: True)

    config = shear_inputs.build_shear_input_panel_config(
        st_module=_FakeStreamlit()
    )

    assert [category.category_id for category in config.categories] == [
        "design_actions",
        "section_material",
        "shear_reinforcement",
        "method_parameters",
    ]
    assert config.categories[0].source is InputSource.LOAD_ANALYSIS
    assert "V* 125.0 kN" in config.categories[0].summary
    assert "N* -50.0 kN" in config.categories[0].summary
    assert "T* 18.0 kNm" in config.categories[0].summary
    assert "300 × 600 mm" in config.categories[1].summary
    assert "T" in config.categories[1].summary
    assert "N12 · 4 legs · 175 mm spacing" == config.categories[2].summary
    assert config.categories[3].summary == values["k_v_method"]


def test_input_module_owns_existing_widget_keys_and_no_capacity_solver() -> None:
    source = (
        ROOT / "engineering_page_sections" / "shear_inputs.py"
    ).read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported_modules = {
        str(node.module or "")
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
    }

    for key in (
        '"inputs_load_Vstar_proxy"',
        '"shear_Tu_star"',
        '"shear_phi_shear"',
        '"shear_sec_shape"',
        '"shear_lig_d"',
        '"shear_lig_legs"',
        '"shear_s_lig"',
        '"shear_n_ducts"',
        '"shear_duct_dia"',
        '"shear_k_d_option"',
        '"shear_d_g"',
        '"shear_k_v_method"',
    ):
        assert key in source

    assert "shear_calculation_runtime" not in imported_modules
    assert "shear_core" not in imported_modules
    assert "build_shear_calc_bundle_from_state" not in source


def test_runtime_delegates_inputs_before_authoritative_bundle_and_visualisation() -> None:
    source = (ROOT / "shear_page_runtime.py").read_text(encoding="utf-8")

    inputs = source.index("    render_shear_inputs(")
    divider = source.index("page_divider()", inputs)
    bundle = source.index(
        "    shear_bundle = build_shear_calc_bundle_from_state(st.session_state)",
        inputs,
    )
    visualisation = source.index("    shear_page_shell.render_visualisation(")

    assert inputs < divider < bundle < visualisation
    assert "compact_check_input_regions(st, _shear_input_config)" not in source
    assert 'number_row("Design shear V* (kN)"' not in source
