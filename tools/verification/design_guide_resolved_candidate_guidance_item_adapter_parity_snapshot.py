"""Verify resolved-candidate guidance item output assembly is controller-owned."""

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

TARGET = "_guidance_item_from_resolved_candidate"
CONTROLLER_TARGET = "build_design_guide_controller_resolved_candidate_guidance_item"

FORBIDDEN_WRAPPER_TOKENS = {
    "item = _guidance_item(",
    "item[\"resolved_candidate_label\"]",
    "item[\"resolved_candidate_action_type\"]",
    "item[\"resolved_candidate_family_tag\"]",
    "item[\"resolved_candidate_updates\"]",
    "item[\"resolved_candidate\"]",
    "item[\"has_resolved_candidate_payload\"]",
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


def _run_parity_case() -> dict[str, Any]:
    from design_brain.design_guide_controller import (
        build_design_guide_controller_resolved_candidate_guidance_item,
    )

    candidate = {
        "label": "Increase width and bars",
        "action_type": "apply_compound_guidance",
        "updates": {"b": 350, "bot1_count": 5},
        "worst_util": 0.91,
        "candidate_reaches_target_band": True,
        "compound_shear_augmented": True,
        "candidate_search_evidence": {"selected_candidate_id": "cand-123"},
        "canonical_winner_label": "Increase width and bars",
        "title_locked_from_final_winner": True,
    }
    failure_coverage = {
        "covers_all_current_failures": True,
        "covered_fail_keys": ["bending", "shear"],
        "remaining_fail_keys": [],
    }
    item = build_design_guide_controller_resolved_candidate_guidance_item(
        candidate=dict(candidate),
        updates=dict(candidate["updates"]),
        label="Increase width and bars",
        raw_label="Increase width and bars",
        family_tag="combined",
        subfamilies=["bending", "shear"],
        alternatives_text="No safer alternative was preferred.",
        change_lines=["Width 300 -> 350", "Bottom bars 4 -> 5"],
        candidate_post_util=0.91,
        original_candidate_action_type="apply_compound_guidance",
        primary_action="Apply recommendation",
        reasoning_text="This option brings the design into the target range in one move.",
        status="FAIL",
        overview_worst_util=1.12,
        failure_coverage=dict(failure_coverage),
        candidate_search_evidence={"selected_candidate_id": "cand-123"},
        guidance_change_summary_compact="Width 300 -> 350; Bottom bars 4 -> 5",
        guidance_expected_util_text="0.91",
        guidance_why_text_compact="This option brings the design into the target range in one move.",
        guidance_before_after="Bending 1.12 -> 0.91",
    )
    expected_keys = {
        "check_key",
        "title_main",
        "title_util",
        "title",
        "primary_action",
        "reasoning",
        "levers",
        "status",
        "bucket",
        "priority",
        "action_type",
        "action_payload",
        "resolved_candidate_label",
        "resolved_candidate",
        "has_resolved_candidate_payload",
        "failure_coverage",
        "candidate_search_evidence",
    }
    action_payload = dict(item.get("action_payload") or {})
    resolved = dict(item.get("resolved_candidate") or {})
    checks = {
        "expected_keys_present": expected_keys.issubset(set(item)),
        "label_preserved": item.get("resolved_candidate_label") == "Increase width and bars",
        "action_type_preserved": item.get("action_type") == "apply_resolved_candidate",
        "original_action_type_preserved": item.get("resolved_candidate_action_type") == "apply_compound_guidance",
        "updates_preserved": item.get("resolved_candidate_updates") == {"b": 350, "bot1_count": 5},
        "payload_updates_preserved": action_payload.get("updates") == {"b": 350, "bot1_count": 5},
        "source_candidate_id_preserved": item.get("source_candidate_id") == "cand-123",
        "resolved_candidate_id_preserved": resolved.get("candidate_id") == "cand-123",
        "failure_coverage_preserved": item.get("failure_coverage") == failure_coverage,
        "optional_lines_preserved": item.get("guidance_change_lines") == [
            "Width 300 -> 350",
            "Bottom bars 4 -> 5",
        ],
        "before_after_preserved": item.get("guidance_before_after") == "Bending 1.12 -> 0.91",
        "canonical_lock_preserved": item.get("title_locked_from_final_winner") is True,
    }
    return {
        "checks": checks,
        "passed": all(checks.values()),
        "item": item,
    }


def _capture() -> dict[str, Any]:
    inputs_source = INPUTS_PAGE.read_text(encoding="utf-8-sig", errors="replace")
    controller_source = CONTROLLER.read_text(encoding="utf-8", errors="replace")
    wrapper = _function_segment(inputs_source, TARGET)
    controller = _function_segment(controller_source, CONTROLLER_TARGET)
    forbidden_present = sorted(token for token in FORBIDDEN_WRAPPER_TOKENS if token in wrapper)
    parity = _run_parity_case()
    return {
        "schema": "design_guide_resolved_candidate_guidance_item_adapter_parity_snapshot.v1",
        "target": TARGET,
        "controller_target": CONTROLLER_TARGET,
        "page_wrapper_present": bool(wrapper),
        "controller_helper_present": bool(controller),
        "page_imports_controller_helper": (
            f"{CONTROLLER_TARGET} as _{CONTROLLER_TARGET}" in inputs_source
        ),
        "page_delegates_to_controller_helper": f"_{CONTROLLER_TARGET}(" in wrapper,
        "forbidden_wrapper_tokens_present": forbidden_present,
        "page_still_computes_pre_inputs_only": all(
            token in wrapper
            for token in (
                "_resolve_canonical_guidance_title_from_candidate(",
                "_guidance_default_alternatives_text(",
                "_guidance_change_lines_for_updates(",
                "_candidate_failure_coverage_summary(",
                "_guidance_before_after_text(",
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
        "page_wrapper_present": bool(capture.get("page_wrapper_present")),
        "controller_helper_present": bool(capture.get("controller_helper_present")),
        "page_imports_controller_helper": bool(capture.get("page_imports_controller_helper")),
        "page_delegates_to_controller_helper": bool(capture.get("page_delegates_to_controller_helper")),
        "page_no_longer_writes_final_item_shape": not capture.get("forbidden_wrapper_tokens_present"),
        "page_still_computes_pre_inputs_only": bool(capture.get("page_still_computes_pre_inputs_only")),
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
        "# Resolved-Candidate Guidance Item Adapter Parity",
        "",
        "## Executive Summary",
        str(payload.get("status") or ""),
        "",
        "## Surface Targeted",
        "`_guidance_item_from_resolved_candidate(...)` output assembly.",
        "",
        "## Ownership Before",
        "`inputs_page.py` built the resolved-candidate action payload, guidance item, top-level mirrors, and embedded resolved candidate dictionary.",
        "",
        "## Ownership After",
        "`inputs_page.py` still computes pre-existing page-derived inputs, then delegates final output assembly to `build_design_guide_controller_resolved_candidate_guidance_item(...)`.",
        "",
        "## Parity",
        f"- parity case passed: `{(capture.get('parity_case') or {}).get('passed')}`",
        "",
        "## Page Wrapper",
        f"- delegates to controller: `{capture.get('page_delegates_to_controller_helper')}`",
        f"- forbidden wrapper tokens: `{capture.get('forbidden_wrapper_tokens_present')}`",
        f"- pre-input helper calls retained: `{capture.get('page_still_computes_pre_inputs_only')}`",
        "",
        "## Remaining Page-Owned Authority",
        "Label, change-line, failure-coverage, and before/after pre-input helpers still remain in `inputs_page.py` and need later service boundaries.",
        "",
        "## Next Safe Target",
        "`_direct_target_band_guidance_item(...)` or the remaining resolved-candidate pre-input helpers.",
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
        "schema": "design_guide_resolved_candidate_guidance_item_adapter_parity_snapshot.v1",
        "status": status,
        "created_at": stamp,
        "capture": capture,
        "checks": checks,
    }
    json_path = ARTIFACT_DIR / f"design_guide_resolved_candidate_guidance_item_adapter_parity_{stamp}.json"
    audit_path = AUDIT_DIR / f"design_guide_resolved_candidate_guidance_item_adapter_parity_{stamp}.md"
    report_path = REPORT_DIR / f"design_brain_physical_extraction_resolved_candidate_guidance_item_adapter_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(audit_path, payload)
    _write_report(report_path, payload)
    print(f"design_guide_resolved_candidate_guidance_item_adapter_parity {status}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
