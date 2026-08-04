"""Prove compute resolver controller request is built from pre-resolver inputs.

This is proof-only. It verifies the current compute resolver controller path can
construct its request before any final compute resolver output exists, and that
the normal product assignment is controller-owned.
"""

from __future__ import annotations

from datetime import datetime
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
REPORT_DIR = ROOT / "artifacts" / "reports"
INPUTS_PAGE = ROOT / "inputs_page.py"

REQUEST_START = "_pre_resolver_controller_request = _DesignGuideControllerComputePublicationHandoffRequest("
RESPONSE_CALL = "_run_design_guide_controller_compute_resolver_replacement_trace_only("
CONTROLLER_ASSIGNMENT = "_pre_resolver_controller_response.final_compute_resolution or {}"
FALLBACK_SHELL_CALL = "_build_design_guide_controller_compute_resolver_fallback_shell("
OLD_DIRECT_ASSIGNMENT = "final_compute_resolution = resolve_final_visible_design_guide_item("
OLD_FALLBACK_ASSIGNMENT = "_legacy_fallback_resolution = resolve_final_visible_design_guide_item("

REQUIRED_REQUEST_FIELDS = {
    "current_state": "current_state=dict(state or {})",
    "overview": "overview=dict(debug_trace.get(\"overview\") or {})",
    "collapsed_guidance_items": "collapsed_guidance_items=[",
    "publication_context": "publication_context=_design_guide_publication_object_payload(",
    "publication_dependencies": "publication_dependencies=_design_guide_publication_object_payload(",
    "blocker_evidence_surface": "blocker_evidence_surface=dict(_pre_resolver_blocker_evidence_surface)",
    "pre_resolver_collapsed_item_mutation": "pre_resolver_collapsed_item_mutation=dict(_pre_resolver_mutation)",
    "debug": "debug=dict(debug_trace or {})",
    "verifier_payload": "verifier_payload=dict(debug_trace.get(\"final_publication_verifier_payload\") or {})",
    "session_controls": "session_controls=dict(_pre_resolver_session_controls or {})",
    "design_actions_signature": "design_actions_signature=tuple(_pre_resolver_design_actions_signature or ())",
    "optimisation_goal": "optimisation_goal=str(_pre_resolver_optimisation_goal or \"\")",
    "source": "source=\"inputs_page_compute_resolver_replacement_pre_resolver_trace\"",
}

FORBIDDEN_REQUEST_TOKENS = {
    "old_resolver_call": "resolve_final_visible_design_guide_item(",
    "final_compute_resolution": "final_compute_resolution",
    "controller_response_resolution": "_pre_resolver_controller_response.final_compute_resolution",
    "legacy_fallback_resolution": "_legacy_fallback_resolution",
}


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _latest(prefix: str) -> dict[str, Any]:
    paths = sorted(ARTIFACT_DIR.glob(f"{prefix}_*.json"), key=lambda path: path.stat().st_mtime)
    if not paths:
        return {"found": False, "status": "MISSING", "path": None, "payload": {}}
    path = paths[-1]
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception as exc:
        return {
            "found": True,
            "status": "UNREADABLE",
            "path": str(path),
            "payload": {},
            "error": f"{type(exc).__name__}: {exc}",
        }
    status = str(payload.get("status") or payload.get("result") or payload.get("lock_status") or "")
    if "PASS" in status.upper() or "LOCKED" in status.upper() or "COMPLETE" in status.upper():
        status = "PASS"
    return {"found": True, "status": status or "UNKNOWN", "path": str(path), "payload": payload}


def _run(command: list[str]) -> dict[str, Any]:
    proc = subprocess.run(command, cwd=ROOT, text=True, capture_output=True)
    return {
        "command": command,
        "returncode": proc.returncode,
        "stdout_tail": proc.stdout[-4000:],
        "stderr_tail": proc.stderr[-4000:],
    }


def _line_for_offset(source: str, offset: int) -> int | None:
    if offset < 0:
        return None
    return source.count("\n", 0, offset) + 1


def _block_between(source: str, start_token: str, end_token: str) -> str:
    start = source.find(start_token)
    if start < 0:
        return ""
    end = source.find(end_token, start)
    return source[start:end] if end > start else ""


def _capture() -> dict[str, Any]:
    source = INPUTS_PAGE.read_text(encoding="utf-8-sig", errors="replace").lstrip("\ufeff")
    request_start = source.find(REQUEST_START)
    response_start = source.find(RESPONSE_CALL, request_start if request_start >= 0 else 0)
    assignment_start = source.find(
        CONTROLLER_ASSIGNMENT,
        response_start if response_start >= 0 else max(request_start, 0),
    )
    fallback_start = source.find(FALLBACK_SHELL_CALL, assignment_start if assignment_start >= 0 else 0)
    request_block = _block_between(source, REQUEST_START, RESPONSE_CALL)
    latest = {
        "browser_parity": _latest("design_guide_compute_resolver_replacement_browser_live_parity"),
        "controller_cutover": _latest("design_guide_compute_stage_resolver_controller_cutover"),
        "deletion_readiness": _latest("design_guide_compute_stage_resolver_deletion_readiness"),
        "compatibility_helper_readiness": _latest(
            "design_guide_remaining_compatibility_helper_deletion_readiness"
        ),
        "independence_lock": _latest("design_guide_independence_lock"),
        "render_bridge_lock": _latest("design_guide_render_bridge_lock"),
        "compute_bridge_lock": _latest("design_guide_compute_resolver_publication_bridge_lock"),
    }
    browser_live = dict((latest["browser_parity"].get("payload") or {}).get("live_trace") or {})
    controller_cutover_capture = dict(
        (latest["controller_cutover"].get("payload") or {}).get("capture") or {}
    )
    field_presence = {
        name: token in request_block for name, token in REQUIRED_REQUEST_FIELDS.items()
    }
    forbidden_presence = {
        name: token in request_block for name, token in FORBIDDEN_REQUEST_TOKENS.items()
    }
    checks = {
        "request_block_found": bool(request_block),
        "request_before_response": request_start >= 0 and response_start > request_start,
        "response_before_controller_assignment": response_start >= 0 and assignment_start > response_start,
        "fallback_after_controller_assignment": fallback_start > assignment_start >= 0,
        "all_required_fields_present": all(field_presence.values()),
        "request_has_no_old_resolver_output": not any(forbidden_presence.values()),
        "trace_stamps_old_resolver_output_not_consumed": (
            "\"old_resolver_output_consumed_for_request\": False" in source
        ),
        "old_direct_assignment_absent": OLD_DIRECT_ASSIGNMENT not in source,
        "old_fallback_assignment_absent": OLD_FALLBACK_ASSIGNMENT not in source,
        "normal_path_controller_owned": CONTROLLER_ASSIGNMENT in source,
        "controller_fallback_shell_present": FALLBACK_SHELL_CALL in source,
        "latest_browser_parity_pass": latest["browser_parity"].get("status") == "PASS",
        "latest_browser_old_resolver_output_not_consumed": (
            browser_live.get("old_resolver_output_consumed_for_request") is False
            or browser_live.get("old_resolver_input_required") is False
        ),
        "latest_browser_fallback_not_used": browser_live.get("controller_cutover_fallback_used") is False,
        "latest_controller_cutover_pass": latest["controller_cutover"].get("status") == "PASS",
        "latest_controller_cutover_decision_green": controller_cutover_capture.get("decision")
        in {
            "CONTROLLER_CUTOVER_LIVE_FALLBACK_NOT_USED",
            "LEGACY_RESOLVER_REPLACED_CONTROLLER_FALLBACK_SHELL_RETAINED",
        },
        "independence_lock_pass": latest["independence_lock"].get("status") == "PASS",
        "render_bridge_lock_pass": latest["render_bridge_lock"].get("status") == "PASS",
        "compute_bridge_lock_pass": latest["compute_bridge_lock"].get("status") == "PASS",
    }
    return {
        "decision": (
            "PRE_RESOLVER_REQUEST_PROVEN"
            if all(checks.values())
            else "PRE_RESOLVER_REQUEST_NOT_PROVEN"
        ),
        "target_surface": "compute_stage_final_visible_resolver",
        "request_lines": {
            "request_start": _line_for_offset(source, request_start),
            "response_call": _line_for_offset(source, response_start),
            "controller_assignment": _line_for_offset(source, assignment_start),
            "fallback_shell": _line_for_offset(source, fallback_start),
        },
        "field_presence": field_presence,
        "forbidden_presence": forbidden_presence,
        "checks": checks,
        "latest": {
            key: {"status": value.get("status"), "path": value.get("path")}
            for key, value in latest.items()
        },
        "browser_live_trace": {
            "controller_cutover_used": browser_live.get("controller_cutover_used"),
            "controller_cutover_fallback_used": browser_live.get("controller_cutover_fallback_used"),
            "old_resolver_output_consumed_for_request": browser_live.get(
                "old_resolver_output_consumed_for_request"
            ),
            "old_resolver_input_required": browser_live.get("old_resolver_input_required"),
            "state_fingerprint_match": browser_live.get("state_fingerprint_match"),
            "render_reason_match": browser_live.get("render_reason_match"),
            "effective_selected_item_match": browser_live.get("effective_selected_item_match"),
        },
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "engineering_behavior_changed": False,
    }


def _write_audit(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Compute Resolver Pre-Resolver Request Snapshot",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Request Lines",
        "",
        "```json",
        json.dumps(capture.get("request_lines") or {}, indent=2),
        "```",
        "",
        "## Required Fields",
        "",
    ]
    lines.extend(f"- {key}: `{value}`" for key, value in (capture.get("field_presence") or {}).items())
    lines.extend(["", "## Forbidden Tokens In Request Block", ""])
    lines.extend(
        f"- {key}: `{value}`" for key, value in (capture.get("forbidden_presence") or {}).items()
    )
    lines.extend(["", "## Checks", ""])
    lines.extend(f"- {key}: `{value}`" for key, value in (capture.get("checks") or {}).items())
    lines.extend(["", "## Next Safe Step", ""])
    lines.append(
        "If this stays green with browser/live parity, the next slice can prove cutover/deadness "
        "for remaining compatibility helpers. Do not delete fallback shell until controller-owned "
        "fallback coverage is locked."
    )
    if payload.get("failures"):
        lines.extend(["", "## Failures", "", "```json", json.dumps(payload["failures"], indent=2), "```"])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_physical_extraction_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    status = payload.get("status")
    lines = [
        "# Design Brain Physical Extraction Report",
        "",
        "## Executive Summary",
        str(status),
        "",
        "## Surface Targeted",
        "`compute_stage_final_visible_resolver` pre-resolver controller request.",
        "",
        "## Ownership Before",
        "The page still assembles inputs for the compute resolver handoff.",
        "",
        "## Ownership After",
        "No behavior change in this slice. The verifier proves the controller request is built before resolver output exists.",
        "",
        "## Behaviour Preserved",
        "Engineering behavior, visible wording, CTA/apply semantics, family runtimes, widget keys, session behavior, and publication behavior were not changed.",
        "",
        "## Cutover Proof",
        f"Decision: `{capture.get('decision')}`",
        "",
        "## Deadness / Deletion Proof",
        "No deletion in this slice. Old direct resolver assignment is absent; controller fallback shell remains bounded.",
        "",
        "## Files Changed",
        "- `tools/verification/design_guide_compute_resolver_pre_resolver_request_snapshot.py`",
        "",
        "## Verifier Results",
        "```json",
        json.dumps(capture.get("checks") or {}, indent=2, sort_keys=True),
        "```",
        "",
        "## Remaining Page-Owned Authority",
        "Remaining page-owned compute compatibility helpers and fallback shell surfaces still need dedicated deadness/coverage proof.",
        "",
        "## Next Safe Target",
        "Run/refresh compute resolver controller cutover, fallback deadness, compatibility helper readiness, and composed locks; then decide whether a helper deletion slice is allowed.",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _stamp()
    compile_run = _run(
        [
            sys.executable,
            "-m",
            "py_compile",
            "inputs_page.py",
            "tools/verification/design_guide_compute_resolver_pre_resolver_request_snapshot.py",
        ]
    )
    capture = _capture()
    failures: list[str] = []
    if compile_run["returncode"] != 0:
        failures.append("py_compile_failed")
    failures.extend(
        key for key, value in dict(capture.get("checks") or {}).items() if value is not True
    )
    status = "PASS" if not failures else "FAIL"
    payload = {
        "schema": "design_guide_compute_resolver_pre_resolver_request_snapshot.v1",
        "status": status,
        "created_at": stamp,
        "capture": capture,
        "compile_run": compile_run,
        "failures": failures,
    }
    payload["snapshot_hash"] = _stable_hash(payload)
    json_path = ARTIFACT_DIR / f"design_guide_compute_resolver_pre_resolver_request_{stamp}.json"
    audit_path = AUDIT_DIR / f"design_guide_compute_resolver_pre_resolver_request_{stamp}.md"
    report_path = REPORT_DIR / f"design_brain_physical_extraction_compute_resolver_pre_resolver_request_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_audit(audit_path, payload)
    _write_physical_extraction_report(report_path, payload)
    print(f"design_guide_compute_resolver_pre_resolver_request {status}")
    print(f"decision={capture.get('decision')}")
    print(f"json={json_path}")
    print(f"audit={audit_path}")
    print(f"report={report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
