"""Verify canonical design-state pack extraction from the Inputs app bridge."""

from __future__ import annotations

import ast
import json
import sys
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BRIDGE = ROOT / "inputs_page_app_contract_bridge.py"
MODULE = ROOT / "inputs_page_modules" / "app_bridge" / "canonical_design_state_pack.py"
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

    bridge_node = _function_node(bridge_source, "_build_canonical_design_state_pack_for_app_bridge")
    module_node = _function_node(module_source, "_build_canonical_design_state_pack_for_app_bridge")
    bridge_body = ast.get_source_segment(bridge_source, bridge_node) or ""

    checks: dict[str, bool] = {
        "bridge_wrapper_is_tiny": (bridge_node.end_lineno or bridge_node.lineno) - bridge_node.lineno + 1 <= 3,
        "bridge_binds_dependencies": "_bind_canonical_design_state_pack_dependencies(globals())" in bridge_body,
        "bridge_delegates_to_extracted_module": "_build_canonical_design_state_pack_for_app_bridge_extracted" in bridge_body,
        "module_contains_extracted_body": (module_node.end_lineno or module_node.lineno) - module_node.lineno + 1 >= 114,
        "module_has_dependency_binder": "def bind_canonical_design_state_pack_dependencies" in module_source,
        "module_does_not_import_streamlit": "import streamlit" not in module_source,
        "module_does_not_import_bridge": "inputs_page_app_contract_bridge" not in module_source,
        "module_keeps_canonical_pack_contract_surface": all(
            token in module_source
            for token in (
                "bot_rows_resolved",
                "top_rows_resolved",
                "bot_bar_coords",
                "top_bar_coords",
                "resolved_longitudinal_bars",
                "Ast_top_web",
                "Ast_bottom_flange",
                "canonical_pack_built",
                "canonical_pack_valid",
                "canonical_pack_source",
                "shared_rebuilt",
                "no_bars_resolved",
                "resolve_longitudinal_bars",
            )
        ),
    }

    import inputs_page_app_contract_bridge as bridge
    from inputs_page_modules.app_bridge import canonical_design_state_pack as extracted

    original = bridge._build_canonical_design_state_pack_for_app_bridge_extracted
    call_record: dict = {}

    def _fake_extracted(state: dict) -> dict:
        call_record.update(
            {
                "state": dict(state),
                "bound_snapshot": getattr(extracted, "_guidance_state_snapshot_for_summary_bridge", None)
                is bridge._guidance_state_snapshot_for_summary_bridge,
                "bound_shape": getattr(extracted, "_canonical_shape_name_and_dims_for_app_bridge", None)
                is bridge._canonical_shape_name_and_dims_for_app_bridge,
                "bound_invalid": getattr(extracted, "_invalid_canonical_design_state_pack_for_app_bridge", None)
                is bridge._invalid_canonical_design_state_pack_for_app_bridge,
                "bound_section_layout": getattr(extracted, "compute_section_layout_pure", None)
                is bridge.compute_section_layout_pure,
                "bound_bars": getattr(extracted, "resolve_longitudinal_bars_from_layout", None)
                is bridge.resolve_longitudinal_bars_from_layout,
            }
        )
        return {"canonical_pack_valid": True}

    try:
        bridge._build_canonical_design_state_pack_for_app_bridge_extracted = _fake_extracted
        returned = bridge._build_canonical_design_state_pack_for_app_bridge({"D": 600})
    finally:
        bridge._build_canonical_design_state_pack_for_app_bridge_extracted = original

    checks["bridge_runtime_binds_module_globals"] = (
        getattr(extracted, "_guidance_state_snapshot_for_summary_bridge", None)
        is bridge._guidance_state_snapshot_for_summary_bridge
        and getattr(extracted, "_canonical_shape_name_and_dims_for_app_bridge", None)
        is bridge._canonical_shape_name_and_dims_for_app_bridge
        and getattr(extracted, "_invalid_canonical_design_state_pack_for_app_bridge", None)
        is bridge._invalid_canonical_design_state_pack_for_app_bridge
        and getattr(extracted, "compute_section_layout_pure", None) is bridge.compute_section_layout_pure
        and getattr(extracted, "resolve_longitudinal_bars_from_layout", None)
        is bridge.resolve_longitudinal_bars_from_layout
    )
    checks["bridge_runtime_delegates_with_arguments"] = (
        returned == {"canonical_pack_valid": True}
        and call_record.get("state") == {"D": 600}
        and call_record.get("bound_snapshot") is True
        and call_record.get("bound_shape") is True
        and call_record.get("bound_invalid") is True
        and call_record.get("bound_section_layout") is True
        and call_record.get("bound_bars") is True
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
    json_path = ARTIFACTS / f"inputs_page_canonical_design_state_pack_extraction_{stamp}.json"
    report_path = AUDITS / f"inputs_page_canonical_design_state_pack_extraction_{stamp}.md"
    json_path.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Canonical Design State Pack Extraction",
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
