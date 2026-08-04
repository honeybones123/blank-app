"""Verify summary-state resolver extraction from the Inputs app bridge."""

from __future__ import annotations

import ast
import json
import sys
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BRIDGE = ROOT / "inputs_page_app_contract_bridge.py"
MODULE = ROOT / "inputs_page_modules" / "summaries" / "summary_state_resolver.py"
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

    bridge_node = _function_node(bridge_source, "_resolved_inputs_summary_state")
    module_node = _function_node(module_source, "_resolved_inputs_summary_state")
    bridge_body = ast.get_source_segment(bridge_source, bridge_node) or ""

    checks: dict[str, bool] = {
        "bridge_wrapper_is_tiny": (bridge_node.end_lineno or bridge_node.lineno) - bridge_node.lineno + 1 <= 3,
        "bridge_binds_dependencies": "_bind_summary_state_resolver_dependencies(globals())" in bridge_body,
        "bridge_delegates_to_extracted_module": "_resolved_inputs_summary_state_extracted" in bridge_body,
        "module_contains_extracted_body": (module_node.end_lineno or module_node.lineno) - module_node.lineno + 1 >= 125,
        "module_has_dependency_binder": "def bind_summary_state_resolver_dependencies" in module_source,
        "module_does_not_import_streamlit": "import streamlit" not in module_source,
        "module_does_not_import_bridge": "inputs_page_app_contract_bridge" not in module_source,
        "module_keeps_summary_state_contract_surface": all(
            token in module_source
            for token in (
                "build_inputs_summary_source_shaping_snapshot",
                "inputs_summary_source_shaping_delegated",
                "shared_only_suppressed",
                "build_inputs_summary_debug_payload_snapshot",
                "summary_design_action_result_overlay_count",
                "row_model_legacy_sync_applied",
                "build_inputs_summary_state_mode_marker_snapshot",
                "_inputs_summary_state_mode",
                "inputs_summary_state_mode_marker_delegated",
                "inputs_page.summary_state_build",
            )
        ),
    }

    import inputs_page_app_contract_bridge as bridge
    from inputs_page_modules.summaries import summary_state_resolver as extracted

    original = bridge._resolved_inputs_summary_state_extracted
    call_record: dict = {}

    def _fake_extracted() -> tuple[dict, dict]:
        call_record.update(
            {
                "bound_st": getattr(extracted, "st", None) is bridge.st,
                "bound_source_shape": getattr(extracted, "build_inputs_summary_source_shaping_snapshot", None)
                is bridge.build_inputs_summary_source_shaping_snapshot,
                "bound_debug_payload": getattr(extracted, "build_inputs_summary_debug_payload_snapshot", None)
                is bridge.build_inputs_summary_debug_payload_snapshot,
                "bound_mode_marker": getattr(extracted, "build_inputs_summary_state_mode_marker_snapshot", None)
                is bridge.build_inputs_summary_state_mode_marker_snapshot,
                "bound_ux_probe": getattr(extracted, "ux_probe_record", None) is bridge.ux_probe_record,
            }
        )
        return {"D": 600}, {"summary_state_source": "fake"}

    try:
        bridge._resolved_inputs_summary_state_extracted = _fake_extracted
        returned = bridge._resolved_inputs_summary_state()
    finally:
        bridge._resolved_inputs_summary_state_extracted = original

    checks["bridge_runtime_binds_module_globals"] = (
        getattr(extracted, "st", None) is bridge.st
        and getattr(extracted, "build_inputs_summary_source_shaping_snapshot", None)
        is bridge.build_inputs_summary_source_shaping_snapshot
        and getattr(extracted, "build_inputs_summary_debug_payload_snapshot", None)
        is bridge.build_inputs_summary_debug_payload_snapshot
        and getattr(extracted, "build_inputs_summary_state_mode_marker_snapshot", None)
        is bridge.build_inputs_summary_state_mode_marker_snapshot
        and getattr(extracted, "ux_probe_record", None) is bridge.ux_probe_record
    )
    checks["bridge_runtime_delegates_with_arguments"] = (
        returned == ({"D": 600}, {"summary_state_source": "fake"})
        and call_record.get("bound_st") is True
        and call_record.get("bound_source_shape") is True
        and call_record.get("bound_debug_payload") is True
        and call_record.get("bound_mode_marker") is True
        and call_record.get("bound_ux_probe") is True
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
    json_path = ARTIFACTS / f"inputs_page_summary_state_resolver_extraction_{stamp}.json"
    report_path = AUDITS / f"inputs_page_summary_state_resolver_extraction_{stamp}.md"
    json_path.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Summary State Resolver Extraction",
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
