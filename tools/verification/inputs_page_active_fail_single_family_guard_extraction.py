"""Verify active-fail single-family guard extraction from the Inputs bridge."""

from __future__ import annotations

import ast
import json
import sys
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BRIDGE = ROOT / "inputs_page_app_contract_bridge.py"
MODULE = ROOT / "inputs_page_modules" / "design_guide" / "active_fail_single_family_guard.py"
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

    name = "_replace_unsafe_combined_active_fail_single_family_action"
    bridge_node = _function_node(bridge_source, name)
    module_node = _function_node(module_source, name)
    bridge_body = ast.get_source_segment(bridge_source, bridge_node) or ""

    checks: dict[str, bool] = {
        "bridge_wrapper_is_small": (bridge_node.end_lineno or bridge_node.lineno) - bridge_node.lineno + 1 <= 5,
        "bridge_binds_dependencies": "_bind_active_fail_single_family_guard_dependencies(globals())" in bridge_body,
        "bridge_delegates_to_extracted_module": "_replace_unsafe_combined_active_fail_single_family_action_extracted" in bridge_body,
        "module_contains_extracted_body": (module_node.end_lineno or module_node.lineno) - module_node.lineno + 1 >= 94,
        "module_has_dependency_binder": "def bind_active_fail_single_family_guard_dependencies" in module_source,
        "module_does_not_import_streamlit": "streamlit" not in module_source and "import st" not in module_source,
        "module_does_not_read_session_state": ".session_state" not in module_source,
        "module_does_not_import_bridge": "inputs_page_app_contract_bridge" not in module_source,
        "module_keeps_controller_guard_contract": all(
            token in module_source
            for token in (
                "CODEX_BROWSER_TEST_MODE",
                "combined_active_fail_single_family_action_blocked",
                "active_fail_executor_no_repair_blocker",
                "No safe one-click combined bending and shear repair is available",
                "combined_bending_shear_fail",
                "build_design_guide_controller_active_fail_executor_no_repair_blocker_from_evidence",
            )
        ),
    }

    import inputs_page_app_contract_bridge as bridge
    from inputs_page_modules.design_guide import active_fail_single_family_guard as extracted

    original = bridge._replace_unsafe_combined_active_fail_single_family_action_extracted
    call_record: dict = {}

    def _fake_extracted(payload: dict, *, state: dict) -> dict:
        call_record.update(
            {
                "payload": dict(payload),
                "state": dict(state),
                "bound_builder": getattr(
                    extracted,
                    "build_design_guide_controller_active_fail_executor_no_repair_blocker_from_evidence",
                    None,
                )
                is bridge.build_design_guide_controller_active_fail_executor_no_repair_blocker_from_evidence,
                "bound_os": getattr(extracted, "os", None) is bridge.os,
            }
        )
        return {"guarded": True}

    try:
        bridge._replace_unsafe_combined_active_fail_single_family_action_extracted = _fake_extracted
        returned = bridge._replace_unsafe_combined_active_fail_single_family_action(
            {"guidance_items": [{"title_main": "Primary"}]},
            state={"D": 650},
        )
    finally:
        bridge._replace_unsafe_combined_active_fail_single_family_action_extracted = original

    checks["bridge_runtime_binds_module_globals"] = (
        getattr(
            extracted,
            "build_design_guide_controller_active_fail_executor_no_repair_blocker_from_evidence",
            None,
        )
        is bridge.build_design_guide_controller_active_fail_executor_no_repair_blocker_from_evidence
        and getattr(extracted, "os", None) is bridge.os
    )
    checks["bridge_runtime_delegates_with_arguments"] = (
        returned == {"guarded": True}
        and call_record.get("payload") == {"guidance_items": [{"title_main": "Primary"}]}
        and call_record.get("state") == {"D": 650}
        and call_record.get("bound_builder") is True
        and call_record.get("bound_os") is True
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
    json_path = ARTIFACTS / f"inputs_page_active_fail_single_family_guard_extraction_{stamp}.json"
    report_path = AUDITS / f"inputs_page_active_fail_single_family_guard_extraction_{stamp}.md"
    json_path.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Active-Fail Single-Family Guard Extraction",
                "",
                f"Status: {result['status']}",
                "",
                f"- Bridge wrapper lines: {result['bridge_wrapper_lines']}",
                f"- Extracted module function lines: {result['module_function_lines']}",
                "",
                "## Checks",
                "",
                *[f"- {check}: {'PASS' if passed else 'FAIL'}" for check, passed in checks.items()],
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
