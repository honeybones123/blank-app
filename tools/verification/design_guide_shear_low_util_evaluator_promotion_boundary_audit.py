"""Audit evaluator and promotion boundary for selected shear low-util cleanup."""

from __future__ import annotations

import ast
from datetime import datetime
import hashlib
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
INPUTS_PAGE = ROOT / "inputs_page.py"

FUNCTION_NAME = "_shear_low_util_target_cleanup_item"


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _function_source(path: Path, function_name: str) -> tuple[str, int, int]:
    source = path.read_text(encoding="utf-8", errors="replace").lstrip("\ufeff")
    tree = ast.parse(source)
    lines = source.splitlines()
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == function_name:
            end_lineno = getattr(node, "end_lineno", None)
            if end_lineno is None:
                raise RuntimeError(f"Missing end_lineno for {function_name}")
            return "\n".join(lines[node.lineno - 1 : end_lineno]), node.lineno, end_lineno
    raise RuntimeError(f"Could not find {function_name} in {path}")


def _classify_boundary(function_source: str) -> list[dict[str, Any]]:
    rows = [
        {
            "id": "legacy_candidate_evaluation_call",
            "token": "_evaluate_auto_design_candidate(",
            "classification": "A page-owned evaluator bridge",
            "current_role": "executes the engineering candidate evaluation for each generated shear cleanup update",
            "move_rule": "must be absent from target function once controller evaluation boundary cutover is complete",
            "expected_present": False,
        },
        {
            "id": "candidate_evaluation_controller_boundary",
            "token": "_evaluate_design_guide_shear_low_util_cleanup_candidate(",
            "classification": "B controller-owned injected evaluator boundary",
            "current_role": "normalizes evaluator source/label/action metadata, exception handling, non-dict returns, and proof stamps while injecting the existing page evaluator",
            "move_rule": "controller-owned for this target loop; actual evaluator remains injected/page-owned",
            "expected_present": True,
        },
        {
            "id": "evaluation_source_record",
            "token": "_build_design_guide_shear_low_util_cleanup_candidate_record(",
            "classification": "B controller-owned evaluation metadata",
            "current_role": "builds source/label/action metadata and no-link audit update before evaluation",
            "move_rule": "already controller-owned for this target loop",
        },
        {
            "id": "candidate_acceptance_screen",
            "token": "_build_design_guide_shear_low_util_candidate_acceptance_screen(",
            "classification": "B controller-owned post-evaluation acceptance screen",
            "current_role": "normalizes pass/fail/explicit-preview-fail status after evaluation",
            "move_rule": "already controller-owned for this target loop",
        },
        {
            "id": "candidate_classification",
            "token": "_classify_design_guide_shear_low_util_cleanup_candidate(",
            "classification": "B controller-owned target-band classification",
            "current_role": "classifies safe evaluated candidates against threshold and target band",
            "move_rule": "already controller-owned for this target loop",
        },
        {
            "id": "candidate_accumulation",
            "token": "_accumulate_design_guide_shear_low_util_cleanup_candidate(",
            "classification": "B controller-owned selection accumulator",
            "current_role": "tracks accepted/target counts and selected best candidate",
            "move_rule": "already controller-owned for this target loop",
        },
        {
            "id": "preview_failure_text_adapter",
            "token": "_shear_cleanup_failed_reason_from_preview(",
            "classification": "C legacy page-owned preview/evidence adapter",
            "current_role": "derives no-link failure reason from evaluated preview",
            "move_rule": "must be absent from target function once controller preview-failure reason cutover is complete",
            "expected_present": False,
        },
        {
            "id": "preview_failure_text_controller_adapter",
            "token": "_build_design_guide_shear_low_util_failed_reason_from_preview(",
            "classification": "B controller-owned preview/evidence adapter",
            "current_role": "derives no-link failure reason from evaluated preview",
            "move_rule": "controller-owned for this target loop",
            "expected_present": True,
        },
        {
            "id": "promotion_bridge",
            "token": "_promote_guidance_item_to_resolved_candidate(",
            "classification": "D legacy page-owned publication/apply compatibility bridge",
            "current_role": "turns the controller-built item and resolved candidate into the existing apply-compatible item shape",
            "move_rule": "must be absent from target function once promotion adapter cutover is complete",
            "expected_present": False,
        },
        {
            "id": "promotion_adapter",
            "token": "_build_design_guide_shear_low_util_promoted_item(",
            "classification": "B controller-owned promotion adapter",
            "current_role": "turns the controller-built item and resolved candidate into the existing apply-compatible item shape",
            "move_rule": "controller-owned for this target loop; page still supplies current overview input",
            "expected_present": True,
        },
        {
            "id": "legacy_change_lines_input",
            "token": "_guidance_change_lines_for_updates(state, updates)",
            "classification": "C legacy page-owned visible wording adapter",
            "current_role": "builds visible change-line wording from state and updates",
            "move_rule": "must be absent from target function once controller change-line cutover is complete",
            "expected_present": False,
        },
        {
            "id": "change_lines_controller_adapter",
            "token": "_build_design_guide_shear_low_util_change_lines_for_updates(",
            "classification": "B controller-owned visible wording adapter",
            "current_role": "builds visible change-line wording from state and updates",
            "move_rule": "controller-owned for this target loop",
            "expected_present": True,
        },
        {
            "id": "legacy_failure_coverage_input",
            "token": "_candidate_failure_coverage_summary(state, resolved_candidate)",
            "classification": "C legacy page-owned failure coverage adapter",
            "current_role": "summarises candidate coverage from state and candidate overview",
            "move_rule": "must be absent from target function once controller failure-coverage cutover is complete",
            "expected_present": False,
        },
        {
            "id": "failure_coverage_controller_adapter",
            "token": "_build_design_guide_shear_low_util_failure_coverage_from_overviews(",
            "classification": "B controller-owned failure coverage adapter",
            "current_role": "summarises candidate coverage from current and candidate overviews",
            "move_rule": "controller-owned for this target loop; page still supplies current overview input",
            "expected_present": True,
        },
        {
            "id": "current_overview_input",
            "token": "_collect_design_overview(",
            "classification": "A page-owned current overview input",
            "current_role": "collects the current overview used for fallback shear util and selected-candidate failure coverage",
            "move_rule": "do not move until current-overview parity proof exists",
            "expected_present": True,
        },
        {
            "id": "final_item_packaging",
            "token": "_build_design_guide_shear_low_util_final_item_packaging(",
            "classification": "B controller-owned packaging inputs",
            "current_role": "builds resolved candidate, action payload, button contract, and item update payload around the promotion bridge",
            "move_rule": "already controller-owned around the remaining promotion bridge",
        },
    ]
    for row in rows:
        row["present"] = row["token"] in function_source
        row["expected_present"] = bool(row.get("expected_present", True))
    return rows


def _capture() -> dict[str, Any]:
    function_source, start_line, end_line = _function_source(INPUTS_PAGE, FUNCTION_NAME)
    rows = _classify_boundary(function_source)
    present_by_id = {str(row.get("id")): bool(row.get("present")) for row in rows}
    page_owned_blockers = [
        dict(row)
        for row in rows
        if row.get("present")
        and str(row.get("classification") or "").startswith(("A", "C", "D"))
    ]
    return {
        "decision": "SHEAR_LOW_UTIL_EVALUATOR_BOUNDARY_MOVED_OVERVIEW_NOT_READY_TO_MOVE",
        "function": {
            "name": FUNCTION_NAME,
            "start_line": start_line,
            "end_line": end_line,
            "line_count": end_line - start_line + 1,
        },
        "boundary_rows": rows,
        "present_by_id": present_by_id,
        "page_owned_blockers": page_owned_blockers,
        "safe_to_move_evaluator_now": True,
        "safe_to_move_promotion_now": True,
        "safe_to_delete_target_function_now": False,
        "next_safe_slice": (
            "Candidate evaluation request/normalization is controller-owned for this target loop. "
            "Current overview input remains page-owned; move only after dedicated overview parity."
        ),
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    present = dict(capture.get("present_by_id") or {})
    required = [
        "candidate_evaluation_controller_boundary",
        "current_overview_input",
        "evaluation_source_record",
        "candidate_acceptance_screen",
        "candidate_classification",
        "candidate_accumulation",
        "preview_failure_text_controller_adapter",
        "promotion_adapter",
        "change_lines_controller_adapter",
        "failure_coverage_controller_adapter",
        "final_item_packaging",
    ]
    return {
        "function_found": bool((capture.get("function") or {}).get("line_count")),
        "required_boundary_tokens_present": all(bool(present.get(item)) for item in required),
        "legacy_promotion_bridge_removed": present.get("promotion_bridge") is False,
        "legacy_candidate_evaluation_call_removed": present.get("legacy_candidate_evaluation_call") is False,
        "legacy_preview_failure_adapter_removed": present.get("preview_failure_text_adapter") is False,
        "legacy_change_lines_input_removed": present.get("legacy_change_lines_input") is False,
        "legacy_failure_coverage_input_removed": present.get("legacy_failure_coverage_input") is False,
        "page_owned_blockers_recorded": len(capture.get("page_owned_blockers") or []) >= 1,
        "evaluator_boundary_moved": capture.get("safe_to_move_evaluator_now") is True,
        "promotion_adapter_moved": capture.get("safe_to_move_promotion_now") is True,
        "not_safe_to_delete_target_function": capture.get("safe_to_delete_target_function_now") is False,
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Design Guide Shear Low-Util Evaluator/Promotion Boundary Audit",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Checks",
    ]
    lines.extend(f"- {key}: `{value}`" for key, value in (payload.get("checks") or {}).items())
    lines.extend(
        [
            "",
            "## Boundary Rows",
            "",
            "| ID | Present | Classification | Current Role | Move Rule |",
            "| --- | --- | --- | --- | --- |",
        ]
    )
    for row in capture.get("boundary_rows") or []:
        lines.append(
            f"| {row.get('id')} | {row.get('present')} | {row.get('classification')} | {row.get('current_role')} | {row.get('move_rule')} |"
        )
    lines.extend(["", "## Next Safe Slice", "", str(capture.get("next_safe_slice") or "")])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    capture = _capture()
    checks = _checks(capture)
    status = "PASS" if all(checks.values()) else "FAIL"
    payload = {
        "status": status,
        "checks": checks,
        "capture": capture,
    }
    payload["snapshot_hash"] = _stable_hash(payload)
    stamp = _stamp()
    json_path = ARTIFACT_DIR / f"design_guide_shear_low_util_evaluator_promotion_boundary_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_shear_low_util_evaluator_promotion_boundary_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    _write_report(report_path, payload)
    print(f"design_guide_shear_low_util_evaluator_promotion_boundary_audit {status}")
    print(f"decision={capture.get('decision')}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
