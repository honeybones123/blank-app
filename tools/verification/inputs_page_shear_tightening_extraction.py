"""Verify shear tightening recommendation extraction from the Inputs app bridge."""

from __future__ import annotations

import ast
import json
import sys
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BRIDGE = ROOT / "inputs_page_app_contract_bridge.py"
MODULE = ROOT / "inputs_page_modules" / "design_guide" / "shear_tightening.py"
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

    bridge_node = _function_node(bridge_source, "_compute_shear_tightening_recommendation")
    module_node = _function_node(module_source, "_compute_shear_tightening_recommendation")
    bridge_body = ast.get_source_segment(bridge_source, bridge_node) or ""
    dependency_block = module_source.split("def bind_shear_tightening_dependencies", 1)[0]

    checks: dict[str, bool] = {
        "bridge_wrapper_is_small": (bridge_node.end_lineno or bridge_node.lineno) - bridge_node.lineno + 1 <= 6,
        "bridge_binds_dependencies": "_bind_shear_tightening_dependencies(globals())" in bridge_body,
        "bridge_delegates_to_extracted_module": "_compute_shear_tightening_recommendation_extracted" in bridge_body,
        "module_contains_extracted_body": (module_node.end_lineno or module_node.lineno) - module_node.lineno + 1 > 190,
        "module_has_dependency_binder": "def bind_shear_tightening_dependencies" in module_source,
        "module_does_not_import_streamlit": "import streamlit" not in module_source,
        "module_does_not_import_bridge": "inputs_page_app_contract_bridge" not in module_source,
        "dependency_binder_excludes_lambda_item": '"item"' not in dependency_block,
        "module_keeps_shear_contract_surface": (
            "canonical_inactive_storage_fixup" in module_source
            and "underdesign_activation" in module_source
            and "spacing_or_leg_reduction" in module_source
            and "resolved_candidate_reaches_target_band" in module_source
        ),
    }

    import inputs_page_app_contract_bridge as bridge
    from inputs_page_modules.design_guide import shear_tightening as extracted

    original = bridge._compute_shear_tightening_recommendation_extracted
    call_record: dict = {}

    def _fake_extracted(state: dict, *, out_debug: dict | None = None) -> dict | None:
        call_record.update(
            {
                "state": dict(state),
                "out_debug": out_debug,
                "bound_seed_eval": getattr(extracted, "evaluate_candidate_full", None)
                is bridge.evaluate_candidate_full,
                "bound_variant_generator": (
                    getattr(extracted, "generate_less_shear_reo_variants", None)
                    is bridge.generate_less_shear_reo_variants
                ),
                "bound_truth_gate": (
                    getattr(extracted, "_shear_governing_truth_allows_overdesign_cleanup", None)
                    is bridge._shear_governing_truth_allows_overdesign_cleanup
                ),
                "bound_fast_eval": (
                    getattr(extracted, "_evaluate_candidate_fast", None)
                    is bridge._evaluate_candidate_fast
                ),
            }
        )
        return {"label": "fake shear"}

    debug: dict = {}
    try:
        bridge._compute_shear_tightening_recommendation_extracted = _fake_extracted
        returned = bridge._compute_shear_tightening_recommendation({"s_lig": 200}, out_debug=debug)
    finally:
        bridge._compute_shear_tightening_recommendation_extracted = original

    checks["bridge_runtime_binds_module_globals"] = (
        getattr(extracted, "evaluate_candidate_full", None) is bridge.evaluate_candidate_full
        and getattr(extracted, "generate_less_shear_reo_variants", None)
        is bridge.generate_less_shear_reo_variants
        and getattr(extracted, "_score_auto_design_candidate", None)
        is bridge._score_auto_design_candidate
        and getattr(extracted, "_candidate_debug_summary", None)
        is bridge._candidate_debug_summary
    )
    checks["bridge_runtime_delegates_with_arguments"] = (
        returned == {"label": "fake shear"}
        and call_record.get("state") == {"s_lig": 200}
        and call_record.get("out_debug") is debug
        and call_record.get("bound_seed_eval") is True
        and call_record.get("bound_variant_generator") is True
        and call_record.get("bound_truth_gate") is True
        and call_record.get("bound_fast_eval") is True
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
    json_path = ARTIFACTS / f"inputs_page_shear_tightening_extraction_{stamp}.json"
    report_path = AUDITS / f"inputs_page_shear_tightening_extraction_{stamp}.md"
    json_path.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Shear Tightening Extraction",
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
