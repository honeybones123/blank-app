"""Verify candidate-pool solver trace coordinator extraction."""

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
    original_under = getattr(module, "_one_click_still_materially_under_target", None)
    calls: list[dict[str, Any]] = []

    def _fake_under(cur_eval: dict, mode_config: dict, *, margin: float) -> bool:
        return cur_eval.get("under") is True and mode_config.get("mode") == "tight" and margin == 0.03

    def _trace(ev: str, dat: dict) -> None:
        calls.append({"ev": ev, "dat": dict(dat)})

    try:
        module._one_click_still_materially_under_target = _fake_under
        module._trace_candidate_pool_solver_coordinator(
            step_idx=2,
            raw_n=5,
            scored=[{"a": 1}, {"b": 2}],
            pool_labels=[("A", "tighten")],
            tightening_mode_active=True,
            governing_domain="shear",
            tightening_meta={"candidate_families_considered": ("spacing",), "candidate_families_pruned": ("depth",)},
            material_improvement_threshold=0.04,
            reduction_candidates_considered=3,
            growth_candidates_rejected_in_tightening=4,
            rejected_as_non_governing_cleanup=5,
            rejected_as_non_governing_shear_strengthening=6,
            rejected_as_non_material_improvement=7,
            tightening_step_count=8,
            max_tightening_steps=9,
            cur_eval={"under": True},
            mode_config={"mode": "tight"},
            no_actionable_after_full_tightening_search=False,
            candidate_family_depth_reached="spacing",
            shear_governing_mode_active=True,
            shear_severity_band="high",
            shear_candidate_family_order=("spacing", "legs"),
            spacing_candidates_considered=10,
            leg_candidates_considered=11,
            dia_candidates_considered=12,
            geometry_candidates_considered_for_shear=13,
            combined_candidates_considered_for_shear=14,
            web_crushing_penalty_applied=15,
            rejected_as_spacing_too_weak=16,
            rejected_as_web_crushing_marginal=17,
            rejected_as_impractical_shear_layout=18,
            shear_governing_family_detected=True,
            governing_family_exists_after_domain_fix=False,
            pruned_non_shear_family_count=19,
            domain_match_prune_used=True,
            shear_prune_rule_source="rule",
            fallback_next_hop_injected=True,
            fallback_next_hop_reason="next_hop",
            trace_callback=_trace,
        )
    finally:
        if original_under is not None:
            module._one_click_still_materially_under_target = original_under

    expected = {
        "step": 2,
        "raw_candidate_count": 5,
        "actionable_candidate_count": 2,
        "labels_action_types": [("A", "tighten")],
        "no_actionable_candidates": False,
        "still_materially_under_target": True,
        "candidate_families_considered": ["spacing"],
        "candidate_families_pruned": ["depth"],
        "shear_candidate_family_order": ["spacing", "legs"],
        "fallback_next_hop_injected": True,
        "fallback_next_hop_reason": "next_hop",
    }
    actual = calls[0]["dat"] if calls else {}
    checks = {
        "event_name": bool(calls and calls[0]["ev"] == "candidate_pool"),
        "selected_payload_fields": all(actual.get(k) == v for k, v in expected.items()),
        "shear_counters_preserved": actual.get("rejected_as_impractical_shear_layout") == 18,
        "domain_prune_preserved": actual.get("domain_match_prune_used") is True,
    }
    return {"checks": checks, "matches": all(checks.values())}


def build_payload() -> dict[str, Any]:
    source = _read(AUTO_DESIGN_COMPUTE)
    helper_start, helper_end, helper = _function_segment(source, "_trace_candidate_pool_solver_coordinator")
    aggregate_start, aggregate_end, aggregate = _function_segment(
        source,
        "_handle_one_click_solver_candidate_fallback_pool_trace_coordinator",
    )
    solve_start, solve_end, solve_body = _function_segment(source, "_solve_one_click_to_target")
    import inputs_page_modules.auto_design_compute as module  # noqa: E402

    runtime = _run_case(module)
    static_checks = {
        "helper_present": "def _trace_candidate_pool_solver_coordinator(" in source,
        "helper_emits_candidate_pool_trace": 'trace_callback(\n        "candidate_pool",' in helper,
        "helper_preserves_under_target_probe": "_one_click_still_materially_under_target(" in helper,
        "helper_preserves_fallback_fields": '"fallback_next_hop_injected"' in helper,
        "aggregate_delegates_candidate_pool_trace": "_trace_candidate_pool_solver_coordinator(" in aggregate,
        "solver_delegates_candidate_fallback_pool_trace": (
            "_handle_one_click_solver_candidate_fallback_pool_trace_coordinator(" in solve_body
        ),
        "solver_no_longer_inlines_candidate_pool_trace": '_t(\n            "candidate_pool",' not in solve_body,
    }
    status = "PASS"
    if not all(static_checks.values()) or not runtime["matches"]:
        status = "FAIL"
    return {
        "status": status,
        "surface": "_solve_one_click_to_target_candidate_pool_trace_coordinator",
        "helper_segment": {
            "function": "_trace_candidate_pool_solver_coordinator",
            "start_line": helper_start,
            "end_line": helper_end,
            "line_count": helper_end - helper_start + 1,
        },
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
        "runtime": runtime,
        "product_behavior_changed": False,
        "next_safe_slice": "extract no-scored stop branch state handoff",
    }


def write_artifacts(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now().isoformat(timespec="seconds").replace(":", "-")
    json_path = ARTIFACT_DIR / f"inputs_page_candidate_pool_solver_trace_coordinator_extraction_{stamp}.json"
    md_path = AUDIT_DIR / f"inputs_page_candidate_pool_solver_trace_coordinator_extraction_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Candidate-Pool Solver Trace Coordinator Extraction",
        "",
        f"Status: `{payload['status']}`",
        "",
        "## Static Checks",
    ]
    for key, value in payload["static_checks"].items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(["", "## Runtime"])
    for key, value in payload["runtime"]["checks"].items():
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
