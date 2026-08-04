"""Verify scored-candidate fallback and selection coordinator extraction."""

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

    def _fallback(**kwargs: Any) -> dict[str, Any]:
        calls.append(
            {
                "helper": "fallback",
                "raw_n": kwargs["raw_n"],
                "scored_count": len(kwargs["scored"]),
            }
        )
        next_scored = list(kwargs["scored"])
        next_scored.append({"title": "Fallback"})
        return {
            "scored": next_scored,
            "fallback_next_hop_injected": True,
            "fallback_next_hop_reason": "next_hop",
        }

    def _selection(**kwargs: Any) -> dict[str, Any]:
        calls.append(
            {
                "helper": "selection",
                "scored_count": len(kwargs["scored"]),
                "no_actionable": kwargs["no_actionable_after_full_tightening_search"],
            }
        )
        return {
            "no_actionable_after_full_tightening_search": True,
            "best": {"title": "Best"},
            "best_distance_to_band_this_iteration": 0.023,
            "should_break": True,
            "stop_reason": "no_actionable_candidates",
            "status": "partial",
            "final_distance_to_band": 0.19,
        }

    originals = _patch(
        module,
        {
            "_handle_one_click_solver_candidate_fallback_pool_trace_coordinator": _fallback,
            "_handle_one_click_solver_candidate_selection_or_stop_coordinator": _selection,
        },
    )
    try:
        returned = module._resolve_one_click_solver_scored_candidate_selection_state_coordinator(
            scored=[{"title": "Scored"}],
            cur_eval={"overview": {}},
            working={"D": 600},
            mode_config=None,
            tightening_mode_active=True,
            step_idx=3,
            raw_n=7,
            pool_labels=["A"],
            governing_domain="bending",
            tightening_meta={"active": True},
            material_improvement_threshold=0.01,
            reduction_candidates_considered=2,
            growth_candidates_rejected_in_tightening=1,
            rejected_as_non_governing_cleanup=0,
            rejected_as_non_governing_shear_strengthening=0,
            rejected_as_non_material_improvement=0,
            tightening_step_count=2,
            max_tightening_steps=8,
            no_actionable_after_full_tightening_search=False,
            candidate_family_depth_reached=True,
            shear_governing_mode_active=False,
            shear_severity_band=None,
            shear_candidate_family_order=[],
            spacing_candidates_considered=False,
            leg_candidates_considered=False,
            dia_candidates_considered=False,
            geometry_candidates_considered_for_shear=False,
            combined_candidates_considered_for_shear=False,
            web_crushing_penalty_applied=0,
            rejected_as_spacing_too_weak=0,
            rejected_as_web_crushing_marginal=0,
            rejected_as_impractical_shear_layout=0,
            shear_governing_family_detected=False,
            governing_family_exists_after_domain_fix=True,
            pruned_non_shear_family_count=0,
            domain_match_prune_used=False,
            shear_prune_rule_source=None,
            cur_pass=False,
            step_trace=[],
            initial_snapshot={},
            cur_ib=False,
            winning_label=None,
            winning_action_type=None,
            in_band_shear_cleanup_deferral=False,
            trace_callback=lambda *_args, **_kwargs: None,
        )
    finally:
        _restore(module, originals)

    return {"calls": calls, "returned": returned}


def build_payload() -> dict[str, Any]:
    source = _read(AUTO_DESIGN_COMPUTE)
    helper_start, helper_end, helper = _function_segment(
        source,
        "_resolve_one_click_solver_scored_candidate_selection_state_coordinator",
    )
    _, _, fallback_dispatch = _function_segment(
        source,
        "_dispatch_one_click_solver_candidate_fallback_pool_trace_from_selection_coordinator",
    )
    _, _, fallback_unpack = _function_segment(
        source,
        "_unpack_one_click_solver_candidate_fallback_pool_trace_state_coordinator",
    )
    _, _, result_helper = _function_segment(
        source,
        "_build_one_click_solver_scored_candidate_selection_state_result_coordinator",
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
    _, _, post_selection_selection_dispatch = _function_segment(
        source, "_dispatch_one_click_solver_post_selection_candidate_selection_state_coordinator"
    )
    _, _, selection_stop_packer = _function_segment(
        source, "_build_one_click_solver_selection_stop_iteration_state_coordinator"
    )
    solve_start, solve_end, solve_body = _function_segment(source, "_solve_one_click_to_target")

    import inputs_page_modules.auto_design_compute as module  # noqa: E402

    runtime = _run_case(module)
    runtime_checks = {
        "fallback_runs_before_selection_with_scored_handoff": runtime["calls"]
        == [
            {"helper": "fallback", "raw_n": 7, "scored_count": 1},
            {"helper": "selection", "scored_count": 2, "no_actionable": False},
        ],
        "selection_state_and_fallback_metadata_propagate": runtime["returned"]
        == {
            "scored": [{"title": "Scored"}, {"title": "Fallback"}],
            "fallback_next_hop_injected": True,
            "fallback_next_hop_reason": "next_hop",
            "no_actionable_after_full_tightening_search": True,
            "best": {"title": "Best"},
            "best_distance_to_band_this_iteration": 0.023,
            "should_break": True,
            "stop_reason": "no_actionable_candidates",
            "status": "partial",
            "final_distance_to_band": 0.19,
        },
    }
    static_checks = {
        "helper_present": (
            "def _resolve_one_click_solver_scored_candidate_selection_state_coordinator(" in source
        ),
        "helper_delegates_fallback_before_selection": (
            "_dispatch_one_click_solver_candidate_fallback_pool_trace_from_selection_coordinator("
            in helper
            and "_handle_one_click_solver_candidate_selection_or_stop_coordinator(" in helper
            and "_handle_one_click_solver_candidate_fallback_pool_trace_coordinator("
            in fallback_dispatch
            and helper.index(
                "_dispatch_one_click_solver_candidate_fallback_pool_trace_from_selection_coordinator("
            )
            < helper.index("_handle_one_click_solver_candidate_selection_or_stop_coordinator(")
        ),
        "helper_preserves_fallback_metadata": (
            'candidate_fallback_pool_trace_state["fallback_next_hop_injected"]'
            in fallback_unpack
            and '"fallback_next_hop_injected": fallback_next_hop_injected'
            in result_helper
            and '"fallback_next_hop_reason": fallback_next_hop_reason'
            in result_helper
        ),
        "helper_returns_selection_state": all(
            token in result_helper
            for token in (
                '"no_actionable_after_full_tightening_search": candidate_selection_or_stop_state[',
                '"best": candidate_selection_or_stop_state["best"]',
                '"best_distance_to_band_this_iteration": candidate_selection_or_stop_state[',
                '"should_break": candidate_selection_or_stop_state["should_break"]',
                '"final_distance_to_band": candidate_selection_or_stop_state[',
            )
        ),
        "post_selection_delegates_scored_candidate_selection_dispatch": (
            "_dispatch_one_click_solver_post_selection_candidate_selection_state_coordinator("
            in post_selection_body
        ),
        "post_selection_selection_dispatch_delegates_scored_candidate_selection_state": (
            "_resolve_one_click_solver_scored_candidate_selection_state_coordinator("
            in post_selection_selection_dispatch
        ),
        "post_selection_rehydrates_selection_state": all(
            token in post_selection_body
            for token in (
                'no_actionable_after_full_tightening_search = scored_candidate_selection_state[',
                'best = scored_candidate_selection_state["best"]',
                'best_distance_to_band_this_iteration = scored_candidate_selection_state[',
                'if scored_candidate_selection_state["should_break"]:',
            )
        ),
        "post_selection_delegates_selection_stop_packer": (
            "_build_one_click_solver_selection_stop_iteration_state_coordinator(" in post_selection_body
        ),
        "selection_stop_packer_preserves_selection_stop_fields": all(
            token in selection_stop_packer
            for token in (
                '"final_distance_to_band": scored_candidate_selection_state[',
                '"stop_reason": scored_candidate_selection_state["stop_reason"]',
                '"status": scored_candidate_selection_state["status"]',
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
        "loop_no_longer_calls_scored_candidate_selection_directly": (
            "_resolve_one_click_solver_scored_candidate_selection_state_coordinator(" not in loop_body
        ),
        "solver_delegates_iteration_loop": "_dispatch_one_click_solver_iteration_loop_from_solver_runtime_setup_coordinator(" in solve_body,
        "solver_no_longer_calls_scored_candidate_selection_directly": (
            "_resolve_one_click_solver_scored_candidate_selection_state_coordinator(" not in solve_body
        ),
        "solver_no_longer_owns_fallback_or_selection_directly": (
            "_handle_one_click_solver_candidate_fallback_pool_trace_coordinator(" not in solve_body
            and "_handle_one_click_solver_candidate_selection_or_stop_coordinator(" not in solve_body
        ),
    }
    status = "PASS"
    if not all(static_checks.values()) or not all(runtime_checks.values()):
        status = "FAIL"
    return {
        "status": status,
        "surface": "_solve_one_click_to_target_scored_candidate_selection_state_coordinator",
        "helper_segment": {
            "function": "_resolve_one_click_solver_scored_candidate_selection_state_coordinator",
            "start_line": helper_start,
            "end_line": helper_end,
            "line_count": helper_end - helper_start + 1,
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
        "runtime": runtime,
        "product_behavior_changed": False,
        "next_safe_slice": "audit remaining accepted-candidate and finalization handoff surfaces",
    }


def write_artifacts(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now().isoformat(timespec="seconds").replace(":", "-")
    json_path = ARTIFACT_DIR / (
        f"inputs_page_solver_scored_candidate_selection_state_coordinator_extraction_{stamp}.json"
    )
    md_path = AUDIT_DIR / (
        f"inputs_page_solver_scored_candidate_selection_state_coordinator_extraction_{stamp}.md"
    )
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Solver Scored Candidate Selection State Coordinator Extraction",
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
