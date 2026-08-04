"""Verify guidance-intent extraction from the Inputs app bridge."""

from __future__ import annotations

import ast
import json
import sys
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BRIDGE = ROOT / "inputs_page_app_contract_bridge.py"
MODULE = ROOT / "inputs_page_modules" / "design_guide" / "guidance_intent.py"
ARTIFACTS = ROOT / "artifacts" / "verification"
AUDITS = ROOT / "artifacts" / "audits"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _function_node(source: str, name: str) -> ast.FunctionDef:
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    raise AssertionError(f"{name} not found")


def main() -> int:
    bridge_source = BRIDGE.read_text(encoding="utf-8")
    module_source = MODULE.read_text(encoding="utf-8")

    bridge_node = _function_node(bridge_source, "_derive_design_guide_guidance_intent")
    module_node = _function_node(module_source, "_derive_design_guide_guidance_intent")
    bridge_body = ast.get_source_segment(bridge_source, bridge_node) or ""

    checks: dict[str, bool] = {
        "bridge_wrapper_is_small": (bridge_node.end_lineno or bridge_node.lineno) - bridge_node.lineno + 1 <= 14,
        "bridge_binds_dependencies": "_bind_guidance_intent_dependencies(globals())" in bridge_body,
        "bridge_delegates_to_extracted_module": "_derive_design_guide_guidance_intent_extracted" in bridge_body,
        "module_contains_extracted_body": (module_node.end_lineno or module_node.lineno) - module_node.lineno + 1 >= 55,
        "module_has_dependency_binder": "def bind_guidance_intent_dependencies" in module_source,
        "module_does_not_import_streamlit": "import streamlit" not in module_source,
        "module_does_not_import_bridge": "inputs_page_app_contract_bridge" not in module_source,
        "module_keeps_guidance_intent_contract_surface": all(
            token in module_source
            for token in (
                "_guidance_item_material_updates",
                "_guidance_item_is_shear_only_cleanup",
                "_guidance_shear_is_non_governing_conservative",
                "_guidance_update_is_lighter_or_smaller",
                "_is_in_target_zone_with_eps",
                "required_fix",
                "efficiency_tightening",
                "optional_cleanup",
                "already_efficient",
                "advisory_warning",
            )
        ),
    }

    import inputs_page_app_contract_bridge as bridge
    from inputs_page_modules.design_guide import guidance_intent as extracted

    original = bridge._derive_design_guide_guidance_intent_extracted
    call_record: dict = {}

    def _fake_extracted(item: dict, *, state: dict, overview: dict | None, efficiency_state: dict | None) -> str:
        call_record.update(
            {
                "item": dict(item),
                "state": dict(state),
                "overview": dict(overview or {}),
                "efficiency_state": dict(efficiency_state or {}),
                "bound_target_min": getattr(extracted, "EFFICIENCY_TARGET_UTIL_MIN", None)
                is bridge.EFFICIENCY_TARGET_UTIL_MIN,
                "bound_material_updates": getattr(extracted, "_guidance_item_material_updates", None)
                is bridge._guidance_item_material_updates,
                "bound_shear_cleanup": getattr(extracted, "_guidance_item_is_shear_only_cleanup", None)
                is bridge._guidance_item_is_shear_only_cleanup,
                "bound_target_zone": getattr(extracted, "_is_in_target_zone_with_eps", None)
                is bridge._is_in_target_zone_with_eps,
            }
        )
        return "fake_intent"

    try:
        bridge._derive_design_guide_guidance_intent_extracted = _fake_extracted
        returned = bridge._derive_design_guide_guidance_intent(
            {"title": "A"},
            state={"D": 650},
            overview={"worst_util": 0.82},
            efficiency_state={"classification": "ok"},
        )
    finally:
        bridge._derive_design_guide_guidance_intent_extracted = original

    checks["bridge_runtime_binds_module_globals"] = (
        getattr(extracted, "EFFICIENCY_TARGET_UTIL_MIN", None) is bridge.EFFICIENCY_TARGET_UTIL_MIN
        and getattr(extracted, "_guidance_item_material_updates", None) is bridge._guidance_item_material_updates
        and getattr(extracted, "_guidance_item_is_shear_only_cleanup", None)
        is bridge._guidance_item_is_shear_only_cleanup
        and getattr(extracted, "_is_in_target_zone_with_eps", None) is bridge._is_in_target_zone_with_eps
    )
    checks["bridge_runtime_delegates_with_arguments"] = (
        returned == "fake_intent"
        and call_record.get("item") == {"title": "A"}
        and call_record.get("state") == {"D": 650}
        and call_record.get("overview") == {"worst_util": 0.82}
        and call_record.get("efficiency_state") == {"classification": "ok"}
        and call_record.get("bound_target_min") is True
        and call_record.get("bound_material_updates") is True
        and call_record.get("bound_shear_cleanup") is True
        and call_record.get("bound_target_zone") is True
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
    json_path = ARTIFACTS / f"inputs_page_guidance_intent_extraction_{stamp}.json"
    report_path = AUDITS / f"inputs_page_guidance_intent_extraction_{stamp}.md"
    json_path.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Guidance Intent Extraction",
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
