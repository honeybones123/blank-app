"""Verify Design Guide action-update resolver extraction from the Inputs bridge."""

from __future__ import annotations

import ast
import json
import sys
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BRIDGE = ROOT / "inputs_page_app_contract_bridge.py"
MODULE = ROOT / "inputs_page_modules" / "design_guide" / "guidance_action_update_resolver.py"
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

    bridge_node = _function_node(bridge_source, "_guidance_action_updates")
    module_node = _function_node(module_source, "_guidance_action_updates")
    bridge_body = ast.get_source_segment(bridge_source, bridge_node) or ""

    checks: dict[str, bool] = {
        "bridge_wrapper_is_tiny": (bridge_node.end_lineno or bridge_node.lineno) - bridge_node.lineno + 1 <= 3,
        "bridge_binds_dependencies": "_bind_guidance_action_update_resolver_dependencies(globals())" in bridge_body,
        "bridge_delegates_to_extracted_module": "_guidance_action_updates_extracted" in bridge_body,
        "module_contains_extracted_body": (module_node.end_lineno or module_node.lineno) - module_node.lineno + 1 >= 128,
        "module_has_dependency_binder": "def bind_guidance_action_update_resolver_dependencies" in module_source,
        "module_does_not_import_streamlit": "import streamlit" not in module_source,
        "module_does_not_import_bridge": "inputs_page_app_contract_bridge" not in module_source,
        "module_keeps_action_update_contract_surface": all(
            token in module_source
            for token in (
                "apply_geometry_recommendation",
                "apply_bottom_recommendation",
                "apply_shear_recommendation",
                "reduce_bottom_reinforcement",
                "increase_link_spacing",
                "reduce_number_of_legs",
                "tighten_geometry",
                "increase_width",
                "reduce_link_spacing",
                "deflection_reduce_sustained_load",
                "reduce_bar_spacing",
                "updates_match_state",
            )
        ),
    }

    import inputs_page_app_contract_bridge as bridge
    from inputs_page_modules.design_guide import guidance_action_update_resolver as extracted

    original = bridge._guidance_action_updates_extracted
    call_record: dict = {}

    def _fake_extracted(action_type: str, payload: dict, *, state: dict | None = None) -> dict | None:
        call_record.update(
            {
                "action_type": action_type,
                "payload": dict(payload),
                "state": dict(state or {}),
                "bound_shared_snapshot": getattr(extracted, "_shared_state_snapshot", None)
                is bridge._shared_state_snapshot,
                "bound_payload_resolver": getattr(
                    extracted,
                    "_resolve_design_guide_controller_guidance_action_payload_updates",
                    None,
                )
                is bridge._resolve_design_guide_controller_guidance_action_payload_updates,
                "bound_generated_resolver": getattr(
                    extracted,
                    "_resolve_design_guide_controller_guidance_action_generated_updates",
                    None,
                )
                is bridge._resolve_design_guide_controller_guidance_action_generated_updates,
                "bound_bottom_arrangement": getattr(extracted, "_bottom_arrangement_to_shared_updates", None)
                is bridge._bottom_arrangement_to_shared_updates,
                "bound_updates_match": getattr(extracted, "_updates_match_state", None)
                is bridge._updates_match_state,
            }
        )
        return {"D": 650}

    try:
        bridge._guidance_action_updates_extracted = _fake_extracted
        returned = bridge._guidance_action_updates(
            "increase_depth",
            {"delta_mm": 50},
            state={"D": 600},
        )
    finally:
        bridge._guidance_action_updates_extracted = original

    checks["bridge_runtime_binds_module_globals"] = (
        getattr(extracted, "_shared_state_snapshot", None) is bridge._shared_state_snapshot
        and getattr(extracted, "_resolve_design_guide_controller_guidance_action_payload_updates", None)
        is bridge._resolve_design_guide_controller_guidance_action_payload_updates
        and getattr(extracted, "_resolve_design_guide_controller_guidance_action_generated_updates", None)
        is bridge._resolve_design_guide_controller_guidance_action_generated_updates
        and getattr(extracted, "_bottom_arrangement_to_shared_updates", None)
        is bridge._bottom_arrangement_to_shared_updates
        and getattr(extracted, "_updates_match_state", None) is bridge._updates_match_state
    )
    checks["bridge_runtime_delegates_with_arguments"] = (
        returned == {"D": 650}
        and call_record.get("action_type") == "increase_depth"
        and call_record.get("payload") == {"delta_mm": 50}
        and call_record.get("state") == {"D": 600}
        and call_record.get("bound_shared_snapshot") is True
        and call_record.get("bound_payload_resolver") is True
        and call_record.get("bound_generated_resolver") is True
        and call_record.get("bound_bottom_arrangement") is True
        and call_record.get("bound_updates_match") is True
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
    json_path = ARTIFACTS / f"inputs_page_guidance_action_update_resolver_extraction_{stamp}.json"
    report_path = AUDITS / f"inputs_page_guidance_action_update_resolver_extraction_{stamp}.md"
    json_path.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Guidance Action Update Resolver Extraction",
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
