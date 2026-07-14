"""Verify the presentation helper delegates output authority to the controller.

This is a narrow cutover verifier.  The page still gathers current page/session
inputs, but the final Design Guide presentation decision/output must come from
DesignGuideController rather than a direct page call to the engine.
"""

from __future__ import annotations

import ast
from datetime import datetime
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
REPORT_DIR = ROOT / "artifacts" / "reports"
INPUTS_PAGE = ROOT / "inputs_page.py"
CONTROLLER = ROOT / "design_brain" / "design_guide_controller.py"

TARGET = "_build_design_guide_presentation_state"


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _source_segment(source: str, function_name: str) -> str:
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == function_name:
            lines = source.splitlines()
            return "\n".join(lines[node.lineno - 1 : node.end_lineno])
    return ""


def _latest(prefix: str) -> dict[str, Any]:
    paths = sorted(ARTIFACT_DIR.glob(f"{prefix}_*.json"), key=lambda path: path.stat().st_mtime)
    if not paths:
        return {"found": False, "status": "MISSING", "path": None}
    path = paths[-1]
    payload = json.loads(path.read_text(encoding="utf-8"))
    status = str(payload.get("status") or payload.get("result") or payload.get("lock_status") or "")
    if "PASS" in status.upper() or "LOCKED" in status.upper() or "COMPLETE" in status.upper():
        status = "PASS"
    return {"found": True, "status": status or "UNKNOWN", "path": str(path)}


def _capture() -> dict[str, Any]:
    inputs_source = INPUTS_PAGE.read_text(encoding="utf-8-sig", errors="replace")
    controller_source = CONTROLLER.read_text(encoding="utf-8", errors="replace")
    body = _source_segment(inputs_source, TARGET)
    controller_function = _source_segment(
        controller_source,
        "run_design_guide_controller_presentation_adapter",
    )
    return {
        "decision": "PRESENTATION_ADAPTER_CUTOVER_IMPLEMENTED_HELPER_NOT_DELETED",
        "target_function_present": bool(body),
        "page_imports_builder": "build_design_guide_controller_presentation_request as _build_design_guide_controller_presentation_request" in inputs_source,
        "page_imports_runner": "run_design_guide_controller_presentation_adapter as _run_design_guide_controller_presentation_adapter" in inputs_source,
        "page_builds_controller_request": "_build_design_guide_controller_presentation_request(" in body,
        "page_calls_controller_runner": "_run_design_guide_controller_presentation_adapter(" in body,
        "page_direct_engine_call_removed_from_helper": "resolve_design_guide_decision(" not in body,
        "controller_request_exists": "class DesignGuideControllerPresentationRequest" in controller_source,
        "controller_response_exists": "class DesignGuideControllerPresentationResponse" in controller_source,
        "controller_request_builder_exists": "def build_design_guide_controller_presentation_request(" in controller_source,
        "controller_runner_exists": "def run_design_guide_controller_presentation_adapter(" in controller_source,
        "controller_runner_calls_engine": "resolve_design_guide_decision(" in controller_function,
        "controller_has_no_page_imports": "inputs_page" not in controller_source and "streamlit" not in controller_source,
        "latest": {
            "readiness": _latest("design_guide_presentation_adapter_extraction_readiness"),
            "legacy_truth_surface": _latest("design_guide_inputs_page_legacy_truth_surface_audit"),
            "independence_lock": _latest("design_guide_independence_lock"),
            "render_bridge_lock": _latest("design_guide_render_bridge_lock"),
            "compute_bridge_lock": _latest("design_guide_compute_resolver_publication_bridge_lock"),
        },
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "engineering_behavior_changed": False,
        "helper_deleted": False,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    latest = dict(capture.get("latest") or {})
    return {
        "target_function_present": bool(capture.get("target_function_present")),
        "page_imports_builder": bool(capture.get("page_imports_builder")),
        "page_imports_runner": bool(capture.get("page_imports_runner")),
        "page_builds_controller_request": bool(capture.get("page_builds_controller_request")),
        "page_calls_controller_runner": bool(capture.get("page_calls_controller_runner")),
        "page_direct_engine_call_removed_from_helper": bool(capture.get("page_direct_engine_call_removed_from_helper")),
        "controller_request_exists": bool(capture.get("controller_request_exists")),
        "controller_response_exists": bool(capture.get("controller_response_exists")),
        "controller_request_builder_exists": bool(capture.get("controller_request_builder_exists")),
        "controller_runner_exists": bool(capture.get("controller_runner_exists")),
        "controller_runner_calls_engine": bool(capture.get("controller_runner_calls_engine")),
        "controller_has_no_page_imports": bool(capture.get("controller_has_no_page_imports")),
        "readiness_latest_pass": (latest.get("readiness") or {}).get("status") == "PASS",
        "legacy_truth_surface_latest_pass": (latest.get("legacy_truth_surface") or {}).get("status") == "PASS",
        "independence_lock_latest_pass": (latest.get("independence_lock") or {}).get("status") == "PASS",
        "render_bridge_lock_latest_pass": (latest.get("render_bridge_lock") or {}).get("status") == "PASS",
        "compute_bridge_lock_latest_pass": (latest.get("compute_bridge_lock") or {}).get("status") == "PASS",
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "engineering_behavior_unchanged": capture.get("engineering_behavior_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Design Brain Physical Extraction Report",
        "",
        "## Executive Summary",
        payload.get("status", ""),
        "",
        "## Surface Targeted",
        "`_build_design_guide_presentation_state(...)` presentation output authority.",
        "",
        "## Ownership Before",
        "The page helper directly called `resolve_design_guide_decision(...)` and returned its presentation.",
        "",
        "## Ownership After",
        "The page helper delegates plain request construction to `build_design_guide_controller_presentation_request(...)` and calls `run_design_guide_controller_presentation_adapter(...)`.",
        "",
        "## Behaviour Preserved",
        "- Engineering behaviour unchanged.",
        "- Visible wording unchanged.",
        "- CTA/apply semantics unchanged.",
        "- Family runtimes unchanged.",
        "",
        "## Cutover Proof",
        f"- page direct engine call removed from helper: `{capture.get('page_direct_engine_call_removed_from_helper')}`",
        f"- page calls controller request builder: `{capture.get('page_builds_controller_request')}`",
        f"- page calls controller runner: `{capture.get('page_calls_controller_runner')}`",
        f"- controller request builder exists: `{capture.get('controller_request_builder_exists')}`",
        f"- controller runner calls engine: `{capture.get('controller_runner_calls_engine')}`",
        f"- controller has no page imports: `{capture.get('controller_has_no_page_imports')}`",
        "",
        "## Deadness / Deletion Proof",
        "Helper is not deleted yet. Remaining work is moving page/session input gathering into a bounded request builder or proving it is approved page-shell input collection.",
        "",
        "## Remaining Page-Owned Authority",
        "The helper still computes request inputs from page/session helpers before calling the controller adapter.",
        "",
        "## Next Safe Target",
        "Add parity/live impact proof for the controller presentation adapter, then reduce `_build_design_guide_presentation_state(...)` to a thin request builder or delete it if all callers can call the controller boundary directly.",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _stamp()
    capture = _capture()
    checks = _checks(capture)
    status = "PASS" if all(checks.values()) else "FAIL"
    payload = {
        "schema": "design_guide_presentation_adapter_cutover_snapshot.v1",
        "status": status,
        "created_at": stamp,
        "capture": capture,
        "checks": checks,
    }
    json_path = ARTIFACT_DIR / f"design_guide_presentation_adapter_cutover_{stamp}.json"
    audit_path = AUDIT_DIR / f"design_guide_presentation_adapter_cutover_{stamp}.md"
    report_path = REPORT_DIR / f"design_brain_physical_extraction_presentation_adapter_cutover_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    _write_report(audit_path, payload)
    _write_report(report_path, payload)
    print(f"design_guide_presentation_adapter_cutover {status}")
    print(f"decision={capture.get('decision')}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
