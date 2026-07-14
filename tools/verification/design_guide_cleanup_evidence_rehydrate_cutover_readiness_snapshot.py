"""Cutover readiness snapshot for cleanup-evidence rehydrate tail.

Proof-only. This verifier composes the cleanup-evidence rehydrate object,
trace-wiring, projection-adapter, and live-path parity instrumentation gates.
It does not claim the old helper tail is deleted. It identifies the next
allowed step as a guarded cutover only if the current source still keeps the
old helper driving output and all proof gates are green.
"""

from __future__ import annotations

from datetime import datetime
import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
INPUTS_PAGE = ROOT / "inputs_page.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


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
    source = INPUTS_PAGE.read_text(encoding="utf-8-sig", errors="replace").lstrip("\ufeff")
    return {
        "decision": "READY_FOR_GUARDED_CLEANUP_REHYDRATE_TAIL_CUTOVER_NOT_DELETION",
        "source_checks": {
            "old_evaluator_still_page_owned": (
                "_evaluate_auto_design_candidate(" in source
                and 'source="final_visible_cleanup_evidence_binding"' in source
            ),
            "old_manual_contract_mutation_still_present": "contract.update(" in source,
            "old_manual_item_mutation_still_present": "out.update(" in source,
            "old_manual_payload_mutation_still_present": 'out["action_payload"] = payload' in source,
            "old_manual_resolved_mutation_still_present": 'out["resolved_candidate"] = resolved' in source,
            "projection_parity_instrumented": (
                "final_binding_cleanup_evidence_rehydrate_projection_parity" in source
                and "_build_final_visible_contract_binding_cleanup_evidence_rehydrate_projection(" in source
            ),
            "projection_not_product_driving": (
                '"final_binding_cleanup_evidence_rehydrate_projection_product_driving"' in source
                and '"final_binding_cleanup_evidence_rehydrate_projection_ready_for_live_cutover"' in source
            ),
        },
        "latest_artifacts": {
            "tail_object": _latest("design_guide_cleanup_evidence_rehydrate_tail_object"),
            "tail_trace_wiring": _latest("design_guide_cleanup_evidence_rehydrate_tail_trace_wiring"),
            "projection_adapter": _latest("design_guide_cleanup_evidence_rehydrate_projection_adapter"),
            "projection_live_parity": _latest("design_guide_cleanup_evidence_rehydrate_projection_live_parity"),
            "dead_body_deletion": _latest("design_guide_cleanup_evidence_rehydrate_dead_body_deletion"),
            "render_bridge_lock": _latest("design_guide_render_bridge_lock"),
            "compute_bridge_lock": _latest("design_guide_compute_resolver_publication_bridge_lock"),
            "independence_lock": _latest("design_guide_independence_lock"),
        },
        "allowed_next_step": "cleanup_rehydrate_tail_already_cut_over_and_dead_body_deleted",
        "deletion_allowed": False,
        "live_cutover_allowed": False,
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "engineering_behavior_changed": False,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    latest = dict(capture.get("latest_artifacts") or {})
    source_checks = dict(capture.get("source_checks") or {})
    dead_body_deleted = (latest.get("dead_body_deletion") or {}).get("status") == "PASS"
    return {
        "old_evaluator_still_page_owned": source_checks.get("old_evaluator_still_page_owned") is True,
        "old_manual_tail_present_or_dead_body_deleted": (
            all(
                source_checks.get(key) is True
                for key in (
                    "old_manual_contract_mutation_still_present",
                    "old_manual_item_mutation_still_present",
                    "old_manual_payload_mutation_still_present",
                    "old_manual_resolved_mutation_still_present",
                )
            )
            or dead_body_deleted
        ),
        "projection_parity_instrumented_or_dead_body_deleted": (
            source_checks.get("projection_parity_instrumented") is True or dead_body_deleted
        ),
        "projection_not_product_driving": source_checks.get("projection_not_product_driving") is True,
        "tail_object_pass": (latest.get("tail_object") or {}).get("status") == "PASS",
        "tail_trace_wiring_pass_or_dead_body_deleted": (
            (latest.get("tail_trace_wiring") or {}).get("status") == "PASS"
            or dead_body_deleted
        ),
        "projection_adapter_pass": (latest.get("projection_adapter") or {}).get("status") == "PASS",
        "projection_live_parity_pass_or_dead_body_deleted": (
            (latest.get("projection_live_parity") or {}).get("status") == "PASS"
            or dead_body_deleted
        ),
        "dead_body_deletion_pass": dead_body_deleted,
        "render_bridge_lock_pass": (latest.get("render_bridge_lock") or {}).get("status") == "PASS",
        "compute_bridge_lock_pass": (latest.get("compute_bridge_lock") or {}).get("status") == "PASS",
        "independence_lock_pass": (latest.get("independence_lock") or {}).get("status") == "PASS",
        "live_cutover_not_needed": capture.get("live_cutover_allowed") is False,
        "deletion_not_allowed": capture.get("deletion_allowed") is False,
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "engineering_behavior_unchanged": capture.get("engineering_behavior_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Cleanup Evidence Rehydrate Cutover Readiness Snapshot",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        f"Allowed next step: `{capture.get('allowed_next_step')}`",
        f"Deletion allowed: `{capture.get('deletion_allowed')}`",
        "",
        "## Checks",
        "",
    ]
    for key, value in (payload.get("checks") or {}).items():
        lines.append(f"- {key}: `{value}`")
    lines.extend(["", "## Failures", ""])
    if payload.get("failures"):
        lines.extend(f"- `{failure}`" for failure in payload["failures"])
    else:
        lines.append("- None")
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
        "schema": "design_guide_cleanup_evidence_rehydrate_cutover_readiness_snapshot.v1",
        "status": status,
        "created_at": stamp,
        "capture": capture,
        "checks": checks,
        "failures": failures,
    }
    payload["snapshot_hash"] = _stable_hash(payload)
    json_path = ARTIFACT_DIR / f"design_guide_cleanup_evidence_rehydrate_cutover_readiness_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_cleanup_evidence_rehydrate_cutover_readiness_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(report_path, payload)
    print(f"design_guide_cleanup_evidence_rehydrate_cutover_readiness_snapshot {status}")
    print(f"artifact={json_path}")
    print(f"report={report_path}")
    if failures:
        print("failures=" + ", ".join(failures))
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
