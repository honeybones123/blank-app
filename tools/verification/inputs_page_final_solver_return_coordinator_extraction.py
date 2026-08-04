"""Verify final solver return coordinator extraction."""

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
    original_coherence = getattr(module, "_coherence_debug_fields", None)
    original_trace_eval = getattr(module, "_one_click_trace_eval_domain_payload", None)

    def _fake_coherence(initial_coherence: dict) -> dict[str, Any]:
        return {"coherence_probe": initial_coherence.get("probe")}

    def _fake_trace_eval(final_eval: dict, mode_config: dict) -> dict[str, Any]:
        return {"band_probe": [final_eval.get("probe"), mode_config.get("mode")]}

    try:
        module._coherence_debug_fields = _fake_coherence
        module._one_click_trace_eval_domain_payload = _fake_trace_eval
        result = module._build_final_solver_return_coordinator(
            step_trace=[{"label": "A"}, {"label": ""}],
            init_worst=0.45,
            final_worst=0.88,
            t_lo=0.8,
            t_hi=0.95,
            stop_reason="max_steps",
            final_in_band=True,
            final_pass=True,
            status="ok",
            rid="rid-1",
            initial_coherence={"probe": "coherent"},
            tightening_step_count=2,
            max_tightening_steps=4,
            no_actionable_after_full_tightening_search=False,
            candidate_family_depth_reached="depth",
            final_distance_to_band=0.01,
            shear_governing_mode_active=True,
            shear_severity_band="medium",
            shear_candidate_family_order=("spacing", "legs"),
            spacing_candidates_considered=3,
            leg_candidates_considered=4,
            dia_candidates_considered=5,
            geometry_candidates_considered_for_shear=6,
            combined_candidates_considered_for_shear=7,
            web_crushing_penalty_applied=8,
            rejected_as_spacing_too_weak=9,
            rejected_as_web_crushing_marginal=10,
            rejected_as_impractical_shear_layout=11,
            final_resolved_shear_util=0.71,
            final_resolved_web_util=0.62,
            shear_governing_family_detected=True,
            governing_family_exists_after_domain_fix=False,
            pruned_non_shear_family_count=12,
            final_governing_domain="shear",
            rejected_as_non_governing_cleanup=13,
            rejected_as_non_governing_shear_strengthening=14,
            target_band_domain="combined",
            target_domains_for_band=("bending", "shear"),
            final_target_domains=("shear",),
            final_eval={"state": {"D": 700}, "probe": "eval"},
            mode_config={"mode": "tight"},
            step_committable_eval_trace=({"step": 1},),
            final_eval_internal_worst_util_dbg=0.86,
            final_eval_committable_worst_util_dbg=0.87,
            final_eval_used_source_dbg="committable",
            final_eval_committable_updates_dbg={"D": 700},
            final_objective_util=0.88,
            shear_remove_links_candidate_seen=True,
            shear_remove_links_candidate_truth_ok=False,
            shear_remove_links_candidate_dropped_reason="truth",
            shear_remove_links_candidate_materiality=0.02,
            early_in_band_exit_blocked_for_tightening=True,
            early_in_band_exit_tightening_classification="tighten",
            early_in_band_exit_available_tightening_paths=("path",),
            early_in_band_exit_reason="continue",
            partial_failing_final_updates_blocked=False,
            partial_failing_final_updates_raw={"raw": 1},
            best_available_out_of_band_retained=True,
            rescue_debug={"rescue_mode_entered": False},
            rescue_gate_debug={"gate": "ok"},
            final_updates={"D": 700},
            working={"D": 650},
            winning_label="A",
            winning_action_type="tighten",
        )
    finally:
        if original_coherence is not None:
            module._coherence_debug_fields = original_coherence
        if original_trace_eval is not None:
            module._one_click_trace_eval_domain_payload = original_trace_eval

    dbg = result["one_click_solver_debug"]
    checks = {
        "return_status": result["status"] == "ok",
        "return_stop_reason": result["stop_reason"] == "max_steps",
        "return_step_count": result["step_count"] == 2,
        "return_final_preview_is_deepcopy": result["final_state_preview"] == {"D": 700}
        and result["final_state_preview"] is not result["final_updates"],
        "debug_target_band": dbg["target_band"] == {"min": 0.8, "max": 0.95},
        "debug_step_labels": dbg["step_candidate_labels"] == ["A", ""],
        "debug_coherence_merged": dbg["coherence_probe"] == "coherent",
        "debug_band_trace": dbg["final_eval_band_trace"] == {"band_probe": ["eval", "tight"]},
        "debug_rescue_merged": dbg["rescue_mode_entered"] is False,
        "debug_rescue_gate": dbg["rescue_gate_debug"] == {"gate": "ok"},
        "debug_final_no_links_marker": dbg["final_no_links_candidate_committed"] is False,
    }
    return {"checks": checks, "matches": all(checks.values())}


def build_payload() -> dict[str, Any]:
    source = _read(AUTO_DESIGN_COMPUTE)
    helper_start, helper_end, helper = _function_segment(source, "_build_final_solver_return_coordinator")
    debug_block_start, debug_block_end, debug_block = _function_segment(
        source,
        "_build_final_solver_debug_block_coordinator",
    )
    payload_with_debug_start, payload_with_debug_end, payload_with_debug = _function_segment(
        source,
        "_build_final_solver_return_payload_with_debug_coordinator",
    )
    finalization_start, finalization_end, finalization = _function_segment(
        source,
        "_finalize_one_click_solver_result_coordinator",
    )
    _, _, after_final_eval_helper = _function_segment(
        source,
        "_run_one_click_solver_finalization_after_final_evaluation_coordinator",
    )
    tail_start, tail_end, tail = _function_segment(
        source,
        "_complete_one_click_solver_final_trace_and_return_coordinator",
    )
    payload_start, payload_end, payload_body = _function_segment(
        source,
        "_build_one_click_solver_final_trace_return_payload_coordinator",
    )
    dispatch_start, dispatch_end, dispatch = _function_segment(
        source,
        "_dispatch_one_click_solver_final_trace_return_coordinator",
    )
    solve_start, solve_end, solve_body = _function_segment(source, "_solve_one_click_to_target")
    _, _, finish_body = _function_segment(
        source,
        "_finish_one_click_solver_iteration_loop_result_coordinator",
    )
    import inputs_page_modules.auto_design_compute as module  # noqa: E402

    runtime = _run_case(module)
    static_checks = {
        "helper_present": "def _build_final_solver_return_coordinator(" in source,
        "debug_block_helper_present": "def _build_final_solver_debug_block_coordinator(" in source,
        "helper_delegates_debug_block": (
            "dbg = _build_final_solver_debug_block_coordinator(" in helper
            and "final_solver_return_scope=final_solver_return_scope" in helper
        ),
        "debug_block_preserves_core_fields": all(
            token in debug_block
            for token in (
                '"iteration_count": len(scope["step_trace"])',
                '"target_band": {"min": scope["t_lo"], "max": scope["t_hi"]}',
                '"final_eval_band_trace"',
                '"best_available_out_of_band_retained"',
            )
        ),
        "payload_with_debug_helper_present": (
            "def _build_final_solver_return_payload_with_debug_coordinator(" in source
        ),
        "helper_delegates_payload_with_debug": (
            "return _build_final_solver_return_payload_with_debug_coordinator(" in helper
            and "final_solver_return_scope=final_solver_return_scope" in helper
        ),
        "payload_with_debug_returns_solver_result": (
            '"one_click_solver_debug": dbg' in payload_with_debug
        ),
        "payload_with_debug_preserves_final_state_deepcopy": (
            "copy.deepcopy(" in payload_with_debug
        ),
        "payload_with_debug_merges_rescue_debug": (
            'dbg.update(final_solver_return_scope["rescue_debug"])' in payload_with_debug
        ),
        "tail_delegates_final_return_payload": (
            "return _build_one_click_solver_final_trace_return_payload_coordinator(" in tail
            and "final_trace_scope=locals()" in tail
        ),
        "payload_delegates_final_return": (
            "return _build_final_solver_return_coordinator(" in payload_body
        ),
        "finalization_delegates_final_trace_and_return_tail": (
            "return _dispatch_one_click_solver_final_trace_return_coordinator("
            in after_final_eval_helper
        ),
        "dispatch_delegates_final_trace_and_return_tail": (
            "return _complete_one_click_solver_final_trace_and_return_coordinator(" in dispatch
        ),
        "finalization_no_longer_builds_final_return_directly": (
            "_build_final_solver_return_coordinator(" not in finalization
            and "_build_final_solver_return_coordinator(" not in after_final_eval_helper
        ),
        "finish_delegates_finalization": "_finalize_one_click_solver_result_coordinator(" in finish_body,
        "solver_delegates_loop_result_finish": "_finish_one_click_solver_iteration_loop_result_coordinator("
        in solve_body,
        "solver_no_longer_builds_final_dbg_inline": "dbg = {\n        \"iteration_count\"" not in solve_body,
    }
    status = "PASS"
    if not all(static_checks.values()) or not runtime["matches"]:
        status = "FAIL"
    return {
        "status": status,
        "surface": "_solve_one_click_to_target_final_solver_return_coordinator",
        "helper_segment": {
            "function": "_build_final_solver_return_coordinator",
            "start_line": helper_start,
            "end_line": helper_end,
            "line_count": helper_end - helper_start + 1,
        },
        "debug_block_segment": {
            "function": "_build_final_solver_debug_block_coordinator",
            "start_line": debug_block_start,
            "end_line": debug_block_end,
            "line_count": debug_block_end - debug_block_start + 1,
        },
        "payload_with_debug_segment": {
            "function": "_build_final_solver_return_payload_with_debug_coordinator",
            "start_line": payload_with_debug_start,
            "end_line": payload_with_debug_end,
            "line_count": payload_with_debug_end - payload_with_debug_start + 1,
        },
        "finalization_segment": {
            "function": "_finalize_one_click_solver_result_coordinator",
            "start_line": finalization_start,
            "end_line": finalization_end,
            "line_count": finalization_end - finalization_start + 1,
        },
        "tail_segment": {
            "function": "_complete_one_click_solver_final_trace_and_return_coordinator",
            "start_line": tail_start,
            "end_line": tail_end,
            "line_count": tail_end - tail_start + 1,
        },
        "payload_segment": {
            "function": "_build_one_click_solver_final_trace_return_payload_coordinator",
            "start_line": payload_start,
            "end_line": payload_end,
            "line_count": payload_end - payload_start + 1,
        },
        "dispatch_segment": {
            "function": "_dispatch_one_click_solver_final_trace_return_coordinator",
            "start_line": dispatch_start,
            "end_line": dispatch_end,
            "line_count": dispatch_end - dispatch_start + 1,
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
        "next_safe_slice": "extract initial solver trace coordinator",
    }


def write_artifacts(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now().isoformat(timespec="seconds").replace(":", "-")
    json_path = ARTIFACT_DIR / f"inputs_page_final_solver_return_coordinator_extraction_{stamp}.json"
    md_path = AUDIT_DIR / f"inputs_page_final_solver_return_coordinator_extraction_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Final Solver Return Coordinator Extraction",
        "",
        f"Status: `{payload['status']}`",
        "",
        "## Static Checks",
    ]
    for key, value in payload["static_checks"].items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(["", "## Runtime"])
    for key, value in payload["runtime"]["checks"].items():
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
