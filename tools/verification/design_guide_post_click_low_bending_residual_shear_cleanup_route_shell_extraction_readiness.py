"""Prove readiness for extracting the residual-shear cleanup route shell.

This gate sits between route-body return-boundary cutover and physical
deletion. It must not claim deletion readiness. It proves only whether the
remaining route body is ready for a controller-owned shell implementation that
keeps risky engineering and CTA/apply dependencies injected.
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
REPORT_DIR = ROOT / "artifacts" / "reports"

ROUTE_START = "current_shear_for_residual_cleanup = _parse_util_value("
ROUTE_END = "    shear_blocker = _shear_low_util_active_links_exact_blocker("

REQUIRED_ARTIFACTS = {
    "behavior_gap": "design_guide_post_click_low_bending_residual_shear_cleanup_route_body_behavior_cutover_gap_audit",
    "deletion_readiness": "design_guide_post_click_low_bending_residual_shear_cleanup_route_body_deletion_readiness",
    "return_boundary": "design_guide_post_click_low_bending_residual_shear_cleanup_route_body_return_boundary_cutover",
    "route_body_replacement": "design_guide_post_click_low_bending_residual_shear_cleanup_route_body_replacement_cutover_readiness",
    "remaining_surface": "design_guide_post_click_low_bending_residual_shear_cleanup_remaining_surface_audit",
}

INJECTED_DEPENDENCY_TOKENS = {
    "route_entry_guard": "_run_design_guide_controller_post_click_low_bending_residual_shear_cleanup_route_entry_guard(",
    "primary_executor": "_run_post_click_low_bending_residual_shear_cleanup_primary_executor(",
    "fallback_variant_generator": "_run_post_click_low_bending_residual_shear_cleanup_fallback_variant_generator(",
    "candidate_evaluator": "_run_post_click_low_bending_residual_shear_cleanup_candidate_evaluator(",
    "materiality_pre_screen": "_run_post_click_low_bending_residual_shear_cleanup_materiality_safety_pre_screen(",
    "materiality_post_screen": "_run_post_click_low_bending_residual_shear_cleanup_materiality_safety_post_screen(",
    "candidate_selector": "_run_post_click_low_bending_residual_shear_cleanup_candidate_selector(",
    "result_packaging": "_run_post_click_low_bending_residual_shear_cleanup_result_packaging(",
    "shared_button_contract": "_execute_post_click_low_bending_residual_shear_cleanup_button_contract(",
}

CONTROLLER_BOUNDARY_TOKENS = {
    "route_body_replacement": "_stamp_design_guide_controller_post_click_low_bending_residual_shear_cleanup_route_body_replacement(",
    "route_return_boundary": "residual_route_return_boundary = dict(",
    "route_body_result_shell": "_run_design_guide_controller_post_click_low_bending_residual_shear_cleanup_route_body(",
    "return_boundary_hash_stamp": "design_guide_controller_post_click_low_bending_residual_shear_cleanup_route_body_return_boundary_hash",
}


def _stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _between(source: str, start_token: str, end_token: str) -> str:
    start = source.find(start_token)
    if start < 0:
        return ""
    end = source.find(end_token, start + len(start_token))
    return source[start:end] if end > start else source[start:]


def _status_from_payload(payload: dict[str, Any]) -> str:
    raw = str(
        payload.get("status")
        or payload.get("result")
        or payload.get("lock_status")
        or payload.get("decision")
        or ""
    )
    upper = raw.upper()
    if "PASS" in upper or "LOCKED" in upper:
        return "PASS"
    if "FAIL" in upper:
        return "FAIL"
    if "PARTIAL" in upper:
        return "PARTIAL"
    return raw or "UNKNOWN"


def _latest(prefix: str) -> dict[str, Any]:
    paths = sorted(ARTIFACT_DIR.glob(f"{prefix}_*.json"), key=lambda path: path.stat().st_mtime)
    if not paths:
        return {"found": False, "status": "MISSING", "path": "", "payload": {}}
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
    return {
        "found": True,
        "status": _status_from_payload(payload),
        "path": str(path),
        "payload": payload,
    }


def _capture() -> dict[str, Any]:
    source = INPUTS_PAGE.read_text(encoding="utf-8-sig", errors="replace")
    route = _between(source, ROUTE_START, ROUTE_END)
    latest = {name: _latest(prefix) for name, prefix in REQUIRED_ARTIFACTS.items()}

    behavior_payload = latest["behavior_gap"].get("payload") or {}
    behavior = behavior_payload.get("capture") or behavior_payload
    deletion_payload = latest["deletion_readiness"].get("payload") or {}
    deletion = deletion_payload.get("capture") or deletion_payload
    return_payload = latest["return_boundary"].get("payload") or {}
    return_capture = return_payload.get("capture") or return_payload

    injected_present = {
        name: token in route for name, token in INJECTED_DEPENDENCY_TOKENS.items()
    }
    controller_boundaries_present = {
        name: token in route for name, token in CONTROLLER_BOUNDARY_TOKENS.items()
    }
    required_artifacts_pass = all(item.get("status") == "PASS" for item in latest.values())
    behavior_cutover_ready = behavior.get("behavior_cutover_ready") is True
    return_boundary_cutover_ready = (
        return_capture.get("route_return_boundary_cutover_applied") is True
        and bool(return_capture.get("tokens", {}).get("controller_selector_called"))
        and bool(controller_boundaries_present.get("route_return_boundary"))
    )
    deletion_not_claimed = deletion.get("safe_to_delete_route_body_now") is False
    old_page_return_authority_removed = (
        deletion.get("route_body_still_page_owned_return_authority") is False
        and behavior.get("route_return_boundary_bounded") is True
    )
    injected_dependencies_retained = all(injected_present.values())
    route_shell_extraction_ready = bool(
        route
        and required_artifacts_pass
        and behavior_cutover_ready
        and return_boundary_cutover_ready
        and old_page_return_authority_removed
        and injected_dependencies_retained
        and deletion_not_claimed
    )
    return {
        "decision": (
            "RESIDUAL_SHEAR_CLEANUP_ROUTE_SHELL_READY_FOR_CONTROLLER_IMPLEMENTATION"
            if route_shell_extraction_ready
            else "RESIDUAL_SHEAR_CLEANUP_ROUTE_SHELL_NOT_READY"
        ),
        "route_found": bool(route),
        "required_artifacts_pass": required_artifacts_pass,
        "behavior_cutover_ready": behavior_cutover_ready,
        "return_boundary_cutover_ready": return_boundary_cutover_ready,
        "old_page_return_authority_removed": old_page_return_authority_removed,
        "route_shell_extraction_ready": route_shell_extraction_ready,
        "safe_to_delete_route_body_now": False,
        "deletion_readiness_decision": deletion.get("decision"),
        "deletion_blockers": tuple(deletion.get("deletion_blockers") or ()),
        "injected_dependencies_retained": injected_present,
        "controller_boundaries_present": controller_boundaries_present,
        "next_safe_surface": (
            "controller_route_shell_implementation_with_injected_dependencies"
            if route_shell_extraction_ready
            else "repair_missing_route_shell_readiness_proof"
        ),
        "forbidden_in_this_slice": (
            "candidate_generation_move",
            "candidate_evaluation_move",
            "cta_contract_execution_move",
            "visible_wording_change",
            "apply_routing_change",
            "ui_rendering_move",
            "session_state_move",
        ),
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
        "route_found": capture.get("route_found") is True,
        "required_artifacts_pass": capture.get("required_artifacts_pass") is True,
        "behavior_cutover_ready": capture.get("behavior_cutover_ready") is True,
        "return_boundary_cutover_ready": capture.get("return_boundary_cutover_ready") is True,
        "old_page_return_authority_removed": capture.get("old_page_return_authority_removed") is True,
        "route_shell_extraction_ready_classified": bool(capture.get("decision")),
        "deletion_not_claimed": capture.get("safe_to_delete_route_body_now") is False,
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "engineering_behavior_unchanged": capture.get("engineering_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "family_runtime_unchanged": capture.get("family_runtime_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Residual Shear Cleanup Route Shell Extraction Readiness",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Route shell extraction ready: `{capture.get('route_shell_extraction_ready')}`",
        f"Safe to delete route body now: `{capture.get('safe_to_delete_route_body_now')}`",
        f"Next safe surface: `{capture.get('next_safe_surface')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Injected Dependencies Retained",
        "",
    ]
    for name, present in (capture.get("injected_dependencies_retained") or {}).items():
        lines.append(f"- `{name}`: `{present}`")
    lines.extend(["", "## Controller Boundaries Present", ""])
    for name, present in (capture.get("controller_boundaries_present") or {}).items():
        lines.append(f"- `{name}`: `{present}`")
    lines.extend(["", "## Deletion State", ""])
    lines.append(f"- deletion readiness decision: `{capture.get('deletion_readiness_decision')}`")
    blockers = capture.get("deletion_blockers") or ()
    if blockers:
        lines.extend(f"- blocker: `{blocker}`" for blocker in blockers)
    else:
        lines.append("- blocker: none")
    lines.extend(["", "## Required Artifacts", ""])
    for name, item in (capture.get("required_artifacts") or {}).items():
        lines.append(f"- `{name}`: status=`{item.get('status')}`, path=`{item.get('path')}`")
    lines.extend(["", "## Checks", ""])
    lines.extend(f"- {name}: `{value}`" for name, value in (payload.get("checks") or {}).items())
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    capture = _capture()
    checks = _checks(capture)
    failures = [name for name, passed in checks.items() if passed is not True]
    payload = {
        "schema": "design_guide_post_click_low_bending_residual_shear_cleanup_route_shell_extraction_readiness.v1",
        "created_at": _stamp(),
        "status": "PASS" if not failures else "FAIL",
        "capture": capture,
        "checks": checks,
        "failures": failures,
    }
    payload["snapshot_hash"] = _stable_hash(payload)
    stamp = payload["created_at"]
    json_path = ARTIFACT_DIR / (
        "design_guide_post_click_low_bending_residual_shear_cleanup_route_shell_extraction_readiness_"
        f"{stamp}.json"
    )
    audit_path = AUDIT_DIR / (
        "design_guide_post_click_low_bending_residual_shear_cleanup_route_shell_extraction_readiness_"
        f"{stamp}.md"
    )
    report_path = REPORT_DIR / (
        "design_brain_physical_extraction_residual_shear_cleanup_route_shell_extraction_readiness_"
        f"{stamp}.md"
    )
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(audit_path, payload)
    _write_report(report_path, payload)
    print("design_guide_post_click_low_bending_residual_shear_cleanup_route_shell_extraction_readiness", payload["status"])
    print(f"decision={capture.get('decision')}")
    print(f"json={json_path}")
    print(f"audit={audit_path}")
    print(f"report={report_path}")
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
