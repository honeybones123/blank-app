"""Verify one-click auto-design run-entry coordinator extraction."""

from __future__ import annotations

import ast
import contextlib
import datetime as _dt
import io
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


class _FakeStreamlit:
    def __init__(self) -> None:
        self.session_state: dict[str, Any] = {}


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
    originals = {
        "st": getattr(module, "st", None),
        "_set_design_guide_live_breadcrumb": getattr(module, "_set_design_guide_live_breadcrumb", None),
        "_new_design_guide_trace_run_id": getattr(module, "_new_design_guide_trace_run_id", None),
        "_design_guide_tracer_path": getattr(module, "_design_guide_tracer_path", None),
        "_should_run_auto_design": getattr(module, "_should_run_auto_design", None),
        "_append_design_guide_trace": getattr(module, "_append_design_guide_trace", None),
        "_agent_debug_log": getattr(module, "_agent_debug_log", None),
    }
    fake_st = _FakeStreamlit()
    fake_st.session_state.update(
        {
            "auto_design_latch_owner": "owner-a",
            "_solver_running": False,
            "_compute_in_progress": False,
        },
    )
    breadcrumbs: list[str] = []
    traces: list[dict[str, Any]] = []
    debug_logs: list[dict[str, Any]] = []

    def _breadcrumb(label: str) -> None:
        breadcrumbs.append(label)

    def _append(ev: str, dat: dict[str, Any], *, run_id: str, source: str) -> None:
        traces.append({"ev": ev, "dat": dict(dat), "run_id": run_id, "source": source})

    def _debug(message: str, payload: dict[str, Any], *, location: str, hypothesis_id: str) -> None:
        debug_logs.append(
            {
                "message": message,
                "payload": dict(payload),
                "location": location,
                "hypothesis_id": hypothesis_id,
            },
        )

    stderr = io.StringIO()
    try:
        module.st = fake_st
        module._set_design_guide_live_breadcrumb = _breadcrumb
        module._new_design_guide_trace_run_id = lambda: "run-entry-123"
        module._design_guide_tracer_path = lambda: "trace/path.jsonl"
        module._should_run_auto_design = lambda: True
        module._append_design_guide_trace = _append
        module._agent_debug_log = _debug
        with contextlib.redirect_stderr(stderr):
            result = module._start_one_click_auto_design_run_entry_coordinator(
                trigger_fingerprint=("x", 1),
                entry_source=" primary_apply_button ",
            )
    finally:
        for name, original in originals.items():
            if original is not None:
                setattr(module, name, original)

    expected_result = {
        "trace_run_id": "run-entry-123",
        "tracer_path": "trace/path.jsonl",
        "trace_src": "run_one_click_auto_design",
        "entry_source_norm": "primary_apply_button",
        "latch_owner": "owner-a",
    }
    expected_traces = [
        {
            "ev": "trace_ping",
            "dat": {"tracer_path": "trace/path.jsonl", "phase": "entry"},
            "run_id": "run-entry-123",
            "source": "run_one_click_auto_design",
        },
    ]
    return {
        "result": result,
        "result_matches": result == expected_result,
        "breadcrumbs": breadcrumbs,
        "breadcrumbs_match": breadcrumbs == ["DG TRACE ENTRY"],
        "traces": traces,
        "traces_match": traces == expected_traces,
        "debug_logs": debug_logs,
        "debug_log_matches": bool(debug_logs)
        and debug_logs[0]["payload"].get("trigger_fingerprint") == "('x', 1)"
        and debug_logs[0]["payload"].get("run_one_click_entry_source") == "primary_apply_button"
        and debug_logs[0]["payload"].get("auto_design_latch_owner") == "owner-a",
        "stderr_contains_entry": "DG TRACE ENTRY" in stderr.getvalue()
        and "trace_run_id=run-entry-123" in stderr.getvalue(),
    }


def build_payload() -> dict[str, Any]:
    source = _read(AUTO_DESIGN_COMPUTE)
    helper_start, helper_end, helper = _function_segment(
        source,
        "_start_one_click_auto_design_run_entry_coordinator",
    )
    run_start, run_end, run_body = _function_segment(source, "run_one_click_auto_design")
    import inputs_page_modules.auto_design_compute as module  # noqa: E402

    runtime = _run_case(module)
    static_checks = {
        "helper_present": "def _start_one_click_auto_design_run_entry_coordinator(" in source,
        "helper_sets_breadcrumb": '_set_design_guide_live_breadcrumb("DG TRACE ENTRY")' in helper,
        "helper_creates_trace_run_id": "_new_design_guide_trace_run_id()" in helper,
        "helper_preserves_trace_ping": '"trace_ping"' in helper and '"phase": "entry"' in helper,
        "helper_preserves_agent_debug_log": "_agent_debug_log(" in helper,
        "helper_returns_entry_state": '"entry_source_norm": entry_source_norm' in helper,
        "run_delegates_entry_setup": "_start_one_click_auto_design_run_entry_coordinator(" in run_body,
        "run_rehydrates_trace_run_id": 'trace_run_id = run_entry_state["trace_run_id"]' in run_body,
        "run_rehydrates_entry_source_norm": 'entry_source_norm = run_entry_state["entry_source_norm"]' in run_body,
    }
    runtime_checks = {
        "result_matches": bool(runtime["result_matches"]),
        "breadcrumbs_match": bool(runtime["breadcrumbs_match"]),
        "traces_match": bool(runtime["traces_match"]),
        "debug_log_matches": bool(runtime["debug_log_matches"]),
        "stderr_contains_entry": bool(runtime["stderr_contains_entry"]),
    }
    status = "PASS"
    if not all(static_checks.values()) or not all(runtime_checks.values()):
        status = "FAIL"
    return {
        "status": status,
        "surface": "run_one_click_auto_design_entry_coordinator",
        "helper_segment": {
            "function": "_start_one_click_auto_design_run_entry_coordinator",
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
        "runtime_checks": runtime_checks,
        "runtime": runtime,
        "product_behavior_changed": False,
        "next_safe_slice": "extract stale-latch entry bookkeeping coordinator",
    }


def write_artifacts(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now().isoformat(timespec="seconds").replace(":", "-")
    json_path = ARTIFACT_DIR / f"inputs_page_auto_design_run_entry_coordinator_extraction_{stamp}.json"
    md_path = AUDIT_DIR / f"inputs_page_auto_design_run_entry_coordinator_extraction_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Auto Design Run Entry Coordinator Extraction",
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
