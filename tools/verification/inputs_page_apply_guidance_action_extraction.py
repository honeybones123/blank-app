"""Verify Apply guidance action extraction from the Inputs app bridge."""

from __future__ import annotations

import ast
import json
import sys
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BRIDGE = ROOT / "inputs_page_app_contract_bridge.py"
MODULE = ROOT / "inputs_page_modules" / "apply_guidance_action.py"
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

    bridge_node = _function_node(bridge_source, "apply_guidance_action")
    bridge_guided_node = _function_node(bridge_source, "apply_guided_solve_sequence")
    module_node = _function_node(module_source, "apply_guidance_action")
    module_guided_node = _function_node(module_source, "apply_guided_solve_sequence")
    bridge_body = ast.get_source_segment(bridge_source, bridge_node) or ""
    bridge_guided_body = ast.get_source_segment(bridge_source, bridge_guided_node) or ""
    dependency_section = module_source.partition("def bind_apply_guidance_action_dependencies")[0]

    checks: dict[str, bool] = {
        "bridge_wrapper_is_small": (bridge_node.end_lineno or bridge_node.lineno) - bridge_node.lineno + 1 <= 4,
        "bridge_binds_dependencies": "_bind_apply_guidance_action_dependencies(globals())" in bridge_body,
        "bridge_delegates_to_extracted_module": "_apply_guidance_action_extracted" in bridge_body,
        "bridge_guided_wrapper_is_small": (bridge_guided_node.end_lineno or bridge_guided_node.lineno) - bridge_guided_node.lineno + 1 <= 8,
        "bridge_guided_binds_dependencies": "_bind_apply_guidance_action_dependencies(globals())" in bridge_guided_body,
        "bridge_guided_delegates_to_extracted_module": "_apply_guided_solve_sequence_extracted" in bridge_guided_body,
        "module_contains_extracted_body": (module_node.end_lineno or module_node.lineno) - module_node.lineno + 1 > 190,
        "module_contains_guided_sequence_body": (module_guided_node.end_lineno or module_guided_node.lineno) - module_guided_node.lineno + 1 >= 65,
        "module_dependency_list_no_longer_binds_guided_sequence": '"apply_guided_solve_sequence"' not in dependency_section,
        "module_has_guided_sequence_low_level_dependencies": all(
            token in dependency_section
            for token in (
                '"_compute_geometry_recommendation"',
                '"_compute_bottom_reo_recommendation"',
                '"_compute_shear_recommendation"',
                '"_bottom_arrangement_to_shared_updates"',
                '"_updates_match_state"',
            )
        ),
        "module_has_dependency_binder": "def bind_apply_guidance_action_dependencies" in module_source,
        "module_does_not_import_streamlit": "import streamlit" not in module_source,
        "module_does_not_import_bridge": "inputs_page_app_contract_bridge" not in module_source,
        "module_keeps_apply_session_and_rerun_behavior": (
            "st.session_state" in module_source and "st.rerun()" in module_source
        ),
    }

    import inputs_page_app_contract_bridge as bridge
    import inputs_page_modules.apply_guidance_action as extracted

    sentinel = {"sentinel": "apply_guidance_action"}
    original = bridge._apply_guidance_action_extracted

    def _fake_extracted(action_type: str, payload: dict) -> dict:
        return {
            "result": dict(sentinel),
            "action_type": action_type,
            "payload": dict(payload),
            "bound_st": getattr(extracted, "st", None) is bridge.st,
            "bound_sys": getattr(extracted, "sys", None) is bridge.sys,
            "bound_time": getattr(extracted, "time", None) is bridge.time,
            "guided_sequence_owned_by_module": getattr(extracted, "apply_guided_solve_sequence", None)
            is bridge._apply_guided_solve_sequence_extracted,
            "guided_sequence_not_bridge_wrapper": getattr(extracted, "apply_guided_solve_sequence", None)
            is not bridge.apply_guided_solve_sequence,
        }

    try:
        bridge._apply_guidance_action_extracted = _fake_extracted
        wrapped = bridge.apply_guidance_action("apply_shear_recommendation", {"updates": {"s_lig": 250}})
    finally:
        bridge._apply_guidance_action_extracted = original

    checks["bridge_runtime_binds_module_globals"] = (
        getattr(extracted, "st", None) is bridge.st
        and getattr(extracted, "sys", None) is bridge.sys
        and getattr(extracted, "time", None) is bridge.time
        and getattr(extracted, "_apply_shared_updates", None) is bridge._apply_shared_updates
        and getattr(extracted, "apply_guided_solve_sequence", None)
        is bridge._apply_guided_solve_sequence_extracted
        and getattr(extracted, "apply_guided_solve_sequence", None)
        is not bridge.apply_guided_solve_sequence
        and getattr(extracted, "_compute_geometry_recommendation", None)
        is bridge._compute_geometry_recommendation
        and getattr(extracted, "_compute_bottom_reo_recommendation", None)
        is bridge._compute_bottom_reo_recommendation
        and getattr(extracted, "_compute_shear_recommendation", None)
        is bridge._compute_shear_recommendation
    )
    checks["bridge_runtime_delegates_with_arguments"] = (
        wrapped.get("result") == sentinel
        and wrapped.get("action_type") == "apply_shear_recommendation"
        and wrapped.get("payload") == {"updates": {"s_lig": 250}}
        and wrapped.get("bound_st") is True
        and wrapped.get("bound_sys") is True
        and wrapped.get("bound_time") is True
        and wrapped.get("guided_sequence_owned_by_module") is True
        and wrapped.get("guided_sequence_not_bridge_wrapper") is True
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
    json_path = ARTIFACTS / f"inputs_page_apply_guidance_action_extraction_{stamp}.json"
    report_path = AUDITS / f"inputs_page_apply_guidance_action_extraction_{stamp}.md"
    json_path.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Apply Guidance Action Extraction",
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
