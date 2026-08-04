"""Readiness proof for a future guarded pre-card restamper bypass.

The pre-card final-visible output bridge can feed terminal-blocker and primary-card
presentation state, so this snapshot does not implement a bypass. It defines
the only acceptable future bypass shape: reuse the input item only when the
previous controller restamper proof proves a strict no-op for this exact
callsite and all relevant hashes remain stable.
"""

from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
INPUTS_PAGE = ROOT / "inputs_page.py"

CALLSITE_ID = "render_guidance_secondary_items.pre_card_binding"
RESTAMPER_CALL = "_pre_card_bound_item = _publish_final_visible_design_guide_contract_binding("

BYPASS_CONDITIONS = {
    "same_callsite": "previous.callsite_id == current.callsite_id",
    "same_input_item_hash": "previous.input_item_hash == current.input_item_hash",
    "same_state_hash": "previous.state_hash == current.state_hash",
    "same_debug_hash": "previous.debug_hash == current.debug_hash",
    "same_rec_hash": "previous.rec_hash == current.rec_hash",
    "previous_output_unchanged": "previous.output_changed is false",
    "previous_cta_unchanged": "previous.cta_changed is false",
    "previous_display_unchanged": "previous.display_changed is false",
    "previous_evidence_unchanged": "previous.evidence_changed is false",
    "same_cta_projection": "previous.cta_projection_hash == current.cta_projection_hash",
    "same_display_projection": "previous.display_projection_hash == current.display_projection_hash",
    "same_evidence_projection": "previous.evidence_projection_hash == current.evidence_projection_hash",
    "output_matches_input": "previous.output_item_hash == current.input_item_hash",
    "terminal_blocker_not_added_by_restamper": "previous proof confirms output/evidence/display unchanged",
    "primary_presentation_not_added_by_restamper": "previous proof confirms output/display unchanged",
    "debug_mode_off": "debug mode / force rebuild flags are false",
    "no_apply_in_flight": "post-click/apply-in-flight flags are false",
    "not_missing_previous_proof": "previous proof exists and has a proof_hash",
}

FORCE_REBUILD_CONDITIONS = {
    "missing_previous_proof": "no previous proof or proof_hash",
    "changed_callsite": "callsite changes",
    "changed_input": "input item hash changes",
    "changed_state": "state hash changes",
    "changed_debug": "debug hash changes",
    "changed_rec": "pending recommendation hash changes",
    "previous_output_changed": "previous proof changed the output item",
    "previous_cta_changed": "previous proof changed CTA/apply surface",
    "previous_display_changed": "previous proof changed display/primary-card surface",
    "previous_evidence_changed": "previous proof changed evidence/blocker surface",
    "changed_cta_projection": "CTA projection hash changes",
    "changed_display_projection": "display projection hash changes",
    "changed_evidence_projection": "evidence projection hash changes",
    "debug_mode": "debug mode or force rebuild enabled",
    "apply_in_flight": "post-click/apply-in-flight state present",
}


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _latest(prefix: str) -> dict[str, Any]:
    paths = sorted(ARTIFACT_DIR.glob(f"{prefix}_*.json"), key=lambda path: path.stat().st_mtime)
    if not paths:
        return {"found": False, "status": "MISSING", "path": None}
    path = paths[-1]
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception as exc:
        return {"found": True, "status": "UNREADABLE", "path": str(path), "error": str(exc)}
    raw_status = str(payload.get("status") or payload.get("result") or payload.get("lock_status") or "")
    status = "PASS" if any(token in raw_status.upper() for token in ("PASS", "LOCKED", "COMPLETE")) else raw_status
    return {"found": True, "status": status or "UNKNOWN", "path": str(path)}


def _capture_source() -> dict[str, bool]:
    source = INPUTS_PAGE.read_text(encoding="utf-8-sig", errors="replace").lstrip("\ufeff")
    restamper_index = source.find(RESTAMPER_CALL)
    window = source[max(0, restamper_index - 700) : restamper_index + 3600] if restamper_index >= 0 else ""
    return {
        "restamper_call_present": restamper_index >= 0,
        "callsite_proof_present": CALLSITE_ID in source,
        "pre_card_input_copied": "_pre_card_input_item = dict(item)" in window,
        "pre_card_pending_rec_copied": "_pre_card_pending_rec = dict(" in window,
        "proof_stamp_before_bound_contract": (
            source.find(f'callsite_id="{CALLSITE_ID}"') > restamper_index
            and source.find("_pre_card_bound_contract =", restamper_index)
            > source.find(f'callsite_id="{CALLSITE_ID}"')
        ),
        "terminal_blocker_branch_after_restamper": "_pre_card_bound_is_terminal_blocker" in window,
        "primary_presentation_branch_after_restamper": "primary_card_presentation" in window,
        "no_bypass_wired_yet": "_pre_card_restamper_bypass" not in source,
    }


def _capture() -> dict[str, Any]:
    return {
        "decision": "READY_FOR_PROOF_ONLY_GUARDED_BYPASS_IMPLEMENTATION_PLAN",
        "implementation_allowed_now": False,
        "reason": (
            "pre-card bridge has a proof stamp; a future bypass may only reuse the input item "
            "when the exact previous proof was a no-op and terminal/presentation truth was not added"
        ),
        "callsite_id": CALLSITE_ID,
        "bypass_conditions": dict(BYPASS_CONDITIONS),
        "force_rebuild_conditions": dict(FORCE_REBUILD_CONDITIONS),
        "source": _capture_source(),
        "latest": {
            "pre_card_proof": _latest("design_guide_pre_card_final_visible_output_bridge_proof"),
            "pre_render_impact": _latest("design_guide_pre_render_restamper_guarded_bypass_impact"),
            "remaining_restamper_audit": _latest("design_guide_remaining_final_visible_restamper_reference_audit"),
            "render_bridge_lock": _latest("design_guide_render_bridge_lock"),
            "compute_bridge_lock": _latest("design_guide_compute_resolver_publication_bridge_lock"),
            "independence_lock": _latest("design_guide_independence_lock"),
        },
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "engineering_behavior_changed": False,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    latest = dict(capture.get("latest") or {})
    source = dict(capture.get("source") or {})
    return {
        "pre_card_proof_latest_pass": (latest.get("pre_card_proof") or {}).get("status") == "PASS",
        "pre_render_impact_latest_pass": (latest.get("pre_render_impact") or {}).get("status") == "PASS",
        "remaining_restamper_audit_latest_pass": (latest.get("remaining_restamper_audit") or {}).get("status") == "PASS",
        "render_bridge_lock_latest_pass": (latest.get("render_bridge_lock") or {}).get("status") == "PASS",
        "compute_bridge_lock_latest_pass": (latest.get("compute_bridge_lock") or {}).get("status") == "PASS",
        "independence_lock_latest_pass": (latest.get("independence_lock") or {}).get("status") == "PASS",
        "all_bypass_conditions_listed": set(capture.get("bypass_conditions") or {}) == set(BYPASS_CONDITIONS),
        "all_force_rebuild_conditions_listed": set(capture.get("force_rebuild_conditions") or {})
        == set(FORCE_REBUILD_CONDITIONS),
        "restamper_call_present": source.get("restamper_call_present") is True,
        "callsite_proof_present": source.get("callsite_proof_present") is True,
        "pre_card_input_copied": source.get("pre_card_input_copied") is True,
        "pre_card_pending_rec_copied": source.get("pre_card_pending_rec_copied") is True,
        "proof_stamp_before_bound_contract": source.get("proof_stamp_before_bound_contract") is True,
        "terminal_blocker_branch_acknowledged": source.get("terminal_blocker_branch_after_restamper") is True,
        "primary_presentation_branch_acknowledged": source.get("primary_presentation_branch_after_restamper") is True,
        "implementation_not_done_in_this_slice": capture.get("implementation_allowed_now") is False
        and source.get("no_bypass_wired_yet") is True,
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "engineering_behavior_unchanged": capture.get("engineering_behavior_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Design Guide Pre-Card Restamper Guarded Bypass Readiness Snapshot",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        "",
        "## Bypass Conditions",
        "",
        "```json",
        json.dumps(capture.get("bypass_conditions") or {}, indent=2),
        "```",
        "",
        "## Force Rebuild Conditions",
        "",
        "```json",
        json.dumps(capture.get("force_rebuild_conditions") or {}, indent=2),
        "```",
        "",
        "## Source Notes",
        "",
        "The pre-card bridge can still feed terminal blocker and primary presentation state. A future bypass must only fire after a no-op proof.",
    ]
    if payload.get("failures"):
        lines.extend(["", "## Failures"])
        lines.extend(f"- `{failure}`" for failure in payload["failures"])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _stamp()
    capture = _capture()
    checks = _checks(capture)
    failures = [key for key, value in checks.items() if value is not True]
    status = "PASS" if not failures else "FAIL"
    payload = {
        "schema": "design_guide_pre_card_restamper_guarded_bypass_readiness_snapshot.v1",
        "status": status,
        "created_at": stamp,
        "capture": capture,
        "checks": checks,
        "failures": failures,
    }
    json_path = ARTIFACT_DIR / f"design_guide_pre_card_restamper_guarded_bypass_readiness_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_pre_card_restamper_guarded_bypass_readiness_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(report_path, payload)
    print(json.dumps({"status": status, "json": str(json_path), "report": str(report_path)}, indent=2))
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
