"""Proof-only audit for BENDING_FAIL_GOVERNS no-button family-selection drift.

This verifier consumes the latest live no-button audit and compares the observed
state with the current family chooser, classification runtime, and publication
guard source. It does not change product behavior.
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

from design_brain.family_chooser import (  # noqa: E402
    USE_CONTRACT_FAMILY_CLASSIFIER,
    classify_family_from_raw_flags,
)
from design_brain.family_classification_runtime import (  # noqa: E402
    classify_family_from_whole_beam_evidence,
)


ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
NO_BUTTON_PATTERN = "design_guide_bending_fail_no_button_root_audit_*.json"


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")


def _load_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _latest_artifact(pattern: str) -> tuple[Path | None, dict[str, Any]]:
    matches = sorted(ARTIFACT_DIR.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)
    if not matches:
        return None, {}
    return matches[0], _load_json(matches[0])


def _as_float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _latest_no_button_scenario() -> tuple[Path | None, dict[str, Any]]:
    path, payload = _latest_artifact(NO_BUTTON_PATTERN)
    scenarios = payload.get("scenarios") if isinstance(payload, dict) else None
    scenario = dict((scenarios or [{}])[0]) if isinstance(scenarios, list) else {}
    return path, scenario


def _exact_blocker_summary(scenario: dict[str, Any]) -> dict[str, Any]:
    blockers = dict(scenario.get("exact_blockers_by_family") or {})
    bending = dict(blockers.get("bending") or {})
    # Artifacts may record values as strings because they originate from browser/debug traces.
    attempted = _as_float(bending.get("attempted_candidate_count"), 0.0)
    safe = _as_float(bending.get("safe_candidate_count"), 0.0)
    executable = _as_float(bending.get("executable_repair_candidate_count"), 0.0)
    exhaustive_text = str(bending.get("repair_search_exhaustive") or "").strip().lower()
    return {
        "raw": bending,
        "repair_search_ran": str(bending.get("repair_search_ran") or "").strip().lower() == "true",
        "repair_search_exhaustive": exhaustive_text == "true",
        "attempted_candidate_count": attempted,
        "safe_candidate_count": safe,
        "executable_repair_candidate_count": executable,
        "no_executable_repair": attempted > 0 and safe == 0 and executable == 0,
        "current_util": bending.get("current_util"),
        "reason": bending.get("reason") or bending.get("visible_reason"),
    }


def _observed_state(scenario: dict[str, Any]) -> dict[str, Any]:
    button_contract = dict(scenario.get("button_contract") or {})
    exact = _exact_blocker_summary(scenario)
    active_failures = list(scenario.get("active_failures") or [])
    return {
        "active_failures": active_failures,
        "selected_family_id": scenario.get("selected_family_id"),
        "policy": scenario.get("policy"),
        "button_contract": button_contract,
        "button_enabled": bool(button_contract.get("enabled")),
        "button_actionable": bool(button_contract.get("actionable")),
        "button_blocking_reason": button_contract.get("blocking_reason"),
        "button_family": button_contract.get("family"),
        "final_publication_cta_present": bool(scenario.get("final_publication_cta")),
        "controller_trace_present": bool(scenario.get("controller_trace_parity_payload")),
        "runtime_blocker_proof_present": bool(
            (scenario.get("runtime_blocker_proof_fields") or {}).get("exact_blocker_bending")
        ),
        "exact_blocker_summary": exact,
        "no_button_card_observed": (
            button_contract.get("blocking_reason") == "family_selection_contract_mismatch"
            and not bool(button_contract.get("enabled"))
            and "bending" in active_failures
        ),
    }


def _classification_probe(scenario: dict[str, Any]) -> dict[str, Any]:
    active_failures = set(scenario.get("active_failures") or [])
    exact = _exact_blocker_summary(scenario)
    current_util = _as_float(exact.get("current_util"), 1.10)
    raw_flags = {
        "geometry_detailing_fail": False,
        "serviceability_fail": False,
        "bending_fail": "bending" in active_failures,
        "shear_fail": "shear" in active_failures,
        "min_bending_reo_fail": False,
        "min_shear_reo_fail": False,
        "bending_overdesigned": False,
        "shear_overdesigned": False,
        "zero_shear_with_ligatures": False,
        "unnecessary_shear_reinforcement_exists": False,
        "shear_cleanup_possible": False,
        "bending_within_target_band": False,
        "shear_within_target_band": True,
        "locked_repair_blocked": bool(exact.get("no_executable_repair")),
        "legal_repair_exists": False,
        "repair_required": bool(active_failures),
        "exact_stop_proven": bool(exact.get("repair_search_exhaustive")),
        "bending_acceptable": False,
        "shear_acceptable": True,
    }
    chooser = classify_family_from_raw_flags(raw_flags)
    whole_beam = {
        "bending_utilisation": current_util,
        "shear_utilisation": 0.90,
        "bending_state": "FAIL",
        "shear_state": "TARGET",
        "serviceability_state": "PASS",
        "geometry_detailing_state": "PASS",
        "minimum_bending_reo_state": "PASS",
        "minimum_shear_reo_state": "PASS",
        "geometry_locked": False,
        "reo_locked": False,
        "can_strengthen_bending": False,
        "can_strengthen_shear": False,
        "can_optimise_bending_without_hurting_shear": False,
        "can_optimise_shear_without_hurting_bending": False,
        "exact_stop_available": bool(exact.get("repair_search_exhaustive")),
        "no_valid_repair_available": bool(exact.get("no_executable_repair")),
    }
    runtime = classify_family_from_whole_beam_evidence(whole_beam)
    return {
        "raw_flags": raw_flags,
        "legacy_chooser_selected_family_id": chooser.get("selected_family_id"),
        "legacy_chooser_matched_family_ids": list(chooser.get("matched_family_ids") or []),
        "legacy_chooser_conflicts": list(chooser.get("selection_conflicts") or []),
        "legacy_chooser_rejected_bending": dict(chooser.get("rejected_families") or {}).get("BENDING_FAIL_GOVERNS"),
        "contract_runtime_selected_family_id": runtime.get("selected_family_id"),
        "contract_runtime_matched_family_ids": list(runtime.get("matched_family_ids") or []),
        "contract_runtime_terminal_status": runtime.get("terminal_status"),
        "contract_runtime_blocked_reason": runtime.get("blocked_reason"),
        "contract_runtime_inactive_bending": dict(runtime.get("inactive_family_evidence") or {}).get("BENDING_FAIL_GOVERNS"),
        "use_contract_family_classifier_live_flag": bool(USE_CONTRACT_FAMILY_CLASSIFIER),
    }


def _source_probe() -> dict[str, Any]:
    chooser_source = _read_text(ROOT / "design_brain" / "family_chooser.py")
    runtime_source = _read_text(ROOT / "design_brain" / "family_classification_runtime.py")
    publication_source = _read_text(ROOT / "design_brain" / "publication.py")
    contract_source = _read_text(ROOT / "design_brain" / "contracts" / "family_classification_contract.json")
    return {
        "family_chooser_uses_legacy_predicates": "USE_CONTRACT_FAMILY_CLASSIFIER = False" in chooser_source,
        "family_chooser_contract_classifier_available": "_classify_family_from_contract_runtime" in chooser_source,
        "publication_safe_item_on_violation": "safe_item = _family_selection_safe_item(primary, diagnostics)" in publication_source,
        "publication_recovers_to_repair_action_only_when_payload_exists": (
            "repair_payload = _repair_action_payload_from_publication(primary, debug, active_failures)" in publication_source
            and "if repair_payload:" in publication_source
        ),
        "publication_violation_on_classification_failure": (
            'violation = "family_chooser_classification_not_exactly_one_match"' in publication_source
        ),
        "contract_bending_fail_must_not_mentions_locked_no_repair": (
            '"terminal exact-stop or locked-no-repair applies"' in contract_source
        ),
        "runtime_locked_no_repair_excludes_bending_only": (
            'e["bending_fail"]' in runtime_source
            and 'not e["shear_fail"]' in runtime_source
            and '"LOCKED_NO_REPAIR"' in runtime_source
        ),
    }


def _decision(observed: dict[str, Any], classification: dict[str, Any], source: dict[str, Any]) -> dict[str, Any]:
    no_button = bool(observed.get("no_button_card_observed"))
    chooser_can_select_bending = classification.get("legacy_chooser_selected_family_id") == "BENDING_FAIL_GOVERNS"
    runtime_selects_bending = classification.get("contract_runtime_selected_family_id") == "BENDING_FAIL_GOVERNS"
    contract_runtime_loses_family = not runtime_selects_bending
    no_runtime_blocker_proof = not observed.get("runtime_blocker_proof_present")
    if no_button and chooser_can_select_bending and contract_runtime_loses_family:
        root = "CONTRACT_RUNTIME_LOCKED_NO_REPAIR_DRIFT"
    elif no_button and chooser_can_select_bending and not observed.get("final_publication_cta_present"):
        root = "PUBLICATION_IDENTITY_OR_REPAIR_PAYLOAD_GAP_AFTER_CHOOSER"
    elif no_button and not chooser_can_select_bending:
        root = "FAMILY_CHOOSER_SELECTION_GAP"
    else:
        root = "NO_BUTTON_ROOT_NOT_REPRODUCED_BY_AUDIT"

    next_step = (
        "Add a contract-backed no-valid-repair ownership proof for BENDING_FAIL_GOVERNS so active bending failure "
        "can publish blocked/exhausted evidence without requiring an executor-backed Apply CTA."
        if root in {"CONTRACT_RUNTIME_LOCKED_NO_REPAIR_DRIFT", "PUBLICATION_IDENTITY_OR_REPAIR_PAYLOAD_GAP_AFTER_CHOOSER"}
        else "Capture a richer live publication payload before implementation."
    )
    return {
        "root_class": root,
        "observed_no_button_card": no_button,
        "legacy_chooser_can_select_bending_fail": chooser_can_select_bending,
        "contract_runtime_selects_bending_fail": runtime_selects_bending,
        "contract_runtime_loses_family_when_no_valid_repair": contract_runtime_loses_family,
        "runtime_blocker_proof_missing_in_live_card": no_runtime_blocker_proof,
        "source_has_publication_safe_item_fallback": bool(source.get("publication_safe_item_on_violation")),
        "source_only_recovers_when_repair_payload_exists": bool(
            source.get("publication_recovers_to_repair_action_only_when_payload_exists")
        ),
        "recommended_next_step": next_step,
        "behaviour_change_allowed": False,
    }


def _write_report(payload: dict[str, Any], path: Path) -> None:
    decision = payload["decision"]
    observed = payload["observed"]
    classification = payload["classification_probe"]
    lines = [
        "# BENDING_FAIL No-Button Family Selection Mismatch Audit",
        "",
        f"Status: `{payload['status']}`",
        f"Product behaviour changed: `{payload['product_behaviour_changed']}`",
        "",
        "## Executive Summary",
        "",
        f"- Root class: `{decision['root_class']}`",
        f"- Observed no-button card: `{decision['observed_no_button_card']}`",
        f"- Legacy chooser selects bending fail: `{decision['legacy_chooser_can_select_bending_fail']}`",
        f"- Contract runtime selects bending fail: `{decision['contract_runtime_selects_bending_fail']}`",
        f"- Runtime blocker proof missing in live card: `{decision['runtime_blocker_proof_missing_in_live_card']}`",
        f"- Recommended next step: {decision['recommended_next_step']}",
        "",
        "## Live Evidence",
        "",
        f"- Source artifact: `{payload['source_no_button_artifact']}`",
        f"- Active failures: `{observed['active_failures']}`",
        f"- Observed selected family: `{observed['selected_family_id']}`",
        f"- Button blocking reason: `{observed['button_blocking_reason']}`",
        f"- Button family: `{observed['button_family']}`",
        f"- Exact blocker no executable repair: `{observed['exact_blocker_summary']['no_executable_repair']}`",
        f"- Exact blocker attempted candidates: `{observed['exact_blocker_summary']['attempted_candidate_count']}`",
        "",
        "## Classification Probe",
        "",
        f"- Legacy chooser selected: `{classification['legacy_chooser_selected_family_id']}`",
        f"- Legacy chooser matched: `{classification['legacy_chooser_matched_family_ids']}`",
        f"- Contract runtime selected: `{classification['contract_runtime_selected_family_id']}`",
        f"- Contract runtime matched: `{classification['contract_runtime_matched_family_ids']}`",
        f"- Contract runtime terminal status: `{classification['contract_runtime_terminal_status']}`",
        f"- Contract runtime blocked reason: `{classification['contract_runtime_blocked_reason']}`",
        "",
        "## Interpretation",
        "",
        "The live card should not need an Apply CTA when the family proves exhausted/no-valid-repair. "
        "The gap is that the final publication path is landing on a family-selection violation instead of a "
        "`BENDING_FAIL_GOVERNS` blocked/exhausted publication with proof-only/no-CTA semantics.",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    no_button_path, scenario = _latest_no_button_scenario()
    observed = _observed_state(scenario)
    classification = _classification_probe(scenario)
    source = _source_probe()
    decision = _decision(observed, classification, source)
    failures: list[str] = []
    if not no_button_path:
        failures.append("missing_no_button_root_audit_artifact")
    if not observed.get("no_button_card_observed"):
        failures.append("latest_artifact_does_not_observe_bending_no_button_card")
    if decision["root_class"] == "NO_BUTTON_ROOT_NOT_REPRODUCED_BY_AUDIT":
        failures.append("no_button_root_not_reproduced")

    payload = {
        "schema": "design_guide_bending_fail_no_button_family_selection_mismatch_audit.v1",
        "status": "PASS" if not failures else "PARTIAL",
        "created_at": stamp,
        "product_behaviour_changed": False,
        "source_no_button_artifact": str(no_button_path) if no_button_path else None,
        "observed": observed,
        "classification_probe": classification,
        "source_probe": source,
        "decision": decision,
        "failures": failures,
    }
    json_path = ARTIFACT_DIR / f"design_guide_bending_fail_no_button_family_selection_mismatch_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_bending_fail_no_button_family_selection_mismatch_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    _write_report(payload, report_path)
    print(
        json.dumps(
            {
                "status": payload["status"],
                "root_class": decision["root_class"],
                "artifact": str(json_path),
                "report": str(report_path),
                "recommended_next_step": decision["recommended_next_step"],
            },
            indent=2,
        )
    )
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
