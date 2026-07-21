"""Verify post-step metrics and trace solver coordinator extraction."""

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


def _run_case(module: Any, *, shear: bool, spacing_fail: bool, still_under: bool) -> dict[str, Any]:
    originals = {
        "_one_click_has_unresolved_spacing_envelope_fail": getattr(
            module,
            "_one_click_has_unresolved_spacing_envelope_fail",
            _MISSING,
        ),
        "_one_click_still_materially_under_target": getattr(
            module,
            "_one_click_still_materially_under_target",
            _MISSING,
        ),
        "_candidate_target_band_distance": getattr(module, "_candidate_target_band_distance", _MISSING),
        "_evaluate_shear_with_state": getattr(module, "_evaluate_shear_with_state", _MISSING),
        "_trace_post_step_solver_iteration_coordinator": module._trace_post_step_solver_iteration_coordinator,
    }
    trace_calls: list[dict[str, Any]] = []

    def _trace_post_step(**kwargs: Any) -> None:
        trace_calls.append(dict(kwargs))

    try:
        module._one_click_has_unresolved_spacing_envelope_fail = lambda w_gate_eval: spacing_fail
        module._one_click_still_materially_under_target = lambda w_gate_eval, mode_config, margin: still_under
        module._candidate_target_band_distance = lambda w_gate_eval, mode_config: 0.04
        module._evaluate_shear_with_state = (
            lambda state: {"util": 0.88, "web_util": 0.62}
            if shear
            else {"util": 9.99, "web_util": 9.99}
        )
        module._trace_post_step_solver_iteration_coordinator = _trace_post_step
        returned = module._handle_one_click_solver_post_step_metrics_and_trace_coordinator(
            w_gate_eval={"overview": {"all_key_pass": True}, "state": {"D": 620}},
            working={"D": 620},
            mode_config={"target": "band"},
            step_idx=3,
            governing_domain="shear" if shear else "bending",
            tightening_mode_active=True,
            tightening_step_count=2,
            max_tightening_steps=4,
            winning_label="Winner",
            winning_action_type="tighten",
            no_actionable_after_full_tightening_search=False,
            candidate_family_depth_reached="combined",
            best_distance_to_band_this_iteration=0.11,
            shear_governing_mode_active=True,
            shear_severity_band="high",
            shear_candidate_family_order=["spacing", "legs"],
            spacing_candidates_considered=5,
            leg_candidates_considered=4,
            dia_candidates_considered=3,
            geometry_candidates_considered_for_shear=2,
            combined_candidates_considered_for_shear=1,
            web_crushing_penalty_applied=1,
            rejected_as_spacing_too_weak=2,
            rejected_as_web_crushing_marginal=3,
            rejected_as_impractical_shear_layout=4,
            final_resolved_shear_util=0.5,
            final_resolved_web_util=0.4,
            shear_governing_family_detected=True,
            governing_family_exists_after_domain_fix=True,
            pruned_non_shear_family_count=6,
            trace_callback=lambda ev, dat: None,
        )
    finally:
        for attr, original in originals.items():
            if original is _MISSING:
                delattr(module, attr)
            else:
                setattr(module, attr, original)

    expected_continuing = bool(still_under)
    expected_shear_util = 0.88 if shear else 0.5
    expected_web_util = 0.62 if shear else 0.4
    return {
        "returned": returned,
        "trace_calls": trace_calls,
        "matches": (
            returned["w_pass"] is True
            and returned["unresolved_spacing_fail_after_step"] is (spacing_fail if shear else False)
            and returned["still_under_after_step"] is still_under
            and returned["continuing_tightening_after_step"] is expected_continuing
            and returned["final_distance_to_band"] == 0.04
            and returned["final_resolved_shear_util"] == expected_shear_util
            and returned["final_resolved_web_util"] == expected_web_util
            and len(trace_calls) == 1
            and trace_calls[0]["continuing_tightening_after_step"] is expected_continuing
            and trace_calls[0]["final_distance_to_band"] == 0.04
            and trace_calls[0]["final_resolved_shear_util"] == expected_shear_util
        ),
    }


def build_payload() -> dict[str, Any]:
    source = _read(AUTO_DESIGN_COMPUTE)
    helper_start, helper_end, helper = _function_segment(
        source,
        "_handle_one_click_solver_post_step_metrics_and_trace_coordinator",
    )
    aggregate_start, aggregate_end, aggregate = _function_segment(
        source,
        "_handle_one_click_solver_accepted_candidate_post_step_coordinator",
    )
    _, _, accepted_post_step_metrics_dispatch = _function_segment(
        source,
        "_dispatch_one_click_solver_post_step_metrics_and_trace_from_accepted_post_step_coordinator",
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
        "shear_continuing": _run_case(module, shear=True, spacing_fail=False, still_under=True)["matches"],
        "shear_spacing_fail_blocks_continuation": _run_case(
            module,
            shear=True,
            spacing_fail=True,
            still_under=True,
        )["matches"],
        "non_shear_preserves_existing_shear_util_defaults": _run_case(
            module,
            shear=False,
            spacing_fail=True,
            still_under=False,
        )["matches"],
    }
    static_checks = {
        "helper_present": "def _handle_one_click_solver_post_step_metrics_and_trace_coordinator(" in source,
        "helper_computes_w_pass": 'w_pass = bool((w_gate_eval.get("overview") or {}).get("all_key_pass"))' in helper,
        "helper_checks_unresolved_spacing": "_one_click_has_unresolved_spacing_envelope_fail(w_gate_eval)" in helper,
        "helper_checks_materially_under_target": "_one_click_still_materially_under_target(w_gate_eval, mode_config, margin=0.03)" in helper,
        "helper_computes_continuing_tightening": "continuing_tightening_after_step = bool(" in helper,
        "helper_computes_final_distance": "_candidate_target_band_distance(w_gate_eval, mode_config)" in helper,
        "helper_re_evaluates_shear_only": 'if governing_domain == "shear" else None' in helper,
        "helper_delegates_post_step_trace": "_trace_post_step_solver_iteration_coordinator(" in helper,
        "aggregate_delegates_post_step_metrics": (
            "_dispatch_one_click_solver_post_step_metrics_and_trace_from_accepted_post_step_coordinator("
            in aggregate
            and "_handle_one_click_solver_post_step_metrics_and_trace_coordinator("
            in accepted_post_step_metrics_dispatch
            and "accepted_post_step_scope[" in accepted_post_step_metrics_dispatch
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
        "result_packer_rehydrates_returned_fields": all(
            token in aggregate_result_packer
            for token in (
                '"w_pass": post_step_metrics_state["w_pass"]',
                '"unresolved_spacing_fail_after_step": post_step_metrics_state[',
                '"still_under_after_step": post_step_metrics_state["still_under_after_step"]',
                '"continuing_tightening_after_step": post_step_metrics_state[',
                '"final_distance_to_band": post_step_metrics_state["final_distance_to_band"]',
                '"final_resolved_shear_util": post_step_metrics_state["final_resolved_shear_util"]',
                '"final_resolved_web_util": post_step_metrics_state["final_resolved_web_util"]',
            )
        ),
    }
    status = "PASS"
    if not all(static_checks.values()) or not all(runtime.values()):
        status = "FAIL"
    return {
        "status": status,
        "surface": "_solve_one_click_to_target_post_step_metrics_and_trace_coordinator",
        "helper_segment": {
            "function": "_handle_one_click_solver_post_step_metrics_and_trace_coordinator",
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
        "next_safe_slice": "extract post-step target-band stop gate and rescue-prep boundary",
    }


def write_artifacts(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now().isoformat(timespec="seconds").replace(":", "-")
    json_path = ARTIFACT_DIR / f"inputs_page_solver_post_step_metrics_and_trace_coordinator_extraction_{stamp}.json"
    md_path = AUDIT_DIR / f"inputs_page_solver_post_step_metrics_and_trace_coordinator_extraction_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Solver Post-Step Metrics And Trace Coordinator Extraction",
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
