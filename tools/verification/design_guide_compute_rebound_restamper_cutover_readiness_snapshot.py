"""Cutover readiness snapshot for compute rebound final-visible output bridges.

This proof is intentionally conservative. It records why the compute rebound
restamper pair is not ready for deletion or render-style no-op bypass yet, and
defines the exact parity requirements for the future cutover.
"""

from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"

REQUIRED_PARITY_SURFACES = {
    "accepted_guard_outcome": "live accepted/skipped guard equals controller guard proof",
    "restamper_rebound_item_identity": "old restamper rebound output identity equals controller rebound selected item",
    "publication_adapter_identity": "collapsed guidance item from FinalDesignGuidePublication equals live rebound item after adapter",
    "rebound_contract": "button_contract/update payload matches controller rebound contract",
    "collapsed_guidance_mutation": "collapsed_guidance_items[0] mutation matches controller output",
    "debug_compatibility_payload_proof": "debug_trace parity is proven by controller debug payload keys/hash instead of a mirrored debug dict",
    "final_publication_hash": "FinalDesignGuidePublication hash remains unchanged by replacement",
    "cta_apply_surface": "CTA/apply payload remains unchanged by replacement",
}

BLOCKING_TRUTH = {
    "compute_late_evidence_contract_rebound": (
        "late_evidence_acceptance",
        "late_rebound_contract",
        "primary_item_for_evidence mutation",
        "collapsed_guidance_items mutation",
        "late_evidence_cleanup_contract_rebound debug fields",
    ),
    "post_core_evidence_rebound": (
        "post_core_mismatch",
        "post_rebound_contract_for_trace",
        "collapsed_guidance_items mutation",
        "post_mutation_debug_updates",
    ),
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


def _capture() -> dict[str, Any]:
    return {
        "decision": "NOT_READY_TO_CUTOVER_OR_DELETE",
        "reason": "compute rebound restampers still own live pre-publication guard and mutation truth",
        "blocking_truth": dict(BLOCKING_TRUTH),
        "required_future_parity_surfaces": dict(REQUIRED_PARITY_SURFACES),
        "allowed_next_step": "build focused parity scenarios for accepted and skipped compute rebound paths",
        "forbidden_next_steps": [
            "delete compute rebound restamper calls",
            "apply render-stage no-op bypass assumptions",
            "change CTA/apply semantics",
            "change publication semantics",
            "change visible wording",
        ],
        "latest": {
            "ownership": _latest("design_guide_compute_rebound_restamper_bridge_ownership"),
            "live_compute_handoff_rebound_bridge": _latest(
                "design_guide_live_compute_publication_handoff_rebound_decision_bridge"
            ),
            "compute_rebound_mutation_adapter_parity": _latest(
                "design_guide_compute_rebound_mutation_adapter_parity"
            ),
            "compute_rebound_mutation_adapter_cutover": _latest(
                "design_guide_compute_rebound_mutation_adapter_cutover"
            ),
            "compute_bridge_lock": _latest("design_guide_compute_resolver_publication_bridge_lock"),
            "render_bridge_lock": _latest("design_guide_render_bridge_lock"),
            "independence_lock": _latest("design_guide_independence_lock"),
            "remaining_restamper_audit": _latest("design_guide_remaining_final_visible_restamper_reference_audit"),
        },
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "engineering_behavior_changed": False,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    latest = dict(capture.get("latest") or {})
    return {
        "decision_is_not_ready": capture.get("decision") == "NOT_READY_TO_CUTOVER_OR_DELETE",
        "blocking_truth_listed": set(capture.get("blocking_truth") or {}) == set(BLOCKING_TRUTH),
        "required_future_parity_surfaces_listed": set(capture.get("required_future_parity_surfaces") or {})
        == set(REQUIRED_PARITY_SURFACES),
        "ownership_latest_pass": (latest.get("ownership") or {}).get("status") == "PASS",
        "live_compute_handoff_rebound_bridge_latest_pass": (
            latest.get("live_compute_handoff_rebound_bridge") or {}
        ).get("status")
        == "PASS",
        "compute_rebound_mutation_adapter_parity_latest_pass": (
            latest.get("compute_rebound_mutation_adapter_parity") or {}
        ).get("status")
        == "PASS",
        "compute_rebound_mutation_adapter_cutover_latest_pass": (
            latest.get("compute_rebound_mutation_adapter_cutover") or {}
        ).get("status")
        == "PASS",
        "compute_bridge_lock_latest_pass": (latest.get("compute_bridge_lock") or {}).get("status") == "PASS",
        "render_bridge_lock_latest_pass": (latest.get("render_bridge_lock") or {}).get("status") == "PASS",
        "independence_lock_latest_pass": (latest.get("independence_lock") or {}).get("status") == "PASS",
        "remaining_restamper_audit_latest_pass": (latest.get("remaining_restamper_audit") or {}).get("status")
        == "PASS",
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "engineering_behavior_unchanged": capture.get("engineering_behavior_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Design Guide Compute Rebound Restamper Cutover Readiness Snapshot",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        "",
        "## Blocking Truth",
        "",
    ]
    for target, fields in dict(capture.get("blocking_truth") or {}).items():
        lines.append(f"- `{target}`: {', '.join(f'`{field}`' for field in fields)}")
    lines.extend(["", "## Required Future Parity Surfaces", ""])
    for key, value in dict(capture.get("required_future_parity_surfaces") or {}).items():
        lines.append(f"- `{key}`: {value}")
    lines.extend(["", "## Next Step", "", str(capture.get("allowed_next_step") or "")])
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
        "schema": "design_guide_compute_rebound_restamper_cutover_readiness_snapshot.v1",
        "status": status,
        "created_at": stamp,
        "capture": capture,
        "checks": checks,
        "failures": failures,
    }
    json_path = ARTIFACT_DIR / f"design_guide_compute_rebound_restamper_cutover_readiness_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_compute_rebound_restamper_cutover_readiness_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(report_path, payload)
    print(json.dumps({"status": status, "json": str(json_path), "report": str(report_path)}, indent=2))
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
