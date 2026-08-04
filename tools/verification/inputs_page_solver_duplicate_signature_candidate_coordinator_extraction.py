"""Verify one-click solver duplicate-signature candidate coordinator extraction."""

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
        "_candidate_state_signature": getattr(module, "_candidate_state_signature", None),
        "_candidate_objective_util": getattr(module, "_candidate_objective_util", None),
        "_candidate_target_band_distance": getattr(module, "_candidate_target_band_distance", None),
        "_trace_candidate_eval_duplicate_signature_solver_coordinator": getattr(
            module,
            "_trace_candidate_eval_duplicate_signature_solver_coordinator",
            None,
        ),
    }
    objective_calls: list[dict[str, Any]] = []
    trace_calls: list[dict[str, Any]] = []

    def _signature(peval: dict[str, Any]) -> tuple[str, ...] | None:
        value = peval.get("sig")
        if value is None:
            return None
        return tuple(value)

    def _objective(peval: dict[str, Any]) -> float:
        objective_calls.append(dict(peval))
        return float(peval.get("u", 0.0) or 0.0)

    def _distance(peval: dict[str, Any], mode_config: Any) -> float:
        return float(peval.get("distance", 0.0) or 0.0)

    def _trace(**kwargs: Any) -> None:
        trace_calls.append(
            {
                "new_d": kwargs.get("new_d"),
                "family_hint": kwargs.get("family_hint"),
                "governing_domain": kwargs.get("governing_domain"),
                "norm_u": dict(kwargs.get("norm_u") or {}),
            }
        )

    try:
        module._candidate_state_signature = _signature
        module._candidate_objective_util = _objective
        module._candidate_target_band_distance = _distance
        module._trace_candidate_eval_duplicate_signature_solver_coordinator = _trace

        duplicate = module._handle_one_click_solver_duplicate_signature_candidate_coordinator(
            peval={"sig": ["a", "b"], "distance": 0.04, "u": 0.91},
            mode_config={"mode": "balanced"},
            seen_sigs={("a", "b")},
            step_idx=2,
            rc={"title": "Duplicate", "action_type": "tighten"},
            norm_u={"D": 650},
            direction={"is_growth_only": False},
            tightening_mode_active=True,
            governing_domain="bending",
            family_hint="geometry",
            rejected_as_duplicate_signature=3,
            trace_callback=lambda *_args, **_kwargs: None,
        )
        fresh = module._handle_one_click_solver_duplicate_signature_candidate_coordinator(
            peval={"sig": ["c"], "distance": 0.02, "u": 0.88},
            mode_config={"mode": "balanced"},
            seen_sigs={("a", "b")},
            step_idx=3,
            rc={"title": "Fresh", "action_type": "tighten"},
            norm_u={"b": 300},
            direction={"is_growth_only": False},
            tightening_mode_active=False,
            governing_domain="shear",
            family_hint="shear",
            rejected_as_duplicate_signature=3,
            trace_callback=lambda *_args, **_kwargs: None,
        )
        no_sig = module._handle_one_click_solver_duplicate_signature_candidate_coordinator(
            peval={"sig": None, "distance": 0.02, "u": 0.88},
            mode_config={"mode": "balanced"},
            seen_sigs={("a", "b")},
            step_idx=4,
            rc={"title": "No sig", "action_type": "tighten"},
            norm_u={},
            direction={},
            tightening_mode_active=False,
            governing_domain=None,
            family_hint="",
            rejected_as_duplicate_signature=3,
            trace_callback=lambda *_args, **_kwargs: None,
        )
    finally:
        for name, original in originals.items():
            if original is not None:
                setattr(module, name, original)
            elif hasattr(module, name):
                delattr(module, name)

    return {
        "duplicate": duplicate,
        "fresh": fresh,
        "no_sig": no_sig,
        "objective_calls": objective_calls,
        "trace_calls": trace_calls,
    }


def build_payload() -> dict[str, Any]:
    source = _read(AUTO_DESIGN_COMPUTE)
    helper_start, helper_end, helper = _function_segment(
        source,
        "_handle_one_click_solver_duplicate_signature_candidate_coordinator",
    )
    solve_start, solve_end, solve_body = _function_segment(source, "_solve_one_click_to_target")
    scoring_loop_start, scoring_loop_end, scoring_loop_body = _function_segment(
        source, "_run_one_click_solver_candidate_scoring_loop_coordinator"
    )
    _, _, single_candidate_body = _function_segment(
        source, "_run_one_click_solver_single_candidate_scoring_flow_coordinator"
    )
    _, _, pre_metric_body = _function_segment(
        source, "_run_one_click_solver_single_candidate_pre_metric_gate_flow_coordinator"
    )
    _, _, pre_selection_body = _function_segment(
        source, "_run_one_click_solver_iteration_pre_selection_candidate_evaluation_coordinator"
    )
    _, _, pre_selection_pipeline_body = _function_segment(
        source,
        "_run_one_click_solver_pre_selection_candidate_pipeline_and_scoring_coordinator",
    )
    import inputs_page_modules.auto_design_compute as module  # noqa: E402

    runtime = _run_cases(module)
    runtime_checks = {
        "duplicate_rejection_preserved": runtime["duplicate"] == {
            "psig": ("a", "b"),
            "rejected_as_duplicate_signature": 4,
            "should_continue": True,
        },
        "fresh_pass_through_preserved": runtime["fresh"] == {
            "psig": ("c",),
            "rejected_as_duplicate_signature": 3,
            "should_continue": False,
        },
        "no_signature_pass_through_preserved": runtime["no_sig"] == {
            "psig": None,
            "rejected_as_duplicate_signature": 3,
            "should_continue": False,
        },
        "objective_call_preserved_for_duplicate": runtime["objective_calls"] == [
            {"sig": ["a", "b"], "distance": 0.04, "u": 0.91}
        ],
        "duplicate_trace_preserved": runtime["trace_calls"] == [
            {
                "new_d": 0.04,
                "family_hint": "geometry",
                "governing_domain": "bending",
                "norm_u": {"D": 650},
            }
        ],
    }
    static_checks = {
        "solver_delegates_iteration_loop": "_dispatch_one_click_solver_iteration_loop_from_solver_runtime_setup_coordinator(" in solve_body,
        "pre_selection_delegates_candidate_scoring_loop": (
            "_run_one_click_solver_pre_selection_candidate_pipeline_and_scoring_coordinator(" in pre_selection_body
            and "_dispatch_one_click_solver_candidate_scoring_loop_from_pre_selection_coordinator("
            in pre_selection_pipeline_body
        ),
        "scoring_loop_delegates_single_candidate_flow": (
            "_run_one_click_solver_single_candidate_scoring_flow_coordinator(" in scoring_loop_body
        ),
        "single_candidate_flow_delegates_pre_metric_gate_flow": (
            "_run_one_click_solver_single_candidate_pre_metric_gate_flow_coordinator(" in single_candidate_body
        ),
        "helper_present": "def _handle_one_click_solver_duplicate_signature_candidate_coordinator(" in source,
        "helper_preserves_signature_gate": "psig = _candidate_state_signature(peval)" in helper
        and "if psig and psig in seen_sigs:" in helper,
        "helper_preserves_counter": "rejected_as_duplicate_signature += 1" in helper,
        "helper_preserves_objective_probe": "_new_u = _candidate_objective_util(peval)" in helper,
        "helper_preserves_distance_and_trace": "_candidate_target_band_distance(peval, mode_config)" in helper
        and "_trace_candidate_eval_duplicate_signature_solver_coordinator(" in helper,
        "pre_metric_flow_delegates_duplicate_signature_branch": (
            "_handle_one_click_solver_duplicate_signature_candidate_coordinator(" in pre_metric_body
        ),
        "pre_metric_flow_rehydrates_duplicate_fields": (
            'psig = duplicate_signature_state["psig"]' in pre_metric_body
            and 'rejected_as_duplicate_signature = duplicate_signature_state[' in pre_metric_body
        ),
        "pre_metric_flow_preserves_continue_gate": (
            'if duplicate_signature_state["should_continue"]:' in pre_metric_body
        ),
        "scoring_loop_no_longer_delegates_duplicate_signature_directly": (
            "_handle_one_click_solver_duplicate_signature_candidate_coordinator(" not in scoring_loop_body
        ),
        "solver_no_longer_inlines_duplicate_trace": (
            "_trace_candidate_eval_duplicate_signature_solver_coordinator(" not in solve_body
        ),
    }
    status = "PASS"
    if not all(static_checks.values()) or not all(runtime_checks.values()):
        status = "FAIL"
    return {
        "status": status,
        "surface": "_solve_one_click_to_target_duplicate_signature_candidate_coordinator",
        "helper_segment": {
            "function": "_handle_one_click_solver_duplicate_signature_candidate_coordinator",
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
        "next_safe_slice": "extract post-preview scalar metric setup for candidate scoring",
    }


def write_artifacts(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now().isoformat(timespec="seconds").replace(":", "-")
    json_path = ARTIFACT_DIR / (
        f"inputs_page_solver_duplicate_signature_candidate_coordinator_extraction_{stamp}.json"
    )
    md_path = AUDIT_DIR / (
        f"inputs_page_solver_duplicate_signature_candidate_coordinator_extraction_{stamp}.md"
    )
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Solver Duplicate-Signature Candidate Coordinator Extraction",
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
