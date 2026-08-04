"""Verify candidate-eval evaluation-failed trace coordinator extraction."""

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

    module._trace_candidate_eval_evaluation_failed_solver_coordinator(
        step_idx=5,
        rc={"title": "Eval fail", "action_type": "preview"},
        norm_u={"b": 300},
        direction={"is_reduction_candidate": False, "is_growth_only": False},
        tightening_mode_active=True,
        governing_domain="bending",
        family_hint="geometry",
        trace_callback=_trace,
    )
    expected = [
        {
            "ev": "candidate_eval",
            "dat": {
                "step": 5,
                "label": "Eval fail",
                "action_type": "preview",
                "updates": {"b": 300},
                "preview_util": None,
                "preview_statuses": None,
                "reaches_target_band": None,
                "distance_to_band": None,
                "duplicate_signature_rejected": False,
                "no_real_change_rejected": False,
                "evaluation_failed": True,
                "ranking_tuple": None,
                "tightening_mode_active": True,
                "reduction_candidate": False,
                "growth_candidate": False,
                "governing_domain": "bending",
                "candidate_family": "geometry",
                "rejection_reason": "evaluation_failed",
            },
        }
    ]
    return {"calls": calls, "matches": calls == expected}


def build_payload() -> dict[str, Any]:
    source = _read(AUTO_DESIGN_COMPUTE)
    helper_start, helper_end, helper = _function_segment(
        source,
        "_trace_candidate_eval_evaluation_failed_solver_coordinator",
    )
    preview_start, preview_end, preview_helper = _function_segment(
        source,
        "_prepare_one_click_solver_candidate_preview_eval_state_coordinator",
    )
    solve_start, solve_end, solve_body = _function_segment(source, "_solve_one_click_to_target")
    import inputs_page_modules.auto_design_compute as module  # noqa: E402

    runtime = _run_case(module)
    static_checks = {
        "helper_present": "def _trace_candidate_eval_evaluation_failed_solver_coordinator(" in source,
        "helper_delegates_to_pre_eval_rejection": "_trace_candidate_eval_pre_eval_rejection_solver_coordinator(" in helper,
        "helper_preserves_failed_reason": '"evaluation_failed"' in helper,
        "helper_overrides_failed_marker": '"evaluation_failed": True' in helper,
        "preview_helper_delegates_evaluation_failed_trace": (
            "_trace_candidate_eval_evaluation_failed_solver_coordinator(" in preview_helper
        ),
        "preview_helper_keeps_peval_none_branch": "if peval is None:" in preview_helper,
        "preview_helper_keeps_evaluation_failed_counter": "rejected_as_evaluation_failed += 1" in preview_helper,
        "solver_delegates_preview_eval_state": (
            "_prepare_one_click_solver_candidate_preview_eval_state_coordinator(" in solve_body
        ),
    }
    status = "PASS"
    if not all(static_checks.values()) or not runtime["matches"]:
        status = "FAIL"
    return {
        "status": status,
        "surface": "_solve_one_click_to_target_candidate_eval_evaluation_failed_trace_coordinator",
        "helper_segment": {
            "function": "_trace_candidate_eval_evaluation_failed_solver_coordinator",
            "start_line": helper_start,
            "end_line": helper_end,
            "line_count": helper_end - helper_start + 1,
        },
        "preview_helper_segment": {
            "function": "_prepare_one_click_solver_candidate_preview_eval_state_coordinator",
            "start_line": preview_start,
            "end_line": preview_end,
            "line_count": preview_end - preview_start + 1,
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
        "next_safe_slice": "extract duplicate-signature candidate trace coordinator",
    }


def write_artifacts(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now().isoformat(timespec="seconds").replace(":", "-")
    json_path = ARTIFACT_DIR / f"inputs_page_candidate_eval_evaluation_failed_trace_coordinator_extraction_{stamp}.json"
    md_path = AUDIT_DIR / f"inputs_page_candidate_eval_evaluation_failed_trace_coordinator_extraction_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Candidate Eval Evaluation-Failed Trace Coordinator Extraction",
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
            f"- Evaluation-failed trace matches: `{payload['runtime']['matches']}`",
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
