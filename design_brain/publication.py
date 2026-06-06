"""Design Brain publication and CTA eligibility helpers.

This module owns pure publication classification and CTA/publication payload
normalisation. It does not render UI, bind session state, execute Apply, search
for candidates, evaluate formulas, or run solver maths.
"""

from __future__ import annotations

from typing import Any

from design_brain.candidates import normalise_candidate_row
from design_brain.evidence import candidate_rows_from_evidence
from design_brain.optimisation import clean_safe_combined_evidence


def _as_dict(value: Any) -> dict:
    return dict(value) if isinstance(value, dict) else {}


def _as_list(value: Any) -> list:
    return list(value) if isinstance(value, list) else []


def _as_float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def button_contract_from_payload(primary: dict, debug: dict) -> dict:
    return _as_dict(
        primary.get("button_contract")
        or debug.get("primary_button_contract")
        or debug.get("button_contract")
    )


def contract_updates_from_publication(contract: dict, primary: dict) -> dict:
    return _as_dict(
        contract.get("updates")
        or primary.get("selected_action_updates")
        or primary.get("updates")
        or _as_dict(primary.get("action_payload")).get("resolved_candidate_updates")
        or _as_dict(primary.get("action_payload")).get("updates")
    )


def contract_enabled(contract: dict) -> bool:
    return bool(contract.get("enabled") or contract.get("actionable"))


def outcome_id_for_publication(
    *,
    active_failures: list[str],
    cta_enabled: bool,
    primary: dict,
    summary: dict,
    evidence: dict,
) -> str:
    intent = str(primary.get("guidance_intent") or "").strip().lower()
    status = str(primary.get("status") or primary.get("critical_status") or "").strip().upper()
    terminal = str(primary.get("design_guide_terminal_state") or "").strip().lower()
    if active_failures:
        return "active_required_failure"
    if cta_enabled and (
        intent in {"efficiency_tightening", "optional_cleanup"}
        or int(evidence.get("safe_local_cleanup_count") or 0) > 0
    ):
        return "passing_with_safe_optimisation_available"
    if terminal or intent == "already_efficient" or status == "PASS":
        return "passing_exact_stop"
    if intent == "specific_blocker" or "blocked" in str(primary.get("title_main") or primary.get("title") or "").lower():
        return "blocked_specific_reason"
    if summary.get("any_fail"):
        return "active_required_failure"
    return "unknown"


def card_kind_for_publication(*, cta_enabled: bool, intent: str, status: str | None) -> str | None:
    return "ACTION" if cta_enabled else (
        "PASS" if intent == "already_efficient" or status == "PASS" else (
            "BLOCKED" if intent == "specific_blocker" else None
        )
    )


def _safe_combined_updates_from_result(
    *,
    result: dict,
    proof: dict,
    evidence: dict,
) -> dict:
    target_id = str(proof.get("candidate_id") or "combined_best_safe_shear_plus_bending_cleanup")
    for source in (
        proof.get("updates"),
        evidence.get("selected_candidate_updates"),
        evidence.get("best_safe_candidate_updates"),
        evidence.get("closest_safe_candidate_updates"),
    ):
        updates = _as_dict(source)
        if updates:
            return updates
    for option in _as_list(result.get("optimisation_options")) + _as_list(result.get("repair_options")):
        if not isinstance(option, dict):
            continue
        option_id = str(option.get("candidate_id") or "").strip()
        raw = _as_dict(option.get("raw"))
        raw_id = str(raw.get("candidate_id") or raw.get("id") or "").strip()
        if target_id not in {option_id, raw_id}:
            continue
        for source in (
            option.get("updates"),
            raw.get("updates"),
            raw.get("proposed_updates"),
            raw.get("selected_candidate_updates"),
            raw.get("best_safe_candidate_updates"),
            raw.get("closest_safe_candidate_updates"),
        ):
            updates = _as_dict(source)
            if updates:
                return updates
    for row in candidate_rows_from_evidence(evidence):
        row_id = str(row.get("candidate_id") or row.get("id") or "").strip()
        row_title = str(row.get("title") or row.get("label") or "").strip()
        if target_id not in row_id and target_id not in row_title:
            continue
        candidate = normalise_candidate_row(row, fallback_id=target_id)
        updates = _as_dict(candidate.get("updates"))
        if updates:
            return updates
    return {}


def _safe_combined_active_failure_reason(result: dict, debug: dict) -> str | None:
    active = {
        str(item or "").strip().lower()
        for item in _as_list(result.get("active_failures"))
        if str(item or "").strip()
    }
    statuses = _as_dict(_as_dict(debug.get("overview")).get("statuses"))
    active.update(
        str(family or "").strip().lower()
        for family, status in statuses.items()
        if str(status or "").strip().upper() == "FAIL" and str(family or "").strip()
    )
    active = {("deflection" if item == "serviceability" else item) for item in active}
    if active:
        return "active_required_failure_invalidates_safe_cleanup_candidate"
    return None


def _remove_safe_combined_validation_failure(validation: dict) -> dict:
    out = dict(validation or {})
    out["failures"] = [
        failure
        for failure in _as_list(out.get("failures"))
        if failure != "safe_combined_cleanup_candidate_visible_cta_disabled"
    ]
    out["warnings"] = [
        warning
        for warning in _as_list(out.get("warnings"))
        if warning != "safe_combined_cleanup_candidate_visible_cta_disabled"
    ]
    out["ok"] = not bool(out.get("failures"))
    return out


def enforce_design_brain_publication_contract(payload: dict) -> dict:
    """Reroute only the proven safe-combined-cleanup stale publication state.

    The function is intentionally narrow: it does not search for candidates or
    change engineering semantics. It only publishes an already proven,
    executor-backed, preview-PASS combined cleanup candidate when the final
    visible publication has drifted to a terminal/blocker/no-CTA state.
    """
    if not isinstance(payload, dict):
        return payload
    out = dict(payload)
    items = [dict(item) for item in _as_list(out.get("guidance_items")) if isinstance(item, dict)]
    if not items:
        return out
    debug = _as_dict(out.get("debug_trace"))
    result = _as_dict(out.get("design_brain_result") or debug.get("design_brain_result"))
    if not result:
        debug["design_brain_publication_contract_enforced"] = False
        debug["design_brain_publication_contract_skip_reason"] = "missing_design_brain_result"
        out["debug_trace"] = debug
        return out
    result_evidence = _as_dict(result.get("evidence"))
    proof = _as_dict(
        debug.get("design_brain_safe_combined_cleanup_proof")
        or result_evidence.get("safe_combined_cleanup")
    )
    evidence = _as_dict(result_evidence.get("candidate_search") or debug.get("candidate_search_evidence"))
    candidate_id = str(proof.get("candidate_id") or "").strip()
    if not candidate_id:
        candidate_id = str(evidence.get("selected_candidate_id") or evidence.get("best_safe_candidate_id") or "").strip()
    target_id = "combined_best_safe_shear_plus_bending_cleanup"
    if target_id not in candidate_id:
        debug["design_brain_publication_contract_enforced"] = False
        debug["design_brain_publication_contract_skip_reason"] = "safe_combined_candidate_not_found"
        out["debug_trace"] = debug
        return out
    updates = _safe_combined_updates_from_result(result=result, proof=proof, evidence=evidence)
    skip_reason = None
    if not proof.get("safe_cleanup_candidate_found"):
        skip_reason = "safe_combined_candidate_not_proven"
    elif proof.get("preview_pass") is not True:
        skip_reason = "safe_combined_candidate_preview_not_pass"
    elif not proof.get("executor_backed"):
        skip_reason = "safe_combined_candidate_not_executor_backed"
    elif not updates:
        skip_reason = "safe_combined_candidate_missing_updates"
    else:
        skip_reason = _safe_combined_active_failure_reason(result, debug)
    if skip_reason:
        proof["publication_contract_skip_reason"] = skip_reason
        proof["publication_contract_enforced"] = False
        validation = _as_dict(result.get("validation") or result_evidence.get("validation"))
        if skip_reason != "safe_combined_candidate_preview_not_pass":
            validation.setdefault("failures", [])
        result["validation"] = validation
        result_evidence["safe_combined_cleanup"] = dict(proof)
        result["evidence"] = dict(result_evidence)
        debug["design_brain_result"] = dict(result)
        debug["design_brain_safe_combined_cleanup_proof"] = dict(proof)
        debug["design_brain_publication_contract_enforced"] = False
        debug["design_brain_publication_contract_skip_reason"] = skip_reason
        out["design_brain_result"] = dict(result)
        out["debug_trace"] = debug
        return out

    primary = dict(items[0])
    contract = button_contract_from_payload(primary, debug)
    current_enabled = contract_enabled(contract)
    title_text = str(primary.get("title_main") or primary.get("title") or "").strip().lower()
    current_kind = str(result.get("card_kind") or "").strip().upper()
    current_outcome = str(result.get("outcome_id") or "").strip()
    stale_terminal_or_blocked = bool(
        not current_enabled
        or current_kind in {"BLOCKED", "PASS"}
        or current_outcome in {"blocked_specific_reason", "passing_exact_stop"}
        or "blocked" in title_text
        or primary.get("design_guide_terminal_state")
    )
    if not stale_terminal_or_blocked:
        proof["publication_contract_enforced"] = False
        proof["publication_contract_skip_reason"] = "publication_already_actionable"
        proof["final_cta_enabled"] = True
        debug["design_brain_safe_combined_cleanup_proof"] = dict(proof)
        out["debug_trace"] = debug
        return out

    expected = proof.get("expected_utilisation") or evidence.get("selected_candidate_util") or evidence.get("best_safe_final_util")
    label = str(proof.get("label") or result.get("selected_candidate_label") or "").strip()
    if not label or "blocked" in label.lower():
        label = str(evidence.get("selected_candidate_title") or "Shear and bending cleanup - one-click optimisation")
    cleaned_evidence = clean_safe_combined_evidence(
        evidence,
        candidate_id=candidate_id,
        updates=updates,
        label=label,
        expected=expected,
    )
    contract = {
        **dict(contract or {}),
        "enabled": True,
        "actionable": True,
        "action_type": "apply_resolved_candidate",
        "family": "combined",
        "updates": dict(updates),
        "preview_pass": True,
        "blocking_reason": None,
        "source_candidate_id": candidate_id,
        "candidate_id": candidate_id,
    }
    expected_value = _as_float(expected)
    if expected_value is not None:
        contract["expected_util"] = expected_value
    item = dict(primary)
    for stale_key in (
        "exact_blockers_by_family",
        "post_click_exact_blockers_by_family",
        "cleanup_evidence_by_family",
        "post_click_cleanup_evidence_by_family",
        "blocker_attempts_by_family",
        "terminal_state_blocked_by_local_cleanup",
        "design_guide_terminal_state",
        "terminal_cleanup_state",
    ):
        item.pop(stale_key, None)
    item.update(
        {
            "title_main": label,
            "title": label,
            "family": "combined",
            "check_key": "combined",
            "selected_action_family": "combined",
            "status": "EFFICIENCY",
            "guidance_intent": "efficiency_tightening",
            "action_type": "apply_resolved_candidate",
            "primary_card_actionable": True,
            "updates": dict(updates),
            "selected_action_updates": dict(updates),
            "candidate_id": candidate_id,
            "source_candidate_id": candidate_id,
            "button_contract": dict(contract),
            "candidate_search_evidence": dict(cleaned_evidence),
            "primary_action": item.get("primary_action") or "Run one-click auto design",
        }
    )
    if expected_value is not None:
        item["util"] = expected_value
        item["expected_util"] = expected_value
        item["candidate_post_util"] = expected_value
    action_payload = dict(item.get("action_payload") or {})
    action_payload.update(
        {
            "action_type": "apply_resolved_candidate",
            "family": "combined",
            "updates": dict(updates),
            "resolved_candidate_updates": dict(updates),
            "resolved_candidate_action_type": "apply_resolved_candidate",
            "resolved_candidate_family_tag": "combined",
            "candidate_id": candidate_id,
            "source_candidate_id": candidate_id,
            "candidate_search_evidence": dict(cleaned_evidence),
        }
    )
    if expected_value is not None:
        action_payload["expected_util"] = expected_value
        action_payload["candidate_post_util"] = expected_value
        action_payload["resolved_candidate_post_util"] = expected_value
    item["action_payload"] = dict(action_payload)
    resolved = dict(item.get("resolved_candidate") or {})
    resolved.update(
        {
            "action_type": "apply_resolved_candidate",
            "family": "combined",
            "recommendation_family_tag": "combined",
            "updates": dict(updates),
            "candidate_id": candidate_id,
            "source_candidate_id": candidate_id,
            "candidate_search_evidence": dict(cleaned_evidence),
        }
    )
    if expected_value is not None:
        resolved["expected_util"] = expected_value
        resolved["candidate_post_util"] = expected_value
    item["resolved_candidate"] = dict(resolved)

    proof.update(
        {
            "safe_cleanup_candidate_found": True,
            "candidate_id": candidate_id,
            "candidate_family": "combined",
            "executor_backed": True,
            "preview_pass": True,
            "updates": dict(updates),
            "label": label,
            "expected_utilisation": expected_value,
            "final_published_outcome": "passing_with_safe_optimisation_available",
            "final_cta_enabled": True,
            "publication_contract_enforced": True,
            "publication_contract_enforcement_reason": "safe_executable_combined_cleanup_outranks_stale_blocker",
        }
    )
    cta = _as_dict(result.get("cta"))
    cta.update(
        {
            "intent": "efficiency_tightening",
            "enabled": True,
            "disabled_reason": None,
            "executor_backed": True,
            "action_type": "apply_resolved_candidate",
            "updates": dict(updates),
            "candidate_id": candidate_id,
            "preview_pass": True,
        }
    )
    contract_ids = list(dict.fromkeys(_as_list(result.get("contract_ids")) + [
        "passing_with_safe_optimisation_available",
        "candidate_integrity",
    ]))
    validation = _remove_safe_combined_validation_failure(
        _as_dict(result.get("validation") or result_evidence.get("validation"))
    )
    validation["publication_contract_enforced"] = True
    result.update(
        {
            "outcome_id": "passing_with_safe_optimisation_available",
            "contract_ids": contract_ids,
            "status": "EFFICIENCY",
            "card_kind": "ACTION",
            "is_terminal": False,
            "selected_candidate_id": candidate_id,
            "selected_candidate_label": label,
            "cta": dict(cta),
            "validation": dict(validation),
        }
    )
    result_evidence["candidate_search"] = dict(cleaned_evidence)
    result_evidence["safe_combined_cleanup"] = dict(proof)
    result_evidence["validation"] = dict(validation)
    result["evidence"] = dict(result_evidence)

    debug.update(
        {
            "design_brain_publication_contract_enforced": True,
            "design_brain_publication_contract_enforcement_reason": "safe_executable_combined_cleanup_outranks_stale_blocker",
            "design_brain_result": dict(result),
            "design_brain_result_validation": dict(validation),
            "design_brain_safe_combined_cleanup_proof": dict(proof),
            "candidate_search_evidence": dict(cleaned_evidence),
            "primary_button_contract": dict(contract),
            "displayed_primary_button_contract": dict(contract),
            "button_contract": dict(contract),
            "button_contract_enabled": True,
            "button_contract_updates": dict(updates),
            "button_contract_preview_pass": True,
            "button_contract_blocking_reason": None,
            "selected_title": label,
            "selected_action_type": "apply_resolved_candidate",
            "selected_action_family": "combined",
            "primary_card_title": label,
            "primary_card_intent": "efficiency_tightening",
            "primary_guidance_intent": "efficiency_tightening",
            "design_guide_terminal_state": None,
            "design_guide_terminal_positive": False,
            "design_guide_has_actionable_recommendation": True,
        }
    )
    for stale_key in (
        "exact_blockers_by_family",
        "post_click_exact_blockers_by_family",
        "cleanup_evidence_by_family",
        "post_click_cleanup_evidence_by_family",
        "blocker_attempts_by_family",
    ):
        debug.pop(stale_key, None)
    out["guidance_items"] = [item] + items[1:]
    out["design_brain_result"] = dict(result)
    out["debug_trace"] = debug
    return out
