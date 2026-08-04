"""Proof-only chooser-priority audit for BENDING_FAIL_SHEAR_OVERDESIGN.

This audit answers whether the bending-fail + shear-overdesign state is intended
to be a selectable mixed family, why the current chooser prunes it, and which
family id is authoritative in the global classification contract.

No product behavior, runtime logic, CTA/publication/apply routing, or visible
wording is changed by this verifier.
"""

from __future__ import annotations

import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from design_brain.family_chooser import classify_family_from_raw_flags  # noqa: E402
from design_brain.family_classification_runtime import classify_family_from_whole_beam_evidence  # noqa: E402

ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"

OLD_ID = "BENDING_FAIL_SHEAR_OPTIMISE_GOVERNS"
NEW_ID = "BENDING_FAIL_SHEAR_OVERDESIGN_GOVERNS"
PLAIN_ID = "BENDING_FAIL_GOVERNS"


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8", errors="ignore")


def _load_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _latest(pattern: str) -> dict[str, Any]:
    matches = sorted(ARTIFACT_DIR.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)
    if not matches:
        return {"found": False, "pattern": pattern, "path": None, "payload": {}}
    path = matches[0]
    return {"found": True, "pattern": pattern, "path": str(path), "payload": _load_json(path)}


def _extract_contract_summary() -> dict[str, Any]:
    contract = json.loads(_read("design_brain/contracts/family_classification_contract.json"))
    rules = dict(contract.get("classification_rules") or {})
    allowed = list(contract.get("allowed_family_ids") or [])
    priority = list(contract.get("classification_priority_order") or [])
    old_rule = dict(rules.get(OLD_ID) or {})
    new_rule = dict(rules.get(NEW_ID) or {})
    return {
        "contract_path": "design_brain/contracts/family_classification_contract.json",
        "old_id": OLD_ID,
        "new_id": NEW_ID,
        "old_id_allowed": OLD_ID in allowed,
        "old_id_priority_index": priority.index(OLD_ID) + 1 if OLD_ID in priority else None,
        "old_id_has_rule": bool(old_rule),
        "old_rule_condition_summary": old_rule.get("condition_summary"),
        "old_rule_purpose": old_rule.get("purpose"),
        "new_id_allowed": NEW_ID in allowed,
        "new_id_priority_index": priority.index(NEW_ID) + 1 if NEW_ID in priority else None,
        "new_id_has_rule": bool(new_rule),
        "allowed_family_ids": allowed,
        "classification_priority_order": priority,
    }


def _extract_source_summary() -> dict[str, Any]:
    runtime = _read("design_brain/family_classification_runtime.py")
    chooser = _read("design_brain/family_chooser.py")
    return {
        "runtime_has_old_predicate": f'"{OLD_ID}"' in runtime,
        "runtime_has_new_predicate": f'"{NEW_ID}"' in runtime,
        "runtime_old_before_plain_bending": runtime.find(f'"{OLD_ID}"') != -1
        and runtime.find(f'"{OLD_ID}"') < runtime.find(f'"{PLAIN_ID}"'),
        "chooser_has_new_definition": f'"{NEW_ID}"' in chooser,
        "chooser_has_old_definition": f'"{OLD_ID}"' in chooser,
        "chooser_prunes_new_when_plain_bending_matches": bool(
            re.search(
                rf"{re.escape(PLAIN_ID)}[\s\S]{{0,220}}{re.escape(NEW_ID)}[\s\S]{{0,260}}if family != \"{re.escape(NEW_ID)}\"",
                chooser,
            )
        )
        or (
            "_prune_secondary_overdesign_matches" in chooser
            and f'family != "{NEW_ID}"' in chooser
            and f'"{PLAIN_ID}" in out' in chooser
        ),
        "chooser_prune_function_present": "_prune_secondary_overdesign_matches" in chooser,
        "chooser_rejection_reason_overdesign_active_failure": "rejected because failure state is active" in chooser,
    }


def _fixture_results() -> dict[str, Any]:
    evidence = {
        "bending_utilisation": 1.20,
        "shear_utilisation": 0.50,
        "bending_state": "FAIL",
        "shear_state": "OVERDESIGNED",
        "serviceability_state": "PASS",
        "geometry_detailing_state": "PASS",
        "minimum_bending_reo_state": "PASS",
        "minimum_shear_reo_state": "PASS",
        "geometry_locked": False,
        "reo_locked": False,
        "can_strengthen_bending": True,
        "can_strengthen_shear": False,
        "can_optimise_bending_without_hurting_shear": False,
        "can_optimise_shear_without_hurting_bending": True,
        "exact_stop_available": False,
        "no_valid_repair_available": False,
    }
    raw_flags = {
        "active_combined_bending_shear_failure": False,
        "any_failure": True,
        "any_min_reo_fail": False,
        "any_overdesign": True,
        "any_strength_fail": True,
        "bending_acceptable": False,
        "bending_fail": True,
        "bending_overdesigned": False,
        "bending_within_target_band": False,
        "exact_stop_proven": False,
        "geometry_detailing_fail": False,
        "legal_repair_exists": True,
        "locked_repair_blocked": False,
        "min_bending_reo_fail": False,
        "min_shear_reo_fail": False,
        "repair_required": False,
        "serviceability_fail": False,
        "shear_acceptable": False,
        "shear_fail": False,
        "shear_overdesigned": True,
        "shear_within_target_band": False,
    }
    contract_runtime = classify_family_from_whole_beam_evidence(evidence)
    chooser = classify_family_from_raw_flags(raw_flags)
    chooser_evidence = dict(chooser.get("selection_evidence") or {})
    return {
        "whole_beam_evidence": evidence,
        "raw_flags": raw_flags,
        "contract_runtime_selected_family_id": contract_runtime.get("selected_family_id"),
        "contract_runtime_matched_family_ids": list(contract_runtime.get("matched_family_ids") or []),
        "contract_runtime_priority": contract_runtime.get("classification_priority"),
        "chooser_selected_family_id": chooser.get("selected_family_id"),
        "chooser_matched_family_ids": list(chooser.get("matched_family_ids") or []),
        "chooser_raw_matched_family_ids": list(chooser_evidence.get("raw_matched_family_ids") or []),
        "chooser_secondary_overdesign_match_pruned": bool(
            chooser_evidence.get("secondary_overdesign_match_pruned")
        ),
        "chooser_rejected_new_id_reason": dict(chooser.get("rejected_families") or {}).get(NEW_ID),
    }


def _artifact_summary() -> dict[str, Any]:
    lock = _latest("bending_fail_shear_overdesign_governs_lock_verifier_*.json")
    replacement = _latest("bending_fail_shear_overdesign_governs_replacement_audit_*.json")
    lock_payload = dict(lock.get("payload") or {})
    replacement_payload = dict(replacement.get("payload") or {})
    lock_chooser = dict(lock_payload.get("chooser") or {})
    replacement_chooser = dict(replacement_payload.get("chooser_result") or {})
    return {
        "lock_artifact": {k: v for k, v in lock.items() if k != "payload"},
        "replacement_artifact": {k: v for k, v in replacement.items() if k != "payload"},
        "lock_result": lock_payload.get("result") or lock_payload.get("status"),
        "lock_failures": list(lock_payload.get("failures") or []),
        "lock_checks": dict(lock_payload.get("checks") or {}),
        "lock_selected_family": lock_chooser.get("selected_family_id"),
        "lock_matched_family_ids": list(lock_chooser.get("matched_family_ids") or []),
        "lock_raw_matched_family_ids": list(
            (dict(lock_chooser.get("selection_evidence") or {})).get("raw_matched_family_ids") or []
        ),
        "replacement_result": replacement_payload.get("result") or replacement_payload.get("status"),
        "replacement_failures": list(replacement_payload.get("failures") or []),
        "replacement_checks": dict(replacement_payload.get("checks") or {}),
        "replacement_selected_family": replacement_chooser.get("selected_family_id"),
        "replacement_matched_family_ids": list(replacement_chooser.get("matched_family_ids") or []),
        "replacement_raw_matched_family_ids": list(
            (dict(replacement_chooser.get("selection_evidence") or {})).get("raw_matched_family_ids") or []
        ),
    }


def _decision(contract: dict[str, Any], source: dict[str, Any], fixture: dict[str, Any], artifacts: dict[str, Any]) -> dict[str, Any]:
    intended_selectable = bool(
        contract["new_id_allowed"]
        and contract["new_id_has_rule"]
        and source["runtime_has_new_predicate"]
        and fixture["contract_runtime_selected_family_id"] == NEW_ID
    )
    current_new_package_selectable = bool(
        source["chooser_has_new_definition"]
        and NEW_ID in fixture["chooser_raw_matched_family_ids"]
        and fixture["chooser_selected_family_id"] == NEW_ID
    )
    chooser_prunes_new = bool(
        fixture["chooser_secondary_overdesign_match_pruned"]
        and fixture["chooser_selected_family_id"] == PLAIN_ID
        and NEW_ID in fixture["chooser_raw_matched_family_ids"]
    )
    authoritative_name = NEW_ID if contract["new_id_allowed"] and contract["new_id_has_rule"] else (
        OLD_ID if contract["old_id_allowed"] and contract["old_id_has_rule"] else "UNRESOLVED"
    )
    if intended_selectable and current_new_package_selectable and authoritative_name == NEW_ID:
        recommendation = (
            "resolved: global contract, classification runtime, and page-facing chooser all select "
            f"{NEW_ID}; keep old optimise id as compatibility alias only."
        )
    elif intended_selectable and authoritative_name == OLD_ID:
        recommendation = (
            "selectable_but_name_drifted: keep the mixed family concept, then reconcile "
            f"{NEW_ID} with authoritative contract id {OLD_ID} before any runtime or CTA work."
        )
    elif not intended_selectable and chooser_prunes_new:
        recommendation = (
            "retire_or_alias_new_package_to_plain_bending_fail: current chooser behavior treats "
            "shear overdesign as secondary evidence under BENDING_FAIL_GOVERNS."
        )
    else:
        recommendation = "unresolved: classification intent and chooser behavior need manual decision."
    return {
        "is_mixed_family_intended_selectable": intended_selectable,
        "current_new_package_selectable": current_new_package_selectable,
        "why_chooser_prunes": (
            "_prune_secondary_overdesign_matches removes BENDING_FAIL_SHEAR_OVERDESIGN_GOVERNS "
            "whenever BENDING_FAIL_GOVERNS also matches and bending fails while shear does not fail."
            if chooser_prunes_new
            else "chooser did not prune the new mixed family in the fixture"
        ),
        "should_retire_or_alias": (
            "do_not_retire_yet; alias/rename/reconcile required because global contract has a selectable mixed-family rule"
            if intended_selectable
            else "safe_to_consider_retirement_or_alias_if BENDING_FAIL_GOVERNS contract owns shear-overdesign cleanup evidence"
        ),
        "authoritative_contract_name": authoritative_name,
        "old_id_authoritative": authoritative_name == OLD_ID,
        "new_id_authoritative": authoritative_name == NEW_ID,
        "recommended_next_step": recommendation,
        "replacement_audit_failure_explained": (
            artifacts.get("replacement_failures") == ["chooser_selects_mixed_family"]
            or artifacts.get("replacement_result") == "PASS"
        ),
        "lock_failure_explained": (
            "chooser_selects_family" in list(artifacts.get("lock_failures") or [])
            or artifacts.get("lock_result") == "PASS"
        ),
    }


def _write_report(payload: dict[str, Any], path: Path) -> None:
    decision = dict(payload.get("decision") or {})
    lines = [
        "# BENDING_FAIL_SHEAR_OVERDESIGN Chooser Priority Audit",
        "",
        f"Status: `{payload['status']}`",
        f"Product behaviour changed: `{payload['product_behaviour_changed']}`",
        "",
        "## Executive Summary",
        "",
        f"- Intended selectable mixed family: `{decision.get('is_mixed_family_intended_selectable')}`",
        f"- Current new package selectable: `{decision.get('current_new_package_selectable')}`",
        f"- Authoritative contract name: `{decision.get('authoritative_contract_name')}`",
        f"- Should retire or alias: `{decision.get('should_retire_or_alias')}`",
        f"- Recommended next step: `{decision.get('recommended_next_step')}`",
        "",
        "## Contract vs Chooser",
        "",
        f"- Global contract old id allowed: `{payload['contract']['old_id_allowed']}`",
        f"- Global contract old id priority: `{payload['contract']['old_id_priority_index']}`",
        f"- Global contract new id allowed: `{payload['contract']['new_id_allowed']}`",
        f"- Runtime has old predicate: `{payload['source']['runtime_has_old_predicate']}`",
        f"- Runtime has new predicate: `{payload['source']['runtime_has_new_predicate']}`",
        f"- Chooser has new definition: `{payload['source']['chooser_has_new_definition']}`",
        f"- Chooser prunes new mixed family: `{payload['source']['chooser_prunes_new_when_plain_bending_matches']}`",
        "",
        "## Fixture Result",
        "",
        f"- Contract runtime selected: `{payload['fixture']['contract_runtime_selected_family_id']}`",
        f"- Contract runtime matched: `{payload['fixture']['contract_runtime_matched_family_ids']}`",
        f"- Chooser selected: `{payload['fixture']['chooser_selected_family_id']}`",
        f"- Chooser raw matched: `{payload['fixture']['chooser_raw_matched_family_ids']}`",
        f"- Chooser matched after prune: `{payload['fixture']['chooser_matched_family_ids']}`",
        f"- Chooser prune flag: `{payload['fixture']['chooser_secondary_overdesign_match_pruned']}`",
        "",
        "## Latest Artifacts",
        "",
        f"- Lock artifact: `{payload['artifacts']['lock_artifact'].get('path')}`",
        f"- Lock result: `{payload['artifacts']['lock_result']}`",
        f"- Lock failures: `{payload['artifacts']['lock_failures']}`",
        f"- Replacement artifact: `{payload['artifacts']['replacement_artifact'].get('path')}`",
        f"- Replacement result: `{payload['artifacts']['replacement_result']}`",
        f"- Replacement failures: `{payload['artifacts']['replacement_failures']}`",
        "",
        "## Answer",
        "",
        "The mixed family concept is contract-intended as selectable. The authoritative global classification id is "
        f"`{decision.get('authoritative_contract_name')}` and the page-facing chooser fixture selects `{payload['fixture']['chooser_selected_family_id']}`.",
    ]
    if payload.get("failures"):
        lines.extend(["", "## Failures", ""])
        for failure in payload["failures"]:
            lines.append(f"- `{failure}`")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    contract = _extract_contract_summary()
    source = _extract_source_summary()
    fixture = _fixture_results()
    artifacts = _artifact_summary()
    decision = _decision(contract, source, fixture, artifacts)
    failures: list[str] = []
    if not decision["is_mixed_family_intended_selectable"]:
        failures.append("mixed_family_not_proven_selectable_by_global_contract")
    if decision["authoritative_contract_name"] == "UNRESOLVED":
        failures.append("authoritative_contract_name_unresolved")
    if decision["authoritative_contract_name"] != NEW_ID:
        failures.append("new_id_not_authoritative")
    if fixture["chooser_selected_family_id"] != NEW_ID:
        failures.append("chooser_does_not_select_new_mixed_family")
    if fixture["contract_runtime_selected_family_id"] != NEW_ID:
        failures.append("classification_runtime_does_not_select_new_mixed_family")
    if fixture["chooser_secondary_overdesign_match_pruned"]:
        failures.append("chooser_still_prunes_new_mixed_family")
    status = "PASS" if not failures else "FAIL"
    payload = {
        "schema": "bending_fail_shear_overdesign_chooser_priority_audit.v1",
        "status": status,
        "created_at": stamp,
        "product_behaviour_changed": False,
        "code_changed": False,
        "contract": contract,
        "source": source,
        "fixture": fixture,
        "artifacts": artifacts,
        "decision": decision,
        "failures": failures,
    }
    artifact_path = ARTIFACT_DIR / f"bending_fail_shear_overdesign_chooser_priority_audit_{stamp}.json"
    report_path = AUDIT_DIR / f"bending_fail_shear_overdesign_chooser_priority_audit_{stamp}.md"
    artifact_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    _write_report(payload, report_path)
    print(
        json.dumps(
            {
                "status": status,
                "artifact": str(artifact_path),
                "report": str(report_path),
                "authoritative_contract_name": decision["authoritative_contract_name"],
                "current_new_package_selectable": decision["current_new_package_selectable"],
                "recommended_next_step": decision["recommended_next_step"],
            },
            indent=2,
        )
    )
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
