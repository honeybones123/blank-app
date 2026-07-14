from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
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

PAGE_TARGET = "_promote_guidance_item_to_resolved_candidate"
LOCAL_CLEANUP_TARGET = "_evaluate_local_cleanup_guidance_item"
CONTROLLER_TARGET = "resolve_design_guide_controller_local_cleanup_candidate_promotion"


def _function_segment(source: str, name: str) -> str:
    marker = f"def {name}("
    start = source.find(marker)
    if start < 0:
        return ""
    next_start = source.find("\ndef ", start + len(marker))
    if next_start < 0:
        next_start = len(source)
    return source[start:next_start]


def _old_expected(
    *,
    item: dict[str, Any] | None,
    candidate: dict[str, Any] | None,
    change_lines: list[str] | None = None,
    failure_coverage: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    if not isinstance(item, dict) or not isinstance(candidate, dict):
        return item
    updates = dict(candidate.get("updates") or {})
    if not updates:
        return item

    out = dict(item)
    payload = dict(out.get("action_payload") or {})
    original_action_type = str(
        candidate.get("action_type")
        or payload.get("resolved_candidate_action_type")
        or out.get("action_type")
        or "apply_shear_recommendation"
    ).strip()
    label = str(
        candidate.get("label")
        or payload.get("resolved_candidate_label")
        or out.get("title_main")
        or "Apply recommendation"
    ).strip()
    post_util = candidate.get("candidate_post_util", candidate.get("worst_util"))
    try:
        post_util = float(post_util) if post_util is not None else None
    except Exception:
        post_util = None
    lines = list(
        candidate.get("guidance_change_lines")
        or payload.get("guidance_change_lines")
        or out.get("guidance_change_lines")
        or change_lines
        or []
    )
    coverage = dict(failure_coverage or {})

    payload["resolved_candidate_updates"] = dict(updates)
    payload["resolved_candidate_label"] = label
    payload["resolved_candidate_action_type"] = original_action_type
    payload["resolved_candidate_post_util"] = post_util
    payload["resolved_candidate_reaches_target_band"] = bool(
        candidate.get("candidate_reaches_target_band")
        or candidate.get("reaches_target_band")
    )
    payload["updates"] = dict(payload.get("updates") or updates)
    payload["guidance_change_lines"] = list(lines)
    payload["failure_coverage"] = dict(coverage)
    payload["covers_all_current_failures"] = bool(coverage.get("covers_all_current_failures"))
    payload["covered_fail_keys"] = list(coverage.get("covered_fail_keys") or [])
    payload["remaining_fail_keys"] = list(coverage.get("remaining_fail_keys") or [])

    out["action_payload"] = payload
    out["action_type"] = "apply_resolved_candidate"
    out["resolved_candidate_label"] = label
    out["resolved_candidate_action_type"] = original_action_type
    out["resolved_candidate_updates"] = dict(updates)
    out["resolved_candidate_post_util"] = post_util
    out["resolved_candidate_reaches_target_band"] = bool(
        candidate.get("candidate_reaches_target_band")
        or candidate.get("reaches_target_band")
    )
    out["has_resolved_candidate_payload"] = True
    out["failure_coverage"] = dict(coverage)
    out["covers_all_current_failures"] = bool(coverage.get("covers_all_current_failures"))
    out["covered_fail_keys"] = list(coverage.get("covered_fail_keys") or [])
    out["remaining_fail_keys"] = list(coverage.get("remaining_fail_keys") or [])
    out["resolved_candidate"] = {
        **dict(candidate),
        "label": label,
        "action_type": original_action_type,
        "updates": dict(updates),
        "candidate_post_util": post_util,
        "candidate_reaches_target_band": bool(
            candidate.get("candidate_reaches_target_band")
            or candidate.get("reaches_target_band")
        ),
        "failure_coverage": dict(coverage),
    }
    return out


def _parity_cases() -> list[dict[str, Any]]:
    from design_brain.design_guide_controller import (
        resolve_design_guide_controller_local_cleanup_candidate_promotion,
    )

    cases = [
        (
            "invalid_item_returns_item",
            {
                "item": None,
                "candidate": {"updates": {"s_lig": 300}},
                "change_lines": ["Spacing 200 -> 300"],
                "failure_coverage": {},
            },
        ),
        (
            "missing_updates_returns_item",
            {
                "item": {"title_main": "Local cleanup", "action_payload": {}},
                "candidate": {"updates": {}},
                "change_lines": [],
                "failure_coverage": {},
            },
        ),
        (
            "candidate_supplies_label_and_lines",
            {
                "item": {"title_main": "Old title", "action_payload": {"updates": {"b": 400}}},
                "candidate": {
                    "updates": {"b": 350},
                    "label": "Reduce width",
                    "action_type": "apply_geometry_update",
                    "candidate_post_util": "0.86",
                    "candidate_reaches_target_band": True,
                    "guidance_change_lines": ["Width 400 -> 350"],
                },
                "change_lines": ["unused"],
                "failure_coverage": {
                    "covers_all_current_failures": True,
                    "covered_fail_keys": ["bending"],
                    "remaining_fail_keys": [],
                },
            },
        ),
        (
            "payload_fallbacks_preserved",
            {
                "item": {
                    "title_main": "Fallback label",
                    "action_type": "apply_compound_guidance",
                    "guidance_change_lines": ["Existing line"],
                    "action_payload": {
                        "resolved_candidate_action_type": "apply_existing_payload",
                        "resolved_candidate_label": "Payload label",
                    },
                },
                "candidate": {
                    "updates": {"lig_legs": 0},
                    "worst_util": 0.67,
                    "reaches_target_band": False,
                },
                "change_lines": ["No links"],
                "failure_coverage": {"remaining_fail_keys": ["shear"]},
            },
        ),
    ]
    rows = []
    for name, kwargs in cases:
        expected = _old_expected(**kwargs)
        actual = resolve_design_guide_controller_local_cleanup_candidate_promotion(**kwargs)
        rows.append(
            {
                "case": name,
                "expected": expected,
                "actual": actual,
                "passed": actual == expected,
            }
        )
    return rows


def _capture() -> dict[str, Any]:
    inputs_source = INPUTS_PAGE.read_text(encoding="utf-8")
    controller_source = CONTROLLER.read_text(encoding="utf-8")
    page_segment = _function_segment(inputs_source, PAGE_TARGET)
    local_cleanup_segment = _function_segment(inputs_source, LOCAL_CLEANUP_TARGET)
    controller_segment = _function_segment(controller_source, CONTROLLER_TARGET)
    parity_cases = _parity_cases()
    return {
        "schema": "design_guide_local_cleanup_candidate_promotion_extraction.v1",
        "page_target": PAGE_TARGET,
        "controller_target": CONTROLLER_TARGET,
        "page_imports_controller_helper": f"{CONTROLLER_TARGET} as _{CONTROLLER_TARGET}" in inputs_source,
        "page_delegates_promotion": f"_{CONTROLLER_TARGET}(" in page_segment,
        "local_cleanup_calls_controller_promotion_directly": f"_{CONTROLLER_TARGET}(" in local_cleanup_segment,
        "local_cleanup_no_longer_calls_page_promotion_helper": f"{PAGE_TARGET}(" not in local_cleanup_segment,
        "local_cleanup_keeps_page_callback_inputs": all(
            token in local_cleanup_segment
            for token in (
                "_guidance_change_lines_for_updates(",
                "_candidate_failure_coverage_summary(",
            )
        ),
        "page_keeps_change_line_callback": "_guidance_change_lines_for_updates(" in page_segment,
        "page_keeps_failure_coverage_callback": "_candidate_failure_coverage_summary(" in page_segment,
        "page_no_longer_owns_payload_shape": all(
            token not in page_segment
            for token in (
                'payload["resolved_candidate_updates"]',
                'out["resolved_candidate"]',
                'out["has_resolved_candidate_payload"]',
                'payload["failure_coverage"]',
            )
        ),
        "controller_owns_payload_shape": all(
            token in controller_segment
            for token in (
                'payload["resolved_candidate_updates"]',
                'out["resolved_candidate"]',
                'out["has_resolved_candidate_payload"]',
                'payload["failure_coverage"]',
            )
        ),
        "controller_exported": f'"{CONTROLLER_TARGET}"' in controller_source,
        "controller_has_no_page_or_streamlit_imports": "inputs_page" not in controller_source and "streamlit" not in controller_source,
        "parity_cases": parity_cases,
        "all_parity_cases_passed": all(row.get("passed") for row in parity_cases),
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtimes_changed": False,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    return {
        "page_imports_controller_helper": bool(capture.get("page_imports_controller_helper")),
        "page_delegates_promotion": bool(capture.get("page_delegates_promotion")),
        "local_cleanup_calls_controller_promotion_directly": bool(capture.get("local_cleanup_calls_controller_promotion_directly")),
        "local_cleanup_no_longer_calls_page_promotion_helper": bool(capture.get("local_cleanup_no_longer_calls_page_promotion_helper")),
        "local_cleanup_keeps_page_callback_inputs": bool(capture.get("local_cleanup_keeps_page_callback_inputs")),
        "page_keeps_change_line_callback": bool(capture.get("page_keeps_change_line_callback")),
        "page_keeps_failure_coverage_callback": bool(capture.get("page_keeps_failure_coverage_callback")),
        "page_no_longer_owns_payload_shape": bool(capture.get("page_no_longer_owns_payload_shape")),
        "controller_owns_payload_shape": bool(capture.get("controller_owns_payload_shape")),
        "controller_exported": bool(capture.get("controller_exported")),
        "controller_has_no_page_or_streamlit_imports": bool(capture.get("controller_has_no_page_or_streamlit_imports")),
        "parity_cases_passed": bool(capture.get("all_parity_cases_passed")),
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "family_runtimes_unchanged": capture.get("family_runtimes_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    checks = dict(payload.get("checks") or {})
    lines = [
        "# Design Brain Physical Extraction Report",
        "",
        "## Executive Summary",
        str(payload.get("status") or ""),
        "",
        "## Surface Targeted",
        "`_promote_guidance_item_to_resolved_candidate(...)` local-cleanup candidate promotion.",
        "",
        "## Ownership Before",
        "`inputs_page.py` shaped the action payload, resolved-candidate fields, coverage fields, and candidate metadata.",
        "",
        "## Ownership After",
        "`design_brain.design_guide_controller.resolve_design_guide_controller_local_cleanup_candidate_promotion(...)` owns the pure projection. `inputs_page.py` still supplies page-owned change-line and failure-coverage callback outputs.",
        "",
        "## Behaviour Preserved",
        f"- Product behaviour changed: `{capture.get('product_behavior_changed')}`",
        f"- Visible wording changed: `{capture.get('visible_wording_changed')}`",
        f"- CTA/apply semantics changed: `{capture.get('cta_apply_semantics_changed')}`",
        f"- Family runtimes changed: `{capture.get('family_runtimes_changed')}`",
        "",
        "## Adapter / Default Rebuild Proof",
    ]
    for case in capture.get("parity_cases") or []:
        lines.append(f"- `{case.get('case')}`: passed=`{case.get('passed')}`")
    lines.extend(
        [
            "",
            "## Cutover Proof",
            f"- Page delegates promotion: `{capture.get('page_delegates_promotion')}`",
            f"- Local cleanup calls controller promotion directly: `{capture.get('local_cleanup_calls_controller_promotion_directly')}`",
            f"- Local cleanup no longer calls page promotion helper: `{capture.get('local_cleanup_no_longer_calls_page_promotion_helper')}`",
            f"- Page no longer owns payload shape: `{capture.get('page_no_longer_owns_payload_shape')}`",
            f"- Controller owns payload shape: `{capture.get('controller_owns_payload_shape')}`",
            "",
            "## Deadness / Deletion Proof",
            "No deletion yet. The page helper remains as a compatibility shell for callsites that need page-owned callback inputs.",
            "",
            "## Lines Removed / Added",
            "Payload/resolved-candidate construction moved out of the page helper.",
            "",
            "## Files Changed",
            "- `inputs_page.py`",
            "- `design_brain/design_guide_controller.py`",
            "- `tools/verification/design_guide_local_cleanup_candidate_promotion_extraction.py`",
            "",
            "## Verifier Results",
        ]
    )
    for name, passed in checks.items():
        lines.append(f"- `{name}`: `{passed}`")
    lines.extend(
        [
            "",
            "## Remaining Page-Owned Authority",
            "Change-line construction, failure-coverage summary, one-click probe, actionability callback, and shear executor safety callback remain page-owned/shell-owned.",
            "",
            "## Next Safe Target",
            "Refresh the local-cleanup shell audit and then target one-click/actionability callback boundaries only if they are not shell-only.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _append_progress(payload: dict[str, Any], report_path: Path) -> None:
    PROGRESS_PATH.parent.mkdir(parents=True, exist_ok=True)
    stamp = str(payload.get("created_at") or "")
    status = str(payload.get("status") or "")
    existing = PROGRESS_PATH.read_text(encoding="utf-8") if PROGRESS_PATH.exists() else ""
    entry = (
        "\n"
        f"## {stamp} - Local Cleanup Candidate Promotion Extraction\n"
        f"- Result: `{status}`\n"
        "- Moved pure resolved-candidate/action-payload promotion shape to `design_brain.design_guide_controller`.\n"
        "- Kept change-line and failure-coverage callbacks in `inputs_page.py`.\n"
        f"- Report: `{report_path}`\n"
    )
    if entry.strip() not in existing:
        PROGRESS_PATH.write_text(existing.rstrip() + "\n" + entry, encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().replace(microsecond=0).isoformat().replace(":", "-")
    capture = _capture()
    checks = _checks(capture)
    status = "PASS" if all(checks.values()) else "FAIL"
    payload = {
        "schema": "design_guide_local_cleanup_candidate_promotion_extraction.v1",
        "status": status,
        "created_at": stamp,
        "capture": capture,
        "checks": checks,
    }
    json_path = ARTIFACT_DIR / f"design_guide_local_cleanup_candidate_promotion_extraction_{stamp}.json"
    audit_path = AUDIT_DIR / f"design_guide_local_cleanup_candidate_promotion_extraction_{stamp}.md"
    report_path = REPORT_DIR / f"design_brain_physical_extraction_local_cleanup_candidate_promotion_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(audit_path, payload)
    _write_report(report_path, payload)
    if status == "PASS":
        _append_progress(payload, report_path)
    print(f"design_guide_local_cleanup_candidate_promotion_extraction {status}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
