"""Verify one-click solver iteration loop coordinator extraction."""

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
MISSING = object()


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


def _patch(module: Any, replacements: dict[str, Any]) -> dict[str, Any]:
    originals = {name: getattr(module, name, MISSING) for name in replacements}
    for name, value in replacements.items():
        setattr(module, name, value)
    return originals


def _restore(module: Any, originals: dict[str, Any]) -> None:
    for name, original in originals.items():
        if original is MISSING:
            delattr(module, name)
        else:
            setattr(module, name, original)


def _run_acceptance_case(module: Any) -> dict[str, Any]:
    calls: list[str] = []
    trace_events: list[str] = []

    def _trace(label: str, *_args: Any, **_kwargs: Any) -> None:
        trace_events.append(label)

    def _iteration_gate(**kwargs: Any) -> dict[str, Any]:
        calls.append("iteration_gate")
        assert kwargs["trace_callback"] is _trace
        return {
            "should_continue": False,
            "should_break": False,
            "cur_eval": {"overview": {"worst_utilisation": 1.04}},
            "cur_pass": False,
            "cur_sig": ("sig",),
            "tightening_mode_active": False,
            "governing_domain": "bending",
            "target_band_domain": "bending",
            "cur_statuses": {"bending": "FAIL"},
            "cur_shear_status": "PASS",
            "cur_shear_failing": False,
            "cur_fail_keys": ["bending"],
            "governing_domain_norm": "bending",
            "governing_domain_failing": True,
            "cur_ib": False,
            "target_work_domain": "bending",
            "required_domain_work_active": True,
            "in_band_shear_cleanup_deferral": False,
            "final_governing_domain": "bending",
            "shear_governing_mode_active": False,
            "shear_governing_family_detected": False,
            "pruned_non_shear_family_count": 0,
            "domain_match_prune_used": False,
            "shear_prune_rule_source": None,
            "material_improvement_threshold": 0.0,
            "tightening_meta": {"mode": "normal"},
            "cur_u": 1.04,
        }

    def _candidate_pipeline(**kwargs: Any) -> dict[str, Any]:
        calls.append("candidate_pipeline")
        assert kwargs["trace_callback"] is _trace
        assert kwargs["trace_run_id"] == "rid-loop"
        return {
            "raw_n": 1,
            "pool_labels": ["candidate"],
            "prepared": [{"label": "candidate"}],
            "prepared_samples": ["candidate"],
            "reduction_candidates_considered": 1,
            "governing_family_exists": True,
            "shear_governing_family_detected": False,
            "governing_family_exists_after_domain_fix": True,
            "mixed_direction_mode": False,
            "tightening_meta": {"mode": "normal"},
            "candidate_family_depth_reached": False,
            "shear_governing_mode_active": False,
            "shear_severity_band": "mild",
            "shear_candidate_family_order": [],
            "spacing_candidates_considered": 0,
            "leg_candidates_considered": 0,
            "dia_candidates_considered": 0,
            "geometry_candidates_considered_for_shear": 0,
            "combined_candidates_considered_for_shear": 0,
            "rejected_as_non_governing_cleanup": 0,
            "rejected_as_non_governing_shear_strengthening": 0,
            "rejected_as_non_material_improvement": 0,
            "rejected_as_no_real_change": 0,
            "rejected_as_duplicate_signature": 0,
            "rejected_as_evaluation_failed": 0,
            "shear_remove_links_candidate_seen": False,
            "shear_remove_links_candidate_dropped_reason": None,
            "pruned_non_shear_family_count": 0,
            "domain_match_prune_used": False,
            "shear_prune_rule_source": None,
            "growth_candidates_rejected_in_tightening": 0,
            "cur_has_td": True,
            "cur_required_fail_count": 1,
            "cur_required_unsatisfied_count": 1,
            "scored": [],
        }

    def _scoring_loop(**kwargs: Any) -> dict[str, Any]:
        calls.append("scoring_loop")
        assert kwargs["trace_callback"] is _trace
        return {
            "scored": [{"label": "candidate", "score": 1.0}],
            "rejected_as_non_governing_cleanup": 0,
            "rejected_as_non_governing_shear_strengthening": 0,
            "rejected_as_evaluation_failed": 0,
            "rejected_as_duplicate_signature": 0,
            "rejected_as_non_material_improvement": 0,
            "growth_candidates_rejected_in_tightening": 0,
            "shear_remove_links_candidate_seen": False,
            "shear_remove_links_candidate_truth_ok": False,
            "shear_remove_links_candidate_dropped_reason": None,
            "shear_remove_links_candidate_materiality": "not_evaluated",
            "rejected_as_spacing_too_weak": 0,
            "rejected_as_web_crushing_marginal": 0,
            "rejected_as_impractical_shear_layout": 0,
            "web_crushing_penalty_applied": False,
        }

    def _selection(**kwargs: Any) -> dict[str, Any]:
        calls.append("selection")
        assert kwargs["trace_callback"] is _trace
        return {
            "no_actionable_after_full_tightening_search": False,
            "best": {"label": "candidate"},
            "best_distance_to_band_this_iteration": 0.01,
            "should_break": False,
        }

    def _accepted(**kwargs: Any) -> dict[str, Any]:
        calls.append("accepted")
        assert kwargs["trace_callback"] is _trace
        return {
            "working": {"D": 610},
            "w_eval": {"overview": {"worst_utilisation": 0.93}},
            "accumulated_updates": {"D": 610},
            "target_domains": ["bending"],
            "winning_label": "candidate",
            "winning_action_type": "increase_depth",
            "tightening_step_count": 1,
            "w_gate_eval": {"overview": {}},
            "w_pass": True,
            "unresolved_spacing_fail_after_step": False,
            "still_under_after_step": False,
            "continuing_tightening_after_step": False,
            "final_distance_to_band": 0.01,
            "final_resolved_shear_util": None,
            "final_resolved_web_util": None,
            "should_break": True,
            "stop_reason": "target_band_hit",
            "status": "ok",
        }

    def _candidate_flow(**kwargs: Any) -> dict[str, Any]:
        calls.append("candidate_flow")
        assert kwargs["trace_callback"] is _trace
        assert kwargs["trace_run_id"] == "rid-loop"
        return {
            "should_break": True,
            "working": {"D": 610},
            "target_band_domain": "bending",
            "winning_label": "candidate",
            "winning_action_type": "increase_depth",
            "tightening_step_count": 1,
            "no_actionable_after_full_tightening_search": False,
            "candidate_family_depth_reached": False,
            "final_distance_to_band": 0.01,
            "final_governing_domain": "bending",
            "shear_governing_mode_active": False,
            "shear_severity_band": "mild",
            "shear_candidate_family_order": [],
            "spacing_candidates_considered": 0,
            "leg_candidates_considered": 0,
            "dia_candidates_considered": 0,
            "geometry_candidates_considered_for_shear": 0,
            "combined_candidates_considered_for_shear": 0,
            "web_crushing_penalty_applied": False,
            "rejected_as_spacing_too_weak": 0,
            "rejected_as_web_crushing_marginal": 0,
            "rejected_as_impractical_shear_layout": 0,
            "final_resolved_shear_util": None,
            "final_resolved_web_util": None,
            "stop_reason": "target_band_hit",
            "status": "ok",
            "rejected_as_non_governing_cleanup": 0,
            "rejected_as_non_governing_shear_strengthening": 0,
            "shear_remove_links_candidate_seen": False,
            "shear_remove_links_candidate_truth_ok": False,
            "shear_remove_links_candidate_dropped_reason": None,
            "shear_remove_links_candidate_materiality": "not_evaluated",
            "shear_governing_family_detected": False,
            "governing_family_exists_after_domain_fix": True,
            "pruned_non_shear_family_count": 0,
        }

    originals = _patch(
        module,
        {
            "_prepare_one_click_solver_iteration_gate_state_coordinator": _iteration_gate,
            "_run_one_click_solver_iteration_candidate_flow_coordinator": _candidate_flow,
            "_prepare_one_click_solver_candidate_pipeline_state_coordinator": _candidate_pipeline,
            "_run_one_click_solver_candidate_scoring_loop_coordinator": _scoring_loop,
            "_resolve_one_click_solver_scored_candidate_selection_state_coordinator": _selection,
            "_handle_one_click_solver_accepted_candidate_post_step_coordinator": _accepted,
        },
    )
    try:
        result = module._run_one_click_solver_iteration_loop_coordinator(
            max_steps=1,
            debug_enabled=False,
            trace_run_id="rid-loop",
            trace_callback=_trace,
            working={"D": 600},
            mode_config={"mode": "balanced"},
            target_band_domain="bending",
            target_domains_for_band=["bending"],
            step_trace=[],
            initial_snapshot={"D": 600},
            winning_label=None,
            winning_action_type=None,
            tightening_step_count=0,
            max_tightening_steps=4,
            tightening_budget_extensions_used=0,
            tightening_budget_extension_cap=2,
            candidate_family_depth_reached=False,
            stop_reason=None,
            status="running",
            final_distance_to_band=None,
            final_governing_domain=None,
            shear_governing_mode_active=False,
            shear_severity_band="mild",
            shear_candidate_family_order=[],
            spacing_candidates_considered=0,
            leg_candidates_considered=0,
            dia_candidates_considered=0,
            geometry_candidates_considered_for_shear=0,
            combined_candidates_considered_for_shear=0,
            web_crushing_penalty_applied=False,
            rejected_as_spacing_too_weak=0,
            rejected_as_web_crushing_marginal=0,
            rejected_as_impractical_shear_layout=0,
            final_resolved_shear_util=None,
            final_resolved_web_util=None,
            step_committable_eval_trace=[],
            no_actionable_after_full_tightening_search=False,
            rejected_as_non_governing_cleanup=0,
            rejected_as_non_governing_shear_strengthening=0,
            shear_remove_links_candidate_seen=False,
            shear_remove_links_candidate_truth_ok=False,
            shear_remove_links_candidate_dropped_reason=None,
            shear_remove_links_candidate_materiality="not_evaluated",
            t_lo=0.85,
            t_hi=0.95,
            seen_sigs=set(),
        )
    finally:
        _restore(module, originals)
    return {"calls": calls, "trace_events": trace_events, "result": result}


def build_payload() -> dict[str, Any]:
    source = _read(AUTO_DESIGN_COMPUTE)
    helper_start, helper_end, helper = _function_segment(
        source, "_run_one_click_solver_iteration_loop_coordinator"
    )
    _, _, loop_candidate_flow_dispatch = _function_segment(
        source,
        "_dispatch_one_click_solver_iteration_candidate_flow_from_iteration_loop_coordinator",
    )
    _, _, candidate_flow_unpacker = _function_segment(
        source,
        "_unpack_one_click_solver_iteration_candidate_flow_state_for_loop_coordinator",
    )
    solve_start, solve_end, solve_body = _function_segment(source, "_solve_one_click_to_target")
    _, _, finish_body = _function_segment(
        source,
        "_finish_one_click_solver_iteration_loop_result_coordinator",
    )
    _, _, result_packer = _function_segment(
        source,
        "_build_one_click_solver_iteration_loop_result_state_coordinator",
    )

    import inputs_page_modules.auto_design_compute as module  # noqa: E402

    runtime = _run_acceptance_case(module)
    expected_order = [
        "iteration_gate",
        "candidate_flow",
    ]
    runtime_checks = {
        "coordinator_calls_preserve_order": runtime["calls"] == expected_order,
        "accepted_candidate_updates_returned": runtime["result"]["working"] == {"D": 610}
        and runtime["result"]["winning_label"] == "candidate"
        and runtime["result"]["winning_action_type"] == "increase_depth",
        "accepted_break_status_returned": runtime["result"]["status"] == "ok"
        and runtime["result"]["stop_reason"] == "target_band_hit",
        "finalization_fields_returned": runtime["result"]["target_band_domain"] == "bending"
        and runtime["result"]["governing_family_exists_after_domain_fix"] is True
        and runtime["result"]["pruned_non_shear_family_count"] == 0,
    }
    ordered_tokens = [
        "_prepare_one_click_solver_iteration_gate_state_coordinator(",
        "_dispatch_one_click_solver_iteration_candidate_flow_from_iteration_loop_coordinator(",
    ]
    static_checks = {
        "helper_present": "def _run_one_click_solver_iteration_loop_coordinator(" in source,
        "solver_delegates_iteration_loop": "_dispatch_one_click_solver_iteration_loop_from_solver_runtime_setup_coordinator(" in solve_body,
        "solver_no_longer_inlines_iteration_loop": "for step_idx in range(max_steps):" not in solve_body,
        "helper_owns_iteration_loop": "for step_idx in range(max_steps):" in helper,
        "result_packer_present": (
            "def _build_one_click_solver_iteration_loop_result_state_coordinator(" in source
        ),
        "helper_delegates_result_packer": (
            "_build_one_click_solver_iteration_loop_result_state_coordinator(" in helper
        ),
        "loop_candidate_flow_dispatch_delegates_candidate_flow": (
            "_run_one_click_solver_iteration_candidate_flow_coordinator("
            in loop_candidate_flow_dispatch
            and "iteration_loop_scope[" in loop_candidate_flow_dispatch
        ),
        "helper_delegates_candidate_flow_state_unpacker": (
            "_unpack_one_click_solver_iteration_candidate_flow_state_for_loop_coordinator("
            in helper
        ),
        "candidate_flow_unpacker_returns_loop_carried_fields": all(
            token in candidate_flow_unpacker
            for token in (
                'iteration_candidate_flow_state["working"]',
                'iteration_candidate_flow_state["status"]',
                'iteration_candidate_flow_state["governing_family_exists_after_domain_fix"]',
                'iteration_candidate_flow_state["pruned_non_shear_family_count"]',
            )
        ),
        "result_packer_preserves_finalization_fields": all(
            token in result_packer
            for token in (
                '"working": iteration_loop_scope["working"]',
                '"status": iteration_loop_scope["status"]',
                '"governing_family_exists_after_domain_fix": iteration_loop_scope[',
                '"pruned_non_shear_family_count": iteration_loop_scope[',
            )
        ),
        "helper_preserves_coordinator_order": [helper.index(token) for token in ordered_tokens]
        == sorted(helper.index(token) for token in ordered_tokens),
        "helper_no_longer_calls_candidate_subcoordinators_directly": all(
            token not in helper
            for token in (
                "_prepare_one_click_solver_candidate_pipeline_state_coordinator(",
                "_run_one_click_solver_candidate_scoring_loop_coordinator(",
                "_resolve_one_click_solver_scored_candidate_selection_state_coordinator(",
                "_handle_one_click_solver_accepted_candidate_post_step_coordinator(",
            )
        ),
        "helper_uses_explicit_trace_callback": "trace_callback=trace_callback" in helper
        and "trace_callback=_t" not in helper,
        "candidate_flow_dispatch_uses_explicit_trace_run_id": (
            'trace_run_id=iteration_loop_scope["trace_run_id"]'
            in loop_candidate_flow_dispatch
            and "trace_run_id=rid" not in loop_candidate_flow_dispatch
        ),
        "solver_delegates_loop_result_finish": (
            "_finish_one_click_solver_iteration_loop_result_coordinator(" in solve_body
        ),
        "finish_rehydrates_loop_state_for_finalization": (
            'working=iteration_loop_state["working"]' in finish_body
            and 'status=iteration_loop_state["status"]' in finish_body
            and 'governing_family_exists_after_domain_fix=iteration_loop_state[' in finish_body
        ),
    }
    status = "PASS"
    if not all(static_checks.values()) or not all(runtime_checks.values()):
        status = "FAIL"
    return {
        "status": status,
        "product_behavior_changed": False,
        "helper_segment": {
            "start_line": helper_start,
            "end_line": helper_end,
            "line_count": helper_end - helper_start + 1,
        },
        "solver_segment": {
            "start_line": solve_start,
            "end_line": solve_end,
            "line_count": solve_end - solve_start + 1,
        },
        "static_checks": static_checks,
        "runtime_checks": runtime_checks,
        "runtime": runtime,
    }


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    payload = build_payload()
    stamp = _dt.datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    json_path = ARTIFACT_DIR / f"inputs_page_solver_iteration_loop_coordinator_extraction_{stamp}.json"
    md_path = AUDIT_DIR / f"inputs_page_solver_iteration_loop_coordinator_extraction_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    lines = [
        "# Inputs Page Solver Iteration Loop Coordinator Extraction",
        "",
        f"Status: {payload['status']}",
        "",
        f"Product behavior changed: {payload['product_behavior_changed']}",
        "",
        "## Static Checks",
        "",
    ]
    for key, value in payload["static_checks"].items():
        lines.append(f"- {key}: {value}")
    lines.extend(["", "## Runtime Checks", ""])
    for key, value in payload["runtime_checks"].items():
        lines.append(f"- {key}: {value}")
    lines.extend(
        [
            "",
            "## Segments",
            "",
            f"- Helper lines: {payload['helper_segment']['line_count']}",
            f"- Solver lines: {payload['solver_segment']['line_count']}",
        ]
    )
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"status={payload['status']}")
    print(f"json={json_path}")
    print(f"md={md_path}")
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
