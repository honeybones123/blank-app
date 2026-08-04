"""Verify executor actionability contract extraction from the Inputs app bridge."""

from __future__ import annotations

import ast
import json
import sys
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BRIDGE = ROOT / "inputs_page_app_contract_bridge.py"
MODULE = ROOT / "inputs_page_modules" / "design_guide" / "executor_actionability_contract.py"
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

    bridge_node = _function_node(bridge_source, "_guidance_executor_actionability_contract")
    module_node = _function_node(module_source, "_guidance_executor_actionability_contract")
    bridge_body = ast.get_source_segment(bridge_source, bridge_node) or ""

    checks: dict[str, bool] = {
        "bridge_wrapper_is_small": (bridge_node.end_lineno or bridge_node.lineno) - bridge_node.lineno + 1 <= 7,
        "bridge_binds_dependencies": "_bind_executor_actionability_contract_dependencies(globals())" in bridge_body,
        "bridge_delegates_to_extracted_module": "_guidance_executor_actionability_contract_extracted" in bridge_body,
        "module_contains_extracted_body": (module_node.end_lineno or module_node.lineno) - module_node.lineno + 1 >= 117,
        "module_has_dependency_binder": "def bind_executor_actionability_contract_dependencies" in module_source,
        "module_does_not_import_streamlit": "import streamlit" not in module_source,
        "module_does_not_import_bridge": "inputs_page_app_contract_bridge" not in module_source,
        "module_keeps_actionability_contract_surface": all(
            token in module_source
            for token in (
                "invalid_guidance_item",
                "missing_action_type",
                "primary_efficiency_card_not_executor_backed",
                "missing_recommendation_updates",
                "blocked_zero_shear_demand_shear_update_not_meaningful",
                "local_cleanup_preview_failed",
                "design_guide_executor_shear_family_threshold_probe",
                "blocked_shear_cleanup_does_not_reach_final_family_threshold",
                "rejected_as_non_governing_cleanup",
            )
        ),
    }

    import inputs_page_app_contract_bridge as bridge
    from inputs_page_modules.design_guide import executor_actionability_contract as extracted

    original = bridge._guidance_executor_actionability_contract_extracted
    call_record: dict = {}

    def _fake_extracted(item: dict | None, *, state: dict | None) -> tuple[bool, str | None]:
        call_record.update(
            {
                "item": dict(item or {}),
                "state": dict(state or {}),
                "bound_snapshot": getattr(extracted, "_guidance_state_snapshot", None)
                is bridge._guidance_state_snapshot,
                "bound_resolve_updates": getattr(extracted, "_resolve_recommendation_updates", None)
                is bridge._resolve_recommendation_updates,
                "bound_preview": getattr(extracted, "_design_guide_preview_contract_for_updates", None)
                is bridge._design_guide_preview_contract_for_updates,
                "bound_overview": getattr(extracted, "_collect_design_overview", None)
                is bridge._collect_design_overview,
                "bound_executor_safe": getattr(extracted, "_resolved_shear_cleanup_is_executor_safe", None)
                is bridge._resolved_shear_cleanup_is_executor_safe,
            }
        )
        return True, None

    try:
        bridge._guidance_executor_actionability_contract_extracted = _fake_extracted
        returned = bridge._guidance_executor_actionability_contract(
            {"action_type": "apply_resolved_candidate"},
            state={"D": 600},
        )
    finally:
        bridge._guidance_executor_actionability_contract_extracted = original

    checks["bridge_runtime_binds_module_globals"] = (
        getattr(extracted, "_guidance_state_snapshot", None) is bridge._guidance_state_snapshot
        and getattr(extracted, "_resolve_recommendation_updates", None) is bridge._resolve_recommendation_updates
        and getattr(extracted, "_design_guide_preview_contract_for_updates", None)
        is bridge._design_guide_preview_contract_for_updates
        and getattr(extracted, "_collect_design_overview", None) is bridge._collect_design_overview
        and getattr(extracted, "_resolved_shear_cleanup_is_executor_safe", None)
        is bridge._resolved_shear_cleanup_is_executor_safe
    )
    checks["bridge_runtime_delegates_with_arguments"] = (
        returned == (True, None)
        and call_record.get("item") == {"action_type": "apply_resolved_candidate"}
        and call_record.get("state") == {"D": 600}
        and call_record.get("bound_snapshot") is True
        and call_record.get("bound_resolve_updates") is True
        and call_record.get("bound_preview") is True
        and call_record.get("bound_overview") is True
        and call_record.get("bound_executor_safe") is True
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
    json_path = ARTIFACTS / f"inputs_page_executor_actionability_contract_extraction_{stamp}.json"
    report_path = AUDITS / f"inputs_page_executor_actionability_contract_extraction_{stamp}.md"
    json_path.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Executor Actionability Contract Extraction",
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
