"""Verify initial solver eval trace coordinator extraction."""

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
    original_truth = getattr(module, "_stage3_final_published_shear_truth_bundle", None)
    original_issue = getattr(module, "_stage3_remaining_issue_class_from_overview_state", None)
    calls: list[dict[str, Any]] = []

    def _fake_truth(working: dict) -> dict[str, Any]:
        return {"D": working.get("D")}

    def _fake_issue(working: dict, overview: dict | None) -> str:
        return f"{working.get('D')}:{overview.get('issue') if overview else None}"

    def _trace(ev: str, dat: dict) -> None:
        calls.append({"ev": ev, "dat": dict(dat)})

    try:
        module._stage3_final_published_shear_truth_bundle = _fake_truth
        module._stage3_remaining_issue_class_from_overview_state = _fake_issue
        module._trace_initial_solver_eval_coordinator(
            init_eval={"overview": {"statuses": {"shear": "PASS"}, "issue": "none"}},
            init_worst=0.86,
            init_in_band=True,
            init_pass=True,
            working={"D": 650},
            trace_callback=_trace,
        )
    finally:
        if original_truth is not None:
            module._stage3_final_published_shear_truth_bundle = original_truth
        if original_issue is not None:
            module._stage3_remaining_issue_class_from_overview_state = original_issue

    expected = [
        {
            "ev": "initial_eval",
            "dat": {
                "initial_worst_util": 0.86,
                "initial_statuses": {"shear": "PASS"},
                "initial_in_target_band": True,
                "initial_all_key_pass": True,
                "stage3_shear_truth_at_initial_eval": {"D": 650},
                "stage3_remaining_issue_class": "650:none",
            },
        }
    ]
    return {"calls": calls, "matches": calls == expected}


def build_payload() -> dict[str, Any]:
    source = _read(AUTO_DESIGN_COMPUTE)
    helper_start, helper_end, helper = _function_segment(source, "_trace_initial_solver_eval_coordinator")
    eval_helper_start, eval_helper_end, eval_helper = _function_segment(
        source,
        "_prepare_one_click_solver_initial_eval_state_coordinator",
    )
    solve_start, solve_end, solve_body = _function_segment(source, "_solve_one_click_to_target")
    runtime_setup_start, runtime_setup_end, runtime_setup_body = _function_segment(
        source, "_prepare_one_click_solver_runtime_setup_state_coordinator"
    )
    import inputs_page_modules.auto_design_compute as module  # noqa: E402

    runtime = _run_case(module)
    static_checks = {
        "solver_delegates_runtime_setup_state": (
            "_prepare_one_click_solver_runtime_setup_state_coordinator(" in solve_body
        ),
        "helper_present": "def _trace_initial_solver_eval_coordinator(" in source,
        "helper_emits_initial_eval_trace": 'trace_callback(\n        "initial_eval",' in helper,
        "helper_preserves_stage3_truth_field": "_stage3_final_published_shear_truth_bundle(working)" in helper,
        "helper_preserves_remaining_issue_field": "_stage3_remaining_issue_class_from_overview_state(working, _init_ov)" in helper,
        "initial_eval_state_delegates_initial_eval_trace": "_trace_initial_solver_eval_coordinator(" in eval_helper,
        "solver_delegates_initial_eval_state": "_prepare_one_click_solver_initial_eval_state_coordinator("
        in runtime_setup_body,
        "solver_no_longer_inlines_initial_eval_trace": '_t(\n        "initial_eval",' not in solve_body,
    }
    status = "PASS"
    if not all(static_checks.values()) or not runtime["matches"]:
        status = "FAIL"
    return {
        "status": status,
        "surface": "_solve_one_click_to_target_initial_eval_trace_coordinator",
        "helper_segment": {
            "function": "_trace_initial_solver_eval_coordinator",
            "start_line": helper_start,
            "end_line": helper_end,
            "line_count": helper_end - helper_start + 1,
        },
        "initial_eval_state_segment": {
            "function": "_prepare_one_click_solver_initial_eval_state_coordinator",
            "start_line": eval_helper_start,
            "end_line": eval_helper_end,
            "line_count": eval_helper_end - eval_helper_start + 1,
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
        "next_safe_slice": "extract candidate pool trace coordinator",
    }


def write_artifacts(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now().isoformat(timespec="seconds").replace(":", "-")
    json_path = ARTIFACT_DIR / f"inputs_page_initial_solver_eval_trace_coordinator_extraction_{stamp}.json"
    md_path = AUDIT_DIR / f"inputs_page_initial_solver_eval_trace_coordinator_extraction_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Initial Solver Eval Trace Coordinator Extraction",
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
            f"- Initial trace matches: `{payload['runtime']['matches']}`",
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
