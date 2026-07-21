"""Verify one-click solver growth-blocked pre-eval prune coordinator extraction."""

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
    original_trace = getattr(module, "_trace_candidate_eval_pre_eval_rejection_solver_coordinator", None)
    calls: list[dict[str, Any]] = []

    def _trace(**kwargs: Any) -> None:
        calls.append(
            {
                "reason": kwargs.get("rejection_reason"),
                "family": kwargs.get("family_hint"),
                "governing_domain": kwargs.get("governing_domain"),
                "updates": dict(kwargs.get("norm_u") or {}),
                "tightening": bool(kwargs.get("tightening_mode_active")),
            }
        )

    try:
        module._trace_candidate_eval_pre_eval_rejection_solver_coordinator = _trace
        pruned = module._handle_one_click_solver_growth_blocked_pre_eval_prune_candidate_coordinator(
            step_idx=1,
            rc={"title": "Growth candidate", "action_type": "increase"},
            norm_u={"D": 700},
            direction={"is_growth_only": True},
            tightening_mode_active=True,
            reduction_candidates_considered=2,
            governing_domain="bending",
            family_hint="geometry",
            growth_candidates_rejected_in_tightening=4,
            trace_callback=lambda *_args, **_kwargs: None,
        )
        no_reductions = module._handle_one_click_solver_growth_blocked_pre_eval_prune_candidate_coordinator(
            step_idx=2,
            rc={"title": "Growth without reductions", "action_type": "increase"},
            norm_u={"D": 700},
            direction={"is_growth_only": True},
            tightening_mode_active=True,
            reduction_candidates_considered=0,
            governing_domain="bending",
            family_hint="geometry",
            growth_candidates_rejected_in_tightening=4,
            trace_callback=lambda *_args, **_kwargs: None,
        )
        not_tightening = module._handle_one_click_solver_growth_blocked_pre_eval_prune_candidate_coordinator(
            step_idx=3,
            rc={"title": "Normal growth", "action_type": "increase"},
            norm_u={"D": 700},
            direction={"is_growth_only": True},
            tightening_mode_active=False,
            reduction_candidates_considered=2,
            governing_domain="bending",
            family_hint="geometry",
            growth_candidates_rejected_in_tightening=4,
            trace_callback=lambda *_args, **_kwargs: None,
        )
        not_growth = module._handle_one_click_solver_growth_blocked_pre_eval_prune_candidate_coordinator(
            step_idx=4,
            rc={"title": "Reduction", "action_type": "reduce"},
            norm_u={"D": 600},
            direction={"is_growth_only": False},
            tightening_mode_active=True,
            reduction_candidates_considered=2,
            governing_domain="bending",
            family_hint="geometry",
            growth_candidates_rejected_in_tightening=4,
            trace_callback=lambda *_args, **_kwargs: None,
        )
    finally:
        if original_trace is not None:
            module._trace_candidate_eval_pre_eval_rejection_solver_coordinator = original_trace
        elif hasattr(module, "_trace_candidate_eval_pre_eval_rejection_solver_coordinator"):
            delattr(module, "_trace_candidate_eval_pre_eval_rejection_solver_coordinator")

    return {
        "pruned": pruned,
        "no_reductions": no_reductions,
        "not_tightening": not_tightening,
        "not_growth": not_growth,
        "calls": calls,
    }


def build_payload() -> dict[str, Any]:
    source = _read(AUTO_DESIGN_COMPUTE)
    helper_start, helper_end, helper = _function_segment(
        source,
        "_handle_one_click_solver_growth_blocked_pre_eval_prune_candidate_coordinator",
    )
    solve_start, solve_end, solve_body = _function_segment(source, "_solve_one_click_to_target")
    import inputs_page_modules.auto_design_compute as module  # noqa: E402

    runtime = _run_cases(module)
    unchanged = {
        "growth_candidates_rejected_in_tightening": 4,
        "should_continue": False,
    }
    runtime_checks = {
        "growth_prune_preserved": runtime["pruned"] == {
            "growth_candidates_rejected_in_tightening": 5,
            "should_continue": True,
        },
        "no_reduction_candidates_pass_through": runtime["no_reductions"] == unchanged,
        "not_tightening_pass_through": runtime["not_tightening"] == unchanged,
        "not_growth_pass_through": runtime["not_growth"] == unchanged,
        "trace_reason_preserved": runtime["calls"] == [
            {
                "reason": "growth_blocked_in_tightening_mode",
                "family": "geometry",
                "governing_domain": "bending",
                "updates": {"D": 700},
                "tightening": True,
            }
        ],
    }
    static_checks = {
        "helper_present": "def _handle_one_click_solver_growth_blocked_pre_eval_prune_candidate_coordinator("
        in source,
        "helper_preserves_gate": "tightening_mode_active" in helper
        and "reduction_candidates_considered > 0" in helper
        and 'bool(direction.get("is_growth_only"))' in helper,
        "helper_preserves_counter_and_trace": "growth_candidates_rejected_in_tightening += 1" in helper
        and '"growth_blocked_in_tightening_mode"' in helper
        and "_trace_candidate_eval_pre_eval_rejection_solver_coordinator(" in helper,
        "solver_delegates_growth_prune_branch": (
            "_handle_one_click_solver_growth_blocked_pre_eval_prune_candidate_coordinator(" in solve_body
        ),
        "solver_rehydrates_counter": (
            'growth_candidates_rejected_in_tightening = growth_prune_state[' in solve_body
        ),
        "solver_preserves_continue_gate": 'if growth_prune_state["should_continue"]:' in solve_body,
        "solver_no_longer_inlines_growth_prune_reason": (
            '"growth_blocked_in_tightening_mode"' not in solve_body
        ),
    }
    status = "PASS"
    if not all(static_checks.values()) or not all(runtime_checks.values()):
        status = "FAIL"
    return {
        "status": status,
        "surface": "_solve_one_click_to_target_growth_blocked_pre_eval_prune_candidate_coordinator",
        "helper_segment": {
            "function": "_handle_one_click_solver_growth_blocked_pre_eval_prune_candidate_coordinator",
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
        "static_checks": static_checks,
        "runtime_checks": runtime_checks,
        "runtime": runtime,
        "product_behavior_changed": False,
        "next_safe_slice": "extract iteration-start state/trace handoff after pre-eval pruning",
    }


def write_artifacts(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now().isoformat(timespec="seconds").replace(":", "-")
    json_path = ARTIFACT_DIR / (
        f"inputs_page_solver_growth_blocked_pre_eval_prune_candidate_coordinator_extraction_{stamp}.json"
    )
    md_path = AUDIT_DIR / (
        f"inputs_page_solver_growth_blocked_pre_eval_prune_candidate_coordinator_extraction_{stamp}.md"
    )
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Solver Growth-Blocked Pre-Eval Prune Candidate Coordinator Extraction",
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
