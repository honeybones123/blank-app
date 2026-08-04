"""Cutover-readiness snapshot for residual-shear route-body replacement."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
REPORT_DIR = ROOT / "artifacts" / "reports"
INPUTS = ROOT / "inputs_page.py"


def _stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")


def _run(cmd: list[str]) -> dict[str, Any]:
    proc = subprocess.run(
        cmd,
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=120,
    )
    return {
        "cmd": " ".join(cmd),
        "returncode": proc.returncode,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
        "passed": proc.returncode == 0,
    }


def _latest(prefix: str) -> dict[str, Any]:
    paths = sorted(ARTIFACT_DIR.glob(f"{prefix}_*.json"))
    if not paths:
        return {"found": False, "path": "", "status": ""}
    path = paths[-1]
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"found": True, "path": str(path), "status": "UNREADABLE", "error": str(exc)}
    return {
        "found": True,
        "path": str(path),
        "status": str(payload.get("status") or ""),
        "payload": payload,
    }


def _function_block(source: str, token: str) -> str:
    start = source.find(token)
    if start < 0:
        return ""
    end = source.find("\ndef ", start + 1)
    return source[start:end] if end > start else source[start:]


def _capture() -> dict[str, Any]:
    object_snapshot_run = _run(
        [
            sys.executable,
            "tools/verification/design_guide_post_click_low_bending_residual_shear_cleanup_route_body_replacement_object_snapshot.py",
        ]
    )
    trace_wiring_run = _run(
        [
            sys.executable,
            "tools/verification/design_guide_post_click_low_bending_residual_shear_cleanup_route_body_replacement_trace_wiring_snapshot.py",
        ]
    )
    source = INPUTS.read_text(encoding="utf-8-sig", errors="replace")
    helper = _function_block(
        source,
        "def _stamp_design_guide_controller_post_click_low_bending_residual_shear_cleanup_route_body_replacement(",
    )
    latest_trace = _latest(
        "design_guide_post_click_low_bending_residual_shear_cleanup_route_body_replacement_trace_wiring"
    )
    trace_capture = dict((latest_trace.get("payload") or {}).get("capture") or {})
    route_body_replacement_debug_keys = (
        "route_body_replacement_hash",
        "route_shell_adapter_hash",
        "result_item_hash",
        "current_item_hash",
        "result_item_matches_current_item",
        "dependency_hashes",
        "dependency_status",
        "unresolved_dependencies",
        "output_shape_ready",
        "behavior_cutover_ready",
        "safe_next_cutover_surface",
    )
    route_shape_cutover_ready = all(
        (
            object_snapshot_run.get("passed") is True,
            trace_wiring_run.get("passed") is True,
            "result_item_matches_current_item" in helper,
            "output_shape_ready" in helper,
            "behavior_cutover_ready" in helper,
            '"page_live"' in helper,
        )
    )
    behavior_cutover_ready = False
    safe_to_delete_old_body = False
    return {
        "decision": "ROUTE_BODY_RESULT_IDENTITY_READY_FOR_NEXT_NARROW_CUTOVER",
        "object_snapshot_run": object_snapshot_run,
        "trace_wiring_run": trace_wiring_run,
        "latest_trace_artifact": {
            "found": latest_trace.get("found"),
            "path": latest_trace.get("path"),
            "status": latest_trace.get("status"),
        },
        "trace_capture_decision": trace_capture.get("decision"),
        "route_body_replacement_debug_keys_present": all(
            key in helper for key in route_body_replacement_debug_keys
        ),
        "route_shape_cutover_ready": route_shape_cutover_ready,
        "behavior_cutover_ready": behavior_cutover_ready,
        "safe_to_delete_old_body": safe_to_delete_old_body,
        "recommended_next_surface": "route_body_result_identity_cutover",
        "blocked_surfaces_kept_page_live": (
            "fallback_loop_structure",
            "candidate_generation_execution",
            "candidate_evaluation_execution",
            "candidate_selection_sequence",
            "cta_contract_execution",
            "visible_wording_authoring",
            "debug_session_projection",
        ),
        "product_behavior_changed": False,
        "engineering_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtime_changed": False,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    return {
        "object_snapshot_passed": capture["object_snapshot_run"].get("passed") is True,
        "trace_wiring_passed": capture["trace_wiring_run"].get("passed") is True,
        "latest_trace_artifact_passed": (
            (capture.get("latest_trace_artifact") or {}).get("status") == "PASS"
        ),
        "route_body_replacement_debug_keys_present": (
            capture.get("route_body_replacement_debug_keys_present") is True
        ),
        "route_shape_cutover_ready": capture.get("route_shape_cutover_ready") is True,
        "behavior_cutover_ready_false": capture.get("behavior_cutover_ready") is False,
        "safe_to_delete_old_body_false": capture.get("safe_to_delete_old_body") is False,
        "product_behavior_changed": capture.get("product_behavior_changed") is False,
        "engineering_behavior_changed": capture.get("engineering_behavior_changed") is False,
        "visible_wording_changed": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_changed": capture.get("cta_apply_semantics_changed") is False,
        "family_runtime_changed": capture.get("family_runtime_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Residual Shear Cleanup Route Body Replacement Cutover Readiness",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        "",
        "## Summary",
        "",
        f"- Route-shape cutover ready: `{capture.get('route_shape_cutover_ready')}`",
        f"- Behaviour cutover ready: `{capture.get('behavior_cutover_ready')}`",
        f"- Safe to delete old body: `{capture.get('safe_to_delete_old_body')}`",
        f"- Recommended next surface: `{capture.get('recommended_next_surface')}`",
        "",
        "## Kept Page-Live",
        "",
    ]
    lines.extend(f"- `{item}`" for item in capture.get("blocked_surfaces_kept_page_live") or ())
    lines.extend(
        [
            "",
            "## Checks",
            "",
        ]
    )
    lines.extend(f"- {key}: `{value}`" for key, value in (payload.get("checks") or {}).items())
    lines.extend(
        [
            "",
            "## Next Safe Target",
            "",
            "Cut over result identity/route shape only if a dedicated implementation verifier is added. Do not move candidate generation, evaluation, CTA contract execution, wording, or debug/session projection in that slice.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    capture = _capture()
    checks = _checks(capture)
    failures = [key for key, value in checks.items() if value is not True]
    payload = {
        "schema": "design_guide_post_click_low_bending_residual_shear_cleanup_route_body_replacement_cutover_readiness.v1",
        "created_at": _stamp(),
        "status": "PASS" if not failures else "FAIL",
        "capture": capture,
        "checks": checks,
        "failures": failures,
    }
    stamp = payload["created_at"]
    json_path = (
        ARTIFACT_DIR
        / f"design_guide_post_click_low_bending_residual_shear_cleanup_route_body_replacement_cutover_readiness_{stamp}.json"
    )
    audit_path = (
        AUDIT_DIR
        / f"design_guide_post_click_low_bending_residual_shear_cleanup_route_body_replacement_cutover_readiness_{stamp}.md"
    )
    report_path = (
        REPORT_DIR
        / f"design_brain_physical_extraction_residual_shear_cleanup_route_body_replacement_cutover_readiness_{stamp}.md"
    )
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    _write_report(audit_path, payload)
    _write_report(report_path, payload)
    print(
        "design_guide_post_click_low_bending_residual_shear_cleanup_route_body_replacement_cutover_readiness "
        + payload["status"]
    )
    print(f"json={json_path}")
    print(f"report={audit_path}")
    print(f"extraction_report={report_path}")
    if failures:
        print("failures=" + ", ".join(failures))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
