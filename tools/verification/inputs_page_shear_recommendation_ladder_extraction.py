"""Lock extraction of shear recommendation ladder-state generation."""

from __future__ import annotations

import ast
import importlib
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BRIDGE_PATH = ROOT / "inputs_page_app_contract_bridge.py"
MODULE_PATH = ROOT / "inputs_page_modules" / "recommendation_shear_ladder.py"
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
    node = _function_node(source, "_iter_shear_recommendation_ladder_states")
    body = _segment(source, node)
    line_count = node.end_lineno - node.lineno + 1
    assert line_count <= 8, f"bridge wrapper too large: {line_count} lines"
    assert "_bind_shear_recommendation_ladder_dependencies(globals())" in body
    assert "_iter_shear_recommendation_ladder_states_extracted(" in body


def _assert_module_owner() -> None:
    source = MODULE_PATH.read_text(encoding="utf-8")
    node = _function_node(source, "_iter_shear_recommendation_ladder_states")
    body = _segment(source, node)
    assert node.end_lineno - node.lineno + 1 >= 90
    assert "def bind_shear_recommendation_ladder_dependencies" in source
    assert "inputs_page_app_contract_bridge" not in source
    assert "import streamlit" not in source
    for token in (
        "spacing_looser",
        "spacing_tighter",
        "shear_activation",
        "no_ligs",
        "depth_up",
        "width_up",
        "material_fc",
        "GUIDANCE_GEOMETRY_TRIAL_DELTAS_MM",
        "REO_SPACINGS",
        "REO_BAR_DIAS",
    ):
        assert token in body, f"missing ladder token: {token}"


def _assert_runtime_delegate_and_binding() -> None:
    bridge = importlib.import_module("inputs_page_app_contract_bridge")
    module = importlib.import_module("inputs_page_modules.recommendation_shear_ladder")

    calls: list[tuple[dict, bool]] = []

    def fake_delegate(state: dict, *, conservative: bool) -> list[tuple[str, dict]]:
        calls.append((state, conservative))
        return [("sentinel", {"ok": True})]

    original = bridge._iter_shear_recommendation_ladder_states_extracted
    bridge._iter_shear_recommendation_ladder_states_extracted = fake_delegate
    try:
        state = {"D": 500.0, "s_lig": 150.0, "lig_legs": 2, "lig_d": 10}
        result = bridge._iter_shear_recommendation_ladder_states(state, conservative=True)
    finally:
        bridge._iter_shear_recommendation_ladder_states_extracted = original

    assert result == [("sentinel", {"ok": True})]
    assert calls == [(state, True)]
    assert module._geometry_lock_enabled is bridge._geometry_lock_enabled
    assert module._float_from_state is bridge._float_from_state
    assert module._int_from_state is bridge._int_from_state
    assert module._activation_shear_state is bridge._activation_shear_state
    assert module._make_auto_design_candidate_key is bridge._make_auto_design_candidate_key
    assert module._shear_state_eligible_for_no_links is bridge._shear_state_eligible_for_no_links


def main() -> None:
    _assert_bridge_wrapper()
    _assert_module_owner()
    _assert_runtime_delegate_and_binding()
    print("inputs_page_shear_recommendation_ladder_extraction: PASS")


if __name__ == "__main__":
    main()
