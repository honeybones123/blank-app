"""Verify auto-design candidate selector extraction from the Inputs app bridge."""

from __future__ import annotations

import ast
import json
import sys
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BRIDGE = ROOT / "inputs_page_app_contract_bridge.py"
MODULE = ROOT / "inputs_page_modules" / "design_guide" / "auto_design_candidate_selector.py"
ARTIFACTS = ROOT / "artifacts" / "verification"
AUDITS = ROOT / "artifacts" / "audits"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _function_node(source: str, name: str) -> ast.FunctionDef:
    tree = ast.parse(source)
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    raise AssertionError(f"{name} not found")


def main() -> int:
    bridge_source = BRIDGE.read_text(encoding="utf-8")
    module_source = MODULE.read_text(encoding="utf-8")

    bridge_node = _function_node(bridge_source, "_select_best_auto_design_candidate")
    module_node = _function_node(module_source, "_select_best_auto_design_candidate")
    bridge_body = ast.get_source_segment(bridge_source, bridge_node) or ""
    dependency_block = module_source.split("def bind_auto_design_candidate_selector_dependencies", 1)[0]

    checks: dict[str, bool] = {
        "bridge_wrapper_is_small": (bridge_node.end_lineno or bridge_node.lineno) - bridge_node.lineno + 1 <= 4,
        "bridge_binds_dependencies": "_bind_auto_design_candidate_selector_dependencies(globals())" in bridge_body,
        "bridge_delegates_to_extracted_module": "_select_best_auto_design_candidate_extracted" in bridge_body,
        "module_contains_extracted_body": (module_node.end_lineno or module_node.lineno) - module_node.lineno + 1 > 200,
        "module_has_dependency_binder": "def bind_auto_design_candidate_selector_dependencies" in module_source,
        "module_does_not_bind_nested_false_positives": '"row"' not in dependency_block,
        "module_does_not_import_streamlit": "streamlit" not in module_source and "import st" not in module_source,
        "module_does_not_read_session_state": ".session_state" not in module_source,
        "module_does_not_import_bridge": "inputs_page_app_contract_bridge" not in module_source,
    }

    import inputs_page_app_contract_bridge as bridge
    from inputs_page_modules.design_guide import auto_design_candidate_selector as extracted

    sentinel = {"sentinel": "auto_design_candidate_selector"}
    original = bridge._select_best_auto_design_candidate_extracted

    def _fake_extracted(candidates: list[dict], mode_config: dict, seed_candidate: dict) -> dict:
        return {
            "result": dict(sentinel),
            "candidates": list(candidates),
            "mode_config": dict(mode_config),
            "seed_candidate": dict(seed_candidate),
            "bound_rank_trace": getattr(extracted, "_ACTIVE_GUIDANCE_RANK_TRACE", "missing")
            is bridge._ACTIVE_GUIDANCE_RANK_TRACE,
        }

    try:
        bridge._select_best_auto_design_candidate_extracted = _fake_extracted
        wrapped = bridge._select_best_auto_design_candidate(
            [{"label": "candidate"}],
            {"search_strategy": "balanced"},
            {"state": {"D": 600}},
        )
    finally:
        bridge._select_best_auto_design_candidate_extracted = original

    checks["bridge_runtime_binds_module_globals"] = (
        getattr(extracted, "_ACTIVE_GUIDANCE_RANK_TRACE", "missing")
        is bridge._ACTIVE_GUIDANCE_RANK_TRACE
        and getattr(extracted, "_score_auto_design_candidate", None)
        is bridge._score_auto_design_candidate
    )
    checks["bridge_runtime_delegates_with_arguments"] = (
        wrapped.get("result") == sentinel
        and wrapped.get("candidates") == [{"label": "candidate"}]
        and wrapped.get("mode_config") == {"search_strategy": "balanced"}
        and wrapped.get("seed_candidate") == {"state": {"D": 600}}
        and wrapped.get("bound_rank_trace") is True
    )

    result = {
        "status": "PASS" if all(checks.values()) else "FAIL",
        "checks": checks,
        "bridge_wrapper_lines": (bridge_node.end_lineno or bridge_node.lineno) - bridge_node.lineno + 1,
        "module_function_lines": (module_node.end_lineno or module_node.lineno) - module_node.lineno + 1,
    }

    stamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    AUDITS.mkdir(parents=True, exist_ok=True)
    json_path = ARTIFACTS / f"inputs_page_auto_design_candidate_selector_extraction_{stamp}.json"
    report_path = AUDITS / f"inputs_page_auto_design_candidate_selector_extraction_{stamp}.md"
    json_path.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Auto-Design Candidate Selector Extraction",
                "",
                f"Status: {result['status']}",
                "",
                f"- Bridge wrapper lines: {result['bridge_wrapper_lines']}",
                f"- Extracted module function lines: {result['module_function_lines']}",
                "",
                "## Checks",
                "",
                *[f"- {name}: {'PASS' if passed else 'FAIL'}" for name, passed in checks.items()],
                "",
            ]
        ),
        encoding="utf-8",
    )
    print(result["status"])
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
