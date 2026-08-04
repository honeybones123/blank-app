"""Verify rejected-best-candidate solver stop coordinator extraction."""

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


def _run_case(module: Any, *, explicit_reason: bool) -> dict[str, Any]:
    originals = {
        "_one_click_trace_eval_domain_payload": getattr(module, "_one_click_trace_eval_domain_payload", None),
        "_candidate_in_target_band": getattr(module, "_candidate_in_target_band", None),
        "_one_click_diff_accumulated_updates": getattr(module, "_one_click_diff_accumulated_updates", None),
        "_one_click_still_materially_under_target": getattr(module, "_one_click_still_materially_under_target", None),
    }
    calls: list[dict[str, Any]] = []

    def _fake_domain_payload(eval_payload: dict, mode_config: dict) -> dict[str, Any]:
        return {"domain_payload": eval_payload.get("domain")}

    def _fake_in_band(eval_payload: dict, mode_config: dict) -> bool:
        return bool(eval_payload.get("in_band"))

    def _fake_diff(initial_snapshot: dict, working: dict) -> dict[str, Any]:
        return {"delta_D": working.get("D", 0) - initial_snapshot.get("D", 0)}

    def _fake_still_under(cur_eval: dict, mode_config: dict, *, margin: float) -> bool:
        return True

    def _trace(ev: str, dat: dict) -> None:
        calls.append({"ev": ev, "dat": dict(dat)})

    selected = {"accepted": False}
    if explicit_reason:
        selected["stop_reason"] = "best_available_out_of_band_candidate"
    best = {
        "eval": {"domain": "shear", "in_band": False, "overview": {"statuses": {"shear": "FAIL"}}},
        "label": "Best candidate",
        "action_type": "tighten",
        "updates": {"D": 650},
        "worst_util": 0.99,
    }
    try:
        module._one_click_trace_eval_domain_payload = _fake_domain_payload
        module._candidate_in_target_band = _fake_in_band
        module._one_click_diff_accumulated_updates = _fake_diff
        module._one_click_still_materially_under_target = _fake_still_under
        returned = module._trace_rejected_best_candidate_solver_stop_coordinator(
            selected_candidate_acceptance=selected,
            best=best,
            mode_config={},
            step_idx=4,
            cur_eval={"overview": {"worst_util": 1.12}},
            cur_pass=False,
            step_trace=[{"step": 0}, {"step": 1}],
            initial_snapshot={"D": 600},
            working={"D": 630},
            winning_label="Previous",
            winning_action_type="previous_action",
            tightening_step_count=3,
            max_tightening_steps=4,
            no_actionable_after_full_tightening_search=False,
            candidate_family_depth_reached="combined",
            best_distance_to_band_this_iteration=0.42,
            in_band_shear_cleanup_deferral={"active": True},
            trace_callback=_trace,
        )
    finally:
        for attr, original in originals.items():
            if original is not None:
                setattr(module, attr, original)

    expected_reason = "best_available_out_of_band_candidate" if explicit_reason else "no_improving_candidate"
    expected_calls = [
        {
            "ev": "iteration_winner",
            "dat": {
                "domain_payload": "shear",
                "step": 4,
                "chosen_label": "Best candidate",
                "chosen_action_type": "tighten",
                "chosen_updates": {"D": 650},
                "chosen_preview_util": 0.99,
                "chosen_statuses": {"shear": "FAIL"},
                "reaches_target_band": False,
                "reason_selected": "rank_lexicographic_then_no_improvement_exit",
                "accepted": False,
                "in_band_shear_cleanup_deferred": True,
            },
        },
        {
            "ev": "stop",
            "dat": {
                "stop_reason": expected_reason,
                "step_count": 2,
                "status": "exhausted",
                "final_preview_util": 1.12,
                "reached_target_band": False,
                "all_key_pass": False,
                "winning_label": "Previous",
                "winning_action_type": "previous_action",
                "final_updates": {"delta_D": 30},
                "tightening_step_count": 3,
                "tightening_depth_budget": 4,
                "still_materially_under_target": True,
                "no_actionable_after_full_tightening_search": False,
                "candidate_family_depth_reached": "combined",
                "best_distance_to_band_this_iteration": 0.42,
            },
        },
    ]
    return {
        "case": "explicit_reason" if explicit_reason else "fallback_reason",
        "returned": returned,
        "calls": calls,
        "matches": returned == (expected_reason, "exhausted") and calls == expected_calls,
    }


def build_payload() -> dict[str, Any]:
    source = _read(AUTO_DESIGN_COMPUTE)
    helper_start, helper_end, helper = _function_segment(source, "_trace_rejected_best_candidate_solver_stop_coordinator")
    gate_start, gate_end, gate_body = _function_segment(
        source,
        "_handle_one_click_solver_selected_candidate_acceptance_gate_coordinator",
    )
    aggregate_start, aggregate_end, aggregate_body = _function_segment(
        source,
        "_handle_one_click_solver_candidate_selection_or_stop_coordinator",
    )
    solve_start, solve_end, solve_body = _function_segment(source, "_solve_one_click_to_target")
    import inputs_page_modules.auto_design_compute as module  # noqa: E402

    rows = [
        _run_case(module, explicit_reason=True),
        _run_case(module, explicit_reason=False),
    ]
    static_checks = {
        "helper_present": "def _trace_rejected_best_candidate_solver_stop_coordinator(" in source,
        "helper_preserves_fallback_reason": '"no_improving_candidate"' in helper,
        "helper_emits_iteration_winner_before_stop": helper.find('"iteration_winner"') < helper.find('"stop"'),
        "helper_preserves_rejected_reason_label": '"rank_lexicographic_then_no_improvement_exit"' in helper,
        "helper_uses_domain_payload": "_one_click_trace_eval_domain_payload(best[\"eval\"], mode_config)" in helper,
        "helper_uses_diff_builder": "_one_click_diff_accumulated_updates(initial_snapshot, working)" in helper,
        "helper_uses_still_under_target": "_one_click_still_materially_under_target(cur_eval, mode_config, margin=0.03)" in helper,
        "gate_delegates_rejected_best_stop": "_trace_rejected_best_candidate_solver_stop_coordinator(" in gate_body,
        "gate_preserves_rejected_acceptance_gate": "if not bool(selected_candidate_acceptance.get(\"accepted\")):" in gate_body,
        "aggregate_delegates_selected_candidate_acceptance_gate": (
            "_handle_one_click_solver_selected_candidate_acceptance_gate_coordinator(" in aggregate_body
        ),
        "solver_delegates_candidate_selection_or_stop": (
            "_handle_one_click_solver_candidate_selection_or_stop_coordinator(" in solve_body
        ),
        "solver_no_longer_inlines_rejected_best_trace": (
            'stop_reason = str(selected_candidate_acceptance.get("stop_reason") or "no_improving_candidate")\n'
            '            status = "exhausted"\n'
            '            _t('
        )
        not in solve_body,
    }
    status = "PASS"
    if not all(static_checks.values()) or any(not row["matches"] for row in rows):
        status = "FAIL"
    return {
        "status": status,
        "surface": "_solve_one_click_to_target_rejected_best_candidate_stop_coordinator",
        "helper_segment": {
            "function": "_trace_rejected_best_candidate_solver_stop_coordinator",
            "start_line": helper_start,
            "end_line": helper_end,
            "line_count": helper_end - helper_start + 1,
        },
        "gate_segment": {
            "function": "_handle_one_click_solver_selected_candidate_acceptance_gate_coordinator",
            "start_line": gate_start,
            "end_line": gate_end,
            "line_count": gate_end - gate_start + 1,
        },
        "aggregate_segment": {
            "function": "_handle_one_click_solver_candidate_selection_or_stop_coordinator",
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
        "runtime_rows": rows,
        "product_behavior_changed": False,
        "next_safe_slice": "extract accepted iteration-winner trace coordinator",
    }


def write_artifacts(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now().isoformat(timespec="seconds").replace(":", "-")
    json_path = ARTIFACT_DIR / f"inputs_page_rejected_best_candidate_solver_stop_coordinator_extraction_{stamp}.json"
    md_path = AUDIT_DIR / f"inputs_page_rejected_best_candidate_solver_stop_coordinator_extraction_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Rejected Best-Candidate Solver Stop Coordinator Extraction",
        "",
        f"Status: `{payload['status']}`",
        "",
        "## Static Checks",
    ]
    for key, value in payload["static_checks"].items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(["", "## Runtime Rows"])
    for row in payload["runtime_rows"]:
        lines.append(f"- `{row['case']}`: `{row['matches']}`")
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
