"""Proof-only final Design Guide publication boundary.

This module defines a stable Design Brain object for the final publication
shape. It does not render CTA, route apply actions, read page/session state, or
replace the current page-owned publication path.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from hashlib import sha256
from typing import Any, Literal


FinalDesignGuideOutcomeState = Literal["PASS", "ACTION", "BLOCKED", "ERROR", "PROOF_PENDING"]


def stable_final_publication_hash(value: Any) -> str:
    """Return a deterministic hash for final-publication proof payloads."""

    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return sha256(payload.encode("utf-8")).hexdigest()


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value or {}) if isinstance(value, dict) else {}


def _text(*values: Any) -> str | None:
    for value in values:
        text = str(value or "").strip()
        if text:
            return text
    return None


@dataclass(frozen=True)
class FinalDesignGuideCTA:
    """Proof representation of final CTA state; not product-driving."""

    enabled: bool = False
    actionable: bool = False
    label: str | None = None
    action_type: str | None = None
    family: str | None = None
    disabled_reason: str | None = None
    apply_payload_summary: dict[str, Any] = field(default_factory=dict)
    apply_payload_fingerprint: str | None = None
    button_contract_hash: str | None = None
    source_candidate_id: str | None = None
    executor_backed_proof: dict[str, Any] = field(default_factory=dict)
    stale_fresh_token_proof: dict[str, Any] = field(default_factory=dict)
    one_click_action_handoff: dict[str, Any] = field(default_factory=dict)
    source_precedence_proof: dict[str, Any] = field(default_factory=dict)
    product_driving: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class FinalDesignGuideDisplay:
    """Proof representation of visible display fields; not renderer-driving."""

    title: str | None = None
    badge: str | None = None
    summary: str | None = None
    status: str | None = None
    bucket: str | None = None
    colour_state: str | None = None
    card_class: str | None = None
    display_state: str | None = None
    expanded_evidence_sections: dict[str, Any] = field(default_factory=dict)
    blocker_explanation: str | None = None
    final_card_model_fields: dict[str, Any] = field(default_factory=dict)
    final_card_model_hash: str | None = None
    render_fallback_shell_model: dict[str, Any] = field(default_factory=dict)
    render_fallback_shell_hash: str | None = None
    visible_wording_hash: str | None = None
    renderer_driving: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class FinalDesignGuideEvidence:
    """Proof evidence behind final publication classification."""

    published_item_id: str | None = None
    post_click_design_guide_state: str | None = None
    selected_family: str | None = None
    publication_reason: str | None = None
    blocker_reason: str | None = None
    exact_stop_proof: dict[str, Any] = field(default_factory=dict)
    target_band_proof: dict[str, Any] = field(default_factory=dict)
    stale_fresh_proof: dict[str, Any] = field(default_factory=dict)
    candidate_search_evidence: dict[str, Any] = field(default_factory=dict)
    evidence_hash: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class FinalDesignGuideVerifierPayload:
    """Verifier/debug proof payload; not browser-driving."""

    payload: dict[str, Any] = field(default_factory=dict)
    payload_hash: str | None = None
    browser_driving: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class FinalDesignGuidePostResolverMutationProof:
    """Proof surface for render-stage post-resolver selected-item mutations."""

    selected_item_identity: dict[str, Any] = field(default_factory=dict)
    adapter_owned_mutation_truth: dict[str, Any] = field(default_factory=dict)
    remaining_resolver_truth: dict[str, Any] = field(default_factory=dict)
    evidence_projection: dict[str, Any] = field(default_factory=dict)
    blocker_projection: dict[str, Any] = field(default_factory=dict)
    terminal_projection: dict[str, Any] = field(default_factory=dict)
    resolver_projection: dict[str, Any] = field(default_factory=dict)
    selected_item_projection: dict[str, Any] = field(default_factory=dict)
    debug_projection: dict[str, Any] = field(default_factory=dict)
    mutation_target_coverage: dict[str, bool] = field(default_factory=dict)
    mutation_proof_hash: str | None = None
    derived_from: str = "FinalDesignGuidePublication"
    proof_only: bool = True
    product_driving: bool = False
    render_driving: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class FinalDesignGuidePublication:
    """Normalized proof object for final Design Guide publication."""

    published_item_id: str | None
    selected_family: str | None
    outcome_state: FinalDesignGuideOutcomeState
    post_click_design_guide_state: str | None = None
    publication_reason: str | None = None
    blocker_reason: str | None = None
    exact_stop_proof: dict[str, Any] = field(default_factory=dict)
    target_band_proof: dict[str, Any] = field(default_factory=dict)
    cta: FinalDesignGuideCTA = field(default_factory=FinalDesignGuideCTA)
    display: FinalDesignGuideDisplay = field(default_factory=FinalDesignGuideDisplay)
    evidence: FinalDesignGuideEvidence = field(default_factory=FinalDesignGuideEvidence)
    verifier_payload: FinalDesignGuideVerifierPayload = field(default_factory=FinalDesignGuideVerifierPayload)
    stale_fresh_proof: dict[str, Any] = field(default_factory=dict)
    source_hash: str | None = None
    publication_hash: str | None = None
    proof_only: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def with_publication_hash(self) -> "FinalDesignGuidePublication":
        payload = self.to_dict()
        payload.pop("publication_hash", None)
        return FinalDesignGuidePublication(
            **{
                **payload,
                "cta": self.cta,
                "display": self.display,
                "evidence": self.evidence,
                "verifier_payload": self.verifier_payload,
                "publication_hash": stable_final_publication_hash(payload),
            }
        )


def infer_final_design_guide_outcome_state(
    *,
    item: dict[str, Any] | None = None,
    cta: FinalDesignGuideCTA | None = None,
    blocker_reason: str | None = None,
) -> FinalDesignGuideOutcomeState:
    """Infer proof outcome state from already-shaped publication fields."""

    item_d = _mapping(item)
    cta_d = cta or FinalDesignGuideCTA()
    status = str(item_d.get("status") or item_d.get("critical_status") or "").strip().upper()
    bucket = str(item_d.get("bucket") or "").strip().lower()
    intent = str(item_d.get("guidance_intent") or "").strip().lower()
    final_state = str(
        item_d.get("final_state_class")
        or item_d.get("final_state_type")
        or item_d.get("design_guide_terminal_state")
        or ""
    ).strip().lower()
    if status in {"ERROR", "CRITICAL"} or bucket == "error":
        return "ERROR"
    if bool(cta_d.enabled or cta_d.actionable):
        return "ACTION"
    if (
        blocker_reason
        or intent == "specific_blocker"
        or final_state == "blocker"
        or isinstance(item_d.get("exact_blockers_by_family"), dict)
        and bool(item_d.get("exact_blockers_by_family"))
    ):
        return "BLOCKED"
    if status in {"PASS", "GOOD", "OK"} or bucket == "pass" or item_d.get("design_guide_terminal_state"):
        return "PASS"
    return "PROOF_PENDING"


def build_final_design_guide_cta(
    *,
    item: dict[str, Any] | None = None,
    debug: dict[str, Any] | None = None,
) -> FinalDesignGuideCTA:
    item_d = _mapping(item)
    debug_d = _mapping(debug)
    contract = _mapping(
        item_d.get("button_contract")
        or debug_d.get("displayed_primary_button_contract")
        or debug_d.get("primary_button_contract")
        or debug_d.get("button_contract")
    )
    action_payload = _mapping(item_d.get("action_payload") or debug_d.get("design_guide_primary_apply_payload"))
    updates = _mapping(
        contract.get("updates")
        or action_payload.get("updates")
        or action_payload.get("resolved_candidate_updates")
        or item_d.get("updates")
    )
    apply_payload_source = action_payload or {"updates": updates}
    evidence = _mapping(item_d.get("candidate_search_evidence") or debug_d.get("candidate_search_evidence"))
    executor_backed_proof = {
        "executor_backed": bool(
            contract.get("executor_backed")
            or action_payload.get("executor_backed")
            or evidence.get("executor_backed")
            or evidence.get("safe_executor_backed_candidate_found")
            or int(evidence.get("safe_executor_backed_candidates_count") or 0) > 0
        ),
        "safe_executor_backed_candidates_count": evidence.get("safe_executor_backed_candidates_count"),
        "preview_pass": contract.get("preview_pass"),
        "source": _text(contract.get("executor_source"), evidence.get("executor_source"), "publication_payload"),
    }
    stale_fresh_token_proof = {
        "component_apply_token": _text(
            action_payload.get("component_apply_token"),
            debug_d.get("component_apply_token"),
        ),
        "stale_apply_payload_blocked": bool(
            action_payload.get("stale_apply_payload_blocked")
            or debug_d.get("stale_apply_payload_blocked")
        ),
        "stale_apply_payload_mismatch_reason": _text(
            action_payload.get("stale_apply_payload_mismatch_reason"),
            debug_d.get("stale_apply_payload_mismatch_reason"),
            debug_d.get("component_apply_stale_reason"),
        ),
        "expected_fingerprint": _text(
            action_payload.get("stale_apply_payload_expected_fingerprint"),
            debug_d.get("stale_apply_payload_expected_fingerprint"),
        ),
        "current_fingerprint": _text(
            action_payload.get("stale_apply_payload_current_fingerprint"),
            debug_d.get("stale_apply_payload_current_fingerprint"),
        ),
    }
    one_click_action_handoff = {
        "action_type": _text(contract.get("action_type"), item_d.get("action_type"), action_payload.get("action_type")),
        "candidate_id": _text(
            contract.get("source_candidate_id"),
            contract.get("candidate_id"),
            action_payload.get("source_candidate_id"),
            action_payload.get("candidate_id"),
            item_d.get("source_candidate_id"),
            item_d.get("candidate_id"),
        ),
        "updates_hash": stable_final_publication_hash(updates),
        "has_updates": bool(updates),
    }
    source_precedence_proof = {
        "button_contract_source": _text(
            debug_d.get("winning_button_contract_source"),
            debug_d.get("button_contract_source"),
            evidence.get("winning_button_contract_source"),
        ),
        "update_payload_source": _text(
            debug_d.get("winning_update_payload_source"),
            debug_d.get("update_payload_source"),
            evidence.get("winning_update_payload_source"),
        ),
        "candidate_source": _text(
            debug_d.get("winning_candidate_source"),
            debug_d.get("candidate_source"),
            evidence.get("winning_candidate_source"),
        ),
        "source_precedence_hash": stable_final_publication_hash(
            {
                "button_contract_source": debug_d.get("winning_button_contract_source")
                or debug_d.get("button_contract_source")
                or evidence.get("winning_button_contract_source"),
                "update_payload_source": debug_d.get("winning_update_payload_source")
                or debug_d.get("update_payload_source")
                or evidence.get("winning_update_payload_source"),
                "candidate_source": debug_d.get("winning_candidate_source")
                or debug_d.get("candidate_source")
                or evidence.get("winning_candidate_source"),
            }
        ),
    }
    return FinalDesignGuideCTA(
        enabled=bool(contract.get("enabled") or contract.get("actionable")),
        actionable=bool(contract.get("actionable")),
        label=_text(item_d.get("primary_action"), item_d.get("cta_label"), contract.get("label")),
        action_type=_text(contract.get("action_type"), item_d.get("action_type"), action_payload.get("action_type")),
        family=_text(contract.get("family"), item_d.get("family"), item_d.get("check_key")),
        disabled_reason=_text(contract.get("disabled_reason"), contract.get("blocking_reason"), item_d.get("blocking_reason")),
        apply_payload_summary={
            "action_type": action_payload.get("action_type") or contract.get("action_type"),
            "family": action_payload.get("family") or contract.get("family"),
            "updates": updates,
            "updates_hash": stable_final_publication_hash(updates),
            "candidate_id": action_payload.get("candidate_id") or contract.get("candidate_id"),
            "source_candidate_id": action_payload.get("source_candidate_id") or contract.get("source_candidate_id"),
        },
        apply_payload_fingerprint=stable_final_publication_hash(apply_payload_source),
        button_contract_hash=stable_final_publication_hash(contract),
        source_candidate_id=_text(contract.get("source_candidate_id"), contract.get("candidate_id"), item_d.get("source_candidate_id"), item_d.get("candidate_id")),
        executor_backed_proof=executor_backed_proof,
        stale_fresh_token_proof=stale_fresh_token_proof,
        one_click_action_handoff=one_click_action_handoff,
        source_precedence_proof=source_precedence_proof,
        product_driving=False,
    )


def build_final_publication_cta_from_current_state(
    *,
    item: dict[str, Any] | None = None,
    debug: dict[str, Any] | None = None,
    button_contract: dict[str, Any] | None = None,
    action_payload: dict[str, Any] | None = None,
    candidate_search_evidence: dict[str, Any] | None = None,
    source_precedence: dict[str, Any] | None = None,
) -> FinalDesignGuideCTA:
    """Proof-only CTA adapter for current distributed publication state.

    The adapter accepts plain dictionaries only. It does not read page/session
    state, render buttons, route apply actions, or drive one-click behavior.
    """

    item_d = _mapping(item)
    debug_d = _mapping(debug)
    if isinstance(button_contract, dict) and button_contract:
        item_d["button_contract"] = dict(button_contract)
    if isinstance(action_payload, dict) and action_payload:
        item_d["action_payload"] = dict(action_payload)
    evidence = _mapping(candidate_search_evidence)
    if evidence:
        item_d["candidate_search_evidence"] = {
            **_mapping(item_d.get("candidate_search_evidence")),
            **evidence,
        }
    precedence = _mapping(source_precedence)
    if precedence:
        debug_d.update(
            {
                "winning_button_contract_source": precedence.get("winning_button_contract_source")
                or precedence.get("button_contract_source"),
                "winning_update_payload_source": precedence.get("winning_update_payload_source")
                or precedence.get("update_payload_source"),
                "winning_candidate_source": precedence.get("winning_candidate_source")
                or precedence.get("candidate_source"),
            }
        )
    return build_final_design_guide_cta(item=item_d, debug=debug_d)


def build_final_design_guide_display(*, item: dict[str, Any] | None = None) -> FinalDesignGuideDisplay:
    item_d = _mapping(item)
    button_contract = _mapping(item_d.get("button_contract"))
    reasons = [dict(row) for row in list(item_d.get("reasons") or []) if isinstance(row, dict)]
    details = _mapping(item_d.get("details"))
    expanded_evidence_sections = {
        "reasons": reasons,
        "current": [dict(row) for row in list(item_d.get("current") or []) if isinstance(row, dict)],
        "preview": _mapping(item_d.get("preview")),
        "details": details,
        "exact_blockers_by_family": _mapping(
            item_d.get("exact_blockers_by_family") or details.get("exact_blockers_by_family")
        ),
        "blocker_attempts_by_family": _mapping(
            item_d.get("blocker_attempts_by_family") or details.get("blocker_attempts_by_family")
        ),
    }
    blocker_explanation = _text(
        item_d.get("blocker_explanation"),
        item_d.get("blocking_reason"),
        button_contract.get("blocking_reason"),
        button_contract.get("disabled_reason"),
        details.get("blocking_reason"),
    )
    display_state = _text(
        item_d.get("display_state"),
        item_d.get("status"),
        item_d.get("bucket"),
        "PROOF_PENDING",
    )
    final_card_model_fields = {
        "title": _text(item_d.get("title_main"), item_d.get("title")),
        "badge": _text(item_d.get("pill"), item_d.get("governing_label"), item_d.get("status"), item_d.get("bucket")),
        "summary": _text(item_d.get("summary_line"), item_d.get("primary_action"), item_d.get("reasoning")),
        "status": _text(item_d.get("status"), item_d.get("critical_status")),
        "bucket": _text(item_d.get("bucket")),
        "colour_state": _text(item_d.get("tone"), item_d.get("status"), item_d.get("bucket")),
        "card_class": _text(item_d.get("card_class"), item_d.get("final_card_class")),
        "display_state": display_state,
        "blocker_explanation": blocker_explanation,
    }
    fallback_shell_model = _mapping(item_d.get("render_fallback_shell_model"))
    if not fallback_shell_model and item_d.get("render_fallback_shell"):
        fallback_shell_model = {
            "title": final_card_model_fields["title"],
            "card_class": final_card_model_fields["card_class"],
            "fallback_only": True,
        }
    visible_wording = {
        "title": final_card_model_fields["title"],
        "summary": final_card_model_fields["summary"],
        "badge": final_card_model_fields["badge"],
        "blocker_explanation": blocker_explanation,
    }
    return FinalDesignGuideDisplay(
        title=visible_wording["title"],
        badge=visible_wording["badge"],
        summary=visible_wording["summary"],
        status=_text(item_d.get("status"), item_d.get("critical_status")),
        bucket=_text(item_d.get("bucket")),
        colour_state=final_card_model_fields["colour_state"],
        card_class=_text(item_d.get("card_class"), item_d.get("final_card_class")),
        display_state=display_state,
        expanded_evidence_sections=expanded_evidence_sections,
        blocker_explanation=blocker_explanation,
        final_card_model_fields=final_card_model_fields,
        final_card_model_hash=stable_final_publication_hash(final_card_model_fields),
        render_fallback_shell_model=fallback_shell_model,
        render_fallback_shell_hash=stable_final_publication_hash(fallback_shell_model),
        visible_wording_hash=stable_final_publication_hash(visible_wording),
        renderer_driving=False,
    )


def build_final_publication_display_from_current_card_model(
    *,
    view_model: dict[str, Any] | None = None,
    render_model: dict[str, Any] | None = None,
    fallback_shell_model: dict[str, Any] | None = None,
) -> FinalDesignGuideDisplay:
    """Proof-only adapter from current card VM/render-model state.

    This accepts already-shaped dictionaries only. It does not import page code,
    render HTML, decide CTA, or mutate live publication state.
    """

    vm_d = _mapping(view_model)
    rm_d = _mapping(render_model)
    shell_d = _mapping(fallback_shell_model)
    reasons = [
        dict(row)
        for row in list(
            rm_d.get("final_reasons")
            or rm_d.get("reason_display_rows")
            or vm_d.get("reasons")
            or []
        )
        if isinstance(row, dict)
    ]
    details = _mapping(rm_d.get("details_payload") or vm_d.get("details"))
    final_card_model_fields = {
        "title": _text(rm_d.get("title"), vm_d.get("title"), vm_d.get("title_main")),
        "badge": _text(rm_d.get("pill"), vm_d.get("pill"), vm_d.get("governing_label"), vm_d.get("status")),
        "summary": _text(rm_d.get("main_text"), vm_d.get("summary_line"), vm_d.get("primary_action")),
        "status": _text(rm_d.get("status"), vm_d.get("status")),
        "bucket": _text(vm_d.get("bucket")),
        "colour_state": _text(rm_d.get("card_tone"), vm_d.get("tone"), vm_d.get("status"), vm_d.get("bucket")),
        "card_class": _text(rm_d.get("card_class"), vm_d.get("card_class"), vm_d.get("final_card_class")),
        "display_state": _text(
            vm_d.get("display_state"),
            rm_d.get("status"),
            vm_d.get("status"),
            vm_d.get("bucket"),
            "PROOF_PENDING",
        ),
        "blocker_explanation": _text(
            rm_d.get("blocker_reason"),
            vm_d.get("blocker_explanation"),
            vm_d.get("blocking_reason"),
            details.get("blocking_reason"),
        ),
    }
    expanded_evidence_sections = {
        "reasons": reasons,
        "reason_display_rows": [
            dict(row)
            for row in list(rm_d.get("reason_display_rows") or [])
            if isinstance(row, dict)
        ],
        "current": [
            dict(row)
            for row in list(rm_d.get("current_rows") or vm_d.get("current") or [])
            if isinstance(row, dict)
        ],
        "preview": _mapping(rm_d.get("preview_rows") or vm_d.get("preview")),
        "preview_display_rows": [
            dict(row)
            for row in list(rm_d.get("preview_display_rows") or [])
            if isinstance(row, dict)
        ],
        "details": details,
        "blocker_evidence_display_fields": _mapping(rm_d.get("blocker_evidence_display_fields")),
        "terminal_status": _mapping(rm_d.get("terminal_status")),
    }
    visible_wording = {
        "title": final_card_model_fields["title"],
        "summary": final_card_model_fields["summary"],
        "badge": final_card_model_fields["badge"],
        "blocker_explanation": final_card_model_fields["blocker_explanation"],
    }
    return FinalDesignGuideDisplay(
        title=final_card_model_fields["title"],
        badge=final_card_model_fields["badge"],
        summary=final_card_model_fields["summary"],
        status=final_card_model_fields["status"],
        bucket=final_card_model_fields["bucket"],
        colour_state=final_card_model_fields["colour_state"],
        card_class=final_card_model_fields["card_class"],
        display_state=final_card_model_fields["display_state"],
        expanded_evidence_sections=expanded_evidence_sections,
        blocker_explanation=final_card_model_fields["blocker_explanation"],
        final_card_model_fields=final_card_model_fields,
        final_card_model_hash=stable_final_publication_hash(final_card_model_fields),
        render_fallback_shell_model=shell_d,
        render_fallback_shell_hash=stable_final_publication_hash(shell_d),
        visible_wording_hash=stable_final_publication_hash(visible_wording),
        renderer_driving=False,
    )


def build_final_design_guide_evidence(
    *,
    item: dict[str, Any] | None = None,
    debug: dict[str, Any] | None = None,
    design_brain_result: dict[str, Any] | None = None,
    publication_reason: str | None = None,
) -> FinalDesignGuideEvidence:
    item_d = _mapping(item)
    debug_d = _mapping(debug)
    result_d = _mapping(design_brain_result)
    evidence = _mapping(
        item_d.get("candidate_search_evidence")
        or debug_d.get("candidate_search_evidence")
        or _mapping(result_d.get("evidence")).get("candidate_search")
    )
    exact_stop_proof = _mapping(
        item_d.get("exact_stop_proof")
        or debug_d.get("exact_stop_proof")
        or result_d.get("exact_stop_proof")
    )
    if item_d.get("design_guide_terminal_state") and not exact_stop_proof:
        exact_stop_proof = {
            "terminal_state": item_d.get("design_guide_terminal_state"),
            "source": "publication_item",
        }
    target_band_proof = _mapping(
        item_d.get("target_band_proof")
        or debug_d.get("target_band_proof")
        or evidence.get("target_band_proof")
    )
    if not target_band_proof:
        target_band_proof = {
            "target_low": evidence.get("target_low") or _mapping(item_d.get("display_truth")).get("target_low"),
            "target_high": evidence.get("target_high") or _mapping(item_d.get("display_truth")).get("target_high"),
            "displayed_util": _mapping(item_d.get("display_truth")).get("displayed_util"),
        }
    stale_fresh_proof = _mapping(
        item_d.get("stale_fresh_proof")
        or debug_d.get("stale_fresh_proof")
        or {
            "render_metadata_normalised": bool(item_d.get("render_metadata_normalised")),
            "final_visible_state_fingerprint": item_d.get("final_visible_state_fingerprint"),
            "debug_publication_fingerprint": debug_d.get("design_guide_publication_fingerprint"),
        }
    )
    selected_family = _text(
        item_d.get("selected_family_id"),
        item_d.get("published_family_id"),
        item_d.get("cta_family_id"),
        debug_d.get("selected_family_id"),
        result_d.get("selected_family_id"),
        item_d.get("family"),
        item_d.get("check_key"),
    )
    published_item_id = _text(
        item_d.get("published_item_id"),
        item_d.get("final_visible_item_id"),
        item_d.get("publication_item_id"),
        item_d.get("source_candidate_id"),
        item_d.get("candidate_id"),
        _mapping(item_d.get("button_contract")).get("source_candidate_id"),
        _mapping(item_d.get("button_contract")).get("candidate_id"),
        _mapping(item_d.get("action_payload")).get("source_candidate_id"),
        _mapping(item_d.get("action_payload")).get("candidate_id"),
    )
    post_click_design_guide_state = _text(
        item_d.get("post_click_design_guide_state"),
        debug_d.get("post_click_design_guide_state"),
        item_d.get("design_guide_terminal_state"),
        debug_d.get("design_guide_terminal_state"),
    )
    blocker_reason = _text(
        item_d.get("blocking_reason"),
        _mapping(item_d.get("button_contract")).get("blocking_reason"),
        debug_d.get("blocked_publication_type"),
    )
    payload = {
        "published_item_id": published_item_id,
        "post_click_design_guide_state": post_click_design_guide_state,
        "selected_family": selected_family,
        "publication_reason": publication_reason,
        "blocker_reason": blocker_reason,
        "exact_stop_proof": exact_stop_proof,
        "target_band_proof": target_band_proof,
        "stale_fresh_proof": stale_fresh_proof,
        "candidate_search_evidence": evidence,
    }
    return FinalDesignGuideEvidence(
        published_item_id=published_item_id,
        post_click_design_guide_state=post_click_design_guide_state,
        selected_family=selected_family,
        publication_reason=_text(publication_reason, item_d.get("final_visible_resolver_reason"), result_d.get("outcome_id")),
        blocker_reason=blocker_reason,
        exact_stop_proof=exact_stop_proof,
        target_band_proof=target_band_proof,
        stale_fresh_proof=stale_fresh_proof,
        candidate_search_evidence=evidence,
        evidence_hash=stable_final_publication_hash(payload),
    )


def build_final_design_guide_verifier_payload(payload: dict[str, Any] | None = None) -> FinalDesignGuideVerifierPayload:
    payload_d = _mapping(payload)
    return FinalDesignGuideVerifierPayload(
        payload=payload_d,
        payload_hash=stable_final_publication_hash(payload_d),
        browser_driving=False,
    )


def build_final_design_guide_publication(
    *,
    item: dict[str, Any] | None = None,
    debug: dict[str, Any] | None = None,
    design_brain_result: dict[str, Any] | None = None,
    verifier_payload: dict[str, Any] | None = None,
    publication_reason: str | None = None,
) -> FinalDesignGuidePublication:
    """Normalize current distributed publication-shaped data into a proof object."""

    item_d = _mapping(item)
    debug_d = _mapping(debug)
    result_d = _mapping(design_brain_result)
    cta = build_final_design_guide_cta(item=item_d, debug=debug_d)
    display = build_final_design_guide_display(item=item_d)
    evidence = build_final_design_guide_evidence(
        item=item_d,
        debug=debug_d,
        design_brain_result=result_d,
        publication_reason=publication_reason,
    )
    verifier = build_final_design_guide_verifier_payload(verifier_payload)
    outcome = infer_final_design_guide_outcome_state(
        item=item_d,
        cta=cta,
        blocker_reason=evidence.blocker_reason,
    )
    source_payload = {
        "item": item_d,
        "debug": debug_d,
        "design_brain_result": result_d,
        "verifier_payload": _mapping(verifier_payload),
        "publication_reason": publication_reason,
    }
    publication = FinalDesignGuidePublication(
        published_item_id=evidence.published_item_id,
        post_click_design_guide_state=evidence.post_click_design_guide_state,
        selected_family=evidence.selected_family,
        outcome_state=outcome,
        publication_reason=evidence.publication_reason,
        blocker_reason=evidence.blocker_reason,
        exact_stop_proof=dict(evidence.exact_stop_proof),
        target_band_proof=dict(evidence.target_band_proof),
        cta=cta,
        display=display,
        evidence=evidence,
        verifier_payload=verifier,
        stale_fresh_proof=dict(evidence.stale_fresh_proof),
        source_hash=stable_final_publication_hash(source_payload),
        publication_hash=None,
        proof_only=True,
    )
    return publication.with_publication_hash()


def build_collapsed_guidance_item_from_final_publication(
    publication: FinalDesignGuidePublication,
    *,
    current_item_compatibility: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a proof-only collapsed-guidance item from final publication truth.

    The adapter accepts an already-built FinalDesignGuidePublication plus
    optional plain legacy item data. It does not render UI, route apply actions,
    read session state, or import page code.
    """

    if not isinstance(publication, FinalDesignGuidePublication):
        raise TypeError("publication must be a FinalDesignGuidePublication")

    legacy = _mapping(current_item_compatibility)
    cta = publication.cta.to_dict()
    display = publication.display.to_dict()
    evidence = publication.evidence.to_dict()
    verifier_payload = publication.verifier_payload.to_dict()
    button_contract = _mapping(legacy.get("button_contract"))
    action_payload = _mapping(legacy.get("action_payload"))
    if not button_contract:
        button_contract = {
            "enabled": bool(cta.get("enabled")),
            "actionable": bool(cta.get("actionable")),
            "label": cta.get("label"),
            "action_type": cta.get("action_type"),
            "family": cta.get("family") or publication.selected_family,
            "disabled_reason": cta.get("disabled_reason"),
            "source_candidate_id": cta.get("source_candidate_id") or publication.published_item_id,
            "final_publication_cta_authority": "FinalDesignGuidePublication.cta",
            "final_publication_cta_hash": stable_final_publication_hash(cta),
        }
    if not action_payload:
        action_payload = dict(cta.get("apply_payload_summary") or {})

    collapsed_item = {
        **legacy,
        "published_item_id": publication.published_item_id,
        "final_visible_item_id": publication.published_item_id,
        "publication_item_id": publication.published_item_id,
        "post_click_design_guide_state": publication.post_click_design_guide_state,
        "selected_family_id": publication.selected_family,
        "published_family_id": publication.selected_family,
        "family": publication.selected_family,
        "outcome_state": publication.outcome_state,
        "publication_reason": publication.publication_reason,
        "blocker_reason": publication.blocker_reason,
        "blocking_reason": publication.blocker_reason,
        "design_guide_terminal_state": publication.post_click_design_guide_state,
        "title_main": display.get("title") or legacy.get("title_main") or legacy.get("title"),
        "title": display.get("title") or legacy.get("title"),
        "pill": display.get("badge") or legacy.get("pill"),
        "summary_line": display.get("summary") or legacy.get("summary_line"),
        "status": display.get("status") or publication.outcome_state,
        "bucket": display.get("bucket") or legacy.get("bucket"),
        "display_state": display.get("display_state") or publication.outcome_state,
        "card_class": display.get("card_class") or legacy.get("card_class"),
        "blocker_explanation": display.get("blocker_explanation") or publication.blocker_reason,
        "button_contract": button_contract,
        "action_payload": action_payload,
        "candidate_search_evidence": dict(evidence.get("candidate_search_evidence") or {}),
        "exact_stop_proof": dict(publication.exact_stop_proof or {}),
        "target_band_proof": dict(publication.target_band_proof or {}),
        "stale_fresh_proof": dict(publication.stale_fresh_proof or {}),
        "final_publication_verifier_payload": dict(verifier_payload.get("payload") or {}),
        "final_publication_publication_hash": publication.publication_hash,
        "publication_hash": publication.publication_hash,
        "final_publication_authority_hash": publication.publication_hash,
        "final_publication_cta_hash": stable_final_publication_hash(cta),
        "final_publication_display_hash": stable_final_publication_hash(display),
        "final_publication_evidence_hash": stable_final_publication_hash(evidence),
        "final_publication_source_hash": publication.source_hash,
        "legacy_non_authoritative": True,
        "compatibility_only": True,
        "derived_from": "FinalDesignGuidePublication",
        "collapsed_guidance_adapter_proof_only": True,
        "product_driving": False,
        "render_driving": False,
    }
    collapsed_item["collapsed_guidance_item_hash"] = stable_final_publication_hash(
        {
            "published_item_id": collapsed_item.get("published_item_id"),
            "post_click_design_guide_state": collapsed_item.get("post_click_design_guide_state"),
            "selected_family": collapsed_item.get("selected_family_id"),
            "outcome_state": collapsed_item.get("outcome_state"),
            "cta_hash": collapsed_item.get("final_publication_cta_hash"),
            "display_hash": collapsed_item.get("final_publication_display_hash"),
            "evidence_hash": collapsed_item.get("final_publication_evidence_hash"),
            "publication_hash": collapsed_item.get("publication_hash"),
        }
    )
    return collapsed_item


def build_render_stage_post_resolver_item_mutation_proof(
    publication: FinalDesignGuidePublication,
    *,
    selected_item: dict[str, Any] | None = None,
    final_visible_resolution: dict[str, Any] | None = None,
    guidance_debug: dict[str, Any] | None = None,
) -> FinalDesignGuidePostResolverMutationProof:
    """Normalize render-stage post-resolver selected-item mutation truth.

    This proof-only adapter accepts plain dictionaries already produced by the
    page path. It does not import page code, render cards, route apply actions,
    read session state, or change the selected item.
    """

    if not isinstance(publication, FinalDesignGuidePublication):
        raise TypeError("publication must be a FinalDesignGuidePublication")

    item_d = _mapping(selected_item)
    resolution_d = _mapping(final_visible_resolution)
    debug_d = _mapping(guidance_debug)
    cta_d = publication.cta.to_dict()
    evidence_d = publication.evidence.to_dict()
    display_d = publication.display.to_dict()
    item_contract = _mapping(item_d.get("button_contract"))
    item_action_payload = _mapping(item_d.get("action_payload"))
    resolver_item = _mapping(resolution_d.get("item"))

    candidate_search_evidence = _mapping(
        evidence_d.get("candidate_search_evidence")
        or item_d.get("candidate_search_evidence")
        or debug_d.get("candidate_search_evidence")
    )
    exact_stop_proof = _mapping(publication.exact_stop_proof or evidence_d.get("exact_stop_proof"))
    target_band_proof = _mapping(publication.target_band_proof or evidence_d.get("target_band_proof"))
    exact_blockers = _mapping(
        item_d.get("exact_blockers_by_family")
        or debug_d.get("exact_blockers_by_family")
        or exact_stop_proof.get("exact_blockers_by_family")
    )
    post_click_exact_blockers = _mapping(
        item_d.get("post_click_exact_blockers_by_family")
        or debug_d.get("post_click_exact_blockers_by_family")
        or exact_stop_proof.get("post_click_exact_blockers_by_family")
    )
    blocker_attempts = _mapping(
        item_d.get("blocker_attempts_by_family")
        or debug_d.get("blocker_attempts_by_family")
        or candidate_search_evidence.get("blocker_attempts_by_family")
    )

    selected_item_identity = {
        "published_item_id": publication.published_item_id,
        "selected_family": publication.selected_family,
        "candidate_id": _text(
            item_d.get("candidate_id"),
            item_contract.get("candidate_id"),
            item_action_payload.get("candidate_id"),
            cta_d.get("apply_payload_summary", {}).get("candidate_id")
            if isinstance(cta_d.get("apply_payload_summary"), dict)
            else None,
            publication.published_item_id,
        ),
        "source_candidate_id": _text(
            item_d.get("source_candidate_id"),
            item_contract.get("source_candidate_id"),
            item_action_payload.get("source_candidate_id"),
            cta_d.get("source_candidate_id"),
            publication.published_item_id,
        ),
        "action_type": _text(
            item_d.get("action_type"),
            item_contract.get("action_type"),
            cta_d.get("action_type"),
        ),
        "family": _text(item_d.get("family"), item_contract.get("family"), publication.selected_family),
    }
    evidence_projection = {
        "candidate_search_evidence": candidate_search_evidence,
        "candidate_search_evidence_hash": stable_final_publication_hash(candidate_search_evidence),
        "target_band_proof": target_band_proof,
        "target_band_proof_hash": stable_final_publication_hash(target_band_proof),
        "stale_fresh_proof": dict(publication.stale_fresh_proof or evidence_d.get("stale_fresh_proof") or {}),
    }
    blocker_projection = {
        "blocker_reason": publication.blocker_reason or evidence_d.get("blocker_reason"),
        "exact_stop_proof": exact_stop_proof,
        "exact_stop_proof_hash": stable_final_publication_hash(exact_stop_proof),
        "exact_blockers_by_family": exact_blockers,
        "post_click_exact_blockers_by_family": post_click_exact_blockers,
        "blocker_attempts_by_family": blocker_attempts,
    }
    terminal_projection = {
        "outcome_state": publication.outcome_state,
        "post_click_design_guide_state": publication.post_click_design_guide_state,
        "design_guide_terminal_state": _text(
            item_d.get("design_guide_terminal_state"),
            publication.post_click_design_guide_state,
            publication.outcome_state,
        ),
        "publication_reason": publication.publication_reason,
    }
    resolver_projection = {
        "has_resolution_item": bool(resolver_item),
        "render_reason": resolution_d.get("render_reason"),
        "presentation": _mapping(resolution_d.get("presentation")),
        "resolution_item_hash": stable_final_publication_hash(resolver_item),
    }
    selected_item_projection = {
        "title": display_d.get("title") or item_d.get("title") or item_d.get("title_main"),
        "status": display_d.get("status") or item_d.get("status") or publication.outcome_state,
        "bucket": display_d.get("bucket") or item_d.get("bucket"),
        "util": item_d.get("util"),
        "expected_util": item_d.get("expected_util") or item_contract.get("expected_util"),
        "candidate_post_util": item_d.get("candidate_post_util"),
        "resolved_candidate": _mapping(item_d.get("resolved_candidate")),
        "action_payload_hash": stable_final_publication_hash(item_action_payload),
        "button_contract_hash": stable_final_publication_hash(item_contract),
    }
    debug_projection = {
        "candidate_search_evidence_hash": stable_final_publication_hash(
            _mapping(debug_d.get("candidate_search_evidence"))
        ),
        "blocker_attempts_hash": stable_final_publication_hash(
            _mapping(debug_d.get("blocker_attempts_by_family"))
        ),
        "debug_keys_hash": stable_final_publication_hash(sorted(debug_d.keys())),
    }
    mutation_target_coverage = {
        "selected_item_identity": bool(selected_item_identity.get("candidate_id")),
        "candidate_search_evidence": bool(candidate_search_evidence),
        "blocker_attempts_by_family": bool(blocker_attempts),
        "exact_blockers_by_family": bool(exact_blockers or post_click_exact_blockers),
        "terminal_state": bool(terminal_projection.get("design_guide_terminal_state")),
        "resolver_output": bool(resolver_projection.get("has_resolution_item") or resolver_projection.get("render_reason")),
        "utilisation_fields": any(
            selected_item_projection.get(key) is not None
            for key in ("util", "expected_util", "candidate_post_util")
        ),
        "resolved_candidate": bool(selected_item_projection.get("resolved_candidate")),
        "cta_apply_identity": bool(selected_item_identity.get("action_type")),
    }
    adapter_owned_mutation_truth = {
        "classification": "adapter_owned_mutation_truth_represented_by_FinalDesignGuidePostResolverMutationProof",
        "candidate_search_evidence": bool(candidate_search_evidence),
        "blocker_attempts_by_family": bool(blocker_attempts),
        "exact_blockers_by_family": bool(exact_blockers or post_click_exact_blockers),
        "terminal_state": bool(terminal_projection.get("design_guide_terminal_state")),
        "utilisation_projection": any(
            selected_item_projection.get(key) is not None
            for key in ("util", "expected_util", "candidate_post_util")
        ),
        "resolved_candidate_projection": bool(selected_item_projection.get("resolved_candidate")),
        "cta_apply_identity": bool(selected_item_identity.get("action_type")),
        "publication_hash": publication.publication_hash,
    }
    remaining_resolver_truth = {
        "classification": "remaining_live_resolver_truth_not_narrowed",
        "selected_item_replacement": bool(item_d),
        "resolution_item_replacement": bool(resolver_item),
        "resolver_render_reason": bool(resolution_d.get("render_reason")),
        "resolver_presentation": bool(resolution_d.get("presentation")),
        "post_resolver_bridge_narrowed": False,
        "narrowing_allowed_by_this_proof": False,
    }
    payload = {
        "selected_item_identity": selected_item_identity,
        "adapter_owned_mutation_truth": adapter_owned_mutation_truth,
        "remaining_resolver_truth": remaining_resolver_truth,
        "evidence_projection": evidence_projection,
        "blocker_projection": blocker_projection,
        "terminal_projection": terminal_projection,
        "resolver_projection": resolver_projection,
        "selected_item_projection": selected_item_projection,
        "debug_projection": debug_projection,
        "mutation_target_coverage": mutation_target_coverage,
        "publication_hash": publication.publication_hash,
    }
    return FinalDesignGuidePostResolverMutationProof(
        selected_item_identity=selected_item_identity,
        adapter_owned_mutation_truth=adapter_owned_mutation_truth,
        remaining_resolver_truth=remaining_resolver_truth,
        evidence_projection=evidence_projection,
        blocker_projection=blocker_projection,
        terminal_projection=terminal_projection,
        resolver_projection=resolver_projection,
        selected_item_projection=selected_item_projection,
        debug_projection=debug_projection,
        mutation_target_coverage=mutation_target_coverage,
        mutation_proof_hash=stable_final_publication_hash(payload),
    )


def build_final_design_guide_post_resolver_mutation_proof(
    publication: FinalDesignGuidePublication,
    *,
    selected_item: dict[str, Any] | None = None,
    final_visible_resolution: dict[str, Any] | None = None,
    guidance_debug: dict[str, Any] | None = None,
) -> FinalDesignGuidePostResolverMutationProof:
    """Alias for the canonical post-resolver mutation proof builder."""

    return build_render_stage_post_resolver_item_mutation_proof(
        publication,
        selected_item=selected_item,
        final_visible_resolution=final_visible_resolution,
        guidance_debug=guidance_debug,
    )


__all__ = [
    "FinalDesignGuideCTA",
    "FinalDesignGuideDisplay",
    "FinalDesignGuideEvidence",
    "FinalDesignGuideOutcomeState",
    "FinalDesignGuidePostResolverMutationProof",
    "FinalDesignGuidePublication",
    "FinalDesignGuideVerifierPayload",
    "build_final_design_guide_cta",
    "build_final_design_guide_display",
    "build_final_design_guide_evidence",
    "build_final_design_guide_publication",
    "build_final_design_guide_post_resolver_mutation_proof",
    "build_final_design_guide_verifier_payload",
    "build_collapsed_guidance_item_from_final_publication",
    "build_final_publication_display_from_current_card_model",
    "build_final_publication_cta_from_current_state",
    "build_render_stage_post_resolver_item_mutation_proof",
    "infer_final_design_guide_outcome_state",
    "stable_final_publication_hash",
]
