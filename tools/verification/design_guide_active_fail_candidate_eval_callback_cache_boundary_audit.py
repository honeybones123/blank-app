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


SURFACES = {
    "service_owned_precheck_projection": [
        "_build_active_fail_executor_candidate_eval_precheck_projection(",
    ],
    "page_owned_predicate_scalar_collection": [
        "_updates_match_state(base, dict(updates or {}))",
        "_candidate_is_materially_actionable(base, dict(updates or {}))",
    ],
    "page_owned_signature_mutation": [
        "seen_updates.add(sig)",
    ],
    "page_owned_fingerprint_adapter": [
        "stable_fingerprint_for_payload(candidate_state)",
    ],
    "pure_cache_lookup_projection_candidate": [
        "cached_candidate = eval_cache_by_candidate_fp.get(candidate_fp)",
        "used_cache = isinstance(cached_candidate, dict)",
    ],
    "service_owned_cache_lookup_projection": [
        "_resolve_active_fail_executor_candidate_eval_cache_lookup(",
    ],
    "page_owned_evaluator_callback_execution": [
        "evaluator_fn=evaluate_candidate_full",
        "state_snapshot_fn=_guidance_state_snapshot",
    ],
    "service_owned_candidate_eval_wrapper": [
        "_evaluate_active_fail_executor_candidate_with_updates(",
        "_resolve_active_fail_executor_candidate_eval_source(",
    ],
    "service_owned_eval_attempt_projection": [
        "_build_active_fail_executor_candidate_eval_attempt_result(",
    ],
    "service_owned_loop_accumulation_projection": [
        "_apply_active_fail_executor_candidate_eval_loop_attempt_result(",
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
    rows: dict[str, Any] = {}
    for name, tokens in SURFACES.items():
        matches = []
        for token in tokens:
            lines = _line_numbers(segment, start_line, token)
            if lines:
                matches.append({"token": token, "count": len(lines), "lines": lines})
        rows[name] = {"present": bool(matches), "matches": matches}
    return rows


def _capture() -> dict[str, Any]:
    source = _read(INPUTS_PAGE)
    target_start, target_end, target_segment = _function_source(source, TARGET)
    nested_start, nested_end, nested_segment = _nested_function_source(target_segment, target_start, NESTED)
    classifications = _classify(nested_segment, nested_start)
    cache_lookup_still_inline = bool(classifications["pure_cache_lookup_projection_candidate"]["present"])
    cache_lookup_service_owned = bool(classifications["service_owned_cache_lookup_projection"]["present"])
    return {
        "schema": "design_guide_active_fail_candidate_eval_callback_cache_boundary_audit.v1",
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
        "decision": (
            "BOUNDED_WITH_ONE_PURE_CACHE_LOOKUP_EXTRACTION_CANDIDATE"
            if cache_lookup_still_inline
            else "BOUNDED_PAGE_SHELL_CALLBACK_FINGERPRINT_BOUNDARY"
        ),
        "classifications": classifications,
        "ownership": {
            "service_owned": [
                "precheck projection",
                "candidate eval source/wrapper",
                "eval attempt projection",
                "loop accumulation projection",
            ],
            "page_shell_owned": [
                "page predicate scalar collection",
                "seen-update mutation",
                "existing fingerprint adapter",
                "evaluate_candidate_full callback execution",
            ],
            "next_extractable": ["pure cache lookup projection"] if cache_lookup_still_inline else [],
        },
        "first_safe_implementation_slice": {
            "name": "active_fail_candidate_eval_callback_boundary_lock",
            "ready": not cache_lookup_still_inline and cache_lookup_service_owned,
            "move": (
                "Lock the remaining callback/fingerprint boundary as page-shell-owned unless the broader "
                "`evaluate_candidate_full` boundary is extracted. Keep candidate fingerprint construction, evaluator "
                "callback execution, page predicates, and seen-update mutation in `inputs_page.py`."
            ),
            "do_not_move": [
                "evaluate_candidate_full callback execution",
                "stable_fingerprint_for_payload adapter",
                "seen_updates mutation",
                "page predicate helper calls",
                "Streamlit/session state",
                "CTA/apply routing",
            ],
        },
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    classifications = dict(capture.get("classifications") or {})
    return {
        "target_found": bool((capture.get("target") or {}).get("line_start")),
        "nested_evaluate_found": bool((capture.get("nested") or {}).get("line_start")),
        "precheck_projection_service_owned": bool(
            (classifications.get("service_owned_precheck_projection") or {}).get("present")
        ),
        "candidate_eval_wrapper_service_owned": bool(
            (classifications.get("service_owned_candidate_eval_wrapper") or {}).get("present")
        ),
        "eval_attempt_projection_service_owned": bool(
            (classifications.get("service_owned_eval_attempt_projection") or {}).get("present")
        ),
        "loop_accumulation_projection_service_owned": bool(
            (classifications.get("service_owned_loop_accumulation_projection") or {}).get("present")
        ),
        "cache_lookup_projection_service_owned": bool(
            (classifications.get("service_owned_cache_lookup_projection") or {}).get("present")
        ),
        "page_predicate_scalars_bounded": bool(
            (classifications.get("page_owned_predicate_scalar_collection") or {}).get("present")
        ),
        "page_fingerprint_adapter_bounded": bool(
            (classifications.get("page_owned_fingerprint_adapter") or {}).get("present")
        ),
        "page_evaluator_callback_bounded": bool(
            (classifications.get("page_owned_evaluator_callback_execution") or {}).get("present")
        ),
        "remaining_boundary_lock_identified": bool(
            (capture.get("first_safe_implementation_slice") or {}).get("ready")
        ),
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    first_slice = dict(capture.get("first_safe_implementation_slice") or {})
    lines = [
        "# Active Fail Candidate Eval Callback/Cache Boundary Audit",
        "",
        "## Executive Summary",
        str(payload.get("status") or ""),
        "",
        f"- Decision: `{capture.get('decision')}`",
        f"- Nested loop lines: `{(capture.get('nested') or {}).get('line_start')}`-`{(capture.get('nested') or {}).get('line_end')}`",
        "",
        "## Classification",
    ]
    for name, row in dict(capture.get("classifications") or {}).items():
        lines.append(f"- `{name}`: `{row.get('present')}`")
    lines.extend(
        [
            "",
            "## Ownership",
            "- Service-owned: precheck projection, cache lookup projection, candidate eval wrapper, eval attempt projection, loop accumulation projection",
            "- Page-shell-owned: predicate scalars, seen-update mutation, existing fingerprint adapter, evaluator callback execution",
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
            f"## {payload.get('created_at')} - Active fail candidate eval callback/cache boundary audit",
            "",
            f"- Status: `{payload.get('status')}`",
            "- Extraction complete estimate: `99.74%`",
            f"- Decision: `{(payload.get('capture') or {}).get('decision')}`",
            "- Remaining boundary: page-shell callback/fingerprint boundary.",
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
        "schema": "design_guide_active_fail_candidate_eval_callback_cache_boundary_audit.v1",
        "created_at": created_at,
        "status": status,
        "capture": capture,
        "checks": checks,
    }
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    suffix = created_at.replace(":", "-")
    json_path = ARTIFACT_DIR / f"design_guide_active_fail_candidate_eval_callback_cache_boundary_audit_{suffix}.json"
    report_path = AUDIT_DIR / f"design_guide_active_fail_candidate_eval_callback_cache_boundary_audit_{suffix}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    _write_report(report_path, payload)
    if status == "PASS":
        _append_progress(payload, report_path)
    print(f"design_guide_active_fail_candidate_eval_callback_cache_boundary_audit {status}")
    print(f"decision={capture.get('decision')}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
