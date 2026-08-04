"""Verify auto-design default no-action response coordinator extraction."""

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
    originals = {
        "_trace_run_end_coordinator": getattr(module, "_trace_run_end_coordinator", None),
        "_attach_no_action_visibility_coordinator": getattr(
            module,
            "_attach_no_action_visibility_coordinator",
            None,
        ),
        "_set_one_click_run_feedback": getattr(module, "_set_one_click_run_feedback", None),
        "_result_recommendation_envelope_coordinator": getattr(
            module,
            "_result_recommendation_envelope_coordinator",
            None,
        ),
    }
    traces: list[dict[str, Any]] = []
    visibility: list[dict[str, Any]] = []
    feedback: list[dict[str, Any]] = []
    envelopes: list[dict[str, Any]] = []
    latch_calls: list[dict[str, Any]] = []

    def _latch(reason: str, payload: dict[str, Any]) -> dict[str, Any]:
        latch_calls.append({"reason": reason, "payload": dict(payload)})
        return {"latch_reason": reason, "payload": payload}

    try:
        module._trace_run_end_coordinator = lambda status, **kwargs: traces.append(
            {"status": status, "kwargs": dict(kwargs)},
        )
        module._attach_no_action_visibility_coordinator = lambda **kwargs: (
            visibility.append(dict(kwargs))
            or {
                "user_visible_no_action_reason": "visible default no action",
                "one_click_no_action_reason_code": "default_no_action",
            }
        )
        module._set_one_click_run_feedback = lambda **kwargs: feedback.append(dict(kwargs))
        module._result_recommendation_envelope_coordinator = lambda **kwargs: (
            envelopes.append(dict(kwargs)) or {"envelope": dict(kwargs)}
        )
        dbg = {
            "current_fail_fingerprint": {"crack": "FAIL"},
            "current_fail_keys": ["crack"],
        }
        result = module._return_auto_design_default_no_action_response_coordinator(
            commit_audit={"audit": "yes"},
            init_u=1.2,
            fin_u=1.1,
            commit_rejected=False,
            commit_reject_reason=None,
            commit_blocked_reason="blocked_by_gate",
            dbg=dbg,
            trace_run_id="run-123",
            action_sig=("action",),
            goal={"mode": "unit"},
            stop_reason="solver_stop",
            win_l="Winner",
            win_at="adjust",
            final_updates={},
            trace_src="unit",
            pre_commit_worst_util=1.2,
            base_steps=["step-a"],
            solver_final_updates={"D": 650},
            solve={"solve": "payload"},
            tracer_path="trace.jsonl",
            return_with_latch_clear=_latch,
        )
    finally:
        for name, original in originals.items():
            if original is not None:
                setattr(module, name, original)
    return {
        "result": result,
        "traces": traces,
        "visibility": visibility,
        "feedback": feedback,
        "envelopes": envelopes,
        "latch_calls": latch_calls,
    }


def build_payload() -> dict[str, Any]:
    source = _read(AUTO_DESIGN_COMPUTE)
    helper_start, helper_end, helper = _function_segment(
        source,
        "_return_auto_design_default_no_action_response_coordinator",
    )
    run_start, run_end, run_body = _function_segment(source, "run_one_click_auto_design")
    _, _, dispatch_body = _function_segment(source, "_dispatch_auto_design_final_response_coordinator")
    _, _, terminal_body = _function_segment(
        source,
        "_dispatch_auto_design_terminal_status_response_from_final_response_coordinator",
    )
    _, _, final_tail_body = _function_segment(
        source,
        "_run_one_click_auto_design_solver_and_final_response_coordinator",
    )
    import inputs_page_modules.auto_design_compute as module  # noqa: E402

    runtime = _run_case(module)
    payload = runtime["result"]["payload"]
    feedback = runtime["feedback"][0]
    envelope = runtime["envelopes"][0]
    runtime_checks = {
        "trace_run_end_preserved": runtime["traces"][0]["status"] == "no_action"
        and runtime["traces"][0]["kwargs"]["commit_audit"] == {"audit": "yes"}
        and runtime["traces"][0]["kwargs"]["commit_rejected"] is False
        and runtime["traces"][0]["kwargs"]["stop_reason"] == "solver_stop"
        and runtime["traces"][0]["kwargs"]["trace_run_id"] == "run-123",
        "visibility_call_preserved": runtime["visibility"] == [
            {
                "stop_reason": "solver_stop",
                "dbg": {
                    "current_fail_fingerprint": {"crack": "FAIL"},
                    "current_fail_keys": ["crack"],
                },
            },
        ],
        "feedback_payload_preserved": feedback["status"] == "blocked"
        and feedback["reason"] == "blocked_by_gate"
        and feedback["winning_label"] == "Winner"
        and feedback["winning_action_type"] == "adjust"
        and feedback["pre_commit_worst_util"] == 1.2
        and feedback["extra_payload"] == {
            "current_fail_fingerprint": {"crack": "FAIL"},
            "current_fail_keys": ["crack"],
            "current_fail_keys_source": "canonical_overview",
        },
        "recommendation_envelope_preserved": envelope["status"] == "no_action"
        and envelope["commit_audit"] == {"audit": "yes"}
        and envelope["updates"] == {"D": 650}
        and envelope["blocked_reason"] == "blocked_by_gate"
        and envelope["commit_eligible"] is False,
        "latch_reason_preserved": runtime["result"]["latch_reason"] == "run_one_click_auto_design:no_action",
        "returned_payload_shape_preserved": payload["status"] == "no_action"
        and payload["stop_reason"] == "solver_stop"
        and payload["steps"] == ["step-a"]
        and payload["recommendation"] is None
        and payload["recommendation_result"] is None
        and payload["auto_design_solver_recommendation"] is None
        and payload["one_click_solve"] == {"solve": "payload"}
        and payload["one_click_commit_audit"] == {"audit": "yes"}
        and payload["trace_run_id"] == "run-123"
        and payload["design_guide_tracer_path"] == "trace.jsonl"
        and payload["tracer_skip_reason"] is None
        and payload["tracer_entry_reached"] is True
        and payload["user_visible_no_action_reason"] == "visible default no action"
        and payload["one_click_no_action_reason_code"] == "default_no_action",
    }
    static_checks = {
        "helper_present": "def _return_auto_design_default_no_action_response_coordinator(" in source,
        "helper_preserves_latch_reason": "run_one_click_auto_design:no_action" in helper,
        "helper_preserves_reason_precedence": "commit_reject_reason or commit_blocked_reason or stop_reason" in helper,
        "helper_preserves_trace": "_trace_run_end_coordinator(" in helper,
        "helper_preserves_visibility": "_attach_no_action_visibility_coordinator(" in helper,
        "helper_preserves_feedback": "_set_one_click_run_feedback(" in helper,
        "helper_preserves_envelope": "_result_recommendation_envelope_coordinator(" in helper,
        "dispatch_delegates_default_no_action_response": "_return_auto_design_default_no_action_response_coordinator("
        in terminal_body
        and "_dispatch_auto_design_terminal_status_response_from_final_response_coordinator(" in dispatch_body,
        "run_delegates_final_tail": "_run_one_click_auto_design_solver_and_final_response_coordinator(" in run_body
        and "_finish_auto_design_post_current_eval_and_dispatch_coordinator(" in final_tail_body,
        "dispatch_response_branches_are_delegated": "_return_auto_design_ready_response_coordinator(" in terminal_body
        and "_return_auto_design_already_in_band_response_coordinator(" in terminal_body,
    }
    status = "PASS"
    if not all(static_checks.values()) or not all(runtime_checks.values()):
        status = "FAIL"
    return {
        "status": status,
        "surface": "run_one_click_auto_design_default_no_action_response_coordinator",
        "helper_segment": {
            "function": "_return_auto_design_default_no_action_response_coordinator",
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
        "next_safe_slice": "audit remaining run_one_click_auto_design orchestration-only surface",
    }


def write_artifacts(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now().isoformat(timespec="seconds").replace(":", "-")
    json_path = ARTIFACT_DIR / f"inputs_page_auto_design_default_no_action_response_coordinator_extraction_{stamp}.json"
    md_path = AUDIT_DIR / f"inputs_page_auto_design_default_no_action_response_coordinator_extraction_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Auto Design Default No-Action Response Coordinator Extraction",
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
