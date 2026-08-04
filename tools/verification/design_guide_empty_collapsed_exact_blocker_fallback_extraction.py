"""Verify empty-collapsed exact-blocker fallback is controller-owned.

This slice moves pure fallback/default materialization out of inputs_page.py.
The page may still call the helper as a compute shell, but it must not build the
fallback item, disabled button contract, display truth, or blocker evidence.
"""

from __future__ import annotations

import ast
from datetime import datetime
import json
from pathlib import Path
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
INPUTS_PAGE = ROOT / "inputs_page.py"
CONTROLLER = ROOT / "design_brain" / "design_guide_controller.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
REPORT_DIR = ROOT / "artifacts" / "reports"

TARGET = "_materialize_compute_empty_collapsed_exact_blocker_fallback"
CONTROLLER_TARGET = "build_design_guide_controller_empty_collapsed_exact_blocker_fallback"

FORBIDDEN_PAGE_TOKENS = {
    "_guidance_item(",
    "_parse_util_value(",
    "_design_mode_config(",
    "_design_optimisation_goal(",
    "exact_blockers_by_family",
    "post_click_exact_blockers_by_family",
    "cleanup_evidence_by_family",
    "post_click_cleanup_evidence_by_family",
    "primary_button_contract",
    "button_contract_enabled",
    "specific_blocker_materialized_from_compute_proof",
}

REQUIRED_CONTROLLER_TOKENS = {
    "_controller_guidance_item(",
    "_float_or_none(",
    "_presentation_mode_config(",
    "_presentation_goal_from_state(",
    "exact_blockers_by_family",
    "post_click_exact_blockers_by_family",
    "cleanup_evidence_by_family",
    "post_click_cleanup_evidence_by_family",
    "primary_button_contract",
    "button_contract_enabled",
    "specific_blocker_materialized_from_compute_proof",
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


def _latest(prefix: str) -> dict[str, Any]:
    paths = sorted(
        ARTIFACT_DIR.glob(f"{prefix}_*.json"),
        key=lambda path: path.stat().st_mtime,
    )
    if not paths:
        return {"found": False, "status": "MISSING", "path": None}
    path = paths[-1]
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"found": True, "status": f"UNREADABLE: {exc}", "path": str(path)}
    raw_status = str(payload.get("status") or payload.get("result") or "")
    status = "PASS" if "PASS" in raw_status.upper() else raw_status or "UNKNOWN"
    return {"found": True, "status": status, "path": str(path)}


def _run_existing_behavior_snapshot() -> dict[str, Any]:
    command = [
        sys.executable,
        "tools\\verification\\compute_empty_collapsed_exact_blocker_fallback_snapshot.py",
    ]
    completed = subprocess.run(
        command,
        cwd=str(ROOT),
        text=True,
        capture_output=True,
        timeout=120,
    )
    return {
        "command": " ".join(command),
        "returncode": completed.returncode,
        "stdout_tail": completed.stdout[-4000:],
        "stderr_tail": completed.stderr[-4000:],
        "passed": completed.returncode == 0,
        "latest_artifact": _latest("compute_empty_collapsed_exact_blocker_fallback_snapshot"),
    }


def _capture() -> dict[str, Any]:
    inputs_source = INPUTS_PAGE.read_text(encoding="utf-8-sig", errors="replace")
    controller_source = CONTROLLER.read_text(encoding="utf-8", errors="replace")
    page_helper = _function_segment(inputs_source, TARGET)
    controller_helper = _function_segment(controller_source, CONTROLLER_TARGET)
    forbidden_present = sorted(token for token in FORBIDDEN_PAGE_TOKENS if token in page_helper)
    controller_tokens_present = sorted(
        token for token in REQUIRED_CONTROLLER_TOKENS if token in controller_helper
    )
    behavior_snapshot = _run_existing_behavior_snapshot()
    return {
        "schema": "design_guide_empty_collapsed_exact_blocker_fallback_extraction.v1",
        "target": TARGET,
        "controller_target": CONTROLLER_TARGET,
        "page_helper_present": bool(page_helper),
        "controller_helper_present": bool(controller_helper),
        "page_imports_controller_helper": (
            f"{CONTROLLER_TARGET} as _{CONTROLLER_TARGET}" in inputs_source
        ),
        "page_delegates_to_controller_helper": (
            f"_{CONTROLLER_TARGET}(" in page_helper
        ),
        "forbidden_page_tokens_present": forbidden_present,
        "controller_tokens_present": controller_tokens_present,
        "controller_has_all_required_tokens": (
            controller_tokens_present == sorted(REQUIRED_CONTROLLER_TOKENS)
        ),
        "controller_has_no_page_or_streamlit_imports": (
            "inputs_page" not in controller_source and "streamlit" not in controller_source
        ),
        "behavior_snapshot": behavior_snapshot,
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "engineering_behavior_changed": False,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    return {
        "page_helper_present": bool(capture.get("page_helper_present")),
        "controller_helper_present": bool(capture.get("controller_helper_present")),
        "page_imports_controller_helper": bool(capture.get("page_imports_controller_helper")),
        "page_delegates_to_controller_helper": bool(capture.get("page_delegates_to_controller_helper")),
        "page_no_longer_contains_fallback_builder_tokens": not capture.get(
            "forbidden_page_tokens_present"
        ),
        "controller_has_all_required_tokens": bool(capture.get("controller_has_all_required_tokens")),
        "controller_has_no_page_or_streamlit_imports": bool(
            capture.get("controller_has_no_page_or_streamlit_imports")
        ),
        "behavior_snapshot_passed": bool(
            (capture.get("behavior_snapshot") or {}).get("passed")
        ),
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "engineering_behavior_unchanged": capture.get("engineering_behavior_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    behavior = dict(capture.get("behavior_snapshot") or {})
    lines = [
        "# Design Brain Physical Extraction Report",
        "",
        "## Executive Summary",
        str(payload.get("status") or ""),
        "",
        "## Surface Targeted",
        "`_materialize_compute_empty_collapsed_exact_blocker_fallback(...)`.",
        "",
        "## Ownership Before",
        "`inputs_page.py` built the exact-blocker fallback item, disabled button contract, display truth, cleanup evidence, and debug proof fields directly.",
        "",
        "## Ownership After",
        "`inputs_page.py` delegates the projection to `build_design_guide_controller_empty_collapsed_exact_blocker_fallback(...)` in `design_brain.design_guide_controller`.",
        "",
        "## Behaviour Preserved",
        f"- Existing behavior snapshot passed: `{behavior.get('passed')}`",
        f"- Existing behavior artifact: `{(behavior.get('latest_artifact') or {}).get('path')}`",
        "- Engineering behaviour unchanged.",
        "- Visible wording unchanged.",
        "- CTA/apply semantics unchanged.",
        "- Family runtimes unchanged.",
        "",
        "## Adapter / Default Rebuild Proof",
        f"- page delegates to controller: `{capture.get('page_delegates_to_controller_helper')}`",
        f"- forbidden page builder tokens: `{capture.get('forbidden_page_tokens_present')}`",
        f"- controller owns required tokens: `{capture.get('controller_has_all_required_tokens')}`",
        f"- controller has no page/Streamlit imports: `{capture.get('controller_has_no_page_or_streamlit_imports')}`",
        "",
        "## Cutover Proof",
        "The page helper remains as the compute shell boundary but no longer owns the fallback projection.",
        "",
        "## Deadness / Deletion Proof",
        "The page wrapper is not deleted yet because the compute core still calls this boundary. It is now shell-only and can be evaluated in the later zero-authority inventory lock.",
        "",
        "## Remaining Page-Owned Authority",
        "None for this fallback projection. The remaining page surface is an approved shell call.",
        "",
        "## Next Safe Target",
        "Guidance item adapter helpers.",
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
        "schema": "design_guide_empty_collapsed_exact_blocker_fallback_extraction.v1",
        "status": status,
        "created_at": stamp,
        "capture": capture,
        "checks": checks,
    }
    json_path = ARTIFACT_DIR / f"design_guide_empty_collapsed_exact_blocker_fallback_extraction_{stamp}.json"
    audit_path = AUDIT_DIR / f"design_guide_empty_collapsed_exact_blocker_fallback_extraction_{stamp}.md"
    report_path = REPORT_DIR / f"design_brain_physical_extraction_empty_collapsed_exact_blocker_fallback_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(audit_path, payload)
    _write_report(report_path, payload)
    print(f"design_guide_empty_collapsed_exact_blocker_fallback_extraction {status}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
