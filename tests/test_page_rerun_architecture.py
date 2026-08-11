from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _direct_rerun_calls(path: Path) -> list[int]:
    tree = ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))
    lines: list[int] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        if node.func.attr not in {"rerun", "experimental_rerun"}:
            continue
        owner = node.func.value
        if isinstance(owner, ast.Name) and owner.id in {"st", "st_module"}:
            lines.append(int(node.lineno))
    return sorted(lines)


def test_general_result_pages_are_fragment_scoped() -> None:
    source = (ROOT / "app.py").read_text(encoding="utf-8-sig")
    expected = {
        "start": "_render_start_page_fragment",
        "bending": "_render_bending_page_fragment",
        "shear": "_render_shear_page_fragment",
        "creep": "_render_creep_page_fragment",
        "shrinkage": "_render_shrinkage_page_fragment",
        "crack": "_render_crack_page_fragment",
        "deflection": "_render_deflection_page_fragment",
    }
    for slug, renderer in expected.items():
        assert f'"{slug}": (' in source
        assert f'"{slug}": (' in source and renderer in source
        assert f"def {renderer}():" in source


def test_global_header_actions_are_fragment_scoped() -> None:
    source = (ROOT / "app.py").read_text(encoding="utf-8-sig")
    assert "@st.fragment\ndef _render_header_actions(" in source
    assert "_render_header_actions(\n                user_id=user_id," in source


def test_result_pages_have_no_direct_app_rerun_authority() -> None:
    pages = (
        "bending_page_runtime.py",
        "shear_page_runtime.py",
        "creep.py",
        "shrinkage.py",
        "crack_page_runtime.py",
        "deflection_page_runtime.py",
    )
    offenders = {
        name: _direct_rerun_calls(ROOT / name)
        for name in pages
        if _direct_rerun_calls(ROOT / name)
    }
    assert offenders == {}


def test_direct_app_reruns_are_confined_to_shell_transition_owners() -> None:
    approved = {
        "app.py",  # project creation modal and authentication/shell transitions
        "start_page.py",  # explicit navigation to another page
        "state_and_helpers.py",  # create/reset beam workspace
        "inputs_page_modules/fragments.py",  # centralized scoped compatibility boundary
    }
    offenders: dict[str, list[int]] = {}
    for path in ROOT.rglob("*.py"):
        relative = path.relative_to(ROOT).as_posix()
        if relative.startswith(("tests/", "tools/", "packages/beamapp-inputs-v2/")):
            continue
        lines = _direct_rerun_calls(path)
        if lines and relative not in approved:
            offenders[relative] = lines
    assert offenders == {}


def test_removed_legacy_apply_path_cannot_reintroduce_full_page_rerun() -> None:
    source = (ROOT / "state_and_helpers.py").read_text(encoding="utf-8-sig")
    assert "def apply_auto_design_results(" not in source


def test_load_analysis_has_no_competing_scroll_restoration_authority() -> None:
    source = (ROOT / "design_page_runtime.py").read_text(encoding="utf-8-sig")
    assert "_install_design_scroll_preserver" not in source
    assert "beam_design_scroll_restore" not in source
    assert "__beamDesignScrollObserver" not in source
