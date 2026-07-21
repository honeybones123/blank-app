"""Verify auto-design cleanup pass extraction from the Inputs app bridge."""

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

    bridge_node = _function_node(bridge_source, "run_cleanup_pass")
    module_node = _function_node(module_source, "run_cleanup_pass")
    bridge_body = ast.get_source_segment(bridge_source, bridge_node) or ""

    checks: dict[str, bool] = {
        "bridge_wrapper_is_small": (bridge_node.end_lineno or bridge_node.lineno) - bridge_node.lineno + 1 <= 18,
        "bridge_binds_dependencies": "_bind_auto_design_solver_dependencies(globals())" in bridge_body,
        "bridge_delegates_to_extracted_module": "_run_cleanup_pass_extracted" in bridge_body,
        "module_contains_extracted_body": (module_node.end_lineno or module_node.lineno) - module_node.lineno + 1 >= 94,
        "module_has_dependency_binder": "def bind_auto_design_solver_dependencies" in module_source,
        "module_does_not_import_streamlit": "import streamlit" not in module_source,
        "module_does_not_import_bridge": "inputs_page_app_contract_bridge" not in module_source,
        "module_keeps_cleanup_contract_surface": all(
            token in module_source
            for token in (
                "cleanup_pass",
                "cleanup_stop_reason",
                "cleanup_selected_score",
                "cleanup_geometry_locked",
                "H_CLEANUP",
                "shear_strength_exceeded",
                "no_noncritical_reduction",
                "protected_case_not_preserved",
                "materially_worsens_current",
                "best_safe_local_cleanup",
            )
        ),
    }

    import inputs_page_app_contract_bridge as bridge
    from inputs_page_modules.app_bridge import auto_design_solver as extracted

    original = bridge._run_cleanup_pass_extracted
    call_record: dict = {}

    def _fake_extracted(
        initial_candidate: dict,
        mode_config: dict,
        *,
        seed_candidate: dict,
        eval_cache: dict,
        metrics: dict,
    ) -> dict:
        call_record.update(
            {
                "initial_candidate": dict(initial_candidate),
                "mode_config": dict(mode_config),
                "seed_candidate": dict(seed_candidate),
                "eval_cache": dict(eval_cache),
                "metrics": dict(metrics),
                "bound_fast": getattr(extracted, "_evaluate_candidate_fast", None)
                is bridge._evaluate_candidate_fast,
                "bound_generate_cleanup": getattr(extracted, "generate_cleanup_candidates", None)
                is bridge.generate_cleanup_candidates,
                "bound_worsens": getattr(extracted, "candidate_materially_worsens", None)
                is bridge.candidate_materially_worsens,
                "bound_debug_log": getattr(extracted, "_agent_debug_log", None)
                is bridge._agent_debug_log,
            }
        )
        return {"label": "cleanup"}

    try:
        bridge._run_cleanup_pass_extracted = _fake_extracted
        returned = bridge.run_cleanup_pass(
            {"state": {"D": 650}, "score": 10.0},
            {"search_strategy": "balanced"},
            seed_candidate={"state": {"D": 600}},
            eval_cache={"cached": True},
            metrics={"_reference_overview": {"worst_util": 0.9}},
        )
    finally:
        bridge._run_cleanup_pass_extracted = original

    checks["bridge_runtime_binds_module_globals"] = (
        getattr(extracted, "AUTO_DESIGN_MAX_TIGHTENING_ITERS", None)
        == bridge.AUTO_DESIGN_MAX_TIGHTENING_ITERS
        and getattr(extracted, "_evaluate_candidate_fast", None) is bridge._evaluate_candidate_fast
        and getattr(extracted, "generate_cleanup_candidates", None) is bridge.generate_cleanup_candidates
        and getattr(extracted, "candidate_materially_worsens", None) is bridge.candidate_materially_worsens
        and getattr(extracted, "_agent_debug_log", None) is bridge._agent_debug_log
    )
    checks["bridge_runtime_delegates_with_arguments"] = (
        returned == {"label": "cleanup"}
        and call_record.get("initial_candidate") == {"state": {"D": 650}, "score": 10.0}
        and call_record.get("mode_config") == {"search_strategy": "balanced"}
        and call_record.get("seed_candidate") == {"state": {"D": 600}}
        and call_record.get("eval_cache") == {"cached": True}
        and call_record.get("metrics") == {"_reference_overview": {"worst_util": 0.9}}
        and call_record.get("bound_fast") is True
        and call_record.get("bound_generate_cleanup") is True
        and call_record.get("bound_worsens") is True
        and call_record.get("bound_debug_log") is True
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
    json_path = ARTIFACTS / f"inputs_page_auto_design_cleanup_pass_extraction_{stamp}.json"
    report_path = AUDITS / f"inputs_page_auto_design_cleanup_pass_extraction_{stamp}.md"
    json_path.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Auto-Design Cleanup Pass Extraction",
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
