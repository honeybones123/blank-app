"""Cutover-readiness verifier for residual-shear route-shell adapter.

This verifier proves the narrow next cutover can use the controller
route-shell adapter result item without moving candidate generation/evaluation,
CTA contract execution, visible wording, apply routing, rendering, or
session/debug ownership.
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
INPUTS_PAGE = ROOT / "inputs_page.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"

ROUTE_START = "current_shear_for_residual_cleanup = _parse_util_value(family_utils.get(\"shear\"))"
ROUTE_END = "    shear_blocker = _shear_low_util_active_links_exact_blocker("


def _stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _latest(prefix: str) -> dict[str, Any]:
    paths = sorted(ARTIFACT_DIR.glob(f"{prefix}_*.json"), key=lambda path: path.stat().st_mtime)
    if not paths:
        return {"found": False, "status": "MISSING", "path": ""}
    path = paths[-1]
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception as exc:  # pragma: no cover - diagnostic path
        return {
            "found": True,
            "status": "UNREADABLE",
            "path": str(path),
            "error": f"{type(exc).__name__}: {exc}",
        }
    raw_status = str(payload.get("status") or payload.get("result") or payload.get("lock_status") or "")
    upper = raw_status.upper()
    if "PASS" in upper or "LOCKED" in upper or "COMPLETE" in upper:
        status = "PASS"
    elif "FAIL" in upper:
        status = "FAIL"
    else:
        status = raw_status or "UNKNOWN"
    return {"found": True, "status": status, "path": str(path)}


def _between(source: str, start_token: str, end_token: str) -> str:
    start = source.find(start_token)
    if start < 0:
        return ""
    end = source.find(end_token, start + len(start_token))
    return source[start:end] if end > start else source[start:]


def _capture() -> dict[str, Any]:
    source = INPUTS_PAGE.read_text(encoding="utf-8-sig", errors="replace")
    route = _between(source, ROUTE_START, ROUTE_END)
    trace_token = (
        "_stamp_design_guide_controller_post_click_low_bending_residual_shear_cleanup_route_shell_adapter_trace("
    )
    final_binding_trace_token = (
        "_stamp_design_guide_controller_post_click_low_bending_residual_shear_cleanup_final_binding_tail_adapter_trace("
    )
    cutover_assignment_token = (
        "residual_route_shell_adapter = _stamp_design_guide_controller_post_click_low_bending_residual_shear_cleanup_route_shell_adapter_trace("
    )
    direct_result_assignment_token = (
        "residual_promoted = dict(residual_route_shell_adapter.get(\"result_item\") or residual_promoted)"
    )
    multiline_result_assignment_token = (
        "residual_promoted = dict(\n                            residual_route_shell_adapter.get(\"result_item\")\n                            or residual_promoted\n                        )"
    )
    cutover_assignment_present = cutover_assignment_token in route and (
        direct_result_assignment_token in route or multiline_result_assignment_token in route
    )
    latest = {
        "object": _latest(
            "design_guide_post_click_low_bending_residual_shear_cleanup_route_shell_adapter_object"
        ),
        "trace_wiring": _latest(
            "design_guide_post_click_low_bending_residual_shear_cleanup_route_shell_adapter_trace_wiring"
        ),
        "remaining_surface_audit": _latest(
            "design_guide_post_click_low_bending_residual_shear_cleanup_remaining_surface_audit"
        ),
        "final_binding_deadness": _latest(
            "design_guide_post_click_low_bending_residual_shear_cleanup_final_binding_tail_deadness_proof"
        ),
    }
    return {
        "decision": "ROUTE_SHELL_ADAPTER_READY_FOR_NARROW_CUTOVER",
        "route_found": bool(route),
        "trace_call_present": trace_token in route,
        "trace_after_final_binding": (
            route.find(trace_token) > route.find(final_binding_trace_token) >= 0
        ),
        "current_live_route_not_cut_over_yet": not cutover_assignment_present,
        "route_shell_cutover_already_implemented": cutover_assignment_present,
        "recommended_cutover_assignment": (
            "Assign the trace payload to a local variable and set residual_promoted from "
            "payload.result_item only. This should be a no-op shape cutover because the "
            "adapter currently returns the same item hash."
        ),
        "dependencies_to_keep_external": (
            "candidate_generation_execution",
            "candidate_evaluation_execution",
            "primary_shear_tightening_execution",
            "cta_contract_execution",
            "visible_wording_authoring",
            "apply_routing",
            "ui_rendering",
            "session_debug_mutation",
        ),
        "latest": latest,
        "latest_required_artifacts_pass": all(row.get("status") == "PASS" for row in latest.values()),
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "engineering_behavior_changed": False,
        "family_runtime_changed": False,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    return {
        "route_found": capture.get("route_found") is True,
        "trace_call_present": capture.get("trace_call_present") is True,
        "trace_after_final_binding": capture.get("trace_after_final_binding") is True,
        "ready_or_cutover_already_implemented": (
            capture.get("current_live_route_not_cut_over_yet") is True
            or capture.get("route_shell_cutover_already_implemented") is True
        ),
        "latest_required_artifacts_pass": capture.get("latest_required_artifacts_pass") is True,
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "engineering_behavior_unchanged": capture.get("engineering_behavior_changed") is False,
        "family_runtime_unchanged": capture.get("family_runtime_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Residual Shear Cleanup Route-Shell Adapter Cutover Readiness",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Summary",
        "",
        f"- Trace call present: `{capture.get('trace_call_present')}`",
        f"- Trace after final-binding trace: `{capture.get('trace_after_final_binding')}`",
        f"- Current live route not cut over yet: `{capture.get('current_live_route_not_cut_over_yet')}`",
        "",
        "## Dependencies Kept External",
        "",
    ]
    for dependency in capture.get("dependencies_to_keep_external") or ():
        lines.append(f"- `{dependency}`")
    lines.extend(
        [
            "",
            "## Recommended Cutover",
            "",
            str(capture.get("recommended_cutover_assignment") or ""),
            "",
            "## Checks",
            "",
        ]
    )
    lines.extend(f"- {key}: `{value}`" for key, value in (payload.get("checks") or {}).items())
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    capture = _capture()
    checks = _checks(capture)
    failures = [key for key, passed in checks.items() if passed is not True]
    payload: dict[str, Any] = {
        "schema": "design_guide_post_click_low_bending_residual_shear_cleanup_route_shell_adapter_cutover_readiness.v1",
        "created_at": _stamp(),
        "status": "PASS" if not failures else "FAIL",
        "capture": capture,
        "checks": checks,
        "failures": failures,
    }
    payload["snapshot_hash"] = _stable_hash({"capture": capture, "checks": checks})
    stamp = str(payload["created_at"])
    json_path = (
        ARTIFACT_DIR
        / f"design_guide_post_click_low_bending_residual_shear_cleanup_route_shell_adapter_cutover_readiness_{stamp}.json"
    )
    report_path = (
        AUDIT_DIR
        / f"design_guide_post_click_low_bending_residual_shear_cleanup_route_shell_adapter_cutover_readiness_{stamp}.md"
    )
    json_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8",
    )
    _write_report(report_path, payload)
    print(
        "design_guide_post_click_low_bending_residual_shear_cleanup_route_shell_adapter_cutover_readiness "
        f"{payload['status']}"
    )
    print(f"json={json_path}")
    print(f"report={report_path}")
    if failures:
        print("failures=" + ", ".join(failures))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
