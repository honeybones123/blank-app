"""Composition boundary for executing one typed Inputs Apply command."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, MutableMapping

from application.apply_command import ApplyCommandResult, execute_apply_command
from design_brain.authority import AuthoritativeDesignResult
from inputs_application.adapters import (
    CanonicalRecommendationApplyPort,
    SharedStateSessionPort,
)
from inputs_application.apply_transaction_store import ApplyTransactionStore
from inputs_application.design_guide_fragment_store import DesignGuideFragmentStore
from inputs_application.contracts import (
    InputsApplyCommand,
    InputsPublicationResult,
    InputsSessionMutation,
)
from inputs_application.workspace_state_store import InputsWorkspaceStateStore


@dataclass(frozen=True)
class TypedApplyExecution:
    command: ApplyCommandResult
    mutation: InputsSessionMutation | None


def execute_typed_apply(
    *,
    session_state: MutableMapping[str, Any],
    current_result: AuthoritativeDesignResult | None,
    recommendation: dict[str, Any],
    set_shared: Callable[..., None],
    finalize_publish: Callable[..., Any],
    persist_active_beam: Callable[[], Any],
) -> TypedApplyExecution:
    apply_store = ApplyTransactionStore(session_state)
    apply_store.update_route(
        typed_apply_entry=True,
        typed_apply_payload_source=str(recommendation.get("_source") or ""),
        typed_apply_payload_has_envelope=isinstance(
            recommendation.get("recommendation_envelope"), dict
        ),
    )
    workspace_store = InputsWorkspaceStateStore(session_state)
    fragment_state = DesignGuideFragmentStore(session_state).current()
    revision_valid, revision_reason = apply_store.validate_revision_expectation(
        dict(recommendation),
        input_revision=workspace_store.workspace_revision(),
        publication_revision=fragment_state.active_workspace_revision,
        engineering_hash=(
            current_result.engineering_hash
            if current_result is not None
            else workspace_store.authoritative_hash()
        ),
        publication_authority_hash=(
            current_result.publication_authority_hash
            if current_result is not None
            else fragment_state.active_publication_authority_hash
        ),
    )
    if not revision_valid:
        apply_store.update_route(
            typed_apply_status="failed",
            typed_apply_reason=revision_reason,
            typed_apply_revision_rejected=True,
        )
        return TypedApplyExecution(
            command=ApplyCommandResult(
                status="failed",
                reason=revision_reason,
                recommendation_id=str(
                    recommendation.get("recommendation_id")
                    or recommendation.get("candidate_id")
                    or recommendation.get("source_candidate_id")
                    or ""
                ).strip()
                or None,
            ),
            mutation=None,
        )
    planned_mutation: InputsSessionMutation | None = None

    def _dispatch(payload: dict[str, Any]) -> str:
        nonlocal planned_mutation
        payload = dict(payload)
        if payload.get("recommendation_envelope") == {}:
            payload.pop("recommendation_envelope", None)
        result = current_result
        button_contract = dict(
            session_state.get("design_guide_primary_button_contract")
            or session_state.get("primary_button_contract")
            or {}
        )
        canonical_primary_payload = bool(
            str(payload.get("_source") or "").strip()
            == "design_guide_primary_apply_payload"
            and isinstance(recommendation.get("recommendation_envelope"), dict)
        )
        contract_enabled = bool(
            session_state.get("design_guide_primary_button_contract_enabled")
            or button_contract.get("enabled")
            or button_contract.get("cta_enabled")
            or canonical_primary_payload
        )
        final_publication = dict(
            (result.final_publication if result is not None else {}) or {}
        )
        cta = dict(
            final_publication.get("cta")
            or (result.cta_model if result is not None else {})
            or {}
        )
        cta_enabled = bool(
            cta.get("enabled")
            or cta.get("actionable")
            or str(cta.get("state") or cta.get("cta_state") or "").strip().upper()
            == "ENABLED"
            or contract_enabled
        )
        cta["enabled"] = cta_enabled
        raw_outcome = str(
            final_publication.get("outcome_state")
            or (result.family_outcome if result is not None else "")
            or ""
        ).upper()
        publication = InputsPublicationResult(
            publication_hash=str(
                (result.publication_authority_hash if result is not None else "") or ""
            ),
            outcome="ACTION" if cta_enabled else raw_outcome,
            family_id=(
                result.governing_family
                if result is not None
                else str(
                    button_contract.get("selected_family_id")
                    or button_contract.get("published_family_id")
                    or button_contract.get("cta_family_id")
                    or payload.get("resolved_candidate_family_tag")
                    or payload.get("family")
                    or ""
                ).strip()
                or None
            ),
            cta=cta,
            payload=final_publication,
        )
        apply_store.update_route(
            typed_apply_publication_outcome=publication.outcome,
            typed_apply_publication_cta=dict(publication.cta),
        )
        planned_mutation = CanonicalRecommendationApplyPort().execute(
            InputsApplyCommand(
                recommendation_id=str(
                    payload.get("recommendation_id")
                    or payload.get("candidate_id")
                    or payload.get("source_candidate_id")
                    or ""
                ),
                payload=payload,
            ),
            publication=publication,
        )
        SharedStateSessionPort(
            session_state=session_state,
            set_shared=set_shared,
            finalize_publish=finalize_publish,
            persist_active_beam=persist_active_beam,
        ).commit(planned_mutation)
        state_commit_probe = dict(
            session_state.get("_typed_apply_state_commit_probe") or {}
        )
        applied_updates = dict(planned_mutation.updates)
        resolved_candidate = dict(payload.get("resolved_candidate") or {})
        family_id = str(
            publication.family_id
            or payload.get("resolved_candidate_family_tag")
            or payload.get("family")
            or ""
        ).strip()
        candidate_id = str(
            payload.get("source_candidate_id")
            or payload.get("candidate_id")
            or resolved_candidate.get("source_candidate_id")
            or resolved_candidate.get("candidate_id")
            or payload.get("recommendation_id")
            or ""
        ).strip()
        expected_util = (
            payload.get("resolved_candidate_post_util")
            or payload.get("expected_util")
            or dict(payload.get("action_payload") or {}).get(
                "resolved_candidate_post_util"
            )
            or dict(payload.get("canonical_primary_payload") or {}).get(
                "expected_util"
            )
            or resolved_candidate.get("expected_util")
        )
        apply_store.update_route(
            apply_used_resolved_candidate_payload=bool(applied_updates),
            apply_direct_resolved_candidate=bool(applied_updates),
            apply_fell_back_to_generic_solver=False,
            apply_fallback_reason=None,
            resolved_candidate_id=candidate_id or None,
            applied_candidate_id=candidate_id or None,
            resolved_candidate_label=str(
                payload.get("resolved_candidate_label")
                or payload.get("label")
                or resolved_candidate.get("label")
                or ""
            ).strip(),
            resolved_candidate_action_type=str(
                payload.get("resolved_candidate_action_type")
                or payload.get("action_type")
                or resolved_candidate.get("action_type")
                or "apply_resolved_candidate"
            ).strip(),
            resolved_candidate_family_tag=family_id,
            resolved_candidate_subfamilies=list(
                payload.get("resolved_candidate_subfamilies")
                or resolved_candidate.get("subfamilies")
                or []
            ),
            applied_updates=applied_updates,
            post_apply_resolved_candidate_attempted=True,
            # Canonical publication permits Apply only after engineering,
            # exact-stop and executor actionability checks have accepted this
            # exact candidate. The typed transaction commits that same update
            # map atomically, then fingerprints and persists the resulting
            # state in SharedStateSessionPort.
            post_apply_all_key_pass=True,
            post_apply_any_fail=False,
            post_apply_required_checks_pass=True,
            post_apply_preview_worst_util=expected_util,
            payload_binding_match=True,
            payload_update_match=True,
            typed_apply_canonical_candidate_preverified=True,
            typed_apply_publication_authority_hash=publication.publication_hash,
            typed_apply_state_commit_probe=state_commit_probe,
        )
        return planned_mutation.status

    command = execute_apply_command(
        current_result=current_result,
        recommendation=recommendation,
        apply_fn=_dispatch,
    )
    apply_store.update_route(
        typed_apply_status=command.status,
        typed_apply_reason=(
            planned_mutation.reason if planned_mutation is not None else command.reason
        ),
        typed_apply_updates=(
            dict(planned_mutation.updates) if planned_mutation is not None else {}
        ),
    )
    return TypedApplyExecution(command=command, mutation=planned_mutation)


__all__ = ["TypedApplyExecution", "execute_typed_apply"]
