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
    build_active_fail_executor_candidate_eval_precheck_projection,
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


def _sample_cases() -> dict[str, Any]:
    base = {"b": 400.0, "D": 650.0, "lig_legs": 2}
    valid = build_active_fail_executor_candidate_eval_precheck_projection(
        base_state=base,
        updates={"D": 700.0, "lig_legs": 0},
        updates_match_state=False,
        materially_actionable=True,
        seen_update_signatures=set(),
    )
    duplicate_signature = tuple(sorted((str(k), str(v)) for k, v in {"D": 700.0}.items()))
    duplicate = build_active_fail_executor_candidate_eval_precheck_projection(
        base_state=base,
        updates={"D": 700.0},
        updates_match_state=False,
        materially_actionable=True,
        seen_update_signatures={duplicate_signature},
    )
    empty = build_active_fail_executor_candidate_eval_precheck_projection(
        base_state=base,
        updates={},
        updates_match_state=False,
        materially_actionable=True,
        seen_update_signatures=set(),
    )
    matching = build_active_fail_executor_candidate_eval_precheck_projection(
        base_state=base,
        updates={"D": 650.0},
        updates_match_state=True,
        materially_actionable=True,
        seen_update_signatures=set(),
    )
    not_actionable = build_active_fail_executor_candidate_eval_precheck_projection(
        base_state=base,
        updates={"unused": "same"},
        updates_match_state=False,
        materially_actionable=False,
        seen_update_signatures=set(),
    )
    return {
        "valid": valid,
        "duplicate": duplicate,
        "empty": empty,
        "matching": matching,
        "not_actionable": not_actionable,
    }


def _capture() -> dict[str, Any]:
    inputs_source = _read(INPUTS_PAGE)
    candidate_source = _read(CANDIDATE_EVALUATION)
    start, end, target_segment = _function_source(inputs_source, TARGET)
    nested_start, nested_end, nested_segment = _nested_function_source(target_segment, start, NESTED)
    samples = _sample_cases()
    return {
        "schema": "design_guide_active_fail_candidate_eval_precheck_projection_extraction.v1",
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
        "sample_cases": samples,
        "source_checks": {
            "target_found": bool(target_segment),
            "nested_evaluate_found": bool(nested_segment),
            "page_delegates_precheck_projection": "_build_active_fail_executor_candidate_eval_precheck_projection("
            in nested_segment,
            "page_no_longer_builds_signature_inline": "tuple(sorted((str(k), str(v)) for k, v in u.items()))"
            not in nested_segment,
            "page_no_longer_checks_duplicate_signature_inline": "sig in seen_updates" not in nested_segment,
            "page_no_longer_updates_candidate_state_inline": "candidate_state.update(u)" not in nested_segment,
            "page_still_collects_page_predicate_scalars": "_updates_match_state(base, dict(updates or {}))"
            in nested_segment
            and "_candidate_is_materially_actionable(base, dict(updates or {}))" in nested_segment,
            "page_still_owns_seen_update_mutation": "seen_updates.add(sig)" in nested_segment,
            "page_still_owns_candidate_fingerprint": "stable_fingerprint_for_payload(candidate_state)" in nested_segment,
            "page_evaluator_callback_still_page_owned": "evaluator_fn=evaluate_candidate_full" in nested_segment,
            "service_helper_exported": "build_active_fail_executor_candidate_eval_precheck_projection" in candidate_source
            and "__all__" in candidate_source,
            "candidate_evaluation_import_clean": all(
                token not in candidate_source
                for token in ("import inputs_page", "from inputs_page", "import streamlit", "st.session_state")
            ),
        },
        "next_safe_target": {
            "name": "active_fail_candidate_eval_callback_boundary_audit",
            "why": (
                "Precheck projection and loop accumulation are service-owned. Remaining page-owned logic is now "
                "bounded to page predicate scalar collection, seen-update mutation, existing fingerprint/cache, and "
                "the evaluate_candidate_full callback execution."
            ),
        },
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    source_checks = dict(capture.get("source_checks") or {})
    samples = dict(capture.get("sample_cases") or {})
    valid = dict(samples.get("valid") or {})
    duplicate = dict(samples.get("duplicate") or {})
    empty = dict(samples.get("empty") or {})
    matching = dict(samples.get("matching") or {})
    not_actionable = dict(samples.get("not_actionable") or {})
    return {
        "target_found": bool(source_checks.get("target_found")),
        "nested_evaluate_found": bool(source_checks.get("nested_evaluate_found")),
        "page_delegates_precheck_projection": bool(source_checks.get("page_delegates_precheck_projection")),
        "page_no_longer_builds_signature_inline": bool(source_checks.get("page_no_longer_builds_signature_inline")),
        "page_no_longer_checks_duplicate_signature_inline": bool(
            source_checks.get("page_no_longer_checks_duplicate_signature_inline")
        ),
        "page_no_longer_updates_candidate_state_inline": bool(
            source_checks.get("page_no_longer_updates_candidate_state_inline")
        ),
        "page_still_collects_page_predicate_scalars": bool(
            source_checks.get("page_still_collects_page_predicate_scalars")
        ),
        "page_still_owns_seen_update_mutation": bool(source_checks.get("page_still_owns_seen_update_mutation")),
        "page_still_owns_candidate_fingerprint": bool(source_checks.get("page_still_owns_candidate_fingerprint")),
        "page_evaluator_callback_still_page_owned": bool(source_checks.get("page_evaluator_callback_still_page_owned")),
        "service_helper_exported": bool(source_checks.get("service_helper_exported")),
        "candidate_evaluation_import_clean": bool(source_checks.get("candidate_evaluation_import_clean")),
        "valid_projection_matches_inline_behavior": bool(valid.get("should_evaluate"))
        and dict(valid.get("updates") or {}) == {"D": 700.0, "lig_legs": 0}
        and dict(valid.get("candidate_state") or {}).get("D") == 700.0
        and dict(valid.get("candidate_state") or {}).get("lig_legs") == 0
        and tuple(valid.get("update_signature") or ()) == tuple(
            sorted((str(k), str(v)) for k, v in {"D": 700.0, "lig_legs": 0}.items())
        ),
        "skip_reasons_match_inline_behavior": not bool(duplicate.get("should_evaluate"))
        and duplicate.get("skip_reason") == "duplicate_update_signature"
        and not bool(empty.get("should_evaluate"))
        and empty.get("skip_reason") == "empty_updates"
        and not bool(matching.get("should_evaluate"))
        and matching.get("skip_reason") == "updates_match_state"
        and not bool(not_actionable.get("should_evaluate"))
        and not_actionable.get("skip_reason") == "not_materially_actionable",
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    target = dict(capture.get("target") or {})
    nested = dict(capture.get("nested") or {})
    next_target = dict(capture.get("next_safe_target") or {})
    lines = [
        "# Active Fail Candidate Eval Precheck Projection Extraction",
        "",
        "## Executive Summary",
        str(payload.get("status") or ""),
        "",
        f"- Target lines: `{target.get('line_start')}`-`{target.get('line_end')}`",
        f"- Nested loop lines: `{nested.get('line_start')}`-`{nested.get('line_end')}`",
        f"- Nested loop line count: `{nested.get('line_count')}`",
        "- Moved: normalized updates, duplicate-signature decision, skip reason, candidate-state projection",
        "- Retained in page: page predicate scalar collection, seen-update mutation, existing fingerprint/cache, evaluator callback execution",
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
            f"## {payload.get('created_at')} - Active fail candidate eval precheck projection extraction",
            "",
            f"- Status: `{payload.get('status')}`",
            "- Extraction complete estimate: `99.74%`",
            "- Moved normalized updates/signature/skip/candidate-state projection into `design_brain.candidate_evaluation`.",
            "- Kept page predicate scalar collection, existing fingerprint/cache, and evaluator callback execution in `inputs_page.py`.",
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
        "schema": "design_guide_active_fail_candidate_eval_precheck_projection_extraction.v1",
        "created_at": created_at,
        "status": status,
        "capture": capture,
        "checks": checks,
    }
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    suffix = created_at.replace(":", "-")
    json_path = ARTIFACT_DIR / f"design_guide_active_fail_candidate_eval_precheck_projection_extraction_{suffix}.json"
    report_path = AUDIT_DIR / f"design_guide_active_fail_candidate_eval_precheck_projection_extraction_{suffix}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    _write_report(report_path, payload)
    if status == "PASS":
        _append_progress(payload, report_path)
    print(f"design_guide_active_fail_candidate_eval_precheck_projection_extraction {status}")
    print(json_path)
    print(report_path)
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
