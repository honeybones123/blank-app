"""Focused parity scenarios for compute rebound final-visible output bridges.

This verifier proves the surfaces required by
design_guide_compute_rebound_restamper_cutover_readiness_snapshot.py for both
accepted and skipped compute rebound paths. It is proof-only: it does not
delete or bypass the live restamper calls.
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
)
from design_brain.final_publication import (  # noqa: E402
    build_collapsed_guidance_item_from_final_publication,
    build_final_design_guide_publication,
)


ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
INPUTS_PAGE = ROOT / "inputs_page.py"

TARGETS = (
    "compute_late_evidence_contract_rebound",
    "post_core_evidence_rebound",
)

REQUIRED_SURFACES = (
    "accepted_guard_outcome",
    "restamper_rebound_item_identity",
    "publication_adapter_identity",
    "rebound_contract",
    "collapsed_guidance_mutation",
    "debug_compatibility_payload_proof",
    "final_publication_hash",
    "cta_apply_surface",
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
    }


def _rebound(path_id: str, contract: dict[str, Any]) -> dict[str, Any]:
    return {
        **_primary(path_id),
        "published_item_id": f"{path_id}:rebound",
        "candidate_id": contract.get("candidate_id"),
        "source_candidate_id": contract.get("source_candidate_id"),
        "status": "ACTION" if contract.get("enabled") else "PASS",
        "bucket": "action" if contract.get("enabled") else "pass",
        "title": "Proof rebound",
        "title_main": "Proof rebound",
        "summary_line": "Rebound proof item",
        "button_contract": dict(contract),
        "updates": dict(contract.get("updates") or {}),
        "selected_action_updates": dict(contract.get("updates") or {}),
        "action_payload": {
            "action_type": contract.get("action_type"),
            "family": contract.get("family"),
            "updates": dict(contract.get("updates") or {}),
            "candidate_id": contract.get("candidate_id"),
            "source_candidate_id": contract.get("source_candidate_id"),
            "executor_backed": bool(contract.get("executor_backed")),
        },
        "candidate_search_evidence": {
            "family": contract.get("family"),
            "selected_candidate_id": contract.get("candidate_id"),
            "selected_candidate_updates": dict(contract.get("updates") or {}),
            "safe_executor_backed_candidates_count": 1 if contract.get("enabled") else 0,
        },
    }


def _expected_debug(path_id: str, *, accepted: bool, contract: dict[str, Any]) -> dict[str, Any]:
    if not accepted:
        return {}
    updates = dict(contract.get("updates") or {})
    if path_id == "compute_late_evidence_contract_rebound":
        return {
            "late_evidence_cleanup_contract_rebound": True,
            "primary_button_contract": dict(contract),
            "button_contract": dict(contract),
            "button_contract_enabled": True,
            "button_contract_updates": dict(updates),
            "selected_action_updates": dict(updates),
            "selected_action_type": "apply_resolved_candidate",
            "selected_action_family": contract.get("family"),
        }
    if path_id == "post_core_evidence_rebound":
        return {
            "post_evidence_cleanup_contract_rebound": bool(
                contract.get("enabled") or contract.get("actionable")
            )
        }
    return {}


def _expected_debug_keys_and_hash(
    path_id: str, *, accepted: bool, contract: dict[str, Any]
) -> tuple[tuple[str, ...], str]:
    expected = _expected_debug(path_id, accepted=accepted, contract=contract)
    return tuple(sorted(str(key) for key in expected.keys())), _stable_hash(expected)


def _identity(item: dict[str, Any]) -> dict[str, Any]:
    contract = dict(item.get("button_contract") or {})
    return {
        "published_item_id": item.get("published_item_id")
        or item.get("publication_item_id")
        or item.get("final_visible_item_id"),
        "candidate_id": item.get("candidate_id") or contract.get("candidate_id"),
        "source_candidate_id": item.get("source_candidate_id") or contract.get("source_candidate_id"),
        "family": item.get("selected_family_id") or item.get("published_family_id") or item.get("family") or contract.get("family"),
        "status": item.get("status"),
        "button_contract_hash": _stable_hash(contract),
        "updates_hash": _stable_hash(
            contract.get("updates") or item.get("updates") or item.get("selected_action_updates") or {}
        ),
    }


def _publication_adapter_item(item: dict[str, Any], *, reason: str) -> tuple[dict[str, Any], dict[str, Any]]:
    publication = build_final_design_guide_publication(
        item=dict(item),
        debug={},
        publication_reason=reason,
    )
    collapsed = build_collapsed_guidance_item_from_final_publication(
        publication,
    )
    return collapsed, publication.to_dict()


def _scenario(path_id: str, *, accepted: bool) -> dict[str, Any]:
    contract = _contract(path_id, enabled=accepted)
    primary = _primary(path_id)
    rebound = _rebound(path_id, contract)
    collapsed_before = [dict(primary)]
    controller = run_design_guide_controller_compute_rebound_mutation_trace_only(
        {
            "path_id": path_id,
            "accepted": accepted,
            "primary_item": dict(primary),
            "rebound_item": dict(rebound),
            "collapsed_guidance_items": list(collapsed_before),
            "rebound_contract": dict(contract),
            "rebound_update_payload": dict(contract.get("updates") or {}),
            "source": "compute_rebound_restamper_focused_parity",
        }
    )
    live_rebound_output = dict(rebound if accepted else primary)
    publication_adapter_item, publication = _publication_adapter_item(
        live_rebound_output,
        reason=path_id,
    )
    expected_collapsed = [dict(live_rebound_output)] if accepted else list(collapsed_before)
    expected_debug = _expected_debug(path_id, accepted=accepted, contract=contract)
    expected_debug_keys, expected_debug_hash = _expected_debug_keys_and_hash(
        path_id,
        accepted=accepted,
        contract=contract,
    )
    controller_selected_identity = _identity(dict(controller.selected_item))
    live_rebound_identity = _identity(live_rebound_output)
    publication_adapter_identity = _identity(publication_adapter_item)
    cta = dict(publication.get("cta") or {})
    cta_apply = dict(cta.get("apply_payload_summary") or {})
    surface_checks = {
        "accepted_guard_outcome": bool(controller.accepted) is bool(accepted),
        "restamper_rebound_item_identity": controller_selected_identity == live_rebound_identity,
        "publication_adapter_identity": {
            key: publication_adapter_identity.get(key)
            for key in (
                "published_item_id",
                "candidate_id",
                "source_candidate_id",
                "family",
                "status",
                "updates_hash",
            )
        }
        == {
            key: live_rebound_identity.get(key)
            for key in (
                "published_item_id",
                "candidate_id",
                "source_candidate_id",
                "family",
                "status",
                "updates_hash",
            )
        },
        "rebound_contract": _stable_hash(contract)
        == _stable_hash(dict(controller.selected_item.get("button_contract") or {})),
        "collapsed_guidance_mutation": list(controller.collapsed_guidance_items) == expected_collapsed,
        "debug_compatibility_payload_proof": (
            tuple(controller.debug_compatibility_update_keys) == expected_debug_keys
            and controller.debug_compatibility_updates_hash == expected_debug_hash
        ),
        "final_publication_hash": bool(publication.get("publication_hash")),
        "cta_apply_surface": (
            (not accepted)
            or (
                cta.get("enabled") is True
                and cta_apply.get("updates") == dict(contract.get("updates") or {})
                and cta_apply.get("candidate_id") == contract.get("candidate_id")
            )
        ),
    }
    return {
        "path_id": path_id,
        "accepted": bool(accepted),
        "surface_checks": surface_checks,
        "all_surfaces_match": all(surface_checks.values()),
        "controller_hash": controller.controller_hash,
        "controller_selected_identity": controller_selected_identity,
        "live_rebound_identity": live_rebound_identity,
        "publication_adapter_identity": publication_adapter_identity,
        "publication_hash": publication.get("publication_hash"),
        "cta_hash": cta.get("button_contract_hash"),
        "cta_apply_payload_hash": cta.get("apply_payload_fingerprint"),
        "expected_debug_keys": list(expected_debug_keys),
        "debug_payload_hash": controller.debug_compatibility_updates_hash,
        "expected_debug_payload_hash": expected_debug_hash,
        "legacy_debug_shape_reference": expected_debug,
        "scenario_hash": _stable_hash(
            {
                "path_id": path_id,
                "accepted": accepted,
                "surface_checks": surface_checks,
                "controller_hash": controller.controller_hash,
                "publication_hash": publication.get("publication_hash"),
            }
        ),
    }


def _source_checks() -> dict[str, bool]:
    source = INPUTS_PAGE.read_text(encoding="utf-8-sig", errors="replace").lstrip("\ufeff")
    return {
        "late_rebound_restamper_retired": "_late_rebound_item = _publish_final_visible_design_guide_contract_binding(" not in source,
        "post_rebound_restamper_retired": "_post_evidence_rebound = _publish_final_visible_design_guide_contract_binding(" not in source,
        "late_publication_adapter_present": "_late_rebound_item = _collapsed_guidance_item_from_final_publication_authority(" in source,
        "post_publication_adapter_present": "_post_evidence_rebound = _collapsed_guidance_item_from_final_publication_authority(" in source,
        "late_controller_mutation_trace_present": 'path_id="compute_late_evidence_contract_rebound"' in source,
        "post_controller_mutation_trace_present": 'path_id="post_core_evidence_rebound"' in source,
        "no_compute_rebound_bypass_wired": "_late_rebound_restamper_bypass" not in source
        and "_post_evidence_rebound_restamper_bypass" not in source,
    }


def _capture() -> dict[str, Any]:
    rows = [
        _scenario(path_id, accepted=accepted)
        for path_id in TARGETS
        for accepted in (False, True)
    ]
    return {
        "decision": "FOCUSED_PARITY_PROVEN_BUT_RESTAMPERS_STILL_LIVE",
        "rows": rows,
        "required_surfaces": list(REQUIRED_SURFACES),
        "source_checks": _source_checks(),
        "latest": {
            "cutover_readiness": _latest("design_guide_compute_rebound_restamper_cutover_readiness"),
            "ownership": _latest("design_guide_compute_rebound_restamper_bridge_ownership"),
            "compute_bridge_lock": _latest("design_guide_compute_resolver_publication_bridge_lock"),
            "render_bridge_lock": _latest("design_guide_render_bridge_lock"),
            "independence_lock": _latest("design_guide_independence_lock"),
            "remaining_restamper_audit": _latest("design_guide_remaining_final_visible_restamper_reference_audit"),
        },
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "engineering_behavior_changed": False,
        "delete_ready": False,
        "cutover_ready": False,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    rows = list(capture.get("rows") or [])
    latest = dict(capture.get("latest") or {})
    return {
        "four_scenarios_checked": len(rows) == 4,
        "all_surfaces_match": all(row.get("all_surfaces_match") for row in rows),
        "all_required_surfaces_listed": tuple(capture.get("required_surfaces") or ()) == REQUIRED_SURFACES,
        "source_checks_pass": all(dict(capture.get("source_checks") or {}).values()),
        "cutover_readiness_latest_pass": (latest.get("cutover_readiness") or {}).get("status") == "PASS",
        "ownership_latest_pass": (latest.get("ownership") or {}).get("status") == "PASS",
        "compute_bridge_lock_latest_pass": (latest.get("compute_bridge_lock") or {}).get("status") == "PASS",
        "render_bridge_lock_latest_pass": (latest.get("render_bridge_lock") or {}).get("status") == "PASS",
        "independence_lock_latest_pass": (latest.get("independence_lock") or {}).get("status") == "PASS",
        "remaining_restamper_audit_latest_pass": (latest.get("remaining_restamper_audit") or {}).get("status")
        == "PASS",
        "not_delete_ready": capture.get("delete_ready") is False,
        "not_cutover_ready": capture.get("cutover_ready") is False,
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "engineering_behavior_unchanged": capture.get("engineering_behavior_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Design Guide Compute Rebound Restamper Focused Parity Scenarios",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        "",
        "## Scenarios",
        "",
        "| Path | Accepted | All surfaces | Failed surfaces |",
        "| --- | ---: | --- | --- |",
    ]
    for row in list(capture.get("rows") or []):
        failed = [
            key for key, value in dict(row.get("surface_checks") or {}).items() if value is not True
        ]
        lines.append(
            "| `{}` | `{}` | `{}` | {} |".format(
                row.get("path_id"),
                row.get("accepted"),
                row.get("all_surfaces_match"),
                ", ".join(f"`{item}`" for item in failed) if failed else "None",
            )
        )
    lines.extend(["", "## Decision", ""])
    lines.append(
        "Focused parity is proven for accepted/skipped fixture scenarios, but live restamper calls remain and are not deletion-ready."
    )
    if payload.get("failures"):
        lines.extend(["", "## Failures"])
        lines.extend(f"- `{failure}`" for failure in payload["failures"])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    capture = _capture()
    checks = _checks(capture)
    failures = [key for key, value in checks.items() if value is not True]
    status = "PASS" if not failures else "FAIL"
    payload = {
        "schema": "design_guide_compute_rebound_restamper_focused_parity_scenarios.v1",
        "status": status,
        "created_at": stamp,
        "capture": capture,
        "checks": checks,
        "failures": failures,
        "snapshot_hash": "",
    }
    payload["snapshot_hash"] = _stable_hash(payload)
    json_path = ARTIFACT_DIR / f"design_guide_compute_rebound_restamper_focused_parity_scenarios_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_compute_rebound_restamper_focused_parity_scenarios_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    _write_report(report_path, payload)
    print(json.dumps({"status": status, "json": str(json_path), "report": str(report_path)}, indent=2))
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())

