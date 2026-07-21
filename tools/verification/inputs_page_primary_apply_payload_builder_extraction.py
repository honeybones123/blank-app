"""Verify primary Apply payload builder extraction from the Inputs app bridge."""

from __future__ import annotations

import ast
import json
import sys
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BRIDGE = ROOT / "inputs_page_app_contract_bridge.py"
MODULE = ROOT / "inputs_page_modules" / "design_guide" / "primary_apply_payload.py"
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

    bridge_node = _function_node(bridge_source, "_build_design_guide_primary_apply_payload")
    module_node = _function_node(module_source, "_build_design_guide_primary_apply_payload")
    bridge_body = ast.get_source_segment(bridge_source, bridge_node) or ""

    checks: dict[str, bool] = {
        "bridge_wrapper_is_small": (bridge_node.end_lineno or bridge_node.lineno) - bridge_node.lineno + 1 <= 14,
        "bridge_binds_dependencies": "_bind_primary_apply_payload_dependencies(globals())" in bridge_body,
        "bridge_delegates_to_extracted_module": "_build_design_guide_primary_apply_payload_extracted" in bridge_body,
        "module_contains_extracted_body": (module_node.end_lineno or module_node.lineno) - module_node.lineno + 1 >= 55,
        "module_has_dependency_binder": "def bind_primary_apply_payload_dependencies" in module_source,
        "module_does_not_import_streamlit": "streamlit" not in module_source and "import st" not in module_source,
        "module_does_not_read_session_state": ".session_state" not in module_source,
        "module_does_not_import_bridge": "inputs_page_app_contract_bridge" not in module_source,
        "module_keeps_apply_payload_contract_surface": all(
            token in module_source
            for token in (
                "_design_guide_button_contract_enabled",
                "_design_guide_apply_updates_current_state_guard",
                "_normalise_design_guide_candidate_id",
                "_design_guide_primary_apply_state_fingerprint",
                "button_contract_updates",
                "render_fingerprint",
                "design_guide_primary_render",
            )
        ),
    }

    import inputs_page_app_contract_bridge as bridge
    from inputs_page_modules.design_guide import primary_apply_payload as extracted

    original = bridge._build_design_guide_primary_apply_payload_extracted
    call_record: dict = {}

    def _fake_extracted(*, item: dict, rec: dict, button_contract: dict, state: dict) -> dict:
        call_record.update(
            {
                "item": dict(item),
                "rec": dict(rec),
                "button_contract": dict(button_contract),
                "state": dict(state),
                "bound_enabled": getattr(extracted, "_design_guide_button_contract_enabled", None)
                is bridge._design_guide_button_contract_enabled,
                "bound_guard": getattr(extracted, "_design_guide_apply_updates_current_state_guard", None)
                is bridge._design_guide_apply_updates_current_state_guard,
                "bound_fingerprint": getattr(extracted, "stable_fingerprint_for_payload", None)
                is bridge.stable_fingerprint_for_payload,
            }
        )
        return {"candidate_id": "fake"}

    try:
        bridge._build_design_guide_primary_apply_payload_extracted = _fake_extracted
        returned = bridge._build_design_guide_primary_apply_payload(
            item={"title": "A"},
            rec={"family": "bending"},
            button_contract={"updates": {"D": 650}},
            state={"D": 600},
        )
    finally:
        bridge._build_design_guide_primary_apply_payload_extracted = original

    checks["bridge_runtime_binds_module_globals"] = (
        getattr(extracted, "_design_guide_button_contract_enabled", None)
        is bridge._design_guide_button_contract_enabled
        and getattr(extracted, "_design_guide_apply_updates_current_state_guard", None)
        is bridge._design_guide_apply_updates_current_state_guard
        and getattr(extracted, "_normalise_design_guide_candidate_id", None)
        is bridge._normalise_design_guide_candidate_id
        and getattr(extracted, "stable_fingerprint_for_payload", None) is bridge.stable_fingerprint_for_payload
    )
    checks["bridge_runtime_delegates_with_arguments"] = (
        returned == {"candidate_id": "fake"}
        and call_record.get("item") == {"title": "A"}
        and call_record.get("rec") == {"family": "bending"}
        and call_record.get("button_contract") == {"updates": {"D": 650}}
        and call_record.get("state") == {"D": 600}
        and call_record.get("bound_enabled") is True
        and call_record.get("bound_guard") is True
        and call_record.get("bound_fingerprint") is True
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
    json_path = ARTIFACTS / f"inputs_page_primary_apply_payload_builder_extraction_{stamp}.json"
    report_path = AUDITS / f"inputs_page_primary_apply_payload_builder_extraction_{stamp}.md"
    json_path.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Primary Apply Payload Builder Extraction",
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
