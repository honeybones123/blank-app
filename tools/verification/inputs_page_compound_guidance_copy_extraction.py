"""Lock extraction of compound Design Guide title/reasoning copy."""

from __future__ import annotations

import ast
import importlib
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BRIDGE_PATH = ROOT / "inputs_page_app_contract_bridge.py"
MODULE_PATH = ROOT / "inputs_page_modules" / "design_guide" / "compound_guidance_copy.py"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _function_node(source: str, name: str) -> ast.FunctionDef:
    module = ast.parse(source)
    for node in module.body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    raise AssertionError(f"{name} not found")


def _segment(source: str, node: ast.FunctionDef) -> str:
    lines = source.splitlines()
    return "\n".join(lines[node.lineno - 1 : node.end_lineno])


def _assert_bridge_wrappers() -> None:
    source = BRIDGE_PATH.read_text(encoding="utf-8")
    geometry = _function_node(source, "_compound_geometry_deltas")
    copy = _function_node(source, "_compound_guidance_title_reasoning_why")
    geometry_body = _segment(source, geometry)
    copy_body = _segment(source, copy)
    assert geometry.end_lineno - geometry.lineno + 1 <= 4
    assert copy.end_lineno - copy.lineno + 1 <= 14
    assert "_bind_compound_guidance_copy_dependencies(globals())" in geometry_body
    assert "_compound_geometry_deltas_extracted(" in geometry_body
    assert "_bind_compound_guidance_copy_dependencies(globals())" in copy_body
    assert "_compound_guidance_title_reasoning_why_extracted(" in copy_body


def _assert_module_owner() -> None:
    source = MODULE_PATH.read_text(encoding="utf-8")
    geometry = _function_node(source, "_compound_geometry_deltas")
    copy = _function_node(source, "_compound_guidance_title_reasoning_why")
    copy_body = _segment(source, copy)
    assert geometry.end_lineno - geometry.lineno + 1 >= 10
    assert copy.end_lineno - copy.lineno + 1 >= 85
    assert "def bind_compound_guidance_copy_dependencies" in source
    assert "inputs_page_app_contract_bridge" not in source
    assert "import streamlit" not in source
    for token in (
        "Increase section size, bottom reinforcement, and shear reinforcement",
        "Increase depth, width, and bottom reinforcement",
        "Increase depth and bottom reinforcement",
        "Increase width and bottom reinforcement",
        "Adjust section and bottom reinforcement",
        "Reduce shear links and adjust bottom reinforcement",
        "Adjust section geometry and shear reinforcement",
        "Apply combined strengthening update",
        "Reduce section size and rebalance bottom reinforcement",
        "Reduce shear links and trim bottom reinforcement",
        "Tighten geometry and shear reinforcement",
        "Apply coordinated efficiency update",
        "Why:",
    ):
        assert token in copy_body, f"missing visible copy token: {token}"


def _assert_runtime_delegate_and_binding() -> None:
    bridge = importlib.import_module("inputs_page_app_contract_bridge")
    module = importlib.import_module("inputs_page_modules.design_guide.compound_guidance_copy")

    calls: list[tuple[dict, dict, list[str], bool]] = []

    def fake_copy(state: dict, updates: dict, subfamilies: list[str], *, strengthening: bool):
        calls.append((state, updates, subfamilies, strengthening))
        return ("sentinel title", "Why: sentinel", "sentinel")

    original = bridge._compound_guidance_title_reasoning_why_extracted
    bridge._compound_guidance_title_reasoning_why_extracted = fake_copy
    try:
        state = {"D": 500.0, "b": 300.0}
        updates = {"D": 550.0}
        subfamilies = ["geometry", "bottom_reo"]
        result = bridge._compound_guidance_title_reasoning_why(
            state,
            updates,
            subfamilies,
            strengthening=True,
        )
    finally:
        bridge._compound_guidance_title_reasoning_why_extracted = original

    assert result == ("sentinel title", "Why: sentinel", "sentinel")
    assert calls == [(state, updates, subfamilies, True)]
    bridge._compound_geometry_deltas({"D": 500.0, "b": 300.0}, {"D": 550.0})
    assert module._guidance_state_snapshot is bridge._guidance_state_snapshot
    assert module._float_from_state is bridge._float_from_state
    assert module._resolve_geometry_width_context is bridge._resolve_geometry_width_context
    assert module._design_width_value is bridge._design_width_value


def main() -> None:
    _assert_bridge_wrappers()
    _assert_module_owner()
    _assert_runtime_delegate_and_binding()
    print("inputs_page_compound_guidance_copy_extraction: PASS")


if __name__ == "__main__":
    main()
