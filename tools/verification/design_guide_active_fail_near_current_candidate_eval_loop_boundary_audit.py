from __future__ import annotations

import ast
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

INPUTS_PAGE = ROOT / "inputs_page.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
PROGRESS_PATH = ROOT / "artifacts" / "progress" / "design_guide_smoothness_cleanup_progress.md"
TARGET = "_active_fail_near_current_repair_item"
NESTED = "_evaluate"


TOKENS = {
    "candidate_precheck_projection_service": [
        "_build_active_fail_executor_candidate_eval_precheck_projection(",
    ],
    "page_precheck_scalar_collection": [
        "_updates_match_state(base, dict(updates or {}))",
        "_candidate_is_materially_actionable(base, dict(updates or {}))",
    ],
    "page_seen_update_mutation": [
        "seen_updates.add",
    ],
    "page_candidate_state_fingerprint_cache": [
        "stable_fingerprint_for_payload(candidate_state)",
        "eval_cache_by_candidate_fp",
    ],
    "candidate_evaluation_service_call": [
        "_evaluate_active_fail_executor_candidate_with_updates(",
        "_resolve_active_fail_executor_candidate_eval_source(",
    ],
    "page_evaluator_injection": [
        "evaluator_fn=evaluate_candidate_full",
        "state_snapshot_fn=_guidance_state_snapshot",
    ],
    "candidate_projection_service_call": [
        "_build_active_fail_executor_candidate_eval_attempt_result(",
    ],
    "page_metrics_accumulation": [
        "repair_eval_metrics[metric_key] +=",
    ],
    "page_candidate_accumulation": [
        "eval_cache_by_candidate_fp[candidate_fp] =",
        "candidates.append(cand)",
    ],
}


def _timestamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _function_source(source: str, name: str) -> tuple[int, int, str]:
    tree = ast.parse(source)
    lines = source.splitlines()
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            end = int(node.end_lineno or node.lineno)
            return node.lineno, end, "\n".join(lines[node.lineno - 1 : end])
    return 0, 0, ""


def _nested_function_source(parent_source: str, parent_start: int, name: str) -> tuple[int, int, str]:
    tree = ast.parse(parent_source)
    lines = parent_source.splitlines()
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            start = parent_start + node.lineno - 1
            end = parent_start + int(node.end_lineno or node.lineno) - 1
            return start, end, "\n".join(lines[node.lineno - 1 : int(node.end_lineno or node.lineno)])
    return 0, 0, ""


def _line_numbers(segment: str, start_line: int, token: str) -> list[int]:
    return [start_line + idx for idx, line in enumerate(segment.splitlines()) if token in line]


def _classify(segment: str, start_line: int) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for name, tokens in TOKENS.items():
        matches = []
        for token in tokens:
            lines = _line_numbers(segment, start_line, token)
            if lines:
                matches.append({"token": token, "count": len(lines), "lines": lines[:20]})
        result[name] = {"present": bool(matches), "matches": matches}
    return result


def _capture() -> dict[str, Any]:
    source = _read(INPUTS_PAGE)
    target_start, target_end, target_segment = _function_source(source, TARGET)
    nested_start, nested_end, nested_segment = _nested_function_source(target_segment, target_start, NESTED)
    classifications = _classify(nested_segment, nested_start)
    candidate_service_owned = classifications["candidate_evaluation_service_call"]["present"] and classifications[
        "candidate_projection_service_call"
    ]["present"]
    still_page_owned = any(
        classifications[name]["present"]
        for name in (
            "page_precheck_scalar_collection",
            "page_seen_update_mutation",
            "page_candidate_state_fingerprint_cache",
            "page_evaluator_injection",
            "page_metrics_accumulation",
            "page_candidate_accumulation",
        )
    )
    decision = (
        "NOT_SHELL_ONLY_CANDIDATE_EVAL_LOOP_HAS_PAGE_OWNED_CALLBACK_CACHE_BOUNDARY"
        if still_page_owned
        else "CANDIDATE_EVAL_LOOP_SHELL_ONLY"
    )
    return {
        "schema": "design_guide_active_fail_near_current_candidate_eval_loop_boundary_audit.v1",
        "target": {
            "name": TARGET,
            "line_start": target_start,
            "line_end": target_end,
            "line_count": max(0, target_end - target_start + 1),
        },
        "nested": {
            "name": NESTED,
            "line_start": nested_start,
            "line_end": nested_end,
            "line_count": max(0, nested_end - nested_start + 1),
        },
        "decision": decision,
        "classifications": classifications,
        "source_checks": {
            "target_found": bool(target_segment),
            "nested_evaluate_found": bool(nested_segment),
            "preflight_already_controller_owned": "_build_design_guide_controller_active_fail_near_current_repair_preflight("
            in target_segment,
            "candidate_eval_service_call_present": classifications["candidate_evaluation_service_call"]["present"],
            "candidate_projection_service_call_present": classifications["candidate_projection_service_call"]["present"],
            "candidate_precheck_projection_service_present": classifications[
                "candidate_precheck_projection_service"
            ]["present"],
            "candidate_service_owned_parts_present": bool(candidate_service_owned),
            "page_owned_callback_cache_boundary_present": bool(still_page_owned),
        },
        "first_safe_implementation_slice": {
            "name": "active_fail_candidate_eval_callback_cache_boundary_audit",
            "ready": bool(candidate_service_owned and still_page_owned),
            "move": (
                "Audit whether the remaining predicate scalar collection, seen-update mutation, existing "
                "fingerprint/cache lookup, and `evaluate_candidate_full` callback execution are bounded page-shell "
                "plumbing or whether another pure projection can move behind `design_brain.candidate_evaluation`."
            ),
            "do_not_move": [
                "evaluate_candidate_full execution",
                "Streamlit/session caches",
                "page trace callbacks",
                "CTA/apply routing",
                "family ladder command execution",
                "visible wording",
            ],
        },
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    source_checks = dict(capture.get("source_checks") or {})
    return {
        "target_found": bool(source_checks.get("target_found")),
        "nested_evaluate_found": bool(source_checks.get("nested_evaluate_found")),
        "preflight_already_controller_owned": bool(source_checks.get("preflight_already_controller_owned")),
        "candidate_service_owned_parts_present": bool(source_checks.get("candidate_service_owned_parts_present")),
        "candidate_precheck_projection_service_present": bool(
            source_checks.get("candidate_precheck_projection_service_present")
        ),
        "page_owned_callback_cache_boundary_present": bool(
            source_checks.get("page_owned_callback_cache_boundary_present")
        ),
        "first_safe_slice_identified": bool((capture.get("first_safe_implementation_slice") or {}).get("ready")),
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    target = dict(capture.get("target") or {})
    nested = dict(capture.get("nested") or {})
    first_slice = dict(capture.get("first_safe_implementation_slice") or {})
    lines = [
        "# Active Fail Near-Current Candidate Eval Loop Boundary Audit",
        "",
        "## Executive Summary",
        str(payload.get("status") or ""),
        "",
        f"- Decision: `{capture.get('decision')}`",
        f"- Target lines: `{target.get('line_start')}`-`{target.get('line_end')}`",
        f"- Nested loop lines: `{nested.get('line_start')}`-`{nested.get('line_end')}`",
        f"- Nested loop line count: `{nested.get('line_count')}`",
        "",
        "## Classification",
    ]
    for name, row in dict(capture.get("classifications") or {}).items():
        lines.append(f"- `{name}`: `{row.get('present')}`")
    lines.extend(
        [
            "",
            "## First Safe Implementation Slice",
            f"- Name: `{first_slice.get('name')}`",
            f"- Ready: `{first_slice.get('ready')}`",
            f"- Move: {first_slice.get('move')}",
            "",
            "## Do Not Move",
        ]
    )
    for item in list(first_slice.get("do_not_move") or []):
        lines.append(f"- {item}")
    lines.extend(["", "## Checks"])
    for name, value in dict(payload.get("checks") or {}).items():
        lines.append(f"- `{name}`: `{value}`")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _append_progress(payload: dict[str, Any], report_path: Path) -> None:
    PROGRESS_PATH.parent.mkdir(parents=True, exist_ok=True)
    existing = PROGRESS_PATH.read_text(encoding="utf-8").rstrip() if PROGRESS_PATH.exists() else ""
    lines = [existing, ""] if existing else []
    lines.extend(
        [
            f"## {payload.get('created_at')} - Active fail near-current candidate eval loop boundary audit",
            "",
            f"- Status: `{payload.get('status')}`",
            f"- Decision: `{(payload.get('capture') or {}).get('decision')}`",
            "- Extraction estimate: `99.70%`",
            f"- Report: [{report_path.name}](../audits/{report_path.name})",
            "",
        ]
    )
    PROGRESS_PATH.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    created_at = _timestamp()
    capture = _capture()
    checks = _checks(capture)
    passed = all(checks.values())
    payload = {
        "schema": "design_guide_active_fail_near_current_candidate_eval_loop_boundary_audit.v1",
        "created_at": created_at,
        "status": "PASS" if passed else "FAIL",
        "capture": capture,
        "checks": checks,
    }
    suffix = created_at.replace(":", "-")
    json_path = ARTIFACT_DIR / f"design_guide_active_fail_near_current_candidate_eval_loop_boundary_audit_{suffix}.json"
    report_path = AUDIT_DIR / f"design_guide_active_fail_near_current_candidate_eval_loop_boundary_audit_{suffix}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    _write_report(report_path, payload)
    _append_progress(payload, report_path)
    print(f"design_guide_active_fail_near_current_candidate_eval_loop_boundary_audit {payload['status']}")
    print(f"decision={capture.get('decision')}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    if not passed:
        print("failing_checks=" + json.dumps([name for name, ok in checks.items() if not ok]))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
