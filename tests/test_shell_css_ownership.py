from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_shared_shell_css_is_emitted_once_inside_main_render_cycle() -> None:
    path = ROOT / "app.py"
    source = path.read_text(encoding="utf-8-sig")
    tree = ast.parse(source, filename=str(path))

    main = next(
        node for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "main"
    )
    calls = [
        node for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "_apply_sharp_embed_css"
    ]
    assert len(calls) == 1
    assert any(call in set(ast.walk(main)) for call in calls)

    main_source = source[source.index("def main():"):]
    assert main_source.index("_apply_sharp_embed_css()") < main_source.index(
        "_apply_normal_user_page_zoom_css()"
    )
    assert main_source.index("_apply_normal_user_page_zoom_css()") < main_source.index(
        "_render_project_header_compact()"
    )


def test_start_page_cannot_own_or_override_application_shell_width() -> None:
    source = (ROOT / "start_page.py").read_text(encoding="utf-8-sig")

    assert 'stMainBlockContainer' not in source
    assert '.block-container' not in source
    assert 'max-width:' not in source


def test_application_shell_remains_full_width() -> None:
    source = (ROOT / "app.py").read_text(encoding="utf-8-sig")
    start = source.index("def _apply_sharp_embed_css()")
    end = source.index("\n\nfrom widgets_helpers import (", start)
    shell_css = source[start:end]

    assert 'width: calc(100% - 2rem) !important;' in shell_css
    assert 'max-width: none !important;' in shell_css
