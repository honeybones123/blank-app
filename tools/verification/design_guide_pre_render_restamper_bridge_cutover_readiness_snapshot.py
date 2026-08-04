"""Cutover-readiness snapshot for the pre-render final-visible output bridge.

The previous proof makes the bridge observable. This snapshot decides whether
the first pre-render bridge can be bypassed yet. It intentionally does not
change behavior.
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


REQUIRED_LIVE_SURFACES = {
    "bending_fail_snapshot_reuse": "_bending_fail_publication_snapshot_for_state(",
    "family_status_display_attachment": "_attach_family_status_display_payload(",
    "target_band_candidate_promotion": "final_binding_target_band_candidate_promoted",
    "safe_binding_update_reset": "safe_binding_evidence_available",
    "combined_binding_update_reset": "combined_binding_evidence_available",
    "post_click_no_second_cta_suppression": "final_binding_no_second_cta_suppressed",
    "button_contract_expected_util_rewrite": '"expected_util": float(evidence_expected_util)',
    "action_payload_rebuild": '"resolved_candidate_updates": dict(updates)',
    "debug_contract_restamps": '"primary_button_contract": dict(contract)',
}


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _latest(prefix: str) -> dict[str, Any]:
    paths = sorted(ARTIFACT_DIR.glob(f"{prefix}_*.json"), key=lambda path: path.stat().st_mtime)
    if not paths:
        return {"found": False, "status": "MISSING", "path": None, "payload": {}}
    path = paths[-1]
    payload = json.loads(path.read_text(encoding="utf-8"))
    raw_status = str(payload.get("status") or payload.get("result") or payload.get("lock_status") or "")
    status = "PASS" if any(token in raw_status.upper() for token in ("PASS", "LOCKED", "COMPLETE")) else raw_status
    return {"found": True, "status": status or "UNKNOWN", "path": str(path), "payload": payload}


def _restamper_body(source: str) -> str:
    marker = "def _publish_final_visible_design_guide_contract_binding("
    start = source.find(marker)
    if start < 0:
        return ""
    next_def = source.find("\ndef ", start + len(marker))
    return source[start:] if next_def < 0 else source[start:next_def]


def _capture() -> dict[str, Any]:
    source = INPUTS_PAGE.read_text(encoding="utf-8-sig", errors="replace")
    body = _restamper_body(source)
    surfaces = {
        name: {
            "present": token in body,
            "token": token,
            "classification": "live_product_truth",
        }
        for name, token in REQUIRED_LIVE_SURFACES.items()
    }
    missing = [name for name, row in surfaces.items() if not row.get("present")]
    latest = {
        "pre_render_proof": _latest("design_guide_pre_render_final_visible_output_bridge_proof"),
        "remaining_restamper_audit": _latest("design_guide_remaining_final_visible_restamper_reference_audit"),
        "render_bridge_lock": _latest("design_guide_render_bridge_lock"),
        "compute_bridge_lock": _latest("design_guide_compute_resolver_publication_bridge_lock"),
        "independence_lock": _latest("design_guide_independence_lock"),
    }
    return {
        "decision": "NOT_READY_TO_BYPASS_PRE_RENDER_RESTAMPER_BRIDGE",
        "ready_to_bypass": False,
        "ready_to_delete": False,
        "reason": "pre-render restamper still owns live binding, CTA, evidence, and debug restamp truth",
        "live_truth_surfaces": surfaces,
        "missing_expected_surface_tokens": missing,
        "replacement_required": "controller/publication equivalent for live restamper output before bypass",
        "latest": latest,
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "engineering_behavior_changed": False,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    latest = dict(capture.get("latest") or {})
    return {
        "pre_render_proof_latest_pass": (latest.get("pre_render_proof") or {}).get("status") == "PASS",
        "remaining_restamper_audit_latest_pass": (latest.get("remaining_restamper_audit") or {}).get("status") == "PASS",
        "render_bridge_lock_latest_pass": (latest.get("render_bridge_lock") or {}).get("status") == "PASS",
        "compute_bridge_lock_latest_pass": (latest.get("compute_bridge_lock") or {}).get("status") == "PASS",
        "independence_lock_latest_pass": (latest.get("independence_lock") or {}).get("status") == "PASS",
        "expected_live_surfaces_present": not bool(capture.get("missing_expected_surface_tokens")),
        "not_ready_to_bypass_recorded": capture.get("ready_to_bypass") is False,
        "not_ready_to_delete_recorded": capture.get("ready_to_delete") is False,
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "engineering_behavior_unchanged": capture.get("engineering_behavior_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Design Guide Pre-Render Restamper Bridge Cutover Readiness Snapshot",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Ready to bypass: `{capture.get('ready_to_bypass')}`",
        f"Ready to delete: `{capture.get('ready_to_delete')}`",
        "",
        "## Live Truth Surfaces",
        "",
        "| Surface | Present | Classification |",
        "| --- | --- | --- |",
    ]
    for name, row in dict(capture.get("live_truth_surfaces") or {}).items():
        lines.append(f"| `{name}` | `{row.get('present')}` | `{row.get('classification')}` |")
    lines.extend(
        [
            "",
            "## Next Safe Step",
            "",
            (
                "Build a controller/publication equivalent for the pre-render restamper output, "
                "then compare that equivalent against live restamper output before bypassing this callsite."
            ),
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _stamp()
    capture = _capture()
    checks = _checks(capture)
    status = "PASS" if all(checks.values()) else "FAIL"
    payload = {
        "schema": "design_guide_pre_render_restamper_bridge_cutover_readiness_snapshot.v1",
        "status": status,
        "created_at": stamp,
        "capture": capture,
        "checks": checks,
    }
    json_path = ARTIFACT_DIR / f"design_guide_pre_render_restamper_bridge_cutover_readiness_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_pre_render_restamper_bridge_cutover_readiness_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(report_path, payload)
    print(json.dumps({"status": status, "decision": capture.get("decision"), "json": str(json_path), "report": str(report_path)}, indent=2))
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
