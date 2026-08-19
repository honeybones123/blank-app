from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _render_expandable_step_node() -> ast.FunctionDef:
    path = ROOT / "step_ui.py"
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == "render_expandable_step":
            return node
    raise AssertionError("render_expandable_step not found")


def test_expandable_engineering_steps_are_fragment_scoped() -> None:
    node = _render_expandable_step_node()
    decorators = {ast.unparse(item) for item in node.decorator_list}
    assert "st.fragment" in decorators


def test_engineering_steps_keep_bodies_mounted_for_instant_toggle() -> None:
    source = (ROOT / "step_ui.py").read_text(encoding="utf-8")
    node = _render_expandable_step_node()
    fn_source = ast.get_source_segment(source, node) or ""

    assert "key=open_key" in fn_source
    assert 'on_change="ignore"' in fn_source
    assert "if not expander.open:" not in fn_source
