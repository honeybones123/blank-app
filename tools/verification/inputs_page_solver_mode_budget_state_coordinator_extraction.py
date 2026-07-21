"""Verify one-click solver mode and budget state coordinator extraction."""

from __future__ import annotations

import ast
import datetime as _dt
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

AUTO_DESIGN_COMPUTE = ROOT / "inputs_page_modules" / "auto_design_compute.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _function_segment(source: str, name: str) -> tuple[int, int, str]:
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            start = int(node.lineno)
            end = int(getattr(node, "end_lineno", node.lineno))
            lines = source.splitlines()
            return start, end, "\n".join(lines[start - 1 : end])
    raise AssertionError(f"Function not found: {name}")


def _run_case(module: Any) -> dict[str, Any]:
    originals = {
        "EFFICIENCY_TARGET_UTIL_MIN": getattr(module, "EFFICIENCY_TARGET_UTIL_MIN", None),
        "EFFICIENCY_TARGET_UTIL_MAX": getattr(module, "EFFICIENCY_TARGET_UTIL_MAX", None),
        "_design_optimisation_goal": getattr(module, "_design_optimisation_goal", None),
        "_design_mode_config": getattr(module, "_design_mode_config", None),
    }
    calls: list[dict[str, Any]] = []
    initial_snapshot = {"D": 650, "nested": {"value": 1}, "goal": "probe"}

    def _goal(state: dict) -> str:
        calls.append({"goal_state": dict(state)})
        return str(state.get("goal"))

    def _config(goal: str) -> dict[str, Any]:
        calls.append({"mode_config_goal": goal})
        return {"target_util_min": 0.72, "target_util_max": 0.91}

    try:
        module.EFFICIENCY_TARGET_UTIL_MIN = 0.75
        module.EFFICIENCY_TARGET_UTIL_MAX = 0.95
        module._design_optimisation_goal = _goal
        module._design_mode_config = _config
        result = module._prepare_one_click_solver_mode_budget_state_coordinator(
            initial_snapshot=initial_snapshot,
            max_steps=7,
        )
    finally:
        for name, original in originals.items():
            if original is not None:
                setattr(module, name, original)

    result["working"]["nested"]["value"] = 2
    copy_isolated = initial_snapshot["nested"]["value"] == 1
    result["working"]["nested"]["value"] = 1
    return {"result": result, "calls": calls, "copy_isolated": copy_isolated}


def build_payload() -> dict[str, Any]:
    source = _read(AUTO_DESIGN_COMPUTE)
    helper_start, helper_end, helper = _function_segment(
        source,
        "_prepare_one_click_solver_mode_budget_state_coordinator",
    )
    solve_start, solve_end, solve_body = _function_segment(source, "_solve_one_click_to_target")
    runtime_setup_start, runtime_setup_end, runtime_setup_body = _function_segment(
        source, "_prepare_one_click_solver_runtime_setup_state_coordinator"
    )
    import inputs_page_modules.auto_design_compute as module  # noqa: E402

    runtime = _run_case(module)
    result = runtime["result"]
    runtime_checks = {
        "working_copy_preserved": result["working"] == {"D": 650, "nested": {"value": 1}, "goal": "probe"}
        and runtime["copy_isolated"],
        "mode_config_pipeline_preserved": runtime["calls"] == [
            {"goal_state": {"D": 650, "nested": {"value": 1}, "goal": "probe"}},
            {"mode_config_goal": "probe"},
        ]
        and result["mode_config"] == {"target_util_min": 0.72, "target_util_max": 0.91},
        "target_band_preserved": result["t_lo"] == 0.72 and result["t_hi"] == 0.91,
        "tightening_budget_preserved": result["max_tightening_steps"] == 4
        and result["tightening_budget_extensions_used"] == 0
        and result["tightening_budget_extension_cap"] == 3
        and result["tightening_step_count"] == 0,
        "candidate_and_shear_defaults_preserved": result["no_actionable_after_full_tightening_search"] is False
        and result["candidate_family_depth_reached"] == "none"
        and result["final_distance_to_band"] is None
        and result["shear_governing_mode_active"] is False
        and result["shear_severity_band"] == "mild"
        and result["shear_candidate_family_order"] == []
        and result["spacing_candidates_considered"] == 0
        and result["leg_candidates_considered"] == 0
        and result["dia_candidates_considered"] == 0
        and result["geometry_candidates_considered_for_shear"] == 0
        and result["combined_candidates_considered_for_shear"] == 0
        and result["web_crushing_penalty_applied"] == 0
        and result["rejected_as_spacing_too_weak"] == 0
        and result["rejected_as_web_crushing_marginal"] == 0
        and result["rejected_as_impractical_shear_layout"] == 0
        and result["final_resolved_shear_util"] is None
        and result["final_resolved_web_util"] is None,
        "final_eval_debug_defaults_preserved": result["step_committable_eval_trace"] == []
        and result["final_eval_internal_worst_util_dbg"] is None
        and result["final_eval_committable_worst_util_dbg"] is None
        and result["final_eval_used_source_dbg"] == "internal_working_preview"
        and result["final_eval_committable_updates_dbg"] == {},
    }
    static_checks = {
        "solver_delegates_runtime_setup_state": (
            "_prepare_one_click_solver_runtime_setup_state_coordinator(" in solve_body
        ),
        "helper_present": "def _prepare_one_click_solver_mode_budget_state_coordinator(" in source,
        "helper_preserves_working_copy": "working = copy.deepcopy(initial_snapshot)" in helper,
        "helper_preserves_mode_config_pipeline": "_design_mode_config(_design_optimisation_goal(working))" in helper,
        "helper_preserves_target_band_fallbacks": "EFFICIENCY_TARGET_UTIL_MIN" in helper
        and "EFFICIENCY_TARGET_UTIL_MAX" in helper,
        "helper_preserves_tightening_budget_math": "max(1, min(int(max_steps), 4))" in helper
        and "max(0, int(max_steps) - int(max_tightening_steps))" in helper,
        "helper_preserves_shear_defaults": '"shear_severity_band": "mild"' in helper
        and '"shear_candidate_family_order": []' in helper
        and '"rejected_as_impractical_shear_layout": 0' in helper,
        "helper_preserves_final_eval_debug_defaults": '"final_eval_used_source_dbg": "internal_working_preview"' in helper
        and '"final_eval_committable_updates_dbg": {}' in helper,
        "solver_delegates_mode_budget_state": "_prepare_one_click_solver_mode_budget_state_coordinator(" in runtime_setup_body,
        "runtime_setup_rehydrates_mode_budget_state_fields": 'working = solver_mode_budget_state["working"]' in runtime_setup_body
        and 'mode_config = solver_mode_budget_state["mode_config"]' in runtime_setup_body
        and 'step_committable_eval_trace = solver_mode_budget_state["step_committable_eval_trace"]'
        in runtime_setup_body,
        "solver_no_longer_inlines_mode_budget_setup": "working = copy.deepcopy(initial_snapshot)" not in solve_body
        and "max_tightening_steps = max(1, min(int(max_steps), 4))" not in solve_body,
    }
    status = "PASS"
    if not all(static_checks.values()) or not all(runtime_checks.values()):
        status = "FAIL"
    return {
        "status": status,
        "surface": "_solve_one_click_to_target_mode_budget_state_coordinator",
        "helper_segment": {
            "function": "_prepare_one_click_solver_mode_budget_state_coordinator",
            "start_line": helper_start,
            "end_line": helper_end,
            "line_count": helper_end - helper_start + 1,
        },
        "solver_segment": {
            "function": "_solve_one_click_to_target",
            "start_line": solve_start,
            "end_line": solve_end,
            "line_count": solve_end - solve_start + 1,
        },
        "static_checks": static_checks,
        "runtime_checks": runtime_checks,
        "runtime": {
            "calls": runtime["calls"],
            "copy_isolated": runtime["copy_isolated"],
            "result": result,
        },
        "product_behavior_changed": False,
        "next_safe_slice": "extract initial solver evaluation domain setup",
    }


def write_artifacts(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now().isoformat(timespec="seconds").replace(":", "-")
    json_path = ARTIFACT_DIR / f"inputs_page_solver_mode_budget_state_coordinator_extraction_{stamp}.json"
    md_path = AUDIT_DIR / f"inputs_page_solver_mode_budget_state_coordinator_extraction_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Solver Mode Budget State Coordinator Extraction",
        "",
        f"Status: `{payload['status']}`",
        "",
        "## Static Checks",
    ]
    for key, value in payload["static_checks"].items():
        lines.append(f"- `{key}`: `{value}`")
    lines.append("")
    lines.append("## Runtime Checks")
    for key, value in payload["runtime_checks"].items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(["", "## Next Safe Slice", "", str(payload["next_safe_slice"])])
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, md_path


def main() -> int:
    payload = build_payload()
    json_path, md_path = write_artifacts(payload)
    print(json.dumps({"status": payload["status"], "json": str(json_path), "report": str(md_path)}, indent=2))
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
