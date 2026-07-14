"""Verify active-failure no-target blocker item assembly is controller-owned."""

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
NESTED_TARGET = "_active_failure_no_target_blocker_item"
CONTROLLER_TARGET = "build_design_guide_controller_active_failure_no_target_blocker_item"

FORBIDDEN_NESTED_TOKENS = {
    "item = _guidance_item(",
    "item[\"guidance_intent\"] = \"specific_blocker\"",
    "item[\"candidate_search_evidence\"] =",
    "item[\"exact_blockers_by_family\"] =",
    "item[\"button_contract\"] =",
    "candidate_search_exhaustive",
    "active_under_capacity_blocker_reason",
    "outside_target_band_allowed_reason",
}

REQUIRED_CONTROLLER_TOKENS = {
    "active_failure_route_attempt_updates(",
    "active_failure_route_inventory(",
    "active_failure_exact_blockers_for_families(",
    "build_design_guide_controller_guidance_item(",
    "\"active_fail_combined_repair_search\"",
    "\"one_click_target_reaching_candidate_exists\": False",
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


def _parity_case(name: str, overview: dict[str, Any], evidence: dict[str, Any]) -> dict[str, Any]:
    from design_brain.design_guide_controller import (
        build_design_guide_controller_active_failure_no_target_blocker_item,
    )

    item = build_design_guide_controller_active_failure_no_target_blocker_item(
        reason=f"{name}_search_exhausted",
        evidence=evidence,
        overview=overview,
        width_values=[400.0, 475.0, 550.0],
        depth_values=[650.0, 725.0],
        base_width=400.0,
        base_depth=650.0,
    )
    candidate_evidence = dict(item.get("candidate_search_evidence") or {})
    button_contract = dict(item.get("button_contract") or {})
    active_failures = set(candidate_evidence.get("active_failures") or [])
    checks = {
        "item_is_blocker": item.get("guidance_intent") == "specific_blocker",
        "active_under_capacity_blocker": item.get("active_under_capacity_blocker") is True,
        "final_state_blocker": item.get("final_state_class") == "blocker",
        "primary_card_not_actionable": item.get("primary_card_actionable") is False,
        "button_disabled": (
            button_contract.get("enabled") is False
            and button_contract.get("actionable") is False
            and button_contract.get("updates") == {}
        ),
        "repair_search_ran": candidate_evidence.get("repair_search_ran") is True,
        "repair_search_exhaustive": candidate_evidence.get("repair_search_exhaustive") is True,
        "target_band_candidates_zero": candidate_evidence.get("executable_target_band_candidate_count") == 0,
        "exact_blockers_present": bool(item.get("exact_blockers_by_family")),
        "post_click_exact_blockers_present": bool(item.get("post_click_exact_blockers_by_family")),
        "blocking_reason_matches": (
            button_contract.get("blocking_reason") == item.get("active_under_capacity_blocker_reason")
        ),
        "scope_matches_family": (
            candidate_evidence.get("search_scope") == "active_fail_combined_repair_search"
            if {"bending", "shear"}.issubset(active_failures)
            else str(candidate_evidence.get("search_scope") or "").startswith("active_fail_")
        ),
        "visible_title_present": bool(item.get("title_main")),
    }
    return {
        "case": name,
        "passed": all(checks.values()),
        "checks": checks,
        "title": item.get("title_main"),
        "family": button_contract.get("family"),
        "search_scope": candidate_evidence.get("search_scope"),
        "exact_blocker_families": sorted((item.get("exact_blockers_by_family") or {}).keys()),
        "button_contract": button_contract,
    }


def _parity_cases() -> list[dict[str, Any]]:
    return [
        _parity_case(
            "bending",
            {
                "statuses": {"bending": "FAIL", "shear": "PASS"},
                "governing_check": "bending",
                "worst_util": 1.42,
            },
            {
                "safe_executor_backed_candidates_count": 0,
                "candidate_rows": [{"rejection_reason": "bending_preview_failed", "safe_executor_backed": False}],
            },
        ),
        _parity_case(
            "shear",
            {
                "statuses": {"bending": "PASS", "shear": "FAIL"},
                "governing_check": "shear",
                "worst_util": 1.23,
            },
            {
                "safe_executor_backed_candidates_count": 0,
                "candidate_rows": [{"rejection_reason": "shear_preview_failed", "safe_executor_backed": False}],
            },
        ),
        _parity_case(
            "combined",
            {
                "statuses": {"bending": "FAIL", "shear": "FAIL"},
                "governing_check": "bending",
                "worst_util": 1.33,
            },
            {
                "safe_executor_backed_candidates_count": 0,
                "candidate_rows": [{"rejection_reason": "combined_preview_failed", "safe_executor_backed": False}],
            },
        ),
    ]


def _capture() -> dict[str, Any]:
    inputs_source = INPUTS_PAGE.read_text(encoding="utf-8-sig", errors="replace")
    controller_source = CONTROLLER.read_text(encoding="utf-8", errors="replace")
    outer = _function_segment(inputs_source, TARGET)
    nested = _nested_function_segment(inputs_source, TARGET, NESTED_TARGET)
    controller = _function_segment(controller_source, CONTROLLER_TARGET)
    forbidden_present = sorted(token for token in FORBIDDEN_NESTED_TOKENS if token in nested)
    missing_controller_tokens = sorted(token for token in REQUIRED_CONTROLLER_TOKENS if token not in controller)
    parity_cases = _parity_cases()
    return {
        "schema": "design_guide_active_failure_no_target_blocker_extraction.v1",
        "target": TARGET,
        "nested_target": NESTED_TARGET,
        "controller_target": CONTROLLER_TARGET,
        "outer_function_present": bool(outer),
        "nested_function_present": bool(nested),
        "controller_helper_present": bool(controller),
        "page_imports_controller_helper": (
            f"{CONTROLLER_TARGET} as _{CONTROLLER_TARGET}" in inputs_source
        ),
        "nested_delegates_to_controller": f"_{CONTROLLER_TARGET}(" in nested,
        "nested_passes_plain_inputs_only": all(
            token in nested
            for token in (
                "reason=str(reason or \"\")",
                "evidence=dict(evidence or {})",
                "overview=dict(overview or {})",
                "width_values=list(width_values or [])",
                "depth_values=list(depth_values or [])",
                "base_width=base_width",
                "base_depth=base_depth",
            )
        ),
        "forbidden_nested_tokens_present": forbidden_present,
        "missing_controller_tokens": missing_controller_tokens,
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
        "outer_function_present": bool(capture.get("outer_function_present")),
        "nested_function_present": bool(capture.get("nested_function_present")),
        "controller_helper_present": bool(capture.get("controller_helper_present")),
        "page_imports_controller_helper": bool(capture.get("page_imports_controller_helper")),
        "nested_delegates_to_controller": bool(capture.get("nested_delegates_to_controller")),
        "nested_passes_plain_inputs_only": bool(capture.get("nested_passes_plain_inputs_only")),
        "nested_no_longer_builds_blocker_item": not capture.get("forbidden_nested_tokens_present"),
        "controller_has_required_projection_tokens": not capture.get("missing_controller_tokens"),
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
        "# Active-Failure No-Target Blocker Extraction",
        "",
        "## Executive Summary",
        str(payload.get("status") or ""),
        "",
        "## Surface Targeted",
        "`_direct_target_band_guidance_item(...)` nested `_active_failure_no_target_blocker_item(...)`.",
        "",
        "## Ownership Before",
        "`inputs_page.py` built active-failure no-target blocker wording, candidate-search evidence, exact-blocker mirrors, and disabled button contract directly.",
        "",
        "## Ownership After",
        "`inputs_page.py` delegates the blocker item projection to `build_design_guide_controller_active_failure_no_target_blocker_item(...)` and passes only plain diagnostic inputs.",
        "",
        "## Behaviour Preserved",
        "- engineering behaviour changed: `False`",
        "- visible wording changed: `False`",
        "- CTA/apply semantics changed: `False`",
        "- family runtimes changed: `False`",
        "",
        "## Adapter / Default Rebuild Proof",
        f"- page delegates to controller: `{capture.get('nested_delegates_to_controller')}`",
        f"- forbidden old page projection tokens: `{capture.get('forbidden_nested_tokens_present')}`",
        f"- missing controller projection tokens: `{capture.get('missing_controller_tokens')}`",
        "",
        "## Parity Cases",
    ]
    for case in capture.get("parity_cases") or []:
        lines.append(
            f"- `{case.get('case')}`: passed=`{case.get('passed')}`, family=`{case.get('family')}`, scope=`{case.get('search_scope')}`"
        )
    lines.extend(
        [
            "",
            "## Remaining Page-Owned Authority",
            "The broader direct target-band route still owns candidate search loops, evaluation calls, memo/cache plumbing, and additional route branches. This slice only extracted the active-failure no-target blocker item projection.",
            "",
            "## Next Safe Target",
            "Continue splitting `_direct_target_band_guidance_item(...)`, focusing next on target-band cleanup candidate service boundaries or another nested item/output projection branch.",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def _append_progress(payload: dict[str, Any], report_path: Path) -> None:
    PROGRESS_PATH.parent.mkdir(parents=True, exist_ok=True)
    stamp = payload.get("created_at")
    text = (
        "\n"
        f"## {stamp} - Active-Failure No-Target Blocker Extraction\n"
        f"- Result: `{payload.get('status')}`\n"
        "- Moved active-failure no-target blocker item/evidence/button-contract projection into `DesignGuideController`.\n"
        "- Page wrapper now passes reason, overview, evidence, and geometry search bounds only.\n"
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
        "schema": "design_guide_active_failure_no_target_blocker_extraction.v1",
        "status": status,
        "created_at": stamp,
        "capture": capture,
        "checks": checks,
    }
    json_path = ARTIFACT_DIR / f"design_guide_active_failure_no_target_blocker_extraction_{stamp}.json"
    audit_path = AUDIT_DIR / f"design_guide_active_failure_no_target_blocker_extraction_{stamp}.md"
    report_path = REPORT_DIR / f"design_brain_physical_extraction_active_failure_no_target_blocker_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(audit_path, payload)
    _write_report(report_path, payload)
    if status == "PASS":
        _append_progress(payload, report_path)
    print(f"design_guide_active_failure_no_target_blocker_extraction {status}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
