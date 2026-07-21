"""Verify final fallback solver stop coordinator extraction."""

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
    original_under = getattr(module, "_one_click_still_materially_under_target", None)
    calls: list[dict[str, Any]] = []

    def _fake_under(final_eval: dict, mode_config: dict, *, margin: float) -> bool:
        return final_eval.get("under") is True and mode_config.get("mode") == "tight" and margin == 0.03

    def _trace(ev: str, dat: dict) -> None:
        calls.append({"ev": ev, "dat": dict(dat)})

    try:
        module._one_click_still_materially_under_target = _fake_under
        module._trace_final_fallback_solver_stop_coordinator(
            stop_reason="max_steps",
            step_trace=[{"step": 1}, {"step": 2}],
            status="exhausted",
            final_worst=0.91,
            final_in_band=True,
            final_pass=False,
            winning_label="Final candidate",
            winning_action_type="tighten",
            final_updates={"D": 650},
            tightening_step_count=3,
            max_tightening_steps=4,
            final_eval={"under": True},
            mode_config={"mode": "tight"},
            no_actionable_after_full_tightening_search=True,
            candidate_family_depth_reached="beam_depth",
            final_distance_to_band=0.07,
            shear_governing_mode_active=True,
            shear_severity_band="high",
            shear_candidate_family_order=["spacing", "legs"],
            spacing_candidates_considered=5,
            leg_candidates_considered=6,
            dia_candidates_considered=7,
            geometry_candidates_considered_for_shear=8,
            combined_candidates_considered_for_shear=9,
            web_crushing_penalty_applied=10,
            rejected_as_spacing_too_weak=11,
            rejected_as_web_crushing_marginal=12,
            rejected_as_impractical_shear_layout=13,
            final_resolved_shear_util=0.82,
            final_resolved_web_util=0.73,
            shear_governing_family_detected=True,
            governing_family_exists_after_domain_fix=False,
            pruned_non_shear_family_count=14,
            rescue_debug={
                "rescue_mode_entered": True,
                "rescue_mode_entry_reason": "blocked",
                "rescue_mode_family": "shear",
                "rescue_mode_tier_requested": "wide",
                "rescue_mode_tier_used": "narrow",
                "rescue_mode_seed_key": "seed-1",
                "rescue_mode_fallback_count": 2,
                "rescue_mode_ineffective_seeds": ("a", "b"),
                "rescue_mode_effective_seed_found": False,
                "rescue_mode_exit_reason": "none",
            },
            trace_callback=_trace,
        )
    finally:
        if original_under is not None:
            module._one_click_still_materially_under_target = original_under

    expected = [
        {
            "ev": "stop",
            "dat": {
                "stop_reason": "max_steps",
                "step_count": 2,
                "status": "exhausted",
                "final_preview_util": 0.91,
                "reached_target_band": False,
                "all_key_pass": False,
                "winning_label": "Final candidate",
                "winning_action_type": "tighten",
                "final_updates": {"D": 650},
                "tightening_step_count": 3,
                "tightening_depth_budget": 4,
                "still_materially_under_target": True,
                "no_actionable_after_full_tightening_search": True,
                "candidate_family_depth_reached": "beam_depth",
                "final_distance_to_band": 0.07,
                "shear_governing_mode_active": True,
                "shear_severity_band": "high",
                "shear_candidate_family_order": ["spacing", "legs"],
                "spacing_candidates_considered": 5,
                "leg_candidates_considered": 6,
                "dia_candidates_considered": 7,
                "geometry_candidates_considered_for_shear": 8,
                "combined_candidates_considered_for_shear": 9,
                "web_crushing_penalty_applied": 10,
                "rejected_as_spacing_too_weak": 11,
                "rejected_as_web_crushing_marginal": 12,
                "rejected_as_impractical_shear_layout": 13,
                "final_resolved_shear_util": 0.82,
                "final_resolved_web_util": 0.73,
                "shear_governing_family_detected": True,
                "governing_family_exists_after_domain_fix": False,
                "pruned_non_shear_family_count": 14,
                "rescue_mode_entered": True,
                "rescue_mode_entry_reason": "blocked",
                "rescue_mode_family": "shear",
                "rescue_mode_tier_requested": "wide",
                "rescue_mode_tier_used": "narrow",
                "rescue_mode_seed_key": "seed-1",
                "rescue_mode_fallback_count": 2,
                "rescue_mode_ineffective_seeds": ["a", "b"],
                "rescue_mode_effective_seed_found": False,
                "rescue_mode_exit_reason": "none",
            },
        }
    ]
    return {"calls": calls, "matches": calls == expected}


def build_payload() -> dict[str, Any]:
    source = _read(AUTO_DESIGN_COMPUTE)
    helper_start, helper_end, helper = _function_segment(source, "_trace_final_fallback_solver_stop_coordinator")
    finalization_start, finalization_end, finalization = _function_segment(
        source,
        "_finalize_one_click_solver_result_coordinator",
    )
    tail_start, tail_end, tail = _function_segment(
        source,
        "_complete_one_click_solver_final_trace_and_return_coordinator",
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
        "helper_present": "def _trace_final_fallback_solver_stop_coordinator(" in source,
        "helper_emits_stop_trace": 'trace_callback(\n        "stop",' in helper,
        "helper_preserves_target_band_marker": '"reached_target_band": bool(final_in_band and final_pass)' in helper,
        "helper_preserves_material_under_target_probe": "_one_click_still_materially_under_target(" in helper,
        "helper_preserves_rescue_fields": '"rescue_mode_effective_seed_found"' in helper,
        "tail_delegates_final_fallback_stop": (
            "_trace_final_fallback_solver_stop_coordinator(" in tail
        ),
        "finalization_delegates_final_trace_and_return_tail": (
            "_dispatch_one_click_solver_final_trace_return_coordinator(" in finalization
        ),
        "dispatch_delegates_final_trace_and_return_tail": (
            "_complete_one_click_solver_final_trace_and_return_coordinator(" in dispatch
        ),
        "finalization_no_longer_traces_final_fallback_stop_directly": (
            "_trace_final_fallback_solver_stop_coordinator(" not in finalization
        ),
        "finish_delegates_finalization": "_finalize_one_click_solver_result_coordinator(" in finish_body,
        "solver_delegates_loop_result_finish": "_finish_one_click_solver_iteration_loop_result_coordinator("
        in solve_body,
        "tail_preserves_stop_trace_gate": "if trace_run_id and not stop_traced[0]:" in tail,
        "solver_no_longer_inlines_stop_trace": '_t(\n            "stop",' not in solve_body,
    }
    status = "PASS"
    if not all(static_checks.values()) or not runtime["matches"]:
        status = "FAIL"
    return {
        "status": status,
        "surface": "_solve_one_click_to_target_final_fallback_stop_coordinator",
        "helper_segment": {
            "function": "_trace_final_fallback_solver_stop_coordinator",
            "start_line": helper_start,
            "end_line": helper_end,
            "line_count": helper_end - helper_start + 1,
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
        "runtime": {"matches": runtime["matches"]},
        "product_behavior_changed": False,
        "next_safe_slice": "extract final solver debug/return coordinator",
    }


def write_artifacts(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now().isoformat(timespec="seconds").replace(":", "-")
    json_path = ARTIFACT_DIR / f"inputs_page_final_fallback_solver_stop_coordinator_extraction_{stamp}.json"
    md_path = AUDIT_DIR / f"inputs_page_final_fallback_solver_stop_coordinator_extraction_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Final Fallback Solver Stop Coordinator Extraction",
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
            f"- Stop trace matches: `{payload['runtime']['matches']}`",
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
