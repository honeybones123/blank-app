"""Verify auto-design candidate scoring extraction from the Inputs app bridge."""

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

    bridge_node = _function_node(bridge_source, "_score_auto_design_candidate_components")
    module_node = _function_node(module_source, "_score_auto_design_candidate_components")
    bridge_body = ast.get_source_segment(bridge_source, bridge_node) or ""

    checks: dict[str, bool] = {
        "bridge_wrapper_is_small": (bridge_node.end_lineno or bridge_node.lineno) - bridge_node.lineno + 1 <= 4,
        "bridge_binds_dependencies": "_bind_auto_design_scoring_dependencies(globals())" in bridge_body,
        "bridge_delegates_to_extracted_module": "_score_auto_design_candidate_components_extracted" in bridge_body,
        "module_contains_extracted_body": (module_node.end_lineno or module_node.lineno) - module_node.lineno + 1 > 185,
        "module_has_dependency_binder": "def bind_auto_design_scoring_dependencies" in module_source,
        "module_does_not_import_streamlit": "import streamlit" not in module_source,
        "module_does_not_import_bridge": "inputs_page_app_contract_bridge" not in module_source,
        "module_keeps_scoring_contract_surface": (
            "ductility_priority" in module_source
            and "shear_candidate_total_practicality_penalty" in module_source
            and "compound_width_reo_bonus" in module_source
            and "total_score" in module_source
        ),
    }

    import inputs_page_app_contract_bridge as bridge
    from inputs_page_modules.design_guide import auto_design_scoring as extracted

    original = bridge._score_auto_design_candidate_components_extracted
    call_record: dict = {}

    def _fake_extracted(candidate: dict, mode_config: dict, seed_candidate: dict) -> dict:
        call_record.update(
            {
                "candidate": dict(candidate),
                "mode_config": dict(mode_config),
                "seed_candidate": dict(seed_candidate),
                "bound_objective_util": (
                    getattr(extracted, "_candidate_objective_util", None)
                    is bridge._candidate_objective_util
                ),
                "bound_practicality": (
                    getattr(extracted, "_shear_candidate_practicality_metrics", None)
                    is bridge._shear_candidate_practicality_metrics
                ),
                "bound_ductility": (
                    getattr(extracted, "_candidate_ductility_governs", None)
                    is bridge._candidate_ductility_governs
                ),
            }
        )
        return {"total_score": 12.5}

    try:
        bridge._score_auto_design_candidate_components_extracted = _fake_extracted
        returned = bridge._score_auto_design_candidate_components(
            {"depth": 600},
            {"target_util_min": 0.7, "target_util_max": 0.9},
            {"depth": 600},
        )
    finally:
        bridge._score_auto_design_candidate_components_extracted = original

    checks["bridge_runtime_binds_module_globals"] = (
        getattr(extracted, "_candidate_objective_util", None) is bridge._candidate_objective_util
        and getattr(extracted, "_shear_candidate_practicality_metrics", None)
        is bridge._shear_candidate_practicality_metrics
        and getattr(extracted, "_shallower_beam_metrics", None)
        is bridge._shallower_beam_metrics
        and getattr(extracted, "_candidate_violation_score", None)
        is bridge._candidate_violation_score
    )
    checks["bridge_runtime_delegates_with_arguments"] = (
        returned == {"total_score": 12.5}
        and call_record.get("candidate") == {"depth": 600}
        and call_record.get("mode_config") == {"target_util_min": 0.7, "target_util_max": 0.9}
        and call_record.get("seed_candidate") == {"depth": 600}
        and call_record.get("bound_objective_util") is True
        and call_record.get("bound_practicality") is True
        and call_record.get("bound_ductility") is True
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
    json_path = ARTIFACTS / f"inputs_page_auto_design_scoring_extraction_{stamp}.json"
    report_path = AUDITS / f"inputs_page_auto_design_scoring_extraction_{stamp}.md"
    json_path.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Auto Design Scoring Extraction",
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
