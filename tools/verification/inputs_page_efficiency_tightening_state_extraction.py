"""Verify efficiency tightening state extraction from the Inputs app bridge."""

from __future__ import annotations

import ast
import json
import sys
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BRIDGE = ROOT / "inputs_page_app_contract_bridge.py"
MODULE = ROOT / "inputs_page_modules" / "design_guide" / "efficiency_tightening_state.py"
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

    bridge_node = _function_node(bridge_source, "compute_efficiency_tightening_state")
    module_node = _function_node(module_source, "compute_efficiency_tightening_state")
    bridge_body = ast.get_source_segment(bridge_source, bridge_node) or ""

    checks: dict[str, bool] = {
        "bridge_wrapper_is_small": (bridge_node.end_lineno or bridge_node.lineno) - bridge_node.lineno + 1 <= 4,
        "bridge_binds_dependencies": "_bind_efficiency_tightening_state_dependencies(globals())" in bridge_body,
        "bridge_delegates_to_extracted_module": "_compute_efficiency_tightening_state_extracted" in bridge_body,
        "module_contains_extracted_body": (module_node.end_lineno or module_node.lineno) - module_node.lineno + 1 > 250,
        "module_has_dependency_binder": "def bind_efficiency_tightening_state_dependencies" in module_source,
        "module_does_not_import_streamlit": "streamlit" not in module_source and "import st" not in module_source,
        "module_does_not_read_session_state": ".session_state" not in module_source,
        "module_does_not_import_bridge": "inputs_page_app_contract_bridge" not in module_source,
    }

    import inputs_page_app_contract_bridge as bridge
    from inputs_page_modules.design_guide import efficiency_tightening_state as extracted

    sentinel = {"sentinel": "efficiency_tightening_state"}
    original = bridge._compute_efficiency_tightening_state_extracted

    def _fake_extracted(state: dict, context: dict | None = None) -> dict:
        return {
            "result": dict(sentinel),
            "state": dict(state),
            "context": dict(context or {}),
            "bound_target": getattr(extracted, "TARGET_BAND_EPS", None),
        }

    try:
        bridge._compute_efficiency_tightening_state_extracted = _fake_extracted
        wrapped = bridge.compute_efficiency_tightening_state({"x": 1}, context={"y": 2})
    finally:
        bridge._compute_efficiency_tightening_state_extracted = original

    checks["bridge_runtime_binds_module_globals"] = (
        hasattr(extracted, "TARGET_BAND_EPS")
        and extracted.TARGET_BAND_EPS == bridge.TARGET_BAND_EPS
    )
    checks["bridge_runtime_delegates_with_arguments"] = (
        wrapped.get("result") == sentinel
        and wrapped.get("state") == {"x": 1}
        and wrapped.get("context") == {"y": 2}
        and wrapped.get("bound_target") == bridge.TARGET_BAND_EPS
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
    json_path = ARTIFACTS / f"inputs_page_efficiency_tightening_state_extraction_{stamp}.json"
    report_path = AUDITS / f"inputs_page_efficiency_tightening_state_extraction_{stamp}.md"
    json_path.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Efficiency Tightening State Extraction",
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
