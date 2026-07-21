"""Verify partial-failing final-updates guard solver coordinator extraction."""

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
_MISSING = object()


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
    final_updates: dict[str, Any],
    final_ok: bool,
    init_fail_count: int,
    final_fail_count: int,
    improves: bool,
    final_spacing_fail: bool,
    final_target_domains: list[str],
) -> dict[str, Any]:
    originals = {
        "_one_click_required_domain_progress": getattr(module, "_one_click_required_domain_progress", _MISSING),
        "_one_click_step_improves": getattr(module, "_one_click_step_improves", _MISSING),
    }
    try:
        module._one_click_required_domain_progress = (
            lambda final_eval, mode_config: {"required_fail_count": final_fail_count}
        )
        module._one_click_step_improves = lambda final_eval, init_eval, mode_config: improves
        result = module._handle_one_click_solver_partial_failing_final_updates_guard_coordinator(
            final_updates=dict(final_updates),
            final_ok=final_ok,
            final_eval={"overview": {"worst_util": 0.91}},
            mode_config={"target": "band"},
            init_pass=init_fail_count == 0,
            final_pass=True,
            init_progress={"required_fail_count": init_fail_count},
            init_eval={"overview": {"worst_util": 1.1}},
            final_spacing_fail=final_spacing_fail,
            final_target_domains=list(final_target_domains),
            stop_reason="previous_stop",
            winning_label="Winner",
            winning_action_type="tighten",
        )
    finally:
        for attr, original in originals.items():
            if original is _MISSING:
                delattr(module, attr)
            else:
                setattr(module, attr, original)
    return result


def build_payload() -> dict[str, Any]:
    source = _read(AUTO_DESIGN_COMPUTE)
    helper_start, helper_end, helper = _function_segment(
        source,
        "_handle_one_click_solver_partial_failing_final_updates_guard_coordinator",
    )
    finalization_start, finalization_end, finalization = _function_segment(
        source,
        "_finalize_one_click_solver_result_coordinator",
    )
    _, _, finalization_guard_dispatch = _function_segment(
        source,
        "_dispatch_one_click_solver_partial_failing_final_updates_guard_from_finalization_coordinator",
    )
    solve_start, solve_end, solve_body = _function_segment(source, "_solve_one_click_to_target")
    _, _, finish_body = _function_segment(
        source,
        "_finish_one_click_solver_iteration_loop_result_coordinator",
    )

    import inputs_page_modules.auto_design_compute as module  # noqa: E402

    no_op = _run_case(
        module,
        final_updates={},
        final_ok=False,
        init_fail_count=0,
        final_fail_count=0,
        improves=True,
        final_spacing_fail=False,
        final_target_domains=[],
    )
    spacing = _run_case(
        module,
        final_updates={"D": 50},
        final_ok=False,
        init_fail_count=0,
        final_fail_count=0,
        improves=True,
        final_spacing_fail=True,
        final_target_domains=["shear"],
    )
    best_effort = _run_case(
        module,
        final_updates={"D": 50},
        final_ok=False,
        init_fail_count=0,
        final_fail_count=0,
        improves=True,
        final_spacing_fail=False,
        final_target_domains=["bending"],
    )
    failing_cleanup = _run_case(
        module,
        final_updates={"D": 50},
        final_ok=False,
        init_fail_count=2,
        final_fail_count=1,
        improves=True,
        final_spacing_fail=False,
        final_target_domains=["shear"],
    )
    no_coverage = _run_case(
        module,
        final_updates={"D": 50},
        final_ok=False,
        init_fail_count=0,
        final_fail_count=1,
        improves=False,
        final_spacing_fail=False,
        final_target_domains=["bending", "shear"],
    )
    runtime = {
        "no_op": (
            no_op["final_updates"] == {}
            and no_op["stop_reason"] == "previous_stop"
            and no_op["partial_failing_final_updates_blocked"] is False
        ),
        "spacing_fail_blocks": (
            spacing["final_updates"] == {}
            and spacing["stop_reason"] == "minimum_shear_detailing_limit"
            and spacing["winning_label"] is None
            and spacing["partial_failing_final_updates_blocked"] is True
        ),
        "overdesign_best_effort_retained": (
            best_effort["final_updates"] == {"D": 50}
            and best_effort["stop_reason"] == "best_available_out_of_band_candidate"
            and best_effort["best_available_out_of_band_retained"] is True
        ),
        "failing_case_cleanup_retained": (
            failing_cleanup["final_updates"] == {"D": 50}
            and failing_cleanup["stop_reason"] == "best_available_out_of_band_candidate"
            and failing_cleanup["best_available_out_of_band_retained"] is True
        ),
        "no_multi_domain_coverage_blocks": (
            no_coverage["final_updates"] == {}
            and no_coverage["stop_reason"] == "no_multi_domain_target_candidate"
            and no_coverage["winning_action_type"] is None
            and no_coverage["partial_failing_final_updates_raw"] == {"D": 50}
        ),
    }
    static_checks = {
        "helper_present": "def _handle_one_click_solver_partial_failing_final_updates_guard_coordinator(" in source,
        "helper_preserves_final_progress": "_one_click_required_domain_progress(final_eval, mode_config)" in helper,
        "helper_preserves_best_effort_gate": "overdesign_best_effort_allowed = bool(" in helper,
        "helper_preserves_failing_cleanup_gate": "failing_case_cleanup_allowed = bool(" in helper,
        "helper_preserves_spacing_fail_stop": '"minimum_shear_detailing_limit"' in helper,
        "helper_preserves_best_available_stop": '"best_available_out_of_band_candidate"' in helper,
        "helper_preserves_no_coverage_stops": (
            '"no_multi_domain_target_candidate"' in helper and '"no_full_coverage_candidate"' in helper
        ),
        "helper_preserves_winner_clearing": (
            "winning_label = None" in helper and "winning_action_type = None" in helper
        ),
        "finalization_delegates_guard": (
            "_dispatch_one_click_solver_partial_failing_final_updates_guard_from_finalization_coordinator("
            in finalization
            and "_handle_one_click_solver_partial_failing_final_updates_guard_coordinator("
            in finalization_guard_dispatch
            and "finalization_scope[" in finalization_guard_dispatch
        ),
        "finish_delegates_finalization": "_finalize_one_click_solver_result_coordinator(" in finish_body,
        "solver_delegates_loop_result_finish": "_finish_one_click_solver_iteration_loop_result_coordinator("
        in solve_body,
        "finalization_rehydrates_guard_fields": all(
            token in finalization
            for token in (
                'final_updates = partial_failing_final_updates_guard_state["final_updates"]',
                'stop_reason = partial_failing_final_updates_guard_state["stop_reason"]',
                'winning_label = partial_failing_final_updates_guard_state["winning_label"]',
                'partial_failing_final_updates_blocked = partial_failing_final_updates_guard_state[',
                'best_available_out_of_band_retained = partial_failing_final_updates_guard_state[',
            )
        ),
    }
    status = "PASS"
    if not all(static_checks.values()) or not all(runtime.values()):
        status = "FAIL"
    return {
        "status": status,
        "surface": "_solve_one_click_to_target_partial_failing_final_updates_guard_coordinator",
        "helper_segment": {
            "function": "_handle_one_click_solver_partial_failing_final_updates_guard_coordinator",
            "start_line": helper_start,
            "end_line": helper_end,
            "line_count": helper_end - helper_start + 1,
        },
        "finalization_segment": {
            "function": "_finalize_one_click_solver_result_coordinator",
            "start_line": finalization_start,
            "end_line": finalization_end,
            "line_count": finalization_end - finalization_start + 1,
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
        "next_safe_slice": "extract final band-hit stop reason normalization",
    }


def write_artifacts(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now().isoformat(timespec="seconds").replace(":", "-")
    json_path = ARTIFACT_DIR / f"inputs_page_solver_partial_failing_final_updates_guard_coordinator_extraction_{stamp}.json"
    md_path = AUDIT_DIR / f"inputs_page_solver_partial_failing_final_updates_guard_coordinator_extraction_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Solver Partial-Failing Final Updates Guard Coordinator Extraction",
        "",
        f"Status: `{payload['status']}`",
        "",
        "## Static Checks",
    ]
    for key, value in payload["static_checks"].items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(["", "## Runtime"])
    for key, value in payload["runtime"].items():
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
