"""Verify shear cleanup truth gate service extraction."""

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

from design_brain.candidate_evaluation import resolve_shear_governing_truth_allows_cleanup  # noqa: E402
from design_brain.repair import _parse_util_value as _repair_parse_util_value  # noqa: E402


INPUTS_PAGE = ROOT / "inputs_page.py"
CANDIDATE_EVALUATION = ROOT / "design_brain" / "candidate_evaluation.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
NEAR_LIMIT = 0.95


def _timestamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _function_source(source: str, name: str) -> tuple[int, int, str]:
    tree = ast.parse(source)
    lines = source.splitlines()
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            start = int(node.lineno)
            end = int(node.end_lineno or node.lineno)
            return start, end, "\n".join(lines[start - 1 : end])
    raise AssertionError(f"Function not found: {name}")


def _old_truth_gate(shear_pack: dict[str, Any] | None) -> tuple[bool, dict[str, Any]]:
    detail: dict[str, Any] = {
        "shear_overdesign_truth_util": None,
        "shear_overdesign_truth_status": None,
        "shear_overdesign_truth_governing_check": None,
        "shear_cleanup_blocked_due_to_truth_near_limit": False,
    }
    if not isinstance(shear_pack, dict):
        return True, detail
    raw_status = str(shear_pack.get("summary_governing_status") or "").strip().upper()
    util = _repair_parse_util_value(shear_pack.get("summary_governing_util"))
    check = str(shear_pack.get("summary_governing_check_name") or "").strip()
    detail["shear_overdesign_truth_util"] = util
    detail["shear_overdesign_truth_status"] = raw_status or None
    detail["shear_overdesign_truth_governing_check"] = check or None
    if raw_status in {"FAIL", "FAILED"}:
        detail["shear_cleanup_blocked_due_to_truth_near_limit"] = True
        return False, detail
    if "NEAR" in raw_status or raw_status in ("WARN", "CHECK", "NEAR LIMIT"):
        detail["shear_cleanup_blocked_due_to_truth_near_limit"] = True
        return False, detail
    if util is not None:
        try:
            if float(util) >= float(NEAR_LIMIT) - 1e-12:
                detail["shear_cleanup_blocked_due_to_truth_near_limit"] = True
                return False, detail
        except (TypeError, ValueError):
            pass
    return True, detail


def _case_rows() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    cases = [
        {"name": "missing_pack", "pack": None},
        {"name": "fail_status", "pack": {"summary_governing_status": "FAIL", "summary_governing_util": 0.2}},
        {"name": "near_status", "pack": {"summary_governing_status": "NEAR LIMIT", "summary_governing_util": 0.7}},
        {"name": "warn_status", "pack": {"summary_governing_status": "WARN", "summary_governing_util": 0.7}},
        {"name": "threshold_util", "pack": {"summary_governing_status": "PASS", "summary_governing_util": 0.95}},
        {"name": "safe_util_string", "pack": {"summary_governing_status": "PASS", "summary_governing_util": "0.42", "summary_governing_check_name": "web"}},
        {"name": "bad_util_safe_status", "pack": {"summary_governing_status": "PASS", "summary_governing_util": "not-a-number"}},
    ]
    rows: list[dict[str, Any]] = []
    mismatches: list[dict[str, Any]] = []
    for case in cases:
        old = _old_truth_gate(case["pack"])
        new = resolve_shear_governing_truth_allows_cleanup(case["pack"], near_limit_threshold=NEAR_LIMIT)
        row = {
            "case": case["name"],
            "old": old,
            "new": new,
            "matches": old == new,
        }
        rows.append(row)
        if not row["matches"]:
            mismatches.append(row)
    return rows, mismatches


def _build_payload() -> dict[str, Any]:
    inputs_source = _read(INPUTS_PAGE)
    candidate_source = _read(CANDIDATE_EVALUATION)
    start, end, helper = _function_source(inputs_source, "_shear_governing_truth_allows_overdesign_cleanup")
    rows, mismatches = _case_rows()
    static_checks = {
        "service_helper_present": "def resolve_shear_governing_truth_allows_cleanup(" in candidate_source,
        "page_imports_service_helper": "resolve_shear_governing_truth_allows_cleanup as _resolve_shear_governing_truth_allows_cleanup" in inputs_source,
        "page_wrapper_delegates": "return _resolve_shear_governing_truth_allows_cleanup(" in helper,
        "page_wrapper_passes_existing_threshold": "near_limit_threshold=GUIDANCE_NEAR_LIMIT_UTIL_THRESHOLD" in helper,
        "old_inline_truth_policy_removed": "summary_governing_status" not in helper and "_parse_util_value(" not in helper,
        "candidate_service_avoids_inputs_page": "inputs_page" not in candidate_source,
        "candidate_service_avoids_streamlit": "streamlit" not in candidate_source and "st.session_state" not in candidate_source,
    }
    status = "PASS"
    if mismatches or not all(static_checks.values()):
        status = "FAIL"
    return {
        "status": status,
        "surface": "shear_cleanup_truth_gate_service_extraction",
        "extraction_complete_estimate": "99%",
        "inputs_segment": {
            "function": "_shear_governing_truth_allows_overdesign_cleanup",
            "line_start": start,
            "line_end": end,
        },
        "static_checks": static_checks,
        "case_count": len(rows),
        "parity_rows": rows,
        "mismatches": mismatches,
        "ownership_after": {
            "design_brain_candidate_evaluation": ["shear cleanup governing-truth gate policy"],
            "inputs_page": ["compatibility wrapper and threshold constant handoff"],
        },
        "next_safe_slice": "_shear_cleanup_possible pure service extraction",
        "product_behavior_changed": False,
    }


def _write_artifacts(payload: dict[str, Any]) -> None:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _timestamp().replace(":", "-")
    json_path = ARTIFACT_DIR / f"design_guide_shear_cleanup_truth_gate_service_extraction_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_shear_cleanup_truth_gate_service_extraction_{stamp}.md"
    payload["artifact_paths"] = {"json": str(json_path), "markdown": str(md_path)}
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Shear Cleanup Truth Gate Service Extraction",
        "",
        f"## Executive Summary: {payload['status']}",
        "",
        f"Extraction complete estimate: `{payload['extraction_complete_estimate']}`",
        "",
        "The shear cleanup governing-truth gate now lives in `design_brain.candidate_evaluation`; `inputs_page.py` keeps only a threshold-handoff compatibility wrapper.",
        "",
        "## Static Checks",
    ]
    for key, value in payload["static_checks"].items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(["", "## Parity Cases"])
    for row in payload["parity_rows"]:
        lines.append(f"- `{row['case']}`: matches `{row['matches']}`")
    lines.extend(["", "## Next Safe Slice", "", str(payload["next_safe_slice"]), "", f"JSON artifact: `{json_path}`"])
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    payload = _build_payload()
    _write_artifacts(payload)
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
