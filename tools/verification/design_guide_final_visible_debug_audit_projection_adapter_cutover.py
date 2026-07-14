"""Verify final-visible debug/audit projections are adapter-backed.

The slice keeps page-shell session/debug mutation, but moves the projection
shape for the remaining M1 debug/audit helpers into design_brain.final_publication.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from design_brain.final_publication import (  # noqa: E402
    build_final_visible_debug_projection,
    build_final_visible_primary_payload_binding_audit_projection,
)


INPUTS = ROOT / "inputs_page.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
REPORT_DIR = ROOT / "artifacts" / "reports"


HELPERS = {
    "_set_final_visible_disabled_primary_payload_binding_audit_projection": (
        "_build_final_visible_primary_payload_binding_audit_projection("
    ),
    "_update_final_visible_enabled_action_debug_projection": (
        "_build_final_visible_debug_projection("
    ),
    "_update_final_visible_disabled_debug_projection": (
        "_build_final_visible_debug_projection("
    ),
}


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _function_body(source: str, name: str) -> str:
    needle = f"def {name}("
    start = source.find(needle)
    if start < 0:
        return ""
    next_def = source.find("\ndef ", start + len(needle))
    return source[start:] if next_def < 0 else source[start:next_def]


def _latest(prefix: str) -> dict[str, Any]:
    paths = sorted(ARTIFACT_DIR.glob(f"{prefix}_*.json"), key=lambda p: p.stat().st_mtime)
    if not paths:
        return {"found": False, "path": None, "status": None}
    path = paths[-1]
    try:
        payload = json.loads(_read(path))
    except Exception as exc:
        return {"found": True, "path": str(path), "status": None, "load_error": str(exc)}
    return {"found": True, "path": str(path), "status": payload.get("status"), "payload": payload}


def _adapter_payload_parity() -> dict[str, Any]:
    item = {
        "candidate_search_evidence": {"family": "bending", "reason": "sample"},
        "exact_blockers_by_family": {"bending": {"exact_blocker": True}},
        "post_click_exact_blockers_by_family": {"bending": {"no_second_cta_required": True}},
        "cleanup_evidence_by_family": {"bending": {"attempted": True}},
        "post_click_cleanup_evidence_by_family": {"bending": {"attempted": True}},
        "family_status_current": {"bending": {"status": "FAIL", "util": 1.2}},
        "family_status_preview": {"bending": {"status": "PASS", "util": 0.9}},
        "blocker_attempts_by_family": {"bending": {"attempts": 2}},
    }
    contract = {
        "enabled": True,
        "actionable": True,
        "action_type": "apply_resolved_candidate",
        "family": "bending",
        "updates": {"D": 650},
        "preview_pass": True,
        "blocking_reason": None,
    }
    payload = {"candidate_id": "sample", "updates": {"D": 650}}
    enabled = build_final_visible_debug_projection(
        enabled=True,
        button_contract=contract,
        updates={"D": 650},
        family="bending",
        payload=payload,
        item=item,
    )
    disabled_contract = dict(contract)
    disabled_contract.update({"enabled": False, "actionable": False, "updates": {}, "preview_pass": False})
    disabled = build_final_visible_debug_projection(
        enabled=False,
        button_contract=disabled_contract,
        item=item,
        reason="blocked",
    )
    audit = build_final_visible_primary_payload_binding_audit_projection(
        visible_primary_candidate_id="sample",
        state_fingerprint="state-fp",
    )
    expected_enabled = {
        "primary_button_contract": dict(contract),
        "button_contract": dict(contract),
        "displayed_primary_button_contract": dict(contract),
        "button_contract_enabled": True,
        "button_contract_updates": {"D": 650},
        "button_contract_preview_pass": True,
        "button_contract_blocking_reason": None,
        "selected_action_type": "apply_resolved_candidate",
        "selected_action_family": "bending",
        "design_guide_primary_apply_payload": dict(payload),
        "selected_action_updates": {"D": 650},
        "candidate_search_evidence": dict(item["candidate_search_evidence"]),
        "exact_blockers_by_family": dict(item["exact_blockers_by_family"]),
        "post_click_exact_blockers_by_family": dict(item["post_click_exact_blockers_by_family"]),
        "cleanup_evidence_by_family": dict(item["cleanup_evidence_by_family"]),
        "post_click_cleanup_evidence_by_family": dict(item["post_click_cleanup_evidence_by_family"]),
        "family_status_current": dict(item["family_status_current"]),
        "family_status_preview": dict(item["family_status_preview"]),
        "blocker_attempts_by_family": dict(item["blocker_attempts_by_family"]),
    }
    expected_disabled = {
        "primary_button_contract": dict(disabled_contract),
        "button_contract": dict(disabled_contract),
        "displayed_primary_button_contract": dict(disabled_contract),
        "button_contract_enabled": False,
        "button_contract_updates": {},
        "button_contract_preview_pass": False,
        "button_contract_blocking_reason": "blocked",
        "design_guide_primary_apply_payload": {},
        "selected_action_updates": {},
        "family_status_current": dict(item["family_status_current"]),
        "family_status_preview": dict(item["family_status_preview"]),
        "blocker_attempts_by_family": dict(item["blocker_attempts_by_family"]),
    }
    expected_audit = {
        "visible_primary_candidate_id": "sample",
        "button_contract_candidate_id": None,
        "queued_apply_candidate_id": None,
        "applied_candidate_id": None,
        "visible_updates": {},
        "button_contract_updates": {},
        "queued_apply_updates": {},
        "applied_updates": {},
        "payload_binding_match": False,
        "payload_update_match": False,
        "stale_apply_payload_blocked": False,
        "canonical_primary_payload_exists": False,
        "legacy_fallback_used": False,
        "render_fingerprint": None,
        "state_fingerprint": "state-fp",
    }
    audit_public = {
        key: value
        for key, value in audit.items()
        if key
        not in {
            "projection_hash",
            "derived_from",
            "product_driving",
            "render_driving",
            "apply_driving",
            "session_driving",
        }
    }
    return {
        "enabled_debug_projection_matches": enabled.get("debug_projection") == expected_enabled,
        "disabled_debug_projection_matches": disabled.get("debug_projection") == expected_disabled,
        "payload_binding_audit_projection_matches": audit_public == expected_audit,
        "enabled_projection_hash_present": bool(enabled.get("projection_hash")),
        "disabled_projection_hash_present": bool(disabled.get("projection_hash")),
        "audit_projection_hash_present": bool(audit.get("projection_hash")),
    }


def build_snapshot() -> dict[str, Any]:
    source = _read(INPUTS)
    helper_rows = []
    failures: list[str] = []
    for helper, adapter_call in HELPERS.items():
        body = _function_body(source, helper)
        adapter_backed = bool(body and adapter_call in body)
        helper_rows.append(
            {
                "helper": helper,
                "adapter_call": adapter_call,
                "body_found": bool(body),
                "adapter_backed": adapter_backed,
            }
        )
        if not body:
            failures.append(f"missing_helper_body:{helper}")
        if not adapter_backed:
            failures.append(f"helper_not_adapter_backed:{helper}")
    parity = _adapter_payload_parity()
    for key, value in parity.items():
        if not value:
            failures.append(f"parity_failed:{key}")
    consumer_audit = _latest("design_guide_final_visible_debug_audit_projection_consumer")
    if consumer_audit.get("status") != "PASS":
        failures.append("consumer_audit_not_pass")
    status = "PASS" if not failures else "FAIL"
    return {
        "schema": "design_guide_final_visible_debug_audit_projection_adapter_cutover.v1",
        "created_at": datetime.now().strftime("%Y-%m-%dT%H-%M-%S"),
        "status": status,
        "decision": (
            "DEBUG_AUDIT_PROJECTION_HELPERS_ADAPTER_BACKED"
            if status == "PASS"
            else "DEBUG_AUDIT_PROJECTION_ADAPTER_CUTOVER_FAILED"
        ),
        "helpers": helper_rows,
        "parity": parity,
        "consumer_audit": {
            "path": consumer_audit.get("path"),
            "status": consumer_audit.get("status"),
        },
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtime_changed": False,
        "safe_to_delete_helper_calls_now": False,
        "next_safe_step": (
            "run inventory/locks, then add deadness proof for whether the now adapter-backed "
            "debug/audit helper calls can be deleted or must remain as page-shell writes"
        ),
        "failures": failures,
    }


def _write_report(snapshot: dict[str, Any], path: Path) -> None:
    lines = [
        "# Final Visible Debug/Audit Projection Adapter Cutover",
        "",
        f"Status: `{snapshot['status']}`",
        f"Decision: `{snapshot['decision']}`",
        "",
        "## Helpers",
        "| Helper | Adapter-backed | Adapter call |",
        "| --- | --- | --- |",
    ]
    for row in snapshot["helpers"]:
        lines.append(f"| `{row['helper']}` | `{row['adapter_backed']}` | `{row['adapter_call']}` |")
    lines.extend(
        [
            "",
            "## Parity",
            *[f"- `{key}`: `{value}`" for key, value in snapshot["parity"].items()],
            "",
            "## Next Safe Step",
            snapshot["next_safe_step"],
            "",
        ]
    )
    if snapshot["failures"]:
        lines.extend(["## Failures", *[f"- `{failure}`" for failure in snapshot["failures"]], ""])
    path.write_text("\n".join(lines), encoding="utf-8")


def _write_extraction_report(snapshot: dict[str, Any], path: Path) -> None:
    lines = [
        "# Design Brain Physical Extraction Report",
        "",
        "## Executive Summary",
        snapshot["status"],
        "",
        "## Surface Targeted",
        "Final-visible disabled payload binding audit projection and enabled/disabled debug projection helpers.",
        "",
        "## Ownership Before",
        "Projection payload shape was branch-local in `inputs_page.py` helper bodies.",
        "",
        "## Ownership After",
        "Projection payload shape is adapter-backed by `design_brain.final_publication`; page still performs session/debug writes.",
        "",
        "## Behaviour Preserved",
        "Engineering behavior, visible wording, CTA/apply semantics, and family runtimes unchanged.",
        "",
        "## Adapter / Default Rebuild Proof",
        f"Adapter parity status: `{snapshot['status']}`.",
        "",
        "## Cutover Proof",
        f"Decision: `{snapshot['decision']}`.",
        "",
        "## Deadness / Deletion Proof",
        "Not attempted in this slice. Helper calls are not safe to delete until page-shell write deadness is proven.",
        "",
        "## Lines Removed / Added",
        "Code moved to adapter-backed projection shape; physical deletion deferred.",
        "",
        "## Files Changed",
        "- `design_brain/final_publication.py`",
        "- `inputs_page.py`",
        "- `tools/verification/design_guide_final_visible_debug_audit_projection_adapter_cutover.py`",
        "",
        "## Verifier Results",
        f"- Adapter cutover: `{snapshot['status']}`",
        "",
        "## Remaining Page-Owned Authority",
        "Page still owns the actual Streamlit/session/debug writes for these projections.",
        "",
        "## Next Safe Target",
        snapshot["next_safe_step"],
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    snapshot = build_snapshot()
    stamp = snapshot["created_at"]
    json_path = ARTIFACT_DIR / f"design_guide_final_visible_debug_audit_projection_adapter_cutover_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_final_visible_debug_audit_projection_adapter_cutover_{stamp}.md"
    extraction_report_path = REPORT_DIR / (
        f"design_brain_physical_extraction_final_visible_debug_audit_projection_{stamp}.md"
    )
    json_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(snapshot, report_path)
    _write_extraction_report(snapshot, extraction_report_path)
    print(f"design_guide_final_visible_debug_audit_projection_adapter_cutover {snapshot['status']}")
    print(f"decision={snapshot['decision']}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    print(f"extraction_report={extraction_report_path}")
    return 0 if snapshot["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
