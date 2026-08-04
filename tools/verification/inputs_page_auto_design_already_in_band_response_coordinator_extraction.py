"""Verify auto-design already-in-band response coordinator extraction."""

from __future__ import annotations

import ast
import datetime as _dt
import json
import sys
from pathlib import Path
from types import SimpleNamespace
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
        "st": getattr(module, "st", None),
        "_trace_run_end_coordinator": getattr(module, "_trace_run_end_coordinator", None),
        "_result_recommendation_envelope_coordinator": getattr(
            module,
            "_result_recommendation_envelope_coordinator",
            None,
        ),
    }
    traces: list[dict[str, Any]] = []
    envelopes: list[dict[str, Any]] = []
    latch_calls: list[dict[str, Any]] = []
    session_state = {"_one_click_run_feedback": {"old": True}, "keep": "yes"}

    def _latch(reason: str, payload: dict[str, Any]) -> dict[str, Any]:
        latch_calls.append({"reason": reason, "payload": dict(payload)})
        return {"latch_reason": reason, "payload": payload}

    try:
        module.st = SimpleNamespace(session_state=session_state)
        module._trace_run_end_coordinator = lambda status, **kwargs: traces.append(
            {"status": status, "kwargs": dict(kwargs)},
        )
        module._result_recommendation_envelope_coordinator = lambda **kwargs: (
            envelopes.append(dict(kwargs)) or {"envelope": dict(kwargs)}
        )
        dbg = {"current_fail_fingerprint": {}, "current_fail_keys": []}
        result = module._return_auto_design_already_in_band_response_coordinator(
            commit_audit={"audit": "yes"},
            init_u=0.82,
            fin_u=0.82,
            commit_rejected=False,
            commit_reject_reason=None,
            dbg=dbg,
            trace_run_id="run-123",
            action_sig=("action",),
            goal={"mode": "unit"},
            stop_reason="already_in_band",
            win_l=None,
            final_updates={},
            trace_src="unit",
            base_steps=["step-a"],
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
        "envelopes": envelopes,
        "latch_calls": latch_calls,
        "session_state": dict(session_state),
    }


def build_payload() -> dict[str, Any]:
    source = _read(AUTO_DESIGN_COMPUTE)
    helper_start, helper_end, helper = _function_segment(
        source,
        "_return_auto_design_already_in_band_response_coordinator",
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
    envelope = runtime["envelopes"][0]
    runtime_checks = {
        "trace_run_end_preserved": runtime["traces"][0]["status"] == "pass"
        and runtime["traces"][0]["kwargs"]["commit_audit"] == {"audit": "yes"}
        and runtime["traces"][0]["kwargs"]["commit_rejected"] is False
        and runtime["traces"][0]["kwargs"]["stop_reason"] == "already_in_band"
        and runtime["traces"][0]["kwargs"]["trace_run_id"] == "run-123",
        "feedback_clear_preserved": "_one_click_run_feedback" not in runtime["session_state"]
        and runtime["session_state"].get("keep") == "yes",
        "recommendation_envelope_preserved": envelope["status"] == "no_action"
        and envelope["commit_audit"] == {"audit": "yes"}
        and envelope["updates"] == {}
        and envelope["blocked_reason"] == "already_in_band"
        and envelope["commit_eligible"] is False,
        "latch_reason_preserved": runtime["result"]["latch_reason"] == "run_one_click_auto_design:already_in_band",
        "returned_payload_shape_preserved": payload["status"] == "pass"
        and payload["stop_reason"] == "already_in_band"
        and payload["steps"] == ["step-a"]
        and payload["recommendation"] is None
        and payload["recommendation_result"] is None
        and payload["auto_design_solver_recommendation"] is None
        and payload["one_click_solve"] == {"solve": "payload"}
        and payload["one_click_commit_audit"] == {"audit": "yes"}
        and payload["trace_run_id"] == "run-123"
        and payload["design_guide_tracer_path"] == "trace.jsonl"
        and payload["tracer_skip_reason"] is None
        and payload["tracer_entry_reached"] is True,
    }
    static_checks = {
        "helper_present": "def _return_auto_design_already_in_band_response_coordinator(" in source,
        "helper_preserves_latch_reason": "run_one_click_auto_design:already_in_band" in helper,
        "helper_preserves_trace": "_trace_run_end_coordinator(" in helper,
        "helper_preserves_feedback_clear": "st.session_state.pop(\"_one_click_run_feedback\", None)" in helper,
        "helper_preserves_envelope": "_result_recommendation_envelope_coordinator(" in helper,
        "dispatch_delegates_already_in_band_response": "_return_auto_design_already_in_band_response_coordinator("
        in terminal_body
        and "_dispatch_auto_design_terminal_status_response_from_final_response_coordinator(" in dispatch_body,
        "run_delegates_final_tail": "_run_one_click_auto_design_solver_and_final_response_coordinator(" in run_body
        and "_finish_auto_design_post_current_eval_and_dispatch_coordinator(" in final_tail_body,
        "dispatch_preserves_other_return_branches": "if final_updates:" in terminal_body
        and "_return_auto_design_ready_response_coordinator(" in terminal_body
        and "_return_auto_design_default_no_action_response_coordinator(" in terminal_body,
    }
    status = "PASS"
    if not all(static_checks.values()) or not all(runtime_checks.values()):
        status = "FAIL"
    return {
        "status": status,
        "surface": "run_one_click_auto_design_already_in_band_response_coordinator",
        "helper_segment": {
            "function": "_return_auto_design_already_in_band_response_coordinator",
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
        "next_safe_slice": "extract ready final return branch from run_one_click_auto_design",
    }


def write_artifacts(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now().isoformat(timespec="seconds").replace(":", "-")
    json_path = ARTIFACT_DIR / f"inputs_page_auto_design_already_in_band_response_coordinator_extraction_{stamp}.json"
    md_path = AUDIT_DIR / f"inputs_page_auto_design_already_in_band_response_coordinator_extraction_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Auto Design Already-In-Band Response Coordinator Extraction",
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
