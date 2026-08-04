"""Verify run-one-click skipped-return coordinator extraction."""

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


class _FakeSt:
    def __init__(self, session_state: dict[str, Any]) -> None:
        self.session_state = session_state


def _run_case(module: Any, skip_reason: str, session_state: dict[str, Any]) -> dict[str, Any]:
    trace_calls: list[dict[str, Any]] = []
    latch_calls: list[dict[str, Any]] = []
    original_st = getattr(module, "st", None)
    original_sys = getattr(module, "sys", None)
    original_debug = getattr(module, "_auto_design_invoke_debug_snapshot", None)
    original_trace = getattr(module, "_append_design_guide_trace", None)
    original_summary = getattr(module, "_tracer_one_click_action_source_summary", None)

    def _debug_snapshot() -> dict[str, Any]:
        return {"debug_snapshot_marker": skip_reason}

    def _append_trace(event: str, data: dict, *, run_id: str | None = None, source: str | None = None) -> None:
        trace_calls.append(
            {
                "event": event,
                "data": dict(data or {}),
                "run_id": run_id,
                "source": source,
            }
        )

    def _summary(trigger_fingerprint: tuple | None) -> dict[str, Any]:
        return {"trigger_fingerprint": list(trigger_fingerprint or ())}

    def _return_with_latch_clear(reason: str, payload: dict) -> dict:
        latch_calls.append({"reason": reason, "payload_status": payload.get("status")})
        payload = dict(payload)
        payload["auto_design_latch_clear"] = {"reason": reason}
        return payload

    try:
        module.st = _FakeSt(session_state)
        module.sys = sys
        module._auto_design_invoke_debug_snapshot = _debug_snapshot
        module._append_design_guide_trace = _append_trace
        module._tracer_one_click_action_source_summary = _summary
        returned = module._trace_run_skipped_return_coordinator(
            skip_reason,
            trace_run_id="trace-001",
            tracer_path="trace.jsonl",
            trace_src="run_one_click_auto_design",
            entry_source_norm="inputs_handle_auto_design",
            trigger_fingerprint=("apply", "button"),
            return_with_latch_clear=_return_with_latch_clear,
        )
    finally:
        if original_st is not None:
            module.st = original_st
        if original_sys is not None:
            module.sys = original_sys
        if original_debug is not None:
            module._auto_design_invoke_debug_snapshot = original_debug
        if original_trace is not None:
            module._append_design_guide_trace = original_trace
        if original_summary is not None:
            module._tracer_one_click_action_source_summary = original_summary

    return {
        "skip_reason": skip_reason,
        "returned": returned,
        "trace_calls": trace_calls,
        "latch_calls": latch_calls,
        "session_state": dict(session_state),
    }


def build_payload() -> dict[str, Any]:
    source = _read(AUTO_DESIGN_COMPUTE)
    helper_start, helper_end, helper = _function_segment(source, "_trace_run_skipped_return_coordinator")
    run_start, run_end, run_body = _function_segment(source, "run_one_click_auto_design")
    import inputs_page_modules.auto_design_compute as module  # noqa: E402

    cases = [
        _run_case(module, "compute_in_progress", {}),
        _run_case(
            module,
            "solver_running",
            {"_solver_running": True, "auto_design_latch_owner": "handle_auto_design"},
        ),
        _run_case(module, "should_run_auto_design_false", {}),
    ]
    expected = {
        "compute_in_progress": {
            "status": "deferred",
            "idle": "deferred_compute_in_progress",
            "latch_reason": "run_one_click_auto_design:deferred_compute_in_progress",
        },
        "solver_running": {
            "status": "deferred",
            "idle": "deferred_solver_running",
            "latch_reason": "run_one_click_auto_design:deferred_solver_running",
        },
        "should_run_auto_design_false": {
            "status": "idle",
            "idle": "idle_should_run_false",
            "latch_reason": "run_one_click_auto_design:idle_should_run_false",
        },
    }
    runtime_rows: list[dict[str, Any]] = []
    runtime_failures: list[str] = []
    for case in cases:
        exp = expected[case["skip_reason"]]
        returned = dict(case["returned"] or {})
        trace_calls = list(case["trace_calls"] or [])
        latch_calls = list(case["latch_calls"] or [])
        trace_data = dict(trace_calls[0]["data"] or {}) if trace_calls else {}
        row = {
            "skip_reason": case["skip_reason"],
            "status": returned.get("status"),
            "idle": returned.get("auto_design_idle_reason"),
            "latch_reason": latch_calls[0]["reason"] if latch_calls else None,
            "trace_event": trace_calls[0]["event"] if trace_calls else None,
            "session_idle": case["session_state"].get("auto_design_idle_reason"),
            "matches": (
                returned.get("status") == exp["status"]
                and returned.get("auto_design_idle_reason") == exp["idle"]
                and (latch_calls[0]["reason"] if latch_calls else None) == exp["latch_reason"]
                and (trace_calls[0]["event"] if trace_calls else None) == "run_skipped"
                and trace_data.get("auto_design_idle_reason") == exp["idle"]
                and case["session_state"].get("auto_design_idle_reason") == exp["idle"]
                and case["session_state"].get("auto_design_invoke_consumed") is False
            ),
        }
        runtime_rows.append(row)
        if not row["matches"]:
            runtime_failures.append(case["skip_reason"])

    static_checks = {
        "helper_present": "def _trace_run_skipped_return_coordinator(" in source,
        "helper_contains_trace_payload": all(
            token in helper
            for token in (
                "run_skipped",
                "auto_design_idle_reason",
                "run_one_click_solver_running_bypassed",
                "return_with_latch_clear",
            )
        ),
        "nested_skip_helper_removed": "def _trace_run_skipped_return(" not in run_body,
        "run_delegates_skip_return_after_skip_gate": (
            "_resolve_auto_design_run_skip_gate_coordinator(" in run_body
            and run_body.count("_trace_run_skipped_return_coordinator(") == 1
        ),
        "latch_closure_retained": "def _return_with_latch_clear(" in run_body,
        "run_skip_conditions_moved_to_skip_gate": all(
            token in source
            for token in (
                "def _resolve_auto_design_run_skip_gate_coordinator(",
                'st.session_state.get("_compute_in_progress")',
                "not _should_run_auto_design()",
                'st.session_state.get("_solver_running") and not solver_running_bypassed',
            )
        ),
        "run_still_uses_skip_gate_result": all(
            token in run_body
            for token in (
                'skip_gate_state["skip_reason"]',
                'skip_gate_state["solver_running_bypassed"]',
            )
        ),
    }
    status = "PASS"
    if runtime_failures or not all(static_checks.values()):
        status = "FAIL"
    return {
        "status": status,
        "surface": "run_one_click_auto_design_skipped_return_coordinator",
        "helper_segment": {
            "function": "_trace_run_skipped_return_coordinator",
            "start_line": helper_start,
            "end_line": helper_end,
            "line_count": helper_end - helper_start + 1,
        },
        "run_segment": {
            "function": "run_one_click_auto_design",
            "start_line": run_start,
            "end_line": run_end,
            "line_count": run_end - run_start + 1,
        },
        "static_checks": static_checks,
        "runtime_rows": runtime_rows,
        "runtime_failures": runtime_failures,
        "ownership": {
            "moved_to_coordinator_helper": [
                "run skipped trace payload",
                "idle-code projection",
                "deferred/idle payload construction",
            ],
            "retained_in_runner": [
                "skip condition checks",
                "latch-clear closure carrying stale-latch context",
                "normal solver entry and commit flow",
            ],
        },
        "product_behavior_changed": False,
        "next_safe_slice": "extract another run_one_click_auto_design coordinator-only block with its own harness",
    }


def write_artifacts(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now().isoformat(timespec="seconds").replace(":", "-")
    json_path = ARTIFACT_DIR / f"inputs_page_run_skipped_return_coordinator_extraction_{stamp}.json"
    md_path = AUDIT_DIR / f"inputs_page_run_skipped_return_coordinator_extraction_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Run One-Click Skipped Return Coordinator Extraction",
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
            "## Runtime Rows",
        ]
    )
    for row in payload["runtime_rows"]:
        lines.append(f"- `{row['skip_reason']}`: `{row['matches']}`")
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
