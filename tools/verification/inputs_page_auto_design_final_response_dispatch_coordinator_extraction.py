"""Verify auto-design final response dispatch coordinator extraction."""

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


BRANCH_HELPERS = {
    "commit_rejected": "_return_auto_design_commit_rejected_response_coordinator",
    "commit_blocked": "_return_auto_design_commit_blocked_response_coordinator",
    "blocked_status": "_return_auto_design_blocked_status_response_coordinator",
    "failed_no_action": "_return_auto_design_failed_no_action_response_coordinator",
    "already_in_band": "_return_auto_design_already_in_band_response_coordinator",
    "ready": "_return_auto_design_ready_response_coordinator",
    "default_no_action": "_return_auto_design_default_no_action_response_coordinator",
}


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _function_segment(source: str, name: str) -> tuple[int, int, str]:
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            start = int(node.lineno)
            end = int(getattr(node, "end_lineno", node.lineno))
            lines = source.splitlines()
            return start, end, "\n".join(lines[start - 1 : end])
    raise AssertionError(f"Function not found: {name}")


def _base_kwargs(**overrides: Any) -> dict[str, Any]:
    kwargs = {
        "commit_audit": {"audit": "yes"},
        "init_u": 1.3,
        "fin_u": 0.97,
        "commit_rejected": False,
        "commit_reject_reason": None,
        "commit_blocked_reason": None,
        "dbg": {"debug": "yes"},
        "trace_run_id": "run-123",
        "action_sig": ("action",),
        "goal": {"mode": "unit"},
        "stop_reason": "solver_stop",
        "win_l": "Winner",
        "win_at": "adjust",
        "final_updates": {},
        "trace_src": "unit",
        "pre_commit_worst_util": 1.2,
        "base_steps": ["step-a"],
        "solver_final_updates": {"D": 650},
        "solve": {"status": "exhausted", "solve": "payload"},
        "solver_stop_reason": "solver_original",
        "tracer_path": "trace.jsonl",
        "return_with_latch_clear": lambda reason, payload: {"reason": reason, "payload": payload},
    }
    kwargs.update(overrides)
    return kwargs


def _run_case(module: Any, case: dict[str, Any]) -> dict[str, Any]:
    originals = {helper: getattr(module, helper, None) for helper in BRANCH_HELPERS.values()}
    calls: list[dict[str, Any]] = []

    def _stub(branch: str):
        def _inner(**kwargs: Any) -> dict[str, Any]:
            captured = dict(kwargs)
            if captured.get("return_with_latch_clear") is not None:
                captured["return_with_latch_clear"] = "<callable>"
            calls.append({"branch": branch, "kwargs": captured})
            return {"branch": branch, "kwargs": captured}

        return _inner

    try:
        for branch, helper in BRANCH_HELPERS.items():
            setattr(module, helper, _stub(branch))
        result = module._dispatch_auto_design_final_response_coordinator(**_base_kwargs(**case["overrides"]))
    finally:
        for helper, original in originals.items():
            if original is not None:
                setattr(module, helper, original)
    return {"case": case["name"], "result": result, "calls": calls}


def build_payload() -> dict[str, Any]:
    source = _read(AUTO_DESIGN_COMPUTE)
    helper_start, helper_end, helper = _function_segment(source, "_dispatch_auto_design_final_response_coordinator")
    _, _, commit_rejected_dispatch = _function_segment(
        source,
        "_dispatch_auto_design_commit_rejected_response_from_final_response_coordinator",
    )
    _, _, commit_blocked_dispatch = _function_segment(
        source,
        "_dispatch_auto_design_commit_blocked_response_from_final_response_coordinator",
    )
    _, _, blocked_status_dispatch = _function_segment(
        source,
        "_dispatch_auto_design_blocked_status_response_from_final_response_coordinator",
    )
    tail_start, tail_end, tail = _function_segment(
        source,
        "_finish_auto_design_post_current_eval_and_dispatch_coordinator",
    )
    run_start, run_end, run_body = _function_segment(source, "run_one_click_auto_design")
    import inputs_page_modules.auto_design_compute as module  # noqa: E402

    cases = [
        {
            "name": "commit_rejected_precedes_all",
            "expected": "commit_rejected",
            "overrides": {
                "commit_rejected": True,
                "commit_reject_reason": "audit_failed",
                "commit_blocked_reason": "blocked_too",
                "solve": {"status": "blocked"},
                "final_updates": {"D": 650},
            },
        },
        {
            "name": "commit_blocked_precedes_status",
            "expected": "commit_blocked",
            "overrides": {
                "commit_blocked_reason": "partial_failure_coverage",
                "solve": {"status": "blocked"},
                "final_updates": {"D": 650},
            },
        },
        {
            "name": "blocked_status",
            "expected": "blocked_status",
            "overrides": {"solve": {"status": "blocked"}},
        },
        {
            "name": "failed_no_action",
            "expected": "failed_no_action",
            "overrides": {"solve": {"status": "failed"}},
        },
        {
            "name": "already_in_band_precedes_ready",
            "expected": "already_in_band",
            "overrides": {
                "solve": {"status": "no_action"},
                "stop_reason": "already_in_band",
                "final_updates": {"D": 650},
            },
        },
        {
            "name": "ready",
            "expected": "ready",
            "overrides": {"final_updates": {"D": 650}},
        },
        {
            "name": "default_no_action",
            "expected": "default_no_action",
            "overrides": {"solve": {"status": "exhausted"}},
        },
    ]
    runtime = [_run_case(module, case) for case in cases]
    runtime_checks = {
        "one_branch_per_case": all(len(item["calls"]) == 1 for item in runtime),
        "branch_order_preserved": all(
            item["calls"][0]["branch"] == case["expected"]
            for item, case in zip(runtime, cases, strict=True)
        ),
        "commit_audit_normalized_for_branch": all(
            item["calls"][0]["kwargs"].get("commit_audit") == {"audit": "yes"}
            for item in runtime
        ),
        "common_payload_passthrough_preserved": all(
            item["calls"][0]["kwargs"].get("trace_run_id") == "run-123"
            and item["calls"][0]["kwargs"].get("dbg") == {"debug": "yes"}
            and item["calls"][0]["kwargs"].get("base_steps") == ["step-a"]
            and item["calls"][0]["kwargs"].get("return_with_latch_clear") is not None
            for item in runtime
        ),
        "solver_stop_reason_reaches_expected_branches": runtime[0]["calls"][0]["kwargs"].get("solver_stop_reason")
        == "solver_original"
        and runtime[1]["calls"][0]["kwargs"].get("solver_stop_reason") == "solver_original",
    }
    static_checks = {
        "helper_present": "def _dispatch_auto_design_final_response_coordinator(" in source,
        "helper_preserves_branch_order": helper.find("if commit_rejected:") < helper.find("if commit_blocked_reason:")
        < helper.find('if out_status == "blocked":')
        < helper.find('if out_status == "failed":')
        < helper.find('if out_status == "no_action" and stop_reason == "already_in_band":')
        < helper.find("if final_updates:")
        < helper.find("_return_auto_design_default_no_action_response_coordinator("),
        "helper_delegates_all_response_helpers": all(
            token in helper
            for branch, token in BRANCH_HELPERS.items()
            if branch not in {"commit_rejected", "commit_blocked", "blocked_status"}
        )
        and "_dispatch_auto_design_commit_rejected_response_from_final_response_coordinator(" in helper
        and "_return_auto_design_commit_rejected_response_coordinator(" in commit_rejected_dispatch
        and "_dispatch_auto_design_commit_blocked_response_from_final_response_coordinator(" in helper
        and "_return_auto_design_commit_blocked_response_coordinator(" in commit_blocked_dispatch
        and "_dispatch_auto_design_blocked_status_response_from_final_response_coordinator(" in helper
        and "_return_auto_design_blocked_status_response_coordinator(" in blocked_status_dispatch,
        "tail_delegates_final_response_dispatch": "_dispatch_auto_design_final_response_coordinator(" in tail,
        "run_delegates_final_tail": (
            "_finish_auto_design_post_current_eval_and_dispatch_coordinator(" in run_body
        ),
        "run_no_longer_delegates_final_response_dispatch_directly": (
            "_dispatch_auto_design_final_response_coordinator(" not in run_body
        ),
        "run_no_longer_owns_response_branch_ladder": "if commit_rejected:" not in run_body
        and 'out_status = str(solve.get("status") or "exhausted")' not in run_body
        and "_return_auto_design_default_no_action_response_coordinator(" not in run_body,
    }
    status = "PASS"
    if not all(static_checks.values()) or not all(runtime_checks.values()):
        status = "FAIL"
    return {
        "status": status,
        "surface": "run_one_click_auto_design_final_response_dispatch_coordinator",
        "helper_segment": {
            "function": "_dispatch_auto_design_final_response_coordinator",
            "start_line": helper_start,
            "end_line": helper_end,
            "line_count": helper_end - helper_start + 1,
        },
        "tail_segment": {
            "function": "_finish_auto_design_post_current_eval_and_dispatch_coordinator",
            "start_line": tail_start,
            "end_line": tail_end,
            "line_count": tail_end - tail_start + 1,
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
        "next_safe_slice": "audit remaining run_one_click_auto_design orchestration block or begin solver decomposition",
    }


def write_artifacts(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now().isoformat(timespec="seconds").replace(":", "-")
    json_path = ARTIFACT_DIR / f"inputs_page_auto_design_final_response_dispatch_coordinator_extraction_{stamp}.json"
    md_path = AUDIT_DIR / f"inputs_page_auto_design_final_response_dispatch_coordinator_extraction_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Auto Design Final Response Dispatch Coordinator Extraction",
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
