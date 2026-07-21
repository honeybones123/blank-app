"""Lock extraction of app-bridge shear evaluation."""

from __future__ import annotations

import ast
import importlib
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BRIDGE_PATH = ROOT / "inputs_page_app_contract_bridge.py"
MODULE_PATH = ROOT / "inputs_page_modules" / "app_bridge" / "shear_evaluation.py"
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


def _assert_bridge_wrapper() -> None:
    source = BRIDGE_PATH.read_text(encoding="utf-8")
    node = _function_node(source, "_evaluate_shear_with_state_for_app_bridge")
    body = _segment(source, node)
    line_count = node.end_lineno - node.lineno + 1
    assert line_count <= 12, f"bridge wrapper too large: {line_count} lines"
    assert "_bind_shear_evaluation_dependencies(globals())" in body
    assert "_evaluate_shear_with_state_for_app_bridge_extracted(" in body


def _assert_module_owner() -> None:
    source = MODULE_PATH.read_text(encoding="utf-8")
    node = _function_node(source, "_evaluate_shear_with_state_for_app_bridge")
    body = _segment(source, node)
    assert node.end_lineno - node.lineno + 1 >= 85
    assert "def bind_shear_evaluation_dependencies" in source
    assert "inputs_page_app_contract_bridge" not in source
    assert "import streamlit" not in source
    for token in (
        "ShearInputs",
        "run_shear_calc",
        "phi_Vu",
        "Vu_max_kN",
        "web_util",
        "lig_d",
        "lig_legs",
        "s_lig",
        "_uls_action_from_state_for_app_bridge",
    ):
        assert token in body, f"missing shear evaluation token: {token}"


def _assert_runtime_delegate_and_binding() -> None:
    bridge = importlib.import_module("inputs_page_app_contract_bridge")
    module = importlib.import_module("inputs_page_modules.app_bridge.shear_evaluation")

    calls: list[tuple[dict, dict | None, dict | None]] = []

    def fake_delegate(
        state: dict,
        *,
        bottom_updates: dict | None = None,
        shear_updates: dict | None = None,
    ) -> dict:
        calls.append((state, bottom_updates, shear_updates))
        return {"util": 0.5, "web_util": 0.6}

    original = bridge._evaluate_shear_with_state_for_app_bridge_extracted
    bridge._evaluate_shear_with_state_for_app_bridge_extracted = fake_delegate
    try:
        state = {"D": 500.0}
        bottom_updates = {"Ast_bot": 1200.0}
        shear_updates = {"s_lig": 150.0}
        result = bridge._evaluate_shear_with_state_for_app_bridge(
            state,
            bottom_updates=bottom_updates,
            shear_updates=shear_updates,
        )
    finally:
        bridge._evaluate_shear_with_state_for_app_bridge_extracted = original

    assert result == {"util": 0.5, "web_util": 0.6}
    assert calls == [(state, bottom_updates, shear_updates)]
    assert module._design_width_value_for_app_bridge is bridge._design_width_value_for_app_bridge
    assert module._effective_bottom_design_state_for_app_bridge is bridge._effective_bottom_design_state_for_app_bridge
    assert module._float_from_state is bridge._float_from_state
    assert module._uls_action_from_state_for_app_bridge is bridge._uls_action_from_state_for_app_bridge


def main() -> None:
    _assert_bridge_wrapper()
    _assert_module_owner()
    _assert_runtime_delegate_and_binding()
    print("inputs_page_app_bridge_shear_evaluation_extraction: PASS")


if __name__ == "__main__":
    main()
