"""Verify finalization handoff solver coordinator extraction."""

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


def _base_kwargs() -> dict[str, Any]:
    return {
        "working": {"D": 650},
        "initial_snapshot": {"D": 600},
        "winning_label": "Winner",
        "winning_action_type": "tighten",
        "target_domains_for_band": ["shear"],
        "target_band_domain": "shear",
        "mode_config": {"mode": "balanced"},
        "init_worst": 1.2,
        "final_resolved_shear_util": 0.4,
        "final_resolved_web_util": 0.3,
        "init_pass": False,
        "init_progress": 0.1,
        "init_eval": {"initial": True},
        "stop_reason": "max_steps",
        "status": "exhausted",
        "rescue_enabled": True,
        "rescue_debug": {},
        "max_steps": 6,
        "debug_enabled": False,
        "trace_run_id": "rid-1",
        "trace_source": "unit",
        "attempted_seed_keys": set(),
        "stop_traced": [False],
        "step_trace": [{"step": 0}],
        "t_lo": 0.8,
        "t_hi": 1.0,
        "initial_coherence": {"ok": True},
        "tightening_step_count": 2,
        "max_tightening_steps": 4,
        "no_actionable_after_full_tightening_search": False,
        "candidate_family_depth_reached": "combined",
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
        "shear_governing_family_detected": True,
        "governing_family_exists_after_domain_fix": True,
        "pruned_non_shear_family_count": 9,
        "final_governing_domain": "shear",
        "rejected_as_non_governing_cleanup": 10,
        "rejected_as_non_governing_shear_strengthening": 11,
        "step_committable_eval_trace": [{"step": 0}],
        "shear_remove_links_candidate_seen": True,
        "shear_remove_links_candidate_truth_ok": False,
        "shear_remove_links_candidate_dropped_reason": "reason",
        "shear_remove_links_candidate_materiality": {"ratio": 0.2},
        "early_in_band_exit_blocked_for_tightening": False,
        "early_in_band_exit_tightening_classification": None,
        "early_in_band_exit_available_tightening_paths": [],
        "early_in_band_exit_reason": None,
        "trace_callback": lambda *_args, **_kwargs: None,
    }


def _final_eval_state() -> dict[str, Any]:
    return {
        "final_eval_internal": {"overview": {"worst_util": 0.95}},
        "final_updates": {"D": 50},
        "final_eval_committable": {"overview": {"worst_util": 0.93}},
        "final_sanitized_updates": {"D": 50},
        "final_eval": {"overview": {"worst_util": 0.93}},
        "final_eval_internal_worst_util_dbg": 0.95,
        "final_eval_committable_worst_util_dbg": 0.93,
        "final_eval_used_source_dbg": "committable_preview",
        "final_eval_committable_updates_dbg": {"D": 50},
        "final_target_domains": ["shear"],
        "final_worst": 0.93,
        "final_pass": True,
        "final_ok": True,
        "final_spacing_fail": False,
        "final_in_band": True,
        "final_band_hit": True,
        "final_objective_util": 0.93,
        "final_distance_to_band": 0.01,
        "final_resolved_shear_util": 0.87,
        "final_resolved_web_util": 0.62,
    }


def _run_cases(module: Any) -> dict[str, Any]:
    patched = (
        "_prepare_one_click_solver_final_evaluation_state_coordinator",
        "_handle_one_click_solver_partial_failing_final_updates_guard_coordinator",
        "_handle_one_click_solver_final_band_hit_stop_normalization_coordinator",
        "_prepare_one_click_solver_rescue_entry_decision_state_coordinator",
        "_prepare_one_click_solver_rescue_seed_loop_state_coordinator",
        "_trace_final_fallback_solver_stop_coordinator",
        "_build_final_solver_return_coordinator",
    )
    originals = {name: getattr(module, name, None) for name in patched}
    calls: list[dict[str, Any]] = []
    active = {"case": "normal"}

    def _final_eval(**kwargs: Any) -> dict[str, Any]:
        calls.append({"fn": "final_eval", "winning_label": kwargs["winning_label"]})
        return _final_eval_state()

    def _guard(**kwargs: Any) -> dict[str, Any]:
        calls.append({"fn": "guard", "final_updates": dict(kwargs["final_updates"])})
        return {
            "final_updates": {"D": 50, "guarded": True},
            "stop_reason": "guarded_reason",
            "winning_label": "Guarded winner",
            "winning_action_type": "guarded_action",
            "partial_failing_final_updates_blocked": False,
            "partial_failing_final_updates_raw": {},
            "best_available_out_of_band_retained": False,
        }

    def _normalise(**kwargs: Any) -> dict[str, Any]:
        calls.append({"fn": "normalise", "stop_reason": kwargs["stop_reason"]})
        return {"stop_reason": "solved", "status": "solved"}

    def _rescue_entry(**kwargs: Any) -> dict[str, Any]:
        calls.append({"fn": "rescue_entry", "stop_reason": kwargs["stop_reason"]})
        return {
            "rescue_should_enter": active["case"] == "rescue",
            "rescue_entry_reason": "needs_rescue",
            "rescue_family": "shear",
            "rescue_tier_requested": 1,
            "rescue_gate_debug": {"gate": True},
        }

    def _rescue_seed(**kwargs: Any) -> dict[str, Any]:
        calls.append({"fn": "rescue_seed", "should_enter": kwargs["rescue_should_enter"]})
        if active["case"] == "rescue":
            return {
                "should_return_rescue_result": True,
                "rescue_result": {"rescued": True},
            }
        return {
            "should_return_rescue_result": False,
            "rescue_result": None,
        }

    def _fallback(**kwargs: Any) -> None:
        calls.append({"fn": "fallback", "stop_reason": kwargs["stop_reason"]})

    def _final_return(**kwargs: Any) -> dict[str, Any]:
        calls.append({"fn": "return", "stop_reason": kwargs["stop_reason"]})
        return {
            "returned": True,
            "stop_reason": kwargs["stop_reason"],
            "status": kwargs["status"],
            "winning_label": kwargs["winning_label"],
            "final_updates": dict(kwargs["final_updates"]),
            "rescue_gate_debug": dict(kwargs["rescue_gate_debug"]),
        }

    try:
        module._prepare_one_click_solver_final_evaluation_state_coordinator = _final_eval
        module._handle_one_click_solver_partial_failing_final_updates_guard_coordinator = _guard
        module._handle_one_click_solver_final_band_hit_stop_normalization_coordinator = _normalise
        module._prepare_one_click_solver_rescue_entry_decision_state_coordinator = _rescue_entry
        module._prepare_one_click_solver_rescue_seed_loop_state_coordinator = _rescue_seed
        module._trace_final_fallback_solver_stop_coordinator = _fallback
        module._build_final_solver_return_coordinator = _final_return

        active["case"] = "normal"
        normal = module._finalize_one_click_solver_result_coordinator(**_base_kwargs())
        active["case"] = "rescue"
        rescue = module._finalize_one_click_solver_result_coordinator(**_base_kwargs())
    finally:
        for name, original in originals.items():
            if original is not None:
                setattr(module, name, original)
            elif hasattr(module, name):
                delattr(module, name)

    return {"normal": normal, "rescue": rescue, "calls": calls}


def build_payload() -> dict[str, Any]:
    source = _read(AUTO_DESIGN_COMPUTE)
    helper_start, helper_end, helper = _function_segment(
        source,
        "_finalize_one_click_solver_result_coordinator",
    )
    _, _, rescue_seed_dispatch = _function_segment(
        source,
        "_dispatch_one_click_solver_rescue_seed_loop_from_finalization_coordinator",
    )
    _, _, rescue_seed_result_dispatch = _function_segment(
        source,
        "_dispatch_one_click_solver_rescue_seed_result_from_finalization_coordinator",
    )
    _, _, partial_guard_dispatch = _function_segment(
        source,
        "_dispatch_one_click_solver_partial_failing_final_updates_guard_from_finalization_coordinator",
    )
    _, _, final_evaluation_dispatch = _function_segment(
        source,
        "_dispatch_one_click_solver_final_evaluation_state_from_finalization_coordinator",
    )
    _, _, band_hit_normalization_dispatch = _function_segment(
        source,
        "_dispatch_one_click_solver_final_band_hit_stop_normalization_from_finalization_coordinator",
    )
    _, _, rescue_entry_dispatch = _function_segment(
        source,
        "_dispatch_one_click_solver_rescue_entry_decision_from_finalization_coordinator",
    )
    tail_start, tail_end, tail = _function_segment(
        source,
        "_complete_one_click_solver_final_trace_and_return_coordinator",
    )
    _, _, payload_body = _function_segment(
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

    runtime = _run_cases(module)
    normal_calls = [call["fn"] for call in runtime["calls"][:7]]
    rescue_calls = [call["fn"] for call in runtime["calls"][7:12]]
    runtime_checks = {
        "normal_call_order": normal_calls
        == ["final_eval", "guard", "normalise", "rescue_entry", "rescue_seed", "fallback", "return"],
        "rescue_call_order_skips_fallback_and_return": rescue_calls
        == ["final_eval", "guard", "normalise", "rescue_entry", "rescue_seed"],
        "normal_return_shape": runtime["normal"] == {
            "returned": True,
            "stop_reason": "solved",
            "status": "solved",
            "winning_label": "Guarded winner",
            "final_updates": {"D": 50, "guarded": True},
            "rescue_gate_debug": {"gate": True},
        },
        "rescue_returns_rescue_result": runtime["rescue"] == {"rescued": True},
    }
    static_checks = {
        "helper_present": "def _finalize_one_click_solver_result_coordinator(" in source,
        "helper_delegates_final_eval": (
            "_dispatch_one_click_solver_final_evaluation_state_from_finalization_coordinator("
            in helper
            and "_prepare_one_click_solver_final_evaluation_state_coordinator("
            in final_evaluation_dispatch
            and "finalization_scope[" in final_evaluation_dispatch
        ),
        "helper_delegates_partial_guard": (
            "_dispatch_one_click_solver_partial_failing_final_updates_guard_from_finalization_coordinator("
            in helper
            and "_handle_one_click_solver_partial_failing_final_updates_guard_coordinator("
            in partial_guard_dispatch
            and "finalization_scope[" in partial_guard_dispatch
        ),
        "helper_delegates_band_hit_normalisation": (
            "_dispatch_one_click_solver_final_band_hit_stop_normalization_from_finalization_coordinator("
            in helper
            and "_handle_one_click_solver_final_band_hit_stop_normalization_coordinator("
            in band_hit_normalization_dispatch
            and "finalization_scope[" in band_hit_normalization_dispatch
        ),
        "helper_delegates_rescue_entry": (
            "_dispatch_one_click_solver_rescue_entry_decision_from_finalization_coordinator("
            in helper
            and "_prepare_one_click_solver_rescue_entry_decision_state_coordinator("
            in rescue_entry_dispatch
            and "finalization_scope[" in rescue_entry_dispatch
        ),
        "helper_delegates_rescue_seed_dispatch": (
            "_dispatch_one_click_solver_rescue_seed_result_from_finalization_coordinator("
            in helper
            and "_dispatch_one_click_solver_rescue_seed_loop_from_finalization_coordinator("
            in rescue_seed_result_dispatch
            and "finalization_scope=finalization_scope" in rescue_seed_result_dispatch
        ),
        "rescue_seed_dispatch_delegates_rescue_seed": (
            "_prepare_one_click_solver_rescue_seed_loop_state_coordinator("
            in rescue_seed_dispatch
            and "finalization_scope[" in rescue_seed_dispatch
        ),
        "helper_preserves_rescue_early_return": (
            "if should_return_rescue_result:" in helper
            and "return rescue_result" in helper
            and 'rescue_seed_loop_state["should_return_rescue_result"]'
            in rescue_seed_result_dispatch
            and 'rescue_seed_loop_state["rescue_result"]' in rescue_seed_result_dispatch
        ),
        "helper_delegates_final_trace_and_return_tail": (
            "_dispatch_one_click_solver_final_trace_return_coordinator(" in helper
        ),
        "dispatch_delegates_final_trace_and_return_tail": (
            "_complete_one_click_solver_final_trace_and_return_coordinator(" in dispatch
        ),
        "helper_no_longer_delegates_final_fallback_trace_directly": (
            "_trace_final_fallback_solver_stop_coordinator(" not in helper
        ),
        "helper_no_longer_delegates_final_return_directly": (
            "_build_final_solver_return_coordinator(" not in helper
        ),
        "tail_delegates_final_fallback_trace": "_trace_final_fallback_solver_stop_coordinator(" in tail,
        "tail_delegates_final_return_payload": (
            "_build_one_click_solver_final_trace_return_payload_coordinator(" in tail
        ),
        "payload_delegates_final_return": "_build_final_solver_return_coordinator(" in payload_body,
        "tail_preserves_final_fallback_before_return": (
            tail.index("_trace_final_fallback_solver_stop_coordinator(")
            < tail.index("_build_one_click_solver_final_trace_return_payload_coordinator(")
        ),
        "finish_delegates_finalization": "_finalize_one_click_solver_result_coordinator(" in finish_body,
        "solver_delegates_loop_result_finish": "_finish_one_click_solver_iteration_loop_result_coordinator("
        in solve_body,
        "solver_no_longer_delegates_final_helpers_directly": all(
            token not in solve_body
            for token in (
                "_prepare_one_click_solver_final_evaluation_state_coordinator(",
                "_handle_one_click_solver_partial_failing_final_updates_guard_coordinator(",
                "_prepare_one_click_solver_rescue_seed_loop_state_coordinator(",
                "_trace_final_fallback_solver_stop_coordinator(",
                "_build_final_solver_return_coordinator(",
            )
        ),
    }
    status = "PASS"
    if not all(static_checks.values()) or not all(runtime_checks.values()):
        status = "FAIL"
    return {
        "status": status,
        "surface": "_solve_one_click_to_target_finalization_handoff_coordinator",
        "helper_segment": {
            "function": "_finalize_one_click_solver_result_coordinator",
            "start_line": helper_start,
            "end_line": helper_end,
            "line_count": helper_end - helper_start + 1,
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
        "runtime_checks": runtime_checks,
        "product_behavior_changed": False,
        "next_safe_slice": "audit remaining solver-loop coordinator surfaces",
    }


def write_artifacts(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now().isoformat(timespec="seconds").replace(":", "-")
    json_path = ARTIFACT_DIR / (
        f"inputs_page_solver_finalization_handoff_coordinator_extraction_{stamp}.json"
    )
    md_path = AUDIT_DIR / (
        f"inputs_page_solver_finalization_handoff_coordinator_extraction_{stamp}.md"
    )
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Solver Finalization Handoff Coordinator Extraction",
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
