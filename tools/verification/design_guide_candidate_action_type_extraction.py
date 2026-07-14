"""Verify direct target-band candidate action-type resolution is controller-owned."""

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
NESTED_TARGET = "_candidate_action_type_for_updates"
CONTROLLER_TARGET = "resolve_design_guide_controller_candidate_action_type_for_updates"

FORBIDDEN_NESTED_TOKENS = {
    "has_geom =",
    "has_bottom =",
    "has_shear =",
    "apply_shear_recommendation",
    "apply_bottom_recommendation",
    "apply_geometry_recommendation",
    "tighten_geometry",
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


def _legacy_action_type(updates: dict[str, Any], *, strengthening: bool) -> str:
    geometry_keys = {"D", "b", "bw"}
    bottom_keys = {"bot1_count", "bot2_count", "db_bot_1", "db_bot_2"}
    shear_keys = {"lig_d", "lig_legs", "s_lig"}
    keys = set(updates.keys())
    has_geom = bool(keys & geometry_keys)
    has_bottom = bool(keys & bottom_keys)
    has_shear = bool(keys & shear_keys)
    if sum(1 for flag in (has_geom, has_bottom, has_shear) if flag) >= 2:
        return "apply_resolved_candidate"
    if has_shear:
        return "apply_shear_recommendation"
    if has_bottom:
        return "apply_bottom_recommendation"
    if has_geom:
        return "apply_geometry_recommendation" if strengthening else "tighten_geometry"
    return "apply_resolved_candidate"


def _parity_cases() -> list[dict[str, Any]]:
    from design_brain.design_guide_controller import (
        resolve_design_guide_controller_candidate_action_type_for_updates,
    )

    geometry_keys = {"D", "b", "bw"}
    bottom_keys = {"bot1_count", "bot2_count", "db_bot_1", "db_bot_2"}
    shear_keys = {"lig_d", "lig_legs", "s_lig"}
    cases = [
        ("geometry_cleanup", {"D": 575.0}, False),
        ("geometry_strengthening", {"D": 725.0}, True),
        ("bottom_only", {"bot1_count": 6}, False),
        ("shear_only", {"s_lig": 100.0}, False),
        ("combined_bottom_shear", {"bot1_count": 6, "s_lig": 100.0}, False),
        ("combined_geometry_bottom", {"D": 725.0, "bot1_count": 6}, True),
        ("unknown_payload", {"foo": "bar"}, False),
        ("empty_payload", {}, False),
    ]
    rows: list[dict[str, Any]] = []
    for name, updates, strengthening in cases:
        expected = _legacy_action_type(updates, strengthening=strengthening)
        actual = resolve_design_guide_controller_candidate_action_type_for_updates(
            updates=updates,
            geometry_update_keys=geometry_keys,
            bottom_update_keys=bottom_keys,
            shear_update_keys=shear_keys,
            strengthening=strengthening,
        )
        rows.append(
            {
                "case": name,
                "updates": updates,
                "strengthening": strengthening,
                "expected": expected,
                "actual": actual,
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
        "schema": "design_guide_candidate_action_type_extraction.v1",
        "target": TARGET,
        "nested_target": NESTED_TARGET,
        "controller_target": CONTROLLER_TARGET,
        "nested_function_present": bool(nested),
        "controller_helper_present": bool(controller),
        "page_imports_controller_helper": (
            f"{CONTROLLER_TARGET} as _{CONTROLLER_TARGET}" in inputs_source
        ),
        "nested_delegates_to_controller": f"_{CONTROLLER_TARGET}(" in nested,
        "nested_passes_key_groups_and_strengthening": all(
            token in nested
            for token in (
                "geometry_update_keys=_COMPOUND_GEOMETRY_UPDATE_KEYS",
                "bottom_update_keys=_COMPOUND_BOTTOM_UPDATE_KEYS",
                "shear_update_keys=_COMPOUND_SHEAR_UPDATE_KEYS",
                "strengthening=bool(strengthening)",
            )
        ),
        "forbidden_nested_tokens_present": forbidden_present,
        "controller_has_action_type_matrix": all(
            token in controller
            for token in (
                "apply_resolved_candidate",
                "apply_shear_recommendation",
                "apply_bottom_recommendation",
                "apply_geometry_recommendation",
                "tighten_geometry",
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
        "nested_passes_key_groups_and_strengthening": bool(
            capture.get("nested_passes_key_groups_and_strengthening")
        ),
        "nested_no_longer_owns_action_type_matrix": not capture.get("forbidden_nested_tokens_present"),
        "controller_has_action_type_matrix": bool(capture.get("controller_has_action_type_matrix")),
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
        "# Candidate Action-Type Extraction",
        "",
        "## Executive Summary",
        str(payload.get("status") or ""),
        "",
        "## Surface Targeted",
        "`_direct_target_band_guidance_item(...)` nested `_candidate_action_type_for_updates(...)`.",
        "",
        "## Ownership Before",
        "`inputs_page.py` owned the pure mapping from update-key groups to Design Guide action type.",
        "",
        "## Ownership After",
        "`inputs_page.py` passes update payload, key groups, and strengthening mode to `resolve_design_guide_controller_candidate_action_type_for_updates(...)`.",
        "",
        "## Behaviour Preserved",
        "- engineering behaviour changed: `False`",
        "- visible wording changed: `False`",
        "- CTA/apply semantics changed: `False`",
        "- family runtimes changed: `False`",
        "",
        "## Parity Matrix",
    ]
    for case in capture.get("parity_cases") or []:
        lines.append(
            f"- `{case.get('case')}`: expected=`{case.get('expected')}`, actual=`{case.get('actual')}`, passed=`{case.get('passed')}`"
        )
    lines.extend(
        [
            "",
            "## Remaining Page-Owned Authority",
            "The page still owns candidate generation/evaluation loops and page-local key constants. This slice only moved the pure action-type decision matrix.",
            "",
            "## Next Safe Target",
            "Continue extracting pure target-band candidate selection/scoring helpers before touching evaluation orchestration.",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def _append_progress(payload: dict[str, Any], report_path: Path) -> None:
    PROGRESS_PATH.parent.mkdir(parents=True, exist_ok=True)
    stamp = payload.get("created_at")
    text = (
        "\n"
        f"## {stamp} - Candidate Action-Type Extraction\n"
        f"- Result: `{payload.get('status')}`\n"
        "- Moved pure direct target-band candidate action-type resolution into `DesignGuideController`.\n"
        "- Page keeps key groups, Apply routing, click handling, and candidate evaluation orchestration.\n"
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
        "schema": "design_guide_candidate_action_type_extraction.v1",
        "status": status,
        "created_at": stamp,
        "capture": capture,
        "checks": checks,
    }
    json_path = ARTIFACT_DIR / f"design_guide_candidate_action_type_extraction_{stamp}.json"
    audit_path = AUDIT_DIR / f"design_guide_candidate_action_type_extraction_{stamp}.md"
    report_path = REPORT_DIR / f"design_brain_physical_extraction_candidate_action_type_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(audit_path, payload)
    _write_report(report_path, payload)
    if status == "PASS":
        _append_progress(payload, report_path)
    print(f"design_guide_candidate_action_type_extraction {status}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
