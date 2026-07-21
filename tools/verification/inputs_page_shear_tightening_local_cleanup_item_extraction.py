"""Verify shear tightening local-cleanup item extraction from the Inputs bridge."""

from __future__ import annotations

import ast
import json
import sys
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BRIDGE = ROOT / "inputs_page_app_contract_bridge.py"
MODULE = ROOT / "inputs_page_modules" / "design_guide" / "shear_local_cleanup.py"
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

    name = "_shear_tightening_as_local_cleanup_item"
    bridge_node = _function_node(bridge_source, name)
    module_node = _function_node(module_source, name)
    bridge_body = ast.get_source_segment(bridge_source, bridge_node) or ""

    checks: dict[str, bool] = {
        "bridge_wrapper_is_small": (bridge_node.end_lineno or bridge_node.lineno) - bridge_node.lineno + 1 <= 9,
        "bridge_binds_dependencies": "_bind_shear_local_cleanup_dependencies(globals())" in bridge_body,
        "bridge_delegates_to_extracted_module": "_shear_tightening_as_local_cleanup_item_extracted" in bridge_body,
        "module_contains_extracted_body": (module_node.end_lineno or module_node.lineno) - module_node.lineno + 1 >= 95,
        "module_has_dependency_binder": "def bind_shear_local_cleanup_dependencies" in module_source,
        "module_exports_packager": '"_shear_tightening_as_local_cleanup_item"' in module_source,
        "module_does_not_import_streamlit": "streamlit" not in module_source and "import st" not in module_source,
        "module_does_not_read_session_state": ".session_state" not in module_source,
        "module_does_not_import_bridge": "inputs_page_app_contract_bridge" not in module_source,
        "module_keeps_packaging_contract": all(
            token in module_source
            for token in (
                "Design is safe - optional cleanup available",
                "Shear reserve is high. Optional cleanup can relax the link layout.",
                "apply_resolved_candidate",
                "increase_link_spacing",
                "_guidance_cleanup_candidate_id",
                "_promote_guidance_item_to_resolved_candidate",
                "_best_safe_shear_local_cleanup_recommendation",
            )
        ),
    }

    import inputs_page_app_contract_bridge as bridge
    from inputs_page_modules.design_guide import shear_local_cleanup as extracted

    original = bridge._shear_tightening_as_local_cleanup_item_extracted
    call_record: dict = {}

    def _fake_extracted(
        state: dict,
        overview: dict,
        efficiency_state: dict | None,
    ) -> dict:
        call_record.update(
            {
                "state": dict(state),
                "overview": dict(overview),
                "efficiency_state": dict(efficiency_state or {}),
                "bound_resolve_actions": getattr(extracted, "_resolve_design_actions_from_state", None)
                is bridge._resolve_design_actions_from_state,
                "bound_guidance_item": getattr(extracted, "_guidance_item", None)
                is bridge._guidance_item,
                "bound_promote": getattr(extracted, "_promote_guidance_item_to_resolved_candidate", None)
                is bridge._promote_guidance_item_to_resolved_candidate,
                "bound_cleanup_id": getattr(extracted, "_guidance_cleanup_candidate_id", None)
                is bridge._guidance_cleanup_candidate_id,
            }
        )
        return {"title_main": "Shear cleanup"}

    try:
        bridge._shear_tightening_as_local_cleanup_item_extracted = _fake_extracted
        returned = bridge._shear_tightening_as_local_cleanup_item(
            {"D": 650},
            {"utils": {"shear": 0.42}},
            {"shear_cleanup_possible": True},
        )
    finally:
        bridge._shear_tightening_as_local_cleanup_item_extracted = original

    checks["bridge_runtime_binds_module_globals"] = (
        getattr(extracted, "_resolve_design_actions_from_state", None)
        is bridge._resolve_design_actions_from_state
        and getattr(extracted, "_guidance_item", None) is bridge._guidance_item
        and getattr(extracted, "_promote_guidance_item_to_resolved_candidate", None)
        is bridge._promote_guidance_item_to_resolved_candidate
        and getattr(extracted, "_guidance_cleanup_candidate_id", None)
        is bridge._guidance_cleanup_candidate_id
    )
    checks["bridge_runtime_delegates_with_arguments"] = (
        returned == {"title_main": "Shear cleanup"}
        and call_record.get("state") == {"D": 650}
        and call_record.get("overview") == {"utils": {"shear": 0.42}}
        and call_record.get("efficiency_state") == {"shear_cleanup_possible": True}
        and call_record.get("bound_resolve_actions") is True
        and call_record.get("bound_guidance_item") is True
        and call_record.get("bound_promote") is True
        and call_record.get("bound_cleanup_id") is True
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
    json_path = ARTIFACTS / f"inputs_page_shear_tightening_local_cleanup_item_extraction_{stamp}.json"
    report_path = AUDITS / f"inputs_page_shear_tightening_local_cleanup_item_extraction_{stamp}.md"
    json_path.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Shear Tightening Local-Cleanup Item Extraction",
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
