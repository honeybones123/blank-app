"""Explicit, pure Design Brain pipeline contracts and orchestrator.

The pipeline owns ordering and cross-stage identity only. Family policy remains
inside injected Design Brain stage implementations. No stage receives session,
render, widget, or cache objects.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Mapping

from design_brain.authority import (
    AuthoritativeDesignResult,
    EngineeringInputSnapshot,
)


PIPELINE_STAGE_ORDER = (
    "snapshot_validation",
    "engineering_result_intake",
    "governing_state_classification",
    "family_dispatch",
    "candidate_generation",
    "candidate_evaluation",
    "candidate_selection",
    "publication_construction",
    "apply_command_construction",
)


@dataclass(frozen=True)
class SnapshotValidationStage:
    snapshot: EngineeringInputSnapshot
    engineering_hash: str
    valid: bool = True
    evidence: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class EngineeringResultIntakeStage:
    snapshot: EngineeringInputSnapshot
    engineering_hash: str
    calculations: Mapping[str, Any] = field(default_factory=dict)
    whole_beam_evidence: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class GoverningStateClassificationStage:
    engineering_hash: str
    family_id: str
    classification_evidence: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class FamilyDispatchStage:
    engineering_hash: str
    family_id: str
    strategy_owner: str
    ladder_method: str | None
    candidate_contract_id: str
    generation_policy_id: str
    evaluation_policy_id: str
    selection_policy_id: str
    terminal_family: bool = False
    dispatch_evidence: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ApprovedCandidateProposal:
    """A candidate emitted by the selected family's approved ladder contract."""

    candidate_id: str
    family_id: str
    candidate_contract_id: str
    ladder_step_id: str
    ordinal: int
    updates: Mapping[str, Any]


@dataclass(frozen=True)
class CandidateGenerationStage:
    engineering_hash: str
    family_id: str
    candidate_contract_id: str
    generation_policy_id: str
    candidates: tuple[ApprovedCandidateProposal, ...] = ()
    generation_evidence: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AuthoritativeCandidateEvaluation:
    """One approved proposal evaluated by the authoritative engineering executor."""

    proposal: ApprovedCandidateProposal
    engineering_hash: str
    evaluator_id: str
    executor_backed: bool
    compliant: bool
    rank_key: tuple[Any, ...]
    result: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class CandidateEvaluationStage:
    engineering_hash: str
    family_id: str
    evaluation_policy_id: str
    evaluated_candidates: tuple[AuthoritativeCandidateEvaluation, ...] = ()
    evaluation_evidence: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class CandidateSelectionStage:
    engineering_hash: str
    family_id: str
    selection_policy_id: str
    ranked_candidate_ids: tuple[str, ...] = ()
    selected_candidate: AuthoritativeCandidateEvaluation | None = None
    no_candidate_outcome: Mapping[str, Any] | None = None
    selection_evidence: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class PublicationConstructionStage:
    engineering_hash: str
    family_id: str
    result: AuthoritativeDesignResult
    publication_evidence: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ApplyCommandConstructionStage:
    engineering_hash: str
    family_id: str
    result: AuthoritativeDesignResult
    apply_command: Mapping[str, Any] = field(default_factory=dict)
    apply_evidence: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class DesignBrainPipelineDependencies:
    engineering_result_intake: Callable[
        [SnapshotValidationStage], EngineeringResultIntakeStage
    ]
    governing_state_classification: Callable[
        [EngineeringResultIntakeStage], GoverningStateClassificationStage
    ]
    family_dispatch: Callable[
        [GoverningStateClassificationStage], FamilyDispatchStage
    ]
    candidate_generation: Callable[
        [FamilyDispatchStage], CandidateGenerationStage
    ]
    candidate_evaluation: Callable[
        [CandidateGenerationStage], CandidateEvaluationStage
    ]
    candidate_selection: Callable[
        [CandidateEvaluationStage], CandidateSelectionStage
    ]
    publication_construction: Callable[
        [CandidateSelectionStage], PublicationConstructionStage
    ]
    apply_command_construction: Callable[
        [PublicationConstructionStage], ApplyCommandConstructionStage
    ]
    snapshot_validation: Callable[
        [EngineeringInputSnapshot], SnapshotValidationStage
    ] | None = None


@dataclass(frozen=True)
class DesignBrainPipelineResult:
    result: AuthoritativeDesignResult
    apply_command: Mapping[str, Any]
    stage_trace: tuple[str, ...]
    engineering_hash: str
    family_id: str


def validate_engineering_snapshot(
    snapshot: EngineeringInputSnapshot,
) -> SnapshotValidationStage:
    if not isinstance(snapshot, EngineeringInputSnapshot):
        raise TypeError("snapshot must be an EngineeringInputSnapshot")
    engineering_hash = str(snapshot.engineering_hash or "")
    if not engineering_hash:
        raise ValueError("snapshot engineering_hash is required")
    return SnapshotValidationStage(
        snapshot=snapshot,
        engineering_hash=engineering_hash,
        valid=True,
        evidence={"schema_version": snapshot.schema_version},
    )


def _require_stage(
    value: Any,
    expected_type: type,
    *,
    stage_name: str,
    engineering_hash: str,
    family_id: str | None = None,
) -> Any:
    if not isinstance(value, expected_type):
        raise TypeError(f"{stage_name} must return {expected_type.__name__}")
    if str(value.engineering_hash or "") != str(engineering_hash or ""):
        raise ValueError(f"{stage_name} changed engineering_hash")
    if family_id is not None and str(value.family_id or "") != str(family_id or ""):
        raise ValueError(f"{stage_name} changed family_id")
    return value


_PROHIBITED_SELECTION_POLICY_TERMS = (
    "random",
    "stochastic",
    "first_fit",
    "first-fit",
    "until_pass",
    "until-pass",
    "try_until",
)


def _require_approved_policy(policy_id: str, *, stage_name: str) -> str:
    value = str(policy_id or "").strip()
    if not value:
        raise ValueError(f"{stage_name} requires an approved policy id")
    lowered = value.lower()
    if any(term in lowered for term in _PROHIBITED_SELECTION_POLICY_TERMS):
        raise ValueError(f"{stage_name} prohibits random or fit-until-pass policy")
    return value


def run_design_brain_pipeline(
    *,
    snapshot: EngineeringInputSnapshot,
    dependencies: DesignBrainPipelineDependencies,
) -> DesignBrainPipelineResult:
    """Run the only legal Design Brain stage sequence."""

    trace: list[str] = []
    validator = dependencies.snapshot_validation or validate_engineering_snapshot
    validated = validator(snapshot)
    if not isinstance(validated, SnapshotValidationStage):
        raise TypeError("snapshot_validation must return SnapshotValidationStage")
    if not validated.valid:
        raise ValueError("snapshot validation failed")
    if validated.snapshot is not snapshot:
        raise ValueError("snapshot validation replaced the immutable snapshot")
    if validated.engineering_hash != snapshot.engineering_hash:
        raise ValueError("snapshot validation changed engineering_hash")
    trace.append("snapshot_validation")

    intake = _require_stage(
        dependencies.engineering_result_intake(validated),
        EngineeringResultIntakeStage,
        stage_name="engineering_result_intake",
        engineering_hash=validated.engineering_hash,
    )
    if intake.snapshot is not snapshot:
        raise ValueError("engineering_result_intake replaced the immutable snapshot")
    trace.append("engineering_result_intake")

    classified = _require_stage(
        dependencies.governing_state_classification(intake),
        GoverningStateClassificationStage,
        stage_name="governing_state_classification",
        engineering_hash=validated.engineering_hash,
    )
    family_id = str(classified.family_id or "").strip()
    if not family_id:
        raise ValueError("governing_state_classification must select family_id")
    trace.append("governing_state_classification")

    dispatched = _require_stage(
        dependencies.family_dispatch(classified),
        FamilyDispatchStage,
        stage_name="family_dispatch",
        engineering_hash=validated.engineering_hash,
        family_id=family_id,
    )
    if not str(dispatched.strategy_owner or "").strip():
        raise ValueError("family_dispatch must identify strategy_owner")
    contract_id = str(dispatched.candidate_contract_id or "").strip()
    if not contract_id:
        raise ValueError("family_dispatch must identify candidate_contract_id")
    generation_policy_id = _require_approved_policy(
        dispatched.generation_policy_id,
        stage_name="family_dispatch generation",
    )
    evaluation_policy_id = _require_approved_policy(
        dispatched.evaluation_policy_id,
        stage_name="family_dispatch evaluation",
    )
    selection_policy_id = _require_approved_policy(
        dispatched.selection_policy_id,
        stage_name="family_dispatch selection",
    )
    trace.append("family_dispatch")

    generated = _require_stage(
        dependencies.candidate_generation(dispatched),
        CandidateGenerationStage,
        stage_name="candidate_generation",
        engineering_hash=validated.engineering_hash,
        family_id=family_id,
    )
    if str(generated.candidate_contract_id or "").strip() != contract_id:
        raise ValueError("candidate_generation changed candidate contract")
    if str(generated.generation_policy_id or "").strip() != generation_policy_id:
        raise ValueError("candidate_generation changed generation policy")
    candidate_ids: list[str] = []
    ordinals: list[int] = []
    for candidate in generated.candidates:
        if not isinstance(candidate, ApprovedCandidateProposal):
            raise TypeError("candidate_generation must emit ApprovedCandidateProposal")
        candidate_id = str(candidate.candidate_id or "").strip()
        if not candidate_id:
            raise ValueError("candidate_generation emitted candidate without id")
        if str(candidate.family_id or "") != family_id:
            raise ValueError("candidate_generation emitted candidate for another family")
        if str(candidate.candidate_contract_id or "") != contract_id:
            raise ValueError("candidate_generation emitted unapproved candidate contract")
        if not str(candidate.ladder_step_id or "").strip():
            raise ValueError("candidate_generation emitted candidate without ladder step")
        if not dict(candidate.updates or {}):
            raise ValueError("candidate_generation emitted candidate without updates")
        candidate_ids.append(candidate_id)
        ordinals.append(int(candidate.ordinal))
    if len(candidate_ids) != len(set(candidate_ids)):
        raise ValueError("candidate_generation emitted duplicate candidate ids")
    if len(ordinals) != len(set(ordinals)):
        raise ValueError("candidate_generation emitted duplicate ladder ordinals")
    if dispatched.terminal_family and candidate_ids:
        raise ValueError("terminal family cannot generate candidates")
    trace.append("candidate_generation")

    evaluated = _require_stage(
        dependencies.candidate_evaluation(generated),
        CandidateEvaluationStage,
        stage_name="candidate_evaluation",
        engineering_hash=validated.engineering_hash,
        family_id=family_id,
    )
    if str(evaluated.evaluation_policy_id or "").strip() != evaluation_policy_id:
        raise ValueError("candidate_evaluation changed evaluation policy")
    evaluation_ids: list[str] = []
    for evaluation in evaluated.evaluated_candidates:
        if not isinstance(evaluation, AuthoritativeCandidateEvaluation):
            raise TypeError(
                "candidate_evaluation must emit AuthoritativeCandidateEvaluation"
            )
        proposal = evaluation.proposal
        if proposal not in generated.candidates:
            raise ValueError("candidate_evaluation evaluated an unapproved proposal")
        if str(evaluation.engineering_hash or "") != validated.engineering_hash:
            raise ValueError("candidate_evaluation changed engineering_hash")
        if not str(evaluation.evaluator_id or "").strip():
            raise ValueError("candidate_evaluation requires evaluator_id")
        if not evaluation.executor_backed:
            raise ValueError("candidate_evaluation must use authoritative executor")
        if not isinstance(evaluation.rank_key, tuple):
            raise TypeError("candidate_evaluation requires deterministic rank_key")
        evaluation_ids.append(proposal.candidate_id)
    if evaluation_ids != candidate_ids:
        raise ValueError("candidate_evaluation must evaluate every approved candidate once")
    trace.append("candidate_evaluation")

    selected = _require_stage(
        dependencies.candidate_selection(evaluated),
        CandidateSelectionStage,
        stage_name="candidate_selection",
        engineering_hash=validated.engineering_hash,
        family_id=family_id,
    )
    if str(selected.selection_policy_id or "").strip() != selection_policy_id:
        raise ValueError("candidate_selection changed selection policy")
    deterministic_order = tuple(
        row.proposal.candidate_id
        for row in sorted(
            evaluated.evaluated_candidates,
            key=lambda row: (row.rank_key, row.proposal.candidate_id),
        )
    )
    if tuple(selected.ranked_candidate_ids) != deterministic_order:
        raise ValueError("candidate_selection ranking is not deterministic")
    if selected.selected_candidate is None and selected.no_candidate_outcome is None:
        raise ValueError(
            "candidate_selection requires selected_candidate or typed no_candidate_outcome"
        )
    if selected.selected_candidate is not None:
        if selected.selected_candidate not in evaluated.evaluated_candidates:
            raise ValueError("candidate_selection selected an unapproved evaluation")
        if not deterministic_order:
            raise ValueError("candidate_selection selected from an empty ranking")
        if selected.selected_candidate.proposal.candidate_id != deterministic_order[0]:
            raise ValueError("candidate_selection did not select approved top-ranked candidate")
        if selected.no_candidate_outcome is not None:
            raise ValueError("candidate_selection cannot publish candidate and no-candidate outcome")
    elif evaluated.evaluated_candidates:
        raise ValueError("candidate_selection cannot discard evaluated candidates")
    trace.append("candidate_selection")

    published = _require_stage(
        dependencies.publication_construction(selected),
        PublicationConstructionStage,
        stage_name="publication_construction",
        engineering_hash=validated.engineering_hash,
        family_id=family_id,
    )
    if not isinstance(published.result, AuthoritativeDesignResult):
        raise TypeError("publication_construction result must be AuthoritativeDesignResult")
    if published.result.engineering_hash != validated.engineering_hash:
        raise ValueError("publication_construction result changed engineering_hash")
    if str(published.result.governing_family or "") != family_id:
        raise ValueError("publication_construction result changed governing family")
    selected_evaluation = selected.selected_candidate
    if selected_evaluation is not None:
        proposal = selected_evaluation.proposal
        if dict(published.result.selected_updates or {}) != dict(proposal.updates):
            raise ValueError(
                "publication_construction changed selected candidate updates"
            )
        published_candidate = dict(published.result.selected_candidate or {})
        published_candidate_id = str(
            published_candidate.get("candidate_id")
            or published_candidate.get("source_candidate_id")
            or ""
        ).strip()
        if published_candidate_id != proposal.candidate_id:
            raise ValueError(
                "publication_construction changed selected candidate id"
            )
    elif dict(published.result.selected_updates or {}):
        raise ValueError(
            "publication_construction published updates without a selected candidate"
        )
    trace.append("publication_construction")

    applied = _require_stage(
        dependencies.apply_command_construction(published),
        ApplyCommandConstructionStage,
        stage_name="apply_command_construction",
        engineering_hash=validated.engineering_hash,
        family_id=family_id,
    )
    if not isinstance(applied.result, AuthoritativeDesignResult):
        raise TypeError("apply_command_construction result must be AuthoritativeDesignResult")
    if applied.result.engineering_hash != validated.engineering_hash:
        raise ValueError("apply_command_construction result changed engineering_hash")
    if str(applied.result.governing_family or "") != family_id:
        raise ValueError("apply_command_construction result changed governing family")
    command_updates = dict(
        applied.apply_command.get("updates")
        or applied.apply_command.get("resolved_candidate_updates")
        or {}
    )
    if selected_evaluation is not None:
        if command_updates != dict(selected_evaluation.proposal.updates):
            raise ValueError(
                "apply_command_construction changed selected candidate updates"
            )
    elif command_updates:
        raise ValueError(
            "apply_command_construction emitted updates without a selected candidate"
        )
    trace.append("apply_command_construction")

    if tuple(trace) != PIPELINE_STAGE_ORDER:
        raise RuntimeError("Design Brain pipeline stage order changed")
    return DesignBrainPipelineResult(
        result=applied.result,
        apply_command=dict(applied.apply_command),
        stage_trace=tuple(trace),
        engineering_hash=validated.engineering_hash,
        family_id=family_id,
    )


__all__ = [
    "ApplyCommandConstructionStage",
    "ApprovedCandidateProposal",
    "AuthoritativeCandidateEvaluation",
    "CandidateEvaluationStage",
    "CandidateGenerationStage",
    "CandidateSelectionStage",
    "DesignBrainPipelineDependencies",
    "DesignBrainPipelineResult",
    "EngineeringResultIntakeStage",
    "FamilyDispatchStage",
    "GoverningStateClassificationStage",
    "PIPELINE_STAGE_ORDER",
    "PublicationConstructionStage",
    "SnapshotValidationStage",
    "run_design_brain_pipeline",
    "validate_engineering_snapshot",
]
