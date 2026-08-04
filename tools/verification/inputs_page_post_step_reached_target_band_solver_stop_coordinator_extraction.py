"""Verify post-step reached-target-band solver stop extraction."""

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
    original_diff = getattr(module, "_one_click_diff_accumulated_updates", None)
    calls: list[dict[str, Any]] = []

    def _fake_diff(initial_snapshot: dict, working: dict) -> dict[str, Any]:
        return {"delta_D": working.get("D", 0) - initial_snapshot.get("D", 0)}

    def _trace(ev: str, dat: dict) -> None:
        calls.append({"ev": ev, "dat": dict(dat)})

    try:
        module._one_click_diff_accumulated_updates = _fake_diff
        returned = module._trace_post_step_reached_target_band_solver_stop_coordinator(
            w_gate_eval={"overview": {"worst_util": 0.94}},
            step_trace=[{"step": 1}, {"step": 2}],
            initial_snapshot={"D": 600},
            working={"D": 660},
            winning_label="Final candidate",
            winning_action_type="tighten",
            tightening_step_count=2,
            max_tightening_steps=4,
            no_actionable_after_full_tightening_search=True,
            candidate_family_depth_reached="combined",
            final_distance_to_band=0.0,
            trace_callback=_trace,
        )
    finally:
        if original_diff is not None:
            module._one_click_diff_accumulated_updates = original_diff

    expected = [
        {
            "ev": "stop",
            "dat": {
                "stop_reason": "reached_target_band",
                "step_count": 2,
                "status": "solved",
                "final_preview_util": 0.94,
                "reached_target_band": True,
                "all_key_pass": True,
                "winning_label": "Final candidate",
                "winning_action_type": "tighten",
                "final_updates": {"delta_D": 60},
                "tightening_step_count": 2,
                "tightening_depth_budget": 4,
                "continuing_tightening_after_step": False,
                "still_materially_under_target": False,
                "no_actionable_after_full_tightening_search": True,
                "candidate_family_depth_reached": "combined",
                "final_distance_to_band": 0.0,
            },
        }
    ]
    return {
        "returned": returned,
        "calls": calls,
        "matches": returned == ("reached_target_band", "solved") and calls == expected,
    }


def build_payload() -> dict[str, Any]:
    source = _read(AUTO_DESIGN_COMPUTE)
    helper_start, helper_end, helper = _function_segment(source, "_trace_post_step_reached_target_band_solver_stop_coordinator")
    gate_start, gate_end, gate_helper = _function_segment(
        source,
        "_handle_one_click_solver_post_step_target_band_stop_gate_coordinator",
    )
    aggregate_start, aggregate_end, aggregate = _function_segment(
        source,
        "_handle_one_click_solver_accepted_candidate_post_step_coordinator",
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

    runtime = _run_case(module)
    static_checks = {
        "helper_present": "def _trace_post_step_reached_target_band_solver_stop_coordinator(" in source,
        "helper_preserves_stop_reason": '"reached_target_band"' in helper,
        "helper_preserves_solved_status": '"solved"' in helper,
        "helper_preserves_post_step_flags": all(
            token in helper
            for token in (
                '"continuing_tightening_after_step": False',
                '"still_materially_under_target": False',
                '"no_actionable_after_full_tightening_search": bool(no_actionable_after_full_tightening_search)',
            )
        ),
        "helper_uses_diff_builder": "_one_click_diff_accumulated_updates(initial_snapshot, working)" in helper,
        "gate_delegates_post_step_stop": "_trace_post_step_reached_target_band_solver_stop_coordinator(" in gate_helper,
        "gate_preserves_post_step_gate": (
            "if w_pass and _candidate_in_target_band(w_gate_eval, mode_config) and not unresolved_spacing_fail_after_step:"
            in gate_helper
        ),
        "aggregate_delegates_post_step_stop_gate": (
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
        "solver_no_longer_inlines_post_step_stop": (
            'if w_pass and _candidate_in_target_band(w_gate_eval, mode_config) and not unresolved_spacing_fail_after_step:\n'
            '            stop_reason = "reached_target_band"\n'
            '            status = "solved"\n'
            '            _t('
        )
        not in solve_body,
    }
    status = "PASS"
    if not all(static_checks.values()) or not runtime["matches"]:
        status = "FAIL"
    return {
        "status": status,
        "surface": "_solve_one_click_to_target_post_step_reached_target_band_stop_coordinator",
        "helper_segment": {
            "function": "_trace_post_step_reached_target_band_solver_stop_coordinator",
            "start_line": helper_start,
            "end_line": helper_end,
            "line_count": helper_end - helper_start + 1,
        },
        "gate_segment": {
            "function": "_handle_one_click_solver_post_step_target_band_stop_gate_coordinator",
            "start_line": gate_start,
            "end_line": gate_end,
            "line_count": gate_end - gate_start + 1,
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
        "next_safe_slice": "extract post-step iteration-winner trace coordinator",
    }


def write_artifacts(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now().isoformat(timespec="seconds").replace(":", "-")
    json_path = ARTIFACT_DIR / f"inputs_page_post_step_reached_target_band_solver_stop_coordinator_extraction_{stamp}.json"
    md_path = AUDIT_DIR / f"inputs_page_post_step_reached_target_band_solver_stop_coordinator_extraction_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Post-Step Reached-Target-Band Solver Stop Coordinator Extraction",
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
            f"- Stop tuple and trace match: `{payload['runtime']['matches']}`",
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
