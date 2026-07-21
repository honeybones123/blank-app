"""Verify progressive auto-design solver extraction from the Inputs app bridge."""

from __future__ import annotations

import ast
import json
import sys
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BRIDGE = ROOT / "inputs_page_app_contract_bridge.py"
MODULE = ROOT / "inputs_page_modules" / "app_bridge" / "auto_design_solver.py"
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

    bridge_node = _function_node(bridge_source, "run_auto_design_solver")
    bridge_reo_node = _function_node(bridge_source, "_solve_reo_for_geometry")
    bridge_progressive_node = _function_node(bridge_source, "_build_progressive_candidate_updates")
    module_node = _function_node(module_source, "run_auto_design_solver")
    module_reo_node = _function_node(module_source, "_solve_reo_for_geometry")
    module_progressive_node = _function_node(module_source, "_build_progressive_candidate_updates")
    bridge_body = ast.get_source_segment(bridge_source, bridge_node) or ""
    bridge_reo_body = ast.get_source_segment(bridge_source, bridge_reo_node) or ""
    bridge_progressive_body = ast.get_source_segment(bridge_source, bridge_progressive_node) or ""

    checks: dict[str, bool] = {
        "bridge_wrapper_is_small": (bridge_node.end_lineno or bridge_node.lineno) - bridge_node.lineno + 1 <= 9,
        "bridge_binds_dependencies": "_bind_auto_design_solver_dependencies(globals())" in bridge_body,
        "bridge_delegates_to_extracted_module": "_run_auto_design_solver_extracted" in bridge_body,
        "bridge_reo_solver_wrapper_is_small": (
            bridge_reo_node.end_lineno or bridge_reo_node.lineno
        ) - bridge_reo_node.lineno + 1 <= 13,
        "bridge_reo_solver_binds_dependencies": "_bind_auto_design_solver_dependencies(globals())" in bridge_reo_body,
        "bridge_reo_solver_delegates_to_extracted_module": "_solve_reo_for_geometry_extracted" in bridge_reo_body,
        "bridge_progressive_builder_wrapper_is_small": (
            bridge_progressive_node.end_lineno or bridge_progressive_node.lineno
        ) - bridge_progressive_node.lineno + 1 <= 14,
        "bridge_progressive_builder_binds_dependencies": (
            "_bind_auto_design_solver_dependencies(globals())" in bridge_progressive_body
        ),
        "bridge_progressive_builder_delegates_to_extracted_module": (
            "_build_progressive_candidate_updates_extracted" in bridge_progressive_body
        ),
        "module_contains_extracted_body": (module_node.end_lineno or module_node.lineno) - module_node.lineno + 1 > 150,
        "module_contains_reo_solver_body": (
            module_reo_node.end_lineno or module_reo_node.lineno
        ) - module_reo_node.lineno + 1 >= 106,
        "module_contains_progressive_builder_body": (
            module_progressive_node.end_lineno or module_progressive_node.lineno
        ) - module_progressive_node.lineno + 1 >= 70,
        "module_has_dependency_binder": "def bind_auto_design_solver_dependencies" in module_source,
        "module_does_not_import_streamlit": "import streamlit" not in module_source,
        "module_does_not_import_bridge": "inputs_page_app_contract_bridge" not in module_source,
        "module_keeps_solver_contract_surface": (
            "progressive_auto_design_seed" in module_source
            and "auto_design_solver_progressive" in module_source
            and "Auto Design Solution" in module_source
            and "has_resolved_candidate_payload" in module_source
            and "resolved_candidate_reaches_target_band" in module_source
            and "run_auto_design_step" in module_source
            and "_build_progressive_candidate_updates" in module_source
            and "Priority order is intentional" in module_source
        ),
        "module_keeps_reo_solver_contract_surface": (
            "geometry_seed" in module_source
            and "reo_band" in module_source
            and "shear_band" in module_source
            and "solve_reo_total_ms" in module_source
            and "candidate_generation_ms" in module_source
            and "pruning_total_ms" in module_source
            and "disable_shear_strength_candidates" in module_source
        ),
    }

    import inputs_page_app_contract_bridge as bridge
    from inputs_page_modules.app_bridge import auto_design_solver as extracted

    original = bridge._run_auto_design_solver_extracted
    original_reo = bridge._solve_reo_for_geometry_extracted
    call_record: dict = {}
    reo_call_record: dict = {}

    def _fake_extracted(state: dict, results: dict) -> dict:
        call_record.update(
            {
                "state": dict(state),
                "results": dict(results),
                "bound_eval": getattr(extracted, "evaluate_candidate_full", None) is bridge.evaluate_candidate_full,
                "bound_step": getattr(extracted, "run_auto_design_step", None) is bridge.run_auto_design_step,
                "bound_overlay": (
                    getattr(extracted, "_overlay_current_normalized_shear_truth", None)
                    is bridge._overlay_current_normalized_shear_truth
                ),
            }
        )
        return {"title": "Auto Design Solution"}

    def _fake_reo_extracted(
        geometry_state: dict,
        *,
        mode_config: dict,
        seed_candidate: dict,
        eval_cache: dict,
        metrics: dict,
    ) -> dict:
        reo_call_record.update(
            {
                "geometry_state": dict(geometry_state),
                "mode_config": dict(mode_config),
                "seed_candidate": dict(seed_candidate),
                "eval_cache": dict(eval_cache),
                "metrics": dict(metrics),
                "bound_fast": getattr(extracted, "_evaluate_candidate_fast", None)
                is bridge._evaluate_candidate_fast,
                "bound_context": getattr(extracted, "_build_auto_design_context", None)
                is bridge._build_auto_design_context,
                "bound_keep": getattr(extracted, "_keep_top_candidates", None)
                is bridge._keep_top_candidates,
                "bound_good_enough": getattr(extracted, "candidate_is_good_enough", None)
                is bridge.candidate_is_good_enough,
            }
        )
        return {"label": "fake reo"}

    try:
        bridge._run_auto_design_solver_extracted = _fake_extracted
        bridge._solve_reo_for_geometry_extracted = _fake_reo_extracted
        returned = bridge.run_auto_design_solver({"D": 600}, {"worst_util": 1.05})
        reo_returned = bridge._solve_reo_for_geometry(
            {"D": 650},
            mode_config={"max_frontier": 4},
            seed_candidate={"state": {"D": 600}},
            eval_cache={"a": 1},
            metrics={"cap_hit": False},
        )
    finally:
        bridge._run_auto_design_solver_extracted = original
        bridge._solve_reo_for_geometry_extracted = original_reo

    checks["bridge_runtime_binds_module_globals"] = (
        getattr(extracted, "TARGET_UTIL", None) == bridge.TARGET_UTIL
        and getattr(extracted, "evaluate_candidate_full", None) is bridge.evaluate_candidate_full
        and getattr(extracted, "run_auto_design_step", None) is bridge.run_auto_design_step
        and getattr(extracted, "_candidate_worst_util_value", None)
        is bridge._candidate_worst_util_value
        and getattr(extracted, "_build_progressive_candidate_updates", None)
        is bridge._build_progressive_candidate_updates_extracted
        and getattr(extracted, "_resolve_geometry_width_context", None)
        is bridge._resolve_geometry_width_context
        and getattr(extracted, "_apply_bottom_bar_count_update", None)
        is bridge._apply_bottom_bar_count_update
        and getattr(extracted, "_scaled_bottom_total_for_factor", None)
        is bridge._scaled_bottom_total_for_factor
        and getattr(extracted, "build_candidate", None)
        is bridge.build_candidate
        and getattr(extracted, "_int_from_state", None)
        is bridge._int_from_state
        and getattr(extracted, "_evaluate_candidate_fast", None) is bridge._evaluate_candidate_fast
        and getattr(extracted, "_build_auto_design_context", None) is bridge._build_auto_design_context
        and getattr(extracted, "_keep_top_candidates", None) is bridge._keep_top_candidates
        and getattr(extracted, "candidate_is_good_enough", None) is bridge.candidate_is_good_enough
    )
    checks["bridge_runtime_delegates_with_arguments"] = (
        returned == {"title": "Auto Design Solution"}
        and call_record.get("state") == {"D": 600}
        and call_record.get("results") == {"worst_util": 1.05}
        and call_record.get("bound_eval") is True
        and call_record.get("bound_step") is True
        and call_record.get("bound_overlay") is True
    )
    checks["bridge_reo_solver_runtime_delegates_with_arguments"] = (
        reo_returned == {"label": "fake reo"}
        and reo_call_record.get("geometry_state") == {"D": 650}
        and reo_call_record.get("mode_config") == {"max_frontier": 4}
        and reo_call_record.get("seed_candidate") == {"state": {"D": 600}}
        and reo_call_record.get("eval_cache") == {"a": 1}
        and reo_call_record.get("metrics") == {"cap_hit": False}
        and reo_call_record.get("bound_fast") is True
        and reo_call_record.get("bound_context") is True
        and reo_call_record.get("bound_keep") is True
        and reo_call_record.get("bound_good_enough") is True
    )

    result = {
        "status": "PASS" if all(checks.values()) else "FAIL",
        "checks": checks,
        "bridge_wrapper_lines": (bridge_node.end_lineno or bridge_node.lineno) - bridge_node.lineno + 1,
        "bridge_reo_solver_wrapper_lines": (
            bridge_reo_node.end_lineno or bridge_reo_node.lineno
        ) - bridge_reo_node.lineno + 1,
        "bridge_progressive_builder_wrapper_lines": (
            bridge_progressive_node.end_lineno or bridge_progressive_node.lineno
        ) - bridge_progressive_node.lineno + 1,
        "module_function_lines": (module_node.end_lineno or module_node.lineno) - module_node.lineno + 1,
        "module_reo_solver_function_lines": (
            module_reo_node.end_lineno or module_reo_node.lineno
        ) - module_reo_node.lineno + 1,
        "module_progressive_builder_function_lines": (
            module_progressive_node.end_lineno or module_progressive_node.lineno
        ) - module_progressive_node.lineno + 1,
    }

    stamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    AUDITS.mkdir(parents=True, exist_ok=True)
    json_path = ARTIFACTS / f"inputs_page_auto_design_solver_extraction_{stamp}.json"
    report_path = AUDITS / f"inputs_page_auto_design_solver_extraction_{stamp}.md"
    json_path.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Auto Design Solver Extraction",
                "",
                f"Status: {result['status']}",
                "",
                f"- Bridge wrapper lines: {result['bridge_wrapper_lines']}",
                f"- Bridge REO solver wrapper lines: {result['bridge_reo_solver_wrapper_lines']}",
                f"- Bridge progressive builder wrapper lines: {result['bridge_progressive_builder_wrapper_lines']}",
                f"- Extracted module function lines: {result['module_function_lines']}",
                f"- Extracted module REO solver function lines: {result['module_reo_solver_function_lines']}",
                f"- Extracted module progressive builder function lines: {result['module_progressive_builder_function_lines']}",
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
