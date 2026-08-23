from __future__ import annotations

import ast
from pathlib import Path

import pytest

from engineering_page_sections.shear_page_context import (
    build_shear_page_snapshot,
)


ROOT = Path(__file__).resolve().parents[1]


def _snapshot(*, actions_mode: str = "manual"):
    return build_shear_page_snapshot(
        engineering_state={"b": 250.0, "D": 300.0, "Vu": 120.0},
        check_pack={"rows": ("row",), "summary_phiVu_kN": 180.0},
        published_results={"phi_Vu_cap": 180.0, "Vu_utilisation": 2.0 / 3.0},
        section_layout={"shape_name": "RECT"},
        actions_mode=actions_mode,
        show_mcft_breakdown=True,
    )


def test_page_snapshot_preserves_revision_matched_presentation_values() -> None:
    snapshot = _snapshot(actions_mode="design")

    assert snapshot.engineering_state["b"] == pytest.approx(250.0)
    assert snapshot.check_pack["summary_phiVu_kN"] == pytest.approx(180.0)
    assert snapshot.published_results["Vu_utilisation"] == pytest.approx(2.0 / 3.0)
    assert snapshot.section_layout["shape_name"] == "RECT"
    assert snapshot.view.is_design_driven is True
    assert snapshot.view.show_mcft_breakdown is True


def test_snapshot_mappings_are_detached_and_read_only() -> None:
    engineering = {"b": 250.0}
    checks = {"summary_phiVu_kN": 180.0}
    published = {"phi_Vu_cap": 180.0}
    snapshot = build_shear_page_snapshot(
        engineering_state=engineering,
        check_pack=checks,
        published_results=published,
        section_layout=None,
        actions_mode="manual",
        show_mcft_breakdown=False,
    )

    engineering["b"] = 999.0
    checks["summary_phiVu_kN"] = 999.0
    published["phi_Vu_cap"] = 999.0

    assert snapshot.engineering_state["b"] == pytest.approx(250.0)
    assert snapshot.check_pack["summary_phiVu_kN"] == pytest.approx(180.0)
    assert snapshot.published_results["phi_Vu_cap"] == pytest.approx(180.0)
    with pytest.raises(TypeError):
        snapshot.engineering_state["b"] = 300.0


def test_invalid_action_mode_is_a_presentation_fallback_only() -> None:
    snapshot = _snapshot(actions_mode="stale-mode")

    assert snapshot.view.actions_mode == "manual"
    assert snapshot.view.is_design_driven is False


def test_context_contract_has_no_streamlit_or_solver_dependency() -> None:
    source = (
        ROOT / "engineering_page_sections" / "shear_page_context.py"
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
    assert "shear_core" not in imported_roots
    assert "shear_calculation_runtime" not in imported_roots
    assert "calculations" not in imported_roots


def test_runtime_routes_summary_authority_through_page_snapshot() -> None:
    source = (ROOT / "shear_page_runtime.py").read_text(encoding="utf-8")

    assert "shear_page_snapshot = build_shear_page_snapshot(" in source
    assert "render_shear_summary(\n        shear_page_snapshot," in source
    assert "page_snapshot=shear_page_snapshot" in source

    inputs_source = (
        ROOT / "engineering_page_sections" / "shear_inputs.py"
    ).read_text(encoding="utf-8")
    assert 'page_snapshot.view.actions_mode == "design"' in inputs_source
