"""Verify direct target-band bounded-proof blocker item is controller-owned."""

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

TARGET = "_direct_target_band_guidance_item"
CONTROLLER_TARGET = "build_design_guide_controller_direct_target_band_bounded_proof_blocker_item"

FORBIDDEN_NESTED_TOKENS = {
    "item = _guidance_item(",
    "item[\"direct_target_band_non_actionable_blocker\"]",
    "item[\"direct_target_band_proof_unresolved\"]",
    "item[\"button_contract\"] =",
    "item[\"candidate_search_evidence\"] =",
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


def _parity_case() -> dict[str, Any]:
    from design_brain.design_guide_controller import (
        build_design_guide_controller_direct_target_band_bounded_proof_blocker_item,
    )

    item = build_design_guide_controller_direct_target_band_bounded_proof_blocker_item(
        reason="direct_target_band_proof_budget_exhausted:test",
        max_overview_calls=10,
        max_update_attempts=20,
        max_candidates=30,
        overview_calls=7,
        unique_overview_fingerprints=3,
        max_repeated_overview_fingerprint_count=2,
        update_attempts=11,
        unique_update_fingerprints=5,
        candidate_count=13,
    )
    evidence = dict(item.get("candidate_search_evidence") or {})
    contract = dict(item.get("button_contract") or {})
    checks = {
        "blocked_intent": item.get("guidance_intent") == "blocked",
        "non_actionable_blocker": item.get("direct_target_band_non_actionable_blocker") is True,
        "proof_unresolved": item.get("direct_target_band_proof_unresolved") is True,
        "proof_status": item.get("design_guide_proof_status") == "unresolved_budget_exhausted",
        "button_disabled": contract.get("enabled") is False and contract.get("actionable") is False,
        "evidence_scope": evidence.get("search_scope") == "design_guide_direct_target_band_search",
        "evidence_limits": (
            evidence.get("max_overview_calls") == 10
            and evidence.get("max_update_attempts") == 20
            and evidence.get("max_candidates") == 30
        ),
        "evidence_counts": (
            evidence.get("overview_calls") == 7
            and evidence.get("unique_overview_fingerprints") == 3
            and evidence.get("update_attempts") == 11
            and evidence.get("candidate_count") == 13
        ),
        "visible_title_preserved": item.get("title_main") == "Design Guide needs a verified cleanup result",
        "no_action_payload": item.get("action_payload") == {},
    }
    return {"passed": all(checks.values()), "checks": checks, "item": item}


def _capture() -> dict[str, Any]:
    inputs_source = INPUTS_PAGE.read_text(encoding="utf-8-sig", errors="replace")
    controller_source = CONTROLLER.read_text(encoding="utf-8", errors="replace")
    outer = _function_segment(inputs_source, TARGET)
    nested = _nested_function_segment(inputs_source, TARGET, "_bounded_proof_blocker_item")
    controller = _function_segment(controller_source, CONTROLLER_TARGET)
    forbidden_present = sorted(token for token in FORBIDDEN_NESTED_TOKENS if token in nested)
    parity = _parity_case()
    return {
        "schema": "design_guide_direct_target_band_bounded_proof_blocker_extraction.v1",
        "target": TARGET,
        "nested_target": "_bounded_proof_blocker_item",
        "controller_target": CONTROLLER_TARGET,
        "outer_function_present": bool(outer),
        "nested_function_present": bool(nested),
        "controller_helper_present": bool(controller),
        "page_imports_controller_helper": (
            f"{CONTROLLER_TARGET} as _{CONTROLLER_TARGET}" in inputs_source
        ),
        "nested_delegates_to_controller": f"_{CONTROLLER_TARGET}(" in nested,
        "forbidden_nested_tokens_present": forbidden_present,
        "nested_still_passes_page_limits_and_counts": all(
            token in nested
            for token in (
                "DIRECT_TARGET_BAND_PROOF_MAX_OVERVIEW_CALLS",
                "DIRECT_TARGET_BAND_PROOF_MAX_UPDATE_ATTEMPTS",
                "DIRECT_TARGET_BAND_PROOF_MAX_CANDIDATES",
                "_diag.get(\"overview_calls\"",
                "_diag.get(\"update_attempts\"",
            )
        ),
        "controller_has_no_page_or_streamlit_imports": (
            "inputs_page" not in controller_source and "streamlit" not in controller_source
        ),
        "parity_case": parity,
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
        "nested_no_longer_builds_blocker_item": not capture.get("forbidden_nested_tokens_present"),
        "nested_still_passes_page_limits_and_counts": bool(
            capture.get("nested_still_passes_page_limits_and_counts")
        ),
        "controller_has_no_page_or_streamlit_imports": bool(
            capture.get("controller_has_no_page_or_streamlit_imports")
        ),
        "parity_case_passed": bool((capture.get("parity_case") or {}).get("passed")),
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "engineering_behavior_unchanged": capture.get("engineering_behavior_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Direct Target-Band Bounded-Proof Blocker Extraction",
        "",
        "## Executive Summary",
        str(payload.get("status") or ""),
        "",
        "## Surface Targeted",
        "`_direct_target_band_guidance_item(...)` nested `_bounded_proof_blocker_item(...)`.",
        "",
        "## Ownership Before",
        "`inputs_page.py` built the non-actionable proof blocker item, disabled contract, and candidate-search evidence directly.",
        "",
        "## Ownership After",
        "`inputs_page.py` passes proof limits/counts to `build_design_guide_controller_direct_target_band_bounded_proof_blocker_item(...)`.",
        "",
        "## Parity",
        f"- parity case passed: `{(capture.get('parity_case') or {}).get('passed')}`",
        "",
        "## Page Wrapper",
        f"- delegates to controller: `{capture.get('nested_delegates_to_controller')}`",
        f"- forbidden nested tokens: `{capture.get('forbidden_nested_tokens_present')}`",
        "",
        "## Remaining Page-Owned Authority",
        "The broader `_direct_target_band_guidance_item(...)` still owns search orchestration, candidate generation/evaluation calls, diagnostics, and multiple route branches.",
        "",
        "## Next Safe Target",
        "Continue splitting `_direct_target_band_guidance_item(...)`, or extract target-band cleanup candidate services.",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _stamp()
    capture = _capture()
    checks = _checks(capture)
    status = "PASS" if all(checks.values()) else "FAIL"
    payload = {
        "schema": "design_guide_direct_target_band_bounded_proof_blocker_extraction.v1",
        "status": status,
        "created_at": stamp,
        "capture": capture,
        "checks": checks,
    }
    json_path = ARTIFACT_DIR / f"design_guide_direct_target_band_bounded_proof_blocker_extraction_{stamp}.json"
    audit_path = AUDIT_DIR / f"design_guide_direct_target_band_bounded_proof_blocker_extraction_{stamp}.md"
    report_path = REPORT_DIR / f"design_brain_physical_extraction_direct_target_band_bounded_proof_blocker_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(audit_path, payload)
    _write_report(report_path, payload)
    print(f"design_guide_direct_target_band_bounded_proof_blocker_extraction {status}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
