"""Lock extraction of auto-design rescue-mode entry gate."""

from __future__ import annotations

import ast
import importlib
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BRIDGE_PATH = ROOT / "inputs_page_app_contract_bridge.py"
MODULE_PATH = ROOT / "inputs_page_modules" / "app_bridge" / "rescue_mode_gate.py"
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
    node = _function_node(source, "_rescue_mode_should_enter")
    body = _segment(source, node)
    line_count = node.end_lineno - node.lineno + 1
    assert line_count <= 22, f"bridge wrapper too large: {line_count} lines"
    assert "_bind_rescue_mode_gate_dependencies(globals())" in body
    assert "_rescue_mode_should_enter_extracted(" in body


def _assert_module_owner() -> None:
    source = MODULE_PATH.read_text(encoding="utf-8")
    node = _function_node(source, "_rescue_mode_should_enter")
    body = _segment(source, node)
    assert node.end_lineno - node.lineno + 1 >= 85
    assert "def bind_rescue_mode_gate_dependencies" in source
    assert "inputs_page_app_contract_bridge" not in source
    assert "import streamlit" not in source
    for token in (
        "non_rectangular_section",
        "initial_state_already_passing",
        "normal_one_click_best_available_still_far_from_band",
        "normal_one_click_no_direct_path_from_implausible_seed",
        "normal_one_click_stopped_outside_practical_neighborhood",
        "normal_one_click_keep_control",
        "both_fail_meaningfully",
        "_rescue_mode_current_beam_plausible",
    ):
        assert token in body, f"missing rescue gate token: {token}"


def _assert_runtime_delegate_and_binding() -> None:
    bridge = importlib.import_module("inputs_page_app_contract_bridge")
    module = importlib.import_module("inputs_page_modules.app_bridge.rescue_mode_gate")

    calls: list[dict] = []

    def fake_delegate(**kwargs):
        calls.append(dict(kwargs))
        return (True, "sentinel", "bending", "high", {"ok": True})

    original = bridge._rescue_mode_should_enter_extracted
    bridge._rescue_mode_should_enter_extracted = fake_delegate
    try:
        result = bridge._rescue_mode_should_enter(
            state={"section_shape": "RECT"},
            init_eval={"overview": {"all_key_pass": False}},
            final_eval={"overview": {}},
            final_pass=False,
            final_updates={},
            stop_reason="no_actionable_candidates",
            mode_config={"target_util_min": 0.8},
        )
    finally:
        bridge._rescue_mode_should_enter_extracted = original

    assert result == (True, "sentinel", "bending", "high", {"ok": True})
    assert calls and calls[0]["stop_reason"] == "no_actionable_candidates"
    assert module._candidate_objective_util is bridge._candidate_objective_util
    assert module._rescue_mode_both_domains_fail_meanfully is bridge._rescue_mode_both_domains_fail_meanfully
    assert module._rescue_mode_choose_family is bridge._rescue_mode_choose_family
    assert module._rescue_mode_choose_tier is bridge._rescue_mode_choose_tier
    assert module._rescue_mode_current_beam_plausible is bridge._rescue_mode_current_beam_plausible


def main() -> None:
    _assert_bridge_wrapper()
    _assert_module_owner()
    _assert_runtime_delegate_and_binding()
    print("inputs_page_rescue_mode_gate_extraction: PASS")


if __name__ == "__main__":
    main()
