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
CANDIDATE_EVALUATION = ROOT / "design_brain" / "candidate_evaluation.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
PROGRESS_PATH = ROOT / "artifacts" / "progress" / "design_guide_smoothness_cleanup_progress.md"
TARGET = "_active_fail_near_current_repair_item"
NESTED = "_evaluate"


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


def _capture() -> dict[str, Any]:
    inputs_source = _read(INPUTS_PAGE)
    candidate_source = _read(CANDIDATE_EVALUATION)
    start, end, target_segment = _function_source(inputs_source, TARGET)
    nested_start, nested_end, nested_segment = _nested_function_source(target_segment, start, NESTED)
    return {
        "schema": "design_guide_active_fail_candidate_eval_callback_boundary_lock.v1",
        "target": {
            "name": TARGET,
            "line_start": start,
            "line_end": end,
            "line_count": max(0, end - start + 1),
        },
        "nested": {
            "name": NESTED,
            "line_start": nested_start,
            "line_end": nested_end,
            "line_count": max(0, nested_end - nested_start + 1),
        },
        "decision": "ACTIVE_FAIL_CANDIDATE_EVAL_CALLBACK_BOUNDARY_BOUNDED",
        "source_checks": {
            "target_found": bool(target_segment),
            "nested_evaluate_found": bool(nested_segment),
            "precheck_projection_service_owned": "_build_active_fail_executor_candidate_eval_precheck_projection("
            in nested_segment,
            "cache_lookup_projection_service_owned": "_resolve_active_fail_executor_candidate_eval_cache_lookup("
            in nested_segment,
            "eval_attempt_projection_service_owned": "_build_active_fail_executor_candidate_eval_attempt_result("
            in nested_segment,
            "loop_accumulation_projection_service_owned": "_apply_active_fail_executor_candidate_eval_loop_attempt_result("
            in nested_segment,
            "no_inline_signature_duplicate_policy": "sig in seen_updates" not in nested_segment
            and "tuple(sorted((str(k), str(v)) for k, v in u.items()))" not in nested_segment,
            "no_inline_cache_lookup_policy": "cached_candidate = eval_cache_by_candidate_fp.get(candidate_fp)"
            not in nested_segment
            and "used_cache = isinstance(cached_candidate, dict)" not in nested_segment,
            "no_inline_accumulator_policy": "repair_eval_metrics[metric_key] +=" not in nested_segment
            and "eval_cache_by_candidate_fp[candidate_fp] =" not in nested_segment
            and "candidates.append(cand)" not in nested_segment,
            "page_predicate_scalar_collection_bounded": "_updates_match_state(base, dict(updates or {}))"
            in nested_segment
            and "_candidate_is_materially_actionable(base, dict(updates or {}))" in nested_segment,
            "page_signature_mutation_bounded": "seen_updates.add(sig)" in nested_segment,
            "page_fingerprint_adapter_bounded": "stable_fingerprint_for_payload(candidate_state)" in nested_segment,
            "page_evaluator_callback_bounded": "evaluator_fn=evaluate_candidate_full" in nested_segment
            and "state_snapshot_fn=_guidance_state_snapshot" in nested_segment,
            "candidate_evaluation_exports_helpers": all(
                token in candidate_source
                for token in (
                    "build_active_fail_executor_candidate_eval_precheck_projection",
                    "resolve_active_fail_executor_candidate_eval_cache_lookup",
                    "build_active_fail_executor_candidate_eval_attempt_result",
                    "apply_active_fail_executor_candidate_eval_loop_attempt_result",
                )
            ),
            "candidate_evaluation_import_clean": all(
                token not in candidate_source
                for token in ("import inputs_page", "from inputs_page", "import streamlit", "st.session_state")
            ),
        },
        "remaining_page_shell_boundary": [
            "predicate scalar collection via existing page helpers",
            "seen-update mutation",
            "existing stable_fingerprint_for_payload adapter",
            "evaluate_candidate_full callback execution",
        ],
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    return {name: bool(value) for name, value in dict(capture.get("source_checks") or {}).items()}


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Active Fail Candidate Eval Callback Boundary Lock",
        "",
        "## Executive Summary",
        str(payload.get("status") or ""),
        "",
        f"- Decision: `{capture.get('decision')}`",
        "- Service-owned: precheck projection, cache lookup projection, eval attempt projection, loop accumulation projection",
        "- Page-shell-owned: predicate scalars, seen-update mutation, fingerprint adapter, evaluator callback execution",
        "",
        "## Remaining Page Shell Boundary",
    ]
    for item in list(capture.get("remaining_page_shell_boundary") or []):
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
            f"## {payload.get('created_at')} - Active fail candidate eval callback boundary lock",
            "",
            f"- Status: `{payload.get('status')}`",
            "- Extraction complete estimate: `99.76%`",
            "- Locked active-fail eval loop remaining surface as page-shell callback/fingerprint plumbing.",
            f"- Report: `{report_path}`",
        ]
    )
    PROGRESS_PATH.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def main() -> int:
    created_at = _timestamp()
    capture = _capture()
    checks = _checks(capture)
    status = "PASS" if all(checks.values()) else "FAIL"
    payload = {
        "schema": "design_guide_active_fail_candidate_eval_callback_boundary_lock.v1",
        "created_at": created_at,
        "status": status,
        "capture": capture,
        "checks": checks,
    }
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    suffix = created_at.replace(":", "-")
    json_path = ARTIFACT_DIR / f"design_guide_active_fail_candidate_eval_callback_boundary_lock_{suffix}.json"
    report_path = AUDIT_DIR / f"design_guide_active_fail_candidate_eval_callback_boundary_lock_{suffix}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    _write_report(report_path, payload)
    if status == "PASS":
        _append_progress(payload, report_path)
    print(f"design_guide_active_fail_candidate_eval_callback_boundary_lock {status}")
    print(f"decision={capture.get('decision')}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
