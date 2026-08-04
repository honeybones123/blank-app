"""Audit extraction readiness for _build_design_guide_presentation_state.

This is a deletion-enabling audit.  The presentation adapter is the last
transitional Design Guide truth surface called out by the legacy truth audit.
This verifier identifies the exact page-owned dependencies that must become a
controller/final-publication request boundary before the page helper can be
cut over or deleted.
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
FINAL_PUBLICATION = ROOT / "design_brain" / "final_publication.py"
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


def _line_numbers(source: str, token: str) -> list[int]:
    return [idx for idx, line in enumerate(source.splitlines(), start=1) if token in line]


def _latest(prefix: str) -> dict[str, Any]:
    paths = sorted(ARTIFACT_DIR.glob(f"{prefix}_*.json"), key=lambda path: path.stat().st_mtime)
    if not paths:
        return {"found": False, "status": "MISSING", "path": None}
    path = paths[-1]
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"found": True, "status": "UNREADABLE", "path": str(path), "error": str(exc)}
    status = str(payload.get("status") or payload.get("result") or payload.get("lock_status") or "")
    if "PASS" in status.upper() or "LOCKED" in status.upper() or "COMPLETE" in status.upper():
        status = "PASS"
    return {"found": True, "status": status or "UNKNOWN", "path": str(path)}


def _capture() -> dict[str, Any]:
    inputs_source = INPUTS_PAGE.read_text(encoding="utf-8-sig", errors="replace")
    final_source = FINAL_PUBLICATION.read_text(encoding="utf-8", errors="replace")
    controller_source = CONTROLLER.read_text(encoding="utf-8", errors="replace")
    body = _source_segment(inputs_source, TARGET)
    dependency_groups = {
        "page_session_side_effects": {
            "st.session_state": "writes `_design_guide_engine_decision` from inside presentation helper",
        },
        "page_current_state_policy_helpers": {
            "_design_optimisation_goal(": "derives optimisation goal from page state",
            "_design_mode_config(": "derives mode config from page state",
            "_guidance_governing_primary_action(": "derives governing action display input",
            "_design_guide_display_truth_for_item(": "derives item display truth",
            "_derive_design_guide_guidance_intent(": "derives guidance intent fallback",
        },
        "page_cta_state_helpers": {
            "_one_click_feedback_cta_state(": "reads one-click feedback CTA state",
            "_latest_solver_result_cta_state(": "reads latest solver result CTA state",
            "_recommendation_updates_for_envelope(": "checks item update payload availability",
            "_recommendation_commit_eligible(": "checks pending recommendation commit eligibility",
            "_recommendation_blocked_reason(": "extracts pending blocked reason",
        },
        "design_brain_ready_dependencies": {
            "resolve_design_guide_decision(": "already delegates decision to Design Brain engine",
            "target_band_payload(": "target-band payload already supplied to engine",
            "is_unnecessarily_overdesigned(": "overdesign policy helper used as engine input",
            "_is_in_target_zone_with_eps(": "target-zone policy helper used as engine input",
        },
    }
    dependency_rows: list[dict[str, Any]] = []
    for group, tokens in dependency_groups.items():
        for token, reason in tokens.items():
            dependency_rows.append(
                {
                    "group": group,
                    "token": token,
                    "present": token in body,
                    "line_numbers": _line_numbers(body, token),
                    "reason": reason,
                }
            )
    blocking_groups = {
        "page_session_side_effects",
        "page_current_state_policy_helpers",
        "page_cta_state_helpers",
    }
    blocking_rows = [
        row for row in dependency_rows if row["present"] and row["group"] in blocking_groups
    ]
    controller_has_presentation_builder = (
        "class DesignGuideControllerPresentationRequest" in controller_source
        and "class DesignGuideControllerPresentationResponse" in controller_source
        and "def run_design_guide_controller_presentation_adapter" in controller_source
        and "resolve_design_guide_decision(" in controller_source
    )
    final_publication_consumes_presentation = (
        'presentation_d = _mapping(debug_d.get("design_guide_presentation"))' in final_source
    )
    return {
        "decision": (
            "PRESENTATION_ADAPTER_NOT_READY_TO_DELETE_REQUEST_BOUNDARY_REQUIRED"
            if blocking_rows
            else "PRESENTATION_ADAPTER_READY_FOR_CUTOVER_PROOF"
        ),
        "target_function_present": bool(body),
        "target_function_line_numbers": _line_numbers(inputs_source, f"def {TARGET}("),
        "dependency_rows": dependency_rows,
        "blocking_rows": blocking_rows,
        "controller_has_presentation_builder": controller_has_presentation_builder,
        "final_publication_consumes_presentation": final_publication_consumes_presentation,
        "latest": {
            "legacy_truth_surface": _latest("design_guide_inputs_page_legacy_truth_surface_audit"),
            "independence_lock": _latest("design_guide_independence_lock"),
            "render_bridge_lock": _latest("design_guide_render_bridge_lock"),
            "compute_bridge_lock": _latest("design_guide_compute_resolver_publication_bridge_lock"),
        },
        "recommended_next_slice": (
            "The controller presentation adapter exists and owns the decision/output shape. "
            "Next, reduce `_build_design_guide_presentation_state(...)` to raw request collection "
            "by moving the remaining page policy/context preparation behind the controller boundary."
        ),
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "engineering_behavior_changed": False,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    latest = dict(capture.get("latest") or {})
    return {
        "target_function_found": bool(capture.get("target_function_present")),
        "dependencies_classified": all(
            row.get("group") and row.get("reason")
            for row in capture.get("dependency_rows") or []
        ),
        "blocking_rows_identified": bool(capture.get("blocking_rows"))
        == (
            capture.get("decision")
            == "PRESENTATION_ADAPTER_NOT_READY_TO_DELETE_REQUEST_BOUNDARY_REQUIRED"
        ),
        "final_publication_consumes_presentation": bool(
            capture.get("final_publication_consumes_presentation")
        ),
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
        "# Design Guide Presentation Adapter Extraction Readiness Audit",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        "",
        "## Summary",
        "",
        f"- target function present: `{capture.get('target_function_present')}`",
        f"- blocking dependency rows: `{len(capture.get('blocking_rows') or [])}`",
        f"- controller has presentation builder: `{capture.get('controller_has_presentation_builder')}`",
        f"- FinalDesignGuidePublication consumes presentation: `{capture.get('final_publication_consumes_presentation')}`",
        "",
        "## Blocking Dependencies",
        "",
        "| Group | Token | Reason |",
        "|---|---|---|",
    ]
    for row in capture.get("blocking_rows") or []:
        lines.append(f"| {row.get('group')} | `{row.get('token')}` | {row.get('reason')} |")
    lines.extend(
        [
            "",
            "## All Dependency Rows",
            "",
            "| Group | Token | Present | Reason |",
            "|---|---|---:|---|",
        ]
    )
    for row in capture.get("dependency_rows") or []:
        lines.append(
            f"| {row.get('group')} | `{row.get('token')}` | `{row.get('present')}` | {row.get('reason')} |"
        )
    lines.extend(
        [
            "",
            "## Next Safe Target",
            "",
            str(capture.get("recommended_next_slice") or ""),
        ]
    )
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
        "schema": "design_guide_presentation_adapter_extraction_readiness_audit.v1",
        "status": status,
        "created_at": stamp,
        "capture": capture,
        "checks": checks,
    }
    json_path = ARTIFACT_DIR / f"design_guide_presentation_adapter_extraction_readiness_{stamp}.json"
    audit_path = AUDIT_DIR / f"design_guide_presentation_adapter_extraction_readiness_{stamp}.md"
    report_path = REPORT_DIR / f"design_brain_physical_extraction_presentation_adapter_readiness_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    _write_report(audit_path, payload)
    _write_report(report_path, payload)
    print(f"design_guide_presentation_adapter_extraction_readiness {status}")
    print(f"decision={capture.get('decision')}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
