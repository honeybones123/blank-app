"""Verify one-click solver trace callback factory extraction."""

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


def _nested_function_names(function_source: str) -> list[str]:
    tree = ast.parse(function_source)
    root = next(node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef))
    names: list[str] = []
    for node in ast.walk(root):
        if node is root:
            continue
        if isinstance(node, ast.FunctionDef):
            names.append(node.name)
    return names


def _run_case(module: Any) -> dict[str, Any]:
    original_append = getattr(module, "_append_design_guide_trace", None)
    calls: list[dict[str, Any]] = []
    stop_traced = [False]

    def _append(ev: str, dat: dict[str, Any], *, run_id: str, source: str) -> None:
        calls.append({"ev": ev, "dat": dict(dat), "run_id": run_id, "source": source})

    try:
        module._append_design_guide_trace = _append
        cb = module._build_one_click_solver_trace_callback_coordinator(
            rid="run-123",
            stop_traced=stop_traced,
            trace_source="unit_source",
        )
        cb("iteration_start", {"step": 1})
        before_stop = bool(stop_traced[0])
        cb("stop", {"stop_reason": "done"})
        after_stop = bool(stop_traced[0])
        no_run_calls_before = list(calls)
        no_run_stop_traced = [False]
        no_run_cb = module._build_one_click_solver_trace_callback_coordinator(
            rid=None,
            stop_traced=no_run_stop_traced,
            trace_source="unit_source",
        )
        no_run_cb("stop", {"stop_reason": "silent"})
    finally:
        if original_append is not None:
            module._append_design_guide_trace = original_append

    expected_calls = [
        {
            "ev": "iteration_start",
            "dat": {"step": 1},
            "run_id": "run-123",
            "source": "unit_source",
        },
        {
            "ev": "stop",
            "dat": {"stop_reason": "done"},
            "run_id": "run-123",
            "source": "unit_source",
        },
    ]
    return {
        "calls": calls,
        "calls_match": calls == expected_calls,
        "before_stop": before_stop,
        "after_stop": after_stop,
        "no_run_added_calls": calls == no_run_calls_before,
        "no_run_stop_traced": bool(no_run_stop_traced[0]),
    }


def build_payload() -> dict[str, Any]:
    source = _read(AUTO_DESIGN_COMPUTE)
    helper_start, helper_end, helper = _function_segment(
        source,
        "_build_one_click_solver_trace_callback_coordinator",
    )
    _, _, initial_state_helper = _function_segment(
        source,
        "_prepare_one_click_solver_initial_state_coordinator",
    )
    solve_start, solve_end, solve_body = _function_segment(source, "_solve_one_click_to_target")
    runtime_setup_start, runtime_setup_end, runtime_setup_body = _function_segment(
        source, "_prepare_one_click_solver_runtime_setup_state_coordinator"
    )
    import inputs_page_modules.auto_design_compute as module  # noqa: E402

    runtime = _run_case(module)
    nested_functions = _nested_function_names(solve_body)
    static_checks = {
        "solver_delegates_runtime_setup_state": (
            "_prepare_one_click_solver_runtime_setup_state_coordinator(" in solve_body
        ),
        "helper_present": "def _build_one_click_solver_trace_callback_coordinator(" in source,
        "helper_delegates_to_append_trace": "_append_one_click_solver_trace_coordinator(" in helper,
        "helper_returns_callback": "return _trace_callback" in helper,
        "initial_state_helper_builds_trace_callback": "_build_one_click_solver_trace_callback_coordinator("
        in initial_state_helper,
        "solver_delegates_initial_state": "_prepare_one_click_solver_initial_state_coordinator(" in runtime_setup_body,
        "solver_no_longer_defines_nested_trace_callback": "_t" not in nested_functions,
    }
    runtime_checks = {
        "calls_match": bool(runtime["calls_match"]),
        "stop_flag_false_before_stop": runtime["before_stop"] is False,
        "stop_flag_true_after_stop": runtime["after_stop"] is True,
        "none_run_id_is_silent": bool(runtime["no_run_added_calls"]) and runtime["no_run_stop_traced"] is False,
    }
    status = "PASS"
    if not all(static_checks.values()) or not all(runtime_checks.values()):
        status = "FAIL"
    return {
        "status": status,
        "surface": "_solve_one_click_to_target_trace_callback_factory",
        "helper_segment": {
            "function": "_build_one_click_solver_trace_callback_coordinator",
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
        "runtime": runtime,
        "product_behavior_changed": False,
        "next_safe_slice": "extract a narrow candidate no-real-change/prune prefilter coordinator",
    }


def write_artifacts(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now().isoformat(timespec="seconds").replace(":", "-")
    json_path = ARTIFACT_DIR / f"inputs_page_solver_trace_callback_factory_extraction_{stamp}.json"
    md_path = AUDIT_DIR / f"inputs_page_solver_trace_callback_factory_extraction_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Solver Trace Callback Factory Extraction",
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
    lines.extend(
        [
            "",
            "## Next Safe Slice",
            "",
            str(payload["next_safe_slice"]),
        ],
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
