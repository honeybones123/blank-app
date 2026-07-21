"""Verify one-click candidate solver extraction from the Inputs app bridge."""

from __future__ import annotations

import ast
import json
import sys
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BRIDGE = ROOT / "inputs_page_app_contract_bridge.py"
MODULE = ROOT / "inputs_page_modules" / "one_click_candidate_solver.py"
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

    bridge_node = _function_node(bridge_source, "_solve_one_click_candidate")
    module_node = _function_node(module_source, "_solve_one_click_candidate")
    bridge_body = ast.get_source_segment(bridge_source, bridge_node) or ""
    module_body = ast.get_source_segment(module_source, module_node) or ""

    dependency_block = module_source.split("def bind_one_click_candidate_solver_dependencies", 1)[0]

    checks: dict[str, bool] = {
        "bridge_wrapper_is_small": (bridge_node.end_lineno or bridge_node.lineno) - bridge_node.lineno + 1 <= 15,
        "bridge_binds_dependencies": "_bind_one_click_candidate_solver_dependencies(globals())" in bridge_body,
        "bridge_delegates_to_extracted_module": "_solve_one_click_candidate_extracted" in bridge_body,
        "module_contains_extracted_body": (module_node.end_lineno or module_node.lineno) - module_node.lineno + 1 > 350,
        "module_keeps_recursive_self_call": "_solve_one_click_candidate(" in module_body,
        "module_dependency_list_does_not_bind_self": '"_solve_one_click_candidate"' not in dependency_block,
        "module_has_dependency_binder": "def bind_one_click_candidate_solver_dependencies" in module_source,
        "module_does_not_import_streamlit": "streamlit" not in module_source and "import st" not in module_source,
        "module_does_not_read_session_state": ".session_state" not in module_source,
        "module_does_not_import_bridge": "inputs_page_app_contract_bridge" not in module_source,
    }

    import inputs_page_app_contract_bridge as bridge
    import inputs_page_modules.one_click_candidate_solver as extracted

    sentinel = {"sentinel": "one_click_candidate_solver"}
    original = bridge._solve_one_click_candidate_extracted

    def _fake_extracted(
        state: dict,
        *,
        goal: str | None = None,
        expanded: bool = False,
        debug_enabled: bool = False,
    ) -> dict:
        return {
            "result": dict(sentinel),
            "state": dict(state),
            "goal": goal,
            "expanded": expanded,
            "debug_enabled": debug_enabled,
            "bound_time": getattr(extracted, "time", None) is bridge.time,
        }

    try:
        bridge._solve_one_click_candidate_extracted = _fake_extracted
        wrapped = bridge._solve_one_click_candidate(
            {"D": 600},
            goal="balanced",
            expanded=True,
            debug_enabled=True,
        )
    finally:
        bridge._solve_one_click_candidate_extracted = original

    checks["bridge_runtime_binds_module_globals"] = (
        getattr(extracted, "time", None) is bridge.time
        and getattr(extracted, "speed_profile_record", None) is bridge.speed_profile_record
    )
    checks["bridge_runtime_delegates_with_arguments"] = (
        wrapped.get("result") == sentinel
        and wrapped.get("state") == {"D": 600}
        and wrapped.get("goal") == "balanced"
        and wrapped.get("expanded") is True
        and wrapped.get("debug_enabled") is True
        and wrapped.get("bound_time") is True
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
    json_path = ARTIFACTS / f"inputs_page_one_click_candidate_solver_extraction_{stamp}.json"
    report_path = AUDITS / f"inputs_page_one_click_candidate_solver_extraction_{stamp}.md"
    json_path.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page One-Click Candidate Solver Extraction",
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
