"""Verify no-actionable-candidates solver stop coordinator extraction."""

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


def _run_case(
    module: Any,
    *,
    name: str,
    governing_domain: str,
    still_under: bool,
    spacing_fail: bool,
    tightening_mode_active: bool,
    rejected_non_material: int,
    expected_reason: str,
    expected_full_search: bool,
) -> dict[str, Any]:
    originals = {
        "_one_click_still_materially_under_target": getattr(module, "_one_click_still_materially_under_target", None),
        "_one_click_has_unresolved_spacing_envelope_fail": getattr(module, "_one_click_has_unresolved_spacing_envelope_fail", None),
        "_candidate_target_band_distance": getattr(module, "_candidate_target_band_distance", None),
        "_one_click_diff_accumulated_updates": getattr(module, "_one_click_diff_accumulated_updates", None),
    }
    calls: list[dict[str, Any]] = []

    def _fake_still_under(cur_eval: dict, mode_config: dict, *, margin: float) -> bool:
        return still_under

    def _fake_spacing_fail(cur_eval: dict) -> bool:
        return spacing_fail

    def _fake_distance(cur_eval: dict, mode_config: dict) -> float:
        return 0.275

    def _fake_diff(initial_snapshot: dict, working: dict) -> dict[str, Any]:
        return {"delta_D": working.get("D", 0) - initial_snapshot.get("D", 0)}

    def _trace(ev: str, dat: dict) -> None:
        calls.append({"ev": ev, "dat": dict(dat)})

    try:
        module._one_click_still_materially_under_target = _fake_still_under
        module._one_click_has_unresolved_spacing_envelope_fail = _fake_spacing_fail
        module._candidate_target_band_distance = _fake_distance
        module._one_click_diff_accumulated_updates = _fake_diff
        returned = module._trace_no_actionable_candidates_solver_stop_coordinator(
            cur_eval={"overview": {"worst_util": 0.81}},
            mode_config={},
            step_trace=[{"step": 0}],
            initial_snapshot={"D": 600},
            working={"D": 630},
            governing_domain=governing_domain,
            tightening_mode_active=tightening_mode_active,
            rejected_as_non_material_improvement=rejected_non_material,
            no_actionable_after_full_tightening_search=False,
            cur_ib=False,
            cur_pass=False,
            winning_label=None,
            winning_action_type=None,
            tightening_step_count=3,
            max_tightening_steps=4,
            candidate_family_depth_reached="spacing",
            trace_callback=_trace,
        )
    finally:
        for attr, original in originals.items():
            if original is not None:
                setattr(module, attr, original)

    expected_trace = {
        "ev": "stop",
        "dat": {
            "stop_reason": expected_reason,
            "step_count": 1,
            "status": "exhausted",
            "final_preview_util": 0.81,
            "reached_target_band": False,
            "all_key_pass": False,
            "winning_label": None,
            "winning_action_type": None,
            "final_updates": {"delta_D": 30},
            "tightening_step_count": 3,
            "tightening_depth_budget": 4,
            "still_materially_under_target": still_under,
            "no_actionable_after_full_tightening_search": expected_full_search,
            "candidate_family_depth_reached": "spacing",
            "final_distance_to_band": 0.275,
            "unresolved_spacing_envelope_fail": bool(governing_domain == "shear" and spacing_fail),
        },
    }
    return {
        "case": name,
        "returned": returned,
        "calls": calls,
        "matches": returned == (expected_reason, "exhausted", 0.275, expected_full_search)
        and calls == [expected_trace],
    }


def build_payload() -> dict[str, Any]:
    source = _read(AUTO_DESIGN_COMPUTE)
    helper_start, helper_end, helper = _function_segment(source, "_trace_no_actionable_candidates_solver_stop_coordinator")
    branch_start, branch_end, branch_helper = _function_segment(
        source,
        "_handle_one_click_solver_no_scored_stop_branch_coordinator",
    )
    solve_start, solve_end, solve_body = _function_segment(source, "_solve_one_click_to_target")
    import inputs_page_modules.auto_design_compute as module  # noqa: E402

    rows = [
        _run_case(
            module,
            name="spacing_limit",
            governing_domain="shear",
            still_under=True,
            spacing_fail=True,
            tightening_mode_active=True,
            rejected_non_material=0,
            expected_reason="minimum_shear_detailing_limit",
            expected_full_search=False,
        ),
        _run_case(
            module,
            name="non_material_remaining",
            governing_domain="bending",
            still_under=True,
            spacing_fail=False,
            tightening_mode_active=True,
            rejected_non_material=2,
            expected_reason="non_material_remaining_candidates",
            expected_full_search=True,
        ),
        _run_case(
            module,
            name="plain_no_actionable",
            governing_domain="bending",
            still_under=False,
            spacing_fail=False,
            tightening_mode_active=False,
            rejected_non_material=0,
            expected_reason="no_actionable_candidates",
            expected_full_search=False,
        ),
    ]
    static_checks = {
        "helper_present": "def _trace_no_actionable_candidates_solver_stop_coordinator(" in source,
        "helper_preserves_reason_paths": all(
            token in helper
            for token in (
                '"minimum_shear_detailing_limit"',
                '"non_material_remaining_candidates"',
                '"no_actionable_candidates_after_full_tightening_search"',
                '"no_actionable_candidates"',
            )
        ),
        "helper_sets_full_tightening_flag": "no_actionable_after_full_tightening_search = True" in helper,
        "helper_uses_spacing_fail_helper": "_one_click_has_unresolved_spacing_envelope_fail(cur_eval)" in helper,
        "helper_uses_distance_helper": "_candidate_target_band_distance(cur_eval, mode_config)" in helper,
        "helper_uses_diff_builder": "_one_click_diff_accumulated_updates(initial_snapshot, working)" in helper,
        "branch_delegates_no_actionable_stop": "_trace_no_actionable_candidates_solver_stop_coordinator(" in branch_helper,
        "branch_preserves_scored_gate": "if scored:" in branch_helper,
        "solver_delegates_no_scored_stop_branch": (
            "_handle_one_click_solver_no_scored_stop_branch_coordinator(" in solve_body
        ),
        "solver_no_longer_inlines_no_actionable_trace": (
            'if unresolved_spacing_fail:\n'
            '                stop_reason = "minimum_shear_detailing_limit"'
        )
        not in solve_body,
    }
    status = "PASS"
    if not all(static_checks.values()) or any(not row["matches"] for row in rows):
        status = "FAIL"
    return {
        "status": status,
        "surface": "_solve_one_click_to_target_no_actionable_candidates_stop_coordinator",
        "helper_segment": {
            "function": "_trace_no_actionable_candidates_solver_stop_coordinator",
            "start_line": helper_start,
            "end_line": helper_end,
            "line_count": helper_end - helper_start + 1,
        },
        "branch_segment": {
            "function": "_handle_one_click_solver_no_scored_stop_branch_coordinator",
            "start_line": branch_start,
            "end_line": branch_end,
            "line_count": branch_end - branch_start + 1,
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
        "next_safe_slice": "extract best-available/out-of-band stop coordinator",
    }


def write_artifacts(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now().isoformat(timespec="seconds").replace(":", "-")
    json_path = ARTIFACT_DIR / f"inputs_page_no_actionable_candidates_solver_stop_coordinator_extraction_{stamp}.json"
    md_path = AUDIT_DIR / f"inputs_page_no_actionable_candidates_solver_stop_coordinator_extraction_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# No-Actionable-Candidates Solver Stop Coordinator Extraction",
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
