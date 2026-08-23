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
    assert "st.session_state" not in source


def test_runtime_uses_shared_bending_input_config_builder() -> None:
    source = (ROOT / "bending_page_runtime.py").read_text(encoding="utf-8")

    assert "_bending_input_config = build_bending_input_panel_config(" in source
    assert "CheckInputPanelConfig(" not in source
