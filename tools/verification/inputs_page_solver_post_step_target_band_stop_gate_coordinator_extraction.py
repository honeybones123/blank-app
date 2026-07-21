"""Verify post-step target-band stop gate solver coordinator extraction."""

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


def _run_case(module: Any, *, w_pass: bool, in_band: bool, unresolved_spacing: bool) -> dict[str, Any]:
    originals = {
        "_candidate_in_target_band": getattr(module, "_candidate_in_target_band", _MISSING),
        "_trace_post_step_reached_target_band_solver_stop_coordinator": (
            module._trace_post_step_reached_target_band_solver_stop_coordinator
        ),
    }
    calls: list[dict[str, Any]] = []

    def _candidate_in_target_band(w_gate_eval: dict[str, Any], mode_config: dict[str, Any]) -> bool:
        calls.append({"name": "in_band", "mode": dict(mode_config)})
        return in_band

    def _stop(**kwargs: Any) -> tuple[str, str]:
        calls.append({"name": "stop", "kwargs": dict(kwargs)})
        return "reached_target_band", "solved"

    try:
        module._candidate_in_target_band = _candidate_in_target_band
        module._trace_post_step_reached_target_band_solver_stop_coordinator = _stop
        returned = module._handle_one_click_solver_post_step_target_band_stop_gate_coordinator(
            w_pass=w_pass,
            w_gate_eval={"overview": {"worst_util": 0.94}},
            mode_config={"target": "band"},
            unresolved_spacing_fail_after_step=unresolved_spacing,
            step_trace=[{"step": 1}],
            initial_snapshot={"D": 600},
            working={"D": 650},
            winning_label="Winner",
            winning_action_type="tighten",
            tightening_step_count=2,
            max_tightening_steps=4,
            no_actionable_after_full_tightening_search=False,
            candidate_family_depth_reached="combined",
            final_distance_to_band=0.0,
            trace_callback=lambda ev, dat: None,
        )
    finally:
        for attr, original in originals.items():
            if original is _MISSING:
                delattr(module, attr)
            else:
                setattr(module, attr, original)

    expected_stop = bool(w_pass and in_band and not unresolved_spacing)
    expected_calls = (["in_band", "stop"] if expected_stop else ["in_band"]) if w_pass else []
    return {
        "returned": returned,
        "calls": calls,
        "matches": (
            returned["should_break"] is expected_stop
            and returned["stop_reason"] == ("reached_target_band" if expected_stop else None)
            and returned["status"] == ("solved" if expected_stop else None)
            and [call["name"] for call in calls] == expected_calls
        ),
    }


def build_payload() -> dict[str, Any]:
    source = _read(AUTO_DESIGN_COMPUTE)
    helper_start, helper_end, helper = _function_segment(
        source,
        "_handle_one_click_solver_post_step_target_band_stop_gate_coordinator",
    )
    aggregate_start, aggregate_end, aggregate = _function_segment(
        source,
        "_handle_one_click_solver_accepted_candidate_post_step_coordinator",
    )
    _, _, aggregate_result_packer = _function_segment(
        source,
        "_build_one_click_solver_accepted_candidate_post_step_result_state_coordinator",
    )
    _, _, iteration_loop = _function_segment(
        source,
        "_run_one_click_solver_iteration_loop_coordinator",
    )
    _, _, candidate_flow = _function_segment(
        source,
        "_run_one_click_solver_iteration_candidate_flow_coordinator",
    )
    _, _, post_selection = _function_segment(
        source,
        "_run_one_click_solver_iteration_post_selection_acceptance_flow_coordinator",
    )
    _, _, accepted_candidate_dispatch = _function_segment(
        source,
        "_dispatch_one_click_solver_accepted_candidate_post_step_from_post_selection_coordinator",
    )
    solve_start, solve_end, solve_body = _function_segment(source, "_solve_one_click_to_target")

    import inputs_page_modules.auto_design_compute as module  # noqa: E402

    runtime = {
        "hit": _run_case(module, w_pass=True, in_band=True, unresolved_spacing=False)["matches"],
        "blocked_by_pass": _run_case(module, w_pass=False, in_band=True, unresolved_spacing=False)["matches"],
        "blocked_by_target_band": _run_case(module, w_pass=True, in_band=False, unresolved_spacing=False)["matches"],
        "blocked_by_spacing": _run_case(module, w_pass=True, in_band=True, unresolved_spacing=True)["matches"],
    }
    static_checks = {
        "helper_present": "def _handle_one_click_solver_post_step_target_band_stop_gate_coordinator(" in source,
        "helper_preserves_gate_condition": (
            "if w_pass and _candidate_in_target_band(w_gate_eval, mode_config) and not unresolved_spacing_fail_after_step:"
            in helper
        ),
        "helper_delegates_post_step_stop": "_trace_post_step_reached_target_band_solver_stop_coordinator(" in helper,
        "helper_returns_should_break_true": '"should_break": True' in helper,
        "helper_returns_should_break_false": '"should_break": False' in helper,
        "aggregate_delegates_target_band_stop_gate": (
            "_handle_one_click_solver_post_step_target_band_stop_gate_coordinator(" in aggregate
        ),
        "solver_delegates_iteration_loop": (
            "_dispatch_one_click_solver_iteration_loop_from_solver_runtime_setup_coordinator(" in solve_body
        ),
        "iteration_loop_delegates_candidate_flow": (
            "_dispatch_one_click_solver_iteration_candidate_flow_from_iteration_loop_coordinator("
            in iteration_loop
        ),
        "candidate_flow_delegates_post_selection": (
            "_dispatch_one_click_solver_post_selection_acceptance_flow_from_iteration_candidate_flow_coordinator("
            in candidate_flow
        ),
        "post_selection_delegates_accepted_candidate_post_step": (
            "_dispatch_one_click_solver_accepted_candidate_post_step_from_post_selection_coordinator("
            in post_selection
        ),
        "accepted_candidate_dispatch_delegates_aggregate": (
            "_handle_one_click_solver_accepted_candidate_post_step_coordinator("
            in accepted_candidate_dispatch
        ),
        "result_packer_rehydrates_break_state": all(
            token in aggregate_result_packer
            for token in (
                '"stop_reason": post_step_target_band_stop_gate_state["stop_reason"]',
                '"status": post_step_target_band_stop_gate_state["status"]',
                '"should_break": post_step_target_band_stop_gate_state["should_break"]',
            )
        ),
        "solver_no_longer_delegates_target_band_stop_gate_directly": (
            "_handle_one_click_solver_post_step_target_band_stop_gate_coordinator(" not in solve_body
        ),
    }
    status = "PASS"
    if not all(static_checks.values()) or not all(runtime.values()):
        status = "FAIL"
    return {
        "status": status,
        "surface": "_solve_one_click_to_target_post_step_target_band_stop_gate_coordinator",
        "helper_segment": {
            "function": "_handle_one_click_solver_post_step_target_band_stop_gate_coordinator",
            "start_line": helper_start,
            "end_line": helper_end,
            "line_count": helper_end - helper_start + 1,
        },
        "aggregate_segment": {
            "function": "_handle_one_click_solver_accepted_candidate_post_step_coordinator",
            "start_line": aggregate_start,
            "end_line": aggregate_end,
            "line_count": aggregate_end - aggregate_start + 1,
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
        "next_safe_slice": "extract final evaluation preparation coordinator",
    }


def write_artifacts(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now().isoformat(timespec="seconds").replace(":", "-")
    json_path = ARTIFACT_DIR / f"inputs_page_solver_post_step_target_band_stop_gate_coordinator_extraction_{stamp}.json"
    md_path = AUDIT_DIR / f"inputs_page_solver_post_step_target_band_stop_gate_coordinator_extraction_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Solver Post-Step Target-Band Stop Gate Coordinator Extraction",
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
