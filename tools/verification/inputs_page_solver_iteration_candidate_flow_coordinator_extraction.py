"""Verify one-click solver iteration candidate-flow coordinator extraction."""

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


def _iteration_gate_state() -> dict[str, Any]:
    return {
        "cur_eval": {"overview": {"worst_utilisation": 1.04}},
        "cur_pass": False,
        "cur_sig": ("sig",),
        "tightening_mode_active": False,
        "governing_domain": "bending",
        "target_band_domain": "bending",
        "cur_shear_failing": False,
        "governing_domain_failing": True,
        "cur_ib": False,
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


def _run_case(module: Any, scenario: str) -> dict[str, Any]:
    calls: list[str] = []

    def _trace(*_args: Any, **_kwargs: Any) -> None:
        return None

    def _candidate_pipeline(**kwargs: Any) -> dict[str, Any]:
        calls.append("candidate_pipeline")
        assert kwargs["trace_callback"] is _trace
        assert kwargs["trace_run_id"] == "rid-flow"
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
            "candidate_family_depth_reached": True,
            "shear_governing_mode_active": False,
            "shear_severity_band": "mild",
            "shear_candidate_family_order": ["bending"],
            "spacing_candidates_considered": 2,
            "leg_candidates_considered": 3,
            "dia_candidates_considered": 4,
            "geometry_candidates_considered_for_shear": 5,
            "combined_candidates_considered_for_shear": 6,
            "rejected_as_non_governing_cleanup": 7,
            "rejected_as_non_governing_shear_strengthening": 8,
            "rejected_as_non_material_improvement": 9,
            "rejected_as_no_real_change": 10,
            "rejected_as_duplicate_signature": 11,
            "rejected_as_evaluation_failed": 12,
            "shear_remove_links_candidate_seen": True,
            "shear_remove_links_candidate_dropped_reason": "kept",
            "pruned_non_shear_family_count": 13,
            "domain_match_prune_used": True,
            "shear_prune_rule_source": "domain_matcher",
            "growth_candidates_rejected_in_tightening": 14,
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
            "rejected_as_non_governing_cleanup": 17,
            "rejected_as_non_governing_shear_strengthening": 18,
            "rejected_as_evaluation_failed": 19,
            "rejected_as_duplicate_signature": 20,
            "rejected_as_non_material_improvement": 21,
            "growth_candidates_rejected_in_tightening": 22,
            "shear_remove_links_candidate_seen": True,
            "shear_remove_links_candidate_truth_ok": True,
            "shear_remove_links_candidate_dropped_reason": "kept_by_scoring",
            "shear_remove_links_candidate_materiality": "material",
            "rejected_as_spacing_too_weak": 23,
            "rejected_as_web_crushing_marginal": 24,
            "rejected_as_impractical_shear_layout": 25,
            "web_crushing_penalty_applied": True,
        }

    def _selection(**kwargs: Any) -> dict[str, Any]:
        calls.append("selection")
        assert kwargs["trace_callback"] is _trace
        return {
            "no_actionable_after_full_tightening_search": scenario == "selection_stop",
            "best": {"label": "candidate"},
            "best_distance_to_band_this_iteration": 0.01,
            "should_break": scenario == "selection_stop",
            "stop_reason": "no_actionable_candidates",
            "status": "partial",
            "final_distance_to_band": 0.19,
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
            "final_resolved_shear_util": 0.88,
            "final_resolved_web_util": 0.62,
            "should_break": True,
            "stop_reason": "target_band_hit",
            "status": "ok",
        }

    originals = _patch(
        module,
        {
            "_prepare_one_click_solver_candidate_pipeline_state_coordinator": _candidate_pipeline,
            "_run_one_click_solver_candidate_scoring_loop_coordinator": _scoring_loop,
            "_resolve_one_click_solver_scored_candidate_selection_state_coordinator": _selection,
            "_handle_one_click_solver_accepted_candidate_post_step_coordinator": _accepted,
        },
    )
    try:
        result = module._run_one_click_solver_iteration_candidate_flow_coordinator(
            iteration_gate_state=_iteration_gate_state(),
            working={"D": 600},
            debug_enabled=False,
            trace_run_id="rid-flow",
            step_idx=0,
            mode_config={"mode": "balanced"},
            target_domains_for_band=["bending"],
            target_band_domain="bending",
            initial_snapshot={"D": 600},
            winning_label=None,
            winning_action_type=None,
            tightening_step_count=0,
            max_tightening_steps=4,
            no_actionable_after_full_tightening_search=False,
            candidate_family_depth_reached=False,
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
            rejected_as_non_governing_cleanup=0,
            rejected_as_non_governing_shear_strengthening=0,
            shear_remove_links_candidate_seen=False,
            shear_remove_links_candidate_truth_ok=False,
            shear_remove_links_candidate_dropped_reason=None,
            shear_remove_links_candidate_materiality="not_evaluated",
            t_lo=0.85,
            t_hi=0.95,
            seen_sigs=set(),
            step_trace=[],
            trace_callback=_trace,
        )
    finally:
        _restore(module, originals)
    return {"calls": calls, "result": result}


def build_payload() -> dict[str, Any]:
    source = _read(AUTO_DESIGN_COMPUTE)
    helper_start, helper_end, helper = _function_segment(
        source, "_run_one_click_solver_iteration_candidate_flow_coordinator"
    )
    scope_builder_start, scope_builder_end, scope_builder = _function_segment(
        source,
        "_build_one_click_solver_iteration_candidate_flow_post_selection_scope_coordinator",
    )
    shear_fields_start, shear_fields_end, shear_fields_builder = _function_segment(
        source,
        "_build_one_click_solver_iteration_candidate_flow_post_selection_shear_fields_coordinator",
    )
    pre_selection_start, pre_selection_end, pre_selection = _function_segment(
        source, "_run_one_click_solver_iteration_pre_selection_candidate_evaluation_coordinator"
    )
    _, _, pre_selection_pipeline_and_scoring = _function_segment(
        source,
        "_run_one_click_solver_pre_selection_candidate_pipeline_and_scoring_coordinator",
    )
    _, _, pre_selection_pipeline_dispatch = _function_segment(
        source, "_dispatch_one_click_solver_candidate_pipeline_state_from_pre_selection_coordinator"
    )
    _, _, pre_selection_packer = _function_segment(
        source, "_build_one_click_solver_pre_selection_candidate_evaluation_state_coordinator"
    )
    post_selection_start, post_selection_end, post_selection = _function_segment(
        source, "_run_one_click_solver_iteration_post_selection_acceptance_flow_coordinator"
    )
    _, _, post_selection_accepted_dispatch = _function_segment(
        source,
        "_dispatch_one_click_solver_accepted_candidate_post_step_from_post_selection_coordinator",
    )
    _, _, post_selection_accepted_iteration_dispatch = _function_segment(
        source,
        "_dispatch_one_click_solver_accepted_iteration_state_from_post_selection_coordinator",
    )
    _, _, iteration_flow_post_selection_dispatch = _function_segment(
        source,
        "_dispatch_one_click_solver_post_selection_acceptance_flow_from_iteration_candidate_flow_coordinator",
    )
    _, _, post_selection_selection_dispatch = _function_segment(
        source, "_dispatch_one_click_solver_post_selection_candidate_selection_state_coordinator"
    )
    _, _, selection_stop_packer = _function_segment(
        source, "_build_one_click_solver_selection_stop_iteration_state_coordinator"
    )
    _, _, accepted_packer = _function_segment(
        source, "_build_one_click_solver_accepted_iteration_state_coordinator"
    )
    loop_start, loop_end, loop_body = _function_segment(
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

    import inputs_page_modules.auto_design_compute as module  # noqa: E402

    accepted_runtime = _run_case(module, "accepted")
    selection_stop_runtime = _run_case(module, "selection_stop")
    runtime_checks = {
        "accepted_path_preserves_order": accepted_runtime["calls"]
        == ["candidate_pipeline", "scoring_loop", "selection", "accepted"],
        "selection_stop_skips_accepted": selection_stop_runtime["calls"]
        == ["candidate_pipeline", "scoring_loop", "selection"],
        "accepted_path_returns_post_step_state": (
            accepted_runtime["result"]["should_break"] is True
            and accepted_runtime["result"]["working"] == {"D": 610}
            and accepted_runtime["result"]["winning_label"] == "candidate"
            and accepted_runtime["result"]["final_resolved_shear_util"] == 0.88
            and accepted_runtime["result"]["status"] == "ok"
        ),
        "selection_stop_preserves_pipeline_and_scoring_state": (
            selection_stop_runtime["result"]["should_break"] is True
            and selection_stop_runtime["result"]["status"] == "partial"
            and selection_stop_runtime["result"]["final_distance_to_band"] == 0.19
            and selection_stop_runtime["result"]["candidate_family_depth_reached"] is True
            and selection_stop_runtime["result"]["rejected_as_non_governing_cleanup"] == 17
            and selection_stop_runtime["result"]["web_crushing_penalty_applied"] is True
            and selection_stop_runtime["result"]["governing_family_exists_after_domain_fix"] is True
        ),
    }
    pre_selection_tokens = [
        "_dispatch_one_click_solver_candidate_pipeline_state_from_pre_selection_coordinator(",
        "_dispatch_one_click_solver_candidate_scoring_loop_from_pre_selection_coordinator(",
    ]
    flow_tokens = [
        "_run_one_click_solver_iteration_pre_selection_candidate_evaluation_coordinator(",
        "_dispatch_one_click_solver_post_selection_acceptance_flow_from_iteration_candidate_flow_coordinator(",
    ]
    post_selection_tokens = [
        "_dispatch_one_click_solver_post_selection_candidate_selection_state_coordinator(",
        "_dispatch_one_click_solver_accepted_candidate_post_step_from_post_selection_coordinator(",
    ]
    static_checks = {
        "helper_present": "def _run_one_click_solver_iteration_candidate_flow_coordinator(" in source,
        "pre_selection_helper_present": (
            "def _run_one_click_solver_iteration_pre_selection_candidate_evaluation_coordinator(" in source
        ),
        "pre_selection_packer_present": (
            "def _build_one_click_solver_pre_selection_candidate_evaluation_state_coordinator(" in source
        ),
        "pre_selection_pipeline_dispatch_present": (
            "def _dispatch_one_click_solver_candidate_pipeline_state_from_pre_selection_coordinator("
            in source
        ),
        "pre_selection_scoring_loop_dispatch_present": (
            "def _dispatch_one_click_solver_candidate_scoring_loop_from_pre_selection_coordinator("
            in source
        ),
        "post_selection_helper_present": (
            "def _run_one_click_solver_iteration_post_selection_acceptance_flow_coordinator(" in source
        ),
        "iteration_flow_post_selection_dispatch_present": (
            "def _dispatch_one_click_solver_post_selection_acceptance_flow_from_iteration_candidate_flow_coordinator("
            in source
        ),
        "iteration_flow_post_selection_scope_builder_present": (
            "def _build_one_click_solver_iteration_candidate_flow_post_selection_scope_coordinator("
            in source
        ),
        "selection_stop_packer_present": (
            "def _build_one_click_solver_selection_stop_iteration_state_coordinator(" in source
        ),
        "accepted_packer_present": (
            "def _build_one_click_solver_accepted_iteration_state_coordinator(" in source
        ),
        "post_selection_selection_dispatch_present": (
            "def _dispatch_one_click_solver_post_selection_candidate_selection_state_coordinator(" in source
        ),
        "pre_selection_preserves_candidate_evaluation_order": all(
            token in pre_selection_pipeline_and_scoring for token in pre_selection_tokens
        )
        and [pre_selection_pipeline_and_scoring.index(token) for token in pre_selection_tokens]
        == sorted(pre_selection_pipeline_and_scoring.index(token) for token in pre_selection_tokens),
        "pre_selection_pipeline_dispatch_delegates_candidate_pipeline_state": (
            "_prepare_one_click_solver_candidate_pipeline_state_coordinator("
            in pre_selection_pipeline_dispatch
            and "pre_selection_scope[" in pre_selection_pipeline_dispatch
        ),
        "pre_selection_delegates_state_packer": (
            "_build_one_click_solver_pre_selection_candidate_evaluation_state_coordinator("
            in pre_selection_pipeline_and_scoring
        ),
        "pre_selection_packer_preserves_return_fields": all(
            token in pre_selection_packer
            for token in (
                '"cur_eval": pre_selection_scope["cur_eval"]',
                '"scored": pre_selection_scope["scored"]',
                '"web_crushing_penalty_applied": pre_selection_scope[',
                '"governing_family_exists_after_domain_fix": pre_selection_scope[',
            )
        ),
        "helper_preserves_candidate_flow_order": all(token in helper for token in flow_tokens)
        and [helper.index(token) for token in flow_tokens] == sorted(helper.index(token) for token in flow_tokens),
        "helper_delegates_post_selection_scope_build": (
            "_build_one_click_solver_iteration_candidate_flow_post_selection_scope_coordinator("
            in helper
            and "iteration_candidate_flow_scope=locals()" in helper
            and "pre_selection_state=pre_selection_state" in helper
        ),
        "helper_no_longer_calls_pre_or_post_subcoordinators_directly": all(
            token not in helper for token in (*pre_selection_tokens, *post_selection_tokens)
        ),
        "post_selection_scope_builder_preserves_rehydrated_fields": all(
            token in scope_builder
            for token in (
                '"cur_eval": pre_selection_state["cur_eval"]',
                '"scored": pre_selection_state["scored"]',
                '"target_band_domain": pre_selection_state["target_band_domain"]',
                '"working": iteration_candidate_flow_scope["working"]',
                '"trace_callback": iteration_candidate_flow_scope["trace_callback"]',
            )
        )
        and all(
            token in shear_fields_builder
            for token in (
                '"web_crushing_penalty_applied": pre_selection_state[',
                '"governing_family_exists_after_domain_fix": pre_selection_state[',
            )
        )
        and "_build_one_click_solver_iteration_candidate_flow_post_selection_shear_fields_coordinator("
        in scope_builder,
        "iteration_flow_post_selection_dispatch_delegates_post_selection": (
            "_run_one_click_solver_iteration_post_selection_acceptance_flow_coordinator("
            in iteration_flow_post_selection_dispatch
            and "iteration_candidate_flow_scope[" in iteration_flow_post_selection_dispatch
        ),
        "post_selection_preserves_selection_then_acceptance_order": all(
            token in post_selection for token in post_selection_tokens
        )
        and [post_selection.index(token) for token in post_selection_tokens]
        == sorted(post_selection.index(token) for token in post_selection_tokens),
        "post_selection_accepted_dispatch_delegates_accepted_post_step": (
            "_handle_one_click_solver_accepted_candidate_post_step_coordinator("
            in post_selection_accepted_dispatch
            and "post_selection_scope[" in post_selection_accepted_dispatch
        ),
        "post_selection_selection_dispatch_delegates_selection_state": (
            "_resolve_one_click_solver_scored_candidate_selection_state_coordinator("
            in post_selection_selection_dispatch
        ),
        "post_selection_does_not_recurse": (
            post_selection.count(
                "_run_one_click_solver_iteration_post_selection_acceptance_flow_coordinator("
            )
            == 1
        ),
        "post_selection_preserves_selection_stop_short_circuit": (
            'if scored_candidate_selection_state["should_break"]:' in post_selection
            and "_build_one_click_solver_selection_stop_iteration_state_coordinator(" in post_selection
        ),
        "selection_stop_packer_returns_stop_fields": all(
            token in selection_stop_packer
            for token in (
                '"should_break": True',
                '"no_actionable_after_full_tightening_search": no_actionable_after_full_tightening_search',
                '"final_distance_to_band": scored_candidate_selection_state[',
                '"status": scored_candidate_selection_state["status"]',
            )
        ),
        "post_selection_returns_finalization_fields": all(
            token in accepted_packer
            for token in (
                '"working": accepted_candidate_post_step_state["working"]',
                '"target_band_domain": target_band_domain',
                '"candidate_family_depth_reached": candidate_family_depth_reached',
                '"final_governing_domain": final_governing_domain',
                '"governing_family_exists_after_domain_fix": governing_family_exists_after_domain_fix',
            )
        ),
        "post_selection_delegates_accepted_packer": (
            "_dispatch_one_click_solver_accepted_iteration_state_from_post_selection_coordinator("
            in post_selection
            and "_build_one_click_solver_accepted_iteration_state_coordinator("
            in post_selection_accepted_iteration_dispatch
            and "post_selection_scope[" in post_selection_accepted_iteration_dispatch
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
        "loop_no_longer_calls_candidate_subcoordinators_directly": all(
            token not in loop_body for token in (*pre_selection_tokens, *post_selection_tokens)
        ),
        "loop_rehydrates_candidate_flow_state": all(
            token in candidate_flow_unpacker
            for token in (
                'iteration_candidate_flow_state["working"]',
                'iteration_candidate_flow_state["status"]',
                'iteration_candidate_flow_state["governing_family_exists_after_domain_fix"]',
            )
        )
        and "_unpack_one_click_solver_iteration_candidate_flow_state_for_loop_coordinator("
        in loop_body
        and 'if iteration_candidate_flow_state["should_break"]:' in loop_body,
    }
    status = "PASS"
    if not all(static_checks.values()) or not all(runtime_checks.values()):
        status = "FAIL"
    return {
        "status": status,
        "product_behavior_changed": False,
        "helper_segment": {
            "function": "_run_one_click_solver_iteration_candidate_flow_coordinator",
            "start_line": helper_start,
            "end_line": helper_end,
            "line_count": helper_end - helper_start + 1,
        },
        "post_selection_scope_builder_segment": {
            "function": "_build_one_click_solver_iteration_candidate_flow_post_selection_scope_coordinator",
            "start_line": scope_builder_start,
            "end_line": scope_builder_end,
            "line_count": scope_builder_end - scope_builder_start + 1,
        },
        "post_selection_shear_fields_builder_segment": {
            "function": "_build_one_click_solver_iteration_candidate_flow_post_selection_shear_fields_coordinator",
            "start_line": shear_fields_start,
            "end_line": shear_fields_end,
            "line_count": shear_fields_end - shear_fields_start + 1,
        },
        "pre_selection_segment": {
            "function": "_run_one_click_solver_iteration_pre_selection_candidate_evaluation_coordinator",
            "start_line": pre_selection_start,
            "end_line": pre_selection_end,
            "line_count": pre_selection_end - pre_selection_start + 1,
        },
        "post_selection_segment": {
            "function": "_run_one_click_solver_iteration_post_selection_acceptance_flow_coordinator",
            "start_line": post_selection_start,
            "end_line": post_selection_end,
            "line_count": post_selection_end - post_selection_start + 1,
        },
        "loop_segment": {
            "function": "_run_one_click_solver_iteration_loop_coordinator",
            "start_line": loop_start,
            "end_line": loop_end,
            "line_count": loop_end - loop_start + 1,
        },
        "static_checks": static_checks,
        "runtime_checks": runtime_checks,
        "runtime": {
            "accepted": accepted_runtime,
            "selection_stop": selection_stop_runtime,
        },
    }


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    payload = build_payload()
    stamp = _dt.datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    json_path = ARTIFACT_DIR / (
        f"inputs_page_solver_iteration_candidate_flow_coordinator_extraction_{stamp}.json"
    )
    md_path = AUDIT_DIR / (
        f"inputs_page_solver_iteration_candidate_flow_coordinator_extraction_{stamp}.md"
    )
    json_path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    lines = [
        "# Inputs Page Solver Iteration Candidate Flow Coordinator Extraction",
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
            f"- Post-selection scope builder lines: {payload['post_selection_scope_builder_segment']['line_count']}",
            f"- Post-selection helper lines: {payload['post_selection_segment']['line_count']}",
            f"- Loop lines: {payload['loop_segment']['line_count']}",
        ]
    )
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"status={payload['status']}")
    print(f"json={json_path}")
    print(f"md={md_path}")
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
