"""Lock extraction of Design Guide pending recommendation construction."""

from __future__ import annotations

import ast
import importlib
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BRIDGE_PATH = ROOT / "inputs_page_app_contract_bridge.py"
MODULE_PATH = ROOT / "inputs_page_modules" / "design_guide" / "pending_recommendation.py"
CTA_READINESS = ROOT / "tools" / "verification" / "design_guide_cta_authority_readiness_snapshot.py"
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
    node = _function_node(source, "_build_pending_recommendation")
    body = _segment(source, node)
    line_count = node.end_lineno - node.lineno + 1
    assert line_count <= 8, f"bridge wrapper too large: {line_count} lines"
    assert "_bind_pending_recommendation_dependencies(globals())" in body
    assert "_build_pending_recommendation_extracted(" in body

    sync_node = _function_node(source, "_sync_pending_recommendation_from_guidance")
    sync_body = _segment(source, sync_node)
    sync_line_count = sync_node.end_lineno - sync_node.lineno + 1
    assert sync_line_count <= 12, f"bridge sync wrapper too large: {sync_line_count} lines"
    assert "_bind_pending_recommendation_dependencies(globals())" in sync_body
    assert "_sync_pending_recommendation_from_guidance_extracted(" in sync_body
    assert "DESIGN_GUIDE_APPLY_BANNER_KEY" not in sync_body


def _assert_module_owner() -> None:
    source = MODULE_PATH.read_text(encoding="utf-8")
    node = _function_node(source, "_build_pending_recommendation")
    sync_node = _function_node(source, "_sync_pending_recommendation_from_guidance")
    body = _segment(source, node)
    sync_body = _segment(source, sync_node)
    assert node.end_lineno - node.lineno + 1 >= 90
    assert sync_node.end_lineno - sync_node.lineno + 1 >= 60
    assert "def bind_pending_recommendation_dependencies" in source
    assert "inputs_page_app_contract_bridge" not in source
    assert "import streamlit" not in source
    for token in (
        "resolved_candidate_label",
        "resolved_candidate_action_type",
        "Review and apply this recommendation.",
        "Optimisation available",
        "apply_resolved_candidate",
        "_attach_recommendation_envelope",
        "_guidance_executor_actionability_contract",
        "_shared_state_snapshot",
    ):
        assert token in body, f"missing pending recommendation token: {token}"
    for token in (
        "terminal_state_norm == \"optimal\"",
        "terminal_state_norm == \"very_low_demand\"",
        "pending_recommendation",
        "DESIGN_GUIDE_APPLY_BANNER_KEY",
        "_pending_matches_actionable_guidance_item",
        "_pending_recommendation_equivalent",
        "_attach_recommendation_envelope",
    ):
        assert token in sync_body, f"missing pending sync token: {token}"


def _assert_cta_readiness_includes_module() -> None:
    source = CTA_READINESS.read_text(encoding="utf-8")
    assert '"pending_recommendation.py"' in source


def _assert_runtime_delegate_and_binding() -> None:
    bridge = importlib.import_module("inputs_page_app_contract_bridge")
    module = importlib.import_module("inputs_page_modules.design_guide.pending_recommendation")

    calls: list[tuple[dict, dict]] = []
    sync_calls: list[tuple[list[dict], dict, str | None]] = []

    def fake_delegate(item: dict, state: dict) -> dict:
        calls.append((item, state))
        return {"recommendation_id": "sentinel"}

    def fake_sync_delegate(guidance_items: list[dict], state: dict, *, terminal_state: str | None = None) -> dict:
        sync_calls.append((guidance_items, state, terminal_state))
        return {"pending": "sentinel"}

    original = bridge._build_pending_recommendation_extracted
    original_sync = bridge._sync_pending_recommendation_from_guidance_extracted
    bridge._build_pending_recommendation_extracted = fake_delegate
    bridge._sync_pending_recommendation_from_guidance_extracted = fake_sync_delegate
    try:
        item = {"action_type": "apply_resolved_candidate"}
        state = {"D": 500.0}
        result = bridge._build_pending_recommendation(item, state)
        sync_result = bridge._sync_pending_recommendation_from_guidance([item], state, terminal_state="active")
    finally:
        bridge._build_pending_recommendation_extracted = original
        bridge._sync_pending_recommendation_from_guidance_extracted = original_sync

    assert result == {"recommendation_id": "sentinel"}
    assert calls == [(item, state)]
    assert sync_result == {"pending": "sentinel"}
    assert sync_calls == [([item], state, "active")]
    assert module._attach_recommendation_envelope is bridge._attach_recommendation_envelope
    assert module._ensure_guidance_item_resolved_candidate_payload is bridge._ensure_guidance_item_resolved_candidate_payload
    assert module._guidance_executor_actionability_contract is bridge._guidance_executor_actionability_contract
    assert module._pending_matches_actionable_guidance_item is bridge._pending_matches_actionable_guidance_item
    assert module._pending_recommendation_equivalent is bridge._pending_recommendation_equivalent
    assert module._resolve_recommendation_updates is bridge._resolve_recommendation_updates
    assert module._shared_state_snapshot is bridge._shared_state_snapshot
    assert module.st is bridge.st


def _assert_sync_module_cases() -> None:
    module = importlib.import_module("inputs_page_modules.design_guide.pending_recommendation")

    class FakeSt:
        def __init__(self, session_state: dict):
            self.session_state = session_state

    ensured: list[dict] = []

    def ensure(item: dict, state: dict | None = None) -> None:
        ensured.append({"item": dict(item), "state": dict(state or {})})

    def attach(rec: dict, *, source: str, status: str, **kwargs) -> dict:
        return {
            **dict(rec),
            "recommendation_envelope": {
                "source": source,
                "status": status,
                **dict(kwargs),
            },
        }

    def equivalent(a: dict | None, b: dict | None) -> bool:
        return bool(isinstance(a, dict) and isinstance(b, dict) and a.get("recommendation_id") == b.get("recommendation_id"))

    def matches(existing: dict, item: dict) -> bool:
        return bool(existing.get("match_item"))

    original_build = module._build_pending_recommendation
    try:
        module.bind_pending_recommendation_dependencies(
            {
                "DESIGN_GUIDE_APPLY_BANNER_KEY": "banner",
                "DESIGN_GUIDE_APPLY_BANNER_META_KEY": "banner_meta",
                "DESIGN_GUIDE_PENDING_STEP_CTX_KEY": "pending_step",
                "_attach_recommendation_envelope": attach,
                "_ensure_guidance_item_resolved_candidate_payload": ensure,
                "_pending_matches_actionable_guidance_item": matches,
                "_pending_recommendation_equivalent": equivalent,
                "st": FakeSt(
                    {
                        "pending_recommendation": {"_source": "guidance"},
                        "banner": {"old": True},
                        "banner_meta": {"old": True},
                        "pending_step": {"old": True},
                    }
                ),
            }
        )
        assert module._sync_pending_recommendation_from_guidance([], {"D": 600}, terminal_state="optimal") is None
        assert module.st.session_state["pending_recommendation"] is None
        assert "banner" not in module.st.session_state
        assert "banner_meta" not in module.st.session_state
        assert "pending_step" not in module.st.session_state

        module.st = FakeSt({"pending_recommendation": {"_source": "auto_design"}})
        assert module._sync_pending_recommendation_from_guidance([], {"D": 600}, terminal_state="very_low_demand") is None
        assert module.st.session_state["pending_recommendation"] is None

        module.st = FakeSt({"pending_recommendation": {"_source": "guidance", "match_item": True}})
        module._build_pending_recommendation = lambda item, state: None
        existing = module.st.session_state["pending_recommendation"]
        returned_existing = module._sync_pending_recommendation_from_guidance(
            [{"action_type": "apply_resolved_candidate"}],
            {"D": 600},
        )
        assert returned_existing is existing

        module.st = FakeSt({"pending_recommendation": {"recommendation_id": "same", "_source": "guidance"}})
        module._build_pending_recommendation = lambda item, state: {"recommendation_id": "same", "updates": {"D": 650}}
        repaired = module._sync_pending_recommendation_from_guidance(
            [{"action_type": "apply_resolved_candidate"}],
            {"D": 600},
        )
        assert repaired["recommendation_envelope"]["source"] == "guidance"
        assert module.st.session_state["pending_recommendation"] is repaired

        module.st = FakeSt({"pending_recommendation": {"recommendation_id": "old", "_source": "guidance"}})
        module._build_pending_recommendation = lambda item, state: {"recommendation_id": "new", "updates": {"D": 700}}
        pending_out = module._sync_pending_recommendation_from_guidance(
            [{"action_type": "apply_resolved_candidate"}],
            {"D": 600},
        )
        assert pending_out["_source"] == "guidance"
        assert pending_out["recommendation_envelope"]["status"] == "ready"
        assert module.st.session_state["pending_recommendation"] == pending_out
    finally:
        module._build_pending_recommendation = original_build


def main() -> None:
    _assert_bridge_wrapper()
    _assert_module_owner()
    _assert_cta_readiness_includes_module()
    _assert_runtime_delegate_and_binding()
    _assert_sync_module_cases()
    print("inputs_page_pending_recommendation_extraction: PASS")


if __name__ == "__main__":
    main()
