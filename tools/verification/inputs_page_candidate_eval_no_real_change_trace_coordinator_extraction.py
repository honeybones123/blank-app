"""Verify candidate-eval no-real-change trace coordinator extraction."""

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


def _direct_trace_events(function_source: str) -> list[str]:
    tree = ast.parse(function_source)
    events: list[str] = []
    for call in ast.walk(tree):
        if not isinstance(call, ast.Call):
            continue
        if not isinstance(call.func, ast.Name) or call.func.id != "_t":
            continue
        if call.args and isinstance(call.args[0], ast.Constant):
            events.append(str(call.args[0].value))
    return events


def _run_case(module: Any, *, norm_u: dict[str, Any], raw_u: dict[str, Any]) -> list[dict[str, Any]]:
    calls: list[dict[str, Any]] = []

    def _trace_cb(ev: str, dat: dict) -> None:
        calls.append({"ev": ev, "dat": dict(dat)})

    module._trace_candidate_eval_no_real_change_solver_coordinator(
        step_idx=7,
        rc={"title": "Already there", "action_type": "noop"},
        norm_u=norm_u,
        raw_u=raw_u,
        direction={"is_reduction_candidate": False, "is_growth_only": True},
        tightening_mode_active=False,
        governing_domain="shear",
        family_hint="shear_adjust",
        trace_callback=_trace_cb,
    )
    return calls


def build_payload() -> dict[str, Any]:
    source = _read(AUTO_DESIGN_COMPUTE)
    helper_start, helper_end, helper = _function_segment(
        source,
        "_trace_candidate_eval_no_real_change_solver_coordinator",
    )
    no_real_change_start, no_real_change_end, no_real_change_helper = _function_segment(
        source,
        "_handle_one_click_solver_no_real_change_candidate_coordinator",
    )
    solve_start, solve_end, solve_body = _function_segment(source, "_solve_one_click_to_target")
    import inputs_page_modules.auto_design_compute as module  # noqa: E402

    norm_runtime = _run_case(module, norm_u={"D": 600}, raw_u={"D": 600})
    raw_fallback_runtime = _run_case(module, norm_u={}, raw_u={"lig_legs": 0})
    expected_norm = [
        {
            "ev": "candidate_eval",
            "dat": {
                "step": 7,
                "label": "Already there",
                "action_type": "noop",
                "updates": {"D": 600},
                "preview_util": None,
                "preview_statuses": None,
                "reaches_target_band": None,
                "distance_to_band": None,
                "duplicate_signature_rejected": False,
                "no_real_change_rejected": True,
                "evaluation_failed": False,
                "ranking_tuple": None,
                "tightening_mode_active": False,
                "reduction_candidate": False,
                "growth_candidate": True,
                "governing_domain": "shear",
                "candidate_family": "shear_adjust",
                "rejection_reason": "no_real_change",
            },
        },
    ]
    expected_raw = [
        {
            **expected_norm[0],
            "dat": {
                **expected_norm[0]["dat"],
                "updates": {"lig_legs": 0},
            },
        },
    ]
    direct_trace_events = _direct_trace_events(solve_body)
    static_checks = {
        "helper_present": "def _trace_candidate_eval_no_real_change_solver_coordinator(" in source,
        "helper_delegates_to_pre_eval_rejection": "_trace_candidate_eval_pre_eval_rejection_solver_coordinator(" in helper,
        "helper_preserves_no_real_change_reason": '"no_real_change"' in helper,
        "helper_preserves_no_real_change_marker": '"no_real_change_rejected": True' in helper,
        "helper_preserves_raw_update_fallback": "dict(norm_u) if norm_u else dict(raw_u)" in helper,
        "no_real_change_helper_delegates_trace": "_trace_candidate_eval_no_real_change_solver_coordinator("
        in no_real_change_helper,
        "solver_delegates_no_real_change_handler": "_handle_one_click_solver_no_real_change_candidate_coordinator("
        in solve_body,
        "solver_delegates_non_governing_cleanup_trace": (
            'rejection_reason="non_governing_cleanup_pruned"' in solve_body
            and "_trace_candidate_eval_pre_eval_rejection_solver_coordinator(" in solve_body
        ),
        "no_real_change_helper_keeps_no_real_change_counter": "rejected_as_no_real_change += 1"
        in no_real_change_helper,
        "no_real_change_helper_keeps_remove_links_drop_reason": (
            'shear_remove_links_candidate_dropped_reason = "no_real_change"' in no_real_change_helper
        ),
        "solver_has_no_direct_candidate_eval_trace": "candidate_eval" not in direct_trace_events,
    }
    runtime = {
        "normalized_update_case": norm_runtime,
        "normalized_update_case_matches": norm_runtime == expected_norm,
        "raw_update_fallback_case": raw_fallback_runtime,
        "raw_update_fallback_case_matches": raw_fallback_runtime == expected_raw,
        "direct_trace_events": direct_trace_events,
    }
    status = "PASS"
    if not all(static_checks.values()) or not all(
        [
            runtime["normalized_update_case_matches"],
            runtime["raw_update_fallback_case_matches"],
        ],
    ):
        status = "FAIL"
    return {
        "status": status,
        "surface": "_solve_one_click_to_target_candidate_eval_no_real_change_trace_coordinator",
        "helper_segment": {
            "function": "_trace_candidate_eval_no_real_change_solver_coordinator",
            "start_line": helper_start,
            "end_line": helper_end,
            "line_count": helper_end - helper_start + 1,
        },
        "no_real_change_handler_segment": {
            "function": "_handle_one_click_solver_no_real_change_candidate_coordinator",
            "start_line": no_real_change_start,
            "end_line": no_real_change_end,
            "line_count": no_real_change_end - no_real_change_start + 1,
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
        "next_safe_slice": "extract iteration_start trace coordinator",
    }


def write_artifacts(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now().isoformat(timespec="seconds").replace(":", "-")
    json_path = ARTIFACT_DIR / f"inputs_page_candidate_eval_no_real_change_trace_coordinator_extraction_{stamp}.json"
    md_path = AUDIT_DIR / f"inputs_page_candidate_eval_no_real_change_trace_coordinator_extraction_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Candidate Eval No-Real-Change Trace Coordinator Extraction",
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
            f"- Normalized update case matches: `{payload['runtime']['normalized_update_case_matches']}`",
            f"- Raw update fallback case matches: `{payload['runtime']['raw_update_fallback_case_matches']}`",
            f"- Direct solver trace events: `{payload['runtime']['direct_trace_events']}`",
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
