"""Verify one-click solver scored candidate append/trace coordinator extraction."""

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


def _run_case(module: Any) -> dict[str, Any]:
    original_trace = getattr(module, "_trace_candidate_eval_scored_solver_coordinator", None)
    trace_calls: list[dict[str, Any]] = []

    def _trace(**kwargs: Any) -> None:
        trace_calls.append(
            {
                "scored_len_at_trace": len(scored),
                "nib": kwargs.get("nib"),
                "sort_key": kwargs.get("sort_key"),
                "tier": kwargs.get("tier"),
                "domain_progress": kwargs.get("domain_progress"),
                "has_target_domains": kwargs.get("has_target_domains"),
                "dk": kwargs.get("dk"),
                "material_improvement_threshold": kwargs.get("material_improvement_threshold"),
            }
        )

    scored: list[dict[str, Any]] = [{"existing": True}]
    try:
        module._trace_candidate_eval_scored_solver_coordinator = _trace
        result = module._handle_one_click_solver_candidate_scored_append_trace_coordinator(
            scored=scored,
            peval={"overview": {"worst_util": "0.87"}},
            mode_config={"mode": "balanced"},
            step_idx=11,
            rc={
                "item": {"action_payload": {"guidance_change_summary_compact": "  compact summary  "}},
                "title": "Candidate",
                "action_type": "tighten",
            },
            norm_u={"D": 640},
            psig=("sig", 1),
            new_d=0.03,
            sort_key=(0, 0.03, 1),
            nib=True,
            tier=0,
            domain_progress={"required_fail_count": 0},
            has_target_domains=True,
            dk=0.12,
            mixed_direction_mode=False,
            mixed_rank={"active": False},
            tightening_mode_active=True,
            direction={"is_reduction_candidate": True},
            governing_domain="bending",
            family_hint="depth",
            material_improvement_threshold=0.01,
            trace_callback=lambda _ev, _dat: None,
        )
    finally:
        if original_trace is not None:
            module._trace_candidate_eval_scored_solver_coordinator = original_trace

    return {
        "result_is_same_list": result["scored"] is scored,
        "scored": scored,
        "trace_calls": trace_calls,
    }


def build_payload() -> dict[str, Any]:
    source = _read(AUTO_DESIGN_COMPUTE)
    helper_start, helper_end, helper = _function_segment(
        source,
        "_handle_one_click_solver_candidate_scored_append_trace_coordinator",
    )
    chain_start, chain_end, chain_body = _function_segment(
        source,
        "_handle_one_click_solver_candidate_scored_assembly_chain_coordinator",
    )
    solve_start, solve_end, solve_body = _function_segment(source, "_solve_one_click_to_target")
    scoring_loop_start, scoring_loop_end, scoring_loop_body = _function_segment(
        source, "_run_one_click_solver_candidate_scoring_loop_coordinator"
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
    expected_row = {
        "sort_key": (0, 0.03, 1),
        "eval": {"overview": {"worst_util": "0.87"}},
        "updates": {"D": 640},
        "label": "Candidate",
        "action_type": "tighten",
        "signature": ("sig", 1),
        "change_summary": "compact summary",
        "worst_util": 0.87,
    }
    runtime_checks = {
        "returns_same_scored_list": runtime["result_is_same_list"] is True,
        "append_preserves_existing_rows_and_shape": runtime["scored"] == [
            {"existing": True},
            expected_row,
        ],
        "trace_runs_after_append_with_inputs": runtime["trace_calls"] == [
            {
                "scored_len_at_trace": 2,
                "nib": True,
                "sort_key": (0, 0.03, 1),
                "tier": 0,
                "domain_progress": {"required_fail_count": 0},
                "has_target_domains": True,
                "dk": 0.12,
                "material_improvement_threshold": 0.01,
            }
        ],
    }
    static_checks = {
        "solver_delegates_iteration_loop": (
            "_dispatch_one_click_solver_iteration_loop_from_solver_runtime_setup_coordinator("
            in solve_body
        ),
        "helper_present": "def _handle_one_click_solver_candidate_scored_append_trace_coordinator(" in source,
        "helper_preserves_summary_lookup": (
            'rc["item"].get("action_payload")' in helper
            and '"guidance_change_summary_compact"' in helper
            and ".strip() or None" in helper
        ),
        "helper_preserves_scored_entry_shape": (
            '"sort_key": sort_key' in helper
            and '"updates": dict(norm_u)' in helper
            and '"signature": psig' in helper
            and '"worst_util": float((peval.get("overview") or {}).get("worst_util", 0.0) or 0.0)' in helper
        ),
        "helper_preserves_append_before_trace": (
            helper.index("scored.append(") < helper.index("_trace_candidate_eval_scored_solver_coordinator(")
        ),
        "helper_returns_scored": 'return {"scored": scored}' in helper,
        "chain_delegates_append_trace": (
            "_handle_one_click_solver_candidate_scored_append_trace_coordinator(" in chain_body
        ),
        "chain_rehydrates_scored": 'scored_append_trace_state["scored"]' in chain_body,
        "solver_delegates_scored_assembly_chain": (
            "_dispatch_one_click_solver_candidate_scored_assembly_chain_from_post_metric_coordinator("
            in post_metric_body
            and "_handle_one_click_solver_candidate_scored_assembly_chain_coordinator("
            in scored_assembly_dispatch_body
        ),
        "solver_rehydrates_scored": 'scored = scored_assembly_chain_state["scored"]' in post_metric_body,
        "solver_no_longer_owns_candidate_summary_lookup": '"guidance_change_summary_compact"' not in solve_body,
        "solver_no_longer_emits_scored_trace_inline": (
            "_trace_candidate_eval_scored_solver_coordinator(" not in solve_body
        ),
    }
    status = "PASS"
    if not all(static_checks.values()) or not all(runtime_checks.values()):
        status = "FAIL"
    return {
        "status": status,
        "surface": "_solve_one_click_to_target_scored_append_trace_coordinator",
        "helper_segment": {
            "function": "_handle_one_click_solver_candidate_scored_append_trace_coordinator",
            "start_line": helper_start,
            "end_line": helper_end,
            "line_count": helper_end - helper_start + 1,
        },
        "chain_segment": {
            "function": "_handle_one_click_solver_candidate_scored_assembly_chain_coordinator",
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
        "next_safe_slice": "extract no-scored-candidates fallback next-hop coordinator",
    }


def write_artifacts(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now().isoformat(timespec="seconds").replace(":", "-")
    json_path = ARTIFACT_DIR / (
        f"inputs_page_solver_candidate_scored_append_trace_coordinator_extraction_{stamp}.json"
    )
    md_path = AUDIT_DIR / (
        f"inputs_page_solver_candidate_scored_append_trace_coordinator_extraction_{stamp}.md"
    )
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Solver Candidate Scored Append Trace Coordinator Extraction",
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
