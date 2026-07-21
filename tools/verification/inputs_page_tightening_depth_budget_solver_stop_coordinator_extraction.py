"""Verify tightening-depth-budget solver stop coordinator extraction."""

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
    originals = {
        "_candidate_target_band_distance": getattr(module, "_candidate_target_band_distance", None),
        "_one_click_diff_accumulated_updates": getattr(module, "_one_click_diff_accumulated_updates", None),
        "_one_click_still_materially_under_target": getattr(module, "_one_click_still_materially_under_target", None),
    }
    calls: list[dict[str, Any]] = []

    def _fake_distance(cur_eval: dict, mode_config: dict) -> float:
        return 0.125

    def _fake_diff(initial_snapshot: dict, working: dict) -> dict[str, Any]:
        return {"delta_D": working.get("D", 0) - initial_snapshot.get("D", 0)}

    def _fake_still_under(cur_eval: dict, mode_config: dict, *, margin: float) -> bool:
        return margin == 0.03 and bool(mode_config.get("under"))

    def _trace(ev: str, dat: dict) -> None:
        calls.append({"ev": ev, "dat": dict(dat)})

    try:
        module._candidate_target_band_distance = _fake_distance
        module._one_click_diff_accumulated_updates = _fake_diff
        module._one_click_still_materially_under_target = _fake_still_under
        returned = module._trace_tightening_depth_budget_solver_stop_coordinator(
            cur_eval={"overview": {"worst_util": 0.72}},
            mode_config={"under": True},
            step_trace=[{"step": 0}, {"step": 1}, {"step": 2}],
            initial_snapshot={"D": 600},
            working={"D": 640},
            cur_ib=False,
            cur_pass=True,
            winning_label="Candidate C",
            winning_action_type="tighten",
            tightening_step_count=5,
            max_tightening_steps=4,
            candidate_family_depth_reached="combined",
            trace_callback=_trace,
        )
    finally:
        for name, original in originals.items():
            if original is not None:
                setattr(module, name, original)

    expected_trace = {
        "ev": "stop",
        "dat": {
            "stop_reason": "tightening_depth_budget_reached",
            "step_count": 3,
            "status": "exhausted",
            "final_preview_util": 0.72,
            "reached_target_band": False,
            "all_key_pass": True,
            "winning_label": "Candidate C",
            "winning_action_type": "tighten",
            "final_updates": {"delta_D": 40},
            "tightening_step_count": 5,
            "tightening_depth_budget": 4,
            "still_materially_under_target": True,
            "no_actionable_after_full_tightening_search": False,
            "candidate_family_depth_reached": "combined",
            "final_distance_to_band": 0.125,
        },
    }
    return {
        "returned": returned,
        "calls": calls,
        "matches": returned == ("tightening_depth_budget_reached", "exhausted", 0.125)
        and calls == [expected_trace],
    }


def build_payload() -> dict[str, Any]:
    source = _read(AUTO_DESIGN_COMPUTE)
    helper_start, helper_end, helper = _function_segment(source, "_trace_tightening_depth_budget_solver_stop_coordinator")
    gate_start, gate_end, gate_helper = _function_segment(
        source,
        "_prepare_one_click_solver_tightening_depth_gate_state_coordinator",
    )
    solve_start, solve_end, solve_body = _function_segment(source, "_solve_one_click_to_target")
    import inputs_page_modules.auto_design_compute as module  # noqa: E402

    runtime = _run_case(module)
    static_checks = {
        "helper_present": "def _trace_tightening_depth_budget_solver_stop_coordinator(" in source,
        "helper_preserves_stop_reason": '"tightening_depth_budget_reached"' in helper,
        "helper_preserves_exhausted_status": '"exhausted"' in helper,
        "helper_computes_distance": "_candidate_target_band_distance(cur_eval, mode_config)" in helper,
        "helper_uses_existing_diff_builder": "_one_click_diff_accumulated_updates(initial_snapshot, working)" in helper,
        "helper_uses_still_under_target": "_one_click_still_materially_under_target(cur_eval, mode_config, margin=0.03)" in helper,
        "gate_delegates_tightening_depth_stop": "_trace_tightening_depth_budget_solver_stop_coordinator("
        in gate_helper,
        "gate_preserves_budget_extension_probe": "_one_click_budget_stop_has_better_next_hop(cur_eval, mode_config)"
        in gate_helper,
        "solver_delegates_tightening_depth_gate": "_prepare_one_click_solver_tightening_depth_gate_state_coordinator("
        in solve_body,
        "solver_preserves_budget_extension_continue": 'if tightening_depth_gate_state["should_continue"]:' in solve_body
        and "continue" in solve_body,
        "solver_no_longer_inlines_tightening_depth_trace": (
            'stop_reason = "tightening_depth_budget_reached"\n'
            '            status = "exhausted"\n'
            '            final_distance_to_band = _candidate_target_band_distance(cur_eval, mode_config)\n'
            '            _t('
        )
        not in solve_body,
    }
    status = "PASS"
    if not all(static_checks.values()) or not runtime["matches"]:
        status = "FAIL"
    return {
        "status": status,
        "surface": "_solve_one_click_to_target_tightening_depth_budget_stop_coordinator",
        "helper_segment": {
            "function": "_trace_tightening_depth_budget_solver_stop_coordinator",
            "start_line": helper_start,
            "end_line": helper_end,
            "line_count": helper_end - helper_start + 1,
        },
        "tightening_depth_gate_segment": {
            "function": "_prepare_one_click_solver_tightening_depth_gate_state_coordinator",
            "start_line": gate_start,
            "end_line": gate_end,
            "line_count": gate_end - gate_start + 1,
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
        "next_safe_slice": "extract no-actionable-candidates stop coordinator",
    }


def write_artifacts(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now().isoformat(timespec="seconds").replace(":", "-")
    json_path = ARTIFACT_DIR / f"inputs_page_tightening_depth_budget_solver_stop_coordinator_extraction_{stamp}.json"
    md_path = AUDIT_DIR / f"inputs_page_tightening_depth_budget_solver_stop_coordinator_extraction_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Tightening-Depth-Budget Solver Stop Coordinator Extraction",
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
            f"- Stop tuple and trace match: `{payload['runtime']['matches']}`",
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
