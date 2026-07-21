"""Verify no-scored stop branch coordinator extraction."""

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


def _run_cases(module: Any) -> dict[str, Any]:
    original_stop = getattr(module, "_trace_no_actionable_candidates_solver_stop_coordinator", None)
    calls: list[dict[str, Any]] = []

    def _stop(**kwargs: Any) -> tuple[str, str, float, bool]:
        calls.append(
            {
                "scored_absent": True,
                "rejected": kwargs.get("rejected_as_non_material_improvement"),
                "candidate_family_depth_reached": kwargs.get("candidate_family_depth_reached"),
            }
        )
        return ("no_actionable_candidates", "exhausted", 0.42, True)

    common = {
        "cur_eval": {"overview": {}},
        "mode_config": {"mode": "balanced"},
        "step_trace": [{"step": 0}],
        "initial_snapshot": {"D": 600},
        "working": {"D": 630},
        "governing_domain": "bending",
        "tightening_mode_active": True,
        "rejected_as_non_material_improvement": 3,
        "no_actionable_after_full_tightening_search": False,
        "cur_ib": False,
        "cur_pass": False,
        "winning_label": None,
        "winning_action_type": None,
        "tightening_step_count": 2,
        "max_tightening_steps": 4,
        "candidate_family_depth_reached": "depth",
        "trace_callback": lambda _ev, _dat: None,
    }
    try:
        module._trace_no_actionable_candidates_solver_stop_coordinator = _stop
        scored_case = module._handle_one_click_solver_no_scored_stop_branch_coordinator(
            scored=[{"candidate": True}],
            **common,
        )
        no_scored_case = module._handle_one_click_solver_no_scored_stop_branch_coordinator(
            scored=[],
            **common,
        )
    finally:
        if original_stop is not None:
            module._trace_no_actionable_candidates_solver_stop_coordinator = original_stop

    return {
        "scored_case": scored_case,
        "no_scored_case": no_scored_case,
        "calls": calls,
    }


def build_payload() -> dict[str, Any]:
    source = _read(AUTO_DESIGN_COMPUTE)
    helper_start, helper_end, helper = _function_segment(
        source,
        "_handle_one_click_solver_no_scored_stop_branch_coordinator",
    )
    aggregate_start, aggregate_end, aggregate = _function_segment(
        source,
        "_handle_one_click_solver_candidate_selection_or_stop_coordinator",
    )
    trace_start, trace_end, trace_helper = _function_segment(
        source,
        "_trace_no_actionable_candidates_solver_stop_coordinator",
    )
    solve_start, solve_end, solve_body = _function_segment(source, "_solve_one_click_to_target")
    selection_state_start, selection_state_end, selection_state_body = _function_segment(
        source, "_resolve_one_click_solver_scored_candidate_selection_state_coordinator"
    )
    import inputs_page_modules.auto_design_compute as module  # noqa: E402

    runtime = _run_cases(module)
    runtime_checks = {
        "scored_case_passes_through_without_stop_call": runtime["scored_case"] == {
            "stop_reason": None,
            "status": None,
            "final_distance_to_band": None,
            "no_actionable_after_full_tightening_search": False,
            "should_break": False,
        },
        "no_scored_case_returns_stop_tuple_fields": runtime["no_scored_case"] == {
            "stop_reason": "no_actionable_candidates",
            "status": "exhausted",
            "final_distance_to_band": 0.42,
            "no_actionable_after_full_tightening_search": True,
            "should_break": True,
        },
        "stop_helper_called_only_for_no_scored": runtime["calls"] == [
            {
                "scored_absent": True,
                "rejected": 3,
                "candidate_family_depth_reached": "depth",
            }
        ],
    }
    static_checks = {
        "solver_delegates_scored_candidate_selection_state": (
            "_resolve_one_click_solver_scored_candidate_selection_state_coordinator(" in solve_body
        ),
        "helper_present": "def _handle_one_click_solver_no_scored_stop_branch_coordinator(" in source,
        "helper_preserves_scored_passthrough_gate": "if scored:" in helper
        and '"should_break": False' in helper,
        "helper_delegates_stop_trace": "_trace_no_actionable_candidates_solver_stop_coordinator(" in helper,
        "helper_preserves_tuple_unpack": (
            "stop_reason," in helper
            and "status," in helper
            and "final_distance_to_band," in helper
            and "no_actionable_after_full_tightening_search," in helper
        ),
        "helper_returns_break_state": '"should_break": True' in helper,
        "trace_helper_preserved": "def _trace_no_actionable_candidates_solver_stop_coordinator(" in source
        and '"no_actionable_candidates"' in trace_helper,
        "aggregate_delegates_no_scored_stop_branch": (
            "_handle_one_click_solver_no_scored_stop_branch_coordinator(" in aggregate
        ),
        "aggregate_rehydrates_no_scored_stop_state": (
            'if no_scored_stop_branch_state["should_break"]:' in aggregate
            and '"stop_reason": no_scored_stop_branch_state["stop_reason"]' in aggregate
            and '"status": no_scored_stop_branch_state["status"]' in aggregate
            and '"final_distance_to_band": no_scored_stop_branch_state["final_distance_to_band"]' in aggregate
            and '"no_actionable_after_full_tightening_search": no_scored_stop_branch_state[' in aggregate
        ),
        "solver_delegates_candidate_selection_or_stop": (
            "_handle_one_click_solver_candidate_selection_or_stop_coordinator(" in selection_state_body
        ),
        "solver_rehydrates_selection_or_stop_state_before_break": (
            'if scored_candidate_selection_state["should_break"]:' in solve_body
            and 'stop_reason = scored_candidate_selection_state["stop_reason"]' in solve_body
            and 'status = scored_candidate_selection_state["status"]' in solve_body
            and 'final_distance_to_band = scored_candidate_selection_state[' in solve_body
        ),
        "solver_no_longer_calls_no_actionable_trace_directly": (
            "_trace_no_actionable_candidates_solver_stop_coordinator(" not in solve_body
        ),
    }
    status = "PASS"
    if not all(static_checks.values()) or not all(runtime_checks.values()):
        status = "FAIL"
    return {
        "status": status,
        "surface": "_solve_one_click_to_target_no_scored_stop_branch_coordinator",
        "helper_segment": {
            "function": "_handle_one_click_solver_no_scored_stop_branch_coordinator",
            "start_line": helper_start,
            "end_line": helper_end,
            "line_count": helper_end - helper_start + 1,
        },
        "aggregate_segment": {
            "function": "_handle_one_click_solver_candidate_selection_or_stop_coordinator",
            "start_line": aggregate_start,
            "end_line": aggregate_end,
            "line_count": aggregate_end - aggregate_start + 1,
        },
        "trace_segment": {
            "function": "_trace_no_actionable_candidates_solver_stop_coordinator",
            "start_line": trace_start,
            "end_line": trace_end,
            "line_count": trace_end - trace_start + 1,
        },
        "solver_segment": {
            "function": "_solve_one_click_to_target",
            "start_line": solve_start,
            "end_line": solve_end,
            "line_count": solve_end - solve_start + 1,
        },
        "static_checks": static_checks,
        "runtime_checks": runtime_checks,
        "runtime": runtime,
        "product_behavior_changed": False,
        "next_safe_slice": "extract selected candidate acceptance gate coordinator",
    }


def write_artifacts(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now().isoformat(timespec="seconds").replace(":", "-")
    json_path = ARTIFACT_DIR / (
        f"inputs_page_solver_no_scored_stop_branch_coordinator_extraction_{stamp}.json"
    )
    md_path = AUDIT_DIR / (
        f"inputs_page_solver_no_scored_stop_branch_coordinator_extraction_{stamp}.md"
    )
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Solver No-Scored Stop Branch Coordinator Extraction",
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
