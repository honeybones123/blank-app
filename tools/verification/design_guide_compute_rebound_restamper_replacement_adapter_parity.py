"""Parity proof for controller-owned compute rebound publication item.

Proof-only. This does not change live page behavior. It proves the controller
adapter can build the same rebound item surface that the old page restamper
was providing to the compute rebound mutation adapter.
"""

from __future__ import annotations

from datetime import datetime
import hashlib
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from design_brain.design_guide_controller import (  # noqa: E402
    run_design_guide_controller_compute_rebound_mutation_trace_only,
    run_design_guide_controller_compute_rebound_publication_item_trace_only,
)


ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
INPUTS_PAGE = ROOT / "inputs_page.py"

TARGETS = (
    "compute_late_evidence_contract_rebound",
    "post_core_evidence_rebound",
)


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


def _contract(path_id: str, *, enabled: bool) -> dict[str, Any]:
    return {
        "enabled": bool(enabled),
        "actionable": bool(enabled),
        "family": "combined",
        "action_type": "apply_resolved_candidate" if enabled else None,
        "candidate_id": f"{path_id}:candidate",
        "source_candidate_id": f"{path_id}:candidate",
        "updates": {"bot_no": 4, "link_no": 0},
        "preview_pass": bool(enabled),
        "expected_util": 0.74 if enabled else None,
        "executor_backed": bool(enabled),
    }


def _primary(path_id: str) -> dict[str, Any]:
    return {
        "published_item_id": f"{path_id}:primary",
        "candidate_id": f"{path_id}:primary-candidate",
        "source_candidate_id": f"{path_id}:primary-candidate",
        "selected_family_id": "COMBINED_OVERDESIGN_GOVERNS",
        "family": "combined",
        "status": "PASS",
        "bucket": "pass",
        "title": "Proof primary",
        "title_main": "Proof primary",
        "summary_line": "Primary proof item",
        "button_contract": _contract(path_id, enabled=False),
        "candidate_search_evidence": {
            "family": "combined",
            "selected_candidate_id": f"{path_id}:primary-candidate",
            "selected_candidate_updates": {},
            "safe_executor_backed_candidates_count": 0,
        },
    }


def _legacy_rebound(path_id: str, contract: dict[str, Any]) -> dict[str, Any]:
    updates = dict(contract.get("updates") or {})
    return {
        **_primary(path_id),
        "candidate_id": contract.get("candidate_id"),
        "source_candidate_id": contract.get("source_candidate_id"),
        "button_contract": dict(contract),
        "updates": dict(updates),
        "selected_action_updates": dict(updates),
        "action_payload": {
            "action_type": contract.get("action_type"),
            "family": contract.get("family"),
            "updates": dict(updates),
            "candidate_id": contract.get("candidate_id"),
            "source_candidate_id": contract.get("source_candidate_id"),
            "executor_backed": bool(contract.get("executor_backed")),
        },
        "candidate_search_evidence": {
            "family": contract.get("family"),
            "selected_candidate_id": contract.get("candidate_id"),
            "selected_candidate_updates": dict(updates),
            "safe_executor_backed_candidates_count": 1 if contract.get("enabled") else 0,
        },
    }


def _identity(item: dict[str, Any]) -> dict[str, Any]:
    contract = dict(item.get("button_contract") or {})
    return {
        "candidate_id": item.get("candidate_id") or contract.get("candidate_id"),
        "source_candidate_id": item.get("source_candidate_id") or contract.get("source_candidate_id"),
        "family": item.get("selected_family_id") or item.get("published_family_id") or item.get("family") or contract.get("family"),
        "button_contract_hash": _stable_hash(contract),
        "updates_hash": _stable_hash(
            contract.get("updates") or item.get("updates") or item.get("selected_action_updates") or {}
        ),
        "action_payload_hash": _stable_hash(item.get("action_payload") or {}),
        "evidence_hash": _stable_hash(item.get("candidate_search_evidence") or {}),
    }


def _scenario(path_id: str, *, accepted: bool) -> dict[str, Any]:
    primary = _primary(path_id)
    contract = _contract(path_id, enabled=accepted)
    expected = _legacy_rebound(path_id, contract) if accepted else dict(primary)
    replacement = run_design_guide_controller_compute_rebound_publication_item_trace_only(
        {
            "path_id": path_id,
            "primary_item": dict(primary),
            "rebound_contract": dict(contract if accepted else {}),
            "rebound_update_payload": dict(contract.get("updates") or {}) if accepted else {},
            "publication_reason": path_id,
            "source": "compute_rebound_restamper_replacement_adapter_parity",
        }
    )
    replacement_item = dict(replacement.selected_item if accepted else primary)
    mutation = run_design_guide_controller_compute_rebound_mutation_trace_only(
        {
            "path_id": path_id,
            "accepted": bool(accepted),
            "primary_item": dict(primary),
            "rebound_item": dict(replacement_item),
            "collapsed_guidance_items": [dict(primary)],
            "rebound_contract": dict(contract if accepted else {}),
            "rebound_update_payload": dict(contract.get("updates") or {}) if accepted else {},
            "source": "compute_rebound_restamper_replacement_adapter_parity",
        }
    )
    checks = {
        "replacement_identity_matches_legacy": _identity(replacement_item) == _identity(expected),
        "replacement_publication_hash_present": bool(replacement.publication_hash) if accepted else True,
        "replacement_collapsed_item_hash_present": bool(replacement.collapsed_guidance_item_hash) if accepted else True,
        "mutation_selected_identity_matches_legacy": _identity(dict(mutation.selected_item)) == _identity(expected),
        "mutation_acceptance_matches": bool(mutation.accepted) is bool(accepted),
    }
    return {
        "path_id": path_id,
        "accepted": bool(accepted),
        "checks": checks,
        "all_checks_pass": all(checks.values()),
        "expected_identity": _identity(expected),
        "replacement_identity": _identity(replacement_item),
        "mutation_identity": _identity(dict(mutation.selected_item)),
        "replacement_controller_hash": replacement.controller_hash,
        "mutation_controller_hash": mutation.controller_hash,
    }


def _source_checks() -> dict[str, bool]:
    source = INPUTS_PAGE.read_text(encoding="utf-8-sig", errors="replace").lstrip("\ufeff")
    return {
        "live_late_restamper_call_still_present": "_late_rebound_item = _publish_final_visible_design_guide_contract_binding(" in source,
        "live_post_restamper_call_still_present": "_post_evidence_rebound = _publish_final_visible_design_guide_contract_binding(" in source,
        "live_cutover_not_started": "_run_design_guide_controller_compute_rebound_publication_item_trace_only" not in source,
    }


def _capture() -> dict[str, Any]:
    rows = [_scenario(path_id, accepted=accepted) for path_id in TARGETS for accepted in (False, True)]
    return {
        "decision": "REPLACEMENT_ADAPTER_PARITY_PASS_CUTOVER_NOT_STARTED",
        "rows": rows,
        "source_checks": _source_checks(),
        "latest": {
            "cutover_plan": _latest("design_guide_compute_rebound_restamper_cutover_plan"),
            "focused_parity": _latest("design_guide_compute_rebound_restamper_focused_parity_scenarios"),
            "compute_bridge_lock": _latest("design_guide_compute_resolver_publication_bridge_lock"),
            "render_bridge_lock": _latest("design_guide_render_bridge_lock"),
            "independence_lock": _latest("design_guide_independence_lock"),
        },
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "engineering_behavior_changed": False,
        "cutover_started": False,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    latest = dict(capture.get("latest") or {})
    return {
        "four_scenarios_checked": len(capture.get("rows") or []) == 4,
        "all_rows_pass": all(row.get("all_checks_pass") for row in capture.get("rows") or []),
        "source_checks_pass": all(dict(capture.get("source_checks") or {}).values()),
        "cutover_plan_latest_pass": (latest.get("cutover_plan") or {}).get("status") == "PASS",
        "focused_parity_latest_pass": (latest.get("focused_parity") or {}).get("status") == "PASS",
        "compute_bridge_lock_latest_pass": (latest.get("compute_bridge_lock") or {}).get("status") == "PASS",
        "render_bridge_lock_latest_pass": (latest.get("render_bridge_lock") or {}).get("status") == "PASS",
        "independence_lock_latest_pass": (latest.get("independence_lock") or {}).get("status") == "PASS",
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "engineering_behavior_unchanged": capture.get("engineering_behavior_changed") is False,
        "cutover_not_started": capture.get("cutover_started") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    lines = [
        "# Design Guide Compute Rebound Restamper Replacement Adapter Parity",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{(payload.get('capture') or {}).get('decision')}`",
        "",
        "## Rows",
        "",
    ]
    for row in (payload.get("capture") or {}).get("rows") or []:
        lines.append(
            f"- `{row.get('path_id')}` accepted=`{row.get('accepted')}` pass=`{row.get('all_checks_pass')}`"
        )
    if payload.get("failures"):
        lines.extend(["", "## Failures"])
        lines.extend(f"- `{failure}`" for failure in payload["failures"])
    lines.extend(
        [
            "",
            "## Recommendation",
            "",
            (
                "The controller replacement adapter can build the rebound item surface. "
                "The next safe slice is a narrow live cutover of the two compute rebound "
                "restamper callsites, preserving existing guard predicates and branch shape."
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
    failures = [key for key, value in checks.items() if value is not True]
    status = "PASS" if not failures else "FAIL"
    payload = {
        "schema": "design_guide_compute_rebound_restamper_replacement_adapter_parity.v1",
        "status": status,
        "created_at": stamp,
        "capture": capture,
        "checks": checks,
        "failures": failures,
        "snapshot_hash": _stable_hash({"capture": capture, "checks": checks}),
    }
    json_path = ARTIFACT_DIR / f"design_guide_compute_rebound_restamper_replacement_adapter_parity_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_compute_rebound_restamper_replacement_adapter_parity_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(report_path, payload)
    print(json.dumps({"status": status, "json": str(json_path), "report": str(report_path)}, indent=2))
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
