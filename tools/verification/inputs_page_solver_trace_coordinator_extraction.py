"""Verify one-click solver trace coordinator extraction."""

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


def _run_case(module: Any, *, rid: str | None, ev: str) -> dict[str, Any]:
    original = getattr(module, "_append_design_guide_trace", None)
    calls: list[dict[str, Any]] = []

    def _fake_append(ev_arg: str, dat_arg: dict, *, run_id: str, source: str) -> None:
        calls.append(
            {
                "ev": ev_arg,
                "dat": dict(dat_arg),
                "run_id": run_id,
                "source": source,
            }
        )

    stop_traced = [False]
    try:
        module._append_design_guide_trace = _fake_append
        returned = module._append_one_click_solver_trace_coordinator(
            rid=rid,
            stop_traced=stop_traced,
            ev=ev,
            dat={"value": 1},
            trace_source="unit-trace",
        )
    finally:
        if original is not None:
            module._append_design_guide_trace = original

    expected_calls = [] if not rid else [{"ev": ev, "dat": {"value": 1}, "run_id": rid, "source": "unit-trace"}]
    return {
        "rid": rid,
        "ev": ev,
        "returned": returned,
        "calls": calls,
        "stop_traced": list(stop_traced),
        "matches": (
            returned is None
            and calls == expected_calls
            and stop_traced == ([True] if rid and ev == "stop" else [False])
        ),
    }


def build_payload() -> dict[str, Any]:
    source = _read(AUTO_DESIGN_COMPUTE)
    helper_start, helper_end, helper = _function_segment(source, "_append_one_click_solver_trace_coordinator")
    solve_start, solve_end, solve_body = _function_segment(source, "_solve_one_click_to_target")
    import inputs_page_modules.auto_design_compute as module  # noqa: E402

    runtime_rows = [
        _run_case(module, rid="trace-1", ev="initial_eval"),
        _run_case(module, rid="trace-2", ev="stop"),
        _run_case(module, rid=None, ev="stop"),
    ]
    static_checks = {
        "helper_present": "def _append_one_click_solver_trace_coordinator(" in source,
        "helper_preserves_rid_guard": "if rid:" in helper,
        "helper_preserves_stop_flag": 'if ev == "stop":' in helper and "stop_traced[0] = True" in helper,
        "helper_uses_existing_trace_writer": "_append_design_guide_trace(ev, dat, run_id=rid, source=trace_source)" in helper,
        "solver_local_trace_adapter_delegates": "_append_one_click_solver_trace_coordinator(" in solve_body,
        "solver_trace_call_sites_preserved": solve_body.count("_t(") >= 20,
    }
    status = "PASS"
    if not all(static_checks.values()) or any(not row["matches"] for row in runtime_rows):
        status = "FAIL"
    return {
        "status": status,
        "surface": "_solve_one_click_to_target_trace_coordinator",
        "helper_segment": {
            "function": "_append_one_click_solver_trace_coordinator",
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
        "runtime_rows": runtime_rows,
        "product_behavior_changed": False,
        "next_safe_slice": "extract blocked-initial-state return assembly from _solve_one_click_to_target",
    }


def write_artifacts(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now().isoformat(timespec="seconds").replace(":", "-")
    json_path = ARTIFACT_DIR / f"inputs_page_solver_trace_coordinator_extraction_{stamp}.json"
    md_path = AUDIT_DIR / f"inputs_page_solver_trace_coordinator_extraction_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# One-Click Solver Trace Coordinator Extraction",
        "",
        f"Status: `{payload['status']}`",
        "",
        "## Static Checks",
    ]
    for key, value in payload["static_checks"].items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(["", "## Runtime Rows"])
    for row in payload["runtime_rows"]:
        lines.append(f"- `rid={row['rid']} ev={row['ev']}`: `{row['matches']}`")
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
