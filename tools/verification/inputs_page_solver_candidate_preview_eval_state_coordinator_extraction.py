"""Verify one-click solver candidate preview eval state coordinator extraction."""

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
        "_guidance_state_snapshot": getattr(module, "_guidance_state_snapshot", None),
        "_build_canonical_design_state_pack": getattr(module, "_build_canonical_design_state_pack", None),
        "evaluate_candidate_full": getattr(module, "evaluate_candidate_full", None),
        "_trace_candidate_eval_evaluation_failed_solver_coordinator": getattr(
            module,
            "_trace_candidate_eval_evaluation_failed_solver_coordinator",
            None,
        ),
    }
    trace_calls: list[dict[str, Any]] = []
    eval_calls: list[dict[str, Any]] = []

    def _snapshot(state: dict[str, Any]) -> dict[str, Any]:
        return {"snap": dict(state)}

    def _canonical(snapshot: dict[str, Any]) -> dict[str, Any]:
        packed = dict(snapshot["snap"])
        packed["canonical"] = True
        return packed

    def _trace(**kwargs: Any) -> None:
        trace_calls.append(
            {
                "step_idx": kwargs.get("step_idx"),
                "family_hint": kwargs.get("family_hint"),
                "governing_domain": kwargs.get("governing_domain"),
                "norm_u": dict(kwargs.get("norm_u") or {}),
            }
        )

    def _eval_success(preview: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
        eval_calls.append({"preview": dict(preview), "kwargs": dict(kwargs)})
        return {"overview": {"worst_util": 0.9}, "preview": dict(preview)}

    def _eval_fail(preview: dict[str, Any], **kwargs: Any) -> None:
        eval_calls.append({"preview": dict(preview), "kwargs": dict(kwargs)})
        return None

    try:
        module._guidance_state_snapshot = _snapshot
        module._build_canonical_design_state_pack = _canonical
        module._trace_candidate_eval_evaluation_failed_solver_coordinator = _trace

        module.evaluate_candidate_full = _eval_success
        success = module._prepare_one_click_solver_candidate_preview_eval_state_coordinator(
            step_idx=2,
            rc={"title": "Preview success", "action_type": "tighten"},
            norm_u={"D": 650},
            direction={"is_growth_only": False},
            working={"D": 600, "b": 300},
            tightening_mode_active=True,
            governing_domain="bending",
            family_hint="geometry",
            rejected_as_evaluation_failed=4,
            trace_callback=lambda *_args, **_kwargs: None,
        )

        module.evaluate_candidate_full = _eval_fail
        failed = module._prepare_one_click_solver_candidate_preview_eval_state_coordinator(
            step_idx=3,
            rc={"title": "Preview fail", "action_type": "tighten"},
            norm_u={"b": 250},
            direction={"is_growth_only": False},
            working={"D": 600, "b": 300},
            tightening_mode_active=False,
            governing_domain="shear",
            family_hint="shear",
            rejected_as_evaluation_failed=4,
            trace_callback=lambda *_args, **_kwargs: None,
        )
    finally:
        for name, original in originals.items():
            if original is not None:
                setattr(module, name, original)
            elif hasattr(module, name):
                delattr(module, name)

    return {
        "success": success,
        "failed": failed,
        "eval_calls": eval_calls,
        "trace_calls": trace_calls,
    }


def build_payload() -> dict[str, Any]:
    source = _read(AUTO_DESIGN_COMPUTE)
    helper_start, helper_end, helper = _function_segment(
        source,
        "_prepare_one_click_solver_candidate_preview_eval_state_coordinator",
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
    import inputs_page_modules.auto_design_compute as module  # noqa: E402

    runtime = _run_cases(module)
    runtime_checks = {
        "success_state_preserved": runtime["success"] == {
            "peval": {
                "overview": {"worst_util": 0.9},
                "preview": {"D": 650, "b": 300, "canonical": True},
            },
            "preview": {"D": 650, "b": 300, "canonical": True},
            "rejected_as_evaluation_failed": 4,
            "should_continue": False,
        },
        "failed_state_preserved": runtime["failed"] == {
            "peval": None,
            "preview": {"D": 600, "b": 250, "canonical": True},
            "rejected_as_evaluation_failed": 5,
            "should_continue": True,
        },
        "preview_eval_inputs_preserved": runtime["eval_calls"] == [
            {
                "preview": {"D": 650, "b": 300, "canonical": True},
                "kwargs": {
                    "source": "one_click_preview_2",
                    "label": "Preview success",
                    "action_type": "tighten",
                    "updates": {"D": 650},
                },
            },
            {
                "preview": {"D": 600, "b": 250, "canonical": True},
                "kwargs": {
                    "source": "one_click_preview_3",
                    "label": "Preview fail",
                    "action_type": "tighten",
                    "updates": {"b": 250},
                },
            },
        ],
        "failed_trace_preserved": runtime["trace_calls"] == [
            {
                "step_idx": 3,
                "family_hint": "shear",
                "governing_domain": "shear",
                "norm_u": {"b": 250},
            }
        ],
    }
    static_checks = {
        "solver_delegates_iteration_loop": "_dispatch_one_click_solver_iteration_loop_from_solver_runtime_setup_coordinator(" in solve_body,
        "pre_selection_delegates_candidate_scoring_loop": (
            "_dispatch_one_click_solver_candidate_scoring_loop_from_pre_selection_coordinator(" in pre_selection_body
        ),
        "scoring_loop_delegates_single_candidate_flow": (
            "_run_one_click_solver_single_candidate_scoring_flow_coordinator(" in scoring_loop_body
        ),
        "single_candidate_flow_delegates_pre_metric_gate_flow": (
            "_run_one_click_solver_single_candidate_pre_metric_gate_flow_coordinator(" in single_candidate_body
        ),
        "helper_present": "def _prepare_one_click_solver_candidate_preview_eval_state_coordinator(" in source,
        "helper_preserves_preview_construction": "preview = copy.deepcopy(working)" in helper
        and "preview.update(norm_u)" in helper
        and "_build_canonical_design_state_pack(_guidance_state_snapshot(preview))" in helper,
        "helper_preserves_evaluate_candidate_full_inputs": "evaluate_candidate_full(" in helper
        and 'source=f"one_click_preview_{step_idx}"' in helper
        and 'label=rc["title"]' in helper
        and 'action_type=rc["action_type"]' in helper
        and "updates=dict(norm_u)" in helper,
        "helper_preserves_failed_branch": "if peval is None:" in helper
        and "rejected_as_evaluation_failed += 1" in helper
        and "_trace_candidate_eval_evaluation_failed_solver_coordinator(" in helper,
        "pre_metric_flow_delegates_preview_eval_state": (
            "_prepare_one_click_solver_candidate_preview_eval_state_coordinator(" in pre_metric_body
        ),
        "pre_metric_flow_rehydrates_preview_eval_fields": (
            'peval = preview_eval_state["peval"]' in pre_metric_body
            and 'preview = preview_eval_state["preview"]' in pre_metric_body
            and 'rejected_as_evaluation_failed = preview_eval_state["rejected_as_evaluation_failed"]' in pre_metric_body
        ),
        "pre_metric_flow_preserves_continue_gate": (
            'if preview_eval_state["should_continue"]:' in pre_metric_body
        ),
        "scoring_loop_no_longer_delegates_preview_eval_directly": (
            "_prepare_one_click_solver_candidate_preview_eval_state_coordinator(" not in scoring_loop_body
        ),
        "solver_no_longer_inlines_failed_trace": (
            "_trace_candidate_eval_evaluation_failed_solver_coordinator(" not in solve_body
        ),
    }
    status = "PASS"
    if not all(static_checks.values()) or not all(runtime_checks.values()):
        status = "FAIL"
    return {
        "status": status,
        "surface": "_solve_one_click_to_target_candidate_preview_eval_state_coordinator",
        "helper_segment": {
            "function": "_prepare_one_click_solver_candidate_preview_eval_state_coordinator",
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
        "next_safe_slice": "extract candidate target-domain attachment branch",
    }


def write_artifacts(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now().isoformat(timespec="seconds").replace(":", "-")
    json_path = ARTIFACT_DIR / (
        f"inputs_page_solver_candidate_preview_eval_state_coordinator_extraction_{stamp}.json"
    )
    md_path = AUDIT_DIR / (
        f"inputs_page_solver_candidate_preview_eval_state_coordinator_extraction_{stamp}.md"
    )
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Solver Candidate Preview Eval State Coordinator Extraction",
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
