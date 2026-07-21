"""Verify candidate sort-key extraction from the Inputs app bridge."""

from __future__ import annotations

import ast
import json
import sys
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BRIDGE = ROOT / "inputs_page_app_contract_bridge.py"
MODULE = ROOT / "inputs_page_modules" / "design_guide" / "auto_design_scoring.py"
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

    name = "_candidate_sort_key_for_mode"
    bridge_node = _function_node(bridge_source, name)
    module_node = _function_node(module_source, name)
    bridge_body = ast.get_source_segment(bridge_source, bridge_node) or ""

    checks: dict[str, bool] = {
        "bridge_wrapper_is_small": (bridge_node.end_lineno or bridge_node.lineno) - bridge_node.lineno + 1 <= 5,
        "bridge_binds_dependencies": "_bind_auto_design_scoring_dependencies(globals())" in bridge_body,
        "bridge_delegates_to_extracted_module": "_candidate_sort_key_for_mode_extracted" in bridge_body,
        "module_contains_extracted_body": (module_node.end_lineno or module_node.lineno) - module_node.lineno + 1 >= 100,
        "module_has_dependency_binder": "def bind_auto_design_scoring_dependencies" in module_source,
        "module_exports_sort_key": '"_candidate_sort_key_for_mode"' in module_source,
        "module_does_not_import_streamlit": "streamlit" not in module_source and "import st" not in module_source,
        "module_does_not_read_session_state": ".session_state" not in module_source,
        "module_does_not_import_bridge": "inputs_page_app_contract_bridge" not in module_source,
        "module_keeps_strategy_branches": all(
            token in module_source
            for token in (
                '"shallow"',
                '"low_reo"',
                "_ductility_priority",
                "_candidate_in_target_band",
                "_shallower_beam_candidate_tier",
                "compute_reo_complexity",
            )
        ),
    }

    import inputs_page_app_contract_bridge as bridge
    from inputs_page_modules.design_guide import auto_design_scoring as extracted

    original = bridge._candidate_sort_key_for_mode_extracted
    call_record: dict = {}

    def _fake_extracted(candidate: dict, mode_config: dict) -> tuple:
        call_record.update(
            {
                "candidate": dict(candidate),
                "mode_config": dict(mode_config),
                "bound_practical": getattr(extracted, "_candidate_is_practical", None)
                is bridge._candidate_is_practical,
                "bound_violation": getattr(extracted, "_candidate_violation_score", None)
                is bridge._candidate_violation_score,
                "bound_distance": getattr(extracted, "_candidate_util_distance", None)
                is bridge._candidate_util_distance,
                "bound_complexity": getattr(extracted, "compute_reo_complexity", None)
                is bridge.compute_reo_complexity,
            }
        )
        return ("sort", "key")

    try:
        bridge._candidate_sort_key_for_mode_extracted = _fake_extracted
        returned = bridge._candidate_sort_key_for_mode(
            {"is_compliant": True, "worst_util": 0.9},
            {"search_strategy": "balanced"},
        )
    finally:
        bridge._candidate_sort_key_for_mode_extracted = original

    checks["bridge_runtime_binds_module_globals"] = (
        getattr(extracted, "_candidate_is_practical", None) is bridge._candidate_is_practical
        and getattr(extracted, "_candidate_violation_score", None) is bridge._candidate_violation_score
        and getattr(extracted, "_candidate_util_distance", None) is bridge._candidate_util_distance
        and getattr(extracted, "compute_reo_complexity", None) is bridge.compute_reo_complexity
    )
    checks["bridge_runtime_delegates_with_arguments"] = (
        returned == ("sort", "key")
        and call_record.get("candidate") == {"is_compliant": True, "worst_util": 0.9}
        and call_record.get("mode_config") == {"search_strategy": "balanced"}
        and call_record.get("bound_practical") is True
        and call_record.get("bound_violation") is True
        and call_record.get("bound_distance") is True
        and call_record.get("bound_complexity") is True
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
    json_path = ARTIFACTS / f"inputs_page_candidate_sort_key_extraction_{stamp}.json"
    report_path = AUDITS / f"inputs_page_candidate_sort_key_extraction_{stamp}.md"
    json_path.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Candidate Sort-Key Extraction",
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
