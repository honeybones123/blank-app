"""Lock extraction of guidance item resolved-candidate promotion."""

from __future__ import annotations

import ast
import importlib
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BRIDGE_PATH = ROOT / "inputs_page_app_contract_bridge.py"
MODULE_PATH = ROOT / "inputs_page_modules" / "design_guide" / "resolved_candidate_guidance_item.py"
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
    node = _function_node(source, "_promote_guidance_item_to_resolved_candidate")
    body = _segment(source, node)
    assert node.end_lineno - node.lineno + 1 <= 12
    assert "_bind_resolved_candidate_guidance_item_dependencies(globals())" in body
    assert "_promote_guidance_item_to_resolved_candidate_extracted(" in body


def _assert_module_owner() -> None:
    source = MODULE_PATH.read_text(encoding="utf-8")
    node = _function_node(source, "_promote_guidance_item_to_resolved_candidate")
    body = _segment(source, node)
    assert node.end_lineno - node.lineno + 1 >= 80
    assert "def bind_resolved_candidate_guidance_item_dependencies" in source
    assert "inputs_page_app_contract_bridge" not in source
    assert "import streamlit" not in source
    for token in (
        "apply_resolved_candidate",
        "resolved_candidate_updates",
        "resolved_candidate_label",
        "resolved_candidate_action_type",
        "resolved_candidate_post_util",
        "resolved_candidate_reaches_target_band",
        "has_resolved_candidate_payload",
        "failure_coverage",
        "covers_all_current_failures",
        "covered_fail_keys",
        "remaining_fail_keys",
    ):
        assert token in body, f"missing promotion token: {token}"


def _assert_runtime_delegate_and_binding() -> None:
    bridge = importlib.import_module("inputs_page_app_contract_bridge")
    module = importlib.import_module("inputs_page_modules.design_guide.resolved_candidate_guidance_item")

    calls: list[tuple[dict | None, dict | None, dict]] = []

    def fake_delegate(item: dict | None, candidate: dict | None, *, state: dict):
        calls.append((item, candidate, state))
        return {"action_type": "apply_resolved_candidate", "sentinel": True}

    original = bridge._promote_guidance_item_to_resolved_candidate_extracted
    bridge._promote_guidance_item_to_resolved_candidate_extracted = fake_delegate
    try:
        item = {"title_main": "A"}
        candidate = {"updates": {"D": 550.0}}
        state = {"D": 500.0}
        result = bridge._promote_guidance_item_to_resolved_candidate(item, candidate, state=state)
    finally:
        bridge._promote_guidance_item_to_resolved_candidate_extracted = original

    assert result == {"action_type": "apply_resolved_candidate", "sentinel": True}
    assert calls == [(item, candidate, state)]
    assert module._candidate_failure_coverage_summary is bridge._candidate_failure_coverage_summary
    assert module._guidance_change_lines_for_updates is bridge._guidance_change_lines_for_updates


def _assert_behavior_probe() -> None:
    from inputs_page_modules.design_guide import resolved_candidate_guidance_item as module

    module._guidance_change_lines_for_updates = lambda state, updates: [f"change:{','.join(sorted(updates))}"]
    module._candidate_failure_coverage_summary = lambda state, candidate: {
        "covers_all_current_failures": True,
        "covered_fail_keys": ["bending"],
        "remaining_fail_keys": [],
    }
    item = {"title_main": "Candidate", "action_type": "apply_shear_recommendation", "action_payload": {}}
    candidate = {
        "updates": {"D": 550.0},
        "label": "Resolved label",
        "action_type": "apply_compound_guidance",
        "candidate_post_util": 0.91,
        "candidate_reaches_target_band": True,
    }
    out = module._promote_guidance_item_to_resolved_candidate(item, candidate, state={"D": 500.0})
    assert out["action_type"] == "apply_resolved_candidate"
    assert out["resolved_candidate_label"] == "Resolved label"
    assert out["resolved_candidate_action_type"] == "apply_compound_guidance"
    assert out["resolved_candidate_updates"] == {"D": 550.0}
    assert out["has_resolved_candidate_payload"] is True
    assert out["covers_all_current_failures"] is True
    assert out["covered_fail_keys"] == ["bending"]
    assert out["remaining_fail_keys"] == []
    payload = out["action_payload"]
    assert payload["guidance_change_lines"] == ["change:D"]
    assert payload["resolved_candidate_reaches_target_band"] is True


def main() -> None:
    _assert_bridge_wrapper()
    _assert_module_owner()
    _assert_runtime_delegate_and_binding()
    _assert_behavior_probe()
    print("inputs_page_guidance_item_promotion_extraction: PASS")


if __name__ == "__main__":
    main()
