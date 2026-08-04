"""Structural lock for the five engineering result-page composition shells."""

from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]

SHELLS = {
    "sfd_bmd_page.py": ("design_page_runtime.py", "render_sfd_bmd_page"),
    "bending_page.py": ("bending_page_runtime.py", "render_bending"),
    "shear_page.py": ("shear_page_runtime.py", "render_shear"),
    "crack_page.py": ("crack_page_runtime.py", "render_crack_control"),
    "deflection.py": ("deflection_page_runtime.py", "render_deflection"),
}
SHELL_MODULES = {Path(path).stem for path in SHELLS}


def _imports(tree: ast.AST) -> set[str]:
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            found.add(node.module)
    return found


def _assert_shell(path: str, runtime_path: str, router_symbol: str) -> None:
    source = (ROOT / path).read_text(encoding="utf-8")
    tree = ast.parse(source, filename=path)
    lines = source.splitlines()
    assert len(lines) <= 250, (path, "shell_too_large", len(lines))
    assert "import streamlit" not in source, (path, "direct_streamlit_import")
    assert "render_timing_mark(" in source, (path, "missing_timing_boundary")
    assert "speed_profiled(" in source, (path, "missing_render_profile")

    imports = _imports(tree)
    assert Path(runtime_path).stem not in imports, (
        path,
        "runtime_must_remain_lazy",
        runtime_path,
    )

    runtime_source = (ROOT / runtime_path).read_text(encoding="utf-8")
    ast.parse(runtime_source, filename=runtime_path)
    assert "render_timing_mark(" in runtime_source, (
        runtime_path,
        "missing_runtime_section_timing",
    )
    if path == "crack_page.py":
        assert "def render_crack(" in runtime_source
    else:
        assert f"def {router_symbol}(" in runtime_source

    app_source = (ROOT / "app.py").read_text(encoding="utf-8")
    assert f'"{router_symbol}"' in app_source, (path, "router_symbol_missing")


def _assert_no_production_imports_from_shells() -> None:
    ignored_roots = {"tools", "tests", "artifacts", "Documents"}
    allowed_files = set(SHELLS) | {"app.py"}
    offenders: list[tuple[str, str]] = []
    for candidate in ROOT.rglob("*.py"):
        rel = candidate.relative_to(ROOT)
        if rel.parts and rel.parts[0] in ignored_roots:
            continue
        rel_posix = rel.as_posix()
        if rel_posix in allowed_files or "Elli" in candidate.name:
            continue
        try:
            tree = ast.parse(candidate.read_text(encoding="utf-8-sig"))
        except (OSError, SyntaxError, UnicodeDecodeError):
            continue
        for imported in _imports(tree):
            root_name = imported.split(".", 1)[0]
            if root_name in SHELL_MODULES:
                offenders.append((rel_posix, imported))
    assert not offenders, ("production_imports_page_shell", offenders)


def _assert_neutral_dependency_cutovers() -> None:
    checks = [
        ("deflection_core.py", "from deflection import"),
        ("deflection_checks_helpers.py", "from deflection import"),
        ("beam_diagram_publish.py", "from sfd_bmd_page import"),
        ("shear_diagrams.py", "from sfd_bmd_page import"),
        ("crack_page_runtime.py", "from bending_page import"),
        ("crack_page_runtime.py", "from bending_page_runtime import"),
    ]
    for path, forbidden in checks:
        source = (ROOT / path).read_text(encoding="utf-8")
        assert forbidden not in source, (path, "legacy_page_dependency", forbidden)


def main() -> int:
    for shell, (runtime, router_symbol) in SHELLS.items():
        _assert_shell(shell, runtime, router_symbol)
    _assert_no_production_imports_from_shells()
    _assert_neutral_dependency_cutovers()
    print("engineering_result_page_shells: PASS")
    for shell, (runtime, _) in SHELLS.items():
        line_count = len((ROOT / shell).read_text(encoding="utf-8").splitlines())
        print(f"- {shell}: {line_count} lines -> {runtime}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
