"""Application composition for the live, fail-closed Design Brain pipeline.

The family runtimes still own their engineering-specific ladder algorithms.
This module owns the application handoff: it projects their finalist and
evidence into the pure pipeline contract, rejects any unapproved or
non-executor-backed finalist, and only then permits publication and Apply.
It contains no Streamlit or session-state dependency.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from math import inf
from typing import Any, Mapping

from application.guidance_result_adapter import (
    GuidanceAuthorityResolution,
    build_authoritative_design_result_from_guidance_payload,
    resolve_guidance_authority,
)
from application.contracts.design_brain import AuthoritativeDesignResult, EngineeringInputSnapshot
from inputs_application.legacy_design_brain_adapter import (
    ApplyCommandConstructionStage,
    ApprovedCandidateProposal,
    AuthoritativeCandidateEvaluation,
    CandidateEvaluationStage,
    CandidateGenerationStage,
    CandidateSelectionStage,
    DesignBrainPipelineDependencies,
    EngineeringResultIntakeStage,
    FamilyDispatchStage,
    GoverningStateClassificationStage,
    PIPELINE_STAGE_ORDER,
    PublicationConstructionStage,
    run_design_brain_pipeline,
    normalise_governing_family,
    resolve_family_ladder_dispatch,
)


LIVE_PIPELINE_SCHEMA = "live_design_brain_pipeline.v1"


@dataclass(frozen=True)
class LiveDesignBrainExecution:
    result: AuthoritativeDesignResult
    guidance_payload: dict[str, Any]
    authority: GuidanceAuthorityResolution
    stage_trace: tuple[str, ...]
    pipeline_applied: bool
    bypass_reason: str | None = None


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _candidate_evidence(
    authority: GuidanceAuthorityResolution,
) -> dict[str, Any]:
    selected = _mapping(authority.selected_candidate)
    return _mapping(
        selected.get("candidate_search_evidence")
        or authority.primary.get("candidate_search_evidence")
        or authority.guidance_debug.get("candidate_search_evidence")
    )


def _approved_value(
    authority: GuidanceAuthorityResolution,
    evidence: Mapping[str, Any],
    key: str,
) -> Any:
    selected = _mapping(authority.selected_candidate)
    if selected.get(key) is not None:
        return selected.get(key)
    if authority.primary.get(key) is not None:
        return authority.primary.get(key)
    return evidence.get(key)


def _float_or_inf(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return inf


def _executor_row_for(
    evidence: Mapping[str, Any],
    candidate_id: str,
) -> dict[str, Any]:
    # The general safe list is intentionally bounded for display evidence;
    # the selected target-band finalist can therefore live only in the
    # target-band evidence list.  Both lists contain the same explicit
    # ``safe_executor_backed`` truth contract.
    for key in (
        "safe_executor_backed_candidates",
        "target_band_candidates",
    ):
        for raw in list(evidence.get(key) or []):
            row = _mapping(raw)
            if str(row.get("candidate_id") or "").strip() == candidate_id:
                return row
    return {}


def run_live_design_brain_pipeline(
    *,
    engineering_snapshot: EngineeringInputSnapshot,
    guidance_payload: Mapping[str, Any] | None,
    family_override: str | None = None,
    resolved_inputs: Mapping[str, Any] | None = None,
    engineering_calculations: Mapping[str, Any] | None = None,
) -> LiveDesignBrainExecution:
    """Validate and publish one classified live guidance result.

    A START/pre-design payload is not a Design Brain decision and is returned
    through the result adapter without pretending that a family was selected.
    Every classified payload takes the complete nine-stage pipeline.
    """

    payload = _mapping(guidance_payload)
    authority = resolve_guidance_authority(
        guidance_payload=payload,
        family_override=family_override,
        resolved_inputs=resolved_inputs,
    )
    family_id = normalise_governing_family(authority.governing_family or "")
    if not family_id:
        if authority.selected_updates:
            raise ValueError(
                "unclassified guidance cannot publish candidate updates"
            )
        result = build_authoritative_design_result_from_guidance_payload(
            engineering_snapshot=engineering_snapshot,
            guidance_payload=payload,
            family_override=family_override,
            resolved_inputs=resolved_inputs,
            engineering_calculations=engineering_calculations,
            authority_resolution=authority,
        )
        return LiveDesignBrainExecution(
            result=result,
            guidance_payload=payload,
            authority=authority,
            stage_trace=(),
            pipeline_applied=False,
            bypass_reason="pre_design_unclassified_payload",
        )

    context: dict[str, Any] = {}

    def intake(validated: Any) -> EngineeringResultIntakeStage:
        context["authority"] = authority
        return EngineeringResultIntakeStage(
            snapshot=validated.snapshot,
            engineering_hash=validated.engineering_hash,
            calculations=_mapping(authority.guidance_debug.get("overview")),
            whole_beam_evidence={
                **authority.guidance_debug,
                "selected_family_id": family_id,
            },
        )

    def classify(
        intake_stage: EngineeringResultIntakeStage,
    ) -> GoverningStateClassificationStage:
        return GoverningStateClassificationStage(
            engineering_hash=intake_stage.engineering_hash,
            family_id=family_id,
            classification_evidence={
                "selected_family_id": family_id,
                "classification_passed": True,
                "selection_source": "application.guidance_result_adapter",
                "whole_beam_evidence": dict(intake_stage.whole_beam_evidence),
            },
        )

    def dispatch(
        classified: GoverningStateClassificationStage,
    ) -> FamilyDispatchStage:
        decision = resolve_family_ladder_dispatch(
            dict(classified.classification_evidence)
        )
        if decision.legacy_fallback_allowed:
            raise RuntimeError(
                "classified family attempted to enter a legacy fallback"
            )
        if not decision.terminal_family and not decision.should_run_family_ladder:
            raise RuntimeError(
                "classified family has no callable approved ladder"
            )
        stage = FamilyDispatchStage(
            engineering_hash=classified.engineering_hash,
            family_id=classified.family_id,
            strategy_owner=(
                decision.strategy_owner
                or "design_brain.family_ladder_dispatch.terminal"
            ),
            ladder_method=decision.ladder_method,
            candidate_contract_id=str(decision.candidate_contract_id or ""),
            generation_policy_id=str(decision.generation_policy_id or ""),
            evaluation_policy_id=str(decision.evaluation_policy_id or ""),
            selection_policy_id=str(decision.selection_policy_id or ""),
            terminal_family=decision.terminal_family,
            dispatch_evidence=decision.to_dict(),
        )
        context["dispatch"] = stage
        return stage

    def generate(
        dispatched: FamilyDispatchStage,
    ) -> CandidateGenerationStage:
        evidence = _candidate_evidence(authority)
        context["candidate_evidence"] = evidence
        if dispatched.terminal_family or not authority.selected_updates:
            return CandidateGenerationStage(
                engineering_hash=dispatched.engineering_hash,
                family_id=dispatched.family_id,
                candidate_contract_id=dispatched.candidate_contract_id,
                generation_policy_id=dispatched.generation_policy_id,
                candidates=(),
                generation_evidence={
                    "terminal_family": dispatched.terminal_family,
                    "typed_no_candidate": not bool(authority.selected_updates),
                },
            )

        selected = _mapping(authority.selected_candidate)
        candidate_id = str(
            selected.get("candidate_id")
            or selected.get("source_candidate_id")
            or evidence.get("selected_candidate_id")
            or ""
        ).strip()
        if not candidate_id:
            raise ValueError("approved live candidate has no stable candidate id")
        approved = _approved_value(
            authority,
            evidence,
            "candidate_contract_approved",
        )
        if approved is not True:
            raise ValueError(
                "live finalist was not emitted by an approved family contract "
                f"(family={dispatched.family_id!r}, candidate_id={candidate_id!r}, "
                f"approved={approved!r}, source_stage="
                f"{_approved_value(authority, evidence, 'candidate_source_stage')!r}, "
                f"evidence_keys={sorted(evidence)})"
            )
        expected_fields = {
            "candidate_contract_id": dispatched.candidate_contract_id,
            "candidate_generation_policy_id": dispatched.generation_policy_id,
            "candidate_evaluation_policy_id": dispatched.evaluation_policy_id,
            "candidate_selection_policy_id": dispatched.selection_policy_id,
        }
        for key, expected in expected_fields.items():
            observed = str(_approved_value(authority, evidence, key) or "").strip()
            if observed != expected:
                raise ValueError(f"live finalist changed approved {key}")
        candidate_family = normalise_governing_family(
            str(
                _approved_value(authority, evidence, "candidate_family_id")
                or _approved_value(authority, evidence, "selected_family_id")
                or dispatched.family_id
            )
        )
        if candidate_family != dispatched.family_id:
            raise ValueError("live finalist belongs to a different family")
        source_stage = str(
            _approved_value(authority, evidence, "candidate_source_stage") or ""
        ).strip()
        if not source_stage.startswith("family_ladder:"):
            raise ValueError("live finalist did not originate from a family ladder")
        proposal = ApprovedCandidateProposal(
            candidate_id=candidate_id,
            family_id=dispatched.family_id,
            candidate_contract_id=dispatched.candidate_contract_id,
            ladder_step_id=str(
                selected.get("family_ladder_candidate_id")
                or selected.get("ladder_step_id")
                or candidate_id
            ),
            ordinal=int(selected.get("candidate_index") or 1),
            updates=dict(authority.selected_updates),
        )
        return CandidateGenerationStage(
            engineering_hash=dispatched.engineering_hash,
            family_id=dispatched.family_id,
            candidate_contract_id=dispatched.candidate_contract_id,
            generation_policy_id=dispatched.generation_policy_id,
            candidates=(proposal,),
            generation_evidence={
                "scope": "approved_family_runtime_finalist",
                "family_ladder_attempts": evidence.get("ladder_attempts"),
                "candidate_contract_approved": True,
                "candidate_source_stage": source_stage,
            },
        )

    def evaluate(
        generated: CandidateGenerationStage,
    ) -> CandidateEvaluationStage:
        evidence = _mapping(context.get("candidate_evidence"))
        dispatched = context.get("dispatch")
        if not isinstance(dispatched, FamilyDispatchStage):
            raise RuntimeError("candidate evaluation has no family dispatch")
        evaluations: list[AuthoritativeCandidateEvaluation] = []
        for proposal in generated.candidates:
            row = _executor_row_for(evidence, proposal.candidate_id)
            if row.get("safe_executor_backed") is not True:
                raise ValueError(
                    "approved live candidate lacks authoritative executor evidence"
                )
            compliant = bool(
                row.get("preview_pass") is True
                and row.get("is_executable") is not False
                and row.get("advisory_only") is not True
            )
            if not compliant:
                raise ValueError(
                    "approved live candidate is not executor-proven compliant"
                )
            distance = _float_or_inf(row.get("distance_to_band"))
            rank_key = (
                0,
                0 if row.get("reaches_target_band") is True else 1,
                distance,
                proposal.ordinal,
                proposal.candidate_id,
            )
            evaluations.append(
                AuthoritativeCandidateEvaluation(
                    proposal=proposal,
                    engineering_hash=generated.engineering_hash,
                    evaluator_id="authoritative_engineering_executor.v1",
                    executor_backed=True,
                    compliant=True,
                    rank_key=rank_key,
                    result=row,
                )
            )
        return CandidateEvaluationStage(
            engineering_hash=generated.engineering_hash,
            family_id=generated.family_id,
            evaluation_policy_id=dispatched.evaluation_policy_id,
            evaluated_candidates=tuple(evaluations),
            evaluation_evidence={
                "evaluated_finalist_count": len(evaluations),
                "executor_backed": all(row.executor_backed for row in evaluations),
            },
        )

    def select(
        evaluated: CandidateEvaluationStage,
    ) -> CandidateSelectionStage:
        dispatched = context.get("dispatch")
        if not isinstance(dispatched, FamilyDispatchStage):
            raise RuntimeError("candidate selection has no family dispatch")
        ranked = tuple(
            sorted(
                evaluated.evaluated_candidates,
                key=lambda row: (row.rank_key, row.proposal.candidate_id),
            )
        )
        if ranked:
            return CandidateSelectionStage(
                engineering_hash=evaluated.engineering_hash,
                family_id=evaluated.family_id,
                selection_policy_id=dispatched.selection_policy_id,
                ranked_candidate_ids=tuple(
                    row.proposal.candidate_id for row in ranked
                ),
                selected_candidate=ranked[0],
                selection_evidence={
                    "approved_system": True,
                    "random_selection_allowed": False,
                    "fit_until_pass_allowed": False,
                    "family_runtime_finalist_revalidated": True,
                },
            )
        no_candidate = dict(authority.selected_candidate_absence or {})
        no_candidate.update(
            {
                "kind": (
                    "terminal_family"
                    if dispatched.terminal_family
                    else "family_no_publishable_candidate"
                ),
                "family": evaluated.family_id,
                "legacy_fallback_allowed": False,
            }
        )
        return CandidateSelectionStage(
            engineering_hash=evaluated.engineering_hash,
            family_id=evaluated.family_id,
            selection_policy_id=dispatched.selection_policy_id,
            ranked_candidate_ids=(),
            selected_candidate=None,
            no_candidate_outcome=no_candidate,
            selection_evidence={
                "approved_system": True,
                "legacy_fallback_allowed": False,
            },
        )

    def publish(
        selected: CandidateSelectionStage,
    ) -> PublicationConstructionStage:
        result = build_authoritative_design_result_from_guidance_payload(
            engineering_snapshot=engineering_snapshot,
            guidance_payload=payload,
            family_override=family_override,
            resolved_inputs=resolved_inputs,
            engineering_calculations=engineering_calculations,
            authority_resolution=authority,
        )
        pipeline_evidence = {
            "schema": LIVE_PIPELINE_SCHEMA,
            "stage_order": list(PIPELINE_STAGE_ORDER),
            "family_id": selected.family_id,
            "candidate_contract_id": (
                selected.selected_candidate.proposal.candidate_contract_id
                if selected.selected_candidate is not None
                else None
            ),
            "approved_candidate_system": True,
            "authoritative_executor_required": True,
            "random_selection_allowed": False,
            "fit_until_pass_allowed": False,
        }
        result = replace(
            result,
            candidate_acceptance_proof={
                **dict(result.candidate_acceptance_proof or {}),
                "live_design_brain_pipeline": pipeline_evidence,
            },
            final_publication={
                **dict(result.final_publication or {}),
                "live_design_brain_pipeline": pipeline_evidence,
            },
            publication_authority_hash=None,
        ).with_publication_authority_hash()
        return PublicationConstructionStage(
            engineering_hash=selected.engineering_hash,
            family_id=selected.family_id,
            result=result,
            publication_evidence=pipeline_evidence,
        )

    def build_apply(
        publication: PublicationConstructionStage,
    ) -> ApplyCommandConstructionStage:
        command = dict(publication.result.apply_payload or {})
        return ApplyCommandConstructionStage(
            engineering_hash=publication.engineering_hash,
            family_id=publication.family_id,
            result=publication.result,
            apply_command=command,
            apply_evidence={
                "source": "authoritative_design_result.apply_payload",
                "engineering_hash": publication.engineering_hash,
            },
        )

    pipeline = run_design_brain_pipeline(
        snapshot=engineering_snapshot,
        dependencies=DesignBrainPipelineDependencies(
            engineering_result_intake=intake,
            governing_state_classification=classify,
            family_dispatch=dispatch,
            candidate_generation=generate,
            candidate_evaluation=evaluate,
            candidate_selection=select,
            publication_construction=publish,
            apply_command_construction=build_apply,
        ),
    )
    return LiveDesignBrainExecution(
        result=pipeline.result,
        guidance_payload=payload,
        authority=authority,
        stage_trace=pipeline.stage_trace,
        pipeline_applied=True,
    )


__all__ = [
    "LIVE_PIPELINE_SCHEMA",
    "LiveDesignBrainExecution",
    "run_live_design_brain_pipeline",
]
