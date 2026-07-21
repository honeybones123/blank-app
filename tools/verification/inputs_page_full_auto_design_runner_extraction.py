"""Verify full auto-design runner extraction from the Inputs app bridge."""

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

    bridge_node = _function_node(bridge_source, "run_full_auto_design")
    module_node = _function_node(module_source, "run_full_auto_design")
    bridge_tightening_node = _function_node(bridge_source, "run_final_tightening_pass")
    module_tightening_node = _function_node(module_source, "run_final_tightening_pass")
    bridge_body = ast.get_source_segment(bridge_source, bridge_node) or ""
    bridge_tightening_body = ast.get_source_segment(bridge_source, bridge_tightening_node) or ""

    checks: dict[str, bool] = {
        "bridge_wrapper_is_small": (bridge_node.end_lineno or bridge_node.lineno) - bridge_node.lineno + 1 <= 10,
        "bridge_binds_dependencies": "_bind_auto_design_solver_dependencies(globals())" in bridge_body,
        "bridge_delegates_to_extracted_module": "_run_full_auto_design_extracted" in bridge_body,
        "bridge_tightening_wrapper_is_small": (bridge_tightening_node.end_lineno or bridge_tightening_node.lineno) - bridge_tightening_node.lineno + 1 <= 18,
        "bridge_tightening_binds_dependencies": "_bind_auto_design_solver_dependencies(globals())" in bridge_tightening_body,
        "bridge_tightening_delegates_to_extracted_module": "_run_final_tightening_pass_extracted" in bridge_tightening_body,
        "module_contains_extracted_body": (module_node.end_lineno or module_node.lineno) - module_node.lineno + 1 >= 93,
        "module_contains_final_tightening_body": (module_tightening_node.end_lineno or module_tightening_node.lineno) - module_tightening_node.lineno + 1 >= 60,
        "module_owns_final_tightening_binding": '"run_final_tightening_pass"' not in module_source.partition("def bind_auto_design_solver_dependencies")[0],
        "module_has_dependency_binder": "def bind_auto_design_solver_dependencies" in module_source,
        "module_does_not_import_streamlit": "import streamlit" not in module_source,
        "module_does_not_import_bridge": "inputs_page_app_contract_bridge" not in module_source,
        "module_keeps_full_runner_contract_surface": all(
            token in module_source
            for token in (
                "final_tightening",
                "cleanup_noncritical",
                "run_full_auto_design:selected_full",
                "run_full_auto_design:post_select_bending_verify",
                "Auto-design final selection",
                "H26",
                "material_change",
                "total_runtime_ms",
            )
        ),
    }

    import inputs_page_app_contract_bridge as bridge
    from inputs_page_modules.app_bridge import auto_design_solver as extracted

    original = bridge._run_full_auto_design_extracted
    call_record: dict = {}

    def _fake_extracted(
        seed_candidate: dict,
        mode: str,
        force: bool = False,
        is_first_hop: bool = False,
    ) -> dict:
        call_record.update(
            {
                "seed_candidate": dict(seed_candidate),
                "mode": mode,
                "force": bool(force),
                "is_first_hop": bool(is_first_hop),
                "bound_primary": getattr(extracted, "run_primary_auto_design", None)
                is bridge.run_primary_auto_design,
                "bound_tightening": getattr(extracted, "run_final_tightening_pass", None)
                is bridge._run_final_tightening_pass_extracted,
                "tightening_not_bound_to_bridge_wrapper": getattr(extracted, "run_final_tightening_pass", None)
                is not bridge.run_final_tightening_pass,
                "bound_tightening_low_level_deps": (
                    getattr(extracted, "generate_local_improvement_candidates", None)
                    is bridge.generate_local_improvement_candidates
                    and getattr(extracted, "select_best_next_hop_candidate", None)
                    is bridge.select_best_next_hop_candidate
                    and getattr(extracted, "is_meaningfully_better", None)
                    is bridge.is_meaningfully_better
                    and getattr(extracted, "AUTO_DESIGN_MAX_KEPT_RESULTS", None)
                    == bridge.AUTO_DESIGN_MAX_KEPT_RESULTS
                ),
                "uses_extracted_cleanup": callable(getattr(extracted, "run_cleanup_pass", None))
                and getattr(extracted, "run_cleanup_pass", None) is not bridge.run_cleanup_pass,
                "bound_select": getattr(extracted, "select_final_candidate", None)
                is bridge.select_final_candidate,
            }
        )
        return {"candidate": {"label": "selected"}, "material_change": True}

    try:
        bridge._run_full_auto_design_extracted = _fake_extracted
        returned = bridge.run_full_auto_design(
            {"state": {"D": 600}},
            "balanced",
            force=True,
            is_first_hop=True,
        )
    finally:
        bridge._run_full_auto_design_extracted = original

    checks["bridge_runtime_binds_module_globals"] = (
        getattr(extracted, "run_primary_auto_design", None) is bridge.run_primary_auto_design
        and getattr(extracted, "run_final_tightening_pass", None) is bridge._run_final_tightening_pass_extracted
        and getattr(extracted, "run_final_tightening_pass", None) is not bridge.run_final_tightening_pass
        and getattr(extracted, "generate_local_improvement_candidates", None)
        is bridge.generate_local_improvement_candidates
        and getattr(extracted, "select_best_next_hop_candidate", None)
        is bridge.select_best_next_hop_candidate
        and getattr(extracted, "is_meaningfully_better", None) is bridge.is_meaningfully_better
        and getattr(extracted, "AUTO_DESIGN_MAX_KEPT_RESULTS", None) == bridge.AUTO_DESIGN_MAX_KEPT_RESULTS
        and callable(getattr(extracted, "run_cleanup_pass", None))
        and getattr(extracted, "run_cleanup_pass", None) is not bridge.run_cleanup_pass
        and getattr(extracted, "select_final_candidate", None) is bridge.select_final_candidate
        and getattr(extracted, "_materialize_full_evaluated_candidate", None)
        is bridge._materialize_full_evaluated_candidate
        and getattr(extracted, "_agent_debug_log", None) is bridge._agent_debug_log
    )
    checks["bridge_runtime_delegates_with_arguments"] = (
        returned == {"candidate": {"label": "selected"}, "material_change": True}
        and call_record.get("seed_candidate") == {"state": {"D": 600}}
        and call_record.get("mode") == "balanced"
        and call_record.get("force") is True
        and call_record.get("is_first_hop") is True
        and call_record.get("bound_primary") is True
        and call_record.get("bound_tightening") is True
        and call_record.get("tightening_not_bound_to_bridge_wrapper") is True
        and call_record.get("bound_tightening_low_level_deps") is True
        and call_record.get("uses_extracted_cleanup") is True
        and call_record.get("bound_select") is True
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
    json_path = ARTIFACTS / f"inputs_page_full_auto_design_runner_extraction_{stamp}.json"
    report_path = AUDITS / f"inputs_page_full_auto_design_runner_extraction_{stamp}.md"
    json_path.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Full Auto-Design Runner Extraction",
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
