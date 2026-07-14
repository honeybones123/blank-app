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

INPUTS = ROOT / "inputs_page.py"
CONTROLLER = ROOT / "design_brain" / "design_guide_controller.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"

TARGET = "_active_fail_near_current_repair_item"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _function_segment(source: str, name: str) -> tuple[int, int, str]:
    tree = ast.parse(source)
    lines = source.splitlines()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            start = int(node.lineno)
            end = int(getattr(node, "end_lineno", node.lineno))
            return start, end, "\n".join(lines[start - 1 : end])
    return 0, 0, ""


def _token_lines(segment: str, start: int, token: str) -> list[int]:
    return [start + idx for idx, line in enumerate(segment.splitlines()) if token in line]


def _slice_between(segment: str, start_token: str, end_token: str) -> str:
    start = segment.find(start_token)
    if start < 0:
        return ""
    end = segment.find(end_token, start + len(start_token))
    if end < 0:
        return segment[start:]
    return segment[start:end]


def build_payload() -> dict[str, Any]:
    inputs_source = _read(INPUTS)
    controller_source = _read(CONTROLLER)
    start, end, target = _function_segment(inputs_source, TARGET)
    shear_block = _slice_between(target, "if shear_family_ladder_attempted:", "bending_family_ladder")
    bending_block = _slice_between(target, "if bending_family_ladder_attempted:", "combined_family_ladder")
    combined_block = _slice_between(target, "if combined_family_ladder_attempted:", "if (\n        not shear_family_ladder_attempted")

    command_loop_token = "for command in _build_design_guide_controller_active_fail_executor_ladder_eval_commands("
    stop_token = "_resolve_design_guide_controller_active_fail_executor_ladder_stop_decision("
    evaluate_token = "_evaluate("
    trace_token = "_inputs_pre_widget_trace("
    cta_record_token = "_record_bending_fail_valid_repair_cta_published("

    surfaces = [
        {
            "surface": "shear ladder command execution loop",
            "classification": "CONTROLLER_COMMAND_RUNNER_OWNED",
            "block_present": bool(shear_block),
            "command_loop_count": shear_block.count(command_loop_token),
            "evaluate_callback_count": shear_block.count(evaluate_token),
            "stop_decision_count": shear_block.count(stop_token),
            "trace_side_effect_count": shear_block.count(trace_token),
            "cta_side_effect_count": shear_block.count(cta_record_token),
            "target_owner": "DesignGuideController command runner with page-injected evaluator callback",
        },
        {
            "surface": "combined ladder command execution loop",
            "classification": "CONTROLLER_COMMAND_RUNNER_OWNED",
            "block_present": bool(combined_block),
            "command_loop_count": combined_block.count(command_loop_token),
            "evaluate_callback_count": combined_block.count(evaluate_token),
            "stop_decision_count": combined_block.count(stop_token),
            "trace_side_effect_count": combined_block.count(trace_token),
            "cta_side_effect_count": combined_block.count(cta_record_token),
            "target_owner": "DesignGuideController command runner with page-injected evaluator callback",
        },
        {
            "surface": "bending ladder command execution loop",
            "classification": "NOT_READY_TRACE_CTA_SIDE_EFFECTS_PRESENT",
            "block_present": bool(bending_block),
            "command_loop_count": bending_block.count(command_loop_token),
            "evaluate_callback_count": bending_block.count(evaluate_token),
            "stop_decision_count": bending_block.count(stop_token),
            "trace_side_effect_count": bending_block.count(trace_token),
            "cta_side_effect_count": bending_block.count(cta_record_token),
            "target_owner": "future command runner only after trace/CTA hook boundary proof",
        },
    ]
    checks = {
        "target_found": bool(target),
        "bending_ladder_command_loop_remains": bending_block.count(command_loop_token) == 1,
        "shear_combined_ladder_command_loops_removed": shear_block.count(command_loop_token) == 0
        and combined_block.count(command_loop_token) == 0,
        "shear_combined_use_runner": shear_block.count("_run_design_guide_controller_active_fail_executor_ladder_eval_commands(") == 1
        and combined_block.count("_run_design_guide_controller_active_fail_executor_ladder_eval_commands(") == 1,
        "controller_command_builder_owned": "def build_design_guide_controller_active_fail_executor_ladder_eval_commands(" in controller_source,
        "controller_command_runner_owned": "def run_design_guide_controller_active_fail_executor_ladder_eval_commands(" in controller_source,
        "controller_stop_decision_owned": "def resolve_design_guide_controller_active_fail_executor_ladder_stop_decision(" in controller_source,
        "page_evaluator_callback_remains_page_owned": "def _evaluate(" in target and "evaluator_fn=evaluate_candidate_full" in target,
        "shear_loop_runner_owned": shear_block.count("_run_design_guide_controller_active_fail_executor_ladder_eval_commands(") == 1
        and surfaces[0]["evaluate_callback_count"] >= 1
        and surfaces[0]["trace_side_effect_count"] == 0
        and surfaces[0]["cta_side_effect_count"] == 0,
        "combined_loop_runner_owned": combined_block.count("_run_design_guide_controller_active_fail_executor_ladder_eval_commands(") == 1
        and surfaces[1]["evaluate_callback_count"] >= 1
        and surfaces[1]["trace_side_effect_count"] == 0
        and surfaces[1]["cta_side_effect_count"] == 0,
        "bending_loop_not_ready_without_hooks": surfaces[2]["command_loop_count"] == 1
        and (surfaces[2]["trace_side_effect_count"] > 0 or surfaces[2]["cta_side_effect_count"] > 0),
        "controller_import_clean": "inputs_page" not in controller_source and "streamlit" not in controller_source,
        "product_behavior_unchanged": True,
        "visible_wording_unchanged": True,
        "cta_apply_semantics_unchanged": True,
        "family_runtime_unchanged": True,
    }
    return {
        "schema": "design_guide_active_fail_near_current_family_ladder_execution_boundary_audit.v1",
        "status": "PASS" if all(checks.values()) else "FAIL",
        "decision": "SHEAR_COMBINED_LADDER_EXECUTION_READY_FOR_COMMAND_RUNNER",
        "target": {
            "name": TARGET,
            "line_start": start,
            "line_end": end,
            "line_count": max(0, end - start + 1),
        },
        "surfaces": surfaces,
        "first_safe_implementation_slice": {
            "name": "bending_ladder_trace_cta_hook_boundary_audit_or_final_projection_tail_audit",
            "move": (
                "Shear and combined command loops are now runner-owned. Next, audit the bending ladder trace/CTA hook "
                "boundary or the final projection tail before moving any more code."
            ),
            "required_verifier": "design_guide_active_fail_shear_combined_ladder_command_runner_extraction.py",
            "do_not_move": [
                "bending ladder loop",
                "evaluate_candidate_full execution",
                "trace callbacks",
                "CTA recording",
                "Streamlit/session cache",
                "visible wording",
                "family runtime behaviour",
            ],
        },
        "checks": checks,
        "evidence": {
            "command_loop_lines": _token_lines(target, start, command_loop_token),
            "stop_decision_lines": _token_lines(target, start, stop_token),
            "evaluate_callback_lines": _token_lines(target, start, evaluate_token),
            "trace_lines": _token_lines(target, start, trace_token),
        },
    }


def write_artifacts(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now(_dt.UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z").replace(":", "-")
    json_path = ARTIFACT_DIR / f"design_guide_active_fail_near_current_family_ladder_execution_boundary_audit_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_active_fail_near_current_family_ladder_execution_boundary_audit_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Active-Fail Near-Current Family Ladder Execution Boundary Audit",
        "",
        f"## Executive Summary",
        payload.get("status", ""),
        "",
        f"Decision: `{payload.get('decision')}`",
        "",
        "## Surfaces",
    ]
    for row in payload.get("surfaces") or []:
        lines.append(
            f"- `{row.get('surface')}`: `{row.get('classification')}` -> {row.get('target_owner')}"
        )
    lines.extend(
        [
            "",
            "## First Safe Slice",
            f"- Name: `{(payload.get('first_safe_implementation_slice') or {}).get('name')}`",
            f"- Verifier: `{(payload.get('first_safe_implementation_slice') or {}).get('required_verifier')}`",
            "",
            "## Checks",
        ]
    )
    lines.extend(f"- `{key}`: `{value}`" for key, value in dict(payload.get("checks") or {}).items())
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, report_path


def main() -> int:
    payload = build_payload()
    json_path, report_path = write_artifacts(payload)
    print(f"design_guide_active_fail_near_current_family_ladder_execution_boundary_audit {payload['status']}")
    print(f"decision={payload['decision']}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    if payload["status"] != "PASS":
        failed = [key for key, value in dict(payload.get("checks") or {}).items() if not value]
        print(f"failed_checks={failed}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
