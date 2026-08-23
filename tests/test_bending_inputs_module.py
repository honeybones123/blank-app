from __future__ import annotations

import ast
from pathlib import Path

from engineering_page_sections.bending_inputs import (
    build_bending_input_panel_config,
)
from engineering_page_sections.compact_check_inputs import InputSource


ROOT = Path(__file__).resolve().parents[1]


def _state() -> dict[str, object]:
    return {
        "sec_shape": "RECT",
        "b": 250.0,
        "D": 300.0,
        "fc": 40.0,
        "P_star": 0.0,
        "bot_row_count": 1,
        "bot_row_1_mode": "Count",
        "bot_row_1_bars": 3,
        "bot_row_1_dia": 10,
        "top_row_count": 1,
        "top_row_1_mode": "Count",
        "top_row_1_bars": 2,
        "top_row_1_dia": 10,
    }


def test_input_config_preserves_existing_card_order_text_and_icons() -> None:
    config = build_bending_input_panel_config(
        engineering_state=_state(),
        mu_pos_star_kNm=20.0,
        mu_neg_star_kNm=10.0,
        load_analysis_actions=False,
    )

    assert config.page_slug == "bending"
    assert config.mount_closed_bodies is True
    assert tuple(category.label for category in config.categories) == (
        "Design actions",
        "Section & material",
        "Reinforcement",
    )
    assert tuple(category.icon for category in config.categories) == ("↧", "▣", "●")
    assert "M* 20.0 kNm" in config.categories[0].summary
    assert "250 × 300 mm" in config.categories[1].summary
    assert "RECT" in config.categories[1].summary
    assert "Bottom 3-N10" in config.categories[2].summary
    assert "Top 2-N10" in config.categories[2].summary


def test_input_config_preserves_action_source_ownership() -> None:
    beam_inputs = build_bending_input_panel_config(
        engineering_state=_state(),
        mu_pos_star_kNm=0.0,
        mu_neg_star_kNm=0.0,
        load_analysis_actions=False,
    )
    load_analysis = build_bending_input_panel_config(
        engineering_state=_state(),
        mu_pos_star_kNm=0.0,
        mu_neg_star_kNm=0.0,
        load_analysis_actions=True,
    )

    assert beam_inputs.categories[0].source == InputSource.BEAM_INPUTS
    assert load_analysis.categories[0].source == InputSource.LOAD_ANALYSIS


def test_input_config_uses_larger_absolute_active_moment() -> None:
    config = build_bending_input_panel_config(
        engineering_state=_state(),
        mu_pos_star_kNm=12.0,
        mu_neg_star_kNm=35.0,
        load_analysis_actions=False,
    )

    assert "M* 35.0 kNm" in config.categories[0].summary


def test_input_config_builder_has_no_solver_or_global_session_dependency() -> None:
    source = (
        ROOT / "engineering_page_sections" / "bending_inputs.py"
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

    assert "streamlit" not in imported_roots
    assert "bending_core" not in imported_roots
    assert "calculations" not in imported_roots
    builder = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef)
        and node.name == "build_bending_input_panel_config"
    )
    builder_source = ast.get_source_segment(source, builder) or ""
    assert "st.session_state" not in builder_source


def test_runtime_delegates_the_complete_input_region_to_the_shared_module() -> None:
    source = (ROOT / "bending_page_runtime.py").read_text(encoding="utf-8")

    assert "render_bending_inputs(" in source
    assert "CheckInputPanelConfig(" not in source
    assert "compact_check_input_regions(" not in source
    assert "number_row(" not in source


def test_input_module_retains_existing_widget_keys_and_state_gateways() -> None:
    source = (
        ROOT / "engineering_page_sections" / "bending_inputs.py"
    ).read_text(encoding="utf-8")

    for widget_key in (
        "bending_P_star",
        "bending_phi_b",
        "bending_sec_shape",
        "bending_D",
        "bending_L",
        "bending_fc",
        "bending_fsy",
    ):
        assert widget_key in source
    assert 'cover_key = f"bending_cover_{face}"' in source
    assert "save_proxies_to_active_set()" in source
    assert "load_proxies_from_active_set()" in source
    assert "recalc_derived_values()" in source
    assert "update_results()" in source
