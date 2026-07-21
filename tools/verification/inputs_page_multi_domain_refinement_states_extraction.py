"""Lock extraction of multi-domain refinement-state generation."""

from __future__ import annotations

import ast
import importlib
import inspect
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BRIDGE_PATH = ROOT / "inputs_page_app_contract_bridge.py"
MODULE_PATH = ROOT / "inputs_page_modules" / "design_guide" / "governing_domain_tightening_candidates.py"
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
    node = _function_node(source, "_one_click_generate_multi_domain_refinement_states")
    body = _segment(source, node)
    line_count = node.end_lineno - node.lineno + 1
    assert line_count <= 12, f"bridge wrapper too large: {line_count} lines"
    assert "_bind_governing_domain_tightening_candidates_dependencies(globals())" in body
    assert "_one_click_generate_multi_domain_refinement_states_extracted(" in body


def _assert_module_owner() -> None:
    source = MODULE_PATH.read_text(encoding="utf-8")
    node = _function_node(source, "_one_click_generate_multi_domain_refinement_states")
    body = _segment(source, node)
    assert node.end_lineno - node.lineno + 1 >= 90
    assert "def bind_governing_domain_tightening_candidates_dependencies" in source
    assert "inputs_page_app_contract_bridge" not in source
    assert "import streamlit" not in source
    prefix = source.split("def bind_governing_domain_tightening_candidates_dependencies", 1)[0]
    assert '"_one_click_generate_multi_domain_refinement_states"' not in prefix
    for token in (
        "Small local vector search",
        '"bending"',
        '"shear"',
        '"s_lig"',
        '"lig_legs"',
        '"lig_d"',
        "_candidate_target_domains_for_band",
        "_one_click_required_domains_satisfied",
        "_one_click_eval_domain_scores",
    ):
        assert token in body, f"missing contract token: {token}"


def _assert_runtime_delegate_and_binding() -> None:
    bridge = importlib.import_module("inputs_page_app_contract_bridge")
    module = importlib.import_module("inputs_page_modules.design_guide.governing_domain_tightening_candidates")

    calls: list[tuple[dict, dict, dict]] = []

    def fake_delegate(working_state: dict, cur_eval: dict, mode_config: dict) -> list[dict]:
        calls.append((working_state, cur_eval, mode_config))
        return [{"sentinel": True}]

    original = bridge._one_click_generate_multi_domain_refinement_states_extracted
    bridge._one_click_generate_multi_domain_refinement_states_extracted = fake_delegate
    try:
        working_state = {"D": 500.0, "s_lig": 150.0, "lig_legs": 2, "lig_d": 10}
        cur_eval = {"overview": {}}
        mode_config = {"target_util_min": 0.8}
        result = bridge._one_click_generate_multi_domain_refinement_states(
            working_state,
            cur_eval,
            mode_config,
        )
    finally:
        bridge._one_click_generate_multi_domain_refinement_states_extracted = original

    assert result == [{"sentinel": True}]
    assert calls == [(working_state, cur_eval, mode_config)]
    assert module._candidate_target_domains_for_band is bridge._candidate_target_domains_for_band
    assert module._one_click_required_domains_satisfied is bridge._one_click_required_domains_satisfied
    assert module._one_click_eval_domain_scores is bridge._one_click_eval_domain_scores
    assert module._one_click_diff_accumulated_updates is bridge._one_click_diff_accumulated_updates


def main() -> None:
    _assert_bridge_wrapper()
    _assert_module_owner()
    _assert_runtime_delegate_and_binding()
    print("inputs_page_multi_domain_refinement_states_extraction: PASS")


if __name__ == "__main__":
    main()
