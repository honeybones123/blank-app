"""Verify candidate fallback plus pool-trace solver coordinator extraction."""

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
    originals = {
        "_handle_one_click_solver_no_scored_fallback_next_hop_injection_coordinator": getattr(
            module,
            "_handle_one_click_solver_no_scored_fallback_next_hop_injection_coordinator",
            None,
        ),
        "_trace_candidate_pool_solver_coordinator": getattr(
            module,
            "_trace_candidate_pool_solver_coordinator",
            None,
        ),
    }
    calls: list[dict[str, Any]] = []

    def _fallback(**kwargs: Any) -> dict[str, Any]:
        calls.append({"fn": "fallback", "kwargs": dict(kwargs)})
        return {
            "scored": [{"row": "fallback"}],
            "fallback_next_hop_injected": True,
            "fallback_next_hop_reason": "guidance_exhausted_but_refinement_next_hop_exists",
        }

    def _trace(**kwargs: Any) -> None:
        calls.append({"fn": "trace", "kwargs": dict(kwargs)})

    try:
        module._handle_one_click_solver_no_scored_fallback_next_hop_injection_coordinator = _fallback
        module._trace_candidate_pool_solver_coordinator = _trace
        result = module._handle_one_click_solver_candidate_fallback_pool_trace_coordinator(
            scored=[],
            cur_eval={"overview": {"worst": 1.1}},
            working={"D": 600},
            mode_config={"mode": "balanced"},
            tightening_mode_active=True,
            step_idx=3,
            raw_n=4,
            pool_labels=[("spacing", "tighten")],
            governing_domain="shear",
            tightening_meta={"candidate_families_considered": ["spacing"]},
            material_improvement_threshold=0.03,
            reduction_candidates_considered=5,
            growth_candidates_rejected_in_tightening=6,
            rejected_as_non_governing_cleanup=7,
            rejected_as_non_governing_shear_strengthening=8,
            rejected_as_non_material_improvement=9,
            tightening_step_count=10,
            max_tightening_steps=11,
            no_actionable_after_full_tightening_search=False,
            candidate_family_depth_reached="spacing",
            shear_governing_mode_active=True,
            shear_severity_band="high",
            shear_candidate_family_order=["spacing", "legs"],
            spacing_candidates_considered=12,
            leg_candidates_considered=13,
            dia_candidates_considered=14,
            geometry_candidates_considered_for_shear=15,
            combined_candidates_considered_for_shear=16,
            web_crushing_penalty_applied=17,
            rejected_as_spacing_too_weak=18,
            rejected_as_web_crushing_marginal=19,
            rejected_as_impractical_shear_layout=20,
            shear_governing_family_detected=True,
            governing_family_exists_after_domain_fix=False,
            pruned_non_shear_family_count=21,
            domain_match_prune_used=True,
            shear_prune_rule_source="domain_match",
            trace_callback=lambda *_args, **_kwargs: None,
        )
    finally:
        for name, original in originals.items():
            if original is not None:
                setattr(module, name, original)
            elif hasattr(module, name):
                delattr(module, name)

    return {"result": result, "calls": calls}


def build_payload() -> dict[str, Any]:
    source = _read(AUTO_DESIGN_COMPUTE)
    aggregate_start, aggregate_end, aggregate = _function_segment(
        source,
        "_handle_one_click_solver_candidate_fallback_pool_trace_coordinator",
    )
    solve_start, solve_end, solve_body = _function_segment(source, "_solve_one_click_to_target")
    selection_state_start, selection_state_end, selection_state_body = _function_segment(
        source, "_resolve_one_click_solver_scored_candidate_selection_state_coordinator"
    )
    _, _, post_selection_dispatch_body = _function_segment(
        source, "_dispatch_one_click_solver_post_selection_candidate_selection_state_coordinator"
    )
    _, _, fallback_dispatch_body = _function_segment(
        source,
        "_dispatch_one_click_solver_candidate_fallback_pool_trace_from_selection_coordinator",
    )
    import inputs_page_modules.auto_design_compute as module  # noqa: E402

    runtime = _run_case(module)
    fallback_call = runtime["calls"][0] if len(runtime["calls"]) > 0 else {}
    trace_call = runtime["calls"][1] if len(runtime["calls"]) > 1 else {}
    trace_kwargs = dict(trace_call.get("kwargs") or {})
    runtime_checks = {
        "calls_fallback_then_trace": [c.get("fn") for c in runtime["calls"]] == ["fallback", "trace"],
        "fallback_receives_solver_state": (
            fallback_call.get("kwargs", {}).get("working") == {"D": 600}
            and fallback_call.get("kwargs", {}).get("tightening_mode_active") is True
        ),
        "trace_receives_fallback_scored": trace_kwargs.get("scored") == [{"row": "fallback"}],
        "trace_receives_fallback_flags": (
            trace_kwargs.get("fallback_next_hop_injected") is True
            and trace_kwargs.get("fallback_next_hop_reason")
            == "guidance_exhausted_but_refinement_next_hop_exists"
        ),
        "trace_receives_candidate_pool_counters": (
            trace_kwargs.get("raw_n") == 4
            and trace_kwargs.get("rejected_as_impractical_shear_layout") == 20
            and trace_kwargs.get("domain_match_prune_used") is True
        ),
        "returns_solver_state": runtime["result"] == {
            "scored": [{"row": "fallback"}],
            "fallback_next_hop_injected": True,
            "fallback_next_hop_reason": "guidance_exhausted_but_refinement_next_hop_exists",
        },
    }
    static_checks = {
        "solver_delegates_scored_candidate_selection_state": (
            "_resolve_one_click_solver_scored_candidate_selection_state_coordinator("
            in post_selection_dispatch_body
        ),
        "aggregate_present": "def _handle_one_click_solver_candidate_fallback_pool_trace_coordinator(" in source,
        "aggregate_delegates_fallback": (
            "_handle_one_click_solver_no_scored_fallback_next_hop_injection_coordinator(" in aggregate
        ),
        "aggregate_delegates_candidate_pool_trace": "_trace_candidate_pool_solver_coordinator(" in aggregate,
        "aggregate_returns_rehydrated_state": (
            '"scored": scored' in aggregate
            and '"fallback_next_hop_injected": fallback_next_hop_injected' in aggregate
            and '"fallback_next_hop_reason": fallback_next_hop_reason' in aggregate
        ),
        "solver_delegates_aggregate": (
            "_dispatch_one_click_solver_candidate_fallback_pool_trace_from_selection_coordinator("
            in selection_state_body
            and "_handle_one_click_solver_candidate_fallback_pool_trace_coordinator("
            in fallback_dispatch_body
        ),
        "solver_no_longer_delegates_fallback_directly": (
            "_handle_one_click_solver_no_scored_fallback_next_hop_injection_coordinator(" not in solve_body
        ),
        "solver_no_longer_delegates_candidate_pool_directly": (
            "_trace_candidate_pool_solver_coordinator(" not in solve_body
        ),
    }
    status = "PASS"
    if not all(static_checks.values()) or not all(runtime_checks.values()):
        status = "FAIL"
    return {
        "status": status,
        "surface": "_solve_one_click_to_target_candidate_fallback_pool_trace_coordinator",
        "aggregate_segment": {
            "function": "_handle_one_click_solver_candidate_fallback_pool_trace_coordinator",
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
        "next_safe_slice": "extract no-scored stop branch state handoff",
    }


def write_artifacts(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now().isoformat(timespec="seconds").replace(":", "-")
    json_path = ARTIFACT_DIR / (
        f"inputs_page_solver_candidate_fallback_pool_trace_coordinator_extraction_{stamp}.json"
    )
    md_path = AUDIT_DIR / (
        f"inputs_page_solver_candidate_fallback_pool_trace_coordinator_extraction_{stamp}.md"
    )
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Solver Candidate Fallback Pool Trace Coordinator Extraction",
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
