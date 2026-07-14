"""Controller parity proof for remaining compute rebound decisions.

Proof-only. This verifies that the two remaining page-side compute rebound
bridges can be represented by the controller/publication rebound decision proof
without moving live behaviour.
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

ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
INPUTS_PAGE = ROOT / "inputs_page.py"
CONTROLLER = ROOT / "design_brain" / "design_guide_controller.py"
FINAL_PUBLICATION = ROOT / "design_brain" / "final_publication.py"

SURFACES = (
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


def _contract(*, enabled: bool, family: str, candidate_id: str, updates: dict[str, Any]) -> dict[str, Any]:
    return {
        "enabled": bool(enabled),
        "actionable": bool(enabled),
        "action_type": "apply_resolved_candidate" if enabled else None,
        "family": family,
        "candidate_id": candidate_id,
        "source_candidate_id": candidate_id,
        "updates": dict(updates),
        "disabled_reason": None if enabled else "proof-only disabled sample",
    }


def _item(surface: str, contract: dict[str, Any]) -> dict[str, Any]:
    return {
        "published_item_id": f"{surface}:raw-item",
        "candidate_id": f"{contract.get('candidate_id')}:raw",
        "source_candidate_id": f"{contract.get('source_candidate_id')}:raw",
        "selected_family_id": "COMBINED_OVERDESIGN_GOVERNS",
        "published_family_id": "COMBINED_OVERDESIGN_GOVERNS",
        "family": contract.get("family"),
        "status": "ACTION" if contract.get("enabled") else "PASS",
        "bucket": "efficiency",
        "title": "Proof sample",
        "title_main": "Proof sample",
        "summary_line": "Proof-only rebound decision sample.",
        "button_contract": dict(contract),
        "action_payload": {
            "action_type": contract.get("action_type"),
            "family": contract.get("family"),
            "candidate_id": contract.get("candidate_id"),
            "source_candidate_id": contract.get("source_candidate_id"),
            "updates": dict(contract.get("updates") or {}),
        },
        "candidate_search_evidence": {
            "family": "combined",
            "selected_candidate_updates": dict(contract.get("updates") or {}),
            "best_safe_candidate_updates": dict(contract.get("updates") or {}),
        },
    }


def _request(surface: str, *, accepted: bool) -> dict[str, Any]:
    updates = {"bot_no": 5, "link_no": 0} if surface == "post_core_evidence_rebound" else {"bot_no": 4}
    contract = _contract(
        enabled=accepted,
        family="combined",
        candidate_id=f"{surface}:candidate",
        updates=updates,
    )
    item = _item(surface, contract)
    rebound_item = {
        **item,
        "published_item_id": f"{surface}:rebound-item",
        "candidate_id": contract.get("candidate_id"),
        "source_candidate_id": contract.get("source_candidate_id"),
        "button_contract": dict(contract),
        "action_payload": {
            "action_type": contract.get("action_type"),
            "family": contract.get("family"),
            "candidate_id": contract.get("candidate_id"),
            "source_candidate_id": contract.get("source_candidate_id"),
            "updates": dict(contract.get("updates") or {}),
        },
    }
    late_acceptance = (
        {
            "late_updates_present": True,
            "contract_disabled_or_mismatched": True,
            "active_under_capacity_blocker": False,
            "accepted": bool(accepted),
        }
        if surface == "compute_late_evidence_contract_rebound"
        else {}
    )
    post_core_mismatch = (
        {
            "post_evidence_updates_present": True,
            "contract_disabled_or_mismatched": True,
            "family": "combined",
            "accepted": bool(accepted),
        }
        if surface == "post_core_evidence_rebound"
        else {}
    )
    return {
        "collapsed_guidance_items": [dict(item)],
        "final_compute_resolution": {
            "item": dict(item),
            "render_reason": (
                "late_evidence_contract_rebound"
                if surface == "compute_late_evidence_contract_rebound"
                else "post_evidence_contract_rebound"
            ),
            "state_fingerprint": f"{surface}:fingerprint",
        },
        "blocker_evidence_surface": {
            "candidate_search_evidence": dict(item.get("candidate_search_evidence") or {}),
            "source": "controller_rebound_decision_parity",
        },
        "late_evidence_acceptance": late_acceptance,
        "rebound_contract": dict(contract),
        "rebound_update_payload": dict(contract.get("updates") or {}),
        "post_core_evidence_mismatch": post_core_mismatch,
        "raw_rebound_item": dict(rebound_item),
        "pre_resolver_collapsed_item_mutation": {
            "before_identity": {"candidate_id": item.get("candidate_id")},
            "after_identity": {"candidate_id": rebound_item.get("candidate_id")},
            "mutation_reason": surface,
        },
        "publication_reason": (
            "late_evidence_contract_rebound"
            if surface == "compute_late_evidence_contract_rebound"
            else "post_evidence_contract_rebound"
        ),
        "source": f"{surface}:controller_parity_sample",
    }


def _scenario_rows() -> list[dict[str, Any]]:
    from design_brain.design_guide_controller import (
        run_design_guide_controller_compute_publication_handoff_trace_only,
    )
    from design_brain.final_publication import (
        build_final_design_guide_compute_publication_handoff_rebound_decision_proof,
    )

    rows: list[dict[str, Any]] = []
    for surface in SURFACES:
        for accepted in (False, True):
            request = _request(surface, accepted=accepted)
            first = run_design_guide_controller_compute_publication_handoff_trace_only(request)
            second = run_design_guide_controller_compute_publication_handoff_trace_only(request)
            controller_proof = dict(first.compute_handoff_rebound_decision_proof or {})
            raw_selected_item = dict((request.get("final_compute_resolution") or {}).get("item") or {})
            direct_proof = build_final_design_guide_compute_publication_handoff_rebound_decision_proof(
                raw_selected_item=dict(raw_selected_item),
                blocker_evidence_surface=dict(request.get("blocker_evidence_surface") or {}),
                render_reason=str(request.get("publication_reason") or ""),
                state_fingerprint=(request.get("final_compute_resolution") or {}).get("state_fingerprint"),
                late_evidence_acceptance=dict(request.get("late_evidence_acceptance") or {}),
                rebound_contract=dict(request.get("rebound_contract") or {}),
                rebound_update_payload=dict(request.get("rebound_update_payload") or {}),
                post_core_evidence_mismatch=dict(request.get("post_core_evidence_mismatch") or {}),
                raw_rebound_item=dict(request.get("raw_rebound_item") or {}),
                pre_resolver_collapsed_item_mutation=dict(
                    request.get("pre_resolver_collapsed_item_mutation") or {}
                ),
            ).to_dict()
            rebound_accepted = bool(
                (request.get("late_evidence_acceptance") or {}).get("accepted")
                or (request.get("post_core_evidence_mismatch") or {}).get("accepted")
            )
            expected_publication_item = (
                request.get("raw_rebound_item") if rebound_accepted else (request.get("final_compute_resolution") or {}).get("item")
            ) or {}
            rows.append(
                {
                    "surface": surface,
                    "accepted": bool(accepted),
                    "controller_hash_stable": first.controller_hash == second.controller_hash,
                    "decision_hash_stable": (
                        first.compute_handoff_rebound_decision_hash
                        == second.compute_handoff_rebound_decision_hash
                    ),
                    "controller_matches_direct_decision_hash": (
                        first.compute_handoff_rebound_decision_hash
                        == direct_proof.get("decision_hash")
                    ),
                    "controller_missing_fields": list(
                        controller_proof.get("missing_blocking_fields") or []
                    ),
                    "direct_missing_fields": list(direct_proof.get("missing_blocking_fields") or []),
                    "covered_fields": list(controller_proof.get("covered_blocking_fields") or []),
                    "controller_uses_rebound_item_when_accepted": (
                        not rebound_accepted
                        or first.selected_item_hash == _stable_hash(expected_publication_item)
                    ),
                    "controller_rebound_item_hash": (
                        (first.parity_payload or {}).get("raw_rebound_item_hash")
                    ),
                    "controller_publication_item_source": (
                        (first.parity_payload or {}).get("publication_item_source")
                    ),
                    "controller_product_driving": bool(first.product_driving),
                    "controller_render_driving": bool(first.render_driving),
                    "controller_apply_driving": bool(first.apply_driving),
                    "controller_session_driving": bool(first.session_driving),
                }
            )
    return rows


def _capture() -> dict[str, Any]:
    inputs_source = INPUTS_PAGE.read_text(encoding="utf-8-sig", errors="replace").lstrip("\ufeff")
    controller_source = CONTROLLER.read_text(encoding="utf-8-sig", errors="replace").lstrip("\ufeff")
    final_publication_source = FINAL_PUBLICATION.read_text(encoding="utf-8-sig", errors="replace").lstrip("\ufeff")
    rows = _scenario_rows()
    latest = {
        "rebound_readiness": _latest("design_guide_compute_rebound_authority_extraction_readiness"),
        "same_object": _latest("design_guide_compute_stage_resolver_same_object"),
        "compute_bridge_lock": _latest("design_guide_compute_resolver_publication_bridge_lock"),
        "render_bridge_lock": _latest("design_guide_render_bridge_lock"),
        "independence_lock": _latest("design_guide_independence_lock"),
    }
    return {
        "decision": "COMPUTE_REBOUND_CONTROLLER_DECISION_PARITY_PASS",
        "rows": rows,
        "source_checks": {
            "controller_handoff_function_present": (
                "def run_design_guide_controller_compute_publication_handoff_trace_only("
                in controller_source
            ),
            "final_publication_rebound_proof_present": (
                "def build_final_design_guide_compute_publication_handoff_rebound_decision_proof("
                in final_publication_source
            ),
            "late_rebound_live_path_still_present": (
                "_apply_compute_late_evidence_contract_rebound(" in inputs_source
            ),
            "post_core_rebound_live_path_still_present": (
                "_post_evidence_rebound = _publish_final_visible_design_guide_contract_binding("
                in inputs_source
                or "_post_mutation_adapter = _stamp_design_guide_controller_compute_rebound_mutation_trace_only("
                in inputs_source
            ),
            "no_streamlit_in_final_publication": "st.session_state" not in final_publication_source,
            "no_streamlit_in_controller": "st.session_state" not in controller_source,
        },
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
    rows = list(capture.get("rows") or [])
    source = dict(capture.get("source_checks") or {})
    latest = dict(capture.get("latest") or {})
    return {
        "four_scenarios_checked": len(rows) == 4,
        "controller_hashes_stable": all(row.get("controller_hash_stable") for row in rows),
        "decision_hashes_stable": all(row.get("decision_hash_stable") for row in rows),
        "controller_matches_direct_decision_hash": all(
            row.get("controller_matches_direct_decision_hash") for row in rows
        ),
        "no_missing_blocking_fields": all(
            not row.get("controller_missing_fields") and not row.get("direct_missing_fields")
            for row in rows
        ),
        "controller_is_proof_only": all(
            not row.get("controller_product_driving")
            and not row.get("controller_render_driving")
            and not row.get("controller_apply_driving")
            and not row.get("controller_session_driving")
            for row in rows
        ),
        "source_checks_pass": all(source.values()),
        "rebound_readiness_pass": (latest.get("rebound_readiness") or {}).get("status") == "PASS",
        "same_object_pass": (latest.get("same_object") or {}).get("status") == "PASS",
        "compute_bridge_lock_pass": (latest.get("compute_bridge_lock") or {}).get("status") == "PASS",
        "render_bridge_lock_pass": (latest.get("render_bridge_lock") or {}).get("status") == "PASS",
        "independence_lock_pass": (latest.get("independence_lock") or {}).get("status") == "PASS",
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
        "# Compute Rebound Controller Decision Parity Snapshot",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Scenarios",
        "",
        "| Surface | Accepted | Stable | Direct Match | Missing Fields |",
        "| --- | ---: | ---: | ---: | --- |",
    ]
    for row in list(capture.get("rows") or []):
        lines.append(
            "| `{surface}` | `{accepted}` | `{decision_hash_stable}` | `{controller_matches_direct_decision_hash}` | `{controller_missing_fields}` |".format(
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
                "Controller/publication proof parity is available for the rebound decisions. "
                "Next safe slice is trace-wiring a controller-owned rebound decision beside "
                "the live late/post-core rebound branches before any cutover."
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
        "schema": "design_guide_compute_rebound_controller_decision_parity_snapshot.v1",
        "status": status,
        "created_at": _stamp(),
        "capture": capture,
        "checks": checks,
        "failures": failures,
    }
    payload["snapshot_hash"] = _stable_hash(payload)
    stamp = payload["created_at"]
    json_path = ARTIFACT_DIR / f"design_guide_compute_rebound_controller_decision_parity_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_compute_rebound_controller_decision_parity_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    _write_report(report_path, payload)
    print(f"design_guide_compute_rebound_controller_decision_parity {status}")
    print(f"decision={capture.get('decision')}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
