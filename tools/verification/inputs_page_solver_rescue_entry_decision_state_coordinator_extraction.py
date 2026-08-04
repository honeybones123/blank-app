"""Verify rescue entry decision state solver coordinator extraction."""

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
_MISSING = object()


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


def _run_case(module: Any, *, enabled: bool) -> dict[str, Any]:
    originals = {
        "_rescue_mode_should_enter": getattr(module, "_rescue_mode_should_enter", _MISSING),
        "_trace_rescue_decision_solver_coordinator": module._trace_rescue_decision_solver_coordinator,
    }
    calls: list[dict[str, Any]] = []
    rescue_debug = {"rescue_mode_exit_reason": "existing"}

    def _should_enter(**kwargs: Any):
        calls.append({"name": "should_enter", "kwargs": dict(kwargs)})
        return True, "blocked", "shear", "wide", {"gate": "open"}

    def _trace(**kwargs: Any) -> None:
        calls.append({"name": "trace", "kwargs": dict(kwargs)})

    try:
        module._rescue_mode_should_enter = _should_enter
        module._trace_rescue_decision_solver_coordinator = _trace
        returned = module._prepare_one_click_solver_rescue_entry_decision_state_coordinator(
            rescue_enabled=enabled,
            rescue_debug=rescue_debug,
            initial_snapshot={"D": 600},
            init_eval={"overview": {"worst_util": 1.1}},
            final_eval={"overview": {"worst_util": 1.0}},
            final_pass=False,
            final_updates={"D": 50},
            stop_reason="no_actionable_candidates",
            mode_config={"target": "band"},
            trace_callback=lambda ev, dat: None,
        )
    finally:
        for attr, original in originals.items():
            if original is _MISSING:
                delattr(module, attr)
            else:
                setattr(module, attr, original)

    if enabled:
        expected_return = {
            "rescue_should_enter": True,
            "rescue_entry_reason": "blocked",
            "rescue_family": "shear",
            "rescue_tier_requested": "wide",
            "rescue_gate_debug": {"gate": "open"},
        }
        expected_calls = ["should_enter", "trace"]
        expected_exit_reason = "existing"
    else:
        expected_return = {
            "rescue_should_enter": False,
            "rescue_entry_reason": None,
            "rescue_family": None,
            "rescue_tier_requested": None,
            "rescue_gate_debug": {},
        }
        expected_calls = ["trace"]
        expected_exit_reason = "not_entered"
    return {
        "returned": returned,
        "rescue_debug": rescue_debug,
        "calls": calls,
        "matches": (
            returned == expected_return
            and [call["name"] for call in calls] == expected_calls
            and rescue_debug["rescue_mode_entered"] is enabled
            and rescue_debug["rescue_mode_entry_reason"] == expected_return["rescue_entry_reason"]
            and rescue_debug["rescue_mode_family"] == expected_return["rescue_family"]
            and rescue_debug["rescue_mode_tier_requested"] == expected_return["rescue_tier_requested"]
            and rescue_debug["rescue_mode_exit_reason"] == expected_exit_reason
            and calls[-1]["kwargs"]["rescue_should_enter"] is enabled
        ),
    }


def build_payload() -> dict[str, Any]:
    source = _read(AUTO_DESIGN_COMPUTE)
    helper_start, helper_end, helper = _function_segment(
        source,
        "_prepare_one_click_solver_rescue_entry_decision_state_coordinator",
    )
    finalization_start, finalization_end, finalization = _function_segment(
        source,
        "_finalize_one_click_solver_result_coordinator",
    )
    _, _, after_final_eval_helper = _function_segment(
        source,
        "_run_one_click_solver_finalization_after_final_evaluation_coordinator",
    )
    _, _, rescue_entry_dispatch = _function_segment(
        source,
        "_dispatch_one_click_solver_rescue_entry_decision_from_finalization_coordinator",
    )
    solve_start, solve_end, solve_body = _function_segment(source, "_solve_one_click_to_target")
    _, _, finish_body = _function_segment(
        source,
        "_finish_one_click_solver_iteration_loop_result_coordinator",
    )

    import inputs_page_modules.auto_design_compute as module  # noqa: E402

    enabled = _run_case(module, enabled=True)
    disabled = _run_case(module, enabled=False)
    runtime = {
        "enabled_rescue_entry": enabled["matches"],
        "disabled_rescue_defaults": disabled["matches"],
    }
    static_checks = {
        "helper_present": "def _prepare_one_click_solver_rescue_entry_decision_state_coordinator(" in source,
        "helper_preserves_default_fields": all(
            token in helper
            for token in (
                "rescue_should_enter = False",
                "rescue_entry_reason = None",
                "rescue_family = None",
                "rescue_tier_requested = None",
                "rescue_gate_debug: dict = {}",
            )
        ),
        "helper_preserves_rescue_enabled_gate": "if rescue_enabled:" in helper,
        "helper_calls_rescue_mode_should_enter": "_rescue_mode_should_enter(" in helper,
        "helper_updates_rescue_debug": all(
            token in helper
            for token in (
                'rescue_debug["rescue_mode_entered"]',
                'rescue_debug["rescue_mode_entry_reason"]',
                'rescue_debug["rescue_mode_family"]',
                'rescue_debug["rescue_mode_tier_requested"]',
                'rescue_debug["rescue_mode_exit_reason"]',
            )
        ),
        "helper_delegates_rescue_decision_trace": "_trace_rescue_decision_solver_coordinator(" in helper,
        "finalization_delegates_rescue_entry_decision": (
            "_dispatch_one_click_solver_rescue_entry_decision_from_finalization_coordinator("
            in after_final_eval_helper
            and "_prepare_one_click_solver_rescue_entry_decision_state_coordinator("
            in rescue_entry_dispatch
            and "finalization_scope[" in rescue_entry_dispatch
        ),
        "finish_delegates_finalization": "_finalize_one_click_solver_result_coordinator(" in finish_body,
        "solver_delegates_loop_result_finish": "_finish_one_click_solver_iteration_loop_result_coordinator("
        in solve_body,
        "finalization_rehydrates_rescue_fields": all(
            token in after_final_eval_helper
            for token in (
                '"rescue_should_enter": rescue_entry_decision_state["rescue_should_enter"]',
                '"rescue_entry_reason": rescue_entry_decision_state["rescue_entry_reason"]',
                '"rescue_family": rescue_entry_decision_state["rescue_family"]',
                '"rescue_tier_requested": rescue_entry_decision_state["rescue_tier_requested"]',
                '"rescue_gate_debug": rescue_entry_decision_state["rescue_gate_debug"]',
            )
        ),
    }
    status = "PASS"
    if not all(static_checks.values()) or not all(runtime.values()):
        status = "FAIL"
    return {
        "status": status,
        "surface": "_solve_one_click_to_target_rescue_entry_decision_state_coordinator",
        "helper_segment": {
            "function": "_prepare_one_click_solver_rescue_entry_decision_state_coordinator",
            "start_line": helper_start,
            "end_line": helper_end,
            "line_count": helper_end - helper_start + 1,
        },
        "finalization_segment": {
            "function": "_finalize_one_click_solver_result_coordinator",
            "start_line": finalization_start,
            "end_line": finalization_end,
            "line_count": finalization_end - finalization_start + 1,
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
        "next_safe_slice": "extract rescue seed loop coordinator",
    }


def write_artifacts(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now().isoformat(timespec="seconds").replace(":", "-")
    json_path = ARTIFACT_DIR / f"inputs_page_solver_rescue_entry_decision_state_coordinator_extraction_{stamp}.json"
    md_path = AUDIT_DIR / f"inputs_page_solver_rescue_entry_decision_state_coordinator_extraction_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Solver Rescue Entry Decision State Coordinator Extraction",
        "",
        f"Status: `{payload['status']}`",
        "",
        "## Static Checks",
    ]
    for key, value in payload["static_checks"].items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(["", "## Runtime"])
    for key, value in payload["runtime"].items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(["", "## Next Safe Slice", "", str(payload["next_safe_slice"])])
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, md_path


def main() -> int:
    payload = build_payload()
    json_path, md_path = write_artifacts(payload)
    print(json.dumps({"status": payload["status"], "json": str(json_path), "report": str(md_path)}, indent=2))
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
