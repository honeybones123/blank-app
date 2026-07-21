"""Verify candidate selection-or-stop solver coordinator extraction."""

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
        "_handle_one_click_solver_no_scored_stop_branch_coordinator": getattr(
            module,
            "_handle_one_click_solver_no_scored_stop_branch_coordinator",
            None,
        ),
        "_handle_one_click_solver_selected_candidate_acceptance_gate_coordinator": getattr(
            module,
            "_handle_one_click_solver_selected_candidate_acceptance_gate_coordinator",
            None,
        ),
    }
    calls: list[dict[str, Any]] = []
    active = {"case": "accepted"}

    def _no_scored(**kwargs: Any) -> dict[str, Any]:
        calls.append({"fn": "no_scored", "case": active["case"], "scored": list(kwargs["scored"])})
        if active["case"] == "no_scored":
            return {
                "stop_reason": "no_actionable_candidates",
                "status": "exhausted",
                "final_distance_to_band": 0.44,
                "no_actionable_after_full_tightening_search": True,
                "should_break": True,
            }
        return {
            "stop_reason": None,
            "status": None,
            "final_distance_to_band": None,
            "no_actionable_after_full_tightening_search": kwargs[
                "no_actionable_after_full_tightening_search"
            ],
            "should_break": False,
        }

    def _acceptance(**kwargs: Any) -> dict[str, Any]:
        calls.append(
            {
                "fn": "acceptance",
                "case": active["case"],
                "step_idx": kwargs["step_idx"],
                "deferral": dict(kwargs["in_band_shear_cleanup_deferral"]),
            }
        )
        if active["case"] == "rejected":
            return {
                "best": {"label": "B"},
                "best_distance_to_band_this_iteration": 0.31,
                "selected_candidate_acceptance": {
                    "accepted": False,
                    "stop_reason": "no_improving_candidate",
                },
                "stop_reason": "no_improving_candidate",
                "status": "exhausted",
                "should_break": True,
            }
        return {
            "best": {"label": "A"},
            "best_distance_to_band_this_iteration": 0.12,
            "selected_candidate_acceptance": {"accepted": True, "stop_reason": None},
            "stop_reason": None,
            "status": None,
            "should_break": False,
        }

    common = {
        "scored": [{"candidate": True}],
        "cur_eval": {"overview": {}},
        "mode_config": {"mode": "balanced"},
        "step_idx": 5,
        "cur_pass": False,
        "step_trace": [{"step": 4}],
        "initial_snapshot": {"D": 600},
        "working": {"D": 630},
        "governing_domain": "shear",
        "tightening_mode_active": True,
        "rejected_as_non_material_improvement": 2,
        "no_actionable_after_full_tightening_search": False,
        "cur_ib": False,
        "winning_label": None,
        "winning_action_type": None,
        "tightening_step_count": 3,
        "max_tightening_steps": 7,
        "candidate_family_depth_reached": "spacing",
        "in_band_shear_cleanup_deferral": {"active": True},
        "trace_callback": lambda *_args, **_kwargs: None,
    }
    try:
        module._handle_one_click_solver_no_scored_stop_branch_coordinator = _no_scored
        module._handle_one_click_solver_selected_candidate_acceptance_gate_coordinator = _acceptance

        active["case"] = "no_scored"
        no_scored = module._handle_one_click_solver_candidate_selection_or_stop_coordinator(
            **{**common, "scored": []}
        )
        active["case"] = "accepted"
        accepted = module._handle_one_click_solver_candidate_selection_or_stop_coordinator(**common)
        active["case"] = "rejected"
        rejected = module._handle_one_click_solver_candidate_selection_or_stop_coordinator(**common)
    finally:
        for name, original in originals.items():
            if original is not None:
                setattr(module, name, original)
            elif hasattr(module, name):
                delattr(module, name)

    return {
        "no_scored": no_scored,
        "accepted": accepted,
        "rejected": rejected,
        "calls": calls,
    }


def build_payload() -> dict[str, Any]:
    source = _read(AUTO_DESIGN_COMPUTE)
    aggregate_start, aggregate_end, aggregate = _function_segment(
        source,
        "_handle_one_click_solver_candidate_selection_or_stop_coordinator",
    )
    solve_start, solve_end, solve_body = _function_segment(source, "_solve_one_click_to_target")
    selection_state_start, selection_state_end, selection_state_body = _function_segment(
        source, "_resolve_one_click_solver_scored_candidate_selection_state_coordinator"
    )
    import inputs_page_modules.auto_design_compute as module  # noqa: E402

    runtime = _run_cases(module)
    runtime_checks = {
        "no_scored_break_skips_acceptance": (
            runtime["no_scored"]["should_break"] is True
            and runtime["no_scored"]["stop_reason"] == "no_actionable_candidates"
            and runtime["no_scored"]["final_distance_to_band"] == 0.44
            and runtime["calls"][0]["fn"] == "no_scored"
            and runtime["calls"][1]["fn"] == "no_scored"
        ),
        "accepted_candidate_continues": runtime["accepted"] == {
            "best": {"label": "A"},
            "best_distance_to_band_this_iteration": 0.12,
            "selected_candidate_acceptance": {"accepted": True, "stop_reason": None},
            "stop_reason": None,
            "status": None,
            "final_distance_to_band": None,
            "no_actionable_after_full_tightening_search": False,
            "should_break": False,
        },
        "rejected_candidate_breaks": runtime["rejected"] == {
            "best": {"label": "B"},
            "best_distance_to_band_this_iteration": 0.31,
            "selected_candidate_acceptance": {
                "accepted": False,
                "stop_reason": "no_improving_candidate",
            },
            "stop_reason": "no_improving_candidate",
            "status": "exhausted",
            "final_distance_to_band": None,
            "no_actionable_after_full_tightening_search": False,
            "should_break": True,
        },
        "call_order_preserved": [c["fn"] for c in runtime["calls"]] == [
            "no_scored",
            "no_scored",
            "acceptance",
            "no_scored",
            "acceptance",
        ],
    }
    static_checks = {
        "solver_delegates_scored_candidate_selection_state": (
            "_resolve_one_click_solver_scored_candidate_selection_state_coordinator(" in solve_body
        ),
        "aggregate_present": "def _handle_one_click_solver_candidate_selection_or_stop_coordinator(" in source,
        "aggregate_delegates_no_scored_stop_first": (
            aggregate.find("_handle_one_click_solver_no_scored_stop_branch_coordinator(")
            < aggregate.find("_handle_one_click_solver_selected_candidate_acceptance_gate_coordinator(")
        ),
        "aggregate_preserves_no_scored_break": (
            'if no_scored_stop_branch_state["should_break"]:' in aggregate
            and '"final_distance_to_band": no_scored_stop_branch_state["final_distance_to_band"]' in aggregate
        ),
        "aggregate_preserves_selected_acceptance_handoff": (
            "_handle_one_click_solver_selected_candidate_acceptance_gate_coordinator(" in aggregate
            and '"best": selected_candidate_acceptance_gate_state["best"]' in aggregate
        ),
        "solver_delegates_aggregate": (
            "_handle_one_click_solver_candidate_selection_or_stop_coordinator(" in selection_state_body
        ),
        "solver_no_longer_delegates_no_scored_directly": (
            "_handle_one_click_solver_no_scored_stop_branch_coordinator(" not in solve_body
        ),
        "solver_no_longer_delegates_acceptance_directly": (
            "_handle_one_click_solver_selected_candidate_acceptance_gate_coordinator(" not in solve_body
        ),
    }
    status = "PASS"
    if not all(static_checks.values()) or not all(runtime_checks.values()):
        status = "FAIL"
    return {
        "status": status,
        "surface": "_solve_one_click_to_target_candidate_selection_or_stop_coordinator",
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
        "product_behavior_changed": False,
        "next_safe_slice": "extract accepted best candidate trace/apply evaluation handoff",
    }


def write_artifacts(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now().isoformat(timespec="seconds").replace(":", "-")
    json_path = ARTIFACT_DIR / (
        f"inputs_page_solver_candidate_selection_or_stop_coordinator_extraction_{stamp}.json"
    )
    md_path = AUDIT_DIR / (
        f"inputs_page_solver_candidate_selection_or_stop_coordinator_extraction_{stamp}.md"
    )
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Solver Candidate Selection Or Stop Coordinator Extraction",
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
