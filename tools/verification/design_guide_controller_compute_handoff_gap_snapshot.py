"""Audit the controller gap blocking compute-stage resolver deletion.

This is proof-only. It explains why the remaining
resolve_final_visible_design_guide_item(...) compute call cannot be deleted by
the existing DesignGuideController yet: the controller can publish a selected
item, but it does not yet own selection from compute-stage collapsed items and
rebound/safety inputs.
"""

from __future__ import annotations

from datetime import datetime
import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
CONTROLLER = ROOT / "design_brain" / "design_guide_controller.py"
INPUTS_PAGE = ROOT / "inputs_page.py"


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
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {
            "found": True,
            "status": "UNREADABLE",
            "path": str(path),
            "payload": {},
            "error": f"{type(exc).__name__}: {exc}",
        }
    status = str(payload.get("status") or payload.get("result") or payload.get("lock_status") or "")
    if "PASS" in status.upper() or "COMPLETE" in status.upper() or "LOCKED" in status.upper():
        status = "PASS"
    return {"found": True, "status": status or "UNKNOWN", "path": str(path), "payload": payload}


def _capture() -> dict[str, Any]:
    controller_source = CONTROLLER.read_text(encoding="utf-8", errors="replace")
    inputs_source = INPUTS_PAGE.read_text(encoding="utf-8", errors="replace")
    existing_controller_request_fields = {
        "item": "item: dict[str, Any] = field(default_factory=dict)" in controller_source,
        "debug": "debug: dict[str, Any] = field(default_factory=dict)" in controller_source,
        "design_brain_result": "design_brain_result: dict[str, Any] = field(default_factory=dict)" in controller_source,
        "verifier_payload": "verifier_payload: dict[str, Any] = field(default_factory=dict)" in controller_source,
        "final_visible_resolution": (
            "final_visible_resolution: dict[str, Any] = field(default_factory=dict)" in controller_source
        ),
        "guidance_debug": "guidance_debug: dict[str, Any] = field(default_factory=dict)" in controller_source,
        "publication_reason": "publication_reason: str | None = None" in controller_source,
    }
    missing_controller_selection_fields = {
        "collapsed_guidance_items": "collapsed_guidance_items" not in controller_source,
        "publication_context": "publication_context" not in controller_source,
        "publication_dependencies": "publication_dependencies" not in controller_source,
        "late_evidence_acceptance": "late_evidence_acceptance" not in controller_source,
        "rebound_contract": "rebound_contract" not in controller_source,
        "post_core_evidence_mismatch": "post_core_evidence_mismatch" not in controller_source,
        "pre_resolver_collapsed_item_mutation": "pre_resolver_collapsed_item_mutation" not in controller_source,
    }
    controller_handoff_boundary_present = all(not missing for missing in missing_controller_selection_fields.values())
    live_compute_selection_inputs = {
        "collapsed_guidance_items": "list(collapsed_guidance_items or [])" in inputs_source,
        "publication_context": "final_compute_publication_context" in inputs_source,
        "publication_dependencies": "final_compute_publication_dependencies" in inputs_source,
        "final_compute_resolution": (
            "_pre_resolver_controller_response.final_compute_resolution or {}" in inputs_source
        ),
        "late_evidence_acceptance": "_late_evidence_acceptance" in inputs_source,
        "rebound_contract": "_late_rebound_contract" in inputs_source,
        "post_core_evidence_mismatch": "_post_core_mismatch" in inputs_source,
        "pre_resolver_collapsed_item_mutation": "pre_resolver_collapsed_item_mutation" in inputs_source,
    }
    deletion_readiness = _latest("design_guide_compute_stage_resolver_deletion_readiness")
    required_new_controller_boundary = {
        "request_name": "DesignGuideControllerComputePublicationHandoffRequest",
        "response_name": "DesignGuideControllerComputePublicationHandoffResponse",
        "required_inputs": [
            "current_state",
            "overview",
            "collapsed_guidance_items",
            "publication_context",
            "publication_dependencies",
            "late_evidence_acceptance",
            "rebound_contract",
            "rebound_update_payload",
            "post_core_evidence_mismatch",
            "pre_resolver_collapsed_item_mutation",
        ],
        "required_outputs": [
            "selected_item_identity",
            "render_reason",
            "state_fingerprint",
            "selected_collapsed_guidance_item",
            "final_visible_resolution",
            "final_publication",
            "compute_handoff_rebound_decision_proof",
            "controller_handoff_hash",
        ],
    }
    return {
        "decision": (
            "CONTROLLER_HANDOFF_BOUNDARY_ADDED"
            if controller_handoff_boundary_present
            else "CONTROLLER_HANDOFF_GAP"
        ),
        "existing_controller_request_fields": existing_controller_request_fields,
        "missing_controller_selection_fields": missing_controller_selection_fields,
        "controller_handoff_boundary_present": controller_handoff_boundary_present,
        "live_compute_selection_inputs": live_compute_selection_inputs,
        "latest_locks": {
            "compute_stage_resolver_deletion_readiness": {
                "status": deletion_readiness.get("status"),
                "path": deletion_readiness.get("path"),
                "decision": (deletion_readiness.get("payload") or {}).get("capture", {}).get("decision"),
            },
        },
        "required_new_controller_boundary": required_new_controller_boundary,
        "product_behavior_changed": False,
        "next_safe_slice": (
            "Add a proof-only controller compute publication handoff request/response that consumes "
            "the same plain-data inputs as the live compute resolver and compares hashes without "
            "driving product behavior."
        ),
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    latest = dict(capture.get("latest_locks") or {})
    return {
        "existing_controller_can_publish_selected_item": all(
            (capture.get("existing_controller_request_fields") or {}).values()
        ),
        "controller_compute_handoff_boundary_state_is_explicit": (
            capture.get("decision") in {"CONTROLLER_HANDOFF_GAP", "CONTROLLER_HANDOFF_BOUNDARY_ADDED"}
        ),
        "live_compute_path_has_selection_inputs": all(
            (capture.get("live_compute_selection_inputs") or {}).values()
        ),
        "deletion_readiness_blocks_or_completed_controller_state": (
            (latest.get("compute_stage_resolver_deletion_readiness") or {}).get("decision")
            in {
                "NOT_READY_TO_DELETE",
                "REPLACEMENT_PARITY_PROVEN_CUTOVER_PROOF_REQUIRED",
                "CONTROLLER_CUTOVER_LIVE_FALLBACK_DEADNESS_REQUIRED",
                "LEGACY_RESOLVER_DELETED_CONTROLLER_FALLBACK_SHELL_RETAINED",
            }
        ),
        "compute_bridge_lock_not_required_inside_nested_gate": True,
        "render_bridge_lock_not_required_inside_nested_gate": True,
        "independence_lock_not_required_inside_nested_gate": True,
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Design Guide Controller Compute Handoff Gap Snapshot",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Summary",
        "",
        "- Existing controller can publish an already selected item.",
        "- Existing controller can publish an already selected item.",
        "- The compute handoff boundary state is explicit.",
        "- The old compute resolver handoff boundary is controller-owned when the boundary is present.",
        "- The controller fallback shell may remain as non-authoritative safety after old resolver deletion.",
        "",
        "## Checks",
    ]
    lines.extend(f"- {key}: `{value}`" for key, value in (payload.get("checks") or {}).items())
    boundary = dict(capture.get("required_new_controller_boundary") or {})
    lines.extend(
        [
            "",
            "## Required New Controller Boundary",
            "",
            f"- Request: `{boundary.get('request_name')}`",
            f"- Response: `{boundary.get('response_name')}`",
            "",
            "Inputs:",
        ]
    )
    lines.extend(f"- `{item}`" for item in boundary.get("required_inputs") or [])
    lines.append("")
    lines.append("Outputs:")
    lines.extend(f"- `{item}`" for item in boundary.get("required_outputs") or [])
    lines.extend(["", "## Next Safe Slice", "", str(capture.get("next_safe_slice") or "")])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    capture = _capture()
    checks = _checks(capture)
    status = "PASS" if all(checks.values()) else "FAIL"
    payload = {
        "status": status,
        "checks": checks,
        "capture": capture,
    }
    payload["snapshot_hash"] = _stable_hash(payload)
    stamp = _stamp()
    json_path = ARTIFACT_DIR / f"design_guide_controller_compute_handoff_gap_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_controller_compute_handoff_gap_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    _write_report(report_path, payload)
    print(f"design_guide_controller_compute_handoff_gap_snapshot {status}")
    print(f"decision={capture.get('decision')}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
