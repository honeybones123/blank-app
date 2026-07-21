"""Verify one-click solver iteration gate state coordinator extraction."""

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


def _call(module: Any, *, scenario: str) -> dict[str, Any]:
    calls: list[str] = []

    def _current_iteration(**_kwargs: Any) -> dict[str, Any]:
        calls.append("current_iteration")
        if scenario == "eval_none":
            return {"cur_eval": None, "stop_reason": "evaluate_failed", "status": "failed"}
        return {
            "cur_eval": {"overview": {}, "scenario": scenario},
            "cur_pass": scenario == "in_band_stop",
            "cur_sig": ("sig", scenario),
            "tightening_mode_active": True,
            "governing_domain": "bending",
            "target_band_domain": "bending",
            "cur_statuses": {"bending": "FAIL"},
            "cur_shear_status": "PASS",
            "cur_shear_failing": False,
            "cur_fail_keys": ["bending"],
            "governing_domain_norm": "bending",
            "governing_domain_failing": True,
        }

    def _target_domain(**kwargs: Any) -> dict[str, Any]:
        calls.append("target_domain")
        return {
            "target_band_domain": kwargs["target_band_domain"],
            "cur_ib": scenario == "in_band_stop",
            "target_work_domain": "bending",
            "required_domain_work_active": True,
            "governing_domain": kwargs["governing_domain"],
            "tightening_mode_active": kwargs["tightening_mode_active"],
        }

    def _in_band(**kwargs: Any) -> dict[str, Any]:
        calls.append("in_band")
        return {
            "in_band_shear_cleanup_deferral": {"active": False},
            "tightening_mode_active": kwargs["tightening_mode_active"],
            "governing_domain": kwargs["governing_domain"],
            "final_governing_domain": kwargs["governing_domain"],
            "shear_governing_mode_active": False,
            "shear_governing_family_detected": False,
            "pruned_non_shear_family_count": 2,
            "domain_match_prune_used": True,
            "shear_prune_rule_source": "domain_matcher",
            "material_improvement_threshold": 0.01,
            "tightening_meta": {"source": "test"},
            "should_stop_current_reached_target_band": scenario == "in_band_stop",
        }

    def _trace_stop(**_kwargs: Any) -> tuple[str, str]:
        calls.append("trace_stop")
        return "current_reached_target_band", "solved"

    def _depth(**_kwargs: Any) -> dict[str, Any]:
        calls.append("depth")
        return {
            "cur_u": 0.88,
            "max_tightening_steps": 9,
            "tightening_budget_extensions_used": 1,
            "should_continue": scenario == "depth_continue",
            "should_break": scenario == "depth_break",
            "stop_reason": "max_tightening_depth",
            "status": "partial",
            "final_distance_to_band": 0.17,
        }

    originals = _patch(
        module,
        {
            "_prepare_one_click_solver_current_iteration_eval_state_coordinator": _current_iteration,
            "_prepare_one_click_solver_current_target_domain_state_coordinator": _target_domain,
            "_prepare_one_click_solver_in_band_cleanup_and_pool_state_coordinator": _in_band,
            "_trace_current_reached_target_band_solver_stop_coordinator": _trace_stop,
            "_prepare_one_click_solver_tightening_depth_gate_state_coordinator": _depth,
        },
    )
    try:
        returned = module._prepare_one_click_solver_iteration_gate_state_coordinator(
            step_idx=1,
            working={"D": 600},
            mode_config=None,
            target_band_domain="bending",
            target_domains_for_band=["bending"],
            step_trace=[],
            initial_snapshot={},
            winning_label="Win",
            winning_action_type="tighten",
            tightening_step_count=1,
            max_tightening_steps=8,
            tightening_budget_extensions_used=0,
            tightening_budget_extension_cap=2,
            candidate_family_depth_reached=False,
            trace_callback=lambda *_args, **_kwargs: None,
        )
    finally:
        _restore(module, originals)
    return {"calls": calls, "returned": returned}


def _runtime_cases(module: Any) -> dict[str, Any]:
    return {
        "normal": _call(module, scenario="normal"),
        "eval_none": _call(module, scenario="eval_none"),
        "in_band_stop": _call(module, scenario="in_band_stop"),
        "depth_continue": _call(module, scenario="depth_continue"),
        "depth_break": _call(module, scenario="depth_break"),
    }


def build_payload() -> dict[str, Any]:
    source = _read(AUTO_DESIGN_COMPUTE)
    helper_start, helper_end, helper = _function_segment(
        source,
        "_prepare_one_click_solver_iteration_gate_state_coordinator",
    )
    _, _, ready_state_packer = _function_segment(
        source,
        "_build_one_click_solver_iteration_gate_ready_state_coordinator",
    )
    _, _, current_target_dispatch = _function_segment(
        source,
        "_dispatch_one_click_solver_current_target_domain_state_from_iteration_gate_coordinator",
    )
    _, _, tightening_depth_dispatch = _function_segment(
        source,
        "_dispatch_one_click_solver_tightening_depth_gate_state_from_iteration_gate_coordinator",
    )
    loop_start, loop_end, loop_body = _function_segment(
        source,
        "_run_one_click_solver_iteration_loop_coordinator",
    )
    _, _, loop_candidate_flow_dispatch = _function_segment(
        source,
        "_dispatch_one_click_solver_iteration_candidate_flow_from_iteration_loop_coordinator",
    )
    solve_start, solve_end, solve_body = _function_segment(source, "_solve_one_click_to_target")

    import inputs_page_modules.auto_design_compute as module  # noqa: E402

    runtime = _runtime_cases(module)
    runtime_checks = {
        "normal_path_preserves_gate_order_and_fields": (
            runtime["normal"]["calls"] == ["current_iteration", "target_domain", "in_band", "depth"]
            and runtime["normal"]["returned"]["should_break"] is False
            and runtime["normal"]["returned"]["cur_sig"] == ("sig", "normal")
            and runtime["normal"]["returned"]["required_domain_work_active"] is True
            and runtime["normal"]["returned"]["cur_u"] == 0.88
        ),
        "current_eval_none_breaks_before_later_gates": (
            runtime["eval_none"]["calls"] == ["current_iteration"]
            and runtime["eval_none"]["returned"]["should_break"] is True
            and runtime["eval_none"]["returned"]["stop_reason"] == "evaluate_failed"
        ),
        "in_band_stop_traces_and_breaks_before_depth": (
            runtime["in_band_stop"]["calls"] == ["current_iteration", "target_domain", "in_band", "trace_stop"]
            and runtime["in_band_stop"]["returned"]["should_break"] is True
            and runtime["in_band_stop"]["returned"]["status"] == "solved"
        ),
        "depth_continue_preserves_budget_updates": (
            runtime["depth_continue"]["calls"] == ["current_iteration", "target_domain", "in_band", "depth"]
            and runtime["depth_continue"]["returned"]["should_continue"] is True
            and runtime["depth_continue"]["returned"]["max_tightening_steps"] == 9
            and runtime["depth_continue"]["returned"]["tightening_budget_extensions_used"] == 1
        ),
        "depth_break_preserves_final_distance": (
            runtime["depth_break"]["calls"] == ["current_iteration", "target_domain", "in_band", "depth"]
            and runtime["depth_break"]["returned"]["should_break"] is True
            and runtime["depth_break"]["returned"]["final_distance_to_band"] == 0.17
        ),
    }
    ordered_tokens = [
        "_prepare_one_click_solver_current_iteration_eval_state_coordinator(",
        "_dispatch_one_click_solver_current_target_domain_state_from_iteration_gate_coordinator(",
        "_prepare_one_click_solver_in_band_cleanup_and_pool_state_coordinator(",
        "_trace_current_reached_target_band_solver_stop_coordinator(",
        "_dispatch_one_click_solver_tightening_depth_gate_state_from_iteration_gate_coordinator(",
    ]
    static_checks = {
        "helper_present": "def _prepare_one_click_solver_iteration_gate_state_coordinator(" in source,
        "helper_preserves_gate_order": all(token in helper for token in ordered_tokens)
        and [helper.index(token) for token in ordered_tokens] == sorted(helper.index(token) for token in ordered_tokens),
        "current_target_dispatch_delegates_current_target_domain_state": (
            "_prepare_one_click_solver_current_target_domain_state_coordinator("
            in current_target_dispatch
            and "iteration_gate_scope[" in current_target_dispatch
        ),
        "tightening_depth_dispatch_delegates_tightening_depth_gate_state": (
            "_prepare_one_click_solver_tightening_depth_gate_state_coordinator("
            in tightening_depth_dispatch
            and "iteration_gate_scope[" in tightening_depth_dispatch
        ),
        "helper_preserves_continue_and_break_flags": all(
            token in helper
            for token in (
                '"should_continue": True',
                '"should_break": True',
                '"final_distance_to_band": tightening_depth_gate_state["final_distance_to_band"]',
            )
        ),
        "helper_delegates_ready_state_packer": (
            "_build_one_click_solver_iteration_gate_ready_state_coordinator(" in helper
            and "iteration_gate_scope=locals()" in helper
        ),
        "ready_state_packer_returns_iteration_fields": all(
            token in ready_state_packer
            for token in (
                '"cur_eval": iteration_gate_scope["cur_eval"]',
                '"cur_sig": iteration_gate_scope["cur_sig"]',
                '"governing_domain_failing": iteration_gate_scope["governing_domain_failing"]',
                '"required_domain_work_active": iteration_gate_scope["required_domain_work_active"]',
                '"material_improvement_threshold": iteration_gate_scope[',
                '"tightening_meta": iteration_gate_scope["tightening_meta"]',
                '"cur_u": iteration_gate_scope["cur_u"]',
            )
        ),
        "loop_delegates_iteration_gate_state": (
            "_prepare_one_click_solver_iteration_gate_state_coordinator(" in loop_body
        ),
        "loop_rehydrates_iteration_gate_state": all(
            token in loop_body
            for token in (
                'if "max_tightening_steps" in iteration_gate_state:',
                'if "tightening_budget_extensions_used" in iteration_gate_state:',
                'if iteration_gate_state["should_continue"]:',
                'if iteration_gate_state["should_break"]:',
                'stop_reason = iteration_gate_state["stop_reason"]',
                'status = iteration_gate_state["status"]',
                'final_distance_to_band = iteration_gate_state["final_distance_to_band"]',
            )
        )
        and 'iteration_gate_state=iteration_loop_scope["iteration_gate_state"]'
        in loop_candidate_flow_dispatch,
        "solver_delegates_iteration_loop": "_dispatch_one_click_solver_iteration_loop_from_solver_runtime_setup_coordinator(" in solve_body,
        "solver_no_longer_calls_iteration_gate_directly": (
            "_prepare_one_click_solver_iteration_gate_state_coordinator(" not in solve_body
        ),
        "solver_no_longer_owns_iteration_subgates": all(token not in solve_body for token in ordered_tokens),
    }
    status = "PASS"
    if not all(static_checks.values()) or not all(runtime_checks.values()):
        status = "FAIL"
    return {
        "status": status,
        "surface": "_solve_one_click_to_target_iteration_gate_state_coordinator",
        "helper_segment": {
            "function": "_prepare_one_click_solver_iteration_gate_state_coordinator",
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
        "static_checks": static_checks,
        "runtime_checks": runtime_checks,
        "runtime": runtime,
        "product_behavior_changed": False,
        "next_safe_slice": "audit remaining solver pre-loop setup or candidate collection handoff",
    }


def write_artifacts(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now().isoformat(timespec="seconds").replace(":", "-")
    json_path = ARTIFACT_DIR / (
        f"inputs_page_solver_iteration_gate_state_coordinator_extraction_{stamp}.json"
    )
    md_path = AUDIT_DIR / (
        f"inputs_page_solver_iteration_gate_state_coordinator_extraction_{stamp}.md"
    )
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Solver Iteration Gate State Coordinator Extraction",
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
