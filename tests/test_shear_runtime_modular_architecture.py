from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_runtime_is_an_orchestrator_not_a_second_check_ui() -> None:
    source = (ROOT / "shear_page_runtime.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    top_level_functions = {
        node.name for node in tree.body if isinstance(node, ast.FunctionDef)
    }

    assert top_level_functions == {
        "_build_shear_sfd_bmd_figure",
        "_safe_image",
        "compute_shear_results",
        "render_shear",
    }
    for dead_name in (
        "build_reo_circles_from_state",
        "_safe_step_diagram",
        "render_shear_step_insight",
        "render_shear_mcft_block",
        "render_shear_steel_and_spacing_block",
    ):
        assert f"def {dead_name}(" not in source
    for check_number in range(1, 11):
        assert f'step_id="shear_check{check_number}"' not in source


def test_runtime_delegates_each_visible_page_region_once() -> None:
    source = (ROOT / "shear_page_runtime.py").read_text(encoding="utf-8")

    delegates = (
        "render_shear_summary(",
        "render_shear_inputs(",
        "render_shear_visualisation_block(",
        "render_shear_torsion_dimensions_checks(",
        "render_shear_mcft_strength_checks(",
        "render_shear_reinforcement_checks(",
        "build_shear_report(",
    )
    for delegate in delegates:
        assert source.count(delegate) == 1
    assert len(source.splitlines()) < 900
