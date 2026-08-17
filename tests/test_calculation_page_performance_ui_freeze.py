from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_repository_instructions_make_performance_ui_freeze_explicit() -> None:
    instructions = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    contract = (ROOT / "ARCHITECTURE_CONTRACT.md").read_text(encoding="utf-8")
    normalized_contract = " ".join(contract.split())

    assert "## Calculation-Page Performance UI Freeze" in instructions
    assert "must not change any visible UI or formatting" in instructions
    assert "### 9.1 Calculation-page presentation freeze" in contract
    assert "has no authority to change **what** the user sees" in normalized_contract
    assert "separately authorised product change" in contract


def test_page_performance_registry_has_no_presentation_or_state_authority() -> None:
    path = ROOT / "application" / "page_module_registry.py"
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))

    imported_roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_roots.update(alias.name.split(".", 1)[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_roots.add(node.module.split(".", 1)[0])

    assert "streamlit" not in imported_roots
    assert "widgets_helpers" not in imported_roots
    assert "inputs_page" not in imported_roots
    assert "st." not in source
    assert "session_state" not in source
    assert "<style" not in source.lower()
    assert "unsafe_allow_html" not in source


def test_performance_registry_only_delegates_to_existing_page_renderers() -> None:
    source = (
        ROOT / "application" / "page_module_registry.py"
    ).read_text(encoding="utf-8")

    assert "importlib.import_module(module_name)" in source
    assert "return renderer()" in source
    assert "CALCULATION_PAGE_MODULES" in source
    for slug in ("bending", "shear", "creep", "shrinkage", "crack", "deflection"):
        assert f'"{slug}": PageModuleSpec(' in source


def test_bending_uses_one_canonical_calcbox_renderer() -> None:
    """Performance work cannot fork calc-card markup/CSS/state ownership."""

    bending_shell = (ROOT / "bending_page.py").read_text(encoding="utf-8")
    bending_tabs = (ROOT / "bending_tabs.py").read_text(encoding="utf-8-sig")
    canonical = (ROOT / "widgets_helpers.py").read_text(encoding="utf-8-sig")

    assert "install_bending_hybrid_calcbox_runtime" not in bending_shell
    assert "_install_presentation_performance_policy" not in bending_shell
    assert not (ROOT / "engineering_page_sections" / "calcbox_performance.py").exists()
    assert "step_expander_calcbox" in bending_tabs
    assert "def step_expander_calcbox(" in canonical
    assert "apply_step_summary_expander_css()" in canonical
    assert "span class='{status_class}'" in canonical
