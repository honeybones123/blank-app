"""Verify auto-design blocked incoherent-state coordinator extraction."""

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
    def __init__(self) -> None:
        self.session_state: dict[str, Any] = {"auto_design_latch_owner": "owner-a"}


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
        "BEAM_STATUS_FAIL": getattr(module, "BEAM_STATUS_FAIL", None),
        "_append_design_guide_trace": getattr(module, "_append_design_guide_trace", None),
        "_coherence_debug_fields": getattr(module, "_coherence_debug_fields", None),
        "_one_click_build_user_visible_no_action_fields": getattr(
            module,
            "_one_click_build_user_visible_no_action_fields",
            None,
        ),
        "_publish_current_normalized_shear_truth_coordinator": getattr(
            module,
            "_publish_current_normalized_shear_truth_coordinator",
            None,
        ),
        "_attach_normalized_shear_truth_debug_coordinator": getattr(
            module,
            "_attach_normalized_shear_truth_debug_coordinator",
            None,
        ),
        "_collect_design_overview": getattr(module, "_collect_design_overview", None),
        "_current_design_guide_fail_fingerprint": getattr(module, "_current_design_guide_fail_fingerprint", None),
        "_set_one_click_run_feedback": getattr(module, "_set_one_click_run_feedback", None),
    }
    traces: list[dict[str, Any]] = []
    published: list[dict[str, Any]] = []
    attached: list[dict[str, Any]] = []
    feedbacks: list[dict[str, Any]] = []
    latch_calls: list[dict[str, Any]] = []

    current_state = {
        "canonical_pack_built": True,
        "canonical_pack_source": "unit",
    }
    raw_coherence = {
        "coherence_ok": False,
        "issues": ["raw-issue"],
        "coherence_blocking_issues": ["raw-block"],
        "coherence_nonblocking_issues": ["raw-note"],
        "coherence_should_block": True,
        "state_coherence_warning": True,
        "state_coherence_warning_issues": ["raw-warning"],
    }
    canonical_coherence = {
        "coherence_ok": False,
        "coherence_blocking_issues": ["no_bars_resolved"],
    }

    def _append(event: str, data: dict[str, Any], *, run_id: str, source: str) -> None:
        traces.append({"event": event, "data": dict(data), "run_id": run_id, "source": source})

    def _publish(source: str, target: dict[str, Any] | None = None) -> dict[str, Any]:
        published.append({"source": source, "target": dict(target or {})})
        return {"normalized": True}

    def _attach(target: dict[str, Any] | None, normalized: dict[str, Any] | None) -> None:
        attached.append({"target": dict(target or {}), "normalized": dict(normalized or {})})
        if isinstance(target, dict):
            target["attached_truth"] = bool(normalized)

    def _feedback(**kwargs: Any) -> None:
        feedbacks.append(dict(kwargs))

    def _return_with_latch_clear(reason: str, payload: dict[str, Any]) -> dict[str, Any]:
        latch_calls.append({"reason": reason, "status": payload.get("status")})
        returned = dict(payload)
        returned["auto_design_latch_clear"] = {"reason": reason}
        return returned

    try:
        module.st = _FakeStreamlit()
        module.BEAM_STATUS_FAIL = "FAIL"
        module._append_design_guide_trace = _append
        module._coherence_debug_fields = lambda coherence: {
            "state_coherence_ok": bool(coherence.get("coherence_ok")),
        }
        module._one_click_build_user_visible_no_action_fields = lambda reason, debug: {
            "user_visible_no_action_reason": f"visible:{reason}",
            "user_visible_rejection_summary": "summary",
        }
        module._publish_current_normalized_shear_truth_coordinator = _publish
        module._attach_normalized_shear_truth_debug_coordinator = _attach
        module._collect_design_overview = lambda state: {
            "statuses": {"bending": "FAIL", "shear": "PASS"},
        }
        module._current_design_guide_fail_fingerprint = lambda overview: {"bending": "FAIL"}
        module._set_one_click_run_feedback = _feedback
        returned = module._handle_auto_design_blocked_incoherent_state_coordinator(
            current_state=current_state,
            raw_coherence=raw_coherence,
            canonical_coherence=canonical_coherence,
            canonical_pack_valid=False,
            canonical_pack_error=None,
            canonical_pack_error_stage=None,
            trace_run_id="trace-123",
            tracer_path="trace.jsonl",
            trace_src="run_one_click_auto_design",
            entry_source_norm="inputs_handle_auto_design",
            solver_running_bypassed=True,
            one_click_run_feedback_cleared_at_entry=True,
            return_with_latch_clear=_return_with_latch_clear,
        )
    finally:
        for name, original in originals.items():
            if original is not None:
                setattr(module, name, original)

    trace_data = dict(traces[0]["data"] or {}) if traces else {}
    debug = dict(returned.get("one_click_solver_debug") or {})
    inner_debug = dict((returned.get("one_click_solve") or {}).get("one_click_solver_debug") or {})
    return {
        "returned": returned,
        "traces": traces,
        "published": published,
        "attached": attached,
        "feedbacks": feedbacks,
        "latch_calls": latch_calls,
        "checks": {
            "returned_blocked": returned.get("status") == "blocked"
            and returned.get("stop_reason") == "no_bars_resolved"
            and returned.get("blocked_state_class") == "hard_invalid",
            "trace_run_end": bool(traces)
            and traces[0]["event"] == "run_end"
            and trace_data.get("overall_result_status") == "blocked"
            and trace_data.get("solver_blocked_by_incoherent_state") is True,
            "latch_clear_reason": latch_calls == [
                {
                    "reason": "run_one_click_auto_design:blocked_incoherent_state",
                    "status": "blocked",
                }
            ],
            "feedback_set": bool(feedbacks)
            and feedbacks[0].get("status") == "blocked"
            and feedbacks[0].get("reason") == "no_bars_resolved",
            "normalized_truth_attached": bool(published)
            and published[0]["source"] == "run_one_click_auto_design:post_current_eval:blocked"
            and bool(attached),
            "fail_keys_collected": debug.get("current_fail_keys") == ["bending"]
            and debug.get("current_fail_fingerprint") == {"bending": "FAIL"},
            "uv_fields_propagated": returned.get("user_visible_no_action_reason")
            == "Add longitudinal reinforcement before running auto-design."
            and inner_debug.get("user_visible_rejection_summary") == "summary",
        },
    }


def build_payload() -> dict[str, Any]:
    source = _read(AUTO_DESIGN_COMPUTE)
    helper_start, helper_end, helper = _function_segment(
        source,
        "_handle_auto_design_blocked_incoherent_state_coordinator",
    )
    _, _, user_visible_helper = _function_segment(
        source,
        "_apply_auto_design_blocked_incoherent_user_visible_fields_coordinator",
    )
    _, _, final_tail = _function_segment(
        source,
        "_run_one_click_auto_design_solver_and_final_response_coordinator",
    )
    run_start, run_end, run_body = _function_segment(source, "run_one_click_auto_design")
    import inputs_page_modules.auto_design_compute as module  # noqa: E402

    runtime = _run_case(module)
    static_checks = {
        "helper_present": "def _handle_auto_design_blocked_incoherent_state_coordinator(" in source,
        "helper_emits_run_end": '"run_end"' in helper,
        "helper_sets_blocked_feedback": "_set_one_click_run_feedback(" in helper,
        "helper_uses_latch_return": 'return_with_latch_clear("run_one_click_auto_design:blocked_incoherent_state"' in helper,
        "helper_preserves_no_bars_message": "Add longitudinal reinforcement before running auto-design."
        in user_visible_helper,
        "helper_publishes_normalized_truth": "_publish_current_normalized_shear_truth_coordinator(" in helper,
        "run_delegates_blocked_path": "_handle_auto_design_blocked_incoherent_state_coordinator(" in run_body,
        "run_keeps_solver_after_blocked_path": "_run_one_click_auto_design_solver_and_final_response_coordinator("
        in run_body
        and "_solve_one_click_to_target(" in final_tail,
    }
    status = "PASS"
    if not all(static_checks.values()) or not all(runtime["checks"].values()):
        status = "FAIL"
    return {
        "status": status,
        "surface": "run_one_click_auto_design_blocked_incoherent_state_coordinator",
        "helper_segment": {
            "function": "_handle_auto_design_blocked_incoherent_state_coordinator",
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
        "runtime": runtime,
        "product_behavior_changed": False,
        "next_safe_slice": "extract post-solver debug coherence enrichment from run_one_click_auto_design",
    }


def write_artifacts(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now().isoformat(timespec="seconds").replace(":", "-")
    json_path = ARTIFACT_DIR / f"inputs_page_auto_design_blocked_incoherent_state_coordinator_extraction_{stamp}.json"
    md_path = AUDIT_DIR / f"inputs_page_auto_design_blocked_incoherent_state_coordinator_extraction_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Auto Design Blocked Incoherent-State Coordinator Extraction",
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
