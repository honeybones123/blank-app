"""Verify post-step solver iteration trace extraction."""

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
    original_payload = getattr(module, "_one_click_trace_eval_domain_payload", None)
    calls: list[dict[str, Any]] = []

    def _fake_domain_payload(eval_payload: dict, mode_config: dict) -> dict[str, Any]:
        return {"domain_payload": eval_payload.get("domain")}

    def _trace(ev: str, dat: dict) -> None:
        calls.append({"ev": ev, "dat": dict(dat)})

    try:
        module._one_click_trace_eval_domain_payload = _fake_domain_payload
        returned = module._trace_post_step_solver_iteration_coordinator(
            w_gate_eval={"domain": "shear"},
            mode_config={},
            step_idx=5,
            winning_label="Post candidate",
            winning_action_type="tighten",
            tightening_step_count=3,
            max_tightening_steps=4,
            continuing_tightening_after_step=True,
            still_under_after_step=True,
            no_actionable_after_full_tightening_search=False,
            candidate_family_depth_reached="combined",
            best_distance_to_band_this_iteration=0.12,
            final_distance_to_band=0.02,
            unresolved_spacing_fail_after_step=False,
            shear_governing_mode_active=True,
            shear_severity_band="severe",
            shear_candidate_family_order=["spacing", "legs"],
            spacing_candidates_considered=4,
            leg_candidates_considered=3,
            dia_candidates_considered=2,
            geometry_candidates_considered_for_shear=1,
            combined_candidates_considered_for_shear=5,
            web_crushing_penalty_applied=1,
            rejected_as_spacing_too_weak=2,
            rejected_as_web_crushing_marginal=3,
            rejected_as_impractical_shear_layout=4,
            final_resolved_shear_util=0.88,
            final_resolved_web_util=0.66,
            shear_governing_family_detected=True,
            governing_family_exists_after_domain_fix=True,
            pruned_non_shear_family_count=7,
            trace_callback=_trace,
        )
    finally:
        if original_payload is not None:
            module._one_click_trace_eval_domain_payload = original_payload

    expected = [
        {
            "ev": "iteration_winner",
            "dat": {
                "domain_payload": "shear",
                "step": 5,
                "chosen_label": "Post candidate",
                "chosen_action_type": "tighten",
                "tightening_step_count": 3,
                "tightening_depth_budget": 4,
                "continuing_tightening_after_step": True,
                "still_materially_under_target": True,
                "no_actionable_after_full_tightening_search": False,
                "candidate_family_depth_reached": "combined",
                "best_distance_to_band_this_iteration": 0.12,
                "final_distance_to_band": 0.02,
                "unresolved_spacing_envelope_fail": False,
                "shear_governing_mode_active": True,
                "shear_severity_band": "severe",
                "shear_candidate_family_order": ["spacing", "legs"],
                "spacing_candidates_considered": 4,
                "leg_candidates_considered": 3,
                "dia_candidates_considered": 2,
                "geometry_candidates_considered_for_shear": 1,
                "combined_candidates_considered_for_shear": 5,
                "web_crushing_penalty_applied": 1,
                "rejected_as_spacing_too_weak": 2,
                "rejected_as_web_crushing_marginal": 3,
                "rejected_as_impractical_shear_layout": 4,
                "final_resolved_shear_util": 0.88,
                "final_resolved_web_util": 0.66,
                "shear_governing_family_detected": True,
                "governing_family_exists_after_domain_fix": True,
                "pruned_non_shear_family_count": 7,
                "accepted": True,
                "reason_selected": "post_apply_tightening_continuation_check",
            },
        }
    ]
    return {
        "returned": returned,
        "calls": calls,
        "matches": returned is None and calls == expected,
    }


def build_payload() -> dict[str, Any]:
    source = _read(AUTO_DESIGN_COMPUTE)
    helper_start, helper_end, helper = _function_segment(source, "_trace_post_step_solver_iteration_coordinator")
    metrics_start, metrics_end, metrics_helper = _function_segment(
        source,
        "_handle_one_click_solver_post_step_metrics_and_trace_coordinator",
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
    delegate_index = metrics_helper.find("_trace_post_step_solver_iteration_coordinator(")
    metrics_dispatch_index = aggregate.find(
        "_dispatch_one_click_solver_post_step_metrics_and_trace_from_accepted_post_step_coordinator("
    )
    _, _, post_step_metrics_dispatch = _function_segment(
        source,
        "_dispatch_one_click_solver_post_step_metrics_and_trace_from_accepted_post_step_coordinator",
    )
    metrics_delegate_index = post_step_metrics_dispatch.find(
        "_handle_one_click_solver_post_step_metrics_and_trace_coordinator("
    )
    target_stop_delegate_index = aggregate.find(
        "_handle_one_click_solver_post_step_target_band_stop_gate_coordinator("
    )
    static_checks = {
        "helper_present": "def _trace_post_step_solver_iteration_coordinator(" in source,
        "helper_emits_iteration_winner": '"iteration_winner"' in helper,
        "helper_preserves_reason": '"post_apply_tightening_continuation_check"' in helper,
        "helper_marks_accepted_true": '"accepted": True' in helper,
        "helper_preserves_shear_diagnostics": all(
            token in helper
            for token in (
                "shear_governing_mode_active",
                "shear_candidate_family_order",
                "web_crushing_penalty_applied",
                "final_resolved_shear_util",
                "pruned_non_shear_family_count",
            )
        ),
        "metrics_helper_delegates_post_step_iteration": delegate_index >= 0,
        "aggregate_delegates_post_step_metrics_dispatch": metrics_dispatch_index >= 0,
        "post_step_metrics_dispatch_delegates_post_step_metrics": metrics_delegate_index >= 0,
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
        "aggregate_delegates_metrics_before_stop": (
            metrics_dispatch_index >= 0
            and target_stop_delegate_index >= 0
            and metrics_dispatch_index < target_stop_delegate_index
        ),
        "solver_no_longer_inlines_post_step_iteration_trace": (
            '"reason_selected": "post_apply_tightening_continuation_check"'
        )
        not in solve_body,
    }
    status = "PASS"
    if not all(static_checks.values()) or not runtime["matches"]:
        status = "FAIL"
    return {
        "status": status,
        "surface": "_solve_one_click_to_target_post_step_iteration_coordinator",
        "helper_segment": {
            "function": "_trace_post_step_solver_iteration_coordinator",
            "start_line": helper_start,
            "end_line": helper_end,
            "line_count": helper_end - helper_start + 1,
        },
        "metrics_helper_segment": {
            "function": "_handle_one_click_solver_post_step_metrics_and_trace_coordinator",
            "start_line": metrics_start,
            "end_line": metrics_end,
            "line_count": metrics_end - metrics_start + 1,
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
        "next_safe_slice": "extract repeated-state stop coordinator",
    }


def write_artifacts(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now().isoformat(timespec="seconds").replace(":", "-")
    json_path = ARTIFACT_DIR / f"inputs_page_post_step_solver_iteration_coordinator_extraction_{stamp}.json"
    md_path = AUDIT_DIR / f"inputs_page_post_step_solver_iteration_coordinator_extraction_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Post-Step Solver Iteration Coordinator Extraction",
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
            f"- Iteration trace matches: `{payload['runtime']['matches']}`",
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
