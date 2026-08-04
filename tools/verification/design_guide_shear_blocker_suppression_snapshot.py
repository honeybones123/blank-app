"""Proof that safe shear repair evidence suppresses late blocker publication.

This is a narrow regression guard for the failure mode where SHEAR_FAIL_GOVERNS
candidate evidence exists, but the page's late active-under-capacity materializer
turns the final card back into a blocker.
"""

from __future__ import annotations

import hashlib
import json
import sys
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


def _stable_hash(value: Any) -> str:
    try:
        raw = json.dumps(value, sort_keys=True, default=str, separators=(",", ":"))
    except TypeError:
        raw = repr(value)
    return hashlib.sha256(raw.encode("utf-8", errors="replace")).hexdigest()[:16]


def _safe_shear_evidence() -> dict[str, Any]:
    safe_row = {
        "candidate_id": "shear_fail_contract_runtime_safe_spacing_dia",
        "title": "Shear capacity is low",
        "updates": {"s_lig": 100.0, "lig_d": 12},
        "proposed_updates": {"s_lig": 100.0, "lig_d": 12},
        "preview_pass": True,
        "safe_executor_backed": True,
        "is_executable": True,
        "preview_shear_util": 0.94,
        "preview_util": 0.96,
    }
    return {
        "family": "shear",
        "governing_family": "SHEAR_FAIL_GOVERNS",
        "search_scope": "shear_fail_governs_contract_runtime",
        "active_failures": ["shear"],
        "candidate_search_exhaustive": True,
        "repair_search_ran": True,
        "repair_search_exhaustive": True,
        "shear_fail_contract_ladder_attempted": True,
        "shear_fail_contract_ladder_used": True,
        "shear_fail_contract_ladder_candidate_count": 4,
        "safe_candidate_count": 1,
        "executable_candidate_count": 1,
        "safe_executor_backed_candidates_count": 1,
        "safe_executor_backed_candidates": [dict(safe_row)],
        "active_fail_repair_candidate_rows": [dict(safe_row)],
        "candidate_rows": [dict(safe_row)],
        "selected_candidate_id": safe_row["candidate_id"],
        "selected_candidate_updates": dict(safe_row["updates"]),
        "selected_candidate_util": 0.96,
        "closest_safe_candidate_id": safe_row["candidate_id"],
        "closest_safe_candidate_updates": dict(safe_row["updates"]),
        "closest_safe_candidate_util": 0.96,
        "active_under_capacity_blocker": True,
        "active_under_capacity_blocker_family": "shear",
        "active_under_capacity_blocker_reason": "stale blocker should be suppressed",
        "exact_blockers_by_family": {
            "shear": {
                "family": "shear",
                "reason": "stale blocker should be suppressed",
            }
        },
        "post_click_exact_blockers_by_family": {
            "shear": {
                "family": "shear",
                "reason": "stale blocker should be suppressed",
            }
        },
    }


def _primary_item(evidence: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": "stale_shear_blocker_primary",
        "candidate_id": "stale_shear_blocker_primary",
        "source_candidate_id": "stale_shear_blocker_primary",
        "family": "shear",
        "check_key": "shear",
        "selected_family_id": "SHEAR_FAIL_GOVERNS",
        "published_family_id": "SHEAR_FAIL_GOVERNS",
        "cta_family_id": "SHEAR_FAIL_GOVERNS",
        "title_main": "Shear repair blocked by shear/detailing limits",
        "title": "Shear repair blocked by shear/detailing limits",
        "primary_action": "No one-click shear repair is available",
        "secondary_action": "Stale blocked wording",
        "reasoning": "Why: stale blocked wording",
        "status": "FAIL",
        "guidance_intent": "specific_blocker",
        "final_state_class": "blocker",
        "primary_card_actionable": False,
        "action_type": None,
        "updates": {},
        "candidate_search_evidence": dict(evidence),
        "button_contract": {
            "enabled": False,
            "actionable": False,
            "action_type": None,
            "family": "shear",
            "updates": {},
            "preview_pass": False,
            "blocking_reason": "stale blocker should be suppressed",
        },
    }


def _run() -> dict[str, Any]:
    import importlib

    inputs_page = importlib.import_module("inputs_page")
    evidence = _safe_shear_evidence()
    primary = _primary_item(evidence)
    debug_trace = {
        "overview": {
            "statuses": {"bending": "PASS", "shear": "FAIL", "crack": "PASS", "deflection": "PASS"},
            "utils": {"bending": 0.96, "shear": 12.12, "crack": 0.0, "deflection": 0.0},
        }
    }
    result = inputs_page._materialize_compute_active_under_capacity_blocker(
        active_blocker_family_for_evidence="shear",
        primary_item_for_evidence=primary,
        existing_evidence=evidence,
        debug_trace=debug_trace,
    )
    contract = dict(primary.get("button_contract") or {})
    final_evidence = dict(primary.get("candidate_search_evidence") or {})
    updates = dict(primary.get("updates") or {})
    exact = dict(final_evidence.get("exact_blockers_by_family") or {})
    failures: list[str] = []
    if result.get("suppressed") is not True or result.get("materialized") is not False:
        failures.append("materializer_did_not_report_suppression")
    if primary.get("action_type") != "apply_resolved_candidate":
        failures.append("primary_not_actionable_repair")
    if contract.get("enabled") is not True or contract.get("actionable") is not True:
        failures.append("enabled_contract_missing")
    if contract.get("blocking_reason") is not None:
        failures.append("blocking_reason_not_cleared")
    if not updates or not (set(updates) & inputs_page._COMPOUND_SHEAR_UPDATE_KEYS):
        failures.append("shear_updates_missing")
    if final_evidence.get("active_under_capacity_blocker") is not False:
        failures.append("active_under_capacity_blocker_not_cleared")
    if final_evidence.get("safe_executor_backed_candidates_count", 0) < 1:
        failures.append("safe_executor_backed_count_not_preserved")
    if exact.get("shear"):
        failures.append("stale_shear_exact_blocker_not_removed")
    if debug_trace.get("active_under_capacity_blocker_suppressed_by_safe_repair") is not True:
        failures.append("debug_trace_not_stamped")
    return {
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "result": result,
        "primary_summary": {
            "title": primary.get("title"),
            "family": primary.get("family"),
            "action_type": primary.get("action_type"),
            "primary_card_actionable": primary.get("primary_card_actionable"),
            "final_state_class": primary.get("final_state_class"),
            "updates": updates,
            "candidate_id": primary.get("candidate_id"),
            "source_candidate_id": primary.get("source_candidate_id"),
        },
        "button_contract": contract,
        "evidence_summary": {
            "active_under_capacity_blocker": final_evidence.get("active_under_capacity_blocker"),
            "safe_executor_backed_candidates_count": final_evidence.get("safe_executor_backed_candidates_count"),
            "selected_candidate_id": final_evidence.get("selected_candidate_id"),
            "selected_candidate_updates": dict(final_evidence.get("selected_candidate_updates") or {}),
            "exact_blockers_by_family": exact,
            "outside_target_band_allowed": final_evidence.get("outside_target_band_allowed"),
        },
        "hashes": {
            "primary": _stable_hash(primary),
            "evidence": _stable_hash(final_evidence),
            "contract": _stable_hash(contract),
        },
    }


def _write_report(payload: dict[str, Any], path: Path) -> None:
    lines = [
        "# Design Guide Shear Blocker Suppression Snapshot",
        "",
        f"Status: `{payload['status']}`",
        "",
        "## Summary",
        "",
        "Safe executor-backed `SHEAR_FAIL_GOVERNS` repair evidence must suppress stale active-under-capacity blocker publication.",
        "",
        "## Primary",
        "",
        f"- Action type: `{payload['primary_summary'].get('action_type')}`",
        f"- Updates: `{payload['primary_summary'].get('updates')}`",
        f"- Contract enabled: `{payload['button_contract'].get('enabled')}`",
        f"- Active blocker: `{payload['evidence_summary'].get('active_under_capacity_blocker')}`",
        "",
        "## Failures",
        "",
    ]
    if payload["failures"]:
        lines.extend(f"- `{failure}`" for failure in payload["failures"])
    else:
        lines.append("- None")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y-%m-%dT%H-%M-%S")
    artifact_path = ARTIFACT_DIR / f"design_guide_shear_blocker_suppression_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_shear_blocker_suppression_{stamp}.md"
    payload = {
        "schema": "design_guide_shear_blocker_suppression_snapshot.v1",
        **_run(),
        "artifact": str(artifact_path),
        "report": str(report_path),
    }
    artifact_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    _write_report(payload, report_path)
    print(f"{payload['status']}: {artifact_path}")
    print(f"REPORT: {report_path}")
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
