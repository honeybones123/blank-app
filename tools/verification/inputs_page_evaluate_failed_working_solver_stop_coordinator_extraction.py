"""Verify evaluate-failed-working solver stop coordinator extraction."""

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
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            start = int(node.lineno)
            end = int(getattr(node, "end_lineno", node.lineno))
            lines = source.splitlines()
            return start, end, "\n".join(lines[start - 1 : end])
    raise AssertionError(f"Function not found: {name}")


def _run_case(module: Any) -> dict[str, Any]:
    original_diff = getattr(module, "_one_click_diff_accumulated_updates", None)
    calls: list[dict[str, Any]] = []

    def _fake_diff(initial_snapshot: dict, working: dict) -> dict[str, Any]:
        return {
            "initial": initial_snapshot.get("D"),
            "working": working.get("D"),
        }

    def _trace(ev: str, dat: dict) -> None:
        calls.append({"ev": ev, "dat": dict(dat)})

    try:
        module._one_click_diff_accumulated_updates = _fake_diff
        returned = module._trace_evaluate_failed_working_solver_stop_coordinator(
            step_trace=[{"label": "one"}, {"label": "two"}],
            initial_snapshot={"D": 600},
            working={"D": 650},
            winning_label="Previous winner",
            winning_action_type="tighten",
            trace_callback=_trace,
        )
    finally:
        if original_diff is not None:
            module._one_click_diff_accumulated_updates = original_diff

    expected_trace = {
        "ev": "stop",
        "dat": {
            "stop_reason": "evaluate_failed_working",
            "step_count": 2,
            "status": "failed",
            "final_preview_util": None,
            "reached_target_band": False,
            "all_key_pass": False,
            "winning_label": "Previous winner",
            "winning_action_type": "tighten",
            "final_updates": {"initial": 600, "working": 650},
        },
    }
    return {
        "returned": returned,
        "calls": calls,
        "matches": returned == ("evaluate_failed_working", "failed") and calls == [expected_trace],
    }


def build_payload() -> dict[str, Any]:
    source = _read(AUTO_DESIGN_COMPUTE)
    helper_start, helper_end, helper = _function_segment(source, "_trace_evaluate_failed_working_solver_stop_coordinator")
    current_eval_start, current_eval_end, current_eval_helper = _function_segment(
        source,
        "_prepare_one_click_solver_current_iteration_eval_state_coordinator",
    )
    solve_start, solve_end, solve_body = _function_segment(source, "_solve_one_click_to_target")
    import inputs_page_modules.auto_design_compute as module  # noqa: E402

    runtime = _run_case(module)
    static_checks = {
        "helper_present": "def _trace_evaluate_failed_working_solver_stop_coordinator(" in source,
        "helper_preserves_stop_reason": '"evaluate_failed_working"' in helper,
        "helper_preserves_failed_status": '"failed"' in helper,
        "helper_uses_step_trace_count": '"step_count": len(step_trace)' in helper,
        "helper_uses_existing_diff_builder": "_one_click_diff_accumulated_updates(initial_snapshot, working)" in helper,
        "current_eval_delegates_evaluate_failed_working_stop": "_trace_evaluate_failed_working_solver_stop_coordinator("
        in current_eval_helper,
        "solver_delegates_current_iteration_eval_state": "_prepare_one_click_solver_current_iteration_eval_state_coordinator("
        in solve_body,
        "solver_no_longer_inlines_evaluate_failed_working_trace": (
            'stop_reason = "evaluate_failed_working"\n'
            '            status = "failed"\n'
            '            _t('
        )
        not in solve_body,
    }
    status = "PASS"
    if not all(static_checks.values()) or not runtime["matches"]:
        status = "FAIL"
    return {
        "status": status,
        "surface": "_solve_one_click_to_target_evaluate_failed_working_stop_coordinator",
        "helper_segment": {
            "function": "_trace_evaluate_failed_working_solver_stop_coordinator",
            "start_line": helper_start,
            "end_line": helper_end,
            "line_count": helper_end - helper_start + 1,
        },
        "current_iteration_eval_segment": {
            "function": "_prepare_one_click_solver_current_iteration_eval_state_coordinator",
            "start_line": current_eval_start,
            "end_line": current_eval_end,
            "line_count": current_eval_end - current_eval_start + 1,
        },
        "solver_segment": {
            "function": "_solve_one_click_to_target",
            "start_line": solve_start,
            "end_line": solve_end,
            "line_count": solve_end - solve_start + 1,
        },
        "static_checks": static_checks,
        "runtime": runtime,
        "product_behavior_changed": False,
        "next_safe_slice": "extract evaluate_failed_after_apply stop branch from _solve_one_click_to_target",
    }


def write_artifacts(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now().isoformat(timespec="seconds").replace(":", "-")
    json_path = ARTIFACT_DIR / f"inputs_page_evaluate_failed_working_solver_stop_coordinator_extraction_{stamp}.json"
    md_path = AUDIT_DIR / f"inputs_page_evaluate_failed_working_solver_stop_coordinator_extraction_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Evaluate-Failed-Working Solver Stop Coordinator Extraction",
        "",
        f"Status: `{payload['status']}`",
        "",
        "## Static Checks",
    ]
    for key, value in payload["static_checks"].items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(
        [
            "",
            "## Runtime",
            f"- Stop tuple and trace match: `{payload['runtime']['matches']}`",
            "",
            "## Next Safe Slice",
            "",
            str(payload["next_safe_slice"]),
        ]
    )
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, md_path


def main() -> int:
    payload = build_payload()
    json_path, md_path = write_artifacts(payload)
    print(json.dumps({"status": payload["status"], "json": str(json_path), "report": str(md_path)}, indent=2))
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
