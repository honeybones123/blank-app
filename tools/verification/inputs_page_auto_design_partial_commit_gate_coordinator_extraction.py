"""Verify auto-design partial-commit gate coordinator extraction."""

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


def _run_case(module: Any, *, case: str) -> dict[str, Any]:
    originals = {
        "_requires_full_coverage_for_primary_one_click": getattr(
            module,
            "_requires_full_coverage_for_primary_one_click",
            None,
        ),
        "evaluate_candidate_full": getattr(module, "evaluate_candidate_full", None),
        "_guidance_state_snapshot": getattr(module, "_guidance_state_snapshot", None),
        "is_valid_progress_while_failing": getattr(module, "is_valid_progress_while_failing", None),
        "_rescue_bootstrap_partial_commit_allowed": getattr(
            module,
            "_rescue_bootstrap_partial_commit_allowed",
            None,
        ),
        "_append_design_guide_trace": getattr(module, "_append_design_guide_trace", None),
    }
    eval_sources: list[str] = []
    traces: list[dict[str, Any]] = []
    current_state = {"D": 600}
    final_updates = {"D": 650}
    candidate_for_commit = {"candidate": case}
    current_overview = {"statuses": {"bending": "FAIL", "shear": "FAIL"}}
    meta = {
        "reason": "partial_failure_coverage",
        "fail_keys": ["bending", "shear"],
        "covered_fail_keys": ["bending"],
        "remaining_fail_keys": ["shear"],
    }
    valid = False
    solve = {"stop_reason": "iterating"}

    if case == "valid":
        valid = True
        meta["reason"] = "accepted"
    elif case == "best_effort":
        solve["stop_reason"] = "best_available_out_of_band_candidate"
        meta["reason"] = "candidate_preview_has_fail_status"
    elif case == "blocked":
        meta["reason"] = "candidate_preview_has_fail_status"
    elif case == "rescue":
        meta["reason"] = "candidate_preview_has_fail_status"

    def _requires(_: dict[str, Any]) -> tuple[bool, list[str]]:
        if case == "best_effort":
            return False, ["bending"]
        return True, ["bending", "shear"]

    def _evaluate(_: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
        eval_sources.append(str(kwargs.get("source") or ""))
        return {"seed": True, "source": kwargs.get("source")}

    def _progress(candidate: dict[str, Any], seed: dict[str, Any]) -> bool:
        if case in {"partial", "best_effort"}:
            return True
        return False

    def _rescue(**_: Any) -> bool:
        return case == "rescue"

    def _trace(event: str, data: dict[str, Any], **kwargs: Any) -> None:
        traces.append({"event": event, "data": dict(data), "kwargs": dict(kwargs)})

    try:
        module._requires_full_coverage_for_primary_one_click = _requires
        module.evaluate_candidate_full = _evaluate
        module._guidance_state_snapshot = lambda state: {"snapshot": dict(state)}
        module.is_valid_progress_while_failing = _progress
        module._rescue_bootstrap_partial_commit_allowed = _rescue
        module._append_design_guide_trace = _trace
        result = module._resolve_auto_design_partial_commit_gate_coordinator(
            solve=solve,
            current_state=current_state,
            current_overview=current_overview,
            candidate_for_commit=candidate_for_commit,
            final_candidate_valid_for_commit=valid,
            final_candidate_commit_meta=meta,
            solver_final_updates={"D": 650},
            final_updates=final_updates,
            dbg={"seed": "kept"},
            win_l="Winner",
            win_at="adjust",
            trace_run_id="run-123",
            trace_src="unit",
        )
    finally:
        for name, original in originals.items():
            if original is not None:
                setattr(module, name, original)

    return {
        "result": result,
        "eval_sources": eval_sources,
        "traces": traces,
    }


def build_payload() -> dict[str, Any]:
    source = _read(AUTO_DESIGN_COMPUTE)
    helper_start, helper_end, helper = _function_segment(
        source,
        "_resolve_auto_design_partial_commit_gate_coordinator",
    )
    orchestration_start, orchestration_end, orchestration_body = _function_segment(
        source,
        "_resolve_auto_design_final_candidate_partial_commit_orchestration_coordinator",
    )
    run_start, run_end, run_body = _function_segment(source, "run_one_click_auto_design")
    _, _, post_solver_commit_body = _function_segment(
        source,
        "_run_auto_design_post_solver_commit_orchestration_coordinator",
    )
    _, _, commit_body = _function_segment(
        source,
        "_run_auto_design_commit_orchestration_coordinator",
    )
    import inputs_page_modules.auto_design_compute as module  # noqa: E402

    cases = {
        name: _run_case(module, case=name)
        for name in ("valid", "partial", "best_effort", "rescue", "blocked")
    }
    valid_result = cases["valid"]["result"]
    partial_result = cases["partial"]["result"]
    best_effort_result = cases["best_effort"]["result"]
    rescue_result = cases["rescue"]["result"]
    blocked_result = cases["blocked"]["result"]
    runtime_checks = {
        "valid_candidate_leaves_updates_unblocked": valid_result["final_updates"] == {"D": 650}
        and valid_result["commit_blocked_reason"] is None
        and valid_result["dbg"].get("one_click_commit_blocked_reason") is None
        and valid_result["final_candidate_valid_for_commit"] is True
        and not cases["valid"]["traces"],
        "partial_combined_gate_allows_commit": partial_result["final_updates"] == {"D": 650}
        and partial_result["final_candidate_valid_for_commit"] is True
        and partial_result["dbg"].get("one_click_partial_progress_commit") is True
        and cases["partial"]["traces"][0]["event"] == "commit_allowed_partial_combined_fail"
        and cases["partial"]["eval_sources"] == ["one_click_partial_commit_combined_gate_seed"],
        "best_effort_gate_allows_commit": best_effort_result["final_updates"] == {"D": 650}
        and best_effort_result["dbg"].get("one_click_best_effort_cleanup_commit") is True
        and cases["best_effort"]["traces"][0]["event"] == "commit_allowed_best_effort_cleanup"
        and cases["best_effort"]["eval_sources"] == ["one_click_best_effort_cleanup_gate_seed"],
        "rescue_bootstrap_allows_commit": rescue_result["final_updates"] == {"D": 650}
        and rescue_result["dbg"].get("one_click_rescue_bootstrap_commit") is True
        and cases["rescue"]["traces"][0]["event"] == "commit_allowed_best_effort_cleanup"
        and cases["rescue"]["eval_sources"] == ["one_click_rescue_bootstrap_gate_seed"],
        "blocked_path_clears_updates_and_traces_reason": blocked_result["final_updates"] == {}
        and blocked_result["commit_blocked_reason"] == "candidate_preview_has_fail_status"
        and blocked_result["dbg"].get("one_click_commit_blocked_reason") == "candidate_preview_has_fail_status"
        and cases["blocked"]["traces"][0]["event"] == "commit_blocked",
        "seed_debug_preserved": all(case["result"]["dbg"].get("seed") == "kept" for case in cases.values()),
    }
    static_checks = {
        "helper_present": "def _resolve_auto_design_partial_commit_gate_coordinator(" in source,
        "helper_preserves_partial_combined_trace": "commit_allowed_partial_combined_fail" in helper,
        "helper_preserves_best_effort_trace": "commit_allowed_best_effort_cleanup" in helper,
        "helper_preserves_blocked_trace": '"commit_blocked"' in helper,
        "helper_preserves_rescue_gate": "_rescue_bootstrap_partial_commit_allowed(" in helper,
        "helper_returns_gate_state": '"commit_blocked_reason": commit_blocked_reason' in helper
        and '"final_updates": final_updates' in helper,
        "commit_orchestration_delegates_final_candidate_partial_gate": (
            "_resolve_auto_design_final_candidate_partial_commit_orchestration_coordinator("
            in commit_body
        ),
        "final_candidate_partial_gate_delegates_partial_commit_gate": (
            "_resolve_auto_design_partial_commit_gate_coordinator(" in orchestration_body
        ),
        "run_no_longer_owns_gate_seed_evaluations": "one_click_partial_commit_combined_gate_seed" not in run_body
        and "one_click_best_effort_cleanup_gate_seed" not in run_body
        and "one_click_rescue_bootstrap_gate_seed" not in run_body,
        "commit_orchestration_owns_commit_path": "_prepare_auto_design_commit_start_coordinator("
        in commit_body
        and "_apply_auto_design_commit_write_audit_setup_coordinator(" in commit_body,
        "post_solver_commit_delegates_commit_orchestration": "_run_auto_design_commit_orchestration_coordinator("
        in post_solver_commit_body,
        "run_delegates_post_solver_commit_orchestration": "_run_auto_design_post_solver_commit_orchestration_coordinator("
        in run_body,
    }
    status = "PASS"
    if not all(static_checks.values()) or not all(runtime_checks.values()):
        status = "FAIL"
    return {
        "status": status,
        "surface": "run_one_click_auto_design_partial_commit_gate_coordinator",
        "helper_segment": {
            "function": "_resolve_auto_design_partial_commit_gate_coordinator",
            "start_line": helper_start,
            "end_line": helper_end,
            "line_count": helper_end - helper_start + 1,
        },
        "orchestration_segment": {
            "function": "_resolve_auto_design_final_candidate_partial_commit_orchestration_coordinator",
            "start_line": orchestration_start,
            "end_line": orchestration_end,
            "line_count": orchestration_end - orchestration_start + 1,
        },
        "run_segment": {
            "function": "run_one_click_auto_design",
            "start_line": run_start,
            "end_line": run_end,
            "line_count": run_end - run_start + 1,
        },
        "static_checks": static_checks,
        "runtime_checks": runtime_checks,
        "cases": cases,
        "product_behavior_changed": False,
        "next_safe_slice": "extract sanitized commit preparation block from run_one_click_auto_design",
    }


def write_artifacts(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now().isoformat(timespec="seconds").replace(":", "-")
    json_path = ARTIFACT_DIR / f"inputs_page_auto_design_partial_commit_gate_coordinator_extraction_{stamp}.json"
    md_path = AUDIT_DIR / f"inputs_page_auto_design_partial_commit_gate_coordinator_extraction_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Auto Design Partial-Commit Gate Coordinator Extraction",
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
