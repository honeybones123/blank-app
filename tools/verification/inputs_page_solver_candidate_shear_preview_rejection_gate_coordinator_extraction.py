"""Verify one-click solver shear preview rejection gate coordinator extraction."""

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
    original_trace = getattr(
        module,
        "_trace_candidate_eval_shear_preview_rejection_solver_coordinator",
        None,
    )
    trace_calls: list[dict[str, Any]] = []

    def _trace(**kwargs: Any) -> None:
        trace_calls.append(
            {
                "reason": kwargs.get("rejection_reason"),
                "new_d": kwargs.get("new_d"),
                "family_hint": kwargs.get("family_hint"),
            }
        )

    common = {
        "peval": {"overview": {}},
        "mode_config": {"mode": "balanced"},
        "step_idx": 3,
        "rc": {"title": "candidate"},
        "norm_u": {"s_lig": 80},
        "new_d": 0.12,
        "governing_domain": "shear",
        "rejected_as_spacing_too_weak": 10,
        "rejected_as_web_crushing_marginal": 20,
        "rejected_as_impractical_shear_layout": 30,
        "trace_callback": lambda _ev, _dat: None,
    }
    try:
        module._trace_candidate_eval_shear_preview_rejection_solver_coordinator = _trace
        spacing = module._handle_one_click_solver_candidate_shear_preview_rejection_gate_coordinator(
            **common,
            family_hint="spacing_reduction",
            shear_util_preview=1.05,
            web_util_preview=1.10,
            s_new=80.0,
            legs_new=6,
            dia_new=16,
            has_geometry_change=False,
        )
        web = module._handle_one_click_solver_candidate_shear_preview_rejection_gate_coordinator(
            **common,
            family_hint="bar_diameter",
            shear_util_preview=1.05,
            web_util_preview=0.99,
            s_new=80.0,
            legs_new=6,
            dia_new=16,
            has_geometry_change=False,
        )
        layout = module._handle_one_click_solver_candidate_shear_preview_rejection_gate_coordinator(
            **common,
            family_hint="spacing_reduction",
            shear_util_preview=1.04,
            web_util_preview=0.98,
            s_new=89.9,
            legs_new=6,
            dia_new=16,
            has_geometry_change=False,
        )
        pass_through = module._handle_one_click_solver_candidate_shear_preview_rejection_gate_coordinator(
            **common,
            family_hint="spacing_reduction",
            shear_util_preview=1.04,
            web_util_preview=0.98,
            s_new=89.9,
            legs_new=6,
            dia_new=16,
            has_geometry_change=True,
        )
    finally:
        if original_trace is not None:
            module._trace_candidate_eval_shear_preview_rejection_solver_coordinator = original_trace

    return {
        "spacing": spacing,
        "web": web,
        "layout": layout,
        "pass_through": pass_through,
        "trace_calls": trace_calls,
    }


def build_payload() -> dict[str, Any]:
    source = _read(AUTO_DESIGN_COMPUTE)
    helper_start, helper_end, helper = _function_segment(
        source,
        "_handle_one_click_solver_candidate_shear_preview_rejection_gate_coordinator",
    )
    aggregate_start, aggregate_end, aggregate_body = _function_segment(
        source,
        "_handle_one_click_solver_candidate_shear_truth_and_preview_gate_coordinator",
    )
    solve_start, solve_end, solve_body = _function_segment(source, "_solve_one_click_to_target")
    scoring_loop_start, scoring_loop_end, scoring_loop_body = _function_segment(
        source, "_run_one_click_solver_candidate_scoring_loop_coordinator"
    )
    _, _, pre_selection_body = _function_segment(
        source,
        "_run_one_click_solver_iteration_pre_selection_candidate_evaluation_coordinator",
    )
    _, _, pre_selection_pipeline_body = _function_segment(
        source,
        "_run_one_click_solver_pre_selection_candidate_pipeline_and_scoring_coordinator",
    )
    _, _, post_metric_body = _function_segment(
        source,
        "_run_one_click_solver_single_candidate_post_metric_scoring_flow_coordinator",
    )
    _, _, post_metric_shear_dispatch_body = _function_segment(
        source,
        "_dispatch_one_click_solver_candidate_shear_truth_preview_gate_from_post_metric_coordinator",
    )
    import inputs_page_modules.auto_design_compute as module  # noqa: E402

    runtime = _run_cases(module)
    base = {
        "rejected_as_spacing_too_weak": 10,
        "rejected_as_web_crushing_marginal": 20,
        "rejected_as_impractical_shear_layout": 30,
    }
    runtime_checks = {
        "spacing_rejection_first_and_counter_preserved": runtime["spacing"] == {
            **base,
            "rejected_as_spacing_too_weak": 11,
            "should_continue": True,
        },
        "web_rejection_counter_preserved": runtime["web"] == {
            **base,
            "rejected_as_web_crushing_marginal": 21,
            "should_continue": True,
        },
        "layout_rejection_counter_preserved": runtime["layout"] == {
            **base,
            "rejected_as_impractical_shear_layout": 31,
            "should_continue": True,
        },
        "pass_through_counters_preserved": runtime["pass_through"] == {
            **base,
            "should_continue": False,
        },
        "trace_reasons_preserved_in_order": [call["reason"] for call in runtime["trace_calls"]]
        == [
            "spacing_too_weak_for_shear_recovery",
            "web_crushing_marginal",
            "impractical_shear_layout",
        ],
    }
    static_checks = {
        "solver_delegates_candidate_scoring_loop": (
            "_run_one_click_solver_pre_selection_candidate_pipeline_and_scoring_coordinator(" in pre_selection_body
            and "_dispatch_one_click_solver_candidate_scoring_loop_from_pre_selection_coordinator("
            in pre_selection_pipeline_body
        ),
        "helper_present": "def _handle_one_click_solver_candidate_shear_preview_rejection_gate_coordinator(" in source,
        "helper_preserves_spacing_condition": (
            "family_hint == \"spacing_reduction\"" in helper
            and "shear_util_preview is not None" in helper
            and "shear_util_preview > 1.04" in helper
        ),
        "helper_preserves_web_condition": "web_util_preview is not None and web_util_preview > 0.98" in helper,
        "helper_preserves_layout_condition": (
            "s_new < 90.0 and legs_new >= 6 and dia_new >= 16 and not has_geometry_change" in helper
        ),
        "helper_preserves_rejection_reasons": (
            '"spacing_too_weak_for_shear_recovery"' in helper
            and '"web_crushing_marginal"' in helper
            and '"impractical_shear_layout"' in helper
        ),
        "helper_returns_continue_state": helper.count('"should_continue": True') == 3
        and '"should_continue": False' in helper,
        "aggregate_delegates_gate": (
            "_handle_one_click_solver_candidate_shear_preview_rejection_gate_coordinator(" in aggregate_body
        ),
        "aggregate_rehydrates_counters_and_continue": (
            'rejected_as_spacing_too_weak = shear_preview_rejection_gate_state[' in aggregate_body
            and 'rejected_as_web_crushing_marginal = shear_preview_rejection_gate_state[' in aggregate_body
            and 'rejected_as_impractical_shear_layout = shear_preview_rejection_gate_state[' in aggregate_body
            and "_build_one_click_solver_candidate_shear_truth_preview_gate_result_state_coordinator("
            in aggregate_body
            and 'should_continue=bool(shear_preview_rejection_gate_state["should_continue"])'
            in aggregate_body
        ),
        "solver_delegates_shear_truth_preview_gate": (
            "_handle_one_click_solver_candidate_shear_truth_and_preview_gate_coordinator("
            in post_metric_shear_dispatch_body
        ),
        "solver_rehydrates_aggregate_counters_and_continue": (
            'rejected_as_spacing_too_weak = shear_truth_preview_gate_state[' in post_metric_body
            and 'rejected_as_web_crushing_marginal = shear_truth_preview_gate_state[' in post_metric_body
            and 'rejected_as_impractical_shear_layout = shear_truth_preview_gate_state[' in post_metric_body
            and 'if shear_truth_preview_gate_state["should_continue"]:' in post_metric_body
        ),
        "solver_no_longer_emits_shear_rejection_trace_inline": (
            "_trace_candidate_eval_shear_preview_rejection_solver_coordinator(" not in solve_body
        ),
    }
    status = "PASS"
    if not all(static_checks.values()) or not all(runtime_checks.values()):
        status = "FAIL"
    return {
        "status": status,
        "surface": "_solve_one_click_to_target_shear_preview_rejection_gate_coordinator",
        "helper_segment": {
            "function": "_handle_one_click_solver_candidate_shear_preview_rejection_gate_coordinator",
            "start_line": helper_start,
            "end_line": helper_end,
            "line_count": helper_end - helper_start + 1,
        },
        "aggregate_segment": {
            "function": "_handle_one_click_solver_candidate_shear_truth_and_preview_gate_coordinator",
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
        "next_safe_slice": "extract wrong-direction candidate gate coordinator",
    }


def write_artifacts(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now().isoformat(timespec="seconds").replace(":", "-")
    json_path = ARTIFACT_DIR / (
        f"inputs_page_solver_candidate_shear_preview_rejection_gate_coordinator_extraction_{stamp}.json"
    )
    md_path = AUDIT_DIR / (
        f"inputs_page_solver_candidate_shear_preview_rejection_gate_coordinator_extraction_{stamp}.md"
    )
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Solver Candidate Shear Preview Rejection Gate Coordinator Extraction",
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
