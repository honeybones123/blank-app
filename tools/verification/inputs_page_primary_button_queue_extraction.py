"""Verify primary Design Guide CTA queue extraction from the Inputs app bridge."""

from __future__ import annotations

import ast
import json
import sys
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BRIDGE = ROOT / "inputs_page_app_contract_bridge.py"
MODULE = ROOT / "inputs_page_modules" / "design_guide" / "primary_button_queue.py"
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

    bridge_node = _function_node(bridge_source, "_queue_primary_design_guide_button_action")
    module_node = _function_node(module_source, "_queue_primary_design_guide_button_action")
    bridge_body = ast.get_source_segment(bridge_source, bridge_node) or ""

    checks: dict[str, bool] = {
        "bridge_wrapper_is_small": (bridge_node.end_lineno or bridge_node.lineno) - bridge_node.lineno + 1 <= 14,
        "bridge_binds_dependencies": "_bind_primary_button_queue_dependencies(globals())" in bridge_body,
        "bridge_delegates_to_extracted_module": "_queue_primary_design_guide_button_action_extracted" in bridge_body,
        "module_contains_extracted_body": (module_node.end_lineno or module_node.lineno) - module_node.lineno + 1 > 190,
        "module_has_dependency_binder": "def bind_primary_button_queue_dependencies" in module_source,
        "module_does_not_import_streamlit": "import streamlit" not in module_source,
        "module_does_not_import_bridge": "inputs_page_app_contract_bridge" not in module_source,
        "module_keeps_cta_session_behavior": (
            "st.session_state" in module_source
            and "apply_recommendation_result(rec_dict)" in module_source
            and "handle_auto_design" in module_source
        ),
    }

    import inputs_page_app_contract_bridge as bridge
    from inputs_page_modules.design_guide import primary_button_queue as extracted

    original = bridge._queue_primary_design_guide_button_action_extracted
    call_record: dict = {}

    def _fake_extracted(
        rec: dict,
        primary_route_target: str,
        apply_label: str,
        button_contract: dict | None = None,
    ) -> None:
        call_record.update(
            {
                "rec": dict(rec),
                "primary_route_target": primary_route_target,
                "apply_label": apply_label,
                "button_contract": dict(button_contract or {}),
                "bound_st": getattr(extracted, "st", None) is bridge.st,
                "bound_time": getattr(extracted, "time", None) is bridge.time,
            }
        )

    try:
        bridge._queue_primary_design_guide_button_action_extracted = _fake_extracted
        returned = bridge._queue_primary_design_guide_button_action(
            {"title": "Apply"},
            "handle_apply_buttons",
            "Apply recommendation",
            button_contract={"action_type": "apply_resolved_candidate"},
        )
    finally:
        bridge._queue_primary_design_guide_button_action_extracted = original

    checks["bridge_runtime_binds_module_globals"] = (
        getattr(extracted, "st", None) is bridge.st
        and getattr(extracted, "sys", None) is bridge.sys
        and getattr(extracted, "time", None) is bridge.time
        and getattr(extracted, "apply_recommendation_result", None)
        is bridge.apply_recommendation_result
    )
    checks["bridge_runtime_delegates_with_arguments"] = (
        returned is None
        and call_record.get("rec") == {"title": "Apply"}
        and call_record.get("primary_route_target") == "handle_apply_buttons"
        and call_record.get("apply_label") == "Apply recommendation"
        and call_record.get("button_contract") == {"action_type": "apply_resolved_candidate"}
        and call_record.get("bound_st") is True
        and call_record.get("bound_time") is True
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
    json_path = ARTIFACTS / f"inputs_page_primary_button_queue_extraction_{stamp}.json"
    report_path = AUDITS / f"inputs_page_primary_button_queue_extraction_{stamp}.md"
    json_path.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Primary Button Queue Extraction",
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
