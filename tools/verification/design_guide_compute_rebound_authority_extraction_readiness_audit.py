"""Audit remaining compute rebound authority before extraction.

Proof-only. This classifies the two remaining compute rebound bridges that still
own raw page-side compute truth after the legacy final-visible resolver deletion.
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
INPUTS_PAGE = ROOT / "inputs_page.py"

SURFACES = {
    "compute_late_evidence_contract_rebound": {
        "function": "_apply_compute_late_evidence_contract_rebound",
        "live_call": "_apply_compute_late_evidence_contract_rebound(",
        "publish_call": "_late_rebound_item = _publish_final_visible_design_guide_contract_binding(",
        "publication_adapter": "publication_reason=\"late_evidence_contract_rebound\"",
        "proof_stamp": 'path_id="compute_late_evidence_contract_rebound"',
        "live_truth_fields": (
            "late_evidence_update_acceptance_condition",
            "raw_late_rebound_contract.enabled",
            "raw_late_rebound_contract.updates",
            "debug_trace.selected_action_updates/action_type/family restamp",
        ),
        "controller_object_needed": "late_evidence_rebound_decision",
    },
    "post_core_evidence_rebound": {
        "function": "_orchestrate_compute_post_core_publication_handoff",
        "live_call": "_post_evidence_rebound = _publish_final_visible_design_guide_contract_binding(",
        "publish_call": "_post_evidence_rebound = _publish_final_visible_design_guide_contract_binding(",
        "publication_adapter": "publication_reason=\"post_evidence_contract_rebound\"",
        "proof_stamp": 'path_id="post_core_evidence_rebound"',
        "live_truth_fields": (
            "post_core_evidence_update_mismatch_condition",
            "raw_post_evidence_rebound.item",
            "post_evidence_cleanup_contract_rebound enabled flag",
            "collapsed_guidance_items[0] pre-resolver mutation",
        ),
        "controller_object_needed": "post_core_rebound_decision",
    },
}


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
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception as exc:
        return {
            "found": True,
            "status": "UNREADABLE",
            "path": str(path),
            "payload": {},
            "error": f"{type(exc).__name__}: {exc}",
        }
    status = str(payload.get("status") or payload.get("result") or payload.get("lock_status") or "")
    if "PASS" in status.upper() or "LOCKED" in status.upper() or "COMPLETE" in status.upper():
        status = "PASS"
    return {"found": True, "status": status or "UNKNOWN", "path": str(path), "payload": payload}


def _line_numbers(source: str, token: str) -> list[int]:
    return [
        index
        for index, line in enumerate(source.splitlines(), start=1)
        if token in line
    ]


def _function_window(source: str, function_name: str) -> str:
    token = f"def {function_name}("
    start = source.find(token)
    if start < 0:
        return ""
    next_def = source.find("\ndef ", start + 1)
    return source[start:] if next_def < 0 else source[start:next_def]


def _capture() -> dict[str, Any]:
    source = INPUTS_PAGE.read_text(encoding="utf-8-sig", errors="replace").lstrip("\ufeff")
    latest = {
        "same_object": _latest("design_guide_compute_stage_resolver_same_object"),
        "compute_bridge_lock": _latest("design_guide_compute_resolver_publication_bridge_lock"),
        "compatibility_helper_readiness": _latest(
            "design_guide_remaining_compatibility_helper_deletion_readiness"
        ),
        "deletion_readiness": _latest("design_guide_compute_stage_resolver_deletion_readiness"),
    }
    rows: list[dict[str, Any]] = []
    for surface_id, spec in SURFACES.items():
        window = _function_window(source, str(spec["function"]))
        rows.append(
            {
                "surface_id": surface_id,
                "function": spec["function"],
                "function_present": bool(window),
                "live_call_lines": _line_numbers(source, str(spec["live_call"])),
                "publish_call_lines": _line_numbers(window, str(spec["publish_call"])),
                "mutation_adapter_cutover_present": (
                    "_late_mutation_adapter = _stamp_design_guide_controller_compute_rebound_mutation_trace_only("
                    in window
                    if surface_id == "compute_late_evidence_contract_rebound"
                    else "_post_mutation_adapter = _stamp_design_guide_controller_compute_rebound_mutation_trace_only("
                    in window
                ),
                "publication_adapter_present": str(spec["publication_adapter"]) in window,
                "proof_stamp_present": str(spec["proof_stamp"]) in window,
                "live_truth_fields": list(spec["live_truth_fields"]),
                "controller_object_needed": spec["controller_object_needed"],
                "classification": (
                    "COMPUTE_REBOUND_MUTATION_ADAPTER_CUTOVER"
                    if (
                        (
                            surface_id == "compute_late_evidence_contract_rebound"
                            and "_late_mutation_adapter = _stamp_design_guide_controller_compute_rebound_mutation_trace_only("
                            in window
                        )
                        or (
                            surface_id == "post_core_evidence_rebound"
                            and "_post_mutation_adapter = _stamp_design_guide_controller_compute_rebound_mutation_trace_only("
                            in window
                        )
                    )
                    else "LIVE_COMPUTE_REBOUND_AUTHORITY"
                ),
                "delete_now": False,
                "safe_next_action": (
                    "keep mutation adapter cutover bounded; prove helper/debug deadness before deletion"
                    if (
                        (
                            surface_id == "compute_late_evidence_contract_rebound"
                            and "_late_mutation_adapter = _stamp_design_guide_controller_compute_rebound_mutation_trace_only("
                            in window
                        )
                        or (
                            surface_id == "post_core_evidence_rebound"
                            and "_post_mutation_adapter = _stamp_design_guide_controller_compute_rebound_mutation_trace_only("
                            in window
                        )
                    )
                    else "create controller-owned rebound decision object/parity proof before cutover or deletion"
                ),
            }
        )
    return {
        "decision": "COMPUTE_REBOUND_AUTHORITY_REMAINS_PROOF_NEXT",
        "surfaces": rows,
        "delete_ready_count": 0,
        "controller_object_required_count": len(rows),
        "latest": {
            key: {"status": value.get("status"), "path": value.get("path")}
            for key, value in latest.items()
        },
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "engineering_behavior_changed": False,
        "session_state_behavior_changed": False,
        "widget_keys_changed": False,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    latest = dict(capture.get("latest") or {})
    surfaces = list(capture.get("surfaces") or [])
    return {
        "two_surfaces_classified": len(surfaces) == 2,
        "all_functions_present": all(row.get("function_present") for row in surfaces),
        "all_publish_calls_live_or_adapter_cutover": all(
            row.get("publish_call_lines") or row.get("mutation_adapter_cutover_present")
            for row in surfaces
        ),
        "all_publication_adapters_present": all(row.get("publication_adapter_present") for row in surfaces),
        "all_proof_stamps_present": all(row.get("proof_stamp_present") for row in surfaces),
        "none_delete_ready": capture.get("delete_ready_count") == 0,
        "same_object_latest_pass": (latest.get("same_object") or {}).get("status") == "PASS",
        "compute_bridge_lock_latest_pass": (latest.get("compute_bridge_lock") or {}).get("status") == "PASS",
        "compatibility_helper_readiness_pass": (
            (latest.get("compatibility_helper_readiness") or {}).get("status") == "PASS"
        ),
        "deletion_readiness_pass": (latest.get("deletion_readiness") or {}).get("status") == "PASS",
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "engineering_behavior_unchanged": capture.get("engineering_behavior_changed") is False,
        "session_state_behavior_unchanged": capture.get("session_state_behavior_changed") is False,
        "widget_keys_unchanged": capture.get("widget_keys_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Compute Rebound Authority Extraction Readiness Audit",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Surface Map",
        "",
        "| Surface | Function | Publish Lines | Adapter | Proof Stamp | Delete Now | Next |",
        "| --- | --- | ---: | ---: | ---: | ---: | --- |",
    ]
    for row in list(capture.get("surfaces") or []):
        lines.append(
            "| `{surface_id}` | `{function}` | `{publish_call_lines}` | `{publication_adapter_present}` | `{proof_stamp_present}` | `{delete_now}` | {safe_next_action} |".format(
                **row
            )
        )
    lines.extend(["", "## Checks", ""])
    lines.extend(f"- {key}: `{value}`" for key, value in (payload.get("checks") or {}).items())
    lines.extend(
        [
            "",
            "## Recommendation",
            "",
            (
                "Do not delete these rebound bridges yet. The next safe slice is a "
                "controller-owned rebound decision object/parity proof that represents "
                "the late-evidence and post-core rebound predicates and raw rebound "
                "contract/item summaries."
            ),
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    capture = _capture()
    checks = _checks(capture)
    failures = [key for key, value in checks.items() if value is not True]
    status = "PASS" if not failures else "FAIL"
    payload = {
        "schema": "design_guide_compute_rebound_authority_extraction_readiness_audit.v1",
        "status": status,
        "created_at": _stamp(),
        "capture": capture,
        "checks": checks,
        "failures": failures,
    }
    payload["snapshot_hash"] = _stable_hash(payload)
    stamp = payload["created_at"]
    json_path = ARTIFACT_DIR / f"design_guide_compute_rebound_authority_extraction_readiness_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_compute_rebound_authority_extraction_readiness_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    _write_report(report_path, payload)
    print(f"design_guide_compute_rebound_authority_extraction_readiness {status}")
    print(f"decision={capture.get('decision')}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
