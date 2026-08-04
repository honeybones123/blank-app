"""Verify rescue-decision solver trace coordinator extraction."""

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
    calls: list[dict[str, Any]] = []

    def _trace(ev: str, dat: dict) -> None:
        calls.append({"ev": ev, "dat": dict(dat)})

    module._trace_rescue_decision_solver_coordinator(
        rescue_should_enter=True,
        rescue_entry_reason="blocked",
        rescue_family="shear",
        rescue_tier_requested="wide",
        final_pass=False,
        final_updates={"D": 650},
        stop_reason="no_actionable_candidates",
        rescue_gate_debug={"gate": "open"},
        trace_callback=_trace,
    )
    expected = [
        {
            "ev": "rescue_decision",
            "dat": {
                "rescue_mode_entered": True,
                "rescue_mode_entry_reason": "blocked",
                "rescue_mode_family": "shear",
                "rescue_mode_tier_requested": "wide",
                "final_pass": False,
                "final_updates_present": True,
                "stop_reason_before_rescue": "no_actionable_candidates",
                "gate_debug": {"gate": "open"},
            },
        }
    ]
    return {"calls": calls, "matches": calls == expected}


def build_payload() -> dict[str, Any]:
    source = _read(AUTO_DESIGN_COMPUTE)
    helper_start, helper_end, helper = _function_segment(source, "_trace_rescue_decision_solver_coordinator")
    decision_start, decision_end, decision_helper = _function_segment(
        source,
        "_prepare_one_click_solver_rescue_entry_decision_state_coordinator",
    )
    solve_start, solve_end, solve_body = _function_segment(source, "_solve_one_click_to_target")
    import inputs_page_modules.auto_design_compute as module  # noqa: E402

    runtime = _run_case(module)
    static_checks = {
        "helper_present": "def _trace_rescue_decision_solver_coordinator(" in source,
        "helper_emits_rescue_decision_trace": 'trace_callback(\n        "rescue_decision",' in helper,
        "helper_preserves_gate_debug_copy": '"gate_debug": dict(rescue_gate_debug or {})' in helper,
        "helper_preserves_final_updates_marker": '"final_updates_present": bool(final_updates)' in helper,
        "decision_helper_delegates_rescue_decision_trace": "_trace_rescue_decision_solver_coordinator(" in decision_helper,
        "solver_delegates_rescue_entry_decision": (
            "_prepare_one_click_solver_rescue_entry_decision_state_coordinator(" in solve_body
        ),
        "solver_no_longer_inlines_rescue_decision_trace": '_t(\n        "rescue_decision",' not in solve_body,
        "decision_helper_keeps_rescue_gate_call": "_rescue_mode_should_enter(" in decision_helper,
    }
    status = "PASS"
    if not all(static_checks.values()) or not runtime["matches"]:
        status = "FAIL"
    return {
        "status": status,
        "surface": "_solve_one_click_to_target_rescue_decision_trace_coordinator",
        "helper_segment": {
            "function": "_trace_rescue_decision_solver_coordinator",
            "start_line": helper_start,
            "end_line": helper_end,
            "line_count": helper_end - helper_start + 1,
        },
        "decision_helper_segment": {
            "function": "_prepare_one_click_solver_rescue_entry_decision_state_coordinator",
            "start_line": decision_start,
            "end_line": decision_end,
            "line_count": decision_end - decision_start + 1,
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
        "next_safe_slice": "extract rescue seed attempt trace coordinator",
    }


def write_artifacts(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now().isoformat(timespec="seconds").replace(":", "-")
    json_path = ARTIFACT_DIR / f"inputs_page_rescue_decision_solver_trace_coordinator_extraction_{stamp}.json"
    md_path = AUDIT_DIR / f"inputs_page_rescue_decision_solver_trace_coordinator_extraction_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Rescue-Decision Solver Trace Coordinator Extraction",
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
            f"- Rescue decision trace matches: `{payload['runtime']['matches']}`",
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
