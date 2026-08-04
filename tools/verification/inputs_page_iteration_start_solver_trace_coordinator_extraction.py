"""Verify iteration-start solver trace coordinator extraction."""

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


def _direct_trace_events(function_source: str) -> list[str]:
    tree = ast.parse(function_source)
    events: list[str] = []
    for call in ast.walk(tree):
        if not isinstance(call, ast.Call):
            continue
        if not isinstance(call.func, ast.Name) or call.func.id != "_t":
            continue
        if call.args and isinstance(call.args[0], ast.Constant):
            events.append(str(call.args[0].value))
        else:
            events.append("?")
    return events


def _run_case(module: Any) -> dict[str, Any]:
    original_summary = getattr(module, "_trace_compact_shared_geom_reo", None)
    original_overview = getattr(module, "_trace_compact_overview_dict", None)
    original_under_target = getattr(module, "_one_click_still_materially_under_target", None)
    calls: list[dict[str, Any]] = []

    def _summary(state: dict[str, Any]) -> dict[str, Any]:
        return {"D": state.get("D"), "b": state.get("b")}

    def _overview(overview: dict[str, Any] | None) -> dict[str, Any]:
        return {"statuses": dict((overview or {}).get("statuses") or {})}

    def _under_target(cur_eval: dict[str, Any], mode_config: dict[str, Any], *, margin: float) -> bool:
        return cur_eval.get("under") == mode_config.get("mode") and margin == 0.03

    def _trace_cb(ev: str, dat: dict[str, Any]) -> None:
        calls.append({"ev": ev, "dat": dict(dat)})

    try:
        module._trace_compact_shared_geom_reo = _summary
        module._trace_compact_overview_dict = _overview
        module._one_click_still_materially_under_target = _under_target
        module._trace_iteration_start_solver_coordinator(
            step_idx=4,
            cur_sig=("sig-a", "sig-b"),
            working={"D": 600, "b": 300, "cover": 30},
            cur_eval={"under": "tight", "overview": {"worst_util": 0.91, "statuses": {"bending": "PASS"}}},
            t_lo=0.85,
            t_hi=0.95,
            tightening_mode_active=True,
            governing_domain="bending",
            material_improvement_threshold=0.01,
            tightening_step_count=2,
            max_tightening_steps=8,
            mode_config={"mode": "tight"},
            no_actionable_after_full_tightening_search=False,
            shear_governing_mode_active=True,
            shear_severity_band="high",
            shear_candidate_family_order=["legs", "spacing"],
            shear_governing_family_detected=True,
            governing_family_exists_after_domain_fix=False,
            mixed_direction_mode="prefer_reduction",
            pruned_non_shear_family_count=3,
            domain_match_prune_used=True,
            shear_prune_rule_source="domain_matcher",
            trace_callback=_trace_cb,
        )
    finally:
        if original_summary is not None:
            module._trace_compact_shared_geom_reo = original_summary
        if original_overview is not None:
            module._trace_compact_overview_dict = original_overview
        if original_under_target is not None:
            module._one_click_still_materially_under_target = original_under_target

    expected = [
        {
            "ev": "iteration_start",
            "dat": {
                "step": 4,
                "working_signature": ["sig-a", "sig-b"],
                "working_summary": {"D": 600, "b": 300},
                "current_worst_util": 0.91,
                "target_band": {"min": 0.85, "max": 0.95},
                "current_overview": {"statuses": {"bending": "PASS"}},
                "tightening_mode_active": True,
                "governing_domain": "bending",
                "material_improvement_threshold": 0.01,
                "tightening_step_count": 2,
                "tightening_depth_budget": 8,
                "still_materially_under_target": True,
                "no_actionable_after_full_tightening_search": False,
                "shear_governing_mode_active": True,
                "shear_severity_band": "high",
                "shear_candidate_family_order": ["legs", "spacing"],
                "shear_governing_family_detected": True,
                "governing_family_exists_after_domain_fix": False,
                "mixed_direction_mode": "prefer_reduction",
                "pruned_non_shear_family_count": 3,
                "domain_match_prune_used": True,
                "shear_prune_rule_source": "domain_matcher",
            },
        },
    ]
    return {"calls": calls, "matches": calls == expected}


def build_payload() -> dict[str, Any]:
    source = _read(AUTO_DESIGN_COMPUTE)
    helper_start, helper_end, helper = _function_segment(
        source,
        "_trace_iteration_start_solver_coordinator",
    )
    handoff_start, handoff_end, handoff_helper = _function_segment(
        source,
        "_prepare_one_click_solver_iteration_scoring_start_state_coordinator",
    )
    solve_start, solve_end, solve_body = _function_segment(source, "_solve_one_click_to_target")
    candidate_pipeline_start, candidate_pipeline_end, candidate_pipeline_body = _function_segment(
        source, "_prepare_one_click_solver_candidate_pipeline_state_coordinator"
    )
    import inputs_page_modules.auto_design_compute as module  # noqa: E402

    runtime = _run_case(module)
    direct_trace_events = _direct_trace_events(solve_body)
    static_checks = {
        "solver_delegates_candidate_pipeline_state": (
            "_prepare_one_click_solver_candidate_pipeline_state_coordinator(" in solve_body
        ),
        "helper_present": "def _trace_iteration_start_solver_coordinator(" in source,
        "helper_emits_iteration_start_trace": 'trace_callback(\n        "iteration_start",' in helper,
        "helper_preserves_working_summary": "_trace_compact_shared_geom_reo(working)" in helper,
        "helper_preserves_current_overview": "_trace_compact_overview_dict(cur_eval.get(\"overview\"))" in helper,
        "helper_preserves_under_target_probe": "_one_click_still_materially_under_target(cur_eval, mode_config, margin=0.03)" in helper,
        "handoff_delegates_iteration_start_trace": "_trace_iteration_start_solver_coordinator(" in handoff_helper,
        "handoff_sets_shear_prune_rule_source_before_trace": (
            'shear_prune_rule_source = "domain_matcher" if domain_match_prune_used else shear_prune_rule_source'
            in handoff_helper
        ),
        "solver_delegates_iteration_scoring_start_state": (
            "_prepare_one_click_solver_iteration_scoring_start_state_coordinator(" in candidate_pipeline_body
        ),
        "solver_no_longer_delegates_iteration_start_trace_directly": (
            "_trace_iteration_start_solver_coordinator(" not in solve_body
        ),
        "solver_has_no_direct_trace_calls": direct_trace_events == [],
    }
    status = "PASS"
    if not all(static_checks.values()) or not runtime["matches"]:
        status = "FAIL"
    return {
        "status": status,
        "surface": "_solve_one_click_to_target_iteration_start_trace_coordinator",
        "helper_segment": {
            "function": "_trace_iteration_start_solver_coordinator",
            "start_line": helper_start,
            "end_line": helper_end,
            "line_count": helper_end - helper_start + 1,
        },
        "handoff_helper_segment": {
            "function": "_prepare_one_click_solver_iteration_scoring_start_state_coordinator",
            "start_line": handoff_start,
            "end_line": handoff_end,
            "line_count": handoff_end - handoff_start + 1,
        },
        "solver_segment": {
            "function": "_solve_one_click_to_target",
            "start_line": solve_start,
            "end_line": solve_end,
            "line_count": solve_end - solve_start + 1,
        },
        "static_checks": static_checks,
        "runtime": runtime,
        "direct_trace_events": direct_trace_events,
        "product_behavior_changed": False,
        "next_safe_slice": "continue reducing solver orchestration with candidate preparation or scoring helpers",
    }


def write_artifacts(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now().isoformat(timespec="seconds").replace(":", "-")
    json_path = ARTIFACT_DIR / f"inputs_page_iteration_start_solver_trace_coordinator_extraction_{stamp}.json"
    md_path = AUDIT_DIR / f"inputs_page_iteration_start_solver_trace_coordinator_extraction_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Iteration Start Solver Trace Coordinator Extraction",
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
            f"- Iteration-start trace matches: `{payload['runtime']['matches']}`",
            f"- Direct solver trace events: `{payload['direct_trace_events']}`",
            "",
            "## Next Safe Slice",
            "",
            str(payload["next_safe_slice"]),
        ],
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
