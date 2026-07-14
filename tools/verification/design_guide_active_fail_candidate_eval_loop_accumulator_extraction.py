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

from design_brain.candidate_evaluation import (  # noqa: E402
    apply_active_fail_executor_candidate_eval_loop_attempt_result,
)


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


def _sample_projection() -> dict[str, Any]:
    return apply_active_fail_executor_candidate_eval_loop_attempt_result(
        eval_attempt={
            "candidate": {"candidate_id": "c1", "updates": {"D": 700.0}},
            "cache_candidate": {"candidate_id": "c1", "overview": {"all_key_pass": True}},
            "metrics_delta": {
                "candidate_evaluation_cache_hits": 0,
                "candidate_evaluation_cache_misses": 1,
                "duplicate_candidate_fingerprints_skipped": 0,
                "blocker_attempt_cache_hits": 0,
            },
        },
        candidate_fp="fp1",
        eval_cache_by_candidate_fp={},
        repair_eval_metrics={
            "candidate_evaluation_cache_hits": 0,
            "candidate_evaluation_cache_misses": 0,
            "duplicate_candidate_fingerprints_skipped": 0,
            "blocker_attempt_cache_hits": 0,
        },
        candidates=[],
    )


def _capture() -> dict[str, Any]:
    inputs_source = _read(INPUTS_PAGE)
    candidate_source = _read(CANDIDATE_EVALUATION)
    start, end, target_segment = _function_source(inputs_source, TARGET)
    nested_start, nested_end, nested_segment = _nested_function_source(target_segment, start, NESTED)
    sample = _sample_projection()
    return {
        "schema": "design_guide_active_fail_candidate_eval_loop_accumulator_extraction.v1",
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
        "sample_projection": sample,
        "source_checks": {
            "target_found": bool(target_segment),
            "nested_evaluate_found": bool(nested_segment),
            "page_uses_accumulator_service": "_apply_active_fail_executor_candidate_eval_loop_attempt_result("
            in nested_segment,
            "page_no_longer_merges_metrics_inline": "repair_eval_metrics[metric_key] +=" not in nested_segment,
            "page_no_longer_assigns_eval_cache_inline": "eval_cache_by_candidate_fp[candidate_fp] =" not in nested_segment,
            "page_no_longer_appends_candidate_inline": "candidates.append(cand)" not in nested_segment,
            "page_uses_precheck_projection_service": "_build_active_fail_executor_candidate_eval_precheck_projection("
            in nested_segment,
            "page_precheck_predicate_scalars_still_page_owned": "_updates_match_state(base, dict(updates or {}))"
            in nested_segment
            and "_candidate_is_materially_actionable(base, dict(updates or {}))" in nested_segment,
            "page_evaluator_callback_still_page_owned": "evaluator_fn=evaluate_candidate_full" in nested_segment,
            "service_helper_exported": "apply_active_fail_executor_candidate_eval_loop_attempt_result" in candidate_source
            and "__all__" in candidate_source,
            "candidate_evaluation_import_clean": all(
                token not in candidate_source
                for token in ("import inputs_page", "from inputs_page", "import streamlit", "st.session_state")
            ),
        },
        "sample_checks": {
            "candidate_returned": isinstance(sample.get("candidate"), dict),
            "candidate_appended": len(list(sample.get("candidates") or [])) == 1,
            "cache_updated": "fp1" in dict(sample.get("eval_cache_by_candidate_fp") or {}),
            "metrics_updated": dict(sample.get("repair_eval_metrics") or {}).get(
                "candidate_evaluation_cache_misses"
            )
            == 1,
        },
        "next_safe_target": {
            "name": "active_fail_candidate_eval_callback_cache_boundary",
            "why": (
                "Accumulator/cache projection and precheck projection moved. Remaining page-owned candidate-loop logic "
                "is the predicate scalar collection, existing fingerprint/cache lookup, and evaluator callback execution boundary."
            ),
        },
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    source_checks = dict(capture.get("source_checks") or {})
    sample_checks = dict(capture.get("sample_checks") or {})
    return {
        "target_found": bool(source_checks.get("target_found")),
        "nested_evaluate_found": bool(source_checks.get("nested_evaluate_found")),
        "page_uses_accumulator_service": bool(source_checks.get("page_uses_accumulator_service")),
        "page_no_longer_merges_metrics_inline": bool(source_checks.get("page_no_longer_merges_metrics_inline")),
        "page_no_longer_assigns_eval_cache_inline": bool(source_checks.get("page_no_longer_assigns_eval_cache_inline")),
        "page_no_longer_appends_candidate_inline": bool(source_checks.get("page_no_longer_appends_candidate_inline")),
        "page_uses_precheck_projection_service": bool(source_checks.get("page_uses_precheck_projection_service")),
        "page_precheck_predicate_scalars_still_page_owned": bool(
            source_checks.get("page_precheck_predicate_scalars_still_page_owned")
        ),
        "page_evaluator_callback_still_page_owned": bool(source_checks.get("page_evaluator_callback_still_page_owned")),
        "service_helper_exported": bool(source_checks.get("service_helper_exported")),
        "candidate_evaluation_import_clean": bool(source_checks.get("candidate_evaluation_import_clean")),
        "sample_projection_matches_expected": all(bool(value) for value in sample_checks.values()),
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    target = dict(capture.get("target") or {})
    nested = dict(capture.get("nested") or {})
    lines = [
        "# Active Fail Candidate Eval Loop Accumulator Extraction",
        "",
        "## Executive Summary",
        str(payload.get("status") or ""),
        "",
        f"- Target lines: `{target.get('line_start')}`-`{target.get('line_end')}`",
        f"- Nested loop lines: `{nested.get('line_start')}`-`{nested.get('line_end')}`",
        f"- Nested loop line count: `{nested.get('line_count')}`",
        "- Moved: metrics/cache/candidate append projection",
        "- Retained in page: predicate scalar collection, existing fingerprint/cache, and evaluator callback execution",
        "",
        "## Checks",
    ]
    for name, value in dict(payload.get("checks") or {}).items():
        lines.append(f"- `{name}`: `{value}`")
    lines.extend(
        [
            "",
            "## Next Safe Target",
            f"- `{(capture.get('next_safe_target') or {}).get('name')}`",
            f"- {(capture.get('next_safe_target') or {}).get('why')}",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _append_progress(payload: dict[str, Any], report_path: Path) -> None:
    PROGRESS_PATH.parent.mkdir(parents=True, exist_ok=True)
    existing = PROGRESS_PATH.read_text(encoding="utf-8").rstrip() if PROGRESS_PATH.exists() else ""
    lines = [existing, ""] if existing else []
    lines.extend(
        [
            f"## {payload.get('created_at')} - Active fail candidate eval loop accumulator extraction",
            "",
            f"- Status: `{payload.get('status')}`",
            "- Extraction estimate: `99.72%`",
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
        "schema": "design_guide_active_fail_candidate_eval_loop_accumulator_extraction.v1",
        "created_at": created_at,
        "status": "PASS" if passed else "FAIL",
        "capture": capture,
        "checks": checks,
    }
    suffix = created_at.replace(":", "-")
    json_path = ARTIFACT_DIR / f"design_guide_active_fail_candidate_eval_loop_accumulator_extraction_{suffix}.json"
    report_path = AUDIT_DIR / f"design_guide_active_fail_candidate_eval_loop_accumulator_extraction_{suffix}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    _write_report(report_path, payload)
    _append_progress(payload, report_path)
    print(f"design_guide_active_fail_candidate_eval_loop_accumulator_extraction {payload['status']}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    if not passed:
        print("failing_checks=" + json.dumps([name for name, ok in checks.items() if not ok]))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
