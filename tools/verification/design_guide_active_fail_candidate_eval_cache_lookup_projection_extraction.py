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
    resolve_active_fail_executor_candidate_eval_cache_lookup,
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
    hit = resolve_active_fail_executor_candidate_eval_cache_lookup(
        candidate_fp="fp1",
        eval_cache_by_candidate_fp={"fp1": {"candidate_id": "c1", "updates": {"D": 700.0}}},
    )
    miss = resolve_active_fail_executor_candidate_eval_cache_lookup(
        candidate_fp="fp2",
        eval_cache_by_candidate_fp={"fp1": {"candidate_id": "c1"}},
    )
    missing_fp = resolve_active_fail_executor_candidate_eval_cache_lookup(
        candidate_fp=None,
        eval_cache_by_candidate_fp={"fp1": {"candidate_id": "c1"}},
    )
    return {"hit": hit, "miss": miss, "missing_fp": missing_fp}


def _capture() -> dict[str, Any]:
    inputs_source = _read(INPUTS_PAGE)
    candidate_source = _read(CANDIDATE_EVALUATION)
    start, end, target_segment = _function_source(inputs_source, TARGET)
    nested_start, nested_end, nested_segment = _nested_function_source(target_segment, start, NESTED)
    sample = _sample_projection()
    return {
        "schema": "design_guide_active_fail_candidate_eval_cache_lookup_projection_extraction.v1",
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
            "page_uses_cache_lookup_service": "_resolve_active_fail_executor_candidate_eval_cache_lookup("
            in nested_segment,
            "page_no_longer_gets_eval_cache_inline": "cached_candidate = eval_cache_by_candidate_fp.get(candidate_fp)"
            not in nested_segment,
            "page_no_longer_resolves_used_cache_inline": "used_cache = isinstance(cached_candidate, dict)"
            not in nested_segment,
            "page_still_owns_candidate_fingerprint": "stable_fingerprint_for_payload(candidate_state)" in nested_segment,
            "page_evaluator_callback_still_page_owned": "evaluator_fn=evaluate_candidate_full" in nested_segment,
            "page_still_uses_loop_accumulator_service": "_apply_active_fail_executor_candidate_eval_loop_attempt_result("
            in nested_segment,
            "service_helper_exported": "resolve_active_fail_executor_candidate_eval_cache_lookup" in candidate_source
            and "__all__" in candidate_source,
            "candidate_evaluation_import_clean": all(
                token not in candidate_source
                for token in ("import inputs_page", "from inputs_page", "import streamlit", "st.session_state")
            ),
        },
        "next_safe_target": {
            "name": "active_fail_candidate_eval_callback_boundary_lock",
            "why": (
                "Precheck projection, cache lookup, eval attempt, and loop accumulation are service-owned. Remaining "
                "candidate-loop lines are page-shell predicate scalar collection, existing fingerprint adapter, "
                "seen-update mutation, and evaluator callback execution."
            ),
        },
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    source_checks = dict(capture.get("source_checks") or {})
    sample = dict(capture.get("sample_projection") or {})
    hit = dict(sample.get("hit") or {})
    miss = dict(sample.get("miss") or {})
    missing_fp = dict(sample.get("missing_fp") or {})
    return {
        "target_found": bool(source_checks.get("target_found")),
        "nested_evaluate_found": bool(source_checks.get("nested_evaluate_found")),
        "page_uses_cache_lookup_service": bool(source_checks.get("page_uses_cache_lookup_service")),
        "page_no_longer_gets_eval_cache_inline": bool(source_checks.get("page_no_longer_gets_eval_cache_inline")),
        "page_no_longer_resolves_used_cache_inline": bool(source_checks.get("page_no_longer_resolves_used_cache_inline")),
        "page_still_owns_candidate_fingerprint": bool(source_checks.get("page_still_owns_candidate_fingerprint")),
        "page_evaluator_callback_still_page_owned": bool(source_checks.get("page_evaluator_callback_still_page_owned")),
        "page_still_uses_loop_accumulator_service": bool(source_checks.get("page_still_uses_loop_accumulator_service")),
        "service_helper_exported": bool(source_checks.get("service_helper_exported")),
        "candidate_evaluation_import_clean": bool(source_checks.get("candidate_evaluation_import_clean")),
        "sample_hit_matches_inline_behavior": bool(hit.get("used_cache"))
        and dict(hit.get("cached_candidate") or {}).get("candidate_id") == "c1",
        "sample_miss_matches_inline_behavior": not bool(miss.get("used_cache"))
        and miss.get("cached_candidate") is None
        and not bool(missing_fp.get("used_cache"))
        and missing_fp.get("cached_candidate") is None,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    target = dict(capture.get("target") or {})
    nested = dict(capture.get("nested") or {})
    next_target = dict(capture.get("next_safe_target") or {})
    lines = [
        "# Active Fail Candidate Eval Cache Lookup Projection Extraction",
        "",
        "## Executive Summary",
        str(payload.get("status") or ""),
        "",
        f"- Target lines: `{target.get('line_start')}`-`{target.get('line_end')}`",
        f"- Nested loop lines: `{nested.get('line_start')}`-`{nested.get('line_end')}`",
        f"- Nested loop line count: `{nested.get('line_count')}`",
        "- Moved: pure cache hit/miss lookup projection",
        "- Retained in page: candidate fingerprint adapter, evaluator callback execution, cache storage through accumulator projection",
        "",
        "## Checks",
    ]
    for name, value in dict(payload.get("checks") or {}).items():
        lines.append(f"- `{name}`: `{value}`")
    lines.extend(
        [
            "",
            "## Next Safe Target",
            f"- `{next_target.get('name')}`",
            f"- {next_target.get('why')}",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _append_progress(payload: dict[str, Any], report_path: Path) -> None:
    PROGRESS_PATH.parent.mkdir(parents=True, exist_ok=True)
    existing = PROGRESS_PATH.read_text(encoding="utf-8").rstrip() if PROGRESS_PATH.exists() else ""
    lines = [existing, ""] if existing else []
    lines.extend(
        [
            f"## {payload.get('created_at')} - Active fail candidate eval cache lookup projection extraction",
            "",
            f"- Status: `{payload.get('status')}`",
            "- Extraction complete estimate: `99.75%`",
            "- Moved pure cache hit/miss lookup projection into `design_brain.candidate_evaluation`.",
            "- Kept candidate fingerprint, evaluator callback execution, and page/session concerns in `inputs_page.py`.",
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
        "schema": "design_guide_active_fail_candidate_eval_cache_lookup_projection_extraction.v1",
        "created_at": created_at,
        "status": status,
        "capture": capture,
        "checks": checks,
    }
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    suffix = created_at.replace(":", "-")
    json_path = ARTIFACT_DIR / f"design_guide_active_fail_candidate_eval_cache_lookup_projection_extraction_{suffix}.json"
    report_path = AUDIT_DIR / f"design_guide_active_fail_candidate_eval_cache_lookup_projection_extraction_{suffix}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    _write_report(report_path, payload)
    if status == "PASS":
        _append_progress(payload, report_path)
    print(f"design_guide_active_fail_candidate_eval_cache_lookup_projection_extraction {status}")
    print(json_path)
    print(report_path)
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
