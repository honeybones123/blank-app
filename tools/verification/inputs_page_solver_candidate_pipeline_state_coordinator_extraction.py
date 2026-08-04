"""Verify one-click solver candidate pipeline state coordinator extraction."""

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
        if isinstance(node, ast.FunctionDef) and node.name == name:
            start = int(node.lineno)
            end = int(getattr(node, "end_lineno", node.lineno))
            lines = source.splitlines()
            return start, end, "\n".join(lines[start - 1 : end])
    raise AssertionError(f"Function not found: {name}")


def _patch(module: Any, replacements: dict[str, Any]) -> dict[str, Any]:
    originals = {name: getattr(module, name, _MISSING) for name in replacements}
    for name, value in replacements.items():
        setattr(module, name, value)
    return originals


def _restore(module: Any, originals: dict[str, Any]) -> None:
    for name, original in originals.items():
        if original is _MISSING:
            delattr(module, name)
        else:
            setattr(module, name, original)


def _run_case(module: Any) -> dict[str, Any]:
    calls: list[dict[str, Any]] = []

    def _collection(**kwargs: Any) -> dict[str, Any]:
        calls.append({"helper": "collection", "step_idx": kwargs["step_idx"]})
        return {
            "raw_candidates": [{"title": "raw"}],
            "raw_n": 3,
            "use_governing_domain_candidates": True,
            "tightening_meta": {"collected": True},
            "candidate_family_depth_reached": True,
            "shear_governing_mode_active": False,
            "shear_severity_band": "low",
            "shear_candidate_family_order": ["spacing"],
            "spacing_candidates_considered": True,
            "leg_candidates_considered": False,
            "dia_candidates_considered": False,
            "geometry_candidates_considered_for_shear": True,
            "combined_candidates_considered_for_shear": False,
        }

    def _prepared(**kwargs: Any) -> dict[str, Any]:
        calls.append(
            {
                "helper": "prepared",
                "raw_n": len(kwargs["raw_candidates"]),
                "use_governing": kwargs["use_governing_domain_candidates"],
            }
        )
        return {
            "pool_labels": ["Depth"],
            "prepared": [{"rc": {"title": "Depth"}, "raw_u": {}, "norm_u": {}, "direction": {}}],
            "prepared_samples": [{"title": "Depth"}],
            "reduction_candidates_considered": 4,
            "governing_family_exists": True,
            "shear_governing_family_detected": False,
            "governing_family_exists_after_domain_fix": True,
            "shear_domain_prune_active": False,
            "should_apply_domain_prune": True,
            "mixed_direction_mode": "mixed",
            "growth_candidates_rejected_in_tightening": 1,
            "rejected_as_non_governing_cleanup": 2,
            "rejected_as_non_governing_shear_strengthening": 3,
            "rejected_as_non_material_improvement": 4,
            "rejected_as_no_real_change": 5,
            "rejected_as_duplicate_signature": 6,
            "rejected_as_evaluation_failed": 7,
        }

    def _pre_scoring(**kwargs: Any) -> dict[str, Any]:
        calls.append(
            {
                "helper": "pre_scoring",
                "prepared_n": len(kwargs["prepared"]),
                "apply_domain_prune": kwargs["should_apply_domain_prune"],
            }
        )
        return {
            "rejected_as_no_real_change": kwargs["rejected_as_no_real_change"] + 10,
            "shear_remove_links_candidate_seen": True,
            "shear_remove_links_candidate_dropped_reason": "pre_scoring",
            "rejected_as_non_governing_cleanup": kwargs["rejected_as_non_governing_cleanup"] + 11,
            "pruned_non_shear_family_count": kwargs["pruned_non_shear_family_count"] + 12,
            "domain_match_prune_used": True,
            "shear_prune_rule_source": "domain_matcher",
            "growth_candidates_rejected_in_tightening": kwargs["growth_candidates_rejected_in_tightening"] + 13,
        }

    def _scoring_start(**kwargs: Any) -> dict[str, Any]:
        calls.append(
            {
                "helper": "scoring_start",
                "cur_sig": list(kwargs["cur_sig"]),
                "domain_match": kwargs["domain_match_prune_used"],
            }
        )
        return {
            "shear_prune_rule_source": "domain_matcher",
            "cur_has_td": True,
            "cur_required_fail_count": 1,
            "cur_required_unsatisfied_count": 2,
            "scored": [],
        }

    originals = _patch(
        module,
        {
            "_prepare_one_click_solver_candidate_collection_state_coordinator": _collection,
            "_prepare_one_click_solver_prepared_candidate_loop_state_coordinator": _prepared,
            "_run_one_click_solver_pre_scoring_prune_pass_coordinator": _pre_scoring,
            "_prepare_one_click_solver_iteration_scoring_start_state_coordinator": _scoring_start,
        },
    )
    try:
        returned = module._prepare_one_click_solver_candidate_pipeline_state_coordinator(
            working={"D": 600},
            debug_enabled=False,
            trace_run_id="rid",
            step_idx=2,
            tightening_mode_active=True,
            governing_domain_failing=True,
            required_domain_work_active=True,
            target_band_domain="bending",
            cur_shear_failing=False,
            governing_domain="bending",
            cur_ib=False,
            cur_eval={"overview": {}},
            mode_config=None,
            tightening_step_count=1,
            tightening_meta={"initial": True},
            candidate_family_depth_reached=False,
            shear_governing_mode_active=False,
            shear_severity_band=None,
            shear_candidate_family_order=[],
            spacing_candidates_considered=False,
            leg_candidates_considered=False,
            dia_candidates_considered=False,
            geometry_candidates_considered_for_shear=False,
            combined_candidates_considered_for_shear=False,
            cur_sig=("sig",),
            t_lo=0.85,
            t_hi=0.95,
            max_tightening_steps=8,
            no_actionable_after_full_tightening_search=False,
            target_domains_for_band=["bending"],
            shear_governing_family_detected=False,
            governing_family_exists_after_domain_fix=False,
            pruned_non_shear_family_count=1,
            domain_match_prune_used=False,
            shear_prune_rule_source=None,
            material_improvement_threshold=0.01,
            rejected_as_non_governing_cleanup=0,
            rejected_as_non_governing_shear_strengthening=0,
            shear_remove_links_candidate_seen=False,
            shear_remove_links_candidate_dropped_reason=None,
            trace_callback=lambda *_args, **_kwargs: None,
        )
    finally:
        _restore(module, originals)
    return {"calls": calls, "returned": returned}


def build_payload() -> dict[str, Any]:
    source = _read(AUTO_DESIGN_COMPUTE)
    helper_start, helper_end, helper = _function_segment(
        source,
        "_prepare_one_click_solver_candidate_pipeline_state_coordinator",
    )
    _, _, after_collection_helper = _function_segment(
        source,
        "_run_one_click_solver_candidate_pipeline_after_collection_coordinator",
    )
    collection_dispatch_start, collection_dispatch_end, collection_dispatch = _function_segment(
        source,
        "_dispatch_one_click_solver_candidate_collection_state_from_candidate_pipeline_coordinator",
    )
    result_helper_start, result_helper_end, result_helper = _function_segment(
        source,
        "_build_one_click_solver_candidate_pipeline_result_state_coordinator",
    )
    pre_scoring_start, pre_scoring_end, pre_scoring_body = _function_segment(
        source,
        "_prepare_one_click_solver_candidate_pipeline_pre_scoring_state_coordinator",
    )
    loop_start, loop_end, loop_body = _function_segment(
        source,
        "_run_one_click_solver_iteration_loop_coordinator",
    )
    _, _, loop_candidate_flow_dispatch = _function_segment(
        source,
        "_dispatch_one_click_solver_iteration_candidate_flow_from_iteration_loop_coordinator",
    )
    flow_start, flow_end, flow_body = _function_segment(
        source,
        "_run_one_click_solver_iteration_candidate_flow_coordinator",
    )
    pre_selection_start, pre_selection_end, pre_selection_body = _function_segment(
        source,
        "_run_one_click_solver_iteration_pre_selection_candidate_evaluation_coordinator",
    )
    _, _, pre_selection_pipeline_and_scoring_body = _function_segment(
        source,
        "_run_one_click_solver_pre_selection_candidate_pipeline_and_scoring_coordinator",
    )
    _, _, pre_selection_pipeline_dispatch_body = _function_segment(
        source,
        "_dispatch_one_click_solver_candidate_pipeline_state_from_pre_selection_coordinator",
    )
    solve_start, solve_end, solve_body = _function_segment(source, "_solve_one_click_to_target")

    import inputs_page_modules.auto_design_compute as module  # noqa: E402

    runtime = _run_case(module)
    runtime_checks = {
        "pipeline_order_preserved": runtime["calls"]
        == [
            {"helper": "collection", "step_idx": 2},
            {"helper": "prepared", "raw_n": 1, "use_governing": True},
            {"helper": "pre_scoring", "prepared_n": 1, "apply_domain_prune": True},
            {"helper": "scoring_start", "cur_sig": ["sig"], "domain_match": True},
        ],
        "pipeline_state_propagates": (
            runtime["returned"]["raw_n"] == 3
            and runtime["returned"]["pool_labels"] == ["Depth"]
            and runtime["returned"]["rejected_as_no_real_change"] == 15
            and runtime["returned"]["rejected_as_non_governing_cleanup"] == 13
            and runtime["returned"]["pruned_non_shear_family_count"] == 13
            and runtime["returned"]["growth_candidates_rejected_in_tightening"] == 14
            and runtime["returned"]["cur_has_td"] is True
            and runtime["returned"]["cur_required_fail_count"] == 1
            and runtime["returned"]["scored"] == []
        ),
    }
    pipeline_ordered_tokens = [
        "_dispatch_one_click_solver_candidate_collection_state_from_candidate_pipeline_coordinator(",
        "_prepare_one_click_solver_candidate_pipeline_pre_scoring_state_coordinator(",
        "_prepare_one_click_solver_iteration_scoring_start_state_coordinator(",
    ]
    pre_scoring_ordered_tokens = [
        "_prepare_one_click_solver_prepared_candidate_loop_state_coordinator(",
        "_run_one_click_solver_pre_scoring_prune_pass_coordinator(",
    ]
    static_checks = {
        "helper_present": "def _prepare_one_click_solver_candidate_pipeline_state_coordinator(" in source,
        "helper_preserves_pipeline_order": (
            pipeline_ordered_tokens[0] in helper
            and all(token in after_collection_helper for token in pipeline_ordered_tokens[1:])
            and [
                after_collection_helper.index(token)
                for token in pipeline_ordered_tokens[1:]
            ]
            == sorted(
                after_collection_helper.index(token)
                for token in pipeline_ordered_tokens[1:]
            )
        ),
        "collection_dispatch_delegates_candidate_collection_state": (
            "_prepare_one_click_solver_candidate_collection_state_coordinator("
            in collection_dispatch
            and "candidate_pipeline_scope[" in collection_dispatch
        ),
        "pre_scoring_helper_preserves_subgate_order": all(
            token in pre_scoring_body for token in pre_scoring_ordered_tokens
        )
        and [pre_scoring_body.index(token) for token in pre_scoring_ordered_tokens]
        == sorted(pre_scoring_body.index(token) for token in pre_scoring_ordered_tokens),
        "helper_delegates_result_state_packing": (
            "_build_one_click_solver_candidate_pipeline_result_state_coordinator("
            in after_collection_helper
            and "candidate_pipeline_scope=candidate_pipeline_after_collection_scope"
            in after_collection_helper
        ),
        "result_helper_returns_scoring_loop_inputs": all(
            token in result_helper
            for token in (
                '"raw_n": candidate_pipeline_scope["raw_n"]',
                '"pool_labels": candidate_pipeline_scope["pool_labels"]',
                '"prepared": candidate_pipeline_scope["prepared"]',
                '"mixed_direction_mode": candidate_pipeline_scope["mixed_direction_mode"]',
                '"rejected_as_duplicate_signature": candidate_pipeline_scope[',
                '"cur_required_unsatisfied_count": candidate_pipeline_scope[',
                '"scored": candidate_pipeline_scope["scored"]',
            )
        ),
        "pre_selection_delegates_candidate_pipeline_dispatch": (
            "_run_one_click_solver_pre_selection_candidate_pipeline_and_scoring_coordinator("
            in pre_selection_body
        ),
        "pre_selection_pipeline_and_scoring_delegates_candidate_pipeline_dispatch": (
            "_dispatch_one_click_solver_candidate_pipeline_state_from_pre_selection_coordinator("
            in pre_selection_pipeline_and_scoring_body
        ),
        "pre_selection_pipeline_dispatch_delegates_candidate_pipeline_state": (
            "_prepare_one_click_solver_candidate_pipeline_state_coordinator("
            in pre_selection_pipeline_dispatch_body
            and "pre_selection_scope[" in pre_selection_pipeline_dispatch_body
        ),
        "pre_selection_rehydrates_candidate_pipeline_state": all(
            token in pre_selection_pipeline_and_scoring_body
            for token in (
                "candidate_pipeline_state = (",
                "pre_selection_scope.update(candidate_pipeline_state)",
                "_dispatch_one_click_solver_candidate_scoring_loop_from_pre_selection_coordinator(",
            )
        ),
        "flow_delegates_pre_selection": (
            "_run_one_click_solver_iteration_pre_selection_candidate_evaluation_coordinator(" in flow_body
        ),
        "flow_no_longer_calls_candidate_pipeline_directly": (
            "_prepare_one_click_solver_candidate_pipeline_state_coordinator(" not in flow_body
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
        "loop_no_longer_calls_candidate_pipeline_directly": (
            "_prepare_one_click_solver_candidate_pipeline_state_coordinator(" not in loop_body
        ),
        "solver_delegates_iteration_loop": "_dispatch_one_click_solver_iteration_loop_from_solver_runtime_setup_coordinator(" in solve_body,
        "solver_no_longer_calls_candidate_pipeline_directly": (
            "_prepare_one_click_solver_candidate_pipeline_state_coordinator(" not in solve_body
        ),
        "solver_no_longer_owns_candidate_pipeline_subgates": all(
            token not in solve_body for token in pipeline_ordered_tokens + pre_scoring_ordered_tokens
        ),
    }
    status = "PASS"
    if not all(static_checks.values()) or not all(runtime_checks.values()):
        status = "FAIL"
    return {
        "status": status,
        "surface": "_solve_one_click_to_target_candidate_pipeline_state_coordinator",
        "helper_segment": {
            "function": "_prepare_one_click_solver_candidate_pipeline_state_coordinator",
            "start_line": helper_start,
            "end_line": helper_end,
            "line_count": helper_end - helper_start + 1,
        },
        "result_helper_segment": {
            "function": "_build_one_click_solver_candidate_pipeline_result_state_coordinator",
            "start_line": result_helper_start,
            "end_line": result_helper_end,
            "line_count": result_helper_end - result_helper_start + 1,
        },
        "collection_dispatch_segment": {
            "function": "_dispatch_one_click_solver_candidate_collection_state_from_candidate_pipeline_coordinator",
            "start_line": collection_dispatch_start,
            "end_line": collection_dispatch_end,
            "line_count": collection_dispatch_end - collection_dispatch_start + 1,
        },
        "pre_scoring_segment": {
            "function": "_prepare_one_click_solver_candidate_pipeline_pre_scoring_state_coordinator",
            "start_line": pre_scoring_start,
            "end_line": pre_scoring_end,
            "line_count": pre_scoring_end - pre_scoring_start + 1,
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
        "flow_segment": {
            "function": "_run_one_click_solver_iteration_candidate_flow_coordinator",
            "start_line": flow_start,
            "end_line": flow_end,
            "line_count": flow_end - flow_start + 1,
        },
        "pre_selection_segment": {
            "function": "_run_one_click_solver_iteration_pre_selection_candidate_evaluation_coordinator",
            "start_line": pre_selection_start,
            "end_line": pre_selection_end,
            "line_count": pre_selection_end - pre_selection_start + 1,
        },
        "static_checks": static_checks,
        "runtime_checks": runtime_checks,
        "runtime": runtime,
        "product_behavior_changed": False,
        "next_safe_slice": "audit remaining scoring-loop/selection/post-step solver handoff",
    }


def write_artifacts(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now().isoformat(timespec="seconds").replace(":", "-")
    json_path = ARTIFACT_DIR / (
        f"inputs_page_solver_candidate_pipeline_state_coordinator_extraction_{stamp}.json"
    )
    md_path = AUDIT_DIR / (
        f"inputs_page_solver_candidate_pipeline_state_coordinator_extraction_{stamp}.md"
    )
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Solver Candidate Pipeline State Coordinator Extraction",
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
            "## Segments",
            f"- Helper lines: `{payload['helper_segment']['line_count']}`",
            f"- Result helper lines: `{payload['result_helper_segment']['line_count']}`",
            f"- Solver lines: `{payload['solver_segment']['line_count']}`",
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
    print(f"status={payload['status']}")
    print(f"json={json_path}")
    print(f"md={md_path}")
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
