"""Verify auto-design run skip-gate coordinator extraction."""

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


class _FakeStreamlit:
    def __init__(self, session_state: dict[str, Any]) -> None:
        self.session_state = dict(session_state)


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


def _run_case(
    module: Any,
    *,
    session_state: dict[str, Any],
    should_run: bool,
    entry_source_norm: str,
) -> dict[str, Any]:
    original_st = getattr(module, "st", None)
    original_should = getattr(module, "_should_run_auto_design", None)
    try:
        module.st = _FakeStreamlit(session_state)
        module._should_run_auto_design = lambda: should_run
        result = module._resolve_auto_design_run_skip_gate_coordinator(
            entry_source_norm=entry_source_norm,
        )
    finally:
        if original_st is not None:
            module.st = original_st
        if original_should is not None:
            module._should_run_auto_design = original_should
    return dict(result)


def _runtime() -> dict[str, Any]:
    import inputs_page_modules.auto_design_compute as module  # noqa: E402

    cases = {
        "compute_first": _run_case(
            module,
            session_state={"_compute_in_progress": True, "_solver_running": True},
            should_run=False,
            entry_source_norm="inputs_handle_auto_design",
        ),
        "should_run_false": _run_case(
            module,
            session_state={"_compute_in_progress": False, "_solver_running": False},
            should_run=False,
            entry_source_norm="inputs_handle_auto_design",
        ),
        "solver_running": _run_case(
            module,
            session_state={
                "_compute_in_progress": False,
                "_solver_running": True,
                "auto_design_latch_owner": "other",
            },
            should_run=True,
            entry_source_norm="inputs_handle_auto_design",
        ),
        "solver_bypassed": _run_case(
            module,
            session_state={
                "_compute_in_progress": False,
                "_solver_running": True,
                "auto_design_latch_owner": "handle_auto_design",
            },
            should_run=True,
            entry_source_norm="inputs_handle_auto_design",
        ),
        "continue": _run_case(
            module,
            session_state={"_compute_in_progress": False, "_solver_running": False},
            should_run=True,
            entry_source_norm="run_one_click_auto_design",
        ),
    }
    checks = {
        "compute_in_progress_wins_first": cases["compute_first"] == {
            "skip_reason": "compute_in_progress",
            "solver_running_bypassed": False,
        },
        "should_run_false_skips_second": cases["should_run_false"] == {
            "skip_reason": "should_run_auto_design_false",
            "solver_running_bypassed": False,
        },
        "solver_running_skips_without_bypass": cases["solver_running"] == {
            "skip_reason": "solver_running",
            "solver_running_bypassed": False,
        },
        "handle_owner_bypasses_solver_running": cases["solver_bypassed"] == {
            "skip_reason": None,
            "solver_running_bypassed": True,
        },
        "continue_without_skip": cases["continue"] == {
            "skip_reason": None,
            "solver_running_bypassed": False,
        },
    }
    return {"cases": cases, "checks": checks}


def build_payload() -> dict[str, Any]:
    source = _read(AUTO_DESIGN_COMPUTE)
    helper_start, helper_end, helper = _function_segment(
        source,
        "_resolve_auto_design_run_skip_gate_coordinator",
    )
    run_state_start, run_state_end, run_state_helper = _function_segment(
        source,
        "_prepare_one_click_auto_design_run_state_coordinator",
    )
    run_start, run_end, run_body = _function_segment(source, "run_one_click_auto_design")
    runtime = _runtime()
    static_checks = {
        "helper_present": "def _resolve_auto_design_run_skip_gate_coordinator(" in source,
        "helper_checks_compute_first": helper.find('"_compute_in_progress"') < helper.find("_should_run_auto_design()"),
        "helper_preserves_three_skip_reasons": all(
            token in helper
            for token in [
                '"compute_in_progress"',
                '"should_run_auto_design_false"',
                '"solver_running"',
            ]
        ),
        "helper_preserves_handle_owner_bypass": all(
            token in helper
            for token in [
                'entry_source_norm == "inputs_handle_auto_design"',
                '"auto_design_latch_owner"',
                '"handle_auto_design"',
            ]
        ),
        "run_delegates_skip_gate": "_resolve_auto_design_run_skip_gate_coordinator(" in run_body,
        "run_has_single_skipped_return_call": run_body.count("_trace_run_skipped_return_coordinator(") == 1,
        "run_rehydrates_solver_bypass": '_solver_running_bypassed = bool(skip_gate_state["solver_running_bypassed"])' in run_body,
        "run_delegates_run_state_after_skip_gate": (
            run_body.find("_resolve_auto_design_run_skip_gate_coordinator(")
            < run_body.find("_prepare_one_click_auto_design_run_state_coordinator(")
        ),
        "run_state_helper_consumes_invoke": "_consume_auto_design_invoke_after_solver_entry_confirmed()" in run_state_helper,
    }
    status = "PASS"
    if not all(static_checks.values()) or not all(runtime["checks"].values()):
        status = "FAIL"
    return {
        "status": status,
        "surface": "run_one_click_auto_design_skip_gate_coordinator",
        "helper_segment": {
            "function": "_resolve_auto_design_run_skip_gate_coordinator",
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
        "run_state_segment": {
            "function": "_prepare_one_click_auto_design_run_state_coordinator",
            "start_line": run_state_start,
            "end_line": run_state_end,
            "line_count": run_state_end - run_state_start + 1,
        },
        "static_checks": static_checks,
        "runtime": runtime,
        "product_behavior_changed": False,
        "next_safe_slice": "update/remove stale skip-return verifier assumptions or extract run pre-state setup",
    }


def write_artifacts(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now().isoformat(timespec="seconds").replace(":", "-")
    json_path = ARTIFACT_DIR / f"inputs_page_auto_design_run_skip_gate_coordinator_extraction_{stamp}.json"
    md_path = AUDIT_DIR / f"inputs_page_auto_design_run_skip_gate_coordinator_extraction_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Auto Design Run Skip-Gate Coordinator Extraction",
        "",
        f"Status: `{payload['status']}`",
        "",
        "## Static Checks",
    ]
    for key, value in payload["static_checks"].items():
        lines.append(f"- `{key}`: `{value}`")
    lines.append("")
    lines.append("## Runtime Checks")
    for key, value in payload["runtime"]["checks"].items():
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
