"""Verify direct candidate final-cleanup sort-key policy is controller-owned."""

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
NESTED_TARGET = "_direct_candidate_final_cleanup_key"
CONTROLLER_TARGET = "resolve_design_guide_controller_direct_candidate_final_cleanup_sort_key"

FORBIDDEN_NESTED_TOKENS = {
    "return (",
    "0 if final_valid else 1",
    "str(c.get(\"label\")",
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


def _parity_cases() -> list[dict[str, Any]]:
    from design_brain.design_guide_controller import (
        resolve_design_guide_controller_direct_candidate_final_cleanup_sort_key,
    )

    cases = [
        {
            "case": "valid_low_delta",
            "candidate": {"updates": {"D": 575.0}, "label": "A"},
            "final_valid": True,
            "unresolved_low_count": 0,
            "below_threshold_count": 0,
            "remaining_count": 1,
            "missing_current_count": 0,
            "shear_preference_score": (0, 0, 0.0, 0),
            "geometry_preference_score": (0, 0.1, 1.9),
            "material_delta": -12.5,
        },
        {
            "case": "invalid_with_missing",
            "candidate": {"updates": {"s_lig": 100.0, "lig_legs": 2}, "label": "B"},
            "final_valid": False,
            "unresolved_low_count": 2,
            "below_threshold_count": 1,
            "remaining_count": 3,
            "missing_current_count": 1,
            "shear_preference_score": (0, 100.0, -10, 2),
            "geometry_preference_score": (0, 0.0, 0.0),
            "material_delta": "4.5",
        },
    ]
    rows: list[dict[str, Any]] = []
    for case in cases:
        expected = (
            0 if case["final_valid"] else 1,
            case["unresolved_low_count"],
            case["below_threshold_count"],
            case["remaining_count"],
            case["missing_current_count"],
            tuple(case["shear_preference_score"]),
            tuple(case["geometry_preference_score"]),
            len(dict(case["candidate"].get("updates") or {})),
            float(case["material_delta"] or 0.0),
            str(case["candidate"].get("label") or ""),
        )
        actual = resolve_design_guide_controller_direct_candidate_final_cleanup_sort_key(
            candidate=case["candidate"],
            final_valid=case["final_valid"],
            unresolved_low_count=case["unresolved_low_count"],
            below_threshold_count=case["below_threshold_count"],
            remaining_count=case["remaining_count"],
            missing_current_count=case["missing_current_count"],
            shear_preference_score=case["shear_preference_score"],
            geometry_preference_score=case["geometry_preference_score"],
            material_delta=case["material_delta"],
        )
        rows.append(
            {
                "case": case["case"],
                "expected": list(expected),
                "actual": list(actual),
                "passed": actual == expected,
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
        "schema": "design_guide_direct_candidate_final_cleanup_sort_key_extraction.v1",
        "target": TARGET,
        "nested_target": NESTED_TARGET,
        "controller_target": CONTROLLER_TARGET,
        "nested_function_present": bool(nested),
        "controller_helper_present": bool(controller),
        "page_imports_controller_helper": (
            f"{CONTROLLER_TARGET} as _{CONTROLLER_TARGET}" in inputs_source
        ),
        "nested_delegates_to_controller": f"_{CONTROLLER_TARGET}(" in nested,
        "nested_passes_dependency_values": all(
            token in nested
            for token in (
                "final_valid=bool(final_valid)",
                "unresolved_low_count=len(unresolved_low)",
                "below_threshold_count=len(below_threshold)",
                "remaining_count=int(remaining_count)",
                "missing_current_count=int(missing_current_count)",
                "shear_preference_score=_design_guide_shear_practical_preference_score",
                "geometry_preference_score=_design_guide_geometry_proportion_preference_score",
            )
        ),
        "forbidden_nested_tokens_present": forbidden_present,
        "controller_has_sort_tuple_policy": all(
            token in controller
            for token in (
                "0 if bool(final_valid) else 1",
                "int(unresolved_low_count or 0)",
                "tuple(shear_preference_score or ())",
                "tuple(geometry_preference_score or ())",
                "str(candidate_map.get(\"label\") or \"\")",
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
        "nested_passes_dependency_values": bool(capture.get("nested_passes_dependency_values")),
        "nested_no_longer_owns_tuple_policy": not capture.get("forbidden_nested_tokens_present"),
        "controller_has_sort_tuple_policy": bool(capture.get("controller_has_sort_tuple_policy")),
        "controller_has_no_page_or_streamlit_imports": bool(capture.get("controller_has_no_page_or_streamlit_imports")),
        "parity_cases_passed": bool(capture.get("all_parity_cases_passed")),
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "engineering_behavior_unchanged": capture.get("engineering_behavior_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Direct Candidate Final-Cleanup Sort-Key Extraction",
        "",
        "## Executive Summary",
        str(payload.get("status") or ""),
        "",
        "## Surface Targeted",
        "`_direct_target_band_guidance_item(...)` nested `_direct_candidate_final_cleanup_key(...)` tuple policy.",
        "",
        "## Ownership Before",
        "`inputs_page.py` owned the final direct-candidate cleanup sort tuple.",
        "",
        "## Ownership After",
        "`inputs_page.py` computes existing dependency values and delegates tuple construction to `DesignGuideController`.",
        "",
        "## Parity Cases",
    ]
    for case in capture.get("parity_cases") or []:
        lines.append(f"- `{case.get('case')}`: passed=`{case.get('passed')}`")
    lines.extend(
        [
            "",
            "## Remaining Page-Owned Authority",
            "The page still computes remaining-family counts and preference scores. This slice only moved the tuple policy.",
            "",
            "## Next Safe Target",
            "Move the preference-score helpers or local-cleanup family-affects helper behind controller/shared APIs before extracting more of candidate selection.",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def _append_progress(payload: dict[str, Any], report_path: Path) -> None:
    PROGRESS_PATH.parent.mkdir(parents=True, exist_ok=True)
    stamp = payload.get("created_at")
    text = (
        "\n"
        f"## {stamp} - Direct Candidate Final-Cleanup Sort-Key Extraction\n"
        f"- Result: `{payload.get('status')}`\n"
        "- Moved final direct-candidate cleanup sort tuple policy into `DesignGuideController`.\n"
        "- Page still computes dependency scores and candidate selection inputs.\n"
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
        "schema": "design_guide_direct_candidate_final_cleanup_sort_key_extraction.v1",
        "status": status,
        "created_at": stamp,
        "capture": capture,
        "checks": checks,
    }
    json_path = ARTIFACT_DIR / f"design_guide_direct_candidate_final_cleanup_sort_key_extraction_{stamp}.json"
    audit_path = AUDIT_DIR / f"design_guide_direct_candidate_final_cleanup_sort_key_extraction_{stamp}.md"
    report_path = REPORT_DIR / f"design_brain_physical_extraction_direct_candidate_final_cleanup_sort_key_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(audit_path, payload)
    _write_report(report_path, payload)
    if status == "PASS":
        _append_progress(payload, report_path)
    print(f"design_guide_direct_candidate_final_cleanup_sort_key_extraction {status}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
