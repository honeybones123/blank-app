"""Adapters from the legacy Design Guide payload to a DesignBrainResult."""

from __future__ import annotations

from typing import Any

from design_brain.candidates import (
    candidate_id_from_item,
    candidate_label_from_item,
    normalise_candidate_row,
)
from design_brain.contracts import contract_ids_for_outcome, validate_design_brain_result
from design_brain.evidence import (
    active_failures_from_evidence,
    candidate_rows_from_evidence,
    candidate_search_evidence_from_payload,
)
from design_brain.optimisation import (
    safe_combined_cleanup_proof,
)
from design_brain.interface import (
    DesignBrainCTA,
    DesignBrainEvidence,
    DesignBrainInput,
    DesignBrainResult,
)
from design_brain.governing_state import classify_governing_state
from design_brain.publication import (
    button_contract_from_payload as _button_contract,
    card_kind_for_publication,
    contract_enabled as _contract_enabled,
    contract_updates_from_publication as _contract_updates,
    enforce_design_brain_publication_contract,
    enforce_family_selection_publication_contract,
    enforce_underdesign_repair_publication_boundary,
    outcome_id_for_publication as _outcome_id,
)


def _as_dict(value: Any) -> dict:
    return dict(value) if isinstance(value, dict) else {}


def _as_list(value: Any) -> list:
    return list(value) if isinstance(value, list) else []


def _primary_item(payload: dict) -> dict:
    items = _as_list(payload.get("guidance_items"))
    return dict(items[0]) if items and isinstance(items[0], dict) else {}


def adapt_design_brain_result_payload(
    payload: dict,
    *,
    design_input: DesignBrainInput | None = None,
    runtime_fingerprint: Any = None,
) -> dict:
    """Attach DesignBrainResult metadata to the legacy payload.

    The returned payload keeps all existing keys and values.  New data is added
    under ``design_brain_result`` and mirrored into ``debug_trace`` for verifier
    proof/debug visibility.
    """
    if not isinstance(payload, dict):
        return payload
    out = dict(payload)
    primary = _primary_item(out)
    debug = _as_dict(out.get("debug_trace"))
    summary = _as_dict(debug.get("overview"))
    contract = _button_contract(primary, debug)
    updates = _contract_updates(contract, primary)
    evidence = candidate_search_evidence_from_payload(out, primary, debug)
    active = active_failures_from_evidence(summary, evidence, debug)
    cta_enabled = _contract_enabled(contract)
    candidate_id = candidate_id_from_item(primary, contract, evidence)
    candidate_label = candidate_label_from_item(primary, evidence)
    safe_combined = safe_combined_cleanup_proof(
        evidence,
        primary,
        contract,
        contract_enabled=_contract_enabled,
    )
    status = str(
        primary.get("status")
        or primary.get("critical_status")
        or debug.get("primary_status")
        or ""
    ).strip() or None
    intent = str(primary.get("guidance_intent") or debug.get("primary_guidance_intent") or "").strip()
    card_kind = card_kind_for_publication(
        cta_enabled=cta_enabled,
        intent=intent,
        status=status,
    )
    terminal_state = str(primary.get("design_guide_terminal_state") or debug.get("design_guide_terminal_state") or "").strip()
    outcome = _outcome_id(
        active_failures=active,
        cta_enabled=cta_enabled,
        primary=primary,
        summary=summary,
        evidence=evidence,
    )
    safe_combined["final_published_outcome"] = outcome
    safe_combined["final_cta_enabled"] = bool(cta_enabled)
    proof_fp = {
        "runtime": runtime_fingerprint,
        "cache": _as_dict(out.get("cache_data")).get("guidance_cache_fp"),
        "publication": debug.get("design_guide_publication_fingerprint"),
        "debug": debug.get("design_guide_publication_fingerprint") or debug.get("debug_fingerprint"),
    }
    cta = DesignBrainCTA(
        intent=intent or None,
        enabled=cta_enabled,
        disabled_reason=contract.get("blocking_reason") or debug.get("button_contract_blocking_reason"),
        executor_backed=bool(cta_enabled and contract.get("preview_pass") is not False and updates),
        action_type=contract.get("action_type") or primary.get("action_type"),
        updates=updates,
        candidate_id=candidate_id,
        preview_pass=contract.get("preview_pass") if isinstance(contract.get("preview_pass"), bool) else None,
    )
    repair_options = [
        normalise_candidate_row(row)
        for row in candidate_rows_from_evidence(evidence)
        if str(row.get("family") or row.get("recommendation_family_tag") or "").strip().lower()
        in {"bending", "shear", "combined"}
        and bool(row.get("active_fail_repair") or row.get("repair_candidate"))
    ]
    optimisation_options = [
        normalise_candidate_row(row)
        for row in candidate_rows_from_evidence(evidence)
        if bool(row.get("safe_executor_backed") or row.get("executor_backed") or row.get("is_executable"))
    ]
    evidence_obj = DesignBrainEvidence(
        active_failures=list(active),
        repair_options=repair_options,
        optimisation_options=optimisation_options,
        candidate_search=dict(evidence),
        safe_combined_cleanup=dict(safe_combined),
    )
    result = DesignBrainResult(
        outcome_id=outcome,
        contract_ids=contract_ids_for_outcome(outcome, evidence),
        status=status,
        card_kind=card_kind,
        is_terminal=bool(terminal_state or outcome == "passing_exact_stop"),
        selected_candidate_id=candidate_id,
        selected_candidate_label=candidate_label,
        cta=cta,
        active_failures=list(active),
        repair_options=repair_options,
        optimisation_options=optimisation_options,
        evidence=evidence_obj,
        fingerprint=proof_fp,
        raw_payload={
            "request_kind": None if design_input is None else design_input.request_kind,
            "primary_item_keys": sorted(primary.keys()),
            "debug_keys": sorted(debug.keys()),
        },
    )
    validation = validate_design_brain_result(result)
    result.evidence.validation = dict(validation)
    result_dict = result.to_dict()
    result_dict["validation"] = dict(validation)
    governing_state = classify_governing_state(
        payload=out,
        primary=primary,
        summary=summary,
        evidence=evidence,
        debug=debug,
        result=result_dict,
    )
    result_dict["governing_state_classifier"] = dict(governing_state)
    out["design_brain_result"] = result_dict
    debug["design_brain_result"] = result_dict
    debug["design_brain_result_validation"] = dict(validation)
    debug["design_brain_safe_combined_cleanup_proof"] = dict(safe_combined)
    debug["governing_state_classifier"] = dict(governing_state)
    out["debug_trace"] = debug
    return out
