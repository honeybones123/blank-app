"""Verify local-cleanup guidance evaluator extraction from the Inputs app bridge."""

from __future__ import annotations

import ast
import json
import sys
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BRIDGE = ROOT / "inputs_page_app_contract_bridge.py"
MODULE = ROOT / "inputs_page_modules" / "design_guide" / "local_cleanup_guidance_evaluator.py"
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

    bridge_node = _function_node(bridge_source, "_evaluate_local_cleanup_guidance_item")
    module_node = _function_node(module_source, "_evaluate_local_cleanup_guidance_item")
    bridge_body = ast.get_source_segment(bridge_source, bridge_node) or ""

    checks: dict[str, bool] = {
        "bridge_wrapper_is_small": (bridge_node.end_lineno or bridge_node.lineno) - bridge_node.lineno + 1 <= 16,
        "bridge_binds_dependencies": "_bind_local_cleanup_guidance_evaluator_dependencies(globals())" in bridge_body,
        "bridge_delegates_to_extracted_module": "_evaluate_local_cleanup_guidance_item_extracted" in bridge_body,
        "module_contains_extracted_body": (module_node.end_lineno or module_node.lineno) - module_node.lineno + 1 >= 145,
        "module_has_dependency_binder": "def bind_local_cleanup_guidance_evaluator_dependencies" in module_source,
        "module_does_not_import_streamlit": "import streamlit" not in module_source,
        "module_does_not_import_bridge": "inputs_page_app_contract_bridge" not in module_source,
        "module_keeps_local_cleanup_contract_surface": all(
            token in module_source
            for token in (
                "cleanup_no_material_update",
                "cleanup_no_net_material_efficiency",
                "cleanup_increases_geometry_without_section_reduction",
                "active_failure_needs_strengthening",
                "shear_cleanup_not_executor_safe",
                "cleanup_does_not_move_governing_utilisation_toward_target",
                "cleanup_not_executor_backed",
                "cleanup_not_executable",
            )
        ),
    }

    import inputs_page_app_contract_bridge as bridge
    from inputs_page_modules.design_guide import local_cleanup_guidance_evaluator as extracted

    original = bridge._evaluate_local_cleanup_guidance_item_extracted
    call_record: dict = {}

    def _fake_extracted(
        item: dict | None,
        *,
        state: dict,
        overview: dict,
        mode_config: dict,
        source: str,
    ) -> tuple[dict | None, dict]:
        call_record.update(
            {
                "item": dict(item or {}),
                "state": dict(state),
                "overview": dict(overview),
                "mode_config": dict(mode_config),
                "source": source,
                "bound_resolve_updates": getattr(extracted, "_resolve_recommendation_updates", None)
                is bridge._resolve_recommendation_updates,
                "bound_eval_candidate": getattr(extracted, "_evaluate_auto_design_candidate", None)
                is bridge._evaluate_auto_design_candidate,
                "bound_executor": getattr(extracted, "_guidance_executor_actionability_contract", None)
                is bridge._guidance_executor_actionability_contract,
                "bound_promote": getattr(extracted, "_promote_guidance_item_to_resolved_candidate", None)
                is bridge._promote_guidance_item_to_resolved_candidate,
                "bound_material_proxy": getattr(extracted, "_local_cleanup_material_proxy", None)
                is bridge._local_cleanup_material_proxy,
            }
        )
        return {"title_main": "fake cleanup"}, {"blocked_reason": None, "is_executable": True}

    try:
        bridge._evaluate_local_cleanup_guidance_item_extracted = _fake_extracted
        returned = bridge._evaluate_local_cleanup_guidance_item(
            {"action_type": "apply_resolved_candidate"},
            state={"D": 600},
            overview={"worst_util": 0.82},
            mode_config={"target_util_min": 0.85},
            source="focused_verifier",
        )
    finally:
        bridge._evaluate_local_cleanup_guidance_item_extracted = original

    checks["bridge_runtime_binds_module_globals"] = (
        getattr(extracted, "_resolve_recommendation_updates", None) is bridge._resolve_recommendation_updates
        and getattr(extracted, "_evaluate_auto_design_candidate", None) is bridge._evaluate_auto_design_candidate
        and getattr(extracted, "_guidance_executor_actionability_contract", None)
        is bridge._guidance_executor_actionability_contract
        and getattr(extracted, "_promote_guidance_item_to_resolved_candidate", None)
        is bridge._promote_guidance_item_to_resolved_candidate
        and getattr(extracted, "_local_cleanup_material_proxy", None) is bridge._local_cleanup_material_proxy
    )
    checks["bridge_runtime_delegates_with_arguments"] = (
        returned == ({"title_main": "fake cleanup"}, {"blocked_reason": None, "is_executable": True})
        and call_record.get("item") == {"action_type": "apply_resolved_candidate"}
        and call_record.get("state") == {"D": 600}
        and call_record.get("overview") == {"worst_util": 0.82}
        and call_record.get("mode_config") == {"target_util_min": 0.85}
        and call_record.get("source") == "focused_verifier"
        and call_record.get("bound_resolve_updates") is True
        and call_record.get("bound_eval_candidate") is True
        and call_record.get("bound_executor") is True
        and call_record.get("bound_promote") is True
        and call_record.get("bound_material_proxy") is True
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
    json_path = ARTIFACTS / f"inputs_page_local_cleanup_guidance_evaluator_extraction_{stamp}.json"
    report_path = AUDITS / f"inputs_page_local_cleanup_guidance_evaluator_extraction_{stamp}.md"
    json_path.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Local Cleanup Guidance Evaluator Extraction",
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
