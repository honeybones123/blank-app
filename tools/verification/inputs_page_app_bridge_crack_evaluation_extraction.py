"""Verify app-bridge crack evaluation extraction."""

from __future__ import annotations

import ast
import json
import sys
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BRIDGE = ROOT / "inputs_page_app_contract_bridge.py"
MODULE = ROOT / "inputs_page_modules" / "app_bridge" / "crack_evaluation.py"
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

    bridge_node = _function_node(bridge_source, "_evaluate_crack_with_state_for_app_bridge")
    module_node = _function_node(module_source, "_evaluate_crack_with_state_for_app_bridge")
    bridge_body = ast.get_source_segment(bridge_source, bridge_node) or ""

    checks: dict[str, bool] = {
        "module_exists": MODULE.exists(),
        "bridge_wrapper_is_small": (bridge_node.end_lineno or bridge_node.lineno) - bridge_node.lineno + 1 <= 10,
        "bridge_binds_dependencies": "_bind_crack_evaluation_dependencies(globals())" in bridge_body,
        "bridge_delegates_to_extracted_module": "_evaluate_crack_with_state_for_app_bridge_extracted" in bridge_body,
        "module_contains_extracted_body": (module_node.end_lineno or module_node.lineno) - module_node.lineno + 1 >= 60,
        "module_has_dependency_binder": "def bind_crack_evaluation_dependencies" in module_source,
        "module_does_not_import_bridge": "inputs_page_app_contract_bridge" not in module_source,
        "module_keeps_crack_contract_surface": all(
            token in module_source
            for token in (
                "table_sigma_max_A",
                "table_sigma_max_B",
                "calc_eps_diff",
                "calc_sr_max",
                "_compute_sls_outer_steel_stress_with_state_for_app_bridge",
                "_effective_bottom_design_state_for_app_bridge",
                "_effective_bottom_spacing_for_app_bridge",
                "effective_depth_with_links_mm",
                "sigma_allow_table",
                "w_calc",
                "passes",
            )
        ),
    }

    import inputs_page_app_contract_bridge as bridge
    from inputs_page_modules.app_bridge import crack_evaluation as extracted

    original = bridge._evaluate_crack_with_state_for_app_bridge_extracted
    call_record: dict = {}

    def _fake_extracted(state: dict, *, bottom_updates: dict | None = None) -> dict:
        call_record.update(
            {
                "state": dict(state),
                "bottom_updates": dict(bottom_updates or {}),
                "bound_bottom_state": getattr(extracted, "_effective_bottom_design_state_for_app_bridge", None)
                is bridge._effective_bottom_design_state_for_app_bridge,
                "bound_spacing": getattr(extracted, "_effective_bottom_spacing_for_app_bridge", None)
                is bridge._effective_bottom_spacing_for_app_bridge,
                "bound_stress": getattr(extracted, "_compute_sls_outer_steel_stress_with_state_for_app_bridge", None)
                is bridge._compute_sls_outer_steel_stress_with_state_for_app_bridge,
                "bound_width": getattr(extracted, "_design_width_value_for_app_bridge", None)
                is bridge._design_width_value_for_app_bridge,
                "bound_float": getattr(extracted, "_float_from_state", None)
                is bridge._float_from_state,
                "bound_effective_depth": getattr(extracted, "effective_depth_with_links_mm", None)
                is bridge.effective_depth_with_links_mm,
            }
        )
        return {"status": "PASS"}

    try:
        bridge._evaluate_crack_with_state_for_app_bridge_extracted = _fake_extracted
        returned = bridge._evaluate_crack_with_state_for_app_bridge(
            {"D": 650},
            bottom_updates={"Ast_bot": 1200},
        )
    finally:
        bridge._evaluate_crack_with_state_for_app_bridge_extracted = original

    checks["bridge_runtime_binds_module_globals"] = (
        getattr(extracted, "_effective_bottom_design_state_for_app_bridge", None)
        is bridge._effective_bottom_design_state_for_app_bridge
        and getattr(extracted, "_effective_bottom_spacing_for_app_bridge", None)
        is bridge._effective_bottom_spacing_for_app_bridge
        and getattr(extracted, "_compute_sls_outer_steel_stress_with_state_for_app_bridge", None)
        is bridge._compute_sls_outer_steel_stress_with_state_for_app_bridge
        and getattr(extracted, "_design_width_value_for_app_bridge", None)
        is bridge._design_width_value_for_app_bridge
        and getattr(extracted, "_float_from_state", None) is bridge._float_from_state
        and getattr(extracted, "effective_depth_with_links_mm", None)
        is bridge.effective_depth_with_links_mm
    )
    checks["bridge_runtime_delegates_with_arguments"] = (
        returned == {"status": "PASS"}
        and call_record.get("state") == {"D": 650}
        and call_record.get("bottom_updates") == {"Ast_bot": 1200}
        and call_record.get("bound_bottom_state") is True
        and call_record.get("bound_spacing") is True
        and call_record.get("bound_stress") is True
        and call_record.get("bound_width") is True
        and call_record.get("bound_float") is True
        and call_record.get("bound_effective_depth") is True
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
    json_path = ARTIFACTS / f"inputs_page_app_bridge_crack_evaluation_extraction_{stamp}.json"
    report_path = AUDITS / f"inputs_page_app_bridge_crack_evaluation_extraction_{stamp}.md"
    json_path.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page App Bridge Crack Evaluation Extraction",
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
