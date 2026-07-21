"""Verify evaluate-failed solver return coordinator extraction."""

from __future__ import annotations

import ast
import copy
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


def _old_payload(
    *,
    working: dict[str, Any],
    t_lo: float,
    t_hi: float,
    rid: str | None,
    trace_callback,
) -> dict[str, Any]:
    dbg = {
        "iteration_count": 0,
        "initial_worst_util": None,
        "final_worst_util": None,
        "target_band": {"min": t_lo, "max": t_hi},
        "stop_reason": "evaluate_failed",
        "reached_target_band": False,
        "step_candidate_labels": [],
        "all_key_pass": False,
        "trace_run_id": rid,
    }
    trace_callback(
        "stop",
        {
            "stop_reason": "evaluate_failed",
            "step_count": 0,
            "status": "failed",
            "final_preview_util": None,
            "reached_target_band": False,
            "all_key_pass": False,
            "winning_label": None,
            "winning_action_type": None,
            "final_updates": {},
        },
    )
    return {
        "status": "failed",
        "stop_reason": "evaluate_failed",
        "step_count": 0,
        "initial_worst_util": None,
        "final_worst_util": None,
        "reached_target_band": False,
        "all_key_pass": False,
        "final_updates": {},
        "final_state_preview": copy.deepcopy(working),
        "step_trace": [],
        "winning_label": None,
        "winning_action_type": None,
        "one_click_solver_debug": dbg,
        "trace_run_id": rid,
    }


def _run_case(module: Any) -> dict[str, Any]:
    original_copy = getattr(module, "copy", None)
    working = {"beam": {"D": 600}, "meta": "unit"}
    old_traces: list[dict[str, Any]] = []
    new_traces: list[dict[str, Any]] = []

    def _old_trace(ev: str, dat: dict) -> None:
        old_traces.append({"ev": ev, "dat": dict(dat)})

    def _new_trace(ev: str, dat: dict) -> None:
        new_traces.append({"ev": ev, "dat": dict(dat)})

    try:
        module.copy = copy
        old = _old_payload(
            working=working,
            t_lo=0.85,
            t_hi=0.95,
            rid="trace-eval-failed",
            trace_callback=_old_trace,
        )
        new = module._build_evaluate_failed_solver_return_coordinator(
            working=working,
            t_lo=0.85,
            t_hi=0.95,
            rid="trace-eval-failed",
            trace_callback=_new_trace,
        )
    finally:
        if original_copy is not None:
            module.copy = original_copy

    new["final_state_preview"]["beam"]["D"] = 700
    copy_isolated = working["beam"]["D"] == 600
    new["final_state_preview"]["beam"]["D"] = 600
    return {
        "matches": old == new and old_traces == new_traces and copy_isolated,
        "trace_matches": old_traces == new_traces,
        "copy_isolated": copy_isolated,
    }


def build_payload() -> dict[str, Any]:
    source = _read(AUTO_DESIGN_COMPUTE)
    helper_start, helper_end, helper = _function_segment(source, "_build_evaluate_failed_solver_return_coordinator")
    solve_start, solve_end, solve_body = _function_segment(source, "_solve_one_click_to_target")
    import inputs_page_modules.auto_design_compute as module  # noqa: E402

    runtime = _run_case(module)
    static_checks = {
        "helper_present": "def _build_evaluate_failed_solver_return_coordinator(" in source,
        "helper_emits_stop_trace": 'trace_callback(\n        "stop"' in helper,
        "helper_preserves_failed_status": '"status": "failed"' in helper,
        "helper_preserves_target_band": '"target_band": {"min": t_lo, "max": t_hi}' in helper,
        "helper_preserves_deepcopy_preview": "copy.deepcopy(working)" in helper,
        "solver_delegates_evaluate_failed_return": "_build_evaluate_failed_solver_return_coordinator(" in solve_body,
        "solver_no_longer_assembles_evaluate_failed_debug_inline": '"stop_reason": "evaluate_failed",\n            "reached_target_band": False,\n            "step_candidate_labels": []' not in solve_body,
    }
    status = "PASS"
    if not all(static_checks.values()) or not runtime["matches"]:
        status = "FAIL"
    return {
        "status": status,
        "surface": "_solve_one_click_to_target_evaluate_failed_return_coordinator",
        "helper_segment": {
            "function": "_build_evaluate_failed_solver_return_coordinator",
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
        "runtime": runtime,
        "product_behavior_changed": False,
        "next_safe_slice": "extract already-in-band return assembly from _solve_one_click_to_target",
    }


def write_artifacts(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now().isoformat(timespec="seconds").replace(":", "-")
    json_path = ARTIFACT_DIR / f"inputs_page_evaluate_failed_solver_return_coordinator_extraction_{stamp}.json"
    md_path = AUDIT_DIR / f"inputs_page_evaluate_failed_solver_return_coordinator_extraction_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Evaluate-Failed Solver Return Coordinator Extraction",
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
            f"- Payload matches: `{payload['runtime']['matches']}`",
            f"- Trace matches: `{payload['runtime']['trace_matches']}`",
            f"- Preview copy isolated: `{payload['runtime']['copy_isolated']}`",
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
