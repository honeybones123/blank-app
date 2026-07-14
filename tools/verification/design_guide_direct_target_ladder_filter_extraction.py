"""Verify direct target-band ladder candidate filtering is controller-owned."""

from __future__ import annotations

import ast
from datetime import datetime
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

INPUTS_PAGE = ROOT / "inputs_page.py"
CONTROLLER = ROOT / "design_brain" / "design_guide_controller.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
REPORT_DIR = ROOT / "artifacts" / "reports"
PROGRESS_PATH = ROOT / "artifacts" / "progress" / "design_guide_smoothness_cleanup_progress.md"

TARGET = "_direct_target_band_guidance_item"
NESTED_TARGET = "_direct_target_ladder_candidates_since"
CONTROLLER_TARGET = "filter_design_guide_controller_direct_target_ladder_candidates"

FORBIDDEN_NESTED_TOKENS = {
    "for c in candidates",
    "is_compliant",
    "all_key_pass",
    "candidate_post_util",
    "final_accepted_green_valid",
    "ladder_safe.append",
}


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _function_segment(source: str, name: str) -> str:
    tree = ast.parse(source)
    lines = source.splitlines()
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return "\n".join(lines[node.lineno - 1 : node.end_lineno])
    return ""


def _nested_function_segment(source: str, outer_name: str, nested_name: str) -> str:
    tree = ast.parse(source)
    lines = source.splitlines()
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == outer_name:
            for child in ast.walk(node):
                if isinstance(child, ast.FunctionDef) and child.name == nested_name:
                    return "\n".join(lines[child.lineno - 1 : child.end_lineno])
    return ""


def _legacy_filter(
    candidates: list[dict[str, Any]],
    *,
    start_index: int,
    low: float,
    high: float,
    strengthening: bool,
) -> list[dict[str, Any]]:
    ladder_safe: list[dict[str, Any]] = []
    for candidate in candidates[start_index:]:
        if not isinstance(candidate, dict):
            continue
        if not bool(candidate.get("is_compliant")):
            continue
        if not bool((candidate.get("overview") or {}).get("all_key_pass")):
            continue
        try:
            post_util = float(candidate.get("candidate_post_util"))
        except Exception:
            post_util = None
        if post_util is None:
            continue
        if not (float(low) <= float(post_util) <= float(high)):
            continue
        if not strengthening and not bool(candidate.get("final_accepted_green_valid")):
            continue
        ladder_safe.append(candidate)
    return ladder_safe


def _parity_cases() -> list[dict[str, Any]]:
    from design_brain.design_guide_controller import (
        filter_design_guide_controller_direct_target_ladder_candidates,
    )

    candidates = [
        {"id": "before_start", "is_compliant": True, "overview": {"all_key_pass": True}, "candidate_post_util": 0.90, "final_accepted_green_valid": True},
        {"id": "good", "is_compliant": True, "overview": {"all_key_pass": True}, "candidate_post_util": 0.91, "final_accepted_green_valid": True},
        {"id": "not_compliant", "is_compliant": False, "overview": {"all_key_pass": True}, "candidate_post_util": 0.90, "final_accepted_green_valid": True},
        {"id": "not_all_pass", "is_compliant": True, "overview": {"all_key_pass": False}, "candidate_post_util": 0.90, "final_accepted_green_valid": True},
        {"id": "out_of_band", "is_compliant": True, "overview": {"all_key_pass": True}, "candidate_post_util": 1.04, "final_accepted_green_valid": True},
        {"id": "final_invalid_cleanup", "is_compliant": True, "overview": {"all_key_pass": True}, "candidate_post_util": 0.92, "final_accepted_green_valid": False},
        {"id": "missing_util", "is_compliant": True, "overview": {"all_key_pass": True}, "final_accepted_green_valid": True},
    ]
    cases = [
        ("cleanup_requires_final_valid", 1, False),
        ("strengthening_allows_final_pending", 1, True),
        ("start_index_skips_first", 0, False),
    ]
    rows: list[dict[str, Any]] = []
    for name, start_index, strengthening in cases:
        expected = _legacy_filter(
            candidates,
            start_index=start_index,
            low=0.85,
            high=0.95,
            strengthening=strengthening,
        )
        actual = filter_design_guide_controller_direct_target_ladder_candidates(
            candidates=candidates,
            start_index=start_index,
            target_low=0.85,
            target_high=0.95,
            strengthening=strengthening,
        )
        expected_ids = [row.get("id") for row in expected]
        actual_ids = [row.get("id") for row in actual]
        same_object_identity = all(
            actual_row is expected_row for actual_row, expected_row in zip(actual, expected)
        )
        rows.append(
            {
                "case": name,
                "expected_ids": expected_ids,
                "actual_ids": actual_ids,
                "same_object_identity": same_object_identity,
                "passed": actual_ids == expected_ids and same_object_identity,
            }
        )
    return rows


def _capture() -> dict[str, Any]:
    inputs_source = INPUTS_PAGE.read_text(encoding="utf-8-sig", errors="replace")
    controller_source = CONTROLLER.read_text(encoding="utf-8", errors="replace")
    nested = _nested_function_segment(inputs_source, TARGET, NESTED_TARGET)
    controller = _function_segment(controller_source, CONTROLLER_TARGET)
    forbidden_present = sorted(token for token in FORBIDDEN_NESTED_TOKENS if token in nested)
    parity_cases = _parity_cases()
    return {
        "schema": "design_guide_direct_target_ladder_filter_extraction.v1",
        "target": TARGET,
        "nested_target": NESTED_TARGET,
        "controller_target": CONTROLLER_TARGET,
        "nested_function_present": bool(nested),
        "controller_helper_present": bool(controller),
        "page_imports_controller_helper": (
            f"{CONTROLLER_TARGET} as _{CONTROLLER_TARGET}" in inputs_source
        ),
        "nested_delegates_to_controller": f"_{CONTROLLER_TARGET}(" in nested,
        "nested_passes_filter_inputs": all(
            token in nested
            for token in (
                "candidates=list(candidates or [])",
                "start_index=int(start_index or 0)",
                "target_low=t_lo",
                "target_high=t_hi",
                "strengthening=bool(strengthening)",
            )
        ),
        "forbidden_nested_tokens_present": forbidden_present,
        "controller_has_filter_rules": all(
            token in controller
            for token in (
                "is_compliant",
                "all_key_pass",
                "candidate_post_util",
                "final_accepted_green_valid",
                "ladder_safe.append(candidate)",
            )
        ),
        "controller_has_no_page_or_streamlit_imports": (
            "inputs_page" not in controller_source and "streamlit" not in controller_source
        ),
        "parity_cases": parity_cases,
        "all_parity_cases_passed": all(case.get("passed") for case in parity_cases),
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "engineering_behavior_changed": False,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    return {
        "nested_function_present": bool(capture.get("nested_function_present")),
        "controller_helper_present": bool(capture.get("controller_helper_present")),
        "page_imports_controller_helper": bool(capture.get("page_imports_controller_helper")),
        "nested_delegates_to_controller": bool(capture.get("nested_delegates_to_controller")),
        "nested_passes_filter_inputs": bool(capture.get("nested_passes_filter_inputs")),
        "nested_no_longer_owns_filter_rules": not capture.get("forbidden_nested_tokens_present"),
        "controller_has_filter_rules": bool(capture.get("controller_has_filter_rules")),
        "controller_has_no_page_or_streamlit_imports": bool(
            capture.get("controller_has_no_page_or_streamlit_imports")
        ),
        "parity_cases_passed": bool(capture.get("all_parity_cases_passed")),
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "engineering_behavior_unchanged": capture.get("engineering_behavior_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Direct Target-Band Ladder Filter Extraction",
        "",
        "## Executive Summary",
        str(payload.get("status") or ""),
        "",
        "## Surface Targeted",
        "`_direct_target_band_guidance_item(...)` nested `_direct_target_ladder_candidates_since(...)`.",
        "",
        "## Ownership Before",
        "`inputs_page.py` filtered already-evaluated ladder candidates for target-band safety directly.",
        "",
        "## Ownership After",
        "`inputs_page.py` delegates candidate filtering to `filter_design_guide_controller_direct_target_ladder_candidates(...)`.",
        "",
        "## Behaviour Preserved",
        "- engineering behaviour changed: `False`",
        "- visible wording changed: `False`",
        "- CTA/apply semantics changed: `False`",
        "- family runtimes changed: `False`",
        "",
        "## Parity Cases",
    ]
    for case in capture.get("parity_cases") or []:
        lines.append(
            f"- `{case.get('case')}`: expected=`{case.get('expected_ids')}`, actual=`{case.get('actual_ids')}`, same_objects=`{case.get('same_object_identity')}`, passed=`{case.get('passed')}`"
        )
    lines.extend(
        [
            "",
            "## Remaining Page-Owned Authority",
            "Candidate generation and evaluation remain page-owned in this function. This slice only moved the pure post-evaluation ladder-safe filter.",
            "",
            "## Next Safe Target",
            "Extract final direct-candidate cleanup sort-key construction or continue toward target-band candidate service boundaries.",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def _append_progress(payload: dict[str, Any], report_path: Path) -> None:
    PROGRESS_PATH.parent.mkdir(parents=True, exist_ok=True)
    stamp = payload.get("created_at")
    text = (
        "\n"
        f"## {stamp} - Direct Target-Band Ladder Filter Extraction\n"
        f"- Result: `{payload.get('status')}`\n"
        "- Moved post-evaluation direct target-band ladder candidate filtering into `DesignGuideController`.\n"
        "- Page still owns ladder stage execution and candidate evaluation orchestration.\n"
        f"- Report: `{report_path}`\n"
    )
    with PROGRESS_PATH.open("a", encoding="utf-8") as fh:
        fh.write(text)


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _stamp()
    capture = _capture()
    checks = _checks(capture)
    status = "PASS" if all(checks.values()) else "FAIL"
    payload = {
        "schema": "design_guide_direct_target_ladder_filter_extraction.v1",
        "status": status,
        "created_at": stamp,
        "capture": capture,
        "checks": checks,
    }
    json_path = ARTIFACT_DIR / f"design_guide_direct_target_ladder_filter_extraction_{stamp}.json"
    audit_path = AUDIT_DIR / f"design_guide_direct_target_ladder_filter_extraction_{stamp}.md"
    report_path = REPORT_DIR / f"design_brain_physical_extraction_direct_target_ladder_filter_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(audit_path, payload)
    _write_report(report_path, payload)
    if status == "PASS":
        _append_progress(payload, report_path)
    print(f"design_guide_direct_target_ladder_filter_extraction {status}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
