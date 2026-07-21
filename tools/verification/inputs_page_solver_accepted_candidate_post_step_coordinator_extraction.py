"""Verify accepted-candidate post-step solver coordinator extraction."""

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
        if isinstance(node, ast.FunctionDef) and node.name == name:
            start = int(node.lineno)
            end = int(getattr(node, "end_lineno", node.lineno))
            lines = source.splitlines()
            return start, end, "\n".join(lines[start - 1 : end])
    raise AssertionError(f"Function not found: {name}")


def _call_kwargs() -> dict[str, Any]:
    return {
        "best": {"label": "Accepted", "action_type": "tighten"},
        "mode_config": {"mode": "balanced"},
        "step_idx": 6,
        "tightening_step_count": 1,
        "max_tightening_steps": 4,
        "candidate_family_depth_reached": "spacing",
        "best_distance_to_band_this_iteration": 0.11,
        "initial_snapshot": {"D": 600},
        "working": {"D": 600},
        "step_trace": [],
        "winning_label": "Previous",
        "winning_action_type": "previous_action",
        "target_domains_for_band": ["bending"],
        "target_band_domain": "bending",
        "seen_sigs": set(),
        "governing_domain": "shear",
        "tightening_mode_active": True,
        "step_committable_eval_trace": [],
        "no_actionable_after_full_tightening_search": False,
        "shear_governing_mode_active": True,
        "shear_severity_band": "high",
        "shear_candidate_family_order": ["spacing", "legs"],
        "spacing_candidates_considered": 5,
        "leg_candidates_considered": 4,
        "dia_candidates_considered": 3,
        "geometry_candidates_considered_for_shear": 2,
        "combined_candidates_considered_for_shear": 1,
        "web_crushing_penalty_applied": 0,
        "rejected_as_spacing_too_weak": 6,
        "rejected_as_web_crushing_marginal": 7,
        "rejected_as_impractical_shear_layout": 8,
        "final_resolved_shear_util": 0.5,
        "final_resolved_web_util": 0.4,
        "shear_governing_family_detected": True,
        "governing_family_exists_after_domain_fix": True,
        "pruned_non_shear_family_count": 9,
        "trace_callback": lambda *_args, **_kwargs: None,
    }


def _run_cases(module: Any) -> dict[str, Any]:
    originals = {
        "_handle_one_click_solver_apply_selected_candidate_and_evaluate_coordinator": getattr(
            module,
            "_handle_one_click_solver_apply_selected_candidate_and_evaluate_coordinator",
            None,
        ),
        "_handle_one_click_solver_post_apply_trace_and_committable_preview_coordinator": getattr(
            module,
            "_handle_one_click_solver_post_apply_trace_and_committable_preview_coordinator",
            None,
        ),
        "_handle_one_click_solver_post_step_metrics_and_trace_coordinator": getattr(
            module,
            "_handle_one_click_solver_post_step_metrics_and_trace_coordinator",
            None,
        ),
        "_handle_one_click_solver_post_step_target_band_stop_gate_coordinator": getattr(
            module,
            "_handle_one_click_solver_post_step_target_band_stop_gate_coordinator",
            None,
        ),
    }
    calls: list[dict[str, Any]] = []
    active = {"case": "success"}

    def _apply(**kwargs: Any) -> dict[str, Any]:
        calls.append({"fn": "apply", "case": active["case"], "step_idx": kwargs["step_idx"]})
        if active["case"] == "break":
            return {
                "working": {"D": 600},
                "w_eval": None,
                "accumulated_updates": None,
                "target_domains": None,
                "stop_reason": "evaluate_failed_after_apply",
                "status": "failed",
                "should_break": True,
            }
        return {
            "working": {"D": 620},
            "w_eval": {"overview": {"worst_util": 0.91}},
            "accumulated_updates": {"D": 20},
            "target_domains": ["bending"],
            "stop_reason": None,
            "status": None,
            "should_break": False,
        }

    def _post_apply(**kwargs: Any) -> dict[str, Any]:
        calls.append(
            {
                "fn": "post_apply",
                "updates": dict(kwargs["accumulated_updates"]),
                "tightening_step_count": kwargs["tightening_step_count"],
            }
        )
        return {
            "winning_label": "Accepted winner",
            "winning_action_type": "tighten",
            "tightening_step_count": 2,
            "w_gate_eval": {"overview": {"all_key_pass": True}, "state": {"D": 620}},
        }

    def _post_metrics(**kwargs: Any) -> dict[str, Any]:
        calls.append(
            {
                "fn": "post_metrics",
                "winning_label": kwargs["winning_label"],
                "tightening_step_count": kwargs["tightening_step_count"],
            }
        )
        return {
            "w_pass": True,
            "unresolved_spacing_fail_after_step": False,
            "still_under_after_step": True,
            "continuing_tightening_after_step": True,
            "final_distance_to_band": 0.03,
            "final_resolved_shear_util": 0.88,
            "final_resolved_web_util": 0.62,
        }

    def _target_stop(**kwargs: Any) -> dict[str, Any]:
        calls.append(
            {
                "fn": "target_stop",
                "case": active["case"],
                "final_distance_to_band": kwargs["final_distance_to_band"],
            }
        )
        if active["case"] == "target_break":
            return {
                "stop_reason": "reached_target_band",
                "status": "solved",
                "should_break": True,
            }
        return {
            "stop_reason": None,
            "status": None,
            "should_break": False,
        }

    try:
        module._handle_one_click_solver_apply_selected_candidate_and_evaluate_coordinator = _apply
        module._handle_one_click_solver_post_apply_trace_and_committable_preview_coordinator = _post_apply
        module._handle_one_click_solver_post_step_metrics_and_trace_coordinator = _post_metrics
        module._handle_one_click_solver_post_step_target_band_stop_gate_coordinator = _target_stop

        active["case"] = "success"
        success = module._handle_one_click_solver_accepted_candidate_post_step_coordinator(**_call_kwargs())
        active["case"] = "target_break"
        target_break = module._handle_one_click_solver_accepted_candidate_post_step_coordinator(**_call_kwargs())
        active["case"] = "break"
        apply_break = module._handle_one_click_solver_accepted_candidate_post_step_coordinator(**_call_kwargs())
    finally:
        for name, original in originals.items():
            if original is not None:
                setattr(module, name, original)
            elif hasattr(module, name):
                delattr(module, name)

    return {
        "success": success,
        "target_break": target_break,
        "apply_break": apply_break,
        "calls": calls,
    }


def build_payload() -> dict[str, Any]:
    source = _read(AUTO_DESIGN_COMPUTE)
    aggregate_start, aggregate_end, aggregate = _function_segment(
        source,
        "_handle_one_click_solver_accepted_candidate_post_step_coordinator",
    )
    _, _, aggregate_result_packer = _function_segment(
        source,
        "_build_one_click_solver_accepted_candidate_post_step_result_state_coordinator",
    )
    _, _, apply_break_packer = _function_segment(
        source,
        "_build_one_click_solver_apply_selected_candidate_break_state_coordinator",
    )
    _, _, post_step_metrics_dispatch = _function_segment(
        source,
        "_dispatch_one_click_solver_post_step_metrics_and_trace_from_accepted_post_step_coordinator",
    )
    loop_start, loop_end, loop_body = _function_segment(
        source,
        "_run_one_click_solver_iteration_loop_coordinator",
    )
    _, _, loop_candidate_flow_dispatch = _function_segment(
        source,
        "_dispatch_one_click_solver_iteration_candidate_flow_from_iteration_loop_coordinator",
    )
    post_selection_start, post_selection_end, post_selection_body = _function_segment(
        source,
        "_run_one_click_solver_iteration_post_selection_acceptance_flow_coordinator",
    )
    _, _, post_selection_accepted_dispatch = _function_segment(
        source,
        "_dispatch_one_click_solver_accepted_candidate_post_step_from_post_selection_coordinator",
    )
    _, _, post_selection_accepted_iteration_dispatch = _function_segment(
        source,
        "_dispatch_one_click_solver_accepted_iteration_state_from_post_selection_coordinator",
    )
    _, _, accepted_packer = _function_segment(
        source, "_build_one_click_solver_accepted_iteration_state_coordinator"
    )
    solve_start, solve_end, solve_body = _function_segment(source, "_solve_one_click_to_target")
    import inputs_page_modules.auto_design_compute as module  # noqa: E402

    runtime = _run_cases(module)
    runtime_checks = {
        "success_calls_apply_post_apply_post_metrics_target_stop": [
            c["fn"] for c in runtime["calls"][:4]
        ]
        == ["apply", "post_apply", "post_metrics", "target_stop"],
        "target_break_calls_full_chain": [c["fn"] for c in runtime["calls"][4:8]]
        == ["apply", "post_apply", "post_metrics", "target_stop"],
        "apply_break_skips_later_helpers": [c["fn"] for c in runtime["calls"][8:]] == ["apply"],
        "success_returns_rehydration_state": runtime["success"] == {
            "working": {"D": 620},
            "w_eval": {"overview": {"worst_util": 0.91}},
            "accumulated_updates": {"D": 20},
            "target_domains": ["bending"],
            "winning_label": "Accepted winner",
            "winning_action_type": "tighten",
            "tightening_step_count": 2,
            "w_gate_eval": {"overview": {"all_key_pass": True}, "state": {"D": 620}},
            "w_pass": True,
            "unresolved_spacing_fail_after_step": False,
            "still_under_after_step": True,
            "continuing_tightening_after_step": True,
            "final_distance_to_band": 0.03,
            "final_resolved_shear_util": 0.88,
            "final_resolved_web_util": 0.62,
            "stop_reason": None,
            "status": None,
            "should_break": False,
        },
        "target_break_returns_stop_gate_state": (
            runtime["target_break"]["should_break"] is True
            and runtime["target_break"]["stop_reason"] == "reached_target_band"
            and runtime["target_break"]["status"] == "solved"
        ),
        "break_returns_apply_stop_state": runtime["apply_break"]["should_break"] is True
        and runtime["apply_break"]["stop_reason"] == "evaluate_failed_after_apply"
        and runtime["apply_break"]["status"] == "failed",
    }
    static_checks = {
        "aggregate_present": "def _handle_one_click_solver_accepted_candidate_post_step_coordinator(" in source,
        "aggregate_delegates_apply_first": (
            aggregate.find("_handle_one_click_solver_apply_selected_candidate_and_evaluate_coordinator(")
            < aggregate.find("_handle_one_click_solver_post_apply_trace_and_committable_preview_coordinator(")
            < aggregate.find(
                "_dispatch_one_click_solver_post_step_metrics_and_trace_from_accepted_post_step_coordinator("
            )
            < aggregate.find("_handle_one_click_solver_post_step_target_band_stop_gate_coordinator(")
        ),
        "post_step_metrics_dispatch_delegates_post_step_metrics": (
            "_handle_one_click_solver_post_step_metrics_and_trace_coordinator("
            in post_step_metrics_dispatch
            and "accepted_post_step_scope[" in post_step_metrics_dispatch
        ),
        "aggregate_preserves_apply_break": (
            'if apply_selected_candidate_state["should_break"]:' in aggregate
            and "_build_one_click_solver_apply_selected_candidate_break_state_coordinator("
            in aggregate
            and '"stop_reason": apply_selected_candidate_state["stop_reason"]'
            in apply_break_packer
            and '"status": apply_selected_candidate_state["status"]' in apply_break_packer
            and '"should_break": True' in apply_break_packer
        ),
        "aggregate_delegates_result_packer": (
            "_build_one_click_solver_accepted_candidate_post_step_result_state_coordinator("
            in aggregate
        ),
        "aggregate_result_packer_returns_post_step_metrics": (
            '"w_pass": post_step_metrics_state["w_pass"]' in aggregate_result_packer
            and '"final_resolved_shear_util": post_step_metrics_state["final_resolved_shear_util"]'
            in aggregate_result_packer
        ),
        "aggregate_result_packer_returns_target_stop_gate_state": (
            '"stop_reason": post_step_target_band_stop_gate_state["stop_reason"]'
            in aggregate_result_packer
            and '"should_break": post_step_target_band_stop_gate_state["should_break"]'
            in aggregate_result_packer
        ),
        "post_selection_delegates_aggregate_dispatch": (
            "_dispatch_one_click_solver_accepted_candidate_post_step_from_post_selection_coordinator("
            in post_selection_body
        ),
        "post_selection_aggregate_dispatch_delegates_aggregate": (
            "_handle_one_click_solver_accepted_candidate_post_step_coordinator("
            in post_selection_accepted_dispatch
            and "post_selection_scope[" in post_selection_accepted_dispatch
        ),
        "post_selection_delegates_accepted_packer": (
            "_dispatch_one_click_solver_accepted_iteration_state_from_post_selection_coordinator("
            in post_selection_body
            and "_build_one_click_solver_accepted_iteration_state_coordinator("
            in post_selection_accepted_iteration_dispatch
            and "post_selection_scope[" in post_selection_accepted_iteration_dispatch
        ),
        "accepted_packer_preserves_post_step_fields": all(
            token in accepted_packer
            for token in (
                '"should_break": accepted_candidate_post_step_state["should_break"]',
                '"working": accepted_candidate_post_step_state["working"]',
                '"final_distance_to_band": accepted_candidate_post_step_state[',
                '"stop_reason": accepted_candidate_post_step_state["stop_reason"]',
                '"status": accepted_candidate_post_step_state["status"]',
            )
        ),
        "loop_delegates_candidate_flow_dispatch": (
            "_dispatch_one_click_solver_iteration_candidate_flow_from_iteration_loop_coordinator("
            in loop_body
        ),
        "loop_candidate_flow_dispatch_delegates_candidate_flow": (
            "_run_one_click_solver_iteration_candidate_flow_coordinator("
            in loop_candidate_flow_dispatch
            and "iteration_loop_scope[" in loop_candidate_flow_dispatch
        ),
        "loop_no_longer_delegates_aggregate_directly": (
            "_handle_one_click_solver_accepted_candidate_post_step_coordinator(" not in loop_body
        ),
        "solver_delegates_iteration_loop": (
            "_dispatch_one_click_solver_iteration_loop_from_solver_runtime_setup_coordinator(" in solve_body
        ),
        "solver_no_longer_delegates_aggregate_directly": (
            "_handle_one_click_solver_accepted_candidate_post_step_coordinator(" not in solve_body
        ),
        "solver_no_longer_delegates_apply_directly": (
            "_handle_one_click_solver_apply_selected_candidate_and_evaluate_coordinator(" not in solve_body
        ),
        "solver_no_longer_delegates_post_apply_directly": (
            "_handle_one_click_solver_post_apply_trace_and_committable_preview_coordinator(" not in solve_body
        ),
        "solver_no_longer_delegates_post_metrics_directly": (
            "_handle_one_click_solver_post_step_metrics_and_trace_coordinator(" not in solve_body
        ),
        "solver_no_longer_delegates_target_stop_gate_directly": (
            "_handle_one_click_solver_post_step_target_band_stop_gate_coordinator(" not in solve_body
        ),
    }
    status = "PASS"
    if not all(static_checks.values()) or not all(runtime_checks.values()):
        status = "FAIL"
    return {
        "status": status,
        "surface": "_solve_one_click_to_target_accepted_candidate_post_step_coordinator",
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
        "loop_segment": {
            "function": "_run_one_click_solver_iteration_loop_coordinator",
            "start_line": loop_start,
            "end_line": loop_end,
            "line_count": loop_end - loop_start + 1,
        },
        "post_selection_segment": {
            "function": "_run_one_click_solver_iteration_post_selection_acceptance_flow_coordinator",
            "start_line": post_selection_start,
            "end_line": post_selection_end,
            "line_count": post_selection_end - post_selection_start + 1,
        },
        "static_checks": static_checks,
        "runtime_checks": runtime_checks,
        "product_behavior_changed": False,
        "next_safe_slice": "extract post-step target-band stop gate handoff",
    }


def write_artifacts(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now().isoformat(timespec="seconds").replace(":", "-")
    json_path = ARTIFACT_DIR / (
        f"inputs_page_solver_accepted_candidate_post_step_coordinator_extraction_{stamp}.json"
    )
    md_path = AUDIT_DIR / (
        f"inputs_page_solver_accepted_candidate_post_step_coordinator_extraction_{stamp}.md"
    )
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Solver Accepted Candidate Post-Step Coordinator Extraction",
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
