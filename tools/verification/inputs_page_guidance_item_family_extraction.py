"""Verify Design Guide guidance-item family extraction."""

from __future__ import annotations

import ast
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
BRIDGE = ROOT / "inputs_page_app_contract_bridge.py"
MODULE = ROOT / "inputs_page_modules" / "design_guide" / "item_identity.py"
INIT = ROOT / "inputs_page_modules" / "design_guide" / "__init__.py"
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
    init_source = INIT.read_text(encoding="utf-8")
    bridge_node = _function_node(bridge_source, "_guidance_item_family")
    module_node = _function_node(module_source, "_guidance_item_family")
    bridge_body = ast.get_source_segment(bridge_source, bridge_node) or ""

    import inputs_page_app_contract_bridge as bridge
    from inputs_page_modules.design_guide.item_identity import _guidance_item_family as extracted_family
    import inputs_page_modules.design_guide as design_guide_package

    cases: dict[str, Any] = {
        "unknown": extracted_family(None),
        "explicit_special": extracted_family({"selected_family_id": "SHEAR_OVERDESIGN_GOVERNS"}),
        "payload_special": extracted_family(
            {"action_payload": {"apply_payload_family_id": "BENDING_FAIL_SHEAR_OVERDESIGN_GOVERNS"}}
        ),
        "shear_action": extracted_family({"action_type": "reduce_link_spacing"}),
        "bending_action": extracted_family({"action_type": "increase_depth"}),
        "combined_updates": extracted_family(
            {"action_payload": {"updates": {"s_lig": 150, "D": 650}}}
        ),
        "shear_updates": extracted_family({"action_payload": {"updates": {"lig_legs": 4}}}),
        "bottom_updates": extracted_family({"action_payload": {"resolved_candidate_updates": {"bot1_count": 6}}}),
        "geom_updates": extracted_family({"action_payload": {"updates": {"b": 350}}}),
        "other": extracted_family({"action_payload": {"updates": {"foo": 1}}}),
    }

    original = bridge._guidance_item_family_extracted
    delegate_call: dict[str, Any] = {}

    def _fake_extracted(item: dict | None) -> str:
        delegate_call["item"] = dict(item or {})
        delegate_call["module_owner"] = extracted_family is original
        return "fake_family"

    try:
        bridge._guidance_item_family_extracted = _fake_extracted
        wrapped = bridge._guidance_item_family({"action_type": "increase_depth"})
    finally:
        bridge._guidance_item_family_extracted = original

    checks: dict[str, bool] = {
        "bridge_wrapper_is_tiny": (bridge_node.end_lineno or bridge_node.lineno) - bridge_node.lineno + 1 <= 2,
        "bridge_delegates_to_extracted_module": "_guidance_item_family_extracted" in bridge_body,
        "module_contains_extracted_body": (module_node.end_lineno or module_node.lineno) - module_node.lineno + 1 >= 65,
        "module_is_pure_no_streamlit": "streamlit" not in module_source and "st." not in module_source,
        "module_does_not_import_bridge": "inputs_page_app_contract_bridge" not in module_source,
        "package_exports_family_helper": "_guidance_item_family" in init_source
        and getattr(design_guide_package, "_guidance_item_family", None) is extracted_family,
        "classification_cases": cases == {
            "unknown": "unknown",
            "explicit_special": "SHEAR_OVERDESIGN_GOVERNS",
            "payload_special": "BENDING_FAIL_SHEAR_OVERDESIGN_GOVERNS",
            "shear_action": "shear",
            "bending_action": "bending",
            "combined_updates": "combined",
            "shear_updates": "shear",
            "bottom_updates": "bending",
            "geom_updates": "bending",
            "other": "other",
        },
        "bridge_runtime_delegates": wrapped == "fake_family"
        and delegate_call.get("item") == {"action_type": "increase_depth"},
        "bridge_runtime_preserves_module_owner": delegate_call.get("module_owner") is True,
    }

    result = {
        "status": "PASS" if all(checks.values()) else "FAIL",
        "checks": checks,
        "cases": cases,
        "bridge_wrapper_lines": (bridge_node.end_lineno or bridge_node.lineno) - bridge_node.lineno + 1,
        "module_function_lines": (module_node.end_lineno or module_node.lineno) - module_node.lineno + 1,
    }

    stamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    AUDITS.mkdir(parents=True, exist_ok=True)
    json_path = ARTIFACTS / f"inputs_page_guidance_item_family_extraction_{stamp}.json"
    report_path = AUDITS / f"inputs_page_guidance_item_family_extraction_{stamp}.md"
    json_path.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Guidance Item Family Extraction",
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
