"""Lock extraction of Design Guide executor-contract sanitization."""

from __future__ import annotations

import ast
import importlib
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BRIDGE_PATH = ROOT / "inputs_page_app_contract_bridge.py"
MODULE_PATH = ROOT / "inputs_page_modules" / "design_guide" / "executor_contract_sanitizer.py"
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
    node = _function_node(source, "_sanitize_guidance_items_for_executor_contract")
    body = _segment(source, node)
    line_count = node.end_lineno - node.lineno + 1
    assert line_count <= 13, f"bridge wrapper too large: {line_count} lines"
    assert "_bind_efficiency_executor_promotion_dependencies(globals())" in body
    assert "_bind_executor_contract_sanitizer_dependencies(globals())" in body
    assert "_sanitize_guidance_items_for_executor_contract_extracted(" in body


def _assert_module_owner() -> None:
    source = MODULE_PATH.read_text(encoding="utf-8")
    node = _function_node(source, "_sanitize_guidance_items_for_executor_contract")
    body = _segment(source, node)
    assert node.end_lineno - node.lineno + 1 >= 90
    assert "def bind_executor_contract_sanitizer_dependencies" in source
    assert "inputs_page_app_contract_bridge" not in source
    assert "import streamlit" not in source
    for token in (
        "design_guide_sanitize_final_acceptance_probe",
        "candidate_final_accepted_state_unresolved_low_util",
        "executor_contract_primary_blocked_reason",
        "design_guide_executor_backed_promotion_debug",
        "_guidance_executor_actionability_contract",
        "_try_promote_efficiency_item_to_executor_backed_candidate",
        "_guidance_item_as_advisory",
        "_post_click_accepted_green_audit",
    ):
        assert token in body, f"missing sanitizer contract token: {token}"


def _assert_runtime_delegate_and_binding() -> None:
    bridge = importlib.import_module("inputs_page_app_contract_bridge")
    module = importlib.import_module("inputs_page_modules.design_guide.executor_contract_sanitizer")

    calls: list[tuple[list[dict] | None, dict, dict | None]] = []

    def fake_delegate(
        guidance_items: list[dict] | None,
        *,
        state: dict,
        debug_sink: dict | None = None,
    ) -> list[dict]:
        calls.append((guidance_items, state, debug_sink))
        return [{"sentinel": True}]

    original = bridge._sanitize_guidance_items_for_executor_contract_extracted
    bridge._sanitize_guidance_items_for_executor_contract_extracted = fake_delegate
    try:
        guidance_items = [{"action_type": "apply_resolved_candidate", "title_main": "Probe"}]
        state = {"D": 500.0}
        debug_sink: dict = {}
        result = bridge._sanitize_guidance_items_for_executor_contract(
            guidance_items,
            state=state,
            debug_sink=debug_sink,
        )
    finally:
        bridge._sanitize_guidance_items_for_executor_contract_extracted = original

    assert result == [{"sentinel": True}]
    assert calls == [(guidance_items, state, debug_sink)]
    assert module._guidance_executor_actionability_contract is bridge._guidance_executor_actionability_contract
    assert module._guidance_item_as_advisory is bridge._guidance_item_as_advisory
    assert module._post_click_accepted_green_audit is bridge._post_click_accepted_green_audit
    assert (
        module._try_promote_efficiency_item_to_executor_backed_candidate
        is bridge._try_promote_efficiency_item_to_executor_backed_candidate
    )


def main() -> None:
    _assert_bridge_wrapper()
    _assert_module_owner()
    _assert_runtime_delegate_and_binding()
    print("inputs_page_executor_contract_sanitizer_extraction: PASS")


if __name__ == "__main__":
    main()
