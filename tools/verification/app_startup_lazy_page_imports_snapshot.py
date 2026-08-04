"""Verify non-active page modules are lazy-loaded by app.py.

This is a startup/smoothness guard. The Inputs route may import its own shell,
but heavyweight non-Inputs pages should not be imported at app module import
time because that cost is paid before the first Inputs paint.
"""

from __future__ import annotations

import ast
import json
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
APP_PATH = ROOT / "app.py"

HEAVY_PAGE_MODULES = {
    "bending_page",
    "shear_page",
    "creep",
    "shrinkage",
    "deflection",
    "crack_page",
    "sfd_bmd_page",
}

EXPECTED_WRAPPERS = {
    "design": "_render_design_page",
    "bending": "_render_bending_page",
    "shear": "_render_shear_page",
    "creep": "_render_creep_page",
    "shrinkage": "_render_shrinkage_page",
    "crack": "_render_crack_page",
    "deflection": "_render_deflection_page",
}


def _line_range(node: ast.AST) -> str:
    return f"{getattr(node, 'lineno', '?')}-{getattr(node, 'end_lineno', getattr(node, 'lineno', '?'))}"


def _literal_pages_assign(tree: ast.AST) -> ast.Assign | None:
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if isinstance(target, ast.Name) and target.id == "PAGES":
                return node
    return None


def _pages_renderers(assign: ast.Assign | None) -> dict[str, str]:
    if assign is None or not isinstance(assign.value, ast.Dict):
        return {}
    renderers: dict[str, str] = {}
    for key_node, value_node in zip(assign.value.keys, assign.value.values):
        if not isinstance(key_node, ast.Constant) or not isinstance(key_node.value, str):
            continue
        if not isinstance(value_node, ast.Tuple) or len(value_node.elts) < 2:
            continue
        renderer = value_node.elts[1]
        if isinstance(renderer, ast.Name):
            renderers[key_node.value] = renderer.id
        elif isinstance(renderer, ast.Attribute):
            renderers[key_node.value] = ast.unparse(renderer)
        else:
            renderers[key_node.value] = ast.unparse(renderer)
    return renderers


def main() -> int:
    source = APP_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)

    eager_imports: list[dict[str, object]] = []
    for node in tree.body:
        if isinstance(node, ast.Import):
            for alias in node.names:
                root_name = alias.name.split(".", 1)[0]
                if root_name in HEAVY_PAGE_MODULES:
                    eager_imports.append(
                        {"module": alias.name, "line": node.lineno, "kind": "import"}
                    )
        elif isinstance(node, ast.ImportFrom) and node.module:
            root_name = node.module.split(".", 1)[0]
            if root_name in HEAVY_PAGE_MODULES:
                eager_imports.append(
                    {"module": node.module, "line": node.lineno, "kind": "from_import"}
                )

    lazy_helper = next(
        (
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef) and node.name == "_render_lazy_page"
        ),
        None,
    )
    pages_assign = _literal_pages_assign(tree)
    renderers = _pages_renderers(pages_assign)

    failures: list[str] = []
    if eager_imports:
        failures.append("heavy_page_modules_imported_at_app_startup")
    if lazy_helper is None:
        failures.append("lazy_page_render_helper_missing")
    for slug, wrapper in EXPECTED_WRAPPERS.items():
        if renderers.get(slug) != wrapper:
            failures.append(f"page_registry_not_lazy:{slug}:{renderers.get(slug)!r}")

    payload = {
        "verifier": "app_startup_lazy_page_imports_snapshot",
        "status": "PASS" if not failures else "FAIL",
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "app_path": str(APP_PATH),
        "heavy_page_modules": sorted(HEAVY_PAGE_MODULES),
        "eager_imports": eager_imports,
        "lazy_helper_lines": _line_range(lazy_helper) if lazy_helper is not None else None,
        "pages_assignment_lines": _line_range(pages_assign) if pages_assign is not None else None,
        "page_renderers": renderers,
        "failures": failures,
        "startup_rule": (
            "app.py must not import non-active page modules at module import time; "
            "PAGES must route through lazy wrapper functions."
        ),
    }

    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    json_path = ARTIFACT_DIR / f"app_startup_lazy_page_imports_snapshot_{stamp}.json"
    md_path = AUDIT_DIR / f"app_startup_lazy_page_imports_snapshot_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    md_path.write_text(
        "\n".join(
            [
                "# App Startup Lazy Page Imports Snapshot",
                "",
                f"Status: {payload['status']}",
                "",
                "## Rule",
                str(payload["startup_rule"]),
                "",
                "## Eager Imports",
                json.dumps(eager_imports, indent=2, sort_keys=True),
                "",
                "## Page Registry",
                json.dumps(renderers, indent=2, sort_keys=True),
                "",
                "## Failures",
                json.dumps(failures, indent=2, sort_keys=True),
            ]
        ),
        encoding="utf-8",
    )
    print(f"app_startup_lazy_page_imports_snapshot {payload['status']}")
    print(f"json: {json_path}")
    print(f"report: {md_path}")
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
