"""Verify candidate-eval scored trace coordinator extraction."""

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
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            start = int(node.lineno)
            end = int(getattr(node, "end_lineno", node.lineno))
            lines = source.splitlines()
            return start, end, "\n".join(lines[start - 1 : end])
    raise AssertionError(f"Function not found: {name}")


def _run_case(module: Any) -> dict[str, Any]:
    original_trace = getattr(module, "_one_click_trace_eval_domain_payload", None)
    calls: list[dict[str, Any]] = []

    def _fake_trace(peval: dict, mode_config: dict) -> dict[str, Any]:
        return {"domain_payload": [peval.get("domain"), mode_config.get("mode")]}

    def _trace_cb(ev: str, dat: dict) -> None:
        calls.append({"ev": ev, "dat": dict(dat)})

    try:
        module._one_click_trace_eval_domain_payload = _fake_trace
        module._trace_candidate_eval_scored_solver_coordinator(
            peval={
                "domain": "bending",
                "overview": {"worst_util": 0.88, "statuses": {"bending": "PASS"}},
            },
            mode_config={"mode": "tight"},
            step_idx=10,
            rc={"title": "Scored", "action_type": "tighten"},
            norm_u={"D": 650, "b": 300},
            nib=True,
            new_d=0.02,
            sort_key=(0, 0.02, 2),
            tier=0,
            domain_progress={"required_fail_count": 1, "required_unsatisfied_count": 2},
            has_target_domains=True,
            dk=0.12,
            mixed_direction_mode="mixed",
            mixed_rank={
                "primary_domain": "bending",
                "secondary_domain": "shear",
                "primary_material_improvement": True,
                "primary_distance": 0.03,
                "secondary_distance": 0.04,
            },
            tightening_mode_active=True,
            direction={"is_reduction_candidate": True, "is_growth_only": False},
            governing_domain="bending",
            family_hint="depth",
            material_improvement_threshold=0.05,
            trace_callback=_trace_cb,
        )
    finally:
        if original_trace is not None:
            module._one_click_trace_eval_domain_payload = original_trace

    expected = [
        {
            "ev": "candidate_eval",
            "dat": {
                "domain_payload": ["bending", "tight"],
                "step": 10,
                "label": "Scored",
                "action_type": "tighten",
                "updates": {"D": 650, "b": 300},
                "preview_util": 0.88,
                "preview_statuses": {"bending": "PASS"},
                "reaches_target_band": True,
                "distance_to_band": 0.02,
                "duplicate_signature_rejected": False,
                "no_real_change_rejected": False,
                "evaluation_failed": False,
                "ranking_tuple": [0, 0.02, 2],
                "ranking_components": {
                    "tier_pass_in_band": 0,
                    "required_fail_count": 1,
                    "required_unsatisfied_count": 2,
                    "distance_to_band": 0.02,
                    "directional_tie_key": 0.12,
                    "mixed_direction_mode": "mixed",
                    "mixed_primary_domain": "bending",
                    "mixed_secondary_domain": "shear",
                    "mixed_primary_material_improvement": True,
                    "mixed_primary_distance": 0.03,
                    "mixed_secondary_distance": 0.04,
                    "tightening_mode_active": True,
                    "reduction_candidate": True,
                    "governing_domain": "bending",
                    "candidate_family": "depth",
                    "material_improvement_threshold": 0.05,
                    "update_key_count": 2,
                },
                "tightening_mode_active": True,
                "reduction_candidate": True,
                "growth_candidate": False,
                "governing_domain": "bending",
                "candidate_family": "depth",
                "rejection_reason": None,
            },
        }
    ]
    return {"calls": calls, "matches": calls == expected}


def build_payload() -> dict[str, Any]:
    source = _read(AUTO_DESIGN_COMPUTE)
    helper_start, helper_end, helper = _function_segment(
        source,
        "_trace_candidate_eval_scored_solver_coordinator",
    )
    append_start, append_end, append_body = _function_segment(
        source,
        "_handle_one_click_solver_candidate_scored_append_trace_coordinator",
    )
    scoring_start, scoring_end, scoring_body = _function_segment(
        source,
        "_prepare_one_click_solver_candidate_scoring_state_coordinator",
    )
    _, _, sorting_body = _function_segment(
        source,
        "_prepare_one_click_solver_candidate_sorting_state_coordinator",
    )
    assembly_start, assembly_end, assembly_body = _function_segment(
        source,
        "_handle_one_click_solver_candidate_scored_assembly_chain_coordinator",
    )
    solve_start, solve_end, solve_body = _function_segment(source, "_solve_one_click_to_target")
    scoring_loop_start, scoring_loop_end, scoring_loop_body = _function_segment(
        source, "_run_one_click_solver_candidate_scoring_loop_coordinator"
    )
    _, _, pre_selection_body = _function_segment(
        source, "_run_one_click_solver_iteration_pre_selection_candidate_evaluation_coordinator"
    )
    _, _, post_metric_body = _function_segment(
        source, "_run_one_click_solver_single_candidate_post_metric_scoring_flow_coordinator"
    )
    _, _, scored_assembly_dispatch_body = _function_segment(
        source,
        "_dispatch_one_click_solver_candidate_scored_assembly_chain_from_post_metric_coordinator",
    )
    import inputs_page_modules.auto_design_compute as module  # noqa: E402

    runtime = _run_case(module)
    static_checks = {
        "solver_delegates_iteration_loop": (
            "_dispatch_one_click_solver_iteration_loop_from_solver_runtime_setup_coordinator(" in solve_body
        ),
        "pre_selection_delegates_candidate_scoring_loop": (
            "_dispatch_one_click_solver_candidate_scoring_loop_from_pre_selection_coordinator(" in pre_selection_body
            or "_run_one_click_solver_pre_selection_candidate_pipeline_and_scoring_coordinator(" in pre_selection_body
        ),
        "helper_present": "def _trace_candidate_eval_scored_solver_coordinator(" in source,
        "helper_emits_candidate_eval_trace": 'trace_callback(\n        "candidate_eval",' in helper,
        "helper_preserves_domain_payload": "_one_click_trace_eval_domain_payload(peval, mode_config)" in helper,
        "helper_preserves_ranking_tuple": '"ranking_tuple": list(sort_key)' in helper,
        "helper_preserves_ranking_components": '"ranking_components": {' in helper,
        "helper_preserves_no_rejection": '"rejection_reason": None' in helper,
        "append_coordinator_delegates_scored_trace": "_trace_candidate_eval_scored_solver_coordinator(" in append_body,
        "append_coordinator_keeps_scored_append": "scored.append(" in append_body,
        "post_metric_flow_delegates_scored_assembly_chain": (
            "_dispatch_one_click_solver_candidate_scored_assembly_chain_from_post_metric_coordinator("
            in post_metric_body
        ),
        "post_metric_scored_assembly_dispatch_delegates_chain": (
            "_handle_one_click_solver_candidate_scored_assembly_chain_coordinator("
            in scored_assembly_dispatch_body
            and "post_metric_scope[" in scored_assembly_dispatch_body
        ),
        "scored_assembly_delegates_scored_append_trace": (
            "_handle_one_click_solver_candidate_scored_append_trace_coordinator(" in assembly_body
        ),
        "scoring_state_keeps_sort_key_resolution": (
            "_prepare_one_click_solver_candidate_sorting_state_coordinator(" in scoring_body
            and "_resolve_target_band_candidate_sort_key(" in sorting_body
        ),
        "scored_assembly_delegates_scoring_state": (
            "_prepare_one_click_solver_candidate_scoring_state_coordinator(" in assembly_body
        ),
    }
    status = "PASS"
    if not all(static_checks.values()) or not runtime["matches"]:
        status = "FAIL"
    return {
        "status": status,
        "surface": "_solve_one_click_to_target_candidate_eval_scored_trace_coordinator",
        "helper_segment": {
            "function": "_trace_candidate_eval_scored_solver_coordinator",
            "start_line": helper_start,
            "end_line": helper_end,
            "line_count": helper_end - helper_start + 1,
        },
        "append_segment": {
            "function": "_handle_one_click_solver_candidate_scored_append_trace_coordinator",
            "start_line": append_start,
            "end_line": append_end,
            "line_count": append_end - append_start + 1,
        },
        "scoring_segment": {
            "function": "_prepare_one_click_solver_candidate_scoring_state_coordinator",
            "start_line": scoring_start,
            "end_line": scoring_end,
            "line_count": scoring_end - scoring_start + 1,
        },
        "assembly_segment": {
            "function": "_handle_one_click_solver_candidate_scored_assembly_chain_coordinator",
            "start_line": assembly_start,
            "end_line": assembly_end,
            "line_count": assembly_end - assembly_start + 1,
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
        "next_safe_slice": "extract no-real-change candidate trace coordinator",
    }


def write_artifacts(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now().isoformat(timespec="seconds").replace(":", "-")
    json_path = ARTIFACT_DIR / f"inputs_page_candidate_eval_scored_trace_coordinator_extraction_{stamp}.json"
    md_path = AUDIT_DIR / f"inputs_page_candidate_eval_scored_trace_coordinator_extraction_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Candidate Eval Scored Trace Coordinator Extraction",
        "",
        f"Status: `{payload['status']}`",
        "",
        "## Static Checks",
    ]
    for key, value in payload["static_checks"].items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(
        [
            "",
            "## Runtime",
            f"- Scored trace matches: `{payload['runtime']['matches']}`",
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
    print(json.dumps({"status": payload["status"], "json": str(json_path), "report": str(md_path)}, indent=2))
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
