"""Verify one-click solver non-material candidate gate coordinator extraction."""

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
    original_trace = getattr(module, "_trace_candidate_eval_non_material_solver_coordinator", None)
    trace_calls: list[dict[str, Any]] = []

    def _trace(**kwargs: Any) -> None:
        trace_calls.append(
            {
                "new_d": kwargs.get("new_d"),
                "governing_domain": kwargs.get("governing_domain"),
                "family_hint": kwargs.get("family_hint"),
            }
        )

    common = {
        "peval": {"overview": {}},
        "mode_config": {"mode": "balanced"},
        "step_idx": 6,
        "rc": {"title": "candidate"},
        "norm_u": {"D": 610},
        "new_d": 0.095,
        "old_d": 0.100,
        "direction": {"is_reduction_candidate": True},
        "family_hint": "depth",
        "tightening_mode_active": True,
        "material_improvement_threshold": 0.010,
        "shear_remove_links_candidate_dropped_reason": None,
        "shear_remove_links_candidate_materiality": "not_evaluated",
        "rejected_as_non_material_improvement": 7,
        "trace_callback": lambda _ev, _dat: None,
    }
    try:
        module._trace_candidate_eval_non_material_solver_coordinator = _trace
        bending_reject = module._handle_one_click_solver_candidate_non_material_gate_coordinator(
            **common,
            governing_domain="bending",
            remove_links_candidate=False,
            remove_links_truth_ok=False,
        )
        shear_remove_links_reject = module._handle_one_click_solver_candidate_non_material_gate_coordinator(
            **common,
            governing_domain="shear",
            remove_links_candidate=True,
            remove_links_truth_ok=False,
        )
        shear_remove_links_truth_bypass = module._handle_one_click_solver_candidate_non_material_gate_coordinator(
            **common,
            governing_domain="shear",
            remove_links_candidate=True,
            remove_links_truth_ok=True,
        )
        material_improvement_pass = module._handle_one_click_solver_candidate_non_material_gate_coordinator(
            **{**common, "new_d": 0.080},
            governing_domain="bending",
            remove_links_candidate=False,
            remove_links_truth_ok=False,
        )
        not_tightening_pass = module._handle_one_click_solver_candidate_non_material_gate_coordinator(
            **{**common, "tightening_mode_active": False},
            governing_domain="bending",
            remove_links_candidate=False,
            remove_links_truth_ok=False,
        )
    finally:
        if original_trace is not None:
            module._trace_candidate_eval_non_material_solver_coordinator = original_trace

    return {
        "bending_reject": bending_reject,
        "shear_remove_links_reject": shear_remove_links_reject,
        "shear_remove_links_truth_bypass": shear_remove_links_truth_bypass,
        "material_improvement_pass": material_improvement_pass,
        "not_tightening_pass": not_tightening_pass,
        "trace_calls": trace_calls,
    }


def build_payload() -> dict[str, Any]:
    source = _read(AUTO_DESIGN_COMPUTE)
    helper_start, helper_end, helper = _function_segment(
        source,
        "_handle_one_click_solver_candidate_non_material_gate_coordinator",
    )
    chain_start, chain_end, chain_body = _function_segment(
        source,
        "_handle_one_click_solver_candidate_direction_material_gate_chain_coordinator",
    )
    solve_start, solve_end, solve_body = _function_segment(source, "_solve_one_click_to_target")
    scoring_loop_start, scoring_loop_end, scoring_loop_body = _function_segment(
        source, "_run_one_click_solver_candidate_scoring_loop_coordinator"
    )
    _, _, post_metric_body = _function_segment(
        source, "_run_one_click_solver_single_candidate_post_metric_scoring_flow_coordinator"
    )
    _, _, direction_material_dispatch_body = _function_segment(
        source,
        "_dispatch_one_click_solver_candidate_direction_material_gate_chain_from_post_metric_coordinator",
    )
    import inputs_page_modules.auto_design_compute as module  # noqa: E402

    runtime = _run_cases(module)
    base_pass = {
        "rejected_as_non_material_improvement": 7,
        "shear_remove_links_candidate_dropped_reason": None,
        "shear_remove_links_candidate_materiality": "not_evaluated",
        "should_continue": False,
    }
    runtime_checks = {
        "bending_rejects_and_increments_counter": runtime["bending_reject"] == {
            "rejected_as_non_material_improvement": 8,
            "shear_remove_links_candidate_dropped_reason": None,
            "shear_remove_links_candidate_materiality": "not_evaluated",
            "should_continue": True,
        },
        "shear_remove_links_reject_updates_reason_and_materiality": runtime["shear_remove_links_reject"] == {
            "rejected_as_non_material_improvement": 8,
            "shear_remove_links_candidate_dropped_reason": "non_material_improvement",
            "shear_remove_links_candidate_materiality": "non_material",
            "should_continue": True,
        },
        "shear_remove_links_truth_bypass_preserved": runtime["shear_remove_links_truth_bypass"] == base_pass,
        "material_improvement_pass_preserved": runtime["material_improvement_pass"] == base_pass,
        "not_tightening_pass_preserved": runtime["not_tightening_pass"] == base_pass,
        "trace_only_for_rejections": runtime["trace_calls"] == [
            {"new_d": 0.095, "governing_domain": "bending", "family_hint": "depth"},
            {"new_d": 0.095, "governing_domain": "shear", "family_hint": "depth"},
        ],
    }
    static_checks = {
        "solver_delegates_iteration_loop": (
            "_dispatch_one_click_solver_iteration_loop_from_solver_runtime_setup_coordinator("
            in solve_body
        ),
        "helper_present": "def _handle_one_click_solver_candidate_non_material_gate_coordinator(" in source,
        "helper_preserves_materiality_gate": (
            "tightening_mode_active and (old_d - new_d) < material_improvement_threshold" in helper
        ),
        "helper_preserves_remove_links_truth_exception": (
            'governing_domain == "shear" and remove_links_candidate and remove_links_truth_ok' in helper
        ),
        "helper_preserves_shear_remove_links_reason_updates": (
            'shear_remove_links_candidate_dropped_reason = "non_material_improvement"' in helper
            and 'shear_remove_links_candidate_materiality = "non_material"' in helper
        ),
        "helper_preserves_counter_and_trace": "rejected_as_non_material_improvement += 1" in helper
        and "_trace_candidate_eval_non_material_solver_coordinator(" in helper,
        "chain_delegates_non_material_gate": (
            "_handle_one_click_solver_candidate_non_material_gate_coordinator(" in chain_body
        ),
        "chain_rehydrates_counter_reason_materiality_and_continue": (
            'rejected_as_non_material_improvement = non_material_gate_state[' in chain_body
            and 'shear_remove_links_candidate_dropped_reason = non_material_gate_state[' in chain_body
            and 'shear_remove_links_candidate_materiality = non_material_gate_state[' in chain_body
            and '"should_continue": non_material_gate_state["should_continue"]' in chain_body
        ),
        "solver_delegates_direction_material_gate_chain": (
            "_dispatch_one_click_solver_candidate_direction_material_gate_chain_from_post_metric_coordinator("
            in post_metric_body
            and "_handle_one_click_solver_candidate_direction_material_gate_chain_coordinator("
            in direction_material_dispatch_body
        ),
        "solver_rehydrates_chain_counter_reason_materiality_and_continue": (
            'rejected_as_non_material_improvement = direction_material_gate_chain_state[' in post_metric_body
            and 'shear_remove_links_candidate_dropped_reason = direction_material_gate_chain_state[' in post_metric_body
            and 'shear_remove_links_candidate_materiality = direction_material_gate_chain_state[' in post_metric_body
            and 'if direction_material_gate_chain_state["should_continue"]:' in post_metric_body
        ),
        "solver_no_longer_emits_non_material_trace_inline": (
            "_trace_candidate_eval_non_material_solver_coordinator(" not in solve_body
        ),
    }
    status = "PASS"
    if not all(static_checks.values()) or not all(runtime_checks.values()):
        status = "FAIL"
    return {
        "status": status,
        "surface": "_solve_one_click_to_target_non_material_gate_coordinator",
        "helper_segment": {
            "function": "_handle_one_click_solver_candidate_non_material_gate_coordinator",
            "start_line": helper_start,
            "end_line": helper_end,
            "line_count": helper_end - helper_start + 1,
        },
        "chain_segment": {
            "function": "_handle_one_click_solver_candidate_direction_material_gate_chain_coordinator",
            "start_line": chain_start,
            "end_line": chain_end,
            "line_count": chain_end - chain_start + 1,
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
        "next_safe_slice": "extract scored candidate metric preparation coordinator",
    }


def write_artifacts(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now().isoformat(timespec="seconds").replace(":", "-")
    json_path = ARTIFACT_DIR / (
        f"inputs_page_solver_candidate_non_material_gate_coordinator_extraction_{stamp}.json"
    )
    md_path = AUDIT_DIR / (
        f"inputs_page_solver_candidate_non_material_gate_coordinator_extraction_{stamp}.md"
    )
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Solver Candidate Non-Material Gate Coordinator Extraction",
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
