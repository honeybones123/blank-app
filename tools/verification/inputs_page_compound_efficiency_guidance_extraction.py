"""Verify compound efficiency guidance extraction from the Inputs app bridge."""

from __future__ import annotations

import ast
import json
import sys
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BRIDGE = ROOT / "inputs_page_app_contract_bridge.py"
MODULE = ROOT / "inputs_page_modules" / "design_guide" / "compound_strengthening.py"
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

    name = "_try_compound_efficiency_guidance_item"
    bridge_node = _function_node(bridge_source, name)
    module_node = _function_node(module_source, name)
    bridge_body = ast.get_source_segment(bridge_source, bridge_node) or ""

    checks: dict[str, bool] = {
        "bridge_wrapper_is_small": (bridge_node.end_lineno or bridge_node.lineno) - bridge_node.lineno + 1 <= 5,
        "bridge_binds_dependencies": "_bind_compound_strengthening_dependencies(globals())" in bridge_body,
        "bridge_delegates_to_extracted_module": "_try_compound_efficiency_guidance_item_extracted" in bridge_body,
        "module_contains_extracted_body": (module_node.end_lineno or module_node.lineno) - module_node.lineno + 1 >= 98,
        "module_has_dependency_binder": "def bind_compound_strengthening_dependencies" in module_source,
        "module_exports_compound_efficiency": '"_try_compound_efficiency_guidance_item"' in module_source,
        "module_does_not_import_streamlit": "streamlit" not in module_source and "import st" not in module_source,
        "module_does_not_read_session_state": ".session_state" not in module_source,
        "module_does_not_import_bridge": "inputs_page_app_contract_bridge" not in module_source,
        "module_keeps_compound_efficiency_contract": all(
            token in module_source
            for token in (
                "compound_efficiency_seed",
                "compound_efficiency_rank",
                "apply_compound_guidance",
                "EFFICIENCY",
                "_candidate_is_growth_move",
                "_compound_efficiency_incoherent",
                "_efficiency_distance_to_target_band",
            )
        ),
    }

    import inputs_page_app_contract_bridge as bridge
    from inputs_page_modules.design_guide import compound_strengthening as extracted

    original = bridge._try_compound_efficiency_guidance_item_extracted
    call_record: dict = {}

    def _fake_extracted(state: dict, efficiency_state: dict) -> dict:
        call_record.update(
            {
                "state": dict(state),
                "efficiency_state": dict(efficiency_state),
                "bound_full_eval": getattr(extracted, "evaluate_candidate_full", None)
                is bridge.evaluate_candidate_full,
                "bound_bottom_updates": getattr(extracted, "_bottom_arrangement_to_shared_updates", None)
                is bridge._bottom_arrangement_to_shared_updates,
                "bound_growth_rejection": getattr(extracted, "_log_efficiency_growth_rejection", None)
                is bridge._log_efficiency_growth_rejection,
                "bound_guidance_item": getattr(extracted, "_guidance_item", None)
                is bridge._guidance_item,
            }
        )
        return {"title_main": "Compound efficiency"}

    try:
        bridge._try_compound_efficiency_guidance_item_extracted = _fake_extracted
        returned = bridge._try_compound_efficiency_guidance_item(
            {"D": 650},
            {"classification": "low", "is_efficiency_reduction_mode": True},
        )
    finally:
        bridge._try_compound_efficiency_guidance_item_extracted = original

    checks["bridge_runtime_binds_module_globals"] = (
        getattr(extracted, "evaluate_candidate_full", None) is bridge.evaluate_candidate_full
        and getattr(extracted, "_bottom_arrangement_to_shared_updates", None)
        is bridge._bottom_arrangement_to_shared_updates
        and getattr(extracted, "_log_efficiency_growth_rejection", None)
        is bridge._log_efficiency_growth_rejection
        and getattr(extracted, "_guidance_item", None) is bridge._guidance_item
    )
    checks["bridge_runtime_delegates_with_arguments"] = (
        returned == {"title_main": "Compound efficiency"}
        and call_record.get("state") == {"D": 650}
        and call_record.get("efficiency_state")
        == {"classification": "low", "is_efficiency_reduction_mode": True}
        and call_record.get("bound_full_eval") is True
        and call_record.get("bound_bottom_updates") is True
        and call_record.get("bound_growth_rejection") is True
        and call_record.get("bound_guidance_item") is True
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
    json_path = ARTIFACTS / f"inputs_page_compound_efficiency_guidance_extraction_{stamp}.json"
    report_path = AUDITS / f"inputs_page_compound_efficiency_guidance_extraction_{stamp}.md"
    json_path.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Compound Efficiency Guidance Extraction",
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
