"""Verify selected candidate acceptance gate coordinator extraction."""

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


def _run_cases(module: Any) -> dict[str, Any]:
    originals = {
        "_select_target_band_ranked_candidate": getattr(module, "_select_target_band_ranked_candidate", None),
        "_candidate_target_band_distance": getattr(module, "_candidate_target_band_distance", None),
        "_one_click_in_band_shear_cleanup_candidate_allowed": getattr(
            module, "_one_click_in_band_shear_cleanup_candidate_allowed", None
        ),
        "_resolve_target_band_selected_candidate_acceptance": getattr(
            module, "_resolve_target_band_selected_candidate_acceptance", None
        ),
        "_one_click_step_improves": getattr(module, "_one_click_step_improves", None),
        "_trace_rejected_best_candidate_solver_stop_coordinator": getattr(
            module, "_trace_rejected_best_candidate_solver_stop_coordinator", None
        ),
    }
    calls: list[dict[str, Any]] = []

    def _select(rows: list[dict[str, Any]]) -> dict[str, Any] | None:
        calls.append({"fn": "select", "count": len(rows)})
        return rows[0] if rows else None

    def _distance(eval_obj: dict[str, Any], mode_config: Any) -> float:
        return float(eval_obj.get("distance", 0.0))

    def _cleanup_allowed(cur_eval: dict[str, Any], best_eval: dict[str, Any], updates: dict[str, Any], mode_config: Any) -> bool:
        calls.append({"fn": "cleanup_allowed", "updates": dict(updates or {})})
        return bool(best_eval.get("cleanup_allowed"))

    def _step_improves(best_eval: dict[str, Any], cur_eval: dict[str, Any], mode_config: Any) -> bool:
        return bool(best_eval.get("improves"))

    def _acceptance(*, candidate_improves: bool, allow_in_band_shear_cleanup_candidate: bool) -> dict[str, Any]:
        calls.append(
            {
                "fn": "acceptance",
                "candidate_improves": candidate_improves,
                "allow_cleanup": allow_in_band_shear_cleanup_candidate,
            }
        )
        accepted = bool(candidate_improves or allow_in_band_shear_cleanup_candidate)
        return {"accepted": accepted, "stop_reason": None if accepted else "no_improving_candidate"}

    def _rejected(**kwargs: Any) -> tuple[str, str]:
        calls.append(
            {
                "fn": "rejected",
                "stop_reason": kwargs["selected_candidate_acceptance"].get("stop_reason"),
                "distance": kwargs.get("best_distance_to_band_this_iteration"),
            }
        )
        return ("no_improving_candidate", "exhausted")

    common = {
        "cur_eval": {"overview": {}},
        "mode_config": {"mode": "balanced"},
        "step_idx": 4,
        "cur_pass": False,
        "step_trace": [],
        "initial_snapshot": {"D": 600},
        "working": {"D": 620},
        "winning_label": None,
        "winning_action_type": None,
        "tightening_step_count": 2,
        "max_tightening_steps": 4,
        "no_actionable_after_full_tightening_search": False,
        "candidate_family_depth_reached": "depth",
        "trace_callback": lambda _ev, _dat: None,
    }
    try:
        module._select_target_band_ranked_candidate = _select
        module._candidate_target_band_distance = _distance
        module._one_click_in_band_shear_cleanup_candidate_allowed = _cleanup_allowed
        module._one_click_step_improves = _step_improves
        module._resolve_target_band_selected_candidate_acceptance = _acceptance
        module._trace_rejected_best_candidate_solver_stop_coordinator = _rejected

        accepted = module._handle_one_click_solver_selected_candidate_acceptance_gate_coordinator(
            scored=[{"eval": {"distance": 0.12, "improves": True}, "updates": {"D": 630}}],
            in_band_shear_cleanup_deferral={"active": False},
            **common,
        )
        rejected = module._handle_one_click_solver_selected_candidate_acceptance_gate_coordinator(
            scored=[{"eval": {"distance": 0.34, "improves": False}, "updates": {"D": 610}}],
            in_band_shear_cleanup_deferral={"active": False},
            **common,
        )
        cleanup_override = module._handle_one_click_solver_selected_candidate_acceptance_gate_coordinator(
            scored=[
                {
                    "eval": {"distance": 0.22, "improves": False, "cleanup_allowed": True},
                    "updates": {"s_lig": 140},
                }
            ],
            in_band_shear_cleanup_deferral={"active": True},
            **common,
        )
    finally:
        for name, original in originals.items():
            if original is not None:
                setattr(module, name, original)
            elif hasattr(module, name):
                delattr(module, name)

    return {
        "accepted": accepted,
        "rejected": rejected,
        "cleanup_override": cleanup_override,
        "calls": calls,
    }


def _reduced(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "best_distance_to_band_this_iteration": result["best_distance_to_band_this_iteration"],
        "selected_candidate_acceptance": result["selected_candidate_acceptance"],
        "stop_reason": result["stop_reason"],
        "status": result["status"],
        "should_break": result["should_break"],
    }


def build_payload() -> dict[str, Any]:
    source = _read(AUTO_DESIGN_COMPUTE)
    helper_start, helper_end, helper = _function_segment(
        source,
        "_handle_one_click_solver_selected_candidate_acceptance_gate_coordinator",
    )
    aggregate_start, aggregate_end, aggregate = _function_segment(
        source,
        "_handle_one_click_solver_candidate_selection_or_stop_coordinator",
    )
    solve_start, solve_end, solve_body = _function_segment(source, "_solve_one_click_to_target")
    selection_state_start, selection_state_end, selection_state_body = _function_segment(
        source, "_resolve_one_click_solver_scored_candidate_selection_state_coordinator"
    )
    _, _, post_selection_dispatch_body = _function_segment(
        source, "_dispatch_one_click_solver_post_selection_candidate_selection_state_coordinator"
    )
    _, _, post_selection_body = _function_segment(
        source, "_run_one_click_solver_iteration_post_selection_acceptance_flow_coordinator"
    )
    import inputs_page_modules.auto_design_compute as module  # noqa: E402

    runtime = _run_cases(module)
    runtime_checks = {
        "accepted_candidate_passes_through": _reduced(runtime["accepted"]) == {
            "best_distance_to_band_this_iteration": 0.12,
            "selected_candidate_acceptance": {"accepted": True, "stop_reason": None},
            "stop_reason": None,
            "status": None,
            "should_break": False,
        },
        "rejected_candidate_traces_and_breaks": _reduced(runtime["rejected"]) == {
            "best_distance_to_band_this_iteration": 0.34,
            "selected_candidate_acceptance": {
                "accepted": False,
                "stop_reason": "no_improving_candidate",
            },
            "stop_reason": "no_improving_candidate",
            "status": "exhausted",
            "should_break": True,
        },
        "cleanup_override_accepts_without_break": _reduced(runtime["cleanup_override"]) == {
            "best_distance_to_band_this_iteration": 0.22,
            "selected_candidate_acceptance": {"accepted": True, "stop_reason": None},
            "stop_reason": None,
            "status": None,
            "should_break": False,
        },
        "rejected_trace_only_for_rejected_case": [
            call for call in runtime["calls"] if call["fn"] == "rejected"
        ]
        == [
            {"fn": "rejected", "stop_reason": "no_improving_candidate", "distance": 0.34}
        ],
        "cleanup_probe_only_when_deferral_active": [
            call for call in runtime["calls"] if call["fn"] == "cleanup_allowed"
        ]
        == [{"fn": "cleanup_allowed", "updates": {"s_lig": 140}}],
    }
    static_checks = {
        "solver_delegates_scored_candidate_selection_state": (
            "_resolve_one_click_solver_scored_candidate_selection_state_coordinator("
            in post_selection_dispatch_body
        ),
        "helper_present": "def _handle_one_click_solver_selected_candidate_acceptance_gate_coordinator(" in source,
        "helper_preserves_ranked_selection": "_select_target_band_ranked_candidate(scored) or scored[0]" in helper,
        "helper_preserves_best_distance": "_candidate_target_band_distance(best[\"eval\"], mode_config)" in helper,
        "helper_preserves_shear_cleanup_override": (
            'bool(in_band_shear_cleanup_deferral.get("active"))' in helper
            and "_one_click_in_band_shear_cleanup_candidate_allowed(" in helper
        ),
        "helper_preserves_acceptance_service": "_resolve_target_band_selected_candidate_acceptance(" in helper
        and "_one_click_step_improves(best[\"eval\"], cur_eval, mode_config)" in helper,
        "helper_preserves_rejected_best_handoff": "_trace_rejected_best_candidate_solver_stop_coordinator(" in helper,
        "helper_returns_break_state": '"should_break": True' in helper and '"should_break": False' in helper,
        "aggregate_delegates_acceptance_gate": (
            "_handle_one_click_solver_selected_candidate_acceptance_gate_coordinator(" in aggregate
        ),
        "aggregate_rehydrates_acceptance_state": (
            '"best": selected_candidate_acceptance_gate_state["best"]' in aggregate
            and '"best_distance_to_band_this_iteration": selected_candidate_acceptance_gate_state[' in aggregate
            and '"should_break": selected_candidate_acceptance_gate_state["should_break"]' in aggregate
        ),
        "solver_delegates_candidate_selection_or_stop": (
            "_handle_one_click_solver_candidate_selection_or_stop_coordinator(" in selection_state_body
        ),
        "solver_rehydrates_best_distance_and_break": (
            'best = scored_candidate_selection_state["best"]' in post_selection_body
            and 'best_distance_to_band_this_iteration = scored_candidate_selection_state['
            in post_selection_body
            and 'if scored_candidate_selection_state["should_break"]:'
            in post_selection_body
        ),
        "solver_no_longer_calls_acceptance_service_inline": (
            "_resolve_target_band_selected_candidate_acceptance(" not in solve_body
        ),
    }
    status = "PASS"
    if not all(static_checks.values()) or not all(runtime_checks.values()):
        status = "FAIL"
    return {
        "status": status,
        "surface": "_solve_one_click_to_target_selected_candidate_acceptance_gate_coordinator",
        "helper_segment": {
            "function": "_handle_one_click_solver_selected_candidate_acceptance_gate_coordinator",
            "start_line": helper_start,
            "end_line": helper_end,
            "line_count": helper_end - helper_start + 1,
        },
        "aggregate_segment": {
            "function": "_handle_one_click_solver_candidate_selection_or_stop_coordinator",
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
        "runtime_checks": runtime_checks,
        "runtime": runtime,
        "product_behavior_changed": False,
        "next_safe_slice": "extract accepted best candidate trace/apply evaluation coordinator",
    }


def write_artifacts(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now().isoformat(timespec="seconds").replace(":", "-")
    json_path = ARTIFACT_DIR / (
        f"inputs_page_solver_selected_candidate_acceptance_gate_coordinator_extraction_{stamp}.json"
    )
    md_path = AUDIT_DIR / (
        f"inputs_page_solver_selected_candidate_acceptance_gate_coordinator_extraction_{stamp}.md"
    )
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Solver Selected Candidate Acceptance Gate Coordinator Extraction",
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
