"""Verify non-app-bridge deflection evaluation extraction from the Inputs bridge."""

from __future__ import annotations

import ast
import json
import sys
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BRIDGE = ROOT / "inputs_page_app_contract_bridge.py"
MODULE = ROOT / "inputs_page_modules" / "app_bridge" / "deflection_evaluation.py"
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

    name = "_evaluate_deflection_with_state"
    bridge_node = _function_node(bridge_source, name)
    module_node = _function_node(module_source, name)
    bridge_body = ast.get_source_segment(bridge_source, bridge_node) or ""

    checks: dict[str, bool] = {
        "bridge_wrapper_is_small": (bridge_node.end_lineno or bridge_node.lineno) - bridge_node.lineno + 1 <= 5,
        "bridge_binds_dependencies": "_bind_deflection_evaluation_dependencies(globals())" in bridge_body,
        "bridge_delegates_to_extracted_module": "_evaluate_deflection_with_state_extracted" in bridge_body,
        "module_contains_extracted_body": (module_node.end_lineno or module_node.lineno) - module_node.lineno + 1 >= 101,
        "module_has_dependency_binder": "def bind_deflection_evaluation_dependencies" in module_source,
        "module_does_not_import_bridge": "inputs_page_app_contract_bridge" not in module_source,
        "module_keeps_deflection_contract_surface": all(
            token in module_source
            for token in (
                "calc_ief_simplified",
                "calc_deflection_as3600",
                "_derive_equiv_udl_from_actions",
                "get_resolved_deflection_support_type",
                "summary_delta_total_mm",
                "summary_defl_limit_mm",
                "summary_util_total",
                "defl_total",
                "Total deflection (short + long-term)",
                "route_page",
                "Long-term deflection",
            )
        ),
    }

    import inputs_page_app_contract_bridge as bridge
    from inputs_page_modules.app_bridge import deflection_evaluation as extracted

    original = bridge._evaluate_deflection_with_state_extracted
    call_record: dict = {}

    def _fake_extracted(state: dict, *, bottom_updates: dict | None = None) -> dict:
        call_record.update(
            {
                "state": dict(state),
                "bottom_updates": dict(bottom_updates or {}),
                "bound_bottom_state": getattr(extracted, "_effective_bottom_design_state", None)
                is bridge._effective_bottom_design_state,
                "bound_width": getattr(extracted, "_design_width_value", None)
                is bridge._design_width_value,
                "bound_float": getattr(extracted, "_float_from_state", None)
                is bridge._float_from_state,
                "bound_status": getattr(extracted, "_status_from_candidate_util", None)
                is bridge._status_from_candidate_util,
                "bound_st": getattr(extracted, "st", None) is bridge.st,
            }
        )
        return {"status": "PASS"}

    try:
        bridge._evaluate_deflection_with_state_extracted = _fake_extracted
        returned = bridge._evaluate_deflection_with_state(
            {"D": 650},
            bottom_updates={"Ast_bot": 1200},
        )
    finally:
        bridge._evaluate_deflection_with_state_extracted = original

    checks["bridge_runtime_binds_module_globals"] = (
        getattr(extracted, "_effective_bottom_design_state", None)
        is bridge._effective_bottom_design_state
        and getattr(extracted, "_design_width_value", None) is bridge._design_width_value
        and getattr(extracted, "_float_from_state", None) is bridge._float_from_state
        and getattr(extracted, "_status_from_candidate_util", None) is bridge._status_from_candidate_util
        and getattr(extracted, "st", None) is bridge.st
    )
    checks["bridge_runtime_delegates_with_arguments"] = (
        returned == {"status": "PASS"}
        and call_record.get("state") == {"D": 650}
        and call_record.get("bottom_updates") == {"Ast_bot": 1200}
        and call_record.get("bound_bottom_state") is True
        and call_record.get("bound_width") is True
        and call_record.get("bound_float") is True
        and call_record.get("bound_status") is True
        and call_record.get("bound_st") is True
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
    json_path = ARTIFACTS / f"inputs_page_deflection_evaluation_extraction_{stamp}.json"
    report_path = AUDITS / f"inputs_page_deflection_evaluation_extraction_{stamp}.md"
    json_path.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Deflection Evaluation Extraction",
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
