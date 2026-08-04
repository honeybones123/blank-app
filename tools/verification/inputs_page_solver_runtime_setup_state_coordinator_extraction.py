"""Verify one-click solver runtime setup state coordinator extraction."""

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


def _run_case(module: Any, scenario: str) -> dict[str, Any]:
    calls: list[str] = []

    def _initial(**_kwargs: Any) -> dict[str, Any]:
        calls.append("initial")
        return {
            "rid": "rid",
            "stop_traced": [False],
            "rescue_debug": {"rescue": True},
            "attempted_seed_keys": {"seed"},
            "trace_callback": lambda *_args, **_kwargs: None,
            "initial_snapshot": {"D": 600},
            "initial_coherence": {"ok": True},
            "initial_pack_valid": scenario != "initial_blocked",
            "initial_coherence_should_block": False,
            "initial_stop_reason": "bad_pack",
        }

    def _initial_blocked(**kwargs: Any) -> dict[str, Any]:
        calls.append("initial_blocked_return")
        return {"kind": "initial_blocked", "reason": kwargs["initial_stop_reason"]}

    def _mode_budget(**_kwargs: Any) -> dict[str, Any]:
        calls.append("mode_budget")
        return {
            "working": {"D": 600},
            "mode_config": {"mode": "balanced"},
            "t_lo": 0.85,
            "t_hi": 0.95,
            "max_tightening_steps": 4,
            "tightening_budget_extensions_used": 0,
            "tightening_budget_extension_cap": 2,
            "tightening_step_count": 0,
            "no_actionable_after_full_tightening_search": False,
            "candidate_family_depth_reached": False,
            "final_distance_to_band": None,
            "shear_governing_mode_active": False,
            "shear_severity_band": None,
            "shear_candidate_family_order": [],
            "spacing_candidates_considered": False,
            "leg_candidates_considered": False,
            "dia_candidates_considered": False,
            "geometry_candidates_considered_for_shear": False,
            "combined_candidates_considered_for_shear": False,
            "web_crushing_penalty_applied": 0,
            "rejected_as_spacing_too_weak": 0,
            "rejected_as_web_crushing_marginal": 0,
            "rejected_as_impractical_shear_layout": 0,
            "final_resolved_shear_util": None,
            "final_resolved_web_util": None,
            "step_committable_eval_trace": [],
        }

    def _initial_eval(**_kwargs: Any) -> dict[str, Any]:
        calls.append("initial_eval")
        if scenario == "eval_failed":
            return {"init_eval": None}
        return {
            "init_eval": {"overview": {}},
            "target_band_domain": "bending",
            "target_domains_for_band": ["bending"],
            "init_worst": 0.91,
            "init_pass": scenario == "already_in_band",
            "init_in_band": scenario == "already_in_band",
            "init_progress": {"ok": True},
        }

    def _eval_failed(**_kwargs: Any) -> dict[str, Any]:
        calls.append("eval_failed_return")
        return {"kind": "eval_failed"}

    def _early(**_kwargs: Any) -> dict[str, Any]:
        calls.append("early")
        return {
            "early_in_band_exit_blocked_for_tightening": False,
            "early_in_band_exit_tightening_classification": "none",
            "early_in_band_exit_available_tightening_paths": [],
            "early_in_band_exit_reason": "already",
            "should_return_already_in_band": scenario == "already_in_band",
        }

    def _already(**_kwargs: Any) -> dict[str, Any]:
        calls.append("already_return")
        return {"kind": "already_in_band"}

    def _iteration(**_kwargs: Any) -> dict[str, Any]:
        calls.append("iteration")
        return {
            "seen_sigs": {("sig",)},
            "step_trace": [],
            "stop_reason": None,
            "status": "running",
            "winning_label": None,
            "winning_action_type": None,
            "final_governing_domain": None,
            "rejected_as_non_governing_cleanup": 0,
            "rejected_as_non_governing_shear_strengthening": 0,
            "shear_remove_links_candidate_seen": False,
            "shear_remove_links_candidate_truth_ok": False,
            "shear_remove_links_candidate_dropped_reason": None,
            "shear_remove_links_candidate_materiality": "not_evaluated",
        }

    originals = _patch(
        module,
        {
            "_prepare_one_click_solver_initial_state_coordinator": _initial,
            "_build_initial_blocked_solver_return_coordinator": _initial_blocked,
            "_prepare_one_click_solver_mode_budget_state_coordinator": _mode_budget,
            "_prepare_one_click_solver_initial_eval_state_coordinator": _initial_eval,
            "_build_evaluate_failed_solver_return_coordinator": _eval_failed,
            "_prepare_one_click_solver_early_in_band_gate_state_coordinator": _early,
            "_build_already_in_band_solver_return_coordinator": _already,
            "_prepare_one_click_solver_iteration_state_coordinator": _iteration,
        },
    )
    try:
        returned = module._prepare_one_click_solver_runtime_setup_state_coordinator(
            state={"D": 600},
            max_steps=6,
            trace_run_id="rid",
            trace_source="unit",
            rescue_attempted_seed_keys=("seed",),
        )
    finally:
        _restore(module, originals)
    if returned.get("seen_sigs") is not None:
        returned = dict(returned)
        returned["seen_sigs"] = [list(sig) for sig in returned["seen_sigs"]]
    if returned.get("attempted_seed_keys") is not None:
        returned = dict(returned)
        returned["attempted_seed_keys"] = sorted(returned["attempted_seed_keys"])
    if callable(returned.get("trace_callback")):
        returned = dict(returned)
        returned["trace_callback"] = "<callable>"
    return {"calls": calls, "returned": returned}


def build_payload() -> dict[str, Any]:
    source = _read(AUTO_DESIGN_COMPUTE)
    helper_start, helper_end, helper = _function_segment(
        source,
        "_prepare_one_click_solver_runtime_setup_state_coordinator",
    )
    _, _, after_initial_helper = _function_segment(
        source,
        "_prepare_one_click_solver_runtime_setup_after_initial_state_coordinator",
    )
    _, _, after_mode_budget_helper = _function_segment(
        source,
        "_prepare_one_click_solver_runtime_setup_after_mode_budget_state_coordinator",
    )
    ready_start, ready_end, ready_body = _function_segment(
        source,
        "_build_one_click_solver_runtime_setup_ready_state_coordinator",
    )
    dispatch_start, dispatch_end, dispatch_body = _function_segment(
        source,
        "_dispatch_one_click_solver_iteration_loop_from_solver_runtime_setup_coordinator",
    )
    solve_start, solve_end, solve_body = _function_segment(source, "_solve_one_click_to_target")

    import inputs_page_modules.auto_design_compute as module  # noqa: E402

    runtime = {
        "initial_blocked": _run_case(module, "initial_blocked"),
        "eval_failed": _run_case(module, "eval_failed"),
        "already_in_band": _run_case(module, "already_in_band"),
        "normal": _run_case(module, "normal"),
    }
    runtime_checks = {
        "initial_blocked_returns_before_mode_budget": (
            runtime["initial_blocked"]["calls"] == ["initial", "initial_blocked_return"]
            and runtime["initial_blocked"]["returned"]["should_return"] is True
            and runtime["initial_blocked"]["returned"]["return_result"] == {
                "kind": "initial_blocked",
                "reason": "bad_pack",
            }
        ),
        "eval_failed_returns_before_early_gate": (
            runtime["eval_failed"]["calls"] == ["initial", "mode_budget", "initial_eval", "eval_failed_return"]
            and runtime["eval_failed"]["returned"]["return_result"] == {"kind": "eval_failed"}
        ),
        "already_in_band_returns_before_iteration_state": (
            runtime["already_in_band"]["calls"]
            == ["initial", "mode_budget", "initial_eval", "early", "already_return"]
            and runtime["already_in_band"]["returned"]["return_result"] == {"kind": "already_in_band"}
        ),
        "normal_setup_returns_loop_state": (
            runtime["normal"]["calls"] == ["initial", "mode_budget", "initial_eval", "early", "iteration"]
            and runtime["normal"]["returned"]["should_return"] is False
            and runtime["normal"]["returned"]["stop_traced"] == [False]
            and runtime["normal"]["returned"]["target_domains_for_band"] == ["bending"]
            and runtime["normal"]["returned"]["seen_sigs"] == [["sig"]]
            and runtime["normal"]["returned"]["status"] == "running"
        ),
    }
    ordered_tokens = [
        "_prepare_one_click_solver_initial_state_coordinator(",
        "_prepare_one_click_solver_mode_budget_state_coordinator(",
        "_prepare_one_click_solver_initial_eval_state_coordinator(",
        "_prepare_one_click_solver_early_in_band_gate_state_coordinator(",
        "_prepare_one_click_solver_iteration_state_coordinator(",
    ]
    static_checks = {
        "helper_present": "def _prepare_one_click_solver_runtime_setup_state_coordinator(" in source,
        "helper_preserves_setup_order": (
            ordered_tokens[0] in helper
            and ordered_tokens[1] in after_initial_helper
            and all(token in after_mode_budget_helper for token in ordered_tokens[2:])
            and [
                after_mode_budget_helper.index(token)
                for token in ordered_tokens[2:]
            ]
            == sorted(
                after_mode_budget_helper.index(token)
                for token in ordered_tokens[2:]
            )
        ),
        "helper_preserves_early_return_paths": all(
            token in (after_initial_helper + after_mode_budget_helper)
            for token in (
                "_build_initial_blocked_solver_return_coordinator(",
                "_build_evaluate_failed_solver_return_coordinator(",
                "_build_already_in_band_solver_return_coordinator(",
                '"should_return": True',
                '"return_result":',
            )
        ),
        "helper_delegates_ready_state_packing": (
            "_build_one_click_solver_runtime_setup_ready_state_coordinator("
            in after_mode_budget_helper
        ),
        "ready_helper_returns_finalization_and_loop_state": all(
            token in ready_body
            for token in (
                '"stop_traced": runtime_setup_scope["stop_traced"]',
                '"initial_snapshot": runtime_setup_scope["initial_snapshot"]',
                '"init_eval": runtime_setup_scope["init_eval"]',
                '"early_in_band_exit_reason": runtime_setup_scope["early_in_band_exit_reason"]',
                '"seen_sigs": solver_iteration_state["seen_sigs"]',
                '"shear_remove_links_candidate_materiality": solver_iteration_state[',
            )
        ),
        "solver_delegates_runtime_setup_state": (
            "_prepare_one_click_solver_runtime_setup_state_coordinator(" in solve_body
        ),
        "solver_uses_runtime_setup_return_gate": (
            'if runtime_setup_state["should_return"]:' in solve_body
            and 'return runtime_setup_state["return_result"]' in solve_body
        ),
        "solver_delegates_iteration_loop_runtime_setup_dispatch": (
            "_dispatch_one_click_solver_iteration_loop_from_solver_runtime_setup_coordinator("
            in solve_body
        ),
        "iteration_loop_runtime_setup_dispatch_maps_loop_state": all(
            token in dispatch_body
            for token in (
                'trace_run_id=runtime_setup_state["rid"]',
                'trace_callback=runtime_setup_state["trace_callback"]',
                'initial_snapshot=runtime_setup_state["initial_snapshot"]',
                'target_domains_for_band=runtime_setup_state["target_domains_for_band"]',
                'seen_sigs=runtime_setup_state["seen_sigs"]',
                'shear_remove_links_candidate_materiality=runtime_setup_state[',
            )
        ),
        "solver_no_longer_owns_setup_subgates": all(token not in solve_body for token in ordered_tokens),
    }
    status = "PASS"
    if not all(static_checks.values()) or not all(runtime_checks.values()):
        status = "FAIL"
    return {
        "status": status,
        "surface": "_solve_one_click_to_target_runtime_setup_state_coordinator",
        "helper_segment": {
            "function": "_prepare_one_click_solver_runtime_setup_state_coordinator",
            "start_line": helper_start,
            "end_line": helper_end,
            "line_count": helper_end - helper_start + 1,
        },
        "ready_state_segment": {
            "function": "_build_one_click_solver_runtime_setup_ready_state_coordinator",
            "start_line": ready_start,
            "end_line": ready_end,
            "line_count": ready_end - ready_start + 1,
        },
        "iteration_loop_dispatch_segment": {
            "function": "_dispatch_one_click_solver_iteration_loop_from_solver_runtime_setup_coordinator",
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
        "runtime": runtime,
        "product_behavior_changed": False,
        "next_safe_slice": "audit remaining solver loop body or finalize handoff",
    }


def write_artifacts(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now().isoformat(timespec="seconds").replace(":", "-")
    json_path = ARTIFACT_DIR / (
        f"inputs_page_solver_runtime_setup_state_coordinator_extraction_{stamp}.json"
    )
    md_path = AUDIT_DIR / (
        f"inputs_page_solver_runtime_setup_state_coordinator_extraction_{stamp}.md"
    )
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Solver Runtime Setup State Coordinator Extraction",
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
