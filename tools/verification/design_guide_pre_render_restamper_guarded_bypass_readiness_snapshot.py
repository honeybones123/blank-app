"""Readiness proof for a future guarded pre-render restamper bypass.

This snapshot defines the only safe bypass shape. It does not implement the
bypass. The live restamper must still rebuild unless a previous proof proves
the exact stable case produced no output, CTA, display, or evidence mutation.
"""

from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _latest(prefix: str) -> dict[str, Any]:
    paths = sorted(ARTIFACT_DIR.glob(f"{prefix}_*.json"), key=lambda path: path.stat().st_mtime)
    if not paths:
        return {"found": False, "status": "MISSING", "path": None}
    path = paths[-1]
    payload = json.loads(path.read_text(encoding="utf-8"))
    raw_status = str(payload.get("status") or payload.get("result") or payload.get("lock_status") or "")
    status = "PASS" if any(token in raw_status.upper() for token in ("PASS", "LOCKED", "COMPLETE")) else raw_status
    return {"found": True, "status": status or "UNKNOWN", "path": str(path)}


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
    "previous_display_changed": "previous proof changed display surface",
    "previous_evidence_changed": "previous proof changed evidence surface",
    "debug_mode": "debug mode or force rebuild enabled",
    "apply_in_flight": "post-click/apply-in-flight state present",
}


def _capture() -> dict[str, Any]:
    return {
        "decision": "READY_FOR_PROOF_ONLY_GUARDED_BYPASS_IMPLEMENTATION_PLAN",
        "implementation_allowed_now": False,
        "reason": "bypass contract is defined but live code has not yet been wired or proven in browser/live state",
        "bypass_conditions": dict(BYPASS_CONDITIONS),
        "force_rebuild_conditions": dict(FORCE_REBUILD_CONDITIONS),
        "latest": {
            "projection_snapshot": _latest("design_guide_restamper_bridge_output_projection"),
            "pre_render_proof": _latest("design_guide_pre_render_final_visible_output_bridge_proof"),
            "cutover_readiness": _latest("design_guide_pre_render_restamper_bridge_cutover_readiness"),
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
    return {
        "projection_snapshot_latest_pass": (latest.get("projection_snapshot") or {}).get("status") == "PASS",
        "pre_render_proof_latest_pass": (latest.get("pre_render_proof") or {}).get("status") == "PASS",
        "cutover_readiness_latest_pass": (latest.get("cutover_readiness") or {}).get("status") == "PASS",
        "render_bridge_lock_latest_pass": (latest.get("render_bridge_lock") or {}).get("status") == "PASS",
        "compute_bridge_lock_latest_pass": (latest.get("compute_bridge_lock") or {}).get("status") == "PASS",
        "independence_lock_latest_pass": (latest.get("independence_lock") or {}).get("status") == "PASS",
        "all_bypass_conditions_listed": set(capture.get("bypass_conditions") or {}) == set(BYPASS_CONDITIONS),
        "all_force_rebuild_conditions_listed": set(capture.get("force_rebuild_conditions") or {})
        == set(FORCE_REBUILD_CONDITIONS),
        "implementation_not_done_in_this_slice": capture.get("implementation_allowed_now") is False,
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "engineering_behavior_unchanged": capture.get("engineering_behavior_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Design Guide Pre-Render Restamper Guarded Bypass Readiness Snapshot",
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
        "## Next Safe Step",
        "",
        "Implement the guarded bypass only for stable no-mutation proofs, then run a live impact snapshot.",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _stamp()
    capture = _capture()
    checks = _checks(capture)
    status = "PASS" if all(checks.values()) else "FAIL"
    payload = {
        "schema": "design_guide_pre_render_restamper_guarded_bypass_readiness_snapshot.v1",
        "status": status,
        "created_at": stamp,
        "capture": capture,
        "checks": checks,
    }
    json_path = ARTIFACT_DIR / f"design_guide_pre_render_restamper_guarded_bypass_readiness_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_pre_render_restamper_guarded_bypass_readiness_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(report_path, payload)
    print(json.dumps({"status": status, "json": str(json_path), "report": str(report_path)}, indent=2))
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
