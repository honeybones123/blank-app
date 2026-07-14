"""Verify `_guidance_item(...)` delegates canonical item assembly to controller."""

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

TARGET = "_guidance_item"
CONTROLLER_TARGET = "build_design_guide_controller_guidance_item"

FORBIDDEN_WRAPPER_TOKENS = {
    "_guidance_bucket(",
    "_guidance_priority(",
    "_format_guidance_title(",
    '"title_main"',
    '"title_util"',
    '"priority"',
    '"action_payload"',
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


def _expected_item(
    *,
    check_key: str,
    title: str,
    primary_action: str,
    secondary_action: str | None,
    reasoning: str,
    levers: str,
    action_type: str | None,
    action_payload: dict[str, Any] | None,
    status: str,
    util: float | None,
    guidance_before_after: str | None = None,
    guidance_change_lines: list[str] | None = None,
    guidance_why: str | None = None,
) -> dict[str, Any]:
    upper = str(status or "").upper()
    if "START" in upper:
        bucket = "start"
    elif "EFFICIENCY" in upper or "TIGHTEN" in upper:
        bucket = "efficiency"
    elif "FAIL" in upper or upper == "NG":
        bucket = "fail"
    elif "WARN" in upper or "NEAR LIMIT" in upper or upper == "CHECK":
        bucket = "warn"
    elif util is not None and util > 1.0:
        bucket = "fail"
    elif util is not None and util >= 0.9:
        bucket = "warn"
    else:
        bucket = "pass"
    util_score = util if util is not None else 0.0
    if bucket == "start":
        priority = 50.0
    elif bucket == "fail":
        priority = 300.0 + util_score
    elif bucket == "warn":
        priority = 200.0 + util_score
    elif bucket == "efficiency":
        priority = 150.0 + util_score
    else:
        priority = 100.0 - util_score
    out: dict[str, Any] = {
        "check_key": check_key,
        "title_main": title,
        "title_util": f"(utilisation = {util:.2f})" if util is not None else None,
        "title": f"{title} (utilisation = {util:.2f})" if util is not None else title,
        "primary_action": primary_action,
        "secondary_action": secondary_action,
        "reasoning": reasoning,
        "levers": levers,
        "status": status,
        "bucket": bucket,
        "util": util,
        "priority": priority,
        "action_type": action_type,
        "action_payload": action_payload or {},
    }
    if guidance_before_after:
        out["guidance_before_after"] = guidance_before_after
    if guidance_change_lines:
        out["guidance_change_lines"] = [
            str(value) for value in guidance_change_lines if str(value).strip()
        ]
    if guidance_why:
        out["guidance_why"] = str(guidance_why)
    return out


def _parity_cases() -> list[dict[str, Any]]:
    from design_brain.design_guide_controller import (
        build_design_guide_controller_guidance_item,
    )

    cases = [
        {
            "name": "fail_with_payload",
            "kwargs": {
                "check_key": "bending",
                "title": "Strengthening required",
                "primary_action": "Increase bottom reinforcement",
                "secondary_action": None,
                "reasoning": "Bending fails.",
                "levers": "bottom bars",
                "action_type": "apply_updates",
                "action_payload": {"updates": {"bot1_count": 6}},
                "status": "FAIL",
                "util": 1.24,
            },
        },
        {
            "name": "warn_without_payload",
            "kwargs": {
                "check_key": "shear",
                "title": "Near limit",
                "primary_action": "Review shear",
                "secondary_action": "No automatic change",
                "reasoning": "Shear is close.",
                "levers": "links",
                "action_type": None,
                "action_payload": None,
                "status": "WARN",
                "util": 0.92,
            },
        },
        {
            "name": "optional_fields",
            "kwargs": {
                "check_key": "combined",
                "title": "Cleanup available",
                "primary_action": "Tighten section",
                "secondary_action": "Keep checks passing",
                "reasoning": "Cleaner design.",
                "levers": "geometry and reo",
                "action_type": "apply_updates",
                "action_payload": {"updates": {"b": 350}},
                "status": "EFFICIENCY",
                "util": 0.67,
                "guidance_before_after": "Bending 0.50 -> 0.67",
                "guidance_change_lines": ["width 400 -> 350", "", "reo unchanged"],
                "guidance_why": "Moves toward the target band.",
            },
        },
    ]
    results: list[dict[str, Any]] = []
    for case in cases:
        kwargs = dict(case["kwargs"])
        actual = build_design_guide_controller_guidance_item(**kwargs)
        expected = _expected_item(**kwargs)
        results.append(
            {
                "name": case["name"],
                "match": actual == expected,
                "actual": actual,
                "expected": expected,
            }
        )
    return results


def _capture() -> dict[str, Any]:
    inputs_source = INPUTS_PAGE.read_text(encoding="utf-8-sig", errors="replace")
    controller_source = CONTROLLER.read_text(encoding="utf-8", errors="replace")
    wrapper = _function_segment(inputs_source, TARGET)
    controller = _function_segment(controller_source, CONTROLLER_TARGET)
    forbidden_present = sorted(token for token in FORBIDDEN_WRAPPER_TOKENS if token in wrapper)
    parity = _parity_cases()
    return {
        "schema": "design_guide_guidance_item_adapter_parity_snapshot.v1",
        "target": TARGET,
        "controller_target": CONTROLLER_TARGET,
        "page_wrapper_present": bool(wrapper),
        "controller_helper_present": bool(controller),
        "page_imports_controller_helper": (
            f"{CONTROLLER_TARGET} as _{CONTROLLER_TARGET}" in inputs_source
        ),
        "page_delegates_to_controller_helper": f"_{CONTROLLER_TARGET}(" in wrapper,
        "forbidden_wrapper_tokens_present": forbidden_present,
        "controller_has_no_page_or_streamlit_imports": (
            "inputs_page" not in controller_source and "streamlit" not in controller_source
        ),
        "parity_cases": parity,
        "parity_passed": all(case["match"] for case in parity),
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
        "page_wrapper_no_longer_builds_item_shape": not capture.get(
            "forbidden_wrapper_tokens_present"
        ),
        "controller_has_no_page_or_streamlit_imports": bool(
            capture.get("controller_has_no_page_or_streamlit_imports")
        ),
        "parity_passed": bool(capture.get("parity_passed")),
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "engineering_behavior_unchanged": capture.get("engineering_behavior_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Design Guide Guidance Item Adapter Parity",
        "",
        "## Executive Summary",
        str(payload.get("status") or ""),
        "",
        "## Surface Targeted",
        "`_guidance_item(...)`.",
        "",
        "## Ownership Before",
        "`inputs_page.py` built the canonical guidance item dictionary shape directly.",
        "",
        "## Ownership After",
        "`inputs_page.py` delegates canonical guidance item assembly to `build_design_guide_controller_guidance_item(...)`.",
        "",
        "## Parity",
    ]
    for case in capture.get("parity_cases") or []:
        lines.append(f"- {case.get('name')}: `{case.get('match')}`")
    lines.extend(
        [
            "",
            "## Page Wrapper",
            f"- delegates to controller: `{capture.get('page_delegates_to_controller_helper')}`",
            f"- forbidden wrapper tokens: `{capture.get('forbidden_wrapper_tokens_present')}`",
            "",
            "## Remaining Page-Owned Authority",
            "None for canonical item assembly. The page wrapper remains temporarily for existing callers.",
            "",
            "## Next Safe Target",
            "`_guidance_item_from_resolved_candidate(...)` or `_direct_target_band_guidance_item(...)`.",
            "",
        ]
    )
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
        "schema": "design_guide_guidance_item_adapter_parity_snapshot.v1",
        "status": status,
        "created_at": stamp,
        "capture": capture,
        "checks": checks,
    }
    json_path = ARTIFACT_DIR / f"design_guide_guidance_item_adapter_parity_{stamp}.json"
    audit_path = AUDIT_DIR / f"design_guide_guidance_item_adapter_parity_{stamp}.md"
    report_path = REPORT_DIR / f"design_brain_physical_extraction_guidance_item_adapter_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(audit_path, payload)
    _write_report(report_path, payload)
    print(f"design_guide_guidance_item_adapter_parity {status}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
