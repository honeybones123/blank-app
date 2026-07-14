"""Ownership snapshot for compute rebound final-visible output bridges.

The remaining final-visible restamper audit identifies two compute rebound
calls. This snapshot does not change code. It classifies what is already
controller/proof-owned and what remains live before any bypass, cutover, or
deletion is attempted.
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

TARGETS = {
    "compute_late_evidence_contract_rebound": {
        "function": "_apply_compute_late_evidence_contract_rebound",
        "restamper_call": "_late_rebound_item = _publish_final_visible_design_guide_contract_binding(",
        "adapter_call": "_late_rebound_item = _collapsed_guidance_item_from_final_publication_authority(",
        "handoff_proof": 'path_id="compute_late_evidence_contract_rebound"',
        "mutation_trace": 'path_id="compute_late_evidence_contract_rebound"',
        "live_truth_fields": (
            "_late_evidence_acceptance",
            "_late_rebound_contract",
            "primary_item_for_evidence.update(_late_mutation_item)",
            "collapsed_guidance_items[0] = dict(",
            "late_evidence_cleanup_contract_rebound_contract",
        ),
    },
    "post_core_evidence_rebound": {
        "function": "_orchestrate_compute_post_core_publication_handoff",
        "restamper_call": "_post_evidence_rebound = _publish_final_visible_design_guide_contract_binding(",
        "adapter_call": "_post_evidence_rebound = _collapsed_guidance_item_from_final_publication_authority(",
        "handoff_proof": 'path_id="post_core_evidence_rebound"',
        "mutation_trace": 'path_id="post_core_evidence_rebound"',
        "live_truth_fields": (
            "_post_core_mismatch",
            "_post_rebound_contract_for_trace",
            "collapsed_guidance_items[0] = dict(",
            "debug_trace.update(_post_mutation_debug_updates)",
        ),
    },
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


def _function_window(source: str, function_name: str) -> str:
    start = source.find(f"def {function_name}(")
    if start < 0:
        return ""
    next_def = source.find("\ndef ", start + 5)
    if next_def < 0:
        next_def = len(source)
    return source[start:next_def]


def _line_for(source: str, token: str) -> int | None:
    index = source.find(token)
    if index < 0:
        return None
    return source.count("\n", 0, index) + 1


def _target_rows(source: str) -> dict[str, Any]:
    rows: dict[str, Any] = {}
    for target_id, spec in TARGETS.items():
        window = _function_window(source, spec["function"])
        restamper_present = spec["restamper_call"] in window
        adapter_present = spec["adapter_call"] in window
        handoff_present = spec["handoff_proof"] in window and "_stamp_final_publication_compute_handoff_rebound_decision_proof(" in window
        mutation_trace_present = spec["mutation_trace"] in window and "_stamp_design_guide_controller_compute_rebound_mutation_trace_only(" in window
        live_truth = {field: field in window for field in spec["live_truth_fields"]}
        rows[target_id] = {
            "function": spec["function"],
            "restamper_line": _line_for(source, spec["restamper_call"]),
            "restamper_present": restamper_present,
            "publication_adapter_present": adapter_present,
            "handoff_rebound_decision_proof_present": handoff_present,
            "controller_rebound_mutation_trace_present": mutation_trace_present,
            "live_truth_fields": live_truth,
            "all_live_truth_fields_present": all(live_truth.values()),
            "classification": (
                "C. still live compute rebound bridge - proofed but not bypass/cutover-ready"
                if restamper_present and handoff_present and mutation_trace_present and all(live_truth.values())
                else "E. ownership gap"
            ),
            "next_required_proof": (
                "Build focused restamper no-op/cutover readiness for this compute rebound path; do not "
                "reuse render-stage bypass assumptions because this bridge can mutate collapsed items and debug."
            ),
        }
    return rows


def _capture() -> dict[str, Any]:
    source = INPUTS_PAGE.read_text(encoding="utf-8-sig", errors="replace").lstrip("\ufeff")
    rows = _target_rows(source)
    return {
        "decision": "COMPUTE_REBOUND_RESTAMPERS_STILL_LIVE_PROOFED_NOT_READY_TO_DELETE",
        "targets": rows,
        "target_count": len(rows),
        "ownership_gap_count": sum(1 for row in rows.values() if row.get("classification") == "E. ownership gap"),
        "ready_for_deletion_count": 0,
        "ready_for_guarded_bypass_count": 0,
        "latest": {
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
    targets = dict(capture.get("targets") or {})
    return {
        "both_targets_found": capture.get("target_count") == 2,
        "no_ownership_gaps": capture.get("ownership_gap_count") == 0,
        "no_deletion_ready_claim": capture.get("ready_for_deletion_count") == 0,
        "no_guarded_bypass_ready_claim": capture.get("ready_for_guarded_bypass_count") == 0,
        "all_restamper_calls_present": all(row.get("restamper_present") for row in targets.values()),
        "all_publication_adapters_present": all(row.get("publication_adapter_present") for row in targets.values()),
        "all_handoff_proofs_present": all(
            row.get("handoff_rebound_decision_proof_present") for row in targets.values()
        ),
        "all_mutation_traces_present": all(
            row.get("controller_rebound_mutation_trace_present") for row in targets.values()
        ),
        "all_live_truth_fields_present": all(row.get("all_live_truth_fields_present") for row in targets.values()),
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
        "# Design Guide Compute Rebound Restamper Bridge Ownership Snapshot",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        "",
        "## Targets",
        "",
        "| Target | Restamper line | Classification | Next proof |",
        "| --- | ---: | --- | --- |",
    ]
    for target_id, row in dict(capture.get("targets") or {}).items():
        lines.append(
            "| `{}` | `{}` | `{}` | {} |".format(
                target_id,
                row.get("restamper_line"),
                row.get("classification"),
                str(row.get("next_required_proof") or "").replace("|", "\\|"),
            )
        )
    lines.extend(["", "## Decision", ""])
    lines.append("The compute rebound final-visible output bridges are proofed but still live. They are not deletion-ready and not yet guarded-bypass-ready.")
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
        "schema": "design_guide_compute_rebound_restamper_bridge_ownership_snapshot.v1",
        "status": status,
        "created_at": stamp,
        "capture": capture,
        "checks": checks,
        "failures": failures,
    }
    json_path = ARTIFACT_DIR / f"design_guide_compute_rebound_restamper_bridge_ownership_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_compute_rebound_restamper_bridge_ownership_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(report_path, payload)
    print(json.dumps({"status": status, "json": str(json_path), "report": str(report_path)}, indent=2))
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
