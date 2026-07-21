"""Verify final band-hit stop normalization solver coordinator extraction."""

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


ELIGIBLE_REASONS = (
    "best_available_out_of_band_candidate",
    "no_improving_candidate",
    "no_actionable_candidates_after_full_tightening_search",
    "non_material_remaining_candidates",
    "no_actionable_candidates",
    "tightening_depth_budget_reached",
)


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


def _run_cases(module: Any) -> dict[str, bool]:
    eligible = [
        module._handle_one_click_solver_final_band_hit_stop_normalization_coordinator(
            final_band_hit=True,
            stop_reason=reason,
            status="exhausted",
        )
        == {"stop_reason": "reached_target_band", "status": "solved"}
        for reason in ELIGIBLE_REASONS
    ]
    ineligible = module._handle_one_click_solver_final_band_hit_stop_normalization_coordinator(
        final_band_hit=True,
        stop_reason="minimum_shear_detailing_limit",
        status="failed",
    )
    no_band_hit = module._handle_one_click_solver_final_band_hit_stop_normalization_coordinator(
        final_band_hit=False,
        stop_reason="best_available_out_of_band_candidate",
        status="exhausted",
    )
    none_reason = module._handle_one_click_solver_final_band_hit_stop_normalization_coordinator(
        final_band_hit=True,
        stop_reason=None,
        status=None,
    )
    return {
        "eligible_reasons_normalize": all(eligible),
        "ineligible_reason_preserved": ineligible
        == {"stop_reason": "minimum_shear_detailing_limit", "status": "failed"},
        "no_band_hit_preserved": no_band_hit
        == {"stop_reason": "best_available_out_of_band_candidate", "status": "exhausted"},
        "none_reason_preserved": none_reason == {"stop_reason": None, "status": None},
    }


def build_payload() -> dict[str, Any]:
    source = _read(AUTO_DESIGN_COMPUTE)
    helper_start, helper_end, helper = _function_segment(
        source,
        "_handle_one_click_solver_final_band_hit_stop_normalization_coordinator",
    )
    finalization_start, finalization_end, finalization = _function_segment(
        source,
        "_finalize_one_click_solver_result_coordinator",
    )
    _, _, normalization_dispatch = _function_segment(
        source,
        "_dispatch_one_click_solver_final_band_hit_stop_normalization_from_finalization_coordinator",
    )
    solve_start, solve_end, solve_body = _function_segment(source, "_solve_one_click_to_target")
    _, _, finish_body = _function_segment(
        source,
        "_finish_one_click_solver_iteration_loop_result_coordinator",
    )

    import inputs_page_modules.auto_design_compute as module  # noqa: E402

    runtime = _run_cases(module)
    static_checks = {
        "helper_present": "def _handle_one_click_solver_final_band_hit_stop_normalization_coordinator(" in source,
        "helper_preserves_final_band_hit_gate": "if final_band_hit and str(stop_reason or \"\") in {" in helper,
        "helper_preserves_reason_set": all(f'"{reason}"' in helper for reason in ELIGIBLE_REASONS),
        "helper_preserves_reached_target_assignment": 'stop_reason = "reached_target_band"' in helper,
        "helper_preserves_solved_status_assignment": 'status = "solved"' in helper,
        "finalization_delegates_normalization": (
            "_dispatch_one_click_solver_final_band_hit_stop_normalization_from_finalization_coordinator("
            in finalization
            and "_handle_one_click_solver_final_band_hit_stop_normalization_coordinator("
            in normalization_dispatch
            and "finalization_scope[" in normalization_dispatch
        ),
        "finish_delegates_finalization": "_finalize_one_click_solver_result_coordinator(" in finish_body,
        "solver_delegates_loop_result_finish": "_finish_one_click_solver_iteration_loop_result_coordinator("
        in solve_body,
        "finalization_rehydrates_normalized_fields": all(
            token in finalization
            for token in (
                'stop_reason = final_band_hit_stop_normalization_state["stop_reason"]',
                'status = final_band_hit_stop_normalization_state["status"]',
            )
        ),
    }
    status = "PASS"
    if not all(static_checks.values()) or not all(runtime.values()):
        status = "FAIL"
    return {
        "status": status,
        "surface": "_solve_one_click_to_target_final_band_hit_stop_normalization_coordinator",
        "helper_segment": {
            "function": "_handle_one_click_solver_final_band_hit_stop_normalization_coordinator",
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
        "next_safe_slice": "extract rescue entry decision state coordinator",
    }


def write_artifacts(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now().isoformat(timespec="seconds").replace(":", "-")
    json_path = ARTIFACT_DIR / f"inputs_page_solver_final_band_hit_stop_normalization_coordinator_extraction_{stamp}.json"
    md_path = AUDIT_DIR / f"inputs_page_solver_final_band_hit_stop_normalization_coordinator_extraction_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Solver Final Band-Hit Stop Normalization Coordinator Extraction",
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
