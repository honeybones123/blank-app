"""Verify primary Apply payload recorder extraction from the Inputs app bridge."""

from __future__ import annotations

import ast
import json
import sys
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BRIDGE = ROOT / "inputs_page_app_contract_bridge.py"
MODULE = ROOT / "inputs_page_modules" / "design_guide" / "primary_apply_payload_recorder.py"
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

    bridge_node = _function_node(bridge_source, "_record_rendered_design_guide_primary_apply_payload")
    module_node = _function_node(module_source, "_record_rendered_design_guide_primary_apply_payload")
    bridge_body = ast.get_source_segment(bridge_source, bridge_node) or ""

    checks: dict[str, bool] = {
        "bridge_wrapper_is_small": (bridge_node.end_lineno or bridge_node.lineno) - bridge_node.lineno + 1 <= 14,
        "bridge_binds_dependencies": "_bind_primary_apply_payload_recorder_dependencies(globals())" in bridge_body,
        "bridge_delegates_to_extracted_module": "_record_rendered_design_guide_primary_apply_payload_extracted" in bridge_body,
        "module_contains_extracted_body": (module_node.end_lineno or module_node.lineno) - module_node.lineno + 1 >= 104,
        "module_has_dependency_binder": "def bind_primary_apply_payload_recorder_dependencies" in module_source,
        "module_does_not_import_streamlit": "import streamlit" not in module_source,
        "module_does_not_import_bridge": "inputs_page_app_contract_bridge" not in module_source,
        "module_keeps_primary_apply_payload_contract_surface": all(
            token in module_source
            for token in (
                "DESIGN_GUIDE_PRIMARY_APPLY_PAYLOAD_KEY",
                "DESIGN_GUIDE_DEBUG_BUNDLE_KEY",
                "_build_design_guide_primary_apply_payload",
                "_build_design_guide_button_contract_source_records",
                "_resolve_design_guide_button_contract_source_precedence",
                "_stamp_final_publication_cta_authority",
                "_set_design_guide_primary_payload_binding_audit",
                "winning_button_contract_source",
                "winning_update_payload_source",
                "winning_action_type_source",
                "winning_candidate_source",
                "final_cta_action_payload_summary",
                "final_publication_cta_hash",
                "stale_apply_payload_blocked",
                "canonical_primary_payload_exists",
                "legacy_fallback_used",
            )
        ),
    }

    import inputs_page_app_contract_bridge as bridge
    from inputs_page_modules.design_guide import primary_apply_payload_recorder as extracted

    original = bridge._record_rendered_design_guide_primary_apply_payload_extracted
    call_record: dict = {}

    def _fake_extracted(*, item: dict, rec: dict, button_contract: dict, state: dict) -> dict:
        call_record.update(
            {
                "item": dict(item),
                "rec": dict(rec),
                "button_contract": dict(button_contract),
                "state": dict(state),
                "bound_st": getattr(extracted, "st", None) is bridge.st,
                "bound_payload_builder": getattr(extracted, "_build_design_guide_primary_apply_payload", None)
                is bridge._build_design_guide_primary_apply_payload,
                "bound_source_records": getattr(
                    extracted,
                    "_build_design_guide_button_contract_source_records",
                    None,
                )
                is bridge._build_design_guide_button_contract_source_records,
                "bound_source_precedence": getattr(
                    extracted,
                    "_resolve_design_guide_button_contract_source_precedence",
                    None,
                )
                is bridge._resolve_design_guide_button_contract_source_precedence,
                "bound_audit": getattr(extracted, "_set_design_guide_primary_payload_binding_audit", None)
                is bridge._set_design_guide_primary_payload_binding_audit,
                "bound_primary_key": getattr(extracted, "DESIGN_GUIDE_PRIMARY_APPLY_PAYLOAD_KEY", None)
                is bridge.DESIGN_GUIDE_PRIMARY_APPLY_PAYLOAD_KEY,
            }
        )
        return {"candidate_id": "fake"}

    try:
        bridge._record_rendered_design_guide_primary_apply_payload_extracted = _fake_extracted
        returned = bridge._record_rendered_design_guide_primary_apply_payload(
            item={"title": "A"},
            rec={"label": "B"},
            button_contract={"candidate_id": "C"},
            state={"D": 650},
        )
    finally:
        bridge._record_rendered_design_guide_primary_apply_payload_extracted = original

    checks["bridge_runtime_binds_module_globals"] = (
        getattr(extracted, "st", None) is bridge.st
        and getattr(extracted, "_build_design_guide_primary_apply_payload", None)
        is bridge._build_design_guide_primary_apply_payload
        and getattr(extracted, "_build_design_guide_button_contract_source_records", None)
        is bridge._build_design_guide_button_contract_source_records
        and getattr(extracted, "_resolve_design_guide_button_contract_source_precedence", None)
        is bridge._resolve_design_guide_button_contract_source_precedence
        and getattr(extracted, "_set_design_guide_primary_payload_binding_audit", None)
        is bridge._set_design_guide_primary_payload_binding_audit
        and getattr(extracted, "DESIGN_GUIDE_PRIMARY_APPLY_PAYLOAD_KEY", None)
        is bridge.DESIGN_GUIDE_PRIMARY_APPLY_PAYLOAD_KEY
    )
    checks["bridge_runtime_delegates_with_arguments"] = (
        returned == {"candidate_id": "fake"}
        and call_record.get("item") == {"title": "A"}
        and call_record.get("rec") == {"label": "B"}
        and call_record.get("button_contract") == {"candidate_id": "C"}
        and call_record.get("state") == {"D": 650}
        and call_record.get("bound_st") is True
        and call_record.get("bound_payload_builder") is True
        and call_record.get("bound_source_records") is True
        and call_record.get("bound_source_precedence") is True
        and call_record.get("bound_audit") is True
        and call_record.get("bound_primary_key") is True
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
    json_path = ARTIFACTS / f"inputs_page_primary_apply_payload_recorder_extraction_{stamp}.json"
    report_path = AUDITS / f"inputs_page_primary_apply_payload_recorder_extraction_{stamp}.md"
    json_path.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Primary Apply Payload Recorder Extraction",
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
