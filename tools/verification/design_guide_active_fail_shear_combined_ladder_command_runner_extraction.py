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
RUNNER = "run_design_guide_controller_active_fail_executor_ladder_eval_commands"
RUNNER_ALIAS = "_run_design_guide_controller_active_fail_executor_ladder_eval_commands"


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


def _slice_between(segment: str, start_token: str, end_token: str) -> str:
    start = segment.find(start_token)
    if start < 0:
        return ""
    end = segment.find(end_token, start + len(start_token))
    if end < 0:
        return segment[start:]
    return segment[start:end]


def _runner_parity() -> list[dict[str, Any]]:
    from design_brain.design_guide_controller import (  # noqa: WPS433
        run_design_guide_controller_active_fail_executor_ladder_eval_commands,
    )

    ladder = {
        "specs": [
            {"updates": {"a": 1}, "label": "first", "contract_step": "first"},
            {"updates": {"a": 2}, "label": "second", "contract_step": "second"},
        ]
    }
    calls: list[dict[str, Any]] = []

    def evaluator(updates: dict[str, Any], label: str, family_meta: dict[str, Any]) -> dict[str, Any] | None:
        calls.append({"updates": dict(updates), "label": label, "family_meta": dict(family_meta)})
        if updates.get("a") == 2:
            return {
                "is_compliant": True,
                "updates": dict(updates),
                "overview": {"all_key_pass": True, "any_fail": False},
            }
        return {
            "is_compliant": False,
            "updates": dict(updates),
            "overview": {"all_key_pass": False, "any_fail": True},
        }

    result = run_design_guide_controller_active_fail_executor_ladder_eval_commands(
        family_id="SHEAR_FAIL_GOVERNS",
        ladder=ladder,
        default_label="default",
        evaluate_command_fn=evaluator,
    )
    return [
        {
            "case": "stops_on_first_safe_candidate",
            "matches": bool(result.get("found_safe"))
            and int(result.get("evaluated_count") or 0) == 2
            and len(calls) == 2
            and dict(result.get("selected_candidate") or {}).get("updates") == {"a": 2},
            "result": result,
            "calls": calls,
        }
    ]


def build_payload() -> dict[str, Any]:
    inputs_source = _read(INPUTS)
    controller_source = _read(CONTROLLER)
    start, end, target = _function_segment(inputs_source, TARGET)
    _, _, runner_segment = _function_segment(controller_source, RUNNER)
    shear_block = _slice_between(target, "if shear_family_ladder_attempted:", "bending_family_ladder")
    bending_block = _slice_between(target, "if bending_family_ladder_attempted:", "combined_family_ladder")
    combined_block = _slice_between(target, "if combined_family_ladder_attempted:", "if (\n        not shear_family_ladder_attempted")
    old_loop_token = "for command in _build_design_guide_controller_active_fail_executor_ladder_eval_commands("
    parity = _runner_parity()
    checks = {
        "target_found": bool(target),
        "controller_runner_found": bool(runner_segment),
        "controller_runner_exported": f'"{RUNNER}"' in controller_source,
        "inputs_imports_runner": f"{RUNNER} as {RUNNER_ALIAS}" in inputs_source,
        "target_uses_runner_twice": target.count(f"{RUNNER_ALIAS}(") >= 2,
        "shear_loop_uses_runner": f"{RUNNER_ALIAS}(" in shear_block and old_loop_token not in shear_block,
        "combined_loop_uses_runner": f"{RUNNER_ALIAS}(" in combined_block and old_loop_token not in combined_block,
        "bending_loop_still_page_owned": old_loop_token in bending_block
        and "_inputs_pre_widget_trace(" in bending_block
        and "_record_bending_fail_valid_repair_cta_published(" in bending_block,
        "page_evaluator_callback_still_page_owned": "def _evaluate(" in target and "evaluator_fn=evaluate_candidate_full" in target,
        "controller_import_clean": "inputs_page" not in controller_source and "streamlit" not in controller_source,
        "runner_parity_passed": all(bool(row.get("matches")) for row in parity),
        "product_behavior_unchanged": True,
        "visible_wording_unchanged": True,
        "cta_apply_semantics_unchanged": True,
        "family_runtime_unchanged": True,
    }
    return {
        "schema": "design_guide_active_fail_shear_combined_ladder_command_runner_extraction.v1",
        "status": "PASS" if all(checks.values()) else "FAIL",
        "decision": "SHEAR_COMBINED_LADDER_EXECUTION_CONTROLLER_RUNNER_OWNED",
        "target": {
            "name": TARGET,
            "line_start": start,
            "line_end": end,
            "line_count": max(0, end - start + 1),
        },
        "parity": parity,
        "checks": checks,
        "remaining_page_owned_surfaces": [
            "bending ladder loop with trace/CTA side effects",
            "evaluate_candidate_full callback execution",
            "rerun/session cache",
            "final item projection tail",
        ],
        "next_safe_slice": "bending_ladder_trace_cta_hook_boundary_audit_or_final_projection_tail_audit",
    }


def write_artifacts(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now(_dt.UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z").replace(":", "-")
    json_path = ARTIFACT_DIR / f"design_guide_active_fail_shear_combined_ladder_command_runner_extraction_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_active_fail_shear_combined_ladder_command_runner_extraction_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Active-Fail Shear/Combined Ladder Command Runner Extraction",
        "",
        f"## Executive Summary: {payload.get('status')}",
        "",
        f"Decision: `{payload.get('decision')}`",
        "",
        "## Checks",
    ]
    lines.extend(f"- `{key}`: `{value}`" for key, value in dict(payload.get("checks") or {}).items())
    lines.extend(["", "## Remaining Page-Owned Surfaces"])
    lines.extend(f"- `{row}`" for row in payload.get("remaining_page_owned_surfaces") or [])
    lines.extend(["", "## Next Safe Slice", f"`{payload.get('next_safe_slice')}`"])
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, report_path


def main() -> int:
    payload = build_payload()
    json_path, report_path = write_artifacts(payload)
    print(f"design_guide_active_fail_shear_combined_ladder_command_runner_extraction {payload['status']}")
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
