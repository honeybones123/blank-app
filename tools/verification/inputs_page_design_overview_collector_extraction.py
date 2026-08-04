"""Verify design-overview collector extraction from the Inputs app bridge."""

from __future__ import annotations

import ast
import json
import sys
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BRIDGE = ROOT / "inputs_page_app_contract_bridge.py"
MODULE = ROOT / "inputs_page_modules" / "app_bridge" / "design_overview_collector.py"
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

    bridge_node = _function_node(bridge_source, "_collect_design_overview")
    module_node = _function_node(module_source, "_collect_design_overview")
    bridge_body = ast.get_source_segment(bridge_source, bridge_node) or ""
    decorator_sources = {
        ast.get_source_segment(bridge_source, decorator) or ""
        for decorator in bridge_node.decorator_list
    }

    checks: dict[str, bool] = {
        "bridge_wrapper_is_tiny": (bridge_node.end_lineno or bridge_node.lineno) - bridge_node.lineno + 1 <= 30,
        "bridge_keeps_speed_profile_decorator": (
            'speed_profiled("inputs_page.summary_overview_build", category="compute")' in decorator_sources
        ),
        "bridge_binds_dependencies": "session_state=st.session_state" in bridge_body,
        "bridge_delegates_to_extracted_module": "collect_design_overview_owned" in bridge_body,
        "module_contains_extracted_body": (module_node.end_lineno or module_node.lineno) - module_node.lineno + 1 >= 135,
        "module_has_dependency_binder": (
            "class DesignOverviewRuntime" in module_source
            and "globals().update" not in module_source
        ),
        "module_does_not_import_streamlit": "import streamlit" not in module_source,
        "module_does_not_import_bridge": "inputs_page_app_contract_bridge" not in module_source,
        "module_keeps_overview_contract_surface": all(
            token in module_source
            for token in (
                "packs",
                "statuses",
                "utils",
                "any_fail",
                "all_key_pass",
                "worst_util",
                "governing_check",
                "stage3_shear_truth_debug",
                "final_published_shear_truth",
                "inputs_page.summary_overview_build",
            )
        ),
    }

    import inputs_page_app_contract_bridge as bridge
    original = bridge.collect_design_overview_owned
    call_record: dict = {}

    def _fake_extracted(state: dict, context: dict | None = None, *, session_state) -> dict:
        call_record.update(
            {
                "state": dict(state),
                "context": dict(context or {}),
                "session_state": session_state,
            }
        )
        return {"overview": "fake"}

    try:
        bridge.collect_design_overview_owned = _fake_extracted
        returned = bridge._collect_design_overview(
            {"D": 600},
            context={"state": {"D": 600}, "actions": {"Ast": 1000}},
        )
    finally:
        bridge.collect_design_overview_owned = original

    checks["bridge_runtime_binds_module_globals"] = (
        call_record.get("session_state") is bridge.st.session_state
    )
    checks["bridge_runtime_delegates_with_arguments"] = (
        returned == {"overview": "fake"}
        and call_record.get("state") == {"D": 600}
        and call_record.get("context") == {"state": {"D": 600}, "actions": {"Ast": 1000}}
        and call_record.get("session_state") is bridge.st.session_state
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
    json_path = ARTIFACTS / f"inputs_page_design_overview_collector_extraction_{stamp}.json"
    report_path = AUDITS / f"inputs_page_design_overview_collector_extraction_{stamp}.md"
    json_path.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Design Overview Collector Extraction",
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
