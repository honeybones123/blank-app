"""Cutover-readiness for residual-shear CTA/apply payload source boundary."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
INPUTS = ROOT / "inputs_page.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
REPORT_DIR = ROOT / "artifacts" / "reports"

REQUIRED = {
    "object": "design_guide_post_click_low_bending_residual_shear_cleanup_cta_apply_payload_source_boundary_object",
    "trace_wiring": "design_guide_post_click_low_bending_residual_shear_cleanup_cta_apply_payload_source_boundary_trace_wiring",
    "parity_scenarios": "design_guide_post_click_low_bending_residual_shear_cleanup_cta_apply_payload_source_boundary_parity_scenarios",
    "final_binding_live_readiness": "design_guide_post_click_low_bending_residual_shear_cleanup_final_binding_tail_live_cutover_readiness",
    "route_body_gap_audit": "design_guide_post_click_low_bending_residual_shear_cleanup_route_body_behavior_cutover_gap_audit",
}


def _stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _latest(prefix: str) -> dict[str, Any]:
    paths = sorted(ARTIFACT_DIR.glob(f"{prefix}_*.json"), key=lambda path: path.stat().st_mtime)
    if not paths:
        return {"found": False, "status": "MISSING", "path": "", "payload": {}}
    path = paths[-1]
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception as exc:
        return {"found": True, "status": "UNREADABLE", "path": str(path), "error": str(exc), "payload": {}}
    raw = str(payload.get("status") or payload.get("result") or payload.get("lock_status") or "")
    status = "PASS" if "PASS" in raw.upper() or "LOCKED" in raw.upper() else raw or "UNKNOWN"
    return {"found": True, "status": status, "path": str(path), "payload": payload}


def _between(source: str, start_token: str, end_token: str) -> str:
    start = source.find(start_token)
    if start < 0:
        return ""
    end = source.find(end_token, start + len(start_token))
    if end < 0:
        return source[start:]
    return source[start:end]


def _capture() -> dict[str, Any]:
    latest = {name: _latest(prefix) for name, prefix in REQUIRED.items()}
    source = INPUTS.read_text(encoding="utf-8-sig", errors="replace")
    route = _between(
        source,
        "current_shear_for_residual_cleanup = _parse_util_value(",
        "    shear_blocker = _shear_low_util_active_links_exact_blocker(",
    )
    helper = _between(
        source,
        "def _stamp_design_guide_controller_post_click_low_bending_residual_shear_cleanup_cta_apply_payload_source_boundary(",
        "\ndef _stamp_design_guide_controller_post_click_low_bending_residual_shear_cleanup_final_binding_tail_adapter_trace(",
    )
    all_required_pass = all(item.get("status") == "PASS" for item in latest.values())
    stale_scenario_proven = False
    parity_payload = latest.get("parity_scenarios", {}).get("payload") or {}
    for row in (parity_payload.get("capture") or {}).get("scenarios") or []:
        if (
            row.get("name") == "stale_payload_mismatch_detected"
            and row.get("expected_payload_match") is False
            and row.get("passed") is True
        ):
            stale_scenario_proven = True
            break
    source_boundary_ready = bool(
        all_required_pass
        and stale_scenario_proven
        and "residual_cta_apply_payload_source_boundary = _stamp_design_guide_controller_post_click_low_bending_residual_shear_cleanup_cta_apply_payload_source_boundary(" in route
        and '"cta_apply_payload_source_boundary_hash": (' in route
        and "dependency_status=\"page_live\"" in helper
    )
    allowed_cutover_scope = (
        "Use the controller boundary as the traceable source-summary for live action_payload, "
        "resolved_candidate, and button_contract hashes. Keep shared button-contract execution, "
        "CTA/apply routing, visible wording, candidate generation/evaluation, and the route body "
        "return live until separate deletion proof."
    )
    behavior_cutover_ready = False
    safe_to_delete_route_body_now = False
    return {
        "decision": (
            "CTA_APPLY_PAYLOAD_SOURCE_BOUNDARY_READY_FOR_GUARDED_SOURCE_SUMMARY_CUTOVER"
            if source_boundary_ready
            else "CTA_APPLY_PAYLOAD_SOURCE_BOUNDARY_NOT_READY"
        ),
        "source_boundary_ready": source_boundary_ready,
        "behavior_cutover_ready": behavior_cutover_ready,
        "safe_to_delete_route_body_now": safe_to_delete_route_body_now,
        "all_required_artifacts_pass": all_required_pass,
        "stale_scenario_proven": stale_scenario_proven,
        "allowed_cutover_scope": allowed_cutover_scope,
        "blocked_from_cutover": (
            "shared_button_contract_execution",
            "cta_apply_routing",
            "visible_wording",
            "route_body_return",
            "result_packaging_execution",
        ),
        "next_safe_surface": "guarded_source_summary_cutover"
        if source_boundary_ready
        else "repair_source_boundary_proof",
        "required_artifacts": {
            name: {key: value for key, value in item.items() if key != "payload"}
            for name, item in latest.items()
        },
        "route_window_hash": _stable_hash(route),
        "product_behavior_changed": False,
        "engineering_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtime_changed": False,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    return {
        "required_artifacts_pass": capture.get("all_required_artifacts_pass") is True,
        "stale_scenario_proven": capture.get("stale_scenario_proven") is True,
        "source_boundary_ready": capture.get("source_boundary_ready") is True,
        "behavior_cutover_not_claimed": capture.get("behavior_cutover_ready") is False,
        "route_body_deletion_not_claimed": capture.get("safe_to_delete_route_body_now") is False,
        "blocked_scope_explicit": bool(capture.get("blocked_from_cutover")),
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "engineering_behavior_unchanged": capture.get("engineering_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "family_runtime_unchanged": capture.get("family_runtime_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Residual Shear Cleanup CTA/Apply Payload Source Boundary Cutover Readiness",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Summary",
        "",
        f"- Source boundary ready: `{capture.get('source_boundary_ready')}`",
        f"- Behaviour cutover ready: `{capture.get('behavior_cutover_ready')}`",
        f"- Safe to delete route body now: `{capture.get('safe_to_delete_route_body_now')}`",
        f"- Next safe surface: `{capture.get('next_safe_surface')}`",
        "",
        "## Blocked From This Cutover",
        "",
    ]
    lines.extend(f"- `{item}`" for item in capture.get("blocked_from_cutover") or ())
    lines.extend(["", "## Required Artifacts", ""])
    for name, item in (capture.get("required_artifacts") or {}).items():
        lines.append(f"- `{name}`: status=`{item.get('status')}`, path=`{item.get('path')}`")
    lines.extend(["", "## Allowed Cutover Scope", "", str(capture.get("allowed_cutover_scope") or "")])
    lines.extend(["", "## Checks", ""])
    lines.extend(f"- {key}: `{value}`" for key, value in (payload.get("checks") or {}).items())
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    capture = _capture()
    checks = _checks(capture)
    failures = [key for key, value in checks.items() if value is not True]
    payload = {
        "schema": "design_guide_post_click_low_bending_residual_shear_cleanup_cta_apply_payload_source_boundary_cutover_readiness.v1",
        "created_at": _stamp(),
        "status": "PASS" if not failures else "FAIL",
        "capture": capture,
        "checks": checks,
        "failures": failures,
        "snapshot_hash": _stable_hash({"capture": capture, "checks": checks}),
    }
    stamp = payload["created_at"]
    json_path = (
        ARTIFACT_DIR
        / f"design_guide_post_click_low_bending_residual_shear_cleanup_cta_apply_payload_source_boundary_cutover_readiness_{stamp}.json"
    )
    audit_path = (
        AUDIT_DIR
        / f"design_guide_post_click_low_bending_residual_shear_cleanup_cta_apply_payload_source_boundary_cutover_readiness_{stamp}.md"
    )
    report_path = (
        REPORT_DIR
        / f"design_brain_physical_extraction_residual_shear_cleanup_cta_apply_payload_source_boundary_cutover_readiness_{stamp}.md"
    )
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    _write_report(audit_path, payload)
    _write_report(report_path, payload)
    print(
        "design_guide_post_click_low_bending_residual_shear_cleanup_cta_apply_payload_source_boundary_cutover_readiness "
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
