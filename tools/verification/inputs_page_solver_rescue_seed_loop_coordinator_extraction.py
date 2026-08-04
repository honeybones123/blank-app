"""Verify rescue seed loop solver coordinator extraction."""

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


def _patch(module: Any, replacements: dict[str, Any]):
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


def _run_inactive_case(module: Any) -> dict[str, Any]:
    rescue_debug = {"marker": "kept"}
    returned = module._prepare_one_click_solver_rescue_seed_loop_state_coordinator(
        rescue_should_enter=False,
        rescue_family="shear",
        rescue_tier_requested="wide",
        rescue_entry_reason="blocked",
        initial_snapshot={"D": 600},
        max_steps=6,
        debug_enabled=False,
        trace_run_id="rid",
        trace_source="one_click_solve",
        attempted_seed_keys=set(),
        rescue_debug=rescue_debug,
        final_eval={"overview": {"worst_util": 1.2}},
        mode_config={"target": "band"},
        target_domains_for_band=["shear"],
        trace_callback=lambda ev, dat: None,
    )
    return {
        "returned": returned,
        "rescue_debug": rescue_debug,
        "matches": returned == {"should_return_rescue_result": False, "rescue_result": None}
        and rescue_debug == {"marker": "kept"},
    }


def _run_no_effective_seed_case(module: Any) -> dict[str, Any]:
    calls: list[dict[str, Any]] = []
    attempted_seed_keys: set[str] = set()
    rescue_debug: dict[str, Any] = {}

    def _validate_seed(initial_snapshot: dict, updates: dict):
        if updates.get("legal"):
            return True, None, {"seeded": dict(updates)}
        return False, "outside_limits", {}

    def _trace_attempt(**kwargs: Any) -> None:
        calls.append({"name": "attempt", "kwargs": dict(kwargs)})

    def _trace_ineffective(**kwargs: Any) -> None:
        calls.append({"name": "ineffective", "kwargs": dict(kwargs)})

    replacements = {
        "RESCUE_SEED_LIBRARY": {
            "shear": {
                "bad": {"key": "bad-seed", "updates": {"legal": False}},
                "weak": {"key": "weak-seed", "updates": {"legal": True}},
            }
        },
        "_rescue_mode_seed_order": lambda tier: ["bad", "weak"],
        "_rescue_mode_validate_seed": _validate_seed,
        "_trace_rescue_seed_attempt_solver_coordinator": _trace_attempt,
        "_trace_rescue_seed_ineffective_solver_coordinator": _trace_ineffective,
        "_solve_one_click_to_target": lambda *args, **kwargs: {
            "final_state_preview": {"D": 610},
            "one_click_solver_debug": {},
        },
        "_rescue_mode_eval_for_result": lambda result: {"overview": {"worst_util": 1.1}},
        "_rescue_mode_path_improved": lambda rescue_eval, final_eval, mode_config: False,
    }
    originals = _patch(module, replacements)
    try:
        returned = module._prepare_one_click_solver_rescue_seed_loop_state_coordinator(
            rescue_should_enter=True,
            rescue_family="shear",
            rescue_tier_requested="wide",
            rescue_entry_reason="blocked",
            initial_snapshot={"D": 600},
            max_steps=6,
            debug_enabled=False,
            trace_run_id="rid",
            trace_source="one_click_solve",
            attempted_seed_keys=attempted_seed_keys,
            rescue_debug=rescue_debug,
            final_eval={"overview": {"worst_util": 1.2}},
            mode_config={"target": "band"},
            target_domains_for_band=["shear"],
            trace_callback=lambda ev, dat: None,
        )
    finally:
        _restore(module, originals)

    return {
        "returned": returned,
        "attempted_seed_keys": sorted(attempted_seed_keys),
        "rescue_debug": rescue_debug,
        "calls": calls,
        "matches": (
            returned["should_return_rescue_result"] is False
            and sorted(attempted_seed_keys) == ["bad-seed", "weak-seed"]
            and rescue_debug["rescue_mode_tier_used"] == "weak"
            and rescue_debug["rescue_mode_seed_key"] == "weak-seed"
            and rescue_debug["rescue_mode_seed_legal"] is True
            and rescue_debug["rescue_mode_fallback_count"] == 1
            and rescue_debug["rescue_mode_ineffective_seeds"] == ["weak-seed"]
            and rescue_debug["rescue_mode_effective_seed_found"] is False
            and rescue_debug["rescue_mode_exit_reason"] == "no_legal_effective_seed_found"
            and [call["name"] for call in calls] == ["attempt", "attempt", "ineffective"]
        ),
    }


def _run_effective_seed_case(module: Any) -> dict[str, Any]:
    calls: list[dict[str, Any]] = []
    rescue_debug: dict[str, Any] = {}

    def _trace_attempt(**kwargs: Any) -> None:
        calls.append({"name": "attempt", "kwargs": dict(kwargs)})

    def _trace_exit(**kwargs: Any) -> None:
        calls.append({"name": "exit", "kwargs": dict(kwargs)})

    def _attach_domains(eval_result: dict, target_domains: list[str], mode_config: dict) -> None:
        eval_result["attached_target_domains"] = list(target_domains)

    replacements = {
        "RESCUE_SEED_LIBRARY": {
            "shear": {
                "wide": {"key": "effective-seed", "updates": {"D": 650}},
            }
        },
        "_rescue_mode_seed_order": lambda tier: ["wide"],
        "_rescue_mode_validate_seed": lambda initial_snapshot, updates: (True, None, {"seeded": dict(updates)}),
        "_trace_rescue_seed_attempt_solver_coordinator": _trace_attempt,
        "_trace_rescue_exit_solver_coordinator": _trace_exit,
        "_solve_one_click_to_target": lambda *args, **kwargs: {
            "final_state_preview": {"D": 650},
            "one_click_solver_debug": {"inner": "debug"},
            "status": "stopped",
            "stop_reason": "max_steps",
        },
        "_rescue_mode_eval_for_result": lambda result: {"overview": {"worst_util": 0.96}},
        "_rescue_mode_path_improved": lambda rescue_eval, final_eval, mode_config: True,
        "_guidance_state_snapshot": lambda state: dict(state),
        "_one_click_diff_accumulated_updates": lambda initial, final: {"D": 50},
        "_build_canonical_design_state_pack": lambda state: {"state": state},
        "evaluate_candidate_full": lambda *args, **kwargs: {
            "overview": {"all_key_pass": True, "worst_util": 0.91},
            "state": {"D": 650, "evaluated": True},
        },
        "_one_click_target_domains_for_eval": lambda domains, updates: list(domains),
        "_one_click_attach_eval_target_domains": _attach_domains,
        "_candidate_in_target_band": lambda eval_result, mode_config: True,
        "_one_click_has_unresolved_spacing_envelope_fail": lambda eval_result: False,
    }
    originals = _patch(module, replacements)
    try:
        returned = module._prepare_one_click_solver_rescue_seed_loop_state_coordinator(
            rescue_should_enter=True,
            rescue_family="shear",
            rescue_tier_requested="wide",
            rescue_entry_reason="blocked",
            initial_snapshot={"D": 600},
            max_steps=6,
            debug_enabled=True,
            trace_run_id="rid",
            trace_source="one_click_solve",
            attempted_seed_keys=set(),
            rescue_debug=rescue_debug,
            final_eval={"overview": {"worst_util": 1.2}},
            mode_config={"target": "band"},
            target_domains_for_band=["shear"],
            trace_callback=lambda ev, dat: None,
        )
    finally:
        _restore(module, originals)

    rescue_result = returned["rescue_result"]
    rescue_dbg = rescue_result["one_click_solver_debug"]
    return {
        "returned": returned,
        "rescue_debug": rescue_debug,
        "calls": calls,
        "matches": (
            returned["should_return_rescue_result"] is True
            and rescue_result["status"] == "solved"
            and rescue_result["stop_reason"] == "reached_target_band"
            and rescue_result["final_updates"] == {"D": 50}
            and rescue_result["final_worst_util"] == 0.91
            and rescue_result["all_key_pass"] is True
            and rescue_result["reached_target_band"] is True
            and rescue_result["final_state_preview"] == {"D": 650, "evaluated": True}
            and rescue_dbg["inner"] == "debug"
            and rescue_dbg["rescue_mode_effective_seed_found"] is True
            and rescue_dbg["rescue_mode_exit_reason"] == "effective_seed_handoff_to_normal_optimizer"
            and [call["name"] for call in calls] == ["attempt", "exit"]
        ),
    }


def build_payload() -> dict[str, Any]:
    source = _read(AUTO_DESIGN_COMPUTE)
    helper_start, helper_end, helper = _function_segment(
        source,
        "_prepare_one_click_solver_rescue_seed_loop_state_coordinator",
    )
    handoff_start, handoff_end, handoff = _function_segment(
        source,
        "_complete_one_click_solver_effective_rescue_seed_handoff_coordinator",
    )
    finalization_start, finalization_end, finalization = _function_segment(
        source,
        "_finalize_one_click_solver_result_coordinator",
    )
    _, _, after_final_eval_helper = _function_segment(
        source,
        "_run_one_click_solver_finalization_after_final_evaluation_coordinator",
    )
    _, _, rescue_seed_dispatch = _function_segment(
        source,
        "_dispatch_one_click_solver_rescue_seed_loop_from_finalization_coordinator",
    )
    _, _, rescue_seed_result_dispatch = _function_segment(
        source,
        "_dispatch_one_click_solver_rescue_seed_result_from_finalization_coordinator",
    )
    solve_start, solve_end, solve_body = _function_segment(source, "_solve_one_click_to_target")
    _, _, finish_body = _function_segment(
        source,
        "_finish_one_click_solver_iteration_loop_result_coordinator",
    )

    import inputs_page_modules.auto_design_compute as module  # noqa: E402

    inactive = _run_inactive_case(module)
    no_effective = _run_no_effective_seed_case(module)
    effective = _run_effective_seed_case(module)
    runtime = {
        "inactive_falls_through_without_mutation": inactive["matches"],
        "no_effective_seed_preserves_fallthrough_debug": no_effective["matches"],
        "effective_seed_returns_rescue_result": effective["matches"],
    }
    static_checks = {
        "helper_present": "def _prepare_one_click_solver_rescue_seed_loop_state_coordinator(" in source,
        "helper_preserves_seed_order": "_rescue_mode_seed_order(rescue_tier_requested)" in helper,
        "helper_preserves_attempted_seed_skip": "if seed_key in attempted_seed_keys:" in helper,
        "helper_preserves_fallback_count": "fallback_count += 1" in helper,
        "helper_preserves_seed_validation": "_rescue_mode_validate_seed(initial_snapshot, seed_updates)" in helper,
        "helper_delegates_seed_attempt_trace": "_trace_rescue_seed_attempt_solver_coordinator(" in helper,
        "helper_preserves_recursive_solver_call": "_solve_one_click_to_target(" in helper,
        "helper_disables_recursive_rescue": "_rescue_enabled=False" in helper,
        "helper_preserves_improvement_gate": "_rescue_mode_path_improved(rescue_eval, final_eval, mode_config)" in helper,
        "helper_delegates_ineffective_trace": "_trace_rescue_seed_ineffective_solver_coordinator(" in helper,
        "helper_delegates_effective_rescue_seed_handoff": (
            "_complete_one_click_solver_effective_rescue_seed_handoff_coordinator("
            in helper
        ),
        "handoff_delegates_rescue_exit_trace": "_trace_rescue_exit_solver_coordinator(" in handoff,
        "handoff_preserves_outer_result_eval": "rescue_mode_outer_result_eval" in handoff,
        "handoff_preserves_effective_seed_debug": '"rescue_mode_effective_seed_found": True' in handoff,
        "helper_preserves_no_effective_exit_reason": '"no_legal_effective_seed_found"' in helper,
        "finalization_delegates_rescue_seed_loop_dispatch": (
            "_dispatch_one_click_solver_rescue_seed_result_from_finalization_coordinator("
            in after_final_eval_helper
        ),
        "rescue_seed_result_dispatch_delegates_rescue_seed_loop_dispatch": (
            "_dispatch_one_click_solver_rescue_seed_loop_from_finalization_coordinator("
            in rescue_seed_result_dispatch
            and "finalization_scope=finalization_scope" in rescue_seed_result_dispatch
        ),
        "rescue_seed_dispatch_delegates_rescue_seed_loop": (
            "_prepare_one_click_solver_rescue_seed_loop_state_coordinator("
            in rescue_seed_dispatch
            and "finalization_scope[" in rescue_seed_dispatch
        ),
        "finish_delegates_finalization": "_finalize_one_click_solver_result_coordinator(" in finish_body,
        "solver_delegates_loop_result_finish": "_finish_one_click_solver_iteration_loop_result_coordinator("
        in solve_body,
        "finalization_returns_rescue_result_from_coordinator": (
            "if should_return_rescue_result:" in after_final_eval_helper
            and "return rescue_result" in after_final_eval_helper
            and 'rescue_seed_loop_state["should_return_rescue_result"]'
            in rescue_seed_result_dispatch
            and 'rescue_seed_loop_state["rescue_result"]' in rescue_seed_result_dispatch
        ),
        "solver_no_longer_inlines_seed_order": "_rescue_mode_seed_order(rescue_tier_requested)" not in solve_body,
        "solver_no_longer_inlines_recursive_rescue": "_rescue_enabled=False" not in solve_body,
    }
    status = "PASS"
    if not all(static_checks.values()) or not all(runtime.values()):
        status = "FAIL"
    return {
        "status": status,
        "surface": "_solve_one_click_to_target_rescue_seed_loop_coordinator",
        "helper_segment": {
            "function": "_prepare_one_click_solver_rescue_seed_loop_state_coordinator",
            "start_line": helper_start,
            "end_line": helper_end,
            "line_count": helper_end - helper_start + 1,
        },
        "handoff_segment": {
            "function": "_complete_one_click_solver_effective_rescue_seed_handoff_coordinator",
            "start_line": handoff_start,
            "end_line": handoff_end,
            "line_count": handoff_end - handoff_start + 1,
        },
        "finalization_segment": {
            "function": "_finalize_one_click_solver_result_coordinator",
            "start_line": finalization_start,
            "end_line": finalization_end,
            "line_count": finalization_end - finalization_start + 1,
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
        "next_safe_slice": "extract rescue result publication/finalization coordinator",
    }


def write_artifacts(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now().isoformat(timespec="seconds").replace(":", "-")
    json_path = ARTIFACT_DIR / f"inputs_page_solver_rescue_seed_loop_coordinator_extraction_{stamp}.json"
    md_path = AUDIT_DIR / f"inputs_page_solver_rescue_seed_loop_coordinator_extraction_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Solver Rescue Seed Loop Coordinator Extraction",
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
