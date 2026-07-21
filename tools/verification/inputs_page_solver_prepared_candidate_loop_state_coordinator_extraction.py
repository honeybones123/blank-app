"""Verify one-click solver prepared candidate loop state coordinator extraction."""

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
    original = getattr(module, "_prepare_one_click_solver_candidates_coordinator", None)
    calls: list[dict[str, Any]] = []

    def _fake_prepare(**kwargs: Any) -> dict[str, Any]:
        calls.append(
            {
                "raw_candidates": list(kwargs.get("raw_candidates") or []),
                "working": dict(kwargs.get("working") or {}),
                "governing_domain": kwargs.get("governing_domain"),
                "use_governing_domain_candidates": kwargs.get("use_governing_domain_candidates"),
                "mode_config": dict(kwargs.get("mode_config") or {}),
            }
        )
        return {
            "pool_labels": ({"label": "A"},),
            "prepared": ({"rc": {"raw_updates": {}}, "raw_u": {}, "norm_u": {}, "direction": {}},),
            "prepared_samples": ({"sample": True},),
            "reduction_candidates_considered": "3",
            "governing_family_exists": 1,
            "shear_governing_family_detected": 0,
            "governing_family_exists_after_domain_fix": True,
            "shear_domain_prune_active": False,
            "should_apply_domain_prune": True,
            "mixed_direction_mode": "mixed",
        }

    try:
        module._prepare_one_click_solver_candidates_coordinator = _fake_prepare
        result = module._prepare_one_click_solver_prepared_candidate_loop_state_coordinator(
            raw_candidates=[{"label": "raw"}],
            working={"D": 650},
            governing_domain="shear",
            use_governing_domain_candidates=True,
            cur_eval={"overview": {}},
            mode_config={"mode": "probe"},
        )
    finally:
        if original is not None:
            module._prepare_one_click_solver_candidates_coordinator = original

    return {"result": result, "calls": calls}


def build_payload() -> dict[str, Any]:
    source = _read(AUTO_DESIGN_COMPUTE)
    helper_start, helper_end, helper = _function_segment(
        source,
        "_prepare_one_click_solver_prepared_candidate_loop_state_coordinator",
    )
    solve_start, solve_end, solve_body = _function_segment(source, "_solve_one_click_to_target")
    candidate_pipeline_start, candidate_pipeline_end, candidate_pipeline_body = _function_segment(
        source, "_prepare_one_click_solver_candidate_pipeline_state_coordinator"
    )
    _, _, pre_scoring_body = _function_segment(
        source,
        "_prepare_one_click_solver_candidate_pipeline_pre_scoring_state_coordinator",
    )
    import inputs_page_modules.auto_design_compute as module  # noqa: E402

    runtime = _run_case(module)
    result = runtime["result"]
    runtime_checks = {
        "prepare_call_preserved": runtime["calls"] == [
            {
                "raw_candidates": [{"label": "raw"}],
                "working": {"D": 650},
                "governing_domain": "shear",
                "use_governing_domain_candidates": True,
                "mode_config": {"mode": "probe"},
            }
        ],
        "prepared_state_rehydration_preserved": result["pool_labels"] == [{"label": "A"}]
        and result["prepared"] == [{"rc": {"raw_updates": {}}, "raw_u": {}, "norm_u": {}, "direction": {}}]
        and result["prepared_samples"] == [{"sample": True}]
        and result["reduction_candidates_considered"] == 3
        and result["governing_family_exists"] is True
        and result["shear_governing_family_detected"] is False
        and result["governing_family_exists_after_domain_fix"] is True
        and result["shear_domain_prune_active"] is False
        and result["should_apply_domain_prune"] is True
        and result["mixed_direction_mode"] == "mixed",
        "rejection_counter_defaults_preserved": result["growth_candidates_rejected_in_tightening"] == 0
        and result["rejected_as_non_governing_cleanup"] == 0
        and result["rejected_as_non_governing_shear_strengthening"] == 0
        and result["rejected_as_non_material_improvement"] == 0
        and result["rejected_as_no_real_change"] == 0
        and result["rejected_as_duplicate_signature"] == 0
        and result["rejected_as_evaluation_failed"] == 0,
    }
    static_checks = {
        "solver_delegates_iteration_loop": "_dispatch_one_click_solver_iteration_loop_from_solver_runtime_setup_coordinator(" in solve_body,
        "helper_present": "def _prepare_one_click_solver_prepared_candidate_loop_state_coordinator(" in source,
        "helper_delegates_to_existing_candidate_preparer": "_prepare_one_click_solver_candidates_coordinator("
        in helper,
        "helper_preserves_list_conversions": 'list(prepared_candidate_state["pool_labels"])' in helper
        and 'list(prepared_candidate_state["prepared"])' in helper
        and 'list(prepared_candidate_state["prepared_samples"])' in helper,
        "helper_preserves_bool_int_conversions": 'int(prepared_candidate_state["reduction_candidates_considered"])'
        in helper
        and 'bool(prepared_candidate_state["governing_family_exists"])' in helper
        and 'bool(prepared_candidate_state["should_apply_domain_prune"])' in helper,
        "helper_preserves_rejection_defaults": '"growth_candidates_rejected_in_tightening": 0' in helper
        and '"rejected_as_no_real_change": 0' in helper
        and '"rejected_as_evaluation_failed": 0' in helper,
        "candidate_pipeline_delegates_pre_scoring_state": (
            "_prepare_one_click_solver_candidate_pipeline_pre_scoring_state_coordinator("
            in candidate_pipeline_body
        ),
        "pre_scoring_delegates_prepared_loop_state": (
            "_prepare_one_click_solver_prepared_candidate_loop_state_coordinator(" in pre_scoring_body
        ),
        "candidate_pipeline_rehydrates_prepared_loop_fields": (
            'pool_labels = pre_scoring_state["pool_labels"]' in candidate_pipeline_body
            and 'mixed_direction_mode = pre_scoring_state["mixed_direction_mode"]'
            in candidate_pipeline_body
            and 'rejected_as_evaluation_failed = pre_scoring_state["rejected_as_evaluation_failed"]'
            in candidate_pipeline_body
        ),
        "solver_no_longer_inlines_prepared_loop_state": "prepared_candidate_state = _prepare_one_click_solver_candidates_coordinator("
        not in solve_body
        and "growth_candidates_rejected_in_tightening = 0" not in solve_body,
    }
    status = "PASS"
    if not all(static_checks.values()) or not all(runtime_checks.values()):
        status = "FAIL"
    return {
        "status": status,
        "surface": "_solve_one_click_to_target_prepared_candidate_loop_state_coordinator",
        "helper_segment": {
            "function": "_prepare_one_click_solver_prepared_candidate_loop_state_coordinator",
            "start_line": helper_start,
            "end_line": helper_end,
            "line_count": helper_end - helper_start + 1,
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
        "next_safe_slice": "extract no-real-change prepared-candidate rejection branch",
    }


def write_artifacts(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now().isoformat(timespec="seconds").replace(":", "-")
    json_path = ARTIFACT_DIR / f"inputs_page_solver_prepared_candidate_loop_state_coordinator_extraction_{stamp}.json"
    md_path = AUDIT_DIR / f"inputs_page_solver_prepared_candidate_loop_state_coordinator_extraction_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Solver Prepared Candidate Loop State Coordinator Extraction",
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
