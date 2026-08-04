"""Verify auto-design run-state setup coordinator extraction."""

from __future__ import annotations

import ast
import contextlib
import datetime as _dt
import io
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
        self.session_state: dict[str, Any] = {}


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
        "_consume_auto_design_invoke_after_solver_entry_confirmed": getattr(
            module,
            "_consume_auto_design_invoke_after_solver_entry_confirmed",
            None,
        ),
        "_shared_state_snapshot": getattr(module, "_shared_state_snapshot", None),
        "_guidance_state_snapshot": getattr(module, "_guidance_state_snapshot", None),
        "_design_state_coherence_check": getattr(module, "_design_state_coherence_check", None),
        "_build_canonical_design_state_pack": getattr(module, "_build_canonical_design_state_pack", None),
        "_canonical_pack_is_valid": getattr(module, "_canonical_pack_is_valid", None),
        "_design_optimisation_goal": getattr(module, "_design_optimisation_goal", None),
        "evaluate_candidate_full": getattr(module, "evaluate_candidate_full", None),
        "_trace_compact_overview_dict": getattr(module, "_trace_compact_overview_dict", None),
        "_trace_compact_shared_geom_reo": getattr(module, "_trace_compact_shared_geom_reo", None),
        "_stage3_final_published_shear_truth_bundle": getattr(
            module,
            "_stage3_final_published_shear_truth_bundle",
            None,
        ),
        "_stage3_remaining_issue_class_from_overview_state": getattr(
            module,
            "_stage3_remaining_issue_class_from_overview_state",
            None,
        ),
        "_design_guide_trace_compare_meta": getattr(module, "_design_guide_trace_compare_meta", None),
        "_coherence_debug_fields": getattr(module, "_coherence_debug_fields", None),
        "_append_design_guide_trace": getattr(module, "_append_design_guide_trace", None),
    }
    fake_st = _FakeStreamlit()
    fake_st.session_state.update(
        {
            "_one_click_run_feedback": {"old": True},
            "auto_design_latch_owner": "owner-a",
        },
    )
    consumed: list[bool] = []
    traces: list[dict[str, Any]] = []

    raw_state = {"D": 500, "raw": True}
    canonical_state = {
        "D": 500,
        "canonical_pack_built": True,
        "canonical_pack_source": "unit",
    }
    raw_coherence = {
        "coherence_ok": True,
        "issues": ["raw-note"],
        "coherence_blocking_issues": [],
        "coherence_nonblocking_issues": ["raw-warning"],
        "coherence_should_block": False,
        "state_coherence_warning": True,
        "state_coherence_warning_issues": ["raw-warning"],
    }
    canonical_coherence = {
        "coherence_ok": True,
        "issues": [],
        "coherence_blocking_issues": [],
        "coherence_nonblocking_issues": [],
        "coherence_should_block": False,
    }
    pre_eval = {
        "overview": {
            "worst_util": 0.88,
            "statuses": {"bending": "PASS"},
        },
    }

    def _coherence(state: dict[str, Any]) -> dict[str, Any]:
        return raw_coherence if state.get("raw") else canonical_coherence

    def _append(event: str, data: dict[str, Any], *, run_id: str, source: str) -> None:
        traces.append({"event": event, "data": dict(data), "run_id": run_id, "source": source})

    stderr = io.StringIO()
    try:
        module.st = fake_st
        module._consume_auto_design_invoke_after_solver_entry_confirmed = lambda: consumed.append(True)
        module._shared_state_snapshot = lambda: {"shared": True}
        module._guidance_state_snapshot = lambda state: dict(raw_state)
        module._design_state_coherence_check = _coherence
        module._build_canonical_design_state_pack = lambda state: dict(canonical_state)
        module._canonical_pack_is_valid = lambda state: True
        module._design_optimisation_goal = lambda state: "balanced"
        module.evaluate_candidate_full = lambda state, **kwargs: dict(pre_eval)
        module._trace_compact_overview_dict = lambda overview: {
            "worst_util": overview.get("worst_util"),
            "statuses": dict(overview.get("statuses") or {}),
        }
        module._trace_compact_shared_geom_reo = lambda state: {"D": state.get("D")}
        module._stage3_final_published_shear_truth_bundle = lambda state: {"truth": "ok"}
        module._stage3_remaining_issue_class_from_overview_state = (
            lambda state, overview: "none" if overview else "missing"
        )
        module._design_guide_trace_compare_meta = lambda **kwargs: dict(kwargs)
        module._coherence_debug_fields = lambda coherence: {
            "state_coherence_ok": bool(coherence.get("coherence_ok")),
        }
        module._append_design_guide_trace = _append
        with contextlib.redirect_stderr(stderr):
            result = module._prepare_one_click_auto_design_run_state_coordinator(
                trigger_fingerprint=("apply", "button"),
                trace_run_id="run-123",
                tracer_path="trace.jsonl",
                trace_src="run_one_click_auto_design",
                entry_source_norm="inputs_handle_auto_design",
                solver_running_bypassed=True,
            )
    finally:
        for name, original in originals.items():
            if original is not None:
                setattr(module, name, original)

    trace_data = dict(traces[0]["data"] or {}) if traces else {}
    expected_result_subset = {
        "one_click_run_feedback_cleared_at_entry": True,
        "raw_coherence": raw_coherence,
        "current_state": canonical_state,
        "canonical_coherence": canonical_coherence,
        "canonical_pack_valid": True,
        "canonical_pack_error": None,
        "canonical_pack_error_stage": None,
        "goal": "balanced",
        "action_sig": "('apply', 'button')",
        "pack_invalid_block": False,
    }
    return {
        "result": result,
        "expected_subset_matches": all(result.get(k) == v for k, v in expected_result_subset.items()),
        "feedback_cleared": "_one_click_run_feedback" not in fake_st.session_state,
        "consume_called_once": consumed == [True],
        "trace": traces,
        "trace_checks": {
            "event": bool(traces and traces[0]["event"] == "run_start"),
            "run_id": bool(traces and traces[0]["run_id"] == "run-123"),
            "action_signature": trace_data.get("resolved_action_signature") == "('apply', 'button')",
            "pre_run_overview": trace_data.get("pre_run_overview", {}).get("worst_util") == 0.88,
            "compare_starting_worst_util": trace_data.get("compare", {}).get("starting_worst_util") == 0.88,
            "solver_bypass": trace_data.get("run_one_click_solver_running_bypassed") is True,
            "stage3_truth": trace_data.get("stage3_shear_truth_at_run_start") == {"truth": "ok"},
            "coherence_before_rebuild": trace_data.get("state_coherence_issues_before_rebuild") == ["raw-note"],
        },
        "stderr_contains_run_start": "DG TRACE RUN_START" in stderr.getvalue()
        and "trace_run_id=run-123" in stderr.getvalue(),
    }


def build_payload() -> dict[str, Any]:
    source = _read(AUTO_DESIGN_COMPUTE)
    helper_start, helper_end, helper = _function_segment(
        source,
        "_prepare_one_click_auto_design_run_state_coordinator",
    )
    run_start, run_end, run_body = _function_segment(source, "run_one_click_auto_design")
    import inputs_page_modules.auto_design_compute as module  # noqa: E402

    runtime = _run_case(module)
    static_checks = {
        "helper_present": "def _prepare_one_click_auto_design_run_state_coordinator(" in source,
        "helper_consumes_invoke": "_consume_auto_design_invoke_after_solver_entry_confirmed()" in helper,
        "helper_clears_feedback": 'st.session_state.pop("_one_click_run_feedback", None)' in helper,
        "helper_builds_canonical_pack": "_build_canonical_design_state_pack(current_state_raw)" in helper,
        "helper_preserves_pre_run_eval": 'source="one_click_trace_run_start"' in helper,
        "helper_emits_run_start_trace": '"run_start"' in helper,
        "helper_returns_run_state": '"current_state": current_state' in helper,
        "run_delegates_run_state_setup": "_prepare_one_click_auto_design_run_state_coordinator(" in run_body,
        "run_rehydrates_current_state": 'current_state = run_state["current_state"]' in run_body,
        "run_keeps_blocked_path": "if _pack_invalid_block:" in run_body,
    }
    runtime_checks = {
        "expected_subset_matches": bool(runtime["expected_subset_matches"]),
        "feedback_cleared": bool(runtime["feedback_cleared"]),
        "consume_called_once": bool(runtime["consume_called_once"]),
        "trace_checks": all(runtime["trace_checks"].values()),
        "stderr_contains_run_start": bool(runtime["stderr_contains_run_start"]),
    }
    status = "PASS"
    if not all(static_checks.values()) or not all(runtime_checks.values()):
        status = "FAIL"
    return {
        "status": status,
        "surface": "run_one_click_auto_design_run_state_coordinator",
        "helper_segment": {
            "function": "_prepare_one_click_auto_design_run_state_coordinator",
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
        "next_safe_slice": "extract blocked incoherent-state return coordinator from run_one_click_auto_design",
    }


def write_artifacts(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now().isoformat(timespec="seconds").replace(":", "-")
    json_path = ARTIFACT_DIR / f"inputs_page_auto_design_run_state_coordinator_extraction_{stamp}.json"
    md_path = AUDIT_DIR / f"inputs_page_auto_design_run_state_coordinator_extraction_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Auto Design Run-State Coordinator Extraction",
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
