"""Lock extraction of guidance item display dedupe."""

from __future__ import annotations

import ast
import importlib
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BRIDGE_PATH = ROOT / "inputs_page_app_contract_bridge.py"
MODULE_PATH = ROOT / "inputs_page_modules" / "design_guide" / "guidance_item_dedupe.py"
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
    node = _function_node(source, "_dedupe_guidance_items_for_display")
    body = _segment(source, node)
    assert node.end_lineno - node.lineno + 1 <= 3
    assert "_bind_guidance_item_dedupe_dependencies(globals())" in body
    assert "_dedupe_guidance_items_for_display_extracted(" in body


def _assert_module_owner() -> None:
    source = MODULE_PATH.read_text(encoding="utf-8")
    node = _function_node(source, "_dedupe_guidance_items_for_display")
    body = _segment(source, node)
    assert node.end_lineno - node.lineno + 1 >= 80
    assert "def bind_guidance_item_dedupe_dependencies" in source
    assert "inputs_page_app_contract_bridge" not in source
    assert "import streamlit" not in source
    for token in (
        "duplicate_action_payload",
        "near_duplicate_primary_overlap",
        "only_primary_and_one_distinct_alternative_allowed",
        "guidance_items_before_dedupe_count",
        "guidance_items_after_dedupe_count",
        "dropped_guidance_items_summary",
        "primary_card_family_tag",
        "secondary_card_family_tag",
        "secondary_card_materially_distinct",
    ):
        assert token in body, f"missing dedupe token: {token}"


def _assert_runtime_delegate_and_binding() -> None:
    bridge = importlib.import_module("inputs_page_app_contract_bridge")
    module = importlib.import_module("inputs_page_modules.design_guide.guidance_item_dedupe")

    calls: list[tuple[list[dict], dict]] = []

    def fake_delegate(items: list[dict], state: dict):
        calls.append((items, state))
        return ([{"title_main": "kept"}], {"deduped": True})

    original = bridge._dedupe_guidance_items_for_display_extracted
    bridge._dedupe_guidance_items_for_display_extracted = fake_delegate
    try:
        items = [{"title_main": "A"}]
        state = {"D": 500.0}
        result = bridge._dedupe_guidance_items_for_display(items, state)
    finally:
        bridge._dedupe_guidance_items_for_display_extracted = original

    assert result == ([{"title_main": "kept"}], {"deduped": True})
    assert calls == [(items, state)]
    assert module._guidance_action_updates is bridge._guidance_action_updates
    assert module._guidance_item_family_tag is bridge._guidance_item_family_tag
    assert module._guidance_item_payload_fingerprint is bridge._guidance_item_payload_fingerprint


def _assert_behavior_probe() -> None:
    from inputs_page_modules.design_guide import guidance_item_dedupe as module

    module._guidance_action_updates = lambda at, pl, *, state: dict(pl.get("updates") or {})
    module._guidance_item_family_tag = lambda item, state: str(item.get("family") or "family")
    module._guidance_item_payload_fingerprint = lambda item, state: (
        str(item.get("action_type") or ""),
        tuple(sorted(dict((item.get("action_payload") or {}).get("updates") or {}).items())),
    )
    state = {"D": 500.0}
    items = [
        {"title_main": "Primary", "action_type": "apply_a", "family": "a", "action_payload": {"updates": {"D": 550}}},
        {"title_main": "Dup", "action_type": "apply_a", "family": "a", "action_payload": {"updates": {"D": 550}}},
        {"title_main": "Distinct", "action_type": "apply_b", "family": "b", "action_payload": {"updates": {"b": 350}}},
        {"title_main": "Third", "action_type": "apply_c", "family": "c", "action_payload": {"updates": {"fc": 40}}},
    ]
    out, meta = module._dedupe_guidance_items_for_display(items, state)
    assert [item["title_main"] for item in out] == ["Primary", "Distinct"]
    reasons = [row.get("dropped_reason") for row in meta.get("dropped_guidance_items_summary") or []]
    assert "duplicate_action_payload" in reasons
    assert "only_primary_and_one_distinct_alternative_allowed" in reasons
    assert meta["guidance_items_before_dedupe_count"] == 4
    assert meta["guidance_items_after_dedupe_count"] == 2
    assert meta["secondary_card_materially_distinct"] is True


def main() -> None:
    _assert_bridge_wrapper()
    _assert_module_owner()
    _assert_runtime_delegate_and_binding()
    _assert_behavior_probe()
    print("inputs_page_guidance_item_dedupe_extraction: PASS")


if __name__ == "__main__":
    main()
