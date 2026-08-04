"""Verify auto-design final-candidate commit context coordinator extraction."""

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


def _run_case(module: Any, *, use_solver_preview: bool) -> dict[str, Any]:
    originals = {
        "BEAM_STATUS_FAIL": getattr(module, "BEAM_STATUS_FAIL", None),
        "_collect_design_overview": getattr(module, "_collect_design_overview", None),
        "_current_design_guide_fail_fingerprint": getattr(module, "_current_design_guide_fail_fingerprint", None),
        "_parse_util_value": getattr(module, "_parse_util_value", None),
        "_evaluate_auto_design_candidate": getattr(module, "_evaluate_auto_design_candidate", None),
        "_build_canonical_design_state_pack": getattr(module, "_build_canonical_design_state_pack", None),
        "_candidate_failure_coverage_summary": getattr(module, "_candidate_failure_coverage_summary", None),
        "_candidate_is_valid_primary_one_click": getattr(module, "_candidate_is_valid_primary_one_click", None),
    }
    eval_calls: list[dict[str, Any]] = []
    current_state = {"D": 600, "canonical": True}
    final_updates = {"D": 650}
    solver_preview = {"D": 640, "preview": True} if use_solver_preview else {}

    def _evaluate(state: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
        eval_calls.append({"state": dict(state), "kwargs": dict(kwargs)})
        return {"candidate": True, "state": dict(state)}

    try:
        module.BEAM_STATUS_FAIL = "FAIL"
        module._collect_design_overview = lambda state: {
            "statuses": {"bending": "FAIL", "shear": "PASS"},
            "utils": {"shear": "0.72"},
            "overview_shear_selection_origin": "overview",
        }
        module._current_design_guide_fail_fingerprint = lambda overview: {"bending": "FAIL"}
        module._parse_util_value = lambda value: float(value)
        module._evaluate_auto_design_candidate = _evaluate
        module._build_canonical_design_state_pack = lambda state: {**dict(state), "packed": True}
        module._candidate_failure_coverage_summary = lambda state, candidate: {
            "covers_all_current_failures": False,
            "covered_fail_keys": ["shear"],
            "remaining_fail_keys": ["bending"],
        }
        module._candidate_is_valid_primary_one_click = lambda candidate, overview: (
            False,
            {
                "reason": "partial_failure_coverage",
                "fail_keys": ["bending", "shear"],
                "covered_fail_keys": ["shear"],
                "remaining_fail_keys": ["bending"],
            },
        )
        result = module._prepare_auto_design_final_candidate_commit_context_coordinator(
            solve={"final_state_preview": solver_preview},
            current_state=current_state,
            final_updates=final_updates,
            win_l="Winner",
            win_at="adjust",
            dbg={"seed": "kept"},
        )
    finally:
        for name, original in originals.items():
            if original is not None:
                setattr(module, name, original)

    return {
        "result": result,
        "eval_calls": eval_calls,
    }


def build_payload() -> dict[str, Any]:
    source = _read(AUTO_DESIGN_COMPUTE)
    helper_start, helper_end, helper = _function_segment(
        source,
        "_prepare_auto_design_final_candidate_commit_context_coordinator",
    )
    orchestration_start, orchestration_end, orchestration_body = _function_segment(
        source,
        "_resolve_auto_design_final_candidate_partial_commit_orchestration_coordinator",
    )
    run_start, run_end, run_body = _function_segment(source, "run_one_click_auto_design")
    _, _, tail_body = _function_segment(
        source,
        "_run_one_click_auto_design_solver_and_final_response_coordinator",
    )
    _, _, post_solver_commit_body = _function_segment(
        source,
        "_run_auto_design_post_solver_commit_orchestration_coordinator",
    )
    _, _, commit_body = _function_segment(
        source,
        "_run_auto_design_commit_orchestration_coordinator",
    )
    _, _, commit_final_candidate_dispatch = _function_segment(
        source,
        "_dispatch_auto_design_final_candidate_partial_gate_from_commit_orchestration_coordinator",
    )
    import inputs_page_modules.auto_design_compute as module  # noqa: E402

    preview_runtime = _run_case(module, use_solver_preview=True)
    update_runtime = _run_case(module, use_solver_preview=False)
    preview_dbg = preview_runtime["result"]["dbg"]
    update_dbg = update_runtime["result"]["dbg"]
    preview_candidate = preview_runtime["result"]["candidate_for_commit"]
    runtime_checks = {
        "preview_path_uses_solver_final_preview": bool(preview_runtime["eval_calls"])
        and preview_runtime["eval_calls"][0]["state"].get("preview") is True
        and preview_runtime["eval_calls"][0]["state"].get("packed") is True
        and preview_runtime["eval_calls"][0]["kwargs"].get("updates") is None,
        "update_path_uses_current_state_with_updates": bool(update_runtime["eval_calls"])
        and update_runtime["eval_calls"][0]["state"].get("D") == 600
        and update_runtime["eval_calls"][0]["kwargs"].get("updates") == {"D": 650}
        and update_runtime["eval_calls"][0]["kwargs"].get("action_type") == "apply_resolved_candidate",
        "debug_fail_context": preview_dbg.get("current_fail_keys") == ["bending"]
        and preview_dbg.get("current_fail_fingerprint") == {"bending": "FAIL"}
        and preview_dbg.get("shear_fail_util_used") == 0.72
        and preview_dbg.get("current_shear_selection_origin") == "overview",
        "candidate_coverage_attached": preview_candidate.get("failure_coverage", {}).get("remaining_fail_keys") == ["bending"]
        and preview_candidate.get("covers_all_current_failures") is False,
        "validity_metadata_written": preview_dbg.get("one_click_final_candidate_valid_for_commit") is False
        and preview_dbg.get("one_click_final_candidate_valid_reason") == "partial_failure_coverage"
        and preview_dbg.get("candidate_remaining_fail_keys") == ["bending"],
        "seed_debug_preserved": update_dbg.get("seed") == "kept",
    }
    static_checks = {
        "helper_present": "def _prepare_auto_design_final_candidate_commit_context_coordinator(" in source,
        "helper_prefers_solver_preview": "solver_final_preview = solve.get(\"final_state_preview\")" in helper,
        "helper_preserves_coverage_summary": "_candidate_failure_coverage_summary(current_state, candidate_for_commit or {})" in helper,
        "helper_preserves_validity_check": "_candidate_is_valid_primary_one_click(" in helper,
        "helper_returns_context": '"final_candidate_commit_meta": final_candidate_commit_meta' in helper,
        "commit_orchestration_delegates_final_candidate_partial_gate": (
            "_dispatch_auto_design_final_candidate_partial_gate_from_commit_orchestration_coordinator("
            in commit_body
            and "_resolve_auto_design_final_candidate_partial_commit_orchestration_coordinator("
            in commit_final_candidate_dispatch
        ),
        "final_candidate_partial_gate_delegates_final_candidate_context": (
            "_prepare_auto_design_final_candidate_commit_context_coordinator("
            in orchestration_body
        ),
        "final_candidate_partial_gate_delegates_partial_commit_gate": (
            "_resolve_auto_design_partial_commit_gate_coordinator(" in orchestration_body
        ),
        "post_solver_commit_delegates_commit_orchestration": "_run_auto_design_commit_orchestration_coordinator("
        in post_solver_commit_body,
        "run_delegates_post_solver_commit_orchestration": (
            "_run_one_click_auto_design_solver_and_final_response_coordinator(" in run_body
            and "_run_auto_design_post_solver_commit_orchestration_coordinator(" in tail_body
        ),
    }
    status = "PASS"
    if not all(static_checks.values()) or not all(runtime_checks.values()):
        status = "FAIL"
    return {
        "status": status,
        "surface": "run_one_click_auto_design_final_candidate_commit_context_coordinator",
        "helper_segment": {
            "function": "_prepare_auto_design_final_candidate_commit_context_coordinator",
            "start_line": helper_start,
            "end_line": helper_end,
            "line_count": helper_end - helper_start + 1,
        },
        "orchestration_segment": {
            "function": "_resolve_auto_design_final_candidate_partial_commit_orchestration_coordinator",
            "start_line": orchestration_start,
            "end_line": orchestration_end,
            "line_count": orchestration_end - orchestration_start + 1,
        },
        "run_segment": {
            "function": "run_one_click_auto_design",
            "start_line": run_start,
            "end_line": run_end,
            "line_count": run_end - run_start + 1,
        },
        "static_checks": static_checks,
        "runtime_checks": runtime_checks,
        "preview_runtime": preview_runtime,
        "update_runtime": update_runtime,
        "product_behavior_changed": False,
        "next_safe_slice": "extract partial commit allowance gate from run_one_click_auto_design",
    }


def write_artifacts(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now().isoformat(timespec="seconds").replace(":", "-")
    json_path = ARTIFACT_DIR / f"inputs_page_auto_design_final_candidate_context_coordinator_extraction_{stamp}.json"
    md_path = AUDIT_DIR / f"inputs_page_auto_design_final_candidate_context_coordinator_extraction_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Auto Design Final-Candidate Context Coordinator Extraction",
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
    lines.extend(
        [
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
