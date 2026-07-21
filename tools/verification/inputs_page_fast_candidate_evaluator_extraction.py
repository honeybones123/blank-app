"""Verify fast candidate evaluator extraction from the Inputs app bridge."""

from __future__ import annotations

import ast
import json
import sys
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BRIDGE = ROOT / "inputs_page_app_contract_bridge.py"
MODULE = ROOT / "inputs_page_modules" / "app_bridge" / "fast_candidate_evaluator.py"
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

    bridge_node = _function_node(bridge_source, "evaluate_candidate_fast")
    module_node = _function_node(module_source, "evaluate_candidate_fast")
    bridge_body = ast.get_source_segment(bridge_source, bridge_node) or ""

    checks: dict[str, bool] = {
        "bridge_wrapper_is_tiny": (bridge_node.end_lineno or bridge_node.lineno) - bridge_node.lineno + 1 <= 3,
        "bridge_binds_dependencies": "_bind_fast_candidate_evaluator_dependencies(globals())" in bridge_body,
        "bridge_delegates_to_extracted_module": "_evaluate_candidate_fast_kernel_extracted" in bridge_body,
        "module_contains_extracted_body": (module_node.end_lineno or module_node.lineno) - module_node.lineno + 1 >= 130,
        "module_has_dependency_binder": "def bind_fast_candidate_evaluator_dependencies" in module_source,
        "module_does_not_import_streamlit": "import streamlit" not in module_source,
        "module_does_not_import_bridge": "inputs_page_app_contract_bridge" not in module_source,
        "module_keeps_fast_eval_contract_surface": all(
            token in module_source
            for token in (
                "fast_eval",
                "Fast Eval",
                "bending_components",
                "reo_congestion_index",
                "shear_density",
                "fail_count",
                "all_key_pass",
                "worst_util",
            )
        ),
    }

    import inputs_page_app_contract_bridge as bridge
    from inputs_page_modules.app_bridge import fast_candidate_evaluator as extracted

    original = bridge._evaluate_candidate_fast_kernel_extracted
    call_record: dict = {}

    def _fake_extracted(candidate_state: dict, context: dict) -> dict | None:
        call_record.update(
            {
                "candidate_state": dict(candidate_state),
                "context": dict(context),
                "bound_bottom_updates": getattr(extracted, "_candidate_bottom_updates", None)
                is bridge._candidate_bottom_updates,
                "bound_shear_updates": getattr(extracted, "_candidate_shear_updates", None)
                is bridge._candidate_shear_updates,
                "bound_bending": getattr(extracted, "_evaluate_bending_with_bottom_state", None)
                is bridge._evaluate_bending_with_bottom_state,
                "bound_status": getattr(extracted, "_status_from_candidate_util", None)
                is bridge._status_from_candidate_util,
                "bound_width": getattr(extracted, "_design_width_value", None) is bridge._design_width_value,
            }
        )
        return {"source": "fake_fast_eval"}

    try:
        bridge._evaluate_candidate_fast_kernel_extracted = _fake_extracted
        returned = bridge.evaluate_candidate_fast(
            {"D": 600},
            {"actions": {"Ast": 1000}, "seed_overview": {"statuses": {}, "utils": {}}},
        )
    finally:
        bridge._evaluate_candidate_fast_kernel_extracted = original

    checks["bridge_runtime_binds_module_globals"] = (
        getattr(extracted, "_candidate_bottom_updates", None) is bridge._candidate_bottom_updates
        and getattr(extracted, "_candidate_shear_updates", None) is bridge._candidate_shear_updates
        and getattr(extracted, "_evaluate_bending_with_bottom_state", None)
        is bridge._evaluate_bending_with_bottom_state
        and getattr(extracted, "_status_from_candidate_util", None) is bridge._status_from_candidate_util
        and getattr(extracted, "_design_width_value", None) is bridge._design_width_value
    )
    checks["bridge_runtime_delegates_with_arguments"] = (
        returned == {"source": "fake_fast_eval"}
        and call_record.get("candidate_state") == {"D": 600}
        and call_record.get("context") == {"actions": {"Ast": 1000}, "seed_overview": {"statuses": {}, "utils": {}}}
        and call_record.get("bound_bottom_updates") is True
        and call_record.get("bound_shear_updates") is True
        and call_record.get("bound_bending") is True
        and call_record.get("bound_status") is True
        and call_record.get("bound_width") is True
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
    json_path = ARTIFACTS / f"inputs_page_fast_candidate_evaluator_extraction_{stamp}.json"
    report_path = AUDITS / f"inputs_page_fast_candidate_evaluator_extraction_{stamp}.md"
    json_path.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Fast Candidate Evaluator Extraction",
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
